"""Model-specific execution policy; real SDK requests over offline transports."""
from contextlib import nullcontext
from copy import deepcopy
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core import preparation
from core.tests import test_preparation_compact_deadlines as compact
from core.tests import test_preparation_stream_transport as streams
from core.tests import test_preparation_error_evidence as errors
from core.tests import test_preparation_schema_transport as schemas
from core.security import private_path
from documents.preparation import digest


class PreparationModelReasoningTests(SimpleTestCase):
    setUp = schemas.PreparationSchemaTransportTests.setUp
    receipt = errors.PreparationErrorEvidenceTests.receipt

    def live(self, *, marked=True):
        config = streams.PreparationStreamTransportTests.live(self, choice=True)
        config['model'] = preparation.REASONING_MODEL
        config[preparation.SCHEMA_TRANSPORT_KEY] = preparation.choice_transport.COMPACT_TRANSPORT
        if marked:
            config[preparation.REASONING_KEY] = preparation.REASONING_PROFILE
        return config

    def canonical(self, role='proposer', proposal=None):
        config = self.live(marked=False)
        config['mode'] = 'fixture'
        del config[preparation.stream_transport.CONFIG_KEY]
        del config[preparation.SCHEMA_TRANSPORT_KEY]
        return preparation.provider_role(self.inventory, role, config, 1, proposal)[0]

    def test_policy_changes_only_execution_and_explicit_request_provenance(self):
        proposal = self.canonical()
        for role in ('proposer', 'checker'):
            old_config, new_config = self.live(marked=False), self.live()
            original = deepcopy((self.inventory, old_config, new_config, proposal))
            old = preparation.provider_request(self.inventory, role, old_config, proposal)
            new = preparation.provider_request(self.inventory, role, new_config, proposal)
            self.assertEqual(new.pop('thinking'), {'type': 'between_tools'})
            self.assertEqual(new['output_config'].pop('effort'), 'high')
            payload = json.loads(new['messages'][0]['content'])
            self.assertEqual(payload.pop('provider_reasoning'), preparation.REASONING_PROFILE)
            new['messages'][0]['content'] = json.dumps(payload, ensure_ascii=False, sort_keys=True)
            self.assertEqual(new, old)
            self.assertNotIn('thinking', old)
            self.assertNotIn('effort', old['output_config'])
            self.assertEqual(preparation.role_limits(self.inventory, old_config),
                             preparation.role_limits(self.inventory, new_config))
            self.assertEqual(preparation.timing_limits(self.inventory, old_config),
                             preparation.timing_limits(self.inventory, new_config))
            self.assertNotEqual(digest(preparation.role_payload(self.inventory, role, proposal, config=old_config)),
                                digest(preparation.role_payload(self.inventory, role, proposal, config=new_config)))
            self.assertEqual((self.inventory, old_config, new_config, proposal), original)

    def invoke(self, *, role='proposer', proposal=None, terminal=True):
        config = self.live()
        value = self.canonical(role, proposal)
        wire = compact.PreparationCompactDeadlineTests.wire(value)
        body = streams.Body(streams.events(wire, terminal=terminal))
        sent = []
        client = streams.PreparationStreamTransportTests.sdk_client(self, body, sent)
        receipt = self.receipt()
        packet = SimpleNamespace(inventory=self.inventory, config=config, proposal=proposal)
        receipt.preparation, receipt.role = packet, role
        receipt.request_sha256 = digest(preparation.role_payload(self.inventory, role, proposal, config=config))
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': streams.SECRET}), \
                patch('anthropic.AsyncAnthropic', return_value=client) as factory, \
                patch('core.testing_authority.identity', return_value=True), \
                patch('core.testing_authority.reserve_role', return_value=receipt) as reserve, \
                patch('core.preparation_campaign.provider_slot', return_value=nullcontext()):
            try:
                result = preparation.call_role(packet, role, time.monotonic() + 60, proposal)
            except Exception as error:
                result = error
        self.assertEqual(len(sent), 1)
        self.assertEqual(reserve.call_count, 1)
        self.assertEqual(factory.call_args.kwargs['max_retries'], 0)
        self.assertEqual(sent[0], preparation.provider_request(self.inventory, role, config, proposal))
        self.assertEqual(sent[0]['thinking'], {'type': 'between_tools'})
        self.assertEqual(sent[0]['output_config']['effort'], 'high')
        self.assertNotIn('tools', sent[0])
        self.assertTrue(client.is_closed())
        self.assertTrue(body.closed)
        return result, receipt, value

    def test_real_sdk_both_roles_accept_text_first_and_keep_all_canonical_checks_and_replay(self):
        proposal = self.canonical()
        for role in ('proposer', 'checker'):
            result, receipt, expected = self.invoke(role=role, proposal=proposal)
            self.assertEqual(result, expected)
            self.assertEqual(receipt.state, 'succeeded')
            self.assertIsNotNone(receipt.computed_cost)
            self.assertEqual(preparation.read_retained_role(receipt, 'live'), expected)

    def test_replay_cannot_erase_the_policy_binding_or_forge_a_different_envelope(self):
        _, receipt, _ = self.invoke()
        original_config = deepcopy(receipt.preparation.config)
        del receipt.preparation.config[preparation.REASONING_KEY]
        with self.assertRaises(preparation.DocumentError):
            preparation.read_retained_role(receipt, 'live')
        receipt.preparation.config = original_config
        evidence = json.loads(private_path(receipt.response_path).read_bytes())
        evidence['request_envelope']['thinking'] = {'type': 'adaptive'}
        evidence['request_envelope_sha256'] = digest(evidence['request_envelope'])
        with self.assertRaises(preparation.DocumentError):
            preparation.decode_role_response(self.inventory, 'proposer', original_config,
                self.canonical(), None, evidence, receipt.request_sha256)

    def test_missing_terminal_still_retains_unknown_usage_and_never_retries(self):
        result, receipt, _ = self.invoke(terminal=False)
        self.assertIsInstance(result, Exception)
        self.assertEqual(receipt.state, 'unknown')
        self.assertIsNone(receipt.computed_cost)
        self.assertFalse(receipt.usage)
        self.assertEqual(receipt.failure['local_transport_reason'], 'unexpected_eof')

    def test_unknown_or_incompatible_policy_fails_before_any_reservation_or_sdk_client(self):
        configs = [{**self.live(), preparation.REASONING_KEY: item}
                   for item in (None, False, True, 0, '', 'future-policy')]
        configs += [{**self.live(), key: value} for key, value in
                    (('model', 'claude-opus-5-5'), ('model', 'claude-sonnet-5'),
                     ('model', 'claude-sonnet-5-5-future'), ('mode', 'fixture'), ('provider', 'openai'))]
        for config in configs:
            with self.subTest(config=config), patch('anthropic.AsyncAnthropic') as client, \
                    patch('core.testing_authority.reserve_role') as reserve, \
                    patch('core.preparation_campaign.reserve_campaign_role') as campaign, \
                    patch.object(preparation.PreparationReceipt.objects, 'create') as legacy:
                packet = SimpleNamespace(inventory=self.inventory, config=config)
                with self.assertRaises(preparation.DocumentError):
                    preparation.call_role(packet, 'proposer', time.monotonic() + 60)
                client.assert_not_called()
                reserve.assert_not_called()
                campaign.assert_not_called()
                legacy.assert_not_called()

    def test_queue_marks_only_new_compatible_live_preparations_without_changing_configuration(self):
        for model in (preparation.REASONING_MODEL, 'claude-sonnet-5', 'claude-opus-5-5'):
            for mode, provider in (('live', 'anthropic'), ('fixture', 'anthropic'), ('live', 'openai')):
                config = {**self.config, 'model': model, 'mode': mode, 'provider': provider}
                original = deepcopy(config)
                with self.subTest(model=model, mode=mode, provider=provider), \
                        patch.object(preparation, 'configuration', return_value=config), \
                        patch('core.preparation_campaign.active_campaign_config', side_effect=lambda value, _: value), \
                        patch('core.testing_authority.identity', return_value=True), \
                        patch('core.testing_authority.create_preparation') as create:
                    preparation.create_preparation(SimpleNamespace(sha256='a' * 64), SimpleNamespace())
                    queued = create.call_args.args[2]
                    if (model, mode, provider) == (preparation.REASONING_MODEL, 'live', 'anthropic'):
                        self.assertEqual(queued[preparation.REASONING_KEY], preparation.REASONING_PROFILE)
                    else:
                        self.assertNotIn(preparation.REASONING_KEY, queued)
                self.assertEqual(config, original)

    def test_queue_cannot_overwrite_an_unknown_explicit_policy(self):
        config = {**self.live(), preparation.REASONING_KEY: 'future-policy'}
        with patch.object(preparation, 'configuration', return_value=config), \
                patch('core.preparation_campaign.active_campaign_config', side_effect=lambda value, _: value), \
                patch('core.testing_authority.create_preparation') as create:
            with self.assertRaises(preparation.DocumentError):
                preparation.create_preparation(SimpleNamespace(sha256='a' * 64), SimpleNamespace())
            create.assert_not_called()
