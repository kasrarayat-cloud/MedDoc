"""Completion design, reach group (2026-11-07): a reach stated by findings (U19), read by routing only, never by the
request side; repaired after its first refutation (cycle 1 -> cycle 2, the owner's decisions).

1. U19: where the installed readers give a colonoscopy or an EGD no extent at all, a findings statement in the family's
   own performed text - "Terminal ileum normal.", "Duodenal bulb and D2 normal.", "Duodenum: The bulb and the second
   portion were normal." - reads its landmarks as reached exactly as its copula twin ("The terminal ileum was normal.")
   is read, deepest wins (detect._stated_clause, _stated_reaches). It is read whole: a source, a time, a limitation or
   a located finding anywhere in its clause makes it no statement.
2. A denial or doubt of a reach anywhere in the family's own text keeps every findings statement from releasing: the
   critic's 'Duodenal bulb normal; second portion not examined.' stays held (its reach-verb twin reads 'incomplete:
   duodenal bulb'), and so do 'Duodenum: not examined.', 'Duodenum: deferred.', 'Cecum and terminal ileum not seen.',
   'Exam limited to the bulb.' and a correction ('not the cecum').
3. The cycle-1 repair:
   (a) a statement never overrides, replaces or deepens an installed reach - it is read only where the installed
       readers read no reach at all, or only the insertion they discard (detect._with_stated);
   (b) it never creates an incompleteness - only a statement at or beyond the depth the family calls for counts;
   (c) it is a statement as written - a whole sentence of statement clauses ending with terminal punctuation, or a list
       item's whole line; never a label-like line standing alone ("Cecum reached" over its answer line) and never a
       line a next sentence or line answers ("No.", "[ ] Yes [x] No") (detect._stated_as_written);
   (d) it is in its own context - the label governing it is a findings heading, the family's own label or an organ
       label (and the titles over that label are too), and the sentence before it carries no time, place, agent or
       source signal (detect._stated_in_context, _stated_titles_allow);
   the present-participle reach (C13, ", reaching the cecum") is dropped with its pattern, and a flexible
   sigmoidoscopy, which calls for no depth, keeps its installed reading.
Synthetic paraphrases of the shapes only."""
from datetime import date

from django.test import SimpleTestCase

from studio.gi import cues, detect, sections

DAY = date(2026, 10, 14)
HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Endoscopy Procedure Report\n'
        'Date of service: 2026-10-14\n'
        'Endoscopist: Synthetic Endoscopist, MD (fictional)\n')
EGD_TAIL = '\nInterventions:\n  1. Cold forceps biopsies of the antrum (jar A).\n\nPlan:\n  1. Await pathology.\n'
COL_TAIL = ('\nInterventions:\n  1. A 6 mm polyp was removed by cold snare from the transverse colon (jar A).\n\n'
            'Plan:\n  1. Await pathology.\n')


def egd(*lines, procedure='EGD', head=HEAD, after=''):
    return (head + f'Procedure: {procedure}\nIndication: Dyspepsia.\n\nFindings:\n'
            + ''.join(f'  {i}. {line}\n' for i, line in enumerate(lines, 1)) + after + EGD_TAIL)


def colonoscopy(*lines, procedure='Colonoscopy', head=HEAD, after=''):
    return (head + f'Procedure: {procedure}\nIndication: Screening.\n\nFindings:\n'
            + ''.join(f'  {i}. {line}\n' for i, line in enumerate(lines, 1)) + after + COL_TAIL)


def finding(text, family):
    return next(f for f in detect.route(text, DAY).findings if f.family == family)


def extent(text, family):
    return next((fact.value for fact in finding(text, family).facts if fact.name == 'extent'), None)


