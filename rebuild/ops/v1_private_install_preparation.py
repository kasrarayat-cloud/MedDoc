"""Pure preparation for a new reviewed private synthetic installation adapter.

No file, environment, database, process, provider or host action is performed.
This binds the prospective declaration and checks preservation inputs supplied
by the normal driver. A returned plan is not an execution authorization or a
replacement for live source/PR/CI/state checks through the existing procedure.
Historical activation drivers and their declarations stay unchanged.
"""
import hashlib
import json
from pathlib import PurePosixPath
import re

BASELINE = 'dedac1625032e32c7a149e6771be22e26c307eb1'
BASELINE_NODE = '0018_servicehealth'
LEAF = '0038_reinspection_confirmation_guard'
SCHEMA_PATH = 'docs/rebuild/v1/private-synthetic-install-preparation-20261004/schema-contract-0038.json'
SCHEMA_SHA256 = '47e45ec7ff94ce89cfa3ce8f3fbc514fa05eddb5e88e480d1ed58fa26706da96'
WORKFLOWS = frozenset({'CI', 'secrets-scan'})
MODEL = 'claude-sonnet-5-5'
CONTRACT = 'ordinary-field-relations-v4'
REQUIRED_SOURCE = frozenset({
    'rebuild/core/generation.py', 'rebuild/core/jobs.py', 'rebuild/core/views.py',
    'rebuild/core/models.py', 'rebuild/core/reviewed_source.py',
    'rebuild/templates/encounter_input.html', 'rebuild/templates/template_detail_v3.html',
    'rebuild/core/import_binding.py', 'rebuild/core/v3_mapping.py', 'rebuild/documents/word_v3.py',
    'rebuild/quillmd/settings.py', 'rebuild/quillmd/application_profile.py', 'rebuild/requirements.txt',
    'rebuild/ops/ordinary_generation_activation.py', 'rebuild/ops/v1_private_install_preparation.py',
})
UNITS = ('quillmd-fresh-doctor.service', 'quillmd-fresh-admin.service', 'quillmd-fresh-worker.service')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_contract(declaration, schema_bytes, source_bytes):
    """Validate declared bytes and the installed migration prefix, not full-tree completeness."""
    require(isinstance(declaration, dict) and set(declaration) == {
        'format', 'baseline', 'target', 'schema_sha256', 'source_sha256', 'data_mode',
        'payment_mode', 'public_maintenance', 'cpt_enabled'}, 'Declaration shape differs.')
    require(declaration['format'] == 'quillmd-private-v1-preparation-v1'
            and declaration['baseline'] == BASELINE
            and isinstance(declaration['target'], str)
            and re.fullmatch('[a-f0-9]{40}', declaration['target'])
            and declaration['target'] != BASELINE, 'Exact baseline and candidate revisions required.')
    require(declaration['data_mode'] == 'synthetic' and declaration['payment_mode'] == 'test'
            and declaration['public_maintenance'] is True and declaration['cpt_enabled'] is False,
            'This preparation preserves the private synthetic boundary.')
    require(isinstance(schema_bytes, bytes) and sha(schema_bytes) == SCHEMA_SHA256
            and declaration['schema_sha256'] == SCHEMA_SHA256, 'Reviewed schema source changed.')
    schema = json.loads(schema_bytes)
    require((schema['baseline_core_migration'], schema['candidate_core_migration']) == (BASELINE_NODE, LEAF)
            and schema['removed_core_tables'] == [] and len(schema['forward_migration_sha256']) == 20,
            'Reviewed forward migration graph differs.')
    sources = declaration['source_sha256']
    require(isinstance(sources, dict) and isinstance(source_bytes, dict)
            and set(sources) == set(source_bytes) and REQUIRED_SOURCE <= set(sources),
            'Required declared source bytes missing or mismatched.')
    expected_migrations = {
        'rebuild/core/migrations/' + name + '.py'
        for name in {**schema['baseline_prefix_sha256'], **schema['forward_migration_sha256']}}
    require({p for p in sources if p.startswith('rebuild/core/migrations/') and p.endswith('.py')
             and not p.endswith('/__init__.py')} == expected_migrations,
            'An undeclared migration cannot be omitted from the reviewed graph.')
    for path, expected in sources.items():
        name = PurePosixPath(path)
        require(not name.is_absolute() and str(name) == path and '..' not in name.parts
                and '.runtime' not in name.parts
                and (not name.name.startswith('.env') or name.name == '.env.example'), 'Non-source input refused.')
        require(isinstance(source_bytes[path], bytes) and isinstance(expected, str)
                and re.fullmatch('[a-f0-9]{64}', expected) and sha(source_bytes[path]) == expected,
                'Candidate source digest differs.')
    for name, expected in {**schema['baseline_prefix_sha256'], **schema['forward_migration_sha256']}.items():
        path = 'rebuild/core/migrations/' + name + '.py'
        require(sources.get(path) == expected, 'Installed prefix or declared forward migration changed.')
    return schema


