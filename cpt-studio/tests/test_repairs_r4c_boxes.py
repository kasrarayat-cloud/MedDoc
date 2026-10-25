"""Regressions for refutation round 5, BOXES' findings, repaired in round 4c: boxed status values, form-field answers,
the shared status-question grammar, status rows read by their own boxes, the separately identifiable E/M attestation,
the unread mark's question mark and the done-question reader's cost.

Each class reproduces one confirmed finding (regression:N, declared:N, extraction:N or bounded:N in the round-5 triage)
from its exact input, adds the variants the finding and its verifier list, and pins the positive controls an
over-correction would break. Routing runs for real, for the document's own service date and through the JSON round
trip the pipeline applies; the real validation engine assesses provider-shaped selections.

The hold-only rule (contract-r4c section 1) governs every rule here: a wording or layout rule may move a reading only to
uncertain (a hold with a non-silent cue), except where it restores the R4B-BASE (4347acd) or R3B-BASE (d05326ef)
reading, or reads an explicit box state. Synthetic text only.
"""
import time
import unittest

from studio.gi import detect
from tests.test_repairs_r4_boxes import BoxCase, EUS_LINE, EUS_NOTE
from tests.test_repairs_r3_forms_routing import outcome
from tests.test_repairs_status_r2_routing import HEADER, family, read, run_engine

NOT_TODAY = ('planned', 'historical', 'cancelled', 'negated')


# --- regression:0 -- a boxed status value whose checked option is a declared hold word ---------------------------------

R0_NOTE = (HEADER + 'Procedure: EUS with fine-needle aspiration of the pancreatic head mass\n{row}\nFindings: A 2.5 cm '
           'hypoechoic mass in the pancreatic head.\n')
R0_LINE = 'EUS with fine-needle aspiration of the pancreatic head mass'


class Regression0BoxedHoldWordTests(BoxCase):
    """regression:0 (critical, a regression of 7207d3038). A status value with boxes is read option by option, but its
    options were only the clause cues, act denials and reschedulings, never the status line's own declared hold words
    (_STATUS_HOLD: pending, TBD, TBA, requested, unknown, unclear, incomplete, on hold); with no option found the value
    denied nothing, so 'Status: Pending ☒ Completed ☐' left the EUS a ready 43242 that both earlier commits held. The hold
    words are options, and a boxed value with no option is read as text again."""
    CLAIMED = ('Status: Pending ☒ Completed ☐', 'Status: Incomplete ☒ Completed ☐',
               'Procedure status: On hold [x] Completed [ ]', 'Status: TBD ☒ Completed ☐', 'Status: Unknown ☒ Completed ☐',
               'Status: Unclear ☒ Completed ☐', 'Status: Requested ☒ Completed ☐', 'Status: TBA ☒ Completed ☐',
               'Status: Pending ☒', 'Procedure status: Pending ☒ Completed ☐',
               'Procedure status: Incomplete [x] Completed [ ]', 'Status: Incomplete [x] | Completed [ ]',
               'Status: Pending: ☒ Completed: ☐', 'Status: On hold ☒ Completed ☐ Cancelled ☐', 'Status: Unclear ☒',
               'Exam status: TBD ☒ Done ☐', 'Case status: Requested [x] Performed [ ]')
    # released at every earlier commit too, and d05326ef's hold of a third option
    OTHER_ORDERS = ('Status: Completed ☐ Pending ☒', 'Status: ☐ Completed ☒ Incomplete',
                    'Status: Completed ☐ Aborted ☐ Incomplete ☒', 'Status: ☐ Completed ☒ Pending ☐ Cancelled')

    def test_a_checked_hold_word_holds_the_service(self):
        for row in self.CLAIMED + self.OTHER_ORDERS:
            with self.subTest(row=row):
                text = R0_NOTE.format(row=row)
                self.assertNotEqual(family(text, 'gi.eus'), 'performed')
                self.assertNotIn(family(text, 'gi.eus'), NOT_TODAY)
                self.assert_held_reading(text, R0_LINE)
                self.assert_outcome(text, '43242', R0_LINE, 'held')

    def test_an_unchecked_hold_word_states_nothing(self):
        for row in ('Status: Pending ☐ Completed ☒', 'Status: Completed ☒ Pending ☐', 'Status: ☒ Completed ☐ Pending',
                    'Procedure status: On hold [ ] Completed [x]', 'Status: Completed ☒ | Incomplete ☐'):
            with self.subTest(row=row):
                text = R0_NOTE.format(row=row)
                self.assertEqual(family(text, 'gi.eus'), 'performed')
                self.assert_outcome(text, '43242', R0_LINE, 'ready')

    def test_a_boxed_value_with_no_option_is_read_as_text(self):
        """The text reading before 7207d3038: a completion holds nothing, a hold word without a box still holds."""
        for row, wanted in (('Status: Completed ☒', 'ready'), ('Status: ☒ Completed', 'ready'), ('Status: Pending', 'held'),
                            ('Status: Done [x]', 'ready'), ('Status: N/A ☒', 'held'), ('Status: ☒ N/A', 'held')):
            with self.subTest(row=row):
                self.assert_outcome(R0_NOTE.format(row=row), '43242', R0_LINE, wanted)


