"""Administration-console computation: money overview, processing health, service status.

Three rules this module keeps, because the console is read as evidence:

1. **Every figure names its own definition.** A tile carries the exact expression that produced
   it, so a number on the overview can be reconciled against the section below it by hand.
2. **Nothing is invented.** Where the product has not decided an accounting policy (what counts
   as revenue when promotional credit funds the work), the components are shown separately and
   no aggregate is synthesised over them.
3. **An absent measurement is reported as absent, never as zero and never as healthy.** The
   whole point of an operations panel is the case where something is not running.

No clinical text is read here: the queries touch identity, money and state columns only.
"""
from datetime import datetime, time, timedelta, timezone as utc_offset
from decimal import Decimal

from django.db import models
from django.utils import timezone

from .models import (AuditEvent, CostReconciliation, Department, Job, LedgerEntry, Membership,
                     Organization, PlatformCost, Payment, Refund, Reservation, ServiceHealth,
                     Usage, User, Wallet)

ZERO = Decimal('0')

#: Jobs whose outcome nobody has established yet. Same set `audit_billing` calls `unresolved_jobs`.
UNRESOLVED_STATES = ['queued', 'running', 'reconciliation']

#: `core.jobs.mark_stale` flips a job that has been `running` longer than this to `reconciliation`.
#: It runs only inside the worker loop, so a job that has outlived it proves the reaper has not run.
STALENESS_BOUND = timedelta(minutes=5)

#: Charges for provider work. These are the kinds `absorb_failed_job` reverses and
#: `reconcile_usage` appends to, i.e. everything that moves a customer's money for a job.
WORK_KINDS = ['usage', 'reconciliation', 'absorbed']


def _sum(queryset, field='amount'):
    return queryset.aggregate(total=models.Sum(field))['total'] or ZERO


# --------------------------------------------------------------------------------------
# Date window
# --------------------------------------------------------------------------------------

def date_window(request):
    """Parse ?from=/?to= (inclusive calendar dates, UTC) into a filter and a legible label.

    Returns a dict with `start`, `end` (exclusive), `filters` (kwargs for `created_at`), the raw
    strings for re-rendering the form, and `problem` when a value could not be read. An
    unparseable date NARROWS nothing and says so: silently ignoring it would show an all-time
    total under a date heading, which is the failure this window exists to prevent.
    """
    # ⚠️ DO NOT TRUNCATE TO TEN CHARACTERS. `[:10]` turned '2026-09-2199' — or a machine-generated
    # '2026-09-21T00:00:00Z' — into a perfectly valid '2026-09-21', narrowing every figure on the
    # page to a window the operator never asked for, with no warning at all. An over-long value is
    # unreadable, and saying so is the whole point of the `problem` line. The cap is kept, well
    # above any legitimate date, purely to bound what reaches strptime. NULs are stripped because
    # PostgreSQL text cannot hold them and psycopg raises DataError out of the view as a 500.
    raw_from = (request.GET.get('from') or '').replace('\x00', '').strip()[:32]
    raw_to = (request.GET.get('to') or '').replace('\x00', '').strip()[:32]
    start = end = None
    problem = ''
    unreadable = False
    for raw, name in ((raw_from, 'from'), (raw_to, 'to')):
        if not raw:
            continue
        try:
            day = datetime.strptime(raw, '%Y-%m-%d').date()
        except ValueError:
            # ⚠️ DROP THE WHOLE WINDOW, not just the bad bound. Abandoning only the unreadable
            # side left the readable one in force: the page then narrowed every figure AND
            # displayed 'these figures cover every record' directly beneath a heading naming the
            # window it had just applied. A banner contradicting the numbers beside it is worse
            # than either behaviour alone.
            problem = 'Dates must be written YYYY-MM-DD. The window was ignored and these figures cover every record.'
            unreadable = True
            continue
        # `django.utils.timezone.utc` was removed in Django 5; the stdlib constant is the one.
        moment = datetime.combine(day, time.min, tzinfo=utc_offset.utc)
        if name == 'from':
            start = moment
        else:
            end = moment + timedelta(days=1)
    if unreadable:
        start = end = None
    if start and end and end <= start:
        problem = 'The end date is before the start date. The window was ignored and these figures cover every record.'
        start = end = None
    filters = {}
    if start:
        filters['created_at__gte'] = start
    if end:
        filters['created_at__lt'] = end
    if start and end:
        label = f'{raw_from} to {raw_to} (UTC, both days included)'
    elif start:
        label = f'{raw_from} onwards (UTC)'
    elif end:
        label = f'up to and including {raw_to} (UTC)'
    else:
        label = 'every record (no date window)'
    return {'start': start, 'end': end, 'filters': filters, 'from': raw_from, 'to': raw_to,
            'label': label, 'problem': problem, 'active': bool(filters)}