class FindingsStatedReachTests(SimpleTestCase):

    def test_a_findings_statement_reads_as_its_copula_twin(self):
        for statement, twin, family, want in (
                ('Terminal ileum normal.', 'The terminal ileum was normal.', 'gi.colonoscopy', 'terminal ileum'),
                ('Cecum reached.', 'The cecum was reached.', 'gi.colonoscopy', 'cecum'),
                ('Duodenal bulb and D2 normal.', 'The duodenal bulb and D2 were normal.', 'gi.egd',
                 'second part of duodenum'),
                ('Second portion of the duodenum normal.', 'The second portion of the duodenum was normal.', 'gi.egd',
                 'second part of duodenum')):
            with self.subTest(statement):
                build = egd if family == 'gi.egd' else colonoscopy
                self.assertEqual(extent(build(twin), family), want)  # the installed reading of the twin
                self.assertEqual(extent(build(statement), family), want)

    def test_the_shapes_the_installed_readers_left_unread(self):
        for lines, want in (
                (('Esophagus normal, stomach normal, duodenum normal.',), 'duodenum'),
                (('Antral erythema.', 'Duodenum: The bulb and the second portion were normal.'), 'second part of duodenum'),
                (('The duodenal bulb and second portion looked normal.',), 'second part of duodenum'),
                (('The stomach, including a retroflexed view of the cardia and fundus, was normal, as were the '
                  'pylorus, the bulb and the second portion of the duodenum, which was as far as the scope went.',),
                 'second part of duodenum')):
            with self.subTest(lines[-1]):
                self.assertEqual(extent(egd(*lines), 'gi.egd'), want)

    def test_a_list_item_without_terminal_punctuation_is_its_whole_line(self):
        text = (HEAD + 'Procedure: Colonoscopy\nIndication: Screening.\n\nFindings:\n  1. The bowel preparation was good.\n'
                '  2. Terminal ileum normal\n' + COL_TAIL)
        self.assertEqual(extent(text, 'gi.colonoscopy'), 'terminal ileum')

    def test_the_latent_extents(self):
        # NAMED CHANGE (cycle-1 repair, decision (a)): 'TI entered ~6 cm' no longer deepens the installed 'cecum' read
        # from 'Advanced to cecum' - a statement never overrides or deepens an installed reach; the reading is installed
        self.assertEqual(extent(colonoscopy('Advanced to cecum - AO + ICV seen and photographed. TI entered ~6 cm, '
                                            'nl mucosa.'), 'gi.colonoscopy'), 'cecum')
        self.assertEqual(extent(colonoscopy('Cecum confirmed by appendiceal orifice and ileocecal valve.'),
                                'gi.colonoscopy'), 'cecum')

    def test_a_statement_with_anything_else_in_its_clause_is_none(self):
        for statement in ('Terminal ileum normal per the outside report.', 'Terminal ileum normal on CT enterography.',
                          'Terminal ileum normal in 2019.', 'Terminal ileum normal at the last colonoscopy.',
                          'On CT enterography, terminal ileum normal.', 'Terminal ileum normal?',
                          'Terminal ileum probably normal.', 'Terminal ileum seen only from the cecum.',
                          'Small polyp in the sigmoid colon, terminal ileum normal.', '[ ] Terminal ileum normal.',
                          'Extent: Terminal ileum, approx 5 cm.'):
            with self.subTest(statement):
                self.assertIsNone(extent(colonoscopy('Transverse colon polyp, 6 mm.', statement), 'gi.colonoscopy'))
        for statement in ('Duodenum seen poorly.', 'Duodenum: poorly visualized due to retained food.',
                          'Bulb and second portion normal.',  # no word of the duodenum: the parts are nobody's
                          'The stomach, including CT images, was normal, as were the duodenal bulb and the second '
                          'portion of the duodenum.'):
            with self.subTest(statement):
                self.assertIsNone(extent(egd('Antral erythema.', statement), 'gi.egd'))


