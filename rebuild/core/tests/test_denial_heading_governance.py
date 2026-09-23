"""A heading governs the lines it introduces; a finding written under it is never a ready answer.

⚠️ THE DEFECT THIS PINS, REPRODUCED ON 02c29f99 BEFORE ANY CHANGE. With a *Review of systems* question on
the form, the notes

    Review of systems: negative for the following:
    Symptoms: chest pain

came back with Symptoms SUPPORTED as "chest pain": pre-filled, needing only the review tick, and the
finalized export said the patient had chest pain. The heading parsed as the Review-of-systems answer, so
every line looked like a self-contained labelled answer (`scoped_lines`), and nothing downstream (save,
finalize, export) re-checks a supported answer. `Family history: the following conditions:` above
`Diabetes: yes` attributed the family's diabetes to the patient the same way.

The EXPECTED answers below were written from what each note says clinically, before the repair existed.
They do not depend on how the repair works. Everything here is offline: fixture generation or
provider-SHAPED selections built in the test (not retained provider output), and no provider call.
"""
from io import BytesIO
import json

from django.test import TestCase
from docx import Document

from core import generation
from core.generation import Selection, Selections, validate_selections
from core.jobs import run_one
from core.models import Encounter
from core.tests.test_workflow import DocumentWorkflow

FIXTURE = {'mode': 'fixture', 'prompt_version': 'legacy-offline-test'}
HEADING = 'Review of systems: negative for the following:'


def form(*labels):
    return [{'key': f'q{index}', 'label': label, 'kind': 'text', 'locator': {'cell': index}}
            for index, label in enumerate(labels)]


def fixture_answers(labels, notes):
    """What the offline generator returns, by question label."""
    fields = form(*labels)
    answers = generation.generate(notes, fields, FIXTURE)[0]
    return {field['label']: answers[field['key']] for field in fields}


def provider_answers(labels, notes, picks):
    """A provider-SHAPED response (built here, not retained): each question quotes its own full line,
    `conflict: false`, which is what the retained live WM response does for every one of its 90 answers."""
    fields = form(*labels)
    chosen = Selections(fields=[Selection(key=field['key'], quotes=picks.get(field['label'], []), conflict=False)
                                for field in fields])
    answers = validate_selections(notes, fields, chosen, evidence_contract='legacy')
    return {field['label']: answers[field['key']] for field in fields}


class ExpectationsMixin:
    """The two outcomes a clinician can be shown, stated independently of the implementation."""

    def assert_ready(self, answer, text):
        self.assertEqual((answer['status'], answer['text']), ('supported', text))

    def assert_needs_decision(self, answer, candidate, context):
        """Not a ready answer, not a one-click offer, and the candidate is kept with what governs it."""
        self.assertEqual(answer['status'], 'conflict', answer)
        self.assertEqual(answer['text'], '', 'a governed finding is never pre-filled')
        self.assertNotIn('suggestion', answer, 'a governed finding is never offered for one click')
        held = answer.get('held_candidate')
        self.assertIsNotNone(held, 'the candidate must be preserved for the clinician, not discarded')
        self.assertEqual(held['text'], candidate)
        quotes = [entry.get('quote', '') for entry in answer['evidence'] + held['evidence'] + held.get('context', [])]
        self.assertTrue(any(context in quote for quote in quotes),
                        f'the governing line {context!r} must be shown with the candidate: {quotes}')


class TheReproducedDefect(ExpectationsMixin, TestCase):
    """E1-E8 of the milestone brief, on the offline generator and on provider-shaped selections."""

    def both(self, labels, notes, picks):
        yield 'fixture', fixture_answers(labels, notes)
        yield 'provider-shaped', provider_answers(labels, notes, picks)

    def test_e1_a_mapped_denial_heading_never_prefills_the_finding_below_it(self):
        notes = HEADING + '\nSymptoms: chest pain'
        for path, answers in self.both(['Review of systems', 'Symptoms'], notes,
                                       {'Review of systems': [HEADING], 'Symptoms': ['Symptoms: chest pain']}):
            with self.subTest(path=path):
                self.assert_needs_decision(answers['Symptoms'], 'chest pain', HEADING)
                self.assert_needs_decision(answers['Review of systems'], 'negative for the following:', HEADING)
                # The stored evidence is the answer's OWN line; the governing line travels only as context.
                self.assertNotIn(HEADING, [entry['quote'] for entry in answers['Symptoms']['evidence']])

    def test_e2_an_ordinary_labelled_line_before_the_heading_stays_ready_and_does_not_hide_it(self):
        notes = 'Indication: screening colonoscopy\n' + HEADING + '\nSymptoms: chest pain'
        for path, answers in self.both(['Indication', 'Review of systems', 'Symptoms'], notes,
                                       {'Indication': ['Indication: screening colonoscopy'],
                                        'Review of systems': [HEADING], 'Symptoms': ['Symptoms: chest pain']}):
            with self.subTest(path=path):
                self.assert_ready(answers['Indication'], 'screening colonoscopy')
                self.assert_needs_decision(answers['Symptoms'], 'chest pain', HEADING)

    def test_e3_an_unmapped_heading_keeps_the_candidate_instead_of_discarding_it(self):
        notes = 'Indication: screening colonoscopy\nROS: negative for the following:\nSymptoms: chest pain'
        for path, answers in self.both(['Indication', 'Symptoms'], notes,
                                       {'Indication': ['Indication: screening colonoscopy'],
                                        'Symptoms': ['Symptoms: chest pain']}):
            with self.subTest(path=path):
                self.assert_needs_decision(answers['Symptoms'], 'chest pain', 'ROS: negative for the following:')
                # The existing whole-note rule for an unlabelled line is NOT relaxed: Indication stays a
                # decision too, but its candidate is kept rather than lost.
                self.assertEqual(answers['Indication']['status'], 'conflict')
                self.assertEqual(answers['Indication'].get('held_candidate', {}).get('text'), 'screening colonoscopy')

    def test_e4_mixed_findings_what_precedes_the_heading_stays_ready_what_follows_needs_a_decision(self):
        """⚠️ REVISED BEFORE IMPLEMENTATION, after the design was refuted. The first expectation kept
        Examination and Plan ready because a blank line separated them. A blank line does not end a list:
        pasted notes separate items with them, and the app itself joins note segments with one, so
        `Dyspnea: yes` after a blank line under the same heading would have been pre-filled. Everything
        after a heading needs a decision; what comes before it does not."""
        notes = ('Chief complaint: right calf pain for three weeks\n' + HEADING + '\nSymptoms: chest pain, dyspnea\n\n'
                 'Examination: mild right ankle swelling\nPlan: duplex ultrasound')
        labels = ['Chief complaint', 'Review of systems', 'Symptoms', 'Examination', 'Plan']
        picks = {'Chief complaint': ['Chief complaint: right calf pain for three weeks'], 'Review of systems': [HEADING],
                 'Symptoms': ['Symptoms: chest pain, dyspnea'], 'Examination': ['Examination: mild right ankle swelling'],
                 'Plan': ['Plan: duplex ultrasound']}
        for path, answers in self.both(labels, notes, picks):
            with self.subTest(path=path):
                self.assert_ready(answers['Chief complaint'], 'right calf pain for three weeks')
                self.assert_needs_decision(answers['Symptoms'], 'chest pain, dyspnea', HEADING)
                self.assert_needs_decision(answers['Examination'], 'mild right ankle swelling', HEADING)
                self.assert_needs_decision(answers['Plan'], 'duplex ultrasound', HEADING)

    def test_e5b_items_separated_by_blank_lines_are_all_governed(self):
        notes = HEADING + '\n\nChest pain: yes\n\nDyspnea: yes\n\nPalpitations: yes'
        labels = ['Review of systems', 'Chest pain', 'Dyspnea', 'Palpitations']
        for path, answers in self.both(labels, notes, {'Review of systems': [HEADING], 'Chest pain': ['Chest pain: yes'],
                                                       'Dyspnea': ['Dyspnea: yes'], 'Palpitations': ['Palpitations: yes']}):
            with self.subTest(path=path):
                for label in ('Chest pain', 'Dyspnea', 'Palpitations'):
                    self.assert_needs_decision(answers[label], 'yes', HEADING)

    def test_e5_a_blank_line_after_the_heading_does_not_release_the_list_below_it(self):
        notes = HEADING + '\n\nSymptoms: chest pain'
        for path, answers in self.both(['Review of systems', 'Symptoms'], notes,
                                       {'Review of systems': [HEADING], 'Symptoms': ['Symptoms: chest pain']}):
            with self.subTest(path=path):
                self.assert_needs_decision(answers['Symptoms'], 'chest pain', HEADING)

    def test_e6_a_heading_with_nothing_after_it_governs_the_lines_above_it(self):
        closing = 'Review of systems: all of the above denied:'
        notes = 'Symptoms: chest pain\n' + closing
        for path, answers in self.both(['Symptoms', 'Review of systems'], notes,
                                       {'Symptoms': ['Symptoms: chest pain'], 'Review of systems': [closing]}):
            with self.subTest(path=path):
                self.assert_needs_decision(answers['Symptoms'], 'chest pain', closing)

    def test_e6b_a_closing_heading_governs_every_earlier_line_even_across_a_blank_line(self):
        closing = 'Review of systems: all of the above denied:'
        notes = 'Chest pain: yes\nDyspnea: yes\n\n' + closing
        labels = ['Chest pain', 'Dyspnea', 'Review of systems']
        for path, answers in self.both(labels, notes, {'Chest pain': ['Chest pain: yes'], 'Dyspnea': ['Dyspnea: yes'],
                                                       'Review of systems': [closing]}):
            with self.subTest(path=path):
                self.assert_needs_decision(answers['Chest pain'], 'yes', closing)
                self.assert_needs_decision(answers['Dyspnea'], 'yes', closing)

    def test_e6d_a_closing_heading_governs_what_precedes_it_even_without_a_pointer_word(self):
        """Structure alone: a heading with nothing after it can only introduce what came before."""
        closing = 'Review of systems: patient denies:'
        notes = 'Chest pain: yes\nDyspnea: yes\n' + closing
        labels = ['Chest pain', 'Dyspnea', 'Review of systems']
        for path, answers in self.both(labels, notes, {'Chest pain': ['Chest pain: yes'], 'Dyspnea': ['Dyspnea: yes'],
                                                       'Review of systems': [closing]}):
            with self.subTest(path=path):
                self.assert_needs_decision(answers['Chest pain'], 'yes', closing)
                self.assert_needs_decision(answers['Dyspnea'], 'yes', closing)

    def test_e6c_a_backward_heading_with_lines_after_it_governs_both_ways(self):
        closing = 'Review of systems: all of the above denied:'
        notes = 'Symptoms: chest pain, dyspnea\n' + closing + '\n\nExamination: mild right ankle swelling'
        labels = ['Symptoms', 'Review of systems', 'Examination']
        for path, answers in self.both(labels, notes, {'Symptoms': ['Symptoms: chest pain, dyspnea'],
                                                       'Review of systems': [closing],
                                                       'Examination': ['Examination: mild right ankle swelling']}):
            with self.subTest(path=path):
                self.assert_needs_decision(answers['Symptoms'], 'chest pain, dyspnea', closing)
                self.assert_needs_decision(answers['Examination'], 'mild right ankle swelling', closing)

    def test_e1b_a_heading_the_vocabulary_does_not_know_still_governs(self):
        """`none` and `absence` are not denial words the gate knows, and `Family hx` is not a reframer it
        knows. Structure decides here, not words."""
        for heading, labels in (('Review of systems: none of the following:', ['Review of systems', 'Symptoms']),
                                ('Review of systems: absence of the following:', ['Review of systems', 'Symptoms']),
                                ('Family hx: the following conditions:', ['Family hx', 'Symptoms'])):
            notes = heading + '\nSymptoms: chest pain'
            for path, answers in self.both(labels, notes, {labels[0]: [heading], 'Symptoms': ['Symptoms: chest pain']}):
                with self.subTest(heading=heading, path=path):
                    self.assert_needs_decision(answers['Symptoms'], 'chest pain', heading)

    def test_e3b_an_unmapped_heading_the_vocabulary_does_not_know_offers_nothing(self):
        """Before the repair this offered `chest pain` for one click: `none` is not a denial word."""
        for heading in ('ROS: none of the following:', 'Family hx: the following conditions:', 'Mother has the following:'):
            notes = 'Indication: screening colonoscopy\n' + heading + '\nSymptoms: chest pain'
            for path, answers in self.both(['Indication', 'Symptoms'], notes,
                                           {'Indication': ['Indication: screening colonoscopy'], 'Symptoms': ['Symptoms: chest pain']}):
                with self.subTest(heading=heading, path=path):
                    self.assert_needs_decision(answers['Symptoms'], 'chest pain', heading)

    def test_e9_a_governing_sentence_without_a_colon_is_read_where_it_points(self):
        """The original defect with a full stop instead of a colon. Only the existing vocabularies, anchored
        on where the pointer sits: the sentence ENDS by pointing forward or back."""
        cases = (
            ('Review of systems: negative for the following symptoms.', ['Symptoms: chest pain'], 'forward'),
            ('Review of systems: patient denies the following', ['Chest pain: yes', 'Dyspnea: yes'], 'forward'),
            ('Review of systems: negative for the symptoms below.', ['Symptoms: chest pain'], 'forward'),
            ('Family history: mother had the following', ['Diabetes: yes', 'Hypertension: yes'], 'forward'),
            # Second pass: read per SENTENCE, not per line.
            ('Review of systems: Patient denies the following. All other systems negative.', ['Symptoms: chest pain'], 'forward'),
            # Second pass: an invisible character inside the pointer word does not hide it.
            ('Review of systems: negative for the fol\u00adlowing symptoms.', ['Symptoms: chest pain'], 'forward'),
            ('Review of systems: patient denies the follow\u200bing', ['Symptoms: chest pain'], 'forward'),
        )
        for line, items, direction in cases:
            notes = '\n'.join([line] + items) if direction == 'forward' else '\n'.join(items + [line])
            labels = [line.split(':')[0]] + [item.split(':')[0] for item in items]
            picks = {line.split(':')[0]: [line], **{item.split(':')[0]: [item] for item in items}}
            for path, answers in self.both(labels, notes, picks):
                with self.subTest(line=line, path=path):
                    for item in items:
                        label, value = item.split(': ', 1)
                        # The governing line is shown from its start through the pointer's sentence.
                        self.assert_needs_decision(answers[label], value, line.split(' All other')[0])

    def test_e8b_a_correction_written_as_another_questions_answer_governs_what_came_before(self):
        for labels, correction in ((['Symptoms', 'Addendum'], 'Addendum: Correction: the patient does report severe crushing chest pain.'),
                                   (['Symptoms', 'Comments'], 'Comments: correction, patient reports severe chest pain')):
            notes = 'Symptoms: no chest pain\n' + correction
            for path, answers in self.both(labels, notes, {'Symptoms': ['Symptoms: no chest pain'], labels[1]: [correction]}):
                with self.subTest(correction=correction, path=path):
                    self.assert_needs_decision(answers['Symptoms'], 'no chest pain', correction)

    def test_e7_an_attribution_heading_never_gives_the_patient_the_familys_finding(self):
        heading = 'Family history: the following conditions:'
        notes = heading + '\nDiabetes: yes'
        for path, answers in self.both(['Family history', 'Diabetes'], notes,
                                       {'Family history': [heading], 'Diabetes': ['Diabetes: yes']}):
            with self.subTest(path=path):
                self.assert_needs_decision(answers['Diabetes'], 'yes', heading)

    def test_e8_a_line_initial_correction_keeps_the_candidate_without_offering_it(self):
        notes = 'Symptoms: no chest pain\nCorrection: severe crushing chest pain.'
        for path, answers in self.both(['Symptoms'], notes, {'Symptoms': ['Symptoms: no chest pain']}):
            with self.subTest(path=path):
                self.assert_needs_decision(answers['Symptoms'], 'no chest pain', 'Correction: severe crushing chest pain.')