def window_filters(window, field='created_at'):
    """The window's predicate, expressed against the date column a given model actually has.

    ⚠️ NOT EVERY MODEL ON THIS PAGE HAS `created_at`. `User` extends `AbstractUser`, not `Entity`,
    so its creation timestamp is `date_joined`; filtering it on `created_at` raises FieldError and
    returns a 500 for any dated request. It was found by checking the assumption rather than by
    any test, because the tests exercised the window through `business_overview()` and through the
    audit view, and neither touches `User`.
    """
    return {field + key[len('created_at'):]: value for key, value in window['filters'].items()}


# --------------------------------------------------------------------------------------
# Business overview
# --------------------------------------------------------------------------------------

def business_overview(window):
    """Money the owner needs before reading any list, each figure with its own definition.

    Deliberately NOT computed: a single 'revenue' or 'margin' number. Work funded by a
    promotional credit debits a wallet without any cash ever arriving, so collapsing the two
    into one figure encodes an accounting policy this product has not chosen. The components
    are exact; the one subtraction shown states both of its terms.
    """
    period = window['filters']
    work = LedgerEntry.objects.filter(kind__in=WORK_KINDS, **period)
    charged_paid = -_sum(work.filter(wallet__kind='paid'))
    charged_promo = -_sum(work.filter(wallet__kind='promo'))
    usage = Usage.objects.filter(**period)
    provider_cost = _sum(usage, 'actual_cost')
    reconciled = CostReconciliation.objects.filter(**period)
    evidence_cost = _sum(reconciled, 'reconciled_cost')
    platform = PlatformCost.objects.filter(**period)
    platform_by_kind = {label: _sum(platform.filter(kind=kind)) for kind, label in PlatformCost.KINDS}
    payments_in = _sum(LedgerEntry.objects.filter(kind='payment', **period))
    refunded_out = -_sum(LedgerEntry.objects.filter(kind='refund', **period))
    granted = _sum(LedgerEntry.objects.filter(kind='welcome', **period))

    # Liability and unresolved work are STATE, not flow: a date window cannot bound them without
    # lying, so they are always as-of-now and the template says so.
    wallets = Wallet.objects.all()
    unreconciled = Usage.objects.filter(costreconciliation__isnull=True, simulated=False)
    pending = CostReconciliation.objects.filter(ledger_status='pending_funds')

    return {
        'window': window,
        'flow': [
            {'label': 'Charged — paid balances', 'amount': charged_paid,
             'definition': 'Net of every usage, reconciliation and absorption ledger movement on PAID wallets. This is money customers actually funded.'},
            {'label': 'Charged — promotional credit', 'amount': charged_promo,
             'definition': 'The same movements on PROMOTIONAL wallets. Real work, no cash: this is welcome credit being consumed.'},
            {'label': 'Provider cost (configured estimate)', 'amount': provider_cost,
             'definition': 'Sum of Usage.actual_cost — provider-returned units at the recorded rates. An estimate until reconciled against provider evidence.'},
            {'label': 'Provider cost (evidence-reconciled)', 'amount': evidence_cost,
             'definition': f'Sum of CostReconciliation.reconciled_cost over the {reconciled.count()} row(s) an administrator has reconciled against authenticated provider evidence. It covers only those rows, and is not comparable to the estimate above unless every row is reconciled.'},
            {'label': 'Carried by QuillMD', 'amount': sum(platform_by_kind.values(), ZERO),
             'definition': 'All platform costs: fixed overhead, absorbed platform failures, and charge above the approved customer limit. Never charged to a user.'},
            {'label': 'Paid in (Stripe)', 'amount': payments_in,
             'definition': "Sum of 'payment' ledger entries — explicit one-time top-ups that settled."},
            {'label': 'Refunded out', 'amount': refunded_out,
             'definition': "Sum of 'refund' ledger entries, as a positive number. Only refunds that reached the ledger."},
            {'label': 'Promotional credit granted', 'amount': granted,
             # A historical sum: each entry keeps the amount it was granted at. No per-account figure from
             # today's QUILLMD_WELCOME_CREDIT, which would contradict the entries it sums once changed.
             'definition': "Sum of the recorded 'welcome' ledger entries, each at the amount granted when it was recorded "
                           "(a later change to QUILLMD_WELCOME_CREDIT does not restate them). A liability, not a cost."},
        ],
        'difference': {
            'label': 'Charged (all balances) less provider cost',
            'amount': charged_paid + charged_promo - provider_cost,
            'definition': ('(charged to paid + charged to promotional) − provider cost at configured rates. '
                           'Stated as a subtraction of two named figures, not as profit: it counts promotional '
                           'credit as though it were cash, and it excludes the costs carried by QuillMD above.'),
        },
        # `platform_by_kind` is deliberately NOT returned. The page renders the platform-cost
        # totals UNWINDOWED (views.py builds them from all records, classified with the balances
        # rather than the flow figures), and handing the template a second, windowed copy of the
        # same money is how the next reader picks the wrong one.
        'position': [
            {'label': 'Unspent promotional credit', 'amount': _sum(wallets.filter(kind='promo'), 'balance'),
             'definition': 'Outstanding promotional liability across every wallet, as of now.'},
            {'label': 'Unspent paid balance', 'amount': _sum(wallets.filter(kind='paid'), 'balance'),
             'definition': 'Customer money held and not yet spent, across every wallet, as of now.'},
            {'label': 'Reserved against open requests', 'amount': _sum(wallets, 'reserved'),
             'definition': 'Funds held for requests that have not settled. A figure that does not fall is a stuck queue.'},
        ],
        'attention': [
            {'label': 'Usage awaiting provider evidence', 'count': unreconciled.count(),
             'amount': _sum(unreconciled, 'actual_cost'),
             'definition': 'Non-simulated usage with no CostReconciliation row. The charge stands on configured rates alone.'},
            {'label': 'Charges waiting for funds', 'count': pending.count(),
             'amount': _sum(pending, 'charge_delta'),
             'definition': "Reconciliations held at 'pending_funds': the evidence raised the charge and the payer's paid balance could not cover it."},
            {'label': 'Jobs with no established outcome', 'count': Job.objects.filter(state__in=UNRESOLVED_STATES).count(),
             'amount': None,
             'definition': "Jobs queued, running or held for reconciliation. The same set the billing audit calls unresolved."},
        ],
        'counts': {
            'accounts_total': User.objects.count(),
            'accounts_clinical': User.objects.filter(is_staff=False).count(),
            'accounts_suspended': User.objects.filter(is_active=False).count(),
            'accounts_unverified': User.objects.filter(verified_at__isnull=True).count(),
            'administrators': User.objects.filter(is_staff=True).count(),
            'organizations': Organization.objects.count(),
            'departments': Department.objects.count(),
            'memberships_active': Membership.objects.filter(active=True).count(),
        },
    }