class StatedReachDoubtTests(SimpleTestCase):

    def test_the_critics_case_stays_held(self):
        # its reach-verb twin reads 'incomplete: duodenal bulb'; the findings statement never reads it complete
        twin = egd('The scope was advanced to the duodenal bulb; the second portion was not examined.')
        self.assertEqual(extent(twin, 'gi.egd'), 'incomplete: duodenal bulb')
        for statement in ('Duodenal bulb normal; second portion not examined.',
                          'Duodenal bulb normal; second portion of the duodenum not examined.'):
            with self.subTest(statement):
                self.assertIsNone(extent(egd('Antral erythema.', statement), 'gi.egd'))

    def test_a_denial_or_doubt_anywhere_in_the_familys_text_holds(self):
        for lines in (('Antral erythema.', 'Duodenum: not examined.'),
                      ('Antral erythema.', 'Duodenum: deferred.'),
                      ('Antral erythema.', 'Duodenum not entered due to pyloric stenosis.'),
                      ('Duodenal bulb and D2 normal.', 'Exam limited to the bulb.'),
                      ('Duodenal bulb normal.', 'Unable to pass into the second portion because of a stricture.'),
                      ('Duodenal bulb normal.', 'Second portion: deferred.')):
            with self.subTest(lines[-1]):
                self.assertIsNone(extent(egd(*lines), 'gi.egd'))
        for lines in (('Transverse colon polyp, 6 mm.', 'Cecum and terminal ileum not seen.'),
                      ('Terminal ileum normal.', 'The cecum was not reached.'),
                      ('Terminal ileum normal.', 'Correction: this was the hepatic flexure, not the cecum.'),
                      ('Terminal ileum normal.', 'The examination was incomplete due to poor preparation.'),
                      ('Cecum normal.', 'Terminal ileum not intubated.')):
            with self.subTest(lines[-1]):
                self.assertIsNone(extent(colonoscopy(*lines), 'gi.colonoscopy'))

    def test_a_statement_never_makes_a_procedure_incomplete(self):
        # the copula twin reads 'incomplete: ascending colon'; a findings statement alone short of the cecum reads none
        self.assertEqual(extent(colonoscopy('The ascending colon was normal.'), 'gi.colonoscopy'),
                         'incomplete: ascending colon')
        self.assertIsNone(extent(colonoscopy('Ascending colon normal.'), 'gi.colonoscopy'))
        self.assertIsNone(extent(egd('Esophagus normal.', 'Stomach normal.'), 'gi.egd'))

    def test_a_statement_never_overrides_a_short_extent_label(self):
        # the document's own statement of the extent, read or not, names a landmark short of the depth called for
        def labelled(build, line, indication, label):
            return build(line).replace(f'Indication: {indication}', f'Indication: {indication}\nExtent: {label}')
        self.assertIsNone(extent(labelled(colonoscopy, 'Terminal ileum normal.', 'Screening.', 'Hepatic flexure.'),
                                 'gi.colonoscopy'))
        self.assertIsNone(extent(labelled(egd, 'Duodenal bulb and D2 normal.', 'Dyspepsia.', 'Stomach.'), 'gi.egd'))
        # a label at the depth called for constrains nothing; one refused as an aim holds (cycle-1 repair)
        text = labelled(colonoscopy, 'Terminal ileum normal.', 'Screening.', 'Cecum.')
        self.assertEqual(extent(text, 'gi.colonoscopy'), 'terminal ileum')
        self.assertIsNone(extent(labelled(colonoscopy, 'Terminal ileum normal.', 'Screening.', 'cecum (intended).'),
                                 'gi.colonoscopy'))

    def test_an_impression_restates_nothing(self):
        text = egd('Esophagus with LA grade B esophagitis.').replace(
            'Plan:', 'Impression:\n  1. Esophagitis.\n  2. Normal stomach and duodenum.\n\nPlan:')
        self.assertIsNone(extent(text, 'gi.egd'))

    def test_the_family_must_be_named_as_todays(self):
        # a colonoscopy's findings statement in a report whose head and section name only the EGD (PE's pasted-block
        # amendment): the colonoscopy reads performed from its own sentence, and its statement is never read
        def report(procedure, line):
            return (HEAD + f'Procedure: {procedure}\nIndication: Dyspepsia.\n\nFindings:\n  1. Stomach normal.\n'
                    f'  2. Duodenal bulb and D2 normal.\n  3. {line}\n' + EGD_TAIL)
        line = 'The colonoscopy was unremarkable; cecum and terminal ileum normal.'
        found = {f.family: f.status for f in detect.route(report('EGD with biopsy', line), DAY).findings}
        self.assertEqual(found.get('gi.colonoscopy'), 'performed')
        self.assertEqual(extent(report('EGD with biopsy', line), 'gi.egd'), 'second part of duodenum')
        self.assertIsNone(extent(report('EGD with biopsy', line), 'gi.colonoscopy'))
        # NAMED CHANGE (cycle-1 repair, decision (c)): the same sentence no longer reads once the head names the
        # colonoscopy - 'The colonoscopy was unremarkable;' is no statement clause, so its sentence is no statement
        self.assertIsNone(extent(report('EGD with biopsy; colonoscopy', line), 'gi.colonoscopy'))


