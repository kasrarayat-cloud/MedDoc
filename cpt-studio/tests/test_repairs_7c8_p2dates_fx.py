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
import time

from django.test import SimpleTestCase

from studio.gi import context
from studio.types import Span
from tests.test_repairs_7c8_context import DateAssertions
from tests.test_repairs_7c8_context3 import (BIRTH, COLO_BODY, EGD_BODY, ELENA_DATE, HEAD, EndToEnd, date_fact,
                                             evidence_text)

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


class EmptyDateFieldTests(DateAssertions, SimpleTestCase):
    """sk:3 (and the dates:0 class): a date-of-service label whose field opens with another field was dropped with
    nothing left behind (round 2's rule A), so any member date was taken - 1998-01-01 was sent and 45385 excluded as
    planned. The label is kept as evidence that reads no date: every member date is held, as for "Date of service:
    20-Oct-26"."""

    CASES = (
        HEAD + 'Colonoscopy report\nDate of Service: Referral date: 10/13/2026\n' + COLO_BODY,
        HEAD + 'Colonoscopy report\nDOS: N/A Referral date: 10/13/2026\n' + COLO_BODY,
        HEAD + 'Colonoscopy report\nDate of service: Admission date: 10/13/2026\n' + COLO_BODY,
        HEAD + 'Colonoscopy report\nDOS: Signed: 10/13/2026\n' + COLO_BODY,
        HEAD + 'Colonoscopy report\nDate of service: DOB: 01/01/1998\n' + COLO_BODY,
        HEAD + 'Colonoscopy report\nDate of Service | Provider\nN/A 10/13/2026 | Dr. A. Synthetic\n' + COLO_BODY,
    )

    def test_an_empty_date_field_is_kept_and_every_member_date_is_held(self):
        for text in self.CASES:
            with self.subTest(line=text.splitlines()[2]):
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('missing', None))
                self.assertTrue(fact.evidence, 'the label is kept as evidence')
                self.assertIsNone(context._date_readings(fact.evidence), evidence_text(text))
                self.assertIn(context.UNREAD_DATE_NOTE, fact.note)
                for value in (ELENA_DATE, '2026-10-13', '2026-10-14'):
                    self.assert_member_conflict(text, value)

    def test_the_date_another_candidate_states_still_answers(self):
        text = HEAD + 'Colonoscopy report - 10/14/2026\nDate of Service: Referral date: 10/13/2026\n' + COLO_BODY
        self.assert_member_date(text, '2026-10-14')
        self.assert_member_conflict(text, '2026-10-13')
        self.assert_member_conflict(text, ELENA_DATE)

    def test_controls(self):
        # a field that states nothing at all keeps nothing, as before: the member supplies the date
        text = HEAD + 'Colonoscopy report\nDate of service: N/A\n' + COLO_BODY
        self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
        self.assert_member_date(text, '2026-10-14')
        # a date in a form the reader does not read is held as before
        text = HEAD + 'Colonoscopy report\nDate of service: 20-Oct-26\n' + COLO_BODY
        self.assert_member_conflict(text, '2026-10-20')


