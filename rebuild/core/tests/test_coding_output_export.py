"""Offline integration checks for the separate accepted API-output appendix.

The support/permission/decision service is isolated here; its real persisted
decision checks are tested separately. No fixture decision represents a user
decision, and no provider operation occurs.
"""
import copy
from contextlib import contextmanager
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from core import coding_service as service
from core.coding_export import append_codes
from core.tests import test_coding_export as original_export


@override_settings(ADMIN_SITE=False, SYNTHETIC_ONLY=True, CODING_PROVIDER='existing')
class AcceptedOutputExport(TestCase):
    setUp = original_export.CodingWordExport.setUp
    save_decision = original_export.CodingWordExport.save_decision
    download = original_export.CodingWordExport.download
    returned_review = original_export.CodingWordExport.returned_review
    forged_selection = original_export.CodingWordExport.forged_selection

    def output(self, **changes):
        return {'system': 'CPT', 'code': '00000', 'description': '15 MINUTES',
                'description_status': 'withheld_defective_provider_text',
                'evidence_spans': [{'quote': 'Synthetic finding.'}],
                'permission_basis': {'id': 'EXPLICIT-OFFLINE-TEST-ONLY'},
                'selection_support': {'status': 'supported', 'fixture': True},
                **changes}

    @contextmanager
    def with_icd_evidence(self):
        run, decision = copy.deepcopy(self.run), copy.deepcopy(self.decision)
        run.result['suggestions'][0]['evidence_spans'] = [
            {'text': 'Synthetic finding.', 'status': 'valid', 'start': 0, 'end': 18}]
        decision.selection_digest = service.selection_digest(run)
        with self.returned_review(run, decision):
            yield

    def content(self, response):
        self.assertEqual(response.status_code, 200)
        result = b''.join(response.streaming_content)
        response.file_to_stream.close()
        return result

    def test_pending_output_keeps_original_approved_bytes_and_ignores_query_acceptance(self):
        with patch('core.coding_output.accepted_output_rows', return_value=[]):
            actual = self.content(self.download(query='?accept_cpt=00000&confirmed=true'))
        expected = append_codes(self.original, [{'system': 'ICD-10-CM', 'code': 'Z00.00',
                                                 'description': 'Synthetic accepted description'}])
        self.assertEqual(actual, expected)
        self.assertNotIn('CPT', original_export.texts(actual))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_accepted_number_evidence_variant_is_bound_separately_and_preserves_original(self):
        with patch('core.coding_output.accepted_output_rows', return_value=[]):
            historical = self.content(self.download())
        historical_path = next((self.root / 'exports' / 'coding').rglob('*.docx'))
        with patch('core.coding_output.accepted_output_rows', return_value=[self.output()]), self.with_icd_evidence():
            actual = self.content(self.download())
            self.assertEqual(self.content(self.download()), actual)
        text = original_export.texts(actual)
        self.assertIn('00000 — clinician-accepted code number', text)
        self.assertEqual(text.count('Original-note evidence: Synthetic finding.'), 2)
        self.assertNotIn('15 MINUTES', '\n'.join(text))
        self.assertNotIn('Z00.01', '\n'.join(text))
        self.assertEqual(text.count('Diagnosis and procedure codes'), 1)
        self.assertIn('not for billing or real-patient use', '\n'.join(text))
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(historical_path.read_bytes(), historical)
        self.assertEqual(len(list((self.root / 'exports' / 'coding').rglob('*.docx'))), 2)
        with ZipFile(BytesIO(self.original)) as before, ZipFile(BytesIO(actual)) as after:
            self.assertEqual(before.namelist(), after.namelist())
            for name in before.namelist():
                if name != 'word/document.xml':
                    self.assertEqual(before.read(name), after.read(name), name)
            clinical = before.read('word/document.xml')
            self.assertTrue(after.read('word/document.xml').startswith(clinical[:clinical.rindex(b'<w:sectPr')]))

    def test_current_support_failure_refuses_cached_accepted_variant(self):
        with patch('core.coding_output.accepted_output_rows', return_value=[self.output()]):
            prior = self.content(self.download())
        cached = next((self.root / 'exports' / 'coding').rglob('*.docx'))
        with patch('core.coding_output.accepted_output_rows', side_effect=ValidationError('Accepted support is stale.')):
            response = self.download()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(cached.read_bytes(), prior)

    def test_unselected_candidate_and_duplicate_output_cannot_enter_appendix(self):
        for outputs in ([self.output(code='99999')], [self.output(), self.output()]):
            with self.subTest(outputs=outputs), patch('core.coding_output.accepted_output_rows', return_value=outputs):
                self.assertEqual(self.download().status_code, 409)
        self.assertFalse((self.root / 'exports' / 'coding').exists())

    def test_missing_nonmatching_and_invalid_evidence_fail_closed(self):
        for spans in (None, [], [{'quote': 'Invented support.'}], [{'text': 'Synthetic finding.', 'status': 'invalid'}]):
            with self.subTest(spans=spans), patch('core.coding_output.accepted_output_rows',
                                                return_value=[self.output(evidence_spans=spans)]):
                self.assertEqual(self.download().status_code, 409)
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_original_held_approval_cannot_use_supplement_to_bypass_eligibility(self):
        with self.returned_review(*self.forged_selection(['held'])), \
                patch('core.coding_output.accepted_output_rows', return_value=[self.output()]) as supplement:
            self.assertEqual(self.download().status_code, 409)
        supplement.assert_not_called()

    def test_no_output_can_supply_a_verified_or_catalogue_description_through_this_route(self):
        with patch('core.coding_output.accepted_output_rows',
                   return_value=[self.output(description_status='verified')]):
            self.assertEqual(self.download().status_code, 409)

    def test_duplicate_appendix_is_refused_even_for_accepted_output(self):
        with patch('core.coding_output.accepted_output_rows', return_value=[self.output()]):
            actual = self.content(self.download())
        with self.assertRaisesMessage(ValidationError, 'already contains'):
            append_codes(actual, [self.output(export_route='bounded_api_output')])
