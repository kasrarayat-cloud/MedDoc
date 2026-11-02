"""harness@2 part B's pipeline (HARNESS.md 11, 12.1-12.5; I1, I5, I8, I9, I10): phase 1 on the tool loop with its
exchanges and tool calls, assess #1's records, the peer stages and their gating, assess #2, the re-assessment after a
confirmation, and the stale sweep, Stop, Resume and reconcile across phase 2.

Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake. Astra and Fable are the real replay
adapters (studio.participants.replay: their requests are built and their answers read by the live adapters' own code)
whose tool loop is the real loop (studio.participants.loop) with the live vendor halves; each exchange is answered by a
script instead of a recording, so a test decides what each turn asks for. Their tool calls are answered by CPT Studio's
real CMS tool executor (studio.reference.tools) over a synthetic reference store and the bundled passage files.
"""
import hashlib
import json
import tempfile
import uuid
from datetime import date, timedelta
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from studio import audit, jobs, models, review
from studio.participants import anthropic_fable, loop, openai_astra, prompt
from studio.participants.http import describe
from studio.participants.replay import ReplayParticipant
from studio.providers.base import canonical_body
from studio.reference import passages as reference_passages
from studio.reference import tools
from studio.types import PeerReview, RawExchange, sha256_json, to_jsonable
from tests.support import factories as f
from tests.test_harness_pipeline import BOTH, TIME_QUOTE, ScriptedCorti
from tests.test_participants_support import (OfflineMixin, astra_tool_call, astra_with, code, empty_reading,
                                             fable_tool_use, fable_with, service)
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_pipeline import LIVE, RECONCILE_NOTE

DAY = '2026-10-20'
PFS_KEY, MUE_KEY = 'cms-pfs-rvu26d', 'cms-mue-practitioner-2026q4'
MODELS = {'astra': openai_astra.MODEL, 'fable': anthropic_fable.MODEL}
LIVE_MODULES = {'astra': openai_astra, 'fable': anthropic_fable}
CORTI_DISPLAY = 'UNVERIFIED PROVIDER WORDING'  # the Corti fake's display text: never shown to a peer (I9)
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
LAND = 'Landmarks photographed: appendiceal orifice and ileocecal valve.'
SNARE = 'was removed with a hot snare'
BIOPSY = 'was biopsied with cold forceps'
# Two colonoscopy codes, each held on the extent (routing reads none: "Landmarks photographed" is not one), as in the
# engine's confirmation suite: two open proposal questions for a peer review and a reviewer to answer.
TWO_EXTENTS = (HEAD + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
               'Place of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
               'A 9 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.\n'
               'A separate 12 mm flat lesion in the ascending colon was biopsied with cold forceps.\n' + LAND + '\n')
PFS_ROWS = {
    '45378': {'status': 'A', 'global_days': '000', 'mult_proc': '2', 'endo_base': None, 'pctc': '0'},
    '45380': {'status': 'A', 'global_days': '000', 'mult_proc': '3', 'endo_base': '45378', 'pctc': '0'},
    '45385': {'status': 'A', 'global_days': '000', 'mult_proc': '3', 'endo_base': '45378', 'pctc': '0'},
    '99213': {'status': 'A', 'global_days': 'XXX', 'mult_proc': '0', 'endo_base': None, 'pctc': '0'},
    '99214': {'status': 'A', 'global_days': 'XXX', 'mult_proc': '0', 'endo_base': None, 'pctc': '0'},
}
MUE_ROW = {'value': 1, 'mai': {'indicator': 2, 'label': 'Date of Service Edit: Policy'},
           'rationale': 'Anatomic Consideration'}


def install_reference_store():
    """Synthetic CMS rows in the layout the importers store, and the bundled passage files as an installation imports
    them."""
    retrieved = timezone.now()

    def source(key, kind, release):
        return models.ReferenceSource.objects.create(
            key=key, kind=kind, publisher='CMS', title=f'Synthetic {key}', release=release,
            url='https://www.cms.gov/synthetic', sha256=hashlib.sha256(key.encode()).hexdigest(),
            retrieved_at=retrieved, effective_start=date(2026, 10, 1), effective_end=date(2026, 12, 31),
            license_note='CPT codes are copyright the American Medical Association.', scope_note='synthetic')
    pfs, mue = source(PFS_KEY, 'cms-pfs', 'RVU26D'), source(MUE_KEY, 'cms-mue-practitioner', '2026-Q4')
    for value, facts in PFS_ROWS.items():
        models.ReferenceCodeFact.objects.create(source=pfs, code=value, facts=facts)
        models.ReferenceCodeFact.objects.create(source=mue, code=value, facts=MUE_ROW)
    for path in reference_passages.bundled_files():
        reference_passages.import_data_file(path)


