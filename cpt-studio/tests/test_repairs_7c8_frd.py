"""Repair round 7c8, the final refutation's dates track (FR-dates; studio/gi/context.py, the service date).

The final refutation attacked the integration head c3c034a08 (P2DN and its fix round) with two lenses, DATES-RULES and
DATES-INSTALLED; each finding below was demonstrated by the lens and reproduced by an independent verifier, end to end
through POST /api/encounters and POST /context with the suite's FakeProvider. Each is reproduced here first, then
repaired by a general rule of SOURCE or of the STRUCTURE of the label's own field - never a header-block requirement,
never a vocabulary of qualifiers, never a sentence the tests name - and rule N7 stays: nothing is sent that the
installed revision 057a7d398 would not send.

fr-dr:5  a lower-case "b." after a name ("Alex Synthetic b. 01/01/1998") was no birth label, so the date of birth was a
         subject line's own date: the note's labelled 10/14 became a question and a member's 1998-01-01 was taken.
fr-dr:2  a bracket after a bare "Date" or a date-of-service label on a dated line ("Date (signed):", "DOS (planned):")
         was read as the line's own date field, so the signing or planned date was the line's date: the labelled 10/14
         became a question and a member's 10/27 or 11/04 was taken and sent.
fr-dr:3  a date after another field's label on a subject line was that field's even after its value had ended ("Re:
         Colonoscopy - Referral date: 10/13/2026; performed 10/21/2026"): the line's own dated statement was silenced,
         and the labelled 10/14 it contradicts was sent.

Synthetic text only; no network (the suite's FakeProvider).
"""
from django.test import SimpleTestCase

from studio.gi import context
from tests.test_repairs_7c8_context import DateAssertions
from tests.test_repairs_7c8_context3 import COLO_BODY, ELENA_DATE, HEAD, EndToEnd, date_fact, evidence_text

BIRTH = '01/01/1998'


# --- fr-dr:5: "b." is a birth label as it is written - lower case - after a name too --------------------------------

B_AFTER_A_NAME = (  # the finding's line, its smallest form, and paraphrases: one space or a tab after a word
    'Re: Colonoscopy for Alex Synthetic b. 01/01/1998',
    'Re: EGD b. 01/01/1998',
    'Re: Colonoscopy for Alex b. 01/01/1998',
    'Regarding: Colonoscopy, Alex Synthetic\tb. 01/01/1998',
    'Subject: EGD for Synthetic Alex b. 1998-01-01',
    'Re: Colonoscopy for Alex Synthetic b. January 1, 1998',
)


class LowerCaseBirthLabelAfterANameTests(DateAssertions, SimpleTestCase):
    """fr-dr:5 (10bdfeb2f, P2DN's fix round issue 7, re-opened a62a18c85's gap): _BIRTH_LABEL read "b." only where no
    letter and one space or tab stood before it, so in "Re: Colonoscopy for Alex Synthetic b. 01/01/1998" the date of
    birth was the subject line's own date. Beside the note's own "Date of service: 10/14/2026" it made a document
    conflict listing 1998-01-01 (a dateless request where 057a7d398 sent 10/14), and a member's 1998-01-01 - entered at
    upload or as the answer to the date question - was taken as a listed documented value and sent. The issue-7 false
    positive was only a CAPITAL initial ("Alex B."), which the lower-case "b" already refuses: "b." written so is a
    birth label wherever it stands (rule N2)."""

    def test_the_note_s_own_date_stands_and_the_date_of_birth_is_never_taken(self):
        for line in B_AFTER_A_NAME:
            text = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\n' + line + '\n' + COLO_BODY
            with self.subTest(line=line):
                self.assert_document(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)
                self.assertFalse(any('1998' in quoted for quoted in evidence_text(text)), evidence_text(text))

    def test_alone_the_line_states_no_date_of_the_service(self):
        # the verifier's related shape: no labelled date - the line keeps its text before the date of birth, which reads
        # no date, so a member's 1998-01-01 is held
        for line in B_AFTER_A_NAME:
            text = HEAD + 'Colonoscopy report\n' + line + '\n' + COLO_BODY
            with self.subTest(line=line):
                self.assert_never(text, ELENA_DATE)
                self.assert_member_conflict(text, ELENA_DATE)

    def test_controls_a_capital_initial_is_still_no_birth_label(self):
        # issue 7's own shapes: "B." after a name is an initial; the line's own 10/14 answers, a member's 1998 is held
        for line in ('Re: Colonoscopy for Synthetic, Alex B. - 10/14/2026', 'EGD - Dr. Robin B. - 10/14/2026',
                     'Colonoscopy - Synthetic, Alex (b. 01/01/1998) - 10/14/2026',
                     'Colonoscopy - Synthetic, Alex, b. 01/01/1998 - 10/14/2026'):
            text = HEAD + line + '\n' + COLO_BODY
            with self.subTest(line=line):
                self.assert_member_date(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)


