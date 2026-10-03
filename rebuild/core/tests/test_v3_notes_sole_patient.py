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
        # (refutation round 6, L1:F4) N01 has two lines naming no topic of their own ('Neurological examination is
        # normal.', 'She will follow up in six weeks.'): nothing in them shows what they are about, so either may change
        # any answer and nothing in N01 is released - as on the base
        for key, picks, choices in (('v3_4', ['She takes ibuprofen as needed.'], None),
                                    ('v3_6', ['She is a nonsmoker.'], NO),
                                    ('v3_9', ['Plan is to start amitriptyline 10 mg at night.',
                                              'She will follow up in six weeks.'], None)):
            with self.subTest(key=key):
                self.assert_held(N01, fields, {key: picks}, key, choices=choices)
        # without them the smoking answer is released; the medication answer stays held beside the history's symptom
        # denial and 'No known drug allergies.' (round 6, L1:F3: a denial of a class bearing on the answer's)
        without = N01.replace(' Neurological examination is normal.', '').replace(' She will follow up in six weeks.', '')
        self.assert_filled(without, fields, {'v3_6': ['She is a nonsmoker.']}, {'v3_6': 'No'}, choices=NO)
        self.assert_held(without, fields, {'v3_4': ['She takes ibuprofen as needed.']}, 'v3_4')
        # (round 5, R1) the history's symptom denial is held: two other lines name a symptom ('headaches'), and only
        # meaning says a headache is not the visual change, nausea or weakness it denies - fail closed, as the base
        self.assert_held(N01, fields, {'v3_2': ['The headaches started two months ago and are worse in the morning.',
                                                'She denies visual changes, nausea, or weakness.']}, 'v3_2')
        self.assert_filled(N03, order_form(), {'v3_2': ['She attends the clinic every week.']},
                           {'v3_2': 'She attends the clinic every week.'})
        # The explicit-subject form of the same statement stays filled (its completeness comes from `syntax_complete`,
        # its patient from the single-patient reading).
        explicit = 'The patient attends the clinic every week.'
        self.assert_filled(N03.replace('She attends the clinic every week.', explicit), order_form(),
                           {'v3_2': [explicit]}, {'v3_2': explicit})
        # ... but not a habit verb left without what it is about ('She attends weekly.': attends what?) - only an
        # intransitive habit ('She smokes.') is whole on its own
        bare = 'She attends weekly.'
        self.assert_held(N03.replace('She attends the clinic every week.', bare), order_form(), {'v3_2': [bare]}, 'v3_2')
        # (refutation round 6, L1:F3) the examination beside the assessment's doubt naming a condition-like term ('a
        # probable medial meniscus tear') is held, as the round-5 R2 rule asked: the doubt's class bears on a finding
        exam ='On examination there is a small effusion and medial joint line tenderness.'
        self.assert_held(N04, fields, {'v3_7': [exam]}, 'v3_7')
        self.assert_filled(N04.replace(' Assessment is a probable medial meniscus tear.', ''), fields, {'v3_7': [exam]},
                           {'v3_7': exam})
        prodrome = 'The patient sees zigzag lines before the headache begins.'
        self.assert_filled(N02, repeated_other(), {'v3_2': [prodrome]}, {'v3_2': prodrome})

    def test_the_presenting_opener_with_an_article(self):
        notes = 'A ' + N04
        exam = 'On examination there is a small effusion and medial joint line tenderness.'
        # (refutation round 6, L1:F3) held beside the assessment's doubt (`test_the_freezes_answers_are_filled`)
        self.assert_held(notes, clinic_form(), {'v3_7': [exam]}, 'v3_7')
        self.assert_filled(notes.replace(' Assessment is a probable medial meniscus tear.', ''), clinic_form(),
                           {'v3_7': [exam]}, {'v3_7': exam})
        # (round 5, R2) the complaint ('knee pain ... after a fall', an injury) beside the assessment's doubt about an
        # injury ('a probable medial meniscus tear') is held: the doubt names a condition-like term of its class
        self.assert_held(notes, clinic_form(), {'v3_1': ['A ' + N04.split('. ')[0] + '.']}, 'v3_1')
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
    ('an unplaced second answer', OPENER + ' She takes warfarin. She takes aspirin.', 'She takes warfarin.', 'v3_4', None),
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
                # (refutation round 6, L1:F3: 'She has asthma.' beside 'She takes no medicines.' is held both ways, as
                # round 5 R1 holds the denial beside a condition - `AnotherLineDenyingABearingClass`)
                (OPENER + ' She has asthma. She is a nonsmoker.', 'She has asthma.', 'v3_3', None, 'She has asthma.'),
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

    def test_self_refutation_lines_hold_the_answer(self):
        """Fresh lines written after the design (probes2, probes3): a line naming no topic that negates, contrasts or
        sides something, an unlabelled fragment naming no topic, an 'NKDA', and a dictated correction each qualify a line
        they do not name."""
        fields = clinic_form()
        hpi, effusion = 'The headaches are worse in the morning.', 'On examination there is a small effusion in the knee.'
        for notes, pick, key in (
                (OPENER + ' ' + hpi + ' Not in the morning.', hpi, 'v3_2'),
                (OPENER + ' ' + hpi + ' Worse at night instead.', hpi, 'v3_2'),
                (OPENER + ' ' + effusion + ' Bilateral.', effusion, 'v3_7'),
                (OPENER + ' ' + effusion + ' Left side.', effusion, 'v3_7'),
                (OPENER + ' ' + effusion + ' The right knee is also swollen.', effusion, 'v3_7'),
                (OPENER + ' She is allergic to penicillin. NKDA.', 'She is allergic to penicillin.', 'v3_5'),
                (OPENER + ' NKDA. She is allergic to penicillin.', 'She is allergic to penicillin.', 'v3_5'),
                (OPENER + ' She has asthma. Make that aspirin.', 'She has asthma.', 'v3_3'),
                (OPENER + ' ' + hpi + ' Worse at night.', hpi, 'v3_2'),
                (OPENER + ' She takes warfarin. Last week.', 'She takes warfarin.', 'v3_4'),
                (OPENER + ' She takes ibuprofen as needed. Every day.', 'She takes ibuprofen as needed.', 'v3_4'),
                (OPENER + ' Severe. She has asthma.', 'She has asthma.', 'v3_3'),
                # a complete line naming no topic but a side
                (OPENER + ' ' + effusion + ' The right knee is swollen.', effusion, 'v3_7'),
                # uncertainty outside an assessment's own line withdraws the note's single-patient scope
                (OPENER + ' She takes warfarin. Asthma is uncertain.', 'She takes warfarin.', 'v3_4'),
                (OPENER + ' She takes warfarin. The asthma is uncertain.', 'She takes warfarin.', 'v3_4'),
                # a line continuing another ('And ...') inherits its subject: it is not whole on its own
                (OPENER + ' She has asthma. And takes warfarin.', 'And takes warfarin.', 'v3_4'),
                # (refutation round 6, L1:F4) a complete line naming no topic of its own may be about any answer
                (OPENER + ' ' + hpi + ' She will follow up in six weeks.', hpi, 'v3_2'),
                (OPENER + ' ' + effusion + ' She will follow up in six weeks.', effusion, 'v3_7'),
                (OPENER + ' She is allergic to penicillin. She will follow up in six weeks.',
                 'She is allergic to penicillin.', 'v3_5'),
                (OPENER + ' She has asthma. She will follow up in six weeks.', 'She has asthma.', 'v3_3')):
            with self.subTest(notes=notes):
                self.assert_held(notes, fields, {key: [pick]}, key)
        # controls: the same answers beside a complete line about something else (another finding beside the
        # examination is the examination's own unplaced topic, held by design) - a topic bearing on none of them
        follow = ' She is a nonsmoker.'
        for notes, pick, key in ((OPENER + ' ' + hpi + follow, hpi, 'v3_2'),
                                 (OPENER + ' ' + effusion + follow, effusion, 'v3_7'),
                                 (OPENER + ' She is allergic to penicillin.' + follow, 'She is allergic to penicillin.',
                                  'v3_5'),
                                 (OPENER + ' She has asthma.' + follow, 'She has asthma.', 'v3_3'),
                                 # 'NKDA' is about allergy: it cannot change a medication answer
                                 (OPENER + ' She takes warfarin. NKDA.', 'She takes warfarin.', 'v3_4')):
            with self.subTest(control=notes):
                self.assert_filled(notes, fields, {key: [pick]}, {key: pick})

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
                ({'V3_FIELD_RELATIONS': False, 'V3_FIELD_RELATIONS_SWITCH': False}, g.SONNET_5_5, False),
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
        # (part 2's first answer renamed to a field part 1 asks)
        next(item for item in foreign['fields'] if item['key'] == plan['parts'][1]['field_ids'][0])['key'] = \
            plan['parts'][0]['field_ids'][0]
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


