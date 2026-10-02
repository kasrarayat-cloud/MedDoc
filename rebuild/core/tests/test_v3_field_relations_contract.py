"""The ordinary-relations contract (v3: positional, self-naming) at its request/response boundary, offline: the
per-request schema reaches the provider unchanged and holds a fixed number of named properties whatever the request,
the strict parser proves the coverage the grammar cannot state and refuses every malformed answer whole, a good one
converts into the unchanged internal selections, v1 and v2 artifacts refuse at their own gates (a stored v2 record stays
readable), and the veto controls run through the whole reader with synthetic model outputs. No provider, no network, no
database."""
import copy
import json
from types import SimpleNamespace

from anthropic import transform_schema
from django.core import signing
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from core.jobs import NoProviderRequest
from .test_v3_field_relations import answer_of, from_keyed, keyed, relate, relation_body, relation_wire, wired
from .test_v3_ordinary_notes import LIVE, field

RELATIONS = dict(LIVE, V3_FIELD_RELATIONS=True, V3_HISTORY_CONTEXT=False, V3_GENERATION_BATCHES=False)
#: The N02 frozen twin's shape: two statements, three questions (one 'Other:' twice in different sections).
N02_NOTES = ('The patient describes the pain as a tight band around her head. '
             'She notices flashing zigzag lines before the headache begins.')


def n02_fields():
    first, second = field('v3_1', 'Other:'), field('v3_2', 'Other:')
    first['context'] = 'Current headache > What does your headache usually feel like?'
    second['context'] = 'Current headache > Which symptoms occur before the headache begins?'
    return [first, second, field('v3_3', 'Additional comments')]


def response(text, *, model=g.SONNET_5, stop_reason='end_turn'):
    return SimpleNamespace(model=model, stop_reason=stop_reason, content=[SimpleNamespace(type='text', text=text)])


def raw_result(notes, fields, text):
    """What generate() retains for a single-request answer (the same keys, the same asked fields)."""
    asked, context, _ = g.v3_generation_fields(fields)
    return {'anthropic_response': response(text), 'ordinary_field_contract': r.CONTRACT, 'notes': notes,
            'fields': asked, 'full_catalogue': fields, 'context_labels': context}


def adopted(notes, fields, body):
    """The whole single-request reader (validated: parse -> records -> validate_selections -> v3_adopted)."""
    answers = r.validated(raw_result(notes, fields, body if isinstance(body, str) else json.dumps(body)))
    return {k: (v['status'], v['text']) for k, v in answers.items()}


#: Every named property the v3 schema may carry, whatever the request (the bounded vocabulary).
V3_NAMES = {'fields', 'key', 'unit_ids', 'conflict', 'option_ids', 'context', 'unit', 'relation'}


def named_properties(node):
    """Every property name written anywhere in a schema ($defs included), with repeats."""
    names = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == 'properties' and isinstance(value, dict):
                names.extend(value)
                for member in value.values():
                    names.extend(named_properties(member))
            elif key not in ('enum', 'required'):
                names.extend(named_properties(value))
    elif isinstance(node, list):
        for value in node:
            names.extend(named_properties(value))
    return names


@override_settings(**RELATIONS)
class PositionalSchema(SimpleTestCase):
    def shapes(self):
        choice = field('smoking', 'Smoker', 'choice', ['Yes', 'No'])
        yield 'N02', N02_NOTES, n02_fields()
        yield 'choice and text', 'The patient does not smoke. The patient walks daily.', [choice, field('f', 'Activity')]
        # (10 x 14: v2's schema for it was refused live as too complex; 10 x 30 and 1 x 400 fit one bounded v3 answer,
        # 10 x 60 no longer does - its positional body exceeds 20,000 bytes and goes to the relations field batches)
        for n_fields, n_units in ((1, 1), (3, 2), (10, 14), (10, 30), (1, 400)):
            notes = ' '.join(f'The patient reports symptom {i}.' for i in range(n_units))
            yield f'{n_fields}x{n_units}', notes, [field(f'q{i}', f'Question {i}') for i in range(n_fields)]

    def test_the_per_request_schema_is_closed_and_reaches_the_provider_unchanged(self):
        for name, notes, fields in self.shapes():
            with self.subTest(shape=name):
                compiled = r.compile_request(notes, fields, g.configuration(fields))
                asked, units = compiled['asked'], compiled['units']
                schema = r.response_schema(asked, units)
                self.assertEqual(transform_schema(copy.deepcopy(schema)), schema)
                self.assertEqual(compiled['wire']['output_config']['format']['schema'], schema)
                ids = [u['id'] for u in units]
                defs = schema['$defs']
                own = [o['id'] for f in asked for o in r.options(f)]
                self.assertEqual(defs['Relation'], {'type': 'string', 'enum': list(r.RELATIONS)})
                self.assertEqual(defs['UnitId'], {'type': 'integer', 'enum': ids})
                self.assertEqual(defs['FieldKey'], {'type': 'string', 'enum': [f['key'] for f in asked]})
                self.assertEqual(defs['Relates'], {'type': 'object', 'properties': {
                    'unit': {'$ref': '#/$defs/UnitId'}, 'relation': {'$ref': '#/$defs/Relation'}},
                    'required': ['unit', 'relation'], 'additionalProperties': False})
                answer = defs['Answer']
                members = ['key', 'unit_ids', 'conflict'] + (['option_ids'] if own else []) + ['context']
                self.assertEqual((list(answer['properties']), answer['required'], answer['additionalProperties']),
                                 (members, members, False))
                self.assertEqual(answer['properties']['context'], {'type': 'array', 'items': {'$ref': '#/$defs/Relates'}})
                self.assertEqual(answer['properties']['unit_ids'], {'type': 'array', 'items': {'$ref': '#/$defs/UnitId'}})
                if own:
                    self.assertEqual(defs['OptionId'], {'type': 'string', 'enum': own})
                else:
                    self.assertNotIn('OptionId', defs)
                self.assertEqual((schema['required'], schema['additionalProperties']), (['fields'], False))
                self.assertEqual(schema['properties']['fields'], {'type': 'array', 'items': {'$ref': '#/$defs/Answer'}})
                # (no length or bound keyword anywhere: the grammar cannot carry one, the parser proves it)
                text = json.dumps(schema)
                for keyword in ('minItems', 'maxItems', 'minimum', 'maximum', 'description', 'pattern'):
                    self.assertNotIn(f'"{keyword}"', text)

    def test_the_named_properties_are_bounded_whatever_the_fields_and_units(self):
        # (live 2026-10-02: v2's 14 units x 10 fields was refused as too complex to compile; v2 wrote one named member
        # per unit per field. v3 writes the same few names whatever the request; only enum VALUES grow, once each.)
        seen = set()
        for n_fields, n_units in ((1, 1), (10, 10), (10, 14), (100, 80)):
            fields = [field(f'q{i}', f'Question {i}', 'choice', ['A', 'B']) if i % 5 == 0 else field(f'q{i}', f'Question {i}')
                      for i in range(n_fields)]
            units = [{'id': i} for i in range(1, n_units + 1)]
            schema = r.response_schema(fields, units)
            names = named_properties(schema)
            self.assertLessEqual(len(names), 8, (n_fields, n_units))
            self.assertLessEqual(set(names), V3_NAMES)
            self.assertEqual(sum(1 for name in names if name == 'relation'), 1)
            seen.add(len(names))
            # (and v2's shape for the refused live case wrote 140 per-unit members: this is what moved)
            self.assertLessEqual(max(len(d.get('properties', {})) for d in schema['$defs'].values()), 5)
        self.assertEqual(len(seen), 1)

    def test_the_response_bound_is_the_positional_worst_case_body(self):
        notes = 'The patient does not smoke. The patient walks daily.'
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No']), field('f', 'Activity')]
        asked, context, _ = g.v3_generation_fields(fields)
        units = g.source_units(notes, asked, context_labels=context)[0]
        entries = [{'unit': 1, 'relation': 'independent'}, {'unit': 2, 'relation': 'independent'}]
        worst = {'fields': [{'key': 'smoking', 'unit_ids': [1, 2], 'conflict': False,
                             'option_ids': ['smoking:0', 'smoking:1'], 'context': entries},
                            {'key': 'f', 'unit_ids': [1, 2], 'conflict': False, 'option_ids': [], 'context': entries}]}
        self.assertEqual(r.response_bound(asked, units), len(json.dumps(worst).encode()))
        self.assertTrue(all(len(json.dumps(rel)) <= len(json.dumps('independent')) for rel in r.RELATIONS))
        # (no option field: no option_ids member at all)
        text = [field('f', 'Activity')]
        asked, context, _ = g.v3_generation_fields(text)
        self.assertEqual(r.response_bound(asked, units), len(json.dumps(
            {'fields': [{'key': 'f', 'unit_ids': [1, 2], 'conflict': False, 'context': entries}]}).encode()))
        # (the bound covers a real answer: the longest valid answer to this request is never above it)
        good = relation_wire(notes, fields, {'smoking': [notes.split('. ')[0] + '.'], 'f': ['The patient walks daily.']},
                             choices={'smoking': ['smoking:0', 'smoking:1']})
        self.assertLessEqual(len(json.dumps(good).encode()), r.response_bound(g.v3_generation_fields(fields)[0], units))

    def test_a_schema_the_sdk_would_change_refuses_before_any_request(self):
        # (were transform_schema ever to move a constraint into a description, the closed schema would not be what the
        # provider enforces: refused at the quote, before any hold)
        from unittest.mock import patch
        fields = n02_fields()
        with patch('anthropic.transform_schema', side_effect=lambda schema: {**schema, 'description': '{minItems: 2}'}):
            with self.assertRaisesMessage(ValidationError, 'would not reach the provider unchanged'):
                r.compile_request(N02_NOTES, fields, g.configuration(fields))
            with self.assertRaises(ValidationError):
                g.maximum_cost(N02_NOTES, fields, g.configuration(fields))

    def test_no_source_unit_refuses_before_any_request(self):
        # (every non-blank note measured yields a unit; the guard keeps an empty enum from ever being sent)
        from unittest.mock import patch
        with patch.object(g, 'source_units', return_value=([], None)), self.assertRaises(ValidationError):
            r.compile_request('History:', [field('f', 'History')], g.configuration())


