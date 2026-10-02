import os,json,socket
from pathlib import Path
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
def forbidden(*a,**k):raise AssertionError('Network forbidden')
socket.socket.connect=forbidden;socket.create_connection=forbidden
import django
django.setup()
from django.test import override_settings
from core.tests.test_generation_batch import sample,manifest,SETTINGS
from core import generation as g,generation_batch as b
rows=[]
with override_settings(**SETTINGS):
 for history in (False,True):
  with override_settings(V3_HISTORY_CONTEXT=history):
   e=sample(101,notes='The patient reports a cough. The patient denies fever.')
   e.template_version.fields[0]['label']='Chief complaint'
   e.template_version.fields[1]['label']='HPI'
   e.template_version.generation_constraints=manifest(e.template_version.fields)
   plan=b.plan_for(e,g.configuration())
   assert plan['contract']=='v3-generation-batch-v1'
   rows.append({'history':history,'plan':plan,'request_sha256':[b.digest(b.request(plan,i)) for i in (1,2)]})
p=Path('rebuild/core/tests/fixtures/batch_v1_plan.json');p.parent.mkdir(parents=True,exist_ok=True)
p.write_text(json.dumps({'scope':'Synthetic before-change immutable v1 request reconstruction; no provider calls','source':'5a36e75276397c19175c5de8dc43a976329a3e2e','cases':rows},ensure_ascii=False,separators=(',',':'))+'\n')
print(json.dumps({'legacy_cases':len(rows),'hashes':[r['request_sha256'] for r in rows],'file_bytes':p.stat().st_size}))
