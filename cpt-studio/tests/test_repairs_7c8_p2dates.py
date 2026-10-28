"""Repair round 7c8, refutation phase 2, cluster P2DATES (studio/gi/context.py): the service date sent to Corti.

Refutation phase 2 attacked the integrated head 2fc8cde3d and every finding below was reproduced by an independent
verifier (dates:0-8, interplay:0, ctxcost:0-1). Four rounds of qualifier words and reaches had each been refuted by the
next paraphrase, so the rule is now one of SOURCE, never of vocabulary (P2FIX.md, "Rule direction"):

1. a document date reaches the request only from a date-of-service label's own value, when that value is a date alone
   (a clock may follow it) and the label's block holds nothing but the document's title, header fields of a closed
   list (patient, name, record or account number, date of birth, age, sex, physician, location or facility,
   referring; their values are read for a word of another occurrence) and date labels that agree. The block is the
   label's paragraph read up to the title, so a line above it - or a heading two paragraphs up - holds it too. Anything
   else in the block makes the date a question (a dateless request, a question for the member);
2. a dated title, a "Date:" or "Date/Time:" line, a dated line naming the service and a letter's subject line are
   evidence only - they can question a labelled date or stand as the only dated text, and the date is then asked, as
   on the installed revision 057a7d398;
3. a date of birth (DOB, D.O.B., date of birth, birth date, born, b. - before it, in any bracket, or heading its
   column or the line above it) is no candidate's value and is never read from the evidence;
4. a member date is taken only when it is a date some candidate states as its own value; otherwise it is a member
   conflict - held, nothing sent.

An over-hold (the date asked although a coder would know it) is a known limit; a wrong date sent is not. Synthetic text
only; no network (the suite's FakeProvider, answering only the selections whose quote the request's text holds).
"""
import time

from django.conf import settings
from django.test import SimpleTestCase

from studio import bounded, jobs
from studio.gi import context
from studio.types import Span
from tests.test_repairs_7c8_context import DateAssertions
from tests.test_repairs_7c8_context3 import (COLO_BODY, COLO_PLAIN, EGD_BODY, ELENA_DATE, HEAD, OFFICE_BODY, EndToEnd,
                                             date_fact, evidence_text)

BIRTH = '01/01/1998'
HEADER = ('Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998    MRN: 0000\nDate of service: 10/14/2026\n'
          'Endoscopist: Dr. A. Synthetic\nFacility: Synthetic Endoscopy Center\n\n')