# ─── Refutation round 4 (notes-notes-refute-verify, 2026-10-01): rows 0e9f1025 adopted and f5fe720f held ─────────────
#: The line breaks every row is read under (the refuters' four variants).
SEPARATORS = {'space': ' ', 'newline': '\n', 'blank line': '\n\n', 'crlf': '\r\n'}
W45 = 'A 45-year-old woman presents with cough.'
M45 = 'A 45-year-old man presents with cough.'


class RoundFour(Floors):
    def held_everywhere(self, rows):
        for lines, pick, key, choices in rows:
            for name, sep in SEPARATORS.items():
                with self.subTest(notes=lines, separator=name):
                    self.assert_held(sep.join(lines), clinic_form(), {key: [pick]}, key, choices=choices)

    def filled_everywhere(self, rows):
        for lines, pick, key, choices, text in rows:
            for name, sep in SEPARATORS.items():
                with self.subTest(notes=lines, separator=name):
                    self.assert_filled(sep.join(lines), clinic_form(), {key: [pick]}, {key: text}, choices=choices)


@override_settings(**RELATIONS)
class OnePresentedPerson(RoundFour, SimpleTestCase):
    """R2-F1: a presenting line naming TWO age-described people ('A 4-year-old girl presents with a 30-year-old man.')
    presents no single patient, whatever their genders: nothing in the note is released as the patient's."""

    def test_an_opener_presenting_two_people_releases_nothing(self):
        girl_man, boy_woman = 'A 4-year-old girl presents with a 30-year-old man.', 'A 4-year-old boy presents with a 30-year-old woman.'
        six = 'A 6-year-old boy presents with a 40-year-old woman.'
        self.held_everywhere((
            ([girl_man, 'He takes warfarin.'], 'He takes warfarin.', 'v3_4', None),
            ([girl_man, 'He is allergic to penicillin.'], 'He is allergic to penicillin.', 'v3_5', None),
            ([boy_woman, 'She has asthma.'], 'She has asthma.', 'v3_3', None),
            ([boy_woman, 'She has asthma.'], 'She has asthma.', 'v3_8', None),
            ([six, 'She smokes.'], 'She smokes.', 'v3_6', YES),
            ([six, 'She smokes twenty cigarettes a day.', 'Smoker: Yes.'], 'Smoker: Yes.', 'v3_6', YES),
            ([six, 'She smokes twenty cigarettes a day.', 'Smoker: Yes.'], 'She smokes twenty cigarettes a day.', 'v3_6', YES),
            (['A 35-year-old man presents with a 5-year-old girl.', 'She has a cough.'], 'She has a cough.', 'v3_2', None),
            (['A 35-year-old man presents with a 5-year-old girl.', 'She has a cough.'], 'She has a cough.', 'v3_1', None),
            (['A 70-year-old woman presents with a 45-year-old male.', 'He takes warfarin.'], 'He takes warfarin.', 'v3_4', None),
            (['A 70-year-old woman presents with a 45-year-old woman.', 'She takes warfarin.'], 'She takes warfarin.', 'v3_4',
             None)))

    def test_the_presenting_line_describes_exactly_one_thing_by_age(self):
        # whatever the second age-described noun is, the presenting line is not positively one patient's
        self.held_everywhere((
            (['A 45-year-old man presents with a 2-year-old fracture.', 'He takes warfarin.'], 'He takes warfarin.', 'v3_4',
             None),))

    def test_a_second_presentation_is_a_second_patient(self):
        # (self-refutation of the round-4 repair) two presenting lines are two patients, with or without the article
        self.held_everywhere((
            (['30-year-old woman presents with headaches.', '50-year-old woman presents with cough.', 'She takes warfarin.'],
             'She takes warfarin.', 'v3_4', None),
            ([OPENER, 'A 50-year-old woman presents with cough.', 'She takes warfarin.'], 'She takes warfarin.', 'v3_4', None),
            ([OPENER, 'This is a 50-year-old woman seen for cough.', 'She takes warfarin.'], 'She takes warfarin.', 'v3_4',
             None)))

    def test_one_presented_person_still_releases(self):
        self.filled_everywhere((
            ([M45, 'He takes warfarin.'], 'He takes warfarin.', 'v3_4', None, 'He takes warfarin.'),
            ([W45, 'She has asthma.'], 'She has asthma.', 'v3_3', None, 'She has asthma.'),
            ([OPENER, 'She smokes.'], 'She smokes.', 'v3_6', YES, 'Yes')))


