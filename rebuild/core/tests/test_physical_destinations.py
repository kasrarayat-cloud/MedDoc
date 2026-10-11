"""Physical/semantic namespace regressions through both real request builders."""
from copy import deepcopy
import json
from unittest.mock import patch
from types import SimpleNamespace
from django.test import SimpleTestCase
from core import preparation
from core.tests import test_word_answer_contract as fixtures
from documents import DocumentError
from documents.engine import DocumentFailure
from documents.preparation_roles import role_rows, source_role_areas, validate_metadata_row


class PhysicalDestinationRequestTests(SimpleTestCase):
    # Generic two-table fixture; no patient document/provider response in git.
    setUp = fixtures.FreshWordContractTests.setUp
    def prospective(self):
        return {**self.config, preparation.DESTINATION_KEY: preparation.DESTINATION_PROFILE}

    def test_both_role_requests_distinguish_and_enumerate_physical_ids(self):
        for role in ('proposer', 'checker'):
            request = preparation.provider_request(self.inv, role, self.prospective(), {'retained': True})
            payload = json.loads(request['messages'][0]['content'])
            areas = payload['physical_answer_areas']
            self.assertEqual(len(areas), 12)
            props = request['output_config']['format']['schema']['properties']['anchors']['items']['properties']
            self.assertEqual(props['metadata']['properties']['destination']['enum'], [a['id'] for a in self.inv['anchors']])
            for anchor, area, semantic in zip(self.inv['anchors'], areas, payload['answer_definition_inventory']['fields']):
                self.assertEqual(area['allowed_destination_ids'], [anchor['id']])
                self.assertEqual(area['source_metadata']['destination'], anchor['id'])
                self.assertNotEqual(anchor['id'], semantic['permitted_destination']['field_key'])
                self.assertNotIn(semantic['key'], props['metadata']['properties']['destination']['enum'])
            self.assertIn('DIFFERENT namespaces', request['system'])
            self.assertIn('single concern, impression, duration', request['system'])

    def test_real_pinned_sdk_sends_finite_schema_to_mock_transport(self):
        import httpx
        from anthropic import Anthropic
        for role in ('proposer', 'checker'):
            config = {**self.prospective(), 'mode': 'live', 'input_rate':'3', 'output_rate':'15', 'cached_rate':'0.3'}
            output, _ = preparation.provider_role(self.inv, role, self.prospective(), 1)
            sent = []
            def transport(request):
                self.assertEqual(request.url.host, 'synthetic-provider.invalid')
                sent.append(json.loads(request.content))
                return httpx.Response(200, json={'id':'offline-message','type':'message','role':'assistant',
                    'model':'offline-returned','content':[{'type':'text','text':json.dumps(output)}],
                    'stop_reason':'end_turn','stop_sequence':None,'usage':{'input_tokens':100,'output_tokens':100}})
            with httpx.Client(transport=httpx.MockTransport(transport)) as http:
                client = Anthropic(api_key='synthetic-offline-only', http_client=http,
                                   base_url='https://synthetic-provider.invalid', max_retries=0)
                with patch('anthropic.Anthropic', return_value=client):
                    text, evidence = preparation.provider_role(self.inv, role, config, 1)
            self.assertEqual(json.loads(text), output)
            self.assertEqual(evidence['response']['stop_reason'], 'end_turn')
            self.assertEqual(sent[0]['output_config']['format']['schema']['properties']['anchors']['items']
                             ['properties']['metadata']['properties']['destination']['enum'],
                             [anchor['id'] for anchor in self.inv['anchors']])

    def test_absent_profile_keeps_historical_payload_and_schema(self):
        for role in ('proposer', 'checker'):
            old = preparation.provider_request(self.inv, role, self.config)
            payload = json.loads(old['messages'][0]['content'])
            self.assertNotIn('physical_answer_areas', payload)
            self.assertNotIn('DIFFERENT namespaces', old['system'])
            props = old['output_config']['format']['schema']['properties']['anchors']['items']['properties']
            self.assertNotIn('enum', props['metadata']['properties']['destination'])
            self.assertEqual(preparation.provider_request(self.inv, role, deepcopy(self.config)), old)

    def test_unknown_explicit_profile_cannot_build_request_or_downgrade(self):
        for value in (None, '', 'unknown', [], {'version': 1}):
            config = {**self.config, preparation.DESTINATION_KEY: value}
            for builder in (lambda: preparation.role_payload(self.inv, 'proposer', config=config),
                            lambda: preparation.role_schema('checker', self.inv['protocol'], self.inv, config),
                            lambda: preparation.provider_request(self.inv, 'proposer', config)):
                with self.subTest(value=value), self.assertRaises(DocumentError): builder()

    def test_semantic_and_cross_anchor_ids_are_rejected_not_normalized(self):
        for role in ('proposer', 'checker'):
            row = role_rows(self.inv, role)[0]
            for wrong in (self.inv['fields'][0]['key'], self.inv['anchors'][1]['id']):
                changed = deepcopy(row); changed['metadata']['destination'] = wrong
                frozen = deepcopy(changed)
                with self.assertRaises(DocumentFailure) as raised:
                    validate_metadata_row(self.inv, self.inv['anchors'][0], changed)
                self.assertEqual(raised.exception.code, 'invalid_destination')
                self.assertEqual(changed, frozen)
        prep = SimpleNamespace(state='blocked', error_code='invalid_destination')
        self.assertIn('allowed locations', preparation.failure_explanation(prep, []))


class FiniteAreaPolicyTests(SimpleTestCase):
    def test_choice_and_protected_areas_keep_original_policy(self):
        from documents.test_preparation_roles import PreparationMetadataTests
        fixture = PreparationMetadataTests()
        for kind, protected, expected in (('choose_cell', False, ['c1', 'c3']),
                                          ('protected_blank', True, ['a1']),
                                          ('literal_blank', False, ['a1'])):
            inv = fixture.inventory(kind=kind, protected=protected)
            frozen = deepcopy(inv)
            areas = source_role_areas(inv)
            self.assertEqual(areas[0]['allowed_destination_ids'], expected)
            if protected: self.assertEqual(areas[0]['source_metadata']['uncertainty'], 'signing_protected')
            if kind == 'choose_cell':
                self.assertEqual(areas[0]['source_metadata']['uncertainty'], 'placement_requires_review')
                self.assertEqual(role_rows(inv, 'checker')[0]['verdict'], 'unresolved')
            self.assertEqual(inv, frozen)

    def test_failure_diagnostic_retains_only_closed_exception_class(self):
        error = DocumentFailure('secret must never be retained', 'invalid_destination')
        result = preparation.safe_provider_failure(error, 'proposer', 'proposal_validation', 10, True, True, 'end_turn')
        self.assertEqual(result['error_class'], 'DocumentFailure')
        self.assertNotIn('secret', json.dumps(result))
