"""GI round 4, package PD, the H5 state rows: real stages, real persistence, on the test database (the throwaway
127.0.0.1:55461 locally, CI's disposable PostgreSQL there), with the H5 battery's in-process stand-in provider (it
answers a request byte-identical to one the live service sent with that retained answer, any other with no codes, and
counts every send).

- h4-01 ("Date seen: 10/26/2026", read now as the evidence of the date asked): the dateless primary is the stored one; a
  member's 1998-01-01 is held and sends nothing; 2026-10-26 sends the stored dated request once; an identical re-save
  sends nothing.
- rule (a), a synthetic report whose installed reading sends 2026-10-18 while "Date performed: 10/19/2026" stands beside
  it: the primary request is now dateless (the cost of the ask: one dateless request), 2026-10-19 is held and sends
  nothing, 2026-10-18 sends one dated request, byte-identical to the one installed sent, and a re-save sends nothing.
- the Wave 1 repair (PD, cycle 1), CTS-6: the live consequence the install declaration records (pd.json
  amendment_20261101, cts6_recorded_consequence; reproduced at the cycle-2 integration against installed and recorded
  as a known limit, pd.json integration_20261101_cycle2), pinned here as recorded behaviour. An encounter whose stages
  ran under the installed reading and labels (gi-context@3, patched in) is re-extracted with this reader at a member's
  context save of ANY field, its new context labelled gi-context@4 (jobs.CONTEXT_VERSION): (i) a rule (a) document
  sends ONE new dateless primary request and the approval whose status moves is invalidated; answering the installed
  date sends nothing new and returns READY, but the approval stays invalidated; re-saving that date first sends
  nothing and carries the decision; (ii) a rule (c) narrowing document holds a member date of another day entered
  before the install: nothing is sent.
Every document is synthetic.
"""
import datetime as dt
import hashlib
import json

from django.test import TestCase, override_settings
from unittest import mock

from studio import jobs, models, review
from studio.gi import context as gi_context
from studio.gi.context import is_member_conflict
from studio.providers.corti import ADAPTER_VERSION, build_coding_request
from studio.types import Fact, RawExchange
from tests.support import factories as f
from tests.test_gi4_state import DOCS, LIVE, RetainedProvider, seed_reference

H401 = DOCS['h4-01']
STORED = {r['service_date']: r['request_sha256'] for r in H401['runs'] if r['request_sha256']}
X_Y = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\nDate of service: '
       '10/18/2026\nDate performed: 10/19/2026\nPlace of service: ambulatory surgical center (POS 24)\nEndoscopist: '
       'Synthetic Endoscopist, MD (fictional)\nFindings: The colonoscope was advanced to the cecum. A 6 mm polyp in the '
       'sigmoid colon was removed with a cold snare.\nSigned: Synthetic Endoscopist, MD (fictional), 10/19/2026\n')


def request_sha(text, day):
    import datetime as dt
    return build_coding_request('corti', ADAPTER_VERSION, text, dt.date.fromisoformat(day) if day else None,
                                10 ** 7).canonical_sha256


