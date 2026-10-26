"""Regressions for refutation round 6 over GI section structure, extent labels, denying labels and cross-line answers
(round "4d", SECTIONS2: studio/gi/sections.py and its readers in studio/gi/detect.py).

Each class reproduces one confirmed round-6 finding (sections:N, regression:N, declared:N or bounded:N in the round-6
triage) from its exact input, adds the variants its verifier listed, and pins controls in both directions. The rule of
round 4d (the owner's decision, 2026-10-25): a wording or layout rule may only hold (uncertain, with a non-silent cue);
it may restore the reading an input had at R5 (9a9f40301), R4B-BASE (4347acd24) or R3B-BASE (d05326ef), and it never
newly excludes or releases otherwise. Where a repair restores a base, the test says so; where it holds an input a base
read as performed, the test names the accepted over-hold.

Routing runs for real, for the document's own service date and through the JSON round trip the pipeline applies; the
real validation engine assesses provider-shaped selections against an empty in-memory reference. Synthetic text only.
"""
import unittest

from studio.gi.sections import layout
from tests.test_repairs_r3_sections import (HEADER, NOT_TODAY, POSITIVE, clarified, fact_value, family, read, ready,
                                            routed, run_engine, word_document)


def kind_at(text, phrase):
    return layout(text).section_at(text.index(phrase)).kind


def held(proposal):
    return (proposal.bucket, proposal.status) == ('selected', 'needs_clarification')


def checks(proposal):
    return {c.id: c.status for c in proposal.checks}


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


# --- sections:0: a service field after an answered plan label --------------------------------------------------------

S0_FIND = ('Procedure: Colonoscopy with biopsy and tattoo\nFindings: The colonoscope was advanced to the cecum. A 4 cm '
           'fungating ascending colon mass was biopsied and tattooed.\n')
S0_HEMI = 'Right hemicolectomy: Dr. B. Synthetic, colorectal surgery'
S0_HEMORRHOID = 'Hemorrhoidectomy: excisional, with Dr. B. Synthetic'
S0_CT = 'CT chest, abdomen and pelvis: with IV contrast'


class S2Sections0ServiceFieldAfterAnsweredPlanLabelTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:0 (critical, a regression from 4347acd24 and 9a9f40301) - after a round-3b plan label with an answer of
    its own ("Referral: Colorectal surgery", "Orders: staging studies"), a field line resumed the section in force before
    the label whenever routing knew no service or intervention in it, so a planned right hemicolectomy (44160), a
    hemorrhoidectomy (46255) or a staging CT (74177) written as a field read as findings and was READY. Now only a field
    whose label is a report field of a closed list (extent, depth of insertion, withdrawal, insertion or cecal intubation
    time, preparation and its quality, BBPS, sedation, complications, EBL, findings, retroflexion) resumes; every other
    field line is held for itself, never performed and never planned (the commit's own rule: a service field is held)."""

    def test_the_claimed_inputs(self):
        hemi = HEADER + S0_FIND + 'Referral: Colorectal surgery\nCEA was drawn.\n' + S0_HEMI + '\nImpression: Ascending colon mass.\n'
        self.assert_held_never_excluded(hemi, '44160', S0_HEMI)
        hemorrhoid = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Large internal '
                      'hemorrhoids with stigmata of recent bleeding.\nReferral: Colorectal surgery\nPatient counseled on '
                      'surgical options.\n' + S0_HEMORRHOID + '\nImpression: Internal hemorrhoids.\n')
        self.assert_held_never_excluded(hemorrhoid, '46255', S0_HEMORRHOID)
        ct = (HEADER + 'Procedure: EGD with biopsy\nFindings: The gastroscope was advanced to the second part of the duodenum. '
              'A 3 cm ulcerated gastric body mass was biopsied.\nOrders: staging studies\nTumor markers were sent.\n' + S0_CT
              + '\nImpression: Gastric mass.\n')
        self.assert_held_never_excluded(ct, '74177', S0_CT)

    def test_the_verifiers_variants(self):
        for label, field, code in (('Referral: Colorectal surgery', S0_HEMI, '44160'),
                                   ('Referral: Colorectal surgery', 'Surgery: right hemicolectomy with Dr. B. Synthetic', '44160'),
                                   ('Orders: CEA, CBC', 'CT abdomen/pelvis: with contrast', '74177'),
                                   ('Orders: CEA, CBC\nThe patient was counseled.', 'CT abdomen/pelvis: with contrast', '74177'),
                                   ('To do: refer', 'Hemorrhoidectomy: excisional', '46255'),
                                   ('Referrals: advanced endoscopy', 'Endoscopic resection: ascending colon polyp, tertiary center',
                                    '45390'),
                                   ('Referrals: advanced endoscopy', 'ESD: ascending colon polyp, tertiary center', '45390'),
                                   ('Pending orders: CBC', 'Anoscopy with banding: Dr. B. Synthetic', '46221'),
                                   ('Orders: CBC', 'Esophageal manometry: outpatient', '91010'),
                                   ('Referral: Colorectal surgery', 'Low anterior resection: rectal cancer', '44145')):
            text = HEADER + S0_FIND + label + '\n' + field + '\nImpression: Ascending colon mass.\n'
            with self.subTest(label=label, field=field):
                self.assert_held_never_excluded(text, code, field)

    def test_report_fields_still_read_in_the_section_before_the_label(self):
        """structure:5's repair stands for the report's own fields: they name a fact of this report, never a service."""
        polyp = 'A 6 mm sigmoid polyp was removed with a cold snare.'
        for field in ('Extent: cecum', 'Extent reached: cecum', 'Furthest extent reached: cecum', 'Extent of exam: cecum',
                      'Extent: Cecum | Prep quality: Good', 'Withdrawal time: 8 minutes', 'Insertion time: 5 minutes',
                      'Cecal intubation time: 4 minutes', 'Prep quality: good', 'Quality of prep: good', 'BBPS: 8',
                      'Boston Bowel Preparation Scale: 8', 'Bowel preparation quality: adequate', 'Retroflexion: done',
                      'Withdrawal time: 8 minutes | BBPS: 9', 'Depth of insertion: 60 cm', 'Final extent reached: cecum',
                      'Scope withdrawal time: 9 minutes'):
            text = (HEADER + 'Procedure: Colonoscopy\nReferral: Dr. B. Synthetic, primary care\n' + field + '\nFindings: The '
                    'colonoscope was advanced to the cecum. ' + polyp + '\n')
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, field), 'procedure')
                self.assertEqual(read(text, field)[0], 'performed')
                self.assertTrue(ready(run_engine(text, [('45385', polyp)])['45385']))
        text = (HEADER + 'Procedure: Colonoscopy\nReferral: Dr. B. Synthetic, primary care\nExtent: cecum\nFindings: ' + polyp
                + '\n')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
        text = HEADER + 'Procedure: Colonoscopy\nReferral: Dr. B. Synthetic, primary care\nComplication: none\n'
        self.assertEqual(kind_at(text, 'Complication: none'), 'procedure')  # its own "none" is read as before

    def test_a_landmark_field_that_states_it_reached_reads_as_before(self):
        """A landmark named as a field and only stated reached or seen is the report's own: held, a complete colonoscopy
        would read incomplete at the insertion landmark (HEAD reads the cecum; 4347acd24's 'incomplete: rectum' is wrong)."""
        technique = 'Procedure: Colonoscopy\nTechnique: The colonoscope was inserted into the rectum and advanced.\n'
        for field, extent in (('Cecum: reached', 'cecum'), ('Terminal ileum: intubated', 'terminal ileum'),
                              ('Cecum: reached and photographed', 'cecum'), ('TI: intubated', 'terminal ileum')):
            for label in ('Referral: Colorectal surgery', 'Orders: CBC, iron studies'):
                text = HEADER + technique + label + '\n' + field + '\n'
                with self.subTest(field=field, label=label):
                    self.assertEqual(kind_at(text, field), 'technique')
                    self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), extent)
                    self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        text = HEADER + 'Procedure: EGD\nFindings: The gastroscope was advanced.\nOrders: CBC\nDuodenum: normal\n'
        self.assertEqual(kind_at(text, 'Duodenum: normal'), 'findings')
        hemi = 'Ascending colon: 4 cm mass, for right hemicolectomy'
        text = HEADER + S0_FIND + 'Referral: Colorectal surgery\n' + hemi + '\n'
        self.assert_held_never_excluded(text, '44160', hemi)

    def test_a_report_field_naming_a_service_is_held(self):
        for field in ('Extent: cecum, EMR of the ascending colon polyp at a tertiary center',
                      'Withdrawal time: 8 minutes; EUS with FNA at the next visit'):
            text = HEADER + S0_FIND + 'Referrals: advanced endoscopy\n' + field + '\n'
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, field), 'other')
                self.assertNotIn(read(text, field)[0], POSITIVE)

    def test_any_other_field_is_held_never_performed(self):
        for field in ('Pathology: pending', 'Scope: Olympus CF-HQ190', 'Specimen jar: 1', 'Surgical consult: requested',
                      'Resection: at a tertiary center', 'Radiation oncology: consult',
                      'Ascending colon: 4 cm mass, for right hemicolectomy', 'Rectum: internal hemorrhoids'):
            text = HEADER + S0_FIND + 'Referral: Colorectal surgery\n' + field + '\n'
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, field), 'other')
                status, cues = read(text, field)
                self.assertEqual(status, 'uncertain', cues)
                self.assertFalse(any(cue.startswith('uncertain: no performance evidence') for cue in cues), cues)
        for field in ('Tumor board: next week', 'Clinic: GI surgery in 2 weeks'):  # its own plan cue reads it, as before
            text = HEADER + S0_FIND + 'Referral: Colorectal surgery\n' + field + '\n'
            with self.subTest(field=field):
                self.assertNotIn(read(text, field)[0], POSITIVE)

    def test_inside_a_plan_or_history_section_the_section_reads_the_field(self):
        for heading, status in (('Plan:', 'planned'), ('Past history:', 'historical')):
            text = HEADER + S0_FIND + heading + '\nReferral: Colorectal surgery\n' + S0_HEMI + '\n'
            with self.subTest(heading=heading):
                self.assertEqual(read(text, S0_HEMI)[0], status)
                self.assertEqual(run_engine(text, [('44160', S0_HEMI)])['44160'].bucket, 'excluded')


