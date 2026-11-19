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
  as for pass 1 (RunTests);
- pass 1's stored answer that the reader refuses when pass 2 is built (adapter.NotBuilt, effect REFUSED: DECISIONS
  D229), recorded as adapter.NotBuilt says step 5b records it - pass 1's refused row, its effect by settle - is a
  definite failure of that run with the retry door (FINAL-V2 7.5), never 'unbuilt'; a cut-off answer stays TOO_LONG
  and a substituted model holds (RefusedStoredReadingTests).

AMENDMENT-2 (docs/gemini-migration/AMENDMENT-2.md 1.5 as its refutation revised it; step F1): the interpreter is Claude
Fable 5.2 (D275). Every test that records a hold names the current adapter version it runs under (FablePath:
ADAPTER_VERSION_V3, the version step F6 makes jobs send), so none depends on when jobs switches. What is proved:
- dispatch by adapter version: a stored run is classified by the adapter that recorded it - a Fable run by
  fable_adapter.classify, a Gemini run (v1 or v2) by adapter.classify, a caller naming no version as Gemini's, any
  other version refused (DispatchTests);
- the two new reasons with their texts, REASONS the union of both adapters' (ReasonTests);
- _check_run accepts both providers of interpretation.READ_PROVIDERS, each at its own adapter versions, and refuses any
  other (the Fable participant's 'fable' included) (ReasonTests);
- 1.5's table through the hold table for Fable runs of both passes, and a Fable hold of either pass stops both
  (FableTableTests);
- a Gemini run never sets a hold on the Fable path - refute-cb-r1 CB1-1's probe input (a stored v1 Argon run with no
  recorded effect) and its v2 twin - while the test-only v1 chain keeps its own (GeminiNeverHoldsTests; D289, G2-02);
- ``request_bound`` true for a declined hold and for a hold an error event set after message_start, false for every
  other, read fail-closed when its bytes are gone (RequestBoundTests) [R:connector-CONN-1];
- the release report naming each run, encounter and request, through ``interpreter_hold --release`` too
  (ReleaseReportTests) [R:connector-CONN-1].
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from studio import interpretation, jobs, models, operator
from studio.interpretation import adapter, fable_adapter, holds, store
from studio.interpretation.contract import extract_read
from studio.types import ProviderRequest, sha256_json
from tests.support import factories as f
from tests.test_interpretation_adapter import (PER_DAY, PER_MINUTE, TRIAL_429, encoded, envelope, error_body,
                                               error_info, quota_failure, violation, with_parts)
from tests.v1_chain import v1_chain
from tests.v2 import test_fable_adapter as streams
from tests.v2.test_adapter import measured_pins

TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Date of service: 2031-06-02\n'
        'Colonoscopy: The colonoscope was advanced to the cecum. A 5 mm polyp was removed with a cold snare.\n')
OK_BODY = encoded(envelope())
NOTE = 'Synthetic release: the synthetic project was restored for a test.'
CAP_429 = encoded({'error': {'code': 429, 'message': 'Synthetic: the project exceeded its monthly spending cap.',
                             'status': 'RESOURCE_EXHAUSTED'}})
CUT_OFF = encoded(with_parts({'text': '{'}, finish='MAX_TOKENS'))


def substituted() -> bytes:
    return encoded(envelope(modelVersion=f'{interpretation.MODEL}-preview'))


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


V3 = interpretation.ADAPTER_VERSION_V3


def fable_run(enc, rev, *, state='succeeded', http_status=200, body=b'', purpose=interpretation.APPRAISAL_PURPOSE,
              provider=interpretation.PROVIDER_V3, adapter_version=V3, sent=True, reused_from=None, response=True):
    """A Fable run (ADAPTER_VERSION_V3) with the given outcome; its request a synthetic stand-in (holds reads the
    outcome, its status and its bytes, never the request). ``response`` False: the run keeps no bytes of its own."""
    request = {'model': fable_adapter.MODEL, 'messages': [{'role': 'user', 'content': rev.text}], 'purpose': purpose}
    kept = body if response else b''
    return models.ProviderRun.objects.create(
        encounter=enc, revision=rev, provider=provider, adapter_version=adapter_version, purpose=purpose,
        request_sha256=sha256_json(request), request_body=request, contexts=[], state=state, sent=sent,
        http_status=http_status, response_bytes=kept, response_sha256=hashlib.sha256(kept).hexdigest(),
        reused_from=reused_from)


def declined(category='cyber') -> bytes:
    return streams.answer_stream(None, stop_reason='refusal', stop_details={
        'type': 'refusal', 'category': category, 'explanation': streams.CATEGORY_EXPLANATION})


