"""The harness pipeline (HARNESS.md 2, 5-6; I1, I8, I10): the participants' stages, their runs, the assess that reads
them, and the records it keeps beside the engine's result.

Synthetic data only. Corti and the participants are in-process fakes - no network, no credentials. The engine's own
handling of the participants belongs to the engine package: these tests call the real engine through a wrapper that
notes what it was given, and with no participant configured they call it untouched.
"""
import dataclasses
import hashlib
import json
import sys
import types
from datetime import date, timedelta
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from studio import audit, jobs, models, review, storage
from studio.gi import detect as gi_detect
from studio.participants import prompt
from studio.providers.base import ProviderUnavailable, canonical_body
from studio.reference.store import prefetched_lookup, selected_codes
from studio.types import (EvidenceSpan, LocatedQuote, PageSpan, ParticipantCode, ParticipantNotCoded,
                          ParticipantReading, ProviderRequest, RawExchange, RoutingResult, from_jsonable, sha256_json)
from studio.validation import engine
from tests.support import docgen
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain
from tests.test_repairs_pipeline import LIVE, RECONCILE_NOTE

TIME_QUOTE = 'Total time on the date of the encounter was 24 minutes.'
PLAN_QUOTE = 'A colonoscopy is scheduled for 2026-12-01.'
MODELS = {'astra': 'gpt-6-astra', 'fable': 'claude-fable-5-1'}
ENDPOINTS = {'astra': 'https://api.openai.com/v1/responses', 'fable': 'https://api.anthropic.com/v1/messages'}
BOTH = dict(ASTRA_MODE='replay', FABLE_MODE='replay')
REAL_ENGINE = jobs.run_assessment


class _WorkerDied(BaseException):
    """Stands in for a SIGKILL: run_job records an Exception, never a BaseException."""


class ScriptedCorti(FakeProvider):
    """Corti's fake (tests.test_pipeline_api.FakeProvider) with scripted outcomes; it records every request it sends."""

    def __init__(self, *args, outcomes=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes, self.requests = list(outcomes), []

    def send(self, request, *, deadline_s):
        self.requests.append(request)
        saved, self.outcome = self.outcome, (self.outcomes.pop(0) if self.outcomes else self.outcome)
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.outcome = saved


class FakeParticipant:
    """Stands in for a harness adapter (studio.participants.Participant): builds its request from the revision alone,
    through the real framing, and 'sends' to an in-process stub that records each call. ``codes`` and ``not_coded`` are
    what its answer proposes: (code, quote) and (code, reason, quote)."""

    def __init__(self, name, *, mode='replay', codes=(), not_coded=(), outcome='succeeded', refused=False,
                 model=None, adapter_version=None):
        self.name, self.mode = name, mode
        self.adapter_version = adapter_version or f'{name}-test@1'
        self.requested_model, self.endpoint = MODELS[name], ENDPOINTS[name]
        self.codes, self.not_coded, self.refused = list(codes), list(not_coded), refused
        self.returned_model = model or MODELS[name]
        self.outcome, self.outcomes = outcome, []
        self.built, self.sent = [], []

    def build_request(self, text, pages, kind, original):
        self.built.append((kind, original))
        framed = prompt.framed_document(text, pages, kind)
        if framed is None:
            raise ProviderUnavailable('The document could not be framed; nothing was sent.')
        body = {'model': self.requested_model, 'instructions': prompt.INSTRUCTIONS, 'input': framed,
                'original': original}
        return ProviderRequest(provider=self.name, adapter_version=self.adapter_version, body=body,
                               canonical_sha256=hashlib.sha256(canonical_body(body)).hexdigest(), contexts=(text,))

    def send(self, request, *, deadline_s, client_request_id, original_bytes):
        outcome = self.outcomes.pop(0) if self.outcomes else self.outcome
        self.sent.append({'request': request.canonical_sha256, 'client_request_id': client_request_id,
                          'deadline_s': deadline_s,
                          'original': hashlib.sha256(original_bytes).hexdigest() if original_bytes else None})
        identity = {'endpoint': self.endpoint, 'requested_model': self.requested_model}
        if outcome == 'unknown':
            return RawExchange(outcome='unknown', sent=True, error='Read timed out after the request was sent '
                                                                   '(synthetic).', **identity)
        if outcome == 'failed':
            data = b'{"error": {"type": "overloaded_error"}}'
            return RawExchange(outcome='failed', sent=True, http_status=529, response_bytes=data,
                               response_sha256=hashlib.sha256(data).hexdigest(), error='Overloaded (synthetic).',
                               provider_request_id='req_synthetic_failed', **identity)
        answer = {'model': self.returned_model, 'refused': self.refused,
                  'codes': [{'code': code, 'quote': quote} for code, quote in self.codes],
                  'not_coded': [{'code': code, 'reason': reason, 'quote': quote}
                                for code, reason, quote in self.not_coded]}
        data = json.dumps(answer, sort_keys=True).encode()
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=21.5,
                           usage={'input_tokens': 1200, 'output_tokens': 300}, usage_basis='vendor_reported_tokens',
                           provider_request_id=f'req_{self.name}_{len(self.sent)}', returned_model=self.returned_model,
                           response_id=f'resp_{self.name}_{len(self.sent)}', **identity)


def locate(quote, text):
    spans, start = [], text.find(quote)
    while start >= 0 and len(spans) < 8 and len(quote) >= 8:
        spans.append(EvidenceSpan(0, start, start + len(quote), quote, True))
        start = text.find(quote, start + 1)
    return LocatedQuote(quote=quote, spans=tuple(spans), reason='' if spans else 'not found in the document')


def fake_reader(provider, adapter_version):
    """studio.participants.reader_for's stand-in: reads a FakeParticipant's answer, locating each quote in the request's
    text (context 0), and refuses a reading whose answer says so."""
    def read(request, data):
        answer = json.loads(data)
        text = request.contexts[0]
        codes = tuple(ParticipantCode(code=c['code'], evidence=(locate(c['quote'], text),)) for c in answer['codes'])
        not_coded = tuple(ParticipantNotCoded(code=n['code'], reason=n['reason'], evidence=(locate(n['quote'], text),))
                          for n in answer['not_coded'])
        quotes = [q for item in codes + not_coded for q in item.evidence]
        refused = bool(answer['refused']) or answer['model'] != MODELS[provider]
        problems = (('The vendor refused the request.',) if answer['refused'] else
                    (f'Answered by {answer["model"]}, not {MODELS[provider]}.',) if refused else ())
        return ParticipantReading(
            provider=provider, adapter_version=adapter_version, reading_version=prompt.READING_VERSION,
            requested_model=MODELS[provider], returned_model=answer['model'], codes=() if refused else codes,
            not_coded=() if refused else not_coded, problems=problems, refused=refused,
            unverified_quotes=0 if refused else sum(1 for q in quotes if not q.spans))
    return read


