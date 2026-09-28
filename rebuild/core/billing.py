from decimal import Decimal, ROUND_DOWN
import hashlib
import json
import re
from django.db import connection, transaction
from django.db.models import Sum
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import User, Wallet, LedgerEntry, Reservation, Usage, Membership, Organization, Payment, Refund, WebhookEvent, CostReconciliation, PlatformCost
from .security import audit, membership
from .stripe_validation import live_payments, real_data_mode, validate_event_environment
from quillmd.application_profile import dollars, stripe_key_matches
ZERO=Decimal('0')
MULTIPLIER=Decimal('1.5')

def stripe_test_key_configured(key):
    """Recognize sandbox server keys; this does not validate provider access."""
    return isinstance(key,str) and re.fullmatch(r'(?:sk|rk)_test_[A-Za-z0-9_]+',key) is not None

def stripe_key_configured(key):
    """A server key of the configured QUILLMD_STRIPE_MODE: test keys in test mode, live keys in live mode.

    A key of the other mode is never recognised, so a live key cannot reach Checkout in test mode and a
    sandbox key cannot in live mode. Test mode is exactly `stripe_test_key_configured`.
    """
    from django.conf import settings
    mode=getattr(settings,'QUILLMD_STRIPE_MODE','test')
    return stripe_test_key_configured(key) if mode=='test' else stripe_key_matches(key,mode)

def welcome_credit_amount():
    from django.conf import settings
    return Decimal(getattr(settings,'QUILLMD_WELCOME_CREDIT',Decimal('10')))

def welcome_credit_label():
    """'$10' at the default; '' when QUILLMD_WELCOME_CREDIT=0, so no screen promises a grant that is not made."""
    amount=welcome_credit_amount()
    return dollars(amount) if amount>0 else ''

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
    # QUILLMD_WELCOME_CREDIT (default 10). Zero grants nothing and writes no entry. Entries already
    # written keep the amount they record; changing the setting never revisits them.
    amount=welcome_credit_amount()
    if amount<=0: return wallet
    wallet.balance+=amount; wallet.save(update_fields=['balance'])
    LedgerEntry.objects.create(wallet=wallet,amount=amount,kind='welcome',key=key,description=f'One {dollars(amount)} personal welcome credit after verification',balance_after=wallet.balance)
    audit(user,'credit.welcome',wallet.pk)
    return wallet

def sandbox_funded(wallet):
    """Whether any money this wallet ever received came from a payment not recorded as live.

    A payment is live only when its checkout was created in live mode (Payment.livemode is True). Rows recorded before
    the mode was stored are sandbox: live mode did not exist then. Only payments that FUNDED the wallet count: a
    checkout nobody paid (creating, pending, processing, uncertain, failed, expired) put no money in it, so an
    abandoned sandbox checkout never freezes a balance live money funded. Two readers, so no route is missed: the
    wallet's paid Payment rows, and its 'payment' ledger credits, where a credit whose Payment row is not live, or is
    missing, counts whatever that row's status says.
    """
    if Payment.objects.filter(wallet=wallet,status='paid').exclude(livemode=True).exists(): return True
    live=[f'payment:{intent}' for intent in Payment.objects.filter(wallet=wallet,livemode=True,stripe_intent__isnull=False).values_list('stripe_intent',flat=True)]
    return LedgerEntry.objects.filter(wallet=wallet,kind='payment').exclude(key__in=live).exists()


def real_mode_refuses(wallet):
    """Whether real data mode refuses this paid balance: it holds money a payment not recorded as live funded.

    One rule, and nothing in real mode moves money out of such a balance: reserve() never holds it, checkout never takes
    live money into it (that money could never be spent), the worker never sends a job it could pay for (sandbox_hold),
    settlement never debits it (settle) and a reconciled charge never comes from it (apply_additional_debit). Always
    False in synthetic mode, which spends sandbox money as before.
    """
    return real_data_mode() and sandbox_funded(wallet)


class SandboxFundsRefused(ValidationError):
    """Real data mode refused to debit a balance sandbox payments funded; nothing was charged."""


def department_payer(user_id,department):
    """The payer reserve() records for a request: the organization when the department pays, otherwise the user."""
    return f'organization:{department.organization_id}' if department.organization_pays else f'user:{user_id}'