class ValidAnswersStillWork(ExpectationsMixin, TestCase):
    """POSITIVE CONTROLS: without them, every assertion above could pass by blanking everything."""

    def test_p1_a_fully_labelled_affirmative_note_is_ready_unchanged(self):
        notes = ('Symptoms: intermittent right calf ache\nExamination: mild right ankle swelling; no skin changes\n'
                 'Plan: duplex ultrasound of both legs')
        answers = fixture_answers(['Symptoms', 'Examination', 'Plan'], notes)
        self.assert_ready(answers['Symptoms'], 'intermittent right calf ache')
        self.assert_ready(answers['Examination'], 'mild right ankle swelling; no skin changes')
        self.assert_ready(answers['Plan'], 'duplex ultrasound of both legs')

    def test_p2_a_denial_written_as_the_answer_itself_is_ready(self):
        notes = 'Symptoms: no chest pain\nReview of systems: negative for chest pain and dyspnea'
        answers = fixture_answers(['Symptoms', 'Review of systems'], notes)
        self.assert_ready(answers['Symptoms'], 'no chest pain')
        self.assert_ready(answers['Review of systems'], 'negative for chest pain and dyspnea')

    def test_p3_a_pointer_word_inside_a_sentence_governs_nothing(self):
        """Anatomy and time use the same words mid-sentence; only a sentence that ENDS on a pointer points."""
        notes = ('Findings: No reflux below the knee.\nAbdomen: Soft, no tenderness above the umbilicus.\n'
                 'Complications: No bleeding following polypectomy.\nDischarge: No driving for the following 24 hours.\n'
                 'Impression: Normal venous study.')
        answers = fixture_answers(['Findings', 'Abdomen', 'Complications', 'Discharge', 'Impression'], notes)
        self.assert_ready(answers['Findings'], 'No reflux below the knee.')
        self.assert_ready(answers['Abdomen'], 'Soft, no tenderness above the umbilicus.')
        self.assert_ready(answers['Complications'], 'No bleeding following polypectomy.')
        self.assert_ready(answers['Discharge'], 'No driving for the following 24 hours.')
        self.assert_ready(answers['Impression'], 'Normal venous study.')

    def test_p3b_a_sentence_referring_back_governs_nothing(self):
        """⚠️ SECOND PASS: the backward sentence arm is WITHDRAWN. Its common case is the standard ROS closing line
        (`…negative except as noted above.`), which would have blanked the very positives it names, and a
        reference back rarely negates what it refers to (`No DVT in the veins listed above.`). A backward
        reach stays STRUCTURAL only: a closing heading, or a heading that names what precedes it."""
        notes = ('Chief complaint: right calf pain\nFindings: No reflux below the knee.\nImpression: No DVT in the veins listed above.\n'
                 'Review of systems: All other systems reviewed and negative except as noted above.\nPlan: repeat in one year')
        answers = fixture_answers(['Chief complaint', 'Findings', 'Impression', 'Review of systems', 'Plan'], notes)
        for label, text in (('Chief complaint', 'right calf pain'), ('Findings', 'No reflux below the knee.'),
                            ('Impression', 'No DVT in the veins listed above.'), ('Plan', 'repeat in one year')):
            self.assert_ready(answers[label], text)

    def test_p3c_the_documented_cost_a_sentence_ending_on_a_forward_pointer_governs_what_follows(self):
        """⚠️ THE TRADE, PINNED SO IT IS NOT MISTAKEN FOR A BUG. `…no reflux at mid-thigh or below.` ends by
        pointing forward exactly as `…negative for the symptoms below.` does; without grammar the two cannot
        be told apart. The sentence itself stays its question's answer; the answers after it need a decision."""
        notes = 'Right GSV: Reflux at the SFJ, 1200 ms; no reflux at mid-thigh or below.\nImpression: Right GSV insufficiency'
        answers = fixture_answers(['Right GSV', 'Impression'], notes)
        self.assert_ready(answers['Right GSV'], 'Reflux at the SFJ, 1200 ms; no reflux at mid-thigh or below.')
        self.assert_needs_decision(answers['Impression'], 'Right GSV insufficiency',
                                   'Right GSV: Reflux at the SFJ, 1200 ms; no reflux at mid-thigh or below.')

    def test_p5_a_reference_back_or_mid_sentence_changes_nothing(self):
        """A sentence that refers back is not read, and a pointer inside a sentence governs nothing."""
        notes = ('Findings: Clinical correlation with the above findings is required.\nPlan: see the instructions below each '
                 'heading of the leaflet\nFollow-up: in two weeks')
        answers = fixture_answers(['Findings', 'Plan', 'Follow-up'], notes)
        self.assert_ready(answers['Findings'], 'Clinical correlation with the above findings is required.')
        self.assert_ready(answers['Plan'], 'see the instructions below each heading of the leaflet')
        self.assert_ready(answers['Follow-up'], 'in two weeks')

    def test_p5b_the_documented_cost_a_sentence_ending_on_a_pointer_governs_whatever_its_words(self):
        """⚠️ THE TRADE, PINNED (third refutation pass). Reading the words before the pointer (a denial, an `except`,
        a family word) was refuted three ways: `except` in an earlier clause released a denied list, a denial in
        the label or an earlier sentence was missed, and `Her mother had the following.` carries no word the
        vocabulary knows. So position alone decides, and these answers after the pointer need a decision too:
        a reference (`see the instructions below`), an exception list (`negative except as noted below`), and a
        time (`until the following day`)."""
        for pointer in ('Plan: see the instructions below', 'Review of systems: negative except as noted below.',
                        'Review of systems: Negative with the exception of the following.',
                        'Discharge instructions: Do not drive or operate machinery until the following day.',
                        'No. of polyps: 2, described below'):
            notes = pointer + '\nFollow-up: in two weeks'
            label = pointer.split(':')[0]
            with self.subTest(pointer=pointer):
                answers = fixture_answers([label, 'Follow-up'], notes)
                self.assert_ready(answers[label], pointer.split(': ', 1)[1])
                self.assert_needs_decision(answers['Follow-up'], 'in two weeks', pointer)

    def test_p4_a_colon_inside_a_value_is_not_a_heading(self):
        notes = 'Plan: review at 10:30\nFollow-up: in 2 weeks: sooner if worse'
        answers = fixture_answers(['Plan', 'Follow-up'], notes)
        self.assert_ready(answers['Plan'], 'review at 10:30')
        self.assert_ready(answers['Follow-up'], 'in 2 weeks: sooner if worse')


def tab_answers(labels, notes):
    fields = [{'key': f'q{index}', 'label': label, 'kind': 'text', 'locator': {'cell': index, 'tab_form': {'version': 1}}}
              for index, label in enumerate(labels)]
    answers = generation.generate(notes, fields, {'mode': 'fixture', 'prompt_version': generation.CURRENT_PROMPT_VERSION})[0]
    return fields, {field['label']: answers[field['key']] for field in fields}


class WhatTheSecondPassFound(ExpectationsMixin, TestCase):
    """Refutation of the finished diff, second pass: each is an input a lens demonstrated, with its expectation."""

    def test_a_correction_is_an_erratum_not_the_clinical_noun(self):
        """`Correction of iron deficiency` and `Correction scale` are treatments; only `Correction:`/`correction,`
        /`Correction —` revise what came before."""
        for notes, labels in (
                ('Indication: Iron deficiency anemia\nRecommendation: Correction of iron deficiency with oral iron',
                 ['Indication', 'Recommendation']),
                ('Medications: Lisinopril 10 mg daily\nInsulin: Correction scale with meals per protocol', ['Medications', 'Insulin']),
                # Third pass: a hyphen attached to the word is the treatment too.
                ('Medications: Lisinopril 10 mg daily\nInsulin: Correction-scale lispro with meals per protocol', ['Medications', 'Insulin']),
                ('Medications: Lisinopril 10 mg daily\nInsulin: Correction-dose insulin lispro before meals', ['Medications', 'Insulin'])):
            with self.subTest(notes=notes):
                answers = fixture_answers(labels, notes)
                self.assertEqual(answers[labels[0]]['status'], 'supported', answers[labels[0]])

    def test_an_erratum_behind_an_invisible_character_or_an_en_dash_bullet_still_governs(self):
        notes = 'Symptoms: no chest pain\nComments: \u200bCorrection, patient reports severe crushing chest pain.'
        self.assert_needs_decision(fixture_answers(['Symptoms', 'Comments'], notes)['Symptoms'], 'no chest pain',
                                   'Comments: \u200bCorrection, patient reports severe crushing chest pain.')
        # Inside the word, too: only the reading with invisible characters removed sees it.
        notes = 'Symptoms: no chest pain\nComments: Correc\u00adtion, patient reports severe crushing chest pain.'
        self.assert_needs_decision(fixture_answers(['Symptoms', 'Comments'], notes)['Symptoms'], 'no chest pain',
                                   'Comments: Correc\u00adtion, patient reports severe crushing chest pain.')
        notes = 'Indication: screening colonoscopy\nSymptoms: no chest pain\n\u2013 Correction: patient reports severe crushing chest pain.'
        answer = fixture_answers(['Indication', 'Symptoms'], notes)['Symptoms']
        self.assertEqual(answer['status'], 'conflict'); self.assertNotIn('suggestion', answer)
        self.assertIn('\u2013 Correction: patient reports severe crushing chest pain.',
                      [entry.get('quote') for entry in answer['held_candidate']['context']])

    def test_the_numero_abbreviation_in_a_label_governs_nothing(self):
        notes = 'No. of polyps: 2\nPathology: Pending\nRecommendation: Repeat colonoscopy in 3 years'
        answers = fixture_answers(['No. of polyps', 'Pathology', 'Recommendation'], notes)
        self.assert_ready(answers['Pathology'], 'Pending')
        self.assert_ready(answers['Recommendation'], 'Repeat colonoscopy in 3 years')

    def test_a_bare_trailing_label_is_not_a_closing_heading(self):
        """`Signed by:` at the end governs nothing: the existing offer for an answer above it survives."""
        notes = 'Fictional software test only.\nSymptoms: no chest pain\nSigned by:'
        answer = fixture_answers(['Symptoms'], notes)['Symptoms']
        self.assertEqual(answer['status'], 'conflict')
        self.assertEqual(answer.get('suggestion'), 'no chest pain')
        # CONTROL: a closing heading with content still governs backward (E6d).

    def test_a_format_character_outside_the_selectors_after_a_colon_still_ends_a_heading(self):
        for tail in (':\U000E0100', ':\u3164', ':\u115f', ':\uffa0'):
            with self.subTest(tail=repr(tail)):
                notes = 'Family hx: pertinent negatives' + tail + '\nDiabetes: yes'
                self.assert_needs_decision(fixture_answers(['Family hx', 'Diabetes'], notes)['Diabetes'], 'yes',
                                           'Family hx: pertinent negatives')

    def test_the_tab_contract_holds_what_finalization_would_refuse(self):
        """The page and finalization must follow ONE rule: a tab answer finalization would refuse is held on the page."""
        notes = ('Extent: The scope was advanced to the splenic flexure.\nCorrection: The scope was advanced to the cecum.\n'
                 'Complications: None.')
        fields, answers = tab_answers(['Extent', 'Complications'], notes)
        extent = answers['Extent']
        self.assertEqual((extent['status'], extent['text']), ('conflict', ''))
        self.assertNotIn('suggestion', extent)
        stored = {field['key']: answers[field['label']] for field in fields}
        self.assertEqual(generation.governed_decisions(notes, fields, stored), [])
        # CONTROL: a clinical `Correction of …` on a tab form governs nothing, and finalization agrees.
        notes = 'RECOMMENDATIONS: Correction of iron deficiency with oral iron.\nCOMPLICATIONS: None.'
        fields, answers = tab_answers(['RECOMMENDATIONS', 'COMPLICATIONS'], notes)
        self.assertEqual({a['status'] for a in answers.values()}, {'supported'})
        stored = {field['key']: answers[field['label']] for field in fields}
        self.assertEqual(generation.governed_decisions(notes, fields, stored), [])