def recording_engine(**kwargs):
    """The real engine, called without the participants (handled by the engine package); what it was given is noted in
    the result's summary, so a test reads it across the bounded child's fork."""
    given = kwargs.pop('participants', None)
    result = REAL_ENGINE(**kwargs)
    if given is None:
        return result
    seen = [[item.provider, item.state, sorted({c.code for c in item.reading.codes}) if item.reading else [],
             item.reason] for item in given]
    return dataclasses.replace(result, summary={**result.summary, 'participants_given': seen})


def engine_refusing_participants(**kwargs):
    """The real engine, failing the assess if it is ever given the participants' keyword (I1)."""
    if 'participants' in kwargs:
        raise AssertionError('the engine was given participants with none configured')
    return REAL_ENGINE(**kwargs)


def fake_passages(recorded):
    """A stand-in for studio.reference.passages: retrieve() reads the lookup it is given (the assess stage's prefetched
    one, which raises for any code it did not prefetch) and returns one trace per code; ``recorded`` keeps each call."""
    module = types.ModuleType('studio.reference.passages')

    def load_passages():
        return ('synthetic-passage-set',)

    def retrieve(codes, service_date, lookup, passages):
        recorded.append((list(codes), service_date, passages))
        out = []
        for code in codes:
            ref = lookup.lookup(code, service_date)
            out.append({'code': code, 'service_date': service_date.isoformat() if service_date else None,
                        'facts': [{'source_key': 'cms-pfs-test', 'release': 'RVU26D',
                                   'effective': ['2026-10-01', '2026-12-31'], 'sha256': '0' * 64,
                                   'field': 'status', 'value': (ref.pfs or {}).get('status', '')}],
                        'passages': [{'source_key': 'cms-ncci-manual-test', 'release': 'Revision 1/1/2026',
                                      'passage_key': 'vi-c-1', 'section': 'Chapter VI §C', 'page': '12',
                                      'topic': 'pfs.mult_proc', 'topic_value': '3', 'sha256': '1' * 64,
                                      'text': 'Synthetic passage text for the test.'}],
                        'lookups': [f'{code}: prefetched'], 'notes': []})
        return out
    module.load_passages, module.retrieve = load_passages, retrieve
    return module


@override_settings(**LIVE)
class HarnessCase(TestCase):
    """Corti is ScriptedCorti; the participants' adapters are FakeParticipants (configured by the settings' modes); the
    engine is called through recording_engine."""
    astra_codes = (('99213', TIME_QUOTE), ('99214', 'not anywhere in the note at all'))
    fable_codes = (('99213', TIME_QUOTE),)

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.corti = ScriptedCorti(selections=[('99213', TIME_QUOTE)])
        self.adapters = {'astra': FakeParticipant('astra', codes=self.astra_codes),
                         'fable': FakeParticipant('fable', codes=self.fable_codes)}
        from studio import participants

        def adapter(name):
            return None if participants.participant_mode(name) == 'disabled' else self.adapters[name]
        for target, kwargs in (('studio.jobs.get_provider', {'return_value': self.corti}),
                               ('studio.participants.get_participant', {'side_effect': adapter}),
                               ('studio.participants.reader_for', {'side_effect': fake_reader}),
                               ('studio.jobs.run_assessment', {'side_effect': recording_engine})):
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
        return list(models.Job.objects.filter(encounter_id=encounter_id).order_by('created_at'))

    def runs_of(self, encounter_id, provider=None):
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at')
        return list(runs.filter(provider=provider) if provider else runs)

    def records(self, encounter_id):
        assessment = self.encounter(encounter_id).current_assessment
        return {record['name']: record for record in assessment.participants}


# --- I1: no participant configured -----------------------------------------------------------------------------------

