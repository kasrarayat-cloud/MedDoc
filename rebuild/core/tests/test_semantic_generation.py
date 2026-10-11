"""Source-bound semantic generation controls; every API reply is a local fixture.

The fixtures intentionally separate a fact's concise answer span from its full
source sentence. They exercise compound statements, people, polarity, timing
and typed values rather than assuming that a passing checker makes a draft safe.
"""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from core import generation
from core import semantic_generation as semantic
from documents.semantic_preparation_roles import default_definitions


NOTES = ('Synthetic Alex Morgan came in because of left ankle pain after stepping off a curb yesterday. '
         'The patient rates the pain as 3 out of 10 and reports no head injury. '
         'Examination shows mild swelling over the left lateral ankle, no deformity, and intact distal sensation. '
         'My assessment is left ankle pain. The plan is a follow-up assessment in one week.')
LABELS = ('Patient name', 'Reason for visit', 'History', 'Findings', 'Pain score0 to 10',
          'Assessment', 'Plan', 'Follow-up')
FIELDS = [{'key': 'cell_'+str(index), 'kind': 'text', 'label': label, 'locator': {'cell': index}}
          for index, label in enumerate(LABELS)]


def span(notes, quote, occurrence=0):
    start = -1
    for _ in range(occurrence+1):
        start = notes.index(quote, start+1)
    return {'start': start, 'end': start+len(quote)}


def fact(notes, fields, identity, quote, *, kind='finding', concept=None,
         subject='patient', polarity='affirmed', timing='current', timing_quote=None,
         name_quote=None, unit=None, unit_quote=None, scale=None, occurrence=0,
         supersedes=()):
    value_span = span(notes, quote, occurrence)
    units, _ = generation.source_units(notes, fields)
    selected = [source['id'] for source in units
                if source['start'] <= value_span['start'] < value_span['end'] <= source['end']]
    if len(selected) != 1:
        raise AssertionError('The fixture value must belong to exactly one complete source unit.')
    return {'id': identity, 'kind': kind, 'concept': concept or identity,
            'subject': {'kind': subject, 'name_span': span(notes, name_quote) if name_quote else None},
            'value_span': value_span, 'polarity': polarity,
            'timing': {'kind': timing, 'span': span(notes, timing_quote) if timing_quote else None},
            'source_unit_ids': selected, 'unit': unit,
            'unit_span': span(notes, unit_quote) if unit_quote else None,
            'scale': scale, 'supersedes': list(supersedes)}


def assignments(fields, selected=None, states=None):
    selected = selected or {}
    states = states or {}
    return {'fields': [{'key': field['key'], 'fact_ids': list(selected.get(field['key'], [])),
                        'status': states.get(field['key'], 'supported' if selected.get(field['key']) else 'missing'),
                        'separator': '; '}
                       for field in fields]}


def checker(assignment, *, verdicts=None, fact_findings=()):
    verdicts = verdicts or {}
    return {'fields': [{'key': row['key'], 'verdict': verdicts.get(row['key'],
                            'pass' if row['status'] == 'supported' else row['status']),
                        'fact_ids': list(row['fact_ids']), 'reason': ''}
                       for row in assignment['fields']],
            'fact_findings': list(fact_findings)}


def source_reference(notes, units, selected_span):
    """Test-only fixture conversion; the application never accepts this fallback."""
    if selected_span is None:
        return None
    unit = next(item for item in units if item['start'] <= selected_span['start']
                < selected_span['end'] <= item['end'])
    quote = notes[selected_span['start']:selected_span['end']]
    occurrence = 1
    position = unit['quote'].find(quote)
    while unit['start']+position != selected_span['start']:
        if position < 0:
            raise AssertionError('Fixture source occurrence was not found.')
        occurrence += 1
        position = unit['quote'].find(quote, position+1)
    return {'quote': quote, 'source_unit_id': unit['id'], 'occurrence': occurrence}


def api_facts(notes, units, facts):
    converted = deepcopy(facts)
    for value in converted:
        value['value_span'] = source_reference(notes, units, value['value_span'])
        value['subject']['name_span'] = source_reference(notes, units, value['subject']['name_span'])
        value['timing']['span'] = source_reference(notes, units, value['timing']['span'])
        value['unit_span'] = source_reference(notes, units, value['unit_span'])
        if value['scale'] is not None:
            value['scale']['span'] = source_reference(notes, units, value['scale']['span'])
    return {'facts': converted}


class FixtureSender:
    """Enforce each expected role/attempt, retaining independent input copies."""
    def __init__(self, facts, assignment, checked=None, *, repaired=None, rechecked=None):
        self.calls = []
        self.responses = [('extractor', 1, {'facts': facts}),
                          ('assigner', 1, assignment),
                          ('checker', 1, checked if checked is not None else checker(assignment))]
        if repaired is not None:
            self.responses += [('assigner', 2, repaired),
                               ('checker', 2, rechecked if rechecked is not None else checker(repaired))]

    def __call__(self, role, attempt, payload, schema, instructions):
        self.calls.append((role, attempt, deepcopy(payload), deepcopy(schema), instructions))
        if not self.responses:
            raise AssertionError('Unbudgeted provider stage '+str((role, attempt)))
        expected_role, expected_attempt, result = self.responses.pop(0)
        if (role, attempt) != (expected_role, expected_attempt):
            raise AssertionError('Expected '+str((expected_role, expected_attempt))+'; got '+str((role, attempt)))
        if role == 'extractor' and 'quote' in schema['properties']['facts']['items']['properties']['value_span'].get('required', []):
            return api_facts(payload['notes'], payload['source_units'], result['facts'])
        return deepcopy(result)


def alex_case():
    fields = deepcopy(FIELDS)
    definitions = default_definitions(fields)
    meanings = ('The synthetic patient name, without the presenting complaint.',
                'The current reason for this visit.',
                'The history of this injury and relevant stated negative history.',
                'The documented examination findings, preserving relevant negatives.',
                'The current pain score as an integer on the stated zero-to-ten scale.',
                'The clinician assessment.', 'The documented management plan.',
                'The planned follow-up interval.')
    for field, meaning in zip(fields, meanings):
        definitions[field['key']]['meaning'] = meaning
    definitions['cell_6']['scope']['temporality'] = 'future'
    definitions['cell_7']['scope']['temporality'] = 'future'
    facts = [
        fact(NOTES, fields, 'name', 'Synthetic Alex Morgan', kind='identity', name_quote='Synthetic Alex Morgan'),
        fact(NOTES, fields, 'reason', 'left ankle pain', kind='reason'),
        fact(NOTES, fields, 'mechanism', 'after stepping off a curb yesterday', kind='history',
             timing='past', timing_quote='yesterday'),
        fact(NOTES, fields, 'head_injury', 'no head injury', kind='history', polarity='negated'),
        fact(NOTES, fields, 'pain', '3', kind='measurement', concept='pain_score',
             scale={'minimum': None, 'maximum': '10', 'span': span(NOTES, '3 out of 10')}),
        fact(NOTES, fields, 'swelling', 'mild swelling over the left lateral ankle'),
        fact(NOTES, fields, 'deformity', 'no deformity', polarity='negated'),
        fact(NOTES, fields, 'sensation', 'intact distal sensation'),
        fact(NOTES, fields, 'assessment', 'left ankle pain', kind='assessment', occurrence=1),
        fact(NOTES, fields, 'plan', 'follow-up assessment in one week', kind='plan',
             timing='future', timing_quote='in one week'),
        fact(NOTES, fields, 'follow_up', 'in one week', kind='follow_up',
             timing='future', timing_quote='in one week'),
    ]
    assigned = assignments(fields, {'cell_0': ['name'], 'cell_1': ['reason'],
        'cell_2': ['mechanism', 'head_injury'], 'cell_3': ['swelling', 'deformity', 'sensation'],
        'cell_4': ['pain'], 'cell_5': ['assessment'], 'cell_6': ['plan'], 'cell_7': ['follow_up']})
    return fields, definitions, facts, assigned