class InstalledReachStandsTests(SimpleTestCase):
    """Decision (a): a statement never overrides, replaces or deepens an installed reach, and never turns a family
    incomplete -> performed (release#7, regress#6); the insertion the installed readers discard opens the family."""

    def test_a_short_installed_reach_keeps_its_incompleteness(self):
        short = 'The gastroscope was advanced to the gastric antrum, where retained food filled the lumen.'
        for after in ('', '\nEGD two years ago: Stomach normal. Duodenal bulb and D2 normal.\n',
                      '\nCT abdomen and pelvis: no obstruction. Duodenum normal.\n'):
            with self.subTest(after):
                self.assertEqual(extent(egd(short, after=after), 'gi.egd'), 'incomplete: stomach')
                self.assertEqual(finding(egd(short, after=after), 'gi.egd').status, 'incomplete')
        text = colonoscopy('The colonoscope was advanced to the hepatic flexure. The examination ended there because of '
                           'poor preparation.', after='\nColonoscopy two years ago: Cecum reached. Terminal ileum normal.\n')
        self.assertEqual(extent(text, 'gi.colonoscopy'), 'incomplete: hepatic flexure')
        self.assertEqual(extent(colonoscopy('The colonoscope was advanced to the hepatic flexure.',
                                            'Terminal ileum normal.'), 'gi.colonoscopy'), 'incomplete: hepatic flexure')

    def test_an_installed_extent_is_never_deepened(self):
        # the installed reading of the organ list and of the copula shapes stands, statements beside it unread.
        # NAMED CHANGE (cycle-1 repair, decision (a)): these three read 'second part of duodenum' before the repair
        for lines, want in (
                (('Esophagus: Normal.', 'Stomach: Normal, including the retroflexed view of the cardia.',
                  'Duodenum: The bulb and the second portion were normal.'), 'incomplete: stomach'),
                (('The esophagus was normal.', 'The stomach was normal.',
                  'The duodenal bulb and second portion looked normal.'), 'incomplete: stomach'),
                (('Duodenum: Normal bulb and second portion.',), 'duodenum')):
            with self.subTest(lines[-1]):
                self.assertEqual(extent(egd(*lines), 'gi.egd'), want)
        self.assertEqual(extent(colonoscopy('At her baseline colonoscopy the cecum was reached. Terminal ileum normal.'),
                                'gi.colonoscopy'), 'cecum')

    def test_a_documented_incompleteness_is_never_consumed(self):
        # routing documents the service incomplete: no statement answers its extent (cycle-1 repair, a doubt of the
        # extent no statement may consume); the copula twin's installed reading is the installed release's own
        text = egd('Antral erythema.', 'Duodenal bulb and D2 normal.', procedure='EGD (incomplete)')
        self.assertIsNone(extent(text, 'gi.egd'))
        self.assertEqual(finding(text, 'gi.egd').status, 'incomplete')
        text = colonoscopy('The bowel preparation was good.', 'Terminal ileum normal.', procedure='Colonoscopy (incomplete)')
        self.assertIsNone(extent(text, 'gi.colonoscopy'))
        self.assertEqual(finding(text, 'gi.colonoscopy').status, 'incomplete')

    def test_a_stop_statement_keeps_the_installed_extent(self):
        text = egd('The gastroscope was advanced into the stomach.', 'The scope went no further than the stomach.',
                   'Duodenum normal.')
        self.assertEqual(extent(text, 'gi.egd'), 'incomplete: stomach')

    def test_the_insertion_alone_opens_the_family_to_a_statement_at_its_depth(self):
        inserted = 'The colonoscope was inserted into the rectum and advanced.'
        self.assertEqual(extent(colonoscopy(inserted, 'Terminal ileum normal.'), 'gi.colonoscopy'), 'terminal ileum')
        # decision (b): a statement short of the depth called for never makes it incomplete (regress#2)
        for line in ('Hepatic flexure normal.', 'Transverse colon normal.'):
            with self.subTest(line):
                text = colonoscopy(inserted, line)
                self.assertIsNone(extent(text, 'gi.colonoscopy'))
                self.assertEqual(finding(text, 'gi.colonoscopy').status, 'performed')
        text = egd('The gastroscope was introduced into the esophagus.', 'Esophagus normal.', 'Stomach normal.')
        self.assertIsNone(extent(text, 'gi.egd'))
        self.assertEqual(finding(text, 'gi.egd').status, 'performed')


