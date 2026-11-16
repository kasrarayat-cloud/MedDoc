"""studio/jobs.py's design v2 pipeline (docs/gemini-migration/FINAL-V2.md 7.4 and 7.5; step 5b of its 8.1, the switch):
the stage tests. TEXT-ONLY and SYNTHETIC: every document is written here or in tests/v2/test_settle.py (fictional
clinicians, no real patient), every pass-1 answer is built by hand (test_settle's builders) and every pass-2 answer is
written by a deterministic oracle over the claim set the production builder makes; nothing is sent anywhere - the
interpreter is design v2's own InterpreterV2 whose one exchange is scripted (its loop, envelope, body checks,
classifier and Stop check are the production code's), and Corti is the in-process FakeProvider. The worker is driven
by jobs.claim_next and jobs.run_job explicitly, so every interleaving is deterministic.

What is proved, against 8.1 step 5b's done-when:
- replay stage tests for both passes: an upload runs extract, interpret (pass 1: extract-read, check and claim),
  appraise (pass 2: read and settle), analyze (engine/derive), predict and assess (engine/assess), the inventory row
  bound to both runs, the appraise key from the request sha [R:MO-5], and the assessment the events engine @2 made
  (PipelineTests);
- Stop between the passes: pass 1's answer stays stored, Resume queues appraise, which reuses it and sends pass 2 only
  (StopTests);
- every failure row of 7.5 (FailureTests): a definite failure (FAILED, retry offered, a retry of pass 2 re-sending pass
  2 only), auth/permission/quota (a bare 429 and a 402 included: the installation-wide hold, never retried in a loop),
  an unknown outcome (the reconcile flow), an answer the reader refuses (pass 1's refused row; pass 2's recorded on its
  run, no row), MAX_TOKENS (TOO_LONG, never re-sent for a member), a claim set over the bound (TOO_LONG, not sent), over
  the size bound (not sent), an unhealthy appraisal (recorded on its run, the retry door), a worker that died mid-stage
  (the settled path);
- the reuse door per workspace: a stored answer of either pass is reused in its workspace and never across one
  (ReuseTests);
- no inventory from pass 1 alone (PipelineTests, FailureTests).

And the renderer's one contract with read time (DECISIONS D246, step 5c's request R1 in full; the lead's seam findings
L1 and L2; RendererTests, PipelineTests):
- ENGINE-MADE items (test_assess's scenes, run through the renderer's own bounded child jobs._assess_child_v2 and
  _render_v2, and through _render_code): two codes competing for one balloon dilation and the base code beside them
  (competing, base_explained), a base code beside an act in doubt (base_included with its acts), an office visit
  beside a same-day sigmoidoscopy (separate_em with its acts) and an upper endoscopy within a coded upper EUS
  (base_within) are each worded by jobs.word_item - wording.build over overlay.item_slots or the item's Fill - with no
  refusal; the stored record (stored_from, JSON) read by read time (overlay.recount, review_view) gives back each item
  and words it identically, and reproduces the assessment's counts (overlay.assessment_counts: no UnreadableCounts);
- the date of service's item is the encounter's one question: no code carries it (persist_assessment refuses an
  encounter-scope clarification on a proposal);
- completeness names a not-listed session with overlay.session_label - the label the child hands engine/assess - so
  read time reproduces the stored counts for a not-listed session of each of the 17 session kinds (the 16 SessionKind
  values and a kind not established; the engine itself lists an office visit beside a procedure, D134), where any
  other label is UnreadableCounts;
- the support record carries what overlay.read_record reads (held_facts as engine/assess.jsonable writes them,
  kept_words, procedural), the member context is overlay.member_context over the context's facts, and jobs keeps no
  second label or item wording (one function, one home);
- persisted through the pipeline and read back by the readers (PipelineTests): a held base code's question is the
  renderer's, read time words it alike and reproduces the counts;
- the procedural mark where it is False (refute-5b-r1 F2, D262): an office visit alone, and beside a same-day
  sigmoidoscopy, recorded not procedural and read back so by read time (RendererTests).

And DECISIONS D267's record half (round w9r, step 5b): the renderer records, beside support['held_facts'] and in its
order, the message of the item that holds each procedure-keyed held fact (support['held_fact_messages']; None for every
other held fact), which customer_api.held_fact_words reads - engine-made for ENTEROSCOPY_THROUGH, ENTEROSCOPY_ROUTE and
EXAMINATION_ROUTE, read back whole by read time, and no field for a code with no procedure-keyed held fact
(RendererTests).

And DECISIONS D261 with its note (round w8r: step 5b builds it): jobs._Integrity.word_runs is contract/geometry's
letter-or-digit runs of a kept span, so R1 returns them and engine/assess hands them to C-10 as kept_words
(IntegrityTests); DENIED_REMOVAL v2 with the provider quoting 'No polyp was removed today.' WITH its stop excludes
45385 and leaves 45378 READY, as the same quote without its stop does, and with no runs the stop is a partial cover
held on statement_scope (D261Tests).
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from studio import interpretation, jobs, models, progress, provider_holds, review
from studio.interpretation import adapter, fable_adapter, holds, overlay, sentinel, wording
from studio.interpretation.contract import appraise_prompt, extract_prompt, jsonschema
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import assess as engine_assess
from studio.interpretation.engine import combination, coverage
from studio.interpretation.engine import questions as engine_questions
from studio.providers.base import request_sha256
from studio.types import CodeReference, RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import FakeProvider
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2.test_adapter import measured_pins
from tests.v2.test_fable_adapter import (FINAL_USAGE, answer_stream, block_start, block_stop, error_event, message_delta,
                                        sse, start, stop, text_delta)
from tests.v2.test_fable_adapter import error_body as fable_error_body
from tests.v2.test_settle import HEALTH_PIN, colonoscopy, event, fact, faithful, roles_of, src

AUTH = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
Run, Job = models.ProviderRun, models.Job
# AMENDMENT-2 (D275, D279): the interpreter of both passes is Claude Fable 5.2 through studio/interpretation/
# fable_adapter.py, and jobs.interpretation_adapter names it (section 9)
EXTRACTION, APPRAISAL = fable_adapter.EXTRACTION, fable_adapter.APPRAISAL
USAGE = copy.deepcopy(FINAL_USAGE)  # Anthropic's usage, final at message_delta (A2 1.4, 1.7)


def fable_pins() -> dict:
    """Every pin a Fable request of either pass is built and read under (AMENDMENT-2 8.2), set to the sha its owning
    step's own function measures on this tree (contract/extract_prompt.pins_fable, contract/appraise_prompt.pins_fable),
    as the integration owner writes them after the build's last repair (D202); and the @2 health thresholds' pin, which
    8.2 sets from D3 (D277 runs none), set to the thresholds' own document (test_settle.HEALTH_PIN). The pin tests of
    steps F0, F2 and F3 judge the written values."""
    return {**extract_prompt.pins_fable(), **appraise_prompt.pins_fable(), 'HEALTH_THRESHOLDS_SHA256_V3': HEALTH_PIN}

# --- the synthetic documents, written for these tests -----------------------------------------------------------------

NOTE = ('SYNTHETIC COLONOSCOPY REPORT\n'                                                 # S1
        'Date of service: 03/14/2031\n'                                                    # S2
        'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                    # S3
        '\n'
        'Findings: The colonoscope was advanced to the cecum.\n')                          # S4
POLYP = ('SYNTHETIC COLONOSCOPY REPORT\n'                                                 # S1
         'Date of service: 03/14/2031\n'                                                   # S2
         'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                   # S3
         '\n'
         'Findings: The colonoscope was advanced to the cecum.\n'                          # S4
         'A 4 mm polyp in the rectum was removed with a cold snare.\n')                    # S5
EXAM = 'The colonoscope was advanced to the cecum.'
SNARE = 'A 4 mm polyp in the rectum was removed with a cold snare.'


def note_answer():
    """NOTE's pass-1 answer: one colonoscopy session X1 reaching the cecum (E1), told in its Findings part."""
    return colonoscopy(NOTE)


def polyp_answer():
    """POLYP's pass-1 answer: NOTE's, and a cold-snare removal of a rectal polyp (E2) in session X1."""
    return colonoscopy(POLYP, event('E2', ['S5'], 'cold snare', 'was removed', 'snare',
                                    session=[fact('X1', src(['S5']))],
                                    target__places=[fact('rectum', src(['S5'], 'rectum'))],
                                    technique__device=[fact('cold_snare', src(['S5'], 'cold snare'))]))


ANSWERS = {NOTE: note_answer, POLYP: polyp_answer}


def body(answer_dict) -> bytes:
    """A complete 200 answer stream of the Fable connector (A2 1.4: message_start naming claude-fable-5-2, a thinking
    block, one text block carrying ``answer_dict`` as JSON, message_delta at end_turn, message_stop)."""
    return answer_stream(json.dumps(answer_dict))


def stream_of(text, *, stop_reason='end_turn', stop_details=None) -> bytes:
    """A complete 200 stream whose one text block is ``text`` and whose turn stopped for ``stop_reason``."""
    return answer_stream(text, stop_reason=stop_reason, stop_details=stop_details)


def declined_stream() -> bytes:
    """A complete 200 stream the model declined (stop_reason refusal; a category, no answer text): A2 1.5's
    request-bound hold, reason declined."""
    return answer_stream(None, stop_reason='refusal', stop_details={'type': 'refusal', 'category': 'cyber'})


def error_after_start(kind='invalid_request_error') -> bytes:
    """A complete 200 stream that opened with message_start and ended with an error event of ``kind`` (A2 1.5: a hold an
    error event sets after message_start is request-bound; an overload FAILED)."""
    return sse(start(), error_event(kind))


def error_first(kind='overloaded_error') -> bytes:
    """A complete 200 stream whose first event is an error event (A2 1.5 precedence (2) [R:connector-CONN-4])."""
    return sse(error_event(kind))


def answered(data: bytes, *, status=200, usage=True) -> RawExchange:
    """A live-like exchange that reached the vendor and was answered (``status``): a 200 stream, or an error body."""
    ok = status == 200
    return RawExchange(outcome='succeeded' if ok else 'failed', sent=True, http_status=status, response_bytes=data,
                       response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=9.5,
                       usage=copy.deepcopy(USAGE) if ok and usage else {},
                       usage_basis='provider_reported_tokens' if ok and usage else '',
                       requested_model=interpretation.MODEL_V3, returned_model=interpretation.MODEL_V3 if ok else '',
                       error='' if ok else f'The interpreter answered HTTP {status}; the response body is retained.')


UNKNOWN = RawExchange(outcome='unknown', sent=True, error='Read timed out after the request was sent.',
                      requested_model=interpretation.MODEL_V3)
# A2 1.5's rows: an HTTP 429 whose body names no rate_limit_error holds quota (D39's fail-closed reading); a 402
# (billing_error) holds quota; a 500 (api_error) fails, retry later
BARE_429 = b'Synthetic: too many requests (no error type named).'
HTTP_402 = fable_error_body('billing_error')
HTTP_500 = fable_error_body('api_error')
HTTP_400 = fable_error_body('invalid_request_error')


def appraisal_for(text, pages, kind, answer_dict):
    """The appraisal request the production builder makes for ``text`` and pass 1's ``answer_dict`` (the claims the
    oracle answers): fable_adapter's (A2 1.2), pass 1's stored answer a Fable stream."""
    extraction = fable_adapter.build_extraction_request(text, pages, kind)
    return fable_adapter.build_appraisal_request(text, pages, kind, extraction, body(answer_dict),
                                                 check=jobs._checked_findings({}))


def oracle_answer(built, oracle=faithful, unlisted=()) -> bytes:
    """Pass 2's answer to ``built``: the oracle's verdict per claim (test_settle's faithful oracle by default)."""
    roles = roles_of(built.built.claim_set)
    verdicts = [found for found in (oracle(claim, roles[claim.id], built.built.claim_set)
                                    for claim in built.built.claim_set.claims) if found is not None]
    return body({'verdicts': verdicts, 'unlisted': list(unlisted)})


class ScriptedInterpreterV2(fable_adapter.InterpreterF):
    """The Fable interpreter (fable_adapter.InterpreterF, AMENDMENT-2 section 1: its request checks, one-exchange loop,
    Stop check, stream reader, envelope and classifier are the production code's) whose one exchange is answered here:
    pass 1 by the registered answer of the document the request carries, pass 2 by the oracle over the claim set the
    production builder makes for it - each a complete answer stream - unless ``script`` holds RawExchanges for the
    purpose, given in turn first. Its endpoint is set, so a run reads as having called a vendor; its mode is 'replay', so
    no live gate applies. ``sent``: (purpose, request sha256) of every exchange made. (The class keeps design v2's name:
    tests/v2_replay.py and the guard matrix subclass it.)"""
    mode = 'replay'
    endpoint = 'https://interpreter.invalid/v1/messages'

    def __init__(self, answers=None, *, oracle=faithful, script=None):
        super().__init__()
        self.answers = dict(answers or {})
        self.oracle = oracle
        self.script = {purpose: list(items) for purpose, items in (script or {}).items()}
        self.sent = []
        self._request = None

    def send_loop(self, request, **kwargs):
        self._request = request
        return super().send_loop(request, **kwargs)

    def _document(self, text):
        revision = models.SourceRevision.objects.filter(text=text).order_by('-created_at').first()
        return text, jobs._participant_pages(revision), jobs._participant_document(revision)[0]

    def _exchange(self, body_dict, deadline, purpose):
        sha = request_sha256(body_dict)
        self.sent.append((purpose, sha))
        queued = self.script.get(purpose)
        if queued:
            return queued.pop(0)
        text = self._request.contexts[0]
        answer_dict = self.answers[text]() if callable(self.answers[text]) else self.answers[text]
        if purpose == EXTRACTION:
            return answered(body(answer_dict))
        built = appraisal_for(*self._document(text), answer_dict)
        assert built.request.canonical_sha256 == sha, 'the appraisal sent is not the one the builder makes'
        return answered(oracle_answer(built, self.oracle))


@override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR='/nonexistent-replay-dir', PROVIDER_MODE='disabled',
                   AUTHORIZATION_REF=AUTH, ASTRA_MODE='disabled', FABLE_MODE='disabled', INTERPRET_MAX_CHARS=20_000,
                   INTERPRET_MAX_PAGES=40)
