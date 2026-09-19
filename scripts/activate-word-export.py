#!/usr/bin/env python3
"""Cited private Word export update; release stamp and three service restarts only.

Run from permanent main after its exact target merge passes citation. The default
is read-only. Execution requires the committed declaration through
scripts/run-ruled-mutation.sh. This code-only activation must preserve all database
rows/schema, original/export/mail bytes, service policies and the installed SDK.
Actual Word fill/review/export evidence follows as a separately declared act.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import types
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
STATE = Path('/var/lib/quillmd')
HERE = Path(__file__).resolve().parent
BASELINE = 'ae6c48bf493a5232ae5016e1086c8e3c6d1e396e'
RUNNING_RELEASE = '6d73c5e9026d974053365468101c2f7921544c6c'
DECL = 'docs/foundation/mutations/20260919-quillmd-word-export-activation.md'
SELF = 'scripts/activate-word-export.py'
CURRENT_MIGRATION = '0014_encounter_service_date'
TABLE_COUNT = 35
MEDIA_TOOLS = ('ffmpeg', 'ffprobe')
RESUME_REPORT = 'word-export-activation-20260919.json'
RESUME_REPORT_SHA256 = '60f7438e07cdbdac1ed7aad9b48e87f47d2ca0204f602af5f54ffe13c85e627d'
RESUME_TARGET = 'e0e92703847cbaf6035e130e512baa886c602eca'
RESUME_LOCK_SHA256 = 'ddfcae0f7b4c1c18a031b9e1ab2ea8b257643927cf6d2b415aaec2b4b1060b1a'
RESUME_ENV_SHA256 = '5e113f4253c109faa9054611ed35d346be12b2e7a654dbc6ea8423662df4fe23'
RESUME_BACKUP = '20260919T153814Z-42c9c0a2'
RESUME_LOCK_SAVED = '.word-export-activation.lock-preserved-20260919-plan'
RECOVERY_PATHS = frozenset((SELF, DECL, 'rebuild/ops/test_word_export_activation.py'))
# These assets were deliberately retained by the completed Word recovery. They
# remain in place and are included in the complete before/after inventory.
RETAINED_STATIC_REPORT = 'word-beta-recovery-20260917-final.json'
RETAINED_STATIC_REPORT_SHA256 = 'af24751df9721d98cdbd84415247f806cd5fc0274717b945e2b4c8609f227fef'
RETAINED_STATIC_SOURCE = 'f2012ea0030b3e5b9ca59ea7023f4da1263a3c69:rebuild/static/app.css'
RETAINED_STATIC = {
    'app.39d54d0ccd1a.css': {
        'directory': False, 'mode': 0o644, 'size': 20621,
        'sha256': '210b3ed9b890243501546ddd98aa82b530cf39af2e1f076199e1c5e288649c63'},
    'app.39d54d0ccd1a.css.gz': {
        'directory': False, 'mode': 0o644, 'size': 4708,
        'sha256': 'faa32aff2ce6b7034f07110112c42e4a3f00307ce8f5a55f3d0d0c7dd54ba022'},
}
# Complete served-to-base payload, including earlier account/mail helper repairs.
PREMERGED_PATHS = {
    'docs/foundation/mutations/20260919-quillmd-account-checks-run2.md',
    'docs/foundation/mutations/20260919-quillmd-account-checks.md',
    'docs/foundation/mutations/20260919-quillmd-word-genuine-fixtures.md',
    'docs/rebuild/CHECKPOINT.md',
    'docs/rebuild/activation-judged.md',
    'docs/rebuild/design.md',
    'docs/rebuild/owner-actions.md',
    'docs/rebuild/verification.md',
    'docs/rebuild/word-review/README.txt',
    'docs/rebuild/word-review/word-acceptance-checklist.md',
    'rebuild/build-word-evidence.mjs',
    'rebuild/core/management/commands/verify_live.py',
    'rebuild/core/tests/test_audio_submission.py',
    'rebuild/core/tests/test_billing_boundary_regressions.py',
    'rebuild/documents/layout.py',
    'rebuild/documents/service.py',
    'rebuild/documents/test_layout.py',
    'rebuild/documents/wm_qualification.py',
    'rebuild/identity-browser.mjs',
    'rebuild/ops/account_mail.py',
    'rebuild/ops/private_mail.py',
    'rebuild/ops/private_storage.py',
    'rebuild/ops/source_module.py',
    'rebuild/ops/test_account_mail.py',
    'rebuild/ops/test_audio_submission_activation.py',
    'rebuild/ops/test_billing_activation.py',
    'rebuild/ops/test_billing_resume.py',
    'rebuild/ops/test_confined_select.py',
    'rebuild/ops/test_os_identity_static.py',
    'rebuild/ops/test_plaintext_reap.py',
    'rebuild/ops/test_private_mail.py',
    'rebuild/ops/test_recording_limit_activation.py',
    'rebuild/ops/test_recording_repair_activation.py',
    'rebuild/ops/test_service_date_activation.py',
    'rebuild/ops/test_source_module.py',
    'rebuild/ops/test_storage_migration.py',
    'rebuild/ops/test_update_guard.py',
    'rebuild/ops/test_word_activation.py',
    'rebuild/ops/test_word_recovery.py',
    'rebuild/private-beta-browser.mjs',
    'rebuild/verify-private-accounts.mjs',
    'rebuild/verify-private-release.mjs',
    'scripts/activate-audio-submission.py',
    'scripts/activate-recording-repair.py',
    'scripts/build-word-review-package.py',
    'scripts/ci/verify-fresh.sh',
}
# Only these reviewed additions may enter from this milestone.
MILESTONE_PATHS = {
    'docs/foundation/mutations/20260919-quillmd-word-export-activation.md',
    'docs/foundation/mutations/20260919-quillmd-word-export-verification.md',
    'rebuild/core/tests/test_wm_workflow.py',
    'rebuild/ops/test_word_export_activation.py',
    'rebuild/test-word-evidence-scenarios.mjs',
    'rebuild/word-evidence-scenarios.mjs',
    'scripts/activate-word-export.py',
    'scripts/build-verified-word-review.py',
    'scripts/ci/prepare-word.sh',
}
ALLOWED = PREMERGED_PATHS | MILESTONE_PATHS
FORBIDDEN = (
    "rebuild/core/migrations", "rebuild/deploy", "rebuild/quillmd",
    "rebuild/documents/sdk_word", "rebuild/documents/sdk_sandbox.py",
    "rebuild/ops/service_launcher.py", "rebuild/requirements.txt",
    "rebuild/static", "rebuild/templates",
)

UNITS = ['quillmd-fresh-' + surface + '.service' for surface in ('doctor', 'admin', 'worker')]
PSQL = ['docker', 'exec', 'quillmd-fresh-postgres', 'psql', '-U', 'quillmd_fresh',
        '-d', 'quillmd_fresh', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c']


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def output(command, **kwargs):
    kwargs.setdefault('timeout', 600)
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    kwargs.setdefault('timeout', 600)
    return subprocess.run(command, check=True, **kwargs)


def load(name, relative):
    """Read exact reviewed source; a matching mtime/size must not select stale pyc."""
    path = ROOT / relative
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module  # inspect.getsource in private_storage needs its module.
    exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
    return module


def validate_changed(changed):
    require(changed <= ALLOWED and DECL in changed and SELF in changed
            and 'rebuild/documents/layout.py' in changed
            and 'rebuild/documents/service.py' in changed,
            'Target differs from the complete reviewed Word export change set.')
    require(not any(path == prefix or path.startswith(prefix + '/')
                    for path in changed for prefix in FORBIDDEN),
            'Schema, installed runtime, units, settings, UI and dependency changes are not declared.')


def updated_environment(original, target):
    require(re.fullmatch('[a-f0-9]{40}', target), 'Use a full target revision.')
    old_line = ('QUILLMD_RELEASE_SHA=' + RUNNING_RELEASE).encode()
    require(original.splitlines().count(old_line) == 1
            and sum(line.startswith(b'QUILLMD_RELEASE_SHA=')
                    for line in original.splitlines()) == 1,
            'Expected exactly one current private release setting.')
    updated = re.sub(rb'(?m)^' + re.escape(old_line) + rb'$',
                     ('QUILLMD_RELEASE_SHA=' + target).encode(), original)
    require(updated != original and updated.count(b'\n') == original.count(b'\n'),
            'Release replacement did not apply cleanly.')
    return updated


def verify_migration_plan(plan):
    rows = [line.strip() for line in plan.splitlines() if line.strip()]
    parsed = [re.fullmatch(r'\[X\][ \t]+([a-z_][a-z_0-9]*\.[a-z_0-9]+)', row) for row in rows]
    require(rows and all(parsed) and 'core.' + CURRENT_MIGRATION in [match.group(1) for match in parsed if match],
            'The migration plan is empty, incomplete or contains unapplied operations.')


def stopped_services():
    for unit in UNITS:
        require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0',
                'Recovery requires all three private services stopped with no main process.')


def load_resume_report(path, word):
    require(Path(path) == PRIVATE / RESUME_REPORT and Path(path).resolve() == Path(path),
            'Only the recorded failed Word activation can be resumed.')
    payload = word.checked_file(Path(path), private=True)
    require(sha(payload) == RESUME_REPORT_SHA256, 'Failed activation evidence changed.')
    report = json.loads(payload)
    require(report.get('complete') is False and report.get('failure_kind') == 'RuntimeError'
            and report.get('stage') == 'verifying_no_schema_work_is_pending'
            and report.get('failure_services_stopped') is True
            and report.get('target') == RESUME_TARGET
            and report.get('running_release_before') == RUNNING_RELEASE
            and report.get('previous_head') == BASELINE
            and report.get('provider_calls') == 0 and report.get('migration') is None
            and report.get('backup_run_id') == RESUME_BACKUP,
            'The failed activation is outside this bounded pre-environment recovery.')
    required = ('schema_before', 'constraints_before', 'indexes_before', 'database_before',
                'clinical_before', 'storage_before', 'static_before', 'artifact', 'worker_before',
                'helper_image', 'media_tools', 'retained_reports_before', 'backup_report')
    require(all(report.get(name) for name in required)
            and len(report['database_before']) == TABLE_COUNT,
            'Failed activation lacks the complete preservation baseline.')
    return report


def compare_resume_state(report, observed):
    # JSON round-trip normalizes SQL tuples to their original report arrays;
    # no key, column, row or value is removed from either side.
    require(set(observed) == {'schema_before', 'constraints_before', 'indexes_before', 'database_before',
                             'clinical_before', 'storage_before', 'static_before', 'artifact',
                             'helper_image', 'media_tools'}, 'Recovery inspection is incomplete.')
    for name, value in observed.items():
        require(json.loads(json.dumps(value)) == report[name], 'Recovery state changed: ' + name)


def verify_resume_state(report, word, storage, identity, artifact, helper, tools, env_before, backup_report):
    stopped_services()
    require(sha(env_before) == RESUME_ENV_SHA256, 'Recovery environment differs from the verified stopped state.')
    require(str(Path(backup_report).absolute()) == report['backup_report'], 'Recovery must use the same backup proof.')
    lock = PRIVATE / '.word-export-activation.lock'
    require(sha(word.checked_file(lock, private=True)) == RESUME_LOCK_SHA256,
            'The failed activation lock changed.')
    saved = PRIVATE / RESUME_LOCK_SAVED
    require(not saved.exists() and not saved.is_symlink(), 'Preserved failed lock destination already exists.')
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Recovery cannot replay pending provider work.')
    names = tables()
    require(set(names) == set(report['database_before']), 'Recovery table population changed.')
    observed = {'schema_before': schema(), 'constraints_before': constraints(), 'indexes_before': indexes(),
                'database_before': fingerprints(names), 'clinical_before': clinical_counts(),
                'storage_before': {name: storage.inventory(STATE / name) for name in ('files', 'mail')},
                'static_before': static_inventory(identity, word), 'artifact': artifact,
                'helper_image': helper, 'media_tools': tools}
    compare_resume_state(report, observed)
    require(retained_unchanged(report['retained_reports_before'], word.retained_reports()),
            'Retained evidence changed after the failed activation.')
    stopped_services()
    return observed


def preserve_failed_lock(word):
    """Exclusive same-directory relocation, retaining the original lock inode/bytes."""
    lock, saved = PRIVATE / '.word-export-activation.lock', PRIVATE / RESUME_LOCK_SAVED
    payload = word.checked_file(lock, private=True)
    require(sha(payload) == RESUME_LOCK_SHA256, 'Failed lock changed before preservation.')
    before = lock.lstat()
    # link() refuses an existing destination. A transient second link remains
    # wholly inside operator-private evidence, followed immediately by unlink.
    os.link(lock, saved, follow_symlinks=False)
    preserved, current = saved.lstat(), lock.lstat()
    require((preserved.st_dev, preserved.st_ino) == (current.st_dev, current.st_ino)
            == (before.st_dev, before.st_ino) and saved.read_bytes() == payload,
            'Failed lock identity changed during preservation.')
    lock.unlink()
    require(sha(word.checked_file(saved, private=True)) == RESUME_LOCK_SHA256,
            'Preserved failed lock differs from its authenticated bytes.')
    return {'path': str(saved), 'sha256': RESUME_LOCK_SHA256}


def static_inventory(identity, word):
    """Keep the first-install inventory guards and authenticate two retained assets.

    The identity activator predates the Word recovery and only recognizes the
    current manifest. Reusing it hid two deliberately preserved old hashes from
    its allowed set. This local checker adds exactly those authenticated files;
    unknown files, ownership/link defects and manifest changes still refuse.
    """
    root = APP / 'staticfiles'
    require(root.resolve() == root, 'Static output path must be canonical.')
    rows = {}
    for path in [root, *sorted(root.rglob('*'))]:
        info = path.lstat()
        require(info.st_uid == os.getuid() and not stat.S_ISLNK(info.st_mode),
                'Static output must be operator-owned and free of symlinks.')
        relative = '.' if path == root else str(path.relative_to(root))
        row = {'mode': stat.S_IMODE(info.st_mode), 'device': info.st_dev, 'inode': info.st_ino}
        if stat.S_ISDIR(info.st_mode):
            row['kind'] = 'directory'
        else:
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= 16 * 1024 * 1024,
                    'Static output contains a nonregular, linked or oversized object.')
            row.update(kind='file', size=info.st_size, sha256=sha(path.read_bytes()))
        rows[relative] = row
        require(len(rows) <= 10000, 'Static output inventory exceeds the bounded scope.')
    manifest = json.loads((root / 'staticfiles.json').read_bytes())
    inputs = identity.static_sources()
    require(isinstance(manifest.get('paths'), dict) and set(manifest['paths']) == set(inputs),
            'Static manifest differs from reviewed application and installed OTP assets.')
    allowed = {'staticfiles.json'}
    allowed_dirs = {'.'}
    for source, compiled in manifest['paths'].items():
        original = Path(source)
        pattern = re.escape(str(original.with_suffix(''))) + r'\.[a-f0-9]{12}' + re.escape(original.suffix)
        require(isinstance(compiled, str) and re.fullmatch(pattern, compiled),
                'Static manifest includes an unexpected path.')
        require((root / source).read_bytes() == inputs[source].read_bytes(),
                'Collected static input differs from current application source.')
        require(compiled in rows and rows[compiled]['kind'] == 'file', 'Compiled static asset is missing.')
        for path in (source, compiled):
            allowed.update((path, path + '.gz', path + '.br'))
            allowed_dirs.update(str(parent) for parent in Path(path).parents)
    proof_bytes = word.checked_file(PRIVATE / RETAINED_STATIC_REPORT, private=True)
    require(sha(proof_bytes) == RETAINED_STATIC_REPORT_SHA256, 'Retained static provenance report changed.')
    proof = json.loads(proof_bytes)
    require(proof.get('complete') is True, 'Retained static provenance did not complete.')
    for name, expected in RETAINED_STATIC.items():
        require(proof.get('static_before', {}).get(name) == expected
                and proof.get('static_after', {}).get(name) == expected,
                'Retained static asset was not preserved by the historical recovery.')
        found = rows.get(name, {})
        require(found.get('kind') == 'file'
                and all(found.get(key) == expected[key] for key in ('mode', 'size', 'sha256')),
                'Retained static asset differs from its exact historical bytes or mode.')
        allowed.add(name)
    original_css = subprocess.check_output(['git', 'show', RETAINED_STATIC_SOURCE], cwd=ROOT)
    require((root / 'app.39d54d0ccd1a.css').read_bytes() == original_css
            and gzip.decompress((root / 'app.39d54d0ccd1a.css.gz').read_bytes()) == original_css,
            'Retained static assets differ from the initial fresh implementation.')
    require(all(name in (allowed_dirs if row['kind'] == 'directory' else allowed) for name, row in rows.items()),
            'Static output contains an object outside the reviewed public asset set.')
    return rows


def sha(data):
    return hashlib.sha256(data).hexdigest()


def schema():
    sql = """SELECT coalesce(jsonb_agg(to_jsonb(c) ORDER BY table_name,ordinal_position),'[]') FROM
      (SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default,numeric_precision,numeric_scale
       FROM information_schema.columns WHERE table_schema='public') c"""
    return json.loads(output(PSQL + [sql]))


def tables():
    names = output(PSQL + ["SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"]).splitlines()
    require(all(re.fullmatch('[a-z_][a-z_0-9]*', name) for name in names), 'Unexpected table name.')
    return names


def fingerprints(names):
    """Row fingerprints per table. No comparable= form: a code-only activation declares NOTHING may differ, so there is
    nothing to subtract, and offering a subtraction would be offering an excuse."""
    rows = {}
    for table in names:
        data = subprocess.check_output(
            PSQL + [f'COPY (SELECT (to_jsonb(t))::text AS value FROM "{table}" t ORDER BY value) TO STDOUT'], timeout=600)
        rows[table] = {'sha256': sha(data), 'rows': len(data.splitlines())}
    return rows


def constraints():
    sql = """SELECT coalesce(jsonb_agg(jsonb_build_array(c.conrelid::regclass::text, c.conname, c.contype::text, c.confrelid::regclass::text,
                 pg_get_constraintdef(c.oid)) ORDER BY c.conrelid::regclass::text, c.conname),'[]')
             FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public'"""
    return [tuple(row) for row in json.loads(output(PSQL + [sql]))]


