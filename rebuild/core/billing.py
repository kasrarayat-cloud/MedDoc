from decimal import Decimal, ROUND_DOWN
import hashlib
import json
import re
from django.db import transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import User, Wallet, LedgerEntry, Reservation, Usage, Membership, Organization, Payment, Refund, WebhookEvent, CostReconciliation, PlatformCost
from .security import audit, membership
ZERO=Decimal('0')
MULTIPLIER=Decimal('1.5')

def stripe_test_key_configured(key):
    """Recognize sandbox server keys; this does not validate provider access."""
    return isinstance(key,str) and re.fullmatch(r'(?:sk|rk)_test_[A-Za-z0-9_]+',key) is not None

def checkout_form(user,data=None):
    from .forms import CheckoutForm
    form=CheckoutForm(data)
    owned=Organization.objects.filter(department__membership__user=user,department__membership__active=True,
        department__membership__role='owner',department__membership__user__is_active=True,
        department__membership__user__verified_at__isnull=False).distinct()
    form.fields['payer'].choices=[('personal','My personal paid balance')]+[(f'organization:{org.pk}',f'{org.name} · organization paid balance') for org in owned]
    return form

def exact(value):
    amount=Decimal(str(value))
    if not amount.is_finite() or amount<0 or amount!=amount.quantize(Decimal('0.000000000001')): raise ValidationError('Invalid billable cost precision.')
    return amount

def signed_exact(value):
    """Ledger precision check for adjustments that may be negative (credits back)."""
    amount=Decimal(str(value))
    if not amount.is_finite() or amount!=amount.quantize(Decimal('0.000000000001')): raise ValidationError('Invalid ledger adjustment precision.')
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
def settle(job,actual_cost,units,rates,provider,provider_request_id='',simulated=False,provider_resource_id=''):
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
    result=Usage.objects.create(job=job,user=job.user,department=d,organization=d.organization,payer=job.payer or f'user:{job.user_id}',provider=provider,provider_request_id=provider_request_id,provider_resource_id=provider_resource_id,units=units,rates=rates,actual_cost=actual,charged_cost=charged,simulated=simulated)
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
    validate_checkout(p,session)
    if session.get('payment_status')!='paid': raise ValidationError('Stripe payment is not paid.')
    intent=session.get('payment_intent')
    if not isinstance(intent,str) or not intent or len(intent)>200: raise ValidationError('Payment intent is missing.')
    if p.status=='paid':
        if p.stripe_intent!=intent: raise ValidationError('Payment intent changed after settlement.')
        return
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
    if type(amount) is not int or amount<=0 or obj.get('currency')!='usd': raise ValidationError('Invalid refund amount or currency.')
    if not isinstance(obj.get('id'),str) or not obj['id'] or len(obj['id'])>200: raise ValidationError('Invalid refund identifier.')
    if obj.get('status') not in ['pending','requires_action','succeeded','failed','canceled']: raise ValidationError('Unknown refund status.')
    previous=Refund.objects.select_for_update().filter(stripe_refund=obj['id']).first()
    if previous:
        if previous.payment_id!=p.pk or previous.amount_cents!=amount: raise ValidationError('Refund identity or amount changed.')
        if previous.status=='succeeded': return
        if previous.status in ['failed','canceled'] and obj.get('status') in ['pending','requires_action']: return
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

def payer_wallet(payer):
    """The PAID wallet of the payer recorded on a usage row ('user:<id>' or 'organization:<id>')."""
    scope,_,identifier=(payer or '').partition(':')
    if scope=='user' and identifier: return Wallet.objects.get_or_create(user_id=identifier,kind='paid')[0]
    if scope=='organization' and identifier: return Wallet.objects.get_or_create(organization_id=identifier,kind='paid')[0]
    raise ValidationError('Usage has no recorded payer; reconciliation requires manual review.')

def proportional_split(entries,total):
    """Split a positive credit across the wallets that were debited, in proportion to their debits, to exact ledger precision."""
    debits=[(entry.wallet_id,-entry.amount) for entry in entries if entry.amount<0]
    debited=sum((amount for _,amount in debits),ZERO)
    if debited<=0: raise ValidationError('No original usage debits exist to credit back.')
    shares=[];allocated=ZERO
    for index,(wallet_id,amount) in enumerate(debits):
        share=(total*amount/debited).quantize(Decimal('0.000000000001'),rounding=ROUND_DOWN) if index<len(debits)-1 else total-allocated
        shares.append((wallet_id,share));allocated+=share
    return shares