# --- regression:3: declared:11's cell cut against a denial in the family's text -------------------------------------

R3_A = HEADER + 'Procedure: Colonoscopy\nFindings:\nExtent: cecum | Prep quality: Good\nCecum not reached.\n'
R3_B = (HEADER + 'Procedure: Colonoscopy\nExtent: cecum | Prep quality: Good\nFindings: The colonoscope was advanced to the '
        'hepatic flexure.\nCecum not reached.\n')
R3_CELLS = ('Extent: cecum | Prep quality: Good', 'Extent: Cecum | Prep quality: Good | Withdrawal time: 9 min',
            'Extent reached: cecum | BBPS: 8', 'Extent: cecum\tWithdrawal time: 8 min', 'Extent: cecum    Prep: good',
            'Extent: Cecum | Bowel preparation: adequate', 'Extent: cecum | Sedation: MAC')
R3_DENIALS = ('Cecum not reached.', 'The cecum could not be reached.', 'The colonoscope failed to reach the cecum.',
              'Unable to reach the cecum because of a tortuous colon.', 'Cecal intubation was not achieved.',
              'The appendiceal orifice was not visualized.')


def r3_note(cell, prose, line, inside=False):
    if inside:
        return (HEADER + 'Procedure: Colonoscopy\nFindings:\n' + cell + '\n' + (prose + '\n' if prose else '') + line
                + '\n')
    return HEADER + 'Procedure: Colonoscopy\n' + cell + '\nFindings: ' + (prose + '\n' if prose else '') + line + '\n'


class S2Regression3CellCutDenialTests(unittest.TestCase):
    """regression:3 (critical, a regression from 9a9f40301) - round 4c declared:11 reads an extent label whose value
    ends at a next report-field cell ("Extent: cecum | Prep quality: Good"), as R4B-BASE did; but beside "Cecum not
    reached." in the family's own text that label still read the cecum reached, a READY 45378 with no extent question
    and no incomplete check, where 9a9f40301 asked for the extent or read the procedure incomplete at the prose landmark.
    A label read only because of the cell cut is now judged against the family's text: a denial of a landmark deeper
    than the deepest one otherwise reached and no deeper than the label's own contradicts it (plan:D2's guard). A reach
    denial of plan:D2's closed list naming that landmark ("Cecum not reached.", "failed to reach the cecum"), or a reading
    of the landmark that denies it outright ("No cecal intubation."), drops the label and 9a9f40301's reading returns. A
    doubt of the label's own landmark that is no such denial ("Cecum: not seen.", "The cecum was not well seen due to
    stool.") withholds the extent, as whether it denies the reach cannot be read. A doubt about a shallower landmark ("The
    sigmoid colon could not be examined.", where 9a9f40301 read a false 'incomplete: rectum') and a denial beyond the
    label's landmark ("TI not intubated.") leave HEAD's reading."""

    def test_the_claimed_inputs_restore_r5(self):
        self.assertIsNone(fact_value(R3_A, 'gi.colonoscopy', 'extent'))
        proposal = run_engine(R3_A, [('45378', 'Procedure: Colonoscopy')])['45378']
        self.assertTrue(held(proposal), (proposal.bucket, proposal.status))
        self.assertIn('extent', clarified(proposal))
        self.assertEqual(fact_value(R3_B, 'gi.colonoscopy', 'extent'), 'incomplete: hepatic flexure')
        self.assertEqual(family(R3_B, 'gi.colonoscopy'), 'incomplete')
        proposal = run_engine(R3_B, [('45378', 'Procedure: Colonoscopy')])['45378']
        self.assertEqual(checks(proposal).get('service.incomplete'), 'warn')

    def test_every_listed_cell_and_denial_never_reads_the_cecum(self):
        for cell in R3_CELLS:
            for line in R3_DENIALS:
                for prose in ('', 'The colonoscope was advanced to the hepatic flexure.'):
                    for inside in (False, True):
                        text = r3_note(cell, prose, line, inside)
                        with self.subTest(cell=cell, line=line, prose=prose, inside=inside):
                            self.assertNotEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
                            self.assertNotEqual(family(text, 'gi.colonoscopy'), None)

    def test_an_outright_denial_in_other_words(self):
        """A landmark whose own reading is negated or incomplete is denied outright, in words plan:D2's list need not read."""
        for line in ('No cecal intubation.', 'Cecal intubation: not done.', 'Despite multiple attempts the cecum was not '
                     'reached.', 'Incomplete colonoscopy; the cecum was not reached.'):
            for prose, extent in (('', None), ('The colonoscope was inserted into the rectum and advanced.',
                                               'incomplete: rectum')):
                text = HEADER + 'Procedure: Colonoscopy\nExtent: cecum | Prep quality: Good\nFindings: ' + prose + ' ' + line + '\n'
                with self.subTest(line=line, prose=prose):
                    self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), extent)  # 9a9f40301's reading

    def test_a_doubt_at_the_labels_own_depth_withholds_the_extent(self):
        """Whether it denies the reach or tells how the cecum was seen cannot be read: the extent is asked, never the
        cecum (HEAD) and never 'incomplete: rectum' (9a9f40301, which never read the label)."""
        for line in ('Cecum: not seen.', 'The cecum was not well seen due to stool.', 'The cecal base was not well '
                     'visualized because of retained stool.', 'The cecum could not be evaluated.',
                     'Appendiceal orifice: not identified.'):
            for prose in ('', 'The colonoscope was inserted into the rectum and advanced.'):
                text = HEADER + 'Procedure: Colonoscopy\nExtent: cecum | Prep quality: Good\nFindings: ' + prose + ' ' + line + '\n'
                with self.subTest(line=line, prose=prose):
                    self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'extent'))
                    proposal = run_engine(text, [('45378', 'Procedure: Colonoscopy')])['45378']
                    self.assertTrue(held(proposal), (proposal.bucket, proposal.status))
                    self.assertIn('extent', clarified(proposal))

    def test_an_outright_denial_decides_beside_a_doubt(self):
        for lines in ('The cecum was not well seen. Cecum not reached.', 'Cecum not reached. The cecum was not well seen.'):
            text = (HEADER + 'Procedure: Colonoscopy\nExtent: cecum | Prep quality: Good\nFindings: The colonoscope was '
                    'inserted into the rectum and advanced. ' + lines + '\n')
            with self.subTest(lines=lines):
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'incomplete: rectum')  # 9a9f40301's reading

    def test_a_doubt_about_a_shallower_landmark_keeps_the_label(self):
        """The scope passed it: 9a9f40301 read a false 'incomplete: rectum' here, HEAD the cecum."""
        for line in ('The ascending colon was not well seen.', 'The sigmoid colon could not be examined.',
                     'The sigmoid colon was not well visualized.'):
            for prose in ('', 'The colonoscope was inserted into the rectum and advanced.'):
                text = HEADER + 'Procedure: Colonoscopy\nExtent: cecum | Prep quality: Good\nFindings: ' + prose + ' ' + line + '\n'
                with self.subTest(line=line, prose=prose):
                    self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')

    def test_a_denial_after_the_cell_on_the_labels_line(self):
        """The label's own sentence ends at the cell (plan:D reads no further), so a denial after it is the family's."""
        for rest in (', cecum not reached.', '; the cecum could not be reached.', ' - cecum not reached'):
            text = HEADER + 'Procedure: Colonoscopy\nFindings:\nExtent: cecum | Prep quality: Good' + rest + '\n'
            with self.subTest(rest=rest):
                self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'extent'))

    def test_the_upper_tract(self):
        for cell in ('Extent: D2 | Sedation: MAC', 'Extent: second part of the duodenum | Withdrawal time: 5 min'):
            for line in ('D2 could not be reached.', 'The duodenum could not be reached.', 'Unable to reach the duodenum.',
                         'The second part of the duodenum was not reached.'):
                for prose, extent in (('', None), ('The gastroscope was passed into the esophagus.', 'incomplete: esophagus')):
                    text = HEADER + 'Procedure: EGD\n' + cell + '\nFindings: ' + (prose + '\n' if prose else '') + line + '\n'
                    with self.subTest(cell=cell, line=line, prose=prose):
                        self.assertEqual(fact_value(text, 'gi.egd', 'extent'), extent)  # 9a9f40301's reading
        text = HEADER + 'Procedure: EGD\nExtent: duodenum | Findings: see below\nFindings: D2 could not be reached.\n'
        self.assertEqual(fact_value(text, 'gi.egd', 'extent'), 'incomplete: duodenum')  # a deeper denial: HEAD's reading

    def test_the_flexible_sigmoidoscopy(self):
        for cell in ('Extent: descending colon | Prep quality: fair', 'Extent: descending colon    Prep: fair'):
            for prose, extent in (('', None), ('The sigmoidoscope was advanced to the sigmoid colon.', 'sigmoid colon')):
                text = (HEADER + 'Procedure: Flexible sigmoidoscopy\n' + cell + '\nFindings: ' + (prose + '\n' if prose else '')
                        + 'The descending colon was not reached.\n')
                with self.subTest(cell=cell, prose=prose):
                    self.assertEqual(fact_value(text, 'gi.flex_sig', 'extent'), extent)  # 9a9f40301's reading
            text = (HEADER + 'Procedure: Flexible sigmoidoscopy\n' + cell + '\nFindings: The splenic flexure could not be '
                    'reached.\n')
            with self.subTest(cell=cell, deeper=True):
                self.assertEqual(fact_value(text, 'gi.flex_sig', 'extent'), 'descending colon')

    def test_declared_11_still_reads_the_cell_cut_label(self):
        """No denial, a denial beyond the label, a denied finding, or a denial shallower than a deeper prose landmark:
        the label reads the cecum, as declared:11 (R4B-BASE) reads it."""
        for cell in R3_CELLS:
            for line in ('', 'Normal mucosa throughout.', 'No polyps were seen in the cecum.', 'TI not intubated.',
                         'The terminal ileum could not be intubated.', 'Unable to intubate the ileocecal valve.'):
                text = r3_note(cell, 'The colonoscope was inserted into the rectum and advanced to the hepatic flexure.',
                               line)
                with self.subTest(cell=cell, line=line):
                    self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')
            text = r3_note(cell, 'The colonoscope was advanced to the transverse colon.',
                           'The sigmoid colon could not be examined.')
            with self.subTest(cell=cell, shallower=True):
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')

    def test_an_addendum_answer_read_by_the_cut(self):
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: Cecum not reached.\n\nADDENDUM (revision 2, added 2026-10-22 '
                '10:00 UTC)\nFurthest extent reached: cecum | Prep quality: Good\n')
        self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'extent'))  # 9a9f40301's reading
        text = text.replace('Findings: Cecum not reached.', 'Findings: Normal mucosa.')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')

    def test_a_landmark_reached_by_another_cue_is_not_guarded(self):
        text = HEADER + 'Procedure: Colonoscopy to cecum | Prep quality: Good\nFindings: Cecum not reached.\n'
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')  # HEAD's and 9a9f40301's reading

    def test_a_denial_above_a_landmark_reached_otherwise_decides_nothing(self):
        """plan:D2's guard: the scope passed it, so it says nothing of the label."""
        for line in ('The sigmoid colon could not be reached.', 'Unable to reach the transverse colon.'):
            text = (HEADER + 'Procedure: Colonoscopy\nExtent: cecum | Prep quality: Good\nFindings: The colonoscope was '
                    'advanced to the hepatic flexure. ' + line + '\n')
            with self.subTest(line=line):
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')

    def test_a_reach_denial_in_another_segment_names_another_thing(self):
        """The cecum's own doubt withholds the extent; a reach denial in another segment of its clause is not the cecum's,
        so it never drops the label to the shallower landmark ('incomplete: rectum')."""
        for rest in (', the guidewire was not advanced.', ' (scope not advanced).', ' - the scope was not advanced.'):
            text = (HEADER + 'Procedure: Colonoscopy\nExtent: cecum | Prep quality: Good\nFindings: The colonoscope was '
                    'inserted into the rectum and advanced. The cecum was not well seen' + rest + '\n')
            with self.subTest(rest=rest):
                self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'extent'))

    def test_a_label_read_whole_is_unchanged(self):
        """Only a label read because of the cell cut is guarded; a plain label keeps every base's reading (the listed
        residual 'round 4c-2 plan:D (rest)')."""
        text = HEADER + 'Procedure: Colonoscopy\nExtent: cecum\nFindings: Cecum not reached.\n'
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')


