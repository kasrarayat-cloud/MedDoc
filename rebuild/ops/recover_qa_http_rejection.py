#!/usr/bin/env python3
"""Resolve one evidenced HTTP400 in synthetic QA, retaining historical ledgers.

Run only through the committed declaration and ruled-mutation runner. A real
loopback admin process authenticates with MFA and invokes the existing resolution
view. No provider call, financial grant, usage reconciliation or retry is made.
"""
import argparse
import hashlib
import hmac
import http.cookiejar
import json
import os
import re
import secrets
import socket
import stat
import struct
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

JOB = '9c432a90-8d63-4238-b9da-a7f6a1e24c35'
DATABASE = 'quillmd_qa_standing_20261002'
ROOT = Path('/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261002')
PASSWORD = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sonnet5-campaign/qa-db/password')
BODY_SHA = '9b9d5893f46ddb5d5701165a39bcb4b3009c101d9a1d1e1c22edbd692801b732'
OUT = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/accounting/rejection-resolution')
PORT = 9162
EMAIL = 'http400-resolution@synthetic.quillmd.invalid'
REBUILD = Path(__file__).resolve().parents[1]
DEADLINE = time.monotonic() + 180


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        while block := stream.read(1048576):
            value.update(block)
    return value.hexdigest()


def protected_file(path):
    for item in (path, *path.parents):
        require(not item.is_symlink(), 'Linked credential/evidence path refused')
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o600, 'Credential/evidence metadata refused')
    parent = path.parent.stat()
    require(parent.st_uid == os.getuid() and stat.S_IMODE(parent.st_mode) == 0o700,
            'Credential/evidence parent is not protected')
    return path.read_text().strip()


def write_new(path, record):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        json.dump(record, stream, default=str, indent=2)


def evidence():
    path = ROOT / 'evidence/003/provider-response.body'
    body = json.loads(protected_file(path))
    response = json.loads(protected_file(ROOT / 'evidence/003/provider-response.json'))
    require(digest(path) == BODY_SHA == response['body_sha256'], 'Original refusal evidence changed')
    require(response['status_code'] == 400 and body['type'] == 'error'
            and body['error']['type'] == 'invalid_request_error' and 'usage' not in body,
            'Response is not the evidenced definite rejection')
    require(response['request_id'] == body['request_id'], 'Request identity changed')
    return {'body_sha256': BODY_SHA, 'request_id': body['request_id'], 'status_code': 400,
            'provider_cost_evidence': 'no metered response; invoice/report unavailable',
            'original_outcome_preserved': True, 'repeat_request': False}


def environment(password, secret):
    require(not (REBUILD / '.env').exists(), 'Source beside .env refused')
    return {'PATH': str(Path(sys.executable).parent) + ':/usr/bin:/bin', 'HOME': str(OUT),
            'LANG': 'C.UTF-8', 'TZ': 'UTC', 'PYTHONDONTWRITEBYTECODE': '1',
            'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_SECRET_KEY': secret,
            'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_DB_PORT': '55731',
            'QUILLMD_DB_USER': 'quillmd_qa', 'QUILLMD_DB_NAME': DATABASE,
            'QUILLMD_DB_PASSWORD': password, 'QUILLMD_DATA_MODE': 'synthetic',
            'QUILLMD_AI_MODE': 'fixture', 'QUILLMD_ADMIN_SITE': '1', 'QUILLMD_HTTPS': '0',
            'QUILLMD_STATE_DIR': str(ROOT / 'qa-state'), 'QUILLMD_EMAIL_MODE': 'file',
            'QUILLMD_RELEASE_SHA': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REBUILD, text=True).strip()}


def snapshot():
    from core.models import AuditEvent, CostReconciliation, Job, LedgerEntry, Payment, PlatformCost, ProviderReceipt, Reservation, Usage, Wallet
    job = Job.objects.get(pk=JOB)
    reservations = list(Reservation.objects.filter(job=job).order_by('pk').values('id', 'wallet_id', 'amount', 'state'))
    return {'job': {'id': str(job.pk), 'state': job.state, 'error': job.error,
                    'request_key': job.request_key, 'finished_at': job.finished_at,
                    'config': job.config, 'encounter_id': job.encounter_id,
                    'provider_request_id': job.provider_request_id},
            'reservations': reservations,
            'wallets': list(Wallet.objects.order_by('pk')
                            .values('id', 'user_id', 'organization_id', 'kind', 'balance', 'reserved')),
            'unrelated_reservations': list(Reservation.objects.exclude(job=job).order_by('pk')
                                          .values('id', 'job_id', 'wallet_id', 'amount', 'state')),
            'ledger': list(LedgerEntry.objects.order_by('created_at', 'pk')
                           .values('id', 'wallet_id', 'amount', 'kind', 'key', 'job_id', 'balance_after')),
            'receipt_count': ProviderReceipt.objects.filter(job=job).count(),
            'usage_count': Usage.objects.filter(job=job).count(),
            'platform_cost_count': PlatformCost.objects.count(),
            'cost_reconciliation_count': CostReconciliation.objects.count(),
            'immutable_financial_rows': {model.__name__: list(model.objects.order_by('pk').values())
                                        for model in (Usage, ProviderReceipt, PlatformCost, CostReconciliation, Payment)},
            'resolution_audits': list(AuditEvent.objects.filter(action='job.resolved', target=JOB)
                                      .values('id', 'actor_id', 'details', 'created_at'))}


