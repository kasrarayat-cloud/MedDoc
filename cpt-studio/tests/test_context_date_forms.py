"""The owner's decision of 2026-11-07: the date reader reads more unambiguous forms of a stated date of service
(docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, "Owner decision, 2026-11-07", interpretation (a)-(d) and (b')
after the first refutation; the declaration tests/fixtures/gi4/declarations/dates-owner-ruling-20261107.json).

(1) Under the installed date-of-service labels (studio/gi/context.py: SERVICE_DATE, date_from_match, _installed_form) a
    day-first date with a month name and a four-digit year, and a weekday before a date the reader reads when the
    weekday is the date's own, read exactly as their month-day-year twin reads - the 2026-10-28 known limits included.
    A weekday naming another day reads exactly as installed (date text it does not read, asked).
(2) "Date of Operation", "Exam date" and "Examination date" (HEAD_SERVICE_DATE) are read ONLY in the document's head
    (before the installed _head_end), only where the label stands as a label (it opens its line or a field of its own),
    never under a title of a note written around a procedure, and only to SEND (context._ruled_head_date): where the
    installed reading sends no date and the fact read with them is the document's one date. Everywhere else, and with a
    blank, unreadable or absent value, they read exactly as installed - "Exam date" a wide label of the head,
    "Date of Operation" nothing: no new question, conflict, held answer or taken one.
(3) "Operation date", "Date/Time of Operation", "Date of exam", "Exam day", a two-digit year, an all-numeric date with
    hyphens or dots, "Date:" alone and every other label stay what installed reads.
The "as installed" classes below (AsInstalledTests and the twin parity) pass on the installed tree too: they pin the
installed reading, not a new one. Synthetic text only; no network.
"""
import datetime as dt

from django.test import SimpleTestCase

from studio import jobs
from studio.gi import context, detect
from studio.gi.sections import layout
from tests.test_repairs_7c8_context import DateAssertions
from tests.test_repairs_7c8_context3 import COLO_PLAIN, HEAD, OFFICE_BODY, date_fact

FAR = '1998-01-01'
DAY = '2026-11-09'  # a Monday
INSTALLED_LABELS = ('Date of service', 'DOS', 'Date of procedure', 'Procedure date', 'Service date', 'Visit date')
HEAD_LABELS = ('Date of Operation', 'Exam date', 'Examination date', 'DATE OF OPERATION', 'Exam Date', 'EXAMINATION DATE')
DECIDED = ('9 November 2026', '09 November 2026', '9-Nov-2026', '09-Nov-2026', '9 Nov 2026', '9 Nov. 2026', '9 Nov, 2026',
           '9th November 2026', 'Monday, November 9, 2026', 'Monday November 9, 2026', 'Mon 09-Nov-2026',
           'Mon., 11/09/2026', 'Monday 9 November 2026', 'MONDAY, 2026-11-09', 'Mon, Nov 9, 2026')
UNREAD = ('11/09/26', '9 Nov 26', '11-09-2026', '11.09.2026', '09.11.2026', '2026/11/09', '9th of November 2026',
          'Monday, 11/09/26', 'Monday, 11-09-2026', 'Tuesday, November 9, 2026', 'Sun 9 Nov 2026')
ANSWERS = (None, DAY, '2026-11-10', FAR, '2026-11-20', '2025-03-15', '2026-10-01')
AROUND = ('Endoscopy booking', 'Colonoscopy preparation instructions', 'Informed consent',
          'Pre-procedure telephone call', 'Pre-operative note')


def sends(text, answer=None):
    """What the request then carries: an ISO date, 'DATELESS' or 'HELD' (the member-date hold)."""
    merged = jobs._merged_facts(context.extract_context(text), {'service_date': answer} if answer else {})
    if context.is_member_conflict(merged['service_date']):
        return 'HELD'
    day = jobs._service_date_of(merged)
    return day.isoformat() if day else 'DATELESS'


def channel(text):
    return [sends(text, a) for a in ANSWERS]


def reading(text):
    """The fact without its note, and the date channel in every member state."""
    fact = date_fact(text)
    return (fact.origin, fact.value, [' '.join(e.text.split()) for e in fact.evidence]), channel(text)


