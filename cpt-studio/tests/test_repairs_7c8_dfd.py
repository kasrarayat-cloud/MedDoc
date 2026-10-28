"""Repair round 7c8, the differential round's dates track (DF-DATES; studio/gi/context.py, the service date).

The differential round asked one bounded question of the final refutation's fix round (c3c034a08..004bf808c): does
004bf808c do anything WORSE than c3c034a08 in a must-fix class? Six date shapes did - a request carrying a date
c3c034a08 did not send, or a member date taken that it held - each demonstrated by the lens and reproduced by an
independent verifier end to end (POST /api/encounters and POST /context with the suite's FakeProvider). Each is
reproduced here first, then repaired by narrowing the fix round's rule that caused it, or by restoring c3c034a08's
reading of that shape, while the final refutation's finding that rule repaired stays closed - or closes in the safe
direction (the date asked, the member date held):

df-d:0  (fr-dr:1, the stack) an 'other' label's place could hold no date alone, so a complete stack whose other label
        has a date ("Patient DOB:", "Referral date:", "Date signed:") was unplaceable, and a date label last in it read
        the line right below it - the first label's date of birth or referral date; a date label's place holding a
        date and more ("10/14/2026 (done)") made it read a name there and fall silent.
df-d:1  (fr-dr:1, the column) a row whose date-of-service cell is no date alone ("TBD") was unplaced for every label of
        its header, so the cell under "DOB" was no longer a date of birth and a dated service line read it as its date.
df-d:3  (fr-dr:1 with fr-dr:0) a date-of-service column cell of digits that are no date with separators ("20261014")
        made the unplaced row state no date: silent, where c3c034a08 asked.
df-d:2  (fr-dr:2) any bracket but a format after a subject line's "Date" or date-of-service label made the field
        another field's, so "Date (performed): 10/21/2026" was silenced and the labelled 10/14 it contradicts sent.
df-d:4  (fr-di:0, fr-dr:4) a date of birth beside a qualifier no longer passed the qualifier over, so the labelled date
        was read as another occurrence's - silent - and another plain label's date was sent.

Synthetic text only; no network (the suite's FakeProvider).
"""
from django.test import SimpleTestCase

from tests.test_repairs_7c8_context import DateAssertions
from tests.test_repairs_7c8_context3 import COLO_PLAIN, ELENA_DATE, HEAD, EndToEnd, date_fact, evidence_text

BIRTH = '01/01/1998'


# --- df-d:0: a complete stack whose places do not fit is never read by the line below its date label ------------------

DATED_OTHER_LABELS = (  # a label of no date kind whose value is a date: (its line, its value, that value as a member's)
    ('Patient DOB:', BIRTH, ELENA_DATE),
    ('Pt DOB:', BIRTH, ELENA_DATE),
    ('Member DOB:', BIRTH, ELENA_DATE),
    ('Patient date of birth:', BIRTH, ELENA_DATE),
    ('Referral date:', '10/13/2026', '2026-10-13'),
    ('Admission date:', '10/13/2026', '2026-10-13'),
    ('Date signed:', '10/27/2026', '2026-10-27'),
)
DATE_LABELS = ('Date of service:', 'DOS:', 'Procedure date:')
MORE_THAN_A_DATE = ('10/14/2026 (done)', '10/14/2026 0830', '10/14/2026 - see report')


