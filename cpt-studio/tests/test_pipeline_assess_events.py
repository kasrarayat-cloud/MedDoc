"""Pipeline II of the Gemini migration (design/FINAL.md 6.6-6.10, as design/ADJUDICATION.md amends them; slice S10): the
assess stage on a gemini context - the events engine over the context's EventInventory, its D22 record, the sentinel's
write gate - the peers on a new-path assess #1, assess #2, the AGAIN recompute and the retained re-assessment, the
bounded second review's follow-up, and the legacy contexts this image never assesses or sends on.

Synthetic data only, no network. Gemini is the replay interpreter over a recording written for each test (the request
built by the production adapter, so the recording is keyed by the live request's sha256); its answer is a synthetic
answer built by the contract suites' builders (tests.test_interpretation_identity, tests.test_interpretation_events).
Corti is an in-process fake (tests.test_pipeline_api.FakeProvider). Astra and Fable, where configured, are the real
replay adapters (their requests built and their answers read by the live adapters' own code) whose one-exchange tool
loop - the real loop - is answered by a script. The legacy reader's entry points are patched to fail if called."""
import hashlib
import json
import shutil
import tempfile
from contextlib import ExitStack
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings

from studio import interpretation, jobs, models, participants, review
from studio.gi import cues
from studio.interpretation import adapter, report, sentinel
from studio.interpretation.assess import SERVICES_STUB, INVENTORY_PROBLEMS
from studio.participants import anthropic_fable, loop, openai_astra, prompt
from studio.participants.http import describe
from studio.participants.replay import ReplayParticipant
from studio.types import RawExchange
from studio.validation import questions
from tests.support import factories as f
from tests.test_interpretation_events import COLONOSCOPE, POLYP, exam, reached, removed
from tests.test_interpretation_identity import a, act, answer, les, tg
from tests.test_participants_support import astra_with, code, empty_reading, fable_with
from tests.test_pipeline_api import FakeProvider

AUTH = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
USAGE = {'promptTokenCount': 1000, 'candidatesTokenCount': 200, 'totalTokenCount': 1200}
G1 = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
G2 = 'EGD: cold forceps biopsies were taken from the gastric antrum.'
G2_QUOTE = 'cold forceps biopsies were taken from the gastric antrum'
P1 = 'Colonoscopy: the colonoscope was inserted.'
L1 = les('L1', '6 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='6 mm')
MODULES = {'astra': openai_astra, 'fable': anthropic_fable}
EVENTS_HEADING = f'== {prompt.EVENTS_READING_HEADING} =='
LEGACY_HEADING = f'== {prompt.READING_HEADING} =='
ACK = review.ACKNOWLEDGEMENTS['human']
Run = models.ProviderRun
Job = models.Job


# --- the synthetic documents ------------------------------------------------------------------------------------------

def document(lines, **options):
    """(Gemini's synthetic answer, the document's text): the contract suites' answer over ``lines`` (P0 the date line,
    'Date of service: 11/09/2026.'), under the synthetic document's head line."""
    value, text = answer(lines, **options)
    return value, HEAD + text


def two_procedures():
    """An EGD to the second portion of the duodenum with antral biopsies - 43239, ready - and a colonoscopy whose extent
    is not stated with the sigmoid polyp's cold snare removal - 45385, held with its questions open."""
    return document({'G1': G1, 'G2': G2, 'P1': P1, 'P2': POLYP}, lesions=[L1], events=[
        exam('E0', 'G1', words='gastroscope', procedure=a('egd', 'EGD', ['G1'])),
        act('E5', 'G2', 'biopsy', 'biopsies', status_words='were taken', procedure=a('egd', 'EGD', ['G2']),
            technique=a('cold_forceps', 'cold forceps', ['G2']),
            target=tg('', 'gastric_antrum', 'gastric antrum', ['G2'])),
        exam('E1', 'P1', words='colonoscope', status_words='was inserted',
             procedure=a('colonoscopy', 'Colonoscopy', ['P1'])),
        removed(procedure=a('colonoscopy', 'polyp', ['P2']))],
        reach=[reached('E0', 'second_portion_duodenum', 'second portion of the duodenum', 'G1')])


def one_colonoscopy():
    """A colonoscopy to the cecum with the sigmoid polyp's cold snare removal: Corti selecting only 45378 leaves the
    removal an unresolved item no proposal covers, marked for the bounded second review."""
    return document({'P1': COLONOSCOPE, 'P2': POLYP}, lesions=[L1], events=[exam(), removed()], reach=[reached()])


TWO_CODES = (('43239', G2), ('45385', POLYP))  # Corti's selections on two_procedures()
PRIMARY_45378 = (('45378', COLONOSCOPE),)  # Corti's on one_colonoscopy(): the snare removal left uncovered
SECOND_45385 = (('45385', POLYP),)  # its second review's, on the excerpt (the removal's own passage)


def envelope(value) -> bytes:
    """A generateContent 200 body carrying ``value`` as its one candidate's text."""
    return json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps(value)}], 'role': 'model'},
                                       'finishReason': 'STOP', 'index': 0}],
                       'modelVersion': interpretation.MODEL, 'responseId': 'synthetic-s10',
                       'usageMetadata': USAGE}).encode()


class Corti(FakeProvider):
    """Corti's in-process fake whose selections depend on the request's text: the first group of (code, quote) whose
    quotes all appear in it - so a second review's excerpt is answered from its own passages."""

    def __init__(self, *groups):
        super().__init__()
        self.groups = [list(group) for group in groups]

    def send(self, request, *, deadline_s):
        text = request.contexts[0]
        self.selections = next((group for group in self.groups if all(quote in text for _, quote in group)), [])
        return super().send(request, deadline_s=deadline_s)