class PipelineCase(TestCase):
    """The v2 pipeline under test: the pins of 2.5 measured on this tree (test_adapter.measured_pins) and the health
    thresholds pinned (step 8 writes HEALTH_THRESHOLDS_SHA256 from D3; settle refuses while it is empty), the sentinel
    installed, a scripted v2 interpreter and the fake Corti."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        status = sentinel.install()
        assert status['state'] == 'ok', status

    def setUp(self):
        super().setUp()
        self.enterContext(mock.patch.multiple(interpretation, HEALTH_THRESHOLDS_SHA256=HEALTH_PIN,
                                              **{**measured_pins(), **fable_pins()}))
        self.ws = f.workspace()
        self.user = f.member(self.ws, f.user(), role=models.Membership.REVIEWER)
        self.interpreter = self.scripted()
        self.provider = FakeProvider([('45378', EXAM)])
        self.enterContext(mock.patch.object(jobs, 'get_provider', side_effect=lambda: self.provider))

    # --- helpers --------------------------------------------------------------------------------------------------------

    def scripted(self, **kwargs):
        interpreter = ScriptedInterpreterV2(ANSWERS, **kwargs)
        patcher = mock.patch.object(fable_adapter, 'get_interpreter_v2', return_value=interpreter)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.interpreter = interpreter
        return interpreter

    def upload(self, text=NOTE, *, workspace=None, values=None):
        encounter = models.Encounter.objects.create(workspace=workspace or self.ws, title='Synthetic note',
                                                    created_by=self.user, user_values=dict(values or {}))
        revision = f.pasted_revision(encounter, self.user, text, extract=False)
        jobs.start_pipeline(revision, self.user)
        return encounter, revision

    def run_next(self, kind=None):
        job = jobs.claim_next()
        self.assertIsNotNone(job, f'no job queued; expected {kind}')
        if kind is not None:
            self.assertEqual(job.kind, kind, job.idempotency_key)
        return jobs.run_job(job)

    def drain(self, limit=50):
        done = []
        for _ in range(limit):
            job = jobs.claim_next()
            if job is None:
                return done
            done.append(jobs.run_job(job))
        self.fail('the worker did not drain')

    def through(self, *kinds, **upload):
        encounter, revision = self.upload(**upload)
        for kind in kinds:
            self.run_next(kind)
        encounter.refresh_from_db()
        revision.refresh_from_db()
        return encounter, revision

    def runs(self, encounter, purpose):
        return list(Run.objects.filter(encounter=encounter, purpose=purpose).order_by('created_at', 'pk'))

    def sent(self, purpose=None):
        return [item for item in self.interpreter.sent if purpose is None or item[0] == purpose]

    def state(self, encounter):
        encounter.refresh_from_db()
        return review._state_and_run(encounter)[0]


class PipelineTests(PipelineCase):
    def test_an_upload_runs_both_passes_and_the_engine_v2(self):
        encounter, revision = self.upload()
        done = self.drain()
        self.assertEqual([job.kind for job in done], ['extract', 'interpret', 'appraise', 'analyze', 'predict', 'assess'],
                         [(job.kind, job.state, job.error, job.result) for job in done])
        encounter.refresh_from_db()
        first, second = self.runs(encounter, EXTRACTION), self.runs(encounter, APPRAISAL)
        self.assertEqual((len(first), len(second)), (1, 1))
        self.assertEqual((first[0].state, first[0].sent, second[0].state, second[0].sent),
                         (Run.SUCCEEDED, True, Run.SUCCEEDED, True))
        # AMENDMENT-2: both runs are Fable's (provider, adapter version, the model asked, the anthropic-version each
        # sent: 1.1, 1.2 [R:replay-R8]), and every writer writes the new labels (8.1 [R:replay-R4])
        self.assertEqual({(run.provider, run.adapter_version, run.requested_model, run.scope.get('api_version'))
                          for run in first + second},
                         {(interpretation.PROVIDER_V3, interpretation.ADAPTER_VERSION_V3, interpretation.MODEL_V3,
                           interpretation.API_VERSION_V3)})
        [inventory] = models.EventInventory.objects.filter(revision=revision)
        self.assertEqual((inventory.state, inventory.interpretation_version, inventory.inventory_version),
                         ('read', interpretation.INTERPRETATION_PAIR_V3, interpretation.INVENTORY_VERSION_V3))
        self.assertTrue(first[0].scope.get('mode') == second[0].scope.get('mode') == 'replay')
        self.assertEqual(Job.objects.get(encounter=encounter, kind=jobs.INTERPRET).idempotency_key,
                         f'interpret:{revision.pk}:{interpretation.INTERPRETATION_VERSION_V3}')  # 1.9's key
        self.assertEqual((inventory.provider_run_id, inventory.appraisal_run_id), (first[0].pk, second[0].pk))
        appraise = Job.objects.get(encounter=encounter, kind=jobs.APPRAISE)
        self.assertEqual(appraise.idempotency_key,
                         f'appraise:{revision.pk}:{first[0].pk}:{second[0].request_sha256[:16]}')  # [R:MO-5]
        context = encounter.current_context
        self.assertEqual((context.version, context.event_inventory_id),
                         (interpretation.CONTEXT_VERSION_V2, inventory.pk))
        assessment = encounter.current_assessment
        self.assertEqual((assessment.engine_version, assessment.event_inventory_id, assessment.context_id),
                         (interpretation.ENGINE_VERSION_V3, inventory.pk, context.pk))
        self.assertEqual(assessment.interpretation.get('engine_version'), interpretation.ENGINE_VERSION_V3)
        self.assertEqual({p.support.get('event_reading') for p in assessment.proposals.all()},
                         {interpretation.ENGINE_VERSION_V3})
        self.assertEqual(assessment.completeness['event_coding']['version'], interpretation.ENGINE_VERSION_V3)
        self.assertTrue(review.fresh(encounter))
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, APPRAISAL])

    def test_no_inventory_is_written_from_pass_1_alone(self):
        encounter, revision = self.through('extract', 'interpret')
        [first] = self.runs(encounter, EXTRACTION)
        self.assertEqual((first.state, first.scope.get('effect')), (Run.SUCCEEDED, holds.ANSWERED))
        self.assertFalse(models.EventInventory.objects.filter(revision=revision).exists())  # FINAL-V2 7.4: no fallback
        [appraise] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertEqual(appraise.kind, jobs.APPRAISE)
        self.assertTrue(appraise.idempotency_key.startswith(f'appraise:{revision.pk}:{first.pk}:'))
        self.assertIsNone(encounter.current_context)  # nothing derived: the analyze reads a settled row only
        self.run_next(jobs.APPRAISE)
        self.assertEqual(models.EventInventory.objects.get(revision=revision).state, 'read')

    def test_the_appraise_key_names_the_request_sha_and_a_changed_claim_set_is_a_new_key(self):
        encounter, revision = self.through('extract', 'interpret')
        [queued] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        [first] = self.runs(encounter, EXTRACTION)
        built = appraisal_for(revision.text, jobs._participant_pages(revision),
                              jobs._participant_document(revision)[0], note_answer())
        self.assertEqual(queued.idempotency_key,
                         f'appraise:{revision.pk}:{first.pk}:{built.request.canonical_sha256[:16]}')
        # a key naming another claim set (a changed check or version since it was queued) sends nothing for it and
        # queues the stage of the request built now [R:MO-5]
        moved = Job.objects.filter(pk=queued.pk).update(idempotency_key=f'appraise:{revision.pk}:{first.pk}:{"0" * 16}')
        self.assertEqual(moved, 1)
        result = self.run_next(jobs.APPRAISE)
        self.assertEqual(result.result['skipped'], jobs.APPRAISE_MOVED)
        self.assertEqual(self.sent(APPRAISAL), [])
        self.assertEqual(self.run_next(jobs.APPRAISE).idempotency_key,
                         f'appraise:{revision.pk}:{first.pk}:{built.request.canonical_sha256[:16]}')
        self.assertEqual(len(self.sent(APPRAISAL)), 1)

    def test_d246_a_held_base_code_is_persisted_in_the_renderers_words_and_read_time_gives_them_back(self):
        """The lead's L1 end to end: POLYP's colonoscopy with its cold-snare removal, the provider selecting 45378 and
        45385. The base code is held beside the code of its session's act (base_explained, its codes form - on the
        integrated tree before D246 wording refused it and the assessment failed); persisted, its one question is the
        renderer's (word_item), and read time over the stored rows and the stored inventory (readers.EventReader) gives
        back its item, words it alike and reproduces the assessment's counts."""
        self.provider = FakeProvider([('45378', EXAM), ('45385', SNARE)])
        encounter, revision = self.upload(POLYP)
        done = self.drain()
        self.assertEqual([job.kind for job in done][-1], 'assess', [(job.kind, job.state, job.error) for job in done])
        encounter.refresh_from_db()
        assessment = encounter.current_assessment
        self.assertEqual(assessment.engine_version, interpretation.ENGINE_VERSION_V3)
        base = assessment.proposals.get(code='45378')
        [question] = list(base.clarifications.filter(state=models.Clarification.OPEN))
        self.assertEqual((base.status, question.scope, question.fact, question.proposal_id),
                         ('needs_clarification', 'proposal', 'base_included', base.pk))
        self.assertIn('45385', question.question)
        proposals, stored, decided, kwargs = review._overlay_inputs(assessment, {})
        R, member = kwargs['facts'], kwargs['member']
        self.assertIsNotNone(R)  # the stored inventory read back (store.load_v2, overlay.reading)
        coding = overlay.read_coding(assessment.completeness)
        engine = [p.key for p in stored if p.bucket == 'selected']
        recount = overlay.recount(stored, engine, engine, coding, R, member=member,
                                  assessed=overlay.assessed_out(assessment.completeness, stored),
                                  uncounted=overlay.assessed_uncounted(assessment.completeness, stored))
        live = recount.live[base.key]
        self.assertEqual(live.item.message, engine_questions.MessageId.BASE_EXPLAINED)
        again = wording.build(wording.Message(live.item.message.value),
                              overlay.item_slots(live.item, base.key, recount.joined, R), '')
        self.assertEqual((again.fact, again.question, again.reason), (question.fact, question.question, question.reason))
        views = review.effective_view(assessment)
        self.assertEqual([(item['fact'], item['question']) for item in views[base.key].questions],
                         [(question.fact, question.question)])
        self.assertEqual((views[base.key].recomputed, views[base.key].stale), ((), ()))
        counts = overlay.assessment_counts(assessment.completeness, R, stored, retrieval=assessment.retrieval)
        self.assertEqual(counts['conflicts'], assessment.completeness['conflicts'])
        self.assertEqual(counts['open_questions'], sum(1 for p in stored if p.bucket == 'selected' and p.questions))

    def test_d246_the_child_assesses_with_the_member_context_read_time_reads(self):
        """MemberContext is overlay.member_context over the context's facts (D246): the one the bounded child is handed is
        the one read time reads (readers.EventReader.member), with the member's own values in it."""
        real, seen = jobs.sentinel.run_counted, []

        def spy(fn, *args, **kwargs):
            if fn is jobs._assess_child_v2:
                seen.append(args[7])  # (view, date, text, pages, provider status, normalized, reference, member, ...)
            return real(fn, *args, **kwargs)

        with mock.patch.object(jobs.sentinel, 'run_counted', side_effect=spy):
            encounter, _ = self.upload(values={'setting': 'office', 'patient_status': 'established'})
            self.drain()
        encounter.refresh_from_db()
        from studio.interpretation import readers

        self.assertEqual(seen, [overlay.member_context(encounter.current_context.facts)])
        self.assertEqual(seen, [readers.EventReader.member(encounter.current_assessment)])
        self.assertEqual((seen[0].setting, seen[0].patient_status), ('office', 'established'))


class StopTests(PipelineCase):
    def test_a_stop_between_the_passes_keeps_pass_1_and_resume_sends_pass_2_only(self):
        encounter, revision = self.through('extract', 'interpret')
        jobs.stop_encounter(encounter, self.user)
        [cancelled] = Job.objects.filter(encounter=encounter, kind=jobs.APPRAISE)
        self.assertEqual(cancelled.state, Job.CANCELLED)
        self.assertEqual(self.state(encounter), 'stopped')
        self.assertTrue(review.can_resume(encounter))
        job = jobs.resume(encounter, self.user)
        self.assertEqual(job.kind, jobs.APPRAISE)
        self.assertTrue(job.idempotency_key.startswith(cancelled.idempotency_key + ':resume:'))
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, APPRAISAL])  # pass 1 not re-sent
        self.assertEqual(len(self.runs(encounter, EXTRACTION)), 1)
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=encounter.pk)))

    def test_a_stop_before_pass_1_sends_resume_runs_pass_1(self):
        encounter, revision = self.through('extract')
        jobs.stop_encounter(encounter, self.user)
        job = jobs.resume(encounter, self.user)
        self.assertEqual(job.kind, jobs.INTERPRET)
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, APPRAISAL])

    def test_a_stop_after_the_reading_resumes_the_analyze(self):
        encounter, revision = self.through('extract', 'interpret', 'appraise')
        jobs.stop_encounter(encounter, self.user)
        job = jobs.resume(encounter, self.user)
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual(job.kind, Job.ANALYZE)
        self.assertTrue(job.idempotency_key.startswith(f'analyze:{revision.pk}:{inventory.pk}:resume:'))
        self.drain()
        self.assertEqual(len(self.interpreter.sent), 2)
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=encounter.pk)))


class FailureTests(PipelineCase):
    """FINAL-V2 7.5, row by row, for each pass it names."""

    def test_a_definite_failure_of_pass_1_fails_with_the_retry_door(self):
        self.scripted(script={EXTRACTION: [answered(HTTP_500, status=500)]})
        encounter, revision = self.through('extract', 'interpret')
        [run] = self.runs(encounter, EXTRACTION)
        self.assertEqual((run.state, run.scope.get('effect')), (Run.FAILED, holds.FAILED))
        self.assertEqual(self.state(encounter), 'provider_failed')
        self.assertFalse(models.EventInventory.objects.exists())
        job = jobs.retry_reading(encounter, self.user)
        self.assertEqual(job.idempotency_key, jobs._interpret_key(revision, f'retry-release:{run.pk}'))
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, EXTRACTION, APPRAISAL])
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=encounter.pk)))

    def test_a_definite_failure_of_pass_2_fails_and_its_retry_resends_pass_2_only(self):
        self.scripted(script={APPRAISAL: [answered(HTTP_500, status=500)]})
        encounter, revision = self.through('extract', 'interpret', 'appraise')
        [run] = self.runs(encounter, APPRAISAL)
        self.assertEqual((run.state, run.scope.get('effect')), (Run.FAILED, holds.FAILED))
        self.assertEqual(self.state(encounter), 'provider_failed')
        self.assertFalse(models.EventInventory.objects.exists())
        self.assertEqual(progress.encounter_progress(encounter)['error']['action'], 'retry_reading')
        job = jobs.retry_reading(encounter, self.user)
        self.assertEqual(job.kind, jobs.APPRAISE)
        self.assertTrue(job.idempotency_key.endswith(f':retry-release:{run.pk}'))
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, APPRAISAL, APPRAISAL])
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=encounter.pk)))

    def assertHeldNeverRetried(self, encounter, purpose):  # noqa: N802 - unittest's naming
        [run] = self.runs(encounter, purpose)
        self.assertEqual(run.scope.get('effect'), holds.HOLD)
        self.assertTrue(holds.is_held())
        self.assertEqual(self.state(encounter), 'stopped')
        self.assertEqual(progress.encounter_progress(encounter)['phase'], 'paused')
        with self.assertRaises(jobs.Refused):
            jobs.retry_reading(encounter, self.user)  # RETRY_PAUSED: never retried while the hold stands
        sent = list(self.interpreter.sent)
        jobs.resume(encounter, self.user)
        self.drain()
        self.assertEqual(self.interpreter.sent, sent)  # a Resume while held pauses again, sending nothing
        held = Run.objects.filter(encounter=encounter, scope__held=holds.HELD_HOLD)
        self.assertTrue(held.exists())

    def test_a_bare_429_on_pass_1_holds_and_is_never_retried_in_a_loop(self):
        self.scripted(script={EXTRACTION: [answered(BARE_429, status=429)]})
        encounter, _ = self.through('extract', 'interpret')
        self.assertHeldNeverRetried(encounter, EXTRACTION)
        self.assertEqual(len(self.sent(EXTRACTION)), 1)

    def test_a_402_on_pass_2_holds_both_passes(self):
        self.scripted(script={APPRAISAL: [answered(HTTP_402, status=402)]})
        encounter, _ = self.through('extract', 'interpret', 'appraise')
        self.assertHeldNeverRetried(encounter, APPRAISAL)
        self.assertEqual(models.InterpreterHold.objects.get().reason, 'quota')  # A11
        other, _ = self.through('extract', 'interpret')  # another encounter: pass 1 pauses, nothing sent
        self.assertEqual(len(self.interpreter.sent), 2)

    def test_an_unknown_outcome_of_pass_2_is_reconciled_never_retried(self):
        self.scripted(script={APPRAISAL: [UNKNOWN]})
        encounter, revision = self.through('extract', 'interpret', 'appraise')
        [run] = self.runs(encounter, APPRAISAL)
        self.assertEqual(run.state, Run.UNKNOWN)
        self.assertEqual(self.state(encounter), 'provider_unknown')
        with self.assertRaises(jobs.Refused):
            jobs.retry_reading(encounter, self.user)
        self.assertTrue(jobs.reconcile(encounter, run, self.user, 'Synthetic: the vendor log shows no answer.'))
        [queued] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertEqual(queued.kind, jobs.APPRAISE)
        self.assertTrue(queued.idempotency_key.endswith(f':after-reconcile:{run.pk}'))
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, APPRAISAL, APPRAISAL])
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=encounter.pk)))

    def test_a_pass_1_answer_the_reader_refuses_is_a_refused_row_with_the_retry_door(self):
        self.scripted(script={EXTRACTION: [answered(stream_of('{"not": "the schema"'))]})
        encounter, revision = self.through('extract', 'interpret')
        [run] = self.runs(encounter, EXTRACTION)
        [row] = models.EventInventory.objects.filter(revision=revision)
        self.assertEqual((row.state, row.appraisal_run_id, row.provider_run_id), ('refused', None, run.pk))
        self.assertEqual(run.scope.get('effect'), holds.FAILED)
        self.assertEqual(self.runs(encounter, APPRAISAL), [])  # nothing is built or sent for pass 2
        self.assertEqual(self.state(encounter), 'provider_failed')
        job = jobs.retry_reading(encounter, self.user)
        self.assertEqual((job.kind, job.idempotency_key), (jobs.INTERPRET,
                                                          jobs._interpret_key(revision, f'retry-release:{run.pk}')))

    def test_a_pass_2_answer_the_reader_refuses_is_recorded_on_its_run_with_no_row(self):
        self.scripted(script={APPRAISAL: [answered(stream_of('{"verdicts": "no"}'))]})
        encounter, revision = self.through('extract', 'interpret', 'appraise')
        [run] = self.runs(encounter, APPRAISAL)
        self.assertEqual((run.scope.get('effect'), run.scope.get('refused')), (holds.FAILED, jobs.READING_REFUSED))
        self.assertFalse(models.EventInventory.objects.filter(revision=revision).exists())
        self.assertEqual(self.state(encounter), 'provider_failed')
        self.assertEqual(jobs.retry_reading(encounter, self.user).kind, jobs.APPRAISE)

    def test_max_tokens_is_too_long_and_never_resent_for_a_member(self):
        # AMENDMENT-2 1.5 [R:truth-T7]: stop_reason max_tokens keeps C5's effect (TOO_LONG, never re-sent for a member)
        # and is worded as a reading that reached its output limit - never as a document too long
        cut = stream_of('{"events": [', stop_reason='max_tokens')
        self.scripted(script={EXTRACTION: [answered(cut)]})
        encounter, revision = self.through('extract', 'interpret')
        [run] = self.runs(encounter, EXTRACTION)
        self.assertEqual(run.scope.get('effect'), holds.TOO_LONG)
        job = Job.objects.get(encounter=encounter, kind=jobs.INTERPRET)
        self.assertEqual((job.state, job.error), (Job.FAILED, jobs.INTERPRET_CUT_OFF_MESSAGE))
        self.assertNotIn('too long', jobs.INTERPRET_CUT_OFF_MESSAGE + jobs.APPRAISE_CUT_OFF_MESSAGE)
        block = progress.encounter_progress(encounter)
        self.assertEqual(block['error'], {'text': progress.INTERPRETATION_ERRORS['cut_off'][0],
                                          'action': 'new_document'})
        self.assertNotIn('too long', block['error']['text'])
        with self.assertRaises(jobs.Refused) as refused:
            jobs.retry_reading(encounter, self.user)
        self.assertEqual(str(refused.exception), jobs.RETRY_CUT_OFF)

    def test_a_claim_set_over_the_bound_is_too_long_and_not_sent(self):
        from studio.interpretation.contract import claims

        # the Fable path's bound (A2 8.2: claims.CLAIM_BOUND_V3), its pin measured again for the planted value
        self.enterContext(mock.patch.object(claims, 'CLAIM_BOUND_V3', 1))
        self.enterContext(mock.patch.multiple(interpretation, **fable_pins()))
        encounter, revision = self.through('extract', 'interpret', 'appraise')
        [run] = self.runs(encounter, APPRAISAL)
        self.assertEqual((run.state, run.sent, run.scope.get('refused'), run.scope.get('effect')),
                         (Run.NOT_SENT, False, jobs.CLAIMS, holds.TOO_LONG))
        self.assertEqual(self.sent(APPRAISAL), [])
        with self.assertRaises(jobs.Refused) as refused:
            jobs.retry_reading(encounter, self.user)
        self.assertEqual(str(refused.exception), jobs.RETRY_TOO_LONG)

    @override_settings(INTERPRET_MAX_CHARS=40)
    def test_over_the_size_bound_nothing_is_sent(self):
        encounter, revision = self.through('extract', 'interpret')
        [run] = self.runs(encounter, EXTRACTION)
        self.assertEqual((run.state, run.scope.get('refused')), (Run.NOT_SENT, jobs.SIZE))
        self.assertEqual(self.interpreter.sent, [])

    def test_an_unhealthy_appraisal_is_recorded_on_its_run_with_the_retry_door(self):
        def yes_man(claim, role, claim_set):
            from tests.v2.test_settle import verdict
            return verdict(claim, 'supports')  # every control supported too: control acceptance refuses
        self.scripted(oracle=yes_man)
        encounter, revision = self.through('extract', 'interpret', 'appraise')
        [run] = self.runs(encounter, APPRAISAL)
        self.assertEqual((run.scope.get('effect'), run.scope.get('refused')), (holds.FAILED, jobs.UNHEALTHY))
        self.assertIn('control_acceptance', run.scope['health']['refused'])
        self.assertFalse(models.EventInventory.objects.filter(revision=revision).exists())
        self.assertEqual(jobs.retry_reading(encounter, self.user).kind, jobs.APPRAISE)

    def test_a_worker_that_died_after_pass_2_was_answered_is_settled_from_its_exchange(self):
        encounter, revision = self.through('extract', 'interpret')
        appraise = Job.objects.get(encounter=encounter, kind=jobs.APPRAISE)
        real = jobs._settle_appraisal

        def dies(job, run, extraction, **kwargs):
            raise KeyboardInterrupt  # the worker dies after the run's outcome was recorded
        with mock.patch.object(jobs, '_settle_appraisal', side_effect=dies):
            job = jobs.claim_next()
            with self.assertRaises(KeyboardInterrupt), jobs._stage_scope(job):
                jobs.STAGES[jobs.APPRAISE](job)  # as the worker runs it, until it dies (the job stays running)
        # older than a reading stage's stale threshold (AMENDMENT-2 1.12: 1,440 s; settings.STALE_RUNNING_SECONDS_BY_KIND)
        Job.objects.filter(pk=appraise.pk).update(started_at=timezone.now() - timedelta(seconds=1500))
        jobs.mark_stale()
        appraise.refresh_from_db()
        self.assertEqual((appraise.state, appraise.result.get('settled')), (Job.SUCCEEDED, jobs.STALE_INTERPRETATION))
        [settled] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertIn(':settled:', settled.idempotency_key)
        self.assertEqual(real.__name__, '_settle_appraisal')
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, APPRAISAL])  # nothing re-sent
        self.assertEqual(models.EventInventory.objects.get(revision=revision).state, 'read')