# --- sections:1: plan:D2's onward words and a same-depth direction after an extent label ----------------------------

S1_POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'


def s1_note(extent, technique='The colonoscope was inserted into the rectum and advanced without difficulty.'):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\nIndication: Surveillance.\nTechnique: ' + technique
            + '\n' + extent + '\nFindings: ' + S1_POLYP + '\nImpression: Sigmoid polyp.\n')


class S2Sections1ReachOnwardTests(unittest.TestCase):
    """sections:1 (high, a regression from all three bases) - plan:D2 read "not advanced further", "could not be
    advanced further" or "not advanced beyond the cecum" after an extent label as a denial of reaching the label's own
    landmark, so a complete colonoscopy or EGD read INCOMPLETE at the insertion landmark ("incomplete: rectum") with a
    service.incomplete warning and a 52/53 consideration. Those words deny going past the landmark, never reaching it:
    an onward word ("further", "farther", "any further") after the denial is no reach denial, and "beyond" or "past" is
    one only before a landmark shallower than the label's own. The label stays refused by plan:D (a negation it cannot
    explain), so it goes to plan:D2's doubted list: the extent is withheld and the family's extent question asks for it,
    never 'incomplete: <insertion landmark>'."""

    ONWARD = ('not advanced further due to looping', 'not advanced any further', 'scope not advanced farther',
              'unable to advance further', 'could not be advanced further', 'scope could not be advanced any further',
              'not advanced further')
    CECUM_BEYOND = ('not advanced beyond the cecum', 'not advanced beyond the ileocecal valve', 'not advanced past the cecum',
                    'not advanced beyond the appendiceal orifice')

    def assert_never_incomplete_at_the_prose(self, text, slug, code, phrase, prose_landmark):
        extent = fact_value(text, slug, 'extent')
        self.assertNotEqual(extent, f'incomplete: {prose_landmark}')
        proposal = run_engine(text, [(code, phrase)])[code]
        self.assertNotEqual(proposal.bucket, 'excluded')
        if family(text, slug) != 'incomplete':
            self.assertNotEqual(checks(proposal).get('service.incomplete'), 'warn', (extent, checks(proposal)))

    def test_the_claimed_input(self):
        text = s1_note('Extent: cecum; not advanced further due to looping')
        self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
        self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'extent'))
        proposal = run_engine(text, [('45385', S1_POLYP)])['45385']
        self.assertNotIn('service.incomplete', [c.id for c in proposal.checks if c.status == 'warn'])
        self.assertIn('extent', clarified(proposal))

    def test_every_rest_and_label(self):
        for label in ('Extent: cecum', 'Extent reached: cecum', 'Furthest extent reached: cecum', 'Extent of exam: cecum',
                      'Extent: appendiceal orifice', 'Extent: terminal ileum', 'Extent reached: TI'):
            beyond = (('not advanced beyond the terminal ileum',) if 'cecum' not in label and 'appendiceal' not in label
                      else self.CECUM_BEYOND)
            for rest in self.ONWARD + beyond:
                text = s1_note(label + '; ' + rest)
                with self.subTest(label=label, rest=rest):
                    self.assert_never_incomplete_at_the_prose(text, 'gi.colonoscopy', '45385', S1_POLYP, 'rectum')

    def test_the_upper_tract(self):
        for rest in ('not advanced further', 'could not be advanced further', 'not advanced beyond D2'):
            text = (HEADER + 'Procedure: EGD with biopsy\nTechnique: The gastroscope was passed into the esophagus and '
                    'advanced without difficulty.\nExtent: D2; ' + rest + '\nFindings: Gastritis in the antrum; biopsies '
                    'were taken.\n')
            with self.subTest(rest=rest):
                self.assert_never_incomplete_at_the_prose(text, 'gi.egd', '43239', 'biopsies were taken.', 'esophagus')

    def test_a_reach_denial_still_denies(self):
        """plan:D's and plan:D2's own reach denials stand: the shallower prose landmark decides."""
        for rest in ('not reached', 'not reached at all', 'not reached despite abdominal pressure',
                     'could not be advanced to the cecum', 'not advanced beyond the transverse colon',
                     'unable to advance past the hepatic flexure', 'could not be advanced beyond the transverse colon',
                     'not advanced further than the sigmoid colon', 'scope could not be advanced farther than the rectum',
                     'could not be advanced any further than the sigmoid colon',
                     'not visualized', 'unable to intubate'):
            text = s1_note('Extent: cecum; ' + rest)
            with self.subTest(rest=rest):
                extent = fact_value(text, 'gi.colonoscopy', 'extent')  # the shallower landmark decides, never the label
                self.assertTrue(extent and extent.startswith('incomplete: '), extent)

    def test_a_label_shallower_than_the_beyond_landmark_reads_as_before(self):
        # round 4d, second round (the verifier's new problem 5): "beyond the cecum" after a terminal-ileum label says the
        # cecum was reached - the label is doubted and its extent withheld, never 'incomplete: rectum' (this pin read
        # it so); a "beyond" short of the cecum still denies the label
        text = s1_note('Extent: terminal ileum; not advanced beyond the cecum')
        self.assertIsNone(fact_value(text, 'gi.colonoscopy', 'extent'))
        text = s1_note('Extent: terminal ileum; not advanced beyond the transverse colon')
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'incomplete: rectum')
        text = s1_note('Extent: cecum')  # a plain label reads as every base reads it
        self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')


# --- sections:3: the cross-line answer hold and a negation the line's own words explain -----------------------------

S3_QUESTION = 'Has the patient had a prior adverse reaction to sedation or anesthesia? No'


def s3_note(question, line):
    return (HEADER + 'Procedure: EGD with biopsy.\nIndication: Dyspepsia.\nPre-procedure assessment:\n' + question + '\n'
            + line + '\nThe gastroscope was advanced to the second part of the duodenum.\n')


class S2Sections3AnswerAboveExplainedNegationTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:3 (high, a declared misread every base shares) - round 4c's cross-line hold (a negation that reaches a
    service only across a line break after a line ending in an answer of its own holds instead of negating) was skipped
    whenever the service's own line carried any negation word, so "Biopsies were taken from the gastric antrum without
    difficulty." under "... anesthesia? No" was NEGATED by the question's "No" and 43239 excluded. The hold is now skipped
    only for a negation word on the service's line that nothing explains; a complication ("without difficulty", "with no
    bleeding", "without complication"), a qualifier or a denied finding denies nothing of the service."""

    LINES = ('Biopsies were taken from the gastric antrum without difficulty.',
             'Biopsies were taken from the gastric antrum with no bleeding.',
             'Biopsies were taken from the gastric antrum; there were no complications.',
             'Biopsies were taken from the gastric antrum without complication.',
             'biopsies were taken from the gastric antrum without difficulty.',
             'Biopsies were taken from the gastric antrum with cold forceps without difficulty.',
             'Biopsies were taken from the gastric antrum with no immediate bleeding.')

    def test_the_claimed_and_listed_lines(self):
        for question in (S3_QUESTION, 'History of an adverse reaction to sedation or to anesthesia in the past - no',
                         "Was there any evidence of Barrett's esophagus at the GE junction? No"):
            for line in self.LINES:
                text = s3_note(question, line)
                with self.subTest(question=question[:30], line=line):
                    self.assert_held_never_excluded(text, '43239', line)

    def test_a_spoken_answer_and_a_field_answered_no(self):
        polyp = 'A 6 mm sigmoid polyp was removed with a cold snare without complication.'
        text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nTechnique: The colonoscope was advanced to '
                'the cecum.\nWhen asked about a biopsy of the hemorrhoid, the patient said, no\n' + polyp + '\nImpression: '
                'Sigmoid polyp.\n')
        self.assert_held_never_excluded(text, '45385', polyp)
        line = 'a 6 mm sigmoid polyp was removed with a cold snare without complication.'
        text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy and tattoo.\nFindings: The colonoscope was '
                'advanced to the cecum.\nTattoo placed today: no\n' + line + '\n')
        self.assert_held_never_excluded(text, '45385', line)

    def test_a_line_that_alone_only_doubts_or_reads_incomplete_holds_too(self):
        """The verifier's weaker sub-variant: the line's own word doubts or reads incomplete, never negates; only the
        question's "No" negated it."""
        for line in ('Biopsies were taken from the gastric antrum, which was not ulcerated.',
                     'Biopsies were taken; the mucosa was not friable.', 'Biopsy was attempted but could not be completed.',
                     'Biopsy was taken; the patient did not tolerate further sampling.',
                     'Biopsies were taken; no polyps were seen.', 'Biopsies were taken; no sedation was given.'):
            text = s3_note(S3_QUESTION, line)
            with self.subTest(line=line):
                self.assert_held_never_excluded(text, '43239', line)

    def test_the_lines_own_denial_still_negates(self):
        for line in ('No biopsies were taken from the gastric antrum.', 'Biopsies were not taken from the gastric antrum.',
                     'no biopsies were taken, without difficulty.', 'Biopsy not done.', 'Biopsy was declined.',
                     'Biopsies: none.', 'Biopsies were not needed.', 'Biopsy of the antrum was not performed.',
                     'No tissue was obtained.', 'The stricture was not dilated.', 'No sample was taken from the antrum.'):
            text = s3_note(S3_QUESTION, line)
            with self.subTest(line=line):
                self.assertEqual(read(text, line)[0], 'negated')
        text = (HEADER + 'Procedure: EGD with biopsy.\nIndication: Dysphagia.\nFindings:\nSchatzki ring present - no\nno '
                'biopsies were taken.\n')
        self.assertEqual(read(text, 'no biopsies were taken.')[0], 'negated')

    def test_the_controls_read_as_before(self):
        line = 'Biopsies were taken from the gastric antrum without difficulty.'
        self.assertEqual(read(s3_note(S3_QUESTION.replace('? No', '? Yes'), line), line)[0], 'performed')
        text = (HEADER + 'Procedure: EUS.\nFindings: Comment: because of time constraints, no\nEUS of the pancreatic cyst was '
                'performed today without difficulty.\n')
        self.assertEqual(read(text, 'EUS of the pancreatic cyst was performed today without difficulty.')[0], 'negated')


# --- sections:5: a Word numbered or bulleted findings list -----------------------------------------------------------

S5_ITEM = '6 mm sigmoid polyp removed with cold snare'


def s5_word(item, style, findings=('Findings:', None)):
    return word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                          ('Procedure: Colonoscopy with cold snare polypectomy.', None), findings,
                          ('The colonoscope was advanced to the cecum.', style), (item, style), (S5_ITEM, style),
                          ('Impression: Sigmoid polyp.', None)])


class S2Sections5WordListHistoryItemTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:5 (high, a declared misread every base shares) - round 4c sections:4 holds a numbered or bulleted
    findings item that names prior therapy ("2. Prior radiation therapy"), but DOCX extraction writes no list marker for
    a Word list, so the same item in a "List Number" or "List Bullet" list opened a HISTORY section and the next item's
    polypectomy (45385) was excluded. Inside a procedure, findings or technique section such a colon-less line now opens
    the held 'other' section whatever its marker; outside those sections an unmarked line reads as before. Accepted
    over-hold, stated in the changed earlier tests: an unmarked history label inside a findings section ("Previous
    endoscopic studies", "History of prior procedures") is held too, where it was historical."""

    ITEMS = ('Prior radiation therapy', 'Previous endoscopic therapy', 'Prior treatment', 'Past endoscopic treatment',
             'History of radiation therapy', 'Status post prior radiation therapy')

    def test_a_word_numbered_or_bulleted_list(self):
        for style in ('List Number', 'List Bullet'):
            for item in self.ITEMS:
                for findings in (('Findings:', None), ('Findings', 'Heading 2')):
                    text = s5_word(item, style, findings)
                    with self.subTest(style=style, item=item, findings=findings[0]):
                        self.assertNotIn(read(text, S5_ITEM)[0], NOT_TODAY)
                        self.assert_held_never_excluded(text, '45385', S5_ITEM)

    def test_the_plain_line_inside_findings_technique_or_procedure(self):
        for heading in ('Findings:', 'Technique: The colonoscope was inserted.', 'Procedure: Colonoscopy.'):
            for item in self.ITEMS:
                text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\n' + heading + '\nThe colonoscope was '
                        'advanced to the cecum.\n' + item + '\n' + S5_ITEM + '\nImpression: Sigmoid polyp.\n')
                with self.subTest(heading=heading, item=item):
                    self.assert_held_never_excluded(text, '45385', S5_ITEM)

    def test_a_cued_sentence_under_a_word_bullet(self):
        polyp = 'A 6 mm sigmoid polyp was removed with a cold snare.'
        text = word_document([('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT', None), ('Date of service: 2026-10-21', None),
                              ('Procedure: Colonoscopy with cold snare polypectomy.', None), ('Findings:', None),
                              ('Radiation proctitis with scattered telangiectasias in the rectum.', 'List Bullet'),
                              ('Status post prior radiation therapy', 'List Bullet'), (polyp, 'List Bullet'),
                              ('Impression: Sigmoid polyp.', None)])
        self.assert_held_never_excluded(text, '45385', polyp)

    def test_other_items_and_sections_are_unchanged(self):
        for style in ('List Number', 'List Bullet', None):
            text = s5_word('Small internal hemorrhoids', style)
            with self.subTest(style=style):
                self.assertEqual(kind_at(text, S5_ITEM), 'findings')
                self.assertTrue(ready(run_engine(text, [('45385', S5_ITEM)])['45385']))
        for heading, kind in (('Indication: Surveillance.', 'history'), ('Past history:', 'history'), ('Plan:', 'history')):
            text = (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy.\nFindings: The colonoscope was advanced to '
                    'the cecum.\n' + heading + '\nPrior radiation therapy\nColonoscopy in 2019 with two adenomas removed.\n')
            with self.subTest(heading=heading):
                self.assertEqual(kind_at(text, 'Colonoscopy in 2019'), kind)
        text = HEADER + 'Prior radiation therapy\nColonoscopy in 2019 with two adenomas removed.\nProcedure: Colonoscopy\n'
        self.assertEqual(kind_at(text, 'Colonoscopy in 2019'), 'history')  # before the first heading, as before


# --- declared:6 and declared:7: denying labels led by a marker and a box, or with longer wording ---------------------

D_FIND = ('Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. A 6 mm sigmoid polyp was seen.\n')
D_POLYP = 'Cold snare polypectomy of the 6 mm sigmoid polyp.'


def d_note(label, item=D_POLYP):
    return HEADER + D_FIND + label + '\n' + item + '\n'


class S2Declared6MarkerAndBoxLedDenyingLabelTests(HeldOrReadyAssertions, unittest.TestCase):
    """declared:6 (high, a declared misread every base shares) - a denying label led by a list marker AND a box ("- [ ]
    Procedures not performed:", "1. [x] Procedures not performed:", "• ☐ ...") was not read: the label reader took a
    marker then words, or a box then a marker, never a marker then a box, so the line under it read performed and 45385
    was READY. ARCHITECTURE 5.3 reads such a label after any list marker the other readers strip, or led by one box of
    any state; the box may now follow the marker."""

    LEADS = ('- [ ] ', '* [ ] ', '• ☐ ', '1. [x] ', '- ☐ ', '- [x] ', '- [?] ', '1) [ ] ', '(1) ☐ ',
             '- ☒ ', '• [ ] ', '2. ☐ ', '- ( ) ')
    LABELS = ('Procedures not performed:', 'Not done:', 'Cancelled procedures:', 'Procedure(s) not performed:',
              'Procedures not performed today:')

    def test_every_marker_and_box_lead(self):
        for lead in self.LEADS:
            for label in self.LABELS:
                text = d_note(lead + label)
                with self.subTest(lead=lead, label=label):
                    self.assert_held_never_excluded(text, '45385', D_POLYP)

    def test_the_leads_alone_still_hold_and_other_labels_do_not(self):
        for lead in ('', '- ', '* ', '1. ', '☐ ', '[ ] ', '[x] ', '☐ 1. '):
            text = d_note(lead + 'Procedures not performed:')
            with self.subTest(lead=lead):
                self.assert_held_never_excluded(text, '45385', D_POLYP)
        for label in ('- [ ] Additional procedures:', '1. [x] Procedures performed:', '- [x] Interventions:'):
            text = d_note(label)
            with self.subTest(label=label):
                self.assertTrue(ready(run_engine(text, [('45385', D_POLYP)])['45385']))

    def test_an_unchecked_item_under_the_label_stays_negated(self):
        text = d_note('- [ ] Procedures not performed:', '[ ] ' + D_POLYP)
        self.assertNotIn(read(text, D_POLYP)[0], POSITIVE)


