"""Declared core workflow repair installation; inert without an exact new plan.

This code-only boundary preserves all current rows and clinical files. Only the release stamp and the
explicitly bound app.js aliases/manifest may change; old hashed assets remain. It submits no provider work and does
not reopen any saved clinical or coding decision.
"""
import argparse
from contextlib import ExitStack, contextmanager
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile

from dotenv import dotenv_values
from dotenv.parser import parse_stream
from . import activate_rowan_corti as prior
from . import activate_coordinated_workflow as preservation

BASE = '179c3030f6ded40bd6c6bd1d0f02909472988943'
SOURCE = Path(__file__).resolve().parents[2]
FORMAT = 'quillmd-core-workflow-repair-native-install-v1'
STATIC = frozenset({'app.js'})
TABLE_FINGERPRINT_CONTRACT = 'sha256-sorted-jsonb-row-sha256-count-v1'
ROW_HASH_BATCH_SIZE = 128
RUNTIME = frozenset({'rebuild/core/semantic_generation.py', 'rebuild/core/clinical_semantics.py',
    'rebuild/core/jobs.py', 'rebuild/core/clinical_source_context.py',
    'rebuild/core/preparation.py', 'rebuild/core/preparation_views.py', 'rebuild/core/word_contract.py',
    'rebuild/core/source_assertion_coding.py',
    'rebuild/core/coding_engine.py', 'rebuild/core/coding_service.py', 'rebuild/core/coding.py',
    'rebuild/core/coding_views.py', 'rebuild/core/coding_export.py',
    'rebuild/core/coding_draft_export.py', 'rebuild/core/coding_source_review.py',
    'rebuild/core/coding_recovery.py', 'rebuild/core/coding_hooks.py', 'rebuild/core/semantic_preparation.py',
    'rebuild/core/coding_dispatch.py', 'rebuild/core/corti_coding.py',
    'rebuild/core/corti_semantics.py', 'rebuild/core/documented_time_source.py',
    'rebuild/core/coding_source_assertions.py', 'rebuild/core/coding_completeness.py',
    'rebuild/core/coding_reference_store.py',
    'rebuild/core/semantic_revalidation.py', 'rebuild/documents/preparation.py',
    'rebuild/documents/complete_narrative_contracts.py', 'rebuild/static/app.js',
    'rebuild/templates/coding_panel.html',
    'rebuild/templates/template_semantic_definition_editor.html'})
SUPPORT = frozenset({'rebuild/ops/activate_core_workflow_repair.py',
    'rebuild/ops/test_activate_core_workflow_repair.py', 'rebuild/ops/test_submission_recovery.cjs',
    'rebuild/documents/test_preparation.py',
    'rebuild/core/tests/test_clinical_semantics.py',
    'rebuild/core/tests/test_current_coding_identity.py',
    'rebuild/core/tests/test_semantic_reference_contract.py',
    'rebuild/core/tests/test_source_context_jobs.py',
    'rebuild/core/tests/test_source_assertion_coding.py',
    'rebuild/core/tests/test_word_answer_contract.py',
    'rebuild/core/tests/test_positioned_time_account.py',
    'rebuild/core/tests/test_shared_coding_source.py',
    'rebuild/core/tests/test_documented_coding_time.py',
    'rebuild/core/tests/test_core_workflow_repair.py',
    'docs/runbooks/core-workflow-repair-install-20261020.md', '.github/workflows/test.yml'})
require, Refusal = prior.require, prior.Refusal


@contextmanager
def bound_primitives():
    """Reuse low-level publication primitives, never a consumed activation."""
    saved = {key: getattr(prior, key) for key in ('BASE', 'SOURCE', 'STATIC')}
    prior.BASE, prior.SOURCE, prior.STATIC = BASE, SOURCE, STATIC
    try:
        yield
    finally:
        for key, value in saved.items():
            setattr(prior, key, value)


