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
        # round 4d sections:5: all three bases read it as history, but a Word list writes its items bare, so the bare item
        # is held as the numbered one is (an accepted over-hold for a real colon-less history label inside findings)
        self.assertEqual(kind_at(text, '6 mm sigmoid polyp'), 'other')
        self.assertNotEqual(run_engine(text, [('45385', '6 mm sigmoid polyp removed with cold snare')])['45385'].bucket,
                            'excluded')
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
        for line in ('Prior procedures', 'Previous procedures'):
            text = s0_under_procedure(line)
            with self.subTest(line=line):
                self.assertEqual(kind_at(text, S0_EMR), 'history')
                self.assertEqual(run_engine(text, [('45390', S0_EMR)])['45390'].bucket, 'excluded')
        # round 4d sections:5 (accepted over-hold): an unknown colon-less history label under the procedure line opens
        # the held 'other' section whatever its marker (a Word list writes none), so the cued EMR under it is held,
        # never ready and never excluded; known headings ("Prior procedures") still open history
        text = s0_under_procedure('History of prior procedures')
        self.assertEqual(kind_at(text, S0_EMR), 'other')
        self.assertEqual(read(text, S0_EMR)[0], 'uncertain')
        proposal = run_engine(text, [('45390', S0_EMR)])['45390']
        self.assertEqual((proposal.bucket, proposal.status), ('selected', 'needs_clarification'))
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
                     'Procedures performed today: no sedation; flexible sigmoidoscopy to 30 cm'):
            text = office + line + '\n'
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.flex_sig'), 'performed')
                self.assertTrue(ready(run_engine(text, [('45330', 'lexible sigmoidoscopy to 30 cm')])['45330']))

    def test_a_cued_line_below_the_label_is_held_too(self):
        """A line with its own performance cue below the label's line is held as well: under "Past history:" R3B-BASE read
        "EGD with balloon dilation was performed." historical, under a plan it held it. Only a checked box keeps the
        section's reading. The accepted cost: a cued item under the bare label in a plan is held (HEAD: performed)."""
        line = 'EGD with balloon dilation was performed.'
        for before in ('Past history:\n', 'Assessment and plan:\n1. Dysphagia.\n', 'Chief complaint: Dysphagia.\n'):
            text = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit.\n' + before + 'Procedures '
                    'performed today: None today\n' + line + '\n')
            with self.subTest(before=before):
                self.assertNotIn(read(text, line)[0], POSITIVE)
                self.assert_never_ready(text, '43249', line)
        text = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nAssessment and plan: Grade II '
                'internal hemorrhoids.\nProcedures performed today:\nFlexible sigmoidoscopy to 30 cm was performed.\n')
        self.assert_held_never_excluded(text, '45330', 'Flexible sigmoidoscopy to 30 cm was performed.')

    def test_an_unboxed_item_under_the_bare_label_is_held_not_excluded(self):
        """The accepted cost of the general form: an unchecked, unverbed item under the bare label in a plan is held
        (HEAD read it performed, R3B-BASE excluded it), never excluded."""
        text = (HEADER + 'Place of service: Office (POS 11)\nEstablished patient office visit.\nAssessment and plan: Grade II '
                'internal hemorrhoids.\nProcedures performed today:\nFlexible sigmoidoscopy to 30 cm\n')
        self.assert_held_never_excluded(text, '45330', 'Flexible sigmoidoscopy to 30 cm')

    def test_over_any_section_but_a_positive_one(self):
        """After an examination, an impression, a chief complaint, an 'other' heading or at the top, R3B-BASE held the
        item (it read in that silent section) and HEAD read it a READY 43249: held too."""
        visit = 'Established patient office visit for dysphagia.'
        for before in ('Physical examination: Abdomen soft.\n', 'Impression: Peptic stricture.\n',
                       'Chief complaint: Dysphagia.\n', 'Sedation: none.\n', ''):
            text = (HEADER + 'Place of service: Office (POS 11)\n' + visit + '\n' + before + 'Procedures performed today: '
                    'None today\n' + S1_ITEM + '\nTotal time: 32 minutes.\n')
            with self.subTest(before=before):
                self.assertNotIn(read(text, S1_ITEM)[0], POSITIVE)
                self.assert_never_ready(text, '43249', S1_ITEM)
        text = 'Procedures performed today: None today\n' + S1_ITEM + '\n'  # nothing before the label at all
        self.assertNotIn(read(text, S1_ITEM)[0], POSITIVE)

    def test_after_a_positive_section_a_negated_answer_holds(self):
        """After a procedure or findings section a label whose answer carries a negation word holds the lines below it
        too (R3B-BASE: the "None" doubted the next line in the same section); an ordinary answer reads as before."""
        for before in ('Procedure: EGD\n', 'Procedure: EGD\nFindings: The gastroscope was advanced to the duodenum.\n'):
            for label in ('- Procedures performed today: None today', 'Procedures performed today: No procedures performed',
                          'Procedures performed today:\nNone today', 'Procedures performed today:\n\nnone performed'):
                text = HEADER + before + label + '\n' + S1_ITEM + '\n'
                with self.subTest(before=before, label=label):
                    self.assertNotIn(read(text, S1_ITEM)[0], POSITIVE)
                    self.assert_never_ready(text, '43249', S1_ITEM)

    def test_after_a_positive_section_the_label_reads_as_before(self):
        polyp = 'Cold snare polypectomy of a 6 mm sigmoid polyp'
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum.\nProcedures performed '
                'today: colonoscopy with polypectomy\n' + polyp + '\n')
        self.assertEqual(read(text, polyp)[0], 'performed')
        self.assertTrue(ready(run_engine(text, [('45385', polyp)])['45385']))
        # under an 'other' heading the next line is held, as R3B-BASE held it (an accepted over-hold against HEAD)
        text = (HEADER + 'Procedure: Colonoscopy\nSedation: Monitored anesthesia care.\nProcedures performed today: '
                'colonoscopy with polypectomy\n' + polyp + '\nFindings: The colonoscope was advanced to the cecum.\n')
        self.assertEqual(read(text, polyp)[0], 'uncertain')
        self.assertEqual(read(text, 'colonoscopy with polypectomy')[0], 'performed')  # the label's own line
        text = s1_note('Procedures performed today: none')  # an exact no-answer value: no heading, as at R3B-BASE
        self.assertEqual(run_engine(text, [('43249', S1_ITEM)])['43249'].bucket, 'excluded')
        self.assertTrue(ready(run_engine(text, [('99214', S1_VISIT)])['99214']))



