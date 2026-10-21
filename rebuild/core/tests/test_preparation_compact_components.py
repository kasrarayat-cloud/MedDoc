"""Prospective compact rows retain every canonical/source-bound component value."""
from copy import deepcopy
import json
from pathlib import Path

from anthropic import transform_schema
from docx import Document
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import preparation, preparation_choice_transport as codec, word_contract
from core.tests import test_preparation_schema_transport as legacy
from core.tests import test_preparation_stream_transport as stream_tests
from core.tests.test_provider_schema import expand
from core.security import private_path
from documents import DocumentError
from documents.component_contracts import CONFIG_KEY, CHOICE_CONTRACT
from documents.preparation import TYPED_PROTOCOL, digest, inventory


def encoded_rows(canonical):
    result = deepcopy(canonical)
    for contract in codec.contracts(result):
        rows = []
        for component in contract['components']:
            assert set(component) == set(codec.COMPONENT_COLUMNS)
            assert set(component['scope']) == set(codec.SCOPE_COLUMNS)
            rows.append([[component[key][name] for name in codec.SCOPE_COLUMNS]
                         if key == 'scope' else component[key] for key in codec.COMPONENT_COLUMNS])
        contract['components'] = json.dumps(rows, ensure_ascii=False, separators=(',', ':'))
    return result


def compound_form(root):
    """New test-only source: twenty distinct questions, three requested parts each."""
    document = Document()
    table = document.add_table(rows=20, cols=2)
    parts = []
    for number, row in enumerate(table.rows, 1):
        first = f'symptom {number:02d}'
        if number == 1:
            first = 'status 01 open or closed'
        if number == 2:
            first = 'status 02 null or active'
        children = [first, f'duration {number:02d}', f'course {number:02d}']
        row.cells[0].text = 'Describe ' + '; '.join(children) + '.'
        parts.append(children)
    path = Path(root) / 'new-synthetic-compound20.docx'
    document.save(path)
    return inventory(path, protocol=TYPED_PROTOCOL), parts


def compound_canonical(inv, parts, config, role='proposer', proposal=None):
    fixture = {k: v for k, v in config.items() if k != preparation.SCHEMA_TRANSPORT_KEY}
    fixture['mode'] = 'fixture'
    result = preparation.provider_role(inv, role, fixture, 1, proposal)[0]
    for number, (field, children) in enumerate(zip(result['answer_definitions']['fields'], parts), 1):
        definition = field['definition']
        scope = {'subject': 'patient', 'temporality': 'current', 'polarity': 'any'}
        definition.update(meaning='Describe the complete requested ' + '; '.join(children) + '.',
                          value_type='text', answer_mode='narrative', choices=[], unit=None,
                          scope=deepcopy(scope))
        components = []
        for index, child in enumerate(children, 1):
            choice = index == 1 and number in (1, 2)
            components.append({'id': f'c{index}', 'question_quote': child,
                'label': child, 'meaning': 'Document the requested ' + child + '.',
                'value_type': 'choice' if choice else 'text', 'scope': deepcopy(scope),
                'unit': None, 'unit_requirement': 'none', 'required': True,
                'encounter_scope': 'current',
                'choices': (['open', 'closed'] if number == 1 else ['null', 'active']) if choice else [],
                'option_quote': ('open or closed' if number == 1 else 'null or active') if choice else None})
        definition['component_contract'] = {'contract': CHOICE_CONTRACT,
                                          'rendering': 'labelled', 'components': components}
    return word_contract.validate_result(inv, result, role, config)


