from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from .models import User, Wallet, LedgerEntry, Reservation, Usage, Membership, Payment, Refund, WebhookEvent
from .security import audit, membership
ZERO=Decimal('0')
MULTIPLIER=Decimal('1.5')

def exact(value):
    amount=Decimal(str(value))
    if not amount.is_finite() or amount<0 or amount!=amount.quantize(Decimal('0.000000000001')): raise ValidationError('Invalid billable cost precision.')
    return amount

@transaction.atomic
def welcome_credit(user):
    user=User.objects.select_for_update().get(pk=user.pk)
    if not user.verified_at: raise ValidationError('Welcome credit requires a verified account.')
    wallet,_=Wallet.objects.get_or_create(user=user,kind='promo')
    Wallet.objects.get_or_create(user=user,kind='paid')
    wallet=Wallet.objects.select_for_update().get(pk=wallet.pk)
    key=f'welcome:{user.pk}'
    if LedgerEntry.objects.filter(key=key).exists(): return wallet
    wallet.balance+=Decimal('10'); wallet.save(update_fields=['balance'])
    LedgerEntry.objects.create(wallet=wallet,amount=10,kind='welcome',key=key,description='One $10 personal welcome credit after verification',balance_after=wallet.balance)
    audit(user,'credit.welcome',wallet.pk)
    return wallet

@transaction.atomic
def reserve(job,maximum_cost):
    membership(job.user,job.encounter.department)
    from .models import Job
    job=Job.objects.select_for_update().get(pk=job.pk)
    maximum_charge=exact(maximum_cost)*MULTIPLIER
    if Reservation.objects.filter(job=job).exists(): return
    promo=Wallet.objects.get(user=job.user,kind='promo')
    department=job.encounter.department
    job.payer=f'organization:{department.organization_id}' if department.organization_pays else f'user:{job.user_id}'
    job.save(update_fields=['payer'])
    payer,_=Wallet.objects.get_or_create(organization=department.organization,kind='paid') if department.organization_pays else Wallet.objects.get_or_create(user=job.user,kind='paid')
    locked={w.pk:w for w in Wallet.objects.select_for_update().filter(pk__in=[promo.pk,payer.pk]).order_by('pk')}
    if sum((w.balance-w.reserved for w in locked.values()),ZERO)<maximum_charge: raise ValidationError('Insufficient available balance. No provider request was made.')
    remaining=maximum_charge
    for wallet in [locked[promo.pk],locked[payer.pk]]:
        amount=min(wallet.balance-wallet.reserved,remaining)
        if amount:
            wallet.reserved+=amount; wallet.save(update_fields=['reserved'])
            Reservation.objects.create(job=job,wallet=wallet,amount=amount)
            audit(job.user,'usage.reserve',job.pk,department=department,wallet=str(wallet.pk),amount=str(amount))
            remaining-=amount

@transaction.atomic
def settle(job,actual_cost,units,rates,provider,provider_request_id='',simulated=False):
    # Lock the job first so replay cannot release/spend twice.
    from .models import Job
    job=Job.objects.select_for_update().select_related('encounter__department__organization','user').get(pk=job.pk)
    existing=Usage.objects.filter(job=job).first()
    if existing: return existing
    actual=exact(actual_cost)
    if simulated and actual!=0: raise ValidationError('Simulated integrations cannot create billable cost.')
    charged=exact(actual*MULTIPLIER)
    reservations=list(Reservation.objects.select_for_update().filter(job=job,state='held').select_related('wallet').order_by('wallet_id'))
    if sum((r.amount for r in reservations),ZERO)<charged: raise ValidationError('Actual usage exceeds the authorized reservation; settlement held for reconciliation.')
    wallets={w.pk:w for w in Wallet.objects.select_for_update().filter(pk__in=[r.wallet_id for r in reservations]).order_by('pk')}
    remaining=charged
    # Personal promotional credit is always used before paid funds.
    for r in sorted(reservations,key=lambda r:0 if r.wallet.kind=='promo' else 1):
        wallet=wallets[r.wallet_id]
        debit=min(r.amount,remaining)
        wallet.reserved-=r.amount; wallet.balance-=debit; wallet.save(update_fields=['reserved','balance'])
        if debit: LedgerEntry.objects.create(wallet=wallet,amount=-debit,kind='usage',key=f'usage:{job.pk}:{wallet.pk}',description='Provider cost × 1.5',job=job,balance_after=wallet.balance)
        r.state='settled'; r.save(update_fields=['state']); remaining-=debit
    d=job.encounter.department
    result=Usage.objects.create(job=job,user=job.user,department=d,organization=d.organization,payer=job.payer or f'user:{job.user_id}',provider=provider,provider_request_id=provider_request_id,units=units,rates=rates,actual_cost=actual,charged_cost=charged,simulated=simulated)
    audit(job.user,'usage.settle',job.pk,department=d,actual=str(actual),charged=str(charged),simulated=simulated)
    return result

