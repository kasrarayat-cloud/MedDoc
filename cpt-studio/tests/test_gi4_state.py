"""GI round 4 harness, H5: the state battery. Real stages, real persistence, on the test database (the throwaway
127.0.0.1:55461 locally, CI's disposable PostgreSQL there); the provider is an in-process stand-in that answers each
request with the live service's RETAINED answer to that exact request (tests/fixtures/gi4/regression/, synthetic), so
a request that rebuilds byte-identically is answered as it was, and every send is counted.

Pinned here, on the regression encounters h4-04 and on a synthetic colonoscopy report:
- a context recorded under an earlier context version is remade under the current one, and the upgrade's own predict
  never sends; only a member's Resume does;
- the round-4 install (pd.json integration_20261101_cycle2, interpretations 49 and 50(d)): installed 80df1831d168's
  context label gi-context@3 is an earlier version here, so a predict queued before the install is remade under the
  current rules before it sends (a date the new rules ask is never sent), no second review is offered or sent on such
  a context until a member's save reads it again, and the routing, inventory and engine labels move without moving any
  proposal fingerprint, so no decision is invalidated by a label alone;
- a Stop then a Resume sends the request once;
- an answered date sends one dated request, byte-identical to the one the live service sent, and an identical re-save
  sends nothing;
- an identical retained request is reused workspace-wide, never sent again;
- a decision carries exactly when its proposal's fingerprint is equal, and is invalidated with a recorded reason
  otherwise;
- a second-review offer stays member-asked: no stage queues one, and asking sends it once.
"""
import contextlib
import datetime as dt
import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from ops.gi4 import battery, regression, replay
from studio import jobs, models, review
from studio.gi import context as gi_context
from studio.gi import detect
from studio.gi import services as gi_services
from studio.providers.corti import ADAPTER_VERSION, build_coding_request
from studio.types import Fact, RawExchange, Span
from studio.validation import engine, reconcile
from tests.support import factories as f

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
DOCS = regression.load_fixtures()
H404 = DOCS['h4-04']
STORED = {r['service_date']: r['request_sha256'] for r in H404['runs']}  # None: the dateless primary
# installed 80df1831d168's labels: every encounter recorded before the round-4 install carries its context label
INSTALLED_LABELS = {'CONTEXT_VERSION': 'gi-context@3', 'EARLIER_CONTEXT_VERSIONS': ('gi-context@1', 'gi-context@2')}
INSTALLED_READER_LABELS = {(detect, 'ROUTING_VERSION'): 'gi-routing@4',
                           (gi_services, 'INVENTORY_VERSION'): 'gi-services@1',
                           (reconcile, 'INVENTORY_SOURCE'): 'cpt-studio:gi-services@1',
                           (engine, 'ENGINE_VERSION'): 'cpt-studio-validation@4'}
# a rule (a) document (pd.json, CTS-6's PD-06): installed reads and sends 2026-10-19; the round-4 reader asks the date
RULE_A = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\n'
          'Date of service: 10/19/2026\nDate seen: 10/12/2026 in clinic; procedure today\nEndoscopist: Synthetic MD\n'
          'Sedation: propofol by CRNA\nFindings: The colonoscope was advanced to the cecum. No polyps were found.\n'
          'Impression: Normal colonoscopy.\n')
COLON = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\n'
         'Date of service: 10/19/2026\nPlace of service: ambulatory surgical center (POS 24)\n'
         'Endoscopist: Synthetic Endoscopist, MD (fictional)\nFindings: The colonoscope was advanced to the cecum. A 6 mm '
         'polyp in the sigmoid colon was removed with a cold snare.\nImpression: One polyp removed.\n')


class RetainedProvider:
    """The Corti adapter's request builder, and an answer from the retained runs: the stored response of the run whose
    request is byte-identical; any other request is answered with no codes (and counted as new)."""
    name, adapter_version, mode = 'corti', ADAPTER_VERSION, 'live'

    def __init__(self):
        self.answers = {r['request_sha256']: json.dumps(r['response']).encode() for doc in DOCS.values()
                        for r in doc['runs'] if r['request_sha256'] and r['response'] is not None}
        self.sent = []

    def build_request(self, text, service_date):
        return build_coding_request(self.name, self.adapter_version, text, service_date, 10 ** 7)

    def send(self, request, *, deadline_s):
        self.sent.append(request.canonical_sha256)
        data = self.answers.get(request.canonical_sha256, b'{"codes": [], "candidates": []}')
        import hashlib
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=10.0,
                           usage={'creditsConsumed': 0.01}, usage_basis='provider_reported_credits_not_usd')