# --------------------------------------------------------------------------------------
# Processing health
# --------------------------------------------------------------------------------------

def processing_health(at=None):
    """What the application can observe about its own queue, and nothing it cannot.

    The web process cannot see whether the worker process exists. What it CAN see is an
    inference with a proof behind it: `core.jobs.mark_stale` moves any job running longer than
    STALENESS_BOUND to `reconciliation`, and it runs on every pass of the worker loop. A job
    still `running` beyond that bound therefore establishes that the reaper has not run — which
    is the fact the owner needs, stated as what it is rather than as 'the worker is down'.
    """
    at = at or timezone.now()
    cutoff = at - STALENESS_BOUND
    queued = Job.objects.filter(state='queued')
    running = Job.objects.filter(state='running')
    overdue = running.filter(started_at__lt=cutoff)
    oldest_queued = queued.order_by('created_at').first()
    oldest_running = running.exclude(started_at=None).order_by('started_at').first()
    last_finished = Job.objects.exclude(finished_at=None).order_by('-finished_at').first()
    held = _sum(Reservation.objects.filter(state='held', job__state__in=UNRESOLVED_STATES))

    reaper_overdue = overdue.exists()
    # The predicate must assert what its message claims. Without `not running.exists()` the
    # panel printed 'nothing is running. Nothing is picking work up.' while the balance strip
    # beside it showed Running = 1 — a healthy worker part-way through a long transcription.
    queue_stalled = bool(oldest_queued and oldest_queued.created_at < cutoff and not running.exists())
    if reaper_overdue:
        verdict, severity = 'No worker has run recently', 'error'
        detail = (f'{overdue.count()} job(s) have been running longer than {int(STALENESS_BOUND.total_seconds() / 60)} minutes. '
                  'The staleness reaper runs on every worker pass and would already have moved them to reconciliation, '
                  'so it has not run. Customer funds stay reserved until it does.')
    elif queue_stalled:
        verdict, severity = 'Queue is not draining', 'error'
        detail = (f'The oldest queued job has waited longer than {int(STALENESS_BOUND.total_seconds() / 60)} minutes and nothing is running. '
                  'Nothing is picking work up.')
    elif queued.exists() or running.exists():
        verdict, severity = 'Work in progress', 'success'
        detail = f'{queued.count()} queued, {running.count()} running, all within the staleness bound.'
    else:
        verdict, severity = 'Queue empty', 'success'
        detail = ('Nothing queued or running. An empty queue is not evidence that a worker exists — it is evidence '
                  'that nothing is waiting. The reaper inference can only speak when there is work.')

    return {
        'verdict': verdict, 'severity': severity, 'detail': detail,
        'observed_at': at,
        'staleness_minutes': int(STALENESS_BOUND.total_seconds() / 60),
        'queued': queued.count(),
        'running': running.count(),
        'overdue': overdue.count(),
        'awaiting_owner': Job.objects.filter(state='reconciliation').count(),
        'oldest_queued_at': oldest_queued.created_at if oldest_queued else None,
        'oldest_running_since': oldest_running.started_at if oldest_running else None,
        'last_finished_at': last_finished.finished_at if last_finished else None,
        'funds_held_on_open_jobs': held,
    }