class PreparationCompactComponentTests(SimpleTestCase):
    setUp = legacy.PreparationSchemaTransportTests.setUp

    def live(self, transport=codec.COMPACT_TRANSPORT):
        return {**self.config, 'mode': 'live', 'word_preparation_protocol': TYPED_PROTOCOL,
                CONFIG_KEY: CHOICE_CONTRACT, preparation.SCHEMA_TRANSPORT_KEY: transport}

    def canonical(self, role='proposer', proposal=None):
        fixture = {**self.live(), 'mode': 'fixture'}
        fixture.pop(preparation.SCHEMA_TRANSPORT_KEY)
        return preparation.provider_role(self.inventory, role, fixture, 1, proposal)[0]

    def evidence(self, value, role='proposer', proposal=None, *, inv=None, config=None):
        inv = self.inventory if inv is None else inv
        config = self.live() if config is None else config
        envelope = preparation.provider_request(inv, role, config, proposal)
        return {'response_transport': codec.COMPACT_TRANSPORT, 'request_envelope': envelope,
                'request_envelope_sha256': digest(envelope),
                'response': {'stop_reason': 'end_turn', 'content': [{'type': 'text',
                    'text': json.dumps(value, ensure_ascii=False)}]}}

    def decode(self, value, role='proposer', proposal=None, *, inv=None, config=None, evidence=None):
        inv = self.inventory if inv is None else inv
        config = self.live() if config is None else config
        evidence = self.evidence(value, role, proposal, inv=inv, config=config) if evidence is None else evidence
        payload = preparation.role_payload(inv, role, proposal, config=config)
        return preparation.decode_role_response(inv, role, config, value, proposal, evidence, digest(payload))

    def first_rows(self, value):
        return json.loads(next(codec.contracts(value))['components'])

    def replace_first_rows(self, value, rows):
        next(codec.contracts(value))['components'] = json.dumps(rows, ensure_ascii=False)
        return value

    def test_explicit_twelve_and_three_columns_without_v4_alias_change(self):
        self.assertEqual(codec.TRANSPORT, 'anthropic-shared-components-json-v4')
        self.assertEqual(codec.COMPONENT_COLUMNS, ('id', 'question_quote', 'label', 'meaning',
            'value_type', 'scope', 'unit', 'unit_requirement', 'required', 'encounter_scope',
            'choices', 'option_quote'))
        self.assertEqual(codec.SCOPE_COLUMNS, ('subject', 'temporality', 'polarity'))
        self.assertEqual(len(codec.COMPONENT_COLUMNS), 12)
        self.assertEqual(len(codec.SCOPE_COLUMNS), 3)

    def test_both_roles_restore_exact_values_before_complete_canonical_validation(self):
        proposal = self.canonical()
        for role in ('proposer', 'checker'):
            value = self.canonical(role, proposal)
            before = deepcopy(value)
            wire = encoded_rows(value)
            self.assertEqual(self.decode(wire, role, proposal), value)
            word_contract.validate_result(self.inventory, self.decode(wire, role, proposal), role, self.live())
            self.assertEqual(value, before)
            self.assertEqual(codec.decode(wire, codec.COMPACT_TRANSPORT), value)

    def test_compact_schema_keeps_same_opaque_string_and_full_canonical_schema(self):
        canonical = preparation.role_schema('proposer', TYPED_PROTOCOL, self.inventory, self.live())
        before = deepcopy(canonical)
        wire = codec.wire_schema(canonical, codec.COMPACT_TRANSPORT)
        properties = wire['properties']['answer_definitions']['properties']['fields']['items']
        prop = properties['properties']['definition']['properties']['component_contract']['properties']['components']
        self.assertEqual(prop['type'], 'string')
        self.assertIn(json.dumps(codec.COMPONENT_COLUMNS), prop['description'])
        self.assertIn(json.dumps(codec.SCOPE_COLUMNS), prop['description'])
        self.assertEqual(canonical, before)
        old = codec.wire_schema(canonical, codec.TRANSPORT)
        def without_descriptions(value):
            if type(value) is dict:
                return {k: without_descriptions(v) for k, v in value.items() if k != 'description'}
            if type(value) is list:
                return [without_descriptions(v) for v in value]
            return value
        self.assertEqual(without_descriptions(transform_schema(wire)),
                         without_descriptions(transform_schema(old)))
        actual = self.evidence(encoded_rows(self.canonical()))['request_envelope']
        self.assertEqual(expand(actual['output_config']['format']['schema']), transform_schema(wire))
        self.assertEqual(preparation.role_limits(self.inventory, self.live()),
                         preparation.role_limits(self.inventory, self.live(codec.TRANSPORT)))

    def test_source_request_and_raw_wire_are_explicitly_bound_for_both_roles(self):
        proposal = self.canonical()
        for role in ('proposer', 'checker'):
            canonical = self.canonical(role, proposal)
            wire = encoded_rows(canonical)
            evidence = self.evidence(wire, role, proposal)
            old = preparation.provider_request(self.inventory, role, self.live(codec.TRANSPORT), proposal)
            self.assertNotEqual(digest(old), evidence['request_envelope_sha256'])
            self.assertEqual(preparation.role_payload(self.inventory, role, proposal, config=self.live())
                             ['response_transport'], codec.COMPACT_TRANSPORT)
            self.assertIn(codec.COMPACT_INSTRUCTIONS, evidence['request_envelope']['system'])
            self.assertNotIn(codec.COMPONENTS_INSTRUCTIONS, evidence['request_envelope']['system'])
            mutations = [lambda e: e.update(response_transport=codec.TRANSPORT),
                lambda e: e.pop('response_transport'), lambda e: e.pop('request_envelope_sha256'),
                lambda e: e['request_envelope'].update(max_tokens=True),
                lambda e: e['response']['content'][0].update(text='{}')]
            for mutate in mutations:
                changed = deepcopy(evidence)
                mutate(changed)
                with self.subTest(role=role, mutate=mutate), self.assertRaises(DocumentError):
                    self.decode(wire, role, proposal, evidence=changed)

    def test_row_cardinality_and_outer_encoded_types_refuse(self):
        base = encoded_rows(self.canonical())
        row = self.first_rows(base)[0]
        for rows in (None, False, {}, 1, '[]', [None], [{}], [False], [row[:-1]],
                     [row + [None]], [json.dumps(row)]):
            with self.subTest(rows=repr(rows)[:60]), self.assertRaises(DocumentError):
                codec.decode(self.replace_first_rows(deepcopy(base), rows), codec.COMPACT_TRANSPORT)
        for encoded in (None, False, [], {}, 3, '', ' ', 'null', '[', '[] trailing',
                        'NaN', 'Infinity', '[NaN]', '[Infinity]', '[[{"x":1,"x":2}]]',
                        '[[{"x":1,"\\u0078":2}]]', '[' * 1200 + ']' * 1200,
                        ' ' * (codec.MAX_ENCODED_BYTES + 1)):
            wire = deepcopy(base)
            next(codec.contracts(wire))['components'] = encoded
            with self.subTest(encoded=repr(encoded)[:50]), self.assertRaises(DocumentError):
                codec.decode(wire, codec.COMPACT_TRANSPORT)

    def test_every_component_and_scope_position_has_exact_native_json_type(self):
        base = encoded_rows(self.canonical())
        rows = self.first_rows(base)
        cases = []
        for index in (0, 1, 3, 4, 7, 9):
            cases.extend((index, value) for value in (None, False, 1, [], {}))
        for index in (2, 6, 11):
            cases.extend((index, value) for value in (False, 1, [], {}))
        cases.extend((8, value) for value in (None, 0, 1, 'true', [], {}))
        cases.extend((10, value) for value in (None, False, 1, '[]', {}, [1], [None], [False], [[]]))
        cases.extend((5, value) for value in (None, False, {}, 'patient', [], ['patient'],
            ['patient', 'any'], ['patient', 'any', 'any', 'extra'], ['patient', None, 'any'],
            ['patient', 0, 'any'], ['patient', False, 'any'], ['patient', [], 'any']))
        for index, value in cases:
            changed = deepcopy(rows)
            changed[0][index] = value
            with self.subTest(index=index, value=value), self.assertRaises(DocumentError):
                codec.decode(self.replace_first_rows(deepcopy(base), changed), codec.COMPACT_TRANSPORT)

    def test_null_literal_null_empty_unicode_quotes_backslashes_do_not_collapse(self):
        canonical = self.canonical()
        for value in (None, 'null', '', '"null"', 'source "é中文😀" \\ quotation\n\t', 'x' * 2000):
            for key in ('label', 'unit', 'option_quote'):
                changed = deepcopy(canonical)
                next(codec.components(changed))[key] = value
                self.assertEqual(codec.decode(encoded_rows(changed), codec.COMPACT_TRANSPORT), changed)
        for key in ('question_quote', 'meaning'):
            changed = deepcopy(canonical)
            next(codec.components(changed))[key] = 'null é中文😀 "quoted" \\ source\n\t'
            self.assertEqual(codec.decode(encoded_rows(changed), codec.COMPACT_TRANSPORT), changed)

    def test_source_required_choices_and_signing_failures_are_still_canonical_failures(self):
        original = self.canonical()
        cases = [lambda c: c.update(question_quote='not part of the immutable question'),
            lambda c: c.update(required=False), lambda c: c.update(value_type='unknown'),
            lambda c: c.update(unit='invented_unit', unit_requirement='printed'),
            lambda c: c.update(choices=['invented']), lambda c: c.update(option_quote='invented'),
            lambda c: c['scope'].update(subject='unknown')]
        for mutate in cases:
            changed = deepcopy(original)
            mutate(next(codec.components(changed)))
            decoded = codec.decode(encoded_rows(changed), codec.COMPACT_TRANSPORT)
            self.assertEqual(decoded, changed)
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                word_contract.validate_result(self.inventory, decoded, 'proposer', self.live())
        for count in (0, 31):
            changed = deepcopy(original)
            contract = next(codec.contracts(changed))
            component = deepcopy(contract['components'][0])
            contract['components'] = [{**component, 'id': 'c' + str(i)} for i in range(count)]
            decoded = codec.decode(encoded_rows(changed), codec.COMPACT_TRANSPORT)
            self.assertEqual(len(next(codec.contracts(decoded))['components']), count)
            with self.subTest(count=count), self.assertRaises(ValueError):
                word_contract.validate_result(self.inventory, decoded, 'proposer', self.live())
        protected = deepcopy(original)
        next(codec.contracts(protected)).update(rendering='protected', components=[])
        with self.assertRaises(ValueError):
            word_contract.validate_result(self.inventory, codec.decode(encoded_rows(protected),
                codec.COMPACT_TRANSPORT), 'proposer', self.live())

    def test_unknown_outer_data_is_preserved_for_full_validator_not_silently_dropped(self):
        canonical = self.canonical()
        for change in (lambda c: c.update(unknown='must remain visible'),
            lambda c: c['answer_definitions']['fields'][0].update(unknown='must remain visible'),
            lambda c: c['answer_definitions']['fields'][0]['definition'].update(unknown='must remain visible')):
            changed = deepcopy(canonical)
            change(changed)
            self.assertEqual(codec.decode(encoded_rows(changed), codec.COMPACT_TRANSPORT), changed)
            with self.assertRaises((ValueError, ValidationError)):
                word_contract.validate_result(self.inventory, changed, 'proposer', self.live())

    def test_compound_twenty_destination_sixty_component_form_roundtrips_and_saves_bytes(self):
        inv, parts = compound_form(self.root)
        proposal = compound_canonical(inv, parts, self.live())
        for role in ('proposer', 'checker'):
            canonical = compound_canonical(inv, parts, self.live(), role, proposal)
            self.assertEqual(len(canonical['anchors']), 20)
            self.assertEqual(sum(len(c['components']) for c in codec.contracts(canonical)), 60)
            wire = encoded_rows(canonical)
            decoded = self.decode(wire, role, proposal, inv=inv)
            self.assertEqual(decoded, canonical)
            word_contract.validate_result(inv, decoded, role, self.live())
            old = deepcopy(canonical)
            for c in codec.contracts(old):
                c['components'] = json.dumps(c['components'], ensure_ascii=False, separators=(',', ':'))
            size = lambda v: len(json.dumps(v, ensure_ascii=False, separators=(',', ':')).encode())
            self.assertLessEqual(size(wire), size(old) * 0.85)
            self.assertEqual(next(codec.components(decoded))['choices'], ['open', 'closed'])
            second = list(codec.contracts(decoded))[1]['components'][0]
            self.assertEqual(second['choices'], ['null', 'active'])
            self.assertEqual(second['option_quote'], 'null or active')
            self.assertIsNone(list(codec.components(decoded))[1]['option_quote'])

    def test_historical_component_object_transport_is_not_silently_row_decoded(self):
        canonical = self.canonical()
        v4 = deepcopy(canonical)
        for contract in codec.contracts(v4):
            contract['components'] = json.dumps(contract['components'], ensure_ascii=False, separators=(',', ':'))
        self.assertEqual(codec.decode(v4, codec.TRANSPORT), canonical)
        self.assertEqual(codec.instructions(codec.TRANSPORT), codec.COMPONENTS_INSTRUCTIONS)
        with self.assertRaises(DocumentError):
            codec.decode(v4, codec.COMPACT_TRANSPORT)
        with self.assertRaises(DocumentError):
            codec.decode(encoded_rows(canonical), codec.TRANSPORT)

    def test_duplicate_components_and_oversized_choice_lists_are_not_hidden_by_encoding(self):
        canonical = self.canonical()
        for change in ('duplicate', '201choices'):
            changed = deepcopy(canonical)
            contract = next(codec.contracts(changed))
            if change == 'duplicate':
                contract['components'].append(deepcopy(contract['components'][0]))
            else:
                contract['components'][0].update(choices=[str(i) for i in range(201)], value_type='choice')
            decoded = codec.decode(encoded_rows(changed), codec.COMPACT_TRANSPORT)
            self.assertEqual(decoded, changed)
            with self.subTest(change=change), self.assertRaises(ValueError):
                word_contract.validate_result(self.inventory, decoded, 'proposer', self.live())


