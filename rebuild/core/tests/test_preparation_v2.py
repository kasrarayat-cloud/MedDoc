"""Product role protocol and historical evidence compatibility; no live calls."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import tempfile
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

    def test_metadata_display_escapes_untrusted_original_and_shows_uncertainty(self):
        metadata = {'label': '<script>original text</script>', 'data_type': 'number', 'unit': '°C',
                    'choices': [], 'destination': 'a1', 'uncertainty_label': 'Printed constraint verified'}
        html = render_to_string('template_preparation_metadata.html', {'metadata': metadata})
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertIn('Unit: °C', html)
        self.assertIn('Printed constraint verified', html)

