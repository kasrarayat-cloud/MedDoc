"""GI round 2 (session 7c8d38da, repair "date"): elapsed time is no date of service, and a member's date equal to a date
the reader reads as another occurrence's is said to be so (studio/gi/context.py).

The 2b82889f acceptance walk's preserved failure (ho-04): "Total time on the date of service: 34 minutes, including
record review, ..." was read as a date-of-service FIELD whose value "34" is a date this service cannot read, so the
note's own "Date of service: 2026-10-22" became a conflict ("A labelled or title date of service is not written in a
form this service reads."), the request went without its date, 99214 waited for a member's answer, and - where a note
labels no date of its own - every member date was held. The installed revision before it, 057a7d398, read 2026-10-22.
The source states the date once ("Date of service: 2026-10-22"); "34 minutes" is the physician's elapsed time ON that
date, a quantity, never a calendar date.

The repair is structural (context._holds_duration, context._measured_on and the date-label loop of
context._service_dates); its only vocabulary is units of time (minutes, hours, seconds and their abbreviations) - days,
weeks and months are left out on purpose, because a date offset is written in them:
- a date-of-service phrase that is the object of the words before it ("Total time ON the date of service", "Time spent
  ON DOS", "Counseling time ON the date of visit": the words end with a connecting word) dates the quantity those words
  name; when its field holds a DURATION and nothing date-like, it is that quantity's field and no date candidate at all;
- a date-of-service field holding nothing but durations ("Date of service: 34 minutes") states no date: it is kept as an
  empty field (rule N3), never a date this service cannot read.
A field that may state another day keeps the installed reading (asked): a date, a number of three or more digits, an
ordinal day or a weekday outside the durations, or a number opening the field. A qualified date label ("Initial date of
service: 2 hours after arrival") is no quantity's label and keeps the installed reading too.

The member note (the occurrence investigation's R4 (ii)): a member's date equal to a date the reader reads in the
document only as another occurrence's or another document's (or possibly one) was held with "the document gives “Date
of service: 10/14/2026”. Both are kept and neither is used until they agree" - as if the two dates differed. The note
now says how this service reads that date (never what the document states nowhere else: the same day may be written in
a form it does not read). What is held, sent and stored is unchanged; the note keeps the installed prefix every reader
(and a rollback to 2b82889f) recognises a member conflict by.

Every text here is synthetic (fictional patients); no network (the suite's FakeProvider).
"""
from django.test import SimpleTestCase

from studio import models
from studio.gi import context
from studio.types import to_jsonable
from studio.validation import checks
from tests.test_repairs_7c8_context import DateAssertions, merged_date
from tests.test_repairs_7c8_context3 import COLO_BODY, ELENA_DATE, HEAD, EndToEnd, date_fact

# the prefix 2b82889f's is_member_conflict (and every reader that words a conflict) recognises a member conflict by
INSTALLED_MEMBER_CONFLICT_PREFIX = 'Encounter metadata entered by a workspace member gives '
DOS = 'Date of service: 2026-10-22\n'


def office(date_line: str, time_line: str) -> str:
    return (HEAD + '\nGastroenterology Office Visit\nPlace of service: Office (POS 11)\n' + date_line
            + 'Visit type: Established patient, return visit.\n\nAssessment\nGastroesophageal reflux disease, improved.'
            '\n\nPlan\nContinue omeprazole 20 mg daily.\n\nMedical decision making: Low. One stable chronic illness.\n'
            + time_line + '\n')