class ReuseTests(PipelineCase):
    """FINAL-V2 7.4 door 2: a stored answer of either pass is reused in its workspace, never across one."""

    def test_the_same_text_in_the_same_workspace_reuses_both_passes(self):
        first, _ = self.upload()
        self.drain()
        second, revision = self.upload()
        self.drain()
        self.assertEqual(len(self.interpreter.sent), 2)  # nothing sent for the second encounter
        runs = self.runs(second, EXTRACTION) + self.runs(second, APPRAISAL)
        self.assertEqual([(run.sent, run.usage_basis) for run in runs],
                         [(False, 'reused_retained_result_no_new_usage')] * 2)
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=second.pk)))

    def test_another_workspace_never_reuses_a_stored_answer(self):
        self.upload()
        self.drain()
        other = f.workspace('Other synthetic practice')
        f.member(other, self.user)
        self.upload(workspace=other)
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, APPRAISAL] * 2)


class D261Tests(PipelineCase):
    """DECISIONS D261 and its note (step 5b of round w8r builds it): jobs._Integrity.word_runs gives
    contract/geometry.word_runs, so engine/assess hands C-10 (engine/evaluate.cover, FINAL-V2 4.6 condition 4) the kept
    evidence's letter-or-digit runs as kept_words. tests/v2_documents.py's DENIED_REMOVAL v2 - a colonoscopy to the cecum
    and the broad current denial 'No polyp was removed today.' (E2: snare, negated, all of its kind, today) - with the
    provider quoting the denial WITH its stop excludes 45385 (reinstatable, a citation) and leaves 45378 READY, exactly as
    the same quote without its stop does; with no runs (word_runs None, the fallback C-10 keeps) the stop is a gap past
    the statement's words, a partial cover: 45385 is held on statement_scope, never excluded."""

    def assessed(self, quote):
        """{code: Proposal} of DENIED_REMOVAL assessed through the pipeline, the provider selecting 45378 (the
        colonoscope's sentence) and 45385 (``quote``), in a workspace of its own (no answer reused across variants)."""
        from tests import v2_documents

        self.interpreter.answers[v2_documents.DENIED_REMOVAL] = v2_documents.denied_removal_answer
        self.provider = FakeProvider([('45378', v2_documents.COLONOSCOPE), ('45385', quote)])
        workspace = f.workspace('Synthetic practice for one quote')
        f.member(workspace, self.user)
        encounter, revision = self.upload(v2_documents.DENIED_REMOVAL, workspace=workspace)
        done = self.drain()
        self.assertEqual([(job.kind, job.state) for job in done],
                         [(kind, Job.SUCCEEDED) for kind in ('extract', 'interpret', 'appraise', 'analyze', 'predict',
                                                             'assess')], [(job.kind, job.error) for job in done])
        encounter.refresh_from_db()
        revision.refresh_from_db()  # the text the extract stage stored
        assessment = encounter.current_assessment
        self.assertEqual(assessment.engine_version, interpretation.ENGINE_VERSION_V3)
        return {p.code: p for p in assessment.proposals.exclude(bucket='alternative')}, revision

    def test_d261_the_denial_quoted_with_its_stop_excludes_45385_and_leaves_45378_ready_as_without_it(self):
        from studio.interpretation.contract import geometry
        from tests import v2_documents

        denial = v2_documents.DENIAL
        self.assertEqual(denial[-1], '.')
        for quote in (denial, denial[:-1]):  # v1's quote (with the stop), and the words alone
            with self.subTest(quote=quote):
                found, revision = self.assessed(quote)
                excluded, base = found['45385'], found['45378']
                self.assertEqual((excluded.bucket, excluded.status, excluded.reinstatable),
                                 ('excluded', 'excluded', True))
                self.assertEqual(excluded.support['exclusion']['cover'], 'citation')  # C-10: covered by citation
                self.assertEqual((base.bucket, base.status), ('selected', 'ready'))
                # the record carries R1's runs: the five words, the stop (when quoted) in none
                start = revision.text.index(denial)
                runs = geometry.word_runs(revision.text, ct.Span(start, start + len(quote)))
                self.assertEqual(excluded.support['kept_words'], [[run.start, run.end] for run in runs])
                self.assertEqual([revision.text[run.start:run.end] for run in runs],
                                 ['No', 'polyp', 'was', 'removed', 'today'])

    def test_d261_the_control_without_runs_the_stop_is_a_partial_cover_never_the_exclusion(self):
        from tests import v2_documents

        with mock.patch.object(jobs._Integrity, 'word_runs', None):  # C-10's fallback: every offset of a kept span
            found, _ = self.assessed(v2_documents.DENIAL)
        held = found['45385']
        self.assertEqual((held.bucket, held.status, held.support['kept_words']), ('selected', 'needs_clarification',
                                                                                  None))
        self.assertEqual([row.fact for row in held.clarifications.all()], ['statement_scope'])


class IntegrityTests(TestCase):
    """jobs._Integrity, R1 for engine/assess (its Integrity protocol): its word_runs is contract/geometry.word_runs
    (DECISIONS D261's note), so R1 returns the kept spans' letter-or-digit runs (engine/assess.admit)."""

    def test_d261_word_runs_is_geometrys_and_r1_returns_the_runs_of_the_kept_spans(self):
        from studio.interpretation.contract import geometry
        from studio.types import EvidenceSpan
        from tests import v2_documents

        integrity = jobs._Integrity()
        self.assertIs(integrity.word_runs, geometry.word_runs)
        text, denial = v2_documents.DENIED_REMOVAL, v2_documents.DENIAL
        start = text.index(denial)
        for quote in (denial, denial[:-1]):
            with self.subTest(quote=quote):
                spans = [EvidenceSpan(0, start, start + len(quote), quote, True)]
                evidence = engine_assess.admit('45385', spans, text, (), integrity)
                self.assertEqual(evidence.kept, (ct.Span(start, start + len(quote)),))
                self.assertEqual([text[run.start:run.end] for run in evidence.runs],
                                 ['No', 'polyp', 'was', 'removed', 'today'])
                self.assertEqual(evidence.runs, geometry.word_runs(text, evidence.kept[0]))


