"""Regressions for refutation round 5 over GI section structure (round "4c", SECTIONS: studio/gi/sections.py and its
readers in studio/gi/detect.py).

Each class reproduces one confirmed round-5 finding (sections:N, regression:N, declared:N or validation:N in the round-5
triage) from its exact input, adds the variants its verifier listed, and pins controls in both directions. The rule of
round 4c: a wording or layout rule may only hold (uncertain, with a non-silent cue); it may restore the reading an input
had at R4B-BASE (4347acd24) or R3B-BASE (d05326ef), and it never newly excludes or releases otherwise. Where a repair
restores a base, the test says so; where it holds an input a base read as performed, the test names the accepted
over-hold.

Routing runs for real, for the document's own service date and through the JSON round trip the pipeline applies; the
real validation engine assesses provider-shaped selections against an empty in-memory reference. Synthetic text only.
"""
import unittest

from studio.gi.sections import layout
from tests.test_repairs_r3_sections import (EMR_LINE, HEADER, NOT_TODAY, POSITIVE, clarified, emr_note, fact_value, family,
                                            read, ready, routed, run_engine, word_document)


def kind_at(text, phrase):
    return layout(text).section_at(text.index(phrase)).kind


def held(proposal):
    return (proposal.bucket, proposal.status) == ('selected', 'needs_clarification')


class HeldOrReadyAssertions:
    def assert_held_never_excluded(self, text, code, phrase):
        """The passage reads uncertain (a hold, never planned, historical, cancelled or negated) and the code is held for
        a reviewer, never ready and never excluded."""
        status, cues = read(text, phrase)
        self.assertEqual(status, 'uncertain', cues)
        self.assertFalse(any(cue.startswith('uncertain: no performance evidence') for cue in cues), cues)
        proposal = run_engine(text, [(code, phrase)])[code]
        self.assertTrue(held(proposal), (proposal.bucket, proposal.status, clarified(proposal)))

    def assert_never_ready(self, text, code, phrase):
        proposal = run_engine(text, [(code, phrase)])[code]
        self.assertFalse(ready(proposal), (proposal.bucket, proposal.status))


# --- sections:2: the plan-first rule on statement lines --------------------------------------------------------------

S2_POLYP = '6 mm sigmoid polyp removed with cold snare'


def s2_note(line, polyp=S2_POLYP, findings=True):
    if not findings:  # the line directly under the Procedure line
        return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\n' + line + '\nThe colonoscope was advanced '
                'to the cecum\n' + polyp + '\nImpression: Sigmoid polyp.\n')
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\nIndication: Surveillance\nFindings:\nThe '
            'colonoscope was advanced to the cecum\n' + line + '\n' + polyp + '\nImpression: Sigmoid polyp.\n')


