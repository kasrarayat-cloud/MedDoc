import hashlib,json,os,signal,subprocess,time
from pathlib import Path
O=Path(__file__).parent;W=Path('/opt/meddoc-pro/.worktrees/v1-elicited-campaign5-bd82576d');PY='/opt/meddoc-pro/.worktrees/v1-workflow-candidate/rebuild/.venv/bin/python'
files=['rebuild/ops/standing_qa.py','rebuild/ops/standing_qa_elicited.py','rebuild/ops/fixtures/elicited-qualification-v1.json','rebuild/ops/tests/test_standing_qa_elicited.py','docs/foundation/mutations/20261004-quillmd-v1-standing-api-testing-5.md','docs/rebuild/v1/elicited-provider-preparation-20261004/pending-standing_qa.source']
def hashes():return {p:hashlib.sha256((W/p).read_bytes()).hexdigest()for p in files}
before=hashes();start=time.monotonic();timed=False
with (O/'tests-r1.stdout.log').open('wb')as stdout,(O/'tests-r1.stderr.log').open('wb')as stderr:
 child=subprocess.Popen([PY,'-B',str(O/'child-pending-hooks.py')],stdout=stdout,stderr=stderr,start_new_session=True,cwd=W/'rebuild')
 try:child.wait(timeout=60)
 except subprocess.TimeoutExpired:
  timed=True;os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=10)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=10)
after=hashes();r={'source_commit':'713da110fb5773d774e9ae883583c81e375d4523','actual_exit':child.returncode,'pid':child.pid,'reaped':child.poll()is not None,'timed_out':timed,'source_before':before,'source_after':after,'source_unchanged':before==after,'elapsed_seconds':time.monotonic()-start}
(O/'result-r1.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if child.returncode==0 and not timed and before==after else 1)