class SemanticGenerationTests(SimpleTestCase):
    def test_actual_narrative_has_concise_values_and_complete_exact_source_evidence(self):
        self.assertEqual(hashlib.sha256(NOTES.encode()).hexdigest(),
                         '07f55572e09e0cb646700e3621d68efb4ee19b5a61570f72d5a92006c1cb7340')
        fields, definitions, facts, assigned = alex_case()
        before = deepcopy((fields, definitions, facts, assigned))
        sender = FixtureSender(facts, assigned)
        answers = semantic.run(NOTES, fields, definitions, sender)
        expected = {'cell_0': 'Synthetic Alex Morgan', 'cell_1': 'Left ankle pain',
                    'cell_2': 'After stepping off a curb yesterday; No head injury',
                    'cell_3': 'Mild swelling over the left lateral ankle; No deformity; Intact distal sensation',
                    'cell_4': '3', 'cell_5': 'Left ankle pain',
                    'cell_6': 'Follow-up assessment in one week', 'cell_7': 'In one week'}
        self.assertEqual(set(answers), set(expected))
        units = {unit['id']: unit for unit in generation.source_units(NOTES, fields)[0]}
        fact_index = {value['id']: value for value in facts}
        for field in fields:
            key = field['key']; answer = answers[key]
            with self.subTest(key=key):
                self.assertEqual(answer['text'], expected[key])
                self.assertEqual(answer['status'], 'supported')
                self.assertFalse(answer['reviewed'])
                self.assertEqual(answer['evidence_contract'], semantic.CONTRACT)
                wanted_ids = sorted({identity for selected in assigned['fields'] if selected['key'] == key
                                     for fact_id in selected['fact_ids']
                                     for identity in fact_index[fact_id]['source_unit_ids']})
                self.assertEqual(answer['evidence'], [{name: units[identity][name]
                                                      for name in ('quote', 'start', 'end')}
                                                     for identity in wanted_ids])
                for evidence in answer['evidence']:
                    self.assertEqual(NOTES[evidence['start']:evidence['end']], evidence['quote'])
        self.assertEqual((fields, definitions, facts, assigned), before)
        self.assertEqual([(role, attempt) for role, attempt, *_ in sender.calls],
                         [('extractor', 1), ('assigner', 1), ('checker', 1)])
        self.assertFalse(sender.responses)

    def test_independent_checker_receives_original_notes_and_approved_meanings(self):
        fields, definitions, facts, assigned = alex_case()
        sender = FixtureSender(facts, assigned)
        semantic.run(NOTES, fields, definitions, sender)
        role, attempt, payload, schema, instructions = sender.calls[-1]
        self.assertEqual((role, attempt), ('checker', 1))
        encoded = json.dumps(payload, ensure_ascii=False)
        self.assertIn(NOTES, encoded)
        for definition in definitions.values():
            self.assertIn(definition['meaning'], encoded)
        self.assertFalse(schema.get('additionalProperties', True))
        self.assertIsInstance(instructions, str)

    def test_checker_api_contract_distinguishes_selected_ids_from_context_and_omission_ids(self):
        fields, definitions, facts, assigned = alex_case()
        sender = FixtureSender(facts, assigned)
        semantic.run(NOTES, fields, definitions, sender)
        _, _, payload, schema, instructions = sender.calls[-1]
        properties = schema['properties']['fields']['items']['properties']
        binding = properties['fact_ids']['description']
        self.assertIn('proposed_answers[key].fact_ids', binding)
        self.assertIn('exactly the same fact ID set', binding)
        self.assertIn('order is immaterial', binding)
        self.assertIn('omission may include unselected facts', binding)
        self.assertIn('exact answer and its selected facts', properties['verdict']['description'])
        self.assertIn('do not silently revise the selection under pass', instructions)
        self.assertIn('distinct facts even when they share source evidence', instructions)
        self.assertEqual(payload['proposed_answers']['cell_3']['fact_ids'],
                         ['swelling', 'deformity', 'sensation'])
        self.assertEqual({value['id'] for value in payload['facts']},
                         {value['id'] for value in facts})

    def test_soap_subjective_cannot_reduce_documented_pain_measurement_to_bare_number(self):
        fields, definitions = self.one_field('Subjective')
        notes = 'Subjective: Left ankle pain. Pain is 3 out of 10.'
        facts = [fact(notes, fields, 'symptom', 'Left ankle pain', kind='history'),
                 fact(notes, fields, 'pain', '3', kind='measurement', concept='pain_score',
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, '3 out of 10')})]
        answer = self.generated(notes, fields, definitions, facts, ['symptom', 'pain'])
        self.assert_held(answer)
        self.assertIn('complete documented measurement phrase', ' '.join(answer['review_reasons']))
        self.assertEqual([item['quote'] for item in answer['evidence']],
                         ['Subjective: Left ankle pain.', 'Pain is 3 out of 10.'])
        stale = deepcopy(answer)
        stale.update(status='supported', text=answer['candidate_text'], value=answer['candidate_text'])
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(notes, fields[0], definitions['answer'], stale)

    def test_labelled_soap_keeps_complete_measurement_phrase_and_separate_typed_numeric_value(self):
        labels = ('Subjective', 'Objective', 'Assessment', 'Plan', 'Pain score0 to 10')
        fields = [{'key': 'soap_'+str(index), 'label': label, 'kind': 'text', 'locator': {'cell': index}}
                  for index, label in enumerate(labels)]
        definitions = default_definitions(fields)
        definitions['soap_3']['scope']['temporality'] = 'future'
        notes = ('Subjective: Left ankle pain after stepping off a curb yesterday. Pain is 3 out of 10.\n'
                 'Objective: Mild swelling over the left lateral ankle, no deformity, and intact distal sensation.\n'
                 'Assessment: Left ankle pain.\n'
                 'Plan: Follow-up assessment in one week.')
        facts = [fact(notes, fields, 'symptom', 'Left ankle pain', kind='history'),
                 fact(notes, fields, 'mechanism', 'after stepping off a curb yesterday', kind='history',
                      timing='past', timing_quote='yesterday'),
                 fact(notes, fields, 'pain_narrative', 'Pain is 3 out of 10', kind='history', concept='pain_score'),
                 fact(notes, fields, 'pain_numeric', '3', kind='measurement', concept='pain_score',
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, '3 out of 10')}),
                 fact(notes, fields, 'swelling', 'Mild swelling over the left lateral ankle'),
                 fact(notes, fields, 'deformity', 'no deformity', polarity='negated'),
                 fact(notes, fields, 'sensation', 'intact distal sensation'),
                 fact(notes, fields, 'assessment', 'Left ankle pain', kind='assessment', occurrence=1),
                 fact(notes, fields, 'plan', 'Follow-up assessment in one week', kind='plan',
                      timing='future', timing_quote='in one week')]
        assigned = assignments(fields, {'soap_0': ['symptom', 'mechanism', 'pain_narrative'],
            'soap_1': ['swelling', 'deformity', 'sensation'], 'soap_2': ['assessment'],
            'soap_3': ['plan'], 'soap_4': ['pain_numeric']})
        sender = FixtureSender(facts, assigned)
        answers = semantic.run(notes, fields, definitions, sender)
        expected = {'soap_0': 'Left ankle pain; After stepping off a curb yesterday; Pain is 3 out of 10',
                    'soap_1': 'Mild swelling over the left lateral ankle; No deformity; Intact distal sensation',
                    'soap_2': 'Left ankle pain', 'soap_3': 'Follow-up assessment in one week', 'soap_4': '3'}
        for field in fields:
            answer = answers[field['key']]
            with self.subTest(field=field['key']):
                self.assertEqual((answer['text'], answer['status']), (expected[field['key']], 'supported'))
                self.assertFalse(answer['reviewed'])
                self.assertIs(semantic.validate_stored_answer(notes, field, definitions[field['key']], answer), answer)
                for evidence in answer['evidence']:
                    self.assertEqual(notes[evidence['start']:evidence['end']], evidence['quote'])
        self.assertEqual(answers['soap_4']['value'], 3)
        self.assertEqual([(role, attempt) for role, attempt, *_ in sender.calls],
                         [('extractor', 1), ('assigner', 1), ('checker', 1)])

    def test_bare_narrative_measurement_cannot_escape_by_extractor_kind_relabelling(self):
        fields, definitions = self.one_field('Subjective')
        notes = 'Subjective: Left ankle pain. Pain is 3 out of 10.'
        for kind in ('history', 'finding', 'other'):
            with self.subTest(kind=kind):
                facts = [fact(notes, fields, 'symptom', 'Left ankle pain', kind='history'),
                         fact(notes, fields, 'pain', '3', kind=kind, concept='pain_score',
                              scale={'minimum': None, 'maximum': '10', 'span': span(notes, '3 out of 10')})]
                answer = self.generated(notes, fields, definitions, facts, ['symptom', 'pain'])
                self.assert_held(answer)
                self.assertIn('complete documented measurement phrase', ' '.join(answer['review_reasons']))

    def test_numeric_measurement_peers_exclude_complete_same_concept_narrative_summary(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        notes = 'Pain is 3 out of 10. Pain is 3.0 out of 10.'
        facts = [fact(notes, fields, 'summary', 'Pain is 3 out of 10', kind='history', concept='pain_score'),
                 fact(notes, fields, 'score_integer', '3', kind='measurement', concept='pain_score',
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, '3 out of 10')}),
                 fact(notes, fields, 'score_decimal', '3.0', kind='measurement', concept='pain_score',
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, '3.0 out of 10')})]
        answer = self.generated(notes, fields, definitions, facts, ['score_integer'])
        self.assertEqual((answer['text'], answer['value'], answer['status']), ('3', 3, 'supported'))
        self.assertFalse(answer['reviewed'])
        self.assertIs(semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer), answer)

    def test_equal_measurement_numbers_on_conflicting_scales_stay_held_with_both_contexts(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        notes = 'Pain is 3 out of 5. Pain is 3 out of 10.'
        facts = [fact(notes, fields, 'score_'+denominator, '3', kind='measurement', concept='pain_score',
                      occurrence=index, scale={'minimum': None, 'maximum': denominator,
                                               'span': span(notes, '3 out of '+denominator)})
                 for index, denominator in enumerate(('5', '10'))]
        answer = self.generated(notes, fields, definitions, facts, ['score_10'])
        self.assert_held(answer)
        self.assertIn('conflicting values', ' '.join(answer['review_reasons']))
        self.assertEqual([item['quote'] for item in answer['evidence']],
                         ['Pain is 3 out of 10.', 'Pain is 3 out of 5.'])

    def one_field(self, label='Findings', **scope):
        fields = [{'key': 'answer', 'label': label, 'kind': 'text', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        definitions['answer']['scope'].update(scope)
        return fields, definitions

    def generated(self, notes, fields, definitions, facts, ids, **kwargs):
        assigned = assignments(fields, {fields[0]['key']: ids})
        return semantic.run(notes, fields, definitions, FixtureSender(facts, assigned, **kwargs))[fields[0]['key']]

    def assert_held(self, answer):
        self.assertEqual(answer['text'], '')
        self.assertNotEqual(answer['status'], 'supported')
        self.assertFalse(answer['reviewed'])

    def test_fact_offsets_unit_ids_and_duplicate_fact_ids_cannot_be_fabricated(self):
        fields, definitions, facts, assigned = alex_case()
        for change in ('negative_offset', 'outside_note', 'wrong_unit', 'duplicate_id', 'boolean_id', 'unknown_id'):
            changed = deepcopy(facts)
            if change == 'negative_offset': changed[0]['value_span']['start'] = -1
            elif change == 'outside_note': changed[0]['value_span']['end'] = len(NOTES)+1
            elif change == 'wrong_unit': changed[0]['source_unit_ids'] = [5]
            elif change == 'duplicate_id': changed[1]['id'] = changed[0]['id']
            elif change == 'boolean_id': changed[0]['source_unit_ids'] = [True]
            else: changed[0]['source_unit_ids'] = [6]
            with self.subTest(change=change), self.assertRaises(ValidationError):
                semantic.validate_facts(NOTES, generation.source_units(NOTES, fields)[0], {'facts': changed})

    def test_assigner_cannot_supply_composed_text_or_another_destination(self):
        fields, definitions, facts, assigned = alex_case()
        for change in ('composed_text', 'unknown_key', 'duplicate_key', 'unknown_fact', 'omitted_field'):
            changed = deepcopy(assigned)
            if change == 'composed_text': changed['fields'][0]['text'] = 'Invented patient'
            elif change == 'unknown_key': changed['fields'][0]['key'] = 'unapproved'
            elif change == 'duplicate_key': changed['fields'][1] = deepcopy(changed['fields'][0])
            elif change == 'unknown_fact': changed['fields'][0]['fact_ids'] = ['invented']
            else: changed['fields'].pop()
            sender = FixtureSender(facts, changed)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                semantic.run(NOTES, fields, definitions, sender)
            self.assertEqual(len(sender.calls), 2)

    def test_compound_positive_measurement_does_not_inherit_later_negative_history(self):
        fields, definitions, facts, assigned = alex_case()
        answers = semantic.run(NOTES, fields, definitions, FixtureSender(facts, assigned))
        self.assertEqual(answers['cell_4']['text'], '3')
        self.assertEqual(answers['cell_4']['value'], 3)
        self.assertEqual(answers['cell_4']['scale'], {'scale_minimum': '0', 'scale_maximum': '10'})
        self.assertIn('No head injury', answers['cell_2']['text'])

    def test_direct_negation_cannot_be_marked_positive_even_if_checker_passes(self):
        fields, definitions = self.one_field()
        notes = 'The patient reports no head injury.'
        facts = [fact(notes, fields, 'injury', 'head injury', polarity='affirmed')]
        self.assert_held(self.generated(notes, fields, definitions, facts, ['injury']))

    def test_shared_negation_survives_conjunction_without_a_new_subject_or_predicate(self):
        fields, definitions = self.one_field()
        notes = 'The patient denies fever and cough.'
        facts = [fact(notes, fields, 'cough', 'cough', polarity='affirmed')]
        self.assert_held(self.generated(notes, fields, definitions, facts, ['cough']))

    def test_negation_of_denial_and_no_change_do_not_become_absence_of_symptom(self):
        fields, definitions = self.one_field()
        for notes, quote in [('The patient does not deny fever.', 'fever'),
                             ('There is no change in ankle pain.', 'ankle pain')]:
            facts = [fact(notes, fields, 'symptom', quote, polarity='negated')]
            with self.subTest(notes=notes):
                self.assert_held(self.generated(notes, fields, definitions, facts, ['symptom']))

    def test_other_person_cannot_be_assigned_to_patient_field(self):
        fields, definitions = self.one_field()
        notes = 'The patient reports ankle pain. Mother reports diabetes.'
        facts = [fact(notes, fields, 'mother_diabetes', 'diabetes', subject='other', name_quote='Mother')]
        answer = self.generated(notes, fields, definitions, facts, ['mother_diabetes'])
        self.assert_held(answer)
        self.assertEqual(answer['evidence'][0]['quote'], 'Mother reports diabetes.')

    def test_named_subject_evidence_cannot_be_borrowed_from_an_unrelated_source_unit(self):
        fields, definitions = self.one_field(subject='other')
        notes = 'Mother reports diabetes. The patient reports ankle pain.'
        facts = [fact(notes, fields, 'pain', 'ankle pain', subject='other', name_quote='Mother')]
        try:
            answer = self.generated(notes, fields, definitions, facts, ['pain'])
        except ValidationError:
            return
        self.assert_held(answer)

    def test_citing_both_units_does_not_reassign_explicit_patient_fact_to_another_person(self):
        fields, definitions = self.one_field(subject='other')
        notes = 'Mother reports diabetes. The patient reports ankle pain.'
        facts = [fact(notes, fields, 'pain', 'ankle pain', subject='other', name_quote='Mother')]
        facts[0]['source_unit_ids'] = [unit['id'] for unit in generation.source_units(notes, fields)[0]]
        try:
            answer = self.generated(notes, fields, definitions, facts, ['pain'])
        except ValidationError:
            return
        self.assert_held(answer)

    def test_current_time_annotation_cannot_be_borrowed_for_explicitly_past_value(self):
        fields, definitions = self.one_field(temporality='current')
        notes = ('The patient had left ankle pain last year. '
                 'The patient currently has no ankle pain.')
        facts = [fact(notes, fields, 'pain', 'left ankle pain', timing='current', timing_quote='currently')]
        facts[0]['source_unit_ids'] = [unit['id'] for unit in generation.source_units(notes, fields)[0]]
        try:
            answer = self.generated(notes, fields, definitions, facts, ['pain'])
        except ValidationError:
            return
        self.assert_held(answer)

    def test_measurement_unit_cannot_be_borrowed_from_a_different_source_expression(self):
        fields, definitions = self.one_field('Vein diameter')
        definitions['answer'].update(value_type='number', unit='mm')
        notes = 'Vein diameter is 3 cm. Another diameter is 4 mm.'
        facts = [fact(notes, fields, 'diameter', '3', kind='measurement', unit='mm', unit_quote='mm')]
        facts[0]['source_unit_ids'] = [unit['id'] for unit in generation.source_units(notes, fields)[0]]
        try:
            answer = self.generated(notes, fields, definitions, facts, ['diameter'])
        except ValidationError:
            return
        self.assert_held(answer)

    def test_named_subject_annotation_cannot_override_explicit_patient_in_same_sentence(self):
        fields, definitions = self.one_field(subject='other')
        notes = 'Mother reports diabetes, and the patient reports ankle pain.'
        facts = [fact(notes, fields, 'pain', 'ankle pain', subject='other', name_quote='Mother')]
        try:
            answer = self.generated(notes, fields, definitions, facts, ['pain'])
        except ValidationError:
            return
        self.assert_held(answer)

    def test_measurement_unit_cannot_be_borrowed_from_a_different_number_in_same_sentence(self):
        fields, definitions = self.one_field('Vein diameter')
        definitions['answer'].update(value_type='number', unit='mm')
        notes = 'Vein diameter is 3 cm and another diameter is 4 mm.'
        facts = [fact(notes, fields, 'diameter', '3', kind='measurement', unit='mm', unit_quote='mm')]
        try:
            answer = self.generated(notes, fields, definitions, facts, ['diameter'])
        except ValidationError:
            return
        self.assert_held(answer)

    def test_numeric_source_value_cannot_drop_sign_or_leading_decimal_point(self):
        fields, definitions = self.one_field('Temperature')
        definitions['answer'].update(value_type='number', unit='C')
        for source_number, expected in [('-3', -3), ('.3', 0.3)]:
            notes = 'Temperature is '+source_number+' C.'
            with self.subTest(source_number=source_number):
                whole = [fact(notes, fields, 'temperature', source_number,
                              kind='measurement', unit='C', unit_quote='C')]
                preserved = self.generated(notes, fields, definitions, whole, ['temperature'])
                self.assertEqual((preserved['status'], preserved['value']), ('supported', expected))
                partial = [fact(notes, fields, 'temperature', '3',
                                kind='measurement', unit='C', unit_quote='C')]
                try:
                    answer = self.generated(notes, fields, definitions, partial, ['temperature'])
                except ValidationError:
                    continue
                self.assert_held(answer)

    def test_numeric_source_value_cannot_select_fragment_of_grouped_or_exponent_number(self):
        fields, definitions = self.one_field('Count')
        definitions['answer']['value_type'] = 'integer'
        for source_number, selected in (('1,000', '1'), ('1,000', '000'),
                                        ('1e3', '1'), ('1e3', '3'), ('1e-3', '-3')):
            notes = 'Count is '+source_number+'.'
            partial = [fact(notes, fields, 'count', selected, kind='measurement')]
            with self.subTest(source_number=source_number, selected=selected):
                try:
                    answer = self.generated(notes, fields, definitions, partial, ['count'])
                except ValidationError:
                    continue
                self.assert_held(answer)

    def test_partial_word_or_digit_spans_are_not_self_contained_answer_values(self):
        for notes, quote, label in [('Synthetic Alexander Morgan reports ankle pain.', 'Alex', 'Patient name'),
                                     ('Examination shows no swelling.', 'well', 'Findings'),
                                     ('The patient reports 13 episodes.', '3', 'Number of episodes')]:
            fields, definitions = self.one_field(label)
            facts = [fact(notes, fields, 'partial', quote)]
            with self.subTest(quote=quote):
                try:
                    answer = self.generated(notes, fields, definitions, facts, ['partial'])
                except ValidationError:
                    continue
                self.assert_held(answer)

    def test_displayed_fact_cannot_drop_adjacent_laterality_severity_or_anatomical_site(self):
        fields, definitions = self.one_field()
        for notes, quote in [('The patient reports left ankle pain.', 'ankle pain'),
                             ('Examination shows mild swelling over the left lateral ankle.', 'swelling'),
                             ('Examination shows swelling over the left lateral ankle.', 'swelling')]:
            facts = [fact(notes, fields, 'finding', quote)]
            with self.subTest(notes=notes):
                try:
                    answer = self.generated(notes, fields, definitions, facts, ['finding'])
                except ValidationError:
                    continue
                self.assert_held(answer)

    def test_family_heading_and_invisible_reframer_cannot_be_lost_from_atomic_fact(self):
        fields, definitions = self.one_field()
        for prefix in ('Family history:\n', 'Family hi\u200bstory is documented here.\n',
                       'The following symptoms are hypothetical.\n',
                       'Correction of a previous finding is required.\n'):
            notes = prefix+'The patient has diabetes.'
            facts = [fact(notes, fields, 'diabetes', 'diabetes')]
            answer = self.generated(notes, fields, definitions, facts, ['diabetes'])
            with self.subTest(prefix=prefix):
                self.assert_held(answer)
                self.assertTrue(any(prefix.strip() in evidence['quote'] for evidence in answer['evidence']))

    def test_scope_mismatch_and_uncertainty_remain_unreviewed(self):
        for case in ('past', 'future', 'uncertain', 'other_subject'):
            fields, definitions = self.one_field(temporality='current')
            if case == 'past':
                notes = 'Previously the patient had ankle pain.'
                facts = [fact(notes, fields, 'pain', 'ankle pain', timing='past', timing_quote='Previously')]
            elif case == 'future':
                notes = 'The plan is an assessment in one week.'
                facts = [fact(notes, fields, 'plan', 'assessment in one week', timing='future', timing_quote='in one week')]
            elif case == 'uncertain':
                notes = 'The patient may have ankle pain.'
                facts = [fact(notes, fields, 'pain', 'ankle pain', polarity='uncertain')]
            else:
                notes = 'The clinician has ankle pain.'
                facts = [fact(notes, fields, 'pain', 'ankle pain', subject='clinician')]
            with self.subTest(case=case):
                self.assert_held(self.generated(notes, fields, definitions, facts, [facts[0]['id']]))

    def test_missing_field_is_not_converted_to_a_negative_answer(self):
        fields, definitions = self.one_field('Head injury')
        notes = 'The patient has ankle pain.'
        answer = self.generated(notes, fields, definitions, [], [])
        self.assertEqual((answer['text'], answer['status'], answer['evidence'], answer['value']),
                         ('', 'missing', [], None))

    def test_numeric_scale_unit_and_integer_constraints_do_not_convert_source(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        for quote, maximum in [('3', '5'), ('3.5', '10'), ('11', '10')]:
            notes = 'The patient rates pain '+quote+' out of '+maximum+'.'
            facts = [fact(notes, fields, 'pain', quote, kind='measurement', concept='pain_score',
                          scale={'minimum': None, 'maximum': maximum,
                                 'span': span(notes, quote+' out of '+maximum)})]
            with self.subTest(quote=quote, maximum=maximum):
                self.assert_held(self.generated(notes, fields, definitions, facts, ['pain']))
        fields, definitions = self.one_field('Temperature')
        definitions['answer'].update(value_type='number', unit='°C')
        notes = 'The patient temperature is 98.6 °F.'
        facts = [fact(notes, fields, 'temperature', '98.6', kind='measurement', unit='°F', unit_quote='°F')]
        self.assert_held(self.generated(notes, fields, definitions, facts, ['temperature']))

    def test_conflicting_measurements_cannot_be_hidden_by_selecting_only_one(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        notes = 'The patient rates pain 3 out of 10. The patient rates pain 6 out of 10.'
        facts = [fact(notes, fields, 'pain_'+value, value, kind='measurement', concept='pain_score',
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, value+' out of 10')})
                 for value in ('3', '6')]
        self.assert_held(self.generated(notes, fields, definitions, facts, ['pain_3']))

    def test_opposite_polarities_for_same_concept_cannot_be_hidden_by_selecting_one(self):
        fields, definitions = self.one_field()
        notes = 'Examination shows ankle swelling. Examination shows no ankle swelling.'
        facts = [fact(notes, fields, 'yes', 'ankle swelling', concept='ankle_swelling'),
                 fact(notes, fields, 'no', 'no ankle swelling', concept='ankle_swelling', polarity='negated')]
        answer = self.generated(notes, fields, definitions, facts, ['yes'])
        self.assert_held(answer)
        self.assertEqual({entry['quote'] for entry in answer['evidence']},
                         {'Examination shows ankle swelling.', 'Examination shows no ankle swelling.'})

    def test_stated_nonzero_scale_minimum_cannot_be_discarded_when_maximum_matches(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        notes = 'The patient rates pain 3 on a 1 to 10 scale.'
        facts = [fact(notes, fields, 'pain', '3', kind='measurement', concept='pain_score',
                      scale={'minimum': '1', 'maximum': '10', 'span': span(notes, '1 to 10')})]
        self.assert_held(self.generated(notes, fields, definitions, facts, ['pain']))

    def test_scale_denominator_cannot_be_adopted_as_the_actual_pain_score(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        notes = 'The patient rates pain 3 out of 10.'
        facts = [fact(notes, fields, 'pain', '10', kind='measurement', concept='pain_score',
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, '3 out of 10')})]
        try:
            answer = self.generated(notes, fields, definitions, facts, ['pain'])
        except ValidationError:
            return
        self.assert_held(answer)

    def test_scale_bound_cannot_be_borrowed_from_a_different_measurement_in_same_sentence(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        notes = 'Today pain is 3 out of 5; yesterday pain was 10 out of 10.'
        facts = [fact(notes, fields, 'pain', '3', kind='measurement', concept='pain_score',
                      scale={'minimum': None, 'maximum': '10',
                             'span': span(notes, '3 out of 5; yesterday pain was 10 out of 10')})]
        try:
            answer = self.generated(notes, fields, definitions, facts, ['pain'])
        except ValidationError:
            return
        self.assert_held(answer)

    def test_explicit_correction_can_select_corrected_fact_and_retains_both_in_stored_proof(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        notes = 'The patient rates pain 3 out of 10. Correction: the patient rates pain 6 out of 10.'
        facts = [fact(notes, fields, 'pain_'+value, value, kind='measurement', concept='pain_score',
                      supersedes=['pain_3'] if value == '6' else [],
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, value+' out of 10')})
                 for value in ('3', '6')]
        answer = self.generated(notes, fields, definitions, facts, ['pain_6'])
        self.assertEqual((answer['text'], answer['value'], answer['status']), ('6', 6, 'supported'))
        self.assertIs(semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer), answer)
        self.assert_held(self.generated(notes, fields, definitions, facts, ['pain_3']))

    def test_checker_omission_gets_one_targeted_repair_and_an_independent_recheck(self):
        fields, definitions = self.one_field()
        notes = 'Examination shows swelling and no deformity.'
        facts = [fact(notes, fields, 'swelling', 'swelling'),
                 fact(notes, fields, 'deformity', 'no deformity', polarity='negated')]
        assigned = assignments(fields, {'answer': ['swelling']})
        checked = checker(assigned, verdicts={'answer': 'omission'})
        checked['fields'][0].update(fact_ids=['swelling', 'deformity'], reason='The stated negative finding was omitted.')
        repaired = assignments(fields, {'answer': ['swelling', 'deformity']})
        sender = FixtureSender(facts, assigned, checked, repaired=repaired)
        answer = semantic.run(notes, fields, definitions, sender)['answer']
        self.assertEqual((answer['text'], answer['status']), ('Swelling; No deformity', 'supported'))
        self.assertEqual([(role, attempt) for role, attempt, *_ in sender.calls],
                         [('extractor', 1), ('assigner', 1), ('checker', 1), ('assigner', 2), ('checker', 2)])
        self.assertEqual(sender.calls[3][2]['repair_keys'], ['answer'])
        self.assertFalse(answer['reviewed'])

    def test_second_checker_failure_is_held_without_an_unbounded_repair_loop(self):
        fields, definitions = self.one_field()
        notes = 'Examination shows swelling and no deformity.'
        facts = [fact(notes, fields, 'swelling', 'swelling')]
        assigned = assignments(fields, {'answer': ['swelling']})
        failed = checker(assigned, verdicts={'answer': 'omission'})
        failed['fields'][0]['reason'] = 'Relevant source content is absent from the facts.'
        sender = FixtureSender(facts, assigned, failed, repaired=assigned, rechecked=failed)
        answer = semantic.run(notes, fields, definitions, sender)['answer']
        self.assert_held(answer)
        self.assertEqual(len(sender.calls), semantic.MAX_CALLS)
        self.assertIn('Relevant source content is absent from the facts.', answer['review_reasons'])

    def test_checker_rejected_fact_cannot_be_laundered_through_assignment_repair(self):
        fields, definitions = self.one_field()
        notes = 'The patient has ankle pain.'
        facts = [fact(notes, fields, 'pain', 'ankle pain')]
        assigned = assignments(fields, {'answer': ['pain']})
        checked = checker(assigned, fact_findings=[{'fact_id': 'pain', 'verdict': 'incorrect',
                                                  'reason': 'The extracted fact has the wrong attribution.'}])
        sender = FixtureSender(facts, assigned, checked)
        self.assert_held(semantic.run(notes, fields, definitions, sender)['answer'])
        self.assertEqual(len(sender.calls), 3)

    def test_passing_checker_must_verify_selected_fact_ids_rather_than_another_fact(self):
        fields, definitions = self.one_field()
        notes = 'Examination shows swelling and intact sensation.'
        facts = [fact(notes, fields, 'swelling', 'swelling'),
                 fact(notes, fields, 'sensation', 'intact sensation')]
        assigned = assignments(fields, {'answer': ['swelling']})
        for checked_ids in ([], ['sensation'], ['swelling', 'swelling']):
            checked = checker(assigned)
            checked['fields'][0]['fact_ids'] = checked_ids
            with self.subTest(checked_ids=checked_ids):
                try:
                    answer = semantic.run(notes, fields, definitions,
                                          FixtureSender(facts, assigned, checked))['answer']
                except ValidationError:
                    continue
                self.assert_held(answer)

    def test_passing_checker_cannot_add_contextual_fact_without_a_clinical_finding(self):
        fields, definitions = self.one_field('Subjective')
        notes = 'Subjective: Left ankle pain. Pain is 3 out of 10.'
        facts = [fact(notes, fields, 'symptom', 'Left ankle pain', kind='history'),
                 fact(notes, fields, 'pain_narrative', 'Pain is 3 out of 10', kind='history', concept='pain_score'),
                 fact(notes, fields, 'pain_numeric', '3', kind='measurement', concept='pain_score',
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, '3 out of 10')})]
        assigned = assignments(fields, {'answer': ['symptom', 'pain_narrative']})
        for checked_ids in (['symptom', 'pain_narrative', 'pain_numeric'],
                            ['symptom', 'pain_numeric'], ['symptom']):
            checked = checker(assigned)
            checked['fields'][0]['fact_ids'] = checked_ids
            sender = FixtureSender(facts, assigned, checked)
            with self.subTest(checked_ids=checked_ids):
                answer = semantic.run(notes, fields, definitions, sender)['answer']
                self.assert_held(answer)
                self.assertEqual(answer['candidate_text'], 'Left ankle pain; Pain is 3 out of 10')
                self.assertEqual(answer['fact_ids'], ['symptom', 'pain_narrative'])
                self.assertIn('does not bind exactly', ' '.join(answer['review_reasons']))
                self.assertEqual([(role, attempt) for role, attempt, *_ in sender.calls],
                                 [('extractor', 1), ('assigner', 1), ('checker', 1)])
                stale = deepcopy(answer)
                stale.update(status='supported', text=answer['candidate_text'], value=answer['candidate_text'])
                with self.assertRaises(ValidationError):
                    semantic.validate_stored_answer(notes, fields[0], definitions['answer'], stale)

    def test_retained_soap_context_id_mismatch_is_held_and_exact_binding_preserves_all_facts(self):
        # The retained public SOAP attempt selected f1/f3/f4. Its checker said
        # pass but also listed f2, the separate numeric version of the same pain.
        notes = ('Subjective: The patient reports left ankle pain after stepping off a curb yesterday. '
                 'Pain is 3 out of 10. No head injury.\r\n\r\n'
                 'Objective: Mild swelling over the left lateral ankle. No deformity. Distal sensation intact.\r\n\r\n'
                 'Assessment: Left ankle pain.\r\n\r\nPlan: Follow-up in one week.')
        self.assertEqual(hashlib.sha256(notes.encode()).hexdigest(),
                         'a023de599fb1359ae7319b28a28e9a8325dbcab70bb2ba70832296000e4bbaa8')
        fields = [{'key': 'cell_'+str(i), 'label': label, 'kind': 'text', 'locator': {'cell': i}}
                  for i, label in enumerate(('Subjective', 'Objective', 'Assessment', 'Plan'))]
        definitions = default_definitions(fields)
        facts = [fact(notes, fields, 'f1', 'left ankle pain after stepping off a curb yesterday', kind='reason',
                      concept='left ankle pain', timing='past', timing_quote='yesterday'),
                 fact(notes, fields, 'f2', '3', kind='measurement', concept='pain severity',
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, '3 out of 10')}),
                 fact(notes, fields, 'f3', 'Pain is 3 out of 10', kind='history', concept='pain severity text'),
                 fact(notes, fields, 'f4', 'No head injury', kind='history', concept='head injury',
                      polarity='negated', timing='unspecified'),
                 fact(notes, fields, 'f5', 'Mild swelling over the left lateral ankle', concept='swelling'),
                 fact(notes, fields, 'f6', 'No deformity', concept='deformity', polarity='negated'),
                 fact(notes, fields, 'f7', 'Distal sensation intact', concept='distal sensation'),
                 fact(notes, fields, 'f8', 'Left ankle pain', kind='assessment', concept='assessment'),
                 fact(notes, fields, 'f9', 'Follow-up in one week', kind='follow_up',
                      concept='follow-up', timing='future', timing_quote='in one week')]
        assigned = assignments(fields, {'cell_0': ['f1', 'f3', 'f4'], 'cell_1': ['f5', 'f6', 'f7'],
                                        'cell_2': ['f8'], 'cell_3': ['f9']})
        expected = {'cell_0': 'Left ankle pain after stepping off a curb yesterday; Pain is 3 out of 10; No head injury',
                    'cell_1': 'Mild swelling over the left lateral ankle; No deformity; Distal sensation intact',
                    'cell_2': 'Left ankle pain', 'cell_3': 'Follow-up in one week'}
        for mismatch in (True, False):
            checked = checker(assigned)
            if mismatch:
                checked['fields'][0]['fact_ids'] = ['f1', 'f2', 'f3', 'f4']
            sender = FixtureSender(facts, assigned, checked)
            with self.subTest(mismatch=mismatch):
                answers = semantic.run(notes, fields, definitions, sender)
                self.assertEqual(len(sender.calls), 3)
                self.assertEqual(answers['cell_0']['fact_ids'], ['f1', 'f3', 'f4'])
                for field in fields:
                    key = field['key']; answer = answers[key]
                    self.assertFalse(answer['reviewed'])
                    if key == 'cell_0' and mismatch:
                        self.assert_held(answer)
                        self.assertEqual(answer['candidate_text'], expected[key])
                    else:
                        self.assertEqual((answer['text'], answer['status']), (expected[key], 'supported'))
                        self.assertIs(semantic.validate_stored_answer(notes, field, definitions[key], answer), answer)
                    for evidence in answer['evidence']:
                        self.assertEqual(notes[evidence['start']:evidence['end']], evidence['quote'])

    def test_passing_checker_id_order_does_not_change_answer_order_or_discard_negation(self):
        fields, definitions = self.one_field()
        notes = 'Examination shows swelling and no deformity.'
        facts = [fact(notes, fields, 'swelling', 'swelling'),
                 fact(notes, fields, 'deformity', 'no deformity', polarity='negated')]
        assigned = assignments(fields, {'answer': ['swelling', 'deformity']})
        checked = checker(assigned)
        checked['fields'][0]['fact_ids'].reverse()
        sender = FixtureSender(facts, assigned, checked)
        answer = semantic.run(notes, fields, definitions, sender)['answer']
        self.assertEqual((answer['text'], answer['status']), ('Swelling; No deformity', 'supported'))
        self.assertEqual(answer['fact_ids'], ['swelling', 'deformity'])
        self.assertFalse(answer['reviewed'])
        self.assertEqual(len(sender.calls), 3)
        self.assertIs(semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer), answer)

    def test_targeted_omission_recheck_still_holds_a_passing_mismatched_fact_set(self):
        fields, definitions = self.one_field()
        notes = 'Examination shows swelling, no deformity, and intact sensation.'
        facts = [fact(notes, fields, 'swelling', 'swelling'),
                 fact(notes, fields, 'deformity', 'no deformity', polarity='negated'),
                 fact(notes, fields, 'sensation', 'intact sensation')]
        assigned = assignments(fields, {'answer': ['swelling']})
        first = checker(assigned, verdicts={'answer': 'omission'})
        first['fields'][0].update(fact_ids=['swelling', 'deformity', 'sensation'],
                                  reason='The documented negative and sensation were omitted.')
        repaired = assignments(fields, {'answer': ['swelling', 'deformity', 'sensation']})
        second = checker(repaired)
        second['fields'][0]['fact_ids'] = ['swelling', 'sensation']
        sender = FixtureSender(facts, assigned, first, repaired=repaired, rechecked=second)
        answer = semantic.run(notes, fields, definitions, sender)['answer']
        self.assert_held(answer)
        self.assertEqual(answer['candidate_text'], 'Swelling; No deformity; Intact sensation')
        self.assertEqual(answer['fact_ids'], ['swelling', 'deformity', 'sensation'])
        self.assertIn('does not bind exactly', ' '.join(answer['review_reasons']))
        self.assertEqual(len(sender.calls), semantic.MAX_CALLS)

    def test_checker_cannot_invent_or_repeat_a_selected_fact_id(self):
        fields, definitions = self.one_field()
        notes = 'Examination shows swelling.'
        facts = [fact(notes, fields, 'swelling', 'swelling')]
        assigned = assignments(fields, {'answer': ['swelling']})
        for checked_ids in (['invented'], ['swelling', 'swelling']):
            checked = checker(assigned)
            checked['fields'][0]['fact_ids'] = checked_ids
            sender = FixtureSender(facts, assigned, checked)
            with self.subTest(checked_ids=checked_ids), self.assertRaises(ValidationError):
                semantic.run(notes, fields, definitions, sender)
            self.assertEqual(len(sender.calls), 3)

    def test_targeted_repair_cannot_reuse_an_initially_rejected_unselected_fact(self):
        fields, definitions = self.one_field()
        notes = 'Examination shows swelling and intact sensation.'
        facts = [fact(notes, fields, 'swelling', 'swelling'),
                 fact(notes, fields, 'sensation', 'intact sensation')]
        assigned = assignments(fields, {'answer': ['swelling']})
        first = checker(assigned, verdicts={'answer': 'incorrect'}, fact_findings=[
            {'fact_id': 'sensation', 'verdict': 'incorrect', 'reason': 'The sensation attribution is unresolved.'}])
        repaired = assignments(fields, {'answer': ['sensation']})
        sender = FixtureSender(facts, assigned, first, repaired=repaired, rechecked=checker(repaired))
        answer = semantic.run(notes, fields, definitions, sender)['answer']
        self.assert_held(answer)
        self.assertIn('The sensation attribution is unresolved.', answer['review_reasons'])

    def test_generated_signatures_remain_manual_but_documented_dates_are_source_driven(self):
        for label in ('Patient signature', 'Signed by (witness)', 'Electronically signed by'):
            fields, definitions = self.one_field(label)
            notes = 'Synthetic Alex Morgan signed the form.'
            facts = [fact(notes, fields, 'signature', 'Synthetic Alex Morgan', kind='identity')]
            with self.subTest(label=label):
                self.assert_held(self.generated(notes, fields, definitions, facts, ['signature']))
        fields, definitions = self.one_field('Date of signature')
        notes = 'The date of signature is 2026-10-10.'
        facts = [fact(notes, fields, 'signature_date', '2026-10-10', kind='other')]
        answer = self.generated(notes, fields, definitions, facts, ['signature_date'])
        self.assertEqual((answer['text'], answer['status']), ('2026-10-10', 'supported'))

    def test_approved_printed_date_formats_do_not_require_rewriting_the_notes(self):
        for printed, quote in [('YYYY-MM-DD', '2026-10-09'), ('DD/MM/YYYY', '09/10/2026'),
                               ('MM/DD/YYYY', '10/09/2026'), ('DD-MM-YYYY', '09-10-2026'),
                               ('MM-DD-YYYY', '10-09-2026')]:
            fields = [{'key': 'date', 'label': 'Visit date ('+printed+')', 'kind': 'text',
                       'locator': {'cell': 0}, 'answer_constraints': {
                           'version': 1, 'data_type': 'date', 'format': printed}}]
            definitions = default_definitions(fields)
            notes = 'The visit date is '+quote+'.'
            facts = [fact(notes, fields, 'visit_date', quote, kind='other')]
            with self.subTest(printed=printed):
                answer = self.generated(notes, fields, definitions, facts, ['visit_date'])
                self.assertEqual((answer['text'], answer['status']), (quote, 'supported'))
                self.assertIs(semantic.validate_stored_answer(notes, fields[0], definitions['date'], answer), answer)

    def test_stored_generated_text_source_definition_and_fact_proof_cannot_drift(self):
        fields, definitions, facts, assigned = alex_case()
        answer = semantic.run(NOTES, fields, definitions, FixtureSender(facts, assigned))['cell_4']
        self.assertIs(semantic.validate_stored_answer(NOTES, fields[4], definitions['cell_4'], answer), answer)
        for change in ('text', 'value', 'source', 'definition', 'fact', 'check', 'evidence_removed'):
            changed = deepcopy(answer); notes = NOTES; definition = deepcopy(definitions['cell_4'])
            if change == 'text': changed['text'] = '4'
            elif change == 'value': changed['value'] = 4
            elif change == 'source': notes += ' The patient has fever.'
            elif change == 'definition': definition['meaning'] += ' Changed.'
            elif change == 'fact': changed['facts'][0]['value_span']['start'] += 1
            elif change == 'check': changed['independent_check']['verdict'] = 'incorrect'
            else: changed['evidence'] = []
            with self.subTest(change=change), self.assertRaises(ValidationError):
                semantic.validate_stored_answer(notes, fields[4], definition, changed)

    def test_stale_supported_status_cannot_hide_global_conflicting_measurements(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        notes = 'The patient rates pain 3 out of 10. The patient rates pain 6 out of 10.'
        facts = [fact(notes, fields, 'pain_'+value, value, kind='measurement', concept='pain_score',
                      scale={'minimum': None, 'maximum': '10', 'span': span(notes, value+' out of 10')})
                 for value in ('3', '6')]
        answer = self.generated(notes, fields, definitions, facts, ['pain_3'])
        self.assert_held(answer)
        answer.update(status='supported', text='3', value=3)
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)

    def test_hidden_invalid_proof_is_not_cleared_by_a_review_tick_and_ordinary_save(self):
        from core import semantic_review
        fields, definitions, facts, assigned = alex_case()
        previous = semantic.run(NOTES, fields, definitions, FixtureSender(facts, assigned))['cell_1']
        previous['semantic_proof_sha256'] = '0'*64
        encounter = SimpleNamespace(notes=NOTES, status='draft', department=SimpleNamespace())
        actor = SimpleNamespace(pk='11111111-1111-4111-8111-111111111111')
        shown = semantic_review.displayed_answer(encounter, fields[1], previous, definitions)
        self.assertEqual((shown['text'], shown['status']), ('', 'conflict'))
        before = deepcopy(previous)
        with patch.object(semantic_review, 'membership'):
            with self.assertRaises(ValidationError):
                semantic_review.save_answer(encounter, fields[1], previous, shown['text'],
                                            actor, True, False, 2, definitions)
            blank = semantic_review.save_answer(encounter, fields[1], previous, '',
                                                actor, True, True, 2, definitions)
            entered = semantic_review.save_answer(encounter, fields[1], previous, 'Clinician reviewed ankle pain',
                                                  actor, True, False, 2, definitions)
        self.assertEqual(previous, before)
        self.assertEqual((blank['text'], blank['status'], blank['semantic_review_mode']), ('', 'left_blank', 'manual'))
        self.assertEqual(blank['semantic_edit_history'][-1]['previous']['text'], previous['text'])
        self.assertEqual((entered['text'], entered['status'], entered['semantic_review_mode']),
                         ('Clinician reviewed ankle pain', 'edited', 'manual'))
        self.assertIs(semantic_review.validate_answer(encounter, fields[1], blank, definitions), blank)
        self.assertIs(semantic_review.validate_answer(encounter, fields[1], entered, definitions), entered)

    def test_standalone_manual_marker_cannot_waive_generated_source_proof(self):
        fields, definitions, facts, assigned = alex_case()
        answer = semantic.run(NOTES, fields, definitions, FixtureSender(facts, assigned))['cell_1']
        answer.update(semantic_review_mode='manual', text='Confirmed acute ankle fracture',
                      value='Confirmed acute ankle fracture', reviewed=True)
        with self.assertRaises(ValidationError):
            semantic.validate_stored_answer(NOTES, fields[1], definitions['cell_1'], answer)

    def test_manual_decision_record_and_typed_value_must_remain_internally_consistent(self):
        from core import semantic_review
        fields, definitions, facts, assigned = alex_case()
        previous = semantic.run(NOTES, fields, definitions, FixtureSender(facts, assigned))['cell_1']
        encounter = SimpleNamespace(notes=NOTES, status='draft', department=SimpleNamespace())
        actor = SimpleNamespace(pk='11111111-1111-4111-8111-111111111111')
        with patch.object(semantic_review, 'membership'):
            original = semantic_review.save_answer(encounter, fields[1], previous,
                'Clinician reviewed ankle pain', actor, True, False, 2, definitions)
        self.assertIs(semantic.validate_stored_answer(NOTES, fields[1], definitions['cell_1'], original), original)
        for change in ('status', 'history', 'actor', 'time', 'revision', 'previous', 'decision', 'value'):
            modified = deepcopy(original)
            last = modified['semantic_edit_history'][-1]
            if change == 'status': modified['status'] = 'supported'
            elif change == 'history': modified['semantic_edit_history'] = []
            elif change == 'actor': last['by'] = 'unidentified editor'
            elif change == 'time': last['at'] = '2026-10-10T12:00:00'
            elif change == 'revision': last['revision'] = True
            elif change == 'previous': last.pop('previous')
            elif change == 'decision': last['decision'] = 'reviewed'
            else: modified['value'] = 3
            with self.subTest(change=change), self.assertRaises(ValidationError):
                semantic.validate_stored_answer(NOTES, fields[1], definitions['cell_1'], modified)


