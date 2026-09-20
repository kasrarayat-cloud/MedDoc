#!/usr/bin/env python3
"""Cited private-preview activation; restores the prior gate on failure."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
DECL = 'docs/foundation/mutations/20260920-quillmd-preview-form.md'
PREVIOUS = '280ec54283abd452f59b129f57a6a17135532430'
NGINX = Path('/etc/nginx/sites-available/quillmd-email-preview')
ORIGIN = 'https://app.quillmd.com:9443'
sys.path.insert(0, str(APP))
from ops import source_module, private_storage, preview_activation, preview_http
from dotenv import dotenv_values
from io import StringIO
import httpx


def require(value, message):
    if not value:
        raise RuntimeError(message)


def output(command, **kwargs):
    return subprocess.check_output(command, stderr=subprocess.PIPE, timeout=90, **kwargs)


def text(command):
    return output(command, text=True).strip()


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    data = value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def private(path):
    require(path.resolve() == path, 'Protected path is not canonical.')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as handle:
        info = os.fstat(handle.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == 0o600, 'Protected file permissions changed.')
        return handle.read()


def nginx_replace(expected, content, helper):
    """Root helper can replace only this one named file after byte comparison."""
    script = '''import os,stat
from pathlib import Path
p=Path('/available/quillmd-email-preview');expected=EXPECTED;content=CONTENT
s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1 and stat.S_IMODE(s.st_mode)==0o644 and p.read_bytes()==expected
q=p.with_name('quillmd-email-preview.form-pending')
fd=os.open(q,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
with os.fdopen(fd,'wb') as f:f.write(content);f.flush();os.fsync(f.fileno())
os.chmod(q,0o644);assert p.read_bytes()==expected;os.replace(q,p)
assert p.read_bytes()==content and p.stat().st_uid==0 and stat.S_IMODE(p.stat().st_mode)==0o644
'''.replace('EXPECTED', repr(expected)).replace('CONTENT', repr(content))
    output(['docker', 'run', '--rm', '-i', '--log-driver=none', '--pull=never', '--network=none',
            '--read-only', '--cap-drop=ALL', '--mount', 'type=bind,src=/etc/nginx/sites-available,dst=/available',
            helper, 'python', '-B', '-'], input=script.encode())


def nginx_reload():
    output(['sudo', '-n', '/usr/sbin/nginx', '-t'])
    output(['sudo', '-n', '/usr/bin/systemctl', 'reload', 'nginx'])


def audit_rows(export):
    rows = json.loads(text(export.PSQL + ["SELECT coalesce(json_object_agg(id::text,md5(to_jsonb(t)::text)), '{}'::json) FROM core_auditevent t"]))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    require(os.environ.get('RULED_MUTATION_DECLARATION') == DECL, 'Committed mutation declaration is required.')
    require(Path.cwd() == ROOT and text(['git', 'branch', '--show-current']) == 'main', 'Use permanent main.')
    require(re.fullmatch('[a-f0-9]{40}', args.target) and text(['git', 'rev-parse', 'HEAD']) == args.target,
            'Target must name the exact permanent source revision.')
    require(not text(['git', 'status', '--porcelain', '--untracked-files=no']), 'Tracked source must be clean.')
    require(re.fullmatch('[a-z0-9][a-z0-9-]{0,48}', args.attempt), 'Use a unique bounded attempt label.')
    output(['bash', 'scripts/check-citation.sh', args.target])
    output(['bash', 'scripts/check-cotenants.sh'])
    changes = text(['git', 'diff', '--name-only', PREVIOUS, args.target, '--', 'rebuild/core', 'rebuild/quillmd']).splitlines()
    allowed = {'rebuild/core/preview_access.py', 'rebuild/core/preview_logging.py', 'rebuild/core/middleware.py', 'rebuild/core/email_backend.py',
               'rebuild/quillmd/settings.py', 'rebuild/quillmd/urls.py'}
    require(all(path in allowed or path.startswith('rebuild/core/tests/') for path in changes),
            'Unexpected application source change outside the preview repair.')
    out = APP / '.runtime' / ('preview-form-activation-' + args.attempt)
    out.mkdir(mode=0o700)
    require(out.resolve() == out and out.stat().st_uid == os.getuid(), 'Invalid evidence directory.')
    original = private(APP / '.env')
    values = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    previous = values.get('QUILLMD_RELEASE_SHA')
    require(previous in {PREVIOUS, args.target} and values.get('QUILLMD_APP_BASE_URL') == ORIGIN
            and values.get('QUILLMD_PREVIEW_AUTH_ENABLED', '0') == '0',
            'Unexpected previous environment or private origin.')
    require(values.get('QUILLMD_TRUST_PROXY') == '1', 'Trusted private HTTPS proxy is required.')
    updated = preview_activation.environment(original, previous, args.target, True)
    rollback_env = preview_activation.environment(updated, args.target, args.target, False)
    write(out / 'environment-before.secrets.env', original)
    write(out / 'environment-rollback.secrets.env', rollback_env)
    prior_nginx = NGINX.read_bytes()
    require(b'auth_basic "QuillMD private email verification";' in prior_nginx, 'Prior Basic gate differs from expectation.')
    require(prior_nginx == output(['git', 'show', PREVIOUS + ':rebuild/deploy/email-private-https.conf']),
            'Dedicated nginx file differs from the reviewed previous release.')
    next_nginx = (APP / 'deploy/email-private-https.conf').read_bytes()
    require(b'auth_basic ' not in next_nginx and b'proxy_set_header X-QuillMD-Preview "1";' in next_nginx,
            'New proxy does not select the form gate.')
    write(out / 'nginx-before.conf', prior_nginx)
    helper = text(['docker', 'image', 'inspect', 'python:3-slim', '--format', '{{.Id}}'])
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper), 'Pinned local helper image unavailable.')
    word = source_module.load('preview_word', ROOT / 'scripts/activate-word-beta.py')
    export = source_module.load('preview_inventory', ROOT / 'scripts/activate-word-export.py')
    identity = source_module.load('preview_identity', ROOT / 'scripts/activate-os-identity.py')
    require(text(export.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Outstanding jobs must finish before private activation.')
    units = {name: hashlib.sha256((Path('/etc/systemd/system') / name).read_bytes()).hexdigest() for name in word.UNITS}
    policy = hashlib.sha256(output(['systemctl', 'cat', *word.UNITS])).hexdigest()
    other_sites = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in Path('/etc/nginx/sites-enabled').glob('*')
                   if path.resolve() != NGINX}
    result = {'started_at': stamp(), 'previous_release': previous, 'target': args.target,
              'complete': False, 'stage': 'before-stop', 'source_changes': changes,
              'rollback_available': True, 'rollback_kind': 'Prior Basic protection on the same reviewed code; no data rollback.',
              'unit_hashes': units, 'other_sites': other_sites,
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'provider_calls': 0, 'emails_sent': 0, 'schema_mutations': 0}
    result['old_proofs'] = identity.verify_live(previous, private_storage)
    write(out / 'before.json', result)
    try:
        word.systemd('stop', helper)
        result['stage'] = 'stopped'
        names = export.tables()
        before = export.fingerprints(names)
        original_audit = audit_rows(export)
        schema, constraints, indexes = word.schema(), export.constraints(), export.indexes()
        storage = {name: private_storage.inventory(Path('/var/lib/quillmd') / name) for name in ('files', 'mail')}
        result.update(database_before=before, audit_rows_before=original_audit, schema_before=schema, constraints_before=constraints,
                      indexes_before=indexes, storage_before=storage)
        write(out / 'stopped-baseline.json', result)
        preview_activation.replace_environment(APP / '.env', original, updated)
        word.systemd('start', helper)
        result['stage'] = 'application-started-behind-prior-edge'
        for attempt in range(45):
            try:
                result['proofs'] = identity.verify_live(args.target, private_storage)
                result['interfaces'] = identity.verify_interfaces()
                break
            except Exception:
                if attempt == 44:
                    raise
                time.sleep(1)
        require(export.fingerprints(names) == before and export.tables() == names, 'Database rows changed across service activation.')
        require(word.schema() == schema and export.constraints() == constraints and export.indexes() == indexes,
                'Database schema changed across activation.')
        require({name: private_storage.inventory(Path('/var/lib/quillmd') / name) for name in storage} == storage,
                'Private files changed across activation.')
        result['all_rows_files_schema_preserved_before_verification'] = True
        write(out / 'preserved-before-public-probes.json', result)
        # Prove the application gate exists before removing the old proxy gate.
        with httpx.Client(base_url='http://127.0.0.1:9130', trust_env=False, follow_redirects=False, timeout=15) as client:
            response = client.get('/health/', headers={'Host': 'app.quillmd.com:9443',
                'X-Forwarded-Proto': 'https', 'X-QuillMD-Preview': '1', 'X-Real-IP': '127.0.0.1'})
            preview_http.sign_in_path(response)
        result['application_gate_proved_before_proxy_change'] = True
        nginx_replace(prior_nginx, next_nginx, helper)
        nginx_reload()
        result['stage'] = 'form-gate-active'
        gate = json.loads(private(APP / '.runtime/email-private-access.json'))
        require(gate['origin'] == ORIGIN, 'Protected gate origin changed.')
        with httpx.Client(base_url=ORIGIN, trust_env=False, follow_redirects=False, verify=True, timeout=15) as client:
            preview_http.authenticate(client, {key: gate[key] for key in ('username', 'password')})
            response = client.get('/health/')
            require(response.status_code == 200 and response.json() == {'status': 'ok', 'data_mode': 'synthetic-only',
                    'surface': 'doctor', 'release': args.target}, 'Actual HTTPS release differs from target.')
            result['actual_https_health'] = response.json()
            preview_http.sign_out(client)
            preview_http.sign_in_path(client.get('/health/'))
        require({name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in other_sites} == other_sites,
                'An unrelated nginx site changed.')
        require({name: hashlib.sha256((Path('/etc/systemd/system') / name).read_bytes()).hexdigest() for name in units} == units
                and hashlib.sha256(output(['systemctl', 'cat', *word.UNITS])).hexdigest() == policy,
                'Private service policy changed.')
        require(private(APP / '.env') == updated, 'Protected environment changed unexpectedly.')
        result['database_after_verification'] = export.fingerprints(names)
        mutable = {'django_session', 'core_auditevent', 'core_loginattempt'}
        require(all(result['database_after_verification'][name] == before[name] for name in names if name not in mutable),
                'A non-session/audit/rate-limit table changed during preview checks.')
        result['allowed_verification_tables'] = sorted(mutable)
        current_audit = audit_rows(export)
        require(all(current_audit.get(key) == value for key, value in original_audit.items()),
                'An existing audit row changed or disappeared during preview checks.')
        result['existing_audit_rows_preserved'] = len(original_audit)
        result['unit_policies_unchanged'] = True
        output(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', public_maintenance_preserved=True)
    except Exception as error:
        result['error_class'] = type(error).__name__
        result['failed_stage'] = result['stage']
        # Restore the independent old gate first, even if the new app is down.
        try:
            current_nginx = NGINX.read_bytes()
            require(current_nginx in {prior_nginx, next_nginx}, 'Dedicated nginx changed independently; preserve it for diagnosis.')
            if current_nginx == next_nginx:
                nginx_replace(next_nginx, prior_nginx, helper)
                nginx_reload()
            # A failed subprocess may already have changed state. Inspect bytes,
            # then stop/start all three idempotently rather than trusting flags.
            current_env = private(APP / '.env')
            require(current_env in {original, updated, rollback_env}, 'Environment changed independently; preserve it for diagnosis.')
            word.systemd('stop', helper)
            preview_activation.replace_environment(APP / '.env', current_env, rollback_env)
            word.systemd('start', helper)
            for attempt in range(45):
                try:
                    result['rollback_proofs'] = identity.verify_live(args.target, private_storage)
                    break
                except Exception:
                    if attempt == 44:
                        raise
                    time.sleep(1)
            with httpx.Client(base_url=ORIGIN, trust_env=False, follow_redirects=False, verify=True, timeout=15) as client:
                response = client.get('/health/')
                require(response.status_code == 401 and response.headers.get('www-authenticate') ==
                        'Basic realm="QuillMD private email verification"', 'Old independent gate was not restored.')
            result['rollback_protection_restored'] = True
            result['rollback_running_revision'] = args.target
        except Exception as rollback_error:
            result['rollback_error_class'] = type(rollback_error).__name__
        raise
    finally:
        result['finished_at'] = stamp()
        write(out / 'result.json', result)
    print('Private preview form activated; original rows/files/schema and public maintenance preserved.')


if __name__ == '__main__':
    main()
