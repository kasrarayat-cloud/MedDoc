"""The customer website's fixtures (tests/fixtures/customer/*.json) are the customer serializer's own output
(CORE-UX-DESIGN.md 5, 7), as tests/test_frontend_harness2.py holds the operator fixtures to the operator serializer.

Every file the customer page's tests (tests/frontend/app.test.cjs) and the dev preview server (ops/dev_preview_server.cjs)
read is generated here, by name. Each scenario is driven through the real endpoints and the real pipeline
(tests.test_harness_pipeline's fakes; no network): the participants are its in-process fakes, Corti its scripted fake
or - for Mara - the retained response bytes of the live synthetic case (tests/fixtures/cux/mara), replayed in process;
the CMS reference store is the synthetic one an installation imports (tests.test_harness2_pipeline). The GI encounter
whose documented services, acts, lesions and modifier considerations are hand-built is persisted through
review.persist_assessment, as the pipeline factories do. Every payload is then read from GET /api/... as a member reads
it. CPT_STUDIO_WRITE_FIXTURES=1 writes them again with stable ids and times; otherwise the committed files must carry
exactly the keys, at every level, and the leaf types the serializer emits now (tests.test_frontend_harness2.shape), so
a change to the customer contract fails here until the website is built for it. Each scenario is also held to what the
page's tests read it for, so a regenerated file that stops showing its scenario fails here first.
"""
import hashlib
import json
import os
import re
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from studio import jobs, models, review
from studio.providers.corti import ADAPTER_VERSION, build_coding_request
from studio.types import RawExchange
from tests.support import factories as f
from tests.support import operator as ops
from tests.test_customer_surface import GI_TWO_LESIONS, LESION_A, SurfaceCase, assert_contract, assert_rows, assert_session
from tests.test_frontend_harness2 import StableIds, shape
from tests.test_harness2_pipeline import MUE_KEY, MUE_ROW, PFS_KEY, install_reference_store
from tests.test_harness_pipeline import BOTH, FakeParticipant, ScriptedCorti
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_pipeline import LIVE

WRITE_FIXTURES = os.environ.get('CPT_STUDIO_WRITE_FIXTURES') == '1'
FILENAME_STAMP = re.compile(r'(CPT-Studio-(?:draft|approved)-r\d+-)\d{8}T\d{6}')
FIXTURES = Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'customer'
MARA = Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'cux' / 'mara'
# fixture -> the uuid prefix of its scenario
SCENARIOS = {
    'encounter-ready.json': 'c2000000', 'encounter-needs-detail.json': 'c3000000',
    'encounter-action-needed.json': 'c4000000', 'encounter-approved.json': 'c5000000',
    'encounter-failed.json': 'c6000000', 'encounter-stopped.json': 'c7000000',
    'encounter-being-confirmed.json': 'c8000000', 'encounter-gi.json': 'c9000000',
    'encounter-reviewed.json': 'cc000000', 'encounter-mara.json': 'cd000000',
    'encounter-awaiting-detail.json': 'ce000000', 'encounter-partial.json': 'cf000000',
    'encounter-processing.json': 'c1000000', 'encounter-queued.json': 'c0000000',
}
NO_PATIENT_STATUS = OFFICE_NOTE.replace('Patient status: Established patient, last seen 2026-03-02.\n', '')

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
CECUM = 'The colonoscope was advanced to the cecum and the examination was completed.'
SIGMOID_SNARE = 'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
TRANSVERSE_SNARE = 'A 6 mm sessile polyp in the transverse colon was removed with a cold snare.'
ASCENDING_BIOPSY = 'A 3 mm sessile polyp in the ascending colon was biopsied with cold forceps.'


def colonoscopy(day, *lines, patient=''):
    """A synthetic colonoscopy report of its own (each scenario that sends reads a document of its own)."""
    head = HEAD + 'Colonoscopy report (fictional)\n' + (f'Patient: {patient}\n' if patient else '')
    return (head + f'Date of service: {day}\nPlace of service: Ambulatory surgery center\nProcedure: Colonoscopy\n'
            + CECUM + '\n' + ''.join(f'{line}\n' for line in lines))