@override_settings(**LIVE)
class CortiOnlyParityTests(HarnessCase):
    """I1: with Astra and Fable disabled, the stages, their keys, the rows and the assessment's sha256 are as before;
    the only additions are the run columns and the assessment's participants ('not configured') and retrieval."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch('studio.jobs.run_assessment', side_effect=engine_refusing_participants)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_stages_keys_rows_and_sha256_are_corti_only(self):
        encounter_id = self.create()
        drain()
        encounter = self.encounter(encounter_id)
        revision, context = encounter.current_revision, encounter.current_context
        corti = self.runs_of(encounter_id)
        self.assertEqual(len(corti), 1)
        run = corti[0]
        self.assertEqual([(j.kind, j.idempotency_key, j.state) for j in self.jobs_of(encounter_id)],
                         [('extract', f'extract:{revision.pk}', 'succeeded'),
                          ('analyze', f'analyze:{revision.pk}', 'succeeded'),
                          ('predict', f'predict:{context.pk}', 'succeeded'),
                          ('assess', f'assess:{context.pk}:{run.pk}', 'succeeded')])
        self.assertEqual(self.adapters['astra'].sent + self.adapters['fable'].sent, [])
        self.assertEqual((run.purpose, run.scope, run.endpoint, run.requested_model, run.returned_model,
                          run.response_id, run.provider, run.state),
                         ('primary', {}, '', '', '', '', 'corti', 'succeeded'))
        assessment = encounter.current_assessment
        self.assertEqual(assessment.provider_run_id, run.pk)
        # the engine's result, recomputed from the same inputs exactly as the round-4 head called it: same sha256
        provider_status, normalized = jobs._provider_inputs(run)
        service_date = jobs.context_service_date(context)
        reference = prefetched_lookup(tuple(sorted(set(selected_codes(normalized)))))
        routing = from_jsonable(RoutingResult, jobs.to_jsonable(gi_detect.route(revision.text, service_date)))
        result = engine.assess(text=revision.text, pages=tuple(PageSpan(**p) for p in revision.pages),
                               context=jobs.context_facts(context), routing=routing, normalized=normalized,
                               reference=reference, service_date=service_date, provider_status=provider_status,
                               extraction_status=revision.extraction_status,
                               extraction_messages=tuple(revision.messages), second=None, second_scope=None)
        self.assertEqual(assessment.sha256, sha256_json(result))
        self.assertEqual([p.code for p in assessment.proposals.all()], ['99213'])
        # the records beside the result: both participants 'not configured', no retrieval module, no retrieval
        self.assertEqual([(r['name'], r['state'], r['run']) for r in assessment.participants],
                         [('astra', 'not_configured', None), ('fable', 'not_configured', None)])
        self.assertEqual(assessment.retrieval, [])
        # Corti's audit rows are as before: no provider named on its 'provider.finished' row
        finished = models.AuditEvent.objects.get(encounter_id=encounter_id, event='provider.finished')
        self.assertEqual(set(finished.data), {'run', 'state', 'http_status', 'usage', 'latency_ms', 'purpose'})
        sending = models.AuditEvent.objects.get(encounter_id=encounter_id, event='provider.sending')
        self.assertEqual(set(sending.data), {'run', 'provider', 'mode', 'request_sha256', 'run_identity', 'purpose'})
        # the whole trail and every row the round-4 head records for this encounter, and nothing more
        self.assertEqual([e.event for e in models.AuditEvent.objects.filter(encounter_id=encounter_id)
                          .order_by('created_at', 'pk')],
                         ['encounter.created', 'revision.extracted', 'provider.sending', 'provider.finished',
                          'assessment.created'])
        self.assertEqual((models.Job.objects.filter(encounter_id=encounter_id).count(),
                          models.ProviderRun.objects.filter(encounter_id=encounter_id).count(),
                          models.Assessment.objects.filter(encounter_id=encounter_id).count(),
                          models.RoutingRun.objects.filter(revision=revision).count(),
                          models.EncounterContext.objects.filter(encounter_id=encounter_id).count()),
                         (4, 1, 1, 1, 1))
        self.assertEqual(encounter.state, 'ready_for_review')

    def test_a_context_change_that_keeps_the_request_queues_todays_assess_key(self):
        encounter_id = self.create()
        drain()
        run = self.runs_of(encounter_id)[0]
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertEqual(response.status_code, 201, response.content)
        context = self.encounter(encounter_id).current_context
        self.assertEqual(self.jobs_of(encounter_id)[-1].idempotency_key, f'assess:{context.pk}:{run.pk}')
        drain()
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_swept_predict_queues_todays_assess_key(self):
        encounter_id = self.create()
        jobs.run_job(jobs.claim_next())  # extract
        jobs.run_job(jobs.claim_next())  # analyze
        job = jobs.claim_next()
        real = audit.record

        def dies_after_the_outcome(workspace, event, **kwargs):
            real(workspace, event, **kwargs)
            if event == 'provider.finished':
                raise _WorkerDied()
        with mock.patch('studio.jobs.audit.record', side_effect=dies_after_the_outcome):
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))
        jobs.mark_stale()
        run = self.runs_of(encounter_id)[0]
        self.assertEqual(self.jobs_of(encounter_id)[-1].idempotency_key, f'assess:{job.context_id}:{run.pk}')

    def test_a_reconciliation_keeps_todays_keys_and_audit_rows(self):
        self.corti.outcomes = ['unknown']
        encounter_id = self.create()
        drain()
        unknown = self.runs_of(encounter_id)[0]
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(unknown.pk), 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        context, sent = self.encounter(encounter_id).current_context, self.runs_of(encounter_id)[1]
        self.assertEqual([j.idempotency_key for j in self.jobs_of(encounter_id)[-2:]],
                         [f'predict:{context.pk}:after-reconcile:{unknown.pk}', f'assess:{context.pk}:{sent.pk}'])
        reconciled = models.AuditEvent.objects.get(encounter_id=encounter_id, event='provider.reconciled')
        self.assertEqual(reconciled.data, {'run': str(unknown.pk)})  # Corti's row names no provider, as before
        summaries = [row['summary'] for row in self.client.get(f'/api/encounters/{encounter_id}').json()['activity']]
        self.assertIn('Unknown provider outcome reconciled', summaries)

    def test_a_held_encounter_and_a_second_review_keep_todays_assess_keys(self):
        held = self.create(service_date='2026-10-22')  # the note documents 2026-10-20: a member conflict
        drain()
        hold = self.runs_of(held)[0]
        self.assertEqual(self.jobs_of(held)[-1].idempotency_key,
                         f'assess:{self.encounter(held).current_context_id}:{hold.pk}')
        from tests.test_services_second_review import REPORT, TwoPassProvider, ask

        corti = TwoPassProvider(first=[('45385', 'was removed with a cold snare')],
                                later=[('45380', 'was sampled with cold biopsy forceps'),
                                       ('45385', 'was removed with a cold snare')])
        with mock.patch('studio.jobs.get_provider', return_value=corti):
            encounter_id = self.create(REPORT)
            drain()
            self.assertEqual(ask(self.client, encounter_id).status_code, 201)
            drain()
        primary, second = self.runs_of(encounter_id)
        self.assertEqual((primary.purpose, second.purpose), ('primary', 'second_review'))
        context = self.encounter(encounter_id).current_context
        self.assertEqual(self.jobs_of(encounter_id)[-1].idempotency_key,
                         f'assess:{context.pk}:{primary.pk}:review2:{second.pk}')
        self.assertEqual(self.encounter(encounter_id).current_assessment.second_run_id, second.pk)


# --- the chain --------------------------------------------------------------------------------------------------------

@override_settings(**LIVE, **BOTH)
class ChainTests(HarnessCase):
    def test_predict_then_astra_then_fable_then_assess(self):
        encounter_id = self.create()
        drain()
        encounter = self.encounter(encounter_id)
        context, corti = encounter.current_context, self.runs_of(encounter_id, 'corti')[0]
        chain = self.jobs_of(encounter_id)
        self.assertEqual([j.kind for j in chain], ['extract', 'analyze', 'predict', 'astra', 'fable', 'assess'])
        self.assertTrue(all(j.state == 'succeeded' for j in chain), [(j.kind, j.state, j.error) for j in chain])
        predict = chain[2]
        digest = hashlib.sha256(f'assess:{context.pk}:{corti.pk}|{predict.pk}'.encode()).hexdigest()[:32]
        self.assertEqual([j.idempotency_key for j in chain[3:5]], [f'astra:{digest}', f'fable:{digest}'])
        self.assertEqual({j.provider_run_id for j in chain[3:]}, {corti.pk})  # the Corti run travels on the chain
        astra, fable = self.runs_of(encounter_id, 'astra')[0], self.runs_of(encounter_id, 'fable')[0]
        ids = hashlib.sha256(f'{astra.pk},{fable.pk}'.encode()).hexdigest()[:12]
        self.assertEqual(chain[5].idempotency_key, f'assess:{context.pk}:{corti.pk}:p:{ids}')
        # each participant sent once, with its run's identity as the client request id and the participant's deadline
        for adapter, run in ((self.adapters['astra'], astra), (self.adapters['fable'], fable)):
            self.assertEqual(adapter.built, [('paste', None)])
            self.assertEqual(adapter.sent, [{'request': run.request_sha256, 'client_request_id': str(run.run_identity),
                                             'deadline_s': 330, 'original': None}])
            self.assertEqual((run.purpose, run.service_date, run.state, run.sent, run.scope),
                             ('independent', None, 'succeeded', True, {'mode': 'replay'}))
            self.assertEqual((run.endpoint, run.requested_model, run.returned_model),
                             (adapter.endpoint, adapter.requested_model, adapter.requested_model))
            self.assertTrue(run.response_id.startswith('resp_') and run.provider_request_id.startswith('req_'))
        self.assertEqual(len(self.corti.requests), 1)
        # the request is the revision alone: no title, member value or CPT Studio reading in it (I5)
        self.assertNotIn(encounter.title, json.dumps(astra.request_body))
        assessment = encounter.current_assessment
        self.assertEqual(assessment.summary['participants_given'],
                         [['astra', 'read', ['99213', '99214'], ''], ['fable', 'read', ['99213'], '']])
        records = self.records(encounter_id)
        self.assertEqual((records['astra']['state'], records['astra']['run'], records['astra']['unverified_quotes']),
                         ('read', str(astra.pk), 1))
        self.assertEqual(records['astra']['codes'], [{'code': '99213', 'quote': TIME_QUOTE},
                                                     {'code': '99214', 'quote': ''}])
        self.assertEqual((records['fable']['requested_model'], records['fable']['returned_model']),
                         ('claude-fable-5-1', 'claude-fable-5-1'))
        self.assertEqual(encounter.state, 'ready_for_review')
        summaries = [row['summary'] for row in self.client.get(f'/api/encounters/{encounter_id}').json()['activity']]
        self.assertIn('Astra request started', summaries)
        self.assertIn('Fable response recorded', summaries)
        self.assertIn('Provider response recorded', summaries)  # Corti's, as before

    def test_a_disabled_participant_is_skipped_and_recorded_as_not_configured(self):
        with override_settings(FABLE_MODE='disabled'):
            encounter_id = self.create()
            drain()
            self.assertEqual([j.kind for j in self.jobs_of(encounter_id)],
                             ['extract', 'analyze', 'predict', 'astra', 'assess'])
            self.assertEqual(self.adapters['fable'].sent, [])
            records = self.records(encounter_id)
            self.assertEqual((records['astra']['state'], records['fable']['state']), ('read', 'not_configured'))
            self.assertEqual(self.encounter(encounter_id).current_assessment.summary['participants_given'][0][:2],
                             ['astra', 'read'])

    def test_a_participant_disabled_after_its_stage_was_queued_records_nothing_and_the_chain_goes_on(self):
        encounter_id = self.create()
        for _ in range(3):
            jobs.run_job(jobs.claim_next())  # extract, analyze, predict: the Astra stage is queued
        with override_settings(ASTRA_MODE='disabled'):
            drain()
        self.assertEqual([j.kind for j in self.jobs_of(encounter_id)][-3:], ['astra', 'fable', 'assess'])
        self.assertEqual(self.jobs_of(encounter_id)[3].result, {'participant': 'astra', 'state': 'disabled'})
        self.assertEqual(self.runs_of(encounter_id, 'astra'), [])
        self.assertEqual(len(self.adapters['fable'].sent), 1)

    def test_an_unavailable_participant_blocks_only_itself(self):
        # I10: its request cannot be built (e.g. no credentials) - a not-sent run with why; Corti and Fable run
        with mock.patch.object(self.adapters['astra'], 'build_request',
                               side_effect=ProviderUnavailable('Astra needs CPT_STUDIO_OPENAI_CREDENTIALS_FILE.')):
            encounter_id = self.create()
            drain()
        astra = self.runs_of(encounter_id, 'astra')
        self.assertEqual([(r.state, r.request_sha256, r.error) for r in astra],
                         [('not_sent', '', 'Astra needs CPT_STUDIO_OPENAI_CREDENTIALS_FILE.')])
        self.assertEqual(len(self.adapters['fable'].sent), 1)
        records = self.records(encounter_id)
        self.assertEqual((records['astra']['state'], records['astra']['reason'], records['fable']['state']),
                         ('not_sent', 'Astra needs CPT_STUDIO_OPENAI_CREDENTIALS_FILE.', 'read'))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_misconfigured_participant_is_recorded_not_sent(self):
        from studio import participants

        def misconfigured(name):
            if name == 'astra':
                raise ProviderUnavailable('Live Astra needs CPT_STUDIO_OPENAI_CREDENTIALS_FILE.')
            return self.adapters[name] if participants.participant_mode(name) != 'disabled' else None
        with mock.patch('studio.participants.get_participant', side_effect=misconfigured):
            encounter_id = self.create()
            drain()
        run = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((run.state, run.adapter_version, run.scope, run.started_at),
                         ('not_sent', '', {'mode': 'replay'}, None))
        self.assertEqual(self.records(encounter_id)['astra']['state'], 'not_sent')
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_participant_failure_never_makes_the_encounter_provider_failed(self):
        self.adapters['astra'].outcome = 'failed'
        encounter_id = self.create()
        drain()
        astra = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((astra.state, astra.http_status), ('failed', 529))
        self.assertEqual(self.records(encounter_id)['astra']['state'], 'failed')
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')  # I10, never provider_failed
        self.assertEqual(len(self.adapters['fable'].sent), 1)

    def test_a_refused_reading_is_recorded_refused_and_never_read(self):
        self.adapters['fable'].returned_model = 'claude-other-model'  # I6: another model answered
        encounter_id = self.create()
        drain()
        record = self.records(encounter_id)['fable']
        self.assertEqual((record['state'], record['codes'], record['returned_model']),
                         ('refused', [], 'claude-other-model'))
        self.assertIn('not claude-fable-5-1', record['reason'])
        given = self.encounter(encounter_id).current_assessment.summary['participants_given']
        self.assertEqual(given[1][:3], ['fable', 'refused', []])

    def test_the_live_gate_refuses_a_live_participant_and_only_it(self):
        self.adapters['astra'].mode = 'live'
        with override_settings(AUTHORIZATION_REF=''), mock.patch('studio.jobs.get_provider', return_value=None):
            encounter_id = self.create()
            drain()
        run = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((run.state, run.sent), ('not_sent', False))
        self.assertEqual(run.error, 'Nothing was sent: Live provider calls are not authorized on this installation.')
        self.assertEqual(self.adapters['astra'].sent, [])
        self.assertEqual(len(self.adapters['fable'].sent), 1)  # Fable (replay) still runs (I10)
        self.assertEqual(self.encounter(encounter_id).current_assessment.provider_run, None)

    def test_corti_disabled_still_runs_the_participants(self):
        with mock.patch('studio.jobs.get_provider', return_value=None):
            encounter_id = self.create()
            drain()
        chain = self.jobs_of(encounter_id)
        self.assertEqual([j.kind for j in chain], ['extract', 'analyze', 'predict', 'astra', 'fable', 'assess'])
        self.assertIsNone(chain[-1].provider_run_id)
        self.assertTrue(chain[-1].idempotency_key.startswith(f'assess:{chain[2].context_id}:no-provider:p:'))
        self.assertEqual(self.encounter(encounter_id).state, 'provider_not_run')
        self.assertEqual(self.records(encounter_id)['astra']['state'], 'read')

    def test_a_second_review_s_assess_reads_the_participants_as_they_are(self):
        from tests.test_services_second_review import REPORT, TwoPassProvider, ask

        corti = TwoPassProvider(first=[('45385', 'was removed with a cold snare')],
                                later=[('45380', 'was sampled with cold biopsy forceps'),
                                       ('45385', 'was removed with a cold snare')])
        self.adapters['astra'].codes = self.adapters['fable'].codes = []
        with mock.patch('studio.jobs.get_provider', return_value=corti):
            encounter_id = self.create(REPORT)
            drain()
            self.assertEqual(ask(self.client, encounter_id).status_code, 201)
            drain()
        primary = self.runs_of(encounter_id, 'corti')[0]
        second = models.ProviderRun.objects.get(encounter_id=encounter_id, purpose='second_review')
        astra, fable = self.runs_of(encounter_id, 'astra'), self.runs_of(encounter_id, 'fable')
        self.assertEqual((len(astra), len(fable)), (1, 1))  # the second review is Corti's own: nothing else is sent
        ids = hashlib.sha256(f'{astra[0].pk},{fable[0].pk}'.encode()).hexdigest()[:12]
        context = self.encounter(encounter_id).current_context
        self.assertEqual(self.jobs_of(encounter_id)[-1].idempotency_key,
                         f'assess:{context.pk}:{primary.pk}:review2:{second.pk}:p:{ids}')
        self.assertEqual(self.records(encounter_id)['astra']['run'], str(astra[0].pk))


# --- unknown outcomes, reuse, failures --------------------------------------------------------------------------------

@override_settings(**LIVE, **BOTH)
class UnknownOutcomeTests(HarnessCase):
    def test_an_unknown_outcome_blocks_every_later_send_and_reconcile_resends_only_that_participant(self):
        self.adapters['astra'].outcomes = ['unknown']
        encounter_id = self.create()
        drain()
        astra, fable = self.runs_of(encounter_id, 'astra'), self.runs_of(encounter_id, 'fable')
        self.assertEqual([r.state for r in astra], ['unknown'])
        # Fable's stage met the unknown outcome: nothing sent, a run that says so, and the chain went on
        self.assertEqual([(r.state, r.sent, r.scope.get('held'), r.error) for r in fable],
                         [('not_sent', False, 'unknown_outcome', jobs.PARTICIPANT_BLOCKED_MESSAGE)])
        self.assertEqual(self.adapters['fable'].sent, [])
        records = self.records(encounter_id)
        self.assertEqual((records['astra']['state'], records['fable']['state']), ('unknown', 'blocked'))
        encounter = self.encounter(encounter_id)
        self.assertEqual(encounter.state, 'provider_unknown')  # the encounter-wide block stays
        self.assertIn('reconciliation', self.client.get('/api/encounters').json()['encounters'][0]['queue_reasons'])
        # reconcile queues predict: Corti's identical request is reused, and only Astra is sent again
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(astra[0].pk), 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual(len(self.corti.requests), 1)
        corti = self.runs_of(encounter_id, 'corti')
        self.assertEqual([(r.state, r.sent, bool(r.reused_from_id)) for r in corti],
                         [('succeeded', True, False), ('succeeded', False, True)])
        self.assertEqual(len(self.adapters['astra'].sent), 2)  # the unknown one, then once after the reconciliation
        self.assertEqual(len(self.adapters['fable'].sent), 1)  # never sent before: sent once now
        records = self.records(encounter_id)
        self.assertEqual((records['astra']['state'], records['fable']['state']), ('read', 'read'))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')
        reconciled = models.AuditEvent.objects.get(encounter_id=encounter_id, event='provider.reconciled')
        self.assertEqual(reconciled.data, {'run': str(astra[0].pk), 'provider': 'astra'})
        summaries = [row['summary'] for row in self.client.get(f'/api/encounters/{encounter_id}').json()['activity']]
        self.assertIn('Unknown Astra outcome reconciled', summaries)

    def test_an_adapter_that_raises_while_sending_leaves_an_unknown_outcome_to_reconcile(self):
        # I8: an adapter answers every attempt with a RawExchange; one that raised may have sent the request, so its
        # outcome is unknown - recorded, blocking every further send, and reconcilable - never a run left 'sending'
        with mock.patch.object(self.adapters['astra'], 'send', side_effect=RuntimeError('synthetic adapter defect')), \
                self.assertLogs('studio.jobs', level='ERROR') as logged:
            encounter_id = self.create()
            drain()
        self.assertIn('participant astra raised while sending run', logged.output[0])
        astra = self.runs_of(encounter_id, 'astra')
        self.assertEqual([(r.state, r.sent, r.finished_at is not None) for r in astra], [('unknown', True, True)])
        self.assertEqual(astra[0].error, jobs.PARTICIPANT_RAISED_MESSAGE.format(label='Astra', error='RuntimeError'))
        self.assertNotIn('synthetic adapter defect', astra[0].error)  # the exception's text is logged, never shown
        self.assertEqual(astra[0].endpoint, ENDPOINTS['astra'])  # what the reservation named it calls
        self.assertEqual([r.scope.get('held') for r in self.runs_of(encounter_id, 'fable')], ['unknown_outcome'])
        self.assertEqual([(j.kind, j.state) for j in self.jobs_of(encounter_id)][-3:],
                         [('astra', 'succeeded'), ('fable', 'succeeded'), ('assess', 'succeeded')])
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(astra[0].pk), 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual((len(self.corti.requests), len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)),
                         (1, 1, 1))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_corti_unknown_blocks_both_participants(self):
        self.corti.outcomes = ['unknown']
        encounter_id = self.create()
        drain()
        self.assertEqual(self.adapters['astra'].sent + self.adapters['fable'].sent, [])
        records = self.records(encounter_id)
        self.assertEqual((records['astra']['state'], records['fable']['state']), ('blocked', 'blocked'))
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        corti = self.runs_of(encounter_id, 'corti')[0]
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(corti.pk), 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual((len(self.corti.requests), len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)),
                         (2, 1, 1))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_retained_answer_is_reused_and_nothing_is_sent(self):
        first = self.create()
        drain()
        second = self.create()  # the same text in the same workspace: the identical requests
        drain()
        self.assertEqual((len(self.corti.requests), len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)),
                         (1, 1, 1))
        for name in ('astra', 'fable'):
            original, reused = self.runs_of(first, name)[0], self.runs_of(second, name)[0]
            self.assertEqual((reused.state, reused.sent, reused.reused_from_id, reused.usage, reused.usage_basis),
                             ('succeeded', False, original.pk, {}, 'reused_retained_result_no_new_usage'))
            self.assertEqual((reused.endpoint, reused.returned_model, reused.response_id, reused.scope),
                             (original.endpoint, original.returned_model, original.response_id, original.scope))
            self.assertEqual(self.records(second)[name]['state'], 'read')
        summaries = [row['summary'] for row in self.client.get(f'/api/encounters/{second}').json()['activity']]
        self.assertIn('Retained Astra result reused (no new request)', summaries)

    def test_a_replayed_answer_never_stands_in_for_a_live_one(self):
        self.create()
        drain()
        self.adapters['astra'].mode = 'live'  # the same adapter version, now live
        second = self.create()
        drain()
        self.assertEqual((len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)), (2, 1))
        live = self.runs_of(second, 'astra')[0]
        self.assertEqual((live.sent, live.reused_from_id, live.scope), (True, None, {'mode': 'live'}))

    def test_a_request_that_failed_is_never_sent_again(self):
        self.adapters['astra'].outcome = 'failed'
        encounter_id = self.create(OFFICE_NOTE.replace('Date of service: 2026-10-20\n', ''), service_date='2026-10-20')
        drain()
        self.assertEqual(len(self.adapters['astra'].sent), 1)
        # a date change re-predicts (Corti's request carries the date); the participants' requests carry none
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-21'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual(len(self.corti.requests), 2)
        self.assertEqual(len(self.adapters['astra'].sent), 1)  # failed before: never sent again
        self.assertEqual(len(self.adapters['fable'].sent), 1)  # answered before: reused
        astra = self.runs_of(encounter_id, 'astra')
        self.assertEqual([r.state for r in astra], ['failed', 'not_sent'])
        self.assertTrue(astra[1].error.startswith(jobs.FAILED_BEFORE_MESSAGE))
        self.assertEqual((astra[1].request_sha256, astra[1].purpose), (astra[0].request_sha256, 'independent'))
        self.assertEqual(self.records(encounter_id)['astra']['state'], 'not_sent')
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_context_change_that_keeps_corti_s_request_reads_the_participants_as_they_are(self):
        encounter_id = self.create()
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertEqual(response.status_code, 201, response.content)
        last = self.jobs_of(encounter_id)[-1]
        astra, fable = self.runs_of(encounter_id, 'astra')[0], self.runs_of(encounter_id, 'fable')[0]
        corti = self.runs_of(encounter_id, 'corti')[0]
        ids = hashlib.sha256(f'{astra.pk},{fable.pk}'.encode()).hexdigest()[:12]
        self.assertEqual((last.kind, last.idempotency_key),
                         ('assess', f'assess:{last.context_id}:{corti.pk}:p:{ids}'))
        drain()
        self.assertEqual((len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)), (1, 1))
        self.assertEqual(self.records(encounter_id)['astra']['run'], str(astra.pk))


@override_settings(**LIVE, **BOTH)
class MemberDateHoldTests(HarnessCase):
    """Session interpretation 19: nothing is built, reused or sent while a member date conflict stands - the
    participants' requests included - and settling the date makes the request and gives the participants their turn."""

    def test_a_held_encounter_sends_nothing_until_the_date_is_settled(self):
        encounter_id = self.create(service_date='2026-10-22')  # the note documents 2026-10-20: a member conflict
        drain()
        self.assertEqual([j.kind for j in self.jobs_of(encounter_id)], ['extract', 'analyze', 'assess'])
        self.assertEqual(self.corti.requests + self.adapters['astra'].sent + self.adapters['fable'].sent, [])
        hold = self.runs_of(encounter_id, 'corti')
        self.assertEqual([(r.state, r.scope) for r in hold], [('not_sent', {'held': 'member_date_conflict'})])
        records = self.records(encounter_id)
        self.assertEqual((records['astra']['state'], records['fable']['state']), ('not_run', 'not_run'))
        # I10: each says why it did not run - the open date question - not merely that no request was made
        self.assertEqual((records['astra']['reason'], records['fable']['reason']),
                         (jobs.PARTICIPANT_HELD_MESSAGE.format(label='Astra'),
                          jobs.PARTICIPANT_HELD_MESSAGE.format(label='Fable')))
        harness = self.client.get(f'/api/encounters/{encounter_id}').json()['harness']
        rows = {row['name']: row for row in harness['participants']}
        self.assertEqual((rows['astra']['state'], rows['astra']['detail']),
                         ('not_sent', 'Nothing was sent: the service date entered as encounter metadata conflicts '
                                      'with the document, and nothing is sent while that question is open. Settling '
                                      'it gives Astra its turn.'))
        self.assertEqual(jobs._participants_owed(self.encounter(encounter_id).current_revision,
                                                 self.encounter(encounter_id).current_context), ())
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': ''})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual((len(self.corti.requests), len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)),
                         (1, 1, 1))
        records = self.records(encounter_id)
        self.assertEqual((records['astra']['state'], records['fable']['state']), ('read', 'read'))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_swept_predict_that_recorded_a_hold_queues_the_assess(self):
        encounter_id = self.create()
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                   {'service_date': '2026-10-22'}).status_code, 201)
        jobs.run_job(jobs.claim_next())  # the hold is recorded where the predict would have been queued: an assess
        self.assertEqual(self.jobs_of(encounter_id)[-1].kind, 'assess')
        job = models.Job.objects.create(
            encounter_id=encounter_id, revision=self.encounter(encounter_id).current_revision, kind='predict',
            context=self.encounter(encounter_id).current_context, idempotency_key='predict:held-sweep-test',
            state='running', started_at=timezone.now() - timedelta(minutes=11),
            deadline_at=timezone.now() + timedelta(minutes=30))
        hold = jobs._member_date_hold(job.encounter, job.revision, self.corti, self.reviewer)
        jobs.mark_stale()
        queued = self.jobs_of(encounter_id)[-1]
        self.assertEqual((queued.kind, queued.provider_run_id), ('assess', hold.pk))
        self.assertTrue(queued.idempotency_key.startswith(f'assess:{job.context_id}:{hold.pk}:p:'))


