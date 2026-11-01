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

WHAT THE INSTALLER ADDS TO THE ENGINE'S SHAPE (the 2026-11-01 refutations: 22 findings, then 14 more)
  * Path guards: a dot-named component only where the base already tracks that path, or a new dot-named file that
    the declaration's contract names exactly (new_dot_paths: never a .git or .env* name, never a path the delta
    does not add); no path whose existing prefix in the shared tree is not a real directory, no added path that
    already exists in any form (ignored files such as rebuild/.env included); no merge-time or maintenance hook
    (pre-auto-gc included); no gate instrument and no .gitattributes in the delta.
  * The citation and the strict declaration gate run from the base's tracked copies in the shared tree, proven
    byte-equal to their blobs at BASE; origin/main is read as refs/remotes/origin/main and refs/heads/main exactly.
  * Git's own state (lock files, an unfinished merge, cherry-pick, revert, rebase or bisect, assume-unchanged or
    skip-worktree entries, replace refs) refuses, in the shared tree and in the candidate worktree, in the
    preflight and again after the stop. A rebase is unfinished only while rebase-merge/ or rebase-apply/ exists: a
    lone REBASE_HEAD, a finished rebase's leftover, is recorded and never refused or removed. No git process reads
    a replace object. Nothing is imported from the candidate worktree before it is proven, nothing untracked may
    sit in rebuild/ops, and no bytecode is read from the source tree.
  * Configuration, clinical files, the venv, foreign services, git's state, rebuild/.env and the static tree are
    compared again AFTER the stop and BEFORE publication. Publication begins only when git has moved HEAD or the
    working tree: a refusal before that, a merge git refused included, restores the original release once every
    child of the act is reaped and the original is MEASURED intact (the engine's verify_original_before_resume and
    the same shared-tree measurement as before the merge, git's own state included).
  * The failure path is exception-proof. Every unit gets its drain or restore attempt whatever happens to an
    evidence write or to releasing the locks; a restore counts only when every unit is active and health reports
    BASE. The act's git processes run with hooks, automatic maintenance and replace objects off.
  * After a completed, healthy install nothing drains: a later observation (a foreign restart, a failed
    configuration read, a signal) is reported for judgement and the act exits 2, as it does when the result file
    cannot be written. --result must be a new file in a private directory before anything runs.

SIGNALS ARE BLOCKED, NEVER HANDLED (the second refutation: an asynchronous handler kept racing what it protected)
  SIGTERM, SIGINT and SIGHUP are blocked with pthread_sigmask from the act's first statement until the process
  exits. No handler runs: this module installs none, managed_helper.run_helper's per-call SIGTERM handler cannot
  fire, KeyboardInterrupt cannot be raised. So no signal interrupts a stage, a helper call, a subprocess start or
  the failure path. checkpoint() takes pending signals (sigtimedwait, zero timeout) between stages and records each
  with its sender: before publication one takes the automatic recovery path; from publication on it is recorded,
  the act runs to completion, and the exit is 2 for judgement. Children inherit the blocked mask, so a git or pip
  child stops only on SIGKILL, and SIGKILL is the only thing that can still cut the act: the runner's ceiling must
  exceed the act's worst duration (docs/runbooks/rebuild-release-install-20261031.md, step 7).
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
import signal
import stat
import subprocess
import sys
import threading
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
#: Hooks git can run during `merge --ff-only`: while it updates the index, the ref and the working tree, and in
#: the automatic maintenance it starts afterwards (`gc --auto` runs pre-auto-gc). None may exist at base, and the
#: candidate may not add one: it would be checked out by the merge and then run by it.
MERGE_HOOKS = ('post-merge', 'reference-transaction', 'post-index-change', 'post-checkout', 'pre-merge-commit',
               'post-rewrite', 'pre-auto-gc')
#: Every git process of the act also runs with hooks, automatic maintenance and replace objects switched off.
ACT_GIT_CONFIG = (('core.hooksPath', '/dev/null'), ('maintenance.auto', 'false'), ('gc.auto', '0'),
                  ('core.useReplaceRefs', 'false'))
#: Environment that would redirect or reconfigure git; refused rather than inherited.
GIT_ENVIRONMENT_REFUSED = ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_OBJECT_DIRECTORY',
                           'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_COMMON_DIR', 'GIT_NAMESPACE', 'GIT_CONFIG',
                           'GIT_CONFIG_PARAMETERS', 'GIT_CONFIG_COUNT', 'GIT_REPLACE_REF_BASE')
#: No git process reads a replace object: a `git replace <candidate> <other>` in the shared object store would make
#: every content check, and the act's own merge, read substituted objects behind the certified sha. main() exports
#: it, so every child that inherits the environment (the engine's git, the citation, the strict gate) has it too;
#: this module's own git() also passes --no-replace-objects, and git_state refuses any refs/replace entry.
NO_REPLACE_OBJECTS = ('GIT_NO_REPLACE_OBJECTS', '1')
#: The gates the act relies on: the citation, the runner and its strict declaration gate. A delta that changes one
#: refuses (the legacy installer's dependency_byte_identity rule for the same files), and the two the installer
#: runs itself are run from the base's tracked copies in the shared tree, never from the candidate.
GATE_INSTRUMENTS = ('scripts/check-citation.sh', 'scripts/lib/runs-api.sh', 'scripts/lib/declaration.sh',
                    'scripts/run-ruled-mutation.sh', 'scripts/lib/run-watched.sh',
                    'scripts/lib/container-revision.sh')
TRUSTED_GATE_SCRIPTS = ('scripts/check-citation.sh', 'scripts/lib/runs-api.sh', 'scripts/lib/declaration.sh')
#: Git's own lock files and unfinished operations in the shared repository (`rev-parse --git-path` names). A rebase
#: is unfinished only while rebase-merge/ or rebase-apply/ exists, which is how git itself decides
#: (wt_status_check_rebase).
GIT_LOCKS = ('index.lock', 'HEAD.lock', 'ORIG_HEAD.lock', 'config.lock', 'packed-refs.lock', 'shallow.lock')
GIT_OPERATIONS = ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply', 'sequencer',
                  'BISECT_LOG', 'BISECT_START')
#: Left behind by a FINISHED operation: `rebase --continue`, `--skip` and `--quit` all leave REBASE_HEAD (git 2.43),
#: and it does not affect `merge --ff-only`. The live repository has had one since 2026-08-10. Recorded as observed,
#: never refused, never removed.
GIT_LEFTOVERS = ('REBASE_HEAD',)
#: A bare interpreter name: Python then finds itself, and its venv, through the process's own PATH.
INTERPRETER_NAME = re.compile(r'python[0-9.]*')
#: Blocked for the whole act (block_signals) and taken only at checkpoints; no handler of any module ever runs.
SIGNALS = ('SIGTERM', 'SIGINT', 'SIGHUP')
SIGNAL_NUMBERS = tuple(getattr(signal, name) for name in SIGNALS)
#: How long the failure path waits for a child of the act (a merge an exception left behind) to exit before it
#: measures anything; a child still running after that counts as a publication that may still move HEAD.
REAP_SECONDS = 120
#: Bytecode is never read from the source tree: a __pycache__ file planted with a pinned source's mtime and size
#: would otherwise run instead of the bytes that were hashed (-B only stops writing it). See ops_module.
BYTECODE_PREFIX = os.devnull
#: Measured after a completed, healthy resume and reported for judgement (exit 2), never drained for.
POSTCONDITIONS = ('configuration_preserved_after_resume', 'foreign_services_preserved_after_resume',
                  'venv_sharing_units_idle_after_resume', 'venv_exact_after_resume')
REFUSED_PARTS = frozenset({'node_modules', '.venv', 'uploads', 'backups', '.git'})
#: A declaration names its new dot paths exactly; a pattern character would read as a glob, so it refuses.
PATTERN_CHARACTERS = frozenset('*?[]{}')
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