class FablePath:
    """The reading stages send ADAPTER_VERSION_V3 (AMENDMENT-2 section 9, step F6): holds.record's current version,
    named here so no test depends on when jobs switches."""

    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.object(holds, 'current_adapter_version', return_value=V3))


class BothPassesTests(TestCase):
    """The dormant Gemini adapter's table, as it classifies its stored runs (dispatch by adapter version). The tests that
    record a hold name ADAPTER_VERSION_V2 as the version in use - the product's before AMENDMENT-2 - since only a run of
    the current version sets one; on the Fable path a Gemini run sets none (GeminiNeverHoldsTests)."""

    def setUp(self):
        self.enc, self.rev = scene()
        self.enterContext(mock.patch.object(holds, 'current_adapter_version',
                                            return_value=interpretation.ADAPTER_VERSION_V2))

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
        self.enterContext(mock.patch.object(holds, 'current_adapter_version',
                                            return_value=interpretation.ADAPTER_VERSION_V2))

    def test_only_a_gemini_run_of_the_two_passes_is_classified_or_holds(self):
        hold = holds.Outcome(holds.HOLD, adapter.classify('failed', 401, b''), 'held')
        for provider, purpose in (('corti', 'primary'), (interpretation.PROVIDER, 'primary'),
                                  ('astra', 'independent'), ('astra', interpretation.APPRAISAL_PURPOSE),
                                  ('fable', interpretation.APPRAISAL_PURPOSE)):
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


class RefusedStoredReadingTests(TestCase):
    """adapter.NotBuilt's REFUSED effect (DECISIONS D229; FINAL-V2 7.5's "answer refused by the reader"): pass 1's
    stored answer, read when pass 2 is built and refused by the reader, recorded exactly as NotBuilt's docstring says
    step 5b records it - pass 1's refused row (store.refused_row_v2 of the NotBuilt's refusal, for the pass-1 run whose
    request and bytes were given; appraisal_run NULL) and that run's effect from holds.settle with the row."""

    def setUp(self):
        self.enterContext(mock.patch.multiple(interpretation, **measured_pins()))
        # the dormant Gemini path, as the version in use (only a run of the current version sets a hold)
        self.enterContext(mock.patch.object(holds, 'current_adapter_version',
                                            return_value=interpretation.ADAPTER_VERSION_V2))
        self.enc, self.rev = scene()

    def pass_1_run(self, body: bytes) -> models.ProviderRun:
        """A sent pass-1 run of this revision's own pass-1 request, ``body`` its stored answer, read back from the
        database as the stage reads it."""
        request = adapter.build_extraction_request(self.rev.text, (), 'paste')
        run = models.ProviderRun.objects.create(
            encounter=self.enc, revision=self.rev, provider=interpretation.PROVIDER,
            adapter_version=request.adapter_version, purpose=interpretation.PURPOSE,
            request_sha256=request.canonical_sha256, request_body=request.body, contexts=list(request.contexts),
            state='succeeded', sent=True, http_status=200, response_bytes=body,
            response_sha256=hashlib.sha256(body).hexdigest())
        return models.ProviderRun.objects.get(pk=run.pk)

    def recorded(self, run: models.ProviderRun) -> tuple:
        """(the NotBuilt, the refused row, settle's outcome, settle's hold): building pass 2 from the stored run, then
        recording what NotBuilt names for REFUSED."""
        stored = ProviderRequest(provider=run.provider, adapter_version=run.adapter_version, body=run.request_body,
                                 canonical_sha256=run.request_sha256, contexts=tuple(run.contexts or ()))
        with self.assertRaises(adapter.NotBuilt) as caught:
            adapter.build_appraisal_request(self.rev.text, (), 'paste', stored, bytes(run.response_bytes),
                                            check=lambda text, pages, answer: {})
        refused = caught.exception
        self.assertEqual((refused.reason, refused.effect), (adapter.STORED, adapter.REFUSED))
        fields = store.refused_row_v2(refused.refusal, encounter_id=self.enc.pk, revision_id=self.rev.pk,
                                      provider_run_id=run.pk, text_sha256=self.rev.text_sha256,
                                      request_sha256=run.request_sha256, response_sha256=run.response_sha256)
        created = models.EventInventory.objects.create(**{name: fields[name] for name in store.FIELDS_V2})
        row = models.EventInventory.objects.get(pk=created.pk)  # as a later stage reads it
        outcome, hold = holds.settle(run, inventory=row)
        return refused, row, outcome, hold

    def test_a_refused_reading_of_a_usable_answer_fails_the_run_with_the_retry_door(self):
        for name, text, stage in (('not JSON inside', '{"x": ', 'json'), ('outside the schema', '{}', 'schema')):
            with self.subTest(name):
                run = self.pass_1_run(encoded(envelope(text)))
                # without the refused row the answer reads as answered: a stage would reuse it (the refutation's P1)
                self.assertEqual(holds.classify_run(run).effect, holds.ANSWERED)
                refused, row, outcome, hold = self.recorded(run)
                self.assertEqual((row.state, row.appraisal_run_id, row.provider_run_id, row.revision_id),
                                 (refused.effect, None, run.pk, self.rev.pk))
                self.assertEqual((row.interpretation_version, row.inventory_version),
                                 (interpretation.INTERPRETATION_PAIR, interpretation.INVENTORY_VERSION_V2))
                self.assertEqual((row.verification['stage'], row.verification['problems']),
                                 (stage, [refused.refusal.reason]))
                self.assertEqual((outcome.effect, outcome.retry, outcome.why, hold),
                                 (holds.FAILED, True, refused.refusal.reason, None))
                self.assertNotIn(adapter.UNBUILT, (outcome.effect, row.state, refused.effect))
                self.assertEqual(holds.classify_run(run, inventory=row), outcome)  # read again: the same effect
                # recorded on the run's scope as jobs._mark_effect records an effect, it is the effect jobs reads
                # first. (AMENDMENT-2: whether jobs' retry door releases a stored Gemini run, and at which versions it
                # reads the refused row, are step F6's - jobs reads Fable's runs at the @3 pair after its switch;
                # FableRefusedStoredReadingTests pins the Fable twin of this record.)
                models.ProviderRun.objects.filter(pk=run.pk).update(scope={**(run.scope or {}),
                                                                          'effect': outcome.effect})
                run.refresh_from_db()
                self.assertEqual(jobs.interpretation_effect(run), holds.FAILED)

    def test_a_cut_off_answer_stays_too_long_and_a_substituted_model_holds(self):
        refused, row, outcome, hold = self.recorded(self.pass_1_run(CUT_OFF))
        self.assertEqual((refused.refusal.stage, row.state), ('envelope', 'refused'))
        self.assertEqual((outcome.effect, outcome.retry, hold), (holds.TOO_LONG, False, None))  # C5: never re-sent
        run = self.pass_1_run(substituted())
        refused, row, outcome, hold = self.recorded(run)
        self.assertEqual((refused.refusal.stage, row.state), ('envelope', 'refused'))
        self.assertEqual((outcome.effect, outcome.reason, outcome.retry), (holds.HOLD, holds.MODEL, False))
        self.assertEqual((hold.reason, hold.run_id), (holds.MODEL, run.pk))
        with override_settings(GEMINI_MODE='live'):
            self.assertEqual(holds.paused_reason(), holds.HELD_HOLD)  # every request of both passes waits on it


