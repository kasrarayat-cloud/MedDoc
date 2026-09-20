"""Owner-directed billing policy: discounted configured estimates, reconciliation to provider evidence,
fixed overhead kept off user ledgers, and absorbed platform failures.

All data is synthetic. No provider, payment or console request leaves the test database.
"""
import json
import os
import tempfile
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from datetime import timedelta
from core.jobs import mark_stale
from core.security import private_path
from core.models import ProviderReceipt

from core import views
from core.billing import absorb_failed_job, apply_pending_reconciliations, reconcile_usage, reserve, settle
from core.generation import configuration, discounted_cost
from core.jobs import enqueue, run_one
from core.management.commands.audit_billing import audit_report
from core.models import AuditEvent, CostReconciliation, Encounter, Job, LedgerEntry, PlatformCost, Reservation, Usage, User, Wallet
from core.tests.test_security import SyntheticFixture
from core.tests.audio_fixtures import wav_bytes

STORAGES={'default':{'BACKEND':'django.core.files.storage.FileSystemStorage'},'staticfiles':{'BACKEND':'django.contrib.staticfiles.storage.StaticFilesStorage'}}
# One thousand synthetic input tokens cost one synthetic dollar, so audits can recompute every estimate exactly.
AUDITABLE_RATES={'input_per_million':'1000','output_per_million':'0','cached_per_million':'0'}


def fund(wallet,amount,key):
    """Paid funds with a matching ledger row, so the wallet audit checks stay meaningful."""
    wallet.refresh_from_db();wallet.balance+=amount;wallet.save(update_fields=['balance'])
    LedgerEntry.objects.create(wallet=wallet,amount=amount,kind='payment',key=key,description='Synthetic paid funds',balance_after=wallet.balance)


class DiscountConfiguration(SimpleTestCase):
    def test_default_discount_is_zero_and_part_of_the_pricing_fingerprint(self):
        with patch.dict(os.environ,{'QUILLMD_PROVIDER_DISCOUNT_RATE':''}):base=configuration()
        self.assertEqual(base['discount_rate'],'0')
        self.assertEqual(Decimal(base['discount_rate']),Decimal('0'))
        self.assertTrue(base['pricing_version'].startswith('configured-v1:'))
        with patch.dict(os.environ,{'QUILLMD_PROVIDER_DISCOUNT_RATE':'0.20'}):discounted=configuration()
        self.assertEqual(discounted['discount_rate'],'0.2')
        self.assertNotEqual(base['pricing_version'],discounted['pricing_version'])
        with patch.dict(os.environ,{'QUILLMD_PROVIDER_DISCOUNT_RATE':'0.2'}):self.assertEqual(configuration()['pricing_version'],discounted['pricing_version'])
        for bad in ['1','-0.1','abc','1.5','NaN','Infinity']:
            with self.subTest(bad=bad),patch.dict(os.environ,{'QUILLMD_PROVIDER_DISCOUNT_RATE':bad}),self.assertRaises(ValidationError):configuration()

    def test_discounted_cost_is_unchanged_at_zero_and_rounded_once_to_ledger_precision(self):
        self.assertEqual(discounted_cost(Decimal('0.00045'),Decimal('0')),Decimal('0.00045'))
        self.assertEqual(discounted_cost(Decimal('0.00045'),Decimal('0.2')),Decimal('0.00036'))
        # Eleven decimals, so the exact 1.5× charge always fits the twelve-decimal ledger (refutation F2).
        self.assertEqual(discounted_cost(Decimal('0.1'),Decimal('0.3333333333333')),Decimal('0.06666666667'))
        # 0.001049382545 is a tie at the eleventh decimal: half-even keeps ...254, and 1.5x still fits twelve decimals.
        self.assertEqual(discounted_cost(Decimal('0.0012345677'),Decimal('0.15')),Decimal('0.00104938254'))
        self.assertEqual(Decimal('0.00104938254')*Decimal('1.5'),Decimal('0.00157407381'))