class RendererTests(TestCase):
    """jobs._render_code, the renderer of engine/assess's Assessed records into the AssessmentResult persist_assessment
    records (5a's R1, option (b)), fed real engine records: an excluded, reinstatable code carries the installed release's
    reinstatement gate and its structured waits (refutation 5b-r1, X5: without them review and the overlay, fail-closed,
    never offered approve on a reinstated code), and a counted code whose PFS row carries 26 and TC rows carries the
    PC/TC consideration FINAL-V2 4.4 lists (X4).

    And D246's one renderer contract with read time, driven by ENGINE-MADE items (the d246 tests): test_assess's scenes
    assessed by the renderer's own bounded child (jobs._assess_child_v2, its FactSet handed in where store's view would
    be read), rendered by _render_v2 and _render_code, stored as persist_assessment stores them (stored_from over JSON)
    and read back by read time (overlay.recount, review_view, assessment_counts)."""

    DAY = __import__('datetime').date(2031, 3, 14)

    def assessed(self, code, *, status, reinstatable=False, waits=(), exclusion=False, family=None):
        from studio.interpretation.contract.types import Attribute, SessionKind
        from studio.interpretation.engine import assess as engine_assess
        from studio.interpretation.engine.types import Cover, Evaluation, Exclusion, Id, IdFamily, Span

        excluded = status is engine_assess.Outcome.EXCLUDED
        ruled = (Exclusion(event=Id(IdFamily.EVENT, 2), fact=Attribute.STATUS, cover=Cover.CITATION,
                           anchor=(Span(0, 9),)) if exclusion else None)
        return engine_assess.Assessed(
            key='exc:0' if excluded else 'sel:0', code=code, family=family or SessionKind.COLONOSCOPY,
            origin=engine_assess.Origin.PRIMARY, proposed_by=('corti',),
            bucket=engine_assess.Bucket.EXCLUDED if excluded else engine_assess.Bucket.SELECTED, status=status, units=1,
            evidence=engine_assess.Evidence(code_kind='cpt1', scope_reason='', kept=(Span(0, 9),), dropped=()),
            reinstatable=reinstatable, session=None,
            evaluation=Evaluation(supporting=(Id(IdFamily.EVENT, 1),), held_facts=(), bindings={}, exclusion=ruled),
            held_facts=(), item=None, waits=tuple(waits), answered=None, considerations=(), competes=(),
            disagreements=(), primary_listed=True, trace=(), pfs=None, mue=None, fingerprint='f' * 64, question='')

    def held(self, fact):
        from studio.interpretation.contract.types import Result
        from studio.interpretation.engine.types import HeldFact, ItemKind

        return HeldFact(fact=fact, attribute=None, subject=None, result=Result.UNKNOWN, kind=ItemKind.QUESTION,
                        cause='reading_unknown', reason=None, spans=(), rank=None)

    def render(self, found, *, refs=None, sources=(), day=DAY, facts=None):
        # these hand-built records carry no item (item=None), so no combination or FactSet is read to word one; the
        # engine-made items are rendered by the D246 tests below
        return jobs._render_code(found, combination=None, R=None, text='The polyp was not removed. Synthetic.',
                                 pages=(), context_values=facts or {}, refs=refs or {}, sources=sources, day=day,
                                 active={}, provider='corti')

    def stored(self, rendered):
        """The proposal as persist_assessment stores it, for review's and the overlay's readers."""
        from types import SimpleNamespace

        return SimpleNamespace(checks=[{'id': check.id, 'status': check.status, 'detail': check.detail}
                                       for check in rendered.checks], support=rendered.support, family=rendered.family,
                               bucket=rendered.bucket)

    def test_x5_an_excluded_reinstatable_code_carries_the_reinstatement_gate_and_its_structured_waits(self):
        from studio.customer_api import held_fact_words
        from studio.interpretation import overlay
        from studio.interpretation.engine.types import Outcome
        from studio.types import ClarificationSpec
        from studio.validation import checks

        waits = (self.held('extent'), self.held('extent'), self.held('performed_status'))
        rendered = self.render(self.assessed('45385', status=Outcome.EXCLUDED, reinstatable=True, waits=waits,
                                             exclusion=True))
        [gate] = [check for check in rendered.checks if check.id == 'review.reinstatement']
        specs = [ClarificationSpec(scope='proposal', fact=fact, question=held_fact_words(fact),
                                   reason=held_fact_words(fact), family=rendered.family, proposal_key=rendered.key)
                 for fact in ('extent', 'performed_status')]
        self.assertEqual(gate, checks.reinstatement_check(specs, date_unknown=False))  # the installed release's gate
        self.assertEqual(gate.status, 'warn')
        self.assertEqual(rendered.support['reinstatement_waits'],
                         [{'fact': 'extent', 'question': held_fact_words('extent')},
                          {'fact': 'performed_status', 'question': held_fact_words('performed_status')}])
        stored = self.stored(rendered)
        self.assertFalse(review._reinstatement_clear(stored))  # approval waits on the questions ...
        asked = overlay._reinstatement_waits(stored)  # ... which the overlay asks as recorded, never its fallback
        self.assertEqual([(item['fact'], item['question']) for item in asked],
                         [('extent', held_fact_words('extent')), ('performed_status', held_fact_words('performed_status'))])

    def test_x5_with_nothing_left_to_wait_for_the_gate_passes_and_review_clears_a_reinstatement(self):
        from studio.interpretation import overlay
        from studio.interpretation.engine.types import Outcome

        rendered = self.render(self.assessed('45385', status=Outcome.EXCLUDED, reinstatable=True, exclusion=True))
        [gate] = [check for check in rendered.checks if check.id == 'review.reinstatement']
        self.assertEqual(gate.status, 'pass')
        self.assertNotIn('reinstatement_waits', rendered.support)
        stored = self.stored(rendered)
        self.assertTrue(review._reinstatement_clear(stored))  # review offers approve after a reinstatement
        self.assertEqual(overlay._reinstatement_waits(stored), ())

    def test_x5_with_no_date_of_service_the_date_waits_first_and_is_not_asked_as_a_question(self):
        from studio.interpretation.engine.types import Outcome

        waits = (self.held('service_date'), self.held('extent'))
        rendered = self.render(self.assessed('45385', status=Outcome.EXCLUDED, reinstatable=True, waits=waits,
                                             exclusion=True), day=None)
        [gate] = [check for check in rendered.checks if check.id == 'review.reinstatement']
        self.assertEqual(gate.status, 'warn')
        self.assertIn(jobs.REINSTATEMENT_DATE_WAIT, gate.detail)
        self.assertEqual(rendered.support['reinstatement_waits'][0],
                         {'fact': 'service_date', 'question': jobs.REINSTATEMENT_DATE_WAIT})
        self.assertEqual([wait['fact'] for wait in rendered.support['reinstatement_waits']], ['service_date', 'extent'])

    def test_x5_no_gate_on_a_code_that_is_not_reinstatable_or_not_excluded(self):
        from studio.interpretation.engine.types import Outcome

        for found in (self.assessed('45385', status=Outcome.EXCLUDED, reinstatable=False, exclusion=True),
                      self.assessed('45385', status=Outcome.READY)):
            with self.subTest(status=found.status, reinstatable=found.reinstatable):
                rendered = self.render(found)
                self.assertNotIn('review.reinstatement', [check.id for check in rendered.checks])
                self.assertNotIn('reinstatement_waits', rendered.support)

    def pfs_world(self, rows):
        from studio.reference.store import PFS
        from studio.types import CodeReference, ReferenceSourceInfo

        source = ReferenceSourceInfo(key='pfs-2031', kind=PFS, publisher='CMS', title='Synthetic PFS',
                                     release='CMS PFS synthetic 2031', url='https://pfs.invalid/', sha256='0' * 64,
                                     effective_start='2031-01-01', effective_end='2031-12-31', license_note='',
                                     scope_note='')
        pfs = {'status': 'A', 'global_days': 'XXX', 'mult_proc': '0', 'endo_base': '', 'pctc': '1',
               'modifier_rows': list(rows), 'source_key': 'pfs-2031'}
        return {'91010': CodeReference(code='91010', pfs=pfs, applicable_sources=('pfs-2031',))}, (source,), pfs

    def test_x4_a_counted_codes_pfs_row_with_26_and_tc_rows_carries_the_pc_tc_consideration(self):
        from studio.interpretation.contract.types import SessionKind
        from studio.interpretation.engine.types import Outcome
        from studio.types import Fact
        from studio.validation import checks

        refs, sources, pfs = self.pfs_world(('26', 'TC'))
        member = {'billing_context': Fact('billing_context', 'facility', 'user', ())}
        for status in (Outcome.READY, Outcome.NEEDS_CLARIFICATION):
            with self.subTest(status=status):
                rendered = self.render(self.assessed('91010', status=status, family=SessionKind.MOTILITY), refs=refs,
                                       sources=sources, facts=member)
                expected = checks.pctc_consideration(
                    '91010', pfs, 'CMS PFS synthetic 2031',
                    'facility, entered by a workspace member as encounter metadata')
                self.assertTrue(expected)
                self.assertIn(expected, rendered.modifier_considerations)
        undocumented = self.render(self.assessed('91010', status=Outcome.READY, family=SessionKind.MOTILITY),
                                   refs=refs, sources=sources)
        self.assertIn(checks.pctc_consideration('91010', pfs, 'CMS PFS synthetic 2031', 'not documented'),
                      undocumented.modifier_considerations)

    def test_x4_no_pc_tc_consideration_without_both_rows_or_on_an_excluded_code(self):
        from studio.interpretation.contract.types import SessionKind
        from studio.interpretation.engine.types import Outcome

        refs, sources, _ = self.pfs_world(('26',))
        rendered = self.render(self.assessed('91010', status=Outcome.READY, family=SessionKind.MOTILITY), refs=refs,
                               sources=sources)
        self.assertEqual(rendered.modifier_considerations, ())
        refs, sources, _ = self.pfs_world(('26', 'TC'))
        excluded = self.render(self.assessed('91010', status=Outcome.EXCLUDED, reinstatable=True, exclusion=True,
                                             family=SessionKind.MOTILITY), refs=refs, sources=sources)
        self.assertEqual(excluded.modifier_considerations, ())

    # --- D246: ENGINE-MADE items through the renderer and back through read time (the lead's L1 and L2) --------------

    def child(self, doc, codes, *, date=TA.DAY, member=TA.ENTERED, label_checked=True):
        """(the engine's Assessment, the AssessmentResult, the FactSet) of ``doc`` assessed by the renderer's own bounded
        child: jobs._assess_child_v2 with ``doc``'s settled FactSet (dated ``date``) handed in where store's view would
        be read (overlay.reading), the proposal provider selecting ``codes`` (test_assess's corti: (code, event)). The
        Assessment is the one engine/assess made inside the child (captured, never made again), and the child is
        asserted to word over that very FactSet and (``label_checked``) to name not-listed sessions with read time's
        label; ``self.label`` keeps the label it handed engine/assess."""
        R = TA.dated(doc.build(), date)
        view, seen, real = object(), {}, engine_assess.assess_facts

        def reading(given, day):
            self.assertIs(given, view)
            self.assertEqual(day, date)
            return R

        def capture(*args, **kwargs):
            seen['args'], seen['kwargs'] = args, kwargs
            seen['assessment'] = found = real(*args, **kwargs)
            return found

        with mock.patch.object(overlay, 'reading', side_effect=reading), \
                mock.patch.object(engine_assess, 'assess_facts', side_effect=capture):
            result = jobs._assess_child_v2(view, date, TA.TEXT, (), 'succeeded', TA.corti(*codes), D246Reference(),
                                           member, (), None, (), {}, 'ok', ())
        self.assertIs(seen['args'][0], R)
        self.assertEqual((seen['kwargs']['date_of_service'], seen['kwargs']['member']), (date, member))
        self.label = seen['kwargs']['label']
        if label_checked:
            self.assertIs(self.label, overlay.session_label)  # L2: the one label, read time's
        return seen['assessment'], result, R

    def stored_rows(self, result):
        """(stored rows, completeness) of ``result`` as persist_assessment stores them and the database gives them back:
        each proposal with its open clarifications (overlay.stored_from), and the completeness, through JSON."""
        rows = []
        for p in result.proposals:
            if p.bucket == 'alternative':
                continue
            row = overlay.stored_from(p)
            rows.append(dataclasses.replace(
                row, checks=tuple(json.loads(json.dumps(list(row.checks)))),
                questions=tuple(json.loads(json.dumps(list(row.questions)))),
                support=json.loads(json.dumps(row.support)), evidence=tuple(json.loads(json.dumps(list(row.evidence))))))
        return rows, json.loads(json.dumps(result.completeness))

    def own_counts(self, assessment):
        """The assessment's own counts as engine/assess computes them (its open items, unverified attributes, provider
        state and conflicts): this test's mirror of assess's sums, independent of the overlay."""
        unverifying = (ct.Result.UNRESOLVED, ct.Result.UNKNOWN, ct.Result.CONTRADICTED)
        selected = [p for p in assessment.codes if p.bucket is engine_assess.Bucket.SELECTED]
        open_items = sum(1 for p in selected if p.item is not None and p.item.held.rank is not None)
        open_items += sum(1 for found in assessment.service_questions if not found.closed)
        open_items += 1 if assessment.date_of_service is None else 0
        unverified = len({(held.subject, held.attribute) for p in assessment.codes
                          if p.evaluation is not None and p.evaluation.exclusion is None
                          for held in p.evaluation.held_facts if held.result in unverifying})
        return {'open_questions': open_items, 'unverified': unverified,
                'provider_ok': assessment.provider_status is engine_assess.ProviderStatus.SUCCEEDED,
                'conflicts': assessment.completeness['conflicts']}

    def read_back(self, rows, completeness, R, member=TA.ENTERED):
        """Read time over the stored rows: (overlay.recount over the engine's own counted set, review_view with no
        decision, assessment_counts)."""
        coding = overlay.read_coding(completeness)
        engine = [p.key for p in rows if p.bucket == 'selected' or overlay.answered_by_engine(p)[0]]
        return (overlay.recount(rows, engine, engine, coding, R, member=member,
                                assessed=overlay.assessed_out(completeness, rows),
                                uncounted=overlay.assessed_uncounted(completeness, rows)),
                overlay.review_view(rows, {}, completeness=completeness, facts=R, member=member),
                overlay.assessment_counts(completeness, R, rows))

    def test_d246_engine_items_are_worded_by_word_item_and_read_time_gives_them_back_in_the_same_words(self):
        for name, (scene, codes, expected) in D246_SCENES.items():
            with self.subTest(scene=name):
                assessment, result, R = self.child(scene(), codes)
                rendered = {p.key: p for p in result.proposals}
                held = [found for found in assessment.codes if found.item is not None]
                self.assertLessEqual(set(expected), {found.code for found in held})
                for found in assessment.codes:
                    p = rendered[found.key]
                    if found.item is None:
                        self.assertEqual(p.clarifications, ())
                        continue
                    slug = engine_assess.family_slug(found.family)
                    spec = jobs.word_item(found.item, found.key, assessment.combination, R, TA.TEXT, family=slug)
                    # one item per held code (D182), worded with no refusal, as a proposal's question
                    self.assertEqual((p.status, p.clarifications), ('needs_clarification', (spec,)))
                    self.assertEqual((spec.scope, spec.family, spec.proposal_key, spec.fact),
                                     ('proposal', slug, found.key, found.item.held.fact))
                    # wording.build over overlay.item_slots, else the Slots of the item's Fill (D246's contract)
                    slots = overlay.item_slots(found.item, found.key, assessment.combination, R)
                    self.assertEqual(slots is not None, found.item.message in overlay.TEXT_FREE, found.code)
                    built = wording.build(wording.Message(found.item.message.value),
                                          slots if slots is not None else jobs._slots_of(found.item.fill), TA.TEXT)
                    self.assertEqual((spec.fact, spec.question, spec.reason), (built.fact, built.question, built.reason))
                    if found.code in expected:
                        cause, named = expected[found.code]
                        self.assertEqual(found.item.held.cause, cause)
                        self.assertIn(found.item.message, overlay.TEXT_FREE)
                        self.assertIn(named, spec.question + ' ' + spec.reason)
                rows, completeness = self.stored_rows(result)
                recount, views, counts = self.read_back(rows, completeness, R)
                by_key = {row.key: row for row in rows}
                for found in held:
                    live = recount.live[found.key]
                    self.assertEqual((live.item, live.held), (found.item, found.held_facts))  # the engine's own item
                    [question] = by_key[found.key].questions
                    if found.item.message in overlay.TEXT_FREE:  # read time words it afresh: in the stored words
                        again = wording.build(wording.Message(live.item.message.value),
                                              overlay.item_slots(live.item, found.key, recount.joined, R), '')
                        self.assertEqual((again.fact, again.question, again.reason),
                                         (question['fact'], question['question'], question['reason']))
                for key, view in views.items():
                    self.assertEqual((list(view.questions), view.recomputed, view.stale),
                                     (list(by_key[key].questions), (), ()), key)
                self.assertEqual(counts, self.own_counts(assessment))  # no UnreadableCounts: the counts reproduce

    def test_d246_render_code_records_the_item_and_what_read_time_reads(self):
        scene, codes, _ = D246_SCENES['competing and base_explained']
        assessment, result, R = self.child(scene(), codes)
        rendered = {p.key: p for p in result.proposals}
        reference = D246Reference()
        refs = {found.code: reference.lookup(found.code, TA.DAY) for found in assessment.codes
                if found.evaluation is not None and found.status.value != 'excluded'}
        for found in assessment.codes:
            with self.subTest(code=found.code):
                p = jobs._render_code(found, combination=assessment.combination, R=R, text=TA.TEXT, pages=(),
                                      context_values={}, refs=refs, sources=(), day=TA.DAY, active={},
                                      provider='corti')
                self.assertEqual(p, rendered[found.key])  # _render_v2 renders each code so
                self.assertEqual(p.support['held_facts'], engine_assess.jsonable(found.held_facts))
                # R1's kept runs, which jobs._Integrity gives (D261: geometry.word_runs of each kept span)
                runs = found.evidence.runs
                self.assertEqual(runs, tuple(dict.fromkeys(run for span in found.evidence.kept
                                                           for run in jobs._Integrity().word_runs(TA.TEXT, span))))
                self.assertEqual(p.support['kept_words'], engine_assess.jsonable(runs))
                self.assertEqual(p.support['procedural'], engine_assess.procedural(
                    SimpleNamespace(family=found.family, evaluation=found.evaluation), found.pfs))
                record = overlay.read_record({row.key: row for row in self.stored_rows(result)[0]}[found.key])
                self.assertEqual((record.held, record.procedural, record.kept_words),
                                 (found.held_facts, p.support['procedural'], runs))  # read back whole

    def test_f2_an_office_visit_alone_is_recorded_not_procedural_and_read_time_reads_it_so(self):
        """refute-5b-r1 F2 (DECISIONS D262: step 5b): the procedural mark through _render_code where it is False - an
        office visit alone (test_assess's _office, 99213 READY: an E/M code is never procedural, engine/assess.procedural),
        and an office visit beside a same-day sigmoidoscopy (99213 False, 45330 True). The record carries the mark
        assess's combination read, overlay.read_record reads it back and read time's recount reproduces the stored
        record; a mark True for every code (mutant ME) fails here, as read time then reads 99213 as a procedure
        (overlay.RecordMismatch)."""
        for name, scene, codes, expected in (('99213 alone', TA._office, (('99213', 1),), {'99213': False}),
                                             ('99213 beside 45330', TA.office_and_sigmoidoscopy,
                                              (('99213', 1), ('45330', 2)), {'99213': False, '45330': True})):
            with self.subTest(scene=name):
                assessment, result, R = self.child(scene(), codes)
                rendered = {p.key: p for p in result.proposals}
                reference = D246Reference()
                refs = {found.code: reference.lookup(found.code, TA.DAY) for found in assessment.codes
                        if found.evaluation is not None and found.status.value != 'excluded'}
                rows, completeness = self.stored_rows(result)
                by_key = {row.key: row for row in rows}
                marks = {}
                for found in assessment.codes:
                    p = jobs._render_code(found, combination=assessment.combination, R=R, text=TA.TEXT, pages=(),
                                          context_values={}, refs=refs, sources=(), day=TA.DAY, active={},
                                          provider='corti')
                    self.assertEqual(p, rendered[found.key])
                    marks[found.code] = p.support['procedural']
                    self.assertIs(overlay.read_record(by_key[found.key]).procedural, p.support['procedural'])
                self.assertEqual(marks, expected)
                if name == '99213 alone':
                    [found] = assessment.codes
                    self.assertEqual(found.status, engine_assess.Outcome.READY)
                recount, views, counts = self.read_back(rows, completeness, R)  # no RecordMismatch
                self.assertEqual({found.code: views[found.key].status for found in assessment.codes},
                                 {found.code: found.status.value for found in assessment.codes})
                self.assertEqual(counts, self.own_counts(assessment))

    def test_d267_the_renderer_records_the_message_of_the_item_that_holds_each_procedure_keyed_held_fact(self):
        """DECISIONS D267's record half (step 5b; refute-r3c-r1 F7, D253 QX (ii)): beside support['held_facts'], in its
        order, support['held_fact_messages'] names the message of the item that holds each procedure-keyed held fact
        and None for every other held fact - the code's own item's message for the held fact it rests on, and
        engine/questions.message_of (over the code's own facts) for any other - which customer_api.held_fact_words
        reads (step r3c). Engine-made through the renderer's own bounded child: the route part whose only unknown is
        the anatomy passed through (44380, ENTEROSCOPY_THROUGH), the oral classes' two-route doubt (44360,
        ENTEROSCOPY_ROUTE) and the stoma EUS class's approach (44406, EXAMINATION_ROUTE), each where the procedure is
        known. Read time reads the record whole: overlay.read_record gives the held facts back unchanged and the recount
        reproduces the stored record (no RecordMismatch). A code with no procedure-keyed held fact records no field."""
        from studio.interpretation.engine import evaluate as engine_evaluate
        from tests.v2 import test_evaluate as TE
        from tests.v2.evaluate_fixtures import sup, unit, unres
        from tests.v2.test_questions import J5, ORAL4, stoma_route

        two_routes = stoma_route(ORAL4, through=TE.doubted(TE.Y(1), spans=(unit(3),)),
                                 entry_type=sup(ct.AnatomyType.STOMA, spans=(unit(8),)), reached=J5)
        scenes = (('44380', stoma_route(), engine_questions.MessageId.ENTEROSCOPY_THROUGH),
                  ('44360', two_routes, engine_questions.MessageId.ENTEROSCOPY_ROUTE),
                  ('44406', TE.lower_eus(sup(ct.Extent.SIGMOID_COLON), unres(ct.Extent.DESCENDING_COLON)),
                   engine_questions.MessageId.EXAMINATION_ROUTE))
        for code, built, message in scenes:
            with self.subTest(code=code):
                assessment, result, R = self.child(SimpleNamespace(build=lambda built=built: built), ((code, 1),))
                [found] = assessment.codes
                self.assertEqual((found.status, found.item.message, found.item.held.fact),
                                 (engine_assess.Outcome.NEEDS_CLARIFICATION, message, 'procedure'))
                [p] = [item for item in result.proposals if item.key == found.key]
                code_facts = engine_evaluate.code_facts(code)
                expected = [None if held.fact != 'procedure' else found.item.message.value if held == found.item.held
                            else engine_questions.message_of(held, code_facts).value for held in found.held_facts]
                self.assertEqual(p.support['held_fact_messages'], expected)
                self.assertEqual(p.support['held_facts'], engine_assess.jsonable(found.held_facts))  # unchanged
                self.assertEqual(expected[found.held_facts.index(found.item.held)], message.value)
                rows, completeness = self.stored_rows(result)
                self.assertEqual(rows[0].support['held_fact_messages'], expected)  # through JSON, as persisted
                self.assertEqual(overlay.read_record(rows[0]).held, found.held_facts)
                recount, views, counts = self.read_back(rows, completeness, R)  # no RecordMismatch
                self.assertEqual(views[found.key].status, found.status.value)
        # the 44406 scene holds a non-procedure fact too (R6's extent): None beside it
        self.assertIn(None, expected)
        scene, codes, _ = D246_SCENES['competing and base_explained']
        assessment, result, R = self.child(scene(), codes)
        self.assertFalse([held for found in assessment.codes for held in found.held_facts if held.fact == 'procedure'])
        self.assertEqual([p.code for p in result.proposals if 'held_fact_messages' in p.support], [])

    def test_d246_the_date_item_is_the_encounters_one_question_carried_by_no_code(self):
        assessment, result, R = self.child(EF.colonoscopy(), (('45385', 2),), date=None)
        [found] = assessment.codes
        self.assertIs(found.item.message, engine_questions.MessageId.SERVICE_DATE)
        spec = jobs.word_item(found.item, found.key, assessment.combination, R, TA.TEXT, family='gi.colonoscopy')
        self.assertEqual((spec.scope, spec.fact, spec.family, spec.proposal_key),
                         ('encounter', 'service_date', '', ''))
        [p] = result.proposals
        self.assertEqual((p.status, p.clarifications), ('needs_clarification', ()))  # no code carries it
        self.assertEqual([(item.scope, item.fact, item.proposal_key) for item in result.clarifications],
                         [('encounter', 'service_date', '')])  # asked once, at encounter scope
        # persist_assessment refuses an encounter-scope clarification on a proposal: none is on one
        self.assertEqual([item.scope for q in result.proposals for item in q.clarifications if item.scope != 'proposal'],
                         [])
        rows, completeness = self.stored_rows(result)
        recount, views, counts = self.read_back(rows, completeness, R)
        self.assertEqual(recount.live[found.key].item, found.item)
        self.assertEqual(views[found.key].questions, ())
        self.assertEqual(counts, self.own_counts(assessment))
        self.assertEqual(counts['open_questions'], 1)  # the encounter's date question, counted once

    def test_d246_read_time_reproduces_the_counts_for_a_not_listed_session_of_each_of_the_17_kinds(self):
        """L2: completeness names a not-listed session with the label the child hands engine/assess, and read time
        reproduces the stored reason with overlay.session_label. The engine lists only an office visit beside a
        procedure (D134; the next test); sessions of RECOGNISED or unprofiled families are never reconciled and a session
        whose kind is not established is listed in doubt, so the not-listed reading of X2 is planted in
        coverage.reconcile - the one function both assess and read time call - for each of the 17 kinds (the 16 session
        kinds and a kind not established). A label other than read time's is never reproduced (UnreadableCounts)."""
        kinds = [*ct.SessionKind, None]
        self.assertEqual(len(kinds), 17)
        real = coverage.reconcile

        def planted(R, counted, **kwargs):
            found = real(R, counted, **kwargs)
            sessions_ = kwargs.get('sessions_') or coverage.sessions(coverage.Reader.of(R).R)
            if sessions_[EF.X(2)] not in found.not_listed:
                found.not_listed.append(sessions_[EF.X(2)])
            return found

        for kind in kinds:
            with self.subTest(kind=kind):
                doc = EF.colonoscopy(snare=False)
                doc.session(2, kind if kind is not None else EF.unres(ct.SessionKind.EGD))
                with mock.patch.object(coverage, 'reconcile', side_effect=planted):
                    assessment, result, R = self.child(doc, (('45378', 1),), label_checked=False)
                    session = coverage.sessions(R)[EF.X(2)]
                    self.assertIs(session.kind, kind)
                    rows, completeness = self.stored_rows(result)
                    # read time reproduces the stored counts (L2: before D246 five kinds read UnreadableCounts here)
                    self.assertEqual(overlay.assessment_counts(completeness, R, rows), self.own_counts(assessment))
                    listed = [reason for reason in result.completeness['reasons'] if 'not listed as unresolved' in reason]
                    self.assertEqual(len(listed), 1, result.completeness['reasons'])
                    self.assertTrue(listed[0].endswith(': ' + overlay.session_label(session)), listed[0])
                    self.assertIs(self.label, overlay.session_label)  # the one label, read time's
                    # the control: assessed with any other label, the stored reason is not read time's
                    other = engine_assess.assess_facts(
                        R, date_of_service=TA.DAY, text=TA.TEXT, pages=(), integrity=jobs._Integrity(),
                        provider_status='succeeded', proposals=TA.corti(('45378', 1)), reference=D246Reference(),
                        member=TA.ENTERED, label=lambda found: 'a session ' + overlay.session_label(found))
                    rendered = jobs._render_v2(other, R=R, text=TA.TEXT, pages=(), context={},
                                               provider_status='succeeded', normalized=TA.corti(('45378', 1)),
                                               reference=D246Reference(), service_date=TA.DAY, extraction_status='ok',
                                               extraction_messages=())
                    rows, completeness = self.stored_rows(rendered)
                    with self.assertRaises(overlay.UnreadableCounts):
                        overlay.assessment_counts(completeness, R, rows)

    def test_d246_an_office_visit_beside_a_procedure_is_not_listed_and_read_time_reproduces_its_counts(self):
        doc = EF.colonoscopy(snare=False)
        doc.session(3, ct.SessionKind.OFFICE_EM, encounter=EF.sup(ct.EncounterRelation.THIS_ENCOUNTER))
        doc.act(5, ct.Kind.EM_VISIT, session=EF.X(3), basis=EF.sup(ct.EmBasis.TOTAL_TIME))
        assessment, result, R = self.child(doc, (('45378', 1),))
        [session] = assessment.coverage.not_listed  # D134: listed by the engine itself, no plant
        self.assertEqual((session.id, session.kind), (EF.X(3), ct.SessionKind.OFFICE_EM))
        self.assertIn(': ' + overlay.session_label(session), result.completeness['statement'])
        rows, completeness = self.stored_rows(result)
        self.assertEqual(self.read_back(rows, completeness, R)[2], self.own_counts(assessment))

    def test_d246_jobs_keeps_no_second_label_or_item_wording(self):
        for name in ('_session_label', '_clarification_of', '_held_record'):
            with self.subTest(name=name):
                self.assertFalse(hasattr(jobs, name))  # one function, one home: overlay's label, word_item's words