@override_settings(**RELATIONS)
class PatientNounPhrases(RoundFour, SimpleTestCase):
    """R2-F2: 'patient' names THIS note's patient only as 'the patient' / 'this patient' with nothing else said of the
    noun: a plural, an indefinite, a possessor, an age or any other modifier may be somebody else."""

    def test_another_or_any_patient_is_not_released(self):
        self.held_everywhere((
            ([W45, 'Some patients are allergic to penicillin.'], 'Some patients are allergic to penicillin.', 'v3_5', None),
            ([W45, 'All patients take aspirin daily.'], 'All patients take aspirin daily.', 'v3_4', None),
            ([W45, 'The male patient takes aspirin daily.'], 'The male patient takes aspirin daily.', 'v3_4', None),
            ([W45, 'Her patient has asthma.'], 'Her patient has asthma.', 'v3_3', None),
            ([W45, 'The older patient takes warfarin.'], 'The older patient takes warfarin.', 'v3_4', None),
            ([W45, 'A patient is allergic to penicillin.'], 'A patient is allergic to penicillin.', 'v3_5', None),
            ([W45, 'The 70-year-old patient has asthma.', 'She is allergic to penicillin.'], 'She is allergic to penicillin.',
             'v3_5', None),
            ([W45, 'Another patient takes warfarin.'], 'Another patient takes warfarin.', 'v3_4', None),
            ([W45, 'The other patient takes warfarin.'], 'The other patient takes warfarin.', 'v3_4', None),
            ([W45, 'The patients take warfarin.'], 'The patients take warfarin.', 'v3_4', None)))

    def test_the_patient_and_this_patient_are_the_presented_patient(self):
        self.filled_everywhere((
            ([W45, 'This patient takes warfarin.'], 'This patient takes warfarin.', 'v3_4', None,
             'This patient takes warfarin.'),
            ([W45, 'She has asthma.', 'The patient is allergic to penicillin.'], 'She has asthma.', 'v3_3', None,
             'She has asthma.')))


@override_settings(**RELATIONS)
class AssessmentNamingTheAnswer(RoundFour, SimpleTestCase):
    """R2-F3: an exclusion is a denial, not a doubt; and an assessment's doubt or denial about the answer's OWN word
    ('Assessment: asthma unlikely.' beside 'She has asthma.') may change it - only an assessment about something else
    is set apart from it."""

    def test_an_assessment_excluding_or_doubting_the_answer_holds_it(self):
        self.held_everywhere((
            ([W45, 'She has asthma.', 'Assessment: asthma excluded.'], 'She has asthma.', 'v3_3', None),
            ([M45, 'He has diabetes.', 'Assessment: diabetes excluded.'], 'He has diabetes.', 'v3_3', None),
            (['A 45-year-old woman presents with wheeze.', 'She has asthma.', 'Assessment: asthma excluded.'],
             'She has asthma.', 'v3_1', None),
            (['A 45-year-old woman presents with wheeze.', 'She has asthma.', 'Assessment: asthma excluded.'],
             'She has asthma.', 'v3_2', None),
            ([W45, 'Assessment: asthma excluded.', 'She has asthma.'], 'She has asthma.', 'v3_3', None),
            ([W45, 'She has asthma.', 'Assessment: asthma unlikely.'], 'She has asthma.', 'v3_3', None),
            ([W45, 'She has asthma.', 'Assessment: asthma ruled out.'], 'She has asthma.', 'v3_3', None),
            ([W45, 'She has asthma.', 'Assessment: possible asthma.'], 'She has asthma.', 'v3_3', None),
            ([W45, 'She has eczema.', 'Assessment: eczema excluded.'], 'She has eczema.', 'v3_3', None),
            # an exclusion is a denial whatever it names: one of a broader class may deny the answer ('lung disease')
            ([W45, 'She has asthma.', 'Assessment: lung disease excluded.'], 'She has asthma.', 'v3_3', None),
            ([W45, 'She has asthma.', 'Assessment: lung disease ruled out.'], 'She has asthma.', 'v3_3', None)))

    def test_an_assessment_about_something_else_does_not(self):
        # (round 5, R2; refutation round 6, L1:F3) 'about something else' is a topic class bearing on neither: a doubt
        # naming a condition-like term holds every clinical answer ('Assessment: probable eczema.' or 'probable knee
        # sprain' beside 'She has asthma.', `AnotherLineDenyingABearingClass`), and is apart from a smoking answer
        self.filled_everywhere((
            ([W45, 'She is a nonsmoker.', 'Assessment: probable asthma.'], 'She is a nonsmoker.', 'v3_6', NO, 'No'),))
        self.held_everywhere((
            ([W45, 'She has asthma.', 'Assessment: probable eczema.'], 'She has asthma.', 'v3_3', None),))


