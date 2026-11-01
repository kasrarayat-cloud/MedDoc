"""GI round 4, package PD (date step 1): wide own-date labels and D2's worded date-of-service field only ever ASK or
NARROW, and are never sent (studio/gi/context.py: _service_dates, _pd_wide_candidates, _head_end, _pd_signoff_day,
_pd_around_procedure, _worded_field, _service_date_fact over the renamed, unchanged _installed_service_date_fact,
_QuotedSpan, merge_user_values, charge_date_problem). Declared before any code: tests/fixtures/gi4/declarations/pd.json,
and its dated amendment_20261101 before the Wave 1 repair's code.

(a) the installed reading sends X and a wide or worded own label states Y: asked, only X taken, every reader reads X;
    never under a title of a note written around a procedure; the note quotes the label's whole line (CTS-5);
(b) it already asks with evidence: unchanged;
(c) it asks with no evidence (Wave 1 repair, cycle 1; DS-1 to DS-4): the labels NARROW the answer to their date only
    when the author's own sign-off states that one day - a line that signs, authenticates, finalizes or attests and
    names the performer or author a head field names (the declaration's second entry), never a co-signature or a
    transcription line - every closing-role day after the head agrees, the closing region is the note's own (never the
    head of a short document, no addendum, no copied-text announcement, not under another occurrence's heading), the
    note is not around a procedure under the broadened detection and states no call or message (the third entry),
    there is one value, and the date stands alone on a clean line. Otherwise the lines are only QUOTED and every member
    date is taken exactly as installed takes it.

The integration of Wave 1 repair cycle 1 (pd.json amendment_20261101_integration, declared before its code): a
procedure report's own head (detect.todays_procedure_report) whose own-date field gives exactly one date holds a
member's answer of any other day (StrongHeadHoldTests). The rule (c) cases below are read on report(), whose head is
no such head (its sedation field is denied), so they read rule (c) alone, as they were written to.

No database (SimpleTestCase): this module is the H6 detector of every PD guard; each guard's killing test says so.
Every document is synthetic.
"""
import datetime as dt

from django.test import SimpleTestCase

from ops.gi4 import regression
from studio import jobs
from studio.gi import context
from studio.gi.sections import layout
from studio.providers.corti import ADAPTER_VERSION, build_coding_request
from studio.types import Span, to_jsonable
from studio.validation import checks

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DOCS = regression.load_fixtures()
FAR = '1998-01-01'
ENDO = 'Wren Halvorsen-Ode, MD (fictional)'
SIGNED = f'Electronically signed by {ENDO}, 10/21/2026 10:05\n'
BODY = ''.join(f'Segment {i}: normal mucosa.\n' for i in range(5))


def report(title='Colonoscopy Report', label='Date performed: 10/21/2026', head_extra='', body_extra='', closing=SIGNED,
           tail=''):
    """A procedure report whose head names its endoscopist and states a wide own-date label: with the defaults its own
    sign-off states the label's day, so every guard of rule (c) passes and the label narrows. Its sedation field is
    denied, so its head is no strong head and the integration's hold never reads it (StrongHeadHoldTests)."""
    return (B + title + '\n' + f'Endoscopist: {ENDO}\n' + label + '\n' + head_extra + 'Sedation: none\n\n'
            'Findings\nThe colonoscope was advanced to the cecum. No polyps were found.\n' + body_extra
            + 'Impression\nNormal colonoscopy.\n' + closing + tail)


def fact(text):
    return context.extract_context(text)['service_date']


def taken(text, answer):
    """Whether a member's answer is taken (origin 'user') rather than held."""
    return context.merge_user_values(context.extract_context(text), {'service_date': answer})['service_date'].origin \
        == 'user'


def sends(text, answer=None):
    """What the request then carries: an ISO date, 'DATELESS' or 'HELD' (the member-date hold)."""
    merged = jobs._merged_facts(context.extract_context(text), {'service_date': answer} if answer else {})
    if context.is_member_conflict(merged['service_date']):
        return 'HELD'
    day = jobs._service_date_of(merged)
    return day.isoformat() if day else 'DATELESS'


def evidence(f):
    return [' '.join(e.text.split()) for e in f.evidence]


def narrows(text, day='2026-10-21', other='2026-10-30'):
    """Whether the document's wide label narrows the answer to ``day`` (``other`` held, ``day`` taken)."""
    return taken(text, day) and not taken(text, other)


def quote_only(text):
    """Whether rule (c) only quotes: origin missing, every evidence span a quoted line, the quote-only note."""
    f = fact(text)
    return (f.origin == 'missing' and bool(f.evidence) and all(isinstance(e, context._QuotedSpan) for e in f.evidence)
            and f.note == context.WIDE_DATE_QUOTE_NOTE)


def every_answer_taken(test, text, answers):
    """As installed with no evidence: nothing is sent before an answer, and every answer is taken and sent."""
    test.assertEqual(sends(text), 'DATELESS', text)
    for answer in answers:
        test.assertTrue(taken(text, answer), (answer, text))
        test.assertEqual(sends(text, answer), answer, (answer, text))


class RegressionDocumentTests(SimpleTestCase):
    """The plan's PD table, on the texts the service read (tests/fixtures/gi4/regression/), as amended 2026-11-01."""

    EXPECTED = {  # doc: (evidence, accepted, held) - the narrowing kept: each own sign-off states the label's day
        'h4-01': (['Date seen: 10/26/2026'], ['2026-10-26'],
                  ['2026-10-14', '2026-10-25', '2026-10-27', '2026-11-02', '2026-11-23', '2026-12-14', FAR]),
        'h4-02': (['Case date: 2026-10-21'], ['2026-10-21'], ['2026-10-20', '2026-10-22', '2026-11-18', FAR]),
        'h4-04': (['Date performed: October 19, 2026'], ['2026-10-19'],
                  ['2026-09-28', '2026-10-18', '2026-10-20', '2026-11-16', FAR]),
        'h4-06': (['Day of procedure: Oct 27, 2026'], ['2026-10-27'],  # attested by the colonoscopist its head names
                  ['2025-09-30', '2026-10-26', '2026-10-28', '2026-11-24', FAR]),
    }

    def test_the_narrowed_documents_take_only_their_labels_dates(self):
        for doc_id, (quoted, accepted, held) in self.EXPECTED.items():
            text = DOCS[doc_id]['text']
            f = fact(text)
            self.assertEqual((f.origin, f.value, f.note), ('missing', None, context.WIDE_DATE_NOTE), doc_id)
            self.assertEqual(evidence(f), quoted, doc_id)
            self.assertFalse(any(isinstance(e, context._QuotedSpan) for e in f.evidence), doc_id)
            for answer in accepted:
                self.assertTrue(taken(text, answer), (doc_id, answer))
                self.assertEqual(sends(text, answer), answer, (doc_id, answer))
            for answer in held:
                self.assertFalse(taken(text, answer), (doc_id, answer))
                self.assertEqual(sends(text, answer), 'HELD', (doc_id, answer))
            self.assertEqual(sends(text), 'DATELESS', doc_id)  # nothing is sent before a member's answer

    def test_h4_03_quotes_its_two_values_and_takes_only_its_heads_date(self):  # amended twice on 2026-11-01
        # rules (1) and (5): its two values narrow nothing, so rule (c) only quotes them; the integration's STRONG-HEAD
        # HOLD (amendment_20261101_integration): its head is a procedure report's own, 'Exam date: 10/06/2026' its
        # one date, so a member's answer of any other day is held (StrongHeadHoldTests)
        text = DOCS['h4-03']['text']
        f = fact(text)
        self.assertEqual((f.origin, f.value), ('missing', None))
        self.assertTrue(all(isinstance(e, context._QuotedSpan) for e in f.evidence))
        self.assertEqual(evidence(f), ['Exam date: 10/06/2026', 'Service date logged for this case: 10/08/2026'])
        self.assertEqual(sends(text), 'DATELESS')
        self.assertTrue(taken(text, '2026-10-06'))
        for answer in ('2026-10-08', '2026-10-09', '2026-10-05', '2026-10-07', FAR):
            self.assertFalse(taken(text, answer), answer)
        state = checks.service_date_state(context.merge_user_values(context.extract_context(text), {}), None)
        self.assertEqual(checks._date_problem(state), 'No usable date of service was read: the document states “Exam '
                                                      'date: 10/06/2026”, which is not read as one')

    def test_h4_05_h2_08_and_h2_10_read_as_installed(self):
        f = fact(DOCS['h4-05']['text'])
        self.assertEqual((f.origin, f.value, evidence(f)), ('document', '2026-10-15', ['Service date: 2026-10-15']))
        f = fact(DOCS['h2-10']['text'])
        self.assertEqual((f.origin, f.value), ('document', '2026-10-23'))
        text = DOCS['h2-08']['text']
        f = fact(text)
        self.assertEqual(context.charge_date_own(f), '2026-10-05')  # the narrow release's question, unchanged
        self.assertTrue(context.charge_date_problem(f).startswith("The lines from “Charge information”"))
        self.assertTrue(taken(text, '2026-10-05'))
        self.assertFalse(taken(text, '2026-10-06'))

    def test_every_stored_request_rebuilds_byte_identically(self):
        for doc_id, doc in DOCS.items():
            for run in doc['runs']:
                if not run['request_sha256']:
                    continue
                answer = run['service_date']
                if answer is not None:
                    self.assertEqual(sends(doc['text'], answer), answer, (doc_id, answer))
                day = dt.date.fromisoformat(answer) if answer else None
                if answer is None and doc_id not in ('h4-05', 'h2-10'):
                    self.assertEqual(sends(doc['text']), 'DATELESS', doc_id)
                built = build_coding_request('corti', ADAPTER_VERSION, doc['text'], day, 10 ** 7).canonical_sha256
                self.assertEqual(built, run['request_sha256'], (doc_id, answer))