def is_peer(body) -> bool:
    instructions = body.get('instructions') if 'instructions' in body else body.get('system')
    return isinstance(instructions, str) and instructions.startswith(prompt.PEER_INSTRUCTIONS)


def final_answer(name, value, number) -> bytes:
    """``name``'s final answer (no tool call) carrying ``value`` - a reading or a peer review - as its output text."""
    data = json.loads(astra_with(value) if name == 'astra' else fable_with(value))
    data['id'] = f'{"resp" if name == "astra" else "msg"}_synthetic_s10_{number:04d}'
    return json.dumps(data).encode()


def reading(codes) -> dict:
    """A first reading in prompt.SCHEMA proposing ``codes``: (code, its verbatim quote)."""
    return empty_reading(codes=[code(value, service_ids=[], evidence=[quote]) for value, quote in codes])


EMPTY_PEER = {'question_answers': [], 'code_positions': [], 'additional_codes': [], 'references_used': []}


class Scripted(ReplayParticipant):
    """The real replay adapter of ``name`` - its requests built and its answers read by the live adapter's own code -
    whose tool loop is the real loop (studio.participants.loop), each phase's one exchange answered by the scripted
    final answer of that phase. ``requests`` records every request it was handed, with its phase."""

    def __init__(self, name, replay_dir, codes):
        super().__init__(name, replay_dir)
        self.endpoint = MODULES[name].ENDPOINT
        self.answers = {'first': final_answer(name, reading(codes), 1), 'peer': final_answer(name, EMPTY_PEER, 2)}
        self.requests = []

    def send_loop(self, request, *, deadline_s, client_request_id, original_bytes, execute_tool, should_stop=None,
                  carried=()):
        phase = 'peer' if is_peer(request.body) else 'first'
        self.requests.append((phase, request))
        data = self.answers[phase]

        def post(turn, body, deadline):
            usage, returned, response_id = describe(data)
            return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                               response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=10.0, usage=usage,
                               usage_basis='provider_reported_tokens', endpoint=self.endpoint,
                               requested_model=self.requested_model, returned_model=returned,
                               response_id=response_id)

        stop = {} if should_stop is None else {'should_stop': should_stop}
        return loop.run(self, request, post=post, parse_turn=self.live.parse_turn, follow_up=self.live.follow_up,
                        execute_tool=execute_tool, deadline_s=deadline_s, longest_s=self.loop_deadline,
                        max_exchanges=self.max_exchanges, max_tool_result_bytes=self.max_tool_result_bytes,
                        max_request_bytes=self.max_request_bytes, body_keys=self.live.BODY_KEYS, carried=carried,
                        **stop)

    def sent(self, phase):
        return [request for kind, request in self.requests if kind == phase]


LEGACY_ENTRY_POINTS = ('run_assessment', '_assess_child', '_analyze_child', '_route_child', 'make_context')


@override_settings(GEMINI_MODE='replay', PROVIDER_MODE='live', AUTHORIZATION_REF=AUTH, ASTRA_MODE='disabled',
                   FABLE_MODE='disabled', INTERPRET_MAX_CHARS=30_000, INTERPRET_MAX_PAGES=40)
