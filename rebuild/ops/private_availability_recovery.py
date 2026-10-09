"""One preserving availability recovery, without authentication or provider work.

The default describes scope. A cited prospective declaration is required for the
read-only preflight and the single execute. Historical failures remain immutable;
the original encrypted capture covers its original population, never newer rows.
"""
import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import importlib.util
from io import StringIO
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time

from dotenv import dotenv_values
from . import legacy_model_activation as old
from . import repair_source_permissions as source_files
from . import publisher_verification as publisher_judge

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
RUNTIME = APP / '.runtime'
SOURCE = Path(__file__).resolve().parents[2]
DECL = 'docs/foundation/mutations/20261007-quillmd-private-availability-recovery.md'
SELF = 'rebuild/ops/private_availability_recovery.py'
TEST = 'rebuild/ops/test_private_availability_recovery.py'
ENTRY = 'scripts/recover-private-availability.py'
STORAGE = 'docs/foundation/mutations/20261006-owner-dashboard-storage-exception.md'
ALLOWED = frozenset({SELF, TEST, ENTRY, DECL, STORAGE,
    'rebuild/ops/repair_source_permissions.py', 'rebuild/ops/test_repair_source_permissions.py',
    'scripts/repair-quillmd-source-permissions.py',
    'docs/foundation/mutations/20261007-quillmd-source-permissions-repair.md'})
INSTALLED = '4d46a71520275d76a36aa83ddff1a85939711a04'
PREPARED = 'fa331c8e33ccf4ed82c7b0a6c36283f463092f62'
FROZEN_OPERATOR = '89b79c18d6cdbeb2c78595d314df76dd8aa0185e14efa3d4f8b7550a117634f3'
FROZEN_VERIFIER = 'b77a1c48f2a08c8a0a73df6fc945da850bdc5f558254d32a526913409f17683c'
VERIFIER = RUNTIME / 'owner-demo-20261006/verify_installed_acceptance_v2.py'
OUTPUT = RUNTIME / 'private-availability-recovery-20261007'
ATTEMPT = RUNTIME / 'owner-demo-20261006/private-availability-recovery-attempt-20261007.json'
EXTERNAL_UNIT = '/etc/systemd/system/voiceassistmain-product.service'
CONTINUATION_RECEIPTS = {
    'admission-before-auth-stderr.log': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    'admission-before-auth-stdout.log': 'd3251d516db404b60f16079b70ab484cb263c979143cc2e7a60cd78f6868d1f2',
    'admission-before-auth.json': '3fef1193fe72cc468c9dc0366fa7380a1f1cc43b8fc4b5f6e9ee98ef2aa585a3',
    'environment-after.fernet': '6932a6e77392e477045050df816370c562a83ebf20eeb6f35f75015103d567f9',
    'environment-before.fernet': 'b91cc4b0e76d40ad20562c9fa252c402c89946f403d319c88b8ae2267a9cc50d',
    'failed.json': '935910f5e77acd21338439d530866da2970691d3d7b8fe22a72b3764a7bb3c3b',
    'prepared.json': 'f97a4712649005b28bedb60153135c3810b40fa98223ad9c98d3e72e0bdb5a31'}
RESERVE = 20 * 1024 ** 3
ALLOWANCES = {'peak_bytes': 1024 ** 3, 'rollback_bytes': 1024 ** 3, 'background_bytes': 8 * 1024 ** 3}
SECONDS = 240
# Genuine native owner authorization has not been exported or source-qualified.
# A future declaration or self-asserted evidence JSON cannot turn this gate on.
NATIVE_APPROVAL_PROTOCOL_QUALIFIED = False
# Distinct prospective owner decision; it never certifies historical deployment approval.
CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED = True
INSTALLATION_QUALIFIED = True
CURRENT_OWNER_PROTOCOL = 'current-owner-preservation-boundary-v1'
OWNER_EVIDENCE_ROOT = RUNTIME / 'owner-demo-20261006/recovery-20261007/co-tenant-unit-evidence-v1'
CURRENT_OWNER_PINS = {
    'native_evidence': {'path': str(OWNER_EVIDENCE_ROOT / 'native-admin-deployment-evidence-export-v15.json'),
        'sha256': 'b23c70d6811a9a1e14e24a6a495e5d4f0aeca2c4d9c7fc68cf2c2f7d5b77568b'},
    'independent_review': {'path': str(OWNER_EVIDENCE_ROOT / 'native-admin-v15-independent-lineage-adjudication-v1.json'),
        'sha256': '423390761a5de0b994ffe972e1f52f630c97cbf8dc6d8795cd8cda9f67da53ff'},
    'original_metadata': {'uid': 0, 'gid': 0, 'mode': 0o644, 'device': 2050, 'inode': 920060,
        'sha256': '1cea35330b619802a3e785158ae6c452553e55776cd5ef8b2eee27b37de4c543'},
    'current_unit_sha256': 'c80609f72457a8ce056cec3fd19b2bab9c9c1edde5a35098b7071a6989c57e72',
    'old_working_directory': '/opt/voiceassistmain-product/releases/ae8516691733d6a8ee105561',
    'new_working_directory': '/opt/voiceassistmain-product/releases/eeae88c6d13c779d53d7ec7b',
    'source_sha256': 'eeae88c6d13c779d53d7ec7b51f42a9806d21dfa9e4ba6d1f80d40b3204adef1',
    'installation_id': '030f73df-e981-4307-a877-df153aab68f9',
    'manifest': {'path': '/etc/voiceassistmain-product.json',
        'sha256': 'b8271787d7a549efb5ca912fd1367a3983387e9931e04ae87331555543c5fdc8'},
    'installation': {'path': '/var/lib/voiceassistmain-product-installation/030f73df-e981-4307-a877-df153aab68f9.json',
        'sha256': 'd25b84d737287387f66b96e11b092a7144a32d45ba01eed7ed03a5b09c008e9c'},
    'added_files': {
        '/etc/systemd/system/voiceassist-restaurant-tajrish-20261007@.service': '4941c488522385711731689233920e2e967ac7cf0913fdfe1e991ae16a1843a8',
        '/etc/systemd/system/voiceassist-restaurant-tajrish-20261007-retention.service': 'bca8c9da6a0a699d36cd5519517ab09381b5b7ccf4e4e91c01881c22a96706d4',
        '/etc/systemd/system/voiceassist-restaurant-tajrish-20261007-retention.timer': '7981a1d4d0daaaa8466df93430808cd25abd697ef218f354191d9df2973ff27e',
        '/etc/systemd/system/voiceassistmain-restaurant-voice.service': 'e056ccfdda0c571b0069fcb7c18c0ef1d685bc8aeab0a07644de8152a95b5d51'},
    'added_links': {
        '/etc/systemd/system/timers.target.wants/voiceassist-restaurant-tajrish-20261007-retention.timer': '/etc/systemd/system/voiceassist-restaurant-tajrish-20261007-retention.timer',
        '/etc/systemd/system/multi-user.target.wants/voiceassistmain-restaurant-voice.service': '/etc/systemd/system/voiceassistmain-restaurant-voice.service'}}
OWNER_DECISION_PATH = OWNER_EVIDENCE_ROOT / 'owner-current-configuration-preservation-decision-v1.json'
PUBLISHER = 'quillmd-fresh-operations-publisher.service'
PUBLISHER_TIMER = 'quillmd-fresh-operations-publisher.timer'
PUBLISHER_UNIT_PINS = {
    PUBLISHER: '62bdacb5d40862e11c8321cedaadf2a6e6b3c1e583a3557abdde900be8dfd2c9',
    PUBLISHER_TIMER: '4327daca96a0cd4299487060b05a0e48afee762f3dd65f6170a40ebbad6ec12d'}
PUBLISHER_ALIGNMENT = {'protocol': 'one-natural-publication-under-input-exclusions-v1',
    'maximum_wait_seconds': 360, 'poll_interval_seconds': 1,
    'timer_cadence_seconds': 300, 'timer_accuracy_seconds': 15, 'service_timeout_seconds': 60,
    'unit_source_sha256': PUBLISHER_UNIT_PINS, 'manual_publications': 0,
    'timer_or_service_actions': 0, 'provider_calls': 0, 'automatic_retries': False}
PUBLISHER_ROW_FIELDS = frozenset({'id', 'created_at', 'key', 'condition', 'severity', 'healthy',
    'action', 'payload', 'computed_at', 'published_at', 'expected_interval_seconds'})
RULED_BUDGET = {'environment_variable': 'RULED_ACT_MAX_SECS', 'maximum_seconds': 1200,
    'source_checks_seconds': 300, 'natural_wait_seconds': 360, 'publication_drain_seconds': 120,
    'full_readiness_seconds': 90, 'preparation_seconds': 30, 'completion_seconds': SECONDS}


class Refusal(RuntimeError):
    """Only fixed nonsecret labels are permitted at this boundary."""


