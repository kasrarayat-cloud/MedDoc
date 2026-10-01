"""Ordinary notes on the field-relations path, 2026-10-01 (T2b): what a POSITIVELY established single-patient note
releases, what it never releases, the floor that closes the two unsafe relations rows, the bare backward repair, the
relations contract's own field batches for a large form, and the claude-sonnet-5-5 default with its explicit switch.

Provider decisions are simulated (the keyed v2 wire through `offered`, every unpicked unit 'independent' - the worst
case: a model that misses whatever could change the answer); what is asserted is what the application does with them,
on generation, the page and finalization. The default path is never changed (`DefaultPathUnchanged`)."""
import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from core import generation as g, generation_batch as b, v3_field_relations as r, v3_actors as actors
from core.tests.test_v3_field_relations import offered, relation_wire
from core.tests.test_v3_notes_floors import (Floors, N01, N05, NO, YES, RELATIONS, DEFAULT, TITLE, clinic_form,
                                             order_form, repeated_other, v3)
from core.tests.test_v3_ordinary_notes import LIVE, field

N03 = 'The patient is subject to a Community Treatment Order (CTO). She attends the clinic every week.'
N04 = ('45-year-old man presents with right knee pain for three weeks after a fall. He has hypertension and takes '
       'lisinopril 10 mg daily. Allergies: penicillin. Smoker: No. On examination there is a small effusion and medial '
       'joint line tenderness. Assessment is a probable medial meniscus tear. Plan is an MRI of the right knee and '
       'physiotherapy referral.')
N02 = 'The patient describes the pain as a tight band around her head. The patient sees zigzag lines before the headache begins.'
OPENER = 'A 30-year-old woman presents with headaches.'


@override_settings(**RELATIONS)
class UnanchoredOtherPerson(Floors, SimpleTestCase):
    """C4 and P4 (the two adverse rows the integrated floors still adopted): a topic or labelled line after another
    person's statement, in a note that has not presented the patient before it, is held whatever the model said."""

    def test_the_two_rows_and_their_line_break_variants_are_held(self):
        fields = clinic_form()
        for sister in ('Her sister was seen in oncology last month. Assessment is breast cancer.',
                       'Her sister was seen in oncology last month.\nAssessment is breast cancer.',
                       'Her sister was seen in oncology last month.\n\nAssessment is breast cancer.'):
            with self.subTest(notes=sister):
                self.assert_held(sister, fields, {'v3_8': ['Assessment is breast cancer.']}, 'v3_8',
                                 shown='Her sister was seen in oncology last month.')
        for father in ('His father had a heart attack at 55. He has asthma. Allergies: none known.',
                       'His father had a heart attack at 55.\nHe has asthma.\nAllergies: none known.',
                       'His father had a heart attack at 55.\n\nHe has asthma.\n\nAllergies: none known.'):
            with self.subTest(notes=father):
                self.assert_held(father, fields, {'v3_5': ['Allergies: none known.']}, 'v3_5')

    def test_a_note_that_presents_the_patient_first_keeps_its_answers(self):
        # N05: the patient is presented before the father; its labelled lines stay the model's to place (the residual
        # stated in the design: meaning alone separates them from a relative's).
        self.assert_filled(N05, clinic_form(), {'v3_5': ['Allergies: none known.'], 'v3_6': ['Smoker: Yes.'],
                                                'v3_7': ['Examination is normal.']},
                           {'v3_5': 'none known.', 'v3_6': 'Yes', 'v3_7': 'normal.'}, choices=YES)
        # the patient presented between: another person's run ends at the patient
        self.assert_filled('His father smoked. The patient presents with cough. Smoker: No.', clinic_form(),
                           {'v3_6': ['Smoker: No.']}, {'v3_6': 'No'}, choices=NO)
        # the patient's own main statement naming somebody else presents the patient too
        self.assert_filled('The patient reports her husband smokes. Smoker: No.', clinic_form(),
                           {'v3_6': ['Smoker: No.']}, {'v3_6': 'No'}, choices=NO)