class StackOfAnotherDatedLabelTests(DateAssertions, SimpleTestCase):
    """df-d:0 (d8ad4bd92, the final refutation's fr-dr:1): a stack's value line must fit its label's kind - a date or
    birth label's place holds a date alone, any other label's place none - so a heading or a findings line counted into
    the stack is caught. "Patient DOB:", "Referral date:", "Admission date:" and "Date signed:" are labels of the
    'other' kind whose values ARE dates, so a complete stack ("Patient DOB:" / "Date of service:" over "01/01/1998" /
    "10/14/2026") did not fit either; and with the date label last, _stacked_value then read the line right below it -
    the FIRST label's place - so the date of birth or the referral date was the date label's value: a member's
    1998-01-01 or 10/13 was taken and sent where c3c034a08 held it. A date label's place holding a date and more
    ("10/14/2026 (done)", "10/14/2026 0830") read the line below it too - a name - and fell silent, so "Date of service:
    10/07/2026" beside it was sent where c3c034a08 asked. A stack whose every label has its value line, but whose places
    do not fit, is never read by the line below its date label: a date anywhere in its values is asked (the label alone
    kept, no date a member's answer agrees with). fr-dr:1's place rule stands - a heading over the stack still shifts a
    date into a place of the other kind and is caught - so the stack's own 10/14 is asked too: a member's 10/14 is held
    there (safe direction; at c3c034a08 it was taken), and agrees where the note labels it elsewhere."""

    def test_the_other_label_s_date_is_never_the_date_label_s_value(self):
        for other, value, member in DATED_OTHER_LABELS:
            for label in DATE_LABELS:
                for above in ('Colonoscopy report\n', 'Colonoscopy report\nDate of service: 10/14/2026\n'):
                    text = HEAD + above + f'{other}\n{label}\n{value}\n10/14/2026\n' + COLO_PLAIN
                    with self.subTest(other=other, label=label, above=above.count('\n')):
                        self.assert_never(text, member)
                        self.assertIn(date_fact(text).origin, ('conflict', 'missing'))
                        self.assert_member_conflict(text, member)
                        self.assertFalse(any(value in quoted for quoted in evidence_text(text)), evidence_text(text))
                        if 'Date of service: 10/14/2026' in above:  # the note's labelled date answers
                            self.assert_member_date(text, '2026-10-14')

    def test_the_verifier_s_smallest_form(self):
        text = HEAD + 'Patient DOB:\nDOS:\n01/01/1998\n10/14/2026\nColonoscopy: a 5 mm polyp was removed with a cold snare.\n'
        self.assert_never(text, ELENA_DATE)
        self.assert_member_conflict(text, ELENA_DATE)

    def test_a_date_label_s_place_holding_more_than_a_date_is_asked(self):
        for cell in MORE_THAN_A_DATE:
            for label in DATE_LABELS:
                text = (HEAD + 'Colonoscopy report\nDate of service: 10/07/2026\nPatient:\n' + label
                        + '\nSynthetic, Alex\n' + cell + '\n' + COLO_PLAIN)
                with self.subTest(cell=cell, label=label):
                    self.assert_never(text, '2026-10-07')
                    self.assertIn(date_fact(text).origin, ('conflict', 'missing'))
                    self.assert_member_date(text, '2026-10-07')
                    self.assert_member_conflict(text, ELENA_DATE)

    def test_a_date_label_line_of_the_other_kind_never_reads_the_first_label_s_place(self):
        # "Date of Service (DOS):" alone on its line reads as a label of the 'other' kind: last in a stack under "DOB:"
        # or "Referral date:" it read the line right below it - the date of birth or the referral date - as its value
        for first, value, member in (('DOB:', '01/01/1998 (age 28)', ELENA_DATE), ('Referral date:', '10/13/2026',
                                                                                   '2026-10-13')):
            for label in ('Date of Service (DOS):', 'Date of service:'):
                text = HEAD + 'Colonoscopy report\n' + first + '\n' + label + '\n' + value + '\n10/14/2026\n' + COLO_PLAIN
                with self.subTest(first=first, label=label):
                    self.assert_never(text, member)
                    self.assert_member_conflict(text, member)
                    self.assertFalse(any(value[:10] in quoted for quoted in evidence_text(text)), evidence_text(text))

    def test_the_lens_s_three_label_stack_beside_another_labelled_date_is_asked(self):
        for text in (HEAD + 'Colonoscopy report\nDate of service: 10/07/2026\nPhysician:\nDate signed:\nProcedure date:\n'
                     'Dr. Robin Synthetic\n10/27/2026\n10/14/2026\n' + COLO_PLAIN,
                     HEAD + 'Colonoscopy report\nDate of service: 10/07/2026\nPatient:\nPatient DOB:\nDate of service:\n'
                     'Synthetic, Alex\n01/01/1998\n10/14/2026\n' + COLO_PLAIN):
            with self.subTest(text=text.splitlines()[3:6]):
                self.assert_never(text, '2026-10-07')
                self.assertIn(date_fact(text).origin, ('conflict', 'missing'))
                self.assert_member_conflict(text, ELENA_DATE)
                self.assert_member_conflict(text, '2026-10-27')

    def test_controls(self):
        # a stack of label kinds that fits: its own value answers, a date of birth never does
        for rows in ('Patient:\nDOB:\nDate of service:\nSynthetic, Alex\n01/01/1998\n10/14/2026\n',
                     'Physician:\nDate of service:\nDr. Robin Synthetic\n10/14/2026\n',
                     'Date of service:\nDOB:\n10/14/2026\n01/01/1998\n'):
            text = HEAD + rows + COLO_PLAIN
            with self.subTest(rows=rows.splitlines()[:2]):
                self.assert_member_date(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)
        # fr-dr:1's shifted stacks (a heading counted as a label, a findings line or a date counted as a value) stay
        # unplaced: the date of birth is never the label's value
        for rows in ('PATIENT INFORMATION:\nDate of service:\nDOB:\n10/14/2026\n01/01/1998\n'
                     '1.5 cm sigmoid polyp removed with a cold snare.\n',
                     'PATIENT INFORMATION:\nDate of service:\nDOB:\n10/14/2026\n01/01/1998\n10/20/2026\n',
                     'INFO:\nDOS:\nDOB:\n10/14/2026\n01/01/1998\n1.5 cm polyp.\n',
                     'Date of service:\nDOB:\n01/01/1998\n3/4 of the colon was prepped.\n'):
            for top in ('Colonoscopy report - 10/14/2026\n', ''):
                text = HEAD + top + rows + COLO_PLAIN
                with self.subTest(rows=rows.splitlines()[:2], top=bool(top)):
                    self.assert_member_conflict(text, ELENA_DATE)
                    self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))
        # a stack whose date label states no date stays silent: the labelled date beside it is the note's own
        text = (HEAD + 'Colonoscopy report\nDate of service: 10/07/2026\nPatient:\nDate of service:\nSynthetic, Alex\n'
                'N/A\n' + COLO_PLAIN)
        self.assert_document(text, '2026-10-07')


