#!/usr/bin/env python3
"""Explicit, pinned retirement. Defaults to read-only checks; no global prune.

Execute only through scripts/run-ruled-mutation.sh after committing its
declaration, manifest, and this script. No archive or migration is created.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SHARED = Path('/opt/meddoc-pro')
MANIFEST = ROOT / 'docs/rebuild/retirement-manifest.json'
REMOVE = [
    'meddoc-pro-transcribe-md-1', 'meddoc-pro-transcribe-md-worker-1',
    'meddoc-pro-meddoc-pro-1', 'meddoc-pro-form-detect-1', 'meddoc-pro-gotenberg-1',
    'meddoc-qa-transcribe-md-1', 'meddoc-qa-transcribe-md-worker-1',
    'meddoc-qa-postgres-1', 'meddoc-qa-minio-1', 'meddoc-qa-redis-1',
]
QA_VOLUMES = [
    'meddoc-qa_qa_pgdata', 'meddoc-qa_qa_minio',
    'd15ddbc95b32f08874fcc62affd7d1253d116a5c7283a7b53c1dab84caccf4b0',
]
OLD_TABLES = '''_prisma_migrations account_deletions accounts ai_calls allergies
api_usage api_usage_events api_usage_logs appointments audit_logs auth_tokens
billing_events doctor_edit_patterns documents hipaa_findings invite_codes
ledger_entries medications note_templates patients practices price_rates
rx_warning_overrides session_logs sessions tasks template_twin_certifications
template_twin_compiled_versions template_twin_field_definitions
template_twin_field_overrides template_twin_fill_manifests
template_twin_semantic_mappings template_twin_source_artifacts threat_resolutions
transcribe_md_patients transcribe_visits user_sessions users verification_tokens
visit_deliveries'''.split()
OLD_TYPES = '''AllergySeverity AppointmentStatus AuditAction AuthTokenPurpose
BillingEventStatus DocumentStatus PatientSex PatientStatus PracticeRole Product
TaskStatus TemplateTwinCertificationStatus TemplateTwinDetectionStatus
TemplateTwinFillStatus TemplateTwinResolutionStatus TranscribeVisitStatus
UserRole VisitType'''.split()


def run(args, stdin=None):
    result = subprocess.run(args, input=stdin, text=True, capture_output=True)
    if result.returncode:
        # Child output may contain document object names; keep it private.
        raise RuntimeError(f'Operation failed (exit {result.returncode}): {args[:3]}')
    return result.stdout.strip()


def sql(query):
    return run(['docker', 'exec', '-i', 'meddoc-pro-postgres-1', 'psql',
                '-U', 'meddoc', '-d', 'meddoc', '-X', '-A', '-t',
                '-v', 'ON_ERROR_STOP=1'], query)


def containers():
    ids = run(['docker', 'ps', '-aq']).split()
    return {d['Name'].lstrip('/'): d for d in json.loads(run(['docker', 'inspect', *ids]))}


def marketing_status():
    with urlopen('http://127.0.0.1:3010/', timeout=10) as response:
        return response.status


def precheck():
    assert SHARED.resolve() == SHARED and ROOT.is_relative_to(SHARED)
    assert ROOT != SHARED, 'Execute the reviewed worktree script; shared main is preserved.'
    expected = json.loads(MANIFEST.read_text())['containers']
    current = containers()
    for name, pinned in expected.items():
        d = current[name]
        labels = d['Config'].get('Labels') or {}
        assert d['Id'] == pinned['id'], f'Container changed: {name}'
        assert d['Image'] == pinned['image_id'], f'Image changed: {name}'
        for key, suffix in [('project', 'project'), ('service', 'service'),
                            ('working_dir', 'project.working_dir')]:
            assert labels.get('com.docker.compose.' + suffix) == pinned[key], name
        mounts = [{k: m.get(k) for k in ['Type', 'Name', 'Source', 'Destination']}
                  for m in d['Mounts']]
        assert sorted(mounts, key=lambda m: m['Destination']) == sorted(
            pinned['mounts'], key=lambda m: m['Destination']), f'Mount changed: {name}'
    for volume in QA_VOLUMES:
        users = [n for n, d in current.items()
                 if any(m.get('Name') == volume for m in d['Mounts'])]
        assert len(users) == 1 and users[0] in REMOVE, f'Shared QA volume: {volume}'
    tables = set(sql("SELECT tablename FROM pg_tables WHERE schemaname='public';").splitlines())
    assert tables == set(OLD_TABLES) | {'waitlist_entries'}, 'Database table set changed.'
    assert sql("SELECT count(*) FROM pg_constraint WHERE contype='f' AND "
               "conrelid='public.waitlist_entries'::regclass;") == '0'
    leads = sql('SELECT count(*) FROM public.waitlist_entries;')
    assert leads == '7', 'Marketing lead baseline changed; update declaration before continuing.'
    assert marketing_status() == 200
    # No lead contents leave PostgreSQL. This digest proves preservation through the act.
    leads_digest = sql("SELECT md5(string_agg(row_to_json(w)::text,'' ORDER BY id)) "
                       "FROM public.waitlist_entries w;")
    print('CHECKED: pinned containers/mounts, dedicated QA volumes, 40 old tables, '
          '7 protected marketing leads, marketing HTTP 200.', flush=True)
    return expected, current, leads_digest


def execute():
    declaration = os.environ.get('RULED_MUTATION_DECLARATION')
    committed = os.environ.get('RULED_MUTATION_DECL_COMMIT')
    assert declaration and committed, 'Must run through the committed ruled-mutation gate.'
    assert Path(declaration).name == '20260917-quillmd-fresh-retirement.md'
    expected, before, leads_digest = precheck()
    print('Stopping old application writers, old QA, sidecars and old backup schedule.', flush=True)
    stop_names = REMOVE + ['meddoc-pro-postgres-backup-1']
    run(['docker', 'update', '--restart=no', *stop_names])
    run(['docker', 'stop', '--time', '20', *stop_names])

    print('Deleting only verified old application tables and enum types.', flush=True)
    drop_tables = ', '.join('public."' + t + '"' for t in OLD_TABLES)
    drop_types = ', '.join('public."' + t + '"' for t in OLD_TYPES)
    # Single transaction, explicit table set. CASCADE drops old inter-table constraints;
    # waitlist has no foreign keys and its content digest is checked afterwards.
    sql('BEGIN; DROP TABLE ' + drop_tables + ' CASCADE; DROP TYPE IF EXISTS '
        + drop_types + '; COMMIT;')
    assert sql("SELECT tablename FROM pg_tables WHERE schemaname='public';") == 'waitlist_entries'
    assert sql("SELECT md5(string_agg(row_to_json(w)::text,'' ORDER BY id)) "
               "FROM public.waitlist_entries w;") == leads_digest

    print('Deleting the two dedicated MinIO buckets, including object versions.', flush=True)
    # Credentials expand only inside their existing container. Temporary mc config is
    # erased; output is suppressed so stored object names cannot escape into the log.
    run(['docker', 'exec', '-i', 'meddoc-pro-minio-1', 'sh', '-s'], r'''
set -eu
cfg=/tmp/quillmd-retirement-mc-$$
mkdir -m 700 "$cfg"
trap 'rm -rf "$cfg"' EXIT
mc --config-dir "$cfg" alias set retirement http://127.0.0.1:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null
mc --config-dir "$cfg" rb --force retirement/transcribe-md-audio >/dev/null
mc --config-dir "$cfg" rb --force retirement/transcribe-md-template-artifacts >/dev/null
remaining=$(mc --config-dir "$cfg" ls retirement)
[ -z "$remaining" ]
''')
    print('Clearing only the verified old application Redis DB 0.', flush=True)
    run(['docker', 'exec', 'meddoc-pro-redis-1', 'redis-cli', '-n', '0', 'FLUSHDB', 'SYNC'])
    assert run(['docker', 'exec', 'meddoc-pro-redis-1', 'redis-cli', '-n', '0', 'DBSIZE']) == '0'

    print('Removing the exact old containers and three dedicated QA volumes.', flush=True)
    run(['docker', 'rm', *REMOVE])
    for volume in QA_VOLUMES:
        # Recheck ownership immediately before volume removal.
        assert not run(['docker', 'ps', '-aq', '--filter', 'volume=' + volume])
        run(['docker', 'volume', 'rm', volume])
    after = containers()
    assert not any(name in after for name in REMOVE)
    for name, d in before.items():
        if name in stop_names:
            continue
        assert name in after and after[name]['Id'] == d['Id'], f'Protected container moved: {name}'
        assert after[name]['Image'] == d['Image'], f'Protected image moved: {name}'
        assert after[name]['State']['Running'] == d['State']['Running'], f'Protected state moved: {name}'
    assert marketing_status() == 200
    result = {
        'finished_at_utc': datetime.now(timezone.utc).isoformat(),
        'declaration_commit': committed,
        'removed_containers': REMOVE, 'removed_qa_volumes': QA_VOLUMES,
        'removed_production_tables': OLD_TABLES,
        'removed_buckets': ['transcribe-md-audio', 'transcribe-md-template-artifacts'],
        'marketing_leads_preserved': 7, 'marketing_content_digest_matches': True,
        'marketing_http_status': 200, 'old_redis_db0_keys': 0,
        'backup_schedule': 'stopped; mixed backups and credentials preserved',
        'shared_tree_source': 'unchanged pending PR',
    }
    path = ROOT / 'docs/rebuild/retirement-result.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print('VERIFIED: exact retirement completed; protected containers and marketing '
          'preserved. Evidence: docs/rebuild/retirement-result.json', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        execute()
    else:
        precheck()
