"""Declared code-only Rowan review-response installation; inert by default.

This boundary has no migration, credential, admission or clinical action. It
publishes one exact source/static delta and changes only the release stamp.
"""
import argparse
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

from dotenv import dotenv_values
from . import activate_rowan_corti as prior
from .activate_rowan_followup import snapshot

BASE = '057d65db7ddb97289e01e85da42cb48eb475c76f'
SOURCE = Path(__file__).resolve().parents[2]
FORMAT = 'quillmd-rowan-review-response-native-install-v1'
RUNTIME = frozenset({'rebuild/core/coding_views.py', 'rebuild/core/coding_service.py', 'rebuild/core/coding_output.py',
                     'rebuild/static/coding.js'})
SUPPORT = frozenset({'rebuild/ops/activate_rowan_response.py',
    'rebuild/ops/test_activate_rowan_response.py', 'rebuild/ops/test_coding_poll_save.cjs',
    'docs/runbooks/rowan-response-install-20261017.md'})
require, Refusal = prior.require, prior.Refusal


@contextmanager
def bound_primitives(static):
    """Reuse publication primitives without invoking a consumed controller."""
    saved = {k: getattr(prior, k) for k in ('BASE', 'SOURCE', 'STATIC')}
    prior.BASE, prior.SOURCE, prior.STATIC = BASE, SOURCE, frozenset(static)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(prior, name, value)


def validate_plan(plan):
    require(type(plan) is dict and set(plan) == {'format', 'base', 'candidate', 'source_sha256',
        'source_worktree', 'evidence_directory', 'environment_before_sha256', 'static'}, 'closed_response_plan')
    require(plan['format'] == FORMAT and plan['base'] == BASE
            and re.fullmatch('[a-f0-9]{40}', plan['candidate']) and plan['candidate'] != BASE, 'exact_response_revision')
    require(re.fullmatch('[a-f0-9]{64}', plan['environment_before_sha256']), 'environment_pin')
    paths = plan['source_sha256']
    require(type(paths) is dict and 0 < len(paths) <= 30 and RUNTIME.intersection(paths), 'finite_response_source_manifest')
    for name, digest in paths.items():
        path = PurePosixPath(name)
        require(name == str(path) and not path.is_absolute()
                and not any(part.startswith('.') for part in path.parts)
                and (name in RUNTIME | SUPPORT
                     or re.fullmatch(r'rebuild/core/tests/test_coding_[a-z0-9_]+\.py', name))
                and re.fullmatch('[a-f0-9]{64}', digest), 'only_review_response_source')
    static = plan['static']
    require(type(static) is list and static == sorted(set(static))
            and set(static) <= {'coding.js'}, 'only_coding_static')
    require(sorted('rebuild/static/' + n for n in static)
            == sorted(n for n in paths if n.startswith('rebuild/static/')), 'exact_changed_static')
    out = Path(plan['evidence_directory']); source = Path(plan['source_worktree'])
    require(out.is_absolute() and out.parent.resolve() == out.parent and not out.exists()
            and out.parent.stat().st_uid == os.getuid() and stat.S_IMODE(out.parent.stat().st_mode) == 0o700,
            'exclusive_private_output')
    require(source.is_absolute() and source.resolve() == source and source == SOURCE, 'exact_operator_worktree')


def render_environment(original, revision):
    values = dotenv_values(stream=io.StringIO(original.decode()), interpolate=False)
    require(values.get('QUILLMD_RELEASE_SHA') == BASE, 'exact_installed_release')
    lines, found = [], False
    for line in original.splitlines(keepends=True):
        match = re.match(rb'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=', line)
        if match and match[1] == b'QUILLMD_RELEASE_SHA':
            require(not found, 'duplicate_release_assignment'); found = True
            lines.append(('QUILLMD_RELEASE_SHA="' + revision + '"\n').encode())
        else:
            lines.append(line)
    require(found, 'release_assignment_found')
    result = b''.join(lines)
    after = dotenv_values(stream=io.StringIO(result.decode()), interpolate=False)
    require(after == {**values, 'QUILLMD_RELEASE_SHA': revision}, 'only_release_value_changed')
    return result


def unchanged(before, after):
    require(before == after, 'all_current_database_state_unchanged')
    require(not any(after['pending'].values()), 'no_provider_work_during_install')