class WhatTheThirdPassFound(ExpectationsMixin, TestCase):
    """Refutation of the finished diff, third pass. Each input was demonstrated by a lens against ba9a950a; the
    expectation is what the note says clinically. Offline: fixture generation and provider-SHAPED selections."""

    def both(self, labels, notes, picks):
        yield 'fixture', fixture_answers(labels, notes)
        yield 'provider-shaped', provider_answers(labels, notes, picks)

    def governed_list(self, line, item):
        label, value = item.split(': ', 1)
        head = line.split(':')[0]
        notes = line + '\n' + item
        for path, answers in self.both([head, label], notes, {head: [line], label: [item]}):
            with self.subTest(line=line, path=path):
                self.assert_needs_decision(answers[label], value, line)

    def test_an_exception_elsewhere_in_the_line_never_releases_a_denied_list(self):
        for line, item in (
                ('Review of systems: negative except for knee pain; she denies the following.', 'Symptoms: chest pain'),
                ('Review of systems: All systems negative except as noted in the HPI; specifically denies the following.',
                 'Symptoms: chest pain, syncope'),
                ('Family history: noncontributory except that her mother had the following.', 'Diagnoses: breast cancer'),
                ('Plan: no follow-up needed, except return if she develops any of the following.', 'Symptoms: chest pain, syncope')):
            self.governed_list(line, item)

    def test_how_sentences_are_split_cannot_release_a_denied_list(self):
        for line in ('Review of systems: negative except for hepatitis B. She denies the following.',
                     'Review of systems: negative except for knee pain.She denies the following.',
                     'Review of systems: negative except for knee pain. \u200bShe denies the following.'):
            self.governed_list(line, 'Symptoms: chest pain')

    def test_a_denial_or_a_relative_outside_the_pointing_sentence_still_governs(self):
        for line, item in (('Family history: Reviewed. Her mother had the following.', 'Diagnoses: breast cancer'),
                           ('Family history: Positive. Mother had the following.', 'Diagnoses: diabetes'),
                           ('Review of systems: Negative. Specifically the following.', 'Symptoms: chest pain'),
                           ('Review of systems: Patient denies. See below.', 'Symptoms: chest pain'),
                           ('Social history: Her mother had the following.', 'Diagnoses: breast cancer'),
                           ('Social history: Her mother had the following conditions.', 'Diagnoses: breast cancer')):
            self.governed_list(line, item)

    def test_an_erratum_behind_a_label_the_form_does_not_know_governs_what_came_before(self):
        correction = 'Addendum: Correction: the patient does report severe crushing chest pain.'
        answer = fixture_answers(['Symptoms'], 'Symptoms: no chest pain\n' + correction)['Symptoms']
        self.assert_needs_decision(answer, 'no chest pain', correction)
        notes = ('EXTENT OF EXAMINATION: The scope was advanced to the cecum.\nCOMPLICATIONS: None.\n'
                 'ADDENDUM: Correction: a small perforation was identified and clipped.')
        fields, answers = tab_answers(['EXTENT OF EXAMINATION', 'COMPLICATIONS'], notes)
        self.assert_needs_decision(answers['COMPLICATIONS'], 'None.', 'ADDENDUM: Correction:')
        stored = {field['key']: answers[field['label']] for field in fields}
        self.assertEqual(generation.governed_decisions(notes, fields, stored), [])

    def test_every_erratum_punctuation_governs(self):
        for correction in ('Addendum: Correction to the above: the patient does report severe crushing chest pain.',
                           'Addendum: Correction. The patient does report severe crushing chest pain.',
                           'Addendum: Correction; the patient does report severe crushing chest pain.',
                           'Addendum: Correction (dictation error): the patient does report severe crushing chest pain.',
                           'Addendum: Correction - the patient does report severe crushing chest pain.'):
            notes = 'Symptoms: no chest pain\n' + correction
            for path, answers in self.both(['Symptoms', 'Addendum'], notes,
                                           {'Symptoms': ['Symptoms: no chest pain'], 'Addendum': [correction]}):
                with self.subTest(correction=correction, path=path):
                    self.assert_needs_decision(answers['Symptoms'], 'no chest pain', correction)
        for line in ('Correction. A small perforation was identified and clipped.',
                     'Correction; a small perforation was identified and clipped.'):
            with self.subTest(line=line):
                fields, answers = tab_answers(['COMPLICATIONS'], 'COMPLICATIONS: None.\n' + line)
                self.assert_needs_decision(answers['COMPLICATIONS'], 'None.', line)

    #: The retained synthetic SOAP fixture (`soap-verification-20260920/source-notes.txt`), whose live typed and voice
    #: responses expected 5 supported, 1 conflict, 2 missing. The erratum restates `Pain score`, already answered.
    SOAP = ('Symptoms: Left ankle soreness began after twisting the left ankle yesterday.\n'
            'Pertinent negatives: Denies fever, numbness, and right ankle pain.\nPain score: Six out of ten.\n'
            'Pain score: Correction: three out of ten; the earlier six out of ten was entered in error.\n'
            'Examination: Mild swelling over the left lateral ankle. No open wound.\n'
            'Assessment: The clinician explicitly documents a left ankle sprain.\n'
            'Plan: The clinician explicitly directs rest, ice wrapped in cloth for fifteen minutes at a time, and follow-up '
            'in three days. No medication is prescribed.')
    SOAP_LABELS = ['Symptoms', 'Pertinent negatives', 'Pain score', 'Allergies', 'Examination', 'Vital signs', 'Assessment', 'Plan']

    def test_an_erratum_that_restates_an_answered_question_corrects_that_question_only(self):
        lines = {line.split(': ', 1)[0]: line for line in self.SOAP.splitlines()}
        picks = {label: [line for line in self.SOAP.splitlines() if line.startswith(label + ':')] for label in self.SOAP_LABELS}
        for path, answers in self.both(self.SOAP_LABELS, self.SOAP, picks):
            with self.subTest(path=path):
                counts = {}
                for answer in answers.values():
                    counts[answer['status']] = counts.get(answer['status'], 0) + 1
                self.assertEqual(counts, {'supported': 5, 'conflict': 1, 'missing': 2})
                self.assert_ready(answers['Pertinent negatives'], lines['Pertinent negatives'].split(': ', 1)[1])
                self.assertEqual(answers['Pain score']['status'], 'conflict')
        # CONTROL: the same erratum under a question NOT answered before it may correct anything above it.
        notes = self.SOAP.replace('Pain score: Six out of ten.\n', '')
        self.assertEqual(fixture_answers(self.SOAP_LABELS, notes)['Symptoms']['status'], 'conflict')

    def test_a_bare_closing_label_is_bare_behind_an_invisible_character(self):
        for tail in ('\u200b', '\ufeff', ' \u200b'):
            with self.subTest(tail=repr(tail)):
                answer = fixture_answers(['Symptoms'], 'Fictional software test only.\nSymptoms: no chest pain\nSigned by:' + tail)['Symptoms']
                self.assertEqual(answer.get('suggestion'), 'no chest pain')

    def test_an_unanswered_question_at_the_end_is_not_a_closing_heading(self):
        notes = 'Fictional software test only.\nSymptoms: no chest pain\nAllergies:'
        self.assertEqual(fixture_answers(['Symptoms', 'Allergies'], notes)['Symptoms'].get('suggestion'), 'no chest pain')
        # Bareness is decided after the recognized label, which may itself contain a colon.
        notes = 'Fictional software test only.\nIndication: screening colonoscopy\nBowel prep: quality:'
        self.assertEqual(fixture_answers(['Indication', 'Bowel prep: quality'], notes)['Indication'].get('suggestion'),
                         'screening colonoscopy')

    def test_the_documented_costs_of_an_erratum_that_fails_closed(self):
        """⚠️ TRADES, PINNED (fifth pass): an unlisted continuation after the word is read as an erratum, so these hold the
        answer above them: a target phrased in words, an occupation in brackets, an order line named Correction."""
        for line in ('Occupation: Corrections (state prison officer).', 'Plan: Correction to no more than 8 mmol/L in 24 hours.',
                     'Insulin: Correction: 2 units per 50 mg/dL above 150.', 'Glucose: 312 correction: 4 units lispro given'):
            label = line.split(':')[0]
            with self.subTest(line=line):
                answer = fixture_answers(['Diagnosis', label], 'Diagnosis: type 2 diabetes\n' + line)['Diagnosis']
                self.assert_needs_decision(answer, 'type 2 diabetes', line)
        # Ninth pass: a line STARTING with the word withholds every offer, a treatment line included (the guide says so).
        notes = ('Fictional patient seen today for insulin review.\nDiagnosis: type 2 diabetes\n'
                 'Basal insulin: glargine 20 units at bedtime\nCorrection scale: lispro 2 units per 50 mg/dL above 150')
        answer = fixture_answers(['Diagnosis', 'Basal insulin', 'Correction scale'], notes)['Diagnosis']
        self.assertNotIn('suggestion', answer)
        self.assertIn('starts with the word Correction', answer['held_candidate']['reason'])

    def test_the_documented_costs_of_errata_and_empty_questions(self):
        """⚠️ TRADES, PINNED. An erratum on no label, or under a label nobody answered before, may correct any line above
        it, so every answer above it needs a decision (`Corrections: none` included). An unanswered question mid-note
        may be a denial heading (`Pertinent negatives:`), so the answers after it need a decision."""
        answers = fixture_answers(['Findings', 'Addendum'], 'Findings: Sigmoid diverticulosis\nAddendum: Corrections to the prior report: none')
        self.assert_needs_decision(answers['Findings'], 'Sigmoid diverticulosis', 'Addendum: Corrections')
        notes = 'Symptoms: chest pain\nAllergies:\nExamination: normal heart sounds'
        answer = fixture_answers(['Symptoms', 'Allergies', 'Examination'], notes)['Examination']
        self.assert_needs_decision(answer, 'normal heart sounds', 'Allergies:')
        notes = 'Pertinent negatives:\nSymptoms: chest pain'
        self.assert_needs_decision(fixture_answers(['Pertinent negatives', 'Symptoms'], notes)['Symptoms'], 'chest pain',
                                   'Pertinent negatives:')