@override_settings(**RELATIONS)
class SinglePatientRelease(Floors, SimpleTestCase):
    """A note whose single-patient scope is POSITIVELY established releases the pronoun, thing and explicit statements
    the relation reader had no patient evidence for."""

    def test_the_freezes_answers_are_filled(self):
        fields = clinic_form()
        self.assert_filled(N01, fields, {
            'v3_2': ['The headaches started two months ago and are worse in the morning.',
                     'She denies visual changes, nausea, or weakness.'],
            'v3_4': ['She takes ibuprofen as needed.'], 'v3_6': ['She is a nonsmoker.'],
            'v3_9': ['Plan is to start amitriptyline 10 mg at night.', 'She will follow up in six weeks.']},
            {'v3_2': 'The headaches started two months ago and are worse in the morning.\n'
                     'She denies visual changes, nausea, or weakness.',
             'v3_4': 'She takes ibuprofen as needed.', 'v3_6': 'No',
             'v3_9': 'to start amitriptyline 10 mg at night.\nShe will follow up in six weeks.'}, choices=NO)
        self.assert_filled(N03, order_form(), {'v3_2': ['She attends the clinic every week.']},
                           {'v3_2': 'She attends the clinic every week.'})
        exam = 'On examination there is a small effusion and medial joint line tenderness.'
        self.assert_filled(N04, fields, {'v3_7': [exam]}, {'v3_7': exam})
        prodrome = 'The patient sees zigzag lines before the headache begins.'
        self.assert_filled(N02, repeated_other(), {'v3_2': [prodrome]}, {'v3_2': prodrome})

    def test_the_presenting_opener_with_an_article(self):
        notes = 'A ' + N04
        self.assert_filled(notes, clinic_form(), {'v3_1': ['A ' + N04.split('. ')[0] + '.'],
                                                  'v3_7': ['On examination there is a small effusion and medial joint '
                                                           'line tenderness.']},
                           {'v3_1': 'A ' + N04.split('. ')[0] + '.',
                            'v3_7': 'On examination there is a small effusion and medial joint line tenderness.'})
        self.assert_filled(OPENER + ' She takes warfarin.', clinic_form(),
                           {'v3_1': [OPENER], 'v3_4': ['She takes warfarin.']},
                           {'v3_1': OPENER, 'v3_4': 'She takes warfarin.'})

    def test_the_still_held_freeze_answers_and_why(self):
        fields = clinic_form()
        # (b2): one statement for two specific questions - an owner decision, kept held
        both = 'He has hypertension and takes lisinopril 10 mg daily.'
        self.assert_held(N04, fields, {'v3_3': [both], 'v3_4': [both]}, 'v3_3')
        # alone in one specific question it is still two topics, so not released
        self.assert_held(N04, fields, {'v3_3': [both]}, 'v3_3')
        # a class denial answering its own question beside meaning-only contradictions stays coupled (unchanged)
        self.assert_held(N01, fields, {'v3_5': ['No known drug allergies.']}, 'v3_5')


