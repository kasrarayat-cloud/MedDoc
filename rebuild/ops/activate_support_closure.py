"""Declared support-closure installation; inert without an exact new plan.

This code-only boundary preserves all current rows, clinical files, static assets
and configuration except the release stamp. It submits no provider work and does
not reopen any saved clinical or coding decision.
"""
import argparse
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

from dotenv import dotenv_values
from dotenv.parser import parse_stream
from . import activate_rowan_corti as prior
from .activate_coordinated_workflow import snapshot, TABLE_FINGERPRINT_CONTRACT

BASE = '899f3a4cf1f4c156702e95bcbec0df71666072fa'
SOURCE = Path(__file__).resolve().parents[2]
FORMAT = 'quillmd-support-closure-native-install-v1'
RUNTIME = frozenset({'rebuild/core/semantic_generation.py', 'rebuild/core/jobs.py',
    'rebuild/core/coding_reference_store.py', 'rebuild/core/coding_engine.py',
    'rebuild/core/corti_coding.py'})
SUPPORT = frozenset({'rebuild/ops/activate_support_closure.py',
    'rebuild/ops/test_activate_support_closure.py',
    'docs/runbooks/support-closure-install-20261017.md',
    'rebuild/core/tests/test_semantic_reference_contract.py',
    'rebuild/core/tests/test_source_context_jobs.py',
    'rebuild/core/tests/test_support_closure_generation.py',
    'rebuild/core/tests/test_coding_prediction_reference.py'})
FIXTURES = frozenset({'rebuild/core/tests/fixtures/elias_support_closure_retained.json',
    'rebuild/core/tests/fixtures/iris_support_closure_retained.json'})
require, Refusal = prior.require, prior.Refusal


@contextmanager
def bound_primitives():
    """Reuse low-level publication primitives, never a consumed activation."""
    saved = {key: getattr(prior, key) for key in ('BASE', 'SOURCE', 'STATIC')}
    prior.BASE, prior.SOURCE, prior.STATIC = BASE, SOURCE, frozenset()
    try:
        yield
    finally:
        for key, value in saved.items():
            setattr(prior, key, value)


def validate_plan(plan):
    require(type(plan) is dict and set(plan) == {'format', 'base', 'candidate', 'source_sha256',
        'source_worktree', 'evidence_directory', 'environment_before_sha256', 'environment', 'static',
        'baseline_path', 'baseline_sha256'},
        'closed_support_closure_plan')
    require(plan['format'] == FORMAT and plan['base'] == BASE
            and re.fullmatch('[a-f0-9]{40}', plan['candidate']) and plan['candidate'] != BASE,
            'exact_support_closure_revision')
    require(re.fullmatch('[a-f0-9]{64}', plan['environment_before_sha256']), 'environment_pin')
    require(re.fullmatch('[a-f0-9]{64}', plan['baseline_sha256']), 'declared_baseline_pin')
    baseline_path = Path(plan['baseline_path'])
    require(baseline_path.is_absolute() and baseline_path.parent.resolve() == baseline_path.parent,
            'canonical_declared_baseline_path')
    paths = plan['source_sha256']
    require(type(paths) is dict and 0 < len(paths) <= len(RUNTIME | SUPPORT | FIXTURES) and RUNTIME.intersection(paths),
            'finite_support_closure_source_manifest')
    for name, digest in paths.items():
        path = PurePosixPath(name)
        require(name == str(path) and not path.is_absolute()
                and not any(part.startswith('.') for part in path.parts)
                and name in RUNTIME | SUPPORT | FIXTURES
                and re.fullmatch('[a-f0-9]{64}', digest), 'only_support_closure_source')
    require(type(plan['environment']) is dict and plan['environment'] == {}, 'release_stamp_only')
    require(type(plan['static']) is list and plan['static'] == [], 'static_must_remain_unchanged')
    out = Path(plan['evidence_directory']); source = Path(plan['source_worktree'])
    require(out.is_absolute() and out.parent.resolve() == out.parent and not out.exists()
            and not out.is_symlink() and out.parent.stat().st_uid == os.getuid()
            and stat.S_IMODE(out.parent.stat().st_mode) == 0o700, 'exclusive_private_output')
    require(source.is_absolute() and source.resolve() == source and source == SOURCE, 'exact_operator_worktree')