@override_settings(**RELATIONS)
class BareRepairRepeatedValue(RoundFour, SimpleTestCase):
    """R2-F4: a bare backward repair ('Sorry, I mean warfarin.') withdraws the value before it; a later line that may
    repeat the withdrawn value is still governed by it. Only a later answer POSITIVELY about another topic is set
    apart from it."""

    def test_a_later_line_on_the_repaired_topic_is_held(self):
        self.held_everywhere((
            (['Medications: aspirin.', 'Sorry, I mean warfarin.', 'Plan: continue aspirin.'], 'Plan: continue aspirin.',
             'v3_9', None),
            (['Past medical history: asthma.', 'Sorry, I mean angina.', 'Assessment: asthma.'], 'Assessment: asthma.',
             'v3_8', None),
            (['Examination: left knee effusion.', 'Sorry, I mean shoulder.', 'Assessment: left knee effusion.'],
             'Assessment: left knee effusion.', 'v3_8', None),
            (['Chief complaint: cough.', 'Sorry, I mean wheeze.', 'History of present illness: cough for a week.'],
             'History of present illness: cough for a week.', 'v3_2', None),
            # a later line about the repaired topic in words the lexicon does not know may repeat it ('ASA')
            (['Medications: aspirin.', 'Sorry, I mean warfarin.', 'Plan: continue ASA.'], 'Plan: continue ASA.', 'v3_9',
             None),
            (['Allergies: penicillin.', 'Sorry, I mean amoxicillin.', 'Plan: avoid penicillin.'], 'Plan: avoid penicillin.',
             'v3_9', None),
            # ... and one on the repaired topic in other words: a penicillin to start after a repaired drug allergy
            (['Allergies: penicillin.', 'Sorry, I mean amoxicillin.', 'Plan: start flucloxacillin.'],
             'Plan: start flucloxacillin.', 'v3_9', None)))

    def test_a_later_answer_about_another_topic_is_still_answered(self):
        for sep in (' ', '\n'):
            notes = sep.join(['Patient presents with a rash on both forearms.', 'Allergies: penicillin. Sorry, I mean '
                              'amoxicillin.', 'Smoker: No.'])
            with self.subTest(separator=sep):
                self.assert_filled(notes, clinic_form(), {'v3_6': ['Smoker: No.']}, {'v3_6': 'No'}, choices=NO)



@override_settings(**RELATIONS)
class GroupsNamesAndOtherQuestions(RoundFour, SimpleTestCase):
    """R2-F5 and R2-F6 (refutation round 4, confirmed LOW): a pronoun that can stand for a group ('Both have asthma.',
    'All take warfarin.') or a bare noun standing as the one who has or takes something ('Spot has a rash.': a name the
    lexicon happens to know) is not positively the patient; and a printed question with a word the lexicons do not know
    ('Maternal conditions', 'Discontinued medications') is not positively about the patient now. Nothing is released."""

    def test_a_group_pronoun_or_a_bare_named_bearer_is_not_the_patient(self):
        itch = 'A 45-year-old woman presents with itching.'
        self.held_everywhere((
            ([W45, 'Both have asthma.'], 'Both have asthma.', 'v3_3', None),
            ([W45, 'All have asthma.'], 'All have asthma.', 'v3_3', None),
            ([W45, 'All take warfarin.'], 'All take warfarin.', 'v3_4', None),
            ([W45, 'These take warfarin.'], 'These take warfarin.', 'v3_4', None),
            ([itch, 'Spot has a rash.'], 'Spot has a rash.', 'v3_7', None),
            ([itch, 'Spot has a rash.'], 'Spot has a rash.', 'v3_2', None),
            ([W45, 'Spot is allergic to penicillin.'], 'Spot is allergic to penicillin.', 'v3_5', None),
            ([W45, 'Spot has a rash.', 'She takes warfarin.'], 'She takes warfarin.', 'v3_4', None)))

    def test_a_thing_as_a_subject_is_still_a_thing(self):
        self.filled_everywhere((
            ([W45, 'The rash is red.'], 'The rash is red.', 'v3_7', None, 'The rash is red.'),
            ([W45, 'Knee pain is worse at night.', 'She takes warfarin.'], 'She takes warfarin.', 'v3_4', None,
             'She takes warfarin.')))
        # (round 5, R3) a BARE noun subject may be a name whatever its verb ('Spot is in pain.'): 'Pain is worse at
        # night.' is held with it, fail closed (the base holds both)
        self.held_everywhere((
            ([W45, 'Pain is worse at night.', 'She takes warfarin.'], 'She takes warfarin.', 'v3_4', None),))

    def test_a_question_with_an_unknown_word_is_not_answered(self):
        for label, notes, pick in (('Maternal conditions', W45 + ' She has asthma.', 'She has asthma.'),
                                   ('Familial conditions', W45 + ' She has asthma.', 'She has asthma.'),
                                   ('Paternal medications', W45 + ' She takes warfarin.', 'She takes warfarin.'),
                                   ('Discontinued medications', W45 + ' She takes warfarin.', 'She takes warfarin.'),
                                   ('Stopped medications', W45 + ' She takes warfarin.', 'She takes warfarin.'),
                                   ('Declined treatment', W45 + ' She takes warfarin.', 'She takes warfarin.'),
                                   # a question framed in another time or a part of the day
                                   ('Old medications', W45 + ' She takes warfarin.', 'She takes warfarin.'),
                                   ('New medications', W45 + ' She takes warfarin.', 'She takes warfarin.'),
                                   ('Night medications', W45 + ' She takes ibuprofen in the morning.',
                                    'She takes ibuprofen in the morning.'),
                                   ('Morning medications', W45 + ' She takes amitriptyline at night.',
                                    'She takes amitriptyline at night.'),
                                   ('Daily medications', W45 + ' She takes ibuprofen as needed.',
                                    'She takes ibuprofen as needed.'),
                                   # a question whose verb is not present: a plan, a past act, a condition
                                   ('Medications to start', W45 + ' She takes warfarin.', 'She takes warfarin.'),
                                   ('Medications to be started', W45 + ' She takes warfarin.', 'She takes warfarin.'),
                                   ('Medications needed', W45 + ' She takes warfarin.', 'She takes warfarin.'),
                                   ('Medications started', W45 + ' She takes warfarin.', 'She takes warfarin.')):
            with self.subTest(label=label):
                self.assert_held(notes, [v3('f', label, 'long_text', TITLE)], {'f': [pick]}, 'f')
        self.assertTrue(actors.neutral_field('Current medications', TITLE))
        self.assertTrue(actors.neutral_field('Medications', TITLE))
        self.assert_filled(W45 + ' She takes warfarin.', [v3('f', 'Current medications', 'long_text', TITLE)],
                           {'f': ['She takes warfarin.']}, {'f': 'She takes warfarin.'})

WI = 'A 45-year-old woman presents with itching.'


