"""Versioned wire choices, canonical safety checks and immutable evidence replay."""
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from anthropic import transform_schema
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import preparation, preparation_choice_transport as codec, word_contract
from core.provider_schema import ANTHROPIC_SCHEMA_TRANSPORT
from core.tests import test_preparation_output, test_preparation_schema_transport as legacy
from core.tests.test_provider_schema import expand
from documents import DocumentError
from documents.component_contracts import CONFIG_KEY, CHOICE_CONTRACT
from documents.preparation import TYPED_PROTOCOL, digest


def encoded(value):
    result = deepcopy(value)
    for component in codec.components(result):
        component['choices'] = json.dumps(component['choices'], ensure_ascii=False, separators=(',', ':'))
    return result


class PreparationChoiceTransportTests(SimpleTestCase):
    setUp = legacy.PreparationSchemaTransportTests.setUp
    response = legacy.PreparationSchemaTransportTests.response

    def live(self):
        return {**self.config, 'mode': 'live', 'word_preparation_protocol': TYPED_PROTOCOL,
                CONFIG_KEY: CHOICE_CONTRACT, preparation.SCHEMA_TRANSPORT_KEY: codec.TRANSPORT}

    def canonical(self, role='proposer', proposal=None):
        config = {**self.live(), 'mode': 'fixture'}
        del config[preparation.SCHEMA_TRANSPORT_KEY]
        return preparation.provider_role(self.inventory, role, config, 1, proposal)[0]

    def evidence(self, role='proposer', proposal=None):
        config = self.live()
        envelope = preparation.provider_request(self.inventory, role, config, proposal)
        return {'response_transport': codec.TRANSPORT, 'request_envelope': envelope,
                'request_envelope_sha256': digest(envelope),
                'response': {'stop_reason': 'end_turn', 'content': [{'type': 'text',
                    'text': json.dumps(encoded(self.canonical(role, proposal)), ensure_ascii=False)}]}}

    def decode(self, value, *, role='proposer', proposal=None, evidence=None, request_sha=None):
        config = self.live()
        payload = preparation.role_payload(self.inventory, role, proposal, config=config)
        if evidence is None:
            evidence = self.evidence(role, proposal)
            evidence['response']['content'][0]['text'] = json.dumps(value, ensure_ascii=False)
        return preparation.decode_role_response(self.inventory, role, config, value, proposal,
            evidence,
            request_sha if request_sha is not None else digest(payload))

    def test_both_roles_decode_exactly_and_only_component_choices_change_on_wire(self):
        proposal = self.canonical()
        for role in ('proposer', 'checker'):
            value = self.canonical(role, proposal)
            before = deepcopy(value)
            wire = encoded(value)
            actual = self.decode(wire, role=role, proposal=proposal)
            self.assertEqual(actual, value)
            self.assertEqual(value, before)
            word_contract.validate_result(self.inventory, actual, role, self.live())
            canonical_schema = preparation.role_schema(role, TYPED_PROTOCOL, self.inventory, self.live())
            expected = transform_schema(codec.wire_schema(canonical_schema))
            actual_schema = self.evidence(role, proposal)['request_envelope']['output_config']['format']['schema']
            self.assertEqual(json.dumps(expand(actual_schema)), json.dumps(expected))
            path = (expected['properties']['answer_definitions']['properties']['fields']['items']
                ['properties']['definition']['properties'])
            self.assertEqual(path['choices']['type'], 'array')
            self.assertEqual(path['component_contract']['properties']['components']['items']
                             ['properties']['option_quote'],
                             transform_schema(canonical_schema)['properties']['answer_definitions']
                             ['properties']['fields']['items']['properties']['definition']['properties']
                             ['component_contract']['properties']['components']['items']['properties']['option_quote'])

    def test_new_payload_and_request_are_explicit_and_deterministic_without_mutating_config(self):
        config = self.live()
        before = deepcopy(config)
        old = {**config, preparation.SCHEMA_TRANSPORT_KEY: ANTHROPIC_SCHEMA_TRANSPORT}
        new_payload = preparation.role_payload(self.inventory, 'proposer', config=config)
        old_payload = preparation.role_payload(self.inventory, 'proposer', config=old)
        self.assertEqual(new_payload['response_transport'], codec.TRANSPORT)
        self.assertNotIn('response_transport', old_payload)
        self.assertNotEqual(digest(new_payload), digest(old_payload))
        reordered = json.loads(json.dumps(self.inventory, sort_keys=True))
        first = preparation.provider_request(self.inventory, 'proposer', config)
        self.assertEqual(digest(first), digest(preparation.provider_request(reordered, 'proposer', config)))
        self.assertEqual(config, before)
        self.assertEqual(preparation.role_limits(self.inventory, config), preparation.role_limits(self.inventory, old))

    def test_transport_refuses_incompatible_profiles_before_reservation_or_client(self):
        invalid = [dict(self.live(), **{key: value}) for key, value in (
            ('mode', 'fixture'), ('provider', 'openai'), ('word_preparation_protocol', 'old'),
            ('word_preparation_output_profile', preparation.OUTPUT_PROFILE),
            (word_contract.CONFIG_KEY, word_contract.PROFILE), (CONFIG_KEY, 'field-components-v2'),
            ('semantic_definition_version', True), ('semantic_definition_version', 3))]
        for config in invalid:
            with self.subTest(config=config), patch('anthropic.Anthropic') as client, \
                    patch('core.testing_authority.reserve_role') as reserve:
                with self.assertRaises(DocumentError):
                    preparation.call_role(SimpleNamespace(inventory=self.inventory, config=config), 'proposer', 999999)
                client.assert_not_called()
                reserve.assert_not_called()

    def test_missing_wrong_or_stale_codec_request_bindings_refuse(self):
        value = encoded(self.canonical())
        for change in (
                lambda e: e.pop('response_transport'),
                lambda e: e.update(response_transport=ANTHROPIC_SCHEMA_TRANSPORT),
                lambda e: e.pop('request_envelope'),
                lambda e: e.pop('response'),
                lambda e: e['response'].update(stop_reason='max_tokens'),
                lambda e: e['response']['content'][0].update(text='{}'),
                lambda e: e.update(request_envelope_sha256='0' * 64),
                lambda e: e['request_envelope'].update(max_tokens=True),
                lambda e: (e['request_envelope'].update(model='different-model'),
                           e.update(request_envelope_sha256=digest(e['request_envelope'])))):
            evidence = self.evidence()
            change(evidence)
            with self.subTest(evidence=evidence), self.assertRaises(DocumentError):
                self.decode(value, evidence=evidence)
        with self.assertRaises(DocumentError):
            self.decode(value, request_sha='0' * 64)
        with self.assertRaises(DocumentError):
            self.decode(value, role='checker', proposal=self.canonical(), evidence=self.evidence())

    def test_invalid_encoded_values_are_never_coerced_or_retried(self):
        for value in (None, True, 4, [], {}, '', 'null', 'true', '{}', '[1]', '[false]',
                      '[null]', '[["a"]]', '"[]"', '[NaN]', '[Infinity]', '["x"] trailing',
                      '["\\ud800"]', ' ' * (codec.MAX_ENCODED_BYTES + 1)):
            wire = encoded(self.canonical())
            next(codec.components(wire))['choices'] = value
            with self.subTest(value=repr(value)[:60]):
                if value == '["\\ud800"]':
                    # JSON permits an escaped unpaired surrogate; the unchanged
                    # canonical non-choice validator still refuses its array.
                    result = self.decode(wire)
                    with self.assertRaises(ValueError):
                        word_contract.validate_result(self.inventory, result, 'proposer', self.live())
                else:
                    with self.assertRaises(DocumentError):
                        self.decode(wire)

    def test_maximum_unicode_choice_array_preserves_order_and_source_text(self):
        values = [str(index) + ' é中文😀"\\\n\t' * 40 for index in range(200)]
        value = self.canonical()
        component = next(codec.components(value))
        component.update(choices=values, option_quote='Literal "source" \\ evidence')
        before = deepcopy(value)
        result = self.decode(encoded(value))
        self.assertEqual(result, before)
        self.assertEqual(value, before)
        # Transport preservation supplies no permission to call an invented
        # source choice supported; canonical source ownership still rejects it.
        with self.assertRaises(ValueError):
            word_contract.validate_result(self.inventory, result, 'proposer', self.live())

    def test_canonical_extra_keys_bounds_required_and_quote_guards_still_refuse(self):
        for change in (
                lambda c: c.update(choices=['x'] * 201),
                lambda c: c.update(extra='not-dropped'),
                lambda c: c.update(required=False),
                lambda c: c.update(option_quote=''),
                lambda c: c.update(choices=['Yes', 'yes']),
                lambda c: c.update(option_quote='foreign source')):
            value = self.canonical()
            change(next(codec.components(value)))
            result = self.decode(encoded(value))
            self.assertEqual(result, value)
            with self.assertRaises(ValueError):
                word_contract.validate_result(self.inventory, result, 'proposer', self.live())

    def test_actual_maximum_physical_choices_remain_valid_and_one_more_remains_invalid(self):
        from documents import component_contracts as cc
        scope = {'subject': 'patient', 'temporality': 'any', 'polarity': 'any'}
        options = [(str(index) + 'é中😀"\\\n\t' * 400)[:2000] for index in range(200)]
        field = {'key': 'color', 'label': 'Choose color', 'locator': {'paragraph': 1},
                 'answer_constraints': {'version': 1, 'data_type': 'choice', 'options': options}}
        component = {'id': 'color', 'question_quote': field['label'], 'label': None,
            'meaning': 'The documented color', 'value_type': 'choice', 'scope': scope,
            'unit': None, 'unit_requirement': 'none', 'required': True,
            'encounter_scope': 'current', 'choices': options, 'option_quote': None}
        definition = {'value_type': 'choice', 'scope': scope, 'unit': None, 'choices': options,
            'answer_mode': 'atomic', 'component_contract': {'contract': CHOICE_CONTRACT,
                'rendering': 'plain', 'components': [component]}}
        cc.validate(field, definition)
        wrapper = {'answer_definitions': {'fields': [{'definition': definition}]}}
        roundtrip = codec.decode(encoded(wrapper))
        self.assertEqual(roundtrip, wrapper)
        cc.validate(field, roundtrip['answer_definitions']['fields'][0]['definition'])
        for change in (lambda d: d['component_contract']['components'][0]['choices'].append('extra'),
                       lambda d: d['component_contract']['components'][0]['choices'].reverse(),
                       lambda d: d['component_contract']['components'][0].update(option_quote='invented')):
            changed = deepcopy(definition)
            change(changed)
            decoded = codec.decode(encoded({'answer_definitions': {'fields': [{'definition': changed}]}}))
            with self.assertRaises(ValueError):
                cc.validate(field, decoded['answer_definitions']['fields'][0]['definition'])

    def test_bad_live_wire_keeps_raw_response_known_usage_and_one_submission(self):
        import httpx
        from anthropic import Anthropic
        for bad in ('not-json', '[]'):
            wire = encoded(self.canonical())
            first = next(codec.components(wire))
            first['choices'] = bad
            if bad == '[]':
                first['required'] = False  # Decodes, then unchanged canonical validation refuses.
            config = self.live()
            packet = SimpleNamespace(inventory=self.inventory, config=config, proposal={})
            receipt = test_preparation_output.PreparationOutputTests.receipt(self)
            receipt.role = 'proposer'
            receipt.preparation = packet
            receipt.request_sha256 = digest(preparation.role_payload(self.inventory, 'proposer', config=config))
            sent = []
            def handle(request):
                sent.append(json.loads(request.content))
                return httpx.Response(200, headers={'request-id': 'offline-request'}, json={
                    'id': 'offline-result', 'type': 'message', 'role': 'assistant',
                    'model': 'offline-returned-model', 'stop_reason': 'end_turn', 'stop_sequence': None,
                    'content': [{'type': 'text', 'text': json.dumps(wire)}],
                    'usage': {'input_tokens': 10, 'output_tokens': 10}})
            with httpx.Client(transport=httpx.MockTransport(handle)) as http:
                client = Anthropic(api_key='synthetic-offline-only', base_url='https://synthetic-provider.invalid',
                    http_client=http, max_retries=0, timeout=60)
                with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
                        patch('anthropic.Anthropic', return_value=client), \
                        patch('core.testing_authority.identity', return_value=True), \
                        patch('core.testing_authority.reserve_role', return_value=receipt), \
                        patch('core.preparation_campaign.provider_slot', return_value=nullcontext()), \
                        patch.object(preparation.time, 'monotonic', return_value=100):
                    with self.assertRaises((DocumentError, ValueError)):
                        preparation.call_role(packet, 'proposer', 280)
            self.assertEqual(len(sent), 1)
            self.assertEqual(receipt.state, 'failed')
            self.assertIsNotNone(receipt.computed_cost)
            evidence = json.loads((self.root / receipt.response_path).read_bytes())
            self.assertEqual(json.loads(evidence['response']['content'][0]['text']), wire)
            with self.assertRaises((DocumentError, ValueError)):
                preparation.read_retained_role(receipt, 'live')

    def test_live_sdk_retains_original_wire_and_replays_canonical_both_roles_once(self):
        import httpx
        from anthropic import Anthropic
        proposal = self.canonical()
        for role in ('proposer', 'checker'):
            value = self.canonical(role, proposal)
            wire = encoded(value)
            config = self.live()
            packet = SimpleNamespace(inventory=self.inventory, config=config, proposal=proposal)
            receipt = test_preparation_output.PreparationOutputTests.receipt(self)
            receipt.role = role
            receipt.preparation = packet
            receipt.request_sha256 = digest(preparation.role_payload(self.inventory, role, proposal, config=config))
            sent = []
            raw_response = {'id': 'offline-result', 'type': 'message', 'role': 'assistant',
                'model': 'offline-returned-model', 'stop_reason': 'end_turn', 'stop_sequence': None,
                'content': [{'type': 'text', 'text': json.dumps(wire, ensure_ascii=False)}],
                'usage': {'input_tokens': 10, 'output_tokens': 10}}
            def handle(request):
                self.assertEqual(request.url.host, 'synthetic-provider.invalid')
                sent.append(json.loads(request.content))
                return httpx.Response(200, headers={'request-id': 'offline-request'}, json=raw_response)
            with httpx.Client(transport=httpx.MockTransport(handle)) as http:
                client = Anthropic(api_key='synthetic-offline-only', base_url='https://synthetic-provider.invalid',
                    http_client=http, max_retries=0, timeout=60)
                with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'synthetic-offline-only'}), \
                        patch('anthropic.Anthropic', return_value=client), \
                        patch('core.testing_authority.identity', return_value=True), \
                        patch('core.testing_authority.reserve_role', return_value=receipt), \
                        patch('core.preparation_campaign.provider_slot', return_value=nullcontext()), \
                        patch.object(preparation.time, 'monotonic', return_value=100):
                    self.assertEqual(preparation.call_role(packet, role, 280, proposal), value)
            self.assertEqual(len(sent), 1)
            self.assertEqual(receipt.state, 'succeeded')
            raw = (self.root / receipt.response_path).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), receipt.response_sha256)
            retained = json.loads(raw)
            self.assertEqual(retained['response']['content'][0]['text'], raw_response['content'][0]['text'])
            self.assertEqual(retained['response']['content'][0]['type'], 'text')
            self.assertIsNone(retained['response']['content'][0]['citations'])
            self.assertEqual(retained['request_envelope'], sent[0])
            self.assertEqual(retained['request_envelope_sha256'], digest(sent[0]))
            self.assertEqual(retained['response_transport'], codec.TRANSPORT)
            self.assertEqual(preparation.read_retained_role(receipt, 'live'), value)
            # A valid file hash cannot authorize another config or receipt payload.
            receipt.request_sha256 = '0' * 64
            with self.assertRaises(DocumentError):
                preparation.read_retained_role(receipt, 'live')
            self.assertEqual((self.root / receipt.response_path).read_bytes(), raw)

    def test_unmarked_old_mode_never_decodes_a_string_or_accepts_a_new_evidence_marker(self):
        value = encoded(self.canonical())
        for config in ({**self.config, 'mode': 'live'},
                       {**self.config, 'mode': 'live', preparation.SCHEMA_TRANSPORT_KEY: ANTHROPIC_SCHEMA_TRANSPORT}):
            self.assertIs(preparation.decode_role_response(self.inventory, 'proposer', config, value,
                          None, {}, None), value)
            with self.assertRaises(DocumentError):
                preparation.decode_role_response(self.inventory, 'proposer', config, value,
                    None, {'response_transport': codec.TRANSPORT}, None)

    def test_queue_keeps_wm_legacy_and_marks_only_new_ordinary_live_v3(self):
        from documents.sdk_service import WM_IOV_SHA256
        for sha, expected in (('a' * 64, codec.TRANSPORT), (WM_IOV_SHA256, ANTHROPIC_SCHEMA_TRANSPORT)):
            config = {**self.config, 'mode': 'live'}
            with patch.object(preparation, 'configuration', return_value=config), \
                    patch('core.preparation_campaign.active_campaign_config', side_effect=lambda value, _: value), \
                    patch('core.testing_authority.identity', return_value=True), \
                    patch('core.testing_authority.create_preparation') as create:
                preparation.create_preparation(SimpleNamespace(sha256=sha), SimpleNamespace())
                queued = create.call_args.args[2]
                self.assertEqual(queued[preparation.SCHEMA_TRANSPORT_KEY], expected)
                self.assertEqual(preparation.schema_transport(queued), expected)
