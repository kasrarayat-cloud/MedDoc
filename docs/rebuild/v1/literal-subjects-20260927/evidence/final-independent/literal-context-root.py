import sys,os,json,hashlib
from pathlib import Path
root=Path(os.environ.get('TASK_ROOT','/opt/meddoc-pro/.worktrees/v1-literal-subjects/rebuild'));sys.path.insert(0,str(root));os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import field,run
rows=[]
for context in ['', 'Examination', 'Mother','Family history']:
 for notes in ['Neurological examination is normal.','Heart and lung examination was normal.']:
  f=field('exam','Examination','long_text');f['context']=context
  a=run(notes,{'Examination':[notes]},fields=[f])['Examination'];stored={'status':'supported','text':notes,'reviewed':True,'evidence':[{'quote':notes,'start':0,'end':len(notes)}]}
  rows.append({'notes':notes,'field_context':context,'answer':a,'forced_refusals':g.governed_decisions(notes,[f],{'exam':stored})})
print(json.dumps({'sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
assert all(r['answer']['status']=='supported' and r['answer']['text']==r['notes'] and not r['forced_refusals'] for r in rows[:4])
assert all(r['answer']['status']=='conflict' and r['forced_refusals']==['Examination'] for r in rows[4:])
