"""Source-boundary counterexamples; no provider, live DB or clinical generation."""
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from anthropic import transform_schema
from pydantic import ValidationError as PydanticValidationError
from core import ai_stages, coding_engine as engine
from core.coding_terminology import parse_reference


def concept(term, evidence, **changes):
    return {'id':'c1','term':term,'index_terms':[term],'evidence':evidence,
            'kind':'symptom','certainty':'confirmed','temporality':'current','subject':'patient',
            'relevant':True,'missing_detail':'','integral_to':'',**changes}


def run(notes, **inputs):
    return SimpleNamespace(inputs={'notes':notes,'answers':{},'service_date':'2026-10-14',
        'patient_identity':{'display_name':'Synthetic Test Patient'},**inputs},
        context={'setting':'outpatient_office','patient_status':'unknown','em_basis':'unknown'},releases=[])


class CodingClinicalPayloadTests(SimpleTestCase):
    def test_complete_saved_text_and_numeric_context_are_preserved(self):
        answers = {
            'identity': {'text':'Synthetic Patient Ω\r\nNo history of cancer.  ', 'status':'edited'},
            'score': {'text':'0', 'value':0, 'status':'supported', 'unit':'points',
                      'scale':{'scale_minimum':0, 'scale_maximum':10}},
            'negative': {'text':'No', 'value':False, 'status':'edited', 'unit':None, 'scale':None},
        }
        original = deepcopy(answers)
        expected = deepcopy(answers)
        del expected['score']['value']; del expected['negative']['value']
        projected = engine.clinical_answers(answers)
        self.assertEqual(projected, expected)
        projected['score']['scale']['scale_maximum'] = 5
        self.assertEqual(answers, original)

    def test_blank_missing_and_held_answers_never_use_proposed_or_typed_text(self):
        answers = {
            'blank': {'text':'', 'status':'left_blank', 'value':'Old diagnosis',
                      'candidate_text':'Proposed diagnosis', 'facts':[{'text':'Unsupported disease'}],
                      'independent_check':{'reason':'Old assertion'}, 'semantic_edit_history':['Earlier value']},
            'missing': {'status':'missing', 'candidate_text':'Do not fill the blank'},
            'conflict': {'text':'', 'status':'conflict', 'value':True},
        }
        self.assertEqual(engine.clinical_answers(answers), {
            'blank':{'text':'','status':'left_blank'}, 'missing':{'status':'missing'},
            'conflict':{'text':'','status':'conflict'}})

    def test_scale_projection_excludes_unrelated_provenance(self):
        self.assertEqual(engine.clinical_answers({'score':{'text':'2','scale':{
            'scale_minimum':0,'scale_maximum':10,'facts':['unrelated']}}}),
            {'score':{'text':'2','scale':{'scale_minimum':0,'scale_maximum':10}}})

    def test_malformed_saved_answer_fields_are_not_silently_discarded(self):
        for answers in [[], {'x':'diagnosis'}, {1:{'text':'diagnosis'}},
                        {'x':{'text':False}}, {'x':{'text':None}}, {'x':{'unit':[]}},
                        {'x':{'status':False}}, {'x':{'scale':'ten'}}]:
            with self.subTest(answers=answers), self.assertRaises(ValidationError):
                engine.clinical_answers(answers)

    def test_generate_uses_projection_and_keeps_full_immutable_inputs(self):
        notes = 'Synthetic Patient has no heartburn.\r\nMother had colon polyps.'
        answers = {'finding':{'text':'No heartburn', 'status':'supported',
                              'facts':['large retained provenance '*30000]}}
        item = run(notes, answers=answers)
        original = deepcopy(item.inputs)
        reference = SimpleNamespace(release=SimpleNamespace(version='FY2027'))
        extracted = {'documented_patient_name':'','patient_name_evidence':'','concepts':[]}
        with patch.object(engine,'reference_for',return_value=reference), \
             patch.object(engine.coding_provider,'execute',return_value=extracted) as send, \
             patch('core.coding_licensing.cpt_status',return_value={'available':False}):
            engine.generate(item)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[2], {'notes':notes, 'answers':{
            'finding':{'text':'No heartburn','status':'supported'}},
            'service_date':'2026-10-14','setting':'outpatient_office'})
        self.assertEqual(item.inputs, original)

    def test_provenance_reduction_passes_real_byte_guard_without_reserving_or_sending(self):
        from core import coding_provider as provider
        class BeforeReservation(Exception): pass
        item = run('No heartburn.', answers={'x':{'text':'No heartburn.', 'status':'supported',
            'facts':['retained provenance '*40000]}})
        item.config = {}
        raw_payload = {'notes':item.inputs['notes'],'answers':item.inputs['answers']}
        with patch.object(provider,'_identity',return_value={'input_digest':'test'}), \
             patch.object(provider.transaction,'atomic',side_effect=BeforeReservation) as reserve:
            with self.assertRaisesMessage(provider.CodingNotSent,'exceeds its byte limit'):
                provider.execute(item,'concepts',raw_payload,engine.Concepts,engine.CONCEPT_INSTRUCTIONS)
            reserve.assert_not_called()
            with self.assertRaises(BeforeReservation):
                provider.execute(item,'concepts',{**raw_payload,'answers':engine.clinical_answers(
                    item.inputs['answers'])},engine.Concepts,engine.CONCEPT_INSTRUCTIONS)
            reserve.assert_called_once()

    def test_large_clinical_text_is_preserved_then_refused_by_unchanged_byte_limit(self):
        from core import coding_provider as provider
        text = 'No heartburn. Ω\r\n' * 40000
        answers = engine.clinical_answers({'x':{'text':text}})
        self.assertEqual(answers['x']['text'],text)
        item = run('No heartburn.'); item.config = {}
        with patch.object(provider,'_identity',return_value={}), patch.object(provider.transaction,'atomic') as reserve:
            with self.assertRaisesMessage(provider.CodingNotSent,'exceeds its byte limit'):
                provider.execute(item,'concepts',{'answers':answers},engine.Concepts,engine.CONCEPT_INSTRUCTIONS)
            reserve.assert_not_called()

    def test_engine_version_changes_snapshot_digest_without_changing_saved_data(self):
        from core import coding_service as service
        encounter = SimpleNamespace(pk='encounter',department_id='department',patient_id='patient',
            patient=SimpleNamespace(pk='patient',display_name='Synthetic Patient',reference='test'),
            template_version_id='version',notes='No heartburn.',revision=2,service_date=date(2026,10,14),
            answers={'x':{'text':'No heartburn.','facts':['retained complete proof']}},
            template_version=SimpleNamespace(fields=[],semantic_definitions={},
                template=SimpleNamespace(sha256='a'*64),prepared_sha256='b'*64))
        original = deepcopy(encounter.answers)
        with patch.object(service,'context_data',return_value={'setting':'outpatient_office'}), \
             patch.object(service,'release_snapshot',return_value=[]):
            with patch.object(engine,'CONTRACT','us-outpatient-index-tabular-v1'):
                old = service.input_snapshot(encounter)
            current = service.input_snapshot(encounter)
            again = service.input_snapshot(encounter)
            encounter.answers['x']['facts'].append('Additional retained proof')
            changed_proof = service.input_snapshot(encounter)
        self.assertEqual(current,again)
        self.assertNotEqual(old[3],current[3])
        self.assertEqual(current[0]['engine_contract'],'us-outpatient-index-tabular-v4')
        self.assertEqual(old[0]['answers'],original)
        self.assertEqual(current[0]['answers'],original)
        old_inputs=deepcopy(old[0]);old_inputs['engine_contract']=engine.CONTRACT
        self.assertEqual(old_inputs,current[0])
        self.assertNotEqual(current[3],changed_proof[3])
        self.assertEqual(engine.clinical_answers(current[0]['answers']),
                         engine.clinical_answers(changed_proof[0]['answers']))