def recorded_paid_wallet(payer):
    """The paid wallet of a payer ('user:<id>' or 'organization:<id>'), or None when it has none. Read-only, unlike
    payer_wallet()."""
    scope,_,identifier=(payer or '').partition(':')
    field={'user':'user_id','organization':'organization_id'}.get(scope)
    return Wallet.objects.filter(**{field:identifier},kind='paid').first() if field and identifier else None


def charge_wallets(job):
    """Every wallet this job's charges can come from: the wallets holding its funds (settlement debits them) and its
    payer's paid wallet (reserve()'s rule; a reconciled charge debits it). A job with no recorded payer yet is judged by
    the payer reserve() would record for it."""
    wallets=[r.wallet for r in Reservation.objects.filter(job=job,state='held').select_related('wallet').order_by('pk')]
    payer=recorded_paid_wallet(job.payer or department_payer(job.user_id,job.department))
    return wallets+([payer] if payer is not None else [])


def sandbox_hold(job):
    """Whether real data mode refuses any wallet this job could be charged from (charge_wallets).

    The worker reads this immediately before the provider request (core.jobs.run_one), so a job reserve() would refuse
    in real mode is never sent: one whose hold, taken before the switch from synthetic mode, sits on sandbox money, and
    one whose hold is wholly promotional while its payer's paid balance holds sandbox money (its reconciled cost would
    be charged there).
    """
    return any(real_mode_refuses(w) for w in charge_wallets(job))


#: The database triggers the sandbox-money rule relies on, as (table, trigger, function, pg_trigger.tgtype): without
#: them a statement can relabel sandbox evidence as live. tgtype bits: 1 row, 2 before, 8 delete, 16 update, 32 truncate.
PAYMENT_EVIDENCE_GUARDS=(
    ('core_ledgerentry','ledger_append_only','quillmd_append_only',27),                    # 0003: no UPDATE or DELETE
    ('core_webhookevent','webhook_evidence_immutable','quillmd_webhook_evidence_guard',27), # 0008: no DELETE
    ('core_payment','payment_evidence_immutable','quillmd_payment_evidence_guard',27),      # 0020: no DELETE, no relabel
    ('core_webhookevent','webhook_livemode_immutable','quillmd_livemode_guard',19),         # 0020: mode fixed
    ('core_payment','payment_no_truncate','quillmd_refuse_truncate',34),                    # 0020: no TRUNCATE
    ('core_webhookevent','webhook_no_truncate','quillmd_refuse_truncate',34),               # 0020
    ('core_ledgerentry','ledger_no_truncate','quillmd_refuse_truncate',34),                 # 0020
)

# SHA256 of the exact prosrc installed by migrations 0003, 0008 and 0020. Do not learn these from
# the inspected database: that would certify a replacement function as its own expected value.
PAYMENT_GUARD_FUNCTION_SHA256={
    'quillmd_append_only':'8d5ec86a531621ac1de53c85109dfb5122f9142b1cb66dcfc377e0945d869764',
    'quillmd_webhook_evidence_guard':'797abc46124f7f810165cd8058731387c10bbad141f840f8fddc5b0b5f732f8c',
    'quillmd_payment_evidence_guard':'4c4c2a8c49133266a8bf61181f1d6ca764ee8e98d5de262cb59eac99190520bd',
    'quillmd_livemode_guard':'231e4fd6d5f23b0b38d9b4353add5b26cb31b62c571ccb0987e06705cf6b32cf',
    'quillmd_refuse_truncate':'1f42decb7308aa5ee0a2f5425bd3ca1e8edf244ef3ff5a3faffe0c1dd6b4f447',
}