#: (why, notes, pick, key, choices): a line that may change the answer - another person, time, side, or meaning - in a
#: note that would otherwise release it. Each is HELD with every other line called 'independent'.
CHANGED = (
    ('a person the lexicons miss', 'The patient employs a housekeeper. She takes warfarin.', 'She takes warfarin.', 'v3_4', None),
    ('a name', 'The patient visits JANE daily. She takes warfarin.', 'She takes warfarin.', 'v3_4', None),
    ('a name in a sentence', 'The patient lives with Grace. She takes warfarin.', 'She takes warfarin.', 'v3_4', None),
    ('a capitalized known word', 'The patient lives with Pain. She takes warfarin.', 'She takes warfarin.', 'v3_4', None),
    ('a status as a companion', 'The patient lives with a smoker. She has asthma.', 'She has asthma.', 'v3_3', None),
    ('a group as a subject', OPENER + ' Her band has asthma.', 'Her band has asthma.', 'v3_3', None),
    ('a metonym as a subject', OPENER + ' The referral takes warfarin.', 'The referral takes warfarin.', 'v3_4', None),
    ('a non-reflexive object', OPENER + ' She gives her warfarin.', 'She gives her warfarin.', 'v3_4', None),
    ('a pronoun of the other gender', '45-year-old man presents with cough. She takes lisinopril.', 'She takes lisinopril.',
     'v3_4', None),
    ('another time, fronted', OPENER + ' On admission she is on warfarin.', 'On admission she is on warfarin.', 'v3_4', None),
    ('another time, in the answer', OPENER + ' She takes warfarin on Mondays.', 'She takes warfarin on Mondays.', 'v3_4', None),
    ('a date', OPENER + ' She is on warfarin in 2019.', 'She is on warfarin in 2019.', 'v3_4', None),
    ('a frame the parse hides', OPENER + ' At the time of the fracture she takes warfarin.',
     'At the time of the fracture she takes warfarin.', 'v3_4', None),
    ('a pending state', OPENER + ' She is in line for insulin.', 'She is in line for insulin.', 'v3_4', None),
    ('a choice', 'The patient takes warfarin or apixaban.', 'The patient takes warfarin or apixaban.', 'v3_4', None),
    ('a risk', OPENER + ' She is at risk of diabetes.', 'She is at risk of diabetes.', 'v3_3', None),
    ('two sides', '45-year-old man presents with knee pain. He has tenderness over the right knee. Assessment is left '
     'knee sprain.', 'He has tenderness over the right knee.', 'v3_7', None),
    ('a word nothing knows', OPENER + ' She takes warfarin. She is not anticoagulated.', 'She takes warfarin.', 'v3_4', None),
    ('a correction by meaning', OPENER + ' She takes warfarin. She was misheard.', 'She takes warfarin.', 'v3_4', None),
    ('a pointer', OPENER + ' She takes warfarin. The previous line is incorrect.', 'She takes warfarin.', 'v3_4', None),
    ('a back-reference', OPENER + ' She takes warfarin. She denies this.', 'She takes warfarin.', 'v3_4', None),
    ('a bare cessation', OPENER + ' She smokes. She stopped last year.', 'She smokes.', 'v3_6', YES),
    ('a class denial', OPENER + ' She takes warfarin. She takes no medicines.', 'She takes warfarin.', 'v3_4', None),
    ('a replacement', OPENER + ' She takes warfarin. She takes apixaban instead.', 'She takes warfarin.', 'v3_4', None),
    ('a planned switch', OPENER + ' She takes warfarin. Plan: switch to apixaban.', 'She takes warfarin.', 'v3_4', None),
    ('a contraindication', OPENER + ' She will start amitriptyline 10 mg at night. She is allergic to amitriptyline.',
     'She will start amitriptyline 10 mg at night.', 'v3_9', None),
    ('the same topic unplaced', OPENER + ' She is a nonsmoker. She has twenty cigarettes a day.', 'She is a nonsmoker.',
     'v3_6', NO),
    ('an ended habit', OPENER + ' She smokes. The patient used to smoke.', 'She smokes.', 'v3_6', YES),
    ('a restriction', OPENER + ' She is allergic to penicillin. The patient is allergic to latex only.',
     'She is allergic to penicillin.', 'v3_5', None),
    ('an incomplete answer', OPENER + ' She is allergic to penicillin. She is also allergic to latex.',
     'She is allergic to penicillin.', 'v3_5', None),
    ('a resolved complaint', OPENER + ' The headaches are worse in the morning. She is now headache free.',
     'The headaches are worse in the morning.', 'v3_2', None),
    ('another destination', OPENER + ' She takes no medicines.', 'She takes no medicines.', 'v3_3', None),
    ('an uncertain line', '45-year-old man presents with knee pain. He has tenderness over the right knee. The patient '
     'is unsure about the side.', 'He has tenderness over the right knee.', 'v3_7', None),
    ('a line leaning on another', OPENER + ' She takes warfarin. She did.', 'She takes warfarin.', 'v3_4', None),
    ('a line leaning on any earlier one', OPENER + ' She takes warfarin. The headaches are worse in the morning. Not '
     'anymore.', 'She takes warfarin.', 'v3_4', None),
    ('another woman by her pronoun', OPENER + ' She sees her at night. She takes warfarin.', 'She takes warfarin.', 'v3_4',
     None),
    ('a frame over the historical present', OPENER + ' At night she has a cough. She is on warfarin.',
     'She is on warfarin.', 'v3_4', None),
    ('an unknown word with no topic', OPENER + ' She takes warfarin. She was mistaken.', 'She takes warfarin.', 'v3_4', None),
    ('a labelled contraindication', OPENER + ' She will start amitriptyline 10 mg at night. Allergies: amitriptyline.',
     'She will start amitriptyline 10 mg at night.', 'v3_9', None),
)


