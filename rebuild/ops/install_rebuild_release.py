#!/usr/bin/env python3
"""Install one code-only rebuild release: the shared tree moves from --base to --candidate.

Without --execute this is a real, read-only preflight: it checks every precondition it can without changing
anything, prints the plan and the declaration contract, and exits non-zero on any failure. With --execute it
performs the act, and only under scripts/run-ruled-mutation.sh.

INTERPRETATION 67 (docs/foundation/rulings/2026-10-23-cpt-studio-gi.md) binds it:
  D1  Code only. The live venv stays exactly as found, asserted by a full footprint before and after the act
      (venv_footprint.snapshot / require_exact). A rebuild/requirements.txt change is admitted only together with
      that check (admit_requirements), and every pin the venv does not satisfy must be declared. Nothing here
      runs pip.
  D2  No rollback downgrades the venv. This module has no dependency path at all. The reverse act is a separate
      declared act (docs/runbooks/rebuild-release-install-20261031.md) and runs no pip either.
  D3  Foreign services, the Corti candidate pair included, keep their MainPID and InvocationID through the act,
      exactly as the October engine required (prior.foreign_services). The venv-sharing ones must also be idle
      before anything stops, and are measured again after the resume.
  D4  The declaration is merged to main before the act, so the candidate contains it. It must be tracked,
      unmodified and committed in the candidate worktree, and the strict gate of run-ruled-mutation.sh must pass.

HOW THE TRACKED ENGINE IS BOUND, AND WHY ITS execute() IS NOT CALLED
The engine rebuild/ops/activate_core_workflow_repair.py and its primitives are imported only after their bytes
match ENGINE_PINS (the same eight pins the October operator used), then bound the way that operator bound them:
BASE, SOURCE and STATIC on the engine and on activate_rowan_corti. Every check and action of the act is one of
their functions: source_plan and publish_source (clean main at base, origin/main == candidate, the exact
whole-repository delta, no deletions, per-file proofs, `git merge --ff-only` under umask 022 with no post-merge
hook), render_environment (QUILLMD_RELEASE_SHA only), snapshot and unchanged (database), private_storage.inventory
(clinical files), Host (configuration hashes; systemctl through the root docker helper), foreign_services,
operation_locks, activation_exclusion.hold, await_health, stop_failed_resume, verify_original_before_resume.

The ORDER of those calls (the engine's execute(), activate_core_workflow_repair.py:185-319) is reproduced in act()
stage for stage instead of calling execute(), because D4 makes one of its checks unsatisfiable by construction:
line 193 requires the declaration's bytes to contain the candidate's own sha and the plan digest, and no file can
contain the sha of the commit that contains it. The declaration is proven the D4 way (declaration_provenance)
and bound to the code through its contract; everything else is the engine's. A test pins the correspondence of
the two stage sequences, so a drift in either one fails CI.
"""
import argparse
from contextlib import ExitStack, contextmanager
import datetime as dt
import hashlib
import importlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import time

ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
VENV = APP / '.venv'
SOURCE = Path(__file__).resolve().parents[2]
SELF = 'rebuild/ops/install_rebuild_release.py'
OPERATOR_FILES = (SELF, 'rebuild/ops/venv_footprint.py', 'rebuild/ops/rebuild_release_backup.py')
FORMAT = 'quillmd-rebuild-release-code-only-v1'
PREFLIGHT_FORMAT = 'quillmd-rebuild-release-preflight-v1'
CONTRACT_FORMAT = 'quillmd-rebuild-release-contract-v1'
MANIFEST_FORMAT = 'quillmd-rebuild-release-manifest-v1'
CONTRACT_MARKER = '<!-- rebuild-release-contract -->'
DECLARATIONS = 'docs/foundation/mutations/'
VENV_POLICY = 'exact-before-and-after'
#: The engine and the primitives it composes, byte-pinned exactly as the October operator pinned them
#: (installed-engine-pins.json). A changed primitive refuses the act until this installer is re-reviewed.
ENGINE_PINS = {
    'activate_core_workflow_repair.py': '436acf8f92c8f146f6be4642e51a0120a547a0f5f2e85a8b6af2de30ecf20785',
    'activate_coordinated_workflow.py': 'dc64eeb8de04f0c73ff762f61147a5e76bf9096706e31b596aa3b853ed691a7a',
    'activate_rowan_corti.py': '38ad5e1d11a216f36da4f3f35c43a5c7dba2a6a0ba5c61542f733b0d5fed5cd4',
    'activation_exclusion.py': '6b55ea3ab70eba8fbc7e4675137ea1da11ff0396a9ed9af5196243c0ae73d2da',
    'backup_restore.py': '6a9953a6e19174c6148fe3ee0a73170017a83f2fef0b3221dbf77be0b92b1351',
    'legacy_model_activation.py': '7858522f287bf79af1defd7b14f43a78153607ca153552d5c772e7abd11b483d',
    'managed_helper.py': 'b6378f202baeecc6e673267d424952835fd432879e61151d40e79df0bee41611',
    'private_storage.py': '3f2264837df9fb465db6049759025501bd8c5d377196503289b63b34fa58a1d0'}
STATIC_PRIMITIVES = ('scripts/activate-typed-voice.py',
                     '4e2efda2357fa2c33262eb2f747ac7201eadbc94875528cde2b7fe9040ebba18')
GUARD_SHA = '13be30775df7ae6f0fc0266e8c1b148ef2bd8aabac8fc954e26b8fdc18b00300'
OWNED_UNITS = ('quillmd-fresh-doctor.service', 'quillmd-fresh-admin.service', 'quillmd-fresh-worker.service')
OPERATION_UNITS = ('quillmd-fresh-backup.service', 'quillmd-fresh-offsite.service',
                   'quillmd-fresh-backup-alerts.service', 'quillmd-fresh-operations-publisher.service')
LOCK_FILES = ('legacy-model-activation.lock', 'backup-monitor/capture.lock', 'automatic-offsite/execution.lock',
              'backup-alerts/monitor.lock', 'publication/.activation-publication.lock')
#: Hooks git can run while `merge --ff-only` updates the index, the ref and the working tree. None may exist at
#: base, and the candidate may not add one: it would be checked out by the merge and then run by it.
MERGE_HOOKS = ('post-merge', 'reference-transaction', 'post-index-change', 'post-checkout', 'pre-merge-commit',
               'post-rewrite')
REFUSED_PARTS = frozenset({'node_modules', '.venv', 'uploads', 'backups', '.git'})
#: activate_rowan_corti's pinned guard reads every blob through `git cat-file` with a 1 MiB output bound.
BLOB_LIMIT = 1024 * 1024
MAX_PATHS = 4000
MAX_DECLARATION_BYTES = 256 * 1024
BACKUP_MAX_AGE = dt.timedelta(hours=12)
#: Scheduled capture 04:30Z and offsite 05:00Z (rebuild/deploy timers), with margins.
QUIET_WINDOWS_UTC = ((dt.time(4, 20), dt.time(4, 50)), (dt.time(4, 55), dt.time(5, 10)))
IDLE_WINDOW_SECONDS = 15
IDLE_MAX_CPU_FRACTION = 0.02
LIVE_VENV_MARKER = str(VENV) + '/bin/'
#: The act writes the rendered environment here and renames it over rebuild/.env (exclusive create).
PENDING_ENVIRONMENT = APP / '.rebuild-release-env-pending'
UNIT_NAME = re.compile(r'[A-Za-z0-9@_.:-]+\.service')
STAGE_LOG = '[rebuild-release]'


class Refusal(RuntimeError):
    """A fixed, non-sensitive label. Exception text from other code is never retained."""


def require(value, label):
    if not value:
        raise Refusal(label)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def note(stage):
    print(STAGE_LOG, now_utc().strftime('%Y-%m-%dT%H:%M:%SZ'), 'stage=' + stage, file=sys.stderr, flush=True)


