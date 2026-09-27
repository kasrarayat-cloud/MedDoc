import os,sys,json,hashlib
from pathlib import Path
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-ordinary-topics/rebuild');sys.path.insert(0,str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
if os.environ.get('TASK_GENERATION_BASE'):exec(compile(Path(os.environ['TASK_GENERATION_BASE']).read_text(),os.environ['TASK_GENERATION_BASE'],'exec'),g.__dict__)
from core.tests.test_v3_ordinary_notes import field,run
from core.tests.test_word_v3_workflow import two_knees_form_bytes
from documents import word_v3
fields=[field('a','Assessment','long_text'),field('p','Plan','long_text')]
result=[]
for assessment,plan in [('infection.','no infection.'),('active bacterial infection.','no active bacterial infection.'),('mechanical low back pain.','naproxen 500 mg twice daily with food and physiotherapy.')]:
 notes='Assessment: '+assessment+'\nPlan: '+plan
 units=g.source_units(notes,fields)[0];forced={}
 for f,u in zip(fields,units):forced[f['key']]={'status':'supported','text':assessment if f['key']=='a' else plan,'reviewed':True,'evidence':[{k:u[k] for k in ('quote','start','end')}]}
 governance=g.governance_for(notes,fields)
 result.append({'notes':notes,'forced':forced,'pages':{f['label']:g.as_currently_governed(governance,notes,{**forced[f['key']],'label':f['label']}) for f in fields},'refusals':g.governed_decisions(notes,fields,forced)})
print(json.dumps({'disk_sha256':hashlib.sha256((ROOT/'core/generation.py').read_bytes()).hexdigest(),'override':os.environ.get('TASK_GENERATION_BASE'),'cases':result},indent=2))