@override_settings(**RELATIONS)
class DenialAgainstItsClass(RoundFour, SimpleTestCase):
    """Refutation round 5, R1: an answer that denies, ends or contraindicates ('She takes no medicines.', 'She has no
    allergies.', 'She is allergic to paracetamol.') is held by ANY other line - the presenting line and another
    question's labelled line included - naming a topic class it bears on (`v3_actors.sole_bears_on`), or, for a
    clinical or allergy denial, a word that may describe the state it denies. A general noun, a drug or condition name,
    a synonym or a UK/US spelling shares no word with the denial; the model's 'independent' for that line is not
    believed."""

    def test_a_denial_beside_its_class_in_other_words_is_held(self):
        bleeding = 'A 45-year-old woman presents with bleeding on {}.'
        self.held_everywhere((
            ([bleeding.format('warfarin'), 'She takes no medicines.'], 'She takes no medicines.', 'v3_4', None),
            ([bleeding.format('warfarin'), 'She takes no tablets.'], 'She takes no tablets.', 'v3_4', None),
            ([bleeding.format('warfarin'), 'She takes no pills.'], 'She takes no pills.', 'v3_4', None),
            ([bleeding.format('apixaban'), 'She takes no medicines.'], 'She takes no medicines.', 'v3_4', None),
            ([bleeding.format('apixaban'), 'She takes no drug.'], 'She takes no drug.', 'v3_4', None),
            ([W45, 'Chief complaint: bleeding on apixaban.', 'She takes no drug.'], 'She takes no drug.', 'v3_4', None),
            ([W45, 'Assessment: diabetes on insulin.', 'She takes no medicines.'], 'She takes no medicines.', 'v3_4',
             None),
            # a condition named alone may be a treated one: a medication denial is not positively apart from it
            ([W45, 'Assessment: diabetes.', 'She takes no medicines.'], 'She takes no medicines.', 'v3_4', None),
            (['A 45-year-old woman presents with diabetes on insulin.', 'She takes no drug.'], 'She takes no drug.',
             'v3_4', None),
            ([W45, 'Chief complaint: diarrhoea.', 'She has no diarrhea.'], 'She has no diarrhea.', 'v3_2', None),
            (['A 45-year-old woman presents with diarrhoea.', 'She has no diarrhea.'], 'She has no diarrhea.', 'v3_2',
             None),
            (['A 45-year-old woman presents with fever.', 'She has no temperature.'], 'She has no temperature.', 'v3_2',
             None),
            (['A 45-year-old woman presents with migraine.', 'She has no headache.'], 'She has no headache.', 'v3_2',
             None),
            (['A 45-year-old woman presents with wheeze.', 'She has no breathlessness.'], 'She has no breathlessness.',
             'v3_2', None),
            ([W45, 'She has no tumor.', 'Assessment: tumour.'], 'She has no tumor.', 'v3_3', None),
            ([W45, 'She has no condition.', 'Assessment: diabetes.'], 'She has no condition.', 'v3_3', None),
            (['A 45-year-old woman presents with asthma.', 'She has no illness.'], 'She has no illness.', 'v3_3', None),
            (['A 45-year-old woman presents with knee effusion.', 'There is no swelling.'], 'There is no swelling.',
             'v3_7', None),
            (['A 45-year-old woman presents with anaphylaxis.', 'She has no allergies.'], 'She has no allergies.', 'v3_5',
             None),
            (['A 45-year-old woman presents with a rash after amoxicillin.', 'She has no allergies.'],
             'She has no allergies.', 'v3_5', None),
            # a contraindication beside the same drug in its other name
            ([W45, 'She is allergic to paracetamol.', 'Medications: acetaminophen.'], 'She is allergic to paracetamol.',
             'v3_5', None),
            # a word that may describe what is denied, with no topic noun of its own
            (['A 45-year-old woman presents with knee pain.', 'The knee is swollen.', 'There is no swelling.'],
             'There is no swelling.', 'v3_7', None),
            (['A 45-year-old woman presents for attendance.', 'The knee is swollen.', 'There is no swelling.'],
             'There is no swelling.', 'v3_7', None)))

    def test_a_denial_beside_other_classes_only_is_still_answered(self):
        self.filled_everywhere((
            ([M45, 'He takes no medicines.'], 'He takes no medicines.', 'v3_4', None, 'He takes no medicines.'),
            ([W45, 'She is a nonsmoker.'], 'She is a nonsmoker.', 'v3_6', NO, 'No'),
            ([OPENER, 'She is allergic to penicillin.'], 'She is allergic to penicillin.', 'v3_5', None,
             'She is allergic to penicillin.'),
            (['A 45-year-old woman presents for attendance.', 'There is no swelling.'], 'There is no swelling.', 'v3_7',
             None, 'There is no swelling.')))
        self.assertEqual(actors.sole_bears_on({'smoking'}), {'smoking'})
        self.assertLessEqual(actors.SOLE_CLINICAL, actors.sole_bears_on({'allergy'}))
        # a class with no row bears on every class (fail closed)
        self.assertEqual(actors.sole_bears_on({'care'}), actors.SOLE_EVERY_CLASS)


@override_settings(**RELATIONS)
class DoubtAboutItsClass(RoundFour, SimpleTestCase):
    """Refutation round 5, R2: an assessment's doubt is set apart only where it names no condition-like term of the
    answer's class; a spelling variant or a synonym of the answer's own condition holds it."""

    def test_a_doubt_in_other_words_holds_the_answer(self):
        self.held_everywhere((
            ([W45, 'She has diarrhoea.', 'Assessment: diarrhea unlikely.'], 'She has diarrhoea.', 'v3_2', None),
            ([W45, 'She has a tumour.', 'Assessment: tumor unlikely.'], 'She has a tumour.', 'v3_3', None),
            ([W45, 'She has a temperature.', 'Assessment: fever unlikely.'], 'She has a temperature.', 'v3_2', None),
            ([WI, 'She has eczema.', 'Assessment: dermatitis unlikely.'], 'She has eczema.', 'v3_3', None),
            ([W45, 'She has fatigue.', 'Assessment: tiredness unlikely.'], 'She has fatigue.', 'v3_2', None),
            ([W45, 'She has a migraine.', 'Assessment: headache unlikely.'], 'She has a migraine.', 'v3_2', None),
            (['A 45-year-old woman presents with knee pain.', 'She has osteoarthritis.', 'Assessment: arthritis unlikely.'],
             'She has osteoarthritis.', 'v3_3', None)))