def full_sha(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{40}', value) is not None


def digest64(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None


def run(argv, *, cwd=None, timeout=120, limit=16 * 1024 * 1024, check=True):
    """A bounded child with a fixed command line; its output is data, never echoed by this module."""
    result = subprocess.run(argv, cwd=cwd, capture_output=True, timeout=timeout)
    require(len(result.stdout) <= limit, 'bounded_command_output')
    if check:
        require(result.returncode == 0, 'command_failed:' + PurePosixPath(argv[0]).name)
    return result


def git(repo, *arguments, timeout=120, limit=16 * 1024 * 1024):
    return run(['git', '--no-optional-locks', '-C', str(repo), *arguments], timeout=timeout, limit=limit).stdout


def git_ok(repo, *arguments):
    return run(['git', '--no-optional-locks', '-C', str(repo), *arguments], check=False).returncode == 0


def ops_module(name, source=None):
    """An unpinned operator module of THIS release, imported from the tree this file runs from."""
    source = source or SOURCE
    rebuild = str(source / 'rebuild')
    if rebuild not in sys.path:
        sys.path.insert(0, rebuild)
    module = importlib.import_module('ops.' + name)
    require(Path(module.__file__).resolve() == source / 'rebuild/ops' / (name + '.py'), 'operator_module_location')
    return module


def pinned_bytes(source=None):
    """sha256 of every engine file on disk, refused unless equal to the pins."""
    source = source or SOURCE
    measured = {}
    for name, digest in ENGINE_PINS.items():
        path = source / 'rebuild/ops' / name
        require(path.resolve(strict=True) == path, 'canonical_engine_path')
        measured[name] = sha(path.read_bytes())
    require(measured == ENGINE_PINS, 'engine_pins')
    static = source / STATIC_PRIMITIVES[0]
    require(static.resolve(strict=True) == static and sha(static.read_bytes()) == STATIC_PRIMITIVES[1],
            'static_primitives_pin')
    return measured


def load_engine(source=None):
    """The sha-pinned tracked engine, imported only after its bytes and its primitives' bytes match."""
    source = source or SOURCE
    pinned_bytes(source)
    engine = ops_module('activate_core_workflow_repair', source)
    prior, preservation, legacy = engine.prior, engine.preservation, engine.prior.legacy
    for module in (engine, prior, preservation, legacy, prior.activation_exclusion, prior.backup_restore,
                   prior.managed_helper, prior.private_storage):
        path = Path(module.__file__).resolve()
        require(path.parent == source / 'rebuild/ops' and ENGINE_PINS.get(path.name) == sha(path.read_bytes()),
                'engine_module_identity')
    require(prior.GUARD_SHA == GUARD_SHA and legacy.STATIC_PRIMITIVES_SHA == STATIC_PRIMITIVES[1]
            and tuple(prior.UNITS) == tuple(legacy.UNITS) == OWNED_UNITS and tuple(legacy.OPERATIONS) == OPERATION_UNITS
            and prior.ROOT == ROOT and prior.APP == APP, 'engine_constants')
    return engine


@contextmanager
def bound(engine, base, static=()):
    """Bind the engine and its primitives to this release, as the October operator did; always restored."""
    prior = engine.prior
    values = {'BASE': base, 'SOURCE': SOURCE, 'STATIC': frozenset(static)}
    saved = [(module, key, getattr(module, key)) for module in (engine, prior) for key in values]
    try:
        for module in (engine, prior):
            for key, value in values.items():
                setattr(module, key, value)
        yield engine
    finally:
        for module, key, value in saved:
            setattr(module, key, value)


def bind_guard(guard):
    """The pinned source guard, with its one base-specific exception removed.

    GROUP_WRITABLE_BASE_PATHS made file_proof REQUIRE mode 0664 for docs/foundation/RULINGS.md at the base of the
    2026-10-09 act. The file is 0644 in today's shared tree, so the unadapted guard would refuse any release whose
    delta modifies RULINGS.md. With the set empty every base file must be exactly 0644 or 0755: stricter, measured.
    validate_published and source_path (the 64-path and path-admission rules) are never called by this installer.
    """
    guard.GROUP_WRITABLE_BASE_PATHS = frozenset()
    return guard


# ----------------------------------------------------------------------------------------------- the manifest
def parse_raw_diff(raw):
    """Entries of `git diff --raw --no-renames -z --no-abbrev`: (status, old_mode, new_mode, old_blob, new_blob, path)."""
    require(isinstance(raw, bytes) and (raw == b'' or raw.endswith(b'\0')), 'nul_terminated_raw_diff')
    fields = raw.split(b'\0')[:-1] if raw else []
    entries, index = [], 0
    while index < len(fields):
        meta = fields[index].decode('ascii')
        parts = meta[1:].split(' ') if meta.startswith(':') else []
        require(len(parts) == 5, 'raw_diff_metadata')
        old_mode, new_mode, old_blob, new_blob, status = parts
        require(not status.startswith(('R', 'C')), 'renames_and_copies_refused')
        require(re.fullmatch('[0-7]{6}', old_mode) and re.fullmatch('[0-7]{6}', new_mode)
                and full_sha(old_blob) and full_sha(new_blob) and re.fullmatch('[A-Z]', status), 'raw_diff_fields')
        require(index + 1 < len(fields), 'raw_diff_path')
        entries.append((status, old_mode, new_mode, old_blob, new_blob, fields[index + 1].decode('utf-8')))
        index += 2
    return entries


def classify(name, status, *, hooks=frozenset()):
    """runtime | requirements | static | support | passenger, or a refusal. Exact membership is checked elsewhere."""
    path = PurePosixPath(name)
    require(type(name) is str and 0 < len(name.encode()) <= 400 and name == str(path) and not path.is_absolute()
            and not set(path.parts) & {'', '.', '..'} and '\\' not in name and name.isprintable(),
            'canonical_manifest_path')
    require(status in ('A', 'M'), 'add_or_modify_only')
    require(name not in hooks, 'merge_time_git_hook')
    require(not set(path.parts) & REFUSED_PARTS, 'refused_path_part')
    if path.parts[0] != 'rebuild':
        return 'passenger'
    require(len(path.parts) >= 2 and 'migrations' not in path.parts, 'rebuild_migration')
    require(path.parts[1] not in ('staticfiles', 'deploy', '.runtime', '.venv'), 'rebuild_generated_or_unit_path')
    if name == 'rebuild/requirements.txt':
        return 'requirements'
    if path.parts[1] == 'static':
        require(len(path.parts) == 3, 'flat_static_source')
        return 'static'
    if 'tests' in path.parts or path.name.startswith('test_') or path.name == 'tests.py':
        return 'support'
    return 'runtime'


def build_manifest(base, entries, blob, *, hooks=frozenset()):
    """The whole-repository delta, one row per path; blob(sha1) returns that blob's bytes."""
    require(full_sha(base), 'full_base_sha')
    require(0 < len(entries) <= MAX_PATHS, 'finite_non_empty_delta')
    paths = {}
    for status, old_mode, new_mode, old_blob, new_blob, name in entries:
        require(name not in paths, 'unique_manifest_path')
        kind = classify(name, status, hooks=hooks)
        require(new_mode in ('100644', '100755'), 'regular_blob_modes_only')
        if status == 'M':
            require(old_mode in ('100644', '100755'), 'regular_blob_modes_only')
        else:
            require(old_mode == '000000' and old_blob == '0' * 40, 'added_path_has_no_base_blob')
        content = blob(new_blob)
        require(len(content) <= BLOB_LIMIT, 'blob_within_guard_bound')
        row = {'status': status, 'class': kind, 'mode': new_mode, 'blob': new_blob, 'bytes': len(content),
               'sha256': sha(content)}
        if status == 'M':
            old = blob(old_blob)
            require(len(old) <= BLOB_LIMIT, 'blob_within_guard_bound')
            row.update(base_mode=old_mode, base_blob=old_blob, base_bytes=len(old), base_sha256=sha(old))
        paths[name] = row
    return {'format': MANIFEST_FORMAT, 'base': base, 'paths': dict(sorted(paths.items()))}


def manifest_digest(manifest):
    return sha(canonical(manifest))


def without(manifest, name):
    paths = dict(manifest['paths'])
    paths.pop(name, None)
    return {**manifest, 'paths': paths}


def manifest_facts(manifest):
    rows = manifest['paths']
    classes = {}
    for row in rows.values():
        classes[row['class']] = classes.get(row['class'], 0) + 1
    return {'paths': {'total': len(rows), 'added': sum(r['status'] == 'A' for r in rows.values()),
                      'modified': sum(r['status'] == 'M' for r in rows.values()), 'classes': dict(sorted(classes.items()))},
            'runtime_paths': sorted(n for n, r in rows.items() if r['class'] in ('runtime', 'requirements')),
            'dot_paths': sorted(n for n in rows if any(part.startswith('.') for part in PurePosixPath(n).parts)),
            'static': sorted(PurePosixPath(n).name for n, r in rows.items() if r['class'] == 'static')}


def admit_requirements(manifest, venv_check):
    """D1: a requirements change is admitted only when the act asserts the venv footprint before and after."""
    if 'rebuild/requirements.txt' in manifest['paths']:
        require(venv_check is True, 'requirements_change_needs_the_venv_footprint_check')
    return True


def merge_hooks(repo=None):
    """Repository-relative paths of every merge-time hook git would run in the shared tree."""
    repo = repo or ROOT
    paths = set()
    for name in MERGE_HOOKS:
        value = git(repo, 'rev-parse', '--git-path', 'hooks/' + name).decode().strip()
        path = Path(value) if Path(value).is_absolute() else repo / value
        require(not path.exists() and not path.is_symlink(), 'no_merge_time_hook_at_base')
        if path.is_relative_to(repo):
            paths.add(path.relative_to(repo).as_posix())
    return frozenset(paths)


def compute_manifest(repo, base, candidate, hooks):
    raw = git(repo, 'diff', '--raw', '--no-renames', '-z', '--no-abbrev', base, candidate)

    def blob(name):
        size = int(git(repo, 'cat-file', '-s', name).decode().strip())
        require(size <= BLOB_LIMIT, 'blob_within_guard_bound')
        return git(repo, 'cat-file', 'blob', name, limit=BLOB_LIMIT)
    return build_manifest(base, parse_raw_diff(raw), blob, hooks=hooks)


# ------------------------------------------------------------------------------------ the declaration (D4)
def declaration_relative(path, source=None):
    source = source or SOURCE
    path = Path(path)
    require(path.is_absolute() and str(path) == os.path.normpath(str(path)), 'absolute_declaration_path')
    require(path.is_relative_to(source), 'declaration_inside_candidate_worktree')
    relative = path.relative_to(source).as_posix()
    parts = PurePosixPath(relative).parts
    require(relative.startswith(DECLARATIONS) and len(parts) == 4 and relative.endswith('.md')
            and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*\.md', parts[-1]), 'ruled_act_declaration_directory')
    return relative


def declaration_provenance(path, candidate, *, source=None, runner_commit=None):
    """D4: tracked, unmodified and committed in the candidate; the committing commit is the candidate's ancestor."""
    source = source or SOURCE
    path = Path(path)
    relative = declaration_relative(path, source)
    require(not path.is_symlink() and path.resolve(strict=True) == path and path.is_file(), 'regular_declaration')
    raw = path.read_bytes()
    require(0 < len(raw) <= MAX_DECLARATION_BYTES, 'bounded_declaration')
    require(git_ok(source, 'ls-files', '--error-unmatch', '--', relative), 'declaration_tracked')
    require(git_ok(source, 'diff', '--quiet', 'HEAD', '--', relative), 'declaration_unmodified')
    commit = git(source, 'log', '-1', '--format=%H', '--', relative).decode().strip()
    require(full_sha(commit), 'declaration_committed')
    require(git(source, 'show', 'HEAD:' + relative) == raw and git(source, 'show', candidate + ':' + relative) == raw
            and git(source, 'show', commit + ':' + relative) == raw, 'declaration_bytes_committed_in_candidate')
    require(git_ok(source, 'merge-base', '--is-ancestor', commit, candidate), 'declaration_commit_in_candidate')
    if runner_commit is not None:
        require(runner_commit == commit, 'runner_declaration_commit')
    return {'path': str(path), 'relative': relative, 'sha256': sha(raw), 'bytes': len(raw), 'commit': commit,
            'committed_at': git(source, 'log', '-1', '--format=%cI', commit).decode().strip()}


def strict_gate(path, source=None):
    """The runner's own strict gate (scripts/lib/declaration.sh), run read-only in the candidate worktree."""
    source = source or SOURCE
    script = '. "$1/scripts/lib/declaration.sh" && declaration_gate "$2" strict "ruled mutation"'
    result = run(['bash', '-c', script, 'gate', str(source), str(path)], cwd=source, check=False)
    require(result.returncode == 0, 'strict_declaration_gate')
    return {'strict_gate': 'passed', 'output_sha256': sha(result.stdout)}


def _unique(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, 'duplicate_contract_key')
        value[key] = item
    return value


def contract_from(text):
    """The one fenced JSON block directly under the contract marker."""
    require(text.count(CONTRACT_MARKER) == 1, 'one_contract_marker')
    lines = text.split(CONTRACT_MARKER, 1)[1].split('\n')
    index = 1 if lines and lines[0].strip() == '' else 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    require(index < len(lines) and lines[index] == '```json', 'contract_block_opens_under_marker')
    body = []
    index += 1
    while index < len(lines) and lines[index] != '```':
        body.append(lines[index])
        index += 1
    require(index < len(lines), 'contract_block_closed')
    try:
        value = json.loads('\n'.join(body), object_pairs_hook=_unique)
    except ValueError:
        raise Refusal('contract_json') from None
    return validate_contract(value)


CONTRACT_KEYS = frozenset({'format', 'base', 'code_candidate', 'code_manifest_sha256', 'paths', 'runtime_paths',
                           'dot_paths', 'static', 'migrations', 'environment_delta', 'dependency_installs', 'venv',
                           'requirements_mismatch', 'foreign_venv_units', 'backup', 'operator'})


def validate_contract(value):
    require(type(value) is dict and set(value) == CONTRACT_KEYS and value['format'] == CONTRACT_FORMAT,
            'closed_contract')
    require(full_sha(value['base']) and full_sha(value['code_candidate']) and value['base'] != value['code_candidate']
            and digest64(value['code_manifest_sha256']), 'contract_revisions')
    paths = value['paths']
    require(type(paths) is dict and set(paths) == {'total', 'added', 'modified', 'classes'}
            and all(type(paths[k]) is int and paths[k] >= 0 for k in ('total', 'added', 'modified'))
            and type(paths['classes']) is dict, 'contract_path_counts')
    for key in ('runtime_paths', 'dot_paths', 'static', 'foreign_venv_units'):
        require(type(value[key]) is list and all(type(x) is str for x in value[key])
                and value[key] == sorted(set(value[key])), 'contract_sorted_unique_lists')
    require(all(UNIT_NAME.fullmatch(unit) for unit in value['foreign_venv_units']), 'contract_unit_names')
    require(value['migrations'] == 0 and value['dependency_installs'] == 0
            and value['environment_delta'] == ['QUILLMD_RELEASE_SHA'], 'contract_code_only_literals')
    venv = value['venv']
    require(type(venv) is dict and set(venv) == {'path', 'footprint_sha256', 'distributions', 'unrecorded_bytecode',
                                                 'policy'}
            and venv['path'] == str(VENV) and venv['policy'] == VENV_POLICY and digest64(venv['footprint_sha256'])
            and type(venv['distributions']) is int and type(venv['unrecorded_bytecode']) is int, 'contract_venv')
    mismatch = value['requirements_mismatch']
    require(type(mismatch) is dict and all(type(row) is dict and set(row) == {'required', 'installed'}
                                           and type(row['required']) is str
                                           and (row['installed'] is None or type(row['installed']) is str)
                                           for row in mismatch.values()), 'contract_requirements_mismatch')
    backup = value['backup']
    require(type(backup) is dict and set(backup) == {'report_sha256', 'run_id', 'restore_run_id'}
            and digest64(backup['report_sha256']) and type(backup['run_id']) is str
            and type(backup['restore_run_id']) is str, 'contract_backup')
    require(type(value['operator']) is dict and set(value['operator']) == set(OPERATOR_FILES)
            and all(digest64(x) for x in value['operator'].values()), 'contract_operator')
    return value


def build_contract(*, base, code_candidate, code_manifest, venv_summary, mismatch, foreign_units, backup, operator):
    facts = manifest_facts(code_manifest)
    return validate_contract({
        'format': CONTRACT_FORMAT, 'base': base, 'code_candidate': code_candidate,
        'code_manifest_sha256': manifest_digest(code_manifest), 'paths': facts['paths'],
        'runtime_paths': facts['runtime_paths'], 'dot_paths': facts['dot_paths'], 'static': facts['static'],
        'migrations': 0, 'environment_delta': ['QUILLMD_RELEASE_SHA'], 'dependency_installs': 0,
        'venv': {'path': str(VENV), 'footprint_sha256': venv_summary['footprint_sha256'],
                 'distributions': venv_summary['distributions'],
                 'unrecorded_bytecode': venv_summary['unrecorded_bytecode'], 'policy': VENV_POLICY},
        'requirements_mismatch': mismatch, 'foreign_venv_units': sorted(foreign_units),
        'backup': {'report_sha256': backup['report_sha256'], 'run_id': backup['run_id'],
                   'restore_run_id': backup['restore_run_id']},
        'operator': operator})


def contract_block(contract):
    return CONTRACT_MARKER + '\n```json\n' + json.dumps(contract, indent=2, sort_keys=True) + '\n```\n'


def code_manifest_for(full, declared, candidate_relative, code_diff_entries):
    """D4: the candidate is the declared code candidate plus exactly the declaration file, added."""
    require([(e[0], e[5]) for e in code_diff_entries] == [('A', candidate_relative)], 'declaration_is_the_only_delta')
    row = full['paths'].get(candidate_relative)
    require(row is not None and row['status'] == 'A', 'declaration_added_by_the_release')
    code = without(full, candidate_relative)
    require(manifest_digest(code) == declared['code_manifest_sha256'], 'code_manifest_matches_declaration')
    return code


def differing_keys(declared, expected):
    return sorted(key for key in set(declared) | set(expected) if declared.get(key) != expected.get(key))


# ------------------------------------------------------------------------- the host (all reads, no actions)
def operator_hashes(source=None):
    source = source or SOURCE
    return {name: sha((source / name).read_bytes()) for name in OPERATOR_FILES}


def uses_live_venv(execstart):
    return LIVE_VENV_MARKER in execstart


def venv_sharing_units(prior, services):
    units = []
    for unit in sorted(services):
        require(UNIT_NAME.fullmatch(unit), 'foreign_unit_name')
        if uses_live_venv(prior.command(['systemctl', 'show', unit, '-p', 'ExecStart']).decode()):
            units.append(unit)
    return units


def cgroup_cpu_usec(unit):
    require(UNIT_NAME.fullmatch(unit) is not None, 'foreign_unit_name')
    text = Path('/sys/fs/cgroup/system.slice', unit, 'cpu.stat').read_text()
    values = [line.split()[1] for line in text.splitlines() if line.startswith('usage_usec ')]
    require(len(values) == 1 and values[0].isdigit(), 'cgroup_cpu_usage')
    return int(values[0])


def foreign_idle(units, *, window=IDLE_WINDOW_SECONDS, fraction=IDLE_MAX_CPU_FRACTION, read=cgroup_cpu_usec,
                 clock=time.monotonic, sleep=time.sleep):
    """D3: CPU each unit spent over a short window, against a small fraction of one CPU."""
    start = {unit: read(unit) for unit in units}
    began = clock()
    sleep(window)
    elapsed = max(clock() - began, 1e-6) * 1e6
    rows = {}
    for unit in units:
        used = read(unit) - start[unit]
        rows[unit] = {'cpu_usec': used, 'window_usec': int(elapsed), 'idle': 0 <= used <= fraction * elapsed}
    return {'idle': all(row['idle'] for row in rows.values()), 'units': rows, 'max_cpu_fraction': fraction}


def locked_inodes(text):
    """(major, minor, inode) of every lock in /proc/locks; device numbers there are hexadecimal."""
    held = set()
    for token in text.split():
        match = re.fullmatch(r'([0-9a-f]+):([0-9a-f]+):([0-9]+)', token)
        if match:
            held.add((int(match[1], 16), int(match[2], 16), int(match[3])))
    return held


def locks_free(runtime=None, read=lambda: Path('/proc/locks').read_text()):
    runtime = runtime or APP / '.runtime'
    held = locked_inodes(read())
    rows = {}
    for relative in LOCK_FILES:
        path = runtime / relative
        if not path.exists() and not path.is_symlink():
            rows[relative] = 'absent'
            continue
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode), 'regular_lock_file')
        rows[relative] = 'held' if (os.major(info.st_dev), os.minor(info.st_dev), info.st_ino) in held else 'free'
    require('held' not in rows.values(), 'coordination_locks_free')
    return rows


def outside_scheduled_windows(moment):
    clock = moment.astimezone(dt.timezone.utc).time()
    require(not any(start <= clock <= end for start, end in QUIET_WINDOWS_UTC), 'outside_scheduled_backup_windows')
    return moment.isoformat()


def owned_units_active(host):
    states = {unit: host.state(unit) for unit in OWNED_UNITS}
    require(all(row.get('ActiveState') == 'active' and row.get('MainPID', '0') != '0' for row in states.values()),
            'owned_units_active')
    return {unit: {key: row.get(key) for key in ('ActiveState', 'SubState', 'MainPID')} for unit, row in states.items()}


def database_facts(snapshot):
    """Row counts per table (the declaration's baseline counts, clinical ones included) and pending work."""
    return {'tables': {name: row[0] for name, row in sorted(snapshot['tables'].items())},
            'pending': snapshot['pending'], 'migrations': len(snapshot['migrations'])}


def live_venv_users(proc=Path('/proc'), venv=None, exclude=()):
    """Processes whose interpreter path resolves into the live venv's bin directory, with their cgroup unit.

    Best effort, read-only: cmdline and cgroup are readable for every process; a relative interpreter path is
    resolved against the process's cwd when that is readable (same user), and skipped otherwise.
    """
    target = os.path.realpath(str((venv or VENV) / 'bin'))
    users = []
    for entry in sorted(proc.iterdir(), key=lambda p: p.name):
        if not entry.name.isdigit() or int(entry.name) in exclude:
            continue
        try:
            argv = (entry / 'cmdline').read_bytes().split(b'\0')
            cgroup = (entry / 'cgroup').read_text()
        except OSError:
            continue
        first = os.fsdecode(argv[0]) if argv and argv[0] else ''
        if '/' not in first:
            continue
        if not first.startswith('/'):
            try:
                first = os.path.join(os.readlink(entry / 'cwd'), first)
            except OSError:
                continue
        if os.path.realpath(os.path.dirname(first)) != target:
            continue
        match = re.search(r'^0::/system\.slice/([^/\n]+\.service)', cgroup, re.M)
        users.append({'pid': int(entry.name), 'unit': match[1] if match else None})
    return users


def no_undeclared_venv_users(foreign_units, users):
    allowed = set(OWNED_UNITS) | set(foreign_units) | set(OPERATION_UNITS)
    strays = [row for row in users if row['unit'] not in allowed]
    require(not strays, 'undeclared_process_on_the_live_venv')
    return {'processes': len(users), 'units': sorted({row['unit'] for row in users if row['unit']})}


# ------------------------------------------------------------------------------------------- the preflight
class Checks:
    """Every check runs and is reported; a refusal never hides the checks after it.

    A check returns a SMALL, non-sensitive detail. Large or protected values (the environment bytes, the venv
    object table, the database snapshot, the engine modules) are kept in ``held`` and never reported.
    """

    def __init__(self):
        self.rows = []
        self.held = {}

    def run(self, name, function, *args, **kwargs):
        try:
            detail = function(*args, **kwargs)
        except Exception as error:
            self.rows.append({'check': name, 'passed': False, 'reason': reason(error)})
            return None
        self.rows.append({'check': name, 'passed': True, 'detail': detail})
        return True if detail is None else detail

    def keep(self, name, function, *args, describe=lambda value: None, **kwargs):
        """Run a check whose value is held, not reported; ``describe`` makes its small public detail."""
        def held():
            value = function(*args, **kwargs)
            self.held[name] = value
            return describe(value)
        return self.held.get(name) if self.run(name, held) is not None else None

    def fail(self, name, why):
        self.rows.append({'check': name, 'passed': False, 'reason': why})

    @property
    def passed(self):
        return bool(self.rows) and all(row['passed'] for row in self.rows)


def reason(error):
    """A fixed label for this module's and the engine's refusals; the class name for anything else."""
    label = str(error)
    if type(error).__name__ in ('Refusal', 'HelperFailure') and re.fullmatch(r'[A-Za-z0-9_.:,/ -]{1,400}', label):
        return label
    name = type(error).__name__
    return name if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', name) else 'Exception'


def preflight(args, *, executing=False):
    """Every precondition, read-only. Returns (report, context); report['passed'] is the verdict."""
    checks = Checks()
    measured = {}
    context = {'measured': measured}
    footprint = checks.keep('operator_module_venv_footprint', ops_module, 'venv_footprint')
    backup = checks.keep('operator_module_backup', ops_module, 'rebuild_release_backup')
    engine = checks.keep('engine_pins', load_engine, describe=lambda _: {'pins': ENGINE_PINS})
    context['engine'] = engine
    if engine is None or footprint is None or backup is None:
        checks.fail('engine_bound', 'prerequisite_failed')
        return finish(args, checks, measured), context
    prior = engine.prior
    with bound(engine, args.base):
        checks.run('candidate_worktree', candidate_worktree, args.candidate)
        checks.run('shared_tree_at_base', shared_tree_at_base, args.base)
        checks.run('origin_main_is_candidate', origin_main_is, args.candidate)
        hooks = checks.keep('no_merge_time_hooks', merge_hooks, describe=sorted)
        venv = checks.keep('venv_footprint', footprint.snapshot, VENV, describe=footprint.summary)
        if venv is not None:
            context['venv'] = venv
            measured['venv'] = footprint.summary(venv)
        manifest = None
        if hooks is not None:
            manifest = checks.keep('whole_repository_manifest', compute_manifest, SOURCE, args.base, args.candidate,
                                   hooks, describe=lambda value: {'sha256': manifest_digest(value),
                                                                  **manifest_facts(value)['paths']})
        if manifest is not None:
            measured['manifest_sha256'] = manifest_digest(manifest)
            measured['manifest'] = manifest
            checks.run('requirements_bound_to_venv_check', admit_requirements, manifest,
                       venv is not None and digest64(venv.get('footprint_sha256')))
            if args.manifest_sha256 is not None:
                checks.run('manifest_equals_the_preflight', lambda: require(
                    measured['manifest_sha256'] == args.manifest_sha256, 'manifest_changed_since_preflight'))
        pins = checks.run('candidate_requirement_pins', lambda: footprint.requirement_pins(
            git(SOURCE, 'show', args.candidate + ':rebuild/requirements.txt').decode()))
        if venv is not None and pins is not None:
            measured['requirements_mismatch'] = footprint.requirements_mismatch(pins, venv['census']['distributions'])
        host = prior.legacy.Host(prior.managed_helper)
        checks.run('owned_units_active', owned_units_active, host)
        services = checks.run('foreign_services', prior.foreign_services)
        if services is not None:
            context['services'] = services
            foreign = checks.run('venv_sharing_foreign_units', venv_sharing_units, prior, services)
            if foreign is not None:
                measured['foreign_venv_units'] = list(foreign) if foreign is not True else []
                idle = checks.run('venv_sharing_units_idle', lambda: idle_verdict(foreign_idle(
                    measured['foreign_venv_units'])))
                measured['foreign_idle'] = idle
                checks.run('no_undeclared_live_venv_process', lambda: no_undeclared_venv_users(
                    measured['foreign_venv_units'], live_venv_users(exclude={os.getpid()})))
        checks.run('served_release_is_base', prior.await_health, args.base)
        checks.run('no_pending_environment_file', lambda: require(
            not PENDING_ENVIRONMENT.exists() and not PENDING_ENVIRONMENT.is_symlink(), 'pending_environment_file'))
        checks.run('coordination_locks_free', locks_free)
        checks.run('outside_scheduled_windows', outside_scheduled_windows, now_utc())
        report = checks.run('backup_report', backup.verify_report, args.backup_report, base=args.base,
                            now=now_utc(), max_age=BACKUP_MAX_AGE)
        if report is not None:
            measured['backup'] = report
        original = checks.keep('release_stamp_renders', release_stamp, engine, args.candidate,
                               describe=lambda _: {'release_stamp_renders': True, 'only_release_stamp_changes': True})
        if original is not None:
            context['environment'] = {'original': original}
            snapshot = checks.keep('database_baseline_read_only', engine.snapshot, original, describe=database_facts)
            if snapshot is not None:
                checks.run('no_pending_provider_work', engine.unchanged, snapshot, snapshot)
                measured['database'] = database_facts(snapshot)
        if manifest is not None:
            plan = {'candidate': args.candidate, 'static': manifest_facts(manifest)['static'],
                    'source_sha256': {name: row['sha256'] for name, row in manifest['paths'].items()}}
            with bound(engine, args.base, plan['static']):
                checks.keep('engine_source_plan', lambda: prior.source_plan(plan, bind_guard(prior.source_guard())),
                            describe=lambda prepared: {'base_files_proven': len(prepared['before']),
                                                       'candidate_files_hashed': len(prepared['after'])})
        citation_line = checks.run('citation', citation, prior, args.candidate)
        if citation_line is not None:
            measured['citation'] = citation_line
        operator = checks.run('operator_hashes', operator_hashes)
        if operator is not None:
            measured['operator'] = operator
        declared = declaration_checks(args, checks, measured, executing=executing)
        if declared is not None:
            context['declaration'] = declared
    return finish(args, checks, measured), context


def idle_verdict(value):
    require(value['idle'], 'venv_sharing_units_not_idle')
    return value


def declaration_checks(args, checks, measured, *, executing):
    """D4 and the contract. Before the declaration exists these fail, and the contract to embed is printed."""
    provenance = checks.run('declaration_provenance', declaration_provenance, args.declaration, args.candidate,
                            runner_commit=os.environ.get('RULED_MUTATION_DECL_COMMIT') if executing else None)
    checks.run('strict_declaration_gate', strict_gate, args.declaration)
    if provenance is not None:
        measured['declaration'] = provenance
    needed = ('manifest', 'venv', 'requirements_mismatch', 'foreign_venv_units', 'backup', 'operator')
    if not all(measured.get(key) is not None for key in needed):
        checks.fail('declaration_contract', 'prerequisite_failed')
        return None
    manifest = measured['manifest']
    common = dict(base=args.base, venv_summary=measured['venv'], mismatch=measured['requirements_mismatch'],
                  foreign_units=measured['foreign_venv_units'], backup=measured['backup'],
                  operator=measured['operator'])
    if provenance is None:
        # Before the declaration PR the candidate IS the code candidate: this is the block to embed.
        measured['contract_to_embed'] = build_contract(code_candidate=args.candidate, code_manifest=manifest,
                                                       **common)
        checks.fail('declaration_contract', 'declaration_not_in_candidate')
        return None
    declared = checks.run('declaration_contract_parses', lambda: contract_from(
        Path(args.declaration).read_bytes().decode()))
    if declared is None:
        return None

    def bind():
        require(declared['base'] == args.base, 'contract_base')
        require(git_ok(SOURCE, 'merge-base', '--is-ancestor', declared['code_candidate'], args.candidate),
                'code_candidate_is_an_ancestor')
        entries = parse_raw_diff(git(SOURCE, 'diff', '--raw', '--no-renames', '-z', '--no-abbrev',
                                     declared['code_candidate'], args.candidate))
        code = code_manifest_for(manifest, declared, provenance['relative'], entries)
        expected = build_contract(code_candidate=declared['code_candidate'], code_manifest=code, **common)
        require(expected == declared, 'contract_differs:' + ','.join(differing_keys(declared, expected)))
        return {'code_candidate': declared['code_candidate'], 'code_manifest_sha256': declared['code_manifest_sha256'],
                'contract_sha256': sha(canonical(declared))}
    if checks.run('declaration_contract_matches_measurement', bind) is None:
        return None
    return {'provenance': provenance, 'contract': declared}


def candidate_worktree(candidate):
    require(full_sha(candidate), 'full_candidate_sha')
    top = Path(git(SOURCE, 'rev-parse', '--show-toplevel').decode().strip())
    require(top == SOURCE and SOURCE != ROOT and SOURCE.resolve() == SOURCE, 'installer_runs_from_a_candidate_worktree')
    require(git(SOURCE, 'rev-parse', 'HEAD').decode().strip() == candidate, 'candidate_worktree_head')
    require(not git(SOURCE, 'status', '--porcelain', '--untracked-files=no').strip(), 'candidate_worktree_clean')
    return {'worktree': str(SOURCE), 'head': candidate}


def shared_tree_at_base(base):
    require(full_sha(base), 'full_base_sha')
    require(git(ROOT, 'branch', '--show-current').strip() == b'main'
            and git(ROOT, 'rev-parse', 'HEAD').decode().strip() == base
            and not git(ROOT, 'status', '--porcelain', '--untracked-files=no').strip(), 'clean_shared_main_at_base')
    return {'head': base, 'branch': 'main'}


def origin_main_is(candidate):
    require(git(ROOT, 'rev-parse', 'origin/main').decode().strip() == candidate, 'origin_main_tracking_ref')
    remote = git(SOURCE, 'ls-remote', 'origin', 'refs/heads/main', timeout=60).decode().split()
    require(remote[:1] == [candidate], 'remote_main_is_candidate')
    return {'origin_main': candidate}


def release_stamp(engine, candidate):
    """The engine's renderer on the real file, never printed: only QUILLMD_RELEASE_SHA may change.

    The bytes are returned to the caller's held values and never enter a check detail or a report.
    """
    original = engine.prior.backup_restore.read_private(APP / '.env', 65536)
    engine.render_environment(original, candidate, {})
    return original


def citation(prior, candidate):
    output = prior.command(['bash', str(SOURCE / 'scripts/check-citation.sh'), candidate], cwd=SOURCE, timeout=120)
    lines = [line for line in output.decode(errors='replace').splitlines() if line.startswith('**Citation')]
    require(lines, 'citation_line')
    return {'citation': lines[-1], 'output_sha256': sha(output)}


def finish(args, checks, measured):
    public = {key: value for key, value in measured.items() if key != 'manifest'}
    report = {'format': PREFLIGHT_FORMAT, 'base': args.base, 'candidate': args.candidate,
              'declaration': str(args.declaration), 'checked_at': now_utc().isoformat(),
              'passed': checks.passed, 'checks': checks.rows, 'measured': public}
    if 'manifest' in measured:
        report['manifest'] = measured['manifest']
    contract = measured.get('contract_to_embed')
    if contract is not None:
        report['contract_block'] = contract_block(contract)
    return report


# ------------------------------------------------------------------------------------------------- the act
def runner_declaration(args):
    """The child of run-ruled-mutation.sh: the runner's exports name this exact declaration."""
    declared = os.environ.get('RULED_MUTATION_DECLARATION', '')
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declared == str(args.declaration) and full_sha(commit), 'ruled_mutation_runner_required')
    return commit