class StackOfAnotherDatedLabelRequestTests(EndToEnd):
    D1 = HEAD + 'Colonoscopy report\nPatient DOB:\nDate of service:\n01/01/1998\n10/14/2026\n' + COLO_PLAIN
    S4 = (HEAD + 'Colonoscopy report\nDate of service: 10/07/2026\nPatient:\nDate of service:\nSynthetic, Alex\n'
          '10/14/2026 (done)\n' + COLO_PLAIN)

    def test_d1_the_member_s_date_of_birth_is_held(self):
        held = self.finished(self.D1, service_date=ELENA_DATE)
        self.assert_held(held)
        self.assert_never_sent(held, ELENA_DATE)
        encounter_id = self.finished(self.D1)  # dateless, then the answer path
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assertEqual(self.dates_sent(encounter_id), [[]])

    def test_s4_no_other_labelled_date_is_sent(self):
        encounter_id = self.finished(self.S4)
        self.assertEqual(self.dates_sent(encounter_id), [[]])


# --- df-d:1: the cell under a birth head is a date of birth whatever the date-of-service cell holds -------------------

UNDATED_DOS_CELLS = ('TBD', 'pending', 'N/A', 'today', 'see below', '2026', '20261014')


def aligned(*cells, width=19):
    """One space-aligned row: each cell but the last padded to ``width`` characters."""
    return ''.join(cell.ljust(width) for cell in cells[:-1]) + cells[-1]


