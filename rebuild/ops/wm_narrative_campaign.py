#!/usr/bin/env python3
"""The WM narrative live campaign runner (docs/rebuild/wm-narrative-design.md, *Live verification*).

It runs the frozen candidate's own product path in ONE process against a synthetic database of its own: the blank
qualified form uploaded through the page, one synthetic clinician, one synthetic wallet funded with the stage's wallet
limit and nothing else, and one encounter per attempt from the frozen benchmark. Per attempt: the page's own quote is
read (its model, pricing version and maximum charge), the doctor's Generate request holds it, the worker's own
`run_one` makes the ONE provider request, settlement and the validator run as in production, and the page is rendered.

EVERY ATTEMPT IS WRITTEN DOWN BEFORE IT CAN COST ANYTHING. An O_EXCL attempt record is written and synced before the
hold and the request; an O_EXCL outcome record after. An attempt with no outcome (a crash, a kill) is an UNKNOWN
provider outcome: it is recorded as such on the next start, counted at its maximum, and never forgotten or retried
as if it cost nothing.

TWO MONEY LIMITS, ENFORCED SEPARATELY, BECAUSE ONE DOES NOT BOUND THE OTHER:

  provider  What the provider may bill QuillMD. A response the validator cannot use is settled and then ABSORBED (the
            customer's charge is reversed; the provider was still paid), a timeout leaves the outcome unknown with the
            hold kept, and cost above a hold is absorbed. None of that is visible in the wallet, so the wallet cannot
            bound it. The runner bounds it: before each attempt, the worst case of every attempt so far (the settled
            cost where a receipt exists, the attempt's maximum where it does not) plus this attempt's maximum, each
            x 1.1 for a US-inference multiplier this key's configuration cannot be checked for, must fit the stage's
            and the campaign's provider limit.
  wallet    What the synthetic customer is charged: 1.5 x cost, never above the hold. The product bounds it (the wallet
            is funded to the stage limit and the product refuses any hold it cannot cover); the runner checks it too.

The provider key never passes through this file's output. Offline, the provider is a loopback mock and the key a fixed
non-secret marker. Live, the key and the price fields are taken from the protected application configuration by the
allowlist reader below (ops/backup_alerts.py's pattern) ONLY with a committed declaration naming the authorization, and
the runner refuses to start if any evidence file it wrote contains the key.

Commands (run from the candidate checkout's rebuild/):
  plan      --mode offline|live --stage N              per-case maxima and limits; no database, no request
  run       --mode offline|live --stage N --campaign-dir DIR --db DB.json --engine DIR [--provider P.json]
            [--declaration FILE]                       the stage
Exit status: 0 PASS, 3 FAIL (a wrong answer or statement), 4 STOPPED (a stop condition), 5 INCOMPLETE, 2 refused.
"""
import argparse
import hashlib
import io
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import time
from decimal import Decimal, ROUND_UP
from pathlib import Path

RUNNER = Path(__file__).resolve()
REBUILD = RUNNER.parents[1]
CAMPAIGN = 'wm-narrative-v1-live-202609'
EXPECTED_MODEL = 'claude-sonnet-4-6'
#: The application's own current pricing version (recorded by its jobs on 2026-09-21 and 2026-09-22, and recomputed from
#: those records' non-secret fields: anthropic, claude-sonnet-4-6, $3 / $15 / $0.30 per MTok, discount 0, Deepgram
#: $0.0043 per minute). Any other version stops the campaign before a request.
EXPECTED_PRICING_VERSION = 'configured-v1:fcc802676fc66faa1dca2e574588ab96d9ee90cba679f047d6a80bb7924583ae'
#: US-only inference costs 1.1 x on Claude 4.6+ (Anthropic pricing, verified 2026-09-26); this key's workspace default
#: cannot be read without an Admin credential, so every provider bound assumes it.
GEO_MARGIN = Decimal('1.1')
MULTIPLIER = Decimal('1.5')
CENT = Decimal('0.000001')

STAGE_1 = ('C14', 'C18', 'C19', 'H05', 'H12')
STAGE_2 = ('C01', 'C02', 'C03', 'C04', 'C05', 'C06', 'C07', 'C08', 'C09', 'C10', 'C11', 'C12', 'C13', 'C15',
           'H01', 'H02', 'H03', 'H04', 'H06', 'H07', 'H08', 'H09', 'H10', 'H11')
STAGES = {
    1: {'cases': STAGE_1, 'max_attempts': 7, 'max_retries': 2,
        'provider_limit': Decimal('2.40'), 'wallet_limit': Decimal('3.50')},
    2: {'cases': STAGE_2, 'max_attempts': 28, 'max_retries': 4,
        'provider_limit': Decimal('9.60'), 'wallet_limit': Decimal('13.00')},
}
CAMPAIGN_PROVIDER_LIMIT = Decimal('12.00')
CAMPAIGN_WALLET_LIMIT = Decimal('16.50')
RETRY_WAIT_SECONDS = 60

#: A provider failure worth ONE bounded retry: the request may not have been processed. Never an answer's quality.
TRANSPORT = {'APITimeoutError', 'APIConnectionError', 'RateLimitError', 'InternalServerError', 'OverloadedError',
             'ServiceUnavailableError', 'DeadlineExceededError'}
#: A failure that says the configuration is wrong: retrying spends money on the same refusal.
CONFIGURATION = {'AuthenticationError', 'PermissionDeniedError', 'NotFoundError', 'BadRequestError',
                 'RequestTooLargeError', 'UnprocessableEntityError', 'ConflictError'}

#: The protected application configuration, and the ONLY fields read from it (ops/backup_alerts.py's pattern).
PROTECTED_CONFIGURATION = Path('/opt/meddoc-pro/rebuild/.env')
PROVIDER_FIELDS = ('ANTHROPIC_API_KEY', 'QUILLMD_AI_PROVIDER', 'QUILLMD_AI_MODEL', 'QUILLMD_AI_INPUT_RATE',
                   'QUILLMD_AI_OUTPUT_RATE', 'QUILLMD_AI_CACHED_RATE', 'QUILLMD_PROVIDER_DISCOUNT_RATE',
                   'QUILLMD_DEEPGRAM_RATE_PER_MINUTE', 'QUILLMD_DEEPGRAM_RATE_PER_SECOND')