def evidence_directory(path):
    path = Path(path)
    require(path.is_absolute() and str(path) == os.path.normpath(str(path)) and not path.exists()
            and not path.is_symlink(), 'new_evidence_directory')
    parent = path.parent.lstat()
    require(path.parent.resolve() == path.parent and stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid()
            and stat.S_IMODE(parent.st_mode) == 0o700, 'private_evidence_parent')
    return path


def diagnostics(engine, error):
    value = engine.failure_diagnostics(error)
    value['label'] = reason(error)
    ours, frame = [], error.__traceback__
    while frame:
        name = Path(frame.tb_frame.f_code.co_filename).name
        if name in ('install_rebuild_release.py', 'venv_footprint.py'):
            ours.append({'module': name, 'line': frame.tb_lineno})
        frame = frame.tb_next
    value['installer_locations'] = ours
    return value


def act(engine, plan, context, *, footprint, idle=foreign_idle, snapshot_venv=None):
    """The act, in the engine's own order (activate_core_workflow_repair.py:185-319), D1/D3 checks inserted.

    Returns (result, postconditions_passed). Raises Refusal on any failure, after the engine's failure handling:
    a started resume is drained first; automatic recovery only when stopped and publication was not attempted.
    """
    prior = engine.prior
    legacy = prior.legacy
    snapshot_venv = snapshot_venv or footprint.snapshot
    require(Path.cwd().resolve() == prior.ROOT, 'permanent_native_actuation_directory')
    original = prior.backup_restore.read_private(prior.APP / '.env', 65536)
    require(original == context['environment']['original'], 'environment_unchanged_since_preflight')
    active = engine.render_environment(original, plan['candidate'], plan['environment'])
    guard = bind_guard(prior.source_guard())
    prepared = prior.source_plan(plan, guard)
    prior.command(['bash', str(SOURCE / 'scripts/check-citation.sh'), plan['candidate']], cwd=SOURCE, timeout=120)
    out = Path(plan['evidence_directory'])
    out.mkdir(mode=0o700)
    prior.write_new(out / 'plan.json', dict(plan, environment_before_sha256=prior.sha(original)))
    prior.write_new(out / 'preflight.json', context['report'])
    cipher = prior.backup_restore.key_at(legacy.KEY)
    prior.write_new(out / 'environment-before.fernet', cipher.encrypt(original))
    prior.write_new(out / 'environment-after.fernet', cipher.encrypt(active))
    require(cipher.decrypt((out / 'environment-before.fernet').read_bytes()) == original,
            'rollback_environment_decryption')
    units = plan['foreign_venv_units']
    venv_before = context['venv']
    stopped = resumed = resume_started = publication_attempted = False
    stage = 'static_baseline'
    host = legacy.Host(prior.managed_helper)
    with ExitStack() as coordination:
        try:
            note(stage)
            primitives = legacy.static_primitives()
            primitives.static_delta = prior.static_delta
            if plan['static']:
                static_stage, static_before, staged = prior.stage_static(plan, out, primitives)
                rollback = engine.verify_static_rollback(out / 'static-before.tar', static_before)
            else:
                static_stage, staged = None, {}
                static_before = primitives.static_inventory(prior.APP / 'staticfiles')
                rollback = {'static_noop': True, 'files': sum(r['kind'] == 'file' for r in static_before.values())}
            prior.write_new(out / 'rollback-readback.json', dict(environment_decryption_matches=True,
                            source_revision=plan['base'], static=rollback, live_restore_actions=0))
            prior.activation_exclusion.bind_runtime(prior.APP / '.runtime')
            stage = 'coordination_locks'; note(stage)
            coordination.enter_context(legacy.operation_locks())
            coordination.enter_context(prior.activation_exclusion.hold(
                'rebuild-release:' + plan['candidate'][:12], timeout=30))
            baseline = {'static': static_before}
            stage = 'baseline_configuration'; baseline['configuration'] = host.configuration()
            stage = 'baseline_foreign_services'; baseline['services'] = prior.foreign_services()
            require(baseline['services'] == context['services'], 'foreign_services_unchanged_since_preflight')
            stage = 'baseline_foreign_idle'; note(stage)
            baseline['foreign_idle'] = idle(units)
            require(baseline['foreign_idle']['idle'], 'venv_sharing_units_idle_before_stop')
            stage = 'baseline_database'; note(stage); baseline['database'] = engine.snapshot(original)
            stage = 'baseline_clinical_files'
            baseline['files'] = prior.private_storage.inventory(Path('/var/lib/quillmd/files'))
            stage = 'baseline_pending_check'; engine.unchanged(baseline['database'], baseline['database'])
            stage = 'baseline_venv'; note(stage)
            footprint.require_exact(venv_before, snapshot_venv(prior.APP / '.venv'), 'venv_unchanged_since_preflight')
            require(venv_before['footprint_sha256'] == plan['venv_footprint_sha256'], 'venv_is_the_declared_venv')
            baseline['venv'] = footprint.summary(venv_before)
            stage = 'retain_baseline'
            prior.write_new(out / 'baseline.json', baseline)
            prior.write_new(out / 'venv-before.json', venv_before)
            stage = 'revalidate_before_stop'; note(stage)
            require(prior.source_plan(plan, guard) == prepared, 'source_cut_unchanged_before_stop')
            require((prior.APP / '.env').read_bytes() == original, 'environment_unchanged_before_stop')
            require(primitives.static_inventory(prior.APP / 'staticfiles') == static_before,
                    'static_unchanged_before_stop')
            require(all(host.state(unit)['ActiveState'] == 'active' and host.state(unit)['MainPID'] != '0'
                        for unit in prior.UNITS), 'owned_units_active_before_stop')
            stage = 'stop_owned_services'; note(stage); stopped = True
            for unit in prior.UNITS:
                host.service('stop', unit)
            stage = 'verify_owned_services_stopped'
            require(all(host.state(unit)['ActiveState'] == 'inactive' and host.state(unit)['MainPID'] == '0'
                        for unit in prior.UNITS), 'owned_units_drained')
            stage = 'database_after_stop'; after_stop = engine.snapshot(original)
            stage = 'retain_database_after_stop'
            prior.write_new(out / 'database-after-stop.json', after_stop)
            stage = 'database_after_stop'; engine.unchanged(baseline['database'], after_stop, health_may_tick=True)
            stage = 'venv_after_stop'; note(stage)
            footprint.require_exact(venv_before, snapshot_venv(prior.APP / '.venv'), 'venv_unchanged_before_publication')
            stage = 'foreign_services_after_stop'
            require(prior.foreign_services() == baseline['services'], 'foreign_services_preserved_before_publication')
            stage = 'source_publication'; note(stage); publication_attempted = True
            prior.publish_source(plan, guard, prepared)
            stage = 'static_publication'
            if plan['static']:
                static_after = primitives.install_static(prior.APP / 'staticfiles', static_stage, static_before, staged)
            else:
                static_after = primitives.static_inventory(prior.APP / 'staticfiles')
                require(static_after == static_before, 'static_noop')
            stage = 'environment_publication'; note(stage)
            require((prior.APP / '.env').read_bytes() == original, 'environment_concurrency')
            temporary = prior.APP / PENDING_ENVIRONMENT.name
            prior.write_new(temporary, active); temporary.replace(prior.APP / '.env')
            stage = 'database_before_resume'; before_resume = engine.snapshot(active)
            stage = 'retain_database_before_resume'
            prior.write_new(out / 'database-before-resume.json', before_resume)
            stage = 'database_before_resume'; engine.unchanged(after_stop, before_resume)
            stage = 'clinical_files_before_resume'
            require(prior.private_storage.inventory(Path('/var/lib/quillmd/files')) == baseline['files'],
                    'all_clinical_files_preserved')
            stage = 'configuration_before_resume'
            require(host.configuration() == baseline['configuration'], 'configuration_preserved')
            stage = 'foreign_services_before_resume'
            require(prior.foreign_services() == baseline['services'], 'foreign_services_preserved')
            stage = 'retain_preservation'
            evidence_sha256 = {name: prior.sha((out / name).read_bytes()) for name in
                               ('baseline.json', 'database-after-stop.json', 'database-before-resume.json',
                                'venv-before.json')}
            prior.write_new(out / 'pre-resume-preservation.json', dict(after_stop_database_exact_before_resume=True,
                            baseline_health_tick_only=True, files_preserved=True, static_inventory=static_after,
                            evidence_sha256=evidence_sha256, provider_calls=0, migrations_executed=0,
                            venv_exact_before_publication=True, environment_delta=['QUILLMD_RELEASE_SHA'],
                            static_sources=list(plan['static'])))
            stage = 'resume_owned_services'; note(stage); resume_started = True
            for unit in (prior.UNITS[2], *prior.UNITS[:2]):
                host.service('start', unit)
            stage = 'normal_https_health'; health = prior.await_health(plan['candidate'])
            stage = 'verify_owned_services_resumed'
            require(all(host.state(unit)['ActiveState'] == 'active' for unit in prior.UNITS), 'owned_units_active')
            resumed = True
            stage = 'configuration_after_resume'
            require(host.configuration() == baseline['configuration'], 'configuration_preserved_after_resume')
            stage = 'foreign_services_after_resume'
            require(prior.foreign_services() == baseline['services'], 'foreign_services_preserved_after_resume')
            # Post-conditions the act cannot cause and draining cannot fix are measured and reported, not drained
            # for: the installation is complete, and a failed post-condition makes the act exit 2 for judgement.
            stage = 'foreign_idle_after_resume'; note(stage)
            postconditions = {}
            try:
                after_idle = idle(units)
                postconditions['venv_sharing_units_idle_after_resume'] = after_idle['idle']
            except Exception as error:
                after_idle = {'error': reason(error)}
                postconditions['venv_sharing_units_idle_after_resume'] = False
            stage = 'venv_after_resume'; note(stage)
            venv_after = None
            try:
                venv_after = snapshot_venv(prior.APP / '.venv')
                footprint.require_exact(venv_before, venv_after, 'venv_changed_during_the_act')
                postconditions['venv_exact_after_resume'] = True
                venv_change = None
            except Exception as error:
                postconditions['venv_exact_after_resume'] = False
                venv_change = {'label': reason(error)}
                if type(venv_after) is dict and type(venv_after.get('files')) is dict:
                    venv_change['difference'] = footprint.difference(venv_before['files'], venv_after['files'])
            passed = all(postconditions.values())
            result = dict(format=FORMAT, installed_revision=plan['candidate'], base=plan['base'], complete=True,
                          health=health, migrations_executed=0, provider_calls=0, clinician_decisions_created=0,
                          dependency_installs=0, evidence_sha256=evidence_sha256, plan_sha256=plan['plan_sha256'],
                          declaration_commit=plan['declaration']['commit'],
                          declaration_sha256=plan['declaration']['sha256'],
                          manifest_sha256=plan['manifest_sha256'], environment_delta=['QUILLMD_RELEASE_SHA'],
                          static_sources=list(plan['static']), venv_footprint_sha256=venv_before['footprint_sha256'],
                          postconditions=postconditions, all_postconditions_passed=passed,
                          foreign_idle_after_resume=after_idle, venv_change=venv_change,
                          strict_preservation_ends_before_resume=True)
            stage = 'retain_completion'; note(stage)
            prior.write_new(out / 'installation-complete.json', result)
            return result, passed
        except BaseException as error:
            drain = engine.stop_failed_resume(host) if resume_started else None
            prior.write_new(out / 'failure.json', dict(format=FORMAT, complete=False, stage=stage,
                            **diagnostics(engine, error), stopped=stopped, resumed=resumed,
                            resume_started=resume_started, publication_attempted=publication_attempted,
                            failed_resume_drain=drain, provider_calls=0, automatic_retry=False))
            if drain is not None:
                prior.write_new(out / 'failed-resume-drain.json', drain)
                require(drain['all_units_inactive'], 'failed_resume_drain_incomplete')
            if stopped and not publication_attempted and not resume_started:
                try:
                    engine.verify_original_before_resume(original, guard, prepared)
                except BaseException as recovery_error:
                    prior.write_new(out / 'original-recovery-refused.json', diagnostics(engine, recovery_error))
                    raise Refusal('original_recovery_refused_inspect_retained_evidence') from None
                for unit in (prior.UNITS[2], *prior.UNITS[:2]):
                    host.service('start', unit)
                prior.write_new(out / 'original-release-resumed.json', {'release': plan['base']})
            raise Refusal('installation_failed_inspect_retained_evidence') from None


