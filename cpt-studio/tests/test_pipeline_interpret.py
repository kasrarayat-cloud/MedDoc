"""Pipeline I of the Gemini migration (design/FINAL.md 6.1-6.5, 6.9 and 6.11, as design/ADJUDICATION.md P-2 and P-6 amend
them; slice S09): extract queues the interpret stage, which reads one Gemini answer into an EventInventory; analyze derives
the gemini-context@1 context and its routing stand-in from it and nothing else; predict routes a new date by that stand-in;
the send purpose, the doors, mark_stale, reconcile, resume, the retry door and the progress panel.

Synthetic data only, no network: the interpreter is the replay interpreter over recordings written for each test (the
request built by the production adapter, so a recording is keyed by the live request's sha256), or a scripted subclass of
the production adapter's Interpreter where an outcome a replay cannot give is needed (a refusal over HTTP, an unknown
outcome) - its loop, envelope and classification are the production code's. Corti is disabled or an in-process fake.
"""
import copy
import hashlib
import json
import shutil
import tempfile
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import TestCase, override_settings
from django.utils import timezone

from studio import interpretation, jobs, models, progress, review
from studio.context_facts import USER_CONFLICT_NOTE, is_member_conflict
from studio.interpretation import adapter, holds, sentinel
from studio.interpretation import store as inventory_store
from studio.providers.base import request_sha256
from studio.types import RawExchange
from tests.support import factories as f
from tests.support import operator as ops
from tests.test_pipeline_api import FakeProvider

AUTH = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
FIXTURE = json.loads((Path(__file__).parent / 'fixtures' / 'interpretation' / 'synthetic'
                      / 's3-twin-colonoscopy-reach.json').read_text())
TEXT = FIXTURE['text']  # a SYNTHETIC colonoscopy report dated November 9, 2026
ANSWER = json.loads(FIXTURE['response']['candidates'][0]['content']['parts'][0]['text'])
TRIAL_429 = (Path(__file__).parent / 'fixtures' / 'interpretation' / 'adapter'
             / 'trial-attempt1-note8-429.json').read_bytes()
# D39: the monthly spending cap's 429 - RESOURCE_EXHAUSTED with a message and no QuotaFailure - is a quota hold
SPENDING_CAP_429 = json.dumps({'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED', 'message': (
    'Your project has exceeded its monthly spending cap. (synthetic copy)')}}).encode()
USAGE = {'promptTokenCount': 1000, 'candidatesTokenCount': 200, 'totalTokenCount': 1200}
NOTE = 'Confirmed with the synthetic vendor log: the request was not answered.'
Run = models.ProviderRun


def envelope(answer=None, *, model=interpretation.MODEL, finish='STOP', text=None) -> bytes:
    """A generateContent 200 body carrying ``answer`` (or raw ``text``) as its one candidate's text."""
    part = text if text is not None else json.dumps(ANSWER if answer is None else answer)
    return json.dumps({'candidates': [{'content': {'parts': [{'text': part}], 'role': 'model'}, 'finishReason': finish,
                                       'index': 0}],
                       'modelVersion': model, 'responseId': 'synthetic-s09', 'usageMetadata': USAGE}).encode()


def undated():
    """The answer with no date of service stated (contract 8.1 'not_stated')."""
    answer = copy.deepcopy(ANSWER)
    answer['encounter']['date_of_service'] = {'value': '', 'state': 'not_stated', 'words': '', 'passages': [],
                                              'other_dates': []}
    return answer


def answered(body: bytes, *, status=200) -> RawExchange:
    """A live-like exchange that reached the vendor and was answered."""
    return RawExchange(outcome='succeeded' if status == 200 else 'failed', sent=True, http_status=status,
                       response_bytes=body, response_sha256=hashlib.sha256(body).hexdigest(), latency_ms=9.5,
                       usage=dict(USAGE) if status == 200 else {}, usage_basis='provider_reported_tokens'
                       if status == 200 else '', requested_model=interpretation.MODEL,
                       returned_model=interpretation.MODEL if status == 200 else '',
                       error='' if status == 200 else f'Google answered HTTP {status}; the response body is retained.')


UNKNOWN = RawExchange(outcome='unknown', sent=True, error='Read timed out after the request was sent.',
                      requested_model=interpretation.MODEL)


class ScriptedInterpreter(adapter.Interpreter):
    """The production adapter's Interpreter (its request, its one-exchange loop, its Stop check) whose one exchange is
    scripted: ``outcomes`` are RawExchanges given in turn, and ``sent`` records each request it was asked to send. Its
    endpoint is set, so its runs read as having called a vendor; its mode is 'replay', so no live gate applies."""
    mode = 'replay'
    endpoint = 'https://interpreter.invalid/v1/synthetic:generateContent'

    def __init__(self, *outcomes):
        super().__init__()
        self.outcomes, self.sent = list(outcomes), []

    def _exchange(self, body, deadline):
        self.sent.append(request_sha256(body))
        return self.outcomes.pop(0)


@override_settings(GEMINI_MODE='replay', PROVIDER_MODE='disabled', AUTHORIZATION_REF=AUTH, ASTRA_MODE='disabled',
                   FABLE_MODE='disabled', INTERPRET_MAX_CHARS=20_000, INTERPRET_MAX_PAGES=40)
class InterpretCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # installed before any test patches a function the deny set is computed from (jobs' archived children): an
        # install that met a patched one would fail, and a failed install stands for the process
        status = sentinel.install()
        assert status['state'] == 'ok', status

    def setUp(self):
        self.replay = tempfile.mkdtemp(prefix='s09-replay-')
        self.addCleanup(shutil.rmtree, self.replay, True)
        replay = override_settings(GEMINI_REPLAY_DIR=self.replay)
        replay.enable()
        self.addCleanup(replay.disable)
        self.ws = f.workspace()
        self.user = f.member(self.ws, f.user(), role=models.Membership.REVIEWER)

    # --- helpers ----------------------------------------------------------------------------------------------------------

    def upload(self, text=TEXT, *, service_date='', workspace=None):
        """An encounter with a pasted SYNTHETIC revision whose pipeline was started (its extract queued)."""
        encounter = models.Encounter.objects.create(
            workspace=workspace or self.ws, title='Synthetic note', created_by=self.user,
            user_values={'service_date': service_date} if service_date else {})
        revision = f.pasted_revision(encounter, self.user, text, extract=False)
        jobs.start_pipeline(revision, self.user)
        return encounter, revision

    def run_next(self, kind):
        job = jobs.claim_next()
        self.assertIsNotNone(job, f'no job queued; expected {kind}')
        self.assertEqual(job.kind, kind, job.idempotency_key)
        return jobs.run_job(job)

    def queued(self):
        return list(models.Job.objects.filter(state=models.Job.QUEUED).order_by('created_at', 'pk'))

    def request_for(self, revision):
        revision.refresh_from_db()
        kind = jobs._participant_document(revision)[0]
        return adapter.build_request(revision.text, jobs._participant_pages(revision), kind)

    def record(self, revision, body=None):
        """The replay recording of ``revision``'s interpretation request: ``body`` (a 200 answer's raw bytes)."""
        request = self.request_for(revision)
        folder = Path(self.replay) / adapter.NAME
        folder.mkdir(exist_ok=True)
        (folder / f'{request.canonical_sha256}.json').write_bytes(envelope() if body is None else body)
        return request

    def scripted(self, *outcomes):
        interpreter = ScriptedInterpreter(*outcomes)
        patcher = mock.patch.object(adapter, 'get_interpreter', return_value=interpreter)
        patcher.start()
        self.addCleanup(patcher.stop)
        return interpreter

    def interpret_runs(self, revision):
        return list(Run.objects.filter(revision=revision, purpose=interpretation.PURPOSE).order_by('created_at', 'pk'))

    def outcome_write_fails_once(self):
        """Decision (k), driven through the stage: the run's first outcome write fails (_finish_run raises once), after
        its one exchange was committed as it ended, so _finish_loop records the run unknown with no bytes of its own."""
        real, calls = jobs._finish_run, []

        def fails_once(run, exchange):
            calls.append(exchange.outcome)
            if len(calls) == 1:
                raise RuntimeError('synthetic: the outcome write failed')
            return real(run, exchange)
        return mock.patch.object(jobs, '_finish_run', side_effect=fails_once)

    def in_another_workspace(self):
        """A member's upload of the same text in another workspace, through extract: (encounter, revision)."""
        other_ws = f.workspace('Other synthetic practice')
        f.member(other_ws, self.user)
        encounter, revision = self.upload(workspace=other_ws)
        self.run_next('extract')
        return encounter, revision

    def through_extract(self, **kwargs):
        encounter, revision = self.upload(**kwargs)
        self.run_next(models.Job.EXTRACT)
        revision.refresh_from_db()
        return encounter, revision

    def state(self, encounter):
        encounter.refresh_from_db()
        return review._state_and_run(encounter)

    def unknown_holding_an_answer(self, encounter, revision, *, state=Run.UNKNOWN, body=None):
        """A run as a worker that died after its exchange was answered and recorded leaves it (decision (k), or a dead
        worker): its outcome not recorded, its one exchange recorded succeeded with HTTP 200 (``body``, the answer by
        default). An UNKNOWN run carries the effect the stage records on one ('unknown': _settle_interpretation and
        _stale_interpretation), as every unknown outcome the stage settled does; a SENDING one carries none."""
        request = self.request_for(revision)
        body = envelope() if body is None else body
        run = Run.objects.create(
            encounter=encounter, revision=revision, provider='gemini', adapter_version=interpretation.ADAPTER_VERSION,
            request_sha256=request.canonical_sha256, request_body=request.body, contexts=list(request.contexts),
            state=state, sent=True, purpose=interpretation.PURPOSE,
            scope={'mode': 'replay', **({'effect': holds.UNKNOWN} if state == Run.UNKNOWN else {})},
            endpoint=ScriptedInterpreter.endpoint, requested_model=interpretation.MODEL, started_at=timezone.now(),
            authorization_ref=AUTH, requested_by=self.user)
        models.ProviderExchange.objects.create(
            run=run, turn=1, request_body=request.body, request_sha256=request.canonical_sha256, state='succeeded',
            http_status=200, response_bytes=body, response_sha256=hashlib.sha256(body).hexdigest(), usage=dict(USAGE),
            response_id='synthetic-s09', started_at=timezone.now(), finished_at=timezone.now())
        return run

    def answered_run(self, encounter, revision, body, *, request_sha256=None):
        """A sent interpretation run recorded SUCCEEDED with ``body`` and its turn-1 exchange, as _send leaves one whose
        worker died before the stage settled its outcome: no effect recorded, no inventory read. ``request_sha256``: the
        request it answered when that is not the one this revision makes now (an upgrade changed the request between the
        stage that sent it and the stage that settles it)."""
        request = self.request_for(revision)
        sha = request_sha256 or request.canonical_sha256
        digest = hashlib.sha256(body).hexdigest()
        run = Run.objects.create(
            encounter=encounter, revision=revision, provider='gemini', adapter_version=interpretation.ADAPTER_VERSION,
            request_sha256=sha, request_body=request.body, contexts=list(request.contexts), state=Run.SUCCEEDED,
            sent=True, http_status=200, response_bytes=body, response_sha256=digest, usage=dict(USAGE),
            purpose=interpretation.PURPOSE, scope={'mode': 'replay'}, endpoint=ScriptedInterpreter.endpoint,
            requested_model=interpretation.MODEL, started_at=timezone.now(), finished_at=timezone.now(),
            authorization_ref=AUTH, requested_by=self.user)
        models.ProviderExchange.objects.create(
            run=run, turn=1, request_body=request.body, request_sha256=sha, state='succeeded', http_status=200,
            response_bytes=body, response_sha256=digest, usage=dict(USAGE), started_at=timezone.now(),
            finished_at=timezone.now())
        return run


