"""Synthetic-only retention inventory and real PostgreSQL read-only proofs."""
import copy
from datetime import timedelta
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from django.apps import apps
from django.core.management import call_command, CommandError
from django.db import connection, DatabaseError, transaction
from django.test import SimpleTestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from core import retention_readiness as retention
from core.models import User, Organization, Department, Patient, Template, TemplateVersion, Encounter, Job, ProviderReceipt, AuditEvent, Wallet, LedgerEntry

class RetentionPolicy(SimpleTestCase):
    def encoded(self,policy):return json.dumps(policy).encode()

    def test_complete_unset_example_is_valid_but_has_no_windows(self):
        policy=retention.parse_policy(self.encoded(retention.unresolved_policy()))
        self.assertTrue(all(rule.days is None for rule in policy.classes.values()))
        self.assertIsNone(policy.schedule_document_sha256)
        labels={item[0] for item in retention.CATALOG.values()}
        self.assertTrue({model._meta.label for model in apps.get_app_config('core').get_models()}<=labels)

    def test_missing_unknown_duplicate_and_overlong_policy_refuse(self):
        good=retention.unresolved_policy();cases=[{}, {**good,'execute':True}, {**good,'coverage':{}}, {**good,'classes':{}}]
        for missing in ['patient_identity','ledger','recording_references']:
            value=copy.deepcopy(good);del value['classes'][missing];cases.append(value)
        for value in cases:
            with self.subTest(keys=list(value)),self.assertRaises(retention.PolicyError):retention.parse_policy(self.encoded(value))
        for raw in [b'{"contract":1,"contract":2}',b'X'*(retention.MAX_POLICY_BYTES+1),b'\xff']:
            with self.assertRaises(retention.PolicyError):retention.parse_policy(raw)

    def test_bad_windows_booleans_arbitrary_anchors_and_protected_classes_refuse(self):
        for name,rule in [('patient_identity',{'mode':'review_window','anchor':'created_at','days':value}) for value in [None,True,False,0,-1,365001,'30']]+[
            ('patient_identity',{'mode':'review_window','anchor':'display_name','days':30}),
            ('patient_identity',{'mode':'preserve','anchor':'created_at','days':30}),
            ('ledger',{'mode':'review_window','anchor':'created_at','days':30}),
            ('final_export_references',{'mode':'review_window','anchor':'finalized_at','days':30}),
            ('mfa_devices',{'mode':'review_window','anchor':'created_at','days':30})]:
            body=retention.unresolved_policy();body['schedule_document_sha256']='a'*64;body['classes'][name]=rule
            with self.subTest(name=name,rule=rule),self.assertRaises(retention.PolicyError):retention.parse_policy(self.encoded(body))
        body=retention.unresolved_policy();body['classes']['patient_identity']={'mode':'review_window','anchor':'created_at','days':30}
        with self.assertRaises(retention.PolicyError):retention.parse_policy(self.encoded(body))

    def test_partial_policy_and_paths_never_leak_or_query_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'SYNTHETIC_PRIVATE_POLICY_NAME.json'
            path.write_text('{"patient_name":"SYNTHETIC_PRIVATE_VALUE"}')
            output=io.StringIO()
            with patch.object(retention,'report') as report,self.assertRaises(CommandError) as error:
                call_command('retention_readiness',policy=str(path),stdout=output)
            report.assert_not_called()
            self.assertEqual(output.getvalue(),'')
            for value in [str(path),'SYNTHETIC_PRIVATE_VALUE']:
                self.assertNotIn(value,str(error.exception))

    def test_validate_only_never_queries_database_and_never_grants_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'policy.json';path.write_bytes(self.encoded(retention.unresolved_policy()))
            output=io.StringIO()
            with patch.object(retention,'report') as report:call_command('retention_readiness',policy=str(path),validate_only=True,stdout=output)
            report.assert_not_called();result=json.loads(output.getvalue())
            self.assertTrue(result['policy_shape_valid']);self.assertFalse(result['purge_available'])
            self.assertFalse(result['policy_authority_verified']);self.assertEqual(result['status'],'blocked')