def missing_payment_evidence_guards():
    """Fixed labels for failed payment-evidence checks; read-only, with no row or unexpected object names returned.

    Compare every full trigger definition, enabled state, schema-qualified function identity and installed prosrc
    hash. Refuse other row or statement triggers, except PostgreSQL's internal foreign-key constraint triggers.
    Require origin both now and in the effective role/database login default. Run on the target database as the
    runtime role: SET ROLE alone does not apply login settings, so pg_db_role_setting is inspected as well.

    An amended migration never re-runs where already applied. These catalog reads provide point-in-time evidence;
    an owner able to change the guards and this checker can defeat it. This is not a lock against that owner.
    """
    tables=sorted({table for table,_,_,_ in PAYMENT_EVIDENCE_GUARDS})
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_schema(),quote_ident(current_schema()),current_setting('session_replication_role')")
        schema,quoted_schema,replication=cursor.fetchone()
        cursor.execute("SELECT c.relname,t.tgname,p.proname,t.tgtype,t.tgenabled,pg_get_triggerdef(t.oid),"
                       "pn.nspname,p.prosrc,p.oid::regproc::text,p.pronargs,t.tgisinternal,con.contype "
                       "FROM pg_trigger t "
                       "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
                       "JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace pn ON pn.oid=p.pronamespace "
                       "LEFT JOIN pg_constraint con ON con.oid=t.tgconstraint "
                       "WHERE n.nspname=current_schema() AND c.relname=ANY(%s)",[tables])
        present={(table,name):row for table,name,*row in cursor.fetchall()}
        # PostgreSQL precedence: role+database > role > database > all roles/databases. These
        # persistent settings need not be reflected in an already-open connection's current_setting.
        cursor.execute("SELECT split_part(setting,'=',2) FROM pg_db_role_setting s "
                       "CROSS JOIN LATERAL unnest(s.setconfig) AS setting "
                       "WHERE s.setdatabase IN (0,(SELECT oid FROM pg_database WHERE datname=current_database())) "
                       "AND s.setrole IN (0,(SELECT oid FROM pg_roles WHERE rolname=current_user)) "
                       "AND split_part(setting,'=',1)='session_replication_role' "
                       "ORDER BY (s.setrole<>0) DESC,(s.setdatabase<>0) DESC LIMIT 1")
        default=cursor.fetchone()

    def installed(table,name,function,kind):
        row=present.get((table,name))
        if row is None: return False
        actual_function,actual_kind,enabled,definition,namespace,body,sql_function,nargs,internal,_=row
        event={27:'DELETE OR UPDATE',19:'UPDATE',34:'TRUNCATE'}[kind]
        each='ROW' if kind & 1 else 'STATEMENT'
        expected=(f'CREATE TRIGGER {name} BEFORE {event} ON {quoted_schema}.{table} '
                  f'FOR EACH {each} EXECUTE FUNCTION {sql_function}()')
        # 'A' always fires, including origin; 'R' and 'D' do not. Full definition also checks
        # UPDATE OF columns, WHEN, arguments, constraint/deferred forms and transition relations.
        return (actual_function==function and namespace==schema and nargs==0 and not internal
                and actual_kind==kind and enabled in ('O','A') and definition==expected
                and hashlib.sha256(body.encode()).hexdigest()==PAYMENT_GUARD_FUNCTION_SHA256[function])
    failed=[name for table,name,function,kind in PAYMENT_EVIDENCE_GUARDS if not installed(table,name,function,kind)]
    expected_keys={(table,name) for table,name,_,_ in PAYMENT_EVIDENCE_GUARDS}
    for table in tables:
        extra=[row for key,row in present.items() if key[0]==table and key not in expected_keys and row[1] & 1
               and not (row[8] and row[9]=='f' and row[4]=='pg_catalog' and row[0].startswith('RI_FKey_'))]
        if extra: failed.append(f'unexpected_row_triggers:{table}')
        statements=[row for key,row in present.items() if key[0]==table and key not in expected_keys and not row[1] & 1]
        if statements: failed.append(f'unexpected_statement_triggers:{table}')
    if replication!='origin' or default is not None and default[0]!='origin':
        failed.append('session_replication_role')
    return failed