class ChainTests(InterpretCase):
    """FINAL 6.1-6.5: a replay upload reaches predict with a gemini context and its stand-in."""

    def test_a_replay_upload_reaches_predict_with_a_gemini_context_and_its_stand_in(self):
        encounter, revision = self.through_extract()
        [interpret] = self.queued()
        self.assertEqual((interpret.kind, interpret.idempotency_key, interpret.context_id),
                         ('interpret', f'interpret:{revision.pk}:gemini-events@1', None))
        request = self.record(revision)
        with mock.patch.object(jobs, '_analyze_child', side_effect=AssertionError('legacy analyze')), \
                mock.patch.object(jobs, '_route_child', side_effect=AssertionError('legacy router')), \
                mock.patch.object(jobs, 'make_context', side_effect=AssertionError('legacy context')):
            job = self.run_next('interpret')
            self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
            [run] = self.interpret_runs(revision)
            self.assertEqual((run.provider, run.adapter_version, run.purpose, run.state, run.sent, run.request_sha256,
                              run.scope['mode'], run.scope['effect'], run.service_date),
                             ('gemini', 'gemini-generate@cptstudio-1', 'interpretation', 'succeeded', False,
                              request.canonical_sha256, 'replay', 'answered', None))
            self.assertEqual((run.endpoint, run.requested_model, run.returned_model), ('', 'gemini-4-argon',
                                                                                       'gemini-4-argon'))
            self.assertEqual(list(run.exchanges.values_list('turn', 'state')), [(1, 'succeeded')])
            [inventory] = models.EventInventory.objects.filter(revision=revision)
            self.assertEqual((inventory.state, inventory.provider_run_id, inventory.interpretation_version,
                              inventory.inventory_version, inventory.text_sha256),
                             ('read', run.pk, 'gemini-events@1', 'gemini-inventory@1', revision.text_sha256))
            self.assertEqual(job.result, {'provider': 'succeeded', 'run': str(run.pk), 'inventory': str(inventory.pk)})
            [analyze] = self.queued()
            self.assertEqual(analyze.idempotency_key, f'analyze:{revision.pk}:{inventory.pk}')

            job = self.run_next('analyze')
            self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
            encounter.refresh_from_db()
            context = encounter.current_context
            self.assertEqual((context.version, context.event_inventory_id, context.revision_id),
                             ('gemini-context@1', inventory.pk, revision.pk))
            service = context.facts['service_date']
            self.assertEqual((service['value'], service['origin'], service['state']),
                             ('2026-11-09', 'document', 'no_member_value'))
            self.assertEqual((context.document_date['origin'], context.document_date['value']), ('document', '2026-11-09'))
            self.assertEqual({name: context.facts[name]['origin'] for name in ('setting', 'billing_context',
                                                                               'patient_status')},
                             {'setting': 'missing', 'billing_context': 'missing', 'patient_status': 'missing'})
            [routing] = models.RoutingRun.objects.filter(revision=revision)
            self.assertEqual((routing.version, routing.service_date, routing.result['inventory'],
                              routing.result['inventory_sha256'], routing.result['document_kind']),
                             ('gemini-routing@1', date(2026, 11, 9), str(inventory.pk), inventory.sha256, ''))
            self.assertEqual([finding['family'] for finding in routing.result['findings']], ['gi.colonoscopy'])
            self.assertTrue(all(finding['mentions'] == [] for finding in routing.result['findings']))
            [predict] = self.queued()
            self.assertEqual((predict.kind, predict.idempotency_key, predict.context_id),
                             ('predict', f'predict:{context.pk}', context.pk))

            job = self.run_next('predict')  # Corti disabled: the assess follows with no provider run
            self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        [assess] = self.queued()
        self.assertEqual((assess.kind, assess.context_id, assess.provider_run_id), ('assess', context.pk, None))
        self.assertEqual(models.RoutingRun.objects.filter(revision=revision).count(), 1)  # the stand-in, once

    def test_an_upload_through_the_api_reaches_predict_with_a_gemini_context(self):
        """The done-when, from the member's own act: a pasted SYNTHETIC document uploaded through POST /api/encounters
        (the attestation and the intake path) is interpreted from its replay recording and reaches predict on a
        gemini-context@1 context with its stand-in, nothing of the legacy reader called."""
        from django.test import Client

        client = Client()
        client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            response = client.post('/api/encounters', {'text': TEXT, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content[:300])
        encounter = models.Encounter.objects.get(pk=response.json()['id'])
        revision = encounter.current_revision
        self.run_next('extract')
        self.record(revision)
        with mock.patch.object(jobs, '_analyze_child', side_effect=AssertionError('legacy analyze')), \
                mock.patch.object(jobs, '_route_child', side_effect=AssertionError('legacy router')):
            for kind in ('interpret', 'analyze', 'predict'):
                job = self.run_next(kind)
                self.assertEqual(job.state, models.Job.SUCCEEDED, f'{kind}: {job.error}')
        encounter.refresh_from_db()
        context = encounter.current_context
        self.assertEqual((context.version, context.event_inventory.provider_run.purpose),
                         ('gemini-context@1', 'interpretation'))
        self.assertTrue(models.RoutingRun.objects.filter(revision=revision, version='gemini-routing@1',
                                                         service_date=date(2026, 11, 9),
                                                         result__inventory=str(context.event_inventory_id)).exists())
        self.assertEqual([(job.kind, job.context_id) for job in self.queued()], [('assess', context.pk)])

    def test_the_stored_inventory_reads_back_through_the_store(self):
        _, revision = self.through_extract()
        self.record(revision)
        self.run_next('interpret')
        inventory = models.EventInventory.objects.get(revision=revision)
        stored = jobs._stored_inventory(inventory, revision)
        self.assertEqual(stored.state, 'read')
        self.assertEqual(stored.encounter_facts['date_of_service']['value'], '2026-11-09')
        self.assertEqual(inventory.sha256, inventory_store.content_sha256(inventory_store.fields_of(inventory)))

    def test_zero_denied_executions_in_interpret_and_analyze(self):
        """FINAL 10.3-10.4 and S09's done-when: interpret and analyze run under new_path with zero denied executions -
        CALL-level checks on (a legacy regex or cache read counts too) - and their write gates find nothing to refuse.
        The positive control shows the instrument counts in this very process."""
        _, revision = self.through_extract()
        self.record(revision)
        gates = []
        real_gate = sentinel.gate

        def spy(entry, **kwargs):
            scope = sentinel.current()
            gates.append((entry, scope.label if scope else None, scope.total(sentinel.NEW_PATH) if scope else None,
                          sentinel.refusal(scope)))
            return real_gate(entry, **kwargs)

        with sentinel.call_checks(), mock.patch.object(sentinel, 'gate', side_effect=spy):
            before = sentinel.totals()[sentinel.NEW_PATH]
            self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
            self.assertEqual(self.run_next('analyze').state, models.Job.SUCCEEDED)
            after = sentinel.totals()[sentinel.NEW_PATH]
            with sentinel.scope(sentinel.NEW_PATH, entry='positive-control') as probe:
                jobs._route_child('Date of service: 2026-11-09\nColonoscopy to the cecum.\n', None)
        self.assertEqual(after - before, 0)
        self.assertEqual([entry for entry, *_ in gates], ['interpret.send', 'interpret', 'analyze'])
        self.assertEqual({(label, total, refusal) for _, label, total, refusal in gates}, {('new_path', 0, None)})
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())
        self.assertGreater(probe.count(sentinel.NEW_PATH), 0)  # the instrument fires: a legacy call is counted

    def test_extract_queues_interpret_and_never_the_legacy_analyze(self):
        _, revision = self.through_extract()
        self.assertEqual([job.kind for job in self.queued()], ['interpret'])
        self.assertFalse(models.Job.objects.filter(idempotency_key=f'analyze:{revision.pk}').exists())


class SizeBoundTests(InterpretCase):
    """FINAL 6.3 step 2 (D4, C9): over the size bound nothing is built or sent, and the stage says so plainly."""

    def test_a_document_over_the_character_bound_is_not_sent(self):
        encounter, revision = self.through_extract()
        interpreter = self.scripted(answered(envelope()))
        with override_settings(INTERPRET_MAX_CHARS=len(TEXT) - 1):
            job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.FAILED, jobs.INTERPRET_TOO_LONG_MESSAGE))
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.state, run.sent, run.request_sha256, run.scope.get('refused'), run.scope.get('bound'),
                          run.scope.get('effect')), ('not_sent', False, '', 'size', 'chars', 'too_long'))
        self.assertEqual((interpreter.sent, run.exchanges.count()), ([], 0))
        self.assertFalse(models.EventInventory.objects.exists())
        self.assertEqual(self.state(encounter), ('provider_failed', run))
        block = progress.encounter_progress(encounter)
        self.assertEqual((block['phase'], block['error']), ('failed', {
            'text': progress.INTERPRETATION_ERRORS['too_long'][0], 'action': 'new_document'}))

    def test_a_document_over_the_page_bound_is_not_sent(self):
        _, revision = self.through_extract()
        with override_settings(INTERPRET_MAX_PAGES=0):
            job = self.run_next('interpret')
        self.assertEqual(job.state, models.Job.FAILED)
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.scope.get('refused'), run.scope.get('bound')), ('size', 'pages'))


