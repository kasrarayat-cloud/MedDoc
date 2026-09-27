import os,sys,json
sys.path.insert(0,os.environ.get('REVIEW_SOURCE','/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild'))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic-only',QUILLMD_DB_PASSWORD='unused',QUILLMD_DB_PORT='1',QUILLMD_AI_MODE='fixture')
import django;django.setup()
from core import generation as g
if source:=os.environ.get("REVIEW_GENERATION"):
 exec(compile(open(source).read(),source,"exec"),g.__dict__)
from core.tests.test_v3_ordinary_notes import field,run
fields=[field('a','Allergies'),field('m','Medications','long_text'),field('e','Examination','long_text'),field('p','Plan','long_text')]
rows=[]
for q in ('Medications are warfarin f\u200bor the donor.',):
 label='Examination' if 'examination' in q else 'Medications';notes='Allergies: penicillin.\n'+q+'\nPlan: rest.'
 a=run(notes,{label:[q]},fields=fields)[label]
 if a['status']=='supported':judged=g.governed_decisions(notes,fields,{next(f['key'] for f in fields if f['label']==label):{**a,'reviewed':True}})
 else:judged=None
 rows.append({'notes':notes,'label':label,'status':a['status'],'text':a['text'],'finalize_refusals':judged})
print(json.dumps(rows,indent=2))