class Sections2PlanFirstStatementTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:2 (critical, a regression from da47d19ef) - a line that starts with "Procedure(s)" or "Plan" and carries a
    plan word opened a PLAN section even when it is a statement ("Procedure completed as planned"), so the performed
    polypectomy after it was excluded as planned. Only a line made of that noun and plan words ("Procedures planned",
    "Plan going forward") is such a label now; any other line that starts with the words is held like a phrase line
    (4347acd24 read it as content, ready: the hold is the accepted cost, because the same shape also writes a real plan
    label, "Procedures planned for next visit", whose planned EMR must never read ready)."""

    CLAIMED = ('Procedure completed as planned', 'Procedure went as planned', 'Procedure proceeded as planned',
               'Procedures completed as scheduled', 'Procedure tolerated well, follow-up as scheduled',
               'Procedure uncomplicated, follow-up as planned', 'Procedure completed, plan as below', 'Procedure as planned',
               'Procedure for further evaluation of anemia', 'Procedure tolerated well; disposition to recovery',
               '2. Procedure completed as planned', 'Procedure completed without difficulty as planned')

    def test_the_claimed_lines(self):
        for line in self.CLAIMED:
            text = s2_note(line)
            with self.subTest(line=line):
                self.assertNotEqual(kind_at(text, S2_POLYP), 'plan')
                self.assertNotIn(read(text, S2_POLYP)[0], NOT_TODAY)
                self.assertNotEqual(run_engine(text, [('45385', S2_POLYP)])['45385'].bucket, 'excluded')

    def test_a_cued_polyp_and_the_line_under_the_procedure_line(self):
        polyp = 'A 6 mm sigmoid polyp was removed with a cold snare.'
        for line in ('Procedure completed as planned', 'Procedure went as planned'):
            with self.subTest(line=line):
                text = s2_note(line, polyp)
                self.assertNotEqual(run_engine(text, [('45385', polyp)])['45385'].bucket, 'excluded')
                text = s2_note(line, findings=False)
                self.assertNotEqual(run_engine(text, [('45385', S2_POLYP)])['45385'].bucket, 'excluded')

    def test_a_word_document(self):
        for style in (None, 'List Bullet'):
            text = word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                                  ('Procedure: Colonoscopy with cold snare polypectomy', None), ('Findings', 'Heading 2'),
                                  ('The colonoscope was advanced to the cecum', style),
                                  ('Procedure completed as planned', style), (S2_POLYP, style)])
            with self.subTest(style=style):
                self.assertNotEqual(run_engine(text, [('45385', S2_POLYP)])['45385'].bucket, 'excluded')

    def test_label_shaped_lines_still_plan(self):
        for label in ('Procedures planned', 'Plan going forward', 'Plan moving forward', 'Procedures recommended',
                      'Procedures scheduled', 'Plan from here', '4. Procedures planned', 'Plans going forward',
                      'Procedures planned next', 'Plan follow-up'):
            text = emr_note(label)
            with self.subTest(label=label):
                self.assertEqual(kind_at(text, EMR_LINE), 'plan')
                self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')

    def test_a_longer_plan_label_never_releases_the_planned_emr(self):
        """The narrowing never releases: a real plan label that is not made of plan words only is held, not content."""
        for label in ('Procedures planned for next week', 'Plan for the coming weeks', 'Procedures scheduled next week',
                      '4. Procedures planned for next week', 'Plans after discharge as discussed'):
            text = emr_note(label)
            with self.subTest(label=label):
                self.assert_never_ready(text, '45390', EMR_LINE)
                self.assertNotIn(read(text, EMR_LINE)[0], POSITIVE)

    def test_outside_a_procedure_findings_or_technique_section(self):
        """In a plan section it plans, as at HEAD; elsewhere (an impression, an indication) it is held: HEAD planned the
        lines after it (excluding a performed polypectomy), and 4347acd24 read it as content, where a silent line takes
        its family's reading (releasing a planned EMR)."""
        base = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 30 mm laterally '
                'spreading polyp was tattooed.\n')
        text = base + 'Plan:\nProcedure completed, plan as below\n' + EMR_LINE + '\n'
        self.assertEqual(kind_at(text, EMR_LINE), 'plan')
        self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')
        for heading in ('Impression: Ascending colon polyp.', 'Indication: Surveillance.'):
            for line in ('Procedure completed, plan as below', 'Procedures planned for next week',
                         'Procedure completed as planned'):
                text = base + heading + '\n' + line + '\n' + EMR_LINE + '\n'
                with self.subTest(heading=heading, line=line):
                    self.assert_held_never_excluded(text, '45390', EMR_LINE)
        text = HEADER + 'Procedure completed as planned\n' + S2_POLYP + '\nProcedure: Colonoscopy\n'  # before any heading
        self.assertNotIn(read(text, S2_POLYP)[0], NOT_TODAY)


# --- sections:4: a numbered findings item naming prior therapy -------------------------------------------------------

S4_ITEM = '3. 6 mm sigmoid polyp removed with cold snare'


def s4_note(item2, prefix='2. ', item3=S4_ITEM):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings:\n1. The colonoscope was advanced to the '
            'cecum.\n' + prefix + item2 + '\n' + item3 + '\nImpression: Sigmoid polyp.\n')