class SemanticSourceScaleContractTests(SimpleTestCase):
    def test_served_invented_zero_minimum_still_refuses_before_assignment(self):
        fields, definitions, facts, assigned = alex_case()
        pain = next(item for item in facts if item['id'] == 'pain')
        # The retained live extractor supplied exactly this unsupported bound.
        pain['scale'] = {'minimum': '0', 'maximum': '10',
                         'span': span(NOTES, 'out of 10')}
        sender = FixtureSender(facts, assigned)
        with self.assertRaisesMessage(ValidationError, 'A scale bound is absent from its exact source evidence.'):
            semantic.run(NOTES, fields, definitions, sender)
        self.assertEqual([(role, attempt) for role, attempt, *_ in sender.calls], [('extractor', 1)])

    def test_source_minimum_null_preserves_typed_three_and_approved_zero_to_ten(self):
        fields, definitions, facts, assigned = alex_case()
        pain = next(item for item in facts if item['id'] == 'pain')
        pain['scale']['span'] = span(NOTES, 'out of 10')
        sender = FixtureSender(facts, assigned)
        answer = semantic.run(NOTES, fields, definitions, sender)['cell_4']
        self.assertEqual((answer['text'], answer['value'], answer['status']), ('3', 3, 'supported'))
        self.assertFalse(answer['reviewed'])
        retained_pain = next(item for item in answer['facts'] if item['id'] == 'pain')
        self.assertIsNone(retained_pain['scale']['minimum'])
        self.assertEqual(retained_pain['scale']['maximum'], '10')
        self.assertEqual(answer['scale'], {'scale_minimum': '0', 'scale_maximum': '10'})
        semantic.validate_stored_answer(NOTES, fields[4], definitions['cell_4'], answer)
        _, _, payload, schema, instructions = sender.calls[0]
        self.assertEqual(payload['approved_definitions']['cell_4']['constraints']['scale_minimum'], '0')
        minimum = schema['properties']['facts']['items']['properties']['scale']['anyOf'][0]['properties']['minimum']
        self.assertIn('null when absent', minimum['description'])
        self.assertIn('approved field minimum', minimum['description'])
        self.assertIn('set scale.minimum to null', instructions)
        self.assertIn('causal or timing connector', instructions)

    def test_denominator_and_point_scales_do_not_supply_an_unstated_lower_bound(self):
        fields = [{'key': 'answer', 'label': 'Pain score0 to 10', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        for expression, scale_quote in [('3 out of 10', 'out of 10'), ('3/10', '/10'),
                                        ('3 on a 10-point scale', '10-point scale')]:
            notes = 'The patient rates pain '+expression+'.'
            facts = [fact(notes, fields, 'pain', '3', kind='measurement',
                          scale={'minimum': None, 'maximum': '10', 'span': span(notes, scale_quote)})]
            assigned = assignments(fields, {'answer': ['pain']})
            with self.subTest(expression=expression):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, assigned))['answer']
                self.assertEqual((answer['text'], answer['value'], answer['status']), ('3', 3, 'supported'))
                self.assertIsNone(answer['facts'][0]['scale']['minimum'])
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)

    def test_explicit_source_lower_bound_is_retained_and_cannot_be_erased(self):
        fields = [{'key': 'answer', 'label': 'Pain score1 to 10', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        notes = 'The patient rates pain 3 on a 1 to 10 scale.'
        facts = [fact(notes, fields, 'pain', '3', kind='measurement',
                      scale={'minimum': '1', 'maximum': '10', 'span': span(notes, '1 to 10')})]
        assigned = assignments(fields, {'answer': ['pain']})
        answer = semantic.run(notes, fields, definitions, FixtureSender(facts, assigned))['answer']
        self.assertEqual((answer['value'], answer['status']), (3, 'supported'))
        self.assertEqual(answer['facts'][0]['scale']['minimum'], '1')
        facts[0]['scale']['minimum'] = None
        with self.assertRaisesMessage(ValidationError, 'The proposed measurement scale changes its exact source bounds.'):
            semantic.run(notes, fields, definitions, FixtureSender(facts, assigned))

    def test_approved_scale_cannot_fill_missing_source_scale(self):
        fields = [{'key': 'answer', 'label': 'Pain score0 to 10', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        notes = 'The patient rates pain 3.'
        facts = [fact(notes, fields, 'pain', '3', kind='measurement')]
        assigned = assignments(fields, {'answer': ['pain']})
        answer = semantic.run(notes, fields, definitions, FixtureSender(facts, assigned))['answer']
        self.assertEqual((answer['text'], answer['value']), ('', None))
        self.assertNotEqual(answer['status'], 'supported')
        self.assertFalse(answer['reviewed'])

    def test_history_keeps_exact_causal_and_timing_relationships(self):
        fields = [{'key': 'answer', 'label': 'History', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        for notes, phrase in [
                ('The patient reports wrist pain after lifting a box yesterday.', 'after lifting a box yesterday'),
                ('The patient reports nausea since last week.', 'since last week'),
                ('The patient reports dizziness before the fall.', 'before the fall')]:
            facts = [fact(notes, fields, 'history', phrase, kind='history', timing='past')]
            assigned = assignments(fields, {'answer': ['history']})
            with self.subTest(phrase=phrase):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, assigned))['answer']
                self.assertEqual((answer['text'], answer['status']), (phrase[0].upper()+phrase[1:], 'supported'))
                self.assertEqual(answer['facts'][0]['value_evidence']['quote'], phrase)
                self.assertEqual(answer['evidence'][0]['quote'], notes)
                self.assertFalse(answer['reviewed'])


class SemanticNumberWordTests(SimpleTestCase):
    def configured(self, label='Pain score0 to 10'):
        fields = [{'key': 'answer', 'label': label, 'locator': {'cell': 0}}]
        return fields, default_definitions(fields)

    def measured(self, notes, quote='six', *, scale_quote='out of ten', minimum=None,
                 maximum='10', label='Pain score0 to 10', polarity='affirmed'):
        fields, definitions = self.configured(label)
        scale = None if scale_quote is None else {'minimum': minimum, 'maximum': maximum,
                                                  'span': span(notes, scale_quote)}
        facts = [fact(notes, fields, 'pain', quote, kind='measurement', concept='pain_score',
                      polarity=polarity, scale=scale)]
        selected = assignments(fields, {'answer': ['pain']})
        return fields, definitions, facts, selected

    def test_exact_six_out_of_ten_becomes_typed_six_with_original_word_evidence(self):
        notes = 'The patient rates the right wrist pain as six out of ten.'
        fields, definitions, facts, selected = self.measured(notes)
        before = deepcopy(facts)
        sender = FixtureSender(facts, selected)
        answer = semantic.run(notes, fields, definitions, sender)['answer']
        self.assertEqual((answer['text'], answer['value'], answer['status']), ('6', 6, 'supported'))
        self.assertIs(type(answer['value']), int)
        self.assertFalse(answer['reviewed'])
        retained = answer['facts'][0]
        self.assertEqual(retained['value_evidence'], {**span(notes, 'six'), 'quote': 'six'})
        self.assertEqual(retained['scale']['evidence'], {**span(notes, 'out of ten'), 'quote': 'out of ten'})
        self.assertIsNone(retained['scale']['minimum'])
        self.assertEqual(retained['scale']['maximum'], '10')
        self.assertEqual(answer['scale'], {'scale_minimum': '0', 'scale_maximum': '10'})
        self.assertEqual(answer['evidence'], [{'start': 0, 'end': len(notes), 'quote': notes}])
        self.assertEqual(facts, before)
        self.assertEqual([(role, attempt) for role, attempt, *_ in sender.calls],
                         [('extractor', 1), ('assigner', 1), ('checker', 1)])
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
        for changed in ('text', 'value', 'source_quote'):
            modified = deepcopy(answer)
            if changed == 'text': modified['text'] = 'Six'
            elif changed == 'value': modified['value'] = 6.0
            else: modified['facts'][0]['value_evidence']['quote'] = '6'
            with self.subTest(changed=changed), self.assertRaises(ValidationError):
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], modified)

    def test_digit_and_word_score_and_scale_combinations_use_same_source_binding(self):
        for expression, value, scale_quote in [
                ('six out of 10', 'six', 'out of 10'), ('6 out of ten', '6', 'out of ten'),
                ('SIX out of TEN', 'SIX', 'out of TEN'), ('six/ten', 'six', '/ten'),
                ('six / ten', 'six', '/ ten'),
                ('six on a ten-point scale', 'six', 'ten-point scale'),
                ('zero out of ten', 'zero', 'out of ten'), ('nine out of ten', 'nine', 'out of ten')]:
            notes = 'The patient rates pain '+expression+'.'
            fields, definitions, facts, selected = self.measured(notes, value, scale_quote=scale_quote)
            with self.subTest(expression=expression):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
                expected = {'zero': 0, 'nine': 9}.get(value, 6)
                self.assertEqual((answer['text'], answer['value'], answer['status']), (str(expected), expected, 'supported'))
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)

    def test_explicit_word_range_preserves_source_minimum_and_legacy_digit_range(self):
        for expression, scale_quote in [('six on a zero to ten scale', 'zero to ten'),
                                        ('six on a 0-10 scale', '0-10'),
                                        ('six on a 0–10 scale', '0–10')]:
            notes = 'The patient rates pain '+expression+'.'
            fields, definitions, facts, selected = self.measured(notes, scale_quote=scale_quote, minimum='0')
            with self.subTest(expression=expression):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
                self.assertEqual((answer['text'], answer['value'], answer['status']), ('6', 6, 'supported'))
                self.assertEqual(answer['facts'][0]['scale']['minimum'], '0')
                facts[0]['scale']['minimum'] = None
                with self.assertRaises(ValidationError):
                    semantic.run(notes, fields, definitions, FixtureSender(facts, selected))

    def test_supported_two_word_and_hyphenated_integers_retain_whole_value_span(self):
        for value, expected in [('twenty one', 21), ('twenty-one', 21), ('twenty  one', 21),
                                ('ninety nine', 99), ('ninety', 90), ('nineteen', 19)]:
            notes = 'The patient reports '+value+' episodes.'
            fields, definitions = self.configured('Episode count')
            definitions['answer']['value_type'] = 'integer'
            facts = [fact(notes, fields, 'episodes', value, kind='measurement')]
            selected = assignments(fields, {'answer': ['episodes']})
            with self.subTest(value=value):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
                self.assertEqual((answer['text'], answer['value'], answer['status']), (str(expected), expected, 'supported'))
                self.assertEqual(answer['facts'][0]['value_evidence']['quote'], value)
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)

    def test_partial_compounds_signed_words_and_fractions_refuse_before_assignment(self):
        for expression, selected_value in [
                ('six hundred', 'six'), ('one hundred and six', 'six'), ('sixty six', 'six'),
                ('sixty-six', 'sixty'), ('twenty one', 'twenty'), ('six point five', 'six'),
                ('one point six', 'six'), ('six and a half', 'six'),
                ('minus six', 'six'), ('negative six', 'six'), ('plus six', 'six'),
                ('- six', 'six'), ('−six', 'six'), ('6 hundred', '6')]:
            notes = 'The patient rates pain '+expression+' out of ten.'
            fields, definitions, facts, selected = self.measured(notes, selected_value)
            sender = FixtureSender(facts, selected)
            with self.subTest(expression=expression), self.assertRaises(ValidationError):
                semantic.run(notes, fields, definitions, sender)
            self.assertEqual(len(sender.calls), 1)

    def test_full_unsupported_numeric_expressions_remain_held_without_partial_conversion(self):
        for quote in ('one hundred', 'six point five', 'minus six', 'six and a half'):
            notes = 'The patient reports '+quote+' episodes.'
            fields, definitions = self.configured('Episode count')
            definitions['answer']['value_type'] = 'number'
            facts = [fact(notes, fields, 'episodes', quote, kind='measurement')]
            selected = assignments(fields, {'answer': ['episodes']})
            with self.subTest(quote=quote):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
                self.assertEqual((answer['text'], answer['value']), ('', None))
                self.assertNotEqual(answer['status'], 'supported')

    def test_scale_free_fragments_cannot_be_normalized_into_exact_counts(self):
        fields, definitions = self.configured('Episode count')
        definitions['answer']['value_type'] = 'integer'
        for expression, quote in [('six hundred', 'six'), ('sixty six', 'six'),
                                  ('six point five', 'six'), ('six and a half', 'six'),
                                  ('six-and-a-quarter', 'six'), ('six and a third', 'six'),
                                  ('six and one-hundredth', 'six'), ('six and one-millionth', 'six'),
                                  ('six and one-zillionth', 'six'), ('six and one-second', 'six'),
                                  ('minus six', 'six'), ('- six', 'six'), ('– six', 'six'),
                                  ('half of six', 'six'), ('about six', 'six'),
                                  ('six to seven', 'six'), ('six or seven', 'six'),
                                  ('six hundred', 'six '), ('minus six', ' six')]:
            notes = 'The patient reports '+expression+' episodes.'
            facts = [fact(notes, fields, 'count', quote, kind='measurement')]
            sender = FixtureSender(facts, assignments(fields, {'answer': ['count']}))
            with self.subTest(expression=expression), self.assertRaises(ValidationError):
                semantic.run(notes, fields, definitions, sender)
            self.assertEqual(len(sender.calls), 1)

    def test_compound_word_denominator_keeps_exact_whole_scale_value(self):
        notes = 'The patient rates pain twenty one out of ninety nine.'
        fields, definitions, facts, selected = self.measured(notes, 'twenty one',
            scale_quote='out of ninety nine', maximum='99', label='Pain score0 to 99')
        answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
        self.assertEqual((answer['text'], answer['value'], answer['status']), ('21', 21, 'supported'))
        self.assertEqual(answer['facts'][0]['value_evidence']['quote'], 'twenty one')
        self.assertEqual(answer['facts'][0]['scale']['evidence']['quote'], 'out of ninety nine')
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)

    def test_teen_denominators_match_whole_words_before_shorter_prefixes(self):
        for word, maximum in [('eleven', 11), ('twelve', 12), ('thirteen', 13), ('fourteen', 14),
                              ('fifteen', 15), ('sixteen', 16), ('seventeen', 17), ('eighteen', 18), ('nineteen', 19)]:
            notes = 'The patient rates pain six out of '+word+'.'
            fields, definitions, facts, selected = self.measured(notes, scale_quote='out of '+word,
                maximum=str(maximum), label='Pain score0 to '+str(maximum))
            with self.subTest(word=word):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
                self.assertEqual((answer['text'], answer['value'], answer['status']), ('6', 6, 'supported'))
                self.assertEqual(answer['facts'][0]['scale']['maximum'], str(maximum))
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)

    def test_unicode_boundaries_hidden_signs_and_fraction_tails_cannot_clip_to_integer(self):
        fields, definitions = self.configured('Episode count')
        definitions['answer']['value_type'] = 'integer'
        for expression, quote in [('six½', 'six'), ('six.5', 'six'), ('six,5', 'six'),
                                  ('six\u0301', 'six'), ('six_teen', 'six'), ('−\u200bsix', 'six'),
                                  ('minus\u200b six', 'six'), ('－six', 'six'),
                                  ('six-to-ten', 'six'), ('six–ten', 'six'), ('six – ten', 'six'),
                                  ('one-third', 'one'), ('two-thirds', 'two'), ('three fifths', 'three')]:
            notes = 'The patient reports '+expression+' episodes.'
            facts = [fact(notes, fields, 'count', quote, kind='measurement')]
            sender = FixtureSender(facts, assignments(fields, {'answer': ['count']}))
            with self.subTest(expression=expression), self.assertRaises(ValidationError):
                semantic.run(notes, fields, definitions, sender)
            self.assertEqual(len(sender.calls), 1)

    def test_count_and_separate_hyphenated_duration_are_not_a_compound_number(self):
        fields, definitions = self.configured('Episode count')
        definitions['answer']['value_type'] = 'integer'
        for value, modifier, expected in [('3', 'one-hour', 3), ('3', '1-hour', 3),
                                          ('six', 'one-hour', 6), ('six', 'one-second', 6)]:
            notes = 'The patient reports '+value+' '+modifier+' episodes.'
            facts = [fact(notes, fields, 'count', value, kind='measurement')]
            selected = assignments(fields, {'answer': ['count']})
            with self.subTest(value=value, modifier=modifier):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
                self.assertEqual((answer['text'], answer['value'], answer['status']), (str(expected), expected, 'supported'))
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)

    def test_unscaled_word_ratio_is_not_an_integer_count(self):
        for slash in ('/', '⁄', '∕'):
            for gap in ('', ' '):
                notes = 'The patient reports six'+gap+slash+gap+'ten episodes.'
                fields, definitions = self.configured('Episode count')
                definitions['answer']['value_type'] = 'integer'
                facts = [fact(notes, fields, 'count', 'six', kind='measurement')]
                selected = assignments(fields, {'answer': ['count']})
                with self.subTest(slash=slash, gap=gap), self.assertRaises(ValidationError):
                    semantic.run(notes, fields, definitions, FixtureSender(facts, selected))
        for ratio in ('six/ten', 'six / ten'):
            notes = 'The patient reports '+ratio+' episodes.'
            scale_quote = ratio[3:].lstrip()
            facts = [fact(notes, fields, 'count', 'six', kind='measurement',
                          scale={'minimum': None, 'maximum': '10', 'span': span(notes, scale_quote)})]
            answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
            self.assertEqual((answer['text'], answer['value']), ('', None))
            self.assertIn('A source ratio requires its explicitly documented matching approved measurement scale.', answer['review_reasons'])

    def test_denominator_cannot_be_clipped_from_another_ratio_or_range(self):
        for suffix in ('/three', ' / three', '⁄three', ' ⁄ three', '–twenty', ' – twenty',
                       ' to twenty', ' through twenty', ' out of twenty', '½', ' ½'):
            notes = 'The patient rates pain six out of ten'+suffix+'.'
            fields, definitions, facts, selected = self.measured(notes)
            sender = FixtureSender(facts, selected)
            with self.subTest(suffix=suffix), self.assertRaises(ValidationError):
                semantic.run(notes, fields, definitions, sender)
            self.assertEqual(len(sender.calls), 1)

    def test_plural_and_ordinal_fraction_prefixes_cannot_be_dropped(self):
        fields, definitions = self.configured('Episode count')
        definitions['answer']['value_type'] = 'integer'
        for prefix in ('two thirds of', 'three quarters of', 'one fifth of', 'two-thirds of',
                       'one third of', 'half of', 'three fourths of', 'one tenth of',
                       'one twenty-first of', 'two thirty seconds of', 'one hundredth of'):
            notes = 'The patient reports '+prefix+' six episodes.'
            facts = [fact(notes, fields, 'count', 'six', kind='measurement')]
            sender = FixtureSender(facts, assignments(fields, {'answer': ['count']}))
            with self.subTest(prefix=prefix), self.assertRaises(ValidationError):
                semantic.run(notes, fields, definitions, sender)
            self.assertEqual(len(sender.calls), 1)

    def test_word_scale_cannot_supply_zero_rescale_or_borrow_another_measurement(self):
        for notes, quote, scale_quote, minimum, maximum in [
                ('The patient rates pain six out of ten.', 'six', 'out of ten', '0', '10'),
                ('The patient rates pain six out of five.', 'six', 'out of five', None, '10'),
                ('The patient rates pain six out of one hundred.', 'six', 'out of one hundred', None, '1'),
                ('The patient rates pain six out of ten point five.', 'six', 'out of ten point five', None, '10'),
                ('The patient rates pain six out of five and anxiety two out of ten.', 'six', 'out of ten', None, '10'),
                ('The patient rates pain six out of ten.', 'ten', 'out of ten', None, '10')]:
            fields, definitions, facts, selected = self.measured(notes, quote, scale_quote=scale_quote,
                                                                minimum=minimum, maximum=maximum)
            with self.subTest(notes=notes, value=quote), self.assertRaises(ValidationError):
                semantic.run(notes, fields, definitions, FixtureSender(facts, selected))
        notes = 'The patient rates pain six out of twenty.'
        fields, definitions, facts, selected = self.measured(notes, scale_quote='out of twenty', maximum='20')
        answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
        self.assertEqual((answer['text'], answer['value']), ('', None))
        self.assertIn('The source scale differs from or does not establish the approved scale.', answer['review_reasons'])

    def test_negative_uncertain_and_other_subject_word_values_remain_held(self):
        for notes, polarity, subject in [
                ('The patient denies pain six out of ten.', 'affirmed', 'patient'),
                ('The patient denies pain six out of ten.', 'negated', 'patient'),
                ('The patient reports possible pain six out of ten.', 'uncertain', 'patient'),
                ('The patient reports pain six out of ten.', 'affirmed', 'uncertain')]:
            fields, definitions, facts, selected = self.measured(notes, polarity=polarity)
            facts[0]['subject']['kind'] = subject
            with self.subTest(notes=notes, polarity=polarity, subject=subject):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
                self.assertEqual((answer['text'], answer['value']), ('', None))
                self.assertNotEqual(answer['status'], 'supported')

    def test_word_and_digit_peers_agree_but_conflicting_value_or_scale_stays_held(self):
        for later, maximum, expected_status in [('6', '10', 'supported'), ('seven', '10', 'conflict'), ('six', '20', 'conflict')]:
            notes = 'The patient rates pain six out of ten. The patient now rates pain '+later+' out of '+maximum+'.'
            fields, definitions, facts, selected = self.measured(notes)
            facts += [fact(notes, fields, 'later', later, concept='pain_score', kind='measurement',
                           occurrence=1 if later == 'six' else 0,
                           scale={'minimum': None, 'maximum': maximum, 'span': span(notes, 'out of '+maximum)})]
            with self.subTest(later=later, maximum=maximum):
                answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
                self.assertEqual(answer['status'], expected_status)
                if expected_status == 'supported': self.assertEqual(answer['value'], 6)
                else:
                    self.assertEqual((answer['text'], answer['value']), ('', None))
                    self.assertEqual(len(answer['evidence']), 2)

    def test_explicit_word_correction_supersedes_only_old_measurement_and_preserves_both_facts(self):
        notes = 'The patient rates pain three out of ten. The patient corrects the pain score: actually six out of ten.'
        fields, definitions, facts, selected = self.measured(notes, 'three')
        facts += [fact(notes, fields, 'corrected', 'six', kind='measurement', concept='pain_score', supersedes=['pain'],
                       scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', 1)})]
        selected = assignments(fields, {'answer': ['corrected']})
        answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
        self.assertEqual((answer['text'], answer['value'], answer['status']), ('6', 6, 'supported'))
        self.assertEqual({item['value_evidence']['quote'] for item in answer['facts']}, {'three', 'six'})
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
        selected = assignments(fields, {'answer': ['pain']})
        held = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
        self.assertEqual((held['text'], held['value']), ('', None))
        self.assertIn('This fact was explicitly corrected by later source documentation.', held['review_reasons'])

    def test_narrative_fields_require_full_word_measurement_phrase_and_do_not_convert_words(self):
        notes = 'The patient reports pain six out of ten.'
        fields, definitions, facts, selected = self.measured(notes, label='History')
        held = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
        self.assertEqual((held['text'], held['value']), ('', None))
        facts += [fact(notes, fields, 'summary', 'pain six out of ten', kind='history', concept='pain_score')]
        selected = assignments(fields, {'answer': ['summary']})
        answer = semantic.run(notes, fields, definitions, FixtureSender(facts, selected))['answer']
        self.assertEqual((answer['text'], answer['value'], answer['status']),
                         ('Pain six out of ten', 'Pain six out of ten', 'supported'))
        self.assertEqual(answer['facts'][0]['value_evidence']['quote'], 'six')
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)


class SemanticSourceReferenceTests(SimpleTestCase):
    def test_exact_api_references_round_trip_to_canonical_original_character_offsets(self):
        fields, _, facts, _ = alex_case()
        units = generation.source_units(NOTES, fields)[0]
        raw = api_facts(NOTES, units, facts)
        before = deepcopy(raw)
        self.assertEqual(semantic.resolve_source_references(NOTES, units, raw), {'facts': facts})
        self.assertEqual(raw, before)
        self.assertFalse(semantic.API_FACT_SCHEMA['additionalProperties'])

    def test_unicode_and_repeated_quote_are_bound_to_explicit_within_unit_occurrence(self):
        fields = [{'key': 'answer', 'label': 'Symptoms', 'locator': {'cell': 0}}]
        notes = 'Synthetic Élise 王 reports pain and pain.'
        selected = fact(notes, fields, 'second_pain', 'pain', occurrence=1,
                        name_quote='Synthetic Élise 王')
        units = generation.source_units(notes, fields)[0]
        raw = api_facts(notes, units, [selected])
        self.assertEqual(raw['facts'][0]['value_span']['occurrence'], 2)
        resolved = semantic.resolve_source_references(notes, units, raw)['facts'][0]
        self.assertEqual(resolved, selected)
        self.assertEqual(notes[resolved['value_span']['start']:resolved['value_span']['end']], 'pain')

    def test_api_refuses_numeric_offset_fallback_and_extra_reference_keys(self):
        fields, _, facts, _ = alex_case()
        units = generation.source_units(NOTES, fields)[0]
        for change in ('offsets', 'extra', 'missing_quote', 'empty_quote'):
            raw = api_facts(NOTES, units, facts)
            ref = raw['facts'][0]['value_span']
            if change == 'offsets': raw['facts'][0]['value_span'] = deepcopy(facts[0]['value_span'])
            elif change == 'extra': ref['start'] = 0
            elif change == 'missing_quote': ref.pop('quote')
            else: ref['quote'] = ''
            with self.subTest(change=change), self.assertRaises(ValidationError):
                semantic.resolve_source_references(NOTES, units, raw)

    def test_api_requires_exact_unicode_quote_without_normalizing_or_nearest_match(self):
        fields = [{'key': 'answer', 'label': 'Patient name', 'locator': {'cell': 0}}]
        notes = 'Synthetic Élise 王 reports pain.'
        units = generation.source_units(notes, fields)[0]
        selected = fact(notes, fields, 'name', 'Synthetic Élise 王', kind='identity')
        for wrong in ('Synthetic E\u0301lise 王', 'synthetic Élise 王', 'Synthetic  Élise 王', 'Synthetic Alex Morgan'):
            raw = api_facts(notes, units, [selected]); raw['facts'][0]['value_span']['quote'] = wrong
            with self.subTest(wrong=wrong), self.assertRaises(ValidationError):
                semantic.resolve_source_references(notes, units, raw)

    def test_unknown_uncited_noninteger_unit_and_invalid_occurrence_are_refused(self):
        fields, _, facts, _ = alex_case()
        units = generation.source_units(NOTES, fields)[0]
        for attribute, wrong in [('source_unit_id', 6), ('source_unit_id', 2),
                                 ('source_unit_id', True), ('source_unit_id', '1'),
                                 ('occurrence', 0), ('occurrence', -1), ('occurrence', 2),
                                 ('occurrence', 50001), ('occurrence', True),
                                 ('occurrence', 1.0), ('occurrence', '1')]:
            raw = api_facts(NOTES, units, facts); raw['facts'][0]['value_span'][attribute] = wrong
            with self.subTest(attribute=attribute, wrong=wrong), self.assertRaises(ValidationError):
                semantic.resolve_source_references(NOTES, units, raw)

    def test_subject_timing_unit_and_scale_references_all_use_the_same_strict_resolver(self):
        fields, _, facts, _ = alex_case()
        units = generation.source_units(NOTES, fields)[0]
        for location in ('subject', 'timing', 'unit', 'scale'):
            raw = api_facts(NOTES, units, facts)
            bad = {'quote': 'invented source text', 'source_unit_id': 1, 'occurrence': 1}
            if location == 'subject': raw['facts'][0]['subject']['name_span'] = bad
            elif location == 'timing': raw['facts'][0]['timing']['span'] = bad
            elif location == 'unit': raw['facts'][0]['unit_span'] = bad
            else: raw['facts'][4]['scale']['span'] = bad
            with self.subTest(location=location), self.assertRaises(ValidationError):
                semantic.resolve_source_references(NOTES, units, raw)

    def test_original_source_units_cannot_be_substituted_after_reference_was_built(self):
        fields, _, facts, _ = alex_case()
        units = generation.source_units(NOTES, fields)[0]
        raw = api_facts(NOTES, units, facts)
        changed = deepcopy(units); changed[0]['quote'] = changed[0]['quote'].replace('Alex', 'Evan')
        with self.assertRaises(ValidationError):
            semantic.resolve_source_references(NOTES, changed, raw)