# E/M time statements written as the field of a date-of-service phrase: each is elapsed time ON the date of service
TIME_FIELDS = (
    'Total time on the date of service: 34 minutes, including record review, history, examination, counseling and '
    'documentation.',  # ho-04's own sentence
    'Total time spent on the date of service: 45 minutes.',
    'Total time on DOS: 30 min',
    'Total time on DOS = 30 min',
    'Time spent on date of service - 40 minutes',
    'Total physician time on date of service: 42 minutes',
    'Total time on date of encounter: 32 minutes',
    'Face-to-face time on the date of service: 25 minutes',
    'Counseling time on the date of visit: 15 minutes',
    'Total time on the date of service: 1 hour 5 minutes',
    'Total time on the date of service: 30-39 minutes',
    'Total time on the date of service: 10 to 15 minutes',
    'Total time on date of service: 1.5 hours',
    'Total time personally spent on the date of service: 34 min',
    'Total time on date of service | 34 minutes',
    'Total time on the date of procedure: 20 minutes',
    'Total time on visit date: 34 minutes',
    'TOTAL TIME ON DATE OF SERVICE: 34 MINUTES',
    'Total Time on Date of Service: 34 minutes, including documentation.',
    'Total time on the Date of Service: 34 minutes, including counseling.',
    'Total time on the date of service: 34 mins',
    'Total time on the date of service - 34 minutes',
    'Time on date of service: 34 minutes (face-to-face 20 minutes).',
    'Prolonged service time on the date of service: 75 minutes',
    'Total time on the date of service: 34 minutes; >50% counseling',
    'Total time spent on this date of service: 34 minutes',
    'Time with patient on date of service: 30 minutes',
    'Total time for the date of service: 34 minutes',
    'Total time on the date of service: 34 minutes    Visit type: Established',
    'Total time on the date of service: 34 minutes. Visit type: established.',
    'Total time on the\ndate of service: 34 minutes, including record review.',  # the label wrapped onto a second line
)
HO04 = (HEAD + '\nGastroenterology Office Visit\nPlace of service: Office (POS 11)\nDate of service: 2026-10-22\n'
        'Visit type: Established patient, return visit. Previous office visit: 2026-08-27.\n\nData Reviewed\n'
        'Barium esophagram of 2026-09-30 reviewed today. CBC of 2026-09-30: hemoglobin 14.1 g/dL.\n\n'
        'Plan\n1. EGD with possible balloon dilation is scheduled for 2026-11-18.\n\n'
        'Medical decision making: Moderate.\n'
        'Total time on the date of service: 34 minutes, including record review, history, examination, counseling and '
        'documentation.\n\nElectronically signed: Synthetic Clinician, MD, 2026-10-22 17:05\n')


class ElapsedTimeIsNoDateTests(DateAssertions, SimpleTestCase):
    def test_the_labelled_date_is_read_beside_a_time_field(self):
        for line in TIME_FIELDS:
            with self.subTest(line=line):
                text = office(DOS, line)
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value, fact.note), ('document', '2026-10-22', ''), fact.note)
                self.assertEqual([e.text for e in fact.evidence], ['Date of service: 2026-10-22'])
                # the member protections stay: another date is a member conflict, the documented one agrees
                self.assert_member_conflict(text, '2026-10-23')
                self.assert_member_conflict(text, ELENA_DATE)
                self.assertEqual((merged_date(text, '2026-10-22').origin, merged_date(text, '2026-10-22').value),
                                 ('user', '2026-10-22'))

    def test_ho04_shape(self):
        # the walk's own sentence in a note shaped like ho-04: the other dates name other occurrences (a previous visit,
        # prior studies, a scheduled EGD) and the signature's day is the same day
        fact = date_fact(HO04)
        self.assertEqual((fact.origin, fact.value, fact.note), ('document', '2026-10-22', ''))
        self.assertEqual(context.service_date_of(HO04).isoformat(), '2026-10-22')
        for other in ('2026-08-27', '2026-09-30', '2026-11-18', '2026-10-23'):
            self.assert_member_conflict(HO04, other)

    def test_no_labelled_date_lets_the_member_answer(self):
        # a time field states no date: the note's date is missing exactly as it is without the time field, and a
        # member's date is taken (2b82889f held every member date: the time field was kept as unreadable date evidence)
        plain = date_fact(office('', ''))
        for line in TIME_FIELDS:
            with self.subTest(line=line):
                text = office('', line)
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value, fact.evidence, fact.note),
                                 (plain.origin, plain.value, plain.evidence, plain.note))
                merged = merged_date(text, '2026-10-22')
                self.assertEqual((merged.origin, merged.value, merged.note), ('user', '2026-10-22', context.USER_NOTE))

    def test_a_date_label_after_a_time_field_is_the_date(self):
        # the field of the time label ends at the next field's label, never at one whose words run back over the unit
        # ("34 minutes. Date of service:"): the next label's date is the note's own (057a7d398 sends the same date)
        for line in ('Total time on the date of service: 34 minutes. Date of service: 10/23/2026',
                     'Total time on the date of service: 34 minutes, Date of service: 10/23/2026',
                     'Total time on the date of service: 34 minutes\nDate of service: 2026-10-23'):
            with self.subTest(line=line):
                self.assert_document(office('', line), '2026-10-23')

    def test_a_date_field_holding_only_durations_states_no_date(self):
        # rule N3: "Date of service: 34 minutes" is a date-of-service field stating no date - kept as an empty field: it
        # never questions the note's own date, and alone it holds a member's date as an empty field does
        for field in ('Date of service: 34 minutes\n', 'Date of service: 1 hour 5 minutes\n', 'DOS: 2 hrs.\n',
                      'Date of service: 34 minutes. Visit type: X\n'):
            with self.subTest(field=field):
                self.assert_document(office(field + 'Procedure date: 2026-10-22\n', ''), '2026-10-22')
                alone = date_fact(office(field, ''))
                self.assertEqual((alone.origin, alone.value), ('missing', None))
                self.assertTrue(alone.evidence)
                self.assertIn(context.EMPTY_DATE_NOTE, alone.note)
                self.assertNotIn(context.UNREAD_DATE_NOTE, alone.note)
                self.assert_member_conflict(office(field, ''), '2026-10-22')