@override_settings(**RELATIONS)
class StrictParser(SimpleTestCase):
    def setUp(self):
        self.fields = n02_fields()
        self.good = relation_wire(N02_NOTES, self.fields, {'v3_1': [N02_NOTES.split('. ')[0] + '.'],
                                                            'v3_2': [N02_NOTES.split('. ')[1]]})
        self.text = json.dumps(self.good)

    def units(self):
        asked, context, _ = g.v3_generation_fields(self.fields)
        return asked, g.source_units(N02_NOTES, asked, context_labels=context)[0]

    def edited(self, edit):
        body = copy.deepcopy(self.good)
        edit(body)
        return json.dumps(body)

    def test_a_correct_positional_answer_is_adopted_through_the_whole_reader(self):
        self.assertEqual(adopted(N02_NOTES, self.fields, self.text),
                         {'v3_1': ('supported', 'The patient describes the pain as a tight band around her head.'),
                          'v3_2': ('conflict', ''), 'v3_3': ('missing', '')})

    def test_fields_in_any_order_convert_to_the_requested_order(self):
        asked, units = self.units()
        body = copy.deepcopy(self.good)
        relate(body, 'v3_1', 2, 'contrary')
        body['fields'] = list(reversed(body['fields']))
        parsed = r.parse(json.dumps(body), asked, units)
        self.assertIsInstance(parsed, r.FieldSelections)
        self.assertEqual([f.key for f in parsed.fields], ['v3_1', 'v3_2', 'v3_3'])
        self.assertEqual(parsed.fields[0].context, ['answer', 'contrary'])
        self.assertEqual(parsed.fields[0].option_ids, [])

    def malformed(self):
        def pop_entry(index):
            return lambda b: answer_of(b, 'v3_3')['context'].pop(index)

        def shift(b):
            # the context names units 2 and 1 in that order: complete, but not the offered order
            answer_of(b, 'v3_1')['context'].reverse()

        def shifted_relations(b):
            # entry i carries entry i+1's unit: a one-place shift that keeps the length
            context = answer_of(b, 'v3_1')['context']
            for entry, unit in zip(context, [2, 2]):
                entry['unit'] = unit

        keyed_v2 = keyed(relation_body(N02_NOTES, self.fields, {'v3_1': [N02_NOTES.split('. ')[0] + '.']}),
                         *self.units())
        v1_list = {'fields': [{'key': item['key'], 'unit_ids': item['unit_ids'], 'conflict': item['conflict'],
                               'option_ids': [], 'context': [entry['relation'] for entry in item['context']]}
                              for item in self.good['fields']]}
        attempt_017 = {'fields': [{'key': 'v3_1', 'unit_ids': [1], 'conflict': False, 'option_ids': [], 'context': ['answer']},
                                  {'key': 'v3_2', 'unit_ids': [2], 'conflict': False, 'option_ids': [], 'context': ['answer']},
                                  {'key': 'v3_3', 'unit_ids': [], 'conflict': False, 'option_ids': [], 'context': []}]}
        # (attempt 017's v1 failure, in this wire: one context entry per SELECTED unit, each correctly named)
        attempt_017_v3 = {'fields': [{'key': 'v3_1', 'unit_ids': [1], 'conflict': False,
                                      'context': [{'unit': 1, 'relation': 'answer'}]},
                                     {'key': 'v3_2', 'unit_ids': [2], 'conflict': False,
                                      'context': [{'unit': 2, 'relation': 'answer'}]},
                                     {'key': 'v3_3', 'unit_ids': [], 'conflict': False, 'context': []}]}
        first = self.text.index('{"key": "v3_1"')
        return {
            'the v2 keyed shape': json.dumps(keyed_v2),
            'the retained v2 attempt 020 text verbatim': ATTEMPT_020_TEXT,
            'the v1 list shape': json.dumps(v1_list),
            'attempt 017 as returned (one context entry for two units)': json.dumps(attempt_017),
            'attempt 017 in this wire (one entry per selected unit)': json.dumps(attempt_017_v3),
            'not JSON': self.text[:-1],
            'two JSON values': self.text + ' {}',
            'a top-level array': '[' + self.text + ']',
            'an extra top-level member': self.edited(lambda b: b.update(note='x')),
            'a duplicate top-level member': '{"fields": [], ' + self.text[1:],
            'fields as an object': self.edited(lambda b: b.update(fields={i['key']: i for i in b['fields']})),
            'a missing field': self.edited(lambda b: b['fields'].pop()),
            'a repeated field': self.edited(lambda b: b['fields'].append(copy.deepcopy(b['fields'][0]))),
            'a repeated field in place of another': self.edited(lambda b: b['fields'].__setitem__(2, copy.deepcopy(b['fields'][0]))),
            'an extra field': self.edited(lambda b: b['fields'].append({**copy.deepcopy(b['fields'][2]), 'key': 'v3_9'})),
            'an unknown key in place of a requested one': self.edited(lambda b: b['fields'][2].update(key='v3_9')),
            'a missing key': self.edited(lambda b: b['fields'][2].pop('key')),
            'a numeric key': self.edited(lambda b: b['fields'][2].update(key=3)),
            'a key that is a list': self.edited(lambda b: b['fields'][2].update(key=['v3_3'])),
            'a key that is an object': self.edited(lambda b: b['fields'][2].update(key={'v3_3': 1})),
            'a field that is not an object': self.edited(lambda b: b['fields'].__setitem__(2, 'v3_3')),
            'a duplicate member inside a field': self.text[:first] + '{"key": "v3_2", ' + self.text[first + 1:],
            'a duplicate member inside a context entry': self.text.replace('{"unit": 1, "relation": "answer"}',
                                                                            '{"unit": 1, "unit": 1, "relation": "answer"}', 1),
            'a short context (an entry dropped)': self.edited(pop_entry(0)),
            'a short context (the last entry dropped)': self.edited(pop_entry(-1)),
            'an empty context': self.edited(lambda b: answer_of(b, 'v3_2').update(context=[])),
            'a long context (an extra unit)': self.edited(
                lambda b: answer_of(b, 'v3_1')['context'].append({'unit': 3, 'relation': 'independent'})),
            'a long context (a repeated unit)': self.edited(
                lambda b: answer_of(b, 'v3_1')['context'].append({'unit': 2, 'relation': 'independent'})),
            'a repeated unit in place of another (the length kept)': self.edited(shifted_relations),
            'the units out of the offered order': self.edited(shift),
            'a unit named by a string': self.edited(lambda b: answer_of(b, 'v3_1')['context'][0].update(unit='1')),
            'a unit named by true': self.edited(lambda b: answer_of(b, 'v3_1')['context'][0].update(unit=True)),
            'a unit named by a float': self.text.replace('{"unit": 1, "relation": "answer"}',
                                                           '{"unit": 1.0, "relation": "answer"}', 1),
            'an entry without its unit': self.edited(lambda b: answer_of(b, 'v3_1')['context'][0].pop('unit')),
            'an entry without its relation': self.edited(lambda b: answer_of(b, 'v3_1')['context'][0].pop('relation')),
            'an entry with an extra member': self.edited(lambda b: answer_of(b, 'v3_1')['context'][0].update(note='x')),
            'a bare relation in place of an entry': self.edited(
                lambda b: answer_of(b, 'v3_1')['context'].__setitem__(0, 'answer')),
            'context as an object': self.edited(lambda b: answer_of(b, 'v3_1').update(context={'1': 'answer', '2': 'independent'})),
            'a relation outside the five': self.edited(lambda b: relate(b, 'v3_1', 2, 'unrelated')),
            'a relation that is not a string': self.edited(lambda b: relate(b, 'v3_1', 2, None)),
            'a repeated unit ID': self.edited(lambda b: answer_of(b, 'v3_1').update(unit_ids=[1, 1])),
            'true as a unit ID': self.edited(lambda b: answer_of(b, 'v3_1').update(unit_ids=[True])),
            'a float unit ID': self.text.replace('"unit_ids": [1]', '"unit_ids": [1.0]', 1),
            'a string unit ID': self.edited(lambda b: answer_of(b, 'v3_1').update(unit_ids=['1'])),
            'an unknown unit ID': self.edited(lambda b: answer_of(b, 'v3_1').update(unit_ids=[9])),
            'NaN': self.text.replace('"unit_ids": [1]', '"unit_ids": [NaN]', 1),
            'Infinity': self.text.replace('"unit_ids": [1]', '"unit_ids": [Infinity]', 1),
            '-Infinity': self.text.replace('"unit_ids": [1]', '"unit_ids": [-Infinity]', 1),
            'a numeric conflict': self.edited(lambda b: answer_of(b, 'v3_1').update(conflict=0)),
            'a string conflict': self.edited(lambda b: answer_of(b, 'v3_1').update(conflict='false')),
            'a missing conflict': self.edited(lambda b: answer_of(b, 'v3_1').pop('conflict')),
            'option_ids in a request without option fields': self.edited(lambda b: answer_of(b, 'v3_1').update(option_ids=[])),
        }

    def test_the_refusal_names_what_is_malformed(self):
        asked, units = self.units()
        for name, edit, reason in (
                ('fields as an object', lambda b: b.update(fields={i['key']: i for i in b['fields']}),
                 'the top level is not exactly one fields list'),
                ('a repeated field', lambda b: b['fields'].append(copy.deepcopy(b['fields'][0])),
                 'the fields are not exactly the requested keys, once each'),
                ('a short context', lambda b: answer_of(b, 'v3_1')['context'].pop(), 'v3_1 context'),
                ('a unit named by true', lambda b: answer_of(b, 'v3_1')['context'][0].update(unit=True), 'v3_1 context'),
                ('an extra member', lambda b: answer_of(b, 'v3_2').update(note='x'), 'v3_2 does not carry exactly its members')):
            with self.subTest(name=name), self.assertRaises(ValidationError) as caught:
                r.parse(self.edited(edit), asked, units)
            self.assertIn(f'({reason})', caught.exception.messages[0])

    def test_every_malformed_answer_is_refused_before_any_record(self):
        asked, units = self.units()
        for name, text in self.malformed().items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError) as caught:
                    r.parse(text, asked, units)
                self.assertIn(r.MALFORMED, caught.exception.messages[0])
                with self.assertRaises(ValidationError):
                    r.validated(raw_result(N02_NOTES, self.fields, text))

    def test_option_fields_are_closed_to_their_own_options(self):
        notes = 'The patient does not smoke.'
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No']), field('other', 'Other', 'choice', ['A', 'B']),
                  field('comment', 'Comment')]
        good = relation_wire(notes, fields, {'smoking': [notes]}, choices={'smoking': ['smoking:1']})
        self.assertEqual(adopted(notes, fields, good)['smoking'], ('supported', 'No'))
        self.assertEqual(answer_of(good, 'comment')['option_ids'], [])      # (every field carries the member)
        for name, edit in (('a missing option_ids', lambda b: answer_of(b, 'smoking').pop('option_ids')),
                           ('a missing option_ids on a text field', lambda b: answer_of(b, 'comment').pop('option_ids')),
                           ('an option on a text field', lambda b: answer_of(b, 'comment').update(option_ids=['smoking:1'])),
                           ('an unknown option', lambda b: answer_of(b, 'smoking').update(option_ids=['smoking:7'])),
                           ('another field\'s option', lambda b: answer_of(b, 'smoking').update(option_ids=['other:1'])),
                           ('a repeated option', lambda b: answer_of(b, 'smoking').update(option_ids=['smoking:1'] * 2)),
                           ('a numeric option', lambda b: answer_of(b, 'smoking').update(option_ids=[1]))):
            body = copy.deepcopy(good); edit(body)
            with self.subTest(name=name), self.assertRaises(ValidationError):
                adopted(notes, fields, body)
            # (the PARSER itself refuses it, whole: records() refusing it later is not the only guard - the stage
            # runner's raw_selection reads parse() alone, and would otherwise drop the foreign option silently)
            asked, context, _ = g.v3_generation_fields(fields)
            units = g.source_units(notes, asked, context_labels=context)[0]
            with self.subTest(name=name, reader='parse'), self.assertRaises(ValidationError) as caught:
                r.parse(json.dumps(body), asked, units)
            self.assertIn(r.MALFORMED, caught.exception.messages[0])

    def test_answers_that_parse_but_disagree_with_their_selection_hold_that_field_only(self):
        # (was: refused by records() for the WHOLE response, which failed the job — live attempt 020. A disagreement
        # is the model's own statement about ONE field, not malformed output: that field is held, nothing else moves.)
        good = adopted(N02_NOTES, self.fields, self.text)
        for name, key, edit in (('an answer relation on an unselected unit', 'v3_3',
                                 lambda b: relate(b, 'v3_3', 1, 'answer')),
                                ('a selected unit marked independent', 'v3_1',
                                 lambda b: relate(b, 'v3_1', 1, 'independent'))):
            with self.subTest(name=name):
                got = adopted(N02_NOTES, self.fields, self.edited(edit))
                self.assertEqual(got[key], ('conflict', ''))
                self.assertEqual({k: v for k, v in got.items() if k != key}, {k: v for k, v in good.items() if k != key})

    def test_a_veto_on_another_unit_holds_the_answer(self):
        for relation in ('contrary', 'unresolved'):
            with self.subTest(relation=relation):
                body = self.edited(lambda b: relate(b, 'v3_1', 2, relation))
                self.assertEqual(adopted(N02_NOTES, self.fields, body)['v3_1'], ('conflict', ''))
        body = self.edited(lambda b: answer_of(b, 'v3_1').update(conflict=True))
        self.assertEqual(adopted(N02_NOTES, self.fields, body)['v3_1'], ('conflict', ''))

    def test_a_shifted_context_is_never_read_against_the_wrong_unit(self):
        # The hazard a bare positional list carries (v1's shape): a one-place shift keeps the length, so 'contrary' for
        # unit 2 read as unit 1's. Here every entry names its unit; any shift, swap or relabel is refused whole.
        asked, units = self.units()
        body = copy.deepcopy(self.good)
        relate(body, 'v3_1', 2, 'contrary')
        self.assertEqual(r.parse(json.dumps(body), asked, units).fields[0].context, ['answer', 'contrary'])
        for name, context in (('swapped', [{'unit': 2, 'relation': 'contrary'}, {'unit': 1, 'relation': 'answer'}]),
                              ('relabelled', [{'unit': 2, 'relation': 'answer'}, {'unit': 1, 'relation': 'contrary'}]),
                              ('shifted', [{'unit': 2, 'relation': 'answer'}, {'unit': 2, 'relation': 'contrary'}])):
            answer_of(body, 'v3_1')['context'] = context
            with self.subTest(name=name), self.assertRaises(ValidationError):
                r.parse(json.dumps(body), asked, units)

    def test_the_parser_is_the_only_reader_of_the_wire(self):
        # the internal selections refuse the wire body, and the parser refuses the internal list: two shapes
        with self.assertRaises(ValueError):
            r.FieldSelections.model_validate_json(self.text)
        asked, units = self.units()
        internal = relation_body(N02_NOTES, self.fields, {})
        with self.assertRaises(ValidationError):
            r.parse(json.dumps(internal), asked, units)
        self.assertEqual(answer_of(json.loads(json.dumps(wired(internal, asked, units))), 'v3_3')['context'],
                         [{'unit': 1, 'relation': 'independent'}, {'unit': 2, 'relation': 'independent'}])


