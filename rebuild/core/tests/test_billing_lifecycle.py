"""Signed synthetic Stripe events; no provider HTTP or charged payment is made."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
import hashlib
import hmac
import json
import threading
import time
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from django.core import signing
from django.db import DatabaseError, close_old_connections, connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from core.billing import record_stripe_event, reserve, settle, release
from core.generation import configuration,generate
from core.models import Job, LedgerEntry, Membership, Payment, ProviderReceipt, Refund, Reservation, Usage, Wallet, WebhookEvent
from core.tests.test_security import SyntheticFixture

SECRET='whsec_synthetic_lifecycle'

class StripeFixture(SyntheticFixture):
    def setUp(self):
        self.scope=self.make_scope('billing-lifecycle')
        self.wallet=Wallet.objects.get(user=self.scope[0],kind='paid')
        self.payment=Payment.objects.create(user=self.scope[0],wallet=self.wallet,amount_cents=1000,stripe_session='cs_test_lifecycle')
        self.session={'id':self.payment.stripe_session,'payment_status':'paid','currency':'usd','amount_total':1000,'metadata':{'payment_id':str(self.payment.pk)},'payment_intent':'pi_test_lifecycle','mode':'payment'}
        self.refund={'id':'re_test_lifecycle','payment_intent':'pi_test_lifecycle','amount':300,'currency':'usd','status':'succeeded'}
    def event(self,event_id,obj=None,kind='checkout.session.completed',client=None,**extras):
        payload={'id':event_id,'object':'event','type':kind,'livemode':False,'data':{'object':self.session if obj is None else obj},**extras}
        body=json.dumps(payload).encode();stamp=str(int(time.time()))
        signature=hmac.new(SECRET.encode(),stamp.encode()+b'.'+body,hashlib.sha256).hexdigest()
        return (client or self.client).post('/billing/webhook/',body,content_type='application/json',HTTP_STRIPE_SIGNATURE=f't={stamp},v1={signature}')
    def balance(self):
        self.wallet.refresh_from_db();return self.wallet.balance

@override_settings(STRIPE_WEBHOOK_SECRET=SECRET,ADMIN_SITE=False,STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class StripeLifecycle(StripeFixture,TestCase):
    def test_currency_mismatch_retains_failure_without_debit(self):
        self.assertEqual(self.event('evt_pay').status_code,200)
        self.assertEqual(self.event('evt_eur',{**self.refund,'currency':'eur'},'refund.created').status_code,409)
        self.assertEqual(self.balance(),10)
        self.assertEqual(WebhookEvent.objects.get(event_id='evt_eur').status,'reconciliation')
        self.assertFalse(Refund.objects.exists())

    def test_failed_and_expired_sessions_are_visible_and_late_success_wins(self):
        unpaid={**self.session,'payment_status':'unpaid'}
        self.assertEqual(self.event('evt_fail',unpaid,'checkout.session.async_payment_failed').status_code,200)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'failed')
        self.assertEqual(self.event('evt_expired',unpaid,'checkout.session.expired').status_code,200)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'expired')
        self.assertEqual(self.balance(),0)
        self.assertEqual(self.event('evt_success',kind='checkout.session.async_payment_succeeded').status_code,200)
        self.assertEqual(self.event('evt_stale_failure',unpaid,'checkout.session.async_payment_failed').status_code,200)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'paid');self.assertEqual(self.balance(),10)

    def test_unpaid_completion_does_not_grant_and_does_not_regress_paid(self):
        unpaid={**self.session,'payment_status':'unpaid'}
        self.assertEqual(self.event('evt_processing',unpaid).status_code,200)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'processing');self.assertEqual(self.balance(),0)
        self.event('evt_success');self.event('evt_stale',unpaid)
        self.payment.refresh_from_db();self.assertEqual(self.payment.status,'paid');self.assertEqual(self.balance(),10)

    def test_refund_before_payment_is_retried_after_success(self):
        self.assertEqual(self.event('evt_early_refund',self.refund,'refund.created').status_code,409)
        self.assertEqual(WebhookEvent.objects.get(event_id='evt_early_refund').status,'reconciliation')
        self.assertEqual(self.event('evt_later_payment').status_code,200)
        pending=WebhookEvent.objects.get(event_id='evt_early_refund')
        self.assertEqual(pending.status,'processed');self.assertEqual(pending.attempts,2)
        self.assertEqual(self.balance(),7)
        self.assertEqual(self.event('evt_early_refund',self.refund,'refund.created').status_code,200)
        self.assertEqual(self.balance(),7)

    def test_webhook_before_session_response_binds_only_authorized_metadata(self):
        self.payment.stripe_session=None;self.payment.save(update_fields=['stripe_session'])
        self.assertEqual(self.event('evt_early_session').status_code,200)
        self.payment.refresh_from_db();self.assertEqual(self.payment.stripe_session,self.session['id'])
        self.assertEqual(self.balance(),10)

    def test_pending_failed_and_stale_refund_do_not_debit(self):
        self.event('evt_pay')
        self.event('evt_pending',{**self.refund,'status':'pending'},'refund.created')
        self.event('evt_failed',{**self.refund,'status':'failed'},'refund.failed')
        self.event('evt_stale',{**self.refund,'status':'pending'},'refund.updated')
        self.assertEqual(Refund.objects.get().status,'failed');self.assertEqual(self.balance(),10)
        self.assertFalse(LedgerEntry.objects.filter(kind='refund').exists())

    def test_successful_refund_is_terminal_and_duplicates_do_not_debit(self):
        self.event('evt_pay');self.event('evt_refund',self.refund,'refund.created')
        self.event('evt_update',self.refund,'refund.updated')
        self.event('evt_stale',{**self.refund,'status':'pending'},'refund.updated')
        self.assertEqual(Refund.objects.get().status,'succeeded');self.assertEqual(self.balance(),7)
        self.assertEqual(LedgerEntry.objects.filter(kind='refund').count(),1)

    def test_changed_refund_amount_or_same_event_identity_is_rejected(self):
        self.event('evt_pay');self.event('evt_refund',self.refund,'refund.created')
        self.assertEqual(self.event('evt_refund',{**self.refund,'amount':400},'refund.created').status_code,409)
        self.assertEqual(self.event('evt_changed',{**self.refund,'amount':400},'refund.updated').status_code,409)
        self.assertEqual(self.balance(),7)

    def test_insufficient_available_paid_funds_are_held_for_reconciliation(self):
        self.event('evt_pay')
        job=Job.objects.create(encounter=self.scope[5],user=self.scope[0],request_key='reserved-paid')
        self.wallet.reserved=8;self.wallet.save(update_fields=['reserved'])
        Reservation.objects.create(wallet=self.wallet,job=job,amount=8)
        self.assertEqual(self.event('evt_held_refund',self.refund,'refund.created').status_code,409)
        self.assertEqual(self.balance(),10);self.assertEqual(self.wallet.reserved,8)
        release(job)
        self.assertEqual(self.event('evt_held_refund',self.refund,'refund.created').status_code,200)
        self.assertEqual(self.balance(),7)

    def test_duplicate_success_validates_original_amount_and_intent(self):
        self.event('evt_pay')
        self.assertEqual(self.event('evt_changed',{**self.session,'payment_intent':'pi_other'}).status_code,409)
        self.assertEqual(self.event('evt_wrong_amount',{**self.session,'amount_total':999}).status_code,409)
        self.assertEqual(self.balance(),10)

    def test_live_mode_and_missing_mode_are_rejected(self):
        self.assertEqual(self.event('evt_live',livemode=True).status_code,400)
        self.assertEqual(self.event('evt_unknown',livemode=None).status_code,400)
        self.assertEqual(self.balance(),0);self.assertFalse(WebhookEvent.objects.exists())

    def test_signed_evidence_strips_customer_fields_and_cannot_mutate(self):
        self.event('evt_safe',{**self.session,'customer_email':'synthetic-person@example.invalid','customer_details':{'name':'SYNTHETIC'},'metadata':{**self.session['metadata'],'private_note':'DO NOT STORE'}})
        row=WebhookEvent.objects.get(event_id='evt_safe')
        serialized=json.dumps(row.object_data)
        self.assertNotIn('synthetic-person',serialized);self.assertNotIn('private_note',serialized)
        with self.assertRaises(DatabaseError),transaction.atomic():WebhookEvent.objects.filter(pk=row.pk).update(object_data={})
        with self.assertRaises(DatabaseError),transaction.atomic():WebhookEvent.objects.filter(pk=row.pk).delete()

    @override_settings(STRIPE_SECRET_KEY='sk_test_synthetic_adapter')
    def test_repeated_checkout_submission_reuses_single_session(self):
        self.client.force_login(self.scope[0])
        token=signing.dumps({'user':str(self.scope[0].pk),'nonce':'one-authorized-click'},salt='checkout-authorization')
        data={'amount':'10.00','consent':'on','checkout_token':token}
        with patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_test_new',url='https://checkout.stripe.com/test/synthetic')) as api:
            first=self.client.post('/billing/checkout/',data);second=self.client.post('/billing/checkout/',data)
        self.assertEqual(first.status_code,302);self.assertEqual(first.url,second.url)
        self.assertEqual(api.call_count,1)
        self.assertEqual(Payment.objects.exclude(pk=self.payment.pk).count(),1)
        self.assertEqual(self.balance(),0)

    @override_settings(STRIPE_SECRET_KEY='sk_test_synthetic_adapter')
    def test_uncertain_checkout_is_not_automatically_retried(self):
        self.client.force_login(self.scope[0])
        token=signing.dumps({'user':str(self.scope[0].pk),'nonce':'timeout-click'},salt='checkout-authorization')
        data={'amount':'10.00','consent':'on','checkout_token':token}
        with patch('stripe.checkout.Session.create',side_effect=TimeoutError) as api:
            self.client.post('/billing/checkout/',data);self.client.post('/billing/checkout/',data)
        self.assertEqual(api.call_count,1)
        self.assertEqual(Payment.objects.exclude(pk=self.payment.pk).get().status,'uncertain')
        self.assertEqual(self.balance(),0)

    def test_pricing_snapshot_is_stable_changes_with_rate_and_is_immutable(self):
        with override_settings(AI_INPUT_RATE='3'): first=configuration();self.assertEqual(first['pricing_version'],configuration()['pricing_version'])
        with override_settings(AI_INPUT_RATE='4'): second=configuration()
        self.assertNotEqual(first['pricing_version'],second['pricing_version'])
        job=Job.objects.create(encounter=self.scope[5],user=self.scope[0],request_key='snapshot',config=first)
        reserve(job,Decimal('1'));job.refresh_from_db()
        with self.assertRaises(DatabaseError),transaction.atomic():Job.objects.filter(pk=job.pk).update(config=second)
        with self.assertRaises(DatabaseError),transaction.atomic():Job.objects.filter(pk=job.pk).update(payer='other')
        usage=settle(job,Decimal('.1'),{'input_tokens':1},{'input_per_million':'3'},'synthetic-provider','request-synthetic')
        self.assertIn('durable receipt unavailable',usage.cost_evidence)
        ProviderReceipt.objects.create(job=job,provider=usage.provider,provider_request_id=usage.provider_request_id,actual_cost=usage.actual_cost,units=usage.units,rates=usage.rates)
        usage=Usage.objects.get(pk=usage.pk)
        self.assertEqual(usage.cost_evidence,'Provider-metered usage × configured rates')
        self.assertEqual(usage.invoice_status,'Not reconciled to a provider invoice')

    @override_settings(AI_MODE='live',AI_PROVIDER='anthropic',AI_MODEL='claude-sonnet-4-6',AI_INPUT_RATE='3',AI_OUTPUT_RATE='15',AI_CACHED_RATE='.3')
    def test_new_provider_call_records_http_request_and_message_ids_separately(self):
        from core.jobs import enqueue,run_one
        response=SimpleNamespace(id='msg_synthetic_resource',_request_id='req_synthetic_http',
            usage=SimpleNamespace(input_tokens=100,output_tokens=10,cache_read_input_tokens=0,cache_creation_input_tokens=0),
            stop_reason='end_turn',content=[SimpleNamespace(type='text',text=json.dumps({'fields':[{'key':'symptoms','quotes':['no chest pain'],'conflict':False}]}))],
            model_dump=lambda **kwargs:{'id':'msg_synthetic_resource'})
        with tempfile.TemporaryDirectory() as directory,override_settings(MEDIA_ROOT=Path(directory)),patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value=response
            job=enqueue(self.scope[5],self.scope[0]);self.assertTrue(run_one())
            from core.management.commands.audit_billing import audit_report
            report=audit_report()
            self.assertTrue(report['all_checks_pass'])
            self.assertEqual(report['rows'][0]['http_request_id'],'req_synthetic_http')
            self.assertFalse(report['rows'][0]['invoice_reconciled'])
            job.refresh_from_db()
            result_file=Path(directory)/job.result_path
            result_file.write_bytes(b'Synthetic tampering to prove the audit notices corruption')
            self.assertFalse(audit_report()['all_checks_pass'])
        job.refresh_from_db();self.assertEqual(job.state,'succeeded')
        usage=Usage.objects.get(job=job);receipt=ProviderReceipt.objects.get(job=job)
        for record in [job,usage,receipt]:
            self.assertEqual(record.http_request_id,'req_synthetic_http')
            self.assertEqual(record.resource_id,'msg_synthetic_resource')
        self.assertTrue(job.pricing_snapshot.startswith('configured-v1:'))
        self.assertEqual(usage.actual_cost,Decimal('.00045'))
        self.assertEqual(usage.charged_cost,Decimal('.000675'))
        self.assertEqual(usage.cost_evidence,'Provider-metered usage × configured rates')

    @override_settings(AI_MODE='live',AI_PROVIDER='openai',AI_MODEL='synthetic-model',AI_INPUT_RATE='3',AI_OUTPUT_RATE='15',AI_CACHED_RATE='.3')
    def test_optional_openai_adapter_returns_http_identifier_not_response_identifier(self):
        response=SimpleNamespace(id='resp_synthetic_resource',_request_id='req_synthetic_http',usage=SimpleNamespace(input_tokens=100,output_tokens=10,input_tokens_details=SimpleNamespace(cached_tokens=0)))
        with patch('openai.OpenAI') as client:
            client.return_value.responses.parse.return_value=response
            result=generate('Synthetic notes',[])
        self.assertEqual(result[5],'req_synthetic_http')
        self.assertEqual(result[0]['response'].id,'resp_synthetic_resource')

    def test_historical_message_identifier_is_not_claimed_as_http_request_id(self):
        for model in [Job,Usage,ProviderReceipt]:
            record=model(provider='anthropic:historical',provider_request_id='msg_historical')
            self.assertEqual(record.http_request_id,'')
            self.assertEqual(record.resource_id,'msg_historical')

    def test_repeated_provider_response_cannot_charge_a_second_job(self):
        jobs=[Job.objects.create(encounter=self.scope[5],user=self.scope[0],request_key=f'provider-replay:{i}') for i in range(3)]
        for job in jobs:reserve(job,Decimal('1'))
        settle(jobs[0],Decimal('.1'),{}, {},'synthetic-provider','req_same',provider_resource_id='resource_same')
        with self.assertRaises(DatabaseError),transaction.atomic():
            settle(jobs[1],Decimal('.1'),{}, {},'synthetic-provider','req_same',provider_resource_id='resource_other')
        with self.assertRaises(DatabaseError),transaction.atomic():
            settle(jobs[2],Decimal('.1'),{}, {},'synthetic-provider','req_other',provider_resource_id='resource_same')
        self.assertEqual(Usage.objects.count(),1)
        self.assertEqual(LedgerEntry.objects.filter(kind='usage').count(),1)
        promo=Wallet.objects.get(user=self.scope[0],kind='promo')
        self.assertEqual(promo.balance,Decimal('9.85'));self.assertEqual(promo.reserved,3)

    def test_provider_identifier_replay_across_model_names_cannot_charge_twice(self):
        first=Job.objects.create(encounter=self.scope[5],user=self.scope[0],request_key='model-first')
        second=Job.objects.create(encounter=self.scope[5],user=self.scope[0],request_key='model-second')
        reserve(first,Decimal('1'));reserve(second,Decimal('1'))
        settle(first,Decimal('.1'),{}, {},'anthropic:model-a','req_same',provider_resource_id='msg_same')
        with self.assertRaises(DatabaseError),transaction.atomic():
            settle(second,Decimal('.1'),{}, {},'anthropic:model-b','req_same',provider_resource_id='msg_same')
        self.assertEqual(Usage.objects.count(),1)
        self.assertEqual(Wallet.objects.get(user=self.scope[0],kind='promo').balance,Decimal('9.85'))

    def test_historical_message_id_cannot_charge_again_in_new_resource_column(self):
        first=Job.objects.create(encounter=self.scope[5],user=self.scope[0],request_key='legacy-first')
        second=Job.objects.create(encounter=self.scope[5],user=self.scope[0],request_key='legacy-second')
        reserve(first,Decimal('1'));reserve(second,Decimal('1'))
        settle(first,Decimal('.1'),{}, {},'anthropic:model-a','msg_same')
        with self.assertRaises(DatabaseError),transaction.atomic():
            settle(second,Decimal('.1'),{}, {},'anthropic:model-b','req_new',provider_resource_id='msg_same')
        self.assertEqual(Usage.objects.count(),1)
        self.assertEqual(Wallet.objects.get(user=self.scope[0],kind='promo').balance,Decimal('9.85'))

    @override_settings(STRIPE_SECRET_KEY='sk_test_synthetic_adapter')
    def test_owner_can_explicitly_fund_organization_without_moving_personal_credit(self):
        Membership.objects.filter(user=self.scope[0]).update(role='owner')
        self.client.force_login(self.scope[0])
        token=signing.dumps({'user':str(self.scope[0].pk),'nonce':'fund-org'},salt='checkout-authorization')
        data={'amount':'10.00','consent':'on','checkout_token':token,'payer':f'organization:{self.scope[1].pk}'}
        with patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_test_org',url='https://checkout.stripe.com/test/synthetic')) as api:
            self.assertEqual(self.client.post('/billing/checkout/',data).status_code,302)
        self.assertEqual(api.call_count,1)
        payment=Payment.objects.exclude(pk=self.payment.pk).get()
        self.assertEqual(payment.wallet.organization_id,self.scope[1].pk)
        session={**self.session,'id':'cs_test_org','payment_intent':'pi_test_org','metadata':{'payment_id':str(payment.pk)}}
        self.assertEqual(self.event('evt_org_paid',session).status_code,200)
        self.assertEqual(Wallet.objects.get(user=self.scope[0],kind='promo').balance,10)
        self.assertEqual(self.balance(),0)
        organization_wallet=Wallet.objects.get(organization=self.scope[1],kind='paid')
        self.assertEqual(organization_wallet.balance,10)
        self.scope[2].organization_pays=True;self.scope[2].save(update_fields=['organization_pays'])
        job=Job.objects.create(encounter=self.scope[5],user=self.scope[0],request_key='org-paid-usage')
        reserve(job,Decimal('8'));usage=settle(job,Decimal('8'),{}, {},'synthetic-cost','req_org_usage')
        self.assertEqual(usage.payer,f'organization:{self.scope[1].pk}')
        self.assertEqual(Wallet.objects.get(user=self.scope[0],kind='promo').balance,0)
        organization_wallet.refresh_from_db();self.assertEqual(organization_wallet.balance,8)
        self.assertEqual(usage.charged_cost,12)

    @override_settings(STRIPE_SECRET_KEY='sk_test_synthetic_adapter')
    def test_employee_and_revoked_owner_cannot_authorize_organization_topup(self):
        self.client.force_login(self.scope[0])
        token=signing.dumps({'user':str(self.scope[0].pk),'nonce':'forbidden-org'},salt='checkout-authorization')
        data={'amount':'10.00','consent':'on','checkout_token':token,'payer':f'organization:{self.scope[1].pk}'}
        with patch('stripe.checkout.Session.create') as api:
            self.assertEqual(self.client.post('/billing/checkout/',data).status_code,302)
            Membership.objects.filter(user=self.scope[0]).update(role='owner',active=False)
            self.assertEqual(self.client.post('/billing/checkout/',data).status_code,302)
        api.assert_not_called()
        self.assertEqual(Payment.objects.count(),1)
        self.assertFalse(Wallet.objects.filter(organization=self.scope[1]).exists())

    @override_settings(STRIPE_SECRET_KEY='sk_test_synthetic_adapter')
    def test_repeat_checkout_cannot_switch_authorized_wallet(self):
        Membership.objects.filter(user=self.scope[0]).update(role='owner')
        self.client.force_login(self.scope[0])
        token=signing.dumps({'user':str(self.scope[0].pk),'nonce':'same-wallet-only'},salt='checkout-authorization')
        data={'amount':'10.00','consent':'on','checkout_token':token,'payer':'personal'}
        with patch('stripe.checkout.Session.create',return_value=SimpleNamespace(id='cs_test_personal',url='https://checkout.stripe.com/test/synthetic')) as api:
            self.assertEqual(self.client.post('/billing/checkout/',data).status_code,302)
            self.assertEqual(self.client.post('/billing/checkout/',{**data,'payer':f'organization:{self.scope[1].pk}'}).status_code,400)
        self.assertEqual(api.call_count,1)

@override_settings(STRIPE_WEBHOOK_SECRET=SECRET,ADMIN_SITE=False)
class ConcurrentStripeLifecycle(StripeFixture,TransactionTestCase):
    def parallel(self,operation):
        barrier=threading.Barrier(2)
        def run(index):
            close_old_connections()
            try:barrier.wait(timeout=10);return operation(index,Client())
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as workers:
            tasks=[workers.submit(run,i) for i in range(2)]
            return [t.result(timeout=20) for t in tasks]

    def test_same_event_concurrently_credits_once(self):
        self.assertEqual(self.parallel(lambda i,c:self.event('evt_concurrent',client=c).status_code),[200,200])
        self.assertEqual(self.balance(),10)
        self.assertEqual(LedgerEntry.objects.filter(kind='payment').count(),1)
        self.assertEqual(WebhookEvent.objects.get().attempts,1)

    def test_distinct_success_events_concurrently_credit_once(self):
        self.assertEqual(self.parallel(lambda i,c:self.event(f'evt_success_{i}',client=c).status_code),[200,200])
        self.assertEqual(self.balance(),10);self.assertEqual(LedgerEntry.objects.filter(kind='payment').count(),1)

    def test_concurrent_refunds_cannot_exceed_payment(self):
        self.event('evt_pay')
        responses=self.parallel(lambda i,c:self.event(f'evt_refund_{i}',{**self.refund,'id':f're_partial_{i}','amount':700},'refund.created',c).status_code)
        self.assertCountEqual(responses,[200,409]);self.assertEqual(self.balance(),3)
        self.assertEqual(LedgerEntry.objects.filter(kind='refund').count(),1)
        self.assertEqual(WebhookEvent.objects.filter(status='reconciliation').count(),1)
