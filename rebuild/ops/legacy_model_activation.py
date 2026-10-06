"""Preserving private legacy-model configuration act; no provider calls or migrations.

The default only reports the qualification contract. Execution requires a separately
completed, committed declaration, exact CI, protected exact-source QA evidence and a
current authenticated backup. The prospective declaration deliberately admits no act.
"""
import argparse
from collections import Counter
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

from dotenv import dotenv_values

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
RUNTIME = APP / '.runtime'
SOURCE = Path(__file__).resolve().parents[2]
BASELINE = 'dedac1625032e32c7a149e6771be22e26c307eb1'
DECL = 'docs/foundation/mutations/20261006-quillmd-legacy-model-demo.md'
SELF = 'rebuild/ops/legacy_model_activation.py'
ALLOWED = frozenset({SELF, DECL, 'rebuild/ops/test_legacy_model_activation.py',
                     'scripts/activate-legacy-model-config.py', 'rebuild/templates/encounter_form.html',
                     'rebuild/ops/test_link_worktree_venv.py', 'scripts/link-worktree-venv.sh',
                     'scripts/setup-worktree.sh',
                     'docs/foundation/mutations/20261006-quillmd-owner-legacy-sonnet55-qa.md',
                     'docs/foundation/mutations/20261006-quillmd-owner-voice-duration-adjudication.md',
                     'docs/rebuild/owner-doctor-test-guide-20261006.html'})
DEPENDENCIES = ('rebuild/ops/managed_helper.py', 'rebuild/ops/private_storage.py',
                'rebuild/ops/backup_restore.py', 'rebuild/ops/email_activation.py',
                'rebuild/ops/activation_exclusion.py', 'scripts/check-citation.sh',
                'scripts/run-ruled-mutation.sh', 'scripts/lib/declaration.sh',
                'scripts/lib/run-watched.sh')
UNITS = tuple('quillmd-fresh-' + surface + '.service' for surface in ('doctor', 'admin', 'worker'))
OPERATIONS = tuple('quillmd-fresh-' + operation + '.service' for operation in
                   ('backup', 'offsite', 'backup-alerts', 'operations-publisher'))
LOCKS = ('backup-monitor/capture.lock', 'automatic-offsite/execution.lock', 'backup-alerts/monitor.lock')
MODEL_VALUES = {'QUILLMD_AI_MODEL': 'claude-sonnet-5-5', 'QUILLMD_AI_INPUT_RATE': '2',
                'QUILLMD_AI_OUTPUT_RATE': '10', 'QUILLMD_AI_CACHED_RATE': '0.20'}
ASSIGNMENT = re.compile(rb'(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=')
PROFILE = {'max_tokens': 6000, 'timeout_seconds': 60, 'max_retries': 0,
           'thinking': 'provider_default', 'effort': 'provider_default', 'inference_geo': 'provider_default'}
OUTCOMES = frozenset({'soap', 'voice', 'custom_word', 'clinical_refutation', 'profile_bounds',
                      'billing', 'provider_defaults'})
EVIDENCE_ROLES = frozenset({'request', 'response', 'profile', 'billing', 'clinical', 'workflows'})
TABLES = frozenset('auth_group auth_group_permissions auth_permission core_auditevent core_code '
                  'core_codeset core_codesuggestion core_costreconciliation core_department core_encounter '
                  'core_invitation core_job core_ledgerentry core_loginattempt core_membership core_organization '
                  'core_patient core_payment core_platformcost core_providerreceipt core_refund core_reservation '
                  'core_servicehealth core_template core_templateversion core_usage core_user core_user_groups '
                  'core_user_user_permissions core_verification core_wallet core_webhookevent django_content_type '
                  'django_migrations django_session otp_totp_totpdevice'.split())
RESTORE = RUNTIME / 'recovery-custody-handoff-20260922/return-evidence/independent-key-restore/result.json'
RESTORE_SHA = 'f2df7c56486b5d09de254ee7ab69c30697ca2b6487b84b700fe06c7fa7f49d0f'
KEY = RUNTIME / 'backup-secrets/fresh-backup-current-20260917.key'
ROLES = RUNTIME / 'db-role-secrets/fresh-db-roles.json'
COMPLETION_SECONDS = 240


class Refusal(RuntimeError):
    """Fixed operator diagnostic; protected exceptions and payloads are suppressed."""


def require(value, label):
    if not value:
        raise Refusal(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), default=str) + '\n').encode()


def protected(path, limit=1024 * 1024):
    path = Path(path)
    require(path.is_absolute() and path.resolve(strict=True) == path, 'protected_path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == os.getuid()
                and stat.S_IMODE(before.st_mode) == 0o600 and before.st_nlink == 1
                and before.st_size <= limit, 'protected_identity')
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
        require(len(raw) == before.st_size and (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_ctime_ns), 'protected_read_race')
    return raw


