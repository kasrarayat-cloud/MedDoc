"""Repair round 7c8, cluster CONTEXT round 2 (studio/gi/context.py): the service date sent to Corti.

Owner decision 2026-10-27 (narrow, install-first), must-fix classes 1 (a wrong or conflicting service date in a provider
request), 2 (stage time) and 4 (a code excluded on a dated check without a reviewer's decision). Round 1 (45d798122)
picked the date with qualifier and title vocabularies; its skeptic demonstrated eight issues, c2:1 .. c2:8 below. The
rule of round 2 is that the reader may be unsure, but it is never silently wrong:

A. every date candidate outside a plan or history section - a labelled date of any reading, a dated title, "Date:" or
   "Re:" line near the top of any reading - is the note's own date or is kept as documented evidence; with no usable own
   date the date is a question, and a member value must agree with that evidence;
B. a title or "Date:" line gives the date only when every labelled candidate agrees with it, and the note's own labelled
   date and its own dated title near the top, when they differ, are a conflict;
C. a label's own words are the label's: a preceding field's value is not, and a clock time is no field label;
D. every changed pattern is linear.

An over-hold (the date asked although a coder would know it) is a known limit; a wrong or member-supplied date where the
document states another is not. A date asked is released when the member answers with a date the evidence reads.
Synthetic text only; no network (the suite's FakeProvider).
"""
import json
import time
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from studio import bounded, jobs, models
from studio.gi import context
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
OFFICE_BODY = OFFICE_NOTE.split('\n', 1)[1].replace('Date of service: 2026-10-20\n', '')
VISIT_BODY = ('Established patient office visit for chronic constipation.\n'
              'Total time on the date of the encounter was 24 minutes.\n')
EGD_BODY = ('PROCEDURE NOTE: EGD\nTechnique: The upper endoscope was advanced to the second portion of the duodenum.\n'
            'Findings: On 10/14/2026 biopsies were taken from the antrum.\n')
COLO_BODY = ('PROCEDURE NOTE: Colonoscopy\nTechnique: The colonoscope was advanced to the cecum.\n'
             'Findings: On 10/14/2026 a 5 mm sigmoid polyp was removed with a cold snare.\n')
COLO_PLAIN = ('PROCEDURE NOTE: Colonoscopy\nTechnique: The colonoscope was advanced to the cecum.\n'
              'Findings: A 5 mm sigmoid polyp was removed with a cold snare.\n')
ELENA_DATE = '1998-01-01'  # a member-entered date far from any documented one (the Elena incident)


def date_fact(text):
    return context.extract_context(text)['service_date']


def merged_date(text, value):
    return context.merge_user_values(context.extract_context(text), {'service_date': value})['service_date']


class DateAssertions:
    def assert_document(self, text, value):
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value), ('document', value), [e.text for e in fact.evidence])

    def assert_never(self, text, *dates):
        fact = date_fact(text)
        self.assertFalse(fact.origin == 'document' and fact.value in dates, (fact.origin, fact.value))

    def assert_conflict(self, text, *values):
        """A conflict inside the document: asked, each value listed, and a member settles it by choosing one."""
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value), ('conflict', None), [e.text for e in fact.evidence])
        self.assertEqual(set(context.documented_values(fact)), set(values), fact.note)
        for value in values:
            self.assert_member_date(text, value)
        self.assert_member_conflict(text, ELENA_DATE)

    def assert_asked(self, text, *evidence):
        """No usable date: asked, with the documented date text kept as evidence a member value must agree with."""
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value), ('missing', None), [e.text for e in fact.evidence])
        quoted = [' '.join(e.text.split()) for e in fact.evidence]
        for text_part in evidence:
            self.assertTrue(any(text_part in q for q in quoted), (text_part, quoted))
        self.assert_member_conflict(text, ELENA_DATE)

    def assert_member_conflict(self, text, value):
        fact = merged_date(text, value)
        self.assertEqual((fact.origin, fact.value), ('conflict', None), fact.note)
        self.assertTrue(context.is_member_conflict(fact), fact.note)

    def assert_member_date(self, text, value):
        fact = merged_date(text, value)
        self.assertEqual((fact.origin, fact.value), ('user', value), fact.note)


