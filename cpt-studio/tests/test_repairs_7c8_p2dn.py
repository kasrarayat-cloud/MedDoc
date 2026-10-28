"""Repair round 7c8, refutation phase 2, the service date narrowed (P2DN; studio/gi/context.py).

Refutation phase 2 attacked the integrated head 2fc8cde3d (whose reader a62a18c85 carries unchanged) and an independent
verifier reproduced every finding below: dates:0-8 and interplay:0 (a wrong service date sent to Corti, must-fix class
1) and ctxcost:0-1 (stage time, class 2). The P2DATES repair closed them with a header-block rule that asked the date of
nearly every real document (8 of the 11 live encounters, every PDF or Word upload), a capability loss the owner has
not accepted. This variant repairs them with rules of SOURCE that leave a normal header's labelled date documented,
and adds no header region, no header-label list, no check of header values and no title-word list:

N1  a document date reaches the request only from a date-of-service label's own value; a dated title, a bare "Date:"
    or "Date/Time:" line (clocked or not), a dated line naming the service and a letter's subject line are evidence
    only - they question a labelled date when they differ, and as the only dated text they are the evidence of a date
    asked (a dateless request), as at the installed revision 057a7d398 (dates:1, dates:3, dates:5);
N2  a date with a birth label before it (DOB, D.O.B., D-O-B, date of birth, birth date, birthday, birth, born, b., and
    their joined forms) is never a candidate's value, never agrees with a member date and is never in the evidence a
    member date is matched against; a field that opens with another field's label states no date of its own
    (dates:0, dates:2, interplay:0; the P2DATES skeptic's sk:3 and sk:4);
N3  a member date is taken only when it equals a date some candidate states as its own value; an empty or non-date
    date-of-service field is kept as evidence that reads no date, so any member date is held (sk:3);
N4  only a label read as the note's own (the closed list, at most with the name of a service this release codes) is
    ever the date; a label carrying words the reader cannot place is asked, as at 2fc8cde3d (sk:1, sk:2);
N5  the label's value is a date alone (a clock at most) up to the end of its own FIELD - the end of the line, a row's
    bar or the next field's label on the line; a bracket or words there make the date a question (dates:8 B3 and V1);
N6  POS's whitespace runs are possessive (ctxcost:0) and SETTING_STATEMENT_LIMIT bounds the setting statements read
    (ctxcost:1).

The pre-existing qualifier gaps the brief keeps as known limits (dates:4, 6, 7, 8's "Recall:" above and short row;
P2DATES sk:5, sk:6, sk:7) are pinned by the tests named ..._known_limit_..., recording today's behaviour: each still
documents the qualified date wherever 2fc8cde3d and 057a7d398 do. Synthetic text only; no network (the suite's
FakeProvider, answering only the selections whose quote the request's text holds).
"""
import json
import time
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from studio import bounded, jobs
from studio.gi import context
from studio.types import Span
from tests.test_repairs_7c8_context import DateAssertions
from tests.test_repairs_7c8_context3 import (COLO_BODY, COLO_PLAIN, EGD_BODY, ELENA_DATE, HEAD, OFFICE_BODY, VISIT_BODY,
                                             EndToEnd, date_fact, evidence_text)

BIRTH = '01/01/1998'
ROOT = Path(__file__).resolve().parent.parent


def note(text):
    return date_fact(text).note


# --- N1: sources ------------------------------------------------------------------------------------------------------

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
    'GI consultation: 10/09/2026', 'PCP note - 10/09/2026', 'Colonoscopy report - 10/09/2026'))


