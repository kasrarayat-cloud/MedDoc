"""Repeatable read-only provider/ledger audit; never calls external providers."""
import hashlib
import json
import os
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum
from django.utils import timezone
from core.models import CostReconciliation, Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage, Wallet
from core.security import private_path


def recompute_list_cost(provider, units, rates):
    if provider.startswith(('anthropic:', 'openai:')):
        inputs=Decimal(units['input_tokens'])
        cached=Decimal(units.get('cached_input_tokens',0))
        outputs=Decimal(units['output_tokens'])
        written=Decimal(units.get('cache_creation_tokens',0))
        if provider.startswith('openai:'):inputs-=cached
        return (inputs*Decimal(rates['input_per_million'])+cached*Decimal(rates['cached_per_million'])+outputs*Decimal(rates['output_per_million'])+written*Decimal(rates['input_per_million'])*Decimal('1.25'))/1000000
    if provider.startswith('deepgram:'):
        return (Decimal(units['duration_seconds'])*Decimal(rates['usd_per_minute'])/60).quantize(Decimal(rates['cost_quantum_usd']),rounding=ROUND_HALF_EVEN)
    raise ValueError('No audited cost formula for provider')


def recompute_cost(provider, units, rates, simulated):
    """Configured estimate: list cost at the recorded rates, less the recorded discount fraction (absent means zero)."""
    from core.generation import discounted_cost
    if simulated:
        return Decimal('0')
    return discounted_cost(recompute_list_cost(provider,units,rates),Decimal(str(rates.get('discount_rate','0') or '0')))