@override_settings(**RELATIONS)
class BareNamedSubject(RoundFour, SimpleTestCase):
    """Refutation round 5, R3: a noun standing ALONE as a subject or a possessor may be a name the lexicon knows, with
    any verb ('Spot is in pain.', 'Spot is with fever.', 'Spot itches.', "Spot's knee ..."): not the patient."""

    def test_a_bare_name_with_be_and_a_preposition_is_not_the_patient(self):
        self.held_everywhere((
            ([WI, 'Spot is in pain.'], 'Spot is in pain.', 'v3_2', None),
            ([WI, 'Spot is in pain.'], 'Spot is in pain.', 'v3_1', None),
            ([WI, 'Flash is in pain.'], 'Flash is in pain.', 'v3_2', None),
            ([WI, 'Spot is with fever.'], 'Spot is with fever.', 'v3_2', None),
            ([WI, 'Spot is in pain at night.'], 'Spot is in pain at night.', 'v3_2', None),
            ([WI, 'Spot itches.'], 'Spot itches.', 'v3_2', None),
            ([WI, "Spot's knee has an effusion."], "Spot's knee has an effusion.", 'v3_7', None),
            ([WI, 'Spot is in pain.', 'She takes warfarin.'], 'She takes warfarin.', 'v3_4', None)))

    def test_a_determined_thing_or_a_heading_word_is_still_a_thing(self):
        self.filled_everywhere((
            ([WI, 'The rash is red.'], 'The rash is red.', 'v3_7', None, 'The rash is red.'),
            ([W45, 'Assessment is asthma.', 'She takes warfarin.'], 'She takes warfarin.', 'v3_4', None,
             'She takes warfarin.')))



@override_settings(**RELATIONS)
class AnotherLineDenyingABearingClass(RoundFour, SimpleTestCase):
    """Refutation round 6, L1:F3: a POSITIVE answer ('She takes warfarin.', 'She has hypertension.') is held by another
    line that denies, ends or doubts a topic class bearing on its own in either direction (`v3_actors.sole_bears_on`):
    'treatment', 'problem', 'blood pressure problem' share no class with the answer, so the class-sharing rule alone let
    the model's 'independent' stand. And, as the original R2 asked, an assessment's doubt naming a condition-like term
    holds a clinical answer whatever its class ('He has knee pain.' beside 'Assessment is a probable medial meniscus
    tear.')."""

    def test_a_denial_of_a_class_bearing_on_the_answer_holds_it(self):
        self.held_everywhere((
            ([OPENER, 'She takes warfarin.', 'She is on no treatment.'], 'She takes warfarin.', 'v3_4', None),
            ([OPENER, 'She has hypertension.', 'She denies any blood pressure problem.'], 'She has hypertension.',
             'v3_3', None),
            ([OPENER, 'She has hypertension.', 'Assessment: blood pressure problem unlikely.'], 'She has hypertension.',
             'v3_3', None),
            ([OPENER, 'She has insomnia.', 'She denies any sleep problem.'], 'She has insomnia.', 'v3_3', None),
            ([OPENER, 'She has depression.', 'She denies any mood problem.'], 'She has depression.', 'v3_3', None),
            ([OPENER, 'She will start amitriptyline 10 mg at night.', 'She needs no treatment.'],
             'She will start amitriptyline 10 mg at night.', 'v3_9', None),
            ([OPENER, 'She takes insulin.', 'Her diabetes needs no treatment.'], 'She takes insulin.', 'v3_4', None),
            ([OPENER, 'She takes warfarin.', 'She has stopped all treatment.'], 'She takes warfarin.', 'v3_4', None),
            # the denial before the answer
            ([OPENER, 'She is on no treatment.', 'She takes warfarin.'], 'She takes warfarin.', 'v3_4', None),
            # a condition beside a medication denial: round 5 R1 holds the denial, so the pair is held both ways
            ([OPENER, 'She has asthma.', 'She takes no medicines.'], 'She has asthma.', 'v3_3', None),
            # each direction of the bearing: a clinical denial bears on a medication answer, and a symptom answer bears
            # on a medication denial
            ([OPENER, 'She takes warfarin.', 'She denies any bleeding.'], 'She takes warfarin.', 'v3_4', None),
            ([OPENER, 'She has a cough.', 'She takes no medicines.'], 'She has a cough.', 'v3_2', None),
            # a doubt naming a condition-like term of another clinical class
            (['A 45-year-old man presents with knee pain.', 'He has knee pain.',
              'Assessment is a probable medial meniscus tear.'], 'He has knee pain.', 'v3_2', None),
            ([W45, 'She has asthma.', 'Assessment: probable knee sprain.'], 'She has asthma.', 'v3_3', None),
            ([W45, 'She takes warfarin.', 'Assessment: no asthma.'], 'She takes warfarin.', 'v3_4', None)))

    def test_a_denial_of_a_class_bearing_on_neither_does_not(self):
        self.filled_everywhere((
            ([W45, 'She is a nonsmoker.', 'Assessment: probable asthma.'], 'She is a nonsmoker.', 'v3_6', NO, 'No'),
            ([W45, 'She takes warfarin.', 'She is a nonsmoker.'], 'She takes warfarin.', 'v3_4', None,
             'She takes warfarin.')))