def birth_column(layout, cell):
    """A header with a "DOB" column over a row naming the service, its date-of-service cell ``cell``."""
    if layout == 'tabs':
        return 'Procedure\tDate of Service\tDOB\nColonoscopy\t' + cell + '\t' + BIRTH + '\n'
    heads, first, width = {'spaces': (('Procedure', 'Date of Service', 'DOB'), 'Colonoscopy', 19),
                           'short heads': (('Exam', 'DOS', 'DOB'), 'Colonoscopy', 14),
                           'a subject row': (('Re', 'Date of Service', 'DOB'), 'Re: Colonoscopy', 19)}[layout]
    return aligned(*heads, width=width) + '\n' + aligned(first, cell, BIRTH, width=width) + '\n'


BIRTH_LAYOUTS = ('spaces', 'tabs', 'short heads', 'a subject row')


class BirthColumnBesideAnUndatedCellTests(DateAssertions, SimpleTestCase):
    """df-d:1 (826fcff2d and d8ad4bd92, the final refutation's fr-dr:1): an aligned row is placed for a header's labels
    only where each cell lies under its own head and every date or birth label's column holds a date alone - tests of
    where a date-of-service label's VALUE is (narrow heads over wide cells shift the date of birth into its column).
    _birth_cells read the same placement, so a date-of-service cell that is no date ("TBD", "pending", "N/A", "today",
    "see below", "2026") - or a tab-separated row, whose character offsets need not line up with its header's - left the
    row unplaced for the "DOB" label too, and the cell under it was no longer a date of birth: the row's dated service
    line ("Colonoscopy  TBD  01/01/1998") read it as its own date, and a member's 1998-01-01 was taken and sent - on
    upload and on the answer path - where c3c034a08, placing it by count, held it. A birth label's cell is placed by
    POSITION whatever the other columns hold (the date-alone test is the date label's), and by count alone where the
    cells do not lie under their heads: such a date is no value and no member's agreement either, but - as it may as
    well be a shifted date of the row's own - a dated line stating it is asked, never silent."""

    def test_the_date_of_birth_is_never_the_row_s_date(self):
        for layout in BIRTH_LAYOUTS:
            for cell in UNDATED_DOS_CELLS:
                text = HEAD + birth_column(layout, cell) + COLO_PLAIN
                with self.subTest(layout=layout, cell=cell):
                    self.assert_never(text, ELENA_DATE)
                    self.assert_member_conflict(text, ELENA_DATE)
                    self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))

    def test_beside_the_labelled_date_the_member_s_date_of_birth_is_held(self):
        for cell in UNDATED_DOS_CELLS:
            text = (HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\n' + birth_column('a subject row', cell)
                    + COLO_PLAIN)
            with self.subTest(cell=cell):
                self.assert_member_conflict(text, ELENA_DATE)
                self.assert_member_date(text, '2026-10-14')

    def test_the_verifier_s_smallest_forms(self):
        for rows in ('DOS      DOB\nEGD TBD  01/01/1998\n', 'Exam  DOS  DOB\nEGD  TBD  01/01/1998\n'):
            text = HEAD + rows
            with self.subTest(rows=rows):
                self.assert_member_conflict(text, ELENA_DATE)

    def test_a_row_placed_by_count_alone_is_asked(self):
        # cells that do not lie under their heads (a cell split at a double space, a cell left empty; tabs): the date
        # under "DOB" by count is no member's answer, and the subject line stating it is asked beside the labelled
        # date - c3c034a08 marked it a date of birth, silencing the line, and sent the labelled 10/07
        for rows in (aligned('Re', 'Exam', 'DOB', width=23) + '\nRe: Colonoscopy  EGD   10/14/2026\n',
                     'Re\tExam\tDOB\nRe: Colonoscopy\tEGD\t10/14/2026\n'):
            text = HEAD + 'Colonoscopy report\nDate of service: 10/07/2026\n' + rows + COLO_PLAIN
            with self.subTest(rows=rows.splitlines()[0]):
                self.assert_never(text, '2026-10-07')
                self.assert_member_date(text, '2026-10-07')
                self.assert_member_conflict(text, '2026-10-14')

    def test_controls(self):
        # a dated cell under the date-of-service head: its own value answers, the date of birth never does
        for rows in ('Exam  DOS  DOB\nEGD  10/14/2026  01/01/1998\n',
                     birth_column('spaces', '10/14/2026')):
            text = HEAD + rows + COLO_PLAIN
            with self.subTest(rows=rows.splitlines()[0]):
                self.assert_member_date(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)
        # fr-dr:1's shifted columns: the date of birth is still never the date-of-service label's value
        for rows in ('Patient            DOB           Date of Service    Endoscopist\n'
                     'Synthetic,  Alex   01/01/1998    10/14/2026\n',
                     'Patient   DOB   DOS   X\nSynthetic,  Alex   01/01/1998   10/14/2026\n',
                     'Patient    DOB    DOS\nDoe,  Jane    01/01/1998\n'):
            for top in ('Colonoscopy report - 10/14/2026\n', ''):
                text = HEAD + top + rows + COLO_PLAIN
                with self.subTest(rows=rows.splitlines()[0], top=bool(top)):
                    self.assert_member_conflict(text, ELENA_DATE)
                    self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))