@override_settings(**RELATIONS)
class SinglePatientRefusals(Floors, SimpleTestCase):
    def test_every_line_that_may_change_the_answer_holds_it(self):
        fields = clinic_form()
        for why, notes, pick, key, choices in CHANGED:
            with self.subTest(why=why, notes=notes):
                self.assert_held(notes, fields, {key: [pick]}, key, choices=choices)

    def test_each_refusal_has_a_released_control(self):
        fields = clinic_form()
        for notes, pick, key, choices, text in (
                (OPENER + ' She takes warfarin.', 'She takes warfarin.', 'v3_4', None, 'She takes warfarin.'),
                (OPENER + ' She is on warfarin.', 'She is on warfarin.', 'v3_4', None, 'She is on warfarin.'),
                (OPENER + ' She has asthma. She takes no medicines.', 'She has asthma.', 'v3_3', None, 'She has asthma.'),
                (OPENER + ' She is a nonsmoker. She takes no medicines.', 'She is a nonsmoker.', 'v3_6', NO, 'No'),
                (OPENER + ' She smokes.', 'She smokes.', 'v3_6', YES, 'Yes'),
                (OPENER + ' She is allergic to penicillin.', 'She is allergic to penicillin.', 'v3_5', None,
                 'She is allergic to penicillin.'),
                (OPENER + ' She will start amitriptyline 10 mg at night.', 'She will start amitriptyline 10 mg at night.',
                 'v3_9', None, 'She will start amitriptyline 10 mg at night.'),
                ('45-year-old man presents with knee pain. He has tenderness over the right knee. Assessment is right '
                 'knee sprain.', 'He has tenderness over the right knee.', 'v3_7', None,
                 'He has tenderness over the right knee.')):
            with self.subTest(notes=notes):
                self.assert_filled(notes, fields, {key: [pick]}, {key: text}, choices=choices)

    def test_two_topics_in_one_statement_answer_no_specific_question(self):
        both = 'He has hypertension and takes lisinopril 10 mg daily.'
        notes = '45-year-old man presents with cough. ' + both
        for label in ('Other', 'Comorbidities', 'Past medical history', 'Medications'):
            with self.subTest(label=label):
                self.assert_held(notes, [v3('f', label, 'long_text', TITLE)], {'f': [both]}, 'f')
        # a general narrative question takes the whole statement
        self.assert_filled(notes, [v3('f', 'History', 'long_text', TITLE)], {'f': [both]}, {'f': both})

    def test_a_group_named_as_an_actor_is_somebody_else(self):
        # a general narrative question with no topic list: only the group rule keeps 'Her band' from being the patient
        self.assert_held(OPENER + ' Her band has asthma.', [v3('f', 'History', 'long_text', TITLE)],
                         {'f': ['Her band has asthma.']}, 'f')
        self.assert_filled(OPENER + ' She has asthma.', [v3('f', 'History', 'long_text', TITLE)],
                           {'f': ['She has asthma.']}, {'f': 'She has asthma.'})

    def test_a_question_about_somebody_else_or_another_time_is_not_answered(self):
        notes = OPENER + ' She takes warfarin.'
        for context in ('Family history', 'Mother > Medications', 'Previous visit', 'Discharge summary'):
            with self.subTest(context=context):
                self.assert_held(notes, [v3('f', 'Medications', 'long_text', context)], {'f': ['She takes warfarin.']}, 'f')
        self.assert_filled(notes, [v3('f', 'Medications', 'long_text', TITLE)], {'f': ['She takes warfarin.']},
                           {'f': 'She takes warfarin.'})

    def test_the_reading_is_a_note_property_not_a_word_list_of_dangers(self):
        """The scope is positive: an unknown noun anywhere withdraws every release in the note."""
        def reading(notes):
            asked, context, _ = g.v3_generation_fields(clinic_form())
            return g.v3_preceding_reading(notes, asked, context, g.source_units(notes, asked, context_labels=context)[0])
        self.assertTrue(reading(OPENER + ' She takes warfarin.')['sole_patient'])
        for notes in (OPENER + ' She takes warfarin. The sherpa came too.', OPENER + ' She takes zorblex.',
                      'Allergies: none.\n' + OPENER, 'She takes warfarin.'):
            with self.subTest(notes=notes):
                self.assertFalse(reading(notes)['sole_patient'])