def validate_plan(plan):
    require(type(plan) is dict and set(plan) == {'format', 'base', 'candidate', 'source_sha256',
        'source_worktree', 'evidence_directory', 'environment_before_sha256', 'environment', 'static'},
        'closed_coordinated_workflow_plan')
    require(plan['format'] == FORMAT and plan['base'] == BASE
            and re.fullmatch('[a-f0-9]{40}', plan['candidate']) and plan['candidate'] != BASE,
            'exact_coordinated_workflow_revision')
    require(re.fullmatch('[a-f0-9]{64}', plan['environment_before_sha256']), 'environment_pin')
    paths = plan['source_sha256']
    require(type(paths) is dict and 0 < len(paths) <= len(RUNTIME | SUPPORT) and RUNTIME.intersection(paths),
            'finite_coordinated_workflow_source_manifest')
    for name, digest in paths.items():
        path = PurePosixPath(name)
        require(name == str(path) and not path.is_absolute()
                and name in RUNTIME | SUPPORT
                and re.fullmatch('[a-f0-9]{64}', digest), 'only_coordinated_workflow_source')
    require(type(plan['environment']) is dict and plan['environment'] == {}, 'release_stamp_only')
    require(type(plan['static']) is list and plan['static'] == sorted(STATIC), 'only_app_js_static_publication')
    out = Path(plan['evidence_directory']); source = Path(plan['source_worktree'])
    require(out.is_absolute() and out.parent.resolve() == out.parent and not out.exists()
            and not out.is_symlink() and out.parent.stat().st_uid == os.getuid()
            and stat.S_IMODE(out.parent.stat().st_mode) == 0o700, 'exclusive_private_output')
    require(source.is_absolute() and source.resolve() == source and source == SOURCE, 'exact_operator_worktree')
    require('rebuild/static/app.js' in paths, 'static_source_bound')


def render_environment(original, revision, environment):
    require(type(environment) is dict and environment == {}, 'release_stamp_only')
    require(re.fullmatch('[a-f0-9]{40}', revision) and revision != BASE, 'exact_coordinated_workflow_revision')
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


def unchanged(before, after, *, health_may_tick=False):
    # Periodic health writers may update existing health rows while services are
    # still running. No other row, sequence or schema difference is permitted.
    if health_may_tick:
        from copy import deepcopy
        before, after = deepcopy(before), deepcopy(after)
        key = 'core_servicehealth'
        require(key in before['tables'] and key in after['tables']
                and before['tables'][key][0] == after['tables'][key][0], 'health_population_unchanged')
        after['tables'][key] = before['tables'][key]
    require(before == after, 'all_current_database_state_unchanged')
    require(not any(after['pending'].values()), 'no_provider_work_during_install')


# Reuse only the complete read-only snapshot and fixed diagnostic primitives.
# No historical activation driver or historical plan is invoked.
snapshot = preservation.snapshot
failure_diagnostics = preservation.failure_diagnostics
stop_failed_resume = preservation.stop_failed_resume


def verify_static_rollback(archive_path, inventory):
    """Read back every rollback byte without extracting or changing live files."""
    expected = {name: row for name, row in inventory.items() if row['kind'] == 'file'}
    seen = set()
    with tarfile.open(archive_path, 'r:') as archive:
        for member in archive:
            require(member.name in expected and member.name not in seen and member.isfile(),
                    'exact_static_rollback_members')
            row = expected[member.name]
            require(member.size == row['size'] and member.mode == row['mode'], 'static_rollback_metadata')
            stream = archive.extractfile(member)
            require(stream is not None, 'static_rollback_file')
            with stream:
                raw = stream.read(row['size'] + 1)
            require(len(raw) == row['size'] and prior.sha(raw) == row['sha256'], 'static_rollback_bytes')
            seen.add(member.name)
    require(seen == set(expected), 'complete_static_rollback')
    return {'files': len(seen), 'archive_sha256': prior.sha(archive_path.read_bytes()),
            'all_file_bytes_match': True, 'extracted_files': 0}


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