# --- declared:2 -- a checked box on a 'Not done' option ----------------------------------------------------------------

class Declared2CheckedNotDoneOptionTests(BoxCase):
    """declared:2 (critical, a regression against d05326ef). For a trailing box, _box_option_states read the option's
    own box through _group_state, whose yes/no rule took the option word 'Not done' for the 'No' of a yes/no pair: a
    checked 'Not done ☒' read as 'No checked', so 'off', and the cancelled EUS was a ready 43242; the mirror 'Completed ☒
    Not done ☐' was held. When the word before the box is the option's own, its own box decides."""
    CHECKED = ('Status: Not done [x]', 'Procedure status: Not done ☒', 'Completed ☐ | Not done ☒', 'Not done ☒',
               'Procedure status: Completed ☐ Not done ☒', 'Status: Done [ ] Not done [x]',
               'Procedure status: Performed ☐ Not performed ☒', 'Status: Completed ☐ Not done ☒ Cancelled ☐')

    def test_a_checked_not_done_option_holds(self):
        for row in self.CHECKED:
            with self.subTest(row=row):
                text = EUS_NOTE.format(row=row)
                self.assertNotEqual(family(text, 'gi.eus'), 'performed')
                self.assert_held_reading(text, EUS_LINE)
                self.assert_outcome(text, '43242', EUS_LINE, 'held')

    def test_an_unchecked_not_done_option_states_nothing(self):
        """The mirror rows read ready again, as at both earlier commits."""
        for row in ('Procedure status: Completed ☒ Not done ☐', 'Status: Done [x] Not done [ ]',
                    'Procedure status: Performed ☒ Not performed ☐', 'Status: Completed ☒ Not done ☐ Cancelled ☐'):
            with self.subTest(row=row):
                text = EUS_NOTE.format(row=row)
                self.assertEqual(family(text, 'gi.eus'), 'performed')
                self.assert_outcome(text, '43242', EUS_LINE, 'ready')

    def test_a_yes_no_pair_after_the_option_is_read_by_the_option_it_marks(self):
        """'Procedure cancelled: [ ] Yes [x] No' is unchanged: its yes/no words follow its boxes."""
        for row, wanted in (('Procedure cancelled: [ ] Yes [x] No', 'ready'), ('Procedure cancelled: Yes [ ] No [x]', 'ready'),
                            ('Procedure cancelled: No [x] Yes [ ]', 'ready'),
                            ('Procedure cancelled: [x] Yes [ ] No', ('held', 'excluded'))):
            with self.subTest(row=row):
                self.assert_outcome(EUS_NOTE.format(row=row), '43242', EUS_LINE, wanted)

    def test_the_option_reader_reads_the_options_own_box(self):
        an = detect._analysis(EUS_NOTE.format(row='Procedure status: Completed ☐ Not done ☒'))[0]
        lo = an.text.index('Completed')
        hi = an.text.index('\n', lo)
        options = detect._box_denying_options(an, lo, hi)
        words = options + [m.span() for m in detect._BOX_DONE_OPTION.finditer(an.text, lo, hi)]
        self.assertEqual(set(detect._box_option_states(an, lo, hi, options, words)), {'on'})



# --- regression:1 -- an untied form-field denial whose label names its item in other words -----------------------------

FIELD_COLO = (HEADER + 'Endoscopy Center - Colonoscopy Report (fillable)\nProcedure: Colonoscopy with polypectomy\n'
              '{printed}Findings: A 6 mm polyp in the ascending colon.\nThe colonoscope was advanced to the cecum.\n\n'
              '[PDF form fields on page 1]\n{fields}')
FIELD_EGD = (HEADER + 'Endoscopy Center - EGD Report (fillable)\nProcedure: EGD with biopsy\n{printed}Findings: The '
             'endoscope was advanced to the second part of the duodenum. Mild gastritis in the antrum.\n\n[PDF form fields '
             'on page 1]\n{fields}')
FIELD_EUS = (HEADER + 'Endoscopy Center - EUS Report (fillable)\nProcedure: EUS with fine-needle aspiration of a pancreatic '
             'cyst\n{printed}Findings: A 2 cm cyst in the pancreatic body.\n\n[PDF form fields on page 1]\n{fields}')
