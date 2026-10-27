"""Repairs made while integrating repair round ec5 (session ec5e7910), for issues a cluster handed back outside its
territory. Synthetic text only."""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.validation import checks

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
NOTE = BANNER + '{line}\nOffice follow-up visit for rectal bleeding.\nMedical decision making: moderate.\n'


def date_wording(text):
    facts = gi_context.extract_context(text)
    fact = facts.get('service_date')
    try:
        day = date.fromisoformat(fact.value) if fact is not None and fact.origin in checks.DOCUMENTED else None
    except (TypeError, ValueError):
        day = None
    state = checks.service_date_state(facts, day)
    check = checks.service_date_check(state)
    return state, check.status, check.detail


class UnusableLabelledDateWordingTests(SimpleTestCase):
    """CONTEXT handed back new:missing-date-wording: a labelled date kept as evidence but not usable as the date of
    service was worded "No date of service is documented" in the check and the question's reason."""

    def test_a_kept_labelled_date_is_quoted_never_called_undocumented(self):
        for line in ('Date of service: Tuesday, October 20, 2026', 'Referring visit date: 09/30/2026.',
                     'Date of service: 2026-02-30'):
            with self.subTest(line=line):
                state, status, detail = date_wording(NOTE.format(line=line))
                self.assertIsNone(state.value)
                self.assertEqual(status, 'fail')
                self.assertNotIn('No date of service is documented', detail)
                self.assertIn('No usable date of service was read', detail)

    def test_control_a_note_without_any_date_is_still_undocumented(self):
        state, status, detail = date_wording(NOTE.format(line='Chief complaint: rectal bleeding.'))
        self.assertEqual(status, 'fail')
        self.assertIn('No date of service is documented', detail)

    def test_control_a_readable_date_is_documented(self):
        _, status, detail = date_wording(NOTE.format(line='Date of service: 2026-10-20'))
        self.assertEqual(status, 'pass')
        self.assertIn('2026-10-20 is documented', detail)