def require(value, label):
    if not value:
        raise Refusal(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return old.encode(value)


class RuledBudget:
    """Reserve every stage inside the explicitly declared outer watchdog ceiling."""
    def __init__(self, contract):
        require(contract.get('ruled_time_budget') == RULED_BUDGET
                and os.environ.get('RULED_ACT_MAX_SECS') == str(RULED_BUDGET['maximum_seconds'])
                and sum(value for key, value in RULED_BUDGET.items() if key.endswith('_seconds')
                        and key != 'maximum_seconds') <= RULED_BUDGET['maximum_seconds'],
                'availability_explicit_ruled_time_budget')
        self.started = time.monotonic()
        self.deadline = self.started + RULED_BUDGET['maximum_seconds']

    def remaining(self, seconds):
        require(time.monotonic() + seconds < self.deadline, 'availability_ruled_time_budget_remaining')

    @contextmanager
    def stage(self, name, remaining):
        allowance = RULED_BUDGET[name + '_seconds']
        self.remaining(allowance + remaining)
        started = time.monotonic()
        yield
        require(time.monotonic() - started <= allowance, 'availability_ruled_stage_time_budget')
        self.remaining(remaining)

    def proof(self):
        return {**RULED_BUDGET, 'elapsed_seconds': time.monotonic() - self.started,
                'post_admission_completion_deadline_seconds': SECONDS}


def protected(path, maximum=32 * 1024 * 1024):
    return old.protected(path, maximum)


def write_new(path, value):
    old.write_new(path, value if isinstance(value, bytes) else encode(value))


def operator_source_bytes(relative, mode=0o644, *, tree=None, root_fd=None):
    """Use the reviewed public-source reader with an explicit tree descriptor."""
    try:
        if root_fd is None:
            with source_files.open_root(SOURCE if tree is None else tree) as opened:
                return source_files.operator_bytes(relative, mode, opened)
        return source_files.operator_bytes(relative, mode, root_fd)
    except source_files.Refusal:
        raise Refusal('availability_public_source_descriptor_refused') from None



def public_git_blob(tree, revision, relative):
    """Bounded public blob reads; metadata/command reads retain their old ceiling."""
    require(tree in (SOURCE, ROOT) and re.fullmatch('[a-f0-9]{40}', revision or ''),
            'availability_public_git_blob_scope')
    try:
        source_files.relative_path(relative)
        # This already reviewed primitive caps stdout at 16 MiB and sanitizes
        # Git's environment. The 2 MiB frozen command primitive is unchanged.
        return source_files.git(tree, 'show', revision + ':' + relative)
    except source_files.Refusal:
        raise Refusal('availability_public_git_blob_refused') from None


def contract_from_bytes(raw):
    marker = b'<!-- private-availability-contract -->\n```json\n'
    require(raw.count(marker) == 1, 'availability_declaration_contract')
    chunks = raw.split(marker, 1)[1].split(b'\n```', 1)
    require(len(chunks) == 2, 'availability_declaration_close')
    contract = json.loads(chunks[0])
    require(contract.get('format') == 1 and contract.get('readonly_qualified') is True
            and contract.get('installation_qualified') is INSTALLATION_QUALIFIED
            and contract.get('baseline_release') == INSTALLED and contract.get('prepared_release') == PREPARED
            and contract.get('frozen_operator_sha256') == FROZEN_OPERATOR
            and contract.get('frozen_verifier_sha256') == FROZEN_VERIFIER
            and contract.get('output') == str(OUTPUT) and contract.get('attempt') == str(ATTEMPT)
            and contract.get('provider_calls') == 0 and contract.get('authentication_submissions') == 0
            and contract.get('new_capture') is False and contract.get('database_restore') is False
            and contract.get('automatic_retries') is False,
            'availability_prospective_scope')
    require(contract.get('original_policy') == original_qualified_policy(), 'availability_original_policy_identity')
    require(contract.get('publisher_alignment') == PUBLISHER_ALIGNMENT,
            'availability_publisher_alignment_contract')
    require(contract.get('ruled_time_budget') == RULED_BUDGET, 'availability_ruled_time_budget_contract')
    return contract


def load_contract():
    return contract_from_bytes(operator_source_bytes(DECL))


def original_qualified_policy():
    raw = old.git(SOURCE, 'show', PREPARED + ':' + old.DECL)
    marker = b'<!-- legacy-model-contract -->\n```json\n'
    require(raw.count(marker) == 1, 'availability_original_qualified_contract')
    contract = json.loads(raw.split(marker, 1)[1].split(b'\n```', 1)[0])
    policy = contract['continuation_contract']
    require(contract['execution_qualified'] is True and policy['qualified'] is True
            and policy['publisher_admission_policy']['qualified'] is True,
            'availability_original_qualification')
    return policy


def source_gate(target, contract):
    require(re.fullmatch('[a-f0-9]{40}', target or '') and SOURCE.is_relative_to(ROOT / '.worktrees')
            and SOURCE.resolve() == SOURCE, 'availability_operator_source')
    require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 1000
            and source_files.SOURCE == SOURCE and source_files.ROOT == ROOT,
            'availability_operator_native_source_binding')
    require(old.git(SOURCE, 'rev-parse', 'HEAD').strip().decode() == target
            and not old.git(SOURCE, 'status', '--porcelain', '--untracked-files=no').strip(),
            'availability_operator_clean')
    old.git(SOURCE, 'merge-base', '--is-ancestor', PREPARED, target)
    changes = set(old.git(SOURCE, 'diff', '--name-only', PREPARED, target).decode().splitlines())
    require(changes <= ALLOWED and {SELF, TEST, ENTRY, DECL} <= changes
            and contract.get('approved_source_paths') == sorted(changes), 'availability_source_scope')
    require(old.git(ROOT, 'branch', '--show-current').strip() == b'main'
            and old.git(ROOT, 'rev-parse', 'HEAD').strip().decode() == INSTALLED
            and not old.git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(),
            'availability_installed_clean_source')
    # Admit the complete operator's metadata and Git bytes before citation or
    # private evidence. Keep checked declaration/citation bytes; never reopen
    # their path to execute or compare them later.
    retained_paths = {DECL, 'rebuild/ops/legacy_model_activation.py',
                      'scripts/check-citation.sh', 'scripts/lib/runs-api.sh'}
    buffers = {}
    with source_files.open_root(SOURCE) as root_fd:
        for line in old.git(SOURCE, 'ls-files', '--stage', '-z').decode().split('\0')[:-1]:
            identity, relative = line.split('\t', 1)
            mode, _, stage = identity.split()
            require(stage == '0' and mode in ('100644', '100755'), 'availability_operator_index_type')
            raw = operator_source_bytes(relative, 0o644 if mode == '100644' else 0o755, root_fd=root_fd)
            require(raw == public_git_blob(SOURCE, target, relative), 'availability_operator_byte_identity')
            if relative.startswith('rebuild/') and relative not in ALLOWED:
                require(raw == public_git_blob(SOURCE, PREPARED, relative),
                        'availability_payload_byte_identity')
            if relative in retained_paths:
                buffers[relative] = raw
    require(set(buffers) == retained_paths, 'availability_operator_retained_source_population')
    require(contract_from_bytes(buffers[DECL]) == contract, 'availability_loaded_declaration_identity')
    # The installed tree contributes only public rebuild source, never an
    # untracked environment, private runtime or symlink destination.
    with source_files.open_root(ROOT) as root_fd:
        for line in old.git(ROOT, 'ls-files', '--stage', '-z', 'rebuild').decode().split('\0')[:-1]:
            identity, relative = line.split('\t', 1)
            mode, _, stage = identity.split()
            source_files.source_path(relative)
            require(stage == '0' and mode in ('100644', '100755'), 'availability_installed_index_type')
            raw = operator_source_bytes(relative, 0o644 if mode == '100644' else 0o755, root_fd=root_fd)
            require(raw == public_git_blob(ROOT, INSTALLED, relative),
                    'availability_installed_byte_identity')
    source_readability(ROOT)
    require(sha(buffers['rebuild/ops/legacy_model_activation.py']) == FROZEN_OPERATOR,
            'availability_frozen_primitive_drift')
    require(os.environ.get('RULED_MUTATION_DECLARATION') == DECL, 'availability_normal_ruled_door')
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(re.fullmatch('[a-f0-9]{40}', commit)
            and old.git(SOURCE, 'log', '-1', '--format=%H', '--', DECL).strip().decode() == commit
            and old.git(SOURCE, 'show', commit + ':' + DECL) == buffers[DECL],
            'availability_committed_declaration')
    require(old.git(ROOT, 'rev-parse', 'origin/main').strip().decode() == target,
            'availability_merged_main_target')
    for revision in (target, PREPARED, INSTALLED):
        source_files.sealed_citation(buffers['scripts/check-citation.sh'], buffers['scripts/lib/runs-api.sh'], revision)
    require(sha(protected(VERIFIER, 2 * 1024 * 1024)) == FROZEN_VERIFIER,
            'availability_frozen_primitive_drift')
    return {'operator_commit': target, 'installed_before': INSTALLED, 'qualified_payload': PREPARED,
            'changed_paths': sorted(changes)}


def source_readability(tree):
    indexed = {}
    for line in old.git(tree, 'ls-files', '--stage', 'rebuild').decode().splitlines():
        identity, relative = line.split('\t', 1)
        mode, _, stage = identity.split()
        require(stage == '0', 'availability_source_index_stage')
        indexed[relative] = mode
    for relative in old.git(tree, 'ls-files', 'rebuild').decode().splitlines():
        path = tree / relative
        require(path.resolve(strict=True) == path and stat.S_ISREG(path.lstat().st_mode)
                and path.stat().st_mode & 0o004, 'availability_source_readability')
        if relative.endswith('.py'):
            require(indexed.get(relative) == '100644' and stat.S_IMODE(path.stat().st_mode) == 0o644,
                    'availability_python_source_mode')
        for parent in (path.parent, *path.parent.parents):
            require(parent.is_dir() and parent.stat().st_mode & 0o001, 'availability_source_traversability')
            if parent == tree:
                break