def real_mode_payment_problems():
    """Why this database may not run in real data mode, as lines of counts; empty when it may. Read-only.

    Real mode runs on a database that has never held sandbox payments: no payment or Stripe event row that is not
    recorded as live, and no paid wallet holding money that live payments do not wholly explain (every 'payment'
    credit live, and the balance equal to its ledger). And every guard that keeps that evidence from being relabelled
    is in place (PAYMENT_EVIDENCE_GUARDS): otherwise the counts above prove nothing.
    """
    problems=[]
    payments=Payment.objects.exclude(livemode=True).count()
    if payments: problems.append(f'{payments} payment row(s) not recorded as live (sandbox, or recorded before the mode was stored)')
    events=WebhookEvent.objects.exclude(livemode=True).count()
    if events: problems.append(f'{events} Stripe event row(s) not recorded as live')
    unexplained=0
    for wallet in Wallet.objects.filter(kind='paid').exclude(balance=0,reserved=0).order_by('pk'):
        ledger=LedgerEntry.objects.filter(wallet=wallet).aggregate(total=Sum('amount'))['total'] or ZERO
        if sandbox_funded(wallet) or ledger!=wallet.balance: unexplained+=1
    if unexplained: problems.append(f'{unexplained} paid wallet(s) holding money that live payments do not wholly explain')
    missing=missing_payment_evidence_guards()
    if missing: problems.append(f'{len(missing)} payment evidence guard check(s) failed ({", ".join(missing)}); '
                                'require the guards installed by migrations 0003, 0008 and 0020, no extra row/statement triggers, '
                                'and session_replication_role origin')
    return problems


def preservation_before_money():
    """Level 3 of the global lock order (core.retention): the preservation lock before any Reservation or Wallet row.

    Every preserved clinical write takes this lock through its trigger and holds it until commit, and reserve() writes
    the job (taking it) before locking wallets. A transaction that locked a wallet first and saved a job afterwards (an
    administrator's resolution, a batch stop or closeout) deadlocked with that payer's next request (RF-1). release,
    settle and absorb_failed_job take it here, right after the job row, so the order is structural rather than a
    property of each caller; reserve reaches it through its own job.save(payer) before the wallet locks."""
    from .retention import lock_preservation
    lock_preservation()


def payer_wallets(user,department):
    """The personal promotional wallet and the paid wallet that pays for this user's requests in this department."""
    promo=Wallet.objects.get(user=user,kind='promo')
    payer,_=Wallet.objects.get_or_create(organization=department.organization,kind='paid') if department.organization_pays else Wallet.objects.get_or_create(user=user,kind='paid')
    return promo,payer


def available_balance(user,department):
    """Unreserved funds a new request could hold (display only; reserve() re-checks under row locks)."""
    return sum((w.balance-w.reserved for w in payer_wallets(user,department)),ZERO)