class BirthDateIsNeverAServiceDateTests(DateAssertions, SimpleTestCase):
    """dates:0, dates:2 and interplay:0 (rules 3 and 4): an empty date-of-service field before a date of birth made the
    date of birth the label's value (round 2's unread value field); a dated line naming the service took the first date
    after the service's name as its own, a date of birth when one stood there (round 3's gap rule). Either way a
    member's 1998-01-01 agreed with the evidence, was taken and sent, and the act done on 10/14 was excluded against
    it - while the member's correct 10/14 was held."""

    EMPTY_FIELD = (  # dates:0: an empty or non-date date-of-service field before a date of birth
        HEAD + 'Colonoscopy report - 10/14/2026\nPatient: Alex Synthetic DOS: DOB: 01/01/1998 MRN: 0000\n' + COLO_BODY,
        HEAD + 'Colonoscopy report - 10/14/2026\nDate of Service: Date of Birth: 01/01/1998\n' + COLO_BODY,
        HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nVisit Date: DOB: 01/01/1998\n' + COLO_BODY,
        HEAD + 'Date: 10/14/2026\nDOS: N/A D.O.B. 01/01/1998\n' + COLO_BODY,
        HEAD + 'Colonoscopy report - 10/14/2026\nProcedure date: TBD Birth date: 01/01/1998\n' + COLO_BODY,
        HEAD + 'Colonoscopy report - 10/14/2026\nDOS: pending (born 01/01/1998)\n' + COLO_BODY,
    )
    SERVICE_LINES = (  # dates:2 and interplay:0: a date of birth between the service's name and the line's own date
        HEAD + 'Procedure: EGD  Patient: Alex Synthetic  DOB: 01/01/1998  Date: 10/14/2026\n' + EGD_BODY,
        HEAD + 'EGD DOB 01/01/1998 10/14/2026\n' + EGD_BODY,
        HEAD + 'Date: 10/27/2026\nRe: Colonoscopy for Alex Synthetic (DOB 01/01/1998) on 10/14/2026\nDear Dr. Synthetic,\n'
        + COLO_BODY,
        HEAD + 'Date of service: 10/14/2026\nRe: Colonoscopy - Synthetic, Alex (DOB 01/01/1998) - 10/14/2026\n' + COLO_BODY,
        HEAD + 'Colonoscopy - Synthetic, Alex (DOB 01/01/1998) - 10/14/2026\n' + COLO_BODY,
        HEAD + 'Colonoscopy report\nColonoscopy DOB 01/01/1998 10/14/2026\n' + COLO_BODY,
    )

    def assert_no_birth_date(self, text):
        self.assertNotEqual((date_fact(text).origin, date_fact(text).value), ('document', ELENA_DATE))
        self.assert_member_conflict(text, ELENA_DATE)
        self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))

    def test_an_empty_date_of_service_field_never_takes_the_date_of_birth(self):
        for text in self.EMPTY_FIELD:
            with self.subTest(line=text.splitlines()[2][:60]):
                self.assert_no_birth_date(text)
                self.assert_member_date(text, '2026-10-14')  # the date the note states still answers the question

    def test_a_service_line_s_own_date_is_its_only_date_that_is_no_date_of_birth(self):
        for text in self.SERVICE_LINES:
            with self.subTest(line=text.splitlines()[1][:60] + ' / ' + text.splitlines()[2][:40]):
                self.assert_no_birth_date(text)
                self.assert_member_date(text, '2026-10-14')

    def test_a_date_of_birth_heading_its_column_is_no_value(self):
        # "any row": the cell under a birth label is a date of birth too, so the service line is no candidate of it
        text = HEAD + 'Date of service: 10/14/2026\nProcedure | DOB\nColonoscopy | 01/01/1998\n' + COLO_BODY
        self.assert_no_birth_date(text)
        text = HEAD + 'Colonoscopy report - 10/14/2026\nDate of birth:\n01/01/1998\n' + COLO_BODY
        self.assert_no_birth_date(text)

    def test_a_line_with_two_dates_states_none(self):
        # interplay:0's referral variant: the line's own date cannot be told from another field's, so neither agrees
        text = HEAD + 'Re: EGD referral 09/01/2026 10/14/2026\n' + EGD_BODY
        self.assert_member_conflict(text, '2026-09-01')
        self.assert_member_conflict(text, ELENA_DATE)

    def test_controls(self):
        # the line's own date after its name, a date of birth after it, still answers; a date of birth alone keeps nothing
        text = HEAD + 'Colonoscopy 10/14/2026 DOB 01/01/1998\n' + COLO_PLAIN
        self.assert_asked(text, 'Colonoscopy 10/14/2026')
        self.assert_member_date(text, '2026-10-14')
        self.assert_member_conflict(text, ELENA_DATE)
        text = HEAD + 'Colonoscopy DOB: 01/01/1998\n' + COLO_PLAIN
        self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
        self.assertEqual(context._date_readings(date_fact(HEAD + 'Date: 01/01/1998\n\n' + COLO_PLAIN).evidence),
                         {'1998-01-01'})  # a date with no birth label is read as any other date

    def test_the_evidence_never_reads_a_date_of_birth(self):
        # whatever span holds one (a stored context, a span another reader kept): only the dates after no birth label
        for quoted in ('Re: Colonoscopy - Synthetic, Alex (DOB 01/01/1998) - 10/14/2026', 'D.O.B. 01/01/1998 10/14/2026',
                       'Date of birth: 01/01/1998; colonoscopy 10/14/2026', 'born on 01/01/1998, seen 10/14/2026'):
            with self.subTest(quoted=quoted):
                self.assertEqual(context._date_readings((Span(0, len(quoted), quoted),)), {'2026-10-14'})