class Interrupted(BaseException):
    """A routed signal taken at a checkpoint before publication (never raised by a handler: none runs), raised so
    that the act's own failure path drains or restores.

    A BaseException, like KeyboardInterrupt, so that no `except Exception` on the way swallows it.
    """

    def __init__(self, name):
        super().__init__('interrupted_by_' + name)
        self.signal_name = name


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
    """A stage line on stderr (the runner's transcript). A closed stderr never fails the act."""
    try:
        print(STAGE_LOG, now_utc().strftime('%Y-%m-%dT%H:%M:%SZ'), 'stage=' + stage, file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass


def emit(record):
    """One JSON line of fixed labels on stderr: the record that survives when an evidence write does not."""
    try:
        print(STAGE_LOG, json.dumps(record, sort_keys=True, default=str), file=sys.stderr, flush=True)
    except (OSError, ValueError):
        pass


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
    return run(['git', '--no-optional-locks', '--no-replace-objects', '-C', str(repo), *arguments], timeout=timeout,
               limit=limit).stdout


def git_ok(repo, *arguments):
    return run(['git', '--no-optional-locks', '--no-replace-objects', '-C', str(repo), *arguments],
               check=False).returncode == 0


def ops_module(name, source=None):
    """An unpinned operator module of THIS release, imported from the tree this file runs from.

    The import, and every module it imports, compiles the source file itself: sys.pycache_prefix points at a path
    no bytecode can be read from for its duration, so a planted rebuild/ops/__pycache__ entry never runs in place of
    the bytes that were hashed. main() keeps it there for the whole process (later imports inside the engine).
    """
    source = source or SOURCE
    rebuild = str(source / 'rebuild')
    if rebuild not in sys.path:
        sys.path.insert(0, rebuild)
    previous, sys.pycache_prefix = sys.pycache_prefix, BYTECODE_PREFIX
    try:
        module = importlib.import_module('ops.' + name)
    finally:
        sys.pycache_prefix = previous
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


def canonical_repository_path(name):
    """A relative, normalized, printable repository path of at most 400 bytes (manifest rows and declared paths)."""
    if type(name) is not str or not name.isprintable():
        return False
    path = PurePosixPath(name)
    return (0 < len(name.encode()) <= 400 and name == str(path) and not path.is_absolute()
            and not set(path.parts) & {'', '.', '..'} and '\\' not in name)


def classify(name, status, *, hooks=frozenset()):
    """runtime | requirements | static | support | passenger, or a refusal. Exact membership is checked elsewhere."""
    require(canonical_repository_path(name), 'canonical_manifest_path')
    path = PurePosixPath(name)
    require(status in ('A', 'M'), 'add_or_modify_only')
    require(name not in hooks, 'merge_time_git_hook')
    require(name not in GATE_INSTRUMENTS, 'gate_instrument_in_delta')
    # Attributes can make the merge's checkout run filter commands or rewrite bytes.
    require(path.name != '.gitattributes', 'git_attributes_in_delta')
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


def refused_dot_name(part):
    """git's own directory and the live environment files (.env, rebuild/.env): refused even when declared."""
    lowered = part.lower()
    return lowered == '.git' or lowered.startswith('.env')


def new_dot_path_list(values):
    """The declaration's new_dot_paths: the exact repository paths of the new dot-named files the act may add.

    A sorted list of unique canonical paths with no pattern character (no globs), each naming a dot-named
    component, none with a .git or .env* component (those refuse even when declared).
    """
    require(type(values) is list and len(values) <= MAX_PATHS and all(type(name) is str for name in values)
            and values == sorted(set(values)), 'declared_dot_path_list')
    for name in values:
        require(canonical_repository_path(name) and not set(name) & PATTERN_CHARACTERS, 'declared_dot_path_exact')
        parts = PurePosixPath(name).parts
        require(any(part.startswith('.') for part in parts), 'declared_dot_path_without_dot_component')
        require(not any(refused_dot_name(part) for part in parts), 'declared_dot_path_git_or_env')
    return values


def tracked_dot_components(name, base_paths, declared=frozenset()):
    """A dot-named component only where the base already tracks that path (a tree or a blob), or where that
    component is the file itself and ``declared`` (the contract's new_dot_paths) names this exact path. Returns
    True when the declaration admitted it.

    The live tree's ignored files and directories are dot names (.env, rebuild/.env, .runtime, .venv, .worktrees);
    a release may not create one, or write into one, that the base does not track. A declaration admits a new
    dot-named FILE only: a dot-named directory the base does not track still refuses, so a declared path can never
    write into an existing ignored directory, and a .git or .env* name refuses even when declared.
    """
    parts = PurePosixPath(name).parts
    admitted = False
    for index, part in enumerate(parts):
        if part.startswith('.') and '/'.join(parts[:index + 1]) not in base_paths:
            require(index == len(parts) - 1 and name in declared, 'untracked_dot_path')
            require(not refused_dot_name(part), 'declared_dot_path_git_or_env')
            admitted = True
    return admitted


def build_manifest(base, entries, blob, *, hooks=frozenset(), base_paths=frozenset(), new_dot_paths=()):
    """The whole-repository delta, one row per path; blob(sha1) returns that blob's bytes.

    ``base_paths`` is every path the base tree tracks, trees included (`git ls-tree -r -t`); without it every dot
    path refuses. ``new_dot_paths`` is the declaration's list (new_dot_path_list): every name in it must be a path
    this delta adds that only the declaration admits, or it refuses as a stale declaration. The manifest records
    the paths it admitted that way, so its digest binds them.
    """
    require(full_sha(base), 'full_base_sha')
    require(0 < len(entries) <= MAX_PATHS, 'finite_non_empty_delta')
    declared = frozenset(new_dot_path_list(list(new_dot_paths)))
    paths, admitted = {}, set()
    for status, old_mode, new_mode, old_blob, new_blob, name in entries:
        require(name not in paths, 'unique_manifest_path')
        kind = classify(name, status, hooks=hooks)
        if tracked_dot_components(name, base_paths, declared):
            admitted.add(name)
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
    for name in sorted(declared):
        require(name in paths, 'declared_dot_path_not_in_delta')
        require(name in admitted, 'declared_dot_path_not_new')
    return {'format': MANIFEST_FORMAT, 'base': base, 'paths': dict(sorted(paths.items())),
            'new_dot_paths': sorted(admitted)}


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
            'new_dot_paths': list(manifest['new_dot_paths']),
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


def base_tree_paths(repo, base):
    """Every path the base tree tracks, trees included."""
    raw = git(repo, 'ls-tree', '-r', '-t', '-z', '--name-only', base)
    require(raw == b'' or raw.endswith(b'\0'), 'nul_terminated_tree_listing')
    return frozenset(name.decode('utf-8') for name in raw.split(b'\0')[:-1])


def compute_manifest(repo, base, candidate, hooks, new_dot_paths=()):
    raw = git(repo, 'diff', '--raw', '--no-renames', '-z', '--no-abbrev', base, candidate)

    def blob(name):
        size = int(git(repo, 'cat-file', '-s', name).decode().strip())
        require(size <= BLOB_LIMIT, 'blob_within_guard_bound')
        return git(repo, 'cat-file', 'blob', name, limit=BLOB_LIMIT)
    return build_manifest(base, parse_raw_diff(raw), blob, hooks=hooks, base_paths=base_tree_paths(repo, base),
                          new_dot_paths=new_dot_paths)


def manifest_paths_on_disk(manifest, root=None):
    """Every manifest path's place in the shared tree, measured with lstat (never following a link).

    Every existing proper prefix must be a real directory: a regular file there (an ignored rebuild/.env), a
    symbolic link or anything else refuses. An added path must not exist in any form, a dangling link included:
    `git merge` silently replaces an IGNORED file that stands in its way. A modified path must be a regular file
    whose mode is its base mode, so the merge changes no mode the manifest does not declare. A declared new dot path
    (the manifest's new_dot_paths) is an added row and gets exactly these guards.
    """
    root = root or ROOT
    added = modified = 0
    for name, row in manifest['paths'].items():
        parts = PurePosixPath(name).parts
        for index in range(1, len(parts)):
            prefix = root.joinpath(*parts[:index])
            try:
                info = prefix.lstat()
            except FileNotFoundError:
                require(row['status'] == 'A', 'modified_path_parent_missing')
                break
            except OSError:
                raise Refusal('manifest_path_unassessable') from None
            require(stat.S_ISDIR(info.st_mode), 'manifest_path_prefix_not_a_directory')
        else:
            path = root.joinpath(*parts)
            try:
                info = path.lstat()
            except FileNotFoundError:
                require(row['status'] == 'A', 'modified_path_missing')
                added += 1
                continue
            except OSError:
                raise Refusal('manifest_path_unassessable') from None
            require(row['status'] == 'M', 'added_path_obstructed')
            expected = 0o755 if row['base_mode'] == '100755' else 0o644
            require(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == expected,
                    'modified_path_regular_at_base_mode')
            modified += 1
            continue
        added += 1
    return {'paths': len(manifest['paths']), 'added_absent': added, 'modified_regular': modified}


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


def declared_new_dot_paths(args):
    """The new dot paths the manifest may admit, which it needs before the declaration rows run.

    Once the declaration is committed in the candidate (its D4 provenance holds), its contract is the only source,
    read from the candidate's blob: the act admits exactly what the merged declaration names, and --new-dot-path,
    if given, must name the same paths. Before that (the preflight of record), they come from --new-dot-path and
    go into the contract to embed. A draft declaration is never read here; its own rows fail.
    """
    given = new_dot_path_list(sorted(set(args.new_dot_path)))
    try:
        proven = declaration_provenance(args.declaration, args.candidate)
    except (Refusal, OSError, subprocess.SubprocessError):
        return {'source': 'command_line', 'new_dot_paths': given}
    raw = git(SOURCE, 'show', args.candidate + ':' + proven['relative'], limit=MAX_DECLARATION_BYTES)
    declared = contract_from(raw.decode())['new_dot_paths']
    require(not given or given == declared, 'new_dot_paths_differ_from_the_declaration')
    return {'source': 'declaration', 'new_dot_paths': declared}


def trusted_gate_scripts(base, root=None):
    """The base's tracked gate scripts in the shared tree, each proven byte-equal to its blob at BASE.

    The citation and the strict declaration gate are judged by these copies, never by the candidate's: a release
    must not be able to certify itself with a checker it changed. Returns {path: sha256}, pinned in the plan.
    """
    root = root or ROOT
    pins = {}
    for relative in TRUSTED_GATE_SCRIPTS:
        path = root / relative
        info = path.lstat()
        require(stat.S_ISREG(info.st_mode) and path.resolve(strict=True) == path, 'trusted_gate_script_file')
        raw = path.read_bytes()
        require(raw == git(root, 'show', base + ':' + relative), 'trusted_gate_script_is_the_base_blob')
        pins[relative] = sha(raw)
    return pins


def verify_gate_scripts(root, pins):
    """The pinned copies are still the bytes on disk, immediately before they run."""
    require(type(pins) is dict and set(pins) == set(TRUSTED_GATE_SCRIPTS), 'gate_script_pins')
    for relative, digest in pins.items():
        path = Path(root) / relative
        require(stat.S_ISREG(path.lstat().st_mode) and path.resolve(strict=True) == path
                and sha(path.read_bytes()) == digest, 'gate_script_unchanged')
    return True


def strict_gate(path, source=None, *, gate_scripts, root=None):
    """The runner's strict gate (scripts/lib/declaration.sh), from the base's copy, read-only in the candidate."""
    source, root = source or SOURCE, root or ROOT
    verify_gate_scripts(root, gate_scripts)
    script = '. "$1/scripts/lib/declaration.sh" && declaration_gate "$2" strict "ruled mutation"'
    result = run(['bash', '-c', script, 'gate', str(root), str(path)], cwd=source, check=False)
    require(result.returncode == 0, 'strict_declaration_gate')
    return {'strict_gate': 'passed', 'output_sha256': sha(result.stdout), 'gate_copy': str(root)}


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
                           'dot_paths', 'new_dot_paths', 'static', 'migrations', 'environment_delta',
                           'dependency_installs', 'venv', 'requirements_mismatch', 'foreign_venv_units', 'backup',
                           'operator'})


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
    new_dot_path_list(value['new_dot_paths'])
    require(set(value['new_dot_paths']) <= set(value['dot_paths']), 'contract_new_dot_paths_are_dot_paths')
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
        'runtime_paths': facts['runtime_paths'], 'dot_paths': facts['dot_paths'],
        'new_dot_paths': facts['new_dot_paths'], 'static': facts['static'],
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