class InstalledSendsXTests(SimpleTestCase):
    """Rule (a): the installed reading sends X and a wide or worded own label states Y."""

    X_Y = (B + 'Colonoscopy Report\nDate of service: 10/18/2026\nDate performed: 10/19/2026\nThe colonoscope was advanced '
           'to the cecum.\nSigned: Synthetic MD, 10/19/2026\n')

    def test_asked_and_only_x_is_taken(self):  # kills pd-rule-a-readers-read-x (with the next test)
        f = fact(self.X_Y)
        self.assertEqual((f.origin, f.value), ('conflict', None))
        self.assertEqual(evidence(f), ['Date of service: 10/18/2026'])
        self.assertEqual(sends(self.X_Y), 'DATELESS')
        self.assertTrue(taken(self.X_Y, '2026-10-18'))
        for answer in ('2026-10-19', FAR, '2026-10-17'):
            self.assertEqual(sends(self.X_Y, answer), 'HELD', answer)

    def test_every_reader_reads_x_while_it_is_asked(self):  # kills pd-rule-a-readers-read-x, pd-rule-a-only-x
        f = fact(self.X_Y)
        self.assertEqual(context.charge_date_own(f), '2026-10-18')
        self.assertEqual(context.charge_question_day(self.X_Y), dt.date(2026, 10, 18))
        self.assertEqual(context.service_date_of(self.X_Y), dt.date(2026, 10, 18))
        problem = context.charge_date_problem(f)
        self.assertEqual(problem, 'The document also states “Date performed: 10/19/2026”, while 2026-10-18 is '
                                  'read from “Date of service: 10/18/2026”')
        self.assertTrue(f.note.startswith(problem))

    def test_the_note_quotes_whole_lines(self):  # CTS-5; kills pd-rule-a-whole-line
        rows = {  # the refuter's PD-02, PD-03, PD-04, PD-06 and PD-08 head lines: the whole line is quoted, once
            'Date performed: 10/21/2026 (pathology)': '“Date performed: 10/21/2026 (pathology)”',
            'Date performed: 10/21/2026 by Mercy GI': '“Date performed: 10/21/2026 by Mercy GI”',
            'Case date: 10/12/2026 (booked)': '“Case date: 10/12/2026 (booked)”',
            'Date seen: 10/12/2026 in clinic; procedure today': '“Date seen: 10/12/2026 in clinic; procedure today”',
            'Day of procedure: 10/19/2026    Date seen: 10/12/2026 (pre-op clinic)':
                '“Day of procedure: 10/19/2026 Date seen: 10/12/2026 (pre-op clinic)”'}
        for line, quoted in rows.items():
            text = (B + 'Colonoscopy Report\nDate of service: 10/19/2026\n' + line + '\nEndoscopist: Synthetic MD\n'
                    'Sedation: propofol by CRNA\nFindings: The colonoscope was advanced to the cecum. No polyps were '
                    'found.\nImpression: Normal colonoscopy.\n')
            f = fact(text)
            self.assertEqual(f.origin, 'conflict', line)
            self.assertEqual(context.charge_date_problem(f), f'The document also states {quoted}, while 2026-10-19 is '
                                                             'read from “Date of service: 10/19/2026”', line)
            self.assertEqual(context.charge_date_own(f), '2026-10-19', line)  # the note's own date, whatever is quoted
            self.assertTrue(taken(text, '2026-10-19'), line)
            self.assertFalse(taken(text, '2026-10-12'), line)

    def test_a_long_line_is_quoted_as_a_window_with_its_cuts_marked(self):
        line = ('Facility: ' + 'Riverside Endoscopy Suite Two ' * 6 + '   Date seen: 10/12/2026    Room: '
                + 'Procedure Room Four ' * 6)  # a flattened header row longer than the quote limit
        text = B + 'Colonoscopy Report\nDate of service: 10/19/2026\n' + line + '\nFindings: normal.\n'
        problem = context.charge_date_problem(fact(text))
        quoted = problem[len('The document also states '):problem.index(', while ')]
        self.assertTrue(quoted.startswith('“…') and quoted.endswith('…”'), quoted)
        self.assertIn('Date seen: 10/12/2026', quoted)
        self.assertLessEqual(len(quoted), 2 * context._PD_QUOTE_WINDOW + 30)

    def test_never_under_a_title_of_a_note_written_around_a_procedure(self):  # kills pd-rule-a-asks-around
        text = (B + 'Pre-procedure telephone call\nDate of service: 10/30/2026\nDay of procedure: 11/04/2026\nPatient '
                'reached; prep reviewed.\nSigned: Synthetic Nurse, RN (fictional), 10/30/2026\n')
        f = fact(text)
        self.assertEqual((f.origin, f.value), ('document', '2026-10-30'))  # as installed: the planned day asks nothing
        self.assertEqual(sends(text), '2026-10-30')

    def test_a_worded_field_asks_the_same_way(self):
        text = (B + 'Variceal Banding Session\nDate of service: 10/06/2026\nProceduralist: Synthetic MD\n\nConclusions\n'
                'Six bands placed.\nCase Room Ledger\nService date logged for this case: 10/08/2026\n')
        f = fact(text)
        self.assertEqual(context.charge_date_own(f), '2026-10-06')
        self.assertIn('“Service date logged for this case: 10/08/2026”', f.note)
        self.assertTrue(taken(text, '2026-10-06'))
        self.assertFalse(taken(text, '2026-10-08'))

    def test_the_same_day_asks_nothing(self):
        text = B + 'Colonoscopy Report\nDate of service: 10/19/2026\nDate performed: 10/19/2026\nFindings: normal.\n'
        f = fact(text)
        self.assertEqual((f.origin, f.value), ('document', '2026-10-19'))
        self.assertEqual(sends(text), '2026-10-19')

    def test_the_relabelled_ledger_keeps_installeds_date_as_every_readers_date(self):  # the judge's F7 (53(b)/54)
        # amended 2026-11-01 by the integration's STRONG-HEAD HOLD (amendment_20261101_integration): rule (a) still
        # asks and keeps installed's 2026-10-08 as every reader's date, but the head's own date is 2026-10-06, so a
        # member's 2026-10-08 is held too and no answer is taken (TAKEN -> HELD; an addendum settles it)
        text = DOCS['h4-03']['text'].replace('Service date logged for this case:', 'Service date:')
        self.assertEqual(sends(text), 'DATELESS')
        self.assertEqual(context.charge_date_own(fact(text)), '2026-10-08')
        self.assertEqual(context.service_date_of(text), dt.date(2026, 10, 8))
        self.assertFalse(taken(text, '2026-10-08'))
        self.assertFalse(taken(text, '2026-10-06'))


class InstalledAsksWithEvidenceTests(SimpleTestCase):
    """Rule (b): where the installed reading already asks with evidence, nothing changes."""

    def test_unchanged(self):
        for text in (B + 'Colonoscopy Report\nDate of service: 14 Oct 2026\nDate performed: 10/19/2026\nFindings: x.\n',
                     B + 'Colonoscopy Report\nDate of service: 10/14/2026 (pending)\nExam date: 10/19/2026\nFindings: x.\n'):
            cands = context._service_dates(text, layout(text))
            self.assertTrue(any(c.wide for c in cands), text)
            plain = tuple(c for c in cands if not c.wide)
            self.assertEqual(context._service_date_fact(cands), context._installed_service_date_fact(plain), text)
            self.assertTrue(context._installed_service_date_fact(plain).evidence, text)


