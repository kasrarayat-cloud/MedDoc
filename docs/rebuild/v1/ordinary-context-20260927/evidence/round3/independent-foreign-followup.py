import os,sys,json,hashlib
ROOT='/opt/meddoc-pro/.worktrees/v1-ordinary-context/rebuild'
sys.path.insert(0,ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings');os.environ.setdefault('QUILLMD_SECRET_KEY','synthetic-only');os.environ.setdefault('QUILLMD_AI_MODE','fixture')
import django
django.setup()
from core import generation as g
if os.environ.get('TASK_GENERATION_BASE'):
    exec(compile(open(os.environ['TASK_GENERATION_BASE']).read(),os.environ['TASK_GENERATION_BASE'],'exec'),g.__dict__)
from core.tests.test_v3_ordinary_notes import field,run
fields=[field('h','Chief complaint'),field('m','Medications','long_text'),field('a','Allergies'),field('e','Examination','long_text'),field('d','Assessment','long_text'),field('p','Plan','long_text')]
cases=[
('sibling-medications','Allergies: penicillin.\nSibling medications are warfarin.\nPlan: rest.',{'Medications':[2]}),
('donor-medications','Allergies: penicillin.\nDonor medications are warfarin.\nPlan: rest.',{'Medications':[2]}),
('planned-examination','Allergies: penicillin.\nPlanned examination will reveal a rash.\nPlan: rest.',{'Examination':[2]}),
]
result=[]
for name,notes,picks in cases:
    units=g.source_units(notes,fields)[0]; byid={u['id']:u['quote'] for u in units}
    answers=run(notes,{label:[byid[i] for i in ids] for label,ids in picks.items()},fields=fields)
    stored={f['key']:{**answers[f['label']],'reviewed':True} for f in fields}
    entry={'case':name,'notes':notes,'picks':picks,'units':units,'answers':{k:v for k,v in answers.items() if k in picks},'finalize_refusals':g.governed_decisions(notes,fields,stored)}
    if name=='question-fixed':
        forced={'text':notes[6:],'status':'supported','reviewed':True,'evidence':[{'quote':notes,'start':0,'end':len(notes)}]}
        entry['forced_supported_refusals']=g.governed_decisions(notes,fields,{'p':forced})
    result.append(entry)
print(json.dumps({'disk_generation_sha256':hashlib.sha256(open(ROOT+'/core/generation.py','rb').read()).hexdigest(),'executed_override':os.environ.get('TASK_GENERATION_BASE'),'cases':result},indent=2))
