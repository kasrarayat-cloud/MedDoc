"""Retained live Iris output and adversarial source-scope controls, all offline.

Changed-source controls below are constructed parser inputs, not provider calls
or substitutes for the retained response. The original v2 result stays held.
"""
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace as N
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import coding_engine as engine, corti_coding, corti_semantics, corti_prediction
from core.corti_response import CatalogRelease, DatedTerminology


FIXTURE = json.loads((Path(__file__).parent / 'fixtures/iris_coding_retained.json').read_text())
NOTES = FIXTURE['notes']
RAW = json.loads(FIXTURE['raw_response'])
SUMMARY = 'There are no additional findings beyond the heartburn described above.'


class ExceptionScopeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        value = deepcopy(FIXTURE['reference'])
        value['release'] = N(**value['release'])
        cls.reference = N(**value)
        release = cls.reference.release
        cls.terms = DatedTerminology([CatalogRelease('icd10cm-outpatient', release.version,
            date(2026, 10, 1), date(2027, 9, 30), release.source_url, release.sha256,
            cls.reference.tabular['codes'], release.source_url)])

    def run_value(self, notes=NOTES, contract=engine.CURRENT_SOURCE_CONTRACT):
        return N(inputs={'notes': notes, 'service_date': '2026-10-17',
            'engine_contract': corti_coding.CONTRACT,
            'patient_identity': {'display_name': 'Synthetic Iris Vale'}, 'patient_name_answers': []},
            context={'setting': 'outpatient_office'},
            config={'mode': 'live', 'provider': 'corti', 'clinical_source_contract': contract})

    def result(self, contract=engine.CURRENT_SOURCE_CONTRACT):
        current = self.run_value(contract=contract)
        with patch.object(corti_coding, 'terminology', return_value=(self.terms, {'available': False})), \
             patch.object(engine, 'reference_for', return_value=self.reference):
            current.result = corti_coding.retained_result(current, FIXTURE['request'], RAW,
                FIXTURE['provenance']['original_response_sha256'])
        return current

    def route(self, notes, quote, code='R12', selected=None):
        start = notes.index(quote)
        proposal = {'id': 'selected:0', 'code': code,
            'terminology': {'description': self.reference.tabular['codes'][code]},
            'evidence': [{'text': quote, 'start': start, 'end': start+len(quote),
                          'status': 'valid', 'context_index': 0}]}
        return corti_coding._icd_source(self.run_value(notes), self.reference, proposal, selected or [code])[1]

    def test_actual_retained_source_and_response_pass_only_prospective_route(self):
        self.assertEqual(hashlib.sha256(NOTES.encode()).hexdigest(), FIXTURE['provenance']['source_sha256'])
        self.assertEqual(hashlib.sha256(FIXTURE['raw_response'].encode()).hexdigest(),
                         FIXTURE['provenance']['original_response_sha256'])
        legacy = self.result(engine.SOURCE_CONTRACT)
        fresh = self.result()
        self.assertEqual([(r['code'], r['eligible']) for r in legacy.result['suggestions']],
                         [('R12', False), ('J30.2', False), ('99214', False)])
        self.assertEqual([(r['code'], r['eligible']) for r in fresh.result['suggestions']],
                         [('R12', True), ('J30.2', False), ('99214', False)])
        self.assertEqual(fresh.result['suggestions'][0]['index_path'], ['Heartburn'])
        self.assertEqual(fresh.result['adapter']['diagnostics']['provider_response'], RAW)
        self.assertEqual(fresh.result['diagnostics_summary'],
                         {'candidate_count': 11, 'alternative_count': 5, 'rejected_selected_count': 0})
        self.assertEqual(set(fresh.result['candidates']), {'selected:0'})
        self.assertEqual(fresh.result['suggestions'][2]['description'], '')

    def test_complete_exception_summaries_do_not_negate_independent_assertions(self):
        for symptom, code in [('heartburn', 'R12'), ('nausea', 'R11.0')]:
            quote = 'The patient has '+symptom+' today.'
            for summary in ('There are no additional findings beyond the '+symptom+' described above.',
                            'No other symptoms apart from '+symptom+'.',
                            'There are no other complaints except for the '+symptom+' already documented.',
                            'No additional findings other than '+symptom+' noted earlier.'):
                notes = 'Patient: Synthetic Iris Vale\nHistory of present illness\n'+quote+'\nReview of systems\n'+summary
                with self.subTest(symptom=symptom, summary=summary):
                    self.assertIsNotNone(self.route(notes, quote, code))

    def test_exception_summary_alone_cannot_establish_the_condition(self):
        for summary in (SUMMARY, 'No other symptoms except heartburn.'):
            notes = 'Patient: Synthetic Iris Vale\nReview of systems\n'+summary
            with self.subTest(summary=summary): self.assertIsNone(self.route(notes, summary))

    def test_true_denials_and_qualified_or_compound_summaries_remain_held(self):
        for summary in ('There are no findings of heartburn.',
                        'There is no evidence of heartburn.',
                        'No other symptoms except possible heartburn.',
                        'No other symptoms except heartburn, which is now denied.',
                        'No other symptoms except heartburn but it is not present.',
                        'It is false that there are no other symptoms except heartburn.',
                        'No additional findings beyond the heartburn described above are present.',
                        'No other symptoms except prior heartburn.'):
            notes = NOTES.replace(SUMMARY, summary)
            quote = 'Synthetic Iris Vale is being evaluated for heartburn present for three weeks.'
            with self.subTest(summary=summary): self.assertIsNone(self.route(notes, quote))

    def test_foreign_background_does_not_change_an_independent_patient_assertion(self):
        # These were already excluded from patient contradiction checks by v2.
        # They do not rely on the new complete exception-summary recognition.
        for summary in ("No other symptoms except the mother's heartburn.",
                        'No other symptoms except resolved heartburn.'):
            notes = NOTES.replace(SUMMARY, summary)
            quote = 'Synthetic Iris Vale is being evaluated for heartburn present for three weeks.'
            with self.subTest(summary=summary): self.assertIsNotNone(self.route(notes, quote))

    def test_current_source_and_other_assertions_cannot_be_replaced_by_exception(self):
        quote = 'The patient has heartburn today.'
        for heading in ('Mother:', 'Previous encounter:', 'Example:'):
            notes = 'Patient: Synthetic Iris Vale\n'+heading+'\n'+quote+'\nReview of systems\n'+SUMMARY
            with self.subTest(heading=heading): self.assertIsNone(self.route(notes, quote))
        for quote in ('Heartburn is a possibility only, not an established symptom.',
                      'The patient was evaluated for heartburn last year.',
                      'The patient denies heartburn.'):
            notes = 'Patient: Synthetic Iris Vale\nAssessment:\n'+quote+'\nReview of systems\n'+SUMMARY
            with self.subTest(quote=quote): self.assertIsNone(self.route(notes, quote))
        quote = 'Synthetic Iris Vale is being evaluated for heartburn present for three weeks.'
        for suffix in ('The patient denies heartburn.', 'Heartburn is not present.',
                       'Heartburn remains only a possibility.'):
            with self.subTest(suffix=suffix): self.assertIsNone(self.route(NOTES+'\r\n'+suffix, quote))

    def test_reference_instructions_are_unchanged(self):
        quote = 'Synthetic Iris Vale is being evaluated for heartburn present for three weeks.'
        self.assertIsNone(self.route(NOTES, quote, selected=['R12', 'K30']))

    def test_approval_and_export_reapply_scope_despite_saved_eligible_bit(self):
        current = self.result()
        selection = {'selected_ids': ['selected:0'], 'overrides': {}}
        def catalog(**kwargs):
            return N(first=lambda: N(description=self.reference.tabular['codes'][kwargs['code']]))
        with patch.object(corti_coding, 'terminology', return_value=(self.terms, {'available': False})), \
             patch.object(engine, 'reference_for', return_value=self.reference), \
             patch.object(engine.Code.objects, 'filter', side_effect=catalog):
            self.assertEqual(corti_coding.validate_selection(current, selection), selection)
            for key in ('selected:1', 'selected:2', 'candidate:0'):
                with self.subTest(key=key), self.assertRaises(ValidationError):
                    corti_coding.validate_selection(current, {'selected_ids': [key], 'overrides': {}})
            # Provider citations and the stored R12 eligibility bit stay intact;
            # the complete original-source recheck must still veto each denial.
            for suffix in ('The patient denies heartburn.', 'Heartburn is not present.',
                           'No other symptoms except heartburn, which is now denied.'):
                current.inputs['notes'] = NOTES+'\r\n'+suffix
                with self.subTest(suffix=suffix), self.assertRaises(ValidationError):
                    corti_coding.validate_selection(current, selection)
            current.inputs['notes'] = NOTES
            current.config['clinical_source_contract'] = engine.SOURCE_CONTRACT
            with self.assertRaises(ValidationError): corti_coding.validate_selection(current, selection)

    def test_v3_preserves_complete_cpt_facts_and_service_checks(self):
        old = corti_semantics.office_time_facts(NOTES, contract=engine.SOURCE_CONTRACT)
        new = corti_semantics.office_time_facts(NOTES, contract=engine.CURRENT_SOURCE_CONTRACT)
        self.assertEqual(old, new)
        self.assertEqual(new['status'], 'documented')
        self.assertEqual(len(new['facts']), 8)
        self.assertEqual(next(f['value'] for f in new['facts'] if f['key']=='time_minutes'), 32)
        self.assertEqual(corti_semantics.office_service_eligibility(NOTES, date(2026,10,17),
                         contract=engine.CURRENT_SOURCE_CONTRACT), [])
        self.assertTrue(corti_semantics.office_service_eligibility(
            NOTES+'\r\nOnly nursing staff saw the patient today; the physician did not participate.',
            date(2026,10,17), contract=engine.CURRENT_SOURCE_CONTRACT))

    def test_surviving_mentions_require_actual_presence_and_respect_corrections(self):
        positives = ['The patient reports heartburn today.',
                     'The patient also reports heartburn today.',
                     'The patient reports heartburn for three weeks.',
                     'The patient has heartburn according to the patient.',
                     'Heartburn is present as reported by the patient.',
                     'She experiences heartburn after meals.',
                     'Her current complaint is heartburn.',
                     'Heartburn has persisted for three weeks.',
                     'Impression\nHeartburn.',
                     'Assessment\nBoth heartburn and nausea were evaluated and discussed during this encounter.',
                     'The patient is being evaluated for heartburn present for three weeks.']
        negatives = ['The patient is worried about developing heartburn.',
                     'The patient asks whether she has heartburn.',
                     'Heartburn is a risk to discuss, not a current symptom.',
                     'The patient is screened for heartburn, without symptoms.',
                     'The patient has heartburn?',
                     'The patient has heartburn according to an unverified report.',
                     'The patient has heartburn according to a fabricated report.',
                     'The patient reports heartburn according to an unauthenticated letter.',
                     'Heartburn is present based on an unconfirmed account.',
                     'Her current complaint is heartburn as an assumed example.',
                     'The patient is being evaluated for heartburn.',
                     'Heartburn was not documented in error.']
        cases = [(quote, '', True) for quote in positives] + [(quote, '', False) for quote in negatives]
        for correction in ('Heartburn was documented in error.',
                           'Correction: the heartburn belongs to another patient.',
                           'The heartburn was entered erroneously.',
                           'The heartburn refers to the previous encounter.',
                           'Correction: heartburn was recorded in error after the chart was checked.',
                           'The reported heartburn actually concerned another patient.',
                           'Heartburn is incorrect.',
                           'Heartburn was not documented in error but is not present.',
                           'Heartburn was not documented in error but the patient is no longer experiencing it.',
                           'Heartburn was not documented in error but the patient has none today.',
                           'Heartburn is not wrong but the symptom is no longer present.',
                           'Heartburn is not wrong but this complaint is resolved.',
                           'Heartburn is not wrong but her condition was recorded in error.',
                           'Heartburn is not wrong but nausea is wrong and the patient has none today.',
                           'The patient has heartburn according to an unverified report.',
                           'Heartburn is present based on an unconfirmed account.'):
            cases.append((positives[0], correction, False))
        cases.extend((positives[0], integrity, True) for integrity in
                     ('Heartburn was not documented in error.', 'Heartburn is not incorrect.',
                      'Nausea was recorded in error after the chart was checked.',
                      'Heartburn is not wrong but nausea is wrong.',
                      'Mother:\nHeartburn was documented in error.',
                      'Previous encounter:\nHeartburn was documented in error.'))
        for quote, suffix, expected in cases:
            notes = 'Patient: Synthetic Iris Vale\nHistory of present illness\n'+quote+'\nReview of systems\n'+SUMMARY
            if suffix: notes += '\n'+suffix
            current = self.run_value(notes)
            start = notes.index(quote)
            raw = {'codes': [{'system': 'icd10cm-outpatient', 'code': 'R12', 'display': 'Heartburn',
                'evidences': [{'contextIndex': 0, 'start': start, 'end': start+len(quote), 'text': quote}],
                'alternatives': []}], 'candidates': []}
            with self.subTest(quote=quote, suffix=suffix), \
                 patch.object(corti_coding, 'terminology', return_value=(self.terms, {'available': False})), \
                 patch.object(engine, 'reference_for', return_value=self.reference), \
                 patch.object(engine.Code.objects, 'filter', side_effect=lambda **kw:
                     N(first=lambda: N(description=self.reference.tabular['codes'][kw['code']]))):
                current.result = corti_coding.retained_result(current, corti_prediction.payload(current), raw,
                    hashlib.sha256(json.dumps(raw).encode()).hexdigest())
                self.assertEqual(current.result['suggestions'][0]['eligible'], expected)
                selection = {'selected_ids': ['selected:0'], 'overrides': {}}
                if expected:
                    self.assertEqual(corti_coding.validate_selection(current, selection), selection)
                else:
                    with self.assertRaises(ValidationError): corti_coding.validate_selection(current, selection)