class D246Reference:
    """The prefetched reference lookup the bounded child reads: no PFS or MUE row for any code and no source (R9:
    records only)."""

    def lookup(self, code, service_date):
        return CodeReference(code=code)

    def sources(self):
        return ()


def base_in_doubt():
    """test_overlay's base-question scene: a colonoscopy X1 (its examination E1) whose snare removal E2 in the sigmoid
    colon is stated in doubt (its status unresolved): 45378 is held beside the act in doubt (base_included, its acts)."""
    doc = EF.colonoscopy(snare=False)
    doc.act(2, ct.Kind.SNARE, places=[EF.sup(ct.Landmark.SIGMOID_COLON)], status=EF.unres(ct.Status.PERFORMED))
    return doc


def egd_within_eus():
    """An upper endoscopy X1 (its examination E1) and an upper EUS X2 (its examination E2 at the pancreas and an FNA
    E3): 43235 is held within the EUS 43242 codes (base_within, an established whole), and 43242 asks its stations."""
    doc = EF.egd()
    doc.session(2, ct.SessionKind.EUS, tract=EF.sup(ct.Tract.UPPER))
    doc.exam(2, session=EF.X(2), places=[EF.sup(ct.Landmark.PANCREAS)])
    doc.act(3, ct.Kind.FNA, session=EF.X(2), places=[EF.sup(ct.Landmark.PANCREAS)], device=EF.sup(ct.Device.NEEDLE))
    return doc


# scene -> (its settled inventory, the codes the provider selects, {code: (the cause its item rests on, words its
# question or reason names)}): test_assess's scenes (CombinationTests) and two of the same shape
D246_SCENES = {
    'competing and base_explained': (TA.one_dilation, (('43249', 2), ('43233', 2), ('43235', 1)), {
        '43249': (combination.COMPETING_CAUSE, '43233'), '43233': (combination.COMPETING_CAUSE, '43249'),
        '43235': (combination.BASE_CAUSE, '43249, 43233')}),
    'base_included with its acts': (base_in_doubt, (('45378', 1),), {
        '45378': (combination.BASE_CAUSE, 'snare removal (stated in doubt)')}),
    'separate_em with its acts': (TA.office_and_sigmoidoscopy, (('99213', 1), ('45330', 2)), {
        '99213': (combination.SAME_DAY_CAUSE, 'Examination is documented as performed on the same date')}),
    'base_within': (egd_within_eus, (('43235', 1), ('43242', 3)), {'43235': (combination.WITHIN_CAUSE, '43242')}),
}


class V1RowsTests(TestCase):
    """Refutation 5b-r1, X8 (FINAL-V2 5.7: jobs.py's facts and events imports are rewired): the branches that read a v1 row
    through a retired v1 module run only under the test-only v1 chain; in production a v1 row fails closed, resumable,
    before any retired module is reached."""

    def test_x8_a_v1_row_outside_the_v1_chain_fails_closed_before_any_retired_module_is_reached(self):
        from types import SimpleNamespace

        reached = []

        class Retired:
            def __getattr__(self, name):
                reached.append(name)
                raise AssertionError(f'a retired v1 module was reached: {name}')
        v1 = SimpleNamespace(interpretation_version=interpretation.INTERPRETATION_VERSION,
                             inventory_version=interpretation.INVENTORY_VERSION, pk='v1', sha256='0' * 64, revision=None)
        self.assertFalse(jobs._is_v2_inventory(v1))
        calls = (lambda: jobs._stand_in(None, v1, None, None),
                 lambda: jobs.derived_facts(SimpleNamespace(user_values={}), v1, None),
                 lambda: jobs._member_date_state(SimpleNamespace(user_values={}, facts={}), None, v1, None))
        with mock.patch.object(interpretation, 'facts', Retired(), create=True), \
                mock.patch.object(interpretation, 'assess', Retired(), create=True):
            for call in calls:
                with self.assertRaises(jobs.StageCancelled) as cancelled:
                    call()
                self.assertEqual(str(cancelled.exception), jobs.EARLIER_READING_MESSAGE)
            self.assertEqual(reached, [])
            with mock.patch.object(jobs, '_v1_chain', return_value=True):  # control: the v1 chain reaches its module
                with self.assertRaises(AssertionError):
                    jobs._stand_in(None, v1, None, None)
            self.assertEqual(reached, ['routing_stand_in'])


# --- AMENDMENT-2's pipeline (step F6 of its section 10): the Fable interpreter through the stages -------------------------
#
# Everything below runs the production stages (jobs.stage_interpret, jobs.stage_appraise, their settle, the doors, the
# stale sweep, retry_reading and resume) over the Fable connector's own reading of constructed answer streams and error
# bodies (tests/v2/test_fable_adapter's builders: SSE bytes and error bodies built in the test). Nothing is sent.

REAL_GET_INTERPRETER = fable_adapter.get_interpreter_v2  # the configured interpreter, as the worker builds it
# A2 1.5: the holds that are REQUEST-BOUND - a decline (stop_reason refusal), or a hold an error event set after
# message_start (here, an authentication_error event inside the stream) - by the labels of test_fable_adapter.table()
REQUEST_BOUND_ROWS = frozenset({'a refusal, any category', 'a refusal with no category',
                                'authentication_error (a stream error event)'})
# no member sentence names a provider or a model (D22; A2 1.5 and 9)
PROVIDER_NAMES = ('anthropic', 'claude', 'fable', 'gemini', 'google', 'opus', 'sonnet', 'corti', 'astra')


def exchange_of(outcome, status, data) -> RawExchange:
    """The exchange the connector records for one row of A2 1.5's table: a 200 stream (outcome 'succeeded', as http.post
    records a whole body the complete hook accepts) or an error body (outcome 'failed')."""
    return RawExchange(outcome=outcome, sent=True, http_status=status, response_bytes=data,
                       response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=7.0, usage={},
                       requested_model=interpretation.MODEL_V3, returned_model='',
                       error='' if status == 200 else f'The interpreter answered HTTP {status}.')


class FableCase(PipelineCase):
    """PipelineCase with the helpers AMENDMENT-2's stage tests share: a fresh workspace per encounter (no stored answer
    reused across scenes), the operator's release of every standing hold, and the member sentence a stage left."""

    def fresh_encounter(self, text=NOTE):
        workspace = f.workspace(f'Synthetic practice {models.Encounter.objects.count()}')
        f.member(workspace, self.user, role=models.Membership.REVIEWER)
        return self.upload(text, workspace=workspace)

    def release_holds(self, note='Synthetic release: the cause was reviewed.'):
        operator = f.user('synthetic-operator-' + str(models.User.objects.count()))
        from tests.support import operator as ops

        ops.grant(operator)
        return holds.release(user=operator, note=note)

    def cancel_queued(self):
        Job.objects.filter(state=Job.QUEUED).update(state=Job.CANCELLED, error='synthetic: cleared between scenes')

    def run_to(self, purpose):
        """Upload NOTE in a workspace of its own and run its stages through the stage of ``purpose`` (pass 1's
        interpret, or pass 2's appraise after an answered pass 1): (encounter, the reading stage's job, its newest
        run of ``purpose``)."""
        encounter, _ = self.fresh_encounter()
        self.run_next('extract')
        job = self.run_next(jobs.INTERPRET)
        if purpose == APPRAISAL:
            self.assertEqual(job.state, Job.SUCCEEDED, job.error)
            job = self.run_next(jobs.APPRAISE)
        return encounter, job, self.runs(encounter, purpose)[-1]

    def assert_named_no_provider(self, *texts):
        for text in texts:
            for name in PROVIDER_NAMES:
                self.assertNotIn(name, (text or '').lower())


class FableReplayTests(FableCase):
    """A2 1.8 and the F6 row's "replay stage tests for both passes on the Fable interpreter": the configured interpreter
    in replay (fable_adapter.get_interpreter_v2 -> interpretation/replay.ReplayInterpreterF), its recordings the raw
    answer streams at GEMINI_REPLAY_DIR/anthropic/<request sha256>.sse - pass 1's for the request the pipeline builds,
    pass 2's for the appraisal request the production builder makes of that answer. Nothing is sent: both runs are
    recorded not sent, with the replay's usage basis and the model and message id the streams name; the inventory is
    read at the @3 pair and the assessment made by the @3 engine."""

    def setUp(self):
        super().setUp()
        import tempfile

        self.replay_dir = self.enterContext(tempfile.TemporaryDirectory(prefix='f6-replay-'))
        self.enterContext(mock.patch.object(fable_adapter, 'get_interpreter_v2', REAL_GET_INTERPRETER))
        self.enterContext(override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR=self.replay_dir))

    def record(self, request, data):
        from pathlib import Path

        folder = Path(self.replay_dir) / 'anthropic'
        folder.mkdir(exist_ok=True)
        (folder / f'{request.canonical_sha256}.sse').write_bytes(data)

    def test_both_passes_replay_from_their_recorded_streams(self):
        encounter, revision = self.fresh_encounter()
        self.run_next('extract')
        revision.refresh_from_db()
        text, pages, kind = jobs._document_of(revision)
        first = fable_adapter.build_extraction_request(text, pages, kind)
        self.record(first, body(note_answer()))
        second = appraisal_for(text, pages, kind, note_answer())
        self.record(second.request, oracle_answer(second))
        self.assertIsInstance(fable_adapter.get_interpreter_v2(), __import__(
            'studio.interpretation.replay', fromlist=['ReplayInterpreterF']).ReplayInterpreterF)
        done = self.drain()
        self.assertEqual([job.kind for job in done], ['interpret', 'appraise', 'analyze', 'predict', 'assess'],
                         [(job.kind, job.state, job.error) for job in done])
        runs = self.runs(encounter, EXTRACTION) + self.runs(encounter, APPRAISAL)
        self.assertEqual([(run.state, run.sent, run.usage, run.usage_basis, run.returned_model, run.request_sha256)
                          for run in runs],
                         [(Run.SUCCEEDED, False, {}, 'historical_replay_not_new_usage', interpretation.MODEL_V3, sha)
                          for sha in (first.canonical_sha256, second.request.canonical_sha256)])
        self.assertEqual({(run.provider, run.adapter_version, run.scope.get('api_version')) for run in runs},
                         {(interpretation.PROVIDER_V3, interpretation.ADAPTER_VERSION_V3,
                           interpretation.API_VERSION_V3)})
        [inventory] = models.EventInventory.objects.filter(revision=revision)
        self.assertEqual((inventory.state, inventory.interpretation_version, inventory.inventory_version),
                         ('read', interpretation.INTERPRETATION_PAIR_V3, interpretation.INVENTORY_VERSION_V3))
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_assessment.engine_version, interpretation.ENGINE_VERSION_V3)
        self.assertTrue(review.fresh(encounter))

    def test_a_recording_that_did_not_reach_its_end_replays_as_an_unknown_outcome_and_nothing_is_read(self):
        encounter, revision = self.fresh_encounter()
        self.run_next('extract')
        revision.refresh_from_db()
        first = fable_adapter.build_extraction_request(*jobs._document_of(revision))
        self.record(first, sse(*[event for event in __import__('tests.v2.test_fable_adapter', fromlist=['answer_events'])
                                 .answer_events(json.dumps(note_answer()))][:-2]))  # no message_delta, no message_stop
        job = self.run_next(jobs.INTERPRET)
        [run] = self.runs(encounter, EXTRACTION)
        self.assertEqual((run.state, run.sent, run.usage, run.scope.get('effect')), (Run.UNKNOWN, False, {}, 'unknown'))
        self.assertEqual(job.state, Job.SUCCEEDED)  # left to the reconcile flow
        self.assertFalse(models.EventInventory.objects.filter(revision=revision).exists())
        self.assertFalse(Job.objects.filter(encounter=encounter, kind=jobs.APPRAISE).exists())

    def test_a_replayed_answer_cut_at_its_output_limit_reads_as_cut_off(self):
        """refute-f6-r1 F6R1-4 (A2 1.5 [R:truth-T7]): a replayed run is recorded not sent, and an answer cut at its
        output limit is still worded as what happened - progress' 'cut_off', never the size bound's 'too_long' - and a
        member's retry is refused with RETRY_CUT_OFF. The control: a document over the size bound reads 'too_long'."""
        encounter, revision = self.fresh_encounter()
        self.run_next('extract')
        revision.refresh_from_db()
        self.record(fable_adapter.build_extraction_request(*jobs._document_of(revision)), cut_off_stream())
        job = self.run_next(jobs.INTERPRET)
        [run] = self.runs(encounter, EXTRACTION)
        self.assertEqual((run.sent, run.scope.get('effect'), job.state, job.error),
                         (False, holds.TOO_LONG, Job.FAILED, jobs.INTERPRET_CUT_OFF_MESSAGE))
        self.assertEqual(progress.encounter_progress(models.Encounter.objects.get(pk=encounter.pk))['error'],
                         {'text': progress.INTERPRETATION_ERRORS['cut_off'][0], 'action': 'new_document'})
        with self.assertRaises(jobs.Refused) as refused:
            jobs.retry_reading(encounter, self.user)
        self.assertEqual(str(refused.exception), jobs.RETRY_CUT_OFF)
        with override_settings(INTERPRET_MAX_CHARS=40):
            long_one, _ = self.fresh_encounter()
            self.run_next('extract')
            self.assertEqual(self.run_next(jobs.INTERPRET).error, jobs.INTERPRET_TOO_LONG_MESSAGE)
            self.assertEqual(progress.encounter_progress(models.Encounter.objects.get(pk=long_one.pk))['error'],
                             {'text': progress.INTERPRETATION_ERRORS['too_long'][0], 'action': 'new_document'})


