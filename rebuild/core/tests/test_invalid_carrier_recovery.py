"""Paid structural-carrier recovery: private TESTONLY files and query doubles.

Canonical-but-clinically-unsafe graphs are deliberately not eligible. No live
provider, database connection, historical row update or automatic POST is used.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, override_settings

from core import ai_stages, clinical_node_transport, generation
from core import generation_recovery as recovery, source_assertion_graph as graph
from core import anthropic_request_policy as policy, testing_authority as authority
from core.tests import test_thinking_budget_recovery as historical


@override_settings(RELEASE_SHA='f'*40, SYNTHETIC_ONLY=True, SECRET_KEY='TESTONLY-carrier-recovery',
    TESTING_AUTHORITY_MODE=authority.MODE, TESTING_AUTHORITY_ID=authority.AUTHORITY_ID,
    TESTING_AUTHORITY_SHA256=authority.AUTHORITY_SHA256,
    AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-5-5')
class InvalidCarrierRecoveryTests(SimpleTestCase):
    write_evidence=historical.ThinkingBudgetRecoveryTests.write_evidence
    rebuild_aggregate=historical.ThinkingBudgetRecoveryTests.rebuild_aggregate
    evidence=historical.ThinkingBudgetRecoveryTests.evidence
    family=historical.ThinkingBudgetRecoveryTests.family
    proof=historical.ThinkingBudgetRecoveryTests.proof
    metered_family=historical.ThinkingBudgetRecoveryTests.metered_family

    def setUp(self):
        historical.ThinkingBudgetRecoveryTests.setUp(self)
        self.job.config[policy.CONFIG_KEY]=policy.PROFILE
        self.stage.config=deepcopy(self.job.config)
        self.request[policy.ENVELOPE_KEY]=deepcopy(policy.PARAMETERS)
        self.request['schema']=graph.extraction_schema()
        self.request['transmitted_schema']=json.dumps(recovery.clinical_transport.transmitted_schema(
            self.request['schema'],recovery.clinical_transport.CURRENT_TRANSPORT))
        self.result['provider_output'].update(stop_reason='end_turn',content=[{'type':'text','text':json.dumps({
            'transport':recovery.clinical_transport.CURRENT_TRANSPORT,
            'nodes':{'parent':[0],'key':[''],'kind':[0]},
            **{k:{'parent':[],'key':[],'value':[]}for k in ('strings','integers','numbers','booleans')}})}])
        self.result['provider_output']['usage'].update(output_tokens=199,output_tokens_details={'thinking_tokens':0})
        self.stage.actual_cost=Decimal('.061834')
        self.stage.quote_maximum=Decimal('.5811425')
        self.stage.usage['output_tokens']=199
        self.stage.rates=generation.cost_rates(generation.rates(self.config),Decimal('.061834'),Decimal('0'))
        self.event.details['calculated_provider_cost']='0.061834'
        self.write_evidence();self.rebuild_aggregate()

    def authenticate(self):
        with self.evidence():return recovery._local_invalid_carrier(self.job)

    def test_complete_paid_invalid_v3_carrier_is_authenticated_without_mutation(self):
        before=deepcopy((self.job,self.stage,self.receipts,self.usages,self.received))
        proof=self.authenticate()
        self.assertIsNotNone(proof)
        self.assertEqual(proof['invalid_carrier'],recovery.clinical_transport.CURRENT_TRANSPORT)
        self.assertNotIn('old_request_profile',proof)
        self.assertEqual(Decimal(proof['metered_cost']),Decimal('.061834'))
        self.assertEqual(Decimal(proof['prior_quote']),Decimal('.5811425'))
        self.assertEqual((self.job,self.stage,self.receipts,self.usages,self.received),before)

    def test_complete_canonical_even_empty_or_clinically_unsupported_graph_is_not_carrier_failure(self):
        canonical={'contract':graph.CONTRACT,'facts':[],'assertions':[],
            'relationships':[],'unit_coverage':[],'time_accounts':[]}
        self.result['provider_output']['content'][0]['text']=json.dumps(
            clinical_node_transport.encode(self.request['schema'],canonical))
        self.write_evidence()
        self.assertIsNone(self.authenticate())

    def test_partial_refusal_empty_mixed_and_nontext_output_cannot_authorize(self):
        original=deepcopy(self.result)
        mutations=[lambda o:o.update(stop_reason='max_tokens'),lambda o:o.update(stop_reason='refusal'),
            lambda o:o.update(content=[]),lambda o:o.update(content=[{'type':'text','text':'  '}]),
            lambda o:o.update(content=[{'type':'text','text':None}]),
            lambda o:o['content'].append({'type':'thinking','thinking':'TESTONLY'}),
            lambda o:o['usage']['output_tokens_details'].update(thinking_tokens=1),
            lambda o:o['usage'].update(output_tokens=32001),
            lambda o:o['usage'].update(output_tokens=True)]
        for i,mutate in enumerate(mutations):
            with self.subTest(case=i):
                self.result=deepcopy(original);mutate(self.result['provider_output']);self.write_evidence()
                self.assertIsNone(self.authenticate())

    def test_raw_request_profile_schema_transmitted_schema_and_source_must_match(self):
        original=deepcopy(self.request)
        mutations=[lambda r:r.pop(policy.ENVELOPE_KEY),
            lambda r:r[policy.ENVELOPE_KEY]['output_config'].update(effort='low'),
            lambda r:r.update(schema={'type':'object','properties':{},'required':[]}),
            lambda r:r.update(transmitted_schema='{}'),
            lambda r:r.update(schema_transport=recovery.clinical_transport.EVIDENCE_TRANSPORT),
            lambda r:r['payload'].update(notes='TESTONLY changed source'),
            lambda r:r['payload']['identity'].update(generation_job_id=str(UUID(int=999))),
            lambda r:r['payload'].update(approved_definitions={}),
            lambda r:r.update(attempt=True)]
        for i,mutate in enumerate(mutations):
            with self.subTest(case=i):
                self.request=deepcopy(original);mutate(self.request);self.write_evidence()
                self.assertIsNone(self.authenticate())

    def test_raw_hash_provider_ids_usage_cost_and_immutable_received_audit_are_required(self):
        saved=self.stage.result_sha256;self.stage.result_sha256='0'*64
        self.assertIsNone(self.authenticate());self.stage.result_sha256=saved
        for attribute in ['receipts','usages','received']:
            original=getattr(self,attribute)
            for bad in [[],original+original]:
                with self.subTest(attribute=attribute,count=len(bad)):
                    setattr(self,attribute,bad);self.assertIsNone(self.authenticate())
            setattr(self,attribute,original)
        for attribute,bad in [('actual_cost',Decimal('.061835')),('actual_cost',None),
            ('provider_request_id','req_OTHER'),('returned_model','other'),('attempt',True)]:
            original=getattr(self.stage,attribute);setattr(self.stage,attribute,bad)
            with self.subTest(attribute=attribute):self.assertIsNone(self.authenticate())
            setattr(self.stage,attribute,original)
        self.event.details['calculated_provider_cost']='0'
        self.assertIsNone(self.authenticate())

    def test_profile_carrier_stage_and_unadopted_first_extractor_are_closed(self):
        for attribute,bad in [('state','unknown'),('stage','assigner'),('error_code','processing_failure'),
            ('simulated',True)]:
            original=getattr(self.stage,attribute);setattr(self.stage,attribute,bad)
            with self.subTest(attribute=attribute):self.assertIsNone(self.authenticate())
            setattr(self.stage,attribute,original)
        self.job.ai_stage_receipts.append(deepcopy(self.stage))
        self.assertIsNone(self.authenticate());self.job.ai_stage_receipts.pop()
        self.job.result_path='receipts/'+'c'*48+'.json'
        self.assertIsNone(self.authenticate());self.job.result_path=''
        self.job.config.pop(policy.CONFIG_KEY);self.stage.config=deepcopy(self.job.config)
        self.assertIsNone(self.authenticate())

    @contextmanager
    def lineage_scope(self):
        with historical.ThinkingBudgetRecoveryTests.lineage_scope(self)as manager,\
             patch.object(recovery,'_local_invalid_carrier',side_effect=lambda j:
                deepcopy(self.carrier_proof)if j.pk==self.carrier.pk else None):
            yield manager

    def successor(self,tip,value,config):
        # Use unique immutable TESTONLY identities for the two paid ancestors.
        child=SimpleNamespace(pk=UUID(int=max(j.pk.int for j in self.jobs)+1),kind='generation',
            config={**deepcopy(config),recovery.RECOVERY_KEY:deepcopy(value)},
            encounter_id=self.encounter.pk,encounter=self.encounter,user_id=self.user.pk,
            revision=0,created_at=tip.finished_at+timedelta(seconds=1),finished_at=None,
            state='queued',request_key=recovery.request_key(tip))
        self.children[tip.pk]=[child];self.jobs.append(child)
        self.events[str(child.pk)]=[SimpleNamespace(created_at=child.created_at,details={'recovery':deepcopy(value)})]
        return child

    def carrier_family(self):
        carrier_proof=self.authenticate();self.assertIsNotNone(carrier_proof)
        # Build the previous four-node family using the independently tested
        # historical proof interface; financial/lineage tests are not raw proofs.
        self.job.config.pop(policy.CONFIG_KEY)
        self.stage.config=deepcopy(self.job.config)
        with patch.object(recovery,'_local_metered_exhaustion',return_value={
            **carrier_proof,'old_request_profile':None,'metered_cost':'.379844','prior_quote':'.580885'}):
            metered=self.metered_family()
        self.metered_proof.pop('invalid_carrier',None)
        self.carrier=SimpleNamespace(pk=UUID(int=99999));self.carrier_proof=None
        config={**deepcopy(metered.config),policy.CONFIG_KEY:policy.PROFILE,'queued_release_sha':'d'*40}
        with self.lineage_scope(),override_settings(RELEASE_SHA='d'*40):
            value=recovery._proposal(metered,self.encounter,self.user,config)
            self.assertIsNotNone(value)
        carrier=self.successor(metered,value,config);carrier.state='failed'
        carrier.finished_at=carrier.created_at
        self.carrier=carrier
        self.carrier_proof={**carrier_proof,'job':str(carrier.pk),
            'old_config_sha256':recovery._digest(carrier.config)}
        return carrier

    def prospective(self,tip):
        return {**deepcopy(tip.config),recovery.TRANSPORT_KEY:recovery.clinical_transport.JSON_TRANSPORT,
            'queued_release_sha':'f'*40}

    def test_five_prior_calls_leave_exactly_three_and_all_exposures_remain(self):
        tip=self.carrier_family();config=self.prospective(tip);before=deepcopy(self.jobs)
        with self.lineage_scope():
            value=recovery._proposal(tip,self.encounter,self.user,config)
            self.assertEqual(value['contract'],recovery.CONTRACT_CARRIER)
            self.assertEqual(value['prior_calls'],5)
            self.assertEqual(Decimal(value['prior_quote']),Decimal('2.6620275'))
            self.assertEqual(value['family_max_calls'],8);self.assertEqual(value['per_batch_max_calls'],5)
            self.assertNotIn('new_request_profile',value)
            parent,decoded=recovery.predecessor(signing.dumps(value,salt=recovery.SALT),self.encounter,self.user)
            self.assertIs(parent,tip);self.assertEqual(decoded,value)
            self.assertEqual(recovery.bind(tip,value,self.encounter,self.user,config)[recovery.RECOVERY_KEY],value)
        self.assertEqual(self.jobs,before)
        child=self.successor(tip,value,config)
        with self.lineage_scope():
            self.assertTrue(recovery.linked(tip,child));self.assertEqual(len(recovery.family_ids(child)),6)
            self.assertIs(recovery.latest(self.jobs[0]),child)
            rows=[SimpleNamespace(quote_maximum=Decimal('.1'),actual_cost=Decimal('.01'))for _ in range(3)]
            for used in range(3):recovery.enforce_stage_budget(child,rows[:used],Decimal('.1'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,rows,Decimal('.1'))
            recovery.enforce_stage_budget(child,[],Decimal('5.4879725'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,[],Decimal('5.487972500001'))

    def test_unchanged_carrier_release_profile_source_and_forged_signed_proof_refuse(self):
        tip=self.carrier_family();config=self.prospective(tip)
        with self.lineage_scope():
            value=recovery._proposal(tip,self.encounter,self.user,config);self.assertIsNotNone(value)
            for key,bad in [(recovery.TRANSPORT_KEY,tip.config[recovery.TRANSPORT_KEY]),
                (recovery.TRANSPORT_KEY,'other'),(policy.CONFIG_KEY,'other'),
                ('semantic_max_calls',6),('semantic_maximum_cost','8.16'),('testing_authority_id','forged')]:
                with self.subTest(key=key):self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,{**config,key:bad}))
            with override_settings(RELEASE_SHA=tip.config['queued_release_sha']):
                self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))
            for key,bad in [('prior_calls',4),('prior_quote','0'),('metered_cost','0'),
                ('invalid_carrier','other'),('family_max_calls',9),('per_batch_max_calls',6),
                ('family_cost_ceiling','8.16'),('received_audit',str(UUID(int=999))),('new_request_profile',policy.PROFILE)]:
                with self.subTest(key=key),self.assertRaises(ValidationError):
                    recovery.bind(tip,{**value,key:bad},self.encounter,self.user,config)
            self.encounter.revision=1
            with patch.object(recovery,'_source_matches',return_value=False):
                self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))
            self.encounter.revision=0
            self.assertIsNone(recovery._proposal(tip,self.encounter,SimpleNamespace(pk=UUID(int=999)),config))
            with patch.object(authority,'admit_actor',side_effect=PermissionDenied):
                self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))

    def test_one_child_dedupe_fork_and_insufficient_remaining_calls_refuse(self):
        tip=self.carrier_family();config=self.prospective(tip)
        with self.lineage_scope():value=recovery._proposal(tip,self.encounter,self.user,config)
        child=self.successor(tip,value,config)
        before=deepcopy(self.jobs)
        with self.lineage_scope():
            self.assertIs(recovery.successor(tip),child)
            self.assertIs(recovery.latest(tip),child)
            self.children[tip.pk].append(SimpleNamespace(pk=UUID(int=9999)))
            self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))
        self.assertEqual(self.jobs,before)
        self.children[tip.pk].pop()
        with self.lineage_scope(),patch.object(recovery,'rejection',return_value={**self.carrier_proof,'prior_calls':6}):
            self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))

    def test_read_only_offer_includes_each_paid_ancestor_and_never_ignores_busy_work(self):
        tip=self.carrier_family();config=self.prospective(tip);before=deepcopy(self.jobs)
        extra=SimpleNamespace(pk=UUID(int=999),state='queued')
        active=[]
        def filtered(**kwargs):
            rows=([j for j in self.jobs if j.state in kwargs['state__in']]+active
                  if 'state__in'in kwargs else [j for j in reversed(self.jobs)if j.state=='failed'])
            return SimpleNamespace(order_by=lambda *args:rows)
        with self.lineage_scope()as manager:
            manager.filter.side_effect=filtered
            token=recovery.offer(self.encounter,self.user,config);self.assertIsNotNone(token)
            value=signing.loads(token,salt=recovery.SALT)
            self.assertEqual(value['job'],str(tip.pk));self.assertEqual(value['prior_calls'],5)
            active.append(extra)
            self.assertIsNone(recovery.offer(self.encounter,self.user,config))
            active.clear()
            # A newer unrelated/opaque paid failure must remain visible. It
            # cannot be filtered away to reveal the older recoverable tip.
            opaque=SimpleNamespace(pk=UUID(int=1001),state='failed')
            self.jobs.append(opaque)
            self.assertIsNone(recovery.offer(self.encounter,self.user,config))
            self.jobs.pop()
        self.assertEqual(self.jobs,before)


# The lead runs this class only on an isolated fixture PostgreSQL database.
# The original source fixture, standing-actor admission and real enqueue/locks
# remain intact. Every provider response is an explicit TESTONLY mock.
from django.test import TestCase
from core.models import Job, AuditEvent, Usage, ProviderReceipt
from core.jobs import enqueue, run_one
from core.security import private_path
import os


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', ADMIN_SITE=False,
    SYNTHETIC_ONLY=True, AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-5-5',
    STORAGES=historical.STORAGES, TESTING_AUTHORITY_MODE=authority.MODE,
    TESTING_AUTHORITY_ID=authority.AUTHORITY_ID, TESTING_AUTHORITY_SHA256=authority.AUTHORITY_SHA256,
    RELEASE_SHA='f'*40)
class InvalidCarrierRecoveryRouteTests(TestCase):
    config=historical.ThinkingBudgetRecoveryRouteTests.config
    historical_queue=historical.ThinkingBudgetRecoveryRouteTests.historical_queue

    def preserved(self):
        value=historical.ThinkingBudgetRecoveryRouteTests.preserved(self)
        ids=[j.pk for j in self.previous]
        value['provider_receipts']=list(ProviderReceipt.objects.filter(job_id__in=ids).order_by('pk').values())
        value['result_files']={s.result_path:private_path(s.result_path).read_bytes()
            for j in self.previous for s in j.ai_stage_receipts.all()if s.result_path}
        targets=[str(j.pk)for j in self.previous]+[str(s.pk)for j in self.previous for s in j.ai_stage_receipts.all()]
        value['audits']=list(AuditEvent.objects.filter(target__in=targets).order_by('pk').values())
        return value

    def setUp(self):
        historical.ThinkingBudgetRecoveryRouteTests.setUp(self)
        original=ai_stages.pipeline_config
        # Create the real fifth failed request through the historical M3 v3
        # profile route before presenting a new-release/v4 offer.
        with override_settings(RELEASE_SHA='d'*40),patch.object(ai_stages,'pipeline_config',
                side_effect=lambda config:{**original(config),recovery.TRANSPORT_KEY:recovery.clinical_transport.CURRENT_TRANSPORT}),\
             patch('core.generation.configuration',return_value=self.config()):
            page=self.client.get(f'/encounters/{self.encounter.pk}/')
            self.assertIsNotNone(page.context['generation_recovery_offer'])
            result=self.client.post(f'/encounters/{self.encounter.pk}/generation/retry-rejected/',{
                'revision':str(self.encounter.revision),'usage_quote':page.context['usage_quote'],
                'recovery_token':page.context['generation_recovery_offer']},HTTP_ACCEPT='application/json')
            self.assertEqual(result.status_code,200,result.content)
        failed=Job.objects.get(encounter=self.encounter,state='queued')
        def malformed(payload,schema,instructions,config,maximum,timeout,on_response):
            text=json.dumps({'transport':recovery.clinical_transport.CURRENT_TRANSPORT,
                'nodes':{'parent':[0],'key':[''],'kind':[0]},
                **{k:{'parent':[],'key':[],'value':[]}for k in ('strings','integers','numbers','booleans')}})
            ident='TESTONLYInvalid'+failed.pk.hex
            raw={'id':'msg_'+ident,'model':config['model'],'type':'message','role':'assistant',
                'content':[{'type':'text','text':text}],'stop_reason':'end_turn',
                'usage':{'input_tokens':29922,'output_tokens':199,'cache_read_input_tokens':0,
                    'cache_creation_input_tokens':0,'output_tokens_details':{'thinking_tokens':0}}}
            response=SimpleNamespace(id=raw['id'],model=config['model'],_request_id='req_'+ident,
                model_dump=lambda **kw:raw)
            on_response(response);cost=Decimal('.061834')
            return response,cost,{'input_tokens':29922,'output_tokens':199,'cached_input_tokens':0,
                'cache_creation_tokens':0},generation.cost_rates(generation.rates(config),cost,Decimal('0')),text,True
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'TESTONLY-NOT-A-CREDENTIAL'}),\
             patch.object(ai_stages,'_response',side_effect=malformed)as send:
            self.assertTrue(run_one());self.assertEqual(send.call_count,1)
        failed.refresh_from_db();self.assertEqual(failed.state,'failed',failed.error)
        self.assertIsNotNone(recovery._local_invalid_carrier(failed))
        self.previous.append(failed);self.failed=failed

    def test_real_five_ancestor_get_post_dedupe_and_latest_v5_three_stage_adoption(self):
        from core import clinical_json_text_transport as codec
        from core.tests.test_source_assertion_graph import checker
        before=self.preserved();revision=self.encounter.revision
        with patch('core.generation.configuration',return_value=self.config()):
            page=self.client.get(f'/encounters/{self.encounter.pk}/')
            token=page.context['generation_recovery_offer'];self.assertIsNotNone(token)
            value=signing.loads(token,salt=recovery.SALT)
            self.assertEqual(value['contract'],recovery.CONTRACT_CARRIER)
            self.assertEqual(value['prior_calls'],5);self.assertEqual(value['family_max_calls'],8)
            self.assertEqual(value['invalid_carrier'],recovery.clinical_transport.CURRENT_TRANSPORT)
            self.assertEqual(value['new_transport'],recovery.clinical_transport.LATEST_TRANSPORT)
            self.assertEqual(value['new_transport'],recovery.clinical_transport.DIRECT_TRANSPORT)
            post={'revision':str(revision),'recovery_token':token,'usage_quote':page.context['usage_quote']}
            url=f'/encounters/{self.encounter.pk}/generation/retry-rejected/'
            first=self.client.post(url,post,HTTP_ACCEPT='application/json')
            second=self.client.post(url,post,HTTP_ACCEPT='application/json')
        self.assertEqual(first.status_code,200,first.content);self.assertFalse(first.json()['reused'])
        self.assertEqual(second.status_code,200,second.content);self.assertTrue(second.json()['reused'])
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),6)
        child=Job.objects.get(encounter=self.encounter,state='queued')
        self.assertEqual(child.config[policy.CONFIG_KEY],self.failed.config[policy.CONFIG_KEY])
        self.assertEqual(self.preserved(),before)
        reused=enqueue(self.encounter,self.user,config=self.config());self.assertEqual(reused.pk,child.pk)
        self.assertTrue(reused.reused)
        roles=[];assigned=None
        def complete(payload,schema,instructions,config,maximum,timeout,on_response):
            nonlocal assigned
            role=('extractor','assigner','checker')[len(roles)];roles.append(role)
            if role=='extractor':
                canonical={'contract':graph.CONTRACT,'facts':[],'assertions':[],'relationships':[],'time_accounts':[],
                    'unit_coverage':[{'source_unit_id':u['id'],'disposition':'nonclinical','assertion_ids':[],
                        'affected_assertion_ids':[]}for u in payload['source_units']]}
            elif role=='assigner':
                canonical={'fields':[{'key':f['key'],'separator':'; ','components':[{'id':c['id'],'disposition':'missing',
                    'fact_ids':[],'predicate_assertion_ids':[],'relationship_ids':[]}for c in
                    payload['approved_definitions'][f['key']]['component_contract']['components']]}for f in payload['fields']]}
                assigned=canonical
            else:canonical=checker(payload['graph'],payload['fields'],payload['approved_definitions'],assigned)
            text=json.dumps(codec.encode(schema,canonical));ident='TESTONLYV4'+child.pk.hex+role
            raw={'id':'msg_'+ident,'model':config['model'],'type':'message','role':'assistant','stop_reason':'end_turn',
                'content':[{'type':'text','text':text}],'usage':{'input_tokens':10,'output_tokens':0}}
            response=SimpleNamespace(id=raw['id'],model=config['model'],_request_id='req_'+ident,model_dump=lambda **kw:raw)
            on_response(response);cost=Decimal('.00002')
            return response,cost,{'input_tokens':10,'output_tokens':0,'cached_input_tokens':0,
                'cache_creation_tokens':0},generation.cost_rates(generation.rates(config),cost,Decimal('0')),text,True
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'TESTONLY-NOT-A-CREDENTIAL'}),\
             patch.object(ai_stages,'_response',side_effect=complete)as send,patch('core.coding_hooks.after_saved_document'):
            self.assertTrue(run_one());self.assertEqual(send.call_count,3)
        child.refresh_from_db();self.encounter.refresh_from_db()
        self.assertEqual(child.state,'succeeded',child.error)
        self.assertEqual(roles,['extractor','assigner','checker']);self.assertEqual(child.ai_stage_receipts.count(),3)
        self.assertEqual(self.encounter.revision,revision);self.assertEqual(self.preserved(),before)
        self.assertEqual(sum(j.ai_stage_receipts.count()for j in self.previous)+child.ai_stage_receipts.count(),8)