def indexes():
    return [tuple(row) for row in json.loads(output(PSQL + [
        "SELECT coalesce(jsonb_agg(jsonb_build_array(tablename,indexname,indexdef) ORDER BY tablename,indexname),'[]') FROM pg_indexes WHERE schemaname='public'"]))]


def clinical_counts():
    """The row counts a deploy must never move. Named separately from the fingerprints because a fingerprint answers
    'did anything change' and this answers 'did a document, a visit or a signature change', which is the question
    somebody will ask first."""
    return {name: int(output(PSQL + [sql])) for name, sql in (
        ('encounters', 'SELECT count(*) FROM core_encounter'),
        ('finalized', "SELECT count(*) FROM core_encounter WHERE status='finalized'"),
        ('jobs', 'SELECT count(*) FROM core_job'),
        ('usage_rows', 'SELECT count(*) FROM core_usage'),
        ('provider_receipts', 'SELECT count(*) FROM core_providerreceipt'),
        ('audit_events', 'SELECT count(*) FROM core_auditevent'))}


def media_tools():
    """Preserve the existing recording tools across the unrelated Word restart."""
    found = {}
    for name in MEDIA_TOOLS:
        path = output(['bash', '-lc', 'command -v ' + name + ' || true'])
        require(path.startswith('/') and os.access(path, os.X_OK), name + ' is not installed, so the reviewed submission path cannot run.')
        found[name] = {'path': path, 'version': output([path, '-version']).splitlines()[0][:120]}
    return found


