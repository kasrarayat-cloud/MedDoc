"""Finite mocked AWS verification; no cloud requests."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from ops import aws_backup_status as s, deployment_profile
from ops.production_operator import OperatorError
from ops.test_production_operator import profile

NOW = datetime(2026,9,27,20,0,tzinfo=timezone.utc)
RECENT = (NOW-timedelta(minutes=30)).isoformat()


def config():
    a,b='123456789012','210987654321'
    return dict(format=1, profile_sha256=profile().sha256, database_arn=f'arn:aws:rds:us-east-1:{a}:db:quillmd-production',
        database_resource_id='db-SYNTHETIC', state_volume_arn=f'arn:aws:ec2:us-east-1:{a}:volume/vol-0123456789abcdef0',
        kms_key_arn=f'arn:aws:kms:us-east-1:{a}:key/12345678-1234-1234-1234-123456789012',
        copy_kms_key_arn=f'arn:aws:kms:us-east-1:{b}:key/12345678-1234-1234-1234-123456789012',
        source_vault_arn=f'arn:aws:backup:us-east-1:{a}:backup-vault:source', copy_vault_arn=f'arn:aws:backup:us-east-1:{b}:backup-vault:copy',
        source_read_role_arn=f'arn:aws:iam::{a}:role/backup-read', copy_read_role_arn=f'arn:aws:iam::{b}:role/backup-read')


class Transport:
    def __init__(self):
        c,p=config(),profile();self.calls=[];self.assumed=[]
        self.db=dict(DBInstanceArn=c['database_arn'],DbiResourceId=c['database_resource_id'],DBInstanceIdentifier=p.database_instance,
            DBName=p.database_name,Endpoint=dict(Address=p.database_host,Port=p.database_port),StorageEncrypted=True,KmsKeyId=c['kms_key_arn'],
            Engine='postgres',DBInstanceStatus='available',BackupRetentionPeriod=35,
            LatestRestorableTime=(NOW-timedelta(minutes=3)).isoformat())
        self.automated=dict(DBInstanceArn=c['database_arn'],DbiResourceId=c['database_resource_id'],DBInstanceIdentifier=p.database_instance,
            Region=p.region,Status='active',Encrypted=True,KmsKeyId=c['kms_key_arn'],Engine='postgres',BackupRetentionPeriod=35,
            RestoreWindow=dict(EarliestTime=(NOW-timedelta(days=3)).isoformat(),LatestTime=(NOW-timedelta(minutes=3)).isoformat()))
        self.automated_response={'DBInstanceAutomatedBackups':[self.automated]}
        self.vault=dict(BackupVaultArn=c['copy_vault_arn'],EncryptionKeyArn=c['copy_kms_key_arn'],Locked=True,LockDate=(NOW-timedelta(days=10)).isoformat())
        self.records={}
        for kind,res in [('RDS',c['database_arn']),('EBS',c['state_volume_arn'])]:
            common=dict(ResourceType=kind,ResourceArn=res,CreationDate=RECENT,CompletionDate=RECENT,State='COMPLETED',MessageCategory='SUCCESS')
            src,dst='arn:aws:backup:us-east-1:123456789012:recovery-point:'+kind,'arn:aws:backup:us-east-1:210987654321:recovery-point:'+kind
            self.records['source','list-backup-jobs',res]={'BackupJobs':[dict(common,BackupVaultArn=c['source_vault_arn'],RecoveryPointArn=src)]}
            self.records['source','list-copy-jobs',res]={'CopyJobs':[dict(common,SourceBackupVaultArn=c['source_vault_arn'],DestinationBackupVaultArn=c['copy_vault_arn'],SourceRecoveryPointArn=src,DestinationRecoveryPointArn=dst)]}
            for scope,arn in [('source',src),('copy',dst)]:
                self.records[scope,'list-recovery-points-by-backup-vault',res]={'RecoveryPoints':[dict(ResourceType=kind,ResourceArn=res,CreationDate=RECENT,BackupVaultArn=c[scope+'_vault_arn'],RecoveryPointArn=arn,Status='COMPLETED',IsEncrypted=True,EncryptionKeyArn=c['kms_key_arn' if scope=='source' else 'copy_kms_key_arn'])]}
    def assume(self,scope,arn):self.assumed.append((scope,arn))
    def request(self,scope,service,operation,*args):
        self.calls.append((scope,service,operation,args))
        if operation=='describe-db-instance-automated-backups':return self.automated_response
        if service=='rds':return {'DBInstances':[self.db]}
        if operation=='describe-backup-vault':return self.vault
        return self.records[scope,operation,args[args.index('--by-resource-arn')+1]]
    def data(self,scope,operation):return self.records[scope,operation,config()['state_volume_arn']]
    def row(self,scope,operation):return next(iter(self.data(scope,operation).values()))[0]


class AWSBackupStatusTests(unittest.TestCase):
    def project(self,aws=None):return s.collect(profile(),config(),aws or Transport(),NOW)[0]
    def test_complete_capture_is_not_restore_or_alert_proof(self):
        aws=Transport();r=self.project(aws)
        self.assertEqual(r['condition'],'aws_capture_current');self.assertEqual(r['offsite']['copy_resources_current'],2)
        self.assertFalse(r['healthy']);self.assertFalse(r['offsite_recovery_verified']);self.assertFalse(r['outside_host_failure_detection'])
        self.assertEqual(r['severity'],'warning');self.assertEqual(len(aws.assumed),2)
        for hidden in ('arn:','123456789012','210987654321','vol-','db-SYNTHETIC'):self.assertNotIn(hidden,json.dumps(r))
    def test_missing_unrelated_or_unencrypted_copy_not_covered_by_other_resource(self):
        for mutation in ('missing','source','destination','encrypted'):
            aws=Transport()
            if mutation=='missing':aws.data('copy','list-recovery-points-by-backup-vault')['RecoveryPoints']=[]
            elif mutation=='encrypted':aws.row('copy','list-recovery-points-by-backup-vault')['IsEncrypted']=False
            else:aws.row('source','list-copy-jobs')['SourceRecoveryPointArn' if mutation=='source' else 'DestinationRecoveryPointArn']='unrelated'
            with self.subTest(mutation=mutation):
                r=self.project(aws);self.assertEqual(r['condition'],'aws_capture_attention');self.assertEqual(r['offsite']['copy_resources_current'],1)
    def test_stale_future_and_completed_with_issues_do_not_pass(self):
        for value in ((NOW-timedelta(hours=3)).isoformat(),(NOW+timedelta(minutes=1)).isoformat()):
            aws=Transport();aws.row('source','list-backup-jobs')['CreationDate']=value
            self.assertEqual(self.project(aws)['condition'],'aws_capture_attention')
        for category in ('PARTIAL',None):
            aws=Transport();aws.row('source','list-copy-jobs')['MessageCategory']=category;r=self.project(aws)
            self.assertEqual(r['offsite']['failed_copy_jobs'],1);self.assertEqual(r['condition'],'aws_capture_attention')
    def test_failed_job_remains_visible_after_other_success(self):
        aws=Transport();d=aws.data('source','list-backup-jobs');d['BackupJobs'].append(dict(d['BackupJobs'][0],State='FAILED'));r=self.project(aws)
        self.assertEqual(r['offsite']['source_resources_current'],2);self.assertEqual(r['offsite']['failed_backup_jobs'],1)
        self.assertEqual(r['condition'],'aws_capture_attention')
    def test_stale_rds_or_unfinalized_lock_remains_warning(self):
        for key,value in [('LatestRestorableTime',(NOW-timedelta(minutes=16)).isoformat()),('BackupRetentionPeriod',7)]:
            aws=Transport();aws.db[key]=value;self.assertEqual(self.project(aws)['condition'],'aws_capture_attention')
        aws=Transport();aws.automated['RestoreWindow']['EarliestTime']=NOW.isoformat()
        self.assertEqual(self.project(aws)['condition'],'aws_capture_attention')
        for change in ({'Locked':False},{'LockDate':None},{'LockDate':(NOW+timedelta(days=1)).isoformat()}):
            aws=Transport();aws.vault.update(change);self.assertEqual(self.project(aws)['condition'],'aws_capture_attention')
    def test_documented_automated_backup_shape_and_wrong_identity_pages(self):
        aws=Transport();self.assertNotIn('EarliestRestorableTime',aws.db)
        self.assertEqual(self.project(aws)['condition'],'aws_capture_current')
        for key,value in [('DBInstanceArn','wrong'),('DbiResourceId','db-OTHER'),('Region','us-east-2'),('Encrypted',False)]:
            aws=Transport();aws.automated[key]=value
            with self.subTest(key=key),self.assertRaises(OperatorError):self.project(aws)
        aws=Transport();aws.automated_response['Marker']='more'
        with self.assertRaisesRegex(OperatorError,'aws_incomplete'):self.project(aws)
        aws=Transport();aws.automated['Status']='retained'
        self.assertEqual(self.project(aws)['condition'],'aws_capture_attention')

    def test_each_rds_latest_timestamp_must_independently_be_current(self):
        for scope in ('instance', 'backup'):
            aws=Transport()
            if scope=='instance':aws.db['LatestRestorableTime']=(NOW+timedelta(minutes=1)).isoformat()
            else:aws.automated['RestoreWindow']['LatestTime']=(NOW+timedelta(minutes=1)).isoformat()
            with self.subTest(scope=scope):self.assertEqual(self.project(aws)['condition'],'aws_capture_attention')

    def test_wrong_identity_refuses(self):
        for scope,op,key in [('source','list-backup-jobs','ResourceArn'),('source','list-copy-jobs','DestinationBackupVaultArn'),('copy','list-recovery-points-by-backup-vault','BackupVaultArn')]:
            aws=Transport();aws.row(scope,op)[key]='wrong'
            with self.subTest(key=key),self.assertRaises(OperatorError):self.project(aws)
        aws=Transport();aws.db['DbiResourceId']='db-OTHER'
        with self.assertRaisesRegex(OperatorError,'rds_identity'):self.project(aws)
    def test_pagination_is_automatic_bounded_and_truncation_refuses(self):
        aws=Transport();aws.data('source','list-backup-jobs')['NextToken']='more'
        with self.assertRaisesRegex(OperatorError,'aws_incomplete'):self.project(aws)
        for call in aws.calls:
            if call[2].startswith('list-'):self.assertIn('--max-items',call[3]);self.assertNotIn('--no-paginate',call[3])
        with patch.object(s.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'{"NextToken":"more"}')) as run:
            with self.assertRaisesRegex(OperatorError,'aws_incomplete'):s.AWS('us-east-1').request('source','backup','list-backup-jobs')
        self.assertNotIn('--no-paginate',run.call_args.args[0]);self.assertEqual(run.call_args.kwargs['env']['AWS_CONFIG_FILE'],'/dev/null')
        self.assertNotIn('ANTHROPIC_API_KEY',run.call_args.kwargs['env'])
    def test_configuration_binds_profile_volume_and_separate_account(self):
        receipt={'state_volume':'vol-0123456789abcdef0'};self.assertEqual(s.validate(config(),profile(),receipt),config())
        for key,value in [('profile_sha256','bad'),('state_volume_arn',config()['state_volume_arn'][:-1]+'1'),('copy_vault_arn',config()['source_vault_arn']),('copy_read_role_arn',config()['source_read_role_arn'])]:
            with self.subTest(key=key),self.assertRaises(OperatorError):s.validate(dict(config(),**{key:value}),profile(),receipt)
    def test_unactivated_profile_refuses_before_aws(self):
        with patch.object(s.subprocess,'run') as run:
            with self.assertRaises(deployment_profile.ProfileError):deployment_profile.load_production()
        run.assert_not_called()
    def test_unavailable_configuration_produces_redacted_failure(self):
        p=profile()
        with patch.object(s,'private_json',return_value={'profile_sha256':p.sha256}),patch.object(s.os,'geteuid',return_value=0),patch.object(s.Path,'resolve',return_value=p.app_root/'ops/aws_backup_status.py'),patch.object(s,'validate',side_effect=ValueError('patient-secret provider-message')):
            r,code=s.status(p)
        self.assertEqual(code,1);self.assertEqual(r['condition'],'aws_backup_unknown');self.assertNotIn('patient-secret',json.dumps(r))
    def test_units_and_entrypoint_are_operator_only_and_not_enabled_by_bootstrap(self):
        from ops import publish_production_status as entry
        root=Path(__file__).resolve().parents[1]
        unit=(root/'deploy/production/quillmd-production-operations-status.service').read_text()
        self.assertIn('User=root',unit);self.assertIn('NoNewPrivileges=true',unit);self.assertIn('ReadWritePaths=/etc/quillmd-production/operator',unit)
        bootstrap=(root/'deploy/production/bootstrap-host.sh').read_text();self.assertIn('heartbeat,operations-status}.timer',bootstrap)
        self.assertNotIn('enable --now',bootstrap)
        with patch.object(entry.deployment_profile,'load_production',side_effect=deployment_profile.ProfileError('unactivated')),patch.object(entry.os,'execv') as execute,patch('sys.argv',['publisher']):
            self.assertEqual(entry.main(),1)
        execute.assert_not_called()