class BirthColumnBesideAnUndatedCellRequestTests(EndToEnd):
    C1 = HEAD + birth_column('spaces', 'TBD') + COLO_PLAIN

    def test_c1_the_member_s_date_of_birth_is_never_sent(self):
        held = self.finished(self.C1, service_date=ELENA_DATE)
        self.assert_held(held)
        self.assert_never_sent(held, ELENA_DATE)
        encounter_id = self.finished(self.C1)  # dateless, then the answer path
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assertEqual(self.dates_sent(encounter_id), [[]])


# --- df-d:3: a date-of-service cell of digits that is no date it can place is asked, never silent ---------------------

COMPACT_CELLS = ('20261014', '10142026')


def compact_column(layout, cell):
    """A date-of-service column whose cell is ``cell``, beside the note's "Date of service: 10/07/2026"."""
    if layout == 'tabs':
        return 'Patient\tMRN\tDate of Service\nSynthetic, Alex\t0000\t' + cell + '\n'
    if layout == 'short heads':
        return 'DOS       MRN\n' + cell.ljust(10) + '0000\n'
    return aligned('Patient', 'MRN', 'Date of Service') + '\n' + aligned('Synthetic, Alex', '0000', cell) + '\n'


class DigitsInADateOfServiceColumnTests(DateAssertions, SimpleTestCase):
    """df-d:3 (826fcff2d with 54bd8206b, the final refutation's fr-dr:1 and fr-dr:0): a row whose date-of-service cell
    is no date alone is not placed, and an unplaced row was asked only where it states a date with separators
    (_GAP_DATE). A cell of digits written without them ("20261014", "10142026") therefore stated no date (form 'empty',
    which never speaks), and "Date of service: 10/07/2026" beside it was documented and sent with 45385 ready, where
    c3c034a08 read the cell as the label's unread value and asked. fr-dr:0's own rule says a field that states something
    it cannot place speaks: an unplaced row whose cell at the label's place holds a digit is asked, the label alone kept
    (only a cell with no digit - "TBD", "N/A" - states no date)."""

    def test_beside_the_labelled_date_the_date_is_asked(self):
        for layout in ('spaces', 'tabs', 'short heads'):
            for cell in COMPACT_CELLS:
                for where in ('above', 'below'):
                    table = compact_column(layout, cell)
                    lines = ('Date of service: 10/07/2026\n' + table) if where == 'above' else \
                        (table + 'Date of service: 10/07/2026\n')
                    text = HEAD + 'Colonoscopy report\n' + lines + COLO_PLAIN
                    with self.subTest(layout=layout, cell=cell, where=where):
                        self.assert_never(text, '2026-10-07')
                        self.assertIn(date_fact(text).origin, ('conflict', 'missing'))
                        self.assert_member_date(text, '2026-10-07')
                        self.assert_member_conflict(text, ELENA_DATE)

    def test_the_verifier_s_smallest_form(self):
        text = HEAD + 'DOS  MRN\n20261014  0000\nDOS: 10/07/2026\n'
        self.assert_never(text, '2026-10-07')
        self.assert_member_date(text, '2026-10-07')

    def test_controls_a_cell_with_no_digit_states_no_date(self):
        for cell in ('TBD', 'N/A'):
            text = HEAD + 'Colonoscopy report\nDate of service: 10/07/2026\n' + compact_column('spaces', cell) + COLO_PLAIN
            with self.subTest(cell=cell):
                self.assert_document(text, '2026-10-07')