@override_settings(**RELATIONS)
class BareBackwardRepair(Floors, SimpleTestCase):
    def test_a_line_after_the_repaired_value_is_answered_and_nothing_before_it(self):
        fields = [v3('v3_1', 'Chief complaint', 'text', 'Skin clinic record'),
                  v3('v3_2', 'Allergies', 'text', 'Skin clinic record'),
                  v3('v3_3', 'Smoker', 'choice', 'Skin clinic record > Smoker', ['Yes', 'No'])]
        no = {'v3_3': ['v3_3:1']}
        for notes in ('Patient presents with a rash on both forearms.\nAllergies: penicillin. Sorry, I mean amoxicillin.\nSmoker: No.',
                      'Patient presents with a rash on both forearms.\n\nAllergies: penicillin.\nSorry, I mean amoxicillin.\n\nSmoker: No.'):
            with self.subTest(notes=notes):
                self.assert_filled(notes, fields, {'v3_3': ['Smoker: No.']}, {'v3_3': 'No'}, choices=no)
                self.assert_held(notes, fields, {'v3_1': ['Patient presents with a rash on both forearms.']}, 'v3_1')
        # a repair of the line before: held; a forward pointer, a repair that is not a known thing, one after an
        # unlabelled line: note-wide as before
        for notes in ('Allergies: penicillin.\nSmoker: No.\nSorry, I mean amoxicillin.',
                      'Patient presents with a rash.\nSmoker: No. Sorry, I mean yes.',
                      'Strike the next entry.\nSmoker: Yes.', 'Sorry, the next one is wrong.\nSmoker: Yes.',
                      'Allergies: none. Sorry, I meant both legs.\nSmoker: No.',
                      'Patient presents with a rash.\nSorry, I mean amoxicillin.\nSmoker: No.'):
            line = next(x for x in notes.split('\n') if x.startswith('Smoker:'))
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {'v3_3': [line]}, 'v3_3',
                                 choices=no if 'No.' in line else {'v3_3': ['v3_3:0']})


