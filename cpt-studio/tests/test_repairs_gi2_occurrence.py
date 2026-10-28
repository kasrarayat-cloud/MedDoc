"""GI round 2 (session 7c8d38da), the narrow source rule for wrong-occurrence dates (studio/gi/context.py).

Interpretation 28 left one family open for the owner: a labelled date that the text around it marks as ANOTHER
occurrence's - a heading over its block ("Outside colonoscopy:" above "Facility: ..." above "Procedure date:
09/03/2026"), a title ("Cancelled colonoscopy" above the label) or a field on its row more than 80 characters before it
("Planned procedure: colonoscopy with ... Procedure Date: 11/04/2026") - was read as the note's own date: documented,
sent to Corti with today's colonoscopy, and an act done today excluded against it (must-fix class 1). The owner ruled
on 2026-10-28 (docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, "Owner decisions, 2026-10-28 ... second round"):

    A labelled date that a heading, a title or a field on its row naming another occurrence governs is asked, never
    sent; a member's answer equal to that other occurrence's date is not taken (an addendum settles it); a neutral
    heading the reader cannot place changes nothing. Status fields beside the label ("Status: Scheduled"), "Recall"
    and another discipline's undated title stay known limits.

The rule reads again only a label the installed reading reads as the note's own, and only moves it to 'beside' - it
keeps speaking (the date is asked) and its date is never a member's answer - so no candidate is silenced and no date is
created: (a) the label's section, opened by a heading the section reader cannot place whose own words name another
occurrence; (b) its row up to 400 characters before it; (c) the reader's own act-status words (cues.CANCELLED_CLAUSE)
read as date qualifiers. A word that opens a field about something else or with a date of its own, or that dates another
date, does not govern the label and changes nothing. Synthetic text only; no network (the suite's FakeProvider).
"""
import time

from django.conf import settings
from django.test import SimpleTestCase

from studio import bounded, jobs
from studio.gi import context
from tests.test_pipeline_api import OFFICE_NOTE
from tests.test_repairs_7c8_context import DateAssertions
from tests.test_repairs_7c8_context3 import (COLO_BODY, COLO_PLAIN, EGD_BODY, ELENA_DATE, HEAD, EndToEnd, date_fact,
                                             evidence_text)

def shape(text):
    """A subtest's name: the text's first lines after the synthetic banner, blank lines skipped."""
    return ' / '.join(line for line in text.splitlines()[1:5] if line.strip())[:90]


FILLER = ('referring physician Dr. B. Synthetic of the Synthetic Valley Clinic, insurance verified, consent signed and '
          'witnessed by the charge nurse in the pre-procedure area ')  # 154 characters of a row, no vocabulary word

