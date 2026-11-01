"""GI round 4, package PD (date step 1): wide own-date labels and D2's worded date-of-service field only ever ASK or
NARROW, and are never sent (studio/gi/context.py: _service_dates, _pd_wide_candidates, _head_end, _closing_days,
_worded_field, _service_date_fact over the renamed, unchanged _installed_service_date_fact, _date_fact's notes,
charge_date_problem). Declared before any code: tests/fixtures/gi4/declarations/pd.json.

(a) the installed reading sends X and a wide or worded own label states Y: asked, only X taken, every reader reads X;
(b) it already asks with evidence: unchanged; (c) it asks with no evidence: the labels become that evidence (one value
only when a closing-role line among the last 8 non-empty lines states the same day, never a consent, order, request,
booking or call line); nothing is read under a title of a note written around a procedure.

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

B = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DOCS = regression.load_fixtures()
FAR = '1998-01-01'


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


class RegressionDocumentTests(SimpleTestCase):
    """The plan's PD table, on the texts the service read (tests/fixtures/gi4/regression/)."""

    EXPECTED = {  # doc: (origin, evidence, accepted, held)
        'h4-01': ('missing', ['Date seen: 10/26/2026'], ['2026-10-26'],
                  ['2026-10-14', '2026-10-25', '2026-10-27', '2026-11-02', '2026-11-23', '2026-12-14', FAR]),
        'h4-02': ('missing', ['Case date: 2026-10-21'], ['2026-10-21'], ['2026-10-20', '2026-10-22', '2026-11-18', FAR]),
        'h4-03': ('conflict', ['Exam date: 10/06/2026', 'Service date logged for this case: 10/08/2026'],
                  ['2026-10-06', '2026-10-08'], ['2026-10-05', '2026-10-07', '2026-10-09', FAR]),
        'h4-04': ('missing', ['Date performed: October 19, 2026'], ['2026-10-19'],
                  ['2026-09-28', '2026-10-18', '2026-10-20', '2026-11-16', FAR]),
        'h4-06': ('missing', ['Day of procedure: Oct 27, 2026'], ['2026-10-27'],
                  ['2025-09-30', '2026-10-26', '2026-10-28', '2026-11-24', FAR]),
    }

    def test_wide_labels_become_the_evidence_and_only_their_dates_are_taken(self):
        for doc_id, (origin, quoted, accepted, held) in self.EXPECTED.items():
            text = DOCS[doc_id]['text']
            f = fact(text)
            self.assertEqual((f.origin, f.value), (origin, None), doc_id)
            self.assertEqual(evidence(f), quoted, doc_id)
            for answer in accepted:
                self.assertTrue(taken(text, answer), (doc_id, answer))
                self.assertEqual(sends(text, answer), answer, (doc_id, answer))
            for answer in held:
                self.assertFalse(taken(text, answer), (doc_id, answer))
                self.assertEqual(sends(text, answer), 'HELD', (doc_id, answer))
            self.assertEqual(sends(text), 'DATELESS', doc_id)  # nothing is sent before a member's answer

    def test_the_notes(self):
        for doc_id in ('h4-01', 'h4-02', 'h4-04', 'h4-06'):
            self.assertEqual(fact(DOCS[doc_id]['text']).note, context.WIDE_DATE_NOTE, doc_id)
        self.assertEqual(fact(DOCS['h4-03']['text']).note, 'Conflicting documented values: 2026-10-06, 2026-10-08.')

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

    def test_every_reader_reads_x_while_it_is_asked(self):  # kills pd-rule-a-readers-read-x
        f = fact(self.X_Y)
        self.assertEqual(context.charge_date_own(f), '2026-10-18')
        self.assertEqual(context.charge_question_day(self.X_Y), dt.date(2026, 10, 18))
        self.assertEqual(context.service_date_of(self.X_Y), dt.date(2026, 10, 18))
        problem = context.charge_date_problem(f)
        self.assertEqual(problem, 'The document also states “Date performed: 10/19/2026”, while 2026-10-18 is '
                                  'read from “Date of service: 10/18/2026”')
        self.assertTrue(f.note.startswith(problem))

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

    def test_the_relabelled_ledger_keeps_installeds_date(self):  # the judge's F7: the 53(b)/54 precedent
        text = DOCS['h4-03']['text'].replace('Service date logged for this case:', 'Service date:')
        self.assertEqual(sends(text), 'DATELESS')
        self.assertTrue(taken(text, '2026-10-08'))
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


