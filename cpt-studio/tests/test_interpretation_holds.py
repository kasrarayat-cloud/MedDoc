"""The installation-wide interpreter hold (Gemini migration slice S07; design/FINAL.md 4.1, 6.3, 11.1 and 11.2; DECISIONS
D11; design/ADJUDICATION.md P-3, P-4 and P-5): the classify table, a hold recorded with exactly what the adapter's
classification read and never re-classified, its release by an operator with a note, the paused state, and the
``interpreter_hold`` command. Synthetic data only; nothing is sent.

The error bodies are S06's synthetic shapes (tests.test_interpretation_adapter) and the trial's own recorded 429 body,
which carries PerDay and PerMinute violations together (a hold, P-4).
"""
from __future__ import annotations

import dataclasses
import hashlib
import io
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from studio import interpretation, models, operator
from studio.interpretation import adapter, holds, read, store
from studio.types import sha256_json
from tests.support import factories as f
from tests.test_interpretation_adapter import (PER_DAY, PER_MINUTE, TRIAL_429, encoded, envelope, error_body,
                                               error_info, quota_failure, retry_info, violation, with_parts)

TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Date of service: 2026-10-21\n'
        'Colonoscopy: The colonoscope was advanced to the cecum. A 6 mm polyp was removed with a cold snare.\n')
OK_BODY = encoded(envelope())
NOTE = 'Synthetic release: billing was restored on the synthetic project and the key re-issued.'


def substituted() -> bytes:
    return encoded(envelope(modelVersion='gemini-4-argon-preview'))


def unnamed() -> bytes:
    value = envelope()
    del value['modelVersion']
    return encoded(value)


# (label, state, http_status, body, effect, reason): FINAL 11.1 as P-3, P-4, P-5 and C5 amend it
TABLE = (
    ('401, whatever the body', 'failed', 401, b'<html>no</html>', holds.HOLD, holds.AUTH),
    ('403, whatever the body', 'failed', 403, b'', holds.HOLD, holds.PERMISSION),
    ('API_KEY_INVALID on a 400', 'failed', 400, error_body(400, 'INVALID_ARGUMENT', error_info('API_KEY_INVALID')),
     holds.HOLD, holds.AUTH),
    ('BILLING_DISABLED on a 403', 'failed', 403, error_body(403, 'PERMISSION_DENIED', error_info('BILLING_DISABLED')),
     holds.HOLD, holds.QUOTA),
    ('the trial\'s 429 (PerDay with PerMinute, free tier)', 'failed', 429, TRIAL_429.read_bytes(), holds.HOLD,
     holds.QUOTA),
    ('a daily quota', 'failed', 429, error_body(429, 'RESOURCE_EXHAUSTED', quota_failure(violation(PER_DAY))),
     holds.HOLD, holds.QUOTA),
    ('another model answered (P-5)', 'succeeded', 200, substituted(), holds.HOLD, holds.MODEL),
    ('no model named (P-5)', 'succeeded', 200, unnamed(), holds.HOLD, holds.MODEL),
    ('a per-minute rate limit', 'failed', 429,
     error_body(429, 'RESOURCE_EXHAUSTED', quota_failure(violation(PER_MINUTE, quotaValue='1000')), retry_info('17s')),
     holds.FAILED, ''),
    ('a 429 with no QuotaFailure', 'failed', 429, error_body(429, 'RESOURCE_EXHAUSTED'), holds.FAILED, ''),
    ('a 5xx', 'failed', 503, error_body(503, 'UNAVAILABLE'), holds.FAILED, ''),
    ('a 400 INVALID_ARGUMENT without a hold name', 'failed', 400, error_body(400, 'INVALID_ARGUMENT'), holds.FAILED, ''),
    ('a refused finish reason', 'succeeded', 200, encoded(with_parts({'text': '{}'}, finish='SAFETY')), holds.FAILED,
     ''),
    ('an envelope that is not JSON', 'succeeded', 200, b'not json', holds.FAILED, ''),
    ('cut off at the output limit (C5)', 'succeeded', 200, encoded(with_parts({'text': '{'}, finish='MAX_TOKENS')),
     holds.TOO_LONG, ''),
    ('a usable answer', 'succeeded', 200, OK_BODY, holds.ANSWERED, ''),
)


