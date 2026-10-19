"""Synthetic immutable provenance; no retained clinical records."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import unittest
from ops import backup_restore as b


def fixture(v=1):
    uid=lambda n:f'00000000-0000-0000-0000-{n:012d}'
    config={'semantic_contract':'semantic-facts-v1','semantic_max_calls':5,
        'semantic_source_sha256':b.digest(b'synthetic source'),'semantic_definitions_sha256':'a'*64,
        'semantic_template_version':uid(3)}
    parent=dict(id=uid(4),kind='generation',state='succeeded',finished_at='2026-01-01T00:00:00Z',
        encounter_id=uid(1),user_id=uid(2),revision=1,config=config,result_path='receipts/parent.json',result_sha256='b'*64)
    def stage(job,role,attempt,n):
        return dict(id=uid(n),job_id=job['id'],stage=role,attempt=attempt,state='succeeded',
            finished_at='2026-01-01T00:00:00Z',config=deepcopy(job['config']),actual_cost='0.100000000000',
            request_path='receipts/request.json',result_path='receipts/result.json',request_sha256='c'*64,
            result_sha256='d'*64,provider_request_id=f'request-{n}',provider_resource_id=f'resource-{n}')
    stages=[stage(parent,r,a,10+i) for i,(r,a) in enumerate([
        ('extractor',1),('assigner',1),('checker',1),('assigner',2),('checker',2)])]
    manifest=[{k:s[k] for k in ('id','stage','attempt','request_sha256','result_sha256',
        'provider_request_id','provider_resource_id','actual_cost')}|{'config_sha256':b._canonical_digest(config)} for s in stages]
    binding=dict(parent_job_id=uid(4),parent_run_id=uid(5),parent_answers_sha256=b._canonical_digest({}),
        source_sha256=config['semantic_source_sha256'],definitions_sha256='a'*64,template_version_id=uid(3),
        encounter_id=uid(1),patient_id=uid(6),revision=1,parent_result_sha256='b'*64,
        parent_receipts_digest=b._canonical_digest(manifest),actor_id=uid(2),
        target_scope_contract='positioned-complete-assertions-v20' if v==3 else 'positioned-objective-negation-v12')
    contract=f'retained-facts-independent-check-v{v}'
    if v>1:binding['contract']=contract
    child=deepcopy(parent);child.update(id=uid(7),state='failed',result_sha256='e'*64,request_key=f'semantic-revalidation:{parent["id"]}:{contract}')
    child['config'].update(semantic_revalidation_contract=contract,semantic_revalidation=binding,
        semantic_max_calls=1,semantic_fact_scope_contract=binding['target_scope_contract'])
    source=dict(id=uid(5),encounter_id=uid(1),user_id=uid(2),state='needs_detail',config={'provider':'corti','mode':'live'},
        inputs=dict(notes='synthetic source',answers={},encounter_id=uid(1),patient_id=uid(6),template_version_id=uid(3),revision=1))
    row=dict(job=child,parent=parent,source=source,parent_stages=stages,stages=[stage(child,'revalidation_checker',1,20)],
        same_contract_count=1,prior=None,prior_stages=None,prior_usage=None,prior_config_md5=None)
    if v==2:
        prior=deepcopy(child);prior['id']=uid(8);prior['request_key']=f'semantic-revalidation:{parent["id"]}:retained-facts-independent-check-v1';prior['config']['semantic_revalidation_contract']='retained-facts-independent-check-v1'
        prior['config']['semantic_revalidation'].pop('contract');ps=stage(prior,'revalidation_checker',1,21)
        pu=dict(id=uid(9),job_id=prior['id'],user_id=prior['user_id'],actual_cost=ps['actual_cost'])
        binding['prior_revalidation']=dict(job_id=prior['id'],contract='retained-facts-independent-check-v1',state='failed',
            config_sha256=b._canonical_digest(prior['config']),result_sha256=prior['result_sha256'],config_database_md5='f'*32,
            receipt_id=ps['id'],request_sha256=ps['request_sha256'],response_sha256=ps['result_sha256'],
            receipt_config_sha256=b._canonical_digest(prior['config']),usage_id=pu['id'],actual_cost=pu['actual_cost'])
        row['stages'][0]['config']=deepcopy(child['config'])
        row.update(prior=prior,prior_stages=[ps],prior_usage=[pu],prior_config_md5='f'*32)
    return row


class RetainedAccountingTests(unittest.TestCase):
    def test_known_contracts_paid_failure_and_success(self):
        for v in (1,2,3):
            row=fixture(v);self.assertTrue(b.revalidation_lineage_valid(row))
            row['stages'][0]['state']='failed';self.assertTrue(b.revalidation_lineage_valid(row))
            row['job']['state']='succeeded';self.assertFalse(b.revalidation_lineage_valid(row))

    def test_retained_live_and_mutable_encounter_not_authorities(self):
        row=fixture(3);row['source']['config'].update(mode='retained_live',retained_prediction={'contract':'retained-live-context-review-v1'})
        row['current_encounter']={'revision':99,'notes':'later','status':'approved'}
        self.assertTrue(b.revalidation_lineage_valid(row))
        row['source']['config']['retained_prediction']['contract']='unknown';self.assertFalse(b.revalidation_lineage_valid(row))

    def test_tampering(self):
        changes=[(('job','user_id'),'wrong'),(('job','revision'),2),(('job','config','semantic_max_calls'),True),
          (('job','config','semantic_max_calls'),1.0),(('job','config','semantic_revalidation_contract'),'unknown'),
          (('job','config','semantic_revalidation','revision'),True),
          (('job','config','semantic_revalidation','parent_result_sha256'),'c'*64),
          (('job','config','semantic_revalidation','parent_receipts_digest'),'c'*64),
          (('source','inputs','notes'),'changed'),(('source','inputs','answers'),{'invented':True}),
          (('source','inputs','patient_id'),'wrong'),(('same_contract_count',),2),
          (('parent_stages',0,'request_sha256'),'a'*64),(('parent_stages',0,'state'),'failed'),
          (('stages',0,'attempt'),2),(('stages',0,'attempt'),True),(('stages',0,'actual_cost'),None),
          (('stages',0,'state'),'unknown'),(('stages',0,'config'),{}),
          (('prior_config_md5',),'0'*32),(('prior','state'),'succeeded'),
          (('prior_stages',0,'state'),'failed'),(('prior_usage',0,'actual_cost'),'0.2')]
        for path,value in changes:
            row=fixture(2);target=row
            for part in path[:-1]:target=target[part]
            target[path[-1]]=value
            with self.subTest(path=path,value=value):self.assertFalse(b.revalidation_lineage_valid(row))

    def test_missing_bindings_and_duplicate_stage(self):
        for v in (1,2,3):
            original=fixture(v)
            for key in original['job']['config']['semantic_revalidation']:
                row=deepcopy(original);del row['job']['config']['semantic_revalidation'][key]
                self.assertFalse(b.revalidation_lineage_valid(row))
            original['stages']*=2;self.assertFalse(b.revalidation_lineage_valid(original))

    def test_unchanged_historical_predicate(self):
        self.assertEqual(hashlib.sha256(b._SEMANTIC_STAGE_TOTAL_VALID.encode()).hexdigest(),'011d69d033a63195c9d6a84607e823f70eed8e3c123e778cc5594f5e298c7801')
        self.assertIn(b._SEMANTIC_STAGE_TOTAL_VALID,b._ACCOUNTED_STAGE_TOTAL_VALID)

    def test_actual_invariant_entrypoint(self):
        def query(sql):
            if sql.startswith('SELECT to_regclass'):return [('present',)]
            if sql==b._REVALIDATION_LINEAGE_ROWS:return [(fixture(1),)]
            return [(0,)]
        self.assertEqual(b.invariant_counts(query)['usage_multiplier'],0)
        invalid=fixture(1);invalid['job']['config']['semantic_max_calls']=2
        with self.assertRaisesRegex(RuntimeError,'Database invariants failed'):
            b.invariant_counts(lambda sql:[(invalid,)] if sql==b._REVALIDATION_LINEAGE_ROWS else query(sql))

    def test_exact_child_and_prior_request_keys(self):
        for version in (1,2,3):
            original=fixture(version)
            self.assertTrue(b.revalidation_lineage_valid(original))
            for key in ('','unrelated-retained-request-key',None,
                    'semantic-revalidation:wrong-parent:retained-facts-independent-check-v1',
                    original['job']['request_key']+':retry'):
                row=deepcopy(original);row['job']['request_key']=key
                with self.subTest(version=version,child_key=key):
                    self.assertFalse(b.revalidation_lineage_valid(row))
            row=deepcopy(original);del row['job']['request_key']
            self.assertFalse(b.revalidation_lineage_valid(row))
        original=fixture(2)
        for key in ('','unrelated-retained-request-key',None,original['job']['request_key']):
            row=deepcopy(original);row['prior']['request_key']=key
            with self.subTest(prior_key=key):self.assertFalse(b.revalidation_lineage_valid(row))
        row=deepcopy(original);del row['prior']['request_key']
        self.assertFalse(b.revalidation_lineage_valid(row))