def render_environment(original, revision, environment):
    require(type(environment) is dict and environment == {}, 'release_stamp_only')
    require(re.fullmatch('[a-f0-9]{40}', revision) and revision != BASE, 'exact_support_closure_revision')
    values = dotenv_values(stream=io.StringIO(original.decode()), interpolate=False)
    require(values.get('QUILLMD_RELEASE_SHA') == BASE, 'exact_installed_release')
    require(sum(binding.key == 'QUILLMD_RELEASE_SHA' for binding in parse_stream(io.StringIO(original.decode()))) == 1,
            'duplicate_release_assignment')
    lines, found = [], False
    for line in original.splitlines(keepends=True):
        match = re.match(rb'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=', line)
        if match and match[1] == b'QUILLMD_RELEASE_SHA':
            require(not found, 'duplicate_release_assignment'); found = True
            ending = b'\r\n' if line.endswith(b'\r\n') else b'\n' if line.endswith(b'\n') else b''
            lines.append(b'QUILLMD_RELEASE_SHA="' + revision.encode() + b'"' + ending)
        else:
            lines.append(line)
    require(found, 'release_assignment_found')
    result = b''.join(lines)
    after = dotenv_values(stream=io.StringIO(result.decode()), interpolate=False)
    require(after == {**values, 'QUILLMD_RELEASE_SHA': revision}, 'only_release_stamp_changed')
    return result


def unchanged(before, after):
    require(before == after, 'all_current_database_state_unchanged')
    require(not any(after['pending'].values()), 'no_provider_work_during_install')


def declared_baseline(plan):
    """Load a fresh, purpose-bound observation; no native state is changed."""
    raw = prior.backup_restore.read_private(Path(plan['baseline_path']), 32 * 1024**2)
    require(prior.sha(raw) == plan['baseline_sha256'], 'declared_baseline_bytes')
    baseline = json.loads(raw)
    require(baseline['read_only'] is True and baseline['native_mutations'] == 0
            and baseline['provider_calls'] == 0 and baseline['coordination_exclusion_acquired'] is False,
            'declared_readonly_observation')
    require(baseline['installed_base'] == BASE and baseline['candidate'] == plan['candidate']
            and baseline['source_worktree'] == plan['source_worktree']
            and baseline['source_sha256'] == plan['source_sha256'], 'declared_baseline_source_binding')
    require(baseline['environment_sha256'] == plan['environment_before_sha256'], 'declared_baseline_environment')
    started = datetime.fromisoformat(baseline['capture_started_at'])
    captured = datetime.fromisoformat(baseline['captured_at'])
    now = datetime.now(timezone.utc)
    require(started.tzinfo is not None and captured.tzinfo is not None
            and 0 <= (captured - started).total_seconds()
            and 0 <= (now - captured).total_seconds() <= (now - started).total_seconds() <= 3600,
            'fresh_declared_baseline')
    require(baseline['database']['table_fingerprint_contract'] == TABLE_FINGERPRINT_CONTRACT,
            'declared_snapshot_contract')
    require(not any(baseline['database']['pending'].values()), 'declared_baseline_pending_work')
    return baseline, raw


def compare_declared_baseline(declared, locked, prepared):
    """Only a service-health refresh may precede the strict locked baseline."""
    require(declared['installed_changed_source_sha256'] ==
            {name: entry['sha256'] for name, entry in prepared['before'].items()},
            'declared_original_source_bytes')
    for key in ('configuration', 'files', 'static'):
        require(declared[key] == locked[key], 'declared_' + key + '_preserved')
    require(declared['foreign_services'] == locked['services'], 'declared_foreign_services_preserved')
    before, after = declared['database'], locked['database']
    require(set(before) == set(after) and all(before[k] == after[k] for k in before if k != 'tables'),
            'declared_database_metadata_preserved')
    old, new = before['tables'], after['tables']
    require(set(old) == set(new) and 'core_servicehealth' in old, 'declared_table_population_preserved')
    changes = [name for name in old if old[name] != new[name]]
    require(set(changes) <= {'core_servicehealth'} and old['core_servicehealth'][0] == new['core_servicehealth'][0],
            'only_predeclared_servicehealth_refresh')
    return dict(declared_baseline_compared_before_stop=True,
        permitted_database_table_changes=changes, foreign_services_preserved=True,
        configuration_preserved=True, files_preserved=True, static_preserved=True,
        installed_source_preserved=True, other_database_state_preserved=True)


