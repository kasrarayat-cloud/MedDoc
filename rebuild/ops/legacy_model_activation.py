"""Preserving private legacy-model configuration act; no direct provider calls or migrations.

The default only reports the qualification contract. Execution requires a separately
completed, committed declaration, exact CI, protected exact-source QA evidence and a
current authenticated backup. Exact merged-source CI remains an execution prerequisite.
Optional separately capped browser acceptance delegates synthetic worker requests while
retaining the original exclusion; installer/provider and acceptance outcomes stay separate.
"""
import argparse
import ast
from collections import Counter
from contextlib import ExitStack, contextmanager
from contextlib import redirect_stdout
from datetime import datetime, timezone
import fcntl
import hashlib
import gzip
import importlib.util
import io
from io import StringIO
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import sys
import tarfile
import time
import types
import uuid
from types import SimpleNamespace

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
                     'docs/rebuild/owner-doctor-test-guide-20261006.html',
                     'docs/foundation/mutations/20261006-owner-dashboard-storage-exception.md',
                     'package-lock.json', 'rebuild/browser-tests.mjs', 'rebuild/ops/automatic_offsite.py',
                     'rebuild/ops/test_automatic_offsite.py', 'rebuild/static/app.css', 'rebuild/static/app.js',
                     'rebuild/static/fonts/dm-sans.ttf', 'rebuild/static/fonts/OFL-DM-Sans.txt',
                     'rebuild/templates/admin_dashboard.html', 'rebuild/templates/admin_services.html',
                     'rebuild/templates/base.html', 'rebuild/templates/dashboard.html',
                     'rebuild/templates/encounter_detail.html', 'rebuild/templates/encounter_input.html',
                     'rebuild/templates/template_detail.html', 'rebuild/templates/template_upload.html'})
DEPENDENCIES = ('rebuild/ops/managed_helper.py', 'rebuild/ops/private_storage.py',
                'rebuild/ops/backup_restore.py', 'rebuild/ops/email_activation.py',
                'rebuild/ops/activation_exclusion.py', 'scripts/check-citation.sh',
                'scripts/run-ruled-mutation.sh', 'scripts/lib/declaration.sh',
                'scripts/lib/run-watched.sh', 'scripts/activate-typed-voice.py',
                'rebuild/ops/service_launcher.py', 'rebuild/quillmd/settings.py',
                'rebuild/quillmd/static_storage.py', 'rebuild/requirements.txt', 'package.json')
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
RECOVERY_SECONDS = 180
ACCEPTANCE_SECONDS = 1200
BACKUPS = ROOT / 'backups/owner-demo-20261006'
CAPTURE_ATTEMPT = RUNTIME / 'owner-demo-20261006/legacy-ui-fresh-capture-attempt.json'
ACCEPTANCE_ROOT = RUNTIME / 'owner-demo-20261006'
ACCEPTANCE_BROWSER = ACCEPTANCE_ROOT / 'installed-browser-acceptance-v2.mjs'
ACCEPTANCE_VERIFIER = ACCEPTANCE_ROOT / 'verify_installed_acceptance_v2.py'
ACCEPTANCE_OUTPUT = ACCEPTANCE_ROOT / 'installed-acceptance-v2-20261006'
STATIC_PRIMITIVES = 'scripts/activate-typed-voice.py'
STATIC_PRIMITIVES_SHA = '4e2efda2357fa2c33262eb2f747ac7201eadbc94875528cde2b7fe9040ebba18'
STATIC_INPUTS = frozenset({'app.css', 'app.js', 'fonts/dm-sans.ttf', 'fonts/OFL-DM-Sans.txt',
                           'django_otp/css/login.css', 'otp_totp/css/qrcode.css', 'otp_totp/js/qrcode.js'})
STORAGE_AUTHORITY = 'docs/foundation/mutations/20261006-owner-dashboard-storage-exception.md'
STORAGE_RESERVE = 20 * 1024 ** 3
STORAGE_ALLOWANCES = {'peak_bytes': 5 * 1024 ** 3, 'rollback_bytes': 1024 ** 3, 'background_bytes': 8 * 1024 ** 3}
CONTINUATION_ORIGINAL = RUNTIME / 'legacy-model-demo-20261007T012249Z'
CONTINUATION_RELEASE = '4d46a71520275d76a36aa83ddff1a85939711a04'
CONTINUATION_OUTPUT = RUNTIME / 'legacy-model-continuation-20261007'
CONTINUATION_ATTEMPT = ACCEPTANCE_ROOT / 'legacy-ui-continuation-attempt-20261007.json'
CONTINUATION_ADMIN = ACCEPTANCE_ROOT / 'installed-admin-continuation-20261007'
CONTINUATION_PREPARATION = ACCEPTANCE_ROOT / 'prepare-installed-admin-auth.mjs'
CONTINUATION_REPAIRS = frozenset({SELF, DECL, 'rebuild/ops/test_legacy_model_activation.py', STORAGE_AUTHORITY})
CONTINUATION_RECEIPTS = {
    'failed.json': 'a29e230d8c1b0d13cd33af76ad42231443956792de25060af400d809c3f27e05',
    'recovery.json': 'df8191bf9e3666db38a1478cd03754187a8106a0efafe3faec5ee46231af496f',
    'static_installed.json': '9f910ddda3bebabdd2faa7ae7c1484b8cfce31c5314b8ef4f459c93d1c535787',
    'fresh-backup-attempt.json': 'fbbe24e19627269b0c63167753b362ef0b58045998a449d2df8fafd59365906e',
    'fresh_backup_verified.json': '8b5984868fe8e5ac2164f9088298fd2cd05ce28b59c13856cf8fcf7868ba9395'}


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


def storage_admission(contract, phase):
    """A scoped owner exception; never turns the original percentage verdict green."""
    require(contract.get('storage_authority_path') == STORAGE_AUTHORITY
            and sha((SOURCE / STORAGE_AUTHORITY).read_bytes()) == contract.get('storage_authority_sha256'),
            'committed_storage_exception_identity')
    require(contract.get('storage_allowances') == STORAGE_ALLOWANCES
            and contract.get('storage_minimum_reserve_bytes') == STORAGE_RESERVE, 'storage_exception_scope')
    measured = os.statvfs(ROOT)
    available = measured.f_bavail * measured.f_frsize
    used = (measured.f_blocks - measured.f_bfree) * measured.f_frsize
    require(available - sum(STORAGE_ALLOWANCES.values()) >= STORAGE_RESERVE, 'task_storage_reserve')
    return {'phase': phase, 'original_preflight_percentage_verdict': 'RED',
            'task_disposition': 'explicit owner exception', 'available_bytes': available,
            'available_inodes': measured.f_favail,
            'current_used_percentage': math.ceil(100 * used / (used + available)),
            'conservative_remaining_allowances': STORAGE_ALLOWANCES,
            'projected_available_bytes': available - sum(STORAGE_ALLOWANCES.values()),
            'minimum_reserve_bytes': STORAGE_RESERVE, 'authority_sha256': contract['storage_authority_sha256']}


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


def source_recovery_state(target):
    """Admit only exact old/new committed bytes during a guarded, interrupted reverse."""
    head = git(ROOT, 'rev-parse', 'HEAD').strip().decode()
    require(head in (BASELINE, target) and git(ROOT, 'branch', '--show-current').strip() == b'main',
            'recovery_source_head')
    trees = {git(ROOT, 'rev-parse', revision + '^{tree}').strip() for revision in (BASELINE, target)}
    require(git(ROOT, 'write-tree').strip() in trees, 'recovery_source_index')
    changed = set(git(ROOT, 'diff', '--name-only', BASELINE, target).decode().splitlines())
    require(changed <= ALLOWED, 'recovery_source_scope')
    require(set(git(ROOT, 'diff', '--name-only', BASELINE).decode().splitlines()) <= changed,
            'recovery_unrelated_worktree_drift')
    populations = {revision: set(git(ROOT, 'ls-tree', '-r', '--name-only', revision).decode().splitlines())
                   for revision in (BASELINE, target)}
    for name in changed:
        path = ROOT / name
        candidates = [git(ROOT, 'show', revision + ':' + name)
                      for revision in (BASELINE, target) if name in populations[revision]]
        if path.exists():
            require(path.is_file() and not path.is_symlink() and path.read_bytes() in candidates,
                    'recovery_unqualified_source_bytes')
        else:
            require(not path.is_symlink() and any(name not in populations[r] for r in populations),
                    'recovery_missing_source_bytes')
    return {'head': head, 'changed_paths': sorted(changed),
            'baseline_tree': git(ROOT, 'rev-parse', BASELINE + '^{tree}').strip()}