# --- the stale sweep, Stop and Resume ---------------------------------------------------------------------------------

@override_settings(**LIVE, **BOTH)
class SweepAndResumeTests(HarnessCase):
    def run_until(self, kind):
        while True:
            job = jobs.claim_next()
            if job.kind == kind:
                return job
            jobs.run_job(job)

    def age(self, job):
        models.Job.objects.filter(pk=job.pk).update(started_at=timezone.now() - timedelta(minutes=11))

    def test_a_participant_whose_outcome_was_recorded_is_settled_and_the_chain_goes_on(self):
        encounter_id = self.create()
        job = self.run_until('astra')
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
        astra = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((job.state, job.result['participant'], job.result['state'], job.result['run']),
                         ('succeeded', 'astra', 'succeeded', str(astra.pk)))
        queued = self.jobs_of(encounter_id)[-1]
        self.assertEqual((queued.kind, queued.idempotency_key), ('fable', 'fable:' + jobs._chain_of(job)))
        drain()
        self.assertEqual((len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)), (1, 1))
        self.assertEqual(self.records(encounter_id)['astra']['state'], 'read')
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_participant_left_mid_send_is_unknown_and_reconcile_resends_only_it(self):
        encounter_id = self.create()
        job = self.run_until('astra')
        with mock.patch.object(self.adapters['astra'], 'send', side_effect=_WorkerDied()):
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        self.age(job)
        jobs.mark_stale()
        job.refresh_from_db()
        astra = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((job.state, astra.state), ('unknown', 'unknown'))
        self.assertEqual(self.encounter(encounter_id).state, 'provider_unknown')
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(astra.pk), 'note': RECONCILE_NOTE})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual(len(self.corti.requests), 1)  # Corti's identical request is reused
        self.assertEqual((len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)), (1, 1))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_participant_that_died_with_its_run_only_reserved_is_resumable(self):
        encounter_id = self.create()
        job = self.run_until('astra')
        with mock.patch('studio.jobs.is_stopped', side_effect=_WorkerDied()):  # dies right after reserving
            with self.assertRaises(_WorkerDied):
                jobs.run_job(job)
        self.age(job)
        jobs.mark_stale()
        job.refresh_from_db()
        run = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((job.state, run.state, run.started_at), ('cancelled', 'not_sent', None))
        self.assertEqual(self.encounter(encounter_id).state, 'stopped')
        response = self.client.post(f'/api/encounters/{encounter_id}/resume')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json(), {'resumed': 'astra'})
        drain()
        self.assertEqual((len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)), (1, 1))
        # the swept reservation is no outcome: the assess reads the run the resumed stage sent
        self.assertEqual(self.records(encounter_id)['astra']['run'], str(self.runs_of(encounter_id, 'astra')[1].pk))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_stop_before_the_participant_sends_cancels_it_and_resume_sends_once(self):
        encounter_id = self.create()
        job = self.run_until('astra')
        models.Job.objects.filter(pk=job.pk).update(stop_requested_at=timezone.now())
        jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.state, 'cancelled')
        self.assertEqual([r.state for r in self.runs_of(encounter_id, 'astra')], ['cancelled'])
        self.assertEqual(self.adapters['astra'].sent, [])
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual((len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)), (1, 1))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_chain_the_upgrade_started_stops_where_a_participant_would_send(self):
        encounter_id = self.create()
        job = self.run_until('astra')
        marked = f'{job.idempotency_key}{jobs.UPGRADE_MARK}'
        models.Job.objects.filter(pk=job.pk).update(idempotency_key=marked)
        job.refresh_from_db()
        jobs.run_job(job)
        job.refresh_from_db()
        self.assertEqual(job.state, 'cancelled')
        self.assertEqual(job.error, jobs.PARTICIPANT_UPGRADE_MESSAGE.format(label='Astra'))
        self.assertEqual(self.adapters['astra'].sent, [])
        self.assertEqual(self.encounter(encounter_id).state, 'stopped')
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual((len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)), (1, 1))
        fable_job = [j for j in self.jobs_of(encounter_id) if j.kind == 'fable'][-1]
        self.assertFalse(fable_job.idempotency_key.endswith(jobs.UPGRADE_MARK))  # a member's Resume sends on

    def test_the_upgrade_s_predict_marks_its_chain_and_no_participant_sends_for_it(self):
        with override_settings(FABLE_MODE='disabled'):
            encounter_id = self.create()
            drain()
        self.assertEqual((len(self.corti.requests), len(self.adapters['astra'].sent)), (1, 1))
        encounter = self.encounter(encounter_id)
        # the predict an upgrade's remake queues at a stage that never sends: Corti's answer is retained (reused) and so
        # is Astra's, but Fable - configured since - has none, and stops where it would send
        jobs.enqueue(models.Job.PREDICT, encounter=encounter, revision=encounter.current_revision,
                     context=encounter.current_context, key=jobs._upgrade_predict_key(encounter.current_context),
                     requested_by=self.reviewer)
        drain()
        chain = self.jobs_of(encounter_id)[-3:]
        self.assertEqual([(j.kind, j.state) for j in chain],
                         [('predict', 'succeeded'), ('astra', 'succeeded'), ('fable', 'cancelled')])
        self.assertTrue(chain[1].idempotency_key.endswith(jobs.UPGRADE_MARK))
        self.assertEqual(chain[2].error, jobs.PARTICIPANT_UPGRADE_MESSAGE.format(label='Fable'))
        self.assertEqual((len(self.corti.requests), len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)),
                         (1, 1, 0))
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(len(self.adapters['fable'].sent), 1)  # a member's Resume sends it, once
        self.assertEqual(self.records(encounter_id)['fable']['state'], 'read')

    def test_a_context_change_after_a_stop_gives_a_participant_with_no_outcome_its_turn(self):
        encounter_id = self.create()
        for _ in range(3):
            jobs.run_job(jobs.claim_next())  # extract, analyze, predict: Astra's stage waits in the queue
        self.assertEqual(self.client.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        # Corti's request is unchanged, so its answer stands; the participants recorded no outcome, so their chain runs
        # before the assess rather than an assess that reads them as 'not run' and leaves no way to run them
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertEqual(response.status_code, 201, response.content)
        context, corti = self.encounter(encounter_id).current_context, self.runs_of(encounter_id, 'corti')[0]
        digest = hashlib.sha256(f'assess:{context.pk}:{corti.pk}|context:{context.pk}'.encode()).hexdigest()[:32]
        last = self.jobs_of(encounter_id)[-1]
        self.assertEqual((last.kind, last.idempotency_key, last.provider_run_id),
                         ('astra', f'astra:{digest}', corti.pk))
        drain()
        self.assertEqual((len(self.corti.requests), len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)),
                         (1, 1, 1))
        records = self.records(encounter_id)
        self.assertEqual((records['astra']['state'], records['fable']['state']), ('read', 'read'))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_participant_configured_since_gets_its_turn_and_the_other_reuses_its_answer(self):
        with override_settings(FABLE_MODE='disabled'):
            encounter_id = self.create()
            drain()
        self.assertEqual(self.records(encounter_id)['fable']['state'], 'not_configured')
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual((len(self.corti.requests), len(self.adapters['astra'].sent), len(self.adapters['fable'].sent)),
                         (1, 1, 1))
        astra = self.runs_of(encounter_id, 'astra')
        self.assertEqual([(r.sent, r.reused_from_id) for r in astra], [(True, None), (False, astra[0].pk)])
        records = self.records(encounter_id)
        self.assertEqual((records['astra']['run'], records['fable']['state']), (str(astra[1].pk), 'read'))

    def test_the_longest_assess_key_fits_with_a_resume(self):
        base = f'assess:{models.uuid.uuid4()}:{models.uuid.uuid4()}:review2:{models.uuid.uuid4()}'
        encounter_id = self.create()
        drain()
        revision = self.encounter(encounter_id).current_revision
        key = jobs._assess_key(base, revision) + f':resume:{models.uuid.uuid4()}'
        self.assertLessEqual(len(key), models.Job._meta.get_field('idempotency_key').max_length)
        self.assertRegex(key, r':p:[0-9a-f]{12}:resume:')


