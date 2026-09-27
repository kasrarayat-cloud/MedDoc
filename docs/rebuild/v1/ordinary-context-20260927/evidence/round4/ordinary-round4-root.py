import os,sys,json,hashlib,socket
sys.path.insert(0,'/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild')
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_SECRET_KEY='synthetic-only',QUILLMD_DB_PASSWORD='unused',QUILLMD_DB_PORT='1',QUILLMD_AI_MODE='fixture')
import django;django.setup()
def forbidden(*args,**kwargs): raise RuntimeError('network forbidden in pure clinical probe')
socket.socket.connect=forbidden
from core import generation as g
from core.tests.test_v3_ordinary_notes import field,run
p='/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild/core/generation.py'
sha=hashlib.sha256(open(p,'rb').read()).hexdigest();assert sha=='2a173620c44229c7403ba4fb170a2436de00dcfc7637e6357fa4d121f995145b'
fields=[field('a','Allergies'),field('m','Medications','long_text'),field('e','Examination','long_text'),field('d','Assessment','long_text'),field('p','Plan','long_text')]
cases=[
 ('sibling','Allergies: penicillin.\nSibling medications are warfarin.\nPlan: rest.',{'Medications':['Sibling medications are warfarin.']},False),
 ('donor','Allergies: penicillin.\nDonor medications are warfarin.\nPlan: rest.',{'Medications':['Donor medications are warfarin.']},False),
 ('future','Allergies: penicillin.\nPlanned examination will reveal the lesion.\nPlan: rest.',{'Examination':['Planned examination will reveal the lesion.']},False),
 ('allergy-denial','Allergies: penicillin.\nAssessment: no penicillin allergy.',{'Allergies':['Allergies: penicillin.'],'Assessment':['Assessment: no penicillin allergy.']},False),
 ('allergy-probable','Allergies: none.\nAssessment is a probable penicillin allergy.',{'Allergies':['Allergies: none.'],'Assessment':['Assessment is a probable penicillin allergy.']},False),
 ('question','Plan: amoxicillin? Return if symptoms worsen.',{'Plan':['Plan: amoxicillin? Return if symptoms worsen.']},False),
 ('absent-referent','Plan: continue current medications.',{'Plan':['Plan: continue current medications.']},False),
 ('current-positive','Allergies: penicillin.\nCurrent medications are aspirin.\nPlan: rest.',{'Medications':['Current medications are aspirin.']},True),
 ('reference-positive','Medications: aspirin.\nPlan: continue current medications.',{'Medications':['Medications: aspirin.'],'Plan':['Plan: continue current medications.']},True),
]
rows=[]
for name,notes,picks,supported in cases:
 answers=run(notes,picks,fields=fields); row={'name':name,'notes':notes,'answers':{},'forced_supported_refusals':{}}
 for label,quotes in picks.items():
  a=answers[label]; row['answers'][label]=a
  assert (a['status']=='supported')==supported,(name,label,a['status'])
  key=next(f['key'] for f in fields if f['label']==label)
  if not supported:
   evidence=[{'quote':q,'start':notes.index(q),'end':notes.index(q)+len(q)} for q in quotes]
   forced={'text':'\n'.join(quotes),'status':'supported','reviewed':True,'evidence':evidence}
   judged=g.governed_decisions(notes,fields,{key:forced});row['forced_supported_refusals'][label]=judged
   assert label in judged,(name,label,judged)
 rows.append(row)
print(json.dumps({'sha256':sha,'cases':rows,'passed':True},indent=2))