COLO_PICK = ('45385', 'Colonoscopy with polypectomy')
EGD_PICK = ('43239', 'EGD with biopsy')
EUS_PICK = ('43242', 'EUS with fine-needle aspiration of a pancreatic cyst')


class Regression1UntiedFieldDenialTests(BoxCase):
    """regression:1 (critical, a regression of 0c7059c58 against 4347acd). A denying field line whose label names its
    item in words the item reader does not know ('Polyps removed: No', 'Cecum reached: No', 'FNA performed: No') was
    given 'a label naming no item holds nothing', so the untied page hold 4347acd gave it was gone and the polypectomy,
    biopsy and FNA were ready. Such a label fails closed again (BOX_FIELD_ANSWER_UNTIED, a truthful cue), unless it is on
    the closed list of labels known to name no item, or it is a status question the reference readers answer."""
    UNTIED = ((FIELD_COLO, 'Were any polyps removed?   Yes   No\n', 'Polyps removed: No', COLO_PICK),
              (FIELD_COLO, '', 'Polyps removed: No', COLO_PICK),
              (FIELD_COLO, '', 'Polyps removed: Yes\nCecum reached: No', COLO_PICK),
              (FIELD_COLO, '', 'Exam complete: No', COLO_PICK),
              (FIELD_EGD, '', 'Specimens obtained: No', EGD_PICK),
              (FIELD_EGD, '', 'Tissue sampling: No', EGD_PICK),
              (FIELD_EUS, '', 'FNA performed: No', EUS_PICK),
              (FIELD_EUS, '', 'Scope inserted: No', EUS_PICK),
              (FIELD_EUS, '', 'Procedure done today: No', EUS_PICK),
              (FIELD_EUS, '', 'Patient consented?: No', EUS_PICK),
              (FIELD_EUS, '', 'Scope inserted: Not done', EUS_PICK),
              (FIELD_EUS, '', 'Specimen obtained: None', EUS_PICK),
              (FIELD_COLO, '', 'Remarks on cecal intubation: Not done', COLO_PICK))  # the closed list is read whole

    def test_an_untied_denial_holds_its_page(self):
        for template, printed, fields, (code, phrase) in self.UNTIED:
            with self.subTest(fields=fields, printed=bool(printed)):
                text = template.format(printed=printed, fields=fields)
                cues = self.assert_held_reading(text, phrase)
                self.assertNotIn('says its item was not done', ' '.join(cues))
                self.assert_outcome(text, code, phrase, 'held')

    def test_labels_known_to_name_no_item_hold_nothing(self):
        for fields in ('Complications: None', 'Complications: No', 'Complications (if any): None', 'Complications?: No',
                       'Any complications?: No', 'EBL: None', 'Estimated blood loss: None', 'Blood loss: None',
                       'Adverse events: None', 'Sedation: None', 'Anesthesia: None', 'Allergies: None',
                       'Comments: None', 'Notes: none', 'Remarks: No', 'EBL (mL): None'):
            with self.subTest(fields=fields):
                text = FIELD_COLO.format(printed='', fields=fields)
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assert_outcome(text, *COLO_PICK, 'ready')

    def test_answers_and_tied_rows_are_unchanged(self):
        for printed, fields in (('', 'Polyps removed: Yes\nCecum reached: Yes'),
                                ('Polyps removed:  ☐ Yes  ☒ No\nCecum reached:  ☒ Yes  ☐ No\n',
                                 'Polyps removed: No\nCecum reached: Yes')):  # a field tied to the row it opens
            with self.subTest(fields=fields):
                self.assert_outcome(FIELD_COLO.format(printed=printed, fields=fields), *COLO_PICK, 'ready')
        for fields in ('Biopsies taken: No', 'Polypectomy: No'):  # labels naming the item: as before
            with self.subTest(fields=fields):
                self.assert_outcome(FIELD_COLO.format(printed='', fields=fields), *COLO_PICK, 'held')

    def test_a_status_question_label_stays_with_the_reference_reader(self):
        """'Procedure cancelled: No' is the status-answer rule's (structure:13): held as a doubt, never excluded."""
        for fields in ('Procedure cancelled: No', 'Procedure aborted: No', 'Exam incomplete: No'):
            with self.subTest(fields=fields):
                text = FIELD_COLO.format(printed='', fields=fields)
                self.assertNotIn(family(text, 'gi.colonoscopy'), ('cancelled', 'negated', 'incomplete', 'performed'))
                self.assert_outcome(text, *COLO_PICK, 'held')
        text = FIELD_COLO.format(printed='', fields='Procedure cancelled: Yes')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'cancelled')

    def test_a_tied_status_question_beyond_the_further_denials_is_held(self):
        """Read as a field that fails closed, the printed row and the field line would both be held with no doubt, and
        the EUS nine lines above would be ready; the status-answer rule holds them as a doubt."""
        text = (HEADER + 'Procedure: EUS with fine-needle biopsy of a pancreatic cyst.\nIndication: Pancreatic cyst on '
                'CT.\nHistory reviewed.\nConsent obtained.\nASA class II.\nAirway assessed.\nAllergies: none known.\n'
                'Anticoagulants: none.\nNPO since midnight.\nProcedure cancelled: ☐ Yes ☒ No\n\n[PDF form fields on page '
                '1]\nProcedure cancelled: No')
        self.assertEqual(family(text, 'gi.eus'), 'uncertain')
        self.assert_outcome(text, '43242', 'EUS with fine-needle biopsy of a pancreatic cyst.', 'held')