# --------------------------------------------------------------------------------------
# Service status: configuration (in-process) and published operations state
# --------------------------------------------------------------------------------------

def shape(value, recogniser=None):
    """'absent', 'present' or a recogniser's verdict. Never the value, never its length.

    Lifted verbatim from `core.management.commands.configuration_status` so the browser screen
    and the terminal screen cannot drift into disagreeing about the same secret.
    """
    if not isinstance(value, str) or not value.strip():
        return 'absent'
    if recogniser is None:
        return 'present'
    return 'present, recognised shape' if recogniser(value) else 'present, UNRECOGNISED shape'


def configuration_rows():
    """Everything `manage.py configuration_status` prints, as data. Values are never returned."""
    import os
    import shutil
    from django.conf import settings
    from .billing import stripe_key_configured

    settings_rows = [
        ('QUILLMD_AI_MODE', settings.AI_MODE),
        ('QUILLMD_AI_PROVIDER', settings.AI_PROVIDER),
        ('QUILLMD_EMAIL_MODE', settings.QUILLMD_EMAIL_MODE),
        ('QUILLMD_EMAIL_FROM', settings.QUILLMD_EMAIL_FROM),
        ('QUILLMD_EMAIL_VERIFIED_DOMAIN', settings.QUILLMD_EMAIL_VERIFIED_DOMAIN),
        ('CPT_LICENSE_ID', settings.CPT_LICENSE_ID),
        ('CPT_LICENSE_EXPIRY', settings.CPT_LICENSE_EXPIRY),
    ]
    secret_rows = [
        ('DEEPGRAM_API_KEY', os.getenv('DEEPGRAM_API_KEY'), None),
        ('ANTHROPIC_API_KEY', os.getenv('ANTHROPIC_API_KEY'), None),
        ('RESEND_API_KEY', settings.RESEND_API_KEY, None),
        ('STRIPE_SECRET_KEY', settings.STRIPE_SECRET_KEY, stripe_key_configured),
        ('STRIPE_WEBHOOK_SECRET', settings.STRIPE_WEBHOOK_SECRET, None),
    ]
    probe, remuxer = shutil.which('ffprobe'), shutil.which('ffmpeg')
    missing = ('NOT INSTALLED — every recording is refused before the provider; nothing is charged')
    return {
        'settings': [{'name': name, 'value': value if isinstance(value, str) and value.strip() else '(unset)'}
                     for name, value in settings_rows],
        'secrets': [{'name': name, 'status': shape(value, recogniser),
                     'severity': 'success' if shape(value, recogniser) == 'present' or shape(value, recogniser).endswith('recognised shape') else
                                 'warning' if shape(value, recogniser) == 'absent' else 'error'}
                    for name, value, recogniser in secret_rows],
        'media_tools': [
            {'name': 'ffprobe', 'status': probe or missing, 'severity': 'success' if probe else 'error'},
            {'name': 'ffmpeg', 'status': remuxer or missing, 'severity': 'success' if remuxer else 'error'},
        ],
        'gates': [
            {'name': 'SYNTHETIC_ONLY', 'value': str(settings.SYNTHETIC_ONLY)},
            {'name': 'STRIPE_LIVE_ENABLED', 'value': str(settings.STRIPE_LIVE_ENABLED)},
            {'name': 'QUILLMD_DATA_MODE', 'value': settings.QUILLMD_DATA_MODE},
            {'name': 'QUILLMD_REGISTRATION', 'value': settings.QUILLMD_REGISTRATION},
            {'name': 'QUILLMD_STRIPE_MODE', 'value': settings.QUILLMD_STRIPE_MODE},
            {'name': 'QUILLMD_MFA_REQUIRED_ALL', 'value': str(settings.QUILLMD_MFA_REQUIRED_ALL)},
            {'name': 'QUILLMD_TRUST_PROXY (effective on this surface)', 'value': str(settings.QUILLMD_TRUST_PROXY)},
            {'name': 'ADMIN_SITE', 'value': str(settings.ADMIN_SITE)},
            {'name': 'Database', 'value': settings.DATABASES['default']['NAME']},
            {'name': 'Release', 'value': settings.RELEASE_SHA},
        ],
    }


