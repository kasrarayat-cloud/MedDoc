"""The structure round (2026-11-08), U18: the corroborated release of a labelled paragraph (studio.gi.structure).

A labelled paragraph that N1 holds only by its two open-world readings - a place object no allow-list anchors and a
temporal adjunct no step of today's anchors - is released when the report itself states the paragraph's acts as today's
by its own structure: a procedure line lists an act of the family (C1), an impression or assessment statement bound to
the family restates it as a plain statement (C2), every act the paragraph states is one or the other, each sentence reads
no closed signal on its own words and an open-world adjunct stands only in a sentence stating today's procedure content
(C3), and nothing before the paragraph names another, undated occasion of the family (C4). Every condition is pinned by a
minimal positive and negative pair; every closed reading, P1-P3, N2 and N3 keep holding as installed, and a held
paragraph keeps its installed reason. Synthetic documents only: the walked shape is paraphrased (other sites, other
words, other numbers), never its lines.

Cycle 2 (u18c2): the repairs of the cycle-1 refutation are pinned below - the parts construction (a corroborated paragraph
changes the kind of no part outside itself: PartsConstructionTests, against the installed reading of the same text), C5
(the paragraph's procedure section is its heading twin's: TwinSectionTests), P4 read again after a withdrawal, and the
cost (one act-predicate search per clause; the bounds: BoundTests).

The changed approach (u18d): C1-C5 only propose; a corroborated release stands only where the installed readers read the
document's heading twin exactly as they read the document with the release (structure._twin_parity: computed, never
predicted), and the document reads as installed otherwise. u18c2's four refuted HIGHs are pinned in paraphrase
(TwinParityTests: the site-less act a label bound in a two-family report, the label read against its second sentence),
with the walked shape (CorroboratedReleaseTests), each structural choice the comparison checks and the comparison's own
withdrawals (ComparisonTests), the reading modes that keep its readings apart from the real one (ReadingModeTests), and
its cost (GuardCostTests)."""
import time

from django.test import SimpleTestCase

from studio.gi import detect, structure
from studio.gi import services as gi_services
from studio.types import EvidenceSpan
from tests.test_harness_engine import DAY, corti, proposal, run, span

HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
        'Gastroenterology Procedure Report\n'
        'Date of service: 2026-10-14\n'
        'Endoscopist: Synthetic Endoscopist, MD (fictional)\n')
LINE = 'Procedures: Upper endoscopy with dilation and biopsies; colonoscopy with polypectomy\n'
IND = 'Indications: Dysphagia; surveillance after adenomas.\n'
BIOPSY = 'Cold forceps biopsies were obtained from the distal esophagus.'
DILATION = 'Bougies of 15 and 16 mm were passed over the guidewire.'
# the open-world sentence of the upper paragraph: a temporal adjunct and a place object no allow-list knows, in a
# sentence about the scope (today's procedure content)
WIRE = 'The scope was removed while the guidewire stayed in position, and its depth mark was read at the mouthpiece.'
EGD = ('Upper endoscopy: The gastroscope was passed through the mouth to the second portion of the duodenum. ' + BIOPSY
       + ' A guidewire was passed into the antrum. ' + WIRE + ' ' + DILATION + '\n')
COURSE = 'The colonoscope was introduced through the anus and advanced to the cecum.'
SNARE = 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
TATTOO = 'The site was tattooed: ink was injected into it at three spots.'
COL = 'Colonoscopy: ' + COURSE + ' ' + SNARE + ' ' + TATTOO + '\n'
IMPRESSION = ('Impression: Esophageal biopsies; distal esophagus dilated. Sigmoid polyp removed with a cold snare; '
              'site tattooed.\n')
TAIL = IMPRESSION + 'Plan: Await pathology.\n'
REPORT = HEAD + LINE + IND + EGD + COL + TAIL
N1 = 'N1: the paragraph states another time, place, agent or source'
P4 = 'P4: it follows a labelled paragraph that is not released'


def why(text):
    return [reason for _, reason in structure.decisions(text)]


def colonoscopy(body, line='Procedures: Colonoscopy with polypectomy\n', ind=IND,
                impression='Impression: Sigmoid polyp removed with a cold snare.\n'):
    """A one-family report: its procedure line, indications, one labelled colonoscopy paragraph, its impression."""
    return HEAD + line + ind + 'Colonoscopy: ' + COURSE + ' ' + body + '\n' + impression + 'Plan: Await pathology.\n'


class CorroboratedReleaseTests(SimpleTestCase):
    """The walked shape, paraphrased: both paragraphs held on the installed release (the upper one by its open-world
    sentence, the lower one by P4's cascade and its own "into it at three spots"), both released by corroboration."""

    def test_both_paragraphs_are_released_and_read_as_todays(self):
        self.assertEqual(why(REPORT), ['', ''])
        findings = {f.family: f for f in detect.route(REPORT, DAY).findings}
        self.assertEqual((findings['gi.egd'].status, findings['gi.colonoscopy'].status), ('performed', 'performed'))
        self.assertEqual([str(f.value) for f in findings['gi.colonoscopy'].facts if f.name == 'extent'], ['cecum'])

    def test_the_colonoscopy_polypectomy_is_ready(self):
        item = proposal(run(REPORT, corti(('45385', span(REPORT, SNARE)))), '45385')
        self.assertEqual((item.bucket, item.status), ('selected', 'ready'))

    def test_without_its_corroboration_each_paragraph_keeps_its_installed_reason(self):
        # the same report with a procedure line that names the families and lists no act: the installed reading
        bare = REPORT.replace(LINE, 'Procedures: Upper endoscopy; colonoscopy\n')
        self.assertEqual(why(bare), [N1, P4])
        no_summary = REPORT.replace(IMPRESSION, 'Impression: See above.\n')
        self.assertEqual(why(no_summary), [N1, P4])

    def test_the_services_reader_keeps_the_installed_parts(self):
        # u18d: a corroborated paragraph is no labelled report part of its family (its twin's "PROCEDURE: <L>" line opens
        # none): the services reader's parts are the installed reading's, inside the paragraphs and outside them
        self.assertTrue(all(p.corroborated for p in structure.released(REPORT)))
        self.assertEqual(structure.installed_released(REPORT), ())
        reports = [p.family for p in gi_services.parts(REPORT, service_date=DAY) if p.kind == 'report' and p.family]
        self.assertEqual(reports, [])
        self.assertEqual(gi_services.parts(REPORT, service_date=DAY), installed(lambda: gi_services.parts(REPORT,
                                                                                                          service_date=DAY)))

    def test_the_cascade_needs_the_next_paragraphs_own_corroboration(self):
        # the lower paragraph is clean, but its own acts are not declared: it is not lifted by the upper one's release,
        # and the upper one's release, ending at a held paragraph's label line (C5: its heading twin's section would run
        # over that paragraph), is withdrawn
        text = REPORT.replace('; colonoscopy with polypectomy', '; colonoscopy').replace(' ' + TATTOO, '')
        self.assertEqual(why(text), [N1, P4])

    def test_a_closed_reading_before_it_still_holds_the_cascade(self):
        text = REPORT.replace(WIRE, 'The scope was removed at the outside hospital.')
        self.assertEqual(why(text), [N1, P4])

    def test_an_installed_release_beside_a_corroborated_one_keeps_the_installed_reading(self):
        # the upper paragraph is clean (the installed release), the lower one a corroboration candidate (u18c2 released
        # it). u18d: the installed release's own label class - a report part of its family, its label read against its
        # second sentence - reads otherwise than its twin's heading, so the computed comparison withdraws the
        # corroboration and the document reads as installed
        text = REPORT.replace(' ' + WIRE, '')
        self.assertEqual(why(text), ['', N1])
        self.assertIn('parts', structure.twin_differences(text))
        self.assertEqual(status(text, '45385', SNARE), installed(lambda: status(text, '45385', SNARE)))


