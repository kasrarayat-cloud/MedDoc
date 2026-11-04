"""The customer website's fixtures (tests/fixtures/customer/*.json) are the customer serializer's own output
(CORE-UX-DESIGN.md 5, 7), as tests/test_frontend_harness2.py holds the operator fixtures to the operator serializer.

Each scenario is driven through the real endpoints and the real pipeline (tests.test_harness_pipeline's fakes; no
network), or - for the GI encounter, whose documented services, acts, lesions and modifier considerations the fakes do
not read - persisted from hand-built rows through review.persist_assessment, as the pipeline factories do; every
payload is then read from GET /api/... as a member reads it. CPT_STUDIO_WRITE_FIXTURES=1 writes them again with stable
ids and times; otherwise the committed files must carry exactly the keys, at every level, and the leaf types the
serializer emits now (tests.test_frontend_harness2.shape), so a change to the customer contract fails here until the
website is built for it. Every detail fixture is also held to the contract's key sets (test_customer_surface).
"""
import json
import os
import re
from pathlib import Path

from django.conf import settings
from django.test import override_settings

from tests.test_customer_surface import GI_TWO_LESIONS, LESION_A, SurfaceCase, assert_contract, assert_rows, assert_session
from tests.test_frontend_harness2 import StableIds, shape
from tests.test_harness_pipeline import BOTH
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_pipeline import LIVE

WRITE_FIXTURES = os.environ.get('CPT_STUDIO_WRITE_FIXTURES') == '1'
FILENAME_STAMP = re.compile(r'(CPT-Studio-(?:draft|approved)-r\d+-)\d{8}T\d{6}')
FIXTURES = Path(settings.BASE_DIR) / 'tests' / 'fixtures' / 'customer'
# fixture -> the uuid prefix of its scenario
SCENARIOS = {
    'encounter-processing.json': 'c1000000', 'encounter-ready.json': 'c2000000',
    'encounter-needs-detail.json': 'c3000000', 'encounter-action-needed.json': 'c4000000',
    'encounter-approved.json': 'c5000000', 'encounter-failed.json': 'c6000000', 'encounter-stopped.json': 'c7000000',
    'encounter-being-confirmed.json': 'c8000000', 'encounter-gi.json': 'c9000000',
}
NO_PATIENT_STATUS = OFFICE_NOTE.replace('Patient status: Established patient, last seen 2026-03-02.\n', '')
def note(number, text=OFFICE_NOTE):
    """The scenario's own document: an identical request is never sent twice (a retained answer is reused), so each
    scenario that sends reads a document of its own."""
    return text.replace('Chief complaint\n', f'Chief complaint\nFollow-up visit number {number}.\n')


@override_settings(**LIVE, **BOTH)
class CustomerFixtureTests(SurfaceCase):
    maxDiff = None

    def setUp(self):
        super().setUp()
        self.inputs += [NO_PATIENT_STATUS, GI_TWO_LESIONS]

    def read(self, encounter_id, user=None):
        client = self.signed_in(user or self.reviewer)
        detail = client.get(f'/api/encounters/{encounter_id}')
        self.assertEqual(detail.status_code, 200, detail.content)
        assert_contract(self, detail.json())
        return detail.json()

    def scenarios(self):
        out = {}
        out['encounter-processing.json'] = self.read(self.create(text=note(1)))
        ready = self.create(text=note(2))
        drain()
        out['encounter-ready.json'] = self.read(ready)
        detail = self.create(text=note(3, NO_PATIENT_STATUS))
        drain()
        out['encounter-needs-detail.json'] = self.read(detail)
        held = self.create(text=note(4), service_date='2026-10-01')
        drain()
        out['encounter-action-needed.json'] = self.read(held)
        approved = self.create(text=note(5))
        drain()
        self.decide_all(approved)
        client = self.signed_in(self.reviewer)
        for kind, fmt in (('approved', 'txt'), ('draft', 'csv')):
            response = client.post(f'/api/encounters/{approved}/reports', data=json.dumps({'kind': kind, 'fmt': fmt}),
                                   content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
        out['encounter-approved.json'] = self.read(approved)
        self.corti.outcomes = ['failed']
        failed = self.create(text=note(6))
        drain()
        out['encounter-failed.json'] = self.read(failed)
        stopped = self.create(text=note(7))
        self.post(f'/api/encounters/{stopped}/stop', {})
        out['encounter-stopped.json'] = self.read(stopped)
        self.corti.outcome = 'unknown'
        unknown = self.create(text=note(8))
        drain()
        self.corti.outcome = 'succeeded'
        out['encounter-being-confirmed.json'] = self.read(unknown)
        out['encounter-gi.json'] = self.read(self.gi_encounter())
        return out

    def test_the_customer_fixtures_are_what_the_customer_serializer_emits(self):
        details = self.scenarios()
        # the scenarios show what they are for
        self.assertEqual({name: doc['state'] for name, doc in details.items()}, {
            'encounter-processing.json': 'processing', 'encounter-ready.json': 'ready',
            'encounter-needs-detail.json': 'awaiting_detail', 'encounter-action-needed.json': 'action_needed',
            'encounter-approved.json': 'reviewed', 'encounter-failed.json': 'failed',
            'encounter-stopped.json': 'stopped', 'encounter-being-confirmed.json': 'being_confirmed',
            'encounter-gi.json': 'ready'})
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
        session = self.signed_in(self.reviewer).get('/api/session').json()
        assert_session(self, session)
        rows = self.signed_in(self.reviewer).get('/api/encounters').json()
        assert_rows(self, rows['encounters'])
        texts = {name: json.dumps(doc, ensure_ascii=False) for name, doc in details.items()}
        texts['session.json'] = json.dumps(session, ensure_ascii=False)
        texts['encounters.json'] = json.dumps(rows, ensure_ascii=False)
        # an export's file name carries its generation time in its own form: made stable as StableIds makes ISO times
        texts = {name: FILENAME_STAMP.sub(r'\g<1>20261101T090000', text) for name, text in texts.items()}
        stable = StableIds(list(texts.values()))
        generated = {}
        for name, prefix in SCENARIOS.items():
            generated[name] = stable(texts[name], prefix)
        generated['session.json'] = stable(texts['session.json'], 'ca000000')
        generated['encounters.json'] = stable(texts['encounters.json'], 'cb000000')
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
