#!/usr/bin/env python3
"""Preserving code-only activation for reviewed typed-note and voice usability.

Default is read-only. Execute only from the exact clean reviewed target worktree
through the committed declaration. Reuse the existing authenticated capture and
independent-key restore honestly; no migration, backup or provider call is made.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import gzip
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile
import uuid
import subprocess
import sys
import time
import types

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
SOURCE = Path(__file__).resolve().parents[1]
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
EVIDENCE = PRIVATE / 'typed-voice-20260921'
SELF = 'scripts/activate-typed-voice.py'
DECL = 'docs/foundation/mutations/20260921-quillmd-typed-voice.md'
ADAPTER = 'scripts/activate-business-readiness.py'
ADAPTER_SHA256 = '4e85207114a175d248907a82a49c60408d1e58f6f9a83011c8f3214734896a04'
BASELINE = '08e40870f18ca4e79b0cc2b27d6b09ba48f911a7'
RUNNING_RELEASE = 'cf3905346d1b72d29cf602b98853f4017294afb5'
MIGRATION = '0017_reconciliation_evidence_kind'
RUNTIME_ALLOWED = {
    '.github/workflows/test.yml',
    SELF, 'rebuild/ops/test_typed_voice_activation.py',
    'rebuild/core/forms.py', 'rebuild/core/views.py', 'rebuild/core/generation.py', 'rebuild/core/jobs.py',
    'rebuild/core/tests/test_input_workflow.py',
    'rebuild/core/tests/test_recording_limit.py',
    'rebuild/core/tests/test_tab_form_workflow.py',
    'rebuild/core/tests/test_natural_tab_generation.py',
    'rebuild/templates/encounter_detail.html', 'rebuild/templates/encounter_input.html',
    'rebuild/templates/encounter_form.html',
    'rebuild/static/app.css', 'rebuild/static/app.js',
    'rebuild/input-workflow-browser.mjs',
    'rebuild/wm-browser-tests.mjs', 'rebuild/build-word-evidence.mjs',
    'scripts/ci/verify-fresh.sh',
}
REQUIRED = {SELF, DECL, 'rebuild/templates/encounter_detail.html',
            'rebuild/ops/test_typed_voice_activation.py'}
STATIC_INPUTS = {'app.css', 'app.js', 'django_otp/css/login.css',
                 'otp_totp/css/qrcode.css', 'otp_totp/js/qrcode.js'}
FAILED_TARGET = '6697433d0a2b6155e35a7d77bbadc2ec0ebeabe6'
FAILED_RECEIPT = EVIDENCE / 'typed-voice-activation-6697433d.json'
FAILED_RECEIPT_SHA256 = '1d4212ba413cf139912c93b20d595a7cc5ea21ef3d38a965d9d8ef166952a8ad'
RESUME_DECL = 'docs/foundation/mutations/20260921-quillmd-typed-voice-static-resume.md'
RESUME_PATHS = {SELF, 'rebuild/ops/test_typed_voice_activation.py', RESUME_DECL}



def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


data = (SOURCE / ADAPTER).read_bytes()
require(sha(data) == ADAPTER_SHA256, 'Qualified preserving adapter changed.')
a = types.ModuleType('_typed_voice_preserving_adapter')
a.__file__ = str(SOURCE / ADAPTER)
sys.modules[a.__name__] = a
exec(compile(data, a.__file__, 'exec'), a.__dict__)
for name in ('ROOT', 'SOURCE', 'APP', 'PRIVATE', 'EVIDENCE', 'SELF', 'DECL', 'BASELINE', 'RUNNING_RELEASE'):
    setattr(a, name, globals()[name])
a.BASELINE_OPERATION_PATHS = set()
b = a.configured_driver()


def validate_changed(changed):
    require(REQUIRED <= changed, 'Required reviewed typed/voice change is absent.')
    require(all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                and str(PurePosixPath(name)) == name for name in changed), 'Noncanonical changed path.')
    require(all(name in RUNTIME_ALLOWED or name == DECL
                or (name.startswith('docs/rebuild/') and name.endswith('.md')) for name in changed),
            'Undeclared source change; expand only after review.')


def full_rows(old):
    # No projection, exclusions, historical count freeze or migration exception:
    # preserve legitimate later activity exactly as captured with writers stopped.
    return old.fingerprints(old.tables())


def unchanged(before, after):
    require(before.keys() == after.keys(), 'Preservation inventory shape changed.')
    for name in before:
        require(after[name] == before[name], 'Undeclared code-only activation delta: ' + name)


def unchanged_saved_snapshot(before, after):
    """Compare all saved/current values using the receipt's JSON representation.

    The qualified SQL readers return constraint/index rows as tuples, while a
    JSON receipt reloads those same arrays as lists. Normalize only that wire
    representation; never sort arrays, omit fields or coerce scalar values.
    """
    def receipt_value(value):
        if isinstance(value, dict):
            require(all(type(key) is str for key in value), 'Snapshot object keys must remain JSON strings.')
            return {key: receipt_value(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [receipt_value(item) for item in value]
        return value
    require(before.keys() == after.keys(), 'Preservation inventory shape changed.')
    for name in before:
        require(json.dumps(receipt_value(after[name]), sort_keys=True, allow_nan=False) ==
                json.dumps(receipt_value(before[name]), sort_keys=True, allow_nan=False),
                'Undeclared saved-state activation delta: ' + name)


def verify_migrations(old, plan):
    b.verify_migration_plan(plan, applied=True)
    require(b.output(old.PSQL + ["SELECT name FROM django_migrations WHERE app='core' ORDER BY id DESC LIMIT 1"]) == MIGRATION,
            'Unexpected migration frontier.')
    require(b.output(old.PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + MIGRATION + "'"]) == '1',
            'Exactly one existing 0017 history row required.')


def assert_retained_capture(manifest, modules, storage):
    require(manifest['run_id'] == a.CAPTURE_RUN, 'Unqualified retained capture.')
    for item in manifest['files']:
        got = storage.get(item['path'])
        require(got and got.get('sha256') == item['sha256'] and got.get('size') == item['size'],
                'Retained backed-up file changed; inspect before activation.')
    import psycopg
    backup = modules['backup']
    with psycopg.connect(**backup.source_options(APP, b.ROLES), autocommit=True) as conn:
        conn.execute("SET timezone='UTC'")
        conn.execute("SET datestyle='ISO, MDY'")
        conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        def copy_hash(statement):
            digest = hashlib.sha256()
            with conn.cursor().copy(statement) as stream:
                for value in stream:
                    digest.update(value)
            return digest.hexdigest()
        actual = backup.fingerprint(lambda statement: conn.execute(statement).fetchall(), copy_hash)
        require(set(actual) == set(manifest['tables']), 'Retained capture table population differs.')
        require(not any(backup.invariant_counts(lambda statement: conn.execute(statement).fetchall()).values()),
                'Current financial invariants fail.')
        conn.execute('ROLLBACK')
    a.BACKUP_COMPARISONS.append({'observed_at': datetime.now(timezone.utc).isoformat(), 'run_id': a.CAPTURE_RUN,
        'all_current_table_hashes_match_capture': actual == manifest['tables'],
        'differing_tables': [name for name in sorted(actual) if actual[name] != manifest['tables'][name]],
        'current_table_fingerprints': actual, 'fresh_capture_performed': False,
        'qualification': 'Historical recovery evidence only; full current stopped rows/files must remain identical.'})


def snapshot(modules, helper):
    # The qualified snapshot resolves rows in b's global namespace.
    return a.snapshot(modules, helper)


b.rows = full_rows


def static_inventory(root):
    """Bounded descriptor reads of operator-owned public assets, without following links."""
    require(root.is_absolute() and root.resolve(strict=True) == root, 'Canonical static root required.')
    rows = {}
    total = 0
    for path in [root, *sorted(root.rglob('*'))]:
        require(len(rows) < 10000, 'Static inventory exceeds bounded population.')
        info = path.lstat()
        directory = stat.S_ISDIR(info.st_mode)
        require(info.st_uid == os.getuid() and (directory or stat.S_ISREG(info.st_mode))
                and stat.S_IMODE(info.st_mode) == (0o755 if directory else 0o644)
                and (directory or info.st_nlink == 1), 'Unsafe public static object or permissions.')
        relative = '.' if path == root else path.relative_to(root).as_posix()
        row = {'mode': stat.S_IMODE(info.st_mode), 'device': info.st_dev, 'inode': info.st_ino,
               'kind': 'directory' if directory else 'file'}
        if not directory:
            total += info.st_size
            require(info.st_size <= 16 * 1024 * 1024 and total <= 64 * 1024 * 1024,
                    'Static inventory exceeds bounded bytes.')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                opened = os.fstat(stream.fileno())
                require((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino), 'Static input changed.')
                data = stream.read(info.st_size + 1)
                after = os.fstat(stream.fileno())
            identity = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            require(len(data) == info.st_size and all(getattr(info, key) == getattr(candidate, key)
                    for candidate in (opened, after, path.lstat()) for key in identity), 'Static input changed during read.')
            row.update(size=len(data), sha256=sha(data))
        rows[relative] = row
    return rows


def create_static_stage(stage):
    """Set the mode of this exclusively created public-assets directory only."""
    require(stage.is_absolute() and stage.parent.resolve(strict=True) == stage.parent,
            'Canonical static stage parent required.')
    stage.mkdir(mode=0o700)
    expected = stage.lstat()
    fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        actual = os.fstat(fd)
        require(stat.S_ISDIR(actual.st_mode) and actual.st_uid == os.getuid()
                and (actual.st_dev, actual.st_ino) == (expected.st_dev, expected.st_ino),
                'New static stage identity changed.')
        os.fchmod(fd, 0o755)
    finally:
        os.close(fd)


def collect_static(stage):
    # Static compilation requires neither project settings/credentials nor a DB
    # role. Keep the migrator's allowlist unchanged; configure only these five
    # public sources in a fresh subprocess instead of invoking management shell.
    require(stage.is_absolute() and stage.resolve(strict=True) == stage
            and stage.is_dir() and not list(stage.iterdir()), 'Unused canonical static stage required.')
    code = (
        'from django.conf import settings; '
        'settings.configure(SECRET_KEY="public-static-build-only", '
        'INSTALLED_APPS=["django.contrib.staticfiles","django_otp","django_otp.plugins.otp_totp"], '
        'STATIC_URL="/static/", STATIC_ROOT=' + repr(str(stage)) + ', '
        'STATICFILES_DIRS=[' + repr(str(APP / 'static')) + '], '
        'STORAGES={"staticfiles":{"BACKEND":"quillmd.static_storage.PublicCompressedManifestStaticFilesStorage",'
        '"OPTIONS":{"file_permissions_mode":420,"directory_permissions_mode":493}}}); '
        'import django; django.setup(); from django.core.management import call_command; '
        'call_command("collectstatic", interactive=False, verbosity=0)')
    # Credentials are not inherited or read; use only the runtime interpreter and
    # its installed packages. The project settings module is never loaded.
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    b.run([str(APP / '.venv/bin/python'), '-B', '-c', code], cwd=APP, env=env,
          stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def validate_staged_static(root, inputs):
    rows = static_inventory(root)
    manifest = json.loads((root / 'staticfiles.json').read_bytes())
    require(set(manifest) == {'paths', 'version', 'hash'} and manifest['version'] == '1.1'
            and type(manifest['paths']) is dict and set(manifest['paths']) == set(inputs) == STATIC_INPUTS,
            'Staged manifest must contain exactly the five qualified static inputs.')
    require(manifest['hash'] == hashlib.md5(json.dumps(sorted(manifest['paths'].items())).encode()).hexdigest()[:12],
            'Staged manifest identity differs from Django content identity.')
    allowed = {'staticfiles.json'}
    directories = {'.'}
    for source, compiled in manifest['paths'].items():
        original = PurePosixPath(source)
        require(not original.is_absolute() and '..' not in original.parts and str(original) == source,
                'Noncanonical public source path.')
        pattern = re.escape(str(original.with_suffix(''))) + r'\.[a-f0-9]{12}' + re.escape(original.suffix)
        require(type(compiled) is str and re.fullmatch(pattern, compiled), 'Unexpected compiled public asset path.')
        source_bytes = inputs[source].read_bytes()
        require(rows.get(source, {}).get('kind') == rows.get(compiled, {}).get('kind') == 'file'
                and (root / source).read_bytes() == source_bytes == (root / compiled).read_bytes()
                and compiled == str(original.with_suffix('')) + '.' + hashlib.md5(source_bytes).hexdigest()[:12] + original.suffix,
                'Compiled public asset differs from its exact current source.')
        for name in (source, compiled):
            allowed.update((name, name + '.gz', name + '.br'))
            directories.update(str(parent) for parent in PurePosixPath(name).parents)
            if name + '.gz' in rows:
                require(gzip.decompress((root / (name + '.gz')).read_bytes()) == source_bytes,
                        'Gzip static output differs from source.')
            if name + '.br' in rows:
                import brotli
                require(brotli.decompress((root / (name + '.br')).read_bytes()) == source_bytes,
                        'Brotli static output differs from source.')
    require(all(name in (directories if row['kind'] == 'directory' else allowed) for name, row in rows.items()),
            'Staged static output contains an undeclared asset.')
    return rows


def static_delta(before, staged):
    """Old hashes and OTP assets are immutable; only current app aliases/manifest move."""
    replaceable = {'staticfiles.json'} | {name + suffix for name in ('app.css', 'app.js') for suffix in ('', '.gz', '.br')}
    require({name for name, row in before.items() if row['kind'] == 'directory'} ==
            {name for name, row in staged.items() if row['kind'] == 'directory'}, 'Static directory layout changed.')
    changes = {}
    for name, row in staged.items():
        if row['kind'] != 'file':
            continue
        old = before.get(name)
        content = {key: row[key] for key in ('kind', 'mode', 'size', 'sha256')}
        if old is not None and all(old.get(key) == value for key, value in content.items()):
            continue
        require(old is None or name in replaceable, 'Previously published immutable static asset changed.')
        changes[name] = row
    return changes


def retain_static(root, archive_path, rows):
    require(static_inventory(root) == rows, 'Static inputs changed before rollback archive.')
    fd = os.open(archive_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        with tarfile.open(fileobj=stream, mode='w') as archive:
            for name, row in rows.items():
                if row['kind'] != 'file':
                    continue
                data = (root / name).read_bytes()
                require(sha(data) == row['sha256'] and len(data) == row['size'], 'Static rollback input changed.')
                item = tarfile.TarInfo(name)
                item.mode = 0o644
                item.size = len(data)
                archive.addfile(item, io.BytesIO(data))
        stream.flush()
        os.fsync(stream.fileno())
    require(static_inventory(root) == rows, 'Static inputs changed during rollback archive.')


def install_static(root, stage, before, staged):
    require(static_inventory(root) == before and static_inventory(stage) == staged,
            'Static source or target changed before installation.')
    changes = static_delta(before, staged)
    # Publish the manifest last; all writers remain stopped throughout this act.
    for name in sorted(changes, key=lambda name: (name == 'staticfiles.json', name)):
        target = root / name
        data = (stage / name).read_bytes()
        require(sha(data) == staged[name]['sha256'] and len(data) == staged[name]['size'], 'Staged asset changed.')
        require(target.parent.resolve(strict=True) == target.parent, 'Static parent changed.')
        temporary = target.with_name('.typed-voice-' + uuid.uuid4().hex)
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o644)
        try:
            with os.fdopen(fd, 'wb') as stream:
                os.fchmod(stream.fileno(), 0o644)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if name in before:
                info = target.lstat()
                require((info.st_dev, info.st_ino) == (before[name]['device'], before[name]['inode'])
                        and stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid()
                        and sha(target.read_bytes()) == before[name]['sha256'], 'Static target changed before replacement.')
                os.replace(temporary, target)
            else:
                os.link(temporary, target, follow_symlinks=False)
                temporary.unlink()
        finally:
            if temporary.exists():
                temporary.unlink()
    after = static_inventory(root)
    require(set(after) == set(before) | set(changes), 'Unexpected static file addition or removal.')
    for name, row in before.items():
        if name not in changes:
            require(after[name] == row, 'Previously published static asset or directory changed.')
    for name in changes:
        require(all(after[name][key] == staged[name][key] for key in ('kind', 'mode', 'size', 'sha256')),
                'Installed static asset differs from validated staged output.')
    return after


def verify_source(target):
    require(re.fullmatch('[a-f0-9]{40}', target), 'Full merged target required.')
    require(SOURCE.is_relative_to(ROOT / '.worktrees') and SOURCE.resolve() == SOURCE,
            'Use the retained reviewed target worktree.')
    require(not b.output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=SOURCE)
            and not b.output(['git', 'diff', '--name-only', target], cwd=SOURCE),
            'Target worktree must be clean and byte-equivalent to the merged target.')
    require(b.git('rev-parse', 'HEAD') == BASELINE and b.git('branch', '--show-current') == 'main'
            and b.git('rev-parse', 'origin/main') == target
            and not b.git('status', '--porcelain', '--untracked-files=no'),
            'Shared main must be clean at the measured baseline; concurrent work requires inspection.')
    b.run(['git', 'merge-base', '--is-ancestor', BASELINE, target], cwd=ROOT)
    changed = set(b.git('diff', '--name-only', BASELINE, target).splitlines())
    validate_changed(changed)
    require(Path(__file__).read_bytes() == b.blob(target, SELF)
            and (SOURCE / ADAPTER).read_bytes() == b.blob(BASELINE, ADAPTER) == b.blob(target, ADAPTER),
            'Adapter/entry-point target identity mismatch.')
    return changed


def validate_failed_receipt(data):
    require(sha(data) == FAILED_RECEIPT_SHA256, 'Original failed activation receipt changed.')
    failed = json.loads(data)
    require(failed.get('complete') is False and failed.get('target') == FAILED_TARGET
            and failed.get('baseline') == BASELINE and failed.get('served_before') == RUNNING_RELEASE
            and failed.get('stage') == 'collect_and_install_source_bound_public_assets'
            and failed.get('failure_kind') == 'CalledProcessError'
            and failed.get('failure_services_stopped') is True
            and failed.get('migration_performed') is False and failed.get('provider_calls') == 0,
            'Only the exact stopped static-collection refusal is resumable.')
    require(failed['stopped_before'] == failed['stopped_after_source'], 'Failed act changed protected stopped state.')
    require(failed['state_directory'] == str(EVIDENCE / ('activation-state-' + FAILED_TARGET[:12])),
            'Original rollback state path changed.')
    return failed


def verify_resume_source(target):
    require(re.fullmatch('[a-f0-9]{40}', target), 'Full merged repair target required.')
    require(SOURCE.is_relative_to(ROOT / '.worktrees') and SOURCE.resolve() == SOURCE,
            'Use the retained reviewed repair worktree.')
    require(not b.output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=SOURCE)
            and not b.output(['git', 'diff', '--name-only', target], cwd=SOURCE),
            'Repair worktree must be clean and byte-equivalent to merged target.')
    require(b.git('rev-parse', 'HEAD') == FAILED_TARGET and b.git('branch', '--show-current') == 'main'
            and b.git('rev-parse', 'origin/main') == target
            and not b.git('status', '--porcelain', '--untracked-files=no'),
            'Shared main must remain at the exact failed target before resume.')
    b.run(['git', 'merge-base', '--is-ancestor', FAILED_TARGET, target], cwd=ROOT)
    changed = set(b.git('diff', '--name-only', FAILED_TARGET, target).splitlines())
    require(changed == RESUME_PATHS, 'Resume may change only the collector, its tests and this declaration.')
    require(Path(__file__).read_bytes() == b.blob(target, SELF)
            and (SOURCE / ADAPTER).read_bytes() == b.blob(FAILED_TARGET, ADAPTER) == b.blob(target, ADAPTER),
            'Repair adapter target identity mismatch.')
    return changed


def failure_details(error, stage):
    result = {'failure_kind': type(error).__name__, 'failure_stage': stage,
              'failure_diagnostic_code': 'activation_guard_or_action_refused'}
    if isinstance(error, subprocess.CalledProcessError):
        stderr = error.stderr if isinstance(error.stderr, bytes) else (error.stderr or '').encode()
        result.update(failed_subprocess_exit_code=error.returncode,
            failure_stderr_bytes=len(stderr), failure_stderr_sha256=sha(stderr),
            failure_diagnostic_code=('credential_free_static_collection_failed'
                if stage == 'collect_and_install_source_bound_public_assets' else 'bounded_subprocess_failed'))
    return result


def resume_failed(args):
    """One exact forward repair; never replay the source/data transition blindly."""
    require(Path(args.resume_failed) == FAILED_RECEIPT, 'Only the pinned failed result may be resumed.')
    changed = verify_resume_source(args.target)
    pulls = json.loads(b.output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'Exact merged repair PR required.')
    b.run(['bash', str(ROOT / 'scripts/check-citation.sh'), args.target], cwd=ROOT)
    modules = {name: a.load(name, relative, args.target) for name, relative in b.HELPERS.items()}
    old, word, identity, storage, previous = (modules[k] for k in ('old', 'word', 'identity', 'storage', 'previous'))
    failed = validate_failed_receipt(word.checked_file(FAILED_RECEIPT, private=True))
    state_before = Path(failed['state_directory'])
    require(state_before.resolve(strict=True) == state_before and state_before.is_dir(), 'Canonical prior state required.')
    old_stage = state_before / 'static-stage'
    require(old_stage.resolve(strict=True) == old_stage and old_stage.is_dir() and not list(old_stage.iterdir()),
            'Original collector progressed unexpectedly; inspect without generic resume.')
    b.stopped()
    require(len(old.tables()) == 35 and b.output(old.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Unexpected tables or unresolved jobs during repair.')
    verify_migrations(old, b.output(b.management('showmigrations', '--plan'), cwd=APP))
    original = word.checked_file(APP / '.env', private=True)
    require(original == word.checked_file(state_before / 'prior-environment.env', private=True)
            and sha(original) == failed['environment_before_sha256'], 'Environment changed after failed activation.')
    updated = b.updated_environment(original, args.target)
    require(args.backup_report == failed['backup_report'], 'Historical recovery reference changed.')
    restore, manifest = a.backup_evidence(args.backup_report, modules)
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper)
            and b.output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper,
            'Pinned service helper unavailable.')
    old.static_inventory = lambda _identity, _word: static_inventory(APP / 'staticfiles')
    baseline = snapshot(modules, helper)
    unchanged_saved_snapshot(failed['stopped_before'], baseline)
    assert_retained_capture(manifest, modules, baseline['storage']['files'])
    protected = previous.protected()
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE), 'Installed Word SDK inputs changed.')
    installed = APP / '.word-sdk' / modules['billing'].SDK_RELEASE
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                   installed / 'build-proof.json', modules['billing'].PIN, inputs)
    identity.source_readability(helper)
    lock = PRIVATE / '.private-readiness-activation.lock'
    lock_bytes = word.checked_file(lock, private=True)
    lock_value = json.loads(lock_bytes)
    require(lock_value.get('target') == FAILED_TARGET and lock_value.get('automatic_rollback') is False
            and type(lock_value.get('pid')) is int and lock_value['pid'] > 1, 'Original activation lock differs.')
    try:
        os.kill(lock_value['pid'], 0)
    except ProcessLookupError:
        pass
    else:
        raise RuntimeError('Original activation process is still present; do not resume concurrently.')
    result_path = Path(args.result)
    state = EVIDENCE / ('static-resume-state-' + args.target[:12])
    require(result_path.is_absolute() and result_path.resolve() == result_path and result_path.parent == EVIDENCE
            and re.fullmatch(r'typed-voice-resume-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not any(p.exists() or p.is_symlink() for p in (result_path, state)), 'Unused protected repair result/state required.')
    b.run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
    print('Read-only exact failed-state repair checks passed; writers remain stopped.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration == SOURCE / RESUME_DECL
            and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == b.blob(args.target, RESUME_DECL) == b.blob(commit, RESUME_DECL),
            'Committed exact repair declaration required.')
    b.run(['git', 'merge-base', '--is-ancestor', commit, args.target], cwd=ROOT)
    state.mkdir(mode=0o700)
    identity.private_write(state / 'original-lock.json', lock_value)
    require(word.checked_file(state / 'original-lock.json', private=True) == lock_bytes,
            'Retained original lock bytes differ.')
    result = {'complete': False, 'started_at': datetime.now(timezone.utc).isoformat(),
        'baseline': FAILED_TARGET, 'served_before': RUNNING_RELEASE, 'target': args.target,
        'changed_paths': sorted(changed), 'resumed_failure': str(FAILED_RECEIPT),
        'resumed_failure_sha256': FAILED_RECEIPT_SHA256, 'prior_rollback_state': str(state_before),
        'state_directory': str(state), 'provider_calls': 0, 'migration_performed': False,
        'stopped_before': baseline, 'environment_before_sha256': sha(original), 'environment_after_sha256': sha(updated),
        'backup_report': args.backup_report, 'backup_run_id': manifest['run_id'],
        'restored_backup_run_id': restore['backup_run_id'], 'original_failed_result_preserved': True}
    phase = 0
    def checkpoint(stage):
        nonlocal phase
        result['stage'] = stage
        identity.private_write(state / f'phase-{phase:02d}.json', result)
        phase += 1
    try:
        checkpoint('advance_only_reviewed_static_repair')
        b.stopped()
        verify_resume_source(args.target)
        unchanged(baseline, snapshot(modules, helper))
        require(word.checked_file(lock, private=True) == lock_bytes
                and word.checked_file(APP / '.env', private=True) == original, 'Repair preconditions changed.')
        b.run(['git', 'merge', '--ff-only', args.target], cwd=ROOT, stdout=subprocess.DEVNULL)
        require(b.git('rev-parse', 'HEAD') == args.target and not b.git('status', '--porcelain', '--untracked-files=no'),
                'Shared source differs from exact repair target.')
        verify_migrations(old, b.output(b.management('showmigrations', '--plan'), cwd=APP))
        b.run(b.management('check'), cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        unchanged(baseline, snapshot(modules, helper))
        checkpoint('collect_and_install_source_bound_public_assets')
        stage = state / 'static-stage'
        create_static_stage(stage)
        collect_static(stage)
        staged = validate_staged_static(stage, identity.static_sources())
        installed_static = install_static(APP / 'staticfiles', stage, baseline['static'], staged)
        result['static_transition'] = {'before': baseline['static'], 'staged': staged, 'after': installed_static,
            'old_immutable_assets_retained': True, 'prior_archive': str(state_before / 'prior-static.tar')}
        baseline = dict(baseline, static=installed_static)
        unchanged(baseline, snapshot(modules, helper))
        result['source_readability'] = identity.source_readability(helper)
        checkpoint('replace_release_setting_only')
        modules['env'].replace_environment(APP / '.env', original, updated)
        checkpoint('start_and_verify_exact_private_release')
        word.systemd('start', helper)
        for attempt in range(45):
            try:
                live_health = b.health(args.target)
                break
            except (subprocess.CalledProcessError, json.JSONDecodeError, RuntimeError):
                time.sleep(1)
        else:
            raise RuntimeError('Repaired private release did not become healthy.')
        result['proofs_after'] = identity.verify_live(args.target, storage)
        result['interfaces_after'] = identity.verify_interfaces()
        worker_after = old.worker_process()
        require(worker_after['systemd_start'] != failed['worker_before']['systemd_start']
                and worker_after['kernel_start_utc'] > failed['worker_before']['kernel_start_utc'], 'Worker restart not evidenced.')
        result['worker_after'] = worker_after
        unchanged(baseline, snapshot(modules, helper))
        require(word.checked_file(APP / '.env', private=True) == updated and previous.protected() == protected,
                'Configuration or protected services changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                    installed / 'build-proof.json', modules['billing'].PIN, inputs) == artifact,
                'Installed Word SDK changed.')
        b.run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
        result.update(complete=True, health=live_health, existing_rows_unchanged=True,
            existing_schema_indexes_constraints_catalog_unchanged=True, private_files_and_mail_unchanged=True,
            existing_hashed_assets_retained=True, static_delta_source_bound=True,
            backup_units_installed=False, finished_at=datetime.now(timezone.utc).isoformat())
        require(word.checked_file(lock, private=True) == lock_bytes, 'Original lock changed before completion.')
        checkpoint('complete')
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(failure_details(error, result.get('stage')), complete=False, finished_at=datetime.now(timezone.utc).isoformat())
        try:
            word.systemd('stop', helper); b.stopped(); result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False; result['stop_failure_kind'] = type(stop_error).__name__
        identity.private_write(result_path, result)
        raise RuntimeError('Private static repair stopped; inspect retained failure and rollback evidence.') from None
    print('Private static repair and exact installed release verified; evidence: ' + str(result_path), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--resume-failed', help='Resume only the pinned static-collection refusal; no generic retry.')
    args = parser.parse_args()
    if args.resume_failed:
        return resume_failed(args)
    changed = verify_source(args.target)
    pulls = json.loads(b.output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'Exact merged PR required.')
    b.run(['bash', str(ROOT / 'scripts/check-citation.sh'), args.target], cwd=ROOT)
    modules = {name: a.load(name, relative, args.target) for name, relative in b.HELPERS.items()}
    old, word, identity, storage, previous = (modules[k] for k in ('old', 'word', 'identity', 'storage', 'previous'))
    original = word.checked_file(APP / '.env', private=True)
    updated = b.updated_environment(original, args.target)
    restore, manifest = a.backup_evidence(args.backup_report, modules)
    require(len(old.tables()) == 35 and b.output(old.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Unexpected tables or unresolved jobs.')
    verify_migrations(old, b.output(b.management('showmigrations', '--plan'), cwd=APP))
    before_health = b.health(RUNNING_RELEASE)
    before_proofs = identity.verify_live(RUNNING_RELEASE, storage)
    worker_before = old.worker_process()
    protected = previous.protected()
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper)
            and b.output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper,
            'Pinned service helper unavailable.')
    readability = identity.source_readability(helper)
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE), 'Installed Word SDK inputs may not change.')
    installed = APP / '.word-sdk' / modules['billing'].SDK_RELEASE
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                   installed / 'build-proof.json', modules['billing'].PIN, inputs)
    # Authenticate the complete historical public-asset population before replacing
    # only the inventory transport for the reviewed new asset transition.
    qualified_static = old.static_inventory(identity, word)
    require(static_inventory(APP / 'staticfiles') == qualified_static, 'Initial static inventory differs.')
    old.static_inventory = lambda _identity, _word: static_inventory(APP / 'staticfiles')
    baseline = snapshot(modules, helper)
    assert_retained_capture(manifest, modules, baseline['storage']['files'])
    result_path = Path(args.result)
    lock = PRIVATE / '.private-readiness-activation.lock'
    state = EVIDENCE / ('activation-state-' + args.target[:12])
    require(result_path.is_absolute() and result_path.resolve() == result_path and result_path.parent == EVIDENCE
            and re.fullmatch(r'typed-voice-activation-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not any(p.exists() or p.is_symlink() for p in (result_path, lock, state)),
            'Unused protected result, shared activation lock and state required.')
    b.run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
    print('Read-only activation checks passed; no source, schema, service or integration changed.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration == SOURCE / DECL
            and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == b.blob(args.target, DECL) == b.blob(commit, DECL),
            'Committed exact target declaration required.')
    b.run(['git', 'merge-base', '--is-ancestor', commit, args.target], cwd=ROOT)
    identity.private_write(lock, {'target': args.target, 'pid': os.getpid(), 'automatic_rollback': False})
    state.mkdir(mode=0o700)
    result = {'complete': False, 'started_at': datetime.now(timezone.utc).isoformat(), 'baseline': BASELINE,
        'served_before': RUNNING_RELEASE, 'target': args.target, 'changed_paths': sorted(changed),
        'backup_report': args.backup_report, 'backup_run_id': manifest['run_id'],
        'restored_backup_run_id': restore['backup_run_id'], 'current_capture_restored': False,
        'provider_calls': 0, 'migration_performed': False, 'before_health': before_health,
        'before_proofs': before_proofs, 'worker_before': worker_before, 'source_readability_before': readability,
        'state_directory': str(state), 'environment_before_sha256': sha(original), 'environment_after_sha256': sha(updated),
        'rollback_policy': 'Stop on failure; retain current data/schema/config and prior source. Reviewed forward repair preferred.'}
    phase = 0
    def checkpoint(stage):
        nonlocal phase
        result['stage'] = stage
        identity.private_write(state / f'phase-{phase:02d}.json', result)
        phase += 1
    try:
        checkpoint('stop_before_source_advance')
        word.systemd('stop', helper)
        b.stopped()
        verify_source(args.target)
        require(b.output(old.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
                'Job appeared during drain; preserve it and inspect.')
        baseline = snapshot(modules, helper)
        result['stopped_before'] = baseline
        assert_retained_capture(manifest, modules, baseline['storage']['files'])
        require(word.checked_file(APP / '.env', private=True) == original, 'Environment changed before stopped capture.')
        archive = subprocess.check_output(['git', 'archive', '--format=tar', BASELINE, 'rebuild'], cwd=ROOT, timeout=60)
        source_manifest = a.retained_source_manifest(archive)
        for name, payload in (('prior-runtime-source.tar', archive), ('prior-environment.env', original)):
            fd = os.open(state / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        identity.private_write(state / 'prior-runtime-manifest.json', source_manifest)
        retain_static(APP / 'staticfiles', state / 'prior-static.tar', baseline['static'])
        checkpoint('advance_stopped_source_ff_only')
        b.stopped()
        b.run(['git', 'merge', '--ff-only', args.target], cwd=ROOT, stdout=subprocess.DEVNULL)
        require(b.git('rev-parse', 'HEAD') == args.target and not b.git('status', '--porcelain', '--untracked-files=no'),
                'Source advance differs from exact target.')
        verify_migrations(old, b.output(b.management('showmigrations', '--plan'), cwd=APP))
        b.run(b.management('check'), cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        after = snapshot(modules, helper)
        unchanged(baseline, after)
        result['stopped_after_source'] = after
        checkpoint('collect_and_install_source_bound_public_assets')
        stage = state / 'static-stage'
        create_static_stage(stage)
        collect_static(stage)
        staged = validate_staged_static(stage, identity.static_sources())
        installed_static = install_static(APP / 'staticfiles', stage, baseline['static'], staged)
        result['static_transition'] = {'before': baseline['static'], 'staged': staged,
            'after': installed_static, 'old_immutable_assets_retained': True,
            'prior_archive': str(state / 'prior-static.tar')}
        baseline = dict(baseline, static=installed_static)
        unchanged(baseline, snapshot(modules, helper))
        result['source_readability'] = identity.source_readability(helper)
        checkpoint('replace_release_setting_only')
        modules['env'].replace_environment(APP / '.env', original, updated)
        checkpoint('start_and_verify_exact_private_release')
        word.systemd('start', helper)
        for attempt in range(45):
            try:
                live_health = b.health(args.target)
                break
            except (subprocess.CalledProcessError, json.JSONDecodeError, RuntimeError):
                time.sleep(1)
        else:
            raise RuntimeError('New private release did not become healthy.')
        result['proofs_after'] = identity.verify_live(args.target, storage)
        result['interfaces_after'] = identity.verify_interfaces()
        worker_after = old.worker_process()
        require(worker_after['systemd_start'] != worker_before['systemd_start']
                and worker_after['kernel_start_utc'] > worker_before['kernel_start_utc'], 'Worker restart not evidenced.')
        result['worker_after'] = worker_after
        unchanged(baseline, snapshot(modules, helper))
        require(word.checked_file(APP / '.env', private=True) == updated and previous.protected() == protected,
                'Configuration or protected services changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                    installed / 'build-proof.json', modules['billing'].PIN, inputs) == artifact,
                'Installed Word SDK changed.')
        b.run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
        result.update(complete=True, health=live_health, existing_rows_unchanged=True,
            existing_schema_indexes_constraints_catalog_unchanged=True, private_files_and_mail_unchanged=True, existing_hashed_assets_retained=True,
            static_delta_source_bound=True,
            backup_units_installed=False, finished_at=datetime.now(timezone.utc).isoformat())
        checkpoint('complete')
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(failure_details(error, result.get('stage')), complete=False, finished_at=datetime.now(timezone.utc).isoformat())
        try:
            word.systemd('stop', helper); b.stopped(); result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False; result['stop_failure_kind'] = type(stop_error).__name__
        identity.private_write(result_path, result)
        raise RuntimeError('Private activation stopped; inspect preserved evidence before a declared repair.') from None
    print('Private code-only activation verified; evidence: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
