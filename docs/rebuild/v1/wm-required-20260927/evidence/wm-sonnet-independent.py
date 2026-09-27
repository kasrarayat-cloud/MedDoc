import django,json,copy
django.setup()
from unittest.mock import patch
from django.test import override_settings
from core import generation as g
from core.jobs import NoProviderRequest
from core.tests.test_wm_narrative_sonnet5 import SETTINGS,response,FIELDS,REQUIREMENTS,SFJ
from types import SimpleNamespace
from django.core.exceptions import ValidationError
rows=[]
with override_settings(**SETTINGS):
 config=g.configuration()
 original=response(); body=original.content[-1].text; midpoint=len(body)//2
 original.content=[SimpleNamespace(type='thinking',thinking='synthetic'),SimpleNamespace(type='text',text=body[:midpoint]),SimpleNamespace(type='text',text=body[midpoint:])]
 with patch('anthropic.Anthropic') as c:
  c.return_value.messages.create.return_value=original
  raw,cost,units,rates,*_=g.generate(SFJ,FIELDS,config,requirements=REQUIREMENTS)
  sent=c.return_value.messages.create.call_args.kwargs
 assert sent['model']=='claude-sonnet-5' and sent['thinking']=={'type':'disabled'}
 assert sent['max_tokens']==config['request_profile']['max_output_tokens']
 assert cost<=g.maximum_cost(SFJ,FIELDS,config,requirements=REQUIREMENTS)
 assert g.adoption(raw)[0]['measurement_1_1']['text']=='7.4 mm'
 rows.append('multiple text blocks after thinking preserve complete JSON and exact source value')
 for stop,model in [('refusal','claude-sonnet-5'),('max_tokens','claude-sonnet-5'),('end_turn','claude-sonnet-4-6')]:
  variant=copy.copy(original);variant.stop_reason=stop;variant.model=model
  rejected=False
  try:g.adoption({**raw,'anthropic_response':variant})
  except ValidationError:rejected=True
  assert rejected,(stop,model)
 rows.append('refusal, incomplete, wrong actual model reject adoption')
 with patch('core.wm_narrative.payload',side_effect=ValueError('synthetic preparation failure')),patch('anthropic.Anthropic') as c:
  try:g.generate(SFJ,FIELDS,config,requirements=REQUIREMENTS);raise AssertionError('accepted preparation error')
  except NoProviderRequest:pass
  c.assert_not_called()
 rows.append('preparation failure classified unsent before client construction')
 with patch('anthropic.Anthropic') as c:
  c.return_value.messages.create.side_effect=TimeoutError('synthetic uncertain outcome')
  try:g.generate(SFJ,FIELDS,config,requirements=REQUIREMENTS);raise AssertionError('accepted timeout')
  except TimeoutError as e:assert not isinstance(e,NoProviderRequest)
  assert c.return_value.messages.create.call_count==1
 rows.append('post-submission timeout stays uncertain and request is not retried')
print(json.dumps({'result':'PASS','checks':rows,'live_provider_calls':0},indent=2))