class PlannedDateIsNeverTheServiceDateTests(DateAssertions, SimpleTestCase):
    """c2:1 (negtime-15, a regression of 45d798122): a clock time ("scheduled for 8:00 AM") read as a field label, and a
    qualifier heading a field of its own ("Planned procedure: EGD", "Scheduled: Yes") passed over, made a planned
    procedure's labelled date the documented service date; it was sent, and 43239 was excluded as historical against
    it. A clock time is no field label; a qualifier field naming an occurrence, or the qualifier alone, holds the date;
    and a labelled date that differs from the note's dated title is a conflict (rule B)."""

    def test_under_a_title_the_planned_date_is_a_conflict_with_the_title(self):
        cases = (
            (HEAD + 'EGD report - 10/14/2026\nIndication: dyspepsia.\nColonoscopy procedure date: 11/04/2026, '
                    'scheduled for 8:00 AM.\n' + EGD_BODY, '2026-10-14'),
            (HEAD + 'Colonoscopy report - 10/14/2026\nPlanned procedure: EGD    Procedure date: 11/04/2026\n'
             + COLO_BODY, '2026-10-14'),
            (HEAD + 'GI office visit - 10/20/2026\nPlanned procedure: Colonoscopy    Procedure date: 11/04/2026\n'
             + OFFICE_BODY, '2026-10-20'),
            (HEAD + 'GI office visit - 10/20/2026\nColonoscopy procedure date: 11/04/2026, scheduled for 8:00 AM.\n'
             + OFFICE_BODY, '2026-10-20'),
            (HEAD + 'EGD report - 10/14/2026\nColonoscopy procedure date: 11/04/2026, scheduled for 8 AM.\n' + EGD_BODY,
             '2026-10-14'),
        )
        for text, titled in cases:
            with self.subTest(text=text.splitlines()[2][:60]):
                self.assert_never(text, '2026-11-04')
                self.assert_conflict(text, titled, '2026-11-04')

    def test_alone_the_planned_date_is_asked(self):
        for line, planned in (('Scheduled: Yes    Procedure date: 11/04/2026', '2026-11-04'),
                              ('Next procedure: Colonoscopy    Procedure date: 10/14/2029', '2029-10-14'),
                              ('Procedure date: 11/04/2026    Scheduled: Yes', '2026-11-04'),
                              ('Procedure date: 10/14/2029    Next procedure: Colonoscopy', '2029-10-14'),
                              ('Scheduled for 8:00 AM    Procedure date: 11/04/2026', '2026-11-04')):
            with self.subTest(line=line):
                text = HEAD + line + '\n' + COLO_PLAIN
                self.assert_never(text, planned)
                self.assert_asked(text, 'Procedure date')

    def test_controls_a_field_about_something_else_is_passed_over(self):
        for line in ('Last name: Synthetic    First name: Alex    DOS: 10/14/2026',
                     'Procedure date: 10/14/2026    Next colonoscopy: 10/2029',
                     'Procedure date: 10/14/2026    Previous surgeries: appendectomy',
                     'Date of service: 10/14/2026 (capsule placement) Recording started at 9:00 AM'):
            with self.subTest(line=line):
                self.assert_document(HEAD + line + '\n' + COLO_PLAIN, '2026-10-14')

    def test_controls_a_clock_never_detaches_a_qualifier_from_its_date(self):
        # "at 8:00 AM (scheduled)" qualifies the planned date itself: another occurrence's, so beside the note's own
        # labelled date it is set aside - never held as a date this service cannot place (an over-hold)
        text = (HEAD + 'Date of service: 10/14/2026\nColonoscopy procedure date: 11/04/2026 at 8:00 AM (scheduled)\n'
                + COLO_PLAIN)
        self.assert_document(text, '2026-10-14')


