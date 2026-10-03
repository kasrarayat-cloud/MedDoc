"""Retained cessation false holds paired with unsafe patient/actor controls.

Synthetic model selections are deliberately adverse: all unselected source
units are called independent. These are source-governance checks, not model
accuracy or audio acceptance.
"""
from django.test import SimpleTestCase, override_settings

from . import test_transcript_context
from .test_v3_supersession_floor import SONNET_55_DEFAULT


@override_settings(**SONNET_55_DEFAULT)
class CancellationScope(SimpleTestCase):
    answers = test_transcript_context.PatientDefault.answers
    check = test_transcript_context.PatientDefault.check
    source = 'Takes warfarin 5 mg daily.'
    prefix = 'Her father switched from prone to supine positioning and '

    def test_complete_passive_group_keeps_recipient_and_cancellation(self):
        for label in ['Medications', 'Current medications']:
            for tail in [
                'warfarin and apixaban were withheld from her father.',
                'warfarin and apixaban were never withheld from the patient.',
                'apixaban and warfarin were not withheld from the patient.',
            ]:
                with self.subTest(label=label, tail=tail):
                    self.check(self.source+' '+self.prefix+tail, label, [self.source])
            for tail in [
                'warfarin and apixaban were withheld from the patient.',
                'warfarin and apixaban were withheld from her father and the patient.',
                'warfarin and apixaban were withheld from someone.',
                'warfarin but not apixaban was withheld from the patient.',
                # This parser cannot establish the complete alternative theme.
                # Cancellation/foreign-recipient counterparts remain explicit
                # conservative holds, not demonstrated unsafe contradictions.
                'warfarin but not apixaban was not withheld from the patient.',
                'warfarin but not apixaban was withheld from her father.',
                'an unknown item and apixaban were withheld from the patient.',
                'warfarin and apixaban were not withheld from her father but the patient stopped warfarin.',
            ]:
                with self.subTest(label=label, tail=tail):
                    self.check(self.source+' '+self.prefix+tail, label, [self.source], 'conflict')

    def test_denied_completed_cessation_is_not_denied_medication_use(self):
        for label in ['Medications', 'Current medications']:
            for tail in [
                'The patient denies having stopped warfarin after her father switched from prone to supine positioning.',
                'The patient denies having stopped warfarin.',
                'The patient denies stopping warfarin.',
            ]:
                with self.subTest(label=label, tail=tail):
                    self.check(self.source+' '+tail, label, [self.source])
            for tail in [
                'The patient denies taking warfarin.',
                'The patient denies having taken warfarin.',
                'The patient denies not having stopped warfarin.',
                'The patient may deny having stopped warfarin.',
                'The patient denies having stopped warfarin but warfarin was withheld from the patient.',
                'The patient denies having stopped warfarin and the patient no longer takes warfarin.',
            ]:
                with self.subTest(label=label, tail=tail):
                    self.check(self.source+' '+tail, label, [self.source], 'conflict')

    def test_source_replacement_context_and_family_controls_remain_binding(self):
        target = 'The patient takes apixaban 5 mg twice daily.'
        change = 'The patient switched from an unknown medication to apixaban.'
        for label in ['Medications', 'Current medications']:
            self.check(target+' '+change, label, [target])
            self.check(self.source+' '+change, label, [self.source], 'conflict')
            self.check(target+' '+change+' Apixaban was stopped.', label, [target], 'conflict')
            family = 'Her father takes apixaban 5 mg twice daily.'
            self.check(family+' '+change, label, [family], 'conflict')
            self.check(self.source+' The patient switched to the supine position.', label, [self.source])
        symptom = 'The patient reports cough.'
        self.check(symptom+' The patient switched from an unknown medication to apixaban.', 'Symptoms', [symptom])

    def test_unproved_possessive_and_beneficiary_roles_stay_held(self):
        for tail in ['his warfarin was withheld.', 'warfarin was stopped for her mother.']:
            self.check(self.source+' '+self.prefix+tail, 'Medications', [self.source], 'conflict')
        # Confirmation binds the current reviewed bytes; it cannot resolve an
        # explicit other person, an uncertain actor or a later contradictory act.
        self.check('Her father takes warfarin 5 mg daily.', 'Medications',
                   ['Her father takes warfarin 5 mg daily.'], 'conflict')

    def test_explicit_replacement_relation_binds_old_value_and_actual_recipient(self):
        change = 'For the patient, apixaban 5 mg twice daily was started in place of warfarin last week.'
        target = 'The patient takes apixaban 5 mg twice daily.'
        for label in ['Medications', 'Current medications']:
            self.check(self.source+' '+change, label, [self.source], 'conflict')
            self.check(target+' '+change, label, [target])
            self.check(target+' '+change+' Apixaban was stopped.', label, [target], 'conflict')
            self.check(change, label, [change], 'conflict')
            for invalid in ['Her father takes apixaban 5 mg twice daily.',
                            'The patient previously took apixaban last year.',
                            'The patient may take apixaban tomorrow.']:
                with self.subTest(label=label, invalid=invalid):
                    self.check(invalid+' '+change, label, [invalid], 'conflict')
            for safe in [
                'For her father, apixaban 5 mg twice daily was started in place of warfarin last week.',
                'For the patient, apixaban 5 mg twice daily was not started in place of warfarin last week.',
                'For the patient, apixaban 5 mg twice daily was never started in place of warfarin.',
                'For the patient, apixaban 5 mg twice daily may be started in place of warfarin tomorrow.',
                'For the patient, apixaban 5 mg twice daily will be started in place of warfarin tomorrow.',
            ]:
                with self.subTest(label=label, safe=safe):
                    self.check(self.source+' '+safe, label, [self.source])
            for unsafe in [
                'For someone, apixaban was started in place of warfarin.',
                'For the patient, apixaban might have been started in place of warfarin last week.',
                'For her father and the patient, apixaban was started in place of warfarin.',
                "For her father, apixaban was started in place of the patient's warfarin.",
                'For the patient, apixaban was started in place of warfarin, not merely proposed.',
            ]:
                with self.subTest(label=label, unsafe=unsafe):
                    self.check(self.source+' '+unsafe, label, [self.source], 'conflict')

    def test_possible_future_cessation_does_not_become_completed_cessation(self):
        for label in ['Medications', 'Current medications']:
            self.check(self.source+" The patient might stop warfarin after next week's procedure.", label, [self.source])
            for tail in ['The patient might have stopped warfarin.',
                         'The patient might stop warfarin tomorrow. Warfarin was withheld today.']:
                self.check(self.source+' '+tail, label, [self.source], 'conflict')

    def test_complete_position_and_separate_medication_clause_do_not_erase_exam(self):
        exam = 'Examination mild swelling over the left lateral ankle.'
        position = 'The patient switched to the supine position for an ECG; she continues warfarin.'
        self.check(exam+' '+position, 'Examination', [exam])
        self.check(exam+' '+position+' The patient denies swelling over the left ankle.',
                   'Examination', [exam], 'conflict')
        dependent = 'The patient reports cough while taking warfarin.'
        self.check(dependent+' '+position, 'Symptoms', [dependent], 'conflict')

    def test_completed_restart_and_present_use_supersede_only_dated_earlier_stop(self):
        old = 'Warfarin was stopped last month.'
        current = 'The patient has restarted warfarin 5 mg daily and takes it now.'
        for label in ['Medications', 'Current medications']:
            self.check(old+' '+current, label, [current])
            self.check(old+' '+current+' Warfarin was withheld today.', label, [current], 'conflict')
            for unbounded_old in ['Warfarin was stopped last month and withheld today.',
                                  'Warfarin was stopped for her father last month.']:
                self.check(unbounded_old+' '+current,label,[current],'conflict')
            for invalid in ['The patient may restart warfarin tomorrow.',
                            'The patient has restarted warfarin 5 mg daily.',
                            'Her father has restarted warfarin 5 mg daily and takes it now.',
                            'The patient has not restarted warfarin 5 mg daily and takes it now.',
                            'The patient has restarted warfarin with apixaban and takes it now.',
                            'The patient has restarted apixaban and takes it now.']:
                # The different replacement has no evidence that warfarin is
                # current; selecting the original current-warfarin sentence
                # must still hold. Other controls select the proposed restart.
                if 'apixaban' in invalid:
                    self.check(self.source+' '+old+' '+invalid, label, [self.source], 'conflict')
                else:self.check(old+' '+invalid, label, [invalid], 'conflict')
