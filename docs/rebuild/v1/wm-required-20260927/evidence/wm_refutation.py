import hashlib,json,os,sys
from pathlib import Path
root=Path('/opt/meddoc-pro/.worktrees/v1-wm-integration/rebuild')
sys.path.insert(0,str(root))
os.environ.update(DJANGO_SETTINGS_MODULE='quillmd.settings',QUILLMD_ENV_MANAGED='1',QUILLMD_SECRET_KEY='synthetic-refutation-only',QUILLMD_DB_PASSWORD='unused',QUILLMD_WM_NARRATIVE='1',QUILLMD_AI_MODE='fixture')
import django;django.setup()
from core import wm_narrative as w,generation as g
from core.views import source_quote_evidence
mapping=json.loads((root/'core/tests/benchmarks/wm_narrative/mapping.json').read_bytes())
fields=mapping['fields'];requirements=mapping['review_requirements'];labels=w.context_labels(requirements)
right=next(f for f in fields if f['label']=='Right GSV at the SFJ: diameter (mm)')
left=next(f for f in fields if f['label']=='Left GSV at the SFJ: diameter (mm)')
notes='RIGHT LEG:\nThe great saphenous vein measures 7.4 mm at the saphenofemoral junction.\n\nLEFT LEG:\nThe great saphenous vein measures 7.4 mm at the saphenofemoral junction.'
units=w.units(notes,fields,labels);recognized=g.recognized_labels(fields,labels)
quote='The great saphenous vein measures 7.4 mm at the saphenofemoral junction.'
read=w.stored_reading(notes,fields,labels,{})
results=[]
for field in (right,left):
 evidence=source_quote_evidence(notes,field['label'],quote,[f['label'] for f in fields]+labels,units,(),
   lambda unit:w.support(field,'7.4 mm',[w.unit_evidence(unit)],notes,recognized,[f['label'] for f in fields]+labels) is None,
   lambda unit:w.copy_rank(field,'7.4 mm',unit,read))
 verdict=w.support(field,'7.4 mm',evidence,notes,recognized,[f['label'] for f in fields]+labels)
 expected=notes.index(quote) if field is right else notes.rindex(quote)
 assert evidence[0]['start']==expected and verdict is None
 again=source_quote_evidence(notes,field['label'],quote,[f['label'] for f in fields]+labels,units,evidence,
   lambda unit:w.support(field,'7.4 mm',[w.unit_evidence(unit)],notes,recognized,[f['label'] for f in fields]+labels) is None,
   lambda unit:w.copy_rank(field,'7.4 mm',unit,read))
 assert again==evidence
 wrong=w.support(field,'7.4 mm',[w.unit_evidence(next(u for u in units if u['start']!=(expected) and u['quote']==quote))],notes,recognized,[f['label'] for f in fields]+labels)
 assert wrong is not None
 results.append({'field':field['label'],'start':expected,'supported':verdict is None,'opposite_copy_refused':wrong,'resave_stable':again==evidence})
print(json.dumps({'synthetic_paired_evidence':results,'source':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['core/views.py','core/wm_review.py','core/wm_narrative.py','documents/sdk_word/Adapter/WmAdapter.cs']}},indent=2))