@override_settings(SYNTHETIC_ONLY=True)
class CodingSemanticIdentityTests(SimpleTestCase):
    def case(self, *, missing=False, label='Subjective'):
        from core import semantic_generation as semantic
        from core.tests.test_document_identity import soap_definitions
        from core.tests.test_semantic_generation import FixtureSender, assignments, fact
        name='Synthetic Avery Sen'
        notes=('The patient reports heartburn.' if missing else name+' reports heartburn. '
               'Referring clinician: Dr. Priya Chen. The patient’s mother, Synthetic Elin Sen, has diabetes.')
        fields=[{'key':'subjective','label':label,'kind':'text','locator':{'cell':0}}]
        definitions=soap_definitions(fields)
        facts=[fact(notes,fields,'symptom','heartburn',kind='history')]
        if not missing:
            facts += [fact(notes,fields,'identity',name,kind='identity',name_quote=name),
                fact(notes,fields,'referrer','Priya Chen',kind='identity',subject='clinician',name_quote='Priya Chen'),
                fact(notes,fields,'relative','Synthetic Elin Sen',kind='identity',subject='other',name_quote='Synthetic Elin Sen')]
        selected={'subjective':['symptom'] if missing else ['identity','symptom']}
        answers=semantic.run(notes,fields,definitions,FixtureSender(facts,assignments(fields,selected)),
            scope_contract=semantic.DOCUMENT_IDENTITY_SCOPE_CONTRACT)
        bridge={'contract':'approved-semantic-patient-name-v1',
            'fields':engine.semantic_patient_name_evidence(notes,fields,definitions,answers)}
        item=run(notes,answers=answers,patient_identity={'display_name':name},documented_patient_name_evidence=bridge)
        return item,fields,definitions

    def test_exact_patient_fact_bridges_narrative_without_relative_or_referrer_or_registry_fallback(self):
        item,_,_=self.case();raw={'documented_patient_name':'','patient_name_evidence':''}
        before=deepcopy((item.inputs,raw))
        rows=engine.checked_patient_name_evidence(item.inputs)
        self.assertEqual([n['name_evidence']['quote'] for r in rows for n in r['names']],['Synthetic Avery Sen'])
        self.assertNotEqual(item.inputs['answers']['subjective']['text'],'Synthetic Avery Sen')
        self.assertEqual(engine.identity_blockers(item,raw),[])
        self.assertEqual((item.inputs,raw),before)
        item.inputs['patient_identity']['display_name']='Synthetic Another Patient'
        self.assertTrue(engine.identity_blockers(item,raw))
        item.context['identity_review_reason']='Owner confirms this specific synthetic source reuse.'
        self.assertEqual(engine.identity_blockers(item,raw),[])
        with override_settings(SYNTHETIC_ONLY=False):self.assertTrue(engine.identity_blockers(item,raw))

    def test_missing_identity_remains_blocked_even_with_matching_registry_and_synthetic_reason(self):
        item,fields,definitions=self.case(missing=True)
        item.context['identity_review_reason']='Owner confirms this specific synthetic source reuse.'
        raw={'documented_patient_name':'','patient_name_evidence':''}
        self.assertTrue(engine.identity_blockers(item,raw))
        self.assertEqual(item.inputs['documented_patient_name_evidence']['fields'][0]['names'],[])
        empty=engine.semantic_patient_name_evidence(item.inputs['notes'],fields,definitions,{})
        self.assertEqual(empty[0]['finding']['verdict'],'unavailable')
        self.assertEqual(empty[0]['names'],[])

    def test_corrupt_or_unvalidated_identity_proof_and_changed_bridge_refuse(self):
        original,_,_=self.case()
        mutations=[lambda i:i['answers']['subjective'].update(text='Synthetic Invented Patient'),
            lambda i:i['answers']['subjective'].pop('semantic_proof_sha256'),
            lambda i:i['answers']['subjective'].update(fact_ids=['symptom']),
            lambda i:i['answers']['subjective']['facts'][1]['subject']['name_evidence'].update(quote='Synthetic Invented Patient'),
            lambda i:i['documented_patient_name_evidence']['fields'][0]['names'][0].update(fact_id='relative'),
            lambda i:i['documented_patient_name_evidence']['fields'][0]['names'][0]['name_evidence'].update(quote='Synthetic Elin Sen'),
            lambda i:i['documented_patient_name_evidence']['fields'][0]['definition'].update(patient_name_requirement='none'),
            lambda i:i['documented_patient_name_evidence']['fields'].append(deepcopy(i['documented_patient_name_evidence']['fields'][0]))]
        for mutate in mutations:
            item=deepcopy(original);mutate(item.inputs)
            with self.subTest(mutation=mutate),self.assertRaises(ValidationError):engine.checked_patient_name_evidence(item.inputs)

    def test_concepts_payload_gets_only_compact_validated_name_and_raw_extraction_stays_empty(self):
        item,_,_=self.case();original=deepcopy(item.inputs)
        raw={'documented_patient_name':'','patient_name_evidence':'','concepts':[]}
        with patch.object(engine,'reference_for',return_value=SimpleNamespace(release=SimpleNamespace(version='FY2027'))), \
             patch.object(engine.coding_provider,'execute',return_value=raw) as send, \
             patch('core.coding_licensing.cpt_status',return_value={'available':False}):
            result=engine.generate(item)
        send.assert_called_once();payload=send.call_args.args[2]
        self.assertEqual(set(payload),{'notes','answers','service_date','setting','approved_patient_names'})
        self.assertEqual(payload['approved_patient_names'],[{'field_key':'subjective','fact_id':'identity',
            'name_evidence':{'start':0,'end':19,'quote':'Synthetic Avery Sen'}}])
        self.assertNotIn('facts',payload['answers']['subjective'])
        self.assertEqual(result['global_blockers'],[])
        self.assertEqual(raw,{'documented_patient_name':'','patient_name_evidence':'','concepts':[]})
        self.assertEqual(item.inputs,original)

    def test_snapshot_adds_only_new_approved_v3_evidence_and_does_not_treat_narrative_label_as_name(self):
        from core import coding_service as service
        item,fields,definitions=self.case(label='Patient name')
        version=SimpleNamespace(fields=fields,semantic_definitions=definitions,
            template=SimpleNamespace(sha256='a'*64),prepared_sha256='')
        encounter=SimpleNamespace(pk='encounter',department_id='department',patient_id='patient',
            patient=SimpleNamespace(pk='patient',display_name='Synthetic Avery Sen',reference='test'),
            template_version_id='version',notes=item.inputs['notes'],revision=0,service_date=date(2026,10,15),
            answers=item.inputs['answers'],template_version=version)
        with patch.object(service,'context_data',return_value={}),patch.object(service,'release_snapshot',return_value=[]), \
             patch('core.semantic_preparation.validated_semantic_definitions',return_value=definitions) as approval:
            inputs,_,_,key=service.input_snapshot(encounter)
        approval.assert_called_once_with(version)
        self.assertEqual(inputs['patient_name_answers'],[])
        self.assertEqual(inputs['documented_patient_name_evidence'],item.inputs['documented_patient_name_evidence'])
        self.assertEqual(inputs['engine_contract'],'us-outpatient-index-tabular-v4')
        with patch.object(service,'context_data',return_value={}),patch.object(service,'release_snapshot',return_value=[]), \
             patch('core.semantic_preparation.validated_semantic_definitions',side_effect=ValidationError('Unapproved version')):
            with self.assertRaisesMessage(ValidationError,'Unapproved version'):service.input_snapshot(encounter)
        version.semantic_definitions={}
        with patch.object(service,'context_data',return_value={}),patch.object(service,'release_snapshot',return_value=[]), \
             patch('core.semantic_preparation.validated_semantic_definitions') as approval:
            legacy=service.input_snapshot(encounter)
        approval.assert_not_called()
        self.assertNotIn('documented_patient_name_evidence',legacy[0])
        self.assertNotEqual(key,legacy[3])