def forward_source(target):
    # Git's file creation must not inherit the private evidence writer's umask.
    done = subprocess.run(['git', '-C', str(ROOT), 'merge', '--ff-only', target],
                          capture_output=True, timeout=30, umask=0o022)
    require(done.returncode == 0 and len(done.stdout) <= 2 * 1024 * 1024,
            'availability_source_forward_failed')
    require(old.git(ROOT, 'rev-parse', 'HEAD').strip().decode() == target
            and not old.git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(),
            'availability_source_forward_identity')
    source_readability(ROOT)


def release_only_environment(current, target):
    values = dotenv_values(stream=StringIO(current.decode()), interpolate=False)
    require(values.get('QUILLMD_RELEASE_SHA') == INSTALLED
            and values.get('QUILLMD_AI_MODE') == 'live' and values.get('QUILLMD_AI_PROVIDER') == 'anthropic'
            and all(values.get(key) == value for key, value in old.MODEL_VALUES.items())
            and values.get('QUILLMD_PREVIEW_AUTH_ENABLED') == '1'
            and values.get('QUILLMD_APP_BASE_URL') == 'https://app.quillmd.com:9443',
            'availability_current_configuration')
    require(re.fullmatch('[a-f0-9]{40}', target or ''), 'availability_release_format')
    result, count = [], 0
    for line in current.splitlines(keepends=True):
        match = old.ASSIGNMENT.match(line)
        if match and match[1] == b'QUILLMD_RELEASE_SHA':
            count += 1
            result.append(('QUILLMD_RELEASE_SHA="' + target + '"\n').encode())
        else:
            result.append(line)
    updated = b''.join(result)
    require(count == 1 and {k: v for k, v in values.items() if k != 'QUILLMD_RELEASE_SHA'}
            == {k: v for k, v in dotenv_values(stream=StringIO(updated.decode()), interpolate=False).items()
                if k != 'QUILLMD_RELEASE_SHA'}, 'availability_release_only_delta')
    return updated


def storage_admission(contract, phase):
    require(contract.get('storage_authority_path') == STORAGE
            and sha(operator_source_bytes(STORAGE)) == contract.get('storage_authority_sha256')
            and contract.get('storage_allowances') == ALLOWANCES
            and contract.get('storage_minimum_reserve_bytes') == RESERVE,
            'availability_storage_authority')
    measured = os.statvfs(ROOT)
    available = measured.f_bavail * measured.f_frsize
    require(available - sum(ALLOWANCES.values()) >= RESERVE and measured.f_favail > 0,
            'availability_storage_reserve')
    used = (measured.f_blocks - measured.f_bfree) * measured.f_frsize
    return {'phase': phase, 'original_preflight_percentage_verdict': 'RED',
            'task_disposition': 'explicit owner exception', 'available_bytes': available,
            'available_inodes': measured.f_favail, 'current_used_percentage': math.ceil(100 * used / (used + available)),
            'conservative_remaining_allowances': ALLOWANCES,
            'projected_available_bytes': available - sum(ALLOWANCES.values()), 'minimum_reserve_bytes': RESERVE,
            'authority_sha256': contract['storage_authority_sha256']}


def authenticate_chain(contract, backup):
    policy = contract['original_policy']
    require(policy == original_qualified_policy() and policy.get('original_receipts') == old.CONTINUATION_RECEIPTS
            and contract.get('continuation_receipts') == CONTINUATION_RECEIPTS,
            'availability_historical_receipt_population')
    original, before_env, current_env, proof, cipher = old.continuation_original(policy, backup)
    retained = {}
    require({path.name for path in old.CONTINUATION_OUTPUT.iterdir()} == set(CONTINUATION_RECEIPTS),
            'availability_failed_continuation_population')
    for name, digest in CONTINUATION_RECEIPTS.items():
        raw = protected(old.CONTINUATION_OUTPUT / name)
        require(sha(raw) == digest, 'availability_failed_continuation_hash')
        if name.endswith('.json'):
            retained[name] = json.loads(raw)
    failed, prepared, admission = (retained[name] for name in ('failed.json', 'prepared.json', 'admission-before-auth.json'))
    require(failed.get('complete') is False and failed.get('stage') == 'failed'
            and failed.get('provider_calls') == 0 and failed.get('acceptance_started') is False
            and prepared.get('complete') is False and prepared.get('provider_calls') == 0
            and failed['source']['operator_commit'] == prepared['source']['operator_commit'] == PREPARED
            and failed['continuation']['original_receipts'] == prepared['continuation']['original_receipts'] == policy['original_receipts']
            and failed['backup'] == prepared['backup'] == original['backup']
            and admission.get('complete') is True and admission.get('release') == PREPARED
            and admission.get('provider_calls') == admission.get('database_writes') == 0,
            'availability_failed_pre_marker_scope')
    require(not any(os.path.lexists(path) for path in (old.CONTINUATION_ATTEMPT, old.ACCEPTANCE_OUTPUT,
                    old.CONTINUATION_ADMIN, OUTPUT, ATTEMPT)), 'availability_consumed_attempt_or_campaign')
    require(protected(APP / '.env', 65536) == current_env, 'availability_current_encrypted_environment')
    require(cipher.decrypt(protected(old.CONTINUATION_OUTPUT / 'environment-before.fernet', 65536)) == current_env
            and cipher.decrypt(protected(old.CONTINUATION_OUTPUT / 'environment-after.fernet', 65536))
                == release_only_environment(current_env, PREPARED), 'availability_failed_environment_chain')
    return original, current_env, proof, cipher


def frozen_verifier():
    raw = protected(VERIFIER, 2 * 1024 * 1024)
    require(sha(raw) == FROZEN_VERIFIER, 'availability_frozen_verifier')
    spec = importlib.util.spec_from_file_location('_quillmd_availability_readonly_verifier', VERIFIER)
    module = importlib.util.module_from_spec(spec)
    # Compile the already authenticated bytes, avoiding a second unauthenticated read.
    exec(compile(raw, str(VERIFIER), 'exec'), module.__dict__)
    return module


def publisher_observation_connection(conn):
    """Canonicalize only the three timestamp columns on each publisher read.

    PostgreSQL row_to_json omits trailing fractional zeroes. The frozen
    adjudicator parses its initial timestamps, but compares the reread's JSON
    strings directly. Use the same aware UTC representation on both reads;
    preserve every column and all actual timestamp, unit and journal changes.
    This proxy permits only the frozen observer's exact read-only statement.
    """
    class Connection:
        def execute(self, statement):
            require(statement == "SELECT row_to_json(h) AS row FROM core_servicehealth h WHERE key='backup'",
                    'availability_publisher_observation_statement')
            cursor = conn.execute(statement)
            class Cursor:
                def fetchall(self):
                    result = []
                    for item in cursor.fetchall():
                        require(isinstance(item, dict) and isinstance(item.get('row'), dict),
                                'availability_publisher_observation_row')
                        row = dict(item['row'])
                        for name in ('created_at', 'computed_at', 'published_at'):
                            value = row.get(name)
                            require(isinstance(value, (str, datetime)),
                                    'availability_publisher_observation_time')
                            try:
                                stamp = value if isinstance(value, datetime) else datetime.fromisoformat(value)
                            except ValueError:
                                raise Refusal('availability_publisher_observation_time') from None
                            require(stamp.tzinfo is not None, 'availability_publisher_observation_time')
                            row[name] = stamp.astimezone(timezone.utc).isoformat()
                        result.append({**item, 'row': row})
                    return result
            return Cursor()
    return Connection()


def own_unit_properties(unit, properties):
    require(unit in old.UNITS + (PUBLISHER, PUBLISHER_TIMER), 'availability_own_unit_observation_scope')
    raw = old.command(['systemctl', 'show', unit, '--property=' + ','.join(properties)]).decode()
    lines = raw.splitlines()
    require(len(lines) == len(properties) and all('=' in line for line in lines),
            'availability_own_unit_observation_population')
    values = dict(line.split('=', 1) for line in lines)
    require(set(values) == set(properties), 'availability_own_unit_observation_population')
    return values


def publisher_unit_sources():
    """Read only the two owned public unit files through held descriptors."""
    result = {}
    with source_files.open_root(Path('/etc/systemd/system')) as root_fd:
        for name, expected in PUBLISHER_UNIT_PINS.items():
            fd = source_files.open_relative(root_fd, name)
            try:
                before = os.fstat(fd)
                require(stat.S_ISREG(before.st_mode) and before.st_uid == before.st_gid == 0
                        and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o644
                        and not os.listxattr(fd), 'availability_publisher_unit_file_identity')
                raw = source_files.bytes_at(fd, 65536)
                require(sha(raw) == expected, 'availability_publisher_unit_file_source')
                reopened = source_files.open_relative(root_fd, name)
                try:
                    require(source_files.stable(before) == source_files.stable(os.fstat(fd))
                            == source_files.stable(os.fstat(reopened)), 'availability_publisher_unit_file_race')
                finally:
                    os.close(reopened)
                result[name] = {**source_files.metadata(before), 'sha256': expected}
            finally:
                os.close(fd)
    return result


