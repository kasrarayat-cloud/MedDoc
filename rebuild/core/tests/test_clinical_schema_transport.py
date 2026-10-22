"""Offline typed codec, clinical meaning, actual SDK and retained replay boundaries."""
from copy import deepcopy
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import patch

from anthropic import Anthropic, transform_schema
from django.test import SimpleTestCase, TestCase, override_settings
import httpx

from core import ai_stages, clinical_schema_transport as codec
from core import source_assertion_generation as generation, source_assertion_graph as graph
from core import source_interpretation_store as store
from core.provider_schema import ANTHROPIC_SCHEMA_TRANSPORT, retained_request_matches, share_anthropic_schema
from core.tests.test_provider_schema import count, expand
from core.tests.test_source_assertion_graph import IDENTITY, base_case, checker, run_case
from core.tests.test_source_assertion_generation import stated_time_case

CONFIG = {'mode': 'live', 'provider': 'anthropic', 'model': 'claude-sonnet-5-5',
          'input_rate': '2', 'cached_rate': '.2', 'output_rate': '10'}


def nullable(item):
    return {'anyOf': [item, {'type': 'null'}]}


def object_schema(properties):
    return {'type': 'object', 'required': list(properties), 'additionalProperties': False, 'properties': properties}


class ClinicalSchemaTransportTests(SimpleTestCase):
    def test_actual_schema_removes_only_nullable_unions_without_mutation(self):
        original = graph.extraction_schema()
        before = deepcopy(original)
        wire = codec.wire_schema(original)
        shared = share_anthropic_schema(transform_schema(wire))
        self.assertEqual(original, before)
        self.assertEqual(count(original, 'anyOf'), 15)
        self.assertEqual(count(wire, 'anyOf'), 1)
        self.assertEqual(count(wire, 'maxItems'), count(original, 'maxItems') + 14)
        self.assertEqual(expand(shared), transform_schema(wire))
        self.assertEqual(transform_schema(shared), shared)

    def test_nested_null_empty_array_and_present_nullable_array_are_distinct(self):
        schema = object_schema({'value': nullable({'type': 'array', 'maxItems': 2,
            'items': nullable({'type': 'string', 'maxLength': 20})})})
        for canonical, wire in ((None, []), ([], [[]]), ([None], [[[]]]),
                                 (['null', ''], [[['null'], ['']]])):
            with self.subTest(canonical=canonical):
                self.assertEqual(codec.encode(schema, {'value': canonical}), {'value': wire})
                self.assertEqual(codec.decode(schema, {'value': wire}), {'value': canonical})

    def test_nonnullable_null_and_nullable_title_are_preserved(self):
        schema = object_schema({'always': {'type': 'null'},
            'maybe': {**nullable({'type': 'string'}), 'title': 'Exact title', 'description': 'Exact description'}})
        wire_schema = codec.wire_schema(schema)
        self.assertEqual(wire_schema['properties']['always'], {'type': 'null'})
        self.assertEqual(wire_schema['properties']['maybe']['title'], 'Exact title')
        self.assertTrue(wire_schema['properties']['maybe']['description'].startswith('Exact description'))
        self.assertEqual(codec.decode(schema, {'always': None, 'maybe': []}), {'always': None, 'maybe': None})

    def test_unicode_quotes_newlines_order_bounds_and_false_values_are_lossless(self):
        schema = object_schema({'value': nullable({'type': 'string', 'maxLength': 2000}),
            'zero': nullable({'type': 'integer', 'minimum': 0}),
            'false': nullable({'type': 'boolean'})})
        value = {'value': '界😀"\\\n' * 300, 'zero': 0, 'false': False}
        before = deepcopy(value)
        wire = codec.encode(schema, value)
        self.assertEqual(codec.decode(schema, wire), value)
        self.assertEqual(list(wire), list(value))
        self.assertEqual(value, before)
        self.assertEqual(codec.decode(schema, codec.strict_loads(json.dumps(wire))), value)

    def test_wire_arity_null_type_and_original_bounds_are_not_coerced(self):
        schema = object_schema({'value': nullable({'type': 'integer', 'minimum': 1, 'maximum': 4})})
        for invalid in (None, 1, {}, '[]', [None], [True], ['1'], [0], [5], [1, 2], [[1]]):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                codec.decode(schema, {'value': invalid})
        for invalid in ({}, {'value': [], 'extra': []}, {'value': [2], 'extra': 3}):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                codec.decode(schema, invalid)

    def test_duplicate_keys_nonfinite_overflow_and_trailing_JSON_refuse(self):
        for text in ('{"value":[],"value":[1]}', '{"x":{"a":1,"a":2}}',
                     '{"value":[NaN]}', '{"value":[Infinity]}', '{"value":[-Infinity]}',
                     '{"value":[]}{}', '\ufeff{"value":[]}'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                codec.strict_loads(text)
        schema = object_schema({'value': nullable({'type': 'number'})})
        for value in (float('inf'), float('-inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                codec.decode(schema, {'value': [value]})
        with self.assertRaises(ValueError):codec.decode(schema, codec.strict_loads('{"value":[1e999]}'))

    def test_all_original_scalar_array_enum_and_closed_object_constraints_apply(self):
        schema = object_schema({'a': {'type': 'array', 'minItems': 1, 'maxItems': 2,
            'items': nullable({'type': 'string', 'minLength': 1, 'maxLength': 2, 'enum': ['a', 'bb']})},
            'b': {'type': 'number', 'minimum': 0, 'maximum': 2}})
        valid = {'a': [None, 'bb'], 'b': 2}
        self.assertEqual(codec.decode(schema, codec.encode(schema, valid)), valid)
        for value in ({**valid, 'a': []}, {**valid, 'a': [None]*3}, {**valid, 'a': ['']},
                      {**valid, 'a': ['abc']}, {**valid, 'a': ['c']}, {**valid, 'b': True},
                      {**valid, 'b': -1}, {**valid, 'b': 3}):
            with self.subTest(value=value), self.assertRaises(ValueError):codec.encode(schema, value)

    def test_unknown_schema_features_refuse_instead_of_dropping_constraints(self):
        for extra in ({'pattern': 'x'}, {'$ref': '#/$defs/x'}, {'allOf': []},
                      {'default': 'guess'}, {'format': 'date'}, {'uniqueItems': True}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                codec.wire_schema({'type': 'string', **extra})
        for schema in ({'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': True},
                       {'type': 'array', 'items': {'type': 'string'}, 'maxItems': True},
                       {'type': 'string', 'maxLength': -1}, {'type': 'number', 'minimum': float('nan')}):
            with self.subTest(schema=schema), self.assertRaises(ValueError):codec.wire_schema(schema)

    def test_graph_run_restore_preserves_identity_time_evidence_and_clinical_results(self):
        def reverse(value):
            if type(value) is dict:return {k: reverse(v) for k, v in reversed(list(value.items()))}
            if type(value) is list:return [reverse(v) for v in value]
            return value
        for case in (base_case(), stated_time_case()):
            expected, _ = run_case(case)
            notes, fields, definitions, raw, assignment = case
            before = deepcopy(case)
            calls = []
            def send(role, attempt, payload, schema, instructions):
                calls.append(role)
                value = raw if role == 'extractor' else assignment if role == 'assigner' else checker(
                    payload['graph'], fields, definitions, assignment)
                return codec.decode(schema, codec.strict_loads(json.dumps(codec.encode(schema, value))))
            actual = generation.run(notes, fields, definitions, send, identity=IDENTITY)
            self.assertEqual(actual, expected)
            self.assertEqual(generation.restore(notes, actual['interpretation']), actual['answers'])
            self.assertEqual(case, before)
            self.assertEqual(calls, ['extractor', 'assigner', 'checker'])
            reversed_case = [reverse(part) for part in case]
            self.assertEqual(run_case(reversed_case)[0], actual)

    def test_roundtrip_does_not_waive_canonical_source_reference_validation(self):
        notes, fields, definitions, raw, assigned = base_case()
        raw['facts'][0]['value_span']['quote'] = 'Invented unrelated name'
        decoded = codec.decode(graph.extraction_schema(), codec.encode(graph.extraction_schema(), raw))
        with self.assertRaises(Exception):graph.compile_graph(notes, decoded)

    def test_prospective_selection_old_limits_and_explicit_bad_markers(self):
        current = ai_stages.pipeline_config(CONFIG)
        self.assertEqual(current[codec.CONFIG_KEY], codec.CURRENT_TRANSPORT)
        self.assertEqual(ai_stages.generation_limits(current), (32000, 240))
        self.assertEqual(Decimal(current['semantic_maximum_cost']), Decimal('8.15'))
        self.assertNotIn(codec.CONFIG_KEY, CONFIG)
        for mode, provider, model in (('fixture', 'anthropic', CONFIG['model']),
                ('live', 'openai', CONFIG['model']), ('live', 'anthropic', 'synthetic-model')):
            self.assertNotIn(codec.CONFIG_KEY, ai_stages.pipeline_config({**CONFIG,
                'mode': mode, 'provider': provider, 'model': model}))
        for marker in (None, False, '', 'unknown', ANTHROPIC_SCHEMA_TRANSPORT):
            with self.subTest(marker=marker), patch.object(ai_stages, 'parent_context') as parent:
                with self.assertRaises(ai_stages.StageNotSent):
                    ai_stages.execute_stage(job=object(), stage='extractor', payload={}, schema={},
                        instructions='', config={**CONFIG, codec.CONFIG_KEY: marker})
                parent.assert_not_called()

    def test_exact_old_new_envelope_binding_and_cross_transport_refusal(self):
        expected = {'stage': 'extractor', 'schema': graph.extraction_schema(), 'payload': {'source': 'Exact'}}
        cfg = {**CONFIG, codec.CONFIG_KEY: codec.TRANSPORT}
        marked = {**expected, 'schema_transport': codec.TRANSPORT}
        self.assertTrue(retained_request_matches(marked, expected, config=cfg, provider='anthropic', simulated=False))
        for request, config in ((expected, cfg), ({**expected, 'schema_transport': ANTHROPIC_SCHEMA_TRANSPORT}, cfg),
                                (marked, CONFIG), ({**marked, 'payload': {}}, cfg),
                                ({**marked, 'stage': 'checker'}, cfg)):
            with self.subTest(request=request, config=config):
                self.assertFalse(retained_request_matches(request, expected,
                    config=config, provider='anthropic', simulated=False))
        for request in (expected, {**expected, 'schema_transport': ANTHROPIC_SCHEMA_TRANSPORT}):
            self.assertTrue(retained_request_matches(request, expected, config=CONFIG, provider='anthropic', simulated=False))

    def sdk_call(self, config):
        sent, retained = [], []
        schema = object_schema({'value': nullable({'type': 'string', 'maxLength': 10})})
        raw = json.dumps({'value': ['exact']} if codec.selected(config) else {'value': 'exact'})
        def handle(request):
            sent.append(json.loads(request.content))
            self.assertEqual(request.extensions['timeout']['read'], 240)
            return httpx.Response(200, headers={'request-id': 'req_offline'}, json={
                'id': 'msg_offline', 'type': 'message', 'role': 'assistant', 'model': CONFIG['model'],
                'content': [{'type': 'text', 'text': raw}], 'stop_reason': 'end_turn',
                'stop_sequence': None, 'usage': {'input_tokens': 1000, 'output_tokens': 20}})
        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            def client(**kwargs):
                self.assertEqual(kwargs, {'timeout': 240, 'max_retries': 0})
                return Anthropic(api_key='offline-only', base_url='https://synthetic.invalid', http_client=http, **kwargs)
            with patch('anthropic.Anthropic', side_effect=client):
                result = ai_stages._response({'source': 'Unchanged'}, schema, 'Original instruction.',
                    config, 32000, 240, retained.append)
        self.assertEqual(len(sent), 1)
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].content[0].text, raw)
        self.assertEqual(result[-2], raw)
        self.assertEqual(result[1], Decimal('0.0022'))
        self.assertNotIn('thinking', sent[0])
        self.assertNotIn('stream', sent[0])
        return sent[0], schema

    def test_actual_SDK_new_wire_and_old_absence_are_exact_separate_paths(self):
        old, schema = self.sdk_call(CONFIG)
        new, _ = self.sdk_call({**CONFIG, codec.CONFIG_KEY: codec.TRANSPORT})
        self.assertEqual(old['system'], 'Original instruction.')
        self.assertEqual(old['output_config']['format']['schema'], share_anthropic_schema(transform_schema(schema)))
        self.assertEqual(new['system'], old['system'] + codec.INSTRUCTIONS)
        self.assertEqual(new['output_config']['format']['schema'], share_anthropic_schema(transform_schema(codec.wire_schema(schema))))
        for key in old.keys() - {'system', 'output_config'}:self.assertEqual(old[key], new[key])

    def test_retained_private_reader_preserves_raw_and_requires_matching_marker(self):
        schema = object_schema({'value': nullable({'type': 'string'})})
        config = {**CONFIG, codec.CONFIG_KEY: codec.TRANSPORT}
        row = SimpleNamespace(simulated=False, config=config, provider='anthropic',
            provider_request_id='req_saved', provider_resource_id='msg_saved', returned_model=CONFIG['model'])
        request = {'schema': schema, 'schema_transport': codec.TRANSPORT}
        wrapper = {'provider_output': {'content': [{'type': 'text', 'text': '{"value":["Exact"]}'}]},
            'provider_request_id': row.provider_request_id, 'provider_resource_id': row.provider_resource_id,
            'returned_model': row.returned_model}
        before = deepcopy(wrapper)
        self.assertEqual(store._output(wrapper, row, request), {'value': 'Exact'})
        self.assertEqual(wrapper, before)
        for bad in ({}, {**request, 'schema_transport': ANTHROPIC_SCHEMA_TRANSPORT}):
            with self.assertRaises(Exception):store._output(wrapper, row, bad)
        malformed = deepcopy(wrapper); malformed['provider_output']['content'][0]['text'] = '{"value":["a","b"]}'
        with self.assertRaises(Exception):store._output(malformed, row, request)

    def test_complete_store_replay_uses_bound_wire_and_keeps_original_private_bytes(self):
        from core.tests.test_source_interpretation_store import InterpretationStoreTests
        fixture = InterpretationStoreTests('test_exact_three_stage_lineage_round_trip_without_provider')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        outputs = [store._output(store._read(r.result_path, r.result_sha256), r) for r in fixture.rows]
        fixture.transport_lineage(marker=codec.TRANSPORT,
            config_changes={'model': CONFIG['model'], codec.CONFIG_KEY: codec.TRANSPORT})
        raw_files = []
        for row, output in zip(fixture.rows, outputs):
            request = store._read(row.request_path, row.request_sha256)
            wrapper = store._read(row.result_path, row.result_sha256)
            wrapper['provider_output']['content'][0]['text'] = json.dumps(codec.encode(request['schema'], output))
            row.result_path, row.result_sha256 = ai_stages.retain(wrapper)
            raw_files.append((row.result_path, row.result_sha256, store.private_path(row.result_path).read_bytes()))
        manifest = store._retained(fixture.job, fixture.interpretation, fixture.answers)
        self.assertEqual(len(manifest), 3)
        self.assertEqual(generation.restore(fixture.encounter.notes, fixture.interpretation), fixture.answers)
        fixture.assert_request_bytes_unchanged(raw_files)
        row = fixture.rows[0]
        original_config = row.config
        row.config = {**original_config, codec.CONFIG_KEY: 'wrong'}
        with self.assertRaises(Exception):store._retained(fixture.job, fixture.interpretation, fixture.answers)


@override_settings(WORD_PREPARATION_ENABLED=True, AI_MODE='fixture', TESTING_AUTHORITY_MODE='',
    TESTING_AUTHORITY_ID='', TESTING_AUTHORITY_SHA256='', ADMIN_SITE=False,
    STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
              'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class ClinicalStageAccountingTests(TestCase):
    def setUp(self):
        from core.tests.test_ai_stages import IndependentStageTests
        IndependentStageTests.setUp(self)

    def test_billable_malformed_wire_is_failed_with_raw_cost_retained_and_no_retry(self):
        import os
        from core.jobs import enqueue
        from core import generation as billing_generation
        from core.models import Wallet
        from core.tests.test_billing_policy import fund
        from core.security import private_path
        fund(Wallet.objects.get(user=self.user, kind='paid'), Decimal('10'), 'payment:clinical-codec-test')
        job = enqueue(self.encounter, self.user, config=CONFIG)
        job.state = 'running'; job.save(update_fields=['state'])
        schema = object_schema({'value': nullable({'type': 'string', 'maxLength': 3})})
        for_wire = '{"value":["a","b"]}'
        response = SimpleNamespace(id='msg_billable_invalid', _request_id='req_billable_invalid', model=CONFIG['model'],
            model_dump=lambda **kwargs: {'content': [{'type': 'text', 'text': for_wire}],
                'usage': {'input_tokens': 1000, 'output_tokens': 20}})
        def provider(payload, schema, instructions, config, maximum, timeout, on_response):
            on_response(response)
            units = {'input_tokens': 1000, 'cached_input_tokens': 0, 'cache_creation_tokens': 0, 'output_tokens': 20}
            rates = billing_generation.cost_rates(billing_generation.rates(config), Decimal('.0022'), Decimal('0'))
            return response, Decimal('.0022'), units, rates, for_wire, True
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'offline-only'}), \
                patch.object(ai_stages, '_response', side_effect=provider) as send:
            with self.assertRaises(ai_stages.StageFailure):
                ai_stages.execute_stage(job=job, stage='extractor', payload={'source': 'Synthetic'},
                    schema=schema, instructions='Original', config=job.config)
            self.assertEqual(send.call_count, 1)
            row = job.ai_stage_receipts.get()
            self.assertEqual((row.state, row.error_code), ('failed', 'invalid_response'))
            self.assertEqual(row.actual_cost, Decimal('.0022'))
            self.assertEqual(row.usage, {'input_tokens': 1000, 'cached_input_tokens': 0,
                                       'cache_creation_tokens': 0, 'output_tokens': 20})
            retained = json.loads(private_path(row.result_path).read_bytes())
            self.assertEqual(retained['provider_output']['content'][0]['text'], for_wire)
            with self.assertRaises(ai_stages.StageNotSent):
                ai_stages.execute_stage(job=job, stage='extractor', payload={'source': 'Synthetic'},
                    schema=schema, instructions='Original', config=job.config)
            self.assertEqual(send.call_count, 1)
            self.assertEqual(job.ai_stage_receipts.count(), 1)
