"""Finite prospective recovery batches; all retained rows and queries are doubles.

The existing retained-400 validator is not mocked as a claim of provider
acceptance: these tests isolate the new protocol, signed joins and accounting.
SimpleTestCase prohibits database access; no provider is called.
"""
from contextlib import contextmanager, ExitStack
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, override_settings

from core import ai_stages, clinical_schema_transport, generation_recovery as recovery
from core import testing_authority as authority


@override_settings(RELEASE_SHA='f'*40, SYNTHETIC_ONLY=True,
    TESTING_AUTHORITY_MODE=authority.MODE, TESTING_AUTHORITY_ID=authority.AUTHORITY_ID,
    TESTING_AUTHORITY_SHA256=authority.AUTHORITY_SHA256,
    AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-5-5', SECRET_KEY='TESTONLY-recovery-v2')
class GenerationRecoveryV2Tests(SimpleTestCase):
    def setUp(self):
        self.user=SimpleNamespace(pk=UUID(int=100),is_active=True)
        self.encounter=SimpleNamespace(pk=UUID(int=200),department_id=UUID(int=300),
            revision=0,status='draft',answers={})
        self.config={'provider':'anthropic','model':'claude-sonnet-5-5','mode':'live',
            'input_rate':'2','cached_rate':'0.2','output_rate':'10','discount_rate':'0',
            'semantic_contract':'semantic-facts-v1','semantic_stage_protocol':'quillmd-ai-stages-v1',
            'semantic_max_calls':5,'semantic_request_byte_limit':512000,
            'semantic_capacity_profile':'bounded-output-32k-v2',
            'semantic_timeout_seconds':240,'semantic_output_token_limit':32000,
            'semantic_maximum_cost':'8.15000000000',
            'semantic_source_sha256':'a'*64,'semantic_definitions_sha256':'b'*64,
            'testing_authority_mode':authority.MODE,'testing_authority_id':authority.AUTHORITY_ID,
            'testing_authority_sha256':authority.AUTHORITY_SHA256,
            'testing_purpose':authority.PURPOSES['generation']}
        self.jobs=[];self.children={};self.events={}

    def proof(self,job):
        return {'job':str(job.pk),'stage':str(UUID(int=job.pk.int+1000)),
            'request_sha256':'1'*64,'error_audit':str(UUID(int=job.pk.int+2000)),
            'error_sha256':'2'*64,'old_transport':job.config[recovery.TRANSPORT_KEY],
            'prior_calls':1,'prior_quote':'0.500000000000',
            'old_config_sha256':recovery._digest(job.config)}

    def family(self,count,*,contracts=None,standing=True):
        """Build immutable TESTONLY rejected nodes, not actual provider evidence."""
        self.jobs=[];self.children={};self.events={}
        base=deepcopy(self.config)
        if not standing:
            for key in authority.KEYS:base.pop(key)
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        for i in range(count):
            config={**deepcopy(base),recovery.TRANSPORT_KEY:'TESTONLY-transport-'+str(i),
                'queued_release_sha':format(i+1,'040x')}
            job=SimpleNamespace(pk=UUID(int=i+1),kind='generation',config=config,
                encounter_id=self.encounter.pk,encounter=self.encounter,user_id=self.user.pk,
                revision=0,created_at=start+timedelta(seconds=2*i),
                finished_at=start+timedelta(seconds=2*i+1),state='reconciliation')
            if i:
                parent=self.jobs[-1]
                contract=(contracts[i-1]if contracts is not None else recovery.CONTRACT)
                proof={**self.proof(parent),'prior_calls':i,
                    'prior_quote':str(Decimal('0.500000000000')*i)}
                bounds=recovery._v2_bounds(config)if contract==recovery.CONTRACT_V2 else {}
                value={'contract':contract,**bounds,**proof,'encounter':str(self.encounter.pk),
                    'actor':str(self.user.pk),'revision':0,'new_transport':config[recovery.TRANSPORT_KEY],
                    'accepted_release':config['queued_release_sha'],
                    'new_configuration_sha256':recovery._digest({k:config[k]for k in recovery.CONFIG_KEYS if k in config})}
                config[recovery.RECOVERY_KEY]=value
                job.request_key=recovery.request_key(parent)
                self.children[parent.pk]=[job]
                self.events[str(job.pk)]=[SimpleNamespace(created_at=job.created_at,
                    details={'recovery':deepcopy(value)})]
            else:job.request_key='TESTONLY-original'
            self.jobs.append(job)
        return self.jobs[-1]

    @contextmanager
    def scope(self):
        manager=Mock()
        by_id={j.pk:j for j in self.jobs}
        manager.get.side_effect=lambda **kw:by_id[UUID(kw['pk'])if isinstance(kw['pk'],str)else kw['pk']]
        manager.select_for_update.return_value=manager
        manager.filter.return_value.order_by.return_value=list(reversed(self.jobs))
        events=SimpleNamespace(objects=SimpleNamespace(filter=lambda **kw:self.events.get(kw['target'],[])))
        job_model=SimpleNamespace(objects=manager,DoesNotExist=recovery.Job.DoesNotExist)
        with ExitStack()as stack:
            stack.enter_context(patch.object(recovery,'Job',job_model))
            stack.enter_context(patch.object(recovery,'AuditEvent',events))
            stack.enter_context(patch.object(recovery,'_children',side_effect=lambda job:self.children.get(job.pk,[])))
            stack.enter_context(patch.object(recovery,'_local_rejection',side_effect=self.proof))
            stack.enter_context(patch.object(recovery,'_source_matches',return_value=True))
            actor=stack.enter_context(patch.object(authority,'admit_actor'))
            encounter=stack.enter_context(patch.object(authority,'admit_encounter'))
            yield manager,actor,encounter

    def prospective(self,tip):
        return {**deepcopy(tip.config),recovery.TRANSPORT_KEY:clinical_schema_transport.CURRENT_TRANSPORT,
            'queued_release_sha':'f'*40}

    def proposal(self,tip,config=None):
        return recovery._proposal(tip,self.encounter,self.user,config or self.prospective(tip))

    def successor(self,tip,value,config):
        child=SimpleNamespace(pk=UUID(int=10000),kind='generation',config={**deepcopy(config),recovery.RECOVERY_KEY:deepcopy(value)},
            encounter_id=self.encounter.pk,encounter=self.encounter,user_id=self.user.pk,
            revision=0,created_at=tip.finished_at+timedelta(seconds=1),finished_at=None,
            state='queued',request_key=recovery.request_key(tip))
        self.children[tip.pk]=[child];self.jobs.append(child)
        self.events[str(child.pk)]=[SimpleNamespace(created_at=child.created_at,details={'recovery':deepcopy(value)})]
        return child

    def test_three_rejections_offer_exact_server_selected_v2_without_new_cost_or_authority(self):
        tip=self.family(3);before=deepcopy(self.jobs)
        with self.scope()as(manager,actor,encounter):
            value=self.proposal(tip)
            self.assertEqual(value['contract'],recovery.CONTRACT_V2)
            self.assertEqual(value['prior_calls'],3)
            self.assertEqual(Decimal(value['prior_quote']),Decimal('1.5'))
            self.assertEqual(value['per_batch_max_calls'],5);self.assertEqual(value['family_max_calls'],8)
            self.assertEqual(value['family_cost_ceiling'],'8.15000000000')
            for key in authority.KEYS:self.assertEqual(value[key],tip.config[key])
            actor.assert_any_call(self.user,self.encounter.department_id,self.prospective(tip))
            encounter.assert_called_once_with(self.user,self.encounter)
            manager.create.assert_not_called()
        self.assertEqual(self.jobs,before)

    def test_actual_page_quote_can_omit_server_authority_enrollment_and_source_metadata(self):
        self.user.pk=UUID('5f4d1a3d-eeb6-4207-b1df-4597dc696e82')
        self.config[authority.ACTOR_ENROLLMENT_KEY]=authority.ACTOR_ENROLLMENTS[str(self.user.pk)]
        tip=self.family(3);config=self.prospective(tip)
        omitted={*authority.KEYS,authority.ACTOR_ENROLLMENT_KEY,'semantic_source_sha256',
            'semantic_definitions_sha256','queued_release_sha',recovery.RECOVERY_KEY}
        quote={k:v for k,v in config.items()if k not in omitted}
        with self.scope():
            full=self.proposal(tip,config);priced=self.proposal(tip,quote)
            self.assertEqual(priced,full)
            self.assertEqual(priced['contract'],recovery.CONTRACT_V2)
            bound=recovery.bind(tip,priced,self.encounter,self.user,config)
            self.assertEqual(bound[authority.ACTOR_ENROLLMENT_KEY],self.config[authority.ACTOR_ENROLLMENT_KEY])
        self.assertNotIn('testing_authority_id',quote)

    def test_signed_offer_and_bind_authenticate_all_v2_fields_without_mutating_history(self):
        tip=self.family(3);config=self.prospective(tip)
        with self.scope():
            value=self.proposal(tip);token=signing.dumps(value,salt=recovery.SALT)
            parent,decoded=recovery.predecessor(token,self.encounter,self.user)
            self.assertIs(parent,tip);self.assertEqual(decoded,value)
            self.assertEqual(recovery.bind(tip,value,self.encounter,self.user,config)[recovery.RECOVERY_KEY],value)
            changes={'per_batch_max_calls':6,'family_max_calls':9,'family_cost_ceiling':'8.16',
                'testing_authority_id':'forged','testing_authority_sha256':'0'*64,
                'testing_purpose':authority.PURPOSES['preparation'],'testing_authority_mode':'other',
                'prior_calls':2,'prior_quote':'0','old_config_sha256':'0'*64,'extra':True,
                'contract':recovery.CONTRACT}
            for key,bad in changes.items():
                with self.subTest(key=key),self.assertRaises(ValidationError):
                    recovery.bind(tip,{**value,key:bad},self.encounter,self.user,config)
            with self.assertRaises(ValidationError):recovery.predecessor(token+'tampered',self.encounter,self.user)

    def test_three_old_calls_and_five_new_calls_fit_eight_but_ninth_and_sixth_job_call_refuse(self):
        tip=self.family(3)
        with self.scope():value=self.proposal(tip)
        child=self.successor(tip,value,self.prospective(tip))
        rows=[SimpleNamespace(quote_maximum=Decimal('0.10'),actual_cost=Decimal('0.01'))for _ in range(5)]
        before=deepcopy(self.jobs)
        with self.scope():
            self.assertEqual(ai_stages.maximum_cost(child.config),Decimal('8.15'))
            for used in range(5):recovery.enforce_stage_budget(child,rows[:used],Decimal('0.10'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,rows,Decimal('0.01'))
        self.assertEqual(self.jobs,before)
        self.assertTrue(all(j.state=='reconciliation'for j in self.jobs[:-1]))

    def test_cumulative_unknown_quotes_and_larger_known_cost_are_never_zeroed(self):
        tip=self.family(3)
        with self.scope():value=self.proposal(tip)
        child=self.successor(tip,value,self.prospective(tip))
        with self.scope():
            recovery.enforce_stage_budget(child,[],Decimal('6.65'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,[],Decimal('6.650000000001'))
            rows=[SimpleNamespace(quote_maximum=Decimal('0.1'),actual_cost=Decimal('6.6'))]
            recovery.enforce_stage_budget(child,rows,Decimal('0.05'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,rows,Decimal('0.050000000001'))
            for bad in [True,1,1.0,'1',Decimal('-1'),Decimal('NaN'),Decimal('Infinity')]:
                with self.subTest(cost=bad),self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,[],bad)

    def test_v1_two_rejections_still_allow_only_three_stages_under_old_five(self):
        child=self.family(3);child.config[recovery.TRANSPORT_KEY]=clinical_schema_transport.CURRENT_TRANSPORT
        value=child.config[recovery.RECOVERY_KEY];value['new_transport']=child.config[recovery.TRANSPORT_KEY]
        value['new_configuration_sha256']=recovery._digest({k:child.config[k]for k in recovery.CONFIG_KEYS if k in child.config})
        self.events[str(child.pk)][0].details={'recovery':deepcopy(value)}
        rows=[SimpleNamespace(quote_maximum=Decimal('0.1'),actual_cost=None)for _ in range(3)]
        with self.scope():
            for used in range(3):recovery.enforce_stage_budget(child,rows[:used],Decimal('0.1'))
            with self.assertRaises(ai_stages.StageNotSent):recovery.enforce_stage_budget(child,rows,Decimal('0.1'))

    def test_v1_sixth_tip_and_invalid_v1_prefix_cannot_use_longer_v2_traversal(self):
        tip=self.family(5)
        with self.scope():self.assertEqual(len(recovery._lineage(tip)[0]),5)
        tip=self.family(6)
        with self.scope(),self.assertRaises(ValueError):recovery._lineage(tip)
        tip=self.family(7,contracts=[recovery.CONTRACT]*5+[recovery.CONTRACT_V2])
        with self.scope(),self.assertRaises(ValueError):recovery._lineage(tip)

    def test_v2_five_rejected_calls_leave_minimum_three_but_six_leave_two_and_no_offer(self):
        tip=self.family(5)
        with self.scope():self.assertEqual(self.proposal(tip)['prior_calls'],5)
        tip=self.family(6,contracts=[recovery.CONTRACT]*4+[recovery.CONTRACT_V2])
        before=deepcopy(self.jobs)
        with self.scope()as(manager,_,__):
            self.assertEqual(len(recovery._lineage(tip)[0]),6)
            self.assertIsNone(self.proposal(tip));self.assertIsNone(recovery.offer(self.encounter,self.user,self.prospective(tip)))
            manager.create.assert_not_called()
        self.assertEqual(self.jobs,before)

    def test_unqualified_request_keeps_v1_and_cannot_extend_three_rejections(self):
        tip=self.family(2,standing=False)
        with self.scope():self.assertEqual(self.proposal(tip)['contract'],recovery.CONTRACT)
        tip=self.family(3,standing=False)
        with self.scope():self.assertIsNone(self.proposal(tip))

    def test_partial_wrong_purpose_inactive_or_unadmitted_authority_has_no_v2_offer(self):
        tip=self.family(3);config=self.prospective(tip)
        cases=[{**config,'testing_authority_id':'wrong'},
            {k:v for k,v in config.items()if k!='testing_authority_sha256'},
            {**config,'testing_purpose':authority.PURPOSES['preparation']},
            {**config,'semantic_max_calls':True},{**config,'semantic_max_calls':8}]
        with self.scope():
            for c in cases:
                with self.subTest(config=c):self.assertIsNone(self.proposal(tip,c))
            with override_settings(TESTING_AUTHORITY_MODE='',TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256=''):
                self.assertIsNone(self.proposal(tip))
            with patch.object(authority,'admit_actor',side_effect=ValidationError('TESTONLY denied actor')):
                self.assertIsNone(self.proposal(tip))
            with patch.object(authority,'admit_actor',side_effect=PermissionDenied('TESTONLY revoked membership')):
                self.assertIsNone(self.proposal(tip))

    def test_current_revocation_denies_new_offer_but_does_not_unlink_historical_v2_edge(self):
        tip=self.family(3)
        with self.scope():value=self.proposal(tip)
        child=self.successor(tip,value,self.prospective(tip));before=deepcopy(self.jobs)
        with self.scope(),override_settings(TESTING_AUTHORITY_MODE='',TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256=''):
            self.assertTrue(recovery.linked(tip,child))
            self.assertEqual(recovery.family_ids(child),{job.pk for job in self.jobs})
            self.assertIsNone(self.proposal(child))
        self.assertEqual(self.jobs,before)

    def test_source_actor_rate_cap_and_unchanged_release_or_transport_cannot_recover(self):
        tip=self.family(3);config=self.prospective(tip)
        cases=[{**config,'input_rate':'3'},{**config,'semantic_maximum_cost':'8.16'},
            {**config,'semantic_source_sha256':'c'*64},
            {**config,recovery.TRANSPORT_KEY:tip.config[recovery.TRANSPORT_KEY]},
            {**config,recovery.TRANSPORT_KEY:self.jobs[0].config[recovery.TRANSPORT_KEY]}]
        with self.scope():
            for c in cases:
                with self.subTest(config=c):self.assertIsNone(self.proposal(tip,c))
            with patch.object(recovery,'_source_matches',return_value=False):self.assertIsNone(self.proposal(tip))
            with override_settings(RELEASE_SHA=tip.config['queued_release_sha']):self.assertIsNone(self.proposal(tip))
            other=SimpleNamespace(pk=UUID(int=999))
            self.assertIsNone(recovery._proposal(tip,self.encounter,other,config))

    def test_v2_edges_require_closed_typed_fields_and_exact_append_only_audit(self):
        tip=self.family(3)
        with self.scope():value=self.proposal(tip)
        child=self.successor(tip,value,self.prospective(tip));proof={**self.proof(tip),'prior_calls':3,'prior_quote':'1.500000000000'}
        with self.scope():
            self.assertTrue(recovery._edge(tip,child,proof))
            for key,bad in [('family_max_calls',8.0),('per_batch_max_calls',True),
                            ('family_cost_ceiling',8.15),('testing_authority_sha256','0'*64),('extra',1)]:
                original=deepcopy(child.config);child.config[recovery.RECOVERY_KEY][key]=bad
                with self.subTest(key=key):self.assertFalse(recovery._edge(tip,child,proof))
                child.config=original
            self.events[str(child.pk)].append(deepcopy(self.events[str(child.pk)][0]))
            self.assertFalse(recovery._edge(tip,child,proof))

    def test_fork_remains_unrecoverable_and_busy_without_consuming_or_rewriting_holds(self):
        tip=self.family(3);before=deepcopy(self.jobs)
        self.children[self.jobs[0].pk].append(SimpleNamespace(pk=UUID(int=9999)))
        with self.scope():
            self.assertIsNone(recovery.rejection(tip));self.assertEqual(recovery.family_ids(tip),set())
            self.assertTrue(recovery.pending_jobs(self.jobs));self.assertIsNone(recovery.offer(self.encounter,self.user,self.prospective(tip)))
        self.assertEqual(self.jobs,before)