# --- declared:0, 1, 9, 10 -- one grammar for the lines that ask whether the procedure was done or called off ----------

FIELD_PAGE = (HEADER + 'Procedure: EUS with fine-needle biopsy of a pancreatic cyst.\nIndication: Pancreatic cyst on CT.\n'
              'History reviewed.\nConsent obtained.\nASA class II.\nAirway assessed.\nAllergies: none known.\nAnticoagulants: '
              'none.\nNPO since midnight.\n{printed}\n\n[PDF form fields on page 1]\n{field}')
NEAR_PAGE = (HEADER + 'Procedure: EUS with fine-needle biopsy of a pancreatic cyst.\n{printed}\nIndication: Pancreatic cyst '
             'on CT.\n\n[PDF form fields on page 1]\n{field}')
FIELD_LINE = 'EUS with fine-needle biopsy of a pancreatic cyst.'
DONE_LABELS = ('Procedure performed?', 'Was the procedure performed?', 'Procedure performed today?', 'Procedure completed?',
               'Exam performed?', 'Study completed?', 'Procedure done?', 'Procedure attempted?', 'Endoscopy performed?',
               'Case completed?', 'PROCEDURE PERFORMED?', 'Was procedure performed?', 'Procedure performed',
               'Procedure completed today', 'Was the exam completed?', '- Procedure performed?')
CANCEL_LABELS = ('Procedure cancelled?', 'Was the procedure cancelled?', 'Procedure cancelled', 'Procedure aborted?',
                 'Was the procedure aborted?', 'Exam cancelled?')


class Declared0DoneQuestionFieldTests(BoxCase):
    """declared:0 (critical, a regression against 4347acd). A fillable PDF's done-question answered No arrives as
    '<label>?: No' (the label's own '?' before the block's ':'), and _BOX_DONE_QUESTION took exactly one separator, no
    'Was the', no 'today': the cancelled EUS was a ready 43242. The field reads the shared grammar: a status field."""

    def test_a_done_question_answered_no_holds_its_page(self):
        for label in DONE_LABELS:
            for answer in ('No', 'None', 'Not done', 'N', 'N/A'):
                for printed in ('', label + ' ☐ Yes ☒ No'):
                    with self.subTest(label=label, answer=answer, printed=bool(printed)):
                        text = FIELD_PAGE.format(printed=printed, field=f'{label}: {answer}')
                        self.assertNotEqual(family(text, 'gi.eus'), 'performed')
                        cues = self.assert_held_reading(text, FIELD_LINE)
                        self.assertIn('a status other than completed', ' '.join(cues))
                        self.assert_outcome(text, '43242', FIELD_LINE, 'held')

    def test_a_remark_after_the_answer(self):
        for field in ('Procedure performed?: No - the patient had eaten breakfast', 'Procedure performed: None today',
                      'Was the procedure performed?: No (see note)'):
            with self.subTest(field=field):
                self.assert_outcome(FIELD_PAGE.format(printed='', field=field), '43242', FIELD_LINE, 'held')

    def test_a_done_question_answered_yes_stays_ready(self):
        for label in DONE_LABELS[:6]:
            with self.subTest(label=label):
                text = FIELD_PAGE.format(printed=label + ' ☒ Yes ☐ No', field=f'{label}: Yes')
                self.assertEqual(family(text, 'gi.eus'), 'performed')
                self.assert_outcome(text, '43242', FIELD_LINE, 'ready')