class WhatTheFourthPassFound(ExpectationsMixin, TestCase):
    """Refutation of the finished diff, fourth pass (over f99f6d95). Each input was demonstrated by a lens; the
    expectation is what the note says clinically. Offline: fixture generation and provider-shaped selections."""

    def both(self, labels, notes, picks):
        yield 'fixture', fixture_answers(labels, notes)
        yield 'provider-shaped', provider_answers(labels, notes, picks)

    def test_an_erratum_in_the_same_paragraph_governs_the_sentences_before_it(self):
        """⚠️ Reach is by POSITION IN THE NOTE, not by line: a dictated paragraph is one line on the tab contract."""
        notes = ('PROCEDURE: diagnostic colonoscopy. COMPLICATIONS: perforation. Correction: there were no complications, '
                 'the perforation was in the prior patient.')
        _, answers = tab_answers(['PROCEDURE', 'COMPLICATIONS'], notes)
        self.assert_needs_decision(answers['COMPLICATIONS'], 'perforation.', 'Correction: there were no complications')
        answer = fixture_answers(['Fever'], 'Fever: yes. Correction: no fever.')['Fever']
        self.assertNotEqual(answer['status'], 'supported')
        self.assertNotIn('suggestion', answer)
        # The governing sentence is on the answer's own line, and the page says so.
        self.assertTrue(answer['held_candidate']['context'][0]['same'])

    def test_a_forward_pointer_in_the_same_paragraph_governs_the_sentences_after_it(self):
        notes = ('PROCEDURE: diagnostic colonoscopy. Her colonoscopy in 2019 at another centre had the following. '
                 'COMPLICATIONS: perforation.')
        _, answers = tab_answers(['PROCEDURE', 'COMPLICATIONS'], notes)
        self.assert_needs_decision(answers['COMPLICATIONS'], 'perforation.', 'had the following.')

    def test_the_answered_question_exception_is_exactly_as_narrow_as_stated(self):
        for labels, notes, held in (
                (['Allergies', 'Comments'], 'Allergies: penicillin\nComments:\nComments: Correction: the allergy is sulfa, not penicillin.',
                 'Allergies'),
                (['Pain score', 'Allergies'], 'Pain score: two out of ten\nAllergies: penicillin\n'
                 'Pain score: Correction: three out of ten. Correction: the allergy is sulfa, not penicillin.', 'Allergies'),
                (['Pain score', 'Allergies'], 'Pain score: 2\nAllergies: penicillin\nPain score: 3. Correction: the allergy is sulfa, not penicillin.',
                 'Allergies'),
                # The word opens the value but is a treatment; the erratum is later on the line.
                (['Insulin', 'Allergies'], 'Insulin: glargine 10 units\nAllergies: penicillin\n'
                 'Insulin: Correction scale with meals. Correction: the allergy is sulfa, not penicillin.', 'Allergies'),
                (['Insulin', 'Allergies'], 'Insulin: glargine 10 units\nAllergies: penicillin\n'
                 'Insulin: Correction scale with meals: correction, the allergy is sulfa, not penicillin.', 'Allergies'),
                # An earlier erratum is not an answer that the later one could be correcting.
                (['Pain score', 'Allergies'], 'Pain score: Correction: three out of ten\nAllergies: penicillin\n'
                 'Pain score: Correction: the allergy is sulfa, not penicillin.', 'Allergies')):
            with self.subTest(notes=notes):
                answer = fixture_answers(labels, notes)[held]
                self.assertEqual(answer['status'], 'conflict', answer)
                self.assertNotIn('suggestion', answer)
                self.assertEqual(answer['held_candidate']['text'], 'penicillin')
        # A question first answered in the tab form's own sentence style is answered too.
        notes = ('Symptoms: Left ankle soreness began yesterday.\nPain score was six out of ten.\n'
                 'Pain score: Correction: three out of ten; the earlier six out of ten was entered in error.')
        _, answers = tab_answers(['Symptoms', 'Pain score'], notes)
        self.assertEqual(answers['Symptoms']['status'], 'supported', answers['Symptoms'])

    def test_an_erratum_behind_a_bracket_a_quote_a_letter_or_an_ellipsis_still_governs(self):
        for correction in ('(Correction: the allergy is sulfa, not penicillin.)', '[Correction: the allergy is sulfa, not penicillin.]',
                           'a) Correction: the allergy is sulfa, not penicillin.',
                           'Comments: Patient said "no other allergies." Correction: the allergy is sulfa, not penicillin.',
                           'Comments: reviewed\u2026 Correction: the allergy is sulfa, not penicillin.',
                           'Comments: reviewed (no other allergies.) Correction: the allergy is sulfa, not penicillin.'):
            notes = 'Allergies: penicillin\n' + correction
            with self.subTest(correction=correction):
                answer = fixture_answers(['Allergies', 'Comments'], notes)['Allergies']
                self.assertEqual(answer['status'], 'conflict', answer)
                self.assertNotIn('suggestion', answer)

    def test_the_word_correction_in_a_treatment_a_target_or_an_occupation_governs_nothing(self):
        for line in ('Insulin: Correction/sliding scale lispro with meals', 'Result: Correction to 14 degrees was achieved.',
                     'Refraction: Correction to 20/20 OU with -1.50 sphere.', 'Occupation: Corrections officer',
                     'Insulin: Correction factor 50'):
            label = line.split(':')[0]
            with self.subTest(line=line):
                answers = fixture_answers(['Diagnosis', label], 'Diagnosis: type 2 diabetes\n' + line)
                self.assert_ready(answers['Diagnosis'], 'type 2 diabetes')

    def test_every_line_that_governs_an_answer_is_shown_with_it_not_only_the_nearest(self):
        notes = 'Review of systems: negative for the following:\nCardiovascular: see below\nSymptoms: chest pain'
        answers = fixture_answers(['Review of systems', 'Cardiovascular', 'Symptoms'], notes)
        quotes = [entry['quote'] for entry in answers['Symptoms']['held_candidate']['context']]
        self.assertIn(HEADING, quotes)
        self.assertIn('Cardiovascular: see below', quotes)

    def test_a_pointer_before_a_semicolon_a_decimal_or_an_abbreviation_does_not_end_its_sentence(self):
        for line, after in (('HPI: Inverted the right ankle playing soccer; swelling appeared the following morning; able to bear weight.',
                             'Examination: mild swelling'),
                            ('Left SSV: Competent at the SPJ and below; diameter 3.0 mm.', 'Impression: normal study'),
                            ('Left SSV: Competent at the SPJ and below; Diameter 3.0 mm.', 'Impression: normal study'),
                            ('Plan: Repeat chest X-ray the following a.m. before discharge.', 'Follow-up: in two weeks'),
                            ('Monitoring: Vital signs every 15 minutes for the following 1.5 hours in recovery.', 'Disposition: home'),
                            ('Plan: Review the scan with the following Dr. Smith next week.', 'Follow-up: in two weeks')):
            label, other = line.split(':')[0], after.split(':')[0]
            with self.subTest(line=line):
                self.assert_ready(fixture_answers([label, other], line + '\n' + after)[other], after.split(': ', 1)[1])

    def test_as_follows_ends_a_sentence_by_pointing_forward(self):
        line = "Social history: Her mother's history is as follows."
        answers = fixture_answers(['Social history', 'Diagnoses'], line + '\nDiagnoses: breast cancer')
        self.assert_needs_decision(answers['Diagnoses'], 'breast cancer', line)

    def test_a_closing_line_is_bare_despite_a_clock_time_and_not_bare_when_its_label_reframes(self):
        notes = 'Fictional software test only.\nSymptoms: no chest pain\nElectronically signed on 09/21/2026 at 10:42 by:'
        self.assertEqual(fixture_answers(['Symptoms'], notes)['Symptoms'].get('suggestion'), 'no chest pain')
        closing = 'Family history: the following conditions:'
        answers = fixture_answers(['Diagnoses', 'Family history'], 'Diagnoses: diabetes\n' + closing)
        self.assert_needs_decision(answers['Diagnoses'], 'diabetes', closing)
        # The reframing word may sit in the label alone (no pointer on the line).
        closing = 'Family history: mother:'
        answer = fixture_answers(['Diagnoses', 'Family history'], 'Diagnoses: diabetes\n' + closing)['Diagnoses']
        self.assert_needs_decision(answer, 'diabetes', closing)
        # A pointer at the very end points at what came before it.
        self.assert_needs_decision(fixture_answers(['Diagnoses'], 'Diagnoses: diabetes\nThe following:')['Diagnoses'],
                                   'diabetes', 'The following:')
        # Governors after the answer are marked as such, so the page says "Followed by".
        self.assertTrue(answers['Diagnoses']['held_candidate']['context'][0]['after'])

    def test_a_colon_look_alike_or_a_blank_braille_cell_still_ends_a_heading(self):
        for heading in ('Review of systems: negative for\u2236', 'Review of systems: negative for\ua789',
                        'Review of systems: negative for:\u2800'):
            with self.subTest(heading=repr(heading)):
                answers = fixture_answers(['Review of systems', 'Symptoms'], heading + '\nSymptoms: chest pain')
                self.assertEqual(answers['Symptoms']['status'], 'conflict', answers['Symptoms'])
                self.assertEqual(answers['Symptoms']['text'], '')

    def test_the_bounded_label_reader_returns_exactly_what_the_unbounded_one_did(self):
        """The fourth pass measured seconds per request on a line of colons; the bound must not change a result."""
        import random

        def unbounded(line, labels):
            candidates = []
            for index, character in enumerate(line):
                if character != ':':
                    continue
                label = line[:index].strip().casefold()
                if label in labels:
                    remainder = line[index + 1:]
                    candidates.append((labels[label], remainder.strip(), index + 1 + len(remainder) - len(remainder.lstrip())))
            return candidates[-1] if candidates else None

        labels = generation.recognized_labels(form('Pain score', 'Right GSV at the SFJ: diameter (mm)', 'ß', 'İx', 'A'))
        pieces = ['Pain score', 'right gsv at the sfj', ': diameter (mm)', ':', '  ', 'ß', 'SS', 'İx', 'a', ' value', '\u00a0', '::']
        rng = random.Random(20260923)
        for _ in range(4000):
            line = ''.join(rng.choice(pieces) for _ in range(rng.randint(1, 8)))
            with self.subTest(line=line):
                self.assertEqual(generation.labelled_value(line, labels), unbounded(line, labels))

    def test_a_candidate_held_for_a_reason_elsewhere_in_the_note_says_so(self):
        notes = 'Symptoms: chest pain\nFever: yes\nIf pain recurs, return to the clinic.'
        held = fixture_answers(['Symptoms', 'Fever'], notes)['Fever']['held_candidate']
        self.assertEqual(held['context'], [])
        self.assertNotIn('the line shown', held['reason'])
        self.assertIn('elsewhere in the note', held['reason'])


class WhatTheFifthPassFound(ExpectationsMixin, TestCase):
    """Refutation of the finished diff, fifth pass (over 32ae81f5). Each input was demonstrated by a lens."""

    def held(self, answer):
        self.assertEqual(answer['status'], 'conflict', answer)
        self.assertEqual(answer['text'], '')
        self.assertNotIn('suggestion', answer)

    def test_the_one_word_after_the_following_is_a_word_as_a_doctor_writes_it(self):
        for line, item in (('Review of systems: patient denies the following symptom(s).', 'Symptoms: chest pain, dyspnea'),
                           ('Review of systems: patient denies the following (reviewed today).', 'Symptoms: chest pain'),
                           ('Review of systems: negative for the following sx/signs.', 'Symptoms: chest pain'),
                           ("Review of systems: negative for the following pt's.", 'Symptoms: chest pain'),
                           ('Family history: her mother had the following co-morbidities.', 'Diabetes: yes')):
            label, value = item.split(': ', 1)
            with self.subTest(line=line):
                self.assert_needs_decision(fixture_answers([line.split(':')[0], label], line + '\n' + item)[label], value, line)

    def test_a_pointer_followed_by_a_colon_governs_what_follows_on_the_line(self):
        for middle in ('Her previous colonoscopy in 2019 elsewhere was as follows: polyps.', 'It showed the following: polyps.'):
            notes = 'PROCEDURE: diagnostic colonoscopy. ' + middle + ' COMPLICATIONS: perforation.'
            with self.subTest(middle=middle):
                _, answers = tab_answers(['PROCEDURE', 'COMPLICATIONS'], notes)
                self.held(answers['COMPLICATIONS'])

    def test_follows_is_read_only_as_as_follows(self):
        notes = 'HEENT: Red reflex present bilaterally. Fixes and follows.\nHeart: Regular rate and rhythm, no murmur.'
        self.assert_ready(fixture_answers(['HEENT', 'Heart'], notes)['Heart'], 'Regular rate and rhythm, no murmur.')

    def test_an_erratum_is_any_correction_that_is_not_a_listed_treatment_or_target(self):
        """⚠️ FAIL CLOSED (fifth pass): the round before narrowed the shapes and `Correction to my dictation, …` stopped
        governing. Now the word governs unless a treatment or target continuation follows it."""
        for correction in ('Correction to my dictation, there were no complications.', 'Correction for the record: there were no complications.',
                           'Correction -- there were no complications.', 'Correction\u2026 there were no complications.',
                           'Correction [transcription error]: there were no complications.', 'Correction per Dr. Smith: there were no complications.',
                           'Correction and addendum: there were no complications.', 'Transcription correction: there were no complications.',
                           'Correction (dictation error) there were no complications.',
                           'Correction to the operative note of September 21: there were no complications.'):
            with self.subTest(correction=correction):
                _, answers = tab_answers(['PROCEDURE', 'COMPLICATIONS'],
                                         'PROCEDURE: diagnostic colonoscopy. COMPLICATIONS: perforation. ' + correction)
                self.held(answers['COMPLICATIONS'])
        answer = fixture_answers(['Extent', 'Plan'], 'Extent: cecum\nNote: correction to my dictation, the scope reached only the '
                                                     'splenic flexure.\nPlan: repeat colonoscopy in one year')['Extent']
        self.held(answer)
        for line in ('Occupation: Corrections officer.', 'Insulin: Correction (sliding scale), lispro with meals.',
                     'Plan: Discussed bracing vs. correction, and the family chose bracing.', 'Plan: Glasses, i.e. correction, full time.',
                     'Refraction: Correction to 20/20 OU.', 'Insulin: Correction dose 2 units.', 'Insulin: correction factor 50.'):
            label = line.split(':')[0]
            with self.subTest(line=line):
                self.assert_ready(fixture_answers(['Diagnosis', label], 'Diagnosis: type 2 diabetes\n' + line)['Diagnosis'], 'type 2 diabetes')

    def test_a_note_wide_hold_is_not_triggered_by_a_lettered_treatment_line(self):
        for line in ('a) Correction of hypokalemia with oral potassium chloride.', '(corrections officer, day shift)'):
            notes = 'Fictional software test only.\nAssessment: Hypokalemia.\nPlan: Potassium chloride 40 mEq orally.\n' + line
            with self.subTest(line=line):
                self.assertEqual(fixture_answers(['Assessment', 'Plan'], notes)['Assessment'].get('suggestion'), 'Hypokalemia.')

    def test_the_answered_question_exception_reads_sentences_not_lines(self):
        notes = ('Symptoms: Left ankle soreness began yesterday. Pertinent negatives: Denies fever. Pain score: Six out of ten. '
                 'Pain score: Correction: three out of ten; the earlier six out of ten was entered in error.')
        _, answers = tab_answers(['Symptoms', 'Pertinent negatives', 'Pain score'], notes)
        self.assertEqual(answers['Symptoms']['status'], 'supported', answers['Symptoms'])
        self.assertEqual(answers['Pertinent negatives']['status'], 'supported')

    def test_many_governors_are_bounded_and_counted_and_every_meaningful_one_is_kept_first(self):
        notes = 'Review of systems: negative for the following:\n' + ''.join(f'Section {i}:\n' for i in range(400)) + 'Symptoms: chest pain'
        held = fixture_answers(['Review of systems', 'Symptoms'], notes)['Symptoms']['held_candidate']
        quotes = [entry.get('quote') for entry in held['context']]
        self.assertIn(HEADING, quotes)
        self.assertLessEqual(len(held['context']), 16)
        self.assertEqual(held['context'][-1].get('more'), 401 - (len(held['context']) - 1))
        # Every one of these changes meaning; the cap still holds and the rest are counted.
        notes = ''.join(f'Negative {i}:\n' for i in range(400)) + 'Symptoms: chest pain'
        held = fixture_answers(['Symptoms'], notes)['Symptoms']['held_candidate']
        self.assertEqual(len(held['context']), 16)
        self.assertEqual(held['context'][-1], {'more': 385})
        # With fewer than the cap, the three nearest ordinary headings are all shown.
        notes = 'Section A:\nSection B:\nSection C:\nSection D:\nSection E:\nSymptoms: chest pain'
        held = fixture_answers(['Symptoms'], notes)['Symptoms']['held_candidate']
        self.assertEqual([e.get('quote') for e in held['context']], ['Section C:', 'Section D:', 'Section E:', None])
        self.assertEqual(held['context'][-1], {'more': 2})

    def test_a_disagreement_says_so_rather_than_pointing_elsewhere(self):
        answer = provider_answers(['Extent', 'Complications'], 'Extent: splenic flexure\nThe scope was advanced to the cecum.\n'
                                  'Complications: none', {'Extent': ['The scope was advanced to the cecum.']})['Extent']
        self.assertEqual(answer['held_candidate']['context'], [])
        self.assertIn('more than one answer', answer['held_candidate']['reason'])

    def test_the_longest_label_is_measured_once_per_form(self):
        class Counting(generation.Labels):
            iterations = 0

            def __iter__(self):
                type(self).iterations += 1
                return super().__iter__()
        labels = Counting(generation.recognized_labels(form('Pain score')))
        for _ in range(100):
            generation.labelled_value('Pain score: 3', labels)
        self.assertLessEqual(Counting.iterations, 1)

    def test_governance_is_linear_on_adversarial_notes(self):
        import time
        fields = [{'key': f'k{i}', 'label': f'Question {i}', 'kind': 'text', 'locator': {'cell': i}} for i in range(100)]
        for notes in ('\n'.join(['x'] * 500 + ['Question 1: Correction, 3'] * 200), 'Question 0: yes.' + '"' * 49984,
                      '\n'.join(['Section:'] * 5000 + [f'Question {i}: yes' for i in range(100)])):
            with self.subTest(size=len(notes)):
                started = time.perf_counter()
                generation.generate(notes, fields, FIXTURE)
                self.assertLess(time.perf_counter() - started, 20)

    def test_a_governed_conflict_for_another_reason_still_shows_its_governing_line(self):
        notes = 'Comments: negative for the following:\nSymptoms: chest pain\nSymptoms: palpitations\nPlan: review'
        answer = fixture_answers(['Comments', 'Symptoms', 'Plan'], notes)['Symptoms']
        self.assertEqual(answer['status'], 'conflict')
        self.assertIn('Comments: negative for the following:', [e.get('quote') for e in answer['held_candidate']['context']])

    def test_a_whole_note_span_is_never_the_answers_own_line(self):
        """An answer whose stored evidence is the whole note is not governed by an erratum that precedes its lines."""
        notes = 'Comments: Correction: dictated in error, disregard the earlier draft.\nSymptoms: chest pain\nSymptoms: palpitations\nSeen today.'
        fields = form('Comments', 'Symptoms')
        answers = generation.generate(notes, fields, FIXTURE)[0]
        cleared = {**answers['q1'], 'status': 'edited', 'text': ''}
        self.assertEqual(generation.governed_decisions(notes, fields, {'q1': {**cleared, 'held_candidate': None}}), [])