class NarrowingTests(SimpleTestCase):
    """Rule (c) narrows: the author's own sign-off states the label's day and every other guard passes."""

    def test_the_label_narrows_to_its_day_with_its_whole_line_as_evidence(self):
        text = report()
        f = fact(text)
        self.assertEqual((f.origin, f.value, f.note), ('missing', None, context.WIDE_DATE_NOTE))
        self.assertEqual([(e.start, e.end, e.text) for e in f.evidence],
                         [(text.index('Date performed'), text.index('Date performed') + 26, 'Date performed: 10/21/2026')])
        self.assertTrue(narrows(text))
        self.assertEqual(sends(text), 'DATELESS')
        self.assertEqual(sends(text, '2026-10-21'), '2026-10-21')
        self.assertEqual(sends(text, FAR), 'HELD')

    def test_an_attestation_by_the_performer_the_head_names_is_the_authors_own_sign_off(self):
        self.assertTrue(narrows(report(closing=f'Attested: {ENDO}, 10/21/2026 10:05\n')))  # h4-06's shape
        self.assertEqual(context._pd_performers(report()), (('Wren', 'Halvorsen-Ode'),))

    def test_a_dictation_word_beside_an_own_verb_does_not_disqualify_it(self):
        self.assertTrue(narrows(report(closing=f'Dictated and electronically signed by {ENDO}, 10/21/2026 10:05\n')))

    def test_a_worded_field_narrows_the_same_way(self):
        text = report(title='Banding Session', label='Service date logged for this case: 10/21/2026')
        self.assertEqual(evidence(fact(text)), ['Service date logged for this case: 10/21/2026'])
        self.assertTrue(narrows(text))

    def test_a_narrowed_wide_label_is_never_sent(self):  # kills pd-wide-never-own
        for text in (report(), report(title='Banding Session', label='Service date logged for this case: 10/21/2026'),
                     DOCS['h4-01']['text'], DOCS['h4-06']['text']):
            self.assertNotEqual(fact(text).origin, 'document', text[:120])
            self.assertEqual(sends(text), 'DATELESS', text[:120])
            self.assertIsNone(context.service_date_of(text), text[:120])  # no reader reads it as the date either


class QuoteOnlyTests(SimpleTestCase):
    """Rule (c) only quotes: the lines are evidence the question quotes, and limit no answer."""

    UNCORROBORATED = (B + 'Colonoscopy\nDay of procedure: 11/04/2026\nPrep reviewed.\nSigned: Synthetic Nurse, RN '
                          '(fictional), 10/30/2026\n')

    def test_an_uncorroborated_value_is_quoted_and_every_answer_taken(self):  # kills pd-quoted-limits-nothing
        text = self.UNCORROBORATED
        self.assertTrue(quote_only(text))
        self.assertEqual(evidence(fact(text)), ['Day of procedure: 11/04/2026'])
        every_answer_taken(self, text, ['2026-10-30', '2026-11-04', FAR])  # the note's real day is never refused

    def test_the_question_quotes_the_line(self):
        state = checks.service_date_state(context.merge_user_values(context.extract_context(self.UNCORROBORATED), {}),
                                          None)
        self.assertEqual(checks._date_problem(state), 'No usable date of service was read: the document states “Day of '
                                                      'procedure: 11/04/2026”, which is not read as one')

    def test_the_quoted_evidence_is_the_whole_line(self):  # kills pd-quote-only-whole-line
        text = (B + 'Endoscopy Appointment\nCase date: 11/04/2026        Transcribed by: M. Clerk\nPatient: Alex '
                'Synthetic\nProcedure: EGD with possible dilation\nArrival 06:30. Driver required.\n')
        self.assertTrue(quote_only(text))
        self.assertEqual([e.text for e in fact(text).evidence], ['Case date: 11/04/2026        Transcribed by: M. Clerk'])

    def test_many_labels_on_one_long_line_are_quoted_once(self):
        text = (B + 'Colonoscopy Report\n' + '    '.join(f'Exam date: 10/{d:02d}/2026' for d in range(1, 21))
                + '\nFindings: normal.\n')
        self.assertEqual(sum(1 for c in context._service_dates(text, layout(text)) if c.wide), 20)
        self.assertTrue(quote_only(text))
        [span] = fact(text).evidence  # one window of the line, never one per label
        self.assertLessEqual(len(span.text), 2 * context._PD_QUOTE_WINDOW + 30)
        every_answer_taken(self, text, ['2026-10-01', '2026-10-30', FAR])

    def test_a_quoted_span_reads_no_date_and_equals_its_plain_span(self):
        quoted = context._QuotedSpan(3, 31, 'Day of procedure: 11/04/2026')
        self.assertIsNone(context._date_readings((quoted,)))
        self.assertEqual(quoted, Span(3, 31, 'Day of procedure: 11/04/2026'))
        self.assertEqual(hash(quoted), hash(Span(3, 31, 'Day of procedure: 11/04/2026')))
        stored = to_jsonable(fact(self.UNCORROBORATED))
        self.assertEqual(stored['evidence'][0]['text'], 'Day of procedure: 11/04/2026')  # plain JSON as stored
        self.assertFalse(context._limits_answers(context.Fact('service_date', None, 'missing', (quoted,), '')))
        self.assertTrue(context._limits_answers(context.Fact('service_date', None, 'missing',
                                                             (quoted, Span(0, 3, 'x')), '')))


class AuthorsOwnSignOffTests(SimpleTestCase):
    """DS-1: only the author's own sign-off of the label's day narrows, and every closing-role day must agree."""

    def test_the_refuters_documents_take_every_answer(self):  # DS-1: E3b, B3, C2 exactly as the refuter wrote them
        e3b = (B + 'Colonoscopy\nDay of procedure: 11/04/2026\nPrep reviewed.\nSigned: Synthetic Nurse, RN (fictional), '
               '10/30/2026\nCo-signed: Synthetic MD, 11/04/2026\n')
        b3 = ('GI Consultation\nPatient: Alex Synthetic\nDay of procedure: 11/04/2026\nChief complaint: rectal bleeding.\n'
              'HPI: 62-year-old with intermittent hematochezia for two months.\nExam: Abdomen soft, nontender.\nAssessment: '
              'hematochezia; colonoscopy indicated.\nElectronically signed by A. Doctor MD, 10/28/2026 16:40\nAttested by A. '
              'Doctor MD, 11/04/2026 07:02\n')
        c2 = ('GI Clinic Note\nPatient: Alex Synthetic\nChief complaint: reflux.\nAssessment: GERD without esophagitis.\n'
              'Electronically signed by A. Doctor MD, 10/12/2026 16:20\n\nAddendum\nDate of service for this addendum: '
              '10/20/2026\nPathology reviewed with the patient.\nElectronically signed by A. Doctor MD, 10/20/2026 09:00\n')
        for text, answers in ((e3b, ['2026-10-30', '2026-11-04', FAR]), (b3, ['2026-10-28', '2026-11-04', FAR]),
                              (c2, ['2026-10-12', '2026-10-20', FAR])):
            self.assertTrue(quote_only(text), text)
            every_answer_taken(self, text, answers)

    def test_a_co_signature_or_a_transcription_line_is_no_sign_off_of_the_author(self):  # kills pd-own-not-cosign
        # by the performer the head names too (the second entry's guard alone would refuse anyone else): his
        # co-signature of someone else's note, or a transcription line, is never the author's own sign-off
        for closing in (f'Co signed by {ENDO}, 10/21/2026 10:05\n', f'Transcribed and signed by {ENDO}, 10/21/2026 10:05\n',
                        'Co signed by Ilse Marchetti, MD (fictional), 10/21/2026 10:05\n',
                        'Countersigned: Ilse Marchetti, MD (fictional), 10/21/2026 10:05\n',
                        'Transcribed and signed by Synthetic Clerk, 10/21/2026 10:05\n'):
            text = report(closing=closing)
            self.assertTrue(quote_only(text), closing)
            self.assertTrue(taken(text, '2026-10-30'), closing)

    def test_an_attestation_by_anyone_the_head_does_not_name_is_no_sign_off(self):  # kills pd-attest-performer
        text = report(closing='Attested by Ilse Marchetti, MD (fictional), 10/21/2026 10:05\n')
        self.assertTrue(quote_only(text))
        self.assertTrue(taken(text, '2026-10-30'))
        self.assertTrue(narrows(report(closing=f'Attested: {ENDO}, 10/21/2026 10:05\n')))  # the performer's own

    def test_a_dictation_line_alone_is_no_sign_off(self):  # kills pd-dictated-only
        text = report(closing=f'Dictated by {ENDO}, 10/21/2026 10:05\n')
        self.assertTrue(quote_only(text))
        self.assertTrue(taken(text, '2026-10-30'))

    def test_a_consent_order_request_booking_or_call_line_is_no_sign_off(self):  # kills pd-not-closing-words
        # each also by the performer the head names, so only the line's own words refuse it
        for closing in (f'Orders signed by {ENDO}, 10/21/2026 10:05\n',
                        f'Consent signed by the patient with {ENDO}, 10/21/2026 10:05\n',
                        f'Booking finalized by {ENDO}, 10/21/2026 10:05\n',
                        f'Scheduling request signed by {ENDO}, 10/21/2026 10:05\n',
                        'Consent signed by the patient 10/21/2026\n', 'Orders signed by Synthetic MD 10/21/2026\n',
                        'Request finalized by Synthetic Clerk 10/21/2026\n', 'Call note signed 10/21/2026\n'):
            text = report(body_extra=BODY, closing=closing)  # the closing line beyond the head's first lines
            self.assertTrue(quote_only(text), closing)
            self.assertTrue(taken(text, '2026-10-30'), closing)

    def test_every_closing_role_day_after_the_head_must_agree(self):  # kills pd-closing-days-agree
        for extra in ('Co-signed: Ilse Marchetti, MD (fictional), 10/22/2026 08:00\n',
                      'Dictated: 10/20/2026\n', 'Attested by Ilse Marchetti, MD (fictional), 10/23/2026\n'):
            text = report(closing=SIGNED + extra)
            self.assertTrue(quote_only(text), extra)
            self.assertTrue(taken(text, '2026-10-30'), extra)
        same_day = report(closing=SIGNED + 'Co-signed: Ilse Marchetti, MD (fictional), 10/21/2026 11:00\n')
        self.assertTrue(narrows(same_day))  # a co-signature of the same day contradicts nothing

    def test_a_date_of_birth_on_a_closing_line_is_never_its_day(self):
        text = report(closing=f'Electronically signed by {ENDO} (DOB 01/01/1970), 10/21/2026 10:05\n')
        self.assertTrue(narrows(text))


