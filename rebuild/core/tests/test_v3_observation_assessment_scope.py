"""An observed Examination and uncertain Assessment retain distinct source roles."""
import json
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_v3_field_relations import relation_wire
from .test_v3_supersession_floor import SONNET_55_DEFAULT, form, raw

ANCHOR = 'A 45-year-old man presents with right knee pain.'
OBSERVATION = 'On examination there is a small effusion and medial joint line tenderness.'
ASSESSMENT = 'Assessment is a probable medial meniscus tear.'


@override_settings(**SONNET_55_DEFAULT)
class ObservationAssessmentScope(SimpleTestCase):
    def check(self, notes, source=OBSERVATION, expected='conflict'):
        fields = form('Examination', 'Assessment', 'History of present illness', 'Medications')
        answer = r.validated(raw(notes, fields, relation_wire(notes, fields, {'f1': [source]}), g.SONNET_5_5))['f1']
        self.assertEqual(answer['status'], expected, (notes, answer))
        page = g.as_currently_governed(g.governance_for(notes, fields), notes, {**fields[0], **answer})
        self.assertEqual((page['status'], page['text']), (answer['status'], answer['text']))
        if expected == 'supported':
            self.assertEqual(answer['text'], source)
            self.assertEqual([ev['quote'] for ev in answer['evidence']], [source])
            self.assertEqual(g.governed_decisions(notes, fields, {'f1': answer}), [])
        else:
            self.assertEqual(answer['text'], '')

    def test_retained_whole_wire_supports_observation_and_keeps_all_other_statuses(self):
        case = json.loads((Path(__file__).parent/'observation_assessment_first_pass_control.json').read_text())
        answers = r.validated(raw(case['notes'], case['fields'], case['model_body'], g.SONNET_5_5))
        self.assertEqual(answers['v3_7']['status'], 'supported')
        self.assertEqual(answers['v3_7']['text'], OBSERVATION)
        self.assertEqual([ev['quote'] for ev in answers['v3_7']['evidence']], [OBSERVATION])
        self.assertEqual({key: a['status'] for key, a in answers.items() if key != 'v3_7'},
                         {key: value for key, value in case['original_statuses'].items() if key != 'v3_7'})
        self.assertEqual(answers['v3_8']['text'], 'a probable medial meniscus tear.')
        row = {**next(f for f in case['fields'] if f['key'] == 'v3_7'), **answers['v3_7']}
        page = g.as_currently_governed(g.governance_for(case['notes'], case['fields']), case['notes'], row)
        self.assertEqual((page['status'], page['text']), ('supported', OBSERVATION))
        self.assertEqual(g.governed_decisions(case['notes'], case['fields'], answers), [])

    def test_distinct_diagnosis_preserves_observation_and_its_own_uncertainty(self):
        self.check(ANCHOR+' '+OBSERVATION+' '+ASSESSMENT, expected='supported')
        self.check(ANCHOR+' '+OBSERVATION+' Assessment: possible medial meniscus tear.', expected='supported')

    def test_same_assertion_other_actor_global_uncertainty_time_and_change_are_held(self):
        variants = [
            ANCHOR+' '+OBSERVATION+' Assessment is a probable effusion.',
            ANCHOR+' '+OBSERVATION+' Assessment: effusion unlikely.',
            ANCHOR+' '+OBSERVATION+' Assessment: effusion excluded.',
            ANCHOR+' '+OBSERVATION+' Assessment: unknown.',
            ANCHOR+' '+OBSERVATION+' Assessment: possible medial meniscus tear if symptoms worsen.',
            ANCHOR+' '+OBSERVATION+' There is no effusion. '+ASSESSMENT,
            ANCHOR+' '+OBSERVATION+' The earlier findings were wrong. '+ASSESSMENT,
            ANCHOR+' '+OBSERVATION+' Sorry, wrong patient. '+ASSESSMENT,
            ANCHOR+' '+OBSERVATION+' The patient switched from an unknown medication. '+ASSESSMENT,
            ANCHOR+' Her father has knee pain. '+OBSERVATION+' '+ASSESSMENT,
            'The doctor has knee pain. '+OBSERVATION+' '+ASSESSMENT,
            'Her father has knee pain. '+OBSERVATION+' '+ASSESSMENT,
            OBSERVATION+' '+ASSESSMENT,
        ]
        for notes in variants:
            with self.subTest(notes=notes):self.check(notes)
        for source, assessment in (
                ('Examination is normal.', 'Assessment: examination may be abnormal.'),
                ('On examination there was a small effusion last year.', ASSESSMENT)):
            with self.subTest(source=source):self.check(ANCHOR+' '+source+' '+assessment, source)

    def test_non_observation_and_incomplete_relation_keep_the_existing_floor(self):
        fields = form('Examination', 'Assessment', 'History of present illness')
        source = 'He has knee pain.'
        notes = ANCHOR+' '+source+' '+ASSESSMENT
        answers = r.validated(raw(notes, fields, relation_wire(notes, fields, {'f3': [source]}), g.SONNET_5_5))
        self.assertEqual(answers['f3']['status'], 'conflict')
        notes = ANCHOR+' '+OBSERVATION+' '+ASSESSMENT
        body = relation_wire(notes, fields, {'f1': [OBSERVATION]})
        aid = next(u['id'] for u in g.source_units(notes, fields)[0] if u['quote'] == ASSESSMENT)
        item = next(row for row in body['fields'] if row['key'] == 'f1')
        item['context']['independent'].remove(aid)
        item['context']['qualifier'].append(aid)
        self.assertEqual(r.validated(raw(notes, fields, body, g.SONNET_5_5))['f1']['status'], 'conflict')