def write_new(path, raw):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def render(original, release, *, rollback_values=None):
    require(re.fullmatch('[a-f0-9]{40}', release or '') is not None, 'release_identity')
    require(isinstance(original, bytes) and original.endswith(b'\n'), 'environment_newline')
    before = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    require(before.get('QUILLMD_AI_MODE') == 'live' and before.get('QUILLMD_AI_PROVIDER') == 'anthropic'
            and before.get('QUILLMD_DATA_MODE', 'synthetic') == 'synthetic'
            and before.get('QUILLMD_PREVIEW_AUTH_ENABLED') == '1'
            and before.get('QUILLMD_APP_BASE_URL') == 'https://app.quillmd.com:9443', 'legacy_private_contract')
    for key in ('QUILLMD_V3_FIELD_RELATIONS', 'QUILLMD_V3_HISTORY_CONTEXT', 'QUILLMD_V3_GENERATION_BATCHES',
                'QUILLMD_MAPPING_ASSISTANCE', 'QUILLMD_WM_NARRATIVE'):
        require(before.get(key, '0') == '0', 'alternate_generation_contract')
    values = dict(MODEL_VALUES if rollback_values is None else rollback_values)
    require(set(values) == set(MODEL_VALUES), 'controlled_key_set')
    require(all(isinstance(v, str) and re.fullmatch(r'[a-zA-Z0-9_.-]+', v) for v in values.values()),
            'controlled_serialization')
    expected_model = 'claude-sonnet-4-6' if rollback_values is None else 'claude-sonnet-5-5'
    require(before.get('QUILLMD_AI_MODEL') == expected_model, 'current_model_drift')
    if before.get('QUILLMD_RELEASE_SHA') != release:
        values['QUILLMD_RELEASE_SHA'] = release
    counts, result, unrelated = Counter(), [], []
    for line in original.splitlines(keepends=True):
        match = ASSIGNMENT.match(line)
        key = match[1].decode() if match else None
        if key in values:
            counts[key] += 1
            result.append((key + '="' + values[key] + '"\n').encode())
        else:
            result.append(line)
            unrelated.append(line)
    require(set(values) <= set(counts), 'missing_controlled_assignment')
    require('QUILLMD_RELEASE_SHA' not in values or counts['QUILLMD_RELEASE_SHA'] == 1, 'duplicate_release')
    updated = b''.join(result)
    after = dotenv_values(stream=StringIO(updated.decode()), interpolate=False)
    require(all(after.get(k) == v for k, v in values.items()), 'effective_configuration')
    require({k: v for k, v in before.items() if k not in values}
            == {k: v for k, v in after.items() if k not in values}, 'unrelated_configuration')
    preserved = [line for line in updated.splitlines(keepends=True)
                 if not ((match := ASSIGNMENT.match(line)) and match[1].decode() in values)]
    require(preserved == unrelated, 'unrelated_bytes')
    return updated, {'values': values, 'assignment_counts': dict(counts), 'before_sha256': sha(original),
                     'after_sha256': sha(updated), 'unrelated_sha256': sha(b''.join(unrelated))}


def command(argv, *, cwd=None, timeout=180):
    done = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout)
    require(done.returncode == 0 and len(done.stdout) <= 2 * 1024 * 1024, 'bounded_command_failed')
    return done.stdout


def git(tree, *args):
    return command(['git', '-C', str(tree), *args])


def declaration():
    raw = (SOURCE / DECL).read_bytes()
    marker = '<!-- legacy-model-contract -->\n```json\n'
    text = raw.decode()
    require(text.count(marker) == 1, 'declaration_contract')
    body = text.split(marker, 1)[1].split('\n```', 1)
    require(len(body) == 2, 'declaration_contract_close')
    return raw, json.loads(body[0])


def validate_qualification(value, evidence):
    require(value.get('format') == 1 and value.get('source_sha') == BASELINE
            and value.get('qualified_for_legacy_config_demo') is True
            and value.get('model') == 'claude-sonnet-5-5' and value.get('provider') == 'anthropic'
            and value.get('request_profile') == PROFILE and value.get('rates') == MODEL_VALUES
            and type(value.get('unsafe_findings')) is int and value['unsafe_findings'] == 0
            and all(value.get('outcomes', {}).get(name) is True for name in OUTCOMES)
            and all(value.get(name) is False for name in ('candidate_install', 'patient_admission', 'public_launch')),
            'legacy_qualification_scope')
    require(set(evidence) == EVIDENCE_ROLES, 'qualification_evidence_population')
    request = json.loads(evidence['request'])
    response = json.loads(evidence['response'])
    body = request.get('body_json', request.get('body'))
    require(request.get('url') == 'https://api.anthropic.com/v1/messages' and request.get('method') == 'POST'
            and isinstance(body, dict) and body.get('model') == 'claude-sonnet-5-5'
            and body.get('max_tokens') == 6000 and 'thinking' not in body
            and set(body.get('output_config', {})) == {'format'}
            and body['output_config']['format'].get('type') == 'json_schema'
            and body.get('messages') and body.get('system'), 'actual_legacy_request_profile')
    response_body = response.get('body_json', response.get('body'))
    require(response.get('status_code') == 200 and isinstance(response_body, dict)
            and response_body.get('model') == 'claude-sonnet-5-5'
            and response_body.get('stop_reason') == 'end_turn'
            and re.fullmatch(r'msg_[A-Za-z0-9]+', response_body.get('id', ''))
            and re.fullmatch(r'req_[A-Za-z0-9]+', response.get('request_id', ''))
            and isinstance(response_body.get('usage'), dict), 'actual_legacy_response')
    return {'qualification_sha256': sha(encode(value)), 'request_id': response['request_id'],
            'resource_id': response_body['id'], 'response_model': response_body['model']}