class GenuineConflictsStayQuestionsTests(DateAssertions, SimpleTestCase):
    """The explicit applicable date is never sent over a date the document may state for another day: a time field that
    names a date, an ordinal day or a weekday keeps the installed reading (asked)."""

    def test_a_time_field_labelled_with_another_date(self):
        self.assert_conflict(office(DOS, 'Total time on the date of service 10/23/2026: 34 minutes'),
                             '2026-10-22', '2026-10-23')

    def test_a_time_field_stating_another_day(self):
        for line in ('Total time on the date of service: 34 minutes on 10/23/2026',
                     'Total time on the date of service: 34 minutes (2026-10-23)',
                     'Total time on the date of service: 34 minutes 10/23/2026',
                     'Time on date of service: 25 min; time on 10/23/2026: 10 min',
                     'Total time on the date of service: 34 minutes on October 23',
                     'Total time on the date of service: 34 minutes on Oct 23',
                     'Total time on the date of service: 34 minutes on 23 Oct 2026',
                     'Total time on the date of service: 34 minutes, 20261023',
                     'Total time on the date of service: 34 minutes on the 23rd',
                     'Total time on the date of service: 34 minutes on Friday',
                     'Total time on the date of service: 34 minutes (Fri)',
                     'Total time on the date of service: 2 x 17 minutes'):
            with self.subTest(line=line):
                text = office(DOS, line)
                self.assert_never(text, '2026-10-22')
                self.assert_question(text)

    def test_two_labelled_dates_of_service(self):
        self.assert_conflict(office(DOS + 'DOS: 2026-10-23\n', TIME_FIELDS[0]), '2026-10-22', '2026-10-23')
        self.assert_conflict(office(DOS, TIME_FIELDS[0] + '\nDate of service: 2026-10-23'), '2026-10-22', '2026-10-23')