class LowerCaseBirthLabelAfterANameRequestTests(EndToEnd):
    TEXT = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nRe: Colonoscopy for Alex Synthetic b. 01/01/1998\n' \
        + COLO_BODY

    def test_the_member_s_date_of_birth_is_held_and_the_note_s_date_sent(self):
        held = self.finished(self.TEXT, service_date=ELENA_DATE)
        self.assert_held(held)
        self.assert_never_sent(held, ELENA_DATE)
        own = self.finished(self.TEXT)
        self.assertEqual(self.dates_sent(own), [['Date of service: 2026-10-14']])
        self.assertEqual(self.bucket(own, '45385'), 'selected')

    def test_the_answer_path_never_sends_the_date_of_birth(self):
        encounter_id = self.finished(HEAD + 'Colonoscopy report\nRe: Colonoscopy for Alex Synthetic b. 01/01/1998\n'
                                     + COLO_BODY)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assert_never_sent(encounter_id, ELENA_DATE)
        self.assertEqual(self.dates_sent(encounter_id), [[]])


# --- fr-dr:2: only a date format in a bracket keeps a "Date" field the line's own ---------------------------------------

BRACKET_WORDS = ('signed', 'dictated', 'referral', 'ordered', 'report', 'planned')
BRACKET_DATES = {'signed': '10/27/2026', 'dictated': '10/26/2026', 'referral': '10/13/2026', 'ordered': '10/12/2026',
                 'report': '10/28/2026', 'planned': '11/04/2026'}
BRACKET_LAYOUTS = {  # the note's own date or a dated text naming it, above a subject line
    'labelled date': 'Colonoscopy report\nDate of service: 10/14/2026\n',
    'dated title': 'Colonoscopy report - 10/14/2026\n',
    'letter date': 'Date: 10/14/2026\n',
    'dated service line': 'Colonoscopy - 10/14/2026\n',
}


def iso(us):
    month, day, year = us.split('/')
    return f'{year}-{month}-{day}'


