"""Real async SDK streams over offline HTTPX transports; no database or network."""
import asyncio
from contextlib import ExitStack, nullcontext
from copy import deepcopy
import hashlib
import json
import os
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

from anthropic import AsyncAnthropic, BadRequestError
from django.test import SimpleTestCase
import httpx

from core import preparation, preparation_stream_transport as transport
from core import preparation_choice_transport as codec
from core.tests.test_preparation_error_evidence import PreparationErrorEvidenceTests
from core.tests.test_preparation_schema_transport import PreparationSchemaTransportTests
from core.tests.test_preparation_choice_transport import encoded
from core.security import private_path
from documents import DocumentError
from documents.preparation import digest, TYPED_PROTOCOL
from documents.component_contracts import CONFIG_KEY, CHOICE_CONTRACT


SECRET = 'synthetic-stream-credential-do-not-copy'


def event(kind, **data):
    return ('event: '+kind+'\ndata: '+json.dumps({'type':kind, **data})+'\n\n').encode()


def events(value, *, stop='end_turn', terminal=True, chunks=3):
    text=json.dumps(value, ensure_ascii=False)
    result=[event('message_start', message={'id':'msg_offline_stream','type':'message',
        'role':'assistant','model':'offline-configured-label','content':[], 'stop_reason':None,
        'stop_sequence':None,'usage':{'input_tokens':10,'output_tokens':0,
            'cache_read_input_tokens':2,'cache_creation_input_tokens':1}}),
        event('content_block_start', index=0, content_block={'type':'text','text':''})]
    width=max(1,len(text)//chunks)
    result += [event('content_block_delta',index=0,delta={'type':'text_delta','text':text[i:i+width]})
               for i in range(0,len(text),width)]
    result += [event('content_block_stop',index=0), event('message_delta',
        delta={'stop_reason':stop,'stop_sequence':None},usage={'output_tokens':20})]
    if terminal:result.append(event('message_stop'))
    return result


class Body(httpx.AsyncByteStream):
    def __init__(self, pieces, *, delay=0, endless=False, read_hook=None):
        self.pieces=pieces;self.delay=delay;self.endless=endless;self.closed=False;self.read_hook=read_hook
        self.closed_at=None
    async def __aiter__(self):
        if self.read_hook:self.read_hook()
        for piece in self.pieces:
            if self.delay:await asyncio.sleep(self.delay)
            yield piece
        while self.endless:
            await asyncio.sleep(.005)
            yield event('ping')
    async def aclose(self):
        self.closed=True;self.closed_at=time.monotonic()


class PreparationStreamTransportTests(SimpleTestCase):
    setUp=PreparationSchemaTransportTests.setUp
    receipt=PreparationErrorEvidenceTests.receipt

    def live(self, *, choice=False):
        config={**self.config,'mode':'live', 'word_preparation_protocol':TYPED_PROTOCOL,
                transport.CONFIG_KEY:transport.TRANSPORT}
        if choice:
            config[CONFIG_KEY]=CHOICE_CONTRACT
            config[preparation.SCHEMA_TRANSPORT_KEY]=codec.TRANSPORT
        return config

    def canonical(self, role='proposer', proposal=None, *, choice=False):
        config=self.live(choice=choice)
        config['mode']='fixture';del config[transport.CONFIG_KEY]
        config.pop(preparation.SCHEMA_TRANSPORT_KEY,None)
        return preparation.provider_role(self.inventory,role,config,1,proposal)[0]

    def sdk_client(self, body, sent, *, status=200, request_id='req_offline_stream'):
        async def handle(request):
            sent.append(json.loads(request.content))
            return httpx.Response(status,request=request, headers={'request-id':request_id,
                'content-type':'text/event-stream' if status==200 else 'application/json'},stream=body)
        return AsyncAnthropic(api_key=SECRET,base_url='https://synthetic-provider.invalid',
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),max_retries=0,timeout=60)

    def invoke(self, body, *, role='proposer', proposal=None, choice=False, seconds=60, status=200,
               fault=None, request_id='req_offline_stream'):
        config=self.live(choice=choice);receipt=self.receipt();sent=[]
        receipt.request_sha256=digest(preparation.role_payload(self.inventory,role,proposal,config=config))
        prep=SimpleNamespace(inventory=self.inventory,config=config,proposal=proposal)
        receipt.preparation=prep;receipt.role=role
        client=self.sdk_client(body,sent,status=status,request_id=request_id)
        with ExitStack() as stack:
            stack.enter_context(patch.dict(os.environ,{'ANTHROPIC_API_KEY':SECRET}))
            factory=stack.enter_context(patch('anthropic.AsyncAnthropic',return_value=client))
            stack.enter_context(patch('core.testing_authority.identity',return_value=True))
            reserve=stack.enter_context(patch('core.testing_authority.reserve_role',return_value=receipt))
            stack.enter_context(patch('core.preparation_campaign.provider_slot',return_value=nullcontext()))
            stack.enter_context(patch.object(preparation,'timing_limits',return_value=(seconds,480)))
            if fault:stack.enter_context(fault)
            try:result=preparation.call_role(prep,role,time.monotonic()+60,proposal)
            except BaseException as exc:result=exc
        return result,receipt,sent,client,factory,reserve

    def trace(self, receipt, phase):
        pointer=receipt.failure[transport.POINTER_KEY][phase]
        raw=private_path(pointer['path']).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),pointer['sha256'])
        self.assertEqual(private_path(pointer['path']).stat().st_mode&0o777,0o600)
        return json.loads(raw)

    def test_real_sdk_both_roles_wire_body_canonical_validation_usage_and_replay(self):
        proposal=self.canonical(choice=True)
        for role in ('proposer','checker'):
            value=self.canonical(role,proposal,choice=True)
            body=Body(events(encoded(value,codec.TRANSPORT)))
            result,receipt,sent,client,factory,reserve=self.invoke(body,role=role,proposal=proposal,choice=True)
            self.assertEqual(result,value)
            self.assertEqual(receipt.state,'succeeded')
            self.assertEqual(receipt.usage,{'input_tokens':10,'output_tokens':20,
                'cached_input_tokens':2,'cache_creation_tokens':1})
            self.assertIsNotNone(receipt.computed_cost)
            self.assertEqual(receipt.provider_request_id,'req_offline_stream')
            expected=preparation.provider_request(self.inventory,role,self.live(choice=True),proposal)
            self.assertEqual(sent,[expected]);self.assertIs(sent[0]['stream'],True)
            self.assertEqual(factory.call_args.kwargs['max_retries'],0)
            self.assertEqual(reserve.call_count,1)
            self.assertTrue(client.is_closed());self.assertTrue(body.closed)
            raw=json.loads(private_path(receipt.response_path).read_bytes())
            self.assertTrue(raw['stream_complete']);self.assertEqual(raw['provider_transport'],transport.TRANSPORT)
            self.assertEqual(raw['request_envelope_sha256'],digest(sent[0]))
            self.assertEqual(preparation.read_retained_role(receipt,'live'),value)
            self.assertTrue(self.trace(receipt,'complete')['stream_complete'])

    def test_header_metadata_is_private_immutable_and_durable_before_first_body_read(self):
        receipt_seen=[]
        original=self.receipt
        def make():
            receipt=original();receipt_seen.append(receipt);return receipt
        def before_read():
            receipt=receipt_seen[0]
            self.assertEqual(receipt.persisted['provider_request_id'],'req_offline_stream')
            self.assertIsNone(receipt.computed_cost)
            self.assertFalse(self.trace(receipt,'headers')['stream_complete'])
        with patch.object(self,'receipt',side_effect=make):
            result,receipt,*_=self.invoke(Body(events(self.canonical()),read_hook=before_read))
        self.assertNotIsInstance(result,BaseException)
        self.assertEqual(receipt.failure[transport.POINTER_KEY]['contract'],transport.CONTRACT)

    def test_clean_eof_after_end_turn_is_unknown_and_never_adopted_or_retried(self):
        body=Body(events(self.canonical(),terminal=False))
        result,receipt,sent,client,*_=self.invoke(body)
        self.assertIsInstance(result,transport.PreparationStreamError)
        self.assertEqual(result.local_reason,'unexpected_eof')
        self.assertEqual(receipt.state,'unknown');self.assertIsNone(receipt.computed_cost)
        self.assertFalse(receipt.response_path);self.assertEqual(len(sent),1)
        self.assertEqual(receipt.failure['provider_error_type'],'unestablished')
        self.assertIsNone(receipt.failure['http_status'])
        self.assertEqual(receipt.failure['stream_http_status'],200)
        self.assertTrue(body.closed);self.assertTrue(client.is_closed())
        self.assertFalse(self.trace(receipt,'partial')['stream_complete'])

    def test_real_wall_deadline_cancels_body_await_and_endless_pings_with_one_send(self):
        for body in (Body([],endless=True), Body(events(self.canonical()),delay=.03)):
            started=time.monotonic()
            result,receipt,sent,client,*_=self.invoke(body,seconds=.025)
            self.assertLess(time.monotonic()-started,1)
            self.assertIsInstance(result,transport.PreparationStreamError)
            self.assertEqual(result.local_reason,'deadline')
            self.assertEqual(receipt.state,'unknown');self.assertIsNone(receipt.computed_cost)
            self.assertEqual(len(sent),1);self.assertTrue(body.closed);self.assertTrue(client.is_closed())

    def test_incomplete_or_malformed_streams_never_adopt(self):
        good=events(self.canonical())
        variants=[good[:1], good[:-3]+good[-2:], [good[0],good[0]]+good[1:],
            [good[0],event('content_block_start',index=1,content_block={'type':'text','text':''})]+good[2:],
            good[:-2]+[event('message_delta',delta={'stop_reason':'end_turn'},usage={}),good[-1]]]
        for pieces in variants:
            with self.subTest(pieces=len(pieces)):
                result,receipt,sent,client,*_=self.invoke(Body(pieces))
                self.assertIsInstance(result,BaseException)
                self.assertEqual(receipt.state,'unknown');self.assertIsNone(receipt.computed_cost)
                self.assertFalse(receipt.response_path);self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_max_tokens_retains_actual_terminal_response_and_known_billable_usage(self):
        result,receipt,sent,*_=self.invoke(Body(events(self.canonical(),stop='max_tokens')))
        self.assertIsInstance(result,DocumentError);self.assertEqual(result.code,'output_limit')
        self.assertEqual(receipt.state,'failed');self.assertIsNotNone(receipt.computed_cost)
        self.assertTrue(receipt.response_path);self.assertEqual(len(sent),1)
        self.assertEqual(json.loads(private_path(receipt.response_path).read_bytes())['response']['stop_reason'],'max_tokens')

    def test_actual_http_error_keeps_sdk_status_id_sanitizer_and_zero_retry(self):
        payload={'type':'error','error':{'type':'invalid_request_error','message':SECRET}}
        body=Body([json.dumps(payload).encode()])
        result,receipt,sent,client,*_=self.invoke(body,status=400,request_id='req_bad_request')
        self.assertIsInstance(result,BadRequestError);self.assertEqual(len(sent),1)
        self.assertEqual(receipt.state,'unknown');self.assertIsNone(receipt.computed_cost)
        self.assertEqual(receipt.failure['http_status'],400)
        self.assertEqual(receipt.failure['provider_request_id'],'req_bad_request')
        self.assertEqual(receipt.failure['provider_error_type'],'invalid_request_error')
        self.assertNotIn(SECRET,json.dumps(receipt.failure));self.assertTrue(client.is_closed())

    def test_private_event_projection_cannot_reassemble_split_credentials_or_clinical_text(self):
        value={'synthetic-private-clinical-marker':SECRET}
        result,receipt,*_=self.invoke(Body(events(value,chunks=80)))
        self.assertIsInstance(result,BaseException)  # Canonical validator rejects this structure.
        trace=self.trace(receipt,'complete')
        raw=json.dumps(trace)
        self.assertNotIn('synthetic-private-clinical-marker',raw);self.assertNotIn(SECRET,raw)
        self.assertNotIn('text',raw);self.assertGreater(trace['events_omitted'],0)
        for row in trace['first_events']+trace['last_events']:
            self.assertEqual(set(row),{'type','bytes','sha256'})
        self.assertNotIn(SECRET,json.dumps(receipt.failure))

    def test_invalid_explicit_marker_refuses_before_client_or_reservation(self):
        for marker in (None,False,True,0,'','future'):
            config={**self.live(),transport.CONFIG_KEY:marker}
            with self.subTest(marker=marker),patch('anthropic.AsyncAnthropic') as client, \
                    patch('core.testing_authority.reserve_role') as reserve:
                with self.assertRaises(DocumentError):
                    preparation.call_role(SimpleNamespace(inventory=self.inventory,config=config),'proposer',time.monotonic()+60)
                client.assert_not_called();reserve.assert_not_called()

    def test_legacy_absence_has_no_stream_no_new_payload_marker_and_unchanged_limits(self):
        config=self.live();del config[transport.CONFIG_KEY]
        before=deepcopy(config)
        envelope=preparation.provider_request(self.inventory,'proposer',config)
        self.assertNotIn('stream',envelope)
        self.assertNotIn('provider_transport',preparation.role_payload(self.inventory,'proposer',config=config))
        self.assertEqual(config,before)
        self.assertEqual(preparation.role_limits(self.inventory,config),preparation.role_limits(self.inventory,self.live()))
        self.assertEqual(preparation.timing_limits(self.inventory,config),preparation.timing_limits(self.inventory,self.live()))

    def test_bound_evidence_refuses_wrong_request_transport_receipt_and_missing_terminal(self):
        value=self.canonical();config=self.live()
        result,receipt,*_=self.invoke(Body(events(value)))
        self.assertEqual(result,value)
        evidence=json.loads(private_path(receipt.response_path).read_bytes())
        for key,new in (('provider_transport','wrong'),('stream_complete',False),
                        ('request_envelope_sha256','a'*64)):
            bad={**evidence,key:new}
            with self.subTest(key=key),self.assertRaises(DocumentError):
                preparation.decode_role_response(self.inventory,'proposer',config,value,None,bad,receipt.request_sha256)
        with self.assertRaises(DocumentError):
            preparation.decode_role_response(self.inventory,'proposer',config,value,None,evidence,'b'*64)
        old={**config};del old[transport.CONFIG_KEY]
        with self.assertRaises(DocumentError):
            preparation.decode_role_response(self.inventory,'proposer',old,value,None,evidence,receipt.request_sha256)

    def test_retention_failure_after_terminal_preserves_usage_without_adoption(self):
        original=preparation.retain_response
        def retain(prep,role,evidence):
            if 'response' in evidence:raise OSError('offline full-response retention failure')
            return original(prep,role,evidence)
        result,receipt,sent,client,*_=self.invoke(Body(events(self.canonical())),
            fault=patch.object(preparation,'retain_response',side_effect=retain))
        self.assertIsInstance(result,transport.CompleteStreamObservationError)
        self.assertIsNotNone(receipt.computed_cost);self.assertEqual(receipt.state,'failed')
        self.assertFalse(receipt.response_path);self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_header_callback_failure_stops_before_body_unknown_and_no_late_publication(self):
        read=[]
        result,receipt,sent,client,*_=self.invoke(Body(events(self.canonical()),read_hook=lambda:read.append(True)),
            fault=patch.object(preparation,'retain_response',side_effect=OSError('offline trace retention failure')))
        self.assertIsInstance(result,OSError);self.assertEqual(receipt.state,'unknown')
        self.assertIsNone(receipt.computed_cost);self.assertFalse(read);self.assertEqual(len(sent),1)
        self.assertTrue(client.is_closed());self.assertEqual(receipt.persisted['provider_request_id'],'req_offline_stream')

    def test_cancelled_sync_callback_is_joined_before_unknown_completion(self):
        writes=[];original=preparation.retain_response;thread_id=threading.get_ident()
        def slow(prep,role,evidence):
            if evidence.get('contract')==transport.CONTRACT and evidence['event_count']==0:
                self.assertEqual(threading.get_ident(),thread_id)
                time.sleep(.10);writes.append(time.monotonic())
            return original(prep,role,evidence)
        body=Body(events(self.canonical()))
        result,receipt,sent,client,*_=self.invoke(body,seconds=.02,
            fault=patch.object(preparation,'retain_response',side_effect=slow))
        self.assertIsInstance(result,transport.PreparationStreamError);self.assertTrue(writes)
        self.assertTrue(client.is_closed());self.assertEqual(receipt.state,'unknown')
        self.assertLess(body.closed_at,writes[0]-.04)
        count=len(writes);time.sleep(.03);self.assertEqual(len(writes),count)

    def test_late_complete_response_callback_never_adopts_but_keeps_known_usage(self):
        original=preparation.retain_response
        def slow(prep,role,evidence):
            if 'response' in evidence:time.sleep(.08)
            return original(prep,role,evidence)
        body=Body(events(self.canonical()))
        result,receipt,sent,client,*_=self.invoke(body,seconds=.06,
            fault=patch.object(preparation,'retain_response',side_effect=slow))
        self.assertIsInstance(result,transport.CompleteStreamObservationError)
        self.assertEqual(receipt.state,'failed');self.assertIsNotNone(receipt.computed_cost)
        self.assertTrue(receipt.response_path);self.assertTrue(body.closed);self.assertTrue(client.is_closed())
        self.assertEqual(len(sent),1)

    def test_midstream_sdk_error_is_not_a_terminal_message_or_known_usage(self):
        pieces=events(self.canonical())[:3]+[event('error',error={
            'type':'overloaded_error','message':SECRET})]
        result,receipt,sent,client,*_=self.invoke(Body(pieces))
        self.assertIsInstance(result,BaseException);self.assertEqual(receipt.state,'unknown')
        self.assertIsNone(receipt.computed_cost);self.assertFalse(receipt.response_path)
        self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())
        self.assertNotIn(SECRET,json.dumps(receipt.failure))

    def test_secret_header_id_is_not_retained_as_ordinary_request_identity(self):
        result,receipt,*_=self.invoke(Body(events(self.canonical())),request_id=SECRET)
        self.assertNotIn(SECRET,json.dumps(receipt.failure))
        self.assertNotIn(SECRET,receipt.provider_request_id)
        self.assertEqual(self.trace(receipt,'headers')['provider_request_id'],'')

    def test_incremental_size_rejection_keeps_unknown_hold_and_closes_once(self):
        pieces=events(self.canonical())[:2]+[event('content_block_delta',index=0,
            delta={'type':'text_delta','text':'x'*(transport.MAX_RESPONSE_BYTES+1)})]
        result,receipt,sent,client,*_=self.invoke(Body(pieces))
        self.assertIsInstance(result,transport.PreparationStreamError)
        self.assertEqual(result.local_reason,'response_size_limit')
        self.assertEqual(receipt.state,'unknown');self.assertIsNone(receipt.computed_cost)
        self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_callback_timeout_before_deadline_preserves_local_cause(self):
        result,receipt,sent,client,*_=self.invoke(Body(events(self.canonical())),
            fault=patch.object(preparation,'retain_response',side_effect=TimeoutError('offline local callback')))
        self.assertIs(type(result),TimeoutError)
        self.assertEqual(receipt.failure['local_transport_reason'],'transport_or_callback_exception')
        self.assertEqual(receipt.state,'unknown');self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_immediately_buffered_ping_flood_cannot_starve_absolute_deadline(self):
        class Flood(Body):
            async def __aiter__(self):
                while True:yield event('ping')
        body=Flood([]);started=time.monotonic()
        result,receipt,sent,client,*_=self.invoke(body,seconds=.025)
        self.assertLess(time.monotonic()-started,1)
        self.assertIsInstance(result,transport.PreparationStreamError)
        self.assertEqual(receipt.state,'unknown');self.assertIsNone(receipt.computed_cost)
        self.assertEqual(len(sent),1);self.assertTrue(body.closed);self.assertTrue(client.is_closed())

    def test_complete_stream_raw_response_must_match_decoded_value_without_choice_codec(self):
        value=self.canonical()
        result,receipt,*_=self.invoke(Body(events(value)))
        self.assertEqual(result,value)
        evidence=json.loads(private_path(receipt.response_path).read_bytes())
        bad=deepcopy(value);bad['inventory_sha256']='a'*64
        with self.assertRaises(DocumentError):
            preparation.decode_role_response(self.inventory,'proposer',self.live(),bad,None,evidence,receipt.request_sha256)

    def test_thinking_signature_and_redacted_blocks_close_generically_before_text(self):
        original=events(self.canonical())
        pieces=original[:1]+[
            event('content_block_start',index=0,content_block={'type':'thinking','thinking':'','signature':''}),
            event('content_block_delta',index=0,delta={'type':'thinking_delta','thinking':'synthetic-private-thinking'}),
            event('content_block_delta',index=0,delta={'type':'signature_delta','signature':'synthetic-signature'}),
            event('content_block_stop',index=0),
            event('content_block_start',index=1,content_block={'type':'redacted_thinking','data':'synthetic-redacted'}),
            event('content_block_stop',index=1)]
        for raw in original[1:]:
            lines=raw.decode().splitlines()
            value=json.loads(lines[1][6:])
            if 'index' in value:value['index']=2
            kind=value.pop('type');pieces.append(event(kind,**value))
        result,receipt,sent,client,*_=self.invoke(Body(pieces))
        self.assertEqual(result,self.canonical());self.assertEqual(receipt.state,'succeeded')
        raw=json.loads(private_path(receipt.response_path).read_bytes())
        self.assertEqual([b['type'] for b in raw['response']['content']],['thinking','redacted_thinking','text'])
        self.assertNotIn('synthetic-private-thinking',json.dumps(self.trace(receipt,'complete')))
        self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_new_queue_alone_selects_streaming_and_never_mutates_saved_configuration(self):
        for mode,provider in (('live','anthropic'),('fixture','anthropic'),('live','openai')):
            config={**self.config,'mode':mode,'provider':provider};before=deepcopy(config)
            with patch.object(preparation,'configuration',return_value=config), \
                    patch('core.preparation_campaign.active_campaign_config',side_effect=lambda value,_:value), \
                    patch('core.testing_authority.identity',return_value=True), \
                    patch('core.testing_authority.create_preparation') as create:
                preparation.create_preparation(SimpleNamespace(sha256='a'*64),SimpleNamespace())
            queued=create.call_args.args[2]
            if (mode,provider)==('live','anthropic'):
                self.assertEqual(queued[transport.CONFIG_KEY],transport.TRANSPORT)
            else:self.assertNotIn(transport.CONFIG_KEY,queued)
            self.assertEqual(config,before)
        bad={**self.live(),transport.CONFIG_KEY:'unrecognized'}
        with patch.object(preparation,'configuration',return_value=bad), \
                patch('core.preparation_campaign.active_campaign_config',side_effect=lambda value,_:value), \
                patch('core.testing_authority.create_preparation') as create:
            with self.assertRaises(DocumentError):
                preparation.create_preparation(SimpleNamespace(sha256='a'*64),SimpleNamespace())
            create.assert_not_called()

    def test_remaining_overall_deadline_bounds_longer_role_timeout(self):
        config=self.live();body=Body([],endless=True);sent=[]
        client=self.sdk_client(body,sent)
        request=preparation.provider_request(self.inventory,'proposer',config)
        started=time.monotonic()
        with self.assertRaises(transport.PreparationStreamError):
            preparation.provider_role(self.inventory,'proposer',config,60,
                prepared_request=request,prepared_client=client,transport_deadline=started+.025)
        self.assertLess(time.monotonic()-started,1)
        self.assertEqual(len(sent),1);self.assertTrue(client.is_closed());self.assertTrue(body.closed)

    def test_usage_only_message_delta_does_not_require_a_premature_stop_reason(self):
        pieces=events(self.canonical())
        pieces.insert(-2,event('message_delta',delta={'stop_reason':None,'stop_sequence':None},
            usage={'output_tokens':18}))
        result,receipt,sent,client,*_=self.invoke(Body(pieces))
        self.assertEqual(result,self.canonical());self.assertEqual(receipt.usage['output_tokens'],20)
        self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def assert_unknown_stream(self, pieces, reason):
        result,receipt,sent,client,*_=self.invoke(Body(pieces))
        self.assertIsInstance(result,transport.PreparationStreamError)
        self.assertEqual(result.local_reason,reason)
        self.assertEqual(receipt.state,'unknown');self.assertIsNone(receipt.computed_cost)
        self.assertFalse(receipt.response_path);self.assertFalse(receipt.usage)
        self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())
        self.assertFalse(self.trace(receipt,'partial')['stream_complete'])

    def test_each_cost_counter_decrease_refuses_without_inventing_final_usage(self):
        good=events(self.canonical())
        for key,earlier,later in (('output_tokens',100,20),('input_tokens',100,10),
                ('cache_read_input_tokens',5,2),('cache_creation_input_tokens',3,1)):
            before={'output_tokens':19,key:earlier}
            final={'output_tokens':20,key:later}
            pieces=good[:-2]+[event('message_delta',delta={'stop_reason':None},usage=before),
                event('message_delta',delta={'stop_reason':'end_turn'},usage=final),good[-1]]
            with self.subTest(key=key):self.assert_unknown_stream(pieces,'contradictory_usage')
        # The independent counterexample also decreases cache counts directly
        # from message_start, without an intermediate message_delta.
        for key in ('cache_read_input_tokens','cache_creation_input_tokens'):
            pieces=good[:-2]+[event('message_delta',delta={'stop_reason':'end_turn'},
                usage={'output_tokens':20,key:0}),good[-1]]
            with self.subTest(start_counter=key):self.assert_unknown_stream(pieces,'contradictory_usage')

    def test_optional_counter_omission_and_null_do_not_reset_cumulative_observations(self):
        good=events(self.canonical())
        for final_optional in ({},{'input_tokens':None,'cache_read_input_tokens':None,
                                'cache_creation_input_tokens':None}):
            before={'input_tokens':100,'output_tokens':18,'cache_read_input_tokens':5,
                    'cache_creation_input_tokens':3}
            pieces=good[:-2]+[event('message_delta',delta={'stop_reason':None},usage=before),
                event('message_delta',delta={'stop_reason':None},usage={'output_tokens':19}),
                event('message_delta',delta={'stop_reason':'end_turn'},
                    usage={'output_tokens':20,**final_optional}),good[-1]]
            result,receipt,sent,client,*_=self.invoke(Body(pieces))
            self.assertEqual(result,self.canonical());self.assertEqual(receipt.state,'succeeded')
            self.assertEqual(receipt.usage,{'input_tokens':100,'output_tokens':20,
                'cached_input_tokens':5,'cache_creation_tokens':3})
            self.assertIsNotNone(receipt.computed_cost);self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_optional_counters_may_start_unobserved_then_increase_and_repeat_exactly(self):
        good=events(self.canonical())
        start=json.loads(good[0].decode().splitlines()[1][6:])
        start['message']['usage'].update(cache_read_input_tokens=None,cache_creation_input_tokens=None)
        pieces=[event('message_start',message=start['message'])]+good[1:-2]+[
            event('message_delta',delta={'stop_reason':None},usage={'output_tokens':18,
                'input_tokens':10,'cache_read_input_tokens':0,'cache_creation_input_tokens':0}),
            event('message_delta',delta={'stop_reason':None},usage={'output_tokens':18,
                'input_tokens':10,'cache_read_input_tokens':2,'cache_creation_input_tokens':1}),
            good[-2],good[-1]]
        result,receipt,sent,client,*_=self.invoke(Body(pieces))
        self.assertEqual(result,self.canonical());self.assertEqual(receipt.usage['cached_input_tokens'],2)
        self.assertEqual(receipt.usage['cache_creation_tokens'],1)
        self.assertIsNotNone(receipt.computed_cost);self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_noninteger_or_negative_supplied_optional_counters_cannot_become_known_cost(self):
        good=events(self.canonical())
        for key in ('input_tokens','cache_read_input_tokens','cache_creation_input_tokens'):
            for bad in (True,-1,1.5,'2',[],{}):
                pieces=good[:-2]+[event('message_delta',delta={'stop_reason':'end_turn'},
                    usage={'output_tokens':20,key:bad}),good[-1]]
                with self.subTest(key=key,bad=bad):
                    self.assert_unknown_stream(pieces,'contradictory_usage')

    def test_conflicting_terminal_and_explicit_retraction_cannot_erase_original_stop(self):
        good=events(self.canonical())
        for first,second in (('max_tokens','end_turn'),('end_turn','max_tokens'),
                             ('max_tokens',None),('end_turn',None)):
            pieces=good[:-2]+[event('message_delta',delta={'stop_reason':first},usage={'output_tokens':19}),
                event('message_delta',delta={'stop_reason':second},usage={'output_tokens':20}),good[-1]]
            with self.subTest(first=first,second=second):
                self.assert_unknown_stream(pieces,'contradictory_terminal')

    def test_terminal_then_omitted_fields_usage_update_keeps_raw_snapshot_separate_and_replays(self):
        for choice in (False,True):
            proposal=self.canonical(choice=choice)
            for role in ('proposer','checker'):
                value=self.canonical(role,proposal,choice=choice)
                good=events(encoded(value,codec.TRANSPORT) if choice else value)
                pieces=good[:-2]+[event('message_delta',delta={'stop_reason':'end_turn'},usage={'output_tokens':19}),
                    event('message_delta',delta={},usage={'output_tokens':20}),good[-1]]
                result,receipt,sent,client,*_=self.invoke(Body(pieces),role=role,proposal=proposal,choice=choice)
                self.assertEqual(result,value);self.assertEqual(receipt.state,'succeeded')
                evidence=json.loads(private_path(receipt.response_path).read_bytes())
                self.assertIsNone(evidence['response']['stop_reason'])  # Exact SDK snapshot; never rewritten.
                self.assertEqual(evidence['stream_observation']['terminal'],{'stop_reason':'end_turn','stop_sequence':None})
                self.assertEqual(evidence['stream_observation']['final_delta_fields'],[])
                self.assertEqual(preparation.read_retained_role(receipt,'live'),result)
                self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_consistent_redundant_terminal_deltas_preserve_cumulative_usage(self):
        good=events(self.canonical())
        for stop in ('end_turn','max_tokens'):
            pieces=good[:-2]+[event('message_delta',delta={'stop_reason':stop},usage={'output_tokens':19}),
                event('message_delta',delta={'stop_reason':stop},usage={'output_tokens':20}),good[-1]]
            result,receipt,sent,client,*_=self.invoke(Body(pieces))
            if stop=='end_turn':self.assertEqual(result,self.canonical())
            else:
                self.assertIsInstance(result,DocumentError);self.assertEqual(result.code,'output_limit')
            self.assertEqual(receipt.usage['output_tokens'],20);self.assertIsNotNone(receipt.computed_cost)
            evidence=json.loads(private_path(receipt.response_path).read_bytes())
            self.assertEqual(evidence['stream_observation']['terminal_declarations'],2)
            self.assertEqual(evidence['response']['stop_reason'],stop)
            self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_raw_duplicate_counter_keys_and_nonfinite_values_are_not_collapsed_by_sdk(self):
        good=events(self.canonical())
        bodies=[
            '{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":100,"output_tokens":20}}',
            '{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":20,"cache_creation_input_tokens":2,"cache\\u005fcreation_input_tokens":0}}']
        bodies += ['{"type":"message_delta","delta":{"stop_reason":"end_turn"},"usage":{"output_tokens":20,"input_tokens":'+value+'}}'
                   for value in ('NaN','Infinity','-Infinity')]
        for raw in bodies:
            pieces=good[:-2]+[('event: message_delta\ndata: '+raw+'\n\n').encode(),good[-1]]
            with self.subTest(raw=raw):self.assert_unknown_stream(pieces,'ambiguous_usage_json')

    def test_retained_observation_must_match_untouched_sdk_snapshot_and_closed_contract(self):
        value=self.canonical()
        result,receipt,*_=self.invoke(Body(events(value)))
        self.assertEqual(result,value)
        evidence=json.loads(private_path(receipt.response_path).read_bytes())
        mutations=[lambda x:x.pop('stream_observation'),
            lambda x:x['stream_observation'].update(contract='wrong'),
            lambda x:x['stream_observation'].update(terminal_declarations=0),
            lambda x:x['stream_observation'].update(final_delta_fields=[]),
            lambda x:x['stream_observation']['cumulative_usage'].update(input_tokens=100),
            lambda x:x['stream_observation']['terminal'].update(stop_reason='max_tokens')]
        for mutate in mutations:
            bad=deepcopy(evidence);mutate(bad)
            with self.assertRaises(DocumentError):
                preparation.decode_role_response(self.inventory,'proposer',self.live(),value,None,bad,receipt.request_sha256)

    def test_every_sdk_dispatched_alias_must_match_inner_type_before_usage_or_stop_adjudication(self):
        good=events(self.canonical())
        aliases=('content_block_delta','content_block_start','content_block_stop','message_start',
            'message_stop','message','completion','agent.message')
        for name in aliases:
            for reason,output in ((None,100),('max_tokens',19)):
                hidden=event(name,type='message_delta',delta={'stop_reason':reason},
                    usage={'output_tokens':output})
                with self.subTest(event=name,reason=reason):
                    self.assert_unknown_stream(good[:-2]+[hidden]+good[-2:],'event_type_mismatch')

    def test_matching_type_is_observed_and_omitted_type_retains_sdk_default_semantics(self):
        good=events(self.canonical())
        hidden=event('message_delta',type='message_delta',delta={},usage={'output_tokens':100})
        self.assert_unknown_stream(good[:-2]+[hidden]+good[-2:],'contradictory_usage')
        pieces=[]
        for raw in good:
            lines=raw.decode().splitlines();name=lines[0][7:]
            value=json.loads(lines[1][6:]);value.pop('type')
            pieces.append(('event: '+name+'\ndata: '+json.dumps(value)+'\n\n').encode())
        result,receipt,sent,client,*_=self.invoke(Body(pieces))
        self.assertEqual(result,self.canonical());self.assertEqual(receipt.state,'succeeded')
        self.assertEqual(receipt.usage['output_tokens'],20)
        self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())

    def test_sdk_ignored_unknown_events_and_ping_remain_ignored_without_decoding_their_payload(self):
        good=events(self.canonical())
        ignored=[b'event: future_provider_event\ndata: not JSON and not clinical evidence\n\n',
            event('future_provider_event',type='message_delta',delta={'stop_reason':'max_tokens'},
                usage={'output_tokens':100}),
            b'event: ping\ndata: not JSON\n\n',
            event('ping',type='message_delta',delta={'stop_reason':'max_tokens'},usage={'output_tokens':100})]
        result,receipt,sent,client,*_=self.invoke(Body(good[:-2]+ignored+good[-2:]))
        self.assertEqual(result,self.canonical());self.assertEqual(receipt.state,'succeeded')
        self.assertEqual(receipt.usage['output_tokens'],20)
        self.assertEqual(len(sent),1);self.assertTrue(client.is_closed())
