"""Closed ordinary interpretation transport; provider decisions are simulated."""
import copy
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_v3_ordinary_notes import LIVE, field


def relation_body(notes, fields, picks, *, choices=None, overrides=None):
    asked, context, _ = g.v3_generation_fields(fields)
    units = g.source_units(notes, asked, context_labels=context)[0]
    by_quote = {u['quote']: u['id'] for u in units}
    body = []
    for f in asked:
        chosen = [by_quote[q] for q in picks.get(f['key'], [])]
        body.append({'key': f['key'], 'unit_ids': chosen, 'conflict': False,
                     'option_ids': (choices or {}).get(f['key'], []),
                     'context': [(overrides or {}).get((f['key'], u['quote']),
                                 'answer' if u['id'] in chosen else 'independent') for u in units]})
    return {'fields': body}


def offered(notes, fields, picks, *, choices=None, overrides=None):
    asked, context, _ = g.v3_generation_fields(fields)
    units = g.source_units(notes, asked, context_labels=context)[0]
    selections = r.FieldSelections.model_validate(relation_body(notes, fields, picks, choices=choices, overrides=overrides))
    records = r.records(notes, fields, context, units, selections, g.SONNET_5)
    answers = g.validate_selections(notes, asked, selections, context_labels=context,
        evidence_contract=g.TAB_CONTRACT, ordinary_records=records, catalogue=fields)
    return g.v3_adopted(fields, answers, notes, asked, context)


def repeated():
    first, second = field('sensation', 'Other:'), field('prodrome', 'Other:')
    first['context'] = 'Current headache > What does your headache usually feel like?'
    second['context'] = 'Current headache > Which symptoms occur before the headache begins?'
    return [first, second]


