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
from studio.interpretation import adapter, holds, overlay, sentinel, wording
from studio.interpretation.contract import appraise_prompt, jsonschema
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import assess as engine_assess
from studio.interpretation.engine import combination, coverage
from studio.interpretation.engine import questions as engine_questions
from studio.providers.base import request_sha256
from studio.types import CodeReference, RawExchange
from tests.support import factories as f
from tests.test_interpretation_adapter import encoded, envelope, error_body, with_parts
from tests.test_pipeline_api import FakeProvider
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2.test_adapter import measured_pins
from tests.v2.test_settle import HEALTH_PIN, colonoscopy, event, fact, faithful, roles_of, src

AUTH = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
Run, Job = models.ProviderRun, models.Job
EXTRACTION, APPRAISAL = adapter.EXTRACTION, adapter.APPRAISAL
USAGE = {'promptTokenCount': 1000, 'candidatesTokenCount': 200, 'totalTokenCount': 1200}

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
    """A generateContent 200 body carrying ``answer_dict`` as its one text part."""
    return encoded(envelope(json.dumps(answer_dict)))


def answered(data: bytes, *, status=200, usage=True) -> RawExchange:
    """A live-like exchange that reached the vendor and was answered (``status``)."""
    ok = status == 200
    return RawExchange(outcome='succeeded' if ok else 'failed', sent=True, http_status=status, response_bytes=data,
                       response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=9.5,
                       usage=dict(USAGE) if ok and usage else {}, usage_basis='provider_reported_tokens' if ok else '',
                       requested_model=interpretation.MODEL, returned_model=interpretation.MODEL if ok else '',
                       error='' if ok else f'Google answered HTTP {status}; the response body is retained.')


UNKNOWN = RawExchange(outcome='unknown', sent=True, error='Read timed out after the request was sent.',
                      requested_model=interpretation.MODEL)
BARE_429 = error_body(429, 'RESOURCE_EXHAUSTED', message='synthetic: monthly spending cap')
HTTP_402 = encoded({'error': {'code': 402, 'message': 'synthetic: payment required'}})
HTTP_500 = encoded({'error': {'code': 500, 'message': 'synthetic', 'status': 'INTERNAL'}})


def appraisal_for(text, pages, kind, answer_dict):
    """The appraisal request the production builder makes for ``text`` and pass 1's ``answer_dict`` (the claims the
    oracle answers)."""
    extraction = adapter.build_extraction_request(text, pages, kind)
    return adapter.build_appraisal_request(text, pages, kind, extraction, body(answer_dict),
                                           check=jobs._checked_findings({}))


def oracle_answer(built, oracle=faithful, unlisted=()) -> bytes:
    """Pass 2's answer to ``built``: the oracle's verdict per claim (test_settle's faithful oracle by default)."""
    roles = roles_of(built.built.claim_set)
    verdicts = [found for found in (oracle(claim, roles[claim.id], built.built.claim_set)
                                    for claim in built.built.claim_set.claims) if found is not None]
    return body({'verdicts': verdicts, 'unlisted': list(unlisted)})