class PauseTests(InterpretCase):
    """FINAL 6.3 step 3 and 11.2: a disabled interpreter or a standing hold pauses the stage - a not-sent run with
    scope.held, the stage CANCELLED, the encounter stopped with the paused phase - and a member's Resume goes on."""

    def assert_paused(self, encounter, revision, held):
        job = models.Job.objects.filter(revision=revision, kind='interpret').latest('created_at')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, holds.PAUSED_MESSAGE))
        if held is not None:  # a pause before anything was built: a not-sent run saying why (else the run is the send's)
            run = self.interpret_runs(revision)[-1]
            self.assertEqual((run.state, run.sent, run.scope.get('held'), run.request_sha256),
                             ('not_sent', False, held, ''))
        self.assertEqual(self.state(encounter)[0], 'stopped')
        self.assertTrue(review.can_resume(encounter))
        block = progress.encounter_progress(encounter)
        self.assertEqual((block['phase'], block['message'], block['error']['action'], block['can_resume']),
                         ('paused', holds.PAUSED_MESSAGE, 'resume', True))

    def test_disabled_mode_pauses_and_a_resume_reads_once_it_is_enabled(self):
        encounter, revision = self.through_extract()
        with override_settings(GEMINI_MODE='disabled'):
            self.run_next('interpret')
        self.assert_paused(encounter, revision, holds.HELD_DISABLED)
        self.assertFalse(models.EventInventory.objects.exists())
        self.record(revision)
        resumed = jobs.resume(encounter, self.user)
        self.assertEqual(resumed.kind, 'interpret')
        self.assertTrue(resumed.idempotency_key.startswith(f'interpret:{revision.pk}:gemini-events@1:resume:'))
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(models.EventInventory.objects.get(revision=revision).state, 'read')

    def test_a_misconfigured_interpreter_pauses_like_a_disabled_one(self):
        encounter, revision = self.through_extract()
        with override_settings(GEMINI_REPLAY_DIR=''):  # replay with no directory: get_interpreter refuses
            self.run_next('interpret')
        self.assert_paused(encounter, revision, holds.HELD_DISABLED)
        self.assertIn('CPT_STUDIO_GEMINI_REPLAY_DIR', self.interpret_runs(revision)[-1].error)

    def test_a_standing_hold_pauses_every_interpretation_until_an_operator_releases_it(self):
        encounter, revision = self.through_extract()
        other = Run.objects.create(encounter=encounter, revision=revision, provider='gemini',
                                   adapter_version=interpretation.ADAPTER_VERSION, request_sha256='', request_body={},
                                   contexts=[], state=Run.FAILED, sent=True, http_status=401,
                                   purpose=interpretation.PURPOSE)
        hold = models.InterpreterHold.objects.create(reason='auth', http_status=401, run=other)
        interpreter = self.scripted(answered(envelope()))
        self.run_next('interpret')
        self.assert_paused(encounter, revision, holds.HELD_HOLD)
        self.assertEqual(interpreter.sent, [])
        models.InterpreterHoldRelease.objects.create(hold=hold, released_by=self.user, note='key rotated (synthetic)')
        jobs.resume(encounter, self.user)
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(len(interpreter.sent), 1)

    def test_an_answer_refused_for_its_key_sets_the_hold_and_pauses(self):
        encounter, revision = self.through_extract()
        body = json.dumps({'error': {'code': 401, 'status': 'UNAUTHENTICATED', 'message': 'synthetic'}}).encode()
        interpreter = self.scripted(answered(body, status=401))
        self.run_next('interpret')
        self.assert_paused(encounter, revision, None)
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.state, run.sent, run.http_status, run.scope['effect']), ('failed', True, 401, 'hold'))
        [hold] = models.InterpreterHold.objects.all()
        self.assertEqual((hold.reason, hold.http_status, hold.vendor_status, hold.run_id),
                         ('auth', 401, 'UNAUTHENTICATED', run.pk))
        # the hold is installation-wide: another workspace's document is paused with nothing sent
        other_ws = f.workspace('Other synthetic practice')
        f.member(other_ws, self.user)
        _, second = self.upload(workspace=other_ws)
        self.run_next('extract')
        self.run_next('interpret')
        self.assertEqual(self.interpret_runs(second)[-1].scope.get('held'), holds.HELD_HOLD)
        self.assertEqual(len(interpreter.sent), 1)

    def test_a_daily_quota_refusal_sets_the_quota_hold(self):
        encounter, revision = self.through_extract()
        self.scripted(answered(TRIAL_429, status=429))
        self.run_next('interpret')
        self.assertEqual(models.InterpreterHold.objects.get().reason, 'quota')
        self.assertEqual(self.state(encounter)[0], 'stopped')

    def test_a_spending_cap_refusal_with_no_quota_detail_sets_the_quota_hold_and_stops_sending(self):
        """D39, measured live on 2026-11-10: the project's monthly spending cap answers 429 RESOURCE_EXHAUSTED with a
        message and no QuotaFailure. It is a quota hold, so the next upload - in any workspace - sends nothing until an
        operator releases it (the directive: quota failures must stop requests)."""
        encounter, revision = self.through_extract()
        body = json.dumps({'error': {'code': 429, 'status': 'RESOURCE_EXHAUSTED',
                                     'message': 'Your project has exceeded its monthly spending cap. (synthetic copy)'}}).encode()
        interpreter = self.scripted(answered(body, status=429), answered(envelope()))
        self.run_next('interpret')
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.state, run.sent, run.http_status, run.scope['effect']), ('failed', True, 429, 'hold'))
        [hold] = models.InterpreterHold.objects.all()
        self.assertEqual((hold.reason, hold.http_status, hold.vendor_status, hold.run_id),
                         ('quota', 429, 'RESOURCE_EXHAUSTED', run.pk))
        self.assertEqual(self.state(encounter)[0], 'stopped')
        other_ws = f.workspace('Other synthetic practice')
        f.member(other_ws, self.user)
        _, second = self.upload(workspace=other_ws)
        self.run_next('extract')
        self.run_next('interpret')
        self.assertEqual(self.interpret_runs(second)[-1].scope.get('held'), holds.HELD_HOLD)
        self.assertEqual(len(interpreter.sent), 1)

    def test_d53_a_hold_an_unsettled_answer_sets_is_recorded_before_the_next_send(self):
        """D53 (the S17 refutation, finding 16): an answer naming another model whose reading child died (the stage
        failed before settling: no hold) - the next document's stage, in another workspace, records that answer's hold at
        its door and sends nothing; a failed 401 run left unsettled likewise."""
        encounter, revision = self.through_extract()
        interpreter = self.scripted(answered(envelope(model='gemini-4-argon-preview')), answered(envelope()))
        with mock.patch.object(jobs, '_read_answer', side_effect=jobs.StageFailure('synthetic: the reading child died')):
            self.run_next('interpret')
        [run] = self.interpret_runs(revision)
        self.assertNotIn('effect', run.scope)  # never settled
        self.assertFalse(models.InterpreterHold.objects.exists())
        other_ws = f.workspace('Other synthetic practice')
        f.member(other_ws, self.user)
        _, second = self.upload(workspace=other_ws)
        self.run_next('extract')
        self.run_next('interpret')
        self.assertEqual(models.InterpreterHold.objects.get().reason, 'model')
        self.assertEqual(self.interpret_runs(second)[-1].scope.get('held'), holds.HELD_HOLD)
        self.assertEqual(len(interpreter.sent), 1)

    def test_d53b_a_hold_kept_only_in_an_unknown_runs_exchange_stops_the_next_send(self):
        """D53b (the round-2 refutation, finding 16, case A): an answer naming another model arrived and its exchange
        was committed (turn 1, HTTP 200), then the run's outcome write failed (decision (k)): the run is UNKNOWN with no
        bytes of its own, and no hold was set. The next document's stage, in another workspace, records the hold that
        exchange sets against that run at its door and sends nothing; the run itself is not written."""
        interpreter = self.scripted(answered(envelope(model='gemini-4-argon-preview')), answered(envelope()))
        encounter, revision = self.through_extract()
        with self.outcome_write_fails_once(), self.assertLogs('studio.jobs', level='ERROR'):
            self.run_next('interpret')
        [run] = self.interpret_runs(revision)
        kept = (run.state, run.sent, bytes(run.response_bytes or b''), run.http_status, run.scope, run.reconciled_at)
        self.assertEqual(kept, ('unknown', True, b'', None, {'mode': 'replay', 'effect': 'unknown'}, None))
        self.assertEqual(list(run.exchanges.values_list('turn', 'state', 'http_status')), [(1, 'succeeded', 200)])
        self.assertFalse(models.InterpreterHold.objects.exists())
        _, second = self.in_another_workspace()
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, holds.PAUSED_MESSAGE))
        hold = models.InterpreterHold.objects.get()
        self.assertEqual((hold.reason, hold.http_status, hold.run_id), ('model', 200, run.pk))
        self.assertEqual(self.interpret_runs(second)[-1].scope.get('held'), holds.HELD_HOLD)
        self.assertEqual(len(interpreter.sent), 1)
        run.refresh_from_db()
        self.assertEqual((run.state, run.sent, bytes(run.response_bytes or b''), run.http_status, run.scope,
                          run.reconciled_at), kept)

    def test_d53b_a_hold_kept_only_in_a_dead_workers_exchange_stops_the_next_send_before_the_sweep(self):
        """D53b (finding 16, case B): the worker died after the run's exchange was committed and before its outcome was
        written, so the run is still 'sending' - marked unsent until the stale sweep settles it, 600 s on - and that
        exchange is the spending cap's 429 (a quota hold, D39). Before the sweep, the next document's stage, in another
        workspace, records that hold against the run (sent by may_have_reached_vendor's rule) and sends nothing; the
        run is not written. The sweep then settles the run unknown, and its answer never sets a second hold: the
        member's reconciliation of it pauses while the hold stands, and sends nothing."""
        interpreter = self.scripted(answered(envelope()))
        encounter, revision = self.through_extract()
        dead = models.Job.objects.get(revision=revision, kind='interpret')
        models.Job.objects.filter(pk=dead.pk).update(state=models.Job.RUNNING, started_at=timezone.now(), attempts=1)
        run = self.unknown_holding_an_answer(encounter, revision, state=Run.SENDING, body=SPENDING_CAP_429)
        Run.objects.filter(pk=run.pk).update(sent=False)  # as _send leaves a run in flight
        models.ProviderExchange.objects.filter(run=run).update(state='failed', http_status=429, usage={})
        jobs.mark_stale()  # the restart sweep: the dead stage is not stale yet, so its run stays 'sending'
        self.assertEqual((Run.objects.get(pk=run.pk).state, models.InterpreterHold.objects.count()), ('sending', 0))
        _, second = self.in_another_workspace()
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, holds.PAUSED_MESSAGE))
        hold = models.InterpreterHold.objects.get()
        self.assertEqual((hold.reason, hold.http_status, hold.vendor_status, hold.run_id),
                         ('quota', 429, 'RESOURCE_EXHAUSTED', run.pk))
        self.assertEqual(self.interpret_runs(second)[-1].scope.get('held'), holds.HELD_HOLD)
        self.assertEqual(interpreter.sent, [])
        stored = Run.objects.get(pk=run.pk)
        self.assertEqual((stored.state, stored.sent, stored.scope, stored.finished_at), ('sending', False,
                                                                                         {'mode': 'replay'}, None))
        models.Job.objects.filter(pk=dead.pk).update(started_at=timezone.now() - timedelta(seconds=700))
        jobs.mark_stale()  # once the stage is stale: the run is settled unknown, sent (it reached the vendor)
        stored.refresh_from_db()
        self.assertEqual((stored.state, stored.sent), ('unknown', True))
        self.assertTrue(jobs.reconcile(encounter, stored, self.user, NOTE))
        job = self.run_next('interpret')  # after-reconcile: P-6 settles no 429, and the hold stands
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, holds.PAUSED_MESSAGE))
        self.assertEqual((models.InterpreterHold.objects.count(), interpreter.sent), (1, []))

    def test_d53b_a_reconciled_unknown_runs_hold_pauses_its_own_after_reconcile_stage(self):
        """D53b reads a run left UNKNOWN whether or not it was reconciled: the spending cap's 429 kept only in the
        exchange of a run whose outcome write failed (decision (k)) is a quota hold, so the member's reconciliation of
        that run - P-6 settles no 429 - pauses its own stage at the door, holding against that run, and sends nothing
        more, where it used to send again."""
        interpreter = self.scripted(answered(SPENDING_CAP_429, status=429), answered(envelope()))
        encounter, revision = self.through_extract()
        with self.outcome_write_fails_once(), self.assertLogs('studio.jobs', level='ERROR'):
            self.run_next('interpret')
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.state, models.InterpreterHold.objects.count()), ('unknown', 0))
        self.assertTrue(jobs.reconcile(encounter, run, self.user, NOTE))
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, holds.PAUSED_MESSAGE))
        hold = models.InterpreterHold.objects.get()
        self.assertEqual((hold.reason, hold.vendor_status, hold.run_id), ('quota', 'RESOURCE_EXHAUSTED', run.pk))
        self.assertEqual(len(interpreter.sent), 1)
        self.assertEqual(Run.objects.get(pk=run.pk).state, 'unknown')

    def test_d53b_reads_an_unsettled_exchange_only_as_p6_reads_it_and_records_only_a_hold(self):
        """D53b's control: an unsettled run's exchange sets a hold only when it is a hold read as P-6 reads it. None is
        set by an exchange whose bytes no longer match their sha256, nor by one that answers another request, nor by a
        run that called no vendor (a replay: no endpoint), nor by an answer that is no hold (a usable 200, a 503) - and
        the next document's stage sends."""
        interpreter = self.scripted(answered(envelope()))
        encounter, revision = self.through_extract()
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        unauthenticated = json.dumps({'error': {'code': 401, 'status': 'UNAUTHENTICATED'}}).encode()
        failure = json.dumps({'error': {'code': 503, 'status': 'UNAVAILABLE'}}).encode()
        for state, body, status, change in (
                (Run.UNKNOWN, unauthenticated, 401, {'response_sha256': '0' * 64}),
                (Run.SENDING, unauthenticated, 401, {'request_sha256': 'a' * 64}),
                (Run.UNKNOWN, envelope(), 200, {}),
                (Run.SENDING, failure, 503, {})):
            run = self.unknown_holding_an_answer(encounter, revision, state=state, body=body)
            models.ProviderExchange.objects.filter(run=run).update(
                state='succeeded' if status == 200 else 'failed', http_status=status, **change)
        for state in (Run.UNKNOWN, Run.SENDING):  # a replay calls no vendor: never sent, whatever its exchange says
            replayed = self.unknown_holding_an_answer(encounter, revision, state=state, body=SPENDING_CAP_429)
            Run.objects.filter(pk=replayed.pk).update(endpoint='', sent=False)
            models.ProviderExchange.objects.filter(run=replayed).update(state='failed', http_status=429)
        _, second = self.in_another_workspace()
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertFalse(models.InterpreterHold.objects.exists())
        self.assertEqual(len(interpreter.sent), 1)
        self.assertEqual(models.EventInventory.objects.get(revision=second).state, 'read')

    def test_an_answer_naming_another_model_is_never_read_and_holds(self):
        """P-5: a substituted model is refused and never read (a 'refused' inventory row), and sets the model hold."""
        encounter, revision = self.through_extract()
        self.scripted(answered(envelope(model='gemini-4-argon-preview')))
        self.run_next('interpret')
        [inventory] = models.EventInventory.objects.all()
        self.assertEqual((inventory.state, inventory.verification['stage']), ('refused', 'envelope'))
        self.assertEqual(models.InterpreterHold.objects.get().reason, 'model')
        self.assertEqual(self.state(encounter)[0], 'stopped')
        self.assertFalse(models.Job.objects.filter(kind='analyze').exists())