class Sections4NumberedHistoryItemTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:4 (critical, a regression from da47d19ef) - a numbered or bulleted findings item that names prior therapy
    ("2. Prior radiation therapy") opened a HISTORY section again, so the next item's performed polypectomy was excluded
    as historical. Inside a procedure, findings or technique section such an item now opens the held 'other' section of
    a phrase line (4347acd24 read it as content, but that also released an argon plasma coagulation that the item really
    heads, which HEAD and R3B-BASE read as historical); elsewhere it is content, as at 4347acd24."""

    CLAIMED = ('Prior radiation therapy', 'Previous endoscopic therapy', 'Prior treatment', 'Past endoscopic treatment')

    def test_the_claimed_items(self):
        for item in self.CLAIMED:
            text = s4_note(item)
            with self.subTest(item=item):
                self.assertNotIn(read(text, S4_ITEM)[0], NOT_TODAY)
                self.assert_held_never_excluded(text, '45385', S4_ITEM)

    def test_every_list_marker_and_wording(self):
        for prefix in ('2. ', '2) ', 'b. ', '* ', 'B) '):
            for item in ('Prior radiation therapy', 'Status post prior radiation therapy', 'History of radiation therapy',
                         'Prior endoscopic therapy', 'Previous treatment'):
                text = s4_note(item, prefix)
                with self.subTest(prefix=prefix, item=item):
                    self.assertNotIn(read(text, S4_ITEM)[0], NOT_TODAY)
                    self.assertNotEqual(run_engine(text, [('45385', S4_ITEM)])['45385'].bucket, 'excluded')

    def test_the_impression_list(self):
        item3 = 'Sigmoid polyp, removed with cold snare'
        for item in ('History of radiation therapy', 'Prior radiation therapy'):
            text = (HEADER + 'Procedure: Colonoscopy with biopsy and cold snare polypectomy.\nFindings: The colonoscope was '
                    'advanced to the cecum. A 6 mm sigmoid polyp was removed with a cold snare.\nImpression:\n1. Ascending '
                    'colon mass, biopsied.\n2. ' + item + '\n3. ' + item3 + '\n')
            with self.subTest(item=item):
                self.assert_held_never_excluded(text, '45385', item3)

    def test_an_item_that_heads_the_next_line_is_held_not_released(self):
        line = 'Argon plasma coagulation of rectal telangiectasias'
        text = (HEADER + 'Procedure: Flexible sigmoidoscopy\n1. Findings\nThe sigmoidoscope was advanced to 40 cm. Rectal '
                'telangiectasias were seen.\n2. Prior endoscopic therapy\n' + line + '\n')
        self.assertEqual(read(text, line)[0], 'uncertain')

    def test_in_a_plan_or_history_section_the_section_goes_on(self):
        """Content there, as at 4347acd24: the section in force reads the next item."""
        item3 = "3. Colonoscopy with cold snare polypectomy"
        text = HEADER + 'Procedure: EGD\nFindings: Normal.\nPast history:\n1. Diabetes\n2. Prior radiation therapy\n' + item3 + '\n'
        self.assertEqual(kind_at(text, item3), 'history')
        self.assertEqual(read(text, item3)[0], 'historical')

    def test_the_unnumbered_line_and_other_items_are_unchanged(self):
        text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: The colonoscope was advanced to the '
                'cecum.\nPrior radiation therapy\n6 mm sigmoid polyp removed with cold snare\n')
        self.assertEqual(kind_at(text, '6 mm sigmoid polyp'), 'history')  # all three bases read it so
        for item in ('Small internal hemorrhoids', 'Prior radiation therapy changes', 'Genetic testing recommended'):
            text = s4_note(item)
            with self.subTest(item=item):
                self.assertEqual(kind_at(text, S4_ITEM), 'findings')
                self.assertTrue(ready(run_engine(text, [('45385', S4_ITEM)])['45385']))
        text = s4_note('Upcoming procedures')  # a numbered plan label: the accepted cost of round 4b (structure:17)
        self.assertEqual(kind_at(text, S4_ITEM), 'plan')


# --- sections:0: an explicit performance statement under a colon-less history phrase line ----------------------------

S0_EMR = 'EMR of a 3 cm ascending colon lesion was performed with clear margins.'
S0_POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'
S0_PHRASES = ('Review of prior procedures', 'Results of previous procedures', 'Comparison with prior procedures',
              'Details of previous procedures', 'Outcome of prior treatment', 'Results of prior studies')


def s0_under_procedure(line):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\n' + line + '\n' + S0_EMR + '\nIndication: '
            'Surveillance.\nFindings: The colonoscope was advanced to the cecum. ' + S0_POLYP + '\n')


def s0_after_findings(line):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\nIndication: Surveillance.\nFindings: The '
            'colonoscope was advanced to the cecum. ' + S0_POLYP + '\n' + line + '\n' + S0_EMR + '\n')


class Sections0CuedLineUnderAPhraseLineTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:0 (critical, a regression from 519608ff2) - under a colon-less phrase line inside a procedure or findings
    section ("Review of prior procedures"), a line with its own performance cue read performed, so the past EMR was a
    ready 45390 (4347acd24 and R3B-BASE read it historical). Such a line is held like the uncued lines under it
    (ARCHITECTURE 5.3: "whose lines are held"), never performed and never excluded."""

    def test_the_claimed_phrases_in_both_positions(self):
        for line in S0_PHRASES:
            for make in (s0_under_procedure, s0_after_findings):
                text = make(line)
                with self.subTest(line=line, where=make.__name__):
                    self.assertEqual(kind_at(text, S0_EMR), 'other')
                    self.assert_held_never_excluded(text, '45390', S0_EMR)
                    self.assertTrue(ready(run_engine(text, [('45385', S0_POLYP)])['45385']))

    def test_a_word_document(self):
        for style in ('Heading 2', None):
            text = word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                                  ('Procedure: Colonoscopy with cold snare polypectomy', None),
                                  ('Review of prior procedures', style), (S0_EMR, None), ('Indication: Surveillance.', None),
                                  ('Findings: The colonoscope was advanced to the cecum. ' + S0_POLYP, None)])
            with self.subTest(style=style):
                self.assert_never_ready(text, '45390', S0_EMR)

    def test_the_cued_emr_under_the_leads_analog(self):
        emr = 'EMR of the ascending colon lesion was performed at a tertiary center.'
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 30 mm laterally '
                'spreading polyp was tattooed.\nSurgical opinion for further management\n' + emr + '\n')
        self.assert_never_ready(text, '45390', emr)

    def test_history_labels_and_no_heading_are_unchanged(self):
        for line in ('Prior procedures', 'History of prior procedures', 'Previous procedures'):
            text = s0_under_procedure(line)
            with self.subTest(line=line):
                self.assertEqual(kind_at(text, S0_EMR), 'history')
                self.assertEqual(run_engine(text, [('45390', S0_EMR)])['45390'].bucket, 'excluded')
        text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\n' + S0_EMR + '\nIndication: Surveillance.\n'
                'Findings: The colonoscope was advanced to the cecum. ' + S0_POLYP + '\n')
        self.assertTrue(ready(run_engine(text, [('45390', S0_EMR)])['45390']))