def apply_additional_debit(row,wallet):
    """Debit a positive charge delta from an already locked paid wallet when its available balance allows it."""
    key=f'reconciliation:{row.usage_id}:{wallet.pk}'
    if LedgerEntry.objects.filter(key=key).exists(): return True
    if wallet.balance-wallet.reserved<row.charge_delta: return False
    wallet.balance-=row.charge_delta; wallet.save(update_fields=['balance'])
    LedgerEntry.objects.create(wallet=wallet,amount=-row.charge_delta,kind='reconciliation',key=key,description='Reconciled provider cost above the configured estimate × 1.5 (additional charge)',job_id=row.usage.job_id,balance_after=wallet.balance)
    return True

@transaction.atomic
def reconcile_usage(usage,reconciled_cost,evidence_reference,actor,provider_credit_applied=ZERO,discount_applied=ZERO,evidence_sha256='',note=''):
    """Record authentic provider evidence for one usage row and settle the difference by appended ledger entries.

    The Usage row and its original 'usage' ledger entries are never modified. Credits back return to the wallets that
    were debited, in proportion to their original debits; additional charges come from the recorded payer's paid wallet.
    """
    from .models import Job
    usage=Usage.objects.select_related('job','department').get(pk=usage.pk)
    Job.objects.select_for_update().get(pk=usage.job_id)
    if CostReconciliation.objects.filter(usage=usage).exists(): raise ValidationError('This usage row has already been reconciled; history is append-only.')
    if actor is None or not getattr(actor,'pk',None): raise ValidationError('A recorded administrator is required.')
    reconciled=exact(reconciled_cost);credit=exact(provider_credit_applied or ZERO);discount=exact(discount_applied or ZERO)
    if usage.simulated and reconciled!=0: raise ValidationError('Simulated usage has no provider cost to reconcile.')
    evidence_reference=(evidence_reference or '').strip()
    if not evidence_reference or len(evidence_reference)>240: raise ValidationError('An evidence reference (invoice number, export sha256 or report id) is required.')
    evidence_sha256=(evidence_sha256 or '').strip().lower()
    if evidence_sha256 and not re.fullmatch(r'[0-9a-f]{64}',evidence_sha256): raise ValidationError('Evidence sha256 must be 64 hexadecimal characters.')
    note=(note or '').strip()
    if len(note)>240: raise ValidationError('Note is limited to 240 characters.')
    delta=signed_exact((reconciled-usage.actual_cost)*MULTIPLIER)
    row=CostReconciliation(usage=usage,reconciled_cost=reconciled,provider_credit_applied=credit,discount_applied=discount,evidence_reference=evidence_reference,evidence_sha256=evidence_sha256,recorded_by=actor,note=note,charge_delta=delta,ledger_status='applied')
    absorbed=LedgerEntry.objects.filter(job_id=usage.job_id,kind='absorbed').exists() or PlatformCost.objects.filter(job_id=usage.job_id,kind='absorbed_failure').exists()
    if absorbed:
        # The user's charge was already reversed in full; the evidence is recorded against the platform cost, never credited or debited twice.
        row.ledger_status='absorbed'; row.save()
    elif delta<0:
        entries=list(LedgerEntry.objects.filter(job_id=usage.job_id,kind='usage').order_by('wallet_id'))
        shares=proportional_split(entries,-delta)
        wallets={w.pk:w for w in Wallet.objects.select_for_update().filter(pk__in=[wallet_id for wallet_id,_ in shares]).order_by('pk')}
        row.save()
        for wallet_id,share in shares:
            if not share: continue
            wallet=wallets[wallet_id]
            wallet.balance+=share; wallet.save(update_fields=['balance'])
            LedgerEntry.objects.create(wallet=wallet,amount=share,kind='reconciliation',key=f'reconciliation:{usage.pk}:{wallet.pk}',description='Reconciled provider cost below the configured estimate × 1.5 (credit back)',job_id=usage.job_id,balance_after=wallet.balance)
    elif delta>0:
        payer=payer_wallet(usage.payer)
        wallet=Wallet.objects.select_for_update().get(pk=payer.pk)
        row.save()
        if not apply_additional_debit(row,wallet):
            row.ledger_status='pending_funds'; row.save(update_fields=['ledger_status'])
    else: row.save()
    audit(actor,'usage.reconcile',usage.job_id,department=usage.department,reconciled_cost=str(reconciled),charge_delta=str(delta),ledger_status=row.ledger_status,evidence_reference=evidence_reference)
    return row