class ClassifyTableTests(SimpleTestCase):
    def test_every_row_of_the_table(self):
        for label, state, status, body, effect, reason in TABLE:
            with self.subTest(label):
                outcome = holds.classify(state, status, body)
                self.assertEqual((outcome.effect, outcome.reason), (effect, reason))
                self.assertEqual(outcome.retry, effect == holds.FAILED)
                for named in ('gemini', 'google', 'argon'):
                    self.assertNotIn(named, outcome.why.lower())

    def test_a_definite_outcome_is_the_adapters_classification_unchanged(self):
        # one classifier (ADJUDICATION P-3 to P-5 assign it to the adapter): every field the hold records is the
        # adapter's own reading of the same response
        for label, state, status, body, _, _ in TABLE:
            with self.subTest(label):
                outcome = holds.classify(state, status, body)
                self.assertEqual(outcome.verdict, adapter.classify(state, status, body))
                if outcome.effect != holds.ANSWERED:
                    self.assertEqual(outcome.why, outcome.verdict.why)

    def test_holds_never_reads_a_response_itself(self):
        # whatever the adapter says is what the hold table says: a planted classification passes straight through
        planted = adapter.Classification(adapter.HOLD, hold=adapter.QUOTA, http_status=599, vendor_status='PLANTED',
                                         violations=({'quotaId': 'planted'},), why='Planted.')
        with mock.patch.object(adapter, 'classify', return_value=planted) as classify:
            outcome = holds.classify('failed', 200, OK_BODY)
        classify.assert_called_once_with('failed', 200, OK_BODY)
        self.assertIs(outcome.verdict, planted)
        self.assertEqual((outcome.effect, outcome.reason, outcome.why), (holds.HOLD, holds.QUOTA, 'Planted.'))
        with mock.patch.object(adapter, 'classify', return_value=None):
            self.assertEqual(holds.classify('failed', 401, b'').effect, holds.NONE)

    def test_a_refused_reading_fails_the_attempt_but_never_changes_a_hold_or_a_cut_off_answer(self):
        refusal = read.refuse('schema', 'its answer does not have the shape this version reads')
        outcome = holds.classify('succeeded', 200, OK_BODY, refused=refusal)
        self.assertEqual((outcome.effect, outcome.why, outcome.retry), (holds.FAILED, refusal.reason, True))
        self.assertEqual(outcome.verdict.kind, adapter.ANSWERED)  # the adapter's verdict is kept as it was
        for body, effect in ((substituted(), holds.HOLD), (encoded(with_parts({'text': '{'}, finish='MAX_TOKENS')),
                                                           holds.TOO_LONG)):
            with self.subTest(effect=effect):
                self.assertEqual(holds.classify('succeeded', 200, body, refused=refusal).effect, effect)

    def test_an_unknown_outcome_is_reconciled_and_nothing_else_is_an_outcome(self):
        unknown = holds.classify(models.ProviderRun.UNKNOWN, None, b'')
        self.assertEqual((unknown.effect, unknown.verdict, unknown.retry), (holds.UNKNOWN, None, False))
        self.assertEqual(unknown.why, holds.UNKNOWN_WHY)
        for state in ('not_sent', 'cancelled', 'reserved', 'sending', '', None):
            with self.subTest(state=state):
                outcome = holds.classify(state, None, b'')
                self.assertEqual((outcome.effect, outcome.verdict, outcome.retry), (holds.NONE, None, False))

    def test_the_reasons_are_the_hold_tables_and_the_adapters(self):
        self.assertEqual(holds.REASONS, adapter.HOLD_REASONS)
        self.assertEqual(holds.REASONS, (models.InterpreterHold.AUTH, models.InterpreterHold.PERMISSION,
                                         models.InterpreterHold.QUOTA, models.InterpreterHold.MODEL))
        self.assertEqual(set(holds.REASON_TEXT), set(holds.REASONS))
        self.assertIn('model', holds.REASONS)  # P-5

    def test_an_outcome_is_one_of_the_table(self):
        hold = adapter.classify('failed', 401, b'')
        failed = adapter.classify('failed', 503, b'')
        for build in (lambda: holds.Outcome('retry'), lambda: holds.Outcome(holds.HOLD, failed),
                      lambda: holds.Outcome(holds.UNKNOWN, hold), lambda: holds.Outcome(holds.FAILED),
                      lambda: holds.Outcome(holds.HOLD, dataclasses.replace(hold, hold='other'))):
            with self.assertRaises(ValueError):
                build()

    def test_the_paused_message_and_scope_marks_are_finals(self):
        self.assertEqual(holds.PAUSED_MESSAGE, 'Reading documented procedures is paused on this installation. Nothing '
                                               'was sent. Resume once it is available again.')
        self.assertEqual((holds.HELD_DISABLED, holds.HELD_HOLD), ('interpreter_disabled', 'interpreter_hold'))


