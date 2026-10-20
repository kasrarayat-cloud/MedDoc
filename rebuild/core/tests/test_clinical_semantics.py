"""General source-scope, field-meaning and narrative-preservation boundaries."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from core import generation, semantic_generation as semantic
from core import clinical_semantics as model
from core.tests.test_semantic_generation import fact, assignments, FixtureSender
from documents.semantic_preparation_roles import default_definitions


class ClinicalSemanticsTests(SimpleTestCase):
    header = 'Patient: Synthetic Ada Tern\nDate of service: 21 October 2027\nTreating clinician: Dr. Mira Cole\n'
    profile = semantic.CLINICAL_SEMANTICS_SCOPE_CONTRACT

    def values(self, body, specs, *, profile=None):
        notes = self.header + body
        units, _ = generation.source_units(notes, [])
        raw = [fact(notes, [], key, quote, kind=kind, polarity=polarity, timing=timing)
            for key, quote, kind, polarity, timing in specs]
        before = deepcopy(raw)
        validated = semantic.validate_facts(notes, units, {'facts': raw},
            scope_contract=profile or self.profile,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)
        self.assertEqual(raw, before)
        return notes, units, validated

    def definition(self, meaning, *, timing='any', polarity='any'):
        fields = [{'key':'answer','label':'Arbitrary label','kind':'text','locator':{'cell':0}}]
        definitions = default_definitions(fields)
        definitions['answer'].update(version=2, answer_mode='narrative', meaning=meaning,
            scope={'subject':'patient','temporality':timing,'polarity':polarity})
        return fields, definitions

    def assign(self, notes, facts, meaning, ids, **kwargs):
        fields, definitions = self.definition(meaning, **kwargs)
        return semantic._assign(notes, fields, definitions, facts, assignments(fields, {'answer':ids}),
            scope_contract=self.profile, timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)['answer']

    def test_account_object_reference_does_not_retract_symptom_or_physician_time(self):
        finding = 'She reports wrist pain lasting approximately 12 minutes'
        total = 'Dr. Cole spent 27 minutes on 21 October 2027: examining and counseling the patient'
        for statement in ('These episode lengths describe the symptom, not the time spent at this visit.',
                'These symptom durations do not represent encounter time.',
                'Four minutes of staff intake are outside that total.'):
            with self.subTest(statement=statement):
                _, _, facts = self.values('S\n'+finding+'. '+statement+'\nP\n'+total+'.',
                    [('pain',finding,'history','affirmed','current'),('total',total,'other','affirmed','current')])
                self.assertTrue(all(not row['issues'] for row in facts.values()), facts)

    def test_unknown_condition_is_local_and_not_a_current_assertion(self):
        finding = 'She reports wrist pain'
        conditional = 'If she develops fever, an infection is possible'
        _, _, facts = self.values('S\n'+finding+'. '+conditional+'.',
            [('pain',finding,'history','affirmed','current'),('fever','fever','finding','affirmed','current')])
        self.assertFalse(facts['pain']['issues'])
        self.assertTrue(facts['fever']['issues'])

    def test_conditional_instruction_preserves_whole_condition_and_future_action(self):
        finding = 'She reports wrist pain'
        instruction = 'If pain worsens, or she notices swelling, she should contact the clinic before the scheduled review'
        notes, _, facts = self.values('S\n'+finding+'.\nP\n'+instruction+'.',
            [('pain',finding,'history','affirmed','current'),('plan',instruction,'follow_up','affirmed','future'),
             ('false_finding','swelling','finding','affirmed','current')])
        self.assertFalse(facts['pain']['issues'])
        self.assertFalse(facts['plan']['issues'], facts['plan']['issues'])
        self.assertTrue(facts['false_finding']['issues'])
        answer = self.assign(notes, facts, 'Plan section: documented advice and follow-up.', ['plan'], timing='future')
        self.assertEqual(answer['status'],'supported',answer['review_reasons'])
        self.assertEqual(answer['text'],instruction)

    def test_scheduled_conditional_followup_variants_use_the_same_instruction_scope(self):
        for instruction in ('Follow-up in four weeks, or earlier if symptoms worsen',
                'Review is scheduled after the investigation, with earlier contact if pain persists',
                'Follow-up is planned in four weeks to review results, with earlier contact if symptoms worsen'):
            with self.subTest(instruction=instruction):
                _,_,facts = self.values('P\n'+instruction+'.',
                    [('plan',instruction,'follow_up','affirmed','future')])
                self.assertFalse(facts['plan']['issues'],facts['plan']['issues'])

    def test_retraction_targets_named_domain_and_keeps_exact_governing_evidence(self):
        finding = 'She reports wrist pain'
        impression = 'Wrist pain was evaluated today'
        retraction = 'The documented assessment is incorrect'
        _, _, facts = self.values('S\n'+finding+'.\nA\n'+impression+'. '+retraction+'.',
            [('pain',finding,'history','affirmed','current'),('assessment',impression,'assessment','affirmed','current')])
        self.assertFalse(facts['pain']['issues'])
        self.assertTrue(facts['assessment']['issues'])
        self.assertTrue(any(retraction in evidence['quote'] for evidence in facts['assessment']['evidence']))

    def test_true_whole_record_retraction_still_holds_identity_and_findings(self):
        finding = 'She reports wrist pain'
        _, _, facts = self.values('S\n'+finding+'.\nThe entire current note is invalid.',
            [('pain',finding,'history','affirmed','current'),('name','Synthetic Ada Tern','identity','affirmed','current')])
        self.assertTrue(all(row['issues'] for row in facts.values()))
        _,_,facts = self.values('S\n'+finding+'.\nThe whole clinical note belongs to another patient.',
            [('pain',finding,'history','affirmed','current'),('name','Synthetic Ada Tern','identity','affirmed','current')])
        self.assertTrue(all(row['issues'] for row in facts.values()))

    def test_inline_deictic_retraction_governs_its_predicate_not_unrelated_facts(self):
        valid = 'She reports wrist pain'
        invalid = 'She reports heartburn, described as burning behind the breastbone but this was recorded in error'
        _,_,facts = self.values('S\n'+valid+'. '+invalid+'.',
            [('pain',valid,'history','affirmed','current'),
             ('heartburn','She reports heartburn, described as burning behind the breastbone','history','affirmed','current')])
        self.assertFalse(facts['pain']['issues'])
        self.assertTrue(facts['heartburn']['issues'])
        self.assertTrue(any('recorded in error' in e['quote'] for e in facts['heartburn']['evidence']))
        intact = 'She reports heartburn but this was not recorded in error'
        _,_,facts = self.values('S\n'+intact+'.',[('heartburn',intact,'history','affirmed','current')])
        self.assertFalse(facts['heartburn']['issues'],facts['heartburn']['issues'])
        for retraction in ('This was recorded incorrectly.', 'This was for another patient.', 'That may be invalid.'):
            _,_,facts = self.values('S\n'+valid+'. She reports heartburn. '+retraction,
                [('pain',valid,'history','affirmed','current'),('heartburn','She reports heartburn','history','affirmed','current')])
            self.assertFalse(facts['pain']['issues'])
            self.assertTrue(facts['heartburn']['issues'],retraction)

    def test_negative_heading_ends_at_explicit_section_boundary(self):
        first = 'Fever'
        second = 'She appears comfortable'
        _, _, facts = self.values('S\nThe following findings are denied:\n'+first+'.\nO:\n'+second+'.',
            [('fever',first,'finding','affirmed','current'),('exam',second,'finding','affirmed','current')])
        self.assertTrue(facts['fever']['issues'])
        self.assertFalse(facts['exam']['issues'],facts['exam']['issues'])

    def test_patient_scope_and_encounter_time_remain_independent(self):
        for heading, timing in [('Mother\nS','current'),('Previous encounter\nS','current')]:
            with self.subTest(heading=heading):
                _, _, facts = self.values(heading+'\nShe reports wrist pain.',
                    [('pain','She reports wrist pain','history','affirmed',timing)])
                self.assertTrue(facts['pain']['issues'])

    def test_negative_embedded_qualifier_does_not_negate_affirmative_symptom(self):
        quote = 'She reports wrist pain without radiation'
        _, _, facts = self.values('S\n'+quote+'.', [('pain',quote,'history','affirmed','current')])
        self.assertFalse(facts['pain']['issues'])
        _, _, facts = self.values('S\nShe denies wrist pain.', [('pain','wrist pain','finding','affirmed','current')])
        self.assertTrue(facts['pain']['issues'])

    def test_shared_subject_new_predicate_ends_denial_but_nominal_list_does_not(self):
        for connector in ('and reports','but reports','and has'):
            _,_,facts = self.values('S\nShe denies fever '+connector+' cough.',
                [('cough','cough','history','affirmed','current')])
            self.assertFalse(facts['cough']['issues'],(connector,facts['cough']['issues']))
        _,_,facts = self.values('S\nShe denies fever, cough and nausea.',
            [('cough','cough','history','affirmed','current')])
        self.assertTrue(facts['cough']['issues'])

    def test_narrow_or_unknown_negative_topic_cannot_acquire_broad_section_permission(self):
        quote = 'She denies difficulty swallowing liquids'
        notes,_,facts = self.values('S\n'+quote+'.',[('denial',quote,'history','negated','current')])
        for meaning in ('Documented urinary symptoms and fluid intake, including documented absence as well as presence.',
                'Subjective: documented urinary symptoms and fluid intake.',
                'Documented renal symptoms and pertinent negatives.',
                'Subjective: reported respiratory symptoms.'):
            answer = self.assign(notes,facts,meaning,['denial'])
            self.assertNotEqual(answer['status'],'supported',meaning)
        for meaning in ('Subjective: reported symptoms.',
                'Subjective: include the documented patient name and the patient’s reported symptoms, retaining documented qualifiers and uncertainty.'):
            answer = self.assign(notes,facts,meaning,['denial'])
            self.assertEqual(answer['status'],'supported',answer['review_reasons'])

    def test_historical_medicine_current_nonuse_requires_declared_attribute_and_selected_trial(self):
        from core.tests.test_complete_narrative_contracts import CompleteNarrativeContractsTests
        # The existing typed medicine evidence must survive the new scope
        # model, including its explicit dates and current/past distinction.
        trial = 'She previously took cetirizine 10 mg by mouth each evening for itching from 2 October through 7 October 2027'
        response = 'It gave no meaningful relief'
        stopped = 'She stopped it on 8 October because it was not helping and is no longer taking cetirizine'
        specs = [('trial',trial,'history','affirmed','past'),('response',response,'history','negated','past'),
            ('stop',stopped.split(' and ')[0],'history','affirmed','past'),
            ('current','no longer taking cetirizine','history','negated','current')]
        meaning = CompleteNarrativeContractsTests.medicine
        notes,_,facts = self.values('S\n'+trial+'. '+response+'. '+stopped+'.',specs)
        complete = self.assign(notes,facts,meaning,list(facts),timing='past')
        self.assertEqual(complete['status'],'supported',complete['review_reasons'])
        for absent in ('trial','response','stop','current'):
            answer = self.assign(notes,facts,meaning,[key for key in facts if key!=absent],timing='past')
            self.assertNotEqual(answer['status'],'supported',absent)
        answer = self.assign(notes,facts,meaning+' Omit current non-use.',list(facts),timing='past')
        self.assertNotEqual(answer['status'],'supported')

    def test_complete_uncertainty_is_preserved_without_becoming_confirmed_diagnosis(self):
        quote = 'An inflammatory cause is a possibility, but it has not been established'
        notes, _, facts = self.values('A\n'+quote+'.', [('cause',quote,'assessment','uncertain','current')])
        answer = self.assign(notes,facts,'Assessment section: documented impression and uncertainty.',['cause'],timing='current')
        self.assertEqual(answer['status'],'supported',answer['review_reasons'])
        self.assertEqual(answer['text'],quote)
        _, _, wrong = self.values('A\n'+quote+'.',[('cause',quote,'assessment','affirmed','current')])
        self.assertTrue(wrong['cause']['issues'])

    def test_complete_meaning_excludes_assessment_in_every_consumer(self):
        exam = 'She appears comfortable'
        assessment = 'The cause remains uncertain'
        notes, _, facts = self.values('O\n'+exam+'.\nA\n'+assessment+'.',
            [('exam',exam,'finding','affirmed','current'),('assessment',assessment,'assessment','uncertain','current')])
        meanings = ('Objective: complete documented examination findings. Excludes assessment content.',
            'Objective section: observations and examination findings. Descriptive content only, not patient-reported symptoms, an assessment or a plan.',
            'Objective: examination findings without assessment or plan.',
            'Objective: examination findings. Do not include an assessment.')
        for meaning in meanings:
            with self.subTest(meaning=meaning):
                fields, definitions = self.definition(meaning,timing='current')
                requirements = model.field_requirements(definitions['answer'])
                self.assertIn('assessment',requirements['excluded_domains'])
                self.assertNotIn('assessment',requirements['required_domains'])
                answer = self.assign(notes,facts,meaning,['exam'],timing='current')
                self.assertEqual(answer['status'],'supported',answer['review_reasons'])
                wrong = self.assign(notes,facts,meaning,['exam','assessment'],timing='current')
                self.assertNotEqual(wrong['status'],'supported')

    def test_mixed_observation_cannot_fill_a_positive_only_meaning(self):
        quote = 'The abdomen is soft and nondistended, with no guarding'
        notes,_,facts = self.values('O\n'+quote+'.',[('exam',quote,'finding','mixed','current')])
        for meaning in ('Objective: examination findings, positive findings only.',
                'Objective: only positive observations.', 'Examination findings. Omit normal findings.'):
            answer = self.assign(notes,facts,meaning,['exam'],timing='current')
            self.assertNotEqual(answer['status'],'supported',meaning)

    def test_literal_negative_examination_predicate_cannot_inherit_positive_permission(self):
        for quote in ('Abdomen is soft and nontender','Abdomen is soft without guarding',
                'The abdomen is soft and nondistended, with no guarding'):
            with self.subTest(quote=quote):
                notes,_,facts = self.values('O\n'+quote+'.',[('exam',quote,'finding','affirmed','current')])
                self.assertFalse(facts['exam']['issues'])
                general = self.assign(notes,facts,'Objective: complete examination findings.',['exam'])
                self.assertEqual(general['status'],'supported',general['review_reasons'])
                restricted = self.assign(notes,facts,
                    'Objective: physical examination findings; include only positive findings.',
                    ['exam'],polarity='positive')
                self.assertNotEqual(restricted['status'],'supported')
                self.assertTrue(any('negative predicate' in issue for issue in restricted['review_reasons']))
        quote = 'She reports pain without radiation'
        notes,_,facts = self.values('S\n'+quote+'.',[('pain',quote,'history','affirmed','current')])
        answer = self.assign(notes,facts,'Subjective: positive reported symptoms only.',
            ['pain'],polarity='positive')
        self.assertEqual(answer['status'],'supported',answer['review_reasons'])

    def test_do_not_omit_is_preservation_not_an_exclusion(self):
        _, definitions = self.definition('Assessment: documented impression. Do not omit uncertainty.')
        requirements = model.field_requirements(definitions['answer'])
        self.assertIn('assessment',requirements['required_domains'])
        self.assertNotIn('assessment',requirements['excluded_domains'])
        _,definitions = self.definition('Complete documented examination findings, preserving relevant negatives.')
        self.assertIn('objective',model.field_requirements(definitions['answer'])['required_domains'])
        _,definitions = self.definition('Do not omit assessment content.')
        self.assertIn('assessment',model.field_requirements(definitions['answer'])['required_domains'])
        self.assertNotIn('assessment',model.field_requirements(definitions['answer'])['excluded_domains'])
        _,definitions = self.definition('Exclude assessment, but include the documented plan.')
        parsed = model.field_requirements(definitions['answer'])
        self.assertIn('assessment',parsed['excluded_domains'])
        self.assertIn('plan',parsed['required_domains'])
        self.assertNotIn('plan',parsed['excluded_domains'])

    def test_narrative_keeps_temporal_qualifier_visible(self):
        for prefix in ('Before this change,','At baseline,','Prior to this episode,'):
            full = prefix+' she passed one formed stool daily'
            current = 'She currently passes one hard stool every three days'
            notes, _, facts = self.values('S\n'+full+'. '+current+'.',
                [('past','she passed one formed stool daily','history','affirmed','past'),
                 ('current',current,'history','affirmed','current')])
            before = deepcopy(facts)
            meaning = 'Subjective: documented patient-reported symptoms and history, retaining qualifiers.'
            clipped = self.assign(notes,facts,meaning,['past','current'])
            self.assertEqual(clipped['status'],'supported',clipped['review_reasons'])
            self.assertIn(full,clipped['text'])
            self.assertEqual(facts,before)
            self.assertEqual(clipped['source_projections']['past']['rendered_evidence']['quote'],full)
            notes, _, complete = self.values('S\n'+full+'. '+current+'.',
                [('past',full,'history','affirmed','past'),('current',current,'history','affirmed','current')])
            answer = self.assign(notes,complete,meaning,['past','current'])
            self.assertEqual(answer['status'],'supported',answer['review_reasons'])
            self.assertIn(prefix,answer['text'])

    def test_temporal_projection_cannot_add_missing_predicate_cross_clauses_or_override_wrong_time(self):
        from core.clinical_semantics import temporal_projection
        _,definitions = self.definition('Subjective: reported symptoms and history.')
        cases = [('Before this change, she passed one formed stool daily.','one formed stool daily','past'),
            ('Before this change, she passed one formed stool daily and she reported pain.','she passed one formed stool daily','past'),
            ('Before this change, she passed one formed stool daily.','she passed one formed stool daily','current')]
        for source,value,timing in cases:
            notes,_,facts = self.values('S\n'+source,[('past',value,'history','affirmed',timing)])
            self.assertIsNone(temporal_projection(notes,definitions['answer'],facts['past']))
            answer = self.assign(notes,facts,definitions['answer']['meaning'],['past'])
            self.assertNotEqual(answer['status'],'supported')

    def test_temporal_projection_proof_is_recomputed_and_atomic_value_is_unchanged(self):
        notes = self.header+'S\nBefore this change, she passed one formed stool daily.'
        fields,definitions = self.definition('Subjective: reported symptoms and history.')
        raw = [fact(notes,fields,'past','she passed one formed stool daily',kind='history',timing='past')]
        sender = FixtureSender(raw,assignments(fields,{'answer':['past']}))
        answer = semantic.run(notes,fields,definitions,sender,scope_contract=self.profile,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)['answer']
        self.assertEqual(answer['status'],'supported',answer['review_reasons'])
        semantic.validate_stored_answer(notes,fields[0],definitions['answer'],answer)
        tampered = deepcopy(answer)
        tampered['source_projections']['past']['rendered_evidence']['start'] += 1
        tampered['semantic_proof_sha256'] = semantic._fact_proof(tampered)
        with self.assertRaisesMessage(ValidationError,'stored temporal projection'):
            semantic.validate_stored_answer(notes,fields[0],definitions['answer'],tampered)
        atomic = deepcopy(definitions['answer'])
        atomic['answer_mode'] = 'atomic'
        from core.clinical_semantics import temporal_projection
        self.assertIsNone(temporal_projection(notes,atomic,answer['facts'][0]))

    def test_current_order_and_actual_not_done_remain_current_in_future_plan(self):
        order = 'A blood count is ordered today for collection next week'
        not_done = 'No blood was collected today and no result is available'
        notes, _, facts = self.values('P\n'+order+'. '+not_done+'.',
            [('order',order,'plan','affirmed','current'),('status',not_done,'finding','negated','current')])
        answer = self.assign(notes,facts,'Plan section: documented clinical plan.',['order','status'],timing='future')
        self.assertEqual(answer['status'],'supported',answer['review_reasons'])
        self.assertEqual(facts['status']['timing']['kind'],'current')

    def test_patient_record_time_keeps_named_clinician_actor_and_service_date(self):
        fields,definitions = self.definition('Plan section: the clinician’s documented plan for the patient.',timing='future')
        for actor,day,passes in (('Cole','21',True),('Other','21',False),('Cole','20',False),('Cole','22',False)):
            quote = 'Dr. '+actor+' spent 27 minutes on '+day+' October 2027: examining and counseling the patient'
            notes = self.header+'P\n'+quote+'.'
            units,_ = generation.source_units(notes,fields)
            raw = fact(notes,fields,'time',quote,kind='other',subject='clinician')
            facts = semantic.validate_facts(notes,units,{'facts':[raw]},scope_contract=self.profile)
            answer = semantic._assign(notes,fields,definitions,facts,assignments(fields,{'answer':['time']}),scope_contract=self.profile)['answer']
            self.assertEqual(answer['status']=='supported',passes,(actor,day,answer['review_reasons']))
            self.assertEqual(facts['time']['subject']['kind'],'clinician')

    def test_contradictions_and_omissions_cannot_be_cleared_by_review(self):
        notes, _, facts = self.values('S\nShe reports fever. She denies fever.',
            [('positive','She reports fever','finding','affirmed','current'),('negative','She denies fever','finding','negated','current')])
        facts['negative']['concept'] = facts['positive']['concept']
        answer = self.assign(notes,facts,'Subjective: reported symptoms and negatives.',['positive','negative'])
        self.assertNotEqual(answer['status'],'supported')
        self.assertTrue(any('contradictory' in reason for reason in answer['review_reasons']))

    def test_original_contract_preserves_historical_blanket_hold(self):
        quote = 'She reports wrist pain'
        body = 'S\n'+quote+'. These symptom durations do not represent encounter time.'
        _, _, old = self.values(body,[('pain',quote,'history','affirmed','current')],profile=semantic.LABELLED_PRESENTATION_SCOPE_CONTRACT)
        _, _, new = self.values(body,[('pain',quote,'history','affirmed','current')])
        self.assertTrue(old['pain']['issues'])
        self.assertFalse(new['pain']['issues'])

    def test_all_stages_share_requirements_and_generated_proof_revalidates(self):
        notes = self.header+'S\nShe reports wrist pain.'
        fields, definitions = self.definition('Subjective: reported symptoms.')
        raw = [fact(notes,fields,'pain','She reports wrist pain',kind='history')]
        sender = FixtureSender(raw, assignments(fields,{'answer':['pain']}))
        answers = semantic.run(notes,fields,definitions,sender,scope_contract=self.profile,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
        self.assertEqual(answers['answer']['status'],'supported',answers['answer']['review_reasons'])
        self.assertEqual(len(sender.calls),3)
        requirements = {key:model.field_requirements(value) for key,value in definitions.items()}
        for role,attempt,payload,schema,instructions in sender.calls:
            self.assertEqual(payload['approved_field_requirements'],requirements)
            self.assertIn(model.INSTRUCTIONS,instructions)
            self.assertEqual(payload['fact_scope_contract'],self.profile)
        semantic.validate_stored_answer(notes,fields[0],definitions['answer'],answers['answer'])

    def test_real_negated_predicate_cannot_be_tagged_affirmative(self):
        quote = 'An infection is not established'
        _,_,facts = self.values('A\n'+quote+'.',[('infection',quote,'assessment','affirmed','current')])
        self.assertTrue(facts['infection']['issues'])

    def test_calendar_month_is_not_uncertainty_and_atomic_site_is_not_clipped(self):
        quote = 'She previously attended on 8 May 2027 for wrist pain'
        _,_,facts = self.values('S\n'+quote+'.',[('prior',quote,'history','affirmed','past')])
        self.assertFalse(facts['prior']['issues'],facts['prior']['issues'])
        _,_,facts = self.values('S\nShe reports severe left wrist pain.',
            [('pain','wrist pain','reason','affirmed','current')])
        self.assertTrue(facts['pain']['issues'])

    def test_current_saved_name_has_its_own_affirmative_record_role(self):
        name = 'Synthetic Iris Vale'
        positives = [name, name+'; She reports pain without radiation',
            'Name: '+name, 'Patient: '+name, 'Patient name is '+name,
            'The patient is '+name+'.', name+' reports a possible infection.',
            name+' denies fever.', name+'. The patient’s identity is confirmed.']
        for text in positives:
            with self.subTest(text=text):
                proof = model.current_document_identity(text,name)
                self.assertFalse(proof['issues'],proof)
                self.assertTrue(proof['assertions'])
                for row in proof['assertions']:
                    span = row['name_evidence']
                    self.assertEqual(text[span['start']:span['end']],name)
        negatives = ['Patient name is not '+name+'.',
            'The patient is Synthetic Different Patient. Her mother is '+name+'.',
            'Prior encounter: '+name+'. Current patient name is blank.',
            name+'’s identity is uncertain.', name+' was entered in error.',
            name+' is a hypothetical example.', 'Mother:\n'+name,
            'Previous encounter:\nPatient: '+name,
            name+'; The patient’s name is incorrect.',
            name+'. Identity remains uncertain.', name+'. This was recorded in error.']
        for text in negatives:
            with self.subTest(text=text):
                self.assertTrue(model.current_document_identity(text,name)['issues'])

    def test_current_identity_proof_checks_saved_name_scope_without_changing_history(self):
        from core.tests.test_document_identity import DocumentIdentityTests
        fixture = DocumentIdentityTests()
        notes, fields, definitions, facts = fixture.case()
        answers, _ = fixture.generate(notes,fields,definitions,facts,{'subjective':['identity','symptom']})
        original = deepcopy(answers)
        valid = semantic.current_identity_proof(notes,fields[0],definitions['subjective'],answers['subjective'])
        self.assertFalse(valid['issues'],valid)
        self.assertEqual(valid['patient_names'][0]['name_evidence']['quote'],'Synthetic Avery Sen')
        self.assertTrue(valid['document_identity_evidence'][0]['assertions'])
        for text in ('Patient name is not Synthetic Avery Sen.',
                'Mother:\nSynthetic Avery Sen', 'Synthetic Avery Sen was entered in error.'):
            edited = deepcopy(answers['subjective'])
            edited.update(text=text,value=text,semantic_review_mode='manual',reviewed=True)
            proof = semantic.current_identity_proof(notes,fields[0],definitions['subjective'],edited)
            self.assertTrue(proof['issues'])
            self.assertEqual(proof['patient_names'],[])
        self.assertEqual(answers,original)

    def test_saved_record_binding_is_explicit_and_cannot_change_source_defaults(self):
        from core.clinical_source_context import source_context
        text = 'Synthetic Iris Vale; She reports pain.'
        units,_ = generation.source_units(text,[])
        self.assertTrue(model.source_context(text,units)['issues'])
        self.assertFalse(model.source_context(text,units,record_identity='Synthetic Iris Vale')['issues'])
        with self.assertRaises(ValueError):
            source_context(text,units,record_identity='Synthetic Iris Vale')
        self.assertTrue(model.current_document_identity(
            'Patient: Synthetic Different Patient.\nSynthetic Iris Vale','Synthetic Iris Vale')['issues'])

    def test_reported_negative_object_cannot_become_a_positive_symptom(self):
        for report in ('She reports no fever','She reports not having fever',
                'She reports never having fever','She reports absence of fever',
                'Fever was denied','She reports fever was denied',
                'She reported an absence of fever','Fever is absent'):
            with self.subTest(report=report):
                notes,_,facts = self.values('S\n'+report+'.',
                    [('negative',report,'history','affirmed','current')])
                self.assertTrue(facts['negative']['issues'])
                answer = self.assign(notes,facts,'Subjective: positive reported symptoms only.',
                    ['negative'],polarity='positive')
                self.assertNotEqual(answer['status'],'supported')
        _,_,facts = self.values('S\nShe denies fever and has cough.',
            [('cough','has cough','history','affirmed','current')])
        self.assertFalse(facts['cough']['issues'],facts['cough']['issues'])
        for quote in ('She reports cough without fever','She reports cough without radiation'):
            with self.subTest(quote=quote):
                _,_,facts = self.values('S\n'+quote+'.',[("cough",quote,'history','affirmed','current')])
                self.assertFalse(facts['cough']['issues'],facts['cough']['issues'])

    def test_field_exclusion_governors_keep_content_and_destination_separate(self):
        for meaning in ('Objective: documented examination findings. Assessment is excluded.',
                'Objective: examination findings except assessment.',
                'Objective: examination findings; no assessment content.',
                'Objective: examination findings with no assessment.',
                'Objective: examination findings. Assessment is excluded from Objective.',
                'Objective: examination findings. Assessment should be omitted.'):
            with self.subTest(meaning=meaning):
                _,definitions = self.definition(meaning)
                requirements = model.field_requirements(definitions['answer'])
                self.assertIn('assessment',requirements['excluded_domains'])
                self.assertNotIn('assessment',requirements['required_domains'])
                self.assertIn('objective',requirements['required_domains'])
                self.assertNotIn('objective',requirements['excluded_domains'])
        _,definitions = self.definition('Objective: examination findings. Assessment is not excluded.')
        self.assertIn('assessment',model.field_requirements(definitions['answer'])['required_domains'])
        _,definitions = self.definition('Objective: examination findings. No assessment is required.')
        self.assertIn('assessment',model.field_requirements(definitions['answer'])['optional_domains'])

    def test_recurring_event_triggers_are_distinct_from_prior_encounter_and_baseline(self):
        for quote in ('Before exercise she experiences wrist pain','She reports wrist pain before meals',
                'Prior to meals she experiences wrist pain'):
            with self.subTest(quote=quote):
                _,_,facts = self.values('S\n'+quote+'.',[("pain",quote,'history','affirmed','current')])
                self.assertFalse(facts['pain']['issues'],facts['pain']['issues'])
                self.assertEqual(facts['pain']['source_assertion']['clinical_timing'],'current')
        for quote in ('She reports wrist pain during her previous visit',
                'She reports wrist pain at the prior encounter',
                'Before this change, she passed one formed stool daily',
                'Prior to this episode, she passed one formed stool daily'):
            with self.subTest(quote=quote):
                _,_,facts = self.values('S\n'+quote+'.',[("pain",quote,'history','affirmed','current')])
                self.assertTrue(facts['pain']['issues'])
                self.assertEqual(facts['pain']['source_assertion']['clinical_timing'],'past')

    def test_unknown_narrow_narrative_cannot_require_or_authorize_a_whole_section(self):
        notes,_,facts = self.values('S\nShe reports heartburn. She reports cough.',
            [('heartburn','She reports heartburn','history','affirmed','current'),
             ('cough','She reports cough','history','affirmed','current')])
        for meaning in ('Description of the heartburn history: onset and frequency.',
                'Documented urinary symptoms and fluid intake.'):
            with self.subTest(meaning=meaning):
                answer = self.assign(notes,facts,meaning,['heartburn'])
                self.assertNotEqual(answer['status'],'supported')
                self.assertTrue(any('verified scope' in reason for reason in answer['review_reasons']))
                self.assertFalse(any('omits a documented assertion' in reason for reason in answer['review_reasons']))


    def test_complete_event_history_keeps_the_predicate_and_standalone_adjunct_stays_held(self):
        quote='She has severe left wrist pain after lifting a box'
        notes,_,facts=self.values('S\n'+quote+'.',[("history",quote,'history','affirmed','current')])
        self.assertFalse(facts['history']['issues'])
        answer=self.assign(notes,facts,'Subjective: complete reported symptoms and history.',['history'])
        self.assertEqual(answer['status'],'supported',answer['review_reasons'])
        for value,kind in (('with movement','finding'),('in the left wrist','finding'),
                ('after lifting a box','history'),('after lifting','history'),('after lifting a box','finding')):
            report=('She reports severe pain '+value if value in ('with movement','in the left wrist') else quote)
            with self.subTest(value=value,kind=kind):
                notes,_,facts=self.values('S\n'+report+'.',[("fragment",value,kind,'affirmed','current')])
                self.assertTrue(facts['fragment']['issues'])
                for meaning in ('Subjective: documented patient-reported symptoms and history, retaining clinical qualifiers.',
                        'Causal event','Precipitating event','The documented injury mechanism.'):
                    fields,definitions=self.definition(meaning,timing='current')
                    definitions['answer']['answer_mode']='atomic'
                    answer=semantic._assign(notes,fields,definitions,facts,assignments(fields,{'answer':['fragment']}),
                        scope_contract=self.profile,timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)['answer']
                    self.assertNotEqual(answer['status'],'supported')


    def test_current_complete_mixed_observation_reaches_checker_and_canonical_saved_proof(self):
        report='Examination shows mild swelling over the left lateral ankle, no deformity, and intact distal sensation'
        notes=self.header+'O\n'+report+'.'
        fields,definitions=self.definition('Objective: complete documented examination findings.',timing='current')
        raw=[fact(notes,fields,'observation',report,kind='finding',polarity='mixed')]
        before=deepcopy(raw)
        sender=FixtureSender(raw,assignments(fields,{'answer':['observation']}))
        answer=semantic.run(notes,fields,definitions,sender,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=self.profile)['answer']
        self.assertEqual([(call[0],call[1])for call in sender.calls],[('extractor',1),('assigner',1),('checker',1)])
        self.assertEqual(raw,before)
        self.assertEqual(answer['status'],'supported',answer['review_reasons'])
        self.assertEqual(answer['text'],report)
        self.assertEqual(answer['fact_scope_contract'],self.profile)
        self.assertEqual(answer['independent_check']['verdict'],'pass')
        semantic.validate_stored_answer(notes,fields[0],definitions['answer'],answer)

    def test_clipped_observation_state_retains_conservative_scope_in_atomic_destinations(self):
        # These literal fragments cannot prove independence from their matrix,
        # a prior negative list, or a contradictory assertion. Whole predicates
        # and explicit graph components have their own successful paths.
        for report,value in (
                ('Examination shows mild swelling over the left lateral ankle, no deformity, and intact distal sensation','intact distal sensation'),
                ('Examination reveals mild swelling, no deformity, and preserved distal sensation','preserved distal sensation'),
                ('Examination never shows mild swelling, no deformity, and intact distal sensation','intact distal sensation'),
                ('No examination shows mild swelling, no deformity, and intact distal sensation','intact distal sensation'),
                ('No assessment demonstrates swelling, no tenderness, and normal strength','normal strength'),
                ('Nobody shows mild swelling, no deformity, and intact distal sensation','intact distal sensation'),
                ('None shows mild swelling, no deformity, and intact distal sensation','intact distal sensation'),
                ('Examination possibly shows mild swelling, no deformity, and intact distal sensation','intact distal sensation'),
                ('A hypothetical examination shows mild swelling, no deformity, and intact distal sensation','intact distal sensation'),
                ('Examination shows mild swelling, no deformity or preserved sensation and normal strength','normal strength'),
                ('Examination shows mild swelling, without tenderness or intact reflexes and normal strength','normal strength'),
                ('Examination shows mild swelling, no deformity or intact distal sensation','intact distal sensation'),
                ('Examination shows mild swelling, no distal sensation, and intact distal sensation','intact distal sensation'),
                ('Examination shows mild swelling, no sensation, and intact distal sensation','intact distal sensation'),
                ('Examination shows mild swelling, no deformity, and intact distal sensation','distal sensation'),
                ('Examination shows mild swelling, no deformity, and possibly intact distal sensation','possibly intact distal sensation'),
                ('Examination shows mild swelling despite an unresolved correction, no deformity, and intact distal sensation','intact distal sensation')):
            with self.subTest(report=report):
                notes,_,facts=self.values('O\n'+report+'.',[("state",value,'finding','affirmed','current')])
                self.assertTrue(facts['state']['issues'])
                fields,definitions=self.definition('Objective: documented examination findings.',timing='current')
                definitions['answer']['answer_mode']='atomic'
                answer=semantic._assign(notes,fields,definitions,facts,assignments(fields,{'answer':['state']}),
                    scope_contract=self.profile,timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)['answer']
                self.assertNotEqual(answer['status'],'supported')

    def test_causal_denial_cannot_make_a_temporal_adjunct_a_supported_causal_event(self):
        for correction in ('Lifting the box did not cause the wrist pain.',
                'No precipitating event is established.'):
            notes,_,facts=self.values('S\nShe has severe left wrist pain after lifting a box. '+correction,
                [("fragment",'after lifting a box','history','affirmed','current')])
            for meaning in ('Causal event','Precipitating event','The documented injury mechanism.'):
                fields,definitions=self.definition(meaning,timing='current')
                definitions['answer']['answer_mode']='atomic'
                answer=semantic._assign(notes,fields,definitions,facts,assignments(fields,{'answer':['fragment']}),
                    scope_contract=self.profile,timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)['answer']
                self.assertNotEqual(answer['status'],'supported')

    def test_unknown_narrow_scope_stays_held_through_a_well_formed_bounded_repair(self):
        from core.tests.test_semantic_generation import fact, assignments, checker, FixtureSender
        notes = self.header+'S\nShe reports heartburn on three days each week.'
        fields = [{'key':'frequency','label':'Requested frequency','kind':'text','locator':{'cell':0}},
            {'key':'identity','label':'Patient full name','kind':'text','locator':{'cell':1}}]
        definitions = default_definitions(fields)
        for definition in definitions.values():
            definition.update(version=3,answer_mode='narrative' if definition['value_type']=='text' else 'atomic',
                patient_name_requirement='none')
        definitions['frequency'].update(meaning='Document only the current heartburn frequency.',
            scope={'subject':'patient','temporality':'current','polarity':'any'})
        definitions['identity'].update(value_type='person_name',answer_mode='atomic')
        raw = [fact(notes,fields,'symptom','She reports heartburn on three days each week',kind='history'),
            fact(notes,fields,'patient','Synthetic Ada Tern',kind='identity',name_quote='Synthetic Ada Tern')]
        original = deepcopy(raw)
        assigned = assignments(fields,{'frequency':['symptom'],'identity':['patient']})
        repaired = {'fields':[assigned['fields'][0]]}
        sender = FixtureSender(raw,assigned,repaired=repaired,rechecked=checker(assigned))
        answers = semantic.run(notes,fields,definitions,sender,
            reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT,scope_contract=self.profile)
        self.assertEqual(raw,original)
        self.assertEqual([(call[0],call[1])for call in sender.calls],
            [('extractor',1),('assigner',1),('checker',1),('assigner',2),('checker',2)])
        self.assertEqual(sender.calls[3][2]['repair_keys'],['frequency'])
        self.assertEqual(answers['identity']['status'],'supported')
        self.assertEqual(answers['identity']['text'],'Synthetic Ada Tern')
        self.assertNotEqual(answers['frequency']['status'],'supported')
        self.assertEqual(answers['frequency']['text'],'')
        self.assertTrue(any('verified scope' in reason for reason in answers['frequency']['review_reasons']))
        for field in fields:
            semantic.validate_stored_answer(notes,field,definitions[field['key']],answers[field['key']])