class ReuseTests(InterpretCase):
    """FINAL 6.3's doors 1 and 2, as P-2 amends door 2."""

    def read_first(self):
        interpreter = self.scripted(answered(envelope()), answered(envelope()))
        encounter, revision = self.through_extract()
        self.run_next('interpret')
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.state, run.sent, run.scope['effect']), ('succeeded', True, 'answered'))
        return interpreter, encounter, revision, run

    def test_an_identical_request_in_the_workspace_reuses_the_stored_answer_and_sends_nothing(self):
        interpreter, _, _, first = self.read_first()
        models.Job.objects.filter(state=models.Job.QUEUED).delete()  # the first encounter's analyze is not run here
        encounter, revision = self.through_extract()
        job = self.run_next('interpret')
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.reused_from_id, run.sent, run.usage, run.usage_basis, run.state, run.exchanges.count()),
                         (first.pk, False, {}, 'reused_retained_result_no_new_usage', 'succeeded', 0))
        self.assertEqual(len(interpreter.sent), 1)
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual((inventory.state, inventory.provider_run_id), ('read', run.pk))
        self.assertEqual(job.result['provider'], 'reused')
        self.assertTrue(models.AuditEvent.objects.filter(event='provider.reused', encounter=encounter,
                                                         data__purpose='interpretation').exists())

    def test_another_workspace_never_reuses_and_a_replayed_answer_never_stands_for_another_mode(self):
        interpreter, _, revision, first = self.read_first()
        models.Job.objects.filter(state=models.Job.QUEUED).delete()
        other_ws = f.workspace('Other synthetic practice')
        f.member(other_ws, self.user)
        _, second = self.upload(workspace=other_ws)
        self.run_next('extract')
        self.run_next('interpret')
        self.assertEqual(len(interpreter.sent), 2)  # sent: the stored answer is the other workspace's
        self.assertIsNone(self.interpret_runs(second)[-1].reused_from_id)
        live_like = ScriptedInterpreter()
        live_like.mode = 'live'
        self.assertIsNone(jobs._retained_interpretation(first.encounter, live_like, self.request_for(revision)))

    def test_p2_an_answer_whose_reading_was_refused_is_never_reused(self):
        interpreter = self.scripted(answered(envelope(text='{"passages": "not the schema"}')), answered(envelope()))
        encounter, revision = self.through_extract()
        job = self.run_next('interpret')
        self.assertEqual(job.state, models.Job.FAILED)
        [refused] = models.EventInventory.objects.all()
        self.assertEqual(refused.state, 'refused')
        [first] = self.interpret_runs(revision)
        self.assertEqual(first.scope['effect'], 'failed')
        self.assertIsNone(jobs._retained_interpretation(encounter, interpreter, self.request_for(revision)))
        _, second = self.through_extract()
        self.run_next('interpret')
        self.assertEqual(len(interpreter.sent), 2)  # the identical request is sent: nothing refused stands in for it
        self.assertIsNone(self.interpret_runs(second)[-1].reused_from_id)
        self.assertEqual(models.EventInventory.objects.get(revision=second).state, 'read')

    def test_p2_a_run_released_for_retry_is_never_reused(self):
        interpreter, encounter, revision, first = self.read_first()
        self.assertEqual(jobs._retained_interpretation(encounter, interpreter, self.request_for(revision)), first)
        Run.objects.filter(pk=first.pk).update(reconciled_by=self.user, reconciled_at=timezone.now(),
                                               reconciliation_note=jobs.RETRY_RELEASE_NOTE)
        self.assertIsNone(jobs._retained_interpretation(encounter, interpreter, self.request_for(revision)))

    def test_an_inventory_already_read_is_used_with_nothing_built_into_a_send(self):
        interpreter, encounter, revision, first = self.read_first()
        inventory = models.EventInventory.objects.get(revision=revision)
        again = jobs.enqueue('interpret', encounter=encounter, revision=revision,
                             key=jobs._interpret_key(revision, 'settled:' + str(first.pk)), requested_by=self.user)
        models.Job.objects.filter(kind='analyze').update(state=models.Job.SUCCEEDED)
        job = self.run_next('interpret')
        self.assertEqual((job.pk, job.result), (again.pk, {'provider': 'read_before', 'run': str(first.pk),
                                                           'inventory': str(inventory.pk)}))
        self.assertEqual((len(interpreter.sent), len(self.interpret_runs(revision))), (1, 1))


class ReadFailureTests(InterpretCase):
    """FINAL 6.3, Read: an answer this server could not read to the end stays reusable (read again, nothing sent); stored
    bytes that no longer match their sha256 are a definite failure of the answer, with the retry door."""

    def test_a_process_that_cannot_vouch_for_its_writes_sends_nothing(self):
        interpreter = self.scripted(answered(envelope()))
        encounter, revision = self.through_extract()
        with mock.patch.object(sentinel, 'refusal', return_value='unavailable'):
            job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.FAILED, sentinel.MESSAGES['unavailable']))
        [run] = self.interpret_runs(revision)  # every outcome is a run (FINAL 6.3): this one says nothing was sent
        self.assertEqual((interpreter.sent, run.state, run.sent, run.scope['refused']), ([], 'not_sent', False,
                                                                                       'sentinel'))
        self.assertEqual(models.AuditEvent.objects.get(event=sentinel.TRIPPED).data['entry'], 'interpret.send')
        self.assertEqual(self.state(encounter), ('provider_not_run', None))
        self.assertEqual(progress.encounter_progress(encounter)['error'],
                         {'text': progress.INTERPRETATION_ERRORS['not_run'][0], 'action': 'none'})

    def test_the_live_gate_refuses_with_a_run_saying_nothing_was_sent(self):
        interpreter = self.scripted(answered(envelope()))
        interpreter.mode = 'live'
        encounter, revision = self.through_extract()
        with override_settings(AUTHORIZATION_REF=''):
            job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.FAILED,
                                                  'Live provider calls are not authorized on this installation.'))
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.state, run.scope['refused'], run.scope['mode'], interpreter.sent),
                         ('not_sent', 'live_gate', 'live', []))
        self.assertEqual(self.state(encounter), ('provider_not_run', None))

    def test_a_refused_write_gate_fails_the_stage_and_leaves_the_answer_reusable(self):
        interpreter = self.scripted(answered(envelope()))
        encounter, revision = self.through_extract()
        real_gate = sentinel.gate

        def write_refused(entry, **kwargs):  # the inventory write's gate refuses; the one before the send passes
            if entry == 'interpret':
                raise sentinel.Tripped('unavailable', {'entry': entry})
            return real_gate(entry, **kwargs)

        with mock.patch.object(sentinel, 'gate', side_effect=write_refused):
            job = self.run_next('interpret')
        self.assertEqual(len(interpreter.sent), 1)
        self.assertEqual((job.state, job.error), (models.Job.FAILED, sentinel.MESSAGES['unavailable']))
        [run] = self.interpret_runs(revision)
        self.assertNotIn('effect', run.scope)
        self.assertEqual(jobs.interpretation_effect(run), 'answered')
        self.assertFalse(models.EventInventory.objects.exists())
        self.assertEqual(self.state(encounter), ('processing_failed', None))
        _, second = self.through_extract()  # the same text uploaded again reads the stored answer: nothing is sent
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(len(interpreter.sent), 1)
        self.assertEqual(self.interpret_runs(second)[-1].reused_from_id, run.pk)
        self.assertEqual(models.EventInventory.objects.get(revision=second).state, 'read')

    def test_stored_bytes_that_no_longer_match_are_a_failure_of_the_answer(self):
        body = envelope()
        changed = RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=body,
                              response_sha256='0' * 64, usage=dict(USAGE), requested_model=interpretation.MODEL,
                              returned_model=interpretation.MODEL)
        interpreter = self.scripted(changed, answered(envelope()))
        encounter, revision = self.through_extract()
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.FAILED, jobs.STORED_ANSWER_CHANGED))
        [run] = self.interpret_runs(revision)
        self.assertEqual(run.scope['effect'], 'failed')
        self.assertEqual(self.state(encounter), ('provider_failed', run))
        self.assertEqual(progress.encounter_progress(encounter)['error']['action'], 'retry_reading')
        self.assertEqual(jobs.retry_target(revision), (run, run))
        jobs.retry_reading(encounter, self.user)
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(len(interpreter.sent), 2)


class FailedBeforeAndRetryTests(InterpretCase):
    """FINAL 6.3's failed-before door and 11.3's recorded retry."""

    def test_a_failed_reading_is_not_sent_again_until_a_recorded_retry_releases_it(self):
        failure = json.dumps({'error': {'code': 503, 'status': 'UNAVAILABLE', 'message': 'synthetic'}}).encode()
        interpreter = self.scripted(answered(failure, status=503), answered(envelope()))
        encounter, revision = self.through_extract()
        job = self.run_next('interpret')
        [failed] = self.interpret_runs(revision)
        self.assertEqual((job.state, failed.state, failed.sent, failed.scope['effect']),
                         (models.Job.FAILED, 'failed', True, 'failed'))
        self.assertFalse(models.InterpreterHold.objects.exists())
        self.assertEqual(self.state(encounter), ('provider_failed', failed))
        block = progress.encounter_progress(encounter)
        self.assertEqual(block['error'], {'text': progress.INTERPRETATION_ERRORS['failed'][0], 'action': 'retry_reading'})
        self.assertFalse(block['can_resume'])

        # any other attempt meets the failed-before door: a not-sent run, nothing sent
        jobs.enqueue('interpret', encounter=encounter, revision=revision, key=jobs._interpret_key(revision, 'again'),
                     requested_by=self.user)
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.FAILED, jobs.INTERPRET_NOT_RESENT_MESSAGE))
        kept = self.interpret_runs(revision)[-1]
        self.assertEqual((kept.state, kept.sent, kept.scope['refused'], kept.scope['failed'], kept.request_sha256),
                         ('not_sent', False, 'failed_before', str(failed.pk), failed.request_sha256))
        self.assertEqual(len(interpreter.sent), 1)
        self.assertEqual(progress.encounter_progress(encounter)['error']['action'], 'retry_reading')

        retry = jobs.retry_reading(encounter, self.user)
        failed.refresh_from_db()
        self.assertEqual((failed.reconciled_by_id, failed.reconciliation_note), (self.user.pk, jobs.RETRY_RELEASE_NOTE))
        self.assertEqual(retry.idempotency_key, f'interpret:{revision.pk}:gemini-events@1:retry:{failed.pk}')
        self.assertTrue(models.AuditEvent.objects.filter(event='interpretation.retry', encounter=encounter).exists())
        job = self.run_next('interpret')
        self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        self.assertEqual(len(interpreter.sent), 2)
        self.assertEqual(models.EventInventory.objects.get(revision=revision).state, 'read')
        with self.assertRaises(jobs.Refused):  # read now: nothing to retry
            models.Job.objects.filter(state=models.Job.QUEUED).delete()
            jobs.retry_reading(encounter, self.user)

    def test_one_release_is_one_attempt_and_a_retry_that_fails_again_blocks_again(self):
        failure = json.dumps({'error': {'code': 500, 'status': 'INTERNAL'}}).encode()
        interpreter = self.scripted(answered(failure, status=500), answered(failure, status=500), answered(envelope()))
        encounter, revision = self.through_extract()
        self.run_next('interpret')
        first = self.interpret_runs(revision)[-1]
        retry = jobs.retry_reading(encounter, self.user)
        # the retry stage stopped before it ran: asking again queues a stage of its own and releases nothing more
        models.Job.objects.filter(pk=retry.pk).update(state=models.Job.CANCELLED, error='Stopped by a workspace member.')
        again = jobs.retry_reading(encounter, self.user)
        self.assertTrue(again.idempotency_key.startswith(f'{retry.idempotency_key}:resume:'))
        self.assertEqual(models.ProviderRun.objects.filter(reconciliation_note=jobs.RETRY_RELEASE_NOTE).count(), 1)
        self.run_next('interpret')  # the one attempt the release allows: sent, and it fails again
        self.assertEqual(len(interpreter.sent), 2)
        second = self.interpret_runs(revision)[-1]
        self.assertEqual(jobs._interpretation_failed_before(encounter, interpreter, self.request_for(revision)), second)
        self.assertEqual(jobs.retry_target(revision), (second, second))
        jobs.retry_reading(encounter, self.user)  # a release of its own for the new failure
        self.assertEqual(Run.objects.get(pk=second.pk).reconciliation_note, jobs.RETRY_RELEASE_NOTE)
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(len(interpreter.sent), 3)
        self.assertEqual(Run.objects.get(pk=first.pk).reconciliation_note, jobs.RETRY_RELEASE_NOTE)

    def test_a_retry_is_refused_while_a_hold_stands(self):
        failure = json.dumps({'error': {'code': 503, 'status': 'UNAVAILABLE'}}).encode()
        self.scripted(answered(failure, status=503))
        encounter, revision = self.through_extract()
        self.run_next('interpret')
        failed = self.interpret_runs(revision)[-1]
        models.InterpreterHold.objects.create(reason='quota', http_status=429, run=failed)
        with self.assertRaisesMessage(jobs.Refused, jobs.RETRY_PAUSED):
            jobs.retry_reading(encounter, self.user)
        self.assertIsNone(Run.objects.get(pk=failed.pk).reconciled_at)

    def test_a_cut_off_answer_is_never_offered_a_paid_retry_unless_an_operator_overrides(self):
        """C5: MAX_TOKENS is persisted like any refusal; the member is told the document is too long."""
        interpreter = self.scripted(answered(envelope(finish='MAX_TOKENS')), answered(envelope()))
        encounter, revision = self.through_extract()
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.FAILED, jobs.INTERPRET_CUT_OFF_MESSAGE))
        [inventory] = models.EventInventory.objects.all()
        self.assertEqual((inventory.state, inventory.verification['stage']), ('refused', 'envelope'))
        [run] = self.interpret_runs(revision)
        self.assertEqual(run.scope['effect'], 'too_long')
        self.assertEqual(progress.encounter_progress(encounter)['error'],
                         {'text': progress.INTERPRETATION_ERRORS['too_long'][0], 'action': 'new_document'})
        with self.assertRaisesMessage(jobs.Refused, jobs.RETRY_TOO_LONG):
            jobs.retry_reading(encounter, self.user)
        self.assertIsNone(Run.objects.get(pk=run.pk).reconciled_at)
        jobs.retry_reading(encounter, self.user, override=True)
        self.assertEqual(models.AuditEvent.objects.get(event='interpretation.retry').data['override'], True)
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(len(interpreter.sent), 2)

    def test_a_retry_is_refused_while_a_stage_runs_or_with_nothing_to_retry(self):
        encounter, revision = self.through_extract()
        with self.assertRaisesMessage(jobs.Refused, jobs.RETRY_BUSY):  # the interpret stage is queued
            jobs.retry_reading(encounter, self.user)
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        with self.assertRaisesMessage(jobs.Refused, jobs.RETRY_NOTHING):
            jobs.retry_reading(encounter, self.user)