class DeclarationTests(SimpleTestCase):
    """C1: the procedure line lists an act of the paragraph's family, in an item naming that family alone, as a plain
    statement."""

    BODY = SNARE + ' The colonoscope was withdrawn at the mouthpiece.'

    def test_a_listed_act_releases_and_a_family_alone_does_not(self):
        self.assertEqual(why(colonoscopy(self.BODY)), [''])
        self.assertEqual(why(colonoscopy(self.BODY, line='Procedures: Colonoscopy\n')), [N1])

    def test_the_item_of_another_family_lists_nothing_for_this_one(self):
        self.assertEqual(why(colonoscopy(self.BODY, line='Procedures: Upper endoscopy with polypectomy; colonoscopy\n')),
                         [N1])
        self.assertEqual(why(colonoscopy(self.BODY, line='Procedures: Upper endoscopy and colonoscopy with polypectomy\n')),
                         [N1])

    def test_a_doubted_item_lists_nothing(self):
        for line in ('Procedures: Colonoscopy with attempted polypectomy\n', 'Procedures: Colonoscopy without polypectomy\n',
                     'Procedures: Colonoscopy with planned polypectomy\n'):
            with self.subTest(line):
                self.assertEqual(why(colonoscopy(self.BODY, line=line)), [N1])

    def test_an_item_after_the_familys_continues_it(self):
        self.assertEqual(why(colonoscopy(self.BODY, line='Procedures: Colonoscopy, cold snare polypectomy\n')), [''])


class SummaryTests(SimpleTestCase):
    """C2: an impression or assessment statement bound to the family restates the listed act as a plain statement."""

    BODY = SNARE + ' The colonoscope was withdrawn at the mouthpiece.'

    def test_a_restating_impression_or_assessment_releases(self):
        for impression in ('Impression: Sigmoid polyp removed with a cold snare.\n',
                           'Assessment: Cold snare polypectomy in the sigmoid colon.\n',
                           'Impression: Polyp removed with a snare.\n'):  # one family declared: a siteless one is its
            with self.subTest(impression):
                self.assertEqual(why(colonoscopy(self.BODY, impression=impression)), [''])

    def test_a_summary_that_does_not_restate_the_act_or_doubts_it_holds(self):
        for impression in ('Impression: Sigmoid polyp removed.\n',  # no act kind restated
                           'Impression: Polyp removed by snare.\n',  # 'by': N1's own agent reading doubts it
                           'Impression: No polyp was removed with a cold snare today.\n',
                           'Impression: Sigmoid polyp to be removed with a cold snare at a later date.\n',
                           'Impression: Cold snare polypectomy of the sigmoid polyp was unsuccessful.\n',
                           'Impression: History of a sigmoid polyp removed with a cold snare.\n',
                           'Impression: Sigmoid polyp removed with a cold snare at the army base.\n',
                           'Plan: Sigmoid polyp removed with a cold snare.\n'):  # a plan is no summary of today's
            with self.subTest(impression):
                self.assertEqual(why(colonoscopy(self.BODY, impression=impression)), [N1])

    def test_a_statement_about_another_familys_site_restates_nothing_for_this_one(self):
        self.assertEqual(why(colonoscopy(self.BODY, impression='Impression: Gastric polyp removed with a cold snare.\n')),
                         [N1])