class PolicyFixture(SyntheticFixture):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        override=override_settings(MEDIA_ROOT=Path(self.directory.name));override.enable();self.addCleanup(override.disable)
        self.scope=self.make_scope('policy')
        self.user=self.scope[0];self.encounter=self.scope[5]
        self.promo=Wallet.objects.get(user=self.user,kind='promo');self.paid=Wallet.objects.get(user=self.user,kind='paid')

    def settled(self,actual,maximum=None,key='policy-usage'):
        """A settled usage row whose configured estimate an audit can recompute (tokens = cost × 1000)."""
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key=key)
        reserve(job,maximum if maximum is not None else actual)
        units={'input_tokens':int(Decimal(actual)*1000),'output_tokens':0,'cached_input_tokens':0,'cache_creation_tokens':0}
        usage=settle(job,actual,units,AUDITABLE_RATES,'anthropic:synthetic-model',f'req_{key}',provider_resource_id=f'msg_{key}')
        job.state='succeeded';job.finished_at=timezone.now();job.save(update_fields=['state','finished_at'])
        return usage

    def balances(self):
        self.promo.refresh_from_db();self.paid.refresh_from_db()
        return self.promo.balance,self.paid.balance


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES)
class ConfiguredEstimateDiscount(PolicyFixture,TestCase):
    @override_settings(AI_MODE='live',AI_PROVIDER='anthropic',AI_MODEL='synthetic-model',AI_INPUT_RATE='3',AI_OUTPUT_RATE='15',AI_CACHED_RATE='.3')
    def test_discount_rate_reduces_the_configured_estimate_and_is_recorded_for_audit(self):
        response=SimpleNamespace(id='msg_discount',_request_id='req_discount',
            usage=SimpleNamespace(input_tokens=100,output_tokens=10,cache_read_input_tokens=0,cache_creation_input_tokens=0),
            stop_reason='end_turn',content=[SimpleNamespace(type='text',text=json.dumps({'fields':[{'key':'symptoms','quotes':['no chest pain'],'conflict':False}]}))],
            model_dump=lambda **kwargs:{'id':'msg_discount'})
        with patch.dict(os.environ,{'QUILLMD_PROVIDER_DISCOUNT_RATE':'0.2'}),patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value=response
            job=enqueue(self.encounter,self.user);self.assertTrue(run_one())
        job.refresh_from_db();self.assertEqual(job.state,'succeeded');self.assertEqual(job.config['discount_rate'],'0.2')
        usage=Usage.objects.get(job=job)
        self.assertEqual(usage.actual_cost,Decimal('0.00036'));self.assertEqual(usage.charged_cost,Decimal('0.00054'))
        self.assertEqual(usage.rates['discount_rate'],'0.2');self.assertEqual(usage.rates['list_cost_usd'],'0.00045')
        self.assertEqual(usage.cost_evidence,'Provider-metered usage × configured rates')
        report=audit_report();row=report['rows'][0]
        self.assertTrue(report['all_checks_pass'])
        self.assertEqual(row['discount_rate'],'0.2');self.assertEqual(row['configured_list_cost_usd'],'0.00045')
        self.assertTrue(row['checks']['recorded_list_cost_matches']);self.assertTrue(row['checks']['recomputed_defined_cost_matches'])
        self.assertIsNone(row['reconciliation']);self.assertFalse(row['absorbed']);self.assertFalse(row['invoice_reconciled'])


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES)
class AbsorbedPlatformFailure(PolicyFixture,TestCase):
    @override_settings(AI_MODE='live')
    def test_settled_cost_of_unadopted_output_is_reversed_and_carried_as_platform_cost(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='policy-absorb')
        reserve(job,Decimal('0.2'))
        invalid=SimpleNamespace(stop_reason='end_turn',content=[SimpleNamespace(type='text',text='not valid provider JSON')])
        invalid.model_dump=lambda **kwargs:{'stop_reason':'end_turn'}
        units={'input_tokens':100,'output_tokens':10,'cached_input_tokens':0,'cache_creation_tokens':0}
        rates={'input_per_million':'1000','output_per_million':'2500','cached_per_million':'0'}
        result=({'anthropic_response':invalid,'notes':self.encounter.notes,'fields':[]},Decimal('0.125'),units,rates,'anthropic:synthetic-model','req_known_invalid',False)
        with patch('core.jobs.generation.generate',return_value=result):self.assertTrue(run_one())
        job.refresh_from_db();self.assertEqual(job.state,'failed')
        usage=Usage.objects.get(job=job)
        self.assertEqual(usage.actual_cost,Decimal('0.125'));self.assertEqual(usage.charged_cost,Decimal('0.1875'))
        debit=LedgerEntry.objects.get(job=job,kind='usage');self.assertEqual(debit.amount,Decimal('-0.1875'))
        reversal=LedgerEntry.objects.get(job=job,kind='absorbed')
        self.assertEqual(reversal.amount,Decimal('0.1875'));self.assertEqual(reversal.wallet_id,debit.wallet_id)
        self.assertEqual(reversal.key,f'absorbed:{job.pk}:{debit.wallet_id}')
        cost=PlatformCost.objects.get(job=job,kind='absorbed_failure')
        self.assertEqual(cost.amount,Decimal('0.125'));self.assertEqual(cost.description,'Provider cost absorbed: output not adopted')
        self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')));self.assertEqual(self.promo.reserved,0)
        self.assertTrue(AuditEvent.objects.filter(action='usage.absorbed',target=str(job.pk)).exists())
        # Replays are no-ops: the same ledger keys and the one-absorbed-failure-per-job constraint.
        absorb_failed_job(job);absorb_failed_job(job);self.assertFalse(run_one())
        self.assertEqual(LedgerEntry.objects.filter(kind='absorbed').count(),1);self.assertEqual(PlatformCost.objects.count(),1)
        self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        report=audit_report();row=report['rows'][0]
        self.assertTrue(row['absorbed']);self.assertEqual(Decimal(row['absorbed_reversal_usd']),Decimal('0.1875'))
        self.assertEqual(Decimal(row['absorbed_platform_cost_usd']),Decimal('0.125'))
        self.assertTrue(row['checks']['absorbed_reversal_matches_usage_debits']);self.assertTrue(report['all_checks_pass'])
        self.assertEqual(Decimal(report['platform_costs']['totals_by_kind']['absorbed_failure']),Decimal('0.125'))
        self.assertEqual(report['reconciliation_summary']['absorbed_rows'],1)
        self.client.force_login(self.user)
        page=self.client.get('/billing/')
        self.assertContains(page,'Configured estimate');self.assertContains(page,'absorbed by QuillMD')

    @override_settings(AI_MODE='fixture')
    def test_fixture_job_failure_is_unchanged_and_records_no_platform_cost(self):
        original=self.encounter
        draft=Encounter.objects.create(department=original.department,patient=original.patient,template_version=original.template_version,created_by=original.created_by,service_date=original.service_date,notes=original.notes)
        job=enqueue(draft,self.user)
        def result(*args,**kwargs):
            User.objects.filter(pk=self.user.pk).update(is_active=False)
            return ({'symptoms':{'text':'unapproved output','status':'supported'}},Decimal('0'),{},{},'synthetic-fixture','',True)
        with patch('core.jobs.generation.generate',side_effect=result):run_one()
        job.refresh_from_db();self.assertEqual(job.state,'failed')
        self.assertTrue(Usage.objects.filter(job=job,simulated=True).exists())
        self.assertFalse(PlatformCost.objects.exists());self.assertFalse(LedgerEntry.objects.filter(kind='absorbed').exists())
        self.assertFalse(AuditEvent.objects.filter(action='usage.absorbed').exists())

    @override_settings(AI_MODE='live')
    def test_uncertain_outcome_is_not_absorbed_automatically(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='policy-uncertain')
        reserve(job,Decimal('0.2'))
        with patch('core.jobs.generation.generate',side_effect=TimeoutError('synthetic uncertain provider outcome')):run_one()
        job.refresh_from_db();self.assertEqual(job.state,'reconciliation')
        self.assertFalse(PlatformCost.objects.exists());self.assertFalse(LedgerEntry.objects.filter(kind='absorbed').exists())
        self.assertEqual(Reservation.objects.get(job=job).state,'held')


    def _unadopted_live_result(self,request_id):
        invalid=SimpleNamespace(stop_reason='end_turn',content=[SimpleNamespace(type='text',text='not valid provider JSON')])
        invalid.model_dump=lambda **kwargs:{'stop_reason':'end_turn'}
        units={'input_tokens':100,'output_tokens':10,'cached_input_tokens':0,'cache_creation_tokens':0}
        rates={'input_per_million':'1000','output_per_million':'2500','cached_per_million':'0'}
        return ({'anthropic_response':invalid,'notes':self.encounter.notes,'fields':[]},Decimal('0.125'),units,rates,'anthropic:synthetic-model',request_id,False)

    @override_settings(AI_MODE='live')
    def test_absorbed_usage_is_never_credited_twice_by_reconciliation(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='policy-absorb-reconcile')
        reserve(job,Decimal('0.2'))
        with patch('core.jobs.generation.generate',return_value=self._unadopted_live_result('req_absorb_then_reconcile')):self.assertTrue(run_one())
        usage=Usage.objects.get(job=job);self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        row=reconcile_usage(usage,Decimal('0.05'),'INV-SYNTH-ABSORBED',self.user)
        self.assertEqual(row.ledger_status,'absorbed');self.assertEqual(row.charge_delta,Decimal('-0.1125'))
        self.assertFalse(LedgerEntry.objects.filter(kind='reconciliation').exists())
        self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        with self.assertRaises(ValidationError):reconcile_usage(usage,Decimal('0.05'),'INV-SYNTH-ABSORBED-2',self.user)
        report=audit_report();reported=report['rows'][0]
        self.assertTrue(report['all_checks_pass']);self.assertEqual(reported['reconciliation']['ledger_status'],'absorbed')
        self.assertTrue(reported['checks']['failed_settled_usage_absorbed']);self.assertTrue(reported['checks']['reconciliation_delta_arithmetic'])

    @override_settings(AI_MODE='live')
    def test_failed_reversal_never_stops_the_worker_and_is_flagged_by_the_audit(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='policy-absorb-error')
        reserve(job,Decimal('0.2'))
        with patch('core.jobs.generation.generate',return_value=self._unadopted_live_result('req_absorb_error')),patch('core.jobs.absorb_failed_job',side_effect=RuntimeError('synthetic reversal failure')):
            self.assertTrue(run_one())
        job.refresh_from_db();self.assertEqual(job.state,'failed')
        self.assertTrue(AuditEvent.objects.filter(action='usage.absorb_failed',target=str(job.pk)).exists())
        self.assertFalse(LedgerEntry.objects.filter(kind='absorbed').exists());self.assertEqual(self.balances(),(Decimal('9.8125'),Decimal('0')))
        report=audit_report();reported=report['rows'][0]
        self.assertFalse(reported['checks']['failed_settled_usage_absorbed']);self.assertFalse(report['all_checks_pass'])
        absorb_failed_job(job)  # the operator repair path is the same idempotent reversal
        self.assertTrue(audit_report()['all_checks_pass']);self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))