def validate_resolution(before, after):
    """Judge the declared exact hold release; wrong unrelated release is a failure."""
    require(after['job']['state'] == 'failed' and after['job']['finished_at'] is not None,
            'Job did not resolve')
    require(after['job']['request_key'] != before['job']['request_key'], 'Request key did not end')
    for key in ('id', 'config', 'encounter_id', 'provider_request_id'):
        require(after['job'][key] == before['job'][key], 'Job evidence binding changed')
    originals = {r['id']: r for r in before['reservations']}
    final = {r['id']: r for r in after['reservations']}
    require(originals.keys() == final.keys() and len(originals) == len(before['reservations'])
            and len(final) == len(after['reservations']), 'Reservation identities changed')
    for key, row in originals.items():
        require(final[key] == {**row, 'state': 'released'} and row['state'] == 'held',
                'Reservation amount, wallet or release changed')
    wallets = {w['id']: w for w in before['wallets']}
    require({w['id'] for w in after['wallets']} == wallets.keys()
            and len(after['wallets']) == len(wallets), 'Wallet identities changed')
    for row in after['wallets']:
        delta = sum(r['amount'] for r in originals.values() if r['wallet_id'] == row['id'])
        require(row == {**wallets[row['id']], 'reserved': wallets[row['id']]['reserved'] - delta},
                'Wallet balance or exact reservation release differs')
    for key in ('ledger', 'unrelated_reservations', 'platform_cost_count', 'cost_reconciliation_count',
                'immutable_financial_rows'):
        require(after[key] == before[key], 'Unrelated financial evidence changed')
    require(after['usage_count'] == after['receipt_count'] == before['usage_count'] == before['receipt_count'] == 0,
            'Unexpected usage or receipt')
    require(len(after['resolution_audits']) == len(before['resolution_audits']) + 1,
            'Resolution audit missing')


