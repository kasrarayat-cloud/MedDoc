"""Source-only preparation security, cost and approval binding tests; no database."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch,Mock
from django.test import SimpleTestCase,override_settings
from django.core.exceptions import ValidationError
from docx import Document
from documents.preparation import inventory,digest,validate_role
from documents.sdk_service import WM_IOV_SHA256
from core import preparation as prep
from core.template_source import source_for_version,approval_binding

class PreparationPureTests(SimpleTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.settings=override_settings(MEDIA_ROOT=self.root,WORD_PREPARATION_ENABLED=True)
        self.settings.enable();self.addCleanup(self.settings.disable)
        d=Document();d.add_paragraph('Assessment: ____');d.add_paragraph('Patient signature: ____')
        d.save(self.root/'original.docx');self.inv=inventory(self.root/'original.docx')

    def config(self,**kw):
        return {'mode':'fixture','provider':'anthropic','model':'configured-label','input_rate':'2',
                'output_rate':'10','cached_rate':'0.2',**kw}

    def packet(self):
        proposal,_=prep.provider_role(self.inv,'proposer',self.config(),1)
        checker,_=prep.provider_role(self.inv,'checker',self.config(),1,proposal)
        p=SimpleNamespace(template_id='template1',template=SimpleNamespace(sha256=self.inv['source_sha256']),
            inventory=deepcopy(self.inv),proposal=proposal,checker=checker,corrections={},revision=0,
            candidate_sha256=self.inv['source_sha256'],candidate_info={'fields':[{'key':'x','label':'Assessment',
            'kind':'text','locator':{'paragraph':1}}],'document_backend':{},'review_requirements':[]},changes=[])
        return p

    def test_fixture_two_roles_bind_all_anchors_and_complete_original_stories(self):
        p=self.packet();validate_role(self.inv,p.proposal,'proposer');validate_role(self.inv,p.checker,'checker')
        self.assertEqual(len(p.proposal['anchors']),2)
        self.assertEqual(len(p.checker['stories']),len(self.inv['stories']))

    def test_ordinary_budget_quote_cannot_overrun_point_ten(self):
        config=self.config(mode='live');payload=prep.role_payload(self.inv,'proposer')
        self.assertEqual(prep.role_limits(self.inv),(2500,Decimal('0.10')))
        self.assertGreater(prep.maximum_cost({'text':'X'*100000},config),Decimal('0.10'))
        self.assertGreater(prep.maximum_cost(payload,config),0)

    def test_name_or_anchor_count_cannot_obtain_wm_exception(self):
        for alteration in ['name','anchors','source','backend']:
            value=deepcopy(self.inv)
            if alteration=='name':value['name']='WM IOV Template'
            if alteration=='anchors':value['anchors']*=45
            if alteration=='source':value['source_sha256']=WM_IOV_SHA256
            if alteration=='backend':value['document_backend']={'backend':'wm-iov-foss-v2','source_sha256':WM_IOV_SHA256}
            value['inventory_sha256']=digest({k:v for k,v in value.items() if k!='inventory_sha256'})
            self.assertEqual(prep.role_limits(value),(2500,Decimal('0.10')))

    def test_approval_seal_catches_proposal_checker_correction_placement_revision_and_candidate_drift(self):
        p=self.packet();sealed=approval_binding(p)
        for name in ['proposal','checker','corrections','revision','candidate_sha256','candidate_info','changes']:
            changed=deepcopy(p)
            if name=='revision':setattr(changed,name,1)
            elif name=='candidate_sha256':setattr(changed,name,'0'*64)
            elif name=='changes':setattr(changed,name,[{'anchor_id':'a1'}])
            else:getattr(changed,name)['tampered']=True
            self.assertNotEqual(approval_binding(changed),sealed)

    def version(self):
        p=self.packet();p.template.original_path='original.docx';p.template.format='docx'
        p.state='approved';p.approved_by_id='doctor1';p.approved_at='now';p.candidate_path='candidate.docx'
        (self.root/p.candidate_path).write_bytes((self.root/'original.docx').read_bytes())
        p.approval_sha256=approval_binding(p)
        return SimpleNamespace(template=p.template,template_id='template1',preparation=p,preparation_id='prep1',
            prepared_path=p.candidate_path,prepared_sha256=p.candidate_sha256,fields=p.candidate_info['fields'],
            document_backend={},review_requirements=[])

    def test_approved_source_is_distinct_and_both_original_and_candidate_are_checked(self):
        v=self.version();self.assertEqual(source_for_version(v),self.root/'candidate.docx')
        (self.root/'original.docx').write_bytes(b'changed')
        with self.assertRaises((ValidationError,ValueError)):source_for_version(v)

    def test_cross_template_unapproved_stale_and_altered_candidate_refuse(self):
        for kind in ['other','unapproved','stale','bytes','placement']:
            v=self.version()
            if kind=='other':v.template_id='other'
            if kind=='unapproved':v.preparation.state='review'
            if kind=='stale':v.preparation.revision=1
            if kind=='bytes':(self.root/'candidate.docx').write_bytes(b'bad')
            if kind=='placement':v.fields=[{**v.fields[0],'locator':{'paragraph':999}}]
            with self.subTest(kind=kind),self.assertRaises((ValidationError,ValueError)):source_for_version(v)

    def test_legacy_version_uses_original_and_cannot_claim_unsigned_prepared_source(self):
        p=self.packet();template=SimpleNamespace(original_path='original.docx',format='docx',sha256=self.inv['source_sha256'])
        v=SimpleNamespace(template=template,preparation_id=None,prepared_path='',prepared_sha256='')
        self.assertEqual(source_for_version(v),self.root/'original.docx')
        v.prepared_path='candidate.docx'
        with self.assertRaises(ValidationError):source_for_version(v)

    def test_fixture_returns_actual_fixture_model_separately_from_configured_label(self):
        _,evidence=prep.provider_role(self.inv,'proposer',self.config(),1)
        self.assertTrue(evidence['simulated']);self.assertEqual(evidence['cost'],'0')
        self.assertNotEqual(evidence['model'],self.config()['model'])

    def test_live_transport_zero_retries_and_actual_response_identity_are_retained(self):
        response=SimpleNamespace(model='actual-returned-model',id='response1',_request_id='request1',
            usage=SimpleNamespace(input_tokens=100,output_tokens=20,cache_read_input_tokens=4,cache_creation_input_tokens=0),
            content=[SimpleNamespace(type='text',text='{}')],model_dump=lambda **kw:{'model':'actual-returned-model','usage':{'input_tokens':100}})
        client=Mock();client.messages.create.return_value=response
        with patch('anthropic.Anthropic',return_value=client) as constructor:
            raw,evidence=prep.provider_role(self.inv,'proposer',self.config(mode='live'),7)
        constructor.assert_called_once_with(timeout=7,max_retries=0)
        self.assertEqual(client.messages.create.call_count,1)
        self.assertEqual(evidence['model'],'actual-returned-model');self.assertEqual(evidence['request_id'],'request1')
        self.assertEqual(evidence['resource_id'],'response1');self.assertFalse(evidence['simulated'])
        self.assertEqual(Decimal(evidence['cost']),Decimal('0.0004008'))

    def test_official_transport_schema_transform_preserves_local_exact_count_guards(self):
        from anthropic import transform_schema
        for role in ['proposer','checker']:
            original=prep.role_schema(role);before=deepcopy(original);wire=transform_schema(original)
            self.assertEqual(original,before)
            for key in ['anchors','stories']:
                self.assertIn('maxItems',original['properties'][key]);self.assertNotIn('maxItems',wire['properties'][key])
                self.assertEqual(wire['properties'][key]['items']['required'],original['properties'][key]['items']['required'])
                self.assertFalse(wire['properties'][key]['items']['additionalProperties'])
            result,_=prep.provider_role(self.inv,role,self.config(),1)
            result['anchors'].pop()
            with self.assertRaises(ValueError):validate_role(self.inv,result,role)

    def test_failure_diagnostic_is_closed_and_does_not_export_exception_text(self):
        import anthropic,httpx
        response=httpx.Response(400,request=httpx.Request('POST','https://offline.invalid'),headers={'request-id':'req_local_1'})
        error=anthropic.BadRequestError('private-key-and-document-text',response=response,body={'error':{'type':'invalid_request_error','message':'private-note'},'secret':'private-key'})
        evidence=prep.safe_provider_failure(error,'proposer','provider_role',12.5,False,False)
        self.assertEqual(evidence['error_class'],'BadRequestError');self.assertEqual(evidence['http_status'],400)
        self.assertEqual(evidence['provider_request_id'],'req_local_1');self.assertEqual(evidence['provider_error_type'],'invalid_request_error')
        self.assertNotIn('private',str(evidence));self.assertFalse(evidence['automatic_retry'])
        class HostileError(Exception):
            status_code=True;request_id='private\nheader';body={'error':{'type':'private-code'}}
        bad=prep.safe_provider_failure(HostileError('private'),'anything','anything',0,False,False)
        self.assertIsNone(bad['http_status']);self.assertEqual(bad['provider_request_id'],'')
        self.assertEqual(bad['error_class'],'other_exception');self.assertEqual(bad['provider_error_type'],'unestablished')

    def test_role_failure_retains_separate_evidence_without_model_usage_or_retry_claim(self):
        import anthropic,httpx,time,json
        response=httpx.Response(400,request=httpx.Request('POST','https://offline.invalid'),headers={'request-id':'req_local_2'})
        error=anthropic.BadRequestError('private-message',response=response,body={'error':{'type':'invalid_request_error'}})
        p=self.packet();p.config=self.config(mode='live')
        for after_response in [False,True]:
            receipt=SimpleNamespace(response_path='',response_sha256='',returned_model='',provider_request_id='',provider_resource_id='',
                computed_cost=None,usage={},failure={},failure_path='',failure_sha256='',save=Mock())
            manager=Mock();manager.count.return_value=0;manager.values_list.return_value=[];manager.create.return_value=receipt
            def fail(*args):
                if after_response:args[-1]({'model':'retained-real-response-model','request_id':'response_req','resource_id':'response_id','response':{'raw':'retained'},'cost':None})
                raise error
            with patch.object(prep.PreparationReceipt,'objects',manager),patch('core.preparation.provider_role',side_effect=fail) as provider:
                with self.assertRaises(anthropic.BadRequestError) as caught:prep.call_role(p,'proposer',time.monotonic()+30)
            self.assertIs(caught.exception,error);self.assertEqual(provider.call_count,1)
            self.assertEqual(receipt.state,'failed' if after_response else 'unknown')
            self.assertIsNone(receipt.computed_cost);self.assertEqual(receipt.usage,{})
            self.assertEqual(receipt.returned_model,'retained-real-response-model' if after_response else '')
            saved=json.loads((self.root/receipt.failure_path).read_bytes());self.assertEqual(saved,receipt.failure)
            self.assertEqual(saved['http_status'],400);self.assertNotIn('private-message',str(saved))
            if after_response:self.assertNotEqual(receipt.failure_path,receipt.response_path)
            else:self.assertEqual(receipt.response_path,'')

    def test_missing_usage_retains_raw_response_and_unknown_cost(self):
        response=SimpleNamespace(model='actual-model',id='response1',content=[],usage=None,
                                  model_dump=lambda **kw:{'model':'actual-model','usage':None})
        client=Mock();client.messages.create.return_value=response
        with patch('anthropic.Anthropic',return_value=client):
            _,evidence=prep.provider_role(self.inv,'proposer',self.config(mode='live'),1)
        self.assertIsNone(evidence['cost']);self.assertEqual(evidence['response']['usage'],None)

    def test_raw_response_is_observed_before_invalid_usage_or_content_properties(self):
        class Response:
            model='genuine-model';id='response1';_request_id='request1'
            def model_dump(self,**kw):return {'model':self.model,'usage':{'broken':True},'content':[{'type':'text','text':'bad'}]}
            @property
            def usage(self):raise ValueError('invalid usage property')
        client=Mock();client.messages.create.return_value=Response();seen=[]
        with patch('anthropic.Anthropic',return_value=client),self.assertRaises(ValueError):
            prep.provider_role(self.inv,'proposer',self.config(mode='live'),1,on_response=seen.append)
        self.assertEqual(len(seen),1);self.assertEqual(seen[0]['model'],'genuine-model')
        self.assertEqual(seen[0]['request_id'],'request1');self.assertIsNone(seen[0]['cost'])

    def test_candidate_keeps_exact_layout_reminder_and_blocks_unresolved_warning(self):
        advisory="DOCX answers expand and can change pagination. Review the exported document's layout."
        for extra in [None,'An unmapped clinical answer remains.',advisory+' Changed']:
            p=self.packet();p.template.original_path='original.docx';p.candidate_history=[];p.save=Mock()
            info={'fields':p.candidate_info['fields'],'warnings':[advisory]+([extra] if extra else [])}
            with patch('core.preparation.inspect_template',return_value=info):
                if extra:
                    with self.assertRaises(prep.DocumentError):prep.build_candidate(p,{})
                else:
                    prep.build_candidate(p,{})
                    self.assertEqual(p.candidate_info['warnings'],[advisory])
                    self.assertTrue((self.root/p.candidate_path).is_file())
        self.assertNotIn('An unmapped clinical answer remains.',prep.LAYOUT_ADVISORIES)

    def test_manual_row_warning_is_admitted_only_for_exact_candidate_row_proof(self):
        from documents.engine import UNMAPPED_NOTES
        from documents import inspect_template
        d=Document();d.add_paragraph('Name: {{Name}}');table=d.add_table(rows=1,cols=3)
        table.cell(0,0).text='Assessment';d.save(self.root/'original.docx')
        self.inv=inventory(self.root/'original.docx')
        choices={a['id']:a['choices'][0]['id'] for a in self.inv['anchors'] if a['kind']=='choose_cell'}
        for wrong in [False,True]:
            p=self.packet();p.template.original_path='original.docx';p.candidate_history=[];p.save=Mock()
            def inspected(path):
                info=inspect_template(path)
                if wrong:info['warnings']=[UNMAPPED_NOTES['multi_column'].format(count=2)]
                return info
            with patch('core.preparation.inspect_template',side_effect=inspected):
                if wrong:
                    with self.assertRaises(prep.DocumentError):prep.build_candidate(p,choices)
                else:
                    prep.build_candidate(p,choices)
                    self.assertEqual(p.candidate_info['reviewed_multi_column_rows'],[{'part':'word/document.xml','row':0}])
                    self.assertIn(UNMAPPED_NOTES['multi_column'].format(count=1),p.candidate_info['warnings'])

    def test_prepared_source_expected_hash_refuses_before_any_parser_process(self):
        from documents.service import _run,DocumentError
        with patch('documents.service.subprocess.run') as process:
            with self.assertRaises(DocumentError):_run(self.root/'original.docx','fill',expected_sha256='0'*64)
        process.assert_not_called()
