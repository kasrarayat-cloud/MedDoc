"""Repair round 7c8, the final refutation's dates track (FR-dates; studio/gi/context.py, the service date).

The final refutation attacked the integration head c3c034a08 (P2DN and its fix round) with two lenses, DATES-RULES and
DATES-INSTALLED; each finding below was demonstrated by the lens and reproduced by an independent verifier, end to end
through POST /api/encounters and POST /context with the suite's FakeProvider. Each is reproduced here first, then
repaired by a general rule of SOURCE or of the STRUCTURE of the label's own field - never a header-block requirement,
never a vocabulary of qualifiers, never a sentence the tests name - and rule N7 stays: nothing is sent that the
installed revision 057a7d398 would not send.

fr-dr:5  a lower-case "b." after a name ("Alex Synthetic b. 01/01/1998") was no birth label, so the date of birth was a
         subject line's own date: the note's labelled 10/14 became a question and a member's 1998-01-01 was taken.

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
