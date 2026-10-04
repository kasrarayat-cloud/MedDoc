"""Retained whole-wire Allergy repairs and bounded explicit-patient controls."""
import json
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_v3_field_relations import relation_wire
from .test_v3_supersession_floor import SONNET_55_DEFAULT, form, raw


@override_settings(**SONNET_55_DEFAULT)
class LabelledCorrectionScope(SimpleTestCase):
    def assert_flow(self, notes, fields, body, key, status):
        answers = r.validated(raw(notes, fields, body, g.SONNET_5_5))
        answer = answers[key]
        self.assertEqual(answer['status'], status, (notes, answer))
        page = g.as_currently_governed(g.governance_for(notes, fields), notes,
                                      {**next(f for f in fields if f['key'] == key), **answer})
        self.assertEqual((page['status'], page['text']), (answer['status'], answer['text']))
        if status == 'supported':
            self.assertEqual(g.governed_decisions(notes, fields, answers), [])
        else:
            self.assertEqual(answer['text'], '')
        return answers

    def test_retained_two_complete_provider_wires_keep_all_other_statuses_and_source(self):
        retained = json.loads((Path(__file__).parent/'labelled_correction_first_pass_controls.json').read_text())
        for case in retained['cases']:
            with self.subTest(attempt=case['attempt']):
                answers = self.assert_flow(case['notes'], case['fields'], case['model_body'], 'v3_1', 'supported')
                self.assertEqual(answers['v3_1']['text'], 'Patient presents with a rash on both forearms.')
                self.assertEqual([ev['quote'] for ev in answers['v3_1']['evidence']],
                                 ['Patient presents with a rash on both forearms.'])
                self.assertEqual({key: a['status'] for key, a in answers.items() if key != 'v3_1'},
                                 {key: value for key, value in case['original_statuses'].items() if key != 'v3_1'})

    def test_unbounded_same_topic_actor_and_pointer_repairs_still_hold(self):
        fields = form('Chief complaint', 'Allergies', 'Medications')
        claim = 'Patient presents with a rash on both forearms.'
        negatives = [
            claim+' Sorry, I mean amoxicillin.',
            claim+'\nSorry, wrong patient.\nAllergies: penicillin.',
            claim+'\nAllergies: penicillin. Sorry, the preceding finding is wrong.',
            claim+'\nAllergies: penicillin. Sorry, I mean both legs.',
            claim+'\nAllergies: penicillin.\n\nSorry, I mean amoxicillin.',
            claim+'\nAllergies: penicillin. Sorry, I mean his father.',
            claim+'\nAllergies: penicillin. Sorry, I mean amoxicillin?'
        ]
        negatives += [claim+' '+invalid+'\nAllergies: penicillin. Sorry, I mean amoxicillin.'
                      for invalid in ('The earlier findings were wrong.',
                                      'The clinician invalidated the earlier report.',
                                      'The prior assessment was superseded.',
                                      'Do not use the earlier findings.',
                                      'The clinician doubted the preceding findings.')]
        for notes in negatives:
            with self.subTest(notes=notes):
                units = g.source_units(notes, fields)[0]
                pick = next(u['quote'] for u in units if u['quote'].startswith(claim))
                self.assert_flow(notes, fields, relation_wire(notes, fields, {'f1': [pick]}), 'f1', 'conflict')
        for actor in ('Her father', 'The doctor', 'I', 'She'):
            source = actor+' presents with a rash on both forearms.'
            notes = source+'\nAllergies: penicillin. Sorry, I mean amoxicillin.'
            with self.subTest(actor=actor):
                self.assert_flow(notes, fields, relation_wire(notes, fields, {'f1': [source]}), 'f1', 'conflict')
        medicine = 'The patient takes penicillin.'
        notes = medicine+'\nAllergies: penicillin. Sorry, I mean amoxicillin.'
        self.assert_flow(notes, fields, relation_wire(notes, fields, {'f3': [medicine]}), 'f3', 'conflict')

    def test_no_relation_and_qualifier_omission_do_not_gain_scope(self):
        from .test_v3_notes_usefulness import adopt
        fields = form('Chief complaint', 'Allergies')
        claim = 'Patient presents with a rash on both forearms.'
        notes = claim+'\nAllergies: penicillin. Sorry, I mean amoxicillin.'
        self.assertNotEqual(adopt(notes, {'f1': [claim]}, fields)['f1']['status'], 'supported')
        body = relation_wire(notes, fields, {'f1': [claim]})
        unit_id = next(u['id'] for u in g.source_units(notes, fields)[0] if u['quote'].startswith('Allergies:'))
        item = next(i for i in body['fields'] if i['key'] == 'f1')
        item['context']['independent'].remove(unit_id)
        item['context']['qualifier'].append(unit_id)
        self.assert_flow(notes, fields, body, 'f1', 'conflict')
