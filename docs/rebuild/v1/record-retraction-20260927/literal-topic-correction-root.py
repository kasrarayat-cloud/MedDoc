import os,sys,json,hashlib
from pathlib import Path
root=Path(os.environ.get('TASK_ROOT','/opt/meddoc-pro/.worktrees/v1-release/rebuild'))
sys.path.insert(0,str(root));os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import field,run
rows=[]
for label,statement,plan in [('Allergies','No known drug allergies.','Plan: removal of erroneous NKA entry.'),('Examination','Neurological examination is normal.','Plan: deletion of erroneous normal neurological entry.')]:
 f=field('a',label,'long_text');p=field('p','Plan','long_text');notes=statement+'\n'+plan
 answers=run(notes,{label:[statement],'Plan':[plan]},fields=[f,p]);stored={'a':{'status':'supported','text':statement,'reviewed':True,'evidence':[{'quote':statement,'start':0,'end':len(statement)}]}}
 rows.append({'notes':notes,'answers':answers,'forced_refusals':g.governed_decisions(notes,[f,p],stored)})
print(json.dumps({'generation_sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