def audit_report(file_reader=None):
    rows=[]
    for usage in Usage.objects.select_related('job__providerreceipt','job__encounter__department').order_by('created_at'):
        try:receipt=usage.job.providerreceipt
        except ProviderReceipt.DoesNotExist:receipt=None
        # Wallet-id order: the same order the writer's proportional split uses, so the audit recomputes the split it wrote.
        entries=list(LedgerEntry.objects.filter(job_id=usage.job_id,kind='usage').order_by('wallet_id').values('amount','wallet_id','wallet__kind','balance_after'))
        try:calculated=recompute_cost(usage.provider,usage.units,usage.rates,usage.simulated)
        except (KeyError,ValueError,ArithmeticError):calculated=None
        # Recording charge limit: the customer charge is exactly 1.5 × cost up to the approved limit (the settled holds); anything
        # above the limit must appear, exactly, as one 'absorbed_over_limit' platform cost and never in the customer's ledger.
        settled_holds=sum((r.amount for r in Reservation.objects.filter(job_id=usage.job_id,state='settled')),Decimal(0))
        limit=settled_holds if settled_holds>0 else None
        uncapped=usage.actual_cost*Decimal('1.5')
        over_rows=list(PlatformCost.objects.filter(job_id=usage.job_id,kind='absorbed_over_limit').values_list('amount',flat=True))
        checks={'recomputed_defined_cost_matches':calculated==usage.actual_cost,
                'exact_1_5_multiplier':usage.charged_cost==(min(uncapped,limit) if limit is not None else uncapped),
                'over_limit_absorbed_exactly':sum(over_rows,Decimal(0))==uncapped-usage.charged_cost and len(over_rows)==(1 if uncapped>usage.charged_cost else 0),
                'ledger_debit_matches':-sum((entry['amount'] for entry in entries),Decimal(0))==usage.charged_cost,
                'no_held_reservation':not Reservation.objects.filter(job_id=usage.job_id,state='held').exists(),
                'usage_scope_matches_job':usage.user_id==usage.job.user_id and usage.department_id==usage.job.encounter.department_id and usage.organization_id==usage.job.encounter.department.organization_id,
                'payer_matches_authorized_snapshot':not usage.job.payer or usage.payer==usage.job.payer}
        if receipt:checks['durable_receipt_matches']=all(getattr(receipt,k)==getattr(usage,k) for k in ['provider','provider_request_id','provider_resource_id','units','rates','actual_cost','simulated'])
        if 'list_cost_usd' in usage.rates:
            try:checks['recorded_list_cost_matches']=recompute_list_cost(usage.provider,usage.units,usage.rates)==Decimal(usage.rates['list_cost_usd'])
            except (KeyError,ValueError,ArithmeticError):checks['recorded_list_cost_matches']=False
        absorbed_entries=list(LedgerEntry.objects.filter(job_id=usage.job_id,kind='absorbed').values('amount','wallet_id','wallet__kind','balance_after'))
        absorbed_cost=PlatformCost.objects.filter(job_id=usage.job_id,kind='absorbed_failure').first()
        absorbed=bool(absorbed_entries or absorbed_cost)
        absorbed_reversal=sum((entry['amount'] for entry in absorbed_entries),Decimal(0))
        if usage.job.state=='failed' and not usage.simulated:
            # Billing boundary: a successful generation the user declined ('not_adopted:') stays charged and must NOT be absorbed;
            # every other settled failure is a platform failure ('platform_failure:', administrator resolutions, older rows) and must be.
            if usage.job.error.startswith('not_adopted:'):checks['user_declined_output_remains_charged']=not absorbed
            else:checks['failed_settled_usage_absorbed']=absorbed
        reconciliation=CostReconciliation.objects.filter(usage=usage).first()
        reconciliation_entries=list(LedgerEntry.objects.filter(job_id=usage.job_id,kind='reconciliation').values('amount','wallet_id','wallet__kind','balance_after'))
        if absorbed:
            # The reversal must return exactly the user's NET charge for the job (usage debits plus any reconciliation movement), per wallet.
            net={}
            for entry in entries+reconciliation_entries:net[entry['wallet_id']]=net.get(entry['wallet_id'],Decimal(0))+entry['amount']
            owed={wallet_id:-amount for wallet_id,amount in net.items() if amount<0}
            reversed_by_wallet={entry['wallet_id']:entry['amount'] for entry in absorbed_entries}
            # Evidence recorded before the absorption sets the platform cost; a later reconciliation leaves the immutable row at the estimate.
            expected_platform_cost=reconciliation.reconciled_cost if reconciliation and absorbed_cost is not None and reconciliation.created_at<absorbed_cost.created_at else usage.actual_cost
            checks['absorbed_reversal_matches_usage_debits']=(reversed_by_wallet==owed and absorbed_reversal==sum(owed.values(),Decimal(0))
                and absorbed_cost is not None and absorbed_cost.amount==expected_platform_cost and usage.job.state=='failed')
            checks['no_reconciliation_pending_after_absorption']=not (reconciliation and reconciliation.ledger_status=='pending_funds')
        if reconciliation_entries:
            # Credits may land only on wallets the usage debited; additional debits only on the recorded payer's paid wallet.
            debited_wallets={entry['wallet_id'] for entry in entries if entry['amount']<0}
            scope,_,identifier=(usage.payer or '').partition(':')
            payer_wallet=Wallet.objects.filter(kind='paid',**({'user_id':identifier} if scope=='user' else {'organization_id':identifier})).values_list('pk',flat=True).first() if identifier and scope in ('user','organization') else None
            checks['reconciliation_wallets_valid']=all((entry['amount']>0 and entry['wallet_id'] in debited_wallets) or (entry['amount']<0 and entry['wallet_id']==payer_wallet) for entry in reconciliation_entries)
            if reconciliation and reconciliation.charge_delta<0 and any(entry['amount']>0 for entry in reconciliation_entries):
                # Credits must follow the proportional split of the original debits, not merely land on a debited wallet.
                from core.billing import proportional_split
                from types import SimpleNamespace
                try:
                    expected={wallet_id:share for wallet_id,share in proportional_split([SimpleNamespace(wallet_id=entry['wallet_id'],amount=entry['amount']) for entry in entries],-reconciliation.charge_delta) if share}
                except Exception:expected=None
                checks['reconciliation_credit_split_proportional']=expected is not None and {entry['wallet_id']:entry['amount'] for entry in reconciliation_entries if entry['amount']>0}==expected
        if reconciliation:
            applied=sum((entry['amount'] for entry in reconciliation_entries),Decimal(0))
            reconciled_uncapped=reconciliation.reconciled_cost*Decimal('1.5')
            customer_after=min(reconciled_uncapped,limit) if limit is not None else reconciled_uncapped
            arithmetic=(reconciliation.charge_delta==customer_after-usage.charged_cost
                        and reconciliation.over_limit_delta==(reconciled_uncapped-customer_after)-(uncapped-usage.charged_cost))
            if reconciliation.ledger_status=='applied':ledger_ok=applied==-reconciliation.charge_delta
            elif reconciliation.ledger_status=='absorbed':ledger_ok=absorbed and not reconciliation_entries
            else:ledger_ok=reconciliation.charge_delta>0 and not reconciliation_entries
            checks['reconciliation_delta_arithmetic']=arithmetic and ledger_ok
        elif reconciliation_entries:checks['reconciliation_delta_arithmetic']=False
        result_integrity='not_recorded'
        if usage.job.result_path:
            try:
                path=private_path(usage.job.result_path)
                data=file_reader(path) if file_reader else path.read_bytes()
                result_integrity='matched' if hashlib.sha256(data).hexdigest()==usage.job.result_sha256 else 'mismatch'
            except (OSError,ValueError):result_integrity='unavailable'
            checks['stored_result_hash_matches']=result_integrity=='matched'
        rows.append({'job_id':str(usage.job_id),'user_id':str(usage.user_id),'department_id':str(usage.department_id),'organization_id':str(usage.organization_id),'payer':usage.payer,
            'provider':usage.provider,'http_request_id':usage.http_request_id or None,'provider_resource_id':usage.resource_id or None,
            'simulated':usage.simulated,'units':usage.units,'configured_rates':usage.rates,'defined_cost_usd':str(usage.actual_cost),'user_charge_usd':str(usage.charged_cost),
            'cost_evidence':usage.cost_evidence,'reconciliation_recorded':bool(reconciliation),'provider_evidence_reconciled':bool(reconciliation and reconciliation.provider_evidence_reconciled),'invoice_reconciled':bool(reconciliation and reconciliation.invoice_reconciled),'enqueue_config_recorded':bool(usage.job.config),
            'discount_rate':str(usage.rates.get('discount_rate','0') or '0'),'configured_list_cost_usd':usage.rates.get('list_cost_usd'),
            'reconciliation':{'evidence_kind':reconciliation.evidence_kind,'evidence_status':reconciliation.evidence_status,'reconciled_cost':str(reconciliation.reconciled_cost),'charge_delta':str(reconciliation.charge_delta),'ledger_status':reconciliation.ledger_status,'evidence_reference':reconciliation.evidence_reference,'evidence_sha256':reconciliation.evidence_sha256,'provider_credit_applied':str(reconciliation.provider_credit_applied),'discount_applied':str(reconciliation.discount_applied),'over_limit_delta':str(reconciliation.over_limit_delta),'recorded_at':reconciliation.created_at.isoformat()} if reconciliation else None,
            'customer_limit_usd':str(limit) if limit is not None else None,'absorbed_over_limit_usd':str(sum(over_rows,Decimal(0))),
            'reconciliation_ledger':reconciliation_entries,
            'absorbed':absorbed,'absorbed_reversal_usd':str(absorbed_reversal),'absorbed_platform_cost_usd':str(absorbed_cost.amount) if absorbed_cost else None,'absorbed_ledger':absorbed_entries,
            'configured_pricing_fingerprint_at_enqueue':usage.job.config.get('pricing_version'),
            'audit_rate_digest_sha256':hashlib.sha256(json.dumps(usage.rates,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'durable_receipt_present':bool(receipt),'stored_result_integrity':result_integrity,'ledger':entries,'checks':checks})
    orphan=LedgerEntry.objects.filter(kind__in=['absorbed','reconciliation'],job__isnull=True).count()
    # A cancelled job ended before any provider request: it may hold no usage, receipt, ledger movement or held funds.
    cancelled=Job.objects.filter(state='cancelled')
    cancellation_policy={'cancelled_jobs':cancelled.count(),'checks':{
        'cancelled_jobs_have_no_usage':not Usage.objects.filter(job__in=cancelled).exists(),
        'cancelled_jobs_have_no_provider_receipt':not ProviderReceipt.objects.filter(job__in=cancelled).exists(),
        'cancelled_jobs_have_no_ledger_entries':not LedgerEntry.objects.filter(job__in=cancelled).exists(),
        'cancelled_jobs_hold_no_funds':not Reservation.objects.filter(job__in=cancelled,state='held').exists()}}
    # A job that has ended (succeeded, failed or cancelled) holds nothing: every reservation was settled or released.
    ended_holding=Reservation.objects.filter(job__state__in=['succeeded','failed','cancelled'],state='held').values_list('job_id',flat=True).distinct()
    hold_policy={'ended_jobs_holding_funds':[str(job_id) for job_id in ended_holding],'checks':{'ended_jobs_hold_no_funds':not ended_holding.exists()}}
    unbound_over_limit=PlatformCost.objects.filter(kind='absorbed_over_limit').exclude(job__usage__isnull=False).count()
    ledger_policy={'orphan_policy_entries':orphan,'checks':{'policy_ledger_entries_bound_to_jobs':orphan==0,
                                                         'over_limit_absorptions_bound_to_settled_usage':unbound_over_limit==0}}
    wallets=[]
    for wallet in Wallet.objects.all().order_by('id'):
        total=LedgerEntry.objects.filter(wallet=wallet).aggregate(total=Sum('amount'))['total'] or Decimal(0)
        held=Reservation.objects.filter(wallet=wallet,state='held').aggregate(total=Sum('amount'))['total'] or Decimal(0)
        wallets.append({'wallet_id':str(wallet.pk),'kind':wallet.kind,'balance_usd':str(wallet.balance),'ledger_sum_usd':str(total),
            'reserved_usd':str(wallet.reserved),'held_reservations_usd':str(held),'checks':{'balance_equals_ledger':wallet.balance==total,'reserved_equals_holds':wallet.reserved==held}})
    unsettled=list(ProviderReceipt.objects.exclude(job__usage__isnull=False).values('job_id','provider','provider_request_id','provider_resource_id','actual_cost','units','rates'))
    unresolved=list(Job.objects.filter(state__in=['queued','running','reconciliation']).values('id','kind','state','provider','provider_request_id','provider_resource_id'))
    platform_costs={'totals_by_kind':{kind:str(PlatformCost.objects.filter(kind=kind).aggregate(total=Sum('amount'))['total'] or Decimal(0)) for kind,_ in PlatformCost.KINDS},
        'rows':PlatformCost.objects.count(),'policy':'Fixed overhead and absorbed platform-failure cost are tracked separately and never charged to users.'}
    evidence_counts={kind:CostReconciliation.objects.filter(evidence_kind=kind).count() for kind,_ in CostReconciliation.EVIDENCE_KINDS}
    reconciliation_summary={'evidence_kinds':evidence_counts,'reconciled_rows':CostReconciliation.objects.count(),'unreconciled_rows':Usage.objects.filter(costreconciliation__isnull=True).count(),
        'pending_funds':CostReconciliation.objects.filter(ledger_status='pending_funds').count(),'absorbed_rows':sum(row['absorbed'] for row in rows)}
    return {'checked_at':timezone.now().isoformat(),'scope':'Read-only fresh application records; no external requests; no clinical text or credentials exported.',
        'charge_policy':'User charge is exactly 1.5 × the attributable metered provider cost after applicable discounts and allocated provider credits; configured-rate rows are estimates until reconciled to authentic provider evidence.',
        'platform_costs':platform_costs,'reconciliation_summary':reconciliation_summary,
        'cost_basis':'Original usage is provider-metered units priced at configured USD rates; reservations are estimates. Classified reconciliation evidence and adjustments are reported separately.',
        'fingerprint_limit':'A configured pricing fingerprint identifies the application configuration, not a provider contract, tariff version, invoice, or verified account discount.',
        'rate_reference_reviewed_on':'2026-09-17','rate_references':['https://platform.claude.com/docs/en/about-claude/pricing','https://deepgram.com/pricing'],
        'rows':rows,'wallets':wallets,'unsettled_provider_receipts':unsettled,'unresolved_jobs':unresolved,
        'ledger_policy':ledger_policy,'cancellation_policy':cancellation_policy,'hold_policy':hold_policy,
        'all_checks_pass':all(all(row['checks'].values()) for row in rows+wallets) and all(ledger_policy['checks'].values()) and all(cancellation_policy['checks'].values()) and all(hold_policy['checks'].values()),
        'durable_receipt_gaps':sum(not row['durable_receipt_present'] and not row['simulated'] for row in rows),
        'invoice_reconciliation':{'invoice_rows':evidence_counts['invoice'],'provider_report_rows':evidence_counts['provider_report'],'unclassified_rows':evidence_counts['unclassified'],'scope':'Administrator-recorded per-usage classification; no account-wide or whole-invoice reconciliation is implied.','provenance':'Source authenticity and attribution require administrator review; this audit verifies ledger arithmetic, not provider authenticity.'}}


class Command(BaseCommand):
    help='Read-only audit of provider units, configured rates, result hashes, exact charges, ledgers and reservations.'
    def add_arguments(self,parser):
        parser.add_argument('--output',help='Private JSON artifact inside rebuild/.runtime; omitted prints JSON.')
        parser.add_argument('--maintenance-storage',action='store_true',help='Use the bounded read-only helper for dedicated-identity application files.')
    def handle(self,*args,**options):
        reader=None
        if options['maintenance_storage']:
            from ops.private_storage import read_file
            if settings.MEDIA_ROOT != Path('/var/lib/quillmd/files'):
                raise CommandError('Maintenance storage is only for the dedicated fresh application state.')
            reader=lambda path: read_file(settings.MEDIA_ROOT,str(path.relative_to(settings.MEDIA_ROOT)))
        report=audit_report(reader)
        payload=json.dumps(report,indent=2,default=str)+'\n'
        if options['output']:
            path=Path(options['output']).resolve();root=(settings.BASE_DIR/'.runtime').resolve()
            if not path.is_relative_to(root) or path==root:raise CommandError('Audit output must be inside the private .runtime directory.')
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_NOFOLLOW,0o600)
            os.fchmod(fd,0o600)
            with os.fdopen(fd,'w') as stream:stream.write(payload)
            self.stdout.write(json.dumps({'all_checks_pass':report['all_checks_pass'],'usage_rows':len(report['rows']),'wallets':len(report['wallets']),'durable_receipt_gaps':report['durable_receipt_gaps']}))
        else:self.stdout.write(payload)
        if not report['all_checks_pass']:raise CommandError('Billing evidence mismatch; inspect the private audit artifact.')
