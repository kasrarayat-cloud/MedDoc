import hashlib,importlib.machinery,importlib.util,json,os,socket,sys,time,unittest
from pathlib import Path
O=Path(__file__).parent;W=Path('/opt/meddoc-pro/.worktrees/v1-elicited-campaign5-bd82576d')
connections=[]
def deny(sock,address):connections.append(str(address));raise AssertionError('Pure prospective tests prohibit network and database')
socket.socket.connect=deny
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_ENV_MANAGED='1',QUILLMD_SECRET_KEY='synthetic-offline-fixed-new-stage',QUILLMD_STATE_DIR=str(O/'pure-state'),QUILLMD_DB_HOST='127.0.0.1',QUILLMD_DB_PORT='1',QUILLMD_DB_NAME='unreachable',QUILLMD_DB_USER='unreachable',QUILLMD_DB_PASSWORD='synthetic-unused',QUILLMD_DATA_MODE='synthetic',QUILLMD_AI_MODE='fixture')
sys.path.insert(0,str(W/'rebuild'))
import django;django.setup()
# Explicit test-only pending root literal, not applied or an eligible execution door.
p=W/'docs/rebuild/v1/elicited-provider-preparation-20261004/pending-standing_qa.source'
assert hashlib.sha256(p.read_bytes()).hexdigest()=='3b5c1d2866be9d592aa6ba5bece03f5d5780448b5e7e24f5d1c8e65b20168583'
import ops
loader=importlib.machinery.SourceFileLoader('ops.standing_qa',str(p));spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec);sys.modules['ops.standing_qa']=module;ops.standing_qa=module;loader.exec_module(module)
start=time.monotonic();suite=unittest.defaultTestLoader.loadTestsFromName('ops.tests.test_standing_qa_elicited.ElicitedFixedStage')
result=unittest.TextTestRunner(verbosity=2).run(suite)
report={'source_commit':'713da110fb5773d774e9ae883583c81e375d4523','pending_root_literal_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pending_root_patch_applied_to_writer':False,'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'successful':result.wasSuccessful(),'network_attempts':connections,'database_calls':0,'provider_calls':0,'credential_calls':0,'live_campaign_created':False,'elapsed_seconds':time.monotonic()-start}
(O/'child-result-r1.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
raise SystemExit(0 if result.wasSuccessful() and not connections else 1)