class BirthLabelFormTests(DateAssertions, SimpleTestCase):
    """sk:4 (dates:0, still reproducing): with a birth label the reader did not know, or a word between a date label and
    the date, a date-of-service label's value was the date of birth - the member's 1998-01-01 agreed with it, was sent,
    and 45385 was excluded. A label's own value opens its field; a date anywhere else in it is not the label's."""

    FORMS = ('DOB/Age', 'Age/DOB', 'DOB (age)', 'Birth', 'Birthday', 'D-O-B', 'DOB/Age:', 'Birth:', '-- DOB/Age',
             'TBD DOB', 'Birth date', 'DOB & Age')

    def shapes(self, form):
        return (HEAD + f'Colonoscopy report - 10/14/2026\nPatient: Alex Synthetic DOS: {form} 01/01/1998 MRN: 0000\n'
                + COLO_BODY,
                HEAD + f'Colonoscopy report - 10/14/2026\nPatient: Alex Synthetic DOS: {form} 01/01/1998 MRN 0000\n'
                + COLO_BODY,
                HEAD + f'Colonoscopy report - 10/14/2026\nPatient: Alex Synthetic DOS: -- {form} 01/01/1998 MRN 0000\n'
                + COLO_BODY,
                HEAD + f'Colonoscopy report\nDate of service: 10/14/2026\nVisit Date: {form} 01/01/1998\n' + COLO_BODY)

    def test_a_date_of_birth_is_never_a_label_s_value(self):
        for form in self.FORMS:
            for text in self.shapes(form):
                with self.subTest(form=form, line=text.splitlines()[2][:60]):
                    self.assert_never(text, ELENA_DATE)
                    self.assert_member_conflict(text, ELENA_DATE)
                    self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))
                    self.assert_member_date(text, '2026-10-14')  # the date the note states still answers

    def test_a_label_s_value_opens_its_field(self):
        text = HEAD + 'Colonoscopy report - 10/14/2026\nDOS: approx. 10/13/2026\n' + COLO_BODY
        self.assert_member_conflict(text, '2026-10-13')  # a date after other words in the field is not the label's
        self.assert_member_date(text, '2026-10-14')

    def test_the_birth_label_forms_are_read_as_birth_labels(self):
        for quoted in ('Birthday 01/01/1998 10/14/2026', 'Birth: 01/01/1998; colonoscopy 10/14/2026',
                       'D-O-B 01/01/1998 seen 10/14/2026', 'DOB/Age: 01/01/1998 / 28, colonoscopy 10/14/2026',
                       'Age/DOB 01/01/1998, colonoscopy 10/14/2026', 'DOB (age) 01/01/1998 colonoscopy 10/14/2026'):
            with self.subTest(quoted=quoted):
                self.assertEqual(context._date_readings((Span(0, len(quoted), quoted),)), {'2026-10-14'})
        # a subject line's own date is its only date that is no date of birth, whatever form the birth label takes
        for label in ('Birthday', 'D-O-B', 'DOB/Age'):
            text = HEAD + f'Re: Colonoscopy - Synthetic, Alex ({label} 01/01/1998) - 10/14/2026\n' + COLO_BODY
            with self.subTest(label=label):
                self.assert_member_date(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)
        # a dated service line whose only date is a date of birth states no date of the service
        text = HEAD + 'Colonoscopy - Synthetic, Alex - Birthday 01/01/1998\n' + COLO_BODY
        self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))

    def test_controls(self):
        # a value that opens its field keeps answering: a weekday before the date, a value on the next line, a column
        for text in (HEAD + 'Colonoscopy report\nDate of service: Tuesday, October 14, 2026\n\n' + COLO_BODY,
                     HEAD + 'Colonoscopy report\nDate of service:\n10/14/2026\n\n' + COLO_BODY,
                     HEAD + 'Colonoscopy report\nDate of Service | Provider\n10/14/2026 | Dr. A. Synthetic\n\n'
                     + COLO_BODY):
            with self.subTest(text=text.splitlines()[2]):
                self.assert_member_date(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)
        # a birth word that labels no date is no birth label ("Birth control" in a sentence)
        text = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\n\n' + COLO_BODY + 'Birth control since 2020.\n'
        self.assert_document(text, '2026-10-14')


DISCIPLINES = ('Cardiology', 'Surgical', 'General surgery', 'Oncology', 'Hematology', 'Pulmonology', 'Dermatology',
               'Gynecology', 'Urology', 'Nephrology', 'Primary care', 'PCP', 'Emergency department', 'Urgent care',
               'Pre-anesthesia', 'Radiology', 'Pathology', 'Surgical pathology')


