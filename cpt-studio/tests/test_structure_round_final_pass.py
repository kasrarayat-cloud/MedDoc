"""The structure round's final refutation pass over the integrated diff (2026-11-08): what broke a claim, repaired and pinned.

- U14 (the labels lens, HIGH): the lead before the motion's scope noun is read by a CLOSED form, never by a list of set-off
  characters. "On 10/14 -- unlike today -- the gastroscope was introduced ... to the third portion of the duodenum."
  (an ASCII double hyphen, another dash, an ellipsis, quotes, a slash, or no punctuation at all) read the dated long reach
  as today's D3, where the installed release reads no extent.
- U18 (the labels lens): the services module's caches are cleared at both ends of the guard, so a withdrawn release
  stores exactly the installed reading. A cache keyed by the reflowed plain text (_occasion_indications) had served the
  guard's candidate reading to the real one: the acts lost their other-occasion hold and a proposal's fingerprint moved.
- U16 with U18 (the interactions lens): U16's own status read takes the text routing reads, as every installed status
  read in build() does, so the guard no longer withdraws every corroborated release of a report that states a bolus
  removal.
Synthetic documents only; nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio import jobs
from studio.gi import services, structure
from tests.test_completion_motion import BIOPSY, UPPER, extent
from tests.test_harness_engine import corti, run, span

LONG = ('the gastroscope was introduced through the mouth and advanced through the upper esophageal sphincter and down a '
        'normal esophagus to the gastroesophageal junction, where a regular Z-line sat at 38 cm above a 2 cm sliding '
        'hiatal hernia, then on through the stomach and the pylorus to the third portion of the duodenum.')


class ClosedLeadTests(SimpleTestCase):
    """U14: a lead the closed form does not read reads no motion, however (or whether) it is set off."""

    def test_a_dated_lead_reads_no_motion_however_it_is_set_off(self):
        for sep in (' -- ', '--', ' ‒ ', ' ― ', ' ‐ ', ' ‑ ', ' − ', ' - ', ' ... ',
                    ' … ', ' " ', ' / ', ' ', ' — ', ', '):
            text = UPPER + 'On 10/14' + sep + 'unlike today' + sep + LONG + ' ' + BIOPSY + '\n'
            with self.subTest(sep=sep):
                self.assertIsNone(extent(text, 'gi.egd'))

    def test_occasion_and_generic_leads_read_no_motion(self):
        for lead in ('Some time back ', 'Way back ', 'At her first endoscopy ', 'In my experience ', 'As usual ',
                     'Unlike today ', 'In theory ', 'Next time ', 'Next, '):
            with self.subTest(lead=lead):
                self.assertIsNone(extent(UPPER + lead + LONG + ' ' + BIOPSY + '\n', 'gi.egd'))

    def test_the_closed_forms_read_the_reach(self):
        for lead in ('The', 'Then the', 'Subsequently the', 'Thereafter the', 'Today the', '1. The', '- The'):
            text = UPPER + lead + LONG[len('the'):] + ' ' + BIOPSY + '\n'
            with self.subTest(lead=lead):
                self.assertEqual(extent(text, 'gi.egd'), 'third part of duodenum')


COL_HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nCOLONOSCOPY REPORT\n'
            'Date of service: 2026-10-14\nEndoscopist: Synthetic Endoscopist, MD (fictional)\n')
COURSE = 'The colonoscope was introduced through the anus and advanced to the cecum.'
SNARE = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
TATTOO = 'The polypectomy site was marked with tattoo.'
OW = 'The colonoscope was withdrawn while the patient was turned supine.'
# the guard proposes this paragraph and withdraws it (blanks before the label's colon: a compared difference)
WITHDRAWN = (COL_HEAD + 'Procedures: Colonoscopy to the cecum with polypectomy and tattoo\n'
             'Indications: Sigmoid polyp seen on an outside colonoscopy on 2026-09-01; referred for removal.\n'
             'Colonoscopy : ' + COURSE + ' ' + SNARE + ' ' + TATTOO + ' ' + OW + '\n'
             'Impression: Sigmoid polyp removed with a cold snare.\nPlan: Await pathology.\n')


def readings(result):
    return [(p.code, p.bucket, p.status, p.fingerprint) for p in result.proposals]


class WithdrawnReleaseTests(SimpleTestCase):
    """U18: what a withdrawn release stores is the installed reading, in the assessment stage's own order."""

    def test_the_guard_proposes_and_withdraws(self):
        jobs.release_routing_caches()
        self.assertNotEqual(structure.twin_differences(WITHDRAWN), ())
        self.assertTrue(all(why for _, why in structure.decisions(WITHDRAWN)))

    def test_the_stage_order_stores_the_clean_reading(self):
        picks = corti(('45385', span(WITHDRAWN, SNARE[:-1])), ('45381', span(WITHDRAWN, TATTOO[:-1])))
        jobs.release_routing_caches()
        staged = run(WITHDRAWN, picks)  # routing (the guard reads, then withdraws), then the services reader
        jobs.release_routing_caches()
        structure.decisions(WITHDRAWN)
        services.release_reading_caches()
        clean = run(WITHDRAWN, picks)  # the services reader with nothing the guard made
        self.assertEqual(readings(staged), readings(clean))
        self.assertEqual(staged.services, clean.services)
        jobs.release_routing_caches()


class BolusBesideTheReleaseTests(SimpleTestCase):
    """U16 with U18: U16's own status read takes the text routing reads (the repair); a release beside U16's full twin is
    still withdrawn, fail closed (recorded: the full twin is a derived text the guard cannot carry)."""

    def test_u16s_status_read_takes_the_text_routing_reads(self):
        from datetime import date
        from unittest import mock
        from studio.gi import detect
        seen = []

        def spy(text, *args, **kwargs):
            seen.append(text)
            return 'performed', ()
        original, reflowed = 'X' * 40, 'Y' * 40
        with mock.patch.object(detect, 'status_for_span', spy):
            token = services._ORIGINAL.set(original)
            try:
                services._account_sentence_today(reflowed, 0, 10, service_date=date(2026, 10, 14), dates=[],
                                                 date_starts=[])
            finally:
                services._ORIGINAL.reset(token)
            services._account_sentence_today(reflowed, 0, 10, service_date=date(2026, 10, 14), dates=[], date_starts=[])
        self.assertEqual(seen, [original, reflowed])

    def test_a_release_beside_the_full_twins_reading_is_withdrawn_and_reads_as_installed(self):
        from tests.test_completion_corroboration import EGD, IMPRESSION, N1, P4, REPORT
        bolus = (' A piece of meat was impacted in the distal esophagus. I opened a Roth net beside the meat and captured '
                 'the meat, and the meat was brought out through the mouth with the scope.')
        text = REPORT.replace(EGD, EGD.rstrip('\n') + bolus + '\n').replace(
            IMPRESSION, IMPRESSION.rstrip('\n') + ' Meat impaction in the distal esophagus, cleared with a Roth net.\n')
        self.assertNotEqual(text, REPORT)
        jobs.release_routing_caches()
        self.assertEqual(structure.twin_differences(text), ('plain-read',))
        self.assertEqual([why for _, why in structure.decisions(text)], [N1, P4])
        jobs.release_routing_caches()
