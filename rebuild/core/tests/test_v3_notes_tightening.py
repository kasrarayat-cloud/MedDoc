"""Round 3 of the notes-usefulness change (2026-09-29): TIGHTENING ONLY.

A test named for a CONFIRMED round-2 finding (phase-b/notes-round2-confirmed.json) uses the refuter's own synthetic
input; those inputs were supported on f2b55f6e in the verifier's own run (agents-b/notes/reverify/out/*-head.json; most on
debaefd9 too) and are held now. A test without a finding id pins one guard of this round in isolation (its in-memory
mutant survives the rest of the suite otherwise). The releases the round-2 refuters broke are withdrawn
(test_v3_notes_usefulness.py, test_v3_notes_repair.py); what is added here only HOLDS (`generation.v3_added_causes`,
`v3_actors`). Forms are the frozen synthetic diagnostic forms (cases.json), read-only. The last class pins what must stay
supported: debaefd9's seven supported answers on the retained responses.
"""
import copy
import json

from django.test import SimpleTestCase

from core import generation as g
from core import v3_actors
from .test_v3_notes_repair import adopt, fields_of

#: Every way one gap between two units may be written: a blank line in four spellings, a line break, U+2028.
GAPS = ('\n\n', '\r\n\r\n', '\n \n', '\n\t\n', '\r\n', ' ', '\n')


class Tightening(SimpleTestCase):
    def assertHeld(self, notes, picks, form='r1-11'):
        """Held at generation, and the same candidate stored as `supported` is refused by finalization."""
        fields = fields_of(form)
        out = adopt(notes, picks, fields)
        for label, answer in out.items():
            with self.subTest(notes=notes, label=label):
                self.assertNotEqual(answer['status'], 'supported', (notes, label, answer.get('text')))
                candidate = answer.get('held_candidate') or {}
                if candidate.get('evidence'):
                    key = next(f['key'] for f in fields if f['label'] == label)
                    stored = {'text': candidate['text'], 'status': 'supported', 'reviewed': True,
                              'evidence': candidate['evidence']}
                    self.assertIn(label, g.governed_decisions(notes, fields, {key: stored}), notes)
        return out

    def assertSupported(self, notes, picks, form='r1-11'):
        fields = fields_of(form)
        out = adopt(notes, picks, fields)
        for label, answer in out.items():
            with self.subTest(notes=notes, label=label):
                self.assertEqual(answer['status'], 'supported', (notes, label, answer.get('held_candidate')))
                key = next(f['key'] for f in fields if f['label'] == label)
                self.assertEqual(g.governed_decisions(notes, fields, {key: {**answer, 'reviewed': True}}), [], notes)
        return out

    def assertHeldInEveryGap(self, first, second, picks, form='r1-11'):
        for gap in GAPS:
            self.assertHeld(first + gap + second, picks, form)


