"""End-to-end pipeline + API tests with a fake provider (no network).

The Gemini migration (design/FINAL.md 14.6; slice S15) put an interpret stage between extract and analyze. The tests
here that assert the pipeline's MECHANICS - the upload API, the send discipline (one send, the retained answer reused,
nothing sent when the request cannot be built), Stop, the unknown outcome and its reconciliation, the provider lock,
addenda and report bytes - run the production chain: extract, interpret, analyze (derive only), predict, assess. Gemini
is the replay interpreter over ONE RECORDED SYNTHETIC INTERPRETATION PER FIXTURE DOCUMENT (RecordedInterpretation;
OFFICE_NOTE's is OFFICE_INTERPRETATION), and Corti is the in-process FakeProvider. The one test that asserts what the
LEGACY reader read in the document - the full flow's selected proposals - is a reading-outcome test, kept as a legacy
regression test under the test-only legacy chain (LegacyReadingTests; tests/legacy_chain.py)."""
import copy
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from unittest import mock

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from studio import interpretation, jobs, models, review
from studio.ingest import extract_paste
from studio.interpretation import adapter as interpretation_adapter
from studio.interpretation import normalize, read
from studio.interpretation.replay import ReplayInterpreter
from studio.providers.base import ProviderUnavailable
from studio.providers.corti import ADAPTER_VERSION
from studio.types import ProviderRequest, RawExchange, sha256_json
from tests import legacy_chain as legacy_chain_module
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.support.operator import OperatorReads

OFFICE_NOTE = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE

Riverbend Digestive Health (fictional)
Date of service: 2026-10-20
Place of service: Office, in-person outpatient visit
Patient status: Established patient, last seen 2026-03-02.

Chief complaint
Follow-up of chronic constipation.

Assessment and plan
Chronic idiopathic constipation, improved. Continue polyethylene glycol daily.
A colonoscopy is scheduled for 2026-12-01.

Medical decision making
Low: one stable chronic illness; prescription drug management.

Time
Total time on the date of the encounter was 24 minutes.
"""


def corti_like_response(text, selections):
    """A provider response in Corti's shape whose evidence points at exact substrings of text."""
    codes = []
    for code, quote in selections:
        start = text.index(quote)
        codes.append({'system': 'cpt', 'code': code, 'display': 'UNVERIFIED PROVIDER WORDING',
                      'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(quote), 'text': quote}],
                      'alternatives': []})
    return json.dumps({'codes': codes, 'candidates': [], 'usageInfo': {'creditsConsumed': 0.02}}).encode()


class FakeProvider:
    """Behaves like the live Corti adapter (same name and adapter version, so the stored run is read
    by the real normaliser) but 'sends' to an in-process stub — no network."""
    name, adapter_version, mode = 'corti', ADAPTER_VERSION, 'live'

    def __init__(self, selections=(), outcome='succeeded'):
        self.selections, self.outcome, self.sent = list(selections), outcome, []

    def build_request(self, text, service_date):
        contexts = [text] + ([f'Date of service: {service_date.isoformat()}'] if service_date else [])
        body = {'system': ['icd10cm-outpatient', 'cpt'], 'context': [{'type': 'text', 'text': c} for c in contexts]}
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(',', ':'),
                                           ensure_ascii=False).encode()).hexdigest()
        return ProviderRequest(provider=self.name, adapter_version=self.adapter_version, body=body,
                               canonical_sha256=digest, contexts=tuple(contexts))

    def send(self, request, *, deadline_s):
        self.sent.append(request.canonical_sha256)
        if self.outcome == 'unknown':
            return RawExchange(outcome='unknown', sent=True, error='Read timed out after the request was sent.')
        data = corti_like_response(request.contexts[0], self.selections)
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=12.5,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


def drain():
    while True:
        job = jobs.claim_next()
        if job is None:
            return
        jobs.run_job(job)


# --- one recorded synthetic interpretation per fixture document (design/FINAL.md 14.6) --------------------------------

def _stated(value, words='', passages=()):
    """An attribute as Gemini gives it (contract 3.2): its value, the words stating it and their passages."""
    return {'value': value, 'words': words, 'passages': list(passages)}


def synthetic_event(eid, procedure, kind, status, *, time=None, technique=None, target=None, scope=None):
    """An event of a synthetic interpretation: ``procedure``, ``kind`` and ``status`` are (value, words, passage) - a
    procedure's words may be '' (its value then the procedure default) - and ``technique`` (value, words, passage),
    ``target`` (lesion, landmark, words, passage) and ``scope`` (value, words, passage) are given when the document
    states them; the time is this encounter's and the performer the documenting team's (the frame defaults) unless
    ``time`` is given."""
    def stated(item):
        return _stated(item[0], item[1], [item[2]] if item[1] else [])
    return {'id': eid, 'procedure': stated(procedure), 'kind': stated(kind),
            'technique': stated(technique) if technique else _stated('not_stated'),
            'target': ({'lesion': target[0], 'landmark': target[1], 'words': target[2], 'passages': [target[3]]}
                       if target else {'lesion': '', 'landmark': 'not_stated', 'words': '', 'passages': []}),
            'time': time or _stated('current_encounter'), 'performer': _stated('documenting_team'),
            'status': stated(status),
            'scope': ({'value': scope[0], 'targets': [], 'words': scope[1], 'passages': [scope[2]]} if scope
                      else {'value': 'not_applicable', 'targets': [], 'words': '', 'passages': []}),
            'purpose': _stated('not_stated'), 'part_of': '', 'sequence': 0, 'contradicts': []}