OPTIONAL_PROVIDER_FIELDS = {'QUILLMD_PROVIDER_DISCOUNT_RATE', 'QUILLMD_DEEPGRAM_RATE_PER_SECOND',
                            'QUILLMD_DEEPGRAM_RATE_PER_MINUTE'}
OFFLINE_KEY = 'offline-mock-provider-no-credential'
KEY_SHAPE = re.compile(r'sk-ant-[A-Za-z0-9_\-]{8,}')

EXIT = {'PASS': 0, 'FAIL': 3, 'STOPPED': 4, 'INCOMPLETE': 5}


class Refused(Exception):
    """The runner will not start, or will not make the next attempt. Nothing further is sent."""


def require(condition, message):
    if not condition:
        raise Refused(message)


def money(value):
    return format(Decimal(value).quantize(CENT, rounding=ROUND_UP), 'f')


# ── private files ────────────────────────────────────────────────────────────────────────────────────────────────

def write_new(path, document):
    """O_EXCL + fsync: a record is written once and never rewritten."""
    path = Path(path)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(document, indent=2, sort_keys=True, default=str) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def private_directory(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    require(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode), f'{path} is not a real directory.')
    require(info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700, f'{path} must be 0700 and ours.')
    return path


def read_private(path, limit=65536):
    """A regular, unlinked-elsewhere, owner-only file of bounded size, opened without following a link."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) & 0o077 == 0 and info.st_size <= limit,
                f'{path} is not a private file of at most {limit} bytes.')
        return os.read(fd, limit + 1)
    finally:
        os.close(fd)


def provider_fields_from(path):
    """ONLY the allowlisted provider fields of a protected configuration; never printed, never returned whole."""
    from dotenv import dotenv_values
    parsed = dotenv_values(stream=io.StringIO(read_private(path).decode('utf-8')), interpolate=False)
    values = {name: (parsed.get(name) or '') for name in PROVIDER_FIELDS}
    missing = [name for name, value in values.items() if not value and name not in OPTIONAL_PROVIDER_FIELDS]
    require(not missing, 'The protected configuration lacks: ' + ', '.join(missing) + '.')
    return values


# ── ledger arithmetic (no Django; unit-tested) ───────────────────────────────────────────────────────────────────

def attempt_bound(maximum_cost):
    """The most the provider can bill for one attempt: the app's own maximum x the US-inference margin."""
    return (Decimal(maximum_cost) * GEO_MARGIN).quantize(CENT, rounding=ROUND_UP)


def exposure(attempt, outcome):
    """What one attempt may have cost at the provider, worst case. Only a product-proven 'not sent' is zero."""
    if outcome is None:
        return attempt_bound(attempt['maximum_cost'])
    if outcome['class'] == 'not_sent':
        return Decimal('0')
    if outcome.get('provider_actual_cost') not in (None, ''):
        return max(attempt_bound(outcome['provider_actual_cost']), Decimal('0'))
    return attempt_bound(attempt['maximum_cost'])


def load_ledger(ledger):
    """[(attempt, outcome or None)] in attempt order, from the O_EXCL records."""
    rows = []
    for path in sorted(Path(ledger).glob('*-attempt.json')):
        outcome_path = path.with_name(path.name.replace('-attempt.json', '-outcome.json'))
        rows.append((read_json(path), read_json(outcome_path) if outcome_path.exists() else None))
    numbers = [attempt['number'] for attempt, _ in rows]
    require(numbers == list(range(1, len(numbers) + 1)), f'The ledger is not a gapless sequence: {numbers}.')
    return rows


def totals(rows, stage=None):
    selected = [(a, o) for a, o in rows if stage is None or a['stage'] == stage]
    return {
        'attempts': len(selected),
        'provider_exposure': sum((exposure(a, o) for a, o in selected), Decimal('0')),
        'wallet_charged': sum((Decimal(o.get('wallet_charged') or '0') for _, o in selected if o), Decimal('0')),
        'unknown': sum(1 for _, o in selected if o is None or o['class'] in ('unknown', 'interrupted_unknown')),
        'retries': sum(1 for a, _ in selected if a['kind'] == 'retry'),
    }


def next_attempt_allowed(rows, stage, maximum_cost):
    """Refuses (with the reason) any attempt that could take the stage or the campaign past a limit."""
    plan = STAGES[stage]
    here, everything = totals(rows, stage), totals(rows)
    bound = attempt_bound(maximum_cost)
    require(here['attempts'] < plan['max_attempts'],
            f'Stage {stage} has used all {plan["max_attempts"]} attempts.')
    require(here['provider_exposure'] + bound <= plan['provider_limit'],
            f'Stage {stage} provider limit: {money(here["provider_exposure"])} already exposed + {money(bound)} '
            f'would exceed ${plan["provider_limit"]}.')
    require(everything['provider_exposure'] + bound <= CAMPAIGN_PROVIDER_LIMIT,
            f'Campaign provider limit: {money(everything["provider_exposure"])} + {money(bound)} would exceed '
            f'${CAMPAIGN_PROVIDER_LIMIT}.')
    hold = (Decimal(maximum_cost) * MULTIPLIER)
    require(here['wallet_charged'] + hold <= plan['wallet_limit'] + Decimal('0.000000000001'),
            f'Stage {stage} wallet limit: {money(here["wallet_charged"])} charged + {money(hold)} held would exceed '
            f'${plan["wallet_limit"]}.')
    require(everything['wallet_charged'] + hold <= CAMPAIGN_WALLET_LIMIT,
            f'Campaign wallet limit would be exceeded.')
    return bound


