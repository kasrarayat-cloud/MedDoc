"""gi2 triage, rule U (session 7c8d38da integration): an own labelled date that stands only after the note's body, where
the note's header dates another occurrence, is asked - never sent. The installed reader (2b82889f) sent the later date:
the body's procedure is dated by the header, and the date after the body may date only what was written after it (522
constructed texts of the broad corpus; 0 existing). Synthetic text only; no database, no provider."""
from django.test import SimpleTestCase

from tests.test_repairs_7c8_context import DateAssertions

TOP = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT\nColonoscopy Report (fictional)\n'
BODY = ('\nTechnique:\nThe colonoscope was advanced to the cecum.\n\nFindings:\n'
        'A 6 mm sigmoid polyp was removed with a cold snare.\n\n')
AFTER = 'Addendum\nDate of service: 10/21/2026\nPathology was reviewed with the patient by telephone.\n'


def report(header, after=AFTER):
    return TOP + header + BODY + after


class AnotherOccurrenceHeaderTests(DateAssertions, SimpleTestCase):
    def test_the_date_after_the_body_is_asked_never_sent(self):
        for header in ('Outside Procedure date: 10/14/2026\nPatient: Synthetic, Alex (fictional)\n',
                       'Procedure date: 10/14/2026 (outside facility)\nPatient: Synthetic, Alex (fictional)\n',
                       'Index procedure date: 10/14/2026\nPatient: Synthetic, Alex (fictional)\n',
                       'Index DOS: 10/14/2026\nPatient: Synthetic, Alex (fictional)\n'):
            with self.subTest(header=header):
                text = report(header)
                self.assert_never(text, '2026-10-21', '2026-10-14')
                self.assert_member_date(text, '2026-10-21')    # a member's answer equal to the own label is taken
                self.assert_member_conflict(text, '2026-10-14')  # the header's other occurrence is never an answer

    def test_controls_where_the_header_states_the_note_s_own_date(self):
        for header in ('Date of service: 10/21/2026\nOutside Procedure date: 10/14/2026\n',
                       'Outside Procedure date: 10/14/2026\nDate of Service: TBD\n'):
            with self.subTest(header=header):
                self.assert_document(report(header), '2026-10-21')

    def test_control_a_later_header_date_is_a_planned_occurrence(self):
        self.assert_document(report('Repeat colonoscopy, Procedure date: 10/14/2029 (planned)\n'), '2026-10-21')

    def test_control_no_body_heading_after_the_header_date(self):
        text = TOP + 'Outside Procedure date: 10/14/2026\nThe colonoscope was advanced to the cecum.\n' + AFTER
        self.assert_document(text, '2026-10-21')

    def test_control_the_app_s_own_addendum_still_settles_the_date(self):
        app_addendum = ('\nADDENDUM (revision 2, added 2026-10-22 10:00 UTC)\nDate of service: 10/21/2026\n'
                        'The date of service was confirmed.\n')
        self.assert_document(report('Outside Procedure date: 10/14/2026\n', after=app_addendum), '2026-10-21')
