"""Product role protocol and historical evidence compatibility; no live calls."""
from copy import deepcopy
from contextlib import nullcontext
from decimal import Decimal
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import Mock, patch
from docx import Document
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from documents.preparation import inventory, TYPED_PROTOCOL, validate_role, digest
from core import preparation


class TypedRoleProductTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'original.docx'
        document = Document()
        document.add_paragraph('Temperature: ____ °C')
        document.add_paragraph('Fever: ____ (Yes / No)')
        document.add_paragraph('Patient signature: ____')
        document.save(self.path)
        self.config = {'mode': 'fixture', 'provider': 'anthropic', 'model': 'configured-label',
                       'input_rate': '3', 'output_rate': '15', 'cached_rate': '0.3'}

    def test_both_new_fixture_roles_include_metadata_and_are_clearly_simulated(self):
        value = inventory(self.path, protocol=TYPED_PROTOCOL)
        proposal, proposed_evidence = preparation.provider_role(value, 'proposer', self.config, 1)
        checked, checked_evidence = preparation.provider_role(value, 'checker', self.config, 1, proposal)
        for role, response, evidence in [('proposer', proposal, proposed_evidence), ('checker', checked, checked_evidence)]:
            validate_role(value, response, role)
            self.assertTrue(evidence['simulated'])
            self.assertEqual(evidence['model'], 'synthetic-blank-preparation-' + role)
            self.assertEqual(evidence['cost'], '0')
            self.assertEqual(response['anchors'][0]['metadata']['unit'], '°C')
            self.assertEqual(response['anchors'][1]['metadata']['choices'], ['Yes', 'No'])

    def test_historical_protocol_payload_schema_and_results_are_not_upgraded(self):
        value = inventory(self.path)
        before = deepcopy(value)
        proposal, _ = preparation.provider_role(value, 'proposer', self.config, 1)
        checker, _ = preparation.provider_role(value, 'checker', self.config, 1, proposal)
        self.assertFalse(any('metadata' in row for row in proposal['anchors'] + checker['anchors']))
        self.assertNotIn('metadata', preparation.role_schema('proposer')['properties']['anchors']['items']['properties'])
        self.assertEqual(preparation.role_payload(value, 'checker', proposal),
                         {'original': preparation.model_inventory(before), 'role': 'checker', 'proposal': proposal})
        validate_role(value, proposal, 'proposer')

    def test_short_schema_and_quote_fit_existing_per_role_bound_without_calling_api(self):
        value = inventory(self.path, protocol=TYPED_PROTOCOL)
        max_output, cap = preparation.role_limits(value)
        self.assertEqual((max_output, cap), (2500, Decimal('0.10')))
        proposal, _ = preparation.provider_role(value, 'proposer', self.config, 1)
        live = {**self.config, 'mode': 'live'}
        for role in ['proposer', 'checker']:
            payload = preparation.role_payload(value, role, proposal if role == 'checker' else None)
            self.assertLessEqual(preparation.maximum_cost(payload, live, max_output), cap)
        self.assertIn('metadata', preparation.role_schema('checker', TYPED_PROTOCOL)['properties']['anchors']['items']['required'])

    def test_pinned_sdk_transforms_both_typed_roles_without_weakening_source_checks(self):
        from anthropic import transform_schema
        value = inventory(self.path, protocol=TYPED_PROTOCOL)
        for role in ['proposer', 'checker']:
            schema = preparation.role_schema(role, TYPED_PROTOCOL)
            before = deepcopy(schema)
            # Preserve the actual pre-send counterexample without invoking a
            # client: the pinned SDK cannot transform JSON Schema type arrays.
            broken = deepcopy(schema)
            broken['properties']['anchors']['items']['properties']['metadata']['properties']['unit'] = {
                'type': ['string', 'null'], 'maxLength': 80}
            with self.assertRaises(AssertionError):
                transform_schema(broken)
            wire = transform_schema(schema)
            self.assertEqual(schema, before)
            metadata = wire['properties']['anchors']['items']['properties']['metadata']
            self.assertEqual(metadata['properties']['unit']['anyOf'][1], {'type': 'null'})
            self.assertEqual(metadata['properties']['unit']['anyOf'][0]['type'], 'string')
            # The SDK documents unsupported length limits in the wire schema;
            # local exact source checks remain mandatory after the response.
            self.assertIn('maxLength: 80', metadata['properties']['unit']['anyOf'][0]['description'])
            self.assertFalse(metadata['additionalProperties'])
            self.assertEqual(metadata['required'], before['properties']['anchors']['items']['properties']['metadata']['required'])
            proposal, _ = preparation.provider_role(value, 'proposer', self.config, 1)
            result, _ = preparation.provider_role(value, role, self.config, 1, proposal)
            validate_role(value, result, role)
            for unsupported_unit in [None, '°F', 'x'*81, False]:
                changed = deepcopy(result)
                changed['anchors'][0]['metadata']['unit'] = unsupported_unit
                with self.subTest(role=role, unsupported_unit=unsupported_unit), self.assertRaises(ValueError):
                    validate_role(value, changed, role)

    def test_nullable_unit_schema_matches_independent_bounded_string_contract(self):
        from pydantic import StringConstraints, TypeAdapter, ValidationError
        # Pydantic independently generates the same nullable 80-character
        # string schema; both declarations have the old union's meaning.
        adapter = TypeAdapter(Annotated[str, StringConstraints(max_length=80)] | None)
        for role in ['proposer', 'checker']:
            schema = preparation.role_schema(role, TYPED_PROTOCOL)
            unit = schema['properties']['anchors']['items']['properties']['metadata']['properties']['unit']
            self.assertEqual(unit, adapter.json_schema())
        for valid in [None, '', '°C', 'x'*80, '°'*80]:
            self.assertEqual(adapter.validate_python(valid, strict=True), valid)
        for invalid in ['x'*81, '°'*81, False, 0, 1.2, [], {}]:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                adapter.validate_python(invalid, strict=True)

    def test_typed_live_branch_reaches_stubbed_transport_for_both_roles(self):
        import json
        value = inventory(self.path, protocol=TYPED_PROTOCOL)
        proposal, _ = preparation.provider_role(value, 'proposer', self.config, 1)
        for role in ['proposer', 'checker']:
            fixture, _ = preparation.provider_role(value, role, self.config, 1, proposal)
            response = SimpleNamespace(model='offline-stub-returned-model', id='offline-response', _request_id='offline-request',
                usage=SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0),
                content=[SimpleNamespace(type='text', text=json.dumps(fixture))],
                model_dump=lambda **kw: {'model': 'offline-stub-returned-model', 'usage': {'input_tokens': 100, 'output_tokens': 20}})
            client = Mock(); client.messages.create.return_value = response
            observed = Mock()
            with patch('anthropic.Anthropic', return_value=client) as constructor:
                raw, evidence = preparation.provider_role(value, role, {**self.config, 'mode': 'live'}, 7, proposal, observed)
            constructor.assert_called_once_with(timeout=7, max_retries=0)
            client.messages.create.assert_called_once()
            arguments = client.messages.create.call_args.kwargs
            self.assertEqual(arguments['model'], self.config['model'])
            wire = arguments['output_config']['format']['schema']
            self.assertEqual(wire['properties']['anchors']['items']['properties']['metadata']['properties']['unit']['anyOf'][1], {'type': 'null'})
            self.assertEqual(json.loads(arguments['messages'][0]['content']), preparation.role_payload(value, role, proposal))
            validate_role(value, json.loads(raw), role)
            observed.assert_called_once()
            self.assertEqual(evidence['model'], 'offline-stub-returned-model')

    def underscore_source(self):
        document=Document()
        for text in ['Synthetic underscore form',
                'Choose one listed option for Fever. Preserve °C. Patient signature must remain blank.',
                'Patient name: ____________________','Date of birth: __________',
                'Temperature: ______ °C','Fever: Yes / No ______','Patient signature: ____________________']:
            document.add_paragraph(text)
        document.save(self.path)
        return inventory(self.path,protocol=TYPED_PROTOCOL)

    def test_canonical_text_and_dob_uncertainty_refuse_the_retained_failure_counterexample(self):
        # Actual failed response is retained unchanged under its SHA-256:
        # 6ff0708d23b08c2a5d994caa78bd323b8b06a7f4507f25b91a918fa105e773f7.
        # Reproduce its two wrong uncertainty values against equivalent source;
        # this is not a rewrite or successful replay of that paid response.
        value=self.underscore_source()
        self.assertEqual(value['questions'][0]['answer_constraints'],{'version':1,'data_type':'text'})
        self.assertEqual(value['questions'][1]['answer_constraints'],{'version':1,'data_type':'text'})
        for role in ['proposer','checker']:
            result,_=preparation.provider_role(value,role,self.config,1)
            validate_role(value,result,role)
            for index in [0,1]:
                metadata=result['anchors'][index]['metadata']
                self.assertEqual(metadata,{'label':'Patient name' if index==0 else 'Date of birth',
                    'data_type':'text','unit':None,'choices':[],'destination':'a'+str(index+1),
                    'uncertainty':'constraints_unstated'})
                wrong=deepcopy(result);wrong['anchors'][index]['metadata']['uncertainty']='none'
                with self.subTest(role=role,index=index),self.assertRaisesMessage(ValueError,
                        'The proposed field metadata differs from the original question, constraints or protection.'):
                    validate_role(value,wrong,role)
            self.assertEqual(result['anchors'][2]['metadata']['data_type'],'number')
            self.assertEqual(result['anchors'][2]['metadata']['unit'],'°C')
            self.assertEqual(result['anchors'][2]['metadata']['uncertainty'],'none')
            self.assertEqual(result['anchors'][3]['metadata']['choices'],['Yes','No'])
            self.assertEqual(result['anchors'][3]['metadata']['uncertainty'],'none')
            self.assertEqual(result['anchors'][4]['metadata']['uncertainty'],'signing_protected')
            for index,change in [(1,{'data_type':'date'}),(2,{'unit':'°F'}),
                    (3,{'choices':['Yes','No','Unknown']}),(4,{'uncertainty':'constraints_unstated'})]:
                wrong=deepcopy(result);wrong['anchors'][index]['metadata'].update(change)
                with self.subTest(role=role,index=index,change=change),self.assertRaises(ValueError):
                    validate_role(value,wrong,role)

    def test_actual_sdk_requests_explain_text_uncertainty_to_both_roles_and_preserve_v1(self):
        import httpx
        from anthropic import Anthropic
        value=self.underscore_source()
        proposal,_=preparation.provider_role(value,'proposer',self.config,1)
        historical=inventory(self.path)
        for source in [value,historical]:
            for role in ['proposer','checker']:
                fixture,_=preparation.provider_role(source,role,self.config,1)
                sent=[]
                def handle(request):
                    self.assertEqual(request.url.host,'synthetic-provider.invalid')
                    self.assertEqual(request.url.path,'/v1/messages')
                    sent.append(json.loads(request.content))
                    return httpx.Response(200,headers={'request-id':'offline-request'},json={
                        'id':'offline-response','type':'message','role':'assistant','model':'offline-returned-model',
                        'content':[{'type':'text','text':json.dumps(fixture)}],'stop_reason':'end_turn',
                        'stop_sequence':None,'usage':{'input_tokens':100,'output_tokens':20}})
                with httpx.Client(transport=httpx.MockTransport(handle)) as http:
                    client=Anthropic(api_key='synthetic-offline-only',base_url='https://synthetic-provider.invalid',
                        http_client=http,timeout=7,max_retries=0)
                    with patch('anthropic.Anthropic',return_value=client) as constructor:
                        raw,evidence=preparation.provider_role(source,role,{**self.config,'mode':'live'},7,
                            proposal if role=='checker' and source is value else None)
                constructor.assert_called_once_with(timeout=7,max_retries=0)
                self.assertEqual(len(sent),1)
                body=sent[0];payload=json.loads(body['messages'][0]['content'])
                self.assertEqual(body['model'],self.config['model'])
                self.assertEqual(payload['original'],preparation.model_inventory(source))
                self.assertEqual(payload['role'],role)
                validate_role(source,json.loads(raw),role)
                self.assertFalse(evidence['simulated'])
                self.assertEqual(evidence['model'],'offline-returned-model')
                if source is value:
                    prompt=body['system']
                    self.assertIn('version 1 and data_type text',prompt)
                    self.assertIn('does not justify uncertainty none',prompt)
                    self.assertIn('Date of birth label without a printed format remains text with constraints_unstated',prompt)
                    self.assertLess(prompt.index('(1) Signing'),prompt.index('(2) Ambiguous'))
                    self.assertLess(prompt.index('(2) Ambiguous'),prompt.index('(3) If the original inventory has issues'))
                    self.assertLess(prompt.index('(3) If the original inventory has issues'),prompt.index('(4) Otherwise every source text'))
                    self.assertIn('use uncertainty none',prompt)
                    self.assertEqual(payload['original']['questions'][1]['answer_constraints'],
                        {'version':1,'data_type':'text'})
                    self.assertNotIn('format',payload['original']['questions'][1]['answer_constraints'])
                    self.assertTrue(payload['original']['anchors'][4]['protected_signing'])
                    if role=='checker':self.assertEqual(payload['proposal'],proposal)
                else:
                    self.assertNotIn('Apply uncertainty in this exact priority order',body['system'])
                    self.assertFalse(any('metadata' in row for row in json.loads(raw)['anchors']))

    def test_metadata_display_escapes_untrusted_original_and_shows_uncertainty(self):
        metadata = {'label': '<script>original text</script>', 'data_type': 'number', 'unit': '°C',
                    'choices': [], 'destination': 'a1', 'uncertainty_label': 'Printed constraint verified'}
        html = render_to_string('template_preparation_metadata.html', {'metadata': metadata})
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('Unit: °C', html)
        self.assertIn('Printed constraint verified', html)


