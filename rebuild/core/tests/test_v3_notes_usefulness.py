"""Ordinary notes made useful without weakening the context that governs evidence (2026-09-29, repaired the same day).

Synthetic notes only; the provider's choice is simulated by unit selections (the `run()` shape). Each group pins one
change to the ONE neighbour rule (`generation.v3_neighbour_causes`) or its readers, with the adverse shapes that must
stay held beside the supported ones. The recorded campaign shapes are named N01..N12; the controls A..H, P, S keep
the names of the over-hold analysis (phase-a/overholds.txt).

⚠️ REPAIRED after the refutation round (test_v3_notes_repair.py pins every confirmed finding): the link reading of a
later unit, the actor release of the unit before, the actor-ledger subsets (G-B1) and the encounter release after a run
(G-J) are withdrawn; the positional rules hold again. What stays: G-A, G-D, G-E, G-F, G-H (each narrowed where it was
refuted), the hold-only actor reading ((b''), X1) and X3.
"""
import copy

from django.test import SimpleTestCase

from core import generation as g
from .test_v3_ordinary_notes import field

TITLE = 'Clinic visit record'


def form(**contexts):
    """The r1-11 shape: every clinical field under the form's title; `contexts` overrides one field's path."""
    spec = (('v3_1', 'Chief complaint', 'text'), ('v3_2', 'History of present illness', 'long_text'),
            ('v3_3', 'Past medical history', 'long_text'), ('v3_4', 'Medications', 'long_text'),
            ('v3_5', 'Allergies', 'text'), ('v3_7', 'Examination', 'long_text'),
            ('v3_8', 'Assessment', 'long_text'), ('v3_9', 'Plan', 'long_text'))
    fields = []
    for key, label, kind in spec:
        f = field(key, label, kind)
        f['context'] = contexts.get(label, TITLE)
        fields.append(f)
    smoker = field('v3_6', 'Smoker', 'choice', ['Yes', 'No'])
    smoker['context'] = contexts.get('Smoker', TITLE + ' > Smoker')
    fields.insert(5, smoker)
    consent = field('v3_10', 'Consent obtained', 'checkbox', ['Consent obtained'])
    consent['context'] = 'Sign-off'
    return fields + [consent]


def adopt(notes, picks, fields):
    """`picks`: {field key: [quotes]}. Validate and adopt as the application does; also return the review reading."""
    asked, context, v3_fields = g.v3_generation_fields(fields)
    units = g.source_units(notes, asked, context_labels=context)[0]
    by_quote = {u['quote']: u['id'] for u in units}
    selections = g.UnitSelections(fields=[g.UnitSelection(key=f['key'], unit_ids=[by_quote[q] for q in picks.get(f['key'], [])],
                                                          conflict=False) for f in asked])
    answers = g.validate_selections(notes, asked, selections, context_labels=context, evidence_contract=g.TAB_CONTRACT)
    return g.v3_adopted(v3_fields, answers, notes, asked, context)


def key_of(fields, label):
    return next(f['key'] for f in fields if f['label'] == label)


N01 = ('This is a 30-year-old female seen for headaches. The headaches started two months ago and are worse in the '
       'morning. She denies visual changes, nausea, or weakness. She takes ibuprofen as needed. No known drug '
       'allergies. She is a nonsmoker. Neurological examination is normal. Assessment is tension-type headache. Plan '
       'is to start amitriptyline 10 mg at night. She will follow up in six weeks.')
N05 = ('Patient presents with chest tightness on exertion for one month. His father had a heart attack at 55. He has '
       'high cholesterol. He takes rosuvastatin. Allergies: none known. Smoker: Yes. Examination is normal. '
       'Assessment is possible stable angina. Plan is an exercise stress test and aspirin 81 mg daily.')
N04 = ('45-year-old man presents with right knee pain for three weeks after a fall. He has hypertension and takes '
       'lisinopril 10 mg daily. Allergies: penicillin. Smoker: No. On examination there is a small effusion and medial '
       'joint line tenderness. Assessment is a probable medial meniscus tear. Plan is an MRI of the right knee and '
       'physiotherapy referral.')