def worker_process():
    """Identify the worker by START TIME, COMMAND and SERVICE MEMBERSHIP, not by PID.

    A PID is reused, and a PID read from one place and checked in another describes whatever happens to hold it now.
    These four facts together cannot be satisfied by a stale or unrelated process: systemd's own record of when it
    started the main process, the kernel's record of when that PID started, the command it is running, and the cgroup
    that says it belongs to this unit.
    """
    unit = 'quillmd-fresh-worker.service'
    pid = int(output(['systemctl', 'show', unit, '--property=MainPID', '--value']))
    require(pid > 0, 'The worker has no main process.')
    cgroup = Path(f'/proc/{pid}/cgroup').read_text().strip()
    require(unit in cgroup, 'The worker PID is not a member of its own service cgroup.')
    command = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\x00', b' ').decode('utf-8', 'replace').strip()
    # ⚠️ IT IS NOT THE LAUNCHER'S COMMAND LINE, AND ASSERTING THAT WAS WRONG. service_launcher.py EXECS the surface,
    # replacing itself, so the main process reads `<venv>/bin/python <app>/manage.py worker` — measured on the live
    # service, which is why this is checked against the running host and not only against the source. The interpreter
    # path is asserted too: it ties the process to the deployed tree rather than to any python that happens to be here.
    require(str(APP / '.venv/bin/python') in command and 'manage.py' in command and command.split()[-1] == 'worker',
            'The worker main process is not the reviewed worker command: ' + command[:120])
    # /proc/<pid>/stat field 22 is start time in clock ticks since boot; boot time comes from /proc/stat.
    fields = Path(f'/proc/{pid}/stat').read_text().rsplit(') ', 1)[1].split()
    ticks = int(fields[19])
    boot = next(int(line.split()[1]) for line in Path('/proc/stat').read_text().splitlines() if line.startswith('btime'))
    started = datetime.fromtimestamp(boot + ticks / os.sysconf('SC_CLK_TCK'), timezone.utc)
    systemd_started = output(['systemctl', 'show', unit, '--property=ExecMainStartTimestamp', '--value'])
    return {'pid': pid, 'cgroup': cgroup, 'command': command, 'kernel_start_utc': started.isoformat(),
            'systemd_start': systemd_started, 'unit': unit}