class OneRunForTheNote(Tightening):
    """RR5, X1, RR4-8: the actor run and the positional rules do not stop at a blank line."""

    def test_RR5_the_adverse_rows_across_a_blank_line(self):
        for first, second, picks in (
                ('His father had a heart attack at 55.', 'He takes rosuvastatin.', {'Medications': ['He takes rosuvastatin.']}),
                ('Her sister was seen in oncology last month.', 'Assessment is breast cancer.',
                 {'Assessment': ['Assessment is breast cancer.']}),
                ('His father had a heart attack at 55. He smoked heavily.', 'Smoker: Yes.', {'Smoker': ['Smoker: Yes.']}),
                ('His father had a heart attack at 55.', 'He is allergic to penicillin.\nAllergies: penicillin.',
                 {'Allergies': ['Allergies: penicillin.']}),
                ('The patient presents with chest pain.', 'The pain resolved yesterday.',
                 {'Chief complaint': ['The patient presents with chest pain.']}),
                ('The patient had an admission in 2019.', 'She presented with chest pain.',
                 {'Chief complaint': ['She presented with chest pain.']}),
                ('The patient was seen in A&E yesterday.', 'Examination is normal.',
                 {'Examination': ['Examination is normal.']}),
                ('Her sister has breast cancer.', 'She takes tamoxifen 20 mg daily.', {'Medications': ['She takes tamoxifen']}),
                ('Her husband takes warfarin.', 'He is allergic to penicillin.', {'Allergies': ['He is allergic']}),
                ('Her father has diabetes.', 'Metformin is taken twice daily.', {'Medications': ['Metformin is taken']}),
                ('Smoker: No.', 'He quit smoking last month.', {'Smoker': ['Smoker: No.']}),
                ('Examination is normal.', 'However, this was before the fall.', {'Examination': ['Examination is normal.']}),
                # A self-standing later line that repeats the answer's core word, leading its paragraph or not (B7, B11).
                ('The patient is on methadone.', 'The patient is not on diazepam or methadone.',
                 {'Medications': ['The patient is on methadone.']}),
                ('The patient presents with chest pain.', 'His father had angina. The pain resolved yesterday.',
                 {'Chief complaint': ['The patient presents with chest pain.']})):
            self.assertHeldInEveryGap(first, second, picks)
        # A self-standing later paragraph that shares no core word still ends the paragraph, as on debaefd9.
        self.assertSupported('The patient is on methadone.\n\nThe patient sleeps well.',
                             {'Medications': ['The patient is on methadone.']})

    def test_X1_a_pronoun_whose_only_antecedent_is_another_person_one_blank_line_away(self):
        self.assertHeld('Her husband was diagnosed with atrial fibrillation last year.\n\nHe takes warfarin 5 mg daily.',
                        {'Medications': ['He takes warfarin 5 mg daily.']})
        self.assertHeld('Mother: breast cancer at 50.\n\nShe had a mastectomy.',
                        {'Past medical history': ['She had a mastectomy.']})
        self.assertHeld('A 30-year-old woman presents with a rash.\n\nHer sister is allergic to penicillin.\n\nShe is also '
                        'allergic to latex.', {'Allergies': ['She is also allergic to latex.']})
        reading = g.governance_for('Her husband has atrial fibrillation.\n\nHe takes warfarin.',
                                   fields_of('r1-11'))[11]['preceding']
        self.assertEqual(reading['resolved'][reading['units'][1]['id']]['actor'], 'other')

    def test_RR4_8_a_pronoun_after_another_persons_paragraph(self):
        self.assertHeld('The patient presents with cough.\n\nHer husband has hypertension.\n\nHe takes lisinopril.',
                        {'Medications': ['He takes lisinopril.']})

    def test_an_unresolved_pronoun_with_another_person_earlier_in_the_note(self):
        reading = g.governance_for('Her mother has migraines.\n\nAllergies: none.\n\nShe takes sumatriptan.',
                                   fields_of('r1-11'))[11]['preceding']
        self.assertEqual(reading['resolved'][reading['units'][-1]['id']]['actor'], 'other')
        self.assertHeld('Her mother has migraines.\n\nAllergies: none.\n\nShe takes sumatriptan.',
                        {'Medications': ['She takes sumatriptan.']})


