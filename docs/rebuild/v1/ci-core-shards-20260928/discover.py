from pathlib import Path
import hashlib,json,os,re,socket,subprocess,sys
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-ci-core-shards'); OUT=Path(__file__).parent
os.chdir(ROOT/'rebuild');sys.path.insert(0,str(ROOT/'rebuild'))
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_ENV_MANAGED='1',QUILLMD_SECRET_KEY='synthetic-discovery-only-no-service',QUILLMD_DB_PASSWORD='synthetic-unused',QUILLMD_DB_NAME='custodian_discovery_never_connect',QUILLMD_DB_HOST='127.0.0.1',QUILLMD_DB_PORT='9',QUILLMD_AI_MODE='fixture',GITHUB_SHA=sha)
def refuse(*a,**k):raise AssertionError('Network/database forbidden during discovery-only evidence')
socket.socket.connect=refuse;socket.create_connection=refuse
import django
django.setup()
from django.db.backends.base.base import BaseDatabaseWrapper
BaseDatabaseWrapper.ensure_connection=refuse
from django.test.runner import DiscoverRunner,iter_test_cases
from ops.ci_test_runner import CoreShardRunner
from ops.ci_test_shards import verify_manifests
baseline=DiscoverRunner(verbosity=0).build_suite(['core.tests'])
base_ids=[t.id() for t in iter_test_cases(baseline)]
assert base_ids and len(base_ids)==len(set(base_ids))
(OUT/'baseline-ids.json').write_text(json.dumps(base_ids,indent=2)+'\n')
selected=[];paths=[]
for n in (1,2):
 path=OUT/f'core-shard-{n}.json';runner=CoreShardRunner(core_shard=n,core_shard_manifest=path,verbosity=0)
 suite=runner.build_suite(['core.tests']);selected.extend(t.id() for t in iter_test_cases(suite));paths.append(path)
assert sorted(selected)==sorted(base_ids)
summary=verify_manifests(paths,sha)
log=Path('/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.runtime/workflow-integration-20260928/ci-52793-core-final.log').read_bytes()
prior=[]
for method,case in re.findall(r'\b(test_[A-Za-z0-9_]+) \(([^)]+)\) \.\.\.',log.decode()):
 prior.append(case if case.endswith('.'+method) else case+'.'+method)
summary.update(baseline_count=len(base_ids),network_and_db_blocked=True,executed_core_tests=0,prior_log_sha256=hashlib.sha256(log).hexdigest(),prior_ci_test_ids=len(prior),prior_ci_unique_ids=len(set(prior)),prior_ci_same_universe=set(prior)==set(base_ids))
assert len(prior)==2097 and len(prior)==len(set(prior)) and summary['prior_ci_same_universe']
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