@override_settings(**DEFAULT)
class DefaultPathUnchanged(SimpleTestCase):
    def test_the_default_path_reads_none_of_it(self):
        from core.tests.test_v3_notes_floors import build  # noqa: F401  (the floors' own default-path guard stays)
        fields = clinic_form()
        asked, context, v3_fields = g.v3_generation_fields(fields)
        units = g.source_units(N01, asked, context_labels=context)[0]
        by_quote = {u['quote']: u['id'] for u in units}
        chosen = g.UnitSelections(fields=[g.UnitSelection(key=f['key'], unit_ids=(
            [by_quote['She takes ibuprofen as needed.']] if f['key'] == 'v3_4' else []), conflict=False) for f in asked])
        with patch('core.v3_field_relations.sole_released', side_effect=AssertionError('read on the default path')), \
                patch('core.generation.v3_relation_corrections', wraps=g.v3_relation_corrections) as corrections:
            answers = g.validate_selections(N01, asked, g.unit_selections(N01, asked, chosen, context_labels=context),
                                            context_labels=context, evidence_contract=g.TAB_CONTRACT)
        self.assertEqual(answers['v3_4']['status'], 'conflict')
        # the correction reader returns every correction unchanged without a relation record
        self.assertTrue(all(call.args[4] is None for call in corrections.call_args_list))


class FieldRelationsSwitch(SimpleTestCase):
    def test_one_effective_switch(self):
        for overrides, model, expected in (
                ({'V3_FIELD_RELATIONS': True}, g.SONNET_5, True), ({'V3_FIELD_RELATIONS': True}, g.SONNET_5_5, True),
                ({'V3_FIELD_RELATIONS': False}, g.SONNET_5_5, False),                       # settings predating the default
                ({'V3_FIELD_RELATIONS': False, 'V3_FIELD_RELATIONS_SWITCH': None}, g.SONNET_5_5, True),
                ({'V3_FIELD_RELATIONS': False, 'V3_FIELD_RELATIONS_SWITCH': None}, g.SONNET_5, False),
                ({'V3_FIELD_RELATIONS': False, 'V3_FIELD_RELATIONS_SWITCH': None}, 'claude-sonnet-4-6', False),
                ({'V3_FIELD_RELATIONS': False, 'V3_FIELD_RELATIONS_SWITCH': False}, g.SONNET_5_5, False)):
            with self.subTest(overrides=overrides, model=model), override_settings(**overrides, AI_MODEL=model):
                self.assertIs(g.field_relations_enabled(), expected)
                self.assertIs(r.enabled(), expected)

    def test_the_default_quotes_the_contract_for_claude_sonnet_5_5_only(self):
        fields = clinic_form()
        with override_settings(**dict(LIVE, AI_MODEL=g.SONNET_5_5, V3_FIELD_RELATIONS=False,
                                      V3_FIELD_RELATIONS_SWITCH=None)):
            config = g.configuration(fields)
        self.assertEqual(config['ordinary_field_contract'], r.CONTRACT)
        self.assertEqual(config['request_profile']['profile'], g.ORDINARY_PROFILES[g.SONNET_5_5])
        for model, switch in ((g.SONNET_5_5, False), (g.SONNET_5, None), ('claude-sonnet-4-6', None)):
            with self.subTest(model=model, switch=switch), override_settings(
                    **dict(LIVE, AI_MODEL=model, V3_FIELD_RELATIONS=False, V3_FIELD_RELATIONS_SWITCH=switch)):
                self.assertNotIn('ordinary_field_contract', g.configuration(fields))

    def test_the_production_renderer_accepts_the_explicit_switch(self):
        from ops import deployment_profile, render_production_environment as render
        from quillmd import application_profile as profile
        base = {'QUILLMD_DEPLOYMENT_PROFILE': 'production'}
        for value in ('0', '1'):
            parsed = render.parse(json.dumps({**base, 'QUILLMD_V3_FIELD_RELATIONS': value}))
            self.assertEqual(parsed['QUILLMD_V3_FIELD_RELATIONS'], value)
        for value in ('true', 'on', '2', 'yes'):
            with self.subTest(value=value), self.assertRaises(render.RenderError):
                render.parse(json.dumps({**base, 'QUILLMD_V3_FIELD_RELATIONS': value}))
        self.assertIn('QUILLMD_V3_FIELD_RELATIONS', deployment_profile.APPLICATION_FEATURE_FLAGS)
        self.assertEqual([profile.field_relations_switch(e) for e in
                          ({}, {'QUILLMD_V3_FIELD_RELATIONS': ''}, {'QUILLMD_V3_FIELD_RELATIONS': '0'},
                           {'QUILLMD_V3_FIELD_RELATIONS': '1'})], [None, None, False, True])
        with self.assertRaises(profile.ProfileError):
            profile.field_relations_switch({'QUILLMD_V3_FIELD_RELATIONS': 'true'})

    def test_real_mode_never_inherits_the_contract_from_a_model_string(self):
        from quillmd import application_profile as profile
        kwargs = dict(allowed_hosts=['app.quillmd.com'], session_cookie_secure=True, csrf_cookie_secure=True,
                      email_mode='resend', app_base_url='https://app.quillmd.com', stripe_mode='live', stripe_secret_key='')
        env = {'QUILLMD_AI_MODEL': g.SONNET_5_5}
        problem = "QUILLMD_V3_FIELD_RELATIONS must be set to '0' or '1' with claude-sonnet-5-5 in real mode"
        self.assertIn(problem, profile.real_mode_problems(env, **kwargs))
        for value in ('0', '1'):
            self.assertNotIn(problem, profile.real_mode_problems({**env, 'QUILLMD_V3_FIELD_RELATIONS': value}, **kwargs))
        self.assertNotIn(problem, profile.real_mode_problems({'QUILLMD_AI_MODEL': 'claude-sonnet-4-6'}, **kwargs))


