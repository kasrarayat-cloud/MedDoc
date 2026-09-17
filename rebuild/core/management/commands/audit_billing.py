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
from core.models import Job, LedgerEntry, ProviderReceipt, Reservation, Usage, Wallet
from core.security import private_path


def recompute_cost(provider, units, rates, simulated):
    if simulated:
        return Decimal('0')
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


def audit_report(file_reader=None):
    rows=[]
    for usage in Usage.objects.select_related('job__providerreceipt','job__encounter__department').order_by('created_at'):
        try:receipt=usage.job.providerreceipt
        except ProviderReceipt.DoesNotExist:receipt=None
        entries=list(LedgerEntry.objects.filter(job_id=usage.job_id,kind='usage').values('amount','wallet_id','wallet__kind','balance_after'))
        try:calculated=recompute_cost(usage.provider,usage.units,usage.rates,usage.simulated)
        except (KeyError,ValueError,ArithmeticError):calculated=None
        checks={'recomputed_defined_cost_matches':calculated==usage.actual_cost,
                'exact_1_5_multiplier':usage.charged_cost==usage.actual_cost*Decimal('1.5'),
                'ledger_debit_matches':-sum((entry['amount'] for entry in entries),Decimal(0))==usage.charged_cost,
                'no_held_reservation':not Reservation.objects.filter(job_id=usage.job_id,state='held').exists(),
                'usage_scope_matches_job':usage.user_id==usage.job.user_id and usage.department_id==usage.job.encounter.department_id and usage.organization_id==usage.job.encounter.department.organization_id,
                'payer_matches_authorized_snapshot':not usage.job.payer or usage.payer==usage.job.payer}
        if receipt:checks['durable_receipt_matches']=all(getattr(receipt,k)==getattr(usage,k) for k in ['provider','provider_request_id','provider_resource_id','units','rates','actual_cost','simulated'])
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
            'cost_evidence':usage.cost_evidence,'invoice_reconciled':False,'enqueue_config_recorded':bool(usage.job.config),
            'configured_pricing_fingerprint_at_enqueue':usage.job.config.get('pricing_version'),
            'audit_rate_digest_sha256':hashlib.sha256(json.dumps(usage.rates,sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'durable_receipt_present':bool(receipt),'stored_result_integrity':result_integrity,'ledger':entries,'checks':checks})
    wallets=[]
    for wallet in Wallet.objects.all().order_by('id'):
        total=LedgerEntry.objects.filter(wallet=wallet).aggregate(total=Sum('amount'))['total'] or Decimal(0)
        held=Reservation.objects.filter(wallet=wallet,state='held').aggregate(total=Sum('amount'))['total'] or Decimal(0)
        wallets.append({'wallet_id':str(wallet.pk),'kind':wallet.kind,'balance_usd':str(wallet.balance),'ledger_sum_usd':str(total),
            'reserved_usd':str(wallet.reserved),'held_reservations_usd':str(held),'checks':{'balance_equals_ledger':wallet.balance==total,'reserved_equals_holds':wallet.reserved==held}})
    unsettled=list(ProviderReceipt.objects.exclude(job__usage__isnull=False).values('job_id','provider','provider_request_id','provider_resource_id','actual_cost','units','rates'))
    unresolved=list(Job.objects.filter(state__in=['queued','running','reconciliation']).values('id','kind','state','provider','provider_request_id','provider_resource_id'))
    return {'checked_at':timezone.now().isoformat(),'scope':'Read-only fresh application records; no external requests; no clinical text or credentials exported.',
        'cost_basis':'Provider-metered units priced at configured USD rates; reservations are estimates; account invoices are not reconciled.',
        'fingerprint_limit':'A configured pricing fingerprint identifies the application configuration, not a provider contract, tariff version, invoice, or verified account discount.',
        'rate_reference_reviewed_on':'2026-09-17','rate_references':['https://platform.claude.com/docs/en/about-claude/pricing','https://deepgram.com/pricing'],
        'rows':rows,'wallets':wallets,'unsettled_provider_receipts':unsettled,'unresolved_jobs':unresolved,
        'all_checks_pass':all(all(row['checks'].values()) for row in rows+wallets),
        'durable_receipt_gaps':sum(not row['durable_receipt_present'] and not row['simulated'] for row in rows),
        'invoice_reconciliation':'Not performed; account invoices, discounts and promotional provider credits remain unverified.'}


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