class WordHolds(Tightening):
    """RR4-4 and the kept hold, note-wide; X4. A shared word may add a hold, never release one."""

    def test_RR4_4_a_labelled_value_after_a_statement_sharing_its_word(self):
        for gap in GAPS:
            self.assertHeld('The patient is suicidal.' + gap + 'Suicidal ideation: none.',
                            {'Suicidal ideation': ['Suicidal ideation: none.']}, form='n13-risk-and-medication')
            self.assertHeld('The patient is allergic to penicillin.' + gap + 'Allergies: none.',
                            {'Allergies': ['Allergies: none.']}, form='n16-mood-and-allergies')
        # the kept direction, across a blank line too
        self.assertHeld('The patient is allergic to penicillin.\n\nAllergies: none.',
                        {'Allergies': ['The patient is allergic to penicillin.']}, form='n16-mood-and-allergies')
        # A labelled line OF the same question holds an unlabelled answer even when they share no word (the kept hold,
        # note-wide): the statement says aspirin, the question's own line says none.
        for gap in ('\n', '\n\n'):
            self.assertHeld('The patient takes aspirin.' + gap + 'Medications: none.',
                            {'Medications': ['The patient takes aspirin.']})
        # A labelled line naming the question holds, across a blank line too; a statement about the patient repeating
        # a labelled answer's word holds it (RR4-4), in either order.
        self.assertHeld('The patient takes warfarin.\n\nPlan: stop current medications.',
                        {'Medications': ['The patient takes warfarin.']})
        self.assertHeld('Allergies: none.\nThe patient is allergic to penicillin.', {'Allergies': ['Allergies: none.']},
                        form='n16-mood-and-allergies')

    def test_X4_a_labelled_block_sharing_a_word_is_not_a_barrier(self):
        self.assertHeld('The patient has a swollen right knee.\nExamination: the swelling is in the left knee, not the right.',
                        {'History of present illness': ['The patient has a swollen right knee.']})
        self.assertHeld('Plan: start warfarin. Assessment: warfarin is contraindicated.', {'Plan': ['Plan: start warfarin.']})

    def test_PRE_2_a_side_or_identity_value_is_not_plain(self):
        self.assertHeld('Right knee: painful.\nLeft knee: wrong side.', {'Right knee': ['Right knee: painful.']},
                        form='n09-knee-pair')
        self.assertHeld('Right knee: effusion.\nClinical findings: opposite side.', {'Right knee': ['Right knee: effusion.']},
                        form='n08-knee-and-findings')
        self.assertHeld('Smoker: Yes.\nAllergies: wrong patient.', {'Smoker': ['Smoker: Yes.']},
                        form='n10-smoker-allergies')