# --- rows ---------------------------------------------------------------------------------------------------------------

def scene():
    ws = f.workspace()
    usr = f.member(ws)
    enc = f.encounter(ws, usr)
    rev = f.pasted_revision(enc, usr, TEXT)
    return ws, usr, enc, rev


def gemini_run(enc, rev, *, state='failed', http_status=401, body=b'', provider=interpretation.PROVIDER,
               purpose=interpretation.PURPOSE):
    request = {'systemInstruction': {'parts': [{'text': 'synthetic'}]}, 'contents': [{'parts': [{'text': rev.text}]}],
               'generationConfig': {'temperature': 0}}
    return models.ProviderRun.objects.create(
        encounter=enc, revision=rev, provider=provider, adapter_version=interpretation.ADAPTER_VERSION, purpose=purpose,
        request_sha256=sha256_json(request), request_body=request, contexts=[], state=state, sent=True,
        http_status=http_status, response_bytes=body, response_sha256=hashlib.sha256(body).hexdigest())


def reused(prior):
    """A reuse of ``prior`` as jobs' reuse doors write one (jobs._reused_participant_run): the whole run, nothing sent,
    its bytes copied, reused_from it."""
    return models.ProviderRun.objects.create(
        encounter=prior.encounter, revision=prior.revision, provider=prior.provider,
        adapter_version=prior.adapter_version, purpose=prior.purpose, request_sha256=prior.request_sha256,
        request_body=prior.request_body, contexts=prior.contexts, state=models.ProviderRun.SUCCEEDED, sent=False,
        http_status=prior.http_status, response_sha256=prior.response_sha256,
        response_bytes=bytes(prior.response_bytes), usage={}, reused_from=prior)


def an_operator(username='synthetic-operator'):
    user = f.user(username)
    operator.grant(user, 'Synthetic grant for an interpreter-hold test.', 'tests')
    return user