class CoverageTests(SimpleTestCase):
    """C3: every act declared; each sentence's own closed reading; an open-world adjunct only in a sentence that states
    today's procedure content; the corroborated act stated once in an undoubted sentence."""

    def test_an_act_the_report_does_not_declare_holds(self):
        body = SNARE + ' Biopsies were taken from the rectum at the mouthpiece.'
        self.assertEqual(why(colonoscopy(body)), [N1])
        declared = colonoscopy(body, line='Procedures: Colonoscopy with cold snare polypectomy and biopsies\n',
                               impression='Impression: Sigmoid polyp removed with a cold snare; rectal biopsies.\n')
        self.assertEqual(why(declared), [''])

    def test_a_sentence_that_says_nothing_of_the_procedure_cannot_carry_the_adjunct(self):
        for sentence in ('Everything was done on the cruise ship.', 'Both were done at the army base.',
                         'What follows was done on the cruise ship.', 'The depth mark was read at the mouthpiece.'):
            with self.subTest(sentence):
                self.assertEqual(why(colonoscopy(SNARE + ' ' + sentence)), [N1])

    def test_the_corroborated_act_needs_an_undoubted_statement_of_its_own(self):
        # the refuted variants' single-act shapes, with the act declared and restated: the only statement of the act
        # carries the adjunct, so nothing the report states is undoubted in the paragraph itself
        for adjunct in ('at the army base', 'on the cruise ship', 'within the prison walls', 'on her home ward',
                        'at the VA', 'in the army surgical unit'):
            with self.subTest(adjunct):
                self.assertEqual(why(colonoscopy('A 6 mm polyp in the sigmoid colon was removed with a cold snare '
                                                 + adjunct + '.')), [N1])
        for adjunct in ('at the time', 'on that trip', 'at that point', 'at the VA'):
            with self.subTest(adjunct):
                self.assertEqual(why(colonoscopy('There was a 6 mm polyp in the sigmoid colon ' + adjunct + ', and it '
                                                 'was removed with a cold snare.')), [N1])

    def test_each_sentence_reads_its_own_time_words(self):
        # the whole paragraph's one future word ("Surveillance") exempts every time unit in it; read sentence by
        # sentence, "Some months back" holds
        body = SNARE + ' Some months back a clip was placed at the mouthpiece. Surveillance in 3 years.'
        self.assertEqual(why(colonoscopy(body, line='Procedures: Colonoscopy with polypectomy and clip placement\n',
                                         impression='Impression: Sigmoid polyp removed with a cold snare; clip placed '
                                                    'in the sigmoid colon.\n')), [N1])

    def test_a_denied_act_is_no_act_stated(self):
        body = SNARE + ' The scar was flat, and it was not sampled. The colonoscope was withdrawn at the mouthpiece.'
        self.assertEqual(why(colonoscopy(body)), [''])

    def test_the_paragraphs_own_statement_of_the_act_is_a_plain_one(self):
        # the procedure line lists the polypectomy and the impression restates it, but the paragraph only denies, fails,
        # plans, hedges or names it: three statements never agree, and the installed reading stands
        for sentence in ('No polyp was removed with a cold snare.',
                         'The sigmoid polyp was not removed with a cold snare.',
                         'Cold snare polypectomy of the sigmoid polyp was attempted but failed.',
                         'We were unable to remove the sigmoid polyp with a cold snare.',
                         'The sigmoid polyp was possibly removed with a cold snare.',
                         'A cold snare was opened, and the sigmoid polyp was left in place.',
                         'The cold snare polypectomy scar in the sigmoid colon was clean.'):
            with self.subTest(sentence):
                self.assertEqual(why(colonoscopy(sentence + ' The colonoscope was withdrawn at the mouthpiece.')), [N1])

    def test_the_open_world_sentence_doubts_nothing_else(self):
        # the corroboration answers the open-world doubt only: a history, negation or hedge word beside it still holds
        for sentence in ('A clip was placed at the mouthpiece, where the polyp had been removed.',
                         'The colonoscope was withdrawn at the mouthpiece; no polyp was removed there.',
                         'The colonoscope was possibly withdrawn at the mouthpiece.'):
            with self.subTest(sentence):
                self.assertEqual(why(colonoscopy(SNARE + ' ' + sentence,
                                                 line='Procedures: Colonoscopy with polypectomy and clip placement\n',
                                                 impression='Impression: Sigmoid polyp removed with a cold snare; clip '
                                                            'placed in the sigmoid colon.\n')), [N1])


class ClosedReadingTests(SimpleTestCase):
    """Every closed reading of N1, N2, N3 and P1-P3 holds as installed, corroborated or not."""

    def test_the_closed_signals_still_hold(self):
        for sentence in ('The colonoscope was withdrawn by a colon specialist.',
                         'The colonoscope was withdrawn at the outside hospital.',
                         'The colonoscope was withdrawn in 2019.', 'The colonoscope was withdrawn at Mercy.',
                         'The colonoscope was withdrawn, as she recalls.', 'The colonoscope was withdrawn last year.'):
            with self.subTest(sentence):
                self.assertEqual(why(colonoscopy(SNARE + ' ' + sentence)), [N1])

    def test_an_undated_other_occasion_before_the_paragraph_holds(self):
        text = colonoscopy(SNARE + ' The colonoscope was withdrawn at the mouthpiece.',
                           ind='History: She had a colonoscopy with polypectomy at the mouthpiece clinic.\n' + IND)
        self.assertNotEqual(why(text), [''])

    def test_n2_and_n3_still_hold(self):
        body = SNARE + ' The colonoscope was withdrawn at the mouthpiece.'
        self.assertTrue(why(colonoscopy(body, ind='Indications: Her last colonoscopy is copied below.\n'))[0]
                        .startswith('N1'))
        later = colonoscopy(body, impression='Impression: Sigmoid polyp removed with a cold snare.\n'
                                             'Note: this colonoscopy was performed in 2019.\n')
        self.assertTrue(why(later)[0].startswith('N1'))

    def test_open_world_set_aside_reads_nothing_else(self):
        sentence = 'A polyp was removed at the army base while she was on the cruise.'
        self.assertTrue(structure._signals(sentence, 0, len(sentence), narrative=True))
        self.assertFalse(structure._signals(sentence, 0, len(sentence), narrative=True, open_world=False))
        for closed in ('A polyp was removed at the outside hospital.', 'A polyp was removed in 2019.',
                       'A polyp was removed by Dr. Synthetic.', 'A polyp was removed at Mercy.',
                       'A polyp was removed, as she recalls.', 'A polyp was removed during her previous admission.'):
            with self.subTest(closed):
                self.assertTrue(structure._signals(closed, 0, len(closed), narrative=True, open_world=False))


class GuardTests(SimpleTestCase):
    """What the release never does: take down an installed release (the tract rule), or release a paragraph whose
    section keeps another one held after it (C5) or before it (P4)."""

    def test_a_tract_misfit_returns_the_installed_decisions(self):
        text = colonoscopy(SNARE + ' The colonoscope was withdrawn at the mouthpiece. The gastric antrum was normal.')
        self.assertEqual(why(text), [N1])

    def test_the_cost_is_linear_in_the_paragraph(self):
        unit = SNARE + ' The colonoscope was withdrawn at the mouthpiece. '

        def elapsed(n):
            text = colonoscopy(unit * n)
            _clear()
            started = time.perf_counter()
            structure.decisions(text)
            return time.perf_counter() - started
        small, large = elapsed(400), elapsed(800)
        self.assertLess(large, max(3 * small, 0.5))
        self.assertLess(large, 8.0)