# the page's "ready" document: a polyp biopsied and two removed by cold snare (the snare code citing both removals,
# each code with the separate-lesion modifier review), and a patient line the page's planted-name control rewrites
READY = colonoscopy('2026-11-02', ASCENDING_BIOPSY, SIGMOID_SNARE, TRANSVERSE_SNARE, patient='Riley Synthetic')
# two lesions treated by different acts: the separate-lesion modifier review with its dated CMS source
REVIEWED = colonoscopy('2026-11-03', ASCENDING_BIOPSY, SIGMOID_SNARE)
# a diagnostic base beside its snare removal (asked whether it is reported separately) and a stated office visit with
# its basis not documented (its questions asked)
AWAITING = colonoscopy('2026-11-04', SIGMOID_SNARE, 'An office visit was also completed today.')


def note(number, text=OFFICE_NOTE):
    """The scenario's own document: an identical request is never sent twice (a retained answer is reused), so each
    scenario that sends reads a document of its own."""
    return text.replace('Chief complaint\n', f'Chief complaint\nFollow-up visit number {number}.\n')


class CitingCorti(ScriptedCorti):
    """Corti's fake whose selections may cite several passages for one code: [(code, (quote, ...))], one code entry
    with one evidence per quote, each at its exact place in the document."""

    def __init__(self, selections):
        super().__init__()
        self.citing = list(selections)

    def send(self, request, *, deadline_s):
        self.requests.append(request)
        text = request.contexts[0]
        codes = [{'system': 'cpt', 'code': code, 'display': 'UNVERIFIED PROVIDER WORDING', 'alternatives': [],
                  'evidences': [{'contextIndex': 0, 'start': text.index(quote), 'end': text.index(quote) + len(quote),
                                 'text': quote} for quote in quotes]} for code, quotes in self.citing]
        data = json.dumps({'codes': codes, 'candidates': [], 'usageInfo': {'creditsConsumed': 0.02}}).encode()
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                           response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=12.5,
                           usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')


class RetainedCorti:
    """Corti's adapter shape for Mara: the real request builder; its send answers with the retained response bytes of
    the live synthetic case (nothing is sent)."""
    name, adapter_version, mode = 'corti', ADAPTER_VERSION, 'live'

    def __init__(self):
        self.body = (MARA / 'corti-response.json').read_bytes()

    def build_request(self, text, service_date):
        return build_coding_request(self.name, self.adapter_version, text, service_date,
                                    settings.PROVIDER_MAX_REQUEST_BYTES)

    def send(self, request, *, deadline_s):
        return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=self.body,
                           response_sha256=hashlib.sha256(self.body).hexdigest(), latency_ms=1.0, usage={},
                           usage_basis='retained_fixture_replayed_in_process')


