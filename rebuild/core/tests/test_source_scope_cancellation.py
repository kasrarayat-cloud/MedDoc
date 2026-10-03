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