# --- what a participant answers ---------------------------------------------------------------------------------------

def reading(codes=(), services=(), references=(), not_coded=(), date_value='', date_evidence=()):
    """A reading in prompt.SCHEMA: ``codes`` (code, quote), ``services`` (id, family, status, quote), ``references``
    (ref, use), ``not_coded`` (code, reason, quote)."""
    return empty_reading(
        date_of_service={'value': date_value, 'evidence': list(date_evidence)},
        services=[service(1, id=sid, family=family, status=status, evidence=[quote])
                  for sid, family, status, quote in services],
        codes=[code(value, service_ids=[], evidence=[quote]) for value, quote in codes],
        not_coded=[{'service_ids': [], 'code': value, 'reason': reason, 'evidence': [quote]}
                   for value, reason, quote in not_coded],
        references_used=[{'ref': ref, 'use': use} for ref, use in references])


def peer_answer(answers=(), positions=(), codes=(), references=()):
    """A peer review in prompt.PEER_SCHEMA: ``answers`` (question id, settled, value, quote), ``positions`` (code,
    position, quote), ``codes`` (code, quote) first proposed after peer review, ``references`` (ref, use)."""
    return {'question_answers': [{'question_id': qid, 'settled': settled, 'value': value,
                                  'evidence': [quote] if quote else []} for qid, settled, value, quote in answers],
            'code_positions': [{'code': value, 'position': position, 'reason': 'Synthetic position.',
                                'evidence': [quote] if quote else []} for value, position, quote in positions],
            'additional_codes': [code(value, service_ids=[], evidence=[quote]) for value, quote in codes],
            'references_used': [{'ref': ref, 'use': use} for ref, use in references]}


def answered(name, answer, number=1):
    """``name``'s final answer, carrying ``answer`` (a reading or a peer review) as its output text."""
    data = astra_with(answer) if name == 'astra' else fable_with(answer)
    envelope = json.loads(data)
    envelope['id'] = f'{"resp" if name == "astra" else "msg"}_synthetic_final_{number:04d}'
    return json.dumps(envelope).encode()


def asks(name, *calls, number=1):
    """``name``'s answer asking for tool calls: (call id, tool, arguments)."""
    return (astra_tool_call if name == 'astra' else fable_tool_use)(*calls, number=number)


def facts_call(call_id, codes, day=DAY):
    return call_id, 'cms_code_facts', {'codes': list(codes), 'date_of_service': day}


def passages_call(call_id, topic, codes=()):
    return call_id, 'cms_policy_passages', {'topic': topic, 'codes': list(codes)}


def failed(note='Overloaded (synthetic).'):
    data = b'{"error": {"type": "overloaded_error"}}'
    return RawExchange(outcome='failed', sent=True, http_status=529, response_bytes=data,
                       response_sha256=hashlib.sha256(data).hexdigest(), error=note,
                       provider_request_id='req_synthetic_failed')


def unknown(note='Read timed out after the request was sent (synthetic).'):
    return RawExchange(outcome='unknown', sent=True, error=note)


def is_peer(body):
    return (body.get('instructions') if 'instructions' in body else body.get('system')) == prompt.PEER_INSTRUCTIONS


def peer_document(name, body):
    return LIVE_MODULES[name]._peer_document(body)


def question_ids(name, body):
    return prompt.peer_document_inputs(peer_document(name, body))[0]


def document_sections(document):
    """The peer document's labelled JSON lines: {label: parsed content}."""
    lines, out = document.split('\n'), {}
    for index, line in enumerate(lines[:-1]):
        if line.startswith('== ') or line.endswith('):'):
            try:
                out[line] = json.loads(lines[index + 1])
            except ValueError:
                pass
    return out


