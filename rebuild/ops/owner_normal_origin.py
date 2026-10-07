"""One inert-by-default owner normal-origin transition after private acceptance.

The original encrypted population remains authoritative. The complete retained
synthetic campaign is independently re-read before the source transition, then
its exact current population is held unchanged. No login or provider call runs.
"""
import argparse
import ast
import base64
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from io import StringIO
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import types
from dotenv import dotenv_values
from . import legacy_model_activation as old
from . import repair_source_permissions as source_files

SOURCE = Path(__file__).resolve().parents[2]
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PYTHON = APP / '.venv/bin/python'
RUNTIME = APP / '.runtime'
EVIDENCE = RUNTIME / 'owner-demo-20261006'
BASE = 'ff60bc49bc053715c66fd741f9151a70819e1617'
SELF = 'rebuild/ops/owner_normal_origin.py'
TEST = 'rebuild/ops/test_owner_normal_origin.py'
ENTRY = 'scripts/prepare-owner-normal-origin.py'
DECL = 'docs/foundation/mutations/20261007-quillmd-owner-normal443.md'
TEMPLATE = 'rebuild/deploy/owner-normal-https.conf'
INGRESS = '/etc/nginx/sites-available/quillmd'
PRIVATE_INGRESS = '/etc/nginx/sites-available/quillmd-email-preview'
OLD_INGRESS_SHA = 'ff7320480fe823cbc1564e3c104ee41bac1dd5e1336f8772274af36a541a7a0a'
PRIVATE_INGRESS_SHA = 'cbc81159b1505fd566625062517bb18dd8d4706cd30b0e334e7fdceec659f21a'
CADDY_SHA = 'bf0c14729a4ae86ecf2e8ff34d9b5e68aeba55a0bb0c06879580bc73e3a23c87'
OUTPUT = EVIDENCE / 'owner-normal443-publication-v1'
ATTEMPT = EVIDENCE / 'owner-normal443-attempt-v1.json'
ACCEPTANCE = 'rebuild/ops/owner_acceptance_v3.py'
RECOVERY_DECL = 'docs/foundation/mutations/20261007-quillmd-private-availability-recovery.md'
PRIVATE_OPS = frozenset((ACCEPTANCE, 'rebuild/ops/test_owner_acceptance_v3.py', 'scripts/run-owner-acceptance-v3.py', 'docs/foundation/mutations/20261007-quillmd-owner-acceptance-v3.md'))
FROZEN_V3 = '34d4d3bf0b9641a2f642717b33833beb7a7f49a0c043bc095e592c41a78b0023'
NATIVE = tuple('rebuild/ops/' + name + '.py' for name in (
    'managed_helper', 'private_storage', 'backup_restore', 'email_activation',
    'activation_exclusion', 'legacy_model_activation', 'repair_source_permissions',
    'publisher_verification', 'private_availability_recovery'))
ALLOWED = frozenset((DECL, TEMPLATE, 'rebuild/quillmd/settings.py', 'rebuild/core/preview_access.py',
    'rebuild/core/tests/test_owner_normal_origin.py', SELF, TEST, ENTRY))
SHARED_NAMES = b'    server_name quillmd.com www.quillmd.com app.quillmd.com admin.quillmd.com;'
RESTRICTED_NAMES = b'    server_name quillmd.com www.quillmd.com admin.quillmd.com;'
ACTIVE_PROTOCOL_QUALIFIED = False
PRIVATE_ACCEPTANCE_QUALIFIED = False
INGRESS_PUBLICATION_QUALIFIED = False
OUTER_SECONDS = 2400
PRIVATE_PATHS = {
    'private_acceptance': EVIDENCE / 'installed-acceptance-v3-20261007/complete.json',
    'private_report': EVIDENCE / 'installed-acceptance-v3-20261007/independent-verification.json',
    'private_authority': EVIDENCE / 'installed-acceptance-v3-preparation-20261007/parent-phase-verify.json',
    'availability': RUNTIME / 'private-availability-recovery-20261007/complete.json'}

class Refusal(RuntimeError):
    pass

def require(condition, label):
    if not condition: raise Refusal(label)

def sha(raw): return hashlib.sha256(raw).hexdigest()
def encode(value): return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
def qualified(): return ACTIVE_PROTOCOL_QUALIFIED and PRIVATE_ACCEPTANCE_QUALIFIED and INGRESS_PUBLICATION_QUALIFIED

def application_gate(preview, settings):
    tree = ast.parse(preview)
    values = [node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'OWNER_NORMAL_ORIGIN_PROTOCOL_QUALIFIED'
                for target in node.targets)]
    require(len(values) == 1 and isinstance(values[0], ast.Constant) and values[0].value is True,
            'normal443_checked_application_qualified')
    setting = [node.value for node in ast.parse(settings).body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'
                for target in node.targets)]
    expected = ast.parse("os.getenv('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED', '0') == '1'", mode='eval').body
    require(len(setting) == 1 and ast.dump(setting[0], include_attributes=False)
        == ast.dump(expected, include_attributes=False), 'normal443_default_disabled_explicit_setting')
    return True

def render_ingress(original, template):
    require(type(original) is bytes and sha(original) == OLD_INGRESS_SHA, 'normal443_original_ingress_drift')
    require(original.count(SHARED_NAMES) == 1 and not original.count(RESTRICTED_NAMES), 'normal443_original_shared_names')
    require(type(template) is bytes and 0 < len(template) <= 16384 and b'\0' not in template, 'normal443_template_bytes')
    result = original.replace(SHARED_NAMES, RESTRICTED_NAMES, 1) + b'\n' + template
    require(len(result) <= 128 * 1024, 'normal443_candidate_ingress_bound')
    require(result[:-len(template)-1].replace(RESTRICTED_NAMES, SHARED_NAMES, 1) == original,
            'normal443_other_ingress_bytes_preserved')
    return result