def retained_unchanged(before, now):
    """Reports retained before the act are unchanged; reports other sessions add meanwhile are allowed."""
    return all(now.get(name) == row for name, row in before.items())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--resume-report', help='Only the pinned pre-environment failure may resume while stopped.')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Use permanent shared main.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'Use the full merge SHA.')
    # HEAD IS THE TARGET, not the previous head: the tree is fast-forwarded before this runs, so the declaration the
    # ruled-mutation gate must find is tracked and committed in this tree. BASELINE is still asserted — as the commit
    # the tree came FROM — because the range being judged runs from the RUNNING RELEASE and must contain both.
    require(output(['git', 'branch', '--show-current']) == 'main'
            and output(['git', 'rev-parse', 'HEAD']) == args.target
            and output(['git', 'rev-parse', 'origin/main']) == args.target, 'Unexpected source release.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    run(['git', 'merge-base', '--is-ancestor', BASELINE, args.target])
    run(['git', 'merge-base', '--is-ancestor', RUNNING_RELEASE, BASELINE])
    # The declaration must be visible HERE, in this tree, or the gate that reads it cannot fire.
    run(['git', 'ls-files', '--error-unmatch', DECL], stdout=subprocess.DEVNULL)
    changed = set(output(['git', 'diff', '--name-only', RUNNING_RELEASE, args.target]).splitlines())
    validate_changed(changed)
    require(set(output(['git', 'diff', '--name-only', RUNNING_RELEASE, BASELINE]).splitlines())
            == PREMERGED_PATHS, 'Previously merged payload differs from its reviewed path inventory.')
    require(output(['git', 'diff', '--name-only', RUNNING_RELEASE, args.target, '--', 'rebuild/core/migrations']) == '',
            'This activation declares NO migration; the target adds one.')
    require(subprocess.check_output(['git', 'show', args.target + ':' + SELF]) == (HERE.parent / SELF).read_bytes(),
            'Activator differs from the reviewed target.')
    helpers = {'word': 'scripts/activate-word-beta.py', 'identity': 'scripts/activate-os-identity.py',
               'previous': 'scripts/update-private-beta.py', 'storage': 'rebuild/ops/private_storage.py',
               'billing': 'scripts/activate-billing-policy.py'}
    modules = {}
    for name, relative in helpers.items():
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative]) == (ROOT / relative).read_bytes(),
                'Existing qualified helper changed.')
        modules[name] = load('word_export_activation_' + name, relative)
    word, identity, previous, storage, billing = (modules[k] for k in ('word', 'identity', 'previous', 'storage', 'billing'))
    resume = load_resume_report(args.resume_report, word) if args.resume_report else None
    if resume:
        run(['git', 'merge-base', '--is-ancestor', RESUME_TARGET, args.target])
        recovery_changed = set(output(['git', 'diff', '--name-only', RESUME_TARGET, args.target]).splitlines())
        require(recovery_changed == RECOVERY_PATHS,
                'Recovery target must contain only the reviewed parser, guards, tests and declaration repair.')
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'A merged PR is required.')
    if resume:
        stopped_services()
        worker_before = resume['worker_before']
    else:
        health = [json.loads(output(['curl', '--fail', '--silent', '--max-time', '5', f'http://127.0.0.1:{p}/health/']))
                  for p in (9130, 9131)]
        require(all(h.get('release') == RUNNING_RELEASE and h.get('data_mode') == 'synthetic-only' for h in health),
                'The private services must be up on the recorded running release, synthetic-only.')
        worker_before = worker_process()
    tools = media_tools()
    backup = previous.validate_restore_report(args.backup_report)
    require(backup.get('decrypted_files_written') == 0 and backup.get('restore_database_on_tmpfs_without_swap') is True,
            'The restore proof must come from the plaintext-free restore check.')
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Unresolved jobs require inspection; never replay a provider request.')
    require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + CURRENT_MIGRATION + "'"]) == '1',
            'Expected the fresh schema through core 0014.')
    latest = output(PSQL + ["SELECT name FROM django_migrations WHERE app='core' ORDER BY id DESC LIMIT 1"])
    require(latest == CURRENT_MIGRATION, 'The schema is not at the migration this activation was reviewed against: ' + latest)
    names = tables()
    require(len(names) == TABLE_COUNT, 'Expected the current tables.')
    live_rows = sum(int(output(PSQL + [f'SELECT count(*) FROM "{t}"'])) for t in names)
    require(live_rows == backup.get('row_count'), 'The restore proof does not cover the current rows; take a fresh backup first.')
    protected = previous.protected()
    retained = word.retained_reports()
    env_before = word.checked_file(APP / '.env', private=True)
    env_after = updated_environment(env_before, args.target)
    installed = APP / '.word-sdk' / billing.SDK_RELEASE
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE) == word.expected_inputs(RUNNING_RELEASE),
            'Compiled Word inputs must not change.')
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                    installed / 'build-proof.json', billing.PIN, inputs)
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper)
            and output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper,
            'Pinned local helper required.')
    for name in ('files', 'mail'):
        storage.inventory(STATE / name)
    for unit in UNITS:
        require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(),
                'Installed service policy differs from reviewed source.')
    if resume:
        verify_resume_state(resume, word, storage, identity, artifact, helper, tools, env_before, args.backup_report)
    else:
        identity.verify_live(RUNNING_RELEASE, storage)
    static_before = static_inventory(identity, word)
    result_path = Path(args.result)
    lock = PRIVATE / '.word-export-activation.lock'
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'word-export-activation-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not result_path.is_symlink()
            and (resume is not None or (not lock.exists() and not lock.is_symlink())),
            'Choose unused private operation evidence; a prior lock needs inspection.')
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Word export activation preflight passed: cited code, restored current state, no pending jobs; '
          'no migration, SDK/static installation or provider operation.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration.name == Path(DECL).name
            and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == subprocess.check_output(['git', 'show', args.target + ':' + DECL])
            == subprocess.check_output(['git', 'show', commit + ':' + DECL]), 'Committed absolute declaration required.')
    run(['git', 'merge-base', '--is-ancestor', commit, args.target])
    result = {'complete': False, 'previous_head': BASELINE, 'running_release_before': RUNNING_RELEASE,
              'target': args.target, 'started_at': datetime.now(timezone.utc).isoformat(), 'provider_calls': 0,
              'migration': None, 'media_tools': tools, 'worker_before': worker_before,
              'backup_report': args.backup_report, 'backup_run_id': backup.get('backup_run_id'),
              'artifact': artifact, 'helper_image': helper, 'retained_reports_before': retained,
              'changed_paths': sorted(changed), 'static_before': static_before,
              'stage': 'stopping_private_services'}
    try:
        if resume:
            result.update(stage='authenticating_recovery_before_lock_preservation',
                          resumed_report=str(PRIVATE / RESUME_REPORT), resumed_report_sha256=RESUME_REPORT_SHA256)
            require(load_resume_report(args.resume_report, word) == resume, 'Failed report changed before recovery.')
            verify_resume_state(resume, word, storage, identity, artifact, helper, tools,
                                word.checked_file(APP / '.env', private=True), args.backup_report)
            result['preserved_failed_lock'] = preserve_failed_lock(word)
        identity.private_write(lock, {'target': args.target, 'pid': os.getpid()})
        result['stage'] = 'stopping_private_services'
        word.systemd('stop', helper)
        for unit in UNITS:
            require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                    and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0', 'Service did not stop.')
        require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
                'Job appeared before stop.')
        old_tables = tables()
        require(old_tables == names, 'Tables changed before the act.')
        result['schema_before'] = schema()
        result['constraints_before'], result['indexes_before'] = constraints(), indexes()
        result['database_before'] = fingerprints(old_tables)
        result['clinical_before'] = clinical_counts()
        result['storage_before'] = {name: storage.inventory(STATE / name) for name in ('files', 'mail')}
        if resume:
            compare_resume_state(resume, {name: result[name] for name in (
                'schema_before', 'constraints_before', 'indexes_before', 'database_before', 'clinical_before',
                'storage_before', 'static_before', 'artifact', 'helper_image', 'media_tools')})
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed.')
        result['stage'] = 'verifying_no_schema_work_is_pending'
        # A code-only activation must find NOTHING to migrate. `showmigrations --plan` listing an unapplied entry, or
        # `makemigrations --check` wanting one, means the reviewed code and the live schema disagree — and the right
        # response is to stop, not to apply something nobody declared.
        credentials = PRIVATE / 'db-role-secrets/fresh-db-roles.json'
        word.checked_file(credentials, private=True, limit=16384)
        plan = output([str(APP / '.venv/bin/python'), '-B', str(APP / 'ops/with_db_role.py'), '--credentials',
                       str(credentials), '--source', str(APP), '--role', 'migrator', '--', 'showmigrations', '--plan'], cwd=APP)
        verify_migration_plan(plan)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'makemigrations', '--check', '--dry-run'], cwd=APP)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'check'], cwd=APP)
        require(static_inventory(identity, word) == static_before, 'Static files changed before restart.')
        result['source_readability'] = identity.source_readability(helper)
        result['stage'] = 'replacing_release_line'
        pending = PRIVATE / ('word-export-env-' + args.target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed concurrently.')
        pending.replace(APP / '.env')
        require(word.checked_file(APP / '.env', private=True) == env_after, 'Environment differs from release-only update.')
        result['stage'] = 'starting_and_verifying'
        word.systemd('start', helper)
        for attempt in range(60):
            try:
                health = [json.loads(output(['curl', '--fail', '--silent', '--max-time', '5',
                                             f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
                if all(h.get('release') == args.target and h.get('data_mode') == 'synthetic-only' for h in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Release health failed.')
        result['proofs'] = identity.verify_live(args.target, storage)
        result['interfaces'] = identity.verify_interfaces()
        worker_after = worker_process()
        require(worker_after['systemd_start'] != worker_before['systemd_start']
                and worker_after['kernel_start_utc'] > worker_before['kernel_start_utc'],
                'The worker did not actually restart onto the reviewed code.')
        result['worker_after'] = worker_after
        result['media_tools_after'] = media_tools()
        require(result['media_tools_after'] == tools, 'The media tools changed during the activation.')
        # The declared delta is EMPTY. Everything below asserts that, and any difference is the finding.
        require(tables() == old_tables, 'A table was created or dropped.')
        require(schema() == result['schema_before'], 'The schema changed.')
        require(constraints() == result['constraints_before'], 'A constraint changed.')
        require(indexes() == result['indexes_before'], 'An index changed.')
        require(fingerprints(old_tables) == result['database_before'], 'Application data changed.')
        require(clinical_counts() == result['clinical_before'], 'A document, job, usage or audit count moved.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'],
                'Private bytes changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                     installed / 'build-proof.json', billing.PIN, inputs) == artifact,
                'Word runtime changed.')
        require(static_inventory(identity, word) == static_before, 'Static files changed during activation.')
        require(retained_unchanged(retained, word.retained_reports()) and previous.protected() == protected,
                'Retained or shared resources changed.')
        for unit in UNITS:
            require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(),
                    'Unit policy changed.')
        if resume:
            require(load_resume_report(args.resume_report, word) == resume,
                    'Original failure evidence changed during recovery.')
            require(sha(word.checked_file(PRIVATE / RESUME_LOCK_SAVED, private=True)) == RESUME_LOCK_SHA256,
                    'Original failed lock changed during recovery.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', health=health, all_existing_rows_identical=True,
                      no_schema_delta=True, all_private_files_and_mail_identical=True, protected_containers=protected,
                      environment_before_sha256=sha(env_before), environment_after_sha256=sha(env_after),
                      finished_at=datetime.now(timezone.utc).isoformat())
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__,
                      finished_at=datetime.now(timezone.utc).isoformat())
        # Fail closed: services stay stopped until the recorded state is inspected.
        try:
            word.systemd('stop', helper)
            result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False
            result['stop_failure_kind'] = type(stop_error).__name__
        if not result_path.exists():
            identity.private_write(result_path, result)
        else:
            identity.private_write(result_path.with_name(result_path.stem + '-publication-failure.json'), result)
        raise
    print('Word export activation completed: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
