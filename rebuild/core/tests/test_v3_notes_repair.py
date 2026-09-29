"""Regression tests for the refutation round of the notes-usefulness change (2026-09-29).

Each test is named for a CONFIRMED finding (verify/ cases, reproduced on 0350b4ea before any repair) and uses the
refuter's own synthetic shapes. Every one FAILS on 0350b4ea and passes on the repair: the repair restored the positional
neighbour rules (`generation.v3_neighbour_causes`) and kept only hold-only readings on top of them. Forms are the frozen
synthetic diagnostic forms (docs/rebuild/v1/sonnet5-campaign/diagnostics/notes/cases.json), read-only.

⚠️ ROUND 3 (2026-09-29): the releases this module pinned as 'still standing' (G-D, G-E, G-H, F2-set2) are WITHDRAWN
(round-2 refutation: RR1, RR2, RR3, RR9, RR2-1..RR2-4); each such assertion now pins debaefd9's hold instead, and says so.
"""
import copy
import functools
import json
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from core import generation as g
from core import v3_syntax

CASES = Path(__file__).resolve().parents[3] / 'docs/rebuild/v1/sonnet5-campaign/diagnostics/notes/cases.json'
CRLF_AND_LS = ('\r\n', ' ')


@functools.lru_cache(maxsize=1)
def _forms():
    return json.loads(CASES.read_text())['forms']


def fields_of(name):
    entry = _forms()[name]
    return copy.deepcopy(entry['fields'] if isinstance(entry, dict) else entry)


def adopt(notes, picks, fields):
    """`picks`: {label: [exact quote or a unique substring of one unit]}; one response, every other field empty."""
    asked, context, v3_fields = g.v3_generation_fields(fields)
    units = g.source_units(notes, asked, context_labels=context)[0]
    chosen = {}
    for label, quotes in picks.items():
        key = next(f['key'] for f in fields if f['label'] == label)
        ids = []
        for quote in quotes:
            found = [u['id'] for u in units if u['quote'] == quote] or [u['id'] for u in units if quote in u['quote']]
            assert len(found) == 1, (quote, [u['quote'] for u in units])
            ids.append(found[0])
        chosen[key] = ids
    selections = g.UnitSelections(fields=[g.UnitSelection(key=f['key'], unit_ids=chosen.get(f['key'], []),
                                                          conflict=False) for f in asked])
    selections = g.unit_selections(notes, asked, selections, context_labels=context)
    answers = g.validate_selections(notes, asked, selections, context_labels=context, evidence_contract=g.TAB_CONTRACT)
    adopted = g.v3_adopted(v3_fields, answers, notes, asked, context)
    return {f['label']: adopted[f['key']] for f in fields if f['key'] in chosen}


class RepairTestCase(SimpleTestCase):
    def assertHeld(self, notes, picks, form='r1-11', finalization=True):
        """Held at generation; and the same candidate stored as `supported` is refused by finalization (the page, save
        and finalization reader agrees)."""
        fields = fields_of(form)
        out = adopt(notes, picks, fields)
        for label, answer in out.items():
            with self.subTest(notes=notes, label=label):
                self.assertNotEqual(answer['status'], 'supported', (notes, label, answer.get('text')))
                self.assertEqual(answer['text'], '')
                candidate = answer.get('held_candidate') or {}
                if finalization and candidate.get('evidence'):
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

    def assertHeldInEveryLayout(self, sentences, picks, form='r1-11'):
        """One paragraph with spaces, and the same sentences on lines split by CRLF and by U+2028."""
        self.assertHeld(' '.join(sentences), picks, form)
        for separator in CRLF_AND_LS:
            self.assertHeld(separator.join(sentences), picks, form)


