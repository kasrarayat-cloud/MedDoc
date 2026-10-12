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

    def fresh_upload(self):
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
        self.assertEqual(prep.state,'review',prep.error_code)
        return template,prep

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
        self.assertContains(review,'data-answer-definitions')
        self.assertContains(review,'name="reviewed_definition"',count=len(prep.inventory['fields']))
        version=self.approve(template,prep)
        self.assertEqual(version.number,1)
        self.assertTrue(word_contract.require_generation(version))
        welcome_credit(self.user)
        response=self.client.post('/encounters/new/',{'patient':str(self.patient.pk),
            'template_version':str(version.pk),'notes':'Patient name: Synthetic Alex Morgan\nAssessment: Left ankle pain',
            'service_date':timezone.localdate().isoformat(),'synthetic_only':'on'})
        self.assertEqual(response.status_code,302,response.content[:300])
        from core.models import Encounter
        encounter=Encounter.objects.get(template_version=version)
        first=enqueue(encounter,self.user)
        self.assertEqual(first.config['semantic_contract'],semantic.CONTRACT)
        self.assertTrue(run_one())
        first.refresh_from_db();self.assertEqual(first.state,'succeeded',first.error)
        second=enqueue(encounter,self.user)
        self.assertEqual(second.pk,first.pk)
        self.assertEqual(Job.objects.filter(encounter=encounter).count(),1)
        self.assertEqual(list(AIStageReceipt.objects.filter(job=first).order_by('created_at').values_list('stage',flat=True)),
            ['extractor','assigner','checker'])

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