class EvidenceSourcesAreNeverSentTests(DateAssertions, SimpleTestCase):
    """dates:1, dates:3 and dates:5 (rule N1): round 3 read a clocked "Date/Time:" or "Date:" line (a fax's or a
    letter's timestamp), a letter's bare "Date:" over the encounter line it names, and a dated consultation title of
    another discipline as the note's own date - the installed revision 057a7d398 sent no date for any of them. The date
    was sent and the snare polypectomy done on 10/14 excluded against it. Each is evidence now: the date is asked."""

    def test_a_fax_s_or_a_letter_s_date_line_is_never_documented(self):
        for text in CLOCKED + (FAX,) + LETTERS:
            with self.subTest(top=text.splitlines()[1][:40] + ' / ' + text.splitlines()[2][:50]):
                self.assert_never(text, '2026-10-27')
                self.assertEqual(date_fact(text).origin, 'missing')
                self.assertIn(context.EVIDENCE_DATE_NOTE, note(text))
                self.assert_member_conflict(text, ELENA_DATE)

    def test_no_dated_title_is_ever_documented(self):
        # dates:5's T1 and T2, the other disciplines of its fuzz, and a title of this note too: a title is evidence
        for text in TITLES:
            with self.subTest(title=text.splitlines()[1]):
                self.assert_asked(text, text.splitlines()[1])
                self.assert_never(text, '2026-10-09')
                self.assert_member_date(text, '2026-10-09')  # the member's answer with the title's date agrees with it

    def test_the_encounter_line_s_date_answers_the_question(self):
        # a line naming the encounter and ending with its date is evidence the member's answer agrees with
        text = HEAD + 'Date: 10/27/2026\nProcedure: Colonoscopy on 10/14/2026\nDear Dr. Synthetic,\n' + COLO_BODY
        self.assert_asked(text, 'Date: 10/27/2026', 'Colonoscopy on 10/14/2026')
        self.assert_member_date(text, '2026-10-14')

    def test_beside_the_own_labelled_date_evidence_questions_it_only_when_it_differs(self):
        self.assert_document(HEAD + 'Colonoscopy report - 10/14/2026\nDate of service: 10/14/2026\n' + COLO_BODY,
                             '2026-10-14')
        self.assert_document(HEAD + 'Date: 10/14/2026\nDate of service: 10/14/2026\n' + COLO_BODY, '2026-10-14')
        self.assert_conflict(HEAD + 'Date: 10/27/2026\nDate of service: 10/14/2026\n' + COLO_BODY,
                             '2026-10-27', '2026-10-14')
        self.assert_conflict(HEAD + 'GI consultation - 10/09/2026\nDate of service: 10/14/2026\n' + COLO_BODY,
                             '2026-10-09', '2026-10-14')


class EvidenceSourcesAreNeverSentRequestTests(EndToEnd):
    """dates:1, dates:3 and dates:5 end to end: each request is dateless and the snare polypectomy done on 10/14 is
    never excluded against the fax's, the letter's or the other discipline's date."""

    def test_f1_f2_l1_l4_t1_t2(self):
        cases = (FAX, CLOCKED[0]) + LETTERS + TITLES[:2]
        for text in cases:
            with self.subTest(top=text.splitlines()[1][:40] + ' / ' + text.splitlines()[2][:40]):
                encounter_id = self.finished(text)
                self.assertEqual(self.dates_sent(encounter_id), [[]])
                self.assert_not_excluded(encounter_id, '45385')

    def test_the_member_s_answer_with_the_encounter_line_s_date_is_sent(self):
        text = HEAD + 'Date: 10/27/2026\nProcedure: Colonoscopy on 10/14/2026\nDear Dr. Synthetic,\n' + COLO_BODY
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': '2026-10-14'})
        self.assertEqual(self.dates_sent(encounter_id), [[], ['Date of service: 2026-10-14']])
        self.assertEqual(self.bucket(encounter_id, '45385'), 'selected')


# --- N2 and N3: a date of birth, a field that states no date of its own ---------------------------------------------

EMPTY_FIELD = (  # dates:0: an empty or non-date date-of-service field before a date of birth
    HEAD + 'Colonoscopy report - 10/14/2026\nPatient: Alex Synthetic DOS: DOB: 01/01/1998 MRN: 0000\n' + COLO_BODY,
    HEAD + 'Colonoscopy report - 10/14/2026\nDate of Service: Date of Birth: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nVisit Date: DOB: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Date: 10/14/2026\nDOS: N/A D.O.B. 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report - 10/14/2026\nProcedure date: TBD Birth date: 01/01/1998\n' + COLO_BODY,
    HEAD + 'Colonoscopy report - 10/14/2026\nDOS: pending (born 01/01/1998)\n' + COLO_BODY,
)
BIRTH_FORMS = ('DOB/Age', 'Age/DOB', 'DOB (age)', 'DOB & Age', 'Birth', 'Birthday', 'D-O-B', 'b.')
SERVICE_LINES = (  # dates:2 and interplay:0: a date of birth between the service's name and the line's own date
    HEAD + 'Procedure: EGD  Patient: Alex Synthetic  DOB: 01/01/1998  Date: 10/14/2026\n' + EGD_BODY,
    HEAD + 'EGD DOB 01/01/1998 10/14/2026\n' + EGD_BODY,
    HEAD + 'Date: 10/27/2026\nRe: Colonoscopy for Alex Synthetic (DOB 01/01/1998) on 10/14/2026\nDear Dr. Synthetic,\n'
    + COLO_BODY,
    HEAD + 'Colonoscopy - Synthetic, Alex (DOB 01/01/1998) - 10/14/2026\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nColonoscopy DOB 01/01/1998 10/14/2026\n' + COLO_BODY,
    HEAD + 'Date: 10/27/2026\nColonoscopy DOB 01/01/1998 10/14/2026\n' + COLO_BODY,
)
INTERPLAY = HEAD + 'Date of service: 10/14/2026\nRe: Colonoscopy - Synthetic, Alex (DOB 01/01/1998) - 10/14/2026\n' + COLO_BODY