class BirthFieldValueTests(DateAssertions, SimpleTestCase):
    """sk:2: a "DOB" head's value - everything up to the next head - was never read, so a qualifier, a field or a
    sentence after a date of birth on a header line left the labelled date documented: it was sent, and 45385 was
    excluded as planned. A birth field holds its date alone."""

    CASES = (
        (HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998, outside records reviewed\n'
                'Procedure date: 09/03/2026\n\n' + COLO_BODY, '2026-09-03'),
        (HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998 outside    Procedure date: 09/03/2026'
                '\n\n' + COLO_BODY, '2026-09-03'),
        (HEAD + 'EGD report\nPatient: Synthetic, Alex    DOB: 01/01/1998    Status: Scheduled\nProcedure date: '
                '11/04/2026\n\n' + EGD_BODY, '2026-11-04'),
        (HEAD + 'EGD report\nProcedure date: 11/04/2026\nDOB: 01/01/1998    Status: Scheduled\n\n' + EGD_BODY,
         '2026-11-04'),
        (HEAD + 'EGD report\nProcedure date: 11/04/2026\nDOB: 01/01/1998 (procedure postponed)\n\n' + EGD_BODY,
         '2026-11-04'),
        # words outside the round-3 vocabulary: the label reads 'own', so only the birth value read holds the date
        (HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998, cancelled\nProcedure date: '
                '09/03/2026\n\n' + COLO_BODY, '2026-09-03'),
        (HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998 (recall)\nProcedure date: 09/03/2026'
                '\n\n' + COLO_BODY, '2026-09-03'),
        (HEAD + 'EGD report\nPatient: Synthetic, Alex    DOB: 01/01/1998    Status: Pending\nProcedure date: '
                '11/04/2026\n\n' + EGD_BODY, '2026-11-04'),
        (HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998 postponed    Procedure date: '
                '09/03/2026\n\n' + COLO_BODY, '2026-09-03'),
        (HEAD + 'EGD report\nProcedure date: 11/04/2026\nDOB: 01/01/1998    Status: Pending\n\n' + EGD_BODY,
         '2026-11-04'),
        # the same birth field two paragraphs above the label: it ends the header, as any line that is no header does
        (HEAD + 'EGD report\nPatient: Synthetic, Alex    DOB: 01/01/1998    Status: Scheduled\n\nMRN: 0000\n\n'
                'Procedure date: 11/04/2026\n\n' + EGD_BODY, '2026-11-04'),
    )

    def test_anything_after_a_date_of_birth_asks_the_date(self):
        for text, other in self.CASES:
            with self.subTest(lines=' / '.join(text.splitlines()[2:4])[:90]):
                self.assert_never(text, other)
                self.assert_asked(text, 'rocedure date')
                self.assert_member_date(text, other)
                self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))

    def test_controls_a_date_of_birth_alone_in_its_field(self):
        for line in ('Patient: Synthetic, Alex    DOB: 01/01/1998    MRN: 0000',
                     'Name: Alex Synthetic | DOB: 01/01/1998 | Age: 28', 'Patient: Synthetic, Alex    DOB 1/1/1998',
                     'Patient: Synthetic, Alex    Date of birth: Jan 1, 1998', 'DOB/Age: 01/01/1998    Sex: F'):
            with self.subTest(line=line):
                text = HEAD + 'Colonoscopy report\n' + line + '\nProcedure date: 09/03/2026\n\n' + COLO_BODY
                self.assert_document(text, '2026-09-03')
                self.assert_member_conflict(text, ELENA_DATE)