class SignedByThePerformerTests(SimpleTestCase):
    """The declaration's second entry: the author's own sign-off NAMES the performer or author a head field names - the
    positive evidence of whose signature a line is - for every sign-off verb alike."""

    COPIED = ('GI Clinic Note\nSeen by: A. Doctor MD\nPatient: Alex Synthetic\nDate performed: 09/03/2026\nChief '
              'complaint: follow-up after a colonoscopy elsewhere.\nAssessment: one adenoma removed; surveillance in '
              'five years.\nSt. Mary Endoscopy\nThe colonoscope was advanced to the cecum. A 10 mm polyp was removed '
              'with a hot snare.\nElectronically signed by B. Other MD, 09/03/2026 10:15\n')

    def test_a_sign_off_by_anyone_the_head_does_not_name_narrows_nothing(self):  # kills pd-signoff-names-performer
        nobody = report().replace(f'Endoscopist: {ENDO}\n', '')  # the same report, its head naming no performer
        for text, answers in ((report(closing='Electronically signed by Ilse Marchetti, MD (fictional), 10/21/2026 '
                                              '10:05\n'), ['2026-10-21', '2026-10-30', FAR]),
                              (self.COPIED, ['2026-10-12', '2026-09-03', FAR]),  # a copied report, no announcement
                              (nobody, ['2026-10-21', '2026-10-30', FAR])):
            self.assertTrue(quote_only(text), text)
            every_answer_taken(self, text, answers)
        self.assertTrue(narrows(report()))

    def test_the_surname_ends_the_signers_name(self):  # kills pd-performer-whole-name
        head = report().replace(f'Endoscopist: {ENDO}', 'Endoscopist: Synthetic MD')
        nurse = head.replace(SIGNED, 'Signed: Synthetic Nurse, RN (fictional), 10/21/2026 10:05\n')
        self.assertTrue(quote_only(nurse))
        self.assertTrue(taken(nurse, '2026-10-30'))
        for closing in ('Signed: Synthetic MD, 10/21/2026 10:05\n', 'Signed: Synthetic, MD, 10/21/2026\n',
                        'Electronically signed by Synthetic Jr., 10/21/2026\n'):
            self.assertTrue(narrows(head.replace(SIGNED, closing)), closing)

    def test_a_first_name_before_the_surname_agrees(self):  # kills pd-performer-first-name
        other = report(closing='Electronically signed by Ilse Halvorsen-Ode, MD (fictional), 10/21/2026 10:05\n')
        self.assertTrue(quote_only(other))
        self.assertTrue(taken(other, '2026-10-30'))
        for closing in ('Electronically signed by W. Halvorsen-Ode, MD, 10/21/2026 10:05\n',
                        'Signed: Dr. Halvorsen-Ode, 10/21/2026\n', 'Signed by Wren J. Halvorsen-Ode, 10/21/2026\n',
                        'ELECTRONICALLY SIGNED BY WREN HALVORSEN-ODE, MD, 10/21/2026\n',
                        'Report finalized by Halvorsen-Ode 10/21/2026\n'):
            self.assertTrue(narrows(report(closing=closing)), closing)

    def test_an_attestation_signs_only_as_the_closings_sole_line(self):  # kills pd-attest-sole-line (the fourth entry)
        for closing in (f'Electronically signed by Ilse Marchetti, MD (fictional)\nAttested by {ENDO}, 10/21/2026 10:05\n',
                        f'Dictated by Ilse Marchetti, MD (fictional)\nAttested: {ENDO}, 10/21/2026 10:05\n'):
            text = report(closing=closing)  # a fellow's undated line, then the head performer's supervising attestation
            self.assertTrue(quote_only(text), closing)
            every_answer_taken(self, text, ['2026-10-21', '2026-10-30', FAR])
        self.assertTrue(narrows(report(closing=f'Attested: {ENDO}, 10/21/2026 10:05\n')))  # h4-06's: its only line
        self.assertTrue(narrows(report(closing=SIGNED + f'Attested: {ENDO}, 10/21/2026 10:06\n')))  # his own signature

    def test_a_sign_off_line_longer_than_the_quote_limit_is_none(self):  # kills pd-signoff-short-line
        line = f'Electronically signed by {ENDO}, 10/21/2026 10:05' + '; workstation Endo Suite Four session' * 6
        self.assertGreater(len(line), context._PD_QUOTE_CHARS)
        text = report(closing=line + '\n')
        self.assertTrue(quote_only(text))
        self.assertTrue(taken(text, '2026-10-30'))

    def test_the_head_fields_names(self):
        text = (B + 'Colonoscopy Report\nEndoscopist: Dr. Jane Smith    Sedation: propofol\nAttending: Smith, John MD\n'
                'Provider: Synthetic MD (fictional)\nReferring physician: Dr. Oak\nDate performed: 10/21/2026\n')
        self.assertEqual(context._pd_performers(text), (('Jane', 'Smith'), ('', 'Smith'), ('', 'Synthetic')))
        self.assertTrue(context._pd_signed_by('Signed: J. Smith, 10/21/2026', (('Jane', 'Smith'),)))
        self.assertFalse(context._pd_signed_by('Signed: Raj Smith, 10/21/2026', (('Jane', 'Smith'),)))
        self.assertFalse(context._pd_signed_by('Signed: Smithson, 10/21/2026', (('', 'Smith'),)))
        self.assertFalse(context._pd_signed_by('Signed: 10/21/2026', ()))


class ProcedureLabelTests(SimpleTestCase):
    """The declaration's fifth entry: a label naming a procedure's occurrence narrows only in a procedure's own report."""

    CONSULT = ('GI Consultation\nSeen by: A. Doctor MD\n{label}\nChief complaint: rectal bleeding.\nAssessment: '
               'hematochezia; colonoscopy scheduled.\nElectronically signed by A. Doctor MD, 11/04/2026 07:30\n')

    def test_a_procedure_label_outside_a_procedure_report(self):  # kills pd-procedure-label-head
        for label in ('Day of procedure: 11/04/2026', 'Case date: 11/04/2026', 'Date performed: 11/04/2026',
                      'Procedure day: 11/04/2026'):
            text = self.CONSULT.format(label=label)  # signed late, on the planned procedure's day (R8)
            self.assertTrue(quote_only(text), label)
            every_answer_taken(self, text, ['2026-10-28', '2026-11-04', FAR])
        self.assertTrue(narrows(self.CONSULT.format(label='Date seen: 11/04/2026'), '2026-11-04', '2026-10-28'))
        for label in ('Day of procedure: 10/21/2026', 'Case date: 10/21/2026', 'Date performed: 10/21/2026'):
            self.assertTrue(narrows(report(label=label)), label)  # the procedure's own report: its head's fields


