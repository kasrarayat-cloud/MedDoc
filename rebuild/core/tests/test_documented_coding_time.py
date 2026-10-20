"""Finite prospective time-reader regression; no provider or database calls."""
from copy import deepcopy
from datetime import date
import hashlib
import json
from types import SimpleNamespace as N
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import coding_dispatch, coding_engine, corti_semantics as time


CONTRACT = 'source-bound-clinical-coding-v8'


class DocumentedCodingTimeTests(SimpleTestCase):
    note = (
        'Patient: Synthetic Ada Tern\nDate of service: 19 October 2026\n'
        'Treating physician: Dr. Maya Chen\nSubjective\n'
        'Ada is a 52-year-old woman seen in person in a United States gastroenterology office. '
        'She is an established patient of Dr. Maya Chen.\nPlan\n'
        'Office E/M selection is based on total physician time on the date of service. '
        'Dr. Chen personally spent 28 minutes on 19 October 2026: four minutes reviewing records, '
        '19 minutes obtaining the history, examining and counseling the patient, and five minutes '
        'placing the laboratory order and documenting the encounter. '
        'These activities were all completed by the physician on the service date. '
        'The 28 minutes exclude six minutes of staff intake and three minutes of physician '
        'chart review on 18 October 2026. '
        'Time for separately reported services is excluded from the 28-minute total.')

    def support(self, note=None, contract=CONTRACT):
        note = self.note if note is None else note
        facts = time.office_time_facts(note, contract=contract)
        errors = time.office_service_eligibility(note, date(2026, 10, 19), contract=contract)
        return facts, errors

    def test_exact_documented_office_account_has_all_eight_facts(self):
        facts, errors = self.support()
        self.assertEqual(errors, [])
        self.assertEqual(facts['status'], 'documented', facts)
        self.assertEqual(len(facts['facts']), 8)
        self.assertEqual(next(f['value'] for f in facts['facts'] if f['key'] == 'time_minutes'), 28)
        self.assertFalse(facts['clinician_confirmed'])
        for fact in facts['facts']:
            self.assertEqual(self.note[fact['start']:fact['end']], fact['quote'])
        self.assertEqual(time.citation_adequacy([], facts['facts'])['status'], 'insufficient_for_time_review')

    def test_legacy_v7_keeps_original_false_rejection(self):
        facts, unused = self.support(contract=coding_engine.QUALIFIED_SOURCE_CONTRACT)
        self.assertEqual(facts['status'], 'requires_clarification')
        self.assertEqual([f['key'] for f in facts['facts']], ['patient_status'])

    def test_actual_retraction_and_exclusion_qualifications_remain_held(self):
        for before, after in (
            ('28-minute total.', '28-minute total. The above physician time is incorrect.'),
            ('The 28 minutes exclude', 'The 28 minutes include'),
            ('The 28 minutes exclude', 'The 28 minutes do not exclude'),
            ('18 October 2026.', '18 October 2026, but the total is incorrect.'),
            ('18 October 2026.', '18 October 2026 unless needed.'),
            ('is excluded from the 28-minute total.', 'is not excluded from the 28-minute total.'),
            ('is excluded from the 28-minute total.', 'is excluded from the 28-minute total unless performed.'),
            ('28-minute total.', '28-minute total. Another physician spent 12 minutes today.'),
        ):
            with self.subTest(after=after):
                facts, errors = self.support(self.note.replace(before, after))
                self.assertTrue(facts['status'] != 'documented' or errors)

    def test_exclusions_do_not_add_staff_or_other_day_work_to_total(self):
        for before, after in (
            ('Dr. Chen personally spent', 'The staff personally spent'),
            ('Dr. Chen personally spent', 'Dr. Other personally spent'),
            ('28 minutes on 19 October 2026:', '28 minutes on 18 October 2026:'),
            ('19 minutes obtaining', '18 minutes obtaining'),
            ('28-minute total.', '29-minute total.'),
            ('The 28 minutes exclude', 'The 29 minutes exclude'),
            ('on 18 October 2026.', 'on 31 February 2026.'),
            ('on 18 October 2026.', 'on 20 October 2026.'),
            ('placing the laboratory order', 'performing the laboratory test'),
        ):
            with self.subTest(after=after):
                facts, errors = self.support(self.note.replace(before, after))
                self.assertTrue(facts['status'] != 'documented' or errors)

    def test_setting_requires_complete_owned_actual_medical_attendance(self):
        for before, after in (
            ('Ada is a', 'Another patient is a'),
            ('Ada is a', 'Beatrice is a'),
            ('woman seen in person', 'woman possibly seen in person'),
            ('woman seen in person', 'woman not seen in person'),
            ('gastroenterology office.', 'gastroenterology office, but the visit was cancelled.'),
            ('gastroenterology office', 'post office'),
            ('gastroenterology office', 'astrology office'),
            ('United States gastroenterology office', 'United States emergency department'),
        ):
            with self.subTest(after=after):
                facts, errors = self.support(self.note.replace(before, after))
                self.assertTrue(facts['status'] != 'documented' or errors)

    def test_new_legacy_request_selects_v8_and_prior_contract_stays_pinned(self):
        first = [None]
        query = N(order_by=lambda *a: N(first=lambda: first[0]))
        from core.models import CodingRun
        with patch.object(coding_dispatch, 'provider', return_value='corti'), \
             patch.object(coding_dispatch, 'source_context_enabled', return_value=True), \
             patch('core.corti_prediction.configuration', side_effect=lambda *unused: {'provider': 'corti'}), \
             patch.object(CodingRun.objects, 'filter', return_value=query):
            result = coding_dispatch.configuration(None, N())
            self.assertEqual(result['clinical_source_contract'], coding_engine.QUALIFIED_SOURCE_CONTRACT)
            self.assertEqual(result['cpt_time_source_contract'], CONTRACT)
            # Historical configurations retain their absent time-policy key.
            # The prospective shared reader requires its explicit paired policy.
            for contract in sorted(coding_engine.SOURCE_CONTRACTS - {coding_engine.SHARED_SOURCE_CONTRACT}):
                with self.subTest(contract=contract):
                    first[0] = N(config={'clinical_source_contract': contract})
                    before = deepcopy(first[0].config)
                    result = coding_dispatch.configuration(None, N())
                    self.assertEqual(result['clinical_source_contract'], contract)
                    self.assertNotIn('cpt_time_source_contract', result)
                    self.assertEqual(first[0].config, before)
            first[0] = N(config={'clinical_source_contract': coding_engine.SHARED_SOURCE_CONTRACT})
            before = deepcopy(first[0].config)
            result = coding_dispatch.configuration(None, N())
            self.assertEqual(result['clinical_source_contract'], coding_engine.SHARED_SOURCE_CONTRACT)
            self.assertEqual(result['cpt_time_source_contract'], time.SHARED_TIME_CONTRACT)
            self.assertEqual(first[0].config, before)
            first[0] = N(config={'clinical_source_contract': coding_engine.QUALIFIED_SOURCE_CONTRACT,
                                'cpt_time_source_contract': CONTRACT})
            self.assertEqual(coding_dispatch.configuration(None, N())['cpt_time_source_contract'], CONTRACT)
            from core import source_assertion_coding as shared
            encounter = N(template_version=N(semantic_definitions={'field': {'version': 4}}))
            with patch.object(shared, 'snapshot', return_value=N()):
                graph = coding_dispatch.configuration(None, encounter)
            self.assertEqual(graph['clinical_source_contract'], shared.CONTRACT)
            self.assertNotIn('cpt_time_source_contract', graph)
            for clinical, policy in ((coding_engine.QUALIFIED_SOURCE_CONTRACT, 'unknown'),
                                      (coding_engine.SOAP_SOURCE_CONTRACT, CONTRACT)):
                first[0] = N(config={'clinical_source_contract': clinical, 'cpt_time_source_contract': policy})
                with self.subTest(clinical=clinical, policy=policy), self.assertRaises(ValidationError):
                    coding_dispatch.configuration(None, N())

    def test_unknown_time_policy_is_refused_and_missing_policy_never_upgrades(self):
        self.assertEqual(time.time_contract({'clinical_source_contract': coding_engine.QUALIFIED_SOURCE_CONTRACT}),
                         coding_engine.QUALIFIED_SOURCE_CONTRACT)
        for clinical, policy in ((coding_engine.QUALIFIED_SOURCE_CONTRACT, 'unknown'),
                                  (coding_engine.SOAP_SOURCE_CONTRACT, CONTRACT)):
            with self.subTest(clinical=clinical, policy=policy), self.assertRaises(ValueError):
                time.time_contract({'clinical_source_contract': clinical, 'cpt_time_source_contract': policy})

    def test_cpt_adaptation_uses_time_policy_without_changing_selection_or_citations(self):
        from core import corti_coding, corti_prediction
        from core.corti_response import DatedTerminology
        run = N(inputs={'engine_contract': corti_coding.CONTRACT, 'notes': self.note,
                        'service_date': '2026-10-19'}, context={'setting': 'outpatient_office'},
                config={'mode': 'live', 'clinical_source_contract': coding_engine.QUALIFIED_SOURCE_CONTRACT})
        request = corti_prediction.payload(run)
        selected = {'system': 'cpt', 'code': '99213', 'display': 'Unverified provider wording',
                    'evidences': [{'contextIndex': 0, 'start': 0, 'end': len(self.note), 'text': self.note}]}
        response = {'codes': [selected]}
        retained = deepcopy(response)
        with patch.object(corti_coding, 'terminology', return_value=(DatedTerminology(), {'available': False})), \
             patch.object(corti_coding.engine, 'reference_for', return_value=N()), \
             patch.object(corti_coding, 'identity_blockers', return_value=[]):
            old = corti_coding.retained_result(run, request, response, hashlib.sha256(json.dumps(response).encode()).hexdigest())
            run.config['cpt_time_source_contract'] = CONTRACT
            new = corti_coding.retained_result(run, request, response, hashlib.sha256(json.dumps(response).encode()).hexdigest())
        before, after = old['suggestions'][0], new['suggestions'][0]
        self.assertEqual(before['semantic_support']['documented_time_facts']['status'], 'requires_clarification')
        self.assertEqual(after['semantic_support']['documented_time_facts']['status'], 'documented')
        self.assertEqual(before['evidence_spans'], after['evidence_spans'])
        self.assertEqual(before['code'], after['code'])
        self.assertFalse(after['eligible'])  # Time support is not catalogue authority or approval.
        self.assertEqual(response, retained)

    def test_bounded_output_review_consumes_time_policy_separately_from_clinical_contract(self):
        from core.tests.test_coordinated_coding import CoordinatedCPTOutputTests, bind_request
        fixture = CoordinatedCPTOutputTests('test_retained_selected_cpt_number_uses_complete_source_and_keeps_descriptor_limit')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.run.config.update(clinical_source_contract=coding_engine.QUALIFIED_SOURCE_CONTRACT,
                                  cpt_time_source_contract=CONTRACT)
        bind_request(fixture.run)
        with patch('core.corti_semantics.office_time_facts', wraps=time.office_time_facts) as observed:
            result = fixture.assessment()
        self.assertEqual(observed.call_args.kwargs['contract'], CONTRACT)
        self.assertEqual(result['selection']['code'], '99214')
        self.assertEqual(len(result['facts']), 8)
        self.assertEqual(result['description_status'], 'withheld_unverified_provider_text')

    def test_later_current_account_and_service_claims_cannot_disappear(self):
        tails = (
            'These activities were actually performed yesterday.',
            'These activities were actually performed by the staff.',
            'These activities were actually performed by Dr. Other.',
            'The physician did not complete these activities on the service date.',
            'The physician did not perform those activities today.',
            'The five minutes placing the laboratory order and documenting the encounter were performed yesterday.',
            'The four minutes reviewing records overlapped the five minutes documenting the encounter.',
            'The 28-minute total should be 29 minutes.',
            'The correct physician total is 20 minutes.',
            'Correction: physician total is 20 minutes.',
            'Revised physician time is 20 minutes.',
            'The twenty-eight-minute total should be twenty-nine minutes.',
            'This time includes the excluded staff intake.',
            'Additional physician time today was 30 minutes.',
            'The physician spent an additional 30 minutes today.',
            'Dr. Chen additionally spent 30 minutes today.',
            'The E/M time selection remains unverified.',
            'This visit was actually performed by telephone.',
            'The visit was actually performed by telephone.',
        )
        for tail in tails:
            with self.subTest(tail=tail):
                facts, errors = self.support(self.note+' '+tail)
                self.assertNotEqual(facts['status'], 'documented')
                self.assertTrue(errors)

    def test_unrelated_foreign_and_historical_accounts_are_separate(self):
        for suffix in (
            '\nMother\nThese activities were actually performed yesterday.',
            '\nPrevious visit\nThe correct physician total is 20 minutes.',
            '\nPrevious visit\nThis visit was actually performed by telephone.',
            '\nAt a previous visit, these activities were actually performed yesterday.',
            "\nHer sister's total should be 29 minutes.",
            '\nThe total fluid intake was 240 mL.',
            '\nThe ten-minute heartburn episodes resolved.',
            '\nHer work was actually performed yesterday.',
            "\nThe patient's work was performed by the staff.",
            '\nThese household activities were actually performed yesterday.',
            '\nThe volunteer work was performed by Dr. Other.',
            "\nAll of her sister's activities were performed yesterday.",
        ):
            with self.subTest(suffix=suffix):
                facts, errors = self.support(self.note+suffix)
                self.assertEqual(facts['status'], 'documented', facts)
                self.assertEqual(errors, [])
        before = self.note.replace('Subjective\n', 'Subjective\nThese activities were performed yesterday.\n')
        facts, errors = self.support(before)
        self.assertEqual(facts['status'], 'documented', facts)
        self.assertEqual(errors, [])

    def test_referential_account_modifiers_and_quantifiers_compose(self):
        for quantifier in ('', 'All ', 'Some of ', 'None of ', 'Each of '):
            for modifier in ('', 'documented ', 'above ', 'current '):
                tail = quantifier+'these '+modifier+'activities were performed yesterday.'
                tail = tail[0].upper()+tail[1:]
                with self.subTest(tail=tail):
                    facts, errors = self.support(self.note+' '+tail)
                    self.assertNotEqual(facts['status'], 'documented')
                    self.assertTrue(errors)
        for modifier in ('current', 'above', 'final', 'corrected'):
            for account, predicate in (('total', 'should be 29 minutes'), ('time', 'was performed yesterday'),
                                       ('work', 'was performed by the staff'), ('activities', 'were performed by Dr. Other')):
                tail = 'The '+modifier+' '+account+' '+predicate+'.'
                with self.subTest(tail=tail):
                    facts, errors = self.support(self.note+' '+tail)
                    self.assertTrue(facts['status'] != 'documented' or errors)

    def test_discourse_prefixes_preserve_current_account_qualifications_and_other_owners(self):
        for prefix in ('However, ', 'Actually, ', 'In fact, ', 'On review, '):
            for statement in ('these activities were actually performed yesterday.',
                              'these activities were performed by the staff.',
                              'the correct physician total is 20 minutes.'):
                tail = prefix+statement
                with self.subTest(tail=tail):
                    facts, errors = self.support(self.note+' '+tail)
                    self.assertTrue(facts['status'] != 'documented' or errors)
            for statement in ("her sister's activities were performed yesterday.",
                              'at a previous visit, these activities were performed yesterday.',
                              'these household activities were performed yesterday.',
                              'the total fluid intake was 240 mL.'):
                with self.subTest(unrelated=prefix+statement):
                    facts, errors = self.support(self.note+' '+prefix+statement)
                    self.assertEqual(facts['status'], 'documented', facts)
                    self.assertEqual(errors, [])

    def test_discourse_prefix_bound_holds_current_scope_and_preserves_explicit_other_scope(self):
        for depth in (4, 5, 8):
            prefix = 'However, '*depth
            for statement in ('these activities were performed by staff.',
                              'the correct physician total is 20 minutes.',
                              'this visit was performed by telephone.'):
                with self.subTest(depth=depth, statement=statement):
                    facts, errors = self.support(self.note+' '+prefix+statement)
                    self.assertNotEqual(facts['status'], 'documented')
                    self.assertTrue(errors)
            for scope in ('Mother', 'Previous visit'):
                with self.subTest(depth=depth, scope=scope):
                    facts, errors = self.support(self.note+'\n'+scope+'\n'+prefix+
                                                 'these activities were performed by staff.')
                    self.assertEqual(facts['status'], 'documented', facts)
                    self.assertEqual(errors, [])
        # The finite parser cannot exempt even a benign current account when
        # its discourse scope exceeds the bound; it must request source review.
        facts, errors = self.support(self.note+' '+'However, '*5+'the total fluid intake was 240 mL.')
        self.assertNotEqual(facts['status'], 'documented')
        self.assertTrue(errors)

    def test_bounded_review_refuses_later_current_account_or_service_qualification(self):
        from core.tests.test_coordinated_coding import CoordinatedCPTOutputTests, NOTE
        for tail in (
            'These activities were actually performed yesterday.',
            'These activities were actually performed by the staff.',
            'These activities were actually performed by Dr. Other.',
            'The 37-minute total should be 29 minutes.',
            'The correct physician total is 20 minutes.',
            'Correction: physician total is 20 minutes.',
            'The E/M time selection remains unverified.',
            'This visit was actually performed by telephone.',
        ):
            with self.subTest(tail=tail):
                fixture = CoordinatedCPTOutputTests('test_retained_selected_cpt_number_uses_complete_source_and_keeps_descriptor_limit')
                fixture.setUp()
                try:
                    fixture.run.config.update(clinical_source_contract=coding_engine.QUALIFIED_SOURCE_CONTRACT,
                                              cpt_time_source_contract=CONTRACT)
                    fixture.source(NOTE+'\r\n'+tail)
                    with self.assertRaises(ValidationError):
                        fixture.assessment()
                finally:
                    fixture.doCleanups()

    def test_independent_round_two_matrix_through_actual_bounded_consumer(self):
        from core.tests.test_coordinated_coding import CoordinatedCPTOutputTests, NOTE
        cases = (
            ('', True),
            ('However, these activities were actually performed yesterday.', False),
            ('In fact, these activities were performed by the staff.', False),
            ('For billing purposes, the correct physician total is 20 minutes.', False),
            ('Total physician time, corrected: 29 minutes.', False),
            ('Correction to the above time: 29 minutes.', False),
            ('The total physician time should read 29 minutes.', False),
            ('The stated 37 minutes are an unconfirmed estimate.', False),
            ('The above physician time belongs to a different patient.', False),
            ('The above total is cumulative over two separate visits.', False),
            ('The stated 37 minutes include time for separately reported services.', False),
            ('The above physician time entry includes the preceding day chart review.', False),
            ('Ten of the stated 37 physician minutes were waiting for the patient to arrive.', False),
            ('Correction: the above encounter took place on 16 October 2026.', False),
            ('No services were provided on the stated date of service.', False),
            ('Correction: this encounter was performed entirely by telephone.', False),
            ('The above encounter was actually a home visit.', False),
            ('This encounter was an inpatient hospital visit.', False),
            ('The patient was actually new to this practice and this specialty.', False),
            ('The documented evaluation was performed only by the nurse.', False),
            ('His mother was seen by telephone yesterday.', True),
            ('His prior visit was a telephone consultation.', True),
            ('His mother spent 29 minutes with her physician at a different clinic yesterday.', True),
            ('The patient spent 20 minutes in the waiting room before this encounter.', True),
            ('Last month he had an unverified report of fever after travel.', True),
            ('His father cancelled an outpatient appointment yesterday.', True),
            ('At an unrelated prior encounter, another physician spent 20 minutes evaluating an ankle sprain.', True),
        )
        for tail, allowed in cases:
            with self.subTest(tail=tail, allowed=allowed):
                fixture = CoordinatedCPTOutputTests('test_retained_selected_cpt_number_uses_complete_source_and_keeps_descriptor_limit')
                fixture.setUp()
                try:
                    fixture.run.config.update(clinical_source_contract=coding_engine.QUALIFIED_SOURCE_CONTRACT,
                                              cpt_time_source_contract=CONTRACT)
                    fixture.source(NOTE+('\r\n'+tail if tail else ''))
                    if allowed:
                        result = fixture.assessment()
                        self.assertEqual(result['selection']['code'], '99214')
                        self.assertEqual(len(result['facts']), 8)
                    else:
                        with self.assertRaises(ValidationError):
                            fixture.assessment()
                finally:
                    fixture.doCleanups()

    def test_complete_current_subject_scope_is_independent_of_preparatory_words(self):
        for prefix in ('For billing purposes, ', 'After reconciling the record, ',
                       'For the avoidance of doubt ', 'A final clarification: '):
            for claim in ('the correct physician total is 20 minutes.',
                          'these documented activities were performed by staff.',
                          'the above encounter took place on 18 October 2026.',
                          'the current encounter was a home visit.',
                          'no services were provided on the stated service date.',
                          'the documented evaluation was performed only by the nurse.',
                          'the patient was actually new to this practice and this specialty.'):
                with self.subTest(prefix=prefix, claim=claim):
                    facts, errors = self.support(self.note+' '+prefix+claim)
                    self.assertNotEqual(facts['status'], 'documented')
                    self.assertTrue(errors)

    def test_complete_unrelated_duration_subjects_do_not_qualify_current_physician_time(self):
        for prefix in ('', 'However, ', 'For administrative purposes, '):
            for claim in ('the patient spent 20 minutes in the waiting room before this encounter.',
                          'the patient spent twenty minutes waiting before this visit.',
                          'at an unrelated prior encounter, another physician spent 20 minutes evaluating an ankle sprain.',
                          'during a previous consultation, a different physician spent 15 minutes reviewing an old knee injury.',
                          'the patient was given a new dietary handout.',
                          "for his mother's visit, the correct physician total is 20 minutes."):
                with self.subTest(prefix=prefix, claim=claim):
                    text = prefix+claim
                    text = text[0].upper()+text[1:]
                    facts, errors = self.support(self.note+'\n'+text)
                    self.assertEqual(facts['status'], 'documented', facts)
                    self.assertEqual(errors, [])
        for claim in ('these activities were actually performed yesterday.',
                      'these activities were actually performed by the staff.',
                      'the stated physician total includes 20 minutes spent waiting for the patient.'):
            with self.subTest(current_claim=claim):
                facts, errors = self.support(self.note+'\nFor administrative purposes, '+claim)
                self.assertNotEqual(facts['status'], 'documented')
                self.assertTrue(errors)

    def test_service_and_status_qualifications_bind_before_or_after_physician_time(self):
        from core.tests.test_coordinated_coding import CoordinatedCPTOutputTests, NOTE
        marker = 'Office E/M selection is based on total physician time on the date of service.'
        self.assertEqual(NOTE.count(marker), 1)
        for statement, allowed in (
            ('The above encounter was actually a home visit.', False),
            ('The patient was actually new to this practice and this specialty.', False),
            ('Correction: the above encounter took place on 16 October 2026.', False),
            ('The documented evaluation was performed only by the nurse.', False),
            ('His mother was seen by telephone yesterday.', True),
            ('His prior visit was a telephone consultation.', True),
            ('At an unrelated prior encounter, another physician spent 20 minutes evaluating an ankle sprain.', True),
            ('The patient spent 20 minutes in the waiting room before this encounter.', True),
        ):
            for position in ('before', 'after'):
                with self.subTest(statement=statement, position=position):
                    note = (NOTE.replace(marker, statement+'\r\n'+marker) if position == 'before'
                            else NOTE+'\r\n'+statement)
                    fixture = CoordinatedCPTOutputTests('test_retained_selected_cpt_number_uses_complete_source_and_keeps_descriptor_limit')
                    fixture.setUp()
                    try:
                        fixture.run.config.update(clinical_source_contract=coding_engine.QUALIFIED_SOURCE_CONTRACT,
                                                  cpt_time_source_contract=CONTRACT)
                        fixture.controlled_source(note)
                        if allowed:
                            self.assertEqual(fixture.assessment()['selection']['code'], '99214')
                        else:
                            with self.assertRaises(ValidationError):
                                fixture.assessment()
                    finally:
                        fixture.doCleanups()

    def test_visit_antecedent_does_not_bind_unrelated_earlier_activities_as_physician_time(self):
        from core.tests.test_coordinated_coding import CoordinatedCPTOutputTests, NOTE
        for marker in ('S - Subjective',
                       'Office E/M selection is based on total physician time on the date of service.'):
            for statement in ('These activities were performed yesterday.',
                              'These activities were performed by staff.'):
                with self.subTest(marker=marker, statement=statement):
                    fixture = CoordinatedCPTOutputTests('test_retained_selected_cpt_number_uses_complete_source_and_keeps_descriptor_limit')
                    fixture.setUp()
                    try:
                        fixture.run.config.update(clinical_source_contract=coding_engine.QUALIFIED_SOURCE_CONTRACT,
                                                  cpt_time_source_contract=CONTRACT)
                        fixture.controlled_source(NOTE.replace(marker, statement+'\r\n'+marker))
                        self.assertEqual(fixture.assessment()['selection']['code'], '99214')
                    finally:
                        fixture.doCleanups()
