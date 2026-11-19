"""Harness repair 2026-11-05 (HARNESS.md P-ADMIT), through the real pipeline and the customer surfaces: a code only the
independent participants proposed, admitted by CPT Studio's readers, is an ordinary numbered code a member decides;
no customer response, page payload or download names a participant, model or provider; and a code the numbered list
suggests is never listed again under "other codes" as not suggested."""
import json
from unittest import mock

from tests.legacy_chain import applied
from tests.test_customer_surface import SurfaceCase
from tests.test_harness_pipeline import REAL_ENGINE
from tests.test_pipeline_api import drain

COLON = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
         'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
         'Procedure: Colonoscopy\n'
         'The colonoscope was advanced to the cecum and the examination was completed.\n'
         'Cold forceps biopsies of the cecum were obtained for histology.\n'
         'A separate 7 mm sessile polyp in the sigmoid colon was removed with a cold snare and retrieved.\n')
BIOPSY = 'Cold forceps biopsies of the cecum were obtained for histology.'
SNARE = 'A separate 7 mm sessile polyp in the sigmoid colon was removed with a cold snare and retrieved.'


@applied
class AdmittedParticipantCodeTests(SurfaceCase):
    astra_codes = (('45385', SNARE),)
    fable_codes = (('45385', SNARE), ('45380', BIOPSY))

    def setUp(self):
        super().setUp()
        self.corti.selections = [('45380', BIOPSY)]
        # HarnessCase's recording_engine calls the real engine WITHOUT the participants; admission is the engine's own
        # merge, so this case runs the real engine with every input the pipeline gives it
        patcher = mock.patch('studio.jobs.run_assessment', side_effect=lambda **kwargs: REAL_ENGINE(**kwargs))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_admitted_code_is_an_ordinary_numbered_code_and_no_surface_names_who_proposed_it(self):
        encounter_id = self.create(text=COLON)
        drain()
        assessment = self.encounter(encounter_id).current_assessment
        stored = {p.code: p for p in assessment.proposals.filter(bucket='selected')}
        self.assertEqual(set(stored), {'45380', '45385'},
                         [(p.code, p.bucket, p.status, p.exclusion_reason[:120]) for p in assessment.proposals.all()])
        self.assertEqual((stored['45385'].support or {}).get('origin'), 'participant')
        doc = self.detail(encounter_id)
        rows = {row['code']: row for row in doc['codes']}
        self.assertEqual(rows['45385']['status'], 'ready')
        self.assertIn('approve', rows['45385']['allowed_actions'])  # a member decides it; nothing approved it
        self.assertIsNone(rows['45385']['decision'])
        numbered = set(rows)
        self.assertFalse([item for item in doc['other_codes'] if item['code'] in numbered], doc['other_codes'])
        # a draft export in both formats, then every customer response, page payload and download for every role
        for fmt in ('txt', 'csv'):
            response = self.signed_in(self.reviewer).post(f'/api/encounters/{encounter_id}/reports',
                                                          data=json.dumps({'kind': 'draft', 'fmt': fmt}),
                                                          content_type='application/json')
            self.assertEqual(response.status_code, 201, response.content)
        texts = self.surface(encounter_id)
        self.assertClean(texts)
        for label, text in texts:
            for word in ('Astra', 'Fable', 'Corti', 'gpt-6-astra', 'claude-fable', 'OpenAI', 'Anthropic',
                         'independent participant', 'Proposed by'):
                self.assertNotIn(word, text, label)
