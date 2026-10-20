"""Prospective shared source scope and complete coding predicates, no IO."""
from copy import deepcopy
from django.test import SimpleTestCase
from core import coding_engine as engine, corti_coding, coding_completeness as completeness
from core.coding_source_assertions import nonassertion_frame
from core.tests import test_coding_qualified_assertions as qualified


class SharedCodingSourceTests(SimpleTestCase):
    def setUp(self):
        self.boundary = qualified.QualifiedAssertionTests()
        self.boundary.setUp()
        self.prefix = 'Patient: Synthetic Ellis Vale\nSubjective:\n'

    def route(self, note, quote, code='R12', *, contract=engine.SHARED_SOURCE_CONTRACT):
        return self.boundary.route(note, code, quote=quote, contract=contract)

    def test_preposed_duration_and_complete_sensation_description_keep_current_presence(self):
        for quote in ('For five weeks she has noticed heartburn, described as burning behind the breastbone without radiation.',
                      'For three days he has experienced heartburn, described as pressure in the chest without spread.',
                      'She reports heartburn, described as burning behind the sternum without radiation.'):
            notes = self.prefix + quote
            with self.subTest(quote=quote):
                self.assertIsNotNone(self.route(notes, quote)[1])
                self.assertIsNone(self.route(notes, quote, contract=engine.QUALIFIED_SOURCE_CONTRACT)[1])

    def test_unknown_description_qualification_is_not_consumed_as_affirmative(self):
        base = 'For five weeks she has noticed heartburn, described as burning behind the breastbone'
        for tail in (' according to an unverified report.', ' in a hypothetical example.',
                     ' but this was recorded in error.', ' for another patient.',
                     ' that may concern her mother.', ' without any diagnosis being established.'):
            quote = base + tail
            with self.subTest(tail=tail):
                self.assertIsNone(self.route(self.prefix + quote, quote)[1])

    def test_current_assessment_and_explicit_no_diagnosis_subtypes_preserve_default_route(self):
        quote = 'Constipation started nine days ago, on 11 October 2026.'
        notes = (self.prefix + quote + '\nAssessment:\n'
            'Heartburn and constipation were both evaluated today.\n'
            'Constipation is unspecified: neither its cause nor a constipation subtype has been established.\n'
            'No diagnosis of slow-transit constipation, outlet dysfunction or irritable bowel syndrome was made today.')
        self.assertIsNotNone(self.route(notes, quote, 'K59.00')[1])
        self.assertIsNone(self.route(notes, quote, 'K59.01')[1])

    def test_negation_uncertainty_foreign_history_and_real_retraction_stay_blocked(self):
        quote = 'She reports heartburn, described as burning behind the breastbone without radiation.'
        for heading in ('Mother:', 'Previous encounter:', 'Unverified report:'):
            with self.subTest(heading=heading):
                self.assertIsNone(self.route(self.prefix+heading+'\n'+quote, quote)[1])
        for extra in ('The patient denies heartburn today.',
                      'The heartburn was recorded in error.',
                      'The whole clinical note belongs to another patient.',
                      'Heartburn is a possible diagnosis, not an established condition.'):
            with self.subTest(extra=extra):
                self.assertIsNone(self.route(self.prefix+quote+'\n'+extra, quote)[1])

    def test_unknown_cause_is_distinct_from_unknown_presence_and_causal_disease(self):
        quote = 'She reports heartburn, described as burning behind the breastbone without radiation.'
        concept = {'id':'finding', 'term':'heartburn', 'index_terms':['heartburn'], 'evidence':quote,
            'kind':'symptom', 'certainty':'confirmed', 'temporality':'current', 'subject':'patient',
            'relevant':True, 'missing_detail':'', 'integral_to':''}
        row = {'eligible':True, 'concept':deepcopy(concept)}
        note = self.prefix+quote+'\nAssessment:\nThe cause of the heartburn is uncertain.'
        self.assertEqual(corti_coding.integral_holds([row], note, source_contract=engine.SHARED_SOURCE_CONTRACT), {})
        self.assertTrue(corti_coding.integral_holds([row], note, source_contract=engine.QUALIFIED_SOURCE_CONTRACT))
        for tail in ('Reflux causes heartburn.', 'Heartburn is due to reflux.'):
            self.assertTrue(corti_coding.integral_holds([row], self.prefix+quote+'\nAssessment:\n'+tail,
                source_contract=engine.SHARED_SOURCE_CONTRACT))

    def test_affirmative_specific_subtype_cannot_be_erased_by_default_code(self):
        quote = 'The patient reports constipation today.'
        notes = self.prefix+quote+'\nAssessment:\nThe patient has slow transit constipation today.'
        self.assertIsNone(self.route(notes, quote, 'K59.00')[1])

    def test_evaluation_of_options_prevention_and_possible_objects_never_establishes_presence(self):
        for quote in ('Treatment options for heartburn were evaluated today.',
                      'Potential heartburn was evaluated today.',
                      'Prevention of heartburn was addressed today.',
                      'Heartburn prevention was evaluated today.',
                      'Education about heartburn was assessed today.'):
            for timing in ('today', 'at this encounter', 'during this encounter'):
                text = quote.replace('today', timing)
                with self.subTest(quote=text):
                    self.assertIsNone(self.route('Patient: Synthetic Ellis Vale\nAssessment:\n'+text, text)[1])

    def test_modal_presence_and_diagnosis_qualify_a_separate_current_report(self):
        quote = 'The patient reports heartburn today.'
        for qualifier in ('Heartburn could be present.', 'Heartburn may be a diagnosis.',
                          'Heartburn might not be present.', 'Potential heartburn was evaluated today.'):
            with self.subTest(qualifier=qualifier):
                self.assertIsNone(self.route(self.prefix+quote+'\nAssessment:\n'+qualifier, quote)[1])
        # Treatment and severity modality do not question the finding's presence.
        for attribute in ('Heartburn may be treated with medication.', 'Heartburn could be severe.'):
            with self.subTest(attribute=attribute):
                self.assertIsNotNone(self.route(self.prefix+quote+'\nAssessment:\n'+attribute, quote)[1])

    def test_complete_no_code_frames_preserve_objects_and_never_silently_consume_tails(self):
        samples = (
            ('Gastroesophageal reflux disease is a possibility, but it has not been established.', 'unestablished_diagnosis'),
            ('Anemia is a possibility but is not confirmed.', 'unestablished_diagnosis'),
            ('No diagnosis of slow-transit constipation, outlet dysfunction or irritable bowel syndrome was made today.', 'negative_diagnosis'),
            ('No diagnosis of pneumonia or bronchitis is established at this encounter.', 'negative_diagnosis'),
            ('Constipation is unspecified: neither its cause nor a constipation subtype has been established.', 'unspecified_attributes'),
            ('Pain is unspecified: neither its site nor a severity has been established.', 'unspecified_attributes'),
            ('The bowel change and the heartburn are separate concerns.', 'distinct_concerns'),
            ('Nausea and dizziness are separate symptoms.', 'distinct_concerns'),
            ('She has a history of seasonal allergies, currently inactive; that condition was not evaluated or treated at this visit.', 'inactive_unevaluated_history'),
        )
        for text, kind in samples:
            with self.subTest(text=text):
                frame = nonassertion_frame(text)
                self.assertEqual(frame['kind'], kind)
                self.assertTrue(frame['objects'])
                inv = completeness.inventory(self.prefix+'Assessment:\n'+text,
                    source_contract=engine.SHARED_SOURCE_CONTRACT)
                self.assertEqual(inv['items'], [])
                self.assertTrue(any(row.get('assertion_frame') == frame for row in inv['unresolved']))
                for suffix in (' for another patient.', ' unless symptoms recur.', ' and the patient has pneumonia.'):
                    self.assertIsNone(nonassertion_frame(text.rstrip('.')+suffix))

    def test_attribute_and_distinction_frames_do_not_veto_independent_current_condition(self):
        quote = 'The patient reports heartburn today.'
        concept = self.boundary.symptom()
        for extra in ('Heartburn is unspecified: neither its cause nor a heartburn subtype has been established.',
                      'Nausea and the heartburn are separate concerns.'):
            notes = self.prefix+quote+'\nAssessment:\nHeartburn was evaluated today.\n'+extra
            inv = completeness.inventory(notes, source_contract=engine.SHARED_SOURCE_CONTRACT)
            with self.subTest(extra=extra):
                self.assertEqual(completeness._condition_reference_errors(notes, concept, 'Heartburn',
                    self.boundary.reference, inv['unresolved'], source_contract=engine.SHARED_SOURCE_CONTRACT,
                    evaluated_names=['Heartburn']), [])

    def test_condition_subject_corrections_preserve_foreign_origin_and_never_presence(self):
        quote = 'The patient reports heartburn today.'
        corrections = ('Heartburn has never been present.', 'Heartburn was never present.',
            'Heartburn was recorded for another patient.',
            'Heartburn was documented for the patient’s mother.',
            "Heartburn was copied from her mother's note.", 'The reported heartburn is fabricated.',
            'Heartburn is a hypothetical example.', 'Heartburn remains to be confirmed.',
            'Heartburn has yet to be established.', 'Heartburn is a tentative diagnosis.',
            'Heartburn is a questionable diagnosis.')
        for correction in corrections:
            with self.subTest(correction=correction):
                self.assertIsNone(self.route(self.prefix+quote+' '+correction,quote)[1])
                self.assertIsNone(self.route(self.prefix+quote+'\n'+correction,quote)[1])
        for foreign in ('Mother:\nHeartburn has never been present.',
                        'Previous encounter:\nHeartburn was recorded for another patient.',
                        "Her mother's heartburn was copied from another patient's note."):
            with self.subTest(foreign=foreign):
                self.assertIsNotNone(self.route(self.prefix+quote+'\n'+foreign,quote)[1])

    def test_unrecognized_current_condition_predicate_is_a_scoped_hold(self):
        quote = 'The patient reports heartburn today.'
        for extra in ('Heartburn carries an unresolved attribution.',
                      'The reported heartburn concerns the clinic’s training scenario.',
                      'Heartburn was transcribed for the neighbour.',
                      'Heartburn has a qualification requiring clarification.'):
            with self.subTest(extra=extra):
                self.assertIsNone(self.route(self.prefix+quote+'\n'+extra,quote)[1])
        # An unrelated unknown condition cannot impose a whole-note hold.
        notes = self.prefix+quote+'\nA rash carries an unresolved attribution.'
        self.assertIsNotNone(self.route(notes,quote)[1])

    def test_complete_timing_attributes_require_consistent_dates_and_do_not_assert_presence(self):
        quote = 'The patient reports constipation today.'
        prefix = 'Patient: Synthetic Ellis Vale\nDate of service: 20 October 2026\nSubjective:\n'
        onset = 'Constipation started nine days ago, on 11 October 2026.'
        self.assertIsNotNone(self.route(prefix+quote+' '+onset,quote,'K59.00')[1])
        self.assertIsNone(self.route(prefix+onset,onset,'K59.00')[1])
        for changed in ('Constipation started nine days ago, on 12 October 2026.',
                        'Constipation started on 21 October 2026.',
                        'Constipation started nine days ago, on 31 February 2026.',
                        onset.rstrip('.')+' unless the history is incorrect.'):
            with self.subTest(changed=changed):
                self.assertIsNone(self.route(prefix+quote+' '+changed,quote,'K59.00')[1])

    def test_current_patient_reporting_envelope_keeps_embedded_correction_scope(self):
        quote = 'The patient reports heartburn today.'
        for correction in ('She says heartburn was documented for her mother.',
                           'She states the heartburn is fabricated.',
                           'She reports that heartburn was recorded for another patient.',
                           'Synthetic Ellis Vale states that heartburn has an unresolved attribution.',
                           'She says that she states heartburn is fabricated.'):
            with self.subTest(correction=correction):
                self.assertIsNone(self.route(self.prefix+quote+' '+correction,quote)[1])
        for other in ('She says her mother’s heartburn is fabricated.',
                      'Mother:\nShe states heartburn is fabricated.',
                      'Previous encounter:\nShe says heartburn was documented for her mother.'):
            with self.subTest(other=other):
                self.assertIsNotNone(self.route(self.prefix+quote+'\n'+other,quote)[1])
        self.assertIsNotNone(self.route(self.prefix+quote+' She states heartburn is present.',quote)[1])
