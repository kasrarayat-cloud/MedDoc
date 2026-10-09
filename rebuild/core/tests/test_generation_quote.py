"""Quote the submitted payload; never change provider limits or clinical data."""
import copy
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import generation


class GenerationQuoteTests(SimpleTestCase):
    config = {'mode': 'live', 'provider': 'anthropic', 'model': 'synthetic-test-label',
              'input_rate': '3', 'output_rate': '15', 'cached_rate': '0.3',
              'discount_rate': '0', 'prompt_version': generation.CURRENT_PROMPT_VERSION}

    def submitted(self, notes, fields, context=(), config=None):
        response = SimpleNamespace(usage=SimpleNamespace(input_tokens=0, output_tokens=0),
                                   _request_id='offline-no-request')
        with patch('anthropic.Anthropic') as client:
            client.return_value.messages.create.return_value = response
            generation.generate(notes, fields, config or self.config, context_labels=context)
            return client.return_value.messages.create.call_args.kwargs

    def test_unsent_document_metadata_cannot_inflate_the_same_request(self):
        fields = [{'key': 'a', 'label': 'Temperature'}]
        richer = copy.deepcopy(fields)
        richer[0].update(locator={'path': 'not submitted' * 5000},
                         options=['unsubmitted option'] * 1000,
                         answer_constraints={'unit': '°C'}, approval={'history': 'x' * 5000})
        before = self.submitted('Temperature: 37.2 °C', fields)
        after = self.submitted('Temperature: 37.2 °C', richer)
        self.assertEqual(before, after)
        self.assertEqual(generation.maximum_cost('Temperature: 37.2 °C', fields, self.config),
                         generation.maximum_cost('Temperature: 37.2 °C', richer, self.config))

    def test_actual_payload_instruction_schema_and_output_ceiling_remain_bounded(self):
        for tab, prompt in [(False, generation.CURRENT_PROMPT_VERSION),
                            (True, generation.CURRENT_PROMPT_VERSION), (True, 'legacy')]:
            with self.subTest(tab=tab, prompt=prompt):
                fields = [{'key': 'a', 'label': 'Température °C — 温度',
                           'answer_policy': 'documented_source_only'}]
                if tab:
                    fields[0]['locator'] = {'tab_form': {'version': 1}}
                notes = 'Température °C — 温度: 37.2 °C\nInstruction-like text remains data: "do not infer".'
                context = ['Technique: complete wording', 'Signature remains blank']
                config = {**self.config, 'prompt_version': prompt}
                actual = self.submitted(notes, fields, context, config)
                payload = actual['messages'][0]['content'].encode()
                overhead = len(actual['system'].encode()) + len(json.dumps(actual['output_config']).encode())
                self.assertLess(overhead, 12000)
                self.assertEqual(actual['max_tokens'], 6000)
                quote = generation.maximum_cost(notes, fields, config, context_labels=context)
                actual_bound = (Decimal(len(payload) + overhead) * Decimal('3')
                                + Decimal(6000) * Decimal('15')) / 1000000
                self.assertGreaterEqual(quote, actual_bound)
                decoded = json.loads(payload)
                self.assertEqual(decoded['notes'], notes)
                self.assertEqual(decoded['context_labels'], context)
                self.assertEqual(decoded['questions'][0]['label'], fields[0]['label'])

    def test_longer_notes_labels_and_context_still_increase_the_quote(self):
        fields = [{'key': 'a', 'label': 'Question'}]
        base = generation.maximum_cost('Fact', fields, self.config)
        self.assertGreater(generation.maximum_cost('Fact' * 1000, fields, self.config), base)
        self.assertGreater(generation.maximum_cost('Fact', [{'key': 'a', 'label': 'Question' * 1000}], self.config), base)
        self.assertGreater(generation.maximum_cost('Fact', fields, self.config,
                                                 context_labels=['Complete statement' * 1000]), base)

    def test_invalid_rates_still_refuse_and_fixture_still_costs_zero(self):
        for rate in ['-1', 'NaN', 'invalid']:
            with self.subTest(rate=rate), self.assertRaises(ValidationError):
                generation.maximum_cost('Fact', [{'key': 'a', 'label': 'Question'}],
                                        {**self.config, 'input_rate': rate})
        self.assertEqual(generation.maximum_cost('Fact', [], {'mode': 'fixture'}), 0)