class BeforeSideFindings(RepairTestCase):
    def test_R1_1_a_scoping_or_hypothetical_sentence_before_holds_the_answer(self):
        self.assertHeldInEveryLayout(
            ['The patient presents with a breast lump.', 'Chemotherapy is an option depending on the biopsy result.',
             'She will start chemotherapy next month.'], {'Plan': ['She will start chemotherapy']})
        for notes, picks in (
                ('The patient presents with knee pain. An MRI may show a meniscal tear. She will then need arthroscopy.',
                 {'Plan': ['She will then need arthroscopy.']}),                                              # M1
                ('The patient presents with chest pain. We debated whether to admit her. She will be admitted to the '
                 'ward.', {'Plan': ['She will be admitted to the ward.']}),                                    # M3
                ('The patient presents with a sore throat. A prescription was given in case symptoms worsen over the '
                 'weekend. She will take penicillin V for ten days.',
                 {'Plan': ['She will take penicillin V'], 'Medications': ['She will take penicillin V']}),    # M4
                ('The patient presents with a sore throat. A prescription was given in case symptoms worsen over the '
                 'weekend. She will take penicillin V for ten days.', {'Medications': ['She will take penicillin V']}),
                ('The patient presents with a sore throat. Should the culture be positive, antibiotics will be sent. '
                 'She will take penicillin V for ten days.', {'Plan': ['She will take penicillin V']}),        # M5
                ('The patient presents with knee pain. Surgery was discussed as a future option. She will have a total '
                 'knee replacement.', {'Plan': ['She will have a total knee replacement.']})):                # M6
            self.assertHeld(notes, picks)

    def test_R1_2_a_past_frame_before_holds_the_answer(self):
        self.assertHeldInEveryLayout(['The patient had an admission in 2019.', 'She presented with chest pain.'],
                                     {'Chief complaint': ['She presented with chest pain.']})
        self.assertHeld('The patient was last seen two years ago. She complained of back pain.',
                        {'Chief complaint': ['She complained of back pain.'],
                         'History of present illness': ['She complained of back pain.']})
        self.assertHeld('The patient had a DVT in 2015. She was on warfarin for six months.',
                        {'Medications': ['She was on warfarin for six months.']})                              # H8
        self.assertHeld('The patient was under a CTO in 2019. She attended the clinic every week.',
                        {'Clinic attendance': ['She attended the clinic every week.']}, form='n03-order-question')

    def test_R1_3_an_encounter_topic_after_another_occasion_is_held(self):
        self.assertHeldInEveryLayout(['The patient was seen in A&E yesterday.', 'Examination was normal.'],
                                     {'Examination': ['Examination was normal.']})
        self.assertHeldInEveryLayout(['The patient was reviewed at the previous visit in May.', 'Examination was normal.'],
                                     {'Examination': ['Examination was normal.']})
        for notes, picks in (
                ('The patient was seen in A&E yesterday. Examination is normal.', {'Examination': ['Examination is normal.']}),
                ('The patient attended the emergency department on Saturday. Assessment was musculoskeletal chest pain.',
                 {'Assessment': ['Assessment was musculoskeletal chest pain.']}),
                ('The patient saw the physiotherapist last week. Examination showed reduced range of movement.',
                 {'Examination': ['Examination showed reduced range of movement.']}),
                ('The patient saw her GP on Monday. Plan is amoxicillin for seven days.',
                 {'Plan': ['Plan is amoxicillin for seven days.']})):
            self.assertHeld(notes, picks)
        # Control, unchanged from before the change: this visit's presentation, then its examination.
        self.assertSupported('The patient presents with knee pain. Examination was normal.',
                             {'Examination': ['Examination was normal.']})

    def test_R1_5_an_embedded_pronoun_of_the_other_gender_holds_the_unit(self):
        self.assertHeldInEveryLayout(['45-year-old woman presents with a rash.', 'Her father visited.',
                                      'The patient says he is allergic to penicillin.'],
                                     {'Allergies': ['The patient says he is allergic to penicillin.']})
        self.assertHeldInEveryLayout(['45-year-old man presents with cough.', 'The patient reports that she takes warfarin.'],
                                     {'Medications': ['The patient reports that she takes warfarin.']})
        self.assertHeld('45-year-old woman presents with fatigue. The patient says he has hypertension.',
                        {'Past medical history': ['The patient says he has hypertension.']})             # W4
        self.assertHeld('The patient presents with cough. His father has diabetes. The patient reports that he takes '
                        'metformin.', {'Medications': ['The patient reports that he takes metformin.']})   # H2
        # The patient's gender is the note's: a later paragraph's embedded pronoun is checked against it too.
        self.assertHeld('45-year-old woman presents with a rash.\n\nThe patient says he is allergic to penicillin.',
                        {'Allergies': ['The patient says he is allergic to penicillin.']})
        self.assertHeld('45-year-old man presents with cough.\n\nShe takes warfarin.', {'Medications': ['She takes warfarin.']})

    def test_R1_6_a_labelled_line_does_not_close_another_persons_run(self):
        for separator in ('\n',) + CRLF_AND_LS:
            notes = separator.join(['The patient presents with chest pain. Her sister was seen in oncology last month.',
                                    'Assessment: breast cancer.', 'Plan is chemotherapy.'])
            self.assertHeld(notes, {'Plan': ['Plan is chemotherapy.'], 'Assessment': ['Assessment: breast cancer.']})
            self.assertHeld(notes, {'Plan': ['Plan is chemotherapy.']})
        self.assertHeld('The patient presents with chest pain. Her sister was seen in oncology last month.\n'
                        'Examination: breast lump.\nAssessment is breast cancer.',
                        {'Assessment': ['Assessment is breast cancer.']})                                 # J3
        self.assertHeld('The patient presents with chest pain. Her sister was seen in oncology last month.\n'
                        'Allergies: none.\nPlan is chemotherapy.', {'Plan': ['Plan is chemotherapy.']})    # H19b
        # A labelled line between them does not return the paragraph to the patient: the next labelled line is held too.
        self.assertHeld('His father had a heart attack at 55. He smoked heavily.\nAllergies: none.\nSmoker: Yes.',
                        {'Smoker': ['Smoker: Yes.']})

    def test_R1_7_indefinite_persons_are_other_persons(self):
        self.assertHeld('Somebody else takes warfarin.', {'Medications': ['Somebody else takes warfarin.']})  # I1
        self.assertHeld('Someone at home takes warfarin.', {'Medications': ['Someone at home takes warfarin.']})
        self.assertHeldInEveryLayout(['The patient presents with bruising.', 'Someone at home takes warfarin.'],
                                     {'Medications': ['Someone at home takes warfarin.']})                  # I2
        self.assertHeld('The patient presents with a rash. Somebody at home is allergic to penicillin. She is allergic '
                        'to penicillin.', {'Allergies': ['She is allergic to penicillin.']})               # I4
        self.assertHeld('The patient presents with cough. Everyone at home has flu. They take paracetamol.',
                        {'Medications': ['They take paracetamol.']})                                     # P4

    def test_R1_8_given_names_and_kinship_compounds_are_other_persons(self):
        question = 'Does a Community Treatment Order (CTO) currently apply to this person?'
        self.assertHeld('The patient lives with Jane. Jane is subject to a Community Treatment Order (CTO).',
                        {question: ['Jane is subject']}, form='n03-order-question')                       # R3
        # STATED RESIDUAL (v3_actors): a given name standing ALONE ('Jane is subject to a CTO.' as the whole note) reads
        # as a thing; the pinned entity recognizer was measured and cannot tell names from drugs. Not asserted here.
        self.assertHeld('The patient lives with Jane. She is subject to a Community Treatment Order (CTO).',
                        {question: ['She is subject']}, form='n03-order-question')                        # R4
        self.assertHeld('The patient cares for Doris. She has dementia.', {'Past medical history': ['She has dementia.']})
        self.assertHeld('The patient is here with Tom. He presents with a rash.', {'Chief complaint': ['He presents with a rash.']})
        self.assertHeld('Her stepbrother takes warfarin.', {'Medications': ['Her stepbrother takes warfarin.']})
        self.assertHeld('The patient presents with bruising. Her stepbrother takes warfarin.',
                        {'Medications': ['Her stepbrother takes warfarin.']})                            # C1h
        self.assertHeld('The patient presents with cough. Her mate has flu. She takes paracetamol.',
                        {'Medications': ['She takes paracetamol.']})                                     # C4c

    def test_R3_2_a_labelled_value_naming_another_person_opens_that_persons_run(self):
        for notes, picks in (
                ('The patient presents with a breast lump.\nPast medical history: her mother had breast cancer at 45.\n'
                 'She takes tamoxifen 20 mg daily.', {'Medications': ['She takes tamoxifen']}),              # Le
                ('The patient presents with a breast lump.\nPast medical history: her mother had breast cancer at 45.\n'
                 'She had a mastectomy in 2015.', {'History of present illness': ['She had a mastectomy']}),   # Lh
                ('The patient presents with cough.\nAllergies: her sister is allergic to penicillin.\nShe takes tamoxifen '
                 '20 mg daily.', {'Medications': ['She takes tamoxifen']}),                                  # La
                ('The patient presents with wheeze.\nSmoker: her husband smokes 20 a day.\nShe uses a salbutamol inhaler.',
                 {'Medications': ['She uses a salbutamol inhaler.']}),                                       # Lf
                ('The patient presents with fever.\nChief complaint: her daughter has had a fever for three days.\n'
                 'She takes paracetamol regularly.', {'Medications': ['She takes paracetamol']})):             # Lg
            self.assertHeld(notes, picks)
        # The actor reading itself: the labelled value opens another person's run, so the pronoun is hers.
        notes = 'The patient presents with cough.\nAllergies: her sister is allergic to penicillin.\nShe takes tamoxifen.'
        reading = g.governance_for(notes, fields_of('r1-11'))[11]['preceding']
        last = reading['units'][-1]['id']
        self.assertEqual(reading['resolved'][last]['actor'], 'other')

    def test_F5_an_earlier_status_by_a_class_word_holds_the_answer(self):
        self.assertHeld('She stopped anticoagulation last month. The patient takes warfarin.',
                        {'Medications': ['The patient takes warfarin.']})
        self.assertHeld('She has no thoughts of self-harm. The patient is suicidal.', {'Risk to self': ['The patient is suicidal.']},
                        form='n15-risk-and-arrangements')
        self.assertHeld('She has never had any lung disease. The patient has asthma.',
                        {'Past medical history': ['The patient has asthma.']})