class StatementAsWrittenTests(SimpleTestCase):
    """Decision (c): a label-like line standing alone, or a line an answer follows, is no statement (release#0)."""

    def test_a_form_question_and_its_answer_are_no_statement(self):
        prior = ('A 6 mm polyp was removed by cold snare from the transverse colon (jar A).', 'The bowel preparation was good.')
        for form in ('\nCecum reached\n\u2610 Yes \u2612 No\n', '\nCecum reached\nNo.\n', '\nCecum reached\nN\n',
                     '\nCecum reached\n[ ] Yes [x] No\n',
                     '\nCecum reached\nNo - poor preparation, examination ended at the hepatic flexure\n',
                     '\nAppendiceal orifice visualized\nNo\nIleocecal valve visualized\nNo\n',
                     '\nCecum reached.\nNo.\n', '\nCecum reached. No.\n', '\nCecum reached.\n\nNo.\n',
                     '\nCecum reached.\nAnswer: No\n', '\nCecum reached.\nYes\n'):
            with self.subTest(form):
                self.assertIsNone(extent(colonoscopy(*prior, after=form), 'gi.colonoscopy'))
        self.assertIsNone(extent(egd('Antral erythema.', after='\nDuodenum entered\nNo\nSecond portion of the duodenum '
                                                               'examined\nNo\n'), 'gi.egd'))
        # the form beside an installed short reach keeps its incompleteness
        text = colonoscopy('The colonoscope was advanced to the hepatic flexure, where looping stopped further progress.',
                           after='\nCecum reached\n\u2610 Yes \u2612 No\n')
        self.assertEqual(extent(text, 'gi.colonoscopy'), 'incomplete: hepatic flexure')

    def test_a_sentence_with_a_clause_that_is_no_statement_is_none(self):
        for line in ('Terminal ileum normal; per the outside report.', 'Terminal ileum normal; this was in 2019.'):
            with self.subTest(line):
                self.assertIsNone(extent(colonoscopy('The bowel preparation was good.', line), 'gi.colonoscopy'))

    def test_a_flexible_sigmoidoscopy_keeps_its_installed_reading(self):
        for line in ('Descending colon normal.', 'Terminal ileum normal.'):
            with self.subTest(line):
                text = colonoscopy('The bowel preparation was good.', line, procedure='Flexible sigmoidoscopy')
                self.assertIsNone(extent(text, 'gi.flex_sig'))
        self.assertIsNone(extent(colonoscopy('The bowel preparation was good.', after='\nDescending colon reached\nNo\n',
                                             procedure='Flexible sigmoidoscopy'), 'gi.flex_sig'))


