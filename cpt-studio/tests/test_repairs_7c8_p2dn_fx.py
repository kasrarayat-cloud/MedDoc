"""Repair round 7c8, P2DN's fix round (the service date narrowed; studio/gi/context.py).

Two independent skeptics attacked P2DN (wip/7c8-p2dn at e33702395) and demonstrated eight must-fix issues, each end to end
through POST /api/encounters and POST /context with the suite's FakeProvider. Each is reproduced here first, then repaired
by a general rule of SOURCE or of the STRUCTURE of the label's own field - never a header-block requirement, never a
vocabulary of qualifiers, never a sentence the tests name:

1  a dated service or subject line read another field's date as its own (P2DN's d095e22fe dropped a62a18c85's rule
   that a date after another field's label is that field's): a member's referral, order or signing date, or a date of
   birth under a format-hint label, agreed with the line and was sent, and the note's own labelled 10/14 became a
   question;
2  N5: words after the labelled date were read as part of the next field's label ("Pending authorization. Status:"),
   so a cancelled or pending date was the note's own;
3  N2: a birth label joined to the date-of-service label ("DOB / Date of Service: 01/01/1998") made the date of birth
   the documented service date, sent with no member at all;
4  N2 "any row": a birth label heading the value's column in a space- or tab-aligned header, a stacked header or a
   two-value joined header made the date of birth the label's value;
5  a "Rescheduled to:" field with its own date on the label's line was passed over, so the superseded date was sent
   where the installed revision 057a7d398 sent none;
6  N3: an empty date-of-service field beside a date of birth kept nothing, so a member's 1998-01-01 was sent;
7  N2's birth labels read a date that is no date of birth as one ("Dr. Robin B.", "hepatitis B." above, a DOB last
   column), so the document's only dated line was dropped: a member's 1998-01-01 was sent and its 10/14 held;
8  the known-limit qualifier shapes, written in a form 057a7d398 does not read ("3 Sep 2026", a table row), or with a
   qualifier that has its own date on the label's line, sent the other occurrence's date where 057a7d398 sent none.

Synthetic text only; no network.
"""
from django.test import SimpleTestCase

from studio.gi import context
from tests.test_repairs_7c8_context import DateAssertions, merged_date
from tests.test_repairs_7c8_context3 import (COLO_BODY, COLO_PLAIN, EGD_BODY, ELENA_DATE, HEAD, OFFICE_BODY, EndToEnd,
                                             date_fact, evidence_text)

BIRTH = '01/01/1998'
BODY = ('Findings: The colonoscope was advanced to the cecum. A 5 mm sigmoid polyp was removed with a cold snare.\n'
        'Impression: one polyp removed.\n')
LETTER = 'Dear Dr. Synthetic,\nYour patient underwent colonoscopy. A 5 mm sigmoid polyp was removed with a cold snare.\n'


def taken(text, value):
    fact = merged_date(text, value)
    return (fact.origin, fact.value) == ('user', value)


# --- 1: a date after another field's label is that field's, never the line's own -----------------------------------

OTHER_FIELD_UNDER_TITLE = (  # the skeptic's X1-X4: a dated title (evidence), then a header line naming the service
    (HEAD + 'Colonoscopy report - 10/14/2026\nProcedure: Colonoscopy  DOB (mm/dd/yyyy): 01/01/1998\n' + COLO_BODY,
     ELENA_DATE),
    (HEAD + 'Colonoscopy report - 10/14/2026\nColonoscopy    Patient: Synthetic, Alex    Date of Birth (MM/DD/YYYY): '
     '01/01/1998\n' + COLO_BODY, ELENA_DATE),
    (HEAD + 'Colonoscopy report - 10/14/2026\nProcedure: Colonoscopy    Referral date: 10/13/2026\n' + COLO_BODY,
     '2026-10-13'),
    (HEAD + 'Colonoscopy report - 10/14/2026\nProcedure: Colonoscopy  Report signed: 10/27/2026\n' + COLO_BODY,
     '2026-10-27'),
    (HEAD + 'Date: 10/14/2026\nEGD    Ordered: 10/13/2026\n' + EGD_BODY, '2026-10-13'),
    (HEAD + 'GI consultation - 10/14/2026\nRe: Colonoscopy - Dictated: 10/27/2026\n' + COLO_BODY, '2026-10-27'),
)
SUBJECT_BESIDE_OWN_LABEL = (  # the skeptic's S1-S3: the note's own labelled 10/14 and a subject line
    (HEAD + 'Date of service: 10/14/2026\nRe: Colonoscopy - Referral date: 10/13/2026\n' + COLO_BODY, '2026-10-13'),
    (HEAD + 'Date of service: 10/14/2026\nSubject: Colonoscopy report - Signed: 10/27/2026\n' + COLO_BODY, '2026-10-27'),
    (HEAD + 'Date of service: 10/14/2026\nRe: Colonoscopy for Alex Synthetic, DOB (mm/dd/yyyy): 01/01/1998\n'
     + COLO_BODY, ELENA_DATE),
    (HEAD + 'DOS: 10/14/2026\nRegarding: EGD, Ordered: 10/13/2026\n' + EGD_BODY, '2026-10-13'),
)


