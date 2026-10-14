"""Invented licensed-rule fixtures test criteria; no real CPT descriptors/ranges."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.core.exceptions import ValidationError

from core import coding_cpt as cpt
from core.tests.test_coding_licensing import synthetic_rules


class LicensedCriteriaTests(SimpleTestCase):
    def setUp(self):
        release = {'version': 'SYNTHETIC', 'effective_from': '2026-01-01', 'effective_until': '2026-12-31',
                   'source_url': 'https://example.invalid/synthetic', 'sha256': 'a' * 64, 'code_count': 2}
        rules = synthetic_rules(release)
        cpt.validate_rules(rules, release)
        self.reference = SimpleNamespace(tabular=rules['tabular'], index=rules['index'], release_id='synthetic-release',
                                         release=SimpleNamespace(version='SYNTHETIC'))
        self.run = SimpleNamespace(inputs={'notes': 'Synthetic procedure performed on left side today.\n'
            'Documented problem evidence.\nDocumented risk evidence.\nTotal practitioner time 45 minutes.', 'answers': {}}, context={})
        quote = self.run.inputs['notes'].split('\n')[0]
        self.evidence = {'source': {'start': 0, 'end': len(quote), 'quote': quote},
                         'assertion': 'affirmed', 'subject': 'patient', 'timing': 'current',
                         'procedure_status': 'performed', 'details': {'side': {'start': 0, 'end': len(quote), 'quote': quote}}}

    def test_current_performed_patient_procedure_requires_supplied_detail(self):
        self.assertTrue(cpt._validate(self.run, '00000', self.evidence, self.reference)['valid'])
        for key, value in [('subject', 'family'), ('assertion', 'negated'), ('timing', 'historical'),
                           ('procedure_status', 'planned'), ('details', {})]:
            with self.subTest(key=key):
                self.assertFalse(cpt._validate(self.run, '00000', {**self.evidence, key: value}, self.reference)['valid'])

    def test_plan_or_history_qualifier_outside_model_quote_is_still_refused(self):
        for prefix in ('Planned: ', 'History of ', 'Not ', 'Scheduled:\n'):
            with self.subTest(prefix=prefix):
                old = self.run.inputs['notes']
                self.run.inputs['notes'] = prefix + old
                evidence = deepcopy(self.evidence)
                for span in (evidence['source'], evidence['details']['side']):
                    span['start'] += len(prefix)
                    span['end'] += len(prefix)
                self.assertFalse(cpt._validate(self.run, '00000', evidence, self.reference)['valid'])
                self.run.inputs['notes'] = old

    def office(self, basis):
        self.run.context = {'setting': 'outpatient_office', 'patient_status': 'established', 'em_basis': basis,
            'mdm_problems': 'moderate', 'mdm_problems_evidence': 'Documented problem evidence.',
            'mdm_data': 'unknown', 'mdm_data_evidence': '',
            'mdm_risk': 'moderate', 'mdm_risk_evidence': 'Documented risk evidence.',
            'time_minutes': '45', 'time_evidence': 'Total practitioner time 45 minutes.',
            'time_qualified_clinician': True, 'time_same_day': True, 'time_excludes_separately_reported': True}

    def test_office_mdm_requires_two_documented_elements_and_patient_status(self):
        self.office('mdm')
        self.assertTrue(cpt._validate(self.run, '00001', {}, self.reference)['valid'])
        for key, value in [('mdm_risk', 'low'), ('mdm_risk_evidence', 'invented evidence'),
                           ('setting', 'unknown'), ('patient_status', 'new')]:
            with self.subTest(key=key):
                previous = self.run.context[key]
                self.run.context[key] = value
                self.assertFalse(cpt._validate(self.run, '00001', {}, self.reference)['valid'])
                self.run.context[key] = previous

    def test_time_uses_one_qualifying_total_not_direct_plus_total(self):
        self.office('time')
        self.assertTrue(cpt._validate(self.run, '00001', {}, self.reference)['valid'])
        for key, value in [('time_minutes', '60'), ('time_same_day', False), ('time_qualified_clinician', False),
                           ('time_excludes_separately_reported', False)]:
            with self.subTest(key=key):
                previous = self.run.context[key]
                self.run.context[key] = value
                self.assertFalse(cpt._validate(self.run, '00001', {}, self.reference)['valid'])
                self.run.context[key] = previous
        quote = 'Total practitioner time 45 minutes, including direct time 15 minutes.'
        self.run.inputs['notes'] += '\n' + quote
        self.run.context['time_evidence'] = quote
        self.assertFalse(cpt._validate(self.run, '00001', {}, self.reference)['valid'])

    def test_missing_entitlement_never_returns_candidates_or_accepts_manual_code(self):
        with patch.object(cpt, '_reference', return_value=(None, 'Licensed criteria missing.')):
            self.assertEqual(cpt.procedure_candidates(self.run, [self.evidence]), [])
            self.assertFalse(cpt.validate_cpt_selection(self.run, '00000', self.evidence['source']['quote'])['valid'])

    def test_engine_concept_and_office_context_have_separate_candidate_paths(self):
        from core.models import Code
        quote = self.evidence['source']['quote']
        concept = {'id': 'c1', 'kind': 'procedure', 'certainty': 'confirmed', 'temporality': 'current',
                   'subject': 'patient', 'relevant': True, 'evidence': quote}
        def catalog(**kwargs):
            code = kwargs['code']
            return SimpleNamespace(first=lambda: SimpleNamespace(code=code, description=self.reference.tabular['codes'][code]['description']))
        with patch.object(cpt, '_reference', return_value=(self.reference, '')), patch.object(Code.objects, 'filter', side_effect=catalog):
            candidates = cpt.procedure_candidates(self.run, [concept])
            self.assertEqual([row['code'] for row in candidates], ['00000'])
            self.assertEqual(set(candidates[0]), {'entry_id', 'code', 'system', 'description', 'path', 'instructions', 'requires_review', 'release_id', 'release_version'})
            self.assertTrue(cpt.validate_cpt_selection(self.run, '00000', quote)['valid'])
            self.assertFalse(cpt.validate_cpt_selection(self.run, '00000', self.evidence)['valid'])
            self.assertEqual(cpt.procedure_candidates(self.run, [{**concept, 'temporality': 'planned'}]), [])
            self.office('time')
            self.assertEqual([row['code'] for row in cpt.procedure_candidates(self.run, [])], ['00001'])
            self.assertEqual([row['code'] for row in cpt.procedure_candidates(self.run, [concept])], ['00000'])

    def test_mdm_and_time_reject_irrelevant_negated_or_historical_evidence(self):
        self.office('mdm')
        self.run.context['mdm_risk_evidence'] = self.evidence['source']['quote']
        self.assertFalse(cpt._validate(self.run, '00001', {}, self.reference)['valid'])
        self.office('time')
        self.run.inputs['notes'] = self.run.inputs['notes'].replace('Total practitioner time', 'Yesterday: Total practitioner time')
        self.assertFalse(cpt._validate(self.run, '00001', {}, self.reference)['valid'])

    def test_three_high_labels_with_patient_feels_well_never_establish_mdm(self):
        self.office('mdm')
        self.run.inputs['notes'] += '\nPatient feels well.'
        for element in ('problems', 'data', 'risk'):
            self.run.context['mdm_' + element] = 'high'
            self.run.context['mdm_' + element + '_evidence'] = 'Patient feels well.'
        self.assertFalse(cpt._validate(self.run, '00001', {}, self.reference)['valid'])

    def test_no_hardcoded_code_or_threshold_fallback(self):
        self.office('time')
        self.reference.tabular['codes']['00001']['requirements']['time']['minimum'] = 46
        self.assertFalse(cpt._validate(self.run, '00001', {}, self.reference)['valid'])
        self.assertFalse(cpt._validate(self.run, '99999', {}, self.reference)['valid'])