def csrf(page):
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page)
    require(match, 'Served CSRF token absent')
    return match.group(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inspect', action='store_true', help='Read evidence and QA rows only; no mutation')
    args = parser.parse_args()
    os.umask(0o077)
    facts = evidence()
    env = environment(protected_file(PASSWORD), secrets.token_urlsafe(48))
    os.environ.clear(); os.environ.update(env)
    sys.path.insert(0, str(REBUILD)); os.environ['DJANGO_SETTINGS_MODULE'] = 'quillmd.settings'
    import django
    django.setup()
    from django.conf import settings
    require(settings.SYNTHETIC_ONLY and settings.DATABASES['default']['NAME'] == DATABASE
            and settings.DATABASES['default']['PORT'] == '55731', 'QA boundary refused')
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('SET statement_timeout=20000'); cursor.execute('SET lock_timeout=5000')
    before = snapshot()
    if args.inspect:
        print(json.dumps({'evidence': facts, 'before': before}, default=str, indent=2))
        return
    # The caller's environment was scrubbed above; inspect the runner provenance
    # via retained variables passed separately by the explicit entry-point below.
    require(DOOR['declaration'] and DOOR['commit'], 'Ruled-mutation provenance absent')
    declaration = Path(DOOR['declaration'])
    if not declaration.is_absolute():
        declaration = REBUILD.parent / declaration
    require(declaration.is_file() and JOB in declaration.read_text()
            and BODY_SHA in declaration.read_text(), 'Declaration does not bind this job and refusal')
    require(before['job']['state'] == 'reconciliation' and before['receipt_count'] == before['usage_count'] == 0
            and all(row['state'] == 'held' for row in before['reservations']), 'Job no longer eligible')
    require(not OUT.exists(), 'Existing resolution evidence: inspect instead of repeating')
    OUT.mkdir(mode=0o700)
    write_new(OUT / 'before.json', {'facts': facts, **before})
    # The container's local socket needs no password. It is the verified QA
    # container; the installed production database/credentials are never used.
    ports = subprocess.check_output(['docker', 'port', 'v1-sonnet5-qa-pg', '5432'], text=True).strip()
    require(ports == '127.0.0.1:55731', 'QA container port identity changed')
    with open(OUT / 'database-before.sql', 'xb') as stream:
        backup = subprocess.run(['docker', 'exec', 'v1-sonnet5-qa-pg', 'pg_dump', '-U', 'quillmd_qa',
                                 '--no-owner', '--no-acl', DATABASE], stdout=stream, stderr=subprocess.PIPE, timeout=40)
    require(backup.returncode == 0 and (OUT / 'database-before.sql').stat().st_size > 0,
            'QA backup failed; no mutation attempted')
    write_new(OUT / 'backup.json', {'database': DATABASE, 'sha256': digest(OUT / 'database-before.sql'),
                                   'bytes': (OUT / 'database-before.sql').stat().st_size})
    with socket.socket() as probe:
        require(probe.connect_ex(('127.0.0.1', PORT)) != 0, 'Temporary admin port occupied')
    from django.db import transaction
    from django.utils import timezone
    from django_otp.plugins.otp_totp.models import TOTPDevice
    from core.models import User
    from core.security import audit
    password = secrets.token_urlsafe(24)
    server = None; log = None; created_admin = False
    try:
        with transaction.atomic():
            require(not User.objects.filter(email=EMAIL).exists(), 'Resolution administrator already exists')
            admin = User.objects.create_user(username=EMAIL, email=EMAIL, password=password, is_staff=True,
                                             verified_at=timezone.now(), first_name='Synthetic', last_name='Reconciliation')
            device = TOTPDevice.objects.create(user=admin, name='Synthetic QA resolution', confirmed=True)
            audit(admin, 'synthetic.account_seeded', admin.pk, purpose='evidenced QA HTTP400 resolution',
                  declaration=str(declaration), declaration_commit=DOOR['commit'])
        created_admin = True
        write_new(OUT / 'admin-access.json', {'email': EMAIL, 'password': password, 'totp_key_hex': device.key})
        log = open(OUT / 'admin-server.log', 'xb')
        server = subprocess.Popen([sys.executable, '-B', '-m', 'gunicorn', 'quillmd.wsgi:application',
                                   '--bind', f'127.0.0.1:{PORT}', '--workers', '1', '--timeout', '30'],
                                  cwd=REBUILD, env=env, stdout=log, stderr=log, start_new_session=True)
        base = f'http://127.0.0.1:{PORT}'
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        while True:
            require(server.poll() is None and time.monotonic() < DEADLINE, 'Admin readiness deadline or process exit')
            try:
                page = opener.open(base + '/login/', timeout=2).read().decode(); break
            except OSError:
                time.sleep(.2)
        code = hmac.new(bytes.fromhex(device.key), struct.pack('>Q', int(time.time())//30), 'sha1').digest()
        offset = code[-1] & 15
        otp = str((struct.unpack('>I', code[offset:offset+4])[0] & 0x7fffffff) % 1000000).zfill(6)
        form = {'email': EMAIL, 'password': password, 'otp': otp, 'csrfmiddlewaretoken': csrf(page)}
        response = opener.open(urllib.request.Request(base + '/login/', data=urllib.parse.urlencode(form).encode(),
                              headers={'Referer': base + '/login/'}), timeout=15)
        require('/login/' not in response.url, 'MFA administrator login failed')
        console = opener.open(base + '/console/', timeout=15).read().decode()
        evidence_note = f'HTTP400 {facts["request_id"]}; response sha256 {BODY_SHA}; no metered usage; no invoice claimed.'
        form = {'outcome': 'release_no_cost', 'evidence_note': evidence_note,
                'csrfmiddlewaretoken': csrf(console)}
        response = opener.open(urllib.request.Request(base + f'/console/jobs/{JOB}/resolve/',
                              data=urllib.parse.urlencode(form).encode(), headers={'Referer': base + '/console/'}), timeout=15)
        require(response.status == 200, 'Served resolution failed')
        after = snapshot()
        validate_resolution(before, after)
        write_new(OUT / 'after.json', after)
        append_dir = ROOT / 'reconciliations'; append_dir.mkdir(mode=0o700, exist_ok=True)
        result = {'historical_attempt': 3, 'job': JOB, **facts, 'resolved_at': timezone.now(),
                  'declaration': str(declaration), 'declaration_commit': DOOR['commit'],
                  'outcome': 'definite HTTP400 rejection; held funds released through MFA admin view',
                  'served_http_status': response.status, 'provider_billed_reconciled': False,
                  'held_amount_released': str(sum(r['amount'] for r in before['reservations'])),
                  'financial_ledger_unchanged': True, 'historical_ledger_unchanged': True}
        write_new(append_dir / '003-provider-refusal.json', result)
        write_new(OUT / 'result.json', result)
        print(json.dumps(result, default=str, indent=2))
    finally:
        if server and server.poll() is None:
            server.terminate()
            try: server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait(timeout=5)
        if log: log.close()
        if created_admin:
            from django.db.models import F
            User.objects.filter(pk=admin.pk).update(is_active=False, session_version=F('session_version') + 1)
            audit(admin, 'synthetic.resolution_admin_retired', admin.pk, service_stopped=True)


DOOR = {'declaration': os.environ.get('RULED_MUTATION_DECLARATION'),
        'commit': os.environ.get('RULED_MUTATION_DECL_COMMIT')}
if __name__ == '__main__':
    main()
