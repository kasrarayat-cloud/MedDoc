"""GI round 2, second fix round (session 7c8d38da, fix agent "dates"; the convergence step): the differential round's
date findings against the integrated head (aec8edf3f, carried to c076702c7) in studio/gi/context.py. Each was reproduced
on that head and on the installed tree 2b82889f before anything changed; every repair NARROWS toward the installed
reading, while the round's intended gains - ho-04's date, the narrow source rule, rule U, BIRTH, PART and ORDER - hold.

edges-2 and F-2 (a must-fix class 1 shape: a genuine date conflict sent where installed asked). The fix round's F4 read
the time statement's whole LINE for a token that may state a day. A PDF upload breaks the statement every 90
characters, so the other day landed on the next line ("... counseling and" / "care coordination; Date: 10/23/2026") and
the header's 2026-10-22 was sent, where the TXT and DOCX uploads of the same note were asked; and the tokens missed the
day words with no digit beside them ("34 minutes on the twenty-third", "October twenty-third") and the Roman-numeral
months ("23/X/26"): sent, and with no labelled date a member's 1998-01-01 or 2026-10-21 taken - installed asked and
held.
The elapsed-time rule's two readings (a: a date-of-service phrase dating a duration is no date field; b: a date field
holding only durations states no date) now apply only where the statement's soft-wrapped RUN - the lines the layout
joins into its sentence, with the next line where the run leaves its field open or does not close its sentence (and
that line opens no field or list item of its own), or that line opens with a bracket, and with the line above where it
leaves its field open over the statement - holds, outside its durations and any date-of-service label with its own
read date, no digit at all and no month's name or abbreviation, weekday or ordinal word ("first" to "thirty-first").
Anything else keeps the installed reading (asked). ho-04's own sentence still sends 2026-10-22 in every form.

F-4 (a capability regression, and F-1's enabler). The ORDER rule read the place word "outside" as an earlier time, so
"Outside colonoscopy (Synthetic Regional Hospital) date of service: 10/27/2026" beside the visit's own "Date of service:
10/13/2026" asked the visit's correct date. ORDER now reads only the history words that state an earlier time (prior,
previous, last, recent, remote, earlier, past, index, history of, s/p, ...), never a place: the visit's date is sent as
installed sends it.

F-1 (must-fix class 1). With the note's own date put in doubt by BIRTH, ORDER or PART and no other own date, every
candidate became the evidence of the date asked, so a member's answer equal to ANY dated line was taken and sent (an
office visit's "EGD on 05/01/2019": 2019-05-01 sent, where installed held it beside the visit's own date). The doubt
rules now only ask: the date asked is answered only by what the reading without them answers with (the doubted label's
own value, a documented conflict's values, or the dates its evidence reads), less a date of birth.

F-3 stays open by decision (rule N1; an owner item): nothing here changes it.

Every text here is synthetic (fictional patients); no network (the suite's FakeProvider).
"""
from django.test import SimpleTestCase

from studio import models
from studio.gi import context
from studio.gi.sections import layout
from studio.ingest import extract as ingest
from studio.types import to_jsonable
from tests.support import docgen
from tests.test_repairs_7c8_context import DateAssertions, merged_date
from tests.test_repairs_7c8_context3 import COLO_PLAIN, ELENA_DATE, HEAD, EndToEnd, date_fact

OFFICE = ('GI Clinic - Office Visit\nPatient: Alex Synthetic    DOB: 01/01/1970\nDate of service: 2026-10-22\n'
          'Provider: Bea Synthetic, MD\n\nHistory of present illness: dysphagia to solids for 3 months.\n'
          'Assessment: dysphagia; EGD scheduled.\nPlan: EGD with possible dilation.\n\n'
          'Medical decision making: Moderate.\n')
UNDATED = OFFICE.replace('Date of service: 2026-10-22\n', '')
SIGNED = '\nElectronically signed by Bea Synthetic, MD\n'
HO04_SENTENCE = ('Total time on the date of service: 34 minutes, including record review, history, examination, '
                 'counseling and documentation.')