class AnotherFieldSDateIsNeverTheLineSTests(DateAssertions, SimpleTestCase):
    """Issue 1 (a regression of d095e22fe against a62a18c85): a dated service or subject line took its only date that is
    no date of birth after the service's first name as its own, whatever field label stood before it - so in "Procedure:
    Colonoscopy    Referral date: 10/13/2026" the referral date was the line's value. Under a dated title (evidence
    only, rule N1) a member's 10/13 agreed with the line and was sent; beside the note's own "Date of service: 10/14/2026"
    the subject line's 10/13 made it a question, the note's own 10/14 was lost and a member's 10/13 was sent. A date
    after another field's label is that field's: only a bare date field ("Date:", "Date/Time:") or a date-of-service
    label gives the line its date, and a line whose dates are all other fields' states no date of the service."""

    def test_under_a_dated_title_the_other_field_s_date_is_never_taken(self):
        for text, other in OTHER_FIELD_UNDER_TITLE:
            with self.subTest(line=text.splitlines()[2][:70]):
                self.assert_member_conflict(text, other)
                self.assert_member_date(text, '2026-10-14')  # the title's date still answers the question
                quoted = ' '.join(evidence_text(text))
                self.assertNotIn(other[5:7] + '/' + other[8:] + '/' + other[:4], quoted)

    def test_beside_the_own_labelled_date_it_stays_documented(self):
        for text, other in SUBJECT_BESIDE_OWN_LABEL:
            with self.subTest(line=text.splitlines()[2][:70]):
                self.assert_document(text, '2026-10-14')
                self.assert_member_conflict(text, other)

    def test_a_today_label_beside_another_field_s_date_holds_every_member_date(self):
        # the lens's G5 rows: 'today' names this encounter, and the line's only date is the order's
        text = HEAD + 'GI office visit\nVisit Date: today Ordered: 10/13/2026\n' + OFFICE_BODY
        for member in (ELENA_DATE, '2026-10-13', '2026-10-14'):
            self.assert_member_conflict(text, member)

    def test_controls_a_bare_date_field_or_the_service_s_own_field(self):
        # dates:2's D1: the line's "Date:" field is its own date; a date right after the name, or after the service's
        # own field label ("Colonoscopy: ..."), is the line's; a date of birth between them is never read
        for line, value in (('Procedure: EGD  Patient: Alex Synthetic  DOB: 01/01/1998  Date: 10/14/2026', '2026-10-14'),
                            ('Colonoscopy: 10/14/2026', '2026-10-14'), ('EGD - 10/14/2026', '2026-10-14'),
                            ('Re: Colonoscopy on 10/14/2026', '2026-10-14'),
                            ('Colonoscopy    Date/Time: 10/14/2026 08:30', '2026-10-14'),
                            ('EGD 10/14/2026    Signed: 10/27/2026', '2026-10-14')):
            text = HEAD + line + '\n' + EGD_BODY
            with self.subTest(line=line):
                self.assert_member_date(text, value)
                self.assert_member_conflict(text, ELENA_DATE)
                self.assert_member_conflict(text, '2026-10-27')


