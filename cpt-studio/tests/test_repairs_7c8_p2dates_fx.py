"""Repair round 7c8, refutation phase 2, cluster P2DATES - the fix round after the cluster's skeptic.

The skeptic of the P2DATES repair (dfb3181de .. cf83eb511) demonstrated seven must-fix issues (class 1: a date sent, or
a member's date taken, where P2FIX's rules ask the date), each re-checked here at its smallest input first. The rule
direction stays P2FIX's: fail closed by SOURCE, never by vocabulary - what may stand beside a sent date is a closed
list, and anything else asks the date.

sk:1  a label carrying words the reader cannot place ("Initial visit date", "Cancelled procedure date") on a header line
      was the sent date. Only a date-of-service label READ as the note's own - the closed list of labels, at most with
      the name of a service this release codes - is ever the note's date, as at 2fc8cde3d.
sk:2  a date-of-birth field's value was never read ("DOB: 01/01/1998, outside records reviewed", "DOB: 01/01/1998
      Status: Scheduled"). A birth field holds its date alone, or its line is no header line.
sk:3  a date-of-service label whose field opens with another field ("Date of Service: Referral date: 10/13/2026") was
      dropped, so any member date was taken. The label is kept as evidence that reads no date: every member date is
      held, as for "Date of service: 20-Oct-26".
sk:4  a birth label the reader did not know ("DOB/Age", "DOB (age)", "Birthday", "D-O-B"), or a word before the date
      ("Visit Date: TBD DOB (age) 01/01/1998"), made a date of birth a label's value. A label's own value opens its
      field: a field opened by anything else states no date. The birth labels are read in those forms too.
sk:5  a title-shaped heading whose qualifier is outside the vocabulary ("Cancelled colonoscopy", "Recall procedure")
      stood as the document's title.
sk:6  a header value held a qualifier outside the vocabulary ("Patient status: pending authorization", "Setting:
      cancelled", "Provider: Dr. A. Synthetic (procedure postponed)").
sk:7  another discipline's undated title over a date-of-service label ("Cardiology consultation") stood as the title.

An over-hold (the date asked although a coder would know it) is a known limit; a wrong date sent is not. Synthetic text
only; no network (the suite's FakeProvider, answering only the selections whose quote the request's text holds).
"""
from django.test import SimpleTestCase

from studio.gi import context
from tests.test_repairs_7c8_context import DateAssertions
from tests.test_repairs_7c8_context3 import COLO_BODY, ELENA_DATE, HEAD, EndToEnd, date_fact

OFFICE = ('Established patient office visit for chronic constipation.\n'
          'Total time on the date of the encounter was 24 minutes.\n')
# The skeptic's qualifier words: the first few are in the round-3 vocabulary, every other one is outside it (dates:8).
QUALIFIERS = ('Outside', 'Prior', 'Next', 'Planned', 'Scheduled', 'Recall', 'Due', 'Cancelled', 'Postponed', 'Pending',
              'Booked', 'Original', 'Initial', 'Deferred', 'Referral', 'Admission', 'Discharge', 'Surgery', 'Pathology',
              'Imaging', 'Lab', 'Rescheduled', 'Tentative')


class LabelWordsTests(DateAssertions, SimpleTestCase):
    """sk:1: the repair counted a label read 'unplaced' - its words name nothing this release codes - as the note's own
    date when it stood on a header line, so "Initial visit date: 01/15/2025" was sent and 99213 made ready, and a
    recall, cancelled or referral visit's date was sent and the act done on 10/14 excluded against it."""

    CASES = (
        (HEAD + 'GI follow-up visit\nName: Alex Synthetic | Initial visit date: 01/15/2025 | MRN: 0000\n\n' + OFFICE,
         '2025-01-15', 'Initial visit date'),
        (HEAD + 'Patient: Synthetic, Alex    Cancelled procedure date: 11/04/2026\n\n' + COLO_BODY, '2026-11-04',
         'Cancelled procedure date'),
        (HEAD + 'Name: Alex Synthetic | Recall visit date: 11/04/2026 | MRN: 0000\n\n' + COLO_BODY, '2026-11-04',
         'Recall visit date'),
        (HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    Referral visit date: 09/01/2026\n\n' + COLO_BODY,
         '2026-09-01', 'Referral visit date'),
    )

    def test_a_label_with_words_the_reader_cannot_place_is_asked(self):
        for text, other, label in self.CASES:
            with self.subTest(label=label):
                self.assert_never(text, other)
                self.assert_asked(text, label)
                self.assert_member_date(text, other)  # the member may still choose the date the label states
                self.assertIn(context.UNPLACED_DATE_NOTE, date_fact(text).note)
                self.assertNotIn(context.HEADER_DATE_NOTE, date_fact(text).note)

    def test_every_label_word_outside_a_service_name_is_asked(self):
        # the skeptic's reader fuzz: 'Patient: Synthetic, Alex    {Q} {procedure date|DOS}: {date}' and a blank line
        for word in QUALIFIERS:
            for label in ('procedure date', 'DOS', 'visit date', 'date of service'):
                for line in (f'Patient: Synthetic, Alex    {word} {label}: 11/04/2026',
                             f'Name: Alex Synthetic | {word} {label}: 11/04/2026 | MRN: 0000'):
                    text = HEAD + line + '\n\n' + COLO_BODY
                    with self.subTest(line=line):
                        self.assert_never(text, '2026-11-04')

    def test_controls_the_plain_label_and_a_service_s_name(self):
        self.assert_document(HEAD + 'Patient: Synthetic, Alex    Procedure date: 10/14/2026\n\n' + COLO_BODY,
                             '2026-10-14')
        self.assert_document(HEAD + 'Patient: Synthetic, Alex    Colonoscopy procedure date: 10/14/2026\n\n'
                             + COLO_BODY, '2026-10-14')
        self.assert_document(HEAD + 'Name: Alex Synthetic | Visit date: 10/14/2026 | MRN: 0000\n\n' + OFFICE,
                             '2026-10-14')
        self.assert_document(HEAD + "Name: Alex Synthetic | Today's visit date: 10/14/2026 | MRN: 0000\n\n" + OFFICE,
                             '2026-10-14')


class RequestTests(EndToEnd):
    """Every issue end to end: the date each provider request carries, and the dated check that excluded an act."""

    def assert_dateless(self, text, code):
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assertNotEqual(self.bucket(encounter_id, code), 'excluded')
        return encounter_id

    def test_sk1_a_label_with_words_the_reader_cannot_place(self):
        self.assert_dateless(LabelWordsTests.CASES[0][0], '99213')
        for text, _, label in LabelWordsTests.CASES[1:]:
            with self.subTest(label=label):
                self.assert_dateless(text, '45385')

    def test_control_a_header_block_s_date_is_sent(self):
        encounter_id = self.finished(HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998    MRN: '
                                     '0000\nDate of service: 10/14/2026\nEndoscopist: Dr. A. Synthetic\n\n' + COLO_BODY)
        self.assertEqual(self.dates_sent(encounter_id), [['Date of service: 2026-10-14']])
        self.assertNotEqual(self.bucket(encounter_id, '45385'), 'excluded')
