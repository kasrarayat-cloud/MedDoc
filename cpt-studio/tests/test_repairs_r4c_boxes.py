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


if __name__ == '__main__':
    unittest.main()