def citation(target, records):
    """Check normalized receipts; the actual driver must independently run check-citation.sh on target."""
    require(isinstance(records, list) and len(records) == len(WORKFLOWS)
            and {r.get('workflow') for r in records} == WORKFLOWS, 'Required workflow receipts incomplete.')
    for row in records:
        require(row.get('head_sha') == target and row.get('status') == 'completed'
                and row.get('conclusion') == 'success' and type(row.get('run_id')) is int and row['run_id'] > 0
                and type(row.get('attempt')) is int and row['attempt'] >= 1, 'Exact-revision successful citation required.')
        require(row['attempt'] == 1 or bool(row.get('rerun_reason', '').strip()), 'A rerun needs its retained reason.')


def plan(declaration, schema_bytes, source_bytes, evidence, *, destination):
    schema = source_contract(declaration, schema_bytes, source_bytes)
    target = declaration['target']
    citation(target, evidence.get('ci'))
    require(destination in ('isolated_fixture_demo', 'installed_qualified_v1'), 'Unknown private destination.')
    require(evidence.get('source_refutation', {}).get('target') == target
            and evidence['source_refutation'].get('clinical_unsafe') == 0
            and evidence['source_refutation'].get('word_unsafe') == 0
            and evidence['source_refutation'].get('complete') is True,
            'Candidate source safety evidence is required separately from CI.')
    if destination == 'isolated_fixture_demo':
        require(evidence.get('ai_mode') == 'fixture' and evidence.get('isolated_state') is True,
                'The demonstration exception requires separate fixture-only state.')
        phases = ('archive_exact_candidate', 'prepare_isolated_synthetic_database_and_state',
                  'apply_isolated_forward_graph', 'build_fixture_demo', 'verify_actual_doctor_admin_worker_and_workflows')
    else:
        require(evidence.get('exact_merged_pr', {}).get('target') == target
                and evidence['exact_merged_pr'].get('base') == 'main'
                and evidence['exact_merged_pr'].get('merged') is True,
                'Exact merged PR receipt required by the normal installation procedure.')
        word = evidence.get('word', {})
        require(word.get('target') == target and word.get('overall_total') == 60
                and type(word.get('overall_pass')) is int and 54 <= word['overall_pass'] <= 60
                and word.get('holdout_total') == 20 and type(word.get('holdout_pass')) is int
                and 18 <= word['holdout_pass'] <= 20 and 54 <= word.get('eligible_overall', 0) <= 60
                and word.get('family_protocol_passed') is True and word.get('safety_protocol_passed') is True
                and word.get('manual_recovery_counted_as_automatic') is False,
                'B-W1 remains unmet; preserve the fixed corpus, family, safety and automatic-correctness gates.')
        model = evidence.get('generation', {})
        require(model.get('target') == target and model.get('requested_model') == MODEL
                and model.get('returned_model') == MODEL and model.get('ordinary_field_contract') == CONTRACT
                and model.get('usefulness_qualified') is True and model.get('unsafe_answers') == 0,
                'Live source-bound model and useful generation gates remain unmet.')
        require(evidence.get('populated_upgrade', {}).get('migration_sha256') == schema['forward_migration_sha256']
                and evidence['populated_upgrade'].get('passed') is True,
                'The actual populated forward upgrade must cover these exact migrations.')
        phases = ('live_validate_exact_pr_citation_source_scope_and_state',
                  'coordinate_existing_publication_and_alert_participants', 'drain_and_resolve_jobs_and_reservations',
                  'stop_only_declared_private_surfaces', 'capture_stopped_rows_files_schema_environment_static_and_recovery',
                  'retain_prior_source_environment_and_static', 'advance_shared_main_to_exact_merged_candidate',
                  'apply_exact_twenty_forward_migrations', 'verify_every_old_column_and_file_and_declared_new_schema',
                  'prepare_reviewed_ordinary_model_environment', 'install_source_bound_static_keep_historical_assets',
                  'restart_and_verify_exact_doctor_admin_worker_and_synthetic_workflows')
    return {'format': 'quillmd-private-v1-preparation-v1', 'target': target, 'baseline': BASELINE,
            'destination': destination, 'execution_authorized': False, 'installed_mutation_performed': False,
            'normal_driver_live_checks_required': True, 'forward_migrations': list(schema['forward_migration_sha256']),
            'private_units': list(UNITS) if destination == 'installed_qualified_v1' else [], 'phases': list(phases),
            'rollback': 'Stop on failure, retain current evidence/state/schema, prefer a cited forward repair. '
                        'No automatic old-source checkout, down-migration or snapshot restoration.'}


