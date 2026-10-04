"""A source operator owns its grammatical property; a relation alone proves none."""
import json
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from core import generation as g, v3_field_relations as r
from .test_v3_field_relations import relation_wire, answer_of, relate
from .test_v3_supersession_floor import SONNET_55_DEFAULT, raw

CASE = json.loads((Path(__file__).parent/'ordinary_scope_first_pass_control.json').read_text())
ANCHOR = 'A 30-year-old woman presents with headaches.'
MED = 'She takes ibuprofen as needed.'
ALLERGY = 'No known drug allergies.'
EXAM = 'Neurological examination is normal.'
PLAN = 'Plan is to start amitriptyline 10 mg at night.'
FOLLOW = 'She will follow up in six weeks.'


@override_settings(**SONNET_55_DEFAULT)
class OrdinarySourceScope(SimpleTestCase):
    def check(self, notes, key, picks, expected='conflict', *, overrides=None):
        fields = CASE['fields']
        body = relation_wire(notes, fields, {key: picks}, overrides=overrides)
        answer = r.validated(raw(notes, fields, body, g.SONNET_5_5))[key]
        self.assertEqual(answer['status'], expected, (notes, key, answer))
        field = next(f for f in fields if f['key'] == key)
        page = g.as_currently_governed(g.governance_for(notes, fields), notes, {**field, **answer})
        self.assertEqual((page['status'], page['text']), (answer['status'], answer['text']))
        if expected == 'supported':
            self.assertEqual([ev['quote'] for ev in answer['evidence']], picks)
            self.assertEqual(g.governed_decisions(notes, fields, {key: answer}), [])
        else:
            self.assertEqual(answer['text'], '')
        return answer

    def test_retained_complete_actual_wire_preserves_originals_and_supported_bytes(self):
        answers = r.validated(raw(CASE['notes'], CASE['fields'], CASE['model_body'], g.SONNET_5_5))
        expected = {'v3_1': 'supported', 'v3_2': 'conflict', 'v3_3': 'missing', 'v3_4': 'supported',
                    'v3_5': 'supported', 'v3_6': 'supported', 'v3_7': 'supported', 'v3_8': 'supported',
                    'v3_9': 'supported', 'v3_10': 'missing', 'v3_11': 'missing'}
        self.assertEqual({k: a['status'] for k, a in answers.items()}, expected)
        self.assertEqual(CASE['original_statuses']['v3_7'], 'conflict')
        self.assertEqual(answers['v3_7']['text'], EXAM)
        self.assertEqual(answers['v3_5']['text'], ALLERGY)
        self.assertEqual(answers['v3_4']['text'], MED)
        self.assertEqual(answers['v3_9']['text'], 'to start amitriptyline 10 mg at night.\n'+FOLLOW)
        self.assertEqual(answers['v3_6']['text'], 'No')
        self.assertEqual({f['context'] for f in CASE['fields'] if f['kind'] == 'long_text'}, {'Clinic visit record'})
        gov = g.governance_for(CASE['notes'], CASE['fields'])
        for field in CASE['fields']:
            answer = answers[field['key']]
            page = g.as_currently_governed(gov, CASE['notes'], {**field, **answer})
            self.assertEqual((page['status'], page['text']), (answer['status'], answer['text']))
        self.assertEqual(g.governed_decisions(CASE['notes'], CASE['fields'], answers), [])

    def test_literal_properties_and_symptom_denial_do_not_end_medication_intake(self):
        denial = 'She denies visual changes, nausea, or weakness.'
        self.check(ANCHOR+' '+MED+' '+denial+' '+ALLERGY+' '+EXAM, 'v3_4', [MED], 'supported')
        self.check(ANCHOR+' '+MED+' '+denial+' '+ALLERGY+' '+EXAM, 'v3_5', [ALLERGY], 'supported')
        self.check(ANCHOR+' '+MED+' '+denial+' '+ALLERGY+' '+EXAM, 'v3_7', [EXAM], 'supported')
        self.check(ANCHOR+' She takes warfarin. She denies any bleeding.', 'v3_4', ['She takes warfarin.'], 'supported')
        self.check(ANCHOR+' '+PLAN+' '+FOLLOW+' She is a nonsmoker.', 'v3_9', [PLAN, FOLLOW], 'supported')

    def test_actual_opposition_allergy_reaction_and_medication_ending_still_hold(self):
        for tail in ('She takes no medicines.', 'She is on no treatment.', 'She has stopped all treatment.',
                     'She denies taking ibuprofen.', 'She switched from ibuprofen to an unknown medicine.',
                     'She is not anticoagulated.', 'The earlier medication entry was wrong.',
                     'She denies any medication changes.', 'She stopped last year.'):
            with self.subTest(tail=tail): self.check(ANCHOR+' '+MED+' '+tail, 'v3_4', [MED])
        for tail in ('She is allergic to penicillin.', 'She has a drug reaction.', 'She has anaphylaxis.',
                     'Allergies: penicillin.', 'The previous allergy entry was incorrect.',
                     'She is on penicillin for a drug reaction.'):
            with self.subTest(tail=tail): self.check(ANCHOR+' '+ALLERGY+' '+tail, 'v3_5', [ALLERGY])

    def test_actor_time_unknown_global_and_same_normal_result_remain_held(self):
        for notes in (EXAM, 'Her father has headaches. '+EXAM,
                ANCHOR+' The doctor underwent colonoscopy. '+EXAM,
                ANCHOR+' Her sister has headaches. '+EXAM,
                ANCHOR+' '+EXAM+' The earlier findings were wrong.',
                ANCHOR+' '+EXAM+' Examination: abnormal.',
                ANCHOR+' '+EXAM+' The previous examination was entered in error.',
                ANCHOR+' '+EXAM+' She has an unknown problem.',
                ANCHOR+' '+EXAM+' Sorry, wrong patient.'):
            with self.subTest(notes=notes): self.check(notes, 'v3_7', [EXAM])
        for exam in ('Neurological examination was normal last year.', 'Her neurological examination is normal.',
                     'Neurological examination may be normal.', 'Neurological examination is normal if she rests.',
                     'If symptoms worsen, Neurological examination is normal.'):
            with self.subTest(exam=exam): self.check(ANCHOR+' '+exam, 'v3_7', [exam])
        for notes in (ALLERGY, 'Her father has headaches. '+ALLERGY,
                      ANCHOR+' Her sister has headaches. '+ALLERGY):
            with self.subTest(notes=notes): self.check(notes, 'v3_5', [ALLERGY])

    def test_full_relation_original_destination_and_clause_union_are_required(self):
        notes = ANCHOR+' '+EXAM
        self.check(notes, 'v3_7', [EXAM], overrides={('v3_7', ANCHOR): 'unresolved'})
        self.check(notes, 'v3_4', [EXAM])
        fields = CASE['fields']
        body = relation_wire(notes, fields, {'v3_7': [EXAM]})
        answer = answer_of(body, 'v3_7')
        uid = next(u['id'] for u in g.source_units(notes, fields)[0] if u['quote'] == ANCHOR)
        relate(body, 'v3_7', uid, 'qualifier')
        self.assertEqual(r.validated(raw(notes, fields, body, g.SONNET_5_5))['v3_7']['status'], 'conflict')
        for notes in (ANCHOR+' '+PLAN+' Her father will follow up in six weeks.',
                      ANCHOR+' '+PLAN+' She will follow up if symptoms worsen.',
                      ANCHOR+' '+PLAN+' She will follow up with her medicine stopped.',
                      ANCHOR+' '+PLAN+' '+FOLLOW+' The earlier plan was wrong.'):
            units = g.source_units(notes, fields)[0]
            picks = [u['quote'] for u in units if u['quote'] == PLAN or 'follow up' in u['quote']]
            with self.subTest(notes=notes): self.check(notes, 'v3_9', picks)