# (text, the other occurrence's date): every one documented and sent at the installed revision 2b82889f
RULED = (
    # (a) a heading over the label's block, a list or a scanned page's blank-line block
    (HEAD + 'Colonoscopy report\nOutside colonoscopy:\nFacility: Synthetic Regional Hospital\nProcedure date: 09/03/2026\n'
     'Findings: two adenomas.\n\n' + COLO_BODY, '2026-09-03'),
    (HEAD + 'Colonoscopy report\nOutside colonoscopy:\n- Procedure date: 09/03/2026\n- Findings: two adenomas.\n\n'
     + COLO_BODY, '2026-09-03'),
    (HEAD + 'Colonoscopy report\n\nOutside colonoscopy:\n\nFacility: Synthetic Regional Hospital\n\n'
     'Procedure date: 09/03/2026\n\n' + COLO_BODY, '2026-09-03'),
    (HEAD + 'Colonoscopy report\nIndex colonoscopy:\nFacility: Synthetic Regional Hospital\nEndoscopist: Dr. B. Synthetic\n'
     'Procedure date: 04/02/2026\n\n' + COLO_BODY, '2026-04-02'),
    (HEAD + 'Colonoscopy report\nCancelled procedure:\nReason: inadequate preparation\nProcedure date: 11/04/2026\n\n'
     + COLO_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nPostponed colonoscopy:\nReason: patient request\nDate of service: 11/04/2026\n\n'
     + COLO_BODY, '2026-11-04'),
    # (b) a field on the label's row more than 80 characters before it (dates:4)
    (HEAD + 'EGD report\nPlanned procedure: colonoscopy with possible cold snare polypectomy under monitored anesthesia '
     'care Procedure Date: 11/04/2026\n' + EGD_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nNext procedure: colonoscopy, ' + FILLER + 'Date of service: 11/04/2026\n\n' + COLO_BODY,
     '2026-11-04'),
    # (c) the reader's own act-status words: a field on the row, the line above, a title, after the date
    (HEAD + 'Colonoscopy report\nCancelled colonoscopy: yes Procedure Date: 11/04/2026\n\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nCancelled procedure:\nProcedure date: 11/04/2026\n\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'Cancelled colonoscopy\nProcedure date: 11/04/2026\n\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'EGD report\nProcedure date: 11/04/2026 (cancelled)\n' + EGD_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nProcedure date: 11/04/2026 (postponed)\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nProcedure date: 11/04/2026    Status: cancelled\n' + COLO_BODY, '2026-11-04'),
)


class NarrowSourceRuleTests(DateAssertions, SimpleTestCase):
    """The ruled family: asked, never sent; the other occurrence's date quoted, never a member's answer; a date the
    document never states (the Elena incident's 1998-01-01) held."""

    def test_the_other_occurrence_s_date_is_asked_never_sent(self):
        for text, other in RULED:
            with self.subTest(text=shape(text)):
                self.assert_never(text, other)
                fact = date_fact(text)
                self.assertIn(fact.origin, ('missing', 'conflict'), fact.evidence)
                self.assertIsNone(fact.value)
                # never silenced: the label stays in the evidence, quoted
                self.assertTrue(any(other[5:7] + '/' + other[8:] + '/' + other[:4] in e for e in evidence_text(text)),
                                evidence_text(text))
                self.assertIn(context.UNPLACED_DATE_NOTE, fact.note)

    def test_a_member_s_answer_equal_to_the_other_occurrence_s_date_is_not_taken(self):
        for text, other in RULED:
            with self.subTest(text=shape(text)):
                self.assert_member_conflict(text, other)
                self.assert_member_conflict(text, ELENA_DATE)

    def test_a_row_attached_to_another_occurrence_far_back(self):
        # c2:6's last case: "Outside colonoscopy ..." attached to the label more than 80 characters back - asked at the
        # installed revision (the dated title speaks) but its 09/03 was a member's answer; within 80 it was not
        text = (HEAD + 'Colonoscopy report - 10/14/2026\nOutside colonoscopy at Synthetic Regional Medical Center with cold '
                'snare removal of two adenomas, procedure date: 09/03/2026\n' + COLO_PLAIN)
        self.assert_never(text, '2026-09-03')
        self.assert_question(text, '2026-10-14')
        self.assert_member_conflict(text, '2026-09-03')

    def test_a_dated_service_line_under_the_heading_is_that_occurrence_s(self):
        # once the label is asked, a dated service line in the same block (evidence a member's answer may agree with
        # when the note gives no date) would have given the index procedure's 04/02 as a member's answer
        text = (HEAD + 'Colonoscopy report\nIndex colonoscopy:\nFacility: Synthetic Regional Hospital\n'
                'Colonoscopy - 04/02/2026\nProcedure date: 04/02/2026\n\n' + COLO_PLAIN)
        self.assert_never(text, '2026-04-02')
        self.assert_member_conflict(text, '2026-04-02')
        self.assert_member_conflict(text, ELENA_DATE)
        # known limit (the prototype's stacked-label exemption, kept): a heading right over a line that is no field with
        # a value reads as a stacked header's label, so its block is not read - as at the installed revision
        self.assert_document(HEAD + 'Colonoscopy report\nIndex colonoscopy:\nColonoscopy - 04/02/2026\nFacility: '
                             'Synthetic Regional Hospital\nProcedure date: 04/02/2026\n\n' + COLO_PLAIN, '2026-04-02')
        # above the heading the line dates today's service: its date answers the question. The installed revision sent
        # the outside block's 09/03 and held this answer (an intended change: a member's 10/14 is now taken)
        text = (HEAD + 'Colonoscopy - 10/14/2026\nOutside colonoscopy:\nFacility: Synthetic Regional Hospital\n'
                'Procedure date: 09/03/2026\n\n' + COLO_PLAIN)
        self.assert_never(text, '2026-09-03')
        self.assert_member_date(text, '2026-10-14')
        self.assert_member_conflict(text, '2026-09-03')
        self.assert_member_conflict(text, ELENA_DATE)

    def test_nothing_is_silenced_and_no_date_is_released(self):
        # a status word beside a second label never releases the own labelled date: still asked (lens:278da78b45c0)
        text = HEAD + 'Date of service: 10/14/2026\nProcedure date: 11/04/2026 (cancelled)\n' + COLO_BODY
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value), ('conflict', None), fact.evidence)
        self.assertIn('Procedure date: 11/04/2026', evidence_text(text))
        self.assert_member_date(text, '2026-10-14')  # the own labelled date answers it
        self.assert_member_conflict(text, '2026-11-04')  # the cancelled procedure's date does not
        self.assert_member_conflict(text, ELENA_DATE)
        # a label inside an outside block beside another occurrence's: genuinely ambiguous - asked, never sent
        text = (HEAD + 'Colonoscopy report\nOutside colonoscopy:\nProcedure date: 09/03/2026\nDate of service: 10/14/2026\n'
                'Endoscopist: Dr. A. Synthetic\n\n' + COLO_PLAIN)
        self.assert_never(text, '2026-09-03', '2026-10-14')
        self.assert_member_conflict(text, '2026-09-03')
        self.assert_member_conflict(text, ELENA_DATE)