def apply_pending_reconciliations(actor=None):
    """Apply additional charges that were held for funds. Idempotent: the unique ledger key guards replay."""
    from .models import Job
    applied=[]
    for pk in list(CostReconciliation.objects.filter(ledger_status='pending_funds').order_by('created_at').values_list('pk',flat=True)):
        with transaction.atomic():
            row=CostReconciliation.objects.select_for_update().select_related('usage__department').get(pk=pk)
            if row.ledger_status!='pending_funds': continue
            Job.objects.select_for_update().get(pk=row.usage.job_id)
            payer=payer_wallet(row.usage.payer)
            wallet=Wallet.objects.select_for_update().get(pk=payer.pk)
            if not apply_additional_debit(row,wallet): continue
            row.ledger_status='applied'; row.save(update_fields=['ledger_status'])
            audit(actor,'usage.reconciliation_applied',row.usage.job_id,department=row.usage.department,charge_delta=str(row.charge_delta))
            applied.append(row)
    return applied

@transaction.atomic
def absorb_failed_job(job):
    """QuillMD absorbs settled provider cost whose output was never adopted: reverse the usage debits and record a platform cost.

    Idempotent: ledger keys and the one-absorbed-failure-per-job constraint make a repeat call a no-op.
    """
    from .models import Job
    job=Job.objects.select_for_update().select_related('encounter__department','user').get(pk=job.pk)
    usage=Usage.objects.filter(job=job).first()
    if usage is None or usage.simulated: return None
    entries=list(LedgerEntry.objects.filter(job=job,kind='usage').order_by('wallet_id'))
    wallets={w.pk:w for w in Wallet.objects.select_for_update().filter(pk__in=[e.wallet_id for e in entries]).order_by('pk')}
    reversed_total=ZERO
    for entry in entries:
        key=f'absorbed:{job.pk}:{entry.wallet_id}'
        if entry.amount>=0 or LedgerEntry.objects.filter(key=key).exists(): continue
        wallet=wallets[entry.wallet_id]; amount=-entry.amount
        wallet.balance+=amount; wallet.save(update_fields=['balance'])
        LedgerEntry.objects.create(wallet=wallet,amount=amount,kind='absorbed',key=key,description='Usage charge reversed: provider cost of a platform failure absorbed by QuillMD',job=job,balance_after=wallet.balance)
        reversed_total+=amount
    cost,created=PlatformCost.objects.get_or_create(job=job,kind='absorbed_failure',defaults={'amount':usage.actual_cost,'description':'Provider cost absorbed: output not adopted','evidence_reference':f'usage:{usage.pk}'})
    if created or reversed_total: audit(job.user,'usage.absorbed',job.pk,department=job.encounter.department,actual_cost=str(usage.actual_cost),reversed=str(reversed_total))
    return cost

def reconciliation():
    rows=[]
    for w in Wallet.objects.all():
        ledger=LedgerEntry.objects.filter(wallet=w).aggregate(total=Sum('amount'))['total'] or ZERO
        held=Reservation.objects.filter(wallet=w,state='held').aggregate(total=Sum('amount'))['total'] or ZERO
        rows.append({'wallet':w.label,'balance':w.balance,'ledger':ledger,'reserved':w.reserved,'held':held,'status':'matched' if w.balance==ledger and w.reserved==held else 'MISMATCH'})
    return rows


def validate_checkout(payment,session):
    if (session.get('currency')!='usd' or type(session.get('amount_total')) is not int
            or session['amount_total']!=payment.amount_cents or session.get('mode')!='payment'
            or session.get('metadata',{}).get('payment_id')!=str(payment.pk)
            or session.get('id')!=payment.stripe_session):
        raise ValidationError('Stripe payment does not match the authorized checkout.')