@override_settings(SYNTHETIC_ONLY=True)
class CodingEngineSourceTests(SimpleTestCase):
    def test_unknown_attributes_do_not_negate_an_independently_affirmed_condition(self):
        for term, attribute in [('constipation','subtype'), ('heartburn','cause'),
                                ('headache','severity'), ('diabetes','type')]:
            positive = f'The patient reports {term}.'
            for detail in [f'No underlying cause or {term} {attribute} has been established.',
                           f'The {attribute} of {term} is not established.',
                           f'No {attribute} of severe {term} has been established.',
                           f'The {term} {attribute} is uncertain.']:
                note = positive+' '+detail
                with self.subTest(note=note):
                    self.assertEqual(engine.source_disposition(concept(term,positive),note),('eligible',''))
                    # Attributes alone do not establish a present condition,
                    # even if a provider calls the concept confirmed.
                    self.assertNotEqual(engine.source_disposition(concept(term,detail),detail)[0],'eligible')
                    self.assertNotEqual(engine.source_disposition(concept(term,term),detail)[0],'eligible')

    def test_attribute_mentions_cannot_mask_condition_denials_or_uncertainty(self):
        positive = 'The patient reports constipation.'
        for detail in [
            'No constipation subtype has been established and the patient denies constipation.',
            'No constipation subtype or constipation has been established.',
            'No evidence of constipation.', 'No signs of constipation.',
            'No diagnosis of constipation.', 'Constipation has not been confirmed.',
            'Constipation is suspected.', 'Constipation is absent.',
            'No constipation-type symptoms are present.',
        ]:
            with self.subTest(detail=detail):
                self.assertEqual(engine.source_disposition(concept('constipation',positive),positive+' '+detail)[0],'question')

    def test_denied_uncertain_family_and_resolved_disease_stay_separate(self):
        for note, changes in [
            ('The patient denies constipation.', {'certainty':'negated'}),
            ('Possible constipation is being evaluated.', {'certainty':'uncertain','kind':'diagnosis'}),
            ('Constipation resolved in 2018.', {}),
            ('The patient previously had constipation.', {'temporality':'historical'}),
            ('Mother has constipation.', {'subject':'family','kind':'diagnosis'}),
        ]:
            with self.subTest(note=note):
                self.assertNotEqual(engine.source_disposition(concept('constipation',note,**changes),note)[0],'eligible')
        note='Mother has constipation. No constipation subtype has been established.'
        self.assertEqual(engine.source_disposition(concept('constipation','Mother has constipation.',
            subject='family',kind='family_history',temporality='historical'),note)[0],'eligible')
        # A faulty provider affirmation cannot turn a source-only denial into
        # a fabricated affirmative/negative contradiction.
        note='The patient denies constipation.'
        state,reason=engine.source_disposition(concept('constipation',note),note)
        self.assertEqual(state,'excluded')
        self.assertIn('source negates',reason)

    def test_mixed_condition_assertions_and_specific_subtype(self):
        for note in ['The patient denies nausea and reports constipation.',
                     'Constipation is documented; nausea is denied.',
                     'No nausea, but slow transit constipation is documented.']:
            with self.subTest(note=note):
                self.assertEqual(engine.source_disposition(concept('constipation',note),note)[0],'eligible')
        note='Slow transit constipation is documented. No underlying cause has been established.'
        self.assertEqual(engine.source_disposition(concept('slow transit constipation',note),note)[0],'eligible')

    def test_clipped_uncertainty_cannot_become_confirmed_disease(self):
        c=concept('GERD','GERD',kind='diagnosis')
        for source in ['Possible GERD is being evaluated.','GERD is suspected.']:
            with self.subTest(source=source):
                self.assertNotEqual(engine.source_disposition(c,source)[0],'eligible')

    def test_clipped_negation_cannot_become_current_disease(self):
        c=concept('GERD','GERD',kind='diagnosis')
        for source in ['The patient denies GERD.','GERD is absent.']:
            with self.subTest(source=source):
                self.assertNotEqual(engine.source_disposition(c,source)[0],'eligible')

    def test_unrelated_negation_does_not_erase_supported_diagnosis(self):
        note='The patient has GERD without dysphagia.'
        self.assertEqual(engine.source_disposition(concept('GERD',note,kind='diagnosis'),note)[0],'eligible')
        note='No nausea, but current heartburn.'
        self.assertEqual(engine.source_disposition(concept('heartburn','current heartburn'),note)[0],'eligible')

    def test_family_subject_cannot_be_removed_by_clipping(self):
        c=concept('colon polyps','colon polyps',kind='diagnosis')
        self.assertNotEqual(engine.source_disposition(c,"The patient's mother had colon polyps.")[0],'eligible')
        c=concept('colon polyps','colon polyps',kind='family_history',subject='family')
        self.assertNotEqual(engine.source_disposition(c,'The patient has colon polyps.')[0],'eligible')

    def test_positive_family_history_remains_eligible(self):
        note="The patient's mother had colon polyps at age 63."
        c=concept('colon polyps',note,kind='family_history',subject='family',temporality='historical')
        self.assertEqual(engine.source_disposition(c,note)[0],'eligible')
        self.assertTrue(engine.specificity_errors(c,'Z83.710','Family history of adenomatous and serrated polyps'))

    def test_documented_histology_cannot_be_guessed_or_downgraded(self):
        c=concept('colon polyps','Mother had adenomatous colon polyps.',kind='family_history',subject='family')
        self.assertTrue(engine.specificity_errors(c,'Z83.719','Family history of colon polyps, unspecified'))
        c['evidence']='Mother had non-adenomatous colon polyps.'
        self.assertTrue(engine.specificity_errors(c,'Z83.710','Family history of adenomatous and serrated polyps'))

    def test_contradictory_mentions_are_held(self):
        note='The patient reports heartburn. The patient denies heartburn.'
        self.assertEqual(engine.source_disposition(concept('heartburn','The patient reports heartburn.'),note)[0],'question')

    def test_plans_and_history_never_become_performed_procedures(self):
        for note,timing in [('Colonoscopy is planned for next month.','planned'),('Appendectomy was performed in 2008.','historical')]:
            c=concept(note.split()[0],note,kind='procedure',temporality=timing)
            self.assertEqual(engine.source_disposition(c,note)[0],'excluded')
        c=concept('colonoscopy','colonoscopy',kind='procedure')
        self.assertNotEqual(engine.source_disposition(c,'We plan colonoscopy next month.')[0],'eligible')

    def test_laterality_cannot_be_guessed_or_discarded(self):
        c=concept('wrist pain','The patient has left wrist pain.')
        self.assertTrue(engine.specificity_errors(c,'M25.531','Pain in right wrist'))
        self.assertTrue(engine.specificity_errors(c,'M25.539','Pain in unspecified wrist'))
        self.assertFalse(engine.specificity_errors(c,'M25.532','Pain in left wrist'))

    def test_identity_answers_do_not_depend_on_extractor(self):
        item=run('Synthetic Other Patient feels well.',patient_name_answers=[{'key':'name','label':'Patient name','text':'Synthetic Other Patient'}])
        result={'documented_patient_name':'','patient_name_evidence':''}
        self.assertTrue(engine.identity_blockers(item,result))
        item.context['identity_review_reason']='Owner confirms intentional reuse of this synthetic source.'
        self.assertEqual(engine.identity_blockers(item,result),[])
        with override_settings(SYNTHETIC_ONLY=False): self.assertTrue(engine.identity_blockers(item,result))

    def test_matching_extracted_identity_needs_no_reuse_exception(self):
        name = 'Synthetic Coding Linden Ash'
        note = name + ' reports heartburn and constipation.'
        item = run(note, patient_identity={'display_name':name},
                   patient_name_answers=[{'key':'name','label':'Patient name','text':name}])
        original = deepcopy(item.inputs)
        self.assertEqual(engine.identity_blockers(item, {
            'documented_patient_name':name, 'patient_name_evidence':note}), [])
        self.assertNotIn('identity_review_reason', item.context)
        self.assertEqual(item.inputs, original)

    def test_extracted_identity_mismatch_is_not_a_general_synthetic_bypass(self):
        name = 'Synthetic Different Patient'
        note = name + ' reports heartburn.'
        item = run(note)
        extracted = {'documented_patient_name':name, 'patient_name_evidence':note}
        for reason in ['', '   ', 'test']:
            with self.subTest(reason=reason):
                item.context['identity_review_reason'] = reason
                self.assertTrue(engine.identity_blockers(item, extracted))
        item.context['identity_review_reason'] = 'Owner confirms this specific intentional synthetic source reuse.'
        self.assertEqual(engine.identity_blockers(item, extracted), [])
        with override_settings(SYNTHETIC_ONLY=False):
            self.assertTrue(engine.identity_blockers(item, extracted))
        fresh = run(note)
        self.assertTrue(engine.identity_blockers(fresh, extracted))

    def test_identity_exception_does_not_waive_exact_source_evidence(self):
        item = run('Synthetic Different Patient reports heartburn.')
        item.context['identity_review_reason'] = 'Owner confirms this specific intentional synthetic source reuse.'
        for extracted in [
            {'documented_patient_name':'Synthetic Different Patient', 'patient_name_evidence':'reports heartburn.'},
            {'documented_patient_name':'Synthetic Invented Patient', 'patient_name_evidence':'Synthetic Invented Patient reports heartburn.'},
        ]:
            with self.subTest(extracted=extracted), self.assertRaises(ValidationError):
                engine.identity_blockers(item, extracted)

    def test_source_quote_is_exact_and_offsets_are_retained(self):
        self.assertEqual(engine.evidence_span('A. A.','A.')['occurrences'],[0,3])
        with self.assertRaises(ValidationError): engine.evidence_span('Heartburn.','heartburn')

    def test_unknown_setting_sends_nothing(self):
        item=run('Heartburn.');item.context['setting']='unknown'
        ref=SimpleNamespace(release=SimpleNamespace(version='FY2027'))
        with patch.object(engine,'reference_for',return_value=ref),patch.object(engine.coding_provider,'execute') as send:
            result=engine.generate(item)
        send.assert_not_called();self.assertTrue(result['global_blockers'])

    def test_mandatory_redirect_and_arbitrary_sibling_not_selectable(self):
        ref=SimpleNamespace(tabular={'codes':{'Z83.719':'Family history of colon polyps, unspecified','Z83.710':'Family history of adenomatous and serrated polyps'}})
        self.assertEqual(engine.code_variants(ref,{'code':'Z83.719','requires_review':True}),[])
        self.assertEqual(engine.code_variants(ref,{'code':'Z83.719'}),['Z83.719'])