class UnknownOutcomeTests(InterpretCase):
    """FINAL 6.9 (reconcile) and 11.1 (an unknown outcome), with ADJUDICATION P-6."""

    def test_an_unknown_outcome_blocks_and_its_reconciliation_interprets_again(self):
        interpreter = self.scripted(UNKNOWN, answered(envelope()))
        encounter, revision = self.through_extract()
        job = self.run_next('interpret')
        [unknown] = self.interpret_runs(revision)
        self.assertEqual((job.state, job.result, unknown.state, unknown.sent, unknown.scope['effect']),
                         (models.Job.SUCCEEDED, {'provider': 'unknown', 'run': str(unknown.pk)}, 'unknown', True,
                          'unknown'))
        self.assertEqual(self.state(encounter)[0], 'provider_unknown')
        self.assertEqual(progress.encounter_progress(encounter)['phase'], 'being_confirmed')
        jobs.enqueue('interpret', encounter=encounter, revision=revision, key=jobs._interpret_key(revision, 'again'),
                     requested_by=self.user)
        self.assertEqual(self.run_next('interpret').result, {'blocked': jobs.INTERPRET_BLOCKED})
        self.assertEqual(len(interpreter.sent), 1)

        self.assertTrue(jobs.reconcile(encounter, unknown, self.user, NOTE))
        [queued] = self.queued()
        self.assertEqual((queued.kind, queued.idempotency_key),
                         ('interpret', f'interpret:{revision.pk}:gemini-events@1:after-reconcile:{unknown.pk}'))
        self.assertFalse(models.Job.objects.filter(kind='predict').exists())
        job = self.run_next('interpret')
        self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        self.assertEqual(len(interpreter.sent), 2)
        self.assertEqual(models.EventInventory.objects.get(revision=revision).state, 'read')

    def test_p6_a_reconciled_run_holding_an_answer_is_read_from_its_exchange_and_nothing_is_sent(self):
        """The run as the stage leaves an unknown outcome - its effect recorded 'unknown' - holding an answered exchange:
        the reconciliation's stage settles it from that exchange and reads it as its own answer."""
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        run = self.unknown_holding_an_answer(encounter, revision)
        self.assertEqual(run.scope['effect'], 'unknown')
        self.assertTrue(jobs.reconcile(encounter, run, self.user, NOTE))
        job = self.run_next('interpret')
        self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        run.refresh_from_db()
        self.assertEqual((run.state, run.http_status, run.scope.get(jobs.SETTLED_FROM_EXCHANGE), run.usage,
                          run.scope['effect']), ('succeeded', 200, True, USAGE, 'answered'))
        self.assertEqual(interpreter.sent, [])  # P-6: nothing is sent
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual((inventory.state, inventory.provider_run_id), ('read', run.pk))
        self.assertEqual(job.result, {'provider': 'succeeded', 'run': str(run.pk), 'inventory': str(inventory.pk)})
        self.assertEqual(len(self.interpret_runs(revision)), 1)  # read as its own answer: no run of the stage's own
        [analyze] = self.queued()
        self.assertEqual(analyze.idempotency_key, f'analyze:{revision.pk}:{inventory.pk}')

    def test_p6_decision_k_an_answer_whose_outcome_write_failed_is_read_after_reconciliation(self):
        """P-6 in the scenario it was adopted for, driven through the stage itself (decision (k)): the answer arrived and
        its exchange was committed as it ended (turn 1, HTTP 200), then the run's outcome could not be written, so
        _finish_loop recorded the run unknown and the stage recorded the effect 'unknown'. The reconciliation's stage
        settles the run from its exchange and reads that answer: it is never paid for again."""
        interpreter = self.scripted(answered(envelope()), answered(envelope()))
        encounter, revision = self.through_extract()
        real, calls = jobs._finish_run, []

        def outcome_write_fails_once(run, exchange):
            calls.append(exchange.outcome)
            if len(calls) == 1:
                raise RuntimeError('synthetic: the outcome write failed')
            return real(run, exchange)

        with mock.patch.object(jobs, '_finish_run', side_effect=outcome_write_fails_once), \
                self.assertLogs('studio.jobs', level='ERROR'):
            job = self.run_next('interpret')
        [run] = self.interpret_runs(revision)
        self.assertEqual((job.state, job.result, run.state, run.sent, run.scope.get('effect')),
                         (models.Job.SUCCEEDED, {'provider': 'unknown', 'run': str(run.pk)}, 'unknown', True,
                          'unknown'))
        self.assertEqual(list(run.exchanges.values_list('turn', 'state', 'http_status')), [(1, 'succeeded', 200)])
        self.assertEqual(len(interpreter.sent), 1)
        self.assertEqual(self.state(encounter)[0], 'provider_unknown')

        self.assertTrue(jobs.reconcile(encounter, run, self.user, NOTE))
        job = self.run_next('interpret')
        self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        self.assertEqual(len(interpreter.sent), 1)  # P-6: the answer CPT Studio holds is not requested again
        run.refresh_from_db()
        self.assertEqual((run.state, run.scope.get(jobs.SETTLED_FROM_EXCHANGE), run.scope.get('effect')),
                         ('succeeded', True, 'answered'))
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual((inventory.state, inventory.provider_run_id), ('read', run.pk))
        self.assertEqual(len(self.interpret_runs(revision)), 1)
        self.assertEqual([job.idempotency_key for job in self.queued()], [f'analyze:{revision.pk}:{inventory.pk}'])

    def test_p6_a_held_answer_naming_another_model_records_its_hold_against_its_own_run_and_sends_nothing(self):
        """P-6 with P-5: the answer an unknown run holds names another model. Settled from its exchange, it is never read
        and never paid for again: its hold is recorded against the run that was sent, and the stage pauses."""
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        run = self.unknown_holding_an_answer(encounter, revision, body=envelope(model='gemini-4-argon-preview'))
        self.assertTrue(jobs.reconcile(encounter, run, self.user, NOTE))
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, holds.PAUSED_MESSAGE))
        self.assertEqual(interpreter.sent, [])
        hold = models.InterpreterHold.objects.get()
        self.assertEqual((hold.reason, hold.run_id), ('model', run.pk))
        run.refresh_from_db()
        self.assertEqual((run.state, run.scope['effect'], run.returned_model),
                         ('succeeded', 'hold', 'gemini-4-argon-preview'))
        self.assertEqual(models.EventInventory.objects.get(provider_run=run).state, 'refused')
        self.assertEqual(len(self.interpret_runs(revision)), 1)
        self.assertFalse(models.Job.objects.filter(kind='analyze').exists())
        self.assertEqual(progress.encounter_progress(encounter)['phase'], 'paused')

    def test_an_effect_recorded_unknown_or_none_never_outlives_a_definite_outcome(self):
        """The effect the stage recorded describes the run as it was settled: P-6 drops it as it settles a run from its
        exchange, and 'unknown' or 'none' read on a run whose outcome is now definite is ignored - the run is classified
        from what it stores. A definite effect, and 'unknown' or 'none' where they still describe the run, stand."""
        encounter, revision = self.through_extract()
        run = self.unknown_holding_an_answer(encounter, revision)
        self.assertEqual(jobs.interpretation_effect(run), 'unknown')
        self.assertTrue(jobs._settle_from_exchange(run))
        self.assertNotIn('effect', run.scope)
        self.assertEqual(Run.objects.get(pk=run.pk).scope, {'mode': 'replay', jobs.SETTLED_FROM_EXCHANGE: True})
        self.assertEqual(jobs.interpretation_effect(run), 'answered')
        failure = json.dumps({'error': {'code': 503, 'status': 'UNAVAILABLE'}}).encode()
        for state, status, body, expected in ((Run.SUCCEEDED, 200, envelope(), 'answered'),
                                              (Run.FAILED, 503, failure, 'failed')):
            for stale in ('unknown', 'none'):
                Run.objects.filter(pk=run.pk).update(state=state, http_status=status, response_bytes=body,
                                                     response_sha256=hashlib.sha256(body).hexdigest(),
                                                     scope={'mode': 'replay', 'effect': stale})
                self.assertEqual(jobs.interpretation_effect(Run.objects.get(pk=run.pk)), expected, (state, stale))
        Run.objects.filter(pk=run.pk).update(state=Run.SUCCEEDED, scope={'mode': 'replay', 'effect': 'hold'})
        self.assertEqual(jobs.interpretation_effect(Run.objects.get(pk=run.pk)), 'hold')
        Run.objects.filter(pk=run.pk).update(state=Run.UNKNOWN, scope={'mode': 'replay', 'effect': 'unknown'})
        self.assertEqual(jobs.interpretation_effect(Run.objects.get(pk=run.pk)), 'unknown')
        Run.objects.filter(pk=run.pk).update(state=Run.NOT_SENT, scope={'mode': 'replay', 'effect': 'none'})
        self.assertEqual(jobs.interpretation_effect(Run.objects.get(pk=run.pk)), 'none')

    def test_p6_an_exchange_that_does_not_check_is_never_settled(self):
        encounter, revision = self.through_extract()
        run = self.unknown_holding_an_answer(encounter, revision)
        models.ProviderExchange.objects.filter(run=run).update(response_sha256='0' * 64)
        self.assertFalse(jobs._settle_from_exchange(run))
        models.ProviderExchange.objects.filter(run=run).update(
            response_sha256=hashlib.sha256(envelope()).hexdigest(), http_status=500)
        self.assertFalse(jobs._settle_from_exchange(run))
        self.assertEqual(Run.objects.get(pk=run.pk).state, 'unknown')

    def test_reconciling_any_run_on_a_revision_never_read_interprets_it(self):
        """FINAL 9: a reconciliation on a revision with no inventory read at the current versions is its first
        interpretation's explicit act - never a predict on a context that is not a gemini context."""
        encounter, revision = self.through_extract()
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        corti = Run.objects.create(encounter=encounter, revision=revision, provider='corti', adapter_version='x',
                                   request_sha256='a' * 64, request_body={}, contexts=[], state=Run.UNKNOWN, sent=True)
        self.assertTrue(jobs.reconcile(encounter, corti, self.user, NOTE))
        [queued] = self.queued()
        self.assertEqual(queued.idempotency_key,
                         f'interpret:{revision.pk}:gemini-events@1:after-reconcile:{corti.pk}')