@transaction.atomic
def reserve(job,maximum_cost=None,*,charge_limit=None):
    """Hold the customer's binding charge limit before any provider request. Either the maximum provider cost (held × 1.5)
    or an exact charge limit the customer saw and approved."""
    membership(job.user,job.department)
    from .models import Job
    job=Job.objects.select_for_update().get(pk=job.pk)
    maximum_charge=exact(charge_limit) if charge_limit is not None else exact(maximum_cost)*MULTIPLIER
    if maximum_charge<0: raise ValidationError('A charge limit cannot be negative.')
    if Reservation.objects.filter(job=job).exists(): return
    department=job.department
    promo,payer=payer_wallets(job.user,department)
    job.payer=department_payer(job.user_id,department)
    # Level 3 of the lock order before any money row: this write takes the preservation lock (the job trigger).
    job.save(update_fields=['payer'])
    locked={w.pk:w for w in Wallet.objects.select_for_update().filter(pk__in=[promo.pk,payer.pk]).order_by('pk')}
    # Real data mode never spends sandbox-funded money: the whole request is refused, before any hold, rather than
    # quietly skipping a balance the payer can see.
    if real_mode_refuses(locked[payer.pk]):
        raise ValidationError('This paid balance holds sandbox (test) payments, which never fund requests in real data mode. '
                              'No provider request was made.')
    available=sum((w.balance-w.reserved for w in locked.values()),ZERO)
    if available<maximum_charge:
        # The requester sees what the request needs, never the payer's balance: an organization's paid funds are shown to owners only.
        raise ValidationError(f'Insufficient available balance: this request needs up to ${maximum_charge.normalize():f} held, '
                              'more than the available balance. No provider request was made.')
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
    # Lock only the job row: the related rows are read, not written, and locking them deadlocks a wallet holder that audits.
    job=Job.objects.select_for_update(of=('self',)).select_related('encounter__department__organization','user').get(pk=job.pk)
    existing=Usage.objects.filter(job=job).first()
    if existing: return existing
    preservation_before_money()
    actual=exact(actual_cost)
    if simulated and actual!=0: raise ValidationError('Simulated integrations cannot create billable cost.')
    uncapped=exact(actual*MULTIPLIER)
    reservations=list(Reservation.objects.select_for_update().filter(job=job,state='held').select_related('wallet').order_by('wallet_id'))
    held=sum((r.amount for r in reservations),ZERO)
    if uncapped>0 and held<=0: raise ValidationError('No authorized charge limit is held for this job; settlement held for reconciliation.')
    # The held amount is the customer's binding limit: charge 1.5 × cost up to it, and absorb anything above it (below).
    charged=min(uncapped,held)
    over_limit=uncapped-charged
    wallets={w.pk:w for w in Wallet.objects.select_for_update().filter(pk__in=[r.wallet_id for r in reservations]).order_by('pk')}
    remaining=charged
    debits=[]
    # Personal promotional credit is always used before paid funds.
    for r in sorted(reservations,key=lambda r:0 if r.wallet.kind=='promo' else 1):
        debits.append((r,min(r.amount,remaining))); remaining-=debits[-1][1]
    # Real data mode never debits a balance sandbox payments funded. The worker refuses such a job before sending
    # (sandbox_hold); this is the last wall, before any write: nothing is charged and the job's settlement is held for
    # reconciliation. A hold on such a balance that this charge does not reach is released unspent, as always.
    if any(debit and real_mode_refuses(wallets[r.wallet_id]) for r,debit in debits):
        raise SandboxFundsRefused('This charge would be debited from a paid balance holding sandbox (test) payments, which real '
                                  'data mode never spends. Nothing was charged; settlement held for reconciliation.')
    for r,debit in debits:
        wallet=wallets[r.wallet_id]
        wallet.reserved-=r.amount; wallet.balance-=debit; wallet.save(update_fields=['reserved','balance'])
        if debit: LedgerEntry.objects.create(wallet=wallet,amount=-debit,kind='usage',key=f'usage:{job.pk}:{wallet.pk}',description='Provider cost × 1.5',job=job,balance_after=wallet.balance)
        r.state='settled'; r.save(update_fields=['state'])
        # The unused part of a paid hold becomes available just as on release().
        # Resume older adjustments only after the settlement and its outer transaction commit.
        if wallet.kind=='paid' and debit<r.amount: reconcile_after_commit(wallet)
    d=job.department
    result=Usage.objects.create(job=job,user=job.user,department=d,organization=d.organization,payer=job.payer or f'user:{job.user_id}',provider=provider,provider_request_id=provider_request_id,provider_resource_id=provider_resource_id,units=units,rates=rates,actual_cost=actual,charged_cost=charged,simulated=simulated)
    if over_limit>0:
        # Provider cost, customer charge and the absorbed difference stay separate: Usage.actual_cost, the usage ledger debits,
        # and this platform cost. The customer is never charged above the limit they approved.
        PlatformCost.objects.create(job=job,kind='absorbed_over_limit',amount=over_limit,
            description='Charge above the approved customer limit, absorbed by QuillMD',
            evidence_reference=f'usage:{result.pk} provider_cost:{actual} uncapped_charge:{uncapped} customer_limit:{held}')
        audit(job.user,'usage.over_limit_absorbed',job.pk,department=d,uncapped=str(uncapped),charged=str(charged),absorbed=str(over_limit))
    audit(job.user,'usage.settle',job.pk,department=d,actual=str(actual),charged=str(charged),simulated=simulated)
    return result

@transaction.atomic
def release(job):
    from .models import Job
    Job.objects.select_for_update().get(pk=job.pk)
    preservation_before_money()
    reservations=list(Reservation.objects.select_for_update().filter(job=job,state='held').order_by('wallet_id'))
    wallets={w.pk:w for w in Wallet.objects.select_for_update().filter(pk__in=[r.wallet_id for r in reservations]).order_by('pk')}
    for r in reservations:
        w=wallets[r.wallet_id]; w.reserved-=r.amount; w.save(update_fields=['reserved'])
        r.state='released'; r.save(update_fields=['state'])
        audit(job.user,'usage.release',job.pk,wallet=str(w.pk),amount=str(r.amount))
    # Apply only after the outer transaction releases wallet locks. Applying here
    # would acquire an older job while holding its wallet, inverting absorption's
    # job -> wallet order. Rollback also discards the pending callback.
    for w in wallets.values():
        if w.kind=='paid': reconcile_after_commit(w)

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
    # New paid funds are the trigger for reconciliation charges that this payer holds; other payers' rows are untouched.
    reconcile_after_commit(w,actor=p.user)