def read_qualification(path, expected):
    require(re.fullmatch('[a-f0-9]{64}', expected or '') is not None, 'qualification_hash_missing')
    require(Path(path).is_relative_to(RUNTIME), 'qualification_runtime_scope')
    raw = protected(path)
    require(sha(raw) == expected, 'qualification_hash')
    value = json.loads(raw)
    entries = value.get('evidence_files')
    require(isinstance(entries, list) and len(entries) == len(EVIDENCE_ROLES), 'qualification_files')
    evidence = {}
    for entry in entries:
        require(set(entry) == {'role', 'path', 'sha256'} and entry['role'] not in evidence
                and entry['role'] in EVIDENCE_ROLES and re.fullmatch('[a-f0-9]{64}', entry['sha256'])
                and Path(entry['path']).is_relative_to(RUNTIME), 'qualification_file_identity')
        blob = protected(entry['path'], 8 * 1024 * 1024)
        require(sha(blob) == entry['sha256'], 'qualification_file_hash')
        evidence[entry['role']] = blob
    result = validate_qualification(value, evidence)
    result['qualification_sha256'] = sha(raw)
    return result


def source_gate(commit, contract, *, executing):
    require(re.fullmatch('[a-f0-9]{40}', commit or '') and SOURCE.is_relative_to(ROOT / '.worktrees')
            and SOURCE.resolve() == SOURCE, 'retained_operator_source')
    require(git(SOURCE, 'rev-parse', 'HEAD').strip().decode() == commit
            and not git(SOURCE, 'status', '--porcelain', '--untracked-files=no').strip(), 'operator_source_drift')
    git(SOURCE, 'merge-base', '--is-ancestor', BASELINE, commit)
    changed = set(git(SOURCE, 'diff', '--name-only', BASELINE, commit).decode().splitlines())
    require(changed <= ALLOWED and {SELF, DECL} <= changed, 'unrelated_source_passenger')
    for relative in DEPENDENCIES:
        require((SOURCE / relative).read_bytes() == git(SOURCE, 'show', BASELINE + ':' + relative),
                'dependency_byte_identity')
    head = git(ROOT, 'rev-parse', 'HEAD').strip().decode()
    require(head in (BASELINE, commit) and git(ROOT, 'branch', '--show-current').strip() == b'main'
            and not git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'shared_deploy_surface_drift')
    # All serving Python/Word/settings/prompt bytes stay identical; only the doctor copy may change.
    for relative in git(ROOT, 'ls-files', 'rebuild').decode().splitlines():
        require((ROOT / relative).read_bytes() == git(ROOT, 'show', head + ':' + relative), 'installed_source_byte_drift')
    if executing:
        require(git(ROOT, 'rev-parse', 'origin/main').strip().decode() == commit,
                'normally_merged_main_target_required')
        require(contract.get('execution_qualified') is True and contract.get('baseline') == BASELINE
                and contract.get('approved_source_paths') == sorted(changed), 'prospective_declaration_refuses_execution')
        require(os.environ.get('RULED_MUTATION_DECLARATION') == DECL, 'normal_ruled_door_required')
        declared_commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
        require(git(SOURCE, 'log', '-1', '--format=%H', '--', DECL).strip().decode() == declared_commit
                and git(SOURCE, 'show', declared_commit + ':' + DECL) == (SOURCE / DECL).read_bytes(),
                'committed_declaration_identity')
        command(['bash', str(SOURCE / 'scripts/check-citation.sh'), commit], cwd=SOURCE)
        command(['bash', str(SOURCE / 'scripts/check-citation.sh'), BASELINE], cwd=SOURCE)
    return {'operator_commit': commit, 'shared_head': head, 'changed_paths': sorted(changed)}


def modules():
    from . import activation_exclusion, backup_restore, email_activation, managed_helper, private_storage
    return activation_exclusion, backup_restore, email_activation, managed_helper, private_storage


