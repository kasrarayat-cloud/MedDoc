import os,sys,json,hashlib,socket
sys.path.insert(0,'/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild')
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic-only',QUILLMD_DB_PASSWORD='unused',QUILLMD_DB_PORT='1',QUILLMD_AI_MODE='fixture')
import django;django.setup()
def forbidden(*args,**kwargs): raise RuntimeError('network forbidden in pure clinical probe')
socket.socket.connect=forbidden
from core import generation as g
from core.tests.test_v3_ordinary_notes import field,run
p='/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild/core/generation.py'
sha=hashlib.sha256(open(p,'rb').read()).hexdigest();assert sha=='166947914409a575269c2bd5e174bdc62b2ae73239ab0754900b85d32c84c24f'
fields=[field('a','Allergies'),field('m','Medications','long_text'),field('e','Examination','long_text'),field('d','Assessment','long_text'),field('p','Plan','long_text')]
cases=[
('unowned-change','Current medications are aspirin daily.\n\nA medication was discontinued.\n\nPlan: continue current medications.',{'Medications':['Current medications are aspirin daily.'],'Plan':['Plan: continue current medications.']},False),
('unowned-addition','Current medications are aspirin daily.\n\nWarfarin is another medication.\n\nPlan: continue current medications.',{'Medications':['Current medications are aspirin daily.'],'Plan':['Plan: continue current medications.']},False),
('unowned-owner','Current medications are aspirin daily.\n\nPatient medications are warfarin.\n\nPlan: continue current medications.',{'Medications':['Current medications are aspirin daily.'],'Plan':['Plan: continue current medications.']},False),
]
rows=[]
for name,notes,picks,supported in cases:
 answers=run(notes,picks,fields=fields); row={'name':name,'notes':notes,'answers':{},'forced_supported_refusals':{}}
 for label,quotes in picks.items():
  a=answers[label]; row['answers'][label]=a
  row.setdefault('unexpected_supported',[]).extend([label] if a['status']=='supported' else [])
  key=next(f['key'] for f in fields if f['label']==label)
  if not supported:
   evidence=[{'quote':q,'start':notes.index(q),'end':notes.index(q)+len(q)} for q in quotes]
   forced={'text':'\n'.join(quotes),'status':'supported','reviewed':True,'evidence':evidence}
   judged=g.governed_decisions(notes,fields,{key:forced});row['forced_supported_refusals'][label]=judged
   row.setdefault('unexpected_finalizable',[]).extend([label] if label not in judged else [])
 rows.append(row)
print(json.dumps({'sha256':sha,'cases':rows,'red_probe':True},indent=2))
