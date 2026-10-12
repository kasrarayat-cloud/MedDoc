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


def inventory_api_facts(notes, units, facts):
    """Test-only explicit v2 envelope; no legacy source-reference fallback."""
    raw = api_facts(notes, units, facts)
    for value in raw['facts']:
        value.pop('source_unit_ids')
    return {'reference_contract': semantic.REFERENCE_INVENTORY_CONTRACT, **raw}


def declared_api_facts(notes, units, facts, reference_contract=semantic.LEGACY_REFERENCE_CONTRACT):
    if reference_contract == semantic.LEGACY_REFERENCE_CONTRACT:
        return api_facts(notes, units, facts)
    if reference_contract == semantic.REFERENCE_INVENTORY_CONTRACT:
        return inventory_api_facts(notes, units, facts)
    raise AssertionError('The fixture cannot fall back from an unknown reference contract.')


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
            return declared_api_facts(payload['notes'], payload['source_units'], result['facts'],
                                      payload.get('reference_contract', semantic.LEGACY_REFERENCE_CONTRACT))
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
    def test_own_visit_metadata_is_not_another_person_or_a_displayed_evidence_sentence(self):
        notes = ('Synthetic Ivo Fenrin, record reference TEST-P416, attended a review visit on 2027-01-08.')
        fields = [{'key': key, 'label': label, 'kind': 'text', 'locator': {'cell': index}}
                  for index, (key, label) in enumerate((('reference', 'Record reference'),
                      ('category', 'Category'), ('date', 'Visit date')))]
        definitions = default_definitions(fields)
        for key, value_type in (('reference', 'identifier'), ('category', 'choice'), ('date', 'date')):
            definitions[key].update(version=2, answer_mode='atomic', value_type=value_type)
            definitions[key]['scope'].update(subject='encounter', temporality='current')
        definitions['category']['choices'] = ['Initial', 'Review']
        facts = [fact(notes, fields, key, value, kind='other', name_quote='Synthetic Ivo Fenrin')
                 for key, value in (('reference', 'TEST-P416'), ('category', 'review'), ('date', '2027-01-08'))]
        selected = assignments(fields, {key: [key] for key in definitions})
        for contract in (semantic.LEGACY_REFERENCE_CONTRACT, semantic.REFERENCE_INVENTORY_CONTRACT):
            with self.subTest(contract=contract):
                sender = FixtureSender(facts, selected)
                answers = semantic.run(notes, fields, definitions, sender, reference_contract=contract)
                self.assertEqual([answers[key]['text'] for key in definitions], ['TEST-P416', 'Review', '2027-01-08'])
                self.assertEqual([call[:2] for call in sender.calls], [('extractor', 1), ('assigner', 1), ('checker', 1)])
                for field in fields:
                    answer = answers[field['key']]
                    self.assertEqual(answer['status'], 'supported')
                    self.assertNotEqual(answer['text'], answer['evidence'][0]['quote'])
                    semantic.validate_stored_answer(notes, field, definitions[field['key']], answer)
                invalid = deepcopy(facts)
                invalid[0]['subject'] = {'kind': 'other', 'name_span': None}
                before = deepcopy(invalid)
                sender = FixtureSender(invalid, selected)
                with self.assertRaisesMessage(ValidationError, 'Another person needs explicit subject evidence.'):
                    semantic.run(notes, fields, definitions, sender, reference_contract=contract)
                self.assertEqual([call[:2] for call in sender.calls], [('extractor', 1)])
                self.assertEqual(invalid, before)

    def test_visit_metadata_without_identity_is_allowed_but_unresolved_ownership_is_held(self):
        notes = 'The patient attended a review visit.'
        fields, definitions = self.one_field('Category', subject='encounter', temporality='current')
        definitions['answer'].update(version=2, answer_mode='atomic', value_type='choice', choices=['Initial', 'Review'])
        for subject, expected in (('patient', 'Review'), ('uncertain', '')):
            with self.subTest(subject=subject):
                facts = [fact(notes, fields, 'category', 'review', kind='other', subject=subject)]
                answer = self.generated(notes, fields, definitions, facts, ['category'])
                self.assertEqual(answer['text'], expected)
                if subject == 'uncertain':
                    self.assert_held(answer)
                    self.assertIn('The subject is unresolved.', answer['review_reasons'])
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)

    def test_other_person_visit_metadata_cannot_be_relabelled_as_patient_metadata(self):
        notes = 'The patient\'s brother, Synthetic Omar Dalen, attended a review visit.'
        fields, definitions = self.one_field('Category', subject='patient', temporality='current')
        definitions['answer'].update(version=2, answer_mode='atomic', value_type='choice', choices=['Initial', 'Review'])
        selected = assignments(fields, {'answer': ['category']})
        other = [fact(notes, fields, 'category', 'review', kind='other', subject='other',
                      name_quote='Synthetic Omar Dalen')]
        answer = semantic.run(notes, fields, definitions, FixtureSender(other, selected))['answer']
        self.assert_held(answer)
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
        for name in ('Synthetic Omar Dalen', None):
            with self.subTest(name=name):
                facts = [fact(notes, fields, 'category', 'review', kind='other', name_quote=name)]
                sender = FixtureSender(facts, selected)
                before = deepcopy(facts)
                with self.assertRaisesMessage(ValidationError, 'Person attribution needs review:') as failure:
                    semantic.run(notes, fields, definitions, sender)
                from core.jobs import failure_reason, PLATFORM_FAILURE
                message = failure_reason(failure.exception)
                self.assertIn('No answers were adopted.', message)
                self.assertNotIn('Omar', message)
                self.assertLessEqual(len(PLATFORM_FAILURE+message), 250)
                self.assertEqual([call[:2] for call in sender.calls], [('extractor', 1)])
                self.assertEqual(facts, before)
        # Historical canonicalization and finalized-proof reading remain stable.
        units = generation.source_units(notes, fields)[0]
        historical = semantic.validate_facts(notes, units, {'facts': facts})
        old = semantic._assign(notes, fields, definitions, historical, selected)['answer']
        old['independent_check'] = checker(selected)['fields'][0]
        self.assertEqual(old['text'], 'Review')
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], old)

    def test_relative_apposition_does_not_override_an_explicit_new_patient_clause(self):
        fields, definitions = self.one_field('Category', subject='patient', temporality='current')
        definitions['answer'].update(version=2, answer_mode='atomic', value_type='choice', choices=['Initial', 'Review'])
        for switch in (', but the patient attended', '; the patient attended', ', the patient attended',
                       ' and reports that the patient attended', ', but the patient presented for',
                       '; the patient came for', ' and accompanied the patient, who attended'):
            notes = "The patient's brother, Synthetic Omar Dalen, attended an initial visit"+switch+' a review visit.'
            with self.subTest(switch=switch):
                good = [fact(notes, fields, 'category', 'review', kind='other')]
                answer = self.generated(notes, fields, definitions, good, ['category'])
                self.assertEqual((answer['status'], answer['text']), ('supported', 'Review'))
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
                wrong_name = deepcopy(good)
                wrong_name[0]['subject']['name_span'] = span(notes, 'Synthetic Omar Dalen')
                # Include the other unit only when a semicolon splits the source.
                wrong_name[0]['source_unit_ids'] = [unit['id'] for unit in generation.source_units(notes, fields)[0]]
                with self.assertRaisesMessage(ValidationError, 'Person attribution needs review:'):
                    self.generated(notes, fields, definitions, wrong_name, ['category'])

    def test_provider_sdk_keeps_other_person_name_required_in_both_reference_contracts(self):
        from anthropic import transform_schema
        for schema in (semantic.API_FACT_SCHEMA, semantic.API_FACT_INVENTORY_SCHEMA):
            with self.subTest(contract=schema.get('required')):
                transformed = transform_schema(schema)
                branches = transformed['properties']['facts']['items']['properties']['subject']['anyOf']
                self.assertEqual(len(branches), 2)
                by_kinds = {tuple(branch['properties']['kind']['enum']): branch for branch in branches}
                self.assertEqual(set(by_kinds), {('patient', 'clinician', 'uncertain'), ('other',)})
                for branch in branches:
                    self.assertEqual(branch['required'], ['kind', 'name_span'])
                    self.assertFalse(branch['additionalProperties'])
                name = by_kinds[('other',)]['properties']['name_span']
                self.assertEqual(name['type'], 'object')
                self.assertEqual(name['required'], ['quote', 'source_unit_id', 'occurrence'])
                self.assertFalse(name['additionalProperties'])
                self.assertNotIn('anyOf', name)
                nullable = by_kinds[('patient', 'clinician', 'uncertain')]['properties']['name_span']['anyOf']
                self.assertEqual([branch['type'] for branch in nullable], ['object', 'null'])

    def test_an_earlier_patient_mention_does_not_clear_a_later_companion_clause(self):
        fields, definitions = self.one_field('Category', subject='patient', temporality='current')
        definitions['answer'].update(version=2, answer_mode='atomic', value_type='choice', choices=['Initial', 'Review'])
        for notes in (
            "The patient's brother, Synthetic Omar Dalen, said the patient was absent, then attended a review visit himself.",
            "The patient's brother, Synthetic Omar Dalen, reports that the patient attended an initial visit, while Synthetic Omar Dalen attended a review visit.",
            "The patient's brother, Synthetic Omar Dalen, discussed the patient and attended a review visit.",
            "The patient's brother, Synthetic Omar Dalen, spoke about the patient before attending a review visit.",
            "The patient's brother, Synthetic Omar Dalen, said the patient was absent, then he himself attended a review visit.",
            "The patient's brother, Synthetic Omar Dalen, told the patient that he himself attended a review visit.",
            "The patient's brother, Synthetic Omar Dalen, discussed the clinic and the patient before attending a review visit.",
            "The patient's brother, Synthetic Omar Dalen, read the patient's record before attending a review visit.",
            "The patient's brother, Synthetic Omar Dalen, brought the patient a letter before attending a review visit.",
            "The patient's brother, Synthetic Omar Dalen, discussed his father and the patient before attending a review visit.",
            "The patient's brother, Synthetic Omar Dalen, told his father and the patient that he himself attended a review visit.",
            "The patient's brother, Synthetic Omar Dalen, brought the patient to the hospital and then attended a review visit himself.",
            "The patient's brother, Synthetic Omar Dalen, discussed that patient before attending a review visit.",
            "The patient's brother, Synthetic Omar Dalen, reported the patient missing before attending a review visit.",
            "The patient's brother, Synthetic Omar Dalen, reported the patient to reception before attending a review visit.",
        ):
            with self.subTest(notes=notes):
                values = [fact(notes, fields, 'category', 'review', kind='other')]
                sender = FixtureSender(values, assignments(fields, {'answer': ['category']}))
                with self.assertRaisesMessage(ValidationError, 'Person attribution needs review:'):
                    semantic.run(notes, fields, definitions, sender)
                self.assertEqual([call[:2] for call in sender.calls], [('extractor', 1)])
        for note in (
            "The patient's brother, Synthetic Omar Dalen, accompanied the patient, who attended a review visit himself.",
            "The patient's brother, Synthetic Omar Dalen, attended an initial visit, but the patient then attended a review visit himself.",
        ):
            values = [fact(note, fields, 'category', 'review', kind='other')]
            self.assertEqual(self.generated(note, fields, definitions, values, ['category'])['text'], 'Review')

    def test_patient_identity_and_owned_metadata_are_not_a_relative_apposition(self):
        fields, definitions = self.one_field('Category', subject='patient', temporality='current')
        definitions['answer'].update(version=2, answer_mode='atomic', value_type='choice', choices=['Initial', 'Review'])
        notes = 'Synthetic Arin Lome is the clinician. His brother, Synthetic Ivo Fenrin, is the patient and attended a review visit.'
        values = [fact(notes, fields, 'category', 'review', kind='other', name_quote='Synthetic Ivo Fenrin')]
        self.assertEqual(self.generated(notes, fields, definitions, values, ['category'])['text'], 'Review')
        # These exact forms have only a category fact: a separate identity
        # extraction or earlier sentence must not be needed to follow the
        # explicit patient attribution already in the source/name reference.
        for name, note in (
            ('Synthetic Alex Morgan', "Synthetic Alex Morgan is the patient. The patient's brother, Synthetic Omar Dalen, reports that Synthetic Alex Morgan attended a review visit."),
            ('Synthetic Omar Dalen Junior', "The patient's brother, Synthetic Omar Dalen, accompanied the patient Synthetic Omar Dalen Junior to a review visit."),
        ):
            values = [fact(note, fields, 'category', 'review', kind='other', name_quote=name)]
            values[0]['source_unit_ids'] = [unit['id'] for unit in generation.source_units(note, fields)[0]]
            self.assertEqual(self.generated(note, fields, definitions, values, ['category'])['text'], 'Review')
        for name, note in (
            ('Synthetic Alex Morgan', "Synthetic Alex Morgan is the patient. The patient's brother, Synthetic Omar Dalen, reports that Synthetic Alex Morgan attended a review visit."),
            ('Synthetic Omar Dalen Junior', "Synthetic Omar Dalen Junior is the patient. The patient's brother, Synthetic Omar Dalen, accompanied the patient Synthetic Omar Dalen Junior to a review visit."),
        ):
            with self.subTest(name=name):
                values = [fact(note, fields, 'identity', name, kind='identity', name_quote=name),
                          fact(note, fields, 'category', 'review', kind='other', name_quote=name)]
                values[1]['source_unit_ids'] = [unit['id'] for unit in generation.source_units(note, fields)[0]]
                answer = self.generated(note, fields, definitions, values, ['category'])
                self.assertEqual((answer['status'], answer['text']), ('supported', 'Review'))
                semantic.validate_stored_answer(note, fields[0], definitions['answer'], answer)
        fields, definitions = self.one_field('Record reference', subject='patient', temporality='current')
        definitions['answer'].update(version=2, answer_mode='atomic', value_type='identifier')
        note = "The patient's brother, Synthetic Omar Dalen, supplied the patient's record reference TEST-P416."
        values = [fact(note, fields, 'reference', 'TEST-P416', kind='identity')]
        self.assertEqual(self.generated(note, fields, definitions, values, ['reference'])['text'], 'TEST-P416')

    def test_explicit_backdated_target_is_current_only_in_the_new_reference_frame(self):
        for notes in ('This record documents the review visit last week.',):
            numeric = 'three' in notes
            fields, definitions = self.one_field('Pain score0 to 10' if numeric else 'Category', temporality='current')
            if not numeric:
                definitions['answer'].update(version=2, answer_mode='atomic', value_type='choice', choices=['Initial','Review'])
            raw = [fact(notes, fields, 'value', 'three' if numeric else 'review',
                        kind='measurement' if numeric else 'other', timing_quote='last week',
                        scale={'minimum':None,'maximum':'10','span':span(notes,'out of ten')} if numeric else None)]
            selected = assignments(fields, {'answer':['value']})
            answer = semantic.run(notes, fields, definitions, FixtureSender(raw, selected))['answer']
            self.assertEqual((answer['status'], answer['text']), ('supported', '3' if numeric else 'Review'))
            semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
            units, _ = generation.source_units(notes, fields)
            old_facts = semantic.validate_facts(notes, units, {'facts':raw})
            old = semantic._assign(notes, fields, definitions, old_facts, selected)['answer']
            self.assert_held(old)
            semantic.validate_stored_answer(notes, fields[0], definitions['answer'], old)

    def test_relative_target_guard_does_not_adopt_an_earlier_or_unbound_visit(self):
        for notes, time_quote in (
            ('At the target encounter last week, the patient rated pain as three out of ten.', 'last week'),
            ('Last week the patient rated pain as three out of ten.', 'Last week'),
            ('At the previous encounter last week, the patient rated pain as three out of ten.', 'last week'),
            ('At the target encounter last week, the patient previously rated pain as three out of ten.', 'last week'),
            ('At the target encounter last week, pain at the prior visit was three out of ten.', 'last week'),
            ('At the target encounter last week, the patient described pain as three out of ten at the 2020 visit.', 'last week'),
            ('At the target encounter last week, the clinician documented the 2020 visit with pain as three out of ten.', 'last week'),
            ('At the target encounter last week, the patient described pain as three out of ten during childhood.', 'last week'),
            ("At the target encounter last week, the pain expected at tomorrow's visit is three out of ten.", 'last week'),
            ('At the target encounter last week, the patient rated pain as three out of ten.', None)):
            fields, definitions = self.one_field('Pain score0 to 10', temporality='current')
            raw = [fact(notes, fields, 'value', 'three', kind='measurement', timing_quote=time_quote,
                        scale={'minimum':None,'maximum':'10','span':span(notes,'out of ten')})]
            answer = semantic.run(notes, fields, definitions, FixtureSender(raw, assignments(fields, {'answer':['value']})))['answer']
            self.assert_held(answer)
            semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)

    def test_dated_target_encounter_uses_explicit_relative_timing_in_every_role_and_saved_proof(self):
        for date in ('October 11, 2026', 'January 8, 2027'):
            notes = 'The patient attended a review visit on '+date+'.'
            fields, definitions = self.one_field('Category', subject='encounter', temporality='current')
            definitions['answer'].update(version=2, answer_mode='atomic', value_type='choice', choices=['Initial','Review'])
            values = [fact(notes, fields, 'category', 'review', kind='other', timing='current', timing_quote=date)]
            selected = assignments(fields, {'answer':['category']})
            sender = FixtureSender(values, selected)
            answer = semantic.run(notes, fields, definitions, sender)['answer']
            self.assertEqual((answer['status'], answer['text']), ('supported','Review'))
            for _, _, payload, schema, instructions in sender.calls:
                self.assertEqual(payload['timing_reference_contract'], semantic.TEMPORAL_REFERENCE_CONTRACT)
                self.assertIn(semantic.TEMPORAL_REFERENCE_INSTRUCTIONS, instructions)
            self.assertIn(semantic.TEMPORAL_REFERENCE_CONTRACT,
                sender.calls[0][3]['properties']['facts']['items']['properties']['timing']['properties']['kind']['description'])
            self.assertEqual(answer['timing_reference_contract'], semantic.TEMPORAL_REFERENCE_CONTRACT)
            before = deepcopy(answer)
            semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
            self.assertEqual(answer, before)
            for value in (None, 'wall-clock', ''):
                changed = deepcopy(answer); changed['timing_reference_contract'] = value
                with self.subTest(value=value), self.assertRaises(ValidationError):
                    semantic.validate_stored_answer(notes, fields[0], definitions['answer'], changed)
            changed = deepcopy(answer); del changed['timing_reference_contract']
            with self.assertRaises(ValidationError):
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], changed)

    def test_relative_contract_does_not_waive_explicit_current_past_or_future_scopes(self):
        notes = 'Previously the patient attended a review visit. This encounter is Initial. The next visit will be a review visit.'
        fields, definitions = self.one_field('Category', subject='encounter', temporality='current')
        definitions['answer'].update(version=2, answer_mode='atomic', value_type='choice', choices=['Initial','Review'])
        raw = [fact(notes, fields, 'prior', 'review', kind='other', timing='past'),
               fact(notes, fields, 'current', 'Initial', kind='other', timing='current'),
               fact(notes, fields, 'next', 'review', kind='other', timing='future', occurrence=1)]
        units, _ = generation.source_units(notes, fields)
        facts = semantic.validate_facts(notes, units, {'facts':raw})
        for scope, matching in (('current','current'), ('past','prior'), ('future','next')):
            definitions['answer']['scope']['temporality'] = scope
            for selected in ('prior','current','next'):
                result = semantic._assign(notes, fields, definitions, facts,
                    assignments(fields, {'answer':[selected]}), timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)['answer']
                with self.subTest(scope=scope, selected=selected):
                    self.assertEqual(result['status']=='supported', selected==matching)

    def test_new_timing_contract_keeps_old_unmarked_saved_fact_proofs_unchanged(self):
        notes = 'The patient attended a review visit on October 11, 2026.'
        fields, definitions = self.one_field('Category', subject='encounter', temporality='current')
        definitions['answer'].update(version=2, answer_mode='atomic', value_type='choice', choices=['Initial','Review'])
        values = [fact(notes, fields, 'category', 'review', kind='other', timing='past', timing_quote='October 11, 2026')]
        units, _ = generation.source_units(notes, fields)
        facts = semantic.validate_facts(notes, units, {'facts':values})
        selected = assignments(fields, {'answer':['category']})
        old = semantic._assign(notes, fields, definitions, facts, selected)['answer']
        self.assertNotIn('timing_reference_contract', old)
        self.assert_held(old)
        before = deepcopy(old)
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], old)
        self.assertEqual(old, before)
        # Even a new declared frame cannot silently retime the retained past fact.
        new = semantic._assign(notes, fields, definitions, facts, selected,
            timing_reference_contract=semantic.TEMPORAL_REFERENCE_CONTRACT)['answer']
        self.assert_held(new)
        self.assertEqual(new['facts'], old['facts'])

    def test_local_conflict_annotation_does_not_blank_independent_supported_facts(self):
        notes = ('Synthetic Mina Solen attended today. Pain is four out of ten. Pain is seven out of ten. '
                 'These simultaneous entries are not marked as a correction. Temperature is 38.2 Celsius.')
        fields = [{'key': key, 'label': label, 'kind': 'text', 'locator': {'cell': i}}
                  for i, (key, label) in enumerate((('name', 'Patient name'), ('pain', 'Pain score0 to 10'),
                                                   ('temperature', 'Temperature'), ('medicines', 'Medicines')))]
        definitions = default_definitions(fields)
        definitions['temperature'].update(value_type='number', unit='Celsius')
        values = [fact(notes, fields, 'name', 'Synthetic Mina Solen', kind='identity', name_quote='Synthetic Mina Solen'),
                  fact(notes, fields, 'temperature', '38.2', kind='measurement', unit='Celsius', unit_quote='Celsius')]
        values += [fact(notes, fields, 'pain_'+word, word, kind='measurement', concept='pain',
                        scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', i)})
                   for i, word in enumerate(('four', 'seven'))]
        selected = assignments(fields, {'name': ['name'], 'pain': ['pain_four', 'pain_seven'],
                                        'temperature': ['temperature']}, {'pain': 'conflict'})
        # Use an independently verified conflict without a paid repair fixture.
        checked = checker(selected, fact_findings=[{'fact_id': 'pain_four', 'verdict': 'ambiguous',
                                                    'reason': 'The current ratings conflict.'}])
        answers = semantic.run(notes, fields, definitions, FixtureSender(values, selected, checked))
        self.assertEqual((answers['name']['text'], answers['name']['status']), ('Synthetic Mina Solen', 'supported'))
        self.assertEqual((answers['temperature']['value'], answers['temperature']['status']), (38.2, 'supported'))
        self.assertEqual((answers['pain']['text'], answers['pain']['value']), ('', None))
        self.assertEqual(answers['medicines']['status'], 'missing')
        for field in fields:
            semantic.validate_stored_answer(notes, field, definitions[field['key']], answers[field['key']])

    def test_bound_local_correction_does_not_reframe_independent_identity_citation(self):
        notes = ('Synthetic Neri Vale attended today. Pain is eight out of ten. '
                 'Correction: pain is three out of ten. Temperature is 36.8 Celsius.')
        fields = [{'key': key, 'label': label, 'kind': 'text', 'locator': {'cell': i}}
                  for i, (key, label) in enumerate((('name', 'Patient name'), ('pain', 'Pain score0 to 10'),
                                                   ('temperature', 'Temperature')))]
        definitions = default_definitions(fields)
        definitions['temperature'].update(value_type='number', unit='Celsius')
        values = [fact(notes, fields, 'name', 'Synthetic Neri Vale', kind='identity', name_quote='Synthetic Neri Vale'),
                  fact(notes, fields, 'temperature', '36.8', kind='measurement', unit='Celsius', unit_quote='Celsius')]
        values += [fact(notes, fields, 'pain_'+word, word, kind='measurement', concept='pain',
                        supersedes=['pain_eight'] if word == 'three' else [],
                        scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', i)})
                   for i, word in enumerate(('eight', 'three'))]
        # Shared identity evidence must not move either measurement before an erratum.
        identity_unit = generation.source_units(notes, fields)[0][0]['id']
        for value in values[1:]:
            value['subject']['name_span'] = span(notes, 'Synthetic Neri Vale')
            value['source_unit_ids'] = [identity_unit, *value['source_unit_ids']]
        answers = semantic.run(notes, fields, definitions, FixtureSender(values, assignments(
            fields, {'name': ['name'], 'pain': ['pain_three'], 'temperature': ['temperature']})))
        self.assertEqual([answers[k]['status'] for k in ('name', 'pain', 'temperature')], ['supported'] * 3)
        self.assertEqual(answers['pain']['value'], 3)
        self.assertEqual(answers['temperature']['value'], 36.8)
        self.assertEqual({f['value_evidence']['quote'] for f in answers['pain']['facts'] if f['concept'] == 'pain'}, {'eight', 'three'})
        for field in fields:
            semantic.validate_stored_answer(notes, field, definitions[field['key']], answers[field['key']])

    def test_correction_concept_identity_is_requested_and_never_repaired_by_code(self):
        notes = ('Synthetic Neri Vale attended today. The patient first reported pain eight out of ten. '
                 "Correction: the patient's current pain score is three out of ten rather than the earlier eight out of ten. "
                 'The patient takes vitamin D 1000 IU once daily. '
                 "The patient's brother Synthetic Tomas Vale reports pain nine out of ten and takes aspirin.")
        fields = [{'key': key, 'label': label, 'kind': 'text', 'locator': {'cell': i}}
                  for i, (key, label) in enumerate((('name', 'Patient name'), ('pain', 'Pain score0 to 10'),
                                                   ('medicines', 'Regular medicines')))]
        definitions = default_definitions(fields)
        values = [fact(notes, fields, 'name', 'Synthetic Neri Vale', kind='identity', name_quote='Synthetic Neri Vale'),
                  fact(notes, fields, 'medicines', 'vitamin D 1000 IU once daily', kind='history'),
                  fact(notes, fields, 'brother_pain', 'nine', kind='measurement', concept='pain intensity',
                       subject='other', name_quote='Synthetic Tomas Vale',
                       scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', 3)})]
        values += [fact(notes, fields, identity, quote, kind='measurement', concept='pain intensity',
                        supersedes=['first'] if identity == 'corrected' else [],
                        scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', i)})
                   for i, (identity, quote) in enumerate((('first', 'eight'), ('corrected', 'three')))]
        identity_unit = generation.source_units(notes, fields)[0][0]['id']
        for value in values:
            if value['id'] not in ('name', 'brother_pain'):
                value['subject']['name_span'] = span(notes, 'Synthetic Neri Vale')
                value['source_unit_ids'] = [identity_unit, *value['source_unit_ids']]
        selected = assignments(fields, {'name': ['name'], 'pain': ['corrected'], 'medicines': ['medicines']})
        for reference in (semantic.LEGACY_REFERENCE_CONTRACT, semantic.REFERENCE_INVENTORY_CONTRACT):
            for drift in (False, True):
                raw = deepcopy(values)
                if drift:
                    next(v for v in raw if v['id'] == 'first')['concept'] += ' initially reported'
                sender = FixtureSender(raw, selected)
                answers = semantic.run(notes, fields, definitions, sender, reference_contract=reference)
                with self.subTest(reference=reference, drift=drift):
                    self.assertEqual(len(sender.calls), 3)
                    requested = sender.calls[0]
                    self.assertIn(semantic.CONCEPT_IDENTITY_INSTRUCTIONS, requested[4])
                    concept_schema = requested[3]['properties']['facts']['items']['properties']['concept']
                    self.assertEqual(concept_schema['description'], semantic.CONCEPT_IDENTITY_INSTRUCTIONS)
                    self.assertIn('select exactly one unambiguous measurement', sender.calls[1][4])
                    self.assertIn('select its replacement', sender.calls[1][4])
                    if drift:
                        self.assertNotEqual(answers['pain']['status'], 'supported')
                        self.assertIn('The proposed correction is not explicitly bound to the same earlier fact.',
                                      answers['pain']['review_reasons'])
                        self.assertNotEqual(answers['name']['status'], 'supported')
                    else:
                        self.assertEqual([answers[k]['status'] for k in ('name', 'pain', 'medicines')], ['supported'] * 3)
                        self.assertEqual(answers['pain']['value'], 3)
                        self.assertEqual(answers['medicines']['text'], 'Vitamin D 1000 IU once daily')
                        inventory = {f['id']: f for f in answers['pain']['facts']}
                        self.assertEqual({inventory[k]['value_evidence']['quote'] for k in ('first', 'corrected', 'brother_pain')},
                                         {'eight', 'three', 'nine'})
                    for field in fields:
                        semantic.validate_stored_answer(notes, field, definitions[field['key']], answers[field['key']])

    def test_correction_marker_cannot_be_borrowed_from_an_unrelated_source_unit(self):
        notes = 'Pain is two out of ten. Correction: temperature is 37 Celsius. Pain is four out of ten.'
        fields, definitions = self.one_field('Pain score0 to 10')
        values = [fact(notes, fields, word, word, kind='measurement', concept='pain',
                       supersedes=['two'] if word == 'four' else [],
                       scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', i)})
                  for i, word in enumerate(('two', 'four'))]
        values[1]['source_unit_ids'].insert(0, 2)
        self.assert_held(self.generated(notes, fields, definitions, values, ['four']))

    def test_correction_marker_cannot_cross_an_independent_clause_or_measurement(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        for correction in ('Correction: the temperature, and only the temperature, is 37 Celsius; pain is four out of ten.',
                           'Temperature correction: 37 Celsius; an independent pain entry is four out of ten.',
                           'Correction: temperature is 37 Celsius and pain is four out of ten.',
                           'Correction to the temperature only: 37 Celsius — pain is four out of ten.',
                           'Correction to the temperature only: 37 Celsius / pain is four out of ten.',
                           'Correction: temperature is 37 Celsius subsequently pain is four out of ten.',
                           'Correction to the medication only: doxycycline with an independent pain rating of four out of ten.',
                           'Correction to allergy only: penicillin instead of amoxicillin with pain remaining four out of ten.',
                           'Correction: doxycycline with an independent pain rating of four out of ten.'):
            notes = 'Pain is two out of ten. '+correction
            values = [fact(notes, fields, word, word, kind='measurement', concept='pain',
                           supersedes=['two'] if word == 'four' else [],
                           scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', i)})
                      for i, word in enumerate(('two', 'four'))]
            with self.subTest(correction=correction):
                self.assert_held(self.generated(notes, fields, definitions, values, ['four']))

    def test_model_concept_cannot_authorize_another_explicit_correction_target(self):
        fields, definitions = self.one_field('Pain score0 to 10')
        for clause in ('Correction to medication only: doxycycline with pain four out of ten.',
                       'Correction: medication only doxycycline with pain four out of ten.',
                       'Correction: doxycycline with pain four out of ten.'):
            notes = 'Medication is doxycycline with pain two out of ten. '+clause
            values = [fact(notes, fields, word, word, kind='measurement',
                           concept='medication doxycycline with pain',
                           supersedes=['two'] if word == 'four' else [],
                           scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', i)})
                      for i, word in enumerate(('two', 'four'))]
            with self.subTest(clause=clause):
                self.assert_held(self.generated(notes, fields, definitions, values, ['four']))

    def test_local_correction_keeps_an_independent_denial_heading_in_the_same_unit(self):
        notes = 'Pain is eight out of ten. Correction: pain is three out of ten; patient denies:\nfever.'
        fields = [{'key': key, 'label': label, 'kind': 'text', 'locator': {'cell': i}}
                  for i, (key, label) in enumerate((('pain', 'Pain score0 to 10'), ('finding', 'Findings')))]
        definitions = default_definitions(fields)
        values = [fact(notes, fields, word, word, kind='measurement', concept='pain',
                       supersedes=['eight'] if word == 'three' else [],
                       scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', i)})
                  for i, word in enumerate(('eight', 'three'))]
        values.append(fact(notes, fields, 'fever', 'fever'))
        answers = semantic.run(notes, fields, definitions, FixtureSender(values,
            assignments(fields, {'pain': ['three'], 'finding': ['fever']})))
        self.assert_held(answers['finding'])
        self.assertTrue(any('patient denies:' in e['quote'] for e in answers['finding']['evidence']))

    def test_correction_cannot_supersede_a_different_explicitly_named_patient(self):
        notes = ('Synthetic Alpha Mason has pain eight out of ten. '
                 'Correction: Synthetic Beta Hale has pain three out of ten.')
        fields, definitions = self.one_field('Pain score0 to 10')
        values = [fact(notes, fields, word, word, kind='measurement', concept='pain', name_quote=name,
                       supersedes=['eight'] if word == 'three' else [],
                       scale={'minimum': None, 'maximum': '10', 'span': span(notes, 'out of ten', i)})
                  for i, (word, name) in enumerate((('eight', 'Synthetic Alpha Mason'), ('three', 'Synthetic Beta Hale')))]
        self.assert_held(self.generated(notes, fields, definitions, values, ['three']))

    def test_denials_of_referenced_facts_are_not_negated_correction_annotations(self):
        fields, definitions = self.one_field()
        for suffix in ('All findings above are denied.', 'Patient denies the above.', 'These findings are denied.',
                       'All findings in this note are denied.', 'Every finding in this note is incorrect.',
                       'These findings are not marked as a correction and are denied.',
                       'These findings are not marked as a correction:\n'):
            notes = 'Fever. '+suffix
            with self.subTest(suffix=suffix):
                self.assert_held(self.generated(notes, fields, definitions,
                    [fact(notes, fields, 'fever', 'Fever')], ['fever']))

    def test_positioned_scope_profile_is_bound_and_old_saved_proofs_remain_immutable(self):
        notes = 'The patient has ankle pain. These entries are not marked as a correction.'
        fields, definitions = self.one_field()
        values = [fact(notes, fields, 'pain', 'ankle pain')]
        units, _ = generation.source_units(notes, fields)
        old_facts = semantic.validate_facts(notes, units, {'facts': values}, scope_contract=semantic.LEGACY_SCOPE_CONTRACT)
        assigned = assignments(fields, {'answer': ['pain']})
        old = semantic._apply_check(semantic._assign(notes, fields, definitions, old_facts, assigned,
            scope_contract=semantic.LEGACY_SCOPE_CONTRACT), *semantic._check(fields, old_facts, checker(assigned)))['answer']
        self.assertNotIn('fact_scope_contract', old)
        self.assert_held(old)
        before = deepcopy(old)
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], old)
        self.assertEqual(old, before)
        answer = self.generated(notes, fields, definitions, values, ['pain'])
        self.assertEqual(answer['fact_scope_contract'], semantic.POSITIONED_SCOPE_CONTRACT)
        semantic.validate_stored_answer(notes, fields[0], definitions['answer'], answer)
        for profile in (None, 'unknown', semantic.LEGACY_SCOPE_CONTRACT):
            bad = deepcopy(answer)
            if profile is None: bad.pop('fact_scope_contract')
            else: bad['fact_scope_contract'] = profile
            with self.subTest(profile=profile), self.assertRaises(ValidationError):
                semantic.validate_stored_answer(notes, fields[0], definitions['answer'], bad)

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

    def test_complete_synthetic_identity_is_not_replaced_by_supported_shorter_name(self):
        fields, definitions = self.one_field('Person full name')
        definitions['answer'].update(version=2, value_type='person_name', answer_mode='atomic')
        for name in ('Synthetic Theo Varen', 'Synthetic Mina Solen', 'Synthetic Élise 王'):
            notes = name+', record reference TEST-731, attended a review visit.'
            with self.subTest(name=name):
                full = fact(notes, fields, 'name', name, kind='identity', name_quote=name)
                answer = self.generated(notes, fields, definitions, [full], ['name'])
                self.assertEqual((answer['status'], answer['text']), ('supported', name))
                self.assertEqual(answer['evidence'][0]['quote'], notes)
                # All three role fixtures agree on a shorter, source-backed name.
                # Code must still hold it, rather than infer or prepend characters.
                shortened = name.removeprefix('Synthetic ')
                partial = fact(notes, fields, 'name', shortened, kind='identity', name_quote=shortened)
                held = self.generated(notes, fields, definitions, [partial], ['name'])
                self.assert_held(held)
                self.assertEqual(held['text'], '')

    def test_another_complete_synthetic_name_cannot_fill_patient_identity(self):
        fields, definitions = self.one_field('Person full name')
        definitions['answer'].update(version=2, value_type='person_name', answer_mode='atomic')
        notes = ('Synthetic Rhea Dalen attended a review visit. '
                 'Her brother, Synthetic Omar Dalen, reports ankle pain.')
        other = fact(notes, fields, 'brother', 'Synthetic Omar Dalen', kind='identity',
                     subject='other', name_quote='Synthetic Omar Dalen')
        self.assert_held(self.generated(notes, fields, definitions, [other], ['brother']))

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


WRIST_NOTES = ('Synthetic Alex Morgan reports right wrist pain after lifting a heavy box two days ago. '
               'The pain is six out of ten. Examination shows mild swelling of the right wrist, '
               'intact sensation and no deformity. My assessment is right wrist pain. '
               'The plan is a reassessment in two weeks.')


def wrist_reference_case():
    """The eleven retained synthetic clinical facts; no opaque provider metadata.

    In the original live response every name reference points to unit 1, while
    the redundant source_unit_ids cites only each value's own complete unit.
    """
    fields, definitions, _, _ = alex_case()
    definitions['cell_0']['meaning'] = 'The documented patient name, including the documented Synthetic prefix.'
    facts = [
        fact(WRIST_NOTES, fields, 'f1', 'Synthetic Alex Morgan', kind='identity',
             concept='Patient name', timing='unspecified', name_quote='Synthetic Alex Morgan'),
        fact(WRIST_NOTES, fields, 'f2', 'right wrist pain', kind='reason', concept='Reason for visit'),
        fact(WRIST_NOTES, fields, 'f3', 'after lifting a heavy box two days ago', kind='history',
             concept='History of injury', timing='past', timing_quote='two days ago'),
        fact(WRIST_NOTES, fields, 'f4', 'mild swelling of the right wrist', concept='Swelling'),
        fact(WRIST_NOTES, fields, 'f5', 'intact sensation', concept='Sensation'),
        fact(WRIST_NOTES, fields, 'f6', 'no deformity', concept='Deformity', polarity='negated'),
        fact(WRIST_NOTES, fields, 'f7', 'six', kind='measurement', concept='Pain score',
             scale={'minimum': None, 'maximum': '10', 'span': span(WRIST_NOTES, 'out of ten')}),
        fact(WRIST_NOTES, fields, 'f8', 'The pain is six out of ten', kind='history', concept='Pain score text'),
        fact(WRIST_NOTES, fields, 'f9', 'right wrist pain', kind='assessment', concept='Clinician assessment', occurrence=1),
        fact(WRIST_NOTES, fields, 'f10', 'a reassessment in two weeks', kind='plan',
             concept='Management plan', timing='future', timing_quote='in two weeks'),
        fact(WRIST_NOTES, fields, 'f11', 'in two weeks', kind='follow_up', concept='Follow-up interval',
             timing='future', timing_quote='in two weeks'),
    ]
    for selected in facts:
        selected['subject']['name_span'] = span(WRIST_NOTES, 'Synthetic Alex Morgan')
    assigned = assignments(fields, {'cell_0': ['f1'], 'cell_1': ['f2'], 'cell_2': ['f3', 'f8'],
        'cell_3': ['f4', 'f5', 'f6'], 'cell_4': ['f7'], 'cell_5': ['f9'], 'cell_6': ['f10'], 'cell_7': ['f11']})
    return fields, definitions, facts, assigned


class SemanticReferenceInventoryTests(SimpleTestCase):
    contract = semantic.REFERENCE_INVENTORY_CONTRACT

    def resolve(self, notes, units, raw):
        return semantic.resolve_source_references(notes, units, raw, reference_contract=self.contract)

    def test_exact_retained_eleven_fact_response_derives_all_reference_units_without_changing_any_fact(self):
        fields, definitions, facts, assigned = wrist_reference_case()
        units = generation.source_units(WRIST_NOTES, fields)[0]
        legacy = api_facts(WRIST_NOTES, units, facts)
        before = deepcopy(legacy)
        with self.assertRaisesMessage(ValidationError, 'A source reference must name a cited unit'):
            semantic.resolve_source_references(WRIST_NOTES, units, legacy)
        raw = inventory_api_facts(WRIST_NOTES, units, facts)
        self.assertEqual(raw['facts'], [{k: v for k, v in value.items() if k != 'source_unit_ids'}
                                        for value in legacy['facts']])
        resolved = self.resolve(WRIST_NOTES, units, raw)
        self.assertEqual([value['source_unit_ids'] for value in resolved['facts']],
                         [[1], [1], [1], [1, 3], [1, 3], [1, 3], [1, 2], [1, 2], [1, 4], [1, 5], [1, 5]])
        for original, current in zip(facts, resolved['facts']):
            self.assertEqual({k: v for k, v in original.items() if k != 'source_unit_ids'},
                             {k: v for k, v in current.items() if k != 'source_unit_ids'})
        self.assertEqual(legacy, before)
        self.assertEqual(semantic.validate_facts(WRIST_NOTES, units, resolved)['f7']['value_evidence']['quote'], 'six')
        sender = FixtureSender(facts, assigned)
        answers = semantic.run(WRIST_NOTES, fields, definitions, sender, reference_contract=self.contract)
        expected = ['Synthetic Alex Morgan', 'Right wrist pain',
                    'After lifting a heavy box two days ago; The pain is six out of ten',
                    'Mild swelling of the right wrist; Intact sensation; No deformity',
                    '6', 'Right wrist pain', 'A reassessment in two weeks', 'In two weeks']
        self.assertEqual([answers[field['key']]['text'] for field in fields], expected)
        self.assertEqual(answers['cell_4']['value'], 6)
        self.assertEqual(answers['cell_4']['scale'], {'scale_minimum': '0', 'scale_maximum': '10'})
        for field in fields:
            answer = answers[field['key']]
            self.assertEqual(answer['status'], 'supported')
            self.assertFalse(answer['reviewed'])
            semantic.validate_stored_answer(WRIST_NOTES, field, definitions[field['key']], answer)
            for evidence in answer['evidence']:
                self.assertEqual(WRIST_NOTES[evidence['start']:evidence['end']], evidence['quote'])
        self.assertEqual(len(sender.calls), 3)
        self.assertEqual(sender.calls[0][2]['reference_contract'], self.contract)
        self.assertEqual(sender.calls[0][3], semantic.API_FACT_INVENTORY_SCHEMA)
        self.assertEqual(sender.calls[0][4], semantic.EXTRACT_INVENTORY_INSTRUCTIONS)

    def test_default_legacy_contract_keeps_original_payload_schema_instructions_and_stored_answers(self):
        fields, definitions, facts, assigned = alex_case()
        old = FixtureSender(facts, assigned)
        current = FixtureSender(facts, assigned)
        legacy_answers = semantic.run(NOTES, fields, definitions, old)
        current_answers = semantic.run(NOTES, fields, definitions, current, reference_contract=self.contract)
        self.assertEqual(current_answers, legacy_answers)
        self.assertNotIn('reference_contract', old.calls[0][2])
        self.assertEqual(old.calls[0][3], semantic.API_FACT_SCHEMA)
        self.assertEqual(old.calls[0][4], semantic.EXTRACT_INSTRUCTIONS)
        self.assertEqual(old.calls[1:], current.calls[1:])
        legacy_item = semantic.API_FACT_SCHEMA['properties']['facts']['items']
        current_item = semantic.API_FACT_INVENTORY_SCHEMA['properties']['facts']['items']
        self.assertIn('source_unit_ids', legacy_item['required'])
        self.assertNotIn('source_unit_ids', current_item['required'])
        self.assertNotIn('source_unit_ids', current_item['properties'])
        self.assertFalse(current_item['additionalProperties'])
        self.assertEqual(semantic.EXTRACT_INVENTORY_INSTRUCTIONS.count('source_unit_ids'), 1)
        self.assertIn('Do not return source_unit_ids.', semantic.EXTRACT_INVENTORY_INSTRUCTIONS)

    def test_unknown_or_null_requested_contract_refuses_before_any_send(self):
        fields, definitions, facts, assigned = alex_case()
        for wrong in (None, '', 'v2', False, [], {}, 2):
            sender = FixtureSender(facts, assigned)
            with self.subTest(wrong=wrong), self.assertRaises(ValidationError):
                semantic.run(NOTES, fields, definitions, sender, reference_contract=wrong)
            self.assertEqual(sender.calls, [])
            with self.assertRaises(ValidationError):
                semantic.resolve_source_references(NOTES, [], {'facts': []}, reference_contract=wrong)
            with self.assertRaises(AssertionError):
                declared_api_facts(NOTES, [], [], wrong)

    def test_response_envelopes_cannot_autodetect_switch_version_or_reintroduce_ids(self):
        fields, _, facts, _ = alex_case()
        units = generation.source_units(NOTES, fields)[0]
        for change in ('no_marker', 'wrong_marker', 'null_marker', 'extra', 'missing_facts', 'legacy_ids', 'missing_fact_key'):
            raw = inventory_api_facts(NOTES, units, facts)
            if change == 'no_marker': raw.pop('reference_contract')
            elif change == 'wrong_marker': raw['reference_contract'] = semantic.LEGACY_REFERENCE_CONTRACT
            elif change == 'null_marker': raw['reference_contract'] = None
            elif change == 'extra': raw['unknown'] = True
            elif change == 'missing_facts': raw.pop('facts')
            elif change == 'legacy_ids': raw['facts'][0]['source_unit_ids'] = [1]
            else: raw['facts'][0].pop('subject')
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.resolve(NOTES, units, raw)
        with self.assertRaises(ValidationError):
            semantic.resolve_source_references(NOTES, units, inventory_api_facts(NOTES, units, facts))
        with self.assertRaises(ValidationError):
            self.resolve(NOTES, units, api_facts(NOTES, units, facts))

    def test_legacy_null_empty_duplicate_or_uncited_ids_are_still_refused_without_augmentation(self):
        fields, _, facts, _ = alex_case()
        units = generation.source_units(NOTES, fields)[0]
        for ids in (None, [], [1, 1], [2], [True], ['1']):
            raw = api_facts(NOTES, units, facts)
            raw['facts'][0]['source_unit_ids'] = ids
            before = deepcopy(raw)
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                semantic.validate_facts(NOTES, units, semantic.resolve_source_references(NOTES, units, raw))
            self.assertEqual(raw, before)

    def test_every_reference_validates_exact_quote_type_unit_and_occurrence(self):
        fields, _, facts, _ = wrist_reference_case()
        units = generation.source_units(WRIST_NOTES, fields)[0]
        locations = [(0, ('value_span',)), (3, ('subject', 'name_span')),
                     (2, ('timing', 'span')), (6, ('unit_span',)), (6, ('scale', 'span'))]
        invalid = [('quote', 'invented'), ('quote', ''), ('quote', None), ('quote', 6),
                   ('source_unit_id', 6), ('source_unit_id', True), ('source_unit_id', '1'),
                   ('occurrence', 0), ('occurrence', -1), ('occurrence', True),
                   ('occurrence', 1.0), ('occurrence', '1'), ('occurrence', 50001)]
        for fact_index, path in locations:
            for key, value in invalid:
                raw = inventory_api_facts(WRIST_NOTES, units, facts)
                parent = raw['facts'][fact_index]
                for part in path[:-1]: parent = parent[part]
                if path == ('unit_span',):
                    parent[path[-1]] = {'quote': 'six', 'source_unit_id': 2, 'occurrence': 1}
                parent[path[-1]][key] = value
                with self.subTest(path=path, key=key, value=value), self.assertRaises(ValidationError):
                    self.resolve(WRIST_NOTES, units, raw)
        for change in ('offsets', 'extra', 'missing', 'absent_occurrence'):
            raw = inventory_api_facts(WRIST_NOTES, units, facts)
            if change == 'offsets': raw['facts'][0]['value_span'] = facts[0]['value_span']
            elif change == 'extra': raw['facts'][0]['value_span']['start'] = 0
            elif change == 'missing': raw['facts'][0]['value_span'].pop('quote')
            else: raw['facts'][0]['value_span']['occurrence'] = 2
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.resolve(WRIST_NOTES, units, raw)

    def test_complete_inventory_checks_uncited_units_ids_metadata_offsets_and_order(self):
        fields, _, facts, _ = alex_case()
        units = generation.source_units(NOTES, fields)[0]
        raw = inventory_api_facts(NOTES, units, facts[:1])
        for change in ('duplicate', 'reorder', 'missing', 'id', 'bool_id', 'float_id', 'bool_offset',
                       'float_offset', 'negative_offset', 'partial', 'quote', 'correction', 'extra', 'missing_key'):
            changed = deepcopy(units)
            last = changed[-1]  # Deliberately not cited by this identity fact.
            if change == 'duplicate': changed.append(deepcopy(last))
            elif change == 'reorder': changed.reverse()
            elif change == 'missing': changed.pop()
            elif change == 'id': last['id'] = 99
            elif change == 'bool_id': last['id'] = True
            elif change == 'float_id': last['id'] = float(last['id'])
            elif change == 'bool_offset': last['start'] = True
            elif change == 'float_offset': last['start'] = float(last['start'])
            elif change == 'negative_offset': last['start'] = -1
            elif change == 'partial':
                last['end'] -= 1; last['quote'] = NOTES[last['start']:last['end']]
            elif change == 'quote': last['quote'] = last['quote'].replace('week', 'month')
            elif change == 'correction': last['correction_value'] = 'invented correction'
            elif change == 'extra': last['unknown'] = 'extra'
            else: last.pop('correction_value')
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.resolve(NOTES, changed, raw)

    def test_repeated_unicode_identity_refs_deduplicate_and_keep_explicit_occurrence(self):
        fields = [{'key': 'answer', 'label': 'Patient name', 'locator': {'cell': 0}}]
        notes = 'Synthetic Élise 王 and Synthetic Élise 王 are present.'
        selected = fact(notes, fields, 'identity', 'Synthetic Élise 王', kind='identity', occurrence=1)
        selected['subject']['name_span'] = deepcopy(selected['value_span'])
        units = generation.source_units(notes, fields)[0]
        raw = inventory_api_facts(notes, units, [selected])
        self.assertEqual(raw['facts'][0]['value_span']['occurrence'], 2)
        self.assertEqual(self.resolve(notes, units, raw)['facts'], [selected])
        for wrong in ('Synthetic E\u0301lise 王', 'synthetic Élise 王', 'Synthetic  Élise 王'):
            changed = deepcopy(raw); changed['facts'][0]['subject']['name_span']['quote'] = wrong
            with self.subTest(wrong=wrong), self.assertRaises(ValidationError): self.resolve(notes, units, changed)

    def test_derived_references_do_not_relax_other_person_timing_or_unit_attribution(self):
        fields = [{'key': 'answer', 'label': 'Findings', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        examples = [
            ('The mother reports a headache. Examination shows swelling.',
             {'quote': 'swelling', 'subject': 'other', 'name_quote': 'mother'}, 'named other person'),
            ('The patient was examined yesterday. Examination shows swelling.',
             {'quote': 'swelling', 'timing': 'past', 'timing_quote': 'yesterday'}, 'timing annotation'),
            ('The patient has 3 lesions. The largest lesion is 5 mm.',
             {'quote': '3', 'kind': 'measurement', 'unit': 'mm', 'unit_quote': 'mm'}, 'measurement unit'),
        ]
        for notes, values, reason in examples:
            selected = fact(notes, fields, 'value', **values)
            assigned = assignments(fields, {'answer': ['value']})
            sender = FixtureSender([selected], assigned)
            with self.subTest(reason=reason):
                answer = semantic.run(notes, fields, definitions, sender, reference_contract=self.contract)['answer']
                self.assertEqual((answer['text'], answer['status']), ('', 'conflict'))
                self.assertIn(reason, ' '.join(answer['review_reasons']))
                self.assertFalse(answer['reviewed'])

    def test_derived_reference_inventory_preserves_negative_and_partial_number_refusal(self):
        fields = [{'key': 'answer', 'label': 'Episode count', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields); definitions['answer']['value_type'] = 'integer'
        for expression in ('six and a half', 'six / ten', 'two thirds of six', '−\u200bsix'):
            notes = 'The patient reports '+expression+' episodes.'
            selected = fact(notes, fields, 'value', 'six', kind='measurement')
            sender = FixtureSender([selected], assignments(fields, {'answer': ['value']}))
            with self.subTest(expression=expression), self.assertRaises(ValidationError):
                semantic.run(notes, fields, definitions, sender, reference_contract=self.contract)
            self.assertEqual(len(sender.calls), 1)
        fields = [{'key': 'answer', 'label': 'Findings', 'locator': {'cell': 0}}]
        definitions = default_definitions(fields)
        notes = 'Examination shows no deformity.'
        selected = fact(notes, fields, 'value', 'deformity')
        sender = FixtureSender([selected], assignments(fields, {'answer': ['value']}))
        answer = semantic.run(notes, fields, definitions, sender, reference_contract=self.contract)['answer']
        self.assertEqual((answer['text'], answer['status']), ('', 'conflict'))

    def test_fixture_stage_returns_only_its_declared_contract_without_medical_inference(self):
        self.assertEqual(semantic.fixture_stage('extractor', {}), {'facts': []})
        self.assertEqual(semantic.fixture_stage('extractor', {'reference_contract': self.contract}),
                         {'reference_contract': self.contract, 'facts': []})
        for wrong in (None, '', 'unknown', False):
            with self.subTest(wrong=wrong), self.assertRaises(ValidationError):
                semantic.fixture_stage('extractor', {'reference_contract': wrong})
        fields, definitions, _, _ = alex_case()
        calls = []
        def sender(role, attempt, payload, schema, instructions):
            calls.append((role, attempt)); return semantic.fixture_stage(role, payload)
        answers = semantic.run(NOTES, fields, definitions, sender, reference_contract=self.contract)
        self.assertTrue(all(answer['status'] == 'missing' and answer['text'] == '' for answer in answers.values()))
        self.assertEqual(calls, [('extractor', 1), ('assigner', 1), ('checker', 1)])