def classify(state, error_class, has_receipt, billing):
    """One attempt's outcome class from the product's own job record."""
    if state == 'succeeded':
        return 'adopted'
    if billing == 'not_processed' and not has_receipt:
        return 'not_sent'
    if has_receipt:
        return 'output_unusable' if state == 'failed' else 'settlement_reconciliation'
    if error_class in TRANSPORT:
        return 'transport_failure'
    if error_class in CONFIGURATION:
        return 'configuration_failure'
    return 'unknown'


def stage_worst_case(maxima, stage):
    """The stage's limits must hold even if every allowed attempt costs the largest case's maximum."""
    plan = STAGES[stage]
    worst = max(attempt_bound(m) for m in maxima.values())
    hold = max(Decimal(m) for m in maxima.values()) * MULTIPLIER
    return {'largest_attempt_bound': worst, 'provider_worst_case': worst * plan['max_attempts'],
            'wallet_worst_case': hold * plan['max_attempts'],
            'fits': worst * plan['max_attempts'] <= plan['provider_limit']
            and hold * plan['max_attempts'] <= plan['wallet_limit']}


# ── environment (the process that makes requests sees only this) ──────────────────────────────────────────────────

def scrubbed_environment(args, provider, campaign_dir):
    db = read_json(args.db)
    require(set(db) >= {'name', 'user', 'password', 'host', 'port'}, 'The database file is incomplete.')
    require(db['name'].startswith('quillmd_wmn_campaign'), 'The campaign database must be a quillmd_wmn_campaign* one.')
    require(db['host'] in ('127.0.0.1', 'localhost') or db['host'].startswith('/'), 'The database must be local.')
    engine = Path(args.engine)
    manifest = engine / 'runtime-manifest.json'
    env = {
        'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1',
        'HOME': str(campaign_dir / 'home'), 'TMPDIR': str(campaign_dir / 'tmp'),
        'DJANGO_SETTINGS_MODULE': 'quillmd.settings',
        'QUILLMD_SECRET_KEY': secrets.token_urlsafe(48),
        'QUILLMD_DB_NAME': db['name'], 'QUILLMD_DB_USER': db['user'], 'QUILLMD_DB_PASSWORD': db['password'],
        'QUILLMD_DB_HOST': db['host'], 'QUILLMD_DB_PORT': str(db['port']),
        'QUILLMD_STATE_DIR': str(campaign_dir / 'state'),
        'QUILLMD_AI_MODE': 'live', 'QUILLMD_WM_NARRATIVE': '1', 'QUILLMD_HTTPS': '0', 'QUILLMD_ADMIN_SITE': '0',
        'QUILLMD_EMAIL_MODE': 'file',
        'QUILLMD_WORD_RUNTIME': str(engine / 'runtime'), 'QUILLMD_WORD_MANIFEST': str(manifest),
        'QUILLMD_WORD_MANIFEST_SHA256': hashlib.sha256(manifest.read_bytes()).hexdigest(),
        'QUILLMD_WORD_QUALIFICATION': '1',
        'WMN_CAMPAIGN_MODE': args.mode,
    }
    env.update({name: value for name, value in provider.items() if value})
    if args.mode == 'offline':
        env['ANTHROPIC_BASE_URL'] = provider['ANTHROPIC_BASE_URL']
    return env


def offline_provider(path):
    value = read_json(path)
    require(value.get('ANTHROPIC_API_KEY') == OFFLINE_KEY, 'Offline mode uses the fixed offline marker, never a key.')
    require(re.fullmatch(r'http://127\.0\.0\.1:\d{2,5}', value.get('ANTHROPIC_BASE_URL', '')),
            'Offline mode needs a loopback mock provider.')
    return value


def declared(args):
    """Live mode: a committed, unmodified declaration that names this campaign, this stage and these limits."""
    require(args.declaration, 'Live mode requires --declaration (a committed declaration naming the authorization).')
    path = Path(args.declaration).resolve()
    tracked = subprocess.run(['git', '-C', str(path.parent), 'ls-files', '--error-unmatch', path.name],
                             capture_output=True).returncode == 0
    clean = subprocess.run(['git', '-C', str(path.parent), 'diff', '--quiet', 'HEAD', '--', path.name]).returncode == 0
    require(tracked and clean, 'The declaration must be tracked, committed and unmodified.')
    text = path.read_text(encoding='utf-8')
    plan = STAGES[args.stage]
    for line in (f'campaign: {CAMPAIGN}', f'stage: {args.stage}', f'provider_limit_usd: {plan["provider_limit"]}',
                 f'wallet_limit_usd: {plan["wallet_limit"]}', f'model: {EXPECTED_MODEL}',
                 f'pricing_version: {EXPECTED_PRICING_VERSION}'):
        require(line in text, f'The declaration does not state `{line}`.')
    authorization = re.search(r'^authorization: (\S.{7,})$', text, re.M)
    require(authorization, 'The declaration names no owner authorization.')
    return {'declaration': str(path), 'sha256': hashlib.sha256(text.encode()).hexdigest(),
            'authorization': authorization.group(1).strip()}