def _process_uid(entry):
    for line in (entry / 'status').read_text().splitlines():
        if line.startswith('Uid:'):
            return int(line.split()[1])
    raise Refusal('process_uid')


def _search_path(entry, name):
    """Where the process found ``name`` on ITS OWN PATH, as Python's getpath does for a bare argv[0].

    None when it has no PATH or no entry holds that file; False when a relative entry comes before the match: that
    entry was resolved against the directory the process STARTED in, which /proc does not keep.
    """
    environ = dict(item.split(b'=', 1) for item in (entry / 'environ').read_bytes().split(b'\0') if b'=' in item)
    if b'PATH' not in environ:
        return None
    for directory in os.fsdecode(environ[b'PATH']).split(os.pathsep):
        if not os.path.isabs(directory):
            return False
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return directory
    return None


def venv_verdict(entry, first, *, target_bin, target_root, interpreter):
    """True, False, or None when this process's use of the venv cannot be determined.

    The executable comes first, read from /proc/<pid>/exe: a symlinked venv runs the system binary (its real path
    is the venv interpreter's real path), so the exe alone separates "another program" from "a Python that may be
    the venv's". Which prefix such a Python took is then decided by how it was started: an absolute argv[0] path,
    or, for a bare name, the process's own PATH. argv alone is never enough: `source .venv/bin/activate && python3
    ...` shows only "python3". A RELATIVE argv[0] (`.venv/bin/python`) or a relative PATH entry was resolved against
    the directory the process started in. /proc keeps only its current directory, which a chdir moves (a test in a
    temporary world, a daemon's chdir('/')), so that use is undetermined, never guessed from the current one.
    """
    try:
        link = os.readlink(entry / 'exe')
        # A binary replaced by a package upgrade reads "<path> (deleted)" for the processes still running it.
        exe = os.path.realpath(link[:-len(' (deleted)')] if link.endswith(' (deleted)') else link)
    except OSError:
        exe = None
    if exe is not None:
        if exe == target_root or exe.startswith(target_root + '/'):
            return True
        if exe != interpreter:
            return False
    if '/' in first:
        if not first.startswith('/'):
            return None    # relative to the start directory, which /proc does not keep
        return os.path.realpath(os.path.dirname(first)) == target_bin
    if exe is None and not INTERPRETER_NAME.fullmatch(first):
        return False
    if not INTERPRETER_NAME.fullmatch(first):
        return None    # the venv's interpreter under a rewritten process title: cannot tell which prefix
    try:
        found = _search_path(entry, first)
    except OSError:
        return None
    return None if found is None or found is False else os.path.realpath(found) == target_bin


def live_venv_users(proc=Path('/proc'), venv=None, exclude=(), uid=None):
    """Processes running the live venv's interpreter, with their cgroup unit.

    Read-only. A process of the operator's own uid whose use of the venv cannot be determined is listed with
    ``undetermined`` (and refuses). Other users' processes expose only cmdline and cgroup: they are decided by an
    absolute argv[0] path, and otherwise counted as ``uninspectable`` in the detail.
    """
    venv = venv or VENV
    target_bin = os.path.realpath(str(venv / 'bin'))
    target_root = os.path.realpath(str(venv))
    interpreter = os.path.realpath(str(venv / 'bin/python'))
    uid = os.getuid() if uid is None else uid
    users = []
    for entry in sorted(proc.iterdir(), key=lambda p: p.name):
        if not entry.name.isdigit() or int(entry.name) in exclude:
            continue
        try:
            argv = (entry / 'cmdline').read_bytes().split(b'\0')
            cgroup = (entry / 'cgroup').read_text()
            owner = _process_uid(entry)
        except (OSError, Refusal):
            continue
        first = os.fsdecode(argv[0]) if argv and argv[0] else ''
        if not first:
            continue    # a kernel thread or a zombie
        verdict = venv_verdict(entry, first, target_bin=target_bin, target_root=target_root, interpreter=interpreter)
        match = re.search(r'^0::/system\.slice/([^/\n]+\.service)', cgroup, re.M)
        row = {'pid': int(entry.name), 'unit': match[1] if match else None}
        if verdict:
            users.append(row)
        elif verdict is None:
            users.append(dict(row, undetermined=True) if owner == uid else dict(row, uninspectable=True))
    return users


def no_undeclared_venv_users(foreign_units, users):
    allowed = set(OWNED_UNITS) | set(foreign_units) | set(OPERATION_UNITS)
    require(not [row for row in users if row.get('undetermined')], 'undeterminable_operator_interpreter_process')
    strays = [row for row in users if not row.get('uninspectable') and row['unit'] not in allowed]
    require(not strays, 'undeclared_process_on_the_live_venv')
    venv_users = [row for row in users if not row.get('uninspectable')]
    return {'processes': len(venv_users), 'units': sorted({row['unit'] for row in venv_users if row['unit']}),
            'uninspectable_other_users': len(users) - len(venv_users)}


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
    if (type(error).__name__ in ('Refusal', 'HelperFailure', 'Interrupted')
            and re.fullmatch(r'[A-Za-z0-9_.:,/ -]{1,400}', label)):
        return label
    name = type(error).__name__
    return name if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', name) else 'Exception'


