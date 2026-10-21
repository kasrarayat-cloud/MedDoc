"""Prospective role allocation; existing total admission and spending controls."""
from contextlib import nullcontext
from copy import deepcopy
import json
import os
import time
from types import SimpleNamespace
from unittest.mock import patch

from docx import Document
from django.test import SimpleTestCase

from core import preparation, preparation_choice_transport as codec, preparation_stream_transport as stream
from core.tests import test_preparation_schema_transport as legacy
from core.tests import test_preparation_stream_transport as sdk_tests
from core.tests import test_preparation_error_evidence as error_tests
from documents.component_contracts import CONFIG_KEY, CHOICE_CONTRACT
from documents.preparation import TYPED_PROTOCOL, digest, inventory


class PreparationCompactDeadlineTests(SimpleTestCase):
    setUp = legacy.PreparationSchemaTransportTests.setUp

    def live(self, marker=None):
        config = {**self.config, 'mode': 'live', 'word_preparation_protocol': TYPED_PROTOCOL,
                  CONFIG_KEY: CHOICE_CONTRACT, stream.CONFIG_KEY: stream.TRANSPORT}
        if marker is not None:
            config[preparation.SCHEMA_TRANSPORT_KEY] = marker
        return config

    def large_inventory(self):
        doc = Document()
        table = doc.add_table(rows=20, cols=2)
        for number, row in enumerate(table.rows):
            row.cells[0].text = f'Documented symptom history for section {number + 1}'
        path = self.root / 'twenty-questions.docx'
        doc.save(path)
        return inventory(path, protocol=TYPED_PROTOCOL)

    def canonical(self, config):
        config = {**config, 'mode': 'fixture'}
        config.pop(preparation.SCHEMA_TRANSPORT_KEY, None)
        config.pop(stream.CONFIG_KEY, None)
        return preparation.provider_role(self.inventory, 'proposer', config, 1)[0]

    @staticmethod
    def wire(value):
        value = deepcopy(value)
        columns = ('id', 'question_quote', 'label', 'meaning', 'value_type', 'scope',
                   'unit', 'unit_requirement', 'required', 'encounter_scope', 'choices', 'option_quote')
        for field in value['answer_definitions']['fields']:
            contract = field['definition']['component_contract']
            rows = []
            for component in contract['components']:
                row = [component[key] for key in columns]
                row[5] = [component['scope'][key] for key in ('subject', 'temporality', 'polarity')]
                rows.append(row)
            contract['components'] = json.dumps(rows, ensure_ascii=False, separators=(',', ':'))
        return value

    def test_only_new_large_compact_profile_uses_two_hundred_with_existing_overall_window(self):
        large = self.large_inventory()
        original = deepcopy(large)
        old = self.live(codec.TRANSPORT)
        compact = self.live(codec.COMPACT_TRANSPORT)
        self.assertGreater(preparation.role_limits(large, compact)[0], preparation.MAX_TYPED_OUTPUT)
        self.assertEqual(preparation.timing_limits(large, compact), (200, 480))
        self.assertEqual(preparation.timing_limits(large, old), (180, 480))
        for marker in (None, codec.ARRAY_TRANSPORT, codec.QUOTE_TRANSPORT):
            self.assertEqual(preparation.timing_limits(large, self.live(marker)), (180, 480))
        self.assertEqual(preparation.role_limits(large, compact), preparation.role_limits(large, old))
        self.assertEqual(large, original)
        # The retained candidate admission guard needs60s; allow20s local work.
        self.assertEqual(480 - 2 * 200, 60 + 20)

    def test_smaller_complete_and_unmarked_profiles_keep_existing_allocation(self):
        old = self.live(codec.TRANSPORT)
        compact = self.live(codec.COMPACT_TRANSPORT)
        self.assertLessEqual(preparation.role_limits(self.inventory, compact)[0], preparation.MAX_TYPED_OUTPUT)
        self.assertEqual(preparation.timing_limits(self.inventory, compact), (120, 360))
        self.assertEqual(preparation.timing_limits(self.inventory, compact), preparation.timing_limits(self.inventory, old))
        self.assertEqual(preparation.timing_limits(self.inventory), (60, 180))

    def exercise(self, *, overall_remaining, terminal=True):
        self.inventory = self.large_inventory()
        config = self.live(codec.COMPACT_TRANSPORT)
        value = self.canonical(config)
        body = sdk_tests.Body(sdk_tests.events(self.wire(value), terminal=terminal), endless=not terminal)
        receipt = error_tests.PreparationErrorEvidenceTests.receipt(self)
        receipt.request_sha256 = digest(preparation.role_payload(self.inventory, 'proposer', config=config))
        packet = SimpleNamespace(inventory=self.inventory, config=config, proposal=None)
        receipt.preparation = packet
        receipt.role = 'proposer'
        sent = []
        client = sdk_tests.PreparationStreamTransportTests.sdk_client(self, body, sent)
        timeouts = []
        original_stream = client.messages.stream
        def observe_timeout(**kwargs):
            timeouts.append(kwargs['timeout'])
            return original_stream(**kwargs)
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': sdk_tests.SECRET}), \
                patch('anthropic.AsyncAnthropic', return_value=client) as factory, \
                patch('core.testing_authority.identity', return_value=True), \
                patch('core.testing_authority.reserve_role', return_value=receipt) as reserve, \
                patch('core.preparation_campaign.provider_slot', return_value=nullcontext()), \
                patch.object(client.messages, 'stream', side_effect=observe_timeout):
            began = time.monotonic()
            try:
                result = preparation.call_role(packet, 'proposer', began + overall_remaining)
            except BaseException as error:
                result = error
            elapsed = time.monotonic() - began
        self.assertEqual(factory.call_args.kwargs, {'timeout': 200, 'max_retries': 0})
        self.assertEqual(reserve.call_count, 1)
        self.assertEqual(len(sent), 1)
        self.assertTrue(client.is_closed())
        self.assertTrue(body.closed)
        self.assertEqual(sent[0]['max_tokens'], preparation.role_limits(self.inventory, config)[0])
        self.assertTrue(sent[0]['stream'])
        self.assertEqual(json.loads(sent[0]['messages'][0]['content'])['response_transport'], codec.COMPACT_TRANSPORT)
        self.assertEqual(len(timeouts), 1)
        return result, receipt, elapsed, timeouts[0], value

    def test_real_sdk_role_is_capped_by_two_hundred_not_total_remaining(self):
        result, receipt, _, timeout, value = self.exercise(overall_remaining=400)
        self.assertEqual(result, value)
        self.assertEqual(receipt.state, 'succeeded')
        self.assertIsNotNone(receipt.computed_cost)
        self.assertGreater(timeout, 199)
        self.assertLessEqual(timeout, 200)

    def test_real_sdk_shorter_overall_deadline_wins_and_unknown_is_never_retried(self):
        result, receipt, elapsed, timeout, _ = self.exercise(overall_remaining=5, terminal=False)
        self.assertIsInstance(result, Exception)
        self.assertEqual(receipt.state, 'unknown')
        self.assertIsNone(receipt.computed_cost)
        self.assertFalse(receipt.usage)
        self.assertEqual(receipt.failure['local_transport_reason'], 'deadline')
        self.assertGreater(timeout, 0)
        self.assertLessEqual(timeout, 5)
        self.assertLess(elapsed, 8)
