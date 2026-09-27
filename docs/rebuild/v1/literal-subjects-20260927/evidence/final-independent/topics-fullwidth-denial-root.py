import sys,os,json,hashlib
from pathlib import Path
root=Path(os.environ.get('TASK_ROOT','/opt/meddoc-pro/.worktrees/v1-ordinary-topics/rebuild'));sys.path.insert(0,str(root))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import field,run
fields=[field('a','Assessment','long_text'),field('p','Plan','long_text')];rows=[]
inputs=json.loads(Path('/opt/meddoc-pro/rebuild/.runtime/v1-astra-recovery-20260927/topics-fullwidth-denial-root-red.json').read_text())['cases']
for original in inputs:
 notes=original['notes'];qs=[u['quote'] for u in g.source_units(notes,fields)[0]]
 answers=run(notes,{'Assessment':[qs[0]],'Plan':qs[1:]},fields=fields)
 forced={f['key']:{'status':'supported','text':q.split(': ',1)[1],'reviewed':True,'evidence':[{'quote':q,'start':notes.index(q),'end':notes.index(q)+len(q)}]} for f,q in zip(fields,qs)}
 rows.append({'notes':notes,'answers':answers,'forced_refusals':g.governed_decisions(notes,fields,forced)})
print(json.dumps({'sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
assert all(r['answers']['Assessment']['status']=='conflict' and r['forced_refusals']==['Assessment'] for r in rows)
assert all(r['answers']['Plan']['text']==r['notes'].split('Plan: ',1)[1] for r in rows)
