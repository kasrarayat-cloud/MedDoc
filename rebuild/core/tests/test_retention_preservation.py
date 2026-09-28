"""Synthetic PostgreSQL preservation and actual authenticated API boundaries."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import uuid
from unittest.mock import patch

from django.core.exceptions import PermissionDenied,ValidationError
from django.conf import settings
from django.db import DatabaseError,connection,connections,transaction
from django.test import Client,TestCase,TransactionTestCase,override_settings
from django.utils import timezone
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import retention
from core.jobs import reap_abandoned_voice_uploads,reap_stray_submissions
from core.models import (AuditEvent,Encounter,Job,PreservedFile,PreservedRecord,RetentionHold,
                         RetentionHoldRelease,User)
from core.tests.test_security import SyntheticFixture

ISOLATED=dict(ADMIN_SITE=False,QUILLMD_PREVIEW_AUTH_ENABLED=False,
              STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},
                        'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})

class Fixture(SyntheticFixture):
    def setup_records(self):
        self.scope=self.make_scope('hold');self.other=self.make_scope('unheld')
        self.encounter=self.scope[5]
        self.admin=User.objects.create_user(username='custodian',email='custodian@synthetic.invalid',verified_at=timezone.now(),is_staff=True)
        self.second=User.objects.create_user(username='custodian2',email='custodian2@synthetic.invalid',verified_at=timezone.now(),is_staff=True)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.override=override_settings(MEDIA_ROOT=Path(self.temp.name));self.override.enable();self.addCleanup(self.override.disable)

    def hold(self,scope='patient',target=None):
        target=target if target is not None else (None if scope=='global' else self.scope[3].pk)
        return retention.create_hold(self.admin,scope,target,'a'*64,uuid.uuid4())

    def file(self,category='audio'):
        path=Path(self.temp.name)/category/(uuid.uuid4().hex+'0'*16+'.wav')
        path.parent.mkdir(exist_ok=True);path.write_bytes(b'SYNTHETIC RECORDING')
        return path


@override_settings(**ISOLATED)
class Preservation(Fixture,TestCase):
    def setUp(self):self.setup_records()

    def test_sql_update_preserves_exact_prior_record_and_correct_scope(self):
        hold=self.hold();old=self.encounter.notes
        with connection.cursor() as cursor:
            cursor.execute('UPDATE core_encounter SET notes=%s,revision=revision+1 WHERE id=%s',['SYNTHETIC CORRECTION',self.encounter.pk])
        saved=PreservedRecord.objects.get(source_id=self.encounter.pk)
        self.assertEqual(saved.prior_record['notes'],old);self.assertEqual(saved.operation,'UPDATE')
        self.assertEqual(saved.hold_ids,[str(hold.pk)])
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.notes,'SYNTHETIC CORRECTION')
        Encounter.objects.filter(pk=self.other[5].pk).update(notes='SYNTHETIC OTHER')
        self.assertEqual(PreservedRecord.objects.count(),1)
        self.assertNotIn(old,json.dumps(list(AuditEvent.objects.filter(action__startswith='retention.').values('details'))))

    def test_organization_department_encounter_and_global_scopes(self):
        for scope,target in [('organization',self.scope[1].pk),('department',self.scope[2].pk),('encounter',self.encounter.pk),('global',None)]:
            with self.subTest(scope=scope):
                hold=retention.create_hold(self.admin,scope,target,'a'*64,uuid.uuid4())
                self.assertTrue(retention.active_holds(encounter_id=self.encounter.pk).filter(pk=hold.pk).exists())
                self.assertEqual(retention.active_holds(encounter_id=self.other[5].pk).filter(pk=hold.pk).exists(),scope=='global')

    def test_hold_and_release_idempotency_and_different_second_custodian(self):
        key=uuid.uuid4();hold=retention.create_hold(self.admin,'global',None,'a'*64,key)
        self.assertEqual(retention.create_hold(self.admin,'global',None,'a'*64,key).pk,hold.pk)
        with self.assertRaises(ValidationError):retention.create_hold(self.admin,'global',None,'b'*64,key)
        with self.assertRaises(PermissionDenied):retention.release_hold(self.admin,hold.pk,'b'*64)
        release=retention.release_hold(self.second,hold.pk,'b'*64)
        self.assertEqual(retention.release_hold(self.second,hold.pk,'b'*64).pk,release.pk)
        self.assertFalse(retention.active_holds().exists())

    def test_held_file_remains_protected_after_release(self):
        hold=self.hold();path=self.file()
        self.assertFalse(retention.cleanup_file(path,encounter_id=self.encounter.pk))
        record=PreservedFile.objects.get()
        self.assertEqual(record.sha256,hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(record.hold_ids,[str(hold.pk)])
        retention.release_hold(self.second,hold.pk,'b'*64)
        self.assertFalse(retention.cleanup_file(path));self.assertTrue(path.exists())
        self.assertEqual(PreservedFile.objects.count(),1)

    def test_unrelated_and_unattributed_files_are_distinguished(self):
        self.hold();other=self.file();unknown=self.file('submissions')
        self.assertTrue(retention.cleanup_file(other,encounter_id=self.other[5].pk))
        self.assertFalse(retention.cleanup_file(unknown));self.assertTrue(unknown.exists())

    def test_release_before_first_cleanup_preserves_existing_file(self):
        path=self.file();hold=self.hold()
        retention.release_hold(self.second,hold.pk,'b'*64)
        self.assertFalse(retention.cleanup_file(path,encounter_id=self.encounter.pk))
        self.assertTrue(path.exists());self.assertEqual(PreservedFile.objects.get().hold_ids,[str(hold.pk)])

    def test_preserved_prior_reference_survives_current_path_and_scope_change(self):
        path=self.file();relative=str(path.relative_to(settings.MEDIA_ROOT))
        job=Job.objects.create(encounter=self.encounter,user=self.scope[0],request_key='archived-file',input_path=relative)
        hold=self.hold();Job.objects.filter(pk=job.pk).update(input_path='audio/replacement.wav')
        retention.release_hold(self.second,hold.pk,'b'*64)
        self.assertFalse(retention.cleanup_file(path,encounter_id=self.other[5].pk))
        self.assertTrue(path.exists());self.assertEqual(PreservedFile.objects.get().hold_ids,[str(hold.pk)])

    def test_creation_ledger_distinguishes_new_files_from_pre_release_and_unknown_files(self):
        hold=self.hold()
        early=Path(self.temp.name)/'audio'/(uuid.uuid4().hex+'.wav');early.parent.mkdir(exist_ok=True)
        retention.begin_private_file(early);early.write_bytes(b'SYNTHETIC DURING HOLD')
        retention.release_hold(self.second,hold.pk,'b'*64)
        late=early.with_name(uuid.uuid4().hex+'.wav')
        retention.begin_private_file(late);late.write_bytes(b'SYNTHETIC AFTER RELEASE')
        # Timestamps are not provenance and cannot defeat the historical hold.
        import os;future=(timezone.now()+timedelta(days=1)).timestamp();os.utime(early,(future,future))
        self.assertFalse(retention.cleanup_file(early,encounter_id=self.encounter.pk))
        self.assertTrue(retention.cleanup_file(late,encounter_id=self.encounter.pk))
        unknown=self.file();self.assertFalse(retention.cleanup_file(unknown,encounter_id=self.encounter.pk))
        with self.assertRaises(ValidationError):retention.begin_private_file(late)

    def test_actual_upload_creation_records_release_boundary(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.security import store_upload,private_path
        hold=self.hold();retention.release_hold(self.second,hold.pk,'b'*64)
        relative=store_upload(SimpleUploadedFile('synthetic.wav',b'SYNTHETIC AUDIO'),'audio')
        birth=AuditEvent.objects.get(action='retention.file_creation',target=relative)
        self.assertEqual(birth.details['released_hold_ids'],[str(hold.pk)])
        self.assertTrue(retention.cleanup_file(private_path(relative),encounter_id=self.encounter.pk))

    def test_reapers_preserve_held_files_and_count_only_real_removals(self):
        self.hold();path=self.file();relative=str(path.relative_to(Path(self.temp.name)))
        event=AuditEvent.objects.create(action='voice.over_limit_quoted',target=str(self.encounter.pk),department=self.scope[2],details={'path':relative})
        # Audit is append-only; create an old clocked event instead of rewriting it.
        # Model auto_now_add is evaluated at insertion, so patch its shared clock.
        old=timezone.now()-timedelta(hours=2)
        with patch('django.utils.timezone.now',return_value=old):
            AuditEvent.objects.create(action='voice.over_limit_quoted',target=str(self.encounter.pk),department=self.scope[2],details={'path':relative})
        stray=self.file('submissions')
        import os;os.utime(stray,(old.timestamp(),old.timestamp()))
        self.assertEqual(reap_abandoned_voice_uploads(),0)
        self.assertTrue(path.exists());self.assertTrue(stray.exists())
        self.assertFalse(AuditEvent.objects.filter(action__in=['voice.over_limit_upload_removed','voice.stray_submission_removed']).exists())

    def test_unheld_expired_transient_reapers_still_work(self):
        path=self.file('submissions');old=(timezone.now()-timedelta(hours=2)).timestamp()
        import os;os.utime(path,(old,old))
        self.assertEqual(reap_stray_submissions(),1);self.assertFalse(path.exists())

    def test_durable_job_references_are_never_transient_cleanup(self):
        path=self.file();relative=str(path.relative_to(Path(self.temp.name)))
        Job.objects.create(encounter=self.encounter,user=self.scope[0],request_key='held-reference',input_path=relative)
        self.assertFalse(retention.cleanup_file(path));self.assertTrue(path.exists())

    def test_sql_cannot_modify_or_delete_preservation_evidence(self):
        self.hold();Encounter.objects.filter(pk=self.encounter.pk).update(notes='SYNTHETIC CHANGE')
        self.file();retention.cleanup_file(next(Path(self.temp.name).rglob('*.wav')))
        for table in ['core_retentionhold','core_preservedrecord','core_preservedfile']:
            for operation in [f'DELETE FROM {table}',f'TRUNCATE {table} CASCADE']:
                with self.subTest(operation=operation),self.assertRaises(DatabaseError),transaction.atomic():
                    with connection.cursor() as cursor:cursor.execute(operation)
        self.assertEqual(PreservedRecord.objects.count(),1);self.assertEqual(PreservedFile.objects.count(),1)

    def test_finalized_row_cannot_be_deleted_even_without_hold(self):
        Encounter.objects.filter(pk=self.encounter.pk).update(status='finalized',finalized_at=timezone.now())
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute('DELETE FROM core_encounter WHERE id=%s',[self.encounter.pk])
        self.assertTrue(Encounter.objects.filter(pk=self.encounter.pk).exists())

    def test_direct_insert_cannot_forge_staff_or_release_by_creator(self):
        with self.assertRaises(DatabaseError),transaction.atomic():
            RetentionHold.objects.create(scope='global',authority_sha256='a'*64,created_by=self.scope[0],request_key=uuid.uuid4())
        hold=self.hold()
        with self.assertRaises(DatabaseError),transaction.atomic():
            RetentionHoldRelease.objects.create(hold=hold,authority_sha256='b'*64,created_by=self.admin)

    def test_invalid_paths_and_database_failure_preserve_bytes(self):
        path=self.file()
        with patch.object(retention,'lock_preservation',side_effect=DatabaseError('PRIVATE ERROR')):
            with self.assertLogs('core.retention',level='ERROR') as log:
                self.assertFalse(retention.cleanup_file(path))
        self.assertTrue(path.exists());self.assertNotIn('PRIVATE ERROR',' '.join(log.output))
        link=path.parent/'link.wav';link.symlink_to(path)
        with self.assertRaises(ValidationError):retention.cleanup_file(link)
        with self.assertRaises(ValidationError):retention.cleanup_file('/etc/passwd')

    def login_admin(self):
        device=TOTPDevice.objects.create(user=self.admin,name='Synthetic',confirmed=True)
        self.client.force_login(self.admin);session=self.client.session;session['otp_device_id']=device.persistent_id;session.save()

    def test_authenticated_mfa_api_and_duplicate_payload(self):
        self.login_admin();payload={'scope':'patient','target':str(self.scope[3].pk),'authority_sha256':'a'*64,'request_key':str(uuid.uuid4())}
        response=self.client.post('/console/retention/holds/',json.dumps(payload),content_type='application/json')
        self.assertEqual(response.status_code,200,response.content);self.assertFalse(response.json()['purge_authorized'])
        self.assertEqual(self.client.post('/console/retention/holds/',json.dumps(payload),content_type='application/json').json(),response.json())
        bad=json.dumps(payload)[:-1]+',"scope":"global"}'
        self.assertEqual(self.client.post('/console/retention/holds/',bad,content_type='application/json').status_code,400)
        self.assertEqual(RetentionHold.objects.count(),1)

    def test_clinician_or_unverified_admin_cannot_register_hold(self):
        for user in [self.scope[0],self.admin]:
            self.client.force_login(user)
            response=self.client.post('/console/retention/holds/','{}',content_type='application/json')
            self.assertIn(response.status_code,[302,404]);self.assertFalse(RetentionHold.objects.exists())

    def test_real_html_forms_require_csrf_confirmation_and_show_preservation_state(self):
        self.client=Client(enforce_csrf_checks=True);self.login_admin()
        with override_settings(ADMIN_SITE=True):
            page=self.client.get('/console/retention/')
            self.assertEqual(page.status_code,200);self.assertContains(page,'Preservation holds')
            payload={'action':'create','scope':'patient','target':str(self.scope[3].pk),'authority_sha256':'a'*64,
                     'request_key':str(uuid.uuid4()),'confirmed':'on'}
            self.assertEqual(self.client.post('/console/retention/',payload).status_code,403)
            payload['csrfmiddlewaretoken']=self.client.cookies[settings.CSRF_COOKIE_NAME].value
            unconfirmed={**payload,'confirmed':''}
            self.assertEqual(self.client.post('/console/retention/',unconfirmed).status_code,200)
            self.assertFalse(RetentionHold.objects.exists())
            self.assertEqual(self.client.post('/console/retention/',payload).status_code,302)
            page=self.client.get('/console/retention/')
            self.assertContains(page,'Active');self.assertContains(page,str(RetentionHold.objects.get().pk))
            self.assertNotContains(page,self.encounter.notes);self.assertNotContains(page,self.scope[3].display_name)
            import os
            if directory:=os.getenv('QUILLMD_RETENTION_ARTIFACT_DIR'):
                target=Path(directory);target.mkdir(parents=True,exist_ok=True)
                (target/'preservation-admin.html').write_bytes(page.content)

    def test_held_scope_cannot_be_moved_and_raw_truncate_is_refused(self):
        self.hold()
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('UPDATE core_patient SET department_id=%s WHERE id=%s',[self.other[2].pk,self.scope[3].pk])
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute('TRUNCATE core_encounter CASCADE')

    def test_release_does_not_remove_prior_record_evidence_and_reverse_refuses_it(self):
        hold=self.hold();Encounter.objects.filter(pk=self.encounter.pk).update(notes='SYNTHETIC LATER')
        retention.release_hold(self.second,hold.pk,'b'*64)
        before=list(PreservedRecord.objects.values())
        Encounter.objects.filter(pk=self.encounter.pk).update(notes='SYNTHETIC LATER AGAIN')
        self.assertEqual(list(PreservedRecord.objects.values()),before)
        import importlib
        reverse=importlib.import_module('core.migrations.0025_preservation_guards').REVERSE
        with self.assertRaises(DatabaseError),transaction.atomic():
            with connection.cursor() as cursor:cursor.execute(reverse)
        self.assertEqual(list(PreservedRecord.objects.values()),before)


class PreservationConcurrency(Fixture,TransactionTestCase):
    def setUp(self):self.setup_records()

    def test_committed_hold_wins_before_waiting_clinical_write(self):
        entered=threading.Event();release=threading.Event()
        def holding():
            try:
                with transaction.atomic():
                    retention.create_hold(self.admin,'global',None,'a'*64,uuid.uuid4())
                    entered.set();self.assertTrue(release.wait(5))
            finally:connections.close_all()
        def updating():
            try:Encounter.objects.filter(pk=self.encounter.pk).update(notes='SYNTHETIC CONCURRENT')
            finally:connections.close_all()
        with ThreadPoolExecutor(2) as pool:
            first=pool.submit(holding);self.assertTrue(entered.wait(5))
            second=pool.submit(updating)
            import time;time.sleep(.15);self.assertFalse(second.done())
            release.set();first.result(5);second.result(5)
        self.assertEqual(PreservedRecord.objects.get().prior_record['notes'],self.encounter.notes)
