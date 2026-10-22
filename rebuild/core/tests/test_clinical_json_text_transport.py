"""Direct canonical JSON: real offline SDK bytes, history and clinical gates."""
from copy import deepcopy
from decimal import Decimal
import json
from unittest.mock import patch

from anthropic import Anthropic
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
import httpx

from core import ai_stages, anthropic_request_policy as policy
from core import clinical_schema_transport as legacy, clinical_json_text_transport as codec
from core import clinical_evidence_transport as evidence, clinical_node_transport as nodes
from core import clinical_json_transport as envelope
from core.provider_schema import retained_request_matches
from core.tests.test_clinical_schema_transport import CONFIG, nullable, object_schema


class ClinicalJSONTextTransportTests(SimpleTestCase):
    def test_exact_nested_values_types_null_empty_and_absent_are_lossless(self):
        schema = object_schema({'/~': {'type': 'string'}, 'i': {'type': 'integer'},
            'n': {'type': 'number'}, 'b': {'type': 'boolean'}, 'null': {'type': 'null'},
            'array': {'type': 'array', 'items': nullable({'type': 'number'})},
            'object': object_schema({})})
        value = {'/~': '界😀"\\\r\n', 'i': 2**100, 'n': -0.0, 'b': False,
            'null': None, 'array': [None, 0, 0.0], 'object': {}}
        before = deepcopy(value)
        decoded = codec.decode(schema, codec.strict_loads(legacy._json(codec.encode(schema, value))))
        self.assertEqual(legacy._json(decoded), legacy._json(value))
        self.assertEqual(value, before)
        self.assertIs(type(decoded['i']), int); self.assertIs(type(decoded['n']), float)
        self.assertIs(type(decoded['b']), bool); self.assertIs(type(decoded['array'][1]), int)
        optional = object_schema({'x': nullable({'type': 'string'})}); optional['required'] = []
        for value in ({}, {'x': None}, {'x': ''}):
            self.assertEqual(codec.decode(optional, codec.encode(optional, value)), value)

    def test_complete_original_schema_once_and_no_provider_grammar(self):
        schema = object_schema({'subject': {'title': 'EXACT_TITLE', 'anyOf': [
            object_schema({'kind': {'type': 'string', 'enum': ['patient'], 'description': 'PATIENT_ONLY'},
                'name': nullable({'type': 'string', 'description': 'NULLABLE_NAME'})}),
            object_schema({'kind': {'type': 'string', 'enum': ['other']},
                'name': {'type': 'string', 'minLength': 1}})]}})
        before = deepcopy(schema); original = legacy._json(schema)
        self.assertEqual(codec.instructions(schema).count(original), 1)
        self.assertTrue(codec.instructions(schema).endswith(original))
        self.assertEqual(codec.wire_schema(schema), schema)
        self.assertIsNot(codec.wire_schema(schema), schema)
        self.assertIsNone(legacy.transmitted_schema(schema, codec.TRANSPORT))
        self.assertEqual(schema, before)
        with self.assertRaises(ValueError):codec.encode(schema, {'subject': {'kind': 'other', 'name': None}})

    def test_duplicate_nonfinite_trailing_wrapped_and_malformed_text_refuses_without_echo(self):
        schema = object_schema({'value': {'type': 'number'}})
        for text in ('{"value":1,"value":2}', '{"value":NaN}', '{"value":Infinity}',
                '{"value":-Infinity}', '{"value":1e999}', '{"value":', '{}{}', 'null',
                '"{\\"value\\":1}"', '```json\n{"value":1}\n```',
                '{"value":"PRIVATE_OUTPUT_MARKER"',
                '{"transport":"anthropic-canonical-json-v4","document_json":"{}"}'):
            with self.subTest(text=text), self.assertRaises(ValueError) as raised:
                codec.decode(schema, codec.strict_loads(text))
            self.assertNotIn('PRIVATE_OUTPUT_MARKER', str(raised.exception))
            self.assertNotIn(text, str(raised.exception))

    def test_original_required_types_enum_closed_objects_and_bounds_still_apply(self):
        schema = object_schema({'x': {'type': 'string', 'enum': ['ok'], 'maxLength': 2},
            'i': {'type': 'integer', 'minimum': 1, 'maximum': 3}, 'b': {'type': 'boolean'},
            'a': {'type': 'array', 'minItems': 1, 'maxItems': 2,
                'items': nullable({'type': 'number', 'minimum': 0})}})
        valid = {'x': 'ok', 'i': 1, 'b': False, 'a': [None, 1.5]}
        self.assertEqual(codec.decode(schema, valid), valid)
        for value in ({}, {**valid, 'extra': None}, {**valid, 'x': 'bad'},
                {**valid, 'i': True}, {**valid, 'i': 0}, {**valid, 'i': 4},
                {**valid, 'b': 0}, {**valid, 'a': []}, {**valid, 'a': [0, 1, 2]},
                {**valid, 'a': [-1]}):
            with self.subTest(value=value), self.assertRaises(ValueError):codec.encode(schema, value)

    def test_complete_three_stage_models_and_twenty_destinations_are_unchanged(self):
        from core import source_assertion_generation as generation
        from core.tests.test_source_assertion_graph import (
            IDENTITY, base_case, checker, run_case, definitions, assignments)
        from core.tests.test_source_assertion_generation import stated_time_case
        base = base_case(); fields, defs = definitions(('Symptoms',) * 20)
        twenty = (base[0], fields, defs, base[3], assignments(fields, {f['key']: ['f1'] for f in fields}))
        for case in (base, stated_time_case(), twenty):
            expected, _ = run_case(case)
            notes, fields, defs, raw, assigned = case
            def send(role, attempt, payload, schema, instructions):
                value = raw if role == 'extractor' else assigned if role == 'assigner' else checker(
                    payload['graph'], fields, defs, assigned)
                return codec.decode(schema, codec.strict_loads(legacy._json(codec.encode(schema, value))))
            actual = generation.run(notes, fields, defs, send, identity=IDENTITY)
            self.assertEqual(actual, expected)
            self.assertEqual(generation.restore(notes, actual['interpretation']), actual['answers'])
            self.assertEqual(len(actual['answers']), len(fields))

    def test_schema_valid_source_invention_ownership_and_incomplete_coverage_still_refuse(self):
        from core import source_assertion_graph as graph
        from core.tests.test_source_assertion_graph import base_case, ref
        notes, _, _, original, _ = base_case()
        bad_quote = deepcopy(original); bad_quote['facts'][1]['value_span']['quote'] = 'Invented source'
        bad_owner = deepcopy(original)
        bad_owner['assertions'][1]['consumer_ref'] = ref(notes, 'Synthetic Ada Vale')
        bad_coverage = deepcopy(original); bad_coverage['unit_coverage'].pop()
        for value in (bad_quote, bad_owner, bad_coverage):
            restored = codec.decode(graph.extraction_schema(), codec.encode(graph.extraction_schema(), value))
            with self.assertRaises(ValidationError):graph.compile_graph(notes, restored)

    def test_full_original_fact_bound_remains_two_hundred(self):
        from core import source_assertion_graph as graph
        from core.tests.test_source_assertion_graph import base_case
        raw = deepcopy(base_case()[3])
        raw['facts'] = [{**deepcopy(raw['facts'][1]), 'id': 'f' + str(i)} for i in range(200)]
        self.assertEqual(codec.decode(graph.extraction_schema(), codec.encode(graph.extraction_schema(), raw)), raw)
        raw['facts'].append({**deepcopy(raw['facts'][0]), 'id': 'f200'})
        with self.assertRaises(ValueError):codec.encode(graph.extraction_schema(), raw)

    def test_versioned_history_and_unknown_or_cross_provider_dispatch(self):
        schema = object_schema({'value': nullable({'type': 'string'})}); value = {'value': 'Exact'}
        modules = (legacy, evidence, nodes, envelope, codec)
        for module in modules:
            cfg = {**CONFIG, legacy.CONFIG_KEY: module.TRANSPORT}
            request = {'schema': schema, 'schema_transport': module.TRANSPORT}
            text = json.dumps(module.encode(schema, value))
            self.assertEqual(legacy.response_value(text, request, config=cfg, provider='anthropic', simulated=False), value)
            expected = module.instructions(schema) if module in (envelope, codec) else module.INSTRUCTIONS
            self.assertEqual(legacy.instructions(cfg, schema=schema), expected)
        self.assertEqual(legacy.CURRENT_TRANSPORT, nodes.TRANSPORT)
        self.assertEqual(legacy.JSON_TRANSPORT, envelope.TRANSPORT)
        self.assertEqual(legacy.LATEST_TRANSPORT, codec.TRANSPORT)
        for cfg, provider, simulated in (({**CONFIG, legacy.CONFIG_KEY: 'unknown'}, 'anthropic', False),
                ({**CONFIG, legacy.CONFIG_KEY: codec.TRANSPORT}, 'openai', False),
                ({**CONFIG, legacy.CONFIG_KEY: codec.TRANSPORT}, 'anthropic', True)):
            with self.assertRaises(ValueError):legacy.response_value(legacy._json(value),
                {'schema': schema, 'schema_transport': codec.TRANSPORT}, config=cfg, provider=provider, simulated=simulated)

    def test_exact_retained_no_format_metadata_binds_full_original_request(self):
        schema = object_schema({'value': nullable({'type': 'string'})})
        config = ai_stages.pipeline_config(CONFIG)
        expected = {'stage': 'extractor', 'schema': schema, 'payload': {'notes': 'Unchanged source'}}
        request = {**deepcopy(expected), 'schema_transport': codec.TRANSPORT,
            policy.ENVELOPE_KEY: policy.parameters(config), 'transmitted_schema': 'null'}
        before = deepcopy(request)
        self.assertTrue(retained_request_matches(request, expected, config=config, provider='anthropic', simulated=False))
        self.assertEqual(legacy.response_value('{"value":"Exact"}', request,
            config=config, provider='anthropic', simulated=False), {'value': 'Exact'})
        for key, value in (('transmitted_schema', None), ('transmitted_schema', '{}'),
                ('schema_transport', envelope.TRANSPORT), ('payload', {'notes': 'Changed'}),
                ('schema', {'type': 'string'}), (policy.ENVELOPE_KEY, {})):
            changed = deepcopy(request); changed[key] = value
            self.assertFalse(retained_request_matches(changed, expected, config=config, provider='anthropic', simulated=False))
        for key in ('transmitted_schema', policy.ENVELOPE_KEY):
            changed = deepcopy(request); changed.pop(key)
            self.assertFalse(retained_request_matches(changed, expected, config=config, provider='anthropic', simulated=False))
        self.assertEqual(request, before)

    def sdk(self, config, *, text='{"value":"Exact"}', stop='end_turn', content=None, extra=None):
        sent, callbacks, constructor = [], [], []
        def handle(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, headers={'request-id': 'req_TESTONLY'}, json={
                'id': 'msg_TESTONLY', 'type': 'message', 'role': 'assistant', 'model': CONFIG['model'],
                'content': content if content is not None else [{'type': 'text', 'text': text}],
                'stop_reason': stop, 'stop_sequence': None,
                'usage': {'input_tokens': 10, 'output_tokens': 20}, **(extra or {})})
        with httpx.Client(transport=httpx.MockTransport(handle), trust_env=False) as http:
            def client(**kwargs):
                constructor.append(kwargs)
                return Anthropic(api_key='TESTONLY-offline', base_url='https://synthetic.invalid', http_client=http, **kwargs)
            with patch('anthropic.Anthropic', side_effect=client):
                result = ai_stages._response({'notes': 'Unchanged source.\r\n', 'all_original_units': [1, 2]},
                    object_schema({'value': {'type': 'string'}}), 'Original instructions.', config, 32000, 240,
                    lambda response: callbacks.append(response.model_dump(mode='json')))
        self.assertEqual(constructor, [{'timeout': 240, 'max_retries': 0}])
        self.assertEqual(len(sent), 1); self.assertEqual(len(callbacks), 1)
        return sent[0], result, callbacks[0]

    def test_actual_SDK_omits_only_format_and_escaping_with_same_profile_payload_and_limits(self):
        config = ai_stages.pipeline_config(CONFIG)
        body, result, _ = self.sdk(config)
        old, _, _ = self.sdk({**config, legacy.CONFIG_KEY: envelope.TRANSPORT},
            text=json.dumps(envelope.encode(object_schema({'value': {'type': 'string'}}), {'value': 'Exact'})))
        schema = object_schema({'value': {'type': 'string'}})
        self.assertEqual(body['output_config'], {'effort': 'high'})
        self.assertEqual(body['thinking'], {'type': 'between_tools'})
        self.assertNotIn('tools', body); self.assertNotIn('tool_choice', body)
        self.assertEqual(body['system'], 'Original instructions.' + codec.instructions(schema))
        self.assertEqual(body['system'].count(legacy._json(schema)), 1)
        expected = deepcopy(old); expected['output_config'].pop('format'); expected['system'] = body['system']
        self.assertEqual(body, expected)
        self.assertEqual(json.loads(body['messages'][0]['content']), {'notes': 'Unchanged source.\r\n', 'all_original_units': [1, 2]})
        self.assertEqual(body['max_tokens'], 32000)
        self.assertEqual(ai_stages.generation_limits(config), (32000, 240))
        self.assertEqual(config['semantic_max_calls'], 5)
        self.assertEqual(Decimal(config['semantic_maximum_cost']), Decimal('8.15'))
        self.assertEqual(result[-2:], ('{"value":"Exact"}', True))

    def test_max_tokens_never_becomes_complete_even_for_valid_JSON_and_raw_is_retained(self):
        config = ai_stages.pipeline_config(CONFIG)
        for text in ('{"value":"Exact"}', '{"value":"PRIVATE_INCOMPLETE'):
            _, result, raw = self.sdk(config, text=text, stop='max_tokens')
            self.assertIs(result[-1], False)
            self.assertEqual(result[-2], text)
            self.assertEqual(raw['content'][0]['text'], text)
            self.assertEqual(raw['stop_reason'], 'max_tokens')
            self.assertIsNotNone(result[1])

    def test_malformed_end_turn_is_metered_and_retained_but_fails_whole_JSON(self):
        text = '{"value":"PRIVATE_OUTPUT_MARKER'
        _, result, raw = self.sdk(ai_stages.pipeline_config(CONFIG), text=text)
        self.assertIsNotNone(result[1]); self.assertEqual(raw['content'][0]['text'], text)
        with self.assertRaises(ValueError) as raised:
            codec.decode(object_schema({'value': {'type': 'string'}}), codec.strict_loads(result[-2]))
        self.assertNotIn('PRIVATE_OUTPUT_MARKER', str(raised.exception))

    def test_empty_refused_and_mixed_responses_stay_metered_but_ineligible(self):
        config = ai_stages.pipeline_config(CONFIG)
        for content, extra in (([], {}), ([{'type': 'text', 'text': '  '}], {}),
                ([{'type': 'text', 'text': '{"value":"Exact"}'}],
                    {'stop_details': {'type': 'refusal'}}),
                ([{'type': 'thinking', 'thinking': 'PRIVATE_THINKING', 'signature': 'TESTONLY'},
                    {'type': 'text', 'text': '{"value":"Exact"}'}], {}),
                ([{'type': 'tool_use', 'id': 'toolu_TESTONLY', 'name': 'unrequested', 'input': {}},
                    {'type': 'text', 'text': '{"value":"Exact"}'}], {}),
                ([{'type': 'unknown_block', 'text': '{"value":"Exact"}'}], {})):
            with self.subTest(content=content, extra=extra):
                _, result, raw = self.sdk(config, content=content, extra=extra)
                self.assertIs(result[-1], False)
                self.assertIsNotNone(result[1])
                self.assertEqual(len(raw['content']), len(content))

    def test_text_chunks_require_one_entire_unambiguous_JSON_value(self):
        schema = object_schema({'value': {'type': 'string'}})
        config = ai_stages.pipeline_config(CONFIG)
        chunks = [{'type': 'text', 'text': '{"value":'}, {'type': 'text', 'text': '"Exact"}'}]
        _, result, _ = self.sdk(config, content=chunks)
        self.assertIs(result[-1], True)
        self.assertEqual(codec.decode(schema, codec.strict_loads(result[-2])), {'value': 'Exact'})
        chunks = [{'type': 'text', 'text': '{"value":"One"}'}, {'type': 'text', 'text': '{"value":"Two"}'}]
        _, result, _ = self.sdk(config, content=chunks)
        with self.assertRaises(ValueError):codec.decode(schema, codec.strict_loads(result[-2]))

    def test_historical_v4_response_eligibility_is_not_reinterpreted(self):
        config = {**ai_stages.pipeline_config(CONFIG), legacy.CONFIG_KEY: envelope.TRANSPORT}
        content = [{'type': 'thinking', 'thinking': 'TESTONLY', 'signature': 'TESTONLY'},
            {'type': 'text', 'text': '{}'}]
        _, result, _ = self.sdk(config, content=content)
        self.assertEqual(result[-2:], ('{}', True))

    def test_unsupported_original_schema_refuses_before_client_creation(self):
        with patch('anthropic.Anthropic') as client, self.assertRaises(ValueError):
            ai_stages._response({}, {'type': 'string', 'default': 'invented'}, 'Original.',
                ai_stages.pipeline_config(CONFIG), 32000, 240, lambda response: None)
        client.assert_not_called()