class RetentionCounts(TransactionTestCase):
    def setUp(self):
        self.now=timezone.now();self.old=self.now-timedelta(days=90)
        self.user=User.objects.create_user(username='SYNTHETIC_PRIVATE_USER',email='retention@synthetic.invalid')
        self.org=Organization.objects.create(name='SYNTHETIC_PRIVATE_CLINIC')
        self.department=Department.objects.create(organization=self.org,name='SYNTHETIC_PRIVATE_DEPT')
        self.patient=Patient.objects.create(department=self.department,display_name='SYNTHETIC_PRIVATE_NAME',reference='SYNTHETIC_PRIVATE_REFERENCE',created_by=self.user)
        Patient.objects.filter(pk=self.patient.pk).update(created_at=self.old)
        Patient.objects.create(department=self.department,display_name='SYNTHETIC_NEW_NAME',reference='new',created_by=self.user)
        template=Template.objects.create(department=self.department,name='SYNTHETIC_PRIVATE_TEMPLATE',format='docx',original_name='private.docx',original_path='originals/SYNTHETIC_PRIVATE_PATH.docx',sha256='1'*64,created_by=self.user)
        version=TemplateVersion.objects.create(template=template,number=1,fields=[],created_by=self.user)
        self.encounter=Encounter.objects.create(department=self.department,patient=self.patient,template_version=version,created_by=self.user,notes='SYNTHETIC_PRIVATE_NOTE',service_date=self.now.date())
        Encounter.objects.create(department=self.department,patient=self.patient,template_version=version,created_by=self.user,notes='SYNTHETIC_FINAL_NOTE',service_date=self.now.date(),status='finalized',finalized_at=self.old,export_path='exports/SYNTHETIC_EXPORT.docx',export_sha256='2'*64)
        self.job=Job.objects.create(encounter=self.encounter,user=self.user,kind='transcription',request_key='synthetic_retention',input_path='audio/SYNTHETIC_RECORDING.wav',result_path='receipts/SYNTHETIC_TRANSCRIPT.json',finished_at=self.old)
        Job.objects.create(encounter=self.encounter,user=self.user,kind='transcription',request_key='synthetic_retention_missing_date',input_path='audio/SYNTHETIC_RECORDING_NEW.wav')
        ProviderReceipt.objects.create(job=self.job,provider='synthetic',actual_cost=0,result_path='receipts/SYNTHETIC_LEGACY_RESULT.json')
        AuditEvent.objects.create(actor=self.user,action='synthetic.retention',details={'note':'SYNTHETIC_AUDIT_CONTENT'})
        wallet=Wallet.objects.create(user=self.user,kind='paid')
        LedgerEntry.objects.create(wallet=wallet,amount=0,kind='synthetic',key='synthetic_retention',description='SYNTHETIC_LEDGER_CONTENT',balance_after=0)

    def policy(self,windows=False,declared=False):
        value=retention.unresolved_policy()
        if windows:
            value['schedule_document_sha256']='a'*64
            for name,anchor in [('patient_identity','created_at'),('recording_references','finished_at')]:
                value['classes'][name]={'mode':'review_window','anchor':anchor,'days':30}
        if declared:
            value['coverage']={name:'declared_for_review' for name in retention.EXTERNAL}
            for name,rule in value['classes'].items():
                if rule['mode']=='unresolved':value['classes'][name]={'mode':'preserve','anchor':None,'days':None}
        return retention.parse_policy(json.dumps(value).encode())

    def test_counts_are_aggregate_only_and_unknown_policy_is_blocked(self):
        with CaptureQueriesContext(connection) as captured,patch('pathlib.Path.open',side_effect=AssertionError('No files read')):
            result=retention.report(self.policy(),self.now)
        rows={row['class']:row for row in result['rows']}
        self.assertEqual(rows['patient_identity']['records'],2)
        self.assertEqual(rows['final_export_references']['records'],1)
        self.assertEqual(rows['recording_references']['records'],2)
        self.assertEqual(rows['ledger']['records'],1)
        self.assertTrue(all(row['at_or_before_review_cutoff'] is None for row in result['rows']))
        self.assertTrue(all(row['deletion_eligible_count'] is None for row in result['rows']))
        text=json.dumps(result)
        for forbidden in ['SYNTHETIC_PRIVATE','SYNTHETIC_RECORDING','SYNTHETIC_TRANSCRIPT','SYNTHETIC_AUDIT_CONTENT','SYNTHETIC_LEDGER_CONTENT','SYNTHETIC_EXPORT',str(self.patient.pk),str(self.job.pk),str(self.user.pk)]:
            self.assertNotIn(forbidden,text)
        queries=[row['sql'] for row in captured.captured_queries]
        self.assertTrue(any('READ ONLY' in query for query in queries))
        for query in queries:
            if query.lstrip().upper().startswith('SELECT'):self.assertIn('COUNT(',query)
            self.assertFalse(query.lstrip().upper().startswith(('INSERT','UPDATE','DELETE','TRUNCATE','ALTER','DROP')))
        self.assertEqual(result['status'],'blocked');self.assertFalse(result['purge_available'])

    def test_declared_windows_produce_only_review_counts_never_deletion_authority(self):
        result=retention.report(self.policy(windows=True,declared=True),self.now)
        rows={row['class']:row for row in result['rows']}
        self.assertEqual(rows['patient_identity']['at_or_before_review_cutoff'],1)
        self.assertEqual(rows['recording_references']['at_or_before_review_cutoff'],1)
        self.assertEqual(rows['recording_references']['missing_review_anchor'],1)
        self.assertIsNone(rows['final_export_references']['at_or_before_review_cutoff'])
        self.assertFalse(result['policy_authority_verified']);self.assertFalse(result['deletion_eligibility_assessed'])
        self.assertIn('tombstone_and_deletion_workflow_not_implemented',result['blockers'])
        self.assertEqual(result['status'],'blocked')
        if location:=__import__('os').getenv('QUILLMD_RETENTION_ARTIFACT_DIR'):
            path=Path(location);path.mkdir(parents=True,exist_ok=True)
            (path/'synthetic-aggregate-report.json').write_text(json.dumps(result,indent=2)+'\n')

    def test_postgresql_refuses_real_write_inside_count_transaction_and_restores_connection(self):
        before=Organization.objects.count()
        def attempted_write(*args):
            with connection.cursor() as cursor:
                cursor.execute('SHOW transaction_read_only');self.assertEqual(cursor.fetchone(),('on',))
            Organization.objects.create(name='SYNTHETIC_FORBIDDEN_WRITE')
        with patch.object(retention,'count_class',side_effect=attempted_write),self.assertRaises(DatabaseError) as error:
            retention.report(self.policy(),self.now)
        self.assertIn('read-only',str(error.exception))
        self.assertEqual(Organization.objects.count(),before)
        self.assertFalse(connection.in_atomic_block)
        positive=Organization.objects.create(name='SYNTHETIC_WRITE_OUTSIDE_CONTROL')
        self.assertTrue(Organization.objects.filter(pk=positive.pk).exists())

    def test_nested_transaction_and_partial_query_failure_return_no_report(self):
        with transaction.atomic(),self.assertRaises(retention.PolicyError):retention.report(self.policy(),self.now)
        count=retention.count_class;calls=0
        def fail_midway(*args):
            nonlocal calls
            calls+=1
            if calls==3:raise DatabaseError('SYNTHETIC_PRIVATE_SQL_EXCEPTION')
            return count(*args)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'policy.json';path.write_text(json.dumps(retention.unresolved_policy()))
            output=io.StringIO()
            with patch.object(retention,'count_class',side_effect=fail_midway),self.assertRaises(CommandError) as error:
                call_command('retention_readiness',policy=str(path),stdout=output)
            self.assertEqual(output.getvalue(),'');self.assertNotIn('SYNTHETIC_PRIVATE',str(error.exception))
        self.assertEqual(Patient.objects.count(),2)

    def test_successful_command_has_no_execution_option_or_mutating_side_effect(self):
        before={model.__name__:model.objects.count() for model in [Patient,Job,ProviderReceipt,AuditEvent,LedgerEntry,Encounter]}
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'policy.json';path.write_text(json.dumps(retention.unresolved_policy()))
            output=io.StringIO();call_command('retention_readiness',policy=str(path),stdout=output)
            self.assertEqual(json.loads(output.getvalue())['status'],'blocked')
            with self.assertRaises(TypeError):call_command('retention_readiness',policy=str(path),execute=True)
        self.assertEqual(before,{model.__name__:model.objects.count() for model in [Patient,Job,ProviderReceipt,AuditEvent,LedgerEntry,Encounter]})