class ScriptedInterpreterV2(adapter.InterpreterV2):
    """Design v2's InterpreterV2 (its request checks, one-exchange loop, Stop check, envelope and classifier are the
    production code's) whose one exchange is answered here: pass 1 by the registered answer of the document the request
    carries, pass 2 by the oracle over the claim set the production builder makes for it - unless ``script`` holds
    RawExchanges for the purpose, given in turn first. Its endpoint is set, so a run reads as having called a vendor;
    its mode is 'replay', so no live gate applies. ``sent``: (purpose, request sha256) of every exchange made."""
    mode = 'replay'
    endpoint = 'https://interpreter.invalid/v2/synthetic:generateContent'

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
        self.enterContext(mock.patch.multiple(interpretation, HEALTH_THRESHOLDS_SHA256=HEALTH_PIN, **measured_pins()))
        self.ws = f.workspace()
        self.user = f.member(self.ws, f.user(), role=models.Membership.REVIEWER)
        self.interpreter = self.scripted()
        self.provider = FakeProvider([('45378', EXAM)])
        self.enterContext(mock.patch.object(jobs, 'get_provider', side_effect=lambda: self.provider))

    # --- helpers --------------------------------------------------------------------------------------------------------

    def scripted(self, **kwargs):
        interpreter = ScriptedInterpreterV2(ANSWERS, **kwargs)
        patcher = mock.patch.object(adapter, 'get_interpreter_v2', return_value=interpreter)
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
        self.assertEqual({run.adapter_version for run in first + second}, {interpretation.ADAPTER_VERSION_V2})
        [inventory] = models.EventInventory.objects.filter(revision=revision)
        self.assertEqual((inventory.state, inventory.interpretation_version, inventory.inventory_version),
                         ('read', interpretation.INTERPRETATION_PAIR, interpretation.INVENTORY_VERSION_V2))
        self.assertEqual((inventory.provider_run_id, inventory.appraisal_run_id), (first[0].pk, second[0].pk))
        appraise = Job.objects.get(encounter=encounter, kind=jobs.APPRAISE)
        self.assertEqual(appraise.idempotency_key,
                         f'appraise:{revision.pk}:{first[0].pk}:{second[0].request_sha256[:16]}')  # [R:MO-5]
        context = encounter.current_context
        self.assertEqual((context.version, context.event_inventory_id),
                         (interpretation.CONTEXT_VERSION_V2, inventory.pk))
        assessment = encounter.current_assessment
        self.assertEqual((assessment.engine_version, assessment.event_inventory_id, assessment.context_id),
                         (interpretation.ENGINE_VERSION_V2, inventory.pk, context.pk))
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
        self.assertEqual(assessment.engine_version, interpretation.ENGINE_VERSION_V2)
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
        recount = overlay.recount(stored, engine, engine, coding, R, member=member)
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
        self.scripted(script={EXTRACTION: [answered(encoded(envelope('{"not": "the schema"')))]})
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
        self.scripted(script={APPRAISAL: [answered(encoded(envelope('{"verdicts": "no"}')))]})
        encounter, revision = self.through('extract', 'interpret', 'appraise')
        [run] = self.runs(encounter, APPRAISAL)
        self.assertEqual((run.scope.get('effect'), run.scope.get('refused')), (holds.FAILED, jobs.READING_REFUSED))
        self.assertFalse(models.EventInventory.objects.filter(revision=revision).exists())
        self.assertEqual(self.state(encounter), 'provider_failed')
        self.assertEqual(jobs.retry_reading(encounter, self.user).kind, jobs.APPRAISE)

    def test_max_tokens_is_too_long_and_never_resent_for_a_member(self):
        cut = encoded(with_parts({'text': '{"events": ['}, finish='MAX_TOKENS'))
        self.scripted(script={EXTRACTION: [answered(cut)]})
        encounter, revision = self.through('extract', 'interpret')
        [run] = self.runs(encounter, EXTRACTION)
        self.assertEqual(run.scope.get('effect'), holds.TOO_LONG)
        self.assertEqual(progress.encounter_progress(encounter)['error']['action'], 'new_document')
        with self.assertRaises(jobs.Refused) as refused:
            jobs.retry_reading(encounter, self.user)
        self.assertEqual(str(refused.exception), jobs.RETRY_TOO_LONG)

    def test_a_claim_set_over_the_bound_is_too_long_and_not_sent(self):
        from studio.interpretation.contract import claims

        self.enterContext(mock.patch.object(claims, 'CLAIM_BOUND', 1))
        self.enterContext(mock.patch.multiple(interpretation, **measured_pins()))
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
        Job.objects.filter(pk=appraise.pk).update(started_at=timezone.now() - timedelta(seconds=700))
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
        self.assertEqual(assessment.engine_version, interpretation.ENGINE_VERSION_V2)
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
        return (overlay.recount(rows, engine, engine, coding, R, member=member),
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