def contract(raw):
    matches = re.findall(rb'<!-- owner-normal443-contract -->\s*```json\s*(.*?)```', raw, re.S)
    require(len(matches) == 1, 'normal443_single_contract')
    result = json.loads(matches[0])
    require(result.get('format') == 1 and result.get('source_base') == BASE
        and result.get('approved_source_paths') == sorted(ALLOWED)
        and result.get('ingress_path') == INGRESS and result.get('original_ingress_sha256') == OLD_INGRESS_SHA
        and result.get('private_ingress_sha256') == PRIVATE_INGRESS_SHA and result.get('caddy_sha256') == CADDY_SHA
        and result.get('origin') == 'https://app.quillmd.com'
        and result.get('private_origin') == 'https://app.quillmd.com:9443'
        and result.get('provider_calls') == result.get('authentication_submissions') == result.get('database_writes') == 0
        and result.get('automatic_retries') is False and result.get('outer_ceiling_seconds') == OUTER_SECONDS,
        'normal443_exact_prospective_scope')
    return result

def source_gate(target):
    require(qualified(), 'normal443_source_protocol_unqualified')
    require(re.fullmatch('[a-f0-9]{40}', target or '') and SOURCE.is_relative_to(ROOT / '.worktrees')
        and SOURCE.resolve() == SOURCE and os.getuid() == os.geteuid() == os.getgid() == os.getegid() == 1000,
        'normal443_operations_identity')
    require(old.git(SOURCE, 'rev-parse', 'HEAD').strip().decode() == target
        and old.git(ROOT, 'rev-parse', 'origin/main').strip().decode() == target
        and not old.git(SOURCE, 'status', '--porcelain', '--untracked-files=no').strip(),
        'normal443_exact_clean_merged_source')
    old.git(SOURCE, 'merge-base', '--is-ancestor', BASE, target)
    require(set(old.git(SOURCE, 'diff', '--name-only', BASE, target).decode().splitlines()) == ALLOWED,
            'normal443_exact_source_scope')
    buffers = {}
    dependencies = (*NATIVE, ACCEPTANCE, RECOVERY_DECL, 'docs/foundation/mutations/20261007-quillmd-owner-acceptance-v3.md',
                    'scripts/check-citation.sh', 'scripts/lib/runs-api.sh')
    with source_files.open_root(SOURCE) as fd:
        for relative in dict.fromkeys((*sorted(ALLOWED), *dependencies)):
            index = old.git(SOURCE, 'ls-files', '-s', '--', relative).decode().split()
            require(len(index) >= 4 and index[0] in ('100644', '100755'), 'normal443_source_index_type')
            raw = source_files.operator_bytes(relative, 0o644 if index[0] == '100644' else 0o755, fd)
            require(raw == old.git(SOURCE, 'show', target + ':' + relative), 'normal443_source_bytes')
            if relative not in ALLOWED:
                require(raw == old.git(SOURCE, 'show', BASE + ':' + relative), 'normal443_unchanged_operational_dependency')
            buffers[relative] = raw
    result = contract(buffers[DECL])
    application_gate(buffers['rebuild/core/preview_access.py'], buffers['rebuild/quillmd/settings.py'])
    require(set(old.git(SOURCE, 'diff', '--name-only', result['private_accepted_revision'], BASE).decode().splitlines()) == PRIVATE_OPS, 'normal443_intermediate_four_operational_paths')
    require(all(result.get(key) is True for key in ('active_protocol_qualified', 'private_acceptance_qualified',
                'ingress_publication_qualified')), 'normal443_committed_qualification')
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(os.environ.get('RULED_MUTATION_DECLARATION') == DECL and re.fullmatch('[a-f0-9]{40}', commit)
        and old.git(SOURCE, 'log', '-1', '--format=%H', '--', DECL).strip().decode() == commit
        and old.git(SOURCE, 'show', commit + ':' + DECL) == buffers[DECL], 'normal443_normal_ruled_door')
    require(os.environ.get('RULED_ACT_MAX_SECS') == str(OUTER_SECONDS), 'normal443_explicit_outer_ceiling')
    for revision in dict.fromkeys((BASE, target, result.get('private_accepted_revision'))):
        require(re.fullmatch('[a-f0-9]{40}', revision or ''), 'normal443_prior_revision_pin')
        source_files.sealed_citation(buffers['scripts/check-citation.sh'], buffers['scripts/lib/runs-api.sh'], revision)
    return result, buffers

def pinned_receipt(item, label, expected_path):
    require(isinstance(item, dict) and set(item) == {'path', 'sha256'}
        and item['path'] == str(expected_path) and re.fullmatch('[a-f0-9]{64}', item['sha256'] or ''), label)
    raw = source_files.protected(expected_path)
    require(sha(raw) == item['sha256'], label)
    return json.loads(raw), raw