class AnotherFieldSDateRequestTests(EndToEnd):
    """Issue 1 end to end: the member's other-field date is held (nothing sent), and the note's own labelled 10/14 is
    sent with no member."""

    def test_x3_x1_under_the_title_the_member_s_other_field_date_is_held(self):
        for text, other in (OTHER_FIELD_UNDER_TITLE[2], OTHER_FIELD_UNDER_TITLE[0]):
            with self.subTest(line=text.splitlines()[2][:50]):
                encounter_id = self.finished(text, service_date=other)
                self.assert_held(encounter_id)
                self.assert_never_sent(encounter_id, other)

    def test_s1_the_own_labelled_date_is_sent_and_the_member_s_referral_date_held(self):
        text, other = SUBJECT_BESIDE_OWN_LABEL[0]
        own = self.finished(text)
        self.assertEqual(self.dates_sent(own), [['Date of service: 2026-10-14']])
        self.assertEqual(self.bucket(own, '45385'), 'selected')
        held = self.finished(text, service_date=other)
        self.assert_held(held)
        self.assert_never_sent(held, other)


# --- 7: a birth label is a label, never an initial, a word ending the line above or a column it does not head -------

INITIALS = (  # 'B.' as a name's initial right before the date, or ending the line above the dated line
    HEAD + 'To: Dr. Robin B.\nRe: Colonoscopy 10/14/2026\n' + LETTER,
    HEAD + 'Patient: Synthetic, Alex B.\nColonoscopy 10/14/2026\n' + BODY,
    HEAD + 'Re: Colonoscopy for Synthetic, Alex B. - 10/14/2026\n' + BODY,
    HEAD + 'EGD - Dr. Robin B. - 10/14/2026\n' + EGD_BODY,
    HEAD + 'Endoscopist: Dr. Robin B.\nColonoscopy 10/14/2026\n' + BODY,
    HEAD + 'cc: Dr. Jordan B.\nRe: Colonoscopy 10/14/2026\n' + LETTER,
)
WORDS_ABOVE = (  # a birth word ending the line above that labels no value on the next line
    HEAD + 'Indication: surveillance, chronic hepatitis B.\nEGD - 10/14/2026\n' + EGD_BODY,
    HEAD + 'Indication: chronic gastritis, type B.\nEGD - 10/14/2026\n' + EGD_BODY,
    HEAD + 'Patient: Synthetic, Alex    DOB:\nColonoscopy 10/14/2026\n' + COLO_PLAIN,
    HEAD + 'Age/DOB:\nColonoscopy 10/14/2026\n' + BODY,
    HEAD + 'Born:\nColonoscopy 10/14/2026\n' + BODY,
    HEAD + 'Indication: chronic constipation since birth\nColonoscopy 10/14/2026\n' + BODY,
)
DOB_LAST_COLUMN = (HEAD + 'Patient             Procedure          Date          DOB\n'
                   'Synthetic, Alex     Colonoscopy        10/14/2026    01/01/1998\n' + BODY)
OUTSIDE_UNDER_INITIAL = (HEAD + 'To: Dr. Robin B.\nRe: Colonoscopy 10/14/2026\nOutside colonoscopy:\nFacility: Synthetic '
                         'Regional Hospital\nProcedure date: 3 Sep 2026\nFindings today: A 5 mm sigmoid polyp was removed '
                         'with a cold snare.\n')


class BirthLabelIsALabelTests(DateAssertions, SimpleTestCase):
    """Issue 7 (a regression of d095e22fe): "b." was read as a birth label in "Dr. Robin B. - 10/14/2026" and at the end
    of "To: Dr. Robin B.", "chronic hepatitis B." or "...since birth" above the dated line, and a birth word ending a
    line marked the next line's FIRST date as a date of birth even where it labels a column ("... Date  DOB" over
    "... 10/14/2026  01/01/1998"). The document's only dated line was then dropped, so a member's 1998-01-01 was taken
    and sent while its correct 10/14 was held, and the line's question over an outside date was lost. A birth label is a
    LABEL: "b." written so, never a capital initial after a name; one ending a line labels the next line only when it
    is that line's only text and the next line opens with the value; one heading a column labels that column."""

    def test_an_initial_or_a_word_ending_the_line_above_is_no_birth_label(self):
        for text in INITIALS + WORDS_ABOVE + (DOB_LAST_COLUMN,):
            with self.subTest(lines=' / '.join(text.splitlines()[1:3])[:80]):
                self.assert_member_conflict(text, ELENA_DATE)
                self.assert_member_date(text, '2026-10-14')

    def test_the_subject_line_still_questions_the_outside_date(self):
        # the skeptic's E14: the Re: line's 10/14 against the outside colonoscopy's "Procedure date: 3 Sep 2026"
        self.assert_never(OUTSIDE_UNDER_INITIAL, '2026-09-03')
        self.assertIn(date_fact(OUTSIDE_UNDER_INITIAL).origin, ('conflict', 'missing'))

    def test_controls_a_birth_label_still_reads_its_value(self):
        for text in (HEAD + 'Colonoscopy - Synthetic, Alex (b. 01/01/1998) - 10/14/2026\n' + COLO_PLAIN,
                     HEAD + 'Colonoscopy report - 10/14/2026\nDate of birth:\n01/01/1998\n' + COLO_PLAIN,
                     HEAD + 'Colonoscopy report - 10/14/2026\nPatient | DOB\nSynthetic, Alex | 01/01/1998\n' + COLO_PLAIN,
                     HEAD + 'Colonoscopy report - 10/14/2026\nPatient          DOB\nSynthetic, Alex  01/01/1998\n'
                     + COLO_PLAIN):
            with self.subTest(lines=' / '.join(text.splitlines()[1:4])[:80]):
                self.assert_member_conflict(text, ELENA_DATE)
                self.assert_member_date(text, '2026-10-14')
                self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))


