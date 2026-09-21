#!/usr/bin/env python3
"""Narrow adapter of the qualified preserving activator for the private billing repair.

Production remains disabled. Reuse historical authenticated recovery evidence;
make no fresh backup/restore/provider request. Default remains read-only. The
inherited driver stops the three private writers before advancing shared main.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import types

SOURCE = Path(__file__).resolve().parents[1]
ROOT = Path('/opt/meddoc-pro')
APP = ROOT / 'rebuild'
PRIVATE = APP / '.runtime'
SELF = 'scripts/activate-business-readiness.py'
DRIVER = 'scripts/activate-private-readiness.py'
DRIVER_SHA256 = '846ef48e812cd187520eba34185ff6e50d83ba261c04946a4cd23b4e62ff48ec'
BASELINE = 'ab4d3659e43c5591477017d9685a7e3d50f8c59b'
RUNNING_RELEASE = '97597c2972072821a27f4ce840775c07fca48a63'
DECL = 'docs/foundation/mutations/20260921-quillmd-business-readiness.md'
MIGRATION = '0017_reconciliation_evidence_kind'
MIGRATION_PATH = 'rebuild/core/migrations/' + MIGRATION + '.py'
MIGRATION_SHA256 = '82453d071e34d737d84a3bf6a1b9caae56197214fec7f3c748125efec5ff7bcb'
PREVIOUS_MIGRATION = '0016_user_session_version'
EVIDENCE = PRIVATE / 'business-readiness-20260921'
RESTORED_RELEASE = '8aa1d1d4efe090d6f0e6e1bf7d594375ddca9940'
CAPTURE_RUN = '20260920T193915Z-9cc67364'
CAPTURE_SOURCE = '2f62e4fecb2ee5307d95bc21d0b501247814d234'
CAPTURE_MANIFEST_SHA256 = '2093841b6072dd0c8f08e33725f6651bf8978f7a4ea62aaaad0ebdeffe53bcae'
RUNTIME_ALLOWED = {
    SELF, MIGRATION_PATH, 'rebuild/core/models.py', 'rebuild/core/billing.py',
    'rebuild/core/forms.py', 'rebuild/core/views.py', 'rebuild/core/stripe_validation.py',
    'rebuild/core/management/commands/audit_billing.py',
    'rebuild/core/tests/test_billing_policy.py', 'rebuild/core/tests/test_reconciliation_evidence_kind.py',
    'rebuild/core/tests/test_stripe_environment.py', 'rebuild/core/tests/test_business_activation.py',
    'rebuild/templates/admin_dashboard.html', 'rebuild/templates/billing.html',
    'rebuild/templates/financial_detail.html',
}
BASELINE_OPERATION_PATHS = set(('''automatic_offsite backup_alerts install_backup_alerts install_backup_schedule
install_offsite_policy install_offsite_schedule managed_helper offsite_account_audit offsite_allocation
 offsite_backup offsite_operator offsite_renewal private_storage recovery_kit test_automatic_offsite
 test_backup_alerts test_install_backup_schedule test_install_offsite_policy test_install_offsite_schedule
 test_managed_helper test_offsite_account_audit test_offsite_allocation test_offsite_backup
 test_offsite_inventory_completeness test_offsite_operator test_offsite_renewal test_offsite_renewal_budget
 test_offsite_renewal_integration test_offsite_shared_accounting test_private_storage test_recovery_kit''').split())
BASELINE_OPERATION_PATHS = {'rebuild/ops/' + name + '.py' for name in BASELINE_OPERATION_PATHS}
OPERATIONAL_FILES = (
    'automatic-offsite/budget.json', 'backup-secrets/offsite-policy.json',
    'backup-secrets/offsite-allocation.json',
    'automatic-offsite/renewal/673a83fbcbfb8f88485acf4088ee44b8.ticket.json',
    'offsite-renewal-20260920/quillmd-renewal-handoff-20260921.zip',
    'recovery-custody-handoff-20260920/return-evidence/independent-key-restore/result.json',
)
EXPECTED_CHECK = ('core_costreconciliation', 'reconciliation_evidence_kind_known', 'c', '-',
    "CHECK (((evidence_kind)::text = ANY ((ARRAY['unclassified'::character varying, 'provider_report'::character varying, 'invoice'::character varying])::text[])))")
BACKUP_COMPARISONS = []


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def compiled_module(name, path, data):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


_driver_path = SOURCE / DRIVER
_driver_bytes = _driver_path.read_bytes()
require(sha(_driver_bytes) == DRIVER_SHA256, 'Qualified activation driver changed.')
base = compiled_module('_business_preserving_driver', _driver_path, _driver_bytes)
_original_snapshot = base.snapshot
_original_retained = base.retained_source_manifest
_original_backup = base.backup_evidence
_original_shared = base.shared_configs


def validate_changed(changed):
    require(all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                and str(PurePosixPath(name)) == name for name in changed), 'Changed path is not canonical.')
    required = RUNTIME_ALLOWED - {'rebuild/core/tests/test_billing_policy.py'}
    require(required | {DECL} <= changed, 'Required reviewed business repair is absent.')
    require(all(name in RUNTIME_ALLOWED or name == DECL
                or (name.startswith('docs/rebuild/') and name.endswith('.md')) for name in changed),
            'Undeclared source change.')
    require({p for p in changed if p.startswith('rebuild/core/migrations/')} == {MIGRATION_PATH},
            'Only the exact additive evidence migration may change.')


def validate_migration(source):
    require(sha(source) == MIGRATION_SHA256, 'Reviewed one-column evidence migration changed.')


def load(name, relative, target):
    # Every reused helper, including the newer cleanup-safe backup reader, must
    # match both the installed ab4d source and the exact target. No old-reader exception.
    path = ROOT / relative
    data = path.read_bytes()
    require(data == base.blob(BASELINE, relative) == base.blob(target, relative),
            'Qualified helper differs from baseline or target.')
    if str(APP / 'ops') not in sys.path:
        sys.path.insert(0, str(APP / 'ops'))
    if name == 'storage':
        load('managed_helper', 'rebuild/ops/managed_helper.py', target)
    module = compiled_module(name if name == 'managed_helper' else '_business_' + name, path, data)
    if name == 'word':
        module.systemd = managed_systemd
    if name == 'identity':
        writer = module.private_write
        module.private_write = lambda path, doc: writer(path, receipt(doc))
    return module


def managed():
    module = sys.modules.get('managed_helper')
    require(module is not None, 'Qualified managed helper must load before host actions.')
    return module


def managed_systemd(action, helper_image):
    helper = managed()
    require(action in ('start', 'stop') and helper_image == helper.IMAGE, 'Fixed private service action/image required.')
    code = ("import os,subprocess\nos.chroot('/host');os.chdir('/')\nsubprocess.run(" +
            repr(['systemctl', action, *base.UNITS]) + ',check=True)\n')
    helper.run_helper(['/usr/bin/docker', 'run', '--rm', '-i', '--pull=never', '--log-driver=none',
        '--network=none', '--pid=host', '--mount', 'type=bind,src=/,dst=/host,readonly',
        helper_image, 'python', '-B', '-'], input=code.encode(), timeout=200,
        failure_directory=EVIDENCE)


def shared_configs(helper_image):
    # Reuse the exact read-only hash program/validation, replace only its obsolete
    # Docker-client transport with the qualified bounded lifecycle implementation.
    helper = managed()
    require(helper_image == helper.IMAGE, 'Qualified hash helper required.')
    def bounded(command, **kwargs):
        require(command[:3] == ['docker', 'run', '--rm'] and kwargs.get('timeout') == 60,
                'Unexpected inherited hash-helper protocol.')
        result = helper.run_helper(command[:3] + ['--log-driver=none'] + command[3:],
            input=kwargs['input'].encode(), timeout=60, failure_directory=EVIDENCE)
        return subprocess.CompletedProcess(command, result.returncode, result.stdout.decode(), '')
    context = dict(_original_shared.__globals__, subprocess=types.SimpleNamespace(run=bounded, PIPE=subprocess.PIPE))
    return types.FunctionType(_original_shared.__code__, context)(helper_image)


def receipt(document):
    result = dict(document)
    if 'only_session_column_and_nonnegative_check_added' in result:
        result['only_reconciliation_evidence_column_and_enum_check_added'] = result.pop('only_session_column_and_nonnegative_check_added')
    if result.get('stage') == 'apply_only_declared_session_generation':
        result['stage'] = 'apply_only_declared_reconciliation_evidence_kind'
    if 'baseline' in result:
        result['activation_adapter'] = SELF
        result['fresh_backup_or_restore_performed'] = False
        result['backup_comparisons'] = list(BACKUP_COMPARISONS)
        result['recovery_basis'] = 'Historical authenticated capture and independent restore; complete stopped-row/file preservation. Historical capture is not asserted to cover current rows.'
    return result


def rows(old, *, exclude_new=False):
    result = {}
    for name in old.tables():
        where = " WHERE NOT (app='core' AND name='" + MIGRATION + "')" if exclude_new and name == 'django_migrations' else ''
        projection = "(to_jsonb(t) - 'evidence_kind')" if exclude_new and name == 'core_costreconciliation' else 'to_jsonb(t)'
        data = subprocess.check_output(old.PSQL + [f'COPY (SELECT {projection}::text AS value FROM "{name}" t{where} ORDER BY value) TO STDOUT'], timeout=600)
        result[name] = {'rows': len(data.splitlines()), 'sha256': sha(data)}
    return result


def check_schema(before, after):
    added = [row for row in after['schema'] if row['table_name'] == 'core_costreconciliation' and row['column_name'] == 'evidence_kind']
    require(not any(row['table_name'] == 'core_costreconciliation' and row['column_name'] == 'evidence_kind' for row in before['schema'])
            and len(added) == 1, 'Evidence column unexpectedly present or absent.')
    expected = {'table_name': 'core_costreconciliation', 'column_name': 'evidence_kind',
        'ordinal_position': 1 + max(row['ordinal_position'] for row in before['schema'] if row['table_name'] == 'core_costreconciliation'),
        'data_type': 'character varying', 'udt_name': 'varchar', 'is_nullable': 'NO',
        'column_default': None, 'numeric_precision': None, 'numeric_scale': None}
    require(added[0] == expected and [row for row in after['schema'] if row != added[0]] == before['schema'],
            'Evidence column definition or existing schema differs.')
    require(EXPECTED_CHECK not in before['constraints'] and after['constraints'].count(EXPECTED_CHECK) == 1
            and [row for row in after['constraints'] if row != EXPECTED_CHECK] == before['constraints'],
            'Only the exact evidence-kind check may be added.')


def verify_evidence_column(old):
    require(base.output(old.PSQL + ["SELECT count(*) FROM core_costreconciliation WHERE evidence_kind <> 'unclassified'"]) == '0',
            'Existing reconciliation evidence was classified without evidence.')
    require(base.output(old.PSQL + ["SELECT character_maximum_length FROM information_schema.columns WHERE table_schema='public' AND table_name='core_costreconciliation' AND column_name='evidence_kind'"]) == '16',
            'Evidence column length differs.')


def backup_evidence(path, modules, current_directory=None):
    current = PRIVATE / 'new-system-backups' / CAPTURE_RUN
    require(current_directory is None or Path(current_directory) == current, 'Only the retained qualified capture is allowed.')
    # The qualified function's historical source claims are evaluated against
    # their original releases, separately from the current served release.
    context = dict(_original_backup.__globals__, RUNNING_RELEASE=RESTORED_RELEASE, BASELINE=CAPTURE_SOURCE)
    report, manifest = types.FunctionType(_original_backup.__code__, context, argdefs=_original_backup.__defaults__)(path, modules, str(current))
    require(manifest['run_id'] == CAPTURE_RUN and manifest['source_commit'] == CAPTURE_SOURCE
            and sha(modules['word'].checked_file(current / 'manifest.json.fernet', private=True)) == CAPTURE_MANIFEST_SHA256,
            'Retained capture identity changed.')
    created = datetime.fromisoformat(manifest['created_at_utc'])
    require(created.tzinfo is not None and 0 <= (datetime.now(timezone.utc) - created).total_seconds() <= 30 * 3600,
            'Retained capture is outside the declared30-hour safety window.')
    return report, manifest


def assert_retained_backup(manifest, modules, storage):
    require(manifest['run_id'] == CAPTURE_RUN, 'Unqualified retained capture.')
    require(base.output(modules['old'].PSQL + ['SELECT count(*) FROM core_costreconciliation']) == '0',
            'This activation expects the measured empty reconciliation table; inspect new evidence before proceeding.')
    for item in manifest['files']:
        got = storage.get(item['path'])
        require(got and got.get('sha256') == item['sha256'] and got.get('size') == item['size'],
                'A retained backed-up file changed; inspect before activation.')
    import psycopg
    backup = modules['backup']
    with psycopg.connect(**backup.source_options(APP, base.ROLES), autocommit=True) as conn:
        conn.execute("SET timezone='UTC'"); conn.execute("SET datestyle='ISO, MDY'")
        conn.execute('BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY')
        def copy_hash(statement):
            digest = hashlib.sha256()
            with conn.cursor().copy(statement) as stream:
                for value in stream: digest.update(value)
            return digest.hexdigest()
        actual = backup.fingerprint(lambda statement: conn.execute(statement).fetchall(), copy_hash)
        require(set(actual) == set(manifest['tables']), 'Current table population differs from the reviewed retained mechanism.')
        require(not any(backup.invariant_counts(lambda statement: conn.execute(statement).fetchall()).values()), 'Current financial invariants fail.')
        conn.execute('ROLLBACK')
    BACKUP_COMPARISONS.append({'observed_at': datetime.now(timezone.utc).isoformat(), 'run_id': CAPTURE_RUN,
        'all_current_table_hashes_match_capture': actual == manifest['tables'],
        'differing_tables': [name for name in sorted(actual) if actual[name] != manifest['tables'][name]],
        'current_table_fingerprints': actual, 'fresh_capture_performed': False,
        'qualification': 'Historical recovery evidence only; complete stopped before/after snapshots protect this additive activation.'})


def operational_state(word):
    files = {name: sha(word.checked_file(PRIVATE / name, private=True)) for name in OPERATIONAL_FILES}
    units = {}
    for unit in ('quillmd-fresh-backup.service', 'quillmd-fresh-backup.timer',
                 'quillmd-fresh-offsite.service', 'quillmd-fresh-offsite.timer',
                 'quillmd-fresh-backup-alerts.service', 'quillmd-fresh-backup-alerts.timer'):
        path = Path('/etc/systemd/system') / unit
        require(path.resolve() == path and path.read_bytes() == (APP / 'deploy' / unit).read_bytes(), 'Backup/monitor unit source differs.')
        for candidate in (path, *sorted(path.with_name(unit + '.d').glob('*.conf'))):
            require(candidate.resolve() == candidate and candidate.is_file(), 'Unexpected timer policy path.')
            units[str(candidate)] = sha(candidate.read_bytes())
    timers = {unit: base.output(['systemctl', 'show', unit, '--property=ActiveState,UnitFileState,NextElapseUSecRealtime'])
              for unit in ('quillmd-fresh-backup.timer', 'quillmd-fresh-offsite.timer')}
    return {'files': files, 'units': units, 'timers': timers}


def snapshot(modules, helper_image):
    result = _original_snapshot(modules, helper_image)
    result['preserved_operations'] = operational_state(modules['word'])
    return result


def retained_source_manifest(archive):
    result = _original_retained(archive)
    result['recovery_policy'] = [
        'Leave the three private services stopped after any failure; inspect original failure and complete stopped fingerprints.',
        'Prefer a cited forward repair. A scoped rollback needs its own declaration, exact CI and preserved current state.',
        'Retain0017 evidence_kind column/check/history and0016 session revocation. Never restore the database or copy an older wallet/clinical snapshot.',
        'Historical encrypted capture does not include every later row. It is not a substitute for preserved current financial/document history.',
        'Keep all later settings; change only the exact cited recovery release stamp after schema-compatible code is installed.',
    ]
    return result


def configured_driver():
    for name in ('BASELINE', 'RUNNING_RELEASE', 'SELF', 'DECL', 'MIGRATION', 'MIGRATION_PATH',
                 'MIGRATION_SHA256', 'PREVIOUS_MIGRATION', 'EVIDENCE', 'SOURCE', 'RUNTIME_ALLOWED', 'BASELINE_OPERATION_PATHS',
                 'validate_changed', 'validate_migration', 'load', 'rows', 'check_schema', 'backup_evidence',
                 'snapshot', 'shared_configs', 'retained_source_manifest'):
        setattr(base, name, globals()[name])
    base.verify_session_versions = verify_evidence_column
    base.assert_backup_current = assert_retained_backup
    # The inherited driver's exact-source check now authenticates this adapter;
    # its own unchanged implementation is separately pinned by DRIVER_SHA256.
    base.__file__ = __file__
    return base


if __name__ == '__main__':
    configured_driver().main()
