"""R-B, part 2: a targeted concurrent reproduction attempt of a DatabaseError inside billing.settle().

Evidence for docs/rebuild/v1/residuals-assessment-20260929.md. Not part of the CI suite (it takes minutes); run it with
the Django test runner and this directory on PYTHONPATH, label `settle_interleavings`, against a throwaway PostgreSQL
database. Output: JSON at $RESID_EXPLORER_OUTPUT.

WHAT IT DOES. The worker's settlement of a running job J (user U, department D, organization O, holds on U's promotional
AND paid wallets, exactly how run_one calls settle: a fresh transaction) is raced against one ordinary operation of
another actor on the same rows, on its own thread and database connection. Every lock-taking statement of either side
(INSERT/UPDATE/DELETE, FOR UPDATE/NO KEY UPDATE/SHARE/KEY SHARE, pg_advisory) is a pause point:

  direction 'settle paused': settle stops right after its k-th lock-taking statement, holding everything so far;
                             the other operation runs until it finishes or waits for a lock; settle resumes.
  direction 'party paused':  the same with the roles swapped.

k runs from 1 until the paused side finishes without reaching k. For two parties whose statement sequence does not
depend on timing, this visits every prefix at which one side can hold locks while the other runs, which is where any
two-party lock cycle (deadlock) or constraint conflict must show. A DatabaseError is looked for everywhere it could be
hidden: raised from any statement of either side (even if the application later catches it), raised out of either
side, an HTTP 5xx, the application's own failure audits (usage.reconciliation_apply_failed, usage.absorb_failed), an
error logged by a robust on-commit callback, and the server's own deadlock counter (pg_stat_database.deadlocks).
Each scenario also checks that settle completed (one usage row, no held reservation on J) and that every wallet of the
scenario still equals its ledger and its held reservations.

POSITIVE CONTROL. A synthetic party that takes U's paid wallet and THEN the preservation lock (the order the global
lock order forbids) must produce a deadlock (40P01) at some pause point, or the instrument is not measuring anything.

Synthetic records only; the provider, Stripe and email are never contacted.
"""
import json
import logging
import os
import threading
import time
import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core import signing
from django.db import DatabaseError, connection, connections, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django_otp.plugins.otp_totp.models import TOTPDevice

from core import billing, clinic_invitations, jobs, retention
from core.billing import reserve
from core.models import (AuditEvent, CostReconciliation, Department, Encounter, Invitation, Job, LedgerEntry, Membership,
                         Payment, ProviderReceipt, Reservation, Usage, User, Wallet)
from core.recovery import recovery_token_generator
from core.security import digest, token
from core.tests.test_billing_policy import fund
from core.tests.test_retention_flow_locks import LOCKED, LockFlowFixture

UNITS = {'input_tokens': 100, 'output_tokens': 0, 'cached_input_tokens': 0, 'cache_creation_tokens': 0}
RATES = {'input_per_million': '1000', 'output_per_million': '0', 'cached_per_million': '0'}
PASSWORD = 'Synthetic-Only-4821!private'
FAILURE_AUDITS = ('usage.reconciliation_apply_failed', 'usage.absorb_failed')


def locking(sql):
    text = sql.lstrip().upper()
    return (text.startswith(('INSERT', 'UPDATE', 'DELETE'))
            or any(clause in text for clause in (' FOR UPDATE', ' FOR NO KEY UPDATE', ' FOR SHARE', ' FOR KEY SHARE', 'PG_ADVISORY')))