class BracketAfterADateFieldTests(DateAssertions, SimpleTestCase):
    """fr-dr:2 (87fb157ca dropped a62a18c85's _GAP_FIELD; 10bdfeb2f's issue-1 rule - a date after ANOTHER field's label is
    that field's - read any bracket of up to 20 characters after "date" or a date-of-service label as part of the line's
    own date field): "Re: Colonoscopy - Date (signed): 10/27/2026" and "DOS (planned): 11/04/2026" gave the subject line
    the signing or planned date, so beside "Date of service: 10/14/2026" the note's own date became a question (a
    dateless request where a62a18c85 and 057a7d398 sent 10/14), and a member's 10/27 or 11/04 - at upload or as the
    answer - was taken as a listed documented value and sent (45385 excluded against the planned date). A bracket that
    names another event makes the field another field's: only a date format ("(mm/dd/yyyy)") or "(DOS)" keeps it the
    line's own date field."""

    def test_the_finding_s_lines_beside_the_labelled_date(self):
        for subject, other in (('Re: Colonoscopy - Date (signed): 10/27/2026', '2026-10-27'),
                               ('Re: Colonoscopy - DOS (planned): 11/04/2026', '2026-11-04')):
            text = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\n' + subject + '\n' + COLO_BODY
            with self.subTest(subject=subject):
                self.assert_document(text, '2026-10-14')
                self.assert_member_conflict(text, other)

    def test_the_family_in_four_layouts(self):
        for layout, top in BRACKET_LAYOUTS.items():
            for word in BRACKET_WORDS:
                for label in ('Date', 'DOS', 'Date of service'):
                    other = BRACKET_DATES[word]
                    text = HEAD + top + f'Re: Colonoscopy - {label} ({word}): {other}\n' + COLO_BODY
                    with self.subTest(layout=layout, line=text.splitlines()[-4]):
                        self.assert_never(text, iso(other))
                        self.assert_member_conflict(text, iso(other))
                        if layout == 'labelled date':
                            self.assert_document(text, '2026-10-14')
                        else:  # the dated text above is evidence: asked, and its 10/14 answers
                            self.assert_member_date(text, '2026-10-14')

    def test_controls_a_date_format_keeps_the_line_s_own_date_field(self):
        for subject in ('Re: Colonoscopy - Date (mm/dd/yyyy): 10/14/2026', 'Re: Colonoscopy - Date (MM/DD/YYYY): 10/14/2026',
                        'Re: Colonoscopy - Date of service (DOS): 10/14/2026', 'Re: Colonoscopy - Date: 10/14/2026',
                        'Re: Colonoscopy - DOS (yyyy-mm-dd): 2026-10-14'):
            text = HEAD + 'Colonoscopy report\n' + subject + '\n' + COLO_BODY
            with self.subTest(subject=subject):
                self.assert_member_date(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)
        # another field's label without a bracket is still another field's (issue 1)
        text = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nRe: Colonoscopy - Signed: 10/27/2026\n' + COLO_BODY
        self.assert_document(text, '2026-10-14')
        self.assert_member_conflict(text, '2026-10-27')


class BracketAfterADateFieldRequestTests(EndToEnd):
    TEXT = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nRe: Colonoscopy - Date (signed): 10/27/2026\n' \
        + COLO_BODY
    PLANNED = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nRe: Colonoscopy - DOS (planned): 11/04/2026\n' \
        + COLO_BODY

    def test_the_note_s_date_is_sent_and_the_other_event_s_date_held(self):
        own = self.finished(self.TEXT)
        self.assertEqual(self.dates_sent(own), [['Date of service: 2026-10-14']])
        self.assertEqual(self.bucket(own, '45385'), 'selected')
        for text, other in ((self.TEXT, '2026-10-27'), (self.PLANNED, '2026-11-04')):
            with self.subTest(other=other):
                held = self.finished(text, service_date=other)
                self.assert_held(held)
                self.assert_never_sent(held, other)

    def test_the_answer_path_never_sends_the_signing_date(self):
        # the verifier's E7: the head asked (a dateless request), then took the member's 10/27 as a listed value and sent
        # a second paid request with it
        encounter_id = self.finished(self.TEXT)
        self.set_context(encounter_id, {'service_date': '2026-10-27'})
        self.assert_never_sent(encounter_id, '2026-10-27')
        self.assertEqual(self.dates_sent(encounter_id), [['Date of service: 2026-10-14']])


# --- fr-dr:3: a field's value ends; a date after its end is not that field's ------------------------------------------

COLO_PLAIN_BODY = ('PROCEDURE NOTE: Colonoscopy\nTechnique: The colonoscope was advanced to the cecum.\n'
                   'Findings: A 5 mm sigmoid polyp was removed with a cold snare.\n')