class AfterSideFindings(RepairTestCase):
    def test_F1_a_later_class_word_changes_the_answer(self):
        for later in ('Anticoagulation was discontinued.', 'She switched to apixaban.', 'She ceased anticoagulation.'):
            self.assertHeld('The patient takes warfarin. ' + later, {'Medications': ['The patient takes warfarin.']})
        self.assertHeld('The patient takes warfarin 5 mg daily. Cardiology reduced her to 3 mg.',
                        {'Medications': ['The patient takes warfarin 5 mg daily.']})
        self.assertHeld('45-year-old man presents with right knee pain for three weeks after a fall. The patient takes '
                        'lisinopril 10 mg daily. Antihypertensives were discontinued after a fall. Allergies: penicillin. '
                        'Smoker: No.', {'Medications': ['The patient takes lisinopril']})
        self.assertHeld('The patient is on methadone.\nShe completed her opioid detox in May.',
                        {'Medication': ['The patient is on methadone.']}, form='n13-risk-and-medication')

    def test_R1_4_a_misparsed_drug_or_a_class_word_later_changes_the_answer(self):
        self.assertHeldInEveryLayout(['The patient takes apixaban 5 mg twice daily.', 'Apixaban was discontinued before surgery.'],
                                     {'Medications': ['The patient takes apixaban']})
        self.assertHeld('- The patient takes apixaban 5 mg twice daily.\n- Apixaban was discontinued before surgery.',
                        {'Medications': ['The patient takes apixaban']})
        for notes, quote in (
                ('The patient takes atorvastatin 40 mg at night. Statin therapy was discontinued due to myalgia.',
                 'The patient takes atorvastatin'),
                ('The patient takes apixaban 5 mg twice daily. Anticoagulants are on hold for surgery.', 'The patient takes apixaban'),
                ('The patient takes ramipril 5 mg daily. ACE inhibitor therapy was ceased because of a cough.',
                 'The patient takes ramipril'),
                ('The patient takes amoxicillin 500 mg three times daily. Antibiotic course completed on Friday.',
                 'The patient takes amoxicillin')):
            self.assertHeld(notes, {'Medications': [quote]})

    def test_F2_a_later_denial_inside_a_noun_phrase_changes_the_answer(self):
        self.assertHeld('The patient is suicidal.\nShe has no thoughts of self-harm.', {'Risk to self': ['The patient is suicidal.']},
                        form='n15-risk-and-arrangements')
        self.assertHeld('The patient takes warfarin. She takes no anticoagulants.', {'Medications': ['The patient takes warfarin.']})
        self.assertHeld('The patient has asthma. There is no evidence of airway disease.',
                        {'Past medical history': ['The patient has asthma.']})
        self.assertHeld('The patient is subject to MAPPA.\nProbation report no current involvement.',
                        {'MAPPA status': ['The patient is subject to MAPPA.']}, form='n15-risk-and-arrangements')

    def test_F3_a_later_antonym_or_contradicting_state_changes_the_answer(self):
        for notes, label in (('The patient smokes.\nThe patient is a lifelong non-smoker.', 'Smoking status'),
                             ('The patient is oriented.\nThe patient is disoriented to time.', 'Mental state'),
                             ('The patient is calm.\nShe is agitated and pacing.', 'Mental state'),
                             ('The patient smokes.\nShe gave up cigarettes in 2019.', 'Smoking status')):
            self.assertHeld(notes, {label: [notes.split('\n')[0]]}, form='n14-smoking-and-mental-state')
        self.assertHeld('The patient is euthymic.\nShe feels hopeless every day.', {'Mental state': ['The patient is euthymic.']},
                        form='n16-mood-and-allergies')
        self.assertHeld('The patient is subject to MAPPA.\nShe was discharged from MAPPA in May.',
                        {'MAPPA status': ['The patient is subject to MAPPA.']}, form='n15-risk-and-arrangements')
        self.assertHeld('The patient presents with chest pain. She is asymptomatic.',
                        {'Chief complaint': ['The patient presents with chest pain.']})

    def test_F6_a_later_class_denial_inside_the_actor_ledger_changes_the_answer(self):
        for later in ('She denies painkillers, NSAIDs, or opioids.', 'She denies analgesic use, opioid use, or alcohol use.'):
            self.assertHeld('This is a 30-year-old female seen for headaches. She takes ibuprofen as needed. ' + later,
                            {'Medications': ['She takes ibuprofen as needed.']})

    def test_F7_a_later_uncertainty_changes_the_answer(self):
        for later in ('Diagnosis is self-reported.', 'Her GP is doubtful.', 'Spirometry is required to confirm.'):
            self.assertHeld('The patient has asthma. ' + later, {'Past medical history': ['The patient has asthma.']})

    def test_F8_a_later_restated_reason_changes_the_chief_complaint(self):
        for later in ('She meant heartburn.', 'She came in for palpitations.', 'She attended for a medication review.'):
            self.assertHeld('The patient presents with chest pain. ' + later,
                            {'Chief complaint': ['The patient presents with chest pain.']})

    def test_R3_1_a_status_verb_in_a_reported_clause_changes_the_answer(self):
        for notes, label, quote in (
                ('The patient takes metformin 500 mg twice daily.\nThe diabetes nurse reports the tablets were stopped in '
                 'June.', 'Medications', 'The patient takes metformin'),
                ('The patient takes warfarin 5 mg daily.\nPharmacy confirmed the anticoagulant stopped.', 'Medications',
                 'The patient takes warfarin'),
                ('The patient takes warfarin 5 mg daily.\nPharmacy confirmed anticoagulation was never started.',
                 'Medications', 'The patient takes warfarin'),
                ('The patient presents with headache.\nShe takes amitriptyline 10 mg at night.\nHer GP says the tablets '
                 'were never collected.', 'Medications', 'She takes amitriptyline'),
                ('The patient has asthma.\nSpirometry confirmed the diagnosis was excluded.', 'Past medical history',
                 'The patient has asthma.'),
                ('The patient reports chest pain on exertion.\nHer husband says the symptoms never happened.',
                 'History of present illness', 'The patient reports chest pain'),
                ('The patient reports chest pain on exertion.\nThe cardiologist thinks the episodes were probably reflux.',
                 'History of present illness', 'The patient reports chest pain'),
                ('The patient takes warfarin 5 mg daily. Discharge summary reviewed, anticoagulation discontinued.',
                 'Medications', 'The patient takes warfarin')):
            self.assertHeld(notes, {label: [quote]})


    def test_a_later_plain_labelled_value_naming_the_question_or_repeating_the_answer_holds_it(self):
        """Kept from the same-day change (hold-only): R3-1 lets another question's plain labelled value pass, but not one
        that names this question or repeats this unlabelled answer's word (frozen N13/N16 entries, leaks before it)."""
        self.assertHeld('The patient is allergic to penicillin.\nAllergies: none.',
                        {'Allergies': ['The patient is allergic to penicillin.']}, form='n16-mood-and-allergies')
        self.assertHeld('The patient is suicidal.\nSuicidal ideation: none.',
                        {'Suicidal ideation': ['The patient is suicidal.']}, form='n13-risk-and-medication')
        # ⚠️ Round 3: the kept hold is what the round-3 brief keeps - a labelled line NAMING the question, or a colon-
        # labelled line with the answer's core word. A 'Label is' sentence repeating a word is debaefd9's positional
        # reading again (supported there and here: its block is independent).
        self.assertSupported('The patient takes ibuprofen as needed. Assessment is ibuprofen overuse.',
                             {'Medications': ['The patient takes ibuprofen as needed.']})
        self.assertHeld('The patient takes ibuprofen as needed. Medications: ibuprofen.',
                        {'Medications': ['The patient takes ibuprofen as needed.']})
        self.assertSupported('The patient takes aspirin.\nAllergies: none.', {'Medications': ['The patient takes aspirin.']})


    def test_a_labelled_lines_label_is_not_who_it_is_about(self):
        """The actor reading reads only a labelled line's VALUE for persons: a label naming a role ('Carer') is the
        question's name. (Not red on 0350b4ea for this label; it pins the repair's own reading, mutation R18.)"""
        from .test_v3_ordinary_notes import field
        fields = [field('v3_1', 'Carer'), field('v3_2', 'Chief complaint')]
        out = adopt('Carer: none.', {'Carer': ['Carer: none.']}, fields)
        self.assertEqual((out['Carer']['status'], out['Carer']['text']), ('supported', 'none.'))
        # ... while a person in the VALUE is read as before (R3-2).
        out = adopt('Carer: her daughter visits daily.', {'Carer': ['Carer: her daughter visits daily.']}, fields)
        self.assertNotEqual(out['Carer']['status'], 'supported')