class S2Declared7LongerDenyingLabelTests(HeldOrReadyAssertions, unittest.TestCase):
    """declared:7 (high, a declared misread every base shares) - a denying label with more than three words before its
    denial word or five after it ("The following procedures were not performed:", "Procedures not performed today due to
    patient refusal of sedation:") was not read, an undeclared bound, so the line under it read performed and 45385 was
    READY while "The following were not performed:" held it. The label is bounded by its length (80 characters, at
    every reader), not by word counts."""

    LABELS = ('The following procedures were not performed:', 'The following procedures were not done:',
              'The following procedures were cancelled:', 'The following procedures were deferred:',
              'The following interventions were not performed today:',
              'Procedures not performed today due to patient refusal of sedation:',
              'Therapeutic interventions planned but not performed:',
              'Additional procedures that were not performed at this visit:')

    def test_every_longer_label(self):
        for label in self.LABELS:
            for lead in ('', '- ', '1. ', '[ ] '):
                text = d_note(lead + label)
                with self.subTest(label=label, lead=lead):
                    self.assert_held_never_excluded(text, '45385', D_POLYP)

    def test_an_egd_report(self):
        line = 'EGD with balloon dilation.'
        text = (HEADER + 'Procedure: EGD\nFindings: The gastroscope was advanced to the second part of the duodenum.\nThe '
                'following procedures were not performed:\n' + line + '\n')
        self.assert_never_ready(text, '43249', line)
        self.assertNotIn(read(text, line)[0], NOT_TODAY)

    def test_a_longer_label_without_a_denial_reads_as_before(self):
        for label in ('The following procedures were performed today without any complication at all:',
                      'Procedures performed today in the endoscopy suite after informed consent:',
                      'The following additional procedures were performed today:'):
            text = d_note(label)
            with self.subTest(label=label):
                self.assertTrue(ready(run_engine(text, [('45385', D_POLYP)])['45385']))


# --- bounded:3: one clause copy per landmark hit ----------------------------------------------------------------------

MIB = 1024 * 1024
B3_HEADER = HEADER + 'Procedure: Colonoscopy\nFindings: '


def b3_line(unit, chars):
    return B3_HEADER + unit * ((chars - len(B3_HEADER)) // len(unit))


class S2Bounded3LandmarkClauseCopiesTests(unittest.TestCase):
    """bounded:3 (high, a cost regression from 9a9f40301) - _landmarks kept its own copy of the whole clause for every
    landmark hit, and round 4c-2's unread, denied and doubted lists retained them, so a one-line note of a repeated denial
    ("\u2610 Completed - aborted at the splenic flexure ", 115,000 characters) exhausted the analyze child's 512 MiB
    allowance where 9a9f40301 routed it in 58 MiB. One Span per clause is now shared by every hit of the clause, so memory
    stays linear in the text; the readings are unchanged."""

    SHAPES = (('\u2610 Completed - aborted at the splenic flexure ', 150000), ('Extent: Cecum (attempted) ', 130000),
              ('\u2612 Rescheduled \u2610 Completed - aborted at the splenic flexure ', 150000),
              ('The scope was advanced to the splenic flexure ', 170000))

    def test_the_claimed_lines_route_inside_the_analyze_allowance(self):
        from datetime import date

        from studio import bounded
        from studio.gi import detect
        for unit, chars in self.SHAPES:
            text = b3_line(unit, chars)
            with self.subTest(unit=unit, chars=len(text)):
                routed_child = bounded.run_bounded(detect.route, text, date(2026, 10, 21), seconds=60,
                                                   memory_bytes=512 * MIB)
                self.assertTrue(routed_child.findings)

    def test_each_hit_keeps_its_own_clause_as_evidence(self):
        text = (HEADER + 'Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the hepatic flexure. The cecum '
                'could not be reached; the transverse colon was tortuous.\n')
        finding = routed(text).finding('gi.colonoscopy')
        extent = next(f for f in finding.facts if f.name == 'extent')
        self.assertEqual(extent.value, 'incomplete: hepatic flexure')
        self.assertEqual([e.text for e in extent.evidence],
                         ['The colonoscope was advanced to the hepatic flexure.', 'The cecum could not be reached;'])

    def test_the_hits_of_one_clause_share_one_span(self):
        from studio.gi import cues, detect
        text = b3_line('\u2610 Completed - aborted at the splenic flexure ', 5000)
        an, _ = detect._analysis(text)
        denied = []
        detect._landmarks(an, an.lay.sentences, cues.LOWER_LANDMARKS, None, denied, None)
        self.assertGreater(len(denied), 50)
        self.assertEqual(len({id(hit[2]) for hit in denied}), len({(hit[2].start, hit[2].end) for hit in denied}))


# --- bounded:6: plan:D's reading of each extent label, once per label ------------------------------------------------

class S2Bounded6LabelRestOnceTests(unittest.TestCase):
    """bounded:6 (medium, a cost regression from 9a9f40301) - on a one-line run of extent labels with a hedge tail
    ("Extent: cecum; prep fair? ", 50,000 characters) route() took 3.6x 9a9f40301's time: _landmarks asked plan:D's
    _P2_label_denied twice per label and _P2_label_rest four times (and plan:D2 again), each reading up to CLAUSE_REACH
    characters. They are now memoised per label (an.memo, keyed by the label's end, depth and table); the readings are
    unchanged (routing JSON identical over the attack corpus), and the time is about 2.3x 9a9f40301's."""

    def test_each_labels_rest_and_verdict_are_read_once(self):
        from datetime import date
        from unittest import mock

        from studio.gi import detect
        text = HEADER + 'Procedure: Colonoscopy\nFindings: ' + 'Extent: cecum; prep fair? ' * 40 + '\n'
        detect._analysis.cache_clear()
        with mock.patch.object(detect, '_S2_label_denied_read', wraps=detect._S2_label_denied_read) as denied:
            detect.route(text, date(2026, 10, 21))
        self.assertGreater(denied.call_count, 0)
        self.assertLessEqual(denied.call_count, 40)  # once per label, never twice
        an, _ = detect._analysis(text, date(2026, 10, 21))
        self.assertTrue(40 >= len([k for k in an.memo if k[0] == 'p2-label-rest']) > 0)
        self.assertTrue(40 >= len([k for k in an.memo if k[0] == 'p2-reach-denied']) > 0)
        detect._analysis.cache_clear()


# === Round 4d, second round: the independent verifier's new problems in this branch ====================================

def extent_status(text, slug):
    finding = routed(text).finding(slug)
    extent = next((f.value for f in (finding.facts if finding else ()) if f.name == 'extent'), None)
    return (finding.status if finding else None), extent


# --- regression:3 (second round): what a denial beside a cell-cut extent label is about ------------------------------

R3R2_RECTUM = 'Technique: The colonoscope was inserted into the rectum and advanced.'
R3R2_SIGMOID = 'Technique: The colonoscope was advanced to the sigmoid colon and beyond.'
R3R2_CELLS = ('Extent: cecum | Prep quality: Good', 'Extent: Cecum | Bowel preparation: adequate',
              'Extent reached: cecum | Withdrawal time: 9 min', 'Extent: cecum  Sedation: MAC')
# an act done (or not) at the label's landmark, or a lesion there: the verifier's eighteen sentences and round 4d's own
R3R2_ACTS = ('The cecum was not biopsied.', 'No biopsies of the cecum were obtained.', 'Cecal biopsies were not taken.',
             'Biopsies of the cecum were not obtained.', 'The cecum was not tattooed.',
             'Photodocumentation of the cecum was not obtained.', 'Photographs of the cecum were not taken.',
             'No photos of the cecum were taken.', 'The appendiceal orifice was not biopsied.',
             'The ileocecal valve was not biopsied.', 'No polypectomy was performed in the cecum.',
             'The cecal polyp was not resected.', 'The cecal lipoma was not removed.',
             'Random biopsies were not taken from the cecum.', 'The cecum was not photographed.', 'Cecum not biopsied.',
             'No cecal biopsies.', 'The cecum was not clipped.', 'Biopsy of the cecum was cancelled.',
             'Tattooing of the cecum was deferred.', 'Biopsies of the cecum were declined by the family.',
             'The cecum was not clipped after polypectomy.', 'Retroflexion in the cecum could not be completed.',
             'Cecal intubation was not photographed.', 'Cecal intubation was not photodocumented.',
             'A 6 mm polyp in the ascending colon was removed; the cecum was not biopsied.',
             'The colonoscope was advanced to the cecum, which was not biopsied.',
             'The colonoscope was advanced without difficulty; the cecum was not biopsied.',
             # a reach word in another segment of the clause, and a denial outside the landmark's own segment
             'The colonoscope was advanced without difficulty, the cecum was not biopsied.',
             'The scope was advanced toward the cecum (not biopsied).', 'Advanced to the cecum - not biopsied.',
             'The colonoscope was advanced to the cecum (photos not taken).',
             # a photo denied beside a view word: the photo is what is denied
             'Photos of the cecum could not be obtained due to poor visualization.',
             'No photos of the cecum were taken as it was poorly seen.')
# a finding at the landmark (a negation that speaks of what was found there, never of reaching it)
R3R2_FINDINGS = ('The cecum was not inflamed.', 'The cecum was not ulcerated.', 'The appendiceal orifice was not inflamed.',
                 'The ileocecal valve was not lipomatous.',
                 'The appendiceal orifice was not seen due to a prior appendectomy.', 'The cecum was not well prepped.')


def r3r2_note(cell, line, technique=R3R2_RECTUM, before=False):
    if before:
        return (HEADER + 'Procedure: Colonoscopy\n' + technique + '\nFindings: ' + line + '\n' + cell
                + '\nImpression: Normal colonoscopy.\n')
    return (HEADER + 'Procedure: Colonoscopy\n' + technique + '\n' + cell + '\nFindings: ' + line + ' The colon was '
            'otherwise normal.\nImpression: Normal colonoscopy.\n')


class S2R2Regression3ActOrFindingAtTheLandmarkTests(unittest.TestCase):
    """regression:3, second round (high, the verifier's new problems 1 and 7) - the outright-denial arm counted any
    negated, cancelled or declined reading of the label's own landmark as a reach denial, so "The cecum was not biopsied."
    or "No photos of the cecum were taken." beside "Extent: cecum | Prep quality: Good" dropped the label and a complete
    colonoscopy read 'incomplete: rectum' (45378 ready with service.incomplete and a 52/53 consideration); and the doubt
    arm withheld the extent for "The cecum was not inflamed." or "The cecum was not photographed.". HEAD, 4347acd24 and
    d05326ef read the cecum (9a9f40301 never read a cell-cut label). A denial now contradicts the label only when it
    speaks of reaching the landmark: a closed-list reach denial, or a reading of it negated with a reach word and no act
    in its own segment, drops it; a reach word otherwise, or a view word or hedge with no act, doubts it; an act or a
    finding at the landmark changes nothing."""

    def test_an_act_at_the_labels_landmark_is_no_reach_denial(self):
        for line in R3R2_ACTS:
            for cell in R3R2_CELLS:
                for technique, before in ((R3R2_RECTUM, False), (R3R2_SIGMOID, False), (R3R2_RECTUM, True)):
                    text = r3r2_note(cell, line, technique, before)
                    with self.subTest(line=line, cell=cell, technique=technique[-30:], before=before):
                        self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('performed', 'cecum'))
            text = r3r2_note(R3R2_CELLS[0], line)
            with self.subTest(line=line, engine=True):
                proposal = run_engine(text, [('45378', 'Procedure: Colonoscopy')])['45378']
                self.assertTrue(ready(proposal), (proposal.bucket, proposal.status, clarified(proposal)))
                self.assertNotIn('service.incomplete', checks(proposal))

    def test_a_finding_at_the_labels_landmark_never_withholds(self):
        for line in R3R2_FINDINGS:
            for cell in R3R2_CELLS:
                text = r3r2_note(cell, line)
                with self.subTest(line=line, cell=cell):
                    self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('performed', 'cecum'))

    def test_the_upper_tract(self):
        for cell in ('Extent: second part of the duodenum | Sedation: MAC', 'Extent: D2 | Sedation: MAC'):
            for line in ('The second part of the duodenum was not biopsied.', 'D2 was not biopsied.',
                         'No biopsies were taken from the second part of the duodenum.',
                         'Photodocumentation of D2 was not obtained.'):
                text = (HEADER + 'Procedure: EGD\nTechnique: The gastroscope was passed into the esophagus.\n' + cell
                        + '\nFindings: ' + line + ' Gastritis in the antrum.\nImpression: Gastritis.\n')
                with self.subTest(cell=cell, line=line):
                    self.assertEqual(extent_status(text, 'gi.egd'), ('performed', 'second part of duodenum'))

    def test_a_denial_of_reaching_it_still_contradicts_the_label(self):
        """Controls: a reach denial in its own segment beside an act, or a landmark answered by a bare denial, still drops
        the label (9a9f40301's reading); a reach word beside an act, or a view word, withholds the extent."""
        for line, extent in (('Cecum not reached; no biopsies taken.', 'incomplete: rectum'),
                             ('No cecal intubation; biopsies of the rectum were taken.', 'incomplete: rectum'),
                             ('No cecal intubation, biopsies of the rectum were taken.', 'incomplete: rectum'),
                             ('The cecum was not intubated.', 'incomplete: rectum'),
                             ('We did not reach the cecum.', 'incomplete: rectum'),
                             ('Cecal intubation: no.', 'incomplete: rectum'),
                             ('Cecum: no.', 'incomplete: rectum'),
                             ('The cecum was not reached or biopsied.', None),
                             ('The lesion near the cecum could not be reached.', None),
                             ('The scope never made it to the cecum.', None),
                             ('The cecum could not be fully examined due to stool.', None)):
            text = r3r2_note(R3R2_CELLS[0], line)
            with self.subTest(line=line):
                self.assertEqual(extent_status(text, 'gi.colonoscopy')[1], extent)
                self.assertNotEqual(extent_status(text, 'gi.colonoscopy')[1], 'cecum')

    def test_a_landmark_answered_as_a_field(self):
        """A landmark written as a field's label is answered across the separator after it (the field's own, never a
        segment break): a denial or a bare answer there drops the label (9a9f40301's reading), a view word withholds,
        and an act or a finding answered there changes nothing. A status answer naming no act ("not done", "declined",
        "cancelled") denies the landmark itself; a bare "none" or "N/A" only doubts it, unless the landmark's own name is
        the reach ("Cecal intubation: none.")."""
        for line, extent in (('Cecum - not reached.', 'incomplete: rectum'), ('Cecum | not reached.', 'incomplete: rectum'),
                             ('Cecum (not reached).', 'incomplete: rectum'), ('The cecum - not reached.', 'incomplete: rectum'),
                             ('Cecum – not reached.', 'incomplete: rectum'), ('Cecum, not reached.', 'incomplete: rectum'),
                             ('Cecum - not intubated due to looping.', 'incomplete: rectum'),
                             ('Cecal intubation: none.', 'incomplete: rectum'), ('Cecum: not done.', 'incomplete: rectum'),
                             ('Cecum: declined.', 'incomplete: rectum'), ('Cecum: cancelled.', 'incomplete: rectum'),
                             ('Cecum: not performed due to poor prep.', 'incomplete: rectum'),
                             ('Cecum - not seen.', None), ('Appendiceal orifice - not identified.', None),
                             ('Cecum: never.', None),
                             # a bare "none" or "N/A" answers a findings-by-segment line as often as a reach: a doubt
                             ('Cecum - none.', None), ('Cecum: none.', None), ('Cecum: N/A.', None),
                             ('Rectum: normal. Sigmoid: diverticulosis. Cecum: none.', None),
                             ('Cecum - no biopsies.', 'cecum'), ('Cecum - no lesions.', 'cecum'),
                             ('Cecum (not photographed).', 'cecum')):
            text = r3r2_note(R3R2_CELLS[0], line)
            with self.subTest(line=line):
                self.assertEqual(extent_status(text, 'gi.colonoscopy')[1], extent)

    def test_a_terminal_ileum_label_beside_a_denial_of_the_terminal_ileum(self):
        """The terminal ileum is a sub-act of a colonoscopy: its denial doubts a terminal-ileum label, never drops it to
        the insertion landmark ('incomplete: rectum', 9a9f40301's reading, which never read the label). A denial of the
        cecum still does."""
        for cell in ('Extent: terminal ileum | Prep quality: Good', 'Extent reached: TI | BBPS: 8'):
            for line in ('The terminal ileum was not intubated.', 'TI not intubated.',
                         'Unable to intubate the terminal ileum.', 'The ileocecal valve could not be traversed.',
                         'The terminal ileum could not be reached.'):
                text = r3r2_note(cell, line)
                with self.subTest(cell=cell, line=line):
                    self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('performed', None))
                    proposal = run_engine(text, [('45378', 'Procedure: Colonoscopy')])['45378']
                    self.assertIn('extent', clarified(proposal))
                    self.assertNotIn('service.incomplete', checks(proposal))
            text = r3r2_note(cell, 'Cecum not reached.')
            with self.subTest(cell=cell, line='Cecum not reached.'):
                self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('incomplete', 'incomplete: rectum'))


