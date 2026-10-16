"""Offline boundary tests; all terminology below is synthetic, not a CPT feed."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import unittest

from core.corti_response import CatalogRelease, DatedTerminology, adapt_response
from core.corti_response import load_icd_catalog

WHEN = date(2026, 10, 16)


def release(system='icd10cm-outpatient', **kwargs):
    values = dict(system=system, version='TEST-ONLY', effective_from=date(2026, 10, 1),
                  effective_until=date(2027, 9, 30), source='https://example.test/synthetic-fixture',
                  sha256='a' * 64, descriptions={'R12': 'Synthetic description'},
                  authorization_reference='TEST FIXTURE ONLY — NOT A LICENSE')
    values.update(kwargs)
    return CatalogRelease(**values)


class CortiBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.request = {'system': ['icd10cm-outpatient', 'cpt'],
                        'context': [{'type': 'text', 'text': 'Synthetic source text.'}]}
        self.row = {'system': 'icd10cm-outpatient', 'code': 'R12', 'display': 'Synthetic description',
                    'evidences': [{'contextIndex': 0, 'start': 0, 'end': 21, 'text': 'Synthetic source text'}],
                    'alternatives': [{'code': 'K5900', 'display': 'Unselected'}]}
        self.response = {'codes': [self.row], 'candidates': [dict(self.row, code='K59.00')],
                         'usageInfo': {'creditsConsumed': 123}, 'future': {'keep': True}}

    def adapt(self, response=None, **kwargs):
        return adapt_response(self.response if response is None else response, self.request,
                              service_date=WHEN, **kwargs)

    def test_only_selected_and_lossless_diagnostics(self):
        before = deepcopy(self.response)
        result = self.adapt()
        self.assertEqual(['R12'], [p['code'] for p in result['proposed_selections']])
        self.assertEqual(self.response, result['diagnostics']['provider_response'])
        self.assertEqual(self.response['candidates'], result['diagnostics']['candidates'])
        self.assertEqual(self.row['alternatives'], result['diagnostics']['alternatives'][0]['alternatives'])
        result['diagnostics']['provider_response']['future']['keep'] = False
        self.assertEqual(before, self.response)

    def test_candidates_cannot_rescue_empty_or_missing_selected(self):
        self.response['codes'] = []
        self.assertEqual([], self.adapt()['proposed_selections'])
        del self.response['codes']
        with self.assertRaises(ValueError): self.adapt()

    def test_missing_evidence_stays_visible_unapproved(self):
        del self.row['evidences']
        proposal = self.adapt()['proposed_selections'][0]
        self.assertEqual('missing', proposal['evidence_status'])
        self.assertFalse(proposal['approved'])
        self.assertFalse(proposal['selectable'])

    def test_offsets_context_and_quote_mismatch(self):
        for changes in [{'start': -1}, {'end': 100}, {'contextIndex': 2}, {'contextIndex': True},
                        {'start': False}, {'text': 'invented'}, {'end': 1}]:
            with self.subTest(changes=changes):
                response = deepcopy(self.response)
                response['codes'][0]['evidences'][0].update(changes)
                self.assertEqual('invalid', self.adapt(response)['proposed_selections'][0]['evidence_status'])

    def test_evidence_and_original_description_intact(self):
        proposal = self.adapt()['proposed_selections'][0]
        self.assertEqual('valid', proposal['evidence_status'])
        self.assertEqual(self.row['display'], proposal['provider_display'])
        for key in ['start', 'end', 'text']:
            self.assertEqual(self.row['evidences'][0][key], proposal['evidence'][0][key])

    def test_catalogue_dates_and_description(self):
        proposal = self.adapt(terminology=DatedTerminology([release()]))['proposed_selections'][0]
        self.assertEqual('verified', proposal['terminology']['status'])
        self.assertTrue(proposal['terminology']['description_matches'])
        self.assertEqual('requires_clinician_review', proposal['clinical_applicability'])
        self.assertFalse(proposal['approved'])

    def test_unknown_code_kept_unverified(self):
        self.row['code'] = 'R99'
        term = self.adapt(terminology=DatedTerminology([release()]))['proposed_selections'][0]['terminology']
        self.assertEqual('unknown_code', term['status'])
        self.assertIsNone(term['description'])

    def test_no_nearest_year_or_requested_version_fallback(self):
        for term in [DatedTerminology([release(effective_until=date(2026, 10, 15))]),
                     DatedTerminology([release()], required_versions={'icd10cm-outpatient': 'MISSING'})]:
            self.assertEqual('version_unavailable', self.adapt(terminology=term)['proposed_selections'][0]['terminology']['status'])

    def test_release_boundaries_inclusive(self):
        term = DatedTerminology([release(effective_from=WHEN, effective_until=WHEN)])
        self.assertEqual('verified', self.adapt(terminology=term)['proposed_selections'][0]['terminology']['status'])

    def test_unauthorized_and_ambiguous_releases(self):
        for term, status in [(DatedTerminology([release(authorization_reference='')]), 'unauthorized'),
                             (DatedTerminology([release(), release(version='OTHER')]), 'ambiguous_release')]:
            self.assertEqual(status, self.adapt(terminology=term)['proposed_selections'][0]['terminology']['status'])

    def test_dotted_undotted_same_catalogue_key(self):
        self.row['code'] = 'k5900'
        term = DatedTerminology([release(descriptions={'K59.00': 'Synthetic description'})])
        proposal = self.adapt(terminology=term)['proposed_selections'][0]
        self.assertEqual('K59.00', proposal['code'])
        self.assertEqual('k5900', proposal['provider_code'])
        self.assertEqual('verified', proposal['terminology']['status'])

    def test_description_mismatch_is_visible_not_replaced(self):
        self.row['display'] = 'Original defective provider text'
        proposal = self.adapt(terminology=DatedTerminology([release()]))['proposed_selections'][0]
        self.assertEqual(self.row['display'], proposal['provider_display'])
        self.assertFalse(proposal['terminology']['description_matches'])
        self.assertEqual('Synthetic description', proposal['terminology']['description'])
        self.assertTrue(any('no silent replacement' in issue for issue in proposal['issues']))

    def test_cpt_never_inherits_icd_verification(self):
        self.row.update(system='cpt', code='12345', display='Synthetic CPT placeholder')
        proposal = self.adapt(terminology=DatedTerminology([release()]))['proposed_selections'][0]
        self.assertEqual('unavailable', proposal['terminology']['status'])
        self.assertIsNone(proposal['terminology']['description'])

    def test_duplicate_and_malformed_entries_quarantined(self):
        self.response['codes'].extend([deepcopy(self.row), None, {'system': 'cpt', 'code': 'G9903'}])
        result = self.adapt()
        self.assertEqual(1, len(result['proposed_selections']))
        self.assertEqual(3, len(result['diagnostics']['rejected_selected']))
        self.assertEqual(self.response, result['diagnostics']['provider_response'])

    def test_provider_cannot_inject_verification_or_approval(self):
        self.row.update(approved=True, selectable=True, terminology={'status': 'verified'},
                        clinical_applicability='approved')
        self.response['dashboard_activation_allowed'] = True
        result = self.adapt()
        p = result['proposed_selections'][0]
        self.assertFalse(p['approved'])
        self.assertFalse(p['selectable'])
        self.assertFalse(result['dashboard_activation_allowed'])
        self.assertEqual('unavailable', p['terminology']['status'])

    def test_invalid_service_date_rejected(self):
        with self.assertRaises(ValueError):
            adapt_response(self.response, self.request, service_date='2026-10-16')

    def test_local_catalogue_hash_and_completeness_fail_closed(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.txt'
            raw = b'R12 Synthetic description\n'
            path.write_bytes(raw)
            metadata = dict(system='icd10cm-outpatient', version='TEST', effective_from='2026-10-01',
                            effective_until='2027-09-30', source='https://ftp.cdc.gov/synthetic-fixture',
                            sha256='0' * 64, code_count=1, authorization_reference='TEST ONLY')
            with self.assertRaisesRegex(ValueError, 'hash'):
                load_icd_catalog(path, metadata)
            metadata['sha256'] = hashlib.sha256(raw).hexdigest()
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                load_icd_catalog(path, metadata)
            metadata['system'] = 'cpt'
            with self.assertRaisesRegex(ValueError, 'provenance'):
                load_icd_catalog(path, metadata)


class CortiPreviewTests(unittest.TestCase):
    setUp = CortiBoundaryTests.setUp
    adapt = CortiBoundaryTests.adapt
    @staticmethod
    def render(result, request):
        import importlib.util
        path = Path(__file__).resolve().parents[2] / 'ops' / 'corti_replay_preview.py'
        spec = importlib.util.spec_from_file_location('offline_corti_preview', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.render_preview(result, request)

    def test_malformed_diagnostics_survive_rendering(self):
        for malformed in [None, 1, True, {}, 'not-an-array']:
            with self.subTest(malformed=malformed):
                self.response['candidates'] = malformed
                self.row['alternatives'] = malformed
                result = self.adapt()
                html = self.render(result, self.request)
                self.assertIn('Synthetic replay', html)
                self.assertEqual(malformed, result['diagnostics']['candidates'])
                self.assertEqual(malformed, result['diagnostics']['alternatives'][0]['alternatives'])

    def test_preview_escapes_and_has_no_clinical_controls(self):
        from html.parser import HTMLParser
        self.row['display'] = '<img src=x onerror="alert(1)">'
        self.request['context'][0]['text'] += '<script>alert(1)</script>'
        html = self.render(self.adapt(), self.request)
        tags = []
        class Parser(HTMLParser):
            def handle_starttag(self, tag, attrs): tags.append(tag)
        Parser().feed(html)
        self.assertFalse(set(tags) & {'img', 'script', 'form', 'input', 'button', 'select', 'iframe'})
        self.assertIn('&lt;img', html)
        self.assertIn('Original response quality: FAIL', html)

    def test_preview_rejects_approval_activation(self):
        for key in ['approved', 'selectable']:
            result = self.adapt()
            result['proposed_selections'][0][key] = True
            with self.assertRaises(ValueError): self.render(result, self.request)
        result = self.adapt()
        result['dashboard_activation_allowed'] = True
        with self.assertRaises(ValueError): self.render(result, self.request)

    def test_candidate_only_identifiers_absent_from_main_table(self):
        html = self.render(self.adapt(), self.request)
        table = html.split('<tbody>', 1)[1].split('</tbody>', 1)[0]
        self.assertNotIn('K59.00', table)
        self.assertNotIn('K5900', table)


if __name__ == '__main__':
    unittest.main()