@override_settings(**dict(LIVE, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=True))
class OrdinaryFieldRelations(SimpleTestCase):
    def assert_stored_clear(self, notes, fields, answers):
        self.assertEqual(g.governed_decisions(notes, fields, answers), [])
        governance = g.governance_for(notes, fields)
        for f in fields:
            value = answers[f['key']]
            if value['status'] != 'supported': continue
            row = g.as_currently_governed(governance, notes, {**f, **value})
            self.assertEqual((row['status'], row['text']), ('supported', value['text']))

    def test_different_complete_questions_can_own_an_ordinary_other_answer(self):
        notes = 'The patient reports that the headache usually feels like intermittent buzzing.'
        fields = repeated(); answers = offered(notes, fields, {'sensation': [notes]})
        self.assertEqual((answers['sensation']['status'], answers['sensation']['text']), ('supported', notes))
        self.assertEqual(answers['prodrome']['status'], 'missing')
        self.assert_stored_clear(notes, fields, answers)

    def test_identical_contexts_and_ambiguous_labelled_answers_stay_held(self):
        notes = 'The patient reports intermittent buzzing.'
        fields = repeated(); fields[1]['context'] = fields[0]['context']
        self.assertEqual(offered(notes, fields, {'sensation': [notes]})['sensation']['status'], 'conflict')
        notes = 'The patient reports intermittent buzzing.'
        answers = offered(notes, repeated(), {'sensation': [notes], 'prodrome': [notes]})
        self.assertEqual({a['status'] for a in answers.values()}, {'conflict'})
        fields = repeated(); notes = 'Other: buzzing.'
        self.assertEqual(offered(notes, fields, {'sensation': [notes]})['sensation']['status'], 'conflict')

    def test_explicit_same_side_is_useful_and_opposite_unknown_or_mixed_sides_hold(self):
        fields = [field('site', 'Right knee')]
        notes = 'The patient has right knee pain.'
        answer = offered(notes, fields, {'site': [notes]})
        self.assertEqual((answer['site']['status'], answer['site']['text']), ('supported', notes))
        self.assert_stored_clear(notes, fields, answer)
        for notes in ('The patient has left knee pain.', 'The patient has knee pain.',
                      'The patient has right and left knee pain.'):
            with self.subTest(notes=notes):
                self.assertEqual(offered(notes, fields, {'site': [notes]})['site']['status'], 'conflict')

    def test_ordinary_predicate_selects_the_original_option_and_keeps_full_evidence(self):
        notes = 'The patient does not smoke.'
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No'])]
        answers = offered(notes, fields, {'smoking': [notes]}, choices={'smoking': ['smoking:1']})
        self.assertEqual((answers['smoking']['status'], answers['smoking']['text']), ('supported', 'No'))
        self.assertEqual(answers['smoking']['evidence'], [{'quote': notes, 'start': 0, 'end': len(notes)}])
        self.assert_stored_clear(notes, fields, answers)

    def test_wrong_binary_polarity_and_an_omitted_opposite_predicate_cannot_be_model_permissions(self):
        for label, yes, no in (('Smoker', 'The patient does smoke.', 'The patient does not smoke.'),
                               ('Pain', 'The patient has pain.', 'The patient has no pain.'),
                               ('Do you smoke?', 'The patient does smoke.', 'The patient does not smoke.')):
            fields = [field('predicate', label, 'choice', ['Yes', 'No'])]
            for notes, option, status in ((yes, 'predicate:0', 'supported'), (no, 'predicate:1', 'supported'),
                                          (yes, 'predicate:1', 'conflict'), (no, 'predicate:0', 'conflict')):
                with self.subTest(label=label, notes=notes, option=option):
                    answer = offered(notes, fields, {'predicate': [notes]}, choices={'predicate': [option]})
                    self.assertEqual(answer['predicate']['status'], status)
                    if status == 'supported': self.assert_stored_clear(notes, fields, answer)
            note = no + ' ' + yes
            self.assertEqual(offered(note, fields, {'predicate': [no]},
                choices={'predicate': ['predicate:1']})['predicate']['status'], 'conflict')
            old = {'status': 'supported', 'text': 'Yes', 'evidence': [{'quote': no, 'start': 0, 'end': len(no)}]}
            self.assertEqual(g.governed_decisions(no, fields, {'predicate': old}), [label])
        fields = [field('predicate', 'Smoker', 'choice', ['Yes', 'No'])]
        for notes in ('The patient does not smoke daily.', 'The patient does not drink.',
                      'The patient formerly smoked.', 'The patient is not a nonsmoker.'):
            self.assertEqual(offered(notes, fields, {'predicate': [notes]},
                choices={'predicate': ['predicate:1']})['predicate']['status'], 'conflict')

    def test_event_relative_destination_requires_explicit_matching_source_scope(self):
        fields = repeated()
        current = 'The patient reports that the headache usually feels like intermittent buzzing.'
        before = 'The patient reports intermittent buzzing before the headache begins.'
        after = 'The patient reports intermittent buzzing after the headache begins.'
        for notes, key, status in ((current, 'sensation', 'supported'), (current, 'prodrome', 'conflict'),
                                   (before, 'prodrome', 'supported'), (after, 'prodrome', 'conflict')):
            with self.subTest(notes=notes, key=key):
                answers = offered(notes, fields, {key: [notes]})
                self.assertEqual(answers[key]['status'], status)
                if status == 'supported': self.assert_stored_clear(notes, fields, answers)
        target = field('symptoms', 'Symptoms before treatment')
        for notes, status in (('The patient reports nausea before treatment.', 'supported'),
                              ('The patient reports nausea after treatment.', 'conflict'),
                              ('The patient reports nausea.', 'conflict')):
            self.assertEqual(offered(notes, [target], {'symptoms': [notes]})['symptoms']['status'], status)

    def test_qualifier_cannot_disappear_into_a_fixed_option(self):
        first, last = 'The patient does not smoke.', 'The patient stopped yesterday.'
        notes = first + ' ' + last
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No'])]
        answers = offered(notes, fields, {'smoking': [first, last]}, choices={'smoking': ['smoking:1']},
                          overrides={('smoking', last): 'qualifier'})
        self.assertEqual(answers['smoking']['status'], 'conflict')

    def test_duplicate_printed_options_and_reordered_identical_occurrences(self):
        notes = 'The patient does not smoke.'
        fields = [field('smoking', 'Smoker', 'choice', ['No', 'No.'])]
        self.assertEqual(offered(notes, fields, {'smoking': [notes]},
            choices={'smoking': ['smoking:0']})['smoking']['status'], 'conflict')
        quote = 'The patient reports persistent aching.'; notes = quote + ' ' + quote
        fields = [field('hpi', 'History of present illness')]
        units = g.source_units(notes, fields)[0]
        selections = r.FieldSelections(fields=[r.FieldSelection(key='hpi', unit_ids=[2, 1], conflict=False,
            option_ids=[], context=['answer', 'answer'])])
        records = r.records(notes, fields, [], units, selections, g.SONNET_5)
        answers = g.validate_selections(notes, fields, selections, evidence_contract=g.TAB_CONTRACT,
            ordinary_records=records, catalogue=fields)
        answers = g.v3_adopted(fields, answers, notes, fields)
        self.assertEqual((answers['hpi']['status'], answers['hpi']['text']), ('supported', quote + '\n' + quote))
        self.assertEqual([e['start'] for e in answers['hpi']['evidence']], [0, len(quote) + 1])

    def test_source_printed_patient_authorship_and_review_attestation_have_literal_prerequisites(self):
        source = {'part': 'word/document.xml', 'slot': 'b/p[0]', 'fingerprint': 'a' * 64, 'text': 'For the patient:'}
        target = field('comments', 'Additional comments')
        target['answer_policy'] = {'source_author': 'patient', 'source': source}
        for notes, expected in (('The patient reports feeling adequately supported.', 'supported'),
                                ('The patient is clinically stable.', 'conflict'),
                                ('The patient had the procedure.', 'conflict'),
                                ('The clinician reports that the patient is stable.', 'conflict')):
            with self.subTest(notes=notes):
                answer = offered(notes, [target], {'comments': [notes]})
                self.assertEqual(answer['comments']['status'], expected)
                if expected == 'supported': self.assert_stored_clear(notes, [target], answer)
                else:
                    old = {'text': notes, 'status': 'supported', 'evidence': [{'quote': notes, 'start': 0, 'end': len(notes)}]}
                    self.assertEqual(g.governed_decisions(notes, [target], {'comments': old}), ['Additional comments'])
        target['answer_policy'] = {'attestation': 'document_review', 'attestation_source': {**source, 'text': 'Confirm patient reviewed report.'}}
        for notes, expected in (('The patient has reviewed the report.', 'supported'),
                                ('The patient was given an opportunity to comment on the report.', 'supported'),
                                ('The patient has not reviewed the report.', 'conflict'),
                                ('The patient will review the report.', 'conflict'),
                                ('The patient had the procedure.', 'conflict')):
            with self.subTest(notes=notes):
                self.assertEqual(offered(notes, [target], {'comments': [notes]})['comments']['status'], expected)
        both = {**target['answer_policy'], 'source_author': 'patient', 'source': source}
        target['answer_policy'] = both
        notes = 'The patient has reviewed the report.'
        self.assertEqual(offered(notes, [target], {'comments': [notes]})['comments']['status'], 'conflict')
        notes = 'The patient reports having read the report.'
        self.assertEqual(offered(notes, [target], {'comments': [notes]})['comments']['status'], 'supported')
        target['answer_policy'] = {'attestation': 'document_review', 'source': source}
        self.assertEqual(offered(notes, [target], {'comments': [notes]})['comments']['status'], 'conflict')

    def test_correction_subject_omission_contradiction_and_consent_guards_survive(self):
        first = 'The patient reports intermittent buzzing.'
        fields = repeated()
        for prefix in ('Family history:\n', 'The following symptoms are denied:\n'):
            self.assertEqual(offered(prefix + first, fields, {'sensation': [first]})['sensation']['status'], 'conflict')
        tail = 'Correction: this history belongs to another patient.'
        self.assertEqual(offered(first + ' ' + tail, fields, {'sensation': [first]})['sensation']['status'], 'conflict')
        for relation in ('qualifier', 'contrary', 'unresolved'):
            tail = 'The buzzing resolved yesterday.'
            self.assertEqual(offered(first + ' ' + tail, fields, {'sensation': [first]},
                overrides={('sensation', tail): relation})['sensation']['status'], 'conflict')
        fields = [field('consent', 'Consent obtained', 'checkbox', ['Consent obtained'])]
        note = 'The patient had the procedure.'
        self.assertEqual(offered(note, fields, {'consent': [note]}, choices={'consent': ['consent:0']})['consent']['status'], 'conflict')

    def test_partition_and_original_option_references_are_closed(self):
        notes = 'The patient does not smoke.'
        fields = [field('smoking', 'Smoker', 'choice', ['Yes', 'No'])]
        original = relation_body(notes, fields, {'smoking': [notes]}, choices={'smoking': ['smoking:1']})
        units = g.source_units(notes, fields)[0]
        mutations = [lambda b: b['fields'].append(copy.deepcopy(b['fields'][0])),
                     lambda b: b['fields'][0].update(context=[]),
                     lambda b: b['fields'][0].update(unit_ids=[999]),
                     lambda b: b['fields'][0].update(option_ids=['other:1']),
                     lambda b: b['fields'][0].update(option_ids=['smoking:1', 'smoking:1']),
                     lambda b: b['fields'][0].update(context=['independent']),
                     lambda b: b['fields'][0].update(conflict='false')]
        for mutate in mutations:
            body = copy.deepcopy(original); mutate(body)
            with self.subTest(body=body), self.assertRaises((ValueError, ValidationError)):
                r.records(notes, fields, [], units, r.FieldSelections.model_validate(body), g.SONNET_5)

    def test_stored_record_binds_source_mapping_destination_output_and_enablement(self):
        notes = 'The patient reports that the headache usually feels like intermittent buzzing.'
        fields = repeated(); original = offered(notes, fields, {'sensation': [notes]})
        for mutate in (lambda a: a['sensation'].update(text=notes + ' Changed.'),
                       lambda a: a['sensation'].update(ordinary_relation=a['sensation']['ordinary_relation'] + 'bad'),
                       lambda a: a['sensation']['evidence'][0].update(end=1),
                       lambda a: a['sensation'].pop('ordinary_relation')):
            answers = copy.deepcopy(original); mutate(answers)
            self.assertIn('Other:', g.governed_decisions(notes, fields, answers))
        moved = {'sensation': original['prodrome'], 'prodrome': original['sensation']}
        self.assertIn('Other:', g.governed_decisions(notes, fields, moved))
        altered = copy.deepcopy(fields); altered[0]['locator']['fingerprint'] = '1' * 64
        self.assertIn('Other:', g.governed_decisions(notes, altered, original))
        self.assertIn('Other:', g.governed_decisions(notes + ' New source.', fields, original))
        with override_settings(V3_FIELD_RELATIONS=False):
            self.assertIn('Other:', g.governed_decisions(notes, fields, original))

    def test_complete_catalogue_actual_wire_and_price_share_one_compiler(self):
        fields = repeated(); fields.append(field('signature', 'Clinician signature', 'signature'))
        fields[0]['source_relationships'] = [{'relation': 'previous_question', 'complete_question': 'Full original wording'}]
        notes = 'The patient reports intermittent buzzing.'
        config = g.configuration(); prepared = r.compile_request(notes, fields, config)
        wire = prepared['wire']; payload = json.loads(wire['messages'][0]['content'])
        self.assertEqual(payload['catalogue'], fields)
        self.assertEqual(payload['requested_field_ids'], ['sensation', 'prodrome'])
        self.assertNotIn('questions', payload)
        rate = g.rates(config)
        required = (Decimal(len(json.dumps(wire).encode()) + 12000) * rate['input_per_million']
                    + Decimal(wire['max_tokens']) * rate['output_per_million']) / 1000000
        self.assertGreaterEqual(g.maximum_cost(notes, fields, config), required)
        self.assertLessEqual(prepared['response_byte_bound'], wire['max_tokens'])
        with patch('anthropic.Anthropic') as sdk:
            sdk.return_value.messages.create.side_effect = RuntimeError('stop at actual SDK boundary')
            with self.assertRaisesRegex(RuntimeError, 'actual SDK boundary'):
                g.generate(notes, fields, config)
            self.assertEqual(sdk.return_value.messages.create.call_args.kwargs, wire)
        with override_settings(V3_FIELD_RELATIONS=False):
            old = g.configuration()
            self.assertNotIn('ordinary_field_contract', old)
            self.assertNotEqual(old['pricing_version'], config['pricing_version'])
            with self.assertRaises(ValidationError): r.compile_request(notes, fields, config)

    def test_closed_response_capacity_refuses_before_any_provider(self):
        fields = repeated(); notes = ' '.join('The patient reports pain.' for _ in range(129))
        with patch('anthropic.Anthropic') as sdk:
            with self.assertRaises(ValidationError): g.maximum_cost(notes, fields)
            sdk.assert_not_called()