class HeaderValueTests(DateAssertions, SimpleTestCase):
    """sk:6: a header value held the date only through the round-3 vocabulary, reached through header labels beyond
    P2FIX's list ("Patient status", "Setting") and through "Provider": 11/04 was sent and 43239 excluded as historical.
    The header labels are P2FIX's closed list; a header value naming an occurrence ends the header; and in a label's
    block a header value holds a name, a number or a code."""

    CASES = ('Patient status: pending authorization', 'Setting: cancelled', 'Setting: Cancelled',
             'Provider: Dr. A. Synthetic (procedure postponed)', 'Provider: Dr. A. Synthetic, procedure postponed',
             'Place of service: Office - cancelled', 'Patient status: Pending', 'Facility: Synthetic Hospital; outside',
             'Endoscopist: Dr. A. Synthetic - booked, not done', 'Provider: Dr. A. Synthetic - Procedure Postponed',
             'Referring physician: Dr. B. Synthetic (pending)')

    def test_a_qualifier_in_a_header_value_asks_the_date(self):
        for line in self.CASES:
            for where in ('below', 'above'):
                block = (f'Procedure date: 11/04/2026\n{line}\n\n' if where == 'below'
                         else f'{line}\nProcedure date: 11/04/2026\n\n')
                text = HEAD + 'EGD report\n' + block + EGD_BODY
                with self.subTest(line=line, where=where):
                    self.assert_never(text, '2026-11-04')
                    self.assert_asked(text, 'Procedure date')
                    self.assert_member_date(text, '2026-11-04')

    def test_a_header_value_naming_an_occurrence_holds_from_anywhere_in_the_header(self):
        for line in ('Provider: Dr. A. Synthetic (procedure postponed)', 'Provider: Dr. A. Synthetic - Procedure Postponed',
                     'Referring physician: Dr. B. Synthetic for colonoscopy', 'Location: Endoscopy suite, visit cancelled'):
            text = HEAD + 'EGD report\n' + line + '\n\nPatient: Synthetic, Alex\n\nProcedure date: 11/04/2026\n\n' + EGD_BODY
            with self.subTest(line=line):
                self.assert_never(text, '2026-11-04')

    def test_the_skeptic_s_patient_status_family_is_asked(self):
        for word in QUALIFIERS:
            for noun in ('colonoscopy', 'procedure'):
                text = (HEAD + 'Procedure date: 09/03/2026\n' + f'Patient status: {word.lower()} {noun}\n\n'
                        + COLO_BODY)
                with self.subTest(word=word, noun=noun):
                    self.assert_never(text, '2026-09-03')

    def test_controls_a_name_a_number_or_a_code(self):
        for lines in ('Provider: Dr. A. Synthetic', 'Endoscopist: Dr. A. Synthetic, MD    MRN: SYN-0003',
                      'Patient: Synthetic, Alex    Age: 28    Sex: F', 'Referring physician: Dr. B. Synthetic',
                      'Facility: Synthetic Endoscopy Center', 'Account number: 12345', 'Location: Suite 3'):
            with self.subTest(lines=lines):
                text = HEAD + 'EGD report\nProcedure date: 10/14/2026\n' + lines + '\n\n' + EGD_BODY
                self.assert_document(text, '2026-10-14')
        # a header value holding a phrase may stand in the header above the label's block: the live gi-03 shape
        text = (HEAD + '\nRiverside Endoscopy Unit (fictional)\nColonoscopy procedure report\n\nPatient: Alex Synthetic '
                '(fictional)\n\nSynthetic record: SYN-0003\n\nDate of procedure: 2026-10-14\n\n' + COLO_BODY)
        self.assert_document(text, '2026-10-14')


