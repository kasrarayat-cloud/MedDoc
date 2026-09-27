import os,sys,json,hashlib
from pathlib import Path
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-ordinary-input/rebuild');sys.path.insert(0,str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
if os.environ.get('TASK_GENERATION_BASE'):exec(compile(Path(os.environ['TASK_GENERATION_BASE']).read_text(),os.environ['TASK_GENERATION_BASE'],'exec'),g.__dict__)
from core.tests.test_v3_ordinary_notes import field,run
fields=[field('r','Referring physician'),field('h','Chief complaint','long_text'),field('a','Allergies'),field('s','Smoker','choice',['Yes','No']),field('p','Plan','long_text'),field('x','Seen recently','choice',['Yes','No'])]
cases=[('father','Father: MI at 50. Smoker: No.','Smoker'),('family','Family hx: father had an MI. Smoker: No.','Smoker'),('positive','Patient presents with knee pain. Smoker: No.','Smoker'),('ancillary-qualified','Smoker: No.\nThe patient drinks socially but smokes daily.','Smoker'),('other-question','Seen recently: No.\nPatient seen today.','Seen recently')]
result=[]
for name,notes,label in cases:
    start=notes.index('No.')
    answer={'status':'supported','text':'No','reviewed':True,'evidence':[{'quote':'No.','start':start,'end':start+3}]}
    governance=g.governance_for(notes,fields);f=next(f for f in fields if f['label']==label)
    result.append({'case':name,'notes':notes,'answer':answer,'source_eligible':g.v3_labelled_source(notes,g.recognized_labels(fields),g.question_key(label),answer['evidence']),'page':g.as_currently_governed(governance,notes,{**answer,'label':label}),'refusals':g.governed_decisions(notes,fields,{f['key']:answer})})
print(json.dumps({'disk_source_sha256':hashlib.sha256((ROOT/'core/generation.py').read_bytes()).hexdigest(),'executed_override':os.environ.get('TASK_GENERATION_BASE'),'override_sha256':hashlib.sha256(Path(os.environ['TASK_GENERATION_BASE']).read_bytes()).hexdigest() if os.environ.get('TASK_GENERATION_BASE') else None,'cases':result},indent=2))