class PersonReadings(Tightening):
    """RR6, RR7, RR8, RR9, X2, X3: who the line is about."""

    def test_RR6_gender_from_a_title_a_copular_noun_or_an_object_pronoun(self):
        for notes, picks in (
                ('Mrs Jones presents with a rash.\n\nThe patient says he is allergic to penicillin.',
                 {'Allergies': ['The patient says he is allergic to penicillin.']}),
                ('The patient is a woman.\n\nThe patient says he is allergic to penicillin.',
                 {'Allergies': ['The patient says he is allergic to penicillin.']}),
                ('45-year-old man presents with cough.\n\nThe patient says warfarin was prescribed for her.',
                 {'Medications': ['The patient says warfarin was prescribed for her.']}),
                ('Mrs Jones presents with chest pain.\n\nHe takes warfarin.', {'Medications': ['He takes warfarin.']}),
                ('The patient is female.\n\nHe is allergic to penicillin.', {'Allergies': ['He is allergic to penicillin.']})):
            self.assertHeld(notes, picks)

    def test_X2_the_gender_given_later_in_the_note(self):
        for notes, picks in (
                ('The patient says he is allergic to penicillin.\n\n45-year-old woman presents with a rash.',
                 {'Allergies': ['The patient says he is allergic to penicillin.']}),
                ('The patient reports that he takes warfarin.\n\nIn summary, this is a 60-year-old woman with palpitations.',
                 {'Medications': ['The patient reports that he takes warfarin.']}),
                ('She takes warfarin.\n\n45-year-old man presents with cough.', {'Medications': ['She takes warfarin.']})):
            self.assertHeld(notes, picks)

    def test_RR7_kinship_words(self):
        for person in ('stepdad', 'stepmum', 'grandad', 'granddad', 'godson', 'nan', 'hubby', 'fiancé', 'fiance',
                       'mum', 'dad', 'son', 'stepnan', 'greatgrandson'):
            self.assertHeld('Her %s takes warfarin.' % person, {'Medications': ['takes warfarin.']})
        # Not kinship: a word ending with a family word's letters.
        reading = g.governance_for('The maximum dose is 4 g.', fields_of('r1-11'))[11]['preceding']
        self.assertFalse(reading['actors'][reading['units'][0]['id']]['other'])

    def test_each_gender_cue_alone(self):
        """Where no other hold applies (the pronoun line comes first, so no run or paragraph stands before it), only the
        note's gender - read from a cue written LATER - holds it: a title, a copular adjective, an object pronoun."""
        for notes, picks in (
                ('He takes warfarin.\n\nMrs Jones presents with chest pain.', {'Medications': ['He takes warfarin.']}),
                ('He takes warfarin.\n\nThe patient is female.', {'Medications': ['He takes warfarin.']}),
                ('Warfarin was prescribed for her.\n\n45-year-old man presents with cough.',
                 {'Medications': ['Warfarin was prescribed for her.']})):
            self.assertHeld(notes, picks)
        self.assertSupported('He takes warfarin.\n\n45-year-old man presents with cough.',
                             {'Medications': ['He takes warfarin.']})

    def test_an_encounter_topic_after_a_line_naming_someone_else(self):
        # The nearest person before it is not the patient: a clinician named in a sentence about the scan, or another
        # person named in the patient's own sentence, across a blank line.
        self.assertHeld('The GP reviewed the scan.\n\nExamination is normal.', {'Examination': ['Examination is normal.']})
        self.assertHeld('The patient lives with her husband.\n\nWarfarin is taken daily.',
                        {'Medications': ['Warfarin is taken daily.']})
        self.assertSupported('The patient lives alone.\n\nWarfarin is taken daily.',
                             {'Medications': ['Warfarin is taken daily.']})

    def test_RR8_a_clinician_bearing_a_medication_allergy_or_history(self):
        for notes, label in (('Dr Smith takes warfarin.', 'Medications'), ('The nurse is allergic to latex.', 'Allergies'),
                             ('Her GP is allergic to penicillin.', 'Allergies'),
                             ('The GP is on warfarin 5 mg daily.', 'Medications'),
                             ('The consultant has asthma.', 'Past medical history'),
                             ('The patient presents with bruising.\n\nThe district nurse takes warfarin.', 'Medications')):
            self.assertHeld(notes, {label: [notes.split('\n')[-1]]})
        # A clinician acting on the patient is not one.
        reading = g.governance_for('Dr Smith reviewed the scan.', fields_of('r1-11'))[11]['preceding']
        self.assertFalse(reading['actors'][reading['units'][0]['id']]['other'])

    def test_RR9_an_appositive_or_relative_clause_naming_a_relative(self):
        for notes in ("A 70-year-old woman, the patient's mother, presents with chest pain.",
                      "A 45-year-old man, the patient's husband, presents with cough.",
                      'This is a 60-year-old woman, mother of the patient, here for follow up of her diabetes.',
                      'A 12-year-old boy presents with his mother, who has chest pain.',
                      '12-year-old boy presents with his mother, who has chest pain.'):
            self.assertHeld(notes, {'Chief complaint': [notes]})

    def test_X3_another_patient(self):
        for notes in ('Another patient takes warfarin.', 'The other patient takes warfarin.',
                      'The patient shares a bay with another patient.\n\nAnother patient takes warfarin.'):
            self.assertHeld(notes, {'Medications': [notes.split('\n')[-1]]})


