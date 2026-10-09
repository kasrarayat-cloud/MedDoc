"""Product role protocol and historical evidence compatibility; no live calls."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import Mock, patch
from docx import Document
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from documents.preparation import inventory, TYPED_PROTOCOL, validate_role
from core import preparation


class TypedRoleProductTests(SimpleTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / 'original.docx'
        document = Document()
        document.add_paragraph('Temperature: ____ °C')
        document.add_paragraph('Fever: ____ (Yes / No)')
        document.add_paragraph('Patient signature: ____')
        document.save(self.path)
        self.config = {'mode': 'fixture', 'provider': 'anthropic', 'model': 'configured-label',
                       'input_rate': '3', 'output_rate': '15', 'cached_rate': '0.3'}

    def test_both_new_fixture_roles_include_metadata_and_are_clearly_simulated(self):
        value = inventory(self.path, protocol=TYPED_PROTOCOL)
        proposal, proposed_evidence = preparation.provider_role(value, 'proposer', self.config, 1)
        checked, checked_evidence = preparation.provider_role(value, 'checker', self.config, 1, proposal)
        for role, response, evidence in [('proposer', proposal, proposed_evidence), ('checker', checked, checked_evidence)]:
            validate_role(value, response, role)
            self.assertTrue(evidence['simulated'])
            self.assertEqual(evidence['model'], 'synthetic-blank-preparation-' + role)
            self.assertEqual(evidence['cost'], '0')
            self.assertEqual(response['anchors'][0]['metadata']['unit'], '°C')
            self.assertEqual(response['anchors'][1]['metadata']['choices'], ['Yes', 'No'])

    def test_historical_protocol_payload_schema_and_results_are_not_upgraded(self):
        value = inventory(self.path)
        before = deepcopy(value)
        proposal, _ = preparation.provider_role(value, 'proposer', self.config, 1)
        checker, _ = preparation.provider_role(value, 'checker', self.config, 1, proposal)
        self.assertFalse(any('metadata' in row for row in proposal['anchors'] + checker['anchors']))
        self.assertNotIn('metadata', preparation.role_schema('proposer')['properties']['anchors']['items']['properties'])
        self.assertEqual(preparation.role_payload(value, 'checker', proposal),
                         {'original': preparation.model_inventory(before), 'role': 'checker', 'proposal': proposal})
        validate_role(value, proposal, 'proposer')

    def test_short_schema_and_quote_fit_existing_per_role_bound_without_calling_api(self):
        value = inventory(self.path, protocol=TYPED_PROTOCOL)
        max_output, cap = preparation.role_limits(value)
        self.assertEqual((max_output, cap), (2500, Decimal('0.10')))
        proposal, _ = preparation.provider_role(value, 'proposer', self.config, 1)
        live = {**self.config, 'mode': 'live'}
        for role in ['proposer', 'checker']:
            payload = preparation.role_payload(value, role, proposal if role == 'checker' else None)
            self.assertLessEqual(preparation.maximum_cost(payload, live, max_output), cap)
        self.assertIn('metadata', preparation.role_schema('checker', TYPED_PROTOCOL)['properties']['anchors']['items']['required'])

    def test_pinned_sdk_transforms_both_typed_roles_without_weakening_source_checks(self):
        from anthropic import transform_schema
        value = inventory(self.path, protocol=TYPED_PROTOCOL)
        for role in ['proposer', 'checker']:
            schema = preparation.role_schema(role, TYPED_PROTOCOL)
            before = deepcopy(schema)
            # Preserve the actual pre-send counterexample without invoking a
            # client: the pinned SDK cannot transform JSON Schema type arrays.
            broken = deepcopy(schema)
            broken['properties']['anchors']['items']['properties']['metadata']['properties']['unit'] = {
                'type': ['string', 'null'], 'maxLength': 80}
            with self.assertRaises(AssertionError):
                transform_schema(broken)
            wire = transform_schema(schema)
            self.assertEqual(schema, before)
            metadata = wire['properties']['anchors']['items']['properties']['metadata']
            self.assertEqual(metadata['properties']['unit']['anyOf'][1], {'type': 'null'})
            self.assertEqual(metadata['properties']['unit']['anyOf'][0]['type'], 'string')
            # The SDK documents unsupported length limits in the wire schema;
            # local exact source checks remain mandatory after the response.
            self.assertIn('maxLength: 80', metadata['properties']['unit']['anyOf'][0]['description'])
            self.assertFalse(metadata['additionalProperties'])
            self.assertEqual(metadata['required'], before['properties']['anchors']['items']['properties']['metadata']['required'])
            proposal, _ = preparation.provider_role(value, 'proposer', self.config, 1)
            result, _ = preparation.provider_role(value, role, self.config, 1, proposal)
            validate_role(value, result, role)
            for unsupported_unit in [None, '°F', 'x'*81, False]:
                changed = deepcopy(result)
                changed['anchors'][0]['metadata']['unit'] = unsupported_unit
                with self.subTest(role=role, unsupported_unit=unsupported_unit), self.assertRaises(ValueError):
                    validate_role(value, changed, role)

    def test_nullable_unit_schema_matches_independent_bounded_string_contract(self):
        from pydantic import StringConstraints, TypeAdapter, ValidationError
        # Pydantic independently generates the same nullable 80-character
        # string schema; both declarations have the old union's meaning.
        adapter = TypeAdapter(Annotated[str, StringConstraints(max_length=80)] | None)
        for role in ['proposer', 'checker']:
            schema = preparation.role_schema(role, TYPED_PROTOCOL)
            unit = schema['properties']['anchors']['items']['properties']['metadata']['properties']['unit']
            self.assertEqual(unit, adapter.json_schema())
        for valid in [None, '', '°C', 'x'*80, '°'*80]:
            self.assertEqual(adapter.validate_python(valid, strict=True), valid)
        for invalid in ['x'*81, '°'*81, False, 0, 1.2, [], {}]:
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                adapter.validate_python(invalid, strict=True)

    def test_typed_live_branch_reaches_stubbed_transport_for_both_roles(self):
        import json
        value = inventory(self.path, protocol=TYPED_PROTOCOL)
        proposal, _ = preparation.provider_role(value, 'proposer', self.config, 1)
        for role in ['proposer', 'checker']:
            fixture, _ = preparation.provider_role(value, role, self.config, 1, proposal)
            response = SimpleNamespace(model='offline-stub-returned-model', id='offline-response', _request_id='offline-request',
                usage=SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=0, cache_creation_input_tokens=0),
                content=[SimpleNamespace(type='text', text=json.dumps(fixture))],
                model_dump=lambda **kw: {'model': 'offline-stub-returned-model', 'usage': {'input_tokens': 100, 'output_tokens': 20}})
            client = Mock(); client.messages.create.return_value = response
            observed = Mock()
            with patch('anthropic.Anthropic', return_value=client) as constructor:
                raw, evidence = preparation.provider_role(value, role, {**self.config, 'mode': 'live'}, 7, proposal, observed)
            constructor.assert_called_once_with(timeout=7, max_retries=0)
            client.messages.create.assert_called_once()
            arguments = client.messages.create.call_args.kwargs
            self.assertEqual(arguments['model'], self.config['model'])
            wire = arguments['output_config']['format']['schema']
            self.assertEqual(wire['properties']['anchors']['items']['properties']['metadata']['properties']['unit']['anyOf'][1], {'type': 'null'})
            self.assertEqual(json.loads(arguments['messages'][0]['content']), preparation.role_payload(value, role, proposal))
            validate_role(value, json.loads(raw), role)
            observed.assert_called_once()
            self.assertEqual(evidence['model'], 'offline-stub-returned-model')

    def test_metadata_display_escapes_untrusted_original_and_shows_uncertainty(self):
        metadata = {'label': '<script>original text</script>', 'data_type': 'number', 'unit': '°C',
                    'choices': [], 'destination': 'a1', 'uncertainty_label': 'Printed constraint verified'}
        html = render_to_string('template_preparation_metadata.html', {'metadata': metadata})
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('Unit: °C', html)
        self.assertIn('Printed constraint verified', html)