def execute(plan, digest):
    validate_plan(plan)
    declaration = Path(os.environ.get('RULED_MUTATION_DECLARATION', ''))
    commit = os.environ.get('RULED_MUTATION_DECL_COMMIT', '')
    require(declaration.is_absolute() and declaration.is_file() and re.fullmatch('[a-f0-9]{40}', commit), 'ruled_declaration_required')
    text = declaration.read_bytes()
    require(all(x.encode() in text for x in (digest, plan['candidate'], FORMAT)), 'declaration_exact_plan')
    repo = Path(prior.command(['git', '-C', str(declaration.parent), 'rev-parse', '--show-toplevel']).decode().strip())
    require(prior.command(['git', '-C', str(repo), 'show', commit + ':' + declaration.relative_to(repo).as_posix()])
            == text, 'committed_declaration_bytes')
    original = prior.backup_restore.read_private(prior.APP / '.env', 65536)
    require(prior.sha(original) == plan['environment_before_sha256'], 'environment_before_pin')
    active = render_environment(original, plan['candidate'])
    guard = prior.source_guard(); prepared = prior.source_plan(plan, guard)
    prior.command(['bash', str(SOURCE / 'scripts/check-citation.sh'), plan['candidate']], cwd=SOURCE, timeout=120)
    out = Path(plan['evidence_directory']); out.mkdir(mode=0o700)
    prior.write_new(out / 'plan.json', plan)
    cipher = prior.backup_restore.key_at(prior.legacy.KEY)
    prior.write_new(out / 'environment-before.fernet', cipher.encrypt(original))
    prior.write_new(out / 'environment-after.fernet', cipher.encrypt(active))
    primitives = prior.legacy.static_primitives(); primitives.static_delta = prior.static_delta
    if plan['static']:
        stage, static_before, staged = prior.stage_static(plan, out, primitives)
    else:
        static_before = primitives.static_inventory(prior.APP / 'staticfiles')
    host = prior.legacy.Host(prior.managed_helper)
    prior.activation_exclusion.bind_runtime(prior.APP / '.runtime')
    stopped = resumed = False
    stage_name = 'prepared'
    with prior.legacy.operation_locks(), prior.activation_exclusion.hold('rowan-review-response:' + plan['candidate'][:12], timeout=30):
        try:
            baseline = dict(configuration=host.configuration(), services=prior.foreign_services(), database=snapshot(original),
                files=prior.private_storage.inventory(Path('/var/lib/quillmd/files')))
            unchanged(baseline['database'], baseline['database'])
            prior.write_new(out / 'baseline.json', baseline)
            stage_name = 'stop_owned_services'; stopped = True
            for unit in prior.UNITS:
                host.service('stop', unit)
            require(all(host.state(u)['ActiveState'] == 'inactive' and host.state(u)['MainPID'] == '0'
                        for u in prior.UNITS), 'owned_units_drained')
            unchanged(baseline['database'], snapshot(original))
            stage_name = 'source_publication'; prior.publish_source(plan, guard, prepared)
            stage_name = 'static_publication'
            if plan['static']:
                static_after = primitives.install_static(prior.APP / 'staticfiles', stage, static_before, staged)
            else:
                static_after = primitives.static_inventory(prior.APP / 'staticfiles')
                require(static_after == static_before, 'static_bytes_unchanged')
            stage_name = 'environment_publication'
            require((prior.APP / '.env').read_bytes() == original, 'environment_concurrency')
            temporary = prior.APP / '.rowan-review-response-env-pending'
            prior.write_new(temporary, active); temporary.replace(prior.APP / '.env')
            unchanged(baseline['database'], snapshot(active))
            require(prior.private_storage.inventory(Path('/var/lib/quillmd/files')) == baseline['files'], 'all_clinical_files_preserved')
            require(host.configuration() == baseline['configuration'] and prior.foreign_services() == baseline['services'],
                    'unrelated_configuration_services_preserved')
            prior.write_new(out / 'pre-resume-preservation.json', dict(all_database_state_unchanged=True,
                files_preserved=True, static_inventory=static_after, provider_calls=0, migrations_executed=0))
            stage_name = 'resume_owned_services'; resumed = True
            for unit in (prior.UNITS[2], *prior.UNITS[:2]):
                host.service('start', unit)
            health = prior.await_health(plan['candidate'])
            require(all(host.state(u)['ActiveState'] == 'active' for u in prior.UNITS), 'owned_units_active')
            require(host.configuration() == baseline['configuration'] and prior.foreign_services() == baseline['services'],
                    'foreign_services_after_resume')
            result = dict(format=FORMAT, installed_revision=plan['candidate'], complete=True, health=health,
                migrations_executed=0, provider_calls=0, clinician_decisions_created=0,
                strict_preservation_ends_before_resume=True)
            prior.write_new(out / 'installation-complete.json', result)
            return result
        except BaseException as error:
            prior.write_new(out / 'failure.json', dict(format=FORMAT, complete=False, stage=stage_name,
                failure_type=type(error).__name__, reason=str(error) if isinstance(error, Refusal) else 'protected_operational_failure',
                stopped=stopped, resumed=resumed, provider_calls=0, automatic_retry=False))
            if stopped and not resumed and prior.git('rev-parse', 'HEAD').decode().strip() == BASE:
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
    with bound_primitives(plan['static']):
        print(json.dumps(execute(plan, digest), sort_keys=True))


if __name__ == '__main__':
    main()
