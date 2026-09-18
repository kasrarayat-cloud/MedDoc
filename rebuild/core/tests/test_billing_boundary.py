"""Owner-directed billing boundary: a successful, user-requested generation stays billable when the user declines its
output; post-settlement platform failures are absorbed; a queued request cancels free; duplicates never charge twice;
additional requests are disclosed as separately billable.

All data is synthetic. No provider, payment or console request leaves the test database.
"""
import json
import os
import tempfile
import threading
import time
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.db.models import F
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from core.billing import absorb_failed_job, reserve, settle
from core.jobs import CANCEL_REFUSALS, CANCELLED_ERROR, OVERFLOW_ERROR, cancel, enqueue, run_one
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, Encounter, Job, LedgerEntry, Membership, PlatformCost, Reservation, Usage, User, Wallet
from core.security import private_path
from core.tests.test_billing_policy import AUDITABLE_RATES, STORAGES, PolicyFixture, unadopted_live_result
from core.tests.test_security import SyntheticFixture
from core.tests.audio_fixtures import wav_bytes

LIVE={'AI_MODE':'live','AI_PROVIDER':'anthropic','AI_MODEL':'synthetic-model','AI_INPUT_RATE':'3','AI_OUTPUT_RATE':'15','AI_CACHED_RATE':'.3'}
GENERATION_DISCLOSURE='This is an additional generation for this document. Earlier generations remain charged; this request is charged separately at provider usage × 1.5.'
VOICE_DISCLOSURE='A previous transcription for this document succeeded and remains charged; this new recording is charged separately at provider usage × 1.5.'
CANCEL_BUTTON='Cancel queued request'


def adopted_live_result(notes,fields,request_id,cost=Decimal('0.1')):
    """A valid live provider result the worker adopts (tokens = cost × 1000 so the audit recomputes the estimate)."""
    response=SimpleNamespace(id=f'msg_{request_id}',stop_reason='end_turn',
        content=[SimpleNamespace(type='text',text=json.dumps({'fields':[{'key':'symptoms','quotes':['no chest pain'],'conflict':False}]}))],
        model_dump=lambda **kwargs:{'id':f'msg_{request_id}'})
    units={'input_tokens':int(Decimal(cost)*1000),'output_tokens':0,'cached_input_tokens':0,'cache_creation_tokens':0}
    return ({'anthropic_response':response,'notes':notes,'fields':fields},cost,units,AUDITABLE_RATES,'anthropic:synthetic-model',request_id,False)


def deepgram(transcript,request_id,duration=12.345678):
    channels=[{'alternatives':[{'transcript':transcript}]}] if transcript is not None else []
    data={'results':{'channels':channels},'metadata':{'duration':duration,'request_id':request_id}}
    return SimpleNamespace(raise_for_status=lambda:None,json=lambda:data)