class PrecedingFieldValueIsNotTheLabelsTests(DateAssertions, SimpleTestCase):
    """c2:2 (negtime-8, a regression of 45d798122): the label's words were taken up to four words back, so a preceding
    field's value on the same line ("Indication: Personal history of colon polyps Date of service: ...") made the note's
    own labelled date another occurrence's; it was dropped with no evidence and a member's 1998-01-01 or a letter's
    date was sent. A capitalised label after a lower-case word opens its own field (rule C)."""

    def test_the_labelled_date_of_service_is_read(self):
        for line in ('Indication: Personal history of colon polyps Date of service: 10/14/2026',
                     'Indication: Recent rectal bleeding Procedure date: 10/14/2026'):
            with self.subTest(line=line):
                text = HEAD + line + '\n' + COLO_PLAIN
                self.assert_document(text, '2026-10-14')
                self.assert_member_conflict(text, ELENA_DATE)
                self.assert_member_date(text, '2026-10-14')

    def test_beside_a_letter_date_it_is_a_conflict_never_the_letter_date(self):
        for letter in ('2026-10-27', '2026-10-16'):
            with self.subTest(letter=letter):
                y, m, d = letter.split('-')
                text = (HEAD + f'Date: {m}/{d}/{y}\nIndication: Personal history of colon polyps Date of service: '
                               '10/14/2026\n' + COLO_BODY)
                self.assert_never(text, letter)
                self.assert_conflict(text, '2026-10-14', letter)

    def test_a_sentence_s_history_words_never_let_a_member_date_replace_it(self):
        text = HEAD + 'Surveillance colonoscopy for history of adenomatous polyps, procedure date 10/14/2026.\n' + COLO_PLAIN
        self.assert_member_conflict(text, ELENA_DATE)
        self.assert_member_date(text, '2026-10-14')

    def test_controls_the_label_s_own_words_still_decide(self):
        for line in ('Prior DOS: 2025-01-02', 'prior DOS: 2025-01-02', 'Outside procedure date: 2019-05-01',
                     'Outside Procedure Date: 2019-05-01', 'Previous procedure date: 2019-05-01'):
            with self.subTest(line=line):
                text = HEAD + line + '\n' + VISIT_BODY
                self.assert_asked(text, line)


class VisitTitleIsTheNotesOwnTests(DateAssertions, SimpleTestCase):
    """c2:3 (negtime-14, a regression of 45d798122): a visit or consultation title naming a nurse practitioner or an
    imaging finding was read as another discipline's document; it gave no date and no evidence, so a member's
    1998-01-01 was sent with 99213 ready. A title naming a visit or consultation heads an encounter: it is the note's own
    heading; another discipline's document is a report or a note."""

    def test_the_title_s_date_is_documented(self):
        for title in ('Nurse practitioner visit - 10/20/2026', 'Anemia and abnormal CT consultation - 10/20/2026'):
            with self.subTest(title=title):
                text = HEAD + title + '\n' + OFFICE_BODY
                self.assert_document(text, '2026-10-20')
                self.assert_member_conflict(text, ELENA_DATE)
                self.assert_member_date(text, '2026-10-20')