# --- declared:3: an outside report's preparation line made its extent today's ----------------------------------------

D3_POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'
D3_TODAY = ('Procedure: Colonoscopy with cold snare polypectomy.\nFindings: The colonoscope was advanced to the hepatic '
            'flexure. ' + D3_POLYP + '\nImpression: Sigmoid polyp.\n')


class Declared3AnsweringSectionsTests(unittest.TestCase):
    """declared:3 (critical, a regression against R3B-BASE) - an outside report's own "Prep:", "Bowel preparation:" or
    "Complications:" line opened an 'other' section that round 4b counted as this report's own, so its "Extent: cecum"
    made an incomplete colonoscopy complete (R3B-BASE: incomplete at the hepatic flexure, with the service.incomplete
    check). Reverted, as the verifier asked: an extent label answers silently only in the product's addendum block and
    the PDF form-field and annotation blocks. The report's own "Bowel preparation: adequate. Furthest extent reached:
    cecum." goes back to its R3B-BASE reading too (the extent is not read: an extent hold, the accepted over-hold)."""

    BLOCKS = ('Prior colonoscopy (outside facility, 2021):\nPrep: adequate\nExtent: cecum\nFindings: two tubular adenomas\n',
              'Outside records: Colonoscopy at another facility in 2021.\nBowel preparation: good. Extent: cecum.\n',
              'Referral information: colonoscopy in 2021 elsewhere.\nComplications: none. Extent: cecum.\n',
              'Last colonoscopy (2021, outside):\nBowel preparation: good\nExtent: cecum\n',
              'Outside records:\nColonoscopy at another facility in 2021.\nPrep: good. Extent: cecum.\n',
              'History:\nColonoscopy in 2021 elsewhere.\nQuality of preparation: fair. Extent reached: cecum.\n')

    def test_the_claimed_and_listed_blocks(self):
        for block in self.BLOCKS:
            text = HEADER + block + D3_TODAY
            with self.subTest(block=block):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'incomplete')
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'incomplete: hepatic flexure')
                proposal = run_engine(text, [('45385', D3_POLYP)])['45385']
                self.assertIn('service.incomplete', {c.id for c in proposal.checks if c.status in ('warn', 'fail')})

    def test_the_flexible_sigmoidoscopy_depth(self):
        text = (HEADER + 'Outside records:\nFlexible sigmoidoscopy at another facility in 2021.\nPrep: good. Depth of '
                'insertion: 60 cm.\nProcedure: Flexible sigmoidoscopy with biopsy.\nFindings: A biopsy was taken from the '
                'rectum.\n')
        self.assertIsNone(fact_value(text, 'gi.flex_sig', 'extent'))
        self.assertFalse(ready(run_engine(text, [('45331', 'A biopsy was taken from the rectum.')])['45331']))

    def test_the_addendum_block_still_answers(self):
        from tests.test_repairs_r3_wording import addendum_text
        parent = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: ' + D3_POLYP + '\nNotes:\nThe '
                  'patient tolerated the procedure.\n')
        text = addendum_text(parent, 'Furthest extent reached: cecum.')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
        self.assertTrue(ready(run_engine(text, [('45385', D3_POLYP)])['45385']))



