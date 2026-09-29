"""The keyed ordinary-relations contract (v2) at its request/response boundary, offline: the per-request schema reaches
the provider unchanged, the strict parser refuses every malformed answer and converts a good one into the unchanged
internal selections, v1 artifacts refuse at their own gates, and the veto controls run through the whole reader with
synthetic model outputs. No provider, no network, no database."""
import copy
import json
from types import SimpleNamespace

from anthropic import transform_schema
from django.core import signing
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from core.jobs import NoProviderRequest
from .test_v3_field_relations import keyed, relation_body, relation_wire
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


@override_settings(**RELATIONS)
class KeyedSchema(SimpleTestCase):
    def shapes(self):
        choice = field('smoking', 'Smoker', 'choice', ['Yes', 'No'])
        yield 'N02', N02_NOTES, n02_fields()
        yield 'choice and text', 'The patient does not smoke. The patient walks daily.', [choice, field('f', 'Activity')]
        for n_fields, n_units in ((1, 1), (3, 2), (10, 60), (1, 400)):
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
                self.assertEqual(defs['Relation'], {'type': 'string', 'enum': list(r.RELATIONS)})
                self.assertEqual(defs['UnitId'], {'type': 'integer', 'enum': ids})
                self.assertEqual(defs['Context']['required'], [str(i) for i in ids])
                self.assertEqual(set(defs['Context']['properties']), {str(i) for i in ids})
                self.assertFalse(defs['Context']['additionalProperties'])
                self.assertTrue(all(p == {'$ref': '#/$defs/Relation'} for p in defs['Context']['properties'].values()))
                top = schema['properties']['fields']
                self.assertEqual((schema['required'], schema['additionalProperties']), (['fields'], False))
                self.assertEqual((top['required'], top['additionalProperties']), ([f['key'] for f in asked], False))
                for f in asked:
                    own = [o['id'] for o in r.options(f)]
                    member = top['properties'][f['key']]
                    if own:
                        self.assertEqual(member['properties']['option_ids']['items']['enum'], own)
                        self.assertIn('option_ids', member['required'])
                        self.assertFalse(member['additionalProperties'])
                    else:
                        self.assertEqual(member, {'$ref': '#/$defs/Answer'})
                        self.assertNotIn('option_ids', defs['Answer']['properties'])

    def test_the_response_bound_is_the_keyed_worst_case_body(self):
        notes = 'The patient does not smoke. The patient walks daily.'
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No']), field('f', 'Activity')]
        asked, context, _ = g.v3_generation_fields(fields)
        units = g.source_units(notes, asked, context_labels=context)[0]
        worst = {'fields': {'smoking': {'unit_ids': [1, 2], 'conflict': False, 'option_ids': ['smoking:0', 'smoking:1'],
                                        'context': {'1': 'independent', '2': 'independent'}},
                            'f': {'unit_ids': [1, 2], 'conflict': False,
                                  'context': {'1': 'independent', '2': 'independent'}}}}
        self.assertEqual(r.response_bound(asked, units), len(json.dumps(worst).encode()))
        self.assertTrue(all(len(json.dumps(rel)) <= len(json.dumps('independent')) for rel in r.RELATIONS))

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

    def edited(self, edit):
        body = copy.deepcopy(self.good)
        edit(body)
        return json.dumps(body)

    def test_a_correct_keyed_answer_is_adopted_through_the_whole_reader(self):
        self.assertEqual(adopted(N02_NOTES, self.fields, self.text),
                         {'v3_1': ('supported', 'The patient describes the pain as a tight band around her head.'),
                          'v3_2': ('conflict', ''), 'v3_3': ('missing', '')})

    def test_context_members_in_any_order_convert_to_the_offered_unit_order(self):
        asked, context, _ = g.v3_generation_fields(self.fields)
        units = g.source_units(N02_NOTES, asked, context_labels=context)[0]
        body = copy.deepcopy(self.good)
        body['fields']['v3_1']['context'] = {'2': 'contrary', '1': 'answer'}
        body['fields'] = dict(reversed(list(body['fields'].items())))
        parsed = r.parse(json.dumps(body), asked, units)
        self.assertIsInstance(parsed, r.FieldSelections)
        self.assertEqual([f.key for f in parsed.fields], ['v3_1', 'v3_2', 'v3_3'])
        self.assertEqual(parsed.fields[0].context, ['answer', 'contrary'])
        self.assertEqual(parsed.fields[0].option_ids, [])

    def malformed(self):
        v3_1 = '{"unit_ids": [1], "conflict": false, "context": {"1": "answer", "2": "independent"}}'
        v1_list = {'fields': [{'key': k, 'unit_ids': v['unit_ids'], 'conflict': v['conflict'], 'option_ids': [],
                               'context': list(v['context'].values())} for k, v in self.good['fields'].items()]}
        attempt_017 = {'fields': [{'key': 'v3_1', 'unit_ids': [1], 'conflict': False, 'option_ids': [], 'context': ['answer']},
                                  {'key': 'v3_2', 'unit_ids': [2], 'conflict': False, 'option_ids': [], 'context': ['answer']},
                                  {'key': 'v3_3', 'unit_ids': [], 'conflict': False, 'option_ids': [], 'context': []}]}
        return {
            'the v1 list shape': json.dumps(v1_list),
            'attempt 017 as returned (one context entry for two units)': json.dumps(attempt_017),
            'not JSON': self.text[:-1],
            'two JSON values': self.text + ' {}',
            'a top-level array': '[' + self.text + ']',
            'an extra top-level member': self.edited(lambda b: b.update(note='x')),
            'a duplicate top-level member': '{"fields": {}, ' + self.text[1:],
            'a duplicate field key': self.text.replace('{"fields": {"v3_1": ', '{"fields": {"v3_1": ' + v3_1 + ', "v3_1": ', 1),
            'a duplicate context member': self.text.replace('"context": {"1": "answer"', '"context": {"1": "independent", "1": "answer"', 1),
            'a duplicate member inside a field': self.text.replace('{"unit_ids": [1]', '{"unit_ids": [], "unit_ids": [1]', 1),
            'a missing field': self.edited(lambda b: b['fields'].pop('v3_3')),
            'an extra field': self.edited(lambda b: b['fields'].update(v3_9=copy.deepcopy(b['fields']['v3_3']))),
            'fields as a list': self.edited(lambda b: b.update(fields=list(b['fields'].values()))),
            'a missing unit key': self.edited(lambda b: b['fields']['v3_3']['context'].pop('2')),
            'an extra unit key': self.edited(lambda b: b['fields']['v3_1']['context'].update({'3': 'independent'})),
            'a unit key that is not its ID': self.edited(lambda b: b['fields']['v3_1']['context'].update(
                {'01': b['fields']['v3_1']['context'].pop('1')})),
            'a relation outside the five': self.edited(lambda b: b['fields']['v3_1']['context'].update({'2': 'unrelated'})),
            'a relation that is not a string': self.edited(lambda b: b['fields']['v3_1']['context'].update({'2': None})),
            'context as a list': self.edited(lambda b: b['fields']['v3_1'].update(context=['answer', 'independent'])),
            'a repeated unit ID': self.edited(lambda b: b['fields']['v3_1'].update(unit_ids=[1, 1])),
            'true as a unit ID': self.edited(lambda b: b['fields']['v3_1'].update(unit_ids=[True])),
            'a float unit ID': self.text.replace('"unit_ids": [1]', '"unit_ids": [1.0]', 1),
            'a string unit ID': self.edited(lambda b: b['fields']['v3_1'].update(unit_ids=['1'])),
            'an unknown unit ID': self.edited(lambda b: b['fields']['v3_1'].update(unit_ids=[9])),
            'NaN': self.text.replace('"unit_ids": [1]', '"unit_ids": [NaN]', 1),
            'Infinity': self.text.replace('"unit_ids": [1]', '"unit_ids": [Infinity]', 1),
            '-Infinity': self.text.replace('"unit_ids": [1]', '"unit_ids": [-Infinity]', 1),
            'a numeric conflict': self.edited(lambda b: b['fields']['v3_1'].update(conflict=0)),
            'a string conflict': self.edited(lambda b: b['fields']['v3_1'].update(conflict='false')),
            'a missing conflict': self.edited(lambda b: b['fields']['v3_1'].pop('conflict')),
            'option_ids on a text field': self.edited(lambda b: b['fields']['v3_1'].update(option_ids=[])),
            'the v1 key member': self.edited(lambda b: b['fields']['v3_1'].update(key='v3_1')),
        }

    def test_every_malformed_answer_is_refused_before_any_record(self):
        asked, context, _ = g.v3_generation_fields(self.fields)
        units = g.source_units(N02_NOTES, asked, context_labels=context)[0]
        for name, text in self.malformed().items():
            with self.subTest(name=name):
                with self.assertRaises(ValidationError) as caught:
                    r.parse(text, asked, units)
                self.assertIn(r.MALFORMED, caught.exception.messages[0])
                with self.assertRaises(ValidationError):
                    r.validated(raw_result(N02_NOTES, self.fields, text))

    def test_option_fields_are_closed_to_their_own_options(self):
        notes = 'The patient does not smoke.'
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No']), field('other', 'Other', 'choice', ['A', 'B'])]
        good = relation_wire(notes, fields, {'smoking': [notes]}, choices={'smoking': ['smoking:1']})
        self.assertEqual(adopted(notes, fields, good)['smoking'], ('supported', 'No'))
        for name, edit in (('a missing option_ids', lambda b: b['fields']['smoking'].pop('option_ids')),
                           ('an unknown option', lambda b: b['fields']['smoking'].update(option_ids=['smoking:7'])),
                           ('another field\'s option', lambda b: b['fields']['smoking'].update(option_ids=['other:1'])),
                           ('a repeated option', lambda b: b['fields']['smoking'].update(option_ids=['smoking:1'] * 2)),
                           ('a numeric option', lambda b: b['fields']['smoking'].update(option_ids=[1]))):
            body = copy.deepcopy(good); edit(body)
            with self.subTest(name=name), self.assertRaises(ValidationError):
                adopted(notes, fields, body)

    def test_answers_that_parse_but_disagree_with_their_selection_hold_that_field_only(self):
        # (was: refused by records() for the WHOLE response, which failed the job — live attempt 020. A disagreement
        # is the model's own statement about ONE field, not malformed output: that field is held, nothing else moves.)
        good = adopted(N02_NOTES, self.fields, self.text)
        for name, key, edit in (('an answer relation on an unselected unit', 'v3_3',
                                 lambda b: b['fields']['v3_3']['context'].update({'1': 'answer'})),
                                ('a selected unit marked independent', 'v3_1',
                                 lambda b: b['fields']['v3_1']['context'].update({'1': 'independent'}))):
            with self.subTest(name=name):
                got = adopted(N02_NOTES, self.fields, self.edited(edit))
                self.assertEqual(got[key], ('conflict', ''))
                self.assertEqual({k: v for k, v in got.items() if k != key}, {k: v for k, v in good.items() if k != key})

    def test_a_veto_on_another_unit_holds_the_answer(self):
        for relation in ('contrary', 'unresolved'):
            with self.subTest(relation=relation):
                body = self.edited(lambda b: b['fields']['v3_1']['context'].update({'2': relation}))
                self.assertEqual(adopted(N02_NOTES, self.fields, body)['v3_1'], ('conflict', ''))
        body = self.edited(lambda b: b['fields']['v3_1'].update(conflict=True))
        self.assertEqual(adopted(N02_NOTES, self.fields, body)['v3_1'], ('conflict', ''))

    def test_the_parser_is_the_only_reader_of_the_wire(self):
        # the internal selections still refuse the keyed body, and the keyed parser refuses the internal list: two shapes
        with self.assertRaises(ValueError):
            r.FieldSelections.model_validate_json(self.text)
        asked, context, _ = g.v3_generation_fields(self.fields)
        units = g.source_units(N02_NOTES, asked, context_labels=context)[0]
        internal = relation_body(N02_NOTES, self.fields, {})
        with self.assertRaises(ValidationError):
            r.parse(json.dumps(internal), asked, units)
        self.assertEqual(json.loads(json.dumps(keyed(internal, asked, units)))['fields']['v3_3']['context'],
                         {'1': 'independent', '2': 'independent'})


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
        answers = r.validated(raw_result(notes, fields, ATTEMPT_020_TEXT))        # (before: ValidationError 'disagree')
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
        """(name, edit of the keyed wire) — every way ONE field's selection can disagree with its relations. `unit` is
        the field's selected unit ID, `other` a unit it did not select."""
        u, o = str(unit), str(other)

        def put(**changes):
            def edit(body):
                entry = body['fields'][key]
                for name, value in changes.items():
                    if name == 'context':
                        entry['context'].update(value)
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
        body['fields']['allergies']['context']['1'] = 'independent'       # (a selected unit the model calls independent)
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
        # and the keyed parser's controls (StrictParser.malformed) still refuse before any record: a disagreement in
        # one field never excuses a malformed other field
        body = copy.deepcopy(wire)
        body['fields']['allergies']['context']['1'] = 'contrary'
        body['fields']['activity']['unit_ids'] = [9]
        with self.assertRaises(ValidationError) as caught:
            r.validated(raw_result(CLEAN_NOTES, fields, json.dumps(body)))
        self.assertIn(r.MALFORMED, caught.exception.messages[0])


