"""Complete canonical JSON carrier, original gates, real offline SDK and history."""
from copy import deepcopy
from decimal import Decimal
import json
from unittest.mock import patch

from anthropic import Anthropic
from django.test import SimpleTestCase
import httpx

from core import ai_stages, anthropic_request_policy as policy
from core import clinical_schema_transport as legacy, clinical_json_transport as codec
from core import clinical_evidence_transport as evidence, clinical_node_transport as nodes
from core.provider_schema import retained_request_matches
from core.tests.test_clinical_schema_transport import CONFIG, nullable, object_schema


class ClinicalJSONTransportTests(SimpleTestCase):
    def test_exact_types_unicode_empty_containers_null_and_optional_missing(self):
        schema = object_schema({'/~': {'type': 'string'}, 'i': {'type': 'integer'},
            'n': {'type': 'number'}, 'b': {'type': 'boolean'}, 'null': {'type': 'null'},
            'array': {'type': 'array', 'items': nullable({'type': 'number'})},
            'object': object_schema({})})
        value = {'/~': '界😀"\\\n', 'i': 2**80, 'n': -0.0, 'b': False, 'null': None,
            'array': [None, 0, 0.0], 'object': {}}
        original = deepcopy(value)
        wire = codec.encode(schema, value)
        decoded = codec.decode(schema, codec.strict_loads(json.dumps(wire)))
        self.assertEqual(legacy._json(decoded), legacy._json(value))
        self.assertIs(type(decoded['i']), int); self.assertIs(type(decoded['n']), float)
        self.assertIs(type(decoded['b']), bool); self.assertIs(type(decoded['array'][1]), int)
        self.assertIs(type(decoded['array'][2]), float)
        self.assertEqual(value, original)
        optional = object_schema({'x': nullable({'type': 'string'})}); optional['required'] = []
        for value in ({}, {'x': None}, {'x': ''}):
            self.assertEqual(codec.decode(optional, codec.encode(optional, value)), value)

    def test_generic_worked_serialization_example_is_valid_not_an_empty_skeleton(self):
        text = codec.INSTRUCTIONS.split('becomes ', 1)[1]
        wire, _ = json.JSONDecoder().raw_decode(text)
        self.assertEqual(wire['transport'], codec.TRANSPORT)
        self.assertEqual(codec.strict_loads(wire['document_json']),
            {'items': [{'label': 'A', 'value': 2.5}], 'missing': None, 'ok': False})

    def test_full_original_schema_annotations_once_in_system_not_wrapper(self):
        schema = object_schema({'subject': {'title': 'EXACT_TITLE', 'anyOf': [
            object_schema({'kind': {'type': 'string', 'enum': ['patient'], 'description': 'PATIENT_ONLY'},
                           'name': nullable({'type': 'string', 'description': 'NULLABLE_NAME'})}),
            object_schema({'kind': {'type': 'string', 'enum': ['other'], 'description': 'OTHER_ONLY'},
                           'name': {'type': 'string', 'minLength': 1}})]}})
        before = deepcopy(schema)
        original = legacy._json(schema)
        instructions = codec.instructions(schema)
        self.assertEqual(instructions.count(original), 1)
        self.assertTrue(instructions.endswith(original))
        wire = codec.wire_schema(schema)
        self.assertNotIn(original, json.dumps(wire))
        self.assertEqual(wire['required'], ['transport', 'document_json'])
        self.assertFalse(wire['additionalProperties'])
        self.assertEqual(schema, before)
        other = object_schema({'x': {'type': 'array', 'items': {'type': 'integer'}}})
        self.assertEqual(wire, codec.wire_schema(other))

    def test_malformed_duplicate_nonfinite_or_incomplete_inner_JSON_refuses(self):
        schema = object_schema({'x': {'type': 'number'}})
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}',
                     '{"x":-Infinity}', '{"x":1e999}', '{"x":', '{}{}', 'null', ''):
            with self.subTest(text=text), self.assertRaises(ValueError):
                codec.decode(schema, {'transport': codec.TRANSPORT, 'document_json': text})
        for text in ('{"transport":"x","transport":"y"}', '{"x":NaN}', '{}{}'):
            with self.subTest(outer=text), self.assertRaises(ValueError): codec.strict_loads(text)

    def test_every_original_type_enum_required_closed_and_bound_still_applies(self):
        schema = object_schema({'x': {'type': 'string', 'enum': ['ok'], 'maxLength': 2},
            'i': {'type': 'integer', 'minimum': 1}, 'b': {'type': 'boolean'},
            'a': {'type': 'array', 'maxItems': 1, 'items': {'type': 'number'}}})
        valid = {'x': 'ok', 'i': 1, 'b': False, 'a': [1.5]}
        for value in ({}, {**valid, 'extra': None}, {**valid, 'x': 'bad'},
                      {**valid, 'i': True}, {**valid, 'i': 0}, {**valid, 'b': 0},
                      {**valid, 'a': [1, 2]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                codec.decode(schema, {'transport': codec.TRANSPORT, 'document_json': json.dumps(value)})
        for wire in ({'transport': nodes.TRANSPORT, 'document_json': '{}'},
                     {'transport': codec.TRANSPORT, 'document_json': {}},
                     {'transport': codec.TRANSPORT, 'document_json': '{}', 'extra': True}):
            with self.subTest(wire=wire), self.assertRaises(ValueError): codec.decode(schema, wire)

    def test_complete_three_stage_model_20_destinations_and_source_gates(self):
        from core import source_assertion_generation as generation, source_assertion_graph as graph
        from core.tests.test_source_assertion_graph import IDENTITY, base_case, checker, run_case, definitions, assignments
        from core.tests.test_source_assertion_generation import stated_time_case
        base = base_case()
        fields, defs = definitions(('Symptoms',) * 20)
        twenty = (base[0], fields, defs, base[3], assignments(fields, {f['key']: ['f1'] for f in fields}))
        for case in (base, stated_time_case(), twenty):
            expected, _ = run_case(case)
            notes, fields, defs, raw, assigned = case
            def send(role, attempt, payload, schema, instructions):
                value = raw if role == 'extractor' else assigned if role == 'assigner' else checker(
                    payload['graph'], fields, defs, assigned)
                return codec.decode(schema, codec.encode(schema, value))
            actual = generation.run(notes, fields, defs, send, identity=IDENTITY)
            self.assertEqual(actual, expected)
            self.assertEqual(generation.restore(notes, actual['interpretation']), actual['answers'])
            self.assertEqual(len(actual['answers']), len(fields))
        bad = deepcopy(raw); bad['facts'][0]['value_span']['quote'] = 'Invented source'
        restored = codec.decode(graph.extraction_schema(), codec.encode(graph.extraction_schema(), bad))
        with self.assertRaises(Exception): graph.compile_graph(notes, restored)

    def test_original_200_fact_bound_preserved_without_truncation(self):
        from core import source_assertion_graph as graph
        from core.tests.test_source_assertion_graph import base_case
        raw = base_case()[3]
        raw['facts'] = [{**deepcopy(raw['facts'][1]), 'id': 'f' + str(i)} for i in range(200)]
        schema = graph.extraction_schema()
        self.assertEqual(codec.decode(schema, codec.encode(schema, raw)), raw)
        raw['facts'].append({**deepcopy(raw['facts'][0]), 'id': 'f200'})
        with self.assertRaises(ValueError): codec.encode(schema, raw)

    def test_exact_new_envelope_schema_and_profile_replay_binding(self):
        schema = object_schema({'value': nullable({'type': 'string'})})
        config = {**ai_stages.pipeline_config(CONFIG), legacy.CONFIG_KEY: codec.TRANSPORT}
        expected = {'stage': 'extractor', 'schema': schema, 'payload': {'notes': 'Complete unchanged source'}}
        request = {**expected, 'schema_transport': codec.TRANSPORT,
            policy.ENVELOPE_KEY: policy.parameters(config), 'transmitted_schema': json.dumps(
                legacy.transmitted_schema(schema, codec.TRANSPORT), ensure_ascii=False, separators=(',', ':'), allow_nan=False)}
        before = deepcopy(request)
        self.assertTrue(retained_request_matches(request, expected, config=config, provider='anthropic', simulated=False))
        text = json.dumps(codec.encode(schema, {'value': 'Exact'}))
        self.assertEqual(legacy.response_value(text, request, config=config, provider='anthropic', simulated=False), {'value': 'Exact'})
        for key in ('transmitted_schema', policy.ENVELOPE_KEY):
            altered = deepcopy(request); altered.pop(key)
            self.assertFalse(retained_request_matches(altered, expected, config=config, provider='anthropic', simulated=False))
        for cfg, provider, simulated in (({**config, legacy.CONFIG_KEY: nodes.TRANSPORT}, 'anthropic', False),
                (config, 'openai', False), (config, 'anthropic', True)):
            with self.assertRaises(ValueError): legacy.response_value(text, request, config=cfg, provider=provider, simulated=simulated)
        self.assertEqual(request, before)

    def test_historical_v1_v2_v3_decode_and_instructions_unchanged(self):
        schema = object_schema({'value': nullable({'type': 'string'})})
        for module in (legacy, evidence, nodes):
            marker = module.TRANSPORT if module is not nodes else legacy.CURRENT_TRANSPORT
            cfg = {**CONFIG, legacy.CONFIG_KEY: marker}
            self.assertEqual(legacy.instructions(cfg, schema=schema), module.INSTRUCTIONS)
            value = {'value': 'Exact historical value'}
            request = {'schema': schema, 'schema_transport': marker}
            text = json.dumps(module.encode(schema, value))
            self.assertEqual(legacy.response_value(text, request, config=cfg, provider='anthropic', simulated=False), value)
        self.assertEqual(legacy.CURRENT_TRANSPORT, nodes.TRANSPORT)
        self.assertEqual(legacy.JSON_TRANSPORT, codec.TRANSPORT)

    def test_actual_SDK_full_canonical_schema_once_complete_payload_and_same_profile(self):
        from core import source_assertion_graph as graph
        schema = graph.extraction_schema()
        payload = {'notes': 'Complete original notes', 'all_original_units': [1, 2]}
        config = {**ai_stages.pipeline_config(CONFIG), legacy.CONFIG_KEY: codec.TRANSPORT}
        sent, callbacks = [], []
        def handle(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, headers={'request-id': 'req_offline'}, json={
                'id': 'msg_offline', 'type': 'message', 'role': 'assistant', 'model': CONFIG['model'],
                'content': [{'type': 'text', 'text': '{}'}], 'stop_reason': 'end_turn',
                'stop_sequence': None, 'usage': {'input_tokens': 10, 'output_tokens': 1}})
        with httpx.Client(transport=httpx.MockTransport(handle), trust_env=False) as http:
            def client(**kwargs):
                self.assertEqual(kwargs, {'timeout': 240, 'max_retries': 0})
                return Anthropic(api_key='offline-only', base_url='https://synthetic.invalid', http_client=http, **kwargs)
            with patch('anthropic.Anthropic', side_effect=client):
                ai_stages._response(payload, schema, 'Original instructions.', config, 32000, 240, callbacks.append)
        self.assertEqual(len(sent), 1); self.assertEqual(len(callbacks), 1)
        body = sent[0]; original = legacy._json(schema)
        self.assertEqual(body['system'], 'Original instructions.' + codec.instructions(schema))
        self.assertEqual(body['system'].count(original), 1)
        self.assertNotIn(original, json.dumps(body['output_config']['format']['schema']))
        self.assertEqual(body['output_config']['format']['schema'], legacy.transmitted_schema(schema, codec.TRANSPORT))
        self.assertEqual(json.loads(body['messages'][0]['content']), payload)
        self.assertEqual(body['thinking'], {'type': 'between_tools'})
        self.assertEqual(body['output_config']['effort'], 'high')
        self.assertEqual(body['max_tokens'], 32000)
        self.assertEqual(config['semantic_max_calls'], 5)
        self.assertEqual(Decimal(config['semantic_maximum_cost']), Decimal('8.15'))

    def test_unsupported_original_schema_refuses_before_SDK_client(self):
        config = ai_stages.pipeline_config(CONFIG)
        with patch('anthropic.Anthropic') as client, self.assertRaises(ValueError):
            ai_stages._response({}, {'type': 'string', 'default': 'invented'}, 'Original.', config, 32000, 240, lambda response: None)
        client.assert_not_called()
