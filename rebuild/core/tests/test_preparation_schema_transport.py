"""Prospective lossless preparation transport; no provider or database calls."""
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

from anthropic import transform_schema
from django.test import SimpleTestCase, override_settings
from docx import Document

from core import preparation, word_contract
from core.provider_schema import ANTHROPIC_SCHEMA_TRANSPORT
from core.tests import test_preparation_output
from core.tests.test_provider_schema import expand, count
from documents.component_contracts import CONFIG_KEY, ENCOUNTER_CONTRACT
from documents.preparation import TYPED_PROTOCOL, digest, inventory
from documents.semantic_preparation_roles import MEANING_CONTRACT_KEY, COMPOUND_ANSWER_CONTRACT


class PreparationSchemaTransportTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        settings = override_settings(MEDIA_ROOT=self.root, WORD_PREPARATION_ENABLED=True,
                                     RELEASE_SHA='synthetic-schema-test')
        settings.enable()
        self.addCleanup(settings.disable)
        document = Document()
        table = document.add_table(rows=4, cols=2)
        for row, label in zip(table.rows, (
                'Documented name', 'Measured temperature',
                'Objective findings, excluding assessment', 'Follow-up plan')):
            row.cells[0].text = label
        self.path = self.root / 'blank.docx'
        document.save(self.path)
        self.inventory = inventory(self.path, protocol=TYPED_PROTOCOL)
        self.config = {
            'mode': 'fixture', 'provider': 'anthropic', 'model': 'offline-configured-label',
            'input_rate': '2', 'output_rate': '10', 'cached_rate': '0.2',
            'word_preparation_output_profile': preparation.COMPLETE_OUTPUT_PROFILE,
            preparation.DESTINATION_KEY: preparation.DESTINATION_PROFILE,
            preparation.IDENTITY_KEY: preparation.IDENTITY_PROFILE,
            word_contract.CONFIG_KEY: word_contract.GRAPH_PROFILE,
            'semantic_definition_version': 4, CONFIG_KEY: ENCOUNTER_CONTRACT,
            MEANING_CONTRACT_KEY: COMPOUND_ANSWER_CONTRACT,
        }

    def live(self, *, marked=True):
        config = {**self.config, 'mode': 'live'}
        if marked:
            config[preparation.SCHEMA_TRANSPORT_KEY] = ANTHROPIC_SCHEMA_TRANSPORT
        return config

    def response(self, role='proposer', proposal=None):
        return preparation.provider_role(self.inventory, role, self.config, 1, proposal)[0]

    def test_both_roles_share_only_the_wire_schema_and_expand_to_exact_original(self):
        proposal = self.response()
        before = deepcopy((self.inventory, self.config, proposal))
        for role in ('proposer', 'checker'):
            original = preparation.provider_request(self.inventory, role, self.live(marked=False), proposal)
            shared = preparation.provider_request(self.inventory, role, self.live(), proposal)
            original_schema = original['output_config']['format']['schema']
            shared_schema = shared['output_config']['format']['schema']
            self.assertIn('$defs', shared_schema)
            self.assertLess(count(shared_schema, 'anyOf'), count(original_schema, 'anyOf'))
            self.assertEqual(json.dumps(expand(shared_schema)), json.dumps(original_schema))
            self.assertEqual(transform_schema(shared_schema), shared_schema)
            self.assertEqual(
                {key: value for key, value in original.items() if key != 'output_config'},
                {key: value for key, value in shared.items() if key != 'output_config'})
            self.assertEqual(shared['max_tokens'], original['max_tokens'])
            self.assertEqual(preparation.role_limits(self.inventory, self.live()),
                             preparation.role_limits(self.inventory, self.live(marked=False)))
        self.assertEqual((self.inventory, self.config, proposal), before)

    def test_payload_and_receipt_digest_remain_exact_with_or_without_transport(self):
        proposal = self.response()
        for role in ('proposer', 'checker'):
            old = preparation.role_payload(self.inventory, role, proposal, config=self.live(marked=False))
            current = preparation.role_payload(self.inventory, role, proposal, config=self.live())
            self.assertEqual(json.dumps(current), json.dumps(old))
            self.assertEqual(digest(current), digest(old))
            self.assertNotIn(preparation.SCHEMA_TRANSPORT_KEY, current)

    def test_absence_never_calls_sharing_for_historical_profiles(self):
        proposal = self.response()
        for config in (self.config, self.live(marked=False)):
            for role in ('proposer', 'checker'):
                with patch.object(preparation, 'share_anthropic_schema',
                                  side_effect=AssertionError('historical wire changed')):
                    request = preparation.provider_request(self.inventory, role, config, proposal)
                expected = transform_schema(preparation.role_schema(
                    role, self.inventory['protocol'], self.inventory, config))
                self.assertEqual(json.dumps(request['output_config']['format']['schema']),
                                 json.dumps(expected))

    def test_unknown_or_incompatible_marker_refuses_before_any_reservation_or_client(self):
        configs = [{**self.live(), preparation.SCHEMA_TRANSPORT_KEY: value}
                   for value in (None, False, True, 0, '', 'future-transport')]
        configs += [{**self.live(), 'mode': 'fixture'},
                    {**self.live(), 'provider': 'openai'}]
        for config in configs:
            with self.subTest(config=config), patch('anthropic.Anthropic') as client, \
                    patch('core.testing_authority.reserve_role') as reserve, \
                    patch('core.preparation_campaign.reserve_campaign_role') as campaign, \
                    patch.object(preparation.PreparationReceipt.objects, 'create') as legacy:
                packet = SimpleNamespace(inventory=self.inventory, config=config)
                with self.assertRaises(preparation.DocumentError):
                    preparation.call_role(packet, 'proposer', 999999999)
                with self.assertRaises(preparation.DocumentError):
                    preparation.provider_request(self.inventory, 'proposer', config)
                client.assert_not_called()
                reserve.assert_not_called()
                campaign.assert_not_called()
                legacy.assert_not_called()

    def test_new_queue_marks_only_live_anthropic_without_mutating_existing_configuration(self):
        template = SimpleNamespace(sha256='a' * 64)
        for mode, provider in (('live', 'anthropic'), ('fixture', 'anthropic'),
                               ('live', 'openai'), ('fixture', 'openai')):
            config = {**self.config, 'mode': mode, 'provider': provider}
            original = deepcopy(config)
            with self.subTest(mode=mode, provider=provider), \
                    patch.object(preparation, 'configuration', return_value=config), \
                    patch('core.preparation_campaign.active_campaign_config', side_effect=lambda value, _: value), \
                    patch('core.testing_authority.identity', return_value=True), \
                    patch('core.testing_authority.create_preparation') as create:
                preparation.create_preparation(template, SimpleNamespace(pk='synthetic-actor'))
                queued = create.call_args.args[2]
                if (mode, provider) == ('live', 'anthropic'):
                    self.assertEqual(queued[preparation.SCHEMA_TRANSPORT_KEY], preparation.choice_transport.COMPACT_TRANSPORT)
                else:
                    self.assertNotIn(preparation.SCHEMA_TRANSPORT_KEY, queued)
            self.assertEqual(config, original)

    def test_queue_cannot_overwrite_an_unknown_explicit_transport(self):
        config = {**self.live(), preparation.SCHEMA_TRANSPORT_KEY: 'future-transport'}
        with patch.object(preparation, 'configuration', return_value=config), \
                patch('core.preparation_campaign.active_campaign_config', side_effect=lambda value, _: value), \
                patch('core.testing_authority.create_preparation') as create:
            with self.assertRaises(preparation.DocumentError):
                preparation.create_preparation(SimpleNamespace(sha256='a' * 64), SimpleNamespace())
            create.assert_not_called()

    def test_real_sdk_transport_retains_shared_envelope_and_original_validated_results(self):
        import httpx
        from anthropic import Anthropic

        proposal = self.response()
        for role in ('proposer', 'checker'):
            value = self.response(role, proposal)
            config = self.live()
            packet = SimpleNamespace(inventory=self.inventory, config=config)
            receipt = test_preparation_output.PreparationOutputTests.receipt(self)
            sent = []

            def handle(request):
                self.assertEqual(request.url.host, 'synthetic-provider.invalid')
                sent.append(json.loads(request.content))
                return httpx.Response(200, headers={'request-id': 'offline-request'}, json={
                    'id': 'offline-result', 'type': 'message', 'role': 'assistant',
                    'model': 'offline-returned-model', 'stop_reason': 'end_turn', 'stop_sequence': None,
                    'content': [{'type': 'text', 'text': json.dumps(value)}],
                    'usage': {'input_tokens': 10, 'output_tokens': 10}})

            with httpx.Client(transport=httpx.MockTransport(handle)) as http:
                client = Anthropic(api_key='synthetic-offline-only', base_url='https://synthetic-provider.invalid',
                                   http_client=http, max_retries=0, timeout=60)
                with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
                        patch('anthropic.Anthropic', return_value=client), \
                        patch('core.testing_authority.identity', return_value=True), \
                        patch('core.testing_authority.reserve_role', return_value=receipt) as reserve, \
                        patch('core.preparation_campaign.provider_slot', return_value=nullcontext()), \
                        patch.object(preparation.time, 'monotonic', return_value=100):
                    actual = preparation.call_role(packet, role, 280, proposal)
            self.assertEqual(actual, value)
            self.assertEqual(receipt.state, 'succeeded')
            self.assertEqual(len(sent), 1)
            self.assertIn('$defs', sent[0]['output_config']['format']['schema'])
            payload = preparation.role_payload(self.inventory, role, proposal, config=config)
            self.assertEqual(reserve.call_args.args[2], digest(payload))
            self.assertEqual(reserve.call_args.args[3], preparation.maximum_cost(
                sent[0], config, preparation.role_limits(self.inventory, config)[0]))
            self.assertEqual(preparation.read_retained_role(receipt, 'live'), value)
            raw = (self.root / receipt.response_path).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt.response_sha256)
            evidence = json.loads(raw)
            self.assertEqual(evidence['request_envelope'], sent[0])
            word_contract.validate_result(self.inventory, actual, role, config)