class StaleSweepTests(InterpretCase):
    """FINAL 6.9 (mark_stale on a context-less interpret) with ADJUDICATION P-6."""

    def dead(self, revision):
        """The interpret stage of ``revision`` claimed by a worker that died 700 s ago."""
        job = models.Job.objects.get(revision=revision, kind='interpret')
        models.Job.objects.filter(pk=job.pk).update(state=models.Job.RUNNING,
                                                    started_at=timezone.now() - timedelta(seconds=700), attempts=1)
        job.refresh_from_db()
        return job

    def test_mark_stale_settles_an_answered_send_from_its_exchange_and_reads_it_with_nothing_sent(self):
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        job = self.dead(revision)
        run = self.unknown_holding_an_answer(encounter, revision, state=Run.SENDING)
        jobs.mark_stale()
        job.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual((run.state, run.scope.get(jobs.SETTLED_FROM_EXCHANGE)), ('succeeded', True))
        self.assertEqual((job.state, job.result['settled'], job.result['run']),
                         (models.Job.SUCCEEDED, jobs.STALE_INTERPRETATION, str(run.pk)))
        [settled] = self.queued()
        self.assertEqual(settled.idempotency_key, f'interpret:{revision.pk}:gemini-events@1:settled:{run.pk}')
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(interpreter.sent, [])
        self.assertEqual(models.EventInventory.objects.get(revision=revision).state, 'read')

    def test_mark_stale_leaves_a_send_with_no_recorded_answer_unknown(self):
        encounter, revision = self.through_extract()
        job = self.dead(revision)
        request = self.request_for(revision)
        run = Run.objects.create(encounter=encounter, revision=revision, provider='gemini',
                                 adapter_version=interpretation.ADAPTER_VERSION, request_sha256=request.canonical_sha256,
                                 request_body=request.body, contexts=[], state=Run.SENDING, sent=False,
                                 purpose=interpretation.PURPOSE, endpoint=ScriptedInterpreter.endpoint)
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual((job.state, Run.objects.get(pk=run.pk).state), (models.Job.UNKNOWN, 'unknown'))
        self.assertEqual(self.state(encounter)[0], 'provider_unknown')
        self.assertEqual(self.queued(), [])

    def test_mark_stale_settles_a_recorded_failure_through_the_classification(self):
        encounter, revision = self.through_extract()
        job = self.dead(revision)
        body = json.dumps({'error': {'code': 403, 'status': 'PERMISSION_DENIED'}}).encode()
        run = Run.objects.create(encounter=encounter, revision=revision, provider='gemini',
                                 adapter_version=interpretation.ADAPTER_VERSION, request_sha256='b' * 64,
                                 request_body={}, contexts=[], state=Run.FAILED, sent=True, http_status=403,
                                 response_bytes=body, response_sha256=hashlib.sha256(body).hexdigest(),
                                 purpose=interpretation.PURPOSE, started_at=timezone.now(), finished_at=timezone.now())
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, holds.PAUSED_MESSAGE))
        self.assertEqual(models.InterpreterHold.objects.get().reason, 'permission')
        self.assertEqual(Run.objects.get(pk=run.pk).scope['effect'], 'hold')

    def test_mark_stale_fails_an_interpret_whose_send_failed_outright(self):
        encounter, revision = self.through_extract()
        job = self.dead(revision)
        body = json.dumps({'error': {'code': 503, 'status': 'UNAVAILABLE'}}).encode()
        Run.objects.create(encounter=encounter, revision=revision, provider='gemini',
                           adapter_version=interpretation.ADAPTER_VERSION, request_sha256='c' * 64, request_body={},
                           contexts=[], state=Run.FAILED, sent=True, http_status=503, response_bytes=body,
                           response_sha256=hashlib.sha256(body).hexdigest(), purpose=interpretation.PURPOSE)
        jobs.mark_stale()
        job.refresh_from_db()
        self.assertEqual(job.state, models.Job.FAILED)
        self.assertFalse(models.InterpreterHold.objects.exists())
        self.assertEqual(self.state(encounter)[0], 'provider_failed')

    def test_p6_an_unknown_outcome_the_stale_sweep_settled_is_read_after_reconciliation(self):
        """The stage recorded its run unknown (the answer's exchange committed, the outcome write failed) and its worker
        died before the stage ended: the sweep settles the stage by that run (_stale_interpretation records 'unknown'),
        and the member's reconciliation reads the answer the run holds - nothing is sent."""
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        job = self.dead(revision)
        run = self.unknown_holding_an_answer(encounter, revision)
        jobs.mark_stale()
        job.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual((job.state, job.result['run'], run.state, run.scope['effect']),
                         (models.Job.SUCCEEDED, str(run.pk), 'unknown', 'unknown'))
        self.assertEqual((self.state(encounter)[0], self.queued()), ('provider_unknown', []))
        self.assertTrue(jobs.reconcile(encounter, run, self.user, NOTE))
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(interpreter.sent, [])
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual((inventory.state, inventory.provider_run_id), ('read', run.pk))

    def test_the_settled_path_records_a_substituted_model_answer_as_its_hold_and_sends_nothing(self):
        """FINAL 6.9 with P-5 and D11: the worker died after the answer was recorded SUCCEEDED and before the stage
        settled its outcome; the answer names another model. The settled path settles that run itself - its hold
        recorded against the run that was sent, the stage paused - and sends nothing: a substituted model's answer is not
        paid for again."""
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        job = self.dead(revision)
        run = self.answered_run(encounter, revision, envelope(model='gemini-4-argon-preview'))
        jobs.mark_stale()
        job.refresh_from_db()
        [settled] = self.queued()
        self.assertEqual((job.state, settled.idempotency_key),
                         (models.Job.SUCCEEDED, f'interpret:{revision.pk}:gemini-events@1:settled:{run.pk}'))
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, holds.PAUSED_MESSAGE))
        self.assertEqual(interpreter.sent, [])
        hold = models.InterpreterHold.objects.get()
        self.assertEqual((hold.reason, hold.run_id), ('model', run.pk))
        self.assertEqual(Run.objects.get(pk=run.pk).scope['effect'], 'hold')
        self.assertEqual(self.interpret_runs(revision), [run])  # nothing attempted: no run of the stage's own
        self.assertEqual(progress.encounter_progress(encounter)['phase'], 'paused')

    def test_a_released_hold_on_a_settled_answer_lets_a_members_resume_send_one_new_attempt(self):
        """After the settled path recorded a substituted model's hold, an operator's release and then a member's Resume -
        the explicit act every released hold waits on (FINAL 11.2) - send one new attempt, as after any hold; the answer
        the hold was set for is settled once and never read."""
        interpreter = self.scripted(answered(envelope()))
        encounter, revision = self.through_extract()
        self.dead(revision)
        run = self.answered_run(encounter, revision, envelope(model='gemini-4-argon-preview'))
        jobs.mark_stale()
        self.assertEqual(self.run_next('interpret').state, models.Job.CANCELLED)
        models.InterpreterHoldRelease.objects.create(hold=models.InterpreterHold.objects.get(), released_by=self.user,
                                                     note='Synthetic: the operator confirmed the model.')
        resumed = jobs.resume(encounter, self.user)
        self.assertEqual(resumed.idempotency_key.split(':resume:')[0],
                         f'interpret:{revision.pk}:gemini-events@1:settled:{run.pk}')
        job = self.run_next('interpret')
        self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        self.assertEqual(len(interpreter.sent), 1)
        inventory = models.EventInventory.objects.get(revision=revision, state='read')
        self.assertNotEqual(inventory.provider_run_id, run.pk)
        self.assertEqual((Run.objects.get(pk=run.pk).scope['effect'], models.InterpreterHold.objects.count()),
                         ('hold', 1))

    def test_the_settled_path_fails_a_cut_off_answer_as_cut_off_and_sends_nothing(self):
        """A cut-off answer the sweep left unsettled is settled as the stage would have settled it: read and refused at
        its output limit (C5), the member told the document is too long - and nothing is sent."""
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        self.dead(revision)
        run = self.answered_run(encounter, revision, envelope(finish='MAX_TOKENS'))
        jobs.mark_stale()
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.FAILED, jobs.INTERPRET_CUT_OFF_MESSAGE))
        self.assertEqual(interpreter.sent, [])
        self.assertEqual(Run.objects.get(pk=run.pk).scope['effect'], 'too_long')
        self.assertEqual(models.EventInventory.objects.get(provider_run=run).state, 'refused')
        self.assertEqual(self.interpret_runs(revision), [run])
        self.assertEqual(self.state(encounter), ('provider_failed', run))
        self.assertEqual(progress.encounter_progress(encounter)['error'],
                         {'text': progress.INTERPRETATION_ERRORS['too_long'][0], 'action': 'new_document'})

    def test_the_settled_path_never_sends_for_a_request_its_run_does_not_answer_until_a_member_resumes(self):
        """FINAL 6.9: the settled path sends nothing, whatever it finds. Here the stored answer answers another request
        (an upgrade changed the request between the stage that sent it and the stage that settles it), so nothing stored
        answers the request made now: the stage records that nothing was sent and ends resumable, and only a member's
        Resume - an explicit act - sends it."""
        interpreter = self.scripted(answered(envelope()))
        encounter, revision = self.through_extract()
        self.dead(revision)
        stale = self.answered_run(encounter, revision, envelope(), request_sha256='f' * 64)
        jobs.mark_stale()
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, jobs.INTERPRET_SETTLED_MESSAGE))
        self.assertEqual(interpreter.sent, [])
        kept = self.interpret_runs(revision)[-1]
        self.assertEqual((kept.state, kept.sent, kept.scope['refused'], kept.scope['effect'], kept.request_sha256),
                         ('not_sent', False, jobs.SETTLED, 'none', self.request_for(revision).canonical_sha256))
        self.assertFalse(models.EventInventory.objects.exists())
        block = progress.encounter_progress(encounter)
        self.assertEqual((block['phase'], block['can_resume']), ('stopped', True))
        resumed = jobs.resume(encounter, self.user)
        self.assertEqual(resumed.idempotency_key.split(':resume:')[0],
                         f'interpret:{revision.pk}:gemini-events@1:settled:{stale.pk}')
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(len(interpreter.sent), 1)
        self.assertEqual(models.EventInventory.objects.get(revision=revision).state, 'read')

    def test_the_settled_path_never_reads_an_answer_recorded_in_another_mode(self):
        """The settled path settles its run only where the stored-answer door would read it - the identical request, in
        the same mode: a live answer never stands in for a replay, nor a replayed one for a live request. Otherwise it
        reads nothing, sends nothing and ends resumable."""
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        self.dead(revision)
        run = self.answered_run(encounter, revision, envelope())
        Run.objects.filter(pk=run.pk).update(scope={'mode': 'live'})
        jobs.mark_stale()
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, jobs.INTERPRET_SETTLED_MESSAGE))
        self.assertEqual(interpreter.sent, [])
        self.assertFalse(models.EventInventory.objects.exists())
        self.assertNotIn('effect', Run.objects.get(pk=run.pk).scope)

    def orphaned(self, encounter, revision, *, answered_exchange=True):
        """A run left 'sending' 700 s ago by an interpret stage that no longer runs: the stage FAILED (decision (k): even
        _finish_loop's fallback write failed), so the dead-worker sweep never visits it."""
        models.Job.objects.filter(revision=revision, kind='interpret').update(
            state=models.Job.FAILED, created_at=timezone.now() - timedelta(seconds=800),
            started_at=timezone.now() - timedelta(seconds=750), finished_at=timezone.now() - timedelta(seconds=690))
        run = self.unknown_holding_an_answer(encounter, revision, state=Run.SENDING)
        if not answered_exchange:
            models.ProviderExchange.objects.filter(run=run).update(state='failed', http_status=503)
        Run.objects.filter(pk=run.pk).update(created_at=timezone.now() - timedelta(seconds=700))
        return run

    def test_p6_an_orphaned_sending_run_whose_exchange_answered_is_settled_and_read_with_nothing_sent(self):
        """ADJUDICATION P-6 in the decision-(k) orphan sweep: a run its stage left 'sending', whose one exchange answered
        (HTTP 200, a sha256 that checks), is settled SUCCEEDED from that exchange - never left unknown for a member's
        reconciliation - and its settled path reads it, with nothing sent."""
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        run = self.orphaned(encounter, revision)
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.error, run.http_status, run.scope.get(jobs.SETTLED_FROM_EXCHANGE)),
                         ('succeeded', '', 200, True))
        [settled] = self.queued()
        self.assertEqual(settled.idempotency_key, f'interpret:{revision.pk}:gemini-events@1:settled:{run.pk}')
        self.assertEqual(self.state(encounter)[0], 'processing')
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        self.assertEqual(interpreter.sent, [])
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual((inventory.state, inventory.provider_run_id), ('read', run.pk))
        self.assertEqual([job.idempotency_key for job in self.queued()], [f'analyze:{revision.pk}:{inventory.pk}'])

    def test_an_answered_orphan_of_an_earlier_revision_is_settled_and_queues_nothing(self):
        """The orphan's answer is settled from its exchange wherever it is - it no longer blocks the encounter as an
        unknown outcome - but only the current revision is read: a newer revision has its own interpretation."""
        interpreter = self.scripted()
        encounter, revision = self.through_extract()
        run = self.orphaned(encounter, revision)
        f.pasted_revision(encounter, self.user, TEXT + '\nSynthetic addendum: no further findings.')
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.scope.get(jobs.SETTLED_FROM_EXCHANGE)), ('succeeded', True))
        self.assertEqual(self.queued(), [])
        encounter.refresh_from_db()
        self.assertFalse(review._unreconciled_unknown(encounter))
        self.assertEqual(interpreter.sent, [])

    def test_an_orphaned_sending_run_with_no_answered_exchange_is_still_settled_unknown(self):
        encounter, revision = self.through_extract()
        run = self.orphaned(encounter, revision, answered_exchange=False)
        jobs.mark_stale()
        run.refresh_from_db()
        self.assertEqual((run.state, run.error, run.sent), ('unknown', jobs.ORPHANED_SENDING_MESSAGE, True))
        self.assertEqual((self.queued(), self.state(encounter)[0]), ([], 'provider_unknown'))


