"""Regressions for refutation round 4 over GI section structure (round "4b", studio/gi/sections.py).

Each class reproduces one confirmed round-4 finding (structure:N or release:N in the round-4 triage) from its exact
input, adds the wordings its verifier listed, and pins controls in both directions. The rule of round 4b is that a
wording or layout rule may only hold; it may restore the reading an input had at R3B-BASE (d05326ef) or at 57b4b3747,
and never newly excludes or releases otherwise. Where a repair restores R3B-BASE, the test says so.

Routing runs for real, for the document's own service date and through the JSON round trip the pipeline applies; the
real validation engine assesses provider-shaped selections against an empty in-memory reference. Synthetic text only.
"""
import unittest

from studio.gi.sections import layout
from tests.test_repairs_r3_sections import (EMR_LINE, HEADER, POSITIVE, emr_note, fact_value, read, ready, run_engine,
                                            word_document)


def kind_at(text, phrase):
    return layout(text).section_at(text.index(phrase)).kind


# --- structure:17 / release:2: a numbered or bulleted plan label, and a plan label that does not end with its noun ---

STRUCTURE17_EMR = 'EMR of the 3 cm ascending colon lesion at a tertiary center'


def structure17_note(label):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\n1. Findings\nThe colonoscope was advanced to the cecum. '
            'A 6 mm polyp was removed with a cold snare. A 3 cm flat ascending colon lesion was tattooed.\n' + label + '\n'
            + STRUCTURE17_EMR + '\n')


RELEASE2_EMR = 'EMR of the ascending colon lesion at a tertiary center.'
RELEASE2_CECUM = '1. The colonoscope was advanced to the cecum.'


def release2_note(label):
    return (HEADER + 'Procedure: Colonoscopy\nIndication: Positive FIT.\nFindings:\n' + RELEASE2_CECUM + '\n2. A 25 mm lateral '
            'spreading tumor in the ascending colon was tattooed and not removed.\n3. Small internal hemorrhoids.\n' + label + '\n'
            + RELEASE2_EMR + '\n')


class PlannedEmrAssertions:
    def assert_planned_emr_not_ready(self, text, emr, code_kind='plan'):
        """The planned EMR reads planned under a plan section, gives no EMR fact and is never a ready 45390 (it is
        excluded as planned, reinstatable, as at R3B-BASE)."""
        self.assertEqual(kind_at(text, emr), code_kind)
        self.assertEqual(read(text, emr)[0], 'planned')
        self.assertNotIn('EMR', fact_value(text, 'gi.colonoscopy', 'interventions') or '')
        proposal = run_engine(text, [('45390', emr)])['45390']
        self.assertFalse(ready(proposal))
        self.assertEqual((proposal.bucket, proposal.reinstatable), ('excluded', True))


class Structure17NumberedPlanLabelTests(PlannedEmrAssertions, unittest.TestCase):
    """structure:17 (a round-3b over-correction, 75a3cfac7) - a numbered, lettered or bulleted line that names a plan
    section ("2. Upcoming procedures") opens a plan section again, as it did at R3B-BASE: the planned EMR on the next
    line is never a ready 45390 with an EMR fact."""

    CLAIMED = ('2. Upcoming procedures', '2. Scheduled procedures', 'B. Future procedures', '2) Upcoming procedures',
               '* Upcoming procedures')

    def test_the_claimed_labels(self):
        for label in self.CLAIMED:
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(structure17_note(label), STRUCTURE17_EMR)

    def test_the_cecum_and_the_polypectomy_above_the_label_still_read(self):
        text = structure17_note('2. Upcoming procedures')
        polyp = 'A 6 mm polyp was removed with a cold snare.'
        self.assertEqual(read(text, polyp)[0], 'performed')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertTrue(ready(run_engine(text, [('45385', polyp)])['45385']))

    def test_the_controls_still_plan(self):
        for label in ('Upcoming procedures', '2. Upcoming procedures:', '2. Plan', '2. Planned procedures', '## Upcoming procedures',
                      '**Upcoming procedures**'):
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(structure17_note(label), STRUCTURE17_EMR)

    def test_the_lines_round_3b_pinned_as_findings(self):
        """Round 3b's test pinned these before the planned EMR as findings content (its verifier: a false green that never
        asserted the 45390 outcome); they open a plan, as at R3B-BASE."""
        for label in ('3. Upcoming procedures', 'b) Further evaluation', '* Upcoming procedures'):
            text = emr_note(label)
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(text, EMR_LINE)