class FableTableTests(FableCase):
    """A2 1.5's table through the stages, both passes (the F6 row: "every row of 1.5 through the stage
    (_settle_interpretation, _settle_outcome), with the member sentence of the run that set each hold [R:truth-T6] and
    of a cut-off answer [R:truth-T7]"): every row of tests/v2/test_fable_adapter.table() (its constructed stream or
    error body) answers pass 1, and again pass 2 after an answered pass 1, and each ends its stage as 1.5 says:
    - answered: the stage succeeds (pass 1 queues pass 2; pass 2 writes the inventory and queues the analyze);
    - too long (max_tokens): FAILED with the cut-off sentence, which says the output limit was reached and never that
      the document is too long; the member reads progress' 'cut_off' (a new document), and a retry is refused with
      RETRY_CUT_OFF;
    - a request-bound hold (a decline; an error event after message_start): FAILED with DECLINED_MESSAGE - the document
      was sent - progress' 'declined' (no action), and a retry refused with RETRY_DECLINED;
    - any other hold: CANCELLED with HOLD_SET_MESSAGE, read as the paused phase with Resume - never "Nothing was sent";
      the hold stands with its reason, every other document pauses unsent (holds.PAUSED_MESSAGE), and an operator's
      release ends it;
    - failed: FAILED with the failed sentence and the recorded retry door (retry_reading).
    No sentence names a provider or a model (D22)."""

    def assert_row(self, purpose, label, outcome, status, data, kind, hold):
        failed = jobs.INTERPRET_FAILED_MESSAGE if purpose == EXTRACTION else jobs.APPRAISE_FAILED_MESSAGE
        cut = jobs.INTERPRET_CUT_OFF_MESSAGE if purpose == EXTRACTION else jobs.APPRAISE_CUT_OFF_MESSAGE
        if kind == 'answered':
            # the row's stream, carrying the document's own pass-1 answer (the table's synthetic object is no answer the
            # reader takes: an answered envelope whose reading is refused is FAILED, the next test's 'answered' half)
            data = answer_stream(json.dumps(note_answer()))
        self.scripted(script={purpose: [exchange_of(outcome, status, data)]})
        encounter, job, run = self.run_to(purpose)
        block = progress.encounter_progress(models.Encounter.objects.get(pk=encounter.pk))
        self.assert_named_no_provider(job.error, (block.get('error') or {}).get('text'), block['message'])
        if kind == 'answered':
            self.assertEqual((job.state, run.scope.get('effect')), (Job.SUCCEEDED, holds.ANSWERED))
            follower = jobs.APPRAISE if purpose == EXTRACTION else Job.ANALYZE
            self.assertTrue(Job.objects.filter(encounter=encounter, kind=follower, state=Job.QUEUED).exists())
        elif kind == 'too_long':
            self.assertEqual((job.state, job.error, run.scope.get('effect')), (Job.FAILED, cut, holds.TOO_LONG))
            self.assertNotIn('too long', job.error)
            self.assertEqual(block['error'], {'text': progress.INTERPRETATION_ERRORS['cut_off'][0],
                                              'action': 'new_document'})
            with self.assertRaises(jobs.Refused) as refused:
                jobs.retry_reading(encounter, self.user)
            self.assertEqual(str(refused.exception), jobs.RETRY_CUT_OFF)
        elif kind == 'hold' and label in REQUEST_BOUND_ROWS:
            self.assertEqual((job.state, job.error, run.scope.get('effect')), (Job.FAILED, jobs.DECLINED_MESSAGE,
                                                                               holds.HOLD))
            self.assertEqual((block['phase'], block['error']), ('failed', {'text': jobs.DECLINED_MESSAGE,
                                                                           'action': 'none'}))
            self.assertEqual(models.InterpreterHold.objects.get(run=run).reason, hold)
            self.release_holds()
            with self.assertRaises(jobs.Refused) as refused:
                jobs.retry_reading(encounter, self.user)
            self.assertEqual(str(refused.exception), jobs.RETRY_DECLINED)
        elif kind == 'hold':
            self.assertEqual((job.state, job.error, run.scope.get('effect')), (Job.CANCELLED, jobs.HOLD_SET_MESSAGE,
                                                                               holds.HOLD))
            self.assertNotIn('Nothing was sent', job.error)
            self.assertEqual((block['phase'], block['error']['text']), ('paused', jobs.HOLD_SET_MESSAGE))
            self.assertEqual(models.InterpreterHold.objects.get(run=run).reason, hold)
            # every other document pauses unsent while it stands: the standing hold's own sentence
            self.cancel_queued()
            other, _ = self.fresh_encounter()
            self.run_next('extract')
            paused = self.run_next(jobs.INTERPRET)
            self.assertEqual((paused.state, paused.error), (Job.CANCELLED, holds.PAUSED_MESSAGE))
            self.release_holds()
        else:
            self.assertEqual((job.state, run.scope.get('effect')), (Job.FAILED, holds.FAILED))
            self.assertTrue(job.error.startswith(failed), job.error)
            self.assertEqual(block['error']['action'], 'retry_reading')
        self.assertFalse(holds.is_held())
        self.cancel_queued()

    def test_every_row_of_1_5_through_pass_1s_stage(self):
        from tests.v2.test_fable_adapter import table

        for label, outcome, status, data, kind, hold, _ in table():
            with self.subTest(label):
                self.assert_row(EXTRACTION, label, outcome, status, data, kind, hold)

    def test_an_answered_envelope_whose_reading_is_refused_fails_with_the_retry_door(self):
        """1.5's first row: ANSWERED is read; a reader refusal makes it FAILED (holds.classify's ``refused``): the
        table's own stream (a JSON object that is no pass-1 answer) - pass 1's refused row, the retry door."""
        from tests.v2.test_fable_adapter import table

        label, outcome, status, data, kind, _, _ = table()[0]
        self.assertEqual(kind, 'answered')
        self.scripted(script={EXTRACTION: [exchange_of(outcome, status, data)]})
        encounter, job, run = self.run_to(EXTRACTION)
        self.assertEqual((job.state, run.scope.get('effect')), (Job.FAILED, holds.FAILED))
        self.assertEqual(models.EventInventory.objects.get(provider_run=run).state, 'refused')
        self.assertEqual(jobs.retry_reading(encounter, self.user).kind, jobs.INTERPRET)

    def test_every_row_of_1_5_through_pass_2s_stage(self):
        from tests.v2.test_fable_adapter import table

        for label, outcome, status, data, kind, hold, _ in table():
            if kind == 'answered':
                continue  # pass 2's answer is the oracle's over the claim set (the other tests)
            with self.subTest(label):
                self.assert_row(APPRAISAL, label, outcome, status, data, kind, hold)

    def test_a_refusal_pauses_both_passes(self):
        """A non-request-bound hold set by pass 1's answer (a 402) pauses every request of both passes: another
        document's pass 2, queued behind it, records a held not-sent run and sends nothing."""
        self.scripted()
        other, _ = self.fresh_encounter()
        self.run_next('extract')
        self.run_next(jobs.INTERPRET)  # the other document's pass 1, answered: its pass 2 is queued
        self.interpreter.script = {EXTRACTION: [exchange_of('failed', 402, HTTP_402)]}
        Job.objects.filter(encounter=other, state=Job.QUEUED).update(created_at=timezone.now() + timedelta(hours=1))
        encounter, _ = self.fresh_encounter()
        self.run_next('extract')
        setting = self.run_next(jobs.INTERPRET)
        self.assertEqual((setting.state, setting.error), (Job.CANCELLED, jobs.HOLD_SET_MESSAGE))
        sent = list(self.interpreter.sent)
        paused = self.run_next(jobs.APPRAISE)
        self.assertEqual((paused.state, paused.error), (Job.CANCELLED, holds.PAUSED_MESSAGE))
        [held] = self.runs(other, APPRAISAL)
        self.assertEqual((held.state, held.sent, held.scope.get('held')), (Run.NOT_SENT, False, holds.HELD_HOLD))
        self.assertEqual(self.interpreter.sent, sent)


class DeclinedRequestTests(FableCase):
    """A2 1.5's request-bound holds [R:connector-CONN-1], both passes (the F6 row: "a decline held, released, then a
    Resume and a Retry refused and an operator override sending once"): the declined run's hold pauses the installation
    (D275); the operator's release ends the pause but never the block on the declined request - a Resume sends nothing
    (the failed-before door returns the declined run for its identical request: a not-resent run), a member's Retry is
    refused with RETRY_DECLINED - and only an operator's recorded override (retry_reading(override=True)) sends it,
    once."""

    def declined_then_released(self, purpose):
        self.scripted(script={purpose: [answered(declined_stream())]})
        encounter, job, run = self.run_to(purpose)
        self.assertEqual((job.state, job.error), (Job.FAILED, jobs.DECLINED_MESSAGE))
        hold = models.InterpreterHold.objects.get(run=run)
        self.assertEqual((hold.reason, holds.request_bound(hold)), (holds.DECLINED, True))
        self.assertTrue(holds.is_held())
        [released] = self.release_holds()
        self.assertEqual(holds.release_report(released)['request_bound'], True)
        self.assertFalse(holds.is_held())
        return encounter, run

    def check(self, purpose):
        stage = jobs.INTERPRET if purpose == EXTRACTION else jobs.APPRAISE
        encounter, declined = self.declined_then_released(purpose)
        sent = list(self.interpreter.sent)
        # a Resume: the stage the member's Resume would run - the reading stage again under a resume key
        resumed = jobs.resume(encounter, self.user)
        if resumed is None:  # FAILED (declined) reads failed, not stopped: no Resume is offered at all ...
            base = Job.objects.filter(encounter=encounter, kind=stage).latest('created_at')
            resumed = jobs.enqueue(stage, encounter=encounter, revision=encounter.current_revision,
                                   key=f"{base.idempotency_key.split(':resume:', 1)[0]}:resume:synthetic",
                                   requested_by=self.user)  # ... and one queued under a Resume key sends nothing
        done = self.run_next(stage)
        self.assertEqual(done.state, Job.FAILED)
        self.assertEqual(self.interpreter.sent, sent)  # nothing sent: the declined request stays blocked
        not_resent = self.runs(encounter, purpose)[-1]
        self.assertEqual((not_resent.scope.get('refused'), not_resent.scope.get('failed'), not_resent.sent),
                         (jobs.FAILED_BEFORE, str(declined.pk), False))
        self.assertEqual(progress.encounter_progress(models.Encounter.objects.get(pk=encounter.pk))['error'],
                         {'text': jobs.DECLINED_MESSAGE, 'action': 'none'})
        # a member's Retry is refused
        with self.assertRaises(jobs.Refused) as refused:
            jobs.retry_reading(encounter, self.user)
        self.assertEqual(str(refused.exception), jobs.RETRY_DECLINED)
        self.assertEqual(jobs.retry_target(encounter.current_revision, override=False)[1], None)
        # the operator's recorded override sends it once: released for that one attempt
        self.assertEqual(jobs.retry_target(encounter.current_revision, override=True)[1], declined)
        job = jobs.retry_reading(encounter, self.user, override=True)
        self.assertTrue(job.idempotency_key.endswith(f':retry-release:{declined.pk}'), job.idempotency_key)
        self.drain()
        self.assertEqual(len(self.sent(purpose)), len([item for item in sent if item[0] == purpose]) + 1)
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=encounter.pk)))
        with self.assertRaises(jobs.Refused):  # read now: nothing left to retry, and nothing is sent again
            jobs.retry_reading(encounter, self.user, override=True)

    def test_pass_1(self):
        self.check(EXTRACTION)

    def test_pass_2(self):
        self.check(APPRAISAL)

    def test_an_error_event_after_message_start_is_request_bound_too(self):
        self.scripted(script={EXTRACTION: [answered(error_after_start('invalid_request_error'))]})
        encounter, job, run = self.run_to(EXTRACTION)
        self.assertEqual((job.state, job.error), (Job.FAILED, jobs.DECLINED_MESSAGE))
        self.assertEqual(models.InterpreterHold.objects.get(run=run).reason, holds.REFUSED)
        self.release_holds()
        with self.assertRaises(jobs.Refused) as refused:
            jobs.retry_reading(encounter, self.user)
        self.assertEqual(str(refused.exception), jobs.RETRY_DECLINED)

    def test_the_control_an_account_hold_releases_and_the_next_resume_sends(self):
        """Every other hold is about the account, the version or the model: a 401's release lets the stopped document's
        Resume send, once (A2 1.5; CONN-5's 'resumed after a release')."""
        self.scripted(script={EXTRACTION: [answered(fable_error_body('authentication_error'), status=401)]})
        encounter, job, run = self.run_to(EXTRACTION)
        self.assertEqual((job.state, job.error), (Job.CANCELLED, jobs.HOLD_SET_MESSAGE))
        self.assertFalse(holds.request_bound(models.InterpreterHold.objects.get(run=run)))
        self.release_holds()
        self.assertIsNotNone(jobs.resume(encounter, self.user))
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, EXTRACTION, APPRAISAL])
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=encounter.pk)))


class FableRetryTests(FableCase):
    """A2 section 9 [R:connector-CONN-5]: the retry door finds the Fable run (retry_target reads the reading path's
    provider and adapter version, never interpretation.PROVIDER's 'gemini'): a FAILED Fable reading is retried once - pass
    1, and pass 2 alone - and an identical failed request is never re-sent by a Resume (the failed-before door)."""

    def test_a_failed_pass_1_is_retried_once(self):
        self.scripted(script={EXTRACTION: [answered(HTTP_500, status=500)]})
        encounter, job, run = self.run_to(EXTRACTION)
        self.assertEqual((run.provider, run.adapter_version, job.state), (interpretation.PROVIDER_V3,
                                                                          interpretation.ADAPTER_VERSION_V3, Job.FAILED))
        newest, released = jobs.retry_target(encounter.current_revision)
        self.assertEqual((newest, released), (run, run))
        jobs.retry_reading(encounter, self.user)
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, EXTRACTION, APPRAISAL])
        with self.assertRaises(jobs.Refused) as refused:
            jobs.retry_reading(encounter, self.user)
        self.assertEqual(str(refused.exception), jobs.RETRY_NOTHING)  # fresh: nothing owed, nothing sent again

    def test_a_failed_pass_2_is_retried_alone(self):
        self.scripted(script={APPRAISAL: [answered(fable_error_body('overloaded_error'), status=529)]})
        encounter, job, run = self.run_to(APPRAISAL)
        self.assertEqual(jobs.retry_target(encounter.current_revision), (run, run))
        self.assertEqual(jobs.retry_reading(encounter, self.user).kind, jobs.APPRAISE)
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, APPRAISAL, APPRAISAL])

    def test_an_error_first_stream_is_failed_retry_later_never_a_model_hold(self):
        """A2 1.5 precedence (2) [R:connector-CONN-4]: an overload as the stream opened is FAILED (retry later), never
        HOLD model: no hold, and the retry door is offered."""
        self.scripted(script={EXTRACTION: [answered(error_first('overloaded_error'))]})
        encounter, job, run = self.run_to(EXTRACTION)
        self.assertEqual((job.state, run.scope.get('effect'), holds.is_held()), (Job.FAILED, holds.FAILED, False))
        self.assertEqual(jobs.retry_reading(encounter, self.user).kind, jobs.INTERPRET)

    def test_a_resume_never_re_sends_a_failed_request(self):
        self.scripted(script={EXTRACTION: [answered(HTTP_500, status=500)]})
        encounter, job, run = self.run_to(EXTRACTION)
        base = Job.objects.get(encounter=encounter, kind=jobs.INTERPRET)
        jobs.enqueue(jobs.INTERPRET, encounter=encounter, revision=encounter.current_revision,
                     key=f'{base.idempotency_key}:resume:synthetic', requested_by=self.user)
        self.run_next(jobs.INTERPRET)
        self.assertEqual(len(self.interpreter.sent), 1)
        self.assertEqual(self.runs(encounter, EXTRACTION)[-1].scope.get('refused'), jobs.FAILED_BEFORE)


def cut_off_stream() -> bytes:
    """A complete 200 stream cut at its output limit (stop_reason max_tokens): A2 1.5's TOO_LONG row (C5)."""
    return stream_of('{"events": [', stop_reason='max_tokens')