# --- u18c cycle 2 (the structure round, 2026-11-08): the repairs of the cycle-1 refutation, pinned in paraphrase ----------
OW = 'The colonoscope was withdrawn at the mouthpiece.'
SIB_BIOPSY = 'Cold forceps biopsies were obtained from the gastric body.'
SIB_DILATION = 'A through-the-scope balloon was inflated to 18 mm across the distal esophageal ring.'
SIB = 'The gastroscope was passed through the mouth to the second portion of the duodenum. ' + SIB_BIOPSY + ' ' + SIB_DILATION


def sibling_report(sibling, impression='Impression: The second portion of the duodenum was normal. Sigmoid polyp removed '
                                       'with a cold snare.\n'):
    """Two families in one frozen Indications section: the upper narrative written as no candidate (``sibling``), then
    the corroborated colonoscopy paragraph."""
    return (HEAD + 'Procedures: Upper endoscopy with biopsy and dilation; colonoscopy with polypectomy\n'
            + 'Indications: Dysphagia; anemia.\n' + sibling + '\n' + 'Colonoscopy: ' + COURSE + ' ' + SNARE + ' ' + OW
            + '\n' + impression + 'Plan: Await pathology.\n')


def status(text, code, phrase):
    item = proposal(run(text, corti((code, span(text, phrase)))), code)
    return item.status, sorted(c.id for c in item.checks if c.status not in ('pass', 'not_applicable', 'not_verified',
                                                                             'info'))


def _clear():
    for f in (structure._installed_state, structure._guarded_decisions, structure._released, structure._clinical_layout,
              structure._reader_layout):
        f.cache_clear()


def installed(read):
    """``read()`` with the corroborated release switched off (no paragraph corroborated): the installed reading."""
    from unittest import mock
    _clear()
    try:
        with mock.patch.object(structure, '_corroborated', lambda *args: False):
            return read()
    finally:
        _clear()


def heading_twin(text):
    """The text with each released paragraph's inline label "<L>: " written "PROCEDURE: <L>" on a line of its own."""
    for p in sorted(structure.released(text), key=lambda p: -p.label.start):
        end = p.label.end
        while end < len(text) and text[end] in ' \t':
            end += 1
        text = text[:p.label.start] + 'PROCEDURE: ' + text[p.label.start:p.label.end - 1] + '\n' + text[end:]
    return text


class PartsConstructionTests(SimpleTestCase):
    """The cycle-1 REGRESS lens (findings 1, 2 and 4): a corroborated release had made services._labelled_parts read
    every other physician line of its frozen Indications section as the indication's, so acts outside the paragraph lost
    their reading (a READY lost; a false evidence.support warning). By construction now: that reading is made on behalf
    of an INSTALLED release only, and a corroborated paragraph (LabelledParagraph.corroborated) changes the kind of no
    part outside itself. Pinned against the installed reading of the same text (outside the paragraph) and against the
    heading twin (inside it)."""

    def test_a_sibling_narrative_written_as_no_candidate_keeps_its_acts(self):
        for label in ('UPPER ENDOSCOPY WITH BIOPSY AND DILATION: ', ''):  # a label that is no service name only; none
            with self.subTest(label=label):
                text = sibling_report(label + SIB)
                self.assertEqual(why(text), [''])
                for code, phrase in (('43239', SIB_BIOPSY), ('43249', SIB_DILATION)):
                    self.assertEqual(status(text, code, phrase), installed(lambda: status(text, code, phrase)))
                self.assertEqual(status(text, '45385', SNARE), status(heading_twin(text), '45385', SNARE))
                self.assertEqual(status(text, '45385', SNARE)[0], 'ready')
                self.assertTrue(structure.released(text)[0].corroborated)

    def test_no_part_outside_the_paragraph_changes_its_kind(self):
        # the parts outside the paragraph, with the corroborated release and with the installed reading, cut at the
        # paragraph's edges: the same kinds, families and roles
        text = sibling_report('UPPER ENDOSCOPY WITH BIOPSY AND DILATION: ' + SIB)
        paragraph = structure.released(text)[0]

        def outside():
            pieces = []
            for p in gi_services.parts(text, service_date=DAY):
                for a, b in ((p.start, min(p.end, paragraph.start)), (max(p.start, paragraph.end), p.end)):
                    if a >= b:
                        continue
                    if pieces and pieces[-1][1] == a and pieces[-1][2:] == (p.kind, p.family, p.role):
                        pieces[-1] = (pieces[-1][0], b) + pieces[-1][2:]
                    else:
                        pieces.append((a, b, p.kind, p.family, p.role))
            return pieces
        corroborated = outside()
        self.assertEqual(corroborated, installed(outside))
        sibling = text.index('UPPER ENDOSCOPY WITH')
        self.assertNotEqual([kind for a, b, kind, _, _ in corroborated if a <= sibling < b], ['indication'])
        self.assertTrue(paragraph.corroborated)

    def test_an_act_line_before_the_paragraph_keeps_its_reading(self):
        line = 'The rectal angioectasia was treated with argon plasma coagulation'
        text = (HEAD + 'Procedures: Colonoscopy with polypectomy\n' + IND + line + '.\nColonoscopy: ' + COURSE + ' '
                + SNARE + ' ' + OW + '\nImpression: Sigmoid polyp removed with a cold snare. The cecum was reached.\n'
                'Plan: Await pathology.\n')
        self.assertEqual(why(text), [''])
        self.assertEqual(status(text, '45388', line), installed(lambda: status(text, '45388', line)))
        self.assertEqual(status(text, '45388', line)[0], 'ready')
        self.assertEqual(status(text, '45385', SNARE), status(heading_twin(text), '45385', SNARE))

    def test_a_restated_sibling_act_draws_no_false_support_warning(self):
        apc = 'Argon plasma coagulation was applied to the gastric antral vascular ectasia'
        text = (HEAD + 'Procedures: Upper endoscopy with APC; colonoscopy with polypectomy\n' + IND
                + 'UPPER ENDOSCOPY WITH ARGON PLASMA COAGULATION: The gastroscope was passed through the mouth to the second '
                'portion of the duodenum. ' + apc + '.\nColonoscopy: ' + COURSE + ' ' + SNARE + ' ' + OW + '\n'
                'Impression: The second portion of the duodenum was normal. Gastric antral vascular ectasia treated with '
                'argon plasma coagulation. Sigmoid polyp removed with a cold snare.\nPlan: Await pathology.\n')
        self.assertEqual(why(text), [''])
        reading = status(text, '43270', apc)
        self.assertEqual(reading, installed(lambda: status(text, '43270', apc)))
        self.assertNotIn('evidence.support', reading[1])