class EventsCase(TestCase):
    """Corti answers ``corti_groups``; Astra and Fable, where a class configures them, answer ``participant_codes``."""
    corti_groups = (TWO_CODES,)
    participant_codes = (('43239', G2_QUOTE),)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # installed before any test patches a function the deny set is computed from (jobs' archived children): an
        # install that met a patched one would fail, and a failed install stands for the process
        status = sentinel.install()
        assert status['state'] == 'ok', status

    def setUp(self):
        self.replay = tempfile.mkdtemp(prefix='s10-replay-')
        self.addCleanup(shutil.rmtree, self.replay, True)
        replay = override_settings(GEMINI_REPLAY_DIR=self.replay)
        replay.enable()
        self.addCleanup(replay.disable)
        self.ws = f.workspace()
        self.user = f.member(self.ws, f.user(), role=models.Membership.REVIEWER)
        self.corti = Corti(*self.corti_groups)
        self.adapters = {name: Scripted(name, self.replay, self.participant_codes) for name in MODULES}
        for target, kwargs in (('studio.jobs.get_provider', {'return_value': self.corti}),
                               ('studio.participants.get_participant', {'side_effect': self.adapter})):
            patcher = mock.patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def adapter(self, name):
        return None if participants.participant_mode(name) == 'disabled' else self.adapters[name]

    # --- helpers ------------------------------------------------------------------------------------------------------

    def upload(self, scenario=two_procedures):
        """An encounter with a pasted SYNTHETIC revision of ``scenario``'s text, its pipeline started (extract queued)
        and Gemini's answer recorded for the request its interpret stage makes."""
        value, text = scenario()
        encounter = models.Encounter.objects.create(workspace=self.ws, title='Synthetic note', created_by=self.user)
        revision = f.pasted_revision(encounter, self.user, text, extract=False)
        jobs.start_pipeline(revision, self.user)
        self.run_next(Job.EXTRACT)
        revision.refresh_from_db()
        kind = jobs._participant_document(revision)[0]
        request = adapter.build_request(revision.text, jobs._participant_pages(revision), kind)
        folder = Path(self.replay) / adapter.NAME
        folder.mkdir(exist_ok=True)
        (folder / f'{request.canonical_sha256}.json').write_bytes(envelope(value))
        return encounter, revision

    def run_next(self, kind):
        job = jobs.claim_next()
        self.assertIsNotNone(job, f'no job queued; expected {kind}')
        self.assertEqual(job.kind, kind, job.idempotency_key)
        return jobs.run_job(job)

    def drain(self):
        """Run every queued stage; the stages run, in order."""
        ran = []
        while True:
            job = jobs.claim_next()
            if job is None:
                return ran
            ran.append(jobs.run_job(job))

    def legacy_reader_fails(self):
        """The legacy reader's entry points in studio.jobs, each patched to fail the test if called."""
        stack = ExitStack()
        for name in LEGACY_ENTRY_POINTS:
            stack.enter_context(mock.patch.object(jobs, name, side_effect=AssertionError(f'legacy {name} called')))
        return stack

    def assessments(self, encounter):
        return list(models.Assessment.objects.filter(encounter=encounter).order_by('created_at', 'pk'))

    def proposal(self, assessment, code_):
        found = [p for p in assessment.proposals.all() if p.code == code_ and p.bucket != 'alternative']
        self.assertEqual(len(found), 1, [(p.key, p.code, p.bucket) for p in assessment.proposals.all()])
        return found[0]

    def interpretation_runs(self, encounter):
        return Run.objects.filter(encounter=encounter, purpose=interpretation.PURPOSE).count()

    def assert_new_path(self, assessment, encounter, *, context=None):
        """A new-path assessment: the events engine's, made from the current context's EventInventory through that
        context, its routing the context's stand-in, and its D22 record describing it with no legacy execution."""
        context = context or assessment.context
        inventory = models.EventInventory.objects.get(revision=assessment.revision)
        self.assertEqual((assessment.engine_version, assessment.event_inventory_id, context.event_inventory_id),
                         ('cpt-studio-events@1', inventory.pk, inventory.pk))
        self.assertEqual((context.version, assessment.context_id), ('gemini-context@1', context.pk))
        self.assertEqual((assessment.routing.version, assessment.routing.result['inventory']),
                         ('gemini-routing@1', str(inventory.pk)))
        self.assertEqual(assessment.services, SERVICES_STUB)
        self.assertEqual(assessment.completeness['inventory_problems'], list(INVENTORY_PROBLEMS))
        record = assessment.interpretation
        self.assertEqual(sorted(record), sorted(report.RECORD_KEYS))
        self.assertEqual(record['inventory'], {'id': str(inventory.pk), 'sha256': inventory.sha256})
        self.assertEqual((record['gemini_run'], record['context'], record['engine_version']),
                         (str(inventory.provider_run_id), str(context.pk), 'cpt-studio-events@1'))
        self.assertEqual((record['interpretation_version'], record['inventory_version']),
                         ('gemini-events@1', 'gemini-inventory@1'))
        self.assertEqual(record['member_date_state']['state'], context.facts['service_date']['state'])
        self.assertEqual(record['sentinel'], {'legacy_calls': 0, 'scope': 'assess', 'tool': 'sys.monitoring',
                                              'deny_size': sentinel.DENY_SIZE, 'positive_control': 'ok'})
        self.assertEqual(report.record_problems(assessment), [])
        return inventory


# --- the chain --------------------------------------------------------------------------------------------------------

class FirstAssessmentTests(EventsCase):
    """FINAL 6.7 FIRST with no participant configured: the chain reaches a new-path assessment, which is final."""

    def test_the_chain_in_replay_makes_a_new_path_assessment_and_no_legacy_reader_runs(self):
        encounter, revision = self.upload()
        with self.legacy_reader_fails():
            ran = self.drain()
        self.assertEqual([(job.kind, job.state) for job in ran],
                         [('interpret', 'succeeded'), ('analyze', 'succeeded'), ('predict', 'succeeded'),
                          ('assess', 'succeeded')])
        [assessment] = self.assessments(encounter)
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_assessment_id, assessment.pk)
        self.assert_new_path(assessment, encounter, context=encounter.current_context)
        self.assertEqual(ran[-1].result['mode'], 'first')
        self.assertEqual(ran[-1].result['inventory'], str(assessment.event_inventory_id))
        self.assertTrue(review.is_final(assessment))
        self.assertEqual((self.proposal(assessment, '43239').status, self.proposal(assessment, '45385').status),
                         ('ready', 'needs_clarification'))
        self.assertEqual(self.interpretation_runs(encounter), 1)
        self.assertEqual(len(self.corti.sent), 1)

    def test_the_assess_reads_the_inventory_its_context_names_in_a_counted_bounded_child(self):
        encounter, revision = self.upload()
        for kind in ('interpret', 'analyze', 'predict'):
            self.run_next(kind)
        calls = []
        real = sentinel.run_counted

        def spy(fn, *args, **kwargs):
            calls.append((fn, args))
            return real(fn, *args, **kwargs)

        with mock.patch.object(sentinel, 'run_counted', side_effect=spy), self.legacy_reader_fails():
            job = self.run_next(Job.ASSESS)
        self.assertEqual(job.state, Job.SUCCEEDED, job.error)
        [(fn, args)] = calls
        self.assertIs(fn, jobs._assess_child_events)
        stored, facts = args[0], args[1]
        encounter.refresh_from_db()
        context = encounter.current_context
        self.assertEqual((stored.state, stored.sha256), ('read', context.event_inventory.sha256))
        self.assertEqual(facts, context.facts)  # the gemini context's facts, as stored