class Declared1CancelQuestionFieldTests(BoxCase):
    """declared:1 (critical, a regression against 4347acd). A cancellation question answered No ('Procedure
    cancelled?: No') was no status answer, since the tail took one separator, and was read as a cancellation: the
    performed EUS was excluded. A printed question standing alone, its answer in the field block, was read the same way.
    Both hold (BOX_STATUS_ANSWER) and are never read as a cancellation."""

    def test_the_field_line_answered_no_holds(self):
        for label in CANCEL_LABELS:
            for answer in ('No', 'None', 'N', 'N/A', 'Not done'):
                with self.subTest(label=label, answer=answer):
                    text = FIELD_PAGE.format(printed='', field=f'{label}: {answer}')
                    self.assertNotIn(family(text, 'gi.eus'), NOT_TODAY + ('incomplete', 'performed'))
                    self.assert_outcome(text, '43242', FIELD_LINE, 'held')
        for field in ('Procedure cancelled? : No', 'Procedure cancelled:: No', 'Procedure cancelled?: no.'):
            with self.subTest(field=field):
                self.assert_outcome(FIELD_PAGE.format(printed='', field=field), '43242', FIELD_LINE, 'held')

    def test_a_printed_question_answered_in_its_field_holds(self):
        for page in (FIELD_PAGE, NEAR_PAGE):
            for label in CANCEL_LABELS:
                for printed in (label + ':' if not label.endswith('?') else label, label + ' ☐ Yes ☒ No'):
                    with self.subTest(label=label, printed=printed, near=page is NEAR_PAGE):
                        text = page.format(printed=printed, field=f'{label}: No')
                        self.assertNotIn(family(text, 'gi.eus'), NOT_TODAY + ('incomplete',))
                        self.assert_outcome(text, '43242', FIELD_LINE, ('held', 'ready'))

    def test_a_cancellation_still_cancels(self):
        for label in ('Procedure cancelled?', 'Procedure cancelled'):
            for printed in ('', label + ':'):
                with self.subTest(label=label, printed=printed):
                    text = FIELD_PAGE.format(printed=printed, field=f'{label}: Yes')
                    self.assertEqual(family(text, 'gi.eus'), 'cancelled')


EUS_STATUS_NOTE = (HEADER + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass.\n{row}\nIndication: '
                   'Pancreatic head mass on CT.\n')


class Declared9TypedDoneQuestionTests(BoxCase):
    """declared:9 (high). The typed done-question readers took no list marker, no 'Was the', no tab and no column
    gap, which the sibling status-question reader declares: '- Procedure performed: No' left a cancelled EUS ready."""
    ROWS = ('- Procedure performed: No (patient had eaten breakfast).', '1. Procedure performed: No',
            'Was the procedure performed? No', 'Procedure performed\tNo', 'Procedure performed    No',
            '- Procedure performed: ☐ Yes ☒ No', 'Was the procedure performed? ☐ Yes ☒ No', '* Procedure performed: No',
            '• Procedure performed: No', '2) Procedure performed: No', '- Procedure completed: No',
            'Was the procedure completed? No', 'Was the exam performed? No', 'Was the procedure done? no',
            '1. Procedure completed: [ ] Yes [x] No', '- Procedure performed: Not performed', '(1) Procedure performed: No',
            'a. Procedure performed: No', 'Procedure performed today: No', 'Procedure performed?: No',
            'Procedure attempted: No', '  Procedure performed: N/A', 'Procedure performed = No')

    def test_the_rows_hold(self):
        for row in self.ROWS:
            for where in ('below', 'above'):
                with self.subTest(row=row, where=where):
                    text = (EUS_STATUS_NOTE.format(row=row) if where == 'below' else
                            HEADER + row + '\nProcedure: EUS with fine-needle biopsy of the pancreatic head mass.\n')
                    self.assertNotEqual(family(text, 'gi.eus'), 'performed')
                    self.assert_outcome(text, '43242', EUS_LINE, 'held')

    def test_a_yes_stays_ready(self):
        for row in ('- Procedure performed: Yes', 'Was the procedure performed? Yes', 'Procedure performed\tYes',
                    '- Procedure performed: ☒ Yes ☐ No', 'Was the procedure performed? ☒ Yes ☐ No',
                    'Procedure performed today: Yes', 'Procedure performed. No complications.'):
            with self.subTest(row=row):
                self.assert_outcome(EUS_STATUS_NOTE.format(row=row), '43242', EUS_LINE, 'ready')


C10_NOTE = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\n{row}\nFindings: The colonoscope was advanced to '
            'the cecum. A 6 mm sigmoid polyp was removed with a cold snare.\nImpression: Sigmoid polyp.\n')
C10_POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'