def preflight(args, *, executing=False):
    """Every precondition, read-only. Returns (report, context); report['passed'] is the verdict."""
    checks = Checks()
    measured = {}
    context = {'measured': measured}
    # Nothing is imported from the candidate worktree before the worktree itself is proven: the first import runs
    # its rebuild/ops/__init__.py, so a tracked file hidden from `git status` (assume-unchanged, skip-worktree) or an
    # untracked module that shadows a source would already have run inside this process by the time a row failed.
    checks.run('git_environment_clean', git_environment_clean)
    if checks.run('candidate_worktree', candidate_worktree, args.candidate) is None:
        for name in ('operator_module_venv_footprint', 'operator_module_backup', 'engine_pins', 'engine_bound'):
            checks.fail(name, 'prerequisite_failed')
        return finish(args, checks, measured), context
    footprint = checks.keep('operator_module_venv_footprint', ops_module, 'venv_footprint')
    backup = checks.keep('operator_module_backup', ops_module, 'rebuild_release_backup')
    engine = checks.keep('engine_pins', load_engine, describe=lambda _: {'pins': ENGINE_PINS})
    context['engine'] = engine
    if engine is None or footprint is None or backup is None:
        checks.fail('engine_bound', 'prerequisite_failed')
        return finish(args, checks, measured), context
    prior = engine.prior
    with bound(engine, args.base):
        checks.run('shared_tree_at_base', shared_tree_at_base, args.base)
        checks.run('origin_main_is_candidate', origin_main_is, args.candidate)
        gate_scripts = checks.run('trusted_gate_scripts', trusted_gate_scripts, args.base)
        if gate_scripts is not None:
            measured['gate_scripts'] = gate_scripts
        hooks = checks.keep('no_merge_time_hooks', merge_hooks, describe=sorted)
        venv = checks.keep('venv_footprint', footprint.snapshot, VENV, describe=footprint.summary)
        if venv is not None:
            context['venv'] = venv
            measured['venv'] = footprint.summary(venv)
        new_dot = checks.run('declared_new_dot_paths', declared_new_dot_paths, args)
        manifest = None
        if hooks is not None and new_dot is not None:
            manifest = checks.keep('whole_repository_manifest', compute_manifest, SOURCE, args.base, args.candidate,
                                   hooks, new_dot['new_dot_paths'],
                                   describe=lambda value: {'sha256': manifest_digest(value),
                                                           **manifest_facts(value)['paths'],
                                                           'new_dot_paths_admitted': value['new_dot_paths']})
        if manifest is not None:
            measured['manifest_sha256'] = manifest_digest(manifest)
            measured['manifest'] = manifest
            checks.run('manifest_paths_unobstructed', manifest_paths_on_disk, manifest)
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
        if gate_scripts is not None:
            citation_line = checks.run('citation', citation, prior, args.candidate, gate_scripts)
            if citation_line is not None:
                measured['citation'] = citation_line
        else:
            checks.fail('citation', 'prerequisite_failed')
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
    if measured.get('gate_scripts') is not None:
        checks.run('strict_declaration_gate', strict_gate, args.declaration, gate_scripts=measured['gate_scripts'])
    else:
        checks.fail('strict_declaration_gate', 'prerequisite_failed')
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


def git_environment_clean():
    """Nothing in the environment redirects or reconfigures git (the act also refuses it, act_git_environment)."""
    require(not [name for name in GIT_ENVIRONMENT_REFUSED if name in os.environ], 'git_environment_clean')
    return {'refused_variables_present': 0}


def candidate_worktree(candidate):
    """The worktree this installer runs from, and imports every operator and engine module from: at the candidate,
    tracked-clean, with git's own state clean (`git status` is silent about assume-unchanged and skip-worktree
    entries, so git_state applies here as in the shared tree), and nothing untracked in rebuild/ops."""
    require(full_sha(candidate), 'full_candidate_sha')
    top = Path(git(SOURCE, 'rev-parse', '--show-toplevel').decode().strip())
    require(top == SOURCE and SOURCE != ROOT and SOURCE.resolve() == SOURCE, 'installer_runs_from_a_candidate_worktree')
    require(git(SOURCE, 'rev-parse', 'HEAD').decode().strip() == candidate, 'candidate_worktree_head')
    require(not git(SOURCE, 'status', '--porcelain', '--untracked-files=no').strip(), 'candidate_worktree_clean')
    return {'worktree': str(SOURCE), 'head': candidate, 'git_state': git_state(SOURCE),
            'import_package': import_package_tracked(SOURCE)}


def import_package_tracked(source=None):
    """rebuild/ops, the package every operator and engine module is imported from, holds nothing git does not track
    (ignored files included). An untracked file there is imported INSTEAD of a tracked source: an extension module
    (__init__.cpython-312-x86_64-linux-gnu.so runs before __init__.py) or a package directory named like a module.
    Bytecode caches are inert (BYTECODE_PREFIX) and allowed."""
    source = source or SOURCE
    raw = git(source, 'ls-files', '--others', '-z', '--', 'rebuild/ops')
    require(raw == b'' or raw.endswith(b'\0'), 'nul_terminated_untracked_listing')
    names = [os.fsdecode(name) for name in raw.split(b'\0')[:-1]]
    strays = [name for name in names if '__pycache__' not in PurePosixPath(name).parts]
    require(not strays, 'untracked_file_in_the_import_package')
    return {'untracked': 0, 'bytecode_caches_ignored': len(names)}


def git_state(repo=None):
    """Git's own state in a repository (the shared tree, or the candidate worktree), read-only: what would make
    `merge --ff-only` refuse or half-apply, or make git read other objects than the ones a sha names.

    Lock files (index, HEAD, ORIG_HEAD, config, packed-refs, shallow, and any under refs/), an unfinished merge,
    cherry-pick, revert, rebase (rebase-merge/ or rebase-apply/, as git decides) or bisect, index entries hidden
    from `git status` by assume-unchanged or skip-worktree, and any replace ref all refuse. A leftover of a finished
    operation (a lone REBASE_HEAD) is reported under ``observed``; it is never refused and never removed.
    """
    repo = repo or ROOT

    def git_path(name):
        value = git(repo, 'rev-parse', '--git-path', name).decode().strip()
        return Path(value) if Path(value).is_absolute() else repo / value

    def present(path):
        try:
            path.lstat()
        except FileNotFoundError:
            return False
        except OSError:
            raise Refusal('git_state_unassessable') from None
        return True
    require(not any(present(git_path(name)) for name in GIT_LOCKS), 'git_lock_file_present')
    refs = git_path('refs')
    require(not any(True for _ in refs.rglob('*.lock')) if refs.is_dir() else True, 'git_ref_lock_present')
    require(not any(present(git_path(name)) for name in GIT_OPERATIONS), 'unfinished_git_operation')
    observed = [name for name in GIT_LEFTOVERS if present(git_path(name))]
    require(not git(repo, 'for-each-ref', '--format=%(refname)', 'refs/replace/').strip(), 'git_replace_refs_present')
    entries = git(repo, 'ls-files', '-v', '-z').split(b'\0')
    hidden = [entry for entry in entries if entry and (entry[:1].islower() or entry[:1] == b'S')]
    require(not hidden, 'assume_unchanged_or_skip_worktree_entries')
    return {'lock_files': 0, 'unfinished_operations': 0, 'hidden_index_entries': 0, 'replace_refs': 0,
            'index_entries': sum(1 for entry in entries if entry), 'observed': observed}


def shared_tree_at_base(base, root=None):
    root = root or ROOT
    require(full_sha(base), 'full_base_sha')
    require(git(root, 'branch', '--show-current').strip() == b'main'
            and git(root, 'rev-parse', 'HEAD').decode().strip() == base
            and not git(root, 'status', '--porcelain', '--untracked-files=no').strip(), 'clean_shared_main_at_base')
    return {'head': base, 'branch': 'main', 'git_state': git_state(root)}