def restore_source(target):
    state = source_recovery_state(target)
    index_is_baseline = git(ROOT, 'write-tree').strip() == state['baseline_tree']
    if not index_is_baseline or git(ROOT, 'diff', '--name-only').strip():
        # Restore only individually authenticated old/new bytes in the exact shipped diff.
        # No reset, force/discard flag, untracked cleanup or unrelated file is reachable.
        paths = state['changed_paths']
        if index_is_baseline:
            baseline_paths = set(git(ROOT, 'ls-tree', '-r', '--name-only', BASELINE).decode().splitlines())
            paths = sorted(set(paths) & baseline_paths)
        git(ROOT, 'restore', '--source=' + BASELINE, '--staged', '--worktree', '--', *paths)
    require(git(ROOT, 'write-tree').strip() == state['baseline_tree']
            and not git(ROOT, 'diff', '--name-only').strip(), 'source_reverse_tree_identity')
    if state['head'] != BASELINE:
        git(ROOT, 'update-ref', 'refs/heads/main', BASELINE, target)
    require(git(ROOT, 'rev-parse', 'HEAD').strip().decode() == BASELINE
            and not git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'source_reverse_complete')
    return {'source': BASELINE, 'scoped_old_new_bytes_only': True, 'untracked_files_removed': False}


def source_gate(commit, contract, *, executing, recovering=False, resuming=False):
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
    if resuming:
        continuation = continuation_policy(contract)
        repairs = set(git(SOURCE, 'diff', '--name-only', CONTINUATION_RELEASE, commit).decode().splitlines())
        git(SOURCE, 'merge-base', '--is-ancestor', CONTINUATION_RELEASE, commit)
        require(repairs == CONTINUATION_REPAIRS
                and continuation.get('repair_source_paths') == sorted(repairs), 'continuation_source_scope')
        require(head == CONTINUATION_RELEASE, 'continuation_installed_source')
    require(head in (BASELINE, commit, CONTINUATION_RELEASE if resuming else BASELINE)
            and git(ROOT, 'branch', '--show-current').strip() == b'main', 'shared_deploy_surface_drift')
    if recovering:
        source_recovery_state(commit)
    else:
        require(not git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'shared_deploy_surface_drift')
    # Core generation, Word, settings and requirements stay byte-identical. Only exact
    # named templates/static and the separately reviewed operator clock/tooling may differ.
    for relative in git(ROOT, 'ls-files', 'rebuild').decode().splitlines():
        if not (recovering and relative in changed):
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
        if resuming:
            command(['bash', str(SOURCE / 'scripts/check-citation.sh'), CONTINUATION_RELEASE], cwd=SOURCE)
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

    def worker_configuration(self, expected_environment, release, boundary):
        """Configuration provenance; deliberately never reads another process's environment.

        Docker AppArmor refuses that read even at the application UID. The reviewed
        unit loads the protected EnvironmentFile before its same-PID launcher execs
        this exact worker. Actual requested/returned models require subsequent job
        configuration and provider-response evidence, not this provenance record.
        """
        state = self.state(UNITS[2])
        require(state.get('ActiveState') == 'active' and int(state.get('MainPID', '0')) > 0
                and boundary.get(UNITS[2]) == state, 'worker_startup_identity')
        pid = int(state['MainPID'])
        root = Path('/proc') / str(pid)
        argv = root.joinpath('cmdline').read_bytes().split(b'\0')
        require(argv == [str(APP / '.venv/bin/python').encode(), str(APP / 'manage.py').encode(),
                         b'worker', b''], 'worker_command_identity')
        cgroup_raw = root.joinpath('cgroup').read_bytes()
        # Native host v2 procfs, not a helper's relative cgroup namespace.
        require(cgroup_raw == ('0::/system.slice/' + UNITS[2] + '\n').encode(), 'worker_cgroup_identity')
        cgroup = cgroup_raw[:-1].decode()
        fields = root.joinpath('stat').read_text().rsplit(') ', 1)[1].split()
        ticks = int(fields[19])
        ticks_per_second = os.sysconf('SC_CLK_TCK')
        systemd_start = int(state.get('ExecMainStartTimestampMonotonic', '0'))
        require(ticks > 0 and systemd_start > 0
                and abs(ticks * 1000000 / ticks_per_second - systemd_start) < 1000000,
                'worker_kernel_systemd_start_identity')
        actual = protected(APP / '.env', 65536)
        require(actual == expected_environment, 'worker_configuration_file_drift')
        parsed = dotenv_values(stream=StringIO(actual.decode()), interpolate=False)
        require(parsed.get('QUILLMD_RELEASE_SHA') == release, 'worker_configuration_release')
        unit = APP / 'deploy' / UNITS[2]
        require(unit.read_bytes() == git(SOURCE, 'show', BASELINE + ':rebuild/deploy/' + UNITS[2])
                and unit.read_bytes().count(b'EnvironmentFile=/opt/meddoc-pro/rebuild/.env\n') == 1,
                'worker_environment_loading_source')
        keys = ('QUILLMD_AI_MODE', 'QUILLMD_AI_PROVIDER', *MODEL_VALUES, 'QUILLMD_RELEASE_SHA',
                'QUILLMD_DATA_MODE', 'QUILLMD_PREVIEW_AUTH_ENABLED')
        result = {'pid': pid, 'unit': UNITS[2], 'cgroup': cgroup,
                  'kernel_start_ticks': ticks, 'systemd_start_monotonic_usec': systemd_start,
                  'configuration_file_sha256': sha(actual), 'unit_source_sha256': sha(unit.read_bytes()),
                  'values': {key: parsed.get(key) for key in keys},
                  'evidence_scope': 'reviewed EnvironmentFile plus fresh same-PID startup and exact protected configuration',
                  'direct_environment_readback': False, 'actual_provider_model_verified': False}
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


def reaper_admission(query, files):
    """No old unapproved clip may age into cleanup during the bounded acceptance phase."""
    candidates = query("""SELECT DISTINCT details->>'path' FROM core_auditevent a
        WHERE action='voice.over_limit_quoted'
        AND NOT EXISTS(SELECT 1 FROM core_job j WHERE j.input_path=a.details->>'path')""")
    require(not any(path in files and re.fullmatch(r'audio/[a-f0-9]{48}\.(wav|webm|mp3|m4a)', path or '')
                    for path, in candidates)
            and not any(path.startswith('submissions/') for path in files), 'worker_reaper_targets')


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
        referenced = {}
        for _, statement in backup.FILE_QUERIES:
            for path, expected_hash in query(statement):
                if path:
                    require(path in files and (not expected_hash or files[path]['sha256'] == expected_hash),
                            'referenced_file_identity')
                    referenced[path] = files[path]['sha256']
        reaper_admission(query, files)
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
    return {'tables': rows, 'catalog': catalog, 'invariants': invariants, 'pending_jobs': pending,
            'held': held, 'referenced_files': referenced}


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
    directory = Path(path)
    require(directory.is_absolute() and directory.parent == BACKUPS
            and directory.resolve(strict=True) == directory
            and re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}', directory.name), 'backup_destination')
    backup.private_dir(BACKUPS)
    backup.private_dir(directory)
    cipher = backup.key_at(KEY)
    loaded, manifest = backup.load_backup(directory, cipher)
    require(loaded == directory and manifest.get('run_id') == directory.name
            and manifest.get('source_commit') == BASELINE
            and manifest.get('database') == 'quillmd_fresh', 'backup_source_identity')
    container = backup.inspect_container('quillmd-fresh-postgres')
    require(container.get('Id') == manifest.get('container_id')
            and container.get('Image') == manifest.get('image_id') and container.get('State', {}).get('Running') is True
            and container.get('HostConfig', {}).get('PortBindings')
            == {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '55438'}]}, 'backup_live_database_identity')
    require(sha(protected(directory / 'manifest.json.fernet', 8 * 1024 * 1024)) == expected_hash,
            'backup_manifest_identity')
    require(manifest['tables'] == snapshot_value['database']['tables']
            and manifest['invariants'] == snapshot_value['database']['invariants'], 'backup_current_row_coverage')
    require({entry['path'] for entry in manifest['files']}
            == set(snapshot_value['database']['referenced_files']), 'backup_current_reference_coverage')
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


