"""Finite independent-refutation regressions. No network or real provider evidence."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone
from core import batch_jobs as jobs, generation as g
from core.management.commands.audit_billing import audit_report
from core.billing import reconciliation
from core.models import Job, Usage, Reservation, ProviderReceipt, PlatformCost, LedgerEntry
from .test_generation_batch import BatchFixture, SETTINGS


@override_settings(**SETTINGS)
class BatchCloseout(BatchFixture, TestCase):
    def resolve(self, part, *, amount=None):
        self.user.is_staff=True;self.user.save(update_fields=['is_staff'])
        data={'outcome':'release_no_cost','evidence_note':'Synthetic administrative provider evidence closeout'}
        if amount is not None:data.update(outcome='absorb_platform_failure',actual_cost=str(amount))
        request=RequestFactory().post('/console/jobs/resolve/',data);request.user=self.user
        with patch('django.contrib.messages.success'):
            return jobs.resolve_view(request,part.job_id)

    def stale(self, part):
        Job.objects.filter(pk=part.job_id).update(started_at=timezone.now()-timedelta(minutes=6))
        jobs.mark_stale()

    def assert_no_user_cost(self, batch, late=None):
        self.assertEqual(sum(LedgerEntry.objects.filter(job__generation_part__batch=batch).values_list('amount',flat=True),Decimal(0)),0)
        self.assertFalse(Reservation.objects.filter(job__generation_part__batch=batch,state='held').exists())
        self.assertTrue(all(row['status']=='matched' for row in reconciliation()))
        self.encounter.refresh_from_db();self.assertEqual(self.encounter.answers,{})
        report=audit_report()
        if late is None:self.assertTrue(report['all_checks_pass'],report);return
        # A late receipt nothing accounts for yet fails the audit on exactly that check, naming its child
        # (audit_billing.provider_receipt_policy, 2026-09-30); everything else still passes.
        self.assertFalse(report['all_checks_pass'])
        self.assertEqual(report['receipt_policy']['late_provider_receipts'],[str(late)])
        self.assertEqual(report['receipt_policy']['checks'],{'provider_receipts_settled_absorbed_or_held':True,
                                                             'late_provider_receipts_resolved':False})
        self.assertTrue(all(all(row['checks'].values()) for row in report['rows']+report['wallets']+report['generation_batches']))
        for section in ('ledger_policy','cancellation_policy','hold_policy'):self.assertTrue(all(report[section]['checks'].values()))

    def test_recorded_final_interruption_financial_closeout_closes_staged_sibling(self):
        batch=self.admit();calls,call=self.fake(batch);store=jobs.store_response
        def interrupted(batch,part,raw,receipt):
            store(batch,part,raw,receipt)
            if part.ordinal==2:raise SystemExit('Synthetic death after final durable response')
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            jobs.run_one()
            with patch('core.batch_jobs.store_response',side_effect=interrupted),self.assertRaises(SystemExit):jobs.run_one()
            part=batch.parts.get(ordinal=2);self.stale(part)
            self.assertEqual(self.resolve(part).status_code,302)
            self.assertFalse(jobs.pending(self.encounter))
            self.assertFalse(jobs.run_one());self.assertEqual(len(calls),2)
        self.assertEqual(set(batch.parts.values_list('job__state',flat=True)),{'failed'})
        self.assertEqual(PlatformCost.objects.filter(job__generation_part__batch=batch,kind='absorbed_failure').count(),2)
        self.assert_no_user_cost(batch)
        self.assertEqual(self.resolve(part).status_code,409)

    def late_response(self, *, new_batch=False, prior_amount=None, unreadable=False):
        batch=self.admit();calls,call=self.fake(batch);store=jobs.store_response;replacement=[]
        def late(batch,part,raw,receipt,**kwargs):
            self.stale(part);self.assertEqual(self.resolve(part,amount=prior_amount).status_code,302)
            if new_batch:
                config,_=jobs.quote(self.encounter,g.configuration())
                replacement.append(jobs.enqueue(self.encounter,self.user,config).generation_part.batch)
            store(batch,part,raw,None if unreadable else receipt,**kwargs)
            if unreadable:raise ValidationError('Synthetic unreadable metering')
        with patch('anthropic.Anthropic') as provider:
            provider.return_value.messages.create.side_effect=call
            with patch('core.batch_jobs.store_response',side_effect=late):jobs.run_one()
            self.assertEqual(len(calls),1)
        batch.refresh_from_db();part=batch.parts.select_related('job').get(ordinal=1)
        self.assertEqual(batch.state,'failed')
        self.assertEqual(part.job.state,'reconciliation')
        self.assertTrue(jobs.pending(self.encounter))
        self.assertTrue(part.events.filter(kind='late_response_recorded').exists())
        self.assertEqual(part.events.filter(kind='send_intent').count(),1)
        receipt=ProviderReceipt.objects.filter(job=part.job).first()
        unaccounted=receipt is not None and not PlatformCost.objects.filter(job=part.job,kind='absorbed_failure',amount=receipt.actual_cost).exists()
        self.assert_no_user_cost(batch,late=part.job_id if unaccounted else None)
        if replacement:
            replacement[0].refresh_from_db();self.assertEqual(replacement[0].state,'queued')
            self.assertEqual(replacement[0].parts.filter(job__state='queued').count(),2)
            self.assertEqual(sum(Reservation.objects.filter(job__generation_part__batch=replacement[0],state='held').values_list('amount',flat=True),Decimal(0)),replacement[0].maximum_charge)
        return batch,part,replacement

    def test_late_known_receipt_reopens_only_accounting_and_can_be_absorbed(self):
        batch,part,_=self.late_response()
        receipt=ProviderReceipt.objects.get(job=part.job)
        self.assertEqual(self.resolve(part).status_code,302)
        self.assertEqual(PlatformCost.objects.get(job=part.job,kind='absorbed_failure').amount,receipt.actual_cost)
        self.assertFalse(Usage.objects.filter(job=part.job).exists())
        self.assertTrue(part.events.filter(kind='financially_resolved').exists())
        self.assertTrue(part.events.filter(kind='late_financially_resolved').exists())
        self.assertFalse(jobs.pending(self.encounter));self.assertFalse(jobs.run_one())
        self.assert_no_user_cost(batch)
        self.assertEqual(self.resolve(part).status_code,409)
        with self.assertRaisesMessage(ValidationError,'Only an interrupted'):jobs.recover_recorded(batch.pk,self.user)

    def test_late_response_preserves_replacement_batch_and_its_holds(self):
        batch,part,replacement=self.late_response(new_batch=True)
        self.assertEqual(self.resolve(part).status_code,302)
        replacement[0].refresh_from_db();self.assertEqual(replacement[0].state,'queued')
        self.assertTrue(jobs.pending(self.encounter));self.assert_no_user_cost(batch)
        self.assertFalse(replacement[0].events.filter(kind='send_intent').exists())

    def test_late_receipt_does_not_overwrite_conflicting_manual_platform_cost(self):
        batch,part,_=self.late_response(prior_amount=Decimal('0.50'))
        with self.assertRaisesMessage(ValidationError,'previously recorded platform cost'):self.resolve(part)
        self.assertEqual(PlatformCost.objects.get(job=part.job,kind='absorbed_failure').amount,Decimal('0.50'))
        part.job.refresh_from_db();self.assertEqual(part.job.state,'reconciliation')
        self.assertTrue(jobs.pending(self.encounter));self.assert_no_user_cost(batch,late=part.job_id)

    def test_late_unreadable_metering_remains_visible_until_explicit_resolution(self):
        batch,part,_=self.late_response(unreadable=True)
        self.assertFalse(ProviderReceipt.objects.filter(job=part.job).exists())
        self.assertTrue(hasattr(part,'response'))
        self.assertEqual(self.resolve(part,amount=Decimal('0.0012')).status_code,302)
        self.assertEqual(PlatformCost.objects.get(job=part.job,kind='absorbed_failure').amount,Decimal('0.0012'))
        self.assertFalse(jobs.pending(self.encounter));self.assert_no_user_cost(batch)

    def test_matching_prior_manual_cost_is_preserved_once(self):
        batch,part,_=self.late_response(prior_amount=Decimal('0.0012'))
        original=PlatformCost.objects.get(job=part.job,kind='absorbed_failure')
        self.assertEqual(self.resolve(part).status_code,302)
        after=PlatformCost.objects.get(job=part.job,kind='absorbed_failure')
        self.assertEqual(after.pk,original.pk);self.assertEqual(after.evidence_reference,original.evidence_reference)
        self.assertFalse(jobs.pending(self.encounter));self.assert_no_user_cost(batch)