class NoteWideFindings(RepairTestCase):
    def test_F4_a_later_line_restating_a_repaired_value_is_in_the_repairs_reach(self):
        self.assertHeld('Patient presents with chest pain, sorry, I mean abdominal pain.\nChief complaint: chest pain.',
                        {'Chief complaint': ['Chief complaint: chest pain.']})
        for gap in ('\n', '\n\n'):
            self.assertHeld('The patient takes warfarin 5 mg daily. Sorry, I mean 3 mg.' + gap +
                            'Medications: warfarin 5 mg daily.', {'Medications': ['Medications: warfarin 5 mg daily.']})
        self.assertHeld('The patient takes warfarin. Scratch that.\nMedications: warfarin.',
                        {'Medications': ['Medications: warfarin.']})
        self.assertHeld('Allergies: penicillin. Sorry, I mean amoxicillin.\nThe patient is allergic to penicillin.',
                        {'Allergies': ['The patient is allergic to penicillin.']}, form='n11-n12-correction')
        # A later labelled line of the SAME question, or one repeating the repaired words, stays in its reach too.
        self.assertHeld('Allergies: penicillin.\nSorry, I mean amoxicillin.\nMedications: penicillin V.',
                        {'Medications': ['Medications: penicillin V.']})
        # The same question written again after its repair stays in reach even when its label has no content word
        # ('other' is a stop word) and the value repeats (so no 'two answers' rule fires either).
        from .test_v3_ordinary_notes import field
        other = [field('v3_1', 'Other'), field('v3_2', 'Chief complaint')]
        notes = 'Other: none.\nSorry, I mean none.\nOther: none.'
        asked, context, v3_fields = g.v3_generation_fields(other)
        units = g.source_units(notes, asked, context_labels=context)[0]
        selections = g.UnitSelections(fields=[g.UnitSelection(key='v3_1', unit_ids=[units[-1]['id']], conflict=False),
                                              g.UnitSelection(key='v3_2', unit_ids=[], conflict=False)])
        answers = g.validate_selections(notes, asked, selections, context_labels=context,
                                        evidence_contract=g.TAB_CONTRACT)
        self.assertNotEqual(g.v3_adopted(v3_fields, answers, notes, asked, context)['v3_1']['status'], 'supported')
        # ⚠️ Round 3: G-H WITHDRAWN (RR3, RR2-1..RR2-3). Every repair is note-wide again, as on debaefd9.
        self.assertHeld('Patient presents with a rash on both forearms.\nAllergies: penicillin. Sorry, I mean '
                        'amoxicillin.\nSmoker: No.', {'Smoker': ['Smoker: No.']}, form='n11-n12-correction')

    def test_F9_a_correction_in_another_paragraph_keeps_the_self_reference_coupled(self):
        for later in ('Wrong side: it is the left knee.', 'The left knee is affected, not the right.',
                      'Amended: left knee pain.', 'Left knee: this is the painful side.'):
            self.assertHeld('The patient has right knee pain.\n\n' + later,
                            {'Right knee': ['The patient has right knee pain.']}, form='n09-knee-pair')
        self.assertHeld('The patient has right knee pain.\n\nDictation error, left knee.',
                        {'Right knee': ['The patient has right knee pain.']}, form='n08-knee-and-findings')
        # ⚠️ Round 3: G-D WITHDRAWN (RR1, RR2-4). The sentence alone stays coupled to the field it names, as on debaefd9.
        self.assertHeld('The patient has right knee pain.', {'Right knee': ['The patient has right knee pain.']},
                        form='n09-knee-pair')

    def test_R1_9_a_state_bounded_by_a_past_clause_is_not_a_complete_current_statement(self):
        for notes, quote in (
                ('The patient attended the clinic every week until the order expired.', None),
                ('The patient attended the clinic every week before the order lapsed.', None),
                ('The patient is under a CTO. She attended the clinic every week until the order expired.',
                 'She attended the clinic every week until the order expired.')):
            self.assertHeld(notes, {'Clinic attendance': [quote or notes]}, form='n03-order-question')
        # A past clause bounded by a present one, and a present clause bounded by a past one, are not proven current.
        self.assertHeld('The patient slept poorly because the knee hurts.',
                        {'History of present illness': ['The patient slept poorly because the knee hurts.']})
        self.assertHeld('The patient attends the clinic every week until the order expired.',
                        {'Clinic attendance': ['The patient attends the clinic every week until the order expired.']},
                        form='n03-order-question')
        self.assertSupported('The patient attended the clinic every week.',
                             {'Clinic attendance': ['The patient attended the clinic every week.']},
                             form='n03-order-question')
        # ⚠️ Round 3: G-E WITHDRAWN (RR2, RR2-7), and a bounding clause holds (PRE-3): both clauses present is not current.
        self.assertHeld('The patient sees zigzag lines before the headache begins.',
                        {'History of present illness': ['The patient sees zigzag lines before the headache begins.']})