class Declared10StatusAnswerRemarkTests(BoxCase):
    """declared:10 (high). A status question answered no with a remark ('Procedure cancelled: No - completed as
    planned.') or 'N/A' was read as a cancellation: the performed colonoscopy was excluded. The answer may be followed by
    a punctuated remark; 'no' opening a reason stays a cancellation."""

    def test_an_answer_with_a_remark_holds(self):
        for row in ('Procedure cancelled: No - completed as planned.', 'Procedure cancelled: No, completed.',
                    'Was the procedure cancelled? No, it was completed.', 'Procedure cancelled: No (completed)',
                    'Procedure cancelled: None - completed as planned.', 'Procedure aborted: No - completed.',
                    'Procedure cancelled: N/A', 'Procedure cancelled: Not applicable', 'Procedure cancelled: NA',
                    'Procedure cancelled: No; completed.', 'Procedure cancelled: No. Completed as planned.',
                    'Procedure cancelled today: No', '- Procedure cancelled: No – completed',
                    'Procedure cancelled: No - ' + 'the procedure was completed as planned without incident ' * 3):
            with self.subTest(row=row):
                text = C10_NOTE.format(row=row)
                self.assertNotIn(family(text, 'gi.colonoscopy'), NOT_TODAY + ('incomplete',))
                self.assert_outcome(text, '45385', C10_POLYP, ('held', 'ready'))

    def test_a_cancellation_with_a_reason_still_cancels(self):
        for row in ('Procedure cancelled: Yes', 'Procedure cancelled: no driver available.', 'Procedure cancelled.',
                    'Procedure cancelled - no IV access.', 'Procedure cancelled: No-show',
                    'Procedure cancelled, no sedation given.'):
            with self.subTest(row=row):
                self.assertEqual(family(C10_NOTE.format(row=row), 'gi.colonoscopy'), 'cancelled')


class OneStatusQuestionGrammarTests(unittest.TestCase):
    """contract-r4c section 4: the four readers of a line that asks whether the procedure was done or called off are
    built from one set of pieces, so a spelling one accepts every one accepts."""
    LEADS = ('', '  ', '- ', '* ', '• ', '1. ', '1) ', '(1) ', 'a. ', 'Was the ', 'Was ', 'Is the ')
    SEPARATORS = (': ', '?: ', '? : ', '? ', ' - ', ' – ', '\t', '    ', ' | ', ' = ', ':: ')
    ANSWERS = ('No', 'None', 'N', 'Not done', 'Not performed', 'N/A', 'NA', 'Not applicable')

    def test_every_reader_takes_every_spelling(self):
        for lead in self.LEADS:
            for sep in self.SEPARATORS:
                for answer in self.ANSWERS:
                    done = f'{lead}procedure performed{sep}{answer}'
                    asked = f'{lead}procedure performed{sep}☐ Yes ☒ No'
                    cancel_tail = f'{sep}{answer}'
                    with self.subTest(lead=lead, sep=sep, answer=answer):
                        self.assertTrue(detect._PERFORMED_ANSWERED_NO.match(done), done)
                        self.assertTrue(detect._BOX_DONE_QUESTION.match(done), done)
                        question = detect._PERFORMED_QUESTION.match(asked)
                        self.assertTrue(question and asked[question.end():].lstrip(' \t:?=|–-').startswith('☐'), asked)
                        self.assertTrue(detect._BOX_ANSWER_LEAD.fullmatch(lead), lead)
                        self.assertTrue(detect._BOX_ANSWER_TAIL.match(cancel_tail), cancel_tail)

    def test_no_reader_takes_a_yes_or_a_sentence(self):
        for line in ('Procedure performed: Yes', 'Procedure performed: Normal', 'Procedure performed. No complications.',
                     'Procedure performed without complications', 'Biopsy performed: No'):
            with self.subTest(line=line):
                self.assertFalse(detect._PERFORMED_ANSWERED_NO.match(line), line)
        for tail in (': Yes', ': no driver available.', ' - no IV access.', ': No-show', ', no sedation given.'):
            with self.subTest(tail=tail):
                self.assertFalse(detect._BOX_ANSWER_TAIL.match(tail), tail)




# --- regression:4 -- a status reference on an option whose own box is unchecked ----------------------------------------

R4_COLON = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\n{row}\nThe colonoscope was advanced to the cecum. A '
            '6 mm polyp was removed with a cold snare.\n')
R4_EUS = (HEADER + 'Procedure: EUS with fine-needle biopsy of the pancreatic head mass\n{row}\nThe echoendoscope was advanced '
          'to the duodenum. FNB of the pancreatic head mass was performed.\n')
R4_COLON_LINE = 'Colonoscopy with cold snare polypectomy'
R4_EUS_LINE = 'EUS with fine-needle biopsy of the pancreatic head mass'