class EvidenceDatesAreNeverSentTests(DateAssertions, SimpleTestCase):
    """dates:1, dates:3 and dates:5 (rule 2): round 3 read a clocked "Date/Time:" or "Date:" line, a letter's bare
    "Date:" over the encounter line it names, and a dated consultation title of another discipline as the note's own
    date (the installed revision sent no date for any of them). The date was sent and the snare polypectomy done on
    10/14 excluded against it. Each is now evidence: the date is asked."""

    CLOCKED = tuple(HEAD + top + '\nDear Dr. Synthetic,\nYour patient underwent colonoscopy on 10/14/2026 at our unit.\n'
                    + COLO_BODY for top in ('Date: 10/27/2026 2:30 PM', 'Date/Time: 10/27/2026 14:30',
                                            'Date & Time: 10/27/2026 14:30', 'Date and time: October 27, 2026 9:05 AM',
                                            'Date / Time: 2026-10-27 14:30', 'Date: 10/27/2026'))
    FAX = (HEAD + 'FAX COVER SHEET\nDate/Time: 10/27/2026 14:30\nTo: Dr. Synthetic\nFrom: Synthetic GI\nPages: 4\n\n'
           'Colonoscopy Report\nThe procedure was performed on 10/14/2026 in the endoscopy unit.\n' + COLO_BODY)
    LETTERS = tuple(HEAD + 'Date: 10/27/2026\n' + line + '\nDear Dr. Synthetic,\n' + COLO_BODY for line in (
        'Procedure: Colonoscopy on 10/14/2026 at Synthetic Endoscopy Center', 'Procedure: Colonoscopy (10/14/2026)',
        'Re: Colonoscopy on 10/14/2026 (report attached)', 'Colonoscopy on 10/14/2026, by Dr. A. Synthetic'))
    TITLES = tuple(HEAD + title + '\nReason: pre-procedure clearance for colonoscopy.\n\n' + COLO_BODY for title in (
        'Cardiology consultation: 10/09/2026', 'Surgical consultation - 10/09/2026', 'Oncology visit - 10/09/2026',
        'GI consultation: 10/09/2026', 'PCP note - 10/09/2026'))

    def test_a_letter_s_or_a_fax_s_date_is_never_documented(self):
        for text in self.CLOCKED + (self.FAX,) + self.LETTERS:
            with self.subTest(top=text.splitlines()[1][:50] + ' / ' + text.splitlines()[2][:50]):
                self.assert_never(text, '2026-10-27')
                self.assertEqual(date_fact(text).origin, 'missing')
                self.assert_member_conflict(text, ELENA_DATE)

    def test_the_encounter_line_s_date_answers_the_question(self):
        # a line naming the encounter and ending with its date is evidence the member's answer agrees with
        text = HEAD + 'Date: 10/27/2026\nProcedure: Colonoscopy on 10/14/2026\nDear Dr. Synthetic,\n' + COLO_BODY
        self.assert_member_date(text, '2026-10-14')
        # a date in the middle of a line is prose, never evidence: the member's answer with it is held (an over-hold,
        # a known limit - the member amends the document or clears the value), never agreed and sent
        for text in self.LETTERS[:1] + self.CLOCKED[:1]:
            with self.subTest(line=text.splitlines()[2][:50]):
                self.assert_member_conflict(text, '2026-10-14')

    def test_a_dated_title_is_evidence_never_the_date(self):
        for text in self.TITLES:
            with self.subTest(title=text.splitlines()[1]):
                self.assert_never(text, '2026-10-09')
                self.assert_asked(text, text.splitlines()[1])
                self.assert_member_date(text, '2026-10-09')  # the member's choice of the title's date is the member's

    def test_controls_a_title_beside_the_header_s_date(self):
        text = HEAD + 'Colonoscopy report - 10/14/2026\nPatient: Synthetic, Alex\nDate of service: 10/14/2026\n\n' + COLO_BODY
        self.assert_document(text, '2026-10-14')
        text = HEAD + 'GI visit - 10/20/2026\nPatient: Synthetic, Alex\nDate of service: 10/14/2026\n\n' + COLO_BODY
        self.assert_conflict(text, '2026-10-20', '2026-10-14')


