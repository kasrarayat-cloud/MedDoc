"""Actual PostgreSQL standing admission/accounting, without provider access."""
from decimal import Decimal
import uuid
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import connection, DatabaseError, transaction
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from core import billing, jobs, testing_authority as authority
from core.models import (Department, Encounter, Job, LedgerEntry, Membership, Organization,
    Patient, PreparationReceipt, ProviderReceipt, Reservation, Template, TemplatePreparation,
    TemplateVersion, TestingReservation, Usage, User, Wallet)
from core.tests.test_preparation_campaign_pg import DeliveryCampaignPostgresTests
from core.tests.test_testing_authority import SETTINGS


@override_settings(**SETTINGS)
class StandingAuthorityPostgresTests(TransactionTestCase):
    # Reuse only the direct-SQL encoder, never its finite admission assumptions.
    raw_insert=DeliveryCampaignPostgresTests.raw_insert
    refusal=DeliveryCampaignPostgresTests.refusal

    def setUp(self):
        if connection.vendor!='postgresql':self.skipTest('Requires actual PostgreSQL triggers.')
        self.organization=Organization.objects.create(name='Synthetic standing guard fixture')
        self.doctor=User.objects.create(id=next(iter(authority.ACTORS)),username='standing-synthetic',
            email='standing@example.invalid',is_active=True,verified_at=timezone.now())
        self.department=Department.objects.create(id=authority.ACTORS[str(self.doctor.pk)],
            organization=self.organization,name='Synthetic standing scope')
        Membership.objects.create(user=self.doctor,department=self.department,role='owner')
        self.patient=Patient.objects.create(department=self.department,created_by=self.doctor,
            display_name='Synthetic only',reference='standing-synthetic')

    def config(self,kind='preparation',**extra):
        return {**authority.active_config({'mode':'live','provider':'anthropic','model':SETTINGS['AI_MODEL']},kind),**extra}

    def template(self):
        return Template.objects.create(department=self.department,created_by=self.doctor,name='Authorized synthetic blank',
            format='docx',original_name='blank.docx',original_path='synthetic-not-read.docx',sha256='a'*64)

    def preparation(self,config=None):
        return self.raw_insert(TemplatePreparation,template=self.template(),requested_by=self.doctor,
            config=config if config is not None else self.config())

    def receipt(self,prep,role='proposer',**extra):
        return self.raw_insert(PreparationReceipt,preparation=prep,role=role,provider='anthropic',
            requested_model=SETTINGS['AI_MODEL'],request_sha256='b'*64,quote_maximum=extra.pop('quote_maximum',Decimal('2.50')),**extra)

    def encounter(self):
        version=TemplateVersion.objects.create(template=self.template(),number=1,created_by=self.doctor)
        return Encounter.objects.create(patient=self.patient,department=self.department,created_by=self.doctor,
            template_version=version,notes='Synthetic documented source only',service_date=timezone.now().date())

    def job(self,**extra):
        return self.raw_insert(Job,encounter=self.encounter(),user=extra.pop('user',self.doctor),
            request_key=str(uuid.uuid4()),config=extra.pop('config',self.config('generation',testing_quote_usd='2.500000000000')),**extra)

    def test_partial_mixed_unknown_scope_and_wrong_purpose_are_sql_refusals(self):
        for config in [{'testing_authority_id':authority.AUTHORITY_ID},
                {**self.config(),'testing_authority_sha256':'0'*64},
                {**self.config(),'campaign':'consumed-finite-approval'},
                {**self.config(),'testing_purpose':authority.PURPOSES['generation']}]:
            self.refusal(lambda:self.preparation(config))
        self.assertEqual(TemplatePreparation.objects.count(),0)

    def test_no_old_call_form_or_dollar_ceiling_and_original_identity_retained(self):
        for _ in range(16):
            prep=self.preparation()
            receipt=self.receipt(prep,state='unknown',finished_at=timezone.now())
            self.assertEqual(receipt.quote_maximum,Decimal('2.50'))
        self.assertEqual(TemplatePreparation.objects.count(),16)
        self.assertEqual(PreparationReceipt.objects.count(),16)
        self.assertEqual(sum(PreparationReceipt.objects.values_list('quote_maximum',flat=True)),Decimal('40'))

    def test_checker_requires_actual_success_and_no_unknown_role_is_replayed(self):
        prep=self.preparation()
        self.refusal(lambda:self.receipt(prep,'checker'))
        original=self.receipt(prep,state='unknown',finished_at=timezone.now())
        self.refusal(lambda:self.receipt(prep),'preparation_role_once')
        self.refusal(lambda:self.receipt(prep,'checker'))
        original.refresh_from_db();self.assertEqual(original.state,'unknown')
        succeeded=self.preparation();self.receipt(succeeded,state='succeeded',finished_at=timezone.now())
        self.receipt(succeeded,'checker',state='succeeded',finished_at=timezone.now())
        self.refusal(lambda:PreparationReceipt.objects.filter(preparation=succeeded).update(computed_cost=1))

    def test_legacy_unknown_hold_and_historical_caps_remain_untouched(self):
        old=self.preparation({'mode':'live','provider':'anthropic','model':'historical-label'})
        old_receipt=self.raw_insert(PreparationReceipt,preparation=old,role='proposer',provider='anthropic',
            requested_model='historical-label',request_sha256='c'*64,quote_maximum=Decimal('0.10'),
            state='unknown',finished_at=timezone.now())
        original=(old.config,old_receipt.state,old_receipt.quote_maximum,old_receipt.computed_cost)
        self.refusal(lambda:self.raw_insert(PreparationReceipt,preparation=old,role='checker',provider='anthropic',
            requested_model='historical-label',request_sha256='d'*64,quote_maximum=Decimal('0.17')))
        for _ in range(9):self.receipt(self.preparation())
        old.refresh_from_db();old_receipt.refresh_from_db()
        self.assertEqual((old.config,old_receipt.state,old_receipt.quote_maximum,old_receipt.computed_cost),original)
        self.assertEqual(PreparationReceipt.objects.get(pk=old_receipt.pk).quote_maximum,Decimal('0.10'))

    def test_enqueue_reserve_and_settle_without_wallet_fabrication(self):
        Wallet.objects.create(user=self.doctor,kind='promo',balance=0,reserved=0)
        Wallet.objects.create(user=self.doctor,kind='paid',balance=0,reserved=0)
        before=list(Wallet.objects.order_by('id').values())
        encounter=self.encounter()
        with patch('core.generation.maximum_cost',return_value=Decimal('2.5')):
            job=jobs.enqueue(encounter,self.doctor,config={'mode':'live','provider':'anthropic','model':SETTINGS['AI_MODEL']})
        row=TestingReservation.objects.get(job=job)
        self.assertEqual(row.quoted_provider_cost,Decimal('2.5'))
        self.assertEqual(row.state,'held')
        self.assertEqual(job.config['testing_authority_id'],authority.AUTHORITY_ID)
        units={'input_tokens':100000,'output_tokens':0,'cached_input_tokens':0}
        rates={'input_per_million':'1','output_per_million':'1','cached_per_million':'1'}
        ProviderReceipt.objects.create(job=job,provider='anthropic:returned-model',provider_request_id='standing-request',
            units=units,rates=rates,actual_cost=Decimal('0.1'))
        usage=billing.settle(job,Decimal('0.1'),units,rates,'anthropic:returned-model','standing-request')
        self.assertEqual(usage.actual_cost,Decimal('0.1'));self.assertEqual(usage.charged_cost,0)
        self.assertEqual(usage.payer,'standing:'+authority.AUTHORITY_ID)
        self.assertEqual(list(Wallet.objects.order_by('id').values()),before)
        self.assertFalse(Reservation.objects.exists());self.assertFalse(LedgerEntry.objects.exists())
        self.assertEqual(TestingReservation.objects.get(job=job).state,'settled')
        self.assertEqual(billing.settle(job,Decimal('0.1'),units,rates,'anthropic:returned-model','standing-request').pk,usage.pk)
        from core.management.commands.audit_billing import audit_report
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_actual_over_estimate_is_retained_not_capped_or_discarded(self):
        job=self.job(config=self.config('generation',testing_quote_usd='0.010000000000'))
        billing.reserve(job,Decimal('0.01'))
        usage=billing.settle(job,Decimal('17.50'),{}, {},'anthropic:returned-model','standing-over-estimate')
        self.assertEqual(usage.actual_cost,Decimal('17.50'));self.assertEqual(usage.charged_cost,0)
        self.assertEqual(TestingReservation.objects.get(job=job).quoted_provider_cost,Decimal('0.01'))
        self.assertFalse(Wallet.objects.exists());self.assertFalse(LedgerEntry.objects.exists())

    def test_sponsor_reservation_cannot_be_relabelled_deleted_or_reused(self):
        job=self.job();billing.reserve(job,Decimal('2.5'))
        self.refusal(lambda:TestingReservation.objects.filter(job=job).update(quoted_provider_cost=1))
        self.refusal(lambda:TestingReservation.objects.filter(job=job).delete())
        billing.release(job)
        self.assertEqual(TestingReservation.objects.get(job=job).state,'released')
        self.refusal(lambda:TestingReservation.objects.filter(job=job).update(state='held'))
        with self.assertRaises(ValidationError):billing.settle(job,Decimal('0.1'),{}, {},'anthropic:returned-model')
        self.assertFalse(Usage.objects.exists())

    def test_standing_job_identity_cannot_be_redirected_after_admission(self):
        job=self.job();billing.reserve(job,Decimal('2.5'))
        for values in [{'kind':'transcription'},{'encounter_id':self.encounter().pk},
                       {'input_path':'different-synthetic-source.wav'},{'revision':999}]:
            self.refusal(lambda:Job.objects.filter(pk=job.pk).update(**values))

    def test_unknown_standing_job_cannot_be_requeued_or_release_reused(self):
        job=self.job();billing.reserve(job,Decimal('2.5'))
        Job.objects.filter(pk=job.pk).update(state='reconciliation')
        self.refusal(lambda:Job.objects.filter(pk=job.pk).update(state='queued'))
        billing.release(job)
        with self.assertRaises(ValidationError):billing.reserve(job,Decimal('2.5'))

    def test_missing_sponsor_reservation_refuses_before_any_provider_send(self):
        job=self.job()
        with patch('core.generation.generate') as provider:
            self.assertTrue(jobs.run_one())
        provider.assert_not_called();job.refresh_from_db()
        self.assertEqual(job.state,'failed');self.assertFalse(TestingReservation.objects.exists())

    def test_invoice_reconciliation_and_failed_absorption_never_create_user_funds(self):
        from core.models import PlatformCost
        from core.management.commands.audit_billing import audit_report
        job=self.job();billing.reserve(job,Decimal('2.5'))
        units={'input_tokens':100000,'output_tokens':0,'cached_input_tokens':0}
        rates={'input_per_million':'1','output_per_million':'1','cached_per_million':'1'}
        ProviderReceipt.objects.create(job=job,provider='anthropic:returned-model',provider_request_id='standing-invoice',
            units=units,rates=rates,actual_cost=Decimal('0.1'))
        usage=billing.settle(job,Decimal('0.1'),units,rates,'anthropic:returned-model','standing-invoice')
        reconciled=billing.reconcile_usage(usage,Decimal('0.15'),'synthetic-invoice-proof',self.doctor,evidence_kind='invoice')
        self.assertEqual(reconciled.charge_delta,0);self.assertEqual(reconciled.over_limit_delta,0)
        self.assertTrue(reconciled.invoice_reconciled);self.assertEqual(reconciled.ledger_status,'applied')
        self.assertEqual(Usage.objects.get(job=job).actual_cost,Decimal('0.1'))
        self.assertTrue(audit_report()['all_checks_pass'])
        Job.objects.filter(pk=job.pk).update(state='failed',error='platform_failure: synthetic unusable response')
        cost=billing.absorb_failed_job(job)
        self.assertEqual(cost.amount,Decimal('0.15'))
        self.assertEqual(PlatformCost.objects.filter(job=job).count(),1)
        self.assertTrue(audit_report()['all_checks_pass'])
        self.assertFalse(Wallet.objects.exists());self.assertFalse(LedgerEntry.objects.exists())

    def test_candidate_authentication_and_legacy_admission_with_0023_while_standing_disabled(self):
        from django.db.migrations.executor import MigrationExecutor
        from django.test import Client
        with transaction.atomic():
            MigrationExecutor(connection).migrate([('core','0023_delivery_campaign')])
            with override_settings(TESTING_AUTHORITY_MODE='',TESTING_AUTHORITY_ID='',TESTING_AUTHORITY_SHA256='',
                    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
                    STORAGES={'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}):
                client=Client();client.force_login(self.doctor)
                self.assertEqual(client.get('/health/').status_code,200)
                self.assertEqual(client.get('/templates/upload/').status_code,200)
                legacy=self.preparation({'mode':'live','provider':'anthropic','model':'historical-label'})
                self.raw_insert(PreparationReceipt,preparation=legacy,role='proposer',provider='anthropic',
                    requested_model='historical-label',request_sha256='e'*64,quote_maximum=Decimal('0.10'))
                self.assertIsNone(authority.identity(legacy.config))
            transaction.set_rollback(True)

    def test_wallet_money_cannot_be_attached_to_standing_requests_by_sql(self):
        job=self.job();billing.reserve(job,Decimal('2.5'))
        wallet=Wallet.objects.create(user=self.doctor,kind='paid',balance=0,reserved=0)
        self.refusal(lambda:self.raw_insert(Reservation,job=job,wallet=wallet,amount=0))
        self.refusal(lambda:self.raw_insert(LedgerEntry,job=job,wallet=wallet,amount=0,
            kind='usage',key='standing-forbidden',description='Synthetic forbidden test',balance_after=0))

    def test_wrong_tenant_unverified_actor_and_kind_fail_before_reservation(self):
        stranger=User.objects.create(username='standing-stranger',email='stranger@example.invalid',verified_at=timezone.now())
        Membership.objects.create(user=stranger,department=self.department,role='owner')
        self.refusal(lambda:self.job(user=stranger))
        self.refusal(lambda:self.job(kind='unrelated'))
        self.refusal(lambda:self.job(config=self.config('transcription',testing_quote_usd='1')))
        self.doctor.verified_at=None;self.doctor.save(update_fields=['verified_at'])
        self.refusal(lambda:self.job())
        self.assertFalse(TestingReservation.objects.exists())

    def test_runtime_admission_proves_installed_controls_without_creating_holds(self):
        result=authority.runtime_admission(self.doctor,self.department.pk)
        self.assertTrue(result['admitted']);self.assertIsNone(result['monetary_ceiling'])
        self.assertIsNone(result['cumulative_call_ceiling']);self.assertEqual(result['provider_calls'],0)
        self.assertFalse(TestingReservation.objects.exists());self.assertFalse(Wallet.objects.exists())

    def test_runtime_admission_rejects_disabled_or_retargeted_guards(self):
        for table,guard in [('core_job','standing_job_guard'),
                            ('core_templatepreparation','preparation_pilot_guard')]:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(f'ALTER TABLE {table} DISABLE TRIGGER {guard}')
                with self.assertRaises(ValidationError):authority.runtime_admission(self.doctor,self.department.pk)
                transaction.set_rollback(True)
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('DROP TRIGGER standing_wallet_ledger_guard ON core_ledgerentry')
                cursor.execute('CREATE TRIGGER standing_wallet_ledger_guard BEFORE INSERT ON core_ledgerentry '
                    'FOR EACH ROW WHEN (false) EXECUTE FUNCTION quillmd_standing_wallet_guard()')
            with self.assertRaises(ValidationError):authority.runtime_admission(self.doctor,self.department.pk)
            transaction.set_rollback(True)

    def test_provider_exception_retains_unknown_reservation_without_retry(self):
        job=self.job();billing.reserve(job,Decimal('2.5'))
        with patch('core.generation.generate',side_effect=TimeoutError('synthetic timeout')) as provider:
            self.assertTrue(jobs.run_one());self.assertFalse(jobs.run_one())
        job.refresh_from_db()
        self.assertEqual(provider.call_count,1);self.assertEqual(job.state,'reconciliation')
        self.assertEqual(TestingReservation.objects.get(job=job).state,'held')
        self.assertFalse(Usage.objects.exists());self.assertFalse(LedgerEntry.objects.exists())

    def test_provider_slot_refusal_releases_only_unsent_standing_request(self):
        job=self.job();billing.reserve(job,Decimal('2.5'))
        with patch('core.preparation_campaign.provider_slot',side_effect=authority.TestingProviderRefusal('Not sent')), \
                patch('core.generation.generate') as provider:
            self.assertTrue(jobs.run_one())
        job.refresh_from_db();provider.assert_not_called()
        self.assertEqual(job.state,'failed');self.assertEqual(TestingReservation.objects.get(job=job).state,'released')
