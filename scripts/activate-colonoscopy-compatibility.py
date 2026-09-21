#!/usr/bin/env python3
"""Preserving code-only activation for reviewed underlined-tab DOCX compatibility.

Default is read-only. Execute only from the exact clean reviewed target worktree
through the committed declaration. Reuse the existing authenticated capture and
independent-key restore honestly; no migration, backup or provider call is made.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
import types

sys.dont_write_bytecode = True
ROOT = Path('/opt/meddoc-pro')
SOURCE = Path(__file__).resolve().parents[1]
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
EVIDENCE = PRIVATE / 'colonoscopy-compatibility-20260921'
SELF = 'scripts/activate-colonoscopy-compatibility.py'
DECL = 'docs/foundation/mutations/20260921-quillmd-colonoscopy-compatibility.md'
ADAPTER = 'scripts/activate-business-readiness.py'
ADAPTER_SHA256 = '4e85207114a175d248907a82a49c60408d1e58f6f9a83011c8f3214734896a04'
BASELINE = RUNNING_RELEASE = '47374a9462dfe5bceb0947c831fc23e35a01e239'
MIGRATION = '0017_reconciliation_evidence_kind'
RUNTIME_ALLOWED = {
    SELF, 'rebuild/ops/test_colonoscopy_activation.py',
    'rebuild/documents/engine.py', 'rebuild/documents/tab_form.py',
    'rebuild/documents/test_tab_form.py', 'rebuild/documents/README.md',
    'rebuild/documents/__fixtures__/Colonoscopy_Operative_Template.docx',
    'rebuild/documents/__fixtures__/README.md',
    'rebuild/core/tab_review.py', 'rebuild/core/generation.py', 'rebuild/core/views.py',
    'rebuild/core/tests/test_tab_form_policy.py', 'rebuild/core/tests/test_tab_form_workflow.py',
    'rebuild/templates/template_detail.html', 'rebuild/templates/encounter_detail.html',
    'rebuild/tab-form-browser.mjs',
    'scripts/ci/verify-fresh.sh', 'scripts/hooks/pre-commit',
}
REQUIRED = {SELF, DECL, 'rebuild/documents/engine.py',
            'rebuild/ops/test_colonoscopy_activation.py'}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


data = (SOURCE / ADAPTER).read_bytes()
require(sha(data) == ADAPTER_SHA256, 'Qualified preserving adapter changed.')
a = types.ModuleType('_colonoscopy_preserving_adapter')
a.__file__ = str(SOURCE / ADAPTER)
sys.modules[a.__name__] = a
exec(compile(data, a.__file__, 'exec'), a.__dict__)
for name in ('ROOT', 'SOURCE', 'APP', 'PRIVATE', 'EVIDENCE', 'SELF', 'DECL', 'BASELINE', 'RUNNING_RELEASE'):
    setattr(a, name, globals()[name])
a.BASELINE_OPERATION_PATHS = set()
b = a.configured_driver()


def validate_changed(changed):
    require(REQUIRED <= changed, 'Required reviewed compatibility change is absent.')
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True)
    parser.add_argument('--backup-report', required=True)
    parser.add_argument('--result', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
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
    baseline = snapshot(modules, helper)
    assert_retained_capture(manifest, modules, baseline['storage']['files'])
    result_path = Path(args.result)
    lock = PRIVATE / '.private-readiness-activation.lock'
    state = EVIDENCE / ('activation-state-' + args.target[:12])
    require(result_path.is_absolute() and result_path.resolve() == result_path and result_path.parent == EVIDENCE
            and re.fullmatch(r'colonoscopy-activation-[a-zA-Z0-9_-]+\.json', result_path.name)
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
            existing_schema_indexes_constraints_catalog_unchanged=True, private_files_mail_and_static_unchanged=True,
            backup_units_installed=False, finished_at=datetime.now(timezone.utc).isoformat())
        checkpoint('complete')
        identity.private_write(result_path, result)
        lock.unlink()
    except BaseException as error:
        result.update(failure_kind=type(error).__name__, finished_at=datetime.now(timezone.utc).isoformat())
        try:
            word.systemd('stop', helper); b.stopped(); result['failure_services_stopped'] = True
        except BaseException as stop_error:
            result['failure_services_stopped'] = False; result['stop_failure_kind'] = type(stop_error).__name__
        identity.private_write(result_path, result)
        raise RuntimeError('Private activation stopped; inspect preserved evidence before a declared repair.') from None
    print('Private code-only activation verified; evidence: ' + str(result_path), flush=True)


if __name__ == '__main__':
    main()