class HeaderBlockTests(DateAssertions, SimpleTestCase):
    """dates:4, dates:6, dates:7 and dates:8 (rule 1): a qualifier more than 80 characters before a label on a
    flattened row, a heading above a block or a bulleted list, a field or sentence after the date, and qualifier words
    outside the reader's vocabulary (pending, cancelled, recall) left another occurrence's labelled date documented; it
    was sent and the act done on 10/14 was excluded against it. Only a header block that holds nothing else gives the
    date now; anything else in the block asks it, whatever its words."""

    OTHER = (
        # dates:4: a long flattened row
        ('EGD report\nPlanned procedure: colonoscopy with possible cold snare polypectomy under monitored anesthesia '
         'care Procedure Date: 11/04/2026', '2026-11-04'),
        ('Colonoscopy report\nPrior colonoscopy: colonoscopy with cold snare polypectomy of two tubular adenomas in the '
         'sigmoid colon, good preparation, no complications Procedure Date: 05/01/2019', '2019-05-01'),
        # dates:6: a block or a list under a heading
        ('Colonoscopy report\nOutside colonoscopy:\nFacility: Synthetic Regional Hospital\nProcedure date: 09/03/2026\n'
         'Findings: two adenomas.', '2026-09-03'),
        ('Colonoscopy report\nOutside colonoscopy:\n- Procedure date: 09/03/2026\n- Findings: two adenomas.', '2026-09-03'),
        ('Colonoscopy report\nLast colonoscopy:\n1. Procedure date: 05/01/2019\n2. Findings: normal.', '2019-05-01'),
        ('Colonoscopy report\nOutside colonoscopy:\n\nPatient: Synthetic, Alex\n\nProcedure date: 09/03/2026', '2026-09-03'),
        # dates:7: a field, a clause or a sentence after the date
        ('EGD report\nProcedure date: 11/04/2026\nStatus: Scheduled', '2026-11-04'),
        ('Colonoscopy report\nProcedure date: 09/03/2026\nFacility: Outside hospital', '2026-09-03'),
        ('Colonoscopy report\nProcedure date: 09/03/2026; outside colonoscopy.', '2026-09-03'),
        ('Colonoscopy report\nProcedure date: 09/03/2026. Outside colonoscopy.', '2026-09-03'),
        # dates:8: words the reader never listed
        ('GI office visit\nProcedure date: 11/04/2026 (pending authorization)', '2026-11-04'),
        ('EGD report\nProcedure date: 11/04/2026 (cancelled)', '2026-11-04'),
        ('Colonoscopy report\nRecall:\nProcedure date: 11/04/2026', '2026-11-04'),
        ('Colonoscopy report\nCancelled procedure:\nProcedure date: 11/04/2026', '2026-11-04'),
        ('Colonoscopy report\nColonoscopy status: cancelled Procedure Date: 11/04/2026', '2026-11-04'),
        ('Colonoscopy report\nProcedure date: 11/04/2026 - postponed', '2026-11-04'),
    )

    def test_another_occurrence_s_labelled_date_is_asked_never_documented(self):
        for lines, other in self.OTHER:
            for after in ('\n', '\n\n'):
                with self.subTest(lines=lines.replace('\n', ' / ')[:70], after=len(after)):
                    text = HEAD + lines + after + COLO_BODY
                    self.assert_never(text, other)
                    self.assert_asked(text, 'rocedure ' if 'rocedure' in lines.lower() else '')
                    self.assert_member_date(text, other)  # the member may still choose the date the label states

    def test_a_header_block_states_the_date(self):
        for header in (HEADER,
                       'Riverside Endoscopy Unit (fictional)\nColonoscopy procedure report\n\nPatient: Alex Synthetic '
                       '(fictional)\n\nSynthetic record: SYN-0003\n\nDate of procedure: 2026-10-14\n\nPlace of service: '
                       'Hospital outpatient department\n\nBilling: professional services only.\n\n',
                       'Procedure report - colonoscopy\n\nPatient: Alex Synthetic\nSynthetic record: SYN-0004\nDate of '
                       'procedure: 2026-10-14\nPlace of service: Ambulatory surgery center\nEndoscopist: Dr. A. '
                       'Synthetic, MD\nReferring clinician: Dr. B. Synthetic\n\n',
                       'Name: Alex Synthetic | MRN: 0000 | DOS: 10/14/2026 09:15 | Age: 28 | Sex: F\n\n'):
            with self.subTest(header=header.replace('\n', ' / ')[:70]):
                text = HEAD + header + COLO_BODY
                self.assert_document(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)

    def test_anything_else_in_the_block_asks_the_date(self):
        # an over-hold (a known limit): the reader no longer decides what a field, a heading or a sentence means
        for block in ('Date of service: 10/14/2026\n', 'Date of service: 10/14/2026\nIndication: screening.\n',
                      'Date of service: 10/14/2026\n(Recorded by Dr. A. Synthetic)\n',
                      'Colonoscopy procedure date: 10/14/2026\n\n', 'Date of service: 10/14/2026 at the clinic\n\n',
                      'Visit type: established patient\nDate of service: 10/14/2026\n\n',
                      'Field | Value\nProcedure date | 10/14/2026\n\n',
                      'Location: Outside hospital\nDate of service: 10/14/2026\n\n'):
            with self.subTest(block=block.replace('\n', ' / ')):
                text = HEAD + block + COLO_BODY
                self.assert_asked(text, 'ate')
                self.assert_member_date(text, '2026-10-14')

    def test_an_addendum_opens_a_header_of_its_own(self):
        # the app's "ADDENDUM (revision N, added ...)" line stands as the addendum's title: an addendum stating the date
        # alone states it (the member-conflict note's remedy), one holding anything else asks it, as at the top
        undated = HEAD + 'Colonoscopy report\n' + COLO_BODY
        stamp = '\n\nADDENDUM (revision 2, added 2026-10-28 02:42 UTC)\n'
        self.assert_document(undated + stamp + 'Date of service: 10/14/2026\n', '2026-10-14')
        self.assert_asked(undated + stamp + 'Procedure date: 11/04/2026\nStatus: scheduled\n', 'Procedure date')
        self.assert_asked(undated + stamp + 'The procedure was postponed.\nProcedure date: 11/04/2026\n', 'Procedure date')
        self.assert_conflict(HEAD + HEADER + COLO_BODY + stamp + 'Date of service: 10/15/2026\n', '2026-10-14',
                             '2026-10-15')

    def test_a_title_may_carry_a_number_that_is_no_date(self):
        for title in ('Colonoscopy report (fictional) M1', 'Endoscopy Suite 3', 'Page 1 of 2'):
            with self.subTest(title=title):
                self.assert_document(HEAD + title + '\nDate of service: 10/14/2026\n\n' + COLO_BODY, '2026-10-14')
        for title in ('Colonoscopy report 09/03/2026 copy', 'Colonoscopy 2019', 'Report of Oct 2026'):
            with self.subTest(title=title):
                self.assert_asked(HEAD + title + '\nDate of service: 10/14/2026\n\n' + COLO_BODY, 'Date of service')

    def test_date_labels_in_the_header_must_agree(self):
        self.assert_document(HEAD + 'Date of service: 10/14/2026\nProcedure date: 10/14/2026\n\n' + COLO_BODY,
                             '2026-10-14')
        self.assert_asked(HEAD + 'Date of service: 10/14/2026\nProcedure date: 10/15/2026\n\n' + COLO_BODY, 'ate')
        self.assert_asked(HEAD + 'Date of service: 10/14/2026\nDOS: 10-14-26\n\n' + COLO_BODY, 'ate')