class HoldRecordTests(TestCase):
    def setUp(self):
        self.ws, self.usr, self.enc, self.rev = scene()

    def test_a_hold_records_exactly_what_the_adapter_read(self):
        raw = TRIAL_429.read_bytes()
        run = gemini_run(self.enc, self.rev, http_status=429, body=raw)
        outcome, hold = holds.settle(run)
        verdict = adapter.classify('failed', 429, raw)
        self.assertEqual(outcome.effect, holds.HOLD)
        stored = models.InterpreterHold.objects.get(pk=hold.pk)
        self.assertEqual((stored.reason, stored.http_status, stored.vendor_status, stored.run_id),
                         (verdict.hold, verdict.http_status, verdict.vendor_status, run.pk))
        self.assertEqual(stored.violations, [dict(item) for item in verdict.violations])
        self.assertEqual(len(stored.violations), 4)  # PerDay and PerMinute together: a hold (P-4)

    def test_each_reason_is_recorded_from_its_answer(self):
        for status, body, reason, vendor in ((401, b'', holds.AUTH, ''),
                                             (403, error_body(403, 'PERMISSION_DENIED'), holds.PERMISSION,
                                              'PERMISSION_DENIED'),
                                             (429, error_body(429, 'RESOURCE_EXHAUSTED',
                                                              quota_failure(violation(PER_DAY))), holds.QUOTA,
                                              'RESOURCE_EXHAUSTED')):
            with self.subTest(reason=reason):
                _, hold = holds.settle(gemini_run(self.enc, self.rev, http_status=status, body=body))
                self.assertEqual((hold.reason, hold.http_status, hold.vendor_status), (reason, status, vendor))
        _, hold = holds.settle(gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=substituted()))
        self.assertEqual((hold.reason, hold.http_status, hold.vendor_status, hold.violations),
                         (holds.MODEL, 200, '', []))  # P-5: a substituted model holds the installation

    def test_a_run_sets_at_most_one_hold_even_after_its_release(self):
        run = gemini_run(self.enc, self.rev)
        _, first = holds.settle(run)
        _, again = holds.settle(run)
        self.assertEqual(first, again)
        holds.release(user=an_operator(), note=NOTE)
        outcome, after = holds.settle(run)  # a stale sweep settling the same run again never stands a new hold ...
        self.assertEqual((outcome.effect, after), (holds.HOLD, None))  # ... and reports none standing
        self.assertEqual(holds.record(run, outcome), first)  # the answer's hold, released
        self.assertEqual(models.InterpreterHold.objects.filter(run=run).count(), 1)
        self.assertFalse(holds.is_held())

    def test_one_answer_sets_one_hold_whichever_run_carries_it(self):
        # a reuse door copies a SUCCEEDED run's answer and sends nothing; a substituted model's answer is SUCCEEDED, so
        # every Resume that reuses it would hold the installation again with nothing sent
        sent = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=substituted())
        outcome, first = holds.settle(sent)
        self.assertEqual((outcome.effect, outcome.reason, first.run_id), (holds.HOLD, holds.MODEL, sent.pk))
        copy = reused(sent)
        outcome, standing = holds.settle(copy)
        self.assertEqual((outcome.effect, standing), (holds.HOLD, first))  # the answer's own hold, still standing
        holds.release(user=an_operator(), note=NOTE)
        for run in (copy, reused(sent), sent):  # every later Resume re-reading the released answer
            with self.subTest(run=str(run.pk), sent=run.sent):
                outcome, standing = holds.settle(run)
                self.assertEqual((outcome.effect, standing), (holds.HOLD, None))
                self.assertEqual(holds.record(run, outcome), first)
        self.assertEqual(models.InterpreterHold.objects.count(), 1)
        self.assertFalse(holds.is_held())
        # a run that was not sent sets no hold of its own, even when its origin's answer set none
        unsettled = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=substituted())
        outcome, standing = holds.settle(reused(unsettled))
        self.assertEqual((outcome.effect, standing), (holds.HOLD, None))
        self.assertEqual(models.InterpreterHold.objects.count(), 1)
        self.assertFalse(holds.is_held())

    def test_a_definite_failure_or_an_answer_sets_no_hold(self):
        for state, status, body in (('failed', 429, error_body(429, 'RESOURCE_EXHAUSTED',
                                                                quota_failure(violation(PER_MINUTE)))),
                                    ('failed', 500, error_body(500, 'INTERNAL')),
                                    ('succeeded', 200, OK_BODY),
                                    ('unknown', None, b''), ('not_sent', None, b'')):
            with self.subTest(state=state, status=status):
                outcome, hold = holds.settle(gemini_run(self.enc, self.rev, state=state, http_status=status, body=body))
                self.assertIsNone(hold)
                self.assertNotEqual(outcome.effect, holds.HOLD)
        self.assertEqual(models.InterpreterHold.objects.count(), 0)

    def test_a_refused_inventory_makes_a_usable_answer_a_failure_with_its_reason(self):
        run = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=OK_BODY)
        refusal = read.refuse('bounds', 'its answer holds more events than this version reads')
        fields = store.refused_row(refusal, encounter_id=self.enc.pk, revision_id=self.rev.pk, provider_run_id=run.pk,
                                   text_sha256=self.rev.text_sha256, request_sha256=run.request_sha256,
                                   response_sha256=run.response_sha256)
        inventory = models.EventInventory.objects.create(**fields)
        outcome, hold = holds.settle(run, inventory=inventory)
        self.assertEqual((outcome.effect, outcome.why, outcome.retry, hold), (holds.FAILED, refusal.reason, True, None))
        self.assertEqual(holds.classify_run(run).effect, holds.ANSWERED)  # without the inventory: as the adapter read it
        other = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=OK_BODY)
        with self.assertRaises(ValueError):
            holds.classify_run(other, inventory=inventory)

    def test_only_an_interpretation_run_is_classified_or_holds(self):
        hold = holds.Outcome(holds.HOLD, adapter.classify('failed', 401, b''), 'held')
        for provider, purpose in (('corti', 'primary'), (interpretation.PROVIDER, 'primary'), ('astra', 'independent')):
            run = gemini_run(self.enc, self.rev, provider=provider, purpose=purpose)
            with self.subTest(provider=provider, purpose=purpose):
                with self.assertRaises(ValueError):
                    holds.classify_run(run)
                with self.assertRaises(ValueError):
                    holds.record(run, hold)
        with self.assertRaises(ValueError):
            holds.record(gemini_run(self.enc, self.rev), holds.classify('failed', 503, b''))
        self.assertEqual(models.InterpreterHold.objects.count(), 0)

    def test_the_paused_reason_follows_the_mode_and_the_hold(self):
        with override_settings(GEMINI_MODE='disabled'):
            self.assertEqual(holds.paused_reason(), holds.HELD_DISABLED)  # D11 refined: disabled is treated as a hold
        with override_settings(GEMINI_MODE='live'):
            self.assertIsNone(holds.paused_reason())
            _, older = holds.settle(gemini_run(self.enc, self.rev))
            _, newer = holds.settle(gemini_run(self.enc, self.rev, http_status=403))
            self.assertEqual(holds.paused_reason(), holds.HELD_HOLD)
            self.assertTrue(holds.is_held())
            self.assertEqual(list(holds.active()), [older, newer])
            self.assertEqual(holds.current(), newer)
            found = holds.state()
            self.assertEqual((found['held'], found['process_mode'], found['process_paused'], found['message']),
                             (True, 'live', holds.HELD_HOLD, holds.PAUSED_MESSAGE))
            self.assertEqual([item['id'] for item in found['standing']], [str(older.pk), str(newer.pk)])
            self.assertEqual({key: found['standing'][0][key] for key in ('reason', 'http_status', 'run', 'released_at')},
                             {'reason': 'auth', 'http_status': 401, 'run': str(older.run_id), 'released_at': None})
            holds.release(user=an_operator(), note=NOTE)
            self.assertIsNone(holds.paused_reason())
            self.assertEqual((holds.state()['standing'], holds.state()['held']), ([], False))
        with override_settings(GEMINI_MODE='replay'):
            self.assertIsNone(holds.paused_reason())

    def test_the_state_names_the_process_mode_apart_from_the_installations_hold(self):
        # a one-shot runs with the interpreter disabled unless given a mode (FINAL 13): its own mode is not the worker's,
        # and nothing in the state presents it as the installation's
        with override_settings(GEMINI_MODE='disabled'):
            found = holds.state()
            self.assertEqual((found['held'], found['standing'], found['process_mode'], found['process_paused']),
                             (False, [], 'disabled', holds.HELD_DISABLED))
            self.assertNotIn('mode', found)
            self.assertNotIn('paused', found)
            holds.settle(gemini_run(self.enc, self.rev))
            self.assertEqual((holds.state()['held'], holds.state()['process_paused']), (True, holds.HELD_DISABLED))

    def test_describe_names_the_reason_statuses_and_run(self):
        raw = TRIAL_429.read_bytes()
        _, hold = holds.settle(gemini_run(self.enc, self.rev, http_status=429, body=raw))
        line = holds.describe(hold)
        for part in (str(hold.pk), 'quota', 'HTTP 429', 'RESOURCE_EXHAUSTED', '4 quota violations', str(hold.run_id)):
            self.assertIn(part, line)