def regression_reference():
    """Small public FY2027 paths/instructions in a synthetic XML wrapper.

    These cases were established against the full official release before the
    engine fixes. This excerpt makes the counterexamples repeatable without
    downloading a catalogue or invoking a database/provider in the test suite.
    """
    index = '''<ICD10CM.index><version>2027</version><letter>
      <mainTerm><title>Heartburn</title><code>R12</code>
        <term><title>psychogenic</title><code>F45.8</code></term></mainTerm>
      <mainTerm><title>Constipation<nemod>(atonic) (neurogenic) (simple) (spastic)</nemod></title><code>K59.00</code>
        <term><title>slow transit</title><code>K59.01</code></term></mainTerm>
      <mainTerm><title>GERD<nemod>(gastroesophageal reflux disease)</nemod></title><code>K21.9</code></mainTerm>
      <mainTerm><title>Disease</title><term><title>gastroesophageal reflux</title><code>K21.9</code></term></mainTerm>
      <mainTerm><title>Polyp</title><term><title>colon</title><code>K63.5</code></term></mainTerm>
      <mainTerm><title>History</title><term><title>family<nemod>(of)</nemod></title>
        <term><title>colonic polyps</title><code>Z83.719</code>
          <term><title>adenomatous and serrated</title><code>Z83.710</code></term></term></term>
        <term><title>personal</title><term><title>neoplasm</title><term><title>benign</title>
          <term><title>colon polyp</title><code>Z86.0100</code></term></term></term></term></mainTerm>
      <mainTerm><title>Screening<nemod>(for)</nemod></title><term><title>colonoscopy</title><code>Z12.11</code></term></mainTerm>
      </letter></ICD10CM.index>'''
    codes = {'R12':'Heartburn', 'F45.8':'Other somatoform disorders',
             'K59.00':'Constipation, unspecified', 'K59.01':'Slow transit constipation',
             'K21.9':'Gastro-esophageal reflux disease without esophagitis', 'K63.5':'Polyp of colon',
             'Z83.719':'Family history of colon polyps, unspecified',
             'Z83.710':'Family history of adenomatous and serrated polyps',
             'Z86.0100':'Personal history of colon polyps, unspecified',
             'Z12.11':'Encounter for screening for malignant neoplasm of colon'}
    nodes = ''.join(f'<diag><name>{code}</name><desc>{codes[code]}</desc></diag>'
                    for code in ('R12','F45.8','K21.9','K63.5','K59.00','K59.01'))
    tabular = f'''<ICD10CM.tabular><version>2027</version><chapter><name>1</name>
      <section id="synthetic-wrapper">{nodes}</section></chapter><chapter><name>21</name>
      <section id="Z00-Z13"><diag><name>Z12</name><desc>Encounter for screening for malignant neoplasms</desc>
        <useAdditionalCode><note>code to identify any family history of malignant neoplasm (Z80.-)</note></useAdditionalCode>
        <excludes1><note>encounter for diagnostic examination-code to sign or symptom</note></excludes1>
        <diag><name>Z12.11</name><desc>{codes['Z12.11']}</desc></diag></diag></section>
      <section id="Z77-Z99"><codeAlso><note>any follow-up examination (Z08-Z09)</note></codeAlso>
        <diag><name>Z83.719</name><desc>{codes['Z83.719']}</desc></diag>
        <diag><name>Z83.710</name><desc>{codes['Z83.710']}</desc></diag>
        <diag><name>Z86</name><desc>Personal history of certain other diseases</desc>
          <codeFirst><note>any follow-up examination after treatment (Z09)</note></codeFirst>
          <diag><name>Z86.0100</name><desc>{codes['Z86.0100']}</desc></diag></diag>
      </section></chapter></ICD10CM.tabular>'''
    return SimpleNamespace(**parse_reference(index, tabular, codes),
                           release_id='synthetic-reference', release=SimpleNamespace(version='FY2027'))


