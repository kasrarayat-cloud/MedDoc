#!/usr/bin/env python3
"""Resume only the recorded stopped billing-policy activation; default is read-only preflight.

The one-shot activator stopped after applying migration core.0012_billing_policy because
its guard expected every existing table to stay row-identical, while Django's post-migrate
bookkeeping legitimately added two content-type rows and eight permission rows for the two
new models. This script requires exactly that partial state, proves it, and finishes the
remaining code-only steps: Django check, collectstatic, release-line environment update,
service start and the same live verification the activator would have performed.

    cd /opt/meddoc-pro && rebuild/.venv/bin/python -B scripts/resume-billing-policy.py \
        --resume-target FULL_MERGE_SHA --result /opt/meddoc-pro/rebuild/.runtime/billing-policy-resume-<label>.json [--execute]
"""
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
STATE = Path('/var/lib/quillmd')
BASELINE = '8f8a6763b80d345e432074df64b907c2db50be2a'
TARGET = 'd2e45b533396390c36d1ffa681c188126be556ce'
FAILED_RESULT = PRIVATE / 'billing-policy-activation-20260918.json'
FAILED_RESULT_SHA = '1bb201a7568f0482b105faa554b30fb84c6bea2c45db1cdc54ea7e7579b1e290'
OLD_LOCK = PRIVATE / '.billing-policy-activation.lock'
OLD_LOCK_SHA = 'b03126bf5b4682686d5b60f6e0190216fc574aa6061b1f8ac1c11fcf2a4949a3'
DECLARATION = 'docs/foundation/mutations/20260918-quillmd-billing-policy-resume.md'
ALLOWED_CHANGES = {'scripts/resume-billing-policy.py', 'rebuild/ops/test_billing_resume.py', DECLARATION}
HELPERS = {'billing': 'scripts/activate-billing-policy.py', 'word': 'scripts/activate-word-beta.py',
           'identity': 'scripts/activate-os-identity.py', 'previous': 'scripts/update-private-beta.py',
           'storage': 'rebuild/ops/private_storage.py'}
# Django's post-migrate bookkeeping for the two new models: the only rows that may differ from the pre-migration
# fingerprints, and they must be present exactly once each.
BOOKKEEPING_MODELS = ('costreconciliation', 'platformcost')
BOOKKEEPING_PERMISSIONS = {f'{action}_{model}' for model in BOOKKEEPING_MODELS for action in ('add', 'change', 'delete', 'view')}
BOOKKEEPING_TABLES = {'django_content_type': "WHERE NOT (app_label='core' AND model IN ('costreconciliation','platformcost'))",
                      'auth_permission': "WHERE content_type_id NOT IN (SELECT id FROM django_content_type WHERE app_label='core' AND model IN ('costreconciliation','platformcost'))"}
UNITS = ['quillmd-fresh-' + surface + '.service' for surface in ('doctor', 'admin', 'worker')]
PSQL = ['docker', 'exec', 'quillmd-fresh-postgres', 'psql', '-U', 'quillmd_fresh',
        '-d', 'quillmd_fresh', '-X', '-At', '-v', 'ON_ERROR_STOP=1', '-c']


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def output(command, **kwargs):
    return subprocess.check_output(command, text=True, **kwargs).strip()