def build_plan(args, context):
    measured = context['measured']
    declaration = context['declaration']
    manifest = measured['manifest']
    plan = {'format': FORMAT, 'base': args.base, 'candidate': args.candidate,
            'source_sha256': {name: row['sha256'] for name, row in manifest['paths'].items()},
            'source_worktree': str(SOURCE), 'evidence_directory': str(args.evidence_directory),
            'environment': {}, 'static': list(declaration['contract']['static']),
            'manifest_sha256': measured['manifest_sha256'],
            'code_manifest_sha256': declaration['contract']['code_manifest_sha256'],
            'declaration': declaration['provenance'], 'backup': measured['backup'],
            'venv_footprint_sha256': declaration['contract']['venv']['footprint_sha256'],
            'foreign_venv_units': list(declaration['contract']['foreign_venv_units'])}
    plan['plan_sha256'] = sha(canonical(plan))
    return plan


# ------------------------------------------------------------------------------------------------- the CLI
def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--base', required=True)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--declaration', required=True, type=Path)
    parser.add_argument('--backup-report', required=True, type=Path)
    parser.add_argument('--result', required=True, type=Path)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--evidence-directory', type=Path)
    parser.add_argument('--manifest-sha256')
    args = parser.parse_args(argv)
    for value in (args.base, args.candidate):
        if not full_sha(value):
            parser.error('--base and --candidate must be full 40-character lowercase commit ids')
    if args.base == args.candidate:
        parser.error('--candidate must differ from --base')
    for name in ('declaration', 'backup_report', 'result'):
        path = getattr(args, name)
        if not path.is_absolute() or str(path) != os.path.normpath(str(path)):
            parser.error('--' + name.replace('_', '-') + ' must be an absolute, normalized path')
    if args.manifest_sha256 is not None and not digest64(args.manifest_sha256):
        parser.error('--manifest-sha256 must be 64 lowercase hex characters')
    if args.execute:
        if args.evidence_directory is None or args.manifest_sha256 is None:
            parser.error('--execute requires --evidence-directory and --manifest-sha256 (from the preflight)')
        if not args.evidence_directory.is_absolute():
            parser.error('--evidence-directory must be absolute')
    elif args.evidence_directory is not None:
        parser.error('--evidence-directory is only meaningful with --execute')
    return args


