"""Recording charge limit: the displayed maximum is binding, duration is measured and credit held before any paid request,
over-limit recordings are explained first, estimates that prove short are absorbed, and usable transcripts are delivered.

All data is synthetic. No provider, payment or console request leaves the test database.
"""
import json
import os
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from core import audio
from core.billing import reconcile_usage
from core.jobs import cancel, enqueue, run_one, transcription_quote
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, Job, LedgerEntry, Membership, PlatformCost, Reservation, Usage, User, Wallet
from core.security import private_path
from core.tests.audio_fixtures import wav_bytes
from core.tests.test_billing_boundary import LIVE, BoundaryFixture, deepgram
from core.tests.test_billing_policy import STORAGES

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'audio'
STANDARD_ENV = {'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.006', 'QUILLMD_DEEPGRAM_RATE_PER_SECOND': '', 'QUILLMD_VOICE_MAX_COST': '0.20',
                'QUILLMD_PROVIDER_DISCOUNT_RATE': '0', 'DEEPGRAM_API_KEY': 'synthetic-placeholder-not-a-key'}
# $60 per minute makes a one-second recording cost more than the $0.30 displayed limit, so the over-limit path is cheap to reach.
EXPENSIVE_ENV = dict(STANDARD_ENV, QUILLMD_DEEPGRAM_RATE_PER_MINUTE='60')
TRANSCRIPT = 'Synthetic transcript: patient reports a mild headache.'


class DurationIsMeasuredFromTheAudio(SimpleTestCase):
    def test_every_supported_format_measures_about_three_seconds_and_never_less(self):
        for name in ('tone-3s.wav', 'tone-3s.mp3', 'tone-3s.m4a', 'tone-3s-fragmented.m4a', 'tone-3s.webm', 'tone-3s-live.webm'):
            with self.subTest(name=name):
                seconds = audio.measure((FIXTURES / name).read_bytes())
                self.assertGreaterEqual(seconds, Decimal('3.0'))
                self.assertLessEqual(seconds, Decimal('3.2'))

    def test_wav_length_is_exact(self):
        self.assertEqual(audio.measure(wav_bytes(seconds=7, tag='exact')), Decimal('7.000'))

    def test_unmeasurable_input_is_refused_before_anything_is_sent(self):
        wav = wav_bytes(seconds=1, tag='compressed')
        compressed = wav[:20] + (2).to_bytes(2, 'little') + wav[22:]  # ADPCM tag: average byte rate only
        for data in (b'', b'RIFF synthetic test audio only', b'not audio at all', compressed, b'ID3\x04\x00\x00\x00\x00\x00\x00' + b'\x13\x37' * 400,
                     b'\x1aE\xdf\xa3' + b'\x00' * 64, b'\x00\x00\x00\x18ftypM4A ' + b'\x00' * 32):
            with self.subTest(data=data[:24]), self.assertRaises(audio.UnmeasurableRecording):
                audio.measure(data)

    def test_a_header_cannot_understate_an_mp4_recording(self):
        """Each AAC frame decodes to 1024 samples; a sample table claiming smaller deltas cannot shorten the measured length."""
        data = bytearray((FIXTURES / 'tone-3s.m4a').read_bytes())
        at = data.find(b'stts') + 4 + 8  # first (count, delta) entry
        count = int.from_bytes(data[at:at + 4], 'big')
        data[at + 4:at + 8] = (1).to_bytes(4, 'big')
        self.assertGreater(count, 10)
        self.assertGreaterEqual(audio.measure(bytes(data)), Decimal('2.9'))


class QuoteArithmetic(SimpleTestCase):
    def config(self, **values):
        base = {'voice_rate_minute': '0.006', 'voice_rate_second': '', 'voice_max_cost': '0.20', 'discount_rate': '0', 'pricing_version': 'test'}
        base.update(values)
        return base

    def test_limit_includes_the_margin_and_rounds_up_to_a_cent(self):
        quote = transcription_quote(Decimal('60'), self.config())
        # (60 × 1.02 + 2) s × $0.0001/s = $0.00632 cost → × 1.5 = $0.00948 → rounded up to $0.01.
        self.assertEqual(quote['charge_limit'], '0.01'); self.assertTrue(quote['within_standard'])
        self.assertEqual(quote['standard_limit'], '0.300')

    def test_the_length_that_fits_the_displayed_limit_is_consistent_with_the_quote(self):
        quote = transcription_quote(Decimal('0'), self.config())
        fits = Decimal(quote['fits_seconds'])
        self.assertTrue(transcription_quote(fits, self.config())['within_standard'])
        self.assertFalse(transcription_quote(fits + 60, self.config())['within_standard'])

    def test_a_zero_rate_costs_and_holds_nothing(self):
        self.assertEqual(transcription_quote(Decimal('30'), self.config(voice_rate_minute='0'))['charge_limit'], '0')