OVERLOADED = fable_error_body('overloaded_error')  # A2 1.5: HTTP 529 overloaded_error, FAILED, retry later


class RequestBlockTests(FableCase):
    """refute-f6-r1 F6R1-1, widened to its class (D276): whenever an attempt of a request was declined (a request-bound
    hold, A2 1.5 [R:connector-CONN-1]) or cut off at its output limit (C5), the block is the REQUEST's
    (jobs._member_block), so a later attempt of it - the one an operator's recorded override sent, answered by a
    transient failure (HTTP 529) or left unknown and reconciled by a member - never lifts it for a member: the member's
    Retry is refused (RETRY_DECLINED, RETRY_CUT_OFF), a Resume and a reconcile send nothing, progress offers no retry;
    and each further operator override sends it once (jobs._override_unspent). Both passes. The control: an ordinary
    failure is released for one attempt by each member retry, as before."""

    def stage_of(self, purpose):
        return jobs.INTERPRET if purpose == EXTRACTION else jobs.APPRAISE

    def overridden(self, purpose, first, second):
        """``first`` answers the request of ``purpose`` (a 200 stream); a standing hold is released by the operator;
        the operator's recorded override sends the identical request once more and ``second`` answers that attempt.
        (encounter, the first attempt, the override's attempt, the sends of ``purpose`` so far)."""
        self.scripted(script={purpose: [answered(first), second]})
        encounter, job, blocked = self.run_to(purpose)
        self.assertEqual(job.state, Job.FAILED)
        if holds.is_held():
            self.release_holds()
        override = jobs.retry_reading(encounter, self.user, override=True)
        self.assertTrue(override.idempotency_key.endswith(f':retry-release:{blocked.pk}'), override.idempotency_key)
        self.run_next(self.stage_of(purpose))
        attempt = self.runs(encounter, purpose)[-1]
        self.assertEqual((attempt.request_sha256, attempt.sent), (blocked.request_sha256, True))
        self.assertEqual(len(self.sent(purpose)), 2)
        return models.Encounter.objects.get(pk=encounter.pk), blocked, attempt, 2

    def assert_member_refused(self, encounter, sentence, situation, purpose, sends):
        text, action = progress.INTERPRETATION_ERRORS[situation]
        self.assertEqual(progress.encounter_progress(models.Encounter.objects.get(pk=encounter.pk))['error'],
                         {'text': text, 'action': action})
        self.assertNotEqual(action, 'retry_reading')
        with self.assertRaises(jobs.Refused) as refused:
            jobs.retry_reading(encounter, self.user)
        self.assertEqual(str(refused.exception), sentence)
        self.assertEqual(len(self.sent(purpose)), sends)

    def resume_sends_nothing(self, encounter, purpose, sends):
        """A member's Resume of the reading stage (queued under a Resume key: a failed stage offers none): nothing sent."""
        stage = self.stage_of(purpose)
        base = Job.objects.filter(encounter=encounter, kind=stage).latest('created_at')
        jobs.enqueue(stage, encounter=encounter, revision=encounter.current_revision,
                     key=f"{base.idempotency_key.split(':resume:', 1)[0]}:resume:synthetic-{len(self.sent())}",
                     requested_by=self.user)
        self.assertEqual(self.run_next(stage).state, Job.FAILED)
        self.assertEqual(len(self.sent(purpose)), sends)
        self.assertEqual(self.runs(encounter, purpose)[-1].scope.get('refused'), jobs.FAILED_BEFORE)

    def another_override_sends_once(self, encounter, purpose, sends):
        jobs.retry_reading(encounter, self.user, override=True)
        self.drain()
        self.assertEqual(len(self.sent(purpose)), sends + 1)
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=encounter.pk)))

    def check_transient(self, purpose, first, sentence, situation):
        encounter, blocked, attempt, sends = self.overridden(purpose, first, answered(OVERLOADED, status=529))
        self.assertEqual((attempt.state, attempt.http_status, attempt.scope.get('effect')), (Run.FAILED, 529,
                                                                                             holds.FAILED))
        self.assertEqual(jobs._member_block(attempt), blocked)
        self.assert_member_refused(encounter, sentence, situation, purpose, sends)
        self.resume_sends_nothing(encounter, purpose, sends)
        self.assert_member_refused(encounter, sentence, situation, purpose, sends)  # the not-resent run changes nothing
        self.another_override_sends_once(encounter, purpose, sends)

    def test_a_declined_request_after_the_overrides_attempt_failed_pass_1(self):
        self.check_transient(EXTRACTION, declined_stream(), jobs.RETRY_DECLINED, 'declined')

    def test_a_declined_request_after_the_overrides_attempt_failed_pass_2(self):
        self.check_transient(APPRAISAL, declined_stream(), jobs.RETRY_DECLINED, 'declined')

    def test_an_error_event_hold_after_the_overrides_attempt_failed(self):
        self.check_transient(EXTRACTION, error_after_start('invalid_request_error'), jobs.RETRY_DECLINED, 'declined')

    def test_a_cut_off_request_after_the_overrides_attempt_failed_pass_1(self):
        self.check_transient(EXTRACTION, cut_off_stream(), jobs.RETRY_CUT_OFF, 'cut_off')

    def test_a_cut_off_request_after_the_overrides_attempt_failed_pass_2(self):
        self.check_transient(APPRAISAL, cut_off_stream(), jobs.RETRY_CUT_OFF, 'cut_off')

    def check_unknown(self, purpose, first, sentence, situation):
        encounter, blocked, attempt, sends = self.overridden(purpose, first, UNKNOWN)
        self.assertEqual(attempt.state, Run.UNKNOWN)
        self.assertTrue(jobs.reconcile(encounter, attempt, self.user, 'Synthetic: the outcome was checked.'))
        done = self.run_next(self.stage_of(purpose))  # the reconciliation's stage: the request stays blocked
        self.assertEqual(done.state, Job.FAILED)
        self.assertEqual(len(self.sent(purpose)), sends)
        kept = self.runs(encounter, purpose)[-1]
        self.assertEqual((kept.scope.get('refused'), kept.scope.get('failed'), kept.sent),
                         (jobs.FAILED_BEFORE, str(blocked.pk), False))
        self.assert_member_refused(encounter, sentence, situation, purpose, sends)
        self.resume_sends_nothing(encounter, purpose, sends)
        self.another_override_sends_once(encounter, purpose, sends)  # a fresh release: the last one was spent

    def test_a_declined_request_after_the_overrides_attempt_was_unknown_and_reconciled_pass_1(self):
        self.check_unknown(EXTRACTION, declined_stream(), jobs.RETRY_DECLINED, 'declined')

    def test_a_declined_request_after_the_overrides_attempt_was_unknown_and_reconciled_pass_2(self):
        self.check_unknown(APPRAISAL, declined_stream(), jobs.RETRY_DECLINED, 'declined')

    def test_a_cut_off_request_after_the_overrides_attempt_was_unknown_and_reconciled(self):
        self.check_unknown(EXTRACTION, cut_off_stream(), jobs.RETRY_CUT_OFF, 'cut_off')

    def test_an_override_stopped_before_it_sent_still_sends_once(self):
        """The override's one attempt not yet made (its stage stopped before it ran): the operator's override asked again
        sends once - the standing release is not spent - and a member's retry after it is still refused."""
        self.scripted(script={EXTRACTION: [answered(declined_stream()), answered(OVERLOADED, status=529)]})
        encounter, job, declined = self.run_to(EXTRACTION)
        self.release_holds()
        first = jobs.retry_reading(encounter, self.user, override=True)
        Job.objects.filter(pk=first.pk).update(state=Job.CANCELLED, error='Stopped by a workspace member.')
        self.assertTrue(jobs._override_unspent(declined))
        again = jobs.retry_reading(encounter, self.user, override=True)
        self.assertEqual(again.idempotency_key, jobs._interpret_key(encounter.current_revision, f'retry:{declined.pk}'))
        self.run_next(jobs.INTERPRET)
        self.assertEqual(len(self.sent(EXTRACTION)), 2)
        self.assertFalse(jobs._override_unspent(declined))
        self.assert_member_refused(models.Encounter.objects.get(pk=encounter.pk), jobs.RETRY_DECLINED, 'declined',
                                   EXTRACTION, 2)

    def test_the_control_an_ordinary_failure_is_released_once_per_member_retry(self):
        self.scripted(script={EXTRACTION: [answered(HTTP_500, status=500), answered(OVERLOADED, status=529)]})
        encounter, job, failed = self.run_to(EXTRACTION)
        self.assertIsNone(jobs._member_block(failed))
        jobs.retry_reading(encounter, self.user)
        self.run_next(jobs.INTERPRET)
        self.assertEqual(len(self.sent(EXTRACTION)), 2)
        self.assertEqual(progress.encounter_progress(models.Encounter.objects.get(pk=encounter.pk))['error']['action'],
                         'retry_reading')
        jobs.retry_reading(encounter, self.user)
        self.drain()
        self.assertEqual([item[0] for item in self.interpreter.sent], [EXTRACTION, EXTRACTION, EXTRACTION, APPRAISAL])
        self.assertTrue(review.fresh(models.Encounter.objects.get(pk=encounter.pk)))


class SettledPathHoldTests(FableCase):
    """refute-f6-r1 F6R1-2 (A2 1.5 [R:truth-T6]: "jobs._settle_outcome and mark_stale's settled path word that run from
    the run itself ... PAUSED_MESSAGE stays for every run a standing hold kept unsent"), widened to its class: every
    stage that settles the run its key names (the stale sweep's ':settled:<run>', a reconciliation's
    ':after-reconcile:<run>') reads that run before the hold door, so a run whose own answer set the hold - recorded
    meanwhile by another stage's send gate (_record_unsettled_holds, D53/D53b) - ends as its run says: a request-bound
    hold FAILED with DECLINED_MESSAGE, any other CANCELLED with HOLD_SET_MESSAGE, never "Nothing was sent"; the control:
    a settled path whose run is already settled meets the hold and pauses (nothing was sent by it)."""

    def dead_stage_after(self, data):
        """Pass 1 answered by ``data`` (a 200 stream); the worker dies after the run was recorded, before the stage
        settled it: (encounter, the RUNNING job, the SUCCEEDED run, no effect recorded)."""
        self.scripted(script={EXTRACTION: [answered(data)]})
        encounter, _ = self.fresh_encounter()
        self.run_next('extract')
        with mock.patch.object(jobs, '_settle_interpretation', side_effect=KeyboardInterrupt):
            job = jobs.claim_next()
            self.assertEqual(job.kind, jobs.INTERPRET)
            with self.assertRaises(KeyboardInterrupt), jobs._stage_scope(job):
                jobs.STAGES[jobs.INTERPRET](job)
        job.refresh_from_db()
        [run] = self.runs(encounter, EXTRACTION)
        self.assertEqual((job.state, run.state, run.sent, (run.scope or {}).get('effect')),
                         (Job.RUNNING, Run.SUCCEEDED, True, None))
        return encounter, job, run

    def settled_with_the_hold_standing(self, data, reason):
        encounter, job, run = self.dead_stage_after(data)
        jobs._record_unsettled_holds()  # another stage's send gate (D53's last ask)
        self.assertEqual(models.InterpreterHold.objects.get(run=run).reason, reason)
        self.assertTrue(holds.is_held())
        jobs.mark_stale(startup=True)
        settled = self.run_next(jobs.INTERPRET)
        self.assertIn(':settled:', settled.idempotency_key)
        self.assertEqual(len(self.sent(EXTRACTION)), 1)
        return encounter, settled

    def test_a_declined_run_is_worded_declined(self):
        encounter, settled = self.settled_with_the_hold_standing(declined_stream(), holds.DECLINED)
        self.assertEqual((settled.state, settled.error), (Job.FAILED, jobs.DECLINED_MESSAGE))
        self.assertEqual(progress.encounter_progress(models.Encounter.objects.get(pk=encounter.pk))['error'],
                         {'text': jobs.DECLINED_MESSAGE, 'action': 'none'})

    def test_a_model_hold_run_is_worded_by_the_hold_it_set(self):
        encounter, settled = self.settled_with_the_hold_standing(
            answer_stream(json.dumps(note_answer()), model='claude-fable-5-1'), holds.MODEL)
        self.assertEqual((settled.state, settled.error), (Job.CANCELLED, jobs.HOLD_SET_MESSAGE))
        block = progress.encounter_progress(models.Encounter.objects.get(pk=encounter.pk))
        self.assertEqual((block['phase'], block['error']['text']), ('paused', jobs.HOLD_SET_MESSAGE))
        self.assertNotIn('Nothing was sent', block['error']['text'])

    def test_the_worker_restarts_with_another_document_queued(self):
        """By the pipeline's order alone: document B's interpret stage queued before the worker died in A's stage; the
        startup sweep queues A's settled path after it; B's send gate records A's hold (B pauses: true for B, nothing
        of B was sent); A's settled path then words A's run as declined."""
        self.scripted(script={EXTRACTION: [answered(declined_stream())]})
        first, _ = self.fresh_encounter()
        self.run_next('extract')
        other, _ = self.fresh_encounter()
        with mock.patch.object(jobs, '_settle_interpretation', side_effect=KeyboardInterrupt):
            job = jobs.claim_next()
            self.assertEqual((job.kind, job.encounter_id), (jobs.INTERPRET, first.pk))
            with self.assertRaises(KeyboardInterrupt), jobs._stage_scope(job):
                jobs.STAGES[jobs.INTERPRET](job)
        self.run_next('extract')
        jobs.mark_stale(startup=True)
        done = self.drain()
        mine = [(item.state, item.error) for item in done if item.encounter_id == first.pk and item.kind == jobs.INTERPRET]
        theirs = [(item.state, item.error) for item in done if item.encounter_id == other.pk]
        self.assertEqual(mine, [(Job.FAILED, jobs.DECLINED_MESSAGE)])
        self.assertEqual(theirs, [(Job.CANCELLED, holds.PAUSED_MESSAGE)])
        self.assertEqual(len(self.sent(EXTRACTION)), 1)

    def test_a_reconciled_unknown_run_whose_exchange_holds_a_decline_is_worded_declined(self):
        """The after-reconcile half: a run left UNKNOWN whose one exchange recorded a declined 200 stream (decision (k));
        D53b records its hold; the member's reconciliation settles it from that exchange (P-6) and words it declined."""
        encounter, revision = self.fresh_encounter()
        self.run_next('extract')
        self.cancel_queued()
        revision.refresh_from_db()
        request = fable_adapter.build_extraction_request(*jobs._document_of(revision))
        data = declined_stream()
        run = Run.objects.create(encounter=encounter, revision=revision, provider=interpretation.PROVIDER_V3,
                                 adapter_version=interpretation.ADAPTER_VERSION_V3,
                                 request_sha256=request.canonical_sha256, request_body={}, contexts=[],
                                 state=Run.UNKNOWN, sent=True, endpoint='https://interpreter.invalid/v1/messages',
                                 purpose=EXTRACTION, scope={'mode': 'replay'}, started_at=timezone.now())
        models.ProviderExchange.objects.create(
            run=run, turn=1, request_body={}, request_sha256=request.canonical_sha256, state=Run.SUCCEEDED,
            http_status=200, response_bytes=data, response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=5.0,
            usage={}, provider_request_id='', response_id='', error='', started_at=timezone.now(),
            finished_at=timezone.now())
        jobs._record_unsettled_holds()
        self.assertTrue(holds.is_held())
        self.assertTrue(jobs.reconcile(encounter, run, self.user, 'Synthetic: the outcome was checked.'))
        done = self.run_next(jobs.INTERPRET)
        self.assertIn(':after-reconcile:', done.idempotency_key)
        self.assertEqual((done.state, done.error), (Job.FAILED, jobs.DECLINED_MESSAGE))
        self.assertEqual(self.sent(), [])

    def test_the_control_a_settled_path_whose_run_was_settled_meets_the_hold(self):
        """PAUSED_MESSAGE stays for every run a standing hold kept unsent: the settled path of a run already settled
        (its effect recorded) reads nothing of its own and pauses at the hold - a held not-sent run, nothing sent."""
        encounter, job, run = self.dead_stage_after(body(note_answer()))
        jobs._mark_effect(run, holds.FAILED)  # settled before (a refused reading): nothing for the settled path to read
        models.InterpreterHold.objects.create(reason=holds.QUOTA, http_status=429, run=run)
        jobs.mark_stale(startup=True)
        settled = self.run_next(jobs.INTERPRET)
        self.assertEqual((settled.state, settled.error), (Job.CANCELLED, holds.PAUSED_MESSAGE))
        self.assertTrue(self.runs(encounter, EXTRACTION)[-1].scope.get('held'))
        self.assertEqual(len(self.sent(EXTRACTION)), 1)