class Host:
    def __init__(self, managed):
        self.managed = managed

    def helper(self, code, timeout=170):
        argv = ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network', 'none',
                '--pid=host', '--mount', 'type=bind,src=/,dst=/host,readonly', self.managed.IMAGE, 'python', '-B', '-']
        return self.managed.run_helper(argv, input=code.encode(), timeout=timeout).stdout

    def state(self, unit):
        require(unit in UNITS + OPERATIONS, 'unit_read_allowlist')
        properties = 'ActiveState,SubState,MainPID,FragmentPath,DropInPaths,UnitFileState,ExecMainStartTimestampMonotonic'
        raw = command(['systemctl', 'show', unit, '--property=' + properties]).decode()
        return dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)

    def service(self, action, unit):
        require(action in ('start', 'stop') and unit in UNITS, 'unit_mutation_allowlist')
        code = "import os,subprocess\nos.chroot('/host');os.chdir('/')\nsubprocess.run(" + repr(
            ['systemctl', action, unit]) + ",check=True,timeout=155,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
        self.helper(code)

    def configuration(self):
        code = '''import os,json,hashlib,pathlib,stat
try:
 roots=(pathlib.Path('/host/etc/systemd/system'),pathlib.Path('/host/etc/nginx'),pathlib.Path('/host/etc/ssh'))
 paths=[pathlib.Path('/host/opt/meddoc-pro/Caddyfile')]
 for root in roots:
  info=root.lstat()
  assert stat.S_ISDIR(info.st_mode) and not root.is_symlink()
  paths.append(root)
  paths.extend(sorted(root.rglob('*')))
 result={}
 for path in paths:
  info=path.lstat();name=str(path)[5:]
  row={'uid':info.st_uid,'gid':info.st_gid,'mode':stat.S_IMODE(info.st_mode),'device':info.st_dev,'inode':info.st_ino}
  if stat.S_ISLNK(info.st_mode): row['link']=os.readlink(path)
  elif stat.S_ISDIR(info.st_mode): row['directory']=True
  elif stat.S_ISREG(info.st_mode): row['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
  else: raise ValueError()
  result[name]=row
 print(json.dumps(result,sort_keys=True))
except Exception: raise SystemExit(1)
'''
        return json.loads(self.helper(code, 30))

    def effective_worker(self):
        state = self.state(UNITS[2])
        require(state.get('ActiveState') == 'active' and int(state.get('MainPID', '0')) > 0, 'worker_not_active')
        pid = int(state['MainPID'])
        code = '''import json,pathlib
try:
 pid=PID
 root=pathlib.Path('/host/proc')/str(pid)
 command=root.joinpath('cmdline').read_bytes().replace(b'\\0',b' ').decode().strip()
 assert command.endswith('manage.py worker') and command.startswith('/opt/meddoc-pro/rebuild/.venv/bin/python ')
 assert '/quillmd-fresh-worker.service' in root.joinpath('cgroup').read_text()
 keys=('QUILLMD_AI_MODE','QUILLMD_AI_PROVIDER','QUILLMD_AI_MODEL','QUILLMD_AI_INPUT_RATE','QUILLMD_AI_OUTPUT_RATE','QUILLMD_AI_CACHED_RATE','QUILLMD_RELEASE_SHA','QUILLMD_DATA_MODE','QUILLMD_PREVIEW_AUTH_ENABLED')
 values={}
 for item in root.joinpath('environ').read_bytes().split(b'\\0'):
  key,sep,value=item.partition(b'=')
  if sep and key.decode() in keys: values[key.decode()]=value.decode()
 print(json.dumps({'pid':pid,'values':values},sort_keys=True))
except Exception: raise SystemExit(1)
'''.replace('PID', str(pid))
        result = json.loads(self.helper(code, 30))
        require(self.state(UNITS[2]) == state, 'worker_identity_race')
        return result