class InstalledAsksWithNoEvidenceTests(SimpleTestCase):
    """Rule (c): the labels become the evidence - one value only with a closing-role line of the same day."""

    def test_a_corroborated_value_restricts_the_answer(self):
        text = B + 'New Patient Evaluation\nDate seen: 10/26/2026\nTotal time: 30 minutes.\nSigned: Synthetic MD, 10/26/2026\n'
        self.assertEqual(evidence(fact(text)), ['Date seen: 10/26/2026'])
        self.assertTrue(taken(text, '2026-10-26'))
        self.assertFalse(taken(text, FAR))

    def test_an_uncorroborated_value_leaves_the_installed_fact(self):  # kills pd-corroboration
        text = (B + 'Colonoscopy\nDay of procedure: 11/04/2026\nPrep reviewed.\nSigned: Synthetic Nurse, RN (fictional), '
                '10/30/2026\n')
        f = fact(text)
        self.assertEqual((f.origin, f.evidence, f.note), ('missing', (), context.MISSING_NOTES['service_date']))
        self.assertTrue(taken(text, '2026-10-30'))  # the note's real day is never refused
        self.assertTrue(taken(text, '2026-11-04'))
        self.assertEqual(sends(text), 'DATELESS')

    def test_several_values_are_a_conflict_of_those_values(self):
        text = B + 'Colonoscopy Report\nExam date: 10/06/2026\nCase date: 10/08/2026\nFindings: normal.\n'
        f = fact(text)
        self.assertEqual(f.note, 'Conflicting documented values: 2026-10-06, 2026-10-08.')
        self.assertTrue(taken(text, '2026-10-06') and taken(text, '2026-10-08'))
        self.assertFalse(taken(text, '2026-10-07'))

    def test_a_worded_field_alone_is_noted_as_a_wide_label_never_as_text_after_its_date(self):
        text = (B + 'Banding Session\nProceduralist: Synthetic MD\nService date logged for this case: 10/08/2026\n'
                'Signed electronically: Synthetic MD, 10/08/2026 07:48\n')
        f = fact(text)
        self.assertEqual((f.origin, evidence(f)), ('missing', ['Service date logged for this case: 10/08/2026']))
        self.assertEqual(f.note, context.WIDE_DATE_NOTE)
        self.assertNotIn(context.FIELD_DATE_NOTE, f.note)
        self.assertTrue(taken(text, '2026-10-08'))
        self.assertFalse(taken(text, '2026-10-09'))

    def test_a_wide_label_is_never_sent(self):  # kills pd-wide-never-own
        for text in (B + 'New Patient Evaluation\nDate seen: 10/26/2026\nSigned: Synthetic MD, 10/26/2026\n',
                     B + 'Colonoscopy Report\nDay of procedure: Oct 27, 2026\nAttested: Synthetic MD, Oct 27, 2026\n',
                     B + 'Colonoscopy Report\nExam date: 10/06/2026\nService date logged for this case: 10/06/2026\n'
                         'Signed: Synthetic MD, 10/06/2026\n'):
            self.assertNotEqual(fact(text).origin, 'document', text)
            self.assertEqual(sends(text), 'DATELESS', text)
            self.assertIsNone(context.service_date_of(text), text)  # no reader reads it as the date either