class LinearCostTests(SimpleTestCase):
    """c2:4 (context-3, a cost regression of 45d798122, class 2): UNREAD_SERVICE_DATE backtracked over a whitespace run
    after a label, a newline and another run, quadratically: 32,226 characters overran the analyze stage's 60 s (and it
    ran in a member's POST /context too); the title reader backtracked the same way over a title's trailing run. The
    label's value is now found by a scan and every changed pattern is possessive: both stages' children read these
    shapes far inside the deadline (the doubling ratios are in the commit)."""

    PIN_SECONDS = 20  # the analyze stage has 60 s; the repaired code takes well under a second here

    SHAPES = {
        'label, spaces, newline, spaces': lambda n: (HEAD + 'Date of service:' + ' ' * n + '\n' + ' ' * n
                                                     + 'Provider: Dr. A. Synthetic\n' + VISIT_BODY),
        'label, spaces, no value': lambda n: HEAD + 'Date of service' + ' ' * n + 'x\n' + VISIT_BODY,
        'title, spaces, no date': lambda n: HEAD + 'GI visit' + ' ' * n + 'x\n' + VISIT_BODY,
        'title, spaces, newline, spaces': lambda n: (HEAD + 'Colonoscopy report' + ' ' * n + '\n' + ' ' * n + 'x\n'
                                                     + VISIT_BODY),
        'label ending its line, blank lines': lambda n: HEAD + 'Date of service:\n' + ' \n' * n + 'x\n' + VISIT_BODY,
        'labels on one line': lambda n: HEAD + 'DOS: ' * (n // 5) + '\n' + VISIT_BODY,
        'table header row': lambda n: HEAD + 'Date of Service | ' * (n // 18) + '\n' + '1 | ' * (n // 4) + '\n',
    }

    def test_the_analyze_child_reads_each_shape_in_time(self):
        for name, shape in self.SHAPES.items():
            with self.subTest(shape=name):
                text = shape(16000)
                started = time.perf_counter()
                bounded.run_bounded(jobs._analyze_child, text, {}, settings.MAX_SERVICE_MENTIONS,
                                    seconds=self.PIN_SECONDS, memory_bytes=settings.BOUNDED_MEMORY_BYTES)
                self.assertLess(time.perf_counter() - started, self.PIN_SECONDS)

    def test_a_member_s_context_child_reads_each_shape_in_time(self):
        for name, shape in self.SHAPES.items():
            with self.subTest(shape=name):
                text = shape(16000)
                started = time.perf_counter()
                bounded.run_bounded(context.extract_context, text, seconds=self.PIN_SECONDS,
                                    memory_bytes=settings.BOUNDED_MEMORY_BYTES)
                self.assertLess(time.perf_counter() - started, self.PIN_SECONDS)


class QualifierOfAnotherItemTests(DateAssertions, SimpleTestCase):
    """c2:5 (negtime-15, still reproducing): a qualifier of another item after the labelled date ("(recall due in 3
    years)", ", next colonoscopy in 3 years", "(follow-up)") set the date aside and the letter's or title's other date was
    sent. A set-aside labelled date that differs from the title or "Date:" line makes the date a conflict (rule B)."""

    def test_the_title_or_letter_date_is_never_taken(self):
        cases = (
            (HEAD + 'Date: 10/16/2026\nDate of service: 10/14/2026 (recall due in 3 years)\n' + COLO_PLAIN,
             '2026-10-16', '2026-10-14'),
            (HEAD + 'Colonoscopy report - 10/16/2026\nProcedure date: 10/14/2026, next colonoscopy in 3 years\n'
             + COLO_PLAIN, '2026-10-16', '2026-10-14'),
            (HEAD + 'Date: 10/27/2026\nRe: GI office visit\nDate of visit: 10/20/2026 (follow-up)\n' + OFFICE_BODY,
             '2026-10-27', '2026-10-20'),
        )
        for text, other, labelled in cases:
            with self.subTest(text=text.splitlines()[2][:60]):
                self.assert_never(text, other)
                self.assert_conflict(text, other, labelled)

    def test_alone_the_labelled_date_is_asked_and_answered(self):
        text = HEAD + 'Date of service: 10/14/2026 (recall due in 3 years)\n' + COLO_PLAIN
        self.assert_asked(text, 'Date of service: 10/14/2026')
        self.assert_member_date(text, '2026-10-14')


class OutsideOrIndexDateTests(DateAssertions, SimpleTestCase):
    """c2:6 (negtime-8, still reproducing): under "Colonoscopy report - 10/14/2026" an outside or index procedure's
    labelled date - qualified after the date, by a heading above it, by a wrapped word, by its table row or more than 80
    characters back - was taken and sent. A labelled date that differs from the title is a conflict (rule B); a bracket
    opened right after the date by a history word ("(outside facility)", "(index EMR)") qualifies that date."""

    TITLED = HEAD + 'Colonoscopy report - 10/14/2026\n'

    def test_the_other_procedure_s_date_is_never_taken(self):
        cases = (
            ('Indication: Surveillance. Procedure date: 09/03/2026 (outside facility; cold snare polypectomy of two '
             'adenomas).', '2026-09-03'),
            ('Outside colonoscopy:\nProcedure date: 09/03/2026', '2026-09-03'),
            ('Procedure date: 04/02/2026 (index EMR of a 25 mm lesion).', '2026-04-02'),
            ('Outside\nprocedure date: 09/03/2026', '2026-09-03'),
            ('Procedure date | 2021-05-03 | Outside colonoscopy', '2021-05-03'),
            ('Outside colonoscopy at Synthetic Regional Medical Center with cold snare removal of two adenomas, '
             'procedure date: 09/03/2026', '2026-09-03'),
        )
        for line, other in cases:
            with self.subTest(line=line[:60]):
                text = self.TITLED + line + '\n' + COLO_PLAIN
                self.assert_never(text, other)
                self.assert_conflict(text, '2026-10-14', other)

    def test_alone_a_bracketed_history_word_holds_the_date(self):
        for line in ('Procedure date: 09/03/2026 (outside facility; cold snare polypectomy of two adenomas).',
                     'Procedure date: 04/02/2026 (index EMR of a 25 mm lesion).'):
            with self.subTest(line=line[:40]):
                self.assert_asked(HEAD + line + '\n' + COLO_PLAIN, 'Procedure date')

    def test_alone_a_wrapped_label_keeps_its_own_words(self):
        # a label opening its line in lower case continues the line above: "Outside" is its own word
        text = HEAD + 'Outside\nprocedure date: 09/03/2026\n' + COLO_PLAIN
        self.assert_never(text, '2026-09-03')
        self.assert_asked(text, 'Outside procedure date: 09/03/2026')
        self.assert_document(HEAD + 'Colonoscopy\nprocedure date: 10/14/2026\n' + COLO_PLAIN, '2026-10-14')


class AnotherDocumentOrLetterTests(DateAssertions, SimpleTestCase):
    """c2:7 (negtime-14, still reproducing): "Colonoscopy pathology report: 10/17/2026" gave 10/17 because a GI service
    name won over the pathology word, other report titles (path, cytopathology, biopsy, laboratory) were the note's
    heading, and a letter's "Date:" was taken beside "Re: GI follow-up consultation of 10/20/2026" or "Re: Consultation of
    10/20/2026". A service name speaks only for the words it covers; a report is the note's own heading only when it
    names a service this release codes; a "Re:" line is a candidate a letter's date must agree with."""

    def test_a_report_title_that_is_not_this_service_s_gives_no_date(self):
        for title in ('Colonoscopy pathology report: 10/17/2026', 'Surgical path report: 10/17/2026',
                      'Cytopathology report: 10/17/2026', 'Biopsy report: 10/17/2026',
                      'Laboratory report: 10/17/2026'):
            with self.subTest(title=title):
                text = HEAD + title + '\nSpecimen A: sigmoid polyp - tubular adenoma.\n\n' + COLO_PLAIN
                self.assert_never(text, '2026-10-17')
                self.assert_asked(text, title)

    def test_a_letter_date_beside_the_encounter_it_names_is_a_conflict(self):
        for re_line in ('Re: GI follow-up consultation of 10/20/2026', 'Re: Consultation of 10/20/2026'):
            with self.subTest(re_line=re_line):
                text = HEAD + 'Date: 10/27/2026\n' + re_line + '\nDear Dr. Synthetic,\n' + OFFICE_BODY
                self.assert_never(text, '2026-10-27')
                self.assert_conflict(text, '2026-10-27', '2026-10-20')

    def test_controls_this_service_s_titles(self):
        self.assert_document(HEAD + 'EGD report - 10/14/2026\nTechnique: advanced to the duodenum.\n', '2026-10-14')
        self.assert_document(HEAD + 'Endoscopic ultrasound report: 10/14/2026\nThe echoendoscope was passed.\n',
                             '2026-10-14')
        self.assert_document(HEAD + 'GI visit - 10/20/2026\n' + VISIT_BODY, '2026-10-20')
        self.assert_document(HEAD + 'Hepatology clinic note - 9/28/2026\n' + VISIT_BODY, '2026-09-28')
        self.assert_document(HEAD + 'Procedure (fictional)\nDate: 14-Oct-2026\nEGD with Savary dilation.\n',
                             '2026-10-14')


class UnreadDateFormsAreKeptTests(DateAssertions, SimpleTestCase):
    """c2:8 (context-3, still reproducing): a date-of-service label with a time ("Date/Time of Service", "Visit Date &
    Time"), a "Re:" line alone, a day-first title, "20-Oct-26", spaced slashes, a table header over its value row and a
    value two blank lines down kept no evidence, so a member's 1998-01-01 became the date and was sent. A date label may
    name the time too; a date-of-service label's value with a digit on its line, in its column of the next row, or on the
    next non-blank line, and every dated title near the top, are kept."""

    def test_a_member_date_never_replaces_the_documented_text(self):
        for header in ('Date/Time of Service: 10/20/2026 09:15', 'Re: GI consultation of 10/20/2026',
                       'GI office visit - 20/10/2026', 'Colonoscopy report - 14/10/2026', 'Date of service: 20-Oct-26',
                       'Date of service: 10 / 20 / 2026', 'Visit Date & Time: 10/20/2026 9:15 AM',
                       'Date of Service | Provider | Location\n10/20/2026 | Dr. A. Synthetic | Office',
                       'Date of service:\n\n\n10/20/2026'):
            with self.subTest(header=header[:40]):
                text = HEAD + header + '\n' + OFFICE_BODY
                fact = date_fact(text)
                self.assertTrue(fact.origin == 'document' or fact.evidence, fact)
                self.assert_member_conflict(text, ELENA_DATE)

    def test_a_member_date_the_text_reads_is_taken(self):
        for header in ('Date/Time of Service: 10/20/2026 09:15', 'Re: GI consultation of 10/20/2026',
                       'Visit Date & Time: 10/20/2026 9:15 AM',
                       'Date of Service | Provider | Location\n10/20/2026 | Dr. A. Synthetic | Office',
                       'Date of service:\n\n\n10/20/2026'):
            with self.subTest(header=header[:40]):
                self.assert_member_date(HEAD + header + '\n' + OFFICE_BODY, '2026-10-20')

    def test_controls_no_value_no_evidence(self):
        for header in ('Date of service: pending', 'The procedure date was moved twice by the patient.',
                       'Date of service:    Provider: Dr. A. Synthetic'):
            with self.subTest(header=header):
                text = HEAD + header + '\n' + VISIT_BODY
                self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
                self.assert_member_date(text, ELENA_DATE)


class DatedServiceLineTests(DateAssertions, SimpleTestCase):
    """c2:8's class, a variant (refutation round 2, rule A): a dated line near the top that names the service with no
    title word ("Colonoscopy - 10/14/2026", "EGD 10/14/2026") was no candidate at all, so a member's 1998-01-01 became
    the date and was sent. With no date of the note's own it is the evidence a member date must agree with; it never
    questions an own date, and a line qualified as another occurrence's or naming no service is not one."""

    def test_kept_as_the_evidence_of_the_date_asked(self):
        for line, body in (('Colonoscopy - 10/14/2026', COLO_PLAIN), ('EGD 10/14/2026', EGD_BODY.replace(
                'On 10/14/2026 b', 'B'))):
            with self.subTest(line=line):
                text = HEAD + line + '\n' + body
                self.assert_asked(text, line)
                self.assert_member_date(text, '2026-10-14')

    def test_a_field_naming_the_service_is_a_candidate_a_letter_date_must_agree_with(self):
        # "Re: Colonoscopy on 10/14/2026" names the encounter as "Re: GI consultation of ..." does: never the letter's
        # "Date:" silently, whatever its qualifier
        for re_line in ('Re: Colonoscopy on 10/14/2026', 'Regarding: your prior colonoscopy of 10/14/2026'):
            with self.subTest(re_line=re_line):
                text = HEAD + 'Date: 10/27/2026\n' + re_line + '\nDear Dr. Synthetic,\n' + COLO_PLAIN
                self.assert_never(text, '2026-10-27')
                self.assert_conflict(text, '2026-10-27', '2026-10-14')

    def test_controls(self):
        self.assert_document(HEAD + 'Colonoscopy - 09/03/2026\nDate of service: 10/14/2026\n' + COLO_PLAIN,
                             '2026-10-14')
        self.assert_document(HEAD + 'Colonoscopy: 05/01/2019\nDate of service: 10/14/2026\n' + COLO_PLAIN, '2026-10-14')
        # a field other than a letter's subject line is only evidence: it never questions the note's own date
        for line in ('Procedure: Colonoscopy x 2026-10-01', 'Indication: surveillance after colonoscopy 2023-05-02'):
            with self.subTest(line=line):
                self.assert_document(HEAD + 'Date of service: 10/14/2026\n' + line + '\n' + COLO_PLAIN, '2026-10-14')
        for line in ('Last colonoscopy 05/01/2019', 'Date of birth: 1961-07-02'):
            with self.subTest(line=line):
                text = HEAD + line + '\n' + VISIT_BODY
                self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
                self.assert_member_date(text, ELENA_DATE)


class AskedDateIsAnswerableTests(DateAssertions, SimpleTestCase):
    """A date asked is never stuck when the member answers with a date its evidence reads - also when the evidence
    reads more than one date (merge_user_values' agreement rule); any other member date is a member conflict."""

    def test_a_member_date_the_evidence_reads_settles_it(self):
        text = HEAD + 'GI follow-up visit - 10/20/2026\nLast visit date: 04/15/2026\n' + VISIT_BODY
        self.assert_asked(text, 'GI follow-up visit - 10/20/2026', 'Last visit date: 04/15/2026')
        self.assert_member_date(text, '2026-10-20')
        self.assert_member_conflict(text, '2026-10-21')

    def test_text_that_reads_no_date_beside_text_that_does_never_blocks_the_answer(self):
        # an unread label beside the title: asked (it may differ), and answered by the date the title reads
        text = HEAD + 'GI visit - 10/20/2026\nLast visit date: 04/15/26\n' + VISIT_BODY
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value), ('conflict', None), fact.note)
        self.assert_member_date(text, '2026-10-20')
        self.assert_member_conflict(text, ELENA_DATE)
        # text that reads no date at all can never be shown to agree: the document is amended or the value cleared
        alone = HEAD + 'Date of service: 20-Oct-26\n' + VISIT_BODY
        self.assert_member_conflict(alone, '2026-10-20')

    def test_a_qualifier_attached_to_the_date_is_never_passed_over_across_a_field_break(self):
        for line in ('Procedure date: 11/04/2026 planned    Endoscopist: Dr. A. Synthetic',
                     'Procedure date: 11/04/2026 at 8:00 AM (scheduled)'):
            with self.subTest(line=line):
                text = HEAD + line + '\n' + COLO_PLAIN
                self.assert_never(text, '2026-11-04')
                self.assert_asked(text, 'Procedure date')