# (text, the date the installed revision documents and this change keeps): every one documented at 2b82889f
UNCHANGED = (
    (OFFICE_NOTE, '2026-10-20'),
    # a neutral heading the reader cannot place changes nothing (the owner's decision)
    (HEAD + 'Colonoscopy report\nPatient information:\nName: Synthetic, Alex\nDOB: 01/01/1998\n'
     'Date of service: 10/14/2026\n\n' + COLO_PLAIN, '2026-10-14'),
    (HEAD + 'Colonoscopy report\nEncounter details:\nFacility: Synthetic Endoscopy Center\nDate of service: 10/14/2026\n\n'
     + COLO_PLAIN, '2026-10-14'),
    (HEAD + 'Colonoscopy report\nPending colonoscopy:\nFacility: Synthetic Endoscopy Center\nDate of service: 10/14/2026\n\n'
     + COLO_PLAIN, '2026-10-14'),
    # a heading naming only a coded service, a stacked header's label, an empty date-of-service label alone on its line
    (HEAD + 'Endoscopy report\nColonoscopy:\nDate of procedure: 10/14/2026\nEndoscopist: Dr. A. Synthetic\n\n' + COLO_PLAIN,
     '2026-10-14'),
    (HEAD + 'Colonoscopy report\nPatient:\nDOB:\nSynthetic, Alex\n01/01/1998\nDate of service: 10/14/2026\n\n' + COLO_PLAIN,
     '2026-10-14'),
    (HEAD + 'Colonoscopy report\nDate of service:\nProcedure date: 10/14/2026\n\n' + COLO_PLAIN, '2026-10-14'),
    # history words beside the header, under it
    (HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nIndication: surveillance; two tubular adenomas removed at '
     'an outside colonoscopy on 08/17/2021.\n\n' + COLO_PLAIN, '2026-10-14'),
    # a word on the row more than 80 characters back that names no occurrence, opens a field about something else or
    # with a date of its own, or is a history word in another field's value: it governs no label
    (HEAD + 'Colonoscopy report\nLast name: Synthetic  ' + FILLER + 'Date of service: 10/14/2026\n\n' + COLO_PLAIN,
     '2026-10-14'),
    (HEAD + 'Colonoscopy report\nNext visit: 11/24/2026  ' + FILLER + 'Date of service: 10/14/2026\n\n' + COLO_PLAIN,
     '2026-10-14'),
    (HEAD + 'Colonoscopy report\nIndication: surveillance, history of polyps.  ' + FILLER + 'Date of service: 10/14/2026\n\n'
     + COLO_PLAIN, '2026-10-14'),
    (HEAD + 'Colonoscopy report\nOutside records: reviewed.  ' + FILLER + 'Date of service: 10/14/2026\n\n' + COLO_PLAIN,
     '2026-10-14'),
    (HEAD + 'Office visit\nVisit type: Follow-up  ' + FILLER + 'Date of service: 10/14/2026\n\n' + COLO_PLAIN, '2026-10-14'),
)


class NeutralAndOwnDatesAreUnchangedTests(DateAssertions, SimpleTestCase):
    """What the rule must not move: the controls the strict branch asked and the prototype's neutral headings (the
    owner: "a neutral heading the reader cannot place changes nothing")."""

    def test_documented_as_at_the_installed_revision(self):
        for text, value in UNCHANGED:
            with self.subTest(text=shape(text)):
                self.assert_document(text, value)
                self.assert_member_date(text, value)
                self.assert_member_conflict(text, ELENA_DATE)

    def test_the_known_limits_the_owner_kept(self):
        # "Recall", another discipline's undated title and a status field on the next line: as at 2b82889f
        for text, value in (
                (HEAD + 'Colonoscopy report\nRecall:\nProcedure date: 11/04/2026\n\n' + COLO_BODY, '2026-11-04'),
                (HEAD + 'Colonoscopy report\nRecall procedure\nProcedure date: 11/04/2026\n\n' + COLO_BODY, '2026-11-04'),
                (HEAD + 'Cardiology consultation\nDate of service: 10/09/2026\n\n' + COLO_BODY, '2026-10-09'),
                (HEAD + 'EGD report\nProcedure date: 11/04/2026\nStatus: Scheduled\n' + EGD_BODY, '2026-11-04')):
            with self.subTest(text=shape(text)):
                self.assert_document(text, value)