def seed_reference(codes):
    """The replay's synthetic reference rows (ops/gi4/replay.py) for ``codes``, under the h4 assessments' sources."""
    for source in H404['reference_sources']:
        row = models.ReferenceSource.objects.create(
            key=source['key'], kind=source['kind'], publisher=source['publisher'], title=source['title'][:200],
            release=source['release'], url=source['url'], sha256=source['sha256'],
            retrieved_at=dt.datetime(2026, 10, 23, tzinfo=dt.timezone.utc),
            effective_start=dt.date.fromisoformat(source['effective_start']),
            effective_end=dt.date.fromisoformat(source['effective_end']), license_note=source['license_note'],
            scope_note=source['scope_note'], row_count=len(codes))
        for code in codes:
            models.ReferenceCodeFact.objects.create(source=row, code=code, facts=dict(
                replay.PFS_ROW if source['kind'] == 'cms-pfs' else replay.MUE_ROW))


@override_settings(**LIVE)
class StateBatteryTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = RetainedProvider()
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        seed_reference(('43251', '45378', '43239', '45385', '99204', '99213'))

    # --- helpers ---
    def upload(self, text):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def post(self, path, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def drain(self):
        while (job := jobs.claim_next()) is not None:
            jobs.run_job(job)

    def run_one(self, kind):
        job = jobs.claim_next()
        self.assertEqual(job.kind, kind)
        jobs.run_job(job)

    def detail(self, encounter_id):
        return self.client.get(f'/api/encounters/{encounter_id}').json()

    def answer(self, encounter_id, value):
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': value})
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()

    def no_review2(self, encounter_id):
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).exists())
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                           purpose=models.ProviderRun.SECOND_REVIEW).exists())

    def proposal(self, encounter_id, code):
        return next(p for p in self.detail(encounter_id)['assessment']['proposals'] if p['code'] == code)

    # --- the battery ---
    def test_an_answered_date_sends_one_identical_request_and_a_resave_sends_nothing(self):
        encounter_id = self.upload(H404['text'])
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])  # the dateless primary, byte-identical to the live one
        self.answer(encounter_id, '2026-10-19')
        self.assertEqual(self.provider.sent, [STORED[None], STORED['2026-10-19']])
        self.answer(encounter_id, '2026-10-19')  # an identical re-save
        self.assertEqual(len(self.provider.sent), 2)
        self.assertEqual(self.proposal(encounter_id, '43251')['status'], 'ready')
        self.no_review2(encounter_id)

    def test_a_retained_request_is_reused_workspace_wide(self):
        first = self.upload(H404['text'])
        self.drain()
        second = self.upload(H404['text'])
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])  # sent once for both encounters
        run = models.ProviderRun.objects.get(encounter_id=second)
        self.assertEqual((run.state, run.sent, run.request_sha256), (models.ProviderRun.SUCCEEDED, False, STORED[None]))
        self.assertEqual(run.reused_from.encounter_id, models.Encounter.objects.get(pk=first).pk)

    def test_a_decision_carries_exactly_when_its_fingerprint_is_equal(self):
        encounter_id = self.upload(H404['text'])
        self.drain()
        self.answer(encounter_id, '2026-10-19')
        item = self.proposal(encounter_id, '43251')
        self.assertIn('approve', item['allowed_actions'])
        response = self.post(f'/api/encounters/{encounter_id}/decisions',
                             {'proposal_id': item['id'], 'action': 'approve',
                              'acknowledgement': review.ACKNOWLEDGEMENTS['human']})
        self.assertEqual(response.status_code, 201, response.content)
        approved = models.Decision.objects.get(encounter_id=encounter_id)
        self.answer(encounter_id, '2026-10-19')  # identical re-save: same fingerprint, the decision carries
        carried = models.Decision.objects.get(carried_from=approved)
        self.assertEqual(carried.proposal_fingerprint, approved.proposal_fingerprint)
        self.assertFalse(models.DecisionInvalidation.objects.filter(decision=approved).exists())
        sends = len(self.provider.sent)
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'hospital_outpatient'})
        self.assertEqual(response.status_code, 201, response.content)  # a context change 43251 does not depend on
        self.drain()
        again = models.Decision.objects.get(carried_from=carried)  # its fingerprint is equal: the decision carries
        self.assertEqual(again.proposal_fingerprint, carried.proposal_fingerprint)
        removed, _ = models.ReferenceCodeFact.objects.filter(code='43251', source__kind='cms-pfs').delete()
        self.assertEqual(removed, 1)  # the fee-schedule row 43251's checks read is gone: a check changes
        self.answer(encounter_id, '2026-10-19')  # the same date again: a re-assessment, nothing to send
        self.assertEqual(len(self.provider.sent), sends)
        self.assertFalse(models.Decision.objects.filter(carried_from=again).exists())
        invalidation = models.DecisionInvalidation.objects.get(decision=again)
        self.assertTrue(invalidation.reason.strip())
        now = models.Proposal.objects.get(pk=self.proposal(encounter_id, '43251')['id'])
        self.assertNotEqual(now.fingerprint, again.proposal_fingerprint)

    def test_an_earlier_context_version_is_remade_and_the_upgrades_predict_never_sends(self):
        earlier = jobs.EARLIER_CONTEXT_VERSIONS[-1]
        labels = {'CONTEXT_VERSION': earlier, 'EARLIER_CONTEXT_VERSIONS': jobs.EARLIER_CONTEXT_VERSIONS[:-1]}
        self.assertEqual(labels, INSTALLED_LABELS)  # the round-4 install: the earlier labels are installed's own
        dated = {name: fact for name, fact in __import__('studio.gi.context', fromlist=['x']).extract_context(
            H404['text']).items()}
        from studio.types import Fact
        dated['service_date'] = Fact('service_date', '2026-10-19', 'document', (), '')
        encounter_id = self.upload(H404['text'])
        with mock.patch.multiple(jobs, **labels):  # the earlier rules read the date as documented, and send it
            self.run_one(models.Job.EXTRACT)
            with mock.patch('studio.gi.context.extract_context', return_value=dated):
                self.run_one(models.Job.ANALYZE)
            self.run_one(models.Job.PREDICT)
        self.assertEqual(self.provider.sent, [STORED['2026-10-19']])
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(encounter.current_context.version, earlier)
        self.drain()  # the swap: this code reads the queued assess, remakes the context, and the upgrade's predict stops
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_context.version, jobs.CONTEXT_VERSION)
        self.assertEqual(encounter.current_context.facts['service_date']['origin'], 'missing')
        self.assertTrue(models.AuditEvent.objects.filter(encounter_id=encounter_id, event='context.remade').exists())
        self.assertEqual(self.provider.sent, [STORED['2026-10-19']])  # nothing sent by the upgrade's predict
        response = self.post(f'/api/encounters/{encounter_id}/resume')  # only a member's Resume sends
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()
        self.assertEqual(self.provider.sent, [STORED['2026-10-19'], STORED[None]])

    def test_stop_then_resume_sends_once(self):
        encounter_id = self.upload(H404['text'])
        self.run_one(models.Job.EXTRACT)
        self.run_one(models.Job.ANALYZE)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.drain()
        self.assertEqual(self.provider.sent, [])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 409)
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])

    def test_a_second_review_offer_stays_member_asked(self):
        encounter_id = self.upload(COLON)  # the stand-in answers this request with no codes: the service is unresolved
        self.drain()
        self.no_review2(encounter_id)  # no stage queued one
        offer = self.detail(encounter_id)['second_review']
        self.assertTrue(offer['available'], offer)
        sends = len(self.provider.sent)
        response = self.post(f'/api/encounters/{encounter_id}/second-review')
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()
        self.assertEqual(len(self.provider.sent), sends + 1)  # asked: sent once
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                           purpose=models.ProviderRun.SECOND_REVIEW).count(), 1)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 409)
        self.drain()
        self.assertEqual(len(self.provider.sent), sends + 1)

    def test_a_predict_queued_before_the_install_is_remade_under_the_new_rules_before_it_sends(self):
        # interpretation 49 at the round-4 install: the upload's extract and analyze ran under installed's labels and
        # reading (the document's 2026-10-19 sent as documented); the predict they queued runs on this revision, which
        # remakes the context first - and the round-4 rules ask the date (PD's rule (a)), so only the dateless request
        # is sent, never installed's dated one
        dated = dict(gi_context.extract_context(RULE_A))
        label = 'Date of service: 10/19/2026'
        start = RULE_A.index(label)
        dated['service_date'] = Fact('service_date', '2026-10-19', 'document',
                                     (Span(start, start + len(label), label),), '')
        encounter_id = self.upload(RULE_A)
        with mock.patch.multiple(jobs, **INSTALLED_LABELS), \
                mock.patch('studio.gi.context.extract_context', return_value=dated):
            self.run_one(models.Job.EXTRACT)
            self.run_one(models.Job.ANALYZE)
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual((encounter.current_context.version, encounter.current_context.facts['service_date']['value']),
                         ('gi-context@3', '2026-10-19'))
        self.drain()  # the install: this revision's worker claims the queued predict
        encounter.refresh_from_db()
        self.assertEqual(encounter.current_context.version, jobs.CONTEXT_VERSION)
        self.assertEqual(encounter.current_context.facts['service_date']['origin'], 'conflict')  # asked
        self.assertTrue(models.AuditEvent.objects.filter(encounter_id=encounter_id, event='context.remade').exists())
        dateless = self.provider.build_request(RULE_A, None).canonical_sha256
        self.assertEqual(self.provider.sent, [dateless])  # never installed's dated request
        installed_dated = self.provider.build_request(RULE_A, dt.date(2026, 10, 19)).canonical_sha256
        self.assertNotIn(installed_dated, self.provider.sent)

    def test_no_second_review_on_a_pre_install_context_until_a_save_reads_it_again(self):
        # interpretation 49: no second review is offered or sent on a context installed recorded (gi-context@3, an
        # earlier version here); a member's context save remakes it under the current rules, and one ask sends once
        encounter_id = self.upload(COLON)  # the stand-in answers its request with no codes: the service is unresolved
        with mock.patch.multiple(jobs, **INSTALLED_LABELS):
            self.drain()  # every stage before the install, under installed's labels
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).current_context.version, 'gi-context@3')
        sends = len(self.provider.sent)
        offer = self.detail(encounter_id)['second_review']
        self.assertFalse(offer['available'], offer)
        self.assertEqual(offer['reason'], jobs.SECOND_REVIEW_EARLIER_CONTEXT)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 409)
        self.drain()
        self.no_review2(encounter_id)
        self.assertEqual(len(self.provider.sent), sends)
        response = self.post(f'/api/encounters/{encounter_id}/context', {'billing_context': ''})  # an unchanged value
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).current_context.version, jobs.CONTEXT_VERSION)
        self.assertEqual(len(self.provider.sent), sends)  # read again: the retained answer is reused, nothing sent
        self.assertTrue(self.detail(encounter_id)['second_review']['available'])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        self.drain()
        self.assertEqual(len(self.provider.sent), sends + 1)  # asked: sent once