# --- what the assess reads, and retrieval -----------------------------------------------------------------------------

@override_settings(**LIVE, **BOTH)
class AssessReadsTests(HarnessCase):
    def test_retrieval_reads_the_same_lookup_for_every_proposal_code(self):
        recorded = []
        with mock.patch.dict(sys.modules, {'studio.reference.passages': fake_passages(recorded)}):
            encounter_id = self.create()
            drain()
        assessment = self.encounter(encounter_id).current_assessment
        self.assertEqual(recorded, [(['99213'], date(2026, 10, 20), ('synthetic-passage-set',))])
        self.assertEqual([(entry['code'], entry['passages'][0]['section']) for entry in assessment.retrieval],
                         [('99213', 'Chapter VI §C')])

    def test_without_the_passages_module_retrieval_is_empty(self):
        encounter_id = self.create()
        drain()
        self.assertEqual(self.encounter(encounter_id).current_assessment.retrieval, [])

    def test_a_participant_code_is_prefetched_for_the_engine(self):
        seen = []
        real = prefetched_lookup

        def recording(codes):
            seen.append(tuple(codes))
            return real(codes)
        with mock.patch('studio.jobs.prefetched_lookup', side_effect=recording):
            self.create()
            drain()
        self.assertEqual(seen, [('99213', '99214')])  # Corti's selected code and both participants' codes

    def test_a_stored_answer_that_no_longer_matches_its_hash_is_refused_not_failed(self):
        encounter_id = self.create()
        drain()
        fable = self.runs_of(encounter_id, 'fable')[0]
        models.ProviderRun.objects.filter(pk=fable.pk).update(response_sha256='0' * 64)
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        record = self.records(encounter_id)['fable']
        self.assertEqual((record['state'], record['reason']),
                         ('refused', 'The stored response no longer matches its recorded hash; it was not read.'))
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_a_reader_that_raises_refuses_only_that_participant(self):
        # I10: a reader defect is that participant's 'refused', with why - never a failed assess that loses Corti's
        def reader_for(provider, adapter_version):
            if provider != 'fable':
                return fake_reader(provider, adapter_version)

            def broken(request, data):
                raise KeyError('synthetic reader defect')
            return broken
        with mock.patch('studio.participants.reader_for', side_effect=reader_for), \
                self.assertLogs('studio.jobs', level='ERROR'):
            encounter_id = self.create()
            drain()
        records = self.records(encounter_id)
        self.assertEqual((records['fable']['state'], records['fable']['reason'], records['astra']['state']),
                         ('refused', jobs.PARTICIPANT_UNREADABLE_MESSAGE.format(error='KeyError'), 'read'))
        self.assertEqual(self.encounter(encounter_id).current_assessment.summary['participants_given'][1][:3],
                         ['fable', 'refused', []])
        self.assertEqual(self.encounter(encounter_id).state, 'ready_for_review')

    def test_the_same_assessment_compares_the_participant_records_and_the_retrieval(self):
        encounter_id = self.create()
        drain()
        encounter = self.encounter(encounter_id)
        assessment = encounter.current_assessment
        common = (assessment, assessment.sha256, encounter.current_revision, encounter.current_context,
                  assessment.routing, assessment.provider_run, None)
        self.assertTrue(review._same_assessment(*common, assessment.participants, assessment.retrieval))
        refused = [dict(record, state='refused') for record in assessment.participants]
        self.assertFalse(review._same_assessment(*common, refused, assessment.retrieval))
        self.assertFalse(review._same_assessment(*common, assessment.participants, [{'code': '99213'}]))


