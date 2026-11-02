"""harness@2 part B's pipeline (HARNESS.md 11, 12.1-12.5; I1, I5, I8, I9, I10): phase 1 on the tool loop with its
exchanges and tool calls, assess #1's records, the peer stages and their gating, assess #2, the re-assessment after a
confirmation, and the stale sweep, Stop, Resume and reconcile across phase 2.

Synthetic data only; nothing is sent. Corti is the harness@1 suite's in-process fake. Astra and Fable are the real
replay adapters (studio.participants.replay: their requests are built and their answers read by the live adapters' own
code) whose tool loop is the real loop (studio.participants.loop) with the live vendor halves; each exchange is answered
by a script instead of a recording, so a test decides what each turn asks for. Their tool calls are answered by CPT
Studio's real CMS tool executor (studio.reference.tools) over a synthetic reference store and the bundled passages.
"""
import dataclasses
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
from tests.support import docgen
from tests.support import factories as f
from tests.test_harness_pipeline import BOTH, TIME_QUOTE, ScriptedCorti, _WorkerDied
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
                    self.assertEqual(exchange.response_sha256,
                                     hashlib.sha256(bytes(exchange.response_bytes)).hexdigest())
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
                self.assertEqual((loop_record['deadline_s'], loop_record['client_request_id']),
                                 (540, str(run.run_identity)))
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

    def test_a_pdf_upload_hands_its_original_to_the_loop_and_none_to_the_peer_review(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.corti.selections = []  # a PDF's extracted text wraps lines: Corti's fake proposes nothing here
        pdf = docgen.make_pdf([OFFICE_NOTE.replace('\n', ' ')[:900]])
        with tempfile.TemporaryDirectory() as store, override_settings(ORIGINALS_DIR=store):
            response = self.client.post('/api/encounters', {'file': SimpleUploadedFile('synthetic-note.pdf', pdf),
                                                            'synthetic_attestation': 'yes'})
            self.assertEqual(response.status_code, 201, response.content)
            encounter_id = response.json()['id']
            drain()
        source = models.SourceFile.objects.get(encounter_id=encounter_id)
        for name in ('astra', 'fable'):
            (first,), (peer,) = self.adapters[name].loops_of('first'), self.adapters[name].loops_of('peer')
            self.assertEqual((first['original'], peer['original']), (hashlib.sha256(pdf).hexdigest(), None))
            run = self.runs_of(encounter_id, name, 'independent')[0]
            self.assertIn(source.sha256, json.dumps(run.request_body))  # named by sha256, never its bytes
            self.assertNotIn('%PDF', json.dumps(run.request_body))
            self.assertNotIn('$original_sha256', json.dumps(self.runs_of(encounter_id, name, 'peer_review')[0]
                                                            .request_body))
        self.assertEqual(jobs.assessment_phase(self.encounter(encounter_id).current_assessment), 2)

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


    def test_a_peer_review_s_references_are_checked_against_its_own_loop_only(self):
        self.adapters['astra'].peer = [
            asks('astra', passages_call('call_peer_1', 'ncci_endoscopy_rules'), number=3),
            answered('astra', peer_answer(references=[('rule-01', 'Retrieved in this peer review.'),
                                                      (f'fact:{PFS_KEY}:99213:status',
                                                       'Retrieved in the first reading, not in this review.')]),
                     number=4)]
        encounter_id = self.create()
        drain()
        peer = self.runs_of(encounter_id, 'astra', 'peer_review')[0]
        self.assertEqual([(e.turn, [c.tool for c in e.tool_calls.all()]) for e in peer.exchanges.order_by('turn')],
                         [(1, ['cms_policy_passages']), (2, [])])
        review_ = jobs.peer_reading(peer)[0]
        self.assertEqual([(ref.ref, ref.retrieved) for ref in review_.references_used],
                         [('rule-01', True), (f'fact:{PFS_KEY}:99213:status', False)])
        record = self.records(self.encounter(encounter_id).current_assessment)['astra']
        self.assertEqual(record['peer_sha256'], sha256_json(to_jsonable(review_)))


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


# --- what a peer request shows, and what assess #2 reads (HARNESS.md 12.1, 12.4, 12.5) -------------------------------

ASTRA_COLON = reading(codes=[('45385', SNARE), ('45380', BIOPSY)], services=[('c1', 'colonoscopy', 'performed', SNARE)])
FABLE_COLON = reading(codes=[('45385', SNARE)], services=[('c1', 'colonoscopy', 'performed', SNARE)])
CPT_STUDIO = "== CPT Studio's rule-based reading - it can be wrong =="


def open_questions(name, body):
    return document_sections(peer_document(name, body))[CPT_STUDIO]['open_questions']


def answers_extent(name, number=2):
    """A peer review answering the open extent question of proposal sel:0 with the landmark passage."""
    def answer(body):
        question = next(q for q in open_questions(name, body) if q['proposal_key'] == 'sel:0')
        return answered(name, peer_answer(answers=[(question['question_id'], True, 'cecum', LAND)],
                                          positions=[('45380', 'supports', BIOPSY)]), number)
    return answer


class ColonCase(Harness2Case):
    corti_codes = (('45385', SNARE), ('45380', BIOPSY))

    def setUp(self):
        super().setUp()
        self.adapters['astra'].first = [answered('astra', ASTRA_COLON)]
        self.adapters['fable'].first = [answered('fable', FABLE_COLON)]
        self.adapters['astra'].peer = [answers_extent('astra')]
        self.adapters['fable'].peer = [answered('fable', peer_answer(codes=[('45378', LAND)]), number=2)]

    def confirm(self, encounter_id, assessment, key, value='cecum', passage=LAND, fact='extent', scope='proposal'):
        """A reviewer's confirmation as the confirmation endpoint records it (HARNESS.md 12.5)."""
        revision = self.encounter(encounter_id).current_revision
        clarification = assessment.clarifications.filter(proposal__key=key).first() or assessment.clarifications.first()
        start = revision.text.index(passage)
        return models.FindingConfirmation.objects.create(
            encounter_id=encounter_id, revision=revision, clarification=clarification, scope=scope, fact=fact,
            family='' if scope == 'encounter' else 'gi.colonoscopy', proposal_key=key if scope == 'proposal' else '',
            value=value, spans=[{'start': start, 'end': start + len(passage), 'text': passage, 'page': None}],
            located_by=['astra'], runs=[], confirmed_by=self.reviewer,
            attestation=f'I read this passage in the source document; it documents {value} for this encounter.')

    def proposal(self, assessment, key):
        return assessment.proposals.get(key=key)


class PeerRequestTests(ColonCase):
    def test_the_peer_request_shows_exactly_the_frozen_inputs(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        first, final = self.assessments(encounter_id)
        records = self.records(first)
        questions = [{'question_id': str(c.pk), 'scope': c.scope, 'fact': c.fact, 'family': c.family,
                      'proposal_key': c.proposal.key if c.proposal_id else '', 'question': c.question,
                      'reason': c.reason} for c in first.clarifications.order_by('created_at', 'pk')]
        self.assertEqual([(q['proposal_key'], q['fact']) for q in questions],
                         [('sel:0', 'extent'), ('sel:1', 'extent')])
        held = [{'key': p.key, 'code': p.code, 'status': p.status,
                 'reasons': [c['detail'] for c in p.checks if c['status'] != 'pass']}
                for p in first.proposals.filter(status='needs_clarification').order_by('position')]
        self.assertEqual([h['code'] for h in held], ['45385', '45380'])
        cpt_studio = {'open_questions': questions, 'held': held, 'excluded': []}
        readings = {name: jobs.participant_reading(self.runs_of(encounter_id, name, 'independent')[0])[0]
                    for name in ('astra', 'fable')}
        for name, other in (('astra', 'fable'), ('fable', 'astra')):
            with self.subTest(name):
                run = self.runs_of(encounter_id, name, 'peer_review')[0]
                document = peer_document(name, run.request_body)
                sections = document_sections(document)
                self.assertEqual(sections['== Your frozen first reading =='], prompt.reading_answer(readings[name]))
                self.assertEqual(sections['corti (another coding system):'],
                                 {'codes': [{'code': '45385', 'modifiers': [], 'units': 1, 'evidence': [SNARE]},
                                            {'code': '45380', 'modifiers': [], 'units': 1, 'evidence': [BIOPSY]}]})
                self.assertEqual(sections[f'{other} (another model):'], prompt.reading_answer(readings[other]))
                self.assertEqual(sections[CPT_STUDIO], cpt_studio)
                frozen = records[name]['frozen'] + [['cpt_studio', sha256_json(cpt_studio)]]
                self.assertEqual(prompt.peer_document_inputs(document),
                                 (tuple(q['question_id'] for q in questions),
                                  tuple(sorted((n, s) for n, s in frozen))))
                # what was shown is recorded with the review, and it never carries Corti's own wording (I9)
                review_ = jobs.peer_reading(run)[0]
                self.assertEqual(review_.frozen_inputs, tuple(sorted((n, s) for n, s in frozen)))
                stored = json.dumps(run.request_body)
                self.assertNotIn(CORTI_DISPLAY, stored)
                self.assertNotIn('"display"', stored)
                self.assertNotIn('$original_sha256', stored)  # a peer review attaches no original file
                self.assertEqual(run.contexts, [TWO_EXTENTS])
        # the frozen list: Corti's response, both readings and the revision text
        corti = self.runs_of(encounter_id, 'corti')[0]
        self.assertEqual([n for n, _ in records['astra']['frozen']], ['corti', 'astra', 'fable', 'revision'])
        self.assertEqual(records['astra']['frozen'][0], ['corti', corti.response_sha256])
        self.assertEqual(final.participants[0]['frozen'], records['astra']['frozen'])

    def test_corti_is_shown_only_its_exact_passages_of_the_document(self):
        real = self.corti.send

        def send(request, *, deadline_s):
            exchange = real(request, deadline_s=deadline_s)
            answer = json.loads(exchange.response_bytes)
            line = request.contexts[1]
            answer['codes'][0]['evidences'] += [  # CPT Studio's own date line, and a passage that is not the text's
                {'contextIndex': 1, 'start': 0, 'end': len(line), 'text': line},
                {'contextIndex': 0, 'start': 0, 'end': 9, 'text': 'Not text.'}]
            data = json.dumps(answer).encode()
            return dataclasses.replace(exchange, response_bytes=data, response_sha256=hashlib.sha256(data).hexdigest())
        with mock.patch.object(self.corti, 'send', side_effect=send):
            encounter_id = self.create(TWO_EXTENTS)
            drain()
        run = self.runs_of(encounter_id, 'astra', 'peer_review')[0]
        shown = document_sections(peer_document('astra', run.request_body))['corti (another coding system):']
        self.assertEqual([(item['code'], item['evidence']) for item in shown['codes']],
                         [('45385', [SNARE]), ('45380', [BIOPSY])])
        self.assertNotIn('Date of service: 2026-10-14', json.dumps(shown))

    def test_assess_two_reads_the_peer_reviews_and_a_code_proposed_after_peer_review_keeps_its_phase(self):
        seen = []
        real = jobs.prefetched_lookup

        def recording(codes):
            seen.append(tuple(codes))
            return real(codes)
        with mock.patch('studio.jobs.prefetched_lookup', side_effect=recording):
            encounter_id = self.create(TWO_EXTENTS)
            drain()
        self.assertEqual(seen, [('45380', '45385'), ('45378', '45380', '45385')])  # assess #2 adds Fable's code
        final = self.encounter(encounter_id).current_assessment
        added = final.proposals.get(code='45378')
        self.assertEqual((added.support.get('origin'), added.support.get('phases')),
                         ('participant', {'fable': 'peer_review'}))
        self.assertIn('Fable after peer review', added.rationale)
        self.assertIn('Corti did not propose this code', added.rationale)
        summary = next(c for c in final.encounter_checks if c['id'] == 'participants.summary')
        self.assertIn('In peer review', summary['detail'])
        # a peer review's answer is never itself a confirmation: sel:0 stays held until a reviewer confirms (11.3)
        self.assertEqual(self.proposal(final, 'sel:0').status, 'needs_clarification')

    def test_assess_two_reads_the_revision_s_confirmations_and_never_the_date_s(self):
        encounter_id = self.create(TWO_EXTENTS)
        job = self.run_until('astra_peer')
        first = self.encounter(encounter_id).current_assessment
        confirmation = self.confirm(encounter_id, first, 'sel:0')
        self.confirm(encounter_id, first, '', value='2026-10-14', passage='Date of service: 2026-10-14',
                     fact='service_date', scope='encounter')
        revision = self.encounter(encounter_id).current_revision
        (finding,) = jobs.confirmed_findings(revision)  # the service date's enters through the context, never here
        self.assertEqual((finding.fact, finding.proposal_key, finding.value, finding.confirmation_id,
                          finding.located_by, finding.confirmed_by),
                         ('extent', 'sel:0', 'cecum', str(confirmation.pk), ('astra',), self.reviewer.label()))
        self.assertTrue(finding.evidence[0].exact)
        jobs.run_job(job)
        drain()
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual(jobs.assessment_phase(final), 2)
        item = self.proposal(final, 'sel:0')
        self.assertEqual((item.code, item.status, item.support['confirmed']),
                         ('45385', 'ready', [str(confirmation.pk)]))
        ids = [c['id'] for c in final.encounter_checks]
        self.assertIn('confirmations.applied', ids)
        self.assertNotIn('confirmations.ignored', ids)  # the date's confirmation was never given to the engine
        self.assertEqual(self.proposal(final, 'sel:1').status, 'needs_clarification')  # another question: untouched


# --- the re-assessment after a confirmation (HARNESS.md 12.1, 12.5) ---------------------------------------------------

class ReassessTests(ColonCase):
    def test_it_reads_what_the_final_assessment_read_plus_the_confirmations_and_sends_nothing(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        final = self.encounter(encounter_id).current_assessment
        made = models.Job.objects.get(encounter_id=encounter_id, kind='assess', result__assessment=str(final.pk))
        runs, loops = models.ProviderRun.objects.count(), [len(a.loops) for a in self.adapters.values()]
        confirmation = self.confirm(encounter_id, final, 'sel:0')
        job = jobs.reassess_after_confirmation(self.encounter(encounter_id), self.reviewer)
        digest = hashlib.sha256(str(confirmation.pk).encode()).hexdigest()[:12]
        self.assertEqual((job.kind, job.idempotency_key, job.context_id, job.provider_run_id),
                         ('assess', f'{made.idempotency_key}:c:{digest}', final.context_id, final.provider_run_id))
        drain()
        again = self.encounter(encounter_id).current_assessment
        self.assertNotEqual(again, final)
        self.assertEqual((models.ProviderRun.objects.count(), [len(a.loops) for a in self.adapters.values()],
                          len(self.corti.requests)), (runs, loops, 1))  # nothing is sent
        self.assertEqual(self.kinds(encounter_id)[-1], 'assess')  # and no peer review is queued
        item = self.proposal(again, 'sel:0')
        self.assertEqual((item.status, item.support['confirmed']), ('ready', [str(confirmation.pk)]))
        before, after = self.records(final), self.records(again)
        for name in ('astra', 'fable'):
            for key in ('state', 'run', 'reading_sha256', 'peer_state', 'peer_run', 'peer_sha256'):
                self.assertEqual(after[name][key], before[name][key])
            self.assertNotIn('frozen', after[name])  # HARNESS.md 12.3: on assess #1 and #2 only
        self.assertEqual(jobs.assessment_phase(again), 2)
        # the same confirmations queue one assess
        self.assertEqual(jobs.reassess_after_confirmation(self.encounter(encounter_id), self.reviewer), job)
        # a second confirmation: the earlier ':c:' part is left off, so the key never grows with each one
        second = self.confirm(encounter_id, again, 'sel:1')
        later = jobs.reassess_after_confirmation(self.encounter(encounter_id), self.reviewer)
        both = hashlib.sha256(','.join(sorted([str(confirmation.pk), str(second.pk)])).encode()).hexdigest()[:12]
        self.assertEqual(later.idempotency_key, f'{made.idempotency_key}:c:{both}')
        drain()
        self.assertEqual({p.key: p.status for p in self.encounter(encounter_id).current_assessment.proposals.all()
                          if p.key in ('sel:0', 'sel:1')}, {'sel:0': 'ready', 'sel:1': 'ready'})

    def test_a_confirmation_is_read_by_every_later_assessment_of_the_revision_assess_one_included(self):
        """Every assessment of the revision with a participant configured reads its confirmations - assess #1 too, the
        current assessment while phase 2 runs (decisions are carried or invalidated against it): one that did not would
        hold the confirmed code again after any later context change."""
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        confirmation = self.confirm(encounter_id, self.encounter(encounter_id).current_assessment, 'sel:0')
        jobs.reassess_after_confirmation(self.encounter(encounter_id), self.reviewer)
        drain()
        before = len(self.assessments(encounter_id))
        response = self.post(f'/api/encounters/{encounter_id}/context', {'billing_context': 'professional'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        later = self.assessments(encounter_id)[before:]
        self.assertEqual([jobs.assessment_phase(a) for a in later], [1, 2])  # a new assess #1, then its assess #2
        for assessment in later:
            item = self.proposal(assessment, 'sel:0')
            self.assertEqual((item.code, item.status, item.support['confirmed']),
                             ('45385', 'ready', [str(confirmation.pk)]))
            self.assertIn('confirmations.applied', [c['id'] for c in assessment.encounter_checks])
        # the new peer requests show the question answered: only sel:1's is open
        peers = self.runs_of(encounter_id, 'astra', 'peer_review')
        self.assertEqual([q['proposal_key'] for q in open_questions('astra', peers[-1].request_body)], ['sel:1'])

    def test_it_is_refused_while_busy_and_without_a_finished_final_assessment(self):
        encounter_id = self.create(TWO_EXTENTS)
        with self.assertRaisesMessage(jobs.Refused, jobs.REASSESS_BUSY):
            jobs.reassess_after_confirmation(self.encounter(encounter_id), self.reviewer)
        drain()
        final = self.encounter(encounter_id).current_assessment
        models.Job.objects.filter(result__assessment=str(final.pk)).update(result={})
        with self.assertRaisesMessage(jobs.Refused, jobs.REASSESS_UNFINISHED):
            jobs.reassess_after_confirmation(self.encounter(encounter_id), self.reviewer)
        other = self.create(TWO_EXTENTS)
        models.Job.objects.filter(encounter_id=other).update(state='cancelled')
        with self.assertRaisesMessage(jobs.Refused, jobs.REASSESS_NONE):
            jobs.reassess_after_confirmation(self.encounter(other), self.reviewer)


# --- the send doors in phase 2: unknown outcomes, failures, reuse, I10 ------------------------------------------------

class PeerSendDoorTests(Harness2Case):
    def test_an_unknown_peer_outcome_blocks_every_later_send_and_reconcile_runs_phase_two_again(self):
        self.adapters['astra'].peer_loops = [[unknown()]]
        encounter_id = self.create()
        drain()
        astra = self.runs_of(encounter_id, 'astra', 'peer_review')
        fable = self.runs_of(encounter_id, 'fable', 'peer_review')
        self.assertEqual([(r.state, r.sent) for r in astra], [('unknown', True)])
        self.assertEqual([(r.state, r.sent, r.scope.get('held'), r.error) for r in fable],
                         [('not_sent', False, 'unknown_outcome', jobs.PARTICIPANT_BLOCKED_MESSAGE)])
        self.assertEqual(self.sent('fable', 'peer'), 0)
        records = self.records(self.encounter(encounter_id).current_assessment)
        self.assertEqual((records['astra']['peer_state'], records['fable']['peer_state']), ('unknown', 'blocked'))
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(astra[0].pk), 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        # Corti's and the participants' first requests are answered and reused; phase 2 runs for the new phase-1 set
        self.assertEqual((len(self.corti.requests), self.sent('astra', 'first'), self.sent('fable', 'first')),
                         (1, 1, 1))
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (2, 1))
        records = self.records(self.encounter(encounter_id).current_assessment)
        self.assertEqual((records['astra']['peer_state'], records['fable']['peer_state']), ('read', 'read'))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')
        reconciled = models.AuditEvent.objects.get(encounter_id=encounter_id, event='provider.reconciled')
        self.assertEqual(reconciled.data, {'run': str(astra[0].pk), 'provider': 'astra'})

    def test_a_peer_request_that_failed_is_never_sent_again_and_an_answered_one_is_reused(self):
        self.adapters['astra'].peer_loops = [[failed()]]
        encounter_id = self.create()
        drain()
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')  # I10: never provider_failed
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual(len(self.assessments(encounter_id)), 4)  # a new assess #1 and its own peer chain
        astra = self.runs_of(encounter_id, 'astra', 'peer_review')
        fable = self.runs_of(encounter_id, 'fable', 'peer_review')
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (1, 1))
        self.assertEqual([r.state for r in astra], ['failed', 'not_sent'])
        self.assertTrue(astra[1].error.startswith(jobs.FAILED_BEFORE_MESSAGE))
        self.assertEqual((astra[1].request_sha256, astra[1].purpose), (astra[0].request_sha256, 'peer_review'))
        self.assertEqual([(r.reused_from_id, r.request_sha256) for r in fable[1:]],
                         [(fable[0].pk, fable[0].request_sha256)])
        records = self.records(self.encounter(encounter_id).current_assessment)
        self.assertEqual((records['astra']['peer_state'], records['fable']['peer_state']), ('not_sent', 'read'))

    def test_one_participant_failing_in_phase_two_blocks_only_itself(self):
        self.adapters['astra'].peer = [failed()]
        encounter_id = self.create()
        drain()
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (1, 1))
        record = self.records(self.encounter(encounter_id).current_assessment)
        self.assertEqual((record['astra']['peer_state'], record['astra']['peer_reason'], record['fable']['peer_state']),
                         ('failed', 'Overloaded (synthetic).', 'read'))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_peer_request_that_cannot_be_built_is_recorded_not_sent_and_blocks_only_itself(self):
        with mock.patch.object(self.adapters['astra'], 'build_peer_request', side_effect=ValueError('synthetic')), \
                self.assertLogs('studio.jobs', level='ERROR'):
            encounter_id = self.create()
            drain()
        (astra,) = self.runs_of(encounter_id, 'astra', 'peer_review')
        self.assertEqual((astra.state, astra.sent, astra.request_sha256, astra.started_at),
                         ('not_sent', False, '', None))
        self.assertEqual(astra.error, jobs.PEER_UNBUILT.format(error='ValueError'))
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (0, 1))
        record = self.records(self.encounter(encounter_id).current_assessment)
        self.assertEqual((record['astra']['peer_state'], record['fable']['peer_state']), ('not_sent', 'read'))

    def test_a_frozen_reading_that_no_longer_reads_back_is_never_shown(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        real = jobs.participant_reading

        def changed(run):
            reading, problem = real(run)
            if run.provider == 'astra' and reading is not None:
                return dataclasses.replace(reading, unverified_quotes=reading.unverified_quotes + 1), problem
            return reading, problem
        with mock.patch('studio.jobs.participant_reading', side_effect=changed):
            jobs.run_job(job)
            drain()
        # Astra's own request and Fable's, which shows Astra's reading, would no longer show what was frozen
        runs = {name: self.runs_of(encounter_id, name, 'peer_review') for name in ('astra', 'fable')}
        self.assertEqual({name: [(r.state, r.error) for r in found] for name, found in runs.items()},
                         {name: [('not_sent', jobs.PEER_FROZEN_CHANGED)] for name in runs})
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (0, 0))
        self.assertEqual(jobs.assessment_phase(self.encounter(encounter_id).current_assessment), 2)

    def test_a_participant_disabled_since_its_peer_stage_was_queued_records_nothing(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        with override_settings(ASTRA_MODE='disabled'):
            jobs.run_job(job)
            job.refresh_from_db()
            self.assertEqual(job.result, {'peer': 'astra_peer', 'state': 'disabled', 'run': None})
            drain()
        self.assertEqual((self.runs_of(encounter_id, 'astra', 'peer_review'), self.sent('fable', 'peer')), ([], 1))
        self.assertEqual(self.kinds(encounter_id)[-2:], ['fable_peer', 'assess'])

    def test_the_live_gate_refuses_a_live_peer_review_and_only_it(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        self.adapters['astra'].mode = 'live'
        with override_settings(AUTHORIZATION_REF=''):
            jobs.run_job(job)
        (astra,) = self.runs_of(encounter_id, 'astra', 'peer_review')
        self.assertEqual((astra.state, astra.sent, astra.scope['mode']), ('not_sent', False, 'live'))
        self.assertEqual(astra.error, 'Nothing was sent: Live provider calls are not authorized on this installation.')
        self.adapters['astra'].mode = 'replay'
        drain()
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (0, 1))

    def test_a_peer_review_another_model_answered_is_refused_and_never_read(self):
        envelope = json.loads(answered('fable', EMPTY_PEER, number=2))
        envelope['model'] = 'claude-other-model'
        self.adapters['fable'].peer = [json.dumps(envelope).encode()]
        encounter_id = self.create()
        drain()
        record = self.records(self.encounter(encounter_id).current_assessment)['fable']
        self.assertEqual(record['peer_state'], 'refused')
        self.assertIn('not claude-fable-5-1', record['peer_reason'])
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')


# --- the stale sweep, Stop, Resume, reconcile and the upgrade across phase 2 (HARNESS.md 12.1) -----------------------

class SweepStopResumeTests(Harness2Case):
    def age(self, job):
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))

    def test_a_peer_stage_whose_outcome_was_recorded_is_settled_and_the_chain_goes_on(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        real = audit.record

        def dies_after_the_outcome(workspace, event, **kwargs):
            real(workspace, event, **kwargs)
            if event == 'provider.finished':
                raise _WorkerDied()
        with mock.patch('studio.jobs.audit.record', side_effect=dies_after_the_outcome):
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        self.age(job)
        jobs.mark_stale()
        job.refresh_from_db()
        peer = self.runs_of(encounter_id, 'astra', 'peer_review')[0]
        self.assertEqual((job.state, job.result['peer'], job.result['state'], job.result['run']),
                         ('succeeded', 'astra_peer', 'succeeded', str(peer.pk)))
        self.assertEqual(peer.exchanges.count(), 1)  # recorded with the outcome, before the worker died
        queued = self.jobs_of(encounter_id)[-1]
        self.assertEqual((queued.kind, queued.idempotency_key),
                         ('fable_peer', 'fable_peer:' + job.idempotency_key.split(':')[1]))
        drain()
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (1, 1))
        self.assertEqual(jobs.assessment_phase(self.encounter(encounter_id).current_assessment), 2)
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_peer_stage_left_mid_send_is_unknown_and_reconcile_runs_phase_two_again(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        with mock.patch.object(self.adapters['astra'], 'send_loop', side_effect=_WorkerDied()):
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        self.age(job)
        jobs.mark_stale()
        job.refresh_from_db()
        peer = self.runs_of(encounter_id, 'astra', 'peer_review')[0]
        self.assertEqual((job.state, peer.state, peer.exchanges.count()), ('unknown', 'unknown', 0))
        self.assertIsNone(jobs.claim_next())  # a send in flight settles nothing further: it is reconciled first
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(peer.pk), 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual((self.sent('astra', 'first'), self.sent('astra', 'peer'), self.sent('fable', 'peer')),
                         (1, 1, 1))  # the reconciled request again, once; Fable for the first time
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_peer_stage_that_died_with_its_run_only_reserved_is_resumable(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        with mock.patch('studio.jobs.is_stopped', side_effect=_WorkerDied()):  # dies right after reserving
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        self.age(job)
        jobs.mark_stale()
        job.refresh_from_db()
        swept = self.runs_of(encounter_id, 'astra', 'peer_review')[0]
        self.assertEqual((job.state, swept.state, swept.started_at), ('cancelled', 'not_sent', None))
        self.assertEqual(self.encounter(encounter_id).state, 'stopped')
        response = self.client.post(f'/api/encounters/{encounter_id}/resume')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json(), {'resumed': 'astra_peer'})
        resumed = self.jobs_of(encounter_id)[-1]
        self.assertTrue(resumed.idempotency_key.startswith(f'{job.idempotency_key}:resume:'))
        drain()
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (1, 1))
        # the swept reservation is no outcome: assess #2 reads the run the resumed stage sent
        final = self.encounter(encounter_id).current_assessment
        self.assertEqual(self.records(final)['astra']['peer_run'],
                         str(self.runs_of(encounter_id, 'astra', 'peer_review')[1].pk))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_stop_before_the_peer_stages_and_resume_runs_phase_two_once(self):
        encounter_id = self.create()
        job = self.run_until('assess')
        jobs.run_job(job)  # assess #1: the first peer stage is queued
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        self.assertEqual(self.jobs_of(encounter_id)[-1].kind, 'astra_peer')
        self.assertEqual((self.jobs_of(encounter_id)[-1].state, self.encounter(encounter_id).state),
                         ('cancelled', 'stopped'))
        self.assertEqual(self.sent('astra', 'peer'), 0)
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (1, 1))
        self.assertEqual(jobs.assessment_phase(self.encounter(encounter_id).current_assessment), 2)
        # Stop and Resume again while assess #2 waits
        other = self.create()
        jobs.run_job(self.run_until('fable_peer'))
        self.assertEqual(self.client.post(f'/api/encounters/{other}/stop').status_code, 200)
        drain()
        self.assertEqual((self.jobs_of(other)[-1].kind, self.jobs_of(other)[-1].state), ('assess', 'cancelled'))
        self.assertEqual(self.client.post(f'/api/encounters/{other}/resume').status_code, 201)
        drain()
        final = self.encounter(other).current_assessment
        self.assertEqual((jobs.assessment_phase(final), self.encounter(other).state), (2, 'ready_for_review'))
        self.assertIn(':q:', self.jobs_of(other)[-1].idempotency_key)

    def test_a_stop_observed_before_the_peer_sends_cancels_it_and_resume_sends_once(self):
        encounter_id = self.create()
        job = self.run_until('astra_peer')
        models.Job.objects.filter(pk=job.pk).update(stop_requested_at=timezone.now())
        jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.state, 'cancelled')
        self.assertEqual([r.state for r in self.runs_of(encounter_id, 'astra', 'peer_review')], ['cancelled'])
        self.assertEqual(self.sent('astra', 'peer'), 0)
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (1, 1))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_reconcile_runs_phase_two_for_the_new_phase_one_set(self):
        self.adapters['astra'].first_loops = [[unknown()]]
        encounter_id = self.create()
        drain()
        # Astra's outcome is unknown and Fable was blocked: no first reading was read, so there is no phase 2
        records = self.records(self.encounter(encounter_id).current_assessment)
        self.assertEqual((records['astra']['state'], records['fable']['state']), ('unknown', 'blocked'))
        self.assertEqual(self.runs_of(encounter_id, purpose='peer_review'), [])
        astra = self.runs_of(encounter_id, 'astra', 'independent')[0]
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(astra.pk), 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual(self.kinds(encounter_id)[-7:], ['predict', 'astra', 'fable', 'assess', 'astra_peer',
                                                         'fable_peer', 'assess'])
        self.assertEqual((len(self.corti.requests), self.sent('astra', 'first'), self.sent('fable', 'first')),
                         (1, 2, 1))
        final = self.encounter(encounter_id).current_assessment
        new_set = {name: str(self.runs_of(encounter_id, name, 'independent')[-1].pk) for name in ('astra', 'fable')}
        self.assertEqual({name: record['run'] for name, record in self.records(final).items()}, new_set)
        self.assertEqual({name: record['peer_state'] for name, record in self.records(final).items()},
                         {'astra': 'read', 'fable': 'read'})
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_an_assess_a_remake_queued_marks_its_peer_stages_which_stop_where_they_would_send(self):
        earlier = jobs.EARLIER_CONTEXT_VERSIONS[-1]
        labels = {'CONTEXT_VERSION': earlier, 'EARLIER_CONTEXT_VERSIONS': jobs.EARLIER_CONTEXT_VERSIONS[:-1]}
        encounter_id = self.create()
        with mock.patch.multiple(jobs, **labels):  # recorded by the installed rules, its assess queued, then the swap
            for kind in ('extract', 'analyze', 'predict', 'astra', 'fable'):
                job = jobs.claim_next()
                self.assertEqual(job.kind, kind)
                jobs.run_job(job)
        self.assertEqual(self.encounter(encounter_id).current_context.version, earlier)
        drain()
        chain = self.jobs_of(encounter_id)
        self.assertEqual([(j.kind, j.state) for j in chain[-3:]],
                         [('assess', 'succeeded'), ('assess', 'succeeded'), ('astra_peer', 'cancelled')])
        self.assertTrue(chain[-2].idempotency_key.endswith(jobs.UPGRADE_MARK))
        self.assertTrue(chain[-1].idempotency_key.endswith(jobs.UPGRADE_MARK))
        self.assertEqual(chain[-1].error, jobs.PEER_UPGRADE_MESSAGE.format(label='Astra'))
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (0, 0))  # nobody asked for it
        self.assertEqual(self.encounter(encounter_id).state, 'stopped')
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()  # a member's Resume sends, and the chain it continues is a member's
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (1, 1))
        self.assertFalse(self.jobs_of(encounter_id)[-2].idempotency_key.endswith(jobs.UPGRADE_MARK))
        self.assertEqual(jobs.assessment_phase(self.encounter(encounter_id).current_assessment), 2)