class StatusWordsAreDateQualifiersTests(DateAssertions, SimpleTestCase):
    """(c): on the label's line the status words are read exactly as the installed reading reads its date qualifiers,
    which it never passes over there (fr-dr:4) - so a status word opening another field after the date asks the date as
    "Follow-up instructions: given" does at the installed revision. Known limit: there the installed qualifier leaves the
    date 'unplaced' (a member's 10/14 answers it), and the rule's status word makes it 'beside' (held: an addendum)."""

    def test_known_limit_a_status_word_in_another_field_after_the_date(self):
        for line in ('Date of service: 10/14/2026    Cancellation policy: reviewed',
                     'Date of service: 10/14/2026    Cancelled on: 10/01/2026'):
            text = HEAD + 'Colonoscopy report\n' + line + '\n\n' + COLO_PLAIN
            with self.subTest(line=line):
                self.assert_never(text, '2026-10-14')
                self.assert_member_conflict(text, '2026-10-14')
        # the installed reading's own date qualifier there: asked, its date a member's answer (unchanged)
        text = HEAD + 'Colonoscopy report\nDate of service: 10/14/2026    Follow-up instructions: given\n\n' + COLO_PLAIN
        self.assert_never(text, '2026-10-14')
        self.assert_member_date(text, '2026-10-14')


class NarrowRuleCostTests(SimpleTestCase):
    """Refutation phase 2's cost rule: each part is computed once per text (the occurrence words in one pass, each
    section heading's verdict once), never a scan per label of a long line. Under the paste cap (400,000 characters) the
    analyze stage stays within its 60 s and a member's context request within its 15 s."""

    TEXTS = {
        'one line of own labels': (HEAD + 'DOS: 10/14/2026 ' * 24000, ('document', '2026-10-14')),
        'a heading line with a long tail over many labels': (
            HEAD + 'Outside colonoscopy:' + ' ' * 200000 + '\nFacility: X\n' + 'DOS: 09/03/2026\n' * 11000,
            ('missing', None)),
        'outside blocks': (HEAD + ('Outside colonoscopy:\n' + 'Facility: X\n' * 7 + 'Procedure date: 09/03/2026\n') * 2900,
                           ('missing', None)),
        'fields about something else before each label': (
            HEAD + ('Outside records: x. ' * 19 + 'DOS: 10/14/2026 ') * 970, ('document', '2026-10-14')),
        'status words before one label': (HEAD + 'cancelled ' * 38000 + 'Procedure Date: 11/04/2026\n', ('missing', None)),
    }

    def test_a_member_s_context_child_reads_each_within_its_bound(self):
        for name, (text, expected) in self.TEXTS.items():
            self.assertLess(len(text), settings.MAX_PASTE_CHARS, name)
            with self.subTest(text=name):
                started = time.perf_counter()
                facts = bounded.run_bounded(context.extract_context, text, seconds=settings.CONTEXT_REQUEST_SECONDS,
                                            memory_bytes=settings.BOUNDED_MEMORY_BYTES)
                self.assertLess(time.perf_counter() - started, settings.CONTEXT_REQUEST_SECONDS)
                self.assertEqual((facts['service_date'].origin, facts['service_date'].value), expected)

    def test_the_analyze_child_reads_the_heaviest_within_the_stage_deadline(self):
        for name in ('one line of own labels', 'a heading line with a long tail over many labels'):
            text, expected = self.TEXTS[name]
            with self.subTest(text=name):
                out = bounded.run_bounded(jobs._analyze_child, text, {}, settings.MAX_SERVICE_MENTIONS,
                                          seconds=settings.JOB_DEADLINE_SECONDS['analyze'],
                                          memory_bytes=settings.BOUNDED_MEMORY_BYTES)
                self.assertEqual((out[0]['service_date'].origin, out[0]['service_date'].value), expected)


class NarrowRuleRequestTests(EndToEnd):
    """End to end: the outside block's date never reaches a request, and the act done today is not excluded against
    it; a member's answer with that date is held (nothing sent), as a member's date the document never states is."""

    OUTSIDE = RULED[0][0]

    def test_the_outside_block_s_date_is_never_sent(self):
        encounter_id = self.finished(self.OUTSIDE)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assert_not_excluded(encounter_id, '45385')

    def test_a_member_s_answer_with_the_outside_date_is_held(self):
        self.assert_held(self.finished(self.OUTSIDE, service_date='2026-09-03'))
        self.assert_held(self.finished(self.OUTSIDE, service_date=ELENA_DATE))