class BirthDateIsNeverAServiceDateTests(DateAssertions, SimpleTestCase):
    """dates:0, dates:2, interplay:0 and the P2DATES skeptic's sk:4 (rule N2): an empty date-of-service field before a
    date of birth made the date of birth the label's value (round 2's unread value field); a dated line naming the
    service took the first date after the service's name as its own, a date of birth when one stood there (round 3's
    gap rule); a birth label the reader did not know ("DOB/Age", "DOB (age)", "Birthday") or a word before the date
    passed the date of birth as the field's value. Each time a member's 1998-01-01 agreed with the evidence, was taken
    and sent, and the act done on 10/14 was excluded against it - while the member's correct 10/14 was held."""

    def assert_no_birth_date(self, text):
        fact = date_fact(text)
        self.assertNotEqual((fact.origin, fact.value), ('document', ELENA_DATE))
        self.assert_member_conflict(text, ELENA_DATE)
        self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))

    def test_an_empty_date_of_service_field_never_takes_the_date_of_birth(self):
        for text in EMPTY_FIELD:
            with self.subTest(line=text.splitlines()[2][:60]):
                self.assert_no_birth_date(text)
                self.assert_member_date(text, '2026-10-14')  # the date the note states still answers the question

    def test_joined_and_bracketed_birth_labels_and_a_word_before_the_date(self):
        # sk:4: the date of birth after a birth label the reader did not know, with or without a word before it
        for form in BIRTH_FORMS:
            for shape in ('Colonoscopy report - 10/14/2026\nPatient: Alex Synthetic DOS: {f} 01/01/1998 MRN 0000\n',
                          'Colonoscopy report\nDate of service: 10/14/2026\nVisit Date: TBD {f} 01/01/1998\n',
                          'Colonoscopy report - 10/14/2026\nDOS: -- {f} 01/01/1998\n'):
                text = HEAD + shape.format(f=form) + COLO_BODY
                with self.subTest(line=text.splitlines()[2][:60]):
                    self.assert_no_birth_date(text)
                    self.assert_member_date(text, '2026-10-14')

    def test_a_service_line_s_own_date_is_its_only_date_that_is_no_date_of_birth(self):
        for text in SERVICE_LINES + (INTERPLAY,):
            with self.subTest(line=text.splitlines()[1][:60] + ' / ' + text.splitlines()[2][:40]):
                self.assert_no_birth_date(text)
                self.assert_member_date(text, '2026-10-14')

    def test_joined_birth_labels_on_a_service_or_subject_line(self):
        # sk:4's joined forms where no field opens a value: a date of birth between the service's name and the line's own
        # date is never the line's value and never in its evidence, whatever form its birth label takes
        for form in BIRTH_FORMS:
            for shape in ('Colonoscopy - Synthetic, Alex ({f} 01/01/1998) - 10/14/2026\n',
                          'Date: 10/27/2026\nRe: Colonoscopy for Alex Synthetic, {f} 01/01/1998, on 10/14/2026\n'):
                text = HEAD + shape.format(f=form) + COLO_BODY
                with self.subTest(line=shape.format(f=form).splitlines()[-1]):
                    self.assert_no_birth_date(text)
                    self.assert_member_date(text, '2026-10-14')

    def test_interplay_the_subject_line_agrees_with_the_own_labelled_date(self):
        # interplay:0: the subject line's own date is 10/14, so the note's own labelled date is documented (it was a
        # question - an unread value of the subject line spoke against it)
        self.assert_document(INTERPLAY, '2026-10-14')

    def test_a_date_of_birth_heading_its_column_or_the_line_above_is_no_value(self):
        self.assert_no_birth_date(HEAD + 'Date of service: 10/14/2026\nProcedure | DOB\nColonoscopy | 01/01/1998\n'
                                  + COLO_BODY)
        self.assert_no_birth_date(HEAD + 'Colonoscopy report - 10/14/2026\nDate of birth:\n01/01/1998\n' + COLO_BODY)

    def test_a_line_with_two_dates_states_none(self):
        text = HEAD + 'Re: EGD referral 09/01/2026 10/14/2026\n' + EGD_BODY
        self.assert_member_conflict(text, '2026-09-01')
        self.assert_member_conflict(text, ELENA_DATE)

    def test_the_evidence_never_reads_a_date_of_birth(self):
        # whatever span holds one (a stored context, a span another reader kept): only the dates after no birth label
        for quoted in ('Re: Colonoscopy - Synthetic, Alex (DOB 01/01/1998) - 10/14/2026', 'D.O.B. 01/01/1998 10/14/2026',
                       'Date of birth: 01/01/1998; colonoscopy 10/14/2026', 'born on 01/01/1998, seen 10/14/2026',
                       'DOB/Age 01/01/1998 10/14/2026'):
            with self.subTest(quoted=quoted):
                self.assertEqual(context._date_readings((Span(0, len(quoted), quoted),)), {'2026-10-14'})

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
        # a labelled date beside a date of birth on its line is the note's own (the next field's label ends its field)
        self.assert_document(HEAD + 'Colonoscopy report\nDOS: 10/14/2026 DOB: 01/01/1998\n' + COLO_BODY, '2026-10-14')