def email_delivery(window=None, at=None):
    """Delivery outcome from the rows the sender already writes. No new writer, no recipients.

    `core.email_delivery` audits every send as 'email.outbox' / 'email.accepted' / 'email.failed'.
    A failure is findable today only by guessing that exact string in a free-text box.
    """
    at = at or timezone.now()
    events = AuditEvent.objects.filter(action__startswith='email.')
    if window and window['filters']:
        events = events.filter(**window['filters'])
    recent = AuditEvent.objects.filter(action='email.failed', created_at__gte=at - timedelta(days=1))
    counts = {row['action']: row['n'] for row in events.values('action').annotate(n=models.Count('pk'))}
    failed_day = recent.count()
    last_failure = recent.order_by('-created_at').first()
    delivered = counts.get('email.accepted', 0) + counts.get('email.outbox', 0)
    failed_window = counts.get('email.failed', 0)
    if failed_day:
        severity, status = 'error', f'{failed_day} delivery failure(s) in the last 24 hours'
    elif failed_window and not delivered:
        # ⚠️ NOT 'no delivery recorded'. Sends WERE recorded and every one of them failed. The old
        # else-branch caught this whenever the failures were older than the 24-hour probe, and
        # printed an amber 'No delivery recorded in this window' directly above a detail line
        # reading 'failed 5'. An absent measurement and a uniformly failing one are opposite
        # findings and must never share a sentence.
        severity, status = 'error', f'Every recorded send in this window failed ({failed_window})'
    elif failed_window:
        severity, status = 'warning', f'{delivered} delivered, {failed_window} failed in this window'
    elif delivered:
        severity, status = 'success', ('Accepted by the provider' if counts.get('email.accepted')
                                       else 'Written to the private outbox')
    else:
        severity, status = 'warning', 'No delivery recorded in this window'
    return {'name': 'Account email delivery', 'status': status, 'severity': severity,
            'detail': ('Counted from the audit rows every send already writes: '
                       f"outbox {counts.get('email.outbox', 0)}, accepted {counts.get('email.accepted', 0)}, "
                       f"failed {counts.get('email.failed', 0)}."),
            'last_failure_at': last_failure.created_at if last_failure else None,
            'counts': counts}