def failure_diagnostics(error):
    """Retain safe classifications and code locations, never exception text/SQL.

    A previous operational failure retained only its class. SQLSTATE and the
    precise operator stage distinguish a database rejection from a transport
    failure; fixed connection categories preserve useful libpq evidence without
    copying credentials, SQL parameters or source content into a receipt.
    """
    import psycopg
    name = type(error).__name__
    result = {'failure_type': name if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', name) else 'Exception',
              'reason': 'protected_operational_failure', 'sqlstate': None, 'connection_failure': None}
    if isinstance(error, Refusal):
        result['reason'] = 'installation_invariant_refused'
    if isinstance(error, psycopg.Error):
        state = error.sqlstate
        if isinstance(state, str) and re.fullmatch('[0-9A-Z]{5}', state):
            result['sqlstate'] = state
        if isinstance(error, psycopg.OperationalError):
            message = str(error).casefold()
            categories = (('connection refused', 'connection_refused'),
                ('timeout expired', 'connection_timeout'), ('connection timeout', 'connection_timeout'),
                ('password authentication failed', 'authentication_failed'),
                ('could not translate host name', 'name_resolution_failed'),
                ('server closed the connection unexpectedly', 'server_closed_connection'),
                ('connection is closed', 'connection_closed'), ('ssl syscall error', 'ssl_transport_error'))
            result['connection_failure'] = next((code for marker, code in categories if marker in message),
                                                'unclassified_operational_error')
    if isinstance(error, OSError) and type(error.errno) is int:
        result['errno'] = error.errno
    locations = []
    frame = error.__traceback__
    allowed = {'activate_support_closure.py', 'activate_coordinated_workflow.py', 'activate_rowan_corti.py'}
    while frame:
        filename = Path(frame.tb_frame.f_code.co_filename).name
        if filename in allowed:
            locations.append({'module': filename, 'line': frame.tb_lineno})
        frame = frame.tb_next
    result['operator_locations'] = locations
    return result


def verify_original_before_resume(original, guard, prepared):
    """HEAD alone does not prove the installed index or working files are old."""
    require(prior.git('rev-parse', 'HEAD').decode().strip() == BASE
            and not prior.git('status', '--porcelain', '--untracked-files=no').strip(),
            'clean_original_checkout_before_recovery')
    require((prior.APP / '.env').read_bytes() == original, 'original_environment_before_recovery')
    for name, entry in prepared['before'].items():
        guard.file_proof(prior.ROOT, name, entry, prepared['binding'], revision=BASE)
    for name in prepared['after'].keys() - prepared['before'].keys():
        path = prior.ROOT / name
        require(not path.exists() and not path.is_symlink(), 'new_source_absent_before_recovery')


def stop_failed_resume(host):
    """Attempt every stop and verify every unit, even if an earlier stop failed."""
    result = {'stop_errors': {}, 'state_errors': {}, 'units_inactive': {}}
    for unit in prior.UNITS:
        try:
            host.service('stop', unit)
        except BaseException as error:
            result['stop_errors'][unit] = failure_diagnostics(error)
    for unit in prior.UNITS:
        try:
            state = host.state(unit)
            result['units_inactive'][unit] = state.get('ActiveState') == 'inactive' and state.get('MainPID') == '0'
        except BaseException as error:
            result['units_inactive'][unit] = False
            result['state_errors'][unit] = failure_diagnostics(error)
    result['all_units_inactive'] = all(result['units_inactive'].values())
    return result