#: The text block of live attempt 020's retained provider response (case N13 on the field-relations path), verbatim:
#: .runtime/v1-sonnet5-campaign/evidence/020/provider-response.body, sha256 4bedab2b5487cb67…c451b6 in that attempt's
#: evidence manifest. Each field has conflict true and its SELECTED units marked 'contrary': the model reporting that
#: the statements it selected contradict each other. records() refused the whole response, so the job failed.
ATTEMPT_020_TEXT = ('{"fields":{"v3_1":{"unit_ids":[1,2],"conflict":true,"context":{"1":"contrary","2":"contrary",'
                    '"3":"independent","4":"independent"}},"v3_2":{"unit_ids":[3,4],"conflict":true,"context":{"1":'
                    '"independent","2":"independent","3":"contrary","4":"contrary"}}}}')


def frozen_case(case_id):
    """(notes, form fields) of one frozen ordinary-notes case, read from the frozen diagnostics (never changed here)."""
    from pathlib import Path
    notes = Path(__file__).resolve().parents[3] / 'docs' / 'rebuild' / 'v1' / 'sonnet5-campaign' / 'diagnostics' / 'notes'
    cases = json.loads((notes / 'cases.json').read_text())
    case = next(c for c in cases['cases'] if c['id'] == case_id)
    return case['notes'], cases['forms'][case['form']]['fields']