def private_receipts(policy):
    values = {key: pinned_receipt(policy.get(key), 'normal443_' + key + '_pin', path)
              for key, path in PRIVATE_PATHS.items()}
    accepted, report, authority, availability = [values[key][0] for key in PRIVATE_PATHS]
    require(accepted.get('format') == 3 and accepted.get('complete') is True
        and accepted['operations_revision'] == BASE and accepted['served_revision'] == policy['private_accepted_revision']
        and accepted['independent_report'] == str(PRIVATE_PATHS['private_report'])
        and accepted['independent_report_sha256'] == policy['private_report']['sha256']
        and accepted['availability_preserved'] is True and accepted['provider_retries'] == 0,
        'normal443_completed_private_acceptance')
    require(report.get('complete') is True and report['operations_revision'] == BASE
        and report['served_revision'] == accepted['served_revision']
        and report['activation_sha256'] == policy['availability']['sha256']
        and report['provider_calls'] == report['database_writes'] == 0
        and {row['name'] for row in report['cases']} == {'soap-typed', 'custom-word-typed', 'soap-voice', 'allergy-missing', 'allergy-legitimate'}
        and len(report['cases']) == 5 and report['preservation']['all_36_tables_all_old_rows_columns_compared'] is True
        and report['preservation']['all_67_old_referenced_files_preserved'] is True,
        'normal443_complete_independent_private_report')
    require(authority['phase'] == 'verify' and authority['operations_revision'] == BASE
        and authority['served_revision'] == accepted['served_revision']
        and availability.get('complete') is True and availability['source']['operator_commit'] == accepted['served_revision'],
        'normal443_private_chain_identity')
    return values

def controlled_environment(original, previous, target, *, enabled):
    values = dotenv_values(stream=StringIO(original.decode()), interpolate=False)
    require(values.get('QUILLMD_RELEASE_SHA') == previous and values.get('QUILLMD_APP_BASE_URL') == 'https://app.quillmd.com:9443'
        and values.get('QUILLMD_PREVIEW_AUTH_ENABLED') == '1'
        and values.get('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED') in (None, '', '0', '1'), 'normal443_original_environment')
    require(re.fullmatch('[a-f0-9]{40}', target or '') and type(enabled) is bool, 'normal443_environment_target')
    assignments = {'QUILLMD_RELEASE_SHA': target, 'QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED': '1' if enabled else '0'}
    result, counts = [], {key: 0 for key in assignments}
    for line in original.splitlines(keepends=True):
        match = old.ASSIGNMENT.match(line)
        key = match[1].decode() if match else None
        if key in assignments:
            counts[key] += 1; result.append((key + '="' + assignments[key] + '"\n').encode())
        else: result.append(line)
    require(counts['QUILLMD_RELEASE_SHA'] == 1 and counts['QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'] <= 1,
            'normal443_duplicate_controlled_assignment')
    if counts['QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'] == 0:
        require(not result or result[-1].endswith(b'\n'), 'normal443_environment_append_separator')
        result.append(('QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED="' + assignments['QUILLMD_OWNER_NORMAL_ORIGIN_ENABLED'] + '"\n').encode())
    updated = b''.join(result)
    after = dotenv_values(stream=StringIO(updated.decode()), interpolate=False)
    require(all(after.get(key) == value for key, value in assignments.items())
        and {key: value for key, value in values.items() if key not in assignments}
          == {key: value for key, value in after.items() if key not in assignments}, 'normal443_only_two_environment_values')
    return updated

def compare_guard(before, after, *, ingress=None):
    require(set(before) == set(after), 'normal443_guard_population')
    for key in ('database', 'files', 'mail', 'static'):
        require(before[key] == after[key], 'normal443_guard_' + key)
    expected = dict(before['configuration'])
    if ingress is not None: expected[INGRESS] = ingress
    require(expected == after['configuration'], 'normal443_only_declared_ingress_delta')
    require(after['database']['pending_jobs'] == after['database']['held'] == 0,
            'normal443_idle_worker_finances')
    return True

def memory_verifier(module):
    """Remove only the checked exclusive output sink; return its complete report."""
    require(sha(module.__authenticated_source) == FROZEN_V3, 'normal443_frozen_verifier_hash')
    function = copy_function(module.__authenticated_source, 'verify')
    constants = [node for node in ast.walk(function) if isinstance(node, ast.Constant) and node.value == 'installed-acceptance-v2-20261006']
    require(len(constants) == 4 and {node.lineno for node in constants} == {942,973,998,1044}, 'normal443_exact_campaign_literals')
    for node in constants: node.value = Path(module.CAMPAIGN).name
    require(len(function.body) > 5 and ast.unparse(function.body[-5]) == 'destination = Path(args.output)'
        and isinstance(function.body[-4], ast.Expr) and isinstance(function.body[-3], ast.Assign)
        and isinstance(function.body[-2], ast.With) and isinstance(function.body[-1], ast.Expr)
        and 'os.O_EXCL' in ast.unparse(function.body[-3])
        and ast.unparse(function.body[-1]).startswith('print(json.dumps('), 'normal443_exact_report_sink')
    function.body[-5:] = [ast.Return(value=ast.Name(id='report', ctx=ast.Load()))]
    namespace = dict(module.__dict__)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])), module.__file__, 'exec'), namespace)
    return namespace['verify'], namespace

def copy_function(raw, name):
    import copy
    nodes = [node for node in ast.parse(raw).body if isinstance(node, ast.FunctionDef) and node.name == name]
    require(len(nodes) == 1, 'normal443_exact_frozen_function')
    return copy.deepcopy(nodes[0])

