"""Owned isolated synthetic PostgreSQL only; no installed environment or provider credentials."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = Path('/opt/meddoc-pro/.worktrees/v1-disposition-integration')
AUTHORITY = Path('/opt/meddoc-pro/.worktrees/v1-release-integration/rebuild/.runtime/release-integration')
HERE = Path(__file__).resolve().parent
tag, *labels = sys.argv[1:]
assert re.fullmatch(r'[a-z0-9_-]+', tag) and labels
receipt = json.loads((AUTHORITY / 'synthetic-postgres-receipt.json').read_text())
container = json.loads(subprocess.check_output(['docker', 'inspect', receipt['name']]))[0]
assert container['Id'] == receipt['id']
assert container['NetworkSettings']['Ports']['5432/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '55821'}]
assert container['Config']['Labels']['quillmd.owner'] == 'v1-full-release-20260928'
config = dict(line.split('=', 1) for line in (AUTHORITY / 'synthetic-postgres.env').read_text().splitlines())
env = {'PATH': '/usr/bin:/bin', 'QUILLMD_ENV_MANAGED': '1', 'PYTHONDONTWRITEBYTECODE': '1',
       'QUILLMD_SECRET_KEY': 'synthetic-integration-tests-only', 'QUILLMD_DATA_MODE': 'synthetic',
       'QUILLMD_AI_MODE': 'fixture', 'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_DB_PORT': '55821',
       'QUILLMD_DB_USER': config['POSTGRES_USER'], 'QUILLMD_DB_PASSWORD': config['POSTGRES_PASSWORD'],
       'QUILLMD_DB_NAME': 'v1_disposition_' + tag, 'QUILLMD_STATE_DIR': str(HERE / ('state-' + tag)),
       'TMPDIR': '/tmp/claude-1000/v1-disposition-integration-20260928', 'DJANGO_SETTINGS_MODULE': 'quillmd.settings', 'QUILLMD_DISPOSITION_ARTIFACT_DIR': str(HERE / ('render-' + tag))}
command = ['/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python', '-B', 'manage.py', 'test', '--noinput', '--verbosity', '2', *labels]
log = HERE / (tag + '.log')
assert not log.exists(), 'Preserve every first result; choose a new run tag'
tracked = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', 'rebuild'], cwd=ROOT, text=True).splitlines()
before = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in tracked if (ROOT / p).is_file()}
record = {'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
          'labels': labels, 'synthetic_container': receipt['id'], 'database': 'test_v1_disposition_' + tag,
          'source_before': before, 'installed_database_touched': False}
with log.open('x') as output:
    result = subprocess.run(command, cwd=ROOT / 'rebuild', env=env, stdout=output, stderr=subprocess.STDOUT)
record.update(completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(), exit_code=result.returncode,
              source_unchanged=all((ROOT / p).is_file() and hashlib.sha256((ROOT / p).read_bytes()).hexdigest() == digest
                                   for p, digest in before.items()))
(HERE / (tag + '-manifest.json')).write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: v for k, v in record.items() if k != 'source_before'}))
print('\n'.join(log.read_text().splitlines()[-18:]))
assert record['source_unchanged'], 'Source changed during verification; evidence needs scope reconciliation'
raise SystemExit(result.returncode)