#: Three fields each adopted from its own paragraph when the answer agrees with its selection (the clean control).
CLEAN_NOTES = 'The patient is not allergic to penicillin.\n\nThe patient walks every day.\n\nThe patient does not smoke.'


def clean_fields():
    return [field('allergies', 'Allergies'), field('activity', 'Activity'),
            field('smoking', 'Smoker', 'choice', ['Yes', 'No'])]


CLEAN_PICKS = {'allergies': ['The patient is not allergic to penicillin.'], 'activity': ['The patient walks every day.'],
               'smoking': ['The patient does not smoke.']}


@override_settings(**RELATIONS)
class DisagreementHolds(SimpleTestCase):
    """A field whose selection disagrees with its own relations (a selected unit that is not answer/qualifier, or an
    answer unit that is not selected) is HELD as that field's conflict and never adopted, while every other field is
    read exactly as before and structural output still refuses the whole response. Generation adoption, the page, save
    and finalization agree because every one of them reads the stored record with v3_field_relations.read()."""

    def clean(self):
        fields = clean_fields()
        wire = relation_wire(CLEAN_NOTES, fields, CLEAN_PICKS, choices={'smoking': ['smoking:1']})
        return fields, wire

    def units(self, notes, fields):
        asked, context, _ = g.v3_generation_fields(fields)
        return g.source_units(notes, asked, context_labels=context)[0]

    def test_the_retained_live_attempt_020_holds_both_fields_and_the_job_succeeds(self):
        notes, fields = frozen_case('N13')
        # (the retained v2 body, translated into this contract's wire: the same selections and relations)
        answers = r.validated(raw_result(notes, fields, from_keyed(ATTEMPT_020_TEXT)))   # (before: ValidationError 'disagree')
        self.assertEqual({k: (v['status'], v['text']) for k, v in answers.items()},
                         {'v3_1': ('conflict', ''), 'v3_2': ('conflict', '')})
        units = self.units(notes, fields)
        wire = json.loads(ATTEMPT_020_TEXT)['fields']
        for key, answer in answers.items():
            with self.subTest(key=key):
                # the record keeps the model's own selection, verbatim; nothing about it was rewritten
                stored = signing.loads(answer['ordinary_relation'], salt=r.SALT)['selection']
                self.assertEqual(stored, {'key': key, 'unit_ids': wire[key]['unit_ids'], 'conflict': True,
                                          'option_ids': [],
                                          'context': [wire[key]['context'][str(u['id'])] for u in units]})
                # a forged `supported` copy that keeps this record is held on the page, save and finalize reader
                chosen = [u for u in units if u['id'] in wire[key]['unit_ids']]
                forged = {**answer, 'status': 'supported', 'text': '\n'.join(u['quote'] for u in chosen),
                          'evidence': [{k: u[k] for k in ('quote', 'start', 'end')} for u in chosen]}
                forged.pop('held_candidate', None)
                label = next(f['label'] for f in fields if f['key'] == key)
                self.assertIn(label, g.governed_decisions(notes, fields, {**answers, key: forged}))

    def disagreements(self, key, unit, other):
        """(name, edit of the v3 wire) — every way ONE field's selection can disagree with its relations. `unit` is
        the field's selected unit ID, `other` a unit it did not select."""
        u, o = unit, other

        def put(**changes):
            def edit(body):
                entry = answer_of(body, key)
                for name, value in changes.items():
                    if name == 'context':
                        for which, relation in value.items():
                            relate(body, key, which, relation)
                    else:
                        entry[name] = value
            return edit
        return [('the selected unit marked contrary, conflict true (attempt 020)', put(context={u: 'contrary'}, conflict=True)),
                ('the selected unit marked contrary, conflict false', put(context={u: 'contrary'})),
                ('the selected unit marked unresolved', put(context={u: 'unresolved'})),
                ('the selected unit marked independent', put(context={u: 'independent'})),
                ('an answer relation on a unit it did not select', put(context={o: 'answer'})),
                ('an answer relation and nothing selected', put(unit_ids=[], context={u: 'answer'},
                                                                **({'option_ids': []} if key == 'smoking' else {})))]

    def test_one_disagreeing_field_is_held_and_every_other_field_reads_as_before(self):
        fields, wire = self.clean()
        good = adopted(CLEAN_NOTES, fields, wire)
        self.assertEqual(good, {'allergies': ('supported', 'The patient is not allergic to penicillin.'),
                                'activity': ('supported', 'The patient walks every day.'),
                                'smoking': ('supported', 'No')})
        units = {u['quote']: u['id'] for u in self.units(CLEAN_NOTES, fields)}
        for key in ('allergies', 'activity', 'smoking'):
            unit = units[CLEAN_PICKS[key][0]]
            other = next(i for i in units.values() if i != unit)
            for name, edit in self.disagreements(key, unit, other):
                with self.subTest(field=key, disagreement=name):
                    body = copy.deepcopy(wire); edit(body)
                    got = adopted(CLEAN_NOTES, fields, body)
                    self.assertEqual(got[key], ('conflict', ''))
                    self.assertEqual({k: v for k, v in got.items() if k != key},
                                     {k: v for k, v in good.items() if k != key})

    def test_the_held_record_is_the_models_selection_and_no_reader_adopts_it(self):
        fields, wire = self.clean()
        units = self.units(CLEAN_NOTES, fields)
        chosen = units[0]
        body = copy.deepcopy(wire)
        relate(body, 'allergies', 1, 'independent')                       # (a selected unit the model calls independent)
        answers = r.validated(raw_result(CLEAN_NOTES, fields, json.dumps(body)))
        held = answers['allergies']
        self.assertEqual((held['status'], held['text']), ('conflict', ''))
        record = signing.loads(held['ordinary_relation'], salt=r.SALT)
        self.assertEqual(record['selection'], {'key': 'allergies', 'unit_ids': [1], 'conflict': False, 'option_ids': [],
                                               'context': ['independent', 'independent', 'independent']})
        evidence = [{k: chosen[k] for k in ('quote', 'start', 'end')}]
        reading = g.governance_for(CLEAN_NOTES, fields)[11]['preceding']
        read = r.read(reading, 'Allergies', evidence, held['ordinary_relation'], text=chosen['quote'], field_key='allergies')
        self.assertFalse(read['valid'])
        self.assertTrue(read['warnings'])
        # the same stored answer, forged `supported` with that record, is governed (page, save and finalization); the
        # agreeing record of the same selection is not (the control that the refusal is the disagreement)
        forged = {**held, 'status': 'supported', 'text': chosen['quote'], 'evidence': evidence}
        forged.pop('held_candidate', None)
        self.assertEqual(g.governed_decisions(CLEAN_NOTES, fields, {**answers, 'allergies': forged}), ['Allergies'])
        clean = r.validated(raw_result(CLEAN_NOTES, fields, json.dumps(wire)))
        self.assertEqual(clean['allergies']['status'], 'supported')
        self.assertEqual(g.governed_decisions(CLEAN_NOTES, fields, clean), [])
        self.assertEqual(g.governed_decisions(CLEAN_NOTES, fields, {**answers, 'allergies': clean['allergies']}), [])

    def test_structural_output_still_refuses_the_whole_response(self):
        fields, wire = self.clean()
        asked, context, _ = g.v3_generation_fields(fields)
        units = self.units(CLEAN_NOTES, fields)
        internal = r.parse(json.dumps(wire), asked, units).model_dump()
        for name, edit in (('a missing field', lambda b: b['fields'].pop()),
                           ('a duplicate field', lambda b: b['fields'].append(copy.deepcopy(b['fields'][0]))),
                           ('an unknown field', lambda b: b['fields'][0].update(key='elsewhere')),
                           ('a short context', lambda b: b['fields'][0]['context'].pop()),
                           ('a long context', lambda b: b['fields'][0]['context'].append('independent')),
                           ('an unknown unit', lambda b: b['fields'][0].update(unit_ids=[9])),
                           ('a repeated unit', lambda b: b['fields'][0].update(unit_ids=[1, 1])),
                           ('another field\'s option', lambda b: b['fields'][0].update(option_ids=['smoking:1'])),
                           ('a repeated option', lambda b: b['fields'][2].update(option_ids=['smoking:1'] * 2))):
            body = copy.deepcopy(internal); edit(body)
            with self.subTest(name=name), self.assertRaises((ValueError, ValidationError)):
                r.records(CLEAN_NOTES, fields, context, units, r.FieldSelections.model_validate(body), g.SONNET_5)
        # and the parser's controls (StrictParser.malformed) still refuse before any record: a disagreement in
        # one field never excuses a malformed other field
        body = copy.deepcopy(wire)
        relate(body, 'allergies', 1, 'contrary')
        answer_of(body, 'activity')['unit_ids'] = [9]
        with self.assertRaises(ValidationError) as caught:
            r.validated(raw_result(CLEAN_NOTES, fields, json.dumps(body)))
        self.assertIn(r.MALFORMED, caught.exception.messages[0])


