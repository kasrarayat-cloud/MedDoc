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


if __name__ == '__main__':
    unittest.main()
