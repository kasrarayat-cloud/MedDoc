#!/usr/bin/env python3
"""Cited, code-only private update; preserve the authentic completed WM job."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
BASELINE = '5d43d3d62c6d3627ffe894e570a455050b042a6e'
SDK_RELEASE = '429283dfb71aa389bccef48976ee0dce2936e0bc'
PIN = '2a2ab5e1ba63e041dfd087e7f2c205999ccf8ff6bc41f9409cfd1d99e4537680'
DECL = 'docs/foundation/mutations/20260917-quillmd-labelled-values.md'
ALLOWED = {'rebuild/core/generation.py', 'rebuild/core/tests/test_labelled_answer_values.py',
           'rebuild/wm-live-browser.mjs', 'scripts/update-word-mapping.py', DECL}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def output(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Use permanent shared main.')
    require(re.fullmatch('[a-f0-9]{40}', args.target), 'Use the full merge SHA.')
    require(output(['git', 'branch', '--show-current']) == 'main'
            and output(['git', 'rev-parse', 'HEAD']) == BASELINE
            and output(['git', 'rev-parse', 'origin/main']) == args.target, 'Unexpected source release.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    run(['git', 'merge-base', '--is-ancestor', BASELINE, args.target])
    require(set(output(['git', 'diff', '--name-only', BASELINE, args.target]).splitlines()) == ALLOWED,
            'Only the reviewed mapper, tests, browser verifier and declared updater may change.')
    require(subprocess.check_output(['git', 'show', args.target + ':scripts/update-word-mapping.py'])
            == Path(__file__).read_bytes(), 'Updater differs from the reviewed target.')
    helpers = {'word': 'scripts/activate-word-beta.py', 'identity': 'scripts/activate-os-identity.py',
               'previous': 'scripts/update-private-beta.py', 'storage': 'rebuild/ops/private_storage.py'}
    modules = {}
    for name, relative in helpers.items():
        require(subprocess.check_output(['git', 'show', args.target + ':' + relative])
                == (ROOT / relative).read_bytes(), 'Existing qualified helper changed.')
        modules[name] = load('mapping_update_' + name, relative)
    word, identity, previous, storage = (modules[k] for k in ('word', 'identity', 'previous', 'storage'))
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.target
                and p.get('base', {}).get('ref') == 'main' for p in pulls), 'A merged PR is required.')
    backup = previous.validate_restore_report(args.backup_report)
    require(backup.get('backup_run_id') == '20260917T211935Z-6f919769', 'Use the restored post-provider snapshot.')
    require(output(word.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0',
            'Unresolved jobs require inspection; never replay a provider request.')
    protected = previous.protected()
    retained = word.retained_reports()
    env_before = word.checked_file(APP / '.env', private=True)
    old_line = ('QUILLMD_RELEASE_SHA=' + BASELINE).encode()
    require(env_before.splitlines().count(old_line) == 1, 'Expected current private release setting.')
    env_after = re.sub(rb'(?m)^' + re.escape(old_line) + rb'$',
                       ('QUILLMD_RELEASE_SHA=' + args.target).encode(), env_before)
    require(env_after != env_before, 'Release replacement did not apply.')
    installed = APP / '.word-sdk' / SDK_RELEASE
    inputs = word.expected_inputs(args.target)
    require(inputs == word.expected_inputs(BASELINE), 'Compiled Word inputs must not change.')
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                    installed / 'build-proof.json', PIN, inputs)
    helper = json.loads(word.checked_file(PRIVATE / 'word-beta-recovery-20260917-final.json', private=True))['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper) and
            output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper, 'Pinned local helper required.')
    result_path = Path(args.result)
    lock = PRIVATE / '.word-mapping-update.lock'
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'word-mapping-update-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not result_path.is_symlink()
            and not lock.exists() and not lock.is_symlink(), 'Choose unused private operation evidence.')
    run(['bash', 'scripts/check-citation.sh', args.target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Code-only update preflight passed; no schema, runtime, static or provider operation.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration
            and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == subprocess.check_output(['git', 'show', args.target + ':' + DECL])
            == subprocess.check_output(['git', 'show', commit + ':' + DECL]), 'Committed absolute declaration required.')
    run(['git', 'merge-base', '--is-ancestor', commit, args.target])
    identity.private_write(lock, {'target': args.target, 'pid': os.getpid()})
    result = {'complete': False, 'previous_head': BASELINE, 'target': args.target,
              'started_at': datetime.now(timezone.utc).isoformat(), 'provider_calls': 0,
              'migration_commands': 0, 'backup_report': args.backup_report, 'artifact': artifact}
    try:
        result['stage'] = 'stopping_private_services'
        word.systemd('stop', helper)
        for unit in word.UNITS:
            require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                    and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0', 'Service did not stop.')
        require(output(word.PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Job appeared before stop.')
        database, schema = word.fingerprints(normalized=False), word.schema()
        files = {name: storage.inventory(word.STATE / name) for name in ('files', 'mail')}
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed.')
        result.update(database_before=database, schema_before=schema, storage_before=files)
        result['stage'] = 'advancing_code_and_release_stamp'
        run(['git', 'merge', '--ff-only', args.target])
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'check'], cwd=APP)
        result['source_readability'] = identity.source_readability(helper)
        pending = PRIVATE / ('word-mapping-env-' + args.target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed concurrently.')
        pending.replace(APP / '.env')
        result['stage'] = 'starting_and_verifying'
        word.systemd('start', helper)
        for attempt in range(30):
            try:
                health = [json.loads(output(['curl', '--fail', '--silent', f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
                if all(h.get('release') == args.target and h.get('data_mode') == 'synthetic-only' for h in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Release health failed.')
        result['proofs'] = identity.verify_live(args.target, storage)
        result['interfaces'] = identity.verify_interfaces()
        require(word.fingerprints(normalized=False) == database and word.schema() == schema, 'Database or migration history changed.')
        require({name: storage.inventory(word.STATE / name) for name in ('files', 'mail')} == files, 'Private bytes changed.')
        require(word.checked_file(APP / '.env', private=True) == env_after, 'Environment differs from release-only update.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json',
                                    installed / 'build-proof.json', PIN, inputs) == artifact, 'Word runtime changed.')
        require(word.retained_reports() == retained and previous.protected() == protected, 'Retained or shared resources changed.')
        for unit in word.UNITS:
            require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(), 'Unit policy changed.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', health=health, all_database_columns_and_rows_identical=True,
                      all_private_files_and_mail_identical=True, protected_containers=protected,
                      environment_before_sha256=hashlib.sha256(env_before).hexdigest(),
                      environment_after_sha256=hashlib.sha256(env_after).hexdigest())
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__)
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
    print('Preserving code-only update completed: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