@override_settings(ASTRA_MODE='replay', FABLE_MODE='replay')
class ParticipantChainTests(EventsCase):
    """FINAL 6.6-6.7 with Astra and Fable configured: assess #1, the peer stages with the events heading, assess #2."""

    def test_the_full_chain_in_replay_makes_first_and_final_new_path_assessments(self):
        encounter, revision = self.upload()
        with self.legacy_reader_fails():
            ran = self.drain()
        self.assertEqual([(job.kind, job.state) for job in ran],
                         [('interpret', 'succeeded'), ('analyze', 'succeeded'), ('predict', 'succeeded'),
                          ('astra', 'succeeded'), ('fable', 'succeeded'), ('assess', 'succeeded'),
                          ('astra_peer', 'succeeded'), ('fable_peer', 'succeeded'), ('assess', 'succeeded')])
        first, final = self.assessments(encounter)
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_assessment_id, final.pk)
        context = encounter.current_context
        inventory = self.assert_new_path(first, encounter, context=context)
        self.assertEqual(self.assert_new_path(final, encounter, context=context), inventory)
        self.assertEqual(([job.result['mode'] for job in ran if job.kind == 'assess']), ['first', 'final'])
        self.assertEqual((jobs.assessment_phase(first), jobs.assessment_phase(final)), (1, 2))
        self.assertFalse(review.is_final(first))
        self.assertTrue(review.is_final(final))
        # assess #2 reads what assess #1 read, by id, and the peer runs made for it
        records1, records2 = review.model_records(first), review.model_records(final)
        for name in MODULES:
            self.assertEqual((records1[name]['state'], records2[name]['state']), ('read', 'read'))
            self.assertEqual(records2[name]['run'], records1[name]['run'])
            self.assertEqual(records2[name]['peer_state'], 'read')
            peer_run = Run.objects.get(pk=records2[name]['peer_run'])
            self.assertEqual((peer_run.purpose, peer_run.scope['assessment']), ('peer_review', str(first.pk)))
            self.assertEqual(records2[name]['frozen'], records1[name]['frozen'])
        self.assertEqual(self.proposal(final, '43239').status, 'ready')
        self.assertIn('astra', self.proposal(final, '43239').support['proposed_by'])
        # each peer request is the participant's own, built by its adapter, and heads CPT Studio's reading as the
        # events engine's reading after its first assessment (D9) - never as the legacy rule-based reading
        for name in MODULES:
            [peer_request] = self.adapters[name].sent('peer')
            document = MODULES[name]._peer_document(peer_request.body)
            self.assertIn(EVENTS_HEADING, document.split('\n'))
            self.assertNotIn(LEGACY_HEADING, document.split('\n'))
            shown = json.loads(document.split('\n')[document.split('\n').index(EVENTS_HEADING) + 1])
            self.assertEqual([item['code'] for item in shown['held']], ['45385'])
            self.assertTrue(shown['open_questions'])
            lowered = json.dumps(shown).lower()
            self.assertFalse([word for word in ('gemini', 'google', 'argon', 'routing') if word in lowered], lowered)
        self.assertEqual(self.interpretation_runs(encounter), 1)  # Gemini read the revision once
        self.assertEqual(len(self.corti.sent), 1)


class SentinelTests(EventsCase):
    """FINAL 6.7 step 6 and 10.3: zero denied executions up to every write of the chain, CALL-level checks on; and the
    assessment's write gate refuses on a planted count - in the stage itself or in its bounded child."""

    def test_zero_denied_executions_up_to_each_write_and_the_record_says_so(self):
        encounter, revision = self.upload()
        gates = []
        real_gate = sentinel.gate

        def spy(entry, **kwargs):
            scope = kwargs.get('scope_') or sentinel.current()
            gates.append((entry, scope.label if scope else None, scope.total(sentinel.NEW_PATH) if scope else None,
                          sentinel.refusal(scope)))
            return real_gate(entry, **kwargs)

        with sentinel.call_checks(), mock.patch.object(sentinel, 'gate', side_effect=spy):
            before = sentinel.totals()[sentinel.NEW_PATH]
            ran = self.drain()
            after = sentinel.totals()[sentinel.NEW_PATH]
            with sentinel.scope(sentinel.NEW_PATH, entry='positive-control') as probe:
                cues.page_number_line('3')
        self.assertTrue(all(job.state == Job.SUCCEEDED for job in ran), [(j.kind, j.state, j.error) for j in ran])
        self.assertEqual(after - before, 0, sentinel.top(sentinel.NEW_PATH))  # every stage, its writes included
        self.assertEqual([entry for entry, *_ in gates], ['interpret.send', 'interpret', 'analyze',
                                                          'assessment.persist'])
        self.assertEqual({(label, total, refusal) for _, label, total, refusal in gates}, {('new_path', 0, None)})
        [assessment] = self.assessments(encounter)
        self.assertEqual(assessment.interpretation['sentinel']['legacy_calls'], 0)
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())
        self.assertGreater(probe.count(sentinel.NEW_PATH), 0)  # the instrument fires: a legacy call is counted

    def through_predict(self, scenario=two_procedures):
        encounter, revision = self.upload(scenario)
        for kind in ('interpret', 'analyze', 'predict'):
            self.assertEqual(self.run_next(kind).state, Job.SUCCEEDED, kind)
        return encounter, revision

    def assert_refused_by_the_gate(self, job, encounter):
        self.assertEqual((job.state, job.error), (Job.FAILED, sentinel.MESSAGES['executed']))
        self.assertEqual(self.assessments(encounter), [])
        encounter.refresh_from_db()
        self.assertIsNone(encounter.current_assessment_id)
        [trip] = models.AuditEvent.objects.filter(event=sentinel.TRIPPED)
        self.assertEqual((trip.data['entry'], trip.data['reason'], trip.data['refused'], trip.data['label']),
                         ('assessment.persist', 'executed', True, 'new_path'))
        self.assertTrue(any('studio/gi/cues.py' in line for line in trip.data['executed']), trip.data)
        self.assertEqual(trip.encounter_id, encounter.pk)

    def test_the_write_gate_refuses_an_assessment_whose_stage_ran_legacy_code(self):
        encounter, _ = self.through_predict()
        real = jobs._retrieval

        def planted(*args, **kwargs):
            cues.page_number_line('3')  # a denied function, run in the stage after the child and before the insert
            return real(*args, **kwargs)

        with mock.patch.object(jobs, '_retrieval', side_effect=planted):
            job = self.run_next(Job.ASSESS)
        self.assert_refused_by_the_gate(job, encounter)

    def test_the_write_gate_refuses_an_assessment_whose_bounded_child_ran_legacy_code(self):
        encounter, _ = self.through_predict()
        real = jobs._assess_child_events

        def planted(*args):
            cues.page_number_line('3')  # run in the forked child: its counts come back with its result
            return real(*args)

        with mock.patch.object(jobs, '_assess_child_events', side_effect=planted):
            job = self.run_next(Job.ASSESS)
        self.assert_refused_by_the_gate(job, encounter)

    def test_an_assessment_is_never_recorded_outside_a_scope_the_sentinel_vouches_for(self):
        encounter, _ = self.through_predict()
        job = jobs.claim_next()
        self.assertEqual(job.kind, Job.ASSESS)
        with mock.patch.object(jobs, '_stage_scope', return_value=ExitStack()):  # a stage run with no scope open
            job = jobs.run_job(job)
        self.assertEqual(job.state, Job.FAILED)
        self.assertEqual(self.assessments(encounter), [])