class ReleaseTests(TestCase):
    def setUp(self):
        self.ws, self.usr, self.enc, self.rev = scene()
        self.operator = an_operator()

    def hold(self, status=401):
        return holds.settle(gemini_run(self.enc, self.rev, http_status=status))[1]

    def test_an_operator_ends_every_standing_hold_with_a_note_and_the_holds_stay(self):
        first, second = self.hold(401), self.hold(403)
        released = holds.release(user=self.operator, note=f'  {NOTE}\n')
        self.assertEqual([item.hold for item in released], [first, second])
        for item in released:
            stored = models.InterpreterHoldRelease.objects.get(pk=item.pk)
            self.assertEqual((stored.released_by, stored.note), (self.operator, NOTE))
        self.assertEqual(models.InterpreterHold.objects.count(), 2)
        self.assertFalse(holds.is_held())
        self.assertEqual(holds.release(user=self.operator, note=NOTE), [])  # nothing stands: nothing is recorded
        self.assertEqual(models.InterpreterHoldRelease.objects.count(), 2)

    def test_only_an_operator_now_may_release(self):
        self.hold()
        member = f.member(self.ws, role=models.Membership.OWNER)  # a practice owner is not an operator
        revoked = an_operator('synthetic-revoked')
        operator.revoke(revoked, 'Synthetic revocation for a test.', 'tests')
        inactive = an_operator('synthetic-inactive')
        inactive.is_active = False
        inactive.save(update_fields=['is_active'])
        for user in (member, revoked, inactive):
            with self.subTest(user=user.username):
                with self.assertRaises(PermissionError):
                    holds.release(user=user, note=NOTE)
        self.assertEqual(models.InterpreterHoldRelease.objects.count(), 0)
        self.assertTrue(holds.is_held())

    def test_a_release_needs_a_storable_note(self):
        self.hold()
        for note in ('', '   \n', None, 'x' * (holds.MAX_NOTE_CHARS + 1), 'a\x00b', 'a\ud800b'):
            with self.subTest(note=repr(note)[:20]):
                with self.assertRaises(ValueError):
                    holds.release(user=self.operator, note=note)
        self.assertEqual(models.InterpreterHoldRelease.objects.count(), 0)
        self.assertEqual(len(holds.release(user=self.operator, note='x' * holds.MAX_NOTE_CHARS)), 1)

    def test_a_hold_released_meanwhile_is_skipped_never_released_twice(self):
        first, second = self.hold(401), self.hold(403)
        models.InterpreterHoldRelease.objects.create(hold=first, released_by=self.operator, note='Released elsewhere.')
        standing = [first, second]  # as a concurrent command read them, before the other release landed
        with mock.patch.object(holds, 'active', return_value=standing):
            released = holds.release(user=self.operator, note=NOTE)
        self.assertEqual([item.hold for item in released], [second])
        self.assertEqual(models.InterpreterHoldRelease.objects.filter(hold=first).count(), 1)