class AroundProcedureTests(SimpleTestCase):
    """DS-2: a note written around a procedure, under the broadened detection, narrows nothing; its labels are quoted."""

    def test_the_judges_f7_call_and_booking_shapes(self):
        for text, own_day in (
                (B + 'Pre-procedure telephone call\nDay of procedure: 11/04/2026\nPatient reached; prep reviewed.\n'
                     'Signed: Synthetic Nurse, RN (fictional), Oct 30, 2026\n', '2026-10-30'),
                (B + 'Pre-procedure call note\nDay of procedure: 11/04/2026\nCall placed on 10/30/2026.\nSigned: '
                     'Synthetic Nurse, RN (fictional), 11/04/2026 07:10\n', '2026-10-30'),
                (B + 'Endoscopy booking\nCase date: 2026-11-04\nColonoscopy booked for the morning list.\n', '2026-10-29'),
                (B + 'Endoscopy booking\nCase date: 2026-11-04\nColonoscopy booked for the morning list.\nAttested: '
                     'Synthetic Scheduler, 2026-11-04\n', '2026-10-29')):
            self.assertTrue(quote_only(text), text)
            self.assertEqual(sends(text), 'DATELESS', text)  # the planned day is never sent by the document
            self.assertTrue(taken(text, own_day), text)  # the note's own day is never refused

    def test_the_refuters_documents_take_every_answer(self):  # DS-2: E1d, E2b, E4, A1-A3, A5-A7, B1, B2, B6, B7
        signed = 'Electronically signed by J. Nurse RN, 11/02/2026 15:42\nAttested by A. Doctor MD, 11/04/2026 07:05\n'
        rows = (
            B + 'Endoscopy appointment\nCase date: 2026-11-04\nColonoscopy booked for the morning list.\nAttested: '
                'Synthetic MD, 2026-11-04\n',
            B + 'Nursing note\nNote type: Telephone\nDay of procedure: 11/04/2026\nCall placed on 10/30/2026.\nSigned: '
                'Synthetic Nurse, RN (fictional), 11/04/2026 07:10\n',
            B + 'Colonoscopy appointment reminder\nDay of procedure: 11/04/2026\nSigned: Synthetic MD, 11/04/2026\n',
            'GI Nurse Note\nNote type: Telephone\nPatient: Alex Synthetic    MRN: 00012345\nDay of procedure: 11/04/2026\n'
            'Procedure: Colonoscopy\nSpoke with patient by phone today. Reviewed split-dose prep, clear liquids the day '
            'before, nothing by mouth after midnight. Questions answered.\n' + signed,
            'Endoscopy Appointment\nPatient: Alex Synthetic\nCase date: 11/04/2026\nProcedure: EGD with possible dilation\n'
            'Arrival 06:30. Driver required. Hold apixaban two days before.\nEntered by front desk 10/20/2026\nAttested by '
            'A. Doctor MD, 11/04/2026 06:55\n',
            'Pre-colonoscopy Nursing Assessment\nPatient: Alex Synthetic\nDay of procedure: 11/04/2026\nAllergies '
            'reviewed. Medication list reconciled. Prep instructions reviewed with the patient in clinic.\nElectronically '
            'signed by J. Nurse RN, 10/30/2026 11:15\nCo-signed by A. Doctor MD, 11/04/2026 07:00\n',
            'Riverside Gastroenterology Associates\n100 Main Street\nSpringfield\nPatient: Alex Synthetic\nMRN: 00012345\n'
            'Provider: A. Doctor MD\nTelephone Encounter\nDay of procedure: 11/04/2026\nCalled patient to review prep. '
            'Patient verbalized understanding.\n' + signed,
            'Gastroenterology nursing telephone outreach regarding upcoming colonoscopy preparation and arrival\nPatient: '
            'Alex Synthetic\nDay of procedure: 11/04/2026\nReviewed prep. Patient verbalized understanding.\n' + signed,
            'Pre procedure prep review\nPatient: Alex Synthetic\nDay of procedure: 11/04/2026\nReviewed prep. Patient '
            'verbalized understanding.\n' + signed,
            'TELEPHONE ENCOUNTER                    MRN: 00012345\nPatient: Alex Synthetic\nDay of procedure: 11/04/2026\n'
            'Called patient to review prep. Patient verbalized understanding.\n' + signed,
            'Patient Message\nPatient: Alex Synthetic\nDay of procedure: 11/04/2026\nPatient asked whether to stop iron '
            'tablets before the colonoscopy. Advised to stop iron five days before.\nElectronically signed by J. Nurse '
            'RN, 11/01/2026 09:30\nCosigned by A. Doctor MD, 11/04/2026 07:01\n',
            'Prep Reminder\nPatient: Alex Synthetic\nCase date: 11/04/2026\nReminder sent with split-dose instructions.\n'
            'Electronically signed by J. Nurse RN, 10/28/2026 12:00\nAttested by A. Doctor MD, 11/04/2026 06:59\n',
            'Pre-Admission Testing\nPatient: Alex Synthetic\nDay of procedure: 11/04/2026\nLabs drawn. ECG normal sinus '
            'rhythm.\nElectronically signed by J. Nurse RN, 10/29/2026 14:00\nFinalized by A. Doctor MD, 11/04/2026 '
            '07:10\n')
        for text in rows:
            self.assertTrue(quote_only(text), text)
            every_answer_taken(self, text, ['2026-10-20', '2026-10-28', '2026-10-30', '2026-11-02', '2026-11-04', FAR])

    def test_a_title_outside_the_closed_title_list(self):  # kills pd-around-broadened
        for title in ('Endoscopy Appointment', 'Patient Message', 'Prep Reminder', 'Pre-Admission Testing',
                      'Pre procedure review', 'Pre-colonoscopy Nursing Assessment', 'Outside Colonoscopy Report Review',
                      'Chart Review', 'GI Triage', 'Portal Message'):
            text = report(title=title)
            self.assertTrue(context._pd_around_procedure(text), title)
            self.assertTrue(quote_only(text), title)
            self.assertTrue(taken(text, '2026-10-30'), title)
        self.assertFalse(context._pd_around_procedure(report()))
        self.assertTrue(narrows(report()))

    def test_a_kind_field_names_the_note(self):  # kills pd-around-kind-field
        for field in ('Note type: Telephone', 'Encounter type: Patient message', 'Visit type: Telehealth',
                      'Type of visit: phone call', 'Encounter: Telephone'):
            text = report(title='GI Note', head_extra=field + '\n')
            self.assertTrue(context._pd_around_procedure(text), field)
            self.assertTrue(quote_only(text), field)
        self.assertFalse(context._pd_around_procedure(report(head_extra='Encounter class: hospital outpatient\n')))

    def test_a_flattened_line_cell_is_read_as_a_title(self):  # kills pd-around-cells
        for line in ('TELEPHONE ENCOUNTER        MRN: 00012345', 'Patient Message\tMRN: 00012345',
                     'MRN: 00012345 | Prep Reminder'):
            text = report(title=line)
            self.assertTrue(context._pd_around_procedure(text), line)
            self.assertTrue(quote_only(text), line)

    def test_a_title_anywhere_among_the_heads_first_twelve_lines(self):  # kills pd-around-head-lines
        text = (B + 'Riverside Gastroenterology Associates\n100 Main Street\nSpringfield\nPatient: Alex Synthetic\n'
                'MRN: 00012345\nTelephone Encounter\n' + f'Endoscopist: {ENDO}\nDate performed: 10/21/2026\n'
                'Sedation: propofol by CRNA\n\nFindings\nThe colonoscope was advanced to the cecum.\nImpression\n'
                f'Normal colonoscopy.\n{SIGNED}')
        self.assertTrue(context._pd_around_procedure(text))
        self.assertTrue(quote_only(text))

    def test_a_title_over_eighty_characters(self):  # kills pd-around-title-chars
        title = 'Gastroenterology nursing telephone outreach regarding upcoming colonoscopy preparation and arrival'
        self.assertGreater(len(title), 80)
        self.assertTrue(quote_only(report(title=title)))

    def test_a_field_value_or_a_sentence_is_no_title(self):
        self.assertFalse(context._pd_around_procedure(report(head_extra='Phone: 555-0100\n')))
        self.assertFalse(context._pd_around_procedure(report(head_extra='Consent was signed and risks were given.\n')))
        self.assertTrue(narrows(report(head_extra='Phone: 555-0100\n')))

    def test_a_call_or_a_message_written_in_the_body(self):  # kills pd-no-call-phrase (the third entry)
        f7 = (B + 'Endoscopy Unit Note\nAuthor: Synthetic Nurse, RN (fictional)\nDay of procedure: 11/04/2026\nCall placed '
              'on 10/30/2026.\nSigned: Synthetic Nurse, RN (fictional), 11/04/2026 07:10\n')  # F7, its kind in the body
        self.assertTrue(quote_only(f7))
        every_answer_taken(self, f7, ['2026-10-30', '2026-11-04', FAR])
        for words in ('Spoke with the patient by phone about the result.', 'Left a voicemail for the patient.',
                      'The pathology result will be called to the patient.', 'Patient messaged about the prep.',
                      'Telephone call with the daughter.'):
            text = report(body_extra=words + '\n')
            self.assertTrue(quote_only(text), words)
            self.assertTrue(taken(text, '2026-10-30'), words)
        for words in ('Recall colonoscopy in three years.', 'Phone: 555-0100', 'Telephone: 555-0101'):
            self.assertTrue(narrows(report(body_extra=words + '\n')), words)  # no call as an event


