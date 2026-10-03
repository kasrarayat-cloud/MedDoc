"""Retained reserved-author name metadata never becomes a clinical actor.

Model responses are simulated. Physical role admission is separately exercised
by the Word workflow; these controls use its retained protected catalogue.
"""
from copy import deepcopy
from django.test import SimpleTestCase, override_settings
from core import generation as g, relations_fixture as fixture, v3_field_relations as r
from .test_v3_supersession_floor import SONNET_55_DEFAULT, form, raw
from .test_v3_field_relations import relation_wire
from .test_transcript_context import proof

CAPTION='This section is for the line manager to add comments'
SOURCE=CAPTION+': Dr Note Person'
NOTES=SOURCE+'\nPlan: Rest.'


def catalogue():
    fields=form(CAPTION,'Plan')
    fields[0].update(context=CAPTION,write_protected=True,
        review_reason="This answer area is reserved for another author's comments. Ordinary clinician notes do not establish that author's statement; complete it through the explicit human workflow.")
    fields[1]['context']='Plan'
    return fields


@override_settings(**SONNET_55_DEFAULT)
class ReservedSourceContext(SimpleTestCase):
    def check(self,notes,*,fields=None,selected='Plan: Rest.',fixture_wire=False,confirmed=False,expected='supported'):
        fields=catalogue() if fields is None else deepcopy(fields)
        asked,context,_=g.v3_generation_fields(fields)
        body=(fixture.body(notes,fields,asked,context) if fixture_wire else
              relation_wire(notes,fields,{'f2':[selected]}))
        result=raw(notes,fields,body,g.SONNET_5_5)
        if confirmed:result['patient_default_context']=proof(notes)
        answers=r.validated(result);answer=answers['f2']
        self.assertEqual(answer['status'],expected,(notes,body,answer))
        governance=g.governance_for(notes,fields)
        page=g.as_currently_governed(governance,notes,{**fields[1],**answer})
        self.assertEqual(page['status'],expected)
        self.assertEqual(answers['f1']['text'],'')
        if expected=='supported':
            self.assertEqual(answer['text'],selected.split(':',1)[1].strip())
            self.assertEqual(answer['evidence'],[{'quote':selected,'start':notes.index(selected),
                                                'end':notes.index(selected)+len(selected)}])
            self.assertEqual(g.governed_decisions(notes,fields,answers),[])
        else:
            self.assertEqual(answer['text'],'')
            stale={**answer,'status':'supported','text':selected.split(':',1)[1].strip() if ':' in selected else selected}
            self.assertEqual(g.governed_decisions(notes,fields,{'f2':stale}),[fields[1]['label']])
        return body,answers

    def test_actual_manager_source_keeps_plan_on_fixture_and_worst_independent_wire(self):
        for fixture_wire in (False,True):
            for confirmed in (False,True):
                with self.subTest(fixture_wire=fixture_wire,confirmed=confirmed):
                    body,answers=self.check(NOTES,fixture_wire=fixture_wire,confirmed=confirmed)
                    self.assertEqual(body['fields'][0]['context']['independent'],[1])
                    self.assertEqual(answers['f1']['status'],'missing')

    def test_name_metadata_is_not_specific_to_manager_or_one_title(self):
        for label,kind,protected,name in [(CAPTION,'long_text',True,'Mrs Synthetic'),
                ('Clinician signature','signature',False,'Dr Note Person'),
                ('Witness signature','signature',False,'Mr Synthetic')]:
            with self.subTest(label=label,name=name):
                fields=catalogue();fields[0].update(label=label,kind=kind,write_protected=protected)
                self.check(label+': '+name+'\nPlan: Rest.',fields=fields)

    def test_actual_clinical_statement_or_correction_cannot_use_name_boundary(self):
        for value in ['Dr Note Person takes warfarin.', 'Dr Note Person has asthma.',
                      'Dr Note Person. Correction: do not rest.',
                      'Dr Note Person with left knee pain', 'Dr Note Person may have asthma.']:
            with self.subTest(value=value):
                self.check(CAPTION+': '+value+'\nPlan: Rest.',expected='conflict')

    def test_boundary_never_establishes_an_unlabelled_or_pronoun_answer(self):
        for selected in ['She will rest.','He will rest.','They will rest.']:
            with self.subTest(selected=selected):
                self.check(SOURCE+'\n'+selected,selected=selected,expected='conflict')

    def test_unprotected_author_source_keeps_the_existing_attribution_hold(self):
        fields=catalogue();fields[0].pop('write_protected');fields[0].pop('review_reason')
        self.check(NOTES,fields=fields,expected='conflict')

    def test_prior_family_source_is_not_erased_by_a_later_reserved_name(self):
        self.check('Her father has asthma.\n'+NOTES,expected='conflict')

    def test_duplicate_context_labels_remain_unresolved_in_the_fixture(self):
        fields=catalogue();duplicate=deepcopy(fields[0]);duplicate['key']='f3';fields.append(duplicate)
        asked,context,_=g.v3_generation_fields(fields)
        body=fixture.body(NOTES,fields,asked,context)
        self.assertEqual(body['fields'][0]['context']['unresolved'],[1])

    def test_printed_label_never_resolves_a_personal_pronoun_after_the_named_author(self):
        for selected in ['Plan: She will rest.','Plan: He will rest.','Plan: They will rest.']:
            for confirmed in (False,True):
                with self.subTest(selected=selected,confirmed=confirmed):
                    self.check(SOURCE+'\n'+selected,selected=selected,confirmed=confirmed,expected='conflict')

    def test_prior_named_clinical_actor_family_and_speaker_context_remain_governing(self):
        for prefix in ['Dr John Smith has asthma.\n','Her father has asthma.\n','Manager: I will rest.\n']:
            for confirmed in (False,True):
                with self.subTest(prefix=prefix,confirmed=confirmed):
                    selected='Plan: She will rest.'
                    self.check(prefix+SOURCE+'\n'+selected,selected=selected,confirmed=confirmed,expected='conflict')

    def test_an_explicit_patient_source_does_not_need_an_invented_pronoun_resolution(self):
        selected='Plan: The patient will rest.'
        self.check(SOURCE+'\n'+selected,selected=selected)