class WhatTheSixthPassFound(ExpectationsMixin, TestCase):
    """Refutation of the finished diff, sixth pass (over 8a72af06). Each input was demonstrated by a lens."""

    def held(self, answer):
        self.assertEqual(answer['status'], 'conflict', answer)
        self.assertEqual(answer['text'], '')
        self.assertNotIn('suggestion', answer)

    def test_the_exemption_needs_the_validator_to_see_both_answers(self):
        """The legacy validator reads a question's answers per LINE, so a mid-line erratum is never its second answer."""
        notes = 'Allergies: none\nMedications: aspirin 81 mg daily. Allergies: Correction: penicillin (anaphylaxis).'
        for path, answers in (('fixture', fixture_answers(['Allergies', 'Medications'], notes)),
                              ('provider-shaped', provider_answers(['Allergies', 'Medications'], notes,
                                                                   {'Allergies': ['Allergies: none'], 'Medications': [notes.split('\n')[1]]}))):
            with self.subTest(path=path):
                self.assertNotEqual(answers['Allergies']['status'], 'supported', answers['Allergies'])
                self.assertNotIn('suggestion', answers['Allergies'])

    def test_any_bullet_or_list_marker_before_the_word_still_makes_an_erratum(self):
        for bullet in ('\u25cf ', '\u25cb ', '\u25a0 ', '\u27a2 ', '\uf0b7 ', '> ', '+ ', 'iii) ', '1- ', '2.1 ', '#2 ',
                       "Physician's correction", 'Late-entry correction', '2nd correction'):
            line = (bullet + ': there were no complications.') if bullet.endswith('correction') else (bullet + 'Correction: there were no complications.')
            with self.subTest(line=line):
                _, answers = tab_answers(['PROCEDURE', 'COMPLICATIONS'], 'PROCEDURE: diagnostic colonoscopy.\nCOMPLICATIONS: perforation.\n' + line)
                self.held(answers['COMPLICATIONS'])
        answer = fixture_answers(['Symptoms', 'Plan'], 'Symptoms: chest pain\n\u25cf Correction: the patient has no chest pain.\nPlan: follow up')['Symptoms']
        self.assertNotIn('suggestion', answer)
        # A number before the word is a list marker even with no separator after the word.
        for line in ('#2 Correction the perforation was in the prior patient.', '2.1 Correction the perforation was in the prior patient.'):
            with self.subTest(line=line):
                _, answers = tab_answers(['PROCEDURE', 'COMPLICATIONS'], 'PROCEDURE: diagnostic colonoscopy.\nCOMPLICATIONS: perforation.\n' + line)
                self.held(answers['COMPLICATIONS'])

    def test_a_single_capital_ends_a_sentence_before_an_erratum(self):
        for sentence in ('Sedation: moderate, ASA class I.', 'Serology positive for hepatitis E.', 'History obtained from the pt.', 'Diet, fluids, etc.'):
            with self.subTest(sentence=sentence):
                _, answers = tab_answers(['PROCEDURE', 'COMPLICATIONS'], 'PROCEDURE: diagnostic colonoscopy.\nCOMPLICATIONS: perforation.\n'
                                         + sentence + ' Correction: there were no complications.')
                self.held(answers['COMPLICATIONS'])

    def test_an_aside_of_any_length_keeps_the_pointer(self):
        line = ('Family history: her mother had the following conditions (reviewed with the patient and with her daughter, '
                'who accompanies her to clinic today).')
        self.assert_needs_decision(fixture_answers(['Family history', 'Diabetes'], line + '\nDiabetes: yes')['Diabetes'], 'yes', 'had the following')

    def test_a_form_question_named_correction_is_not_an_erratum(self):
        notes = 'Procedure: left hallux valgus osteotomy\nFindings: HVA 32 degrees\nCorrection achieved: HVA 10 degrees\nPlan: post-op shoe'
        answers = fixture_answers(['Procedure', 'Findings', 'Correction achieved', 'Plan'], notes)
        self.assert_ready(answers['Procedure'], 'left hallux valgus osteotomy')
        answers = fixture_answers(['VA', 'Correction'], 'VA: 6/6 both eyes\nCorrection: spectacles for distance')
        self.assert_ready(answers['VA'], '6/6 both eyes')
        # CONTROL: the same words when Correction is NOT one of the form's questions are an erratum.
        self.held(fixture_answers(['VA'], 'VA: 6/6 both eyes\nCorrection: spectacles for distance')['VA'])

    def test_a_heading_closing_a_paragraph_governs_from_its_own_sentence(self):
        notes = 'Indication: screening colonoscopy. Findings: sigmoid polyp. Plan: repeat colonoscopy in 5 years. Signed by:'
        _, answers = tab_answers(['Indication', 'Findings', 'Plan'], notes)
        self.assertEqual(answers['Indication'].get('suggestion'), 'screening colonoscopy.', answers['Indication'])
        # CONTROL: a closing heading that is not bare reaches every sentence before it, on its own line too.
        notes = 'Indication: screening colonoscopy. Findings: sigmoid polyp. Patient denies:'
        _, answers = tab_answers(['Indication', 'Findings'], notes)
        self.assertNotIn('suggestion', answers['Indication'])
        self.assertIn('Patient denies:', [e.get('quote') for e in answers['Indication']['held_candidate']['context']])

    def test_a_pointer_period_is_a_sentence_end_only_before_a_new_sentence(self):
        for line in ('Plan: sutures out the following wk. at the GP surgery', 'Plan: sutures out the following Mon. at the GP surgery'):
            with self.subTest(line=line):
                self.assert_ready(fixture_answers(['Plan', 'Follow-up'], line + '\nFollow-up: in two weeks')['Follow-up'], 'in two weeks')

    def test_an_erratum_is_shown_as_its_sentence_and_bounded(self):
        notes = 'Q0: finding 0\n' + 'Correction: none. ' * 300
        held = fixture_answers(['Q0'], notes)['Q0']['held_candidate']
        self.assertTrue(all(len(entry.get('quote', '')) <= 402 for entry in held['context']))
        self.assertTrue(held['context'][0]['quote'].startswith('Correction: none.'))

    def test_more_counts_distinct_lines(self):
        answers = fixture_answers(['Symptoms'], 'Symptoms: chest pain\nNone of these apply:\nSymptoms: dyspnea')
        self.assertNotIn({'more': 1}, answers['Symptoms']['held_candidate']['context'])
        answers = fixture_answers(['Indication', 'Findings'], 'Indication: screening colonoscopy\nFindings: sigmoid polyp\n'
                                  'Correction to the above:\nThe polyp was in the rectum.')
        self.assertEqual([e.get('more') for e in answers['Indication']['held_candidate']['context'] if 'more' in e], [])


class WhatTheSeventhPassFound(ExpectationsMixin, TestCase):
    """Refutation of the finished diff, seventh pass (over 19e441f9). Each input was demonstrated by a lens."""

    def held(self, answer):
        self.assertEqual(answer['status'], 'conflict', answer)
        self.assertEqual(answer['text'], '')
        self.assertNotIn('suggestion', answer)

    def test_a_pointer_sentence_ends_whatever_trails_it_to_the_line_end(self):
        for line in ('Review of systems: Patient denies the following.\u2800', 'Review of systems: *Patient denies the following.*',
                     'Review of systems: Patient denies the following.<br>', 'Review of systems: Patient denies the following. -',
                     'Review of systems: Patient denies the following (see HPI (2019)).', 'Review of systems: Patient denies the following (a) (b).',
                     'Review of systems: Patient denies the following (see HPI) (reviewed today).',
                     # More asides than are read one by one end the sentence: fail closed.
                     'Review of systems: Patient denies the following (first) (second) (third) (fourth) (fifth) (sixth).'):
            with self.subTest(line=line):
                self.held(fixture_answers(['Review of systems', 'Symptoms'], line + '\nSymptoms: chest pain')['Symptoms'])

    def test_a_pointer_before_a_heading_on_the_same_line_still_governs(self):
        notes = ('PATIENT NAME: SYNTHETIC TAB PATIENT.\nBefore the procedure the risks were explained, including the following. '
                 'COMPLICATIONS: perforation, bleeding and missed lesions. Findings are as follows:\nFINDINGS: sigmoid diverticulosis.')
        _, answers = tab_answers(['PATIENT NAME', 'COMPLICATIONS', 'FINDINGS'], notes)
        self.held(answers['COMPLICATIONS'])

    def test_an_erratum_in_markdown_underscores_still_governs(self):
        for line in ('_Correction:_ a small perforation was identified and clipped.', '__Correction__: a small perforation was identified.'):
            with self.subTest(line=line):
                _, answers = tab_answers(['COMPLICATIONS'], 'COMPLICATIONS: There were no immediate complications.\n' + line)
                self.held(answers['COMPLICATIONS'])

    def test_a_closing_as_follows_is_not_bare(self):
        answer = fixture_answers(['Indication', 'Diagnoses'], 'Indication: screening colonoscopy\nDiagnoses: breast cancer\nMother had them, as follows:')['Diagnoses']
        self.assertNotIn('suggestion', answer)

    def test_a_trailing_invisible_line_does_not_hide_the_closing_heading(self):
        answer = fixture_answers(['Indication', 'Symptoms'], 'Indication: screening colonoscopy\nSymptoms: chest pain\nExcluded the following:\n\u200b')['Symptoms']
        self.assertNotIn('suggestion', answer)

    def test_a_form_question_named_with_correction_withholds_nothing_note_wide(self):
        notes = ('Seen with her daughter today.\nVisual acuity: 6/12 right, 6/9 left unaided\nRefractive correction: spectacles, '
                 'prescription two years old\nIOP: 15 mmHg both eyes\nPlan: update spectacles')
        answers = fixture_answers(['Visual acuity', 'Refractive correction', 'IOP', 'Plan'], notes)
        self.assertEqual(answers['IOP'].get('suggestion'), '15 mmHg both eyes', answers['IOP'])

    def test_a_value_or_a_clock_time_before_the_word_is_not_a_list_marker(self):
        for line in ('Glucose: 312 correction given', 'Potassium: 3.1 - correction started orally', 'Calcium: 2.02 (albumin correction: 2.26)',
                     'Events: at 12:00 correction 4 units for glucose 280', 'Events: at 12:00 correction: 4 units for glucose 280'):
            label = line.split(':')[0]
            with self.subTest(line=line):
                self.assert_ready(fixture_answers(['Diagnosis', label], 'Diagnosis: type 2 diabetes\n' + line)['Diagnosis'], 'type 2 diabetes')
        # CONTROL: a list number after a label is still a marker.
        self.held(fixture_answers(['Diagnosis', 'Comments'], 'Diagnosis: type 2 diabetes\nComments: 1. Correction: type 1 diabetes')['Diagnosis'])

    def test_a_question_whose_own_label_ends_on_a_pointer_does_not_govern(self):
        notes = ('Procedure: colonoscopy with polypectomy\nPatient was informed of the following risks: bleeding, perforation, missed lesion\n'
                 'Consent: written consent obtained')
        answers = fixture_answers(['Procedure', 'Patient was informed of the following risks', 'Consent'], notes)
        self.assert_ready(answers['Consent'], 'written consent obtained')
        self.assert_ready(answers['Patient was informed of the following risks'], 'bleeding, perforation, missed lesion')

    def test_one_line_is_shown_once_and_its_own_line_is_named_so(self):
        notes = 'Impression: no reflux\n' + ' '.join(f'Correction: segment {i} is the left side.' for i in range(20))
        held = fixture_answers(['Impression'], notes)['Impression']['held_candidate']
        self.assertEqual(len([e for e in held['context'] if 'quote' in e]), 1)
        self.assertNotIn('more', held['context'][-1])

    def test_a_one_line_notes_whole_line_is_the_answers_own_line(self):
        notes = 'Symptoms: chest pain. Correction: no chest pain.'
        fields = form('Symptoms')
        cleared = {'status': 'edited', 'text': '', 'evidence': [{'quote': notes, 'start': 0, 'end': len(notes)}]}
        self.assertEqual(generation.governed_decisions(notes, fields, {'q0': cleared}), ['Symptoms'])

    def test_the_cap_holds_for_an_answers_own_heading_sentences(self):
        notes = '\n'.join(f'Allergies: item{i} of the following:' for i in range(40))
        held = fixture_answers(['Allergies'], notes)['Allergies']['held_candidate']
        self.assertLessEqual(len(held['context']), 16)
        self.assertIn('more', held['context'][-1])

    def test_a_dash_only_note_is_linear(self):
        import time
        fields = [{'key': f'k{i}', 'label': f'Question {i}', 'kind': 'text', 'locator': {'cell': i}} for i in range(100)]
        notes = ''.join(f'Question {i}: yes\n' for i in range(100)) + '\u2014\n' * 5000
        started = time.perf_counter()
        generation.generate(notes, fields, FIXTURE)
        self.assertLess(time.perf_counter() - started, 20)