class S2R2Regression3ShallowCutLabelTests(unittest.TestCase):
    """regression:3, second round (high, the verifier's new problem 3) - the withhold arm dropped the incompleteness of
    a cell-cut label short of the expected depth: "Extent: transverse colon | Prep quality: Poor" beside "The transverse
    colon was not well seen due to stool." read performed with the extent withheld (a [PASS] 'Documented as performed'),
    where every older tree read the procedure incomplete. A doubt withholds only for a label at or beyond the depth the
    procedure calls for; a shorter label reads the procedure incomplete at its own landmark, as HEAD, 4347acd24 and
    d05326ef read it."""

    def test_a_doubt_beside_a_shallow_label_keeps_its_incompleteness(self):
        for cell, line, extent in (
                ('Extent: transverse colon | Prep quality: Poor', 'The transverse colon was not well seen due to stool.',
                 'incomplete: transverse colon'),
                ('Extent: transverse colon | Prep quality: Poor', 'The transverse colon could not be fully examined.',
                 'incomplete: transverse colon'),
                ('Extent: splenic flexure | Bowel preparation: inadequate', 'The splenic flexure was not inflamed.',
                 'incomplete: splenic flexure'),
                ('Extent: descending colon | Withdrawal time: 6 min', 'The descending colon was not ulcerated.',
                 'incomplete: descending colon'),
                ('Extent: hepatic flexure | Prep quality: Poor', 'The hepatic flexure was not biopsied.',
                 'incomplete: hepatic flexure'),
                ('Extent: ascending colon | Prep quality: Poor', 'The ascending colon could not be evaluated.',
                 'incomplete: ascending colon')):
            text = r3r2_note(cell, line)
            with self.subTest(cell=cell, line=line):
                self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('incomplete', extent))
                proposal = run_engine(text, [('45378', 'Procedure: Colonoscopy')])['45378']
                self.assertEqual(checks(proposal).get('service.incomplete'), 'warn')

    def test_an_outright_denial_of_a_shallow_label_still_drops_it(self):
        for cell, line in (('Extent: transverse colon | Prep quality: Poor', 'The transverse colon was not reached.'),
                           ('Extent: hepatic flexure | Prep quality: Poor', 'The hepatic flexure was not reached.')):
            text = r3r2_note(cell, line)
            with self.subTest(cell=cell):
                self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('incomplete', 'incomplete: rectum'))

    def test_the_upper_tract_short_of_its_depth(self):
        for line in ('The stomach was not well seen due to retained food.', 'The stomach was not biopsied.'):
            text = (HEADER + 'Procedure: EGD\nTechnique: The gastroscope was passed into the esophagus.\nExtent: stomach | '
                    'Sedation: MAC\nFindings: ' + line + ' Gastritis in the antrum.\nImpression: Gastritis.\n')
            with self.subTest(line=line):
                self.assertEqual(extent_status(text, 'gi.egd'), ('incomplete', 'incomplete: stomach'))
        text = (HEADER + 'Procedure: EGD\nTechnique: The gastroscope was passed into the esophagus.\nExtent: D2 | Sedation: '
                'MAC\nFindings: D2 was not well seen. Gastritis in the antrum.\nImpression: Gastritis.\n')
        self.assertEqual(extent_status(text, 'gi.egd'), ('performed', None))  # at the depth called for: withheld