class BirthLabelIsALabelRequestTests(EndToEnd):
    def test_e3_e4_e8_the_member_s_1998_is_held_and_its_10_14_sent(self):
        for text in (INITIALS[0], INITIALS[1], DOB_LAST_COLUMN):
            with self.subTest(lines=' / '.join(text.splitlines()[1:3])[:60]):
                encounter_id = self.finished(text, service_date=ELENA_DATE)
                self.assert_held(encounter_id)
                self.set_context(encounter_id, {'service_date': '2026-10-14'})
                self.assertEqual(self.dates_sent(encounter_id), [['Date of service: 2026-10-14']])

    def test_e13_the_member_s_1998_entered_afterwards_is_never_sent(self):
        encounter_id = self.finished(INITIALS[1])
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assert_never_sent(encounter_id, ELENA_DATE)
        self.assertEqual(self.dates_sent(encounter_id), [[]])

    def test_e14_the_outside_date_is_never_sent(self):
        encounter_id = self.finished(OUTSIDE_UNDER_INITIAL)
        self.assertEqual(self.dates_sent(encounter_id), [[]])


# --- 3 and 4: a date of birth in any row - a joined header, an aligned column, a stacked header ----------------------

JOINED_ONE_VALUE = (  # issue 3: J1, J2 - a birth label joined to the date-of-service label, one value
    HEAD + 'Colonoscopy report\nDOB / Date of Service: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nDate of Birth & DOS: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Patient: Synthetic, Alex\nD.O.B. and Procedure Date: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nDate of Service / DOB: 01/01/1998\n' + COLO_BODY,
)
ROWS = {  # issue 4 (and J3): the date of birth heads its own column or row; the date of service the other
    'space columns': 'DOB            Date of Service\n01/01/1998     10/14/2026',
    'tab columns': 'DOB\tDate of Service\n01/01/1998\t10/14/2026',
    'columns with colons': 'DOB:        Procedure Date:\n01/01/1998  10/14/2026',
    'service first': 'Date of Service    DOB\n10/14/2026         01/01/1998',
    'stacked': 'DOB:\nDate of service:\n01/01/1998\n10/14/2026',
    'stacked, no colons': 'DOB\nDate of Service\n01/01/1998\n10/14/2026',
    'joined, two values': 'DOB / Date of Service: 01/01/1998 / 10/14/2026',
    'joined, service first': 'Visit Date & Date of Birth: 10/14/2026 & 01/01/1998',
}