@override_settings(SYNTHETIC_ONLY=True)
class CodingEngineDemonstratedRegressionTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reference = regression_reference()

    def generate_rows(self, notes, concepts, wanted):
        item = run(notes)
        def response(_run, stage, payload, *_args):
            if stage == 'concepts':
                return {'documented_patient_name':'', 'patient_name_evidence':'', 'concepts':concepts}
            choices = []
            for current in payload['concepts']:
                candidate = next((c for c in payload['candidates'][current['id']]
                                  if c['code'] == wanted[current['id']]), None)
                choices.append({'concept_id':current['id'], 'entry_id':candidate['entry_id'] if candidate else '',
                    'code':candidate['code'] if candidate else '', 'explanation':'Choose only a supplied candidate.',
                    'missing_detail':'' if candidate else 'The requested code was not supplied.'})
            return {'choices':choices}
        def code_lookup(**kwargs):
            return SimpleNamespace(first=lambda:SimpleNamespace(description=self.reference.tabular['codes'][kwargs['code']]))
        with patch.object(engine, 'reference_for', return_value=self.reference), \
             patch.object(engine.coding_provider, 'execute', side_effect=response), \
             patch('core.coding_licensing.cpt_status', return_value={'available':False}), \
             patch.object(engine.Code.objects, 'filter', side_effect=code_lookup):
            item.result = engine.generate(item)
            selected = [row['id'] for row in item.result['suggestions']]
            engine.validate_selection(item, {'selected_ids':selected, 'overrides':{}})
        return item.result

    def assert_codes(self, notes, current, requested, expected):
        result = self.generate_rows(notes, [current], {current['id']:requested})
        self.assertEqual([r['code'] for r in result['suggestions']], expected)
        return result

    def test_affirmed_condition_with_unspecified_attribute_reaches_resolution_and_approval(self):
        # These two Index routes/descriptions were verified against retained
        # official FY2027 XML; this reduced fixture tests orchestration only.
        positive='The patient reports constipation.'
        detail='No underlying cause or constipation subtype has been established.'
        notes=positive+' '+detail
        result=self.assert_codes(notes,concept('constipation',positive),'K59.00',['K59.00'])
        check=result['source_checks']['c1']
        self.assertEqual(check['disposition'],'eligible')
        self.assertEqual([s['quote'] for s in check['condition_assertions']],[positive])
        self.assertEqual([s['quote'] for s in check['attribute_assertions']],[detail])
        self.assertFalse(any(q['system']=='ICD-10-CM' for q in result['questions']))
        self.assertEqual([q['id'] for q in result['questions']],['office_em'])
        row=result['suggestions'][0]
        self.assertTrue(row['eligible'])
        self.assertEqual(notes[row['evidence_span']['start']:row['evidence_span']['end']],positive)

    def test_catalogue_membership_does_not_override_unsupported_assertion(self):
        for notes, changes in [
            ('No constipation.', {'certainty':'negated'}),
            ('Possible constipation.', {'certainty':'uncertain','kind':'diagnosis'}),
            ('Constipation resolved in 2018.', {}),
            ('Mother has constipation.', {'kind':'diagnosis'}),
            ('No constipation subtype is established.', {}),
            ('The patient reports constipation. The patient denies constipation.', {}),
        ]:
            with self.subTest(notes=notes):
                result=self.assert_codes(notes,concept('constipation',notes,**changes),'K59.00',[])
                self.assertNotEqual(result['source_checks']['c1']['disposition'],'eligible')
                self.assertNotIn('c1',result['candidates'])

    def test_specific_subtype_requires_its_documented_index_route(self):
        notes='The patient has slow transit constipation.'
        self.assert_codes(notes,concept('constipation',notes,index_terms=['Constipation slow transit']),
                          'K59.01',['K59.01'])
        notes='The patient has constipation. The subtype is not documented.'
        self.assert_codes(notes,concept('constipation',notes,index_terms=['Constipation slow transit']),
                          'K59.01',[])

    def test_default_cannot_discard_specific_subtype_in_complete_source(self):
        for notes,evidence in [
            ('The patient has slow transit constipation.','The patient has slow transit constipation.'),
            ('The patient has constipation. Slow transit constipation is documented.','The patient has constipation.'),
            ('The patient has constipation. The subtype of constipation is slow transit.','The patient has constipation.'),
        ]:
            with self.subTest(notes=notes):
                result=self.assert_codes(notes,concept('Constipation',evidence),'K59.00',[])
                self.assertTrue(result['source_checks']['c1']['specificity_holds'])
        note='The patient has slow transit constipation.'
        for label in ['Unspecified constipation','Difficulty passing stool','Slow transit constipation']:
            with self.subTest(label=label):
                self.assert_codes(note,concept(label,note,index_terms=['Constipation']),'K59.00',[])

    def test_another_subjects_attribute_does_not_supply_patient_specificity(self):
        quote='The patient reports constipation.'
        for owner in ["The nurse's", "The husband's", "The mother's", 'The physician’s']:
            note=quote+' '+owner+' constipation type is slow transit.'
            with self.subTest(owner=owner):
                self.assert_codes(note,concept('Constipation',quote),'K59.00',['K59.00'])
        note=quote+' The nurse denies constipation.'
        self.assert_codes(note,concept('Constipation',quote),'K59.00',['K59.00'])
        for reporter in ['The doctor has confirmed that the patient', 'The physician reports that the patient']:
            note=quote+' '+reporter+' has no constipation.'
            with self.subTest(reporter=reporter):
                result=self.assert_codes(note,concept('Constipation',quote),'K59.00',[])
                self.assertEqual(result['source_checks']['c1']['disposition'],'question')

    def test_negated_index_subtype_does_not_negate_affirmed_parent(self):
        quote='The patient reports constipation.'
        for suffix in ['Slow transit constipation is not established.',
                       'Slow transit constipation is suspected.', 'No slow transit constipation.']:
            with self.subTest(suffix=suffix):
                result=self.assert_codes(quote+' '+suffix,concept('Constipation',quote),'K59.00',['K59.00'])
                self.assertEqual(result['source_checks']['c1']['disposition'],'eligible')
                self.assertEqual(result['source_checks']['c1']['attribute_assertions'][0]['quote'],suffix)
                self.assert_codes(quote+' '+suffix,concept('Constipation',quote,
                    index_terms=['Constipation','Slow transit constipation']),'K59.00',['K59.00'])
        note='The patient has constipation and slow transit nausea.'
        self.assert_codes(note,concept('Constipation',note),'K59.00',['K59.00'])

    def test_conflicting_extractions_have_one_consistent_source_verdict(self):
        notes='The patient reports constipation. The patient denies constipation.'
        concepts=[concept('constipation','The patient reports constipation.'),
                  concept('constipation','The patient denies constipation.',id='c2',certainty='negated')]
        result=self.generate_rows(notes,concepts,{'c1':'K59.00','c2':'K59.00'})
        self.assertEqual(result['suggestions'],[])
        self.assertEqual(result['excluded'],[])
        for key in ('c1','c2'):
            check=result['source_checks'][key]
            self.assertEqual(check['disposition'],'question')
            self.assertEqual([q['question'] for q in result['questions'] if q['id']==key],[check['reason']])

    def test_bare_symptom_cannot_select_psychogenic_child_or_disease_route(self):
        for terms, code in [(['Heartburn'],'F45.8'), (['Disease gastroesophageal reflux'],'K21.9')]:
            with self.subTest(terms=terms):
                c=concept('heartburn','Heartburn.',index_terms=terms)
                self.assert_codes('Heartburn.',c,code,[])
        self.assert_codes('Heartburn.',concept('heartburn','Heartburn.'),'R12',['R12'])

    def test_family_taxonomy_does_not_establish_an_unmentioned_condition(self):
        note="The patient's mother has heartburn."
        c=concept('heartburn',note,index_terms=['History family colonic polyps'],kind='family_history',subject='family')
        self.assert_codes(note,c,'Z83.719',[])

    def test_patient_and_heading_owned_family_findings_cannot_swap_roles(self):
        for note, evidence in [("The patient's mother had colon polyps.",'colon polyps'),
                               ('Family history:\nMother:\nColon polyps.','Colon polyps.')]:
            with self.subTest(note=note):
                self.assert_codes(note,concept('colon polyps',evidence,index_terms=['Polyp colon'],kind='diagnosis'),'K63.5',[])
        note='The patient has colon polyps.'
        c=concept('colon polyps',note,index_terms=['History family colonic polyps'],kind='family_history',subject='family')
        self.assert_codes(note,c,'Z83.719',[])

    def test_postposed_uncertainty_negation_and_resolved_history_override_model_labels(self):
        for note in ['GERD is suspected.','GERD is absent.','GERD has not been confirmed.','GERD resolved in 2018.']:
            with self.subTest(note=note):
                self.assert_codes(note,concept('GERD',note,kind='diagnosis'),'K21.9',[])

    def test_negated_branch_cannot_supply_missing_specificity(self):
        note='Heartburn. A psychogenic cause is not diagnosed.'
        self.assert_codes(note,concept('heartburn',note),'F45.8',[])
        note="The patient's mother had non-adenomatous colon polyps."
        c=concept('colon polyps',note,index_terms=['History family colonic polyps adenomatous'],kind='family_history',subject='family')
        self.assert_codes(note,c,'Z83.710',[])

    def test_official_and_title_accepts_either_documented_alternative(self):
        for histology in ['adenomatous','serrated']:
            note=f"The patient's mother had {histology} colon polyps."
            c=concept('colon polyps',note,index_terms=['History family colonic polyps '+histology],kind='family_history',subject='family')
            with self.subTest(histology=histology): self.assert_codes(note,c,'Z83.710',['Z83.710'])

    def test_source_causality_excludes_integral_symptom_without_model_link(self):
        note='The patient has GERD causing heartburn.'
        concepts=[concept('GERD',note,kind='diagnosis'),concept('heartburn',note,id='c2')]
        result=self.generate_rows(note,concepts,{'c1':'K21.9','c2':'R12'})
        self.assertEqual([r['code'] for r in result['suggestions']],['K21.9'])
        self.assertEqual([r['concept_id'] for r in result['excluded']],['c2'])

    def test_patient_profession_and_physician_report_do_not_transfer_ownership(self):
        for note in ['The patient is a doctor with GERD.','The physician reports that the patient has GERD.']:
            with self.subTest(note=note):
                self.assert_codes(note,concept('GERD',note,kind='diagnosis'),'K21.9',['K21.9'])
        note='The referring doctor has GERD.'
        self.assert_codes(note,concept('GERD',note,kind='diagnosis'),'K21.9',[])

    def test_complete_quote_does_not_absorb_later_family_sentence(self):
        quote='The patient has GERD.'
        self.assert_codes(quote+" The patient's mother had colon polyps.",
                          concept('GERD',quote,kind='diagnosis'),'K21.9',['K21.9'])

    def screening(self, suffix=''):
        quote='Asymptomatic patient here specifically for colon cancer screening; screening colonoscopy is planned.'
        current=concept('screening',quote,index_terms=['Screening colonoscopy'],kind='reason')
        return quote+suffix,current

    def test_screening_without_family_malignancy_does_not_invent_additional_code(self):
        for suffix in ['', ' No family history of malignant neoplasm.']:
            notes,current=self.screening(suffix)
            with self.subTest(suffix=suffix): self.assert_codes(notes,current,'Z12.11',['Z12.11'])

    def test_screening_with_family_malignancy_retains_unresolved_instruction(self):
        for suffix in [' Mother had colon cancer.','\nFamily history:\nMother:\nColon cancer.']:
            notes,current=self.screening(suffix)
            with self.subTest(suffix=suffix):
                result=self.assert_codes(notes,current,'Z12.11',[])
                self.assertTrue(any('family history of malignant neoplasm' in q['question'] for q in result['questions']))

    def test_later_same_procedure_diagnostic_correction_cannot_be_clipped_away(self):
        notes,current=self.screening(" Correction: the same colonoscopy is diagnostic for the patient's current abdominal pain.")
        result=self.assert_codes(notes,current,'Z12.11',[])
        self.assertTrue(any('diagnostic examination' in q['question'] for q in result['questions']))

    def test_personal_history_follow_up_condition_is_evaluated_from_whole_source(self):
        quote='The patient previously had a colon polyp removed.'
        current=concept('colon polyp',quote,index_terms=['History personal neoplasm benign colon polyp'],kind='personal_history',temporality='historical')
        self.assert_codes(quote,current,'Z86.0100',['Z86.0100'])
        result=self.assert_codes(quote+' This is a follow-up examination after completed treatment.',current,'Z86.0100',[])
        self.assertTrue(any('follow-up examination after treatment' in q['question'] for q in result['questions']))


