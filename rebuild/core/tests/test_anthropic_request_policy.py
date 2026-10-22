"""Actual SDK bytes, historical replay and durable policy admission, offline."""
from contextlib import nullcontext
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from anthropic import Anthropic
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
import httpx

from core import ai_stages, anthropic_request_policy as policy, generation, preparation
from core import clinical_schema_transport as transport, clinical_node_transport as nodes
from core.provider_schema import retained_request_matches
from core.tests.test_clinical_schema_transport import CONFIG
from core.tests.test_source_assertion_graph import base_case


class AnthropicRequestPolicyTests(SimpleTestCase):
    def sdk(self, invoke, *, thinking_only=False):
        sent, retained = [], []
        def handle(request):
            self.assertEqual(request.url.host, 'synthetic-provider.invalid')
            sent.append(json.loads(request.content))
            content = ([{'type': 'thinking', 'thinking': '[offline control]', 'signature': 'TESTONLY'}]
                if thinking_only else [{'type': 'text', 'text': self.response_text}])
            return httpx.Response(200, headers={'request-id': 'req_offline_policy'}, json={
                'id': 'msg_offline_policy', 'type': 'message', 'role': 'assistant', 'model': CONFIG['model'],
                'content': content, 'stop_reason': 'max_tokens' if thinking_only else 'end_turn',
                'stop_sequence': None, 'usage': {'input_tokens': 10,
                    'output_tokens': 32000 if thinking_only else 1}})
        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            def client(**kwargs):
                self.assertEqual(kwargs['max_retries'], 0)
                return Anthropic(api_key='offline-only', base_url='https://synthetic-provider.invalid',
                    http_client=http, **kwargs)
            with patch('anthropic.Anthropic', side_effect=client):
                result = invoke(retained.append)
        self.assertEqual(len(sent), 1)
        return sent[0], result, retained

    def test_closed_profile_historical_absence_and_defensive_copies(self):
        self.assertEqual(policy.parameters(CONFIG), {})
        self.assertNotIn(policy.CONFIG_KEY, CONFIG)
        selected = policy.prospective(CONFIG)
        self.assertEqual(selected[policy.CONFIG_KEY], policy.PROFILE)
        self.assertEqual(policy.parameters(selected), {
            'thinking': {'type': 'between_tools'}, 'output_config': {'effort': 'high'}})
        value = policy.parameters(selected); value['thinking']['type'] = 'adaptive'
        self.assertEqual(policy.parameters(selected)['thinking']['type'], 'between_tools')
        envelope = {'output_config': {'format': {'schema': {'exact': ['unchanged']}}}, 'messages': []}
        before = deepcopy(envelope)
        new = policy.apply(envelope, selected)
        new['output_config']['format']['schema']['exact'].append('local mutation')
        self.assertEqual(envelope, before)
        self.assertEqual(policy.apply(envelope, CONFIG), envelope)
        for config in ({**CONFIG, 'model': 'unreviewed'}, {**CONFIG, 'provider': 'openai'},
                       {**CONFIG, 'mode': 'fixture'}):
            self.assertEqual(policy.prospective(config), config)

    def test_unknown_or_incompatible_explicit_profiles_refuse_before_parent_or_SDK(self):
        cases = [{**CONFIG, policy.CONFIG_KEY: x} for x in (None, False, True, 0, '', [], {}, 'future')]
        cases += [{**policy.prospective(CONFIG), key: value} for key, value in (
            ('mode', 'fixture'), ('provider', 'openai'), ('model', 'claude-sonnet-5-5-future'))]
        for config in cases:
            with self.subTest(config=config), patch.object(ai_stages, 'parent_context') as parent, \
                 patch('anthropic.Anthropic') as SDK:
                with self.assertRaises(ai_stages.StageNotSent):
                    ai_stages.execute_stage(job=object(), stage='extractor', payload={}, schema={},
                        instructions='', config=config)
                with self.assertRaises(ai_stages.StageNotSent):
                    ai_stages._response({}, {}, '', config, 32000, 240, lambda value: None)
                with self.assertRaises(ValidationError): generation.generate('', [], config)
                parent.assert_not_called(); SDK.assert_not_called()

    @override_settings(AI_MODE='live', AI_PROVIDER='anthropic', AI_MODEL=policy.MODEL)
    def test_new_configuration_and_all_new_stage_profiles_share_the_selection(self):
        config = generation.configuration()
        self.assertEqual(config[policy.CONFIG_KEY], policy.PROFILE)
        for value in (ai_stages.pipeline_config(CONFIG), ai_stages.definition_pipeline_config(CONFIG),
                      ai_stages.revalidation_config(CONFIG)):
            self.assertEqual(value[policy.CONFIG_KEY], policy.PROFILE)
        self.assertNotIn(policy.CONFIG_KEY, CONFIG)
        stage = ai_stages.pipeline_config(CONFIG)
        self.assertEqual(ai_stages.generation_limits(stage), (32000, 240))
        self.assertEqual(stage['semantic_max_calls'], 5)
        self.assertEqual(stage['semantic_maximum_cost'], '8.15000000000')

    def test_actual_stage_SDK_changes_only_thinking_and_effort(self):
        from core import source_assertion_graph as graph
        raw = base_case()[3]; schema = graph.extraction_schema()
        self.response_text = json.dumps(nodes.encode(schema, raw))
        # Isolate the historical v3 policy comparison from newer carrier defaults.
        old = {**ai_stages.pipeline_config(CONFIG), transport.CONFIG_KEY: nodes.TRANSPORT}
        old.pop(policy.CONFIG_KEY)
        new = policy.prospective(old)
        payload = {'notes': 'Unchanged synthetic source.\r\n', 'source_units': [], 'all_fields': ['one', 'two']}
        old_body, old_result, _ = self.sdk(lambda callback: ai_stages._response(
            payload, schema, 'Complete original instructions.', old, 32000, 240, callback))
        body, result, retained = self.sdk(lambda callback: ai_stages._response(
            payload, schema, 'Complete original instructions.', new, 32000, 240, callback))
        self.assertEqual(body.pop('thinking'), {'type': 'between_tools'})
        self.assertEqual(body['output_config'].pop('effort'), 'high')
        self.assertEqual(body, old_body)
        self.assertEqual(body['max_tokens'], 32000)
        self.assertEqual(json.loads(body['messages'][0]['content']), payload)
        self.assertEqual(result[-2:], old_result[-2:])
        self.assertTrue(result[-1]); self.assertEqual(len(retained), 1)
        request = {'schema': schema, 'schema_transport': nodes.TRANSPORT}
        self.assertEqual(transport.response_value(result[-2], request, config=new,
            provider='anthropic', simulated=False), raw)

    def test_thinking_only_max_token_response_remains_incomplete(self):
        self.response_text = '{}'
        config = ai_stages.pipeline_config(CONFIG)
        _, result, retained = self.sdk(lambda callback: ai_stages._response(
            {}, {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False},
            'Original.', config, 32000, 240, callback), thinking_only=True)
        self.assertEqual(result[-2], '')
        self.assertIs(result[-1], False)
        self.assertEqual(result[2]['output_tokens'], 32000)
        self.assertEqual(len(retained), 1)

    def test_durable_stage_envelope_and_reader_bind_exact_new_parameters(self):
        class CapturedBeforeCreate(Exception): pass
        for marked in (False, True):
            config = ai_stages.pipeline_config(CONFIG)
            if not marked: config.pop(policy.CONFIG_KEY)
            job = SimpleNamespace(pk=uuid4(), config=config)
            manager = Mock(); manager.select_for_update.return_value.get.return_value = job
            previous = Mock(); previous.filter.return_value.exists.return_value = False
            previous.exclude.return_value.exists.return_value = False
            previous.count.return_value = 0; previous.__iter__ = lambda self: iter(())
            captured = []
            def retain(envelope):
                captured.append(deepcopy(envelope)); raise CapturedBeforeCreate()
            with patch.object(ai_stages, 'Job', SimpleNamespace(objects=manager)), \
                 patch.object(ai_stages.AIStageReceipt.objects, 'filter', return_value=previous), \
                 patch.object(ai_stages.AIStageReceipt.objects, 'create') as create, \
                 patch.object(ai_stages.transaction, 'atomic', side_effect=lambda: nullcontext()), \
                 patch.object(ai_stages, 'parent_context', return_value=(job, object(), object())), \
                 patch.object(ai_stages, 'assert_installed_guards'), \
                 patch.object(ai_stages, 'retain', side_effect=retain), \
                 patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'offline-only'}), \
                 patch.object(ai_stages, '_response') as send:
                with self.assertRaises(CapturedBeforeCreate):
                    ai_stages.execute_stage(job=job, stage='extractor', payload={'source': 'Exact'},
                        schema={'type': 'string'}, instructions='Exact instructions.', config=config)
                create.assert_not_called(); send.assert_not_called()
            envelope = captured[0]
            self.assertEqual(envelope.get(policy.ENVELOPE_KEY), policy.PARAMETERS if marked else None)
            expected = {k:v for k,v in envelope.items() if k not in (
                'schema_transport', 'transmitted_schema', policy.ENVELOPE_KEY)}
            self.assertTrue(retained_request_matches(envelope, expected, config=config,
                provider='anthropic', simulated=False))
            changed = deepcopy(envelope)
            if marked:
                changed[policy.ENVELOPE_KEY]['thinking']['type'] = 'adaptive'
                self.assertFalse(retained_request_matches(changed, expected, config=config,
                    provider='anthropic', simulated=False))
                changed = deepcopy(envelope); changed.pop(policy.ENVELOPE_KEY)
            else: changed[policy.ENVELOPE_KEY] = deepcopy(policy.PARAMETERS)
            self.assertFalse(retained_request_matches(changed, expected, config=config,
                provider='anthropic', simulated=False))

    def test_legacy_direct_SDK_uses_shared_policy_without_changing_payload_or_validation(self):
        self.response_text = json.dumps({'fields': [{'key': 'symptom', 'quotes': [], 'conflict': False}]})
        fields = [{'key': 'symptom', 'label': 'Symptom'}]
        old = {**CONFIG, 'prompt_version': 'historical'}; new = policy.prospective(old)
        old_body, old_result, _ = self.sdk(lambda callback: generation.generate('Unchanged source.', fields, old))
        body, result, _ = self.sdk(lambda callback: generation.generate('Unchanged source.', fields, new))
        self.assertEqual(body.pop('thinking'), {'type': 'between_tools'})
        self.assertEqual(body['output_config'].pop('effort'), 'high')
        self.assertEqual(body, old_body); self.assertEqual(body['max_tokens'], 6000)
        self.assertEqual(generation.validated(result[0]), generation.validated(old_result[0]))