def publisher_observer(backup):
    """Every poll gets a new read-only snapshot, so a natural commit is visible."""
    import psycopg
    from psycopg.rows import dict_row
    options = {**backup.source_options(APP, old.ROLES), 'connect_timeout': 10}
    unit_properties = ('ActiveState', 'SubState', 'MainPID', 'LoadState', 'FragmentPath', 'DropInPaths',
        'NeedDaemonReload', 'InvocationID', 'Result', 'ExecMainStatus', 'ExecMainStartTimestamp', 'ExecMainExitTimestamp')
    timer_properties = ('ActiveState', 'SubState', 'LoadState', 'UnitFileState', 'FragmentPath', 'DropInPaths', 'NeedDaemonReload')
    def observe():
        timer = own_unit_properties(PUBLISHER_TIMER, timer_properties)
        require(timer['SubState'] in ('waiting', 'running')
                and {key: value for key, value in timer.items() if key != 'SubState'}
                    == {'ActiveState': 'active', 'LoadState': 'loaded',
                'UnitFileState': 'enabled', 'FragmentPath': '/etc/systemd/system/' + PUBLISHER_TIMER,
                'DropInPaths': '', 'NeedDaemonReload': 'no'}, 'availability_publisher_timer_boundary')
        unit = own_unit_properties(PUBLISHER, unit_properties)
        require(unit['LoadState'] == 'loaded' and unit['FragmentPath'] == '/etc/systemd/system/' + PUBLISHER
                and unit['DropInPaths'] == '' and unit['NeedDaemonReload'] == 'no',
                'availability_publisher_loaded_boundary')
        with psycopg.connect(**options, row_factory=dict_row) as conn:
            conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            conn.execute("SET LOCAL timezone='UTC'")
            conn.execute("SET LOCAL statement_timeout='10s'")
            flags = conn.execute("SELECT current_user,current_database(),current_setting('transaction_read_only') AS read_only").fetchone()
            require(flags == {'current_user': 'quillmd_backup', 'current_database': 'quillmd_fresh', 'read_only': 'on'},
                    'availability_publisher_readonly_database_identity')
            rows = publisher_observation_connection(conn).execute(
                "SELECT row_to_json(h) AS row FROM core_servicehealth h WHERE key='backup'").fetchall()
            require(len(rows) == 1 and set(rows[0]['row']) == PUBLISHER_ROW_FIELDS,
                    'availability_publisher_observation_population')
        row = rows[0]['row']
        journal = []
        if unit['MainPID'] == '0' and unit['ActiveState'] in ('inactive', 'failed'):
            try:
                end = (datetime.strptime(unit['ExecMainExitTimestamp'], '%a %Y-%m-%d %H:%M:%S UTC')
                       + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S UTC')
            except ValueError:
                raise Refusal('availability_publisher_completed_time') from None
            raw = old.command(['journalctl', '-u', PUBLISHER, '--since', unit['ExecMainStartTimestamp'],
                '--until', end, '-o', 'json', '--no-pager'])
            journal = [(value.get('_SYSTEMD_INVOCATION_ID'), value.get('MESSAGE'))
                       for value in map(json.loads, raw.splitlines())]
        after = own_unit_properties(PUBLISHER, unit_properties)
        timer_after = own_unit_properties(PUBLISHER_TIMER, timer_properties)
        return {'row': row, 'unit': unit, 'timer': timer, 'journal': journal,
                'coherent_unit': after == unit and timer_after == timer}
    return observe


def await_natural_publication(contract, observe):
    """Select one advancing natural publication; never call publish or retry admission."""
    require(contract.get('publisher_alignment') == PUBLISHER_ALIGNMENT, 'availability_publisher_alignment_contract')
    deadline = time.monotonic() + PUBLISHER_ALIGNMENT['maximum_wait_seconds']
    baseline = observe()
    require(time.monotonic() < deadline, 'availability_natural_publication_timeout')
    require(baseline['coherent_unit'] and set(baseline['row']) == PUBLISHER_ROW_FIELDS
            and baseline['row']['key'] == 'backup' and baseline['row']['expected_interval_seconds'] == 300,
            'availability_publisher_alignment_original_row')
    previous_time = datetime.fromisoformat(baseline['row']['computed_at'])
    while time.monotonic() < deadline:
        current = observe()
        require(time.monotonic() < deadline, 'availability_natural_publication_timeout')
        require(set(current['row']) == PUBLISHER_ROW_FIELDS
                and current['row']['expected_interval_seconds'] == 300
                and all(current['row'][key] == baseline['row'][key] for key in ('id', 'created_at', 'key')),
                'availability_publisher_alignment_immutable_identity')
        unit, row = current['unit'], current['row']
        if current['coherent_unit'] and current['timer']['SubState'] == 'waiting' \
                and unit['MainPID'] == '0' and unit['ActiveState'] in ('inactive', 'failed') \
                and unit['InvocationID'] != baseline['unit']['InvocationID'] \
                and datetime.fromisoformat(row['computed_at']) > previous_time:
            judge_unit = {key: unit[key] for key in ('Result', 'ExecMainStartTimestamp', 'ExecMainExitTimestamp', 'ExecMainStatus', 'InvocationID')}
            # The real unchanged judge accepts verified unhealthy exit1, while
            # rejecting deferred invocations, foreign writes and missing logs.
            publication = publisher_judge.judge(baseline['row'], baseline['unit']['InvocationID'],
                                               judge_unit, row, current['journal'])
            require(time.monotonic() < deadline, 'availability_natural_publication_timeout')
            return {**current, 'publication': publication}
        time.sleep(PUBLISHER_ALIGNMENT['poll_interval_seconds'])
    raise Refusal('availability_natural_publication_timeout')


@contextmanager
def aligned_publication_exclusion(target, contract, backup, exclusion, budget):
    with existing_operation_locks():
        budget.remaining(360 + 120 + 90 + 30 + SECONDS)
        storage_proof = storage_admission(contract, 'before_natural_publication_wait')
        sources = publisher_unit_sources()
        observe = publisher_observer(backup)
        selected = await_natural_publication(contract, observe)
        budget.remaining(120 + 90 + 30 + SECONDS)
        draining_started = time.monotonic()
        with exclusion.hold('private-availability:' + target[:12]):
            current = observe()
            require(current['coherent_unit'] and all(current[name] == selected[name]
                    for name in ('row', 'unit', 'timer', 'journal')), 'availability_selected_publication_drift')
            require(publisher_unit_sources() == sources, 'availability_publisher_unit_file_drift')
            require(time.monotonic() - draining_started <= RULED_BUDGET['publication_drain_seconds'],
                    'availability_ruled_stage_time_budget')
            proof = {'protocol': PUBLISHER_ALIGNMENT['protocol'], 'selected_invocation': selected['unit']['InvocationID'],
                'selected_row_sha256': sha(encode(selected['row'])), 'selected_unit_sha256': sha(encode(selected['unit'])),
                'selected_journal_sha256': sha(encode(selected['journal'])), 'publication': selected['publication'],
                'maximum_wait_seconds': 360, 'storage_admission': storage_proof, 'unit_sources': sources,
                'manual_publications': 0, 'timer_or_service_actions': 0, 'provider_calls': 0}
            budget.remaining(90 + 30 + SECONDS)
            yield proof


def database_admission(contract, original, verifier, backup):
    """Adapt qualified read-only functions; no frozen main/auth/progress function runs."""
    import psycopg
    from psycopg.rows import dict_row
    from django.utils.crypto import salted_hmac
    policy = contract['original_policy']
    captured, baseline, manifest, old_rows = verifier.original_continuation_capture(policy, datetime.now(timezone.utc))
    require(captured == original and manifest['tables']['django_session']['rows'] == 212,
            'availability_original_capture_population')
    environment = backup.key_at(old.KEY).decrypt(protected(old.CONTINUATION_ORIGINAL / 'environment-before.fernet', 65536))
    values = dotenv_values(stream=StringIO(environment.decode()), interpolate=False)
    secret = values['QUILLMD_SECRET_KEY']
    fingerprint = salted_hmac('quillmd-preview-v1', values['QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME'] + '\0'
                             + values['QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD'], secret=secret).hexdigest()
    del values, environment
    options = backup.source_options(APP, old.ROLES)
    with psycopg.connect(**options, row_factory=dict_row) as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        conn.execute("SET LOCAL timezone='UTC'")
        conn.execute("SET LOCAL datestyle='ISO, MDY'")
        conn.execute("SET LOCAL statement_timeout='90s'")
        flags = conn.execute("SELECT current_user,current_database(),current_setting('transaction_read_only') AS read_only").fetchone()
        require(flags['current_user'] == 'quillmd_backup' and flags['current_database'] == 'quillmd_fresh'
                and flags['read_only'] == 'on', 'availability_readonly_database_identity')
        current, keys, tables = verifier.current_copy_tables(conn, old_rows, backup)
        original_health = list(verifier.row_mapping('core_servicehealth', old_rows['core_servicehealth']['rows'],
                                                   old_rows['core_servicehealth']['columns'], keys['core_servicehealth']).values())
        rows = [row for row in original_health if row['key'] == b'backup']
        require(len(rows) == 1, 'availability_one_original_publisher')
        publisher = verifier.publisher_source_admission(publisher_observation_connection(conn), rows[0], policy)
        semantic = verifier.continuation_rows_admission(old_rows, current, keys,
                    {**policy, 'original_tables': manifest['tables']}, secret, fingerprint, None, publisher)
        fingerprint = verifier.continuation_database_fingerprint(conn, tables, baseline, backup)
    return {'format': 1, 'complete': True, 'provider_calls': 0, 'database_writes': 0,
            'original_records_adjudicated': True, 'original_backup_rows_only': True,
            'current_database_fingerprint': fingerprint, 'allowed_deltas': semantic}


def working_directory_transition(before, after):
    """Only one literal existing [Service] WorkingDirectory assignment may differ."""
    require(before != after, 'availability_external_transition_required')
    def split(raw):
        require(b'\x00' not in raw and len(raw) <= 65536, 'availability_external_unit_bytes')
        section, count, stable, directory = None, 0, [], None
        for line in raw.splitlines(keepends=True):
            text = line.strip()
            if text.startswith(b'[') and text.endswith(b']'):
                section = text
            if text.startswith(b'WorkingDirectory='):
                count += 1
                require(section == b'[Service]' and line.startswith(b'WorkingDirectory='),
                        'availability_external_working_directory_scope')
                directory = text.split(b'=', 1)[1]
                require(directory.startswith(b'/') and b'%' not in directory and b'\\' not in directory
                        and all(value > 32 for value in directory), 'availability_external_working_directory_literal')
                stable.append(b'WorkingDirectory=<declared>\n')
            else:
                stable.append(line)
        require(count == 1, 'availability_external_single_working_directory')
        return b''.join(stable), directory.decode()
    old_stable, old_directory = split(before)
    new_stable, new_directory = split(after)
    require(old_stable == new_stable and old_directory != new_directory, 'availability_external_other_unit_delta')
    return {'old_working_directory': old_directory, 'new_working_directory': new_directory}


def approval_protocol_qualified(acknowledgement):
    protocol = acknowledgement.get('approval_protocol')
    if protocol == CURRENT_OWNER_PROTOCOL:
        return CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED
    return protocol in (None, 'existing-approved-root-deployment-v1') and NATIVE_APPROVAL_PROTOCOL_QUALIFIED


def export_configuration_metadata(item, *, link=False):
    values = item.get('metadata')
    require(isinstance(values, list) and len(values) == 8
            and all(type(value) is int for value in values)
            and values[0] > 0 and values[1] > 0 and values[2:4] == [0, 0]
            and values[4] == (0o777 if link else 0o644) and all(value > 0 for value in values[5:]),
            'availability_owner_boundary_export_metadata')
    result = dict(zip(('device', 'inode', 'uid', 'gid', 'mode'), values[:5]))
    result['link' if link else 'sha256'] = item['target' if link else 'sha256']
    return result


def owner_boundary_inputs(acknowledgement):
    """Authenticate retained installation identity, without inferring past approval."""
    require(acknowledgement.get('approval_protocol') == CURRENT_OWNER_PROTOCOL
            and acknowledgement.get('unit_path') == EXTERNAL_UNIT,
            'availability_owner_boundary_protocol')
    retained = {}
    for name in ('native_evidence', 'independent_review'):
        require(acknowledgement.get(name) == CURRENT_OWNER_PINS[name], 'availability_owner_boundary_evidence_binding')
        raw = protected(Path(CURRENT_OWNER_PINS[name]['path']))
        require(sha(raw) == CURRENT_OWNER_PINS[name]['sha256'], 'availability_owner_boundary_evidence_hash')
        retained[name] = json.loads(raw)
    export, review = retained['native_evidence'], retained['independent_review']
    require(export.get('bounded_collection_complete') is True and export.get('measured_native_checks_complete') is True
            and export.get('native_administrator') is True and export.get('missing') == []
            and export.get('original_baseline_immutable') is True
            and export.get('approval_lineage_assessment') == 'unassessed'
            and export.get('service_actions') == export.get('provider_calls') == 0
            and review['exports']['v15'] == {**CURRENT_OWNER_PINS['native_evidence'],
                'collected_at_utc': export['collected_at_utc'], 'record_count': len(export['records'])}
            and review['adjudication']['current_authorization_verified'] is False
            and review['adjudication']['current_source_installation_and_unit_identity_established'] is True,
            'availability_owner_boundary_retained_identity')
    transition = export['original_and_observed_unit_evidence']
    product = transition['observed_current_unit']
    require(transition['original_immutable_unit']['sha256'] == CURRENT_OWNER_PINS['original_metadata']['sha256']
            and product['path'] == EXTERNAL_UNIT and product['sha256'] == CURRENT_OWNER_PINS['current_unit_sha256']
            and transition['no_bytes_change_outside_original_working_directory_line'] is True
            and transition['original_baseline_replaced'] is False
            and export['original_release'] == CURRENT_OWNER_PINS['old_working_directory']
            and transition['observed_current_release'] == CURRENT_OWNER_PINS['new_working_directory']
            and export['expected_current_source_sha256'] == CURRENT_OWNER_PINS['source_sha256'],
            'availability_owner_boundary_transition')
    additional = export['additional_configuration_evidence']
    files = {item['path']: item for item in additional['exact_added_files']}
    links = {item['path']: item for item in additional['exact_added_enablement_links']}
    require(len(files) == len(additional['exact_added_files']) == 4
            and len(links) == len(additional['exact_added_enablement_links']) == 2
            and {path: item['sha256'] for path, item in files.items()} == CURRENT_OWNER_PINS['added_files']
            and {path: item['target'] for path, item in links.items()} == CURRENT_OWNER_PINS['added_links']
            and additional['template_loaded_state_not_claimed'] is True,
            'availability_owner_boundary_seven_paths')
    current = {EXTERNAL_UNIT: export_configuration_metadata(product),
               **{path: export_configuration_metadata(item) for path, item in files.items()},
               **{path: export_configuration_metadata(item, link=True) for path, item in links.items()}}
    boundary = {'before': {EXTERNAL_UNIT: CURRENT_OWNER_PINS['original_metadata']}, 'after': current}
    require(acknowledgement.get('boundary_sha256') == sha(encode(boundary)), 'availability_owner_boundary_scope_hash')
    for name in ('manifest', 'installation'):
        item = export['installation_binding'][name]
        require({key: item[key] for key in ('path', 'sha256')} == CURRENT_OWNER_PINS[name]
                and item['uid'] == item['gid'] == 0 and item['mode'] == '0o644',
                'availability_owner_boundary_installation_binding')
    require(export['installation_binding']['observed_current_source_sha256'] == CURRENT_OWNER_PINS['source_sha256']
            and export['installation_binding']['receipt_matches_same_loaded_pid'] is True,
            'availability_owner_boundary_source_binding')
    return export, boundary


def owner_boundary_configuration(before, current, acknowledgement):
    export, boundary = owner_boundary_inputs(acknowledgement)
    changed = {key for key in set(before) | set(current) if before.get(key) != current.get(key)}
    require(changed == set(boundary['after']) and before.get(EXTERNAL_UNIT) == boundary['before'][EXTERNAL_UNIT]
            and all(path not in before for path in set(boundary['after']) - {EXTERNAL_UNIT})
            and all(current.get(path) == value for path, value in boundary['after'].items()),
            'availability_owner_boundary_exact_seven_deltas')
    return export, boundary


def acknowledge_current_owner_configuration(before, current, acknowledgement):
    require(CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED and acknowledgement.get('qualified') is True,
            'availability_current_owner_protocol_unqualified')
    _, boundary = owner_boundary_configuration(before, current, acknowledgement)
    item = acknowledgement.get('owner_decision_evidence')
    require(isinstance(item, dict) and set(item) == {'path', 'sha256'}
            and item['path'] == str(OWNER_DECISION_PATH) and re.fullmatch('[a-f0-9]{64}', item['sha256'] or ''),
            'availability_current_owner_decision_missing')
    raw = protected(OWNER_DECISION_PATH, 65536)
    require(sha(raw) == item['sha256'], 'availability_current_owner_decision_hash')
    decision = json.loads(raw)
    expected = {'format': 1, 'protocol': CURRENT_OWNER_PROTOCOL,
        'decision': 'authorize_exact_current_preservation_boundary', 'boundary_sha256': sha(encode(boundary)),
        'native_evidence': CURRENT_OWNER_PINS['native_evidence'], 'independent_review': CURRENT_OWNER_PINS['independent_review'],
        'historical_deployment_authorization_verified': False, 'current_owner_preservation_authorized': True,
        'original_baseline_replaced': False, 'voiceassistmain_changes_authorized': False}
    require(set(decision) == set(expected) | {'owner_reply_evidence'}
            and all(type(decision[key]) is type(value) and decision[key] == value for key, value in expected.items()),
            'availability_current_owner_decision_scope')
    reply = decision['owner_reply_evidence']
    require(isinstance(reply, dict) and set(reply) == {'path', 'sha256'}
            and reply['path'] == str(OWNER_EVIDENCE_ROOT / 'owner-current-configuration-preservation-message-v1.txt')
            and re.fullmatch('[a-f0-9]{64}', reply['sha256'] or ''), 'availability_current_owner_reply_binding')
    reply_raw = protected(Path(reply['path']), 65536)
    require(reply_raw.strip() and sha(reply_raw) == reply['sha256'], 'availability_current_owner_reply_hash')
    return {'qualified': True, 'approval_protocol': CURRENT_OWNER_PROTOCOL, 'unit_path': EXTERNAL_UNIT,
        'old_metadata': boundary['before'][EXTERNAL_UNIT], 'new_metadata': boundary['after'][EXTERNAL_UNIT],
        'configuration_deltas': boundary, 'boundary_sha256': sha(encode(boundary)),
        'old_working_directory': CURRENT_OWNER_PINS['old_working_directory'],
        'new_working_directory': CURRENT_OWNER_PINS['new_working_directory'],
        'native_evidence': CURRENT_OWNER_PINS['native_evidence'], 'independent_review': CURRENT_OWNER_PINS['independent_review'],
        'owner_decision_evidence': item, 'historical_deployment_authorization_verified': False,
        'current_owner_preservation_authorized': True, 'unit_mutated_by_this_act': False}


def acknowledge_configuration(before, current, acknowledgement):
    """Authentic approval evidence must be pinned prospectively; no current-as-old substitution."""
    if acknowledgement.get('approval_protocol') == CURRENT_OWNER_PROTOCOL:
        return acknowledge_current_owner_configuration(before, current, acknowledgement)
    require(NATIVE_APPROVAL_PROTOCOL_QUALIFIED, 'availability_native_authorization_protocol_unqualified')
    require(acknowledgement.get('qualified') is True and acknowledgement.get('unit_path') == EXTERNAL_UNIT,
            'availability_external_approval_missing')
    changed = {key for key in set(before) | set(current) if before.get(key) != current.get(key)}
    require(changed == {EXTERNAL_UNIT} and acknowledgement.get('old_metadata') == before[EXTERNAL_UNIT]
            and acknowledgement.get('new_metadata') == current[EXTERNAL_UNIT], 'availability_external_exact_metadata')
    old_meta, new_meta = before[EXTERNAL_UNIT], current[EXTERNAL_UNIT]
    require(set(old_meta) == set(new_meta) == {'uid', 'gid', 'mode', 'device', 'inode', 'sha256'}
            and all(old_meta[key] == new_meta[key] for key in ('uid', 'gid', 'mode', 'device'))
            and old_meta['uid'] == old_meta['gid'] == 0 and old_meta['mode'] == 0o644,
            'availability_external_native_identity')
    old_bytes = protected(Path(acknowledgement['old_bytes_path']), 65536)
    new_bytes = protected(Path(acknowledgement['new_bytes_path']), 65536)
    require(sha(old_bytes) == old_meta['sha256'] and sha(new_bytes) == new_meta['sha256'],
            'availability_external_retained_bytes')
    transition = working_directory_transition(old_bytes, new_bytes)
    # The reviewed collector's actual approval protocol is pinned separately. Until
    # that evidence exists this gate cannot be qualified or accept a current hash.
    require(acknowledgement.get('approval_protocol') == 'existing-approved-root-deployment-v1',
            'availability_external_approval_protocol')
    proof_raw = protected(Path(acknowledgement['approval_path']))
    require(sha(proof_raw) == acknowledgement.get('approval_sha256'), 'availability_external_approval_hash')
    proof = json.loads(proof_raw)
    require(proof.get('complete') is True and proof.get('existing_deployment_authorization_verified') is True
            and proof.get('native_root_installation_verified') is True
            and proof.get('unit_path') == EXTERNAL_UNIT
            and proof.get('old_unit_sha256') == old_meta['sha256']
            and proof.get('new_unit_sha256') == new_meta['sha256']
            and proof.get('approved_working_directory') == transition['new_working_directory']
            and proof.get('authorization_evidence') == acknowledgement.get('authorization_evidence')
            and proof.get('installation_evidence') == acknowledgement.get('installation_evidence'),
            'availability_external_deployment_authority')
    for role in ('authorization_evidence', 'installation_evidence'):
        item = acknowledgement[role]
        require(isinstance(item, dict) and re.fullmatch('[a-f0-9]{64}', item.get('sha256', ''))
                and sha(protected(Path(item['path']))) == item['sha256'], 'availability_external_provenance_artifact')
    return {'qualified': True, 'unit_path': EXTERNAL_UNIT, 'old_metadata': old_meta, 'new_metadata': new_meta,
            **transition, 'approval_sha256': sha(proof_raw), 'authorization_evidence': acknowledgement['authorization_evidence'],
            'installation_evidence': acknowledgement['installation_evidence'], 'unit_mutated_by_this_act': False}


def native_boundary_identity():
    require(os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 1000
            and not Path('/.dockerenv').exists(), 'availability_owner_boundary_native_observer')
    return {'hostname': socket.gethostname(), 'machine_id_sha256': sha(Path('/etc/machine-id').read_bytes()),
        'pid1_comm': Path('/proc/1/comm').read_text().strip(),
        'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        'mount_namespace': os.readlink('/proc/self/ns/mnt'), 'pid_namespace': os.readlink('/proc/self/ns/pid')}


def full_native_metadata(info):
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode),
            info.st_size, info.st_mtime_ns, info.st_ctime_ns]


