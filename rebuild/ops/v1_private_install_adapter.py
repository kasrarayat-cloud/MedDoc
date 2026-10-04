"""The preserving 0018→0037 lifecycle used by the normal private installer.

Only the explicitly supplied backend can perform actions. The command-line door
constructs its fixed reviewed backend after live source/PR/CI and product gates;
tests supply a simulated backend. There is no rollback, alternate command, live
payment, provider request or new infrastructure path here.
"""
import json
import re

from . import v1_private_install_preparation as preparation


NONCORE = frozenset({'auth_group', 'auth_group_permissions', 'auth_permission',
                    'django_content_type', 'django_migrations', 'django_session', 'otp_totp_totpdevice'})
CATALOG_KEYS = frozenset({'tables', 'schema', 'constraints', 'indexes', 'catalog'})
CATALOG_SOURCES = frozenset({'rebuild/core/models.py', 'rebuild/ops/integrity_contract.py',
                             'rebuild/ops/v1_install_catalog.py', 'rebuild/ops/database_roles.py'})
PRESERVED_KEYS = frozenset({'storage', 'unit_files', 'shared_configs', 'protected', 'operations'})


def require(value, message):
    preparation.require(value, message)


def canonical(value):
    return json.loads(json.dumps(value, sort_keys=True))


def schema_catalog(snapshot, *, owner):
    """Normalize only the known schema-owner spelling, retaining privileges.

    QA and the installed database use different named owners. An unexpected
    function owner is an error, never an owner to learn from the inspected data.
    Owners/configuration/ACL and function/trigger bodies remain in the contract.
    """
    require(isinstance(owner, str) and re.fullmatch('[a-z_][a-z_0-9]*', owner), 'Declared schema owner required.')
    result = canonical({key: snapshot[key] for key in CATALOG_KEYS})
    for row in result['catalog']['functions']:
        require(row['owner'] == owner, 'Unexpected SQL function owner.')
        row['owner'] = '<schema-owner>'
        if row.get('acl') is not None:
            require(isinstance(row['acl'], str), 'SQL function ACL must retain its exact catalog spelling.')
            row['acl'] = re.sub(r'(?<![a-z_0-9])' + re.escape(owner) + r'(?![a-z_0-9])',
                                '<schema-owner>', row['acl'])
    return result


def validate_catalog_contract(raw, sources, schema_bytes):
    require(isinstance(raw, bytes) and raw, 'Frozen synthetic PostgreSQL catalog contract is absent.')
    value = json.loads(raw)
    require(set(value) == {'format', 'baseline', 'source_sha256', 'schema_sha256',
                           'before', 'after', 'new_permissions', 'new_content_types'}
            and value['format'] == 'quillmd-v1-postgresql-upgrade-contract-v1'
            and value['baseline'] == preparation.BASELINE
            and value['schema_sha256'] == preparation.sha(schema_bytes), 'Catalog contract identity differs.')
    schema = json.loads(schema_bytes)
    paths = CATALOG_SOURCES | {'rebuild/core/migrations/' + name + '.py'
            for name in {**schema['baseline_prefix_sha256'], **schema['forward_migration_sha256']}}
    require(value['source_sha256'] == {path: preparation.sha(sources[path]) for path in paths},
            'PostgreSQL rehearsal covers different source bytes.')
    require(set(value['before']) == CATALOG_KEYS and set(value['after']) == CATALOG_KEYS,
            'Full schema/index/constraint/function/trigger contract required.')
    require(set(value['before']['tables']) == set(schema['baseline_core_columns']) | NONCORE
            and set(value['after']['tables']) == set(schema['candidate_core_columns']) | NONCORE,
            'Catalog table membership differs; counts cannot substitute for identities.')
    for key in ('new_permissions', 'new_content_types'):
        require(isinstance(value[key], list) and value[key] == sorted(value[key])
                and len({json.dumps(row) for row in value[key]}) == len(value[key]),
                'Post-migrate semantic additions must be exact and unique.')
    return value


def verify_migration_plan(plan, schema, *, applied):
    rows = [re.fullmatch(r'\[([X ])\]\s+([a-z_][a-z_0-9]*\.[a-z_0-9]+)', line.strip())
            for line in plan.splitlines() if line.strip()]
    require(rows and all(rows), 'Migration plan cannot be parsed completely.')
    names = [row[2] for row in rows]
    require(len(names) == len(set(names)), 'Repeated migration in the plan.')
    expected = {'core.' + name for name in schema['forward_migration_sha256']}
    require({name for name in names if name.startswith('core.')} == expected | {
                'core.' + name for name in schema['baseline_prefix_sha256']}, 'Reviewed core graph differs.')
    pending = {row[2] for row in rows if row[1] != 'X'}
    require(pending == (set() if applied else expected), 'An undeclared migration is pending or missing.')


