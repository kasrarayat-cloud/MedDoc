"""Actual SDK conversion and immutable retained evidence for prospective transport."""
from copy import deepcopy
import json
from unittest.mock import patch

from anthropic import Anthropic
from django.test import SimpleTestCase
import httpx

from core import ai_stages, clinical_schema_transport as transport
from core import clinical_evidence_transport as evidence
from core import source_assertion_graph as graph, source_interpretation_store as store
from core.provider_schema import retained_request_matches
from core.tests.test_clinical_schema_transport import CONFIG


class EvidenceIntegrationTests(SimpleTestCase):
    def test_actual_SDK_schema_matches_retained_conversion_without_network(self):
        schema = graph.extraction_schema()
        config = {**CONFIG, transport.CONFIG_KEY: evidence.TRANSPORT}
        expected = transport.transmitted_schema(schema, evidence.TRANSPORT)
        sent = []
        def handle(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, headers={'request-id': 'req_offline'}, json={
                'id': 'msg_offline', 'type': 'message', 'role': 'assistant', 'model': CONFIG['model'],
                'content': [{'type': 'text', 'text': '{}'}], 'stop_reason': 'end_turn',
                'stop_sequence': None, 'usage': {'input_tokens': 1000, 'output_tokens': 20}})
        with httpx.Client(transport=httpx.MockTransport(handle)) as http:
            def client(**kwargs):
                self.assertEqual(kwargs, {'timeout': 240, 'max_retries': 0})
                return Anthropic(api_key='offline-only', base_url='https://synthetic.invalid', http_client=http, **kwargs)
            retained = []
            with patch('anthropic.Anthropic', side_effect=client):
                ai_stages._response({'source': 'Complete unchanged source'}, schema, 'Original instruction.',
                    config, 32000, 240, retained.append)
        self.assertEqual(len(sent), 1)
        self.assertEqual(len(retained), 1)
        self.assertEqual(sent[0]['output_config']['format']['schema'], expected)
        self.assertEqual(json.dumps(sent[0]['output_config']['format']['schema'],
            ensure_ascii=False, separators=(',', ':'), allow_nan=False),
            json.dumps(expected, ensure_ascii=False, separators=(',', ':'), allow_nan=False))
        self.assertEqual(sent[0]['system'], 'Original instruction.' + evidence.INSTRUCTIONS)
        self.assertEqual(sent[0]['messages'][0]['content'], json.dumps({'source': 'Complete unchanged source'}, ensure_ascii=False))
        self.assertEqual(sent[0]['max_tokens'], 32000)

    def test_full_request_and_exact_transmitted_schema_must_both_match(self):
        expected = {'stage': 'extractor', 'schema': graph.extraction_schema(), 'payload': {'source': 'Complete'}}
        config = {**CONFIG, transport.CONFIG_KEY: evidence.TRANSPORT}
        request = {**expected, 'schema_transport': evidence.TRANSPORT,
            'transmitted_schema': json.dumps(transport.transmitted_schema(expected['schema'], evidence.TRANSPORT),
                ensure_ascii=False, separators=(',', ':'), allow_nan=False)}
        self.assertTrue(retained_request_matches(request, expected, config=config, provider='anthropic', simulated=False))
        for key in ('schema', 'payload', 'transmitted_schema', 'schema_transport'):
            bad = deepcopy(request); bad.pop(key)
            self.assertFalse(retained_request_matches(bad, expected, config=config, provider='anthropic', simulated=False))
        bad = deepcopy(request); transmitted = json.loads(bad['transmitted_schema'])
        transmitted['properties'].pop('evidence'); bad['transmitted_schema'] = json.dumps(transmitted)
        self.assertFalse(retained_request_matches(bad, expected, config=config, provider='anthropic', simulated=False))
        reordered = deepcopy(request)
        reordered['transmitted_schema'] = json.dumps(json.loads(request['transmitted_schema']),
            sort_keys=True, ensure_ascii=False, separators=(',', ':'))
        self.assertNotEqual(reordered['transmitted_schema'], request['transmitted_schema'])
        self.assertFalse(retained_request_matches(reordered, expected, config=config, provider='anthropic', simulated=False))

    def test_invalid_schema_refuses_before_receipt_reservation_or_send(self):
        config = ai_stages.pipeline_config(CONFIG)
        with patch.object(ai_stages, 'parent_context', return_value=(object(), object(), object())), \
                patch.object(ai_stages, 'retain') as retain, patch.object(ai_stages, '_response') as send, \
                patch.object(ai_stages, 'assert_installed_guards') as guards:
            with self.assertRaises(ai_stages.StageNotSent):
                ai_stages.execute_stage(stage='extractor', payload={'source': 'Complete unchanged source'},
                    schema={'type': 'string', 'default': 'invented'}, instructions='Original', config=config)
        retain.assert_not_called(); send.assert_not_called(); guards.assert_not_called()

    def test_complete_three_stage_retained_replay_restores_original_canonical_model(self):
        from core.tests.test_source_interpretation_store import InterpretationStoreTests
        fixture = InterpretationStoreTests('test_exact_three_stage_lineage_round_trip_without_provider')
        fixture.setUp(); self.addCleanup(fixture.doCleanups)
        outputs = [store._output(store._read(r.result_path, r.result_sha256), r) for r in fixture.rows]
        fixture.transport_lineage(marker=evidence.TRANSPORT,
            config_changes={'model': CONFIG['model'], transport.CONFIG_KEY: evidence.TRANSPORT})
        preserved = []
        for row, output in zip(fixture.rows, outputs):
            request = store._read(row.request_path, row.request_sha256)
            # Reconstruct the original request factory's schema ordering, rather
            # than the sorted order of the saved canonical JSON document.
            original_schema = fixture.requests[fixture.rows.index(row)]['schema']
            request['transmitted_schema'] = json.dumps(transport.transmitted_schema(original_schema, evidence.TRANSPORT),
                ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            row.request_path, row.request_sha256 = ai_stages.retain(request)
            wrapper = store._read(row.result_path, row.result_sha256)
            wrapper['provider_output']['content'][0]['text'] = json.dumps(evidence.encode(request['schema'], output))
            row.result_path, row.result_sha256 = ai_stages.retain(wrapper)
            preserved.extend([(row.request_path, row.request_sha256, store.private_path(row.request_path).read_bytes()),
                (row.result_path, row.result_sha256, store.private_path(row.result_path).read_bytes())])
        before = deepcopy(fixture.interpretation)
        self.assertEqual(len(store._retained(fixture.job, fixture.interpretation, fixture.answers)), 3)
        self.assertEqual(fixture.interpretation, before)
        fixture.assert_request_bytes_unchanged(preserved)
