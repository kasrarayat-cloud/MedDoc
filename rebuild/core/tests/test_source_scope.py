"""Narrow transition dependencies through the real v4 selections and stored governance."""
from unittest.mock import patch
from django.test import SimpleTestCase, override_settings
from .test_v3_supersession_floor import Worst, SONNET_55_DEFAULT, WARFARIN


@override_settings(**SONNET_55_DEFAULT)
class TransitionScope(Worst, SimpleTestCase):
    model = 'claude-sonnet-5-5'
    def test_complete_positional_change_cannot_end_an_unrelated_medication(self):
        for tail in ['The patient switched to the supine position.', 'Switched to the supine position.',
                     'The patient changed to the prone position.']:
            with self.subTest(tail=tail):
                notes = WARFARIN+' '+tail
                with patch('core.source_scope.bare_affects', return_value=True):
                    self.assert_held(notes, ('Medications','Plan'), 'Medications', WARFARIN)
                self.assert_adopted(notes, ('Medications','Plan'), 'Medications', WARFARIN)

    def test_elided_medication_source_and_actual_treatment_dependencies_stay_held(self):
        for tail in ['She was switched to apixaban.', 'Switched to apixaban.',
                     'The patient was changed to apixaban.', 'Withheld today.',
                     'Haematology reviewed and stopped.', 'Her INR was checked and stopped.',
                     'The patient switched to the supine position and stopped.']:
            with self.subTest(tail=tail):
                self.assert_held(WARFARIN+' '+tail, ('Medications','Plan'), 'Medications', WARFARIN)

    def test_named_source_target_and_time_are_distinct(self):
        for change in ['The patient was switched from warfarin to apixaban.',
                       'Warfarin was replaced by apixaban last month.',
                       'Apixaban replaces warfarin.', 'Apixaban was substituted for warfarin.']:
            with self.subTest(change=change):
                self.assert_held(WARFARIN+' '+change, ('Medications','Plan'), 'Medications', WARFARIN)
                self.assert_adopted('The patient takes apixaban 5 mg twice daily. '+change,
                    ('Medications','Plan'), 'Medications', 'The patient takes apixaban 5 mg twice daily.')

    def test_unrelated_known_patient_topic_does_not_depend_on_elided_medication(self):
        source = 'The patient reports cough.'
        tail = 'She was switched to apixaban.'
        with patch('core.source_scope.bare_affects', return_value=True):
            self.assert_held(source+' '+tail, ('Symptoms','Medications'), 'Symptoms', source)
        self.assert_adopted(source+' '+tail, ('Symptoms','Medications'), 'Symptoms', source)
        # The dependency appears in the answer itself; it must stay held even
        # when the printed destination asks about a symptom instead of a drug.
        source = 'The patient reports cough while taking warfarin.'
        self.assert_held(source+' '+tail, ('Symptoms','Medications'), 'Symptoms', source)

    def test_no_release_of_stopped_held_withheld_replaced_or_family_medication(self):
        for tail in ['Warfarin stopped.', 'Warfarin is on hold for surgery.', 'Warfarin was withheld today.',
                     'Warfarin was replaced by apixaban.', 'The patient stopped warfarin last year.',
                     'The patient may stop warfarin tomorrow.']:
            with self.subTest(tail=tail):
                self.assert_held(WARFARIN+' '+tail, ('Medications','Plan'), 'Medications', WARFARIN)
        source = 'Her father takes warfarin 5 mg daily.'
        self.assert_held(source+' The patient switched to the supine position.',
                         ('Medications','Plan'), 'Medications', source)

    def test_replacement_target_requires_its_own_current_patient_claim(self):
        change='The patient was switched from warfarin to apixaban.'
        for source in ['The patient previously took apixaban last year.',
                       'The patient may take apixaban tomorrow.',
                       'Her mother takes apixaban 5 mg twice daily.']:
            with self.subTest(source=source):
                self.assert_held(source+' '+change, ('Medications','Plan'), 'Medications', source)
        source='The patient takes apixaban 5 mg twice daily.'
        for denial in ['Apixaban was stopped.', 'Apixaban was withheld today.', 'Apixaban is on hold for surgery.',
                       'The patient takes no apixaban.']:
            with self.subTest(denial=denial):
                self.assert_held(source+' '+change+' '+denial, ('Medications','Plan'), 'Medications', source)
        self.assert_adopted(source+' '+change, ('Medications','Plan'), 'Medications', source)

    def test_non_medication_uses_of_change_words_do_not_change_drug_status(self):
        for source in ['The patient held her breath.', 'The light was switched on.',
                       'Dressing changed daily.', 'There is no change in symptoms.']:
            with self.subTest(source=source):
                self.assert_adopted(WARFARIN+' '+source, ('Medications','Plan'), 'Medications', WARFARIN)

    def test_named_positional_source_and_target_are_not_a_medication_change(self):
        for tail in ['The patient switched from prone to supine positioning.',
                     'The patient switched from a prone position to a supine position.',
                     'The patient changed from upright to lateral positioning.']:
            with self.subTest(tail=tail):
                # Only the independently demonstrated first shape reaches the
                # additional bare-event floor. Other full position phrases
                # were already independent; do not manufacture a mutation
                # failure for a guard that their source never enters.
                if tail=='The patient switched from prone to supine positioning.':
                    with patch('core.source_scope.bare_affects',return_value=True):
                        self.assert_held(WARFARIN+' '+tail,('Medications','Plan'),'Medications',WARFARIN)
                self.assert_adopted(WARFARIN+' '+tail,('Medications','Plan'),'Medications',WARFARIN)
        for tail in ['The patient switched from warfarin to supine positioning.',
                     'The patient switched from an UNKNOWN medication to supine positioning.',
                     'The patient switched from prone to supine positioning and stopped.']:
            with self.subTest(tail=tail):self.assert_held(WARFARIN+' '+tail,('Medications','Plan'),'Medications',WARFARIN)
