import sys,os,json,hashlib
from pathlib import Path
root=Path(os.environ.get('TASK_ROOT','/opt/meddoc-pro/.worktrees/v1-ordinary-topics/rebuild'));sys.path.insert(0,str(root))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import field,run
fields=[field('a','Assessment','long_text'),field('p','Plan','long_text')];rows=[]
for finding,plan in [('infection.','no infection.'),('active bacterial infection.','no active bacterial infection.'),('mechanical low back pain.','naproxen 500 mg twice daily with food and physiotherapy.')]:
 notes=f'Assessment: {finding}\nPlan: {plan}'
 quotes=[u['quote'] for u in g.source_units(notes,fields)[0]]
 answers=run(notes,{'Assessment':[quotes[0]],'Plan':quotes[1:]},fields=fields)
 stored={f['key']:{**answers[f['label']],'reviewed':True} for f in fields}
 forced={f['key']:{'status':'supported','text':text,'reviewed':True,'evidence':[{'quote':q,'start':notes.index(q),'end':notes.index(q)+len(q)}]} for f,text,q in zip(fields,[finding,plan],quotes)}
 rows.append(dict(notes=notes,answers=answers,refusals=g.governed_decisions(notes,fields,stored),forced_refusals=g.governed_decisions(notes,fields,forced)))
print(json.dumps(dict(source_sha256=hashlib.sha256((root/'core/generation.py').read_bytes()).hexdigest(),cases=rows),indent=2))
assert all(r['answers']['Assessment']['status']=='conflict' and r['forced_refusals']==['Assessment'] for r in rows[:2])
assert rows[2]['answers']['Assessment']['status']=='supported' and rows[2]['forced_refusals']==[]
