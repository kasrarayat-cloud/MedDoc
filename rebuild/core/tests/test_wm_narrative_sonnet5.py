"""WM narrative request migration: synthetic responses through patched clients, no network."""
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import generation as g, wm_narrative as wm
from core.jobs import NoProviderRequest
from core.tests.test_wm_narrative import FIELDS, REQUIREMENTS, SFJ, selections

SETTINGS = dict(WM_NARRATIVE=True, AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL='claude-sonnet-5',
                AI_INPUT_RATE='2', AI_OUTPUT_RATE='10', AI_CACHED_RATE='0.20', AI_THINKING='disabled',
                AI_EFFORT='medium', AI_INFERENCE_GEO='')


def response(*, stop='end_turn', model='claude-sonnet-5', geo=None):
    body = selections(SFJ, {'measurement_1_1': ('7.4 mm', [SFJ], {})}).model_dump_json()
    return SimpleNamespace(model=model, stop_reason=stop, _request_id='synthetic-wm-sonnet',
        stop_details=None, content=[SimpleNamespace(type='thinking', thinking='synthetic hidden block'),
                                    SimpleNamespace(type='text', text=body)],
        usage=SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=3,
                              cache_creation_input_tokens=2, inference_geo=geo,
                              output_tokens_details=SimpleNamespace(thinking_tokens=5)))


@override_settings(**SETTINGS)
class WMNarrativeSonnet5Profile(SimpleTestCase):
    def test_the_recorded_profile_governs_request_bound_and_timeout(self):
        for mode, cap in [('disabled', 8000), ('adaptive', 16000)]:
            with self.subTest(mode=mode), override_settings(AI_THINKING=mode, AI_INFERENCE_GEO='us'):
                config=g.configuration()
                with patch('anthropic.Anthropic') as client:
                    client.return_value.messages.create.return_value=response(geo='us')
                    raw,cost,units,rates,provider,request_id,simulated=g.generate(SFJ,FIELDS,config,requirements=REQUIREMENTS)
                    sent=client.return_value.messages.create.call_args.kwargs
                self.assertEqual(client.call_args.kwargs, {'timeout':120, 'max_retries':0})
                self.assertEqual((sent['model'],sent['max_tokens'],sent['inference_geo']),('claude-sonnet-5',cap,'us'))
                self.assertEqual(sent['thinking'],config['request_profile']['thinking'])
                self.assertEqual(sent['output_config']['effort'],'medium')
                self.assertFalse({'temperature','top_p','top_k'} & set(sent))
                self.assertEqual(sent['system'],wm.INSTRUCTIONS)
                self.assertEqual(json.loads(sent['messages'][0]['content'])['notes'],SFJ)
                self.assertEqual(sent['output_config']['format']['schema'],wm.NarrativeSelections.model_json_schema())
                bound=g.maximum_cost(SFJ,FIELDS,config,requirements=REQUIREMENTS)
                payload=json.dumps(wm.payload(SFJ,FIELDS,REQUIREMENTS))
                serialized=payload+wm.INSTRUCTIONS+json.dumps(wm.NarrativeSelections.model_json_schema())
                exact=(Decimal(len(serialized.encode())+12000)*2/1000000+Decimal(cap)*10/1000000)*Decimal('1.1')
                self.assertEqual(bound,exact.quantize(g.COST_QUANTUM,rounding=g.ROUND_CEILING))
                self.assertGreaterEqual(bound,cost)
                self.assertEqual((provider,request_id,simulated),('anthropic:claude-sonnet-5','synthetic-wm-sonnet',False))
                answers,review=g.adoption(raw)
                self.assertEqual((answers['measurement_1_1']['status'],answers['measurement_1_1']['text']),('supported','7.4 mm'))

    def test_usage_is_recorded_with_thinking_inside_output_and_metered_geography(self):
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value=response(geo='us')
            _,cost,units,rates,*_=g.generate(SFJ,FIELDS,g.configuration(),requirements=REQUIREMENTS)
        self.assertEqual(cost,Decimal('0.00044616'))
        self.assertEqual((units['output_tokens'],units['thinking_tokens'],units['inference_geo'],units['stop_reason']),
                         (20,5,'us','end_turn'))
        self.assertEqual(rates['inference_geo_multiplier'],'1.1')

    def test_refusal_incomplete_and_wrong_response_model_are_never_adopted(self):
        for stop,model in [('refusal','claude-sonnet-5'),('max_tokens','claude-sonnet-5'),
                           ('model_context_window_exceeded','claude-sonnet-5'),('end_turn','claude-sonnet-4-6')]:
            with self.subTest(stop=stop,model=model), patch('anthropic.Anthropic') as client:
                client.return_value.messages.create.return_value=response(stop=stop,model=model)
                raw,*_=g.generate(SFJ,FIELDS,g.configuration(),requirements=REQUIREMENTS)
                with self.assertRaises(ValidationError):g.adoption(raw)

    def test_request_preparation_failure_is_explicitly_unsent(self):
        with patch('anthropic.Anthropic',side_effect=RuntimeError('synthetic client preparation failure')):
            with self.assertRaises(NoProviderRequest):
                g.generate(SFJ,FIELDS,g.configuration(),requirements=REQUIREMENTS)