def owner_public_record(root_fd, path, digest, expected_metadata):
    allowed = {EXTERNAL_UNIT: CURRENT_OWNER_PINS['current_unit_sha256'], **CURRENT_OWNER_PINS['added_files'],
        CURRENT_OWNER_PINS['manifest']['path']: CURRENT_OWNER_PINS['manifest']['sha256'],
        CURRENT_OWNER_PINS['installation']['path']: CURRENT_OWNER_PINS['installation']['sha256']}
    require(allowed.get(path) == digest, 'availability_owner_boundary_public_read_scope')
    fd = source_files.open_relative(root_fd, path[1:])
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_uid == before.st_gid == 0
                and stat.S_IMODE(before.st_mode) == 0o644 and before.st_nlink == 1
                and not os.listxattr(fd) and full_native_metadata(before) == expected_metadata,
                'availability_owner_boundary_public_metadata')
        raw = source_files.bytes_at(fd, 2 * 1024 * 1024)
        require(sha(raw) == digest, 'availability_owner_boundary_public_bytes')
        reopened = source_files.open_relative(root_fd, path[1:])
        try:
            require(source_files.stable(before) == source_files.stable(os.fstat(fd))
                    == source_files.stable(os.fstat(reopened)), 'availability_owner_boundary_public_path_race')
        finally:
            os.close(reopened)
        return raw
    finally:
        os.close(fd)