class TitleHeadingTests(DateAssertions, SimpleTestCase):
    """sk:5 and sk:7: a line at the top counted as the document's title unless it held a word of the round-3
    vocabulary, so "Cancelled colonoscopy", "Colonoscopy report" over "Recall procedure", or "Cardiology consultation"
    above a date-of-service label let the label's date be sent (45385 excluded as planned, or needs_clarification)."""

    def test_a_heading_with_a_qualifier_outside_any_list_is_asked(self):
        self.assert_asked(HEAD + 'Cancelled colonoscopy\nProcedure date: 11/04/2026\n\n' + COLO_BODY, 'Procedure date')
        self.assert_asked(HEAD + 'Colonoscopy report\nRecall procedure\nProcedure date: 11/04/2026\n\n' + COLO_BODY,
                          'Procedure date')
        for word in QUALIFIERS:
            for noun in ('colonoscopy', 'procedure'):
                for label in ('Procedure date', 'Date of service', 'DOS'):
                    for title in ('', 'Colonoscopy report\n'):
                        text = HEAD + f'{title}{word} {noun}\n{label}: 11/04/2026\n\n' + COLO_BODY
                        with self.subTest(heading=f'{word} {noun}', label=label, title=bool(title)):
                            self.assert_never(text, '2026-11-04')
                            self.assert_member_date(text, '2026-11-04')

    def test_a_heading_two_paragraphs_up_still_holds_the_date(self):
        for heading in ('Cancelled colonoscopy', 'Recall procedure', 'Cardiology consultation'):
            for title in ('', 'Colonoscopy report\n'):
                with self.subTest(heading=heading, title=bool(title)):
                    text = (HEAD + title + heading + '\n\nPatient: Synthetic, Alex\n\nProcedure date: 11/04/2026\n\n'
                            + COLO_BODY)
                    self.assert_never(text, '2026-11-04')
        # a line naming nothing below the title is a heading, never a letterhead
        for heading in ('CANCELLED', 'Recall', 'Pending authorization'):
            with self.subTest(heading=heading):
                text = (HEAD + 'Colonoscopy report\n' + heading + '\n\nPatient: Synthetic, Alex\n\nProcedure date: '
                        '11/04/2026\n\n' + COLO_BODY)
                self.assert_never(text, '2026-11-04')

    def test_a_line_in_the_block_that_is_no_title_is_a_heading(self):
        for line in ('CANCELLED', 'Recall', 'Endoscopy Suite 3', 'Page 1 of 2'):
            with self.subTest(line=line):
                self.assert_asked(HEAD + line + '\nDate of service: 11/04/2026\n\n' + COLO_BODY, 'Date of service')
                self.assert_asked(HEAD + 'Colonoscopy report\n' + line + '\nDate of service: 11/04/2026\n\n' + COLO_BODY,
                                  'Date of service')

    def test_another_discipline_s_title_is_no_title_of_this_note(self):
        self.assert_asked(HEAD + 'Cardiology consultation\nDate of service: 10/09/2026\n\n' + COLO_BODY,
                          'Date of service')
        for discipline in DISCIPLINES:
            for word in ('consultation', 'consult', 'visit', 'note', 'report'):
                for label in ('Date of service', 'Visit date'):
                    text = HEAD + f'{discipline} {word}\n{label}: 10/09/2026\n\n' + COLO_BODY
                    with self.subTest(title=f'{discipline} {word}', label=label):
                        self.assert_never(text, '2026-10-09')
                        self.assert_member_date(text, '2026-10-09')
        # another discipline's name alone heads its own document wherever it stands: never a letterhead
        for heading in ('Pathology', 'Surgical pathology', 'Radiology', 'Laboratory', 'Anesthesia'):
            for title in ('', 'Colonoscopy report\n'):
                with self.subTest(heading=heading, title=bool(title)):
                    text = (HEAD + heading + '\n' + title + '\nPatient: Synthetic, Alex\n\nDate of service: 10/09/2026\n\n'
                            + COLO_BODY)
                    self.assert_never(text, '2026-10-09')
        # the same title as the document's first line, with no banner above it
        for title in ('Cardiology consultation', 'Pathology report', 'Radiology note', 'Discharge summary'):
            with self.subTest(first_line=title):
                self.assert_never(title + '\nDate of service: 10/09/2026\n\n' + COLO_BODY, '2026-10-09')

    def test_controls_a_title_of_this_note(self):
        for title in ('Colonoscopy report', 'COLONOSCOPY PROCEDURE REPORT', 'Screening colonoscopy', 'GI office visit',
                      'Gastroenterology consultation', 'Upper endoscopy report', 'EGD procedure note',
                      'Established patient visit - office progress note', 'Colonoscopy report - 10/14/2026',
                      'Procedure report - upper endoscopy and colonoscopy in the same session', 'Telehealth visit',
                      'Endoscopic ultrasound procedure report'):
            with self.subTest(title=title):
                self.assert_document(HEAD + title + '\nDate of service: 10/14/2026\n\n' + COLO_BODY, '2026-10-14')
        # a letterhead above the title, outside the label's block, is the document's; so is its banner
        for letterhead in ('Riverside Endoscopy Unit (fictional)', 'Northgate Ambulatory Endoscopy Center (fictional)',
                           'St. Brigid Medical Center (fictional) - Advanced Endoscopy'):
            with self.subTest(letterhead=letterhead):
                text = (HEAD + '\n' + letterhead + '\nColonoscopy procedure report\n\nPatient: Alex Synthetic\n\n'
                        'Synthetic record: SYN-0003\n\nDate of procedure: 2026-10-14\n\n' + COLO_BODY)
                self.assert_document(text, '2026-10-14')
        self.assert_document(HEAD + 'Date of service: 10/14/2026\n\n' + COLO_BODY, '2026-10-14')
        self.assert_document('Riverside GI Associates\nDate of service: 10/14/2026\n\n' + COLO_BODY, '2026-10-14')
        # a letterhead with no title below it, outside the label's block (the suite's office note)
        self.assert_document(HEAD + 'Riverbend Digestive Health (fictional)\n\nPatient: Alex Synthetic\n\nDate of '
                             'service: 10/14/2026\n\n' + COLO_BODY, '2026-10-14')


