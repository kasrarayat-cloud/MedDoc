"""Authenticated metered recovery; private synthetic files and query doubles only."""
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from django.core import signing
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import ai_stages, generation, generation_recovery as recovery
from core import anthropic_request_policy as policy
from core import testing_authority as authority
from core.security import private_path
from core.tests import test_generation_recovery_v2 as old_family


class Rows(list):
    def all(self): return self
    def order_by(self, *args): return self


@override_settings(RELEASE_SHA='f'*40, SYNTHETIC_ONLY=True, SECRET_KEY='TESTONLY-thinking-recovery',
    TESTING_AUTHORITY_MODE=authority.MODE, TESTING_AUTHORITY_ID=authority.AUTHORITY_ID,
    TESTING_AUTHORITY_SHA256=authority.AUTHORITY_SHA256,
    AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-5-5')
class ThinkingBudgetRecoveryTests(SimpleTestCase):
    def setUp(self):
        old_family.GenerationRecoveryV2Tests.setUp(self)
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.files=Path(self.temp.name)
        self.encounter.department=SimpleNamespace(pk=self.encounter.department_id)
        self.config.update(semantic_schema_transport='anthropic-flat-typed-nodes-v3',
            queued_release_sha='e'*40, semantic_encounter_binding={'encounter_id':str(self.encounter.pk)})
        self.request={'protocol':'quillmd-ai-stages-v1','stage':'extractor','attempt':1,
            'max_output_tokens':32000,'timeout_seconds':240,
            'schema_transport':'anthropic-flat-typed-nodes-v3',
            'payload':{'identity':{**self.config['semantic_encounter_binding'],'generation_job_id':str(UUID(int=4))},
                'notes':'TESTONLY source','approved_definitions':{'field':'TESTONLY approved'}}}
        self.config['semantic_source_sha256']=hashlib.sha256(self.request['payload']['notes'].encode()).hexdigest()
        self.config['semantic_definitions_sha256']=recovery._digest(self.request['payload']['approved_definitions'])
        now=datetime(2026,1,1,tzinfo=timezone.utc)
        self.job=SimpleNamespace(pk=UUID(int=4),kind='generation',state='failed',config=deepcopy(self.config),
            encounter_id=self.encounter.pk,encounter=self.encounter,user_id=self.user.pk,revision=0,
            created_at=now-timedelta(seconds=1),finished_at=now+timedelta(seconds=5),
            result_path='',result_sha256='',error='platform_failure: TESTONLY retained validation failure',request_key='TESTONLY-ended')
        self.result={'provider_request_id':'req_TESTONLY','provider_resource_id':'msg_TESTONLY','returned_model':'claude-sonnet-5-5',
            'provider_output':{'id':'msg_TESTONLY','model':'claude-sonnet-5-5','type':'message','role':'assistant',
                'stop_reason':'max_tokens','content':[{'type':'thinking','thinking':'','signature':'TESTONLY'}],
                'usage':{'input_tokens':29922,'output_tokens':32000,'cache_read_input_tokens':0,
                    'cache_creation_input_tokens':0,'output_tokens_details':{'thinking_tokens':32000}}}}
        self.stage=SimpleNamespace(pk=UUID(int=1004),stage='extractor',attempt=1,state='failed',error_code='invalid_response',
            simulated=False,actual_cost=Decimal('0.379844000000'),quote_maximum=Decimal('0.580885000000'),
            started_at=now,finished_at=now+timedelta(seconds=2),config=deepcopy(self.config),provider='anthropic',
            requested_model='claude-sonnet-5-5',returned_model='claude-sonnet-5-5',
            provider_request_id='req_TESTONLY',provider_resource_id='msg_TESTONLY',
            request_path='receipts/'+'a'*48+'.json',result_path='receipts/'+'b'*48+'.json',
            usage={'input_tokens':29922,'output_tokens':32000,'cached_input_tokens':0,'cache_creation_tokens':0},
            rates=generation.cost_rates(generation.rates(self.config),Decimal('0.379844'),Decimal('0')))
        self.job.ai_stage_receipts=Rows([self.stage]);self.write_evidence()
        self.event=SimpleNamespace(pk=UUID(int=2004),created_at=now+timedelta(seconds=1),details={
            'stage':'extractor','attempt':1,'calculated_provider_cost':'0.379844',
            'provider_request_id':'req_TESTONLY','provider_resource_id':'msg_TESTONLY','simulated':False})
        self.received=[self.event]
        self.rebuild_aggregate()

    def write_evidence(self):
        for kind,obj in [('request',self.request),('result',self.result)]:
            path=getattr(self.stage,kind+'_path');raw=json.dumps(obj,sort_keys=True).encode()
            (self.files/Path(path).name).write_bytes(raw)
            setattr(self.stage,kind+'_sha256',hashlib.sha256(raw).hexdigest())

    def rebuild_aggregate(self):
        total,units,rates,provider,_,_=ai_stages.aggregate(self.job)
        data=dict(actual_cost=total,units=units,rates=rates,provider=provider,simulated=False,
            provider_request_id='',provider_resource_id='',created_at=self.stage.finished_at+timedelta(seconds=1))
        self.receipts=[SimpleNamespace(pk=UUID(int=3004),**deepcopy(data))]
        self.usages=[SimpleNamespace(pk=UUID(int=4004),user_id=self.user.pk,
            department_id=self.encounter.department_id,**deepcopy(data))]

    @contextmanager
    def evidence(self):
        with ExitStack()as stack:
            stack.enter_context(patch.object(recovery,'private_path',side_effect=lambda p:self.files/Path(p).name))
            stack.enter_context(patch.object(recovery,'ProviderReceipt',SimpleNamespace(objects=SimpleNamespace(filter=lambda **k:self.receipts))))
            stack.enter_context(patch.object(recovery,'Usage',SimpleNamespace(objects=SimpleNamespace(filter=lambda **k:self.usages))))
            stack.enter_context(patch.object(recovery,'AuditEvent',SimpleNamespace(objects=SimpleNamespace(filter=lambda **k:self.received))))
            yield

    def test_exact_metered_raw_thinking_failure_authenticates_without_mutation(self):
        before=deepcopy((self.job,self.stage,self.receipts,self.usages,self.received))
        with self.evidence():proof=recovery._local_metered_exhaustion(self.job)
        self.assertIsNotNone(proof)
        self.assertEqual(Decimal(proof['metered_cost']),Decimal('.379844'))
        self.assertEqual(Decimal(proof['prior_quote']),Decimal('.580885'))
        self.assertIsNone(proof['old_request_profile'])
        self.assertEqual((self.job,self.stage,self.receipts,self.usages,self.received),before)

    def test_stop_reason_text_mixed_blocks_and_partial_thinking_cannot_authorize(self):
        original=deepcopy(self.result)
        cases=[lambda p:p.update(stop_reason='end_turn'),
            lambda p:p.update(content=[]),
            lambda p:p.update(content=[{'type':'text','text':'{}'}]),
            lambda p:p['content'].append({'type':'text','text':''}),
            lambda p:p['usage']['output_tokens_details'].update(thinking_tokens=31999),
            lambda p:p['usage']['output_tokens_details'].update(thinking_tokens=True),
            lambda p:p['usage'].update(output_tokens=0),
            lambda p:p['usage'].update(input_tokens=0),
            lambda p:p['usage'].update(cache_read_input_tokens=False),
            lambda p:p.update(id='msg_UNRELATED')]
        for mutate in cases:
            with self.subTest(mutation=cases.index(mutate)):
                self.result=deepcopy(original);mutate(self.result['provider_output']);self.write_evidence()
                with self.evidence():self.assertIsNone(recovery._local_metered_exhaustion(self.job))

    def test_missing_or_tampered_durable_request_result_and_identity_refuse(self):
        original=deepcopy(self.request)
        for key,bad in [('attempt',True),('schema_transport','other'),('max_output_tokens',True),
            (policy.ENVELOPE_KEY,policy.PARAMETERS)]:
            with self.subTest(key=key):
                self.request={**deepcopy(original),key:bad};self.write_evidence()
                with self.evidence():self.assertIsNone(recovery._local_metered_exhaustion(self.job))
        self.request=deepcopy(original);self.request['payload']['identity']['encounter_id']=str(UUID(int=999));self.write_evidence()
        with self.evidence():self.assertIsNone(recovery._local_metered_exhaustion(self.job))
        self.request=original;self.write_evidence()
        (self.files/Path(self.stage.result_path).name).write_bytes(b'tampered')
        with self.evidence():self.assertIsNone(recovery._local_metered_exhaustion(self.job))

    def test_usage_receipt_received_audit_and_exact_metered_cost_required(self):
        with self.evidence():
            for attribute in ['receipts','usages','received']:
                saved=getattr(self,attribute)
                for bad in [[],saved+saved]:
                    with self.subTest(attribute=attribute,count=len(bad)):
                        setattr(self,attribute,bad);self.assertIsNone(recovery._local_metered_exhaustion(self.job))
                setattr(self,attribute,saved)
            for bad in [None,Decimal('0'),Decimal('.379845'),Decimal('NaN')]:
                saved=self.stage.actual_cost;self.stage.actual_cost=bad
                with self.subTest(cost=bad):self.assertIsNone(recovery._local_metered_exhaustion(self.job))
                self.stage.actual_cost=saved
            saved=self.usages[0].units;self.usages[0].units={'protocol':'forged'}
            self.assertIsNone(recovery._local_metered_exhaustion(self.job));self.usages[0].units=saved
            self.event.details['simulated']=True;self.assertIsNone(recovery._local_metered_exhaustion(self.job))

    def test_current_source_revision_notes_and_definition_identity_remain_required(self):
        self.encounter.notes=self.request['payload']['notes'];self.encounter.template_version=SimpleNamespace()
        identity={**self.job.config['semantic_encounter_binding'],'generation_job_id':str(self.job.pk)}
        with patch('core.word_contract.require_generation',return_value=self.request['payload']['approved_definitions']),\
             patch('core.source_interpretation_store.identity_for',return_value=identity):
            self.assertTrue(recovery._source_matches(self.job,self.encounter))
            self.encounter.revision=1;self.assertFalse(recovery._source_matches(self.job,self.encounter))
            self.encounter.revision=0;self.encounter.notes+=' changed'
            self.assertFalse(recovery._source_matches(self.job,self.encounter))

    def test_ineligible_failed_unknown_and_already_explicit_profiles_refuse(self):
        with self.evidence():
            for attribute,bad in [('state','reconciliation'),('kind','transcription'),('result_path','receipts/'+'c'*48+'.json')]:
                saved=getattr(self.job,attribute);setattr(self.job,attribute,bad)
                with self.subTest(attribute=attribute):self.assertIsNone(recovery._local_metered_exhaustion(self.job))
                setattr(self.job,attribute,saved)
            self.job.config[policy.CONFIG_KEY]=policy.PROFILE
            self.assertIsNone(recovery._local_metered_exhaustion(self.job))

    def test_same_metered_cause_authenticates_all_supported_historical_carriers(self):
        for marker in [None,recovery.clinical_transport.TRANSPORT,
                       recovery.clinical_transport.EVIDENCE_TRANSPORT,recovery.clinical_transport.CURRENT_TRANSPORT]:
            with self.subTest(marker=marker):
                if marker is None:
                    self.job.config.pop(recovery.TRANSPORT_KEY,None)
                    self.request.pop('schema_transport',None)
                else:
                    self.job.config[recovery.TRANSPORT_KEY]=marker;self.request['schema_transport']=marker
                self.stage.config=deepcopy(self.job.config);self.write_evidence();self.rebuild_aggregate()
                with self.evidence():proof=recovery._local_metered_exhaustion(self.job)
                self.assertIsNotNone(proof)
                self.assertEqual(proof['old_transport'],marker or recovery.ANTHROPIC_SCHEMA_TRANSPORT)

    # Reuse only the existing pure family builder; no inherited test duplication.
    family=old_family.GenerationRecoveryV2Tests.family
    proof=old_family.GenerationRecoveryV2Tests.proof
    successor=old_family.GenerationRecoveryV2Tests.successor

    @contextmanager
    def lineage_scope(self):
        manager=Mock();manager.select_for_update.return_value=manager
        manager.get.side_effect=lambda **kw:next(j for j in self.jobs if str(j.pk)==str(kw['pk']))
        def events(**kw):return self.events.get(kw['target'],[])
        with ExitStack()as stack:
            stack.enter_context(patch.object(recovery,'Job',SimpleNamespace(objects=manager,DoesNotExist=recovery.Job.DoesNotExist)))
            stack.enter_context(patch.object(recovery,'AuditEvent',SimpleNamespace(objects=SimpleNamespace(filter=events))))
            stack.enter_context(patch.object(recovery,'_children',side_effect=lambda j:self.children.get(j.pk,[])))
            stack.enter_context(patch.object(recovery,'_local_rejection',side_effect=self.proof))
            stack.enter_context(patch.object(recovery,'_local_metered_exhaustion',side_effect=lambda j:deepcopy(self.metered_proof)if j.pk==self.metered.pk else None))
            stack.enter_context(patch.object(recovery,'_source_matches',return_value=True))
            stack.enter_context(patch.object(authority,'admit_actor'))
            stack.enter_context(patch.object(authority,'admit_encounter'))
            yield manager

    def metered_family(self):
        # Three authenticated unknown400 ancestors followed by the paid first extractor.
        with self.evidence():proof=recovery._local_metered_exhaustion(self.job)
        tip=self.family(4,contracts=[recovery.CONTRACT,recovery.CONTRACT,recovery.CONTRACT_V2])
        tip.state='failed';tip.config[recovery.TRANSPORT_KEY]='anthropic-flat-typed-nodes-v3'
        value=tip.config[recovery.RECOVERY_KEY];value['new_transport']=tip.config[recovery.TRANSPORT_KEY]
        value['new_configuration_sha256']=recovery._digest({k:tip.config[k]for k in recovery.CONFIG_KEYS if k in tip.config})
        self.events[str(tip.pk)][0].details={'recovery':deepcopy(value)}
        self.metered=tip;self.metered_proof={**proof,'job':str(tip.pk),'old_config_sha256':recovery._digest(tip.config)}
        return tip

    def prospective(self,tip):
        return {**deepcopy(tip.config),policy.CONFIG_KEY:policy.PROFILE,'queued_release_sha':'f'*40}

    def test_new_profile_same_carrier_signed_successor_keeps_all_four_prior_exposures(self):
        tip=self.metered_family();config=self.prospective(tip);before=deepcopy(self.jobs)
        with self.lineage_scope():
            value=recovery._proposal(tip,self.encounter,self.user,config)
            self.assertEqual(value['contract'],recovery.CONTRACT_METERED)
            self.assertEqual(value['prior_calls'],4)
            self.assertEqual(Decimal(value['prior_quote']),Decimal('2.080885'))
            self.assertEqual(value['new_transport'],value['old_transport'])
            self.assertEqual(value['new_request_profile'],policy.PROFILE)
            self.assertEqual(value['family_max_calls'],8);self.assertEqual(value['family_cost_ceiling'],'8.15000000000')
            token=signing.dumps(value,salt=recovery.SALT)
            parent,decoded=recovery.predecessor(token,self.encounter,self.user)
            self.assertIs(parent,tip);self.assertEqual(decoded,value)
            self.assertEqual(recovery.bind(tip,value,self.encounter,self.user,config)[recovery.RECOVERY_KEY],value)
        self.assertEqual(self.jobs,before)
        child=self.successor(tip,value,config)
        with self.lineage_scope():
            self.assertTrue(recovery.linked(tip,child));self.assertEqual(len(recovery.family_ids(child)),5)
            self.assertIs(recovery.latest(self.jobs[0]),child)
            self.assertFalse(recovery.pending_jobs(self.jobs[:-1]))
            rows=[SimpleNamespace(quote_maximum=Decimal('.1'),actual_cost=Decimal('.01'))for _ in range(4)]
            for used in range(4):recovery.enforce_stage_budget(child,rows[:used],Decimal('.1'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,rows,Decimal('.1'))
            recovery.enforce_stage_budget(child,[],Decimal('6.069115'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,[],Decimal('6.069115000001'))

    def test_authenticated_metered_v3_can_bind_current_v4_profile_and_preserve_history(self):
        # metered_family authenticates the actual raw request/result, received
        # audit and exact Usage/ProviderReceipt before constructing query doubles.
        tip=self.metered_family()
        config={**self.prospective(tip),
            recovery.TRANSPORT_KEY:recovery.clinical_transport.LATEST_TRANSPORT}
        self.assertEqual(config[recovery.TRANSPORT_KEY],recovery.clinical_transport.JSON_TRANSPORT)
        self.assertEqual(tip.config[recovery.TRANSPORT_KEY],recovery.clinical_transport.CURRENT_TRANSPORT)
        self.assertNotIn(policy.CONFIG_KEY,tip.config)
        before=deepcopy((self.jobs,self.stage,self.receipts,self.usages,self.received))
        with self.lineage_scope():
            value=recovery._proposal(tip,self.encounter,self.user,config)
            self.assertIsNotNone(value)
            self.assertEqual(value['contract'],recovery.CONTRACT_METERED)
            self.assertEqual(value['old_transport'],recovery.clinical_transport.CURRENT_TRANSPORT)
            self.assertEqual(value['new_transport'],recovery.clinical_transport.JSON_TRANSPORT)
            self.assertIsNone(value['old_request_profile'])
            self.assertEqual(value['new_request_profile'],policy.PROFILE)
            self.assertEqual(value['prior_calls'],4)
            self.assertEqual(Decimal(value['prior_quote']),Decimal('2.080885'))
            self.assertEqual(value['per_batch_max_calls'],5)
            self.assertEqual(value['family_max_calls'],8)
            self.assertEqual(value['family_cost_ceiling'],'8.15000000000')
            parent,decoded=recovery.predecessor(signing.dumps(value,salt=recovery.SALT),
                self.encounter,self.user)
            self.assertIs(parent,tip);self.assertEqual(decoded,value)
            self.assertEqual(recovery.bind(tip,value,self.encounter,self.user,config)[recovery.RECOVERY_KEY],value)
            # This same proposal was denied by the former finite whitelist.
            historical=(recovery.clinical_transport.TRANSPORT,
                recovery.clinical_transport.EVIDENCE_TRANSPORT,recovery.clinical_transport.CURRENT_TRANSPORT)
            with patch.object(recovery,'METERED_SUCCESSOR_TRANSPORTS',historical):
                self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))
        self.assertEqual((self.jobs,self.stage,self.receipts,self.usages,self.received),before)
        child=self.successor(tip,value,config)
        proof={key:value[key]for key in self.metered_proof}
        with self.lineage_scope():
            self.assertTrue(recovery._edge(tip,child,proof))
            self.assertTrue(recovery.linked(tip,child))
            self.assertEqual(len(recovery.family_ids(child)),5)
            with patch.object(recovery,'METERED_SUCCESSOR_TRANSPORTS',historical):
                self.assertFalse(recovery._edge(tip,child,proof))

    def test_current_metered_successor_still_refuses_unsupported_carrier_and_changed_scope(self):
        tip=self.metered_family()
        config={**self.prospective(tip),
            recovery.TRANSPORT_KEY:recovery.clinical_transport.JSON_TRANSPORT}
        unsupported=['anthropic-canonical-json-v5','unrecognized',None,True]
        before=deepcopy(self.jobs)
        with self.lineage_scope():
            value=recovery._proposal(tip,self.encounter,self.user,config)
            self.assertIsNotNone(value)
            for marker in unsupported:
                with self.subTest(unsupported_transport=marker):
                    self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,
                        {**config,recovery.TRANSPORT_KEY:marker}))
            for key,bad in [(policy.CONFIG_KEY,None),(policy.CONFIG_KEY,'other'),
                    ('semantic_source_sha256','0'*64),('semantic_definitions_sha256','0'*64),
                    ('semantic_max_calls',6),('semantic_maximum_cost','8.16'),
                    ('semantic_timeout_seconds',241),('input_rate','2.1')]:
                with self.subTest(changed_scope=key,bad=bad):
                    self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,{**config,key:bad}))
        self.assertEqual(self.jobs,before)
        child=self.successor(tip,value,config)
        proof={key:value[key]for key in self.metered_proof}
        with self.lineage_scope():
            self.assertTrue(recovery._edge(tip,child,proof))
            for marker in unsupported:
                # Recompute the digest and audit so rejection exercises the
                # carrier boundary, rather than an unrelated stale hash.
                forged={**config,recovery.TRANSPORT_KEY:marker}
                edge={**value,'new_transport':marker,
                    'new_configuration_sha256':recovery._digest({k:forged[k]
                        for k in recovery.CONFIG_KEYS if k in forged})}
                child.config={**forged,recovery.RECOVERY_KEY:edge}
                self.events[str(child.pk)][0].details={'recovery':deepcopy(edge)}
                with self.subTest(edge_unsupported_transport=marker):
                    self.assertFalse(recovery._edge(tip,child,proof))

    def test_unchanged_profile_transport_release_actor_source_and_forged_caps_refuse(self):
        tip=self.metered_family();config=self.prospective(tip)
        with self.lineage_scope():
            value=recovery._proposal(tip,self.encounter,self.user,config);self.assertIsNotNone(value)
            bad_configs=[{k:v for k,v in config.items()if k!=policy.CONFIG_KEY},
                {**config,policy.CONFIG_KEY:None},{**config,policy.CONFIG_KEY:'other'},
                {**config,recovery.TRANSPORT_KEY:'different'},
                {**config,'semantic_maximum_cost':'8.16'},{**config,'testing_authority_id':'forged'}]
            for c in bad_configs:
                with self.subTest(config=c):self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,c))
            for key,bad in [('prior_calls',True),('prior_quote','0'),('metered_cost','0'),
                ('new_request_profile','other'),('family_max_calls',9),('per_batch_max_calls',6),
                ('family_cost_ceiling','8.16'),('received_audit',str(UUID(int=999)))]:
                with self.subTest(key=key),self.assertRaises(ValidationError):
                    recovery.bind(tip,{**value,key:bad},self.encounter,self.user,config)
            with override_settings(RELEASE_SHA=tip.config['queued_release_sha']):
                self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))
            other=SimpleNamespace(pk=UUID(int=999))
            self.assertIsNone(recovery._proposal(tip,self.encounter,other,config))
            with patch.object(recovery,'_source_matches',return_value=False):
                self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))

    def test_extra_child_and_missing_ancestor_refuse_without_history_changes(self):
        tip=self.metered_family();config=self.prospective(tip)
        with self.lineage_scope():value=recovery._proposal(tip,self.encounter,self.user,config)
        child=self.successor(tip,value,config)
        self.children[tip.pk].append(SimpleNamespace(pk=UUID(int=9999)))
        before=deepcopy(self.jobs)
        with self.lineage_scope():
            self.assertFalse(recovery.linked(tip,child));self.assertEqual(recovery.family_ids(child),set())
            self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,config))
        self.assertEqual(self.jobs,before)

    def test_historical_unknown_rejection_can_bind_new_transport_and_profile_explicitly(self):
        tip=self.family(3);self.metered=SimpleNamespace(pk=UUID(int=99999));self.metered_proof=None
        config={**self.prospective(tip),recovery.TRANSPORT_KEY:'anthropic-flat-typed-nodes-v3'}
        before=deepcopy(self.jobs)
        with self.lineage_scope():
            value=recovery._proposal(tip,self.encounter,self.user,config)
            self.assertEqual(value['contract'],recovery.CONTRACT_PROFILE)
            self.assertEqual(value['new_request_profile'],policy.PROFILE)
            self.assertEqual(value['prior_calls'],3);self.assertNotEqual(value['new_transport'],value['old_transport'])
            self.assertNotIn(policy.CONFIG_KEY,tip.config)
            self.assertEqual(recovery.bind(tip,value,self.encounter,self.user,config)[recovery.RECOVERY_KEY],value)
            self.assertIsNone(recovery._proposal(tip,self.encounter,self.user,self.prospective(tip)))
        self.assertEqual(self.jobs,before)
        child=self.successor(tip,value,config)
        with self.lineage_scope():self.assertTrue(recovery.linked(tip,child))