def preserve_stopped_inventory(schema_bytes, before, after):
    """Verify source-bound old-column projection hashes, exact column identities and retained file hashes.

    The normal driver produces projections from the real stopped database, with
    schema/source receipts retained. Supplied digests never substitute for that
    capture. No row contents or secrets are included in errors or return data.
    """
    require(isinstance(schema_bytes, bytes) and sha(schema_bytes) == SCHEMA_SHA256, 'Reviewed schema source changed.')
    schema = json.loads(schema_bytes)
    old_columns, new_columns = schema['baseline_core_columns'], schema['candidate_core_columns']
    require(before.get('core_columns') == old_columns and after.get('core_columns') == new_columns,
            'Actual baseline or target column identities differ from the reviewed source contract.')
    require(after.get('projection_columns') == old_columns,
            'Every historical column must remain in the preservation projection.')
    require(set(before.get('core_rows', {})) == set(old_columns)
            and after.get('old_core_rows') == before['core_rows'], 'Historical core row fingerprints changed.')
    for row in before['core_rows'].values():
        require(isinstance(row, dict) and set(row) == {'rows', 'sha256'}
                and type(row['rows']) is int and row['rows'] >= 0
                and isinstance(row['sha256'], str) and re.fullmatch('[a-f0-9]{64}', row['sha256']),
                'Historical row fingerprint is malformed.')
    require(set(after.get('new_core_rows', {})) == set(schema['new_core_tables'])
            and all(row == {'rows': 0, 'sha256': sha(b'')} for row in after['new_core_rows'].values()),
            'Unexpected records appeared in new clinical/financial tables during the stopped migration.')
    require(after.get('files') == before.get('files') and isinstance(before.get('files'), dict)
            and before['files'], 'An original, recording, receipt, final download or other private file changed.')
    for path, record in before['files'].items():
        require(isinstance(path, str) and path and not PurePosixPath(path).is_absolute()
                and str(PurePosixPath(path)) == path and '..' not in PurePosixPath(path).parts
                and isinstance(record, dict) and set(record) == {'sha256', 'bytes'}
                and isinstance(record['sha256'], str) and re.fullmatch('[a-f0-9]{64}', record['sha256'])
                and type(record['bytes']) is int and record['bytes'] >= 0,
                'Historical private file fingerprint is malformed.')
    require(after.get('unrelated_services') == before.get('unrelated_services')
            and before.get('unrelated_services'), 'Protected unrelated service identities changed.')
    return {'old_core_tables_preserved': len(old_columns), 'new_core_tables_empty': len(schema['new_core_tables']),
            'private_files_preserved': len(before['files']), 'execution_authorized': False}
