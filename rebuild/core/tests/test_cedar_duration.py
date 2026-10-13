from copy import deepcopy
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from core import semantic_generation as semantic
from core.tests.test_semantic_generation import fact, assignments, checker, FixtureSender
from documents.semantic_preparation_roles import default_definitions

class CedarDurationTests(SimpleTestCase):
    def case(self, notes, value, *, label='Symptom duration', verdict='pass'):
        fields=[{'key':'duration','label':label,'kind':'text','locator':{'cell':0}}]
        definitions=default_definitions(fields)
        definitions['duration'].update(version=2,answer_mode='atomic',meaning='How long the symptom has lasted, as a concise duration.')
        facts=[fact(notes,fields,'duration',value,kind='history')]
        assigned=assignments(fields,{'duration':['duration']})
        checked=checker(assigned,verdicts={'duration':verdict})
        return fields,definitions,facts,assigned,checked

    def run_case(self, notes, value, profile=semantic.DURATION_SCOPE_CONTRACT):
        fields, definitions, facts, assigned, checked=self.case(notes,value)
        sender=FixtureSender(facts,assigned,checked)
        answers=semantic.run(notes,fields,definitions,sender,scope_contract=profile)
        semantic.validate_stored_answer(notes,fields[0],definitions['duration'],answers['duration'])
        self.assertEqual(len(sender.calls),3)
        return answers['duration']

    def test_complete_durations_do_not_inherit_symptom_laterality(self):
        for source,value in [
            ('She describes right knee stiffness that began four days ago.','four days'),
            ('Severe right knee stiffness started four days ago.','four days'),
            ('Right knee stiffness has lasted four days.','four days'),
            ('Right knee stiffness has lasted about four days.','about four days'),
            ('Right knee stiffness has lasted four to six days.','four to six days'),
            ('Right knee stiffness has lasted at least four days.','at least four days'),
            ('She had severe stiffness for four days after surgery.','four days'),
            ('Right knee stiffness has lasted four days since surgery.','four days'),
            ('Right knee stiffness has lasted four days and tenderness persists.','four days'),
            ('Right knee stiffness has lasted four days and one clinician reviewed her.','four days')]:
            with self.subTest(source=source):
                answer=self.run_case(source,value)
                self.assertEqual(answer['status'],'supported',answer['review_reasons'])
                self.assertEqual(answer['text'].casefold(),value)

    def test_temporal_qualifiers_ranges_anchors_and_compounds_are_not_dropped(self):
        for phrase,value in [('about four days','four days'),('at least four days','four days'),
                ('over four days','four days'),('four to six days','six days'),
                ('between four and six days','six days'),('four days or more','four days'),
                ('one week and four days','four days'),('four hours per day','four hours'),
                ('four days and six hours','four days'),
                ('four days to six days','six days'),('four days or so','four days'),
                ('one week plus four days','four days'),('four days ago or so','four days'),('four days ago at most','four days'),
                ('four days ago at least','four days')]:
            with self.subTest(phrase=phrase):
                answer=self.run_case('Right knee stiffness has lasted '+phrase+'.',value)
                self.assertEqual(answer['status'],'conflict')
                self.assertEqual(answer['text'],'')

    def test_onset_offset_is_not_elapsed_duration(self):
        answer=self.run_case('Severe stiffness began four days after surgery.','four days')
        self.assertEqual(answer['status'],'conflict')

    def test_old_profile_keeps_original_hold_and_proof(self):
        notes='She describes right knee stiffness that began four days ago.'
        old=self.run_case(notes,'four days',semantic.POSITIONED_SCOPE_CONTRACT)
        self.assertEqual(old['status'],'conflict')
        self.assertIn('The selected value omits an adjacent documented clinical qualifier.',old['review_reasons'])
        self.assertEqual(self.run_case(notes,'four days')['status'],'supported')

    def test_field_relevant_qualifiers_and_uncertainty_still_hold(self):
        for notes,value in [('Right knee stiffness began four days ago.','knee stiffness'),
                ('Severe knee stiffness began four days ago.','knee stiffness'),
                ('Possible right knee stiffness began four days ago.','four days'),
                ('Her mother describes right knee stiffness for four days.','four days')]:
            with self.subTest(notes=notes):
                self.assertEqual(self.run_case(notes,value)['status'],'conflict')

    def test_checker_prose_cannot_clear_structured_ambiguity(self):
        notes='She describes right knee stiffness that began four days ago.'
        fields, definitions, facts, assigned, checked=self.case(notes,'four days')
        checked['fact_findings']=[{'fact_id':'duration','verdict':'ambiguous','reason':'The duration is correct.'}]
        sender=FixtureSender(facts,assigned,checked)
        answer=semantic.run(notes,fields,definitions,sender,scope_contract=semantic.DURATION_SCOPE_CONTRACT)['duration']
        self.assertEqual(answer['status'],'ambiguous')
        self.assertEqual(len(sender.calls),3)

    def test_structured_repair_cannot_resolve_with_unrelated_ids_or_missing_value(self):
        notes='She describes right knee stiffness that began four days ago.'
        fields,definitions,facts,assigned,checked=self.case(notes,'four days',verdict='omission')
        for repaired,rechecked,raises in [
                ({'fields':[{'key':'duration','fact_ids':['invented'],'status':'supported','separator':''}]},checked,True),
                (assignments(fields),checker(assignments(fields)),False)]:
            sender=FixtureSender(facts,assigned,checked,repaired=repaired,rechecked=rechecked)
            if raises:
                with self.assertRaises(ValidationError):semantic.run(notes,fields,definitions,sender,scope_contract=semantic.DURATION_SCOPE_CONTRACT)
            else:
                answer=semantic.run(notes,fields,definitions,sender,scope_contract=semantic.DURATION_SCOPE_CONTRACT)['duration']
                self.assertEqual(answer['status'],'ambiguous')
