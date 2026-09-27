import sys,json,socket,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,'/opt/meddoc-pro/.worktrees/v1-release/rebuild')
from ops import render_production_environment as r
from ops.test_production_deploy import EnvironmentRendererTests,ip_access_lists,ip_reachable,PRODUCTION,PROFILE,METADATA_ADDRESSES,unit,one
from quillmd.application_profile import deepgram_mip_opt_out
cases=0
with patch.object(socket,'socket',side_effect=AssertionError('No network permitted')):
 for name,allowed in [('QUILLMD_DEEPGRAM_MIP_OPT_OUT',{'true'}),('QUILLMD_DEEPGRAM_SMART_FORMAT',{'true','false'})]:
  for value in ['true','false','TRUE','False','1','0',' true','false ','false\n','true;X=1',True,False,None,{},'$(id)','true\\nKEY=x']:
   expected=type(value) is str and value in allowed
   try: r.parse(json.dumps({**EnvironmentRendererTests.VALID,name:value}));actual=True
   except r.RenderError:actual=False
   assert actual==expected,(name,value,actual);cases+=1
 for name in ['ANTHROPIC_BASE_URL','DEEPGRAM_BASE_URL','AWS_SECRET_ACCESS_KEY','PRIVATE_KEY']:
  try:r.parse(json.dumps({**EnvironmentRendererTests.VALID,name:'synthetic'}))
  except r.RenderError:pass
  else:raise AssertionError(name)
  cases+=1
 assert deepgram_mip_opt_out({},'real') == 'true'
 assert deepgram_mip_opt_out({},'synthetic') is None
 for path in PRODUCTION.glob('*.service'):
  allow,deny=ip_access_lists(path)
  if path.name in {PROFILE.unit_prefix+n+'.service' for n in ('environment','operations-status')}:
   assert one(unit(path)['Service'],'User')=='root'
  else:
   assert not any(ip_reachable(address,allow,deny) for address in METADATA_ADDRESSES),path
  cases+=1
print('NOTHING FOUND;',cases,'pure cases plus real/synthetic unset defaults. No network, database or host mutations.')
for name in ['deployment_profile.py','render_production_environment.py','test_production_deploy.py']:
 p=Path('/opt/meddoc-pro/.worktrees/v1-release/rebuild/ops')/name
 print(name,hashlib.sha256(p.read_bytes()).hexdigest())
