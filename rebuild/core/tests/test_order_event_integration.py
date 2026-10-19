"""Current order placement and future performance retain distinct source roles."""
from django.test import SimpleTestCase

from core import semantic_generation as semantic
from core.tests import test_soap_destination_integration as integration


class OrderEventIntegrationTests(SimpleTestCase):
    header = integration.SoapDestinationIntegrationTests.header
    run_assignment = integration.SoapDestinationIntegrationTests.run_assignment
    order = ('A thyroid-stimulating hormone blood test is ordered for collection at a laboratory '
             'after this visit as part of the constipation evaluation')
    status = 'No blood sample was collected today, the test was not performed today and no result is available'
    meaning = ('Narrative of the investigation ordered: the evaluation purpose, intended collection timing, '
               'and the actual status today of collection, performance and result. Keep intended and actual '
               'status distinct; do not state a result unless documented.')

    def assess(self, *, order=None, timing='future', scope='any', selected=None,
               order_value=None, kind='plan', polarity='affirmed', section='P', suffix='', profile=None):
        source = self.order if order is None else order
        return self.run_assignment(section+'\n'+source+'. '+self.status+'.'+suffix,
            {'order': (order_value or source, kind, polarity, timing),
             'status': (self.status, 'finding', 'negated', 'current')},
            {'investigation': (self.meaning, 'patient', scope, 'any')},
            {'investigation': ['order', 'status'] if selected is None else selected},
            profile=profile or semantic.ORDER_EVENT_SCOPE_CONTRACT)

    def test_current_placement_with_future_collection_keeps_original_annotation_and_wording(self):
        for timing in ('current', 'future'):
            with self.subTest(timing=timing):
                answers, facts = self.assess(timing=timing)
                answer = answers['investigation']
                self.assertEqual(answer['status'], 'supported', answer['review_reasons'])
                self.assertEqual(answer['text'], self.order+'; '+self.status)
                self.assertEqual(facts['order']['timing']['kind'], timing)
                self.assertEqual(facts['order']['issues'], [])
                self.assertEqual(facts['status']['timing']['kind'], 'current')
                self.assertEqual(facts['status']['polarity'], 'negated')

    def test_retained_v22_keeps_its_current_only_coverage_result(self):
        answers, _ = self.assess(profile=semantic.COMPLETE_NARRATIVE_SCOPE_CONTRACT)
        self.assertEqual(answers['investigation']['status'], 'conflict')
        self.assertTrue(any('investigation_order' in reason
            for reason in answers['investigation']['review_reasons']))

    def test_future_label_does_not_acquire_current_only_destination_permission(self):
        answers, _ = self.assess(scope='current')
        self.assertEqual(answers['investigation']['status'], 'conflict')
        self.assertTrue(any('timing does not match' in reason
            for reason in answers['investigation']['review_reasons']))

    def test_order_and_nonperformance_both_remain_required(self):
        for selected in (['order'], ['status'], []):
            with self.subTest(selected=selected):
                answers, _ = self.assess(selected=selected)
                self.assertNotEqual(answers['investigation']['status'], 'supported')

    def test_partial_order_cannot_cover_its_purpose_or_future_event(self):
        for value in ('thyroid-stimulating hormone blood test',
                      self.order.split(' for collection')[0],
                      self.order.split(' as part of')[0], 'constipation evaluation'):
            with self.subTest(value=value):
                answers, _ = self.assess(order_value=value)
                self.assertNotEqual(answers['investigation']['status'], 'supported')

    def test_complete_future_order_requires_plan_kind_affirmed_polarity_and_bounded_timing(self):
        for options in ({'kind': 'finding'}, {'kind': 'assessment'}, {'kind': 'history'},
                        {'polarity': 'negated'}, {'polarity': 'uncertain'}, {'polarity': 'mixed'},
                        {'timing': 'past'}, {'timing': 'unspecified'}):
            with self.subTest(options=options):
                answers, facts = self.assess(**options)
                self.assertTrue(facts['order']['issues'])
                self.assertNotEqual(answers['investigation']['status'], 'supported')

    def test_family_history_indication_remains_a_complete_order_without_patient_disease(self):
        source = 'I ordered a blood test for family history of thyroid disease, with collection planned tomorrow'
        for timing in ('current', 'future'):
            with self.subTest(timing=timing):
                answers, facts = self.assess(order=source, timing=timing)
                self.assertEqual(answers['investigation']['status'], 'supported', answers)
                self.assertEqual(answers['investigation']['text'], source+'; '+self.status)
                self.assertEqual(facts['order']['issues'], [])
                self.assertEqual(facts['order']['timing']['kind'], timing)
        for value in ('thyroid disease', 'family history of thyroid disease', 'collection planned tomorrow'):
            answers, facts = self.assess(order=source, order_value=value)
            self.assertTrue(facts['order']['issues'])
            self.assertNotEqual(answers['investigation']['status'], 'supported')

    def test_foreign_historical_uncertain_and_qualified_orders_remain_held(self):
        sources = [self.order.replace(' is ordered ', ' was ordered '),
                   self.order.replace(' is ordered ', ' may be ordered '),
                   self.order.replace(' is ordered ', ' is not ordered '),
                   self.order+' unless symptoms resolve', self.order+' and is withdrawn',
                   'Reportedly, '+self.order, '"'+self.order+'"',
                   self.order.replace(' for collection', ' for her mother for collection')]
        for source in sources:
            with self.subTest(source=source):
                answers, _ = self.assess(order=source)
                self.assertNotEqual(answers['investigation']['status'], 'supported')
        for section in ('Previous encounter:', "Mother's history:", 'Future encounter:', 'A'):
            with self.subTest(section=section):
                answers, _ = self.assess(section=section)
                self.assertNotEqual(answers['investigation']['status'], 'supported')

    def test_a_future_order_plan_never_becomes_current_placement(self):
        from core.order_event_roles import order_event_frame
        source = self.order.replace(' is ordered ', ' will be ordered ')
        self.assertIsNone(order_event_frame(source))
        answers, facts = self.assess(order=source)
        self.assertEqual(facts['order']['timing']['kind'], 'future')
        answer = answers['investigation']
        if answer['status'] == 'supported':
            self.assertEqual(answer['text'], source+'; '+self.status)
        else:
            self.assertEqual(answer['text'], '')