def candidate_identity():
    head = subprocess.run(['git', '-C', str(REBUILD), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(['git', '-C', str(REBUILD), 'status', '--porcelain', '--untracked-files=no'],
                           capture_output=True, text=True).stdout.strip()
    require(len(head) == 40 and not dirty, 'The candidate checkout must be a clean commit.')
    require(not (REBUILD / '.env').exists(), 'The candidate checkout must have no .env (nothing else may be loaded).')
    return {'commit': head, 'runner_sha256': hashlib.sha256(RUNNER.read_bytes()).hexdigest()}


def outer(args):
    """Validate, build the scrubbed environment, and re-execute as the process that makes requests."""
    require(args.stage in STAGES, 'Unknown stage.')
    campaign_dir = private_directory(Path(args.campaign_dir).resolve())
    for name in ('ledger', 'responses', 'replay', 'scores', 'state', 'home', 'tmp'):
        private_directory(campaign_dir / name)
    identity = candidate_identity()
    require(not (campaign_dir / f'stage-{args.stage}-verdict.json').exists(),
            f'Stage {args.stage} of this campaign already has a verdict; it is never re-run in place.')
    if args.stage == 2:
        verdict = campaign_dir / 'stage-1-verdict.json'
        require(verdict.exists() and read_json(verdict)['verdict'] == 'PASS',
                'Stage 2 is gated: stage 1 has not passed in this campaign.')
    if args.mode == 'offline':
        provider = offline_provider(args.provider)
        authority = {'authorization': 'offline-validation (no provider request)'}
    else:
        require(not os.environ.get('ANTHROPIC_BASE_URL'), 'Live mode never routes the provider elsewhere.')
        authority = declared(args)          # refused here, before the protected configuration is opened
        provider = provider_fields_from(PROTECTED_CONFIGURATION)
    env = scrubbed_environment(args, provider, campaign_dir)
    env['WMN_CAMPAIGN_CONTEXT'] = json.dumps({**identity, **authority, 'stage': args.stage, 'mode': args.mode,
                                              'campaign_dir': str(campaign_dir),
                                              'offline_timeout': args.offline_timeout,
                                              'offline_retry_wait': args.offline_retry_wait,
                                              'expectation_override': args.expectation_override if args.mode == 'offline' else None})
    os.chdir(REBUILD)
    os.execve(sys.executable, [sys.executable, '-B', str(RUNNER), '_inner'], env)


# ── the process that makes requests ──────────────────────────────────────────────────────────────────────────────

class Stop(Exception):
    """A stop condition: record it and send nothing further."""


def inner():
    context = json.loads(os.environ['WMN_CAMPAIGN_CONTEXT'])
    campaign_dir, stage, mode = Path(context['campaign_dir']), context['stage'], context['mode']
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    sys.path.insert(0, str(REBUILD))
    import django
    django.setup()
    from django.conf import settings
    require(settings.AI_MODE == 'live' and settings.WM_NARRATIVE and settings.SYNTHETIC_ONLY, 'Live synthetic narrative mode required.')
    require(str(settings.STATE_DIR).startswith(str(campaign_dir)), 'The state directory must be the campaign\'s.')
    require(settings.DATABASES['default']['NAME'].startswith('quillmd_wmn_campaign'), 'Wrong database.')
    if mode == 'offline':
        require(key == OFFLINE_KEY and os.environ.get('ANTHROPIC_BASE_URL', '').startswith('http://127.0.0.1:'),
                'Offline mode reached a non-loopback provider.')
        from core import wm_narrative
        wm_narrative.PROVIDER_TIMEOUT_SECONDS = float(context['offline_timeout'])
    else:
        require(key and not os.environ.get('ANTHROPIC_BASE_URL'), 'Live mode needs the provider key and no redirect.')
    from django.core.management import call_command
    call_command('migrate', interactive=False, verbosity=0)
    ledger = campaign_dir / 'ledger'
    record = campaign_record(campaign_dir, context)
    recover_interrupted(ledger)
    report = {'campaign': CAMPAIGN, 'stage': stage, 'mode': mode, 'candidate': context['commit'],
              'authorization': context['authorization'], 'cases': {}, 'stops': []}
    verdict = 'INCOMPLETE'
    try:
        world = Synthetic(campaign_dir, stage)
        stage_zero = world.stage_zero()
        report['stage_zero'] = stage_zero
        verdict = run_stage(world, ledger, stage, context, report)
    except (Stop, Refused) as stop:
        report['stops'].append(str(stop))
        verdict = 'FAIL' if str(stop).startswith('WRONG') else 'STOPPED'
    except Exception as error:      # fail closed: an unexpected runner error sends nothing further
        report['stops'].append(f'runner error: {type(error).__name__}')
        verdict = 'STOPPED'
    finally:
        rows = load_ledger(ledger)
        report['totals_stage'] = {k: (money(v) if isinstance(v, Decimal) else v) for k, v in totals(rows, stage).items()}
        report['totals_campaign'] = {k: (money(v) if isinstance(v, Decimal) else v) for k, v in totals(rows).items()}
        report['limits'] = {'stage_provider': str(STAGES[stage]['provider_limit']),
                            'stage_wallet': str(STAGES[stage]['wallet_limit']),
                            'campaign_provider': str(CAMPAIGN_PROVIDER_LIMIT), 'campaign_wallet': str(CAMPAIGN_WALLET_LIMIT)}
        try:
            export_records(campaign_dir, stage)
        except Exception as error:  # the verdict still stands; the missing export is itself reported
            report['stops'].append(f'record export failed: {type(error).__name__}')
            verdict = 'STOPPED' if verdict == 'PASS' else verdict
        secret = key if mode == 'live' else ''
        leaks = leaked(campaign_dir, secret)
        if leaks:
            report['stops'].append('KEY FOUND IN EVIDENCE: ' + ', '.join(leaks))
            verdict = 'STOPPED'
        report['verdict'] = verdict
        text = json.dumps(report, default=str)
        if (secret and secret in text) or KEY_SHAPE.search(text):
            report = {'verdict': 'STOPPED', 'stops': ['The report itself carried a key-shaped value; withheld.']}
            verdict = 'STOPPED'
        write_new(campaign_dir / f'stage-{stage}-verdict.json', {'verdict': verdict, 'stops': report['stops'],
                                                                 'record': record})
        write_new(campaign_dir / f'report-stage-{stage}.json', report)
        late = leaked(campaign_dir, secret)
        if late:
            write_new(campaign_dir / f'KEY-LEAK-stage-{stage}.json', {'files': late})
            verdict = 'STOPPED'
        os.environ.pop('ANTHROPIC_API_KEY', None)
        print(json.dumps({'verdict': verdict, 'stops': report['stops'], 'totals_stage': report.get('totals_stage')}, indent=1))
    return EXIT[verdict]


def campaign_record(campaign_dir, context):
    path = campaign_dir / 'campaign.json'
    record = {'campaign': CAMPAIGN, 'mode': context['mode'], 'candidate': context['commit'],
              'runner_sha256': context['runner_sha256'], 'expected_model': EXPECTED_MODEL,
              'expected_pricing_version': EXPECTED_PRICING_VERSION, 'geo_margin': str(GEO_MARGIN),
              'campaign_provider_limit': str(CAMPAIGN_PROVIDER_LIMIT), 'campaign_wallet_limit': str(CAMPAIGN_WALLET_LIMIT),
              'stages': {str(n): {**{k: (list(v) if isinstance(v, tuple) else str(v)) for k, v in p.items()}}
                         for n, p in STAGES.items()}}
    if not path.exists():
        from core.models import Job
        require(not Job.objects.exists(), 'A new campaign needs an empty synthetic database.')
        write_new(path, record)
    stored = read_json(path)
    for name in ('campaign', 'mode', 'candidate', 'runner_sha256', 'expected_pricing_version'):
        require(stored[name] == record[name], f'This campaign directory belongs to another {name}.')
    return stored


def recover_interrupted(ledger):
    """An attempt with no outcome is an UNKNOWN provider outcome, recorded once and counted at its maximum. The job the
    product created for it (if any) is named, so it is accounted for rather than read as a request nobody made."""
    from core.models import Job, ProviderReceipt
    for attempt, outcome in load_ledger(ledger):
        if outcome is None:
            job = Job.objects.filter(encounter_id=attempt.get('encounter')).first() if attempt.get('encounter') else None
            receipt = ProviderReceipt.objects.filter(job=job).first() if job else None
            write_new(ledger / f'{attempt["number"]:03d}-{attempt["case"]}-outcome.json',
                      {'class': 'interrupted_unknown', 'recorded_at': now(), 'job': str(job.pk) if job else None,
                       'state': job.state if job else None, 'worker_ran': bool(job and job.state != 'queued'),
                       'provider_actual_cost': str(receipt.actual_cost) if receipt else None,
                       'note': 'No outcome was written: the provider may have received and billed this request.'})


def now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class Synthetic:
    """The campaign's synthetic world, created through the product's own pages."""

    def __init__(self, campaign_dir, stage):
        from django.test import Client
        from django.utils import timezone
        from core.models import Department, Membership, Organization, Patient, Template, User, Wallet, LedgerEntry
        from core.tests.wm_narrative_benchmark import load
        self.stage = stage
        self.mapping = load('mapping.json')
        self.cases = {c['id']: c for name in ('cases.json', 'heldout-cases.json') for c in load(name)['cases']}
        self.user, created = User.objects.get_or_create(
            username='wmn-campaign-clinician', defaults={'email': 'wmn-campaign@synthetic.quillmd.invalid',
                                                        'first_name': 'SYNTHETIC', 'last_name': 'Campaign Clinician',
                                                        'verified_at': timezone.now()})
        if created:
            organization = Organization.objects.create(name='Synthetic WM narrative campaign')
            department = Department.objects.create(organization=organization, name='Synthetic venous duplex')
            Membership.objects.create(user=self.user, department=department, role='clinician')
            Patient.objects.create(department=department, display_name='SYNTHETIC CAMPAIGN PATIENT',
                                   reference='WMN-CAMPAIGN', created_by=self.user)
        self.department = Membership.objects.get(user=self.user).department
        self.patient = Patient.objects.get(department=self.department, reference='WMN-CAMPAIGN')
        self.client = Client()
        self.client.force_login(self.user)
        if not Template.objects.filter(department=self.department).exists():
            original = REBUILD.parent / 'WM IOV Template.docx'
            from django.core.files.uploadedfile import SimpleUploadedFile
            from core.wm_review import ORIGINAL_SHA256
            data = original.read_bytes()
            require(hashlib.sha256(data).hexdigest() == ORIGINAL_SHA256, 'The blank qualified form is not the original.')
            response = self.client.post('/templates/upload/', {'name': 'Synthetic WM campaign form',
                                                              'department': self.department.pk, 'synthetic_only': 'on',
                                                              'file': SimpleUploadedFile('WM IOV Template.docx', data)})
            require(response.status_code == 302, f'Template upload refused ({response.status_code}).')
        self.version = Template.objects.get(department=self.department).versions.get(number=1)
        require(self.version.fields == self.mapping['fields']
                and self.version.review_requirements == self.mapping['review_requirements'],
                'The uploaded form is not the benchmark\'s mapping.')
        # The wallet: funded TO the stage's limit, so the product can never hold more than the stage allows.
        wallet, _ = Wallet.objects.get_or_create(user=self.user, kind='promo')
        from core.billing import available_balance
        available = available_balance(self.user, self.department)
        fund = STAGES[stage]['wallet_limit'] - available
        if fund > 0:
            wallet.balance += fund
            wallet.save(update_fields=['balance'])
            LedgerEntry.objects.create(wallet=wallet, amount=fund, kind='campaign_grant',
                                       key=f'campaign:{CAMPAIGN}:stage:{stage}', balance_after=wallet.balance,
                                       description=f'Synthetic campaign funding to the stage {stage} wallet limit')
        self.wallet = wallet

    def stage_zero(self):
        """The application's own configuration and pre-send quote, before anything is sent."""
        from core import generation
        config = generation.configuration()
        seen = {'model': config['model'], 'provider': config['provider'], 'mode': config['mode'],
                'pricing_version': config['pricing_version'], 'narrative_contract': config.get('narrative_contract'),
                'input_rate': config['input_rate'], 'output_rate': config['output_rate'],
                'cached_rate': config['cached_rate'], 'discount_rate': config['discount_rate']}
        if (config['provider'], config['model'], config['pricing_version']) != ('anthropic', EXPECTED_MODEL, EXPECTED_PRICING_VERSION):
            raise Stop(f'Stage 0: the application is configured for {config["provider"]}:{config["model"]} '
                       f'{config["pricing_version"]}, not the declared model and pricing.')
        require(config.get('narrative_contract') == generation.NARRATIVE_CONTRACT, 'Stage 0: the narrative contract is off.')
        seen['maxima'] = {case: str(self.maximum_cost(case)) for case in STAGES[self.stage]['cases']}
        worst = stage_worst_case({c: Decimal(v) for c, v in seen['maxima'].items()}, self.stage)
        seen['worst_case'] = {k: (money(v) if isinstance(v, Decimal) else v) for k, v in worst.items()}
        if not worst['fits']:
            raise Stop('Stage 0: the stage limits do not cover every allowed attempt at the largest case.')
        return seen

    def maximum_cost(self, case_id):
        from core import generation
        requirements = self.version.review_requirements
        return generation.maximum_cost(self.cases[case_id]['notes'], self.version.fields, generation.configuration(),
                                       context_labels=[row['label'] for row in requirements], requirements=requirements)

    def encounter(self, case_id):
        from django.utils import timezone
        from core.models import Encounter
        before = set(Encounter.objects.values_list('pk', flat=True))
        response = self.client.post('/encounters/new/', {'patient': self.patient.pk, 'template_version': self.version.pk,
                                                         'notes': self.cases[case_id]['notes'], 'synthetic_only': 'on',
                                                         'service_date': timezone.localdate().isoformat()})
        require(response.status_code == 302, f'Encounter creation refused ({response.status_code}).')
        created = Encounter.objects.exclude(pk__in=before)
        require(created.count() == 1, 'Encounter creation did not create exactly one encounter.')
        encounter = created.get()
        require(encounter.notes == self.cases[case_id]['notes'], 'The saved notes are not the case\'s notes.')
        return encounter

    def quote(self, encounter):
        """The generate form exactly as the page shows it: the signed quote, the revision, the maximum charge."""
        import html
        from django.core import signing
        page = self.client.get(f'/encounters/{encounter.pk}/')
        require(page.status_code == 200, f'The encounter page failed ({page.status_code}).')
        text = page.content.decode()
        form = re.search(r'<form[^>]*data-generate-form[^>]*>(.*?)</form>', text, re.S)
        require(form, 'The page offers no Generate form.')
        token = html.unescape(re.search(r'name="usage_quote" value="([^"]*)"', form.group(1)).group(1))
        revision = re.search(r'name="revision" value="(\d+)"', form.group(1)).group(1)
        shown = re.search(r'Reserve up to \$([0-9.]+)\.', text)
        require(shown, 'The page shows no maximum charge.')
        quoted = signing.loads(token, salt='usage-quote')['config']
        return token, revision, Decimal(shown.group(1)), quoted


def run_stage(world, ledger, stage, context, report):
    from core.models import Job, ProviderReceipt, Usage
    plan = STAGES[stage]
    consecutive = 0
    offline = context['mode'] == 'offline'
    retry_wait = float(context['offline_retry_wait']) if offline else RETRY_WAIT_SECONDS
    override = context.get('expectation_override') if offline else None
    queue = list(plan['cases'])
    done = {a['case'] for a, o in load_ledger(ledger) if a['stage'] == stage and o and o['class'] in ('adopted', 'output_unusable')}
    queue = [c for c in queue if c not in done]
    while queue:
        case_id = queue[0]
        rows = load_ledger(ledger)
        # Any earlier attempt of this case in this stage (a transport failure, an interrupted run) makes this a retry.
        kind = 'retry' if any(a['stage'] == stage and a['case'] == case_id for a, _ in rows) else 'initial'
        if kind == 'retry' and totals(rows, stage)['retries'] >= plan['max_retries']:
            raise Stop(f'Case {case_id} needs a retry and all {plan["max_retries"]} stage retries are used.')
        maximum = world.maximum_cost(case_id)
        next_attempt_allowed(rows, stage, maximum)
        number = len(rows) + 1
        attempt = {'number': number, 'stage': stage, 'case': case_id, 'kind': kind, 'maximum_cost': str(maximum),
                   'provider_bound': money(attempt_bound(maximum)), 'hold': str(maximum * MULTIPLIER),
                   'started_at': now(), 'pid': os.getpid(), 'mode': context['mode']}
        encounter = world.encounter(case_id)
        token, revision, shown, quoted = world.quote(encounter)
        if (quoted['model'], quoted['pricing_version']) != (EXPECTED_MODEL, EXPECTED_PRICING_VERSION):
            raise Stop(f'The page quoted {quoted["model"]} {quoted["pricing_version"]}.')
        if shown != (maximum * MULTIPLIER).quantize(Decimal(1).scaleb(shown.as_tuple().exponent)):
            raise Stop(f'The page shows ${shown}, the runner computed ${maximum * MULTIPLIER}.')
        attempt.update(encounter=str(encounter.pk), quoted_model=quoted['model'],
                       quoted_pricing_version=quoted['pricing_version'], shown_maximum_charge=str(shown))
        write_new(ledger / f'{number:03d}-{case_id}-attempt.json', attempt)      # BEFORE the hold and the request
        outcome = one_request(world, encounter, token, revision, quoted)
        write_new(ledger / f'{number:03d}-{case_id}-outcome.json', outcome)
        if outcome.get('stop'):
            raise Stop(outcome['stop'])
        # Nothing but the runner's own attempts may have reached the provider or the ledger of this database.
        recorded = load_ledger(ledger)
        with_job = sum(1 for _, o in recorded if o and o.get('job'))
        with_receipt = sum(1 for _, o in recorded if o and o.get('provider_actual_cost') not in (None, ''))
        if (Job.objects.count(), ProviderReceipt.objects.count()) != (with_job, with_receipt):
            raise Stop(f'Uninitiated request: {Job.objects.count()} jobs / {ProviderReceipt.objects.count()} receipts '
                       f'against {with_job} / {with_receipt} attempts.')
        if Usage.objects.count() != with_receipt:
            raise Stop('A usage row exists that no attempt accounts for.')
        cls = outcome['class']
        if outcome.get('provider_actual_cost') not in (None, '') and Decimal(outcome['provider_actual_cost']) > maximum:
            raise Stop(f'Attempt {number}: provider cost {outcome["provider_actual_cost"]} above its maximum {maximum}.')
        if outcome.get('absorbed_over_limit'):
            raise Stop(f'Attempt {number}: a charge above its hold was absorbed.')
        if outcome.get('response_model') and not outcome['response_model'].startswith(EXPECTED_MODEL):
            raise Stop(f'Attempt {number}: the provider answered as {outcome["response_model"]}.')
        if cls == 'adopted':
            consecutive = 0
            score = score_attempt(world, encounter, case_id, number, override)
            report['cases'][case_id] = score
            if score['counts'].get('wrong_supported') or score['counts'].get('statement_wrong'):
                raise Stop(f'WRONG ANSWER: case {case_id} pre-filled {score["counts"].get("wrong_supported", 0)} wrong '
                           f'answer(s) and {score["counts"].get("statement_wrong", 0)} wrong statement(s).')
            queue.pop(0)
        elif cls == 'output_unusable':
            consecutive = 0
            report['cases'][case_id] = {'outcome': 'output_unusable', 'error': outcome.get('error')}
            queue.pop(0)
        elif cls == 'transport_failure':
            consecutive += 1
            used = totals(load_ledger(ledger), stage)['retries']
            if consecutive >= 2:
                raise Stop('Two consecutive transport failures.')
            if used >= plan['max_retries']:
                raise Stop(f'Transport failure with all {plan["max_retries"]} stage retries used.')
            time.sleep(retry_wait)
        elif cls == 'not_sent':
            raise Stop(f'Attempt {number} was refused before any request: {outcome.get("error")}')
        else:
            raise Stop(f'Attempt {number} ended {cls}: {outcome.get("error_class") or outcome.get("error")}')
    complete = all(case in report['cases'] and report['cases'][case].get('outcome') == 'adopted' for case in plan['cases'])
    return 'PASS' if complete else 'INCOMPLETE'


def one_request(world, encounter, token, revision, quoted):
    """The doctor's Generate request, then the worker's own run_one: the ONE provider request of this attempt."""
    from core.jobs import run_one
    from core.models import AuditEvent, Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage
    started = time.monotonic()
    response = world.client.post(f'/encounters/{encounter.pk}/generate/', {'usage_quote': token, 'revision': revision})
    jobs = list(Job.objects.filter(encounter=encounter))
    if response.status_code != 302 or len(jobs) != 1:
        return {'class': 'not_sent', 'job': None, 'error': 'Generate did not queue exactly one job.',
                'recorded_at': now()}
    job = jobs[0]
    held = sum((r.amount for r in Reservation.objects.filter(job=job)), Decimal('0'))
    if job.config.get('pricing_version') != quoted['pricing_version'] or job.config.get('model') != EXPECTED_MODEL:
        return {'class': 'not_sent', 'job': str(job.pk), 'held': str(held), 'recorded_at': now(),
                'stop': 'The queued job does not carry the quoted model and pricing; the worker was not run.'}
    worked = run_one()
    job.refresh_from_db()
    receipt = ProviderReceipt.objects.filter(job=job).first()
    usage = Usage.objects.filter(job=job).first()
    audit = AuditEvent.objects.filter(target=str(job.pk), action__in=('job.failed', 'job.reconciliation', 'job.succeeded')).order_by('-created_at').first()
    details = audit.details if audit else {}
    outcome = {
        'job': str(job.pk), 'worker_ran': worked, 'state': job.state, 'error': job.error, 'recorded_at': now(),
        'seconds': round(time.monotonic() - started, 3), 'held': str(held),
        'error_class': details.get('error_class', ''), 'billing': details.get('billing', ''),
        'provider_request_id': job.provider_request_id, 'provider_resource_id': job.provider_resource_id,
        'provider_actual_cost': str(receipt.actual_cost) if receipt else None,
        'units': receipt.units if receipt else None,
        # What the synthetic customer was actually charged for this job: its usage debits net of any absorption.
        'wallet_charged': str(-sum((e.amount for e in LedgerEntry.objects.filter(job=job)), Decimal('0'))),
        'usage_charged_cost': str(usage.charged_cost) if usage else None,
        'platform_absorbed': str(PlatformCost.objects.filter(job=job, kind='absorbed_failure').first().amount)
        if PlatformCost.objects.filter(job=job, kind='absorbed_failure').exists() else None,
        'absorbed_over_limit': str(PlatformCost.objects.filter(job=job, kind='absorbed_over_limit').first().amount)
        if PlatformCost.objects.filter(job=job, kind='absorbed_over_limit').exists() else None,
        'reservations': sorted({r.state for r in Reservation.objects.filter(job=job)}),
    }
    outcome['class'] = classify(job.state, outcome['error_class'], receipt is not None, outcome['billing'])
    if job.result_path:
        outcome.update(retain_response(world, job, encounter))
    return outcome


def retain_response(world, job, encounter):
    """The provider's answer, kept as evidence and as an offline replay file for exactly these notes."""
    from core.security import private_path
    saved = json.loads(private_path(job.result_path).read_bytes())
    output = saved.get('provider_output') or {}
    text = ''.join(block.get('text', '') for block in output.get('content', []) if block.get('type') == 'text')
    base = Path(os.environ['QUILLMD_STATE_DIR']).parent
    digest = hashlib.sha256(encounter.notes.encode()).hexdigest()
    number = len(list((base / 'responses').glob('*.json'))) + 1
    write_new(base / 'responses' / f'{number:03d}-{job.pk}.json', output)
    replay = base / 'replay' / f'{digest}.json'
    if text and not replay.exists():
        fd = os.open(replay, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
    return {'response_model': output.get('model', ''), 'stop_reason': output.get('stop_reason', ''),
            'response_sha256': hashlib.sha256(text.encode()).hexdigest() if text else ''}


def score_attempt(world, encounter, case_id, number, override):
    """The frozen scorer against the expectations written before any live response existed; and the page renders."""
    from core.tests.wm_narrative_benchmark import score_case
    encounter.refresh_from_db()
    case = world.cases[case_id]
    if override and override.get('case') == case_id:        # offline validation of the stop wiring only
        case = json.loads(json.dumps(case))
        case['expected_fields'][override['key']] = override['expected']
    proposals = (encounter.template_review or {}).get('proposals') or {}
    counts, rows = score_case(case, encounter.answers, proposals, world.version.review_requirements)
    page = world.client.get(f'/encounters/{encounter.pk}/')
    if page.status_code != 200 or b'data-wm-narrative' not in page.content:
        raise Stop(f'The generated draft\'s page did not render ({page.status_code}).')
    score = {'outcome': 'adopted', 'attempt': number, 'counts': dict(counts), 'rows': rows}
    write_new(Path(os.environ['QUILLMD_STATE_DIR']).parent / 'scores' / f'{number:03d}-{case_id}.json', score)
    return score


def export_records(campaign_dir, stage):
    """The synthetic database's financial and job records, kept with the evidence (no clinical text)."""
    from core.models import AuditEvent, Job, LedgerEntry, PlatformCost, ProviderReceipt, Reservation, Usage, Wallet
    rows = {
        'jobs': list(Job.objects.values('id', 'state', 'error', 'provider', 'provider_request_id', 'created_at',
                                        'started_at', 'finished_at', 'config__pricing_version', 'config__model')),
        'receipts': list(ProviderReceipt.objects.values('job_id', 'provider', 'provider_request_id', 'actual_cost', 'units')),
        'usage': list(Usage.objects.values('job_id', 'actual_cost', 'charged_cost', 'units', 'rates')),
        'reservations': list(Reservation.objects.values('job_id', 'amount', 'state')),
        'ledger': list(LedgerEntry.objects.values('kind', 'amount', 'balance_after', 'key', 'job_id')),
        'platform_costs': list(PlatformCost.objects.values('kind', 'amount', 'job_id')),
        'wallets': list(Wallet.objects.values('kind', 'balance', 'reserved')),
        'audit': list(AuditEvent.objects.filter(action__startswith='job.').values('action', 'target', 'details', 'created_at')),
    }
    path = campaign_dir / f'db-records-stage-{stage}.json'
    if path.exists():
        path = campaign_dir / f'db-records-stage-{stage}-{int(time.time())}.json'
    write_new(path, rows)


def leaked(campaign_dir, key):
    """Every evidence file this campaign wrote, searched for the key (by value, never printed) and its shape."""
    found = []
    for path in campaign_dir.rglob('*'):
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 50 * 1024 * 1024:
            continue
        data = path.read_bytes()
        if (key and key.encode() in data) or KEY_SHAPE.search(data.decode('utf-8', 'replace')):
            found.append(str(path.relative_to(campaign_dir)))
    return found


# ── plan ─────────────────────────────────────────────────────────────────────────────────────────────────────────

def plan(args):
    """Per-case maxima at the declared rates, from the frozen notes and mapping; no database, no request."""
    sys.path.insert(0, str(REBUILD))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
    import django
    django.setup()
    from django.test.utils import override_settings
    from core import generation
    from core.tests.wm_narrative_benchmark import load
    mapping = load('mapping.json')
    cases = {c['id']: c for name in ('cases.json', 'heldout-cases.json') for c in load(name)['cases']}
    config = {'mode': 'live', 'provider': 'anthropic', 'model': EXPECTED_MODEL, 'input_rate': '3', 'output_rate': '15',
              'cached_rate': '0.30', 'discount_rate': '0', 'narrative_contract': generation.NARRATIVE_CONTRACT}
    out = {}
    with override_settings(WM_NARRATIVE=True):
        for stage, spec in STAGES.items():
            maxima = {c: generation.maximum_cost(cases[c]['notes'], mapping['fields'], config,
                                                 context_labels=[r['label'] for r in mapping['review_requirements']],
                                                 requirements=mapping['review_requirements']) for c in spec['cases']}
            worst = stage_worst_case(maxima, stage)
            out[stage] = {'cases': {c: {'maximum_cost': money(m), 'provider_bound': money(attempt_bound(m)),
                                        'hold': money(m * MULTIPLIER)} for c, m in maxima.items()},
                          'max_attempts': spec['max_attempts'], 'max_retries': spec['max_retries'],
                          'provider_limit': str(spec['provider_limit']), 'wallet_limit': str(spec['wallet_limit']),
                          **{k: (money(v) if isinstance(v, Decimal) else v) for k, v in worst.items()}}
    print(json.dumps({'campaign': CAMPAIGN, 'model': EXPECTED_MODEL, 'pricing_version': EXPECTED_PRICING_VERSION,
                      'geo_margin': str(GEO_MARGIN), 'campaign_provider_limit': str(CAMPAIGN_PROVIDER_LIMIT),
                      'campaign_wallet_limit': str(CAMPAIGN_WALLET_LIMIT), 'stages': out}, indent=1))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['_inner']:
        try:
            return inner()
        except Refused as refused:
            print('REFUSED: ' + str(refused), file=sys.stderr)
            return 2
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('command', choices=['plan', 'run'])
    parser.add_argument('--mode', choices=['offline', 'live'], required=True)
    parser.add_argument('--stage', type=int, default=1)
    parser.add_argument('--campaign-dir')
    parser.add_argument('--db')
    parser.add_argument('--engine')
    parser.add_argument('--provider', help='offline only: the loopback mock provider file')
    parser.add_argument('--declaration', help='live only: the committed declaration naming the authorization')
    parser.add_argument('--offline-timeout', type=float, default=5.0)
    parser.add_argument('--offline-retry-wait', type=float, default=1.0)
    parser.add_argument('--expectation-override', type=json.loads, default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == 'plan':
            return plan(args)
        require(args.campaign_dir and args.db and args.engine, 'run needs --campaign-dir, --db and --engine.')
        require(args.mode == 'offline' or (args.provider is None and args.expectation_override is None),
                'Live mode takes no mock provider and no expectation override.')
        outer(args)
    except Refused as refused:
        print('REFUSED: ' + str(refused), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