def complete_concept(**changes):
    return {'id':'c1', 'term':'heartburn', 'index_terms':['Heartburn'],
            'evidence':'The patient has heartburn.', 'kind':'symptom',
            'certainty':'confirmed', 'temporality':'current', 'subject':'patient',
            'relevant':True, 'missing_detail':'', 'integral_to':'', **changes}


def extraction(concepts):
    return {'documented_patient_name':'', 'patient_name_evidence':'', 'concepts':concepts}


class CodingConceptValidationTests(SimpleTestCase):
    def test_retained_empty_placeholder_reply_is_rejected(self):
        # Exact nonclinical placeholder shape from the retained invalid reply.
        reply = extraction([{'certainty':'confirmed', 'evidence':'', 'id':'',
            'index_terms':[' '], 'integral_to':' ', 'kind':'reason', 'missing_detail':' ',
            'relevant':True, 'subject':'patient', 'temporality':'current', 'term':' '}])
        original = deepcopy(reply)
        with self.assertRaises(PydanticValidationError) as caught:
            engine.Concepts.model_validate(reply, strict=True)
        locations = {tuple(e['loc']) for e in caught.exception.errors()}
        for name in ('id', 'term', 'evidence', 'index_terms'):
            self.assertIn(('concepts', 0, name), locations)
        self.assertEqual(reply, original)

    def test_required_clinical_strings_reject_blank_and_unicode_whitespace(self):
        for blank in ('', ' ', '\t\r\n', '\u00a0\u2003'):
            for field in ('term', 'evidence', 'index_terms'):
                value = [blank] if field == 'index_terms' else blank
                with self.subTest(field=field, value=blank), self.assertRaises(PydanticValidationError):
                    engine.Concept.model_validate(complete_concept(**{field:value}), strict=True)

    def test_each_index_term_must_be_nonblank(self):
        for terms in (['Heartburn', ' '], ['\t', 'Heartburn']):
            with self.subTest(terms=terms), self.assertRaises(PydanticValidationError):
                engine.Concept.model_validate(complete_concept(index_terms=terms), strict=True)

    def test_supported_complete_concept_preserves_exact_source_strings(self):
        notes = '\tThe patient has heartburn.\r\n'
        concept = complete_concept(term=' heartburn ', index_terms=[' Heartburn\t'], evidence=notes)
        reply = extraction([concept])
        original = deepcopy(reply)
        parsed = engine.Concepts.model_validate(reply, strict=True).model_dump()
        self.assertEqual(parsed, original)
        self.assertEqual(reply, original)
        self.assertEqual(engine.source_disposition(parsed['concepts'][0], notes)[0], 'eligible')
        self.assertEqual(parsed['concepts'][0]['evidence'].encode(), notes.encode())

    def test_empty_extraction_and_optional_absent_details_are_not_fabricated(self):
        self.assertEqual(engine.Concepts.model_validate(extraction([]), strict=True).model_dump(), extraction([]))
        concept = complete_concept()
        self.assertEqual(engine.Concept.model_validate(concept, strict=True).model_dump(), concept)

    def test_closed_schema_and_strict_types_remain_required(self):
        for change in ({'term':False}, {'evidence':None}, {'index_terms':'Heartburn'},
                       {'index_terms':[1]}, {'code':'R12'}, {'id':'placeholder'}):
            with self.subTest(change=change), self.assertRaises(PydanticValidationError):
                engine.Concept.model_validate(complete_concept(**change), strict=True)

    def test_invalid_extraction_cannot_reach_resolution_or_change_saved_input(self):
        item = SimpleNamespace(inputs={'notes':'The patient has heartburn.', 'answers':{},
            'service_date':'2026-10-14'}, context={'setting':'outpatient_office'}, releases=[])
        original = deepcopy(item.inputs)
        reference = SimpleNamespace(release=SimpleNamespace(version='synthetic-reference'))
        reply = extraction([complete_concept(index_terms=[' '])])
        with patch.object(engine, 'reference_for', return_value=reference), \
             patch.object(engine.coding_provider, 'execute', return_value=reply) as send:
            with self.assertRaises(PydanticValidationError):
                engine.generate(item)
        send.assert_called_once()
        self.assertEqual(send.call_args.args[1], 'concepts')
        self.assertEqual(item.inputs, original)

    def test_anthropic_wire_schema_preserves_guidance_but_local_constraints_still_apply(self):
        local = engine.Concepts.model_json_schema()
        original = deepcopy(local)
        wire = transform_schema(local)
        local_fields = local['$defs']['Concept']['properties']
        wire_fields = wire['$defs']['Concept']['properties']
        for name in ('id', 'term', 'index_terms', 'evidence'):
            with self.subTest(field=name):
                self.assertTrue(local_fields[name].get('description'))
                self.assertIn(local_fields[name]['description'], wire_fields[name]['description'])
        self.assertNotIn('pattern', wire_fields['id'])
        self.assertIn('pattern', wire_fields['id']['description'])
        self.assertNotIn('minLength', wire_fields['evidence'])
        self.assertIn('minLength', wire_fields['evidence']['description'])
        self.assertEqual(local, original)
        with self.assertRaises(PydanticValidationError):
            engine.Concept.model_validate(complete_concept(evidence=' '), strict=True)

    def test_transport_gets_complete_data_and_explicit_guidance_once_without_network(self):
        class SendBoundary(Exception): pass
        payload = {'notes':'The patient has heartburn.\r\nNo dysphagia.',
                   'answers':{'finding':{'text':'Heartburn; no dysphagia', 'status':'supported'}},
                   'service_date':'2026-10-14', 'setting':'outpatient_office'}
        original = deepcopy(payload)
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.side_effect = SendBoundary
            with self.assertRaises(SendBoundary):
                ai_stages._response(payload, engine.Concepts, engine.CONCEPT_INSTRUCTIONS,
                    {'provider':'anthropic', 'model':'offline-synthetic-model'}, 8000, 120,
                    lambda _: self.fail('No response or transport was authorized.'))
        client.assert_called_once_with(timeout=120, max_retries=0)
        client.return_value.messages.create.assert_called_once()
        request = client.return_value.messages.create.call_args.kwargs
        import json
        self.assertEqual(json.loads(request['messages'][0]['content']), original)
        self.assertEqual(payload, original)
        self.assertEqual(request['output_config']['format']['schema'], transform_schema(engine.Concepts))
        self.assertIn('c1, c2', request['system'])
        self.assertIn('whitespace', request['system'].lower())
        self.assertIn('placeholder', request['system'])
        self.assertEqual(engine.CONTRACT, 'us-outpatient-index-tabular-v4')