@transaction.atomic
def release(job):
    from .models import Job
    Job.objects.select_for_update().get(pk=job.pk)
    reservations=list(Reservation.objects.select_for_update().filter(job=job,state='held').order_by('wallet_id'))
    wallets={w.pk:w for w in Wallet.objects.select_for_update().filter(pk__in=[r.wallet_id for r in reservations]).order_by('pk')}
    for r in reservations:
        w=wallets[r.wallet_id]; w.reserved-=r.amount; w.save(update_fields=['reserved'])
        r.state='released'; r.save(update_fields=['state'])
        audit(job.user,'usage.release',job.pk,wallet=str(w.pk),amount=str(r.amount))

@transaction.atomic
def credit_payment(payment,session):
    p=Payment.objects.select_for_update().get(pk=payment.pk)
    if p.status=='paid': return
    if session.get('payment_status')!='paid' or session.get('currency')!='usd' or session.get('amount_total')!=p.amount_cents or session.get('id')!=p.stripe_session or session.get('metadata',{}).get('payment_id')!=str(p.pk): raise ValidationError('Stripe payment does not match the authorized checkout.')
    intent=session.get('payment_intent')
    if not intent: raise ValidationError('Payment intent is missing.')
    w=Wallet.objects.select_for_update().get(pk=p.wallet_id)
    amount=Decimal(p.amount_cents)/100
    w.balance+=amount; w.save(update_fields=['balance'])
    LedgerEntry.objects.create(wallet=w,amount=amount,kind='payment',key=f'payment:{intent}',description='Explicit Stripe wallet top-up',balance_after=w.balance)
    p.status='paid'; p.stripe_intent=intent; p.save(update_fields=['status','stripe_intent'])
    audit(p.user,'payment.settle',p.pk,amount=str(amount))

@transaction.atomic
def reconcile_refund(obj):
    p=Payment.objects.select_for_update().filter(stripe_intent=obj.get('payment_intent'),status='paid').first()
    if not p: raise ValidationError('Refund references an unknown payment.')
    amount=obj.get('amount')
    if not isinstance(amount,int) or amount<=0: raise ValidationError('Invalid refund amount.')
    previous=Refund.objects.select_for_update().filter(stripe_refund=obj['id']).first()
    if previous and previous.status=='succeeded': return
    if obj.get('status')!='succeeded':
        Refund.objects.update_or_create(stripe_refund=obj['id'],defaults={'payment':p,'amount_cents':amount,'status':obj.get('status','pending')}); return
    refunded=Refund.objects.filter(payment=p,status='succeeded').aggregate(total=Sum('amount_cents'))['total'] or 0
    if refunded+amount>p.amount_cents: raise ValidationError('Refund exceeds payment.')
    w=Wallet.objects.select_for_update().get(pk=p.wallet_id)
    debit=Decimal(amount)/100
    if w.balance-w.reserved<debit: raise ValidationError('Refund requires manual reconciliation: paid funds already used or reserved.')
    w.balance-=debit; w.save(update_fields=['balance'])
    LedgerEntry.objects.create(wallet=w,amount=-debit,kind='refund',key=f'refund:{obj["id"]}',description='Stripe refund',balance_after=w.balance)
    Refund.objects.update_or_create(stripe_refund=obj['id'],defaults={'payment':p,'amount_cents':amount,'status':'succeeded'})
    audit(p.user,'payment.refund',p.pk,amount=str(debit))

def reconciliation():
    rows=[]
    for w in Wallet.objects.all():
        ledger=LedgerEntry.objects.filter(wallet=w).aggregate(total=Sum('amount'))['total'] or ZERO
        held=Reservation.objects.filter(wallet=w,state='held').aggregate(total=Sum('amount'))['total'] or ZERO
        rows.append({'wallet':w.label,'balance':w.balance,'ledger':ledger,'reserved':w.reserved,'held':held,'status':'matched' if w.balance==ledger and w.reserved==held else 'MISMATCH'})
    return rows
