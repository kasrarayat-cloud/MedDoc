"""Bounded served authorization evidence on a confirmed, isolated synthetic demo.

Execute through that demo's protected qa_launch.py only after the lead verifies
its source/database/processes. No provider call, installed credential, existing
account mutation or financial deletion. Auth fixtures are explicitly synthetic;
their direct finalized files qualify authorization, not clinical finalization.
Passwords, OTP keys, cookies and CSRF tokens remain in memory or a protected
credential file. Reports contain hashes and synthetic identifiers only.
"""
import argparse
import hashlib
import http.cookiejar
import json
import os
import re
import secrets
import socket
import stat
import sys
import tarfile
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TASK = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002')
SCRATCH = TASK / 'security'
MAX_REQUESTS = 150
DEADLINE_SECONDS = 180


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_new(path, data):
    if not isinstance(data, bytes):
        data = json.dumps(data, indent=2, sort_keys=True, default=str).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
    require(sha(path.read_bytes()) == sha(data), 'retained_hash_mismatch')


def protected_file(path):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
            and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o600,
            'unsafe_private_file_metadata')
    require(not path.is_symlink(), 'private_symlink_refused')
    for parent in (path.parent, path.parent.parent):
        info = parent.lstat()
        require(stat.S_ISDIR(info.st_mode) and not parent.is_symlink()
                and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
                'unsafe_private_parent_metadata')
    return path.read_bytes()


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Served:
    def __init__(self):
        self.started = time.monotonic()
        self.requests = 0
        self.records = []

    def client(self):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), NoRedirect())

    def request(self, opener, port, path, method='GET', data=None, host=None, label=''):
        require(time.monotonic() - self.started < DEADLINE_SECONDS, 'request_deadline')
        require(self.requests < MAX_REQUESTS, 'request_count_bound')
        require(port in (9160, 9161) and path.startswith('/') and not path.startswith('//'), 'request_scope')
        self.requests += 1
        url = f'http://127.0.0.1:{port}{path}'
        headers = {'Referer': f'http://127.0.0.1:{port}/login/'}
        if host:
            headers['Host'] = host
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            response = opener.open(req, timeout=6)
        except urllib.error.HTTPError as response_error:
            response = response_error
        payload = response.read(2 * 1024 * 1024 + 1)
        require(len(payload) <= 2 * 1024 * 1024, 'response_size_bound')
        self.records.append({'label': label, 'port': port, 'path': path,
            'method': method, 'host': host or f'127.0.0.1:{port}', 'status': response.code,
            'location': response.headers.get('Location'), 'body_sha256': sha(payload)})
        return response.code, response.headers, payload

    def login(self, account, port, otp=None, expect=True):
        opener = self.client()
        status, _, page = self.request(opener, port, '/login/', label='login_form')
        require(status == 200, 'login_form_unavailable')
        token = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', page)
        require(token is not None, 'login_csrf_missing')
        form = {'email': account['email'], 'password': account['password'],
                'csrfmiddlewaretoken': token[1].decode()}
        if otp is not None:
            form['otp'] = otp
        status, headers, _ = self.request(opener, port, '/login/', 'POST', form, label='login_submit')
        require((status == 302 and headers.get('Location') != '/login/') if expect else status == 200,
                'expected_login_outcome_failed')
        return opener

    def expect(self, opener, port, path, status, *, host=None, method='GET', data=None, label=''):
        code, headers, body = self.request(opener, port, path, method, data=data, host=host, label=label)
        require(code == status, 'unexpected_served_status:' + label)
        if status == 404:
            require(headers.get('Location') is None, 'refusal_redirect:' + label)
        return body