class LoopParticipant(ReplayParticipant):
    """The real replay adapter of ``name`` with a scripted tool loop: ``first`` and ``peer`` are the steps of its
    phase-1 and peer-review loops, one per exchange - the answer's bytes (a 200), a RawExchange, or a callable given the
    exchange's stored request body that returns either - used for every loop of that phase, unless ``first_loops`` or
    ``peer_loops`` holds step lists, of which each loop takes the next. Every loop and exchange is recorded."""

    def __init__(self, name, replay_dir, *, mode='replay'):
        super().__init__(name, replay_dir)
        self.mode, self.first, self.peer, self.loops = mode, [], [], []
        self.first_loops, self.peer_loops = [], []
        self.endpoint = LIVE_MODULES[name].ENDPOINT

    def send_loop(self, request, *, deadline_s, client_request_id, original_bytes, execute_tool):
        phase = 'peer' if is_peer(request.body) else 'first'
        queued = self.peer_loops if phase == 'peer' else self.first_loops
        steps = list(queued.pop(0) if queued else (self.peer if phase == 'peer' else self.first))
        record = {'phase': phase, 'request': request.canonical_sha256, 'deadline_s': deadline_s,
                  'client_request_id': client_request_id, 'execute_tool': execute_tool, 'bodies': [],
                  'original': hashlib.sha256(original_bytes).hexdigest() if original_bytes else None}
        self.loops.append(record)

        def post(turn, body, deadline):
            record['bodies'].append(body)
            if turn > len(steps):
                raise AssertionError(f'{self.name} {phase}: no scripted answer for exchange {turn}')
            step = steps[turn - 1]
            step = step(body) if callable(step) else step
            if isinstance(step, RawExchange):
                return step
            usage, returned, response_id = describe(step)
            return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=step,
                               response_sha256=hashlib.sha256(step).hexdigest(), latency_ms=10.0 + turn, usage=usage,
                               usage_basis='provider_reported_tokens', provider_request_id=f'req_{self.name}_{turn}',
                               endpoint=self.endpoint, requested_model=self.requested_model, returned_model=returned,
                               response_id=response_id)

        return loop.run(self, request, post=post, parse_turn=self.live.parse_turn, follow_up=self.live.follow_up,
                        execute_tool=execute_tool, deadline_s=deadline_s, longest_s=self.loop_deadline,
                        max_exchanges=self.max_exchanges, max_tool_result_bytes=self.max_tool_result_bytes,
                        max_request_bytes=self.max_request_bytes, body_keys=self.live.BODY_KEYS)

    def loops_of(self, phase):
        return [record for record in self.loops if record['phase'] == phase]


ASTRA_READING = reading(codes=[('99213', TIME_QUOTE)], services=[('v1', 'office_em', 'performed', TIME_QUOTE)],
                        references=[(f'fact:{PFS_KEY}:99213:status', 'The visit code is payable.'),
                                    ('rule-01', 'Cited but never retrieved.')])
FABLE_READING = reading(codes=[('99213', TIME_QUOTE)], services=[('v1', 'office_em', 'performed', TIME_QUOTE)],
                        references=[('status-A', 'What status A means.'),
                                    (f'fact:{PFS_KEY}:99213:status', 'Retrieved by Astra, never by Fable.')])
EMPTY_PEER = peer_answer()