# the differential round's edges-2 statements: each dates the time on 10/23 while the header says 10/22
OTHER_DAY = (
    'Total time on the date of service: 34 minutes, including record review, counseling and care coordination; '
    'Date: 10/23/2026',
    'Total time on the date of service: 34 minutes, including record review, counseling and coordination (see note: '
    '10/23/2026)',
    'Total Time on Date of Service: 34 min, including record review, counseling and care coordination | Date: '
    '10/23/2026',
    'Total time on the date of service: 34 minutes, including review of outside records and counseling (23OCT26)',
)
# the same statements broken by hand as a PDF line or a narrow column may break them
HAND_WRAPPED = (
    'Total time on the date of service: 34 minutes, including record review and counseling, all of it spent on\n'
    '10/23/2026.',
    'Total time on the date of service: 34 minutes, including record review and counseling performed\non 10/23/2026.',
    'Total Time on Date of Service: 34 min, including review of outside records and counseling, on Friday\n10/23/2026.',
    'Total time on the date of service: 34 minutes\n(10/23/2026).',
    'Total time on the date of service: 34 minutes (time spent on\n23OCT26).',
    'Time spent on 10/23/2026:\nTotal time on the date of service: 34 minutes.',
    'Total time on the date of service: 34 minutes | Date:\n10/23/2026',
    'Total time on the date of service: 34 minutes, including counseling (see note dated\n10/23/2026).',
)
# F-2: a day stated with no digit beside it, or with a Roman-numeral month
DAY_WORDS = ('34 minutes on the twenty-third', '34 minutes on the twenty third', '34 minutes on October twenty-third',
             '34 minutes on the twenty-third of October', '34 minutes on the third', '34 minutes (twenty-third)',
             '34 minutes on the thirty-first', '34 minutes on 23/X/26', '34 minutes on 23-X-26',
             '34 minutes on 23.X.26', '34 minutes in October', '34 minutes on Tuesday')


def pdf_wrapped(line: str) -> str:
    """The statement as a PDF upload's lines break it (tests.support.docgen, 90 characters)."""
    return '\n'.join(docgen._wrapped(line, docgen.PDF_LINE_CHARS))


def uploaded(text: str, form: str) -> str:
    """The text the engine reads from an upload of ``text`` in ``form`` (the product's own extraction door)."""
    if form == 'pdf':
        data = docgen.make_pdf(['\n'.join(docgen._wrapped(text.rstrip('\n'), docgen.PDF_LINE_CHARS))])
        return ingest.extract_document(data, 'case.pdf', 'application/pdf', ocr=None).text
    if form == 'docx':
        data = docgen.make_docx(text.split('\n'))
        return ingest.extract_document(
            data, 'case.docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', ocr=None).text
    return ingest.extract_paste(text).text