@override_settings(**RELATIONS)
class ClaimedUnitsCompete(SimpleTestCase):
    """A field's CLAIM on a statement is every unit it selected plus every unit its relations call its answer or a
    qualifier (v3_field_relations.claimed). What competes between two repeated questions, or two numbered slots, is the
    claim: a field that calls a statement its answer without selecting it (a disagreement, held since dfde4fc8) claims
    it exactly as if it had selected it, so the field that DID select it is held as it is when both select it.
    (Refutation of dfde4fc8, F1 and F2: the competitor exclusion and the numbered-slot hold read unit_ids only, so the
    selecting field was adopted beside the claim; 691e27d0 had refused the whole response.)"""
    NOTES = 'The patient reports flashing zigzag lines.'

    @staticmethod
    def entry(unit_ids, relation, conflict=False):
        return {'unit_ids': unit_ids, 'conflict': conflict, 'context': {'1': relation}}

    def respond(self, fields, notes, entries):
        """`entries`: {key: entry}, each entry's context keyed by unit ID (as this class wrote them for v2), sent in the v3
        wire (`from_keyed`: the same selections and relations)."""
        answers = r.validated(raw_result(notes, fields, from_keyed(json.dumps({'fields': entries}))))
        return answers, {k: (v['status'], v['text']) for k, v in answers.items()}

    def forged_is_governed(self, notes, fields, answers, key):
        """A forged `supported` copy of `key` that keeps its stored record: governed on the page, save and finalize."""
        asked, context, _ = g.v3_generation_fields(fields)
        units = g.source_units(notes, asked, context_labels=context)[0]
        selection = signing.loads(answers[key]['ordinary_relation'], salt=r.SALT)['selection']
        chosen = [u for u in units if u['id'] in selection['unit_ids']]
        forged = {**answers[key], 'status': 'supported', 'text': '\n'.join(u['quote'] for u in chosen),
                  'evidence': [{k: u[k] for k in ('quote', 'start', 'end')} for u in chosen]}
        forged.pop('held_candidate', None)
        label = next(f['label'] for f in fields if f['key'] == key)
        return label in g.governed_decisions(notes, fields, {**answers, key: forged})

    def test_claimed_is_the_selection_plus_every_answer_and_qualifier_relation(self):
        units = [{'id': i} for i in (1, 2, 3, 4, 5)]
        item = r.FieldSelection(key='f', unit_ids=[4, 2], conflict=False, option_ids=[],
                                context=['answer', 'contrary', 'qualifier', 'independent', 'unresolved'])
        self.assertEqual(r.claimed(item, units), [1, 2, 3, 4])      # (source order; a veto is not a claim)
        clean = r.FieldSelection(key='f', unit_ids=[2], conflict=False, option_ids=[],
                                 context=['independent', 'answer', 'independent', 'independent', 'contrary'])
        self.assertEqual(r.claimed(clean, units), [2])              # (an agreeing answer: the claim IS the selection)

    def test_a_repeated_question_that_claims_what_another_selected_holds_both(self):
        # refute-1:F1 input, verbatim: sensation selects unit 1; prodrome calls unit 1 its answer and selects nothing.
        from .test_v3_field_relations import repeated
        fields = repeated()
        for name, entries in (
                ('the sibling claims it as an answer (refute-1:F1)',
                 {'sensation': self.entry([1], 'answer'), 'prodrome': self.entry([], 'answer')}),
                ('the other direction', {'sensation': self.entry([], 'answer'), 'prodrome': self.entry([1], 'answer')}),
                ('the sibling claims it as a qualifier',
                 {'sensation': self.entry([1], 'answer'), 'prodrome': self.entry([], 'qualifier')}),
                ('the sibling claims it with conflict true',
                 {'sensation': self.entry([1], 'answer'), 'prodrome': self.entry([], 'answer', conflict=True)}),
                ('the consistent double selection (the rule the claim now follows)',
                 {'sensation': self.entry([1], 'answer'), 'prodrome': self.entry([1], 'answer')})):
            with self.subTest(name=name):
                answers, got = self.respond(fields, self.NOTES, entries)
                self.assertEqual(got, {'sensation': ('conflict', ''), 'prodrome': ('conflict', '')})
                # every record carries every competitor's CLAIM, and a forged supported copy of the question that
                # selected the statement (keeping its record) is governed on the page, save and finalize reader
                for key in ('sensation', 'prodrome'):
                    stored = signing.loads(answers[key]['ordinary_relation'], salt=r.SALT)
                    self.assertEqual(stored['competing_output'], {'sensation': [1], 'prodrome': [1]})
                    if entries[key]['unit_ids']:
                        self.assertTrue(self.forged_is_governed(self.NOTES, fields, answers, key))
        # controls: a sibling that does NOT claim the statement leaves the selecting question adopted (no false hold)
        for relation in ('independent', 'contrary', 'unresolved'):
            with self.subTest(sibling=relation):
                answers, got = self.respond(fields, self.NOTES, {'sensation': self.entry([1], 'answer'),
                                                                 'prodrome': self.entry([], relation)})
                self.assertEqual(got['sensation'], ('supported', self.NOTES))
                self.assertEqual(g.governed_decisions(self.NOTES, fields, answers), [])

    def test_two_comments_questions_one_claiming_what_the_other_selected_hold_both(self):
        # refute-2:F2 input, verbatim: two 'Comments:' questions under Diet and Exercise.
        first, second = field('v3_1', 'Comments:'), field('v3_2', 'Comments:')
        first['context'] = 'Diet > What does the patient eat?'
        second['context'] = 'Exercise > What exercise does the patient do?'
        fields = [first, second]
        notes = 'The patient eats vegetables every day.\n\nThe patient swims twice a week.'
        claim = {'unit_ids': [], 'conflict': False, 'context': {'1': 'independent', '2': 'answer'}}
        chosen = {'unit_ids': [2], 'conflict': False, 'context': {'1': 'independent', '2': 'answer'}}
        answers, got = self.respond(fields, notes, {'v3_1': chosen, 'v3_2': claim})
        self.assertEqual(got, {'v3_1': ('conflict', ''), 'v3_2': ('conflict', '')})  # (was: v3_1 supported, swims)
        self.assertTrue(self.forged_is_governed(notes, fields, answers, 'v3_1'))
        # control: the sibling calls the statement independent -> the selecting question is adopted
        answers, got = self.respond(fields, notes, {'v3_1': chosen, 'v3_2': {**claim, 'context': {'1': 'independent',
                                                                                             '2': 'independent'}}})
        self.assertEqual(got['v3_1'], ('supported', 'The patient swims twice a week.'))

    def test_a_numbered_slot_that_claims_what_another_slot_selected_holds_the_selecting_slot(self):
        # refute-1:F2 input, verbatim: 'Diagnosis - 1' calls the statement its answer and selects nothing,
        # 'Diagnosis - 2' selects it. The numbered-slot rule now reads the claim, as it reads a selection.
        fields = [field('d1', 'Diagnosis - 1'), field('d2', 'Diagnosis - 2')]
        notes = 'The patient has type 2 diabetes.'
        for name, entries, expected in (
                ('slot 1 claims, slot 2 selects (refute-1:F2)',
                 {'d1': self.entry([], 'answer'), 'd2': self.entry([1], 'answer')},
                 {'d1': ('conflict', ''), 'd2': ('conflict', '')}),
                ('slot 1 claims it as a qualifier, slot 2 selects',
                 {'d1': self.entry([], 'qualifier'), 'd2': self.entry([1], 'answer')},
                 {'d1': ('conflict', ''), 'd2': ('conflict', '')}),
                # a statement SELECTED by two questions holds both: the ordinary-note tightening's
                # one-statement-two-questions guard (integrated with fix/v1-notes-usefulness 1d22d0a5) is stricter than
                # the form-order numbered rule this branch was written against, and the stricter hold wins
                ('both select (two-question guard)', {'d1': self.entry([1], 'answer'), 'd2': self.entry([1], 'answer')},
                 {'d1': ('conflict', ''), 'd2': ('conflict', '')}),
                # an unselected claim is not a second selection: the earlier slot's selection stands, the later is held
                ('slot 1 selects, slot 2 claims', {'d1': self.entry([1], 'answer'), 'd2': self.entry([], 'answer')},
                 {'d1': ('supported', notes), 'd2': ('conflict', '')}),
                ('control: slot 1 calls it independent', {'d1': self.entry([], 'independent'),
                                                          'd2': self.entry([1], 'answer')},
                 {'d1': ('missing', ''), 'd2': ('supported', notes)})):
            with self.subTest(name=name):
                self.assertEqual(self.respond(fields, notes, entries)[1], expected)