class BirthDateInAnyRowTests(DateAssertions, SimpleTestCase):
    """Issues 3 and 4 (N2 "in any position, any row"): _BIRTH_BEFORE reads only a birth label right before the date, and
    _birth_cells only a bar table's column or a birth label above its value - so a birth label joined to the
    date-of-service label ("DOB / Date of Service: 01/01/1998"), heading the value's column in a space- or tab-aligned
    header, or stacked over its value ("DOB:" / "Date of service:" / "01/01/1998" / "10/14/2026") left the date of birth
    the label's value: documented and sent with no member at all (issue 3), or a member's 1998-01-01 taken and sent
    while the 10/14 the note states was held (issue 4). A header names its fields in order: each value is its field's,
    by position - a column by its column, a stacked label by its place in the stack, a joined header by its place in
    the header - and where the positions do not match the label states no date."""

    def test_a_birth_label_joined_to_the_label_is_never_its_value(self):
        for text in JOINED_ONE_VALUE:
            with self.subTest(line=text.splitlines()[2]):
                self.assert_never(text, ELENA_DATE)
                self.assertEqual(date_fact(text).origin, 'missing', evidence_text(text))
                self.assert_member_conflict(text, ELENA_DATE)
                self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))

    def test_each_value_is_its_own_field_s_by_position(self):
        for shape, rows in ROWS.items():
            for top in ('Colonoscopy report\n', ''):
                text = HEAD + top + rows + '\n' + COLO_BODY
                with self.subTest(shape=shape, top=bool(top)):
                    self.assert_never(text, ELENA_DATE)
                    self.assert_member_conflict(text, ELENA_DATE)
                    self.assert_member_date(text, '2026-10-14')
                    self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))

    def test_the_skeptic_s_family_b(self):
        shapes = ('{b}        {l}\n01/01/1998        10/14/2026', '{b}\t{l}\n01/01/1998\t10/14/2026',
                  '{b}:        {l}:\n01/01/1998        10/14/2026', '{b}:\n{l}:\n01/01/1998\n10/14/2026',
                  '{b}\n{l}\n01/01/1998\n10/14/2026', '{b} / {l}: 01/01/1998 / 10/14/2026',
                  '{b} & {l}: 01/01/1998 & 10/14/2026')
        for shape in shapes:
            for b in ('DOB', 'Date of Birth', 'D.O.B.', 'Birth Date'):
                for label in ('Date of Service', 'DOS', 'Visit Date', 'Procedure Date'):
                    for top in ('Colonoscopy report\n', ''):
                        text = HEAD + top + shape.format(b=b, l=label) + '\n' + COLO_BODY
                        with self.subTest(text=text.splitlines()[1:4]):
                            self.assertFalse(taken(text, ELENA_DATE))
                            self.assertTrue(taken(text, '2026-10-14'))

    def test_controls_where_positions_do_not_match_the_label_states_no_date(self):
        # three values under two column heads, or a stack with a value missing: no value is the label's
        for rows in ('DOB            Date of Service\n01/01/1998     10/14/2026     10/20/2026',
                     'DOB:\nDate of service:\n01/01/1998\n\nPROCEDURE NOTE'):
            text = HEAD + 'Colonoscopy report\n' + rows + '\n' + COLO_PLAIN
            with self.subTest(rows=rows):
                self.assert_member_conflict(text, ELENA_DATE)
                self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))
        # a bar table is read as before; a stack of one label reads the next line
        self.assert_member_conflict(HEAD + 'DOB | Date of Service\n01/01/1998 | 10/14/2026\n' + COLO_BODY, ELENA_DATE)
        self.assert_member_date(HEAD + 'Date of service:\n10/14/2026\n' + COLO_BODY, '2026-10-14')


class BirthDateInAnyRowRequestTests(EndToEnd):
    def test_j1_no_date_is_sent(self):
        encounter_id = self.finished(JOINED_ONE_VALUE[0])
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assert_not_excluded(encounter_id, '45385')

    def test_y1_y2_the_member_s_1998_is_held_and_its_10_14_sent(self):
        for shape in ('space columns', 'stacked'):
            text = HEAD + 'Colonoscopy report\n' + ROWS[shape] + '\n' + COLO_BODY
            with self.subTest(shape=shape):
                held = self.finished(text, service_date=ELENA_DATE)
                self.assert_held(held)
                own = self.finished(text, service_date='2026-10-14')
                self.assertEqual(self.dates_sent(own), [['Date of service: 2026-10-14']])
                self.assertEqual(self.bucket(own, '45385'), 'selected')


# --- 2: the next field's label is a label - one word, or words a label is written in, with no sentence inside -------