class ElapsedTimeReadsTheStatementsRunTests(DateAssertions, SimpleTestCase):
    """edges-2 and F-2: a time statement stating another day keeps the installed reading (asked), in every form."""

    def assert_asked_as_installed(self, text):
        self.assert_never(text, '2026-10-22')
        self.assert_question(text, '2026-10-22')  # the header's own date answers it; ELENA_DATE is held
        self.assert_member_conflict(text, '2026-10-23')

    def test_a_statement_naming_another_day_is_asked_when_a_pdf_breaks_its_line(self):
        for line in OTHER_DAY:
            for text in (OFFICE + pdf_wrapped(line) + '\n' + SIGNED, OFFICE + line + '\n' + SIGNED):
                with self.subTest(text=text.split('Moderate.\n')[1][:90]):
                    self.assertTrue('\n' in pdf_wrapped(line))  # the PDF form really breaks the statement
                    self.assert_asked_as_installed(text)

    def test_every_upload_form_of_the_note_is_asked(self):
        # through the product's extraction door: TXT (paste), DOCX and PDF uploads of one note read alike
        for line in OTHER_DAY:
            for form in ('text', 'docx', 'pdf'):
                with self.subTest(line=line[-30:], form=form):
                    self.assert_asked_as_installed(uploaded(OFFICE + line + '\n' + SIGNED, form))

    def test_a_statement_broken_by_hand_is_asked(self):
        for statement in HAND_WRAPPED:
            text = OFFICE + statement + '\n' + SIGNED
            with self.subTest(statement=statement):
                self.assert_asked_as_installed(text)

    def test_a_date_field_beside_the_statement_is_read(self):
        # deep in a note, where a bare "Date:" line is no dated title of its own: a PDF break before the field (the
        # one-line form "34 minutes Date: 10/23/2026" is asked), a field after the closed sentence, a field above it
        deep = OFFICE.replace('Medical decision making: Moderate.\n', ''.join(
            f'Review of systems item {i}: negative.\n' for i in range(15)) + 'Medical decision making: Moderate.\n')
        statement = 'Total time on the date of service: 34 minutes'
        for tail in (statement + '\nDate: 10/23/2026\n', statement + '.\nDate: 10/23/2026\n',
                     statement + '.\n10/23/2026\n', 'Date: 10/23/2026\n' + statement + '.\n',
                     'Date/Time: 10/23/2026 14:05\n' + statement + '.\n'):
            with self.subTest(tail=tail):
                self.assert_never(deep + tail + SIGNED, '2026-10-22')
                self.assert_question(deep + tail + SIGNED, '2026-10-22')
        # a date-of-service label above speaks as a label of its own (its date is masked): the note's date is sent
        self.assert_document(deep + 'Date of service: 10/22/2026\n' + statement + '.\n' + SIGNED, '2026-10-22')

    def test_a_day_with_no_digit_beside_it_or_a_roman_numeral_month_is_asked(self):
        for words in DAY_WORDS:
            statement = 'Total time on the date of service: ' + words
            with self.subTest(words=words):
                self.assert_asked_as_installed(OFFICE + statement + '\n' + SIGNED)
                # with no labelled date the statement holds every member date, as installed (no date to agree with)
                undated = UNDATED + statement + '\n' + SIGNED
                for member in ('2026-10-21', '2026-10-22', ELENA_DATE):
                    self.assert_member_conflict(undated, member)

    def test_ho04_s_sentence_still_sends_its_date_in_every_form(self):
        for form in ('text', 'docx', 'pdf'):
            text = uploaded(OFFICE + HO04_SENTENCE + '\n' + SIGNED, form)
            with self.subTest(form=form):
                self.assert_document(text, '2026-10-22')
                self.assert_member_conflict(text, '2026-10-23')
        self.assert_document(OFFICE + pdf_wrapped(HO04_SENTENCE) + '\n' + SIGNED, '2026-10-22')

    def test_what_the_run_does_not_read_still_sends_the_date(self):
        # durations of every form; a wrapped label; a next line that opens a field or a list item of its own, or
        # follows a closed sentence; a line above that closes its own sentence
        for statement in ('Total time on the date of service: 120 minutes',
                          'Total time on the date of service: 30-39 minutes',
                          'Total time on the date of service: 1 hour 5 minutes',
                          'Time on date of service: 34 minutes (face-to-face 20 minutes).',
                          'Total time on the\ndate of service: 34 minutes, including record review.',
                          'Total time on the date of service: 34 minutes\nPlan: Return in 3 months.',
                          'Total time on the date of service: 34 minutes.\nReturn in 3 months.',
                          'Total time on the date of service: 34 minutes\n1. EGD on 2026-11-18.'):
            with self.subTest(statement=statement):
                self.assert_document(OFFICE + statement + '\n' + SIGNED, '2026-10-22')
        above = OFFICE.replace('Medical decision making: Moderate.', 'Medical decision making: Moderate (2 problems).')
        self.assert_document(above + HO04_SENTENCE + '\n' + SIGNED, '2026-10-22')

    def test_the_rule_s_vocabulary_is_closed(self):
        # the ordinal words "first" to "thirty-first" with a hyphen, a space or neither; the calendar's own names
        self.assertEqual(len(context._ORDINAL_WORDS), 21 + 9 * 3 + 3)
        for word in ('twenty-third', 'twenty third', 'twentythird', 'thirty-first', 'third', 'October', 'Oct',
                     'Tuesday', 'Tue', 'March'):
            with self.subTest(word=word):
                self.assertIsNotNone(context._RUN_DAY.fullmatch(word))
        for word in ('documentation', 'monitoring', 'thirty', 'twenty', 'seconds'):
            with self.subTest(word=word):
                self.assertIsNone(context._RUN_DAY.search(word))

    def test_known_limit_a_digit_beside_the_duration_keeps_the_installed_reading(self):
        # Pinned so a change is seen (moved here from test_repairs_gi2_date's TIME_FIELDS by this round): a run that
        # holds any digit outside its durations, or a word that may name a month, a weekday or an ordinal day, keeps the
        # installed reading (asked) - an over-hold, never another date
        for statement in ('Total time on the date of service: 34 minutes; >50% counseling',
                          'Total time on the date of service: 34 minutes; the patient may return as needed',
                          'Total time on the date of service: 34 minutes, first visit with this clinic'):
            with self.subTest(statement=statement):
                self.assert_never(OFFICE + statement + '\n' + SIGNED, '2026-10-22')
                self.assert_question(OFFICE + statement + '\n' + SIGNED, '2026-10-22')

    def test_known_limit_the_reach_is_one_line_either_side(self):
        # Pinned so a change is seen: a day two lines past a broken statement whose middle line closes nothing and is
        # no field, or a date field two lines above it, is not read - the note's date is sent, as 057a7d398 sends it
        # (installed asked only because "34" was misread as a date); the one-line forms are asked
        deep = OFFICE.replace('Medical decision making: Moderate.\n', ''.join(
            f'Review of systems item {i}: negative.\n' for i in range(15)) + 'Medical decision making: Moderate.\n')
        statement = 'Total time on the date of service: 34 minutes'
        for tail in (statement + '\nIncluding counseling\nPerformed 10/23/2026.\n',
                     'Date: 10/23/2026\nTime statement\n' + statement + '.\n'):
            with self.subTest(tail=tail):
                self.assert_document(deep + tail + SIGNED, '2026-10-22')
        self.assert_never(deep + statement + ' including counseling performed 10/23/2026.\n' + SIGNED, '2026-10-22')

    def test_known_limit_a_relative_day_word_is_not_read(self):
        # Pinned (row gi2 dates-day-words): a relative day is no word of the closed classes, so the date is sent, as
        # 057a7d398 sends it; installed asked only because "34" was misread as a date
        self.assert_document(OFFICE + 'Total time on the date of service: 34 minutes, of which 10 minutes yesterday\n'
                             + SIGNED, '2026-10-22')