class Release2PlanLabelsTests(PlannedEmrAssertions, unittest.TestCase):
    """release:2 (a round-3b new defect, 75a3cfac7) - a numbered or bulleted plan label, and a plan label whose first word
    names the plan ("Procedures planned", "Plan going forward"), open a plan section again, as at R3B-BASE: the planned
    EMR is never a ready 45390 with an EMR fact, while the cecum item above it still reads performed."""

    CLAIMED = ('4. Upcoming procedures', '* Upcoming procedures', 'Procedures planned', 'Plan going forward')
    LISTED = ('4) Upcoming procedures', 'D. Upcoming procedures', '4. Procedures planned', '4. Plan going forward',
              'Plan moving forward', 'Procedures recommended', 'Procedures scheduled', 'Plan from here')

    def test_the_claimed_and_listed_labels(self):
        for label in self.CLAIMED + self.LISTED:
            text = release2_note(label)
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(text, RELEASE2_EMR)
                self.assertTrue(ready(run_engine(text, [('45378', RELEASE2_CECUM)])['45378']))

    def test_in_prose_findings(self):
        for label in ('Plan going forward', 'Procedures planned', 'Plan moving forward', 'Procedures recommended',
                      'Procedures scheduled', 'Plan from here', '* Upcoming procedures'):
            text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 25 mm lateral spreading '
                    'tumor in the ascending colon was tattooed and not removed.\n' + label + '\n' + RELEASE2_EMR + '\n')
            with self.subTest(label=label):
                self.assert_planned_emr_not_ready(text, RELEASE2_EMR)

    def test_a_word_heading_paragraph(self):
        for label in ('Plan going forward', 'Procedures planned'):
            text = word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                                  ('Procedure: Colonoscopy', None),
                                  ('Findings: The colonoscope was advanced to the cecum. A 25 mm lateral spreading tumor in the '
                                   'ascending colon was tattooed and not removed.', None),
                                  (label, 'Heading 2'), (RELEASE2_EMR, None)])
            with self.subTest(label=label):
                self.assertIn('\n' + label + '\n', text)
                self.assert_planned_emr_not_ready(text, RELEASE2_EMR)

    def test_lines_that_only_start_with_the_words_stay_content(self):
        """A line whose first word is "Procedure(s)" or "Plan" is a plan label only with a plan word in it, and never a
        title, a service, an act or a sentence."""
        for line in ('Procedures tolerated well', 'Procedure note for next visit', 'Procedure complicated by mild bleeding',
                     'Procedures were uneventful', 'Planning stage', 'Procedure with cold snare polypectomy'):
            text = release2_note(line)
            with self.subTest(line=line):
                self.assertEqual(kind_at(text, RELEASE2_EMR), 'findings')

    def test_round3_routing2_statements_stay_content(self):
        """routing:2 (round 3): a numbered findings item that is a statement is never a label, so the polypectomy after it
        stays a ready 45385; the noun-last rule keeps these content without the list-item guard."""
        polyp = '6 mm sigmoid polyp removed with cold snare.'
        for item in ('Further workup recommended', 'Further evaluation recommended', 'Surgical management recommended',
                     'Further imaging recommended', 'Follow-up imaging advised', 'Previous treatments failed',
                     'Prior therapy ineffective', 'Prior radiation therapy changes', 'Genetic testing recommended', 'History of AS'):
            text = (HEADER + 'Procedure: Colonoscopy with biopsy and cold snare polypectomy.\nFindings:\n1. The colonoscope was advanced '
                    'to the cecum.\n2. A 3 cm ascending colon mass, biopsied and tattooed.\n3. ' + item + '\n4. ' + polyp + '\n')
            with self.subTest(item=item):
                self.assertEqual(kind_at(text, polyp), 'findings')
                self.assertTrue(ready(run_engine(text, [('45385', polyp)])['45385']))

    def test_a_numbered_plan_label_item_reads_as_at_r3b_base(self):
        """The cost of restoring R3B-BASE, accepted and stated: a numbered item that is itself a plan label ("3. Upcoming
        procedures", "3. Further evaluation") opens a plan section even when the next line is the next item of the same
        list, so the performed item after it is excluded as planned (reinstatable, for a reviewer), never ready. Round
        3b's list-item guard read it as content, and that guard is what released the planned EMR above."""
        polyp = '6 mm sigmoid polyp removed with cold snare.'
        for item in ('Further evaluation', 'Upcoming procedures'):
            text = (HEADER + 'Procedure: Colonoscopy with biopsy and cold snare polypectomy.\nFindings:\n1. The colonoscope was advanced '
                    'to the cecum.\n2. A 3 cm ascending colon mass, biopsied and tattooed.\n3. ' + item + '\n4. ' + polyp + '\n')
            with self.subTest(item=item):
                self.assertEqual(kind_at(text, polyp), 'plan')
                proposal = run_engine(text, [('45385', polyp)])['45385']
                self.assertFalse(ready(proposal))
                self.assertNotIn(read(text, polyp)[0], POSITIVE)


if __name__ == '__main__':
    unittest.main()