class Party:
    """One actor: its own thread and connection, an optional pause after its k-th lock-taking statement."""

    def __init__(self, name, action, pause_at=None):
        self.name, self.action, self.pause_at = name, action, pause_at
        self.count, self.pid, self.errors, self.outcome = 0, None, [], {}
        self.paused, self.resume, self.done = threading.Event(), threading.Event(), threading.Event()

    def wrapper(self, execute, sql, params, many, context):
        try:
            result = execute(sql, params, many, context)
        except DatabaseError as error:
            cause = error.__cause__
            self.errors.append({'class': type(error).__name__, 'sqlstate': getattr(cause, 'sqlstate', None),
                                'message': (str(error).splitlines() or [''])[0][:160], 'statement': sql[:100]})
            raise
        if locking(sql):
            self.count += 1
            if self.count == self.pause_at and not self.paused.is_set():
                self.paused.set()
                self.resume.wait(60)
        return result

    def run(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_backend_pid()')
                self.pid = cursor.fetchone()[0]
            with connection.execute_wrapper(self.wrapper):
                value = self.action()
            status = getattr(value, 'status_code', None)
            self.outcome = {'status': status}
            if status is not None and status >= 500:
                info = getattr(value, 'exc_info', None)
                self.outcome['server_error'] = repr(info[1])[:200] if info else 'HTTP %s' % status
        except BaseException as error:  # recorded, never lost in the thread
            self.outcome = {'error': f'{type(error).__name__}: {(str(error).splitlines() or [""])[0][:160]}'}
            if isinstance(error, DatabaseError) and not self.errors:
                self.errors.append({'class': type(error).__name__, 'sqlstate': getattr(error.__cause__, 'sqlstate', None),
                                    'message': (str(error).splitlines() or [''])[0][:160], 'statement': 'COMMIT or outside a statement'})
        finally:
            self.done.set()
            connections.close_all()

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()


class Captured(logging.Handler):
    def __init__(self):
        super().__init__(logging.ERROR)
        self.records = []

    def emit(self, record):
        self.records.append(f'{record.name}: {record.getMessage()[:160]}')


def waiting(pid):
    with connection.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM pg_locks WHERE NOT granted AND pid=%s', [pid])
        return cursor.fetchone()[0] > 0


def phase_of(party, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if party.done.is_set():
            return 'finished'
        if party.pid and waiting(party.pid):
            return 'waited'
        time.sleep(.01)
    return 'still running'


def server_deadlocks():
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_stat_clear_snapshot()')
        cursor.execute('SELECT deadlocks FROM pg_stat_database WHERE datname=current_database()')
        return cursor.fetchone()[0]


# ---- the other actors. Each builder prepares its rows on the main thread and returns the operation to race. ----

def generate_other_document(t, sc):
    draft = sc.draft('Symptoms: no chest pain')
    quote = sc.doctor.get(f'/encounters/{draft.pk}/').context['usage_quote']
    return lambda: sc.doctor.post(f'/encounters/{draft.pk}/generate/', {'usage_quote': quote, 'revision': str(draft.revision)})


def generate_on_the_running_document(t, sc):
    quote = sc.doctor.get(f'/encounters/{sc.encounter.pk}/').context.get('usage_quote') or ''
    return lambda: sc.doctor.post(f'/encounters/{sc.encounter.pk}/generate/', {'usage_quote': quote, 'revision': str(sc.encounter.revision)})


def cancel_another_queued_job(t, sc):
    draft = sc.draft('Symptoms: no chest pain')
    other = jobs.enqueue(draft, sc.user)
    return lambda: sc.doctor.post(f'/encounters/{draft.pk}/jobs/{other.pk}/cancel/')


def cancel_the_running_job(t, sc):
    return lambda: sc.doctor.post(f'/encounters/{sc.encounter.pk}/jobs/{sc.job.pk}/cancel/')


def held_job(sc, receipt=False):
    other = Job.objects.create(encounter=sc.draft('Symptoms: no chest pain'), user=sc.user, request_key=f'{sc.label}-held',
                               config={'mode': 'live'})
    reserve(other, charge_limit=Decimal('0.5'))
    if receipt:
        ProviderReceipt.objects.create(job=other, provider='anthropic:synthetic', provider_request_id=f'req_{sc.label}_held',
                                       actual_cost=Decimal('0.1'), units=UNITS, rates=RATES)
    Job.objects.filter(pk=other.pk).update(state='reconciliation')
    return other


def resolve_another_held_job(t, sc):
    other = held_job(sc)
    return lambda: sc.console.post(f'/console/jobs/{other.pk}/resolve/', {'outcome': 'release_no_cost', 'evidence_note': 'Synthetic console lookup for this probe'})


def resolve_another_held_job_with_a_receipt(t, sc):
    other = held_job(sc, receipt=True)
    return lambda: sc.console.post(f'/console/jobs/{other.pk}/resolve/', {'outcome': 'release_no_cost', 'evidence_note': 'Synthetic console lookup for this probe'})


def resolve_the_running_job(t, sc):
    return lambda: sc.console.post(f'/console/jobs/{sc.job.pk}/resolve/', {'outcome': 'release_no_cost', 'evidence_note': 'Synthetic console lookup for this probe'})


def settled_job(sc, charge_limit=Decimal('0.5'), state='succeeded', error=''):
    other = Job.objects.create(encounter=sc.draft('Symptoms: no chest pain'), user=sc.user, request_key=f'{sc.label}-settled',
                               config={'mode': 'live'})
    reserve(other, charge_limit=charge_limit)
    usage = billing.settle(other, Decimal('0.1'), UNITS, RATES, 'anthropic:synthetic', f'req_{sc.label}_settled', provider_resource_id=f'msg_{sc.label}_settled')
    Job.objects.filter(pk=other.pk).update(state=state, error=error)
    return other, usage


def absorb_a_failed_job(t, sc):
    other, _ = settled_job(sc, state='failed', error='platform_failure: synthetic')
    return lambda: billing.absorb_failed_job(Job.objects.get(pk=other.pk))


def reconcile_usage_additional_charge(t, sc):
    _, usage = settled_job(sc)
    return lambda: sc.console.post(f'/console/usage/{usage.pk}/reconcile/', {'reconciled_cost': '0.3', 'evidence_kind': 'invoice', 'evidence_reference': f'INV-{sc.label}'})


def reconcile_usage_credit_back(t, sc):
    _, usage = settled_job(sc)
    return lambda: sc.console.post(f'/console/usage/{usage.pk}/reconcile/', {'reconciled_cost': '0.05', 'evidence_kind': 'invoice', 'evidence_reference': f'INV-{sc.label}'})


def apply_a_pending_reconciliation(t, sc):
    _, usage = settled_job(sc, charge_limit=Decimal('4'))
    sc.paid.refresh_from_db()
    blocker = Job.objects.create(encounter=sc.draft('Symptoms: no chest pain'), user=sc.user, request_key=f'{sc.label}-blocker', config={'mode': 'live'})
    reserve(blocker, charge_limit=sc.paid.balance - sc.paid.reserved)
    row = billing.reconcile_usage(usage, Decimal('4'), f'INV-{sc.label}', t.admin)
    assert row.ledger_status == 'pending_funds', row.ledger_status
    fund(sc.paid, Decimal('10'), f'payment:{sc.label}-pending')
    return lambda: billing.apply_pending_reconciliations(actor=t.admin, wallet=Wallet.objects.get(pk=sc.paid.pk))


def paid_checkout(sc):
    payment = Payment.objects.create(user=sc.user, wallet=sc.paid, amount_cents=1000, stripe_session=f'cs_test_{sc.label}', livemode=False)
    return payment, {'metadata': {'payment_id': str(payment.pk)}, 'id': f'cs_test_{sc.label}', 'currency': 'usd', 'amount_total': 1000,
                     'mode': 'payment', 'payment_status': 'paid', 'payment_intent': f'pi_{sc.label}'}


def webhook_credits_a_top_up(t, sc):
    _, session = paid_checkout(sc)
    return lambda: billing.checkout_event('checkout.session.completed', session)


def webhook_records_a_refund(t, sc):
    _, session = paid_checkout(sc)
    billing.checkout_event('checkout.session.completed', session)
    return lambda: billing.reconcile_refund({'payment_intent': f'pi_{sc.label}', 'amount': 100, 'currency': 'usd', 'id': f're_{sc.label}', 'status': 'succeeded'})


def personal_checkout(t, sc):
    data = {'amount': '10.00', 'consent': 'on', 'payer': 'personal',
            'checkout_token': signing.dumps({'user': str(sc.user.pk), 'nonce': sc.label}, salt='checkout-authorization')}
    session = SimpleNamespace(id=f'cs_test_checkout_{sc.label}', url='https://checkout.stripe.com/test/synthetic-probe')

    def run():
        with override_settings(STRIPE_SECRET_KEY='sk_test_synthetic_adapter'), patch('stripe.checkout.Session.create', return_value=session):
            return sc.doctor.post('/billing/checkout/', data)
    return run


def department_invitation_existing_account(t, sc):
    department = Department.objects.create(organization=sc.organization, name=f'{sc.label} second')
    Membership.objects.create(user=sc.owner, department=department, role='owner')
    raw = token()
    Invitation.objects.create(email=sc.user.email, department=department, role='clinician', invited_by=sc.owner,
                              token_hash=digest(raw), expires_at=timezone.now() + timedelta(days=1))
    return lambda: sc.doctor.post(f'/invite/{raw}/', {})


def clinic_invitation_existing_account(t, sc):
    _, raw = clinic_invitations.issue(t.admin, sc.user.email, f'{sc.label} clinic', 'Synthetic front desk')
    return lambda: sc.doctor.post(f'/invite/clinic/{raw}/', {})


def suspend_the_account(t, sc):
    return lambda: sc.console.post(f'/console/accounts/{sc.user.pk}/', {'active': ''})


def revoke_the_accounts_sessions(t, sc):
    return lambda: sc.console.post(f'/console/accounts/{sc.user.pk}/sessions/')


def reset_the_accounts_mfa(t, sc):
    TOTPDevice.objects.create(user=sc.user, name='Synthetic authenticator', confirmed=True)

    def run():
        with override_settings(QUILLMD_MFA_REQUIRED_ALL=True):
            return sc.console.post(f'/console/accounts/{sc.user.pk}/mfa-reset/', {'reason': 'Synthetic identity check for this probe', 'confirm': 'on'})
    return run


def password_recovery(t, sc):
    client = Client(raise_request_exception=False)
    uid = urlsafe_base64_encode(force_bytes(sc.user.pk))
    step = client.get(f'/recovery/confirm/{uid}/{recovery_token_generator.make_token(sc.user)}/')
    assert step.status_code == 302, step.status_code
    return lambda: client.post(step['Location'], {'new_password1': PASSWORD + 'x', 'new_password2': PASSWORD + 'x'})


def sign_in(t, sc):
    return lambda: Client(raise_request_exception=False).post('/login/', {'email': sc.user.email, 'password': PASSWORD})


def owner_deactivates_the_membership(t, sc):
    owner = Client(raise_request_exception=False)
    owner.force_login(sc.owner)
    membership = Membership.objects.get(user=sc.user, department=sc.department)
    return lambda: owner.post(f'/team/membership/{membership.pk}/', {'role': 'clinician'})


def owner_creates_a_department(t, sc):
    owner = Client(raise_request_exception=False)
    owner.force_login(sc.owner)
    return lambda: owner.post('/team/departments/', {'name': f'{sc.label} new'})


def payer_change(t, sc):
    type(t.admin).objects.filter(pk=t.admin.pk).update(is_superuser=True)

    def run():
        with override_settings(QUILLMD_PAYER_ROLE_GRANTED=True):
            return sc.console.post(f'/console/departments/{sc.department.pk}/payer/', {'organization_pays': 'on', 'reason': 'Synthetic payer change for this probe', 'confirm': 'on'})
    return run


def notes_save_on_another_document(t, sc):
    draft = sc.draft('Symptoms: no chest pain')
    return lambda: sc.doctor.post(f'/encounters/{draft.pk}/notes/', {'notes': 'Symptoms: SYNTHETIC CORRECTION', 'revision': str(draft.revision)})


def notes_save_on_the_running_document(t, sc):
    return lambda: sc.doctor.post(f'/encounters/{sc.encounter.pk}/notes/', {'notes': 'Symptoms: SYNTHETIC CORRECTION', 'revision': str(sc.encounter.revision)})


def hold(scope):
    def build(t, sc):
        target = {'organization': sc.organization.pk, 'department': sc.department.pk, 'patient': sc.patient.pk,
                  'encounter': sc.encounter.pk, 'global': None}[scope]
        return lambda: retention.create_hold(t.admin, scope, target, 'a' * 64, uuid.uuid4())
    build.__name__ = f'preservation_hold_{scope}'
    return build


def release_a_hold(t, sc):
    held = retention.create_hold(t.admin, 'patient', sc.patient.pk, 'a' * 64, uuid.uuid4())
    return lambda: retention.release_hold(t.second, held.pk, 'b' * 64)


def mark_stale(t, sc):
    return jobs.mark_stale


def second_worker_settles_another_job(t, sc):
    """NOT an ordinary actor (the worker is one process): kept to show two settlements of one payer serialize."""
    other = Job.objects.create(encounter=sc.draft('Symptoms: no chest pain'), user=sc.user, request_key=f'{sc.label}-second', config={'mode': 'live'})
    reserve(other, charge_limit=Decimal('0.5'))
    Job.objects.filter(pk=other.pk).update(state='running')
    return lambda: billing.settle(Job.objects.get(pk=other.pk), Decimal('0.1'), UNITS, RATES, 'anthropic:synthetic', f'req_{sc.label}_second', provider_resource_id=f'msg_{sc.label}_second')


def CONTROL_wallet_then_preservation_lock(t, sc):
    """POSITIVE CONTROL, never an application path: the order the global lock order forbids."""
    def run():
        with transaction.atomic():
            Wallet.objects.select_for_update().get(pk=sc.paid.pk)
            retention.lock_preservation()
            Wallet.objects.select_for_update().get(pk=sc.promo.pk)
    return run


PARTIES = [generate_other_document, generate_on_the_running_document, cancel_another_queued_job, cancel_the_running_job,
           resolve_another_held_job, resolve_another_held_job_with_a_receipt, resolve_the_running_job, absorb_a_failed_job,
           reconcile_usage_additional_charge, reconcile_usage_credit_back, apply_a_pending_reconciliation,
           webhook_credits_a_top_up, webhook_records_a_refund, personal_checkout, department_invitation_existing_account,
           clinic_invitation_existing_account, suspend_the_account, revoke_the_accounts_sessions, reset_the_accounts_mfa,
           password_recovery, sign_in, owner_deactivates_the_membership, owner_creates_a_department, payer_change,
           notes_save_on_another_document, notes_save_on_the_running_document, hold('organization'), hold('department'),
           hold('patient'), hold('encounter'), hold('global'), release_a_hold, mark_stale, second_worker_settles_another_job,
           CONTROL_wallet_then_preservation_lock]


@override_settings(**LOCKED)
class SettleInterleavings(LockFlowFixture, TransactionTestCase):
    counter = 0

    def scenario(self):
        SettleInterleavings.counter += 1
        label = f'x{SettleInterleavings.counter}'
        user, organization, department, patient, template, encounter, _ = self.make_scope(label)
        user.set_password(PASSWORD)
        user.save(update_fields=['password'])
        owner = User.objects.create_user(username=f'{label}-owner', email=f'{label}-owner@synthetic.invalid', verified_at=timezone.now())
        Membership.objects.create(user=owner, department=department, role='owner')
        billing.welcome_credit(owner)
        promo, paid = Wallet.objects.get(user=user, kind='promo'), Wallet.objects.get(user=user, kind='paid')
        fund(paid, Decimal('5'), f'payment:{label}')
        job = Job.objects.create(encounter=encounter, user=user, request_key=f'{label}-J', config={'mode': 'live'})
        reserve(job, charge_limit=Decimal('10.3'))  # the whole promotional balance and 0.3 of the paid one
        Job.objects.filter(pk=job.pk).update(state='running', started_at=timezone.now())
        doctor = Client(raise_request_exception=False)
        doctor.force_login(user)
        console = self.custodian_client()

        def draft(notes=''):
            return Encounter.objects.create(department=department, patient=patient, template_version=encounter.template_version,
                                            created_by=user, notes=notes, service_date=encounter.service_date)
        return SimpleNamespace(label=label, user=user, organization=organization, department=department, patient=patient,
                               encounter=encounter, owner=owner, promo=promo, paid=paid, job=job, doctor=doctor,
                               console=console, draft=draft)

    def scenario_wallets(self, sc):
        return Wallet.objects.filter(user__in=[sc.user, sc.owner]) | Wallet.objects.filter(organization=sc.organization)

    def one(self, build, paused_side, k):
        sc = self.scenario()
        action = build(self, sc)
        before_failures = AuditEvent.objects.filter(action__in=FAILURE_AUDITS).count()
        settling = Party('settle', lambda: billing.settle(Job.objects.get(pk=sc.job.pk), Decimal('0.1'), UNITS, RATES, 'anthropic:synthetic',
                                                           f'req_{sc.label}', provider_resource_id=f'msg_{sc.label}'),
                         pause_at=k if paused_side == 'settle' else None)
        other = Party(build.__name__, action, pause_at=k if paused_side == 'party' else None)
        first, second = (settling, other) if paused_side == 'settle' else (other, settling)
        captured = Captured()
        logging.getLogger('django').addHandler(captured)
        try:
            first.start()
            deadline = time.monotonic() + 30
            while not (first.paused.is_set() or first.done.is_set()) and time.monotonic() < deadline:
                time.sleep(.005)
            exhausted = not first.paused.is_set()
            second.start()
            phase = phase_of(second)
            first.resume.set()
            for party in (first, second):
                party.thread.join(60)
            hung = [p.name for p in (first, second) if p.thread.is_alive()]
        finally:
            first.resume.set()
            logging.getLogger('django').removeHandler(captured)
        wallets = [{'kind': w.kind, 'balance_is_ledger': w.balance == sum(LedgerEntry.objects.filter(wallet=w).values_list('amount', flat=True), Decimal(0)),
                    'reserved_is_held': w.reserved == sum(Reservation.objects.filter(wallet=w, state='held').values_list('amount', flat=True), Decimal(0))}
                   for w in self.scenario_wallets(sc)]
        settled = Usage.objects.filter(job=sc.job).exists() and not Reservation.objects.filter(job=sc.job, state='held').exists()
        return {'party': build.__name__, 'paused': paused_side, 'k': k, 'exhausted': exhausted,
                'second_phase': phase, 'hung': hung,
                'settle': {'errors': settling.errors, 'outcome': settling.outcome, 'lock_statements': settling.count},
                'other': {'errors': other.errors, 'outcome': other.outcome, 'lock_statements': other.count},
                'failure_audits': AuditEvent.objects.filter(action__in=FAILURE_AUDITS).count() - before_failures,
                'logged_errors': captured.records, 'settled': settled,
                'wallets_consistent': all(w['balance_is_ledger'] and w['reserved_is_held'] for w in wallets)}

    def test_explore(self):
        started = time.monotonic()
        deadlocks_before = server_deadlocks()
        rows = []
        only = [name for name in os.environ.get('RESID_EXPLORER_ONLY', '').split(',') if name]
        for build in [party for party in PARTIES if not only or party.__name__ in only]:
            for paused_side in ('settle', 'party'):
                k = 1
                while True:
                    row = self.one(build, paused_side, k)
                    rows.append(row)
                    if row['exhausted'] or k >= 80:
                        break
                    k += 1
        time.sleep(2)
        deadlocks_after = server_deadlocks()

        def failed(row):
            return bool(row['settle']['errors'] or row['other']['errors'] or 'error' in row['settle']['outcome']
                        or 'error' in row['other']['outcome'] or 'server_error' in row['other']['outcome']
                        or row['failure_audits'] or row['logged_errors'] or row['hung'] or not row['settled']
                        or not row['wallets_consistent'])
        by_party = {}
        for row in rows:
            entry = by_party.setdefault(row['party'], {'scenarios': 0, 'failed': 0, 'second_waited': 0, 'statuses': set(),
                                                        'settle_errors': [], 'other_errors': []})
            entry['scenarios'] += 1
            entry['failed'] += failed(row)
            entry['second_waited'] += row['second_phase'] == 'waited'
            entry['statuses'].add(row['other']['outcome'].get('status'))
            entry['settle_errors'] += [e['sqlstate'] for e in row['settle']['errors']]
            entry['other_errors'] += [e['sqlstate'] for e in row['other']['errors']]
        for entry in by_party.values():
            entry['statuses'] = sorted(str(s) for s in entry['statuses'])
        control = by_party.pop('CONTROL_wallet_then_preservation_lock', {'failed': 0, 'settle_errors': [], 'other_errors': []})
        ordinary = {name: entry for name, entry in by_party.items()}
        summary = {'scenarios': len(rows), 'seconds': round(time.monotonic() - started, 1),
                   'server_deadlocks_during_run': deadlocks_after - deadlocks_before,
                   'failed_scenarios_excluding_control': sum(entry['failed'] for entry in ordinary.values()),
                   'control': control, 'by_party': ordinary}
        output = os.environ.get('RESID_EXPLORER_OUTPUT')
        if output:
            with open(output, 'w') as stream:
                json.dump({'summary': summary, 'rows': rows}, stream, indent=1, default=str)
        print(json.dumps(summary, indent=1, default=str))
        self.assertGreater(control['failed'], 0, 'the positive control produced no failure: the instrument measures nothing')
        self.assertIn('40P01', control['settle_errors'] + control['other_errors'])
        self.assertEqual(summary['failed_scenarios_excluding_control'], 0)