class AnalyzeTests(InterpretCase):
    """FINAL 6.4: analyze derives only, and the member-date hold is decided there."""

    def interpreted(self, body=None, **kwargs):
        encounter, revision = self.through_extract(**kwargs)
        self.record(revision, body)
        self.assertEqual(self.run_next('interpret').state, models.Job.SUCCEEDED)
        return encounter, revision, models.EventInventory.objects.get(revision=revision)

    def test_the_member_date_hold_is_decided_in_analyze(self):
        corti = FakeProvider(selections=[])
        with mock.patch.object(jobs, 'get_provider', return_value=corti):
            encounter, revision, inventory = self.interpreted(service_date='2026-10-01')
            job = self.run_next('analyze')
        self.assertEqual(job.result['member_date_state'], 'conflict_differs')
        encounter.refresh_from_db()
        context = encounter.current_context
        service = context.facts['service_date']
        self.assertEqual((service['origin'], service['value'], service['state']), ('conflict', None, 'conflict_differs'))
        self.assertEqual(service['note'], USER_CONFLICT_NOTE.format(user='2026-10-01', document='2026-11-09'))
        self.assertTrue(is_member_conflict(service))
        [held] = Run.objects.filter(revision=revision, provider='corti')
        self.assertEqual((held.state, held.scope, held.request_sha256),
                         ('not_sent', {'held': Run.HELD_MEMBER_DATE_CONFLICT}, ''))
        [queued] = self.queued()
        self.assertEqual((queued.kind, queued.provider_run_id, queued.context_id), ('assess', held.pk, context.pk))
        self.assertEqual(corti.sent, [])
        self.assertEqual(progress.encounter_progress(encounter)['phase'], 'action_needed')

    def test_a_legacy_analyze_key_is_cancelled_resumably(self):
        encounter, revision = self.through_extract()
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        jobs.enqueue('analyze', encounter=encounter, revision=revision, key=f'analyze:{revision.pk}',
                     requested_by=self.user)
        with mock.patch.object(jobs, '_analyze_child', side_effect=AssertionError('legacy analyze')):
            job = self.run_next('analyze')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, jobs.EARLIER_READING_MESSAGE))
        resumed = jobs.resume(encounter, self.user)
        self.assertEqual(resumed.kind, 'interpret')

    def test_an_analyze_of_a_refused_inventory_derives_nothing(self):
        interpreter = self.scripted(answered(envelope(text='[]')))
        encounter, revision = self.through_extract()
        self.run_next('interpret')
        refused = models.EventInventory.objects.get(revision=revision)
        jobs.enqueue('analyze', encounter=encounter, revision=revision, key=f'analyze:{revision.pk}:{refused.pk}',
                     requested_by=self.user)
        job = self.run_next('analyze')
        self.assertEqual((job.state, job.error), (models.Job.FAILED, jobs.INVENTORY_NOT_READ_MESSAGE))
        self.assertFalse(models.EncounterContext.objects.filter(revision=revision).exists())
        self.assertEqual(len(interpreter.sent), 1)


class PredictTests(InterpretCase):
    """FINAL 6.5: predict on a gemini context routes a new date by the stand-in; a legacy context is never sent."""

    def test_a_new_date_gets_the_routing_stand_in_and_never_the_legacy_router(self):
        corti = FakeProvider(selections=[])
        with mock.patch.object(jobs, 'get_provider', return_value=corti), \
                mock.patch.object(jobs, '_route_child', side_effect=AssertionError('legacy router')):
            encounter, revision = self.through_extract()
            self.record(revision, envelope(undated()))
            self.run_next('interpret')
            self.run_next('analyze')
            encounter.refresh_from_db()
            first = encounter.current_context
            self.assertEqual((first.facts['service_date']['origin'], first.facts['service_date']['value']),
                             ('missing', None))
            self.assertEqual(list(models.RoutingRun.objects.filter(revision=revision)
                                  .values_list('version', 'service_date')), [('gemini-routing@1', None)])
            models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)

            # a member supplies the date: the context derived again from the FROZEN inventory (no text, no send)
            encounter.user_values = {'service_date': '2026-11-09'}
            encounter.save(update_fields=['user_values'])
            inventory = first.event_inventory
            stored = jobs._stored_inventory(inventory, revision)
            derived = jobs.derived_facts(encounter, inventory, stored)
            self.assertEqual((derived.member_date.state, derived.effective), ('supplies', '2026-11-09'))
            context = jobs.record_derived_context(encounter, revision, inventory, derived, created_by=self.user)
            models.Encounter.objects.filter(pk=encounter.pk).update(current_context=context)
            jobs.enqueue('predict', encounter=encounter, revision=revision, context=context,
                         key=f'predict:{context.pk}', requested_by=self.user)
            job = self.run_next('predict')
        self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        stand_in = models.RoutingRun.objects.get(revision=revision, service_date=date(2026, 11, 9))
        self.assertEqual((stand_in.version, stand_in.result['inventory']), ('gemini-routing@1', str(inventory.pk)))
        [sent] = Run.objects.filter(revision=revision, provider='corti')
        self.assertEqual((sent.service_date, sent.state), (date(2026, 11, 9), 'succeeded'))
        self.assertEqual(len(corti.sent), 1)

    def test_a_legacy_context_is_never_remade_or_sent_and_resume_interprets(self):
        corti = FakeProvider(selections=[])
        encounter = f.encounter(self.ws, self.user)
        revision = f.pasted_revision(encounter, self.user, TEXT)
        legacy = models.EncounterContext.objects.create(
            encounter=encounter, revision=revision, version='gi-context@5', sha256='0' * 64,
            facts={'service_date': {'name': 'service_date', 'value': '2026-11-09', 'origin': 'document',
                                    'evidence': [], 'note': ''}})
        models.Encounter.objects.filter(pk=encounter.pk).update(current_context=legacy)
        jobs.enqueue('predict', encounter=encounter, revision=revision, context=legacy, key=f'predict:{legacy.pk}',
                     requested_by=self.user)
        with mock.patch.object(jobs, 'get_provider', return_value=corti), \
                mock.patch.object(jobs, 'make_context', side_effect=AssertionError('remade')):
            job = self.run_next('predict')
        self.assertEqual((job.state, job.error), (models.Job.CANCELLED, jobs.EARLIER_READING_MESSAGE))
        self.assertEqual((corti.sent, Run.objects.filter(revision=revision).count()), ([], 0))
        self.assertEqual(self.state(encounter)[0], 'stopped')
        resumed = jobs.resume(encounter, self.user)
        self.assertEqual((resumed.kind, resumed.context_id), ('interpret', None))


class SendPurposeTests(InterpretCase):
    """FINAL 6.3's send: the looped branch of _send with purpose 'interpretation'."""

    def test_the_send_is_one_recorded_exchange_naming_the_endpoint_and_model(self):
        interpreter = self.scripted(answered(envelope()))
        encounter, revision = self.through_extract()
        self.run_next('interpret')
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.endpoint, run.requested_model, run.returned_model, run.http_status, run.usage),
                         (ScriptedInterpreter.endpoint, 'gemini-4-argon', 'gemini-4-argon', 200, USAGE))
        [exchange] = run.exchanges.all()
        self.assertEqual((exchange.turn, exchange.state, exchange.http_status, exchange.request_sha256),
                         (1, 'succeeded', 200, run.request_sha256))
        self.assertEqual(exchange.tool_calls.count(), 0)
        self.assertEqual(interpreter.sent, [run.request_sha256])
        self.assertTrue(models.AuditEvent.objects.filter(event='provider.sending', encounter=encounter,
                                                         data__purpose='interpretation').exists())

    def test_a_stop_is_observed_before_the_one_send(self):
        interpreter = self.scripted(answered(envelope()))
        encounter, revision = self.through_extract()
        job = jobs.claim_next()
        models.Job.objects.filter(pk=job.pk).update(stop_requested_at=timezone.now())
        jobs.run_job(job)
        job.refresh_from_db()
        [run] = self.interpret_runs(revision)
        self.assertEqual((job.state, run.state, run.sent), (models.Job.CANCELLED, 'cancelled', False))
        self.assertEqual(interpreter.sent, [])

    def test_the_loop_deadline_is_the_purposes(self):
        _, revision = self.through_extract()
        job = models.Job.objects.get(revision=revision, kind='interpret')
        job.started_at = timezone.now() - timedelta(seconds=30)
        jobs._check_loop_time(job, interpretation.PURPOSE)  # 30 + 510 + 15 = 555 <= 560 (D49)
        job.started_at = timezone.now() - timedelta(seconds=40)
        with self.assertRaises(jobs.Requeue):  # 40 + 510 + 15 = 565 > 560
            jobs._check_loop_time(job, interpretation.PURPOSE)
        job.kind = 'astra'
        job.started_at = timezone.now() - timedelta(seconds=20)
        jobs._check_loop_time(job, Run.INDEPENDENT)  # 20 + 540 + 15 = 575 <= 580

    def test_the_interpreter_is_offered_no_tool(self):
        self.assertEqual(jobs._no_interpretation_tool('lookup_code', {'code': '45378'}),
                         ({'error': 'CPT Studio offers no tool to this request.'}, ()))


