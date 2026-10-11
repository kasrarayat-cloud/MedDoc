"""Bound complete blank-form output; retain failures and accounting without retry."""
from contextlib import nullcontext
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from docx import Document
from django.test import SimpleTestCase, RequestFactory, override_settings

from core import preparation
from documents.preparation import inventory, digest, model_inventory, TYPED_PROTOCOL
from documents.preparation_roles import role_rows


class PreparationOutputTests(SimpleTestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name)/'two-tables.docx'
        document=Document()
        for first in (1,7):
            table=document.add_table(rows=6,cols=2)
            for offset,row in enumerate(table.rows):
                number=first+offset
                row.cells[0].text='Question '+str(number)
                row.cells[1].text='{{Answer '+str(number)+'}}'
        document.save(self.path)
        self.inventory=inventory(self.path,protocol=TYPED_PROTOCOL)
        self.config={'mode':'fixture','provider':'anthropic','model':'offline-configured-label',
                     'input_rate':'3','output_rate':'15','cached_rate':'0.3',
                     'word_preparation_output_profile':preparation.OUTPUT_PROFILE}

    def receipt(self):
        return SimpleNamespace(response_path='',response_sha256='',returned_model='',provider_request_id='',
            provider_resource_id='',computed_cost=None,usage={},rates={},failure={},failure_path='',
            failure_sha256='',simulated=False,state='running',error_code='',quote_maximum=Decimal('0.10'),save=Mock())

    def complete_output(self,role='proposer'):
        return preparation.provider_role(self.inventory,role,self.config,1)[0]

    def exercise_transport(self,text,stop_reason='end_turn',usage=True,role='proposer'):
        """Real pinned SDK on an in-memory HTTP transport; zero network requests."""
        import httpx
        from anthropic import Anthropic
        receipt=self.receipt();retained=[];sent=[]
        config={**self.config,'mode':'live'}
        proposal=self.complete_output() if role=='checker' else None
        packet=SimpleNamespace(inventory=self.inventory,config=config)
        def handle(request):
            body=json.loads(request.content);sent.append(body)
            self.assertEqual(request.url.host,'synthetic-provider.invalid')
            self.assertEqual(body['max_tokens'],preparation.role_limits(self.inventory,config)[0])
            result={'id':'offline-response','type':'message','role':'assistant','model':'offline-returned-model',
                'content':[{'type':'text','text':text}],'stop_reason':stop_reason,'stop_sequence':None,
                'usage':{'input_tokens':100,'output_tokens':2500} if usage else None}
            return httpx.Response(200,headers={'request-id':'offline-request'},json=result)
        def retain(*args):
            retained.append(deepcopy(args[-1]));return 'offline-retained.json','c'*64
        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            client=Anthropic(api_key='synthetic-offline-only',base_url='https://synthetic-provider.invalid',
                http_client=http,timeout=60,max_retries=0)
            with patch('anthropic.Anthropic',return_value=client), \
                    patch('core.testing_authority.identity',return_value=True), \
                    patch('core.testing_authority.reserve_role',return_value=receipt) as reserve, \
                    patch('core.preparation_campaign.provider_slot',return_value=nullcontext()), \
                    patch.object(preparation,'retain_response',side_effect=retain), \
                    patch.object(preparation.time,'monotonic',return_value=100):
                try:
                    result=preparation.call_role(packet,role,280,proposal)
                except preparation.DocumentError as error:
                    result=error
        return result,receipt,retained,sent,reserve

    def test_two_tables_twelve_fields_get_complete_inventory_sized_profile(self):
        from zipfile import ZipFile
        from lxml import etree
        with ZipFile(self.path) as package:
            root=etree.fromstring(package.read('word/document.xml'))
        self.assertEqual(len(root.findall('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tbl')),2)
        self.assertEqual(len(self.inventory['anchors']),12)
        before=deepcopy(self.inventory)
        output,cap=preparation.role_limits(self.inventory,self.config)
        self.assertGreater(output,2500)
        self.assertLessEqual(output,16000)
        self.assertEqual(cap,Decimal('0.10'))
        for role in ('proposer','checker'):
            canonical={'inventory_sha256':self.inventory['inventory_sha256'],
                'anchors':role_rows(self.inventory,role),
                'stories':[{'story_id':row['id'],'content_sha256':row['content_sha256'],'verdict':'retain'}
                    for row in model_inventory(self.inventory)['stories']]}
            size=len(json.dumps(canonical,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode())
            self.assertGreaterEqual(output,size+2500)
        self.assertEqual(self.inventory,before)

    def test_only_new_preparations_receive_profile_without_mutating_base_config(self):
        original={key:value for key,value in self.config.items() if key!='word_preparation_output_profile'}
        before=deepcopy(original)
        with patch.object(preparation,'feature_enabled',return_value=True), \
                patch.object(preparation,'configuration',return_value=original), \
                patch('core.preparation_campaign.active_campaign_config',side_effect=lambda config,_:config), \
                patch('core.testing_authority.identity',return_value=True), \
                patch('core.testing_authority.create_preparation') as create:
            preparation.create_preparation(SimpleNamespace(sha256=self.inventory['source_sha256']),'synthetic-doctor')
        self.assertEqual(create.call_args.args[2]['word_preparation_output_profile'],preparation.OUTPUT_PROFILE)
        self.assertEqual(original,before)
        self.assertEqual(preparation.role_limits(self.inventory,original),(2500,Decimal('0.10')))
        self.assertEqual(preparation.role_limits(self.inventory),(2500,Decimal('0.10')))

    def test_explicit_invalid_profile_and_wrong_inventory_protocol_refuse_before_reservation_or_transport(self):
        for profile in (None,False,0,'','unknown-output-profile'):
            config={**self.config,'word_preparation_output_profile':profile}
            with self.subTest(profile=profile), \
                    patch('core.testing_authority.reserve_role') as reserve,patch('anthropic.Anthropic') as provider:
                with self.assertRaises(preparation.DocumentError) as refused:
                    preparation.call_role(SimpleNamespace(inventory=self.inventory,config=config),'proposer',280)
                self.assertEqual(refused.exception.code,'preparation_limit')
                reserve.assert_not_called();provider.assert_not_called()
        legacy=inventory(self.path)
        with self.assertRaises(preparation.DocumentError):preparation.role_limits(legacy,self.config)

    def test_oversize_complete_response_refuses_without_dropping_fields_or_sending(self):
        value=deepcopy(self.inventory)
        for row in value['questions']:row['text']='Question '+row['id']+' '+('x'*1900)
        value['inventory_sha256']=digest({key:item for key,item in value.items() if key!='inventory_sha256'})
        before=deepcopy(value)
        with patch('core.testing_authority.reserve_role') as reserve,patch('anthropic.Anthropic') as provider:
            with self.assertRaises(preparation.DocumentError) as refused:
                preparation.call_role(SimpleNamespace(inventory=value,config=self.config),'proposer',280)
        self.assertEqual(refused.exception.code,'preparation_limit')
        reserve.assert_not_called();provider.assert_not_called();self.assertEqual(value,before)

    def test_both_complete_roles_reach_same_quoted_transport_limit_and_validate_all_areas(self):
        for role in ('proposer','checker'):
            expected=self.complete_output(role)
            result,receipt,retained,sent,reserve=self.exercise_transport(json.dumps(expected),role=role)
            self.assertEqual(result,expected)
            self.assertEqual(len(result['anchors']),12)
            self.assertEqual(len(result['stories']),len(self.inventory['stories']))
            self.assertEqual(receipt.state,'succeeded');self.assertEqual(receipt.error_code,'')
            self.assertEqual(len(sent),1);self.assertEqual(len(retained),1)
            maximum=preparation.maximum_cost(json.loads(sent[0]['messages'][0]['content']),
                {**self.config,'mode':'live'},sent[0]['max_tokens'])
            self.assertEqual(reserve.call_args.args[-1],maximum)
            self.assertEqual(receipt.computed_cost,Decimal('0.0378'))

    def test_truncated_response_is_known_output_limit_with_usage_and_raw_failure_preserved(self):
        full=json.dumps(self.complete_output(),separators=(',',':'))
        truncated=full[:-20]
        with self.assertRaises(json.JSONDecodeError):json.loads(truncated)
        result,receipt,retained,sent,_=self.exercise_transport(truncated,'max_tokens')
        self.assertIsInstance(result,preparation.DocumentError);self.assertEqual(result.code,'output_limit')
        self.assertEqual(receipt.state,'failed');self.assertEqual(receipt.error_code,'output_limit')
        self.assertEqual(receipt.computed_cost,Decimal('0.0378'));self.assertEqual(receipt.usage['output_tokens'],2500)
        self.assertEqual(retained[0]['response']['content'][0]['text'],truncated)
        self.assertEqual(retained[0]['response']['stop_reason'],'max_tokens')
        self.assertEqual(receipt.failure['provider_stop_reason'],'max_tokens')
        self.assertTrue(receipt.failure['usage_established']);self.assertTrue(receipt.failure['response_retained'])
        self.assertFalse(receipt.failure['automatic_retry']);self.assertEqual(len(sent),1)
        self.assertEqual(retained[-1],receipt.failure)

    def test_valid_json_with_incomplete_stop_is_never_adopted_and_parse_failure_is_distinct(self):
        full=json.dumps(self.complete_output())
        for stop,code in [('max_tokens','output_limit'),('refusal','invalid_response'),
                          ('stop_sequence','invalid_response'),('tool_use','invalid_response')]:
            result,receipt,_,sent,_=self.exercise_transport(full,stop)
            self.assertEqual(result.code,code);self.assertEqual(receipt.state,'failed')
            self.assertEqual(receipt.computed_cost,Decimal('0.0378'));self.assertEqual(len(sent),1)
        result,receipt,_,sent,_=self.exercise_transport('not JSON','end_turn')
        self.assertEqual(result.code,'invalid_response');self.assertEqual(receipt.error_code,'invalid_response')
        self.assertEqual(receipt.failure['stage'],'response_parsing')
        self.assertEqual(receipt.computed_cost,Decimal('0.0378'));self.assertEqual(len(sent),1)

    def test_unestablished_usage_cannot_be_relabelled_known_or_released(self):
        result,receipt,retained,sent,_=self.exercise_transport(json.dumps(self.complete_output()),'max_tokens',usage=False)
        self.assertEqual(result.code,'provider_unknown');self.assertIsNone(receipt.computed_cost)
        self.assertEqual(receipt.quote_maximum,Decimal('0.10'));self.assertEqual(len(sent),1)
        self.assertFalse(receipt.failure['usage_established']);self.assertTrue(receipt.failure['response_retained'])
        self.assertIsNone(retained[0]['response']['usage']);self.assertFalse(receipt.failure['automatic_retry'])

    def test_historical_explanation_preserves_label_and_does_not_infer_output_limit(self):
        packet=SimpleNamespace(error_code='provider_unknown')
        receipt=self.receipt();receipt.response_path='retained-original.json';receipt.computed_cost=Decimal('0.031788')
        receipt.failure={'error_class':'JSONDecodeError','response_retained':True,'usage_established':True,
                         'private-message':'secret-is-never-displayed'}
        before=deepcopy(receipt.failure)
        message=preparation.failure_explanation(packet,[receipt])
        self.assertIn('could not be parsed',message);self.assertIn('computed provider usage',message)
        self.assertNotIn('output limit',message);self.assertNotIn('secret',message)
        self.assertEqual(packet.error_code,'provider_unknown');self.assertEqual(receipt.failure,before)
        receipt.state='unknown';receipt.computed_cost=None;receipt.failure={}
        message=preparation.failure_explanation(packet,[receipt])
        self.assertIn('reconcile',message);self.assertIn('reservation is retained',message)
        for bad in (None,[],False,'private-message'):
            receipt.failure=bad
            self.assertNotIn('private-message',preparation.failure_explanation(packet,[receipt]))
        receipt.save.assert_not_called()

    def test_department_scoped_detail_and_status_expose_closed_explanation_only(self):
        from core import preparation_views
        receipt=self.receipt();receipt.response_path='retained-original.json';receipt.computed_cost=Decimal('0.031788')
        receipt.failure={'error_class':'JSONDecodeError','response_retained':True,'usage_established':True,
                         'private-body':'must-not-appear'}
        receipts=Mock();receipts.order_by.return_value=[receipt]
        receipts.filter.return_value.values_list.return_value.first.return_value='failed'
        packet=SimpleNamespace(inventory=self.inventory,proposal={},checker={},candidate_info={},corrections={},
            receipts=receipts,error_code='provider_unknown',state='blocked',revision=0,started_at=None,finished_at=None)
        request=RequestFactory().get('/templates/00000000-0000-0000-0000-000000000001/preparation/')
        template=SimpleNamespace(pk='00000000-0000-0000-0000-000000000001')
        with patch.object(preparation_views,'selected',return_value=(template,packet)) as scoped, \
                patch.object(preparation_views,'render') as render:
            preparation_views.detail(request,template.pk)
        scoped.assert_called_once_with(request,template.pk)
        context=render.call_args.args[2]
        self.assertIn('could not be parsed',context['failure_explanation'])
        self.assertNotIn('must-not-appear',context['failure_explanation'])
        with patch.object(preparation_views,'selected',return_value=(template,packet)) as scoped:
            response=preparation_views.status(request,template.pk)
        scoped.assert_called_once_with(request,template.pk)
        status=json.loads(response.content)
        self.assertEqual(status['error_code'],'provider_unknown')
        self.assertEqual(status['explanation'],context['failure_explanation'])
        self.assertNotIn('must-not-appear',response.content.decode())
        receipt.save.assert_not_called()

    @override_settings(STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
                                'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
    def test_stopped_page_displays_safe_explanation_and_preserves_retained_label(self):
        from django.template.loader import render_to_string
        packet=SimpleNamespace(state='blocked',error_code='provider_unknown',revision=0,
            started_at=None,finished_at=None,candidate_info={},candidate_path='')
        template=SimpleNamespace(pk='00000000-0000-0000-0000-000000000001',name='Synthetic blank',
            format='docx',sha256=self.inventory['source_sha256'])
        html=render_to_string('template_preparation.html',{'user':SimpleNamespace(username='synthetic-doctor',email='',is_staff=False),
            'preparation':packet,'template':template,'failure_explanation':'Safe explanation <private-markup>',
            'preview_token':'a'*48})
        self.assertIn('data-preparation-explanation',html)
        self.assertIn('Safe explanation &lt;private-markup&gt;',html)
        self.assertNotIn('Safe explanation <private-markup>',html)
        self.assertIn('provider_unknown',html)
        self.assertIn('No automatic retry was made',html)