def synthetic_lesion(lid, words, passage, landmark, site_words, size_words):
    """A lesion of a synthetic interpretation, stated in ``passage``: one lesion, its site and size words given."""
    return {'id': lid, 'words': words, 'landmark': landmark, 'site_words': site_words, 'size_words': size_words,
            'multiplicity': 'single', 'passages': [passage]}


def synthetic_interpretation(passages, *, date=None, reach=(), lesions=(), events=(), visit_facts=()):
    """Gemini's synthetic answer (schema gemini-events@1) over ``passages`` ({id: a line of the document}): the date of
    service stated by ``date`` (value, words, passage) or not stated; ``reach`` entries (event, landmark, words,
    passage), the lesions and events (synthetic_lesion, synthetic_event) and the visits' facts given."""
    if date:
        stated = {'value': date[0], 'state': 'stated', 'words': date[1], 'passages': [date[2]], 'other_dates': []}
    else:
        stated = {'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []}
    return {'passages': [{'id': pid, 'text': text} for pid, text in passages.items()],
            'encounter': {'date_of_service': stated, 'documenting_endoscopist': {'words': '', 'passages': []},
                          'team': [], 'anatomy': [],
                          'reach': [{'event': event, 'landmark': landmark, 'words': words, 'passages': [passage],
                                     'completion': _stated('not_stated')} for event, landmark, words, passage in reach],
                          'visit_facts': list(visit_facts)},
            'lesions': list(lesions), 'events': list(events), 'open_questions': []}


# Gemini's synthetic answer to OFFICE_NOTE (schema gemini-events@1): every passage a line of the note, every claimed
# attribute verified by normalization - the office visit of 2026-10-20 (its basis the stated total time) and the
# colonoscopy scheduled for a later date.
OFFICE_INTERPRETATION = {
    'passages': [{'id': 'P1', 'text': 'Date of service: 2026-10-20'},
                 {'id': 'P2', 'text': 'Place of service: Office, in-person outpatient visit'},
                 {'id': 'P3', 'text': 'Total time on the date of the encounter was 24 minutes.'},
                 {'id': 'P4', 'text': 'A colonoscopy is scheduled for 2026-12-01.'}],
    'encounter': {'date_of_service': {'value': '2026-10-20', 'state': 'stated', 'words': '2026-10-20',
                                      'passages': ['P1'], 'other_dates': []},
                  'documenting_endoscopist': {'words': '', 'passages': []}, 'team': [], 'anatomy': [], 'reach': [],
                  'visit_facts': [{'event': 'E1', 'basis': _stated('total_time', '24 minutes', ['P3']),
                                   'separately_identifiable': _stated('not_stated')}]},
    'lesions': [],
    'events': [synthetic_event('E1', ('office_em', 'Office', 'P2'), ('em_visit', 'in-person outpatient visit', 'P2'),
                               ('performed', 'in-person outpatient visit', 'P2')),
               synthetic_event('E2', ('colonoscopy', 'colonoscopy', 'P4'), ('examination', 'colonoscopy', 'P4'),
                               ('planned', 'is scheduled', 'P4'),
                               time=_stated('future', 'scheduled for 2026-12-01', ['P4']))],
    'open_questions': []}


# The state a finished production chain leaves an OFFICE_NOTE (or NO_DATE_NOTE) encounter in: the visit's setting and
# patient status come only from member values there (DECISIONS D3), so 99213 waits on them and the encounter needs
# clarification - where the legacy reader, reading both in the note, left it ready for review. A mechanics test that
# asserted 'ready_for_review' as the end of its chain asserts this on the production chain: a chain left unfinished,
# stopped or failed still fails it.
OFFICE_NOTE_STATE = 'needs_clarification'


def gemini_answer(answer) -> bytes:
    """The raw body of Gemini's 200 answer carrying ``answer`` (a recording's bytes, contract 2.3)."""
    return json.dumps({'candidates': [{'content': {'parts': [{'text': json.dumps(answer)}], 'role': 'model'},
                                       'finishReason': 'STOP', 'index': 0}],
                       'modelVersion': interpretation.MODEL, 'responseId': 'synthetic-s15',
                       'usageMetadata': {'promptTokenCount': 1000, 'candidatesTokenCount': 200,
                                         'totalTokenCount': 1200}}).encode()


def with_addendum(answer, passages, **encounter):
    """Gemini's synthetic answer to an ADDENDUM revision of the document ``answer`` reads (design/FINAL.md 14.6): an
    addendum revision's text is its parent's followed by the addendum block, so the parent's passages and events are
    still its own; ``passages`` ({id: text}) are the addendum's own lines and ``encounter`` the encounter facts the
    addendum states (each replacing the parent's - a date of service it states, say). What the addendum says is read
    from its words, never assumed from its parent: a test that posts an addendum registers this answer for that exact
    revision (RecordedInterpretation.register_addendum)."""
    value = copy.deepcopy(answer)
    taken = {item['id'] for item in value['passages']}
    for pid, text in passages.items():
        if pid in taken:
            raise ValueError(f'The parent answer already has a passage {pid}.')
        value['passages'].append({'id': pid, 'text': text})
    value['encounter'].update(copy.deepcopy(encounter))
    return value


class RecordedReplayInterpreter(ReplayInterpreter):
    """The production replay interpreter (studio/interpretation/replay.py) whose recordings are a test's synthetic
    interpretations. Before a request is replayed, its recording is written from the interpretation registered for
    EXACTLY the document the request carries (its contexts[0], the revision text). Nothing else matches: an addendum
    revision - its parent's text followed by the addendum block - is a document of its own, read only from an answer
    registered for it, so an addendum's words are never read as if they were not there. The recording is keyed as a
    live answer's is, by the request's canonical sha256, and the stage reads, normalizes and stores it through the
    production path. A document with no registered interpretation gets no recording: the replay answers 'No recorded
    response', as it would in production, and the document is listed in ``unrecorded``."""

    def __init__(self, replay_dir, interpretations, **limits):
        super().__init__(replay_dir, **limits)
        self.interpretations = interpretations  # (document text, answer) pairs, read at each send: a live registry
        self.replayed = []  # the canonical sha256 of every request it was asked to send, in order
        self.unrecorded = []  # the documents (revision texts) it met with no registered interpretation

    def answer_for(self, text):
        """The answer registered for exactly ``text``, else None."""
        for document, answer in self.interpretations:
            if document == text:
                return answer
        return None

    def _record(self, request):
        self.replayed.append(request.canonical_sha256)
        document = request.contexts[0] if request.contexts else ''
        answer = self.answer_for(document)
        if answer is None:
            self.unrecorded.append(document)
            return
        folder = self.replay_dir / interpretation_adapter.NAME
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f'{request.canonical_sha256}.json').write_bytes(gemini_answer(answer))

    def send(self, request, **kwargs):
        self._record(request)
        return super().send(request, **kwargs)

    def send_loop(self, request, **kwargs):
        self._record(request)
        return super().send_loop(request, **kwargs)