@override_settings(**LIVE, **BOTH)
class Harness2Case(OfflineMixin, TestCase):
    """Corti is ScriptedCorti; Astra and Fable are LoopParticipants (configured by the settings' modes), each answering
    its first reading after one tool call and its peer review at once, unless a test scripts otherwise."""
    corti_codes = (('99213', TIME_QUOTE),)

    def setUp(self):
        super().setUp()
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        install_reference_store()
        self.corti = ScriptedCorti(selections=list(self.corti_codes))
        self.adapters = {name: LoopParticipant(name, self.tmp) for name in ('astra', 'fable')}
        self.adapters['astra'].first = [asks('astra', facts_call('call_astra_1', ['99213'])),
                                        answered('astra', ASTRA_READING)]
        self.adapters['fable'].first = [asks('fable', facts_call('toolu_fable_1', ['99213'])),
                                        answered('fable', FABLE_READING)]
        for name in ('astra', 'fable'):
            self.adapters[name].peer = [answered(name, EMPTY_PEER, number=2)]
        from studio import participants

        def adapter(name):
            return None if participants.participant_mode(name) == 'disabled' else self.adapters[name]
        for target, kwargs in (('studio.jobs.get_provider', {'return_value': self.corti}),
                               ('studio.participants.get_participant', {'side_effect': adapter})):
            patcher = mock.patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)

    def create(self, text=OFFICE_NOTE, **extra):
        response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def post(self, path, data):
        return self.client.post(path, data=json.dumps(data), content_type='application/json')

    def encounter(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id)

    def jobs_of(self, encounter_id):
        return list(models.Job.objects.filter(encounter_id=encounter_id).order_by('created_at', 'pk'))

    def kinds(self, encounter_id):
        return [job.kind for job in self.jobs_of(encounter_id)]

    def runs_of(self, encounter_id, provider=None, purpose=None):
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at', 'pk')
        if provider:
            runs = runs.filter(provider=provider)
        return list(runs.filter(purpose=purpose) if purpose else runs)

    def assessments(self, encounter_id):
        return list(models.Assessment.objects.filter(encounter_id=encounter_id).order_by('created_at', 'pk'))

    def records(self, assessment):
        return {record['name']: record for record in assessment.participants}

    def run_until(self, kind):
        """Run queued stages until one of ``kind`` is claimed; that job, claimed and not run."""
        while True:
            job = jobs.claim_next()
            if job is None:
                raise AssertionError(f'no {kind} stage was queued')
            if job.kind == kind:
                return job
            jobs.run_job(job)

    def sent(self, name, phase):
        return len(self.adapters[name].loops_of(phase))


# --- the chain --------------------------------------------------------------------------------------------------------

class ChainTests(Harness2Case):
    def test_both_phases_run_in_order_with_their_keys(self):
        encounter_id = self.create()
        drain()
        chain = self.jobs_of(encounter_id)
        self.assertEqual([j.kind for j in chain], ['extract', 'analyze', 'predict', 'astra', 'fable', 'assess',
                                                   'astra_peer', 'fable_peer', 'assess'])
        self.assertTrue(all(j.state == 'succeeded' for j in chain), [(j.kind, j.state, j.error) for j in chain])
        first, final = self.assessments(encounter_id)
        context, corti = self.encounter(encounter_id).current_context, self.runs_of(encounter_id, 'corti')[0]
        astra, fable = self.runs_of(encounter_id, 'astra', 'independent')[0], self.runs_of(encounter_id, 'fable')[0]
        phase1 = hashlib.sha256(f'{astra.pk},{fable.pk}'.encode()).hexdigest()[:12]
        self.assertEqual(chain[5].idempotency_key, f'assess:{context.pk}:{corti.pk}:p:{phase1}')  # exactly as before
        digest = hashlib.sha256(str(first.pk).encode()).hexdigest()[:12]
        self.assertEqual([j.idempotency_key for j in chain[6:8]], [f'astra_peer:{digest}', f'fable_peer:{digest}'])
        astra_peer = self.runs_of(encounter_id, 'astra', 'peer_review')[0]
        fable_peer = self.runs_of(encounter_id, 'fable', 'peer_review')[0]
        ids = ','.join(map(str, (astra.pk, fable.pk, astra_peer.pk, fable_peer.pk)))
        self.assertEqual(chain[8].idempotency_key,
                         f'assess:{context.pk}:{corti.pk}:q:{hashlib.sha256(ids.encode()).hexdigest()[:12]}')
        self.assertEqual({j.provider_run_id for j in chain[3:]}, {corti.pk})  # the Corti run travels on the chain
        self.assertEqual({j.context_id for j in chain[3:]}, {context.pk})
        self.assertEqual(self.encounter(encounter_id).current_assessment, final)
        self.assertEqual((jobs.assessment_phase(first), jobs.assessment_phase(final)), (1, 2))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')
        self.assertEqual(len(self.corti.requests), 1)
        self.assertEqual([(self.sent(n, 'first'), self.sent(n, 'peer')) for n in ('astra', 'fable')], [(1, 1), (1, 1)])
        for run in (astra_peer, fable_peer):
            self.assertEqual((run.state, run.sent, run.scope), ('succeeded', True,
                                                                {'mode': 'replay', 'assessment': str(first.pk)}))


