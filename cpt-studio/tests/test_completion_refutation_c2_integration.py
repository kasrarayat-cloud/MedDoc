"""Refutation of the integrated completion diff, cycle 2: the owner session's integration rules (2026-11-06; HARNESS.md
"Refutation of the integrated diff, cycle 2"). Builder K's listing rule withholds a listed removal unless the report
states a lesion removed; the services reader's plain subject reading needs both subject walks to agree, which a locative
after the head defeats ("A 6 mm polyp in the ascending colon was removed."), so a sentence that is only a lesion's
removal is recognized whole by a closed form of its own (services._removed_only). Builder K's widened same-act hold
doubts a done act over a later failure of its kind; two specific techniques that differ are two instances
(services._techniques_differ). Every document is synthetic."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.gi import services as gi_services
from tests.test_harness_engine import corti, run, span

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
LISTED = (BANNER + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\n'
          'Procedure: Colonoscopy with cold snare polypectomy\nThe colonoscope was advanced to the cecum.\n')
LISTING = 'Colonoscopy with cold snare polypectomy'
UPPER = (BANNER + 'Upper endoscopy report\nDate of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD '
         '(fictional)\nProcedure\nThe gastroscope was passed to the second portion of the duodenum.\n')
COLON = (BANNER + 'Colonoscopy report (fictional)\nDate of service: 2026-10-14\nProcedure: Colonoscopy\n'
         'The colonoscope was advanced to the cecum and the examination was completed.\n')


def status(text, code, quote):
    (item,) = [p for p in run(text, corti((code, span(text, quote)))).proposals if p.code == code and p.bucket != 'alternative']
    return item.bucket, item.status


class RemovedOnlyFormTests(SimpleTestCase):
    """A listed removal stands beside a lesion whose own sentence is only its removal, recognized whole."""

    def test_a_sentence_that_is_only_the_removal_lets_the_listing_stand(self):
        for line in ('A 6 mm polyp in the ascending colon was removed.',
                     'Findings: A 6 mm polyp in the ascending colon was removed.',
                     'A 6 mm polyp in the ascending colon was removed in one piece and retrieved.',
                     'A 12 mm polyp in the sigmoid colon was resected piecemeal.'):
            with self.subTest(line):
                self.assertEqual(status(LISTED + line + '\n', '45385', LISTING), ('selected', 'ready'))

    def test_anything_else_keeps_the_listing_withheld(self):
        # with a lesion recorded (the polyp seen), only a sentence that is that lesion's removal, recognized whole, lets
        # the listing stand; a removal of another time, place or object, a negation, or a clause is no such sentence
        seen = 'A 6 mm polyp in the ascending colon was seen. '
        for line in ('The polyp was removed in 2019.', 'The polyp was removed at an outside hospital.',
                     'The polyp was not removed.', 'The stool was suctioned and removed.',
                     'A polyp that was found last year was removed.'):
            with self.subTest(line):
                self.assertEqual(status(LISTED + seen + line + '\n', '45385', LISTING), ('selected', 'needs_clarification'))
        self.assertEqual(status(LISTED + 'A 6 mm polyp in the ascending colon was seen and the stool was removed.\n',
                                '45385', LISTING), ('selected', 'needs_clarification'))
        # a second lesion's own removal sentence lets the listing stand (one polypectomy documented)
        self.assertEqual(status(LISTED + seen + 'A 4 mm polyp in the rectum was removed.\n', '45385', LISTING),
                         ('selected', 'ready'))

    def test_recorded_residual_a_service_with_no_lesion_recorded(self):
        # the installed release's own reading, unchanged (ACCURACY-RESIDUALS.md, round 7 and cycle 2): where the services
        # reader records no lesion - a negated or another time's sentence - the listing stands as it read it
        for line in ('A 6 mm polyp in the ascending colon was not removed.', 'No polyp in the ascending colon was removed.'):
            with self.subTest(line):
                self.assertEqual(status(LISTED + line + '\n', '45385', LISTING), ('selected', 'ready'))

    def test_the_form_is_closed(self):
        self.assertIsNotNone(gi_services._REMOVED_ONLY.fullmatch('A 6 mm polyp was removed with a cold snare.'))
        self.assertIsNone(gi_services._REMOVED_ONLY.fullmatch('A 6 mm polyp was removed, and the clip was placed.'))


class SameActTechniqueTests(SimpleTestCase):
    """A failure of an act of a kind beside a done act of that kind stated with another specific technique."""

    def test_two_specific_techniques_are_two_instances(self):
        balloon = 'The Schatzki ring in the distal esophagus was dilated with a through-the-scope balloon to 18 mm.'
        text = UPPER + balloon + '\nDilation with a Savary bougie failed.\n'
        self.assertEqual(status(text, '43249', balloon), ('selected', 'ready'))
        done = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
        text = COLON + done + '\nHot snare polypectomy of a large pedunculated polyp failed.\n'
        self.assertEqual(status(text, '45385', done), ('selected', 'ready'))

    def test_a_generic_or_the_same_technique_keeps_the_hold(self):
        done = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
        for tail in ('The snare polypectomy failed.', 'Cold snare polypectomy of the polyp failed.'):
            with self.subTest(tail):
                self.assertEqual(status(COLON + done + '\n' + tail + '\n', '45385', done), ('selected', 'needs_clarification'))
        balloon = 'The stricture was dilated with a through-the-scope balloon to 15 mm.'
        self.assertEqual(status(UPPER + balloon + '\nThe balloon dilation failed.\n', '43249', balloon),
                         ('selected', 'needs_clarification'))

    def test_the_techniques_compared(self):
        self.assertTrue(gi_services._techniques_differ('balloon', 'guidewire'))
        self.assertTrue(gi_services._techniques_differ('cold snare', 'hot snare'))
        self.assertFalse(gi_services._techniques_differ('snare', 'cold snare'))
        self.assertFalse(gi_services._techniques_differ('', 'balloon'))
        self.assertFalse(gi_services._techniques_differ('balloon', 'balloon'))


class ListingScopeTests(SimpleTestCase):
    """The listing rule judges only lesions a snare, EMR, ESD or hot biopsy removes (services._NEVER_REMOVED_BY_SNARE)."""

    def test_a_stricture_beside_a_listed_snare_is_not_judged(self):
        self.assertIn('stricture', gi_services._NEVER_REMOVED_BY_SNARE)
        self.assertNotIn('polyp', gi_services._NEVER_REMOVED_BY_SNARE)
        # a polyp only seen beside the listing is judged: withheld (held); a stricture alone is not: the listing stands
        self.assertEqual(status(LISTED + 'A 6 mm polyp in the ascending colon was seen.\n', '45385', LISTING),
                         ('selected', 'needs_clarification'))
        self.assertEqual(status(LISTED + 'A benign-appearing stricture was seen in the sigmoid colon.\n', '45385', LISTING),
                         ('selected', 'ready'))