class DecidedFormsUnderInstalledLabelsTests(DateAssertions, SimpleTestCase):
    def test_every_decided_form_under_every_installed_label_is_sent(self):
        for label in INSTALLED_LABELS:
            for value in DECIDED:
                text = HEAD + f'{label}: {value}\n' + COLO_PLAIN
                with self.subTest(label=label, value=value):
                    self.assert_document(text, DAY)
                    self.assertEqual(sends(text), DAY)
                    self.assert_member_conflict(text, FAR)
                    self.assertEqual(sends(text, '2026-11-10'), 'HELD')
                    self.assertEqual(context.service_date_of(text), dt.date(2026, 11, 9))

    def test_a_decided_form_reads_as_its_month_day_year_twin(self):
        # anywhere the installed label reads - a body block, an indication, a title of another discipline, a note
        # written around a procedure - the decided form reads as "11/09/2026" does: by construction, its limits too
        shapes = ('Colonoscopy Report\n{L}\n' + COLO_PLAIN, 'GI Procedure Note\nRadiology:\nCT abdomen\n{L}\n' + COLO_PLAIN,
                  'Colonoscopy Report\nIndication: Surveillance.\n{L}\n' + COLO_PLAIN, 'Informed consent\n{L}\n' + COLO_PLAIN,
                  'Cardiology consultation\n{L}\n' + COLO_PLAIN, 'Colonoscopy Report\n{L}\nStatus: Scheduled\n' + COLO_PLAIN,
                  'Recall:\n{L}\n' + COLO_PLAIN, 'Last procedure:\n{L}\n' + OFFICE_BODY)
        for shape in shapes:
            for label in ('Date of service', 'Procedure date'):
                twin = HEAD + shape.format(L=f'{label}: 11/09/2026')
                for value in ('9 November 2026', 'Monday, November 9, 2026', 'Mon 09-Nov-2026'):
                    text = HEAD + shape.format(L=f'{label}: {value}')
                    with self.subTest(shape=shape[:30], label=label, value=value):
                        a, b = date_fact(twin), date_fact(text)
                        self.assertEqual((b.origin, b.value), (a.origin, a.value))
                        self.assertEqual(channel(text), channel(twin))

    def test_the_weekday_is_the_dates_own(self):
        for weekday, ok in (('Monday', True), ('Mon', True), ('Mon.', True), ('Tuesday', False), ('Tue', False),
                            ('Sunday', False), ('Thurs', False), ('Wed.', False)):
            text = HEAD + f'Date of service: {weekday}, November 9, 2026\n' + COLO_PLAIN
            with self.subTest(weekday=weekday):
                if ok:
                    self.assert_document(text, DAY)
                else:  # one of the two is wrong: read exactly as installed reads it - date text it does not read, asked
                    fact = date_fact(text)
                    self.assertEqual((fact.origin, fact.value), ('missing', None))
                    self.assertIn(context.UNREAD_DATE_NOTE, fact.note)
                    self.assertEqual(sends(text), 'DATELESS')
                    self.assert_member_conflict(text, FAR)
        for value, day in (('Thursday, 2026-09-03', '2026-09-03'), ('Thu 3 Sep 2026', '2026-09-03'),
                           ('Sat 7 Nov 2026', '2026-11-07'), ('Sunday, November 8, 2026', '2026-11-08')):
            self.assertEqual(sends(HEAD + f'Procedure date: {value}\n' + COLO_PLAIN), day, value)

    def test_a_weekday_naming_another_day_masks_no_time_statement(self):
        # the elapsed-time rule reads the line above as installed reads it: the unread value masks nothing (_TimeRuns)
        text = HEAD + 'Total time on the date of service: 34 minutes.\nDate of service: Tuesday, November 9, 2026\n'
        fact = date_fact(text + COLO_PLAIN)
        self.assertEqual([' '.join(e.text.split()) for e in fact.evidence],
                         ['Total time on the date of service: 34', 'Date of service: Tuesday, November 9, 2026'])

    def test_the_other_forms_rule_n7_refuses_are_still_asked(self):
        for line in ('Date/Time of Service: 9 November 2026 08:00', 'Date & Time of Service: Monday, November 9, '
                     '2026 08:00', 'Date of service | 9 November 2026'):
            text = HEAD + 'Colonoscopy report\n' + line + '\n' + COLO_PLAIN
            with self.subTest(line=line):
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('missing', None), [e.text for e in fact.evidence])
                self.assertIn(context.FORM_DATE_NOTE, fact.note)
                self.assert_member_date(text, DAY)
                self.assert_member_conflict(text, FAR)

    def test_a_newly_read_date_that_disagrees_is_a_conflict(self):
        for first, second in (('Date of service: 11/10/2026', 'Procedure date: 9 November 2026'),
                              ('Date of service: Monday, November 9, 2026', 'Procedure date: 11/10/2026')):
            text = HEAD + first + '\n' + second + '\n' + COLO_PLAIN
            with self.subTest(first=first, second=second):
                self.assert_conflict(text, DAY, '2026-11-10')
                self.assertEqual(sends(text), 'DATELESS')
        self.assert_conflict(HEAD + 'Date of service: 9 November 2026\nRe: Colonoscopy 11/10/2026\n' + COLO_PLAIN,
                             DAY, '2026-11-10')
        self.assert_document(HEAD + 'Date of service: 9 November 2026\nRe: Colonoscopy 11/09/2026\n' + COLO_PLAIN, DAY)

    def test_still_unread_forms_keep_asking(self):
        for label in INSTALLED_LABELS:
            for value in UNREAD:
                text = HEAD + f'{label}: {value}\n' + COLO_PLAIN
                with self.subTest(label=label, value=value):
                    fact = date_fact(text)
                    self.assertEqual((fact.origin, fact.value), ('missing', None), [e.text for e in fact.evidence])
                    self.assertTrue(fact.evidence)  # documented date text: asked, never a gap filled silently
                    self.assertEqual(sends(text), 'DATELESS')
                    self.assert_member_conflict(text, FAR)

    def test_the_head_reader_reads_a_weekday_form_as_an_own_date_field(self):
        # detect's head (todays_procedure_report, the head's own date) reads SERVICE_DATE: the weekday form as its twin
        for line, own in (('Date of service: Monday, November 9, 2026', (dt.date(2026, 11, 9),)),
                          ('Date of service: 9-Nov-2026', (dt.date(2026, 11, 9),)),
                          ('Date of service: Tuesday, November 9, 2026', ()),
                          ('Date of service: 11/09/26', ()),
                          ('Date of Operation: 11/09/2026', ())):  # the head labels feed the date fact only
            text = (HEAD + 'Colonoscopy Report\n' + line + '\nEndoscopist: Synthetic MD\nSedation: propofol\n'
                    + COLO_PLAIN)
            with self.subTest(line=line):
                self.assertEqual(detect._gi4_head(text).own_dates, own)