@contextmanager
def operation_locks():
    with ExitStack() as stack:
        for relative in ('legacy-model-activation.lock', *LOCKS):
            path = RUNTIME / relative
            require(path.parent.resolve() == path.parent and path.parent.is_dir(), 'operation_lock_parent')
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                    and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1, 'operation_lock_identity')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def database(backup, files):
    import psycopg
    from psycopg import sql
    opts = backup.source_options(APP, ROLES)
    with psycopg.connect(**opts, autocommit=True) as conn:
        conn.execute("SET timezone='UTC'")
        conn.execute("SET datestyle='ISO, MDY'")
        conn.execute("SET statement_timeout='90s'")
        conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        query = lambda statement: conn.execute(statement).fetchall()
        def copy_hash(statement):
            digest = hashlib.sha256()
            with conn.cursor().copy(statement) as stream:
                for chunk in stream:
                    digest.update(chunk)
            return digest.hexdigest()
        rows = backup.fingerprint(query, copy_hash)
        require(set(rows) == TABLES, 'baseline_table_population')
        pending = query("SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')")[0][0]
        held = query("SELECT count(*) FROM core_reservation WHERE state='held'")[0][0]
        require(pending == held == 0, 'pending_or_unknown_provider_work')
        invariants = backup.invariant_counts(query)
        reaper = query("""SELECT details->>'path' FROM core_auditevent a WHERE action='voice.over_limit_quoted'
            AND created_at<now()-interval '35 minutes' AND created_at>=now()-interval '7 days 40 minutes'
            AND NOT EXISTS(SELECT 1 FROM core_job j WHERE j.input_path=a.details->>'path')""")
        require(not any(path in files for path, in reaper)
                and not any(path.startswith('submissions/') for path in files), 'worker_reaper_targets')
        catalog = {}
        statements = {
            'columns': "SELECT row_to_json(c)::text FROM (SELECT * FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position)c",
            'constraints': "SELECT c.conrelid::regclass::text,c.conname,pg_get_constraintdef(c.oid) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public' ORDER BY 1,2",
            'indexes': "SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY 1,2",
            'functions': "SELECT p.oid::regprocedure::text,pg_get_functiondef(p.oid),p.proacl::text,p.proconfig::text,p.prosecdef,pg_get_userbyid(p.proowner) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.prokind='f' ORDER BY 1",
            'triggers': "SELECT c.relname,t.tgname,pg_get_triggerdef(t.oid),t.tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1,2",
            'relations': "SELECT c.relname,c.relkind,c.relacl::text,c.relrowsecurity,c.relforcerowsecurity,pg_get_userbyid(c.relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' ORDER BY 1",
            'sequences': "SELECT * FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename",
            'policies': "SELECT * FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname",
        }
        for label, statement in statements.items():
            catalog[label] = sha(encode(query(statement)))
        for name, in query("SELECT sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename"):
            statement = sql.SQL('SELECT last_value,is_called FROM public.{}').format(sql.Identifier(name)).as_string()
            catalog['sequence:' + name] = sha(encode(query(statement)))
        conn.execute('COMMIT')
    return {'tables': rows, 'catalog': catalog, 'invariants': invariants, 'pending_jobs': pending, 'held': held}


def inventory(root):
    root = Path(root)
    require(root.resolve(strict=True) == root and root.is_dir() and not root.is_symlink(), 'static_root_identity')
    result = {}
    for path in [root, *sorted(root.rglob('*'))]:
        info = path.lstat()
        require(not path.is_symlink() and (path.is_file() or path.is_dir()), 'static_object')
        result[str(path.relative_to(root))] = {'directory': path.is_dir(), 'mode': stat.S_IMODE(info.st_mode),
                                             'uid': info.st_uid, 'gid': info.st_gid,
                                             'device': info.st_dev, 'inode': info.st_ino,
                                             'sha256': None if path.is_dir() else sha(path.read_bytes())}
    return result


def snapshot(host, backup, storage):
    files = storage.inventory(Path('/var/lib/quillmd/files'))
    return {'database': database(backup, files), 'files': files,
            'mail': storage.inventory(Path('/var/lib/quillmd/mail')),
            'static': inventory(APP / 'staticfiles'), 'configuration': host.configuration()}


def verify_backup(path, expected_hash, snapshot_value, backup):
    require(Path(path).is_relative_to(RUNTIME / 'new-system-backups'), 'backup_destination')
    cipher = backup.key_at(KEY)
    directory, manifest = backup.load_backup(path, cipher)
    require(sha(protected(directory / 'manifest.json.fernet', 8 * 1024 * 1024)) == expected_hash,
            'backup_manifest_identity')
    require(manifest['tables'] == snapshot_value['database']['tables']
            and manifest['invariants'] == snapshot_value['database']['invariants'], 'backup_current_row_coverage')
    for entry in manifest['files']:
        current = snapshot_value['files'].get(entry['path'])
        require(current and current['sha256'] == entry['sha256'] and current['size'] == entry['size'],
                'backup_current_file_coverage')
        backup.decrypt_checked(directory / entry['object'], entry, cipher)
    # Authenticate the dump itself, without writing plaintext to disk or restoring any database.
    backup.decrypt_checked(directory / 'database.dump.fernet', manifest['dump'], cipher)
    require(sha(protected(RESTORE)) == RESTORE_SHA, 'independent_restore_evidence')
    restored = json.loads(protected(RESTORE))
    proof = restored.get('isolated_restore', {})
    require(restored.get('complete') is True and restored.get('independent_key_restore_verified') is True
            and proof.get('complete') is True and proof.get('all_table_hashes_match') is True
            and proof.get('all_file_hashes_match') is True and proof.get('workers_started') == 0,
            'independent_restore_result')
    return {'run_id': manifest['run_id'], 'manifest_cipher_sha256': expected_hash,
            'all_current_tables_covered': True, 'authenticated_dump_and_objects': True,
            'independent_restore_result_sha256': RESTORE_SHA, 'new_restore_performed': False}