# --- sections:7 / sections:8 / declared:5: a negation that reaches a service only across an answer on the line above --

S7_BIOPSY = 'Biopsies were taken from the gastric antrum to evaluate for Helicobacter pylori.'
D5_BIOPSY = 'biopsies were taken from the mid esophagus to evaluate for eosinophilic esophagitis.'
S8_POLYP = 'Cold snare polypectomy of a 6 mm sigmoid polyp was performed.'


def s7_note(question, line=S7_BIOPSY):
    return (HEADER + 'Procedure: EGD with biopsy.\nIndication: Dyspepsia.\nPre-procedure assessment:\n' + question + '\n'
            + line + '\nThe gastroscope was advanced to the second part of the duodenum.\n')


def d5_note(answer):
    return HEADER + 'Procedure: EGD with biopsy.\nIndication: Dysphagia.\nFindings:\n' + answer + '\n' + D5_BIOPSY + '\n'


def s8_note(line):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nTechnique: The colonoscope was advanced to the '
            'cecum.\n' + line + '\n' + S8_POLYP + '\nImpression: Sigmoid polyp.\n')


class AnswerOnTheLineAboveTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:7, sections:8 and declared:5 (high) - a line that ends in an answer of its own was joined to the service
    line under it, and its "No" negated that service (43239 / 45385 excluded): a field question longer than 60
    characters ("Has the patient had a prior adverse reaction to sedation or anesthesia? No"), a spoken answer written
    with a comma ("the patient said, no"), and a dash, column or option-row answer before a lower-case line
    ("Schatzki ring present - no", "Schatzki ring present      no", "Hiatal hernia [box] Yes [box] No"). The join itself
    stays (every base excluded these, so ending the sentence would release); the cross-line negation HOLDS instead
    (a doubt), read from the whole line above with sections' own answer readers, so the two never disagree."""

    QUESTIONS = ('Has the patient had a prior adverse reaction to sedation or anesthesia? No',
                 'Did the patient stop clopidogrel at least 5 days before the procedure? No',
                 'Any anticoagulant or antiplatelet medication taken in the past 7 days? no',
                 'History of an adverse reaction to sedation or to anesthesia in the past - no',
                 "Was there any evidence of Barrett's esophagus at the GE junction? No",
                 'Prior adverse reaction to sedation? no')

    def test_a_long_question_answered_no(self):
        lower = S7_BIOPSY[0].lower() + S7_BIOPSY[1:]
        for question in self.QUESTIONS:
            for line in (S7_BIOPSY, lower):
                text = s7_note(question, line)
                with self.subTest(question=question, line=line[:10]):
                    if line == S7_BIOPSY and len(question) < 60:
                        # sections reads a short question as answered: the capitalised line is never joined, performed
                        self.assertEqual(read(text, line)[0], 'performed')
                    else:
                        self.assert_held_never_excluded(text, '43239', line)

    def test_the_short_controls_still_read(self):
        for question in ('Did the patient stop clopidogrel 5 days before the procedure? No', 'Schatzki ring present: no'):
            text = s7_note(question)
            with self.subTest(question=question):
                self.assertTrue(ready(run_engine(text, [('43239', S7_BIOPSY)])['43239']))

    def test_a_spoken_answer_with_a_comma(self):
        for line in ('When asked about a biopsy of the hemorrhoid, the patient said, no',
                     'When asked about a biopsy of the hemorrhoid, she said, No',
                     'When asked about a biopsy of the hemorrhoid, the patient answered, no',
                     'When asked about a biopsy of the hemorrhoid, the patient replied, no',
                     'When asked about a biopsy of the hemorrhoid, the patient said , no',
                     'When asked about a biopsy of the hemorrhoid, the patient said: no'):
            text = s8_note(line)
            with self.subTest(line=line):
                self.assertNotIn(read(text, S8_POLYP)[0], NOT_TODAY)
                self.assertNotEqual(run_engine(text, [('45385', S8_POLYP)])['45385'].bucket, 'excluded')

    def test_cut_prose_still_negates(self):
        """Cut prose is a wrapped sentence, not an answer: it stays negated (round 2 status:16)."""
        text = (HEADER + 'Procedure: EUS.\nFindings: Comment: because of time constraints, no\nEUS of the pancreatic cyst was '
                'performed today.\n')
        self.assertEqual(read(text, 'EUS of the pancreatic cyst was performed today.')[0], 'negated')
        text = s8_note('When asked about a biopsy, the patient said, no')
        text = text.replace(S8_POLYP, 'EUS of the pancreatic cyst.')  # a verbless next line runs on, as before
        self.assertEqual(read(text, 'EUS of the pancreatic cyst.')[0], 'negated')
        text = HEADER + 'Procedure: EGD.\nFindings: Colonoscopy was performed - no\nbiopsies were taken from the antrum.\n'
        self.assertEqual(read(text, 'biopsies were taken from the antrum.')[0], 'negated')

    def test_answers_above_a_lower_case_line(self):
        for answer in ('Schatzki ring present: no', 'Schatzki ring present - no', 'Schatzki ring present \u2013 no',
                       'Schatzki ring present      no', 'Schatzki ring present\tno', 'Schatzki ring present [ ] Yes [x] No',
                       'Schatzki ring: \u2610 Yes \u2612 No', 'Hiatal hernia \u2610 Yes \u2612 No',
                       'Hiatal hernia \u2612 Yes \u2610 No'):
            text = d5_note(answer)
            with self.subTest(answer=answer):
                self.assert_held_never_excluded(text, '43239', D5_BIOPSY)
        text = d5_note('Mucosa: normal, hiatal hernia: no')  # read performed before, and still never negated
        self.assertNotIn(read(text, D5_BIOPSY)[0], NOT_TODAY)

    def test_an_answer_after_a_heading_label_on_its_line(self):
        """Read the way sections reads it, from after the heading label on that line."""
        text = (HEADER + 'Procedure: EGD with biopsy.\nIndication: Dysphagia.\nFindings: Schatzki ring present      no\n'
                + D5_BIOPSY + '\n')
        self.assert_held_never_excluded(text, '43239', D5_BIOPSY)

    def test_an_upper_case_line_and_a_denial_on_its_own_line(self):
        text = d5_note('Schatzki ring present - no').replace(D5_BIOPSY, D5_BIOPSY[0].upper() + D5_BIOPSY[1:])
        self.assertEqual(read(text, D5_BIOPSY[0].upper() + D5_BIOPSY[1:])[0], 'performed')
        text = d5_note('Schatzki ring present - no').replace(D5_BIOPSY, 'no biopsies were taken.')
        self.assertEqual(read(text, 'no biopsies were taken.')[0], 'negated')