@override_settings(**RELATIONS)
class VersionedArtifacts(SimpleTestCase):
    """v1 records, queued jobs, configurations and raw results refuse at their own gates; nothing reads them as v2."""

    def test_the_contract_and_salt_moved_and_the_pricing_version_with_them(self):
        self.assertEqual((r.CONTRACT, r.SALT), ('ordinary-field-relations-v2', 'quillmd.ordinary-field-relations.v2'))
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
        self.assertNotEqual(real(previous, 'ordinary-field-relations-v1'), config['pricing_version'])

    def test_the_campaign_runners_amendment_formula_is_the_applications(self):
        from unittest.mock import patch
        from ops import provider_campaign as pc
        for previous in ('configured-v1:' + 'a' * 64, 'configured-v1:47caed2bcbbabc7f0d1c2713ba8b497db26f9fdf2dfff1de092410fdd7f784b4'):
            for contract in ('ordinary-field-relations-v1', r.CONTRACT, 'x'):
                self.assertEqual(pc.contract_pricing_version(previous, contract), g.ordinary_pricing_version(previous, contract))
        seen, real = [], g.ordinary_pricing_version
        with patch.object(g, 'ordinary_pricing_version', side_effect=lambda p, c: seen.append(p) or real(p, c)):
            config = g.configuration()
        self.assertEqual(pc.contract_pricing_version(seen[0], r.CONTRACT), config['pricing_version'])

    def test_a_v1_record_is_refused_on_every_reader(self):
        notes = 'The patient reports that the headache usually feels like intermittent buzzing.'
        first, second = field('sensation', 'Other:'), field('prodrome', 'Other:')
        first['context'] = 'Current headache > What does your headache usually feel like?'
        second['context'] = 'Current headache > Which symptoms occur before the headache begins?'
        fields = [first, second]
        answers = r.validated(raw_result(notes, fields, json.dumps(relation_wire(notes, fields, {'sensation': [notes]}))))
        self.assertEqual(answers['sensation']['status'], 'supported')
        self.assertEqual(g.governed_decisions(notes, fields, answers), [])
        record = signing.loads(answers['sensation']['ordinary_relation'], salt=r.SALT)
        old = {**record, 'contract': 'ordinary-field-relations-v1', 'binding': r.digest(
            {'contract': 'ordinary-field-relations-v1', 'notes': notes, 'catalogue': fields, 'context_labels': []})}
        for salt in ('quillmd.ordinary-field-relations.v1', r.SALT):
            with self.subTest(salt=salt):
                stale = {**answers, 'sensation': {**answers['sensation'],
                                                  'ordinary_relation': signing.dumps(old, salt=salt, compress=True)}}
                self.assertIn('Other:', g.governed_decisions(notes, fields, stale))

    def test_a_v1_job_configuration_and_raw_result_are_refused(self):
        config = {**g.configuration(), 'ordinary_field_contract': 'ordinary-field-relations-v1'}
        with self.assertRaises(ValidationError):
            r.require_config(config)
        with self.assertRaises(NoProviderRequest):
            g.job_request_profile(config)
        result = raw_result(N02_NOTES, n02_fields(), json.dumps(relation_wire(N02_NOTES, n02_fields(), {})))
        self.assertEqual(r.validated(result)['v3_3']['status'], 'missing')
        with self.assertRaises(ValidationError):
            r.validated({**result, 'ordinary_field_contract': 'ordinary-field-relations-v1'})


