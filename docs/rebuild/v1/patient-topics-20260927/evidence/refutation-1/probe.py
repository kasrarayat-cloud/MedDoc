import os,sys,json,hashlib
from pathlib import Path
from unittest.mock import patch
root=Path(os.environ['TASK_ROOT']);sys.path.insert(0,str(root))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic',QUILLMD_AI_MODE='fixture',QUILLMD_ENV_MANAGED='1',QUILLMD_DB_PASSWORD='synthetic',QUILLMD_DB_PORT='1')
import django;django.setup()
if os.environ.get('GENERATION_OVERRIDE'):
 import types,core
 path=Path(os.environ['GENERATION_OVERRIDE']); module=types.ModuleType('core.generation')
 module.__file__=str(path);module.__package__='core';sys.modules['core.generation']=module;core.generation=module
 exec(compile(path.read_text(),str(path),'exec'),module.__dict__)
from core import generation as g
from core.tests.test_v3_ordinary_notes import run
source=Path('/opt/meddoc-pro/.worktrees/v1-release/docs/rebuild/v1/ordinary-input-20260927/evidence/known-results.json')
c=next(c for c in json.loads(source.read_text())['cases'] if c['name']=='r1-note4')
cases=[('original',c['notes']),('female_he',c['notes'].replace('She ','He ')),('male_she',c['notes'].replace('30-year-old female','30-year-old male')),('anaphylaxis',c['notes'].replace('Assessment is tension-type headache.','Assessment is penicillin anaphylaxis.')),('reaction',c['notes'].replace('Assessment is tension-type headache.','Assessment is penicillin hypersensitivity.')),('plan_negation',c['notes'].replace('Plan is to start amitriptyline','Plan is not to start amitriptyline')),('foreign_examination',c['notes'].replace('Neurological examination is normal.','Neurological examination is normal for her mother.')),('third_party',c['notes'].replace('She takes ibuprofen as needed.','Her friend takes ibuprofen as needed.'))]
rows=[]
with patch('socket.socket.connect',side_effect=AssertionError('Network denied')):
 for name,notes in cases:
  picks={k:[x.replace('She ','He ') if name=='female_he' else x.replace('30-year-old female','30-year-old male') if name=='male_she' else x for x in v] for k,v in c['unchanged_picks'].items()}
  # For changed clinical statements select ONLY unaffected exact NKA/Examination/full Plan.
  if name not in ['original','female_he','male_she']:picks={'Allergies':[c['unchanged_picks']['Allergies'][0]]}
  answers=run(notes,picks,fields=c['fields']);forced={}
  for f in c['fields']:
   if f['label'] in picks:
    qs=picks[f['label']]
    if all(q in notes for q in qs):forced[f['key']]={'status':'supported','text':' '.join(qs),'reviewed':True,'evidence':[{'quote':q,'start':notes.index(q),'end':notes.index(q)+len(q)} for q in qs]}
  rows.append({'name':name,'notes':notes,'selected':picks,'answers':{k:{'status':answers[k]['status'],'text':answers[k]['text']} for k in picks},'forced_refusals':g.governed_decisions(notes,c['fields'],forced)})
print(json.dumps({'generation_sha256':hashlib.sha256(Path(g.__file__).read_bytes()).hexdigest(),'cases':rows},indent=2))
