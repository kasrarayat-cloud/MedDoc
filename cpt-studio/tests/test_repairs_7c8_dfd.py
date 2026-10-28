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