@override_settings(ADMIN_SITE=False, STORAGES=STORAGES, **LIVE)
class RecordingChargeLimit(BoundaryFixture, TestCase):
    def upload(self, env, tag='rec', seconds=1, client=None):
        client = client or self.client
        with patch.dict(os.environ, env):
            page = client.get(f'/encounters/{self.encounter.pk}/')
            return client.post(f'/encounters/{self.encounter.pk}/voice/', {
                'audio': SimpleUploadedFile(f'{tag}.wav', wav_bytes(seconds=seconds, tag=tag), content_type='audio/wav'),
                'consent': 'on', 'usage_quote': page.context['usage_quote']})

    def approve(self, response, decision='approve', env=EXPENSIVE_ENV, client=None):
        with patch.dict(os.environ, env):
            return (client or self.client).post(f'/encounters/{self.encounter.pk}/voice/approve/',
                                               {'approval': response.context['approval'], 'decision': decision})

    def process(self, response_or_job, env=STANDARD_ENV, **provider):
        job = response_or_job if isinstance(response_or_job, Job) else Job.objects.get(encounter=self.encounter, state='queued')
        with patch.dict(os.environ, env), patch('core.jobs.httpx.post', **provider) as post:
            self.assertTrue(run_one())
        job.refresh_from_db()
        return job, post

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_within_the_displayed_limit_it_holds_its_own_exact_limit_and_is_processed(self):
        response = self.upload(STANDARD_ENV)
        self.assertEqual(response.status_code, 302)
        job = Job.objects.get(encounter=self.encounter, kind='transcription')
        self.assertEqual(job.config['limit_basis'], 'standard'); self.assertEqual(job.config['recording_seconds'], '1.000')
        self.assertEqual(Decimal(job.config['charge_limit']), Decimal('0.01'))
        self.assertEqual(sum(r.amount for r in Reservation.objects.filter(job=job)), Decimal('0.01'))
        job, post = self.process(job, return_value=deepgram(TRANSCRIPT, 'dg_limit_within', duration=1))
        self.assertEqual(post.call_count, 1); self.assertEqual(job.state, 'succeeded')
        usage = Usage.objects.get(job=job); self.assertEqual(usage.charged_cost, usage.actual_cost * Decimal('1.5'))
        self.assertFalse(PlatformCost.objects.exists()); self.assertTrue(audit_report()['all_checks_pass'])

    def test_the_voice_form_states_the_limit_and_the_length_that_fits(self):
        with patch.dict(os.environ, STANDARD_ENV):
            page = self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertContains(page, 'Limit $0.30 per recording, which fits recordings up to')
        self.assertContains(page, 'never more than the limit')

    def test_over_the_limit_nothing_is_sent_and_the_choice_is_explained_first(self):
        with patch('core.jobs.httpx.post') as post:
            response = self.upload(EXPENSIVE_ENV)
        self.assertEqual(response.status_code, 409); self.assertEqual(post.call_count, 0)
        self.assertFalse(Job.objects.filter(kind='transcription').exists()); self.assertFalse(Reservation.objects.exists())
        self.assertContains(response, 'Nothing was sent', status_code=409)
        self.assertContains(response, 'Approve a limit of $4.53 and transcribe', status_code=409)
        self.assertContains(response, 'Upload a shorter segment instead', status_code=409)
        self.assertTrue(AuditEvent.objects.filter(action='voice.over_limit_quoted', target=str(self.encounter.pk)).exists())
        kept = list(private_path('audio').iterdir()); self.assertEqual(len(kept), 1)  # the upload is kept for the decision

    def test_an_approved_higher_limit_is_held_exactly_and_charged_at_most(self):
        response = self.upload(EXPENSIVE_ENV)
        approved = self.approve(response)
        self.assertEqual(approved.status_code, 302)
        job = Job.objects.get(encounter=self.encounter, kind='transcription')
        self.assertEqual(job.config['limit_basis'], 'approved'); self.assertEqual(job.config['charge_limit'], '4.53')
        self.assertEqual(sum(r.amount for r in Reservation.objects.filter(job=job)), Decimal('4.53'))
        self.assertTrue(AuditEvent.objects.filter(action='voice.limit_approved', target=str(job.pk)).exists())
        job, _ = self.process(job, env=EXPENSIVE_ENV, return_value=deepgram(TRANSCRIPT, 'dg_limit_approved', duration=1))
        usage = Usage.objects.get(job=job)
        self.assertEqual(usage.actual_cost, Decimal('1')); self.assertEqual(usage.charged_cost, Decimal('1.5'))
        self.assertEqual(self.balances(), (Decimal('8.5'), Decimal('0'))); self.assertTrue(audit_report()['all_checks_pass'])

    def test_choosing_a_shorter_segment_sends_nothing_and_removes_the_upload(self):
        response = self.upload(EXPENSIVE_ENV)
        declined = self.approve(response, decision='shorter')
        self.assertEqual(declined.status_code, 302)
        self.assertFalse(Job.objects.filter(kind='transcription').exists()); self.assertEqual(list(private_path('audio').iterdir()), [])

    def test_an_approval_is_bound_to_its_user_document_version_and_recording(self):
        response = self.upload(EXPENSIVE_ENV)
        # Another clinician of the same department cannot spend this doctor's approval.
        other = User.objects.create_user(username='limit-other', email='limit-other@synthetic.invalid', verified_at=timezone.now())
        Membership.objects.create(user=other, department=self.encounter.department, role='clinician')
        from django.test import Client
        stranger = Client(); stranger.force_login(other)
        self.assertEqual(self.approve(response, client=stranger).status_code, 403)
        # A forged approval is refused.
        with patch.dict(os.environ, EXPENSIVE_ENV):
            forged = self.client.post(f'/encounters/{self.encounter.pk}/voice/approve/', {'approval': response.context['approval'] + 'x', 'decision': 'approve'})
        self.assertEqual(forged.status_code, 302)
        # A changed recording is refused.
        path = next(private_path('audio').iterdir()); original = path.read_bytes()
        path.write_bytes(wav_bytes(seconds=1, tag='swapped'))
        self.approve(response)
        self.assertFalse(Job.objects.filter(kind='transcription').exists())
        path.write_bytes(original)
        # A changed document version is refused.
        type(self.encounter).objects.filter(pk=self.encounter.pk).update(revision=self.encounter.revision + 1)
        self.approve(response)
        self.assertFalse(Job.objects.filter(kind='transcription').exists()); self.assertFalse(Reservation.objects.exists())

    def test_another_department_cannot_use_the_approval_endpoint(self):
        response = self.upload(EXPENSIVE_ENV)
        other_scope = self.make_scope('limit-foreign')
        from django.test import Client
        foreign = Client(); foreign.force_login(other_scope[0])
        self.assertEqual(self.approve(response, client=foreign).status_code, 404)

    def test_insufficient_credit_is_explained_before_anything_is_sent(self):
        Wallet.objects.filter(pk=self.promo.pk).update(balance=Decimal('1'))
        LedgerEntry.objects.none()
        response = self.upload(EXPENSIVE_ENV)
        self.assertContains(response, 'Your available balance is below this limit', status_code=409)
        self.assertNotContains(response, 'Approve a limit of', status_code=409)
        with patch.dict(os.environ, EXPENSIVE_ENV), patch('core.jobs.httpx.post') as post:
            self.approve(response)
        self.assertEqual(post.call_count, 0); self.assertFalse(Job.objects.filter(kind='transcription').exists())
        Wallet.objects.filter(pk=self.promo.pk).update(balance=Decimal('0.001'))
        with patch('core.jobs.httpx.post') as post:
            self.upload(STANDARD_ENV, tag='cheap')
        self.assertEqual(post.call_count, 0); self.assertFalse(Job.objects.filter(kind='transcription').exists())
        messages = [str(m) for m in self.client.get(f'/encounters/{self.encounter.pk}/').context['messages']]
        self.assertTrue(any('needs up to $0.01 held' in m for m in messages), messages)

    def test_a_recording_longer_than_the_hard_maximum_is_refused_and_not_kept(self):
        env = dict(STANDARD_ENV, QUILLMD_VOICE_MAX_MINUTES='0.01')
        with patch('core.jobs.httpx.post') as post:
            response = self.upload(env)
        self.assertEqual(response.status_code, 302); self.assertEqual(post.call_count, 0)
        self.assertFalse(Job.objects.filter(kind='transcription').exists()); self.assertEqual(list(private_path('audio').iterdir()), [])

    def test_cancelling_an_approved_request_releases_the_whole_limit(self):
        self.approve(self.upload(EXPENSIVE_ENV))
        job = Job.objects.get(encounter=self.encounter, kind='transcription')
        self.promo.refresh_from_db(); self.assertEqual(self.promo.reserved, Decimal('4.53'))
        cancel(job, self.user)
        self.promo.refresh_from_db(); self.assertEqual(self.promo.reserved, 0); self.assertEqual(self.promo.balance, Decimal('10'))
        self.assertFalse(Usage.objects.filter(job=job).exists()); self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_provider_failure_holds_the_limit_and_a_retry_is_charged_once(self):
        response = self.upload(EXPENSIVE_ENV)
        self.approve(response)
        job = Job.objects.get(encounter=self.encounter, kind='transcription')
        job, _ = self.process(job, env=EXPENSIVE_ENV, side_effect=TimeoutError('synthetic provider timeout'))
        self.assertEqual(job.state, 'reconciliation'); self.promo.refresh_from_db(); self.assertEqual(self.promo.reserved, Decimal('4.53'))
        # An unusable transcript after settlement is a platform failure: absorbed, and the key is freed for a retry.
        second = self.upload(STANDARD_ENV, tag='retry')
        self.assertIn('pending job', ' '.join(str(m) for m in self.client.get(f'/encounters/{self.encounter.pk}/').context['messages']))
        Job.objects.filter(pk=job.pk).update(state='failed', error='Resolved by administrator: no provider cost evidenced.',
                                             request_key=job.request_key + ':failed:' + job.pk.hex)
        from core.billing import release
        release(job)
        retry = self.upload(STANDARD_ENV, tag='retry')
        fresh = Job.objects.get(encounter=self.encounter, state='queued')
        fresh, _ = self.process(fresh, return_value=deepgram(None, 'dg_limit_unusable', duration=1))
        self.assertTrue(fresh.error.startswith('platform_failure: ')); self.assertTrue(LedgerEntry.objects.filter(job=fresh, kind='absorbed').exists())
        again = self.upload(STANDARD_ENV, tag='retry')
        final = Job.objects.get(encounter=self.encounter, state='queued')
        final, _ = self.process(final, return_value=deepgram(TRANSCRIPT, 'dg_limit_retry_ok', duration=1))
        self.assertEqual(final.state, 'succeeded')
        charged = Usage.objects.get(job=final).charged_cost
        self.assertEqual(self.balances(), (Decimal('10') - charged, Decimal('0'))); self.assertTrue(audit_report()['all_checks_pass'])

    def test_a_short_provider_duration_is_labelled_incomplete_never_silently_truncated(self):
        self.upload(STANDARD_ENV, seconds=60, tag='partial')
        job, _ = self.process(None or Job.objects.get(encounter=self.encounter, state='queued'),
                              return_value=deepgram(TRANSCRIPT, 'dg_limit_partial', duration=20))
        self.assertEqual(job.state, 'succeeded')
        self.encounter.refresh_from_db()
        self.assertIn(TRANSCRIPT, self.encounter.notes)
        self.assertIn('[Transcription incomplete: the provider processed 0:20 of this 1:00 recording; the final 0:40 was not transcribed.]', self.encounter.notes)

    def test_a_duplicate_submission_is_one_job_and_one_hold(self):
        self.upload(STANDARD_ENV, tag='same')
        self.upload(STANDARD_ENV, tag='same')
        self.assertEqual(Job.objects.filter(kind='transcription').count(), 1); self.assertEqual(Reservation.objects.count(), 1)

    def test_reconciliation_never_raises_the_customer_charge_above_the_limit(self):
        self.upload(STANDARD_ENV, tag='reconcile')
        job, _ = self.process(Job.objects.get(encounter=self.encounter, state='queued'),
                              return_value=deepgram(TRANSCRIPT, 'dg_limit_reconcile', duration=6000))
        usage = Usage.objects.get(job=job)
        self.assertEqual(usage.charged_cost, Decimal('0.01')); self.assertEqual(PlatformCost.objects.get(job=job, kind='absorbed_over_limit').amount, Decimal('0.89'))
        row = reconcile_usage(usage, Decimal('0.8'), 'INV-SYNTH-LIMIT', self.user)
        self.assertEqual(row.charge_delta, 0); self.assertEqual(row.over_limit_delta, Decimal('0.3'))
        self.assertFalse(LedgerEntry.objects.filter(kind='reconciliation').exists())
        self.assertEqual(self.balances(), (Decimal('9.99'), Decimal('0')))
        report = audit_report(); self.assertTrue(report['all_checks_pass'])

    def test_welcome_credit_is_unchanged_by_the_limit(self):
        self.assertEqual(self.balances(), (Decimal('10'), Decimal('0')))
        self.assertEqual(LedgerEntry.objects.filter(wallet=self.promo, kind='welcome').count(), 1)