class DigitsInADateOfServiceColumnRequestTests(EndToEnd):
    def test_k1_no_date_is_sent(self):
        text = HEAD + 'Colonoscopy report\n' + compact_column('spaces', '20261014') + 'Date of service: 10/07/2026\n' \
            + COLO_PLAIN
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])


# --- df-d:2: a bracket that is no format after a subject line's date field leaves the date asked, never silent ---------

THIS_SERVICE_BRACKETS = ('corrected', 'performed', 'actual', 'of procedure', 'done', 'amended', 'final')
OTHER_EVENT_BRACKETS = ('signed', 'dictated', 'planned')
BRACKETED_FIELDS = ('Date', 'DOS', 'Date of service', 'Procedure date')


class BracketThatIsNoFormatTests(DateAssertions, SimpleTestCase):
    """df-d:2 (4ca4458a8, the final refutation's fr-dr:2): a bracket after a subject line's "Date" or date-of-service
    label kept the field the line's own only when it held a date format; any other made the field another field's, so
    its date was excluded and the line - evidence reading no date (form 'empty') - never spoke. That silenced brackets
    naming THIS service ("Date of service (corrected): 10/21/2026", "Date (performed): 10/21/2026"), and "Date of
    service: 10/14/2026" above, which the line contradicts, was documented and sent with 45385 ready, where c3c034a08
    asked. A bracket the grammar cannot read as a format (only a word list could tell "(performed)" from "(signed)")
    leaves the field's date one this service cannot place: the line speaks against the labelled date (asked) and reads
    no date, so no member date agrees with it alone - fr-dr:2's other-event dates ("(signed)", "(planned)") stay held."""

    def test_beside_the_labelled_date_the_date_is_asked(self):
        for word in THIS_SERVICE_BRACKETS + OTHER_EVENT_BRACKETS:
            for label in BRACKETED_FIELDS:
                for lead in ('Re: Colonoscopy - ', 'Regarding: Colonoscopy, '):
                    line = f'{lead}{label} ({word}): 10/21/2026'
                    text = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\n' + line + '\n' + COLO_PLAIN
                    with self.subTest(line=line):
                        self.assert_never(text, '2026-10-14', '2026-10-21')
                        self.assertIn(date_fact(text).origin, ('conflict', 'missing'))
                        self.assert_member_date(text, '2026-10-14')
                        self.assert_member_conflict(text, '2026-10-21')
                        self.assert_member_conflict(text, ELENA_DATE)

    def test_the_verifier_s_smallest_form(self):
        text = HEAD + 'DOS: 10/14/2026\nRe: EGD Date (done): 10/21/2026\n'
        self.assert_never(text, '2026-10-14')
        self.assert_member_date(text, '2026-10-14')
        self.assert_member_conflict(text, '2026-10-21')

    def test_controls(self):
        # a date format, or no bracket at all: the line's own date field, as before
        for subject, member in (('Re: Colonoscopy - Date (mm/dd/yyyy): 10/14/2026', '2026-10-14'),
                                ('Re: Colonoscopy - Date of service (DOS): 10/14/2026', '2026-10-14'),
                                ('Re: Colonoscopy - Date: 10/14/2026', '2026-10-14')):
            text = HEAD + 'Colonoscopy report\n' + subject + '\n' + COLO_PLAIN
            with self.subTest(subject=subject):
                self.assert_member_date(text, member)
                self.assert_member_conflict(text, ELENA_DATE)
        # another field's label is still another field's: the labelled date stands
        text = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nRe: Colonoscopy - Signed: 10/27/2026\n' + COLO_PLAIN
        self.assert_document(text, '2026-10-14')
        self.assert_member_conflict(text, '2026-10-27')