class TwinSectionTests(SimpleTestCase):
    """C5: a corroborated paragraph's procedure section is exactly its heading twin's. A report field after it would lie
    inside the twin's procedure section and outside the paragraph (the cycle-1 REGRESS lens's F1 shapes; and, measured
    in this cycle, content after the field that the twin reads as today's procedure while the release would not)."""

    def test_a_report_field_after_the_paragraph_keeps_the_installed_reading(self):
        apc = 'an angioectasia in the rectum was treated with argon plasma coagulation'
        text = colonoscopy(SNARE + ' ' + OW + '\nRetroflexion: performed; ' + apc + '.')
        self.assertEqual(why(text), [N1])
        self.assertEqual(status(text, '45388', apc), installed(lambda: status(text, '45388', apc)))
        for trail in ('Withdrawal time: 9 minutes.\nThe procedure was aborted.',
                      'Withdrawal time: 9 minutes.\nThe examination was incomplete because of poor preparation.',
                      'Retroflexion: not performed.\nThe cecum was not reached.'):
            with self.subTest(trail):
                self.assertEqual(why(colonoscopy(SNARE + ' ' + OW + '\n' + trail)), [N1])

    def test_a_heading_or_the_end_of_the_text_after_it_releases(self):
        self.assertEqual(why(colonoscopy(SNARE + ' ' + OW)), [''])  # the impression's heading follows
        text = HEAD + 'Procedures: Colonoscopy with polypectomy\nImpression: Sigmoid polyp removed with a cold snare.\n' \
            + IND + 'Colonoscopy: ' + COURSE + ' ' + SNARE + ' ' + OW + '\n'
        self.assertEqual(why(text), [''])  # the end of the text

    def test_the_twin_section_is_computed_on_the_twin_itself(self):
        # the walked shape, paraphrased: both paragraphs' twin sections are the paragraphs themselves; were the lower
        # paragraph held (not written as a heading in the twin), the upper one's twin section would run over it
        text = REPORT
        lay = structure.gi_sections.layout(text)
        candidates = structure._candidates(text, lay)
        self.assertEqual(structure._twin_disagrees(text, candidates, ['corroborated', 'corroborated']), set())
        self.assertEqual(structure._twin_disagrees(text, candidates, ['corroborated', '']), {0})

    def test_a_paragraph_released_after_a_withdrawn_one_is_withdrawn(self):
        # the upper paragraph is corroborated, then withdrawn by its frame (it names a procedure with no released
        # paragraph of its own: P2's frames, as installed); the lower one, released through P4's cascade on it, follows
        # a held paragraph again and is withdrawn too (P4 read again after every withdrawal)
        def report(frame):
            return (HEAD + 'Procedures: Upper endoscopy with biopsy; colonoscopy with polypectomy\n' + IND
                    + 'Upper endoscopy: ' + frame + ' gastroscope was passed through the mouth to the second portion of '
                    'the duodenum. Cold forceps biopsies were obtained from the gastric antrum. The gastroscope was '
                    'withdrawn at the mouthpiece.\nColonoscopy: ' + COURSE + ' ' + SNARE + '\n'
                    'Impression: Gastric antral biopsies. Sigmoid polyp removed with a cold snare.\nPlan: Await pathology.\n')
        self.assertEqual(why(report('The')), ['', ''])
        self.assertEqual(why(report('After the flexible sigmoidoscopy, the')), [N1, P4])

    def test_p4_is_read_against_the_releases_that_remain(self):
        text = REPORT
        lay = structure.gi_sections.layout(text)
        candidates = structure._candidates(text, lay)
        self.assertEqual(len(candidates), 2)
        self.assertFalse(structure._p4_passes(text, lay, candidates, ['', 'corroborated'], 1))
        self.assertTrue(structure._p4_passes(text, lay, candidates, ['corroborated', 'corroborated'], 1))


class BoundTests(SimpleTestCase):
    """The cycle-1 REGRESS lens's cost finding: the work is one predicate search per clause (never per mention), and
    bounded: a paragraph or a document beyond its bound keeps the installed reading."""

    def test_a_long_paragraph_or_document_keeps_the_installed_reading(self):
        filler = 'The mucosa of the transverse colon was normal. '
        self.assertEqual(why(colonoscopy(SNARE + ' ' + filler * 100 + OW)), [''])
        self.assertEqual(why(colonoscopy(SNARE + ' ' + filler * 140 + OW)), [N1])  # beyond CORROBORATED_PARAGRAPH
        plan = 'Plan: ' + 'Await pathology and call with results. ' * 1100 + '\n'
        self.assertEqual(why(colonoscopy(SNARE + ' ' + OW)[:-len('Plan: Await pathology.\n')] + plan), [N1])

    def test_many_act_mentions_in_one_clause_cost_their_length_once(self):
        from unittest import mock

        def elapsed(n):
            body = ('Also ' + 'cold snare polypectomy of a 4 mm sessile polyp in the sigmoid colon, ' * n
                    + 'and a flat polyp in the rectum. ' + SNARE + ' ' + OW)
            text = colonoscopy(body)
            # the candidate generator's own cost: the computed twin is pinned by GuardCostTests
            with mock.patch.object(structure, 'CORROBORATED_PARAGRAPH', 10 ** 7), \
                    mock.patch.object(structure, 'CORROBORATED_DOCUMENT', 10 ** 7), \
                    mock.patch.object(structure, '_twin_parity', lambda text, candidate: True):
                _clear()
                started = time.perf_counter()
                self.assertEqual([w for _, w in structure.decisions(text)], [''])
                return time.perf_counter() - started
        small, large = elapsed(400), elapsed(800)
        self.assertLess(large, max(3 * small, 0.5))  # quadratic per-mention searches took about 4x per doubling
        _clear()