# --- sections:6: the second of two phrase lines ----------------------------------------------------------------------

S6_POLYP = '6 mm sigmoid polyp removed with cold snare'
S6_A, S6_B = 'Changes of prior radiation therapy', 'Retained stool limiting further evaluation'


def s6_note(lines, polyp=S6_POLYP):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings:\nThe colonoscope was advanced to the '
            'cecum.\n' + ''.join(line + '\n' for line in lines) + polyp + '\n')


class Sections6SecondPhraseLineTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:6 (high, an under-correction of structure:4) - the second of two phrase lines inside a findings section
    opened a plan or history section, because the section in force was the first phrase line's 'other' section; the
    polypectomy after them was excluded. A phrase line's 'other' section stands in for the section that encloses it, so
    every phrase line in a run opens 'other' and its lines are held."""

    def test_two_phrase_lines_in_either_order(self):
        for lines in ((S6_A, S6_B), (S6_B, S6_A), ('Changes consistent with prior radiation therapy',
                                                    'Telangiectasias from previous radiation therapy'), (S6_A, S6_B, S6_A)):
            text = s6_note(lines)
            with self.subTest(lines=lines):
                self.assertEqual(kind_at(text, S6_POLYP), 'other')
                self.assert_held_never_excluded(text, '45385', S6_POLYP)

    def test_a_cued_polyp_and_a_planned_emr(self):
        polyp = 'A 6 mm sigmoid polyp was removed with a cold snare.'
        for lines in ((S6_A, S6_B), (S6_B, S6_A)):
            with self.subTest(lines=lines):
                self.assertNotEqual(run_engine(s6_note(lines, polyp), [('45385', polyp)])['45385'].bucket, 'excluded')
                emr = 'EMR of the ascending colon lesion at a tertiary center.'
                self.assert_never_ready(s6_note(lines, emr), '45390', emr)

    def test_a_word_bullet_list(self):
        text = word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                              ('Procedure: Colonoscopy with cold snare polypectomy.', None), ('Findings', 'Heading 2'),
                              ('The colonoscope was advanced to the cecum.', 'List Bullet'), (S6_B, 'List Bullet'),
                              (S6_A, 'List Bullet'), (S6_POLYP, 'List Bullet')])
        self.assertNotEqual(run_engine(text, [('45385', S6_POLYP)])['45385'].bucket, 'excluded')

    def test_outside_a_positive_section_two_phrase_lines_still_plan(self):
        base = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\nImpression: Polyp.\n')
        emr = 'EMR of the ascending colon lesion at a tertiary center.'
        text = base + 'Surgical opinion for further management\nSpecimens sent for further evaluation\n' + emr + '\n'
        self.assertEqual(kind_at(text, emr), 'plan')
        self.assertEqual(run_engine(text, [('45390', emr)])['45390'].bucket, 'excluded')



# --- regression:2 / sections:5: a round-3b plan label with an answer of its own -------------------------------------

R2_FIND = ('Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 30 mm laterally spreading polyp '
           'in the ascending colon was tattooed and not removed.\n')
R2_EGD = ('Procedure: EGD with biopsy\nFindings: The gastroscope was advanced to the second part of the duodenum. A 2 cm '
          'subepithelial lesion in the gastric body. Biopsies of the antrum were taken.\n')
S5_POLYP = '6 mm sigmoid polyp removed with cold snare'


class Regression2PlannedServiceFieldTests(HeldOrReadyAssertions, unittest.TestCase):
    """regression:2 (critical, a regression from 400f4ebf1) - after a round-3b plan label with an answer of its own
    ("Referrals: advanced endoscopy"), a planned service written as a field line ("Colonoscopy with EMR: ascending colon
    polyp, tertiary center") took the findings section again through round 4b's resume, so 45390 / 43242 were READY
    (4347acd24 excluded them). Any line after such a label that names a service or an intervention, up to the next
    heading, is now held for itself, never performed and never planned; the lines that name none (an "Extent: cecum"
    field, prose) read in the section in force before the label, as round 4b's structure:5 repair wanted."""

    CLAIMED = (('Referrals: advanced endoscopy', 'Colonoscopy with EMR: ascending colon polyp, tertiary center'),
               ('Orders: CBC, INR', 'EMR: ascending colon polyp at a tertiary center'),
               ('To do: refer', 'Colonoscopy with EMR: ascending colon polyp'),
               ('Pending procedures: see below', 'Colonoscopy with EMR: ascending colon polyp, tertiary center'))

    def test_the_claimed_inputs(self):
        for label, field in self.CLAIMED:
            text = HEADER + R2_FIND + label + '\n' + field + '\n'
            with self.subTest(label=label):
                self.assert_held_never_excluded(text, '45390', field)
                self.assertNotIn('EMR', fact_value(text, 'gi.colonoscopy', 'interventions') or '')
        field = 'EUS with FNA: gastric body subepithelial lesion'
        text = HEADER + R2_EGD + 'Orders: CT abdomen\n' + field + '\n'
        self.assert_held_never_excluded(text, '43242', field)
        self.assertNotIn(family(text, 'gi.eus'), POSITIVE)

    def test_the_verifiers_variants(self):
        emr = 'EMR: ascending colon polyp at a tertiary center'
        for body in ('Referral: advanced endoscopy\nProcedure requested: colonoscopy with EMR of the ascending colon polyp',
                     'Orders: CBC, INR\nReferral: advanced endoscopy\n' + emr,
                     'Referrals: advanced endoscopy\n\n' + emr,
                     'Pending procedures: at a tertiary center\n' + emr,
                     'To do: schedule\n' + emr,
                     'Referrals: advanced endoscopy\nExtent: cecum\n' + emr,  # second in the run
                     'Referrals: advanced endoscopy\nExtent: cecum\nWithdrawal time: 8 minutes\n' + emr,
                     '1. Referrals: advanced endoscopy\n2. ' + emr,
                     'Referrals: advanced endoscopy\nThe patient was counseled.\n' + emr):
            text = HEADER + R2_FIND + body + '\n'
            phrase = body.rsplit('\n', 1)[-1]
            with self.subTest(body=body):
                self.assertNotIn(read(text, phrase)[0], POSITIVE)
                self.assert_never_ready(text, '45390', phrase)

    def test_a_cited_span_from_a_resumed_field_into_a_held_line(self):
        """A passage cited across the line break, from the "Extent: cecum" field the section before the label reads into
        the held field or sentence after it, reads as the held line does, never as the findings it starts in."""
        for second in ('EMR: ascending colon polyp at a tertiary center',
                       'EMR of the ascending colon polyp was performed at a tertiary center.'):
            text = HEADER + R2_FIND + 'Referrals: advanced endoscopy\nExtent: cecum\n' + second + '\n'
            with self.subTest(second=second):
                self.assertEqual(read(text, 'Extent: cecum')[0], 'performed')  # the field itself reads as before
                self.assertEqual(read(text, 'Extent: cecum\n' + second)[0], 'uncertain')
                self.assert_never_ready(text, '45390', 'Extent: cecum\n' + second)

    def test_a_cued_line_after_the_label(self):
        """A line with its own performance cue after such a label is held too (HEAD held it in the label's plan section)."""
        line = 'EMR of the ascending colon polyp was performed at a tertiary center.'
        text = HEADER + R2_FIND + 'Referrals: advanced endoscopy\n' + line + '\n'
        self.assertEqual(read(text, line)[0], 'uncertain')
        self.assert_never_ready(text, '45390', line)

    def test_the_labels_plan_bare_inline_and_under_a_plan(self):
        for label in ('Referrals:', 'Pending procedures', 'Orders:'):
            text = emr_note(label)
            with self.subTest(label=label):
                self.assertEqual(kind_at(text, EMR_LINE), 'plan')
                self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')
        text = emr_note('Orders: ' + EMR_LINE).replace('\n' + EMR_LINE + '\n', '\n')  # the label's own line plans
        self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')
        field = 'EMR: ascending colon polyp at a tertiary center'
        text = HEADER + R2_FIND + 'Plan:\nReferrals: advanced endoscopy\n' + field + '\n'
        self.assertEqual(kind_at(text, field), 'plan')
        self.assertEqual(run_engine(text, [('45390', field)])['45390'].bucket, 'excluded')

    def test_a_field_that_names_no_service_reads_in_the_section_before_the_label(self):
        """structure:5's repair stands: "Extent: cecum" after the label is the report's own extent."""
        text = (HEADER + 'Procedure: Colonoscopy\nReferral: Dr. B. Synthetic, primary care\nExtent: cecum\nFindings: A 6 mm '
                'sigmoid polyp was removed with a cold snare.\n')
        self.assertEqual(kind_at(text, 'Extent: cecum'), 'procedure')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertTrue(ready(run_engine(text, [('45385', 'A 6 mm sigmoid polyp was removed with a cold snare.')])['45385']))


class Sections5PlanLabelOverProseTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:5 (critical, a round-3b regression that round 4b kept) - a round-3b plan label with an answer of its own
    ("Referral: Dr. B. Synthetic, primary care") opened a plan over the prose after it, so the performed polypectomy was
    excluded (R3B-BASE read it ready). The label plans only its own line (ARCHITECTURE 5.3); up to the next heading the
    lines after it are HELD, except a field that names no service ("Extent: cecum"), which reads in the section before
    the label. An accepted over-hold against R3B-BASE: the same layout writes "Orders: EGD with esophageal dilation"
    over a planned EMR, or over "Resection of the lesion at a tertiary center", which must never read ready."""

    LABELS = ('Referral: Dr. B. Synthetic, primary care', 'Orders: CBC and iron studies', 'Referrals: GI clinic',
              'To do: pathology follow-up', 'Pending orders: CBC')

    def test_the_claimed_labels_under_the_procedure_line(self):
        for label in self.LABELS:
            text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\n' + label + '\nThe colonoscope was advanced '
                    'to the cecum.\n' + S5_POLYP + '\nImpression: Sigmoid polyp.\n')
            with self.subTest(label=label):
                self.assert_held_never_excluded(text, '45385', S5_POLYP)
                # the prose under the label is held too, never planned (a cited span across the two lines holds)
                self.assertEqual(read(text, 'The colonoscope was advanced to the cecum.')[0], 'uncertain')
                self.assert_held_never_excluded(text, '45385', 'The colonoscope was advanced to the cecum.\n' + S5_POLYP)

    def test_the_claimed_labels_in_a_findings_list(self):
        for label in self.LABELS:
            text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\nFindings:\n' + label + '\nThe colonoscope '
                    'was advanced to the cecum.\n' + S5_POLYP + '\nImpression: Sigmoid polyp.\n')
            with self.subTest(label=label):
                self.assertNotEqual(run_engine(text, [('45385', S5_POLYP)])['45385'].bucket, 'excluded')

    def test_more_shapes(self):
        polyp_field = 'Polypectomy: 6 mm sigmoid polyp removed with cold snare'
        for body, phrase in (('Indication: Positive FIT\nReferral: Dr. B. Synthetic\nCecum reached.\n' + S5_POLYP, S5_POLYP),
                             ('Referral: Dr. B. Synthetic\nThe colonoscope was advanced to the cecum.\n' + polyp_field,
                              polyp_field),
                             ('Referral: Dr. B. Synthetic\nA 6 mm sigmoid polyp was removed with a cold snare.',
                              'A 6 mm sigmoid polyp was removed with a cold snare.')):
            text = HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\n' + body + '\nImpression: Sigmoid polyp.\n'
            with self.subTest(body=body):
                self.assertNotIn(read(text, phrase)[0], NOT_TODAY)
                self.assertNotEqual(run_engine(text, [('45385', phrase)])['45385'].bucket, 'excluded')

    def test_a_planned_emr_after_the_label_is_never_ready(self):
        for label in ('Orders: EGD with esophageal dilation', 'Referral: GI surgery\n', 'Referrals: advanced endoscopy'):
            text = emr_note(label)
            with self.subTest(label=label):
                self.assertNotIn(read(text, EMR_LINE)[0], POSITIVE)
                self.assert_never_ready(text, '45390', EMR_LINE)
        text = emr_note('Referrals: advanced endoscopy\nGI clinic in 2 weeks')  # the second line after the label
        self.assert_never_ready(text, '45390', EMR_LINE)
        text = HEADER + R2_FIND + 'Referral: Dr. B.\nThe ascending colon polyp needs\nEMR at a tertiary center.\n'
        self.assert_never_ready(text, '45390', 'The ascending colon polyp needs\nEMR at a tertiary center.')
        self.assert_never_ready(text, '45390', 'EMR at a tertiary center.')

    def test_prose_that_names_no_service_is_held_too(self):
        """A planned procedure written without a service name the readers know ("Resection of the lesion at a tertiary
        center.") is never read in the section before the label, in a positive section or in an impression or an
        indication, where a silent line would take the colonoscopy's performed reading."""
        line = 'Resection of the ascending colon lesion at a tertiary center.'
        for heading in ('', 'Impression: Ascending colon polyp.\n', 'Indication: Surveillance.\n'):
            text = HEADER + R2_FIND + heading + 'Referrals: advanced endoscopy\n' + line + '\n'
            with self.subTest(heading=heading):
                self.assert_held_never_excluded(text, '45390', line)

    def test_the_labels_own_value_wrapped_onto_the_next_line_plans(self):
        line = 'advanced endoscopy for EMR of the ascending colon polyp'
        text = HEADER + R2_FIND + 'To do: refer to\n' + line + '\n'
        self.assertEqual(read(text, line)[0], 'planned')
        self.assertEqual(run_engine(text, [('45390', line)])['45390'].bucket, 'excluded')

    def test_outside_a_procedure_findings_or_technique_section_the_section_in_force_reads(self):
        base = HEADER + R2_FIND
        for heading, status in (('Plan:', 'planned'), ('Past history:', 'historical')):
            text = base + heading + '\nReferral: GI clinic\n' + EMR_LINE + '\n'
            with self.subTest(heading=heading):
                self.assertEqual(read(text, EMR_LINE)[0], status)
                self.assertEqual(run_engine(text, [('45390', EMR_LINE)])['45390'].bucket, 'excluded')



# --- sections:1: a performed-today label whose answer is none in words -----------------------------------------------

S1_ITEM = '2. Upper endoscopy to D2 with balloon dilation at the hospital endoscopy unit.'
S1_VISIT = 'Established patient office visit for dysphagia.'


def s1_note(line, item=S1_ITEM):
    return (HEADER + 'Place of service: Office (POS 11)\n' + S1_VISIT + '\nChief complaint: Dysphagia.\nAssessment and '
            'plan:\n1. Dysphagia, likely peptic stricture.\n' + line + '\n' + item + '\n3. Continue omeprazole.\nMedical '
            'decision making: moderate.\nTotal time: 32 minutes.\n')


class Sections1TodayLabelAnsweredNoneInWordsTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:1 (critical, a round-3b regression left in place for every answer but the exact no-answer values) -
    "Procedures performed today: None today" (and "none performed", "No procedures performed", ...) opened a procedure
    section over the plan, so the planned EGD after it was a READY 43249. Under a procedure section that one of round
    3b's performed-today labels opens over a plan or history section, a line after the label's own line that only that
    section would read as performed is held, never performed (R3B-BASE excluded it as planned; the hold is the
    verifier's general form, so no list of ways to say none is needed). A line with its own performance cue or a box
    keeps its reading (round 3 contract:8's checked list under the bare label)."""

    CLAIMED = ('Procedures performed today: None today', 'Procedures performed today: none performed',
               'Procedures performed today: No procedures performed', 'Procedures performed today: None were performed',
               'Procedures performed today: none (scheduled at the hospital)', 'Interventions performed: none today',
               'Procedures done today: no procedures', 'Procedures performed today:\nNo procedures',
               'Procedures performed today:\nNone today')
    EXTRA = ('Procedures performed today: None; EGD with dilation to be scheduled.',
             'Procedures performed today: None. EGD to be scheduled at the hospital.',
             'Procedures performed today: None at this visit', 'Procedures performed today: Nothing',
             'Procedure performed today: none - EGD to be arranged')

    def test_the_claimed_and_extra_answers(self):
        for line in self.CLAIMED + self.EXTRA:
            text = s1_note(line)
            with self.subTest(line=line):
                self.assertNotIn(read(text, S1_ITEM)[0], POSITIVE)
                self.assertNotIn(family(text, 'gi.egd'), POSITIVE)
                proposal = run_engine(text, [('43249', S1_ITEM), ('99214', S1_VISIT)])['43249']
                self.assertFalse(ready(proposal), (proposal.bucket, proposal.status))

    def test_under_a_history_section(self):
        item = 'Upper endoscopy with balloon dilation of a peptic stricture'
        text = (HEADER + 'Place of service: Office (POS 11)\n' + S1_VISIT + '\nInterval history:\nDysphagia for 3 months.\n'
                'Procedures performed today: None today\n' + item + '\nTotal time: 32 minutes.\n')
        self.assertNotIn(read(text, item)[0], POSITIVE)
        self.assert_never_ready(text, '43249', item)

    def test_the_label_at_the_top_of_the_plan(self):
        item = '1. Dysphagia, likely peptic stricture - upper endoscopy to the duodenum with balloon dilation.'
        text = (HEADER + 'Place of service: Office (POS 11)\n' + S1_VISIT + '\nChief complaint: Dysphagia.\nAssessment and '
                'plan:\nProcedures performed today: None today\n' + item + '\nTotal time: 32 minutes.\n')
        self.assertNotIn(read(text, item)[0], POSITIVE)
        self.assert_never_ready(text, '43249', item)

    def test_the_labels_own_line_and_checked_items_keep_their_reading(self):
        office = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nChief complaint: Rectal '
                  'bleeding.\nMedical decision making: Moderate.\nAssessment and plan: Grade II internal hemorrhoids.\n')
        for line in ('Procedures performed today: flexible sigmoidoscopy to 30 cm',
                     'Procedures performed today:\n\u2612 Flexible sigmoidoscopy to 30 cm',
                     'Procedures performed today: no sedation; flexible sigmoidoscopy to 30 cm',
                     'Procedures performed today:\nFlexible sigmoidoscopy to 30 cm was performed.'):
            text = office + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.flex_sig'), 'performed')
                self.assertTrue(ready(run_engine(text, [('45330', 'lexible sigmoidoscopy to 30 cm')])['45330']))

    def test_an_unboxed_item_under_the_bare_label_is_held_not_excluded(self):
        """The accepted cost of the general form: an unchecked, unverbed item under the bare label in a plan is held
        (HEAD read it performed, R3B-BASE excluded it), never excluded."""
        text = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nAssessment and plan: Grade II '
                'internal hemorrhoids.\nProcedures performed today:\nFlexible sigmoidoscopy to 30 cm\n')
        self.assert_held_never_excluded(text, '45330', 'Flexible sigmoidoscopy to 30 cm')

    def test_outside_a_plan_or_history_section_the_label_reads_as_before(self):
        polyp = 'Cold snare polypectomy of a 6 mm sigmoid polyp'
        for before in ('Findings: The colonoscope was advanced to the cecum.\n', 'Sedation: Monitored anesthesia care.\n'):
            text = (HEADER + 'Procedure: Colonoscopy\n' + before + 'Procedures performed today: colonoscopy with '
                    'polypectomy\n' + polyp + '\nFindings: The colonoscope was advanced to the cecum.\n')
            with self.subTest(before=before):
                self.assertEqual(read(text, polyp)[0], 'performed')
                self.assertTrue(ready(run_engine(text, [('45385', polyp)])['45385']))
        text = s1_note('Procedures performed today: none')  # an exact no-answer value: no heading, as at R3B-BASE
        self.assertEqual(run_engine(text, [('43249', S1_ITEM)])['43249'].bucket, 'excluded')
        self.assertTrue(ready(run_engine(text, [('99214', S1_VISIT)])['99214']))


if __name__ == '__main__':
    unittest.main()