class ReplaySetFindings(RepairTestCase):
    N04 = ('45-year-old man presents with right knee pain for three weeks after a fall. He has hypertension and takes '
           'lisinopril 10 mg daily. Allergies: penicillin. Smoker: No. On examination there is a small effusion and '
           'medial joint line tenderness. Assessment is a probable medial meniscus tear. Plan is an MRI of the right knee '
           'and physiotherapy referral.')

    def test_F1_set2_the_combined_statement_in_one_specific_question_is_held(self):
        for label in ('Past medical history', 'Medications'):
            self.assertHeld(self.N04, {label: ['He has hypertension and takes lisinopril']})

    def test_F5_set2_forbidden_model_dependent_selections_are_held(self):
        self.assertHeld('The patient is subject to a Community Treatment Order (CTO). She attends the clinic every week.',
                        {'Clinic attendance': ['The patient is subject to a Community Treatment Order (CTO).']},
                        form='n03-order-question')
        n01 = ('This is a 30-year-old female seen for headaches. The headaches started two months ago and are worse in '
               'the morning. She denies visual changes, nausea, or weakness. She takes ibuprofen as needed. No known '
               'drug allergies. She is a nonsmoker. Neurological examination is normal. Assessment is tension-type '
               'headache. Plan is to start amitriptyline 10 mg at night. She will follow up in six weeks.')
        self.assertHeld(n01, {'History of present illness': ['She denies visual changes, nausea, or weakness.']})

    def test_F2_set2_withdrawn_a_person_presented_by_age_or_by_name_is_read_like_any_person(self):
        """⚠️ Round 3: F2-set2 WITHDRAWN (RR9: an appositive naming the presented person as the patient's relative was
        released). Only the deterministic age grammar (`AGE_PATIENT_PRESENTATION`) presents the patient; these shapes are
        held again, as on 0350b4ea (an over-hold: debaefd9 supported them only because it had no actor reader)."""
        for notes, label in (('A 45-year-old man presents with cough.', 'Chief complaint'),
                             ('Mrs Jones presents with chest pain.', 'Chief complaint'),
                             ('This is a 60-year-old woman here for follow up of her diabetes.', 'Chief complaint'),
                             ('This is a 60-year-old woman here for follow up of her diabetes.', 'History of present illness'),
                             ('Pleasant 70-year-old gentleman seen for review of his COPD.', 'Chief complaint'),
                             ('She is a 60-year-old woman who takes metformin.', 'Medications'),
                             ("A 70-year-old woman, the patient's mother, presents with chest pain.", 'Chief complaint'),
                             ('A 12-year-old boy presents with his mother, who has chest pain.', 'Chief complaint')):
            self.assertHeld(notes, {label: [notes]})
        # The deterministic grammar still presents the patient ...
        self.assertSupported('45-year-old man presents with cough.', {'Chief complaint': ['45-year-old man presents with cough.']})
        # ... unless a relative clause gives another person something (RR9).
        self.assertHeld('12-year-old boy presents with his mother, who has chest pain.',
                        {'Chief complaint': ['12-year-old boy presents with his mother, who has chest pain.']})
        # A presented patient after another person's line in the same paragraph may be that person (unchanged), and a
        # named person who is not presenting cannot be shown to be the patient (a stated over-hold).
        self.assertHeld('Her brother was seen yesterday. A 45-year-old man presents with cough.',
                        {'Chief complaint': ['A 45-year-old man presents with cough.']})
        self.assertHeld('The patient lives with Jane.\n\nMrs Jones presents with chest pain.',
                        {'Chief complaint': ['Mrs Jones presents with chest pain.']})
        self.assertHeld('Mr Smith takes aspirin 75 mg daily.', {'Medications': ['Mr Smith takes aspirin 75 mg daily.']})

    def test_F3_set2_a_unit_held_as_another_persons_names_that_reason(self):
        out = self.assertHeld('Her husband takes warfarin.', {'Medications': ['Her husband takes warfarin.']})
        candidate = out['Medications']['held_candidate']
        self.assertEqual(candidate['reason'], g.V3_OTHER_PERSON_REASON)
        self.assertTrue(all(entry.get('other_person') for entry in candidate['context']))
        # Beside another cause the general reason stays (it names a family history among the causes).
        out = self.assertHeld('The patient presents with bruising. Her husband takes warfarin.',
                              {'Medications': ['Her husband takes warfarin.']})
        self.assertEqual(out['Medications']['held_candidate']['reason'], g.HELD_REASON)