def reconcile_after_commit(wallet,actor=None):
    """Do not acquire another job's locks while a payment/release holds its wallet."""
    transaction.on_commit(lambda:apply_pending_reconciliations(actor=actor,wallet=wallet),robust=True)

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

def customer_limit(usage):
    """The binding charge limit for a usage row: the holds that settled for its job (None when nothing was ever held)."""
    held=sum((r.amount for r in Reservation.objects.filter(job_id=usage.job_id,state='settled')),ZERO)
    return held if held>0 else None

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

def apply_additional_debit(row,wallet,actor=None):
    """Debit a positive charge delta from an already locked paid wallet when its available balance allows it.

    Never from a balance real data mode refuses (sandbox-funded): the charge stays pending_funds, and the refusal is
    audited each time it is attempted. Both callers (reconcile_usage, apply_pending_reconciliations) come through here.
    """
    key=f'reconciliation:{row.usage_id}:{wallet.pk}'
    if LedgerEntry.objects.filter(key=key).exists(): return True
    if real_mode_refuses(wallet):
        audit(actor,'usage.reconciliation_sandbox_refused',row.usage.job_id,department=row.usage.department,wallet=str(wallet.pk),
              charge_delta=str(row.charge_delta))
        return False
    if wallet.balance-wallet.reserved<row.charge_delta: return False
    wallet.balance-=row.charge_delta; wallet.save(update_fields=['balance'])
    LedgerEntry.objects.create(wallet=wallet,amount=-row.charge_delta,kind='reconciliation',key=key,description='Reconciled provider cost above the configured estimate × 1.5 (additional charge)',job_id=row.usage.job_id,balance_after=wallet.balance)
    return True

@transaction.atomic
def reconcile_usage(usage,reconciled_cost,evidence_reference,actor,provider_credit_applied=ZERO,discount_applied=ZERO,evidence_sha256='',note='',evidence_kind='unclassified'):
    """Record authentic provider evidence for one usage row and settle the difference by appended ledger entries.

    The Usage row and its original 'usage' ledger entries are never modified. Credits back return to the wallets that
    were debited, in proportion to their original debits; additional charges come from the recorded payer's paid wallet.
    """
    from .models import Job
    usage=Usage.objects.select_related('job','department').get(pk=usage.pk)
    Job.objects.select_for_update().get(pk=usage.job_id)
    if CostReconciliation.objects.filter(usage=usage).exists(): raise ValidationError('This usage row has already been reconciled; history is append-only.')
    if actor is None or not getattr(actor,'pk',None): raise ValidationError('A recorded administrator is required.')
    if not isinstance(evidence_kind,str) or evidence_kind not in dict(CostReconciliation.EVIDENCE_KINDS): raise ValidationError('Unknown reconciliation evidence kind.')
    reconciled=exact(reconciled_cost);credit=exact(provider_credit_applied or ZERO);discount=exact(discount_applied or ZERO)
    if reconciled!=reconciled.quantize(Decimal('0.00000000001')): raise ValidationError('Reconciled cost is limited to 11 decimal places so its exact 1.5× delta fits the 12-decimal ledger.')
    if usage.simulated and reconciled!=0: raise ValidationError('Simulated usage has no provider cost to reconcile.')
    evidence_reference=(evidence_reference or '').strip()
    if not evidence_reference or len(evidence_reference)>240: raise ValidationError('An evidence reference (invoice number, export sha256 or report id) is required.')
    evidence_sha256=(evidence_sha256 or '').strip().lower()
    if evidence_sha256 and not re.fullmatch(r'[0-9a-f]{64}',evidence_sha256): raise ValidationError('Evidence sha256 must be 64 hexadecimal characters.')
    note=(note or '').strip()
    if len(note)>240: raise ValidationError('Note is limited to 240 characters.')
    # The customer's total never exceeds the limit they approved (the settled holds): evidence of a higher provider cost raises the
    # customer charge only up to that limit, and moves the absorbed amount for the rest. Rows without a hold keep plain 1.5×.
    limit=customer_limit(usage)
    uncapped_before=signed_exact(usage.actual_cost*MULTIPLIER); uncapped_after=signed_exact(reconciled*MULTIPLIER)
    customer_after=min(uncapped_after,limit) if limit is not None else uncapped_after
    delta=customer_after-usage.charged_cost
    over_limit_delta=(uncapped_after-customer_after)-(uncapped_before-usage.charged_cost)
    row=CostReconciliation(usage=usage,evidence_kind=evidence_kind,reconciled_cost=reconciled,provider_credit_applied=credit,discount_applied=discount,evidence_reference=evidence_reference,evidence_sha256=evidence_sha256,recorded_by=actor,note=note,charge_delta=delta,over_limit_delta=over_limit_delta,ledger_status='applied')
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
            if wallet.kind=='paid': reconcile_after_commit(wallet,actor=actor)
    elif delta>0:
        payer=payer_wallet(usage.payer)
        wallet=Wallet.objects.select_for_update().get(pk=payer.pk)
        row.save()
        if not apply_additional_debit(row,wallet,actor=actor):
            row.ledger_status='pending_funds'; row.save(update_fields=['ledger_status'])
    else: row.save()
    audit(actor,'usage.reconcile',usage.job_id,department=usage.department,reconciled_cost=str(reconciled),charge_delta=str(delta),ledger_status=row.ledger_status,evidence_reference=evidence_reference,evidence_kind=evidence_kind)
    return row