#: Twelve five-minute cadences is one hour: past any ordinary miss, restart or maintenance pause.
FAILED_PUBLICATION_CADENCES = 12


def published_operations(keys=ServiceHealth.KEYS, at=None):
    """Read what the privileged side PUBLISHED. Never guess, never report absence as health.

    The web process cannot compute backup state and must not pretend to. The admin unit runs as
    `quillmd-app` and carries `InaccessiblePaths=/opt/meddoc-pro/rebuild/.runtime`, so every
    backup state file is masked from its mount namespace outright — a view that reads that path
    would return 'unavailable' on a perfectly healthy host, which is a false red that gets read
    as a false green the first time somebody decides the panel is unreliable.

    So the privileged side publishes into the database (`manage.py publish_operations_status`,
    run as the identity that owns the state) and this reads the row. Three distinct outcomes,
    never collapsed: never published, published but stale, published and fresh.
    """
    at = at or timezone.now()
    rows = {row.key: row for row in ServiceHealth.objects.filter(key__in=list(keys))}
    result = []
    for key, label in ServiceHealth.KEYS.items():
        if key not in keys:
            continue
        row = rows.get(key)
        if row is None:
            result.append({'key': key, 'name': label, 'severity': 'warning', 'published': False,
                           'status': 'Never published',
                           'detail': ('No privileged process has published this status. That is not a report of health: '
                                      'it means the publisher has not run here. Install the publisher, or treat this as unknown.'),
                           'computed_at': None, 'age_seconds': None, 'stale': None, 'failed': None,
                           'payload': {}})
            continue
        age = (at - row.computed_at).total_seconds()
        stale = age > row.expected_interval_seconds * 2 or age < 0
        #: ⚠️ A MISSED TICK AND A DEAD PUBLISHER ARE DIFFERENT FACTS AND USED TO RENDER ALIKE.
        #: Staleness was capped at 'warning' however old the row was, so the 2026-09-22 outage —
        #: the publisher raising EROFS on every tick for six and a half hours, seventy-seven
        #: cadences — presented with the same badge as one late publication. The age was in the
        #: text, but a badge that cannot escalate is one people stop reading.
        #:
        #: FAILED is deliberately far past STALE rather than just after it: at twelve cadences
        #: (an hour, at the five-minute cadence) no ordinary miss, restart or brief maintenance
        #: pause can reach it, so the escalation means the publisher is not running rather than
        #: that a tick slipped. Negative ages are clock movement, not evidence of a dead
        #: publisher, so they stay STALE.
        failed = age > row.expected_interval_seconds * FAILED_PUBLICATION_CADENCES
        result.append({
            'key': key, 'name': label, 'published': True,
            'severity': 'failure' if failed else 'warning' if stale else row.severity,
            'status': (f'No publication for {int(age // 60)} min — FAILED, past {FAILED_PUBLICATION_CADENCES}x its '
                       f'{row.expected_interval_seconds // 60}-minute cadence; the publisher is not running'
                       if failed else
                       f'Last published {int(age // 60)} min ago — STALE, older than twice its {row.expected_interval_seconds // 60}-minute cadence'
                       if stale else row.condition),
            'detail': row.action if not stale else (row.action + (
                ' · This is not a late reading: at this age the publisher itself has stopped. '
                'Inspect the unit and its journal, not the state it last described.'
                if failed else ' · This reading is old; it describes the state at the time shown, not now.')),
            'computed_at': row.computed_at, 'age_seconds': int(age), 'stale': stale, 'failed': failed,
            'payload': row.payload if isinstance(row.payload, dict) else {},
        })
    return result