EMPTY_LABELS = (  # sk:3 and N3: a date-of-service field another field opens, or anything but its own value opens
    HEAD + 'Colonoscopy report\nDate of Service: Referral date: 10/13/2026\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nDOS: N/A Referral date: 10/13/2026\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nDate of service: Admission date: 10/13/2026\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nProcedure date: see 10/13/2026\n' + COLO_BODY,
)


class EmptyDateFieldIsKeptTests(DateAssertions, SimpleTestCase):
    """The P2DATES skeptic's sk:3 and rule N3: a date-of-service field that states no date of its own - another field's
    label opens it ("Date of Service: Referral date: 10/13/2026"), or a word does ("DOS: N/A Referral date: ...") - is
    kept as evidence that reads no date: every member date is held, the other field's date included (at a62a18c85 a
    member's 2026-10-13, the referral date, agreed with the label's field and was taken and sent). It is never dropped
    with nothing left behind (round 2's rule A), which let any member date be taken."""

    def test_every_member_date_is_held(self):
        for text in EMPTY_LABELS:
            with self.subTest(line=text.splitlines()[2]):
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('missing', None))
                self.assertTrue(fact.evidence, 'the label is kept')
                self.assertFalse(any('10/13' in quoted for quoted in evidence_text(text)), evidence_text(text))
                for member in (ELENA_DATE, '2026-10-13', '2026-10-14'):
                    self.assert_member_conflict(text, member)

    def test_the_date_another_candidate_states_still_answers(self):
        text = HEAD + 'Colonoscopy report - 10/14/2026\nDate of Service: Referral date: 10/13/2026\n' + COLO_BODY
        self.assert_member_date(text, '2026-10-14')
        self.assert_member_conflict(text, '2026-10-13')
        self.assert_member_conflict(text, ELENA_DATE)

    def test_controls(self):
        # a field with no digit at all keeps nothing, as before; an unread value of its own is kept as before
        text = HEAD + 'Colonoscopy report\nDate of service: N/A\n' + COLO_BODY
        self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
        text = HEAD + 'Colonoscopy report\nDate of service: 20-Oct-26\n' + COLO_BODY
        self.assert_asked(text, 'Date of service: 20-Oct-26')
        self.assert_member_conflict(text, '2026-10-20')