def owner_unit_state(name, properties):
    allowed = {EXTERNAL_UNIT.rsplit('/', 1)[1], 'voiceassist-restaurant-tajrish-20261007-retention.service',
        'voiceassist-restaurant-tajrish-20261007-retention.timer', 'voiceassistmain-restaurant-voice.service'}
    require(name in allowed, 'availability_owner_boundary_unit_scope')
    lines = old.command(['systemctl', 'show', name, '--property=' + ','.join(properties)], timeout=10).decode().splitlines()
    require(len(lines) == len(properties) and all('=' in line for line in lines), 'availability_owner_boundary_unit_population')
    values = dict(line.split('=', 1) for line in lines)
    require(set(values) == set(properties), 'availability_owner_boundary_unit_population')
    return values


def loaded_current_owner_boundary(acknowledgement):
    """Native read-only exact paths; no foreign source traversal or service action."""
    require(CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED and acknowledgement.get('qualified') is True,
            'availability_current_owner_protocol_unqualified')
    export, boundary = owner_boundary_inputs(acknowledgement)
    # Reauthenticate the exact owner decision on every native boundary reread.
    acknowledge_current_owner_configuration(boundary['before'], boundary['after'], acknowledgement)
    native = native_boundary_identity()
    require(native == export['native_host_proof'], 'availability_owner_boundary_native_identity')
    expected_product = export['same_loaded_state']
    product_name = EXTERNAL_UNIT.rsplit('/', 1)[1]
    product = owner_unit_state(product_name, tuple(expected_product))
    require(product == expected_product and product['WorkingDirectory'] == CURRENT_OWNER_PINS['new_working_directory']
            and product['UnitFileState'] == 'enabled' and product['NeedDaemonReload'] == 'no'
            and product['LoadState'] == 'loaded' and product['ActiveState'] == 'active' and product['SubState'] == 'running'
            and product['DropInPaths'] == '' and product['User'] == product['Group'] == 'voiceassistmain'
            and re.fullmatch('[a-f0-9]{32}', product['InvocationID'])
            and re.fullmatch('[1-9][0-9]*', product['MainPID']), 'availability_owner_boundary_product_identity')
    additional = export['additional_configuration_evidence']
    units = {row['Id']: row for row in additional['loaded_states']}
    names = {'voiceassist-restaurant-tajrish-20261007-retention.service',
        'voiceassist-restaurant-tajrish-20261007-retention.timer', 'voiceassistmain-restaurant-voice.service'}
    require(set(units) == names and len(additional['loaded_states']) == 3, 'availability_owner_boundary_loaded_unit_scope')
    stable_units = {}
    for name, expected in units.items():
        # Natural retention/voice lifecycle transitions are observed, not pinned
        # as restaurant process identities. Preserve every configuration field.
        actual = owner_unit_state(name, tuple(expected))
        stable = {key: value for key, value in expected.items() if key not in ('ActiveState', 'SubState')}
        require({key: actual[key] for key in stable} == stable
                and actual['LoadState'] == 'loaded' and actual['DropInPaths'] == '' and actual['NeedDaemonReload'] == 'no'
                and actual['UnitFileState'] == ('static' if name.endswith('retention.service') else 'enabled')
                and actual['ActiveState'] in ('active', 'inactive', 'activating', 'deactivating', 'failed', 'reloading', 'maintenance')
                and actual['SubState'] in ('dead', 'running', 'waiting', 'elapsed', 'exited', 'failed', 'start',
                    'start-pre', 'start-post', 'stop', 'stop-sigterm', 'stop-sigkill', 'stop-post',
                    'final-sigterm', 'final-sigkill', 'auto-restart', 'cleaning', 'reload'),
                'availability_owner_boundary_additional_loaded_identity')
        repeated = owner_unit_state(name, tuple(expected))
        require({key: repeated[key] for key in stable} == stable, 'availability_owner_boundary_added_unit_race')
        stable_units[name] = stable
    records = [export['original_and_observed_unit_evidence']['observed_current_unit'], *additional['exact_added_files']]
    with source_files.open_root(Path('/')) as root_fd:
        for item in records:
            raw = owner_public_record(root_fd, item['path'], item['sha256'], item['metadata'])
            if item['path'] == EXTERNAL_UNIT:
                lines = raw.splitlines()
                assignments = [line for line in lines if line.strip().startswith(b'WorkingDirectory=')]
                require(assignments == [b'WorkingDirectory=' + CURRENT_OWNER_PINS['new_working_directory'].encode()],
                        'availability_owner_boundary_current_working_directory')
        for item in additional['exact_added_enablement_links']:
            path = Path(item['path'])
            fd = source_files.open_relative(root_fd, str(path.parent)[1:], directory=True)
            try:
                before = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                require(stat.S_ISLNK(before.st_mode) and before.st_uid == before.st_gid == 0 and before.st_nlink == 1
                        and full_native_metadata(before) == item['metadata']
                        and os.readlink(path.name, dir_fd=fd) == CURRENT_OWNER_PINS['added_links'][str(path)],
                        'availability_owner_boundary_enablement_link')
                require(source_files.stable(before) == source_files.stable(os.stat(path.name, dir_fd=fd, follow_symlinks=False)),
                        'availability_owner_boundary_link_race')
            finally:
                os.close(fd)
        parsed = {}
        for name in ('manifest', 'installation'):
            item = export['installation_binding'][name]
            metadata = [item[key] for key in ('device', 'inode', 'uid', 'gid')] + [0o644] + [
                item[key] for key in ('size', 'mtime_ns', 'ctime_ns')]
            parsed[name] = json.loads(owner_public_record(root_fd, item['path'], item['sha256'], metadata))
            require(parsed[name]['installation_id'] == CURRENT_OWNER_PINS['installation_id']
                    and parsed[name]['source_sha256'] == CURRENT_OWNER_PINS['source_sha256']
                    and parsed[name]['release_root'] == CURRENT_OWNER_PINS['new_working_directory'],
                    'availability_owner_boundary_current_installation')
        receipt = parsed['installation']
        require(receipt['manifest_sha256'] == CURRENT_OWNER_PINS['manifest']['sha256']
                and receipt['main_pid'] == int(product['MainPID']) and receipt['installed'] is True
                and receipt['calls_started'] == receipt['provider_writes'] == 0 and receipt['nginx_changed'] is False,
                'availability_owner_boundary_current_installation_receipt')
    require(owner_unit_state(product_name, tuple(expected_product)) == product
            and native_boundary_identity() == native, 'availability_owner_boundary_native_final_race')
    return {'approval_protocol': CURRENT_OWNER_PROTOCOL, 'native_host_proof': native,
        'configuration': boundary['after'], 'product_loaded_state': product,
        'additional_unit_configuration': stable_units,
        'manifest': CURRENT_OWNER_PINS['manifest'], 'installation': CURRENT_OWNER_PINS['installation'],
        'owner_decision_evidence': acknowledgement['owner_decision_evidence']}