class ReviewAndProgressTests(InterpretCase):
    """FINAL 6.11 and review.estimated_cost for the interpreter's runs."""

    def run_of(self, **fields):
        encounter = f.encounter(self.ws, self.user)
        revision = f.pasted_revision(encounter, self.user, TEXT)
        return Run.objects.create(encounter=encounter, revision=revision, provider='gemini',
                                  adapter_version=interpretation.ADAPTER_VERSION, request_sha256='d' * 64,
                                  request_body={}, contexts=[], purpose=interpretation.PURPOSE,
                                  requested_model=interpretation.MODEL, **fields)

    def test_the_estimated_cost_of_an_interpretation_is_priced_on_the_day_it_was_sent(self):
        november = datetime(2026, 11, 9, 12, 0, tzinfo=dt_timezone.utc)
        run = self.run_of(state=Run.SUCCEEDED, sent=True, usage=USAGE, usage_basis='provider_reported_tokens',
                          started_at=november)
        self.assertEqual(review.estimated_cost(run), '0.0040')  # 1,000 x $2/M + 200 x $10/M
        unstarted = self.run_of(state=Run.SUCCEEDED, sent=True, usage=USAGE, usage_basis='provider_reported_tokens')
        self.assertIsNone(review.estimated_cost(unstarted))  # a dated rate needs its day
        self.assertIsNone(review.estimated_cost(self.run_of(state=Run.SUCCEEDED, usage={})))  # a reuse or a replay

    def test_failed_stage_states_of_an_interpret_stage(self):
        encounter, revision = self.through_extract()
        job = models.Job.objects.get(revision=revision, kind='interpret')
        job.state = models.Job.UNKNOWN
        self.assertEqual(review._failed_stage_state(encounter, revision, job), ('provider_unknown', None))
        job.state = models.Job.FAILED
        self.assertEqual(review._failed_stage_state(encounter, revision, job), ('provider_not_run', None))
        sending = Run.objects.create(encounter=encounter, revision=revision, provider='gemini',
                                     adapter_version=interpretation.ADAPTER_VERSION, request_sha256='e' * 64,
                                     request_body={}, contexts=[], state=Run.SENDING, purpose=interpretation.PURPOSE)
        self.assertEqual(review._failed_stage_state(encounter, revision, job), ('provider_unknown', None))
        Run.objects.filter(pk=sending.pk).update(state=Run.FAILED)
        self.assertEqual(review._failed_stage_state(encounter, revision, job)[0], 'provider_failed')

    def test_the_step_and_its_wording(self):
        self.assertEqual((progress.STEP_OF['interpret'], progress.DETAILS['interpret'],
                          progress.stage_bound('interpret')), ('identifying', 'Reading the documented procedures', 560))
        encounter, revision = self.through_extract()
        job = jobs.claim_next()
        block = progress.encounter_progress(encounter)
        self.assertEqual((block['phase'], block['active_detail']), ('processing', 'Reading the documented procedures'))
        self.assertEqual([step['state'] for step in block['steps']][:2], ['done', 'active'])
        self.assertNotIn('gemini', json.dumps(block).lower())
        self.assertEqual(job.kind, 'interpret')


class ReconciledRetryTests(InterpretCase):
    """DECISIONS D52 (the S17 refutation, finding 0): an operator's recorded reconciliation of an unknown outcome - who,
    when and the note, whose only copy is the run (the audit trail keeps no note text) - survives a retry release of the
    same run; the release is then the retry stage queued for it, keyed 'retry-release:<run>' (D60), which every door
    reads as the release."""

    NOTE = 'Synthetic operator note: the vendor console shows one answered request (D52 pin).'

    def unknown_after_outcome_write_failure(self, *after):
        interpreter = self.scripted(answered(envelope(text='{"passages": "not the schema"}')), *after)
        encounter, revision = self.through_extract()
        real, calls = jobs._finish_run, []

        def fails_once(run, exchange):
            calls.append(exchange.outcome)
            if len(calls) == 1:
                raise RuntimeError('synthetic: the outcome write failed')
            return real(run, exchange)
        with mock.patch.object(jobs, '_finish_run', side_effect=fails_once), self.assertLogs('studio.jobs', 'ERROR'):
            self.run_next('interpret')
        [run] = self.interpret_runs(revision)
        self.assertEqual(run.state, models.ProviderRun.UNKNOWN)
        return interpreter, encounter, revision, run

    def test_the_operators_reconciliation_survives_a_retry_and_the_release_is_read(self):
        operator_user = f.user('d52-operator')
        ops.grant(operator_user)
        interpreter, encounter, revision, run = self.unknown_after_outcome_write_failure()
        self.assertTrue(jobs.reconcile(encounter, run, operator_user, self.NOTE))
        run.refresh_from_db()
        recorded = (run.reconciled_by_id, run.reconciled_at, run.reconciliation_note)
        self.run_next('interpret')  # after-reconcile: settled from its exchange (P-6), the reading refused
        run.refresh_from_db()
        self.assertEqual((run.state, recorded[0], recorded[2]), ('succeeded', operator_user.pk, self.NOTE))
        self.assertFalse(jobs.released_for_retry(run))
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        job = jobs.retry_reading(encounter, self.user)
        run.refresh_from_db()
        self.assertEqual((run.reconciled_by_id, run.reconciled_at, run.reconciliation_note), recorded)
        self.assertTrue(jobs.released_for_retry(run))  # the release, read from the retry stage
        self.assertEqual(job.idempotency_key, jobs._interpret_key(revision, f'retry-release:{run.pk}'))  # D60
        # a second retry finds it released and writes nothing over the operator's record either
        models.Job.objects.filter(state=models.Job.QUEUED).update(state=models.Job.CANCELLED)
        jobs.retry_reading(encounter, self.user)
        run.refresh_from_db()
        self.assertEqual((run.reconciled_by_id, run.reconciled_at, run.reconciliation_note), recorded)

    def test_d60_a_reconciled_runs_release_is_its_retry_release_stage_and_lets_one_attempt_send(self):
        """D60 on D52's own path: the release of a run an operator reconciled is the retry stage keyed
        'retry-release:<run>' - the only key released_for_retry reads as a release - so the failed-before door lets that
        retry send its one attempt, and the operator's record is never written over."""
        operator_user = f.user('d60-operator')
        ops.grant(operator_user)
        interpreter, encounter, revision, run = self.unknown_after_outcome_write_failure(answered(envelope()))
        self.assertTrue(jobs.reconcile(encounter, run, operator_user, self.NOTE))
        self.run_next('interpret')  # after-reconcile: settled from its exchange (P-6), the reading refused
        run.refresh_from_db()
        recorded = (run.reconciled_by_id, run.reconciled_at, run.reconciliation_note)
        self.assertEqual((run.state, jobs.interpretation_effect(run), jobs.retry_target(revision)),
                         ('succeeded', 'failed', (run, run)))
        retry = jobs.retry_reading(encounter, self.user)
        key = jobs._interpret_key(revision, f'retry-release:{run.pk}')
        self.assertEqual(retry.idempotency_key, key)
        self.assertLessEqual(len(key) + len(':resume:') + 36, models.Job._meta.get_field('idempotency_key').max_length)
        self.assertTrue(jobs.released_for_retry(run))
        self.assertEqual(models.AuditEvent.objects.get(event='interpretation.retry').data['released'], True)
        job = self.run_next('interpret')  # the one attempt the release allows: sent, and read
        self.assertEqual(job.state, models.Job.SUCCEEDED, job.error)
        self.assertEqual(len(interpreter.sent), 2)
        self.assertEqual(models.EventInventory.objects.get(revision=revision, state='read').provider_run_id,
                         self.interpret_runs(revision)[-1].pk)
        run.refresh_from_db()
        self.assertEqual((run.reconciled_by_id, run.reconciled_at, run.reconciliation_note), recorded)


class UnreadAnswerRetryTests(InterpretCase):
    """DECISIONS D60 (the round-2 refutation, finding 15): only a retry that RELEASED a run reads as a release. A usable
    answer whose reading failed on this server has nothing to release (retry_target); its retry is keyed 'retry:<run>',
    which is never read as a release - nor is a Resume of it - so the stored-answer door reads the answer again with
    nothing sent, and a later upload of the same text in the workspace reuses it too, whether or not that retry ran."""

    def overran(self):
        """A usable answer, sent and stored, whose reading overran on this server (a genuine bounded.Overrun: no reading
        time, for this stage only): the stage failed, nothing was read, and the answer stays reusable (_read_answer)."""
        interpreter = self.scripted(answered(envelope()), answered(envelope()))
        encounter, revision = self.through_extract()
        with override_settings(JOB_DEADLINE_SECONDS={**settings.JOB_DEADLINE_SECONDS, 'analyze': 0}):
            job = self.run_next('interpret')
        self.assertEqual((job.state, job.error), (models.Job.FAILED, jobs.READ_OVERRUN_MESSAGE.format(reason='time')))
        [run] = self.interpret_runs(revision)
        self.assertEqual((run.state, run.sent, jobs.interpretation_effect(run)), ('succeeded', True, 'answered'))
        self.assertNotIn('effect', run.scope)
        self.assertFalse(models.EventInventory.objects.exists())
        self.assertEqual(self.state(encounter), ('processing_failed', None))
        self.assertEqual(jobs.retry_target(revision), (run, None))  # nothing to release: the answer was never read
        return interpreter, encounter, revision, run

    def test_d60_a_retry_of_a_usable_answer_whose_reading_overran_reads_it_again_with_nothing_sent(self):
        interpreter, encounter, revision, run = self.overran()
        retry = jobs.retry_reading(encounter, self.user)
        self.assertEqual(retry.idempotency_key, jobs._interpret_key(revision, f'retry:{run.pk}'))
        run.refresh_from_db()
        self.assertIsNone(run.reconciled_at)
        self.assertFalse(jobs.released_for_retry(run))
        self.assertEqual(jobs._retained_interpretation(encounter, interpreter, self.request_for(revision)), run)
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.result['provider']), (models.Job.SUCCEEDED, 'reused'), job.error)
        self.assertEqual(len(interpreter.sent), 1)  # one send in all: the retry read the stored answer
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual((inventory.state, Run.objects.get(pk=inventory.provider_run_id).reused_from_id),
                         ('read', run.pk))

    def test_d60_a_stopped_retry_leaves_the_unread_answer_reusable_by_a_new_upload(self):
        interpreter, encounter, revision, run = self.overran()
        retry = jobs.retry_reading(encounter, self.user)
        self.assertEqual(jobs.stop_encounter(encounter, self.user), 1)  # stopped before it ran
        retry.refresh_from_db()
        self.assertEqual(retry.state, models.Job.CANCELLED)
        self.assertFalse(jobs.released_for_retry(run))
        _, second = self.through_extract()  # the same text, uploaded again in the workspace
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.result['provider']), (models.Job.SUCCEEDED, 'reused'), job.error)
        self.assertEqual(self.interpret_runs(second)[-1].reused_from_id, run.pk)
        self.assertEqual(len(interpreter.sent), 1)

    def test_d60_a_resume_of_that_retry_is_no_release_either(self):
        interpreter, encounter, revision, run = self.overran()
        retry = jobs.retry_reading(encounter, self.user)
        jobs.stop_encounter(encounter, self.user)
        resumed = jobs.resume(encounter, self.user)
        self.assertEqual(resumed.idempotency_key.split(':resume:')[0], retry.idempotency_key)
        self.assertFalse(jobs.released_for_retry(run))
        job = self.run_next('interpret')
        self.assertEqual((job.state, job.result['provider']), (models.Job.SUCCEEDED, 'reused'), job.error)
        self.assertEqual(len(interpreter.sent), 1)