@override_settings(ASTRA_MODE='replay', FABLE_MODE='replay')
class ParticipantSentinelTests(EventsCase):
    def test_zero_denied_executions_across_the_participants_and_peers(self):
        self.upload()
        with sentinel.call_checks():
            before = sentinel.totals()[sentinel.NEW_PATH]
            ran = self.drain()
            after = sentinel.totals()[sentinel.NEW_PATH]
        self.assertTrue(all(job.state == Job.SUCCEEDED for job in ran), [(j.kind, j.state, j.error) for j in ran])
        self.assertEqual(len(ran), 9)
        self.assertEqual(after - before, 0, sentinel.top(sentinel.NEW_PATH))


# --- AGAIN: an answer's recompute and the retained re-assessment (FINAL 6.7, 6.10; D8) --------------------------------

class AgainTests(EventsCase):
    def finished(self):
        encounter, revision = self.upload()
        ran = self.drain()
        self.assertTrue(all(job.state == Job.SUCCEEDED for job in ran), [(j.kind, j.state, j.error) for j in ran])
        [final] = self.assessments(encounter)
        return encounter, revision, final

    def approve(self, encounter, proposal):
        membership = models.Membership.objects.get(user=self.user, workspace=self.ws)
        return review.record_decision(encounter=encounter, proposal=proposal, action=review.APPROVE, user=self.user,
                                      membership=membership, acknowledgement=ACK)

    def answer_first_question(self, encounter, revision, assessment, proposal,
                              value=models.MemberAnswer.NOT_DOCUMENTED):
        """A member's answer to ``proposal``'s first open question, bound to that question's fingerprint as the stored
        rows give it (questions.question_passages over the record's services stub - FINAL 7.11: the same function the
        engine and the old image compute)."""
        row = proposal.clarifications.filter(state=models.Clarification.OPEN).order_by('created_at', 'pk').first()
        family = row.family or proposal.family
        shown = questions.question_passages(assessment.services, family, row.fact, proposal.evidence, proposal.support,
                                            revision.text, questions.acts_of(assessment.services))
        key = questions.member_key(proposal.code, family, row.fact)
        fingerprint = questions.group([(key, questions.instance(row.scope, family, row.fact, proposal.code,
                                                                row.question, row.reason, shown))])[key]
        return models.MemberAnswer.objects.create(encounter=encounter, revision=revision, assessment=assessment,
                                                  fact=row.fact, family=family, code=proposal.code, value=value,
                                                  answered_by=self.user, question=fingerprint)

    def test_decisions_carry_across_an_answer_recompute_and_nothing_is_sent(self):
        encounter, revision, final = self.finished()
        ready = self.proposal(final, '43239')
        decision = self.approve(encounter, ready)
        held = self.proposal(final, '45385')
        answer_ = self.answer_first_question(encounter, revision, final, held)
        runs = Run.objects.filter(encounter=encounter).count()
        encounter.refresh_from_db()  # as answers.save_details passes it: the encounter as it stands, under its lock
        queued = jobs.recompute_after_answers(encounter, self.user)
        self.assertIn(f'{jobs.AGAIN_MARK}{jobs.ANSWERS_MARK}', queued.idempotency_key)
        with self.legacy_reader_fails():
            [job] = self.drain()
        self.assertEqual((job.kind, job.state, job.result['mode']), ('assess', Job.SUCCEEDED, 'again'))
        _, again = self.assessments(encounter)
        self.assert_new_path(again, encounter)
        self.assertEqual((again.context_id, again.provider_run_id), (final.context_id, final.provider_run_id))
        excluded = self.proposal(again, '45385')
        self.assertEqual((excluded.bucket, excluded.support['answered']['answers']), ('excluded', [str(answer_.pk)]))
        carried_to = self.proposal(again, '43239')
        self.assertEqual(carried_to.fingerprint, ready.fingerprint)
        carried = models.Decision.objects.get(assessment=again, proposal=carried_to)
        self.assertEqual((carried.action, carried.carried_from_id), (models.Decision.APPROVE, decision.pk))
        self.assertFalse(models.DecisionInvalidation.objects.exists())
        self.assertEqual(Run.objects.filter(encounter=encounter).count(), runs)  # nothing sent, nothing reused
        self.assertEqual((len(self.corti.sent), self.interpretation_runs(encounter)), (1, 1))

    def test_a_retained_re_assessment_re_reads_the_final_by_id_and_sends_nothing(self):
        encounter, revision, final = self.finished()
        decision = self.approve(encounter, self.proposal(final, '43239'))
        runs = Run.objects.filter(encounter=encounter).count()
        out = jobs.reassess_retained(encounter, 'release-s10')
        self.assertEqual((out['action'], out['final_assessment']), ('queued', str(final.pk)))
        with self.legacy_reader_fails():
            [job] = self.drain()
        self.assertEqual((job.state, job.result['mode']), (Job.SUCCEEDED, 'again'))
        # the same inputs give the same result: the final stands, its decision with it
        self.assertEqual(job.result['assessment'], str(final.pk))
        self.assertEqual(self.assessments(encounter), [final])
        self.assertEqual(review.current_decisions(final), {decision.proposal_id: decision})
        self.assertEqual(Run.objects.filter(encounter=encounter).count(), runs)

    def test_an_assess_after_the_final_reads_only_a_final_made_from_its_contexts_inventory(self):
        encounter, revision, final = self.finished()
        jobs.reassess_retained(encounter, 'release-s10')
        moved = SimpleNamespace(pk=final.pk, context_id=final.context_id, provider_run_id=final.provider_run_id,
                                event_inventory_id=None)  # a final made from another inventory (here: none)
        with mock.patch.object(jobs, '_newest_assessment', return_value=moved):
            [job] = self.drain()
        self.assertEqual((job.state, job.result), (Job.SUCCEEDED, {'skipped': jobs.ASSESS_MOVED}))
        self.assertEqual(self.assessments(encounter), [final])