@override_settings(**RELATIONS)
class ALineWhoseReferentIsElided(RoundFour, SimpleTestCase):
    """Refutation round 6, L1:F4: a line that names no topic of its own ('She has twenty a day.', 'She takes one every
    morning.') or counts something it does not name ('twenty', '20', 'one' standing for a noun) may be about any answer
    of the note: it is not positively apart from any, whatever the model calls it."""

    def test_an_elided_referent_holds_every_answer(self):
        self.held_everywhere((
            ([OPENER, 'She is a nonsmoker.', 'She has twenty a day.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She is a nonsmoker.', 'She has 20 a day.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She does not smoke.', 'She has twenty a day.'], 'She does not smoke.', 'v3_6', NO),
            ([OPENER, 'She takes no medicines.', 'She takes one every morning.'], 'She takes no medicines.', 'v3_4',
             None),
            # a number standing for a noun beside a topic of another class
            ([OPENER, 'She is a nonsmoker.', 'She has twenty a day despite her asthma.'], 'She is a nonsmoker.', 'v3_6',
             NO),
            ([OPENER, 'She is a nonsmoker.', 'She has two every morning with her inhaler.'], 'She is a nonsmoker.',
             'v3_6', NO),
            ([OPENER, 'She is a nonsmoker.', 'She has twenty a day for asthma.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She is a nonsmoker.', 'She has twenty a day with headaches.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She is a nonsmoker.', 'She has asthma and twenty a day.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She is a nonsmoker.', 'She has 20 daily with a cough.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She is a nonsmoker.', 'She has had twenty a day for years.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She takes no medicines.', 'She takes two for headaches.'], 'She takes no medicines.', 'v3_4',
             None),
            ([OPENER, 'She takes no medicines.', 'She takes one at night for the headaches.'], 'She takes no medicines.',
             'v3_4', None),
            ([OPENER, 'She takes warfarin.', 'She has two.'], 'She takes warfarin.', 'v3_4', None),
            # a clause naming no topic at all
            ([OPENER, 'She takes no medicines.', 'She takes daily.'], 'She takes no medicines.', 'v3_4', None),
            ([OPENER, 'She is a nonsmoker.', 'She does now.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She has a headache.', 'She feels better.'], 'She has a headache.', 'v3_2', None)))

    def test_a_number_counting_its_own_noun_does_not(self):
        self.filled_everywhere((
            ([OPENER, 'She is a nonsmoker.', 'She takes warfarin 5 mg daily.'], 'She is a nonsmoker.', 'v3_6', NO, 'No'),
            ([OPENER, 'She is a nonsmoker.', 'She takes salbutamol daily.'], 'She is a nonsmoker.', 'v3_6', NO, 'No'),
            ([OPENER, 'She takes warfarin 5 mg daily.'], 'She takes warfarin 5 mg daily.', 'v3_4', None,
             'She takes warfarin 5 mg daily.')))


@override_settings(**RELATIONS)
class EachEarlierGuardStillHolds(RoundFour, SimpleTestCase):
    """Refutation round 6: the rows that pinned earlier guards are now also held by round 6's broader holds (a line
    naming no topic, a bearing class), so each guard gets a row where it is the only hold: uncertainty outside an
    assessment (round 4), a side in a labelled value naming no topic (self-refutation round 2), a word that may
    describe what a clinical denial denies (round 5, R1), and a non-reflexive object pronoun ('She sees her ...':
    somebody else)."""

    def test_each_guard_alone(self):
        self.held_everywhere((
            ([OPENER, 'She is a nonsmoker.', 'The asthma is uncertain.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She is a nonsmoker.', 'The cough is possibly asthma.'], 'She is a nonsmoker.', 'v3_6', NO),
            ([OPENER, 'She has knee pain.', 'Examination: left side.'], 'She has knee pain.', 'v3_2', None),
            ([OPENER, 'She is a nonsmoker.', 'Examination: left side.'], 'She is a nonsmoker.', 'v3_6', NO),
            (['A 45-year-old woman presents for attendance.', 'The knee is swollen at the clinic.',
              'There is no swelling.'], 'There is no swelling.', 'v3_7', None),
            ([OPENER, 'She sees her for cough.'], 'She sees her for cough.', 'v3_2', None),
            ([OPENER, 'She has asthma.', 'She sees her for cough.'], 'She has asthma.', 'v3_3', None)))

ON55 = dict(LIVE, AI_MODEL=g.SONNET_5_5, V3_HISTORY_CONTEXT=False, V3_FIELD_RELATIONS=False, V3_FIELD_RELATIONS_SWITCH=None,
            V3_GENERATION_BATCHES=False)


class OneSwitchAtEveryReader(SimpleTestCase):
    """NR1-F1: the contract is on for a request or a record only while it is on for the deployment NOW (the configured
    model) AND for the model the request or record names. The gate before a send (`require_config`), the provenance
    (`records`) and the reader of stored answers (`read`) give that one answer, so a job is never sent and charged
    under a contract its result cannot be read under."""

    def test_a_quote_made_under_the_default_is_refused_after_the_deployment_moves_off_it(self):
        with override_settings(**ON55):
            config = g.configuration(clinic_form())
            self.assertEqual(config['ordinary_field_contract'], r.CONTRACT)
            r.require_config(config)                                                    # control: unchanged deployment
        for run in (dict(ON55, AI_MODEL=g.SONNET_5), dict(ON55, AI_MODEL='claude-sonnet-4-6'),
                    dict(ON55, AI_MODEL=g.SONNET_5, V3_FIELD_RELATIONS_SWITCH=False),
                    dict(ON55, V3_FIELD_RELATIONS_SWITCH=False)):
            with self.subTest(model=run['AI_MODEL'], switch=run['V3_FIELD_RELATIONS_SWITCH']), override_settings(**run):
                self.assertIs(r.enabled(g.SONNET_5_5), r.enabled())
                with self.assertRaisesMessage(ValidationError, 'disabled'):
                    r.require_config(config)

    def test_the_explicit_switch_keeps_a_queued_job_across_a_model_change(self):
        # the base's behaviour: '1' is on for every native model whatever the configured model is now
        with override_settings(**dict(ON55, V3_FIELD_RELATIONS=True, V3_FIELD_RELATIONS_SWITCH=True)):
            config = g.configuration(clinic_form())
        with override_settings(**dict(ON55, AI_MODEL='claude-sonnet-4-6', V3_FIELD_RELATIONS=True,
                                      V3_FIELD_RELATIONS_SWITCH=True)):
            r.require_config(config)
            self.assertTrue(r.enabled(g.SONNET_5_5))

    def test_a_record_is_read_only_while_its_model_takes_the_contract(self):
        from core.tests.test_v3_field_relations import relation_body
        notes, fields = OPENER + ' She takes warfarin.', clinic_form()

        def stored(model):
            asked, context, _ = g.v3_generation_fields(fields)
            units = g.source_units(notes, asked, context_labels=context)[0]
            selections = r.FieldSelections.model_validate(relation_body(notes, fields, {'v3_4': ['She takes warfarin.']}))
            records = r.records(notes, fields, context, units, selections, model)
            answers = g.v3_adopted(fields, g.validate_selections(
                notes, asked, selections, context_labels=context, evidence_contract=g.TAB_CONTRACT,
                ordinary_records=records, catalogue=fields), notes, asked, context)
            self.assertEqual(answers['v3_4']['status'], 'supported')
            return {'v3_4': answers['v3_4']}

        with override_settings(**ON55):
            mine = stored(g.SONNET_5_5)
            self.assertEqual(g.governed_decisions(notes, fields, mine), [])               # control
        with override_settings(**RELATIONS):
            explicit = stored(g.SONNET_5)
        for run, answer in ((ON55, explicit), (dict(ON55, AI_MODEL=g.SONNET_5), mine),
                            (dict(ON55, AI_MODEL='claude-sonnet-4-6'), mine), (dict(ON55, V3_FIELD_RELATIONS_SWITCH=False), mine)):
            with self.subTest(model=run['AI_MODEL'], record=answer is mine), override_settings(**run):
                # a claude-sonnet-5 record under a default that is claude-sonnet-5-5's, or any record once the deployment
                # is off the contract: refused by the reader, so the page, save and finalization hold it
                self.assertEqual(g.governed_decisions(notes, fields, answer), ['Medications'])