GI_VISIT = 'GI office visit\n'
VISIT_TAIL = ('History of present illness: Synthetic patient seen in clinic for constipation.\n'
              'Assessment: Chronic constipation.\nPlan: fiber; return in 3 months.\n')
# the differential round's F-4 inputs (o1, o2, o5) and the broad corpus's lens:0eb7032f9299
OUTSIDE = 'Outside colonoscopy (Synthetic Regional Hospital) date of service: 10/27/2026\n'
OUTSIDE_LATER = (
    (HEAD + GI_VISIT + 'Date of service: 10/13/2026\n' + OUTSIDE + 'EGD on 05/01/2019\n' + VISIT_TAIL, '2026-10-13'),
    (HEAD + GI_VISIT + 'Date of service: 10/13/2026\n' + OUTSIDE + VISIT_TAIL, '2026-10-13'),
    (HEAD + 'GI visit\nDate of Service: 10/13/2026\nOutside procedure (MRN 0000) Date of Service: 10/27/2026\n'
     'EGD on 05/01/2019\nGI office visit\n' + VISIT_TAIL, '2026-10-13'),
    (HEAD + 'Date of procedure    Room    MRN\ntoday    Synthetic, Alex\nDate of Service: 10/14/2026 08:30    '
     'Scheduled by: Front desk\nDOS: 10/14/2026\nOutside EGD Date of Service: 10/21/2026 pending\n'
     'PROCEDURE NOTE: EGD\nTechnique: The upper endoscope was advanced to the second portion of the duodenum.\n'
     'Findings: biopsies were taken from the antrum.\n', '2026-10-14'),
)
EARLIER_LABELS = ('Recent EGD - Date of service', 'Prior colonoscopy - Date of service', 'Last EGD Date of Service',
                  'Index colonoscopy - Encounter date', 'Previous procedure date',
                  'Remote colonoscopy - Date of service', 'Past EGD - Date of service')


def earlier_than(label: str) -> str:
    """The visit's own 10/13 beside an earlier occurrence's label dated 10/27, and a dated line of 2019."""
    return (HEAD + GI_VISIT + 'Date of service: 10/13/2026\n' + label + ': 10/27/2026\nColonoscopy on 05/01/2019\n'
            + VISIT_TAIL)


