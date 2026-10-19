"""Whole patient orders retain their indication without asserting its disease."""
from copy import deepcopy
from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core.clinical_assertions_v4 import family_history_order_frame
from core.tests import test_soap_destination_integration as integration
from core.tests.test_semantic_generation import fact


class FamilyHistoryOrderTests(SimpleTestCase):
    header = integration.SoapDestinationIntegrationTests.header
    run_assignment = integration.SoapDestinationIntegrationTests.run_assignment
    order = 'I ordered a blood test for family history of thyroid disease, with collection planned tomorrow'
    status = 'No blood sample was collected today, the test was not performed today and no result is available'
    meaning = ('Investigation ordered, its evaluation purpose, intended collection timing, and the actual '
        'collection, performance and result status today. Retain documented not-yet-done or not-resulted status.')

    def assess(self, order=None, *, section='P', selected=None, order_value=None,
               kind='plan', polarity='affirmed', timing='current', suffix='', profile=None):
        order = self.order if order is None else order
        return self.run_assignment(section+'\n'+order+'. '+self.status+'.'+suffix,
            {'order': (order_value or order, kind, polarity, timing),
             'status': (self.status, 'finding', 'negated', 'current')},
            {'investigation': (self.meaning, 'patient', 'current', 'any')},
            {'investigation': ['order', 'status'] if selected is None else selected}, profile=profile)

    def test_complete_order_and_status_are_supported_with_exact_source_text(self):
        result, facts = self.assess()
        self.assertEqual(result['investigation']['status'], 'supported', result)
        self.assertEqual(facts['order']['issues'], [])
        self.assertEqual(facts['status']['issues'], [])
        self.assertEqual(result['investigation']['text'], self.order+'; '+self.status)

    def test_general_test_and_indication_nouns_and_active_passive_forms(self):
        for order in (
            self.order.replace('blood test', 'urine culture').replace('thyroid disease', 'renal disease'),
            self.order.replace('I ordered a blood test', 'A serum assay is ordered'),
            self.order.replace('I ordered', 'I have ordered').replace('tomorrow', 'after this visit'),
        ):
            with self.subTest(order=order):
                result, _ = self.assess(order)
                self.assertEqual(result['investigation']['status'], 'supported', result)

    def test_frame_exposes_only_whole_value_and_exact_component_spans(self):
        source = '  '+self.order+'.\r\n'
        frame = family_history_order_frame(source)
        self.assertEqual([source[a:b] for a,b in frame['values']], [self.order])
        for key, expected in [('test','a blood test'), ('relationship','family history'),
                              ('indication','thyroid disease'), ('collection','collection planned tomorrow')]:
            a,b = frame[key]
            self.assertEqual(source[a:b], expected)
        self.assertEqual(frame['required_timing'], 'current')
        self.assertEqual(frame['required_section'], 'plan')

    def test_clipped_order_disease_and_collection_cannot_be_asserted_as_findings(self):
        for quote in ('blood test', 'family history of thyroid disease', 'thyroid disease',
                      'collection planned tomorrow', self.order.split(',')[0]):
            for kind in ('plan', 'finding', 'assessment', 'history'):
                with self.subTest(quote=quote, kind=kind):
                    result, facts = self.assess(order_value=quote, kind=kind)
                    self.assertTrue(facts['order']['issues'])
                    self.assertNotEqual(result['investigation']['status'], 'supported')

    def test_whole_order_requires_exact_kind_polarity_and_timing(self):
        for changes in ({'kind':'finding'}, {'kind':'assessment'}, {'kind':'history'},
                        {'polarity':'negated'}, {'polarity':'uncertain'}, {'polarity':'mixed'},
                        {'timing':'past'}, {'timing':'future'}, {'timing':'unspecified'}):
            with self.subTest(changes=changes):
                result, facts = self.assess(**changes)
                self.assertTrue(facts['order']['issues'])
                self.assertNotEqual(result['investigation']['status'], 'supported')

    def test_unknown_qualifiers_retractions_and_retrospective_orders_remain_held(self):
        variants = [self.order+suffix for suffix in (
            ' but this is unverified', ' unless symptoms recur', ' and is withdrawn',
            ' for another patient', ' according to her mother', ' and a diagnosis is confirmed',
            ' with an unfamiliar qualification')]
        variants += [prefix+self.order for prefix in ('Yesterday, ', 'Reportedly, ', 'If true, ', '"')]
        variants += [self.order.replace('thyroid disease', value) for value in (
            'possible thyroid disease', 'prior thyroid disease', 'unknown thyroid disease',
            'her thyroid disease', 'thyroid disease or fever', 'thyroid disease for her mother',
            'thyroid disease with an unfamiliar qualification')]
        variants += [self.order.replace('I ordered', 'I previously ordered'),
            self.order.replace('I ordered a blood test', 'A blood test was ordered')]
        for order in variants:
            with self.subTest(order=order):
                self.assertIsNone(family_history_order_frame(order))
                result, facts = self.assess(order)
                self.assertTrue(facts['order']['issues'])
                self.assertNotEqual(result['investigation']['status'], 'supported')

    def test_foreign_beneficiary_cannot_become_patient_order(self):
        for beneficiary in ('her mother', 'his father', 'their sister', 'another patient',
                            "the patient's cousin", 'her family member'):
            order = self.order.replace('for family history', 'for '+beneficiary+' for family history')
            with self.subTest(beneficiary=beneficiary):
                self.assertIsNone(family_history_order_frame(order))
                result, facts = self.assess(order)
                self.assertTrue(any('beneficiary' in reason for reason in facts['order']['issues']))
                self.assertNotEqual(result['investigation']['status'], 'supported')

    def test_source_owner_section_and_later_retraction_still_gate_order(self):
        for section in ('Mother\nP', 'Previous visit\nP', 'A', 'S', 'O'):
            with self.subTest(section=section):
                result, facts = self.assess(section=section)
                self.assertTrue(facts['order']['issues'])
                self.assertNotEqual(result['investigation']['status'], 'supported')
        for suffix in ("\nThe above note is not this patient's record.",
                       '\nThe preceding clinical account is incorrect.'):
            result, facts = self.assess(suffix=suffix)
            self.assertTrue(facts['order']['issues'])
            self.assertTrue(facts['status']['issues'])

    def test_order_or_status_omission_cannot_pass_complete_investigation(self):
        for selected in (['order'], ['status'], []):
            result, facts = self.assess(selected=selected)
            self.assertEqual(facts['order']['issues'], [])
            self.assertEqual(facts['status']['issues'], [])
            self.assertNotEqual(result['investigation']['status'], 'supported')
            self.assertTrue(any('omits documented encounter support' in reason
                for reason in result['investigation']['review_reasons']))

    def test_unselected_complete_order_does_not_hold_unrelated_fact(self):
        notes = self.header+'S\nHe reports mild wrist pain.\nP\n'+self.order+'.'
        units, _ = generation.source_units(notes, [])
        raw = {'facts':[fact(notes, [], 'pain', 'He reports mild wrist pain')]}
        before = deepcopy(raw)
        current = semantic.validate_facts(notes, units, raw, scope_contract=semantic.SOAP_ASSERTION_SCOPE_CONTRACT)
        old = semantic.validate_facts(notes, units, raw, scope_contract=semantic.COMPLETE_ASSERTION_SCOPE_CONTRACT)
        self.assertEqual(raw, before)
        self.assertEqual(current['pain']['issues'], [])
        self.assertTrue(old['pain']['issues'])
        self.assertIsNone(semantic._governance_literal(self.order, semantic.COMPLETE_ASSERTION_SCOPE_CONTRACT))

    def test_historical_v20_keeps_original_order_and_whole_note_holds(self):
        result, facts = self.assess(profile=semantic.COMPLETE_ASSERTION_SCOPE_CONTRACT)
        self.assertTrue(any('explicit past time' in reason for reason in facts['order']['issues']))
        self.assertTrue(any('Governing source context' in reason for reason in facts['status']['issues']))
        self.assertNotEqual(result['investigation']['status'], 'supported')

    def test_dated_other_encounter_headings_persist_through_soap_plan(self):
        from core.clinical_source_context import source_context, SOAP_ASSERTION_PROFILE
        for heading, expected in (
                ('Prior encounter on 20 October 2027', 'past'),
                ('Previous office visit on October 20, 2027:', 'past'),
                ('Earlier clinical consultation dated 2027-10-20', 'past'),
                ('Future encounter on 22 October 2027', 'future'),
                ('Next visit dated 2027-10-22', 'future')):
            with self.subTest(heading=heading):
                result, facts = self.assess(section=heading+'\nP')
                self.assertNotEqual(result['investigation']['status'], 'supported')
                self.assertTrue(facts['order']['issues'])
                self.assertTrue(facts['status']['issues'])
                notes = self.header+heading+'\nP\n'+self.order+'.'
                context = source_context(notes, profile=SOAP_ASSERTION_PROFILE)
                self.assertEqual(context['units'][notes.index(self.order)]['section_timing'], expected)

    def test_invalid_dates_and_unknown_heading_tails_remain_unresolved(self):
        from core.clinical_source_context import source_context, SOAP_ASSERTION_PROFILE
        for heading in (
                'Prior encounter on',
                'Prior encounter on 31 February 2027',
                'Previous visit dated 2027-13-20',
                'Earlier encounter on 20 October 2027 pending confirmation',
                'Prior encounter on 20 October 2027 but current today',
                'Future encounter on 22 October 2027 unless cancelled'):
            with self.subTest(heading=heading):
                result, facts = self.assess(section=heading+'\nP')
                self.assertNotEqual(result['investigation']['status'], 'supported')
                for value in facts.values():
                    self.assertTrue(any('Governing source context' in reason for reason in value['issues']))
                notes = self.header+heading+'\nP\n'+self.order+'.'
                row = source_context(notes, profile=SOAP_ASSERTION_PROFILE)['units'][notes.index(self.order)]
                self.assertTrue(any('dated encounter heading' in reason for reason in row['issues']))

    def test_explicit_current_heading_restores_time_but_not_foreign_owner(self):
        for previous in ('Prior encounter on 20 October 2027',
                         'Prior encounter on 31 February 2027',
                         'Future encounter on 22 October 2027'):
            with self.subTest(previous=previous):
                section = previous+'\nP\nCurrent encounter\nP'
                result, facts = self.assess(section=section)
                self.assertEqual(result['investigation']['status'], 'supported', result)
                self.assertEqual(facts['order']['issues'], [])
                result, facts = self.assess(section='Mother\n'+section)
                self.assertNotEqual(result['investigation']['status'], 'supported')
                self.assertTrue(facts['order']['issues'])

    def test_malformed_heading_does_not_hide_current_account_retraction(self):
        for heading in ('Prior encounter on 31 February 2027',
                        'Prior encounter on 20 October 2027 but this is not a historical account'):
            result, facts = self.assess(suffix='\n'+heading+'\nThe above clinical account is retracted.')
            self.assertNotEqual(result['investigation']['status'], 'supported')
            for value in facts.values():
                self.assertTrue(any('retracts' in reason for reason in value['issues']))

    def test_unknown_dated_header_scope_survives_time_only_reset(self):
        from core.clinical_source_context import source_context, SOAP_ASSERTION_PROFILE
        for tail in ('for her mother', 'with an unfamiliar qualification',
                     'pending confirmation', 'but current today'):
            heading = 'Prior encounter on 20 October 2027 '+tail
            for reset in ('Current encounter', 'Present visit', "Today's consultation"):
                with self.subTest(tail=tail, reset=reset):
                    section = heading+'\n'+reset+'\nP'
                    result, facts = self.assess(section=section)
                    self.assertNotEqual(result['investigation']['status'], 'supported')
                    for value in facts.values():
                        self.assertTrue(any('Governing source context' in reason for reason in value['issues']))
                    notes = self.header+section+'\n'+self.order+'.'
                    row = source_context(notes, profile=SOAP_ASSERTION_PROFILE)['units'][notes.index(self.order)]
                    self.assertEqual(row['section_timing'], 'current')
                    self.assertTrue(any('source scope' in reason for reason in row['issues']))

    def test_unknown_header_scope_requires_explicit_current_patient_identity(self):
        for tail in ('for her mother', 'with an unfamiliar qualification', 'pending confirmation'):
            heading = 'Prior encounter on 20 October 2027 '+tail
            for reset in ('Current patient: Synthetic Ada Tern',
                          "Today's patient full name: Synthetic Ada Tern"):
                with self.subTest(tail=tail, reset=reset):
                    result, facts = self.assess(section=heading+'\n'+reset+'\nP')
                    self.assertEqual(result['investigation']['status'], 'supported', result)
                    self.assertEqual(facts['order']['issues'], [])
                    self.assertEqual(facts['status']['issues'], [])
            for reset in ('Patient: Synthetic Ada Tern', 'Current encounter\nPatient: Synthetic Ada Tern'):
                result, facts = self.assess(section=heading+'\n'+reset+'\nP')
                self.assertNotEqual(result['investigation']['status'], 'supported')

    def test_scope_reset_does_not_erase_prior_current_account_retraction(self):
        suffix = ('\nPrior encounter on 20 October 2027 with an unfamiliar qualification'
            '\nThe above clinical account is retracted.'
            '\nCurrent patient: Synthetic Ada Tern\nP')
        result, facts = self.assess(suffix=suffix)
        self.assertNotEqual(result['investigation']['status'], 'supported')
        for value in facts.values():
            self.assertTrue(any('retracts' in reason for reason in value['issues']))

    def test_dated_heading_change_is_only_in_soap_profile(self):
        from core.clinical_source_context import (source_context, SOURCE_GOVERNANCE_PROFILE,
            COMPLETE_ASSERTION_PROFILE, SOAP_ASSERTION_PROFILE)
        for heading in ('Prior encounter on 20 October 2027', 'Prior encounter on 31 February 2027',
                        'Prior encounter on 20 October 2027 for her mother\nCurrent encounter',
                        'Prior encounter on 20 October 2027 with an unfamiliar qualification\nCurrent encounter'):
            notes = self.header+heading+'\nP\n'+self.order+'.'
            start = notes.index(self.order)
            for profile in (None, SOURCE_GOVERNANCE_PROFILE, COMPLETE_ASSERTION_PROFILE):
                with self.subTest(profile=profile, heading=heading):
                    row = source_context(notes, profile=profile)['units'][start]
                    self.assertEqual(row['section_timing'], 'current')
                    self.assertEqual(row['issues'], [])
            row = source_context(notes, profile=SOAP_ASSERTION_PROFILE)['units'][start]
            self.assertTrue(row['section_timing'] != 'current' or row['issues'])