def health(release):
    import httpx
    result = []
    for port, surface in ((9130, 'doctor'), (9131, 'admin')):
        response = httpx.get('http://127.0.0.1:' + str(port) + '/health/', timeout=5)
        require(response.status_code == 200, 'private_health_http')
        value = response.json()
        require(value.get('release') == release and value.get('surface') == surface
                and value.get('data_mode') == 'synthetic-only', 'private_health_contract')
        result.append(value)
    for origin in ('https://app.quillmd.com', 'https://admin.quillmd.com'):
        response = httpx.get(origin + '/', timeout=10, follow_redirects=False)
        require(response.status_code == 503 and response.headers.get('retry-after') == '3600'
                and response.headers.get('cache-control') == 'no-store', 'public_maintenance')
    require(httpx.get('https://quillmd.com/', timeout=10, follow_redirects=False).status_code == 200,
            'marketing_status')
    require(httpx.get('https://pro.quillmd.com/', timeout=10, follow_redirects=False).status_code == 410,
            'retired_status')
    from .preview_http import sign_in_path
    with httpx.Client(base_url='https://app.quillmd.com:9443', timeout=10, follow_redirects=False) as client:
        sign_in_path(client.get('/health/'))
    return result


def await_health(release, timeout=30):
    """Read-only startup readiness; policy/HTTP-contract failures are never retried."""
    import httpx
    deadline = time.monotonic() + timeout
    while True:
        try:
            return health(release)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            require(time.monotonic() < deadline, 'startup_http_deadline')
            time.sleep(0.2)


def service_boundary(host, storage, release):
    result = {}
    for unit, surface in zip(UNITS, ('doctor', 'admin', 'worker')):
        state = host.state(unit)
        require(state.get('ActiveState') == 'active' and int(state.get('MainPID', '0')) > 0
                and state.get('FragmentPath') == '/etc/systemd/system/' + unit
                and state.get('DropInPaths') == '' and state.get('UnitFileState') == 'enabled', 'private_service_identity')
        installed = Path('/etc/systemd/system') / unit
        info = installed.lstat()
        require(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1
                and stat.S_IMODE(info.st_mode) == 0o644 and installed.resolve() == installed
                and installed.read_bytes() == (APP / 'deploy' / unit).read_bytes(),
                'private_unit_source_identity')
        raw = storage.read_file(Path('/var/lib/quillmd/proofs'), surface + '.json')
        proof = json.loads(raw)
        require(proof.get('passed') is True and proof.get('surface') == surface
                and proof.get('release') == release and proof.get('pid') == int(state['MainPID'])
                and proof.get('identity', {}).get('all_capability_sets_empty') is True
                and proof.get('identity', {}).get('no_new_privileges') is True, 'same_pid_boundary_proof')
        require(host.state(unit) == state, 'private_service_identity_race')
        result[unit] = state
    return result