def validate_transition(before, after, schema, contract, *, owner):
    """Compare complete old-row projections; allow only reviewed recorder/permission additions."""
    require(schema_catalog(before, owner=owner) == contract['before']
            and schema_catalog(after, owner=owner) == contract['after'],
            'Actual PostgreSQL schema differs from the frozen synthetic contract.')
    require(set(before['rows']) == set(contract['before']['tables'])
            and after['old_rows'] == before['rows'] and after['old_columns'] == before['columns'],
            'A historical column, row or fingerprint changed.')
    for key in PRESERVED_KEYS:
        require(before[key] == after[key], 'Undeclared preserved-state delta: ' + key)
    require(after['new_core_rows'] == {name: {'rows': 0, 'sha256': preparation.sha(b'')}
                for name in schema['new_core_tables']}, 'Unexpected new clinical/financial records appeared.')
    require(after['new_noncore_rows'] == {
        'django_migrations': sorted([['core', name] for name in schema['forward_migration_sha256']]),
        'django_content_type': contract['new_content_types'], 'auth_permission': contract['new_permissions']},
        'Unexpected recorder, permission, session or other non-core records appeared.')
    require(after['unresolved_jobs'] == 0 and after['held_reservations'] == 0,
            'A job or unresolved charge appeared during the stopped transition.')
    return {'historical_tables_preserved': len(before['rows']),
            'new_core_tables_empty': len(schema['new_core_tables']), 'full_postgresql_catalog_verified': True}


def activate(backend, declaration, schema_bytes, source_bytes, evidence, catalog_bytes):
    """Execute only after the command's normal-door live validation.

    A failure always asks the same fixed backend to stop the three private
    surfaces and retains its original phase/error. No automatic old-source,
    schema, environment or backup restoration is available.
    """
    preparation.plan(declaration, schema_bytes, source_bytes, evidence, destination='installed_qualified_v1')
    contract = validate_catalog_contract(catalog_bytes, source_bytes, schema_bytes)
    schema = json.loads(schema_bytes)
    outcome = {'target': declaration['target'], 'baseline': preparation.BASELINE,
               'complete': False, 'provider_calls': 0, 'live_payments': 0,
               'fresh_restore_drill_performed': False, 'phases': []}
    # This also checks the ruled declaration, CI/PR/source a second time, package
    # compatibility, clean drained jobs/holds and reusable recovery identities.
    backend.validate_live(declaration, evidence, contract)
    backend.create_unused_evidence(outcome)
    try:
        with backend.exclude_publication():
            for phase in ('stop', 'retain_stopped_baseline', 'advance_exact_source',
                          'apply_reviewed_graph', 'verify_stopped_preservation',
                          'install_reviewed_static_and_environment', 'start_and_verify'):
                outcome['stage'] = phase
                outcome['phases'].append(phase)
                backend.checkpoint(outcome)
                if phase == 'stop':
                    backend.stop()
                elif phase == 'retain_stopped_baseline':
                    before = backend.snapshot()
                    require(schema_catalog(before, owner=backend.schema_owner) == contract['before'],
                            'Stopped installed schema is not the declared baseline.')
                    require(before['unresolved_jobs'] == before['held_reservations'] == 0, 'Jobs/holds are unresolved.')
                    backend.retain_recovery(before)
                elif phase == 'advance_exact_source':
                    backend.assert_stopped(); backend.advance_source(declaration['target'])
                elif phase == 'apply_reviewed_graph':
                    backend.assert_stopped()
                    verify_migration_plan(backend.migration_plan(), schema, applied=False)
                    backend.migrate(preparation.LEAF)
                    verify_migration_plan(backend.migration_plan(), schema, applied=True)
                elif phase == 'verify_stopped_preservation':
                    after = backend.snapshot(before=before)
                    outcome['preservation'] = validate_transition(before, after, schema, contract, owner=backend.schema_owner)
                    backend.retain_transition(before, after)
                elif phase == 'install_reviewed_static_and_environment':
                    backend.install_assets_and_environment()
                    # Static/environment have separately validated, declared
                    # deltas. All clinical/financial/state rows and old assets
                    # must still be exact before any private process starts.
                    backend.verify_installed_stopped(before, contract)
                else:
                    backend.start_and_verify(declaration['target'], before, contract)
        backend.verify_publication_restored()
        outcome.update(complete=True, stage='complete')
        backend.checkpoint(outcome)
        return outcome
    except BaseException as error:
        outcome.update(failure_kind=type(error).__name__, complete=False)
        # The user-facing error is deliberately generic. Its original cause,
        # traceback and child output must already exist in protected evidence;
        # a phase/type-only checkpoint cannot explain a failed migration.
        try:
            outcome['failure_evidence'] = backend.record_failure(error, 'activation')
            outcome['failure_evidence_retained'] = True
        except BaseException as retention_error:
            outcome.update(failure_evidence_retained=False,
                           retention_failure_kind=type(retention_error).__name__)
        try:
            backend.stop(); backend.assert_stopped(); outcome['failure_services_stopped'] = True
        except BaseException as stop_error:
            outcome.update(failure_services_stopped=False, stop_failure_kind=type(stop_error).__name__)
            try:
                outcome['stop_failure_evidence'] = backend.record_failure(stop_error, 'failure_stop')
            except BaseException:
                outcome['stop_failure_evidence_retained'] = False
        backend.checkpoint(outcome)
        raise RuntimeError('Private activation stopped; inspect retained original evidence before a forward repair.') from None