def apply_pending_reconciliations(actor=None,wallet=None):
    """Apply additional charges that were held for funds. Idempotent: the unique ledger key guards replay.

    Locks the job before the reconciliation row (the same order as absorb_failed_job) so the two never deadlock, and
    isolates each row so one failure cannot block the others or the payment that triggered the attempt.
    """
    from django.db import DatabaseError
    from .models import Job
    applied=[]
    pending=CostReconciliation.objects.filter(ledger_status='pending_funds')
    if wallet is not None:
        # A top-up applies only the charges its own payer holds; other tenants' rows wait for their own funds.
        pending=pending.filter(usage__payer=(f'user:{wallet.user_id}' if wallet.user_id else f'organization:{wallet.organization_id}'))
    for pk,job_id in list(pending.order_by('created_at').values_list('pk','usage__job_id')):
        try:
            with transaction.atomic():
                Job.objects.select_for_update().get(pk=job_id)
                row=CostReconciliation.objects.select_for_update().select_related('usage__department').get(pk=pk)
                if row.ledger_status!='pending_funds': continue
                if LedgerEntry.objects.filter(job_id=row.usage.job_id,kind='absorbed').exists() or PlatformCost.objects.filter(job_id=row.usage.job_id,kind='absorbed_failure').exists():
                    # The job was absorbed after this reconciliation was held: the user owes nothing further for it.
                    row.ledger_status='absorbed'; row.save(update_fields=['ledger_status'])
                    audit(actor,'usage.reconciliation_absorbed',row.usage.job_id,department=row.usage.department,charge_delta=str(row.charge_delta)); continue
                payer=payer_wallet(row.usage.payer)
                wallet=Wallet.objects.select_for_update().get(pk=payer.pk)
                if not apply_additional_debit(row,wallet,actor=actor): continue
                row.ledger_status='applied'; row.save(update_fields=['ledger_status'])
                audit(actor,'usage.reconciliation_applied',row.usage.job_id,department=row.usage.department,charge_delta=str(row.charge_delta))
                applied.append(row)
        except (DatabaseError,ValidationError) as error:
            audit(actor,'usage.reconciliation_apply_failed',job_id,error_class=type(error).__name__)
    return applied