# --- AMENDMENT-2 (step F1): the interpreter is Claude Fable 5.2 -----------------------------------------------------------

EFFECT = {'answered': holds.ANSWERED, 'failed': holds.FAILED, 'too_long': holds.TOO_LONG, 'hold': holds.HOLD}


class DispatchTests(TestCase):
    """AMENDMENT-2 1.5 (refute-cb-r1 CB1-1, TRIAGE G2-02): a stored run is classified by the adapter that recorded it."""

    def setUp(self):
        self.enc, self.rev = scene()

    def test_each_run_is_classified_by_the_adapter_that_recorded_it(self):
        decline = declined()
        fable = fable_run(self.enc, self.rev, body=decline)
        gemini = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=decline)
        outcome = holds.classify_run(fable)
        self.assertEqual((outcome.effect, outcome.reason), (holds.HOLD, holds.DECLINED))
        self.assertEqual(outcome.verdict, fable_adapter.classify('succeeded', 200, decline))
        # the same bytes on a Gemini run are read by Gemini's envelope: not JSON, a failure - never Fable's reading
        self.assertEqual(holds.classify_run(gemini).verdict, adapter.classify('succeeded', 200, decline))
        self.assertEqual(holds.classify_run(gemini).effect, holds.FAILED)
        # and Gemini's answer on a Fable run is not a stream: a failure of that attempt, never Gemini's reading
        fable_gemini = fable_run(self.enc, self.rev, body=OK_BODY)
        self.assertEqual(holds.classify_run(fable_gemini).verdict, fable_adapter.classify('succeeded', 200, OK_BODY))
        self.assertEqual(holds.classify_run(fable_gemini).effect, holds.FAILED)

    def test_classify_dispatches_by_its_keyword_and_a_caller_naming_none_is_read_as_geminis(self):
        stream = streams.answer_stream()
        self.assertEqual(holds.classify('succeeded', 200, stream, adapter_version=V3).effect, holds.ANSWERED)
        for version in (interpretation.ADAPTER_VERSION, interpretation.ADAPTER_VERSION_V2):
            with self.subTest(version=version):
                self.assertEqual(holds.classify('succeeded', 200, OK_BODY, adapter_version=version).effect,
                                 holds.ANSWERED)
        self.assertEqual(holds.classify('succeeded', 200, OK_BODY).effect, holds.ANSWERED)  # jobs until F6
        self.assertEqual(holds.classify('succeeded', 200, stream).effect, holds.FAILED)  # Gemini's reading of it
        for version in ('anthropic-messages@cptstudio-harness-4', '', None, 7):
            with self.subTest(version=version), self.assertRaises(ValueError):
                holds.classify('succeeded', 200, stream, adapter_version=version)
        with mock.patch.object(fable_adapter, 'classify', return_value=None) as classify:
            self.assertEqual(holds.classify('failed', 401, b'', adapter_version=V3).effect, holds.NONE)
        classify.assert_called_once_with('failed', 401, b'')
        self.assertEqual(holds.classify('unknown', None, b'', adapter_version=V3).effect, holds.UNKNOWN)


