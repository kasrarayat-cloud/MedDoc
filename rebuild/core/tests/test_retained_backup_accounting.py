"""Execute the actual accounting SQL against synthetic, transaction-local rows."""
from copy import deepcopy
import json
from django.db import connection
from django.test import TestCase
from psycopg.types.json import Jsonb
from ops import backup_restore as b
from ops.test_retained_backup_accounting import fixture


class RetainedBackupSQLTests(TestCase):
    def setUp(self):
        if connection.vendor!='postgresql':self.skipTest('PostgreSQL JSONB accounting predicate')
        self.cursor=connection.cursor();self.addCleanup(self.cursor.close)
        for table in ('core_job','core_aistagereceipt','core_codingrun','core_usage','core_encounter'):
            self.cursor.execute(f'CREATE TEMP TABLE {table} ON COMMIT DROP AS SELECT * FROM public.{table} WITH NO DATA')

    def insert(self,table,row):
        self.cursor.execute(f'INSERT INTO {table} SELECT * FROM jsonb_populate_record(NULL::{table}, %s::jsonb)',[Jsonb(row)])

    def load(self,v):
        row=fixture(v)
        for j in [row['job'],row['parent']]+([row['prior']] if row['prior'] else []):
            j['config'].update(semantic_stage_protocol='quillmd-ai-stages-v1',semantic_capacity_profile='bounded-output-16k-v1',
                semantic_output_token_limit=16000,semantic_timeout_seconds=120,semantic_request_byte_limit=512000)
        for s in row['parent_stages']+row['stages']+(row['prior_stages'] or []):
            job=next(j for j in [row['job'],row['parent'],row['prior']] if j and j['id']==s['job_id'])
            s['config']=deepcopy(job['config'])
            s.update(created_at='2026-01-01T00:00:%02dZ'%int(s['id'][-2:]),provider='anthropic',requested_model='synthetic-model',
                returned_model='synthetic-model',error_code='',simulated=True,usage={'output_tokens':0},rates={},started_at=None)
        # Recompute genuinely changed synthetic provenance after adding SQL columns/config.
        manifest=[{k:s[k] for k in ('id','stage','attempt','request_sha256','result_sha256','provider_request_id','provider_resource_id','actual_cost')}
            |{'config_sha256':b._canonical_digest(s['config'])} for s in row['parent_stages']]
        binding=row['job']['config']['semantic_revalidation'];binding['parent_receipts_digest']=b._canonical_digest(manifest)
        if v==2:
            row['prior']['config']['semantic_revalidation']['parent_receipts_digest']=binding['parent_receipts_digest']
            row['prior_stages'][0]['config']=deepcopy(row['prior']['config'])
            self.cursor.execute('SELECT md5(%s::jsonb::text)',[Jsonb(row['prior']['config'])])
            row['prior_config_md5']=self.cursor.fetchone()[0]
            binding['prior_revalidation'].update(config_sha256=b._canonical_digest(row['prior']['config']),
                receipt_config_sha256=b._canonical_digest(row['prior']['config']),config_database_md5=row['prior_config_md5'])
        row['stages'][0]['config']=deepcopy(row['job']['config'])
        for j in [row['parent'],row['job']]+([row['prior']] if row['prior'] else []):self.insert('core_job',j)
        for s in row['parent_stages']+row['stages']+(row['prior_stages'] or []):self.insert('core_aistagereceipt',s)
        self.insert('core_codingrun',row['source'])
        s=row['stages'][0]
        item={k:s[k] for k in ('id','stage','attempt','provider','requested_model','returned_model','state','error_code','request_sha256','result_sha256','simulated','usage','rates','started_at','actual_cost')}
        item.update(request_id=s['provider_request_id'],resource_id=s['provider_resource_id'],config_sha256=b._canonical_digest(s['config']))
        usage=dict(id='00000000-0000-0000-0000-000000000099',job_id=row['job']['id'],provider='quillmd:semantic-stages',
            provider_request_id='',provider_resource_id='',units={'protocol':'quillmd-ai-stages-v1','stages':[item]},
            rates={'aggregation':'sum_of_independently_rounded_stage_costs'},actual_cost=s['actual_cost'],simulated=True)
        self.insert('core_usage',usage)
        for u in row['prior_usage'] or []:self.insert('core_usage',u)
        return row

    def valid_sql(self):
        self.cursor.execute('SELECT ('+b._REVALIDATION_STAGE_TOTAL_VALID+") IS TRUE FROM core_job j JOIN core_usage u ON u.job_id=j.id LEFT JOIN core_encounter e ON e.id=j.encounter_id WHERE j.id='00000000-0000-0000-0000-000000000007'")
        return self.cursor.fetchone()[0]

    def test_three_contracts_full_query_and_typed_forgeries(self):
        for v in (1,2,3):
            with self.subTest(version=v):
                row=self.load(v);self.assertTrue(self.valid_sql())
                self.cursor.execute(b._REVALIDATION_LINEAGE_ROWS)
                parsed=[json.loads(x[0]) if isinstance(x[0],str) else x[0] for x in self.cursor.fetchall()]
                observed=[x for x in parsed if x['job']['id']==row['job']['id']]
                self.assertEqual(len(observed),1);self.assertTrue(b.revalidation_lineage_valid(observed[0]))
                for job in [row['job']]+([row['prior']] if row['prior'] else []):
                    self.cursor.execute('UPDATE core_job SET request_key=%s WHERE id=%s',['unrelated-retained-request-key',job['id']])
                    self.cursor.execute(b._REVALIDATION_LINEAGE_ROWS)
                    altered=[json.loads(x[0]) if isinstance(x[0],str) else x[0] for x in self.cursor.fetchall()]
                    proof=next(x for x in altered if x['job']['id']==row['job']['id'])
                    self.assertFalse(b.revalidation_lineage_valid(proof))
                    self.cursor.execute('UPDATE core_job SET request_key=%s WHERE id=%s',[job['request_key'],job['id']])
                for value in ('true','"1"','2','null'):
                    self.cursor.execute("UPDATE core_job SET config=jsonb_set(config,'{semantic_max_calls}',%s::jsonb) WHERE id=%s",[value,row['job']['id']])
                    self.assertFalse(self.valid_sql())
                for table in ('core_job','core_aistagereceipt','core_codingrun','core_usage','core_encounter'):
                    self.cursor.execute(f'TRUNCATE pg_temp.{table}')

    def test_known_paid_failed_checker_not_lost_and_unknown_still_refuses(self):
        row=self.load(1)
        self.cursor.execute("UPDATE core_aistagereceipt SET state='failed' WHERE job_id=%s",[row['job']['id']])
        self.cursor.execute("UPDATE core_usage SET units=jsonb_set(units,'{stages,0,state}','\"failed\"'::jsonb)")
        self.assertTrue(self.valid_sql())
        self.cursor.execute(b._REVALIDATION_LINEAGE_ROWS)
        raw=self.cursor.fetchone()[0];proof=json.loads(raw) if isinstance(raw,str) else raw
        self.assertTrue(b.revalidation_lineage_valid(proof))
        self.cursor.execute("UPDATE core_aistagereceipt SET state='unknown', actual_cost=NULL WHERE job_id=%s",[row['job']['id']])
        self.assertFalse(self.valid_sql())

    def test_capacity_and_stage_limits_cannot_be_relaxed_by_coherent_config_edit(self):
        row=self.load(1);original=row['job']['config']
        for key,value in [('semantic_capacity_profile','bounded-output-32k-v2'),('semantic_timeout_seconds',240),
                ('semantic_timeout_seconds','120'),('semantic_output_token_limit',True),
                ('semantic_request_byte_limit','512000'),('semantic_revalidation_contract','unknown')]:
            config=deepcopy(original);config[key]=value
            self.cursor.execute('UPDATE core_job SET config=%s WHERE id=%s',[Jsonb(config),row['job']['id']])
            self.cursor.execute('UPDATE core_aistagereceipt SET config=%s WHERE job_id=%s',[Jsonb(config),row['job']['id']])
            with self.subTest(key=key,value=value):self.assertFalse(self.valid_sql())

    def test_original_five_stage_sql_positive_remains_valid(self):
        row=self.load(1);p=row['parent'];items=[]
        for s in row['parent_stages']:
            item={k:s[k] for k in ('id','stage','attempt','provider','requested_model','returned_model','state','error_code',
                'request_sha256','result_sha256','simulated','usage','rates','started_at','actual_cost')}
            item.update(request_id=s['provider_request_id'],resource_id=s['provider_resource_id'],config_sha256=b._canonical_digest(s['config']))
            items.append(item)
        self.insert('core_encounter',dict(id=p['encounter_id'],template_version_id=p['config']['semantic_template_version']))
        self.insert('core_usage',dict(id='00000000-0000-0000-0000-000000000098',job_id=p['id'],provider='quillmd:semantic-stages',
            provider_request_id='',provider_resource_id='',units={'protocol':'quillmd-ai-stages-v1','stages':items},
            rates={'aggregation':'sum_of_independently_rounded_stage_costs'},actual_cost='0.500000000000',simulated=True))
        self.cursor.execute('SELECT ('+b._SEMANTIC_STAGE_TOTAL_VALID+') IS TRUE FROM core_job j JOIN core_usage u ON u.job_id=j.id JOIN core_encounter e ON e.id=j.encounter_id WHERE j.id=%s',[p['id']])
        self.assertTrue(self.cursor.fetchone()[0])
