"""Prospective diagnostic provenance without changing an eligibility decision."""
from copy import deepcopy
import hashlib
from types import SimpleNamespace as N
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import coding_engine as engine, corti_coding as coding
from core.tests import test_coding_qualified_assertions as fixtures
from core.tests.test_coding_nec import retained_case
from core.tests.test_coding_source_governance import FIXTURE


class CortiSourceDiagnosticTests(SimpleTestCase):
    def setUp(self):
        fixture = fixtures.QualifiedAssertionTests()
        fixture.setUp()
        self.reference = fixture.reference
        self.prefix = 'Patient: Synthetic Ellis Vale\r\nAssessment\r\n'

    def route(self, body, code='R12', *, selected=None, quote=None, reference=None, spans=None):
        notes = self.prefix + body
        reference = reference or self.reference
        quote = quote or body
        start = notes.index(quote)
        proposal = {'id': 'selected:0', 'code': code,
            'terminology': {'description': reference.tabular['codes'][code]},
            'evidence': spans or [{'text': quote, 'start': start, 'end': start + len(quote),
                                  'status': 'valid', 'context_index': 0}]}
        run = N(inputs={'notes': notes}, config={'clinical_source_contract': engine.QUALIFIED_SOURCE_CONTRACT})
        # The existing reference reader memoizes its lookup on first use.
        # Compare the stable bound reference, not that pre-existing cache fill.
        engine.index_lookup(reference)
        before = deepcopy((vars(run), vars(reference), proposal))
        legacy = coding._icd_source(run, reference, proposal, selected or [code])
        diagnostics = coding._route_diagnostics(run, reference, proposal)
        current = coding._icd_source(run, reference, proposal, selected or [code], diagnostics=diagnostics)
        self.assertEqual(current, legacy)
        self.assertEqual((vars(run), vars(reference), proposal), before)
        return current, diagnostics

    def test_actual_shape_unrecognized_assertion_keeps_the_initiating_reason(self):
        body = 'Heartburn and constipation were each evaluated at this encounter.'
        for code in ('R12', 'K59.00'):
            with self.subTest(code=code):
                result, trace = self.route(body, code)
                self.assertIsNone(result[1])
                failure = trace['initiating_failure']
                self.assertEqual(failure['gate'], 'source_disposition')
                self.assertEqual(failure['detail']['disposition'], 'question')
                self.assertIn('does not independently affirm', failure['detail']['reason'])
                first = trace['attempts'][0]
                self.assertEqual([x['gate'] for x in first['gates']], ['source_scope',
                    'source_disposition', 'contextual_validation', 'index_route', 'specificity',
                    'more_specific_source_routes'])
                self.assertEqual(first['gates'][-1]['status'], 'not_evaluated')
                self.assertTrue(all(x['status'] == 'passed' for x in first['gates'][2:5]))
                self.assertTrue(all(u['owned_current'] for w in first['expanded_source'] for u in w['units']))
                self.assertEqual(trace['source_sha256'], hashlib.sha256((self.prefix + body).encode()).hexdigest())
                self.assertEqual(trace['source_profile'], engine.source_profile(engine.QUALIFIED_SOURCE_CONTRACT))
                fallback = trace['attempts'][-1]['gates'][0]
                self.assertEqual(fallback['detail']['internal_checks'], 'not_instrumented')

    def test_scope_stop_does_not_claim_that_later_gates_ran(self):
        body = 'Mother:\r\nThe patient reports heartburn today.'
        _, trace = self.route(body, quote=body.split('\r\n')[1])
        first = trace['attempts'][0]
        self.assertEqual(first['failures'][0]['gate'], 'source_scope')
        self.assertEqual([x['status'] for x in first['gates']], ['failed'] + ['not_evaluated'] * 5)
        self.assertTrue(any(not u['owned_current'] for w in first['expanded_source'] for u in w['units']))

    def test_reference_conflict_is_distinct_from_source_interpretation(self):
        _, trace = self.route('The patient reports heartburn today.', selected=['R12', 'K30'])
        self.assertEqual(trace['initiating_failure']['gate'], 'contextual_validation')
        self.assertIn('excludes1_selected_code_conflict', trace['initiating_failure']['detail']['errors'])
        self.assertEqual(trace['attempts'][0]['gates'][1]['status'], 'passed')
        self.assertEqual(trace['attempts'][0]['gates'][-1]['status'], 'not_evaluated')

    def test_index_qualifier_is_distinct_from_source_and_tabular(self):
        _, trace = self.route('The patient reports constipation today.', 'K59.01')
        self.assertEqual(trace['initiating_failure']['gate'], 'index_route')
        self.assertTrue(trace['initiating_failure']['detail']['errors'])

    def test_missing_or_review_only_index_entry_does_not_invent_source_failure(self):
        for review_only in (False, True):
            reference = deepcopy(self.reference)
            if review_only:
                for entry in reference.index:
                    if entry.get('code') == 'R12':
                        entry['requires_review'] = True
            else:
                reference.index = [x for x in reference.index if x.get('code') != 'R12']
            with self.subTest(review_only=review_only):
                _, trace = self.route('The patient reports heartburn today.', reference=reference)
                self.assertEqual(trace['initiating_failure']['gate'], 'index_candidate')
                self.assertEqual(bool(trace['initiating_failure']['detail']['review_required_entry_ids']), review_only)

    def test_eligible_route_has_no_overall_failure_and_no_extra_candidate(self):
        result, trace = self.route('The patient reports heartburn today.')
        self.assertEqual(result[1]['code'], 'R12')
        self.assertEqual(trace['outcome'], 'eligible')
        self.assertIsNone(trace['initiating_failure'])
        self.assertEqual(trace['attempts'][0]['gates'][-1]['status'], 'passed')
        self.assertEqual(len(trace['attempts']), 1)

    def test_repeated_source_text_retains_every_occurrence_and_scope(self):
        quote = 'The patient reports heartburn today.'
        _, trace = self.route(quote + '\r\nMother:\r\n' + quote, quote=quote)
        witnesses = trace['attempts'][0]['expanded_source']
        self.assertEqual(len(witnesses), 2)
        self.assertNotEqual(witnesses[0]['start'], witnesses[1]['start'])
        self.assertTrue(any(u['owned_current'] for w in witnesses for u in w['units']))
        self.assertTrue(any(not u['owned_current'] for w in witnesses for u in w['units']))
        self.assertEqual(trace['initiating_failure']['gate'], 'source_scope')

    def test_invalid_and_unrelated_spans_are_not_omitted(self):
        body = 'The patient reports heartburn today.\r\nNausea.'
        start = len(self.prefix)
        spans = [{'text': 'Nausea.', 'start': start + len(body) - 7, 'end': start + len(body),
                  'status': 'valid', 'context_index': 0},
                 {'text': 'Heartburn', 'start': 0, 'end': 9, 'status': 'invalid', 'context_index': 0},
                 {'text': body.split('\r\n')[0], 'start': start, 'end': start + len(body.split('\r\n')[0]),
                  'status': 'valid', 'context_index': 0}]
        result, trace = self.route(body, spans=spans)
        self.assertEqual(result[1]['code'], 'R12')
        self.assertEqual([a['gates'][0]['gate'] for a in trace['attempts']],
                         ['source_lexical_link', 'provider_span', 'source_scope'])
        self.assertEqual(trace['attempts'][0]['gates'][0]['status'], 'not_applicable')
        self.assertEqual([a['provider_span'] for a in trace['attempts']], spans)
        self.assertIsNone(trace['initiating_failure'])

    def test_unmentioned_official_synonym_cannot_hide_real_source_blocker(self):
        reference = deepcopy(self.reference)
        head = next(x for x in reference.index if x.get('code') == 'R12')
        alias = {**deepcopy(head), 'id': 'synthetic-alternate-head', 'term': 'Pyrosis', 'path': ['Pyrosis']}
        reference.index.insert(0, alias)
        _, trace = self.route('Heartburn and constipation were each evaluated at this encounter.', reference=reference)
        self.assertEqual(trace['attempts'][0]['gates'][0]['status'], 'not_applicable')
        self.assertEqual(trace['initiating_failure']['gate'], 'source_disposition')

    def test_diagnostics_do_not_evaluate_short_circuited_predicate(self):
        with patch.object(engine, 'more_specific_source_routes', side_effect=AssertionError('must not run')):
            self.route('Heartburn and constipation were each evaluated at this encounter.')

    def test_all_evaluated_failures_are_ordered_and_not_replaced_by_first(self):
        with patch.object(engine, 'contextual_validation', return_value={'valid': False, 'errors': ['context-error']}), \
             patch.object(engine, 'index_route_errors', return_value=['index-error']), \
             patch.object(engine, 'specificity_errors', return_value=['specificity-error']):
            _, trace = self.route('Heartburn and constipation were each evaluated at this encounter.')
        first = trace['attempts'][0]
        self.assertEqual([x['gate'] for x in first['failures']],
            ['source_disposition', 'contextual_validation', 'index_route', 'specificity'])
        self.assertEqual(trace['initiating_failure']['gate'], 'source_disposition')
        self.assertEqual(first['gates'][-1]['status'], 'not_evaluated')

    def retained(self, contract=None):
        case = retained_case()
        run = case.run_value(0, contract=engine.ASSERTION_SOURCE_CONTRACT)
        if contract is not None:
            run.config['coding_diagnostic_contract'] = contract
        old = FIXTURE['runs'][0]['result']
        with patch.object(coding, 'terminology', return_value=(case.terms, old['cpt'])), \
             patch.object(engine, 'reference_for', return_value=case.reference):
            return coding.retained_result(run, old['provider_request'],
                old['adapter']['diagnostics']['provider_response'], FIXTURE['runs'][0]['requests'][0]['response_sha256'])

    def test_historical_retained_result_without_contract_is_exact(self):
        result = self.retained()
        expected = {k: v for k, v in FIXTURE['runs'][0]['result'].items() if k != 'retained_prediction'}
        self.assertEqual(engine.canonical(result), engine.canonical(expected))
        self.assertNotIn('source_diagnostics', result)

    def test_opt_in_keeps_all_provider_proposals_and_authority_holds(self):
        old, current = self.retained(), self.retained(coding.DIAGNOSTIC_CONTRACT)
        self.assertEqual(current['adapter'], old['adapter'])
        self.assertEqual(current['provider_request'], old['provider_request'])
        self.assertEqual(current['candidates'], old['candidates'])
        self.assertEqual(current['source_checks'], old['source_checks'])
        self.assertEqual([(x['id'], x['code'], x['eligible']) for x in current['suggestions']],
                         [(x['id'], x['code'], x['eligible']) for x in old['suggestions']])
        self.assertEqual(current['suggestions'][-1], old['suggestions'][-1])
        first = current['source_diagnostics']['icd_routes']['selected:0']['initiating_failure']
        self.assertIsNotNone(first)
        self.assertIn(first['gate'], current['suggestions'][0]['hold_reasons'][0])
        self.assertNotIn('lacks a locally verified source-to-Index-to-Tabular', current['suggestions'][0]['hold_reasons'][0])

    def test_unknown_diagnostic_contract_refuses_before_reference_access(self):
        with patch.object(coding, 'terminology', side_effect=AssertionError('reference access')):
            with self.assertRaisesMessage(ValidationError, 'Unknown coding diagnostic contract'):
                # retained() deliberately provides a local reference; validation must precede it.
                case = retained_case(); run = case.run_value(0)
                run.config['coding_diagnostic_contract'] = 'unknown'
                old = FIXTURE['runs'][0]['result']
                coding.retained_result(run, old['provider_request'],
                    old['adapter']['diagnostics']['provider_response'], 'a' * 64)