class ReasonTests(TestCase):
    def setUp(self):
        self.enc, self.rev = scene()

    def test_the_two_new_reasons_and_their_texts(self):
        self.assertEqual((holds.REFUSED, holds.DECLINED), ('refused', 'declined'))
        self.assertEqual((models.InterpreterHold.REFUSED, models.InterpreterHold.DECLINED), ('refused', 'declined'))
        self.assertEqual(holds.REASONS, tuple(dict.fromkeys(adapter.HOLD_REASONS + fable_adapter.HOLD_REASONS)))
        self.assertEqual(set(holds.REASON_TEXT), set(holds.REASONS))
        self.assertEqual(holds.REASON_TEXT[holds.REFUSED], 'requests of this version were refused as invalid')
        self.assertEqual(holds.REASON_TEXT[holds.DECLINED], 'the model declined to answer a request; it was not read '
                                                            'and nothing was re-asked of another model')
        for reason in (holds.REFUSED, holds.DECLINED):
            verdict = fable_adapter.Classification(fable_adapter.HOLD, hold=reason)
            self.assertEqual(holds.Outcome(holds.HOLD, verdict, 'held').reason, reason)
        with self.assertRaises(ValueError):
            holds.Outcome(holds.HOLD, fable_adapter.Classification(fable_adapter.HOLD, hold='other'), 'held')

    def test_both_read_providers_at_their_own_versions_and_no_other(self):
        for provider, version in ((interpretation.PROVIDER_V3, V3),
                                  (interpretation.PROVIDER, interpretation.ADAPTER_VERSION_V2),
                                  (interpretation.PROVIDER, interpretation.ADAPTER_VERSION)):
            with self.subTest(provider=provider, version=version):
                run = fable_run(self.enc, self.rev, provider=provider, adapter_version=version, body=b'')
                holds.classify_run(run)  # accepted
        self.assertEqual(interpretation.READ_PROVIDERS, ('anthropic', 'gemini'))
        for provider, version in (('fable', V3), ('corti', V3), ('astra', V3),
                                  (interpretation.PROVIDER_V3, interpretation.ADAPTER_VERSION_V2),
                                  (interpretation.PROVIDER, V3)):
            with self.subTest(provider=provider, version=version):
                run = fable_run(self.enc, self.rev, provider=provider, adapter_version=version, body=b'')
                with self.assertRaises(ValueError):
                    holds.classify_run(run)
                with self.assertRaises(ValueError):
                    holds.record(run, holds.Outcome(holds.HOLD, fable_adapter.classify('failed', 401, b''), 'held'))
        self.assertEqual(models.InterpreterHold.objects.count(), 0)