class BoundaryFixture(PolicyFixture):
    VOICE_ENV={'QUILLMD_DEEPGRAM_RATE_PER_MINUTE':'0.006','QUILLMD_DEEPGRAM_RATE_PER_SECOND':'','DEEPGRAM_API_KEY':'synthetic-placeholder-not-a-key'}

    def cancel_url(self,job):
        return f'/encounters/{job.encounter_id}/jobs/{job.pk}/cancel/'

    def live_job(self,request_id,side_effect=None,cost=Decimal('0.1')):
        """Queue a live generation as the user does and run the worker once; `side_effect` runs while the provider is 'busy'."""
        job=enqueue(self.encounter,self.user)
        result=adopted_live_result(self.encounter.notes,self.encounter.template_version.fields,request_id,cost)
        def provider(*args,**kwargs):
            if side_effect:side_effect()
            return result
        with patch('core.jobs.generation.generate',side_effect=provider):self.assertTrue(run_one())
        job.refresh_from_db();return job

    def transcription_job(self,key,response):
        recording=private_path(f'uploads/{key}.wav');recording.parent.mkdir(parents=True,exist_ok=True);recording.write_bytes(wav_bytes(tag=key))
        with patch.dict(os.environ,self.VOICE_ENV):
            job=enqueue(self.encounter,self.user,kind='transcription',input_path=f'uploads/{key}.wav')
            with patch('core.jobs.httpx.post',return_value=response):self.assertTrue(run_one())
        job.refresh_from_db();return job

    def assert_charged_never_absorbed(self,job,charged):
        """One usage row, one debit, no reversal, no platform cost, audit green with the user-declined check."""
        self.assertEqual(Usage.objects.filter(job=job,simulated=False).count(),1)
        self.assertEqual(LedgerEntry.objects.filter(job=job,kind='usage').count(),1)
        self.assertEqual(LedgerEntry.objects.get(job=job,kind='usage').amount,-charged)
        self.assertFalse(LedgerEntry.objects.filter(kind='absorbed').exists());self.assertFalse(PlatformCost.objects.exists())
        self.assertFalse(Reservation.objects.filter(job=job,state='held').exists())
        self.assertEqual(self.balances(),(Decimal('10')-charged,Decimal('0')))
        report=audit_report();row=[r for r in report['rows'] if r['job_id']==str(job.pk)][0]
        self.assertTrue(report['all_checks_pass'],row['checks']);self.assertFalse(row['absorbed'])
        return row['checks']

    def assert_absorbed(self,job):
        """The settled charge is reversed in full and carried as a platform cost; audit green with the absorption check."""
        usage=Usage.objects.get(job=job,simulated=False)
        reversal=LedgerEntry.objects.get(job=job,kind='absorbed');self.assertEqual(reversal.amount,usage.charged_cost)
        self.assertEqual(PlatformCost.objects.get(job=job,kind='absorbed_failure').amount,usage.actual_cost)
        self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        report=audit_report();row=[r for r in report['rows'] if r['job_id']==str(job.pk)][0]
        self.assertTrue(report['all_checks_pass'],row['checks']);self.assertTrue(row['absorbed'])
        return row['checks']


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class SuccessfulGenerationStaysBillable(BoundaryFixture,TestCase):
    """Rule 1: the charge follows the successful generation, not what the clinician later does with its output."""

    def test_editing_then_discarding_the_output_leaves_usage_and_ledger_untouched(self):
        job=self.live_job('req_boundary_success')
        self.assertEqual(job.state,'succeeded');self.assertEqual(job.error,'')
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers['symptoms']['text'],'no chest pain')
        usage_before=list(Usage.objects.values_list('pk','charged_cost'));ledger_before=list(LedgerEntry.objects.order_by('created_at').values_list('key','amount'))
        self.client.force_login(self.user)
        url=f'/encounters/{self.encounter.pk}/'
        edited=self.client.post(url+'save/',{'revision':self.encounter.revision,'answer_symptoms':'clinician-edited value'})
        self.assertEqual(edited.status_code,302)
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers['symptoms']['text'],'clinician-edited value')
        discarded=self.client.post(url+'notes/',{'revision':self.encounter.revision,'notes':'Symptoms: replaced after review'})
        self.assertEqual(discarded.status_code,302)
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers,{})
        job.refresh_from_db();self.assertEqual(job.state,'succeeded')
        self.assertEqual(list(Usage.objects.values_list('pk','charged_cost')),usage_before)
        self.assertEqual(list(LedgerEntry.objects.order_by('created_at').values_list('key','amount')),ledger_before)
        self.assertFalse(LedgerEntry.objects.filter(kind='absorbed').exists());self.assertFalse(PlatformCost.objects.exists())
        self.assertEqual(self.balances(),(Decimal('9.85'),Decimal('0')))
        report=audit_report();checks=report['rows'][0]['checks']
        self.assertTrue(report['all_checks_pass'])
        self.assertNotIn('failed_settled_usage_absorbed',checks);self.assertNotIn('user_declined_output_remains_charged',checks)

    def test_source_revision_changed_while_running_is_billable_not_absorbed(self):
        original=Encounter.objects.get(pk=self.encounter.pk).answers
        job=self.live_job('req_boundary_revision',side_effect=lambda:Encounter.objects.filter(pk=self.encounter.pk).update(revision=F('revision')+1))
        self.assertEqual(job.state,'failed');self.assertTrue(job.error.startswith('not_adopted: '),job.error);self.assertLessEqual(len(job.error),250)
        self.assertIn('stays billed',job.error)
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers,original)
        checks=self.assert_charged_never_absorbed(job,Decimal('0.15'))
        self.assertTrue(checks['user_declined_output_remains_charged']);self.assertNotIn('failed_settled_usage_absorbed',checks)
        self.assertEqual(AuditEvent.objects.get(action='job.failed',target=str(job.pk)).details['billing'],'not_adopted')
        self.assertFalse(AuditEvent.objects.filter(action__in=['usage.absorbed','usage.absorb_failed']).exists())

    def test_finalized_while_running_is_billable_not_absorbed(self):
        job=self.live_job('req_boundary_finalized',side_effect=lambda:Encounter.objects.filter(pk=self.encounter.pk).update(status='finalized'))
        self.assertEqual(job.state,'failed');self.assertTrue(job.error.startswith('not_adopted: '),job.error)
        checks=self.assert_charged_never_absorbed(job,Decimal('0.15'))
        self.assertTrue(checks['user_declined_output_remains_charged'])

    def test_membership_revoked_at_adoption_is_billable_not_absorbed(self):
        job=self.live_job('req_boundary_revoked',side_effect=lambda:Membership.objects.filter(user=self.user,department=self.encounter.department).update(active=False))
        self.assertEqual(job.state,'failed');self.assertTrue(job.error.startswith('not_adopted: '),job.error)
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.status,'draft')
        checks=self.assert_charged_never_absorbed(job,Decimal('0.15'))
        self.assertTrue(checks['user_declined_output_remains_charged'])

    def test_absorbing_a_declined_generation_is_refused_by_the_writer_and_flagged_by_the_audit(self):
        job=self.live_job('req_boundary_violation',side_effect=lambda:Encounter.objects.filter(pk=self.encounter.pk).update(revision=F('revision')+1))
        self.assertTrue(job.error.startswith('not_adopted: '))
        with self.assertRaises(ValidationError):absorb_failed_job(job)
        self.assertFalse(LedgerEntry.objects.filter(kind='absorbed').exists());self.assertFalse(PlatformCost.objects.exists())
        # A defective writer that reverses the charge anyway is a policy violation the audit must report, not accept.
        self.promo.refresh_from_db();self.promo.balance+=Decimal('0.15');self.promo.save(update_fields=['balance'])
        LedgerEntry.objects.create(wallet=self.promo,amount=Decimal('0.15'),kind='absorbed',key=f'absorbed:{job.pk}:{self.promo.pk}',description='forbidden reversal',job=job,balance_after=self.promo.balance)
        PlatformCost.objects.create(job=job,kind='absorbed_failure',amount=Decimal('0.1'),description='forbidden',evidence_reference='synthetic')
        report=audit_report();row=[r for r in report['rows'] if r['job_id']==str(job.pk)][0]
        self.assertFalse(row['checks']['user_declined_output_remains_charged']);self.assertNotIn('failed_settled_usage_absorbed',row['checks'])
        self.assertFalse(report['all_checks_pass'])


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class PlatformFailuresAreAbsorbed(BoundaryFixture,TestCase):
    """Rule 2: everything else that fails after settlement is QuillMD's failure and is absorbed as before."""

    def test_invalid_provider_output_is_a_platform_failure(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='boundary-invalid')
        reserve(job,Decimal('0.2'))
        with patch('core.jobs.generation.generate',return_value=unadopted_live_result(self.encounter.notes,'req_boundary_invalid')):self.assertTrue(run_one())
        job.refresh_from_db();self.assertEqual(job.state,'failed')
        self.assertTrue(job.error.startswith('platform_failure: '),job.error);self.assertLessEqual(len(job.error),250)
        self.assertNotIn('not valid provider JSON',job.error)  # provider text never reaches a job record
        checks=self.assert_absorbed(job)
        self.assertTrue(checks['failed_settled_usage_absorbed']);self.assertNotIn('user_declined_output_remains_charged',checks)
        self.assertEqual(AuditEvent.objects.get(action='job.failed',target=str(job.pk)).details['billing'],'platform_failure')

    def test_unusable_transcript_is_a_platform_failure(self):
        job=self.transcription_job('unusable',deepgram(None,'dg_boundary_unusable'))
        self.assertEqual(job.state,'failed');self.assertEqual(job.error,'platform_failure: Provider supplied no usable transcript.')
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.notes,'Symptoms: no chest pain')
        checks=self.assert_absorbed(job);self.assertTrue(checks['failed_settled_usage_absorbed'])

    def test_transcript_over_the_note_limit_is_a_platform_failure(self):
        job=self.transcription_job('overflow',deepgram('x'*50000,'dg_boundary_overflow'))
        self.assertEqual(job.state,'failed');self.assertEqual(job.error,'platform_failure: '+OVERFLOW_ERROR)
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.notes,'Symptoms: no chest pain')
        checks=self.assert_absorbed(job);self.assertTrue(checks['failed_settled_usage_absorbed'])


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class QueuedRequestCancellation(BoundaryFixture,TestCase):
    """Rule 4: cancellation is free only while queued; anything later is billed by result."""

    def test_cancel_queued_releases_funds_records_no_usage_and_allows_a_new_request(self):
        job=enqueue(self.encounter,self.user)
        key=f'generation:{self.encounter.pk}:{self.encounter.revision}';self.assertEqual(job.request_key,key)
        held=Reservation.objects.get(job=job,state='held');self.promo.refresh_from_db();self.assertEqual(self.promo.reserved,held.amount)
        self.client.force_login(self.user)
        page=self.client.get(f'/encounters/{self.encounter.pk}/');self.assertContains(page,CANCEL_BUTTON)
        response=self.client.post(self.cancel_url(job));self.assertEqual(response.status_code,302)
        job.refresh_from_db()
        self.assertEqual(job.state,'cancelled');self.assertEqual(job.error,CANCELLED_ERROR);self.assertIsNotNone(job.finished_at);self.assertIsNone(job.started_at)
        self.assertEqual(job.request_key,f'{key}:cancelled:{job.pk.hex}')
        self.assertEqual(Reservation.objects.get(job=job).state,'released')
        self.promo.refresh_from_db();self.assertEqual(self.promo.reserved,0);self.assertEqual(self.promo.balance,Decimal('10'))
        self.assertFalse(Usage.objects.filter(job=job).exists());self.assertFalse(LedgerEntry.objects.filter(job=job).exists())
        self.assertTrue(AuditEvent.objects.filter(action='job.cancelled',target=str(job.pk),actor=self.user).exists())
        with patch('core.jobs.generation.generate') as provider:self.assertFalse(run_one())
        self.assertEqual(provider.call_count,0)
        report=audit_report();self.assertTrue(report['all_checks_pass']);self.assertEqual(report['unresolved_jobs'],[]);self.assertEqual(report['rows'],[])
        page=self.client.get(f'/encounters/{self.encounter.pk}/');self.assertNotContains(page,CANCEL_BUTTON)
        self.assertContains(page,'Cancelled before any provider request; nothing was charged.');self.assertNotContains(page,CANCELLED_ERROR)
        self.assertEqual(self.client.post(self.cancel_url(job)).status_code,409)
        # The cancelled row no longer holds the key: a fresh request for the same revision reserves again.
        again=enqueue(self.encounter,self.user)
        self.assertNotEqual(again.pk,job.pk);self.assertEqual(again.state,'queued');self.assertEqual(again.request_key,key)
        self.assertEqual(Reservation.objects.filter(state='held').count(),1);self.assertEqual(Reservation.objects.filter(job=again).count(),1)
        # Cancelling that one too keeps every historical row under a distinct key, and none of them is pending.
        cancel(again,self.user);again.refresh_from_db();self.assertEqual(again.request_key,f'{key}:cancelled:{again.pk.hex}')
        self.assertEqual(Job.objects.filter(encounter=self.encounter,state='cancelled').count(),2)
        notes=self.client.post(f'/encounters/{self.encounter.pk}/notes/',{'revision':self.encounter.revision,'notes':'Symptoms: edited after cancellation'})
        self.assertEqual(notes.status_code,302)
        self.promo.refresh_from_db();self.assertEqual(self.promo.reserved,0);self.assertTrue(audit_report()['all_checks_pass'])

    def test_cancelled_transcription_key_fits_the_column(self):
        recording=private_path('uploads/cancel.wav');recording.parent.mkdir(parents=True,exist_ok=True);recording.write_bytes(wav_bytes(tag='cancel'))
        with patch.dict(os.environ,self.VOICE_ENV):job=enqueue(self.encounter,self.user,kind='transcription',input_path='uploads/cancel.wav')
        self.assertEqual(len(job.request_key),115)
        cancel(job,self.user);job.refresh_from_db()
        self.assertEqual(job.state,'cancelled');self.assertEqual(len(job.request_key),158);self.assertLessEqual(len(job.request_key),Job._meta.get_field('request_key').max_length)
        self.assertEqual(Reservation.objects.get(job=job).state,'released');self.promo.refresh_from_db();self.assertEqual(self.promo.reserved,0)

    def test_cancel_refuses_every_state_past_queued_without_changing_it(self):
        self.client.force_login(self.user)
        for state,reason in CANCEL_REFUSALS.items():
            with self.subTest(state=state):
                job=Job.objects.create(encounter=self.encounter,user=self.user,request_key=f'boundary-{state}',state=state)
                reserve(job,Decimal('0.1'))
                response=self.client.post(self.cancel_url(job))
                self.assertEqual(response.status_code,409);self.assertEqual(response.content.decode(),reason)
                job.refresh_from_db();self.assertEqual(job.state,state);self.assertEqual(job.error,'')
                self.assertEqual(Reservation.objects.get(job=job).state,'held')
        self.assertEqual(CANCEL_REFUSALS['running'],'Processing already started; the outcome will be billed by result.')
        self.assertFalse(AuditEvent.objects.filter(action='job.cancelled').exists())
        # A settled success keeps its charge: 409, nothing released, nothing reversed.
        usage=self.settled(Decimal('0.5'),key='boundary-settled')
        self.assertEqual(self.client.post(self.cancel_url(usage.job)).status_code,409)
        self.assertEqual(self.balances(),(Decimal('9.25'),Decimal('0')));self.assertEqual(self.promo.reserved,Decimal('0.75'))
        # Another department's member cannot see the job at all (created directly: the running/reconciliation rows above block enqueue).
        queued=Job.objects.create(encounter=self.encounter,user=self.user,request_key='boundary-queued-foreign');reserve(queued,Decimal('0.1'))
        self.client.force_login(self.make_scope('boundary-other')[0])
        self.assertEqual(self.client.post(self.cancel_url(queued)).status_code,404)
        queued.refresh_from_db();self.assertEqual(queued.state,'queued')


    def test_only_the_requester_or_a_clinician_may_cancel(self):
        from core.models import Membership
        job=enqueue(self.encounter,self.user)
        employee=User.objects.create_user(username='boundary-employee',email='boundary-employee@synthetic.invalid',verified_at=timezone.now())
        Membership.objects.create(user=employee,department=self.encounter.department,role='employee')
        colleague=User.objects.create_user(username='boundary-colleague',email='boundary-colleague@synthetic.invalid',verified_at=timezone.now())
        Membership.objects.create(user=colleague,department=self.encounter.department,role='clinician')
        url=f'/encounters/{self.encounter.pk}/jobs/{job.pk}/cancel/'
        self.client.force_login(employee)
        self.assertEqual(self.client.post(url).status_code,403)
        job.refresh_from_db();self.assertEqual(job.state,'queued')
        self.client.force_login(colleague)
        self.assertEqual(self.client.post(url).status_code,302)
        job.refresh_from_db();self.assertEqual(job.state,'cancelled')
        self.assertTrue(AuditEvent.objects.filter(action='job.cancelled',actor=colleague,target=str(job.pk)).exists())


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class CancellationRace(SyntheticFixture,TransactionTestCase):
    """The worker's `select_for_update(skip_locked=True)` and the cancel's `select_for_update` contend for one row lock,
    so pickup and cancellation serialize: never both, never a double state."""

    def setUp(self):
        if connection.vendor!='postgresql':self.skipTest('Row-lock verification requires PostgreSQL')
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        override=override_settings(MEDIA_ROOT=Path(directory.name));override.enable();self.addCleanup(override.disable)
        self.scope=self.make_scope('boundary-race');self.user=self.scope[0];self.encounter=self.scope[5]
        self.client.force_login(self.user)

    def in_thread(self,operation):
        outcome={}
        def run():
            close_old_connections()
            try:outcome['value']=operation()
            except BaseException as error:outcome['error']=error
            finally:connections.close_all()
        thread=threading.Thread(target=run);thread.start();return thread,outcome

    def joined(self,thread,outcome):
        thread.join(timeout=20);self.assertFalse(thread.is_alive(),'thread did not finish')
        if 'error' in outcome:raise outcome['error']
        return outcome['value']

    def lock_waiters(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid() AND wait_event_type='Lock'")
            return cursor.fetchone()[0]

    def test_worker_pickup_wins_over_a_concurrent_cancel(self):
        job=enqueue(self.encounter,self.user)
        locked=threading.Event();proceed=threading.Event()
        def worker_first_transaction():
            # Exactly run_one's first transaction: lock the queued row with skip_locked, mark it running, hold the lock.
            with transaction.atomic():
                picked=Job.objects.select_for_update(skip_locked=True).filter(state='queued').order_by('created_at').first()
                picked.state='running';picked.started_at=timezone.now();picked.save(update_fields=['state','started_at'])
                locked.set()
                if not proceed.wait(timeout=20):raise AssertionError('cancel never arrived')
            return picked.pk
        worker,worker_outcome=self.in_thread(worker_first_transaction)
        self.assertTrue(locked.wait(timeout=20))
        # The row is provably locked by the worker ...
        with self.assertRaises(DatabaseError),transaction.atomic():Job.objects.select_for_update(nowait=True).get(pk=job.pk)
        # ... so a cancel submitted now waits on that lock instead of racing it, then reads the committed state.
        canceller,cancel_outcome=self.in_thread(lambda:self.client.post(f'/encounters/{self.encounter.pk}/jobs/{job.pk}/cancel/'))
        deadline=time.monotonic()+15
        while self.lock_waiters()<1 and time.monotonic()<deadline:time.sleep(0.02)
        self.assertEqual(self.lock_waiters(),1,'the cancel request must block on the worker\'s row lock')
        proceed.set()
        self.assertEqual(self.joined(worker,worker_outcome),job.pk)
        response=self.joined(canceller,cancel_outcome)
        self.assertEqual(response.status_code,409);self.assertEqual(response.content.decode(),CANCEL_REFUSALS['running'])
        job.refresh_from_db();self.assertEqual(job.state,'running');self.assertEqual(job.error,'')
        self.assertEqual(Reservation.objects.get(job=job).state,'held');self.assertFalse(AuditEvent.objects.filter(action='job.cancelled').exists())

    def test_a_cancel_in_progress_is_never_picked_up_by_the_worker(self):
        job=enqueue(self.encounter,self.user)
        with patch('core.jobs.generation.generate') as provider:
            with transaction.atomic():
                cancel(job,self.user)  # holds the row lock until this block commits
                worker,outcome=self.in_thread(run_one)
                self.assertFalse(self.joined(worker,outcome))  # skip_locked: the locked queued row is invisible to the worker
            worker,outcome=self.in_thread(run_one)
            self.assertFalse(self.joined(worker,outcome))
        self.assertEqual(provider.call_count,0)
        job.refresh_from_db();self.assertEqual(job.state,'cancelled');self.assertEqual(job.error,CANCELLED_ERROR)
        self.assertEqual(Reservation.objects.get(job=job).state,'released')
        self.assertEqual(Wallet.objects.get(user=self.user,kind='promo').reserved,0)


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class DuplicateProcessingNeverDuplicatesCharges(BoundaryFixture,TestCase):
    """Rule 5. The cross-job provider-identifier refusals are also covered by test_provider_dedup_refutation.ProviderDedupRefutation."""

    def test_two_enqueues_for_the_same_revision_return_one_job_and_reserve_once(self):
        first=enqueue(self.encounter,self.user);second=enqueue(self.encounter,self.user)
        self.assertEqual(first.pk,second.pk);self.assertEqual(Job.objects.filter(encounter=self.encounter).count(),1)
        self.assertEqual(Reservation.objects.filter(job=first).count(),1)
        self.promo.refresh_from_db();self.assertEqual(self.promo.reserved,Reservation.objects.get(job=first).amount)
        self.assertEqual(AuditEvent.objects.filter(action='usage.reserve',target=str(first.pk)).count(),1)
        self.assertEqual(AuditEvent.objects.filter(action='job.queued').count(),1)

    def test_settling_the_same_job_twice_creates_one_usage_and_one_debit(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='boundary-replay')
        reserve(job,Decimal('0.2'))
        units={'input_tokens':100,'output_tokens':0,'cached_input_tokens':0,'cache_creation_tokens':0}
        first=settle(job,Decimal('0.1'),units,AUDITABLE_RATES,'anthropic:synthetic-model','req_boundary_replay',provider_resource_id='msg_boundary_replay')
        replay=settle(job,Decimal('0.1'),units,AUDITABLE_RATES,'anthropic:synthetic-model','req_boundary_replay',provider_resource_id='msg_boundary_replay')
        self.assertEqual(first.pk,replay.pk);self.assertEqual(Usage.objects.count(),1)
        self.assertEqual(LedgerEntry.objects.filter(kind='usage').count(),1);self.assertEqual(self.balances(),(Decimal('9.85'),Decimal('0')))
        self.assertEqual(AuditEvent.objects.filter(action='usage.settle').count(),1)

    def test_a_duplicate_provider_request_id_across_jobs_is_refused_by_the_database(self):
        jobs=[Job.objects.create(encounter=self.encounter,user=self.user,request_key=f'boundary-dup-{index}') for index in range(2)]
        for job in jobs:reserve(job,Decimal('0.2'))
        units={'input_tokens':100,'output_tokens':0,'cached_input_tokens':0,'cache_creation_tokens':0}
        settle(jobs[0],Decimal('0.1'),units,AUDITABLE_RATES,'anthropic:synthetic-model','req_boundary_dup',provider_resource_id='msg_boundary_dup_a')
        with self.assertRaises(DatabaseError):
            settle(jobs[1],Decimal('0.1'),units,AUDITABLE_RATES,'anthropic:synthetic-model','req_boundary_dup',provider_resource_id='msg_boundary_dup_b')
        self.assertEqual(Usage.objects.count(),1);self.assertEqual(LedgerEntry.objects.filter(kind='usage').count(),1)
        self.assertEqual(self.balances(),(Decimal('9.85'),Decimal('0')))


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,**LIVE)
class AdditionalRequestDisclosure(BoundaryFixture,TestCase):
    """Rule 3: a further request after a successful one is disclosed as separately billable."""

    def test_generation_disclosure_appears_only_after_a_prior_success(self):
        self.encounter.answers={};self.encounter.save(update_fields=['answers'])
        self.client.force_login(self.user);url=f'/encounters/{self.encounter.pk}/'
        first=self.client.get(url)
        self.assertContains(first,'Generate supported answers');self.assertNotContains(first,GENERATION_DISCLOSURE);self.assertEqual(first.context['prior_generations'],0)
        job=self.live_job('req_boundary_disclosure');self.assertEqual(job.state,'succeeded')
        adopted=self.client.get(url)
        self.assertNotContains(adopted,'Generate supported answers');self.assertNotContains(adopted,GENERATION_DISCLOSURE)
        self.encounter.refresh_from_db()
        self.assertEqual(self.client.post(url+'notes/',{'revision':self.encounter.revision,'notes':'Symptoms: edited, needs a new draft'}).status_code,302)
        again=self.client.get(url)
        self.assertContains(again,'Generate supported answers');self.assertContains(again,GENERATION_DISCLOSURE);self.assertEqual(again.context['prior_generations'],1)
        self.assertNotContains(again,VOICE_DISCLOSURE)

    def test_voice_disclosure_appears_only_after_a_prior_transcription(self):
        self.client.force_login(self.user);url=f'/encounters/{self.encounter.pk}/'
        first=self.client.get(url)
        self.assertContains(first,'Transcribe recording');self.assertNotContains(first,VOICE_DISCLOSURE);self.assertEqual(first.context['prior_transcriptions'],0)
        job=self.transcription_job('disclosure',deepgram('synthetic transcript','dg_boundary_disclosure'))
        self.assertEqual(job.state,'succeeded')
        again=self.client.get(url)
        self.assertContains(again,VOICE_DISCLOSURE);self.assertEqual(again.context['prior_transcriptions'],1)
        self.assertNotContains(again,GENERATION_DISCLOSURE);self.assertEqual(again.context['prior_generations'],0)