class BirthDateRequestTests(EndToEnd):
    """dates:0, dates:2, interplay:0, sk:3 and sk:4 end to end: nothing is sent for the member's 1998-01-01 (a held
    member conflict), and no act is excluded against it; the member's correct date is taken and sent."""

    def test_e_a_e_b_e_c_created_with_the_member_date(self):
        for text in EMPTY_FIELD[:3]:
            with self.subTest(line=text.splitlines()[2][:50]):
                encounter_id = self.finished(text, service_date=ELENA_DATE)
                self.assert_held(encounter_id)
                self.assert_never_sent(encounter_id, ELENA_DATE)

    def test_e_a2_the_member_date_entered_afterwards(self):
        encounter_id = self.finished(EMPTY_FIELD[0])
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assert_never_sent(encounter_id, ELENA_DATE)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assertNotEqual(self.bucket(encounter_id, '45385'), 'excluded')

    def test_d1_d2_d3_a_date_of_birth_on_the_service_line(self):
        d1 = self.finished(SERVICE_LINES[0], service_date=ELENA_DATE)
        self.assert_held(d1)
        d3 = self.finished(SERVICE_LINES[2], service_date=ELENA_DATE)
        self.assert_held(d3)
        d2 = self.finished(SERVICE_LINES[0])
        self.assertEqual(self.dates_sent(d2), [[]])
        self.set_context(d2, {'service_date': '2026-10-14'})
        self.assertEqual(self.dates_sent(d2), [[], ['Date of service: 2026-10-14']])
        self.assertEqual(self.bucket(d2, '43239'), 'selected')
        self.set_context(d2, {'service_date': ELENA_DATE})
        self.assert_never_sent(d2, ELENA_DATE)
        self.assert_not_excluded(d2, '43239')

    def test_interplay_0(self):
        held = self.finished(INTERPLAY, service_date=ELENA_DATE)
        self.assert_held(held)
        own = self.finished(INTERPLAY)
        self.assertEqual(self.dates_sent(own), [['Date of service: 2026-10-14']])
        self.assertEqual(self.bucket(own, '45385'), 'selected')

    def test_sk3_and_sk4(self):
        for text in (EMPTY_LABELS[0], EMPTY_LABELS[1],
                     HEAD + 'Colonoscopy report - 10/14/2026\nPatient: Alex Synthetic DOS: DOB/Age 01/01/1998 MRN 0000\n'
                     + COLO_BODY):
            with self.subTest(line=text.splitlines()[2][:50]):
                encounter_id = self.finished(text, service_date=ELENA_DATE)
                self.assert_held(encounter_id)
        encounter_id = self.finished(HEAD + 'Colonoscopy report\nDate of service: 10/14/2026\nVisit Date: TBD DOB (age) '
                                     '01/01/1998\n' + COLO_BODY)
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assert_never_sent(encounter_id, ELENA_DATE)
        self.assertNotEqual(self.bucket(encounter_id, '45385'), 'excluded')


# --- N4: the label ----------------------------------------------------------------------------------------------------

UNPLACED_LABELS = (  # the P2DATES skeptic's sk:1 inputs, and its sk:2 (a)-(c) (asked at 2fc8cde3d, sent by P2DATES)
    HEAD + 'GI follow-up visit\nName: Alex Synthetic | Initial visit date: 01/15/2025 | MRN: 0000\n\n' + VISIT_BODY,
    HEAD + 'Patient: Synthetic, Alex    Cancelled procedure date: 11/04/2026\n\n' + COLO_BODY,
    HEAD + 'Name: Alex Synthetic | Recall visit date: 11/04/2026 | MRN: 0000\n\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    Referral visit date: 09/01/2026\n\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998, outside records reviewed\n'
           'Procedure date: 09/03/2026\n\n' + COLO_BODY,
    HEAD + 'Colonoscopy report\nPatient: Synthetic, Alex    DOB: 01/01/1998 outside    Procedure date: 09/03/2026\n\n'
    + COLO_BODY,
    HEAD + 'EGD report\nPatient: Synthetic, Alex    DOB: 01/01/1998    Status: Scheduled\nProcedure date: 11/04/2026\n\n'
    + EGD_BODY,
)


