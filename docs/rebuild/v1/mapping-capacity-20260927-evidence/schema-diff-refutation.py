"""Independent pure check of root's shared compiler plus this branch's compact schema."""
import copy,hashlib,importlib.util,json,socket,sys
from pathlib import Path
from unittest.mock import patch
import httpx
from anthropic import Anthropic
from pydantic import ValidationError
sys.path.insert(0,'/opt/meddoc-pro/.worktrees/v1-release/rebuild')
from django.conf import settings
settings.configure(INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','core'],SECRET_KEY='synthetic-only',DATABASES={'default':{'ENGINE':'django.db.backends.dummy'}})
import django
django.setup()
from core import generation as g, mapping_assistance as old,wm_narrative
spec=importlib.util.spec_from_file_location('core.capacity_wire','/opt/meddoc-pro/.worktrees/v1-mapping-capacity/rebuild/core/mapping_wire.py')
wire=importlib.util.module_from_spec(spec);spec.loader.exec_module(wire)
from core.tests.test_anthropic_schema_compatibility import unsupported
count=0
for schema in [g.UnitSelections,wm_narrative.NarrativeSelections,old.Proposal,wire.Proposal]:
 original=schema.model_json_schema();before=copy.deepcopy(original)
 class SharedSchema:
  @staticmethod
  def model_json_schema():return original
 for model in ['claude-sonnet-5','claude-sonnet-4-6']:
  profile={'max_output_tokens':20000,'timeout_seconds':120,'thinking':{'type':'disabled'},'effort':'medium','inference_geo':'us'}
  prior=copy.deepcopy(profile);payload={'text':'Synthetic 🏥 input'}
  request=g.anthropic_request(model,profile,'UNTRUSTED test',payload,SharedSchema)
  observed=[]
  def receive(req):
   observed.append(json.loads(req.content))
   return httpx.Response(200,json={'id':'msg_offline','type':'message','role':'assistant','model':model,'content':[{'type':'text','text':'{}'}],'stop_reason':'end_turn','stop_sequence':None,'usage':{'input_tokens':1,'output_tokens':1}})
  with patch.object(socket,'socket',side_effect=AssertionError('No network')):
   with httpx.Client(transport=httpx.MockTransport(receive)) as transport:
    with Anthropic(api_key='synthetic',http_client=transport,max_retries=0) as client:client.messages.create(**request)
  actual=observed[0]['output_config']['format']['schema']
  if model=='claude-sonnet-5':assert not unsupported(actual),unsupported(actual)
  else:
   expected={'model':model,'max_tokens':20000,'system':'UNTRUSTED test','messages':[{'role':'user','content':json.dumps(payload)}],'output_config':{'format':{'type':'json_schema','schema':before},'effort':'medium'},'thinking':{'type':'disabled'},'inference_geo':'us'}
   assert request==expected
  assert original==before;assert schema.model_json_schema()==before;assert profile==prior
  count+=1
payload={'slots':[],'fields':[]};payload['text_refs']=wire.catalog(payload)
body=wire.fixture(payload)
for update in [{'x':[[True,0,0,0,0,1,-1]]},{'x':[[0]*6]},{'e':1},{'f':{'k':[200],'r':[],'n':[],'u':[]}}]:
 try:wire.Proposal.model_validate({**body,**update})
 except ValidationError:pass
 else:raise AssertionError(update)
 count+=1
print('NOTHING FOUND:',count,'pure/SDK-mock controls. Sonnet5 transformed; historical4.6 complete request exact; source/profile unchanged; local bounds remain strict.')
p=Path('/opt/meddoc-pro/.worktrees/v1-release/rebuild/core/generation.py')
print('generation.py SHA256',hashlib.sha256(p.read_bytes()).hexdigest())