AFTER_THE_VALUE = (  # the finding's line, its three variants, the smallest form and an undated field
    'Re: Colonoscopy - Referral date: 10/13/2026; performed 10/21/2026',
    'Re: Colonoscopy - Ordered: 10/13/2026, done 10/21/2026',
    'Re: Colonoscopy - Referral date: 10/13/2026 - performed on 10/21/2026',
    'Re: Colonoscopy (referral date: 10/13/2026) performed 10/21/2026',
    'Re: Colonoscopy - Ref: 10/13/2026; 10/21/2026',
    'Re: Colonoscopy - Referral: Dr. Synthetic; performed 10/21/2026',
    'Regarding: EGD - Ordered: 10/13/2026    10/21/2026',
)


class DateAfterAFieldSValueEndedTests(DateAssertions, SimpleTestCase):
    """fr-dr:3 (10bdfeb2f's issue-1 rule): _other_field gave a date to the last colon's field whatever stood between
    them, so in "Re: Colonoscopy - Referral date: 10/13/2026; performed 10/21/2026" the performed date was the referral
    field's: both dates were excluded, the subject line kept as evidence that reads no date (form 'empty', which never
    speaks), and the labelled "Date of service: 10/14/2026" it contradicts was documented and sent with 45385 ready
    (a62a18c85 asked). A field's value ends - at a semicolon, a comma, a spaced dash, a bracket it does not open, a field
    break or the field's own date - and a date after that end is not that field's: the line states a date this service
    cannot place (neither the field's nor certainly the line's own), so the line speaks against the labelled date (asked)
    and its evidence reads no date (every member date it alone would agree with is held)."""

    def test_beside_the_labelled_date_the_date_is_asked(self):
        for line in AFTER_THE_VALUE:
            text = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\n' + line + '\n' + COLO_PLAIN_BODY
            with self.subTest(line=line):
                self.assert_never(text, '2026-10-14')
                self.assertIn(date_fact(text).origin, ('conflict', 'missing'))
                self.assert_member_date(text, '2026-10-14')
                self.assert_member_conflict(text, '2026-10-21')
                self.assert_member_conflict(text, '2026-10-13')

    def test_under_a_dated_title_no_other_field_s_date_is_taken(self):
        for line in AFTER_THE_VALUE:
            text = HEAD + 'Colonoscopy report - 10/14/2026\n' + line + '\n' + COLO_PLAIN_BODY
            with self.subTest(line=line):
                self.assert_member_date(text, '2026-10-14')
                self.assert_member_conflict(text, '2026-10-13')
                self.assert_member_conflict(text, ELENA_DATE)

    def test_controls_the_field_s_own_date_is_still_the_field_s(self):
        # issue 1's shapes: the date right after another field's label is that field's; the labelled date stands
        for line in ('Re: Colonoscopy - Referral date: 10/13/2026', 'Re: Colonoscopy - Signed: 10/27/2026',
                     'Re: Colonoscopy for Alex Synthetic, DOB (mm/dd/yyyy): 01/01/1998'):
            text = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\n' + line + '\n' + COLO_PLAIN_BODY
            with self.subTest(line=line):
                self.assert_document(text, '2026-10-14')
        # no field before the date: the line's own date, which questions the labelled one (the verifier's control)
        self.assert_conflict(HEAD + 'Date of service: 10/14/2026\nRe: Colonoscopy performed 10/21/2026\n'
                             + COLO_PLAIN_BODY, '2026-10-14', '2026-10-21')
        # a date right after the service's name keeps the line's own date beside a later field's
        self.assert_member_date(HEAD + 'EGD 10/14/2026    Signed: 10/27/2026\n' + COLO_PLAIN_BODY, '2026-10-14')


class DateAfterAFieldSValueEndedRequestTests(EndToEnd):
    def test_no_date_is_sent_where_the_subject_line_differs(self):
        text = (HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nRe: Colonoscopy - Referral date: 10/13/2026; '
                'performed 10/21/2026\n' + COLO_PLAIN_BODY)
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assert_not_excluded(encounter_id, '45385')
        self.set_context(encounter_id, {'service_date': '2026-10-21'})
        self.assert_never_sent(encounter_id, '2026-10-21')