class RoundFourLabelTests(SimpleTestCase):
    """The round-4 install's labels (interpretations 49 and 50(d); pd.json integration_20261101_cycle2): every reader
    that reads differently from installed 80df1831d168 moves its label by one, and no proposal fingerprint reads a
    label (engine._fingerprint), so a label alone invalidates no decision."""

    def test_the_labels(self):
        self.assertEqual((jobs.CONTEXT_VERSION, jobs.EARLIER_CONTEXT_VERSIONS),
                         ('gi-context@4', ('gi-context@1', 'gi-context@2', 'gi-context@3')))
        self.assertEqual((detect.ROUTING_VERSION, gi_services.INVENTORY_VERSION, reconcile.INVENTORY_SOURCE,
                          engine.ENGINE_VERSION),
                         ('gi-routing@5', 'gi-services@2', 'cpt-studio:gi-services@2', 'cpt-studio-validation@5'))
        self.assertEqual(reconcile.INVENTORY_SOURCE, f'cpt-studio:{gi_services.INVENTORY_VERSION}')
        for (module, name), installed in INSTALLED_READER_LABELS.items():
            self.assertNotEqual(getattr(module, name), installed, name)

    def labels_and_fingerprints(self):
        """Every H4 row read through the stages (ops/gi4/battery.py): the labels each result carries and every
        proposal's fingerprint."""
        m = battery.modules()
        labels, fingerprints = set(), {}
        for name, (text, codes) in battery.CASES.items():
            document_facts, day, routing = m.jobs._analyze_child(text, {}, 1000)
            facts = m.jobs._merged_facts(document_facts, {})
            context = m.jobs.context_facts(SimpleNamespace(facts=facts))
            _, result = m.jobs._assess_child(text, day, (m.PageSpan(1, 0, len(text)),), context,
                                             battery.response(m, text, codes), m.Lookup([], {}), 'succeeded', 'ok', ())
            m.jobs.release_routing_caches()
            labels.add((routing['version'], (result.services or {}).get('version', ''), result.engine_version))
            labels.update(('source', c.source) for p in result.proposals for c in p.checks
                          if c.source.startswith('cpt-studio:gi-services@'))
            fingerprints.update({(name, p.code, p.bucket): p.fingerprint for p in result.proposals})
        return labels, fingerprints

    def test_a_label_moves_no_fingerprint(self):
        current_labels, current = self.labels_and_fingerprints()
        with contextlib.ExitStack() as stack:
            for (module, name), installed in INSTALLED_READER_LABELS.items():
                stack.enter_context(mock.patch.object(module, name, installed))
            installed_labels, installed = self.labels_and_fingerprints()
        # the patches applied: every result names installed's labels under them, and these labels without them
        self.assertEqual(installed_labels - {('source', 'cpt-studio:gi-services@1')},
                         {('gi-routing@4', 'gi-services@1', 'cpt-studio-validation@4')})
        self.assertEqual(current_labels - {('source', 'cpt-studio:gi-services@2')},
                         {('gi-routing@5', 'gi-services@2', 'cpt-studio-validation@5')})
        self.assertIn(('source', 'cpt-studio:gi-services@1'), installed_labels)
        self.assertGreater(len(current), 50)
        self.assertEqual(installed, current)