class OnlyALabelReadAsTheNoteSOwnTests(DateAssertions, SimpleTestCase):
    """Rule N4 (the P2DATES skeptic's sk:1 and sk:2, regressions of P2DATES' dfb3181de, never of this head): only a
    label READ as the note's own - the closed list of labels, at most with the name of a service this release codes - is
    ever the date. A label carrying words the reader cannot place ("Initial visit date", "Cancelled procedure date") or
    one its line or the line above may qualify is asked, as at 2fc8cde3d."""

    def test_a_label_the_reader_cannot_place_is_asked(self):
        for text in UNPLACED_LABELS:
            with self.subTest(line=[line for line in text.splitlines() if 'date' in line.lower()][0][:70]):
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('missing', None), fact.evidence)
                self.assertIn(context.UNPLACED_DATE_NOTE, fact.note)

    def test_controls_the_closed_list_and_a_coded_service_s_name(self):
        for line, value in (('Date of service: 10/14/2026', '2026-10-14'), ('Colonoscopy procedure date: 10/14/2026',
                                                                            '2026-10-14'),
                            ("Today's visit date: 10/20/2026", '2026-10-20'), ('DOS: 2026-10-14', '2026-10-14')):
            with self.subTest(line=line):
                self.assert_document(HEAD + 'Patient: Synthetic, Alex    ' + line + '\n\n' + COLO_BODY, value)


class OnlyALabelReadAsTheNoteSOwnRequestTests(EndToEnd):
    def test_sk1_inputs_send_no_date(self):
        for text in UNPLACED_LABELS[:4]:
            with self.subTest(line=text.splitlines()[1][:50]):
                encounter_id = self.finished(text)
                self.assertEqual(self.dates_sent(encounter_id), [[]])


# --- N5: the label's own field ----------------------------------------------------------------------------------------