class PopulationControlsTests(DateAssertions, SimpleTestCase):
    """Shapes the corpus, the fixtures and the live encounters carry, which must read as before."""

    def test_controls(self):
        self.assert_document(HEAD + 'Date of service: 2026-10-20\n' + VISIT_BODY, '2026-10-20')
        self.assert_document(HEAD + 'MRN: SYN-100201 Date of service: 2026-10-06 Place of service: Office (POS 11)\n',
                             '2026-10-06')
        self.assert_document(HEAD + 'Date of service: 2026-10-05 (capsule placement)\n', '2026-10-05')
        elena = HEAD + 'Report | Patient Synthetic | Service date 20 October 2026 | Endoscopist Dr. A. Synthetic\n'
        self.assert_document(elena, '2026-10-20')
        self.assert_member_conflict(elena, ELENA_DATE)
        self.assert_document(HEAD + 'GI consultation note: 2026-10-20\nNext visit: 2026-12-01\n', '2026-10-20')
        planned = HEAD + 'Chief complaint: reflux.\nPlan\nColonoscopy scheduled.\nProcedure date: 2026-11-04\n'
        self.assertEqual((date_fact(planned).origin, date_fact(planned).evidence), ('missing', ()))


class Provider(FakeProvider):
    """FakeProvider whose response names only the selections the request's own text contains."""

    def send(self, request, *, deadline_s):
        every = self.selections
        self.selections = [(code, quote) for code, quote in every if quote in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.selections = every


@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class RequestDateTests(TestCase):
    """End to end with the suite's FakeProvider: the date each provider request carries, and the dated checks."""

    BIOPSY = ('43239', 'biopsies were taken from the antrum')
    SNARE = ('45385', 'was removed with a cold snare')
    VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(selections=[self.VISIT, self.SNARE, self.BIOPSY])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def finished(self, text, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return response.json()['id']

    def set_context(self, encounter_id, values):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/encounters/{encounter_id}/context', data=json.dumps(values),
                                        content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        drain()

    def dates_sent(self, encounter_id):
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id, sent=True).order_by('created_at')
        return [list(run.contexts[1:]) for run in runs]

    def proposal(self, encounter_id, code):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        return encounter.current_assessment.proposals.get(code=code, bucket__in=('selected', 'excluded'))

    def assert_held(self, encounter_id):
        self.assertEqual(self.dates_sent(encounter_id), [])
        held = models.ProviderRun.objects.get(encounter_id=encounter_id)
        self.assertEqual((held.state, held.scope),
                         (models.ProviderRun.NOT_SENT, {'held': models.ProviderRun.HELD_MEMBER_DATE_CONFLICT}))
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'needs_clarification')

    def test_c2_1_a_planned_date_is_never_sent_and_the_act_done_today_never_excluded(self):
        text = (HEAD + 'EGD report - 10/14/2026\nIndication: dyspepsia.\nColonoscopy procedure date: 11/04/2026, '
                       'scheduled for 8:00 AM.\n' + EGD_BODY)
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])  # the date is asked, no date is sent
        self.assertNotEqual(self.proposal(encounter_id, '43239').bucket, 'excluded')
        self.set_context(encounter_id, {'service_date': '2026-10-14'})  # the member chooses the report's date
        self.assertEqual(self.dates_sent(encounter_id), [[], ['Date of service: 2026-10-14']])
        self.assertNotEqual(self.proposal(encounter_id, '43239').bucket, 'excluded')

    def test_c2_2_a_member_date_never_replaces_the_labelled_date_and_a_letter_date_is_never_sent(self):
        text = HEAD + 'Indication: Personal history of colon polyps Date of service: 10/14/2026\n' + COLO_PLAIN
        self.assert_held(self.finished(text, service_date=ELENA_DATE))
        letter = (HEAD + 'Date: 10/27/2026\nIndication: Personal history of colon polyps Date of service: 10/14/2026\n'
                  + COLO_BODY)
        encounter_id = self.finished(letter)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assertNotEqual(self.proposal(encounter_id, '45385').bucket, 'excluded')

    def test_c2_3_a_member_date_never_replaces_a_visit_title_s_date(self):
        text = HEAD + 'Nurse practitioner visit - 10/20/2026\n' + OFFICE_BODY
        self.assert_held(self.finished(text, service_date=ELENA_DATE))
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [['Date of service: 2026-10-20']])

    def test_c2_5_a_letter_or_title_date_is_never_sent_for_the_labelled_one(self):
        for text in (HEAD + 'Date: 10/16/2026\nDate of service: 10/14/2026 (recall due in 3 years)\n' + COLO_PLAIN,
                     HEAD + 'Date: 10/27/2026\nRe: GI office visit\nDate of visit: 10/20/2026 (follow-up)\n'
                     + OFFICE_BODY):
            with self.subTest(text=text.splitlines()[2][:40]):
                self.assertEqual(self.dates_sent(self.finished(text)), [[]])

    def test_c2_6_an_outside_procedure_date_is_never_sent(self):
        for line in ('Indication: Surveillance. Procedure date: 09/03/2026 (outside facility; cold snare polypectomy '
                     'of two adenomas).', 'Outside colonoscopy:\nProcedure date: 09/03/2026'):
            with self.subTest(line=line[:40]):
                text = HEAD + 'Colonoscopy report - 10/14/2026\n' + line + '\n' + COLO_PLAIN
                self.assertEqual(self.dates_sent(self.finished(text)), [[]])

    def test_c2_7_a_pathology_or_letter_date_is_never_sent(self):
        pathology = (HEAD + 'Colonoscopy pathology report: 10/17/2026\nSpecimen A: sigmoid polyp - tubular adenoma.\n\n'
                     + COLO_PLAIN)
        self.assertEqual(self.dates_sent(self.finished(pathology)), [[]])
        self.assert_held(self.finished(pathology, service_date=ELENA_DATE))
        letter = HEAD + 'Date: 10/27/2026\nRe: GI follow-up consultation of 10/20/2026\nDear Dr. Synthetic,\n' + OFFICE_BODY
        encounter_id = self.finished(letter)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': '2026-10-20'})  # the member chooses the visit's date
        self.assertEqual(self.dates_sent(encounter_id), [[], ['Date of service: 2026-10-20']])

    def test_c2_8_a_member_date_never_replaces_an_unread_or_re_line_date(self):
        for header in ('Date/Time of Service: 10/20/2026 09:15', 'Re: GI consultation of 10/20/2026'):
            with self.subTest(header=header):
                self.assert_held(self.finished(HEAD + header + '\n' + OFFICE_BODY, service_date=ELENA_DATE))