# --------------------------------------------------------------------------------------
# Who may change who pays
# --------------------------------------------------------------------------------------

def may_change_payer(user):
    """Whether this account may change `Department.organization_pays`. Today: nobody.

    ⚠️ THE SETTING IS READ-ONLY BECAUSE THE ROLE MODEL CANNOT EXPRESS THE BOUNDARY, not because
    the implementation is missing. The operating instruction is that changing who is billed
    belongs to an explicitly authorized highest-privilege platform owner / billing role, and that
    an ordinary organization or department administrator must never be able to do it silently.

    Measured, not assumed: `is_superuser` is referenced in exactly one place in this codebase — a
    template branch that renders the same word as `is_staff` — so it confers nothing, and
    production carries **1 staff account and 0 superusers**. Granting the capability to `is_staff`
    would hand it to precisely the population the instruction excludes. Inventing a new role here
    would be inventing an authorization boundary nobody ratified.

    So the capability requires BOTH an explicit deployment grant and the highest flag that exists.
    Both are false today, the control is read-only for everyone, and the refusal is enforced on
    the SERVER rather than by hiding the form. The implementation and its invariant tests are
    retained behind this gate so that enabling the role later is a configuration change, not a
    rewrite.
    """
    from django.conf import settings
    return bool(getattr(settings, 'QUILLMD_PAYER_ROLE_GRANTED', False)
                and getattr(user, 'is_superuser', False)
                and getattr(user, 'is_staff', False))


def payer_restriction_note():
    """What the screen says instead of offering the control. Honest about the existing path."""
    return ('Who pays is shown here but cannot be changed from this console. Changing which '
            'balance is billed is reserved for an explicitly authorized platform owner or '
            'billing role, and this deployment has not established one — no account holds it. '
            'The supported path today is to create the department with the intended payer, or '
            'to have the deployment grant that role before using this control. The setting is '
            'displayed on every department so the current answer is never in doubt.')


# --------------------------------------------------------------------------------------
# Per-account detail
# --------------------------------------------------------------------------------------