def process_identity(pid, source, release, db, surface, port=None):
    proc = Path('/proc') / str(pid)
    require(proc.stat().st_uid == os.getuid(), 'process_owner_mismatch')
    require((proc / 'cwd').resolve() == source, 'process_source_mismatch')
    command = (proc / 'cmdline').read_bytes().split(b'\0')
    if port is None:
        require(b'manage.py' in command and b'worker' in command, 'worker_command_mismatch')
    else:
        require(b'quillmd.wsgi:application' in command and f'127.0.0.1:{port}'.encode() in command,
                'server_command_mismatch')
    # Only safe identifiers are retained. Never print/cache the process environment.
    names = {'QUILLMD_DB_HOST', 'QUILLMD_DB_PORT', 'QUILLMD_DB_NAME', 'QUILLMD_RELEASE_SHA',
             'QUILLMD_AI_MODE', 'QUILLMD_DATA_MODE', 'QUILLMD_ADMIN_SITE'}
    values = {}
    for part in (proc / 'environ').read_bytes().split(b'\0'):
        key, _, value = part.partition(b'=')
        if key.decode(errors='replace') in names:
            values[key.decode()] = value.decode()
    require(values == {'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_DB_PORT': '55731',
        'QUILLMD_DB_NAME': db, 'QUILLMD_RELEASE_SHA': release, 'QUILLMD_AI_MODE': 'fixture',
        'QUILLMD_DATA_MODE': 'synthetic', 'QUILLMD_ADMIN_SITE': '1' if surface == 'admin' else '0'},
        'process_profile_mismatch')
    return {'pid': pid, 'cwd': str(source), 'surface': surface, 'release': release,
            'database': db, 'command_sha256': sha(b'\0'.join(command)),
            'start_ticks': (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo-dir', type=Path)
    parser.add_argument('--expected-commit')
    parser.add_argument('--doctor-pid', type=int)
    parser.add_argument('--admin-pid', type=int)
    parser.add_argument('--worker-pid', type=int)
    parser.add_argument('--run-id')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'prepared_only': True, 'max_requests': MAX_REQUESTS,
                          'deadline_seconds': DEADLINE_SECONDS, 'mutations': 0, 'provider_requests': 0}))
        return
    require(all((args.demo_dir, args.expected_commit, args.doctor_pid, args.admin_pid,
                 args.worker_pid, args.run_id)), 'confirmed_execution_identity_required')
    require(re.fullmatch('[0-9a-f]{40}', args.expected_commit), 'invalid_release_identity')
    require(re.fullmatch('[a-z0-9][a-z0-9-]{1,55}', args.run_id), 'invalid_run_identity')
    demo = args.demo_dir.absolute()
    require(demo.parent == TASK and demo.name == 'demo-' + args.expected_commit[:8], 'demo_scope_mismatch')
    require(not demo.is_symlink(), 'demo_symlink_refused')
    prepared = json.loads(protected_file(demo / 'prepared.json'))
    require(prepared['commit'] == args.expected_commit and prepared['ports'] == [9160, 9161]
        and prepared['ai_mode'] == 'fixture' and prepared['field_relations'] is True
        and prepared['role_suggestions'] is False, 'prepared_profile_mismatch')
    db = 'quillmd_qa_int_sol_' + args.expected_commit[:8]
    require(prepared['database'] == db and prepared['root'] == str(demo), 'prepared_database_mismatch')
    require(sha(protected_file(demo / 'source.tar')) == prepared['source_tar_sha256'], 'source_archive_mismatch')
    source = demo / 'src' / 'rebuild'
    require(not os.path.lexists(source / '.env'), 'dotenv_refused')
    source_members = {}
    with tarfile.open(demo / 'source.tar') as archive:
        for member in archive.getmembers():
            require(member.isfile() or member.isdir(), 'linked_archive_member_refused')
            parts = Path(member.name)
            require(not parts.is_absolute() and '..' not in parts.parts and parts.parts[0] == 'rebuild',
                    'archive_member_boundary')
            if member.isfile():
                target = demo / 'src' / parts
                require(target.is_file() and not target.is_symlink()
                    and target.stat().st_nlink == 1, 'extracted_source_missing_or_linked')
                require(all(not parent.is_symlink() for parent in target.parents
                    if parent == demo or parent.is_relative_to(demo)), 'extracted_source_parent_linked')
                expected_hash = sha(archive.extractfile(member).read())
                require(sha(target.read_bytes()) == expected_hash, 'extracted_source_changed')
                source_members[member.name] = expected_hash
    processes = [process_identity(args.doctor_pid, source, args.expected_commit, db, 'doctor', 9160),
                 process_identity(args.admin_pid, source, args.expected_commit, db, 'admin', 9161),
                 process_identity(args.worker_pid, source, args.expected_commit, db, 'doctor')]
    require(Path.cwd() == source, 'use_confirmed_demo_launcher')
    connect = socket.socket.connect
    def local_connection(sock, address):
        require(isinstance(address, tuple) and address[0] == '127.0.0.1'
                and address[1] in (55731, 9160, 9161), 'out_of_scope_network_connection')
        return connect(sock, address)
    socket.socket.connect = local_connection
    sys.path.insert(0, str(source))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'quillmd.settings')
    import django
    django.setup()
    from django.conf import settings
    from django.db import transaction, connection
    from django.db.models import F
    from django.utils import timezone
    from django_otp.oath import totp
    from django_otp.plugins.otp_totp.models import TOTPDevice
    from core import models as m
    from core.security import audit, private_path
    require(settings.SYNTHETIC_ONLY and settings.AI_MODE == 'fixture'
        and settings.RELEASE_SHA == args.expected_commit
        and settings.DATABASES['default']['NAME'] == db
        and settings.DATABASES['default']['HOST'] == '127.0.0.1'
        and str(settings.DATABASES['default']['PORT']) == '55731', 'harness_environment_mismatch')
    with connection.cursor() as cursor:
        cursor.execute("SET lock_timeout = '3s'")
        cursor.execute("SET statement_timeout = '8s'")
    out = SCRATCH / ('served-auth-' + args.run_id)
    require(not out.exists(), 'terminal_run_identity_not_reusable')
    out.mkdir(mode=0o700)
    served = Served()
    created = []
    report = {'run_id': args.run_id, 'release': args.expected_commit, 'database': db,
        'processes': processes, 'provider_requests': 0,
        'source_members': len(source_members),
        'source_manifest_sha256': sha(json.dumps(source_members, sort_keys=True).encode()),
        'fixture_scope': 'Direct synthetic authorization rows/files; no clinical workflow qualification',
        'credentials_recorded': False, 'financial_history_deleted': False, 'status': 'preparing'}
    financial_models = [m.Job, m.Wallet, m.Reservation, m.Usage, m.LedgerEntry, m.ProviderReceipt,
                        m.Payment, m.PlatformCost, m.CostReconciliation]

    def fingerprints():
        return {model.__name__: {'count': model.objects.count(),
            'sha256': sha(json.dumps(list(model.objects.order_by('pk').values()),
                sort_keys=True, default=str, separators=(',', ':')).encode())} for model in financial_models}

    try:
        for port, surface in [(9160, 'doctor'), (9161, 'admin')]:
            payload = served.expect(served.client(), port, '/health/', 200, label='synthetic_health')
            health = json.loads(payload)
            require(health['release'] == args.expected_commit and health['surface'] == surface
                    and health['data_mode'] == 'synthetic-only', 'served_identity_mismatch')
        report['before_fixture_financial'] = fingerprints()
        prefix = 'SEC-' + args.run_id
        accounts = {}
        ids = []
        with transaction.atomic():
            org = m.Organization.objects.create(name=prefix + ' Synthetic shared payer')
            a = m.Department.objects.create(organization=org, name=prefix + '-AUTHORIZED', organization_pays=True)
            b = m.Department.objects.create(organization=org, name=prefix + '-FOREIGN', organization_pays=True)
            for name, deps, role in [('owner', [a], 'owner'), ('dual_owner', [a, b], 'owner'),
                    ('manager', [a], 'manager'), ('author_a', [a], 'clinician'),
                    ('author_b', [b], 'clinician'), ('admin', [], None)]:
                email = f'{args.run_id}-{name}@synthetic.quillmd.invalid'
                password = secrets.token_urlsafe(32)
                user = m.User.objects.create_user(username=email, email=email, password=password,
                    verified_at=timezone.now(), is_staff=name == 'admin')
                ids.append(user.pk)
                for dept in deps:
                    m.Membership.objects.create(user=user, department=dept, role=role)
                accounts[name] = {'email': email, 'password': password, 'id': str(user.pk)}
                if name == 'admin':
                    device = TOTPDevice.objects.create(user=user, name='Synthetic served authorization', confirmed=True)
                    accounts[name]['totp_key_hex'] = device.key
                audit(user, 'synthetic.authorization_fixture_account', user.pk, run_id=args.run_id)
            # Fixed synthetic amounts, no welcome grant, payment or provider settlement.
            wallet = m.Wallet.objects.create(organization=org, kind='paid', balance='87.95', reserved='6.30')
            m.LedgerEntry.objects.create(wallet=wallet, amount='88.01', kind='funding', key=prefix + ':funding',
                description=prefix + ' SYNTHETIC_FIXED_FINANCIAL_FIXTURE', balance_after='88.01')
            jobs = {}; encounters = {}; forbidden = [b.name, accounts['author_b']['email'], '$87.95', '$6.30']
            from docx import Document
            import io
            doc = Document(); doc.add_paragraph('Synthetic authorization fixture; no patient data.')
            stream = io.BytesIO(); doc.save(stream); blob = stream.getvalue()
            balance = __import__('decimal').Decimal('88.01')
            for tag, dept, account in [('authorized', a, 'author_a'), ('foreign', b, 'author_b')]:
                author = m.User.objects.get(pk=accounts[account]['id'])
                relative = 'authorization-fixtures/' + args.run_id + '-' + tag + '.docx'
                path = private_path(relative); path.parent.mkdir(mode=0o700, exist_ok=True)
                write_new(path, blob)
                template = m.Template.objects.create(department=dept, name=prefix + '-' + tag,
                    format='docx', original_name='synthetic-authorization.docx', original_path=relative,
                    sha256=sha(blob), created_by=author)
                version = m.TemplateVersion.objects.create(template=template, number=1, fields=[], created_by=author)
                patient = m.Patient.objects.create(department=dept, display_name='SYNTHETIC AUTHORIZATION ' + tag,
                    reference=prefix + '-' + tag, created_by=author)
                encounter = m.Encounter.objects.create(department=dept, patient=patient, template_version=version,
                    notes='SYNTHETIC_AUTH_NOTES_' + tag, service_date=timezone.localdate(), created_by=author,
                    status='finalized', finalized_by=author, finalized_at=timezone.now(),
                    export_path=relative, export_sha256=sha(blob))
                encounters[tag] = encounter
                for kind in ['generation', 'transcription', 'mapping', 'settled']:
                    scope = {'mapping_version': version} if kind == 'mapping' else {'encounter': encounter}
                    config = {'mode': 'fixture'}
                    if kind == 'mapping':
                        config.update(source_sha256=template.sha256, department_id=str(dept.pk),
                                      mapping_version_id=str(version.pk))
                    report['fixture_stage'] = tag + ':' + kind
                    job = m.Job.objects.create(**scope, user=author,
                        kind=kind if kind != 'settled' else 'generation', payer='organization:' + str(org.pk),
                        request_key=prefix + ':' + tag + ':' + kind,
                        state='succeeded' if kind == 'settled' else 'reconciliation', config=config)
                    jobs[tag, kind] = job
                    if kind != 'settled':
                        m.Reservation.objects.create(job=job, wallet=wallet,
                            amount='.13' if tag == 'authorized' else '1.97')
                    else:
                        balance -= __import__('decimal').Decimal('.03')
                        m.LedgerEntry.objects.create(wallet=wallet, job=job, amount='-.03', kind='usage',
                            key=prefix + ':' + tag + ':usage', description=prefix + '_' + tag.upper() + '_LEDGER',
                            balance_after=balance)
                        usage = m.Usage.objects.create(job=job, user=author, department=dept, organization=org,
                            payer=job.payer, provider=prefix + '_' + tag.upper() + '_PROVIDER',
                            actual_cost='.02', charged_cost='.03', simulated=True)
                        if tag == 'foreign':
                            forbidden += [str(job.pk), usage.provider]
                if tag == 'foreign':
                    forbidden += [str(encounter.pk), str(patient.pk), 'SYNTHETIC_AUTH_NOTES_foreign']
                    forbidden += [str(jobs[tag, kind].pk) for kind in ['generation', 'transcription', 'mapping']]
            write_new(out / 'credentials.json', accounts)
        created = ids
        report['fixture_ids'] = {'organization': str(org.pk), 'departments': [str(a.pk), str(b.pk)],
            'users': [str(pk) for pk in ids], 'jobs': [str(job.pk) for job in jobs.values()],
            'encounters': [str(e.pk) for e in encounters.values()], 'file_sha256': sha(blob)}
        expected = fingerprints()
        report['after_fixture_financial'] = expected
        owner = served.login(accounts['owner'], 9160)
        dual = served.login(accounts['dual_owner'], 9160)
        manager = served.login(accounts['manager'], 9160)
        foreign = served.login(accounts['author_b'], 9160)
        require(protected_file(out / 'credentials.json'), 'credential_route_check')
        page = served.expect(owner, 9160, '/patients/', 200, label='doctor_positive_and_csrf')
        csrf = re.search(rb'name="csrfmiddlewaretoken" value="([^"]+)"', page)
        require(csrf is not None, 'authenticated_csrf_missing')
        for query in ['', '?q=FOREIGN', '?q=' + str(jobs['foreign', 'mapping'].pk), '?usage_page=100&ledger_page=100']:
            body = served.expect(owner, 9160, '/billing/' + query, 200, label='owner_scoped_billing').decode()
            # A reflected filter value supplied by the probe is not a disclosure.
            # Strip that one search input; retain every result/aggregate/link.
            body = re.sub(r'<input[^>]*\bname="q"[^>]*>', '', body)
            require(all(marker not in body for marker in forbidden), 'foreign_billing_metadata_disclosed')
            require(body.count('data-held-request') == 3, 'held_count_leak_or_omission')
            if not query or query.startswith('?usage_page'):
                require('configured cost $0.02' in body and 'original charges $0.03' in body,
                        'owner_aggregate_scope_wrong')
        body = served.expect(dual, 9160, '/billing/', 200, label='second_owner_positive').decode()
        require(body.count('data-held-request') == 6 and accounts['author_b']['email'] in body
            and 'configured cost $0.04' in body and 'original charges $0.06' in body,
            'explicit_second_owner_missing')
        body = served.expect(manager, 9160, '/billing/', 200, label='nonowner_financial_denial').decode()
        require('data-held-request' not in body and accounts['author_a']['email'] not in body,
                'manager_inherited_owner_financial_access')
        for kind in ['generation', 'transcription', 'mapping', 'settled']:
            allowed = '/billing/jobs/' + str(jobs['authorized', kind].pk) + '/'
            body = served.expect(owner, 9160, allowed, 200, label='owned_department_detail').decode()
            require(accounts['author_a']['email'] in body and 'SYNTHETIC_AUTH_NOTES' not in body
                    and '$87.95' not in body and '$6.30' not in body, 'detail_overdisclosure')
            target = '/billing/jobs/' + str(jobs['foreign', kind].pk) + '/'
            for method in ['GET', 'HEAD']:
                for host in ['127.0.0.1:9160', 'localhost:9160', 'app.quillmd.com', 'ADMIN.QUILLMD.COM.:9160']:
                    served.expect(owner, 9160, target, 404, host=host, method=method, label='foreign_detail_denied')
            served.expect(owner, 9160, target, 404, method='POST',
                          data={'csrfmiddlewaretoken': csrf[1].decode()}, label='foreign_detail_valid_csrf_post_denied')
            served.expect(dual, 9160, target, 200, label='second_owner_detail_positive')
            served.expect(manager, 9160, allowed, 404, label='manager_detail_denied')
        for target in ['/api/encounters/{}/', '/encounters/{}/', '/encounters/{}/export/']:
            body = served.expect(owner, 9160, target.format(encounters['authorized'].pk), 200,
                                 label='authorized_clinical_or_export')
            if target.endswith('/export/'):
                require(sha(body) == sha(blob), 'authorized_export_hash_mismatch')
            served.expect(owner, 9160, target.format(encounters['foreign'].pk), 404, label='foreign_clinical_denied')
        served.expect(owner, 9160, '/jobs/' + str(jobs['foreign', 'generation'].pk) + '/result/', 404,
                      label='foreign_job_result_denied')
        for path in ['/billing/', '/console/', '/console/usage.csv',
                     '/console/jobs/' + str(jobs['foreign', 'generation'].pk) + '/']:
            served.expect(owner, 9161, path, 404, label='nonadmin_alternate_surface_denied')
        # Existing clinical revocation policy: own financial history survives.
        with transaction.atomic():
            m.Membership.objects.filter(user_id=accounts['author_b']['id']).update(active=False)
            audit(None, 'synthetic.authorization_membership_revoked', accounts['author_b']['id'], run_id=args.run_id)
        body = served.expect(foreign, 9160, '/billing/', 200, label='revoked_personal_history_positive').decode()
        require(body.count('data-held-request') == 3, 'personal_history_lost_after_revocation')
        served.expect(foreign, 9160, '/billing/jobs/' + str(jobs['foreign', 'generation'].pk) + '/', 200,
                      label='revoked_own_financial_positive')
        served.expect(foreign, 9160, '/api/encounters/' + str(encounters['foreign'].pk) + '/', 404,
                      label='revoked_clinical_denial')
        bare = served.login(accounts['admin'], 9161, expect=False)
        served.expect(bare, 9161, '/console/', 302, label='password_only_admin_not_authenticated')
        time.sleep(2.1)  # Respect the actual authenticator's failure throttle.
        key = bytes.fromhex(accounts['admin']['totp_key_hex'])
        admin = served.login(accounts['admin'], 9161, otp=str(totp(key)).zfill(6))
        served.expect(admin, 9161, '/console/', 200, label='admin_mfa_positive')
        served.expect(admin, 9161, '/console/usage.csv', 200, label='admin_mfa_export_positive')
        for caller in [served.client(), owner, admin]:
            for path in ['/console', '/console/', '/console/audit', '/console/usage.csv']:
                served.expect(caller, 9160, path, 404, label='doctor_console_denied')
        for port, host in [(9160, 'admin.quillmd.com'), (9160, 'ADMIN.QUILLMD.COM.:9160'),
                           (9161, 'app.quillmd.com'), (9161, 'APP.QUILLMD.COM.:9161')]:
            for path in ['/login/', '/health/', '/console', '/console/']:
                served.expect(admin, port, path, 404, host=host, label='wrong_public_host_denied')
        for port, host in [(9160, 'app.quillmd.com'), (9161, 'admin.quillmd.com')]:
            served.expect(served.client(), port, '/login/', 200, host=host, label='correct_public_host_positive')
        report['after_requests_financial'] = fingerprints()
        require(expected == report['after_requests_financial'], 'served_checks_changed_financial_history')
        require(not m.AuditEvent.objects.filter(actor_id=accounts['owner']['id'], action='billing.job_read',
                target__in=[str(jobs['foreign', kind].pk) for kind in ['generation', 'transcription', 'mapping', 'settled']]).exists(),
                'denied_financial_read_audited_as_allowed')
        report['status'] = 'passed'
    except BaseException as ex:
        report['status'] = 'failed'
        report['failure_type'] = type(ex).__name__
        report['failure_frames'] = [{'file': frame.filename, 'line': frame.lineno, 'function': frame.name}
                                    for frame in traceback.extract_tb(ex.__traceback__)]
        cause = getattr(ex, '__cause__', None)
        if getattr(cause, 'sqlstate', None):
            report['database_sqlstate'] = cause.sqlstate
            primary = getattr(getattr(cause, 'diag', None), 'message_primary', '') or ''
            report['database_message_sha256'] = sha(primary.encode())
            if primary == 'Mapping job source and tenant binding mismatch':
                report['database_guard_refusal'] = primary
        # Our own controlled assertion messages contain no credentials/payload.
        if isinstance(ex, RuntimeError):
            report['failure_reason'] = str(ex)
        raise
    finally:
        if created:
            with transaction.atomic():
                m.User.objects.filter(pk__in=created).update(is_active=False, session_version=F('session_version') + 1)
                m.Membership.objects.filter(user_id__in=created).update(active=False)
                for pk in created:
                    audit(None, 'synthetic.authorization_fixture_retired', pk, run_id=args.run_id)
            report['retired_accounts'] = list(m.User.objects.filter(pk__in=created)
                .values('id', 'is_active', 'session_version'))
            require(all(not row['is_active'] and row['session_version'] >= 1 for row in report['retired_accounts']),
                    'fixture_retirement_failed')
        report['at_exit_financial'] = fingerprints()
        if not created and report.get('before_fixture_financial'):
            report['failed_seed_financial_rollback_verified'] = (
                report['before_fixture_financial'] == report['at_exit_financial'])
        report['request_count'] = served.requests
        report['elapsed_seconds'] = round(time.monotonic() - served.started, 3)
        report['http_evidence'] = served.records
        write_new(out / 'result.json', report)
        print(json.dumps({'run_id': args.run_id, 'status': report['status'], 'requests': served.requests,
            'provider_requests': 0, 'evidence': str(out / 'result.json'), 'credentials_recorded': False}))


if __name__ == '__main__':
    try:
        main()
    except BaseException as ex:
        # No generic traceback: connection/HTTP exceptions can contain secrets.
        print(json.dumps({'status': 'refused_or_failed', 'error_type': type(ex).__name__}), file=sys.stderr)
        raise SystemExit(1)