def loaded_external_state(host, acknowledgement):
    """Read only the explicitly approved foreign unit, never change or reload it."""
    if acknowledgement.get('approval_protocol') == CURRENT_OWNER_PROTOCOL:
        return loaded_current_owner_boundary(acknowledgement)
    require(acknowledgement.get('qualified') is True, 'availability_external_approval_missing')
    names = ('WorkingDirectory', 'FragmentPath', 'DropInPaths', 'LoadState', 'ActiveState', 'SubState',
             'UnitFileState', 'NeedDaemonReload', 'User', 'Group', 'InvocationID', 'MainPID',
             'ExecMainStartTimestampMonotonic')
    unit = EXTERNAL_UNIT.rsplit('/', 1)[1]
    code = ('import os,json,subprocess\nos.chroot("/host");os.chdir("/")\n'
            'raw=subprocess.check_output(' + repr(['systemctl', 'show', unit,
                '--property=' + ','.join(names)]) + ',timeout=10,text=True)\n'
            'print(json.dumps(dict(line.split("=",1) for line in raw.splitlines() if "=" in line),sort_keys=True))\n')
    actual = json.loads(host.helper(code, 20))
    expected = acknowledgement.get('loaded_state')
    require(isinstance(expected, dict) and set(actual) == set(expected) == set(names)
            and actual == expected and actual['FragmentPath'] == EXTERNAL_UNIT
            and actual['DropInPaths'] == '' and actual['LoadState'] == 'loaded'
            and actual['ActiveState'] == 'active' and actual['SubState'] == 'running'
            and actual['UnitFileState'] == 'enabled' and actual['NeedDaemonReload'] == 'no'
            and re.fullmatch('[a-f0-9]{32}', actual['InvocationID'])
            and re.fullmatch('[1-9][0-9]*', actual['MainPID'])
            and re.fullmatch('[1-9][0-9]*', actual['ExecMainStartTimestampMonotonic']),
            'availability_external_loaded_state')
    raw = protected(Path(acknowledgement['approval_path']))
    proof = json.loads(raw)
    require(sha(raw) == acknowledgement['approval_sha256'] and proof.get('loaded_state') == actual
            and proof.get('approved_working_directory') == actual['WorkingDirectory']
            and proof.get('approved_user') == actual['User'] and proof.get('approved_group') == actual['Group'],
            'availability_external_loaded_authority')
    return actual


def compare_population(original, current, admission, acknowledgement, *, allow_pending=False):
    require(current['database'] == admission['current_database_fingerprint'], 'availability_database_snapshot_race')
    require(set(current) == set(original['expected_population']), 'availability_snapshot_population')
    for name in ('files', 'mail', 'static'):
        require(current[name] == original['expected_population'][name], 'availability_' + name + '_delta')
    if allow_pending and (acknowledgement.get('qualified') is not True or not approval_protocol_qualified(acknowledgement)):
        previous = original['expected_population']['configuration']
        following = current['configuration']
        changes = {key for key in set(previous) | set(following) if previous.get(key) != following.get(key)}
        if acknowledgement.get('approval_protocol') == CURRENT_OWNER_PROTOCOL:
            _, boundary = owner_boundary_configuration(previous, following, acknowledgement)
            return {'status': 'RED', 'qualified': False, 'approval_protocol': CURRENT_OWNER_PROTOCOL,
                'reason': 'availability_current_owner_decision_pending', 'unit_path': EXTERNAL_UNIT,
                'observed_configuration_deltas': boundary, 'historical_deployment_authorization_verified': False,
                'current_owner_preservation_authorized': False, 'current_metadata_is_not_approval': True}
        require(changes == {EXTERNAL_UNIT}, 'availability_unadjudicated_other_configuration_delta')
        return {'status': 'RED', 'qualified': False, 'reason': 'availability_native_authorization_protocol_unqualified',
                'unit_path': EXTERNAL_UNIT, 'observed_old_metadata': previous[EXTERNAL_UNIT],
                'observed_current_metadata': following[EXTERNAL_UNIT], 'current_metadata_is_not_approval': True}
    return acknowledge_configuration(original['expected_population']['configuration'], current['configuration'], acknowledgement)


@contextmanager
def existing_operation_locks():
    with ExitStack() as stack:
        for relative in ('legacy-model-activation.lock', *old.LOCKS):
            path = RUNTIME / relative
            require(path.resolve(strict=True) == path, 'availability_existing_lock_path')
            fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
            stack.callback(os.close, fd)
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid()
                    and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1,
                    'availability_existing_lock_identity')
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def stopped_scope(host):
    result = {unit: host.state(unit) for unit in old.UNITS + old.OPERATIONS}
    require(all(row.get('MainPID') == '0' and row.get('ActiveState') in ('inactive', 'failed')
                for row in result.values()), 'availability_active_private_or_operation')
    return result


def readiness(contract, host, backup, storage, *, preflight=False):
    storage_proof = storage_admission(contract, 'before_admission')
    original, environment, backup_proof, cipher = authenticate_chain(contract, backup)
    units = stopped_scope(host)
    admission = database_admission(contract, original, frozen_verifier(), backup)
    current = old.snapshot(host, backup, storage)
    acknowledgement = compare_population(original, current, admission, contract['external_configuration_ack'],
                                         allow_pending=preflight)
    if acknowledgement.get('status') != 'RED':
        acknowledgement['loaded_state'] = loaded_external_state(host, contract['external_configuration_ack'])
    require(stopped_scope(host) == units and protected(APP / '.env', 65536) == environment,
            'availability_stopped_identity_race')
    return {'original': original, 'environment': environment, 'cipher': cipher,
            'backup': backup_proof, 'admission': admission, 'before': current, 'units': units,
            'external_acknowledgement': acknowledgement, 'storage_admission': storage_proof}


def boundary(host, storage, target, worker_required):
    units = old.await_service_boundary(host, storage, target, worker_required=worker_required)
    for unit, state in units.items():
        pid = int(state['MainPID'])
        require((Path('/proc') / str(pid) / 'cgroup').read_bytes()
                == ('0::/system.slice/' + unit + '\n').encode(), 'availability_exact_native_cgroup')
        require(host.state(unit) == state, 'availability_same_pid_race')
    require(old.git(ROOT, 'rev-parse', 'HEAD').strip().decode() == target, 'availability_served_source_identity')
    return units


def completion_unit_provenance(host, units):
    """Measure invocation UUIDs without changing the frozen legacy state map."""
    require(set(units) == set(old.UNITS), 'availability_completion_unit_population')
    result = {}
    for unit, legacy in units.items():
        require(set(legacy) == {'ActiveState', 'SubState', 'MainPID', 'FragmentPath', 'DropInPaths',
                'UnitFileState', 'ExecMainStartTimestampMonotonic'}, 'availability_completion_legacy_population')
        measured = own_unit_properties(unit, tuple(legacy) + ('InvocationID', 'NeedDaemonReload'))
        require({key: measured[key] for key in legacy} == legacy
                and re.fullmatch('[a-f0-9]{32}', measured['InvocationID'])
                and measured['NeedDaemonReload'] == 'no'
                and host.state(unit) == legacy, 'availability_completion_unit_identity')
        require(own_unit_properties(unit, tuple(measured)) == measured,
                'availability_completion_unit_observation_race')
        result[unit] = measured
    return result