def execute(plan, digest):
    validate_plan(plan)
    require(Path.cwd().resolve() == prior.ROOT, 'permanent_native_actuation_directory')
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
    guard = prior.source_guard(); prepared = prior.source_plan(plan, guard)
    prior.command(['bash', str(SOURCE / 'scripts/check-citation.sh'), plan['candidate']], cwd=SOURCE, timeout=120)
    out = Path(plan['evidence_directory']); out.mkdir(mode=0o700)
    prior.write_new(out / 'plan.json', plan)
    cipher = prior.backup_restore.key_at(prior.legacy.KEY)
    prior.write_new(out / 'environment-before.fernet', cipher.encrypt(original))
    prior.write_new(out / 'environment-after.fernet', cipher.encrypt(active))
    require(cipher.decrypt((out / 'environment-before.fernet').read_bytes()) == original,
            'rollback_environment_decryption')
    stopped = resumed = resume_started = publication_attempted = False
    stage = 'static_baseline'
    host = prior.legacy.Host(prior.managed_helper)
    with ExitStack() as coordination:
        try:
            primitives = prior.legacy.static_primitives()
            primitives.static_delta = prior.static_delta
            static_stage, static_before, staged = prior.stage_static(plan, out, primitives)
            rollback = verify_static_rollback(out / 'static-before.tar', static_before)
            prior.write_new(out / 'rollback-readback.json', dict(environment_decryption_matches=True,
                source_revision=BASE, static=rollback, live_restore_actions=0))
            prior.activation_exclusion.bind_runtime(prior.APP / '.runtime')
            stage = 'coordination_locks'
            coordination.enter_context(prior.legacy.operation_locks())
            coordination.enter_context(prior.activation_exclusion.hold(
                'core-workflow-repair:' + plan['candidate'][:12], timeout=30))
            baseline = {'static': static_before}
            stage = 'baseline_configuration'; baseline['configuration'] = host.configuration()
            stage = 'baseline_foreign_services'; baseline['services'] = prior.foreign_services()
            stage = 'baseline_database'; baseline['database'] = snapshot(original)
            stage = 'baseline_clinical_files'; baseline['files'] = prior.private_storage.inventory(Path('/var/lib/quillmd/files'))
            stage = 'baseline_pending_check'; unchanged(baseline['database'], baseline['database'])
            stage = 'retain_baseline'; prior.write_new(out / 'baseline.json', baseline)
            # Preparation precedes lock acquisition. An earlier owner may have
            # completed publication while this operation was preparing/waiting.
            # Revalidate the whole installed cut under the locks before stopping
            # any service; post-stop publication checks alone are too late.
            stage = 'revalidate_before_stop'
            require(prior.source_plan(plan, guard) == prepared, 'source_cut_unchanged_before_stop')
            require((prior.APP / '.env').read_bytes() == original, 'environment_unchanged_before_stop')
            require(primitives.static_inventory(prior.APP / 'staticfiles') == static_before,
                    'static_unchanged_before_stop')
            require(all(host.state(unit)['ActiveState'] == 'active' and host.state(unit)['MainPID'] != '0'
                        for unit in prior.UNITS), 'owned_units_active_before_stop')
            stage = 'stop_owned_services'; stopped = True
            for unit in prior.UNITS:
                host.service('stop', unit)
            stage = 'verify_owned_services_stopped'
            require(all(host.state(unit)['ActiveState'] == 'inactive' and host.state(unit)['MainPID'] == '0'
                        for unit in prior.UNITS), 'owned_units_drained')
            stage = 'database_after_stop'; after_stop = snapshot(original)
            stage = 'retain_database_after_stop'
            prior.write_new(out / 'database-after-stop.json', after_stop)
            stage = 'database_after_stop'; unchanged(baseline['database'], after_stop, health_may_tick=True)
            stage = 'source_publication'; publication_attempted = True
            prior.publish_source(plan, guard, prepared)
            stage = 'static_publication'
            static_after = primitives.install_static(prior.APP / 'staticfiles', static_stage, static_before, staged)
            stage = 'environment_publication'
            require((prior.APP / '.env').read_bytes() == original, 'environment_concurrency')
            temporary = prior.APP / '.core-workflow-repair-env-pending'
            prior.write_new(temporary, active); temporary.replace(prior.APP / '.env')
            stage = 'database_before_resume'; before_resume = snapshot(active)
            stage = 'retain_database_before_resume'
            prior.write_new(out / 'database-before-resume.json', before_resume)
            stage = 'database_before_resume'; unchanged(after_stop, before_resume)
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
            prior.write_new(out / 'pre-resume-preservation.json', dict(after_stop_database_exact_before_resume=True,
                baseline_health_tick_only=True,
                files_preserved=True, static_inventory=static_after, evidence_sha256=evidence_sha256,
                provider_calls=0, migrations_executed=0,
                environment_delta=['QUILLMD_RELEASE_SHA'], static_sources=sorted(STATIC)))
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
                declaration_commit=commit, declaration_sha256=prior.sha(text),
                environment_delta=['QUILLMD_RELEASE_SHA'], static_sources=sorted(STATIC),
                strict_preservation_ends_before_resume=True)
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
