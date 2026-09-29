"""Ordinary notes made useful without weakening the context that governs evidence (2026-09-29).

Synthetic notes only; the provider's choice is simulated by unit selections (the `run()` shape). Each group pins one
change to the ONE neighbour rule (`generation.v3_neighbour_causes`) or its readers, with the adverse shapes that must
stay held beside the supported ones. The recorded campaign shapes are named N01..N12; the controls A..H, P, S keep
the names of the over-hold analysis (phase-a/overholds.txt).
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
                             ('The patient reports her husband takes warfarin.', 'Medications')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, label, [notes])
                # Finalization refuses the same statement stored as supported (one reader).
                fields = form()
                key = key_of(fields, label)
                stored = {'text': notes, 'status': 'supported', 'reviewed': True,
                          'evidence': [{'quote': notes, 'start': 0, 'end': len(notes)}]}
                self.assertEqual(g.governed_decisions(notes, fields, {key: stored}), [label])
        self.assertSupported("The patient's neighbour takes warfarin. The patient takes aspirin.", 'Medications',
                             ['The patient takes aspirin.'], 'The patient takes aspirin.')

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
                 'Allergies', 'Allergies: penicillin.')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, label, [quote])
        # With the patient re-established first, the labelled line names its question as before.
        self.assertSupported('His father had a heart attack at 55. The patient takes aspirin. Allergies: penicillin.',
                             'Allergies', ['Allergies: penicillin.'], 'penicillin.')

    # ── G-J: encounter topics after a CLOSED run belong to the encounter ────────────────────────────────────────────
    def test_encounter_topics_after_a_closed_run_and_not_after_an_open_one(self):
        fields = form()
        out = adopt(N05, {'v3_1': ['Patient presents with chest tightness on exertion for one month.'],
                          'v3_5': ['Allergies: none known.'], 'v3_6': ['Smoker: Yes.'],
                          'v3_7': ['Examination is normal.'], 'v3_8': ['Assessment is possible stable angina.'],
                          'v3_9': ['Plan is an exercise stress test and aspirin 81 mg daily.'],
                          'v3_4': ['He takes rosuvastatin.'],
                          'v3_3': ['His father had a heart attack at 55.', 'He has high cholesterol.']}, fields)
        for key, text in (('v3_1', 'Patient presents with chest tightness on exertion for one month.'),
                          ('v3_7', 'normal.'), ('v3_8', 'possible stable angina.'),
                          ('v3_9', 'an exercise stress test and aspirin 81 mg daily.')):
            self.assertEqual((out[key]['status'], out[key]['text']), ('supported', text), key)
        for key in ('v3_3', 'v3_4', 'v3_5', 'v3_6'):
            self.assertNotEqual(out[key]['status'], 'supported', key)
        for notes, label, quote in (
                ('Her sister was seen in oncology last month. Assessment is breast cancer.', 'Assessment',   # C4
                 'Assessment is breast cancer.'),
                ('His father had a heart attack at 55. Examination at that time was normal.', 'Examination',  # C8
                 'Examination at that time was normal.'),
                ('His father had a heart attack at 55. Examination is normal.', 'Examination', 'Examination is normal.'),
                # the patient's encounter was established first, but the run is still OPEN
                ('Patient presents with chest pain. His father had a heart attack at 55. Examination is normal.',
                 'Examination', 'Examination is normal.'),
                # a paragraph that OPENS with another person has no encounter of the patient to return to
                ('Her sister was seen in oncology last month.\nAllergies: penicillin.\nPlan is chemotherapy.', 'Plan',
                 'Plan is chemotherapy.'),
                ('Her sister was seen in oncology last month. Smoker: No. Assessment is breast cancer.', 'Assessment',
                 'Assessment is breast cancer.'),
                ('Her sister was seen in oncology last month.\nAllergies: penicillin.\nAssessment: breast cancer.',
                 'Assessment', 'Assessment: breast cancer.')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, label, [quote])

    # ── (b'): the actor comes from the nearest preceding person, and must be uniquely the patient ─────────────────
    def test_pronoun_resolved_to_the_patient_and_competing_actors(self):
        self.assertSupported('The patient is subject to a Community Treatment Order (CTO). She attends the clinic every '
                             'week.', 'Past medical history', ['She attends the clinic every week.'],
                             'She attends the clinic every week.')
        for notes, quote in (('His father had a heart attack at 55. He takes rosuvastatin.', 'He takes rosuvastatin.'),  # B6
                             ('Her mother has migraines. She takes sumatriptan.', 'She takes sumatriptan.'),
                             ('The patient lives with her husband. He takes warfarin.', 'He takes warfarin.'),
                             ('45-year-old man presents with cough. She takes warfarin.', 'She takes warfarin.'),
                             ('The patient lives with their partner. He takes warfarin.', 'He takes warfarin.')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, 'Medications', [quote])

    # ── (a'): a later unit holds only when linked ──────────────────────────────────────────────────────────────────
    def test_a_later_unit_holds_only_when_linked(self):
        cc = '45-year-old man presents with right knee pain for three weeks after a fall.'
        self.assertSupported(N04, 'Chief complaint', [cc], cc)
        self.assertSupported(N04, 'History of present illness', [cc], cc)
        self.assertSupported('The patient takes aspirin.\nShe sleeps well.', 'Medications', ['The patient takes aspirin.'])
        # A possessed thing as a later subject refers back ('Her mood is low.'): linked, so held (conservative).
        self.assertHeld('The patient takes aspirin.\nHer mood is low.', 'Medications', ['The patient takes aspirin.'])
        for notes, label, quote in (
                ('The patient was seen for removal of a skin lesion on the left forearm. It was postponed.',      # B1
                 'Chief complaint', 'The patient was seen for removal of a skin lesion on the left forearm.'),
                ('The patient presents with chest pain. The pain resolved yesterday.', 'Chief complaint',          # B2
                 'The patient presents with chest pain.'),
                ('The patient presents with chest pain. The pain has resolved.', 'Chief complaint',
                 'The patient presents with chest pain.'),
                ('The patient is on methadone. The patient is not on diazepam or methadone.', 'Medications',       # B7
                 'The patient is on methadone.'),
                ('Patient presents with chest pain. Not anymore.', 'Chief complaint', 'Patient presents with chest pain.'),  # B8
                ('The patient presents with chest pain. His father had angina. The pain resolved yesterday.',       # B11
                 'Chief complaint', 'The patient presents with chest pain.'),
                ('Examination is normal. However, this was before the fall.', 'Examination', 'Examination is normal.'),  # C3
                ('The patient takes warfarin. Dr Smith stopped anticoagulation.', 'Medications', 'The patient takes warfarin.'),
                ('The patient takes aspirin. She stopped it last week.', 'Medications', 'The patient takes aspirin.'),
                ('The patient takes warfarin. Warfarin was stopped last month.', 'Medications', 'The patient takes warfarin.'),
                ('Assessment is migraine. Diagnosis unclear.', 'Assessment', 'Assessment is migraine.'),
                ('Plan is physiotherapy. No physiotherapy until the fracture heals.', 'Plan', 'Plan is physiotherapy.'),
                ('The patient presents with a rash. Her husband has the same rash.', 'Chief complaint',
                 'The patient presents with a rash.')):
            with self.subTest(notes=notes):
                self.assertHeld(notes, label, [quote])

    def test_each_link_condition_alone_holds(self):
        cc = 'The patient presents with chest pain.'
        for later in ('Worse at night.',                                  # (1) no nominal subject
                      'It radiates to the jaw.',                          # (2) neuter pronoun
                      'Chest pain radiates to the jaw.',                  # (3) it repeats a core word of ours
                      'Also, she reports nausea.',                        # (4) a connective attached to its root
                      'She asks whether surgery is needed?',              # (5) a shape reader (it asks)
                      'She declined admission.'):                         # (6) a status word at clause level
            with self.subTest(later=later):
                self.assertHeld(cc + ' ' + later, 'Chief complaint', [cc])
        self.assertHeld('The patient takes warfarin 5 mg daily. The dose was reduced to 3 mg.', 'Medications',
                        ['The patient takes warfarin 5 mg daily.'])       # (2) a definite thing subject refers back
        self.assertHeld('The patient reports a rash after amoxicillin. Allergy testing was arranged.', 'Allergies',
                        ['The patient reports a rash after amoxicillin.'])  # (3) it names the question's label
        self.assertSupported(cc + ' She sleeps well.', 'Chief complaint', [cc], cc)
        presentation = '45-year-old man presents with right knee pain.'
        self.assertHeld(presentation + ' He reports the opposite side.', 'Chief complaint', [presentation])  # (7) a side
        # Another question's PLAIN value that repeats this unit's own word links to it.
        self.assertHeld('The patient takes ibuprofen as needed. Assessment is ibuprofen overuse.', 'Medications',
                        ['The patient takes ibuprofen as needed.'])
        # A LABELLED answer keeps R3-1 exactly: another question's plain labelled value never holds it, shared word or
        # not (the laterality round trip: 'Injected joint: (R) knee' above 'Aspirated joint: L knee').
        self.assertSupported('Allergies: penicillin.\nMedications: penicillin desensitisation.', 'Allergies',
                             ['Allergies: penicillin.'], 'penicillin.')
        # A subject-less fragment written just before a unit may scope it ('Previously.').
        self.assertHeld('Previously. The patient took warfarin.', 'Medications', ['The patient took warfarin.'])

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

    # ── G-A + G-B1: the title is not a qualifier; actor-ledger units are selected alone ────────────────────────────
    def test_actor_ledger_units_selected_alone_under_the_form_title(self):
        fields = form()
        picks = {'v3_1': ['This is a 30-year-old female seen for headaches.'],
                 'v3_2': ['The headaches started two months ago and are worse in the morning.',
                          'She denies visual changes, nausea, or weakness.'],
                 'v3_4': ['She takes ibuprofen as needed.'], 'v3_5': ['No known drug allergies.'],
                 'v3_6': ['She is a nonsmoker.'], 'v3_7': ['Neurological examination is normal.'],
                 'v3_8': ['Assessment is tension-type headache.'],
                 'v3_9': ['Plan is to start amitriptyline 10 mg at night.', 'She will follow up in six weeks.']}
        out = adopt(N01, picks, fields)
        expected = {'v3_1': 'This is a 30-year-old female seen for headaches.',
                    'v3_2': 'The headaches started two months ago and are worse in the morning.\n'
                            'She denies visual changes, nausea, or weakness.',
                    'v3_4': 'She takes ibuprofen as needed.', 'v3_7': 'Neurological examination is normal.',
                    'v3_8': 'tension-type headache.',
                    'v3_9': 'to start amitriptyline 10 mg at night.\nShe will follow up in six weeks.'}
        for key, text in expected.items():
            self.assertEqual((out[key]['status'], out[key]['text']), ('supported', text), key)
            self.assertEqual(g.governed_decisions(N01, fields, {key: {**out[key], 'reviewed': True}}), [], key)
        # G-I (allergy contextual consistency) and G-G (an option from prose) stay held.
        self.assertNotEqual(out['v3_5']['status'], 'supported')
        self.assertNotEqual(out['v3_6']['status'], 'supported')

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

    # ── G-D: a present-tense patient sentence naming its own field ─────────────────────────────────────────────────
    def test_a_patient_sentence_naming_its_own_side_field(self):
        right, left = field('v3_1', 'Right knee'), field('v3_2', 'Left knee')
        right['context'], left['context'] = 'Knee review > Right knee', 'Knee review > Left knee'
        fields = [right, left]
        self.assertSupported('The patient has right knee pain.', 'Right knee', ['The patient has right knee pain.'],
                             'The patient has right knee pain.', fields=fields)
        findings = field('v3_3', 'Clinical findings', 'long_text')
        findings['context'] = 'Knee review > Clinical findings'
        self.assertHeld('The patient has right knee pain and normal clinical findings.', 'Right knee',
                        ['The patient has right knee pain and normal clinical findings.'], fields=[right, findings])
        self.assertHeld('The patient sleeps poorly because she worries.', 'History of present illness',
                        ['The patient sleeps poorly because she worries.'])  # a pronoun subject: no admissible adverbial
        self.assertSupported('The patient sleeps poorly because the knee hurts.', 'History of present illness',
                             ['The patient sleeps poorly because the knee hurts.'])  # a thing subject: admissible
        for notes in ("The patient's mother has right knee pain.",                          # D1
                      'The patient has right knee pain and the left knee is swollen.',     # D2
                      'The patient has left knee pain.',                                    # D4
                      'The patient had right knee pain last year.',                         # D5
                      'The patient had right knee pain.',
                      'Does the patient have right knee pain?',                             # D6
                      'The patient possibly has right knee pain.'):                         # D7
            with self.subTest(notes=notes):
                self.assertHeld(notes, 'Right knee', [notes], fields=fields)

    # ── G-H: a bare speech repair governs only what precedes it ────────────────────────────────────────────────────
    def test_a_bare_repair_governs_only_what_precedes_it(self):
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
                             ('Allergies: none.\nActually, she smokes daily.\nSmoker: No.', 'Smoker: No.')):
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
        notes = pain + ' ' + aura
        out = adopt(notes, {'v3_1': [pain], 'v3_2': [aura]}, fields)
        self.assertEqual((out['v3_1']['status'], out['v3_1']['text']), ('supported', pain))
        self.assertEqual((out['v3_2']['status'], out['v3_2']['text']), ('supported', aura))
        for key in ('v3_1', 'v3_2'):
            self.assertEqual(g.governed_decisions(notes, fields, {key: {**out[key], 'reviewed': True}}), [])
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
        out = adopt(N04, {'v3_3': [sentence], 'v3_4': [sentence]}, form())
        self.assertNotEqual(out['v3_3']['status'], 'supported')
        self.assertNotEqual(out['v3_4']['status'], 'supported')

    # ── X3: the line shown with a hold is the one that causes it ───────────────────────────────────────────────────
    def test_the_line_shown_with_a_hold_is_its_cause(self):
        notes = 'His father had a heart attack at 55. He is allergic to penicillin. Allergies: penicillin.'
        held = self.assertHeld(notes, 'Allergies', ['Allergies: penicillin.'])
        shown = [entry['quote'] for entry in held['held_candidate']['context']]
        self.assertIn('His father had a heart attack at 55.', shown)
        self.assertNotIn('He is allergic to penicillin.', shown)
