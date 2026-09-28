from pathlib import Path
import ast
import hashlib
import json
import os
import socket
import subprocess
import sys
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-disposition-integration')
os.environ.clear()
os.environ.update(PATH='/usr/bin:/bin', QUILLMD_ENV_MANAGED='1', PYTHONDONTWRITEBYTECODE='1', DJANGO_SETTINGS_MODULE='quillmd.settings', QUILLMD_SECRET_KEY='synthetic-no-db-schema', QUILLMD_DATA_MODE='synthetic', QUILLMD_AI_MODE='fixture', QUILLMD_DB_PASSWORD='unused', QUILLMD_DB_HOST='127.0.0.1', QUILLMD_DB_PORT='1', QUILLMD_DB_NAME='unused', QUILLMD_STATE_DIR=str(ROOT/'rebuild/.runtime/disposition-enforcement/schema-state'), TMPDIR='/tmp/claude-1000/v1-disposition-integration-20260928')
def refuse(*args,**kwargs): raise AssertionError('No network permitted in schema proof')
socket.socket.connect=refuse
sys.path.insert(0,str(ROOT/'rebuild'))
import django
django.setup()
from django.apps import apps
from django.conf import settings
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState
from django.db.migrations.autodetector import MigrationAutodetector
from core import disposition,retention_readiness
from ops import integrity_contract
loader=MigrationLoader(None,ignore_no_migrations=True)
changes=MigrationAutodetector(loader.project_state(),ProjectState.from_apps(apps)).changes(graph=loader.graph)
assert not changes, list(changes)
disposition.check_catalog()
def constants(text):
 return {n.targets[0].id:ast.literal_eval(n.value) for n in ast.parse(text).body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('GUARDS','FUNCTION_SHA256')}
old=constants(subprocess.check_output(['git','show','644e2835:rebuild/ops/integrity_contract.py'],cwd=ROOT,text=True))
assert set(old['GUARDS']) <= set(integrity_contract.GUARDS)
assert all(integrity_contract.FUNCTION_SHA256[k]==v for k,v in old['FUNCTION_SHA256'].items())
assert len(integrity_contract.GUARDS)==82 and len(integrity_contract.FUNCTION_SHA256)==21
unset=json.loads((ROOT/'rebuild/ops/retention/policy.unset.json').read_text())
assert all(rule['mode']=='unresolved' and rule['days'] is None for rule in unset['classes'].values())
assert settings.DISPOSITION_ENABLED is False and settings.DISPOSITION_AUTHORITY_KEYS=={} and not settings.DISPOSITION_JOURNAL_PATH
assert settings.V3_GENERATION_BATCHES is False
print(json.dumps({'core_leaf_nodes':loader.graph.leaf_nodes('core'),'model_migration_changes':list(changes),'closed_catalog_matches':True,'prior_guards_preserved':len(old['GUARDS']),'prior_function_hashes_preserved':len(old['FUNCTION_SHA256']),'expected_guards':len(integrity_contract.GUARDS),'expected_function_bodies':len(integrity_contract.FUNCTION_SHA256),'execution_default':settings.DISPOSITION_ENABLED,'batch_feature_default':settings.V3_GENERATION_BATCHES,'policy_classes_unresolved':len(unset['classes']),'authority_keys_unset':True,'journal_path_unset':True,'network':'denied','database_connections':0},indent=2))