def origin_main_is(candidate):
    """candidate == origin/main, locally (the exact tracking ref) and on the remote (refs/heads/main exactly)."""
    tracking = git(ROOT, 'rev-parse', '--verify', '--end-of-options', 'refs/remotes/origin/main^{commit}')
    require(tracking.decode().strip() == candidate, 'origin_main_tracking_ref')
    # The engine's source_plan reads `rev-parse origin/main`, which a branch or tag named origin/main would win.
    require(git(ROOT, 'rev-parse', 'origin/main').decode().strip() == candidate
            and not any(git_ok(ROOT, 'rev-parse', '--verify', '--quiet', '--end-of-options', shadow)
                        for shadow in ('refs/origin/main', 'refs/tags/origin/main', 'refs/heads/origin/main')),
            'origin_main_unambiguous')
    # ls-remote matches its pattern against the TAIL of every ref name: decl/refs/heads/main matches too.
    rows = [line.split('\t') for line in git(SOURCE, 'ls-remote', 'origin', 'refs/heads/main',
                                              timeout=60).decode().splitlines()]
    exact = [row[0] for row in rows if len(row) == 2 and row[1] == 'refs/heads/main']
    require(len(exact) == 1 and exact[0] == candidate, 'remote_main_is_candidate')
    return {'origin_main': candidate}


def release_stamp(engine, candidate):
    """The engine's renderer on the real file, never printed: only QUILLMD_RELEASE_SHA may change.

    The bytes are returned to the caller's held values and never enter a check detail or a report.
    """
    original = engine.prior.backup_restore.read_private(APP / '.env', 65536)
    engine.render_environment(original, candidate, {})
    return original


def citation(prior, candidate, gate_scripts, root=None):
    """The citation, judged by the base's pinned check-citation.sh in the shared tree (never the candidate's)."""
    root = root or ROOT
    verify_gate_scripts(root, gate_scripts)
    output = prior.command(['bash', str(root / 'scripts/check-citation.sh'), candidate], cwd=root, timeout=120)
    lines = [line for line in output.decode(errors='replace').splitlines() if line.startswith('**Citation')]
    require(lines, 'citation_line')
    return {'citation': lines[-1], 'output_sha256': sha(output), 'checker': str(root / 'scripts/check-citation.sh')}


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


def private_writable_directory(path, label):
    """An existing real directory the operator owns, mode 0700, that this process can create files in."""
    try:
        info = path.lstat()
    except OSError:
        raise Refusal(label) from None
    require(path.resolve() == path and stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
            and stat.S_IMODE(info.st_mode) == 0o700 and os.access(path, os.W_OK | os.X_OK), label)
    return path


def evidence_directory(path):
    path = Path(path)
    require(path.is_absolute() and str(path) == os.path.normpath(str(path)) and not path.exists()
            and not path.is_symlink(), 'new_evidence_directory')
    private_writable_directory(path.parent, 'private_evidence_parent')
    return path


def result_destination(path, evidence=None):
    """--result, checked BEFORE anything else: a new file in a private, writable directory, outside the evidence
    directory. The final write is O_EXCL, and a result path that already exists (a re-run after a refused preflight
    with the same command) would otherwise surface only after a complete install."""
    path = Path(path)
    require(path.is_absolute() and str(path) == os.path.normpath(str(path)) and not path.exists()
            and not path.is_symlink(), 'new_result_file')
    if evidence is not None:
        evidence = Path(evidence)
        require(path != evidence and not path.is_relative_to(evidence) and not evidence.is_relative_to(path),
                'result_outside_the_evidence_directory')
    private_writable_directory(path.parent, 'private_result_directory')
    return path


def diagnostics(engine, error):
    """Fixed classifications and this module's code locations; never exception text. Never raises."""
    try:
        value = engine.failure_diagnostics(error)
    except BaseException:
        value = {'failure_type': 'Exception', 'reason': 'protected_operational_failure'}
    value['label'] = reason(error)
    ours, frame = [], error.__traceback__
    while frame:
        name = Path(frame.tb_frame.f_code.co_filename).name
        if name in ('install_rebuild_release.py', 'venv_footprint.py'):
            ours.append({'module': name, 'line': frame.tb_lineno})
        frame = frame.tb_next
    value['installer_locations'] = ours
    return value


#: The process's record of routed signals while they are blocked (block_signals); None while they are not.
SIGNAL_LEDGER = None


def block_signals():
    """Block SIGTERM, SIGINT and SIGHUP in this process and return the signal ledger (idempotent while blocked).

    No asynchronous handler runs while they are blocked: not one of this module's, not the SIGTERM handler that
    managed_helper.run_helper installs for each helper call, not Python's KeyboardInterrupt. A signal stays pending
    until a checkpoint takes it (take_pending), so it can interrupt no stage, helper call, subprocess start or
    failure path. Children inherit the blocked mask: a git or pip child that keeps it stops only on SIGKILL.
    A signal sent to the process goes to any thread that does not block it, so there must be no other thread.
    """
    global SIGNAL_LEDGER
    if SIGNAL_LEDGER is not None:
        return SIGNAL_LEDGER
    require(threading.current_thread() is threading.main_thread() and threading.active_count() == 1,
            'signals_blocked_in_the_only_thread')
    previous = signal.pthread_sigmask(signal.SIG_BLOCK, SIGNAL_NUMBERS)
    SIGNAL_LEDGER = {'received': [], 'previous_mask': previous}
    return SIGNAL_LEDGER


def take_pending(ledger, stage):
    """Take every pending routed signal without running any handler (sigtimedwait, zero timeout) and record each
    with the stage and its sender. Returns the names taken now. Standard signals do not queue: two SIGTERMs that
    arrive between two checkpoints are one pending signal and one record."""
    taken = []
    while True:
        info = signal.sigtimedwait(SIGNAL_NUMBERS, 0)
        if info is None:
            return taken
        name = signal.Signals(info.si_signo).name
        ledger['received'].append({'signal': name, 'stage': stage, 'sender_pid': info.si_pid,
                                   'sender_uid': info.si_uid})
        taken.append(name)


def signal_names(ledger):
    return [row['signal'] for row in ledger['received']]


def unblock_signals(stage='unblocked'):
    """Take what is still pending (recorded), then restore the mask block_signals found. main() never calls this:
    the signals stay blocked until the process exits, so none is ever delivered with its default action."""
    global SIGNAL_LEDGER
    ledger = SIGNAL_LEDGER
    if ledger is None:
        return None
    take_pending(ledger, stage)
    signal.pthread_sigmask(signal.SIG_SETMASK, ledger['previous_mask'])
    SIGNAL_LEDGER = None
    return ledger


@contextmanager
def blocked_signals():
    """The act's signal scope. Under main() the signals are already blocked and the ledger is shared; when act() is
    called on its own (the tests), it blocks them here and, on the way out, takes and reports what is still pending
    before the previous mask comes back."""
    outer = SIGNAL_LEDGER is not None
    ledger = block_signals()
    try:
        yield ledger
    finally:
        if not outer:
            late = take_pending(ledger, 'after_the_act')
            if late:
                emit({'signals_after_the_act': late})
            unblock_signals()


def child_processes(parent=None, proc=Path('/proc')):
    """The pids whose parent is this process (or ``parent``), read from /proc/<pid>/stat; zombies included."""
    parent = str(os.getpid() if parent is None else parent)
    children = set()
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            text = (entry / 'stat').read_text()
        except OSError:
            continue
        fields = text[text.rfind(')') + 2:].split()
        if len(fields) > 1 and fields[1] == parent:
            children.add(int(entry.name))
    return children


def reap_children(before, *, seconds=REAP_SECONDS, clock=time.monotonic, sleep=time.sleep):
    """Wait for, and reap, every child of this process that was not already running at ``before``.

    subprocess.run kills and waits for its child only once Popen() has returned. An exception raised while Popen is
    still starting `git merge --ff-only` leaves git running with nobody waiting for it, and a measurement of the
    tree taken then can pass while the merge is still about to move HEAD (RP-1). Nothing measures the tree before
    this returns. Returns {'reaped': [{pid, exit}], 'running': [pid]}: ``running`` is what was still alive after
    ``seconds``.
    """
    deadline = clock() + seconds
    reaped = []
    while True:
        alive = []
        for pid in sorted(child_processes() - set(before)):
            try:
                done, status = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                continue
            if done:
                reaped.append({'pid': pid, 'exit': os.waitstatus_to_exitcode(status)})
            else:
                alive.append(pid)
        if not alive or clock() >= deadline:
            return {'reaped': reaped, 'running': alive}
        sleep(0.05)