class WhatTheEighthPassFound(ExpectationsMixin, TestCase):
    """Refutation of the finished diff, eighth pass (over dc4f8fff)."""

    def held(self, answer):
        self.assertEqual(answer['status'], 'conflict', answer)
        self.assertEqual(answer['text'], '')
        self.assertNotIn('suggestion', answer)

    def test_a_correction_after_a_clinical_abbreviation_still_governs(self):
        for notes, labels, held in (
                ('Symptoms: no chest pain\nEcho: mild MR. Correction: patient reports severe crushing chest pain.', ['Symptoms', 'Echo'], 'Symptoms'),
                ('QTc: 450 ms\nRhythm: sinus, PR 160 ms. Correction: QTc 520 ms, prolonged.', ['QTc', 'Rhythm'], 'QTc'),
                ('Symptoms: no chest pain\nHistory: MS. Correction: patient reports severe chest pain.', ['Symptoms', 'History'], 'Symptoms')):
            with self.subTest(notes=notes):
                self.held(fixture_answers(labels, notes)[held])

    def test_one_word_is_one_token_as_it_is_written(self):
        for line, item in (('Review of systems: negative for the following sign(s)/symptom(s).', 'Symptoms: chest pain, dyspnea'),
                           ('Family history: her mother had the following diagnosis(es).', 'Diabetes: yes'),
                           ('Review of systems: negative for the following co\u2011morbidities.', 'Symptoms: chest pain')):
            label = item.split(':')[0]
            with self.subTest(line=line):
                self.held(fixture_answers([line.split(':')[0], label], line + '\n' + item)[label])
        answer = fixture_answers(['Symptoms', 'Comments'], 'Symptoms: no chest pain\nComments: Late\u2011entry correction: patient does report severe crushing chest pain.')['Symptoms']
        self.held(answer)

    def test_a_question_label_mid_paragraph_is_never_a_pointer(self):
        notes = ('Consent: obtained from the patient. Patient was informed of the following risks: bleeding and perforation. '
                 'Complications: none. Estimated blood loss: minimal.')
        _, answers = tab_answers(['Consent', 'Patient was informed of the following risks', 'Complications', 'Estimated blood loss'], notes)
        self.assertEqual(answers['Complications'].get('suggestion') or answers['Complications']['text'], 'none.', answers['Complications'])

    def test_a_question_label_stated_as_label_was_value_is_not_an_erratum(self):
        notes = 'Diagnosis: right hallux valgus.\nProcedure: chevron osteotomy.\nCorrection achieved was 7 degrees.'
        _, answers = tab_answers(['Diagnosis', 'Procedure', 'Correction achieved'], notes)
        self.assertEqual(answers['Diagnosis']['status'], 'supported', answers['Diagnosis'])

    def test_more_colon_look_alikes_and_a_blank_cell_before_a_correction(self):
        for mark in ('\u205a', '\u2982', '\u1361'):
            with self.subTest(mark=repr(mark)):
                self.held(fixture_answers(['ROS', 'Symptoms'], 'ROS: negative for' + mark + '\nSymptoms: chest pain')['Symptoms'])
        self.held(fixture_answers(['Symptoms', 'Comments'], 'Symptoms: no chest pain\nComments: reviewed.\u2800 Correction: patient reports severe chest pain.')['Symptoms'])
        self.held(fixture_answers(['Symptoms', 'Comments'], 'Symptoms: no chest pain\nComments: reviewed.\u2800Correction: patient reports severe chest pain.')['Symptoms'])

    def test_every_governing_span_on_a_line_is_shown(self):
        for notes, labels, word in (('Review of systems: patient denies the following. Cardiovascular:\nSymptoms: chest pain',
                                     ['Review of systems', 'Symptoms'], 'patient denies the following'),
                                    ('Family history: her mother had the following. Endocrine:\nDiabetes: yes',
                                     ['Family history', 'Diabetes'], 'her mother had the following')):
            with self.subTest(notes=notes):
                answers = fixture_answers(labels, notes)
                held = answers[labels[1]]['held_candidate']
                self.assertTrue(any(word in entry.get('quote', '') for entry in held['context']), held['context'])


class WhatTheNinthPassFound(ExpectationsMixin, TestCase):
    """Refutation of the finished diff, ninth pass (over 9ba301cb)."""

    def held(self, answer):
        self.assertEqual(answer['status'], 'conflict', answer)
        self.assertEqual(answer['text'], '')
        self.assertNotIn('suggestion', answer)

    def test_a_pointer_next_to_markup_or_a_dash_still_governs(self):
        for line in ('Review of systems: _negative for the following_', 'Review of systems: negative for the following--',
                     'Review of systems: negative for the following-', "Review of systems: 'negative for the following'",
                     'Review of systems: __negative for the following__', 'Review of systems: _see below_'):
            with self.subTest(line=line):
                self.held(fixture_answers(['Review of systems', 'Symptoms'], line + '\nSymptoms: chest pain')['Symptoms'])
        answer = fixture_answers(['Symptoms'], '_Patient denies the following_\nSymptoms: chest pain')['Symptoms']
        self.assertNotIn('suggestion', answer)

    def test_a_colon_heading_in_markup_still_governs(self):
        for heading in ('Family history: **Mother:**', 'Family history: _Mother:_', 'Family history: (Mother:)',
                        'Family history: Mother:\x01', 'Family history: Mother\ua4fd', 'Family history: Mother:*'):
            with self.subTest(heading=repr(heading)):
                self.held(fixture_answers(['Family history', 'Diabetes'], heading + '\nDiabetes: yes')['Diabetes'])

    def test_every_occurrence_of_a_quoted_answer_is_judged(self):
        notes = 'Symptoms: chest pain\nReview of systems: negative for the following:\nSymptoms: chest pain'
        self.assertNotEqual(fixture_answers(['Symptoms', 'Review of systems'], notes)['Symptoms']['status'], 'supported')
        self.assertNotEqual(tab_answers(['Symptoms', 'Review of systems'], notes)[1]['Symptoms']['status'], 'supported')
        notes = 'Review of systems: negative for the following:\nSymptoms: chest pain\nPlan: review\nSymptoms: chest pain'
        self.assertNotEqual(tab_answers(['Symptoms', 'Review of systems', 'Plan'], notes)[1]['Symptoms']['status'], 'supported')

    def test_the_page_and_finalization_judge_every_occurrence_of_a_stored_draft(self):
        """A draft from the installed release kept ONE occurrence; the page and finalization judge them all, by the
        index generation reads, so they agree with generation."""
        notes = 'Symptoms: chest pain\nReview of systems: negative for the following:\nSymptoms: chest pain'
        for tab in (False, True):
            with self.subTest(tab=tab):
                fields = [{'key': f'q{i}', 'label': label, 'kind': 'text',
                           'locator': {'cell': i, **({'tab_form': {'version': 1}} if tab else {})}}
                          for i, label in enumerate(['Symptoms', 'Review of systems'])]
                quote = 'Symptoms: chest pain' + ('' if not tab else '')
                stored = {'q0': {'status': 'supported', 'text': 'chest pain', 'reviewed': False,
                                 'evidence': [{'quote': quote, 'start': 0, 'end': len(quote)}]}}
                governance = generation.governance_for(notes, fields)
                row = generation.as_currently_governed(governance, notes, {**fields[0], **stored['q0']})
                self.assertEqual((row['status'], row['text']), ('conflict', ''), row)
                self.assertIn('Symptoms', generation.governed_decisions(notes, fields, stored))
                # CONTROL: the same draft with no governor after it stays as it was, and finalizes.
                plain = 'Symptoms: chest pain\nReview of systems: reviewed\nSymptoms: chest pain'
                governance = generation.governance_for(plain, fields)
                self.assertEqual(generation.as_currently_governed(governance, plain, {**fields[0], **stored['q0']})['status'], 'supported')
                self.assertNotIn('Symptoms', generation.governed_decisions(plain, fields, stored))

    def test_a_short_value_repeated_under_another_label_is_not_judged_for_this_question(self):
        notes = 'Question 2: yes\nReview: negative for the following:\nQuestion 5: yes'
        answers = fixture_answers(['Question 2', 'Review', 'Question 5'], notes)
        self.assert_ready(answers['Question 2'], 'yes')
        self.held(answers['Question 5'])
        fields = form('Question 2', 'Review', 'Question 5')
        stored = {fields[0]['key']: answers['Question 2']}
        self.assertEqual(generation.governed_decisions(notes, fields, stored), [])

    def test_each_governing_window_on_a_long_line_is_shown(self):
        middle = ' '.join(f'System {i}: symptom {i}, sign {i} or finding {i}.' for i in range(12))
        line = 'Review of systems: the patient denies the following. ' + middle + ' Correction: the patient does report exertional chest pain.'
        self.assertGreater(len(line), 450)
        notes = 'Symptoms: no chest pain\n' + line + '\nExamination: normal heart sounds'
        answers = fixture_answers(['Symptoms', 'Review of systems', 'Examination'], notes)
        before = ' '.join(e.get('quote', '') for e in answers['Symptoms']['held_candidate']['context'])
        after = ' '.join(e.get('quote', '') for e in answers['Examination']['held_candidate']['context'])
        self.assertIn('does report exertional chest pain', before)
        self.assertIn('the patient denies the following', after)

    def test_the_governing_windows_shown_are_the_ones_that_change_meaning_then_the_nearest(self):
        line = 'Plan: see below. See below. See below. See below. The patient denies the following.'
        context = fixture_answers(['Plan', 'Symptoms'], line + '\nSymptoms: chest pain')['Symptoms']['held_candidate']['context']
        self.assertIn('The patient denies the following.', ' '.join(entry.get('quote', '') for entry in context))

    def test_an_ungoverned_answer_cleared_on_a_one_paragraph_note_finalizes_empty(self):
        notes = ('Fictional software test only. Indication: rectal bleeding. Correction: the indication is iron deficiency anemia. '
                 'Findings: sigmoid diverticulosis. No immediate complications. Recommendation: repeat colonoscopy if bleeding recurs.')
        fields, answers = tab_answers(['Indication', 'Findings', 'COMPLICATIONS', 'Recommendation'], notes)
        stored = {field['key']: answers[field['label']] for field in fields}
        key = next(field['key'] for field in fields if field['label'] == 'Recommendation')
        stored[key] = {**stored[key], 'status': 'edited', 'text': '', 'held_candidate': None}
        stored[key].pop('suggestion', None); stored[key].pop('suggestion_evidence', None)
        self.assertNotIn('Recommendation', generation.governed_decisions(notes, fields, stored))

    def test_a_long_non_letter_value_prefix_before_many_errata_is_linear(self):
        import time
        fields = [{'key': f'k{i}', 'label': f'Question {i}', 'kind': 'text', 'locator': {'cell': i}} for i in range(100)]
        notes = ''.join(f'Question {i}: yes\n' for i in range(100)) + 'Question 1: ' + '-' * 20000 + ':correction' * 2000
        started = time.perf_counter()
        generation.governance_for(notes, fields)
        self.assertLess(time.perf_counter() - started, 2)