class NotesUsefulness(SimpleTestCase):
    def status(self, notes, label, quotes, fields=None, extra=None):
        fields = fields or form()
        picks = {key_of(fields, label): quotes, **(extra or {})}
        out = adopt(notes, picks, fields)[key_of(fields, label)]
        return out

    def assertHeld(self, notes, label, quotes, fields=None, extra=None):
        out = self.status(notes, label, quotes, fields, extra)
        self.assertNotEqual(out['status'], 'supported', (notes, label, out.get('text')))
        self.assertEqual(out['text'], '', notes)
        return out

    def assertSupported(self, notes, label, quotes, text=None, fields=None, extra=None):
        fields = fields or form()
        out = self.status(notes, label, quotes, fields, extra)
        self.assertEqual(out['status'], 'supported', (notes, label, out.get('held_candidate')))
        if text is not None:
            self.assertEqual(out['text'], text)
        # The page, save and finalization reader agrees: nothing it would refuse is offered here.
        key = key_of(fields, label)
        self.assertEqual(g.governed_decisions(notes, fields, {key: {**out, 'reviewed': True}}), [], notes)
        return out

    # ── step 1 (b''): another person as the unit's own subject or possessor ──────────────────────────────────────
    def test_another_person_as_subject_or_possessor_holds_the_unit_itself(self):
        for notes, label in (('Her husband takes warfarin.', 'Medications'),                        # S1
                             ("The patient's neighbour takes warfarin.", 'Medications'),            # S2
                             ('His father has hypertension.', 'Past medical history'),              # S3
                             ("Her daughter's examination is normal.", 'Examination'),              # S4
                             ("The patient takes her husband's warfarin.", 'Medications'),
                             ('Warfarin was prescribed for her husband.', 'Medications'),
                             ('The patient and her father have diabetes.', 'Past medical history'),
                             ('The patient reports her husband takes warfarin.', 'Medications'),
                             ('Somebody at home takes warfarin.', 'Medications'),                   # R1-7
                             ('Her stepbrother takes warfarin.', 'Medications')):                   # R1-8
            with self.subTest(notes=notes):
                held = self.assertHeld(notes, label, [notes])
                self.assertEqual(held['held_candidate']['reason'], g.V3_OTHER_PERSON_REASON)
                # Finalization refuses the same statement stored as supported (one reader).
                fields = form()
                key = key_of(fields, label)
                stored = {'text': notes, 'status': 'supported', 'reviewed': True,
                          'evidence': [{'quote': notes, 'start': 0, 'end': len(notes)}]}
                self.assertEqual(g.governed_decisions(notes, fields, {key: stored}), [label])
        # In its own paragraph the patient's sentence is its own; in the same paragraph the positional rule holds it.
        self.assertSupported("The patient's neighbour takes warfarin.\n\nThe patient takes aspirin.", 'Medications',
                             ['The patient takes aspirin.'], 'The patient takes aspirin.')
        self.assertHeld("The patient's neighbour takes warfarin. The patient takes aspirin.", 'Medications',
                        ['The patient takes aspirin.'])

    def test_labelled_person_attribute_after_an_other_person_run_is_held(self):
        for notes, label, quote in (
                ('His father had a heart attack at 55. He is allergic to penicillin. Allergies: penicillin.',   # P1
                 'Allergies', 'Allergies: penicillin.'),
                ('His father had a heart attack at 55. He is allergic to penicillin.\nAllergies: penicillin.',  # P2
                 'Allergies', 'Allergies: penicillin.'),
                ('His father had a heart attack at 55. He smoked heavily.\nSmoker: Yes.', 'Smoker', 'Smoker: Yes.'),  # P3
                ('His father had a heart attack at 55. He has asthma. Allergies: none known.',                 # P4
                 'Allergies', 'Allergies: none known.'),
                ('His father had a heart attack at 55. He smoked heavily. Smoker: Yes.', 'Smoker', 'Smoker: Yes.'),  # C5
                ('The patient lives with her husband. He is allergic to penicillin. Allergies: penicillin.',
                 'Allergies', 'Allergies: penicillin.'),
                # R3-2: a labelled value naming another person opens that person's run.
                ('The patient presents with cough.\nAllergies: her sister is allergic to penicillin.\nSmoker: Yes.',
                 'Smoker', 'Smoker: Yes.')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, label, [quote])
        # With the patient re-established first, the labelled line names its question as before.
        self.assertSupported('His father had a heart attack at 55. The patient takes aspirin. Allergies: penicillin.',
                             'Allergies', ['Allergies: penicillin.'], 'penicillin.')

    # ── G-J, revised: an encounter topic after another person's run is not the encounter's ─────────────────────────
    def test_encounter_topics_after_another_persons_run_are_held(self):
        fields = form()
        out = adopt(N05, {'v3_1': ['Patient presents with chest tightness on exertion for one month.'],
                          'v3_5': ['Allergies: none known.'], 'v3_6': ['Smoker: Yes.'],
                          'v3_7': ['Examination is normal.'], 'v3_8': ['Assessment is possible stable angina.'],
                          'v3_9': ['Plan is an exercise stress test and aspirin 81 mg daily.'],
                          'v3_4': ['He takes rosuvastatin.'],
                          'v3_3': ['His father had a heart attack at 55.', 'He has high cholesterol.']}, fields)
        for key in ('v3_1', 'v3_3', 'v3_4', 'v3_5', 'v3_6', 'v3_7', 'v3_8', 'v3_9'):
            self.assertNotEqual(out[key]['status'], 'supported', key)
        # The line shown is the one that holds it: the father's line, not only the line next to it (X3).
        shown = [entry['quote'] for entry in out['v3_8']['held_candidate']['context']]
        self.assertIn('His father had a heart attack at 55.', shown)
        for notes, label, quote in (
                ('Her sister was seen in oncology last month. Assessment is breast cancer.', 'Assessment',   # C4
                 'Assessment is breast cancer.'),
                ('His father had a heart attack at 55. Examination at that time was normal.', 'Examination',  # C8
                 'Examination at that time was normal.'),
                ('Patient presents with chest pain. His father had a heart attack at 55. Examination is normal.',
                 'Examination', 'Examination is normal.'),
                # R1-6: a labelled line between them is held as possibly that person's; it does not close the run.
                ('Patient presents with chest pain. Her sister was seen in oncology last month.\nAllergies: none.\n'
                 'Plan is chemotherapy.', 'Plan', 'Plan is chemotherapy.'),
                ('Patient presents with chest pain. Her sister was seen in oncology last month.\nAssessment: breast '
                 'cancer.', 'Assessment', 'Assessment: breast cancer.')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, label, [quote])

    # ── the actor of a pronoun: never released on it; held when it is not uniquely the patient ────────────────────
    def test_a_pronoun_that_is_not_uniquely_the_patients_is_held(self):
        for notes, quote in (('His father had a heart attack at 55. He takes rosuvastatin.', 'He takes rosuvastatin.'),  # B6
                             ('Her mother has migraines. She takes sumatriptan.', 'She takes sumatriptan.'),
                             ('The patient lives with her husband. He takes warfarin.', 'He takes warfarin.'),
                             ('45-year-old man presents with cough. She takes warfarin.', 'She takes warfarin.'),
                             ('The patient lives with their partner. He takes warfarin.', 'He takes warfarin.'),
                             ('45-year-old man presents with cough.\n\nShe takes warfarin.', 'She takes warfarin.'),
                             # The positional rule, restored: the sentence before may set its frame.
                             ('The patient is subject to a Community Treatment Order (CTO). She attends the clinic '
                              'every week.', 'She attends the clinic every week.')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, 'Medications', [quote])
        reading = g.governance_for('45-year-old man presents with cough.\n\nShe takes warfarin.', form())[11]['preceding']
        second = reading['units'][1]['id']
        self.assertEqual(reading['resolved'][second]['actor'], 'ambiguous')
        self.assertEqual(reading['resolved'][second]['hold_cause']['quote'], '45-year-old man presents with cough.')

    # ── the positional rule, restored: anything later in the paragraph but a plain labelled value may change it ────
    def test_a_later_unit_holds_by_position(self):
        cc = '45-year-old man presents with right knee pain for three weeks after a fall.'
        for notes, label, quote in (
                (N04, 'Chief complaint', cc), (N04, 'History of present illness', cc),
                ('The patient takes aspirin.\nShe sleeps well.', 'Medications', 'The patient takes aspirin.'),
                ('The patient was seen for removal of a skin lesion on the left forearm. It was postponed.',      # B1
                 'Chief complaint', 'The patient was seen for removal of a skin lesion on the left forearm.'),
                ('The patient presents with chest pain. The pain resolved yesterday.', 'Chief complaint',          # B2
                 'The patient presents with chest pain.'),
                ('The patient is on methadone. The patient is not on diazepam or methadone.', 'Medications',       # B7
                 'The patient is on methadone.'),
                ('Patient presents with chest pain. Not anymore.', 'Chief complaint', 'Patient presents with chest pain.'),  # B8
                ('The patient presents with chest pain. His father had angina. The pain resolved yesterday.',       # B11
                 'Chief complaint', 'The patient presents with chest pain.'),
                ('Examination is normal. However, this was before the fall.', 'Examination', 'Examination is normal.'),  # C3
                ('The patient takes warfarin. Anticoagulation was discontinued.', 'Medications',                   # F1
                 'The patient takes warfarin.'),
                ('The patient presents with chest pain. She came in for palpitations.', 'Chief complaint',          # F8
                 'The patient presents with chest pain.'),
                ('Previously. The patient took warfarin.', 'Medications', 'The patient took warfarin.')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, label, [quote])
        # Another asked question's PLAIN labelled value never holds it (R3-1, unchanged).
        self.assertSupported('Allergies: penicillin.\nMedications: penicillin desensitisation.', 'Allergies',
                             ['Allergies: penicillin.'], 'penicillin.')
        self.assertSupported('The patient takes aspirin.\nSmoker: No.', 'Medications', ['The patient takes aspirin.'],
                             'The patient takes aspirin.')

    def test_labelled_and_negative_answers_keep_the_positional_rule(self):
        for notes, label, quote in (
                ('Allergies: none known.\nPenicillin causes a rash.', 'Allergies', 'Allergies: none known.'),
                ('The patient is not allergic to anything. Penicillin causes a rash.', 'Allergies',
                 'The patient is not allergic to anything.'),
                ('Allergies: none known.\nCorrection: penicillin.', 'Allergies', 'Allergies: none known.'),       # C1
                ('Smoker: No.\nBut he quit only last month.', 'Smoker', 'Smoker: No.'),                          # C2
                ('Smoker: No.\nHe quit smoking last month.', 'Smoker', 'Smoker: No.')):                          # B12
            with self.subTest(notes=notes):
                self.assertHeld(notes, label, [quote])

    # ── G-A: the title is not a qualifier ──────────────────────────────────────────────────────────────────────────
    def test_the_form_title_is_not_a_qualifier(self):
        fields = form()
        picks = {'v3_1': ['This is a 30-year-old female seen for headaches.'],
                 'v3_2': ['The headaches started two months ago and are worse in the morning.',
                          'She denies visual changes, nausea, or weakness.'],
                 'v3_4': ['She takes ibuprofen as needed.'], 'v3_5': ['No known drug allergies.'],
                 'v3_6': ['She is a nonsmoker.'], 'v3_7': ['Neurological examination is normal.'],
                 'v3_8': ['Assessment is tension-type headache.'],
                 'v3_9': ['Plan is to start amitriptyline 10 mg at night.', 'She will follow up in six weeks.']}
        out = adopt(N01, picks, fields)
        expected = {'v3_7': 'Neurological examination is normal.', 'v3_8': 'tension-type headache.',
                    'v3_9': 'to start amitriptyline 10 mg at night.\nShe will follow up in six weeks.'}
        for key, text in expected.items():
            self.assertEqual((out[key]['status'], out[key]['text']), ('supported', text), key)
            self.assertEqual(g.governed_decisions(N01, fields, {key: {**out[key], 'reviewed': True}}), [], key)
        # Held by position (a later sentence can change them by meaning), G-I (allergy consistency) and G-G (an option
        # from prose): the actor-ledger subsets (G-B1) are withdrawn.
        for key in ('v3_1', 'v3_2', 'v3_4', 'v3_5', 'v3_6'):
            self.assertNotEqual(out[key]['status'], 'supported', key)

    def test_a_qualifier_that_remains_after_the_title_still_holds(self):
        for label, context, notes in (('Allergies', 'Family history', 'No known drug allergies.'),               # A1
                                      ('Allergies', TITLE + ' > Family history', 'No known drug allergies.'),     # A4
                                      ('Examination', 'Cardiovascular examination', 'Neurological examination is normal.')):  # A2
            with self.subTest(context=context):
                self.assertHeld(notes, label, [notes], fields=form(**{label: context}))
        self.assertSupported('Neurological examination is normal.', 'Examination',
                             ['Neurological examination is normal.'], 'Neurological examination is normal.')
        self.assertEqual(g.v3_field_qualifier({'label': 'Smoker', 'context': TITLE + ' > Smoker'}, [TITLE]), '')
        self.assertEqual(g.v3_field_qualifier({'label': 'Smoker', 'context': 'Mother > Smoker'}, []), 'Mother')

    # ── G-D: a present-tense patient sentence naming its own field, with nothing else in the note ─────────────────
    def test_a_patient_sentence_naming_its_own_side_field(self):
        right, left = field('v3_1', 'Right knee'), field('v3_2', 'Left knee')
        right['context'], left['context'] = 'Knee review > Right knee', 'Knee review > Left knee'
        fields = [right, left]
        self.assertSupported('The patient has right knee pain.', 'Right knee', ['The patient has right knee pain.'],
                             'The patient has right knee pain.', fields=fields)
        # F9: another paragraph can reframe it, and only the coupling reader reads the note that far.
        self.assertHeld('The patient has right knee pain.\n\nWrong side: it is the left knee.', 'Right knee',
                        ['The patient has right knee pain.'], fields=fields)
        findings = field('v3_3', 'Clinical findings', 'long_text')
        findings['context'] = 'Knee review > Clinical findings'
        self.assertHeld('The patient has right knee pain and normal clinical findings.', 'Right knee',
                        ['The patient has right knee pain and normal clinical findings.'], fields=[right, findings])
        for notes in ("The patient's mother has right knee pain.",                          # D1
                      'The patient has right knee pain and the left knee is swollen.',     # D2
                      'The patient has left knee pain.',                                    # D4
                      'The patient had right knee pain last year.',                         # D5
                      'The patient had right knee pain.',
                      'Does the patient have right knee pain?',                             # D6
                      'The patient possibly has right knee pain.'):                         # D7
            with self.subTest(notes=notes):
                self.assertHeld(notes, 'Right knee', [notes], fields=fields)

    # ── G-E: one admissible adverbial clause, both clauses present tense ───────────────────────────────────────────
    def test_an_admissible_adverbial_clause(self):
        self.assertHeld('The patient sleeps poorly because she worries.', 'History of present illness',
                        ['The patient sleeps poorly because she worries.'])  # a pronoun subject: no admissible adverbial
        self.assertSupported('The patient sleeps poorly because the knee hurts.', 'History of present illness',
                             ['The patient sleeps poorly because the knee hurts.'])  # a thing subject: admissible
        self.assertHeld('The patient slept poorly until the knee healed.', 'History of present illness',
                        ['The patient slept poorly until the knee healed.'])   # R1-9: an ended state

    # ── G-H: a bare repair of a labelled answer does not reach a later unrelated plain labelled value ──────────────
    def test_a_bare_repairs_reach(self):
        fields = [field('v3_1', 'Chief complaint'), field('v3_2', 'Allergies'), field('v3_3', 'Smoker', 'choice', ['Yes', 'No'])]
        for f in fields:
            f['context'] = 'Skin clinic record' + (' > Smoker' if f['label'] == 'Smoker' else '')
        cc = 'Patient presents with a rash on both forearms.'
        for notes in (cc + '\nAllergies: penicillin. Sorry, I mean amoxicillin.\nSmoker: No.',              # N11
                      cc + '\n\nAllergies: penicillin.\nSorry, I mean amoxicillin.\n\nSmoker: No.'):         # N12
            with self.subTest(notes=notes):
                self.assertSupported(notes, 'Smoker', ['Smoker: No.'], 'No', fields=fields)
                self.assertHeld(notes, 'Chief complaint', [cc], fields=fields)
        for notes, quote in (('Smoker: No. Sorry, I mean yes.', 'Smoker: No. Sorry, I mean yes.'),                 # H1
                             ('Allergies: penicillin.\nSmoker: No.\nSorry, I mean amoxicillin.', 'Smoker: No.'),   # H2
                             ('Strike the next entry.\nSmoker: Yes.', 'Smoker: Yes.'),                              # H3
                             ('Disregard the following.\nSmoker: Yes.', 'Smoker: Yes.'),                            # H4
                             ('Sorry, the next one is wrong.\nSmoker: Yes.', 'Smoker: Yes.'),                       # H5
                             ('Sorry, next line is wrong.\nSmoker: Yes.', 'Smoker: Yes.'),
                             ('Allergies: none.\nActually, she smokes daily.\nSmoker: No.', 'Smoker: No.'),
                             # F4: the repaired statement is unlabelled, so its question is unknown: note-wide.
                             ('Patient presents with a rash, sorry, I mean a wound.\nSmoker: No.', 'Smoker: No.'),
                             # A later line of the SAME question stays in the repair's reach.
                             ('Smoker: No.\nSorry, I mean yes.\nSmoker: Yes.', 'Smoker: Yes.')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, 'Smoker', [quote], fields=fields)
        self.assertHeld(cc + '\n\nAllergies: none. Sorry, I meant both legs.', 'Chief complaint', [cc], fields=fields)  # H6
        # A bare repair in a LATER paragraph still governs what precedes it (only the note-wide reader sees it).
        self.assertHeld('Smoker: No.\n\nSorry, I mean yes.', 'Smoker', ['Smoker: No.'], fields=fields)
        # A replacement naming a place or a direction is not bare: note-wide as before.
        self.assertHeld('Sorry, next one.\nSmoker: Yes.', 'Smoker', ['Smoker: Yes.'], fields=fields)

    # ── G-F: repeated write-in labels identified by their printed parent question ───────────────────────────────────
    def test_repeated_write_ins_identified_by_their_parent_question(self):
        fields = []
        for key, context in (('v3_1', 'How would you describe the pain? (tick all that apply)'),
                             ('v3_2', 'Do you notice anything before the headache begins? (tick all that apply)'),
                             ('v3_3', 'What makes the pain worse? (tick all that apply)')):
            f = field(key, 'Other')
            f['context'] = context
            fields.append(f)
        pain = 'The patient describes the pain as a tight band around her head.'
        aura = 'The patient sees zigzag lines before the headache begins.'
        notes = pain + '\n\n' + aura
        out = adopt(notes, {'v3_1': [pain], 'v3_2': [aura]}, fields)
        self.assertEqual((out['v3_1']['status'], out['v3_1']['text']), ('supported', pain))
        self.assertEqual((out['v3_2']['status'], out['v3_2']['text']), ('supported', aura))
        for key in ('v3_1', 'v3_2'):
            self.assertEqual(g.governed_decisions(notes, fields, {key: {**out[key], 'reviewed': True}}), [])
        # In ONE paragraph each is held by position, as any sentence beside another.
        joined = adopt(pain + ' ' + aura, {'v3_1': [pain], 'v3_2': [aura]}, fields)
        for key in ('v3_1', 'v3_2'):
            self.assertNotEqual(joined[key]['status'], 'supported', key)
        for picks in ({'v3_1': [aura]},                                   # F3: the model misassigns it
                      {'v3_1': [pain], 'v3_2': [pain]},                   # F2: one sentence into two of them
                      {'v3_1': [aura], 'v3_2': [pain]}):
            with self.subTest(picks=picks):
                out = adopt(notes, picks, fields)
                for key in picks:
                    self.assertNotEqual(out[key]['status'], 'supported', (picks, key))
        out = adopt('Other: tight band.', {'v3_1': ['Other: tight band.']}, fields)                           # F1
        self.assertNotEqual(out['v3_1']['status'], 'supported')
        # (i) a labelled line names every one of them, even when its words point to one parent question.
        labelled = 'Other: described as a tight band.'
        self.assertNotEqual(adopt(labelled, {'v3_1': [labelled]}, fields)['v3_1']['status'], 'supported')
        same = copy.deepcopy(fields)
        same[1]['context'] = same[0]['context']
        self.assertNotEqual(adopt(notes, {'v3_1': [pain]}, same)['v3_1']['status'], 'supported')

    def test_one_statement_for_two_specific_questions_is_held(self):
        sentence = 'He has hypertension and takes lisinopril 10 mg daily.'
        for notes in (N04, sentence):
            out = adopt(notes, {'v3_3': [sentence], 'v3_4': [sentence]}, form())
            self.assertNotEqual(out['v3_3']['status'], 'supported', notes)
            self.assertNotEqual(out['v3_4']['status'], 'supported', notes)

    # ── X3: the line shown with a hold is the one that causes it ───────────────────────────────────────────────────
    def test_the_line_shown_with_a_hold_is_its_cause(self):
        notes = 'His father had a heart attack at 55. He is allergic to penicillin. Allergies: penicillin.'
        held = self.assertHeld(notes, 'Allergies', ['Allergies: penicillin.'])
        shown = [entry['quote'] for entry in held['held_candidate']['context']]
        self.assertIn('His father had a heart attack at 55.', shown)
        self.assertNotIn('He is allergic to penicillin.', shown)
        # A positional hold whose exemption another block denied shows that block (N06: the consent block).
        n06 = ('The patient was seen for removal of a skin lesion on the left forearm. The risks and benefits were '
               'discussed. Consent obtained: yes. The lesion was excised under local anesthesia and closed with '
               'sutures. She tolerated the procedure well. Plan is suture removal in ten days.')
        held = self.assertHeld(n06, 'Plan', ['Plan is suture removal in ten days.'])
        shown = [entry['quote'] for entry in held['held_candidate']['context']]
        self.assertIn('Consent obtained: yes.', shown)
