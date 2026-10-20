"""Fresh Word capability and exact-value regressions; zero provider calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch
from docx import Document
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from core import preparation, word_contract, semantic_generation as semantic
from core.semantic_preparation import validated_semantic_definitions
from core.semantic_review import definitions_for
from core.template_source import approval_binding, source_for_version
from core.tests.test_semantic_generation import fact, span, assignments, FixtureSender
from documents.preparation import inventory, TYPED_PROTOCOL
from documents.semantic_preparation_roles import default_definitions, validate_definitions


THEO = ('Synthetic Theo Varen, clinic reference TEST-B942, attended a review visit on October 11, 2026. '
        'He reports left ankle soreness lasting two weeks and rates it as two out of ten. '
        'His measured temperature is 37.0 degrees Celsius. He reports that penicillin causes a rash. '
        'The clinician records left ankle discomfort as the impression and requests review in fourteen days.')
LABELS = ('Encounter category: Initial or Review', 'Clinic record reference', 'Person full name',
          'Date seen', 'Main reported concern', 'Symptoms present for', 'Patient rated intensity: 0 to 10',
          'Measured temperature: Degrees Celsius', 'Regular medicines or supplements', 'Drug allergy details',
          'Clinician recorded impression', 'Requested review interval')


class FreshWordContractTests(SimpleTestCase):
    def graph_config(self):
        from documents.component_contracts import CONFIG_KEY, ENCOUNTER_CONTRACT
        return {**self.config, word_contract.CONFIG_KEY:word_contract.GRAPH_PROFILE,
            'semantic_definition_version':4, CONFIG_KEY:ENCOUNTER_CONTRACT,
            'word_preparation_output_profile':preparation.COMPLETE_OUTPUT_PROFILE}

    def test_new_word_graph_profile_is_explicit_and_reuses_both_existing_component_roles(self):
        from documents.component_contracts import CONFIG_KEY, ENCOUNTER_CONTRACT
        config = self.graph_config()
        before = deepcopy(self.config)
        old = preparation.provider_request(self.inv,'proposer',self.config)
        proposal = None
        for role in ('proposer','checker'):
            response,evidence = preparation.provider_role(self.inv,role,config,1,proposal)
            word_contract.validate_result(self.inv,response,role,config)
            definitions = response['answer_definitions']['fields']
            self.assertTrue(all(row['definition']['version']==4 for row in definitions))
            self.assertTrue(all(row['definition']['component_contract']['contract']==ENCOUNTER_CONTRACT for row in definitions))
            self.assertEqual([row['field_key'] for row in definitions],[field['key'] for field in self.fields])
            request = preparation.provider_request(self.inv,role,config,proposal)
            self.assertIn('Use definition version 4',request['system'])
            self.assertIn(ENCOUNTER_CONTRACT,request['system'])
            self.assertLessEqual(request['max_tokens'],preparation.MAX_COMPLETE_OUTPUT)
            self.assertLessEqual(len(json.dumps(request,ensure_ascii=False).encode()),preparation.MAX_PREPARATION_REQUEST_BYTES)
            self.assertTrue(evidence['simulated'])
            proposal = response
        self.assertEqual(self.config,before)
        self.assertEqual(old,preparation.provider_request(self.inv,'proposer',self.config))
        self.assertEqual(word_contract.definition_version(self.config),2)
        missing = deepcopy(config);del missing[CONFIG_KEY]
        with self.assertRaises(ValidationError):
            preparation.provider_request(self.inv,'proposer',missing)
        old_response,_ = preparation.provider_role(self.inv,'proposer',self.config,1)
        with self.assertRaisesMessage(ValidationError,'complete answer contract'):
            word_contract.validate_result(self.inv,old_response,'proposer',config)

    def test_new_inline_component_approval_preserves_the_original_destination_and_profile(self):
        version = self.version()
        prep = version.preparation
        config = self.graph_config()
        proposal,_ = preparation.provider_role(self.inv,'proposer',config,1)
        checker,_ = preparation.provider_role(self.inv,'checker',config,1,proposal)
        original = deepcopy((proposal,checker,self.fields))
        prep.config,prep.proposal,prep.checker = config,proposal,checker
        prep.candidate_info.pop(word_contract.INFO_KEY)
        values = word_contract.proposed(prep)
        word_contract.seal(prep,list(values),SimpleNamespace(pk='doctor'))
        prep.approval_sha256 = approval_binding(prep)
        self.assertEqual(word_contract.require_generation(version),values)
        self.assertTrue(all(value['version']==4 for value in values.values()))
        self.assertEqual(prep.candidate_info[word_contract.INFO_KEY]['profile'],word_contract.GRAPH_PROFILE)
        self.assertEqual((proposal,checker,self.fields),original)
        invalid = deepcopy(values)
        invalid[next(iter(invalid))]['version'] = 2
        prep.corrections['answer_definitions'] = invalid
        with self.assertRaises((ValidationError,ValueError)):
            word_contract.proposed(prep)

    def test_unresolved_semantic_result_cannot_be_sealed_by_review_checkboxes_or_layout_corrections(self):
        for role in ('proposal', 'checker'):
            for correction in ({}, {'labels': {'cell_2': 'Person full name'}}):
                with self.subTest(role=role, correction=correction):
                    prep = self.version().preparation
                    prep.candidate_info.pop(word_contract.INFO_KEY)
                    row = next(r for r in getattr(prep, role)['answer_definitions']['fields']
                               if r['field_key'] == 'cell_2')
                    row.update(state='unresolved', reason='Clarify whose name belongs here.')
                    # Enum-valid patient scope was the actual fresh-upload counterexample.
                    self.assertEqual(row['definition']['scope']['subject'], 'patient')
                    prep.corrections = correction
                    before = deepcopy(prep.__dict__)
                    self.assertEqual(set(word_contract.approval_issues(prep)), {'cell_2'})
                    with self.assertRaisesMessage(ValidationError, 'Save doctor corrections'):
                        word_contract.seal(prep, list(self.definitions()), SimpleNamespace(pk='doctor'))
                    self.assertEqual(prep.__dict__, before)

    def test_complete_reviewed_definition_correction_resolves_but_does_not_replace_model_result(self):
        prep = self.version().preparation
        prep.candidate_info.pop(word_contract.INFO_KEY)
        row = prep.checker['answer_definitions']['fields'][2]
        row.update(state='unresolved', reason='Clarify whose name belongs here.')
        original = deepcopy((prep.proposal, prep.checker))
        values = self.definitions()
        values['cell_2']['meaning'] = 'The full name of the patient whose encounter is recorded.'
        for incomplete in ({'cell_0': values['cell_0']}, {k:v for k,v in values.items() if k != 'cell_2'}):
            prep.corrections = {'answer_definitions': incomplete}
            with self.assertRaises(ValueError): word_contract.approval_issues(prep)
        prep.corrections = {'answer_definitions': values, 'reason': 'Confirmed the patient section against the original.'}
        self.assertEqual(word_contract.approval_issues(prep), {})
        self.assertEqual(word_contract.review_rows(prep)[2]['state'], 'pass')
        word_contract.seal(prep, list(values), SimpleNamespace(pk='doctor'))
        self.assertEqual(prep.candidate_info[word_contract.INFO_KEY]['definitions'], values)
        self.assertEqual((prep.proposal, prep.checker), original)

    def test_historical_unresolved_seal_stays_readable_but_cannot_start_new_generation(self):
        version = self.version(); prep = version.preparation
        prep.checker['answer_definitions']['fields'][2].update(state='unresolved', reason='Choose the named person.')
        prep.approval_sha256 = approval_binding(prep)
        before = deepcopy(prep.__dict__)
        self.assertEqual(validated_semantic_definitions(version), self.definitions())
        self.assertEqual(source_for_version(version), self.root/'prepared.docx')
        with patch('core.ai_stages.maximum_cost') as quote, self.assertRaisesMessage(ValidationError, 'new answer-definition version'):
            word_contract.require_generation(version)
        quote.assert_not_called()
        self.assertEqual(prep.__dict__, before)

    def test_separate_approved_definitions_supersede_prior_inline_unresolved_decision(self):
        version = self.version()
        version.preparation.checker['answer_definitions']['fields'][2]['state'] = 'unresolved'
        version.semantic_preparation_id = 'separately-approved-version'
        version.semantic_definitions = self.definitions()
        # The existing reader owns the separate approval integrity check.
        with patch('core.semantic_preparation.validated_semantic_definitions', return_value=self.definitions()) as reader:
            self.assertEqual(word_contract.require_generation(version), self.definitions())
        reader.assert_called_once_with(version)

    def test_unspecified_identity_is_visible_but_cannot_receive_new_approval(self):
        prep = self.version().preparation
        prep.candidate_info.pop(word_contract.INFO_KEY)
        for response in (prep.proposal, prep.checker):
            for row in response['answer_definitions']['fields']:
                if row['field_key'] == 'cell_2':
                    row['definition']['scope']['subject'] = 'unspecified'
                    row['definition']['meaning'] = 'The full name of the person only.'
        before = deepcopy((prep.proposal, prep.checker, prep.corrections))
        row = next(row for row in word_contract.review_rows(prep) if row['key'] == 'cell_2')
        self.assertEqual(row['state'], 'unresolved')
        self.assertIn('Choose whose name', row['reason'])
        with self.assertRaisesMessage(ValidationError, 'Choose whose name'):
            word_contract.seal(prep, list(self.definitions()), SimpleNamespace(pk='doctor'))
        self.assertNotIn(word_contract.INFO_KEY, prep.candidate_info)
        self.assertEqual((prep.proposal, prep.checker, prep.corrections), before)

    def test_historical_identity_contract_stays_readable_but_cannot_start_new_generation(self):
        version = self.version(); prep = version.preparation
        # Represent a previously sealed ambiguous contract, without changing production data.
        for response in (prep.proposal, prep.checker):
            next(row for row in response['answer_definitions']['fields']
                 if row['field_key'] == 'cell_2')['definition']['scope']['subject'] = 'unspecified'
        prep.candidate_info[word_contract.INFO_KEY]['definitions']['cell_2']['scope']['subject'] = 'unspecified'
        prep.approval_sha256 = approval_binding(prep)
        before = deepcopy(prep.__dict__)
        self.assertEqual(validated_semantic_definitions(version)['cell_2']['scope']['subject'], 'unspecified')
        self.assertEqual(source_for_version(version), self.root/'prepared.docx')
        with patch('core.ai_stages.maximum_cost') as quote, self.assertRaisesMessage(ValidationError, 'Choose whose name'):
            word_contract.require_generation(version)
        quote.assert_not_called()
        self.assertEqual(prep.__dict__, before)

    def test_identity_capability_preserves_distinct_people_and_unrelated_scopes(self):
        from documents.semantic_preparation_roles import DefinitionError, require_identity_scopes
        values = self.definitions()
        for subject in ('patient', 'clinician', 'other'):
            values['cell_2']['scope']['subject'] = subject
            self.assertIs(require_identity_scopes(self.fields, values), values)
        for subject in ('encounter', 'unspecified'):
            values['cell_2']['scope']['subject'] = subject
            self.assertIs(validate_definitions(self.fields, values), values)  # historical reader
            with self.assertRaises(DefinitionError): require_identity_scopes(self.fields, values)
        values['cell_2']['scope']['subject'] = 'patient'
        values['cell_1']['scope']['subject'] = 'unspecified'
        values['cell_0']['scope']['subject'] = 'encounter'
        self.assertIs(require_identity_scopes(self.fields, values), values)
        for role in ('proposer', 'checker'):
            request = preparation.provider_request(self.inv, role, self.config,
                self.version().preparation.proposal if role == 'checker' else None)
            self.assertIn('person_name requires scope.subject', request['system'])
            self.assertIn('Do not make every name a patient name', request['system'])

    def test_new_preparation_frame_is_explicit_in_both_requests_and_the_immutable_seal(self):
        from documents.semantic_preparation_roles import TEMPORAL_REFERENCE_CONTRACT
        version = self.version()
        self.assertEqual(version.preparation.candidate_info[word_contract.INFO_KEY]['profile'], word_contract.PROFILE)
        for role in ('proposer','checker'):
            proposal = version.preparation.proposal if role=='checker' else None
            payload = preparation.role_payload(self.inv, role, proposal, config=self.config)
            request = preparation.provider_request(self.inv, role, self.config, proposal)
            self.assertEqual(payload['timing_reference_contract'], TEMPORAL_REFERENCE_CONTRACT)
            self.assertIn(TEMPORAL_REFERENCE_CONTRACT, request['system'])
            self.assertIn('scope.temporality any unless', request['system'])
        version.preparation.config[word_contract.CONFIG_KEY] = word_contract.LEGACY_PROFILE
        with self.assertRaises(ValidationError):
            word_contract.require_generation(version)

    def test_legacy_approved_profile_and_request_keep_their_original_frame(self):
        self.config[word_contract.CONFIG_KEY] = word_contract.LEGACY_PROFILE
        version = self.version()
        before = deepcopy(version.preparation.candidate_info)
        self.assertEqual(before[word_contract.INFO_KEY]['profile'], word_contract.LEGACY_PROFILE)
        self.assertEqual(word_contract.require_generation(version), self.definitions())
        self.assertEqual(version.preparation.candidate_info, before)
        for role in ('proposer','checker'):
            proposal = version.preparation.proposal if role=='checker' else None
            payload = preparation.role_payload(self.inv, role, proposal, config=self.config)
            request = preparation.provider_request(self.inv, role, self.config, proposal)
            self.assertNotIn('timing_reference_contract', payload)
            self.assertNotIn('documented-encounter-relative-v1', request['system'])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        setting = override_settings(MEDIA_ROOT=self.root)
        setting.enable(); self.addCleanup(setting.disable)
        doc = Document()
        for first in (0, 6):
            table = doc.add_table(rows=6, cols=2)
            for offset, row in enumerate(table.rows): row.cells[0].text = LABELS[first+offset]
        doc.save(self.root/'blank.docx')
        self.inv = inventory(self.root/'blank.docx', protocol=TYPED_PROTOCOL)
        self.fields = deepcopy(self.inv['fields'])
        self.config = {'mode':'fixture', 'provider':'anthropic', 'model':'offline',
            'word_preparation_output_profile':preparation.OUTPUT_PROFILE,
            word_contract.CONFIG_KEY:word_contract.PROFILE}

    def definitions(self):
        values = default_definitions(self.fields)
        kinds = ('choice','identifier','person_name','date','text','text','integer','number',
                 'text','text','text','text')
        for field, kind in zip(self.fields, kinds):
            value = values[field['key']]
            value.update(version=2, value_type=kind, answer_mode='narrative' if field['key'] in ('cell_8','cell_9') else 'atomic')
        values['cell_0']['choices'] = ['Initial','Review']
        values['cell_6']['constraints'] = dict(minimum='0',maximum='10',scale_minimum='0',scale_maximum='10')
        values['cell_7']['unit'] = 'Celsius'
        return validate_definitions(self.fields, values)

    def version(self):
        proposal, _ = preparation.provider_role(self.inv, 'proposer', self.config, 1)
        checked, _ = preparation.provider_role(self.inv, 'checker', self.config, 1, proposal)
        for result in (proposal, checked):
            for row in result['answer_definitions']['fields']:
                row['definition'] = self.definitions()[row['field_key']]
        raw = (self.root/'blank.docx').read_bytes(); (self.root/'prepared.docx').write_bytes(raw)
        template = SimpleNamespace(pk='template', format='docx', original_path='blank.docx', sha256=hashlib.sha256(raw).hexdigest())
        prep = SimpleNamespace(template=template, template_id='template', pk='preparation', inventory=self.inv,
            proposal=proposal, checker=checked, config=self.config, corrections={}, correction_history=[], revision=0,
            candidate_sha256=template.sha256, candidate_path='prepared.docx', changes=[],
            candidate_info={'fields':self.fields, 'document_backend':{}, 'review_requirements':[]},
            state='review', approved_by_id='doctor', approved_at=timezone.now())
        word_contract.seal(prep, list(self.definitions()), SimpleNamespace(pk='doctor'))
        prep.state='approved'; prep.approval_sha256=approval_binding(prep)
        return SimpleNamespace(pk='version', number=1, template=template, template_id='template', fields=self.fields,
            preparation_id='preparation', preparation=prep, prepared_path='prepared.docx', prepared_sha256=template.sha256,
            semantic_preparation_id=None, semantic_definitions={}, document_backend={}, review_requirements=[])

    def test_first_approved_mapping_version_is_semantic_through_every_shared_reader(self):
        version = self.version()
        self.assertEqual(version.number, 1)
        self.assertEqual(version.semantic_definitions, {})
        for reader in (validated_semantic_definitions, definitions_for, word_contract.require_generation):
            self.assertEqual(reader(version), self.definitions())
        self.assertEqual(source_for_version(version), self.root/'prepared.docx')
        from core.jobs import generation_maximum
        with patch('core.ai_stages.maximum_cost', return_value=17) as quote:
            self.assertEqual(generation_maximum(SimpleNamespace(template_version=version), self.config), 17)
        quote.assert_called_once()

    @override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
                                'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
    def test_preparation_detail_renders_before_inventory_or_both_role_results_exist(self):
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from core import preparation_views
        template = SimpleNamespace(pk='00000000-0000-0000-0000-000000000001',
            name='Fresh blank form', sha256='a'*64)
        for state, inv, proposal in [('queued', {}, {}), ('inventory', {}, {}),
                ('proposer', self.inv, {}), ('checker', self.inv, {'pending':True}),
                ('blocked', {}, {})]:
            with self.subTest(state=state):
                prep = SimpleNamespace(template=template, state=state, inventory=inv,
                    proposal=proposal, checker={}, config=self.config, candidate_info={},
                    corrections={}, candidate_path='', candidate_sha256='', changes=[],
                    started_at=None, finished_at=None, error_code='', revision=0,
                    receipts=Mock())
                prep.receipts.order_by.return_value=[]
                request=RequestFactory().get('/templates/'+template.pk+'/preparation/')
                request.user=AnonymousUser()
                with patch.object(preparation_views, 'selected', return_value=(template,prep)):
                    response=preparation_views.detail(request, template.pk)
                self.assertEqual(response.status_code, 200)
                html=response.content.decode()
                self.assertIn('data-state="'+state+'"', html)
                self.assertNotIn('name="reviewed_definition"', html)
                self.assertNotIn('Approve layout and create form version', html)

    def test_complete_review_keeps_all_definitions_and_rejects_malformed_contract(self):
        prep=self.version().preparation
        self.assertEqual(len(word_contract.review_rows(prep)),12)
        prep.checker['answer_definitions'].pop('fields')
        with self.assertRaises((ValidationError, ValueError)):
            word_contract.review_rows(prep)

    def test_missing_or_tampered_contract_never_downgrades(self):
        for name in ('payload','label','locator','definition','profile','reviewer','reviewed_fields'):
            version = deepcopy(self.version()); info = version.preparation.candidate_info
            if name == 'payload': info.pop(word_contract.INFO_KEY)
            if name == 'label': version.fields[0]['label'] = 'Changed question'
            if name == 'locator': version.fields[0]['locator'] = {'cell':99}
            if name == 'definition': info[word_contract.INFO_KEY]['definitions']['cell_0']['choices'].append('Invented')
            if name == 'profile': version.preparation.config[word_contract.CONFIG_KEY] = None
            if name == 'reviewer': info[word_contract.INFO_KEY]['reviewed_by'] = 'other'
            if name == 'reviewed_fields': info[word_contract.INFO_KEY]['reviewed_fields'].pop()
            with self.subTest(name=name), self.assertRaises((ValidationError, ValueError)):
                word_contract.require_generation(version)

    def test_old_physical_only_form_requires_definitions_but_historical_source_remains_readable(self):
        version = self.version()
        del version.preparation.config[word_contract.CONFIG_KEY]
        del version.preparation.candidate_info[word_contract.INFO_KEY]
        version.preparation.approval_sha256 = approval_binding(version.preparation)
        self.assertEqual(validated_semantic_definitions(version), {})
        self.assertEqual(source_for_version(version), self.root/'prepared.docx')
        with self.assertRaisesMessage(ValidationError, 'needs approved answer definitions'):
            word_contract.require_generation(version)

    def test_missing_approved_source_is_actionable_through_all_contract_readers(self):
        version=self.version()
        (self.root/'blank.docx').unlink()
        for reader in (validated_semantic_definitions,word_contract.require_generation,definitions_for):
            with self.subTest(reader=reader.__name__),self.assertRaisesMessage(ValidationError,'source is unavailable'):
                reader(version)

    def test_incomplete_semantic_response_is_not_adopted(self):
        response, _ = preparation.provider_role(self.inv,'proposer',self.config,1)
        response.pop('answer_definitions')
        with self.assertRaisesMessage(ValidationError,'omitted its required answer definitions'):
            word_contract.validate_result(self.inv,response,'proposer',self.config)

    def test_twelve_fields_have_complete_bounded_schema_and_output(self):
        self.assertTrue(word_contract.eligible(self.inv))
        schema=preparation.role_schema('proposer',TYPED_PROTOCOL,self.inv,self.config)
        self.assertIn('answer_definitions',schema['required'])
        self.assertGreater(preparation.role_limits(self.inv,self.config)[0],6500)
        self.assertLessEqual(preparation.role_limits(self.inv,self.config)[0],16000)
        self.assertEqual(preparation.timing_limits(self.inv,self.config),(120,360))

    def test_exact_theo_note_gets_values_separate_from_complete_evidence(self):
        fields, definitions = self.fields, self.definitions()
        quotes = ('review','TEST-B942','Synthetic Theo Varen','October 11, 2026','left ankle soreness',
                  'two weeks','two','37.0',None,'penicillin causes a rash','left ankle discomfort','in fourteen days')
        facts=[]; selected={}
        for index, quote in enumerate(quotes):
            if quote is None: continue
            options = {}
            if index == 2: options.update(kind='identity', name_quote=quote)
            if index == 6: options.update(kind='measurement', occurrence=1, scale={'minimum':None,'maximum':'10','span':span(THEO,'two out of ten')})
            if index == 7: options.update(kind='measurement',unit='Celsius',unit_quote='Celsius')
            if index == 11: options.update(kind='follow_up',timing='future',timing_quote=quote)
            identity='f'+str(index)
            facts.append(fact(THEO,fields,identity,quote,**options)); selected['cell_'+str(index)]=[identity]
        sender = FixtureSender(facts,assignments(fields,selected))
        answers=semantic.run(THEO,fields,definitions,sender,reference_contract=semantic.REFERENCE_INVENTORY_CONTRACT)
        expected=('Review','TEST-B942','Synthetic Theo Varen','October 11, 2026','Left ankle soreness',
                  'Two weeks','2','37.0','','Penicillin causes a rash','Left ankle discomfort','In fourteen days')
        for field, value in zip(fields,expected):
            answer=answers[field['key']]
            with self.subTest(field=field['label']):
                self.assertEqual(answer['text'],value,answer.get('review_reasons'))
                self.assertEqual(answer['status'],'missing' if not value else 'supported')
                semantic.validate_stored_answer(THEO,field,definitions[field['key']],answer)
                if value: self.assertNotEqual(answer['text'],answer['evidence'][0]['quote'])
        self.assertEqual(answers['cell_6']['value'],2)
        self.assertEqual(answers['cell_7']['value'],37)
        self.assertEqual([(r,a) for r,a,*_ in sender.calls],[('extractor',1),('assigner',1),('checker',1)])

    def test_whole_sentences_are_not_valid_specific_values(self):
        values=self.definitions()
        failures={'cell_1':'The clinic reference is TEST-B942.',
            'cell_2':'SYNTHETIC THEO VAREN ATTENDED THE CLINIC',
            'cell_3':'Attended on October 11, 2026.', 'cell_5':'The patient reports symptoms for two weeks',
            'cell_6':'Rates it as two out of ten.', 'cell_7':'Temperature is 37.0 degrees Celsius.',
            'cell_11':'The patient requests reassessment in fourteen days'}
        for key,text in failures.items():
            with self.subTest(key=key),self.assertRaises(ValidationError): semantic.validate_value(values[key],text)
        for clause in ('SYNTHETIC THEO VAREN VISITED THE CLINIC', 'SYNTHETIC THEO VAREN CAME FOR REVIEW'):
            with self.subTest(clause=clause), self.assertRaises(ValidationError):
                semantic.validate_value(values['cell_2'],clause)

    def test_reference_requires_complete_token_not_a_punctuation_delimited_fragment(self):
        for source in ('TEST-B942--ALT','ABC..TEST-B942','TEST-B942-ALT','TEST-B942Z','ZTEST-B942'):
            notes='Clinic reference: '+source+'.'
            self.assertTrue(semantic.identifier_fragment(notes,span(notes,'TEST-B942'),'Clinic reference'))
        for source in ('TEST-B942','TEST-B942--ALT','ABC..TEST-B942'):
            notes='Clinic reference:'+source+'. Next sentence.'
            self.assertFalse(semantic.identifier_fragment(notes,span(notes,source),'Clinic reference'))

    def test_separate_definition_response_must_match_explicit_requested_version(self):
        from core.semantic_preparation import _require_definition_version
        from documents.semantic_preparation_roles import DefinitionError
        response={'fields':[{'definition':{'version':1}}]}
        self.assertEqual(_require_definition_version(response,1),response)
        with self.assertRaises(DefinitionError): _require_definition_version(response,2)
        self.assertEqual(_require_definition_version({'fields':[{'definition':{'version':2}}]},2)['fields'][0]['definition']['version'],2)

    def test_complete_calendar_dates_validate_without_invented_printed_format(self):
        definition=self.definitions()['cell_3']
        for text in ('October 11, 2026','11 October 2026','2026-10-11','February 29, 2024'):
            self.assertEqual(semantic.validate_value(definition,text),text)
        for text in ('October 11','10/11/2026','February 29, 2025','October 32, 2026',
                     'Seen October 11, 2026','October 11, 2026 at noon','2026-10-11 to 2026-10-12'):
            with self.subTest(text=text),self.assertRaises(ValidationError): semantic.validate_value(definition,text)

    def test_names_abbreviations_and_exact_identifiers_keep_supported_spelling(self):
        values=self.definitions()
        for text in ('Synthetic J.R. Varen','Synthetic J. R. Varen','山田 太郎','علی رضایی','Synthetic Anne-Marie O’Neill'):
            self.assertEqual(semantic.validate_value(values['cell_2'],text),text)
        self.assertEqual(semantic.validate_value(values['cell_4'],'Right M.C.P. joint pain'),'Right M.C.P. joint pain')
        f={'value_evidence':{'quote':'ab-42'}}
        self.assertEqual(semantic._render_fact(f,values['cell_1']),'ab-42')

    def test_local_schema_failure_precedes_reservation_or_provider_admission(self):
        packet=SimpleNamespace(inventory=self.inv,config={**self.config,'mode':'live','input_rate':'3','output_rate':'15','cached_rate':'0.3'})
        import time
        with patch('anthropic.transform_schema',side_effect=ValueError('offline malformed schema')), \
                patch('core.testing_authority.reserve_role') as reserve,patch('anthropic.Anthropic') as client:
            with self.assertRaises(ValueError): preparation.call_role(packet,'proposer',time.monotonic()+360)
        reserve.assert_not_called();client.assert_not_called()

    def test_local_provider_configuration_failure_has_no_reservation_or_send(self):
        from documents import DocumentError
        import time
        import os
        packet=SimpleNamespace(inventory=self.inv,config={**self.config,'mode':'live','input_rate':'3','output_rate':'15','cached_rate':'0.3'})
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'synthetic-local-only'}), \
                patch('anthropic.Anthropic',side_effect=ValueError('synthetic unavailable configuration')) as client, \
                patch('core.testing_authority.reserve_role') as reserve:
            with self.assertRaises(DocumentError) as raised:
                preparation.call_role(packet,'proposer',time.monotonic()+360)
        self.assertEqual(raised.exception.code,'provider_not_configured')
        reserve.assert_not_called();client.assert_called_once()

    def test_real_sdk_missing_credentials_refuse_before_reservation_and_http_send(self):
        from documents import DocumentError
        import os,time
        packet=SimpleNamespace(inventory=self.inv,config={**self.config,'mode':'live','input_rate':'3','output_rate':'15','cached_rate':'0.3'})
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'','ANTHROPIC_AUTH_TOKEN':''}), \
                patch('httpx.Client.send') as send, patch('core.testing_authority.reserve_role') as reserve:
            with self.assertRaises(DocumentError) as raised:
                preparation.call_role(packet,'proposer',time.monotonic()+360)
        self.assertEqual(raised.exception.code,'provider_not_configured')
        reserve.assert_not_called();send.assert_not_called()


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', ADMIN_SITE=False,
    TESTING_AUTHORITY_MODE='', TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='',
    STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
              'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class OrdinaryClinicianWordTests(TestCase):
    def setUp(self):
        from core.tests.test_semantic_preparation import DefinitionPreparationDatabaseTests
        DefinitionPreparationDatabaseTests.setUp(self)
        from core.models import Patient
        self.patient = Patient.objects.create(department=self.department, display_name='Synthetic test person',
            reference='fresh-contract-test', created_by=self.user)
        self.client.force_login(self.user)

    def fresh_upload(self, expected_state='review'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.models import Template
        response=self.client.post('/templates/upload/', {'name':'Fresh ordinary clinician form',
            'department':str(self.department.pk), 'synthetic_only':'on', 'prepare_with_ai':'on',
            'file':SimpleUploadedFile('ordinary-blank.docx',(self.root/'blank.docx').read_bytes(),
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        self.assertEqual(response.status_code,302)
        template=Template.objects.exclude(pk=self.template.pk).get()
        self.assertEqual(template.created_by_id,self.user.pk)
        self.assertEqual(template.versions.count(),0)
        self.assertTrue(preparation.run_one())
        prep=template.preparation; prep.refresh_from_db()
        self.assertEqual(prep.state,expected_state,prep.error_code)
        return template,prep

    def test_fresh_ambiguous_name_is_guided_and_server_refuses_approval_without_changing_responses(self):
        original_role = preparation.provider_role
        def ambiguous(*args, **kwargs):
            response, evidence = original_role(*args, **kwargs)
            row = response['answer_definitions']['fields'][0]
            row['definition'].update(value_type='person_name', answer_mode='atomic')
            row['definition']['scope']['subject'] = 'unspecified'
            if row['definition'].get('component_contract'):
                component = row['definition']['component_contract']['components'][0]
                component.update(value_type='person_name',scope=deepcopy(row['definition']['scope']))
            return response, evidence
        with patch.object(preparation, 'provider_role', side_effect=ambiguous):
            template, prep = self.fresh_upload('guided')
        original = deepcopy((prep.proposal, prep.checker, prep.corrections))
        response = self.client.get(f'/templates/{template.pk}/preparation/')
        self.assertContains(response, 'Choose whose name')
        self.assertNotContains(response, 'Approve layout and create form version')
        # Even a retained pre-repair review-state preparation cannot bypass the server gate.
        prep.state = 'review'; prep.save(update_fields=['state'])
        response = self.client.post(f'/templates/{template.pk}/preparation/approve/', {
            'revision':str(prep.revision), 'candidate_sha256':prep.candidate_sha256,
            'approved_change':[c['anchor_id'] for c in prep.changes],
            'original_reviewed':'on', 'prepared_reviewed':'on',
            'reviewed_definition':[f['key'] for f in prep.inventory['fields']]})
        self.assertContains(response, 'Choose whose name', status_code=409)
        prep.refresh_from_db()
        self.assertFalse(template.versions.exists())
        self.assertEqual((prep.proposal, prep.checker, prep.corrections), original)

    def test_unresolved_checker_with_valid_scope_requires_separate_clinician_correction(self):
        original_role = preparation.provider_role
        def unresolved(*args, **kwargs):
            response, evidence = original_role(*args, **kwargs)
            if args[1] == 'checker':
                response['answer_definitions']['fields'][0].update(
                    state='unresolved', reason='The intended answer needs a clinician decision.')
            return response, evidence
        with patch.object(preparation, 'provider_role', side_effect=unresolved):
            template, prep = self.fresh_upload('guided')
        original = deepcopy((prep.proposal, prep.checker))
        self.assertEqual(prep.inventory['issues'], [])
        # A retained old review state also cannot expose or bypass approval.
        prep.state = 'review'; prep.save(update_fields=['state'])
        page = self.client.get(f'/templates/{template.pk}/preparation/')
        self.assertContains(page, 'Answer definitions need your decision')
        self.assertContains(page, 'Save decisions')
        self.assertNotContains(page, 'Approve layout and create form version')
        response = self.client.post(f'/templates/{template.pk}/preparation/approve/', {
            'revision':str(prep.revision), 'candidate_sha256':prep.candidate_sha256,
            'approved_change':[c['anchor_id'] for c in prep.changes],
            'original_reviewed':'on', 'prepared_reviewed':'on',
            'reviewed_definition':[f['key'] for f in prep.inventory['fields']]})
        self.assertContains(response, 'Save doctor corrections', status_code=409)
        self.assertFalse(template.versions.exists())
        values = word_contract.proposed(prep)
        corrected = values[next(iter(values))]
        corrected['meaning'] = 'The documented patient answer to the original clinical question.'
        if corrected['version'] == 4:
            corrected['component_contract']['components'][0]['meaning'] = corrected['meaning']
        preparation.correct(prep.pk, self.user, prep.revision,
            {f['key']:f['label'] for f in prep.candidate_info['fields']},
            [a['id'] for a in prep.inventory['anchors']],
            'Checked the complete original and clarified the requested patient answer.',
            definitions=values, reviewed_definitions=list(values))
        prep.refresh_from_db()
        self.assertEqual(prep.state, 'review')
        self.assertEqual((prep.proposal, prep.checker), original)
        self.assertEqual(prep.correction_history[-1]['answer_definitions'], values)
        version = self.approve(template, prep)
        self.assertEqual(version.number, 1)
        self.assertEqual(word_contract.require_generation(version), values)

    def test_pre_upgrade_queued_job_rechecks_unresolved_definitions_before_any_stage(self):
        from decimal import Decimal
        from core.models import Encounter, AIStageReceipt, Usage, Reservation
        from core.jobs import enqueue, run_one
        from core.billing import welcome_credit
        original_role = preparation.provider_role
        def unresolved(*args, **kwargs):
            response, evidence = original_role(*args, **kwargs)
            if args[1] == 'checker':
                response['answer_definitions']['fields'][0].update(
                    state='unresolved', reason='The original question still needs a semantic decision.')
            return response, evidence
        # Represent an immutable version and queue admitted by the old release.
        with patch.object(preparation, 'provider_role', side_effect=unresolved), \
                patch.object(word_contract, 'approval_issues', return_value={}):
            template, prep = self.fresh_upload()
            version = self.approve(template, prep)
        values = validated_semantic_definitions(version)
        welcome_credit(self.user)
        encounter = Encounter.objects.create(patient=self.patient, department=self.department,
            template_version=version, created_by=self.user, notes='Patient name: Synthetic Test',
            service_date=timezone.localdate())
        with patch.object(word_contract, 'require_generation', return_value=values), \
                patch('core.ai_stages.maximum_cost', return_value=Decimal('0.01')):
            job = enqueue(encounter, self.user)
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state',flat=True)), {'held'})
        before = deepcopy((prep.proposal, prep.checker))
        with patch('core.ai_stages.execute_stage') as send, patch('core.semantic_generation.run') as pipeline:
            self.assertTrue(run_one())
        send.assert_not_called(); pipeline.assert_not_called()
        job.refresh_from_db(); encounter.refresh_from_db(); prep.refresh_from_db()
        self.assertEqual(job.state, 'failed')
        self.assertIn('new definition version', job.error)
        self.assertFalse(AIStageReceipt.objects.filter(job=job).exists())
        self.assertFalse(Usage.objects.filter(job=job).exists())
        self.assertEqual(set(Reservation.objects.filter(job=job).values_list('state',flat=True)), {'released'})
        self.assertEqual(encounter.answers, {})
        self.assertEqual((prep.proposal, prep.checker), before)
        self.assertEqual(validated_semantic_definitions(version), values)

    def approve(self,template,prep):
        response=self.client.post(f'/templates/{template.pk}/preparation/approve/',{
            'revision':str(prep.revision),'candidate_sha256':prep.candidate_sha256,
            'approved_change':[c['anchor_id'] for c in prep.changes],
            'original_reviewed':'on','prepared_reviewed':'on',
            'reviewed_definition':[f['key'] for f in prep.inventory['fields']]})
        self.assertEqual(response.status_code,302, response.content[:300])
        return template.versions.get()

    def test_fresh_clinician_upload_approval_and_generation_use_semantics_on_v1(self):
        from core.models import Job, AIStageReceipt
        from core.jobs import enqueue, run_one
        from core.billing import welcome_credit
        template,prep=self.fresh_upload()
        review=self.client.get(f'/templates/{template.pk}/preparation/')
        self.assertEqual(review.context['definition_version'],4)
        self.assertContains(review,'data-answer-definitions')
        self.assertContains(review,'Required parts of this answer')
        for field in prep.inventory['fields']:
            self.assertContains(review,'name="field_'+field['key']+'_patient_name_requirement"')
        self.assertContains(review,'data-review-field=',count=len(prep.inventory['fields']))
        self.assertContains(review,'name="review_summary" required>',count=1)
        self.assertNotContains(review,'name="reviewed_definition"')
        version=self.approve(template,prep)
        self.assertEqual(version.number,1)
        self.assertTrue(word_contract.require_generation(version))
        welcome_credit(self.user)
        response=self.client.post('/encounters/new/',{'patient':str(self.patient.pk),
            'template_version':str(version.pk),'notes':'Patient name: Synthetic Alex Morgan\nAssessment: Left ankle pain',
            'service_date':timezone.localdate().isoformat(),'synthetic_only':'on'})
        self.assertEqual(response.status_code,302,response.content[:300])
        from core.models import Encounter, CodingRun
        encounter=Encounter.objects.get(template_version=version)
        before_jobs = Job.objects.filter(encounter=encounter).count()
        self.assertEqual(encounter.answers,{})
        self.assertFalse(CodingRun.objects.filter(encounter=encounter).exists())
        empty_coding = self.client.get(f'/encounters/{encounter.pk}/?tab=coding')
        self.assertEqual(empty_coding.status_code,200)
        encounter.refresh_from_db()
        self.assertEqual(encounter.answers,{})
        self.assertEqual(Job.objects.filter(encounter=encounter).count(),before_jobs)
        self.assertFalse(CodingRun.objects.filter(encounter=encounter).exists())
        first=enqueue(encounter,self.user)
        self.assertEqual(first.config['semantic_contract'],semantic.CONTRACT)
        self.assertTrue(run_one())
        first.refresh_from_db();self.assertEqual(first.state,'succeeded',first.error)
        second=enqueue(encounter,self.user)
        self.assertEqual(second.pk,first.pk)
        self.assertEqual(Job.objects.filter(encounter=encounter).count(),1)
        self.assertEqual(list(AIStageReceipt.objects.filter(job=first).order_by('created_at').values_list('stage',flat=True)),
            ['extractor','assigner','checker'])
        # Inline approved definitions live in the sealed preparation; an empty
        # separate-definition column must not disconnect coding from the same
        # retained graph that generated the current document.
        from core import source_assertion_coding as shared, source_assertion_graph as graph
        from core import coding_service
        encounter.refresh_from_db()
        self.assertEqual(version.semantic_definitions,{})
        self.assertTrue(all(d['version']==4 for d in word_contract.require_generation(version).values()))
        self.assertEqual(first.config['semantic_fact_scope_contract'],graph.CONTRACT)
        checked = shared.snapshot(encounter)
        self.assertIsNotNone(checked)
        inputs,context,releases,key = coding_service.input_snapshot(encounter)
        self.assertEqual(inputs['source_interpretation'],checked)
        self.assertEqual(checked['identity']['generation_job_id'],str(first.pk))
        self.assertEqual(inputs['revision'],encounter.revision)
        projected = shared.source(SimpleNamespace(inputs=inputs,config={'clinical_source_contract':shared.CONTRACT}))
        self.assertEqual(projected['identity']['encounter_id'],str(encounter.pk))
        self.assertEqual(projected['identity']['generation_job_id'],str(first.pk))

    def test_inline_graph_flat_review_keeps_its_profile_and_source_component_baseline(self):
        template,prep = self.fresh_upload()
        original = deepcopy((prep.proposal,prep.checker))
        values = word_contract.proposed(prep)
        post = {'revision':str(prep.revision),
            'reviewed_anchor':[a['id'] for a in prep.inventory['anchors']],
            'reviewed_field':list(values),
            'correction_reason':'Checked each complete answer definition and its original source location.'}
        for field in prep.inventory['fields']:
            key = field['key']; definition = values[key]; prefix = 'field_'+key+'_'
            post['label_'+key] = field['label']
            for name in ('meaning','value_type','answer_mode','patient_name_requirement'):
                post[prefix+name] = definition[name]
            post[prefix+'unit'] = definition['unit'] or ''
            post[prefix+'choices'] = '\n'.join(definition['choices'])
            for name,value in {**definition['scope'],**definition['constraints']}.items():
                post[prefix+name] = value if value is not None else ''
            # Component JSON from a browser is never the authoritative baseline.
            post[prefix+'component_contract'] = '{"components":[]}'
        from django.urls import reverse
        response = self.client.post(reverse('template_preparation_correct',args=[template.pk]),post)
        self.assertEqual(response.status_code,302,response.content[:300])
        prep.refresh_from_db()
        self.assertEqual(prep.corrections['answer_definitions'],values)
        self.assertEqual((prep.proposal,prep.checker),original)
        self.assertTrue(all(d['version']==4 for d in prep.corrections['answer_definitions'].values()))

    def test_physical_only_form_is_actionable_and_cannot_start_generation(self):
        from core.models import Encounter,Job,AIStageReceipt
        from core.jobs import enqueue
        page=self.client.get(f'/templates/{self.template.pk}/')
        self.assertContains(page,'data-answer-contract-required')
        self.assertNotContains(page,'Use this form <span')
        encounter=Encounter.objects.create(department=self.department,patient=self.patient,template_version=self.source,
            created_by=self.user,service_date=timezone.localdate(),notes='Synthetic source note.')
        with self.assertRaisesMessage(ValidationError,'needs approved answer definitions'):
            enqueue(encounter,self.user)
        self.assertFalse(Job.objects.exists());self.assertFalse(AIStageReceipt.objects.exists())
        detail=self.client.get(f'/encounters/{encounter.pk}/')
        self.assertTrue(detail.context['manual_entry'])
        self.assertContains(detail,'name="answer_'+self.source.fields[0]['key']+'"')
        self.assertContains(detail,'needs approved answer definitions')

    def test_missing_own_approved_source_is_withheld_without_http_500(self):
        template,prep=self.fresh_upload()
        version=self.approve(template,prep)
        from core.security import private_path
        private_path(template.original_path).unlink()
        page=self.client.get('/encounters/new/')
        self.assertEqual(page.status_code,200)
        self.assertNotIn(version.pk,[v.pk for v in page.context['form'].fields['template_version'].queryset])
        detail=self.client.get(f'/templates/{template.pk}/')
        self.assertContains(detail,'source is unavailable')
        self.assertFalse(detail.context['manual_form_allowed'])

    def test_targeted_fixture_preparation_does_not_execute_older_live_request(self):
        from core.models import Template,TemplatePreparation
        older=TemplatePreparation.objects.create(template=self.template,requested_by=self.user,config={'mode':'live'})
        template=Template.objects.create(department=self.department,name='Targeted fixture form',format='docx',
            original_name=self.template.original_name,original_path=self.template.original_path,
            sha256=self.template.sha256,created_by=self.user)
        selected=preparation.create_preparation(template,self.user)
        original=preparation.call_role
        called=[]
        def record(packet,*args,**kwargs):
            self.assertEqual(packet.pk,selected.pk)
            self.assertEqual(packet.config['mode'],'fixture')
            called.append(packet.pk)
            return original(packet,*args,**kwargs)
        with patch.object(preparation,'call_role',side_effect=record):
            self.assertTrue(preparation.run_one(preparation_pk=selected.pk))
        older.refresh_from_db();selected.refresh_from_db()
        self.assertEqual(older.state,'queued');self.assertEqual(selected.state,'review',selected.error_code)
        self.assertEqual(called,[selected.pk,selected.pk])

    def test_foreign_missing_source_is_never_evaluated_for_clinician_choices(self):
        from core.models import Organization,Department,Template,TemplateVersion
        from core.forms import EncounterForm
        org=Organization.objects.create(name='Other synthetic tenant')
        dept=Department.objects.create(organization=org,name='Other department')
        template=Template.objects.create(department=dept,name='Unavailable foreign form',format='docx',
            original_name='missing.docx',original_path='missing.docx',sha256='a'*64,created_by=self.user)
        foreign=TemplateVersion.objects.create(template=template,number=1,fields=self.source.fields,created_by=self.user)
        from core import semantic_preparation
        actual=semantic_preparation.validated_semantic_definitions
        seen=[]
        def inspect(version):
            seen.append(version.pk)
            if version.pk==foreign.pk: raise AssertionError('Foreign mapping was evaluated')
            return actual(version)
        with patch.object(semantic_preparation,'validated_semantic_definitions',side_effect=inspect):
            self.assertEqual([v.pk for v in EncounterForm(user=self.user).fields['template_version'].queryset],[self.source.pk])
        self.assertNotIn(foreign.pk,seen)
