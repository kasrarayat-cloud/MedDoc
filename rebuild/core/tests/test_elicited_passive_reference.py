"""Pointed assertion roles differ from passive document authorship; no sends."""
from django.test import override_settings

from .test_elicited_source_reference import ElicitedSourceReference
from .test_v3_field_relations import offered
from .test_v3_ordinary_notes import LIVE
from core import generation as g


@override_settings(**dict(LIVE, V3_FIELD_RELATIONS=True, V3_HISTORY_CONTEXT=False))
class ElicitedPassiveReference(ElicitedSourceReference):
    def test_passive_denial_and_negative_patient_creation_retract_the_assertion(self):
        for tail in ('That report was denied by the patient.',
                     'That statement was not made by the patient.',
                     'That statement was not made.',
                     'That statement was not true.',
                     'The report was denied by the patient.',
                     'The statement was not made by the patient.',
                     'The statement was not true.'):
            with self.subTest(tail=tail):
                self.assert_held(self.quote+'\n'+tail, self.target, self.quote)

    def test_passive_authorship_access_and_unrelated_truth_do_not_retract_patient_speech(self):
        for tail in ('That report was made by the clinician.',
                     'That report was not made by the clinician.',
                     'That report was prepared by the clinician.',
                     'That report was not prepared by the clinician.',
                     'That report was reviewed by the clinician.',
                     'That report was not reviewed by the clinician.',
                     'That report was read by the patient.',
                     'That report was not read by the patient.',
                     'That report was not denied by the patient.',
                     'That statement was true.',
                     'That statement was not false.',
                     'Another statement was not true.',
                     'That appointment was not made by the patient.',
                     'That appointment was not true.'):
            with self.subTest(tail=tail):
                notes = self.quote+'\n'+tail
                answer = offered(notes,[self.target],{self.target['key']:[self.quote]})[self.target['key']]
                self.assertEqual((answer['status'],answer['text']),('supported',self.quote),answer)
                page=g.as_currently_governed(g.governance_for(notes,[self.target]),notes,{**self.target,**answer})
                self.assertEqual((page['status'],page['text']),('supported',self.quote))
                self.assertEqual(g.governed_decisions(notes,[self.target],{self.target['key']:answer}),[])
