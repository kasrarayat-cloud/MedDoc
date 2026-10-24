"""Residual routing risks the round-1 routing repair named in its own report, closed fail-closed.

Each case was measured as 'performed' before the change. Synthetic text only.
"""
from django.test import SimpleTestCase

from studio.gi.detect import status_for_span

DOS = 'Date of service: 2026-10-21\n'


def status(text, phrase='Colonoscopy'):
    start = text.index(phrase)
    return status_for_span(text, start, start + len(phrase))[0]


class ToIsOnlyAnExtentTests(SimpleTestCase):
    def test_a_purpose_or_future_after_to_does_not_let_the_section_speak(self):
        for line in ('Findings: Colonoscopy to come.', 'Findings: Colonoscopy to be scheduled.',
                     'Findings: Colonoscopy to check for recurrence.'):
            with self.subTest(line=line):
                self.assertNotEqual(status(DOS + line + '\n'), 'performed')

    def test_an_extent_after_to_still_describes_the_service(self):
        for line in ('Findings: Colonoscopy to the cecum. Normal colon.', 'Procedure: Colonoscopy to the terminal ileum.',
                     'Procedure: Colonoscopy to 40 cm.', 'Procedure: Colonoscopy to approximately 60 cm.'):
            with self.subTest(line=line):
                self.assertEqual(status(DOS + line + '\n'), 'performed')


class DeniedPreconditionTests(SimpleTestCase):
    def test_no_prep_is_not_a_denied_finding(self):
        self.assertNotEqual(status(DOS + 'Procedure: Colonoscopy, no prep.\n'), 'performed')
        self.assertNotEqual(status(DOS + 'Procedure: Colonoscopy, no consent obtained.\n'), 'performed')

    def test_a_denied_finding_still_explains_its_negation(self):
        self.assertEqual(status(DOS + 'Procedure: Colonoscopy, no polyps.\n'), 'performed')


class ShortDenyingLineTests(SimpleTestCase):
    def test_a_short_refusal_after_a_bare_service_line_holds_it(self):
        for line in ('Patient declined.', 'Pt refused.', 'Patient refused today.'):
            with self.subTest(line=line):
                self.assertNotEqual(status(DOS + 'Procedure: Colonoscopy.\n' + line + '\n'), 'performed')

    def test_a_refused_other_act_or_a_denied_finding_does_not(self):
        for line in ('Patient declined sedation.', 'No complications.', 'No polyps were seen.'):
            with self.subTest(line=line):
                self.assertEqual(status(DOS + 'Procedure: Colonoscopy.\n' + line + '\n'), 'performed')
