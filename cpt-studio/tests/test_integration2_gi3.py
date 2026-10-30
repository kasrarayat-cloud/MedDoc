"""CPT Studio GI round 3, the integration after fix round 2: a booking heading that names today asks (51(c)).

The dates fix owner left one shape as "needs an owner decision": under a plan, "Today's appointment" / "Visit date:
2026-10-06" beside the note's own "Date of service: 2026-10-05" - the booking word governed the visit date, so it was
dropped and 2026-10-05 was sent. Today's appointment may be this very visit, so by interpretation 51(c) (an uncertain
binding asks) the date under such a heading speaks against the note's own date: a conflict, asked, never dropped while
the contradicted date is sent. Where the note labels no date of its own it stays dropped, as the installed reading
dropped it (48(b)). Synthetic text only.
"""
from django.test import SimpleTestCase

from studio.gi import context
from tests.test_repairs_gi3_dates import HEADER, STRANGER, UNDATED, DateAsserts, date_fact, member

PLAN = 'Assessment and plan\nContinue iron. Return in 3 months.\n'


class BookingTodayTests(DateAsserts, SimpleTestCase):
    def test_a_booking_heading_naming_today_makes_the_visit_date_a_conflict(self):
        # (a heading that also names another occurrence explicitly - "Today's scheduled appointment", "Next
        # appointment, booked today" - governs as before: _names_occurrence_explicitly's closed class wins)
        for heading in ("Today's appointment", 'Appointment today', 'Appointment - today', "Today's appointments"):
            with self.subTest(heading=heading):
                self.assert_conflict(HEADER + PLAN + heading + '\nVisit date: 2026-10-06\n', '2026-10-05', '2026-10-06')

    def test_a_procedure_date_under_it_too(self):
        self.assert_conflict(HEADER + PLAN + "Today's appointment\nProcedure date: 2026-10-06\n", '2026-10-05',
                             '2026-10-06')

    def test_with_no_own_date_it_stays_dropped_as_installed(self):
        text = UNDATED + PLAN + "Today's appointment\nVisit date: 2026-10-06\n"
        self.assertEqual(date_fact(text).origin, 'missing')
        self.assertEqual(member(text, STRANGER), 'taken')  # never the only answer (48(b))

    def test_controls_other_booking_and_block_headings_still_govern(self):
        for heading in ('Next appointment', 'Appointment', 'Scheduling', 'Results reviewed today', 'Referral',
                        'Appointment for repeat colonoscopy today', "Next appointment, booked today",
                        "Today's scheduled appointment", 'Lab appointment today'):
            with self.subTest(heading=heading):
                self.assert_document(HEADER + PLAN + heading + '\nVisit date: 2026-11-18\n', '2026-10-05')

    def test_the_predicate(self):
        for line in ("Today's appointment", 'Appointment today', 'Scheduling today'):
            with self.subTest(line=line):
                self.assertTrue(context._names_booking_today(line))
        for line in ('Next appointment', "Today's visit", 'Results reviewed today', 'Appointment',
                     "Next appointment, booked today", 'Appointment for repeat colonoscopy today',
                     "Today's scheduled appointment", 'Lab appointment today'):
            with self.subTest(line=line):
                self.assertFalse(context._names_booking_today(line))