@override_settings(**LIVE)
class WideDateStateTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = RetainedProvider()
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        seed_reference(('99204', '45385', '45378'))

    def upload(self, text):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def drain(self):
        while (job := jobs.claim_next()) is not None:
            jobs.run_job(job)

    def answer(self, encounter_id, value):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/encounters/{encounter_id}/context',
                                        data=json.dumps({'service_date': value}), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        self.drain()

    def service_date(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id).current_context.facts['service_date']

    def test_h4_01_takes_only_the_date_it_states(self):
        encounter_id = self.upload(H401['text'])
        self.drain()
        self.assertEqual(self.provider.sent, [STORED[None]])  # the dateless primary, byte-identical to the live one
        fact = self.service_date(encounter_id)
        self.assertEqual((fact['origin'], [e['text'] for e in fact['evidence']]), ('missing', ['Date seen: 10/26/2026']))
        self.answer(encounter_id, '1998-01-01')  # held: no date it could carry, nothing built or sent
        self.assertEqual(self.provider.sent, [STORED[None]])
        self.assertTrue(is_member_conflict(self.service_date(encounter_id)))
        self.answer(encounter_id, '2026-10-26')
        self.assertEqual(self.provider.sent, [STORED[None], STORED['2026-10-26']])
        self.answer(encounter_id, '2026-10-26')  # an identical re-save
        self.assertEqual(len(self.provider.sent), 2)
        self.assertEqual(self.service_date(encounter_id)['origin'], 'user')

    def test_rule_a_asks_and_takes_only_the_installed_date(self):
        encounter_id = self.upload(X_Y)
        self.drain()
        self.assertEqual(self.provider.sent, [request_sha(X_Y, None)])  # asked: the primary carries no date
        fact = self.service_date(encounter_id)
        self.assertEqual(fact['origin'], 'conflict')
        self.assertTrue(fact['note'].startswith('The document also states “Date performed: 10/19/2026”'))
        self.answer(encounter_id, '2026-10-19')  # the wide label's date: held, nothing sent
        self.assertEqual(len(self.provider.sent), 1)
        self.assertTrue(is_member_conflict(self.service_date(encounter_id)))
        self.answer(encounter_id, '2026-10-18')  # installed's own date: one dated request, as installed sent it
        self.assertEqual(self.provider.sent, [request_sha(X_Y, None), request_sha(X_Y, '2026-10-18')])
        self.answer(encounter_id, '2026-10-18')
        self.assertEqual(len(self.provider.sent), 2)
        self.assertFalse(models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.REVIEW2).exists())


# installed 80df1831d168's context labels: every stage of an encounter recorded before the install ran under them
INSTALLED_LABELS = {'CONTEXT_VERSION': 'gi-context@3', 'EARLIER_CONTEXT_VERSIONS': ('gi-context@1', 'gi-context@2')}
# CTS-6's document (the refuter's PD-06 colonoscopy report): installed sends 2026-10-19; this reader asks it (rule (a))
RULE_A = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\n'
          'Date of service: 10/19/2026\nDate seen: 10/12/2026 in clinic; procedure today\nEndoscopist: Synthetic MD\n'
          'Sedation: propofol by CRNA\nFindings: The colonoscope was advanced to the cecum. No polyps were found.\n'
          'Impression: Normal colonoscopy.\n')
# a rule (c) narrowing document: installed asks with no evidence; this reader takes only 2026-10-21 (the sign-off's day)
NARROWED = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy Report\nEndoscopist: Wren '
            'Halvorsen-Ode, MD (fictional)\nDate performed: 10/21/2026\nSedation: propofol by CRNA\n\nFindings\nThe '
            'colonoscope was advanced to the cecum. No polyps were found.\nImpression\nNormal colonoscopy.\n'
            'Electronically signed by Wren Halvorsen-Ode, MD (fictional), 10/21/2026 10:05\n')
QUOTE = 'The colonoscope was advanced to the cecum.'


class CecumProvider:
    """Answers every request with 45378, citing the cecum sentence of ``text``, and counts every send."""
    name, adapter_version, mode = 'corti', ADAPTER_VERSION, 'live'

    def __init__(self, text):
        self.text, self.sent = text, []

    def build_request(self, text, service_date):
        return build_coding_request(self.name, self.adapter_version, text, service_date, 10 ** 7)

    def send(self, request, *, deadline_s):
        self.sent.append(request.canonical_sha256)
        start = self.text.index(QUOTE)
        data = json.dumps({'codes': [{'code': '45378', 'display': 'SYNTHETIC', 'system': 'cpt', 'alternatives': [],
                                      'evidences': [{'contextIndex': 0, 'start': start, 'end': start + len(QUOTE),
                                                     'text': QUOTE}]}], 'candidates': []}).encode()
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=10.0,
                           usage={'creditsConsumed': 0.01}, usage_basis='provider_reported_credits_not_usd')


def installed_reading(text, service_date):
    """The installed tree's facts for ``text``: this reader's, with the service date as installed reads it."""
    facts = dict(gi_context.extract_context(text))
    if service_date is None:
        facts['service_date'] = Fact('service_date', None, 'missing', (), gi_context.MISSING_NOTES['service_date'])
    else:
        label = 'Date of service: 10/19/2026'
        start = text.index(label)
        facts['service_date'] = Fact('service_date', service_date, 'document',
                                     (gi_context.Span(start, start + len(label), label),), '')
    return facts