class HeadLabelsAreSentTests(DateAssertions, SimpleTestCase):
    """(2): the head labels send their date where the installed reading sends none, and only there."""

    def test_a_head_label_with_a_read_date_is_sent(self):
        for label in HEAD_LABELS:
            for value in ('11/09/2026', 'November 9, 2026', '2026-11-09') + DECIDED[:6] + DECIDED[8:12]:
                text = HEAD + f'{label}: {value}\n' + COLO_PLAIN
                with self.subTest(label=label, value=value):
                    self.assert_document(text, DAY)
                    self.assertEqual(channel(text), [DAY, DAY, 'HELD', 'HELD', 'HELD', 'HELD', 'HELD'])
                    self.assertEqual(context.service_date_of(text), dt.date(2026, 11, 9))

    def test_the_label_stands_as_a_label(self):
        for line in ('Patient: Alex Synthetic    Exam date: 11/09/2026', 'Patient: Alex Synthetic | Exam date: 11/09/2026',
                     'Patient: Alex Synthetic\tDate of Operation: 11/09/2026', '- Exam date: 11/09/2026',
                     '## Date of Operation: 11/09/2026', 'Date of Operation (DOS): 11/09/2026',
                     'Exam date - 11/09/2026', 'Examination date = 11/09/2026'):
            with self.subTest(line=line):
                self.assert_document(HEAD + 'Colonoscopy Report\n' + line + '\n' + COLO_PLAIN, DAY)

    def test_a_lower_case_label_continuing_the_line_above_sends_nothing(self):
        # a label opening its line in lower case continues the line above (_label_words): "date of operation" is read
        # with the words of that line, as "date of procedure" is - not the note's own date ('unplaced'). The installed
        # twin then asks with its line as evidence; a head label never adds a question or a held answer, so it reads as
        # installed reads it (nothing: every answer taken). After a line that ends its sentence it sends as its twin does
        for value in ('11/09/2026', '9 November 2026', 'Monday, November 9, 2026'):
            for twin, new in (('date of procedure', 'date of operation'), ('procedure date', 'exam date'),
                              ('procedure date', 'examination date')):
                for lead in ('', 'Colonoscopy Report\n'):
                    a = HEAD + lead + f'{twin}: {value}\n' + COLO_PLAIN
                    b = HEAD + lead + f'{new}: {value}\n' + COLO_PLAIN
                    with self.subTest(twin=twin, value=value, lead=lead):
                        self.assertNotEqual(date_fact(a).origin, 'document')
                        self.assertEqual((date_fact(b).origin, date_fact(b).evidence), ('missing', ()))
                        self.assertEqual(channel(b), ['DATELESS'] + list(ANSWERS[1:]))
                a = HEAD + 'Colonoscopy Report.\n' + f'{twin}: {value}\n' + COLO_PLAIN
                b = HEAD + 'Colonoscopy Report.\n' + f'{new}: {value}\n' + COLO_PLAIN
                with self.subTest(twin=twin, value=value, lead='sentence'):
                    self.assert_document(a, DAY)
                    self.assert_document(b, DAY)
                    self.assertEqual(channel(b), channel(a))

    def test_a_member_answer_agrees_or_is_held_as_with_any_sent_date(self):
        text = HEAD + 'Exam date: 11/09/2026\n' + COLO_PLAIN
        self.assert_member_date(text, DAY)
        for answer in ('2026-11-10', FAR):
            self.assert_member_conflict(text, answer)

    def test_the_wide_reading_it_replaces_is_kept_beside_it(self):
        # where it sends, the head's "Exam date" is the document's date; the wide candidate of the same label still
        # stands beside it in the installed candidates (a label read once as the fact's own), and agrees
        text = HEAD + 'Colonoscopy Report\nExam date: 11/09/2026\n' + COLO_PLAIN
        lay = layout(text)
        self.assertTrue(any(c.wide for c in context._service_dates(text, lay)))
        extra = tuple(context._head_label_candidates(text, lay, context._Rows(text)))
        self.assertEqual([(c.value, c.reading, c.form, c.alone, c.installed, c.wide) for c in extra],
                         [(DAY, 'own', 'read', True, True, False)])
        self.assertTrue(any(not c.wide and c.value == DAY for c in context._service_dates(text, lay, extra)))
        for title in AROUND:  # none under a title written around a procedure, and none beyond the head
            other = HEAD + f'{title}\nExam date: 11/09/2026\n' + COLO_PLAIN
            self.assertEqual(context._head_label_candidates(other, layout(other), context._Rows(other)), [], title)
        body = HEAD + 'Colonoscopy Report\nIndication: screening.\nExam date: 11/09/2026\n' + COLO_PLAIN
        self.assertEqual(context._head_label_candidates(body, layout(body), context._Rows(body)), [])