class Regression4OwnOptionBoxTests(BoxCase):
    """regression:4 (high, declared misreading). _references read the bare 'Aborted' of 'Status: Completed ☒ Aborted ☐
    Cancelled ☐' by its item orientation: the boxes lead, so the box before it, Completed's ☒, was its own, and the
    unchecked 'Cancelled' option's cue decided: the completed colonoscopy was cancelled and 45385 excluded. A status
    reference whose own option box (read by the line's option words) is unchecked states nothing."""
    ROWS = ('Status: Completed ☒ Aborted ☐ Cancelled ☐', 'Procedure status: Completed [x] Aborted [ ] Cancelled [ ]',
            'Status: Completed: ☒ Aborted: ☐ Cancelled: ☐', 'Status: Completed ☒ | Aborted ☐ | Cancelled ☐',
            'Status: Completed (x) Aborted ( ) Cancelled ( )', 'Status: Completed ☒ Aborted ☐ Terminated ☐',
            'Status: Done ☒ Aborted ☐ Cancelled ☐', 'Status: Completed ☒ Aborted ☐ Postponed ☐',
            'Procedure completed ☒ | Procedure cancelled ☐', 'Procedure completed: ☒ Procedure cancelled: ☐',
            'Status: Completed ☒ Aborted ☐ Cancelled ☐ Rescheduled ☐', 'Status: | Completed ☒ | Aborted ☐ | Cancelled ☐',
            'Status: | Completed | ☒ | Aborted | ☐ | Cancelled | ☐', 'Status: Completed ☑ Aborted ❑ Cancelled ❑')

    def test_an_unchecked_option_never_cancels_or_aborts(self):
        for template, line, code, slug in ((R4_COLON, R4_COLON_LINE, '45385', 'gi.colonoscopy'),
                                           (R4_EUS, R4_EUS_LINE, '43242', 'gi.eus')):
            for row in self.ROWS:
                with self.subTest(row=row, slug=slug):
                    text = template.format(row=row)
                    if row == 'Procedure completed: ☒ Procedure cancelled: ☐':
                        # at worst held (the finding's own bound): the short-line test still reads its six words
                        self.assertNotIn(family(text, slug), NOT_TODAY + ('incomplete',))
                        self.assert_outcome(text, code, line, ('ready', 'held'))
                        continue
                    self.assertEqual(family(text, slug), 'performed')
                    self.assert_outcome(text, code, line, 'ready')

    def test_a_checked_denying_option_still_holds(self):
        for row in ('Status: Completed ☐ Aborted ☒ Cancelled ☐', 'Status: Completed ☐ Aborted ☐ Cancelled ☒',
                    'Status: Completed ☐ Aborted ☐ Terminated ☒', 'Procedure completed ☐ | Procedure cancelled ☒',
                    'Status: Completed ☒ Aborted ☒ Cancelled ☐', 'Status: Completed ☒ Aborted [?] Cancelled ☐'):
            with self.subTest(row=row):
                text = R4_COLON.format(row=row)
                self.assertNotEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assert_outcome(text, '45385', R4_COLON_LINE, ('held', 'excluded'))

    def test_the_status_row_cited_as_evidence_is_never_a_cancellation(self):
        """A code citing the row itself reads a hold, never the unchecked options' words as a cancellation."""
        for row in ('Status: Performed | ☑ | Procedure aborted | ❏ | Procedure cancelled | ( )',
                    'Completed ☒ | Procedure aborted [ ] | Postponed [ ]', 'Status: Completed ☒ Aborted ☐ Cancelled ☐'):
            with self.subTest(row=row):
                text = R4_COLON.format(row=row)
                status, cues = read(text, row)
                self.assertNotIn(status, NOT_TODAY + ('incomplete',), cues)
                self.assert_outcome(text, '45385', row, ('held', 'ready'))

    def test_an_option_with_no_box_of_its_own_is_read_as_written(self):
        """Only an option's own unchecked box makes it state nothing; a denial with no box is a statement (5.3: a
        denying option that has no box holds), here past the six sentences, where only the reference reader sees it."""
        for row in ('Procedure cancelled, Completed ☒', 'Procedure aborted; Completed ☒',
                    'Procedure cancelled (patient ate) | Completed ☒'):
            with self.subTest(row=row):
                text = FIELD_PAGE.split('{printed}')[0] + row + '\n'
                self.assertNotEqual(family(text, 'gi.eus'), 'performed')

    def test_leading_rows_and_an_abort_without_its_own_box(self):
        for row in ('Status: ☒ Completed ☐ Aborted ☐ Cancelled', 'Status: Completed ☒ Cancelled ☐ Aborted ☐'):
            with self.subTest(row=row):
                self.assert_outcome(R4_COLON.format(row=row), '45385', R4_COLON_LINE, 'ready')
        # an abort with no box of its own is read as before
        text = R4_COLON.format(row='Procedure aborted due to poor preparation.')
        self.assertNotEqual(family(text, 'gi.colonoscopy'), 'performed')