@override_settings(**LIVE)
class RecordedInstallConsequenceTests(TestCase):
    """CTS-6: what an encounter recorded before the install meets at its first context save after it (recorded for the
    install declaration). Before the install every stage runs under installed 80df1831d168's labels (INSTALLED_LABELS:
    its context is gi-context@3, now an earlier version) as well as its reading."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)

    def start(self, text, installed_date):
        self.provider = CecumProvider(text)
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        encounter_id = response.json()['id']
        with mock.patch.multiple(jobs, **INSTALLED_LABELS), \
                mock.patch('studio.gi.context.extract_context', return_value=installed_reading(text, installed_date)):
            self.drain()  # extract, analyze, predict and assess under the installed reading and labels
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).current_context.version, 'gi-context@3')
        return encounter_id

    def post(self, path, data):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(path, data=json.dumps(data), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        return response

    def drain(self):
        while (job := jobs.claim_next()) is not None:
            jobs.run_job(job)

    def proposal(self, encounter_id, code):
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        return next(p for p in detail['assessment']['proposals'] if p['code'] == code)

    def approve(self, encounter_id):
        item = self.proposal(encounter_id, '45378')
        self.assertEqual(item['status'], 'ready')
        self.post(f'/api/encounters/{encounter_id}/decisions', {'proposal_id': item['id'], 'action': 'approve',
                                                                 'acknowledgement': review.ACKNOWLEDGEMENTS['human']})
        return models.Decision.objects.get(encounter_id=encounter_id)

    def test_a_rule_a_document_sends_one_dateless_request_and_invalidates_the_approval(self):  # CTS-6 (i)
        encounter_id = self.start(RULE_A, '2026-10-19')
        dated = self.provider.build_request(RULE_A, dt.date(2026, 10, 19)).canonical_sha256
        dateless = self.provider.build_request(RULE_A, None).canonical_sha256
        self.assertEqual(self.provider.sent, [dated])  # before the install: installed's dated request
        approved = self.approve(encounter_id)
        self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'asc'})  # after it: a save of another field
        self.drain()
        self.assertEqual(self.provider.sent, [dated, dateless])  # ONE new paid dateless primary request
        self.assertEqual(self.proposal(encounter_id, '45378')['status'], 'needs_clarification')
        invalidation = models.DecisionInvalidation.objects.get(decision=approved)
        self.assertIn('service date: 2026-10-19 \u2192 asked', invalidation.reason)
        context = models.Encounter.objects.get(pk=encounter_id).current_context
        self.assertEqual((context.facts['service_date']['origin'], context.version), ('conflict', jobs.CONTEXT_VERSION))
        self.assertEqual(jobs.CONTEXT_VERSION, 'gi-context@4')  # the save read it under this revision's rules and label
        self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-19'})
        self.drain()
        self.assertEqual(self.provider.sent, [dated, dateless])  # the retained dated run is reused: nothing new
        self.assertEqual(self.proposal(encounter_id, '45378')['status'], 'ready')
        self.assertTrue(models.DecisionInvalidation.objects.filter(decision=approved).exists())  # stays invalidated

    def test_re_saving_the_installed_date_first_sends_nothing_and_carries_the_decision(self):  # CTS-6 (i)
        encounter_id = self.start(RULE_A, '2026-10-19')
        approved = self.approve(encounter_id)
        self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-19'})
        self.drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(self.proposal(encounter_id, '45378')['status'], 'ready')
        self.assertTrue(models.Decision.objects.filter(carried_from=approved).exists())
        self.assertFalse(models.DecisionInvalidation.objects.filter(decision=approved).exists())

    def test_a_narrowed_document_holds_a_member_date_of_another_day(self):  # CTS-6 (ii)
        encounter_id = self.start(NARROWED, None)
        with mock.patch.multiple(jobs, **INSTALLED_LABELS), \
                mock.patch('studio.gi.context.extract_context', return_value=installed_reading(NARROWED, None)):
            self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-30'})
            self.drain()  # before the install: installed takes the member's 2026-10-30 and sends it
        sent = list(self.provider.sent)
        self.assertEqual(sent[-1], self.provider.build_request(NARROWED, dt.date(2026, 10, 30)).canonical_sha256)
        self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'asc'})  # after it
        self.drain()
        self.assertEqual(self.provider.sent, sent)  # nothing is sent
        fact = models.Encounter.objects.get(pk=encounter_id).current_context.facts['service_date']
        self.assertTrue(is_member_conflict(fact))
