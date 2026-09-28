from pathlib import Path
import hashlib,json,re,subprocess,sys
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-ci-core-shards');OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'rebuild'))
from ops.ci_test_shards import verify_manifests
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
summary=verify_manifests([OUT/'core-shard-1.json',OUT/'core-shard-2.json'],sha)
base=json.loads((OUT/'baseline-ids.json').read_bytes())
log=Path('/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.runtime/workflow-integration-20260928/ci-52793-core-final.log').read_bytes()
prior=[]
for method,case in re.findall(r'\b(test_[A-Za-z0-9_]+) \(([^)]+)\)',log.decode()):
 prior.append(case if case.endswith('.'+method) else case+'.'+method)
summary.update(baseline_count=len(base),network_and_db_blocked=True,executed_core_tests=0,prior_log_sha256=hashlib.sha256(log).hexdigest(),prior_ci_test_ids=len(prior),prior_ci_unique_ids=len(set(prior)),prior_ci_same_universe=set(prior)==set(base))
assert len(prior)==2097 and len(prior)==len(set(prior)) and summary['prior_ci_same_universe']
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