class ClausesAndRetractions(Tightening):
    """PRE-1, PRE-3, RR2 (and its older modality gap), RR4-2."""

    def test_PRE_3_and_RR2_a_bounding_or_conditional_clause(self):
        for notes, label, form in (
                ('The patient had attended the clinic every week until the order expired.', 'Clinic attendance',
                 'n03-order-question'),
                ('The patient has attended the clinic every week until the order has lapsed.', 'Clinic attendance',
                 'n03-order-question'),
                ('The patient attends the clinic unless the order lapses.', 'Clinic attendance', 'n03-order-question'),
                ('The patient will start warfarin when the bleeding stops.', 'Medications', 'r1-11'),
                ('The patient takes insulin when the sugar exceeds twenty.', 'Medications', 'r1-11')):
            out = self.assertHeld(notes, {label: [notes]}, form=form)
            self.assertEqual(out[label]['held_candidate']['reason'], g.V3_HELD_REASON)

    def test_PRE_1_a_forward_retraction_of_the_rest(self):
        for line in ('Strike the rest.', 'Delete the rest of this dictation.'):
            self.assertHeld('Allergies: none.\n' + line + '\nSmoker: Yes.', {'Smoker': ['Smoker: Yes.']})
        self.assertFalse(g.v3_note_correction('Advised bed rest for the rest of the week.'))

    def test_RR4_2_a_past_frame_before_an_encounter_finding(self):
        for first in ('The patient was seen in the emergency department.', 'The patient was reviewed at her last visit in May.',
                      'The patient was examined at her last visit.', 'The patient was examined at another hospital.',
                      'The patient was examined in 2019.'):
            self.assertHeld(first + ' Examination was normal.', {'Examination': ['Examination was normal.']})
        # control, unchanged from debaefd9: this visit's presentation, then its examination
        self.assertSupported('The patient presents with knee pain. Examination was normal.',
                             {'Examination': ['Examination was normal.']})


class FailClosed(Tightening):
    """RR4-1, RR4-3, C3: above the actor reader's unit cap every unit is held, with a reason that says it was not read."""

    def long_note(self, first, fillers):
        return first + ''.join('\n\nLine %d is recorded.' % n for n in range(1, fillers + 1))

    def test_RR4_1_above_the_unit_cap_the_reader_fails_closed(self):
        fields = fields_of('r1-11')
        for first, label, quote in (
                ('Her stepbrother takes warfarin.', 'Medications', 'Her stepbrother takes warfarin.'),
                ('45-year-old woman presents with a rash.\n\nHe takes warfarin.', 'Medications', 'He takes warfarin.'),
                ('The patient takes aspirin.', 'Medications', 'The patient takes aspirin.')):
            notes = self.long_note(first, v3_actors.MAX_UNITS + 5)
            reading = g.governance_for(notes, fields)[11]['preceding']
            self.assertGreater(len(reading['units']), v3_actors.MAX_UNITS)
            unit = next(u for u in reading['units'] if u['quote'] == quote)
            self.assertFalse(reading['actors'][unit['id']]['readable'])
            evidence = [{k: unit[k] for k in ('quote', 'start', 'end')}]
            warnings = g.v3_preceding_warnings(reading, label, evidence)
            self.assertIn(unit['id'], {w['id'] for w in warnings if w.get('unread')}, first)
            out = adopt(notes, {label: [quote]}, fields)[label]
            self.assertNotEqual(out['status'], 'supported', first)
            key = next(f['key'] for f in fields if f['label'] == label)
            stored = {'text': quote, 'status': 'supported', 'reviewed': True, 'evidence': evidence}
            self.assertIn(label, g.governed_decisions(notes, fields, {key: stored}))

    def test_one_overlong_line_in_a_readable_note_holds_only_when_it_may_name_a_person(self):
        fields = fields_of('r1-11')
        long_value = ', '.join(['daily aching discomfort'] * 60) + '.'
        for value, held in (('The patient reports ' + long_value, False), ('Her husband reports ' + long_value, True),
                            ('She reports ' + long_value, True)):
            notes = 'History of present illness: ' + value
            reading = g.governance_for(notes, fields)[11]['preceding']
            unit = reading['units'][0]
            self.assertFalse(reading['actors'][unit['id']]['readable'])      # longer than the parser reads
            out = adopt(notes, {'History of present illness': [notes]}, fields)['History of present illness']
            self.assertEqual(out['status'] != 'supported', held, value[:30])

    def test_after_an_overlong_line_naming_a_person_the_run_is_not_the_patients(self):
        long_value = ', '.join(['daily aching discomfort'] * 60) + '.'
        self.assertHeld('History of present illness: Her husband reports ' + long_value + '\nAllergies: none.',
                        {'Allergies': ['Allergies: none.']})

    def test_an_unread_line_is_not_said_to_be_another_persons(self):
        notes = 'The patient is a lorry driver.' + ''.join('\n\nBlood pressure reading %d was recorded.' % n
                                                           for n in range(1, v3_actors.MAX_UNITS + 1))
        reading = g.governance_for(notes, fields_of('r1-11'))[11]['preceding']
        unit = reading['units'][0]
        warnings = g.v3_preceding_warnings(reading, 'History of present illness',
                                           [{k: unit[k] for k in ('quote', 'start', 'end')}])
        own = next(w for w in warnings if w['id'] == unit['id'])
        self.assertTrue(own.get('unread'))
        self.assertFalse(own.get('other_person'))
        self.assertEqual(g.held_reason([{'unread': True}], False), g.V3_UNREAD_REASON)