class StatementContextTests(SimpleTestCase):
    """Decision (d): another record's label, its title over a findings heading, or a sentence before the statement
    that names another time, place, agent or source keeps it from releasing (release#3, release#4)."""

    STOP = 'The colonoscope reached only the hepatic flexure because of looping.'

    def test_another_records_label_holds(self):
        for after in ('\nColonoscopy 2 years ago: No polyps. Terminal ileum normal.\n',
                      '\nMost recent colonoscopy (2 years ago): No polyps. Terminal ileum normal.\n',
                      '\nBaseline: Left-sided colitis. Terminal ileum normal.\n',
                      "\nDr. Synthetic Other's colonoscopy: No polyps. Terminal ileum normal.\n",
                      '\nCT colonography (same day, to complete the evaluation):\n  - Cecum and terminal ileum normal.\n',
                      '\nBaseline colonoscopy:\nCecum reached. Terminal ileum normal.\n',
                      '\nPrior colonoscopy report:\nFindings:\n1. Terminal ileum normal.\n',
                      '\nPrior colonoscopy report:\nEndoscopist: Synthetic Other, MD\nFindings:\n1. Terminal ileum normal.\n',
                      '\nPrior colonoscopy report:\n\nFindings:\n1. Terminal ileum normal.\n',
                      '\nImpression:\n  1. Terminal ileum normal.\n'):
            with self.subTest(after):
                self.assertIsNone(extent(colonoscopy(self.STOP, after=after), 'gi.colonoscopy'))
        for after in ('\nEGD two years ago: Stomach normal. Duodenal bulb and D2 normal.\n',
                      '\nCT abdomen: Duodenum normal.\n', '\nCapsule endoscopy:\n- Duodenum and jejunum normal.\n'):
            with self.subTest(after):
                self.assertIsNone(extent(egd('Antral erythema.', after=after), 'gi.egd'))

    def test_a_sentence_before_it_that_names_another_occasion_holds(self):
        for prior in ('For comparison, her colonoscopy two years ago showed no polyps.',
                      'At diagnosis the colitis was left-sided.', 'The referring physician reports no polyps.',
                      'Most recent colonoscopy: cecum reached.', 'Outside records reviewed.'):
            with self.subTest(prior):
                self.assertIsNone(extent(colonoscopy(self.STOP, prior, 'Terminal ileum normal.'), 'gi.colonoscopy'))
        # across a blank line too, within the section
        self.assertIsNone(extent(colonoscopy(self.STOP, after='\nOutside records reviewed.\n\nTerminal ileum normal.\n'),
                                 'gi.colonoscopy'))

    def test_its_own_context_releases(self):
        self.assertEqual(extent(colonoscopy('The bowel preparation was good.', 'Terminal ileum normal.'),
                                'gi.colonoscopy'), 'terminal ileum')
        self.assertEqual(extent(colonoscopy('The bowel preparation was good.', after='\nColonoscopy: Terminal ileum '
                                                                                   'normal.\n'), 'gi.colonoscopy'),
                         'terminal ileum')
        self.assertEqual(extent(egd('Antral erythema.', 'Duodenum: The bulb and the second portion were normal.'),
                                'gi.egd'), 'second part of duodenum')
        # a two-procedure report whose part title the layout leaves inside a "Prior endoscopy: None." section: the
        # title over the findings heading is judged by its words, the family's own name
        text = (HEAD + 'Procedure: EGD with biopsies; colonoscopy with polypectomy\nIndication: Anemia.\n'
                'Prior endoscopy: None.\nScope: Standard gastroscope.\n\n-- EGD --\nExtent of exam: Second portion of '
                'duodenum.\nFindings:\n  1. Antral erythema.\n  2. Duodenal bulb and D2 normal.\n' + EGD_TAIL)
        self.assertEqual(extent(text, 'gi.egd'), 'second part of duodenum')


class StatedExtentIsNoEvidenceTests(SimpleTestCase):
    """A findings statement answers the extent, never whether the procedure was done (detect._with_stated,
    STATED_ONLY_EXTENT): where only statements give a family its extent, routing does not count it among the family's
    evidence (EVIDENCE_FACTS), so a family held on its section alone in a visit note stays held."""

    VISIT = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nClinic Visit Note\n'
             'Date of service: 2026-10-14\nHistory of present illness: Change in bowel habit for three months.\n'
             'Medical decision making: moderate complexity.\nProcedure: Colonoscopy\nFindings:\n  1. {line}\n'
             'Assessment and plan: Follow up in clinic.\n')

    def status(self, text):
        return finding(text, 'gi.colonoscopy').status

    def test_the_family_stays_held_while_its_extent_is_read(self):
        text = self.VISIT.format(line='Terminal ileum normal.')
        self.assertEqual(extent(text, 'gi.colonoscopy'), 'terminal ileum')
        self.assertEqual(self.status(text), 'uncertain')
        # the installed copula twin is the family's evidence, as before
        twin = self.VISIT.format(line='The terminal ileum was normal.')
        self.assertEqual((extent(twin, 'gi.colonoscopy'), self.status(twin)), ('terminal ileum', 'performed'))


