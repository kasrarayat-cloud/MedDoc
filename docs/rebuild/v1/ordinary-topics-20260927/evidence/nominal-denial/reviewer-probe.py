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
fields=word_v3.inspect(two_knees_form_bytes())['fields'];result=[]
for tail in ('settled','left knee','Lt. knee','(L)','Ｌｅｆｔ knee','le\u200bft knee','Indication is wrong.','Actually, the indication is left knee pain.','The pain is in the other knee.','see above.'):
 notes='Indication: right knee assessment\nPain: yes\nComments: '+tail
 answers=g.generate(notes,fields,{**g.configuration(),'mode':'fixture'})[0]
 stored={k:{**a,'reviewed':True} for k,a in answers.items()}
 result.append({'case':'repeated:'+tail,'notes':notes,'answers':{f['key']:{'label':f['label'],**answers[f['key']]} for f in fields},'refusals':g.governed_decisions(notes,fields,stored)})
fields=[field('a','Assessment','long_text'),field('p','Plan','long_text'),field('l','Allergies')]
for name,assessment,plan in [('positive','mechanical low back pain.','naproxen 500 mg twice daily with food and physiotherapy.'),('question','mechanical low back pain.','naproxen?'),('pointer','mechanical low back pain.','see above.'),('correction','mechanical low back pain.','naproxen. Actually, do not give it.'),('reference','infection.','the assessment is wrong.'),('negation','infection.','no infection.'),('long-negation','active bacterial infection.','no active bacterial infection.'),('conditional','infection.','amoxicillin if symptoms develop.')]:
 notes='Assessment: '+assessment+'\nPlan: '+plan
 qs=[u['quote'] for u in g.source_units(notes,fields)[0]]
 picks={'Assessment':[qs[0]],'Plan':qs[1:]}
 answers=run(notes,picks,fields=fields)
 stored={f['key']:{**answers[f['label']],'reviewed':True} for f in fields}
 result.append({'case':'plan:'+name,'notes':notes,'answers':answers,'refusals':g.governed_decisions(notes,fields,stored)})
print(json.dumps({'disk_source_sha256':hashlib.sha256((ROOT/'core/generation.py').read_bytes()).hexdigest(),'override':os.environ.get('TASK_GENERATION_BASE'),'cases':result},indent=2))