class CommandTests(TestCase):
    def setUp(self):
        self.ws, self.usr, self.enc, self.rev = scene()
        self.operator = an_operator()

    def run_command(self, *args):
        out = io.StringIO()
        call_command('interpreter_hold', *args, stdout=out)
        return out.getvalue()

    def hold(self, **run):
        return holds.settle(gemini_run(self.enc, self.rev, **run))[1]

    def test_with_no_option_it_shows_the_holds_and_its_own_processs_mode_and_writes_nothing(self):
        with override_settings(GEMINI_MODE='live'):
            shown = self.run_command()
            self.assertIn('interpreter hold (installation-wide): none standing; interpret stages are not held', shown)
            self.assertIn('interpreter mode (this command\'s own process): live;', shown)
            hold = self.hold()
            shown = self.run_command()
            self.assertIn('interpreter hold (installation-wide): 1 standing; every interpret stage sends nothing', shown)
            self.assertIn(holds.describe(hold), shown)
        with override_settings(GEMINI_MODE='disabled'):  # a one-shot's own mode, never the installation's state
            shown = self.run_command()
            self.assertIn('interpreter mode (this command\'s own process): disabled; a one-shot runs with the interpreter '
                          'disabled unless it is given a mode', shown)
            self.assertNotIn('paused (interpreter_disabled)', shown)
            self.assertNotIn('interpreter mode: disabled', shown)
        self.assertEqual(models.InterpreterHoldRelease.objects.count(), 0)

    def test_release_with_a_note_records_it_and_says_members_may_resume(self):
        hold = self.hold(state='succeeded', http_status=200, body=substituted())  # P-5's model hold
        shown = self.run_command('--release', '--username', self.operator.username, '--note', NOTE)
        release = models.InterpreterHoldRelease.objects.get()
        self.assertEqual((release.hold, release.released_by, release.note), (hold, self.operator, NOTE))
        self.assertIn(f'(release {release.pk})', shown)
        self.assertIn('1 hold released by synthetic-operator. Members may now Resume.', shown)
        self.assertIn(f'released: hold {hold.pk} (model) by synthetic-operator', self.run_command())

    def test_release_reads_the_note_from_a_file(self):
        self.hold()
        self.hold(http_status=403)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'note.txt'
            path.write_text(NOTE + '\n', encoding='utf-8')
            shown = self.run_command('--release', '--username', self.operator.username, '--note-file', str(path))
        self.assertEqual(sorted(models.InterpreterHoldRelease.objects.values_list('note', flat=True)), [NOTE, NOTE])
        self.assertIn('2 holds released by synthetic-operator.', shown)

    def test_every_refusal_records_nothing(self):
        self.hold()
        member = f.member(self.ws)
        cases = (
            (('--release', '--note', NOTE), '--release needs --username'),
            (('--release', '--username', self.operator.username), '--release needs --note-file or --note'),
            (('--username', self.operator.username), 'go with --release'),
            (('--note', NOTE), 'go with --release'),
            (('--release', '--username', 'nobody-at-all', '--note', NOTE), "No account is named 'nobody-at-all'"),
            (('--release', '--username', member.username, '--note', NOTE), 'Only an operator may release'),
            (('--release', '--username', self.operator.username, '--note', '   '), 'needs a note'),
            (('--release', '--username', self.operator.username, '--note-file', '/nonexistent/synthetic-note.txt'),
             'The note file cannot be read'),
        )
        for args, expected in cases:
            with self.subTest(args=args):
                with self.assertRaises(CommandError) as refused:
                    self.run_command(*args)
                self.assertIn(expected, str(refused.exception))
        self.assertEqual(models.InterpreterHoldRelease.objects.count(), 0)
        self.assertTrue(holds.is_held())

    def test_releasing_with_no_hold_standing_is_refused(self):
        with self.assertRaises(CommandError) as refused:
            self.run_command('--release', '--username', self.operator.username, '--note', NOTE)
        self.assertIn('No interpreter hold is standing; nothing was recorded.', str(refused.exception))
        self.assertEqual(models.InterpreterHoldRelease.objects.count(), 0)