@transaction.atomic
def absorb_failed_job(job,actor=None,note=''):
    """QuillMD absorbs settled provider cost whose output was never adopted: reverse the user's NET charge for the job and record one platform cost.

    The net charge is every 'usage' and 'reconciliation' ledger movement for the job, per wallet, so a reconciliation applied
    before the absorption is neither credited twice nor left charged. A pending additional charge is marked absorbed and never
    applied. Only a failed job can be absorbed. Idempotent: ledger keys and the one-absorbed-failure-per-job constraint.
    """
    from .models import Job
    job=Job.objects.select_for_update(of=('self',)).select_related('encounter__department','user').get(pk=job.pk)
    usage=Usage.objects.filter(job=job).first()
    if usage is None or usage.simulated: return None
    if job.state!='failed': raise ValidationError('Only a failed job can be absorbed; a succeeded or pending job keeps its charge.')
    if job.error.startswith('not_adopted:'): raise ValidationError('A successful generation the user did not adopt remains charged; there is no platform failure to absorb.')
    preservation_before_money()
    reconciliation=CostReconciliation.objects.select_for_update().filter(usage=usage).first()
    net={}
    for entry in LedgerEntry.objects.filter(job=job,kind__in=['usage','reconciliation']).order_by('wallet_id'):
        net[entry.wallet_id]=net.get(entry.wallet_id,ZERO)+entry.amount
    wallets={w.pk:w for w in Wallet.objects.select_for_update().filter(pk__in=list(net)).order_by('pk')}
    reversed_total=ZERO
    for wallet_id in sorted(net,key=str):
        owed=-net[wallet_id]
        key=f'absorbed:{job.pk}:{wallet_id}'
        if owed<=0 or LedgerEntry.objects.filter(key=key).exists(): continue
        wallet=wallets[wallet_id]; wallet.balance+=owed; wallet.save(update_fields=['balance'])
        LedgerEntry.objects.create(wallet=wallet,amount=owed,kind='absorbed',key=key,description='Usage charge reversed: provider cost of a platform failure absorbed by QuillMD',job=job,balance_after=wallet.balance)
        reversed_total+=owed
        if wallet.kind=='paid': reconcile_after_commit(wallet,actor=actor)
    if reconciliation and reconciliation.ledger_status=='pending_funds':
        reconciliation.ledger_status='absorbed'; reconciliation.save(update_fields=['ledger_status'])
    amount=reconciliation.reconciled_cost if reconciliation else usage.actual_cost
    evidence=f'usage:{usage.pk}'+(f' reconciliation:{reconciliation.evidence_reference}' if reconciliation else '')+(f' note:{note.strip()}' if note and note.strip() else '')
    cost,created=PlatformCost.objects.get_or_create(job=job,kind='absorbed_failure',defaults={'amount':amount,'description':'Provider cost absorbed: output not adopted','evidence_reference':evidence[:240],'recorded_by':actor if getattr(actor,'pk',None) else None})
    if created or reversed_total: audit(job.user,'usage.absorbed',job.pk,department=job.department,actual_cost=str(usage.actual_cost),platform_cost=str(cost.amount),reversed=str(reversed_total))
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
    validate_event_environment(event)
    event_id=event.get('id');kind=event.get('type')
    if not isinstance(event_id,str) or not event_id or len(event_id)>180 or not isinstance(kind,str) or len(kind)>80:
        raise ValidationError('Malformed payment event.')
    data=event.get('data',{})
    if not isinstance(data,dict): raise ValidationError('Malformed payment event data.')
    raw=data.get('object',{})
    if not isinstance(raw,dict): raise ValidationError('Malformed payment event object.')
    if live_payments():
        if raw.get('livemode') is False: raise ValidationError('Test payment objects are not accepted in live mode.')
    elif raw.get('livemode') is True: raise ValidationError('Live payment objects are not accepted.')
    keys=('id','payment_intent','amount','status','currency','payment_status','amount_total','mode')
    obj={k:raw[k] for k in keys if k in raw}
    if 'metadata' in raw:
        if not isinstance(raw['metadata'],dict): raise ValidationError('Malformed payment metadata.')
        obj['metadata']={'payment_id':raw['metadata'].get('payment_id')}
    semantic=hashlib.sha256(json.dumps({'kind':kind,'object':obj},sort_keys=True,separators=(',',':')).encode()).hexdigest()
    row,_=WebhookEvent.objects.get_or_create(event_id=event_id,defaults={'kind':kind,'payload_hash':payload_hash,'semantic_hash':semantic,'object_data':obj,'status':'received','livemode':event['livemode']})
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