class FableTableTests(FablePath, TestCase):
    def setUp(self):
        super().setUp()
        self.enc, self.rev = scene()

    def test_one_table_for_both_passes(self):
        rows = [(label, state, status, body, EFFECT[kind], hold)
                for label, state, status, body, kind, hold, _ in streams.table()]
        rows += [('unknown', 'unknown', 200, streams.sse(*streams.answer_events()[:-1]), holds.UNKNOWN, ''),
                 ('not sent', 'not_sent', None, b'', holds.NONE, '')]
        for label, state, status, body, effect, reason in rows:
            outcomes = {}
            for purpose in holds.PURPOSES:
                with self.subTest(label, purpose=purpose):
                    run = fable_run(self.enc, self.rev, state=state, http_status=status, body=body, purpose=purpose)
                    outcome = holds.classify_run(run)
                    self.assertEqual((outcome.effect, outcome.reason, outcome.retry),
                                     (effect, reason, effect == holds.FAILED))
                    if effect not in (holds.UNKNOWN, holds.NONE):
                        self.assertEqual(outcome.verdict, fable_adapter.classify(state, status, body))
                    outcomes[purpose] = outcome
            self.assertEqual(outcomes[interpretation.PURPOSE], outcomes[interpretation.APPRAISAL_PURPOSE])

    def test_a_fable_hold_on_either_pass_holds_both_passes_and_one_release_ends_it(self):
        cases = [(purpose, status, body, reason) for purpose in holds.PURPOSES
                 for status, body, reason in ((429, b'', holds.QUOTA), (402, streams.error_body('billing_error'),
                                                                        holds.QUOTA),
                                              (200, declined(), holds.DECLINED),
                                              (400, streams.error_body('invalid_request_error'), holds.REFUSED),
                                              (200, streams.answer_stream(model='claude-opus-5-5'), holds.MODEL))]
        for number, (purpose, status, body, reason) in enumerate(cases):
            with self.subTest(purpose=purpose, status=status, reason=reason), override_settings(GEMINI_MODE='live'):
                self.assertIsNone(holds.paused_reason())
                run = fable_run(self.enc, self.rev, state='succeeded' if status == 200 else 'failed',
                                http_status=status, body=body, purpose=purpose)
                outcome, hold = holds.settle(run)
                self.assertEqual((outcome.effect, outcome.reason, outcome.retry), (holds.HOLD, reason, False))
                stored = models.InterpreterHold.objects.get(pk=hold.pk)
                self.assertEqual((stored.reason, stored.http_status, stored.run_id, stored.violations),
                                 (reason, status, run.pk, []))
                self.assertEqual(holds.paused_reason(), holds.HELD_HOLD)  # every request of both passes waits on it
                holds.release(user=an_operator(f'synthetic-operator-fable-{number}'), note=NOTE)
                self.assertIsNone(holds.paused_reason())

    def test_the_vendor_status_is_the_error_type_or_the_refusal_category(self):
        for body, status, vendor_status in ((streams.error_body('authentication_error'), 401, 'authentication_error'),
                                            (declined('cyber'), 200, 'cyber'), (declined('Two Words'), 200, ''),
                                            (b'', 403, '')):
            with self.subTest(vendor_status=vendor_status, status=status):
                run = fable_run(self.enc, self.rev, state='succeeded' if status == 200 else 'failed',
                                http_status=status, body=body)
                _, hold = holds.settle(run)
                self.assertEqual(hold.vendor_status, vendor_status)
                self.assertNotIn(streams.CATEGORY_EXPLANATION, holds.describe(hold))
                holds.release(user=an_operator(f'synthetic-operator-vs-{status}-{len(body)}'), note=NOTE)

    def test_a_cut_off_answer_and_a_failure_set_no_hold(self):
        for body, effect in ((streams.answer_stream(stop_reason='max_tokens'), holds.TOO_LONG),
                             (streams.sse(streams.error_event('overloaded_error')), holds.FAILED)):
            with self.subTest(effect=effect):
                outcome, hold = holds.settle(fable_run(self.enc, self.rev, body=body))
                self.assertEqual((outcome.effect, hold), (effect, None))
        self.assertEqual(models.InterpreterHold.objects.count(), 0)

    def test_one_answer_sets_one_hold_whichever_run_carries_it(self):
        sent = fable_run(self.enc, self.rev, body=declined())
        outcome, first = holds.settle(sent)
        copy = fable_run(self.enc, self.rev, body=declined(), sent=False, reused_from=sent)
        self.assertEqual(holds.settle(copy), (outcome, first))
        self.assertEqual(holds.hold_of(copy), first)
        holds.release(user=an_operator(), note=NOTE)
        self.assertEqual(holds.settle(sent)[1], None)  # released: settling the same answer again stands none
        self.assertEqual(holds.record(copy, outcome), first)
        self.assertEqual(models.InterpreterHold.objects.count(), 1)