class SharedPreparationRequestPolicyTests(SimpleTestCase):
    from core.tests.test_preparation_schema_transport import PreparationSchemaTransportTests
    from core.tests.test_preparation_model_reasoning import PreparationModelReasoningTests
    setUp = PreparationSchemaTransportTests.setUp
    canonical = PreparationModelReasoningTests.canonical
    invoke = PreparationModelReasoningTests.invoke
    receipt = PreparationModelReasoningTests.receipt

    def live(self, *, marked=True):
        value = self.PreparationModelReasoningTests.live(self, marked=False)
        if marked: value[policy.CONFIG_KEY] = policy.PROFILE
        return value

    def test_old_word_and_new_shared_profiles_make_identical_complete_envelopes(self):
        proposal = self.canonical()
        shared = self.live(); old_word = self.live(marked=False)
        old_word[preparation.REASONING_KEY] = preparation.REASONING_PROFILE
        for role in ('proposer', 'checker'):
            self.assertEqual(preparation.provider_request(self.inventory, role, shared, proposal),
                preparation.provider_request(self.inventory, role, old_word, proposal))

    def test_shared_profile_actual_streaming_SDK_and_retained_both_roles(self):
        proposal = self.canonical()
        for role in ('proposer', 'checker'):
            result, receipt, expected = self.invoke(role=role, proposal=proposal)
            self.assertEqual(result, expected)
            self.assertEqual(preparation.read_retained_role(receipt, 'live'), expected)

    def test_bad_shared_preparation_profile_refuses_before_client(self):
        for value in (None, False, '', 'unknown'):
            config = {**self.live(), policy.CONFIG_KEY: value}
            with self.subTest(value=value), patch('anthropic.AsyncAnthropic') as SDK:
                with self.assertRaises(preparation.DocumentError):
                    preparation.provider_request(self.inventory, 'proposer', config)
                SDK.assert_not_called()