class RequestTests(EndToEnd):
    """Every finding end to end: the date each provider request carries, and the dated check that excluded an act."""

    BIOPSY = EndToEnd.BIOPSY
    SNARE = EndToEnd.SNARE

    def assert_dateless(self, text, code):
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assertNotEqual(self.bucket(encounter_id, code), 'excluded')
        return encounter_id

    def test_dates_0_an_empty_date_of_service_field_before_a_date_of_birth(self):
        for text in BirthDateIsNeverAServiceDateTests.EMPTY_FIELD[:3]:
            with self.subTest(line=text.splitlines()[2][:50]):
                encounter_id = self.finished(text, service_date=ELENA_DATE)
                self.assert_held(encounter_id)
                self.assert_not_excluded(encounter_id, '45385')

    def test_dates_2_a_date_of_birth_in_a_dated_service_line(self):
        d1 = BirthDateIsNeverAServiceDateTests.SERVICE_LINES[0]
        encounter_id = self.finished(d1, service_date=ELENA_DATE)
        self.assert_held(encounter_id)
        self.assert_not_excluded(encounter_id, '43239')
        encounter_id = self.assert_dateless(d1, '43239')  # D2: the member's 10/14 answers, 1998 never sent
        self.set_context(encounter_id, {'service_date': '2026-10-14'})
        self.assertEqual(self.dates_sent(encounter_id), [[], ['Date of service: 2026-10-14']])
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assert_never_sent(encounter_id, ELENA_DATE)
        self.assert_not_excluded(encounter_id, '43239')

    def test_interplay_0_a_member_s_date_of_birth_beside_the_subject_line(self):
        encounter_id = self.finished(BirthDateIsNeverAServiceDateTests.SERVICE_LINES[3], service_date=ELENA_DATE)
        self.assert_held(encounter_id)
        self.assert_not_excluded(encounter_id, '45385')

    def test_dates_1_a_fax_s_or_a_letter_s_clocked_date(self):
        for text in (EvidenceDatesAreNeverSentTests.FAX, EvidenceDatesAreNeverSentTests.CLOCKED[0]):
            with self.subTest(top=text.splitlines()[1][:30]):
                self.assert_dateless(text, '45385')

    def test_dates_3_a_letter_s_date_over_the_encounter_line(self):
        for text in EvidenceDatesAreNeverSentTests.LETTERS:
            with self.subTest(line=text.splitlines()[2][:50]):
                self.assert_dateless(text, '45385')
        # the member's answer agrees with a line naming the encounter that ends with its date, and is sent
        encounter_id = self.assert_dateless(HEAD + 'Date: 10/27/2026\nProcedure: Colonoscopy on 10/14/2026\n'
                                            'Dear Dr. Synthetic,\n' + COLO_BODY, '45385')
        self.set_context(encounter_id, {'service_date': '2026-10-14'})
        self.assertEqual(self.dates_sent(encounter_id), [[], ['Date of service: 2026-10-14']])
        self.assertNotEqual(self.bucket(encounter_id, '45385'), 'excluded')

    def test_dates_5_another_discipline_s_dated_title(self):
        self.assert_dateless(EvidenceDatesAreNeverSentTests.TITLES[0], '45385')

    def test_dates_4_6_7_8_another_occurrence_s_labelled_date(self):
        for index in (0, 2, 3, 6, 7, 8, 11, 12):
            lines, _ = HeaderBlockTests.OTHER[index]
            body, code = (EGD_BODY, '43239') if lines.startswith('EGD') else (COLO_BODY, '45385')
            with self.subTest(lines=lines.replace('\n', ' / ')[:60]):
                self.assert_dateless(HEAD + lines + '\n' + body, code)

    def test_dates_8_an_office_visit_beside_a_pending_procedure_s_date(self):
        encounter_id = self.finished(HEAD + 'GI office visit\nProcedure date: 11/04/2026 (pending authorization)\n'
                                     + OFFICE_BODY)
        self.assertEqual(self.dates_sent(encounter_id), [[]])

    def test_control_a_header_block_s_date_is_sent(self):
        encounter_id = self.finished(HEAD + HEADER + COLO_BODY)
        self.assertEqual(self.dates_sent(encounter_id), [['Date of service: 2026-10-14']])
        self.assertNotEqual(self.bucket(encounter_id, '45385'), 'excluded')