class GeminiNeverHoldsTests(FablePath, TestCase):
    """DECISIONS D289 G2-02 (refute-cb-r1 CB1-1): no stored Gemini or v1 run is a source of a new hold on the Fable path
    - holds.record sets a hold only for a run of the current adapter version - pinned with the probe's input and its v2
    twin; the test-only v1 chain, whose current version is v1's, keeps its own holds."""

    def setUp(self):
        super().setUp()
        self.enc, self.rev = scene()

    def test_the_probe_input_and_its_v2_twin_set_no_hold(self):
        v1 = probe_run(self.enc, self.rev)
        twin = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=substituted())
        quota = gemini_run(self.enc, self.rev, http_status=429, body=CAP_429)
        for run in (v1, twin, quota):
            with self.subTest(version=run.adapter_version, status=run.http_status), \
                    override_settings(GEMINI_MODE='live'):
                outcome, hold = holds.settle(run)
                self.assertEqual(outcome.effect, holds.HOLD)  # the answer is still never read
                self.assertIsNone(hold)
                self.assertIsNone(holds.record(run, outcome))
                self.assertIsNone(holds.paused_reason())  # a Gemini answer never pauses Fable
        self.assertEqual(models.InterpreterHold.objects.count(), 0)

    def test_a_hold_a_stored_run_set_before_is_returned_never_a_second(self):
        twin = gemini_run(self.enc, self.rev, state='succeeded', http_status=200, body=substituted())
        earlier = models.InterpreterHold.objects.create(reason=holds.MODEL, http_status=200, run=twin)
        self.assertEqual(holds.record(twin, holds.classify_run(twin)), earlier)
        self.assertEqual(models.InterpreterHold.objects.count(), 1)


def probe_run(enc, rev):
    """refute-cb-r1 CB1-1's probe input: a stored v1 run - adapter gemini-generate@cptstudio-1, purpose interpretation,
    sent, succeeded, requested gemini-4-argon, answered by gemini-4-argon - with no recorded effect (its worker died
    before settling it)."""
    run = gemini_run(enc, rev, state='succeeded', http_status=200, body=encoded(envelope(modelVersion='gemini-4-argon')),
                     purpose=interpretation.PURPOSE)
    models.ProviderRun.objects.filter(pk=run.pk).update(adapter_version=interpretation.ADAPTER_VERSION,
                                                        requested_model='gemini-4-argon')
    run.refresh_from_db()
    assert 'effect' not in (run.scope or {})
    return run


class CurrentVersionTests(TestCase):
    def setUp(self):
        self.enc, self.rev = scene()

    def test_the_current_version_is_jobs_own_and_the_v1_chain_keeps_its_holds(self):
        self.assertEqual(holds.current_adapter_version(), jobs._reading_adapter_version())
        with mock.patch.object(jobs, '_reading_adapter_version', return_value='synthetic-version@1'):
            self.assertEqual(holds.current_adapter_version(), 'synthetic-version@1')  # read at call time: one rule
        with v1_chain():
            self.assertEqual(holds.current_adapter_version(), interpretation.ADAPTER_VERSION)
            v1 = probe_run(self.enc, self.rev)
            outcome, hold = holds.settle(v1)
            self.assertEqual((outcome.reason, hold.run_id), (holds.MODEL, v1.pk))  # v1's mechanics, as recorded