class LinearContext(SimpleTestCase):
    """C1: a held answer shows at most a few lines per selected unit, never every denying block."""

    def test_C1_the_shown_context_is_linear_in_the_selected_units(self):
        from .test_v3_ordinary_notes import field
        fields = [field('v3_%d' % n, 'Question %d' % n, 'long_text') for n in range(1, 31)]
        notes = '\n'.join('Question %d: mild swelling was noted over the region %d.' % (n, n) for n in range(1, 31))
        governance = g.governance_for(notes, fields)
        reading = governance[11]['preceding']
        total = 0
        for unit, field in zip(reading['units'], fields):
            evidence = [{k: unit[k] for k in ('quote', 'start', 'end')}]
            total += len(g.judged_context(governance, notes, governance[10], field['label'], evidence) or [])
        self.assertLessEqual(total, 8 * len(fields))


class StillSupported(Tightening):
    """debaefd9's seven supported answers on the 14 retained responses stay supported (N04 x5, N08, N10)."""

    N04 = ('45-year-old man presents with right knee pain for three weeks after a fall. He has hypertension and takes '
           'lisinopril 10 mg daily. Allergies: penicillin. Smoker: No. On examination there is a small effusion and '
           'medial joint line tenderness. Assessment is a probable medial meniscus tear. Plan is an MRI of the right knee '
           'and physiotherapy referral.')

    def test_debaefd9s_reviewed_reference_exemptions_stay(self):
        # 'Plan: continue current medications.' is debaefd9's reviewed unchanged reference to its one referent; no word
        # hold of this round overrides it (retained note 9 keeps its seven answers), while 'stop' is coupled as before.
        note = ('Patient presents for medication review.\nCurrent medications are atorvastatin 20 mg and metformin 1000 '
                'mg.\nAllergies: codeine.\nExamination was not performed today.\nPlan: continue current medications.')
        self.assertSupported(note, {'Medications': ['Current medications are'], 'Plan': ['Plan: continue']})
        self.assertHeld(note.replace('continue', 'stop'), {'Medications': ['Current medications are']})

    def test_the_seven(self):
        self.assertSupported(self.N04, {'Allergies': ['Allergies: penicillin.'], 'Smoker': ['Smoker: No.'],
                                        'Examination': ['On examination'], 'Assessment': ['Assessment is a probable'],
                                        'Plan': ['Plan is an MRI']})
        self.assertSupported('The patient has left knee pain.', {'Clinical findings': ['The patient has left knee pain.']},
                             form='n08-knee-and-findings')
        self.assertSupported('The patient does not smoke. Allergies: none known.', {'Allergies': ['Allergies: none known.']},
                             form='n10-smoker-allergies')
