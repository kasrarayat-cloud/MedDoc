"""Documented conditional instructions retain their qualifications.

All wires are simulated, through ordinary-v4 adoption and stored governance.
Physical SOAP upload/finalization/export is exercised separately by the route.
"""
from copy import deepcopy
from django.test import SimpleTestCase, override_settings
from core import generation as g, relations_fixture as fixture, v3_field_relations as r
from .test_v3_supersession_floor import SONNET_55_DEFAULT, form, raw
from .test_v3_field_relations import relation_wire

HEAD='Subjective: cough for two days.\nObjective: lungs clear.\nAssessment: clinician assessed a viral upper respiratory infection.\n'
PLAN='Plan: rest, hydration and review if symptoms worsen.'
NOTES=HEAD+PLAN


def catalogue():
    fields=form('Subjective','Objective','Assessment','Plan')
    for field in fields:
        field['context']='SOAP note > '+field['label']
        if field['label']!='Plan':field['kind']='text'
    return fields


@override_settings(**SONNET_55_DEFAULT)
class ConditionalPlanScope(SimpleTestCase):
    def answers(self,notes,*,fixture_wire=False,picks=None):
        fields=catalogue()
        asked,context,_=g.v3_generation_fields(fields)
        picks=picks if picks is not None else {f['key']:[next(line for line in notes.splitlines()
            if line.startswith(f['label']+':'))] for f in fields}
        body=fixture.body(notes,fields,asked,context) if fixture_wire else relation_wire(notes,fields,picks)
        answers=r.validated(raw(notes,fields,body,g.SONNET_5_5))
        return fields,answers

    def supported(self,notes,**kwargs):
        fields,answers=self.answers(notes,**kwargs)
        gov=g.governance_for(notes,fields)
        for field in fields:
            answer=answers[field['key']]
            source=next(line for line in notes.splitlines() if line.startswith(field['label']+':'))
            self.assertEqual((answer['status'],answer['text']),('supported',source.split(':',1)[1].strip()),(notes,answer))
            self.assertEqual(answer['evidence'],[{'quote':source,'start':notes.index(source),'end':notes.index(source)+len(source)}])
            page=g.as_currently_governed(gov,notes,{**field,**answer})
            self.assertEqual((page['status'],page['text']),('supported',answer['text']))
        self.assertEqual(g.governed_decisions(notes,fields,answers),[])
        return fields,answers

    def test_retained_whole_soap_source_and_all_qualifications_survive(self):
        for fixture_wire in (False,True):
            with self.subTest(fixture_wire=fixture_wire):self.supported(NOTES,fixture_wire=fixture_wire)

    def test_subjectless_imperative_and_coordinated_nominal_instructions(self):
        for value in ['Review if symptoms worsen.','Return if symptoms worsen.',
                      'Review if the patient has chest pain.',
                      'Rest, hydration and review if symptoms worsen.',
                      'rest and return if symptoms worsen.',
                      'rest, hydration and review if symptoms do not improve.']:
            with self.subTest(value=value):self.supported(HEAD+'Plan: '+value)

    def test_assertion_fragment_unknown_actor_and_uncertain_action_keep_holds(self):
        for value in ['physiotherapy if pain persists.',
                      'The patient has cough if symptoms worsen.',
                      'rest and reviewed if symptoms worsen.',
                      'rest and may review if symptoms worsen.',
                      'rest, hydration and review if symptoms might worsen.',
                      'rest, hydration and review if he has chest pain.',
                      'rest, hydration and review if her father has chest pain.',
                      'rest, hydration and review if symptoms worsen?',
                      'rest, hydration and review if those symptoms worsen.',
                      'cough and fever if symptoms worsen.']:
            with self.subTest(value=value):
                notes=HEAD+'Plan: '+value
                fields,answers=self.answers(notes)
                answer=answers['f4']
                self.assertEqual((answer['status'],answer['text']),('conflict',''),(notes,answer))
                stored={**answer,'status':'supported','text':value}
                self.assertIn('Plan',g.governed_decisions(notes,fields,{'f4':stored}))

    def test_hypothetical_or_correction_heading_cannot_be_localized_to_plan(self):
        for prefix in ['Hypothetical case for teaching.\n','If symptoms recur:\n',
                       'Correction: these findings were for her father.\n']:
            with self.subTest(prefix=prefix):
                notes=prefix+NOTES
                _,answers=self.answers(notes)
                for answer in answers.values():self.assertEqual((answer['status'],answer['text']),('conflict',''))

    def test_conditional_plan_does_not_remove_a_contradiction_to_an_earlier_fact(self):
        notes=NOTES+'\nThe patient denies cough.'
        fields,answers=self.answers(notes)
        answer=answers['f1']
        self.assertEqual((answer['status'],answer['text']),('conflict',''),answer)
        stored={**answer,'status':'supported','text':'cough for two days.'}
        self.assertIn('Subjective',g.governed_decisions(notes,fields,{'f1':stored}))

    def test_stored_answer_cannot_drop_the_condition_or_select_a_partial_source(self):
        fields,answers=self.supported(NOTES)
        truncated=deepcopy(answers['f4']);truncated['text']='rest, hydration and review.'
        gov=g.governance_for(NOTES,fields)
        page=g.as_currently_governed(gov,NOTES,{**fields[3],**truncated})
        self.assertEqual((page['status'],page['text']),('conflict',''))
        self.assertEqual(g.governed_decisions(NOTES,fields,{'f4':truncated}),['Plan'])
        partial=deepcopy(answers['f4']);quote='Plan: rest, hydration and review'
        partial['evidence']=[{'quote':quote,'start':NOTES.index(quote),'end':NOTES.index(quote)+len(quote)}]
        self.assertEqual(g.governed_decisions(NOTES,fields,{'f4':partial}),['Plan'])