@contextmanager
def merge_observed(prior, flags):
    """``flags['merge_invoked']`` becomes True only when publish_source calls `git merge` (activate_rowan_corti.git),
    never for one of its refusals before that call. The engine's function is bound back afterwards."""
    original = prior.git

    def observed(*arguments, **options):
        if arguments[:1] == ('merge',):
            flags['merge_invoked'] = True
        return original(*arguments, **options)
    prior.git = observed
    try:
        yield
    finally:
        prior.git = original


def release_coordination(stack):
    """Leave the operation locks and the activation exclusion. The exclusion's release appends a record, which can
    fail (a full disk): that is reported, and never replaces the act's own outcome. Closing twice is harmless."""
    try:
        stack.close()
    except BaseException as error:
        emit({'coordination_release_failed': reason(error)})
        return {'released': False, 'label': reason(error)}
    return {'released': True}


@contextmanager
def act_git_environment():
    """Every git process of the act runs with hooks and automatic maintenance off (GIT_CONFIG_COUNT entries).

    A merge then runs no hook and no `gc --auto` whatever the configured hooks path holds; the path guards keep
    refusing hooks in the delta as well. The environment is restored afterwards.
    """
    git_environment_clean()
    values = {'GIT_CONFIG_COUNT': str(len(ACT_GIT_CONFIG))}
    for index, (key, value) in enumerate(ACT_GIT_CONFIG):
        values['GIT_CONFIG_KEY_%d' % index] = key
        values['GIT_CONFIG_VALUE_%d' % index] = value
    saved = {name: os.environ.get(name) for name in values}
    os.environ.update(values)
    try:
        yield values
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def publication_preconditions(root, base, manifest):
    """Measured again after the stop, immediately before the merge: clean main at base, git's own state (locks,
    unfinished operations, hidden index entries) and every manifest path's place in the tree."""
    return dict(shared_tree_at_base(base, root=root), manifest_paths=manifest_paths_on_disk(manifest, root=root))


def retain(prior, path, value):
    """One evidence file, best effort: a failed write is reported on stderr and never stops a recovery."""
    try:
        prior.write_new(path, value)
        return True
    except BaseException as error:
        emit({'evidence_write_failed': Path(path).name, 'label': reason(error),
              'errno': getattr(error, 'errno', None)})
        return False


def restore_original(engine, host, plan):
    """Start every owned unit (worker first), whatever happens to any one start, then MEASURE the result.

    The original release counts as serving only when every start returned, health reports BASE (the forward
    path's await_health), and every unit is then active with a main PID. `systemctl start` returning 0 proves
    none of that for a Type=simple unit.
    """
    prior = engine.prior
    starts, errors, units = {}, {}, {}
    for unit in (prior.UNITS[2], *prior.UNITS[:2]):
        try:
            host.service('start', unit)
            starts[unit] = True
        except BaseException as error:
            starts[unit] = False
            errors['start:' + unit] = diagnostics(engine, error)
    try:
        value = prior.await_health(plan['base'])
        health = {'release': value.get('release'), 'status': value.get('status')} if type(value) is dict else {}
    except BaseException as error:
        health = {'label': reason(error)}
    for unit in prior.UNITS:
        try:
            state = host.state(unit)
            units[unit] = state.get('ActiveState') == 'active' and state.get('MainPID', '0') not in ('', '0')
        except BaseException as error:
            units[unit] = False
            errors['state:' + unit] = diagnostics(engine, error)
    serving = all(starts.values()) and all(units.values()) and health.get('release') == plan['base']
    return {'release': plan['base'], 'starts': starts, 'health': health, 'units_active': units,
            'original_release_serving': serving, 'errors': errors}


def failure_path(error, *, engine, host, out, plan, stage, flags, original, guard, prepared, signals, measure,
                 children):
    """The act failed before the installation was complete and healthy. Returns the Refusal to raise.

    Exception-proof and uninterruptible (the routed signals are blocked; any that arrive are recorded): whatever
    happens to an evidence write, every unit gets its drain or restore attempt, and what happened is recorded in
    failure.json, in an outcome file, on stderr, and in the Refusal's ``outcome`` (which main() writes to --result,
    in another directory).

      resume started               -> drain every owned unit (the engine's stop_failed_resume)
      stopped, nothing published   -> restore the original release, verified first and measured after
      stopped, publication begun   -> the units stay drained; only a newly declared corrective act may follow

    PUBLICATION BEGINS ONLY WHEN GIT HAS MOVED HEAD OR THE WORKING TREE, and that is MEASURED, never assumed. Every
    child the act started is reaped first (reap_children), so no merge can still move HEAD behind the measurement;
    one still running counts as publication. Then the engine's verify_original_before_resume (HEAD at BASE, the tree
    clean, every base file proven, every new path absent) and ``measure`` (the shared tree as measured before the
    merge: clean main at BASE, git's own state, every manifest path unobstructed) must both pass. A refusal inside
    publish_source before the merge passes them. A lock or an unfinished operation that git left behind, or that
    another process holds, does not: the original is then not intact and nothing is started. A failure after
    publish_source returned is always publication.
    """
    take_pending(signals, 'failure_path')
    recovery, verification = 'none', None
    measuring = flags['stopped'] and not flags['resume_started'] and not flags['publication_completed']
    reaped = reap_children(children, seconds=REAP_SECONDS if measuring else 0)
    if flags['resume_started']:
        recovery = 'drain'
    elif measuring:
        try:
            require(not reaped['running'], 'act_child_process_still_running')
            engine.verify_original_before_resume(original, guard, prepared)
            measure()
            verification, recovery = {'original_intact': True}, 'restore'
        except BaseException as check:
            # Only a merge that was invoked can have begun publication; otherwise the original is simply not proven.
            verification = dict(diagnostics(engine, check), original_intact=False)
            recovery = 'none' if flags['merge_invoked'] else 'refused'
    publication_attempted = flags['publication_completed'] or (flags['merge_invoked'] and recovery != 'restore')
    failure = dict(format=FORMAT, complete=False, stage=stage, **diagnostics(engine, error),
                   stopped=flags['stopped'], resumed=False, resume_started=flags['resume_started'],
                   publication_attempted=publication_attempted, merge_invoked=flags['merge_invoked'],
                   original_verification=verification, recovery=recovery, children=reaped,
                   signals_received=signal_names(signals), signal_records=list(signals['received']),
                   provider_calls=0, automatic_retry=False)
    outcome = {'stage': stage, 'label': failure['label'], 'recovery': recovery,
               'publication_attempted': publication_attempted}
    emit({'rebuild_release_failure': outcome})
    outcome['failure_json'] = retain(engine.prior, out / 'failure.json', failure)
    label = 'installation_failed_inspect_retained_evidence'
    if recovery == 'drain':
        try:
            drain = engine.stop_failed_resume(host)
        except BaseException as drain_error:
            drain = {'all_units_inactive': False, 'drain_error': diagnostics(engine, drain_error)}
        outcome['units_drained'] = drain.get('all_units_inactive') is True
        outcome['outcome_file'] = retain(engine.prior, out / 'failed-resume-drain.json', drain)
        if not outcome['units_drained']:
            label = 'failed_resume_drain_incomplete'
    elif recovery == 'restore':
        restore = restore_original(engine, host, plan)
        outcome['original_release_serving'] = restore['original_release_serving']
        if restore['original_release_serving']:
            outcome['outcome_file'] = retain(engine.prior, out / 'original-release-resumed.json', restore)
        else:
            outcome['outcome_file'] = retain(engine.prior, out / 'original-release-restore-unverified.json', restore)
            label = 'original_restore_unverified_inspect_retained_evidence'
    elif recovery == 'refused':
        outcome['outcome_file'] = retain(engine.prior, out / 'original-recovery-refused.json', verification)
        label = 'original_recovery_refused_inspect_retained_evidence'
    take_pending(signals, 'recovery')
    outcome['signals_received'] = signal_names(signals)
    emit({'rebuild_release_outcome': outcome})
    refusal = Refusal(label)
    refusal.outcome = outcome
    return refusal