class ReadingCostTests(SimpleTestCase):
    """Every scan this round changes reads each line, field and title line once: the time doubles with the text, never
    squares (a doubling ratio near 4 over two doublings; quadratic would be 16), and the largest is read far inside a
    member's 15 s. The paste-cap figures through the bounded children are in the commit."""

    SHAPES = {
        'birth forms on one line': lambda n: HEAD + 'DOS: Age/DOB 01/01/1998 ' * n + '\n',
        'fields opened by a field': lambda n: HEAD + 'DOS: Referral date: 10/13/2026 ' * n + '\n',
        'words before dates': lambda n: HEAD + 'Visit date: TBD DOB (age) 01/01/1998 ' * n + '\n',
        'phrase header lines': lambda n: HEAD + 'Provider: Dr. A. Synthetic (fictional)\n' * n + 'DOS: 10/14/2026\n\n',
        'one long header value': lambda n: HEAD + 'Provider: Dr. ' + 'Ab ' * n + '\nDOS: 10/14/2026\n\n',
        'one long birth value': lambda n: HEAD + 'DOB: 01/01/1998 ' + 'x ' * n + '\nDOS: 10/14/2026\n\n',
        'labels beside phrase lines': lambda n: HEAD + 'Patient: X (fictional)\nDOS: 10/14/2026\n\n' * (n // 4),
    }

    def test_the_changed_readers_are_linear(self):
        for name, make in self.SHAPES.items():
            timings = []
            for n in (4000, 8000, 16000):
                text = make(n)
                context._context.cache_clear()
                started = time.perf_counter()
                context.extract_context(text)
                timings.append(time.perf_counter() - started)
            with self.subTest(shape=name, timings=[round(t, 3) for t in timings]):
                self.assertLess(timings[-1], 5)
                self.assertLess(timings[-1], max(timings[0], 0.02) * 10)


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

    def test_sk3_an_empty_date_field_holds_the_member_s_date(self):
        for text in EmptyDateFieldTests.CASES[:2]:
            with self.subTest(line=text.splitlines()[2]):
                encounter_id = self.finished(text, service_date=ELENA_DATE)
                self.assert_held(encounter_id)
                self.assert_not_excluded(encounter_id, '45385')
        # created without a member date (dateless), then the member's 1998-01-01: never sent, never excluded against
        encounter_id = self.finished(EmptyDateFieldTests.CASES[0])
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assert_never_sent(encounter_id, ELENA_DATE)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assert_not_excluded(encounter_id, '45385')

    def test_sk4_a_birth_label_form_or_a_word_before_the_date(self):
        encounter_id = self.finished(HEAD + 'Colonoscopy report - 10/14/2026\nPatient: Alex Synthetic DOS: DOB/Age '
                                     '01/01/1998 MRN 0000\n' + COLO_BODY, service_date=ELENA_DATE)
        self.assert_held(encounter_id)
        self.assert_not_excluded(encounter_id, '45385')
        encounter_id = self.finished(HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nVisit Date: TBD DOB (age) '
                                     '01/01/1998\n' + COLO_BODY)
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assert_never_sent(encounter_id, ELENA_DATE)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assert_not_excluded(encounter_id, '45385')

    def test_sk2_a_qualifier_after_a_date_of_birth(self):
        for text, _ in BirthFieldValueTests.CASES:
            with self.subTest(lines=' / '.join(text.splitlines()[2:4])[:90]):
                self.assert_dateless(text, '43239' if EGD_BODY in text else '45385')

    def test_sk5_a_heading_outside_the_vocabulary(self):
        self.assert_dateless(HEAD + 'Cancelled colonoscopy\nProcedure date: 11/04/2026\n\n' + COLO_BODY, '45385')
        self.assert_dateless(HEAD + 'Colonoscopy report\nRecall procedure\nProcedure date: 11/04/2026\n\n' + COLO_BODY,
                             '45385')

    def test_sk6_a_qualifier_in_a_header_value(self):
        for line in ('Patient status: pending authorization', 'Setting: cancelled',
                     'Provider: Dr. A. Synthetic (procedure postponed)'):
            with self.subTest(line=line):
                self.assert_dateless(HEAD + 'EGD report\nProcedure date: 11/04/2026\n' + line + '\n\n' + EGD_BODY,
                                     '43239')

    def test_sk7_another_discipline_s_undated_title(self):
        self.assert_dateless(HEAD + 'Cardiology consultation\nDate of service: 10/09/2026\n\n' + COLO_BODY, '45385')

    def test_control_a_header_block_s_date_is_sent(self):
        encounter_id = self.finished(HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998    MRN: '
                                     '0000\nDate of service: 10/14/2026\nEndoscopist: Dr. A. Synthetic\n\n' + COLO_BODY)
        self.assertEqual(self.dates_sent(encounter_id), [['Date of service: 2026-10-14']])
        self.assertNotEqual(self.bucket(encounter_id, '45385'), 'excluded')