class AroundProcedureTitleTests(SimpleTestCase):
    """Hardening: nothing is read under a title of a note written around a procedure; the installed fact stands."""

    def test_the_judges_f7_call_and_booking_shapes(self):  # kills pd-around-title
        for text, own_day in (
                (B + 'Pre-procedure telephone call\nDay of procedure: 11/04/2026\nPatient reached; prep reviewed.\n'
                     'Signed: Synthetic Nurse, RN (fictional), Oct 30, 2026\n', '2026-10-30'),
                (B + 'Pre-procedure call note\nDay of procedure: 11/04/2026\nCall placed on 10/30/2026.\nSigned: '
                     'Synthetic Nurse, RN (fictional), 11/04/2026 07:10\n', '2026-10-30'),
                (B + 'Endoscopy booking\nCase date: 2026-11-04\nColonoscopy booked for the morning list.\n', '2026-10-29'),
                (B + 'Endoscopy booking\nCase date: 2026-11-04\nColonoscopy booked for the morning list.\nAttested: '
                     'Synthetic Scheduler, 2026-11-04\n', '2026-10-29')):
            f = fact(text)
            self.assertEqual((f.origin, f.evidence), ('missing', ()), text)
            self.assertEqual(sends(text), 'DATELESS', text)  # the planned day is never sent by the document
            self.assertTrue(taken(text, own_day), text)  # the note's own day is never refused

    def test_every_around_title_holds(self):
        for title in ('Procedure consent', 'Colonoscopy preparation instructions', 'Patient Education Handout',
                      'GI Records Review', 'Clinic Correspondence', 'Colonoscopy scheduling'):
            text = B + title + '\nDay of procedure: 11/04/2026\nSigned: Synthetic MD, 11/04/2026\n'
            self.assertEqual(fact(text).evidence, (), title)
            self.assertTrue(taken(text, '2026-10-30'), title)


class ClosingLineTests(SimpleTestCase):
    """Hardening: corroboration only from closing-role lines among the last 8 non-empty lines, never from a consent,
    order, request, booking or call line."""

    def test_a_closing_line_far_above_the_end_corroborates_nothing(self):  # kills pd-closing-last-lines
        text = (B + 'Colonoscopy\nDay of procedure: 11/04/2026\nSigned: Synthetic MD, 11/04/2026\n'
                + ''.join(f'Line {i} of the note.\n' for i in range(10)))
        self.assertEqual(fact(text).evidence, ())
        self.assertTrue(taken(text, '2026-10-30'))
        near = text + 'Signed: Synthetic MD, 11/04/2026\n'  # the same line among the last eight
        self.assertEqual(evidence(fact(near)), ['Day of procedure: 11/04/2026'])
        self.assertFalse(taken(near, '2026-10-30'))

    def test_consent_order_request_booking_and_call_lines_corroborate_nothing(self):  # kills pd-not-closing-words
        for line in ('Call signed: Synthetic Nurse, RN (fictional), 11/04/2026',
                     'Consent signed by the patient 11/04/2026', 'Orders signed by Synthetic MD 11/04/2026',
                     'Request finalized by Synthetic Clerk 11/04/2026', 'Booking attested: Synthetic Clerk, 11/04/2026',
                     'Phone note signed 11/04/2026', 'Scheduled and signed by the front desk 11/04/2026'):
            text = B + 'Colonoscopy\nDay of procedure: 11/04/2026\nPrep reviewed.\n' + line + '\n'
            self.assertEqual(fact(text).evidence, (), line)
            self.assertTrue(taken(text, '2026-10-30'), line)

    def test_the_closing_days(self):
        text = (B + 'Note\nDOB: 01/01/1998\nElectronically authenticated by Synthetic MD, 10/26/2026 18:22\n'
                'Co-signed: Synthetic Fellow (DOB 01/02/1999), 10/27/2026\n')
        self.assertEqual(context._closing_days(text), frozenset({'2026-10-26', '2026-10-27'}))
        self.assertEqual(context._closing_days(B + 'Consent signed 10/26/2026\n'), frozenset())

    def test_the_last_lines_start(self):
        text = 'a\n\n' + ''.join(f'line {i}\n\n \n' for i in range(9))
        start = context._pd_closing_start(text)
        self.assertEqual(text[start:].split('\n')[0], 'line 1')
        self.assertEqual(context._pd_closing_start('one\ntwo\n'), 0)
        self.assertEqual(context._pd_closing_start(''), 0)


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
