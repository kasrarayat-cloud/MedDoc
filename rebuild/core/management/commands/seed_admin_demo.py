"""Synthetic operational data for exercising the administration console.

⚠️ EVERY ROW IS CREATED THROUGH THE REAL BILLING PATH — `reserve`, `settle`, `release`,
`absorb_failed_job`, `reconcile_usage`, `record_stripe_event`, `process_stripe_event`. Nothing
here hand-writes a Wallet balance or a LedgerEntry.

That is not fastidiousness. A fixture that pokes rows in directly can produce a state the product
cannot reach — a balance that disagrees with its ledger, a Usage row with no reservation, a refund
larger than its payment — and then the console screenshots prove that the console renders an
impossible world correctly. Going through the real functions means the wallet-integrity panel on
the dashboard is a genuine check on this data rather than a decoration.

Synthetic only, and it refuses to run otherwise: it requires `SYNTHETIC_ONLY`, it refuses if any
non-synthetic account exists, and it refuses to run twice.

    python manage.py seed_admin_demo
"""
import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.billing import (absorb_failed_job, process_stripe_event, reconcile_usage,
                          record_stripe_event, release, reserve, settle)
from core.models import (Department, Encounter, Invitation, Job, Patient, PlatformCost, Payment,
                         TemplateVersion, User, Wallet)
from core.security import audit, digest, token

SYNTHETIC_DOMAIN = '@synthetic.quillmd.invalid'
MARKER = 'admin-console-demo'
PROVIDER = 'anthropic:claude-demo'
# Every rate key the pricing formula reads, so the recomputation cannot KeyError into a mismatch.
RATES = {'input_per_million': '3', 'output_per_million': '15', 'cached_per_million': '0.30', 'discount_rate': '0'}


def event(kind, obj, index):
    """A signed-shaped Stripe event, minus the signature: `record_stripe_event` validates the rest."""
    return {'id': f'evt_{MARKER}_{index}', 'object': 'event', 'type': kind, 'livemode': False,
            'data': {'object': obj}}


