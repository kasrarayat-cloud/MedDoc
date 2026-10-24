"""Round 4, INGEST lens, end to end: the uploads the verifiers used, through the real API, the extraction child, the
jobs and the validation engine, with an in-process provider stand-in (no network). A service the page shows checked
or performed is never excluded; one whose box cannot be read is held for a reviewer.
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from tests.test_pipeline_api import drain
from tests.test_repairs_pipeline import LIVE
from tests.test_repairs_r4_ingest import mark_over_snare, printed_ticked_under_off, two_column, wrapped_checklist
from tests.test_repairs_r4_ingest_docx import FORCEPS, SNARE, bulleted
from tests.test_repairs_status_r2_validation_api import MultiEvidenceApiCase

DOCX = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


@override_settings(**LIVE)
class UploadsHoldWhatTheyCannotReadTests(MultiEvidenceApiCase, TestCase):
    def upload(self, name, data, content_type, *selections):
        self.provider.selections = list(selections)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'file': SimpleUploadedFile(name, data, content_type),
                                                            'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return response.json()['id']

    def assert_held(self, encounter_id, code):
        proposal = self.proposal(encounter_id, code)
        self.assertNotEqual(proposal['bucket'], 'excluded', proposal)
        self.assertEqual(proposal['status'], 'needs_clarification', proposal)

    def test_a_label_left_box_in_a_two_column_table(self):
        encounter = self.upload('twocol.pdf', two_column(False), 'application/pdf', ('45385', 'Cold snare polypectomy'))
        self.assert_held(encounter, '45385')
        checked = self.upload('twocol-on.pdf', two_column(True), 'application/pdf', ('45385', 'Cold snare polypectomy'))
        self.assertEqual(self.proposal(checked, '45385')['status'], 'ready')

    def test_a_printed_tick_under_an_unchecked_widget(self):
        encounter = self.upload('tick.pdf', printed_ticked_under_off('empty'), 'application/pdf',
                                ('45385', 'Cold snare polypectomy'))
        self.assert_held(encounter, '45385')
        self.assertEqual(self.detail(encounter)['revision']['extraction']['status'], 'partial')

    def test_an_ink_tick_over_a_printed_box(self):
        encounter = self.upload('ink.pdf', mark_over_snare('ink'), 'application/pdf', ('45385', 'Cold snare polypectomy'))
        self.assert_held(encounter, '45385')

    def test_a_wrapped_checklist_with_default_field_names(self):
        encounter = self.upload('wrapped.pdf', wrapped_checklist(True, True), 'application/pdf',
                                ('45385', 'Cold snare polypectomy'), ('45380', 'Biopsy'))
        for code in ('45385', '45380'):
            self.assert_held(encounter, code)

    def test_word_box_bullets_on_an_ordinary_list(self):
        encounter = self.upload('bullets.docx', bulleted('\uf071', 'Wingdings'), DOCX, ('45385', SNARE),
                                ('45380', FORCEPS))
        for code in ('45385', '45380'):
            self.assert_held(encounter, code)