@override_settings(**LIVE, **BOTH)
class CustomerFixtureTests(SurfaceCase):
    maxDiff = None

    def setUp(self):
        super().setUp()
        self.mara = (MARA / 'rev1.txt').read_text(encoding='utf-8')
        self.inputs += [NO_PATIENT_STATUS, GI_TWO_LESIONS, READY, REVIEWED, AWAITING, self.mara,
                        'Mara Ellison (synthetic)']
        self.agent = f.member(self.ws, f.user('reviewbot', actor_kind=models.User.AGENT))
        install_reference_store()
        # the synthetic store's upper-endoscopy rows, beside its colonoscopy and office-visit rows
        pfs, mue = models.ReferenceSource.objects.get(key=PFS_KEY), models.ReferenceSource.objects.get(key=MUE_KEY)
        for value, facts in (('43235', {'status': 'A', 'global_days': '000', 'mult_proc': '2', 'endo_base': None,
                                        'pctc': '0'}),
                             ('43239', {'status': 'A', 'global_days': '000', 'mult_proc': '3', 'endo_base': '43235',
                                        'pctc': '0'})):
            models.ReferenceCodeFact.objects.create(source=pfs, code=value, facts=facts)
            models.ReferenceCodeFact.objects.create(source=mue, code=value, facts=MUE_ROW)

    def read(self, encounter_id, user=None):
        client = self.signed_in(user or self.reviewer)
        detail = client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(detail.status_code, 200, detail.content)
        assert_contract(self, detail.json())
        return detail.json()

    def agreeing(self, selections):
        """Both participants read what Corti cites: their first readings agree, and their peer reviews add nothing."""
        for name in ('astra', 'fable'):
            self.adapters[name] = FakeParticipant(name, codes=[(code, quotes[0]) for code, quotes in selections])

    def sent_gi(self, text, selections, **extra):
        """A GI document through the pipeline: Corti (CitingCorti) and both participants cite ``selections``."""
        self.agreeing(selections)
        with mock.patch('studio.jobs.get_provider', return_value=CitingCorti(selections)):
            encounter_id = self.create(text=text, **extra)
            drain()
        return encounter_id

    def decide(self, encounter_id, code, action, user, modifiers=None):
        doc = self.read(encounter_id, user)
        (row,) = [item for item in doc['codes'] if item['code'] == code]
        body = {'proposal_id': row['id'], 'action': action}
        if action == 'approve':
            body['acknowledgement'] = review.ACKNOWLEDGEMENTS[user.actor_kind]
        if modifiers is not None:
            body['modifiers'] = modifiers
        response = self.signed_in(user).post(f'/api/encounters/{encounter_id}/decisions', data=json.dumps(body),
                                             content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)

    def export(self, encounter_id, kind, fmt, user=None):
        response = self.signed_in(user or self.reviewer).post(
            f'/api/encounters/{encounter_id}/reports', data=json.dumps({'kind': kind, 'fmt': fmt}),
            content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)

    def scenarios(self):
        out = {}
        # ready: the snare code citing both of its removals beside a biopsy of another lesion, every check done
        out['encounter-ready.json'] = self.read(self.sent_gi(READY, [('45380', (ASCENDING_BIOPSY,)),
                                                                    ('45385', (SIGMOID_SNARE, TRANSVERSE_SNARE))],
                                                             title='Synthetic colonoscopy, three polyps'))
        # reviewed: separate lesions, both approved by the review agent (one with the distinct-lesion modifier XS); an
        # approved export made before one approval was revoked and given again (stale) and one made after (current)
        reviewed = self.sent_gi(REVIEWED, [('45380', (ASCENDING_BIOPSY,)), ('45385', (SIGMOID_SNARE,))],
                                title='Synthetic colonoscopy, two lesions')
        self.decide(reviewed, '45380', 'approve', self.agent, ['XS'])
        self.decide(reviewed, '45385', 'approve', self.agent)
        self.export(reviewed, 'approved', 'txt', self.agent)
        self.decide(reviewed, '45385', 'revoke', self.agent)
        self.decide(reviewed, '45385', 'approve', self.agent)
        self.export(reviewed, 'approved', 'csv', self.agent)
        out['encounter-reviewed.json'] = self.read(reviewed)
        # Mara: the owner's worked example, uploaded as the document it is and read with Corti's retained answer
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled'), \
                mock.patch('studio.jobs.get_provider', return_value=RetainedCorti()):
            upload = SimpleUploadedFile('mara-ellison-synthetic.txt', self.mara.encode('utf-8'),
                                        content_type='text/plain')
            response = self.client.post('/api/encounters', {'file': upload, 'title': 'Mara Ellison (synthetic)',
                                                            'synthetic_attestation': 'yes'})
            self.assertEqual(response.status_code, 201, response.content)
            mara = response.json()['id']
            drain()
        self.assertEqual(self.encounter(mara).current_revision.text, self.mara)
        out['encounter-mara.json'] = self.read(mara)
        # awaiting detail: one code reviewable while another waits on a detail, a visit's questions, one answered
        awaiting = self.sent_gi(AWAITING, [('45378', (CECUM,)), ('45385', (SIGMOID_SNARE,))],
                                title='Synthetic colonoscopy and office visit')
        doc = self.read(awaiting)
        (basis,) = [row for row in doc['details_needed'] if row['fact'] == 'em_basis']
        saved = self.signed_in(self.reviewer).post(
            f'/api/encounters/{awaiting}/details', content_type='application/json',
            data=json.dumps({'answers': [{'id': basis['id'], 'fact': 'em_basis', 'value': 'not_documented'}]}))
        self.assertEqual(saved.status_code, 201, saved.content)
        out['encounter-awaiting-detail.json'] = self.read(awaiting)
        # partial: an independent check failed, the results stand
        self.adapters['astra'] = FakeParticipant('astra', codes=self.astra_codes, outcome='failed')
        self.adapters['fable'] = FakeParticipant('fable', codes=self.fable_codes)
        partial = self.create(text=note(9), title='Synthetic office follow-up 9')
        drain()
        out['encounter-partial.json'] = self.read(partial)
        self.adapters['astra'] = FakeParticipant('astra', codes=self.astra_codes)
        detail = self.create(text=note(3, NO_PATIENT_STATUS), title='Synthetic office follow-up 3')
        drain()
        out['encounter-needs-detail.json'] = self.read(detail)
        held = self.create(text=note(4), service_date='2026-10-01', title='Synthetic office follow-up 4')
        drain()
        out['encounter-action-needed.json'] = self.read(held)
        approved = self.create(text=note(5), title='Synthetic office follow-up 5')
        drain()
        self.decide_all(approved)
        for kind, fmt in (('approved', 'txt'), ('draft', 'csv')):
            self.export(approved, kind, fmt)
        out['encounter-approved.json'] = self.read(approved)
        self.corti.outcomes = ['failed']
        failed = self.create(text=note(6), title='Synthetic office follow-up 6')
        drain()
        out['encounter-failed.json'] = self.read(failed)
        stopped = self.create(text=note(7), title='Synthetic office follow-up 7')
        self.post(f'/api/encounters/{stopped}/stop', {})
        out['encounter-stopped.json'] = self.read(stopped)
        self.corti.outcome = 'unknown'
        unknown = self.create(text=note(8), title='Synthetic office follow-up 8')
        drain()
        self.corti.outcome = 'succeeded'
        out['encounter-being-confirmed.json'] = self.read(unknown)
        out['encounter-gi.json'] = self.read(self.gi_encounter())
        # processing: read and analysed, its document review running (claimed, as a worker claims it); queued: just
        # uploaded. Made last, so nothing else is drained past them.
        processing = self.create(text=note(1), title='Synthetic office follow-up 1')
        for _ in range(2):
            jobs.run_job(jobs.claim_next())
        running = jobs.claim_next()
        self.assertEqual(running.state, models.Job.RUNNING)
        out['encounter-processing.json'] = self.read(processing)
        out['encounter-queued.json'] = self.read(self.create(text=note(10), title='Synthetic office follow-up 10'))
        return out

    def assertScenarios(self, details, session, agent_session, rows):
        """Each scenario shows what the page's tests read it for (tests/frontend/app.test.cjs)."""
        self.assertEqual({name: (doc['state'], doc['progress']['phase']) for name, doc in details.items()}, {
            'encounter-ready.json': ('ready', 'completed'), 'encounter-reviewed.json': ('reviewed', 'completed'),
            'encounter-mara.json': ('ready', 'completed'),
            'encounter-awaiting-detail.json': ('awaiting_detail', 'awaiting_detail'),
            'encounter-partial.json': ('ready', 'partial'),
            'encounter-needs-detail.json': ('awaiting_detail', 'awaiting_detail'),
            'encounter-action-needed.json': ('action_needed', 'action_needed'),
            'encounter-approved.json': ('reviewed', 'completed'), 'encounter-failed.json': ('failed', 'failed'),
            'encounter-stopped.json': ('stopped', 'stopped'),
            'encounter-being-confirmed.json': ('being_confirmed', 'being_confirmed'),
            'encounter-gi.json': ('ready', 'completed'), 'encounter-processing.json': ('processing', 'processing'),
            'encounter-queued.json': ('processing', 'queued')})
        ready = details['encounter-ready.json']
        self.assertEqual([(code['code'], code['status']) for code in ready['codes']], [('45380', 'ready'),
                                                                                       ('45385', 'ready')])
        snare = ready['codes'][1]
        self.assertTrue(len(snare['why']['quotes']) >= 2 and snare['why']['qualifications'] and snare['modifier_review'])
        self.assertRegex(ready['document']['text'], r'Patient: \w+')
        reviewed = details['encounter-reviewed.json']
        self.assertTrue(reviewed['readiness']['approved'])
        self.assertEqual([(code['code'], code['status'], code['decision']['by_kind'], code['modifiers'])
                          for code in reviewed['codes']], [('45380', 'approved', 'agent', ['XS']),
                                                           ('45385', 'approved', 'agent', [])])
        self.assertEqual(sorted(report['current'] for report in reviewed['reports']), [False, True])
        mara = details['encounter-mara.json']
        self.assertEqual([(code['code'], code['status']) for code in mara['codes']],
                         [('43239', 'ready'), ('45380', 'ready'), ('45385', 'ready')])
        self.assertEqual([bool(code['modifier_review']) for code in mara['codes']], [False, True, True])
        for code in mara['codes']:
            self.assertTrue(code['why']['quotes'], code['code'])
            if code['modifier_review']:
                self.assertRegex(' '.join(code['modifier_review']['sources']), r'\d{4}-\d{2}-\d{2}', code['code'])
        self.assertTrue(mara['other_codes'] and mara['not_separately_coded'] and mara['limitations'])
        self.assertTrue(mara['document']['original_url'] and mara['service_date']['document_quote'])
        self.assertEqual((mara['readiness']['draft'], mara['readiness']['approved']), (True, False))
        self.assertEqual(mara['details_needed'], [])
        awaiting = details['encounter-awaiting-detail.json']
        self.assertEqual({code['code']: code['status'] for code in awaiting['codes']},
                         {'45378': 'needs_detail', '45385': 'ready'})
        controls = {(row['control'], row['saved'] is not None) for row in awaiting['details_needed']}
        self.assertTrue({('choice', False), ('confirm', False), ('confirm', True)} <= controls, controls)
        action = details['encounter-action-needed.json']
        (date,) = action['details_needed']  # while the date is held it is the one detail asked
        self.assertEqual((date['document_value'], date['entered_value'], bool(date['quote'])),
                         ('2026-10-20', '2026-10-01', True))
        self.assertFalse(action['progress']['busy'])
        processing = details['encounter-processing.json']
        self.assertEqual([step['state'] for step in processing['progress']['steps']].count('active'), 1)
        self.assertTrue(processing['progress']['active_detail'] and processing['progress']['can_stop'])
        self.assertEqual(details['encounter-queued.json']['progress']['steps'][0]['state'], 'waiting')
        stopped = details['encounter-stopped.json']
        self.assertTrue(stopped['progress']['can_resume'] and stopped['document']['original_url'] is None)
        self.assertEqual(details['encounter-partial.json']['checks'][1]['state'], 'unavailable')
        gi = details['encounter-gi.json']
        self.assertEqual([(code['code'], code['status']) for code in gi['codes']],
                         [('43239', 'approved'), ('45380', 'ready'), ('45385', 'ready'), ('45378', 'excluded')])
        self.assertEqual(gi['codes'][0]['sub_label'], 'Agent-executed synthetic review — not clinical approval')
        self.assertEqual([code['modifier_review']['options'] if code['modifier_review'] else None
                          for code in gi['codes']], [None, ['59', 'XS'], ['59', 'XS'], None])
        self.assertEqual(gi['other_codes'], [{'code': '45381', 'reason': 'Listed as an alternative only; not suggested '
                                                                       'for approval.'}])
        self.assertEqual(gi['not_separately_coded'], [{'label': 'Clip placement at the sigmoid colon (Colonoscopy)',
                                                       'reason': 'A clip placed to prevent bleeding is not reported as a '
                                                                 'separate service.'}])
        self.assertEqual([quote['text'] for quote in gi['codes'][1]['why']['quotes']], [LESION_A])
        self.assertTrue(details['encounter-needs-detail.json']['details_needed'])
        self.assertTrue(details['encounter-approved.json']['readiness']['approved'])
        self.assertEqual({report['kind'] for report in details['encounter-approved.json']['reports']},
                         {'approved', 'draft'})
        # the list is every encounter of the workspace; the queue lists the rows marked in_queue - the three customer
        # states that wait on the member and every encounter the review queue's rule holds waiting (the operator view's
        # queue_reasons) - and the session counts exactly those rows (session decision (o), 2026-11-04)
        self.assertEqual(sorted(row['id'] for row in rows), sorted(doc['id'] for doc in details.values()))
        queue = {row['id'] for row in rows if row['state'] in ('action_needed', 'awaiting_detail', 'ready')}
        self.assertEqual({row['state'] for row in rows if row['id'] in queue}, {'action_needed', 'awaiting_detail', 'ready'})
        waiting = {row['id'] for row in ops.client(f.user('platform-operator')).get('/ops/api/encounters').json()
                   ['encounters'] if row['queue_reasons']}
        self.assertGreater(len(waiting - queue), 0, 'a scenario the review queue holds beyond the three states')
        listed = {row['id'] for row in rows if row['in_queue'] is True}
        self.assertEqual(listed, queue | waiting)
        self.assertEqual((session['counts']['queue'], agent_session['counts']['queue']), (len(listed), len(listed)))
        self.assertEqual((session['user']['actor_kind'], agent_session['user']['actor_kind']), ('human', 'agent'))

    def test_the_customer_fixtures_are_what_the_customer_serializer_emits(self):
        details = self.scenarios()
        session = self.signed_in(self.reviewer).get('/api/session').json()
        agent_session = self.signed_in(self.agent).get('/api/session').json()
        for doc in (session, agent_session):
            assert_session(self, doc)
        rows = self.signed_in(self.reviewer).get('/api/encounters').json()
        assert_rows(self, rows['encounters'])
        elsewhere = f.member(f.workspace(), f.user('newcomer'))  # a member of a workspace with no document yet
        empty = self.signed_in(elsewhere).get('/api/encounters').json()
        self.assertEqual(empty, {'encounters': []})
        self.assertScenarios(details, session, agent_session, rows['encounters'])
        texts = {name: json.dumps(doc, ensure_ascii=False) for name, doc in details.items()}
        texts['session.json'] = json.dumps(session, ensure_ascii=False)
        texts['session-agent.json'] = json.dumps(agent_session, ensure_ascii=False)
        texts['encounters.json'] = json.dumps(rows, ensure_ascii=False)
        texts['encounters-empty.json'] = json.dumps(empty, ensure_ascii=False)
        # an export's file name carries its generation time in its own form: made stable as StableIds makes ISO times
        texts = {name: FILENAME_STAMP.sub(r'\g<1>20261101T090000', text) for name, text in texts.items()}
        stable = StableIds(list(texts.values()))
        generated = {}
        for name, prefix in SCENARIOS.items():
            generated[name] = stable(texts[name], prefix)
        for name, prefix in (('session.json', 'ca000000'), ('session-agent.json', 'ca100000'),
                             ('encounters.json', 'cb000000'), ('encounters-empty.json', 'cb100000')):
            generated[name] = stable(texts[name], prefix)
        self.assertClean([(name, json.dumps(doc)) for name, doc in generated.items()])
        if WRITE_FIXTURES:
            FIXTURES.mkdir(parents=True, exist_ok=True)
            for name, data in generated.items():
                (FIXTURES / name).write_text(json.dumps(data, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
        committed = sorted(path.name for path in FIXTURES.glob('*.json'))
        self.assertEqual(committed, sorted(generated), 'every customer fixture is generated here, and only those')
        for name, data in generated.items():
            with self.subTest(name):
                stored = json.loads((FIXTURES / name).read_text(encoding='utf-8'))
                self.assertEqual(sorted(shape(stored) ^ shape(data)), [],
                                 f'{name} no longer has the shape the customer serializer emits; regenerate it with '
                                 'CPT_STUDIO_WRITE_FIXTURES=1 and build the website for the change')
