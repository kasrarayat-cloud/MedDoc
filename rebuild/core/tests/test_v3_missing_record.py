"""Complete omission values stay held; actual facts and source evidence survive.

Pure relation parsing, validation and source revalidation, without DB/provider.
"""
from django.test import SimpleTestCase, override_settings
from core import generation as g, v3_field_relations as r


def field(key, label, kind='text'):
    return {'key': key, 'label': label, 'kind': kind, 'context': '', 'locator': {
        'contract': 'v3', 'part': 'word/document.xml', 'slot': 'b/p[0]',
        'fingerprint': '0' * 64, 'target': {'type': 'span', 'shape': 'after_label', 'start': 0, 'end': 0}}}


def selected(notes, fields, labels):
    asked, context, _ = g.v3_generation_fields(fields)
    units = g.source_units(notes, asked, context_labels=context)[0]
    selections = r.FieldSelections(fields=[r.FieldSelection(key=f['key'], unit_ids=[
        u['id'] for u in units if u['quote'] in labels.get(f['label'], ())], conflict=False,
        option_ids=[], context=['answer' if u['quote'] in labels.get(f['label'], ()) else 'independent'
                                for u in units]) for f in asked])
    records = r.records(notes, fields, context, units, selections, g.SONNET_5_5)
    answers = g.validate_selections(notes, asked, selections, context_labels=context,
        evidence_contract=g.TAB_CONTRACT, ordinary_records=records, catalogue=fields)
    return g.v3_adopted(fields, answers, notes, asked, context)


@override_settings(V3_FIELD_RELATIONS=True, V3_HISTORY_CONTEXT=False)
class MissingRecordValues(SimpleTestCase):
    def test_complete_omission_values_hold_with_candidate_and_exact_evidence(self):
        fields = [field('a', 'Allergies')]
        for value in ('not documented.', 'Not recorded.', 'not provided.', 'not available.',
                      'currently not documented.', 'not recorded in the notes.', 'not documented yet.',
                      'never documented.'):
            with self.subTest(value=value):
                notes = 'Allergies: ' + value
                answer = selected(notes, fields, {'Allergies': [notes]})['a']
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                self.assertEqual(answer['held_candidate']['text'], value)
                self.assertEqual(answer['evidence'], [{'quote': notes, 'start': 0, 'end': len(notes)}])

    def test_actual_negatives_and_medication_facts_remain_useful(self):
        for label, value in (('Allergies', 'No known drug allergies.'), ('Allergies', 'penicillin.'),
                             ('Medications', 'not taking warfarin.'), ('Medications', 'warfarin 5 mg daily.')):
            with self.subTest(label=label, value=value):
                notes = label + ': ' + value
                answer = selected(notes, [field('a', label)], {label: [notes]})['a']
                self.assertEqual((answer['status'], answer['text']), ('supported', value))

    def test_refuted_omission_variants_hold_without_normalizing_retained_evidence(self):
        fields = [field('a', 'Allergies')]
        for value in ('not yet documented.', 'not documented in the chart.', 'not documented!',
                      'not documented\u200b.', 'not docu\u200bmented.', 'not documented\uff0e'):
            with self.subTest(value=value):
                notes = 'Allergies: ' + value
                answer = selected(notes, fields, {'Allergies': [notes]})['a']
                self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
                self.assertEqual(answer['held_candidate']['text'], value)
                self.assertEqual(answer['evidence'], [{'quote': notes, 'start': 0, 'end': len(notes)}])
                stale = {**answer, 'status': 'supported', 'text': value}
                self.assertEqual(g.governed_decisions(notes, fields, {'a': stale}), ['Allergies'])

    def test_new_floor_is_complete_value_only_and_keeps_other_floors(self):
        for value in ('not undocumented.', 'not documented as severe.', 'no known drug allergies.',
                      'The patient is not taking warfarin.', 'not documented and penicillin.',
                      'The father reports not documented.', 'documented as not taking warfarin.'):
            with self.subTest(value=value):
                self.assertIsNone(g.MISSING_RECORD_VALUE.fullmatch(value))
        notes = 'The patient\'s father has a penicillin allergy.'
        answer = selected(notes, [field('a', 'Allergies')], {'Allergies': [notes]})['a']
        self.assertNotEqual(answer['status'], 'supported')
        self.assertEqual(answer['text'], '')

    def test_false_independence_does_not_release_an_omission_value(self):
        fields = [field('a', 'Allergies'), field('p', 'Plan', 'long_text')]
        notes = 'Allergies: not documented.\nPlan: Follow-up assessment.'
        answer = selected(notes, fields, {'Allergies': ['Allergies: not documented.'],
                                         'Plan': ['Plan: Follow-up assessment.']})
        self.assertEqual((answer['a']['status'], answer['a']['text']), ('conflict', ''))
        self.assertEqual((answer['p']['status'], answer['p']['text']), ('supported', 'Follow-up assessment.'))
        stale = {**answer, 'a': {**answer['a'], 'status': 'supported', 'text': 'not documented.'}}
        self.assertTrue(g.governed_decisions(notes, fields, stale))