# --- sections:9 / sections:10: the line after a line cut on a plan, cancellation or denial verb -----------------------

S9_EUS = 'EUS with fine-needle aspiration of the pancreatic head mass'


def s9_note(cut, line):
    return (HEADER + 'Procedure: EGD.\nIndication: Dysphagia; pancreatic head mass on CT.\nFindings: The gastroscope was '
            'advanced to the second portion of the duodenum. The esophagus was normal. ' + cut + '\n' + line + '\n')


S10_POLYP = 'Cold snare polypectomy of a 6 mm sigmoid polyp.'


def s10_note(line):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nTechnique: After informed consent was obtained, the '
            'colonoscope was advanced to the cecum. ' + line + '\n' + S10_POLYP + '\nImpression: Sigmoid polyp.\n')


class CutVerbHoldTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:9 (high, an under-correction of structure:11) - the hold of a service line after a line cut on a plan,
    cancellation or denial verb ("Dr. Smith recommended") skipped a bulleted or numbered service line, so "- EUS with
    FNA ..." was a READY 43242; the hold now reads the line without its list marker (a field or a table row stays
    exempt). sections:10 (medium) - it fires after a complete sentence that ends in a kept booking ("The procedure was
    performed as planned"), holding an ordinary polypectomy: deliberately left held (see the test below)."""

    def test_a_marked_service_line_is_held(self):
        for cut in ('Dr. Smith recommended', 'The endoscopist deferred', 'The family declined to authorize'):
            for mark in ('- ', '* ', '1. ', '1) ', '  - ', 'A. ', '(1) ', '\u2022 ', ''):
                line = mark + S9_EUS
                text = s9_note(cut, line)
                with self.subTest(cut=cut, mark=mark):
                    self.assert_held_never_excluded(text, '43242', S9_EUS)
            # a lower-case letter marker joins the cut line, as at HEAD: the cut verb's own cue reads the service
            text = s9_note(cut, 'a) ' + S9_EUS)
            with self.subTest(cut=cut, mark='a) '):
                self.assert_never_ready(text, '43242', S9_EUS)
        text = s9_note('Dr. Smith recommended', '- ' + S9_EUS + '.')
        self.assert_held_never_excluded(text, '43242', S9_EUS + '.')
        text = s9_note('Dr. Smith recommended', '- eus with fine-needle aspiration of the pancreatic head mass')
        self.assert_never_ready(text, '43242', 'eus with fine-needle aspiration of the pancreatic head mass')
        for line in ('EUS: FNA of the pancreatic head mass', '- EUS: FNA of the pancreatic head mass'):  # a service field
            text = s9_note('Dr. Smith recommended', line)
            with self.subTest(field=line):
                self.assert_held_never_excluded(text, '43242', 'EUS: FNA of the pancreatic head mass')

    def test_a_list_item_after_a_cut_list_item_is_held_too(self):
        """Dropping the list-item exemption holds more, the safe direction (an accepted over-hold)."""
        text = (HEADER + 'Procedure: EGD.\nFindings:\n1. The esophagus was normal.\n2. Genetic testing recommended\n3. '
                + S9_EUS + '\n')
        self.assert_held_never_excluded(text, '43242', S9_EUS)

    def test_the_controls(self):
        text = s9_note('Dr. Smith recommended ' + S9_EUS[0].lower() + S9_EUS[1:] + '.', 'Biopsies were not taken.')
        self.assertEqual(run_engine(text, [('43242', S9_EUS[0].lower() + S9_EUS[1:])])['43242'].bucket, 'excluded')
        for line in ('Referring physician: Dr. B. Synthetic', 'EUS | FNA | pancreatic head mass'):
            text = s9_note('Dr. Smith recommended', line)
            with self.subTest(line=line):
                self.assertNotEqual(kind_at(text, line), 'other')
        polyp = '4. 6 mm sigmoid polyp removed with cold snare.'  # round 3 routing:2: an item with a clause of its own
        text = (HEADER + 'Procedure: Colonoscopy with biopsy and cold snare polypectomy.\nFindings:\n1. The colonoscope was '
                'advanced to the cecum.\n2. A 3 cm ascending colon mass, biopsied and tattooed.\n3. Further workup '
                'recommended\n' + polyp + '\n')
        self.assertTrue(ready(run_engine(text, [('45385', polyp)])['45385']))

    def test_a_kept_booking_line_still_holds_and_never_excludes(self):
        """sections:10 is deliberately NOT released: after an unpunctuated kept-booking sentence ("The procedure was
        performed as planned") a verbless service line may be the performed polypectomy or the planned EMR at a
        tertiary center written the same way, and lifting the hold read the EMR a READY 45390 (HEAD held it). So both
        are held, never excluded; with closing punctuation the sentence ends and the polypectomy reads performed."""
        emr = 'EMR of the ascending colon lesion at a tertiary center.'
        for line in ('The procedure was performed as planned', 'The patient completed the bowel preparation as ordered',
                     'The patient arrived for the procedure as scheduled', 'Moderate sedation was given as planned'):
            with self.subTest(line=line):
                self.assert_held_never_excluded(s10_note(line), '45385', S10_POLYP)
                self.assert_never_ready(s10_note(line).replace(S10_POLYP, emr), '45390', emr)
                text = s10_note(line + '.')
                self.assertEqual(read(text, S10_POLYP)[0], 'performed')

    def test_a_cut_plan_verb_still_holds(self):
        for line in ('Dr. Smith recommended', 'The procedure was planned', 'Dr. Smith ordered',
                     'The procedure will be done as scheduled', 'The procedure was postponed as planned',
                     'Procedure scheduled as planned', 'The second study was put off, as deferred'):
            text = s10_note(line)
            with self.subTest(line=line):
                self.assert_held_never_excluded(text, '45385', S10_POLYP)



# --- declared:6: a denying label in other spellings -------------------------------------------------------------------

D6_EGD = 'EGD with balloon dilation.'


def d6_note(label):
    return (HEADER + 'Procedures performed: EGD with biopsy.\nIndication: Dysphagia.\nFindings: The endoscope was advanced to '
            'the second part of the duodenum. Mild esophagitis; biopsies were taken.\n' + label + '\n' + D6_EGD + '\nPlan: '
            'PPI twice daily.\n')


class Declared6DenyingLabelSpellingsTests(HeldOrReadyAssertions, unittest.TestCase):
    """declared:6 (high) - a label that denies performance ("Procedures not performed:", "Cancelled procedures:") held
    the service listed under it only in one spelling: a numbered, lettered or bulleted label ("1. Procedures not
    performed:", "• Cancelled procedures:") or one with parentheses ("Procedure(s) not performed:", "Cancelled
    procedures (patient request):") left the cancelled EGD with dilation a ready 43249. The label is read with the list
    markers the other readers strip (detect._LEADING_MARK's) and with parentheses in its words. Colon-less denying lines
    stay a recorded residual (the label rule is a line that ends with a colon)."""

    LABELS = ('1. Procedures not performed:', '2) Procedures not performed:', 'b. Procedures not performed:',
              '(1) Procedures not performed:', '\u2022 Procedures not performed:', '\u2022 Cancelled procedures:',
              '\u00b7 Procedures not performed:', 'Procedure(s) not performed:', 'Procedures not performed (see note):',
              'Cancelled procedures (patient request):', 'Procedure(s) cancelled:', '1. Cancelled procedures:',
              'Procedures not performed:', '- Procedures not performed:', '* Cancelled procedures:')

    def test_every_spelling_holds(self):
        for label in self.LABELS:
            text = d6_note(label)
            with self.subTest(label=label):
                self.assertNotIn(read(text, D6_EGD)[0], POSITIVE)
                proposal = run_engine(text, [('43249', D6_EGD)])['43249']
                self.assertTrue(held(proposal), (proposal.bucket, proposal.status))

    def test_a_numbered_outline_report(self):
        text = (HEADER + '1. Procedures performed: EGD with biopsy.\n2. Indication: Dysphagia.\n3. Findings: The endoscope was '
                'advanced to the second part of the duodenum. Mild esophagitis; biopsies were taken.\n4. Procedures not '
                'performed:\n' + D6_EGD + '\n')
        self.assertTrue(held(run_engine(text, [('43249', D6_EGD)])['43249']))

    def test_other_labels_are_unchanged(self):
        for label in ('Additional procedures:', '1. Additional procedures:', 'Procedures (all performed):'):
            text = d6_note(label)
            with self.subTest(label=label):
                self.assertTrue(ready(run_engine(text, [('43249', D6_EGD)])['43249']))



# --- declared:11: ordinary extent labels the closed tail list left unread --------------------------------------------

D11_POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'


class Declared11ExtentTailTests(unittest.TestCase):
    """declared:11 (high) - cues.EXTENT_TAIL, the closed list of words that may follow an extent label's landmark, lacked
    the landmark table's own spellings ("TI", "neo-terminal", "cecal base"), and a Word table row's or a column
    layout's next cell was read as the value's tail ("Extent: Cecum | Prep quality: Good"), so an ordinary extent label
    stayed unread (45385 held for the extent, and with prose naming the rectum the colonoscopy read INCOMPLETE). The
    tail now admits those spellings, and a next cell ends the value when it opens one of a closed list of other report
    fields; any other next cell ("| intended", "| Reached: No") stays in the tail, so an aim still leaves it unread."""

    def note(self, extent, where='after procedure', technique=''):
        if where == 'after procedure':
            return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\n' + technique + extent + '\nFindings: '
                    + D11_POLYP + '\n')
        if where == 'in findings':
            return HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings:\n' + extent + '\n' + D11_POLYP + '\n'
        return HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: ' + D11_POLYP + '\n' + extent + '\n'

    READ = (('Extent: cecum and TI.', 'cecum'), ('Extent reached: terminal ileum (TI).', 'terminal ileum'),
            ('Extent: Cecum | Prep quality: Good | Withdrawal time: 9 min', 'cecum'), ('Extent: cecum    Prep: good', 'cecum'),
            ('Extent reached: cecum | Boston Bowel Preparation Scale: 8', 'cecum'), ('Extent: cecum\tWithdrawal time: 8 min', 'cecum'),
            ('Extent: neo-terminal ileum.', 'terminal ileum'), ('Extent: cecum (cecal base).', 'cecum'),
            ('Extent: Cecum | Bowel preparation: adequate', 'cecum'), ('Extent: cecum | BBPS: 8', 'cecum'))

    def test_ordinary_extent_labels_are_read(self):
        for extent, value in self.READ:
            for where in ('after procedure', 'in findings', 'after findings'):
                text = self.note(extent, where)
                with self.subTest(extent=extent, where=where):
                    self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), value)
                    self.assertTrue(ready(run_engine(text, [('45385', D11_POLYP)])['45385']))

    def test_never_incomplete_from_the_rectum_beside_a_table_row(self):
        technique = 'Technique: The colonoscope was inserted into the rectum and advanced without difficulty.\n'
        for extent in ('Extent: Cecum | Prep quality: Good | Withdrawal time: 9 min', 'Extent: cecum and TI.'):
            text = self.note(extent, technique=technique)
            with self.subTest(extent=extent):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')

    def test_an_aim_or_another_next_cell_still_leaves_it_unread(self):
        for extent in ('Extent: cecum (intended).', 'Extent: cecum was the goal.', 'Extent: cecum | intended',
                       'Extent: cecum | Reached: No', 'Extent: cecum    Intended: yes', 'Extent: cecum, TI intended.',
                       'Extent: cecum (TI not reached).'):
            text = self.note(extent)
            with self.subTest(extent=extent):
                self.assertNotEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
                self.assertFalse(ready(run_engine(text, [('45385', D11_POLYP)])['45385']))