class RetentionPublishedPolicy(SimpleTestCase):
    def test_published_schema_and_unset_policy_match_runtime_exactly(self):
        root=Path(__file__).resolve().parents[2]/'ops'/'retention'
        self.assertEqual(json.loads((root/'policy.schema.json').read_text()),retention.policy_schema())
        self.assertEqual(json.loads((root/'policy.unset.json').read_text()),retention.unresolved_policy())
        schema=retention.policy_schema()
        self.assertEqual(set(schema['properties']['classes']['required']),set(retention.CATALOG))
        self.assertFalse(schema['properties']['classes']['additionalProperties'])

    def test_published_reviewed_transcripts_have_no_aging_or_deletion_authority(self):
        root=Path(__file__).resolve().parents[2]/'ops'/'retention'
        body=json.loads((root/'policy.unset.json').read_text())
        policy=retention.parse_policy(json.dumps(body).encode())
        self.assertEqual(policy.classes['reviewed_transcripts'].mode,'unresolved')
        self.assertIsNone(policy.classes['reviewed_transcripts'].days)
        self.assertIsNone(policy.schedule_document_sha256)
        # A forged review window on immutable clinical reviews cannot become
        # accepted merely because the published catalog now names their class.
        body['schedule_document_sha256']='a'*64
        body['classes']['reviewed_transcripts']={'mode':'review_window','anchor':'created_at','days':30}
        with self.assertRaises(retention.PolicyError):
            retention.parse_policy(json.dumps(body).encode())
