#!/usr/bin/env python3
"""Resume only the pinned, stopped 20260920 private activation after cache-mode diagnosis.

Default is read-only. No migration runs; no prior data or failure history is
rewritten. Execution repairs only three exact nonsecret generated cache modes,
advances stopped source, updates only the release stamp and verifies the runtime.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import marshal
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import types

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
EVIDENCE = PRIVATE / 'overnight-completion-20260920'
SOURCE = Path(__file__).resolve().parents[1]
FAILED_TARGET = '8fd222dad206cc76f79580753567a802cdbe3b33'
SELF = 'scripts/resume-private-operations.py'
TEST = 'rebuild/ops/test_private_operations_resume.py'
DECL = 'docs/foundation/mutations/20260920-quillmd-private-operations-resume.md'
REPORT = EVIDENCE / 'private-operations-activation-01.json'
REPORT_SHA256 = '1e0d6a67e7095b4a9f85037a9d231d4431dced7122d63eefaf8d8b90cd8e4eee'
FAILED_LOCK = PRIVATE / '.private-operations-activation.lock'
FAILED_LOCK_SHA256 = 'b126f89db91941f132439234cc328e51fabcaf9ea6142c0b65a880bc4348d034'
PRIOR_STATE = EVIDENCE / 'activation-state-8fd222dad206'
CACHES = {
    'source_module': ('8849dfd56c389bed9e160a795b498c348f2aece678895fa8ec41df8e5dde65fb', 2433,
                      '2b8b7f3fe9551d374bdb7b68e392ea4cdb500a144cc327894fcd4682aaf6c836'),
    'private_storage': ('0992638389b722ea78ca00837a1deade3009bc7e014fe3826e18e6ee84023fb5', 33973,
                        'dd4f7502193d0e3b5fe99ca9a5ab356686557e3e26d695f833148ce5d724054b'),
    'email_activation': ('d42366afd7d3f3250a874835b2b0877da396db276289da50de24bb14e415b414', 8244,
                         '66ad2090ad58823e5313d098ef9be4afa105409eaa606569e3e5248b9d9df05b'),
}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def normalized(value):
    return json.loads(json.dumps(value, sort_keys=True))


def validate_changed(paths):
    require(set(paths) == {SELF, TEST, DECL}, 'Resume target must change only the exact resume tool, tests and declaration.')


def load(relative, target, name):
    path = ROOT / relative
    data = path.read_bytes()
    for commit in (FAILED_TARGET, target):
        require(data == subprocess.check_output(['git', 'show', commit + ':' + relative], cwd=ROOT, timeout=60),
                'Reused reviewed helper changed.')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


def failure_report(word):
    data = word.checked_file(REPORT, private=True)
    require(sha(data) == REPORT_SHA256, 'Pinned failed activation record changed.')
    report = json.loads(data)
    require(report.get('complete') is False and report.get('failure_kind') == 'RuntimeError'
            and report.get('failure_services_stopped') is True and report.get('target') == FAILED_TARGET
            and report.get('stage') == 'apply_only_declared_reconciliation_guard'
            and report.get('provider_calls') == 0 and report.get('state_directory') == str(PRIOR_STATE)
            and report.get('stopped_before') and report.get('stopped_after_migration'),
            'Only the recorded stopped post-migration pre-environment failure can resume.')
    return report


def check_state(report, current, act, expected_body):
    require(normalized(current) == report['stopped_after_migration'],
            'Current state differs from the exact preserved post-migration failure.')
    act.validate_after(normalized(report['stopped_before']), normalized(current), expected_body)


def cache_inventory(mode, *, app=APP):
    """Read the exact diagnosed objects without following links or broadening scope."""
    result = {}
    for name, (expected_hash, expected_size, source_hash) in CACHES.items():
        path = app / 'ops/__pycache__' / (name + '.cpython-312.pyc')
        source = app / 'ops' / (name + '.py')
        require(path.resolve() == path and source.resolve() == source, 'Cache/source path may not contain symlinks.')
        require(sha(source.read_bytes()) == source_hash, 'A diagnosed cache source changed.')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() == 1000 and info.st_gid == 1000
                    and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == mode and info.st_size == expected_size,
                    'Cache owner, links, mode or size differs from the diagnosed nonsecret object.')
            data = os.read(fd, expected_size + 1)
            require(sha(data) == expected_hash, 'Diagnosed cache bytes changed.')
            require(marshal.loads(data[16:]) == compile(source.read_bytes(), str(source), 'exec'),
                    'Pinned generated cache is not the exact compiled nonsecret source.')
            result[str(path.relative_to(app))] = {'sha256': sha(data), 'size': info.st_size,
                'uid': info.st_uid, 'gid': info.st_gid, 'mode': stat.S_IMODE(info.st_mode),
                'device': info.st_dev, 'inode': info.st_ino, 'mtime_ns': info.st_mtime_ns}
        finally:
            os.close(fd)
    return result


def repair_cache_modes(before, *, app=APP):
    require(cache_inventory(0o600, app=app) == before, 'Cache state changed before repair.')
    for relative, expected in before.items():
        require(relative in {'ops/__pycache__/' + name + '.cpython-312.pyc' for name in CACHES}, 'Undeclared cache repair.')
        fd = os.open(app / relative, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            require(info.st_dev == expected['device'] and info.st_ino == expected['inode']
                    and info.st_nlink == 1 and stat.S_IMODE(info.st_mode) == 0o600
                    and info.st_uid == info.st_gid == 1000 and info.st_mtime_ns == expected['mtime_ns']
                    and sha(os.read(fd, expected['size'] + 1)) == expected['sha256'], 'Cache changed during repair.')
            os.fchmod(fd, 0o644)
            os.fsync(fd)
        finally:
            os.close(fd)
    after = cache_inventory(0o644, app=app)
    require({k: {**v, 'mode': 0o600} for k, v in after.items()} == before, 'Cache repair changed more than the three modes.')
    return after


def exact_lock(word):
    data = word.checked_file(FAILED_LOCK, private=True)
    require(sha(data) == FAILED_LOCK_SHA256, 'Original failed-operation lock changed.')
    info = FAILED_LOCK.lstat()
    return data, {'device': info.st_dev, 'inode': info.st_ino, 'bytes': info.st_size, 'mode': stat.S_IMODE(info.st_mode)}


def private_bytes(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(re.fullmatch('[a-f0-9]{40}', args.target) and args.target != FAILED_TARGET, 'Exact new full merged target required.')
    require(SOURCE.resolve() == SOURCE and SOURCE.is_relative_to(ROOT / '.worktrees'), 'Run the reviewed resume from its worktree.')
    act = load('scripts/activate-private-operations.py', args.target, 'resume_original_activator')
    require(act.git('rev-parse', 'HEAD') == FAILED_TARGET and act.git('branch', '--show-current') == 'main'
            and act.git('rev-parse', 'origin/main') == args.target and not act.git('status', '--porcelain', '--untracked-files=no'),
            'Shared main must be clean at the exact failed target.')
    act.run(['git', 'merge-base', '--is-ancestor', FAILED_TARGET, args.target], cwd=ROOT)
    validate_changed(act.git('diff', '--name-only', FAILED_TARGET, args.target).splitlines())
    require(Path(__file__).read_bytes() == act.blob(args.target, SELF), 'Resume tool differs from its reviewed target.')
    pulls = json.loads(act.output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target and p.get('base', {}).get('ref') == 'main' for p in pulls), 'Exact merged PR required.')
    act.run(['bash', str(ROOT / 'scripts/check-citation.sh'), args.target], cwd=ROOT)
    modules = {name: act.load(name, relative, args.target) for name, relative in act.HELPERS.items()}
    old, word, identity, storage, previous = (modules[k] for k in ('old', 'word', 'identity', 'storage', 'previous'))
    report = failure_report(word)
    require(report['baseline'] == act.BASELINE and report['served_before'] == act.RUNNING_RELEASE, 'Unexpected activation ancestry.')
    act.stopped()
    original = word.checked_file(APP / '.env', private=True)
    require(sha(original) == report['environment_before_sha256']
            and original == word.checked_file(PRIOR_STATE / 'prior-environment.env', private=True), 'Original environment changed after failure.')
    updated = act.updated_environment(original, args.target)
    archive = word.checked_file(PRIOR_STATE / 'prior-runtime-source.tar', private=True)
    require(sha(archive) == report['retained_source']['sha256'] and len(archive) == report['retained_source']['bytes']
            and act.retained_source_manifest(archive) == json.loads(word.checked_file(PRIOR_STATE / 'prior-runtime-manifest.json', private=True)), 'Prior runtime recovery archive or manifest changed.')
    lock_bytes, lock_identity = exact_lock(word)
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper) and act.output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper, 'Qualified helper unavailable.')
    act.validate_migration((ROOT / act.MIGRATION_PATH).read_bytes())
    act.verify_migration_plan(act.output(act.management('showmigrations', '--plan'), cwd=APP), applied=True)
    require(act.output(old.PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='" + act.MIGRATION + "'"]) == '1', 'Exactly one existing 0015 migration history row required.')
    require(act.output(old.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Unresolved jobs prohibit this preserving resume.')
    expected_body = (ROOT / act.MIGRATION_PATH).read_text().split('AS $$', 1)[1].split('$$;', 1)[0]
    def current_state():
        value = act.snapshot(modules, helper)
        value['rows'] = act.rows(old, exclude_new=True)
        return normalized(value)
    baseline = current_state()
    check_state(report, baseline, act, expected_body)
    backup_report, backup_manifest = act.backup_evidence(report['backup_report'], modules,
        str(PRIVATE / 'new-system-backups' / report['backup_run_id']))
    require(backup_manifest['run_id'] == report['backup_run_id'] and backup_report['backup_run_id'] == report['restored_backup_run_id'], 'Original restore/capture identities changed.')
    caches_before = cache_inventory(0o600)
    protected = previous.protected()
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(FAILED_TARGET), 'Word SDK build inputs changed.')
    installed = APP / '.word-sdk' / modules['billing'].SDK_RELEASE
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', modules['billing'].PIN, inputs)
    act.run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
    result_path = Path(args.result)
    state = EVIDENCE / ('resume-state-' + args.target[:12])
    lock = PRIVATE / '.private-operations-resume.lock'
    require(result_path.resolve() == result_path and result_path.parent == EVIDENCE
            and re.fullmatch(r'private-operations-resume-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not any(p.exists() or p.is_symlink() for p in (result_path, state, lock)), 'Unused protected resume paths required.')
    print('Read-only resume gates passed; no cache mode, source, data or service changed.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration == SOURCE / DECL
            and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == act.blob(args.target, DECL) == act.blob(commit, DECL), 'Exact committed resume declaration required.')
    act.run(['git', 'merge-base', '--is-ancestor', commit, args.target], cwd=ROOT)
    identity.private_write(lock, {'target': args.target, 'pid': os.getpid(), 'prior_failure_sha256': REPORT_SHA256})
    state.mkdir(mode=0o700)
    result = {'complete': False, 'started_at': datetime.now(timezone.utc).isoformat(), 'target': args.target,
        'failed_target': FAILED_TARGET, 'prior_failure_sha256': REPORT_SHA256, 'provider_calls': 0,
        'migrations_executed': 0, 'prior_lock_identity': lock_identity, 'caches_before': caches_before,
        'baseline': baseline, 'environment_before_sha256': sha(original), 'environment_after_sha256': sha(updated)}
    phase = 0
    def checkpoint(stage):
        nonlocal phase
        result['stage'] = stage
        identity.private_write(state / f'phase-{phase:02d}.json', result)
        phase += 1
    try:
        checkpoint('verify_stopped_unchanged_failure_state')
        act.stopped()
        check_state(report, current_state(), act, expected_body)
        require(act.git('rev-parse', 'HEAD') == FAILED_TARGET and not act.git('status', '--porcelain', '--untracked-files=no')
                and word.checked_file(APP / '.env', private=True) == original and exact_lock(word) == (lock_bytes, lock_identity), 'State changed immediately before repair.')
        private_bytes(state / 'original-failed-lock.json', lock_bytes)
        checkpoint('repair_only_three_diagnosed_cache_modes')
        result['caches_after'] = repair_cache_modes(caches_before)
        result['source_readability_before_advance'] = identity.source_readability(helper)
        checkpoint('advance_only_stopped_resume_source')
        act.stopped()
        act.run(['git', 'merge', '--ff-only', args.target], cwd=ROOT, stdout=subprocess.DEVNULL)
        require(act.git('rev-parse', 'HEAD') == args.target and not act.git('status', '--porcelain', '--untracked-files=no'), 'Source differs from exact resume target.')
        result['source_readability_after_advance'] = identity.source_readability(helper)
        act.verify_migration_plan(act.output(act.management('showmigrations', '--plan'), cwd=APP), applied=True)
        check_state(report, current_state(), act, expected_body)
        checkpoint('replace_release_setting_only')
        modules['env'].replace_environment(APP / '.env', original, updated)
        checkpoint('start_and_verify_exact_resumed_private_release')
        word.systemd('start', helper)
        for attempt in range(45):
            try:
                result['health'] = act.health(args.target)
                break
            except (subprocess.CalledProcessError, json.JSONDecodeError, RuntimeError):
                time.sleep(1)
        else:
            raise RuntimeError('Resumed private runtime did not become healthy.')
        result['proofs'] = identity.verify_live(args.target, storage)
        result['interfaces'] = identity.verify_interfaces()
        worker = old.worker_process()
        require(worker['systemd_start'] != report['worker_before']['systemd_start']
                and worker['kernel_start_utc'] > report['worker_before']['kernel_start_utc'], 'Actual worker restart was not proved.')
        result['worker'] = worker
        result['final_state'] = current_state()
        check_state(report, result['final_state'], act, expected_body)
        require(word.checked_file(APP / '.env', private=True) == updated and previous.protected() == protected
                and exact_lock(word) == (lock_bytes, lock_identity) and cache_inventory(0o644) == result['caches_after'], 'Environment, protected services, cache bytes or retained failed lock changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', modules['billing'].PIN, inputs) == artifact, 'Word runtime artifact changed.')
        require(sha(word.checked_file(REPORT, private=True)) == REPORT_SHA256, 'Historical failed record changed.')
        act.run(['bash', str(ROOT / 'scripts/check-cotenants.sh')], cwd=ROOT)
        result.update(existing_rows_preserved=True, migration_guard_preserved=True,
                      original_lock_retired=False, resume_lock_retired=False)
        checkpoint('complete_verified_before_lock_retirement')
        FAILED_LOCK.unlink()
        result['original_lock_retired'] = True
        lock.unlink()
        result['resume_lock_retired'] = True
        result.update(complete=True, finished_at=datetime.now(timezone.utc).isoformat())
        checkpoint('complete')
        identity.private_write(result_path, result)
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, finished_at=datetime.now(timezone.utc).isoformat())
        try:
            word.systemd('stop', helper); act.stopped(); result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False; result['stop_failure_kind'] = type(stop_error).__name__
        if not result_path.exists():
            identity.private_write(result_path, result)
        else:
            identity.private_write(state / 'failure-after-result.json', result)
        raise RuntimeError('Resume failed closed; inspect retained evidence. No automatic retry or data rollback.') from None
    print('Private resume verified; evidence: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