# --- u18d (the structure round, 2026-11-08): the computed heading twin -------------------------------------------------
# u18c2's four refuted HIGHs, paraphrased (other sites, other words): each read here at computed parity with its heading
# twin, or as installed where the twin differs. The twin is read on this tree with its installed decisions: it carries no
# label of a paragraph released here, so this tree reads it as the installed release does.
EGD_COURSE = 'The gastroscope was passed through the mouth to the second portion of the duodenum.'
BODY_BX = 'Cold forceps biopsies were taken from the gastric body.'
HOT = 'A 5 mm polyp in the descending colon was removed with a hot snare.'
TERMINAL = 'A food bolus was removed with a retrieval net in the ferry terminal.'


def two_family(egd, col, line='Procedures: Upper endoscopy with biopsy; colonoscopy with polypectomy\n',
               impression='Impression: Gastric body biopsies. Descending colon polyp removed with a hot snare.\n'):
    return (HEAD + line + 'Indications: Anemia; history of a colon polyp.\n' + 'Upper endoscopy: ' + egd + '\n'
            + 'Colonoscopy: ' + col + '\n' + impression + 'Plan: Await pathology.\n')


def corroborated(text):
    return [(p.corroborated, reason) for p, reason in structure.decisions(text)]


class TwinParityTests(SimpleTestCase):
    """What the corroborated release now reads: exactly its computed heading twin, or the installed reading."""

    def assert_as_twin(self, text, picks):
        twin = heading_twin(text)
        self.assertNotEqual(twin, text)
        for code, phrase in picks:
            with self.subTest(code=code):
                self.assertEqual(status(text, code, phrase), status(twin, code, phrase))

    def test_a_site_less_act_beside_another_family_binds_as_in_its_twin(self):
        # u18c2 release HIGHs 0-2: the label bound a site-less act to its family where the twin's line binds it to none
        # (a report declaring two families). Each act below is held as its twin holds it; the rest reads as the twin
        bolus = two_family(EGD_COURSE + ' ' + BODY_BX + ' ' + TERMINAL, COURSE + ' ' + HOT,
                           line='Procedures: Upper endoscopy with biopsy and foreign body removal; colonoscopy with '
                                'polypectomy\n')
        left = two_family(EGD_COURSE + ' ' + BODY_BX + ' The gastroscope was withdrawn while the patient lay prone.',
                          COURSE + ' A 9 mm polyp was seen in the descending colon. A hot snare was passed through the '
                          'channel, and the polyp was then left in place because she takes clopidogrel. The colonoscope '
                          'was withdrawn while the patient lay prone.',
                          impression='Impression: Gastric body biopsies. Descending colon polyp; polypectomy withheld '
                                     'because she takes clopidogrel.\n')
        stent = two_family(EGD_COURSE + ' The stent was reached and was patent. The gastroscope was withdrawn while the '
                           'patient lay prone.', COURSE + ' ' + HOT,
                           line='Procedures: Upper endoscopy (stent check); colonoscopy with polypectomy\n',
                           impression='Impression: Esophageal stent patent. Descending colon polyp removed with a hot '
                                      'snare.\n')
        cases = ((bolus, '43247', TERMINAL[:-1], [('43239', BODY_BX), ('45385', HOT)]),
                 (left, '45385', 'A hot snare was passed through the channel', [('43239', BODY_BX)]),
                 (stent, '43266', 'The stent was reached', [('45385', HOT)]))
        for text, code, phrase, others in cases:
            with self.subTest(code=code):
                self.assertEqual(corroborated(text), [(True, ''), (True, '')])
                self.assertNotEqual(status(text, code, phrase)[0], 'ready')
                self.assert_as_twin(text, [(code, phrase)] + others)

    def test_one_labelled_paragraph_under_a_two_family_line_binds_as_its_twin(self):
        text = (HEAD + 'Procedures: Upper endoscopy; colonoscopy with biopsies and polypectomy\n' + IND
                + 'Colonoscopy: ' + COURSE + ' Biopsies were taken from the cecum. A 5 mm polyp was removed with a hot '
                'snare in the ferry terminal.\nImpression: Cecal biopsies. Normal upper endoscopy.\nPlan: Await pathology.\n')
        self.assertEqual(corroborated(text), [(True, '')])
        snare = 'A 5 mm polyp was removed with a hot snare in the ferry terminal'
        self.assertNotEqual(status(text, '45385', snare)[0], 'ready')
        self.assertEqual(status(text, '45380', 'Biopsies were taken from the cecum')[0], 'ready')
        self.assert_as_twin(text, [('45385', snare), ('45380', 'Biopsies were taken from the cecum')])

    def test_the_label_is_read_against_its_first_sentence_as_its_twin(self):
        # u18c2 regress HIGH 0: routing read a released label against its paragraph's second sentence ("Ileal intubation
        # was not attempted."), spread the doubt to the procedure line, and the impression's polypectomy lost READY.
        # The label's words are now a sentence of their own (structure._heading_split), as the twin's heading line is
        for doubt in ('Ileal intubation was not attempted.', 'Retroflexion in the rectum was not possible.'):
            with self.subTest(doubt):
                text = colonoscopy(doubt + ' ' + HOT + ' The colonoscope was withdrawn at the mouthpiece.',
                                   impression='Impression: Descending colon polyp removed with a hot snare. The cecum '
                                              'was reached.\n')
                self.assertEqual(corroborated(text), [(True, '')])
                findings = {f.family: f.status for f in detect.route(text, DAY).findings}
                self.assertEqual(findings['gi.colonoscopy'], 'performed')
                cited = 'Descending colon polyp removed with a hot snare'
                self.assertEqual(status(text, '45385', cited)[0], 'ready')
                self.assert_as_twin(text, [('45385', cited), ('45385', HOT)])

    def test_the_walked_shape_reads_as_its_twin(self):
        # the walked member, paraphrased (REPORT): both paragraphs corroborated, every compared fact equal
        self.assertEqual(structure.twin_differences(REPORT), ())
        self.assertEqual(corroborated(REPORT), [(True, ''), (True, '')])
        self.assertEqual(status(REPORT, '45385', SNARE)[0], 'ready')
        self.assert_as_twin(REPORT, [('45385', SNARE), ('43239', BIOPSY), ('45381', TATTOO), ('43248', DILATION)])

    def test_a_code_citing_only_a_label_reads_as_its_twin(self):
        # a label's own words are compared like every other characters: the services reader reads a corroborated label
        # as it reads the twin's "PROCEDURE: <label>" line (an EGD code citing only "Colonoscopy" is held, as there)
        twin = heading_twin(REPORT)
        for code in ('43239', '45378', '45385'):
            for label in ('Upper endoscopy', 'Colonoscopy'):
                with self.subTest(code=code, label=label):
                    at = REPORT.index(label + ': ')
                    there = twin.index('PROCEDURE: ' + label) + len('PROCEDURE: ')
                    mine = proposal(run(REPORT, corti((code, EvidenceSpan(0, at, at + len(label), label, True)))), code)
                    theirs = proposal(run(twin, corti((code, EvidenceSpan(0, there, there + len(label), label, True)))),
                                      code)
                    self.assertEqual((mine.status, sorted(c.id for c in mine.checks if c.status not in QUIET)),
                                     (theirs.status, sorted(c.id for c in theirs.checks if c.status not in QUIET)))