# --- validation:3: a hedged same-day procedure under Assessment and plan ----------------------------------------------

V3_VISIT = 'Established patient office visit.'


def v3_note(line):
    return (HEADER + 'Place of service: Office (POS 11)\n' + V3_VISIT + '\nChief complaint: rectal bleeding.\nHistory of '
            'present illness: Intermittent bright red blood per rectum for three weeks.\n' + line + '\nMedical decision '
            'making: moderate.\nTotal time: 32 minutes.\n')


class Validation3PlanHedgeTodayTests(unittest.TestCase):
    """validation:3 (high) - a same-day procedure stated under "Assessment and plan" whose sentence also hedges the
    diagnosis ("Anoscopy was performed today and showed grade 2 internal hemorrhoids versus prolapse.") kept only the
    hedge cue, so routing dropped PLAN_TODAY with the performance cue and the office E/M was approved without the
    same-day hold. ARCHITECTURE 5.3: in a plan section any clause that says today holds (PLAN_TODAY), whatever hedge is
    in it; routing now carries PLAN_TODAY on such an uncertain reading too, and validation holds the E/M beside it."""

    HELD = ('Assessment and plan: Anoscopy was performed today and showed grade 2 internal hemorrhoids versus prolapse.',
            'Assessment and plan: Rubber band ligation x3 was performed today, ?fissure.',
            'A/P: Flexible sigmoidoscopy was performed today with biopsies, proctitis versus infection.',
            'Assessment and plan: EGD was performed today with biopsies, eosinophilic esophagitis versus reflux.',
            'Impression and plan: Anoscopy was performed today and showed grade 2 internal hemorrhoids vs prolapse.',
            'Plan: Anoscopy was performed today and showed grade 2 internal hemorrhoids versus prolapse.',
            'Assessment and plan: EGD was performed today with biopsies, ?eosinophilic esophagitis.')
    READY = ('Plan: Possible EGD if symptoms persist.', 'Assessment and plan: EGD versus empiric PPI trial.',
             'Plan: GERD. Possible EGD if symptoms persist.',
             'Assessment and plan: Discussed colonoscopy; patient will call to schedule.',
             # round 3 validation:1 and round 2 review:1: a plan clause that hedges, conditions or discusses a
             # procedure and says today, with no performance statement, keeps the visit approvable
             'Assessment and plan: Possible EGD today if symptoms persist.',
             'Assessment and plan: Discussed colonoscopy today; she will think about it.',
             'Assessment and plan: Colonoscopy? Will decide today after labs.')

    def test_the_claimed_lines_hold_the_visit(self):
        for line in self.HELD:
            text = v3_note(line)
            with self.subTest(line=line):
                proposal = run_engine(text, [('99214', V3_VISIT)])['99214']
                self.assertEqual(proposal.status, 'needs_clarification')
                self.assertIn('separate_em', clarified(proposal))

    def test_only_a_procedure_clause_in_a_plan_section_carries_it(self):
        """The rule is the plan arm's: an E/M documentation mention keeps its own reading, and outside a plan section a
        hedge already counts for the same-day check (round 4 validation:0), so no PLAN_TODAY is added there."""
        from studio.gi.detect import PLAN_TODAY
        text = v3_note('Plan: Established patient visit was performed today, ?IBS.')
        status, cues = read(text, 'Established patient visit')
        self.assertEqual(status, 'uncertain')
        self.assertNotIn(PLAN_TODAY, cues)
        text = v3_note('Assessment: EGD was performed today, esophagitis versus reflux.')
        status, cues = read(text, 'EGD was performed today, esophagitis versus reflux.')
        self.assertEqual(status, 'uncertain')
        self.assertNotIn(PLAN_TODAY, cues)
        text = v3_note('Assessment and plan: EGD was performed today, esophagitis versus reflux.')
        self.assertIn(PLAN_TODAY, read(text, 'EGD was performed today, esophagitis versus reflux.')[1])
        # and never on a clause that does not say today: the cue would state something false
        text = v3_note('Assessment and plan: Anoscopy was performed and showed grade 2 internal hemorrhoids versus prolapse.')
        self.assertNotIn(PLAN_TODAY, read(text, 'Anoscopy was performed and showed')[1])

    def test_the_accepted_plan_releases_stay_ready(self):
        for line in self.READY:
            text = v3_note(line)
            with self.subTest(line=line):
                self.assertTrue(ready(run_engine(text, [('99214', V3_VISIT)])['99214']))


if __name__ == '__main__':
    unittest.main()
