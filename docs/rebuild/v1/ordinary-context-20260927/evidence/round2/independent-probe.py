import os,sys,json,hashlib
ROOT='/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild'
sys.path.insert(0,ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
os.environ.setdefault('QUILLMD_SECRET_KEY','synthetic-refutation-no-secret')
os.environ.setdefault('QUILLMD_AI_MODE','fixture')
import django
django.setup()
from core import generation as g
from core.tests.test_v3_ordinary_notes import field,run
fields=[field('h','History','long_text'),field('c','Chief complaint'),field('a','Allergies'),field('p','Plan','long_text')]
CASES=[
 ('question-before-return','Plan: amoxicillin? Return if symptoms worsen.',{'Plan':[1]}),
 ('denial-before-return','Plan: no amoxicillin. Return if symptoms worsen.',{'Plan':[1]}),
 ('aunt-allergy','Her aunt has asthma.\nAllergies: penicillin.\nPlan is physiotherapy twice weekly.',{'Allergies':[2],'Plan':[3]}),
 ('family-specific','For her aunt.\nAllergies: penicillin.\nPlan is physiotherapy twice weekly.',{'Allergies':[2],'Plan':[3]}),
 ('family-nurse','The nurse has asthma.\nAllergies: penicillin.\nPlan is physiotherapy twice weekly.',{'Allergies':[2],'Plan':[3]}),
 ('direct-patient','Patient presents with cough.\nAllergies: none known.\nPlan: amoxicillin.\nReturn if symptoms worsen.',{'Chief complaint':[1],'Allergies':[2],'Plan':[3,4]}),
 ('repeated-plan','Plan: take one tablet.\nWait ten minutes.\nTake one tablet.',{'Plan':[3,2,1]}),
 ('wrong-side','History: right knee pain.\nPlan: inject the left knee.\nReturn if symptoms worsen.',{'History':[1],'Plan':[2,3]}),
]
rows=[]
for name,notes,picks in CASES:
  units=g.source_units(notes,fields)[0]
  byid={u['id']:u['quote'] for u in units}
  try:
    answers=run(notes,{lab:[byid[i] for i in ids] for lab,ids in picks.items()},fields=fields)
    stored={f['key']:{**answers[f['label']],'reviewed':True} for f in fields}
    judged=g.governed_decisions(notes,fields,stored)
    rows.append({'case':name,'notes':notes,'units':units,'picks':picks,'answers':{key:value for key,value in answers.items() if key in picks},'finalize_refusals':judged})
  except Exception as e:rows.append({'case':name,'notes':notes,'units':units,'error':type(e).__name__+':'+str(e)})
print(json.dumps({'generation_sha256':hashlib.sha256(open(ROOT+'/core/generation.py','rb').read()).hexdigest(),'cases':rows},indent=2))