class PreparationCompactSDKTests(SimpleTestCase):
    """Reuse the actual installed async SDK/receipt fixture, without its other tests."""
    setUp = legacy.PreparationSchemaTransportTests.setUp
    receipt = stream_tests.PreparationStreamTransportTests.receipt
    sdk_client = stream_tests.PreparationStreamTransportTests.sdk_client
    invoke = stream_tests.PreparationStreamTransportTests.invoke
    trace = stream_tests.PreparationStreamTransportTests.trace

    def live(self, *, choice=False):
        return {**self.config, 'mode': 'live', 'word_preparation_protocol': TYPED_PROTOCOL,
                CONFIG_KEY: CHOICE_CONTRACT, preparation.SCHEMA_TRANSPORT_KEY: codec.COMPACT_TRANSPORT,
                preparation.stream_transport.CONFIG_KEY: preparation.stream_transport.TRANSPORT}

    def canonical(self, role='proposer', proposal=None):
        fixture = {**self.live(), 'mode': 'fixture'}
        fixture.pop(preparation.SCHEMA_TRANSPORT_KEY)
        fixture.pop(preparation.stream_transport.CONFIG_KEY)
        return preparation.provider_role(self.inventory, role, fixture, 1, proposal)[0]

    def test_actual_sdk_both_roles_send_exact_v5_body_retain_raw_and_replay_canonical(self):
        proposal = self.canonical()
        for role in ('proposer', 'checker'):
            canonical = self.canonical(role, proposal)
            wire = encoded_rows(canonical)
            body = stream_tests.Body(stream_tests.events(wire))
            result, receipt, sent, client, factory, reserve = self.invoke(body,
                role=role, proposal=proposal, choice=True)
            self.assertEqual(result, canonical)
            self.assertEqual(receipt.state, 'succeeded')
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0], preparation.provider_request(self.inventory, role, self.live(), proposal))
            self.assertIs(sent[0]['stream'], True)
            self.assertEqual(factory.call_args.kwargs['max_retries'], 0)
            self.assertEqual(reserve.call_count, 1)
            self.assertEqual(receipt.usage, {'input_tokens':10, 'output_tokens':20,
                'cached_input_tokens':2, 'cache_creation_tokens':1})
            self.assertIsNotNone(receipt.computed_cost)
            self.assertTrue(client.is_closed())
            self.assertTrue(body.closed)
            raw = json.loads(private_path(receipt.response_path).read_bytes())
            self.assertEqual(raw['response_transport'], codec.COMPACT_TRANSPORT)
            self.assertEqual(raw['request_envelope_sha256'], digest(sent[0]))
            self.assertEqual(json.loads(''.join(b.get('text', '') for b in raw['response']['content'])), wire)
            self.assertEqual(preparation.read_retained_role(receipt, 'live'), canonical)

    def test_actual_sdk_malformed_compact_rows_retain_known_cost_raw_failure_without_retry(self):
        wire = encoded_rows(self.canonical())
        contract = next(codec.contracts(wire))
        rows = json.loads(contract['components'])
        rows[0].pop()
        contract['components'] = json.dumps(rows)
        body = stream_tests.Body(stream_tests.events(wire))
        result, receipt, sent, client, factory, reserve = self.invoke(body, choice=True)
        self.assertIsInstance(result, DocumentError)
        self.assertEqual(receipt.state, 'failed')
        self.assertIsNotNone(receipt.computed_cost)
        self.assertEqual(len(sent), 1)
        self.assertEqual(reserve.call_count, 1)
        self.assertEqual(factory.call_args.kwargs['max_retries'], 0)
        self.assertTrue(body.closed)
        self.assertTrue(client.is_closed())
        raw = json.loads(private_path(receipt.response_path).read_bytes())
        self.assertEqual(json.loads(''.join(b.get('text', '') for b in raw['response']['content'])), wire)
        with self.assertRaises(DocumentError):
            preparation.read_retained_role(receipt, 'live')