class CostFindings(SimpleTestCase):
    def test_R3_3_the_neighbour_rule_does_no_pairwise_work(self):
        """One paragraph of N unrelated units, every one selected for one question: the rule reads each unit's own
        neighbours once. The link reading of 0350b4ea compared every selected unit with every later one, each comparison
        running the correction/pointer/scope readers again (N*(N-1)/2 comparisons, under the row lock)."""
        fields = fields_of('r1-11')
        words = ('ambrosis bexalitis cedromia dalvenosis embrusia fenomalgia garnitosis hazelopathy indrosis '
                 'juniperitis kelpomia lilacosis mapleuria nutmegitis olivaria pepperosis quartzemia rowanitis '
                 'sagelosis thymeuria').split()                     # no two units share a word but 'patient'
        notes = ' '.join('The patient has %s.' % word for word in words)
        reading = g.governance_for(notes, fields)[11]['preceding']
        self.assertEqual(len(reading['units']), len(words))
        evidence = [{k: u[k] for k in ('quote', 'start', 'end')} for u in reading['units']]
        with patch.object(g, 'safety_readings', wraps=g.safety_readings) as readings:
            g.v3_preceding_warnings(reading, 'Medications', evidence)
        self.assertLessEqual(readings.call_count, 2 * len(words))

    def test_R3_4_the_note_is_parsed_once(self):
        """⚠️ Round 3: G-H (the bare repair reader) is WITHDRAWN; the actor reader still parses the note in ONE call."""
        fields = fields_of('r1-11')
        notes = '\n'.join('Allergies: drug%d. Sorry, I mean drug%d.' % (n, n + 1) for n in range(12))
        with patch.object(v3_syntax, 'docs', wraps=v3_syntax.docs) as docs:
            governance = g.governance_for(notes, fields)
        self.assertEqual(docs.call_count, 1)
        self.assertNotIn('bare_repairs', governance[11])
