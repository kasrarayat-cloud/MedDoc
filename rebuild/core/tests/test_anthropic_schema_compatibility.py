"""Inspect the actual SDK HTTP body without any network or provider operation."""
import json
from unittest.mock import patch

import httpx
from anthropic import Anthropic
from django.test import SimpleTestCase
from pydantic import ValidationError

from core import generation as g, mapping_assistance, wm_narrative


def unsupported(schema, path='$'):
    found = []
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in {'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum',
                       'multipleOf', 'minLength', 'maxLength', 'maxItems'}:
                found.append(path + '.' + key)
            if key == 'minItems' and value not in (0, 1):
                found.append(path + '.' + key)
            found.extend(unsupported(value, path + '.' + key))
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            found.extend(unsupported(value, f'{path}[{index}]'))
    return found


class NativeSchemaCompatibility(SimpleTestCase):
    def wire(self, model, schema):
        profile = {'max_output_tokens': 8000, 'thinking': {'type': 'disabled'}, 'effort': 'medium'}
        body = g.anthropic_request(model, profile, 'Synthetic schema check.', {}, schema)
        observed = []

        def receive(request):
            observed.append(json.loads(request.content))
            return httpx.Response(200, json={'id': 'msg_synthetic', 'type': 'message',
                'role': 'assistant', 'model': model, 'content': [{'type': 'text', 'text': '{}'}],
                'stop_reason': 'end_turn', 'stop_sequence': None,
                'usage': {'input_tokens': 1, 'output_tokens': 1}})

        with patch('socket.socket', side_effect=AssertionError('Network forbidden')):
            with httpx.Client(transport=httpx.MockTransport(receive)) as transport:
                with Anthropic(api_key='synthetic-schema-only', http_client=transport, max_retries=0) as client:
                    client.messages.create(**body)
        self.assertEqual(len(observed), 1)
        return observed[0]['output_config']['format']['schema']

    def test_selected_model_schema_survives_actual_sdk_without_unsupported_constraints(self):
        schemas = [g.UnitSelections, wm_narrative.NarrativeSelections, mapping_assistance.Proposal]
        if hasattr(mapping_assistance, 'wire'):
            schemas.append(mapping_assistance.wire.Proposal)
        for schema in schemas:
            with self.subTest(schema=schema.__module__ + '.' + schema.__name__):
                self.assertEqual(unsupported(self.wire(g.SONNET_5, schema)), [])

    def test_the_per_request_ordinary_schema_reaches_the_sdk_body_unchanged(self):
        # (the v4 relations answer: a plain dictionary built per request; enums, references, required members and closed
        # objects only - no length bound, which the parser proves instead)
        from core import v3_field_relations as r
        from .test_v3_ordinary_notes import field
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No']), field('other', 'Other:')]
        for count in (1, 2, 40, 80):
            with self.subTest(units=count):
                schema = r.response_schema(fields, [{'id': i} for i in range(1, count + 1)])
                sent = self.wire(g.SONNET_5, schema)
                self.assertEqual(sent, schema)
                self.assertEqual(unsupported(sent), [])
                self.assertNotIn('description', json.dumps(sent))

    def test_prior_model_request_schema_remains_exact(self):
        self.assertEqual(self.wire('claude-sonnet-4-6', mapping_assistance.Proposal),
                         mapping_assistance.Proposal.model_json_schema())

    def test_local_strict_mapping_validation_still_rejects_constraints(self):
        for key, value in (('label', ''), ('label', 'x' * 1001), ('label', '\U0001f9ea' * 1001),
                           ('glyph', -1), ('glyph', True)):
            with self.subTest(key=key, value=value), self.assertRaises(ValidationError):
                mapping_assistance.Target.model_validate({'slot': 'b/p[0]', 'kind': 'text',
                    'label': 'History', 'options': [], 'glyph': None, key: value})

    def test_local_mapping_label_boundary_preserves_complete_unicode_source(self):
        for character in ('x', '\U0001f9ea'):
            for length in (301, 1000):
                label = character * length
                with self.subTest(character=character, length=length):
                    target = mapping_assistance.Target.model_validate({'slot': 'b/p[0]', 'kind': 'text',
                        'label': label, 'options': [], 'glyph': None})
                    self.assertEqual(target.label, label)