class BracketThatIsNoFormatRequestTests(EndToEnd):
    B2 = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nRe: Colonoscopy - Date (performed): 10/21/2026\n' \
        + COLO_PLAIN

    def test_b2_no_date_is_sent_where_the_subject_line_differs(self):
        encounter_id = self.finished(self.B2)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': '2026-10-21'})
        self.assert_never_sent(encounter_id, '2026-10-21')


# --- df-d:4: a date of birth beside a qualifier makes the labelled date unplaced (asked), never another occurrence's -----

QUALIFIERS = ('Repeat', 'Next', 'Planned', 'Outside', 'Index', 'Prior', 'Recent')
BEFORE_FORMS = ('{Q} colonoscopy for Synthetic, Alex (DOB 01/01/1998) Procedure date: 10/14/2026',
                '{Q} colonoscopy (DOB 01/01/1998) Procedure date: 10/14/2026',
                '{Q} (DOB 01/01/1998) DOS: 10/14/2026',
                '{Q} colonoscopy, Synthetic, Alex, born 01/01/1998, Date of service: 10/14/2026')
AFTER_FORMS = ('Procedure date: 10/14/2026 for Synthetic, Alex (DOB 01/01/1998) {q}',
               'Procedure date: 10/14/2026 (DOB 01/01/1998) {q}',
               'Procedure date: 10/14/2026, for Synthetic, Alex, {q} DOB 01/01/1998')
ADDENDUM = '\nAddendum\nDate of service: 10/21/2026\n'