def normal_controller_command(operations, source, mode, pid, started, acquired, deadline, *,
                              parse_start,
                              monotonic=time.monotonic,
                              read_bytes=lambda path: Path(path).read_bytes(),
                              read_text=lambda path: Path(path).read_text()):
    """Authenticate this normal controller; never reinterpret private authority."""
    now = monotonic()
    require(pid == os.getpid() and os.getuid() == os.geteuid() == 1000
        and mode in ('--execute', '--preflight') and re.fullmatch('[a-f0-9]{40}', operations or '')
        and type(acquired) in (int, float) and type(deadline) in (int, float)
        and math.isfinite(acquired) and math.isfinite(deadline)
        and 0 < acquired <= now < deadline and callable(parse_start), 'normal443_own_controller_interval')
    proc = Path('/proc') / str(pid)
    command = [str(PYTHON), '-B', str(source / ENTRY), mode, '--operations-revision', operations]
    raw = read_bytes(proc / 'cmdline')
    require(raw == b'\0'.join(value.encode() for value in command) + b'\0', 'normal443_own_fixed_command')
    # The existing authenticated process-start parser handles parentheses in
    # native comm names; no string split silently changes its field position.
    require(parse_start(read_text(proc / 'stat')) == started, 'normal443_own_process_reused')
    return {'controller': 'normal443', 'parent_pid': pid, 'parent_start_ticks': started,
            'own_mode': mode, 'argv_sha256': sha(raw), 'acquired_monotonic': acquired,
            'deadline_monotonic': deadline}