class TypedWMDeadlineTests(SimpleTestCase):
    """Deadline classifier/queue controls; synthetic SDK transport, no live API."""
    setUp=TypedRoleProductTests.setUp

    def wm_inventory(self):
        # A classifier fixture, not a claim that these synthetic questions were
        # discovered in WM. Actual WM source/mapping qualification is separate.
        value=inventory(self.path,protocol=TYPED_PROTOCOL)
        value['source_sha256']=preparation.WM_IOV_SHA256
        value['fields']=[{'key':'field_'+str(i),'label':'Synthetic question '+str(i),
            'kind':'text','locator':{'index':i}} for i in range(90)]
        value['questions']=[{'id':'q'+str(i),'text':'Synthetic question '+str(i),
            'protected_signing':False} for i in range(90)]
        value['anchors']=[{'id':'a'+str(i),'question_id':'q'+str(i),'kind':'existing',
            'field_key':'field_'+str(i),'locator':None,'protected_signing':False} for i in range(90)]
        value['stories']=[{**value['stories'][0],'part':'word/story'+str(i)+'.xml'} for i in range(16)]
        value['review_requirements']=[{'key':'claim_'+str(i)} for i in range(14)]
        value['document_backend']={'backend':'wm-iov-foss-v2','source_sha256':preparation.WM_IOV_SHA256,
            'mapping_digest':preparation.WM_MAPPING_DIGEST}
        value['issues']=[]
        self.seal(value)
        return value

    def seal(self,value):
        value['inventory_sha256']=digest({k:v for k,v in value.items() if k!='inventory_sha256'})

    def test_only_complete_source_qualified_typed_wm_gets_the_longer_deadline(self):
        value=self.wm_inventory()
        before=deepcopy(value)
        self.assertEqual(preparation.timing_limits(value),(120,360))
        self.assertEqual(preparation.role_limits(value),(12000,Decimal('0.30')))
        self.assertEqual(value,before)
        self.assertEqual(preparation.timing_limits(inventory(self.path,protocol=TYPED_PROTOCOL)),(60,180))
        for changed in ['protocol','source','backend','backend_source','mapping','backend_extra',
                'fields','anchors','questions','stories','review_requirements','kind','issues']:
            bad=deepcopy(value)
            if changed=='protocol':bad['protocol']='blank-word-preparation-v1'
            elif changed=='source':bad['source_sha256']='0'*64
            elif changed=='backend':bad['document_backend']['backend']='other'
            elif changed=='backend_source':bad['document_backend']['source_sha256']='0'*64
            elif changed=='mapping':bad['document_backend']['mapping_digest']='0'*64
            elif changed=='backend_extra':bad['document_backend']['unapproved']=True
            elif changed=='kind':bad['anchors'][0]['kind']='literal_blank'
            elif changed=='issues':bad['issues']=[{'code':'unsupported_structure','message':'Synthetic issue'}]
            else:bad[changed].pop()
            self.seal(bad)
            with self.subTest(changed=changed):
                self.assertEqual(preparation.timing_limits(bad),(60,180))
        historical=deepcopy(value);historical['protocol']='blank-word-preparation-v1';self.seal(historical)
        self.assertEqual(preparation.role_limits(historical),(6000,Decimal('0.16')))
        bad=deepcopy(value);bad['source_sha256']='0'*64
        with self.assertRaises(ValueError):preparation.timing_limits(bad)

    def receipt(self):
        return SimpleNamespace(response_path='',computed_cost=None,quote_maximum=Decimal('0.220432'),
            state='running',save=Mock())

    def test_actual_sdk_timeout_is_scoped_clamped_and_never_retries(self):
        import httpx
        from anthropic import Anthropic,transform_schema
        prompts=[]
        wm=self.wm_inventory();ordinary=inventory(self.path,protocol=TYPED_PROTOCOL)
        for value,remaining,expected_timeout in [(wm,300,120),(wm,43,43),(ordinary,170,60)]:
            for role in ['proposer','checker']:
                fixture,_=preparation.provider_role(value,role,self.config,1)
                before=deepcopy(value);sent=[];clients=[]
                def handle(request):
                    self.assertEqual(request.url.host,'synthetic-provider.invalid')
                    self.assertEqual(request.extensions['timeout']['read'],expected_timeout)
                    sent.append(json.loads(request.content))
                    return httpx.Response(200,headers={'request-id':'offline-request'},json={
                        'id':'offline-response','type':'message','role':'assistant','model':'offline-returned-model',
                        'content':[{'type':'text','text':json.dumps(fixture)}],'stop_reason':'end_turn',
                        'stop_sequence':None,'usage':{'input_tokens':100,'output_tokens':20}})
                def client(**kwargs):
                    self.assertEqual(kwargs,{'timeout':expected_timeout,'max_retries':0})
                    result=Anthropic(api_key='synthetic-offline-only',base_url='https://synthetic-provider.invalid',
                        http_client=http,**kwargs);clients.append(result);return result
                packet=SimpleNamespace(inventory=value,config={**self.config,'mode':'live'})
                with httpx.Client(transport=httpx.MockTransport(handle)) as http, \
                        patch('anthropic.Anthropic',side_effect=client), \
                        patch('core.testing_authority.identity',return_value=True), \
                        patch('core.testing_authority.reserve_role',return_value=self.receipt()), \
                        patch('core.preparation_campaign.provider_slot',return_value=nullcontext()), \
                        patch.object(preparation,'retain_response',return_value=('offline.json','a'*64)), \
                        patch.object(preparation.time,'monotonic',return_value=100):
                    result=preparation.call_role(packet,role,100+remaining)
                self.assertEqual(result,fixture);self.assertEqual(len(sent),1)
                self.assertEqual(clients[0].max_retries,0)
                self.assertEqual(sent[0]['max_tokens'],12000 if value is wm else 2500)
                self.assertEqual(sent[0]['output_config']['format']['schema'],
                    transform_schema(preparation.role_schema(role,TYPED_PROTOCOL)))
                prompts.append((role,sent[0]['system']))
                self.assertEqual(packet.config,{**self.config,'mode':'live'})
                self.assertEqual(value,before)
        for role in ['proposer','checker']:
            self.assertEqual(len({prompt for item,prompt in prompts if item==role}),1)

    def worker_fixture(self,value,inspection_seconds,role_seconds,candidate_seconds):
        clock={'now':100.0};packet=SimpleNamespace(inventory={},config={'word_preparation_protocol':value['protocol']},
            template=SimpleNamespace(sha256=value['source_sha256'],department='synthetic-department',original_path='original.docx'),
            requested_by='synthetic-doctor',state='queued',pk='synthetic-prep',save=Mock(),error_code='')
        manager=Mock();manager.select_for_update.return_value.filter.return_value.order_by.return_value.first.return_value=packet
        manager.filter.return_value.exists.return_value=False
        def inspect(*args,**kwargs):clock['now']+=inspection_seconds;return deepcopy(value)
        calls=[]
        def role(prep,which,deadline,proposal=None):
            calls.append((which,deadline));clock['now']+=role_seconds
            return preparation.provider_role(value,which,self.config,1)[0]
        def candidate(*args):clock['now']+=candidate_seconds
        with patch.object(preparation,'feature_enabled',return_value=True), \
                patch.object(preparation.transaction,'atomic',side_effect=nullcontext), \
                patch.object(preparation.TemplatePreparation,'objects',manager), \
                patch.object(preparation,'membership'),patch.object(preparation,'private_path',return_value=self.path), \
                patch.object(preparation,'inspect_template'),patch.object(preparation,'inspect_preparation',side_effect=inspect), \
                patch.object(preparation,'call_role',side_effect=role), \
                patch.object(preparation,'build_candidate',side_effect=candidate) as build, \
                patch.object(preparation,'audit'),patch.object(preparation.time,'monotonic',side_effect=lambda:clock['now']):
            self.assertTrue(preparation.run_one())
        return packet,calls,build

    def test_worker_total_clock_includes_inventory_and_preserves_default_profile(self):
        for value,total in [(self.wm_inventory(),360),(inventory(self.path,protocol=TYPED_PROTOCOL),180),
                (inventory(self.path),180)]:
            before=deepcopy(value)
            packet,calls,build=self.worker_fixture(value,20,20,10)
            self.assertEqual(calls,[('proposer',100+total),('checker',100+total)])
            self.assertIn(packet.state,['review','guided']);build.assert_called_once()
            self.assertEqual(value,before)
            self.assertEqual(packet.config,{'word_preparation_protocol':value['protocol']})

    def test_inventory_time_cannot_buy_a_fresh_total_deadline_or_skip_candidate_reserve(self):
        packet,calls,build=self.worker_fixture(self.wm_inventory(),110,100,1)
        self.assertEqual(calls,[('proposer',460),('checker',460)])
        self.assertEqual(packet.state,'blocked');self.assertEqual(packet.error_code,'deadline')
        build.assert_not_called()  # Only50s remain; the existing60s reserve is mandatory.

    def test_candidate_completion_is_checked_against_the_original_total_deadline(self):
        packet,_,build=self.worker_fixture(self.wm_inventory(),20,100,141)
        build.assert_called_once()
        self.assertEqual(packet.state,'blocked');self.assertEqual(packet.error_code,'deadline')

    def test_timed_out_role_retains_unknown_quote_and_cannot_buy_a_replay(self):
        import httpx
        from anthropic import Anthropic,APITimeoutError
        from django.core.exceptions import ValidationError
        value=self.wm_inventory();receipt=self.receipt();sent=[]
        def handle(request):
            sent.append(request);raise httpx.ReadTimeout('synthetic timeout',request=request)
        packet=SimpleNamespace(inventory=value,config={**self.config,'mode':'live'})
        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            client=Anthropic(api_key='synthetic-offline-only',base_url='https://synthetic-provider.invalid',
                http_client=http,timeout=120,max_retries=0)
            with patch('anthropic.Anthropic',return_value=client), \
                    patch('core.testing_authority.identity',return_value=True), \
                    patch('core.testing_authority.reserve_role',side_effect=[receipt,ValidationError('Role already reserved')]), \
                    patch('core.preparation_campaign.provider_slot',return_value=nullcontext()), \
                    patch.object(preparation,'retain_response',return_value=('offline-failure.json','b'*64)), \
                    patch.object(preparation.time,'monotonic',return_value=100):
                with self.assertRaises(APITimeoutError):preparation.call_role(packet,'proposer',460)
                frozen=(receipt.state,receipt.quote_maximum,receipt.computed_cost,deepcopy(receipt.failure))
                with self.assertRaises(ValidationError):preparation.call_role(packet,'proposer',460)
        self.assertEqual(len(sent),1)
        self.assertEqual(receipt.state,'unknown');self.assertIsNone(receipt.computed_cost)
        self.assertEqual(receipt.quote_maximum,Decimal('0.220432'))
        self.assertFalse(receipt.failure['automatic_retry']);self.assertFalse(receipt.failure['response_retained'])
        self.assertEqual(receipt.failure['error_class'],'APITimeoutError')
        self.assertEqual((receipt.state,receipt.quote_maximum,receipt.computed_cost,receipt.failure),frozen)