# --- sections:1 (second round): an extent label short of the depth called for keeps the procedure incomplete ----------

S1R2_TECH = 'Technique: The colonoscope was inserted into the rectum and advanced.'
S1R2_EGD = 'Technique: The gastroscope was passed into the esophagus.'


def s1r2_note(label, technique=S1R2_TECH, extra=''):
    return (HEADER + 'Procedure: Colonoscopy\nIndication: Screening.\n' + technique + '\n' + label + '\nFindings: Sigmoid '
            'diverticulosis.' + extra + '\nImpression: Sigmoid diverticulosis.\n')


def s1r2_egd(label):
    return (HEADER + 'Procedure: EGD with biopsy\n' + S1R2_EGD + '\n' + label + '\nFindings: Gastritis. Biopsies were taken '
            'from the antrum.\nImpression: Gastritis.\n')


class S2R2Sections1ShallowLabelTests(unittest.TestCase):
    """sections:1, second round (high, the verifier's new problem 2) - the first round's rule sent a label refused for an
    onward rest ("not advanced further", "not advanced beyond the <its own landmark>") to plan:D2's doubted list, and a
    doubted label withheld the extent whatever its depth: "Extent: transverse colon; not advanced further due to looping"
    beside "The colonoscope was inserted into the rectum" read performed with the extent withheld (a [PASS] 'Documented as
    performed', no service.incomplete), though every base reads 'incomplete: transverse colon' (HEAD 'incomplete:
    rectum'). A doubted label short of the depth the procedure calls for now reads the procedure incomplete at its own
    landmark - reached and no further, or not reached at all, the procedure is incomplete - the bases' reading; plan:D2's
    other doubts on such a label ("; no biopsies taken", "; prep fair?") read so too, where HEAD withheld. A label at or
    beyond that depth still withholds; a reach denial, or a denial of the label's landmark elsewhere in the family's text,
    still lets the shallower prose landmark decide."""

    SHALLOW = ('sigmoid colon', 'descending colon', 'splenic flexure', 'transverse colon', 'hepatic flexure', 'ascending colon')
    ONWARD = ('not advanced further', 'not advanced further due to looping', 'could not be advanced any further',
              'scope not advanced farther due to angulation', 'not advanced beyond the {}',
              'not advanced past the {} due to a stricture', 'not advanced further, cecum not reached')

    def test_the_verifiers_inputs(self):
        for label, extent in (
                ('Extent: transverse colon; not advanced further due to looping', 'incomplete: transverse colon'),
                ('Extent: transverse colon; not advanced past the transverse colon due to a stricture',
                 'incomplete: transverse colon'),
                ('Extent: transverse colon; not advanced further, cecum not reached', 'incomplete: transverse colon'),
                ('Extent reached: splenic flexure; scope not advanced farther', 'incomplete: splenic flexure'),
                ('Extent: sigmoid colon; not advanced further due to a stricture', 'incomplete: sigmoid colon'),
                ('Extent: descending colon; scope not advanced farther due to angulation', 'incomplete: descending colon'),
                ('Extent: splenic flexure; not advanced beyond the splenic flexure due to looping',
                 'incomplete: splenic flexure')):
            text = s1r2_note(label)
            with self.subTest(label=label):
                self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('incomplete', extent))
                proposal = run_engine(text, [('45378', 'Procedure: Colonoscopy')])['45378']
                self.assertEqual(checks(proposal).get('service.incomplete'), 'warn')
        text = s1r2_egd('Extent: stomach; not advanced further due to a pyloric stricture')
        self.assertEqual(extent_status(text, 'gi.egd'), ('incomplete', 'incomplete: stomach'))
        proposal = run_engine(text, [('43239', 'Biopsies were taken from the antrum.')])['43239']
        self.assertEqual(checks(proposal).get('service.incomplete'), 'warn')

    def test_every_onward_rest_on_every_shallow_label(self):
        for landmark in self.SHALLOW:
            for rest in self.ONWARD:
                text = s1r2_note('Extent: ' + landmark + '; ' + rest.format(landmark))
                with self.subTest(landmark=landmark, rest=rest):
                    self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('incomplete', 'incomplete: ' + landmark))

    def test_plan_d2s_other_doubts_on_a_shallow_label(self):
        """The bases' reading, where HEAD withheld the extent of an incomplete colonoscopy."""
        for rest in ('no biopsies taken', 'prep fair?', 'consent not signed', 'polypectomy not performed'):
            for landmark in ('transverse colon', 'hepatic flexure'):
                text = s1r2_note('Extent: ' + landmark + '; ' + rest)
                with self.subTest(rest=rest, landmark=landmark):
                    self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('incomplete', 'incomplete: ' + landmark))
        self.assertEqual(extent_status(s1r2_egd('Extent: stomach; prep fair?'), 'gi.egd'), ('incomplete', 'incomplete: stomach'))
        # two such labels: the deepest decides
        text = s1r2_note('Extent: transverse colon; prep fair?\nFurthest extent reached: hepatic flexure; no biopsies taken')
        self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('incomplete', 'incomplete: hepatic flexure'))

    def test_a_reach_denial_or_a_denial_elsewhere_lets_the_prose_decide(self):
        for label, extra in (('Extent: transverse colon; not reached', ''),
                             ('Extent: transverse colon; not advanced beyond the sigmoid colon', ''),
                             ('Extent: hepatic flexure; not advanced further than the splenic flexure', ''),
                             ('Extent: transverse colon; could not be advanced to the transverse colon', ''),
                             ('Extent: transverse colon; no biopsies taken', ' The transverse colon was not reached.'),
                             ('Extent: transverse colon; not advanced further', ' The splenic flexure could not be reached.')):
            text = s1r2_note(label, extra=extra)
            with self.subTest(label=label, extra=extra):
                self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('incomplete', 'incomplete: rectum'))

    def test_a_label_at_the_depth_called_for_still_withholds(self):
        self.assertEqual(extent_status(s1r2_note('Extent: cecum; not advanced further due to looping'), 'gi.colonoscopy'),
                         ('performed', None))
        # plan:D2's guard reads the nearest denial outside the label's own sentence: one between still lets the prose
        # landmark decide, whatever lies beyond the label
        text = s1r2_note('Extent: cecum; prep fair?', extra=' The transverse colon was not reached. TI not intubated.')
        self.assertEqual(extent_status(text, 'gi.colonoscopy')[1], 'incomplete: rectum')
        text = s1r2_note('Extent: cecum; prep fair?', extra=' TI not intubated.')
        self.assertIsNone(extent_status(text, 'gi.colonoscopy')[1])
        for label in ('Extent: D2; not advanced further', 'Extent: duodenal bulb; not advanced past the duodenal bulb'):
            with self.subTest(label=label):
                self.assertEqual(extent_status(s1r2_egd(label), 'gi.egd'), ('performed', None))

    def test_a_deeper_prose_landmark_still_decides(self):
        text = s1r2_note('Extent: transverse colon; not advanced further',
                         'Technique: The colonoscope was advanced to the hepatic flexure.')
        self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('incomplete', 'incomplete: hepatic flexure'))


# --- sections:1 (second round): "beyond" a landmark the procedure calls for, after a deeper label ---------------------

S1B_POLYP = 'A 6 mm sigmoid polyp was removed with a cold snare.'


def s1b_note(label):
    return (HEADER + 'Procedure: Colonoscopy with cold snare polypectomy\nTechnique: The colonoscope was inserted into the '
            'rectum and advanced.\n' + label + '\nFindings: ' + S1B_POLYP + '\n')


def s1b_egd(label):
    return (HEADER + 'Procedure: EGD with biopsy\nTechnique: The gastroscope was passed into the esophagus and advanced.\n'
            + label + '\nFindings: Gastritis. Biopsies were taken from the antrum.\n')


class S2R2Sections1BeyondACompleteLandmarkTests(unittest.TestCase):
    """sections:1, second round (high, the verifier's new problem 5; every base and the round 4c-2 head disagree) - after
    a terminal-ileum label, "not advanced beyond the cecum" or "not advanced past the ileocecal valve" still counted as a
    denial of reaching the label's landmark, and the cecum in it as denied, so a complete colonoscopy read 'incomplete:
    rectum' (45385 ready with service.incomplete and a 52/53 consideration); 9a9f40301, 4347acd24 and d05326ef read it
    performed. "Beyond" or "past" now denies reaching the label's landmark only before a landmark short of both the
    label's depth and the depth the procedure calls for: the label is doubted and its extent withheld (the verifier's
    acceptable reading), never incomplete at the insertion landmark. "To" and "into", and a "beyond" short of the
    depth called for, still deny."""

    def test_the_verifiers_inputs(self):
        for label in ('Extent: terminal ileum; not advanced beyond the cecum', 'Extent: terminal ileum; not advanced past the cecum',
                      'Extent: terminal ileum; not advanced past the ileocecal valve', 'Extent: TI; not advanced beyond the cecum',
                      'Extent: terminal ileum; not advanced beyond the cecum due to looping',
                      'Extent: terminal ileum; not advanced beyond the appendiceal orifice'):
            text = s1b_note(label)
            with self.subTest(label=label):
                self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('performed', None))
                proposal = run_engine(text, [('45385', S1B_POLYP)])['45385']
                self.assertIn('extent', clarified(proposal))
                self.assertNotIn('service.incomplete', checks(proposal))

    def test_the_upper_tract(self):
        """An EGD calls for the duodenum (the bulb): "beyond D2" after a third-part label is no incompleteness."""
        for label in ('Extent: third part of the duodenum; not advanced beyond D2',
                      'Extent: third part of the duodenum; not advanced beyond the second part of the duodenum',
                      'Extent: third part of the duodenum; not advanced past the duodenal bulb'):
            text = s1b_egd(label)
            with self.subTest(label=label):
                self.assertEqual(extent_status(text, 'gi.egd'), ('performed', None))
                proposal = run_engine(text, [('43239', 'Biopsies were taken from the antrum.')])['43239']
                self.assertNotIn('service.incomplete', checks(proposal))

    def test_a_denial_short_of_the_depth_called_for_still_denies(self):
        for label, slug, extent in (
                ('Extent: terminal ileum; not advanced beyond the transverse colon', 'gi.colonoscopy', 'incomplete: rectum'),
                ('Extent: terminal ileum; not advanced further than the sigmoid colon', 'gi.colonoscopy', 'incomplete: rectum'),
                ('Extent: terminal ileum; could not be advanced to the cecum', 'gi.colonoscopy', 'incomplete: rectum'),
                ('Extent: cecum; not advanced beyond the hepatic flexure', 'gi.colonoscopy', 'incomplete: rectum'),
                ('Extent: D2; not advanced beyond the stomach', 'gi.egd', 'incomplete: esophagus'),
                ('Extent: D2; could not be advanced past the pylorus', 'gi.egd', 'incomplete: esophagus')):
            text = s1b_note(label) if slug == 'gi.colonoscopy' else s1b_egd(label)
            with self.subTest(label=label):
                self.assertEqual(extent_status(text, slug)[1], extent)