def direct_health(target):
    import httpx
    values = []
    for port, surface in ((9130, 'doctor'), (9131, 'admin')):
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=5) as client:
            response = client.get('http://127.0.0.1:' + str(port) + '/health/')
        require(response.status_code == 200 and response.json() == {
            'status': 'ok', 'surface': surface, 'release': target, 'data_mode': 'synthetic-only'},
            'availability_direct_health_contract')
        values.append(response.json())
    return values


def await_direct_health(target, timeout=30):
    import httpx
    deadline = time.monotonic() + timeout
    while True:
        try:
            return direct_health(target)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout):
            require(time.monotonic() < deadline, 'availability_startup_http_deadline')
            time.sleep(0.2)


def complete_recovery(target, contract, source, *, host, backup, storage, exclusion, env_writer,
                      preflight=False, budget=None):
    if not preflight:
        require(INSTALLATION_QUALIFIED and approval_protocol_qualified(contract.get('external_configuration_ack', {}))
                and contract.get('installation_qualified') is True,
                'availability_native_authorization_protocol_unqualified')
    budget = budget or RuledBudget(contract)
    exclusion.bind_runtime(RUNTIME)
    with aligned_publication_exclusion(target, contract, backup, exclusion, budget) as alignment:
        with budget.stage('full_readiness', 30 + SECONDS):
            prepared = readiness(contract, host, backup, storage, preflight=preflight)
        publisher = prepared['admission']['allowed_deltas']['publisher']
        require(sha(encode(publisher['current_full_row'])) == alignment['selected_row_sha256']
                and publisher['publication']['invocation'] == alignment['selected_invocation'],
                'availability_admitted_selected_publication_identity')
        if preflight:
            accepted = prepared['external_acknowledgement'].get('status') != 'RED'
            return {'complete': accepted, 'independent_checks_complete': True, 'read_only_preflight': True, 'source': source,
                    'provider_calls': 0, 'database_writes': 0, 'authentication_submissions': 0,
                    'original_records_adjudicated': True, 'current_snapshot_sha256': sha(encode(prepared['before'])),
                    'external_acknowledgement': prepared['external_acknowledgement'],
                    'publisher': prepared['admission']['allowed_deltas']['publisher'],
                    'publisher_alignment': alignment,
                    'ruled_time_budget': budget.proof(),
                    'storage_admission': prepared['storage_admission']}
        budget.remaining(30 + SECONDS)
        updated = release_only_environment(prepared['environment'], target)
        outcome = {'format': 1, 'complete': False, 'stage': 'admitted', 'source': source,
                   'provider_calls': 0, 'authentication_submissions': 0, 'database_restore_performed': False,
                   'new_capture_performed': False, 'acceptance_started': False, 'automatic_retries': False,
                   'original_failure_reason': 'unknown; original parent Refusal detail was not retained',
                   'original_before': prepared['original']['before'],
                   'original_expected_population': prepared['original']['expected_population'],
                   'original_backup': prepared['original']['backup'], 'authenticated_original_backup': prepared['backup'],
                   'original_receipts': contract['original_policy']['original_receipts'],
                   'failed_continuation_receipts': CONTINUATION_RECEIPTS, 'before': prepared['before'],
                   'admission': prepared['admission'], 'external_acknowledgement': prepared['external_acknowledgement'],
                   'publisher_alignment': alignment,
                   'ruled_time_budget': budget.proof(),
                   'environment_before_sha256': sha(prepared['environment']), 'environment_after_sha256': sha(updated),
                   'storage_admission': [prepared['storage_admission']], 'started_at': datetime.now(timezone.utc).isoformat()}
        OUTPUT.mkdir(mode=0o700)
        mutation_started = False
        deadline = time.monotonic() + SECONDS
        def check(stage):
            require(time.monotonic() < deadline, 'availability_completion_deadline')
            budget.remaining(0)
            outcome['storage_admission'].append(storage_admission(contract, stage))
        try:
            write_new(OUTPUT / 'environment-before.fernet', prepared['cipher'].encrypt(prepared['environment']))
            write_new(OUTPUT / 'environment-after.fernet', prepared['cipher'].encrypt(updated))
            write_new(OUTPUT / 'prepared.json', outcome)
            check('before_marker')
            require(old.snapshot(host, backup, storage) == prepared['before']
                    and stopped_scope(host) == prepared['units'], 'availability_before_marker_race')
            require(loaded_external_state(host, contract['external_configuration_ack'])
                    == prepared['external_acknowledgement']['loaded_state'], 'availability_external_before_marker_race')
            write_new(ATTEMPT, {'format': 1, 'attempt': 1, 'source': target, 'output': str(OUTPUT),
                               'provider_calls': 0, 'automatic_retries': False})
            mutation_started = True
            forward_source(target)
            check('source_forwarded')
            env_writer.replace_environment(APP / '.env', prepared['environment'], updated)
            outcome['stage'] = 'configuration_written'
            require(old.snapshot(host, backup, storage) == prepared['before'], 'availability_stopped_preservation')
            for unit in old.UNITS[:2]:
                check('before_' + unit)
                host.service('start', unit)
            outcome['web_units'] = boundary(host, storage, target, False)
            outcome['health_before_worker'] = await_direct_health(target)
            require(old.snapshot(host, backup, storage) == prepared['before']
                    and host.state(old.UNITS[2]).get('MainPID') == '0', 'availability_web_start_preservation')
            check('before_worker_start')
            host.service('start', old.UNITS[2])
            outcome['units_after'] = boundary(host, storage, target, True)
            outcome['completion_unit_provenance'] = completion_unit_provenance(host, outcome['units_after'])
            outcome['worker_configuration_provenance'] = host.worker_configuration(updated, target, outcome['units_after'])
            outcome['health'] = await_direct_health(target)
            require(old.snapshot(host, backup, storage) == prepared['before'], 'availability_post_start_preservation')
            require(loaded_external_state(host, contract['external_configuration_ack'])
                    == prepared['external_acknowledgement']['loaded_state'], 'availability_external_post_start_race')
            check('complete')
            require(completion_unit_provenance(host, outcome['units_after']) == outcome['completion_unit_provenance'],
                    'availability_completion_unit_final_race')
            outcome.update(complete=True, stage='complete', completed_at=datetime.now(timezone.utc).isoformat(),
                           preserved=prepared['before'], actual_provider_model_verified=False,
                           next_step='Separately qualified same-URL browser/provider acceptance; allowance remains unconsumed.')
            write_new(OUTPUT / 'complete.json', outcome)
            return {'complete': True, 'provider_calls': 0, 'authentication_submissions': 0,
                    'availability_restored': True, 'actual_provider_model_verified': False,
                    'evidence_directory': str(OUTPUT), 'release': target}
        except BaseException as error:
            outcome.update(complete=False, stage='failed', mutation_started=mutation_started,
                           failure_kind=type(error).__name__,
                           refusal_label=safe_failure_label(error))
            if mutation_started:
                outcome['fail_stop'] = old.best_effort_private_stop(host)
            old.best_effort_capture(outcome, 'failure_checkpoint', lambda: write_new(OUTPUT / 'failed.json', outcome))
            raise Refusal('availability_failed_preserving_evidence') from None


def safe_failure_label(error):
    if isinstance(error, (Refusal, old.Refusal)) and re.fullmatch('[a-z0-9_]{1,100}', str(error)):
        return str(error)
    return 'availability_protected_operation_failure'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operator-commit')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--execute', action='store_true')
    args = parser.parse_args(argv)
    if not (args.preflight or args.execute):
        print(json.dumps({'execution_performed': False, 'installed_state_accessed': False,
              'provider_calls': 0, 'authentication_submissions': 0, 'database_writes': 0,
              'declaration': DECL, 'baseline_release': INSTALLED, 'prepared_release': PREPARED,
              'installation_qualified': INSTALLATION_QUALIFIED,
              'native_authorization_protocol_qualified': NATIVE_APPROVAL_PROTOCOL_QUALIFIED,
              'current_owner_boundary_protocol_qualified': CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED,
              'output': str(OUTPUT), 'maximum_attempts': 1, 'automatic_retries': False,
              'scope': 'Preserving forward source/release-only recovery and private structural health; no clinical campaign.'}, sort_keys=True))
        return 0
    if args.execute:
        require(INSTALLATION_QUALIFIED and (NATIVE_APPROVAL_PROTOCOL_QUALIFIED or CURRENT_OWNER_BOUNDARY_PROTOCOL_QUALIFIED),
                'availability_native_authorization_protocol_unqualified')
        from .direct_account_access import refuse_legacy_operation
        refuse_legacy_operation()
    started = time.monotonic()
    contract = load_contract()
    budget = RuledBudget(contract)
    # Include declaration authentication in the same source-check allowance.
    budget.started = started
    budget.deadline = started + RULED_BUDGET['maximum_seconds']
    with budget.stage('source_checks', 360 + 120 + 90 + 30 + SECONDS):
        source = source_gate(args.operator_commit, contract)
    require(time.monotonic() - started <= RULED_BUDGET['source_checks_seconds'],
            'availability_ruled_stage_time_budget')
    exclusion, backup, env_writer, managed, storage = old.modules()
    result = complete_recovery(args.operator_commit, contract, source, host=old.Host(managed), backup=backup,
                               storage=storage, exclusion=exclusion, env_writer=env_writer,
                               preflight=args.preflight, budget=budget)
    print(json.dumps(result, sort_keys=True, default=str))
    return 0 if result['complete'] else 2