class ClosingRegionTests(SimpleTestCase):
    """DS-3: the sign-off is read only in the note's own closing region."""

    def test_the_refuters_documents_take_every_answer(self):  # DS-3: B4, B5, C1, C5
        rows = (
            ('Outside Colonoscopy Report Review\nPatient: Alex Synthetic\nDate performed: 09/03/2026\nReviewed in clinic '
             'with the patient today. Copied report text follows.\nThe colonoscope was advanced to the cecum. A 10 mm '
             'polyp was removed with a hot snare.\nImpression: one adenoma removed.\nElectronically signed by B. Outside '
             'MD, 09/03/2026 10:15\n', ['2026-10-12', '2026-09-03', FAR]),
            ('Chart Review\nPatient: Alex Synthetic\nDate performed: 09/03/2026\nFacility: Mercy GI\nReviewed in clinic '
             'with the patient today. Copied report text follows.\nThe colonoscope was advanced to the cecum. A 10 mm '
             'polyp was removed with a hot snare.\nImpression: one adenoma removed.\nElectronically signed by B. Outside '
             'MD, 09/03/2026 10:15\n', ['2026-10-12', '2026-09-03', FAR]),
            ('Endoscopy Appointment\nCase date: 11/04/2026        Transcribed by: M. Clerk\nPatient: Alex Synthetic\n'
             'Procedure: EGD with possible dilation\nArrival 06:30. Driver required.\n', ['2026-10-20', '2026-11-04', FAR]),
            ('Endoscopy Pre-Assessment\nDay of procedure: 11/04/2026   Signed by: J. Nurse RN\nPatient: Alex Synthetic\n'
             'Allergies reviewed.\n', ['2026-10-30', '2026-11-04', FAR]))
        for text, answers in rows:
            self.assertTrue(quote_only(text), text)
            every_answer_taken(self, text, answers)

    def test_the_head_of_a_short_document_is_never_its_closing(self):  # kills pd-region-not-head
        # its head names the signer and its label is a visit's (the fifth entry's rule would refuse a procedure's), so
        # only the region keeps the label's own line from signing it
        text = (B + 'Endoscopy Note\nAuthor: J. Nurse RN\nDate seen: 11/04/2026   Signed by: J. Nurse RN\nPatient: '
                'Alex Synthetic\nAllergies reviewed.\n')
        self.assertTrue(quote_only(text))
        self.assertTrue(taken(text, '2026-10-30'))

    def test_a_sign_off_above_the_last_eight_lines_is_not_read(self):  # kills pd-closing-last-lines
        text = report(tail=''.join(f'Plan line {i}: continue the current regimen.\n' for i in range(10)))
        self.assertTrue(quote_only(text))
        self.assertTrue(taken(text, '2026-10-30'))
        self.assertTrue(narrows(report(body_extra=BODY)))  # the same sign-off among the last eight lines

    def test_an_addendum_after_the_head(self):  # kills pd-no-addendum
        text = report(tail=f'Addendum\nPathology: no dysplasia.\nElectronically signed by {ENDO}, 10/21/2026 15:00\n')
        self.assertTrue(quote_only(text))
        self.assertTrue(taken(text, '2026-10-30'))

    def test_a_line_announcing_copied_text(self):  # kills pd-no-copied-text
        for words in ('Copied report text follows.', 'Outside report pasted below.', 'See attached report.',
                      'Report imported from the referring practice.'):
            text = report(body_extra=words + '\n')
            self.assertTrue(quote_only(text), words)
            self.assertTrue(taken(text, '2026-10-30'), words)

    def test_a_sign_off_under_a_heading_naming_another_record(self):  # kills pd-signoff-not-under-occurrence
        text = (report(closing='') + ''.join(f'Line {i} of the plan.\n' for i in range(6)) + 'Outside Report\nThe '
                'colonoscope was advanced to the cecum.\n' + SIGNED)
        self.assertTrue(quote_only(text))
        self.assertTrue(taken(text, '2026-10-30'))


class OneValueTests(SimpleTestCase):
    """DS-4: several values never narrow, and are never worded as documented conflicting dates of service."""

    def test_the_refuters_documents_take_every_answer(self):  # DS-4: F1, D1, D2, C4
        rows = (
            ('GI Consultation\nPatient: Alex Synthetic\nDay of procedure: 11/04/2026\nSurveillance colonoscopy\nDate '
             'performed: 05/02/2019\nChief complaint: due for surveillance; intermittent hematochezia.\nExam: Abdomen '
             'soft, nontender.\nAssessment: personal history of adenomas; colonoscopy scheduled.\nElectronically signed '
             'by A. Doctor MD, 10/28/2026 16:40\n', ['2026-10-28', '2026-11-04', '2019-05-02', FAR]),
            ('Pre-colonoscopy Nursing Assessment\nPatient: Alex Synthetic\nDay of procedure: 11/04/2026\nSurveillance '
             'colonoscopy\nDate performed: 05/02/2019\nAllergies reviewed. Medication list reconciled.\nElectronically '
             'signed by J. Nurse RN, 10/30/2026 11:15\n', ['2026-10-30', '2026-11-04', '2019-05-02', FAR]),
            ('Endoscopy Appointment\nPatient: Alex Synthetic\nCase date: 11/04/2026\nMoved at patient\'s request; new slot '
             'below.\nDay of procedure: 11/18/2026\nArrival 06:30. Driver required.\nEntered by front desk 10/20/2026\n',
             ['2026-10-20', '2026-11-04', '2026-11-18', FAR]),
            ('Pre-colonoscopy Nursing Assessment\nPatient: Alex Synthetic\nExam date: 10/02/2026\nDay of procedure: '
             '11/04/2026\nAllergies reviewed. Medication list reconciled.\nElectronically signed by J. Nurse RN, '
             '10/30/2026 11:15\n', ['2026-10-30', '2026-10-02', '2026-11-04', FAR]))
        for text, answers in rows:
            self.assertTrue(quote_only(text), text)
            every_answer_taken(self, text, answers)
            state = checks.service_date_state(context.merge_user_values(context.extract_context(text), {}), None)
            self.assertNotIn('Conflicting dates of service', checks._date_problem(state), text)

    def test_one_value_the_sign_off_states_and_another_narrow_nothing(self):  # kills pd-every-candidate-narrows
        text = report(head_extra='Day of procedure: 11/04/2026\n')
        self.assertTrue(quote_only(text))
        self.assertEqual(evidence(fact(text)), ['Date performed: 10/21/2026', 'Day of procedure: 11/04/2026'])
        every_answer_taken(self, text, ['2026-10-21', '2026-11-04', '2026-10-30'])

    def test_a_wide_label_in_doubt_beside_it_narrows_nothing(self):  # kills pd-no-wide-in-doubt
        text = report(head_extra='DOB: 01/01/1998\nExam date: 01/01/1998\n')
        self.assertEqual([c.doubt for c in context._service_dates(text, layout(text)) if c.wide], ['', 'birth'])
        self.assertTrue(quote_only(text))
        self.assertTrue(taken(text, '2026-10-30'))


class CleanLineTests(SimpleTestCase):
    """Fail-closed beside the binding rules: the label's date alone in its field, on a short line stating no other date."""

    def test_a_date_with_words_after_it_in_its_field(self):  # kills pd-label-alone
        text = report(label='Date performed: 10/21/2026 (screening)')
        self.assertTrue(quote_only(text))
        self.assertEqual(evidence(fact(text)), ['Date performed: 10/21/2026 (screening)'])
        self.assertTrue(taken(text, '2026-10-30'))

    def test_another_date_on_the_labels_line(self):  # kills pd-clean-line-dates
        for line in ('Date performed: 10/21/2026    Accession: 10/22/2026', 'Date performed: 10/21/2026    Printed: '
                     '10/22/26', 'Date performed: 10/21/2026    Scope serviced 05/2019',
                     'Date performed: 10/21/2026    Scope model: Olympus 190, May 2019'):
            text = report(label=line)
            self.assertTrue(quote_only(text), line)
            self.assertTrue(taken(text, '2026-10-30'), line)

    def test_a_line_longer_than_the_quote_limit(self):  # kills pd-clean-line-length
        text = report(label='Date performed: 10/21/2026    Location: ' + 'Riverside Endoscopy Suite Two ' * 9)
        self.assertTrue(quote_only(text))
        self.assertTrue(taken(text, '2026-10-30'))
        addendum = report(label='Date performed: 10/21/2026    Addendum pending')
        self.assertTrue(quote_only(addendum))