# A true ORM/Client lifecycle uses the existing synthetic worker source fixture.
# Every provider attempt below is an explicit mock; no row or revision is edited.
from django.test import TestCase
from core.tests.test_billing_policy import STORAGES
from core.tests.test_generation_recovery import RecoveryFixture
from core.tests import test_source_assertion_worker as worker_fixture
from core.models import Job, AuditEvent, Usage, TestingReservation, User, Department
from core.jobs import enqueue, run_one
import os
import httpx
from anthropic import BadRequestError


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', ADMIN_SITE=False,
    SYNTHETIC_ONLY=True, AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-5-5', STORAGES=STORAGES,
    TESTING_AUTHORITY_MODE=authority.MODE, TESTING_AUTHORITY_ID=authority.AUTHORITY_ID,
    TESTING_AUTHORITY_SHA256=authority.AUTHORITY_SHA256, RELEASE_SHA='f'*40)
class ThinkingBudgetRecoveryRouteTests(TestCase):
    config=RecoveryFixture.config

    def setUp(self):
        preparation_settings=override_settings(TESTING_AUTHORITY_MODE='',TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='')
        preparation_settings.enable();self.addCleanup(preparation_settings.disable)
        # Reuse the unchanged source fixture with the real standing actor scope;
        # both Python admission and the installed PostgreSQL trigger remain real.
        create_user=User.objects.create_user;create_department=Department.objects.create
        with patch.object(User.objects,'create_user',side_effect=lambda *a,**k:create_user(*a,
                id=UUID('2247e403-a830-4807-9a34-6903b95a0f50'),**k)),\
             patch.object(Department.objects,'create',side_effect=lambda **k:create_department(
                id=UUID('46a5abdd-36f1-41f0-968f-8c09c39d9daa'),**k)):
            worker_fixture.SourceAssertionWorkerTests.setUp(self)
        active_settings=override_settings(TESTING_AUTHORITY_MODE=authority.MODE,
            TESTING_AUTHORITY_ID=authority.AUTHORITY_ID,TESTING_AUTHORITY_SHA256=authority.AUTHORITY_SHA256)
        active_settings.enable();self.addCleanup(active_settings.disable)
        self.original_pipeline=ai_stages.pipeline_config
        self.previous=[]
        for index,marker in enumerate([None,'anthropic-nullable-singleton-arrays-v1','anthropic-evidence-reference-table-v2']):
            job=self.historical_queue(marker,format(index+1,'040x'))
            response=httpx.Response(400,request=httpx.Request('POST','https://synthetic.invalid/messages'),
                headers={'request-id':'req_TESTONLYRejected'+job.pk.hex},
                json={'error':{'type':'invalid_request_error','message':'TESTONLY grammar rejection'}})
            error=BadRequestError('TESTONLY retained rejection',response=response,body=response.json())
            with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'TESTONLY-NOT-A-CREDENTIAL'}),patch.object(ai_stages,'_response',side_effect=error)as send:
                self.assertTrue(run_one());self.assertEqual(send.call_count,1)
            job.refresh_from_db();self.assertEqual(job.state,'reconciliation');self.previous.append(job)
        self.failed=self.historical_queue('anthropic-flat-typed-nodes-v3','e'*40)
        def thinking(payload,schema,instructions,config,maximum,timeout,on_response):
            ident='TESTONLYThinking'+self.failed.pk.hex
            raw={'id':'msg_'+ident,'model':config['model'],'type':'message','role':'assistant',
                'content':[{'type':'thinking','thinking':'','signature':'TESTONLY'}],
                'stop_reason':'max_tokens','usage':{'input_tokens':29922,'output_tokens':32000,
                'cache_read_input_tokens':0,'cache_creation_input_tokens':0,
                'output_tokens_details':{'thinking_tokens':32000}}}
            value=SimpleNamespace(id=raw['id'],model=config['model'],_request_id='req_'+ident,model_dump=lambda **kw:raw)
            on_response(value);cost=Decimal('.379844')
            units={'input_tokens':29922,'output_tokens':32000,'cached_input_tokens':0,'cache_creation_tokens':0}
            return value,cost,units,generation.cost_rates(generation.rates(config),cost,Decimal('0')),'',False
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'TESTONLY-NOT-A-CREDENTIAL'}),patch.object(ai_stages,'_response',side_effect=thinking)as send:
            self.assertTrue(run_one());self.assertEqual(send.call_count,1)
        self.failed.refresh_from_db();self.assertEqual(self.failed.state,'failed',self.failed.error)
        self.assertIsNotNone(recovery._local_metered_exhaustion(self.failed))
        self.previous.append(self.failed)

    def historical_queue(self,marker,release):
        def pipeline(config):
            value=self.original_pipeline(config);value.pop(policy.CONFIG_KEY,None)
            if marker is None:value.pop(recovery.TRANSPORT_KEY,None)
            else:value[recovery.TRANSPORT_KEY]=marker
            return value
        with override_settings(RELEASE_SHA=release),patch.object(ai_stages,'pipeline_config',side_effect=pipeline):
            config=pipeline(self.config())
            token=recovery.offer(self.encounter,self.user,config)if self.previous else None
            if self.previous:self.assertIsNotNone(token)
            return enqueue(self.encounter,self.user,config=self.config(),recovery_token=token)

    def preserved(self):
        ids=[job.pk for job in self.previous]
        return {'jobs':list(Job.objects.filter(pk__in=ids).order_by('pk').values()),
            'stages':[list(job.ai_stage_receipts.order_by('pk').values())for job in self.previous],
            'usage':list(Usage.objects.filter(job_id__in=ids).order_by('pk').values()),
            'holds':list(TestingReservation.objects.filter(job_id__in=ids).order_by('pk').values()),
            'files':{stage.request_path:private_path(stage.request_path).read_bytes()
                for job in self.previous for stage in job.ai_stage_receipts.all()}}

    def test_real_get_post_double_click_and_three_stage_success_preserve_four_old_attempts(self):
        # This retained test exercises the historical same-v3/new-profile
        # contract. A newer prospective carrier must not relabel that fixture.
        pipeline=ai_stages.pipeline_config
        with patch.object(ai_stages,'pipeline_config',side_effect=lambda config:{
                **pipeline(config),recovery.TRANSPORT_KEY:recovery.clinical_transport.CURRENT_TRANSPORT}):
            self._assert_real_v3_get_post_double_click_and_three_stage_success()

    def _assert_real_v3_get_post_double_click_and_three_stage_success(self):
        from core.security import private_path
        from core import clinical_node_transport as codec, source_assertion_graph as graph
        from core.tests.test_source_assertion_graph import checker
        before=self.preserved();original_revision=self.encounter.revision
        config=self.config()
        with patch('core.generation.configuration',return_value=config):
            page=self.client.get(f'/encounters/{self.encounter.pk}/')
            self.assertEqual(page.status_code,200)
            token=page.context['generation_recovery_offer'];self.assertIsNotNone(token)
            binding=page.context['generation_recovery_binding']
            self.assertEqual(binding['max_calls'],5);self.assertEqual(binding['family_max_calls'],8)
            decoded=signing.loads(token,salt=recovery.SALT)
            self.assertEqual(decoded['contract'],recovery.CONTRACT_METERED);self.assertEqual(decoded['prior_calls'],4)
            post={'revision':str(original_revision),'recovery_token':token,'usage_quote':page.context['usage_quote']}
            url=f'/encounters/{self.encounter.pk}/generation/retry-rejected/'
            first=self.client.post(url,post,HTTP_ACCEPT='application/json')
            second=self.client.post(url,post,HTTP_ACCEPT='application/json')
        self.assertEqual(first.status_code,200,first.content);self.assertFalse(first.json()['reused'])
        self.assertEqual(second.status_code,200,second.content);self.assertTrue(second.json()['reused'])
        self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),5)
        job=Job.objects.filter(encounter=self.encounter,state='queued').get()
        self.assertEqual(job.config[policy.CONFIG_KEY],policy.PROFILE)
        self.assertEqual(job.config[recovery.TRANSPORT_KEY],self.failed.config[recovery.TRANSPORT_KEY])
        self.assertEqual(self.preserved(),before)
        # Ordinary generation is still a lookup, even with a newly selected profile.
        reused=enqueue(self.encounter,self.user,config=self.config());self.assertEqual(reused.pk,job.pk);self.assertTrue(reused.reused)
        calls=[];assigned=None
        def complete(payload,schema,instructions,config,maximum,timeout,on_response):
            nonlocal assigned
            role=('extractor','assigner','checker')[len(calls)];calls.append(role)
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
            text=json.dumps(codec.encode(schema,canonical));ident='TESTONLYComplete'+job.pk.hex+role
            raw={'id':'msg_'+ident,'model':config['model'],'type':'message','role':'assistant','stop_reason':'end_turn',
                'content':[{'type':'text','text':text}],'usage':{'input_tokens':10,'output_tokens':0}}
            value=SimpleNamespace(id=raw['id'],model=config['model'],_request_id='req_'+ident,model_dump=lambda **kw:raw)
            on_response(value);cost=Decimal('.00002')
            return value,cost,{'input_tokens':10,'output_tokens':0,'cached_input_tokens':0,'cache_creation_tokens':0},generation.cost_rates(generation.rates(config),cost,Decimal('0')),text,True
        with patch.dict(os.environ,{'ANTHROPIC_API_KEY':'TESTONLY-NOT-A-CREDENTIAL'}),patch.object(ai_stages,'_response',side_effect=complete)as send,patch('core.coding_hooks.after_saved_document'):
            self.assertTrue(run_one());self.assertEqual(send.call_count,3)
        job.refresh_from_db();self.encounter.refresh_from_db()
        self.assertEqual(job.state,'succeeded',job.error);self.assertEqual(calls,['extractor','assigner','checker'])
        self.assertEqual(self.encounter.revision,original_revision);self.assertEqual(self.preserved(),before)
        self.assertTrue(all(j.state=='reconciliation'for j in self.previous[:3]))
        self.assertTrue(all(j.ai_stage_receipts.get().actual_cost is None for j in self.previous[:3]))
        self.assertEqual(self.failed.ai_stage_receipts.get().actual_cost,Decimal('.379844'))
        self.assertEqual(job.ai_stage_receipts.count(),3)
