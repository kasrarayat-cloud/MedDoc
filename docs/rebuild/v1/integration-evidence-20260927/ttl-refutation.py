"""Independent pure metering refutation; no database or network routes allowed."""
import os,sys,json,hashlib,copy
from pathlib import Path
from decimal import Decimal,ROUND_HALF_EVEN
from types import SimpleNamespace as S
from unittest.mock import patch
root=Path('/opt/meddoc-pro/.worktrees/v1-release/rebuild');sys.path.insert(0,str(root))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','quillmd.settings')
import django
django.setup()
from core import generation as g,mapping_jobs
from core.management.commands.audit_billing import recompute_cost,recompute_list_cost
from core.tests.test_sonnet5_profile import SONNET_5
from django.test import override_settings
sources=['core/generation.py','core/mapping_jobs.py','core/management/commands/audit_billing.py','core/tests/test_sonnet5_settlement.py']
hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources}
r={'input_per_million':Decimal(2),'output_per_million':Decimal(10),'cached_per_million':Decimal('.2')}
checks=0
with patch('django.db.backends.base.base.BaseDatabaseWrapper.ensure_connection',side_effect=AssertionError('No database allowed')),patch('socket.socket.connect',side_effect=AssertionError('No network allowed')):
 for geo in ['us','global',None]:
  for discount in ['0','.2','.3333333']:
   for short,long in [(0,0),(0,7),(5,0),(5,7),(12345,67890)]:
    cfg={'model':'claude-sonnet-5','discount_rate':discount}
    response=S(usage=S(input_tokens=1234,output_tokens=567,cache_read_input_tokens=89,cache_creation_input_tokens=short+long,
     cache_creation=S(ephemeral_5m_input_tokens=short,ephemeral_1h_input_tokens=long),inference_geo=geo),stop_reason='end_turn')
    before=copy.deepcopy(cfg)
    cost,units,rates=g.anthropic_settlement(response,r,cfg)
    # Independently expand each category: ordinary input/output, cached reads, each write TTL.
    exact=(Decimal('0.002468')+Decimal('0.00567')+Decimal('0.0000178')+Decimal(short)*Decimal('0.0000025')+Decimal(long)*Decimal('0.000004'))
    if geo=='us':exact*=Decimal('1.1')
    expected=(exact*(1-Decimal(discount))).quantize(Decimal('.00000000001'),rounding=ROUND_HALF_EVEN)
    assert cost==expected,(short,long,geo,discount,cost,expected)
    assert recompute_list_cost('anthropic:claude-sonnet-5',units,rates)==exact
    assert recompute_cost('anthropic:claude-sonnet-5',units,rates,False)==expected
    assert cfg==before
    checks+=1
 # Historical no-TTL units keep both value and exact Decimal representation; no in-place mutation.
 for provider in ['anthropic:claude-sonnet-4-6','anthropic:claude-sonnet-5','openai:gpt-4.1-mini']:
  units={'input_tokens':17,'cached_input_tokens':5,'output_tokens':2,'cache_creation_tokens':3}
  prices={'input_per_million':'3','output_per_million':'15','cached_per_million':'.3'}
  before=copy.deepcopy((units,prices))
  expected=(Decimal(12 if provider.startswith('openai:') else 17)*3+Decimal(5)*Decimal('.3')+Decimal(2)*15+Decimal(3)*3*Decimal('1.25'))/1000000
  assert str(recompute_list_cost(provider,units,prices))==str(expected)
  assert (units,prices)==before
  checks+=1
 # The actual mapping sender delegates TTL metering without altering the request profile.
 with override_settings(**SONNET_5),patch.dict(os.environ,{'QUILLMD_PROVIDER_DISCOUNT_RATE':'.2'}):
  config=g.configuration();before=copy.deepcopy(config)
  response=S(usage=S(input_tokens=1234,output_tokens=567,cache_read_input_tokens=89,cache_creation_input_tokens=12,
   cache_creation=S(ephemeral_5m_input_tokens=5,ephemeral_1h_input_tokens=7),inference_geo='us'),stop_reason='end_turn',model='claude-sonnet-5',id='msg_synthetic',_request_id='req_synthetic')
  compiled={'request':{'model':'claude-sonnet-5','messages':[{'role':'user','content':'synthetic blank'}]}}
  with patch('anthropic.Anthropic') as client:
   client.return_value.messages.create.return_value=response
   result=mapping_jobs.send(compiled,config)
   client.return_value.messages.create.assert_called_once_with(**compiled['request'])
  raw,cost,units,recorded,provider,request,resource,simulated=result
  assert units['cache_creation_1h_tokens']==7 and units['cache_creation_5m_tokens']==5
  assert units['response_model']=='claude-sonnet-5' and cost==Decimal('.00721274400')
  assert recompute_cost(provider,units,recorded,simulated)==cost
  assert config==before and request=='req_synthetic' and resource=='msg_synthetic' and not simulated
  checks+=1
assert hashes=={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources},'source moved during review'
print(json.dumps({'result':'NOTHING FOUND','pure_probe_cases':checks,'network':'denied','database':'denied','sha256':hashes},indent=2))