IN_THE_FIELD = (  # issue 2: the skeptic's Z1-Z5 - words in the label's own field, read as part of the next field's label
    (HEAD + 'GI office visit\nProcedure date: 11/04/2026 Pending authorization. Status: open\n' + OFFICE_BODY, '99213'),
    (HEAD + 'EGD report\nProcedure date: 11/04/2026 Cancelled. Reason: patient illness\n' + EGD_BODY, '43239'),
    (HEAD + 'Colonoscopy report\nDate of service: 11/04/2026 Cancelled Status: closed\n' + COLO_BODY, '45385'),
    (HEAD + 'EGD report\nProcedure date: 11/04/2026  pending authorization Status: open\n' + EGD_BODY, '43239'),
    (HEAD + 'Colonoscopy report\nDate of service: 11/04/2026\tNot yet performed. Indication: screening\n' + COLO_BODY,
     '45385'),
)


class NextFieldSLabelIsALabelTests(DateAssertions, SimpleTestCase):
    """Issue 2 (N5, pre-existing at a62a18c85, 2fc8cde3d and 057a7d398 - but N5 states the label's field runs to the next
    field's label): _NEXT_FIELD read up to six words with full stops and brackets before a colon as the next field's
    label, so "Procedure date: 11/04/2026 Pending authorization. Status: open" read "Pending authorization." as part of
    the label "Status" and documented the planned 11/04 (99213 ready, 43239 excluded). The next field's label is the
    words right before its colon only when they are one label: no full stop, comma or semicolon inside, no bracket but
    a format after it, one word - or a label of several words, written with a capital first and no capitalised word
    after a word of its own ("Place of service", "Referring physician", "Place of Service"). Where the words could be
    the date's field's own and a label's ("Cancelled Status:", "pending authorization Status:") the date is asked."""

    def test_words_in_the_label_s_field_ask_the_date(self):
        for text, _code in IN_THE_FIELD:
            with self.subTest(line=text.splitlines()[2]):
                self.assert_never(text, '2026-11-04')
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('missing', None), fact.evidence)
                self.assertIn(context.FIELD_DATE_NOTE, fact.note)
                self.assert_member_date(text, '2026-11-04')

    def test_a_sentence_or_a_list_before_a_lower_case_label(self):
        # what only the sentence-end rule asks: a full stop or a comma ends a word before a label written in lower case
        for line in ('Procedure date: 11/04/2026  Cancelled. status: open',
                     'Date of service: 11/04/2026\tPostponed, reason: patient illness',
                     'Date of service: 11/04/2026    Pending; reason: authorization'):
            text = HEAD + 'Colonoscopy report\n' + line + '\n' + COLO_BODY
            with self.subTest(line=line):
                self.assert_never(text, '2026-11-04')
                self.assert_member_date(text, '2026-11-04')

    def test_the_skeptic_s_family_a(self):
        words = ('Cancelled.', 'Cancelled', 'Pending authorization.', 'Not yet performed.', 'Postponed (patient request)',
                 'Awaiting insurance approval.', 'CANCELLED', 'Tentative only.', 'pending authorization')
        for word in words:
            for sep in (' ', '  ', '\t'):
                if sep == ' ' and word[0].islower():
                    continue
                for nxt in ('Status: open', 'Reason: patient illness', 'Indication: screening', 'Comments: see note'):
                    for label, body in (('Procedure date', EGD_BODY), ('Date of service', COLO_BODY)):
                        text = HEAD + 'Procedure report\n' + f'{label}: 11/04/2026{sep}{word} {nxt}' + '\n' + body
                        with self.subTest(line=text.splitlines()[2]):
                            self.assert_never(text, '2026-11-04')

    def test_controls_the_next_field_s_label(self):
        for line in ('DOS: 10/14/2026 MRN: 0000', 'DOS: 10/14/2026 DOB: 01/01/1998',
                     'Date of service: 10/14/2026    Place of service: Office',
                     'Date of service: 10/14/2026    Place of Service: 22',
                     'Date of service: 10/14/2026    PLACE OF SERVICE: 22',
                     'Date of service: 2026-10-14 Place of service: Office',
                     'Date of service: 10/14/2026\tReferring physician: Dr. B. Synthetic',
                     'Date of service: 10/14/2026 08:30 Provider: Dr. A. Synthetic',
                     'Date of service: 10/14/2026    DOB (mm/dd/yyyy): 01/01/1998',
                     'Date of service: 10/14/2026    D.O.B.: 01/01/1998', 'Date of service: 10/14/2026    time: 08:30'):
            with self.subTest(line=line):
                self.assert_document(HEAD + 'Colonoscopy report\n' + line + '\n' + COLO_BODY, '2026-10-14')
        for line in ('Date of service: 10/14/2026    Patient Name: Synthetic', 'DOS: 10/14/2026 mrn: 0000',
                     'Date of service: 10/14/2026    Ref. physician: Dr. B. Synthetic'):
            with self.subTest(line=line):  # where the label may start later: asked, never another date
                self.assert_question(HEAD + 'Colonoscopy report\n' + line + '\n' + COLO_BODY, '2026-10-14')


