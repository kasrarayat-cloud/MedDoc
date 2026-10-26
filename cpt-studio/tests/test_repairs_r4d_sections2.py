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
        text = s1_note('Extent: terminal ileum; not advanced beyond the cecum')  # the TI label denied by its own rest
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


if __name__ == '__main__':
    unittest.main()
