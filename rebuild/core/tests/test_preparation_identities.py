"""Provider schemas constrain source identities; local association checks remain authoritative."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from core import preparation, word_contract
from documents.engine import DocumentFailure
from documents.preparation import model_inventory, PROTOCOL
from documents.semantic_preparation_roles import DefinitionError
from . import test_complete_preparation as complete


class PreparationIdentityTests(SimpleTestCase):
    receipt = complete.CompletePreparationTests.receipt
    complete_output = complete.CompletePreparationTests.complete_output
    exercise_transport = complete.CompletePreparationTests.exercise_transport

    def setUp(self):
        complete.CompletePreparationTests.setUp(self)
        self.historical = deepcopy(self.config)
        self.config[preparation.IDENTITY_KEY] = preparation.IDENTITY_PROFILE

    def test_actual_sdk_wire_enumerates_original_identities_for_both_roles(self):
        fields = self.inventory['fields']
        hashes = [hashlib.sha256(json.dumps(field['locator'], sort_keys=True,
                    separators=(',', ':'), ensure_ascii=False).encode()).hexdigest() for field in fields]
        before = deepcopy(self.inventory)
        for role in ('proposer', 'checker'):
            response = self.complete_output(role)
            result, receipt, retained, sent, _ = self.exercise_transport(json.dumps(response), role=role)
            self.assertEqual(result, response)
            self.assertEqual(receipt.state, 'succeeded')
            self.assertEqual(len(sent), 1)
            self.assertEqual(retained[0]['response']['content'][0]['text'], json.dumps(response))
            request = sent[0]
            payload = json.loads(request['messages'][0]['content'])
            self.assertEqual(payload['source_identity_contract'], preparation.IDENTITY_PROFILE)
            schema = request['output_config']['format']['schema']['properties']
            self.assertEqual(schema['inventory_sha256']['enum'], [self.inventory['inventory_sha256']])
            definitions = schema['answer_definitions']['properties']
            self.assertEqual(definitions['inventory_sha256']['enum'],
                             [payload['answer_definition_inventory']['inventory_sha256']])
            row = definitions['fields']['items']['properties']
            self.assertEqual(row['field_key']['enum'], [f['key'] for f in fields])
            destination = row['definition']['properties']['permitted_destination']['properties']
            self.assertEqual(destination['field_key'], row['field_key'])
            self.assertEqual(destination['locator_sha256']['enum'], hashes)
            story = schema['stories']['items']['properties']
            source_stories = model_inventory(self.inventory)['stories']
            self.assertEqual(story['story_id']['enum'], [s['id'] for s in source_stories])
            self.assertEqual(story['content_sha256']['enum'],
                             list(dict.fromkeys(s['content_sha256'] for s in source_stories)))
            self.assertLess(len(json.dumps(request, ensure_ascii=False).encode()), 512000)
            self.assertEqual(request['max_tokens'], preparation.role_limits(self.inventory, self.historical)[0])
        self.assertEqual(self.inventory, before)

    def test_corrupt_digest_is_not_offered_and_known_but_wrong_associations_still_refuse(self):
        good = self.complete_output()
        schema = preparation.provider_request(self.inventory, 'proposer', self.config)['output_config']['format']['schema']
        destinations = schema['properties']['answer_definitions']['properties']['fields']['items']['properties']['definition']['properties']['permitted_destination']['properties']['locator_sha256']['enum']
        rows = good['answer_definitions']['fields']
        original = rows[26]['definition']['permitted_destination']['locator_sha256']
        other = rows[6]['definition']['permitted_destination']['locator_sha256']
        # Observed failure class: the correct digest's prefix plus another field's suffix.
        corrupt = original[:35] + other[-19:]
        self.assertEqual(len(corrupt), 54)
        self.assertNotIn(corrupt, destinations)
        for value in (corrupt, other, '0'*64):
            bad = deepcopy(good)
            bad['answer_definitions']['fields'][26]['definition']['permitted_destination']['locator_sha256'] = value
            with self.subTest(value=value), self.assertRaises(DefinitionError):
                word_contract.validate_result(self.inventory, bad, 'proposer', self.config)
        for change in ('missing', 'duplicate', 'wrong_field_key', 'wrong_story_digest'):
            bad = deepcopy(good)
            if change == 'missing': bad['answer_definitions']['fields'].pop()
            elif change == 'duplicate': bad['answer_definitions']['fields'][1] = deepcopy(bad['answer_definitions']['fields'][0])
            elif change == 'wrong_field_key': bad['answer_definitions']['fields'][0]['definition']['permitted_destination']['field_key'] = rows[1]['field_key']
            else: bad['stories'][0]['content_sha256'] = '0'*64
            with self.subTest(change=change), self.assertRaises((DefinitionError, DocumentFailure)):
                word_contract.validate_result(self.inventory, bad, 'proposer', self.config)

    def test_absent_policy_keeps_historical_payload_and_schema(self):
        for role in ('proposer', 'checker'):
            proposal = self.complete_output() if role == 'checker' else None
            old = preparation.provider_request(self.inventory, role, self.historical, proposal)
            with patch.object(preparation, 'finite_identities', return_value=False):
                self.assertEqual(old, preparation.provider_request(self.inventory, role, self.historical, proposal))
            self.assertNotIn('source_identity_contract', json.loads(old['messages'][0]['content']))
            destination = old['output_config']['format']['schema']['properties']['answer_definitions']['properties']['fields']['items']['properties']['definition']['properties']['permitted_destination']['properties']
            self.assertNotIn('enum', destination['locator_sha256'])
            self.assertIn('minLength: 64', destination['locator_sha256']['description'])

    def test_unknown_or_incompatible_policy_refuses_before_client_or_reservation(self):
        configs = [{**self.config, preparation.IDENTITY_KEY: value} for value in (None, False, 0, '', 'future')]
        configs.append({k:v for k,v in self.config.items() if k != preparation.DESTINATION_KEY})
        for config in configs:
            with self.subTest(config=config), patch('anthropic.Anthropic') as client, \
                    patch('core.testing_authority.reserve_role') as reserve:
                with self.assertRaises(preparation.DocumentError):
                    preparation.call_role(SimpleNamespace(inventory=self.inventory, config=config), 'proposer', 999999999)
                client.assert_not_called(); reserve.assert_not_called()
        wrong = deepcopy(self.inventory)
        wrong['protocol'] = PROTOCOL
        with self.assertRaises(preparation.DocumentError):
            preparation.role_schema('proposer', PROTOCOL, wrong, self.config)

    def test_only_new_ordinary_preparations_freeze_identity_policy(self):
        original = {'mode':'fixture'}
        for source in ('a'*64, preparation.WM_IOV_SHA256):
            with patch.object(preparation, 'feature_enabled', return_value=True), \
                    patch.object(preparation, 'configuration', return_value=original), \
                    patch('core.preparation_campaign.active_campaign_config', side_effect=lambda c,_:c), \
                    patch('core.testing_authority.identity', return_value=True), \
                    patch('core.testing_authority.create_preparation') as create:
                preparation.create_preparation(SimpleNamespace(sha256=source), 'synthetic-clinician')
            frozen = create.call_args.args[2]
            if source == preparation.WM_IOV_SHA256:
                self.assertNotIn(preparation.IDENTITY_KEY, frozen)
            else:
                self.assertEqual(frozen[preparation.IDENTITY_KEY], preparation.IDENTITY_PROFILE)
        self.assertEqual(original, {'mode':'fixture'})