class MustHoldTests(SimpleTestCase):
    """The plan's must-hold cases beyond F7."""

    def test_an_outside_date_performed_is_never_sent(self):  # kills pd-own-reading-filter
        text = (B + 'Prior colonoscopy at an outside center\nDate performed: May 2, 2019\n\nColonoscopy Report\nDate of '
                'service: October 19, 2026\nThe colonoscope was advanced to the cecum.\n')
        self.assertEqual(sends(text), '2026-10-19')
        self.assertFalse(taken(text, '2019-05-02'))
        outside = B + 'Colonoscopy Report\nOutside date performed: 05/02/2019\nSigned: Synthetic MD, 05/02/2019\n'
        self.assertEqual(fact(outside).evidence, ())  # another occurrence's: dropped as installed drops it

    def test_a_last_exam_date_beside_a_date_of_service(self):
        text = B + 'Office visit\nDate of service: 10/06/2026\nLast exam date: 04/02/2025\nEstablished patient\n'
        self.assertEqual(sends(text), '2026-10-06')
        self.assertFalse(taken(text, '2025-04-02'))

    def test_a_wide_head_beside_an_aside_header_and_an_addendum_keeps_the_installed_ask(self):  # kills pd-plain-apart
        text = (B + 'Colonoscopy Report\nDate performed: 10/21/2026\nOutside procedure date: 10/14/2026\nFindings: The '
                'colonoscope was advanced to the cecum.\nImpression: normal.\nAddendum\nDate of service: 10/21/2026\n'
                'Signed: Synthetic MD, 10/21/2026\n')
        f = fact(text)
        self.assertEqual((f.origin, f.value), ('missing', None))  # installed asks (rule U puts the addendum's label in doubt)
        self.assertEqual(sends(text), 'DATELESS')
        self.assertTrue(taken(text, '2026-10-21'))
        self.assertFalse(taken(text, '2026-10-14'))

    def test_a_worded_field_naming_another_occurrence_is_dropped(self):  # kills pd-worded-occurrence-words
        for words in ('requested by patient', 'of the prior exam', 'previously scheduled'):
            text = (B + f'Procedure note\nProcedure date {words}: 11/04/2026\nFindings: normal.\nSigned: Synthetic MD, '
                        f'11/04/2026\n')
            self.assertEqual(fact(text).evidence, (), words)
            self.assertTrue(taken(text, '2026-10-30'), words)

    def test_a_wide_label_below_the_head_is_not_read(self):  # kills pd-head-reach
        text = (B + 'Colonoscopy Report\nProceduralist: Synthetic MD\n\nFindings\nThe colonoscope was advanced to the '
                'cecum.\nDate performed: 10/19/2026\nSigned: Synthetic MD, 10/19/2026\n')
        self.assertEqual(fact(text).evidence, ())
        self.assertTrue(taken(text, '2026-10-20'))
        head = text.replace('\nDate performed: 10/19/2026', '').replace('Proceduralist: Synthetic MD\n',
                                                                        'Proceduralist: Synthetic MD\nDate performed: '
                                                                        '10/19/2026\n')
        self.assertEqual(evidence(fact(head)), ['Date performed: 10/19/2026'])

    def test_a_two_digit_year_or_a_plan_section_reads_nothing(self):
        self.assertEqual(fact(B + 'New Patient Evaluation\nDate seen: 10/26/26\nSigned: X, 10/26/2026\n').evidence, ())
        text = B + 'Office visit\nPlan\nExam date: 11/04/2026\nSigned: Synthetic MD, 11/04/2026\n'
        self.assertEqual(fact(text).evidence, ())

    def test_a_wide_label_is_never_sent(self):
        for text in (B + 'New Patient Evaluation\nDate seen: 10/26/2026\nSigned: Synthetic MD, 10/26/2026\n',
                     B + 'Colonoscopy Report\nDay of procedure: Oct 27, 2026\nAttested: Synthetic MD, Oct 27, 2026\n',
                     B + 'Colonoscopy Report\nExam date: 10/06/2026\nService date logged for this case: 10/06/2026\n'
                         'Signed: Synthetic MD, 10/06/2026\n', report()):
            self.assertNotEqual(fact(text).origin, 'document', text)
            self.assertEqual(sends(text), 'DATELESS', text)
            self.assertIsNone(context.service_date_of(text), text)