# --- phase 1 on the tool loop (HARNESS.md 11.2, 12.1) -----------------------------------------------------------------

class PhaseOneLoopTests(Harness2Case):
    def setUp(self):
        super().setUp()
        self.adapters['fable'].first = [asks('fable', passages_call('toolu_fable_1', 'ncci_endoscopy_rules')),
                                        asks('fable', passages_call('toolu_fable_2', 'pfs_indicator_definitions',
                                                                    ['99213']), number=2),
                                        answered('fable', FABLE_READING, number=3)]

    def test_a_two_and_a_three_exchange_loop_are_recorded_exchange_by_exchange(self):
        encounter_id = self.create()
        drain()
        executor = tools.executor(self.ws)
        for name, calls in (('astra', [[facts_call('call_astra_1', ['99213'])], []]),
                            ('fable', [[passages_call('toolu_fable_1', 'ncci_endoscopy_rules')],
                                       [passages_call('toolu_fable_2', 'pfs_indicator_definitions', ['99213'])],
                                       []])):
            with self.subTest(name):
                run = self.runs_of(encounter_id, name, 'independent')[0]
                exchanges = list(run.exchanges.order_by('turn'))
                (loop_record,) = self.adapters[name].loops_of('first')
                self.assertEqual([e.turn for e in exchanges], list(range(1, len(calls) + 1)))
                self.assertEqual({e.state for e in exchanges}, {'succeeded'})
                # each exchange's stored request is what was posted, hashed as stored; the run holds the first request
                self.assertEqual([e.request_body for e in exchanges], loop_record['bodies'])
                self.assertEqual((exchanges[0].request_body, exchanges[0].request_sha256),
                                 (run.request_body, run.request_sha256))
                for exchange in exchanges:
                    self.assertEqual(exchange.request_sha256,
                                     hashlib.sha256(canonical_body(exchange.request_body)).hexdigest())
                    self.assertEqual(exchange.response_sha256, hashlib.sha256(bytes(exchange.response_bytes)).hexdigest())
                    self.assertEqual(exchange.provider_request_id, f'req_{name}_{exchange.turn}')
                    self.assertEqual(exchange.latency_ms, 10.0 + exchange.turn)
                    self.assertTrue(exchange.response_id)
                    self.assertIsNotNone(exchange.started_at)
                self.assertEqual(len({e.request_sha256 for e in exchanges}), len(exchanges))
                # the run's response is the final exchange's; its usage is summed over the exchanges
                self.assertEqual((bytes(run.response_bytes), run.response_sha256, run.response_id),
                                 (bytes(exchanges[-1].response_bytes), exchanges[-1].response_sha256,
                                  exchanges[-1].response_id))
                self.assertEqual((run.usage, run.usage_basis),
                                 (loop.summed_usage([e.usage for e in exchanges]), loop.LOOP_USAGE_BASIS))
                self.assertEqual((run.state, run.sent, run.endpoint, run.returned_model, run.requested_model),
                                 ('succeeded', True, LIVE_MODULES[name].ENDPOINT, MODELS[name], MODELS[name]))
                # one tool loop, given the loop deadline, the run identity and CPT Studio's own executor
                self.assertEqual((loop_record['deadline_s'], loop_record['client_request_id']), (540, str(run.run_identity)))
                self.assertEqual(loop_record['execute_tool'].__qualname__, 'executor.<locals>.execute_tool')
                # every tool call as the loop executed it: CPT Studio's executor's result and refs, exactly
                for exchange, asked in zip(exchanges, calls):
                    recorded = list(exchange.tool_calls.order_by('id'))
                    self.assertEqual([(c.call_id, c.tool, c.arguments) for c in recorded], asked)
                    for call in recorded:
                        result, refs = executor(call.tool, call.arguments)
                        self.assertEqual((call.result, call.refs), (result, refs))
                        self.assertEqual(call.result_sha256, hashlib.sha256(json.dumps(
                            result, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest())
                        self.assertIsNotNone(call.executed_at)
                        self.assertTrue(refs)
        self.assertEqual(models.ProviderExchange.objects.filter(run__encounter_id=encounter_id,
                                                                run__purpose='independent').count(), 5)

    def test_references_used_are_retrieved_only_from_the_run_s_own_tool_refs(self):
        self.adapters['fable'].first = [asks('fable', passages_call('toolu_fable_1', 'pfs_indicator_definitions')),
                                        answered('fable', FABLE_READING, number=2)]
        encounter_id = self.create()
        drain()
        astra, fable = self.runs_of(encounter_id, 'astra', 'independent')[0], self.runs_of(encounter_id, 'fable')[0]
        self.assertIn(f'fact:{PFS_KEY}:99213:status', jobs.run_refs(astra))
        self.assertNotIn(f'fact:{PFS_KEY}:99213:status', jobs.run_refs(fable))
        self.assertIn('status-A', jobs.run_refs(fable))
        used = {name: [(ref.ref, ref.retrieved) for ref in jobs.participant_reading(run)[0].references_used]
                for name, run in (('astra', astra), ('fable', fable))}
        self.assertEqual(used, {'astra': [(f'fact:{PFS_KEY}:99213:status', True), ('rule-01', False)],
                                # Astra retrieved the fact; Fable never did, so it is cited, not retrieved
                                'fable': [('status-A', True), (f'fact:{PFS_KEY}:99213:status', False)]})

    def test_an_adapter_that_raises_leaves_an_unknown_outcome_and_no_exchange(self):
        with mock.patch.object(self.adapters['astra'], 'send_loop', side_effect=RuntimeError('synthetic defect')), \
                self.assertLogs('studio.jobs', level='ERROR'):
            encounter_id = self.create()
            drain()
        astra = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((astra.state, astra.sent, astra.exchanges.count()), ('unknown', True, 0))
        self.assertEqual(astra.error, jobs.PARTICIPANT_RAISED_MESSAGE.format(label='Astra', error='RuntimeError'))
        self.assertEqual([r.scope.get('held') for r in self.runs_of(encounter_id, 'fable')], ['unknown_outcome'])
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')

    def test_an_outcome_that_cannot_be_recorded_whole_is_unknown(self):
        with mock.patch('studio.jobs._record_exchanges', side_effect=RuntimeError('synthetic')), \
                self.assertLogs('studio.jobs', level='ERROR'):
            encounter_id = self.create()
            jobs.run_job(self.run_until('astra'))
        astra = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((astra.state, astra.sent, astra.exchanges.count()), ('unknown', True, 0))
        self.assertEqual(astra.error, jobs.UNRECORDED_MESSAGE.format(label='Astra'))
        self.assertEqual(models.ToolCall.objects.filter(exchange__run=astra).count(), 0)

    def test_a_stage_with_no_time_left_for_a_whole_loop_reserves_and_sends_nothing(self):
        encounter_id = self.create()
        job = self.run_until('astra')
        job.started_at = timezone.now() - timedelta(seconds=60)
        with mock.patch('studio.jobs.time.sleep'):
            jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual((job.state, job.result), ('queued', {'requeued': jobs.LOOP_LATE_MESSAGE}))
        self.assertEqual((self.runs_of(encounter_id, 'astra'), self.adapters['astra'].loops), ([], []))
        drain()
        self.assertEqual(self.runs_of(encounter_id, 'astra')[0].state, 'succeeded')
        # the deadline of a phase-1 or peer job covers the loop and its recording, within the stale-stage bound
        from django.conf import settings
        for kind in ('astra', 'fable', 'astra_peer', 'fable_peer'):
            budget = min(settings.JOB_DEADLINE_SECONDS[kind], settings.STALE_RUNNING_SECONDS)
            self.assertLessEqual(settings.PARTICIPANT_LOOP_DEADLINE_SECONDS + jobs.LOOP_RECORDING_SECONDS, budget)

    def test_a_reuse_records_no_exchange_and_reads_with_the_runs_it_reuses(self):
        first = self.create()
        drain()
        second = self.create()  # the same text in the same workspace: the identical requests
        drain()
        self.assertEqual([(self.sent(n, 'first'), self.sent(n, 'peer')) for n in ('astra', 'fable')], [(1, 1), (1, 1)])
        records = {encounter_id: self.records(self.encounter(encounter_id).current_assessment)
                   for encounter_id in (first, second)}
        for name in ('astra', 'fable'):
            original, reused = self.runs_of(first, name, 'independent')[0], self.runs_of(second, name, 'independent')[0]
            self.assertEqual((reused.reused_from_id, reused.sent, reused.exchanges.count()), (original.pk, False, 0))
            self.assertEqual(jobs.loop_run(reused), original)
            self.assertEqual(jobs.run_refs(reused), jobs.run_refs(original))
            # read with the refs of the loop that answered: the same reading, so the same frozen sha256
            for key in ('reading_sha256', 'exchanges', 'tool_calls', 'state'):
                self.assertEqual(records[second][name][key], records[first][name][key])
            # the peer request repeats too (no open question here), so its answer is reused as well
            peer = self.runs_of(second, name, 'peer_review')[0]
            self.assertEqual((peer.reused_from_id, peer.sent, peer.state),
                             (self.runs_of(first, name, 'peer_review')[0].pk, False, 'succeeded'))
            self.assertEqual((peer.scope['assessment'], records[second][name]['peer_run']),
                             (str(self.assessments(second)[0].pk), str(peer.pk)))
        self.assertEqual(self.encounter(second).state, 'ready_for_review')


# --- what assess #1 and assess #2 record (HARNESS.md 12.3) ------------------------------------------------------------

class RecordsTests(Harness2Case):
    def test_assess_one_records_every_frozen_phase_one_output_and_assess_two_the_peer_reviews(self):
        encounter_id = self.create()
        drain()
        first, final = self.assessments(encounter_id)
        revision = self.encounter(encounter_id).current_revision
        corti = self.runs_of(encounter_id, 'corti')[0]
        runs = {name: self.runs_of(encounter_id, name, 'independent')[0] for name in ('astra', 'fable')}
        shas = {name: sha256_json(to_jsonable(jobs.participant_reading(run)[0])) for name, run in runs.items()}
        frozen = [['corti', corti.response_sha256], ['astra', shas['astra']], ['fable', shas['fable']],
                  ['revision', revision.text_sha256]]
        for assessment in (first, final):
            records = self.records(assessment)
            for name, counts in (('astra', (2, 1)), ('fable', (2, 1))):
                record = records[name]
                self.assertEqual((record['state'], record['run'], record['reading_sha256']),
                                 ('read', str(runs[name].pk), shas[name]))
                self.assertEqual((record['exchanges'], record['tool_calls']), counts)
                self.assertEqual(record['frozen'], frozen)  # identical in every entry of one assessment
        self.assertTrue(all('peer_state' not in record for record in first.participants))
        peers = {name: self.runs_of(encounter_id, name, 'peer_review')[0] for name in ('astra', 'fable')}
        for name, record in self.records(final).items():
            review_ = jobs.peer_reading(peers[name])[0]
            self.assertIsInstance(review_, PeerReview)
            self.assertEqual({key: record[key] for key in ('peer_state', 'peer_run', 'peer_reason', 'peer_sha256',
                                                           'peer_unverified_quotes')},
                             {'peer_state': 'read', 'peer_run': str(peers[name].pk), 'peer_reason': '',
                              'peer_sha256': sha256_json(to_jsonable(review_)), 'peer_unverified_quotes': 0})
            self.assertEqual(review_.frozen_inputs[-1][0], 'revision')
        self.assertEqual((jobs.assessment_phase(first), jobs.assessment_phase(final)), (1, 2))


# --- the peer stages' gating (HARNESS.md 12.1) ------------------------------------------------------------------------

class PeerGatingTests(Harness2Case):
    def test_a_participant_whose_first_reading_was_not_read_gets_no_peer_stage(self):
        self.adapters['astra'].first = [failed()]
        encounter_id = self.create()
        drain()
        self.assertEqual(self.kinds(encounter_id)[3:], ['astra', 'fable', 'assess', 'fable_peer', 'assess'])
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (0, 1))
        record = self.records(self.encounter(encounter_id).current_assessment)['astra']
        self.assertEqual((record['state'], record['peer_state'], record['peer_run'], record['peer_reason']),
                         ('failed', 'not_run', None, jobs.PEER_FIRST_NOT_READ))
        self.assertEqual(self.runs_of(encounter_id, 'astra', 'peer_review'), [])
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')  # I10: never provider_failed

    def test_no_first_reading_read_means_no_peer_review_and_assess_one_is_final(self):
        self.adapters['astra'].first = self.adapters['fable'].first = [failed()]
        encounter_id = self.create()
        drain()
        self.assertEqual(self.kinds(encounter_id)[-3:], ['astra', 'fable', 'assess'])
        (only,) = self.assessments(encounter_id)
        self.assertEqual(jobs.assessment_phase(only), 1)
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (0, 0))

    def test_a_peer_stage_waits_while_a_phase_one_run_has_not_finished(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        fable = self.runs_of(encounter_id, 'fable', 'independent')[0]
        pending = models.ProviderRun.objects.create(
            encounter=fable.encounter, revision=fable.revision, provider='fable', adapter_version=fable.adapter_version,
            request_sha256=fable.request_sha256, request_body=fable.request_body, contexts=fable.contexts,
            state=models.ProviderRun.SENDING, purpose='independent', scope={'mode': 'replay'})
        with mock.patch('studio.jobs.time.sleep'):
            jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual((job.state, job.result), ('queued', {'requeued': jobs.PEER_WAITS}))
        self.assertEqual(self.sent('astra', 'peer'), 0)
        # settled as a reservation that never reached the send, it is no outcome: the peer stage runs
        models.ProviderRun.objects.filter(pk=pending.pk).update(state=models.ProviderRun.NOT_SENT)
        drain()
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (1, 1))
        self.assertEqual(jobs.assessment_phase(self.encounter(encounter_id).current_assessment), 2)

    def test_a_newer_assessment_leaves_the_peer_stage_not_run_and_queues_nothing(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        first = self.encounter(encounter_id).current_assessment
        newer = models.Assessment.objects.create(**{
            field: getattr(first, field) for field in (
                'encounter', 'revision', 'context', 'routing', 'provider_run', 'second_run', 'profiles_version',
                'engine_version', 'reference_sources', 'encounter_checks', 'unsupported', 'summary', 'services',
                'completeness', 'participants', 'retrieval', 'sha256')})
        jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual((job.state, job.result),
                         ('succeeded', {'peer': 'astra_peer', 'state': 'not_run', 'reason': jobs.PEER_NEWER}))
        self.assertIsNone(jobs.claim_next())  # the newer chain owns the revision: nothing more is queued
        self.assertEqual((self.sent('astra', 'peer'), self.runs_of(encounter_id, purpose='peer_review')), (0, []))
        self.assertEqual(self.assessments(encounter_id)[-1], newer)

    def test_a_peer_stage_whose_first_assessment_read_other_phase_one_runs_is_not_run(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        fable = self.runs_of(encounter_id, 'fable', 'independent')[0]
        models.ProviderRun.objects.create(  # a newer phase-1 outcome that assess #1 never read
            encounter=fable.encounter, revision=fable.revision, provider='fable', adapter_version=fable.adapter_version,
            request_sha256=fable.request_sha256, request_body=fable.request_body, contexts=fable.contexts,
            state=models.ProviderRun.FAILED, sent=True, purpose='independent', scope={'mode': 'replay'},
            started_at=timezone.now(), finished_at=timezone.now())
        jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.result, {'peer': 'astra_peer', 'state': 'not_run', 'reason': jobs.PEER_MOVED})
        self.assertIsNone(jobs.claim_next())

    def test_nothing_is_sent_for_phase_two_while_a_member_date_conflict_holds(self):
        encounter_id = self.create()
        drain()
        before = len(self.jobs_of(encounter_id))
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-22'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        # the hold is recorded and the assess reads the participants' frozen readings - and queues no peer review
        self.assertEqual([j.kind for j in self.jobs_of(encounter_id)[before:]], ['assess'])
        self.assertEqual([(self.sent(n, 'first'), self.sent(n, 'peer')) for n in ('astra', 'fable')], [(1, 1), (1, 1)])
        records = self.records(self.encounter(encounter_id).current_assessment)
        self.assertEqual((records['astra']['state'], 'peer_state' in records['astra']), ('read', False))