class RequestBoundTests(FablePath, TestCase):
    """AMENDMENT-2 1.5 [R:connector-CONN-1]: a hold is request-bound when the answer that set it began as a 200 stream
    and says something about that request - a decline, or a hold an error event set after message_start."""

    def setUp(self):
        super().setUp()
        self.enc, self.rev = scene()

    def held(self, body, status=200, **run):
        made = fable_run(self.enc, self.rev, state='succeeded' if status == 200 else 'failed', http_status=status,
                         body=body, **run)
        outcome, hold = holds.settle(made)
        self.assertEqual(outcome.effect, holds.HOLD)
        return made, hold

    def test_a_decline_and_an_error_event_after_message_start_are_request_bound(self):
        for name, body, reason in (
                ('a decline', declined(), holds.DECLINED),
                ('a decline with no category', streams.answer_stream(None, stop_reason='refusal'), holds.DECLINED),
                ('invalid_request_error after message_start',
                 streams.sse(streams.start(), streams.error_event('invalid_request_error')), holds.REFUSED),
                ('billing_error inside a block', streams.sse(streams.start(), streams.block_start(0),
                                                            streams.text_delta(0, '{'),
                                                            streams.error_event('billing_error')), holds.QUOTA)):
            with self.subTest(name):
                run, hold = self.held(body)
                self.assertEqual(hold.reason, reason)
                self.assertTrue(holds.request_bound(hold))
                self.assertTrue(holds.request_bound_run(run))

    def test_every_other_hold_is_not(self):
        for name, body, status in (
                ('an error event before message_start', streams.sse(streams.error_event('authentication_error')), 200),
                ('a 401 body', streams.error_body('authentication_error'), 401),
                ('a 400 body', streams.error_body('invalid_request_error'), 400),
                ('a 402', b'', 402), ('a 403', b'', 403), ('a 404', streams.error_body('not_found_error'), 404),
                ('an unnamed 429', b'', 429), ('a substituted model', streams.answer_stream(model='claude-opus-5-5'),
                                               200),
                ('a fallback', streams.sse(streams.start(), streams.block_start(0, 'fallback'), streams.block_stop(0)),
                 200)):
            with self.subTest(name):
                run, hold = self.held(body, status)
                self.assertFalse(holds.request_bound(hold))
                self.assertFalse(holds.request_bound_run(run))
        # a Gemini hold (set while Gemini was the version in use) is never request-bound
        with mock.patch.object(holds, 'current_adapter_version', return_value=interpretation.ADAPTER_VERSION_V2):
            _, gemini_hold = holds.settle(gemini_run(self.enc, self.rev, http_status=401, body=b''))
        self.assertFalse(holds.request_bound(gemini_hold))

    def test_the_bytes_are_read_from_the_runs_exchange_and_fail_closed_when_gone(self):
        body = streams.sse(streams.start(), streams.error_event('invalid_request_error'))
        run = fable_run(self.enc, self.rev, body=body, response=False)
        hold = models.InterpreterHold.objects.create(reason=holds.REFUSED, http_status=200, run=run)
        self.assertTrue(holds.request_bound(hold))  # no bytes kept anywhere: read fail-closed (its request blocked)
        first = streams.sse(streams.error_event('invalid_request_error'))  # an error before message_start
        models.ProviderExchange.objects.create(run=run, turn=1, request_body=run.request_body,
                                               request_sha256=run.request_sha256, state='succeeded', http_status=200,
                                               response_bytes=first, response_sha256=hashlib.sha256(first).hexdigest())
        self.assertFalse(holds.request_bound(models.InterpreterHold.objects.get(pk=hold.pk)))  # read from turn 1
        models.ProviderExchange.objects.filter(run=run).update(response_bytes=body)  # its sha no longer checks
        self.assertTrue(holds.request_bound(models.InterpreterHold.objects.get(pk=hold.pk)))

    def test_a_declined_run_is_request_bound_with_or_without_its_hold_row(self):
        sent, hold = self.held(declined())
        copy = fable_run(self.enc, self.rev, body=declined(), sent=False, reused_from=sent)
        self.assertTrue(holds.request_bound_run(copy))  # its answer's hold
        holds.release(user=an_operator(), note=NOTE)
        self.assertTrue(holds.request_bound_run(sent))  # released: the block on its request stays
        unsent = fable_run(self.enc, self.rev, body=declined(), sent=False)  # a replayed decline: no hold row
        self.assertIsNone(holds.hold_of(unsent))
        self.assertTrue(holds.request_bound_run(unsent))
        self.assertFalse(holds.request_bound_run(fable_run(self.enc, self.rev, body=streams.answer_stream())))
        self.assertFalse(holds.request_bound_run(gemini_run(self.enc, self.rev, state='succeeded', http_status=200,
                                                            body=substituted())))


class ReleaseReportTests(FablePath, TestCase):
    def setUp(self):
        super().setUp()
        self.enc, self.rev = scene()
        self.operator = an_operator()

    def test_the_release_report_names_each_run_encounter_and_request(self):
        bound_run = fable_run(self.enc, self.rev, body=declined())
        _, bound = holds.settle(bound_run)
        free_run = fable_run(self.enc, self.rev, state='failed', http_status=401, body=b'')
        _, free = holds.settle(free_run)
        released = holds.release(user=self.operator, note=NOTE)
        self.assertEqual([item.hold for item in released], [bound, free])
        reports = [holds.release_report(item) for item in released]
        self.assertEqual(reports[0], {'hold': str(bound.pk), 'reason': 'declined',
                                      'means': holds.REASON_TEXT['declined'], 'run': str(bound_run.pk),
                                      'encounter': str(self.enc.pk), 'request': bound_run.request_sha256[:16],
                                      'request_bound': True, 'members': holds.BLOCKED})
        self.assertEqual((reports[1]['request_bound'], reports[1]['members'], reports[1]['run']),
                         (False, holds.UNBLOCKED, str(free_run.pk)))
        line = holds.released_line(released[0])
        for part in (str(bound.pk), str(bound_run.pk), str(self.enc.pk), bound_run.request_sha256[:16],
                     'stays blocked for members'):
            self.assertIn(part, line)
        self.assertNotIn(bound_run.request_sha256[16:], line)
        self.assertEqual(holds.release_report(bound), reports[0])  # the hold itself reads the same

    def test_interpreter_hold_release_prints_it(self):
        import io

        from django.core.management import call_command

        bound_run = fable_run(self.enc, self.rev, body=declined())
        _, bound = holds.settle(bound_run)
        free_run = fable_run(self.enc, self.rev, state='failed', http_status=429, body=b'')
        _, free = holds.settle(free_run)
        out = io.StringIO()
        call_command('interpreter_hold', '--release', '--username', self.operator.username, '--note', NOTE,
                     stdout=out)
        shown = out.getvalue()
        self.assertIn(holds.released_line(bound), shown)
        self.assertIn(holds.released_line(free), shown)
        self.assertIn(f'run {bound_run.pk} of encounter {self.enc.pk}, request {bound_run.request_sha256[:16]}; its '
                      'request stays blocked for members', shown)
        self.assertIn(f'run {free_run.pk} of encounter {self.enc.pk}, request {free_run.request_sha256[:16]}; a '
                      "member's next Resume may send its request again", shown)
        self.assertIn('2 holds released by synthetic-operator. Members may now Resume.', shown)
        self.assertIn('1 of them is request-bound: its request stays blocked for members', shown)
        self.assertNotIn(streams.CATEGORY_EXPLANATION, shown)


