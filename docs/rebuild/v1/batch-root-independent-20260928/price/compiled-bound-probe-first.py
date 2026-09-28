import os,json,socket
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
def forbidden(*a,**k):raise AssertionError('Network forbidden')
socket.socket.connect=forbidden;socket.create_connection=forbidden
import django
django.setup()
from django.test import override_settings
from core.tests.test_generation_batch import sample,manifest,SETTINGS
from core import generation as g,generation_batch as b
rows=[]
with patch.dict(os.environ,QUILLMD_PROVIDER_DISCOUNT_RATE='0'),override_settings(**SETTINGS):
 for count in (101,203,559,800):
  for thinking,cap in [('disabled',8000),('adaptive',16000)]:
   for geo,factor in [('',Decimal('1')),('us',Decimal('1.1'))]:
    with override_settings(AI_THINKING=thinking,AI_INFERENCE_GEO=geo):
     e=sample(count,notes='The patient reports a cough. The patient denies fever.')
     for field in e.template_version.fields:field['context']='Independent source context — β / café / clinically unchanged.'
     e.template_version.generation_constraints=manifest(e.template_version.fields)
     plan=b.plan_for(e,g.configuration());total=Decimal(0)
     for ordinal,part in enumerate(plan['parts'],1):
      wire=b.request(plan,ordinal);size=len(json.dumps(wire).encode())
      assert wire['model']=='claude-sonnet-5' and wire['max_tokens']==cap
      assert part['input_token_bound']==size+12000
      expected=(Decimal(size+12000)*Decimal('2')+Decimal(cap)*Decimal('10'))/Decimal(1000000)*factor
      cost=Decimal(part['maximum_cost']);charge=Decimal(part['maximum_charge'])
      assert expected<=cost<expected+Decimal('.00000000001')
      assert charge==cost*Decimal('1.5')
      total+=charge
     assert Decimal(plan['maximum_charge'])==total
     rows.append({'count':count,'parts':len(plan['parts']),'thinking':thinking,'geo':geo,'maximum_charge':str(total),'last_request_bytes':size})
Path(__file__).with_suffix('.json').write_text(json.dumps({'cases':rows,'case_count':len(rows),'network_forbidden':True,'provider_calls':0,'result':'PASS','scope':'Actual compiler bound at fixed current native rates; not token-count/usage or clinical qualification.'},indent=2)+'\n')
print(json.dumps({'cases':len(rows),'result':'PASS','parts_compiled':sum(r['parts'] for r in rows),'provider_calls':0}))