@override_settings(ADMIN_SITE=False,STORAGES=STORAGES)
class ReconciliationLedger(PolicyFixture,TestCase):
    def test_credit_back_returns_to_debited_wallets_in_proportion(self):
        fund(self.paid,Decimal('5'),'payment:policy-split')
        usage=self.settled(Decimal('8'))
        self.assertEqual(LedgerEntry.objects.get(job=usage.job,kind='usage',wallet=self.promo).amount,Decimal('-10'))
        self.assertEqual(LedgerEntry.objects.get(job=usage.job,kind='usage',wallet=self.paid).amount,Decimal('-2'))
        row=reconcile_usage(usage,Decimal('4'),'INV-SYNTH-0001',self.user,provider_credit_applied=Decimal('2'),discount_applied=Decimal('2'),note='Synthetic invoice line')
        self.assertEqual(row.charge_delta,Decimal('-6'));self.assertEqual(row.ledger_status,'applied');self.assertEqual(row.recorded_by,self.user)
        promo_credit=LedgerEntry.objects.get(kind='reconciliation',wallet=self.promo);paid_credit=LedgerEntry.objects.get(kind='reconciliation',wallet=self.paid)
        self.assertEqual(promo_credit.amount,Decimal('5'));self.assertEqual(paid_credit.amount,Decimal('1'))
        self.assertEqual(promo_credit.key,f'reconciliation:{usage.pk}:{self.promo.pk}');self.assertEqual(promo_credit.job_id,usage.job_id)
        self.assertEqual(self.balances(),(Decimal('5'),Decimal('4')))
        usage=Usage.objects.get(pk=usage.pk)
        self.assertEqual(usage.actual_cost,Decimal('8'));self.assertEqual(usage.charged_cost,Decimal('12'))
        self.assertEqual(LedgerEntry.objects.filter(kind='usage').count(),2)
        self.assertEqual(usage.invoice_status,'Reconciled to provider evidence: INV-SYNTH-0001')
        report=audit_report();row=report['rows'][0]
        self.assertTrue(report['all_checks_pass']);self.assertTrue(row['invoice_reconciled'])
        self.assertEqual(Decimal(row['reconciliation']['charge_delta']),Decimal('-6'));self.assertEqual(row['reconciliation']['ledger_status'],'applied')
        self.assertEqual(row['reconciliation']['evidence_reference'],'INV-SYNTH-0001');self.assertTrue(row['checks']['reconciliation_delta_arithmetic'])
        self.assertEqual(len(row['reconciliation_ledger']),2)
        self.client.force_login(self.user)
        page=self.client.get('/billing/')
        self.assertContains(page,'Reconciled actual');self.assertContains(page,'credit back')

    def test_additional_charge_is_debited_from_the_payer_paid_wallet(self):
        fund(self.paid,Decimal('5'),'payment:policy-debit')
        usage=self.settled(Decimal('0.5'),maximum=Decimal('1'))  # approved limit 1.5 leaves headroom for the reconciled 1.5
        self.assertEqual(usage.payer,f'user:{self.user.pk}')
        row=reconcile_usage(usage,Decimal('1'),'export-sha256',self.user,evidence_sha256='B'*64)
        self.assertEqual(row.charge_delta,Decimal('0.75'));self.assertEqual(row.ledger_status,'applied');self.assertEqual(row.evidence_sha256,'b'*64)
        entry=LedgerEntry.objects.get(kind='reconciliation')
        self.assertEqual(entry.wallet_id,self.paid.pk);self.assertEqual(entry.amount,Decimal('-0.75'))
        self.assertEqual(self.balances(),(Decimal('9.25'),Decimal('4.25')))
        report=audit_report()
        self.assertTrue(report['all_checks_pass']);self.assertTrue(report['rows'][0]['checks']['reconciliation_delta_arithmetic'])

    def test_insufficient_paid_funds_hold_the_additional_charge_until_topped_up(self):
        usage=self.settled(Decimal('0.5'),maximum=Decimal('1'))
        row=reconcile_usage(usage,Decimal('1'),'INV-SYNTH-0002',self.user)
        self.assertEqual(row.ledger_status,'pending_funds');self.assertEqual(row.charge_delta,Decimal('0.75'))
        self.assertFalse(LedgerEntry.objects.filter(kind='reconciliation').exists())
        self.assertEqual(self.balances(),(Decimal('9.25'),Decimal('0')))
        self.assertEqual(apply_pending_reconciliations(),[])
        report=audit_report()
        self.assertTrue(report['all_checks_pass']);self.assertEqual(report['reconciliation_summary']['pending_funds'],1)
        self.assertEqual(report['rows'][0]['reconciliation']['ledger_status'],'pending_funds')
        fund(self.paid,Decimal('5'),'payment:policy-topup')
        self.assertEqual([applied.pk for applied in apply_pending_reconciliations()],[row.pk])
        row.refresh_from_db();self.assertEqual(row.ledger_status,'applied')
        self.assertEqual(LedgerEntry.objects.get(kind='reconciliation').amount,Decimal('-0.75'))
        self.assertEqual(self.balances(),(Decimal('9.25'),Decimal('4.25')))
        self.assertEqual(apply_pending_reconciliations(),[])
        self.assertEqual(LedgerEntry.objects.filter(kind='reconciliation').count(),1)
        self.assertTrue(AuditEvent.objects.filter(action='usage.reconciliation_applied',target=str(usage.job_id)).exists())
        report=audit_report()
        self.assertTrue(report['all_checks_pass']);self.assertEqual(report['reconciliation_summary']['pending_funds'],0)

    def test_exactly_one_reconciliation_per_usage_and_zero_delta_records_evidence_only(self):
        usage=self.settled(Decimal('0.5'))
        row=reconcile_usage(usage,Decimal('0.5'),'INV-SYNTH-0003',self.user)
        self.assertEqual(row.charge_delta,0);self.assertEqual(row.ledger_status,'applied')
        self.assertFalse(LedgerEntry.objects.filter(kind='reconciliation').exists())
        with self.assertRaises(ValidationError):reconcile_usage(usage,Decimal('0.4'),'INV-SYNTH-0004',self.user)
        self.assertEqual(CostReconciliation.objects.count(),1)
        with self.assertRaises(ValidationError):reconcile_usage(self.settled(Decimal('0.1'),key='policy-no-evidence'),Decimal('0.1'),'   ',self.user)
        with self.assertRaises(ValidationError):reconcile_usage(Usage.objects.get(job__request_key='policy-no-evidence'),Decimal('-1'),'INV-SYNTH-0005',self.user)
        row.reconciled_cost=Decimal('9')
        with self.assertRaises(ValidationError):row.save()
        with self.assertRaises(ValidationError):row.delete()
        self.assertEqual(CostReconciliation.objects.get(pk=row.pk).reconciled_cost,Decimal('0.5'))
        self.assertEqual(self.balances(),(Decimal('9.1'),Decimal('0')))

    def test_audit_report_keeps_existing_keys_and_adds_policy_keys(self):
        self.settled(Decimal('0.5'))
        report=audit_report()
        for key in ['checked_at','scope','cost_basis','fingerprint_limit','rows','wallets','unsettled_provider_receipts','unresolved_jobs','all_checks_pass','durable_receipt_gaps','invoice_reconciliation','charge_policy','platform_costs','reconciliation_summary']:
            self.assertIn(key,report)
        self.assertEqual(set(report['platform_costs']['totals_by_kind']),{'fixed_overhead','absorbed_failure','absorbed_over_limit'})
        row=report['rows'][0]
        for key in ['defined_cost_usd','user_charge_usd','cost_evidence','invoice_reconciled','ledger','checks','discount_rate','configured_list_cost_usd','reconciliation','reconciliation_ledger','absorbed','absorbed_reversal_usd','absorbed_platform_cost_usd','absorbed_ledger']:
            self.assertIn(key,row)
        self.assertIsNone(row['reconciliation']);self.assertFalse(row['absorbed']);self.assertEqual(row['discount_rate'],'0')
        self.assertEqual(report['reconciliation_summary'],{'reconciled_rows':0,'unreconciled_rows':1,'pending_funds':0,'absorbed_rows':0})


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES)
class AdminConsolePolicy(PolicyFixture,TestCase):
    password='Synthetic-console-proof-52831!'

    def admin_login(self):
        admin=User.objects.create_user(username='console-admin',email='console-admin@synthetic.invalid',password=self.password,verified_at=timezone.now(),is_staff=True)
        device=TOTPDevice.objects.create(user=admin,confirmed=True,name='Synthetic authenticator')
        code=str(totp(device.bin_key,step=device.step,t0=device.t0,digits=device.digits)).zfill(6)
        response=self.client.post('/login/',{'email':admin.email,'password':self.password,'otp':code})
        self.assertEqual(response.status_code,302)
        return admin

    def uncertain_job(self,key):
        # A live job records its mode at enqueue; the resolver treats a fixture-mode job as costless (round-2 F-5).
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key=key,config={'mode':'live'})
        reserve(job,Decimal('0.2'))
        with override_settings(AI_MODE='live'),patch('core.jobs.generation.generate',side_effect=TimeoutError('synthetic uncertain provider outcome')):run_one()
        job.refresh_from_db();self.assertEqual(job.state,'reconciliation')
        return job

    def test_non_staff_and_unverified_staff_cannot_use_policy_endpoints(self):
        usage=self.settled(Decimal('0.5'))
        job=self.uncertain_job('policy-uncertain-guard')
        endpoints=[(f'/console/usage/{usage.pk}/reconcile/',{'reconciled_cost':'0.4','evidence_reference':'INV-SYNTH-0006'}),
                   ('/console/platform-costs/',{'amount':'12','description':'Synthetic hosting'}),
                   (f'/console/jobs/{job.pk}/resolve/',{'outcome':'release_no_cost','evidence_note':'Synthetic provider console shows no request'})]
        self.client.force_login(self.user)
        for url,data in endpoints:
            with self.subTest(url=url,stage='clinical user'):self.assertEqual(self.client.post(url,data).status_code,404)
        self.user.is_staff=True;self.user.save(update_fields=['is_staff']);self.client.force_login(self.user)
        for url,data in endpoints:
            with self.subTest(url=url,stage='staff without MFA'):
                response=self.client.post(url,data)
                self.assertEqual(response.status_code,302);self.assertEqual(response.url,'/mfa/')
        # The views refuse on their own as well, independently of the middleware redirect.
        factory=RequestFactory()
        for view,args,(url,data) in [(views.admin_reconcile_usage,(usage.pk,),endpoints[0]),(views.admin_platform_cost,(),endpoints[1]),(views.admin_resolve_job,(job.pk,),endpoints[2])]:
            request=factory.post(url,data);request.user=self.user;request.user.is_verified=lambda:False
            with self.subTest(view=view.__name__),self.assertRaises(Http404):view(request,*args)
        self.assertFalse(CostReconciliation.objects.exists());self.assertFalse(PlatformCost.objects.exists())
        job.refresh_from_db();self.assertEqual(job.state,'reconciliation')

    def test_staff_with_mfa_can_reconcile_record_overhead_and_resolve_uncertain_jobs(self):
        admin=self.admin_login()
        fund(self.paid,Decimal('5'),'payment:policy-console')
        usage=self.settled(Decimal('0.5'))
        ledger_before=LedgerEntry.objects.count()
        response=self.client.post(f'/console/usage/{usage.pk}/reconcile/',{'reconciled_cost':'0.4','evidence_reference':'INV-SYNTH-0007','provider_credit_applied':'0.05','note':'Synthetic invoice line'})
        self.assertEqual(response.status_code,302)
        row=CostReconciliation.objects.get(usage=usage)
        self.assertEqual(row.recorded_by,admin);self.assertEqual(row.charge_delta,Decimal('-0.15'));self.assertEqual(row.provider_credit_applied,Decimal('0.05'))
        self.assertEqual(self.balances(),(Decimal('9.4'),Decimal('5')))
        self.assertEqual(self.client.post(f'/console/usage/{usage.pk}/reconcile/',{'reconciled_cost':'0.3','evidence_reference':'INV-SYNTH-0008'}).status_code,400)
        self.assertEqual(self.client.post(f'/console/usage/{usage.pk}/reconcile/',{'reconciled_cost':'0.3'}).status_code,400)
        self.assertEqual(CostReconciliation.objects.count(),1)
        self.assertEqual(LedgerEntry.objects.count(),ledger_before+1)
        self.assertTrue(AuditEvent.objects.filter(action='usage.reconcile',actor=admin,target=str(usage.job_id)).exists())
        overhead=self.client.post('/console/platform-costs/',{'amount':'40.00','description':'Synthetic VPS hosting','period_start':'2026-09-01','period_end':'2026-09-30','evidence_reference':'STATEMENT-SYNTH-9'})
        self.assertEqual(overhead.status_code,302)
        cost=PlatformCost.objects.get(kind='fixed_overhead')
        self.assertEqual(cost.amount,Decimal('40'));self.assertEqual(cost.recorded_by,admin);self.assertEqual(str(cost.period_start),'2026-09-01')
        self.assertEqual(self.client.post('/console/platform-costs/',{'amount':'-1','description':'Synthetic'}).status_code,400)
        self.assertEqual(self.client.post('/console/platform-costs/',{'amount':'1','description':'Synthetic','period_start':'2026-09-30','period_end':'2026-09-01'}).status_code,400)
        self.assertEqual(PlatformCost.objects.count(),1)
        self.assertEqual(LedgerEntry.objects.count(),ledger_before+1)
        self.assertEqual(self.balances(),(Decimal('9.4'),Decimal('5')))
        report=audit_report()
        self.assertTrue(report['all_checks_pass']);self.assertEqual(Decimal(report['platform_costs']['totals_by_kind']['fixed_overhead']),Decimal('40'))
        absorb=self.uncertain_job('policy-uncertain-absorb');release=self.uncertain_job('policy-uncertain-release')
        self.promo.refresh_from_db();self.assertEqual(self.promo.reserved,Decimal('0.6'))
        url=f'/console/jobs/{absorb.pk}/resolve/'
        self.assertEqual(self.client.post(url,{'outcome':'release_no_cost','evidence_note':'short'}).status_code,400)
        self.assertEqual(self.client.post(url,{'outcome':'absorb_platform_failure','evidence_note':'Provider console shows a completed request'}).status_code,400)
        self.assertEqual(self.client.post(url,{'outcome':'unknown','evidence_note':'Provider console shows a completed request'}).status_code,400)
        absorb.refresh_from_db();self.assertEqual(absorb.state,'reconciliation')
        response=self.client.post(url,{'outcome':'absorb_platform_failure','evidence_note':'Provider console shows request req_synthetic billed','actual_cost':'0.05'})
        self.assertEqual(response.status_code,302)
        absorb.refresh_from_db()
        self.assertEqual(absorb.state,'failed');self.assertEqual(absorb.error,'Resolved by administrator: provider cost absorbed by QuillMD.')
        self.assertEqual(Reservation.objects.get(job=absorb).state,'released')
        absorbed=PlatformCost.objects.get(job=absorb,kind='absorbed_failure')
        self.assertEqual(absorbed.amount,Decimal('0.05'));self.assertEqual(absorbed.evidence_reference,'Provider console shows request req_synthetic billed');self.assertEqual(absorbed.recorded_by,admin)
        self.assertFalse(Usage.objects.filter(job=absorb).exists());self.assertFalse(LedgerEntry.objects.filter(job=absorb).exists())
        self.assertEqual(self.client.post(url,{'outcome':'release_no_cost','evidence_note':'Provider console shows nothing further'}).status_code,409)
        response=self.client.post(f'/console/jobs/{release.pk}/resolve/',{'outcome':'release_no_cost','evidence_note':'Provider console shows no request for this job'})
        self.assertEqual(response.status_code,302)
        release.refresh_from_db()
        self.assertEqual(release.state,'failed');self.assertEqual(release.error,'Resolved by administrator: no provider cost evidenced.')
        self.assertEqual(Reservation.objects.get(job=release).state,'released');self.assertFalse(PlatformCost.objects.filter(job=release).exists())
        self.promo.refresh_from_db();self.assertEqual(self.promo.reserved,0)
        self.assertEqual(self.balances(),(Decimal('9.4'),Decimal('5')))
        self.assertEqual(AuditEvent.objects.filter(action='job.resolved',actor=admin).count(),2)
        report=audit_report()
        self.assertTrue(report['all_checks_pass']);self.assertEqual(report['unresolved_jobs'],[])
        self.assertEqual(Decimal(report['platform_costs']['totals_by_kind']['absorbed_failure']),Decimal('0.05'))
        page=self.client.get('/console/')
        self.assertEqual(page.status_code,200)
        for text in ['Cost reconciliation','Platform costs (never charged to users)','INV-SYNTH-0007','Synthetic VPS hosting','Resolved by administrator']:
            self.assertContains(page,text)