class OwnPartTests(SimpleTestCase):
    """A two-procedure report's organ lines belong to the procedure whose part they are in (detect._reach_own_part),
    whatever family routing attributes their sentence to."""

    def report(self, procedures, *lines):
        return (HEAD + f'Procedures: {procedures}\nIndication: Abnormal imaging.\n\nFINDINGS:\n' + '\n'.join(lines)
                + '\n' + EGD_TAIL)

    def test_another_upper_procedures_part_is_not_the_egds(self):
        for other, line in (('ERCP', 'ERCP: The duodenoscope was advanced to the major papilla. Duodenal bulb and D2 '
                                     'normal. The bile duct was cannulated.'),
                            ('EUS', 'Endoscopic ultrasound: The echoendoscope was passed into the duodenum. Duodenal '
                                    'bulb and D2 normal. The pancreatic head was normal.'),
                            ('ERCP', 'ERCP: The duodenoscope was advanced, reaching the second portion of the '
                                     'duodenum. The bile duct was cannulated.')):
            with self.subTest(line):
                text = self.report(f'EGD; {other}', 'EGD: Esophagus normal. Stomach normal. Cold forceps biopsies of '
                                                    'the antrum were taken.', line)
                self.assertIsNone(extent(text, 'gi.egd'))

    def test_the_egds_own_part_after_another_still_reads(self):
        text = self.report('EGD; ERCP', 'ERCP: The bile duct was cannulated with the duodenoscope.',
                           'EGD: Esophagus normal, stomach normal, duodenal bulb and D2 normal.')
        self.assertEqual(extent(text, 'gi.egd'), 'second part of duodenum')


class ParticipleReachDroppedTests(SimpleTestCase):
    """The cycle-1 repair drops C13, the present-participle reach (cues.REACHED_BEFORE_GERUND and its arm in
    detect._pe_reached_before): every participle shape reads as the installed release reads it."""

    def test_the_participle_reads_as_installed(self):
        for line, want in (
                ('Incomplete colonoscopy, reaching the hepatic flexure, stopped because of retained solid stool.', None),
                ('With the pediatric colonoscope, reaching the cecum was impossible.', None),
                ('A complete colonoscopy, reaching the cecum, was intended, but the colonoscope reached only the hepatic '
                 'flexure.', None),
                ('The colonoscope reached only the sigmoid colon because of severe colitis, which on CT extends '
                 'proximally, reaching the cecum.', None),
                ('Incomplete colonoscopy, reaching the cecum the following day after a second preparation.', None),
                ('The colonoscope was advanced to the transverse colon, reaching the cecum was impossible.',
                 'incomplete: transverse colon'),
                ('The colonoscope was advanced to the hepatic flexure, reaching the cecum was the goal.',
                 'incomplete: hepatic flexure')):
            with self.subTest(line):
                self.assertEqual(extent(colonoscopy(line), 'gi.colonoscopy'), want)

    def test_the_sub_act_reading_is_installed(self):
        # regress#1: the participle no longer feeds _reached_expected_depth, so the TI failure stays an incompleteness
        text = colonoscopy('With the colonoscope, reaching the cecum was impossible.',
                           'The terminal ileum could not be intubated.')
        self.assertEqual(finding(text, 'gi.colonoscopy').status, 'incomplete')
        self.assertIsNone(extent(text, 'gi.colonoscopy'))


class RequestSideTests(SimpleTestCase):

    def test_the_new_vocabulary_is_routing_only(self):
        # sections reads the landmark tables and the installed reach cues; the parts are not theirs, and the dropped
        # participle pattern is gone
        source = open(sections.__file__, encoding='utf-8').read()
        self.assertNotIn('DUODENAL_PARTS', source)
        self.assertFalse(hasattr(cues, 'REACHED_BEFORE_GERUND'))
        self.assertFalse(any(label == 'second part of duodenum' and pattern.search('second portion normal')
                             for label, _, pattern in cues.UPPER_LANDMARKS))

    def test_a_clause_too_long_or_naming_too_many_parts_is_no_statement(self):
        long = egd('Duodenum: ' + ' and the '.join(['bulb'] * (detect._STATED_PARTS + 1)) + ' were normal.')
        self.assertIsNone(extent(long, 'gi.egd'))
