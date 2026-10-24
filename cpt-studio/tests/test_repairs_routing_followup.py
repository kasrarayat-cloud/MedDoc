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


class CheckboxTests(SimpleTestCase):
    """Extraction now writes checkboxes as glyphs (☐ unchecked, ☒/☑/✓ checked). An unchecked box denies its
    item; the box nearest before an item on its line governs it."""

    def test_an_unchecked_box_negates_its_item(self):
        for text in (DOS + 'Procedure: Colonoscopy to the cecum. Findings: polyp.\n☐ Biopsy\n',
                     DOS + 'Procedure: Colonoscopy to the cecum.\nInterventions:\n☐ Biopsy\n☒ Cold snare polypectomy\n',
                     DOS + 'Procedure: Colonoscopy to the cecum. Findings: polyp.\n[ ] Biopsy\n'):
            with self.subTest(text=text):
                self.assertEqual(status(text, 'Biopsy'), 'negated')

    def test_the_nearest_box_governs_and_a_checked_box_does_not_negate(self):
        line = DOS + 'Procedure: Colonoscopy to the cecum.\nInterventions:\n☐ Biopsy ☒ Cold snare polypectomy\n'
        self.assertEqual(status(line, 'Biopsy'), 'negated')
        self.assertNotEqual(status(line, 'Cold snare polypectomy'), 'negated')
        self.assertEqual(status(DOS + 'Procedure: Colonoscopy to the cecum. Findings: polyp.\n[x] Biopsy\n', 'Biopsy'),
                         'performed')

    def test_an_unchecked_service_is_negated_in_routing(self):
        from studio.gi.detect import route
        families = {f.family: f.status for f in route(DOS + 'Procedures performed today:\n☐ EGD\n☒ Colonoscopy\n').findings}
        self.assertEqual(families['gi.egd'], 'negated')


class CheckboxReachTests(SimpleTestCase):
    """The box rule's reach is bounded: a per-span scan back to the start of a long line made routing a long
    single-line document quadratic (28 s against 4.9 s without the rule, measured)."""

    def test_a_box_governs_only_an_item_within_reach(self):
        """Distances are literal (round-2 evidence:8): an input computed from BOX_REACH could not pin it.
        A box 152 characters before its item governs it; one 252 characters before does not."""
        near = DOS + 'Procedure: Colonoscopy to the cecum. Findings: polyp.\n☐ ' + 'x ' * 75 + 'Biopsy\n'
        far = DOS + 'Procedure: Colonoscopy to the cecum. Findings: polyp.\n☐ ' + 'x ' * 125 + 'Biopsy\n'
        self.assertEqual(near.index('Biopsy') - near.index('☐'), 152)
        self.assertEqual(far.index('Biopsy') - far.index('☐'), 252)
        self.assertEqual(status(near, 'Biopsy'), 'negated')
        self.assertNotEqual(status(far, 'Biopsy'), 'negated')

    def test_a_box_far_back_on_a_long_line_does_not_govern(self):
        """A checklist box 992 characters back on the same line says nothing of a later polypectomy."""
        text = (DOS + 'Procedure: Colonoscopy. Checklist: ☐ Biopsy. Findings: '
                + 12 * 'The colonoscope was advanced to the cecum and the mucosa was examined carefully. '
                + 'Cold snare polypectomy of a 7 mm sigmoid polyp was performed.\n')
        self.assertEqual(text.index('Cold snare polypectomy') - text.index('☐'), 992)
        self.assertEqual(status(text, 'Cold snare polypectomy'), 'performed')
        self.assertEqual(status(text, 'Biopsy'), 'negated')