@override_settings(**RELATIONS)
class VetoControls(SimpleTestCase):
    """Synthetic model outputs through the keyed wire and the whole reader (parse -> records -> validate_selections ->
    v3_adopted). `other` is the relation the simulated model gives every non-selected unit."""

    def outcome(self, notes, label, picks, *, other='independent', kind='text', options=None, choices=None,
                relations=None):
        fields = [field('f', label, kind, options)] if options else [field('f', label)]
        asked, context, _ = g.v3_generation_fields(fields)
        units = g.source_units(notes, asked, context_labels=context)[0]
        by_quote = {u['quote']: u['id'] for u in units}
        self.assertTrue(set(picks) <= set(by_quote), (picks, list(by_quote)))
        chosen = [by_quote[q] for q in picks]
        entry = {'unit_ids': chosen, 'conflict': False,
                 'context': {str(u['id']): (relations or {}).get(u['quote'], 'answer' if u['id'] in chosen else other)
                             for u in units}}
        if options:
            entry['option_ids'] = choices or []
        return adopted(notes, fields, {'fields': {'f': entry}})['f']

    def test_a_real_contradiction_is_held_when_the_model_vetoes_it(self):
        for notes in ('The patient smokes. The patient does not smoke.',
                      'The patient smokes. She quit smoking last year and has not smoked since.'):
            for other in ('contrary', 'unresolved'):
                with self.subTest(notes=notes, other=other):
                    self.assertEqual(self.outcome(notes, 'Smoking status', ['The patient smokes.'], other=other),
                                     ('conflict', ''))
            # (F14, recorded: the application's own readers do not hold a non-copular opposite the model calls
            # independent — the keyed contract makes the veto expressible, never effective; paid sends measure it)
            self.assertEqual(self.outcome(notes, 'Smoking status', ['The patient smokes.']),
                             ('supported', 'The patient smokes.'))
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
    on every relations case, and the keyed translation of the SAME selection is accepted — so the refusal is the answer's
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

    def test_the_frozen_walks_relations_answer_is_refused_and_its_keyed_translation_read(self):
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
                translated = keyed(body, compiled['asked'], compiled['units'])
                parsed = r.parse(json.dumps(translated), compiled['asked'], compiled['units'])
                self.assertEqual([(row.key, list(row.unit_ids), row.conflict) for row in parsed.fields],
                                 [(item['key'], item['unit_ids'], item['conflict']) for item in body['fields']])
        self.assertEqual(sorted(measured), ['N02', 'N03', 'N10', 'N13', 'N14', 'N15', 'N16'])