class StrongHeadHoldTests(SimpleTestCase):
    """The integration's STRONG-HEAD HOLD (pd.json amendment_20261101_integration, Wave 1 repair cycle 1): a procedure
    report's own head (detect.todays_procedure_report, imported) whose own-date field gives exactly one date holds a
    member's answer of any other day - never narrowed, taken or sent; only an answer the reader would take moves (TAKEN ->
    HELD); the 'none' state is unchanged. Not in a note written around a procedure (rule (c)'s broadened detection, a call
    or a message stated). The documents here are written for these tests (h4-03 apart) and are synthetic."""

    EGD = (B + 'Esophagogastroduodenoscopy Report\nDate performed: 09/14/2026\nEndoscopist: Lorcan Abernethy-Vale, MD '
               '(fictional)\nModerate sedation: midazolam 2 mg and fentanyl 50 mcg, nurse-administered\nIndication: '
               'solid-food dysphagia for four months.\n\nFindings\nThe endoscope was passed through the upper esophageal '
               'sphincter and advanced to the second part of the duodenum. A Schatzki ring at 38 cm was dilated with a '
               '54 French bougie.\nImpression\nSchatzki ring, dilated. Otherwise a normal examination.\nPlan\nBiopsy '
               'results by 09/21/2026; repeat dilation if the dysphagia returns.\n')
    CONSULT = (B + 'Gastroenterology Consultation\nSeen by: Odile Fairweather-Ng, MD (fictional)\nDay of procedure: '
                   '11/04/2026\nReason for consultation: iron deficiency anemia.\nAssessment and plan: bidirectional '
                   'endoscopy is planned for 11/04/2026 with monitored anesthesia care.\nElectronically signed by Odile '
                   'Fairweather-Ng, MD (fictional), 10/30/2026 16:40\n')
    BOOKING = (B + 'Endoscopy Appointment\nDay of procedure: 11/04/2026\nEndoscopist: Lorcan Abernethy-Vale, MD '
                   '(fictional)\nSedation: monitored anesthesia care\nArrival 06:30; clear liquids until 04:30; a driver '
                   'is required.\nSigned: Synthetic Scheduler (fictional), 10/30/2026\n')
    CALL = (B + 'Endoscopy Unit Note\nDay of procedure: 11/04/2026\nProceduralist: Lorcan Abernethy-Vale, MD '
                '(fictional)\nSedation: monitored anesthesia care\nCall placed on 10/30/2026 to go over the bowel '
                'preparation; the patient confirmed the arrival time.\nSigned: Synthetic Nurse, RN (fictional), '
                '10/30/2026\n')

    def held_note(self, text, answer):
        merged = context.merge_user_values(context.extract_context(text), {'service_date': answer})['service_date']
        self.assertTrue(context.is_member_conflict(merged), (answer, text[:80]))
        return merged.note

    def test_h4_03_holds_every_answer_but_its_heads_own_date(self):  # kills pd-head-hold
        text = DOCS['h4-03']['text']
        for answer in ('2026-10-08', '2026-10-09', '2026-10-05', '2026-10-07', FAR):
            self.assertEqual(sends(text, answer), 'HELD', answer)
        self.assertEqual(sends(text, '2026-10-06'), '2026-10-06')  # the walk's answer: the stored dated request
        self.assertEqual(sends(text), 'DATELESS')
        held = context.merge_user_values(context.extract_context(text), {'service_date': '2026-10-08'})
        self.assertEqual(checks._date_problem(checks.service_date_state(held, None)),
                         'The date of service is in conflict. Encounter metadata entered by a workspace member gives '
                         "2026-10-08; this procedure report's own head gives its date of service as 2026-10-06 (“Exam "
                         'date: 10/06/2026”), and the document also states “Service date logged for this case: '
                         '10/08/2026”. Both are kept and neither is used: correct the metadata, clear it, or add an '
                         'addendum to the document')

    def test_a_strong_head_holds_an_entered_date_of_another_day(self):  # kills pd-head-hold
        text = self.EGD
        f = fact(text)
        self.assertEqual((f.origin, f.value, evidence(f)), ('missing', None, ['Date performed: 09/14/2026']))
        self.assertTrue(all(isinstance(e, context._QuotedSpan) for e in f.evidence))  # rule (c) still only quotes
        self.assertEqual(f.note, context.HEAD_DATE_NOTE.format(day='2026-09-14', head='“Date performed: 09/14/2026”',
                                                               also=''))
        self.assertEqual(sends(text), 'DATELESS')  # the 'none' state is unchanged: nothing is sent before an answer
        self.assertEqual(sends(text, '2026-09-14'), '2026-09-14')
        for answer in ('2026-09-21', '2026-09-15', '2026-09-13', FAR):
            self.assertEqual(sends(text, answer), 'HELD', answer)
        self.assertEqual(self.held_note(text, '2026-09-21'), context.HEAD_HOLD_NOTE.format(
            user='2026-09-21', day='2026-09-14', head='“Date performed: 09/14/2026”', also=''))

    def test_a_weak_head_holds_nothing_new(self):  # kills pd-head-strong
        text = self.EGD.replace('Endoscopist:', 'Attending:')  # an attending is no proceduralist field
        self.assertNotIsInstance(fact(text), context._HeadHeldFact)
        self.assertTrue(quote_only(text))
        every_answer_taken(self, text, ['2026-09-14', '2026-09-21', '2026-09-15', FAR])
        no_sedation = self.EGD.replace('Moderate sedation: midazolam 2 mg and fentanyl 50 mcg, nurse-administered',
                                       'Sedation: none')
        self.assertTrue(quote_only(no_sedation))
        every_answer_taken(self, no_sedation, ['2026-09-21', FAR])

    def test_a_head_with_no_single_date_holds_nothing_new(self):  # kills pd-head-one-date
        two_fields = self.EGD.replace('Date performed: 09/14/2026\n', 'Date performed: 09/14/2026\nExam date: '
                                                                      '09/15/2026\n')
        self.assertNotIsInstance(fact(two_fields), context._HeadHeldFact)
        every_answer_taken(self, two_fields, ['2026-09-14', '2026-09-15', '2026-09-21', FAR])
        two_dates = self.EGD.replace('Date performed: 09/14/2026', 'Date performed: 09/14/2026 (rescheduled from '
                                                                   '09/07/2026)')
        self.assertNotIsInstance(fact(two_dates), context._HeadHeldFact)
        every_answer_taken(self, two_dates, ['2026-09-07', '2026-09-14', '2026-09-21', FAR])

    def test_a_consult_with_a_planned_procedure_date_holds_nothing(self):
        text = self.CONSULT  # no proceduralist or sedation field: no procedure report's own head
        self.assertNotIsInstance(fact(text), context._HeadHeldFact)
        self.assertTrue(quote_only(text))
        every_answer_taken(self, text, ['2026-10-30', '2026-11-04', FAR])  # the consultation's own day stays an answer

    def test_a_note_written_around_a_procedure_holds_nothing(self):  # kills pd-head-around
        text = self.BOOKING  # a strong head, under a booking's title
        self.assertNotIsInstance(fact(text), context._HeadHeldFact)
        every_answer_taken(self, text, ['2026-10-30', '2026-11-04', FAR])

    def test_a_call_written_in_the_body_holds_nothing(self):  # kills pd-head-call
        text = self.CALL  # a strong head under a neutral title; the call is stated in the body
        self.assertNotIsInstance(fact(text), context._HeadHeldFact)
        every_answer_taken(self, text, ['2026-10-30', '2026-11-04', FAR])

    def test_a_documented_conflict_takes_only_the_heads_date(self):
        text = (DOCS['h4-03']['text'].replace('Exam date: 10/06/2026', 'Date of service: 10/06/2026')
                .replace('Service date logged for this case:', 'Service date:'))
        f = fact(text)
        self.assertEqual((f.origin, f.note), ('conflict', 'Conflicting documented values: 2026-10-06, 2026-10-08.'))
        self.assertEqual(context.documented_values(f), ('2026-10-06', '2026-10-08'))  # its note is read: as made
        self.assertEqual(sends(text), 'DATELESS')
        self.assertEqual(sends(text, '2026-10-06'), '2026-10-06')
        self.assertEqual(sends(text, '2026-10-08'), 'HELD')

    def test_the_note_says_which_answers_are_held(self):  # kills pd-head-note
        f = fact(DOCS['h4-03']['text'])
        self.assertEqual(f.note, context.HEAD_DATE_NOTE.format(
            day='2026-10-06', head='“Exam date: 10/06/2026”',
            also=', and the document also states “Service date logged for this case: 10/08/2026”'))
        self.assertNotIn("a member's date is taken", f.note)

    def test_rule_a_keeps_its_question_and_says_its_date_is_held_too(self):  # kills pd-head-charge-note
        text = DOCS['h4-03']['text'].replace('Service date logged for this case:', 'Service date:')
        f = fact(text)
        self.assertTrue(f.note.endswith("so the date is asked; a member's answer is taken only when it is 2026-10-08. "
                                        "This procedure report's own head gives its date of service as 2026-10-06, so "
                                        'an answer of 2026-10-08 is held too.'))
        self.assertEqual(context.charge_date_problem(f), 'The document also states “Exam date: 10/06/2026”, while '
                                                         '2026-10-08 is read from “Service date: 10/08/2026”')

    def test_only_an_answer_the_reader_takes_is_held(self):
        # an answer held before keeps its own note (h4-04's narrowing holds every other day already)
        note = self.held_note(DOCS['h4-04']['text'], '2026-10-20')
        self.assertTrue(note.startswith(context.USER_CONFLICT_NOTE.split('{', 1)[0]))
        self.assertNotIn("procedure report's own head", note)
        self.assertIsInstance(fact(DOCS['h4-04']['text']), context._HeadHeldFact)
        # the hold never takes: the head's own day, held before, stays held
        listed = context.Fact('service_date', None, 'conflict', (), context.DOCUMENT_CONFLICT_NOTE + '2026-10-01, '
                                                                    '2026-10-02.')
        marked = context._head_held(listed, listed.note, '2026-10-06', '“Exam date: 10/06/2026”', '')
        def merged(answer):
            return context.merge_user_values({'service_date': marked}, {'service_date': answer})['service_date']

        self.assertEqual((merged('2026-10-06').origin, merged('2026-10-06').note),  # held before: held as before
                         ('conflict', context.USER_CONFLICT_NOTE.format(user='2026-10-06',
                                                                       document='2026-10-01 or 2026-10-02')))
        self.assertEqual((merged('2026-10-01').origin, merged('2026-10-01').note),  # taken before: held by the head
                         ('conflict', context.HEAD_HOLD_NOTE.format(user='2026-10-01', day='2026-10-06',
                                                                   head='“Exam date: 10/06/2026”', also='')))
        self.assertEqual(context.merge_user_values({'service_date': marked}, {})['service_date'], listed)

    def test_the_marked_fact_is_stored_compared_and_carried_as_its_plain_fact(self):
        import pickle
        f = fact(DOCS['h4-03']['text'])
        plain = context.Fact(f.name, f.value, f.origin, f.evidence, f.note)
        self.assertIsInstance(f, context._HeadHeldFact)
        self.assertEqual(f, plain)
        self.assertEqual(plain, f)
        self.assertEqual(hash(f), hash(plain))
        self.assertEqual(to_jsonable(f), to_jsonable(plain))
        carried = pickle.loads(pickle.dumps(f))  # the analyze child hands its facts to the worker by pickle
        self.assertEqual((carried.head_day, carried.head_quotes), (f.head_day, f.head_quotes))
        self.assertEqual(context.merge_user_values({'service_date': carried}, {'service_date': FAR})['service_date'].note,
                         self.held_note(DOCS['h4-03']['text'], FAR))

    def test_takes_another_day_reads_as_merge_user_values_takes(self):
        texts = [doc['text'] for doc in DOCS.values()] + [self.EGD, self.CONSULT, self.BOOKING, self.CALL, report(),
                                                         DOCS['h4-03']['text'].replace('Service date logged for this case:',
                                                                                       'Service date:')]
        for text in texts:
            f = fact(text)
            plain = context.Fact(f.name, f.value, f.origin, f.evidence, f.note)
            dates = regression.documented_dates(text)
            day = getattr(f, 'head_day', None) or (dates[0] if dates else '2026-10-01')
            near = dt.date.fromisoformat(day)
            answers = set(dates) | {FAR, (near - dt.timedelta(days=1)).isoformat(),
                                    (near + dt.timedelta(days=1)).isoformat()}
            others = {a for a in answers - {day} if context.merge_user_values(
                {'service_date': plain}, {'service_date': a})['service_date'].origin == 'user'}
            if others:
                self.assertTrue(context._takes_another_day(plain, day), (text[:80], others))
            if not context._takes_another_day(plain, day):
                self.assertEqual(others, set(), text[:80])


class HelperTests(SimpleTestCase):
    def test_the_last_lines_start(self):
        text = 'a\n\n' + ''.join(f'line {i}\n\n \n' for i in range(9))
        start = context._pd_closing_start(text)
        self.assertEqual(text[start:].split('\n')[0], 'line 1')
        self.assertEqual(context._pd_closing_start('one\ntwo\n'), 0)
        self.assertEqual(context._pd_closing_start(''), 0)

    def test_the_sign_off_day(self):
        text = report()
        self.assertEqual(context._pd_signoff_day(text, context._head_end(text, layout(text))), '2026-10-21')
        for other in (report(title='Endoscopy Appointment'), report(body_extra='Copied report text follows.\n'),
                      report(closing='Co-signed: X Y, MD, 10/21/2026\n')):
            self.assertIsNone(context._pd_signoff_day(other, context._head_end(other, layout(other))))

    def test_the_line_and_its_quote(self):
        text = 'x\n  Date seen: 10/26/2026  \ny'
        start = text.index('Date')
        span, quote = context._pd_line(text, 2, text.index('\ny'), start, start + 21)
        self.assertEqual((span.text, quote), ('Date seen: 10/26/2026', '“Date seen: 10/26/2026”'))