class RecordedInterpretation:
    """A TestCase mixin, first among the bases (FINAL 14.6, the mechanics side): the interpreter is the replay
    interpreter (GEMINI_MODE 'replay', a replay directory of the test's own) over ``interpretations`` - (document text,
    Gemini's synthetic answer) pairs, one per fixture document the class uploads - so every upload takes the production
    chain. ``interpreters`` lists every interpreter the stages were given, in order. The registry is matched by exact
    revision text: a test that posts an addendum registers that revision's own interpretation (register_addendum). A
    test that asked the interpreter to read a document with no registered interpretation - an unregistered addendum
    revision included - fails once it ends: a test switched to the production chain never passes on a reading that
    silently did not happen. The recorder is set up before the test's own setUp runs, whether or not that setUp calls
    super()."""
    interpretations = ((OFFICE_NOTE, OFFICE_INTERPRETATION),)

    def _callSetUp(self):
        # unittest calls every test's setUp from here (TestCase.run and TestCase.debug): the recorder is in place first,
        # so a class whose own setUp never calls super() cannot take the production chain without its recordings
        self._set_up_the_recorder()
        super()._callSetUp()

    def _set_up_the_recorder(self):
        self.addCleanup(self._every_document_was_recorded)
        replay_dir = tempfile.mkdtemp(prefix='s15-replay-')
        self.addCleanup(shutil.rmtree, replay_dir, True)
        replay = override_settings(GEMINI_MODE='replay', GEMINI_REPLAY_DIR=replay_dir)
        replay.enable()
        self.addCleanup(replay.disable)
        self.interpreters = []
        self.recorded = []  # this test's registry: the class's interpretations, then any the test registers
        for text, answer in self.interpretations:
            self.register(text, answer)
        original = interpretation_adapter.get_interpreter

        def get_interpreter(mode=None):
            if mode not in (None, 'replay'):
                return original(mode)
            interpreter = RecordedReplayInterpreter(Path(replay_dir), self.recorded)
            self.interpreters.append(interpreter)
            return interpreter
        patcher = mock.patch.object(interpretation_adapter, 'get_interpreter', side_effect=get_interpreter)
        patcher.start()
        self.addCleanup(patcher.stop)

    def register(self, text, answer):
        """Record Gemini's synthetic ``answer`` for the document whose revision text is exactly ``text``: one answer per
        document (the same answer again changes nothing - two encounters can hold one text)."""
        known = [recorded for document, recorded in self.recorded if document == text]
        if known and known[0] != answer:
            raise AssertionError('That document already has another recorded synthetic interpretation.')
        if not known:
            self.recorded.append((text, answer))

    def register_addendum(self, encounter_id, answer):
        """Record ``answer`` (with_addendum's) for the addendum revision just added to the encounter - its current
        revision, not yet extracted - by the exact text extract will record for it: the parent's text and the addendum
        block, as studio/jobs.py stage_extract composes them. Returns that text."""
        revision = models.Encounter.objects.get(pk=encounter_id).current_revision
        if revision.kind != models.SourceRevision.ADDENDUM or revision.parent is None:
            raise AssertionError('The encounter\'s current revision is not an addendum revision.')
        text = extract_paste(revision.parent.text + jobs.addendum_block(revision), method='addendum').text
        self.register(text, answer)
        return text

    def register_addendum_lines(self, encounter_id, *lines, **encounter):
        """register_addendum for an addendum whose words are ``lines`` and state the encounter facts ``encounter`` (a date
        of service, say) and nothing else: the answer registered for its parent's exact text, with each line a passage
        of its own (with_addendum). Returns the addendum revision's text."""
        parent = models.Encounter.objects.get(pk=encounter_id).current_revision.parent
        [answer] = [answer for document, answer in self.recorded if parent is not None and document == parent.text]
        taken = {item['id'] for item in answer['passages']}
        ids = (f'A{number}' for number in range(1, 100) if f'A{number}' not in taken)
        return self.register_addendum(encounter_id, with_addendum(answer, dict(zip(ids, lines)), **encounter))

    def _every_document_was_recorded(self):
        unrecorded = [document for interpreter in self.interpreters for document in interpreter.unrecorded]
        if unrecorded:
            self.fail(f'{len(unrecorded)} interpretation request(s) for a document with no recorded synthetic '
                      f'interpretation; the first begins {unrecorded[0][:80]!r} and ends {unrecorded[0][-80:]!r}')

    def interpretation_runs(self, encounter_id):
        return list(models.ProviderRun.objects.filter(encounter_id=encounter_id, purpose=interpretation.PURPOSE)
                    .order_by('created_at', 'pk'))

    def replayed(self):
        """Every interpretation request the stages asked the interpreter to send, in order (their sha256)."""
        return [sha for interpreter in self.interpreters for sha in interpreter.replayed]


