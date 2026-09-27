import os,sys,json,socket,copy
sys.path.insert(0,'/opt/meddoc-pro/.worktrees/v1-retention-readiness/rebuild')
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic-only',QUILLMD_DB_PASSWORD='unused',QUILLMD_DB_PORT='1',QUILLMD_AI_MODE='fixture')
import django;django.setup()
socket.socket=lambda *a,**k: (_ for _ in ()).throw(AssertionError('No network'))
from core import retention_readiness as r
from django.apps import apps
base=r.unresolved_policy();checks=[]
def rejects(name,body):
 try:r.parse_policy(json.dumps(body).encode())
 except r.PolicyError:checks.append(name);return
 raise AssertionError('ACCEPTED '+name)
for name in ('classes','coverage','contract'):
 b=copy.deepcopy(base);b.pop(name);rejects('missing '+name,b)
for days in (True,False,'30',0,-1,365001,1.5):
 b=copy.deepcopy(base);b['schedule_document_sha256']='f'*64;b['classes']['patient_identity']={'mode':'review_window','days':days,'anchor':'created_at'};rejects('days '+str(days),b)
for name in ('ledger','audit','provider_receipts','usage','mapping_versions','finalized_clinical_records','final_export_references'):
 b=copy.deepcopy(base);b['schedule_document_sha256']='f'*64;b['classes'][name]={'mode':'review_window','days':30,'anchor':r.CATALOG[name][2][0]};rejects('protected '+name,b)
for anchor in ('notes','created_at__year','created_at;DROP TABLE','export_path'):
 b=copy.deepcopy(base);b['schedule_document_sha256']='f'*64;b['classes']['patient_identity']={'mode':'review_window','days':30,'anchor':anchor};rejects('anchor '+anchor,b)
for declared in (False,True):
 b=copy.deepcopy(base)
 if declared:b['coverage']={k:'declared_for_review' for k in r.EXTERNAL};b['schedule_document_sha256']='f'*64
 p=r.parse_policy(json.dumps(b).encode());assert all(v.days is None for v in p.classes.values());checks.append('valid declaration remains no window '+str(declared))
labels={x[0] for x in r.CATALOG.values()};assert {m._meta.label for m in apps.get_app_config('core').get_models()}<=labels;checks.append('all current models represented')
print(json.dumps({'result':'PASS','checks':checks,'count':len(checks),'scope':'independent policy/domain controls only; PostgreSQL read-only proof remains separate synthetic evidence'},indent=2))
