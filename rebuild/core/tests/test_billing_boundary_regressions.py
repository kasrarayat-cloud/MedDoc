"""Regressions for the refutation findings against the billing boundary (2026-09-18).

Each test asserts the CORRECT behaviour for a scenario a refuter demonstrated to be wrong in 345e61dd/061bf1f4:
output QuillMD cannot use is a platform failure whatever the user did meanwhile; charged declines are disclosed before a
further request; output is delivered only for requests that stand charged; nothing billable happened means nothing held;
a failed request can be retried; cancellation never deadlocks; the doctor reads classifications in words.

All data is synthetic. No provider, payment or console request leaves the test database.
"""
import json
import os
import tempfile
import threading
import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core import generation
from core import jobs as jobs_module
from core.billing import reserve
from core.jobs import CANCEL_REFUSALS, cancel, enqueue, run_one
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, Encounter, Job, LedgerEntry, Membership, PlatformCost, ProviderReceipt, Reservation, Usage, User, Wallet
from core.security import private_path
from core.tests.test_billing_boundary import (CANCEL_BUTTON, GENERATION_DISCLOSURE, LIVE, VOICE_DISCLOSURE, BoundaryFixture,
                                              adopted_live_result, deepgram)
from core.tests.test_billing_policy import STORAGES, unadopted_live_result
from core.tests.test_security import SyntheticFixture
from core.tests.audio_fixtures import wav_bytes

VOICE_ENV={'QUILLMD_DEEPGRAM_RATE_PER_MINUTE':'0.006','QUILLMD_DEEPGRAM_RATE_PER_SECOND':'','QUILLMD_VOICE_MAX_COST':'0.20',
           'QUILLMD_PROVIDER_DISCOUNT_RATE':'0','DEEPGRAM_API_KEY':'synthetic-placeholder-not-a-key'}
TRANSCRIPT='Synthetic complete visit transcript: patient reports intermittent headache for three days.'