def write_result(path, value):
    path = Path(path)
    parent = path.parent.lstat()
    require(path.parent.resolve() == path.parent and stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.getuid()
            and stat.S_IMODE(parent.st_mode) == 0o700, 'private_result_directory')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(json.dumps(value, indent=1, sort_keys=True, default=str).encode() + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def summary(report):
    keep = ('format', 'base', 'candidate', 'declaration', 'checked_at', 'passed', 'checks')
    value = {key: report[key] for key in keep}
    measured = report.get('measured', {})
    value['measured'] = {key: measured[key] for key in ('manifest_sha256', 'venv', 'requirements_mismatch',
                                                        'foreign_venv_units', 'backup', 'declaration', 'database')
                         if key in measured}
    if 'manifest' in report:
        value['measured']['manifest_facts'] = manifest_facts(report['manifest'])
    return value


def main(argv=None):
    args = arguments(argv)
    os.umask(0o077)
    sys.dont_write_bytecode = True
    # Read-only git everywhere: no index refresh, no optional lock in the shared tree or the worktree.
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    if args.execute:
        require(Path.cwd().resolve() == SOURCE, 'run_from_the_candidate_worktree_under_the_runner')
        runner_declaration(args)
        evidence_directory(args.evidence_directory)
    report, context = preflight(args, executing=args.execute)
    if not args.execute:
        write_result(args.result, report)
        print(json.dumps(summary(report), indent=1, sort_keys=True, default=str))
        if 'contract_block' in report:
            print(report['contract_block'])
        return 0 if report['passed'] else 1
    if not report['passed']:
        write_result(args.result, report)
        print(json.dumps(summary(report), indent=1, sort_keys=True, default=str))
        print('REFUSED before any action: the preflight did not pass.', file=sys.stderr)
        return 1
    require(context['measured']['manifest_sha256'] == args.manifest_sha256, 'manifest_changed_since_preflight')
    context['report'] = report
    plan = build_plan(args, context)
    engine = context['engine']
    os.chdir(ROOT)
    with bound(engine, args.base, plan['static']):
        try:
            result, passed = act(engine, plan, context, footprint=ops_module('venv_footprint'))
        except BaseException as error:
            write_result(args.result, {'format': FORMAT, 'complete': False, 'label': reason(error),
                                       'evidence_directory': str(args.evidence_directory)})
            raise
    write_result(args.result, {'format': FORMAT, 'complete': True, 'all_postconditions_passed': passed,
                               'evidence_directory': str(args.evidence_directory),
                               'receipt_sha256': sha((Path(plan['evidence_directory']) /
                                                      'installation-complete.json').read_bytes())})
    print(json.dumps(result, indent=1, sort_keys=True, default=str))
    return 0 if passed else 2


if __name__ == '__main__':
    try:
        code = main()
    except SystemExit:
        raise
    except BaseException as error:
        # Only a fixed label leaves: another module's exception text could carry configuration or row data.
        print(json.dumps({'complete': False, 'refused': reason(error), 'automatic_retry': False}), file=sys.stderr)
        code = 1
    sys.exit(code)