def execute(plan, digest):
    validate_plan(plan)
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.is_file() and re.fullmatch('[a-f0-9]{40}', commit),
            'ruled_declaration_required')
    text = declaration.read_bytes()
    require(all(value.encode() in text for value in (digest, plan['candidate'], FORMAT)), 'declaration_exact_plan')
    repo = Path(prior.command(['git', '-C', str(declaration.parent), 'rev-parse', '--show-toplevel']).decode().strip())
    require(prior.command(['git', '-C', str(repo), 'show', commit + ':' + declaration.relative_to(repo).as_posix()])
            == text, 'committed_declaration_bytes')
    original = prior.backup_restore.read_private(prior.APP / '.env', 65536)
    require(prior.sha(original) == plan['environment_before_sha256'], 'environment_before_pin')
    active = render_environment(original, plan['candidate'], plan['environment'])
    declared, declared_raw = declared_baseline(plan)
    guard = prior.source_guard(); prepared = prior.source_plan(plan, guard)
    prior.command(['bash', str(SOURCE / 'scripts/check-citation.sh'), plan['candidate']], cwd=SOURCE, timeout=120)
    out = Path(plan['evidence_directory']); out.mkdir(mode=0o700)
    prior.write_new(out / 'plan.json', plan)
    prior.write_new(out / 'declared-baseline.json', declared_raw)
    cipher = prior.backup_restore.key_at(prior.legacy.KEY)
    prior.write_new(out / 'environment-before.fernet', cipher.encrypt(original))
    prior.write_new(out / 'environment-after.fernet', cipher.encrypt(active))
    stopped = resumed = resume_started = publication_attempted = False
    stage = 'coordination_locks'
    host = prior.legacy.Host(prior.managed_helper)
    with ExitStack() as coordination:
        try:
            primitives = prior.legacy.static_primitives()
            prior.activation_exclusion.bind_runtime(prior.APP / '.runtime')
            stage = 'coordination_locks'
            coordination.enter_context(prior.legacy.operation_locks())
            coordination.enter_context(prior.activation_exclusion.hold(
                'support-closure:' + plan['candidate'][:12], timeout=30))
            stage = 'baseline_static'
            static_before = primitives.static_inventory(prior.APP / 'staticfiles')
            baseline = {'static': static_before}
            stage = 'baseline_configuration'; baseline['configuration'] = host.configuration()
            stage = 'baseline_foreign_services'; baseline['services'] = prior.foreign_services()
            stage = 'baseline_database'; baseline['database'] = snapshot(original)
            stage = 'baseline_clinical_files'; baseline['files'] = prior.private_storage.inventory(Path('/var/lib/quillmd/files'))
            stage = 'baseline_pending_check'; unchanged(baseline['database'], baseline['database'])
            stage = 'retain_baseline'; prior.write_new(out / 'baseline.json', baseline)
            stage = 'declared_baseline_comparison'
            refreshed, refreshed_raw = declared_baseline(plan)
            require(refreshed_raw == declared_raw and refreshed == declared, 'declared_baseline_recheck')
            comparison = compare_declared_baseline(declared, baseline, prepared)
            stage = 'original_source_before_stop'
            verify_original_before_resume(original, guard, prepared)
            stage = 'retain_pre_stop_comparison'
            prior.write_new(out / 'pre-stop-comparison.json', comparison)
            stage = 'stop_owned_services'; stopped = True
            for unit in prior.UNITS:
                host.service('stop', unit)
            stage = 'verify_owned_services_stopped'
            require(all(host.state(unit)['ActiveState'] == 'inactive' and host.state(unit)['MainPID'] == '0'
                        for unit in prior.UNITS), 'owned_units_drained')
            stage = 'database_after_stop'; after_stop = snapshot(original)
            stage = 'retain_database_after_stop'
            prior.write_new(out / 'database-after-stop.json', after_stop)
            stage = 'database_after_stop'; unchanged(baseline['database'], after_stop)
            stage = 'source_publication'; publication_attempted = True
            prior.publish_source(plan, guard, prepared)
            stage = 'static_preservation'
            static_after = primitives.static_inventory(prior.APP / 'staticfiles')
            require(static_after == static_before, 'static_bytes_unchanged')
            stage = 'environment_publication'
            require((prior.APP / '.env').read_bytes() == original, 'environment_concurrency')
            temporary = prior.APP / '.support-closure-env-pending'
            prior.write_new(temporary, active); temporary.replace(prior.APP / '.env')
            stage = 'database_before_resume'; before_resume = snapshot(active)
            stage = 'retain_database_before_resume'
            prior.write_new(out / 'database-before-resume.json', before_resume)
            stage = 'database_before_resume'; unchanged(baseline['database'], before_resume)
            stage = 'clinical_files_before_resume'
            require(prior.private_storage.inventory(Path('/var/lib/quillmd/files')) == baseline['files'],
                    'all_clinical_files_preserved')
            stage = 'configuration_before_resume'
            require(host.configuration() == baseline['configuration'], 'configuration_preserved')
            stage = 'foreign_services_before_resume'
            require(prior.foreign_services() == baseline['services'], 'foreign_services_preserved')
            stage = 'retain_preservation'
            evidence_sha256 = {name: prior.sha((out / name).read_bytes()) for name in
                ('baseline.json', 'database-after-stop.json', 'database-before-resume.json')}
            prior.write_new(out / 'pre-resume-preservation.json', dict(all_database_state_unchanged=True,
                files_preserved=True, static_inventory=static_after, evidence_sha256=evidence_sha256,
                declared_baseline_sha256=plan['baseline_sha256'],
                pre_stop_comparison_sha256=prior.sha((out / 'pre-stop-comparison.json').read_bytes()),
                provider_calls=0, migrations_executed=0,
                environment_delta=['QUILLMD_RELEASE_SHA']))
            stage = 'resume_owned_services'; resume_started = True
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
            result = dict(format=FORMAT, installed_revision=plan['candidate'], complete=True, health=health,
                migrations_executed=0, provider_calls=0, clinician_decisions_created=0,
                evidence_sha256=evidence_sha256, plan_sha256=digest,
                declared_baseline_sha256=plan['baseline_sha256'],
                pre_stop_comparison_sha256=prior.sha((out / 'pre-stop-comparison.json').read_bytes()),
                declaration_commit=commit, declaration_sha256=prior.sha(text),
                environment_delta=['QUILLMD_RELEASE_SHA'], strict_preservation_ends_before_resume=True)
            stage = 'retain_completion'; prior.write_new(out / 'installation-complete.json', result)
            return result
        except BaseException as error:
            # Drain before retaining evidence: a disk/write error must not leave
            # newly started units running after an unsuccessful installation.
            drain = stop_failed_resume(host) if resume_started else None
            prior.write_new(out / 'failure.json', dict(format=FORMAT, complete=False, stage=stage,
                **failure_diagnostics(error), stopped=stopped, resumed=resumed, resume_started=resume_started,
                publication_attempted=publication_attempted,
                failed_resume_drain=drain, provider_calls=0, automatic_retry=False))
            if drain is not None:
                prior.write_new(out / 'failed-resume-drain.json', drain)
                require(drain['all_units_inactive'], 'failed_resume_drain_incomplete')
            if stopped and not publication_attempted and not resume_started:
                try:
                    verify_original_before_resume(original, guard, prepared)
                except BaseException as recovery_error:
                    prior.write_new(out / 'original-recovery-refused.json', failure_diagnostics(recovery_error))
                    raise Refusal('original_recovery_refused_inspect_retained_evidence') from None
                for unit in (prior.UNITS[2], *prior.UNITS[:2]):
                    host.service('start', unit)
                prior.write_new(out / 'original-release-resumed.json', {'release': BASE})
            raise Refusal('installation_failed_inspect_retained_evidence') from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true'); parser.add_argument('--plan'); parser.add_argument('--plan-sha256')
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps(dict(inert=True, database_queries=0, provider_calls=0, service_actions=0))); return
    os.umask(0o077); sys.dont_write_bytecode = True
    plan, digest = prior.private_json(Path(args.plan))
    require(digest == args.plan_sha256, 'private_plan_hash')
    validate_plan(plan)
    with bound_primitives():
        print(json.dumps(execute(plan, digest), sort_keys=True))


if __name__ == '__main__':
    main()