def account_detail(user):
    """Everything about one account in one place, money included, clinical content excluded."""
    from django_otp.plugins.otp_totp.models import TOTPDevice
    memberships = (Membership.objects.filter(user=user)
                   .select_related('department__organization').order_by('department__organization__name', 'department__name'))
    organizations = {m.department.organization_id for m in memberships if m.active}
    wallets = list(Wallet.objects.filter(models.Q(user=user) | models.Q(organization_id__in=organizations))
                   .select_related('user', 'organization').order_by('kind', 'pk'))
    usage = Usage.objects.filter(user=user)
    return {
        'account': user,
        'verified': bool(user.verified_at),
        'mfa_devices': list(TOTPDevice.objects.filter(user=user).order_by('name')),
        'memberships': list(memberships),
        'wallets': wallets,
        'wallet_totals': {
            'promo': _sum(Wallet.objects.filter(user=user, kind='promo'), 'balance'),
            'paid': _sum(Wallet.objects.filter(user=user, kind='paid'), 'balance'),
            'reserved': _sum(Wallet.objects.filter(user=user), 'reserved'),
        },
        'charged_total': -_sum(LedgerEntry.objects.filter(wallet__user=user, kind__in=WORK_KINDS)),
        'usage_count': usage.count(),
        'usage_cost': _sum(usage, 'actual_cost'),
        'usage_charged': _sum(usage, 'charged_cost'),
        'payments': list(Payment.objects.filter(user=user).select_related('wallet__organization').order_by('-created_at', 'pk')[:20]),
        'refunds': list(Refund.objects.filter(payment__user=user).select_related('payment').order_by('-created_at', 'pk')[:20]),
        'jobs_unresolved': Job.objects.filter(user=user, state__in=UNRESOLVED_STATES).count(),
        'jobs_total': Job.objects.filter(user=user).count(),
    }


def refunded_cents(payment_ids):
    """Succeeded refund total per payment, so a refunded payment cannot keep reading as 'paid'."""
    rows = (Refund.objects.filter(payment_id__in=list(payment_ids), status='succeeded')
            .values('payment_id').annotate(total=models.Sum('amount_cents')))
    return {row['payment_id']: row['total'] for row in rows}


# --------------------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------------------

EXPORT_COLUMNS = ['recorded_at', 'usage_id', 'job_id', 'user_email', 'organization', 'department',
                  'payer', 'provider', 'provider_request_id', 'provider_resource_id', 'simulated',
                  'configured_cost', 'charged_cost', 'reconciled_cost', 'evidence_kind',
                  'evidence_reference', 'ledger_status', 'charge_delta', 'absorbed_reversal']


def export_rows(queryset):
    """One row per usage record, identifiers and money only — the columns an accountant asks for.

    `charged_cost` is the charge AT SETTLEMENT, before any later movement; `charge_delta` is a
    reconciliation against provider evidence; `absorbed_reversal` is a charge QuillMD reversed in
    full as a platform failure. The three together are the same set the console sums
    (`WORK_KINDS`), so net charge = charged_cost + charge_delta − absorbed_reversal, and the file
    reconciles to the screen without it.

    ⚠️ The reversal column exists because leaving it out was not neutral. A usage row whose whole
    charge had been reversed exported as `charged_cost 0.1845` with every reconciliation column
    blank — indistinguishable from a charge that stands. An accountant reading the file alone
    would have billed it.

    Generated lazily, with the reversal as one subquery rather than a per-row query, so a large
    export still streams.
    """
    reversal = (LedgerEntry.objects.filter(kind='absorbed', job_id=models.OuterRef('job_id'))
                .values('job_id').annotate(total=models.Sum('amount')).values('total')[:1])
    yield EXPORT_COLUMNS
    for item in (queryset.select_related('user', 'department', 'organization', 'costreconciliation')
                 .annotate(absorbed_reversal=models.Subquery(reversal)).iterator()):
        row = item.reconciliation
        yield [
            item.created_at.strftime('%Y-%m-%dT%H:%M:%SZ'),
            str(item.pk), str(item.job_id), item.user.email,
            item.organization.name, item.department.name, item.payer,
            item.provider, item.provider_request_id, item.provider_resource_id,
            'yes' if item.simulated else 'no',
            format(item.actual_cost, 'f'), format(item.charged_cost, 'f'),
            format(row.reconciled_cost, 'f') if row else '',
            row.evidence_kind if row else '',
            row.evidence_reference if row else '',
            row.ledger_status if row else '',
            format(row.charge_delta, 'f') if row else '',
            format(item.absorbed_reversal, 'f') if item.absorbed_reversal else '',
        ]
