"""Use only the explicitly reserved localhost synthetic PostgreSQL fixture, never log credentials."""
import json
import os
from pathlib import Path
import subprocess
import sys

tree = Path(os.environ.get('WORD_TREE', Path(__file__).resolve().parents[3]))
assert str(tree) in ('/opt/meddoc-pro/.worktrees/v1-word-workflows', '/opt/meddoc-pro/.worktrees/v1-release')
fixture = json.loads(subprocess.check_output(['docker', 'inspect', 'v1-blockers-pg']))[0]
assert fixture['Name'] == '/v1-blockers-pg'
assert fixture['NetworkSettings']['Ports']['5432/tcp'] == [{'HostIp': '127.0.0.1', 'HostPort': '55702'}]
config = dict(item.split('=', 1) for item in fixture['Config']['Env'] if '=' in item)
env = {**os.environ, 'QUILLMD_ENV_MANAGED': '1', 'QUILLMD_SECRET_KEY': 'synthetic-d30-only',
       'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_DB_PORT': '55702',
       'QUILLMD_DB_NAME': config.get('POSTGRES_DB', config.get('POSTGRES_USER', 'postgres')),
       'QUILLMD_DB_USER': config.get('POSTGRES_USER', 'postgres'),
       'QUILLMD_DB_PASSWORD': config['POSTGRES_PASSWORD'], 'QUILLMD_AI_MODE': 'fixture',
       'DJANGO_SETTINGS_MODULE': 'quillmd.settings',
       'PYTHONPATH': str(tree / 'rebuild') + ':' + str(Path(__file__).parent)}
exe = '/opt/meddoc-pro/.worktrees/v1-release/rebuild/.venv/bin/python'
cmd = [exe, str(tree / 'rebuild/manage.py'), 'test', '--noinput', '--verbosity', '2'] + sys.argv[1:]
raise SystemExit(subprocess.run(cmd, cwd=tree, env=env).returncode)