class NextFieldSLabelIsALabelRequestTests(EndToEnd):
    def test_z1_z5_send_no_date(self):
        for text, code in IN_THE_FIELD:
            with self.subTest(line=text.splitlines()[2][:60]):
                encounter_id = self.finished(text)
                self.assertEqual(self.dates_sent(encounter_id), [[]])
                self.assert_not_excluded(encounter_id, code)


# --- 5 and 8: a qualifier with a date of its own on the label's line ------------------------------------------------

RESCHEDULED = HEAD + 'Colonoscopy report\nDate of service: 10/07/2026 Rescheduled to: 10/14/2026\n' + COLO_BODY
FOLLOW_UP_BEFORE = HEAD + 'Follow-up visit 10/20/2026. Procedure date: 11/04/2026\n' + OFFICE_BODY


class QualifierWithItsOwnDateOnTheLineTests(DateAssertions, SimpleTestCase):
    """Issue 5 and issue 8's E9 (pre-existing since round 2's c2:1, never at 057a7d398): a qualifier on the label's own
    line that has a date of its own ("Rescheduled to: 10/14/2026" after "Date of service: 10/07/2026", "Follow-up visit
    10/20/2026." before "Procedure date: 11/04/2026") was passed over as belonging elsewhere, so the superseded or
    planned date was documented and sent - and 45385 done on 10/14 excluded as planned - where the installed revision's
    same-line window held it. The label's line then states two occurrences' dates, and the reader cannot tell which is
    this encounter's: the date is asked. A qualifier opening a field about something else ("Last name: Synthetic") is
    still passed over, and a qualifier on the line above keeps the round-3 rule."""

    def test_the_skeptic_s_family_w(self):
        for label in ('Date of service', 'Procedure date', 'DOS', 'Visit date'):
            for qualifier in ('Rescheduled to', 'Rescheduled for', 'Rescheduled date', 'Rescheduled procedure date'):
                for sep in (' ', '    ', '\t'):
                    text = HEAD + 'Colonoscopy report\n' + f'{label}: 10/07/2026{sep}{qualifier}: 10/14/2026\n' + COLO_BODY
                    with self.subTest(line=text.splitlines()[2]):
                        self.assert_never(text, '2026-10-07', '2026-10-14')
                        self.assertIn(date_fact(text).origin, ('missing', 'conflict'))
                        self.assert_member_conflict(text, ELENA_DATE)

    def test_a_qualifier_with_its_own_date_before_the_label(self):
        # the skeptic's case set 4 (E9 and its paraphrases), in m/d/y and day-first forms
        for line in ('Follow-up visit 10/20/2026. Procedure date: 11/04/2026',
                     'Follow-up visit 10/20/2026; procedure date: 11/04/2026',
                     'Last colonoscopy 05/01/2019. Procedure date: 11/04/2026',
                     'Rescheduled from 10/27/2026. Procedure date: 11/04/2026',
                     'Next visit 12/01/2026. Procedure date: 11/04/2026',
                     'Prior EGD 2024-02-02; procedure date: 11/04/2026'):
            for form in ('11/04/2026', '4 Nov 2026'):
                text = HEAD + line.replace('11/04/2026', form) + '\n' + OFFICE_BODY
                with self.subTest(line=text.splitlines()[1]):
                    self.assert_never(text, '2026-11-04')

    def test_the_installed_revision_s_window_shapes_are_asked(self):
        for line in ('Date of service: 10/14/2026    Next visit: 11/24/2026',
                     'Date of service: 10/14/2026    Recall due: 10/2029',
                     'Last colonoscopy 05/01/2019    Date of service: 10/14/2026'):
            with self.subTest(line=line):
                self.assert_question(HEAD + 'Colonoscopy report\n' + line + '\n' + COLO_BODY, '2026-10-14')

    def test_controls(self):
        for text in (HEAD + 'Colonoscopy report\nDate of service: 10/14/2026    Last name: Synthetic\n' + COLO_BODY,
                     HEAD + 'Colonoscopy report\nLast colonoscopy: 05/01/2019\nDate of service: 10/14/2026\n' + COLO_BODY,
                     HEAD + 'Colonoscopy report\nDate of service: 10/14/2026    DOB: 01/01/1998\n' + COLO_BODY,
                     HEAD + 'Colonoscopy report\nDate of service: 10/14/2026    Previous name: Synthetic\n' + COLO_BODY):
            with self.subTest(lines=text.splitlines()[2:4]):
                self.assert_document(text, '2026-10-14')