def act(engine, plan, context, *, footprint, idle=foreign_idle, snapshot_venv=None, source_state=None):
    """The act, in the engine's own order (activate_core_workflow_repair.py:185-319), with the installer's checks
    inserted (the stage-order test names every insertion).

    Returns (result, postconditions_passed). Raises Refusal on any failure before the install is complete and
    healthy, after failure_path has drained or restored. ``source_state()`` re-measures the shared tree after the
    stop (publication_preconditions over prior.ROOT by default), and again in the failure path before a restore.

    SIGTERM, SIGINT and SIGHUP are blocked from the first statement (block_signals). checkpoint() takes them between
    stages: before publication a signal raises Interrupted into the failure path, which drains or restores; from
    publication on it is recorded only, the act runs to completion and returns not passed (main exits 2).
    """
    prior = engine.prior
    legacy = prior.legacy
    snapshot_venv = snapshot_venv or footprint.snapshot
    if source_state is None:
        def source_state():
            return publication_preconditions(prior.ROOT, plan['base'], context['measured']['manifest'])
    require(Path.cwd().resolve() == prior.ROOT, 'permanent_native_actuation_directory')
    with blocked_signals() as signals, act_git_environment():
        children = child_processes()
        flags = dict(stopped=False, resume_started=False, publication_started=False, publication_completed=False,
                     merge_invoked=False)

        def checkpoint(where):
            taken = take_pending(signals, where)
            if taken and not flags['publication_started']:
                raise Interrupted(taken[0])
        checkpoint('act_start')
        original = prior.backup_restore.read_private(prior.APP / '.env', 65536)
        require(original == context['environment']['original'], 'environment_unchanged_since_preflight')
        active = engine.render_environment(original, plan['candidate'], plan['environment'])
        guard = bind_guard(prior.source_guard())
        prepared = prior.source_plan(plan, guard)
        citation(prior, plan['candidate'], plan['gate_scripts'], root=prior.ROOT)
        checkpoint('evidence_directory')
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
        host = legacy.Host(prior.managed_helper)
        coordination = ExitStack()
        try:
            try:
                stage = 'static_baseline'; note(stage); checkpoint(stage)
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
                stage = 'coordination_locks'; note(stage); checkpoint(stage)
                coordination.enter_context(legacy.operation_locks())
                coordination.enter_context(prior.activation_exclusion.hold(
                    'rebuild-release:' + plan['candidate'][:12], timeout=30))
                baseline = {'static': static_before}
                stage = 'baseline_configuration'; checkpoint(stage); baseline['configuration'] = host.configuration()
                stage = 'baseline_foreign_services'; checkpoint(stage); baseline['services'] = prior.foreign_services()
                require(baseline['services'] == context['services'], 'foreign_services_unchanged_since_preflight')
                stage = 'baseline_foreign_idle'; note(stage); checkpoint(stage)
                baseline['foreign_idle'] = idle(units)
                require(baseline['foreign_idle']['idle'], 'venv_sharing_units_idle_before_stop')
                stage = 'baseline_database'; note(stage); checkpoint(stage); baseline['database'] = engine.snapshot(original)
                stage = 'baseline_clinical_files'; checkpoint(stage)
                baseline['files'] = prior.private_storage.inventory(Path('/var/lib/quillmd/files'))
                stage = 'baseline_pending_check'; checkpoint(stage)
                engine.unchanged(baseline['database'], baseline['database'])
                stage = 'baseline_venv'; note(stage); checkpoint(stage)
                footprint.require_exact(venv_before, snapshot_venv(prior.APP / '.venv'), 'venv_unchanged_since_preflight')
                require(venv_before['footprint_sha256'] == plan['venv_footprint_sha256'], 'venv_is_the_declared_venv')
                baseline['venv'] = footprint.summary(venv_before)
                stage = 'retain_baseline'; checkpoint(stage)
                prior.write_new(out / 'baseline.json', baseline)
                prior.write_new(out / 'venv-before.json', venv_before)
                stage = 'revalidate_before_stop'; note(stage); checkpoint(stage)
                require(prior.source_plan(plan, guard) == prepared, 'source_cut_unchanged_before_stop')
                require((prior.APP / '.env').read_bytes() == original, 'environment_unchanged_before_stop')
                require(primitives.static_inventory(prior.APP / 'staticfiles') == static_before,
                        'static_unchanged_before_stop')
                require(all(host.state(unit)['ActiveState'] == 'active' and host.state(unit)['MainPID'] != '0'
                            for unit in prior.UNITS), 'owned_units_active_before_stop')
                stage = 'stop_owned_services'; note(stage); checkpoint(stage); flags['stopped'] = True
                for unit in prior.UNITS:
                    host.service('stop', unit)
                stage = 'verify_owned_services_stopped'; checkpoint(stage)
                require(all(host.state(unit)['ActiveState'] == 'inactive' and host.state(unit)['MainPID'] == '0'
                            for unit in prior.UNITS), 'owned_units_drained')
                stage = 'database_after_stop'; checkpoint(stage); after_stop = engine.snapshot(original)
                stage = 'retain_database_after_stop'; checkpoint(stage)
                prior.write_new(out / 'database-after-stop.json', after_stop)
                stage = 'database_after_stop'; checkpoint(stage)
                engine.unchanged(baseline['database'], after_stop, health_may_tick=True)
                # Everything taken while the units still served is compared again now, before publication: a
                # change in that window refuses here, and the original release is restored once it is measured
                # intact (the environment and the static tree last, nearest the merge).
                stage = 'venv_after_stop'; note(stage); checkpoint(stage)
                footprint.require_exact(venv_before, snapshot_venv(prior.APP / '.venv'),
                                        'venv_unchanged_before_publication')
                stage = 'foreign_services_after_stop'; checkpoint(stage)
                require(prior.foreign_services() == baseline['services'], 'foreign_services_preserved_before_publication')
                stage = 'configuration_after_stop'; checkpoint(stage)
                require(host.configuration() == baseline['configuration'], 'configuration_preserved_before_publication')
                stage = 'clinical_files_after_stop'; note(stage); checkpoint(stage)
                require(prior.private_storage.inventory(Path('/var/lib/quillmd/files')) == baseline['files'],
                        'clinical_files_preserved_before_publication')
                stage = 'git_state_after_stop'; checkpoint(stage); source_state()
                stage = 'environment_after_stop'; checkpoint(stage)
                require(prior.sha((prior.APP / '.env').read_bytes()) == prior.sha(original),
                        'environment_preserved_before_publication')
                stage = 'static_after_stop'; checkpoint(stage)
                require(primitives.static_inventory(prior.APP / 'staticfiles') == static_before,
                        'static_preserved_before_publication')
                # The last checkpoint that can still recover: from here on a signal is recorded, never acted on.
                stage = 'source_publication'; note(stage); checkpoint(stage); flags['publication_started'] = True
                with merge_observed(prior, flags):
                    prior.publish_source(plan, guard, prepared)
                flags['publication_completed'] = True
                stage = 'static_publication'; checkpoint(stage)
                if plan['static']:
                    static_after = primitives.install_static(prior.APP / 'staticfiles', static_stage, static_before,
                                                             staged)
                else:
                    static_after = primitives.static_inventory(prior.APP / 'staticfiles')
                    require(static_after == static_before, 'static_noop')
                stage = 'environment_publication'; note(stage); checkpoint(stage)
                require((prior.APP / '.env').read_bytes() == original, 'environment_concurrency')
                temporary = prior.APP / PENDING_ENVIRONMENT.name
                prior.write_new(temporary, active); temporary.replace(prior.APP / '.env')
                stage = 'database_before_resume'; checkpoint(stage); before_resume = engine.snapshot(active)
                stage = 'retain_database_before_resume'; checkpoint(stage)
                prior.write_new(out / 'database-before-resume.json', before_resume)
                stage = 'database_before_resume'; checkpoint(stage); engine.unchanged(after_stop, before_resume)
                stage = 'clinical_files_before_resume'; checkpoint(stage)
                require(prior.private_storage.inventory(Path('/var/lib/quillmd/files')) == baseline['files'],
                        'all_clinical_files_preserved')
                stage = 'configuration_before_resume'; checkpoint(stage)
                require(host.configuration() == baseline['configuration'], 'configuration_preserved')
                stage = 'foreign_services_before_resume'; checkpoint(stage)
                require(prior.foreign_services() == baseline['services'], 'foreign_services_preserved')
                stage = 'retain_preservation'; checkpoint(stage)
                evidence_sha256 = {name: prior.sha((out / name).read_bytes()) for name in
                                   ('baseline.json', 'database-after-stop.json', 'database-before-resume.json',
                                    'venv-before.json')}
                prior.write_new(out / 'pre-resume-preservation.json', dict(
                    after_stop_database_exact_before_resume=True, baseline_health_tick_only=True,
                    files_preserved=True, static_inventory=static_after, evidence_sha256=evidence_sha256,
                    provider_calls=0, migrations_executed=0, venv_exact_before_publication=True,
                    configuration_and_files_exact_before_publication=True,
                    environment_delta=['QUILLMD_RELEASE_SHA'], static_sources=list(plan['static'])))
                stage = 'resume_owned_services'; note(stage); checkpoint(stage); flags['resume_started'] = True
                for unit in (prior.UNITS[2], *prior.UNITS[:2]):
                    host.service('start', unit)
                stage = 'normal_https_health'; checkpoint(stage); health = prior.await_health(plan['candidate'])
                stage = 'verify_owned_services_resumed'; checkpoint(stage)
                require(all(host.state(unit)['ActiveState'] == 'active' for unit in prior.UNITS), 'owned_units_active')
            except BaseException as error:
                try:
                    refusal = failure_path(error, engine=engine, host=host, out=out, plan=plan, stage=stage,
                                           flags=flags, original=original, guard=guard, prepared=prepared,
                                           signals=signals, measure=source_state, children=children)
                except BaseException:
                    emit({'rebuild_release_failure_path_error': True, 'stage': stage})
                    refusal = Refusal('installation_failed_recovery_state_unknown')
                # The locks and the exclusion are left after the drain or restore; a failure there is reported and
                # never replaces the refusal (or drops its outcome from --result).
                released = release_coordination(coordination)
                if isinstance(getattr(refusal, 'outcome', None), dict):
                    refusal.outcome['coordination_released'] = released['released']
                raise refusal from None
            # INSTALLED AND HEALTHY. From here every observation is reported for judgement and nothing drains: a
            # foreign restart, a failed configuration read or a signal is a post-condition the act cannot undo by
            # stopping a healthy release. Every measurement still runs; the receipt is written.
            postconditions = {}

            def observe(name, measure):
                try:
                    passed, detail = measure()
                except BaseException as observation_error:
                    postconditions[name] = False
                    return {'label': reason(observation_error)}
                postconditions[name] = passed is True
                return detail

            def venv_measure():
                venv_after = snapshot_venv(prior.APP / '.venv')
                try:
                    footprint.require_exact(venv_before, venv_after, 'venv_changed_during_the_act')
                except Exception as change_error:
                    change = {'label': reason(change_error)}
                    if type(venv_after) is dict and type(venv_after.get('files')) is dict:
                        change['difference'] = footprint.difference(venv_before['files'], venv_after['files'])
                    return False, change
                return True, None

            def idle_measure():
                value = idle(units)
                return value['idle'], value
            observations = {}
            stage = 'configuration_after_resume'; checkpoint(stage)
            observations['configuration'] = observe('configuration_preserved_after_resume', lambda: (
                host.configuration() == baseline['configuration'], None))
            stage = 'foreign_services_after_resume'; checkpoint(stage)
            observations['foreign_services'] = observe('foreign_services_preserved_after_resume', lambda: (
                prior.foreign_services() == baseline['services'], None))
            stage = 'foreign_idle_after_resume'; note(stage); checkpoint(stage)
            after_idle = observe('venv_sharing_units_idle_after_resume', idle_measure)
            stage = 'venv_after_resume'; note(stage); checkpoint(stage)
            venv_change = observe('venv_exact_after_resume', venv_measure)
            for name in POSTCONDITIONS:
                postconditions.setdefault(name, False)
            stage = 'retain_completion'; note(stage); checkpoint(stage)
            released = release_coordination(coordination)
            # Every signal in the ledger arrived after publication: one taken before it would have recovered.
            received = signal_names(signals)
            passed = all(postconditions.values()) and not received and released['released']
            result = dict(format=FORMAT, installed_revision=plan['candidate'], base=plan['base'], complete=True,
                          health=health, migrations_executed=0, provider_calls=0, clinician_decisions_created=0,
                          dependency_installs=0, evidence_sha256=evidence_sha256, plan_sha256=plan['plan_sha256'],
                          declaration_commit=plan['declaration']['commit'],
                          declaration_sha256=plan['declaration']['sha256'],
                          manifest_sha256=plan['manifest_sha256'], environment_delta=['QUILLMD_RELEASE_SHA'],
                          static_sources=list(plan['static']), venv_footprint_sha256=venv_before['footprint_sha256'],
                          postconditions=postconditions, all_postconditions_passed=passed,
                          observations={key: value for key, value in observations.items() if value is not None},
                          foreign_idle_after_resume=after_idle, venv_change=venv_change,
                          interrupted=received[0] if received else None, signals_received=received,
                          signal_records=list(signals['received']), coordination_released=released,
                          strict_preservation_ends_before_resume=True)
            result['receipt_retained'] = retain(prior, out / 'installation-complete.json', result)
            if not result['receipt_retained']:
                emit({'rebuild_release_installed': plan['candidate'], 'all_postconditions_passed': passed,
                      'receipt_retained': False})
            return result, passed and result['receipt_retained']
        finally:
            release_coordination(coordination)


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
            'foreign_venv_units': list(declaration['contract']['foreign_venv_units']),
            'gate_scripts': dict(measured['gate_scripts'])}
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
    parser.add_argument('--new-dot-path', action='append', default=[], metavar='PATH',
                        help='a new dot-named file the delta adds (exact path, repeatable), for the preflight before '
                             'the declaration is committed; from then on the declaration is the only source')
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
    try:
        new_dot_path_list(sorted(set(args.new_dot_path)))
    except Refusal as refusal:
        parser.error('--new-dot-path: ' + str(refusal))
    if args.execute:
        if args.new_dot_path:
            parser.error('--new-dot-path is refused with --execute: the act admits what the merged declaration names')
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
    # No bytecode is read from the source tree for the rest of the process: every module compiles its source.
    sys.pycache_prefix = BYTECODE_PREFIX
    # Read-only git everywhere: no index refresh, no optional lock in the shared tree or the worktree. And no git
    # process, this module's or a child's, reads a replace object.
    os.environ['GIT_OPTIONAL_LOCKS'] = '0'
    os.environ[NO_REPLACE_OBJECTS[0]] = NO_REPLACE_OBJECTS[1]
    if args.execute:
        require(Path.cwd().resolve() == SOURCE, 'run_from_the_candidate_worktree_under_the_runner')
        runner_declaration(args)
        evidence_directory(args.evidence_directory)
    result_destination(args.result, args.evidence_directory if args.execute else None)
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
    # From here until the process exits SIGTERM, SIGINT and SIGHUP stay blocked: only SIGKILL can still cut the act
    # (the runner's ceiling SIGTERMs, then SIGKILLs 15 s later), and every other signal is recorded, never delivered.
    signals = block_signals()
    with bound(engine, args.base, plan['static']):
        try:
            result, passed = act(engine, plan, context, footprint=ops_module('venv_footprint'))
        except BaseException as error:
            late = take_pending(signals, 'after_the_act')
            # A second record of the outcome, in another directory; a failure to write it never masks the act's.
            try:
                write_result(args.result, {'format': FORMAT, 'complete': False, 'label': reason(error),
                                           'recovery': getattr(error, 'outcome', None),
                                           'evidence_directory': str(args.evidence_directory),
                                           'signals_received': signal_names(signals)})
            except BaseException as write_error:
                emit({'result_write_failed': reason(write_error), 'label': reason(error)})
            if late:
                emit({'signals_after_the_act': late})
            raise
    # INSTALLED. Nothing from here may turn the install into a failure: the result file and stdout are second
    # records (the receipt is the first), so a failure to write either is reported and the exit is 2, never 1.
    late = take_pending(signals, 'after_the_act')
    written = True
    try:
        receipt = Path(plan['evidence_directory']) / 'installation-complete.json'
        write_result(args.result, {'format': FORMAT, 'complete': True, 'all_postconditions_passed': passed,
                                   'evidence_directory': str(args.evidence_directory),
                                   'receipt_sha256': sha(receipt.read_bytes()) if receipt.is_file() else None,
                                   'signals_received': signal_names(signals), 'signals_after_the_act': late})
    except BaseException as write_error:
        written = False
        emit({'result_write_failed': reason(write_error), 'rebuild_release_installed': plan['candidate'],
              'all_postconditions_passed': passed})
    try:
        print(json.dumps(result, indent=1, sort_keys=True, default=str))
    except (OSError, ValueError):
        pass
    late += take_pending(signals, 'after_the_result')
    if late:
        emit({'signals_after_the_act': late})
    return 0 if passed and written and not late else 2


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