def await_service_boundary(host, storage, release, timeout=30):
    """Type=simple start returns before its existing launcher writes the new-PID proof."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return service_boundary(host, storage, release)
        except Refusal as error:
            require(str(error) == 'same_pid_boundary_proof' and time.monotonic() < deadline,
                    'startup_boundary_deadline_or_refusal')
            time.sleep(0.2)


def best_effort_private_stop(host):
    """Every unit gets an independent stop attempt even when reads/actions/evidence fail."""
    result = {}
    for unit in UNITS:
        row = {'stop_attempted': False}
        result[unit] = row
        should_stop = True
        try:
            row['before'] = host.state(unit)
            should_stop = not (row['before'].get('ActiveState') == 'inactive'
                               and row['before'].get('MainPID') == '0')
        except BaseException as error:
            row['state_read_failure'] = type(error).__name__
        if should_stop:
            row['stop_attempted'] = True
            try:
                host.service('stop', unit)
                row['stop_command_completed'] = True
            except BaseException as error:
                row['stop_failure'] = type(error).__name__
        try:
            row['after'] = host.state(unit)
            row['stopped_verified'] = (row['after'].get('ActiveState') == 'inactive'
                                       and row['after'].get('MainPID') == '0')
        except BaseException as error:
            row['state_verification_failure'] = type(error).__name__
            row['stopped_verified'] = False
    return result


def best_effort_capture(outcome, label, operation):
    """Diagnostic availability never controls fail-stop or another independent diagnostic."""
    try:
        outcome[label] = operation()
    except BaseException as error:
        outcome[label + '_capture_failure'] = type(error).__name__


def execute(args, contract, evidence, source_info, *, host, backup, storage, exclusion, env_writer):
    original = protected(APP / '.env', 65536)
    require(sha(original) == contract.get('environment_before_sha256'), 'declared_environment_baseline')
    before_values = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    require(before_values.get('QUILLMD_RELEASE_SHA') == BASELINE, 'running_release_baseline')
    updated, configuration = render(original, args.operator_commit)
    health(BASELINE)
    units_before = service_boundary(host, storage, BASELINE)
    for unit in OPERATIONS:
        state = host.state(unit)
        require(state.get('ActiveState') in ('inactive', 'failed') and state.get('MainPID') == '0',
                'active_operator_operation')
    before = snapshot(host, backup, storage)
    verified_backup = verify_backup(args.backup_directory, contract.get('backup_manifest_sha256'), before, backup)
    destination = RUNTIME / ('legacy-model-demo-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    destination.mkdir(mode=0o700)
    cipher = backup.key_at(KEY)
    write_new(destination / 'environment-before.fernet', cipher.encrypt(original))
    write_new(destination / 'environment-after.fernet', cipher.encrypt(updated))
    outcome = {'format': 1, 'complete': False, 'stage': 'prepared', 'provider_calls': 0,
               'source': source_info, 'configuration': configuration, 'qualification': evidence,
               'backup': verified_backup, 'units_before': units_before, 'before': before,
               'directory': str(destination), 'installed_engine_baseline': BASELINE}
    def checkpoint(stage):
        outcome['stage'] = stage
        write_new(destination / (stage + '.json'), encode(outcome))
        print(json.dumps({'stage': stage, 'complete': outcome['complete'], 'provider_calls': 0,
                          'evidence_directory': str(destination)}, sort_keys=True), flush=True)
    checkpoint('prepared')
    deadline = time.monotonic() + COMPLETION_SECONDS
    try:
        exclusion.bind_runtime(RUNTIME)
        with operation_locks(), exclusion.hold('legacy-model-demo:' + args.operator_commit[:12]):
            # Freeze new admission before draining. Refuse unknowns; never cancel/replay jobs.
            host.service('stop', UNITS[0])
            host.service('stop', UNITS[1])
            # Admission was empty at preflight; any intervening work fails closed and is retained.
            database(backup, storage.inventory(Path('/var/lib/quillmd/files')))
            host.service('stop', UNITS[2])
            require(all(host.state(unit).get('ActiveState') == 'inactive'
                        and host.state(unit).get('MainPID') == '0' for unit in UNITS), 'private_drain_failed')
            stopped = snapshot(host, backup, storage)
            require(stopped == before, 'population_changed_during_drain')
            require(protected(APP / '.env', 65536) == original, 'environment_changed_during_drain')
            outcome['stopped_baseline'] = stopped
            checkpoint('stopped')
            require(time.monotonic() < deadline, 'activation_bound')
            if source_info['shared_head'] != args.operator_commit:
                git(ROOT, 'merge', '--ff-only', args.operator_commit)
            # No migration/static collection/package installation or unit write is reachable.
            env_writer.replace_environment(APP / '.env', original, updated)
            checkpoint('configuration_written')
            require(snapshot(host, backup, storage) == stopped, 'stopped_preservation_failure')
            for unit in (UNITS[2], UNITS[0], UNITS[1]):
                host.service('start', unit)
            outcome['units_after'] = await_service_boundary(host, storage, args.operator_commit)
            require(all(outcome['units_after'][unit]['MainPID'] != units_before[unit]['MainPID']
                        and outcome['units_after'][unit]['ExecMainStartTimestampMonotonic']
                        != units_before[unit]['ExecMainStartTimestampMonotonic'] for unit in UNITS),
                    'service_restart_identity')
            outcome['effective_worker'] = host.effective_worker()
            require(all(outcome['effective_worker']['values'].get(key) == value
                        for key, value in configuration['values'].items()), 'actual_worker_configuration')
            outcome['health'] = await_health(args.operator_commit)
            require(snapshot(host, backup, storage) == stopped, 'post_start_preservation_failure')
            require(time.monotonic() < deadline, 'activation_bound')
            outcome['complete'] = True
            checkpoint('complete')
    except BaseException as error:
        # Fail-stop is independent of disk availability and every diagnostic operation.
        outcome['complete'] = False
        outcome['failure_kind'] = type(error).__name__
        outcome['fail_stop'] = best_effort_private_stop(host)
        if getattr(error, 'reason', None):
            outcome['managed_helper_reason'] = error.reason
            outcome['managed_helper_cleanup_complete'] = error.cleanup_complete
        best_effort_capture(outcome, 'actual_environment_sha256_on_failure', lambda: sha(protected(APP / '.env', 65536)))
        best_effort_capture(outcome, 'actual_shared_head_on_failure', lambda: git(ROOT, 'rev-parse', 'HEAD').strip().decode())
        best_effort_capture(outcome, 'failure_checkpoint', lambda: checkpoint('failed'))
        raise Refusal('activation_failed_recovery_required') from None
    return outcome


def restore_environment(original, current, release):
    """Restore the exact original assignment population; change only its actual source stamp."""
    require(re.fullmatch('[a-f0-9]{40}', release or '') is not None, 'rollback_release')
    if current != original:
        before = dotenv_values(stream=StringIO(current.decode()), interpolate=False)
        expected, _ = render(original, before.get('QUILLMD_RELEASE_SHA'))
        require(current == expected, 'rollback_environment_drift')
    parsed = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    # Validate the retained private baseline even when no configuration write completed.
    render(original, release)
    if parsed.get('QUILLMD_RELEASE_SHA') == release:
        return original
    lines, count = [], 0
    for line in original.splitlines(keepends=True):
        match = ASSIGNMENT.match(line)
        if match and match[1] == b'QUILLMD_RELEASE_SHA':
            count += 1
            lines.append(('QUILLMD_RELEASE_SHA="' + release + '"\n').encode())
        else:
            lines.append(line)
    require(count == 1, 'rollback_release_population')
    restored = b''.join(lines)
    restored_values = dotenv_values(stream=StringIO(restored.decode()), interpolate=False)
    require(all(restored_values.get(key) == parsed.get(key) for key in MODEL_VALUES), 'rollback_model_values')
    return restored


def rollback(args, source_info, *, host, backup, storage, exclusion, env_writer):
    directory = args.activation_directory
    require(directory and directory.is_relative_to(RUNTIME) and directory.resolve(strict=True) == directory
            and directory.name.startswith('legacy-model-demo-'), 'rollback_protected_directory')
    backup.private_dir(directory)
    cipher = backup.key_at(KEY)
    original = cipher.decrypt(protected(directory / 'environment-before.fernet', 65536))
    expected = cipher.decrypt(protected(directory / 'environment-after.fernet', 65536))
    current = protected(APP / '.env', 65536)
    require(current in (original, expected), 'rollback_exact_expected_environment')
    actual_source = git(ROOT, 'rev-parse', 'HEAD').strip().decode()
    require(actual_source in (BASELINE, args.operator_commit), 'rollback_source_identity')
    restored = restore_environment(original, current, actual_source)
    receipt = {'format': 1, 'complete': False, 'provider_calls': 0, 'stage': 'rollback_prepared',
               'source': source_info, 'activation_directory': str(directory),
               'current_sha256': sha(current), 'restored_sha256': sha(restored),
               'preserved_source': actual_source, 'database_restore_performed': False}
    destination = RUNTIME / ('legacy-model-rollback-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    destination.mkdir(mode=0o700)
    write_new(destination / 'prepared.json', encode(receipt))
    try:
        exclusion.bind_runtime(RUNTIME)
        with operation_locks(), exclusion.hold('legacy-model-rollback:' + args.operator_commit[:12]):
            for unit in UNITS:
                host.service('stop', unit)
            require(all(host.state(unit).get('ActiveState') == 'inactive'
                        and host.state(unit).get('MainPID') == '0' for unit in UNITS), 'rollback_private_drain')
            before = snapshot(host, backup, storage)
            env_writer.replace_environment(APP / '.env', current, restored)
            require(snapshot(host, backup, storage) == before, 'rollback_stopped_preservation')
            for unit in (UNITS[2], UNITS[0], UNITS[1]):
                host.service('start', unit)
            receipt['units_after'] = await_service_boundary(host, storage, actual_source)
            receipt['worker_after'] = host.effective_worker()
            parsed = dotenv_values(stream=StringIO(restored.decode()), interpolate=False)
            require(all(receipt['worker_after']['values'].get(key) == parsed.get(key)
                        for key in (*MODEL_VALUES, 'QUILLMD_RELEASE_SHA')), 'rollback_effective_worker')
            await_health(actual_source)
            require(snapshot(host, backup, storage) == before, 'rollback_post_start_preservation')
            receipt.update(complete=True, stage='rollback_complete', preserved=before)
            write_new(destination / 'complete.json', encode(receipt))
    except BaseException as error:
        receipt['stage'] = 'rollback_failed'
        receipt['complete'] = False
        receipt['failure_kind'] = type(error).__name__
        receipt['fail_stop'] = best_effort_private_stop(host)
        best_effort_capture(receipt, 'actual_environment_sha256', lambda: sha(protected(APP / '.env', 65536)))
        best_effort_capture(receipt, 'failure_checkpoint', lambda: write_new(destination / 'failed.json', encode(receipt)))
        raise Refusal('rollback_failed_recovery_required') from None
    print(json.dumps({'rollback_complete': True, 'provider_calls': 0, 'evidence_directory': str(destination)}, sort_keys=True))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator-commit')
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--backup-directory', type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--rollback', action='store_true')
    parser.add_argument('--activation-directory', type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'execution_performed': False, 'baseline': BASELINE, 'declaration': DECL,
                          'required_profile': PROFILE, 'required_rates': MODEL_VALUES,
                          'required_outcomes': sorted(OUTCOMES), 'required_evidence_roles': sorted(EVIDENCE_ROLES),
                          'note': 'No environment, provider, service or database is accessed by this plan.'}, sort_keys=True))
        return 0
    raw, contract = declaration()
    info = source_gate(args.operator_commit, contract, executing=True)
    exclusion, backup, env_writer, managed, storage = modules()
    if args.rollback:
        require(contract.get('rollback_qualified') is True, 'separately_committed_rollback_required')
        rollback(args, info, host=Host(managed), backup=backup, storage=storage,
                 exclusion=exclusion, env_writer=env_writer)
        return 0
    require(args.qualification and args.backup_directory, 'qualification_and_backup_required')
    evidence = read_qualification(args.qualification, contract.get('qualification_sha256'))
    execute(args, contract, evidence, info, host=Host(managed), backup=backup, storage=storage,
            exclusion=exclusion, env_writer=env_writer)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Legacy model configuration refused or stopped; inspect protected evidence. No automatic retry.') from None