@override_settings(**RELATIONS)
class VersionedArtifacts(SimpleTestCase):
    """v1 and v2 queued jobs, configurations and raw results refuse at their own gates; a v1 record is refused on every
    reader; a stored draft's v2 record is still read, under its own salt and binding, exactly as before."""

    def test_the_contract_and_salt_moved_and_the_pricing_version_with_them(self):
        self.assertEqual((r.CONTRACT, r.SALT), ('ordinary-field-relations-v3', 'quillmd.ordinary-field-relations.v3'))
        self.assertEqual(r.READABLE, {'ordinary-field-relations-v3': 'quillmd.ordinary-field-relations.v3',
                                      'ordinary-field-relations-v2': 'quillmd.ordinary-field-relations.v2'})
        config = g.configuration()
        self.assertEqual(config['ordinary_field_contract'], r.CONTRACT)
        with override_settings(V3_FIELD_RELATIONS=False):
            base_profile = g.configuration()['pricing_version']
        self.assertNotEqual(config['pricing_version'], base_profile)
        seen = []
        real = g.ordinary_pricing_version

        def capture(previous, contract):
            seen.append((previous, contract))
            return real(previous, contract)
        from unittest.mock import patch
        with patch.object(g, 'ordinary_pricing_version', side_effect=capture):
            again = g.configuration()
        (previous, contract), = seen
        self.assertEqual((again['pricing_version'], contract), (config['pricing_version'], r.CONTRACT))
        for old in ('ordinary-field-relations-v1', 'ordinary-field-relations-v2'):
            self.assertNotEqual(real(previous, old), config['pricing_version'])

    def test_the_campaign_runners_amendment_formula_is_the_applications(self):
        from unittest.mock import patch
        from ops import provider_campaign as pc
        for previous in ('configured-v1:' + 'a' * 64, 'configured-v1:47caed2bcbbabc7f0d1c2713ba8b497db26f9fdf2dfff1de092410fdd7f784b4'):
            for contract in ('ordinary-field-relations-v1', 'ordinary-field-relations-v2', r.CONTRACT, 'x'):
                self.assertEqual(pc.contract_pricing_version(previous, contract), g.ordinary_pricing_version(previous, contract))
        seen, real = [], g.ordinary_pricing_version
        with patch.object(g, 'ordinary_pricing_version', side_effect=lambda p, c: seen.append(p) or real(p, c)):
            config = g.configuration()
        self.assertEqual(pc.contract_pricing_version(seen[0], r.CONTRACT), config['pricing_version'])

    def adopted_record(self):
        notes = 'The patient reports that the headache usually feels like intermittent buzzing.'
        first, second = field('sensation', 'Other:'), field('prodrome', 'Other:')
        first['context'] = 'Current headache > What does your headache usually feel like?'
        second['context'] = 'Current headache > Which symptoms occur before the headache begins?'
        fields = [first, second]
        answers = r.validated(raw_result(notes, fields, json.dumps(relation_wire(notes, fields, {'sensation': [notes]}))))
        self.assertEqual(answers['sensation']['status'], 'supported')
        self.assertEqual(g.governed_decisions(notes, fields, answers), [])
        record = signing.loads(answers['sensation']['ordinary_relation'], salt=r.SALT)
        self.assertEqual(record['contract'], r.CONTRACT)
        return notes, fields, answers, record

    def restamped(self, record, notes, fields, contract):
        """The same record as `contract` would have written it (its own binding)."""
        return {**record, 'contract': contract, 'binding': r.digest(
            {'contract': contract, 'notes': notes, 'catalogue': fields, 'context_labels': []})}

    def test_a_v1_record_is_refused_on_every_reader(self):
        notes, fields, answers, record = self.adopted_record()
        old = self.restamped(record, notes, fields, 'ordinary-field-relations-v1')
        for salt in ('quillmd.ordinary-field-relations.v1', 'quillmd.ordinary-field-relations.v2', r.SALT):
            with self.subTest(salt=salt):
                stale = {**answers, 'sensation': {**answers['sensation'],
                                                  'ordinary_relation': signing.dumps(old, salt=salt, compress=True)}}
                self.assertIn('Other:', g.governed_decisions(notes, fields, stale))

    def test_a_stored_v2_record_is_still_read_and_held_exactly_as_v2_did(self):
        # (drafts generated under v2 keep their records: the internal selection is v3's; only its contract, salt and
        # binding name v2. A v2 record under another salt, or naming the other contract, is refused.)
        notes, fields, answers, record = self.adopted_record()
        v2 = self.restamped(record, notes, fields, 'ordinary-field-relations-v2')
        stored = {**answers, 'sensation': {**answers['sensation'], 'ordinary_relation': signing.dumps(
            v2, salt='quillmd.ordinary-field-relations.v2', compress=True)}}
        self.assertEqual(g.governed_decisions(notes, fields, stored), [])
        reading = g.governance_for(notes, fields)[11]['preceding']
        evidence = answers['sensation']['evidence']
        read = r.read(reading, 'Other:', evidence, stored['sensation']['ordinary_relation'], text=notes,
                      field_key='sensation')
        self.assertTrue(read['valid'])
        # a v2 record keeps v2's holds: the same record with a contrary relation is held
        held = {**v2, 'selection': {**v2['selection'], 'context': ['contrary']}}
        self.assertFalse(r.read(reading, 'Other:', evidence, signing.dumps(
            held, salt='quillmd.ordinary-field-relations.v2', compress=True), text=notes, field_key='sensation')['valid'])
        for name, value, salt in (
                ('v2 salt, v3 contract named', self.restamped(record, notes, fields, r.CONTRACT),
                 'quillmd.ordinary-field-relations.v2'),
                ('v3 salt, v2 contract named', v2, r.SALT),
                ('v2 salt, v3 binding', {**v2, 'binding': record['binding']}, 'quillmd.ordinary-field-relations.v2'),
                ('v3 salt, v2 binding', {**record, 'binding': v2['binding']}, r.SALT)):
            with self.subTest(name=name):
                forged = {**answers, 'sensation': {**answers['sensation'],
                                                   'ordinary_relation': signing.dumps(value, salt=salt, compress=True)}}
                self.assertIn('Other:', g.governed_decisions(notes, fields, forged))

    def test_v1_and_v2_job_configurations_and_raw_results_are_refused(self):
        for contract in ('ordinary-field-relations-v1', 'ordinary-field-relations-v2'):
            with self.subTest(contract=contract):
                config = {**g.configuration(), 'ordinary_field_contract': contract}
                with self.assertRaises(ValidationError):
                    r.require_config(config)
                with self.assertRaises(NoProviderRequest):
                    g.job_request_profile(config)
                result = raw_result(N02_NOTES, n02_fields(), json.dumps(relation_wire(N02_NOTES, n02_fields(), {})))
                self.assertEqual(r.validated(result)['v3_3']['status'], 'missing')
                with self.assertRaises(ValidationError):
                    r.validated({**result, 'ordinary_field_contract': contract})


