"""Prospective v3 SDK/retained boundaries and pre-submit technical admission."""
from copy import deepcopy
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from anthropic import Anthropic
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
import httpx

from core import ai_stages, generation_recovery as recovery
from core import clinical_schema_transport as transport
from core import clinical_evidence_transport as evidence, clinical_node_transport as nodes
from core.provider_schema import retained_request_matches
from core.tests.test_clinical_schema_transport import CONFIG, nullable, object_schema


class ClinicalNodeIntegrationTests(SimpleTestCase):
    def test_actual_SDK_preserves_payload_bounds_and_uses_complete_flat_carrier(self):
        from core import source_assertion_graph as graph
        schema = graph.extraction_schema()
        config = ai_stages.pipeline_config(CONFIG)
        self.assertEqual(config[transport.CONFIG_KEY], nodes.TRANSPORT)
        self.assertEqual(ai_stages.generation_limits(config), (32000, 240))
        self.assertEqual(Decimal(config['semantic_maximum_cost']), Decimal('8.15'))
        expected = transport.transmitted_schema(schema, nodes.TRANSPORT)
        payload = {'source': 'Complete unchanged source', 'all_original_obligations': ['one', 'two']}
        sent, retained = [], []
        def handle(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, headers={'request-id': 'req_offline'}, json={
                'id': 'msg_offline', 'type': 'message', 'role': 'assistant', 'model': CONFIG['model'],
                'content': [{'type': 'text', 'text': '{}'}], 'stop_reason': 'end_turn',
                'stop_sequence': None, 'usage': {'input_tokens': 10, 'output_tokens': 1}})
        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            def client(**kwargs):
                self.assertEqual(kwargs, {'timeout': 240, 'max_retries': 0})
                return Anthropic(api_key='offline-only', base_url='https://synthetic.invalid',
                    http_client=http, **kwargs)
            with patch('anthropic.Anthropic', side_effect=client):
                ai_stages._response(payload, schema, 'Original instructions.', config, 32000, 240, retained.append)
        self.assertEqual(len(sent), 1); self.assertEqual(len(retained), 1)
        self.assertEqual(sent[0]['messages'][0]['content'], json.dumps(payload, ensure_ascii=False))
        self.assertEqual(sent[0]['system'], 'Original instructions.' + nodes.INSTRUCTIONS)
        self.assertEqual(sent[0]['output_config']['format']['schema'], expected)
        self.assertEqual(sent[0]['max_tokens'], 32000)
        self.assertEqual(config['semantic_max_calls'], 5)

    def test_all_three_versions_decode_only_their_exact_immutable_envelopes(self):
        schema = object_schema({'value': nullable({'type': 'string'})})
        value = {'value': 'Exact unchanged text'}
        expected = {'stage': 'extractor', 'schema': schema, 'payload': {'source': 'Complete'}}
        for marker, encode in ((transport.TRANSPORT, transport.encode),
                               (evidence.TRANSPORT, evidence.encode), (nodes.TRANSPORT, nodes.encode)):
            config = {**CONFIG, transport.CONFIG_KEY: marker}
            request = {**expected, 'schema_transport': marker}
            if marker != transport.TRANSPORT:
                request['transmitted_schema'] = json.dumps(transport.transmitted_schema(schema, marker),
                    ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            before = deepcopy(request)
            self.assertTrue(retained_request_matches(request, expected,
                config=config, provider='anthropic', simulated=False))
            text = json.dumps(encode(schema, value))
            self.assertEqual(transport.response_value(text, request, config=config,
                provider='anthropic', simulated=False), value)
            self.assertEqual(request, before)
            for wrong in ({**CONFIG, transport.CONFIG_KEY: 'unknown'},
                          {**CONFIG, transport.CONFIG_KEY: nodes.TRANSPORT if marker != nodes.TRANSPORT else evidence.TRANSPORT}):
                with self.assertRaises(ValueError): transport.response_value(text, request,
                    config=wrong, provider='anthropic', simulated=False)
            if marker != transport.TRANSPORT:
                bad = deepcopy(request); bad.pop('transmitted_schema')
                self.assertFalse(retained_request_matches(bad, expected,
                    config=config, provider='anthropic', simulated=False))
                bad = deepcopy(request); bad['transmitted_schema'] += ' '
                self.assertFalse(retained_request_matches(bad, expected,
                    config=config, provider='anthropic', simulated=False))

    def test_v2_dispatch_and_exact_schema_are_retained_after_current_moves_to_v3(self):
        from anthropic import transform_schema
        from core.provider_schema import share_anthropic_schema
        schema = object_schema({'value': nullable({'type': 'string'})})
        config = {**CONFIG, transport.CONFIG_KEY: evidence.TRANSPORT}
        self.assertEqual(transport.EVIDENCE_TRANSPORT, evidence.TRANSPORT)
        self.assertEqual(transport.instructions(config), evidence.INSTRUCTIONS)
        self.assertEqual(transport.transmitted_schema(schema, evidence.TRANSPORT),
            share_anthropic_schema(transform_schema(evidence.wire_schema(schema))))

    @override_settings(RELEASE_SHA='b'*40)
    def test_offer_and_bind_require_three_remaining_roles_before_any_new_work(self):
        config = ai_stages.pipeline_config(CONFIG)
        original = {**config, transport.CONFIG_KEY: evidence.TRANSPORT, 'queued_release_sha': 'a'*40}
        actor = SimpleNamespace(pk=uuid4())
        encounter = SimpleNamespace(pk=uuid4(), status='draft', answers={}, revision=0)
        job = SimpleNamespace(pk=uuid4(), user_id=actor.pk, config=original)
        proof = {'job': str(job.pk), 'stage': str(uuid4()), 'request_sha256': 'a'*64,
            'error_audit': str(uuid4()), 'error_sha256': 'b'*64, 'old_transport': evidence.TRANSPORT,
            'prior_calls': 2, 'prior_quote': '1.022172500000', 'old_config_sha256': recovery._digest(original)}
        queryset = MagicMock(); queryset.order_by.return_value.__getitem__.return_value = [job]
        before = deepcopy(original)
        with patch.object(recovery, 'rejection', return_value=proof) as rejected, \
             patch.object(recovery, '_source_matches', return_value=True), \
             patch.object(recovery, '_lineage', return_value=([job], Decimal('0'), set())), \
             patch.object(recovery, '_children', return_value=[]), \
             patch.object(recovery, 'successor', return_value=None), \
             patch.object(recovery, 'family_ids', return_value={job.pk}), \
             patch.object(recovery.Job.objects, 'filter', return_value=queryset), \
             patch.object(recovery.Job.objects, 'create') as create_job, \
             patch('core.models.Reservation.objects.create') as reserve, \
             patch.object(ai_stages, '_response') as send:
            offered = recovery.offer(encounter, actor, config)
            self.assertIsNotNone(offered)
            value = recovery._proposal(job, encounter, actor, config)
            self.assertEqual(value['prior_calls'], 2)
            self.assertEqual(recovery.bind(job, value, encounter, actor, {**original,
                transport.CONFIG_KEY: nodes.TRANSPORT, 'queued_release_sha': 'b'*40})[recovery.RECOVERY_KEY], value)
            rejected.return_value = {**proof, 'prior_calls': 3}
            self.assertIsNone(recovery.offer(encounter, actor, config))
            with self.assertRaises(ValidationError): recovery.bind(job, value, encounter, actor, config)
            create_job.assert_not_called(); reserve.assert_not_called(); send.assert_not_called()
        self.assertEqual(original, before)
        self.assertEqual(config['semantic_max_calls'], 5)
        self.assertEqual(Decimal(config['semantic_maximum_cost']), Decimal('8.15'))