class RegressionFixture(BoundaryFixture):
    def set_active(self,active):
        Membership.objects.filter(user=self.user,department=self.encounter.department).update(active=active)

    def recording(self,key):
        path=private_path(f'uploads/{key}.wav');path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(wav_bytes(tag=key))
        return f'uploads/{key}.wav'

    def run_transcription(self,key,response=None,env=None,side_effect=None):
        with patch.dict(os.environ,env or VOICE_ENV):
            job=enqueue(self.encounter,self.user,kind='transcription',input_path=self.recording(key))
            with patch('core.jobs.httpx.post',return_value=response,side_effect=side_effect) as post:self.assertTrue(run_one())
        job.refresh_from_db();return job,post

    def download_status(self,job):
        return self.client.get(f'/jobs/{job.pk}/result/').status_code

    def assert_absorbed_platform_failure(self,job):
        self.assertEqual(job.state,'failed');self.assertTrue(job.error.startswith('platform_failure: '),job.error)
        usage=Usage.objects.get(job=job,simulated=False)
        self.assertEqual(LedgerEntry.objects.get(job=job,kind='absorbed').amount,usage.charged_cost)
        self.assertTrue(PlatformCost.objects.filter(job=job,kind='absorbed_failure').exists())
        self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        self.assertEqual(AuditEvent.objects.get(action='job.failed',target=str(job.pk)).details['billing'],'platform_failure')
        self.assertTrue(audit_report()['all_checks_pass'])


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class UnusableOutputIsAPlatformFailureWhateverTheUserDid(RegressionFixture,TestCase):
    def test_invalid_generation_output_with_access_revoked_mid_run_is_absorbed(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='regression-invalid-revoked')
        reserve(job,Decimal('0.2'))
        result=unadopted_live_result(self.encounter.notes,'req_regression_invalid_revoked')
        def provider(*args,**kwargs):
            self.set_active(False);return result
        with patch('core.jobs.generation.generate',side_effect=provider):self.assertTrue(run_one())
        job.refresh_from_db();self.assert_absorbed_platform_failure(job)

    def test_invalid_generation_output_with_source_edited_mid_run_is_absorbed(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='regression-invalid-edited',revision=self.encounter.revision)
        reserve(job,Decimal('0.2'))
        result=unadopted_live_result(self.encounter.notes,'req_regression_invalid_edited')
        def provider(*args,**kwargs):
            Encounter.objects.filter(pk=self.encounter.pk).update(revision=self.encounter.revision+1);return result
        with patch('core.jobs.generation.generate',side_effect=provider):self.assertTrue(run_one())
        job.refresh_from_db();self.assert_absorbed_platform_failure(job)

    def test_unusable_transcript_with_access_revoked_mid_run_is_absorbed(self):
        def revoked(*args,**kwargs):
            self.set_active(False);return deepgram(None,'dg_regression_unusable_revoked')
        job,_=self.run_transcription('unusable-revoked',side_effect=revoked)
        self.assert_absorbed_platform_failure(job)

    def test_usable_output_with_access_revoked_mid_run_stays_charged(self):
        """Control: the reorder must not turn a genuine user-side decline into an absorption."""
        job=self.live_job('req_regression_usable_revoked',side_effect=lambda:self.set_active(False))
        self.assertEqual(job.state,'failed');self.assertTrue(job.error.startswith('not_adopted: '),job.error)
        self.assertFalse(LedgerEntry.objects.filter(job=job,kind='absorbed').exists())
        self.assertLess(self.balances()[0],Decimal('10'))


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class OutputIsDeliveredOnlyForChargedRequests(RegressionFixture,TestCase):
    def test_a_recording_is_never_refused_on_an_estimate_of_its_transcript_length(self):
        """The notes check happens on the real transcript: a short one fits nearly full notes and is added."""
        self.client.force_login(self.user)
        base='Symptoms: no chest pain\n';padded=base+'P'*(49000-len(base))
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/notes/',{'revision':self.encounter.revision,'notes':padded}).status_code,302)
        job,post=self.run_transcription('near-full',deepgram(TRANSCRIPT,'dg_regression_near_full'))
        self.assertEqual(post.call_count,1);self.assertEqual(job.state,'succeeded')
        self.encounter.refresh_from_db();self.assertIn(TRANSCRIPT,self.encounter.notes)

    def test_an_overflowing_transcript_is_delivered_and_stays_charged_never_free(self):
        """The real transcript does not fit the notes: it is not discarded and not free; it is charged within the limit and downloadable."""
        self.client.force_login(self.user)
        base='Symptoms: no chest pain\n';padded=base+'P'*(49960-len(base))
        self.assertEqual(self.client.post(f'/encounters/{self.encounter.pk}/notes/',{'revision':self.encounter.revision,'notes':padded}).status_code,302)
        job,post=self.run_transcription('overflow',deepgram(TRANSCRIPT,'dg_regression_overflow'))
        self.assertEqual(post.call_count,1);self.assertEqual(job.state,'failed');self.assertTrue(job.error.startswith('not_adopted: '),job.error)
        charged=Usage.objects.get(job=job).charged_cost;self.assertGreater(charged,0)
        self.assertFalse(LedgerEntry.objects.filter(job=job,kind='absorbed').exists());self.assertFalse(PlatformCost.objects.filter(job=job).exists())
        self.assertEqual(self.balances(),(Decimal('10')-charged,Decimal('0')));self.assertTrue(audit_report()['all_checks_pass'])
        self.encounter.refresh_from_db();self.assertNotIn(TRANSCRIPT,self.encounter.notes)
        page=self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertContains(page,f'/jobs/{job.pk}/result/');self.assertContains(page,'download it from the document record')
        response=self.client.get(f'/jobs/{job.pk}/result/');self.assertEqual(response.status_code,200)
        self.assertEqual(json.loads(b''.join(response.streaming_content))['transcript'],TRANSCRIPT)

    def test_cost_above_the_approved_limit_is_capped_absorbed_and_delivered(self):
        """The provider bills far more audio than we measured: the customer pays the limit, QuillMD absorbs the rest."""
        self.client.force_login(self.user)
        job,post=self.run_transcription('long',deepgram(TRANSCRIPT,'dg_regression_long',duration=6000))
        self.assertEqual(post.call_count,1);self.assertEqual(job.state,'succeeded')
        limit=Decimal(job.config['charge_limit']);usage=Usage.objects.get(job=job)
        self.assertEqual(usage.actual_cost,Decimal('0.6'));self.assertEqual(usage.charged_cost,limit)
        self.assertEqual(PlatformCost.objects.get(job=job,kind='absorbed_over_limit').amount,Decimal('0.9')-limit)
        self.assertEqual(self.balances(),(Decimal('10')-limit,Decimal('0')))
        self.encounter.refresh_from_db();self.assertIn(TRANSCRIPT,self.encounter.notes)
        self.assertEqual(self.download_status(job),200)
        report=audit_report();row=[r for r in report['rows'] if r['job_id']==str(job.pk)][0]
        self.assertTrue(report['all_checks_pass'],row['checks']);self.assertTrue(row['checks']['over_limit_absorbed_exactly'])

    def test_succeeded_and_declined_outputs_remain_downloadable(self):
        self.client.force_login(self.user)
        succeeded=self.live_job('req_regression_download_ok')
        self.assertEqual(succeeded.state,'succeeded');self.assertEqual(self.download_status(succeeded),200)
        self.encounter.refresh_from_db();self.encounter.answers={};self.encounter.save(update_fields=['answers'])
        Encounter.objects.filter(pk=self.encounter.pk).update(revision=self.encounter.revision+1);self.encounter.refresh_from_db()
        declined=self.live_job('req_regression_download_declined',side_effect=lambda:self.set_active(False))
        self.set_active(True)
        self.assertTrue(declined.error.startswith('not_adopted: '));self.assertEqual(self.download_status(declined),200)


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class NothingBillableMeansNothingHeld(RegressionFixture,TestCase):
    def test_missing_transcription_key_fails_before_any_request_and_releases_the_hold(self):
        self.client.force_login(self.user)
        job,post=self.run_transcription('no-key',deepgram(TRANSCRIPT,'dg_regression_nokey'),env={**VOICE_ENV,'DEEPGRAM_API_KEY':''})
        self.assertEqual(post.call_count,0);self.assertFalse(ProviderReceipt.objects.filter(job=job).exists())
        self.assertEqual(job.state,'failed');self.assertTrue(job.error.startswith('Not processed: Transcription provider is not connected.'),job.error)
        self.assertEqual(Reservation.objects.get(job=job).state,'released')
        self.promo.refresh_from_db();self.assertEqual(self.promo.reserved,0);self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        self.assertEqual(AuditEvent.objects.get(action='job.failed',target=str(job.pk)).details['billing'],'not_processed')
        self.encounter.refresh_from_db()
        edited=self.client.post(f'/encounters/{self.encounter.pk}/notes/',{'revision':self.encounter.revision,'notes':'Symptoms: edited'})
        self.assertEqual(edited.status_code,302)
        report=audit_report();self.assertTrue(report['all_checks_pass']);self.assertEqual(report['unresolved_jobs'],[])

    def test_missing_recording_fails_before_any_request_and_releases_the_hold(self):
        with patch.dict(os.environ,VOICE_ENV):
            job=enqueue(self.encounter,self.user,kind='transcription',input_path=self.recording('vanished'))
            private_path(job.input_path).unlink()
            with patch('core.jobs.httpx.post') as post:self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(post.call_count,0);self.assertEqual(job.state,'failed')
        self.assertTrue(job.error.startswith('Not processed: The recording is not available.'),job.error)
        self.assertEqual(Reservation.objects.get(job=job).state,'released')

    def test_a_transport_failure_after_the_request_is_still_held_for_reconciliation(self):
        """Control: once the request may have reached the provider the outcome stays uncertain and funds stay held."""
        job,post=self.run_transcription('timeout',side_effect=TimeoutError('synthetic timeout'))
        self.assertEqual(post.call_count,1);self.assertEqual(job.state,'reconciliation')
        self.assertEqual(job.error,'Provider outcome is uncertain; reconcile before retrying.')
        self.assertEqual(Reservation.objects.get(job=job).state,'held')

    def test_fixture_decline_reports_recorded_usage_not_a_charge(self):
        with self.settings(AI_MODE='fixture'):
            self.encounter.answers={};self.encounter.save(update_fields=['answers'])
            job=enqueue(self.encounter,self.user)
            def revoke(*args,**kwargs):
                self.set_active(False);return original(*args,**kwargs)
            original=generation.generate
            with patch('core.jobs.generation.generate',side_effect=revoke):self.assertTrue(run_one())
        job.refresh_from_db()
        self.assertEqual(job.state,'failed');self.assertIn('recorded usage stays billed',job.error);self.assertNotIn('remains charged',job.error)
        self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class ChargedDeclinesAreDisclosedAndFailuresCanBeRetried(RegressionFixture,TestCase):
    def declined_generation(self):
        self.encounter.answers={};self.encounter.save(update_fields=['answers'])
        job=self.live_job('req_regression_declined',side_effect=lambda:self.set_active(False))
        self.assertTrue(job.error.startswith('not_adopted: '));self.set_active(True)
        return job

    def test_a_charged_decline_discloses_the_next_generation_as_additional(self):
        self.declined_generation()
        self.client.force_login(self.user);url=f'/encounters/{self.encounter.pk}/'
        page=self.client.get(url)
        self.assertEqual(page.context['prior_generations'],1);self.assertContains(page,GENERATION_DISCLOSURE)

    def test_a_charged_decline_discloses_the_next_recording_as_additional(self):
        def revoked(*args,**kwargs):
            self.set_active(False);return deepgram('synthetic transcript','dg_regression_declined')
        job,_=self.run_transcription('declined',side_effect=revoked)
        self.assertTrue(job.error.startswith('not_adopted: '));self.set_active(True)
        self.client.force_login(self.user)
        page=self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertEqual(page.context['prior_transcriptions'],1);self.assertContains(page,VOICE_DISCLOSURE)

    def test_the_doctor_reads_classifications_in_words(self):
        self.declined_generation()
        self.client.force_login(self.user)
        page=self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertNotContains(page,'not_adopted:');self.assertContains(page,'Access was revoked before the output could be adopted')
        Encounter.objects.filter(pk=self.encounter.pk).update(revision=self.encounter.revision+5)
        self.encounter.refresh_from_db()
        failed=enqueue(self.encounter,self.user)
        with patch('core.jobs.generation.generate',return_value=unadopted_live_result(self.encounter.notes,'req_regression_words')):self.assertTrue(run_one())
        page=self.client.get(f'/encounters/{self.encounter.pk}/')
        self.assertNotContains(page,'platform_failure:');self.assertContains(page,'This was a platform failure; it is not charged to you.')

    def test_a_request_can_be_retried_after_an_absorbed_platform_failure(self):
        self.encounter.answers={};self.encounter.save(update_fields=['answers'])
        failed=enqueue(self.encounter,self.user)
        with patch('core.jobs.generation.generate',return_value=unadopted_live_result(self.encounter.notes,'req_regression_retry_bad')):self.assertTrue(run_one())
        failed.refresh_from_db();self.assert_absorbed_platform_failure(failed)
        key=f'generation:{self.encounter.pk}:{self.encounter.revision}'
        self.assertEqual(failed.request_key,f'{key}:failed:{failed.pk.hex}')
        self.client.force_login(self.user);url=f'/encounters/{self.encounter.pk}/'
        page=self.client.get(url)
        self.assertEqual(self.client.post(url+'generate/',{'usage_quote':page.context['usage_quote']}).status_code,302)
        retry=Job.objects.exclude(pk=failed.pk).get(encounter=self.encounter)
        self.assertEqual(retry.state,'queued');self.assertEqual(retry.request_key,key)
        with patch('core.jobs.generation.generate',return_value=adopted_live_result(self.encounter.notes,self.encounter.template_version.fields,'req_regression_retry_ok')):
            self.assertTrue(run_one())
        retry.refresh_from_db();self.assertEqual(retry.state,'succeeded')
        # Charged once, for the success only; the failure stays absorbed.
        self.assertEqual(sum(e.amount for e in LedgerEntry.objects.filter(kind__in=['usage','absorbed'])),-Usage.objects.get(job=retry).charged_cost)
        self.assertTrue(audit_report()['all_checks_pass'])
        # A second submit for the same revision returns the same job rather than charging again.
        self.assertEqual(enqueue(self.encounter,self.user).pk,retry.pk)

    def test_the_cancel_button_is_offered_only_to_members_the_server_allows(self):
        job=enqueue(self.encounter,self.user)
        self.client.force_login(self.user);self.assertContains(self.client.get(f'/encounters/{self.encounter.pk}/'),CANCEL_BUTTON)
        for role,allowed in (('employee',False),('manager',False),('clinician',True)):
            with self.subTest(role=role):
                member=User.objects.create_user(username=f'regression-{role}',email=f'regression-{role}@synthetic.invalid',verified_at=timezone.now())
                Membership.objects.create(user=member,department=self.encounter.department,role=role)
                self.client.force_login(member)
                page=self.client.get(f'/encounters/{self.encounter.pk}/')
                (self.assertContains if allowed else self.assertNotContains)(page,CANCEL_BUTTON)


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class AuditCoversCancelledJobs(RegressionFixture,TestCase):
    def test_a_cancelled_job_with_usage_or_held_funds_fails_the_audit(self):
        job=enqueue(self.encounter,self.user);cancel(job,self.user)
        report=audit_report();self.assertTrue(report['all_checks_pass']);self.assertEqual(report['cancellation_policy']['cancelled_jobs'],1)
        held=Reservation.objects.get(job=job);Reservation.objects.filter(pk=held.pk).update(state='held')
        Wallet.objects.filter(pk=held.wallet_id).update(reserved=held.amount)
        report=audit_report()
        self.assertFalse(report['cancellation_policy']['checks']['cancelled_jobs_hold_no_funds']);self.assertFalse(report['all_checks_pass'])


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class CancellationNeverDeadlocks(SyntheticFixture,TransactionTestCase):
    def setUp(self):
        if connection.vendor!='postgresql':self.skipTest('Row-lock ordering requires PostgreSQL')
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        override=override_settings(MEDIA_ROOT=Path(directory.name));override.enable();self.addCleanup(override.disable)
        self.scope=self.make_scope('regression-cancel-lock');self.user=self.scope[0];self.encounter=self.scope[5]

    def in_thread(self,operation):
        outcome={}
        def run():
            close_old_connections()
            try:outcome['value']=operation()
            except BaseException as error:outcome['error']=error
            finally:connections.close_all()
        thread=threading.Thread(target=run,daemon=True);thread.start();return thread,outcome

    def deadlock_timeout_seconds(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT setting::int FROM pg_settings WHERE name='deadlock_timeout'");return cursor.fetchone()[0]/1000

    def cancel_during_adoption(self,extra_pause):
        job=enqueue(self.encounter,self.user)
        original_validated=generation.validated
        adopting=threading.Event()
        def paused_validated(result):
            adopting.set();time.sleep(0.5+extra_pause);return original_validated(result)
        result=adopted_live_result(self.encounter.notes,self.encounter.template_version.fields,'req_regression_cancel_lock')
        browser=Client();browser.force_login(self.user)
        with patch('core.jobs.generation.generate',return_value=result),patch('core.jobs.generation.validated',side_effect=paused_validated):
            worker,worker_outcome=self.in_thread(run_one)
            self.assertTrue(adopting.wait(timeout=30))
            canceller,cancel_outcome=self.in_thread(lambda:browser.post(f'/encounters/{self.encounter.pk}/jobs/{job.pk}/cancel/'))
            worker.join(timeout=60);canceller.join(timeout=60)
        self.assertFalse(worker.is_alive());self.assertFalse(canceller.is_alive())
        if 'error' in worker_outcome:raise worker_outcome['error']
        self.assertNotIn('error',cancel_outcome,cancel_outcome.get('error'))
        job.refresh_from_db();return job,cancel_outcome['value']

    def test_cancel_during_adoption_answers_409_and_the_generation_stands(self):
        job,response=self.cancel_during_adoption(0)
        self.assertEqual(response.status_code,409);self.assertEqual(response.content.decode(),CANCEL_REFUSALS['running'])
        self.assertEqual(job.state,'succeeded');self.assertFalse(LedgerEntry.objects.filter(kind='absorbed').exists())

    def test_a_slow_adoption_is_never_the_deadlock_victim(self):
        job,response=self.cancel_during_adoption(self.deadlock_timeout_seconds()+0.75)
        self.assertEqual(response.status_code,409);self.assertEqual(job.state,'succeeded')
        self.assertFalse(PlatformCost.objects.exists());self.assertFalse(LedgerEntry.objects.filter(kind='absorbed').exists())

    def test_cancel_and_a_request_on_another_encounter_of_the_same_wallet_both_complete(self):
        other=Encounter.objects.create(department=self.encounter.department,patient=self.encounter.patient,
            template_version=self.encounter.template_version,created_by=self.user,notes='Symptoms: no chest pain')
        job=enqueue(self.encounter,self.user)
        original_release=jobs_module.release
        holding=threading.Event()
        def paused_release(target):
            holding.set();time.sleep(0.5+self.deadlock_timeout_seconds());return original_release(target)
        with patch('core.jobs.release',side_effect=paused_release):
            canceller,cancel_outcome=self.in_thread(lambda:cancel(Job.objects.get(pk=job.pk),self.user))
            self.assertTrue(holding.wait(timeout=30))
            requester,request_outcome=self.in_thread(lambda:enqueue(Encounter.objects.get(pk=other.pk),self.user))
            canceller.join(timeout=60);requester.join(timeout=60)
        self.assertNotIn('error',cancel_outcome,cancel_outcome.get('error'));self.assertNotIn('error',request_outcome,request_outcome.get('error'))
        job.refresh_from_db();self.assertEqual(job.state,'cancelled');self.assertEqual(request_outcome['value'].state,'queued')


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class RoundTwoRegressions(RegressionFixture,TestCase):
    password='Synthetic-console-regression-5521!'

    def admin_client(self):
        from django_otp.oath import totp
        from django_otp.plugins.otp_totp.models import TOTPDevice
        admin=User.objects.create_user(username='regression-admin',email='regression-admin@synthetic.invalid',password=self.password,verified_at=timezone.now(),is_staff=True)
        device=TOTPDevice.objects.create(user=admin,confirmed=True,name='Synthetic authenticator')
        code=str(totp(device.bin_key,step=device.step,t0=device.t0,digits=device.digits)).zfill(6)
        client=Client()
        self.assertEqual(client.post('/login/',{'email':admin.email,'password':self.password,'otp':code}).status_code,302)
        return client

    def test_a_failed_release_never_leaves_a_job_claiming_its_hold_was_released(self):
        with patch.dict(os.environ,{**VOICE_ENV,'DEEPGRAM_API_KEY':''}):
            job=enqueue(self.encounter,self.user,kind='transcription',input_path=self.recording('release-fails'))
            with patch('core.jobs.release',side_effect=RuntimeError('synthetic release failure')),self.assertRaises(RuntimeError):
                run_one()
        job.refresh_from_db()
        self.assertEqual(job.state,'running');self.assertNotIn('released',job.error)
        self.assertEqual(Reservation.objects.get(job=job).state,'held')
        self.assertIn(str(job.pk),[str(row['id']) for row in audit_report()['unresolved_jobs']])

    def test_an_ended_job_that_still_holds_funds_fails_the_audit(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='regression-ended-holding')
        reserve(job,Decimal('0.1'))
        self.assertTrue(audit_report()['hold_policy']['checks']['ended_jobs_hold_no_funds'])
        Job.objects.filter(pk=job.pk).update(state='failed',error='Not processed: synthetic')
        report=audit_report()
        self.assertEqual(report['hold_policy']['ended_jobs_holding_funds'],[str(job.pk)]);self.assertFalse(report['all_checks_pass'])

    def test_an_administrator_resolution_frees_the_key_for_a_new_request(self):
        path=self.recording('resolved')
        with patch.dict(os.environ,VOICE_ENV):
            job=enqueue(self.encounter,self.user,kind='transcription',input_path=path)
            with patch('core.jobs.httpx.post',side_effect=TimeoutError('synthetic provider timeout')):self.assertTrue(run_one())
        job.refresh_from_db();self.assertEqual(job.state,'reconciliation');key=job.request_key
        resolved=self.admin_client().post(f'/console/jobs/{job.pk}/resolve/',{'outcome':'release_no_cost','evidence_note':'Synthetic resolution for the regression test'})
        self.assertEqual(resolved.status_code,302)
        job.refresh_from_db();self.assertEqual(job.state,'failed');self.assertEqual(job.request_key,f'{key}:failed:{job.pk.hex}')
        with patch.dict(os.environ,VOICE_ENV):
            again=enqueue(self.encounter,self.user,kind='transcription',input_path=path)
        self.assertNotEqual(again.pk,job.pk);self.assertEqual(again.state,'queued');self.assertEqual(again.request_key,key)
        self.assertTrue(audit_report()['all_checks_pass'])