QUIET = ('pass', 'not_applicable', 'not_verified', 'info')


class ComparisonTests(SimpleTestCase):
    """The computed comparison is the guard: any fact the twin reads otherwise withdraws every corroborated release of the
    document, and it reads as installed. Each structural choice is pinned by removing it: the comparison then sees the
    difference it removed, and withdraws."""

    def test_an_installed_release_beside_a_corroborated_one_keeps_the_installed_reading(self):
        text = two_family(EGD_COURSE + ' ' + BODY_BX, COURSE + ' ' + HOT + ' The colonoscope was withdrawn while the '
                          'patient lay prone.')
        self.assertEqual(corroborated(text), [(False, ''), (False, N1)])
        self.assertTrue({'parts', 'services'} <= set(structure.twin_differences(text)))
        self.assertEqual(status(text, '45385', HOT), installed(lambda: status(text, '45385', HOT)))

    def test_without_the_heading_split_routing_differs_and_withdraws(self):
        from unittest import mock
        text = colonoscopy('Ileal intubation was not attempted. ' + HOT + ' The colonoscope was withdrawn at the '
                           'mouthpiece.', impression='Impression: Descending colon polyp removed with a hot snare.\n')
        _clear()
        try:
            with mock.patch.object(structure, '_heading_split', lambda text, spans, paragraphs: spans):
                self.assertIn('routing', structure.twin_differences(text))
                self.assertEqual(why(text), [N1])
        finally:
            _clear()
        self.assertEqual(why(text), [''])

    def test_with_a_labelled_part_the_services_binding_differs_and_withdraws(self):
        # u18c2's construction (a corroborated paragraph as a report part of its family) bound the site-less act
        from unittest import mock
        text = two_family(EGD_COURSE + ' ' + BODY_BX + ' ' + TERMINAL, COURSE + ' ' + HOT,
                          line='Procedures: Upper endoscopy with biopsy and foreign body removal; colonoscopy with '
                               'polypectomy\n')
        installed_only = structure.installed_released

        def labelled(text):  # every released paragraph of the guard's reading a labelled part, as u18c2 made it
            if isinstance(text, structure._Reading):
                return tuple(p for p, reason in text.carried if not reason)
            return installed_only(text)
        _clear()
        try:
            with mock.patch.object(structure, 'installed_released', labelled):
                differences = set(structure.twin_differences(text))
                self.assertTrue({'services', 'parts'} & differences, differences)
                self.assertEqual(why(text), [N1, P4])
        finally:
            _clear()
        self.assertEqual(corroborated(text), [(True, ''), (True, '')])

    def test_without_the_label_read_as_the_twins_line_services_differ_and_withdraw(self):
        from unittest import mock
        _clear()
        try:
            with mock.patch.object(gi_services, '_corroborated_labels', lambda source: ()):
                self.assertTrue({'services', 'span-readings'} & set(structure.twin_differences(REPORT)))
                self.assertEqual(why(REPORT), [N1, P4])
        finally:
            _clear()

    def test_a_reading_the_guard_cannot_complete_withdraws(self):
        from unittest import mock

        def broken(*args, **kwargs):
            raise RuntimeError('a reader failed')
        _clear()
        try:
            with mock.patch.object(gi_services, 'build', broken):
                self.assertEqual(why(REPORT), [N1, P4])
        finally:
            _clear()

    def test_a_plain_text_read_while_the_guard_reads_withdraws(self):
        # a reader that asks for another text's paragraphs (here: a copy of the document) while the guard reads: the
        # guard cannot tell which release that text reads in the real reading, so it fails closed
        from unittest import mock
        original = gi_services.passage_readings

        def copying(text, *args, **kwargs):
            structure.released(''.join(text))
            return original(text, *args, **kwargs)
        _clear()
        try:
            with mock.patch.object(gi_services, 'passage_readings', copying):
                self.assertEqual(why(REPORT), [N1, P4])
        finally:
            _clear()
        self.assertEqual(why(REPORT), ['', ''])

    def test_the_heading_quote_is_the_only_cue_word_set_aside(self):
        quoted = (' (Colonoscopy)',)
        self.assertEqual(structure._section_cue('section: procedure (Colonoscopy)', quoted), 'section: procedure')
        self.assertEqual(structure._section_cue('section: procedure (Procedures)', quoted),
                         'section: procedure (Procedures)')
        self.assertEqual(structure._section_cue('uncertain: section silent: the text after it qualifies it', quoted),
                         'uncertain: section silent: the text after it qualifies it')


