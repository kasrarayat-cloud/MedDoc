"""studio/interpretation/holds.py, the purpose ``appraisal`` (docs/gemini-migration/FINAL-V2.md 7.4 and 7.5,
AMENDMENT-1.md 7.3 and A11; step 3b of 8.1). Synthetic rows only; nothing is sent.

What is proved:
- one table for both passes: a run of design v2's appraisal (ProviderRun.purpose 'appraisal') is classified exactly as a
  pass-1 run with the same outcome is, by the one classifier (adapter.classify), for every row of the table
  (BothPassesTests);
- a bare 429 holds both passes: whichever pass's answer carries it, it records the installation-wide hold that stops
  every request of either pass, and one operator's release ends it (BothPassesTests);
- a 402 holds as quota (A11), recorded with its status, on either pass (BothPassesTests);
- MAX_TOKENS is TOO_LONG on either pass: no hold, no member retry (BothPassesTests);
- an appraisal's refused reading, recorded on its own run (no inventory row: FINAL-V2 7.5), fails the attempt with the
  retry door and never changes a hold or a cut-off answer; an inventory is bound by the run's pass
  (AppraisalRefusalTests);
- only a Gemini run of one of the two passes is classified or holds; one answer sets at most one hold for an appraisal
  as for pass 1 (RunTests).
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

from django.test import TestCase, override_settings

from studio import interpretation, models, operator
from studio.interpretation import adapter, holds
from studio.interpretation.contract import extract_read
from studio.types import sha256_json
from tests.support import factories as f
from tests.test_interpretation_adapter import (PER_DAY, PER_MINUTE, TRIAL_429, encoded, envelope, error_body,
                                               error_info, quota_failure, violation, with_parts)

TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Date of service: 2031-06-02\n'
        'Colonoscopy: The colonoscope was advanced to the cecum. A 5 mm polyp was removed with a cold snare.\n')
OK_BODY = encoded(envelope())
NOTE = 'Synthetic release: the synthetic project was restored for a test.'
CAP_429 = encoded({'error': {'code': 429, 'message': 'Synthetic: the project exceeded its monthly spending cap.',
                             'status': 'RESOURCE_EXHAUSTED'}})
CUT_OFF = encoded(with_parts({'text': '{'}, finish='MAX_TOKENS'))


def substituted() -> bytes:
    return encoded(envelope(modelVersion='gemini-4-argon-preview'))


# (label, state, http_status, body, effect, reason): FINAL 11.1 as P-3, P-4, P-5, C5 and A11 amend it
TABLE = (
    ('401', 'failed', 401, b'', holds.HOLD, holds.AUTH),
    ('402, an empty body (A11)', 'failed', 402, b'', holds.HOLD, holds.QUOTA),
    ('402, a JSON error naming no hold (A11)', 'failed', 402, error_body(402, 'FAILED_PAYMENT'), holds.HOLD,
     holds.QUOTA),
    ('403', 'failed', 403, b'<html>no</html>', holds.HOLD, holds.PERMISSION),
    ('BILLING_DISABLED', 'failed', 403, error_body(403, 'PERMISSION_DENIED', error_info('BILLING_DISABLED')),
     holds.HOLD, holds.QUOTA),
    ('a bare 429: the spending cap (D39)', 'failed', 429, CAP_429, holds.HOLD, holds.QUOTA),
    ('a bare 429: an empty body', 'failed', 429, b'', holds.HOLD, holds.QUOTA),
    ("the trial's 429", 'failed', 429, TRIAL_429.read_bytes(), holds.HOLD, holds.QUOTA),
    ('a daily quota', 'failed', 429, error_body(429, 'RESOURCE_EXHAUSTED', quota_failure(violation(PER_DAY))),
     holds.HOLD, holds.QUOTA),
    ('a per-minute paid rate limit', 'failed', 429,
     error_body(429, 'RESOURCE_EXHAUSTED', quota_failure(violation(PER_MINUTE, quotaValue='1000'))), holds.FAILED, ''),
    ('another model (P-5)', 'succeeded', 200, substituted(), holds.HOLD, holds.MODEL),
    ('a 5xx', 'failed', 503, error_body(503, 'UNAVAILABLE'), holds.FAILED, ''),
    ('cut off (MAX_TOKENS)', 'succeeded', 200, CUT_OFF, holds.TOO_LONG, ''),
    ('a usable answer', 'succeeded', 200, OK_BODY, holds.ANSWERED, ''),
    ('unknown', 'unknown', None, b'', holds.UNKNOWN, ''),
    ('not sent', 'not_sent', None, b'', holds.NONE, ''),
)


def scene():
    ws = f.workspace()
    usr = f.member(ws)
    enc = f.encounter(ws, usr)
    rev = f.pasted_revision(enc, usr, TEXT)
    return enc, rev


def gemini_run(enc, rev, *, state='failed', http_status=401, body=b'', purpose=interpretation.APPRAISAL_PURPOSE,
               provider=interpretation.PROVIDER, sent=True, reused_from=None):
    """A Gemini run of design v2 with the given outcome (its request a synthetic stand-in: holds reads the outcome, its
    status and its bytes, never the request)."""
    request = {'systemInstruction': {'parts': [{'text': 'synthetic'}]}, 'contents': [{'parts': [{'text': rev.text}]}],
               'generationConfig': {'temperature': 0}, 'purpose': purpose}
    return models.ProviderRun.objects.create(
        encounter=enc, revision=rev, provider=provider, adapter_version=interpretation.ADAPTER_VERSION_V2,
        purpose=purpose, request_sha256=sha256_json(request), request_body=request, contexts=[], state=state,
        sent=sent, http_status=http_status, response_bytes=body, response_sha256=hashlib.sha256(body).hexdigest(),
        reused_from=reused_from)


def an_operator(username='synthetic-operator'):
    user = f.user(username)
    operator.grant(user, 'Synthetic grant for an interpreter-hold test of design v2.', 'tests')
    return user


class BothPassesTests(TestCase):
    def setUp(self):
        self.enc, self.rev = scene()

    def test_one_table_for_both_passes(self):
        self.assertEqual(holds.PURPOSES, (interpretation.PURPOSE, interpretation.APPRAISAL_PURPOSE))
        for label, state, status, body, effect, reason in TABLE:
            outcomes = {}
            for purpose in holds.PURPOSES:
                with self.subTest(label, purpose=purpose):
                    run = gemini_run(self.enc, self.rev, state=state, http_status=status, body=body, purpose=purpose)
                    outcome = holds.classify_run(run)
                    self.assertEqual((outcome.effect, outcome.reason, outcome.retry),
                                     (effect, reason, effect == holds.FAILED))
                    self.assertEqual(outcome.verdict, adapter.classify(state, status, body))
                    for named in ('gemini', 'google', 'argon'):
                        self.assertNotIn(named, outcome.why.lower())
                    outcomes[purpose] = outcome
            self.assertEqual(outcomes[interpretation.PURPOSE], outcomes[interpretation.APPRAISAL_PURPOSE])

    def test_a_bare_429_on_either_pass_holds_both_passes(self):
        cases = [(purpose, body) for purpose in holds.PURPOSES
                 for body in (CAP_429, b'', error_body(429, 'RESOURCE_EXHAUSTED'))]
        for number, (purpose, body) in enumerate(cases):
            with self.subTest(purpose=purpose, body=body[:20]), override_settings(GEMINI_MODE='live'):
                self.assertIsNone(holds.paused_reason())
                run = gemini_run(self.enc, self.rev, http_status=429, body=body, purpose=purpose)
                outcome, hold = holds.settle(run)
                self.assertEqual((outcome.effect, outcome.reason, outcome.retry), (holds.HOLD, holds.QUOTA, False))
                stored = models.InterpreterHold.objects.get(pk=hold.pk)
                self.assertEqual((stored.reason, stored.http_status, stored.run_id, stored.violations),
                                 (holds.QUOTA, 429, run.pk, []))
                # the hold names no purpose: every request of both passes waits on it, installation-wide
                self.assertEqual(holds.paused_reason(), holds.HELD_HOLD)
                self.assertTrue(holds.is_held())
                self.assertEqual([item.run_id for item in holds.active()], [run.pk])
                holds.release(user=an_operator(f'synthetic-operator-429-{number}'), note=NOTE)
                self.assertIsNone(holds.paused_reason())

    def test_a_402_holds_as_quota_on_either_pass(self):
        cases = [(purpose, body) for purpose in holds.PURPOSES
                 for body in (b'', b'<html>Payment Required</html>', error_body(402, 'INVALID_ARGUMENT'))]
        for number, (purpose, body) in enumerate(cases):
            with self.subTest(purpose=purpose, body=body[:20]):
                run = gemini_run(self.enc, self.rev, http_status=402, body=body, purpose=purpose)
                outcome, hold = holds.settle(run)
                self.assertEqual((outcome.effect, outcome.reason, outcome.retry), (holds.HOLD, holds.QUOTA, False))
                self.assertEqual((hold.reason, hold.http_status, hold.run_id), (holds.QUOTA, 402, run.pk))
                self.assertIn('payment', holds.REASON_TEXT[hold.reason])
                self.assertIn('payment', holds.describe(hold))
                holds.release(user=an_operator(f'synthetic-operator-402-{number}'), note=NOTE)

    def test_max_tokens_is_too_long_on_either_pass(self):
        for purpose in holds.PURPOSES:
            with self.subTest(purpose=purpose):
                outcome, hold = holds.settle(gemini_run(self.enc, self.rev, state='succeeded', http_status=200,
                                                        body=CUT_OFF, purpose=purpose))
                self.assertEqual((outcome.effect, outcome.retry, hold), (holds.TOO_LONG, False, None))
        self.assertEqual(models.InterpreterHold.objects.count(), 0)


class AppraisalRefusalTests(TestCase):
    def setUp(self):
        self.enc, self.rev = scene()

    def test_a_refused_appraisal_reading_fails_the_attempt_with_its_reason(self):
        run = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=OK_BODY)
        refusal = extract_read.refuse('schema', 'the appraisal breaks its schema: a synthetic reason')
        outcome, hold = holds.settle(run, refused=refusal)
        self.assertEqual((outcome.effect, outcome.why, outcome.retry, hold), (holds.FAILED, refusal.reason, True, None))
        self.assertEqual(outcome.verdict.kind, adapter.ANSWERED)  # the adapter's verdict is kept as it was
        # an unhealthy appraisal settle refuses (3.2.6) carries its own sentence; one with none gets the pass's
        unhealthy = SimpleNamespace(reason='The appraisal was refused whole: a synthetic health reason.')
        self.assertEqual(holds.classify_run(run, refused=unhealthy).why, unhealthy.reason)
        self.assertEqual(holds.classify_run(run, refused=object()).why, holds.APPRAISAL_REFUSED_WHY)
        pass_1 = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=OK_BODY,
                            purpose=interpretation.PURPOSE)
        self.assertEqual(holds.classify_run(pass_1, refused=object()).why, holds.REFUSED_WHY)
        self.assertEqual(holds.classify_run(run).effect, holds.ANSWERED)  # without it: as the adapter read it

    def test_a_refusal_never_changes_a_hold_a_failure_or_a_cut_off_answer(self):
        refusal = extract_read.refuse('bounds', 'it gives more verdicts than the request has claims')
        for state, status, body, effect in (('succeeded', 200, substituted(), holds.HOLD),
                                            ('succeeded', 200, CUT_OFF, holds.TOO_LONG),
                                            ('failed', 429, CAP_429, holds.HOLD),
                                            ('failed', 503, error_body(503, 'UNAVAILABLE'), holds.FAILED)):
            with self.subTest(effect=effect, status=status):
                run = gemini_run(self.enc, self.rev, state=state, http_status=status, body=body)
                self.assertEqual(holds.classify_run(run, refused=refusal).effect, effect)

    def test_an_inventory_is_bound_by_the_runs_pass(self):
        appraisal = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=OK_BODY)
        pass_1 = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=OK_BODY,
                            purpose=interpretation.PURPOSE)
        # the fields of an EventInventory row classify_run reads (store's row: its two runs and its state)
        read = SimpleNamespace(provider_run_id=pass_1.pk, appraisal_run_id=appraisal.pk, state='read')
        self.assertEqual(holds.classify_run(appraisal, inventory=read).effect, holds.ANSWERED)
        self.assertEqual(holds.classify_run(pass_1, inventory=read).effect, holds.ANSWERED)
        self.assertEqual(holds.classify_run(appraisal, inventory=SimpleNamespace(
            provider_run_id=pass_1.pk, appraisal_run_id=str(appraisal.pk), state='read')).effect, holds.ANSWERED)
        for run, inventory in ((appraisal, SimpleNamespace(provider_run_id=appraisal.pk, appraisal_run_id=None,
                                                           state='read')),
                               (pass_1, SimpleNamespace(provider_run_id=appraisal.pk, appraisal_run_id=pass_1.pk,
                                                        state='read'))):
            with self.subTest(purpose=run.purpose), self.assertRaises(ValueError):
                holds.classify_run(run, inventory=inventory)
        # a refused pass-1 row (it binds no appraisal run, FINAL-V2 6.3) fails its own run's answer
        refused = SimpleNamespace(provider_run_id=pass_1.pk, appraisal_run_id=None, state='refused',
                                  verification={'problems': ['The interpretation was not used: a synthetic reason.']})
        outcome = holds.classify_run(pass_1, inventory=refused)
        self.assertEqual((outcome.effect, outcome.why), (holds.FAILED, 'The interpretation was not used: a synthetic '
                                                                       'reason.'))


class RunTests(TestCase):
    def setUp(self):
        self.enc, self.rev = scene()

    def test_only_a_gemini_run_of_the_two_passes_is_classified_or_holds(self):
        hold = holds.Outcome(holds.HOLD, adapter.classify('failed', 401, b''), 'held')
        for provider, purpose in (('corti', 'primary'), (interpretation.PROVIDER, 'primary'),
                                  ('astra', 'independent'), ('astra', interpretation.APPRAISAL_PURPOSE)):
            run = gemini_run(self.enc, self.rev, provider=provider, purpose=purpose)
            with self.subTest(provider=provider, purpose=purpose):
                with self.assertRaises(ValueError):
                    holds.classify_run(run)
                with self.assertRaises(ValueError):
                    holds.record(run, hold)
        with self.assertRaises(ValueError):
            holds.classify('failed', 401, b'', purpose='primary')
        self.assertEqual(models.InterpreterHold.objects.count(), 0)
        appraisal = gemini_run(self.enc, self.rev)
        self.assertEqual(holds.record(appraisal, holds.classify_run(appraisal)).run, appraisal)

    def test_one_appraisal_answer_sets_one_hold_whichever_run_carries_it(self):
        sent = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=substituted())
        outcome, first = holds.settle(sent)
        self.assertEqual((outcome.effect, outcome.reason, first.run_id), (holds.HOLD, holds.MODEL, sent.pk))
        copy = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=substituted(), sent=False,
                          reused_from=sent)
        self.assertEqual(holds.settle(copy), (outcome, first))  # a reuse copies the answer: its hold, not a second
        holds.release(user=an_operator(), note=NOTE)
        self.assertEqual(holds.settle(sent)[1], None)  # released: settling the same answer again stands none
        self.assertEqual(holds.record(copy, outcome), first)
        self.assertEqual(models.InterpreterHold.objects.count(), 1)