def capture_current_backup(backup, baseline, destination, contract):
    """Exactly one local encrypted capture after drain, still under publication exclusion."""
    policy = {'source': str(APP), 'output': str(BACKUPS), 'source_commit': BASELINE,
              'key_file': str(KEY), 'database_credentials': str(ROLES), 'maximum_attempts': 1,
              'exclusive_attempt_marker': str(CAPTURE_ATTEMPT),
              'timing': 'inside_exclusion_after_private_drain_before_publication',
              'primitive_sha256': sha(git(SOURCE, 'show', BASELINE + ':rebuild/ops/backup_restore.py')),
              'offsite_upload': False, 'provider_calls': 0}
    require(contract.get('fresh_capture_policy') == policy, 'prospective_fresh_capture_scope')
    require(sha((SOURCE / 'rebuild/ops/backup_restore.py').read_bytes()) == policy['primitive_sha256'],
            'qualified_fresh_capture_primitive')
    backup.private_dir(BACKUPS)
    retained = inventory(BACKUPS)
    before_fingerprint = sha(encode(baseline))
    attempt = encode({'attempt': 1, 'activation_directory': str(destination), 'policy': policy,
                      'stopped_before_fingerprint_sha256': before_fingerprint, 'automatic_retries': False})
    backup.private_dir(CAPTURE_ATTEMPT.parent)
    # A new invocation cannot spend another capture attempt after this prospective act failed.
    write_new(CAPTURE_ATTEMPT, attempt)
    write_new(destination / 'fresh-backup-attempt.json', attempt)
    output = io.StringIO()
    # Normal qualified primitive exports a READ ONLY snapshot and pg_dump uses the
    # same snapshot. Its key/role remain private and plaintext never reaches disk.
    with redirect_stdout(output):
        backup.backup(SimpleNamespace(source=APP, output=BACKUPS, key_file=KEY, database_credentials=ROLES))
    summary = json.loads(output.getvalue())
    run_id = summary.get('run_id', '')
    require(summary.get('complete') is True and re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}', run_id)
            and summary.get('backup_directory') == str(BACKUPS / run_id), 'fresh_capture_output_identity')
    actual = inventory(BACKUPS)
    require(all(actual.get(name) == row for name, row in retained.items())
            and all(name in retained or name == run_id or name.startswith(run_id + '/') for name in actual),
            'previous_capture_preservation')
    verified = verify_backup(BACKUPS / run_id, summary.get('manifest_cipher_sha256'), baseline, backup)
    verified.update(capture_attempts=1, stopped_before_fingerprint_sha256=before_fingerprint,
                    backup_directory=str(BACKUPS / run_id), previous_captures_preserved=True,
                    local_encrypted_capture=True, offsite_upload=False, provider_calls=0)
    return verified


def static_primitives():
    """Load only five pure, hash-pinned public-asset functions, not their old activation driver."""
    raw = (SOURCE / STATIC_PRIMITIVES).read_bytes()
    require(sha(raw) == STATIC_PRIMITIVES_SHA, 'qualified_static_primitives_identity')
    names = {'static_inventory', 'create_static_stage', 'static_delta', 'retain_static', 'install_static'}
    nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name in names]
    require({node.name for node in nodes} == names and len(nodes) == len(names), 'qualified_static_primitives_population')
    module = types.ModuleType('_legacy_demo_static_primitives')
    module.__dict__.update(Path=Path, PurePosixPath=PurePosixPath, os=os, stat=stat,
                           hashlib=hashlib, io=io, tarfile=tarfile, uuid=uuid, require=require, sha=sha)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SOURCE / STATIC_PRIMITIVES), 'exec'), module.__dict__)
    return module


def static_sources():
    otp = Path(importlib.util.find_spec('django_otp').origin).parent
    return {'app.css': SOURCE / 'rebuild/static/app.css', 'app.js': SOURCE / 'rebuild/static/app.js',
            'fonts/dm-sans.ttf': SOURCE / 'rebuild/static/fonts/dm-sans.ttf',
            'fonts/OFL-DM-Sans.txt': SOURCE / 'rebuild/static/fonts/OFL-DM-Sans.txt',
            'django_otp/css/login.css': otp / 'static/django_otp/css/login.css',
            'otp_totp/css/qrcode.css': otp / 'plugins/otp_totp/static/otp_totp/css/qrcode.css',
            'otp_totp/js/qrcode.js': otp / 'plugins/otp_totp/static/otp_totp/js/qrcode.js'}