#: a large clinic-like form: many short questions under few printed sections, the note long enough that one keyed
#: answer cannot be bounded by one response (`b.needed`).
def large_form(sections=6, per_section=8):
    fields = []
    for s in range(sections):
        for i in range(per_section):
            f = field(f's{s}q{i}', f'Question {s}-{i}', 'long_text')
            f['context'] = f'Section {s}'
            f['locator']['slot'] = f'b/tbl[{s}]/tr[{i}]/tc[1]/p[0]'
            fields.append(f)
    return fields


LARGE_NOTE = ' '.join(f'The patient reports finding {i}.' for i in range(40))


def large_encounter(fields=None, notes=LARGE_NOTE, constraints=None):
    fields = fields or large_form()
    version = SimpleNamespace(pk=uuid.uuid4(), contract='v3', fields=fields, review_requirements=[],
                              template=SimpleNamespace(sha256='a' * 64), generation_constraints=constraints)
    return SimpleNamespace(pk=uuid.uuid4(), revision=0, template_version=version, notes=notes)


@override_settings(**dict(RELATIONS, V3_GENERATION_BATCHES=False))
class RelationsFieldBatches(SimpleTestCase):
    """A relations quote whose complete keyed answer cannot be bounded by one response is split into field batches of
    whole printed sections - without the generic large-form flag or a form-wide manifest - and adopted only whole."""

    def reply(self, plan, ordinal, picks):
        ids = set(plan['parts'][ordinal - 1]['field_ids'])
        body = relation_wire(plan['notes'], plan['fields'], {k: v for k, v in picks.items() if k in ids}, keys=ids)
        return {'model': g.SONNET_5, 'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(body)}]}

    def test_every_field_once_in_bounded_whole_section_requests(self):
        encounter = large_encounter(); config = g.configuration()
        self.assertTrue(b.needed(encounter.template_version.fields, encounter.notes, config))
        with self.assertRaisesMessage(ValidationError, 'exceeds one bounded response'):
            r.compile_request(encounter.notes, encounter.template_version.fields, config)
        plan = b.plan_for(encounter, config)
        self.assertEqual(plan['contract'], b.RELATIONS_PARTS_CONTRACT)
        self.assertIsNone(plan['constraints'])
        self.assertGreater(len(plan['parts']), 1)
        ids = [k for p in plan['parts'] for k in p['field_ids']]
        self.assertEqual(ids, [f['key'] for f in plan['asked']])               # each field exactly once, in form order
        sections = {f['key']: f['context'] for f in plan['asked']}
        for ordinal, part in enumerate(plan['parts'], 1):
            # a printed section is never split across requests
            for other in plan['parts']:
                if other is not part:
                    self.assertFalse({sections[k] for k in part['field_ids']} & {sections[k] for k in other['field_ids']})
            wire = b.request(plan, ordinal); payload = json.loads(wire['messages'][0]['content'])
            self.assertEqual((payload['catalogue'], payload['source_units'], payload['requested_field_ids']),
                             (plan['fields'], plan['units'], part['field_ids']))
            self.assertIsNone(payload['form_constraints'])
            bound = r.response_bound([f for f in plan['asked'] if f['key'] in part['field_ids']], plan['units'])
            self.assertLessEqual(bound, wire['max_tokens'])
            self.assertEqual(b.digest(wire), part['request_sha256'])
        self.assertEqual(Decimal(plan['maximum_charge']), sum(Decimal(p['maximum_charge']) for p in plan['parts']))

    def test_the_union_is_adopted_only_whole(self):
        encounter = large_encounter(); plan = b.plan_for(encounter, g.configuration())
        quote = 'The patient reports finding 7.'
        picks = {'s0q0': [quote]}
        replies = [self.reply(plan, n, picks) for n in range(1, len(plan['parts']) + 1)]
        answers, _ = b.assemble(plan, replies)
        self.assertEqual((answers['s0q0']['status'], answers['s0q0']['text']), ('supported', quote))
        self.assertEqual(len(answers), len(plan['fields']))
        # a part missing, a part answering another part's field, a truncated or refused part: nothing adopted
        with self.assertRaises(ValidationError):
            b.assemble(plan, replies[:-1])
        foreign = json.loads(replies[1]['content'][0]['text'])
        foreign['fields'][plan['parts'][0]['field_ids'][0]] = foreign['fields'].pop(plan['parts'][1]['field_ids'][0])
        with self.assertRaises(ValidationError):
            b.parse_part(plan, 2, {**replies[1], 'content': [{'type': 'text', 'text': json.dumps(foreign)}]})
        for changed in ({**replies[1], 'stop_reason': 'max_tokens'}, {**replies[1], 'model': g.SONNET_5_5},
                        {**replies[1], 'content': [{'type': 'refusal'}]}):
            with self.subTest(changed=changed.get('stop_reason'), model=changed.get('model')):
                with self.assertRaises(ValidationError):
                    b.assemble(plan, [replies[0], changed] + replies[2:])

    def test_a_section_larger_than_one_response_is_refused_not_split(self):
        fields = large_form(sections=1, per_section=60)
        with self.assertRaisesMessage(ValidationError, 'indivisible'):
            b.plan_for(large_encounter(fields), g.configuration())

    def test_the_generic_flag_and_a_manifest_keep_their_own_contract(self):
        from core.tests.test_generation_batch import manifest
        encounter = large_encounter()
        encounter.template_version.generation_constraints = manifest(encounter.template_version.fields)
        with override_settings(V3_GENERATION_BATCHES=True):
            plan = b.plan_for(encounter, g.configuration())
        self.assertEqual(plan['contract'], b.CONTRACT)
        self.assertEqual(plan['constraints'], encounter.template_version.generation_constraints)
        # a relations-parts plan whose manifest appears or whose config loses the contract is refused before a send
        plain = b.plan_for(large_encounter(), g.configuration())
        with override_settings(V3_FIELD_RELATIONS=False), self.assertRaises(ValidationError):
            b.request({**plain, 'config': {**plain['config'], 'ordinary_field_contract': None}}, 1)
        with override_settings(V3_FIELD_RELATIONS=False), self.assertRaises(ValidationError):
            b.require_config(plain['config'])

    def test_a_single_response_form_keeps_the_single_request(self):
        notes = OPENER + ' She takes warfarin.'
        self.assertFalse(b.needed(clinic_form(), notes, g.configuration()))