class PeerRunLookupTests(Harness2Case):
    def test_assess_two_reads_only_the_peer_runs_made_for_its_assess_one(self):
        encounter_id = self.create()
        drain()
        first, final = self.assessments(encounter_id)
        revision = self.encounter(encounter_id).current_revision
        made = self.runs_of(encounter_id, 'astra', 'peer_review')[0]
        self.assertEqual(jobs._peer_run(revision, 'astra', first), made)
        # a newer peer run made for another assessment is never this assess #1's
        models.ProviderRun.objects.create(
            encounter=made.encounter, revision=revision, provider='astra', adapter_version=made.adapter_version,
            request_sha256=made.request_sha256, request_body=made.request_body, contexts=made.contexts,
            state=models.ProviderRun.FAILED, sent=True, purpose='peer_review',
            scope={'mode': 'replay', 'assessment': str(final.pk)}, started_at=timezone.now(),
            finished_at=timezone.now())
        self.assertEqual(jobs._peer_run(revision, 'astra', first), made)
        self.assertEqual(jobs._final_key(first), self.jobs_of(encounter_id)[-1].idempotency_key)


class UpgradeChainTests(ColonCase):
    def test_the_upgrade_s_chain_carries_its_mark_to_the_peer_stages(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        sent = (len(self.corti.requests), self.sent('astra', 'first'), self.sent('fable', 'first'),
                self.sent('astra', 'peer'), self.sent('fable', 'peer'))
        encounter = self.encounter(encounter_id)
        jobs.enqueue(models.Job.PREDICT, encounter=encounter, revision=encounter.current_revision,
                     context=encounter.current_context, key=jobs._upgrade_predict_key(encounter.current_context),
                     requested_by=self.reviewer)
        drain()
        chain = self.jobs_of(encounter_id)[-5:]
        # every first answer is retained and reused; the new assess #1 asks new questions, so the peer request is new
        self.assertEqual([(j.kind, j.state) for j in chain], [('predict', 'succeeded'), ('astra', 'succeeded'),
                                                              ('fable', 'succeeded'), ('assess', 'succeeded'),
                                                              ('astra_peer', 'cancelled')])
        self.assertTrue(chain[-1].idempotency_key.endswith(jobs.UPGRADE_MARK))
        self.assertEqual(chain[-1].error, jobs.PEER_UPGRADE_MESSAGE.format(label='Astra'))
        self.assertEqual((len(self.corti.requests), self.sent('astra', 'first'), self.sent('fable', 'first'),
                          self.sent('astra', 'peer'), self.sent('fable', 'peer')), sent)
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual((self.sent('astra', 'peer'), self.sent('fable', 'peer')), (sent[3] + 1, sent[4] + 1))


# --- I1: no model participant configured ------------------------------------------------------------------------------

REAL_ENGINE = jobs.run_assessment


def engine_refusing_harness(**kwargs):
    """The real engine, failing the assess if it is ever given the participants or the confirmations (I1)."""
    for keyword in ('participants', 'confirmed'):
        if keyword in kwargs:
            raise AssertionError(f'the engine was given {keyword} with no participant configured')
    return REAL_ENGINE(**kwargs)


class CortiOnlyTests(Harness2Case):
    """I1: with Astra and Fable disabled, nothing of harness@2 runs - no peer stage, no second assess, no exchange, no
    new record key - and the engine is never given the revision's confirmations."""

    def test_nothing_of_harness_two_runs_and_confirmations_are_never_read(self):
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled'), \
                mock.patch('studio.jobs.run_assessment', side_effect=engine_refusing_harness):
            encounter_id = self.create()
            drain()
            encounter = self.encounter(encounter_id)
            context, corti = encounter.current_context, self.runs_of(encounter_id)[0]
            self.assertEqual([(j.kind, j.idempotency_key) for j in self.jobs_of(encounter_id)],
                             [('extract', f'extract:{encounter.current_revision_id}'),
                              ('analyze', f'analyze:{encounter.current_revision_id}'),
                              ('predict', f'predict:{context.pk}'), ('assess', f'assess:{context.pk}:{corti.pk}')])
            (assessment,) = self.assessments(encounter_id)
            self.assertEqual(assessment.participants, [jobs.not_configured_record('astra'),
                                                       jobs.not_configured_record('fable')])
            self.assertEqual(jobs.assessment_phase(assessment), 0)
            self.assertEqual((models.ProviderExchange.objects.count(), models.ToolCall.objects.count()), (0, 0))
            # a confirmation recorded for the revision (as when the participants were configured) is never read
            clarification = models.Clarification.objects.create(
                encounter=encounter, assessment=assessment, scope='service', family='gi.office_em', fact='em_basis',
                question='Synthetic question.', reason='Synthetic reason.')
            start = encounter.current_revision.text.index(TIME_QUOTE)
            models.FindingConfirmation.objects.create(
                encounter=encounter, revision=encounter.current_revision, clarification=clarification, scope='service',
                fact='em_basis', family='gi.office_em', value='total time: 24 minutes',
                spans=[{'start': start, 'end': start + len(TIME_QUOTE), 'text': TIME_QUOTE, 'page': None}],
                located_by=['fable'], confirmed_by=self.reviewer, attestation='Synthetic attestation.')
            response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
            self.assertEqual(response.status_code, 201, response.content)
            drain()
            again, last = self.encounter(encounter_id).current_assessment, self.jobs_of(encounter_id)[-1]
            self.assertEqual((last.kind, last.state, last.idempotency_key),
                             ('assess', 'succeeded', f'assess:{again.context_id}:{corti.pk}'))
            self.assertNotEqual((again.pk, again.context_id), (assessment.pk, assessment.context_id))
            self.assertEqual(again.participants, assessment.participants)
            self.assertNotIn('confirmations', again.completeness)
            self.assertFalse(any(c['id'].startswith('confirmations.') for c in again.encounter_checks))
        self.assertEqual(self.adapters['astra'].loops + self.adapters['fable'].loops, [])
