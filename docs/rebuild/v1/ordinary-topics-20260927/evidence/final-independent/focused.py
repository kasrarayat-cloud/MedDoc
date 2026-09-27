import os,sys,json,hashlib,socket
from pathlib import Path
from unittest.mock import patch
ROOT=Path('/opt/meddoc-pro/.worktrees/v1-ordinary-topics/rebuild');sys.path.insert(0,str(ROOT))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
from core import generation as g
if os.environ.get('TASK_GENERATION_BASE'):exec(compile(Path(os.environ['TASK_GENERATION_BASE']).read_text(),os.environ['TASK_GENERATION_BASE'],'exec'),g.__dict__)
from core.tests.test_v3_ordinary_notes import field,run
fs=[field('a','Assessment','long_text'),field('p','Plan','long_text')];out=[]
with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
 for value in ('ｎｏ active bacterial infection.','ｎ\u200bｏ infection.','amoxicillin ｉｆ symptoms develop.','ａｃｔｕａｌｌｙ no infection.','ｓｅｅ above.','ｆｏｒ mother.','naproxen 500 mg twice daily with food and physiotherapy.','paracétamol 500 mg twice daily.'):
  notes='Assessment: infection.\nPlan: '+value;units=g.source_units(notes,fs)[0]
  ans=run(notes,{'Assessment':[units[0]['quote']],'Plan':[units[1]['quote']]},fields=fs)
  forced={'a':{'status':'supported','text':'infection.','reviewed':True,'evidence':[{k:units[0][k] for k in ('quote','start','end')}]}}
  out.append({'notes':notes,'plain_value':g.plain_value(value),'answers':ans,'forced_page':g.as_currently_governed(g.governance_for(notes,fs),notes,{**forced['a'],'label':'Assessment'}),'forced_refusals':g.governed_decisions(notes,fs,forced)})
 opt=field('s','Smoker','choice',['Yes','No'])
 option_values={x:g.v3_option_value(opt,x) for x in ('No.','Ｎｏ.','Ｙｅｓ.')}
 labels={x: sorted(g.recognized_labels([field('p',x,'long_text')])) for x in ('Plan','Ｐｌａｎ')}
print(json.dumps({'disk_sha256':hashlib.sha256((ROOT/'core/generation.py').read_bytes()).hexdigest(),'override':os.environ.get('TASK_GENERATION_BASE'),'cases':out,'option_values':option_values,'recognized_labels':labels},indent=2))