def public_source(path):
    require(path.is_absolute() and path.resolve(strict=True) == path, 'public_source_canonical')
    with path.open('rb') as stream:
        info = os.fstat(stream.fileno())
        # Checkouts and the qualified installed venv use operator-group 0664.
        # Their bytes are separately source/hash pinned; application UID996/GID988 cannot write them.
        require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_gid == os.getgid()
                and info.st_nlink == 1 and not info.st_mode & 0o002
                and info.st_size <= 16 * 1024 * 1024, 'public_source_identity')
        raw = stream.read(info.st_size + 1)
        current = path.stat()
        require(len(raw) == info.st_size and all(getattr(info, key) == getattr(current, key)
                for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'public_source_read_race')
        return raw


def validate_static_stage(root, inputs, primitives):
    """Exactly seven public sources; only the declared CSS font URL may be rewritten."""
    rows = primitives.static_inventory(root)
    manifest = json.loads((root / 'staticfiles.json').read_bytes())
    require(set(manifest) == {'paths', 'version', 'hash'} and manifest['version'] == '1.1'
            and isinstance(manifest['paths'], dict) and set(manifest['paths']) == set(inputs) == STATIC_INPUTS,
            'static_manifest_source_population')
    require(manifest['hash'] == hashlib.md5(json.dumps(sorted(manifest['paths'].items())).encode()).hexdigest()[:12],
            'static_manifest_content_identity')
    font = public_source(inputs['fonts/dm-sans.ttf'])
    font_name = 'fonts/dm-sans.' + hashlib.md5(font).hexdigest()[:12] + '.ttf'
    require(manifest['paths']['fonts/dm-sans.ttf'] == font_name, 'static_font_content_identity')
    allowed, directories = {'staticfiles.json'}, {'.'}
    for name, source in inputs.items():
        raw = public_source(source)
        compiled_bytes = raw
        if name == 'app.css':
            text = raw.decode()
            urls = re.findall(r'url\(\s*[\"\']?([^\)\"\']+)[\"\']?\s*\)', text)
            require(urls and all(value.strip() == 'fonts/dm-sans.ttf' for value in urls), 'static_css_url_scope')
            compiled_bytes = text.replace('fonts/dm-sans.ttf', font_name).encode()
        original = PurePosixPath(name)
        compiled = str(original.with_suffix('')) + '.' + hashlib.md5(compiled_bytes).hexdigest()[:12] + original.suffix
        require(manifest['paths'][name] == compiled and (root / name).read_bytes() == raw
                and (root / compiled).read_bytes() == compiled_bytes, 'static_compiled_source_identity')
        for output, expected in ((name, raw), (compiled, compiled_bytes)):
            require(rows.get(output, {}).get('kind') == 'file', 'static_compiled_file_identity')
            allowed.update((output, output + '.gz', output + '.br'))
            directories.update(str(parent) for parent in PurePosixPath(output).parents)
            if output + '.gz' in rows:
                require(gzip.decompress((root / (output + '.gz')).read_bytes()) == expected, 'static_gzip_identity')
            if output + '.br' in rows:
                import brotli
                require(brotli.decompress((root / (output + '.br')).read_bytes()) == expected, 'static_brotli_identity')
    require(all(name in (directories if row['kind'] == 'directory' else allowed) for name, row in rows.items()),
            'static_undeclared_output')
    return rows


def prepare_static(destination, contract):
    inputs = static_sources()
    expected = contract.get('static_source_sha256')
    require(isinstance(expected, dict) and set(expected) == STATIC_INPUTS
            and all(re.fullmatch('[a-f0-9]{64}', value or '') for value in expected.values()), 'static_source_pins_required')
    require({name: sha(public_source(path)) for name, path in inputs.items()} == expected, 'static_source_pin_drift')
    primitives = static_primitives()
    before = primitives.static_inventory(APP / 'staticfiles')
    require(sha(encode(before)) == contract.get('static_before_inventory_sha256'), 'declared_static_baseline')
    stage = destination / 'static-stage'
    primitives.create_static_stage(stage)
    code = ('from django.conf import settings; settings.configure(SECRET_KEY="public-static-only", '
            'INSTALLED_APPS=["django.contrib.staticfiles","django_otp","django_otp.plugins.otp_totp"], '
            'STATIC_URL="/static/", STATIC_ROOT=' + repr(str(stage)) + ', STATICFILES_DIRS=['
            + repr(str(SOURCE / 'rebuild/static')) + '], STORAGES={"staticfiles":{'
            '"BACKEND":"quillmd.static_storage.PublicCompressedManifestStaticFilesStorage",'
            '"OPTIONS":{"file_permissions_mode":420,"directory_permissions_mode":493}}}); '
            'import django; django.setup(); from django.core.management import call_command; '
            'call_command("collectstatic", interactive=False, verbosity=0)')
    done = subprocess.run([str(APP / '.venv/bin/python'), '-B', '-c', code], cwd=SOURCE / 'rebuild',
                          env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'},
                          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=90)
    require(done.returncode == 0, 'isolated_static_collection_failed')
    staged = validate_static_stage(stage, inputs, primitives)
    require({name: sha(public_source(path)) for name, path in inputs.items()} == expected, 'static_source_collection_race')
    primitives.retain_static(APP / 'staticfiles', destination / 'public-assets-before.tar', before)
    return {'sources': expected, 'before': before, 'staged': staged, 'stage': str(stage),
            'prior_assets_archive_sha256': sha(protected(destination / 'public-assets-before.tar', 64 * 1024 * 1024)),
            'provider_calls': 0, 'database_connections': 0}


def install_static(preparation):
    primitives = static_primitives()
    root, stage = APP / 'staticfiles', Path(preparation['stage'])
    require(primitives.static_inventory(root) == preparation['before'], 'static_before_install_drift')
    require(validate_static_stage(stage, static_sources(), primitives) == preparation['staged'], 'static_stage_install_drift')
    old_dirs = {name for name, row in preparation['before'].items() if row['kind'] == 'directory'}
    new_dirs = {name for name, row in preparation['staged'].items() if row['kind'] == 'directory'}
    require(new_dirs - old_dirs <= {'fonts'} and old_dirs <= new_dirs, 'static_directory_delta_scope')
    if 'fonts' not in old_dirs:
        primitives.create_static_stage(root / 'fonts')
    before = primitives.static_inventory(root)
    after = primitives.install_static(root, stage, before, preparation['staged'])
    return {'before': preparation['before'], 'after': after,
            'old_immutable_assets_retained': True, 'source_bound': True,
            'new_directories': sorted(new_dirs - old_dirs)}


def restore_static(preparation, activation_directory):
    """Restore old manifest/aliases; retain all previously published immutable hashes."""
    primitives = static_primitives()
    root = APP / 'staticfiles'
    before, staged = preparation['before'], preparation['staged']
    current = primitives.static_inventory(root)
    replaceable = {'staticfiles.json'} | {name + suffix for name in ('app.css', 'app.js')
                                           for suffix in ('', '.gz', '.br')}
    require(set(before) <= set(current) and set(current) - set(before) <= set(staged), 'rollback_static_population')
    for name, row in current.items():
        original = before.get(name)
        if original is not None and name not in replaceable:
            require(row == original, 'rollback_static_immutable_drift')
        elif original is not None:
            candidates = [candidate for candidate in (original, staged.get(name)) if candidate is not None]
            require(any(all(row.get(key) == candidate.get(key) for key in ('kind', 'mode', 'size', 'sha256'))
                        for candidate in candidates), 'rollback_static_alias_drift')
        else:
            require(all(row.get(key) == staged[name].get(key) for key in ('kind', 'mode', 'size', 'sha256')),
                    'rollback_static_added_drift')
    archive = protected(activation_directory / 'public-assets-before.tar', 64 * 1024 * 1024)
    require(sha(archive) == preparation['prior_assets_archive_sha256'], 'rollback_static_archive_identity')
    payload = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:') as source:
        for member in source:
            require(member.name in before and member.name not in payload and member.isfile()
                    and member.mode == 0o644 and member.size == before[member.name]['size'], 'rollback_static_archive_member')
            data = source.extractfile(member).read(member.size + 1)
            require(len(data) == member.size and sha(data) == before[member.name]['sha256'], 'rollback_static_archive_content')
            payload[member.name] = data
    require(set(payload) == {name for name, row in before.items() if row['kind'] == 'file'}, 'rollback_static_archive_population')
    for name in sorted(replaceable & set(payload), key=lambda value: (value == 'staticfiles.json', value)):
        if current[name]['sha256'] == before[name]['sha256']:
            continue
        path = root / name
        require(path.parent.resolve(strict=True) == path.parent and primitives.static_inventory(root)[name] == current[name],
                'rollback_static_write_race')
        temporary = path.with_name('.legacy-model-rollback-' + uuid.uuid4().hex)
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
        try:
            with os.fdopen(fd, 'wb') as output:
                os.fchmod(output.fileno(), 0o644)
                output.write(payload[name]); output.flush(); os.fsync(output.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
    after = primitives.static_inventory(root)
    require(set(after) == set(current), 'rollback_static_retained_population')
    for name, row in before.items():
        if name in replaceable:
            require(all(after[name][key] == row[key] for key in ('kind', 'mode', 'size', 'sha256')),
                    'rollback_static_alias_identity')
        else:
            require(after[name] == row, 'rollback_static_retained_identity')
    return {'previous_manifest_aliases_restored': True, 'immutable_assets_retained': True, 'after': after}


def health(release, *, probe_preview=False):
    """Structural readiness; the ordinary gated GET creates an anonymous session.

    That probe is permitted only before the authoritative preservation baseline.
    Post-start and recovery checks retain the immutable ingress fingerprint instead.
    """
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
    if probe_preview:
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


def service_boundary(host, storage, release, *, worker_required=True):
    result = {}
    require(type(worker_required) is bool, 'private_boundary_mode')
    surfaces = ('doctor', 'admin', 'worker') if worker_required else ('doctor', 'admin')
    for unit, surface in zip(UNITS, surfaces):
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


def await_service_boundary(host, storage, release, timeout=30, *, worker_required=True):
    """Type=simple start returns before its existing launcher writes the new-PID proof."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            return service_boundary(host, storage, release, worker_required=worker_required)
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


def acceptance_preparation(contract, target, *, continuation=False):
    """Fixed prospective synthetic campaign; hash admission performs no login or request."""
    require(re.fullmatch('[a-f0-9]{40}', target or '') is not None, 'acceptance_target_identity')
    scope = {'browser_path': str(ACCEPTANCE_BROWSER), 'verifier_path': str(ACCEPTANCE_VERIFIER),
             'output_path': str(ACCEPTANCE_OUTPUT), 'origin': 'https://app.quillmd.com:9443',
             'maximum_generations': 5, 'maximum_transcriptions': 1, 'provider_usd_limit': '0.70',
             'concurrency': 1, 'automatic_retries': False, 'maximum_seconds': ACCEPTANCE_SECONDS,
             'retains_original_publication_exclusion': True, 'baseline_recovery_after_acceptance_start': False}
    require(contract.get('acceptance_phase') == scope, 'prospective_acceptance_scope')
    require(not os.path.lexists(ACCEPTANCE_OUTPUT), 'acceptance_campaign_replay')
    raw, actual_contract = declaration()
    require(actual_contract == contract, 'acceptance_declaration_identity')
    def pin(name):
        matches = re.findall('^' + name + r': ([a-f0-9]{64})$', raw.decode(), re.M)
        require(len(matches) == 1, 'acceptance_committed_pin')
        return matches[0]
    paths = {'acceptance_browser_sha256': ACCEPTANCE_BROWSER, 'acceptance_verifier_sha256': ACCEPTANCE_VERIFIER,
             'acceptance_options_sha256': ACCEPTANCE_ROOT / 'prepared-options.json',
             'acceptance_allergy_manifest_sha256': ACCEPTANCE_ROOT / 'acceptance-v2-inputs/manifest.json',
             'acceptance_allergy_form_sha256': ACCEPTANCE_ROOT / 'acceptance-v2-inputs/allergy-review.docx'}
    hashes = {}
    for label, path in paths.items():
        hashes[label] = sha(protected(path, 2 * 1024 * 1024))
        require(hashes[label] == pin(label), 'acceptance_reviewed_artifact_identity')
    # The ordinary admin login/MFA is performed before capture; only its protected proof is read here.
    admin_directory = CONTINUATION_ADMIN if continuation else ACCEPTANCE_ROOT / 'installed-admin-before-activation'
    auth_raw = protected(admin_directory / 'normal-authentication.json')
    auth = json.loads(auth_raw)
    session = admin_directory / 'browser-session.json'
    require(auth.get('format') == 1 and auth.get('complete') is True and auth.get('release') == target
            and auth.get('csrf403_no_OTP_noauththrottle') is True
            and auth.get('normal_mfa_login') is True and auth.get('auth_reset') is False
            and auth.get('origin') == scope['origin'] and auth.get('session_cookie_name') == 'quillmd_doctor_session'
            and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', auth.get('actor_id', ''))
            and auth.get('session_file') == str(session)
            and sha(protected(session)) == auth.get('session_sha256'), 'normal_admin_mfa_prerequisite')
    authenticated = datetime.fromisoformat(auth.get('authenticated_at', '').replace('Z', '+00:00'))
    require(authenticated.tzinfo is not None
            and 0 <= (datetime.now(timezone.utc) - authenticated).total_seconds() < 1800,
            'normal_admin_auth_timestamp')
    return {'scope': scope, 'artifact_sha256': hashes, 'normal_admin_authentication_sha256': sha(auth_raw),
            'installer_provider_calls': 0, 'delegated_requests_are_separate': True}


def acceptance_child(argv, destination, label, deadline, *, ruled):
    """Bound the fixed child process group; retain unknown jobs and never repeat a child."""
    remaining = deadline - time.monotonic()
    require(remaining > 0, 'acceptance_phase_deadline')
    env = dict(os.environ)
    if ruled:
        # Existing nested ruled watchdog survives the operator and retains its normal kill/cleanup policy.
        env['RULED_ACT_MAX_SECS'] = str(max(1, int(remaining)))
    with subprocess.Popen(argv, cwd=SOURCE, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True) as process:
        try:
            stdout, stderr = process.communicate(timeout=remaining)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.communicate(timeout=5)
            except BaseException:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                process.communicate(timeout=10)
            raise Refusal('acceptance_child_stopped_unknown_outcome') from None
        write_new(destination / (label + '-stdout.log'), stdout)
        write_new(destination / (label + '-stderr.log'), stderr)
        require(process.returncode == 0 and len(stdout) <= 2 * 1024 * 1024
                and len(stderr) <= 2 * 1024 * 1024 and time.monotonic() < deadline, 'acceptance_child_failed')
    return {'exit_code': 0, 'stdout_sha256': sha(stdout), 'stderr_sha256': sha(stderr), 'automatic_retries': 0}


def installed_acceptance(target, directory, prepared, *, continuation=False):
    """Caller retains the installation exclusion through both exact reviewed children."""
    require(prepared == acceptance_preparation(declaration()[1], target, continuation=continuation), 'acceptance_preparation_drift')
    deadline = time.monotonic() + ACCEPTANCE_SECONDS
    child_scope = {'complete': False, 'installer_provider_calls': 0,
                   'delegated_maximum_generations': 5, 'delegated_maximum_transcriptions': 1,
                   'delegated_provider_usd_limit': '0.70', 'automatic_retries': 0,
                   'maximum_seconds': ACCEPTANCE_SECONDS}
    write_new(directory / 'acceptance-started.json', encode(child_scope))
    browser = ['bash', str(SOURCE / 'scripts/run-ruled-mutation.sh'), '--declaration', DECL, '--',
               '/usr/bin/node', str(ACCEPTANCE_BROWSER), '--execute', target, str(directory)]
    child_scope['browser'] = acceptance_child(browser, directory, 'acceptance-browser', deadline, ruled=True)
    verifier = [str(APP / '.venv/bin/python'), '-B', str(ACCEPTANCE_VERIFIER), '--verify']
    child_scope['verifier'] = acceptance_child(verifier, directory, 'acceptance-verifier', deadline, ruled=False)
    verification_raw = protected(ACCEPTANCE_OUTPUT / 'independent-verification.json', 16 * 1024 * 1024)
    verification = json.loads(verification_raw)
    require(verification.get('complete') is True and time.monotonic() < deadline, 'independent_acceptance_incomplete')
    child_scope.update(complete=True, independent_verification_sha256=sha(verification_raw))
    write_new(directory / 'acceptance-complete.json', encode(child_scope))
    return child_scope


def continuation_policy(contract):
    """One named failed attempt; prospective source-qualified repair, never a retry."""
    policy = contract.get('continuation_contract', {})
    require(policy.get('qualified') is True and policy.get('original_activation') == str(CONTINUATION_ORIGINAL)
            and policy.get('original_release') == CONTINUATION_RELEASE
            and policy.get('original_receipts') == CONTINUATION_RECEIPTS
            and policy.get('repair_source_paths') == sorted(CONTINUATION_REPAIRS)
            and policy.get('resume_output') == str(CONTINUATION_OUTPUT)
            and policy.get('resume_attempt_marker') == str(CONTINUATION_ATTEMPT)
            and policy.get('admin_evidence_directory') == str(CONTINUATION_ADMIN)
            and policy.get('admin_preparation_path') == str(CONTINUATION_PREPARATION)
            and policy.get('admission_verifier_path') == str(ACCEPTANCE_VERIFIER)
            and policy.get('preparation_maximum_seconds') == 180
            and policy.get('original_backup_reused') is True and policy.get('new_capture') is False
            and policy.get('provider_calls') == 0 and policy.get('automatic_retries') is False
            and policy.get('publisher_admission_policy', {}).get('qualified') is True,
            'prospective_continuation_scope')
    for key, path in (('admin_preparation_sha256', CONTINUATION_PREPARATION),
                      ('admission_verifier_sha256', ACCEPTANCE_VERIFIER)):
        expected = policy.get(key)
        require(re.fullmatch('[a-f0-9]{64}', expected or '') is not None
                and sha(protected(path, 2 * 1024 * 1024)) == expected, 'continuation_reviewed_artifact')
    return policy


def continuation_original(policy, backup):
    """Authenticate retained evidence and ORIGINAL coverage, not a fresh current capture."""
    rows = {}
    for name, digest in CONTINUATION_RECEIPTS.items():
        raw = protected(CONTINUATION_ORIGINAL / name, 32 * 1024 * 1024)
        require(sha(raw) == digest, 'continuation_original_receipt_identity')
        rows[name] = json.loads(raw)
    original = rows['failed.json']
    require(original.get('complete') is False and original.get('acceptance_started') is False
            and original.get('provider_calls') == 0 and original.get('stage') == 'failed'
            and original.get('source', {}).get('operator_commit') == CONTINUATION_RELEASE
            and original.get('before') == original.get('stopped_baseline')
            and sha(encode(original['before'])) == policy.get('original_before_sha256')
            and sha(encode(original['expected_population'])) == policy.get('original_expected_population_sha256'),
            'continuation_original_failure_scope')
    require(rows['fresh_backup_verified.json'].get('backup') == original.get('backup')
            and rows['fresh_backup_verified.json'].get('before') == original['before']
            and rows['static_installed.json'].get('expected_population') == original['expected_population']
            and {k: v for k, v in original['expected_population'].items() if k != 'static'}
            == {k: v for k, v in original['before'].items() if k != 'static'}
            and sha(protected(CAPTURE_ATTEMPT)) == CONTINUATION_RECEIPTS['fresh-backup-attempt.json'],
            'continuation_retained_capture_and_population')
    receipt = original['backup']
    require(receipt.get('capture_attempts') == 1 and receipt.get('provider_calls') == 0
            and receipt.get('local_encrypted_capture') is True and receipt.get('offsite_upload') is False,
            'continuation_original_capture_scope')
    authenticated = verify_backup(Path(receipt['backup_directory']), receipt['manifest_cipher_sha256'],
                                  original['before'], backup)
    authenticated['all_original_tables_covered'] = authenticated.pop('all_current_tables_covered')
    authenticated.update(coverage_basis='original_before', current_population_covered=False,
                         new_capture_performed=False)
    cipher = backup.key_at(KEY)
    before = cipher.decrypt(protected(CONTINUATION_ORIGINAL / 'environment-before.fernet', 65536))
    current = cipher.decrypt(protected(CONTINUATION_ORIGINAL / 'environment-after.fernet', 65536))
    declared, configuration = render(before, CONTINUATION_RELEASE)
    require(current == declared and sha(before) == original['configuration']['before_sha256']
            and sha(current) == original['configuration']['after_sha256'], 'continuation_original_environment')
    return original, before, current, authenticated, cipher


def continuation_admission(phase, target, directory, policy, original, *, host, backup, storage, deadline):
    """Fixed independently qualified read-only adjudicator; locally recheck its entire result."""
    require(phase in ('before-auth', 'after-auth') and directory == CONTINUATION_OUTPUT,
            'continuation_admission_phase')
    require(sha(protected(ACCEPTANCE_VERIFIER, 2 * 1024 * 1024)) == policy['admission_verifier_sha256'],
            'continuation_admission_source_drift')
    argv = [str(APP / '.venv/bin/python'), '-B', str(ACCEPTANCE_VERIFIER), '--admit-continuation',
            '--phase', phase, '--continuation-directory', str(directory)]
    child = acceptance_child(argv, directory, 'admission-' + phase, deadline, ruled=False)
    stdout = protected(directory / ('admission-' + phase + '-stdout.log'), 2 * 1024 * 1024)
    require(sha(stdout) == child['stdout_sha256'], 'continuation_admission_stdout_identity')
    summary = json.loads(stdout)
    report_path = directory / ('admission-' + phase + '.json')
    require(summary.get('complete') is True and summary.get('phase') == phase
            and summary.get('release') == target
            and summary.get('report') == str(report_path) and summary.get('provider_calls') == 0
            and summary.get('database_writes') == 0, 'continuation_admission_summary')
    raw = protected(report_path, 32 * 1024 * 1024)
    require(sha(raw) == summary.get('sha256'), 'continuation_admission_report_identity')
    report = json.loads(raw)
    require(report.get('format') == 1 and report.get('complete') is True and report.get('phase') == phase
            and report.get('release') == target
            and report.get('original_activation') == str(CONTINUATION_ORIGINAL)
            and report.get('original_failed_sha256') == CONTINUATION_RECEIPTS['failed.json']
            and report.get('original_backup_manifest_cipher_sha256') == original['backup']['manifest_cipher_sha256']
            and report.get('original_records_adjudicated') is True
            and report.get('provider_calls') == 0 and report.get('database_writes') == 0,
            'continuation_original_record_adjudication')
    current = snapshot(host, backup, storage)
    require(current['database'] == report.get('current_database_fingerprint')
            and current['database'] == summary.get('current_database_fingerprint'), 'continuation_admission_population_race')
    require({k: v for k, v in current.items() if k != 'database'}
            == {k: v for k, v in original['expected_population'].items() if k != 'database'},
            'continuation_files_static_mail_or_security_delta')
    return {'path': str(report_path), 'sha256': sha(raw), 'report': report, 'child': child}, current


def resume_pre_acceptance(args, contract, evidence, source_info, *, host, backup, storage, exclusion, env_writer):
    """Preserve the failed install and legitimate lifecycle rows; no original-act replay."""
    policy = continuation_policy(contract)
    require(getattr(args, 'acceptance_v2', False) is True and not getattr(args, 'fresh_backup', False)
            and not getattr(args, 'rollback', False), 'continuation_explicit_phase')
    require(not os.path.lexists(CONTINUATION_ATTEMPT) and not os.path.lexists(CONTINUATION_OUTPUT)
            and not os.path.lexists(ACCEPTANCE_OUTPUT), 'continuation_attempt_or_campaign_replay')
    storage_before = storage_admission(contract, 'continuation_preparation')
    original, original_environment, current, backup_proof, cipher = continuation_original(policy, backup)
    require(protected(APP / '.env', 65536) == current, 'continuation_installed_environment')
    updated, configuration = render(original_environment, args.operator_commit)
    # Exact prior canonical assignments mean the continuation changes ONLY the source stamp.
    release_line = ('QUILLMD_RELEASE_SHA="' + args.operator_commit + '"\n').encode()
    old_release_line = ('QUILLMD_RELEASE_SHA="' + CONTINUATION_RELEASE + '"\n').encode()
    require(updated.count(release_line) == 1 and updated.replace(release_line, old_release_line) == current,
            'continuation_release_only_environment')
    configuration['before_sha256'] = sha(current)
    CONTINUATION_OUTPUT.mkdir(mode=0o700)
    write_new(CONTINUATION_OUTPUT / 'environment-before.fernet', cipher.encrypt(current))
    write_new(CONTINUATION_OUTPUT / 'environment-after.fernet', cipher.encrypt(updated))
    outcome = {'format': 1, 'complete': False, 'stage': 'continuation_prepared', 'provider_calls': 0,
               'started_at': datetime.now(timezone.utc).isoformat(), 'source': source_info,
               'directory': str(CONTINUATION_OUTPUT), 'installed_engine_baseline': BASELINE,
               'configuration': configuration, 'qualification': evidence, 'backup': original['backup'],
               'continuation': {'original_activation': str(CONTINUATION_ORIGINAL),
                   'original_receipts': policy['original_receipts'], 'original_release': CONTINUATION_RELEASE,
                   'original_before': original['before'], 'original_expected_population': original['expected_population'],
                   'original_backup': original['backup'], 'original_backup_authentication': backup_proof,
                   'health_session': policy['health_session'], 'new_capture': False, 'original_attempt_replayed': False},
               'storage_admission': [storage_before], 'acceptance_started': False}
    def checkpoint(stage):
        outcome['stage'] = stage
        outcome['storage_admission'].append(storage_admission(contract, stage))
        write_new(CONTINUATION_OUTPUT / (stage + '.json'), encode(outcome))
        print(json.dumps({'stage': stage, 'complete': outcome['complete'], 'provider_calls': 0,
                          'evidence_directory': str(CONTINUATION_OUTPUT)}, sort_keys=True), flush=True)
    checkpoint('prepared')
    mutation_started = False
    try:
        exclusion.bind_runtime(RUNTIME)
        with operation_locks(), exclusion.hold('legacy-model-continuation:' + args.operator_commit[:12]):
            try:
                for unit in UNITS + OPERATIONS:
                    state = host.state(unit)
                    require(state.get('ActiveState') in ('inactive', 'failed') and state.get('MainPID') == '0',
                            'continuation_private_or_operator_active')
                require(git(ROOT, 'rev-parse', 'HEAD').strip().decode() == CONTINUATION_RELEASE
                        and protected(APP / '.env', 65536) == current
                        and not os.path.lexists(CONTINUATION_ATTEMPT), 'continuation_initial_identity_race')
                preparation_deadline = time.monotonic() + policy['preparation_maximum_seconds']
                proof, before = continuation_admission('before-auth', args.operator_commit, CONTINUATION_OUTPUT,
                    policy, original, host=host, backup=backup, storage=storage,
                    deadline=preparation_deadline)
                require(time.monotonic() < preparation_deadline, 'continuation_preparation_bound')
                outcome['continuation']['admission_before_auth'] = proof
                outcome['before_auth'] = before
                checkpoint('original_records_admitted')
                require(time.monotonic() < preparation_deadline, 'continuation_preparation_bound')
                deadline = time.monotonic() + COMPLETION_SECONDS
                require(time.monotonic() < deadline, 'continuation_completion_bound')
                write_new(CONTINUATION_ATTEMPT, encode({'format': 1, 'attempt': 1, 'source': args.operator_commit,
                    'original_activation': str(CONTINUATION_ORIGINAL), 'directory': str(CONTINUATION_OUTPUT),
                    'automatic_retries': False, 'provider_calls': 0}))
                mutation_started = True
                require(time.monotonic() < deadline, 'continuation_completion_bound')
                git(ROOT, 'merge', '--ff-only', args.operator_commit)
                require(time.monotonic() < deadline, 'continuation_completion_bound')
                env_writer.replace_environment(APP / '.env', current, updated)
                require(snapshot(host, backup, storage) == before, 'continuation_stopped_preservation')
                checkpoint('configuration_written')
                # Authentication has no worker/provider transport. Retain every normal auth/audit row.
                for unit in UNITS[:2]:
                    require(time.monotonic() < deadline, 'continuation_completion_bound')
                    host.service('start', unit)
                outcome['web_units_before_auth'] = await_service_boundary(host, storage, args.operator_commit,
                                                                         worker_required=False)
                require(host.state(UNITS[2]).get('MainPID') == '0'
                        and host.state(UNITS[2]).get('ActiveState') in ('inactive', 'failed'),
                        'continuation_worker_before_auth')
                outcome['health_before_auth'] = await_health(args.operator_commit)
                require(snapshot(host, backup, storage) == before, 'continuation_pre_auth_start_preservation')
                require(sha(protected(CONTINUATION_PREPARATION, 2 * 1024 * 1024))
                        == policy['admin_preparation_sha256'], 'continuation_auth_source_drift')
                auth = ['bash', str(SOURCE / 'scripts/run-ruled-mutation.sh'), '--declaration', DECL, '--',
                        '/usr/bin/node', str(CONTINUATION_PREPARATION), '--execute-continuation',
                        args.operator_commit, str(CONTINUATION_OUTPUT)]
                require(time.monotonic() < deadline, 'continuation_completion_bound')
                outcome['continuation']['normal_authentication_child'] = acceptance_child(auth, CONTINUATION_OUTPUT,
                    'normal-authentication', min(deadline, time.monotonic() + policy['preparation_maximum_seconds']), ruled=True)
                acceptance = acceptance_preparation(contract, args.operator_commit, continuation=True)
                outcome['acceptance_preparation'] = acceptance
                require(time.monotonic() < deadline, 'continuation_completion_bound')
                proof, admitted = continuation_admission('after-auth', args.operator_commit, CONTINUATION_OUTPUT,
                    policy, original, host=host, backup=backup, storage=storage, deadline=deadline)
                require(time.monotonic() < deadline, 'continuation_completion_bound')
                outcome['continuation']['admission_after_auth'] = proof
                outcome['before'] = outcome['stopped_baseline'] = outcome['expected_population'] = admitted
                outcome['baseline_phase'] = 'after_normal_authentication_before_worker_start'
                checkpoint('normal_authentication_admitted')
                require(host.state(UNITS[2]).get('MainPID') == '0'
                        and host.state(UNITS[2]).get('ActiveState') in ('inactive', 'failed'),
                        'continuation_worker_during_auth')
                require(time.monotonic() < deadline, 'continuation_completion_bound')
                host.service('start', UNITS[2])
                outcome['units_after'] = await_service_boundary(host, storage, args.operator_commit)
                outcome['worker_configuration_provenance'] = host.worker_configuration(updated, args.operator_commit,
                                                                                      outcome['units_after'])
                require(all(outcome['worker_configuration_provenance']['values'].get(key) == value
                            for key, value in configuration['values'].items()), 'continuation_worker_configuration')
                outcome['health'] = await_health(args.operator_commit)
                require(snapshot(host, backup, storage) == admitted, 'continuation_post_start_preservation')
                require(time.monotonic() < deadline, 'continuation_completion_bound')
                outcome['complete'] = True
                checkpoint('complete')
                require(time.monotonic() < deadline, 'continuation_completion_bound')
                outcome['acceptance_started'] = True
                outcome['acceptance'] = installed_acceptance(args.operator_commit, CONTINUATION_OUTPUT, acceptance,
                                                            continuation=True)
            except BaseException as error:
                outcome['complete'] = False
                outcome['failure_kind'] = type(error).__name__
                if mutation_started and not outcome['acceptance_started']:
                    outcome['fail_stop'] = best_effort_private_stop(host)
                best_effort_capture(outcome, 'failure_checkpoint', lambda: checkpoint('failed'))
                raise Refusal('continuation_failed_no_automatic_retry') from None
    except BaseException as error:
        outcome['complete'] = False
        outcome.setdefault('failure_kind', type(error).__name__)
        if mutation_started and not outcome['acceptance_started'] and 'fail_stop' not in outcome:
            outcome['fail_stop'] = best_effort_private_stop(host)
        if 'failure_checkpoint' not in outcome and 'failure_checkpoint_capture_failure' not in outcome:
            best_effort_capture(outcome, 'failure_checkpoint', lambda: checkpoint('failed'))
        raise Refusal('continuation_failed_no_automatic_retry') from None
    return outcome


def execute(args, contract, evidence, source_info, *, host, backup, storage, exclusion, env_writer):
    require(getattr(args, 'fresh_backup', False) is True, 'explicit_one_fresh_capture_required')
    require(contract.get('rollback_qualified') is True, 'prospectively_qualified_recovery_required')
    storage_before = storage_admission(contract, 'preparation')
    backup.private_dir(CAPTURE_ATTEMPT.parent)
    require(not os.path.lexists(CAPTURE_ATTEMPT), 'fresh_capture_attempt_already_consumed')
    acceptance = acceptance_preparation(contract, args.operator_commit) if getattr(args, 'acceptance_v2', False) else None
    original = protected(APP / '.env', 65536)
    require(sha(original) == contract.get('environment_before_sha256'), 'declared_environment_baseline')
    before_values = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    require(before_values.get('QUILLMD_RELEASE_SHA') == BASELINE, 'running_release_baseline')
    updated, configuration = render(original, args.operator_commit)
    health(BASELINE, probe_preview=True)
    units_before = service_boundary(host, storage, BASELINE)
    destination = RUNTIME / ('legacy-model-demo-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    destination.mkdir(mode=0o700)
    cipher = backup.key_at(KEY)
    write_new(destination / 'environment-before.fernet', cipher.encrypt(original))
    write_new(destination / 'environment-after.fernet', cipher.encrypt(updated))
    static_preparation = prepare_static(destination, contract)
    outcome = {'format': 1, 'complete': False, 'stage': 'prepared', 'provider_calls': 0,
               'source': source_info, 'configuration': configuration, 'qualification': evidence,
               'units_before': units_before,
               'directory': str(destination), 'installed_engine_baseline': BASELINE,
               'acceptance_preparation': acceptance, 'acceptance_started': False,
               'static_preparation': static_preparation, 'storage_admission': [storage_before]}
    def checkpoint(stage):
        outcome['stage'] = stage
        outcome['storage_admission'].append(storage_admission(contract, stage))
        write_new(destination / (stage + '.json'), encode(outcome))
        print(json.dumps({'stage': stage, 'complete': outcome['complete'], 'provider_calls': 0,
                          'evidence_directory': str(destination)}, sort_keys=True), flush=True)
    checkpoint('compilation_ready')
    deadline = time.monotonic() + COMPLETION_SECONDS
    private_stop_started = False
    try:
        exclusion.bind_runtime(RUNTIME)
        with operation_locks(), exclusion.hold('legacy-model-demo:' + args.operator_commit[:12]):
            try:
                for unit in OPERATIONS:
                    state = host.state(unit)
                    require(state.get('ActiveState') in ('inactive', 'failed') and state.get('MainPID') == '0',
                            'active_operator_operation')
                require(not os.path.lexists(CAPTURE_ATTEMPT), 'fresh_capture_attempt_already_consumed')
                # Publication is already excluded before the authoritative baseline exists.
                before = snapshot(host, backup, storage)
                outcome['before'] = before
                require(service_boundary(host, storage, BASELINE) == units_before, 'pre_drain_unit_identity')
                checkpoint('prepared')
                # Freeze new admission before draining. Refuse unknowns; never cancel/replay jobs.
                private_stop_started = True
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
                outcome['backup'] = capture_current_backup(backup, stopped, destination, contract)
                require(snapshot(host, backup, storage) == stopped, 'fresh_capture_population_preservation')
                checkpoint('fresh_backup_verified')
                require(time.monotonic() < deadline, 'activation_bound')
                if source_info['shared_head'] != args.operator_commit:
                    git(ROOT, 'merge', '--ff-only', args.operator_commit)
                # Compilation was isolated before the stop; no DB, packages or unit policy changes.
                env_writer.replace_environment(APP / '.env', original, updated)
                checkpoint('configuration_written')
                require(snapshot(host, backup, storage) == stopped, 'stopped_preservation_failure')
                outcome['static_transition'] = install_static(static_preparation)
                expected_population = dict(stopped, static=inventory(APP / 'staticfiles'))
                require(snapshot(host, backup, storage) == expected_population, 'static_only_population_delta')
                outcome['expected_population'] = expected_population
                checkpoint('static_installed')
                for unit in (UNITS[2], UNITS[0], UNITS[1]):
                    host.service('start', unit)
                outcome['units_after'] = await_service_boundary(host, storage, args.operator_commit)
                require(all(outcome['units_after'][unit]['MainPID'] != units_before[unit]['MainPID']
                            and outcome['units_after'][unit]['ExecMainStartTimestampMonotonic']
                            != units_before[unit]['ExecMainStartTimestampMonotonic'] for unit in UNITS),
                        'service_restart_identity')
                outcome['worker_configuration_provenance'] = host.worker_configuration(
                    updated, args.operator_commit, outcome['units_after'])
                require(all(outcome['worker_configuration_provenance']['values'].get(key) == value
                            for key, value in configuration['values'].items()), 'actual_worker_configuration')
                outcome['health'] = await_health(args.operator_commit)
                require(snapshot(host, backup, storage) == expected_population, 'post_start_preservation_failure')
                require(time.monotonic() < deadline, 'activation_bound')
                outcome['complete'] = True
                checkpoint('complete')
                if acceptance is not None:
                    # This boundary is conservative: no baseline rollback or private fail-stop after it.
                    outcome['acceptance_started'] = True
                    outcome['acceptance'] = installed_acceptance(args.operator_commit, destination, acceptance)
            except BaseException as error:
                outcome['complete'] = False
                outcome['failure_kind'] = type(error).__name__
                outcome['private_stop_started'] = private_stop_started
                if getattr(error, 'reason', None):
                    outcome['managed_helper_reason'] = error.reason
                    outcome['managed_helper_cleanup_complete'] = error.cleanup_complete
                if private_stop_started and not outcome['acceptance_started']:
                    outcome['fail_stop'] = best_effort_private_stop(host)
                    # Retain the original exclusion: the publisher cannot invalidate recovery's baseline.
                    best_effort_capture(outcome, 'recovery', lambda: recover_baseline(
                        args.operator_commit, destination, outcome, original, updated, contract=contract,
                        host=host, backup=backup, storage=storage, env_writer=env_writer))
                    if not outcome.get('recovery', {}).get('complete'):
                        outcome['recovery_fail_stop'] = best_effort_private_stop(host)
                    best_effort_capture(outcome, 'recovery_checkpoint', lambda: write_new(
                        destination / 'recovery.json', encode({'activation_complete': False,
                        'original_failure_kind': outcome['failure_kind'],
                        'recovery': outcome.get('recovery'),
                        'recovery_capture_failure': outcome.get('recovery_capture_failure')})))
                best_effort_capture(outcome, 'failure_checkpoint', lambda: checkpoint('failed'))
                raise Refusal('activation_failed_recovery_required') from None
    except BaseException as error:
        # Fail-stop is independent of disk availability and every diagnostic operation.
        outcome['complete'] = False
        outcome.setdefault('failure_kind', type(error).__name__)
        outcome['private_stop_started'] = private_stop_started
        if private_stop_started and not outcome['acceptance_started'] and not outcome.get('recovery', {}).get('complete'):
            outcome['fail_stop'] = best_effort_private_stop(host)
        elif not private_stop_started:
            outcome['fail_stop'] = {}
        if getattr(error, 'reason', None):
            outcome['managed_helper_reason'] = error.reason
            outcome['managed_helper_cleanup_complete'] = error.cleanup_complete
        best_effort_capture(outcome, 'actual_environment_sha256_on_failure', lambda: sha(protected(APP / '.env', 65536)))
        best_effort_capture(outcome, 'actual_shared_head_on_failure', lambda: git(ROOT, 'rev-parse', 'HEAD').strip().decode())
        if 'failure_checkpoint' not in outcome and 'failure_checkpoint_capture_failure' not in outcome:
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


def admit_recovery_population(prepared, host, backup, storage):
    """Strict all-table admission; no publisher/acceptance/unknown-row exception."""
    before = snapshot(host, backup, storage)
    require({key: value for key, value in before.items() if key != 'static'}
            == {key: value for key, value in prepared['before'].items() if key != 'static'},
            'rollback_acceptance_or_population_changed')
    return before


def recover_baseline(target, directory, prepared, original, expected, *, contract, host, backup, storage, env_writer):
    """Only inside an existing exclusion after private drain; never restores database history."""
    require(contract.get('rollback_qualified') is True, 'prospectively_qualified_recovery_required')
    started = time.monotonic();deadline = started + RECOVERY_SECONDS
    admission = [storage_admission(contract, 'recovery_preparation')]
    require(all(host.state(unit).get('ActiveState') == 'inactive'
                and host.state(unit).get('MainPID') == '0' for unit in UNITS), 'recovery_private_drain')
    current = protected(APP / '.env', 65536)
    require(current in (original, expected), 'rollback_exact_expected_environment')
    require(git(ROOT, 'rev-parse', 'HEAD').strip().decode() in (BASELINE, target), 'rollback_source_identity')
    restored = restore_environment(original, current, BASELINE)
    before = admit_recovery_population(prepared, host, backup, storage)
    result = {'complete': False, 'provider_calls': 0, 'restored_source': BASELINE,
              'current_sha256': sha(current), 'restored_sha256': sha(restored),
              'database_restore_performed': False, 'storage_admission': admission}
    result['static_recovery'] = restore_static(prepared['static_preparation'], directory)
    admission.append(storage_admission(contract, 'recovery_static_restored'))
    require(time.monotonic() < deadline, 'recovery_completion_bound')
    result['source_recovery'] = restore_source(target)
    require(time.monotonic() < deadline, 'recovery_completion_bound')
    env_writer.replace_environment(APP / '.env', current, restored)
    expected_population = dict(before, static=inventory(APP / 'staticfiles'))
    require(snapshot(host, backup, storage) == expected_population, 'rollback_stopped_preservation')
    for unit in (UNITS[2], UNITS[0], UNITS[1]):
        require(time.monotonic() < deadline, 'recovery_completion_bound')
        host.service('start', unit)
    result['units_after'] = await_service_boundary(host, storage, BASELINE)
    result['worker_configuration_provenance'] = host.worker_configuration(restored, BASELINE, result['units_after'])
    parsed = dotenv_values(stream=StringIO(restored.decode()), interpolate=False)
    require(all(result['worker_configuration_provenance']['values'].get(key) == parsed.get(key)
                for key in (*MODEL_VALUES, 'QUILLMD_RELEASE_SHA')), 'rollback_worker_configuration_provenance')
    await_health(BASELINE)
    require(snapshot(host, backup, storage) == expected_population, 'rollback_post_start_preservation')
    require(time.monotonic() < deadline, 'recovery_completion_bound')
    admission.append(storage_admission(contract, 'recovery_complete'))
    result.update(complete=True, preserved=expected_population, elapsed_seconds=time.monotonic() - started,
                  completion_limit_seconds=RECOVERY_SECONDS)
    return result


def rollback(args, source_info, *, contract, host, backup, storage, exclusion, env_writer):
    storage_before = storage_admission(contract, 'rollback_preparation')
    directory = args.activation_directory
    require(directory and directory.is_relative_to(RUNTIME) and directory.resolve(strict=True) == directory
            and directory.name.startswith('legacy-model-demo-'), 'rollback_protected_directory')
    backup.private_dir(directory)
    cipher = backup.key_at(KEY)
    original = cipher.decrypt(protected(directory / 'environment-before.fernet', 65536))
    expected = cipher.decrypt(protected(directory / 'environment-after.fernet', 65536))
    prepared = json.loads(protected(directory / 'prepared.json', 16 * 1024 * 1024))
    require(prepared.get('source', {}).get('operator_commit') == args.operator_commit
            and prepared.get('configuration', {}).get('before_sha256') == sha(original), 'rollback_preparation_identity')
    current = protected(APP / '.env', 65536)
    require(current in (original, expected), 'rollback_exact_expected_environment')
    actual_source = git(ROOT, 'rev-parse', 'HEAD').strip().decode()
    require(actual_source in (BASELINE, args.operator_commit), 'rollback_source_identity')
    restored = restore_environment(original, current, BASELINE)
    receipt = {'format': 1, 'complete': False, 'provider_calls': 0, 'stage': 'rollback_prepared',
               'source': source_info, 'activation_directory': str(directory),
               'current_sha256': sha(current), 'restored_sha256': sha(restored),
               'restored_source': BASELINE, 'database_restore_performed': False,
               'storage_admission': [storage_before]}
    destination = RUNTIME / ('legacy-model-rollback-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    destination.mkdir(mode=0o700)
    write_new(destination / 'prepared.json', encode(receipt))
    private_stop_started = False
    try:
        exclusion.bind_runtime(RUNTIME)
        with operation_locks(), exclusion.hold('legacy-model-rollback:' + args.operator_commit[:12]):
            try:
                # Refuse any prior cadence or acceptance delta before interrupting coherent services.
                admit_recovery_population(prepared, host, backup, storage)
                private_stop_started = True
                for unit in UNITS:
                    host.service('stop', unit)
                recovered = recover_baseline(args.operator_commit, directory, prepared, original, expected,
                                             contract=contract, host=host, backup=backup, storage=storage,
                                             env_writer=env_writer)
                receipt.update(recovered, stage='rollback_complete')
                write_new(destination / 'complete.json', encode(receipt))
            except BaseException:
                # A partially restarted recovery must stop before diagnostics or publication resumes.
                receipt['fail_stop'] = best_effort_private_stop(host) if private_stop_started else {}
                raise
    except BaseException as error:
        receipt['stage'] = 'rollback_failed'
        receipt['complete'] = False
        receipt['failure_kind'] = type(error).__name__
        receipt['private_stop_started'] = private_stop_started
        if 'fail_stop' not in receipt:
            receipt['fail_stop'] = best_effort_private_stop(host) if private_stop_started else {}
        best_effort_capture(receipt, 'actual_environment_sha256', lambda: sha(protected(APP / '.env', 65536)))
        best_effort_capture(receipt, 'failure_checkpoint', lambda: write_new(destination / 'failed.json', encode(receipt)))
        raise Refusal('rollback_failed_recovery_required') from None
    print(json.dumps({'rollback_complete': True, 'provider_calls': 0, 'evidence_directory': str(destination)}, sort_keys=True))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator-commit')
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--fresh-backup', action='store_true', help='One encrypted local capture under exclusion after private drain.')
    parser.add_argument('--acceptance-v2', action='store_true', help='Retain exclusion for the exact separately bounded synthetic campaign.')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--rollback', action='store_true')
    parser.add_argument('--resume-pre-acceptance', action='store_true',
                        help='One preserving continuation of the exact failed pre-acceptance install; never replays it.')
    parser.add_argument('--activation-directory', type=Path)
    args = parser.parse_args(argv)
    if not args.execute:
        print(json.dumps({'execution_performed': False, 'baseline': BASELINE, 'declaration': DECL,
                          'required_profile': PROFILE, 'required_rates': MODEL_VALUES,
                          'required_outcomes': sorted(OUTCOMES), 'required_evidence_roles': sorted(EVIDENCE_ROLES),
                          'note': 'No environment, provider, service or database is accessed by this plan.'}, sort_keys=True))
        return 0
    raw, contract = declaration()
    require(not args.resume_pre_acceptance or (not args.rollback and not args.fresh_backup),
            'continuation_cli_scope')
    info = source_gate(args.operator_commit, contract, executing=True, recovering=args.rollback,
                       resuming=args.resume_pre_acceptance)
    from .direct_account_access import refuse_legacy_operation
    refuse_legacy_operation()
    exclusion, backup, env_writer, managed, storage = modules()
    if args.resume_pre_acceptance:
        require(args.qualification and args.acceptance_v2, 'continuation_qualification_and_acceptance_required')
        evidence = read_qualification(args.qualification, contract.get('qualification_sha256'))
        resume_pre_acceptance(args, contract, evidence, info, host=Host(managed), backup=backup, storage=storage,
                             exclusion=exclusion, env_writer=env_writer)
        return 0
    if args.rollback:
        require(contract.get('rollback_qualified') is True, 'separately_committed_rollback_required')
        rollback(args, info, contract=contract, host=Host(managed), backup=backup, storage=storage,
                 exclusion=exclusion, env_writer=env_writer)
        return 0
    require(args.qualification and args.fresh_backup, 'qualification_and_explicit_fresh_capture_required')
    evidence = read_qualification(args.qualification, contract.get('qualification_sha256'))
    execute(args, contract, evidence, info, host=Host(managed), backup=backup, storage=storage,
            exclusion=exclusion, env_writer=env_writer)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        raise SystemExit('Legacy model configuration refused or stopped; inspect protected evidence. No automatic retry.') from None