class DateLabelsStayDateLabelsTests(DateAssertions, SimpleTestCase):
    def test_date_time_of_service(self):
        # a label naming the time is read and asked as before (rule N7); the time field no longer speaks against it, so
        # the member's answer with its date is taken and another date held
        text = office('Date/Time of service: 2026-10-22 14:05\n', TIME_FIELDS[0])
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value, fact.note), ('missing', None, context.FORM_DATE_NOTE))
        self.assertEqual([e.text for e in fact.evidence], ['Date/Time of service: 2026-10-22'])
        self.assert_member_date(text, '2026-10-22')
        self.assert_member_conflict(text, '2026-10-23')

    def test_empty_unreadable_and_non_date_fields_are_still_asked(self):
        for date_line in ('Date of service:\n', 'Date of service: 22-Oct-26\n', 'Date of service: N/A\n'):
            with self.subTest(date_line=date_line):
                text = office(date_line, TIME_FIELDS[0])
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('missing', None))
                self.assertTrue(fact.evidence)
                self.assert_member_conflict(text, ELENA_DATE)
                self.assert_member_conflict(text, '2026-10-22')

    def test_a_qualified_date_label_with_a_relative_value_keeps_the_installed_reading(self):
        # no quantity's label: the label's own word qualifies the date (no connecting word before the date phrase), and
        # its field carries words beside the duration - a date stated relative to another event, asked as before
        for line in ('Initial date of service: 2 hours after arrival',
                     'Revised date of service: 48 hours after the original visit',
                     'Actual date of service: 2 hours later',
                     'Colonoscopy date of service: 34 minutes after sedation'):
            with self.subTest(line=line):
                text = office(DOS, line)
                self.assert_never(text, '2026-10-22')
                self.assert_question(text)

    def test_a_relative_date_of_service_is_still_asked(self):
        text = office('Date of service: 48 hours after the index procedure\nProcedure date: 2026-10-14\n', '')
        self.assert_question(text, '2026-10-14')


class ElapsedTimeKnownLimitTests(DateAssertions, SimpleTestCase):
    """Pinned so a change is seen. A time field with no unit of time, a unit this grammar does not read, or no connecting
    word before the date phrase keeps the installed reading (asked beside a labelled date); a time field whose value is
    on the next line is an empty date field, as installed (beside a labelled date it is silent; with none it holds a
    member's date)."""

    def test_known_limit_no_unit_or_another_unit(self):
        for line in ('Total time on the date of service: 34', 'Minutes spent on date of service: 34',
                     'Time on date of service: 00:34', 'Total time on the date of service: 34m',
                     # no connecting word before the date phrase ("during" is none) and words beside the duration
                     'Time spent during DOS: 30 min, including counseling'):
            with self.subTest(line=line):
                self.assertEqual((date_fact(office(DOS, line)).origin, date_fact(office(DOS, line)).value),
                                 ('conflict', None))

    def test_known_limit_an_empty_date_field(self):
        # a time field read as an empty date field (rule N3): silent beside a labelled date; with none it holds a
        # member's date, as installed - its value on the next line, or a duration alone after a word that is no
        # connecting word ("during")
        for line in ('Total time on the date of service:\n34 minutes', 'Time spent during DOS: 30 min'):
            with self.subTest(line=line):
                self.assert_document(office(DOS, line), '2026-10-22')
                self.assert_member_conflict(office('', line), '2026-10-22')