# --- the bounded second review's follow-up (FINAL 6.8, 7.10) ----------------------------------------------------------

class SecondReviewCase(EventsCase):
    corti_groups = (PRIMARY_45378, SECOND_45385)

    def asked(self, encounter):
        """The final assessment, once the member asked for the bounded second review on it (the stage queued)."""
        [final] = [a for a in self.assessments(encounter) if review.is_final(a)][-1:]
        encounter.refresh_from_db()
        marked = [item for item in final.completeness['unresolved_items'] if item.get('second_review')]
        self.assertEqual([item['reason'] for item in marked], ['not_covered'])
        status = jobs.second_review_status(encounter)
        self.assertEqual((status['available'], status['reason']), (True, ''))
        job = jobs.request_second_review(encounter, self.user)
        self.assertEqual(job.kind, Job.REVIEW2)
        return final


class SecondReviewTests(SecondReviewCase):
    def test_the_follow_up_merges_the_second_review_through_the_events_engine_and_queues_nothing(self):
        encounter, revision = self.upload(one_colonoscopy)
        self.drain()
        final = self.asked(encounter)
        with self.legacy_reader_fails():
            ran = self.drain()
        self.assertEqual([(job.kind, job.state) for job in ran], [('review2', 'succeeded'), ('assess', 'succeeded')])
        second = Run.objects.get(encounter=encounter, purpose=Run.SECOND_REVIEW)
        self.assertEqual((second.state, second.scope['assessment']), (Run.SUCCEEDED, str(final.pk)))
        self.assertIn(POLYP, second.contexts[0])  # the excerpt: the uncovered removal's own passage
        self.assertNotIn(COLONOSCOPE, second.contexts[0])
        self.assertEqual((ran[1].result['mode'], ran[1].result['second_review']), ('review2', str(second.pk)))
        self.assertIn(':review2:', ran[1].idempotency_key)
        _, followed = self.assessments(encounter)
        self.assert_new_path(followed, encounter)
        self.assertEqual((followed.second_run_id, followed.context_id, followed.provider_run_id),
                         (second.pk, final.context_id, final.provider_run_id))
        added = self.proposal(followed, '45385')
        self.assertEqual(added.support['origin'], 'second_review')
        self.assertTrue(review.is_final(followed))
        self.assertIsNone(jobs.claim_next())  # it queues nothing
        self.assertEqual((len(self.corti.sent), self.interpretation_runs(encounter)), (2, 1))