class OrderReadsOnlyWordsOfAnEarlierTimeTests(DateAssertions, SimpleTestCase):
    """F-4: a place word ("outside") states no earlier time."""

    def test_a_later_outside_procedure_leaves_the_visit_s_own_date(self):
        for text, own in OUTSIDE_LATER:
            with self.subTest(text=text.splitlines()[2][:60]):
                self.assert_document(text, own)
                self.assertNotIn(context.ORDER_DATE_NOTE, date_fact(text).note)
                self.assert_member_date(text, own)
                for other in ('2026-10-27', '2026-10-21', '2019-05-01', ELENA_DATE):
                    if other != own:
                        self.assert_member_conflict(text, other)

    def test_a_word_of_an_earlier_time_still_asks(self):
        for label in EARLIER_LABELS:
            text = earlier_than(label)
            with self.subTest(label=label):
                self.assert_never(text, '2026-10-13')
                self.assertIn(context.ORDER_DATE_NOTE, date_fact(text).note)
                self.assert_member_date(text, '2026-10-13')

    def test_the_vocabulary_is_the_history_words_less_the_place_word(self):
        self.assertEqual(context._EARLIER_TIME_WORDS,
                         (r'history\s+of', r'hx\s+of', 'h/o', 's/p', r'status\s+post', 'prior', 'previous',
                          'previously', 'last', r'most\s+recent', 'recent', 'recently', 'remote', 'earlier', 'past',
                          'index'))
        self.assertIsNone(context._EARLIER_OCCURRENCE.search('Outside colonoscopy (Synthetic Regional Hospital)'))
        self.assertIsNotNone(context._EARLIER_OCCURRENCE.search('Prior colonoscopy'))
        self.assertNotIn('outside', context.ORDER_DATE_NOTE)


# F-1: an own date in doubt beside a dated line naming another date
DOUBTED = (
    # ORDER: the visit's own 10/13 earlier than a recent or prior procedure's 10/27; a 2019 history line
    (earlier_than('Recent EGD - Date of service'), '2026-10-13', '2019-05-01'),
    (HEAD + GI_VISIT + 'Date of service: 10/13/2026\nPrior colonoscopy (Synthetic Regional Hospital) date of service: '
     '10/27/2026\nEGD on 05/01/2019\n' + VISIT_TAIL, '2026-10-13', '2019-05-01'),
    # PART: a later numbered part that documents no procedure; a 2019 dated service line at the top
    (HEAD + 'EGD 05/01/2019\nGI office visit\nPlan:\nColonoscopy.\nSection B: Procedure note\nDate of service: '
     '11/04/2026\n', '2026-11-04', '2019-05-01'),
    (HEAD + 'Colonoscopy 05/01/2019\nGI office visit\nPlan:\nColonoscopy with possible polypectomy.\n\nPART 2 - '
     'PROCEDURE NOTE\nProcedure date: 11/04/2026\n', '2026-11-04', '2019-05-01'),
)
# BIRTH: the label states the date of birth; a dated service line of 10/14 beside it
BIRTH_BESIDE_A_LINE = (
    HEAD + 'Colonoscopy report\nColonoscopy 10/14/2026\nPatient: Synthetic, Alex\nDOB: 01/01/1998\n'
    'Date of service: 01/01/1998\n\n' + COLO_PLAIN,
    HEAD + 'Colonoscopy 10/14/2026\nColonoscopy report\nDate of service: 01/01/1998    Date of birth: 01/01/1998\n\n'
    + COLO_PLAIN,
)
# the reading without the doubt answers with the dates its stacked labels' values state (installed takes them)
STACKED = (HEAD + 'GI visit\nColonoscopy performed 10/21/2026\nEncounter date:\nDate of service:\nLocation:\n'
           '10/14/2026\n01/01/1998\nEndoscopy unit\nIndex EGD (MRN 0000) Service date: 10/21/2026 (signed)\n'
           'DOS - 10/13/2026\nGI office visit\n' + VISIT_TAIL)