# --- what a participant is given --------------------------------------------------------------------------------------

@override_settings(**LIVE, **BOTH)
class DocumentKindTests(HarnessCase):
    def setUp(self):
        super().setUp()
        import tempfile

        self.corti.selections = []  # a PDF's extracted text wraps lines: Corti's fake proposes nothing here
        self.store = tempfile.TemporaryDirectory()
        self.addCleanup(self.store.cleanup)
        override = override_settings(ORIGINALS_DIR=self.store.name)
        override.enable()
        self.addCleanup(override.disable)

    def upload(self, data, name):
        response = self.client.post('/api/encounters', {'file': self.file(data, name), 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    @staticmethod
    def file(data, name):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, data)

    def test_a_pdf_upload_sends_its_original_and_names_it_by_sha256_and_size(self):
        pdf = docgen.make_pdf([OFFICE_NOTE.replace('\n', ' ')[:900]])
        encounter_id = self.upload(pdf, 'synthetic-note.pdf')
        drain()
        source = models.SourceFile.objects.get(encounter_id=encounter_id)
        original = {'sha256': source.sha256, 'bytes': source.size}
        self.assertEqual(self.adapters['astra'].built, [('pdf', original)])
        self.assertEqual(self.adapters['astra'].sent[0]['original'], hashlib.sha256(pdf).hexdigest())
        run = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual(run.request_body['original'], original)  # named, never its bytes
        self.assertNotIn('%PDF', json.dumps(run.request_body))

    def test_an_original_that_no_longer_reads_back_is_not_sent(self):
        pdf = docgen.make_pdf([OFFICE_NOTE.replace('\n', ' ')[:900]])
        encounter_id = self.upload(pdf, 'synthetic-note.pdf')
        job = None
        while True:
            job = jobs.claim_next()
            if job.kind == 'astra':
                break
            jobs.run_job(job)
        with mock.patch('studio.jobs.read_original', side_effect=storage.OriginalCorrupted('changed')):
            jobs.run_job(job)
        run = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((run.state, run.error), ('not_sent', jobs.PARTICIPANT_ORIGINAL_MESSAGE))
        self.assertEqual(self.adapters['astra'].sent, [])
        drain()
        self.assertEqual(len(self.adapters['fable'].sent), 1)

    def test_kinds_for_docx_txt_paste_and_addendum(self):
        self.assertEqual(self.kind_of(self.upload(b'Synthetic plain text note.\n' + OFFICE_NOTE.encode(), 'note.txt')),
                         ('txt', None))
        paste = self.create()
        self.assertEqual(self.kind_of(paste), ('paste', None))
        drain()
        response = self.post(f'/api/encounters/{paste}/addenda',
                             {'text': 'Synthetic addendum text.', 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        revision = self.encounter(paste).current_revision
        self.assertEqual(jobs._participant_document(revision), ('addendum', None, None))
        # the addendum revision keeps its parent's pages; the participants' framing still reads all of its text
        for name in ('astra', 'fable'):
            run = models.ProviderRun.objects.filter(revision=revision, provider=name).get()
            self.assertEqual((run.state, run.sent), ('succeeded', True))
            self.assertIn('Synthetic addendum text.', run.request_body['input'])
        self.assertEqual(self.adapters['astra'].built[-1], ('addendum', None))
        docx = docgen.make_docx([OFFICE_NOTE])
        self.assertEqual(self.kind_of(self.upload(docx, 'note.docx')), ('docx', None))

    def test_a_multi_page_pdf_is_framed_page_by_page(self):
        pages = ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT. Page one of a synthetic note.',
                 'Page two of the synthetic note. Plan: repeat colonoscopy in 3 years.']
        encounter_id = self.upload(docgen.make_pdf(pages), 'two-pages.pdf')
        drain()
        revision = self.encounter(encounter_id).current_revision
        self.assertEqual(len(revision.pages), 2)
        run = self.runs_of(encounter_id, 'astra')[0]
        self.assertEqual((run.state, run.sent), ('succeeded', True))
        framed = run.request_body['input']
        self.assertLess(framed.index('[Page 1]'), framed.index('[Page 2]'))

    def test_the_pages_given_to_a_participant_tile_the_text(self):
        revision = types.SimpleNamespace(text='x' * 25, pages=[{'page': 2, 'start': 12, 'end': 20},
                                                               {'page': 1, 'start': 0, 'end': 10}])
        self.assertEqual(jobs._participant_pages(revision), (PageSpan(1, 0, 12), PageSpan(2, 12, 25)))
        self.assertEqual(jobs._participant_pages(types.SimpleNamespace(text='abc', pages=[])), ())

    def kind_of(self, encounter_id):
        revision = self.encounter(encounter_id).current_revision
        kind, original, _ = jobs._participant_document(revision)
        return kind, original