NOT_ALONE = (  # dates:8 B3 and V1, and the brackets and words of its fuzz after the date in the label's own field
    (HEAD + 'GI office visit\nProcedure date: 11/04/2026 (pending authorization)\n' + OFFICE_BODY, '2026-11-04'),
    (HEAD + 'EGD report\nProcedure date: 11/04/2026 (cancelled)\n' + EGD_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nProcedure date: 11/04/2026 (postponed)\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nDate of service: 11/04/2026 - pending\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nDate of service: 11/04/2026 booked\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nDate of service: 11/04/2026    Recall colonoscopy\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nDate of service: 11/04/2026, at Synthetic Regional Hospital\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nProcedure date: 09/03/2026; outside colonoscopy.\n\n' + COLO_BODY, '2026-09-03'),
    (HEAD + 'Colonoscopy report\nDate of service: 11/04/2026 cancelled Status: closed\n' + COLO_BODY, '2026-11-04'),
    (HEAD + 'Colonoscopy report\nDate of service: 10/14/2026 to 10/15/2026\n' + COLO_BODY, '2026-10-14'),
)
ALONE = (  # the date alone, a clock at most, up to the field's end: the line's end, a row's bar or the next label
    'Date of service: 10/14/2026', 'Date of service: 10/14/2026   ', 'Date of service: 10/14/2026.',
    'Date of service: 10/14/2026 09:15', 'Date/Time of Service: 10/14/2026 at 9:15 AM',
    'Date of service: 10/14/2026 | Provider: Dr. A. Synthetic', 'Service date 14 October 2026  |  Endoscopist A. Synthetic',
    'DOS: 10/14/2026 MRN: 0000', 'Date of service: 10/14/2026    Place of service: Office',
    'Date of service: 10/14/2026\tReferring physician: Dr. B. Synthetic', 'Date of procedure: 2026-10-14\r',
)


class LabelSOwnFieldTests(DateAssertions, SimpleTestCase):
    """dates:8 B3 and V1 (rule N5): "Procedure date: 11/04/2026 (pending authorization)" in an office visit, or "(cancelled)"
    in an EGD report, documented a planned procedure's date - sent with 99213 ready, and 43239 excluded at 057a7d398.
    The label's value is a date alone, a clock at most, up to the end of its own FIELD: the end of the line, a row's
    cell bar or the next field's label on the same line. A bracket or words there make the date a question - asked,
    never sent, the date kept as evidence the member's answer may agree with. The structure only: no word list."""

    def test_a_bracket_or_words_after_the_date_ask_it(self):
        for text, value in NOT_ALONE:
            with self.subTest(line=text.splitlines()[2]):
                self.assert_never(text, value)
                fact = date_fact(text)
                self.assertEqual((fact.origin, fact.value), ('missing', None), fact.evidence)
                self.assertIn(context.FIELD_DATE_NOTE, fact.note)
                self.assert_member_date(text, value)  # its date is evidence the member's answer agrees with
                self.assert_member_conflict(text, ELENA_DATE)

    def test_controls_the_date_alone_in_its_field(self):
        for line in ALONE:
            with self.subTest(line=line):
                value = '2026-10-14'
                self.assert_document(HEAD + 'Colonoscopy report\n' + line + '\n' + COLO_BODY, value)

    def test_beside_the_own_labelled_date_it_speaks(self):
        # a labelled date with more in its field questions the own labelled date when it differs, agrees otherwise
        self.assert_conflict(HEAD + 'Date of service: 10/14/2026\nProcedure date: 11/04/2026 (cancelled)\n' + COLO_BODY,
                             '2026-10-14', '2026-11-04')
        self.assert_document(HEAD + 'Date of service: 10/14/2026\nProcedure date: 10/14/2026 (completed)\n' + COLO_BODY,
                             '2026-10-14')


class LabelSOwnFieldRequestTests(EndToEnd):
    def test_b3_and_v1_send_no_date(self):
        b3 = self.finished(NOT_ALONE[0][0])
        self.assertEqual(self.dates_sent(b3), [[]])
        v1 = self.finished(NOT_ALONE[1][0])
        self.assertEqual(self.dates_sent(v1), [[]])
        self.assert_not_excluded(v1, '43239')


# --- N6: cost ---------------------------------------------------------------------------------------------------------

class SettingReaderCostTests(SimpleTestCase):
    """ctxcost:0 and ctxcost:1 (class 2, pre-existing at 057a7d398): POS's two adjacent optional whitespace runs were
    quadratic ('POS' + 96,000 spaces overran the analyze stage's 60 s, 48,000 a member's POST /context), and a repeated
    setting phrase ('HOPD ' x 70,000) cost a statement check each, so a member's POST /context overran its 15 s after
    the pipeline had succeeded. POS's runs are possessive; past SETTING_STATEMENT_LIMIT phrases the setting is asked."""

    POS_TEXT = (HEAD + 'Date of service: 10/14/2026\nOffice visit.\nPOS' + ' ' * 96000 + 'x\n'
                + 'Established patient office visit.\nTotal time on the date of the encounter was 24 minutes.\n')
    HOPD_TEXT = HEAD + 'Date of service: 10/14/2026\nOffice visit. HOPD ' + 'HOPD ' * 70000 + '\n' + VISIT_BODY

    def test_the_place_of_service_pattern_is_linear(self):
        started = time.perf_counter()
        self.assertIsNone(context.POS.search('POS' + ' ' * 16000 + 'x'))  # 3.3 s at 2fc8cde3d
        self.assertLess(time.perf_counter() - started, 0.5)
        self.assertEqual(context.POS.search('Place of service (POS) code: 11').group('code'), '11')

    def test_the_analyze_child_reads_the_spaces_within_its_deadline(self):
        out = bounded.run_bounded(jobs._analyze_child, self.POS_TEXT, {}, settings.MAX_SERVICE_MENTIONS,
                                  seconds=settings.JOB_DEADLINE_SECONDS['analyze'],
                                  memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertEqual(out[0]['service_date'].value, '2026-10-14')

    def test_a_member_s_context_child_reads_the_repeated_setting_within_its_bound(self):
        started = time.perf_counter()
        facts = bounded.run_bounded(context.extract_context, self.HOPD_TEXT, seconds=settings.CONTEXT_REQUEST_SECONDS,
                                    memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertLess(time.perf_counter() - started, settings.CONTEXT_REQUEST_SECONDS)
        self.assertEqual((facts['setting'].origin, facts['setting'].value), ('missing', None))
        self.assertIn(str(context.SETTING_STATEMENT_LIMIT), facts['setting'].note)

    def test_controls_a_few_setting_statements_are_read(self):
        text = HEAD + 'Date of service: 10/14/2026\n' + 'Office visit. ' * 3 + '\n' + VISIT_BODY
        self.assertEqual(context.extract_context(text)['setting'].value, 'office')
        # past the limit (200; a fixed count, never one sized by the constant) the setting is asked
        self.assertEqual(context.SETTING_STATEMENT_LIMIT, 200)
        text = HEAD + 'Date of service: 10/14/2026\n' + 'Office visit. ' * 201
        self.assertEqual(context.extract_context(text)['setting'].origin, 'missing')


# --- the live shapes --------------------------------------------------------------------------------------------------

class VerificationDocumentsTests(SimpleTestCase):
    """Must hold: each verification document's service date is read as its manifest expects, and the live shapes - a
    header whose labelled date stands alone, ordinary header lines around it - keep their documented date."""

    def test_each_document_s_service_date_is_the_manifest_s(self):
        manifest = json.loads((ROOT / 'ops' / 'verification' / 'manifest.json').read_text())
        for entry in manifest['documents']:
            expected = entry['expected_context']['service_date']
            text = (ROOT / 'ops' / 'verification' / entry['source']).read_text()
            with self.subTest(document=entry['id']):
                fact = date_fact(text)
                self.assertIn(fact.origin, expected['origin_in'])
                if 'value_in' in expected:
                    self.assertIn(fact.value, expected['value_in'])


# --- known limits (P2DN "Known limits this variant keeps"): today's behaviour, recorded ------------------------------

class KnownLimitTests(DateAssertions, SimpleTestCase):
    """Pre-existing qualifier gaps where the lines around a labelled date say it is another occurrence's date. Closing
    them by structure (a header region) asked the date of most documents (P2DATES, wip/7c8-p2dates); closing them by
    vocabulary has leaked in every refutation round. They stay as at 2fc8cde3d and 057a7d398 - the qualified date is
    documented and sent - and each is recorded in ARCHITECTURE 5.2. A change here is a change of a known limit: say so."""

    def test_dates4_known_limit_a_long_flattened_row(self):
        self.assert_document(HEAD + 'EGD report\nPlanned procedure: colonoscopy with possible cold snare polypectomy under '
                             'monitored anesthesia care Procedure Date: 11/04/2026\n' + EGD_BODY, '2026-11-04')

    def test_dates6_known_limit_a_heading_above_a_block_or_a_list(self):
        self.assert_document(HEAD + 'Colonoscopy report\nOutside colonoscopy:\nFacility: Synthetic Regional Hospital\n'
                             'Procedure date: 09/03/2026\nFindings: two adenomas.\n\n' + COLO_BODY, '2026-09-03')
        self.assert_document(HEAD + 'Colonoscopy report\nOutside colonoscopy:\n- Procedure date: 09/03/2026\n'
                             '- Findings: two adenomas.\n\n' + COLO_BODY, '2026-09-03')

    def test_dates7_known_limit_another_field_beside_the_label(self):
        self.assert_document(HEAD + 'EGD report\nProcedure date: 11/04/2026\nStatus: Scheduled\n' + EGD_BODY, '2026-11-04')
        self.assert_document(HEAD + 'Colonoscopy report\nProcedure date: 09/03/2026\nFacility: Outside hospital\n\n'
                             + COLO_BODY, '2026-09-03')
        self.assert_document(HEAD + 'EGD report\nProcedure date: 11/04/2026\nDOB: 01/01/1998    Status: Scheduled\n\n'
                             + EGD_BODY, '2026-11-04')  # P2DATES sk:2 (d)

    def test_dates8_known_limit_a_qualifier_field_above_or_a_short_row(self):
        for above in ('Recall:', 'Cancelled procedure:'):
            self.assert_document(HEAD + 'Colonoscopy report\n' + above + '\nProcedure date: 11/04/2026\n\n' + COLO_BODY,
                                 '2026-11-04')
        self.assert_document(HEAD + 'Colonoscopy report\nCancelled colonoscopy: yes Procedure Date: 11/04/2026\n\n'
                             + COLO_BODY, '2026-11-04')

    def test_sk5_known_limit_a_title_above(self):
        self.assert_document(HEAD + 'Cancelled colonoscopy\nProcedure date: 11/04/2026\n\n' + COLO_BODY, '2026-11-04')
        self.assert_document(HEAD + 'Colonoscopy report\nRecall procedure\nProcedure date: 11/04/2026\n\n' + COLO_BODY,
                             '2026-11-04')

    def test_sk6_known_limit_a_status_setting_or_provider_beside_the_label(self):
        for line in ('Patient status: pending authorization', 'Setting: cancelled',
                     'Provider: Dr. A. Synthetic (procedure postponed)'):
            self.assert_document(HEAD + 'EGD report\nProcedure date: 11/04/2026\n' + line + '\n\n' + EGD_BODY,
                                 '2026-11-04')

    def test_sk7_known_limit_another_discipline_s_undated_title(self):
        self.assert_document(HEAD + 'Cardiology consultation\nDate of service: 10/09/2026\n\n' + COLO_BODY, '2026-10-09')