class TheQualifiedWordFormKeepsItsLabelsSelfContained(ExpectationsMixin, TestCase):
    """On the qualified Word form every label names its own side, vein and measure, so a sentence in one value
    cannot re-scope another: only structural headings and corrections govern there. Round 6 of the pilot
    measured the alternative: one location `not visualized below` emptied all 90 answers."""
    FIELDS = [{'key': 'location_11', 'label': 'Right tributary row 11: anatomical location', 'kind': 'text',
               'locator': {'row': 11}},
              {'key': 'measurement_15_2', 'label': 'Left GSV at the SFJ: reflux time (ms)', 'kind': 'measurement',
               'locator': {'row': 15, 'column': 2, 'unit': 'ms'}},
              {'key': 'sdt_-213273323', 'label': 'Right impression: reflux or absence', 'kind': 'choice',
               'locator': {'part': 'word/document.xml', 'sdt_id': '1'}}]

    def answers(self, notes):
        return generation.generate(notes, self.FIELDS, FIXTURE)[0]

    def test_a_free_text_value_ending_on_a_pointer_governs_nothing_on_the_qualified_form(self):
        notes = ('Right tributary row 11: anatomical location: lateral calf, not visualized below\n'
                 'Left GSV at the SFJ: reflux time (ms): 700 ms\nRight impression: reflux or absence: reflux positive.')
        answers = self.answers(notes)
        self.assert_ready(answers['measurement_15_2'], '700 ms')
        self.assert_ready(answers['sdt_-213273323'], 'reflux positive.')

    def test_an_unlabelled_heading_still_withholds_the_offers_below_it_on_the_qualified_form(self):
        notes = ('Right tributary row 11: anatomical location: lateral calf\nNone of the following:\n'
                 'Left GSV at the SFJ: reflux time (ms): 700 ms')
        answers = self.answers(notes)
        self.assert_needs_decision(answers['measurement_15_2'], '700 ms', 'None of the following:')
        # The candidate keeps the answer's OWN line (the Word review validates evidence per label); the governing line
        # is carried only as context. (`evidence` is the whole note here: the existing whole-note rule, unchanged.)
        self.assertEqual([entry['quote'] for entry in answers['measurement_15_2']['held_candidate']['evidence']], ['700 ms'])
        # Above the heading, the existing whole-note rule applies unchanged: a decision, with its one-click offer.
        self.assertEqual(answers['location_11'].get('suggestion'), 'lateral calf')
        # Third pass: the Word form's own guidance has no "Leave blank — reviewed".
        self.assertNotIn('Leave blank', answers['measurement_15_2']['held_candidate']['reason'])

    def test_an_unlabelled_sentence_or_erratum_withholds_the_offers_it_governs_on_the_qualified_form(self):
        """Fourth pass: an UNLABELLED line is read in full on the qualified form (suppression only: it already sends
        every answer back); only labelled lines are self-contained there."""
        line = 'Prior duplex from 2019 at another clinic is below.'
        answers = self.answers(line + '\nLeft GSV at the SFJ: reflux time (ms): 700 ms')
        self.assert_needs_decision(answers['measurement_15_2'], '700 ms', line)
        answers = self.answers('Left GSV at the SFJ: reflux time (ms): 700 ms\nCorrection: sides swapped.')
        self.assert_needs_decision(answers['measurement_15_2'], '700 ms', 'Correction: sides swapped.')

    def test_a_labelled_line_never_governs_on_the_qualified_form(self):
        """⚠️ THIRD PASS. Its labels carry colons, its signature statement's approved wording ends in `By:`, and an
        unanswered question ends in a colon: read as headings, each held every one of the 90 answers."""
        fields = self.FIELDS + [{'key': 'measurement_1_1', 'label': 'Right GSV at the SFJ: diameter (mm)', 'kind': 'measurement',
                                 'locator': {'row': 1, 'column': 1, 'unit': 'mm'}}]
        signature = 'Prewritten statement: Signature timestamp: Electronically Signed On <<insert date and time>> By:'
        base = ('Left GSV at the SFJ: reflux time (ms): 700 ms\nRight impression: reflux or absence: reflux positive.\n'
                'Right tributary row 11: anatomical location: lateral calf')
        heading = 'Right tributary row 11: anatomical location: none of the following:'
        for notes in (base + '\n' + signature, heading + '\n' + base.rsplit('\n', 1)[0]):
            with self.subTest(notes=notes):
                answers = generation.generate(notes, fields, FIXTURE, context_labels=['Prewritten statement: Signature timestamp'])[0]
                self.assert_ready(answers['measurement_15_2'], '700 ms')
                self.assert_ready(answers['sdt_-213273323'], 'reflux positive.')
        # An unanswered question already sends every answer back under the whole-note rule; its offers survive.
        for notes in ('Right GSV at the SFJ: diameter (mm):\n' + base, base + '\nRight GSV at the SFJ: diameter (mm):'):
            with self.subTest(notes=notes):
                answers = generation.generate(notes, fields, FIXTURE)[0]
                self.assertEqual(answers['measurement_15_2'].get('suggestion'), '700 ms', answers['measurement_15_2'])
                self.assertEqual(answers['sdt_-213273323'].get('suggestion'), 'reflux positive.')

    def test_a_correction_value_on_the_qualified_form_corrects_only_its_own_label(self):
        notes = ('Left GSV at the SFJ: reflux time (ms): 700 ms\n'
                 'Right tributary row 11: anatomical location: correction, lateral calf')
        self.assert_ready(self.answers(notes)['measurement_15_2'], '700 ms')