@override_settings(**RELATIONS)
class VetoControls(SimpleTestCase):
    """Synthetic model outputs through the v3 wire and the whole reader (parse -> records -> validate_selections ->
    v3_adopted). `other` is the relation the simulated model gives every non-selected unit."""

    def outcome(self, notes, label, picks, *, other='independent', kind='text', options=None, choices=None,
                relations=None):
        fields = [field('f', label, kind, options)] if options else [field('f', label)]
        asked, context, _ = g.v3_generation_fields(fields)
        units = g.source_units(notes, asked, context_labels=context)[0]
        by_quote = {u['quote']: u['id'] for u in units}
        self.assertTrue(set(picks) <= set(by_quote), (picks, list(by_quote)))
        chosen = [by_quote[q] for q in picks]
        entry = {'key': 'f', 'unit_ids': chosen, 'conflict': False,
                 'context': [{'unit': u['id'], 'relation': (relations or {}).get(u['quote'], 'answer' if u['id'] in chosen
                                                                                 else other)} for u in units]}
        if options:
            entry['option_ids'] = choices or []
        return adopted(notes, fields, {'fields': [entry]})['f']

    def test_a_real_contradiction_is_held_when_the_model_vetoes_it(self):
        for notes in ('The patient smokes. The patient does not smoke.',
                      'The patient smokes. She quit smoking last year and has not smoked since.'):
            for other in ('contrary', 'unresolved'):
                with self.subTest(notes=notes, other=other):
                    self.assertEqual(self.outcome(notes, 'Smoking status', ['The patient smokes.'], other=other),
                                     ('conflict', ''))
            # (F14 closed 2026-09-30: the relation floors hold a non-copular opposite the model calls independent -
            # 'smokes' / 'does not smoke' (OPPOSED SAME TOPIC), and 'quit smoking last year' (a cessation of what it
            # claims) - whatever it says; `g.v3_relation_causes`)
            self.assertEqual(self.outcome(notes, 'Smoking status', ['The patient smokes.']), ('conflict', ''))
        # a copular opposite is held by the application whatever the model says
        notes = 'The patient is suicidal. The patient is not suicidal.'
        self.assertEqual(self.outcome(notes, 'Risk to self', ['The patient is suicidal.']), ('conflict', ''))

    def test_an_unrelated_statement_stays_independent(self):
        notes = 'The patient is not allergic to penicillin. The patient walks every day.'
        self.assertEqual(self.outcome(notes, 'Allergies', ['The patient is not allergic to penicillin.']),
                         ('supported', 'The patient is not allergic to penicillin.'))
        self.assertEqual(self.outcome(notes, 'Allergies', ['The patient is not allergic to penicillin.'],
                                      other='contrary'), ('conflict', ''))           # (an over-veto: a hold, never unsafe)

    def test_a_qualifier_is_kept_with_its_answer_and_never_dropped_silently(self):
        first, second = 'The patient reports knee pain.', 'The patient reports that the pain is worse on stairs.'
        notes = first + ' ' + second
        self.assertEqual(self.outcome(notes, 'Clinical observation', [first, second], relations={second: 'qualifier'}),
                         ('supported', first + '\n' + second))
        # a qualifier the model names but does not select holds the answer
        for label in ('Clinical observation', 'Knee pain'):
            self.assertEqual(self.outcome(notes, label, [first], relations={second: 'qualifier'}), ('conflict', ''))
        # (recorded: a qualifier the model misses — called independent — is held where the application reads the
        # question's own subject in it, and otherwise leaves the answer without it; that depends on the model)
        self.assertEqual(self.outcome(notes, 'Knee pain', [first]), ('conflict', ''))
        self.assertEqual(self.outcome(notes, 'Clinical observation', [first]), ('supported', first))
        # a qualifier cannot disappear into a fixed option
        notes = 'The patient does not smoke. The patient stopped yesterday.'
        self.assertEqual(self.outcome(notes, 'Smoker', ['The patient does not smoke.', 'The patient stopped yesterday.'],
                                      kind='choice', options=['Yes', 'No'], choices=['f:1'],
                                      relations={'The patient stopped yesterday.': 'qualifier'}), ('conflict', ''))

    def test_a_correction_holds_the_answer_whatever_the_model_says(self):
        notes = 'The patient is allergic to penicillin. Sorry, I mean amoxicillin.'
        for other in ('independent', 'contrary'):
            with self.subTest(other=other):
                self.assertEqual(self.outcome(notes, 'Allergies', ['The patient is allergic to penicillin.'], other=other),
                                 ('conflict', ''))

    def test_a_denial_is_its_own_option_and_never_the_opposite(self):
        notes = 'The patient does not smoke.'
        self.assertEqual(self.outcome(notes, 'Smoker', [notes], kind='choice', options=['Yes', 'No'], choices=['f:1']),
                         ('supported', 'No'))
        self.assertEqual(self.outcome(notes, 'Smoker', [notes], kind='choice', options=['Yes', 'No'], choices=['f:0']),
                         ('conflict', ''))

    def test_another_subject_is_never_the_patient(self):
        first = 'The patient is not allergic to penicillin.'
        named = first + ' Her mother is allergic to penicillin.'
        self.assertEqual(self.outcome(named, 'Allergies', [first]), ('supported', first))
        self.assertEqual(self.outcome(named, 'Allergies', [first], other='contrary'), ('conflict', ''))
        for other in ('independent', 'contrary'):
            with self.subTest(other=other):
                self.assertEqual(self.outcome(first + ' He is allergic to penicillin.', 'Allergies', [first], other=other),
                                 ('conflict', ''))
        self.assertEqual(self.outcome('Her mother is allergic to penicillin.', 'Allergies',
                                      ['Her mother is allergic to penicillin.']), ('conflict', ''))

    def test_the_other_side_is_never_this_side(self):
        self.assertEqual(self.outcome('The patient has right knee pain.', 'Right knee', ['The patient has right knee pain.']),
                         ('supported', 'The patient has right knee pain.'))
        self.assertEqual(self.outcome('The patient has left knee pain.', 'Right knee', ['The patient has left knee pain.']),
                         ('conflict', ''))
        notes = 'The patient has right knee pain. The left knee is swollen.'
        for other in ('independent', 'contrary'):
            with self.subTest(other=other):
                self.assertEqual(self.outcome(notes, 'Right knee', ['The patient has right knee pain.'], other=other),
                                 ('conflict', ''))

    def test_history_is_not_the_present_answer(self):
        past, present = 'The patient was responsive to physiotherapy.', 'The patient is not responsive to physiotherapy.'
        notes = past + ' ' + present
        self.assertEqual(self.outcome(notes, 'Clinical observation', [present]), ('supported', present))
        self.assertEqual(self.outcome(notes, 'Clinical observation', [present], other='contrary'), ('conflict', ''))
        notes = 'The patient is subject to MAPPA. Today the patient was not subject to MAPPA.'
        for other in ('independent', 'contrary'):
            with self.subTest(other=other):
                self.assertEqual(self.outcome(notes, 'MAPPA status', ['The patient is subject to MAPPA.'], other=other),
                                 ('conflict', ''))