def recorded_addendum(test, encounter_id, *lines, **encounter):
    """Where ``test`` takes the production chain (RecordedInterpretation), RecordedInterpretation.register_addendum_lines
    for the addendum just posted to the encounter, before the pipeline reads it; on the legacy chain no interpreter reads
    it, and nothing is registered. For a helper both chains' tests share."""
    if isinstance(test, RecordedInterpretation):
        return test.register_addendum_lines(encounter_id, *lines, **encounter)
    return None


@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class PipelineApiCase(OperatorReads, TestCase):
    """The upload client, Corti's fake and the helpers both chains' tests use."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self, text=OFFICE_NOTE, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def detail(self, encounter_id, client=None):
        response = (client or self.client).get(f'/ops/api/encounters/{encounter_id}')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def post(self, path, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data), content_type='application/json')

    @staticmethod
    def primary_runs(data):
        """The encounter payload's runs of Corti's primary request (purpose 'primary'), oldest first: the runs these
        tests assert about. On the production chain the interpretation's own run is served beside them (FINAL 6.3)."""
        return [run for run in data['provider_runs'] if run['purpose'] == models.ProviderRun.PRIMARY]


class PipelineApiTests(RecordedInterpretation, PipelineApiCase):
    """The upload API and the pipeline's mechanics on the production chain (FINAL 14.6): Gemini reads each upload from
    its recorded synthetic interpretation, and the assertions are the ones these tests always made - where one names
    "the" run of an encounter, it is Corti's primary run, which the interpretation's own run now stands beside."""

    def test_an_upload_here_takes_the_production_chain(self):
        """The positive control of the switch: the stages, the recorded interpretation read once, the gemini context
        derived from its inventory, the predict on that context and the events engine's assessment."""
        encounter_id = self.create()
        drain()
        jobs_run = list(models.Job.objects.filter(encounter_id=encounter_id).order_by('created_at', 'pk'))
        self.assertEqual([(job.kind, job.state) for job in jobs_run],
                         [('extract', 'succeeded'), ('interpret', 'succeeded'), ('analyze', 'succeeded'),
                          ('predict', 'succeeded'), ('assess', 'succeeded')])
        [run] = self.interpretation_runs(encounter_id)
        self.assertEqual((run.provider, run.state, run.scope.get('mode')),
                         (interpretation.PROVIDER, 'succeeded', 'replay'))
        self.assertEqual(self.replayed(), [run.request_sha256])
        inventory = models.EventInventory.objects.get(provider_run=run)
        self.assertEqual(inventory.state, models.EventInventory.READ)
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertTrue(interpretation.is_new_context(encounter.current_context))
        self.assertEqual(encounter.current_context.event_inventory_id, inventory.pk)
        self.assertEqual(encounter.current_context.facts['service_date']['value'], '2026-10-20')
        self.assertTrue(interpretation.is_new_assessment(encounter.current_assessment))
        self.assertEqual(len(self.provider.sent), 1)

    def test_upload_requires_attestation_and_one_source(self):
        self.assertEqual(self.client.post('/api/encounters', {'text': 'x'}).status_code, 400)
        self.assertEqual(self.client.post('/api/encounters', {'synthetic_attestation': 'yes'}).status_code, 400)

    def test_cross_workspace_access_is_404(self):
        encounter_id = self.create()
        other_ws = f.workspace('Other synthetic workspace')
        outsider = f.member(other_ws, f.user('outsider'))
        client = Client()
        client.force_login(outsider)
        self.assertEqual(client.get(f'/api/encounters/{encounter_id}').status_code, 404)
        self.assertEqual(client.post(f'/api/encounters/{encounter_id}/stop').status_code, 404)

    def test_unauthenticated_api_is_401(self):
        self.assertEqual(Client().get('/api/encounters').status_code, 401)

    def test_csrf_is_enforced_on_posts(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.reviewer)
        response = client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 403)

    def test_viewer_cannot_upload_or_decide(self):
        viewer = f.member(self.ws, f.user('viewer'), role=models.Membership.VIEWER)
        client = Client()
        client.force_login(viewer)
        response = client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 403)

    def test_identical_request_reuses_retained_result_without_sending(self):
        first = self.create()
        drain()
        second = self.create()
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        run = models.ProviderRun.objects.filter(encounter_id=second, purpose=models.ProviderRun.PRIMARY).get()
        self.assertIsNotNone(run.reused_from_id)
        self.assertEqual(run.usage, {})
        self.assertEqual(run.usage_basis, 'reused_retained_result_no_new_usage')
        self.assertEqual(self.primary_runs(self.detail(first))[0]['reused_from'], None)

    def test_stop_before_send_sends_nothing(self):
        encounter_id = self.create()
        response = self.client.post(f'/api/encounters/{encounter_id}/stop')
        self.assertEqual(response.status_code, 200)
        drain()
        self.assertEqual(self.provider.sent, [])
        self.assertEqual(self.detail(encounter_id)['state'], 'stopped')

    def test_unknown_outcome_blocks_resend_until_reconciled(self):
        self.provider.outcome = 'unknown'
        encounter_id = self.create()
        drain()
        data = self.detail(encounter_id)
        self.assertEqual(data['state'], 'provider_unknown')
        self.assertEqual(len(self.provider.sent), 1)
        run_id = self.primary_runs(data)[0]['id']
        # Adding context does not resend while the outcome is unknown.
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        # A reconciliation note is required, then exactly one new attempt happens.
        self.assertEqual(self.post(f'/ops/api/encounters/{encounter_id}/reconcile',
                                   {'provider_run_id': run_id, 'note': 'short'}).status_code, 400)
        self.provider.outcome = 'succeeded'
        response = self.post(f'/ops/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': run_id, 'note': 'Checked the provider console: no response recorded.'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        self.assertEqual(len(self.provider.sent), 2)
        self.assertEqual(self.post(f'/ops/api/encounters/{encounter_id}/reconcile',
                                   {'provider_run_id': run_id, 'note': 'Second reconciliation attempt.'}).status_code, 409)

    def test_addendum_creates_revision_and_invalidates_decisions(self):
        """A decision recorded on revision 1 is invalidated by the addendum's revision. On the production chain the
        decision OFFICE_NOTE's 99213 allows is a rejection (its approval waits on the visit's open facts), so that is
        the decision recorded - always one, so the invalidation is always asserted (LegacyReadingTests keeps the
        approval's twin on the legacy chain, where 99213 is approvable)."""
        encounter_id = self.create()
        drain()
        data = self.detail(encounter_id)
        [proposal] = [p for p in data['assessment']['proposals'] if p['code'] == '99213']
        self.assertIn('reject', proposal['allowed_actions'], proposal)
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': proposal['id'], 'action': 'reject',
                              'note': 'Synthetic review: rejected before the addendum.'})
        self.assertEqual(response.status_code, 201, response.content)
        response = self.post(f'/api/encounters/{encounter_id}/addenda',
                             {'text': 'Setting confirmed as office.', 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        self.register_addendum(encounter_id, with_addendum(OFFICE_INTERPRETATION,
                                                           {'A1': 'Setting confirmed as office.'}))
        drain()
        data = self.detail(encounter_id)
        self.assertEqual(data['revision']['number'], 2)
        self.assertTrue(data['revision']['text'].startswith(OFFICE_NOTE.replace('\r\n', '\n')[:40]))
        earlier = [decision for decision in data['decisions']['history'] if decision['revision_number'] == 1]
        self.assertEqual([decision['action'] for decision in earlier], ['reject'], data['decisions'])
        for decision in earlier:
            self.assertIsNotNone(decision['invalidated'])
        [_, read] = self.interpretation_runs(encounter_id)  # the addendum revision was read from its own answer
        self.assertEqual(models.EventInventory.objects.get(provider_run=read).state, models.EventInventory.READ)

    def test_report_download_bytes_match_recorded_sha(self):
        encounter_id = self.create()
        drain()
        response = self.post(f'/ops/api/encounters/{encounter_id}/reports', {'kind': 'draft', 'fmt': 'csv'})
        self.assertEqual(response.status_code, 201, response.content)
        report = response.json()
        download = self.client.get(report['download_url'])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(hashlib.sha256(download.content).hexdigest(), report['sha256'])
        self.assertIn('attachment;', download['Content-Disposition'])
        reviewed = self.post(f'/ops/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
        self.assertIn(reviewed.status_code, {201, 409})

    def test_provider_unavailable_is_recorded_not_sent(self):
        self.provider.build_request = mock.Mock(side_effect=ProviderUnavailable('Request too large.'))
        encounter_id = self.create()
        drain()
        runs = self.primary_runs(self.detail(encounter_id))
        self.assertEqual(runs[0]['state'], 'not_sent')
        self.assertEqual(self.provider.sent, [])

    def test_health_is_public_and_reports_synthetic_mode(self):
        response = Client().get('/health/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data_mode'], 'synthetic-only')

    def test_original_download_matches_upload(self):
        payload = OFFICE_NOTE.encode('utf-8')
        from django.core.files.uploadedfile import SimpleUploadedFile
        upload = SimpleUploadedFile('note.txt', payload, content_type='text/plain')
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'file': upload, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        encounter_id = response.json()['id']
        original = self.client.get(f'/ops/api/encounters/{encounter_id}/original')
        self.assertEqual(original.content, payload)
        self.assertEqual(original['X-Content-SHA256'], hashlib.sha256(payload).hexdigest())

    def test_upload_rejects_disguised_files(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile('note.pdf', b'not a pdf at all', content_type='application/pdf')
        response = self.client.post('/api/encounters', {'file': fake_pdf, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 400)


class RecordedInterpretationTests(RecordedInterpretation, PipelineApiCase):
    """The recorded synthetic interpretations themselves (FINAL 14.6): a recording is written only for the exact
    document it was registered for, and a test that meets any other - an addendum revision included - fails."""

    ADDED = 'Setting confirmed as office.'

    def addendum(self, encounter_id):
        response = self.post(f'/api/encounters/{encounter_id}/addenda',
                             {'text': self.ADDED, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)

    def test_a_text_that_only_begins_with_a_registered_document_has_no_answer(self):
        interpreter = RecordedReplayInterpreter(Path(tempfile.gettempdir()), self.recorded)
        added = OFFICE_NOTE + jobs.addendum_block_text(2, timezone.now(), self.ADDED)
        self.assertIs(interpreter.answer_for(OFFICE_NOTE), OFFICE_INTERPRETATION)
        self.assertIsNone(interpreter.answer_for(added))
        self.assertIsNone(interpreter.answer_for(OFFICE_NOTE[:-1]))

    def test_an_unregistered_addendum_revision_is_never_read_and_fails_the_test(self):
        encounter_id = self.create()
        drain()
        self.addendum(encounter_id)
        drain()
        unrecorded = [document for interpreter in self.interpreters for document in interpreter.unrecorded]
        revision = models.Encounter.objects.get(pk=encounter_id).current_revision
        self.assertEqual(unrecorded, [revision.text])
        self.assertTrue(revision.text.startswith(OFFICE_NOTE) and revision.text.endswith(f'{self.ADDED}\n'))
        self.assertFalse(models.EventInventory.objects.filter(revision=revision).exists())  # nothing was read for it
        with self.assertRaises(self.failureException):
            self._every_document_was_recorded()
        for interpreter in self.interpreters:  # accounted for here, so this test's own cleanup passes
            interpreter.unrecorded.clear()

    def test_every_recorded_synthetic_interpretation_is_verified(self):
        """Every recorded synthetic interpretation the production-chain suites register is one Gemini could answer: the
        strict read accepts it, and normalized over its document every attribute it claims is verified - but the date
        in NO_DATE_NOTE's scheduled colonoscopy's time words, which a document stating no date of service leaves
        unchecked (contract 5.3)."""
        from tests.test_cux_r3_progress import NO_PATIENT_STATUS_INTERPRETATIONS
        from tests.test_harness2_pipeline import TWO_EXTENTS_INTERPRETATIONS
        from tests.test_harness_pipeline import COLD_BIOPSY, COLON, COLON_INTERPRETATIONS, colon_interpretation
        from tests.test_repairs_7c8_p1reports import COLONOSCOPY_INTERPRETATIONS
        from tests.test_repairs_gi2_sends import SENDS_INTERPRETATIONS
        from tests.test_repairs_pipeline import INTERPRETATIONS, NO_DATE_NOTE
        from tests.test_repairs_r4_pipeline import R4_INTERPRETATIONS
        from tests.test_services_second_review import REPORT_INTERPRETATIONS
        every = (INTERPRETATIONS + REPORT_INTERPRETATIONS + COLONOSCOPY_INTERPRETATIONS + TWO_EXTENTS_INTERPRETATIONS
                 + COLON_INTERPRETATIONS + ((f'{COLON}{COLD_BIOPSY}\n', colon_interpretation(biopsy=True)),)
                 + R4_INTERPRETATIONS + NO_PATIENT_STATUS_INTERPRETATIONS + SENDS_INTERPRETATIONS)
        recorded = {}
        for text, answer in every:  # the registries share some documents: one answer per document
            self.assertEqual(recorded.setdefault(text, answer), answer)
        self.assertEqual(len(recorded), 18)  # 11 notes and reports, and REPORT's 7 tagged copies
        recorded = list(recorded.items())
        for text, answer in recorded:
            with self.subTest(document=text[:120]):
                parsed = read.read(json.dumps(answer))
                self.assertNotIsInstance(parsed, read.Refusal, parsed)
                report = normalize.normalize(parsed, text).verification
                unverified = {name: row['unverified'] for name, row in report['counts'].items() if row['unverified']}
                expected = ({'time': 1}, {'date_unchecked': 1}) if text == NO_DATE_NOTE else ({}, {})
                self.assertEqual((unverified, report['reasons']), expected, report)
                self.assertEqual((report['discarded'], report['problems']), ([], []), report)

    def test_a_registered_addendum_revision_is_read_from_its_own_answer(self):
        encounter_id = self.create()
        drain()
        self.addendum(encounter_id)
        text = self.register_addendum(encounter_id, with_addendum(OFFICE_INTERPRETATION, {'A1': self.ADDED}))
        drain()
        revision = models.Encounter.objects.get(pk=encounter_id).current_revision
        self.assertEqual(revision.text, text)
        inventory = models.EventInventory.objects.get(revision=revision)
        self.assertEqual(inventory.state, models.EventInventory.READ)
        located = [span['text'] for passage in inventory.events['passages'] for span in passage['spans']]
        self.assertIn(self.ADDED, located)  # the addendum's own line, located in the addendum revision's text
        self.register(text, with_addendum(OFFICE_INTERPRETATION, {'A1': self.ADDED}))  # the same answer: nothing changes
        self.assertEqual([document for document, _ in self.recorded].count(text), 1)
        with self.assertRaises(AssertionError):  # one answer per document
            self.register(text, OFFICE_INTERPRETATION)


class LegacyChainMarkTests(RecordedInterpretation, PipelineApiCase):
    """tests.legacy_chain.applied on one test METHOD of a class on the production chain (FINAL 14.6): that test's body
    runs the legacy chain, and the class's setUp and its other tests run the production chain (the test methods run in
    name order, so the unmarked one runs after the marked one and finds the chain left)."""

    def setUp(self):
        super().setUp()
        self.after_extract_in_setup = jobs._after_extract

    @applied
    def test_a_marked_test_runs_the_legacy_chain_in_its_body_only(self):
        self.assertIs(jobs._after_extract, legacy_chain_module.legacy_after_extract)
        self.assertIsNot(self.after_extract_in_setup, legacy_chain_module.legacy_after_extract)
        encounter_id = self.create()
        drain()
        kinds = [job.kind for job in models.Job.objects.filter(encounter_id=encounter_id).order_by('created_at', 'pk')]
        self.assertEqual(kinds, ['extract', 'analyze', 'predict', 'assess'])
        self.assertEqual(self.replayed(), [])  # nothing was interpreted

    def test_an_unmarked_test_runs_the_production_chain(self):
        self.assertIs(jobs._after_extract, self.after_extract_in_setup)
        self.assertIsNot(jobs._after_extract, legacy_chain_module.legacy_after_extract)
        encounter_id = self.create()
        drain()
        self.assertEqual(len(self.interpretation_runs(encounter_id)), 1)


@applied
class LegacyReadingTests(PipelineApiCase):
    """A reading-outcome test (FINAL 14.6): what the LEGACY reader read in OFFICE_NOTE - the proposals it selected and
    their exact evidence - kept as a legacy regression test under the test-only legacy chain (tests/legacy_chain.py)."""

    def test_full_flow_reviews_and_reports(self):
        encounter_id = self.create()
        drain()
        data = self.detail(encounter_id)
        self.assertEqual(data['revision']['extraction']['status'], 'ok')
        self.assertEqual(len(self.provider.sent), 1)
        selected = [p for p in data['assessment']['proposals'] if p['bucket'] == 'selected']
        self.assertTrue(selected, data['assessment'])
        text = data['revision']['text']
        for proposal in selected:
            for span in proposal['evidence']:
                self.assertEqual(text[span['start']:span['end']], span['text'])
        self.assertNotIn('UNVERIFIED PROVIDER WORDING', json.dumps(data))

    def test_addendum_invalidates_an_approval(self):
        """The approval's twin of PipelineApiTests.test_addendum_creates_revision_and_invalidates_decisions: the LEGACY
        reader holds OFFICE_NOTE's 99213 approvable, so a revision-1 approval is recorded and the addendum invalidates
        it."""
        encounter_id = self.create()
        drain()
        data = self.detail(encounter_id)
        approvable = [p for p in data['assessment']['proposals'] if 'approve' in p['allowed_actions']]
        self.assertTrue(approvable, data['assessment']['proposals'])
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': approvable[0]['id'], 'action': 'approve',
                              'acknowledgement': review.ACKNOWLEDGEMENTS['human']})
        self.assertEqual(response.status_code, 201, response.content)
        response = self.post(f'/api/encounters/{encounter_id}/addenda',
                             {'text': 'Setting confirmed as office.', 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        data = self.detail(encounter_id)
        self.assertEqual(data['revision']['number'], 2)
        earlier = [decision for decision in data['decisions']['history'] if decision['revision_number'] == 1]
        self.assertEqual([decision['action'] for decision in earlier], ['approve'], data['decisions'])
        for decision in earlier:
            self.assertIsNotNone(decision['invalidated'])


class SnapshotHashTests(OperatorReads, TestCase):
    def test_sha256_json_is_order_independent(self):
        self.assertEqual(sha256_json({'a': 1, 'b': [1, 2]}), sha256_json({'b': [1, 2], 'a': 1}))


class _OtherSession:
    """A second database session, as another worker's or the access check's: it takes and releases the installation-wide
    provider lock (jobs.PROVIDER_LOCK_KEY) on its own connection."""

    def __init__(self, test):
        from django.db import connections

        self.connection = connections.create_connection('default')
        test.addCleanup(self.connection.close)

    def try_lock(self):
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT pg_try_advisory_lock(%s)', [jobs.PROVIDER_LOCK_KEY])
            return cursor.fetchone()[0]

    def unlock(self):
        with self.connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [jobs.PROVIDER_LOCK_KEY])
            return cursor.fetchone()[0]


@applied
@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class ProviderLockTests(OperatorReads, TestCase):
    """Refutation round 1, FG-4 (I8; HARNESS.md 2: every provider send takes the one installation-wide advisory lock):
    no test held the lock from another session, so removing it from jobs._send stayed green.

    Under the test-only legacy chain (design/FINAL.md 14.6): the first test asserts the legacy chain's stage order (no
    interpretation before the predict) and the legacy reader's outcome for the note ('ready_for_review'), so both run as
    legacy regression tests; ProductionChainProviderLockTests proves the lock on the production chain, whose
    interpretation is a send of its own."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', 'Total time on the date of the encounter was 24 minutes.')])
        for target, kwargs in (('studio.jobs.get_provider', {'return_value': self.provider}),
                               ('studio.jobs.time.sleep', {})):  # a requeued stage waits a second: not here
            patcher = mock.patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.other = _OtherSession(self)

    def create(self):
        response = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def test_a_predict_waits_while_another_session_holds_the_provider_lock(self):
        encounter_id = self.create()
        self.assertTrue(self.other.try_lock())
        try:
            for _ in range(3):
                job = jobs.run_job(jobs.claim_next())  # extract, analyze, then the predict, which waits
            job.refresh_from_db()
            self.assertEqual((job.kind, job.state, job.result, job.started_at),
                             ('predict', 'queued', {'requeued': 'another provider request is in flight'}, None))
            self.assertEqual((self.provider.sent, models.ProviderRun.objects.filter(encounter_id=encounter_id).count()),
                             ([], 0))  # nothing reserved, nothing sent
        finally:
            self.assertTrue(self.other.unlock())
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'ready_for_review')

    def test_the_lock_is_held_while_the_provider_sends_and_released_after(self):
        held = []
        send = self.provider.send

        def checked(request, *, deadline_s):
            acquired = self.other.try_lock()  # from the other session, while the worker's send is in flight
            if acquired:
                self.other.unlock()
            held.append(not acquired)
            return send(request, deadline_s=deadline_s)
        self.provider.send = checked
        self.create()
        drain()
        self.assertEqual(held, [True])
        self.assertTrue(self.other.try_lock())  # released once the send's outcome was recorded
        self.assertTrue(self.other.unlock())


class ProductionChainProviderLockTests(RecordedInterpretation, PipelineApiCase):
    """FG-4 on the production chain (FINAL 6.3: the interpretation is sent through jobs._send's looped branch): each
    send - the interpretation's, then Corti's - waits while another session holds the installation-wide provider lock,
    reserving and sending nothing, holds the lock while it is in flight, and releases it once its outcome is
    recorded."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch('studio.jobs.time.sleep')  # a requeued stage waits a second: not here
        patcher.start()
        self.addCleanup(patcher.stop)
        self.other = _OtherSession(self)

    def test_the_interpretation_and_the_predict_each_wait_while_another_session_holds_the_provider_lock(self):
        encounter_id = self.create()
        requeued = {'requeued': 'another provider request is in flight'}
        self.assertTrue(self.other.try_lock())
        try:
            for _ in range(2):
                job = jobs.run_job(jobs.claim_next())  # extract, then the interpretation, which waits
            job.refresh_from_db()
            self.assertEqual((job.kind, job.state, job.result, job.started_at), ('interpret', 'queued', requeued, None))
            self.assertEqual((self.replayed(), models.ProviderRun.objects.filter(encounter_id=encounter_id).count()),
                             ([], 0))  # nothing reserved, nothing sent
        finally:
            self.assertTrue(self.other.unlock())
        for kind in ('interpret', 'analyze'):
            job = jobs.run_job(jobs.claim_next())
            self.assertEqual((job.kind, job.state), (kind, 'succeeded'), job.error)
        self.assertTrue(self.other.try_lock())
        try:
            job = jobs.run_job(jobs.claim_next())  # the predict, which waits
            job.refresh_from_db()
            self.assertEqual((job.kind, job.state, job.result, job.started_at), ('predict', 'queued', requeued, None))
            self.assertEqual((self.provider.sent, models.ProviderRun.objects.filter(
                encounter_id=encounter_id, purpose=models.ProviderRun.PRIMARY).count()), ([], 0))
        finally:
            self.assertTrue(self.other.unlock())
        drain()
        self.assertEqual((len(self.replayed()), len(self.provider.sent)), (1, 1))
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertTrue(interpretation.is_new_assessment(encounter.current_assessment))

    def test_the_lock_is_held_while_each_provider_sends_and_released_after(self):
        held = []
        send, send_loop = self.provider.send, RecordedReplayInterpreter.send_loop

        def in_flight():
            acquired = self.other.try_lock()  # from the other session, while the worker's send is in flight
            if acquired:
                self.other.unlock()
            return not acquired

        def checked(request, *, deadline_s):
            held.append(('corti', in_flight()))
            return send(request, deadline_s=deadline_s)

        def checked_loop(interpreter, request, **kwargs):
            held.append(('interpretation', in_flight()))
            return send_loop(interpreter, request, **kwargs)
        self.provider.send = checked
        with mock.patch.object(RecordedReplayInterpreter, 'send_loop', checked_loop):
            self.create()
            drain()
        self.assertEqual(held, [('interpretation', True), ('corti', True)])
        self.assertTrue(self.other.try_lock())  # released once the sends' outcomes were recorded
        self.assertTrue(self.other.unlock())