class ReadingModeTests(SimpleTestCase):
    """The guard's two readings share no cache with the real one, never decide again, and the twin is read once."""

    def test_a_reading_is_equal_only_to_itself(self):
        carried = structure.decisions(REPORT)
        reading = structure._Reading(REPORT, carried)
        self.assertNotEqual(reading, REPORT)
        self.assertNotEqual(REPORT, reading)
        self.assertNotEqual(reading, structure._Reading(REPORT, carried))
        self.assertEqual(reading, reading)
        self.assertIs(structure.decisions(reading), carried)
        held = structure._installed_state(REPORT)[0]
        self.assertEqual(structure.decisions(structure._Reading(REPORT, held)), held)

    def test_u14s_direct_reach_twin_reads_the_installed_release(self):
        token = detect._MOTION_OFF.set(True)
        try:
            self.assertEqual(why(REPORT), [N1, P4])
        finally:
            detect._MOTION_OFF.reset(token)
        self.assertEqual(why(REPORT), ['', ''])

    def test_a_plain_text_asked_for_while_the_guard_reads_fails_it(self):
        refused = []
        token = structure._GUARDING.set(refused)
        try:
            with self.assertRaises(structure._GuardRead):
                structure.decisions(REPORT + ' ')
        finally:
            structure._GUARDING.reset(token)
        self.assertEqual(refused, [len(REPORT) + 1])

    def test_the_twin_is_read_once_per_document_and_never_inside_itself(self):
        from unittest import mock
        calls, nested = [], []
        original = structure._twin_parity

        def counted(text, candidate):
            if structure._GUARDING.get() is not None:
                nested.append(text)
            calls.append(text)
            return original(text, candidate)
        text = REPORT.replace('Plan: Await pathology.', 'Plan: Await pathology; repeat in 3 years.')
        _clear()
        try:
            with mock.patch.object(structure, '_twin_parity', counted):
                for _ in range(2):
                    structure.decisions(text)
                    detect.route(text, DAY)
                    status(text, '45385', SNARE)
        finally:
            _clear()
        self.assertEqual((len(calls), nested), (1, []))

    def test_the_layout_cuts_the_label_off_and_the_frozen_layout_keeps_it(self):
        label = REPORT.index('Colonoscopy: ')
        body = label + len('Colonoscopy: ')
        clinical = structure.clinical_layout(REPORT)
        self.assertIn((label, label + len('Colonoscopy:')), clinical.sentences)
        self.assertTrue(any(s == body for s, _ in clinical.sentences))
        frozen = structure.gi_sections.layout(REPORT)
        self.assertFalse(any(s == body for s, _ in frozen.sentences))  # the request side's layout is untouched
        # an installed release keeps its sentences
        clean = colonoscopy(SNARE)
        self.assertEqual(why(clean), [''])
        self.assertFalse(structure.released(clean)[0].corroborated)
        self.assertEqual(structure.clinical_layout(clean).sentences, structure.gi_sections.layout(clean).sentences)


class GuardCostTests(SimpleTestCase):
    """The twin is read at most once per document with a corroborated candidate, within the corroborated release's bound;
    a longer document never reads it."""

    def test_a_document_beyond_the_bound_never_reads_the_twin(self):
        from unittest import mock

        def never(text, candidate):
            raise AssertionError('the twin was read')
        plan = 'Plan: ' + 'Await pathology and call with results. ' * 1100 + '\n'
        text = REPORT[:-len('Plan: Await pathology.\n')] + plan
        self.assertGreater(len(text), structure.CORROBORATED_DOCUMENT)
        with mock.patch.object(structure, '_twin_parity', never):
            _clear()
            self.assertEqual(why(text), [N1, P4])
        _clear()

    def test_the_guard_is_linear_in_the_document(self):
        def elapsed(n):
            text = REPORT[:-len('Plan: Await pathology.\n')] + 'Plan: ' + 'Await pathology and call. ' * n + '\n'
            _clear()
            started = time.perf_counter()
            self.assertEqual(why(text), ['', ''])
            return time.perf_counter() - started
        small, large = elapsed(300), elapsed(600)
        self.assertLess(large, max(3 * small, 1.0))
        self.assertLess(large, 8.0)
        _clear()

class GuardWorkBoundTests(SimpleTestCase):
    """Integration (2026-11-08; u18d's REGRESS lens, cost finding 0): where the released paragraphs meet more than
    GUARD_SPANS sentences and clauses, the guard does not run and the installed reading stands."""

    PAD = ' '.join(['The mucosa was normal.'] * 170)  # about 4,000 characters: inside CORROBORATED_PARAGRAPH

    def padded(self):
        text = REPORT.replace(COL, 'Colonoscopy: ' + COURSE + ' ' + SNARE + ' ' + TATTOO + ' ' + self.PAD + '\n')
        self.assertNotEqual(text, REPORT)
        return text

    def test_past_the_bound_the_twin_is_never_read_and_the_installed_reading_stands(self):
        from unittest import mock

        def never(text, candidate):
            raise AssertionError('the twin was read')
        text = self.padded()
        with mock.patch.object(structure, 'GUARD_SPANS', 10 ** 6):
            _clear()
            self.assertEqual(why(text), ['', ''])  # the candidate exists, and its twin reads as it does
        _clear()
        with mock.patch.object(structure, '_twin_parity', never):
            self.assertEqual(why(text), [N1, P4])
        _clear()

    def test_the_padded_paragraph_is_past_the_bound_and_inside_the_paragraph_bound(self):
        text = self.padded()
        installed, read = structure._installed_state(text)
        lay = read[0]
        start = text.index('Colonoscopy: ')
        end = text.index('\n', start) + 1
        self.assertLess(end - start, structure.CORROBORATED_PARAGRAPH)
        met = sum(1 for spans in (lay.sentences, lay.clauses) for s, e in spans if start < e and s < end)
        self.assertGreater(met, structure.GUARD_SPANS)

    def test_the_walked_shape_is_well_within_the_bound(self):
        _clear()
        self.assertEqual(why(REPORT), ['', ''])
        installed, read = structure._installed_state(REPORT)
        lay = read[0]
        regions = [(p.start, p.end) for p in structure.released(REPORT)]
        met = sum(1 for spans in (lay.sentences, lay.clauses) for s, e in spans
                  if any(rs < e and s < re_ for rs, re_ in regions))
        self.assertLess(met, structure.GUARD_SPANS // 2)
        _clear()