class NativeHost:
    source = SOURCE
    def __init__(self, policy, target, buffers, started, *, mode='--execute'):
        require(qualified(), 'normal443_source_protocol_unqualified')
        self.policy, self.operations, self.buffers = policy, target, buffers
        self.deadline = started + OUTER_SECONDS
        self.mode = mode; self.parent_pid = os.getpid()
        self.served = policy['private_accepted_revision']
        self.inside = False; self.lock_rows = []; self.alignment = None
        self.acceptance = types.ModuleType('_quillmd_normal443_acceptance_' + target)
        self.acceptance.__file__ = str(SOURCE / ACCEPTANCE)
        exec(compile(buffers[ACCEPTANCE], self.acceptance.__file__, 'exec'), self.acceptance.__dict__)
        self.acceptance.execution_gate()
        package = self.acceptance.checked_native_modules(self)
        self.old, self.recovery = package.legacy_model_activation, package.private_availability_recovery
        self.exclusion, self.backup, self.env_writer, self.managed, self.storage = self.old.modules()
        self.native = self.old.Host(self.managed)
        self.common, self.verifier, self.historical_policy = self.acceptance.frozen_modules()
        self.inputs = private_receipts(policy)
        self.authority = self.inputs['private_authority'][0]['authority']
        require(self.authority['operations_revision'] == BASE and self.authority['served_revision'] == self.served,
                'normal443_actual_private_authority')
        for phase in ('before-auth', 'after-auth'):
            item = self.authority['admissions'][phase]
            pinned_receipt(item, 'normal443_private_admission_hash', self.acceptance.PREPARATION / ('admission-' + phase + '.json'))
        self.original_environment = self.old.protected(APP / '.env', 65536)
        self.cipher = self.backup.key_at(self.old.KEY)

    def git(self, tree, *args): return old.git(tree, *args)
    def read_source(self, path):
        relative = str(Path(path).relative_to(SOURCE))
        require(relative in self.buffers, 'normal443_checked_module_read')
        return self.buffers[relative]
    def check(self, reserve=0): require(time.monotonic() + reserve < self.deadline, 'normal443_outer_deadline')
    def snapshot(self): return self.old.snapshot(self.native, self.backup, self.storage)
    def service(self, action, unit):
        require(action in ('start', 'stop') and unit in self.old.UNITS, 'normal443_own_service_scope')
        self.check_hold()
        self.check(0 if getattr(self, 'rolling_back', False) else 500)
        code = "import os,subprocess\nos.chroot('/host');os.chdir('/')\nsubprocess.run(" + repr(
            ['/usr/bin/systemctl', action, unit]) + ",check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
        self.native.helper(code, 40)
    def boundary(self, release):
        result = self.old.await_service_boundary(self.native, self.storage, release)
        proof = self.recovery.completion_unit_provenance(self.native, result)
        self.recovery.await_direct_health(release)
        return {'units': result, 'completion_unit_provenance': proof,
                'worker_configuration_provenance': self.native.worker_configuration(self.old.protected(APP / '.env', 65536), release, result)}
    def foreign(self):
        require(RECOVERY_DECL in self.buffers, 'normal443_checked_recovery_contract')
        # The declaration is authenticated separately to BASE, as are all retained
        # V8/V15/owner decision inputs consumed by this unchanged native reader.
        declaration = self.buffers[RECOVERY_DECL]
        require(declaration == self.git(ROOT, 'show', self.served + ':' + self.recovery.DECL), 'normal443_recovery_declaration')
        policy = self.recovery.contract_from_bytes(declaration)
        return self.recovery.loaded_external_state(self.native, policy['external_configuration_ack'])
    @contextmanager
    def hold(self):
        with ExitStack() as stack:
            def acquire(relative, seconds):
                with source_files.open_root(RUNTIME / Path(relative).parent) as parent:
                    fd = os.open(Path(relative).name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
                stack.callback(os.close, fd)
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 1000
                    and stat.S_IMODE(info.st_mode) == 0o600 and info.st_nlink == 1, 'normal443_existing_owned_lock')
                end = min(self.deadline, time.monotonic() + seconds)
                while True:
                    try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                    except BlockingIOError:
                        require(time.monotonic() < end, 'normal443_lock_drain_timeout'); time.sleep(.05)
                self.lock_rows.append({'path': str(RUNTIME / relative), 'fd': fd, 'device': info.st_dev, 'inode': info.st_ino})
            for relative in self.acceptance.LOCKS: acquire(relative, 30)
            policy = self.recovery.contract_from_bytes(self.buffers[RECOVERY_DECL])
            sources = self.recovery.publisher_unit_sources()
            observe = self.recovery.publisher_observer(self.backup)
            selected = self.recovery.await_natural_publication(policy, observe)
            acquire(self.acceptance.PUBLICATION_LOCK, 120)
            acquired = time.monotonic()
            current = observe()
            require(current['coherent_unit'] and all(current[name] == selected[name] for name in ('row', 'unit', 'timer', 'journal'))
                and self.recovery.publisher_unit_sources() == sources, 'normal443_selected_publication_drift')
            self.alignment = {'selected': selected, 'unit_sources': sources,
                'hold': {'acquired_monotonic': acquired, 'deadline_monotonic': self.deadline}}
            self.parent_start = self.acceptance.process_start(Path('/proc/self/stat').read_text())
            self.inside = True
            try: self.check_hold(); yield
            finally: self.inside = False; self.lock_rows = []; self.alignment = None
    def check_hold(self):
        self.check()
        require(self.inside and len(self.lock_rows) == 5
            and {row['path'] for row in self.lock_rows} == {str(RUNTIME / name) for name in (*self.acceptance.LOCKS, self.acceptance.PUBLICATION_LOCK)}
            and self.acceptance.process_start(Path('/proc/self/stat').read_text()) == self.parent_start,
            'normal443_same_five_lock_parent')
        controller = normal_controller_command(self.operations, self.source, self.mode, self.parent_pid,
            self.parent_start, self.alignment['hold']['acquired_monotonic'], self.deadline,
            parse_start=self.acceptance.process_start)
        held = self.acceptance.lock_population(Path('/proc/locks').read_text(), os.getpid())
        for row in self.lock_rows:
            info = os.fstat(row['fd'])
            with source_files.open_root(Path(row['path']).parent) as parent:
                attached = os.stat(Path(row['path']).name, dir_fd=parent, follow_symlinks=False)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 1000 and stat.S_IMODE(info.st_mode) == 0o600
                and info.st_nlink == 1 and (info.st_dev, info.st_ino) == (row['device'], row['inode']) == (attached.st_dev, attached.st_ino)
                and (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino) in held, 'normal443_kernel_five_locks')
        require(self.acceptance.process_start(Path('/proc/self/stat').read_text()) == self.parent_start,
                'normal443_controller_final_process_race')
        return {**controller, 'locks': [dict(row) for row in self.lock_rows],
                'same_five_kernel_locks_verified': True}
    def observe_publication(self):
        self.check_hold()
        fields = ('InvocationID', 'ExecMainStartTimestampMonotonic', 'ExecMainExitTimestampMonotonic')
        before = self.recovery.own_unit_properties(self.acceptance.PUBLISHER, fields)
        current = self.recovery.publisher_observer(self.backup)()
        after = self.recovery.own_unit_properties(self.acceptance.PUBLISHER, fields)
        require(before == after and after['InvocationID'] == current['unit']['InvocationID'], 'normal443_latest_invocation_race')
        selected = self.alignment['selected']['unit']
        end = (datetime.strptime(selected['ExecMainExitTimestamp'], '%a %Y-%m-%d %H:%M:%S UTC') + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S UTC')
        journal = self.old.command(['/usr/bin/journalctl', '-u', self.acceptance.PUBLISHER,
            '--since', selected['ExecMainStartTimestamp'], '--until', end, '-o', 'json', '--no-pager'])
        current.update(unit_monotonic={key: after[key] for key in fields if key != 'InvocationID'},
            selected_journal=[(row.get('_SYSTEMD_INVOCATION_ID'), row.get('MESSAGE')) for row in map(json.loads, journal.splitlines())],
            unit_sources=self.recovery.publisher_unit_sources())
        current['normal_controller_witness'] = self.check_hold(); return current
    def publisher_admission(self, conn, original, policy):
        args, kwargs = self.acceptance.captured_publisher_factory(self.verifier,
            self.recovery.publisher_observation_connection(conn), original, policy)
        current = self.observe_publication()
        witness = self.acceptance.held_publication_admission(self.alignment, current, time.monotonic())
        selected = self.alignment['selected']; names = self.acceptance.PUBLISHER_JUDGE_FIELDS
        require(self.acceptance.canonical_publisher_comparison(args[1]) == self.acceptance.canonical_publisher_comparison(current['row'])
            and args[2] == {key: current['unit'][key] for key in names} and args[3] == current['journal'], 'normal443_real_factory_observation')
        genuine = {key: selected['unit'][key] for key in names}
        def final(actual, row, unit, journal):
            latest = self.observe_publication()
            require(latest == current, 'normal443_final_publication_race')
            self.acceptance.held_publication_admission(self.alignment, latest, time.monotonic())
            require(self.acceptance.canonical_publisher_comparison(actual['row']) == row
                and actual['unit'] == {key: latest['unit'][key] for key in names} and actual['journal'] == latest['journal']
                and unit == genuine and journal == selected['journal'], 'normal443_real_callback_binding')
            return True
        proof = self.acceptance.publisher_final_adapter(self.verifier, final)(args[0], current['row'], genuine, selected['journal'], **kwargs)
        return {**proof, 'latest_invocation_assessment': witness, 'selected_previous_genuine_publication': selected}
    def current_private_completion(self, receipt):
        actual = self.recovery.completion_unit_provenance(self.native, receipt['units_after'])
        require(actual == receipt['completion_unit_provenance'] and sha(self.old.protected(APP/'.env',65536)) == receipt['environment_after_sha256'], 'normal443_same_private_completion_identity')
        return actual
    def full_preservation(self):
        import psycopg
        from psycopg.rows import dict_row
        self.check_hold()
        _, _, manifest, original = self.verifier.original_continuation_capture(self.historical_policy, datetime.now(timezone.utc))
        require(len(original) == 36 and manifest['tables']['django_session']['rows'] == 212, 'normal443_original_36_tables_212_sessions')
        columns = original['core_servicehealth']['columns']
        original_health = [row for row in self.verifier.row_mapping('core_servicehealth', original['core_servicehealth']['rows'], columns, ['id']).values() if row['key'] == b'backup']
        require(len(original_health) == 1, 'normal443_original_backup_identity')
        with psycopg.connect(**self.backup.source_options(APP, self.old.ROLES), row_factory=dict_row) as conn:
            self.acceptance.readonly_connection_flags(conn)
            publisher = self.publisher_admission(conn, original_health[0], self.historical_policy)
            with conn.cursor().copy("COPY (SELECT * FROM core_servicehealth WHERE key='backup') TO STDOUT") as stream:
                current = b''.join(bytes(chunk) for chunk in stream)
            rows = self.verifier.row_mapping('core_servicehealth', current.splitlines(keepends=True), columns, ['id'])
            require(len(rows) == 1, 'normal443_current_backup_identity')
            health = next(iter(rows.values()))
            require(self.verifier.service_health_original(health) == publisher['current_full_row'], 'normal443_full_current_backup_copy')
            conn.rollback()
        raw = self.acceptance.protected(self.acceptance.FROZEN / 'verify_installed_acceptance_v3.py')
        module = self.acceptance.verifier_adapter(raw, self.common, self.authority, self.verifier,
                                                 self.current_private_completion,
                                                 publisher_admission=self.publisher_admission)
        setattr(module, '__authenticated_source', raw)
        genuine_old = module.admitted_original_row
        def admitted(original_row, names, transition, table, actor, authentication):
            result = genuine_old(original_row, names, transition, table, actor, authentication)
            if table != 'core_servicehealth': return result
            require(all(health[key] == original_row[key] for key in ('id', 'created_at', 'key'))
                and self.verifier.service_health_original(health) == publisher['current_full_row'], 'normal443_only_source_adjudicated_backup_progress')
            return dict(health)
        module.admitted_original_row = admitted
        verify, _ = memory_verifier(module)
        report = verify(types.SimpleNamespace(progress=str(self.acceptance.CAMPAIGN / 'progress.json'), output=None))
        self.check_hold()
        require(report['complete'] is True and report['provider_calls'] == report['database_writes'] == 0
            and report['served_revision'] == self.served, 'normal443_complete_original_and_new_campaign_verification')
        # This is a new read-only report, not the immutable private receipt.
        # Its admitted backup progress must not inherit the old report's false
        # claim that no further health publication was admitted.
        report['preservation'] = {**report['preservation'], 'new_health_publications_admitted': True,
            'health_publication_admission': 'complete current row independently source-adjudicated against original identity'}
        return {'private_workflow_report': report, 'current_source_adjudicated_backup': publisher,
                'original_capture_replaced': False, 'current_population_guard_is_not_a_new_historical_baseline': True}
    def ingress(self):
        path = Path(INGRESS)
        with source_files.open_root(path.parent) as fd:
            leaf = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            try:
                info = os.fstat(leaf)
                require(stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0 and stat.S_IMODE(info.st_mode) == 0o644
                    and info.st_nlink == 1 and not os.listxattr(leaf), 'normal443_public_ingress_metadata')
                raw = source_files.bytes_at(leaf, 128*1024)
                again = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                require(source_files.stable(info) == source_files.stable(again), 'normal443_public_ingress_race')
                return raw, {'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode),
                             'device': info.st_dev, 'inode': info.st_ino, 'sha256': sha(raw)}
            finally: os.close(leaf)
    def replace_ingress(self, original, candidate, metadata):
        self.check_hold()
        require(type(original) is bytes and type(candidate) is bytes and 0 < len(candidate) <= 128 * 1024
            and set(metadata) == {'uid', 'gid', 'mode', 'device', 'inode', 'sha256'}
            and metadata['uid'] == metadata['gid'] == 0 and metadata['mode'] == 0o644
            and metadata['sha256'] == sha(original), 'normal443_ingress_helper_inputs')
        # The helper has one writable mount, exactly this nginx directory. It
        # changes one fixed file and never grants writes to any co-tenant path.
        code = """import os,stat,json,hashlib,base64,subprocess
root=os.open('/target',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
os.chroot('/host');os.chdir('/')
name='quillmd';temporary='.quillmd-owner-normal443-v1-candidate'
expected=EXPECTED
replacement=base64.b64decode(REPLACEMENT)
def digest(v):return hashlib.sha256(v).hexdigest()
def current():
 f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=root)
 try:
  i=os.fstat(f);assert stat.S_ISREG(i.st_mode) and i.st_nlink==1 and not os.listxattr(f)
  raw=os.read(f,131073);assert len(raw)==i.st_size<=131072
  m={'uid':i.st_uid,'gid':i.st_gid,'mode':stat.S_IMODE(i.st_mode),'device':i.st_dev,'inode':i.st_ino,'sha256':digest(raw)}
  assert os.stat(name,dir_fd=root,follow_symlinks=False).st_ino==i.st_ino
  return raw,m
 finally:os.close(f)
old,m=current();assert m==expected and m['uid']==m['gid']==0 and m['mode']==420
assert digest(old)==ORIGINAL_SHA
f=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,420,dir_fd=root)
try:
 os.fchmod(f,420);assert os.write(f,replacement)==len(replacement);os.fsync(f)
 assert current()[1]==expected
 os.replace(temporary,name,src_dir_fd=root,dst_dir_fd=root);os.fsync(root)
finally:
 os.close(f)
 try:os.unlink(temporary,dir_fd=root)
 except FileNotFoundError:pass
subprocess.run(['/usr/sbin/nginx','-t'],check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['/usr/bin/systemctl','reload','nginx.service'],check=True,timeout=30,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
raw,m=current();assert digest(raw)==digest(replacement)
print(json.dumps(m,sort_keys=True))
""".replace('EXPECTED', repr(metadata)).replace('REPLACEMENT', repr(base64.b64encode(candidate))).replace('ORIGINAL_SHA', repr(sha(original)))
        argv = ['docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none', '--network', 'none', '--pid=host',
            '--mount', 'type=bind,src=/,dst=/host,readonly', '--mount', 'type=bind,src=/etc/nginx/sites-available,dst=/target',
            self.managed.IMAGE, 'python', '-B', '-']
        result = json.loads(self.managed.run_helper(argv, input=code.encode(), timeout=60,
                                                  failure_directory=OUTPUT).stdout)
        self.check_hold()
        return result
    def forward(self, target):
        self.check_hold()
        result = subprocess.run(['git', '-C', str(ROOT), 'merge', '--ff-only', target], capture_output=True, timeout=30, umask=0o022)
        require(result.returncode == 0 and self.git(ROOT, 'rev-parse', 'HEAD').strip().decode() == target
            and not self.git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'normal443_source_fast_forward')
        self.recovery.source_readability(ROOT)
    def write(self, name, value):
        raw = value if isinstance(value, bytes) else encode(value)+b'\n'
        path = ATTEMPT if name == 'attempt' else OUTPUT / name
        with source_files.open_root(path.parent) as parent:
            fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            with os.fdopen(fd, 'wb') as stream: stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    def routes(self):
        import httpx
        with httpx.Client(trust_env=False, follow_redirects=False, timeout=10) as client:
            statuses = {}
            for origin, expected in (('https://app.quillmd.com',503), ('https://admin.quillmd.com',503),
                                      ('https://quillmd.com',200), ('https://www.quillmd.com',200), ('https://pro.quillmd.com',410)):
                response = client.get(origin+'/', headers={'Cookie':''})
                require(response.status_code == expected, 'normal443_anonymous_or_cotenant_http')
                if expected == 503:
                    require(response.headers.get('retry-after') == '3600' and response.headers.get('cache-control') in ('no-store', 'no-store, no-store'), 'normal443_maintenance_headers')
                statuses[origin] = response.status_code
            return statuses

def transition(host, policy, target, buffers, *, execute=False):
    require(type(buffers) is dict and TEMPLATE in buffers, 'normal443_checked_template_buffer')
    require(not os.path.lexists(OUTPUT) and not os.path.lexists(ATTEMPT), 'normal443_single_consumable_attempt')
    with host.hold():
        host.check(500)
        require(host.git(ROOT, 'rev-parse', 'HEAD').strip().decode() == policy['private_accepted_revision']
            and host.git(ROOT, 'branch', '--show-current').strip() == b'main'
            and not host.git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'normal443_exact_prior_served_source')
        before = host.snapshot()
        require(before['database']['pending_jobs'] == before['database']['held'] == 0, 'normal443_idle_current_population')
        private = host.full_preservation()
        # Bind the complete verifier to the same observed transition population.
        # The input locks do not prevent an owner/browser from writing an old
        # row between verification and the guard capture.
        compare_guard(before, host.snapshot())
        foreign = host.foreign()
        original, metadata = host.ingress()
        require(before['configuration'][INGRESS] == metadata
            and metadata == policy['original_ingress_metadata']
            and before['configuration'][PRIVATE_INGRESS]['sha256'] == PRIVATE_INGRESS_SHA
            and before['configuration'][str(ROOT/'Caddyfile')]['sha256'] == CADDY_SHA, 'normal443_ingress_and_caddy_boundary')
        candidate = render_ingress(original, buffers[TEMPLATE])
        prior = policy['private_accepted_revision']
        updated = controlled_environment(host.original_environment, prior, target, enabled=True)
        disabled = controlled_environment(host.original_environment, prior, target, enabled=False)
        own = host.boundary(prior)
        compare_guard(before, host.snapshot())
        require(host.foreign() == foreign, 'normal443_foreign_initial_race')
        if not execute:
            return {'complete':True,'read_only_preflight':True,'execution_performed':False,
                'candidate_sha256':sha(candidate),'full_original_and_new_acceptance_population_reverified':True,
                'original_capture_replaced':False,'provider_calls':0,'authentication_submissions':0,'database_writes':0}
        host.check(500)
        OUTPUT.mkdir(mode=0o700)
        prepared = {'format':1,'complete':False,'protocol':'owner-normal443-active-source-v1', 'previous_served_revision':prior,
            'served_revision':target,'private_acceptance_sha256':policy['private_acceptance']['sha256'],
            'preservation':private,'guard_before':before,'foreign_before':foreign,'units_before':own,
            'candidate_sha256':sha(candidate),'original_ingress_metadata':metadata,'provider_calls':0,
            'authentication_submissions':0,'database_writes':0,'original_capture_replaced':False,'automatic_retries':False}
        forwarded = False; ingress_helper_completed = False; mutation_started = False
        try:
            host.write('environment-before.fernet',host.cipher.encrypt(host.original_environment))
            host.write('environment-enabled.fernet',host.cipher.encrypt(updated))
            host.write('environment-disabled.fernet',host.cipher.encrypt(disabled))
            host.write('original-ingress.conf',original); host.write('prepared.json',prepared)
            compare_guard(before, host.snapshot()); host.check(500)
            require(host.foreign() == foreign, 'normal443_foreign_before_marker_race')
            host.write('attempt',{'format':1,'attempt':1,'served_revision':target,'output':str(OUTPUT),'provider_calls':0,'authentication_submissions':0,'automatic_retries':False})
            mutation_started = True
            for unit in reversed(host.old.UNITS): host.service('stop',unit)
            compare_guard(before, host.snapshot())
            host.forward(target); forwarded = True
            host.env_writer.replace_environment(APP/'.env',host.original_environment,updated)
            for unit in host.old.UNITS: host.service('start',unit)
            active = host.boundary(target)
            compare_guard(before, host.snapshot())
            require(host.foreign() == foreign, 'normal443_foreign_post_start_race')
            host.check(500)
            new_metadata = host.replace_ingress(original,candidate,metadata); ingress_helper_completed = True
            compare_guard(before, host.snapshot(), ingress=new_metadata)
            statuses = host.routes()
            compare_guard(before, host.snapshot(), ingress=new_metadata)
            require(host.foreign() == foreign and host.boundary(target) == active, 'normal443_final_source_or_foreign_race')
            completed = {**prepared,'complete':True,'stage':'complete','units_after':active,'ingress_after':new_metadata,
                'anonymous_http_statuses':statuses,'owner_normal_origin_enabled':True,'preview_origin':'https://app.quillmd.com:9443',
                'normal_origin':'https://app.quillmd.com','full_original_and_new_acceptance_population_preserved':True,
                'actual_provider_model_reverified_by_this_transition':False,'workflow_byte_identity_inherited_from_private_acceptance':True}
            host.write('complete.json',completed)
            return {'complete':True,'application_url':'https://app.quillmd.com/','private_origin':'https://app.quillmd.com:9443',
                'served_revision':target,'restricted_to_existing_owner_grants':True,'provider_calls':0,'authentication_submissions':0,'database_writes':0}
        except BaseException as error:
            if not mutation_started:
                host.write('failed.json',{**prepared,'stage':'preparation_failed','failure_kind':type(error).__name__,'mutation_started':False,'service_actions':0,'ingress_actions':0,'automatic_retries':False})
                raise Refusal('normal443_preparation_failed_preserving_availability') from None
            host.rolling_back = True
            rollback = {'attempted':True,'source_reset':False,'provider_calls':0,'authentication_submissions':0,
                        'ingress_observed_before_rollback': 'unassessed'}
            try:
                actual_revision = host.git(ROOT, 'rev-parse', 'HEAD').strip().decode()
                require(actual_revision in (prior, target)
                    and host.git(ROOT, 'branch', '--show-current').strip() == b'main'
                    and not host.git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(),
                    'normal443_rollback_known_source')
                # A successful merge can be followed by a failed read-through
                # or interrupted return. Decide from actual HEAD, never from
                # whether the forward method happened to return to this caller.
                forwarded = actual_revision == target
                current, current_metadata = host.ingress()
                rollback['ingress_observed_before_rollback'] = current_metadata
                if sha(current) == sha(candidate):
                    restored = host.replace_ingress(current,original,current_metadata)
                else:
                    require(current == original, 'normal443_rollback_unknown_ingress'); restored = current_metadata
                for unit in reversed(host.old.UNITS): host.service('stop',unit)
                environment = host.old.protected(APP/'.env',65536)
                if forwarded:
                    require(environment in (host.original_environment,updated,disabled), 'normal443_rollback_unknown_environment')
                    if environment != disabled:host.env_writer.replace_environment(APP/'.env',environment,disabled)
                    release = target
                else:
                    require(environment == host.original_environment, 'normal443_rollback_pre_forward_environment');release = prior
                for unit in host.old.UNITS:host.service('start',unit)
                rollback['units'] = host.boundary(release)
                compare_guard(before, host.snapshot(), ingress=restored)
                require(host.foreign() == foreign, 'normal443_rollback_foreign_preservation')
                rollback.update(complete=True,private_availability_preserved=True,owner_normal_origin_enabled=False,served_revision=release,ingress=restored)
            except BaseException:
                rollback.update(complete=False,private_availability_preserved=False,fail_stop=host.old.best_effort_private_stop(host.native))
            host.write('failed.json',{**prepared,'stage':'failed','failure_kind':type(error).__name__,'rollback':rollback,
                'ingress_helper_completed_before_failure':ingress_helper_completed,'automatic_retries':False})
            raise Refusal('normal443_failed_with_preserved_evidence') from None

def main(argv=None, *, host=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--operations-revision')
    mode=parser.add_mutually_exclusive_group();mode.add_argument('--preflight',action='store_true');mode.add_argument('--execute',action='store_true')
    args=parser.parse_args(argv)
    if not (args.preflight or args.execute):
        print(json.dumps({'execution_performed':False,'installed_state_accessed':False,'active_protocol_qualified':ACTIVE_PROTOCOL_QUALIFIED,
            'private_acceptance_qualified':PRIVATE_ACCEPTANCE_QUALIFIED,'ingress_publication_qualified':INGRESS_PUBLICATION_QUALIFIED,
            'provider_calls':0,'authentication_submissions':0,'database_writes':0,'automatic_retries':False},sort_keys=True));return 0
    started=time.monotonic();policy,buffers=source_gate(args.operations_revision)
    host=host if host is not None else NativeHost(policy,args.operations_revision,buffers,started,
                                                mode='--execute' if args.execute else '--preflight')
    result=transition(host,policy,args.operations_revision,buffers,execute=args.execute)
    print(json.dumps(result,sort_keys=True));return 0 if result['complete'] else 2