def run(command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fingerprints_excluding_bookkeeping(tables):
    """Row fingerprints of every table, excluding only the ten expected bookkeeping rows and the 0012 history row."""
    rows = {}
    for table in tables:
        where = BOOKKEEPING_TABLES.get(table, '')
        if table == 'django_migrations':
            where = "WHERE NOT (app='core' AND name='0012_billing_policy')"
        data = subprocess.check_output(PSQL + [f'COPY (SELECT (to_jsonb(t))::text AS value FROM "{table}" t {where} ORDER BY value) TO STDOUT'])
        rows[table] = {'sha256': sha(data), 'rows': len(data.splitlines())}
    return rows


def bookkeeping_rows():
    types = output(PSQL + ["SELECT model FROM django_content_type WHERE app_label='core' AND model IN ('costreconciliation','platformcost') ORDER BY model"]).splitlines()
    perms = output(PSQL + ["SELECT p.codename FROM auth_permission p JOIN django_content_type c ON c.id=p.content_type_id WHERE c.app_label='core' AND c.model IN ('costreconciliation','platformcost') ORDER BY 1"]).splitlines()
    return types, perms


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resume-target', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    require(Path.cwd() == ROOT and ROOT.resolve() == ROOT, 'Run from permanent shared main.')
    require(re.fullmatch('[a-f0-9]{40}', args.resume_target), 'A full reviewed resume merge SHA is required.')
    require(output(['git', 'branch', '--show-current']) == 'main' and output(['git', 'rev-parse', 'HEAD']) == TARGET
            and output(['git', 'rev-parse', 'origin/main']) == args.resume_target, 'Expected permanent main at the partially activated target with the resume merged on origin.')
    run(['git', 'diff', '--exit-code', 'HEAD', '--', '.'])
    run(['git', 'merge-base', '--is-ancestor', TARGET, args.resume_target])
    changed = set(output(['git', 'diff', '--name-only', TARGET, args.resume_target]).splitlines())
    require(changed == ALLOWED_CHANGES, 'The resume target may carry only the resume script, its tests and its declaration: ' + ', '.join(sorted(changed ^ ALLOWED_CHANGES)))
    require(subprocess.check_output(['git', 'show', args.resume_target + ':scripts/resume-billing-policy.py']) == Path(__file__).read_bytes(),
            'Resume script differs from the reviewed target.')
    modules = {}
    for name, relative in HELPERS.items():
        require(subprocess.check_output(['git', 'show', args.resume_target + ':' + relative]) == (ROOT / relative).read_bytes(),
                'Previously reviewed helper changed: ' + relative)
        modules[name] = module_at('billing_resume_' + name, ROOT / relative)
    billing, word, identity, previous, storage = (modules[k] for k in ('billing', 'word', 'identity', 'previous', 'storage'))
    pulls = json.loads(output(['gh', 'api', f'repos/kasrarayat-cloud/MedDoc/commits/{args.resume_target}/pulls']))
    require(any(p.get('merged_at') and p.get('merge_commit_sha') == args.resume_target and p.get('base', {}).get('ref') == 'main' for p in pulls),
            'A merged resume PR into main is required.')
    failed_bytes = word.checked_file(FAILED_RESULT, private=True)
    require(sha(failed_bytes) == FAILED_RESULT_SHA, 'Failed activation result differs from the recorded partial attempt.')
    failed = word.unique_json(failed_bytes)
    require(failed.get('complete') is False and failed.get('stage') == 'applying_two_new_tables' and failed.get('target') == TARGET
            and failed.get('previous_head') == BASELINE and failed.get('failure_kind') == 'RuntimeError' and failed.get('failure_services_stopped') is True
            and failed.get('provider_calls') == 0, 'Recorded partial state is not the one this resume was written for.')
    old_lock_bytes = word.checked_file(OLD_LOCK, private=True)
    require(sha(old_lock_bytes) == OLD_LOCK_SHA and word.unique_json(old_lock_bytes).get('target') == TARGET, 'Original activation lock differs from the recorded partial attempt.')
    result_path = Path(args.result)
    lock = PRIVATE / '.billing-policy-resume.lock'
    backlink = PRIVATE / '.billing-policy-activation.recovery.json'
    require(result_path.is_absolute() and result_path.parent == PRIVATE and result_path.resolve() == result_path
            and re.fullmatch(r'billing-policy-resume-[a-zA-Z0-9_-]+\.json', result_path.name)
            and not result_path.exists() and not result_path.is_symlink()
            and not lock.exists() and not lock.is_symlink() and not backlink.exists() and not backlink.is_symlink(),
            'Choose unused private resume evidence; an earlier resume needs inspection.')
    require(not any((PRIVATE / ('billing-policy-env-' + t + '.pending')).exists() for t in (TARGET, args.resume_target)), 'A pending environment file exists; inspect it first.')
    # --- the partial state, proved rather than assumed ---
    for unit in UNITS:
        require(output(['systemctl', 'show', unit, '--property=ActiveState', '--value']) == 'inactive'
                and output(['systemctl', 'show', unit, '--property=MainPID', '--value']) == '0', 'Private services must be stopped: ' + unit)
        require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(), 'Installed service policy differs from reviewed source.')
    require(output(PSQL + ["SELECT count(*) FROM core_job WHERE state IN ('queued','running','reconciliation')"]) == '0', 'Unresolved jobs require inspection.')
    require(output(PSQL + ["SELECT count(*) FROM django_migrations WHERE app='core' AND name='0012_billing_policy'"]) == '1', 'Exactly one applied 0012 history row is required.')
    for table in billing.NEW_TABLES:
        require(output(PSQL + [f'SELECT count(*) FROM {table}']) == '0', 'New table must still be empty: ' + table)
    tables = billing.tables()
    require(len(tables) == 35 and set(billing.NEW_TABLES) <= set(tables), 'Expected the 33 original tables plus the two new ones.')
    require(billing.schema() == failed['schema_after'], 'Schema differs from the recorded post-migration schema.')
    billing.check_schema(failed['schema_before'], failed['schema_after'])
    # The recorded result is JSON: its constraint rows are lists, the live query returns tuples.
    require([list(row) for row in billing.constraints()] == failed['constraints_after'] and billing.indexes() == failed['indexes_after'], 'Constraints or indexes differ from the recorded post-migration catalog.')
    billing.check_catalog(failed['constraints_before'], failed['constraints_after'], failed['indexes_before'], failed['indexes_after'])
    old_tables = [t for t in tables if t not in billing.NEW_TABLES]
    require(fingerprints_excluding_bookkeeping(old_tables) == failed['database_before'], 'Existing rows differ beyond the ten expected bookkeeping rows.')
    types, perms = bookkeeping_rows()
    require(types == list(BOOKKEEPING_MODELS) and set(perms) == BOOKKEEPING_PERMISSIONS and len(perms) == 8, 'Bookkeeping rows are not exactly the expected two content types and eight permissions.')
    for name in ('files', 'mail'):
        require(storage.inventory(STATE / name) == failed['storage_before'][name], 'Private files or mail changed since the activation attempt: ' + name)
    env_before = word.checked_file(APP / '.env', private=True)
    old_line = ('QUILLMD_RELEASE_SHA=' + BASELINE).encode()
    require(env_before.splitlines().count(old_line) == 1, 'Expected the environment still to name the running release.')
    env_after = re.sub(rb'(?m)^' + re.escape(old_line) + rb'$', ('QUILLMD_RELEASE_SHA=' + args.resume_target).encode(), env_before)
    require(env_after != env_before and env_after.count(b'\n') == env_before.count(b'\n'), 'Release replacement did not apply cleanly.')
    installed = APP / '.word-sdk' / billing.SDK_RELEASE
    inputs = word.expected_inputs(args.resume_target)
    require(inputs == word.expected_inputs(BASELINE), 'Compiled Word inputs must not change.')
    artifact = word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', billing.PIN, inputs)
    require(artifact == failed['artifact'], 'Installed Word runtime differs from the recorded activation attempt.')
    helper = failed['helper_image']
    require(re.fullmatch('sha256:[a-f0-9]{64}', helper) and output(['docker', 'image', 'inspect', helper, '--format', '{{.Id}}']) == helper, 'Pinned local helper required.')
    protected = previous.protected()
    reports_before = word.retained_reports()
    run(['bash', 'scripts/check-citation.sh', args.resume_target])
    run(['bash', 'scripts/check-cotenants.sh'])
    print('Billing-policy resume preflight passed: recorded partial state proven, only bookkeeping rows differ, services stopped, code-only steps remain.', flush=True)
    if not args.execute:
        return
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.resolve() == declaration and declaration.name == Path(DECLARATION).name
            and re.fullmatch('[a-f0-9]{40}', commit)
            and declaration.read_bytes() == subprocess.check_output(['git', 'show', args.resume_target + ':' + DECLARATION])
            == subprocess.check_output(['git', 'show', commit + ':' + DECLARATION]), 'Committed absolute resume declaration required.')
    run(['git', 'merge-base', '--is-ancestor', commit, args.resume_target])
    identity.private_write(lock, {'resume_target': args.resume_target, 'pid': os.getpid()})
    result = {'complete': False, 'partial_activation_result': str(FAILED_RESULT), 'partial_activation_sha256': FAILED_RESULT_SHA,
              'previous_head': TARGET, 'resume_target': args.resume_target, 'started_at': datetime.now(timezone.utc).isoformat(),
              'provider_calls': 0, 'migration_commands': 0, 'helper_image': helper, 'artifact': artifact,
              'bookkeeping_rows': {'content_types': types, 'permissions': sorted(perms)}, 'stage': 'advancing_reviewed_main'}
    try:
        result['database_before'] = billing.fingerprints(tables, exclude_new_migration=False)
        result['schema_before'], result['constraints_before'], result['indexes_before'] = billing.schema(), billing.constraints(), billing.indexes()
        result['storage_before'] = {name: storage.inventory(STATE / name) for name in ('files', 'mail')}
        run(['git', 'merge', '--ff-only', args.resume_target])
        result['stage'] = 'django_check_and_static'
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'check'], cwd=APP)
        run([str(APP / '.venv/bin/python'), '-B', 'manage.py', 'collectstatic', '--noinput'], cwd=APP)
        result['static_permissions'] = word.static_permissions()
        result['source_readability'] = identity.source_readability(helper)
        result['stage'] = 'replacing_release_line'
        pending = PRIVATE / ('billing-policy-env-' + args.resume_target + '.pending')
        fd = os.open(pending, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(env_after); stream.flush(); os.fsync(stream.fileno())
        require(word.checked_file(APP / '.env', private=True) == env_before, 'Environment changed concurrently.')
        pending.replace(APP / '.env')
        require(word.checked_file(APP / '.env', private=True) == env_after, 'Environment differs from release-only update.')
        result['stage'] = 'starting_and_verifying'
        word.systemd('start', helper)
        for attempt in range(30):
            try:
                health = [json.loads(output(['curl', '--fail', '--silent', f'http://127.0.0.1:{p}/health/'])) for p in (9130, 9131)]
                if all(h.get('release') == args.resume_target and h.get('data_mode') == 'synthetic-only' for h in health):
                    break
            except (subprocess.CalledProcessError, json.JSONDecodeError):
                pass
            time.sleep(1)
        else:
            raise RuntimeError('Release health failed.')
        result['proofs'] = identity.verify_live(args.resume_target, storage)
        result['interfaces'] = identity.verify_interfaces()
        require(billing.fingerprints(tables, exclude_new_migration=False) == result['database_before'], 'Startup changed application data.')
        require(billing.schema() == result['schema_before'] and billing.constraints() == result['constraints_before'] and billing.indexes() == result['indexes_before'], 'Schema, constraints or indexes changed after startup.')
        require({name: storage.inventory(STATE / name) for name in ('files', 'mail')} == result['storage_before'], 'Private bytes changed.')
        require(word.verify_artifact(installed / 'runtime', installed / 'runtime-manifest.json', installed / 'build-proof.json', billing.PIN, inputs) == artifact, 'Word runtime changed.')
        require(word.retained_reports() == reports_before and previous.protected() == protected, 'Retained or shared resources changed.')
        for unit in UNITS:
            require((APP / 'deploy' / unit).read_bytes() == (Path('/etc/systemd/system') / unit).read_bytes(), 'Unit policy changed.')
        run(['bash', 'scripts/check-cotenants.sh'])
        result.update(complete=True, stage='complete', health=health, all_rows_identical_across_restart=True, exactly_two_empty_new_tables=True,
                      all_private_files_and_mail_identical=True, protected_containers=protected,
                      environment_before_sha256=sha(env_before), environment_after_sha256=sha(env_after))
        identity.private_write(result_path, result)
        identity.private_write(backlink, {'partial_activation_result': str(FAILED_RESULT), 'partial_activation_sha256': FAILED_RESULT_SHA,
                                          'resume_result': str(result_path), 'resume_result_sha256': sha(result_path.read_bytes()),
                                          'resolved_at': datetime.now(timezone.utc).isoformat()})
        lock.unlink()
    except BaseException as error:
        result.update(complete=False, failure_kind=type(error).__name__, finished_at=datetime.now(timezone.utc).isoformat())
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
    print('Billing-policy resume completed: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
