"""Bounded operational navigation and financial evidence; no clinical payloads."""
from decimal import Decimal
from django.core.paginator import Paginator
from django.db.models import Q, Sum, CharField
from django.db.models.functions import Cast
from .models import Job, Usage, Reservation, LedgerEntry, Wallet, ProviderReceipt, PlatformCost, AuditEvent


def searched(queryset, query, fields):
    if not query:
        return queryset
    predicate = Q(search_identity__icontains=query)
    for field in fields:
        predicate |= Q(**{field + '__icontains': query})
    return queryset.annotate(search_identity=Cast('pk', CharField())).filter(predicate).distinct()


def page_for(request, queryset, parameter='page', anchor='', size=25):
    page = Paginator(queryset, size).get_page(request.GET.get(parameter))
    def link(number):
        query = request.GET.copy()
        query[parameter] = str(number)
        return '?' + query.urlencode() + ('#' + anchor if anchor else '')
    return {'page': page, 'previous': link(page.previous_page_number()) if page.has_previous() else '',
            'next': link(page.next_page_number()) if page.has_next() else '', 'label': anchor or 'history'}


def financial_context(job, visible_wallets=None):
    """Explicit projection: never pass notes, answers, patient names or raw provider output."""
    usage = Usage.objects.filter(job=job).select_related('costreconciliation__recorded_by').first()
    receipt = ProviderReceipt.objects.filter(job=job).first()
    entries = list(LedgerEntry.objects.filter(job=job).select_related('wallet__user', 'wallet__organization').order_by('created_at', 'pk'))
    reservations = list(Reservation.objects.filter(job=job).select_related('wallet__user', 'wallet__organization').order_by('created_at', 'pk'))
    movements = []
    for entry in entries:
        visible = visible_wallets is None or entry.wallet_id in visible_wallets
        movements.append({'entry': entry, 'before': entry.balance_after - entry.amount if visible else None, 'after': entry.balance_after if visible else None})
    wallet_ids = {row.wallet_id for row in entries + reservations}
    if visible_wallets is not None:
        wallet_ids &= visible_wallets
    balances = []
    for wallet in Wallet.objects.filter(pk__in=wallet_ids).select_related('user', 'organization').order_by('pk'):
        total = LedgerEntry.objects.filter(wallet=wallet).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        held = Reservation.objects.filter(wallet=wallet, state='held').aggregate(total=Sum('amount'))['total'] or Decimal('0')
        balances.append({'wallet': wallet, 'ledger_total': total, 'held': held,
                         'matches': total == wallet.balance and held == wallet.reserved})
    from .models import Department
    scope = Department.objects.select_related('organization').get(pk=job.encounter.department_id)
    evidence_ids = [str(job.pk)] + ([str(usage.pk)] if usage else [])
    return {'financial_job': {'id': job.pk, 'kind': job.kind, 'state': job.state,
                             'user': job.user.email, 'department': scope.name, 'organization': scope.organization.name,
                             'payer': job.payer, 'pricing': job.pricing_snapshot, 'created_at': job.created_at,
                             'request_id': job.http_request_id, 'resource_id': job.resource_id},
            'usage': usage, 'receipt': receipt, 'movements': movements, 'reservations': reservations,
            'balances': balances, 'net_charge': -sum((entry.amount for entry in entries), Decimal('0')),
            'cost_times_multiplier': usage.actual_cost * Decimal('1.5') if usage else None,
            'approved_limit': sum((r.amount for r in reservations), Decimal('0')),
            'platform_costs': PlatformCost.objects.filter(job=job).order_by('created_at', 'pk'),
            'audit_targets': evidence_ids}