class QualifierWithItsOwnDateOnTheLineRequestTests(EndToEnd):
    def test_w1_and_e9_send_no_date(self):
        w1 = self.finished(RESCHEDULED)
        self.assertEqual(self.dates_sent(w1), [[]])
        self.assert_not_excluded(w1, '45385')
        e9 = self.finished(FOLLOW_UP_BEFORE)
        self.assertEqual(self.dates_sent(e9), [[]])
        self.assert_not_excluded(e9, '99213')


# --- 6: an empty or non-date date-of-service field is kept as evidence that reads no date ---------------------------

EMPTY_BESIDE_BIRTH = (  # the skeptic's V1, V2 and C3
    HEAD + 'Colonoscopy report\nDate of service:\nDOB: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOS:    DOB: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nDate of service: N/A\nDOB: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nProcedure date: TBD\nDate of birth: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nDate of Service\n\nDOB: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex Date of service:\nDOB: 01/01/1998\n' + COLO_BODY,
)


class EmptyDateFieldIsEvidenceTests(DateAssertions, SimpleTestCase):
    """Issue 6 (N3 as written; pre-existing at a62a18c85, 2fc8cde3d and 057a7d398): a date-of-service label whose field
    is empty or holds no date kept nothing when its value was on no line ("Date of service:" over "DOB: 01/01/1998"), past
    a field break ("DOS:    DOB: 01/01/1998") or held no digit ("Date of service: N/A") - so a member's 1998-01-01 was
    taken and sent and 45385 excluded against it. A date-of-service FIELD - a label with a separator, or alone on its
    line - that states no date is kept as evidence that reads no date: every member date is held until the document
    states the date (an addendum) or the member clears it. A label in prose has no field and keeps nothing."""

    def test_every_member_date_is_held(self):
        for text in EMPTY_BESIDE_BIRTH:
            with self.subTest(lines=text.splitlines()[2:4]):
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('missing', None))
                self.assertTrue(fact.evidence, 'the label is kept')
                self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))
                for member in (ELENA_DATE, '2026-10-14'):
                    self.assert_member_conflict(text, member)

    def test_a_field_that_states_no_date_never_questions_the_own_date(self):
        # it states no date that could differ: the note's own labelled date stands (the reading gate's PDF form - a blank
        # "Date of service:" over its filled form field - was asked when such a label spoke)
        for text in (HEAD + 'Endoscopy unit - procedure form\nDate of service:\nProcedure performed:\nExtent reached:\n\n'
                     '[PDF form fields on page 1]\ndos: 2026-10-14\nprocedure: Colonoscopy, screening, to the cecum\n'
                     + COLO_BODY,
                     HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nProcedure date: N/A\n' + COLO_BODY,
                     HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nVisit Date: TBD DOB (age) 01/01/1998\n'
                     + COLO_BODY):
            with self.subTest(lines=text.splitlines()[2:4]):
                self.assert_document(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)

    def test_controls_a_label_in_prose_keeps_nothing(self):
        text = HEAD + 'The procedure date was moved twice.\n' + COLO_BODY
        self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
        self.assert_member_date(text, '2026-10-14')


class EmptyDateFieldIsEvidenceRequestTests(EndToEnd):
    def test_v1_v2_the_member_s_1998_is_held(self):
        for text in EMPTY_BESIDE_BIRTH[:2]:
            with self.subTest(lines=text.splitlines()[2:4]):
                encounter_id = self.finished(text, service_date=ELENA_DATE)
                self.assert_held(encounter_id)
                self.assert_never_sent(encounter_id, ELENA_DATE)