@override_settings(ASTRA_MODE='replay', FABLE_MODE='replay')
class SecondReviewParticipantTests(SecondReviewCase):
    participant_codes = (('45378', 'The colonoscope was advanced to the cecum'),)

    def test_the_follow_up_reads_the_finals_inputs_by_id_and_no_peer_review_is_asked_again(self):
        encounter, revision = self.upload(one_colonoscopy)
        self.assertEqual(len(self.drain()), 9)
        final = self.asked(encounter)
        self.assertEqual(jobs.assessment_phase(final), 2)
        with self.legacy_reader_fails():
            ran = self.drain()
        self.assertEqual([(job.kind, job.state) for job in ran], [('review2', 'succeeded'), ('assess', 'succeeded')])
        followed = self.assessments(encounter)[-1]
        self.assert_new_path(followed, encounter)
        self.assertEqual(ran[1].result['mode'], 'review2')
        before, after = review.model_records(final), review.model_records(followed)
        for name in MODULES:
            self.assertEqual({key: after[name][key] for key in ('state', 'run', 'peer_state', 'peer_run')},
                             {key: before[name][key] for key in ('state', 'run', 'peer_state', 'peer_run')})
            self.assertEqual(after[name]['frozen'], before[name]['frozen'])
            self.assertEqual((len(self.adapters[name].sent('first')), len(self.adapters[name].sent('peer'))), (1, 1))
        self.assertEqual((jobs.assessment_phase(followed), review.is_final(followed)), (2, True))
        self.assertEqual(self.proposal(followed, '45385').support['origin'], 'second_review')
        self.assertIsNone(jobs.claim_next())


# --- a legacy context: never assessed, sent on, recomputed or re-assessed on this image (FINAL 6.7-6.10, 9) -----------

@override_settings(ASTRA_MODE='replay', FABLE_MODE='replay')
class LegacyContextTests(EventsCase):
    def legacy_encounter(self):
        return legacy_encounter(self.ws, self.user)

    def test_no_stage_assesses_or_sends_on_a_legacy_context_and_a_resume_has_the_revision_read(self):
        encounter, revision, context, legacy = self.legacy_encounter()
        keys = ((Job.ASSESS, f'assess:{context.pk}:no-provider'), (Job.ASTRA, f'astra:{"0" * 32}'),
                (Job.ASTRA_PEER, f'astra_peer:{jobs._digest(legacy.pk)}'),
                (Job.REVIEW2, f'review2:{revision.pk}:{legacy.pk}'))
        with self.legacy_reader_fails():
            for kind, key in keys:
                jobs.enqueue(kind, encounter=encounter, revision=revision, context=context, key=key,
                             requested_by=self.user)
                job = self.run_next(kind)
                self.assertEqual((job.state, job.error), (Job.CANCELLED, jobs.EARLIER_READING_MESSAGE), kind)
        self.assertEqual(self.assessments(encounter), [legacy])
        self.assertFalse(Run.objects.filter(encounter=encounter).exists())
        self.assertEqual(len(self.corti.sent), 0)
        self.assertEqual([len(adapter_.requests) for adapter_ in self.adapters.values()], [0, 0])
        encounter.refresh_from_db()
        job = jobs.resume(encounter, self.user)  # a member's explicit act: the revision's first interpretation
        self.assertEqual((job.kind, job.context_id, job.idempotency_key.split(':resume:')[0]),
                         ('interpret', None, f'interpret:{revision.pk}:gemini-events@1'))

    def test_an_answer_is_not_recomputed_and_no_retained_re_assessment_or_second_review_is_taken(self):
        encounter, revision, context, legacy = self.legacy_encounter()
        jobs.enqueue(Job.ASSESS, encounter=encounter, revision=revision, context=context,
                     key=f'assess:{context.pk}:no-provider', requested_by=self.user)
        Job.objects.filter(encounter=encounter).update(state=Job.SUCCEEDED, result={'assessment': str(legacy.pk)})
        encounter.refresh_from_db()
        self.assertIsNone(jobs.recompute_after_answers(encounter, self.user))
        with self.assertRaises(jobs.Refused) as refused:
            jobs.reassess_retained(encounter, 'release-s10')
        self.assertEqual(str(refused.exception), jobs.RETAINED_LEGACY)
        self.assertEqual(jobs._second_review_bounds(encounter, revision, context, legacy),
                         jobs.SECOND_REVIEW_EARLIER_CONTEXT)
        self.assertEqual(Job.objects.filter(encounter=encounter).count(), 1)  # nothing queued


def legacy_encounter(ws, user, scenario=two_procedures):
    """An encounter the legacy reader read, as the live encounters stand at the install: its revision of ``scenario``'s
    text extracted, a gi-context@5 context and a legacy routing current, a legacy final assessment; no event inventory.
    (encounter, revision, context, assessment)."""
    encounter = models.Encounter.objects.create(workspace=ws, title='Synthetic note', created_by=user)
    _, text = scenario()
    revision = f.pasted_revision(encounter, user, text)
    context = models.EncounterContext.objects.create(
        encounter=encounter, revision=revision, version=jobs.CONTEXT_VERSION, sha256='0' * 64, user_values={},
        facts={'service_date': {'name': 'service_date', 'value': '2026-11-09', 'origin': 'document', 'evidence': [],
                                'note': ''}})
    routing = models.RoutingRun.objects.create(revision=revision, version='gi-routing@12', sha256='1' * 64,
                                               result={'version': 'gi-routing@12', 'findings': []},
                                               service_date=date(2026, 11, 9))
    legacy = models.Assessment.objects.create(
        encounter=encounter, revision=revision, context=context, routing=routing, provider_run=None,
        profiles_version='gi-profiles@3', engine_version='cpt-studio-validation@10', sha256='2' * 64)
    encounter.current_context, encounter.current_assessment = context, legacy
    encounter.save(update_fields=['current_context', 'current_assessment', 'updated_at'])
    return encounter, revision, context, legacy