def unadopted_live_result(notes,request_id):
    invalid=SimpleNamespace(stop_reason='end_turn',content=[SimpleNamespace(type='text',text='not valid provider JSON')])
    invalid.model_dump=lambda **kwargs:{'stop_reason':'end_turn'}
    units={'input_tokens':100,'output_tokens':10,'cached_input_tokens':0,'cache_creation_tokens':0}
    rates={'input_per_million':'1000','output_per_million':'2500','cached_per_million':'0'}
    return ({'anthropic_response':invalid,'notes':notes,'fields':[]},Decimal('0.125'),units,rates,'anthropic:synthetic-model',request_id,False)


@override_settings(ADMIN_SITE=False,STORAGES=STORAGES,AI_MODE='live')
class RefutationRegressions(PolicyFixture,TestCase):
    """Counterexamples found by the independent refutation pass, now asserting the corrected behaviour."""
    password='Synthetic-console-proof-52831!'

    def failed_unabsorbed_job(self,key):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key=key)
        reserve(job,Decimal('0.2'))
        with patch('core.jobs.generation.generate',return_value=unadopted_live_result(self.encounter.notes,f'req_{key}')),patch('core.jobs.absorb_failed_job',side_effect=RuntimeError('synthetic transient reversal failure')):
            self.assertTrue(run_one())
        job.refresh_from_db();self.assertEqual(job.state,'failed');self.assertEqual(self.balances(),(Decimal('9.8125'),Decimal('0')))
        return job,Usage.objects.get(job=job)

    def admin_login(self):
        admin=User.objects.create_user(username='console-admin',email='console-admin@synthetic.invalid',password=self.password,verified_at=timezone.now(),is_staff=True)
        device=TOTPDevice.objects.create(user=admin,confirmed=True,name='Synthetic authenticator')
        code=str(totp(device.bin_key,step=device.step,t0=device.t0,digits=device.digits)).zfill(6)
        self.assertEqual(self.client.post('/login/',{'email':admin.email,'password':self.password,'otp':code}).status_code,302)
        return admin

    def test_credit_back_then_absorb_reverses_only_the_net_charge(self):
        job,usage=self.failed_unabsorbed_job('regress-credit-then-absorb')
        row=reconcile_usage(usage,Decimal('0.05'),'INV-SYNTH-R1',self.user)
        self.assertEqual(row.ledger_status,'applied');self.assertEqual(self.balances(),(Decimal('9.925'),Decimal('0')))
        absorb_failed_job(job);absorb_failed_job(job)
        self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        self.assertEqual(LedgerEntry.objects.get(job=job,kind='absorbed').amount,Decimal('0.075'))
        self.assertEqual(PlatformCost.objects.get(job=job).amount,Decimal('0.05'))
        report=audit_report();checks=report['rows'][0]['checks']
        self.assertTrue(report['all_checks_pass']);self.assertTrue(checks['absorbed_reversal_matches_usage_debits']);self.assertTrue(checks['reconciliation_wallets_valid'])

    def test_pending_additional_charge_is_never_applied_after_absorption(self):
        job,usage=self.failed_unabsorbed_job('regress-pending-then-absorb')
        row=reconcile_usage(usage,Decimal('0.5'),'INV-SYNTH-R2',self.user)
        self.assertEqual(row.ledger_status,'pending_funds')
        absorb_failed_job(job)
        row.refresh_from_db();self.assertEqual(row.ledger_status,'absorbed');self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        fund(self.paid,Decimal('5'),'payment:regress-topup')
        self.assertEqual(apply_pending_reconciliations(),[]);self.assertEqual(self.balances(),(Decimal('10'),Decimal('5')))
        self.assertFalse(LedgerEntry.objects.filter(kind='reconciliation').exists())
        report=audit_report();self.assertTrue(report['all_checks_pass']);self.assertTrue(report['rows'][0]['checks']['no_reconciliation_pending_after_absorption'])

    def test_pending_charge_held_then_absorbed_is_marked_when_applied_later(self):
        job,usage=self.failed_unabsorbed_job('regress-pending-later')
        row=reconcile_usage(usage,Decimal('0.5'),'INV-SYNTH-R2b',self.user)
        LedgerEntry.objects.create(wallet=self.promo,amount=Decimal('0.1875'),kind='absorbed',key=f'absorbed:{job.pk}:{self.promo.pk}',description='synthetic prior reversal',job=job,balance_after=Decimal('10'))
        Wallet.objects.filter(pk=self.promo.pk).update(balance=Decimal('10'))
        fund(self.paid,Decimal('5'),'payment:regress-topup-2')
        self.assertEqual(apply_pending_reconciliations(),[])
        row.refresh_from_db();self.assertEqual(row.ledger_status,'absorbed');self.assertEqual(self.balances(),(Decimal('10'),Decimal('5')))

    def test_absorb_refuses_a_job_that_is_not_failed(self):
        usage=self.settled(Decimal('0.5'),key='regress-succeeded')
        with self.assertRaises(ValidationError):absorb_failed_job(usage.job)
        self.assertFalse(LedgerEntry.objects.filter(kind='absorbed').exists());self.assertFalse(PlatformCost.objects.exists())
        self.assertEqual(self.balances(),(Decimal('9.25'),Decimal('0')))

    def test_discounted_transcription_settles_exactly(self):
        recording=private_path('uploads/regress.wav');recording.parent.mkdir(parents=True,exist_ok=True);recording.write_bytes(wav_bytes(tag='regress'))
        env={'QUILLMD_PROVIDER_DISCOUNT_RATE':'0.125','QUILLMD_DEEPGRAM_RATE_PER_MINUTE':'0.006','QUILLMD_DEEPGRAM_RATE_PER_SECOND':'','DEEPGRAM_API_KEY':'synthetic-placeholder-not-a-key'}
        data={'results':{'channels':[{'alternatives':[{'transcript':'synthetic transcript'}]}]},'metadata':{'duration':12.345678,'request_id':'dg_regress'}}
        response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:data)
        with patch.dict(os.environ,env):
            job=enqueue(self.encounter,self.user,kind='transcription',input_path='uploads/regress.wav')
            with patch('core.jobs.httpx.post',return_value=response):self.assertTrue(run_one())
        job.refresh_from_db();self.assertEqual(job.state,'succeeded')
        usage=Usage.objects.get(job=job);receipt=ProviderReceipt.objects.get(job=job)
        # 12.345678 s x 0.006/min = 0.0012345678 list; x 0.875 = 0.0010802468250 -> half-even tie keeps ...682.
        self.assertEqual(usage.actual_cost,Decimal('0.00108024682'));self.assertEqual(receipt.actual_cost,usage.actual_cost)
        self.assertEqual(usage.charged_cost,usage.actual_cost*Decimal('1.5'));self.assertEqual(usage.rates['discount_rate'],'0.125')
        self.assertEqual(Reservation.objects.filter(job=job,state='held').count(),0)
        report=audit_report();self.assertTrue(report['all_checks_pass']);self.assertEqual(report['unresolved_jobs'],[])

    def test_resolving_an_uncertain_job_that_already_settled_reverses_the_charge(self):
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='regress-stranded')
        reserve(job,Decimal('0.2'))
        Job.objects.filter(pk=job.pk).update(state='running',started_at=timezone.now()-timedelta(minutes=6))
        units={'input_tokens':125,'output_tokens':0,'cached_input_tokens':0,'cache_creation_tokens':0}
        settle(job,Decimal('0.125'),units,AUDITABLE_RATES,'anthropic:synthetic-model','req_regress-stranded',provider_resource_id='msg_regress-stranded')
        mark_stale();job.refresh_from_db();self.assertEqual(job.state,'reconciliation');self.assertEqual(self.balances(),(Decimal('9.8125'),Decimal('0')))
        self.admin_login()
        with override_settings(ADMIN_SITE=True):
            response=self.client.post(f'/console/jobs/{job.pk}/resolve/',{'outcome':'absorb_platform_failure','evidence_note':'Provider console shows one billed request','actual_cost':'9'})
        self.assertEqual(response.status_code,302)
        job.refresh_from_db();self.assertEqual(job.state,'failed');self.assertIn('settled provider cost absorbed',job.error)
        self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        self.assertEqual(PlatformCost.objects.get(job=job).amount,Decimal('0.125'))  # the settled amount, never the typed one
        report=audit_report();self.assertTrue(report['all_checks_pass']);self.assertEqual(report['unresolved_jobs'],[])

    def test_audit_rejects_a_reconciliation_credit_on_a_foreign_wallet(self):
        usage=self.settled(Decimal('0.5'),key='regress-foreign')
        other=self.make_scope('policy-other')[0];foreign=Wallet.objects.get(user=other,kind='promo')
        CostReconciliation.objects.create(usage=usage,reconciled_cost=Decimal('0.3'),evidence_reference='INV-SYNTH-FOREIGN',recorded_by=self.user,charge_delta=Decimal('-0.3'),ledger_status='applied')
        foreign.balance+=Decimal('0.3');foreign.save(update_fields=['balance'])
        LedgerEntry.objects.create(wallet=foreign,amount=Decimal('0.3'),kind='reconciliation',key=f'reconciliation:{usage.pk}:{foreign.pk}',description='misdirected credit',job_id=usage.job_id,balance_after=foreign.balance)
        report=audit_report();row=[r for r in report['rows'] if r['job_id']==str(usage.job_id)][0]
        self.assertFalse(row['checks']['reconciliation_wallets_valid']);self.assertFalse(report['all_checks_pass'])

    def test_negative_zero_discount_is_plain_zero(self):
        with patch.dict(os.environ,{'QUILLMD_PROVIDER_DISCOUNT_RATE':'-0'}):
            config=configuration()
        with patch.dict(os.environ,{'QUILLMD_PROVIDER_DISCOUNT_RATE':'0'}):
            plain=configuration()
        self.assertEqual(config['discount_rate'],'0');self.assertEqual(config['pricing_version'],plain['pricing_version'])

    def test_reconciled_cost_precision_is_eleven_decimals(self):
        usage=self.settled(Decimal('0.4'),maximum=Decimal('0.5'),key='regress-precision')
        with self.assertRaises(ValidationError):reconcile_usage(usage,Decimal('0.400000000001'),'INV-SYNTH-P12',self.user)
        row=reconcile_usage(usage,Decimal('0.40000000001'),'INV-SYNTH-P11',self.user)
        self.assertEqual(row.charge_delta,Decimal('0.000000000015'));self.assertEqual(row.ledger_status,'pending_funds')

    def test_absorbed_status_admits_no_reconciliation_entries(self):
        job,usage=self.failed_unabsorbed_job('regress-r2-absorbed-entries')
        absorb_failed_job(job)
        row=reconcile_usage(usage,Decimal('0.05'),'INV-SYNTH-R2A',self.user);self.assertEqual(row.ledger_status,'absorbed')
        self.promo.refresh_from_db();self.promo.balance+=Decimal('0.5');self.promo.save(update_fields=['balance'])
        LedgerEntry.objects.create(wallet=self.promo,amount=Decimal('0.5'),kind='reconciliation',key=f'reconciliation:{usage.pk}:{self.promo.pk}',description='illegitimate credit',job=job,balance_after=self.promo.balance)
        report=audit_report();reported=[r for r in report['rows'] if r['job_id']==str(job.pk)][0]
        self.assertFalse(reported['checks']['reconciliation_delta_arithmetic']);self.assertFalse(report['all_checks_pass'])

    def test_audit_requires_the_proportional_credit_split(self):
        fund(self.paid,Decimal('5'),'payment:regress-r2-split')
        usage=self.settled(Decimal('8'),key='regress-r2-split')
        CostReconciliation.objects.create(usage=usage,reconciled_cost=Decimal('4'),evidence_reference='INV-SYNTH-SPLIT',recorded_by=self.user,charge_delta=Decimal('-6'),ledger_status='applied')
        self.paid.refresh_from_db();self.paid.balance+=Decimal('6');self.paid.save(update_fields=['balance'])
        LedgerEntry.objects.create(wallet=self.paid,amount=Decimal('6'),kind='reconciliation',key=f'reconciliation:{usage.pk}:{self.paid.pk}',description='whole credit to the paid wallet',job=usage.job,balance_after=self.paid.balance)
        report=audit_report();reported=[r for r in report['rows'] if r['job_id']==str(usage.job_id)][0]
        self.assertTrue(reported['checks']['reconciliation_wallets_valid']);self.assertFalse(reported['checks']['reconciliation_credit_split_proportional']);self.assertFalse(report['all_checks_pass'])

    def test_audit_rejects_policy_entries_without_a_job(self):
        self.settled(Decimal('0.5'),key='regress-r2-orphan')
        self.promo.refresh_from_db();self.promo.balance+=Decimal('5');self.promo.save(update_fields=['balance'])
        LedgerEntry.objects.create(wallet=self.promo,amount=Decimal('5'),kind='absorbed',key='absorbed:orphan',description='orphan',job=None,balance_after=self.promo.balance)
        report=audit_report()
        self.assertEqual(report['ledger_policy']['orphan_policy_entries'],1);self.assertFalse(report['ledger_policy']['checks']['policy_ledger_entries_bound_to_jobs']);self.assertFalse(report['all_checks_pass'])

    @override_settings(AI_MODE='fixture')
    def test_resolving_a_stale_fixture_job_records_no_platform_cost(self):
        original=self.encounter
        draft=Encounter.objects.create(department=original.department,patient=original.patient,template_version=original.template_version,created_by=original.created_by,service_date=original.service_date,notes=original.notes)
        job=enqueue(draft,self.user)
        Job.objects.filter(pk=job.pk).update(state='running',started_at=timezone.now()-timedelta(minutes=6))
        mark_stale();job.refresh_from_db();self.assertEqual(job.state,'reconciliation')
        self.admin_login()
        with override_settings(ADMIN_SITE=True):
            response=self.client.post(f'/console/jobs/{job.pk}/resolve/',{'outcome':'absorb_platform_failure','evidence_note':'Fixture job stalled in a synthetic test','actual_cost':'0.05'})
        self.assertEqual(response.status_code,302)
        job.refresh_from_db();self.assertEqual(job.state,'failed');self.assertIn('fixture',job.error)
        self.assertFalse(PlatformCost.objects.exists());self.assertEqual(self.balances(),(Decimal('10'),Decimal('0')))
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_stripe_top_up_applies_a_reconciliation_held_for_funds(self):
        from core.billing import credit_payment
        from core.models import Payment
        usage=self.settled(Decimal('0.5'),maximum=Decimal('1'),key='regress-r2-topup')
        row=reconcile_usage(usage,Decimal('0.9'),'INV-SYNTH-TOPUP',self.user);self.assertEqual(row.ledger_status,'pending_funds')
        payment=Payment.objects.create(user=self.user,wallet=self.paid,amount_cents=500,stripe_session='cs_test_regress_topup')
        session={'id':payment.stripe_session,'payment_status':'paid','currency':'usd','amount_total':500,'metadata':{'payment_id':str(payment.pk)},'payment_intent':'pi_test_regress_topup','mode':'payment'}
        with self.captureOnCommitCallbacks(execute=True):credit_payment(payment,session)
        row.refresh_from_db();self.assertEqual(row.ledger_status,'applied')
        self.assertEqual(self.balances(),(Decimal('9.25'),Decimal('5')-Decimal('0.6')))
        self.assertTrue(AuditEvent.objects.filter(action='usage.reconciliation_applied',target=str(usage.job_id)).exists())
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_twelve_decimal_list_cost_settles_at_zero_discount_and_never_exceeds_list(self):
        self.assertEqual(discounted_cost(Decimal('0.000000000019'),Decimal('0')),Decimal('0.00000000001'))
        self.assertEqual(discounted_cost(Decimal('0.000000000019'),Decimal('0.01')),Decimal('0.00000000001'))
        self.assertLessEqual(discounted_cost(Decimal('0.000000000019'),Decimal('0.01')),Decimal('0.000000000019'))
        job=Job.objects.create(encounter=self.encounter,user=self.user,request_key='regress-r2-12dp')
        reserve(job,Decimal('0.2'))
        units={'input_tokens':1,'output_tokens':0,'cached_input_tokens':0,'cache_creation_tokens':0}
        rates={'input_per_million':'0.000019','output_per_million':'0','cached_per_million':'0'}
        cost=discounted_cost(Decimal('0.000000000019'),Decimal('0'))
        usage=settle(job,cost,units,rates,'anthropic:synthetic-model','req_regress-12dp',provider_resource_id='msg_regress-12dp')
        self.assertEqual(usage.charged_cost,cost*Decimal('1.5'))

    def test_audit_accepts_the_split_the_writer_produced_in_either_wallet_order(self):
        seen=set()
        for attempt in range(12):
            scope=self.make_scope(f'policy-order-{attempt}');user=scope[0];encounter=scope[5]
            promo=Wallet.objects.get(user=user,kind='promo');paid=Wallet.objects.get(user=user,kind='paid')
            fund(paid,Decimal('6.5'),f'payment:policy-order-{attempt}')
            job=Job.objects.create(encounter=encounter,user=user,request_key=f'policy-order-{attempt}')
            reserve(job,Decimal('11'))
            units={'input_tokens':11000,'output_tokens':0,'cached_input_tokens':0,'cache_creation_tokens':0}
            usage=settle(job,Decimal('11'),units,AUDITABLE_RATES,'anthropic:synthetic-model',f'req_order_{attempt}',provider_resource_id=f'msg_order_{attempt}')
            job.state='succeeded';job.finished_at=timezone.now();job.save(update_fields=['state','finished_at'])
            row=reconcile_usage(usage,Decimal('10'),f'INV-SYNTH-ORDER-{attempt}',user)
            self.assertEqual(row.charge_delta,Decimal('-1.5'))
            seen.add(str(promo.pk)<str(paid.pk))
            report=audit_report();reported=[r for r in report['rows'] if r['job_id']==str(job.pk)][0]
            self.assertTrue(reported['checks']['reconciliation_credit_split_proportional'],reported['checks'])
            self.assertTrue(report['all_checks_pass'])
            if len(seen)==2:break
        self.assertEqual(seen,{True,False},'Both wallet-id orders must be exercised.')

    def test_a_top_up_applies_only_its_own_payer_held_charges_and_records_that_payer(self):
        from core.billing import credit_payment
        from core.models import Payment
        other=self.make_scope('policy-tenant-b');other_user=other[0];other_encounter=other[5]
        other_paid=Wallet.objects.get(user=other_user,kind='paid')
        job=Job.objects.create(encounter=other_encounter,user=other_user,request_key='policy-tenant-b-job');reserve(job,Decimal('1'))
        units={'input_tokens':500,'output_tokens':0,'cached_input_tokens':0,'cache_creation_tokens':0}
        usage=settle(job,Decimal('0.5'),units,AUDITABLE_RATES,'anthropic:synthetic-model','req_tenant_b',provider_resource_id='msg_tenant_b')
        job.state='succeeded';job.finished_at=timezone.now();job.save(update_fields=['state','finished_at'])
        row=reconcile_usage(usage,Decimal('0.9'),'INV-SYNTH-TENANT-B',other_user);self.assertEqual(row.ledger_status,'pending_funds')
        payment=Payment.objects.create(user=self.user,wallet=self.paid,amount_cents=500,stripe_session='cs_test_tenant_a')
        with self.captureOnCommitCallbacks(execute=True):
            credit_payment(payment,{'id':payment.stripe_session,'payment_status':'paid','currency':'usd','amount_total':500,'metadata':{'payment_id':str(payment.pk)},'payment_intent':'pi_test_tenant_a','mode':'payment'})
        row.refresh_from_db();self.assertEqual(row.ledger_status,'pending_funds')
        self.assertFalse(AuditEvent.objects.filter(action='usage.reconciliation_applied').exists())
        payment_b=Payment.objects.create(user=other_user,wallet=other_paid,amount_cents=500,stripe_session='cs_test_tenant_b')
        with self.captureOnCommitCallbacks(execute=True):
            credit_payment(payment_b,{'id':payment_b.stripe_session,'payment_status':'paid','currency':'usd','amount_total':500,'metadata':{'payment_id':str(payment_b.pk)},'payment_intent':'pi_test_tenant_b','mode':'payment'})
        row.refresh_from_db();self.assertEqual(row.ledger_status,'applied')
        event=AuditEvent.objects.get(action='usage.reconciliation_applied',target=str(job.pk));self.assertEqual(event.actor_id,other_user.pk)
        other_paid.refresh_from_db();self.assertEqual(other_paid.balance,Decimal('5')-Decimal('0.6'))
        self.assertTrue(audit_report()['all_checks_pass'])

    def test_funds_freed_by_a_released_reservation_apply_a_held_charge(self):
        from core.billing import release
        fund(self.paid,Decimal('1.4'),'payment:policy-release-funds')
        usage=self.settled(Decimal('0.5'),maximum=Decimal('1'),key='policy-release-usage')   # promo 10 -> 9.25
        self.settled(Decimal('6'),key='policy-release-drain')             # promo 9.25 -> 0.25, so the next reservation reaches the paid wallet
        blocker=Job.objects.create(encounter=self.encounter,user=self.user,request_key='policy-release-blocker',config={'mode':'live'})
        reserve(blocker,Decimal('1.0'))   # 1.5 reserved: 0.25 promo + 1.25 paid; paid available becomes 0.15
        self.paid.refresh_from_db();available=self.paid.balance-self.paid.reserved;self.assertEqual(available,Decimal('0.15'))
        row=reconcile_usage(usage,Decimal('0.9'),'INV-SYNTH-RELEASE',self.user)
        self.assertEqual(row.charge_delta,Decimal('0.6'));self.assertGreater(row.charge_delta,available);self.assertEqual(row.ledger_status,'pending_funds')
        with self.captureOnCommitCallbacks(execute=True):release(blocker)
        row.refresh_from_db();self.assertEqual(row.ledger_status,'applied')
        self.paid.refresh_from_db();self.assertEqual(self.paid.reserved,0);self.assertEqual(self.paid.balance,Decimal('1.4')-Decimal('0.6'))
        self.assertTrue(audit_report()['all_checks_pass'])
