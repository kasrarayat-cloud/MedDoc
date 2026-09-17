#!/usr/bin/env python3
"""Resume only the recorded stopped Word activation; default is read-only."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
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
BROKEN_RELEASE = '429283dfb71aa389bccef48976ee0dce2936e0bc'
FAILED_REPORT = PRIVATE / 'word-beta-activation-20260917-repaired.json'
FAILED_REPORT_SHA = 'b1e157455bbf089655a10c05866fbddb235e15364ef7b0f692eb10f8f9a9bafb'
PARTIAL_AUDIT = PRIVATE / 'word-partial-state-audit-20260917.json'
PARTIAL_AUDIT_SHA = '088065ee0becdfdea70de3e2008269d4fe4277818ece8423fb90b1ea90ff5589'
OLD_LOCK = PRIVATE / '.word-beta-activation.lock'
OLD_LOCK_SHA = 'f4b20bf7cbe7afe62d5c48cdf8a08a7227f73d81cafb2a8440db275728516506'
MANIFEST_SHA = '2a2ab5e1ba63e041dfd087e7f2c205999ccf8ff6bc41f9409cfd1d99e4537680'
BAD_ASSET = 'app.279720c6eccc.css.gz'
BAD_ASSET_SHA = '097328d627f54b8e026520cce973058f351d32674c0d2523545cc49557f10f3d'
DECLARATION = 'docs/foundation/mutations/20260917-quillmd-static-recovery.md'
ALLOWED_CHANGES = {
    'rebuild/quillmd/settings.py', 'rebuild/quillmd/static_storage.py',
    'rebuild/core/tests/test_static_permissions.py',
    'scripts/resume-word-beta.py', 'rebuild/ops/test_word_recovery.py', DECLARATION,
}
HELPERS = ('scripts/activate-word-beta.py', 'scripts/activate-os-identity.py',
           'scripts/update-private-beta.py', 'rebuild/ops/private_storage.py')


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def output(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_changes(names):
    changed = set(names)
    required = {'scripts/resume-word-beta.py', 'rebuild/quillmd/settings.py',
                'rebuild/quillmd/static_storage.py', 'rebuild/core/tests/test_static_permissions.py',
                'rebuild/ops/test_word_recovery.py', DECLARATION}
    require(changed == required and changed <= ALLOWED_CHANGES,
            'Recovery target differs beyond the exact static fix, recovery checks and declaration.')


def validate_failed_report(word, data):
    require(digest(data) == FAILED_REPORT_SHA, 'Failed activation evidence differs from its recorded SHA256.')
    report = word.unique_json(data)
    require(report.get('target') == BROKEN_RELEASE and report.get('previous_head') == word.BASELINE
            and report.get('complete') is False and report.get('provider_calls') == 0
            and report.get('stage') == 'applying_three_json_columns'
            and report.get('failure_kind') == 'RuntimeError'
            and report.get('failure_services_stopped') is True
            and len(report.get('database_after_all_columns', {})) == 33
            and set(report.get('storage_before', {})) == {'files', 'mail'}
            and report.get('artifact', {}).get('manifest_sha256') == MANIFEST_SHA
            and 'static_permissions' not in report,
            'Evidence does not describe the exact inspected partial activation.')
    word.check_schema(report['schema_before'], report['schema_after'])
    return report


def validate_partial_audit(word, data, env):
    require(digest(data) == PARTIAL_AUDIT_SHA, 'Partial-state audit differs from its independently recorded SHA256.')
    audit = word.unique_json(data)
    require(audit.get('complete') is True and audit.get('main_head') == BROKEN_RELEASE
            and audit.get('failed_report_sha256') == FAILED_REPORT_SHA
            and audit.get('word_env_keys_present') is False and audit.get('provider_calls') == 0
            and audit.get('all33_old_row_hashes_match') is True
            and audit.get('all33_post_schema_table_hashes_match') is True
            and audit.get('schema_matches_declared_after') is True
            and audit.get('all_files_mail_identical') is True
            and audit.get('private_env_sha256') == digest(env),
            'Environment or partial activation differs from the independently inspected state.')
    return audit


def stopped(word):
    for unit in word.UNITS:
        require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0',
                'Recovery requires all three private services already stopped.')
    require(output(word.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running')"]) == '0',
            'A pending job requires inspection; recovery never retries providers.')


def static_inventory(*, before):
    """Only the observed gzip mode may differ; all bytes remain public assets."""
    root = APP / 'staticfiles'
    require(root.resolve() == root, 'Static output path is not canonical.')
    rows, total = {}, 0
    for path in [root, *sorted(root.rglob('*'))]:
        info = path.lstat()
        name = str(path.relative_to(root))
        directory = stat.S_ISDIR(info.st_mode)
        expected_mode = 0o755 if directory else 0o644
        if before and name == BAD_ASSET:
            expected_mode = 0o664
        require((directory or stat.S_ISREG(info.st_mode)) and info.st_uid == os.getuid()
                and stat.S_IMODE(info.st_mode) == expected_mode
                and (directory or info.st_nlink == 1),
                'Static population differs from the single inspected compression-mode failure.')
        row = {'directory': directory, 'mode': stat.S_IMODE(info.st_mode)}
        if not directory:
            require(info.st_size <= 16 * 1024 * 1024, 'Public asset exceeds the bounded size.')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                with os.fdopen(os.dup(fd), 'rb') as stream:
                    data = stream.read(16 * 1024 * 1024 + 1)
                after = os.fstat(fd)
                require(all(getattr(info, key) == getattr(after, key) for key in
                            ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))
                        and len(data) == info.st_size, 'Static artifact changed during inventory.')
            finally:
                os.close(fd)
            row.update(sha256=digest(data), size=len(data))
            total += len(data)
        rows[name] = row
        require(len(rows) <= 10000 and total <= 128 * 1024 * 1024, 'Static population exceeds its bounded size.')
    require(rows.get(BAD_ASSET, {}).get('sha256') == BAD_ASSET_SHA,
            'The inspected gzip content changed; do not infer a different recovery.')
    return rows


def compare_static(before, after):
    expected = {name: {**row, 'mode': 0o755 if row['directory'] else 0o644}
                for name, row in before.items()}
    require(after == expected, 'Static recovery changed public content or population beyond the declared mode.')


def verify_preserved(word, storage, failed):
    require(word.schema() == failed['schema_after'], 'Applied schema differs from the failed activation evidence.')
    word.check_new_defaults()
    require(word.fingerprints(normalized=False) == failed['database_after_all_columns']
            and word.fingerprints() == failed['database_before'],
            'Application rows or migration history changed after the recorded partial activation.')
    require({name: storage.inventory(word.STATE / name) for name in ('files', 'mail')} == failed['storage_before'],
            'Private files or mail differ from the failed activation evidence.')
    require(word.retained_reports() == failed['retained_reports_before'], 'Historical retained reports changed.')
    for unit in word.UNITS:
        require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(),
                'Installed unit policy changed.')


def publish_result(identity, word, helper, result_path, lock, backlink, result):
    """Publication failures also stop services and retain an append-only marker."""
    try:
        identity.private_write(result_path, result)
        if result['complete']:
            identity.private_write(backlink, {'original_lock': str(OLD_LOCK), 'original_lock_sha256': OLD_LOCK_SHA,
                'failed_report': str(FAILED_REPORT), 'failed_report_sha256': FAILED_REPORT_SHA,
                'partial_state_audit': str(PARTIAL_AUDIT), 'partial_state_audit_sha256': PARTIAL_AUDIT_SHA,
                'completed_recovery': str(result_path), 'completed_recovery_sha256': digest(word.checked_file(result_path, private=True))})
            lock.unlink()
    except BaseException as error:
        stopped_after_failure = False
        try:
            word.systemd('stop', helper)
            stopped_after_failure = True
        finally:
            marker = result_path.with_name(result_path.stem + '-publication-failure.json')
            try:
                identity.private_write(marker, {'complete': False, 'stage': 'evidence_publication_failed',
                    'result_path': str(result_path), 'backlink': str(backlink),
                    'failure_kind': type(error).__name__, 'failure_services_stopped': stopped_after_failure})
            except BaseException:
                pass  # A failing filesystem cannot be made into successful evidence.
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Run from permanent shared main.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'A full reviewed recovery merge SHA is required.')
    require(output(['git', 'branch', '--show-current']) == 'main'
            and output(['git', 'rev-parse', 'HEAD']) == BROKEN_RELEASE
            and output(['git', 'rev-parse', 'origin/main']) == args.target
            and output(['git', 'remote', 'get-url', 'origin']) == 'https://github.com/kasrarayat-cloud/MedDoc.git',
            'Expected stopped shared main at the recorded partial activation and exact origin/main target.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    run(['git', 'merge-base', '--is-ancestor', BROKEN_RELEASE, args.target])
    validate_changes(output(['git', 'diff', '--name-only', BROKEN_RELEASE, args.target]).splitlines())
    require(subprocess.check_output(['git', 'show', args.target + ':scripts/resume-word-beta.py']) == Path(__file__).read_bytes(),
            'Recovery script differs from the reviewed target.')
    for path in HELPERS:
        require(subprocess.check_output(['git', 'show', args.target + ':' + path]) == (ROOT / path).read_bytes()
                == subprocess.check_output(['git', 'show', BROKEN_RELEASE + ':' + path]),
                'Previously reviewed recovery helper changed.')
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(row.get('merged_at') and row.get('merge_commit_sha') == args.target
                and row.get('base', {}).get('ref') == 'main' for row in pulls), 'A merged recovery PR into main is required.')
    require(PRIVATE.resolve() == PRIVATE and PRIVATE.stat().st_uid == os.getuid()
            and stat.S_IMODE(PRIVATE.stat().st_mode) == 0o700, 'Operator runtime must remain private.')
    result_path = Path(args.result)
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'word-beta-recovery-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not result_path.is_symlink(), 'Choose a unique private recovery result path.')
    lock = PRIVATE / '.word-beta-recovery.lock'
    backlink = PRIVATE / '.word-beta-activation.recovery.json'
    require(not lock.exists() and not lock.is_symlink() and not backlink.exists() and not backlink.is_symlink(),
            'An earlier recovery needs inspection; never repeat automatically.')
    word = module_at('recovery_word_activation', ROOT / HELPERS[0])
    identity = module_at('recovery_identity', ROOT / HELPERS[1])
    previous = module_at('recovery_previous_updater', ROOT / HELPERS[2])
    storage = module_at('recovery_private_storage', ROOT / HELPERS[3])
    failed = validate_failed_report(word, word.checked_file(FAILED_REPORT, private=True))
    old_lock_bytes = word.checked_file(OLD_LOCK, private=True)
    require(digest(old_lock_bytes) == OLD_LOCK_SHA and word.unique_json(old_lock_bytes).get('target') == BROKEN_RELEASE,
            'Original activation lock differs from the recorded partial attempt.')
    stopped(word)
    verify_preserved(word, storage, failed)
    protected_before = previous.protected()  # Independently checks original committed container IDs/mounts.
    helper = failed['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper)
            and output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper,
            'The original fixed local helper image is unavailable; no image is pulled.')
    installed = APP / '.word-sdk' / BROKEN_RELEASE
    runtime, manifest, proof = installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json'
    inputs = word.expected_inputs(args.target)
    require(len(inputs) == 17 and inputs == word.expected_inputs(BROKEN_RELEASE), 'Recovery changed a compiled SDK input.')
    artifact = word.verify_artifact(runtime, manifest, proof, MANIFEST_SHA, inputs)
    require(artifact == failed['artifact'], 'Installed SDK differs from the recorded completed installation.')
    env_before = word.checked_file(APP / '.env', private=True)
    validate_partial_audit(word, word.checked_file(PARTIAL_AUDIT, private=True), env_before)
    env_after = word.updated_environment(env_before, args.target, runtime, manifest, MANIFEST_SHA)
    assets_before = static_inventory(before=True)
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Verified the stopped partial activation, unchanged data, installed SDK and cited static-only recovery.', flush=True)
    if not args.execute:
        return
    decl_commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    declaration_path = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    require(declaration_path.is_absolute() and declaration_path.resolve() == declaration_path
            and declaration_path.name == Path(DECLARATION).name and re.fullmatch('[a-f0-9]{40}', decl_commit),
            'Use the absolute committed-worktree declaration path through the ruled-mutation runner.')
    require(declaration_path.read_bytes() == subprocess.check_output(['git', 'show', args.target + ':' + DECLARATION])
            == subprocess.check_output(['git', 'show', decl_commit + ':' + DECLARATION]),
            'Declaration bytes differ from the committed reviewed recovery scope.')
    run(['git', 'merge-base', '--is-ancestor', decl_commit, args.target])
    identity.private_write(lock, {'pid': os.getpid(), 'target': args.target, 'failed_report_sha256': FAILED_REPORT_SHA})
    result = {'started_at': datetime.now(timezone.utc).isoformat(), 'complete': False, 'stage': 'rechecking_stopped_state',
              'previous_head': BROKEN_RELEASE, 'target': args.target, 'provider_calls': 0, 'migration_commands': 0,
              'failed_report': str(FAILED_REPORT), 'failed_report_sha256': FAILED_REPORT_SHA,
              'partial_state_audit': str(PARTIAL_AUDIT), 'partial_state_audit_sha256': PARTIAL_AUDIT_SHA,
              'original_lock_sha256': OLD_LOCK_SHA, 'environment_before_sha256': digest(env_before),
              'helper_image': helper, 'artifact': artifact, 'static_before': assets_before,
              'protected_containers': protected_before, 'completion_requires_link': str(backlink)}
    try:
        stopped(word)
        verify_preserved(word, storage, failed)
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed during preflight.')
        require(static_inventory(before=True) == assets_before, 'Static artifacts changed during preflight.')
        result['stage'] = 'advancing_reviewed_main'
        run(['git', 'merge', '--ff-only', args.target])
        result['stage'] = 'rebuilding_public_static_assets'
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'check'], cwd=APP)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'collectstatic', '--noinput'], cwd=APP)
        result['static_after'] = static_inventory(before=False)
        compare_static(assets_before, result['static_after'])
        result['static_permissions'] = word.static_permissions()
        result['source_readability'] = identity.source_readability(helper)
        stopped(word)
        verify_preserved(word, storage, failed)
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed before its scoped update.')
        pending = PRIVATE / ('word-beta-recovery-env-' + args.target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed concurrently.')
        pending.replace(APP / '.env')
        require(word.checked_file(APP / '.env', private=True) == env_after, 'Scoped environment update differs.')
        result['stage'] = 'starting_and_verifying_private_services'
        word.systemd('start', helper)
        for attempt in range(30):
            try:
                health = [json.loads(output(['curl', '--fail', '--silent', f'http://127.0.0.1:{port}/health/'])) for port in (9130, 9131)]
                if all(row.get('release') == args.target and row.get('data_mode') == 'synthetic-only' for row in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Private health did not identify the reviewed recovery release.')
        result['proofs'] = identity.verify_live(args.target, storage)
        result['interfaces'] = identity.verify_interfaces()
        verify_preserved(word, storage, failed)
        require(word.verify_artifact(runtime, manifest, proof, MANIFEST_SHA, inputs) == artifact, 'Installed SDK changed.')
        require(word.checked_file(APP / '.env', private=True) == env_after, 'Environment changed at startup.')
        require(digest(word.checked_file(FAILED_REPORT, private=True)) == FAILED_REPORT_SHA
                and digest(word.checked_file(PARTIAL_AUDIT, private=True)) == PARTIAL_AUDIT_SHA
                and word.checked_file(OLD_LOCK, private=True) == old_lock_bytes, 'Prior evidence or lock changed.')
        require(previous.protected() == protected_before, 'Protected container population changed.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', health=health, public_maintenance=True,
                      all_database_columns_and_rows_identical=True, all_private_files_and_mail_identical=True,
                      installed_sdk_unchanged=True, environment_after_sha256=digest(env_after))
    except BaseException as error:
        result['failure_kind'] = type(error).__name__
        try:
            word.systemd('stop', helper)
            result['failure_services_stopped'] = True
        except BaseException:
            result['failure_services_stopped'] = False
        raise
    finally:
        result['finished_at'] = datetime.now(timezone.utc).isoformat()
        publish_result(identity, word, helper, result_path, lock, backlink, result)
        print('Private Word recovery evidence: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