# --- declared:8 -- a checked 'Not performed' option on a line naming no item ---------------------------------------------

class Declared8CheckedNotPerformedOptionTests(BoxCase):
    """declared:8 (high). _OPTION_LABEL explains the 'not' of any 'Not performed' written beside a box, whatever the
    box's state, so '☒ Not performed' under the procedure line denied nothing and the EUS was a ready 43242 (no cue
    covers 'not performed', unlike 'not done'). On a line naming no item, a 'Not performed' or 'Not done' option whose own
    box is checked, unread or disagrees holds the service above it."""
    CHECKED = ('☒ Not performed', '[x] Not performed', '☐ Performed ☒ Not performed', '[ ] Performed [x] Not performed',
               'Performed ☐ Not performed ☒', 'Not performed ☒', '☑ Not performed', '[X] Not performed.',
               '☒ Not performed - patient ate breakfast', '(x) Not performed', 'Not performed: ☒', 'Not performed | ☒',
               '☒ Performed ☒ Not performed', '[?] Not performed', 'Completed | ☐ | Not done | ☒')

    def test_a_selected_denial_option_holds(self):
        for row in self.CHECKED:
            with self.subTest(row=row):
                text = EUS_NOTE.format(row=row)
                self.assertNotEqual(family(text, 'gi.eus'), 'performed')
                self.assert_held_reading(text, EUS_LINE)
                self.assert_outcome(text, '43242', EUS_LINE, 'held')

    def test_an_unselected_option_and_another_acts_denial_state_nothing(self):
        for row in ('☐ Not performed', '☒ Performed ☐ Not performed', 'Performed ☒ Not performed ☐',
                    '[x] Performed [ ] Not performed', 'Completed | ☒ | Not done | ☐',
                    '☒ Retroflexion not performed', '☒ Sedation not given', '☒ Patient declined anesthesia',
                    'Biopsy: [x] Not performed', '☒ Photos not taken'):
            with self.subTest(row=row):
                text = EUS_NOTE.format(row=row)
                self.assertEqual(family(text, 'gi.eus'), 'performed')
                self.assert_outcome(text, '43242', EUS_LINE, 'ready')


# --- bounded:3 and contract-r4c section 6 -- every changed reader is bounded per line ---------------------------------

class Bounded3ScaleTests(unittest.TestCase):
    """bounded:3 (high). _performed_answer_denies read the whole line's boxes once per sentence _called_off_further
    read, so 'Procedure performed: ☒ Yes ☐ No. ' + 'EGD. ' * 2000 on one line took 74 s (4347acd: 0.5 s) and failed the
    analyze stage. It is read once per line; each reader changed in round 4c is timed on a long line of its trigger."""

    def timed(self, text, budget):
        started = time.monotonic()
        result = detect.route(text)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, budget, (len(text), elapsed))
        return result

    def test_the_claimed_lines_are_linear(self):
        egd = self.timed(HEADER + 'Procedure performed: ☒ Yes ☐ No. ' + 'EGD. ' * 2000, 15).finding('gi.egd')
        self.assertEqual(egd.status, 'performed')
        egd = self.timed(HEADER + 'Procedure performed: ☐ Yes ☒ No. ' + 'EGD. ' * 4000, 12).finding('gi.egd')
        self.assertEqual(egd.status, 'uncertain')

    def test_long_lines_of_the_round_4c_triggers(self):
        for name, unit in (('status values', 'Status: Pending ☒ Completed ☐ EGD. '),
                           ('own option boxes', 'Procedure status: Completed ☐ Not done ☒ EGD. '),
                           ('done questions', '- Was the procedure performed today?: No (see note). EGD. '),
                           ('status answers', 'Procedure cancelled: No - completed as planned; EGD. '),
                           ('boxed questions', 'Was the procedure performed? ☐ Yes ☒ No EGD. ')):
            with self.subTest(name):
                self.timed(HEADER + 'Procedure: EGD.\n' + (unit * 5000)[:50000], 10)

    def test_a_form_block_of_questions_and_labels(self):
        printed = ''.join(f'Procedure cancelled? ☐ Yes ☒ No {n}\nPolyps removed {n}:\n' for n in range(1500))
        block = ''.join(f'Procedure cancelled?: No\nPolyps removed {n}: No\nComplications {n}: None\n' for n in range(1500))
        self.timed(HEADER + 'Procedure: Colonoscopy with polypectomy.\n' + printed + '\n[PDF form fields on page 1]\n'
                   + block, 15)


if __name__ == '__main__':
    unittest.main()