class DateOfBirthBesideAQualifierTests(DateAssertions, SimpleTestCase):
    """df-d:4 (a3774bcb0, the final refutation's fr-di:0 and fr-dr:4): a date of birth between a qualifier and a labelled
    date - before the label ("Repeat colonoscopy for Synthetic, Alex (DOB 01/01/1998) Procedure date: 10/14/2026"), or
    between the date and a qualifier after it, or after that qualifier nearer to it than the date - had made c3c034a08
    pass the qualifier over (it read the date of birth as the qualifier's own date). The fix round rightly stopped that
    (a date of birth dates no occurrence: the office visit's planned 11/04 was sent), but the qualifier was then read as
    attached to the label: another occurrence's date, which never speaks. So "Date of service: 10/21/2026" in an
    addendum was documented and sent with 45385 ready where c3c034a08 asked (the two labels differ), also where the
    installed revision asked (history words: "Outside colonoscopy (DOB ...) Procedure date:"). A date of birth between
    a qualifier and the date neither passes the qualifier over nor attaches it: the date reads 'beside' - it speaks
    against another labelled date (asked, as at c3c034a08), and as it may be another occurrence's it is never a value a
    documented conflict lists nor a member's answer (held, as at 004bf808c: an office visit's member answer 11/04 is
    never taken)."""

    def test_beside_another_labelled_date_the_date_is_asked(self):
        for qualifier in QUALIFIERS:
            for form in BEFORE_FORMS + AFTER_FORMS:
                line = form.format(Q=qualifier, q=qualifier.lower())
                text = HEAD + 'Colonoscopy report\n' + line + '\n' + COLO_PLAIN + ADDENDUM
                with self.subTest(line=line):
                    self.assert_never(text, '2026-10-21', '2026-10-14')
                    self.assertIn(date_fact(text).origin, ('conflict', 'missing'))
                    self.assert_member_date(text, '2026-10-21')
                    self.assert_member_conflict(text, '2026-10-14')  # it may be another occurrence's
                    self.assert_member_conflict(text, ELENA_DATE)

    def test_the_verifier_s_smallest_forms(self):
        for text in (HEAD + 'Repeat (DOB 01/01/1998) DOS: 10/14/2026\nDOS: 10/21/2026\n',
                     HEAD + 'Outside colonoscopy (DOB 01/01/1998) Procedure date: 10/14/2026\nDate of service: 10/21/2026\n'
                     + COLO_PLAIN):
            with self.subTest(text=text.splitlines()[1]):
                self.assert_never(text, '2026-10-21')
                self.assertIn(date_fact(text).origin, ('conflict', 'missing'))

    def test_controls_the_fix_round_s_office_and_recall_lines_send_nothing(self):
        # fr-di:0 and fr-di:1: a planned or recall date beside a date of birth is still never the note's own
        for line, beside in (('Repeat colonoscopy for Synthetic, Alex (DOB 01/01/1998) Procedure date: 11/04/2026', True),
                             ('Procedure date: 11/04/2026    DOB: 01/01/1998    Status: Scheduled', False),
                             ('Due (DOB 01/01/1998) DOS: 11/04/2026', True)):
            text = HEAD + 'GI office visit\n' + line + '\nAssessment and plan: colonoscopy will be scheduled.\n'
            with self.subTest(line=line):
                self.assert_never(text, '2026-11-04')
                self.assert_member_conflict(text, ELENA_DATE)
                if beside:  # read beside the qualifier: the planned date is never the member's answer (as at 004bf808c)
                    self.assert_member_conflict(text, '2026-11-04')
        text = (HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\n' + COLO_PLAIN
                + 'Procedure date: 10/14/2029 for Synthetic, Alex (DOB 01/01/1998) follow-up\n')
        self.assert_never(text, '2029-10-14')
        self.assert_member_conflict(text, '2029-10-14')
        self.assert_member_date(text, '2026-10-14')
        # no date of birth: the qualifier attached to the label still makes it another occurrence's
        text = HEAD + 'Colonoscopy report\nRepeat colonoscopy for Synthetic, Alex Procedure date: 10/14/2029\n' \
            + COLO_PLAIN + 'Date of service: 10/14/2026\n'
        self.assert_document(text, '2026-10-14')


class DateOfBirthBesideAQualifierRequestTests(EndToEnd):
    OFFICE = (HEAD + 'GI office visit\nRepeat colonoscopy for Synthetic, Alex (DOB 01/01/1998) Procedure date: 11/04/2026\n'
              'Assessment and plan: colonoscopy will be scheduled.\n')

    def test_the_office_line_s_planned_date_is_never_sent(self):
        encounter_id = self.finished(self.OFFICE)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': '2026-11-04'})
        self.assert_never_sent(encounter_id, '2026-11-04')

    def test_q1_no_date_is_sent_where_the_labels_differ(self):
        for line in ('Repeat colonoscopy for Synthetic, Alex (DOB 01/01/1998) Procedure date: 10/14/2026',
                     'Outside colonoscopy (DOB 01/01/1998) Procedure date: 10/14/2026'):
            with self.subTest(line=line):
                encounter_id = self.finished(HEAD + 'Colonoscopy report\n' + line + '\n' + COLO_PLAIN + ADDENDUM)
                self.assertEqual(self.dates_sent(encounter_id), [[]])