# --- persist_assessment's new-path record (FINAL 4.2, 6.7, 8.3) -------------------------------------------------------

class PersistTests(EventsCase):
    def test_an_insert_whose_record_does_not_describe_it_is_never_kept(self):
        encounter, _ = self.upload()
        for kind in ('interpret', 'analyze', 'predict'):
            self.run_next(kind)
        real = report.interpretation_record

        def counted(**kwargs):
            record = real(**kwargs)
            return {**record, 'sentinel': {**record['sentinel'], 'legacy_calls': 2}}

        with mock.patch.object(report, 'interpretation_record', side_effect=counted):
            job = self.run_next(Job.ASSESS)
        self.assertEqual(job.state, Job.FAILED)
        self.assertIn('Its interpretation record does not describe it: The sentinel counted 2 legacy executions',
                      job.error)
        self.assertEqual(self.assessments(encounter), [])

    def test_an_assessment_is_recorded_only_with_its_inventorys_stand_in(self):
        encounter, revision = self.upload()
        for kind in ('interpret', 'analyze', 'predict'):
            self.run_next(kind)
        legacy_routing = models.RoutingRun.objects.create(
            revision=revision, version='gi-routing@12', sha256='1' * 64, service_date=date(2026, 11, 9),
            result={'version': 'gi-routing@12', 'findings': []})
        with mock.patch.object(jobs, '_events_stand_in', return_value=legacy_routing):
            job = self.run_next(Job.ASSESS)
        self.assertEqual((job.state, job.error), (Job.FAILED, 'The assessment was not recorded: The routing record is '
                                                              'not the one derived from this event inventory.'))
        self.assertEqual(self.assessments(encounter), [])

    def test_a_context_its_inventory_and_values_do_not_derive_is_never_assessed(self):
        encounter, revision = self.upload()
        for kind in ('interpret', 'analyze', 'predict'):
            self.run_next(kind)
        real = jobs.interpretation_facts.derive

        def other(stored, values):
            derived = real(stored, values)
            return derived.__class__(facts=derived.facts, document_date=derived.document_date,
                                     effective=derived.effective,
                                     member_date=derived.member_date.__class__(
                                         **{**vars(derived.member_date), 'state': 'conflicts'}))

        with mock.patch.object(jobs.interpretation_facts, 'derive', side_effect=other):
            job = self.run_next(Job.ASSESS)
        self.assertEqual((job.state, job.error), (Job.FAILED, jobs.CONTEXT_DERIVATION_MESSAGE))
        self.assertEqual(self.assessments(encounter), [])

    def test_the_two_engines_rows_never_cross(self):
        new = SimpleNamespace(engine_version='cpt-studio-events@1')
        old = SimpleNamespace(engine_version='cpt-studio-validation@10')
        gemini = SimpleNamespace(version='gemini-context@1')
        legacy = SimpleNamespace(version='gi-context@5')
        inventory, record = SimpleNamespace(pk='i'), {'sentinel': {}}
        self.assertTrue(review._new_path(new, gemini, inventory, record))
        self.assertFalse(review._new_path(old, legacy, None, None))
        for result, context, inv, rec in ((new, gemini, None, record), (new, gemini, inventory, None),
                                          (new, legacy, inventory, record), (old, legacy, inventory, None),
                                          (old, legacy, None, record), (old, gemini, None, None)):
            with self.subTest(result=result.engine_version, context=context.version, inventory=inv, record=rec):
                with self.assertRaises(ValueError):
                    review._new_path(result, context, inv, rec)

    def test_the_same_assessment_is_the_same_only_from_the_same_inventory(self):
        previous = SimpleNamespace(sha256='d', revision_id=1, context_id=2, routing_id=3, provider_run_id=None,
                                   second_run_id=None, event_inventory_id='inv-1', participants=[])
        ids = SimpleNamespace(pk=1), SimpleNamespace(pk=2), SimpleNamespace(pk=3)
        self.assertTrue(review._same_assessment(previous, 'd', *ids, None,
                                                event_inventory=SimpleNamespace(pk='inv-1')))
        self.assertFalse(review._same_assessment(previous, 'd', *ids, None,
                                                 event_inventory=SimpleNamespace(pk='inv-2')))
        self.assertFalse(review._same_assessment(previous, 'd', *ids, None))  # a legacy re-assessment names none
        legacy = SimpleNamespace(**{**vars(previous), 'event_inventory_id': None})
        self.assertTrue(review._same_assessment(legacy, 'd', *ids, None))  # as before the migration

    def test_what_changed_says_the_interpretation_changed(self):
        def made(engine, inventory):
            return SimpleNamespace(context=SimpleNamespace(facts={}, user_values={}), provider_run=None,
                                   routing=SimpleNamespace(sha256='r'), profiles_version='gi-profiles@3',
                                   engine_version=engine, reference_sources=[], event_inventory_id=inventory)

        legacy, legacy2 = made('cpt-studio-validation@10', None), made('cpt-studio-validation@10', None)
        first, same, other = (made('cpt-studio-events@1', 'i1'), made('cpt-studio-events@1', 'i1'),
                              made('cpt-studio-events@1', 'i2'))
        self.assertEqual(review._what_changed(legacy, first),
                         ['engine cpt-studio-validation@10 → cpt-studio-events@1', 'the interpretation changed'])
        self.assertEqual(review._what_changed(first, other), ['the interpretation changed'])
        self.assertEqual(review._what_changed(first, same), [])
        self.assertEqual(review._what_changed(legacy, legacy2), [])  # two legacy assessments: worded as before