class ReadingCostTests(SimpleTestCase):
    """ctxcost:0 and ctxcost:1 (class 2), and the cost of every pattern this cluster changed."""

    def test_ctxcost_0_the_place_of_service_pattern_is_linear(self):
        # 'POS', a long run of spaces and no code: every split of the run was tried (16,000 spaces: 3.3 s)
        timings = []
        for n in (4000, 8000, 16000):
            text = 'POS' + ' ' * n + 'x'
            started = time.perf_counter()
            self.assertIsNone(context.POS.search(text))
            timings.append(time.perf_counter() - started)
        self.assertLess(timings[-1], 0.05, timings)
        text = HEAD + 'Date of service: 10/14/2026\nOffice visit.\nPOS' + ' ' * 96000 + 'x\n' + OFFICE_BODY
        started = time.perf_counter()
        out = bounded.run_bounded(jobs._analyze_child, text, {}, settings.MAX_SERVICE_MENTIONS,
                                  seconds=settings.JOB_DEADLINE_SECONDS['analyze'],
                                  memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertLess(time.perf_counter() - started, 20)
        self.assertNotIsInstance(out, int)
        started = time.perf_counter()
        bounded.run_bounded(context.extract_context, text[:48300], seconds=settings.CONTEXT_REQUEST_SECONDS,
                            memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertLess(time.perf_counter() - started, 5)

    def test_ctxcost_1_a_repeated_setting_phrase_is_read_within_the_member_s_bound(self):
        # 'HOPD ' 70,000 times: 0.45 ms per phrase in is_current_statement, 30 s; a member's POST /context was refused
        text = HEAD + 'Date of service: 10/14/2026\nOffice visit. HOPD ' + 'HOPD ' * 70000 + '\n' + OFFICE_BODY
        started = time.perf_counter()
        facts = bounded.run_bounded(context.extract_context, text, seconds=settings.CONTEXT_REQUEST_SECONDS,
                                    memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertLess(time.perf_counter() - started, 5)
        setting = facts['setting']
        self.assertEqual((setting.origin, setting.value, setting.evidence), ('missing', None, ()))
        self.assertIn('setting is asked', setting.note)
        merged = context.merge_user_values(facts, {'setting': 'office'})['setting']
        self.assertEqual((merged.origin, merged.value), ('user', 'office'))  # the member supplies it

    def test_controls_a_note_s_few_setting_statements_are_read_as_before(self):
        text = HEAD + 'Date of service: 10/14/2026\n\nOffice visit. Seen in the clinic. ' + 'Office visit. ' * 150 + '\n'
        self.assertEqual(context.extract_context(text)['setting'].value, 'office')
        text = HEAD + 'Office visit. HOPD.\n'
        self.assertEqual(context.extract_context(text)['setting'].origin, 'conflict')

    def test_the_changed_readers_are_linear(self):
        # every shape this cluster's patterns and scans read, at 4,000 / 8,000 / 16,000 units: the time doubles at most
        # about twice (noise), never squares; the largest is read far inside the member's 15 s
        shapes = {
            'header lines': lambda n: HEAD + 'Patient: Synthetic, Alex    DOB: 01/01/1998\n' * n + 'DOS: 10/14/2026\n\n',
            'one header line': lambda n: HEAD + 'DOS: 10/14/2026 ' + 'MRN: 0000 ' * n + '\n\n',
            'labels in one paragraph': lambda n: HEAD + 'Date of service: 10/14/2026\n' * n,
            'blank-separated labels': lambda n: HEAD + 'Date of service: 10/14/2026\n\n' * n,
            'birth table': lambda n: HEAD + 'DOB | ' * n + '\n' + '01/01/1998 | ' * n + '\n',
            'birth labels': lambda n: HEAD + 'DOB: 01/01/1998 ' * n + '\n',
            'empty fields': lambda n: HEAD + 'DOS: DOB: 01/01/1998 ' * n + '\n',
            'service lines': lambda n: HEAD + ('Colonoscopy DOB 01/01/1998 10/14/2026\n' * 12) + 'x ' * n + '\n',
            'title lines': lambda n: HEAD + ('Colonoscopy report ' + 'a ' * n + '\n') * 12,
        }
        for name, make in shapes.items():
            timings = []
            for n in (4000, 8000, 16000):
                text = make(n)
                context._context.cache_clear()
                started = time.perf_counter()
                context.extract_context(text)
                timings.append(time.perf_counter() - started)
            with self.subTest(shape=name, timings=[round(t, 3) for t in timings]):
                self.assertLess(timings[-1], 3)
                self.assertLess(timings[-1], max(timings[0], 0.02) * 8)