class TheDecisionIsEnforcedThroughFinalizationAndExport(DocumentWorkflow):
    """E1 on a real Word form, authenticated, through generate -> review -> finalize -> export."""
    NOTES = HEADING + '\nSymptoms: chest pain'
    TYPED = 'denies chest pain'

    def make_ros_docx(self):
        document = Document()
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = 'Review of systems'
        table.cell(1, 0).text = 'Symptoms'
        buffer = BytesIO(); document.save(buffer)
        return buffer.getvalue()

    def generated(self):
        template, mapping = self.upload(self.make_ros_docx(), 'docx')
        encounter = self.create_encounter(mapping, self.NOTES)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/generate/').status_code, 302)
        self.assertTrue(run_one())
        encounter.refresh_from_db()
        by_label = {f['label'].rstrip(':'): f['key'] for f in mapping.fields}
        self.ros, self.symptoms = by_label['Review of systems'], by_label['Symptoms']
        return encounter

    def save(self, encounter, **extra):
        payload = {'revision': encounter.revision,
                   'answer_' + self.ros: '', 'answer_' + self.symptoms: '',
                   'reviewed_' + self.ros: 'on', 'reviewed_' + self.symptoms: 'on'}
        payload.update(extra)
        self.assertEqual(self.client.post(f'/encounters/{encounter.pk}/save/', payload).status_code, 302)
        encounter.refresh_from_db()

    def finalize_attempt(self, encounter):
        return self.client.post(f'/encounters/{encounter.pk}/finalize/',
                                {'reviewed': 'on', 'revision': encounter.revision}, follow=True)

    def test_the_governed_finding_is_generated_as_a_decision_not_an_answer(self):
        encounter = self.generated()
        answer = encounter.answers[self.symptoms]
        self.assertEqual((answer['status'], answer['text']), ('conflict', ''))
        self.assertNotIn('suggestion', answer)
        self.assertEqual(answer['held_candidate']['text'], 'chest pain')

    def test_ticking_reviewed_alone_cannot_finalize_and_nothing_is_exported(self):
        encounter = self.generated()
        self.save(encounter)
        response = self.finalize_attempt(encounter)
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.status, 'finalized')
        self.assertContains(response, 'Symptoms')
        self.assertEqual(self.client.get(f'/encounters/{encounter.pk}/export/').status_code, 404)

    def test_the_held_candidate_cannot_be_accepted_by_a_crafted_post(self):
        encounter = self.generated()
        self.save(encounter, **{'accept_' + self.symptoms: 'on', 'accept_' + self.ros: 'on'})
        self.assertEqual(encounter.answers[self.symptoms]['text'], '')
        self.assertEqual(encounter.answers[self.symptoms]['status'], 'conflict')
        self.assertFalse(encounter.answers[self.symptoms].get('accepted_suggestion'))

    def test_a_typed_decision_finalizes_and_the_export_carries_it_not_the_candidate(self):
        encounter = self.generated()
        self.save(encounter, **{'answer_' + self.symptoms: self.TYPED,
                                'answer_' + self.ros: 'negative for chest pain'})
        exported = self.finalize(encounter)
        cells = [cell.text for row in Document(BytesIO(exported)).tables[0].rows for cell in row.cells]
        self.assertEqual(cells, ['Review of systems', 'negative for chest pain', 'Symptoms', self.TYPED])

    def section(self, encounter, label):
        page = self.client.get(f'/encounters/{encounter.pk}/').content.decode()
        sections = [part.split('</section>')[0] for part in page.split('<section class="answer">') if f'{label}</h3>' in part]
        self.assertEqual(len(sections), 1, f'expected exactly one {label} section')
        return sections[0]

    def test_the_page_shows_the_candidate_and_its_governing_line_with_no_accept_control(self):
        encounter = self.generated()
        section = self.section(encounter, 'Symptoms')
        self.assertIn('data-held-candidate', section)
        self.assertIn('not offered as an answer', section)
        self.assertIn('<blockquote class="suggestion-text">chest pain</blockquote>', section)
        self.assertIn('data-governing-line', section)
        self.assertIn(HEADING, section)
        self.assertNotIn(f'name="accept_{self.symptoms}"', section)
        self.assertNotIn('>chest pain</textarea>', section)

    def test_a_draft_generated_before_the_rule_cannot_finalize_the_denied_finding_on_a_tick(self):
        """What 02c29f99 stored for these notes, measured before the repair: both answers `supported`."""
        encounter = self.generated()
        value = HEADING.index('negative')
        finding = encounter.notes.index('chest pain')
        stale = {self.ros: {'text': 'negative for the following:', 'status': 'supported', 'reviewed': False,
                            'evidence': [{'quote': 'negative for the following:', 'start': value, 'end': len(HEADING)}]},
                 self.symptoms: {'text': 'chest pain', 'status': 'supported', 'reviewed': False,
                                 'evidence': [{'quote': 'chest pain', 'start': finding, 'end': finding + len('chest pain')}]}}
        Encounter.objects.filter(pk=encounter.pk).update(answers=stale)
        encounter.refresh_from_db()
        # A page opened before this release posts the pre-filled text back; the tick alone is the defect's whole gesture.
        self.save(encounter, **{'answer_' + self.ros: 'negative for the following:', 'answer_' + self.symptoms: 'chest pain'})
        self.assertEqual(encounter.answers[self.symptoms]['status'], 'supported')
        response = self.finalize_attempt(encounter)
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.status, 'finalized')
        self.assertContains(response, 'still need your decision: Review of systems, Symptoms.')
        self.assertEqual(self.client.get(f'/encounters/{encounter.pk}/export/').status_code, 404)
        # Third pass: THIS page shows each one held, as finalization will judge it: nothing pre-filled, the line shown.
        section = self.section(encounter, 'Symptoms')
        self.assertIn('data-held-candidate', section)
        self.assertIn(HEADING, section)
        self.assertNotIn('>chest pain</textarea>', section)
        self.assertIn(f'name="held_shown_{self.symptoms}"', section)
        # Typed on this page, the clinician's answer is their decision even in the candidate's own words.
        self.save(encounter, **{'answer_' + self.symptoms: self.TYPED, 'answer_' + self.ros: 'negative for the following:',
                                'held_shown_' + self.symptoms: '1', 'held_shown_' + self.ros: '1'})
        self.assertEqual(encounter.answers[self.ros]['status'], 'edited')
        exported = self.finalize(encounter)
        cells = [cell.text for row in Document(BytesIO(exported)).tables[0].rows for cell in row.cells]
        self.assertEqual(cells, ['Review of systems', 'negative for the following:', 'Symptoms', self.TYPED])

    def stale_offer(self, encounter, accepted=False):
        """What 02c29f99 stored for `Patient reports none of the following:` above `Symptoms: chest pain`: a conflict
        whose one-click suggestion the old gate allowed (`none` is not a denial word it knew)."""
        finding = encounter.notes.index('chest pain')
        own = [{'quote': 'chest pain', 'start': finding, 'end': finding + len('chest pain')}]
        symptoms = {'status': 'conflict', 'text': '', 'reviewed': False, 'suggestion': 'chest pain', 'suggestion_evidence': own,
                    'reason': 'Another line in this note may govern this answer.',
                    'evidence': [{'quote': encounter.notes, 'start': 0, 'end': len(encounter.notes)}]}
        if accepted:
            symptoms.update(status='edited', text='chest pain', accepted_suggestion=True, accepted_by=str(self.user.pk))
        Encounter.objects.filter(pk=encounter.pk).update(answers={self.ros: {'status': 'missing', 'text': '', 'evidence': [], 'reviewed': False},
                                                                  self.symptoms: symptoms})
        encounter.refresh_from_db()

    def test_a_pre_repair_offer_under_a_heading_is_no_longer_offered_or_accepted(self):
        self.NOTES = 'Patient reports none of the following:\nSymptoms: chest pain'
        encounter = self.generated()
        self.stale_offer(encounter)
        section = self.section(encounter, 'Symptoms')
        self.assertNotIn(f'name="accept_{self.symptoms}"', section)
        self.assertIn('data-held-candidate', section)
        response = self.client.post(f'/encounters/{encounter.pk}/save/', {'revision': encounter.revision,
            'answer_' + self.ros: '', 'answer_' + self.symptoms: '', 'accept_' + self.symptoms: 'on',
            'reviewed_' + self.ros: 'on', 'reviewed_' + self.symptoms: 'on'})
        self.assertEqual(response.status_code, 400)
        encounter.refresh_from_db()
        self.assertEqual((encounter.answers[self.symptoms]['status'], encounter.answers[self.symptoms]['text']), ('conflict', ''))

    def test_a_finalized_record_keeps_what_was_actually_offered(self):
        """Third pass: a finalized record is never re-described by a later release."""
        self.NOTES = 'Patient reports none of the following:\nSymptoms: chest pain'
        encounter = self.generated()
        self.stale_offer(encounter)
        self.save(encounter, **{'answer_' + self.symptoms: self.TYPED, 'answer_' + self.ros: 'none'})
        self.finalize(encounter)
        section = self.section(encounter, 'Symptoms')
        self.assertIn('This suggestion was offered and was not accepted.', section)
        self.assertNotIn('data-held-candidate', section)
        self.assertNotIn('data-governed-acceptance', section)

    def test_a_save_reads_the_notes_governance_once(self):
        from unittest.mock import patch
        self.NOTES = 'Patient reports none of the following:\nSymptoms: chest pain'
        encounter = self.generated()
        self.stale_offer(encounter)
        with patch('core.generation.heading_governance', wraps=generation.heading_governance) as reader:
            self.save(encounter, **{'answer_' + self.symptoms: self.TYPED, 'answer_' + self.ros: 'none'})
        self.assertEqual(reader.call_count, 1)

    def test_an_accepted_governed_offer_is_shown_held_and_decided_again_in_one_save(self):
        """Fourth pass: the page showed no governing line, and clearing the acceptance left an empty answer that
        finalized. Now: shown held with the line; an empty save keeps the act (still refused); a typed answer, even
        in the suggestion's own words, is a new decision; a page from before this release keeps the act."""
        self.NOTES = 'Patient reports none of the following:\nSymptoms: chest pain'
        encounter = self.generated()
        self.stale_offer(encounter, accepted=True)
        section = self.section(encounter, 'Symptoms')
        self.assertIn('data-governed-acceptance', section)
        self.assertIn('data-governing-line', section)
        self.assertIn('Patient reports none of the following:', section)
        self.assertNotIn('>chest pain</textarea>', section)
        marker = {'held_shown_' + self.symptoms: '1'}
        self.save(encounter, **marker)                         # the empty box, as rendered
        self.assertTrue(encounter.answers[self.symptoms]['accepted_suggestion'])
        self.assertContains(self.finalize_attempt(encounter), 'still need your decision: Symptoms.')
        encounter.refresh_from_db()
        self.save(encounter, **{'answer_' + self.symptoms: 'chest pain'})    # a page from before this release
        self.assertTrue(encounter.answers[self.symptoms]['accepted_suggestion'])
        self.save(encounter, **{'answer_' + self.symptoms: 'chest pain', **marker})
        self.assertFalse(encounter.answers[self.symptoms]['accepted_suggestion'])
        self.save(encounter, **{'answer_' + self.ros: 'none', 'answer_' + self.symptoms: 'chest pain'})
        exported = self.finalize(encounter)
        cells = [cell.text for row in Document(BytesIO(exported)).tables[0].rows for cell in row.cells]
        self.assertEqual(cells[-2:], ['Symptoms', 'chest pain'])

    def test_a_line_after_the_answer_is_shown_as_following_it(self):
        self.NOTES = 'Review of systems: negative for chest pain\nSymptoms: chest pain\nCorrection: the patient has no chest pain.'
        encounter = self.generated()
        section = self.section(encounter, 'Symptoms')
        self.assertIn('<strong>Followed by:</strong> <q>Correction: the patient has no chest pain.</q>', section)
        self.assertNotIn('>chest pain</textarea>', section)

    def test_a_governed_answer_cleared_to_nothing_needs_leave_blank(self):
        encounter = self.generated()
        self.save(encounter, **{'answer_' + self.symptoms: self.TYPED, 'answer_' + self.ros: 'negative for chest pain'})
        self.save(encounter, **{'answer_' + self.ros: 'negative for chest pain'})             # typed, then cleared
        self.assertEqual((encounter.answers[self.symptoms]['status'], encounter.answers[self.symptoms]['text']), ('edited', ''))
        response = self.finalize_attempt(encounter)
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.status, 'finalized')
        self.assertContains(response, 'still need your decision: Symptoms.')
        self.save(encounter, **{'answer_' + self.ros: 'negative for chest pain', 'blank_' + self.symptoms: 'on',
                                'blank_shown_' + self.symptoms: '1'})
        self.assertEqual(encounter.answers[self.symptoms]['status'], 'left_blank')
        exported = self.finalize(encounter)
        cells = [cell.text for row in Document(BytesIO(exported)).tables[0].rows for cell in row.cells]
        self.assertEqual(cells, ['Review of systems', 'negative for chest pain', 'Symptoms', ''])

    def test_a_stale_page_cannot_turn_the_prefilled_governed_text_into_a_decision_with_a_space(self):
        encounter = self.generated()
        value = HEADING.index('negative')
        finding = encounter.notes.index('chest pain')
        stale = {self.ros: {'text': 'negative for the following:', 'status': 'supported', 'reviewed': False,
                            'evidence': [{'quote': 'negative for the following:', 'start': value, 'end': len(HEADING)}]},
                 self.symptoms: {'text': 'chest pain', 'status': 'supported', 'reviewed': False,
                                 'evidence': [{'quote': 'chest pain', 'start': finding, 'end': finding + len('chest pain')}]}}
        Encounter.objects.filter(pk=encounter.pk).update(answers=stale)
        encounter.refresh_from_db()
        self.save(encounter, **{'answer_' + self.ros: 'negative for the following: ', 'answer_' + self.symptoms: 'chest pain '})
        self.assertEqual(encounter.answers[self.symptoms]['status'], 'supported')
        response = self.finalize_attempt(encounter)
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.status, 'finalized')
        self.assertContains(response, 'still need your decision: Review of systems, Symptoms.')

    def test_an_invisible_answer_is_saved_as_no_answer(self):
        encounter = self.generated()
        self.save(encounter, **{'answer_' + self.symptoms: '\u200b\u2800', 'answer_' + self.ros: 'none'})
        self.assertEqual(encounter.answers[self.symptoms]['text'], '')

    def test_a_stale_page_keeps_an_accepted_governed_suggestion_despite_a_space(self):
        self.NOTES = 'Patient reports none of the following:\nSymptoms: chest pain'
        encounter = self.generated()
        self.stale_offer(encounter, accepted=True)
        self.save(encounter, **{'answer_' + self.symptoms: 'chest pain '})
        self.assertTrue(encounter.answers[self.symptoms]['accepted_suggestion'])
        self.assertContains(self.finalize_attempt(encounter), 'still need your decision: Symptoms.')

    def test_a_governed_answer_cleared_on_a_stale_page_shows_its_lines(self):
        encounter = self.generated()
        finding = encounter.notes.index('chest pain')
        stale = {self.ros: {'text': 'none', 'status': 'edited', 'reviewed': False, 'evidence': []},
                 self.symptoms: {'text': 'chest pain', 'status': 'supported', 'reviewed': False,
                                 'evidence': [{'quote': 'chest pain', 'start': finding, 'end': finding + len('chest pain')}]}}
        Encounter.objects.filter(pk=encounter.pk).update(answers=stale)
        encounter.refresh_from_db()
        self.save(encounter, **{'answer_' + self.ros: 'none'})          # a page from before: the box cleared
        self.assertEqual((encounter.answers[self.symptoms]['status'], encounter.answers[self.symptoms]['text']), ('edited', ''))
        section = self.section(encounter, 'Symptoms')
        self.assertIn('data-governing-line', section)
        self.assertIn(HEADING, section)

    def test_a_stale_page_cannot_make_a_decision_with_an_invisible_character(self):
        encounter = self.generated()
        finding = encounter.notes.index('chest pain')
        stale = {self.ros: {'text': 'none', 'status': 'edited', 'reviewed': False, 'evidence': []},
                 self.symptoms: {'text': 'chest pain', 'status': 'supported', 'reviewed': False,
                                 'evidence': [{'quote': 'chest pain', 'start': finding, 'end': finding + len('chest pain')}]}}
        Encounter.objects.filter(pk=encounter.pk).update(answers=stale)
        encounter.refresh_from_db()
        self.save(encounter, **{'answer_' + self.ros: 'none', 'answer_' + self.symptoms: 'chest pain\u200b'})
        self.assertEqual(encounter.answers[self.symptoms]['status'], 'supported')

    def test_a_finalized_draft_from_an_earlier_release_says_it_was_filled_in(self):
        encounter = self.generated()
        finding = encounter.notes.index('chest pain')
        stale = {self.ros: {'text': 'none', 'status': 'edited', 'reviewed': False, 'evidence': []},
                 self.symptoms: {'text': 'chest pain', 'status': 'supported', 'reviewed': False,
                                 'evidence': [{'quote': 'chest pain', 'start': finding, 'end': finding + len('chest pain')}]}}
        Encounter.objects.filter(pk=encounter.pk).update(answers=stale)
        encounter.refresh_from_db()
        self.save(encounter, **{'answer_' + self.ros: 'none', 'answer_' + self.symptoms: self.TYPED, 'held_shown_' + self.symptoms: '1'})
        self.finalize(encounter)
        section = self.section(encounter, 'Symptoms')
        self.assertNotIn('never offered', section)
        self.assertIn('filled in by an earlier release', section)

    def test_an_earlier_release_offer_this_release_withholds_note_wide_cannot_be_accepted(self):
        self.NOTES = '\u25cf Correction: the following symptoms belong to another patient.\nSymptoms: chest pain'
        encounter = self.generated()
        self.stale_offer(encounter)
        section = self.section(encounter, 'Symptoms')
        self.assertNotIn(f'name="accept_{self.symptoms}"', section)
        response = self.client.post(f'/encounters/{encounter.pk}/save/', {'revision': encounter.revision,
            'answer_' + self.ros: '', 'answer_' + self.symptoms: '', 'accept_' + self.symptoms: 'on',
            'reviewed_' + self.ros: 'on', 'reviewed_' + self.symptoms: 'on'})
        self.assertEqual(response.status_code, 400)

    def test_an_oversized_answer_is_refused_before_it_is_read(self):
        import time
        encounter = self.generated()
        started = time.perf_counter()
        response = self.client.post(f'/encounters/{encounter.pk}/save/', {'revision': encounter.revision,
            'answer_' + self.symptoms: '\u2800' * 2000000, 'answer_' + self.ros: 'none'})
        self.assertEqual(response.status_code, 400)
        self.assertLess(time.perf_counter() - started, 5)

    def test_a_stale_page_cannot_make_a_decision_with_a_no_break_space(self):
        encounter = self.generated()
        finding = encounter.notes.index('chest pain')
        stale = {self.ros: {'text': 'none', 'status': 'edited', 'reviewed': False, 'evidence': []},
                 self.symptoms: {'text': 'chest pain', 'status': 'supported', 'reviewed': False,
                                 'evidence': [{'quote': 'chest pain', 'start': finding, 'end': finding + len('chest pain')}]}}
        Encounter.objects.filter(pk=encounter.pk).update(answers=stale)
        encounter.refresh_from_db()
        self.save(encounter, **{'answer_' + self.ros: 'none', 'answer_' + self.symptoms: 'chest\u00a0pain'})
        self.assertEqual(encounter.answers[self.symptoms]['status'], 'supported')

    def test_an_earlier_release_conflict_typed_then_cleared_needs_a_decision(self):
        self.NOTES = 'ROS: negative for the following:\nSymptoms: chest pain'
        encounter = self.generated()
        whole = {'quote': encounter.notes, 'start': 0, 'end': len(encounter.notes)}
        stale = {self.ros: {'text': 'none', 'status': 'edited', 'reviewed': False, 'evidence': []},
                 self.symptoms: {'text': '', 'status': 'conflict', 'reviewed': False, 'evidence': [whole]}}
        Encounter.objects.filter(pk=encounter.pk).update(answers=stale)
        encounter.refresh_from_db()
        self.save(encounter, **{'answer_' + self.ros: 'none', 'answer_' + self.symptoms: 'chest pain'})
        self.save(encounter, **{'answer_' + self.ros: 'none'})
        response = self.finalize_attempt(encounter)
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.status, 'finalized')
        self.assertContains(response, 'still need your decision: Symptoms.')

    def test_a_pre_repair_accepted_offer_under_a_heading_cannot_finalize(self):
        self.NOTES = 'Patient reports none of the following:\nSymptoms: chest pain'
        encounter = self.generated()
        self.stale_offer(encounter, accepted=True)
        self.save(encounter, **{'answer_' + self.symptoms: 'chest pain'})
        response = self.finalize_attempt(encounter)
        encounter.refresh_from_db()
        self.assertNotEqual(encounter.status, 'finalized')
        self.assertContains(response, 'still need your decision: Symptoms.')
