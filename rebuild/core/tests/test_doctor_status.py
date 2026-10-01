"""Money wording: one status vocabulary for the doctor (core.doctor_status), a list of requests holding funds on the
billing page, and the right answer to a re-posted request while its earlier job is still pending.

Offline and synthetic: fixture generation, rows made directly. Wording only: amounts, settlement and the ledger are read,
never changed, and the tests check that no money row moves.
"""
import re
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from core import doctor_status as ds
from core.jobs import CANCELLED_ERROR, LATE_RECEIPT, NOT_ADOPTED, PLATFORM_FAILURE, billable_outcome
from core.models import Job, LedgerEntry, Reservation, Usage, Wallet
from . import test_workflow
from .test_workflow import TEST_SETTINGS

INTERNAL = re.compile(r'reconciliation|staged|validating|not_adopted|platform_failure|not_processed|administrator:|'
                      r'Resolved by|Worker stopped|automatic retry|Late provider evidence', re.I)
ADMIN_NOTES = ['Resolved by administrator: settled provider cost absorbed by QuillMD.',
               'Resolved by administrator: no provider cost evidenced.', LATE_RECEIPT,
               'Worker stopped with an unknown provider outcome. Automatic retry is disabled.',
               'Late provider evidence requires financial reconciliation; this attempt cannot run again.',
               'Batch request outcome requires reconciliation; it will not be sent again.']


class Mapping(TestCase):
    def job(self, state, error=''):
        return Job(state=state, error=error, kind='generation')

    def test_every_state_reads_in_the_doctor_s_words_without_internal_words_or_administrator_notes(self):
        cases = [('queued', ''), ('running', ''), ('staged', ''), ('validating', ''), ('succeeded', ''), ('cancelled', CANCELLED_ERROR),
                 ('failed', NOT_ADOPTED + 'Source or permission changed; output was not adopted.'),
                 ('failed', PLATFORM_FAILURE + 'The provider returned an error.'), ('failed', 'Access was revoked before processing.')]
        cases += [('reconciliation', note) for note in ADMIN_NOTES] + [('failed', note) for note in ADMIN_NOTES]
        for state, error in cases:
            with self.subTest(state=state, error=error[:40]):
                status = ds.doctor_status(self.job(state, error))
                self.assertIn(status.key, ds.LABELS)
                self.assertIsNone(INTERNAL.search(status.label + ' ' + status.explanation), status)
                self.assertNotEqual(status.key, 'unknown')
                self.assertEqual(status.charged, billable_outcome(self.job(state, error)))  # billing's predicate, not wording

    def test_pending_held_and_ended_states_say_what_happens_to_the_money(self):
        self.assertEqual(ds.doctor_status(self.job('queued')).label, 'Waiting to start')
        self.assertTrue(ds.doctor_status(self.job('running')).pending)
        held = ds.doctor_status(self.job('reconciliation', LATE_RECEIPT))
        self.assertEqual((held.label, held.pending), ('On hold for review', True))
        self.assertIn('within the maximum you approved', held.explanation)
        self.assertIn('remains charged', ds.doctor_status(self.job('failed', NOT_ADOPTED + 'Changed.')).explanation)
        self.assertIn('not charged to you', ds.doctor_status(self.job('failed', PLATFORM_FAILURE + 'Error.')).explanation)
        self.assertEqual(ds.doctor_status(self.job('cancelled', CANCELLED_ERROR)).explanation,
                         'Cancelled before any provider request; nothing was charged.')
        self.assertEqual(ds.doctor_status(self.job('mystery')).key, 'unknown')


@override_settings(**TEST_SETTINGS)
class Pages(TestCase):
    workflow = test_workflow.DocumentWorkflow
    setUp, make_docx, upload = workflow.setUp, workflow.make_docx, workflow.upload
    create_encounter = workflow.create_encounter
    NOTES = 'Symptoms: No chest pain.\nExamination: Normal gait.'

    def money(self):
        return (list(Reservation.objects.order_by('pk').values()), list(LedgerEntry.objects.order_by('pk').values()),
                list(Wallet.objects.order_by('pk').values('pk', 'balance', 'reserved')), Usage.objects.count())

    def test_a_stale_re_post_while_the_first_request_is_queued_says_so_not_answer_draft(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.NOTES)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/generate/').status_code, 302)
        job = Job.objects.get(encounter=encounter); self.assertEqual(job.state, 'queued')
        before = self.money()
        response = self.client.post(f'/encounters/{encounter.pk}/generate/', follow=True)
        text = response.content.decode()
        self.assertNotIn('already have an answer draft', text)  # ac43e379: it said so while the request was queued
        self.assertIn('was already made and is waiting to start. No new request was made and nothing more was charged.', text)
        self.assertEqual(Job.objects.filter(encounter=encounter).count(), 1); self.assertEqual(self.money(), before)
        # Once it has completed, the earlier answer is right.
        Job.objects.filter(pk=job.pk).update(state='succeeded')
        response = self.client.post(f'/encounters/{encounter.pk}/generate/', follow=True)
        self.assertContains(response, 'These source notes already have an answer draft from an earlier request.')
        # A charged completion keeps the page's own next step, not a generic status sentence.
        self.assertContains(response, 'The answer draft is ready below.')

    def test_the_document_page_shows_the_doctor_status_never_the_state_word_or_administrator_note(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.NOTES)
        Job.objects.create(encounter=encounter, user=self.user, request_key='held:1', state='reconciliation',
                           error='Worker stopped with an unknown provider outcome. Automatic retry is disabled.')
        page = self.client.get(f'/encounters/{encounter.pk}/').content.decode()
        self.assertIn('data-request-status="held">On hold for review</span>', page)
        self.assertNotIn('Automatic retry is disabled', page)  # ac43e379: the administrator's note, verbatim
        self.assertNotIn('>reconciliation<', page); self.assertNotIn('· reconciliation', page)  # list and latest-job notice
        self.assertIn('data-latest-job role="status"><strong>Generation · <span data-request-status="held">On hold for review</span>', page)
        self.assertIn('<dt>Status</dt><dd>Draft</dd>', page)
        self.assertIn('<span class="badge draft">Draft</span>', page)  # the heading badge, not the raw word

    def test_the_billing_page_lists_requests_holding_funds_with_their_status(self):
        _template, version = self.upload(self.make_docx(), 'docx')
        encounter = self.create_encounter(version, self.NOTES)
        wallet = Wallet.objects.get(user=self.user, kind='promo')
        job = Job.objects.create(encounter=encounter, user=self.user, request_key='held:2', state='reconciliation', error=LATE_RECEIPT)
        Reservation.objects.create(job=job, wallet=wallet, amount=Decimal('0.25'), state='held')
        settled = Job.objects.create(encounter=encounter, user=self.user, request_key='done:2', state='succeeded')
        Reservation.objects.create(job=settled, wallet=wallet, amount=Decimal('0.50'), state='settled')
        before = self.money()
        page = self.client.get('/billing/')
        self.assertEqual(page.status_code, 200)
        rows = page.context['held_requests']
        self.assertEqual([(row['job'].pk, row['amount'], row['status'].key) for row in rows], [(job.pk, Decimal('0.25'), 'held')])
        text = page.content.decode()
        self.assertIn('Requests holding funds', text); self.assertIn('data-held-request', text)
        self.assertIn('On hold for review', text); self.assertNotIn('an administrator must reconcile it', text)
        self.assertEqual(self.money(), before)  # read-only
        detail = self.client.get(f'/billing/jobs/{job.pk}/').content.decode()
        self.assertIn('data-request-status="held">On hold for review</span>', detail)