class Command(BaseCommand):
    help = 'Create synthetic jobs, charges, payments, refunds and failures for console verification.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Add another round even if demo rows exist.')

    # All or nothing: a half-seeded database leaves unique provider-request ids behind and the
    # next attempt fails on them instead of on whatever actually broke.
    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.SYNTHETIC_ONLY:
            raise CommandError('Synthetic-only environment required.')
        real = User.objects.exclude(email__endswith=SYNTHETIC_DOMAIN).exclude(email__endswith='@synthetic.invalid')
        if real.exists():
            raise CommandError(f'Refusing to run: {real.count()} account(s) are not synthetic. '
                               'This command is for an isolated verification database only.')
        if PlatformCost.objects.filter(description__contains=MARKER).exists() and not options['force']:
            self.stdout.write('Demo data already present; nothing to do. Pass --force to add another round.')
            return
        doctor = User.objects.filter(email__startswith='doctor').first()
        employee = User.objects.filter(email__startswith='xray_employee').first()
        ultrasound = User.objects.filter(email__startswith='ultrasound').first()
        if not (doctor and employee and ultrasound):
            raise CommandError('Run `manage.py seed_private` first; this builds on its accounts.')
        version = TemplateVersion.objects.select_related('template__department').first()
        if version is None:
            raise CommandError('No template version exists; run `manage.py seed_private` first.')
        department = version.template.department
        made = []

        # `reserve()` enforces department membership, so each account needs a form in a department
        # it actually belongs to. The second department reuses the same BLANK original file — it is
        # the seeded fixture, carries no patient data, and sharing it keeps this command from
        # inventing a document.
        from core.models import Membership, Template
        versions = {}
        for account in (doctor, employee, ultrasound):
            member = Membership.objects.filter(user=account, active=True).select_related('department').first()
            if member is None:
                raise CommandError(f'{account.email} belongs to no department.')
            scope = member.department
            if scope.pk not in versions:
                if scope.pk == department.pk:
                    versions[scope.pk] = version
                else:
                    source = version.template
                    clone = Template.objects.create(department=scope, name=source.name, format=source.format,
                                                    original_name=source.original_name,
                                                    original_path=source.original_path, sha256=source.sha256,
                                                    warnings=source.warnings, created_by=account)
                    versions[scope.pk] = TemplateVersion.objects.create(template=clone, number=1,
                                                                        fields=version.fields, created_by=account)
            if not Patient.objects.filter(department=scope).exists():
                Patient.objects.create(department=scope, display_name=f'Synthetic Example {scope.name}',
                                       reference=f'SYNTH-{MARKER}', created_by=account)

        def encounter(who, note):
            scope = Membership.objects.filter(user=who, active=True).select_related('department').first().department
            return Encounter.objects.create(department=scope, patient=Patient.objects.filter(department=scope).first(),
                                            template_version=versions[scope.pk], created_by=who,
                                            service_date=timezone.localdate(),
                                            notes=f'History: {note}\nFindings: synthetic.\nPlan: synthetic.')

        def job(who, kind, key):
            return Job.objects.create(encounter=encounter(who, key), user=who, kind=kind,
                                      request_key=f'{MARKER}:{key}', config={'pricing_version': f'{MARKER}-rates-v1'})

        def provider_call(target, units, request_id, rates=None):
            """Settle a charge the way the worker does: the durable receipt FIRST, then settle().

            `core.jobs.run_one` writes a ProviderReceipt before it settles, and `audit_billing`
            checks that every settled Usage has one. Omitting it produced demo data that made the
            shipped billing audit fail — a fixture that cannot pass the product's own audit is not
            demonstrating the product.
            """
            from core.models import ProviderReceipt
            from core.management.commands.audit_billing import recompute_cost
            rates = rates or RATES
            # THE COST IS DERIVED, NEVER TYPED. audit_billing recomputes every settled cost from
            # its own units and rates and fails the whole audit when the two disagree. Choosing a
            # plausible-looking number by hand produced exactly that: three rows, all
            # recomputed_defined_cost_matches false. Calling the auditor's own function means the
            # fixture agrees with the auditor by construction rather than by coincidence.
            cost = recompute_cost(PROVIDER, units, rates, False)
            ProviderReceipt.objects.get_or_create(job=target, defaults={
                'provider': PROVIDER, 'provider_request_id': request_id, 'provider_resource_id': '',
                'actual_cost': cost, 'units': units, 'rates': rates, 'simulated': False})
            target.provider = PROVIDER
            target.provider_request_id = request_id
            target.save(update_fields=['provider', 'provider_request_id'])
            return settle(target, cost, units, rates, PROVIDER, request_id, False)

        # 1 — an ordinary settled generation. Promotional credit is spent first, so this exercises
        #     the promo/paid split the console now prints on every ledger row.
        settled = job(doctor, 'generation', 'settled')
        reserve(settled, Decimal('0.40'))
        provider_call(settled, {'input_tokens': 4210, 'output_tokens': 866, 'cached_input_tokens': 0},
                      f'req_{MARKER}_settled')
        settled.state = 'succeeded'; settled.started_at = timezone.now() - timedelta(minutes=9)
        settled.finished_at = timezone.now() - timedelta(minutes=8)
        settled.save(update_fields=['state', 'started_at', 'finished_at'])
        made.append('settled generation with a real charge')

        # 2 — the provider cost exceeded the limit the customer approved. settle() caps the charge
        #     and records the difference as an `absorbed_over_limit` platform cost.
        over = job(employee, 'generation', 'over-limit')
        reserve(over, charge_limit=Decimal('0.05'))
        provider_call(over, {'input_tokens': 900000, 'output_tokens': 150000, 'cached_input_tokens': 0},
                      f'req_{MARKER}_over')
        over.state = 'succeeded'; over.started_at = timezone.now() - timedelta(minutes=30)
        over.finished_at = timezone.now() - timedelta(minutes=29)
        over.save(update_fields=['state', 'started_at', 'finished_at'])
        made.append('charge capped at the approved limit, difference absorbed')

        # 3 — a platform failure: charged, then reversed in full and carried by QuillMD.
        broke = job(ultrasound, 'generation', 'absorbed')
        reserve(broke, Decimal('0.30'))
        provider_call(broke, {'input_tokens': 21000, 'output_tokens': 4000, 'cached_input_tokens': 0},
                      f'req_{MARKER}_absorbed')
        broke.state = 'failed'; broke.error = 'Provider returned an unusable document.'
        broke.started_at = timezone.now() - timedelta(hours=2)
        broke.finished_at = timezone.now() - timedelta(hours=2)
        broke.save(update_fields=['state', 'error', 'started_at', 'finished_at'])
        absorb_failed_job(broke, actor=None, note=f'{MARKER}: output not adopted')
        made.append('platform failure absorbed and the charge reversed')

        # 4 — an uncertain outcome held for the administrator, with the customer's funds still on
        #     hold. This is the row the dashboard's "Awaiting your decision" tile counts.
        held = job(doctor, 'generation', 'reconciliation')
        reserve(held, Decimal('0.50'))
        held.state = 'reconciliation'
        held.error = 'Worker stopped with an unknown provider outcome. Automatic retry is disabled.'
        held.started_at = timezone.now() - timedelta(hours=6)
        held.save(update_fields=['state', 'error', 'started_at'])
        made.append('job held for reconciliation with funds still reserved')

        # 5 — a job that has been `running` past the staleness bound. The worker's own reaper would
        #     already have moved it, so its presence is how the console infers no worker has run.
        stuck = job(employee, 'transcription', 'stuck')
        reserve(stuck, Decimal('0.20'))
        stuck.state = 'running'; stuck.started_at = timezone.now() - timedelta(hours=3)
        stuck.save(update_fields=['state', 'started_at'])
        made.append('job running past the staleness bound')

        # 6 — a plain failure that never reached the provider: held funds released, nothing charged.
        nothing = job(ultrasound, 'generation', 'released')
        reserve(nothing, Decimal('0.15'))
        release(nothing)
        nothing.state = 'failed'; nothing.error = 'Insufficient documented findings for any answer.'
        nothing.started_at = timezone.now() - timedelta(days=1)
        nothing.finished_at = timezone.now() - timedelta(days=1)
        nothing.save(update_fields=['state', 'error', 'started_at', 'finished_at'])
        made.append('failed job with funds released and nothing charged')

        # 7 — provider evidence arrives and is BELOW the configured estimate: the difference × 1.5
        #     is credited back to the wallets originally debited.
        from core.models import Usage
        usage = Usage.objects.get(job=settled)
        admin = User.objects.filter(is_staff=True).first()
        reconcile_usage(usage, Decimal('0.18'), f'{MARKER}-invoice-2026-09', admin,
                        evidence_kind='invoice', note='Monthly provider invoice, line 14')
        made.append('usage reconciled against an invoice, credit returned')

        # 8 — a real top-up through the webhook path, then a partial refund through the same path.
        wallet = Wallet.objects.get(user=doctor, kind='paid')
        payment = Payment.objects.create(user=doctor, wallet=wallet, amount_cents=2500,
                                         stripe_session=f'cs_test_{MARKER}', request_key=f'{MARKER}:payment')
        session = {'id': payment.stripe_session, 'payment_status': 'paid', 'currency': 'usd',
                   'amount_total': 2500, 'mode': 'payment', 'metadata': {'payment_id': str(payment.pk)},
                   'payment_intent': f'pi_test_{MARKER}'}
        body = json.dumps(session, sort_keys=True).encode()
        row = record_stripe_event(event('checkout.session.completed', session, 1), hashlib.sha256(body).hexdigest())
        process_stripe_event(row.pk)
        refund = {'id': f're_test_{MARKER}', 'payment_intent': f'pi_test_{MARKER}', 'amount': 500,
                  'currency': 'usd', 'status': 'succeeded'}
        row = record_stripe_event(event('refund.created', refund, 2),
                                  hashlib.sha256(json.dumps(refund, sort_keys=True).encode()).hexdigest())
        process_stripe_event(row.pk)
        made.append('$25.00 top-up and a $5.00 refund, both through the signed-event path')

        # 9 — a refund the ledger CANNOT take, because the funds are already reserved. The event is
        #     kept with status 'reconciliation'; no Refund row is written and no money moves. This
        #     is the state the console previously showed only as a generic error string.
        stranded = Payment.objects.create(user=ultrasound, wallet=Wallet.objects.get(user=ultrasound, kind='paid'),
                                          amount_cents=1000, stripe_session=f'cs_test_{MARKER}_stranded',
                                          request_key=f'{MARKER}:stranded')
        stranded_session = {'id': stranded.stripe_session, 'payment_status': 'paid', 'currency': 'usd',
                            'amount_total': 1000, 'mode': 'payment',
                            'metadata': {'payment_id': str(stranded.pk)},
                            'payment_intent': f'pi_test_{MARKER}_stranded'}
        row = record_stripe_event(event('checkout.session.completed', stranded_session, 3),
                                  hashlib.sha256(json.dumps(stranded_session, sort_keys=True).encode()).hexdigest())
        process_stripe_event(row.pk)
        spender = job(ultrasound, 'generation', 'spender')
        reserve(spender, Decimal('11.00'))  # holds the welcome credit and the whole top-up
        stranded_refund = {'id': f're_test_{MARKER}_stranded', 'payment_intent': f'pi_test_{MARKER}_stranded',
                           'amount': 1000, 'currency': 'usd', 'status': 'succeeded'}
        row = record_stripe_event(event('refund.created', stranded_refund, 4),
                                  hashlib.sha256(json.dumps(stranded_refund, sort_keys=True).encode()).hexdigest())
        process_stripe_event(row.pk)
        made.append('refund that the ledger could not take, held for reconciliation')

        # 10 — fixed overhead, an unverified account, a suspended account, an organization-paying
        #      department and an outstanding invitation: the non-money states the console must show.
        PlatformCost.objects.create(kind='fixed_overhead', amount=Decimal('149.00'),
                                    description=f'Hosting and licences ({MARKER})',
                                    period_start=timezone.localdate() - timedelta(days=30),
                                    period_end=timezone.localdate(), evidence_reference=f'{MARKER}-statement-09',
                                    recorded_by=admin)
        unverified = User.objects.create_user(username=f'pending{SYNTHETIC_DOMAIN}',
                                              email=f'pending{SYNTHETIC_DOMAIN}', password=token())
        suspended = User.objects.create_user(username=f'former{SYNTHETIC_DOMAIN}',
                                             email=f'former{SYNTHETIC_DOMAIN}', password=token(),
                                             verified_at=timezone.now(), is_active=False)
        ultrasound_department = Department.objects.exclude(pk=department.pk).order_by('name').first()
        if ultrasound_department:
            ultrasound_department.organization_pays = True
            ultrasound_department.save(update_fields=['organization_pays'])
            Wallet.objects.get_or_create(organization=ultrasound_department.organization, kind='paid')
        Invitation.objects.create(email=f'invited{SYNTHETIC_DOMAIN}', department=department, role='clinician',
                                  token_hash=digest(token()), expires_at=timezone.now() + timedelta(days=7),
                                  invited_by=doctor)
        made.append('fixed overhead, an unverified and a suspended account, an org-paying department, an open invitation')
        audit(admin, 'synthetic.console_demo_seeded', details={'marker': MARKER})

        self.stdout.write('Synthetic console demo data created:')
        for line in made:
            self.stdout.write(f'  · {line}')
        self.stdout.write(f'  unverified: {unverified.email} · suspended: {suspended.email}')


Command.requires_migrations_checks = True