# --- sections:0 (second round): landmark fields stating the landmark, and report fields naming a procedure ----------

S0R2_TECH = 'Procedure: Colonoscopy\nTechnique: The colonoscope was inserted into the rectum and advanced.\n'
S0R2_FIELDS = (('Cecum: reached', 'cecum'), ('Cecum: reached without difficulty', 'cecum'),
               ('Cecum: reached at 6 minutes', 'cecum'), ('Cecum: reached in 5 min', 'cecum'),
               ('Cecum: reached with ease', 'cecum'), ('Cecum: reached after abdominal pressure', 'cecum'),
               ('Cecum: reached with patient repositioning', 'cecum'), ('Cecum: reached, landmarks photographed', 'cecum'),
               ('Cecum: reached and confirmed by photos', 'cecum'), ('Cecum: reached - yes', 'cecum'),
               ('Cecum: reached and examined', 'cecum'), ('Cecum: reached (with pictures)', 'cecum'),
               ('Cecum: reached, normal', 'cecum'), ('Terminal ileum: intubated for 5 cm', 'terminal ileum'),
               ('TI: intubated and normal', 'terminal ileum'), ('Terminal ileum: intubated, normal mucosa', 'terminal ileum'),
               ('Cecum: reached; prep good', 'cecum'), ('Cecum: reached, good prep', 'cecum'),
               ('Cecum: reached by colonoscope', 'cecum'), ('Cecum: reached, photodocumented', 'cecum'),
               ('Cecum: intubated without difficulty', 'cecum'), ('Cecum: reached easily', 'cecum'),
               ('Cecum: reached at 08:42', 'cecum'), ('Cecum: reached; photo taken', 'cecum'),
               ('Terminal ileum: intubated, 10 cm examined', 'terminal ileum'))
S0R2_PLANS = (('Findings: Sigmoid diverticulosis.\nReferral: Colorectal surgery\n', ''),
              ('Referral: Dr. B. Synthetic\n', 'Findings: Sigmoid diverticulosis.\n'),
              ('Findings: Sigmoid diverticulosis.\nOrders: CBC\n', ''))


class S2R2Sections0LandmarkFieldStatementTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:0, second round (high, the verifier's new problem 4) - the first round's landmark arm resumed a landmark
    field after an answered plan label only when every word of its value was on a closed list, so "Cecum: reached
    without difficulty", "Cecum: reached at 6 minutes" or "Terminal ileum: intubated, normal mucosa" were held and a
    complete colonoscopy read 'incomplete: rectum' (45378 ready with service.incomplete), where HEAD, 9a9f40301 and
    d05326ef read the landmark (4347acd24's 'incomplete: rectum' is the reading the first round itself rejected). A
    landmark field now resumes when its value OPENS by saying the landmark was reached or seen; the rest of the value is
    read by the section as at HEAD. A value opening with anything else, or naming a service, an intervention or a
    procedure by its form, is still held."""

    def test_the_verifiers_inputs(self):
        for field, extent in S0R2_FIELDS:
            for before, after in S0R2_PLANS:
                text = HEADER + S0R2_TECH + before + field + '\n' + after + 'Impression: Diverticulosis.\n'
                with self.subTest(field=field, plan=before[-25:]):
                    self.assertEqual(extent_status(text, 'gi.colonoscopy'), ('performed', extent))
            text = HEADER + S0R2_TECH + S0R2_PLANS[0][0] + field + '\nImpression: Diverticulosis.\n'
            with self.subTest(field=field, engine=True):
                proposal = run_engine(text, [('45378', 'Procedure: Colonoscopy')])['45378']
                self.assertTrue(ready(proposal), (proposal.bucket, proposal.status, clarified(proposal)))
                self.assertNotIn('service.incomplete', checks(proposal))

    def test_the_upper_tract(self):
        for field in ('Second part of the duodenum: reached without difficulty', 'D2: reached, normal mucosa',
                      'Second part of the duodenum: intubated with ease'):
            text = (HEADER + 'Procedure: EGD\nTechnique: The gastroscope was passed into the esophagus.\nReferral: Dr. B. '
                    'Synthetic\n' + field + '\nFindings: Gastritis.\nImpression: Gastritis.\n')
            with self.subTest(field=field):
                self.assertEqual(extent_status(text, 'gi.egd'), ('performed', 'second part of duodenum'))

    def test_a_value_opening_otherwise_is_still_held(self):
        for field in ('Rectum: internal hemorrhoids', 'Cecum: 4 cm mass', 'Cecum: not reached', 'Cecum: to be examined',
                      'Ascending colon: 4 cm mass, for right hemicolectomy', 'Cecum: with a 3 cm mass',
                      'Ileocecal valve: the site of a lipoma'):
            text = HEADER + S0R2_TECH + S0R2_PLANS[0][0] + field + '\nImpression: Diverticulosis.\n'
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, field), 'other')

    def test_a_landmark_field_naming_a_procedure_is_held(self):
        for field, code in (('Cecum: reached; right hemicolectomy with Dr. B. Synthetic', '44160'),
                            ('Cecum: reached, hemorrhoidectomy to follow', '46255'),
                            ('Duodenum: normal, esophageal manometry outpatient', '91010')):
            text = HEADER + S0_FIND + 'Referral: Colorectal surgery\n' + field + '\n'
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, field), 'other')
                self.assert_held_never_excluded(text, code, field)


class S2R2Sections0ReportFieldNamingAProcedureTests(HeldOrReadyAssertions, unittest.TestCase):
    """sections:0, second round (critical, the verifier's new problem 6; 4347acd24 excluded it, the other trees read it
    ready) - a field of the closed list resumed whatever else its value named, when routing detected no service in it:
    "Extent: cecum, right hemicolectomy with Dr. B. Synthetic" or "Retroflexion: done; hemorrhoidectomy with Dr. B.
    Synthetic" after "Referral: Colorectal surgery" read performed (section: findings) and 44160 / 46255 were READY. The
    first round's report wrongly said every base read it ready. A report field that names a procedure by its form (as
    routing's gi.other reader reads it: -ectomy, -otomy, -scopy, ligation, banding, manometry...) is now held, never
    performed and never planned."""

    def test_the_verifiers_inputs(self):
        colon = ('Procedure: Colonoscopy with biopsy and tattoo\nFindings: The colonoscope was advanced to the cecum. A 4 cm '
                 'fungating ascending colon mass was biopsied and tattooed.\nReferral: Colorectal surgery\n')
        hemorrhoids = ('Procedure: Colonoscopy\nFindings: The colonoscope was advanced to the cecum. Large internal '
                       'hemorrhoids with stigmata of recent bleeding.\nReferral: Colorectal surgery\n')
        for body, field, code in ((colon, 'Extent: cecum, right hemicolectomy with Dr. B. Synthetic', '44160'),
                                  (hemorrhoids, 'Retroflexion: done; hemorrhoidectomy with Dr. B. Synthetic', '46255')):
            text = HEADER + body + field + '\nImpression: Findings as above.\n'
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, field), 'other')
                self.assert_held_never_excluded(text, code, field)
                self.assertEqual(fact_value(text, 'gi.colonoscopy', 'extent'), 'cecum')  # the prose still reaches it

    def test_every_listed_field_naming_a_procedure(self):
        for field, code in (('Withdrawal time: 8 min; hemorrhoidectomy with Dr. B. Synthetic', '46255'),
                            ('Insertion time: 5 min; right hemicolectomy with Dr. B. Synthetic', '44160'),
                            ('Prep quality: good; anoscopy by Dr. B. Synthetic', '46600'),
                            ('BBPS: 8, esophageal manometry with Dr. B. Synthetic', '91010'),
                            ('Retroflexion: done; right hemicolectomy with Dr. B. Synthetic', '44160'),
                            ('Extent: cecum | Withdrawal time: 9 min | hemorrhoidectomy referral', '46255')):
            text = HEADER + S0_FIND + 'Referral: Colorectal surgery\n' + field + '\n'
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, field), 'other')
                self.assert_held_never_excluded(text, code, field)

    def test_report_fields_naming_nothing_still_resume(self):
        for field in ('Extent: cecum', 'Withdrawal time: 8 minutes', 'Prep quality: good', 'BBPS: 8',
                      'Retroflexion: done', 'Extent: cecum, photos taken', 'Insertion time: 5 minutes'):
            text = HEADER + 'Procedure: Colonoscopy\nReferral: Dr. B. Synthetic, primary care\n' + field + '\n'
            with self.subTest(field=field):
                self.assertEqual(kind_at(text, field), 'procedure')


if __name__ == '__main__':
    unittest.main()