class DoubtedDateIsAnsweredOnlyAsBeforeTests(DateAssertions, SimpleTestCase):
    """F-1: the own-dates-in-doubt rules ask; they never let a member's answer be taken that the reading without them
    holds."""

    def test_a_dated_line_beside_a_doubted_date_is_no_member_s_answer(self):
        for text, doubted, line_date in DOUBTED:
            with self.subTest(text=text.splitlines()[1:4]):
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('missing', None))  # asked: the doubt rules stand
                self.assert_member_date(text, doubted)  # the doubted label's own value answers, as installed takes it
                held = merged_date(text, line_date)
                self.assertTrue(context.is_member_conflict(held), held.note)
                # said with the installed note: the request then goes without a date (no ISO date is named as the
                # document's), and every reader knows a member conflict by its prefix, also as stored
                self.assertTrue(held.note.startswith(context.USER_CONFLICT_NOTE.split('{', 1)[0]))
                self.assertIn('the document gives “', held.note)
                self.assertTrue(context.is_member_conflict(to_jsonable(held)))
                self.assert_member_conflict(text, ELENA_DATE)

    def test_a_date_of_birth_label_answers_nothing(self):
        for text in BIRTH_BESIDE_A_LINE:
            with self.subTest(text=text.splitlines()[1:3]):
                self.assertIn(context.BIRTH_DATE_NOTE, date_fact(text).note)
                for member in ('2026-10-14', '1998-01-01', '2026-10-21'):
                    self.assert_member_conflict(text, member)
                self.assertIn("the patient's date of birth", merged_date(text, '1998-01-01').note)

    def test_what_the_reading_without_the_doubt_answers_with_is_still_taken(self):
        # a stacked header's values the installed reading reads as the evidence of the date asked
        self.assertIn(context.ORDER_DATE_NOTE, date_fact(STACKED).note)
        for member in ('2026-10-13', '2026-10-14', ELENA_DATE):  # ELENA_DATE: the stack's own 01/01/1998 value
            self.assert_member_date(STACKED, member)
        self.assert_member_conflict(STACKED, '2026-10-21')

    def test_only_which_spans_answer_moved(self):
        # the fact's origin, value, note and quoted evidence are what the reading gives without the bound
        for text, _, _ in DOUBTED + tuple((t, None, None) for t in BIRTH_BESIDE_A_LINE + (STACKED,)):
            found = context._service_dates(text, layout(text))
            bounded, unbounded = context._service_date_fact(found), context._date_fact(found)
            with self.subTest(text=text.splitlines()[1:3]):
                self.assertEqual((bounded.origin, bounded.value, bounded.note),
                                 (unbounded.origin, unbounded.value, unbounded.note))
                self.assertEqual([(e.start, e.end, e.text) for e in bounded.evidence],
                                 [(e.start, e.end, e.text) for e in unbounded.evidence])
                self.assertEqual(to_jsonable(bounded), to_jsonable(unbounded))  # as stored


class TheRequestCarriesWhatInstalledSendsTests(EndToEnd):
    """End to end with the suite's FakeProvider: the request bodies of the findings' inputs."""

    def test_the_visit_s_own_date_is_sent_and_a_dated_line_s_date_is_held(self):
        text = OUTSIDE_LATER[0][0]
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [['Date of service: 2026-10-13']])
        self.set_context(encounter_id, {'service_date': '2019-05-01'})
        self.assert_held(encounter_id, runs=2)
        self.assert_never_sent(encounter_id, '2019-05-01')

    def test_a_doubted_date_s_dated_line_is_never_sent(self):
        text = DOUBTED[0][0]
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])  # asked: a dateless request
        self.set_context(encounter_id, {'service_date': '2019-05-01'})
        # held as a member conflict: nothing new is built or sent (the dateless request stands, never re-sent)
        stored = models.Encounter.objects.get(pk=encounter_id).current_context.facts['service_date']
        self.assertTrue(context.is_member_conflict(stored), stored)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assert_never_sent(encounter_id, '2019-05-01')
        # the doubted label's own date answers the question and makes the dated request
        self.set_context(encounter_id, {'service_date': '2026-10-13'})
        self.assertEqual(self.dates_sent(encounter_id), [[], ['Date of service: 2026-10-13']])

    def test_a_pdf_broken_statement_naming_another_day_sends_no_date(self):
        encounter_id = self.finished(OFFICE + pdf_wrapped(OTHER_DAY[0]) + '\n' + SIGNED)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assertTrue(models.Clarification.objects.filter(encounter_id=encounter_id, fact='service_date').exists())