class SettleByVersionTests(FableCase):
    """A2 1.10 and 1.5 (the F6 row: "P-6 and _record_unsettled_holds by adapter version"): a run is described and
    classified by the adapter that recorded it - fable_adapter for ADAPTER_VERSION_V3, the dormant Gemini adapter for a
    stored Gemini run - and only a run of the version the reading stages send now sets a hold (DECISIONS D289, G2-02: no
    stored Gemini run is a source of a new hold)."""

    def unsettled(self, encounter, revision, *, provider, version, body_bytes, status=200, state=Run.SENDING):
        sha = 'c' * 64
        run = Run.objects.create(encounter=encounter, revision=revision, provider=provider, adapter_version=version,
                                 request_sha256=sha, request_body={}, contexts=[], state=state, sent=True,
                                 endpoint='https://interpreter.invalid/v1/messages', purpose=interpretation.PURPOSE,
                                 scope={'mode': 'replay'}, started_at=timezone.now())
        models.ProviderExchange.objects.create(
            run=run, turn=1, request_body={}, request_sha256=sha, state=Run.SUCCEEDED if status == 200 else Run.FAILED,
            http_status=status, response_bytes=body_bytes, response_sha256=hashlib.sha256(body_bytes).hexdigest(),
            latency_ms=5.0, usage={}, provider_request_id='', response_id='', error='', started_at=timezone.now(),
            finished_at=timezone.now())
        return run

    def test_p6_settles_a_fable_run_by_fable_adapter_describe(self):
        encounter, revision = self.fresh_encounter()
        self.cancel_queued()
        run = self.unsettled(encounter, revision, provider=interpretation.PROVIDER_V3,
                             version=interpretation.ADAPTER_VERSION_V3, body_bytes=body(note_answer()))
        self.assertTrue(jobs._settle_from_exchange(run))
        run.refresh_from_db()
        self.assertEqual((run.state, run.returned_model, run.response_id), (Run.SUCCEEDED, interpretation.MODEL_V3,
                                                                             'msg_synthetic_0001'))

    def test_p6_settles_a_stored_gemini_run_by_the_dormant_adapters_describe(self):
        from tests.test_interpretation_adapter import encoded, envelope

        encounter, revision = self.fresh_encounter()
        self.cancel_queued()
        data = encoded(envelope(json.dumps(note_answer())))
        run = self.unsettled(encounter, revision, provider=interpretation.PROVIDER,
                             version=interpretation.ADAPTER_VERSION_V2, body_bytes=data)
        self.assertTrue(jobs._settle_from_exchange(run))
        run.refresh_from_db()
        self.assertEqual((run.state, run.returned_model), (Run.SUCCEEDED, adapter.describe(data)[1]))
        # a run of a version no adapter here records is left as it is
        other = self.unsettled(encounter, revision, provider=interpretation.PROVIDER_V3,
                               version='synthetic-messages@0', body_bytes=body(note_answer()))
        self.assertFalse(jobs._settle_from_exchange(other))

    def test_unsettled_holds_are_recorded_for_fable_runs_only(self):
        from tests.test_interpretation_adapter import encoded

        encounter, revision = self.fresh_encounter()
        self.cancel_queued()
        quota = encoded({'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED', 'message': 'synthetic cap'}})
        gemini = self.unsettled(encounter, revision, provider=interpretation.PROVIDER,
                                version=interpretation.ADAPTER_VERSION_V2, body_bytes=quota, status=429,
                                state=Run.UNKNOWN)
        jobs._record_unsettled_holds()
        self.assertFalse(models.InterpreterHold.objects.filter(run=gemini).exists())  # G2-02
        fable = self.unsettled(encounter, revision, provider=interpretation.PROVIDER_V3,
                               version=interpretation.ADAPTER_VERSION_V3, body_bytes=declined_stream(),
                               state=Run.UNKNOWN)
        jobs._record_unsettled_holds()
        self.assertEqual(models.InterpreterHold.objects.get(run=fable).reason, holds.DECLINED)  # by fable's classify
        self.assertEqual(models.InterpreterHold.objects.count(), 1)


class StaleThresholdTests(FableCase):
    """A2 1.12 [R:connector-CONN-7] (the F6 row: "the per-kind stale threshold in mark_stale and _check_loop_time, and the
    startup sweep settling a 70 s-old RUNNING stage"; 11.1: "a 1,000 s-old interpret stage not swept by the periodic
    sweep, a 700 s-old predict swept, and any RUNNING stage settled by the worker's startup sweep")."""

    def running(self, kind, seconds):
        encounter, revision = self.fresh_encounter()
        self.cancel_queued()
        job = Job.objects.create(encounter=encounter, revision=revision, kind=kind, state=Job.RUNNING,
                                 idempotency_key=f'{kind}:{revision.pk}:synthetic-stale', attempts=1,
                                 started_at=timezone.now() - timedelta(seconds=seconds),
                                 deadline_at=timezone.now() + jobs.QUEUE_DEADLINE)
        return job

    def test_the_thresholds_are_settings_per_kind(self):
        from django.conf import settings

        self.assertEqual((jobs.stale_threshold(jobs.INTERPRET), jobs.stale_threshold(jobs.APPRAISE)), (1440, 1440))
        self.assertEqual(jobs.stale_threshold(Job.PREDICT), settings.STALE_RUNNING_SECONDS)
        with override_settings(STALE_RUNNING_SECONDS_BY_KIND={'interpret': 2000}):
            self.assertEqual((jobs.stale_threshold(jobs.INTERPRET), jobs.stale_threshold(jobs.APPRAISE)),
                             (2000, settings.STALE_RUNNING_SECONDS))

    def test_the_periodic_sweep_keeps_a_1000_s_old_reading_stage_and_sweeps_a_700_s_old_predict(self):
        interpret = self.running(jobs.INTERPRET, 1000)
        appraise = self.running(jobs.APPRAISE, 1000)
        predict = self.running(Job.PREDICT, 700)
        jobs.mark_stale()
        for job, state in ((interpret, Job.RUNNING), (appraise, Job.RUNNING)):
            job.refresh_from_db()
            self.assertEqual(job.state, state, job.kind)
        predict.refresh_from_db()
        self.assertNotEqual(predict.state, Job.RUNNING)
        Job.objects.filter(pk=interpret.pk).update(started_at=timezone.now() - timedelta(seconds=1441))
        jobs.mark_stale()  # past its kind's threshold: swept
        interpret.refresh_from_db()
        self.assertNotEqual(interpret.state, Job.RUNNING)
        appraise.refresh_from_db()
        self.assertEqual(appraise.state, Job.RUNNING)

    def test_the_startup_sweep_settles_a_70_s_old_running_stage(self):
        job = self.running(jobs.INTERPRET, 70)
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, Job.RUNNING)  # the periodic sweep keeps it ...
        jobs.mark_stale(startup=True)
        job.refresh_from_db()
        self.assertEqual(job.state, Job.CANCELLED)  # ... the worker's startup sweep settles it, resumable
        self.assertTrue(review.can_resume(job.encounter))

    def test_the_worker_starts_with_the_startup_sweep(self):
        job = self.running(jobs.APPRAISE, 70)
        with mock.patch.object(jobs, 'remove_stale_ingest_dirs'):
            jobs.work(lambda: True)
        job.refresh_from_db()
        self.assertEqual(job.state, Job.CANCELLED)

    def test_the_loop_budget_of_a_reading_stage_is_its_deadline_under_its_kinds_threshold(self):
        # 1,320 s send + 15 s recording within the stage's 1,380 s (min with the 1,440 s threshold)
        for kind, purpose in ((jobs.INTERPRET, INTERPRETATION_PURPOSE), (jobs.APPRAISE, APPRAISAL)):
            with self.subTest(kind=kind):
                fits = SimpleNamespace(kind=kind, started_at=timezone.now() - timedelta(seconds=30))
                jobs._check_loop_time(fits, purpose)  # 30 + 1320 + 15 = 1365 <= 1380
                late = SimpleNamespace(kind=kind, started_at=timezone.now() - timedelta(seconds=60))
                with self.assertRaises(jobs.Requeue):
                    jobs._check_loop_time(late, purpose)  # 60 + 1320 + 15 = 1395 > 1380
        # a participant's stage keeps the shared 600 s threshold
        from django.conf import settings

        participant = SimpleNamespace(kind=Job.ASTRA, started_at=timezone.now() - timedelta(seconds=40))
        budget = min(settings.JOB_DEADLINE_SECONDS.get(Job.ASTRA, settings.STALE_RUNNING_SECONDS),
                     settings.STALE_RUNNING_SECONDS)
        if 40 + settings.PARTICIPANT_LOOP_DEADLINE_SECONDS + jobs.LOOP_RECORDING_SECONDS > budget:
            with self.assertRaises(jobs.Requeue):
                jobs._check_loop_time(participant)
        else:
            jobs._check_loop_time(participant)


INTERPRETATION_PURPOSE = interpretation.PURPOSE


class QueueDeadlineTests(FableCase):
    """A2 1.12: QUEUE_DEADLINE is 60 minutes - a job queued behind two long readings still starts."""

    def test_sixty_minutes(self):
        self.assertEqual(jobs.QUEUE_DEADLINE, timedelta(minutes=60))
        encounter, revision = self.fresh_encounter()
        [queued] = Job.objects.filter(encounter=encounter, state=Job.QUEUED)
        self.assertAlmostEqual((queued.deadline_at - queued.created_at).total_seconds(), 3600, delta=5)
        with mock.patch.object(timezone, 'now', return_value=queued.created_at + timedelta(minutes=59)):
            self.assertEqual(jobs.claim_next().state, Job.RUNNING)
        Job.objects.filter(pk=queued.pk).update(state=Job.QUEUED, started_at=None)
        with mock.patch.object(timezone, 'now', return_value=queued.created_at + timedelta(minutes=61)):
            expired = jobs.claim_next()
        self.assertEqual((expired.state, expired.error), (Job.CANCELLED, 'The stage expired before it could start; '
                                                                         'resume to run it.'))


class DoorOrderTests(FableCase):
    """A2 1.9's doors, in their order, on the appraise stage (the interpret stage's are FINAL 6.3's, unchanged): the
    unknown-outcome block (door 3) before the failed-before door (door 4); the failed-before door - a request-bound
    hold's run among its runs - before the interpreter's mode and the hold (door 6); door 0's claim bound before any
    stored answer is reused (door 2)."""

    def test_the_unknown_outcome_block_comes_before_the_failed_before_door(self):
        self.scripted(script={APPRAISAL: [answered(HTTP_500, status=500)]})
        encounter, job, failed = self.run_to(APPRAISAL)
        self.assertEqual(job.state, Job.FAILED)
        Run.objects.create(encounter=encounter, revision=encounter.current_revision, provider='corti',
                           adapter_version='synthetic', request_sha256='d' * 64, request_body={}, contexts=[],
                           state=Run.UNKNOWN, sent=True, purpose=models.ProviderRun.PRIMARY)
        base = job.idempotency_key.split(':resume:', 1)[0]
        jobs.enqueue(jobs.APPRAISE, encounter=encounter, revision=encounter.current_revision,
                     key=f'{base}:resume:synthetic', requested_by=self.user)
        done = self.run_next(jobs.APPRAISE)
        self.assertEqual(done.result, {'blocked': jobs.INTERPRET_BLOCKED})
        self.assertEqual(self.runs(encounter, APPRAISAL), [failed])  # no not-resent run: door 3 answered first

    def test_the_failed_before_door_comes_before_the_hold(self):
        self.scripted(script={APPRAISAL: [answered(declined_stream())]})
        encounter, job, declined = self.run_to(APPRAISAL)
        self.assertTrue(holds.is_held())  # the decline's hold stands (not released)
        base = job.idempotency_key.split(':resume:', 1)[0]
        jobs.enqueue(jobs.APPRAISE, encounter=encounter, revision=encounter.current_revision,
                     key=f'{base}:resume:synthetic', requested_by=self.user)
        self.run_next(jobs.APPRAISE)
        newest = self.runs(encounter, APPRAISAL)[-1]
        self.assertEqual((newest.scope.get('refused'), newest.scope.get('failed'), newest.scope.get('held')),
                         (jobs.FAILED_BEFORE, str(declined.pk), None))  # door 4, never door 6's held run

    def test_the_claim_bound_comes_before_a_stored_answer(self):
        from studio.interpretation.contract import claims

        self.scripted()
        first, _ = self.upload()
        self.drain()  # a stored answer of both passes in this workspace
        self.enterContext(mock.patch.object(claims, 'CLAIM_BOUND_V3', 1))
        self.enterContext(mock.patch.multiple(interpretation, **fable_pins()))
        second, _ = self.upload()
        self.drain()
        [run] = self.runs(second, APPRAISAL)
        self.assertEqual((run.state, run.scope.get('refused'), run.reused_from_id), (Run.NOT_SENT, jobs.CLAIMS, None))


class GuardTests(TestCase):
    """A2 section 9 and 8.1 (the F6 row: "the guard test of section 9's path list" [R:connector-CONN-5]; 8.1's guard
    [R:replay-R4]): no line of jobs.py names interpretation.PROVIDER, MODEL or ADAPTER_VERSION_V2 but the three
    _reading_* functions (which give v1's names under the test-only v1 chain and the _V3 names otherwise); no
    current-path writer of jobs.py names a design v2 @2 (or @1) label; every reader of a stored row accepts both
    families."""

    JOBS = __import__('pathlib').Path(jobs.__file__)

    def names(self, wanted):
        """[(enclosing function, attribute, line)] of every interpretation.<wanted> attribute read in jobs.py."""
        import ast

        tree = ast.parse(self.JOBS.read_text(encoding='utf-8'))
        found = []

        def visit(node, function):
            for child in ast.iter_child_nodes(node):
                inner = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else function
                if (isinstance(child, ast.Attribute) and isinstance(child.value, ast.Name)
                        and child.value.id == 'interpretation' and child.attr in wanted):
                    found.append((function, child.attr, child.lineno))
                visit(child, inner)
        visit(tree, None)
        return found

    def test_no_other_line_names_the_v1_and_v2_interpreter(self):
        import ast

        found = self.names({'PROVIDER', 'MODEL', 'ADAPTER_VERSION_V2'})
        self.assertEqual({(function, name) for function, name, _ in found},
                         {('_reading_provider', 'PROVIDER'), ('_reading_model', 'MODEL')})
        # nor by another route: no name imported from the package, and no alias of the package itself
        tree = ast.parse(self.JOBS.read_text(encoding='utf-8'))
        imported = [(node.module, alias.name, alias.asname) for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) for alias in node.names]
        self.assertFalse([item for item in imported if item[1] in ('PROVIDER', 'MODEL', 'ADAPTER_VERSION_V2')])
        self.assertEqual([item for item in imported if item[1] == 'interpretation'],
                         [(None, 'interpretation', None)])  # `from . import ..., interpretation, ...`, unaliased
        with mock.patch.object(jobs, '_v1_chain', return_value=True):
            self.assertEqual((jobs._reading_provider(), jobs._reading_model(), jobs._reading_adapter_version()),
                             (interpretation.PROVIDER, interpretation.MODEL, interpretation.ADAPTER_VERSION))
        self.assertEqual((jobs._reading_provider(), jobs._reading_model(), jobs._reading_adapter_version()),
                         (interpretation.PROVIDER_V3, interpretation.MODEL_V3, interpretation.ADAPTER_VERSION_V3))
        self.assertIs(jobs.interpretation_adapter, fable_adapter)
        self.assertEqual(holds.current_adapter_version(), interpretation.ADAPTER_VERSION_V3)

    def test_no_current_path_writer_names_an_earlier_label_and_every_reader_reads_both(self):
        from studio.interpretation import readers, store

        earlier = {'INTERPRETATION_VERSION_V2', 'APPRAISAL_VERSION', 'INVENTORY_VERSION_V2', 'ENGINE_VERSION_V2',
                   'INTERPRETATION_PAIR'}
        self.assertEqual(self.names(earlier), [])
        self.assertEqual(jobs.current_versions(), (interpretation.INTERPRETATION_PAIR_V3,
                                                   interpretation.INVENTORY_VERSION_V3))
        self.assertEqual(jobs._pass1_version(), interpretation.INTERPRETATION_VERSION_V3)
        self.assertEqual(jobs.V2_CHECK_SOURCE, f'cpt-studio:{interpretation.ENGINE_VERSION_V3}')
        both_engines = {interpretation.ENGINE_VERSION_V2, interpretation.ENGINE_VERSION_V3}
        self.assertEqual(set(readers.READ_ENGINES), both_engines)
        self.assertEqual(set(overlay.READ_CODINGS), both_engines)
        self.assertEqual(set(overlay.READ_RECORDS), both_engines)
        self.assertEqual(set(review.V2_ENGINES), both_engines)
        self.assertEqual(set(review.V2_PAIRS), {interpretation.INTERPRETATION_PAIR, interpretation.INTERPRETATION_PAIR_V3})
        self.assertTrue({(interpretation.INTERPRETATION_PAIR, interpretation.INVENTORY_VERSION_V2),
                         (interpretation.INTERPRETATION_PAIR_V3, interpretation.INVENTORY_VERSION_V3)}
                        <= set(store.READ_VERSIONS))
        self.assertTrue(all(jobs._is_v2_inventory(SimpleNamespace(interpretation_version=pair,
                                                                  inventory_version=inventory))
                            for pair, inventory in store.READ_VERSIONS))

    def test_the_new_sentences_name_no_provider_or_model(self):
        texts = (jobs.DECLINED_MESSAGE, jobs.HOLD_SET_MESSAGE, jobs.RETRY_DECLINED, jobs.RETRY_CUT_OFF,
                 jobs.INTERPRET_CUT_OFF_MESSAGE, jobs.APPRAISE_CUT_OFF_MESSAGE,
                 progress.INTERPRETATION_ERRORS['cut_off'][0], progress.INTERPRETATION_ERRORS['declined'][0])
        for text in texts:
            for name in PROVIDER_NAMES:
                self.assertNotIn(name, text.lower())
        from studio import customer_api

        for text in texts:
            self.assertIsNone(customer_api.FORBIDDEN.search(text), text)