class AsInstalledTests(DateAssertions, SimpleTestCase):
    """Everything here reads exactly as the installed release reads it (measured on design/base-cpt-studio): these pins
    pass on the installed tree too."""

    def test_in_the_body_a_head_label_reads_as_installed(self):
        colo = 'Colonoscopy Report\n' + COLO_PLAIN
        for label in HEAD_LABELS[:3]:
            for text, want in (
                    (HEAD + colo + f'Recall:\n{label}: 11/09/2029\n', None),
                    (HEAD + colo + f'IMAGING:\nCT abdomen and pelvis\n{label}: 10/01/2026\n', None),
                    (HEAD + f'Colonoscopy Report\nIndication: Surveillance after right hemicolectomy.\n{label}: '
                            '03/15/2025\n' + COLO_PLAIN, None),
                    (HEAD + 'Chief complaint: reflux.\nPlan\n' + f'{label}: 11/09/2026\n', None)):
                with self.subTest(label=label, text=text[-60:]):
                    fact = date_fact(text)
                    self.assertEqual((fact.origin, fact.value, fact.evidence), ('missing', want, ()))
                    self.assertEqual(channel(text), ['DATELESS'] + list(ANSWERS[1:]))  # every answer taken

    def test_inside_another_fields_sentence_it_reads_as_installed(self):
        for label in ('Date of operation', 'Exam date', 'Examination date'):
            text = (HEAD + 'Colonoscopy Report\nInterval events: Underwent right hemicolectomy. ' + f'{label}: '
                    '03/15/2025.\n' + COLO_PLAIN)
            with self.subTest(label=label):
                self.assertNotEqual(date_fact(text).origin, 'document')
                self.assertEqual(channel(text), ['DATELESS'] + list(ANSWERS[1:]))

    def test_under_a_title_written_around_a_procedure_it_reads_as_installed(self):
        for title in AROUND:
            for label in HEAD_LABELS[:3]:
                text = HEAD + f'{title}\n{label}: 11/20/2026\n' + COLO_PLAIN
                with self.subTest(title=title, label=label):
                    fact = date_fact(text)
                    self.assertEqual((fact.origin, fact.value), ('missing', None))
                    self.assertEqual(channel(text), ['DATELESS'] + list(ANSWERS[1:]))  # never sent, never asks
                    quoted = [' '.join(e.text.split()) for e in fact.evidence]
                    self.assertEqual(quoted, [f'{label}: 11/20/2026'] if label != 'Date of Operation' else [])

    def test_a_blank_unreadable_or_absent_value_reads_as_installed(self):
        for label in HEAD_LABELS[:3]:
            for value in ('11/09/26', '11-09-2026', '11.09.2026', 'TBD', '', 'pending', 'Tuesday, November 9, 2026',
                          '02/30/2026', '9 Nov 26'):
                alone = HEAD + f'{label}: {value}\n' + COLO_PLAIN
                beside = HEAD + f'Date of service: 11/09/2026\n{label}: {value}\n' + COLO_PLAIN
                with self.subTest(label=label, value=value):
                    fact = date_fact(alone)
                    self.assertEqual((fact.origin, fact.value, fact.evidence), ('missing', None, ()))
                    self.assertEqual(channel(alone), ['DATELESS'] + list(ANSWERS[1:]))  # no new held answer
                    self.assert_document(beside, DAY)  # no new conflict
                    self.assertEqual(channel(beside), [DAY, DAY, 'HELD', 'HELD', 'HELD', 'HELD', 'HELD'])

    def test_it_never_moves_a_date_installed_sends_nor_makes_a_question(self):
        for label, origin in (('Date of Operation', 'document'), ('Exam date', 'conflict')):
            # installed: "Date of Operation" is nothing beside the date of service; "Exam date" is a wide label whose
            # other day asks (rule (a)) - either way the head label adds nothing to what installed reads
            other = HEAD + f'Date of service: 11/09/2026\n{label}: 11/10/2026\n' + COLO_PLAIN
            with self.subTest(label=label):
                self.assertEqual(date_fact(other).origin, origin)
                self.assertEqual(channel(other)[1:3], [DAY, 'HELD'])
                same = HEAD + f'Date of service: 11/09/2026\n{label}: 11/09/2026\n' + COLO_PLAIN
                self.assert_document(same, DAY)
                # the fact installed sends is installed's, its evidence included: the head label joins nothing
                self.assertEqual([e.text for e in date_fact(same).evidence], ['Date of service: 11/09/2026'])
        post = HEAD + 'Post-operative visit\nDate of visit: 11/09/2026\nDate of Operation: 10/01/2026\n' + OFFICE_BODY
        self.assert_document(post, DAY)
        self.assertEqual(sends(post, '2026-10-01'), 'HELD')

    def test_where_installed_asks_with_evidence_it_still_asks(self):
        for lines in ('Date of service: 11/09/26\nExam date: 11/09/2026',  # an unread labelled date speaks
                      'Exam date: 11/09/2026 (rescheduled)',  # not alone in its field (rule N5)
                      'DOB: 01/01/1998\nExam date: 01/01/1998',  # the date of birth (BIRTH doubt)
                      'Exam date: 11/09/2026\nRe: Colonoscopy 11/10/2026',  # a subject line of another day
                      'Date of service: 10/14/2026 (pending)\nExam date: 10/19/2026'):
            text = HEAD + lines + '\n' + COLO_PLAIN
            with self.subTest(lines=lines):
                self.assertNotEqual(date_fact(text).origin, 'document')
                self.assertEqual(sends(text), 'DATELESS')

    def test_a_table_column_label_reads_as_installed_beside_a_head_label(self):
        # a date-of-service label heading a table column keeps its value cell (the installed reading); a head label
        # stated as a column head is no label standing in its field, and the column reads as installed
        for lead in ('', 'Exam date: 11/09/2026\n', 'Exam date | Endoscopist\n11/09/2026 | Dr. A. Synthetic\n'):
            text = (HEAD + 'Colonoscopy Report\n' + lead + 'Date of Service | Provider\n10/20/2026 | Dr. A. Synthetic\n'
                    + COLO_PLAIN)
            with self.subTest(lead=lead):
                fact = date_fact(text)
                self.assertNotEqual(fact.origin, 'document')
                self.assertEqual(sends(text), 'DATELESS')

    def test_other_labels_are_not_the_head_labels(self):
        for label in ('Operation date', 'Date/Time of Operation', 'Date of exam', 'Exam day', 'Date of surgery',
                      'Operation', 'Exam', 'Date', 'Admission date', 'Referral date', 'Date of birth'):
            text = HEAD + f'{label}: 11/09/2026\n' + COLO_PLAIN
            with self.subTest(label=label):
                self.assertNotEqual(date_fact(text).origin, 'document')
                self.assertEqual(sends(text), 'DATELESS')

    def test_previous_operations_above_a_date_of_service_read_as_installed(self):
        # the first design's occurrence noun "operation" is dropped: such a line above the label never holds it
        for line in ('Previous operations: None', 'Prior operation: none', 'Last operation: appendectomy',
                     'Planned operation: colonoscopy with polypectomy', 'Last operation:', 'Operation: deferred'):
            text = HEAD + f'Patient: Alex Synthetic\n{line}\nDate of service: 11/09/2026\n' + COLO_PLAIN
            with self.subTest(line=line):
                self.assert_document(text, DAY)
                self.assert_member_date(text, DAY)
        text = HEAD + 'Colonoscopy Report\nDate of service: 11/09/2026\nLast operation:\nProcedure date: 05/01/2019\n'
        self.assert_conflict(text + COLO_PLAIN, DAY, '2019-05-01')