@transaction.atomic
def checkout_event(kind,obj):
    # Metadata is emitted by our server and covered by Stripe's signature. It lets
    # an early webhook bind its session before Session.create returns locally.
    payment_id=obj.get('metadata',{}).get('payment_id')
    try: payment=Payment.objects.select_for_update().get(pk=payment_id)
    except (Payment.DoesNotExist,ValueError,TypeError): raise ValidationError('Checkout is not registered locally.')
    session_id=obj.get('id')
    if not isinstance(session_id,str) or not session_id or len(session_id)>200: raise ValidationError('Invalid checkout session.')
    if payment.stripe_session is None:
        payment.stripe_session=session_id
        validate_checkout(payment,obj)
        payment.save(update_fields=['stripe_session'])
    else: validate_checkout(payment,obj)
    if kind in ['checkout.session.completed','checkout.session.async_payment_succeeded'] and obj.get('payment_status')=='paid':
        credit_payment(payment,obj)
    elif payment.status!='paid':
        if kind=='checkout.session.async_payment_failed': payment.status='failed'
        elif kind=='checkout.session.expired': payment.status='expired'
        elif payment.status not in ['failed','expired']: payment.status='processing'
        payment.save(update_fields=['status'])


CHECKOUT_EVENTS={'checkout.session.completed','checkout.session.async_payment_succeeded','checkout.session.async_payment_failed','checkout.session.expired'}
REFUND_EVENTS={'refund.created','refund.updated','refund.failed'}


def record_stripe_event(event,payload_hash):
    event_id=event.get('id');kind=event.get('type')
    if not isinstance(event_id,str) or not event_id or len(event_id)>180 or not isinstance(kind,str) or len(kind)>80:
        raise ValidationError('Malformed payment event.')
    data=event.get('data',{})
    if not isinstance(data,dict): raise ValidationError('Malformed payment event data.')
    raw=data.get('object',{})
    if not isinstance(raw,dict): raise ValidationError('Malformed payment event object.')
    if raw.get('livemode') is True: raise ValidationError('Live payment objects are not accepted.')
    keys=('id','payment_intent','amount','status','currency','payment_status','amount_total','mode')
    obj={k:raw[k] for k in keys if k in raw}
    if 'metadata' in raw:
        if not isinstance(raw['metadata'],dict): raise ValidationError('Malformed payment metadata.')
        obj['metadata']={'payment_id':raw['metadata'].get('payment_id')}
    semantic=hashlib.sha256(json.dumps({'kind':kind,'object':obj},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    row,_=WebhookEvent.objects.get_or_create(event_id=event_id,defaults={'kind':kind,'payload_hash':payload_hash,'semantic_hash':semantic,'object_data':obj,'status':'received'})
    if row.semantic_hash and row.semantic_hash!=semantic: raise ValidationError('Repeated Stripe event has different billing contents.')
    if row.kind!=kind: raise ValidationError('Repeated Stripe event changed type.')
    return row


def process_stripe_event(event_id):
    from django.db import IntegrityError
    with transaction.atomic():
        row=WebhookEvent.objects.select_for_update().get(pk=event_id)
        if row.status in ['processed','ignored']: return True
        row.attempts+=1
        try:
            # Keep the signed event even when settlement's savepoint rolls back.
            with transaction.atomic():
                if row.kind in CHECKOUT_EVENTS: checkout_event(row.kind,row.object_data)
                elif row.kind in REFUND_EVENTS: reconcile_refund(row.object_data)
                else: row.status='ignored'
            if row.status!='ignored': row.status='processed'
            row.error='';row.processed_at=timezone.now()
        except (ValidationError,IntegrityError):
            row.status='reconciliation';row.error='Billing data or available paid funds require reconciliation.'
        row.save(update_fields=['status','attempts','error','processed_at'])
        audit(None,'stripe.event',row.event_id,kind=row.kind,status=row.status,attempts=row.attempts)
        success=row.status in ['processed','ignored']
        intent=row.object_data.get('payment_intent') if row.kind in CHECKOUT_EVENTS and success else None
    # Stripe does not guarantee event order. A settled payment can unblock an
    # earlier refund; replay uses the same immutable identity and debit guard.
    if intent:
        pending=WebhookEvent.objects.filter(kind__in=REFUND_EVENTS,status='reconciliation',object_data__payment_intent=intent).values_list('pk',flat=True)
        for pending_id in list(pending): process_stripe_event(pending_id)
    return success
