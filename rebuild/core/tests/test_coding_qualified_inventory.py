"""Prospective whole SOAP inventory, without inference or database access."""
from copy import deepcopy
from types import SimpleNamespace as N
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import coding_completeness as c, coding_engine as e, coding_reference_store as store


class QualifiedInventoryTests(SimpleTestCase):
    contract = e.QUALIFIED_SOURCE_CONTRACT
    allergy = 'She reports an allergy to penicillin, which caused hives.'
    assessment = 'Heartburn and constipation were both separately assessed today.'
    uncertainty = ('The cause of the heartburn is not established; '
                   'reflux disease is a possibility but is not diagnosed.')
    note = ('Patient: Synthetic Uma Bell\nService date: 21 October 2027\nS\n'
            'She reports heartburn today.\nShe reports constipation today.\n'
            + allergy + '\nA\n' + assessment + '\n' + uncertainty + '\n'
            'Constipation is documented without an established subtype or cause.\n'
            'Slow-transit constipation and drug-induced constipation are not diagnosed today.\n'
            'P\nFollow-up is planned in three weeks.')

    def inventory(self, note=None):
        return c.inventory(self.note if note is None else note, source_contract=self.contract)

    def test_all_source_objects_and_typed_noncoding_review_remain_visible(self):
        result = self.inventory()
        self.assertEqual(result['blockers'], [])
        self.assertEqual([r['condition_text'] for r in result['items']], ['heartburn','constipation'])
        self.assertTrue(all(r['current_evaluation_evidence'] for r in result['items']))
        self.assertEqual(len(result['unresolved']), 1)
        row = result['unresolved'][0]
        self.assertEqual(row['condition_text'], self.uncertainty)
        self.assertEqual(row['state'], 'review_required')
        self.assertEqual(row['source_assertion_kind'], 'explicit_unestablished_cause')
        self.assertEqual(row['candidates'], [])
        self.assertIn(self.allergy, [r['evidence']['quote'] for r in result['excluded']])
        self.assertEqual(result['service_date'], '2027-10-21')
        for row in result['items'] + result['unresolved']:
            for span in row['evidence']:
                self.assertEqual(self.note[span['start']:span['end']], span['quote'])

    def test_old_profiles_keep_identical_inventory_bytes_and_no_new_contract_field(self):
        before = c.inventory(self.note)
        for contract in (e.CURRENT_SOURCE_CONTRACT, e.PROSPECTIVE_SOURCE_CONTRACT, e.SOAP_SOURCE_CONTRACT):
            self.assertEqual(c.inventory(self.note, source_contract=contract), before)
        self.assertNotIn('source_contract', before)
        self.assertEqual(self.inventory()['source_contract'], self.contract)
        self.assertNotEqual(self.inventory()['inventory_sha256'], before['inventory_sha256'])

    def test_only_complete_assessment_predicates_establish_evaluation(self):
        for changed in ('Heartburn and constipation were both separately assessed today for her mother.',
                        'Heartburn and constipation were both separately assessed yesterday.',
                        'Heartburn and constipation were both separately assessed today but this is uncertain.',
                        'Heartburn and constipation were both separately assessed today and withdrawn.'):
            with self.subTest(changed=changed):
                result = self.inventory(self.note.replace(self.assessment, changed))
                self.assertFalse(all(r['current_evaluation_evidence'] for r in result['items']))

    def test_unknown_uncertainty_suffixes_are_not_converted_to_noncoding_reviews(self):
        for changed in (self.uncertainty[:-1]+' except as noted elsewhere.',
                        self.uncertainty[:-1]+' for her mother.',
                        self.uncertainty.replace('not diagnosed', 'diagnosed'),
                        self.uncertainty.replace('is a possibility but is not diagnosed', 'may be present'),
                        self.uncertainty+' The heartburn statement is withdrawn.'):
            with self.subTest(changed=changed):
                result = self.inventory(self.note.replace(self.uncertainty, changed))
                if changed.startswith(self.uncertainty):
                    self.assertTrue(any('withdrawn' in r['condition_text'] for r in result['unresolved']))
                else:
                    self.assertTrue(any(r['state']=='unresolved' for r in result['unresolved']))

    def test_allergy_unknown_tail_and_current_evaluation_are_not_erased(self):
        for replacement in (self.allergy[:-1]+' and she has wheezing now.',
                            self.allergy[:-1]+' according to an unverified account.',
                            self.allergy.replace('which caused', 'which may have caused')):
            with self.subTest(replacement=replacement):
                result = self.inventory(self.note.replace(self.allergy,replacement))
                self.assertTrue(any(replacement==r['condition_text'] for r in result['unresolved']))
        result = self.inventory(self.note.replace(self.assessment,self.assessment+' Allergy was assessed today.'))
        self.assertTrue(any(self.allergy==r['condition_text'] for r in result['unresolved']))
        result = self.inventory(self.note.replace(self.assessment,self.assessment+' Hives were assessed today.'))
        self.assertTrue(any(self.allergy==r['condition_text'] for r in result['unresolved']))

    def test_separate_concern_is_bound_to_two_independently_evaluated_literals(self):
        text = 'The constipation is a separate concern from the heartburn.'
        note = self.note.replace(self.allergy,text+'\n'+self.allergy)
        inv = self.inventory(note)
        self.assertTrue(all(text in [s['quote']for s in row['evidence']] for row in inv['items']))
        for changed in (text[:-1]+' for her mother.', text.replace('heartburn','constipation'),
                        text.replace('heartburn','nausea'), text[:-1]+' but that is uncertain.'):
            with self.subTest(changed=changed):
                self.assertIsNone(c._separate_condition_reference(changed, {'heartburn','constipation'}))
        self.assertIsNone(c._separate_condition_reference(text, {'constipation'}))

    def test_soap_headings_do_not_reset_foreign_or_prior_scope(self):
        for frame in ('Mother:', 'Prior encounter on 20 October 2027:',
                      'Prior encounter on 20 October 2027 for her mother:'):
            with self.subTest(frame=frame):
                note = self.note.replace('S\n',frame+'\nS\n')
                result = self.inventory(note)
                self.assertFalse(any(r['current_evaluation_evidence'] for r in result['items']))

    def test_v7_loader_refuses_wrong_inventory_contract_before_reading(self):
        current = self.inventory()
        historical = c.inventory(self.note)
        for contract, inventory in ((self.contract,historical), (e.SOAP_SOURCE_CONTRACT,current)):
            with self.subTest(contract=contract), patch.object(store,'_Projection',side_effect=AssertionError('Query must not start')):
                with self.assertRaisesMessage(ValidationError,'inventory and reference contract differ'):
                    store.prediction_reference(N(), ['R12'], source_contract=contract, source_inventory=inventory)

    def test_recognized_noncoding_row_still_requires_explicit_review(self):
        from core.coding_source_review import presentation, validated_choices
        inv = self.inventory()
        row = inv['unresolved'][0]
        review = {'evaluation':{'inventory':[row],'suggestions':[],'blockers':[], 'coverage':{}}}
        self.assertFalse(presentation(review)['complete'])
        choices = {row['id']:{'action':'no_code','suggestion_id':'',
            'reason':'The complete source explicitly leaves the cause and possible diagnosis unestablished.'}}
        self.assertEqual(validated_choices(review,deepcopy(choices)),choices)
        self.assertTrue(presentation(review,N(choices=choices))['complete'])
        self.assertFalse(presentation(review,N(choices=choices))['all_coded'])

    def test_unconsumed_whole_condition_references_cannot_disappear_before_assessment(self):
        for relation in ('Apparently constipation is a separate concern from heartburn.',
                         'Reportedly constipation is a separate concern from heartburn.',
                         'Apparently, the constipation is a separate concern from heartburn.',
                         'Constipation is reportedly a separate concern from heartburn.',
                         'Constipation is a separate concern from heartburn under an unresolved account.',
                         'Constipation is a separate concern from heartburn?',
                         'Constipation has an unfamiliar relationship with heartburn.'):
            with self.subTest(relation=relation):
                note = self.note.replace(self.allergy, relation+'\n'+self.allergy)
                result = self.inventory(note)
                gaps = [r for r in result['unresolved'] if r['condition_text']==relation]
                self.assertEqual(len(gaps), 1)
                self.assertEqual(gaps[0]['state'], 'unresolved')
                span = gaps[0]['evidence'][0]
                self.assertEqual(note[span['start']:span['end']], relation)

    def test_unresolved_relation_blocks_coverage_even_with_both_codes_approved(self):
        from core.tests.test_coding_qualified_assertions import QualifiedAssertionTests
        from core.tests.test_coding_completeness import bind
        reference_case = QualifiedAssertionTests(); reference_case.setUp()
        reference = reference_case.reference
        reference.release = N(version='SYNTHETIC-UNIT', system='ICD-10-CM', effective_from='2027-01-01',
            effective_until='2027-12-31', source_url='https://www.cms.gov/synthetic-unit-only', sha256='b'*64)
        release = dict(id=reference.release_id, sha256=reference.release.sha256, version=reference.release.version,
            effective_from=reference.release.effective_from, effective_until=reference.release.effective_until)
        for relation, complete in (('Constipation is a separate concern from heartburn.', True),
                                   ('Apparently constipation is a separate concern from heartburn.', False),
                                   ('Reportedly constipation is a separate concern from heartburn.', False)):
            with self.subTest(relation=relation):
                note = ('Patient: Synthetic Uma Bell\nS\nShe reports heartburn today.\n'
                    'She reports constipation today.\n'+relation+'\nA\n'+self.assessment)
                inv = self.inventory(note)
                run = N(inputs={'notes':note,'service_date':'2027-10-21'},
                    config={'clinical_source_contract':self.contract}, releases=[release])
                evaluation = c.evaluate(run,bind(deepcopy(reference),inv),approved_codes=['R12','K59.00'])
                self.assertEqual(evaluation['coverage']['complete'],complete)
                if not complete:
                    self.assertGreater(evaluation['coverage']['unresolved'],0)
                    self.assertFalse(any(row['eligible'] for row in evaluation['suggestions']))