class KeptContextVersionTests(SimpleTestCase):
    """The recall round (2026-11-08): a context recorded under gi-context@4 stays CURRENT (jobs.CONTEXT_VERSION's note).
    The final refutation showed what that keeps: a @4 context that asked where @5 reads the document's head date, then
    took a member's answer, sends that answer although @5 HOLDS it as contradicting the document (through the
    findings-stated reach 45385 read READY on it). Retiring @4 was refuted in its turn: the participant and peer stages
    send on an earlier context without remaking it, and answers, withdrawals, reconciliations and second reviews
    regressed on the encounters @4 read. The class is bounded by measurement - no live context @4 recorded reads
    differently under @5, a stop condition of the install's declaration - and by structure: once @5 is installed no
    context is recorded under @4."""

    TEXT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nEndoscopy Procedure Report\n'
            'Date of Operation: 11/05/2026\nEndoscopist: Synthetic Endoscopist, MD (fictional)\nProcedure: Colonoscopy\n'
            'Indication: Screening.\n\nFindings:\n  1. Terminal ileum normal.\n'
            '  2. A 6 mm polyp was removed by cold snare from the transverse colon (jar A).\n\nPlan:\n  1. Await pathology.\n'
            'Electronically signed by Synthetic Endoscopist, MD on 11/05/2026\n')

    def test_gi_context_4_stays_current(self):
        from studio import jobs
        self.assertEqual(jobs.CONTEXT_VERSION, 'gi-context@5')
        self.assertEqual(jobs.EARLIER_CONTEXT_VERSIONS, ('gi-context@1', 'gi-context@2', 'gi-context@3'))

    def test_the_current_reading_holds_the_member_date_a_kept_context_would_send(self):
        fact = context.extract_context(self.TEXT)['service_date']
        self.assertEqual((fact.origin, fact.value), ('document', '2026-11-05'))
        self.assertEqual(sends(self.TEXT), '2026-11-05')
        self.assertEqual(sends(self.TEXT, '2026-11-09'), 'HELD')  # a @4 context had taken it and would send it