@override_settings(**RELATIONS)
class FrozenWalkShape(SimpleTestCase):
    """Refutation F2-FROZEN-WALK, measured independently of the campaign runner (which states the same fact in its notes
    plan and stage decisions: ops/sonnet5_stages.frozen_walk_check). The frozen N6 walk's provider answers through the
    FROZEN diagnostics/notes/app_path_steps.reference_answer, which builds contract v1's list body; this engine refuses it
    on every relations case, and the v3 translation of the SAME selection is accepted — so the refusal is the answer's
    shape, not its content. The frozen file is read, never changed (the freeze manifest pins it)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import sys
        from pathlib import Path
        notes = Path(__file__).resolve().parents[3] / 'docs' / 'rebuild' / 'v1' / 'sonnet5-campaign' / 'diagnostics' / 'notes'
        if str(notes) not in sys.path:
            sys.path.insert(0, str(notes))
        import app_path_steps
        cls.steps = app_path_steps
        cls.cases = json.loads((notes / 'cases.json').read_text())

    def test_the_frozen_walks_relations_answer_is_refused_and_its_v3_translation_read(self):
        measured = []
        for case in self.cases['cases']:
            if 'field_relations' not in case['send_paths']:
                continue
            measured.append(case['id'])
            fields = self.cases['forms'][case['form']]['fields']
            with self.subTest(case=case['id']), override_settings(**self.steps.PATH_FLAGS['field_relations']):
                compiled = r.compile_request(case['notes'], fields, g.configuration(fields))
                payload = json.loads(compiled['wire']['messages'][0]['content'])
                body, _ = self.steps.reference_answer(case['notes'], fields, payload,
                                                      self.steps.reference_selection(case, 'field_relations'))
                self.assertIsInstance(body['fields'], list)                       # (contract v1's shape)
                with self.assertRaises(ValidationError) as caught:
                    r.parse(json.dumps(body), compiled['asked'], compiled['units'])
                self.assertIn('malformed', ' '.join(caught.exception.messages))
                translated = wired(body, compiled['asked'], compiled['units'])
                parsed = r.parse(json.dumps(translated), compiled['asked'], compiled['units'])
                self.assertEqual([(row.key, list(row.unit_ids), row.conflict) for row in parsed.fields],
                                 [(item['key'], item['unit_ids'], item['conflict']) for item in body['fields']])
        self.assertEqual(sorted(measured), ['N02', 'N03', 'N10', 'N13', 'N14', 'N15', 'N16'])