class MemberDateOfAnotherOccurrenceNoteTests(SimpleTestCase):
    """R4 (ii): the member's date equals a date the document states only where the reader reads it as another
    occurrence's or another document's date (or possibly one, 'beside'). It is held as before; its note says why."""

    CASES = (  # (text, the member's date equal to the quoted date, the quoted span)
        (HEAD + 'Colonoscopy report\nDate of service: 10/14/2026 (recall due in 3 years)\n' + COLO_BODY, '2026-10-14',
         'Date of service: 10/14/2026'),
        (HEAD + 'Office visit\nNext procedure date: 11/04/2026\nAssessment: reflux.\n', '2026-11-04',
         'Next procedure date: 11/04/2026'),
        (HEAD + 'Colonoscopy report\nPrior DOS: 05/01/2019\n' + COLO_BODY, '2019-05-01', 'Prior DOS: 05/01/2019'),
        (HEAD + 'Surgical pathology report: 10/17/2026\nSpecimen: colon polyp.\n' + COLO_BODY, '2026-10-17',
         'Surgical pathology report: 10/17/2026'),
        (HEAD + 'Colonoscopy report\nPrior colonoscopy (DOB 01/01/1998) Date of service: 05/01/2019\n' + COLO_BODY,
         '2019-05-01', 'Date of service: 05/01/2019'),  # 'beside' (df-d:4): possibly another occurrence's
        (HEAD + 'Colonoscopy report\nNext procedure date: 11/04/2026\nLast visit date: 04/15/2026\n' + COLO_BODY,
         '2026-04-15', 'Last visit date: 04/15/2026'),
    )
    PHRASE = ("this service reads that date in the document as another occurrence's or another document's date, or as "
              "possibly one")

    def test_the_note_says_the_document_gives_that_date_only_as_another_occurrence_s(self):
        for text, member, quoted in self.CASES:
            with self.subTest(member=member, quoted=quoted):
                documented = date_fact(text)
                fact = merged_date(text, member)
                self.assertEqual((fact.origin, fact.value, fact.evidence), ('conflict', None, documented.evidence))
                self.assertTrue(context.is_member_conflict(fact), fact.note)
                self.assertTrue(fact.note.startswith(INSTALLED_MEMBER_CONFLICT_PREFIX + member + '; '), fact.note)
                self.assertIn(self.PHRASE, fact.note)
                self.assertIn('“' + quoted + '”', fact.note)
                self.assertNotIn('the document gives', fact.note)
                self.assertNotIn('until they agree', fact.note)
                stored = to_jsonable(fact)  # as stored: every reader of the stored fact recognises the conflict
                self.assertTrue(context.is_member_conflict(stored))
                self.assertTrue(stored['note'].startswith(INSTALLED_MEMBER_CONFLICT_PREFIX))

    def test_only_the_spans_stating_that_date_are_quoted(self):
        text = self.CASES[-1][0]
        fact = merged_date(text, '2026-11-04')
        self.assertIn('“Next procedure date: 11/04/2026”', fact.note)
        self.assertNotIn('Last visit date', fact.note)

    def test_the_note_never_says_the_document_states_it_nowhere_else(self):
        # the same day may also be written where this service reads no date ("Date of service: 11/04/26", a two-digit
        # year): the note speaks of what the service reads, never of everything the document states
        text = HEAD + 'Office visit\nDate of service: 11/04/26\nNext procedure date: 11/04/2026\nAssessment: reflux.\n'
        fact = merged_date(text, '2026-11-04')
        self.assertTrue(context.is_member_conflict(fact), fact.note)
        self.assertIn(self.PHRASE, fact.note)
        self.assertNotIn('only', fact.note)

    def test_another_date_keeps_the_installed_note(self):
        text, _, quoted = self.CASES[0]
        fact = merged_date(text, '2026-10-22')
        self.assertEqual(fact.note, context.USER_CONFLICT_NOTE.format(user='2026-10-22',
                                                                      document='“' + quoted + '”'))
        self.assertTrue(context.is_member_conflict(fact))

    def test_a_date_the_evidence_reads_is_still_taken(self):
        # interpretation 22 / rule N3: a member's date equal to a date the evidence reads as possibly this encounter's
        text = HEAD + 'Colonoscopy report - 10/14/2026\n' + COLO_BODY
        self.assertEqual((merged_date(text, '2026-10-14').origin, merged_date(text, '2026-10-14').value),
                         ('user', '2026-10-14'))

    def test_the_date_check_says_so(self):
        text, member, quoted = self.CASES[0]
        merged = context.merge_user_values(context.extract_context(text), {'service_date': member})
        check = checks.service_date_check(checks.service_date_state(merged, None))
        self.assertEqual(check.status, 'fail')
        self.assertIn('The date of service is in conflict. ' + INSTALLED_MEMBER_CONFLICT_PREFIX + member, check.detail)
        self.assertIn(self.PHRASE, check.detail)


class ElapsedTimeRequestTests(EndToEnd):
    """End to end with the suite's FakeProvider: the request of an ho-04-shaped note carries its labelled date (the walk
    sent it without one), and an undated note with a time field sends the member's date (2b82889f held it)."""

    VISIT = ('99214', 'Total time on the date of service: 34 minutes')

    def test_the_request_carries_the_labelled_date(self):
        encounter_id = self.finished(HO04)
        self.assertEqual(self.dates_sent(encounter_id), [['Date of service: 2026-10-22']])
        self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id, sent=False).exists())
        self.assertEqual(self.bucket(encounter_id, '99214'), 'selected')

    def test_an_undated_note_with_a_time_field_takes_the_member_date(self):
        encounter_id = self.finished(office('', TIME_FIELDS[0]))
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': '2026-10-22'})
        self.assertEqual(self.dates_sent(encounter_id), [[], ['Date of service: 2026-10-22']])