class FableRefusedStoredReadingTests(streams.FablePinned, FablePath, TestCase):
    """The Fable twin of RefusedStoredReadingTests (DECISIONS D229 on the Fable path): pass 1's stored answer stream,
    read when pass 2 is built and refused by the reader, is NotBuilt REFUSED with its Refusal, and that run's effect
    from holds with the refusal is a definite failure with the retry door; a cut-off answer stays TOO_LONG, a
    substituted model and a decline hold."""

    def setUp(self):
        super().setUp()
        self.enc, self.rev = scene()

    def pass_1_run(self, body: bytes) -> models.ProviderRun:
        request = fable_adapter.build_extraction_request(self.rev.text, (), 'paste')
        run = models.ProviderRun.objects.create(
            encounter=self.enc, revision=self.rev, provider=request.provider, adapter_version=request.adapter_version,
            purpose=interpretation.PURPOSE, request_sha256=request.canonical_sha256, request_body=request.body,
            contexts=list(request.contexts), state='succeeded', sent=True, http_status=200, response_bytes=body,
            response_sha256=hashlib.sha256(body).hexdigest())
        return models.ProviderRun.objects.get(pk=run.pk)

    def refused(self, run):
        stored_request = ProviderRequest(provider=run.provider, adapter_version=run.adapter_version,
                                         body=run.request_body, canonical_sha256=run.request_sha256,
                                         contexts=tuple(run.contexts or ()))
        with self.assertRaises(fable_adapter.NotBuilt) as caught:
            fable_adapter.build_appraisal_request(self.rev.text, (), 'paste', stored_request, bytes(run.response_bytes),
                                                  check=lambda text, pages, answer: {})
        self.assertEqual((caught.exception.reason, caught.exception.effect), (adapter.STORED, adapter.REFUSED))
        return caught.exception

    def test_a_refused_reading_of_a_usable_answer_fails_the_run_with_the_retry_door(self):
        for text, stage in (('{"x": ', 'envelope'), ('{}', 'schema')):
            with self.subTest(stage=stage):
                run = self.pass_1_run(streams.answer_stream(text))
                self.assertEqual(holds.classify_run(run).effect, holds.ANSWERED)  # without the refusal: answered
                refused = self.refused(run)
                self.assertEqual(refused.refusal.stage, stage)
                outcome, hold = holds.settle(run, refused=refused.refusal)
                self.assertEqual((outcome.effect, outcome.retry, outcome.why, hold),
                                 (holds.FAILED, True, refused.refusal.reason, None))
                row = SimpleNamespace(provider_run_id=run.pk, appraisal_run_id=None, state='refused',
                                      verification={'problems': [refused.refusal.reason]})
                self.assertEqual(holds.classify_run(run, inventory=row).effect, holds.FAILED)

    def test_a_cut_off_answer_stays_too_long_and_a_substituted_model_or_a_decline_holds(self):
        refused = self.refused(self.pass_1_run(streams.answer_stream(stop_reason='max_tokens')))
        self.assertEqual(refused.refusal.stage, 'envelope')
        outcome, hold = holds.settle(self.pass_1_run(streams.answer_stream(stop_reason='max_tokens')),
                                     refused=refused.refusal)
        self.assertEqual((outcome.effect, outcome.retry, hold), (holds.TOO_LONG, False, None))  # C5
        for body, reason in ((streams.answer_stream(model='claude-opus-5-5'), holds.MODEL), (declined(), holds.DECLINED)):
            with self.subTest(reason=reason):
                run = self.pass_1_run(body)
                refused = self.refused(run)
                outcome, hold = holds.settle(run, refused=refused.refusal)
                self.assertEqual((outcome.effect, outcome.reason, hold.reason, hold.run_id),
                                 (holds.HOLD, reason, reason, run.pk))
                holds.release(user=an_operator(f'synthetic-operator-refused-{reason}'), note=NOTE)
