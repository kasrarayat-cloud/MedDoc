"""Paid text truncation recovery, using private synthetic receipts and query doubles.

Raw evidence authentication is exercised separately from the existing immutable
family fixtures. No partial clinical text is decoded, adopted or sent again.
"""
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from django.core import signing
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import ai_stages, generation, source_assertion_graph as graph
from core import generation_recovery as recovery
from core import anthropic_request_policy as policy, testing_authority as authority
from core.tests import test_thinking_budget_recovery as thinking
from core.tests import test_invalid_carrier_recovery as carrier


@override_settings(RELEASE_SHA='f'*40, SYNTHETIC_ONLY=True, SECRET_KEY='TESTONLY-truncation',
    TESTING_AUTHORITY_MODE=authority.MODE, TESTING_AUTHORITY_ID=authority.AUTHORITY_ID,
    TESTING_AUTHORITY_SHA256=authority.AUTHORITY_SHA256,
    AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-5-5')
class TruncatedJsonRecoveryTests(SimpleTestCase):
    write_evidence=thinking.ThinkingBudgetRecoveryTests.write_evidence
    rebuild_aggregate=thinking.ThinkingBudgetRecoveryTests.rebuild_aggregate
    family=thinking.ThinkingBudgetRecoveryTests.family
    proof=thinking.ThinkingBudgetRecoveryTests.proof
    successor=carrier.InvalidCarrierRecoveryTests.successor

    def setUp(self):
        thinking.ThinkingBudgetRecoveryTests.setUp(self)
        self.job.config.update({policy.CONFIG_KEY:policy.PROFILE,
            recovery.TRANSPORT_KEY:recovery.clinical_transport.JSON_TRANSPORT,
            'testing_quote_usd':'1.594557500000'})
        self.job.payer='standing:'+authority.AUTHORITY_ID
        self.stage.config=deepcopy(self.job.config)
        self.request.update({policy.ENVELOPE_KEY:deepcopy(policy.PARAMETERS),
            'schema_transport':recovery.clinical_transport.JSON_TRANSPORT,
            'schema':graph.extraction_schema()})
        self.request['transmitted_schema']=json.dumps(recovery.clinical_transport.transmitted_schema(
            self.request['schema'],recovery.clinical_transport.JSON_TRANSPORT))
        self.result['provider_output'].update(stop_reason='max_tokens',stop_details=None,
            content=[{'type':'text','text':'{"transport":"anthropic-canonical-json-v4","document_json":"{'}])
        self.result['provider_output']['usage'].update(input_tokens=26089,
            output_tokens_details={'thinking_tokens':0})
        self.stage.usage['input_tokens']=26089
        self.stage.actual_cost=Decimal('.372178000000')
        self.stage.quote_maximum=Decimal('.512470000000')
        self.stage.rates=generation.cost_rates(generation.rates(self.config),Decimal('.372178'),Decimal('0'))
        self.event.details['calculated_provider_cost']='0.372178'
        self.write_evidence();self.rebuild_aggregate()
        self.usages[0].payer=self.job.payer;self.usages[0].charged_cost=Decimal('0')
        self.holds=[SimpleNamespace(pk=UUID(int=5004),state='settled',authority_id=authority.AUTHORITY_ID,
            quoted_provider_cost=Decimal('1.594557500000'))]
        self.settlements=[SimpleNamespace(pk=UUID(int=6004),created_at=self.usages[0].created_at,details={
            'authority_id':authority.AUTHORITY_ID,'calculated_provider_cost':'0.372178000000',
            'confirmed_provider_charge':None,'user_charge':'0','simulated':False})]
        self.wallet_holds=False

    @contextmanager
    def evidence(self):
        with thinking.ThinkingBudgetRecoveryTests.evidence(self),\
             patch.object(recovery,'AuditEvent',SimpleNamespace(objects=SimpleNamespace(filter=lambda **k:
                 self.received if k['action']=='ai.stage_received' else self.settlements))),\
             patch.object(recovery,'TestingReservation',SimpleNamespace(objects=SimpleNamespace(filter=lambda **k:self.holds))),\
             patch.object(recovery,'Reservation',SimpleNamespace(objects=SimpleNamespace(filter=lambda **k:
                 SimpleNamespace(exists=lambda:self.wallet_holds)))):
            yield

    def authenticate(self):
        with self.evidence():return recovery._local_truncated_json(self.job)

    def snapshot(self):
        return deepcopy((self.job,self.stage,self.receipts,self.usages,self.received,self.holds,self.settlements)),\
            {p.name:p.read_bytes()for p in self.files.iterdir()}

    def test_exact_metered_text_truncation_authenticates_without_decoding_or_mutating(self):
        before=self.snapshot()
        with patch.object(recovery.clinical_transport,'response_value',side_effect=AssertionError('no salvage')):
            proof=self.authenticate()
        self.assertIsNotNone(proof)
        self.assertEqual(proof['truncated_transport'],recovery.clinical_transport.JSON_TRANSPORT)
        self.assertEqual(proof['metered_cost'],'0.372178000000')
        self.assertEqual(Decimal(proof['prior_quote']),Decimal('.512470'))
        self.assertEqual(proof['settled_reservation'],str(self.holds[0].pk))
        self.assertEqual(proof['settlement_audit'],str(self.settlements[0].pk))
        self.assertNotIn('invalid_carrier',proof);self.assertNotIn('old_request_profile',proof)
        self.assertEqual(self.snapshot(),before)

    def test_max_tokens_even_parseable_text_never_certifies_complete_output(self):
        self.result['provider_output']['content']=[{'type':'text','text':'{"transport":"anthropic-canonical-json-v4","document_json":"{}"}'}]
        self.write_evidence();self.rebuild_aggregate()
        self.usages[0].payer=self.job.payer;self.usages[0].charged_cost=Decimal('0')
        with patch.object(recovery.clinical_transport,'response_value',side_effect=AssertionError('no salvage')):
            self.assertIsNotNone(self.authenticate())

    def test_end_turn_refusal_thinking_mixed_empty_or_incomplete_usage_refuses(self):
        original=deepcopy(self.result)
        cases=[('stop_reason','end_turn'),('stop_reason','refusal'),
            ('stop_details',{'type':'refusal'}),('content',[]),
            ('content',[{'type':'text','text':' '}]),('content',[{'type':'text','text':False}]),
            ('content',[{'type':'thinking','thinking':''}]),
            ('content',[{'type':'text','text':'{'},{'type':'thinking','thinking':''}])]
        for key,bad in cases:
            with self.subTest(key=key,bad=bad):
                self.result=deepcopy(original);self.result['provider_output'][key]=bad
                self.write_evidence();self.assertIsNone(self.authenticate())
        for key,bad in [('input_tokens',0),('output_tokens',31999),('output_tokens',True),
                ('output_tokens_details',{}),('output_tokens_details',{'thinking_tokens':1}),
                ('output_tokens_details',{'thinking_tokens':False})]:
            with self.subTest(usage=key,bad=bad):
                self.result=deepcopy(original);self.result['provider_output']['usage'][key]=bad
                self.write_evidence();self.assertIsNone(self.authenticate())

    def test_exact_request_schema_profile_source_receipts_rates_and_hashes_required(self):
        original=deepcopy(self.request)
        for key,bad in [('schema',{}),('transmitted_schema','{}'),('transmitted_schema',None),
                ('schema_transport',recovery.clinical_transport.CURRENT_TRANSPORT),
                (policy.ENVELOPE_KEY,{}),('max_output_tokens',True),('timeout_seconds',241)]:
            with self.subTest(request=key):
                self.request=deepcopy(original);self.request[key]=bad;self.write_evidence()
                self.assertIsNone(self.authenticate())
        for key,bad in [('notes','different source'),('approved_definitions',{}),('identity',{})]:
            with self.subTest(payload=key):
                self.request=deepcopy(original);self.request['payload'][key]=bad;self.write_evidence()
                self.assertIsNone(self.authenticate())
        self.request=original;self.write_evidence()
        for attribute in ('receipts','usages','received'):
            saved=getattr(self,attribute)
            for bad in ([],saved*2):
                with self.subTest(population=attribute),self.evidence():
                    setattr(self,attribute,bad);self.assertIsNone(recovery._local_truncated_json(self.job))
            setattr(self,attribute,saved)
        for attribute,bad in [('actual_cost',Decimal('0')),('actual_cost',Decimal('.1')),
                ('rates',{}),('usage',{}),('result_sha256','0'*64),('request_sha256','0'*64)]:
            saved=getattr(self.stage,attribute)
            with self.subTest(stage=attribute):
                setattr(self.stage,attribute,bad);self.assertIsNone(self.authenticate())
            setattr(self.stage,attribute,saved)

    def test_settled_authority_reservation_and_settlement_audit_required(self):
        original=deepcopy((self.holds,self.settlements,self.usages,self.job.payer))
        mutations=[lambda:self.holds.clear(),lambda:self.holds.append(deepcopy(self.holds[0])),
            lambda:setattr(self.holds[0],'state','held'),lambda:setattr(self.holds[0],'state','released'),
            lambda:setattr(self.holds[0],'authority_id','other'),
            lambda:setattr(self.holds[0],'quoted_provider_cost',Decimal('0')),
            lambda:self.settlements.clear(),lambda:self.settlements.append(deepcopy(self.settlements[0])),
            lambda:self.settlements[0].details.update(calculated_provider_cost='0'),
            lambda:self.settlements[0].details.update(confirmed_provider_charge='0.372178'),
            lambda:setattr(self.usages[0],'payer','other'),lambda:setattr(self.usages[0],'charged_cost',Decimal('1')),
            lambda:setattr(self.job,'payer','other')]
        for index,mutate in enumerate(mutations):
            self.holds,self.settlements,self.usages,self.job.payer=deepcopy(original)
            with self.subTest(mutation=index):mutate();self.assertIsNone(self.authenticate())
        self.holds,self.settlements,self.usages,self.job.payer=deepcopy(original)
        self.wallet_holds=True;self.assertIsNone(self.authenticate())

    def test_first_stage_failed_unadopted_live_and_exact_profile_required(self):
        for target,key,bad in [(self.job,'state','succeeded'),(self.job,'result_path','some-result'),
                (self.stage,'attempt',2),(self.stage,'stage','assigner'),(self.stage,'simulated',True),
                (self.stage,'error_code','clinical_hold'),(self.stage,'returned_model','other')]:
            saved=getattr(target,key)
            with self.subTest(key=key):setattr(target,key,bad);self.assertIsNone(self.authenticate())
            setattr(target,key,saved)
        for key,bad in [(policy.CONFIG_KEY,None),(policy.CONFIG_KEY,'other'),
                (recovery.TRANSPORT_KEY,recovery.clinical_transport.DIRECT_TRANSPORT),('mode','fixture')]:
            saved=self.job.config[key]
            with self.subTest(config=key):self.job.config[key]=bad;self.assertIsNone(self.authenticate())
            self.job.config[key]=saved

    @contextmanager
    def lineage_scope(self):
        with thinking.ThinkingBudgetRecoveryTests.lineage_scope(self)as manager,\
             patch.object(recovery,'_local_invalid_carrier',side_effect=lambda j:
                 deepcopy(self.carrier_proof)if j.pk==self.carrier.pk else None),\
             patch.object(recovery,'_local_truncated_json',side_effect=lambda j:
                 deepcopy(self.truncated_proof)if j.pk==self.truncated.pk else None):
            yield manager

    def initialize_lineage(self):
        proof=self.authenticate();self.assertIsNotNone(proof)
        self.jobs=[self.job];self.children={};self.events={}
        self.metered=SimpleNamespace(pk=UUID(int=90001));self.metered_proof=None
        self.carrier=SimpleNamespace(pk=UUID(int=90002));self.carrier_proof=None
        self.truncated=self.job;self.truncated_proof=proof
        return self.job

    def prospective(self,tip):
        return {**deepcopy(tip.config),recovery.TRANSPORT_KEY:recovery.clinical_transport.DIRECT_TRANSPORT,
            'queued_release_sha':'f'*40}

    def test_signed_changed_v5_successor_preserves_original_paid_failure_and_finite_bounds(self):
        tip=self.initialize_lineage();config=self.prospective(tip);before=self.snapshot()
        with self.lineage_scope():
            value=recovery._proposal(tip,self.encounter,self.user,config)
            self.assertEqual(value['contract'],recovery.CONTRACT_TRUNCATED)
            self.assertEqual(value['prior_calls'],1)
            self.assertEqual(value['family_max_calls'],8);self.assertEqual(value['per_batch_max_calls'],5)
            self.assertEqual(value['family_cost_ceiling'],'8.15000000000')
            parent,decoded=recovery.predecessor(signing.dumps(value,salt=recovery.SALT),self.encounter,self.user)
            self.assertIs(parent,tip);self.assertEqual(decoded,value)
            self.assertEqual(recovery.bind(tip,value,self.encounter,self.user,config)[recovery.RECOVERY_KEY],value)
        self.assertEqual(self.snapshot(),before)
        child=self.successor(tip,value,config)
        with self.lineage_scope():
            self.assertTrue(recovery.linked(tip,child));self.assertIs(recovery.latest(tip),child)
            rows=[SimpleNamespace(quote_maximum=Decimal('.1'),actual_cost=Decimal('.01'))for _ in range(5)]
            for used in range(5):recovery.enforce_stage_budget(child,rows[:used],Decimal('.1'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,rows,Decimal('.1'))
            recovery.enforce_stage_budget(child,[],Decimal('7.63753'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,[],Decimal('7.637530000001'))

    def test_unchanged_transport_or_profile_source_actor_forged_caps_and_fork_refuse(self):
        tip=self.initialize_lineage();config=self.prospective(tip)
        with self.lineage_scope():
            value=recovery._proposal(tip,self.encounter,self.user,config)
            for key,bad in [(recovery.TRANSPORT_KEY,recovery.clinical_transport.JSON_TRANSPORT),
                    (recovery.TRANSPORT_KEY,recovery.clinical_transport.CURRENT_TRANSPORT),
                    (policy.CONFIG_KEY,None),('semantic_source_sha256','0'*64),
                    ('semantic_definitions_sha256','0'*64),('semantic_max_calls',6),
                    ('semantic_maximum_cost','8.16'),('semantic_timeout_seconds',241),
                    ('semantic_output_token_limit',64000),('input_rate','2.1')]:
                with self.subTest(config=key,bad=bad):
                    self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,{**config,key:bad}))
            for key,bad in [('family_max_calls',9),('per_batch_max_calls',6),('family_cost_ceiling','8.16'),
                    ('prior_calls',True),('prior_quote','0'),('contract',recovery.CONTRACT_CARRIER),
                    ('settled_reservation',str(UUID(int=999))),('settlement_audit',str(UUID(int=998)))]:
                with self.subTest(proof=key),self.assertRaises(ValidationError):
                    recovery.bind(tip,{**value,key:bad},self.encounter,self.user,config)
            self.assertIsNone(recovery._proposal(tip,self.encounter,SimpleNamespace(pk=UUID(int=999)),config))
            with patch.object(recovery,'_source_matches',return_value=False):
                self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))
            with override_settings(RELEASE_SHA=tip.config['queued_release_sha']):
                self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))
        child=self.successor(tip,value,config)
        with self.lineage_scope():
            self.assertTrue(recovery.linked(tip,child))
            self.children[tip.pk].append(SimpleNamespace(pk=UUID(int=999)))
            self.assertFalse(recovery.linked(tip,child))

    def test_historical_invalid_v3_can_prospectively_bind_latest_v5_without_relabeling_v4(self):
        fixture=carrier.InvalidCarrierRecoveryTests(methodName='runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        tip=fixture.carrier_family();config={**fixture.prospective(tip),
            recovery.TRANSPORT_KEY:recovery.clinical_transport.LATEST_TRANSPORT}
        with fixture.lineage_scope():
            value=recovery._proposal(tip,fixture.encounter,fixture.user,config)
            self.assertIsNotNone(value);self.assertEqual(value['contract'],recovery.CONTRACT_CARRIER)
            self.assertEqual(value['new_transport'],recovery.clinical_transport.DIRECT_TRANSPORT)
            self.assertEqual(value['prior_calls'],5)
        child=fixture.successor(tip,value,config)
        with fixture.lineage_scope():self.assertTrue(recovery.linked(tip,child))

    def test_six_paid_or_unknown_calls_refuse_minimum_three_roles_under_unchanged_eight(self):
        raw_proof=self.authenticate();self.assertIsNotNone(raw_proof)
        fixture=carrier.InvalidCarrierRecoveryTests(methodName='runTest');fixture.setUp();self.addCleanup(fixture.doCleanups)
        tip=fixture.carrier_family();config=fixture.prospective(tip)
        with fixture.lineage_scope():value=recovery._proposal(tip,fixture.encounter,fixture.user,config)
        tip=fixture.successor(tip,value,config);tip.state='failed';tip.finished_at=tip.created_at
        for name in ('jobs','children','events','metered','metered_proof','carrier','carrier_proof'):
            setattr(self,name,getattr(fixture,name))
        self.truncated=tip;self.truncated_proof={**raw_proof,'job':str(tip.pk),
            'old_config_sha256':recovery._digest(tip.config)}
        before=deepcopy(self.jobs)
        with self.lineage_scope()as manager:
            proof=recovery.rejection(tip);self.assertEqual(proof['prior_calls'],6)
            self.assertEqual(len(recovery.family_ids(tip)),6)
            self.assertEqual(Decimal(proof['prior_quote']),Decimal('3.174497500000'))
            self.assertEqual(recovery.V2_FAMILY_MAX_CALLS-proof['prior_calls'],2)
            self.assertEqual(recovery.MIN_SUCCESSOR_CALLS,3)
            self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,self.prospective(tip)))
            manager.create.assert_not_called()
        self.assertEqual(self.jobs,before)

    def test_opaque_latest_failure_never_reveals_an_older_recoverable_tip(self):
        tip=self.initialize_lineage();unknown=SimpleNamespace(pk=UUID(int=800),state='failed')
        rows=Mock();rows.order_by.return_value=[tip,unknown]
        manager=SimpleNamespace(filter=lambda **kw:rows)
        with patch.object(recovery,'Job',SimpleNamespace(objects=manager,DoesNotExist=recovery.Job.DoesNotExist)),\
             patch.object(recovery,'_local_failure',side_effect=lambda j:self.truncated_proof if j is tip else None),\
             patch.object(recovery,'_proposal',side_effect=AssertionError('must not choose older failure')):
            self.assertIsNone(recovery.offer(self.encounter,self.user,self.prospective(tip)))