def _keyed_reply(body, picks):
    """A complete relations answer (contract v4's wire: answers naming their keys, each context the partition of the
    units by relation) to the request itself (the picked unit 'answer', every other 'independent'), from the model the request
    named, end_turn."""
    payload = json.loads(body['messages'][0]['content'])
    units = payload['source_units']
    by_quote = {u['quote']: u['id'] for u in units}
    labels = {f['key']: f['label'] for f in payload['catalogue']}
    requested = payload['requested_field_ids']
    with_options = any(payload['option_catalogue'].get(key) for key in requested)
    fields = []
    for key in requested:
        chosen = [by_quote[picks[labels[key]]]] if picks.get(labels[key]) in by_quote else []
        entry = {'key': key, 'unit_ids': chosen, 'conflict': False}
        if with_options:
            entry['option_ids'] = []
        entry['context'] = {'answer': [u['id'] for u in units if u['id'] in chosen], 'qualifier': [], 'contrary': [],
                            'unresolved': [], 'independent': [u['id'] for u in units if u['id'] not in chosen]}
        fields.append(entry)
    return {'id': 'msg_switch', 'type': 'message', 'role': 'assistant', 'model': body['model'],
            'content': [{'type': 'text', 'text': json.dumps({'fields': fields})}], 'stop_reason': 'end_turn',
            'stop_details': None, 'stop_sequence': None,
            'usage': {'input_tokens': 100, 'output_tokens': 10, 'cache_read_input_tokens': 0,
                      'cache_creation_input_tokens': 0}}


from core.tests.test_word_v3_workflow import V3EncounterFixture  # noqa: E402
from django.test import TestCase  # noqa: E402


@override_settings(**ON55)
class OneSwitchAtTheWorker(V3EncounterFixture, TestCase):
    """NR1-F1 end to end: a job quoted under the claude-sonnet-5-5 default and run after the deployment moved off it is
    refused BEFORE any request - nothing sent, nothing charged, the hold released - exactly as the base refused a job
    whose flag was turned off after its quote. With no change it is sent once and both answers are adopted."""
    NOTES = 'Patient presents with right knee pain.\nReferring physician: Dr Example'
    PICKS = {'Reason for visit': 'Patient presents with right knee pain.',
             'Referring physician': 'Referring physician: Dr Example'}

    def run_job(self, run_settings):
        import os
        import anthropic
        import httpx
        from core.jobs import enqueue, run_one
        from core.models import Encounter, Job, LedgerEntry, Reservation
        from core.tests.test_sonnet5_profile import PRICE_ENV
        env = patch.dict(os.environ, PRICE_ENV); env.start(); self.addCleanup(env.stop)
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        self.assertEqual(self.client.post(f"/encounters/{encounter.pk}/notes/",
                                          {"revision": encounter.revision, "notes": self.NOTES}).status_code, 302)
        with patch('anthropic.Anthropic') as never:
            job = enqueue(Encounter.objects.get(pk=self.encounter.pk), self.user)
            never.assert_not_called()
        self.assertEqual(job.config['ordinary_field_contract'], r.CONTRACT)
        sent, real = [], anthropic.Anthropic

        def handler(request):
            body = json.loads(request.content); sent.append(body)
            return httpx.Response(200, json=_keyed_reply(body, self.PICKS))

        def client(**kwargs):
            return real(api_key='synthetic-no-network', http_client=httpx.Client(transport=httpx.MockTransport(handler)),
                        **kwargs)
        with override_settings(**run_settings), patch('anthropic.Anthropic', side_effect=client):
            run_one()
        job = Job.objects.get(pk=job.pk)
        encounter = Encounter.objects.get(pk=self.encounter.pk)
        answers = {label: (encounter.answers.get(self.key(label)) or {}).get('status') for label in self.PICKS}
        return job, sent, answers, [r.state for r in Reservation.objects.filter(job=job)], \
            list(LedgerEntry.objects.filter(job=job).values_list('kind', flat=True))

    def test_unchanged_deployment_sends_once_and_adopts(self):
        job, sent, answers, reservations, ledger = self.run_job(ON55)
        self.assertEqual((job.state, len(sent), [b['model'] for b in sent]), ('succeeded', 1, [g.SONNET_5_5]))
        self.assertEqual(answers, {'Reason for visit': 'supported', 'Referring physician': 'supported'})

    def assert_refused_before_any_request(self, run):
        job, sent, answers, reservations, ledger = self.run_job(run)
        self.assertEqual((job.state, sent, reservations, ledger), ('failed', [], ['released'], []), job.error)
        self.assertIn('No provider request was made', job.error)

    def test_moved_to_claude_sonnet_5_refuses_before_any_request(self):
        self.assert_refused_before_any_request(dict(ON55, AI_MODEL=g.SONNET_5))

    def test_moved_to_claude_sonnet_4_6_refuses_before_any_request(self):
        self.assert_refused_before_any_request(dict(ON55, AI_MODEL='claude-sonnet-4-6'))
