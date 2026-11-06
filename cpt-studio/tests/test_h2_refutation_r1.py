"""Harness repair 2026-11-05: the refutation passes over the finished P-ADMIT diff and their repairs, pinned on both
paths - a Corti selection and an independent participant's first reading - with the controls that must stay READY.
Every input is a lens's own counterexample, verbatim. Real engine, no provider or database calls.

Round 1 (six lenses over 3907cd592) found that under D14 a reader gap leaving a false open act beside Corti's correct
code had been a conservative failure, and that P-ADMIT let a participant fill it READY; the gaps were repaired in the
shared readers. Round 2 (three lenses over e88afe58b) found the phrase-level repairs both escaped and over-reached, so
the rules that did not converge were dropped (the programme's two-cycle rule) and the rest narrowed; a dropped rule's
input is pinned here as a recorded residual of the readers, under the directive's equivalent standards: a
participant's code is READY only where Corti's selection of the same passages is (RecordedResidualTests). HARNESS.md,
"Refutation round 1 (2026-11-05)" and "Refutation round 2 (2026-11-05)"."""
from django.test import SimpleTestCase

from studio.validation import engine
from tests.test_harness_engine import code, corti, read, run, span

COLON = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy report (fictional)\n'
         'Date of service: 2026-10-14\nProcedure: Colonoscopy\n'
         'The colonoscope was advanced to the cecum and the examination was completed.\n')
EGD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nUpper endoscopy report (fictional)\n'
       'Date of service: 2026-10-14\nProcedure: Upper endoscopy\n'
       'The gastroscope was passed to the second portion of the duodenum.\n')
ERCP = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nERCP report (fictional)\n'
        'Date of service: 2026-10-14\nProcedure: ERCP\nThe duodenoscope was advanced to the major papilla.\n')
CECUM = 'The colonoscope was advanced to the cecum'
READY = ('selected', 'ready')
ALTERNATIVE = ('alternative', 'informational')


def outcome(result, which):
    return [(p.bucket, p.status) for p in result.proposals if p.code == which]


def both(text, which, quote, primary=()):
    """(Corti selecting ``which`` beside ``primary``, a participant's first reading proposing it beside ``primary``)."""
    selected = [(c, span(text, q)) for c, q in primary]
    by_corti = run(text, corti(*selected, (which, span(text, quote))))
    by_astra = run(text, corti(*selected), [read('astra', [code(text, which, quote)])])
    return outcome(by_corti, which), outcome(by_astra, which)


class EmrComponentsTests(SimpleTestCase):
    """multi-1: an EMR is a snare-based resection; its own snare is never a second removal (45385) charged beside it.
    Round 2 (over-4): only at the resection's lesion and site, or in its clause at one site."""
    FORMS = ('A 25 mm flat lesion in the ascending colon was resected by EMR with a hot snare after a saline lift.',
             'Endoscopic mucosal resection of a 20 mm sessile lesion in the cecum was performed using a hot snare.',
             'A 20 mm lesion in the cecum was lifted with saline and resected with a hot snare (EMR).',
             'Hot snare EMR of the 20 mm cecal lesion was performed.',
             'A 15 mm sessile polyp in the transverse colon was injected with saline and removed by EMR using a hot '
             'snare.',
             'A 15 mm sessile polyp in the transverse colon was removed by EMR. The polyp was resected with a hot snare '
             'in one piece.')

    def test_an_emrs_own_snare_is_never_ready(self):
        for line in self.FORMS:
            with self.subTest(line):
                text = COLON + line + '\n'
                first = line.split('. ')[0] + ('' if line.split('. ')[0].endswith('.') else '.') \
                    if '. ' in line else line
                by_corti, by_astra = both(text, '45385', line, primary=[('45390', first)])
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_two_participants_never_add_the_snare_beside_the_emr(self):
        # moved by the completion repair (owner directive 2026-11-06, item 3: equal eligibility; builder Q1): Fable's
        # explicit 45385 is read by the per-code path and is exactly what Corti's own selection of both codes on the line
        # is - held, its question asking whether a snare removal apart from the EMR was done - never READY beside the
        # EMR (it was listed as an alternative)
        line = self.FORMS[0]
        text = COLON + line + '\n'
        result = run(text, corti(), [read('astra', [code(text, '45390', line)]),
                                     read('fable', [code(text, '45385', line)])])
        by_corti = run(text, corti(('45390', span(text, line)), ('45385', span(text, line))))
        self.assertEqual(outcome(result, '45390'), [READY])
        self.assertEqual(outcome(result, '45385'), [('selected', 'needs_clarification')])
        self.assertEqual(outcome(result, '45385'), outcome(by_corti, '45385'))
        (snare,) = [p for p in result.proposals if p.code == '45385']
        self.assertIn('is part of another procedure documented with it', snare.clarifications[0].question)

    def test_a_snare_at_another_lesion_or_site_keeps_its_code(self):
        emr = 'A 25 mm flat lesion in the ascending colon was removed by endoscopic mucosal resection.'
        for text, snare, first in (
                (COLON + emr + '\nA separate 6 mm polyp in the sigmoid colon was removed with a cold snare.\n',
                 'A separate 6 mm polyp in the sigmoid colon was removed with a cold snare.', emr),
                # round 2, over-4: another sentence's polyp the reader had bound to the EMR's lesion; two sites in one
                # clause; two lesions in one clause
                (COLON + emr + '\nThe sigmoid polyp was removed with a cold snare.\n',
                 'The sigmoid polyp was removed with a cold snare.', emr),
                (COLON + 'Endoscopic mucosal resection was performed in the ascending colon, and cold snare polypectomy '
                 'was performed in the sigmoid colon.\n', 'Endoscopic mucosal resection was performed in the ascending '
                 'colon, and cold snare polypectomy was performed in the sigmoid colon.',
                 'Endoscopic mucosal resection was performed in the ascending colon, and cold snare polypectomy was '
                 'performed in the sigmoid colon.'),
                (COLON + 'EMR of a 20 mm cecal lesion and cold snare polypectomy of a 5 mm rectal polyp were performed.\n',
                 'EMR of a 20 mm cecal lesion and cold snare polypectomy of a 5 mm rectal polyp were performed.',
                 'EMR of a 20 mm cecal lesion and cold snare polypectomy of a 5 mm rectal polyp were performed.')):
            with self.subTest(snare):
                by_corti, by_astra = both(text, '45385', snare, primary=[('45390', first)])
                self.assertEqual(by_corti, [READY])
                self.assertEqual(by_astra, [READY])


class SecondLesionInOneSentenceTests(SimpleTestCase):
    """Refutation round 7 (L7-2): the reader binds two acts to one lesion whenever one sentence names two lesions at one
    site, so a second lesion's snare removal (or biopsy) had been bundled into the first lesion's EMR (or removal) and
    hidden from completeness. Acts read in separate clauses are one lesion's only at a lesion recorded alone and
    singular (reconcile._one_lesion); in doubt the act is its own, as at main."""
    LINES = ('A 25 mm lesion in the cecum was removed by EMR, and a 4 mm polyp in the cecum was removed with a cold snare.',
             'Two polyps were found in the ascending colon; one was removed by EMR, and the second was removed with a '
             'cold snare.',
             'Two sessile polyps in the transverse colon: the first was resected by EMR; the second was removed with a '
             'hot snare.')

    def test_a_second_lesions_snare_is_never_bundled_into_the_emr(self):
        for line in self.LINES:
            with self.subTest(line):
                text = COLON + line + '\n'
                result = run(text, corti(('45390', span(text, line))))
                self.assertNotEqual(result.completeness['state'], 'complete_pending_review')
                self.assertNotIn('snare', [b['act'] for b in result.completeness['bundled']])
                self.assertTrue(any('snare' in u['label'] for u in result.completeness['unresolved_items']))

    def test_a_second_lesions_biopsy_is_never_bundled_into_the_removal(self):
        line = 'A 25 mm lesion in the cecum was biopsied, and a 4 mm polyp in the cecum was removed with a cold snare.'
        text = COLON + line + '\n'
        result = run(text, corti(('45385', span(text, line))))
        self.assertNotIn('biopsy', [b['act'] for b in result.completeness['bundled']])
        self.assertTrue(any('biops' in u['label'] for u in result.completeness['unresolved_items']))


class BiopsyOfRemovedLesionTests(SimpleTestCase):
    """The biopsy of a recorded lesion then removed is part of the removal (round 1's multi-2 rule, LESION_SITED, was
    dropped in round 2: its unrecorded forms are RecordedResidualTests)."""

    def test_a_restatement_naming_its_site_is_the_lesion_it_restates(self):
        biopsy = 'A 10 mm polyp in the sigmoid colon was biopsied with cold forceps.'
        snare = 'Impression: a 10 mm sigmoid polyp was removed with a hot snare.'
        text = COLON + biopsy + '\n' + snare + '\n'
        by_corti, by_astra = both(text, '45380', biopsy, primary=[('45385', snare)])
        self.assertNotIn(READY, by_corti)
        self.assertNotIn(READY, by_astra)

    def test_a_lesion_only_observed_binds_no_act_beside_it(self):
        text = COLON + 'A 6 mm sigmoid polyp was seen.\nBiopsy: [X] Cold snare polypectomy of the 6 mm sigmoid polyp was ' \
            'performed.\n'
        line = 'Biopsy: [X] Cold snare polypectomy of the 6 mm sigmoid polyp was performed.'
        result = run(text, corti(('45385', span(text, line)), ('45380', span(text, 'Biopsy'))))
        self.assertEqual(outcome(result, '45385'), [READY])
        self.assertNotIn('part of another documented act',
                         ' '.join(c.detail for p in result.proposals if p.code == '45380' for c in p.checks))

    def test_a_biopsy_of_another_polyp_keeps_its_code(self):
        biopsy = 'A 7 mm polyp in the cecum was biopsied with cold forceps.'
        snare = 'A separate 9 mm sigmoid polyp was removed with a hot snare.'
        text = COLON + biopsy + '\n' + snare + '\n'
        by_corti, by_astra = both(text, '45380', biopsy, primary=[('45385', snare)])
        self.assertEqual(by_corti, [READY])
        self.assertEqual(by_astra, [READY])


class ProphylacticClipTests(SimpleTestCase):
    """multi-3, the owner's "no separate charges for prophylactic clipping": "hemostatic" names a device, never that
    bleeding was controlled. Not a prophylaxis word list (round 4b's R4c was refuted): no purpose word is read. Round 2:
    a stated bleeding object keeps the act (over-5), a negated control statement never switches the rule off (esc-9)."""
    EMR = 'A 25 mm flat lesion in the ascending colon was lifted with saline and removed by endoscopic mucosal resection.'

    def test_a_hemostatic_clip_named_alone_is_never_control_of_bleeding(self):
        for clip in ('Two hemostatic clips were placed prophylactically to close the resection defect.',
                     'Two hemostatic clips were placed at the resection site.',
                     'A hemostatic clip was deployed.',
                     'Two hemostatic clips were placed for prevention of bleeding, not for control of bleeding.'):
            with self.subTest(clip):
                text = COLON + self.EMR + '\n' + clip + '\n'
                by_corti, by_astra = both(text, '45382', clip, primary=[('45390', self.EMR)])
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_bleeding_control_stated_stays_ready(self):
        for head, which, clip, primary in (
                (COLON + self.EMR + '\n', '45382', 'Hemostasis was achieved with two hemostatic clips.', [('45390', self.EMR)]),
                (COLON + self.EMR + '\n', '45382', 'Hemostasis was achieved with two clips.', [('45390', self.EMR)]),
                (EGD, '43255', 'The bleeding ulcer in the gastric antrum was treated with two hemostatic clips.', []),
                (EGD, '43255', 'Hemostatic clips were applied to the actively bleeding vessel in the duodenal bulb.', [])):
            with self.subTest(clip):
                by_corti, by_astra = both(head + clip + '\n', which, clip, primary=primary)
                self.assertEqual(by_corti, [READY])
                self.assertEqual(by_astra, [READY])

    def test_control_the_inventory_reads_no_act_of_is_read_by_the_codes_own_passage(self):
        # the inventory reads no act ("controlled" and "stopped" are not act predicates; the same at main): Corti's
        # code stands on the routing-era reading of its own passage. Moved by the completion repair (owner directive
        # 2026-11-06, item 3: equal eligibility; builder Q1): a participant's explicit code is read by the same per-code
        # path, so it stands on the same reading - READY, as Corti's is (it was listed: it filled no open item)
        for clip in ('Active bleeding was controlled with two hemostatic clips.', 'Bleeding was stopped with two clips.'):
            with self.subTest(clip):
                text = COLON + self.EMR + '\n' + clip + '\n'
                by_corti, by_astra = both(text, '45382', clip, primary=[('45390', self.EMR)])
                self.assertEqual(by_corti, [READY])
                self.assertEqual(by_astra, by_corti)


class DifferentActsTests(SimpleTestCase):
    """multi-4: two codes compete only for one same act; an esophageal and a pyloric dilation are two acts."""
    D1 = 'The distal esophageal stricture was dilated with an 18 mm through-the-scope balloon.'
    D2 = 'A separate pyloric stricture was dilated with a 15 mm through-the-scope balloon.'

    def test_codes_for_two_different_acts_are_both_admitted(self):
        text = EGD + self.D1 + '\n' + self.D2 + '\n'
        result = run(text, corti(), [read('astra', [code(text, '43249', self.D1)]),
                                     read('fable', [code(text, '43245', self.D2)])])
        self.assertEqual(outcome(result, '43249'), [READY])
        self.assertEqual(outcome(result, '43245'), [READY])

    def test_codes_for_one_act_still_compete_and_say_so_truly(self):
        # harness repair 3 (P-ADMIT2; the owner's second message of 2026-11-05, interpretation (a)): the "neither is
        # added" rule is withdrawn - both codes reach review, each held by one question naming the other, no proposer
        # named and neither chosen
        text = EGD + self.D1 + '\n'
        result = run(text, corti(), [read('astra', [code(text, '43249', self.D1), code(text, '43245', self.D1)])])
        for which, other in (('43249', '43245'), ('43245', '43249')):
            (item,) = [p for p in result.proposals if p.code == which]
            self.assertEqual((item.bucket, item.status), ('selected', 'needs_clarification'))
            (hold,) = [c for c in item.checks if c.id == engine.COMPETING_CHECK]
            self.assertIn(other, hold.detail)
            self.assertNotIn('astra', hold.detail.lower())
            self.assertNotIn('participant', hold.detail.lower())


class NegationReleaseTests(SimpleTestCase):
    """neg-1, neg-3 and round 2's esc-3: beside another act's denial, the routing-era hold is released only where the
    code's own act's clause carries no negation marker of the closed class (engine.OWN_CLAUSE_DENIAL); "nothing" and the
    zero numeral are negative quantifiers (NEG_LEAD)."""
    LEAD = 'In the distal rectum, a 5 mm sessile polyp was seen; '

    def test_a_denied_biopsy_beside_another_denial_is_never_ready(self):
        for body in ('nothing was biopsied; it was not snared.', 'nothing was biopsied.',
                     # the zero numeral alone, with no other act's denial: no routing-era hold, NEG_LEAD decides
                     'zero biopsies were taken.', '0 biopsies were obtained.',
                     'zero biopsies were taken; it was not snared.', '0 biopsies were obtained; it was not snared.',
                     'the decision was made not to biopsy it; it was not snared.',
                     'biopsies were obtained from none of the polyps; it was not snared.',
                     'it was sampled with cold biopsy forceps, which yielded no tissue; it was not snared.',
                     # round 2, esc-3
                     'zero (0) biopsies were taken; it was not snared.', '0 (zero) biopsies were taken; it was not snared.',
                     'not a single biopsy was taken; it was not snared.',
                     'the decision was made against biopsy; it was not snared.',
                     'nothing was sent for biopsy; it was not snared.', 'biopsies taken: 0; it was not snared.',
                     'it was sampled with cold biopsy forceps, which yielded nothing; it was not snared.',
                     'it was sampled with cold biopsy forceps, which retrieved no tissue; it was not snared.',
                     'it was sampled with cold biopsy forceps, with no tissue obtained; it was not snared.',
                     # round 3, LENS-3: an act done elsewhere, historically or unsuccessfully, beside another's denial
                     'it was biopsied at the referring facility, showing a tubular adenoma; it was not snared.',
                     'cold forceps biopsies were taken from it elsewhere; it was not snared.'):
            with self.subTest(body):
                line = self.LEAD + body
                by_corti, by_astra = both(COLON + line + '\n', '45380', line)
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_genuine_acts_beside_a_denial_of_something_else_stay_ready(self):
        # round 2, over-1 to over-3: the dropped rules' wrongly denied inputs, and round 1's controls
        for head, which, line in (
                (COLON, '45380', 'Cold forceps biopsies were taken from the 5 mm rectal polyp; nothing else was sampled.'),
                (COLON, '45380', 'Nothing abnormal was seen in the rectum; cold forceps biopsies were taken from the '
                                 'rectal mucosa.'),
                (COLON, '45380', 'Cold forceps biopsies were taken from the rectal mucosa; the stool culture yielded no '
                                 'growth.'),
                (COLON, '45385', 'A 6 mm polyp in the sigmoid colon was removed with a cold snare, which produced no '
                                 'bleeding.'),
                (COLON, '45380', 'Cold forceps biopsies were taken from the rectal mucosa, yielding no significant '
                                 'bleeding.'),
                (EGD, '43249', 'The distal esophageal stricture was dilated with an 18 mm through-the-scope balloon, '
                               'producing no mucosal tear.'),
                (COLON, '45385', 'A 6 mm polyp in the sigmoid colon was removed with a cold snare, taking care not to '
                                 'snare the adjacent fold.'),
                (EGD, '43239', 'Four-quadrant biopsies were taken at no more than 2 cm intervals throughout the Barrett '
                               'segment.'),
                (EGD, '43239', 'Random biopsies were obtained from no fewer than six sites in the stomach.')):
            with self.subTest(line):
                by_corti, by_astra = both(head + line + '\n', which, line)
                self.assertEqual(by_corti, [READY])
                self.assertEqual(by_astra, [READY])


class TattooPlaceTests(SimpleTestCase):
    """neg-2: "marked" names a tattoo placed only as its instrument (round 2, over-8: anywhere in its instrument
    phrase), and a tattoo named as a place is no tattoo act."""

    def test_a_tattoo_named_as_a_place_or_a_label_is_never_ready(self):
        for line in ('The tattoo site in the ascending colon was marked with a clip and not resected.',
                     'The existing tattoo in the ascending colon was marked with a clip and not resected.',
                     'The tattooed scar in the ascending colon was marked with a clip and not resected.',
                     'The scar beside the tattoo in the ascending colon was marked with a clip and not resected.',
                     'Specimen jar A was marked "tattoo site" and not resected.',
                     'The lesion in the ascending colon was marked on the diagram as the tattoo location and not '
                     'resected.',
                     'The lesion in the ascending colon was marked with tattoo ink that was unavailable and not '
                     'resected.',
                     'The tattoo in the ascending colon was marked with a clip and not resected.',
                     'Specimen jar A was marked "tattoo" and not resected.',
                     'The lesion in the ascending colon was marked as tattoo-free and not resected.',
                     'A 5 mm polyp adjacent to the tattoo was removed with a cold snare.',
                     'The tattoo site was biopsied.',
                     # round 3, LENS-2: no tattoo placed today, the marker outside the package's shape
                     'The lesion in the ascending colon was marked with a clip since the tattoo ink ran out and not '
                     'resected.',
                     'The lesion in the ascending colon was marked with a photo of the tattoo and not resected.',
                     'The lesion in the ascending colon was marked with a clip since tattoo ink had run out and not '
                     'resected.',
                     'The lesion in the ascending colon was marked with India ink at the referring facility and not '
                     'resected.',
                     'The lesion in the ascending colon was marked with a label reading tattoo and not resected.'):
            with self.subTest(line):
                by_corti, by_astra = both(COLON + line + '\n', '45381', line)
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_a_tattoo_placed_stays_ready(self):
        # round 6: the package's coordinated "marked with tattoo ... and not resected" is dropped and reads as main
        # reads it, held (PackageSentenceTests); the participle forms below are main's own reading
        for line in ('The lesion in the ascending colon was tattooed and not resected.',
                     'A tattoo was placed distal to the lesion in the ascending colon.',
                     'India ink was injected adjacent to the polyp in the ascending colon.'):
            with self.subTest(line):
                by_corti, by_astra = both(COLON + line + '\n', '45381', line)
                self.assertEqual(by_corti, [READY])
                self.assertEqual(by_astra, [READY])


class MarkedShapeTests(SimpleTestCase):
    """Round 3: the repair package's coordinated "marked ... and not resected" is read at the package's own shape only
    (the tattoo heading the instrument phrase, nothing but its purpose before the denial). Round 2's over-8 forms fall
    outside it and read as main reads them: held, never ready - a hold on the safe side, recorded."""

    def test_a_marker_outside_the_packages_shape_is_held(self):
        for line in ('The lesion in the ascending colon was marked with 3 mL of India ink and not resected.',
                     'The lesion in the ascending colon was marked with three injections of tattoo ink and not resected.',
                     'The lesion in the ascending colon was marked distally with tattoo ink and not resected.'):
            with self.subTest(line):
                by_corti, by_astra = both(COLON + line + '\n', '45381', line)
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_the_tattoo_with_its_future_purpose_and_the_resections_denial_reads_as_its_participle_form(self):
        # harness repair 3's F-NEG S gives the denial to the resection; its F-TIME R is dropped (refutation cycle 2, two
        # cycles refuted). Completion repair (2026-11-06, U5; builder A) closes the recorded residual (a false exclusion)
        # by another mechanism: a purpose phrase's "future" never dates the act its clause's main predicate states done
        # (studio.gi.purpose), so both forms read as the completed marking today they are - still equal (D1). Builder
        # Q1's equal eligibility holds with it: the participant's explicit code reads as Corti's (both READY)
        line = 'The lesion in the ascending colon was marked with submucosal tattoo for future localization and not resected.'
        plain = 'The transverse colon lesion was tattooed for future localization.'
        self.assertEqual(both(COLON + line + '\n', '45381', line), both(COLON + plain + '\n', '45381', plain))
        self.assertEqual(both(COLON + line + '\n', '45381', line), ([READY], [READY]))


class MarkedAdverbTests(SimpleTestCase):
    """Round 4: round 3's restored "marked" took any word before a bare "marked", so a tattoo placed at another time
    read as today's 45381, READY on both paths where main holds it. Reproduced on the merge commit 92b24d3b9f5b."""

    def test_a_marking_dated_to_another_time_is_never_ready(self):
        for line in ('The lesion in the ascending colon was already marked with tattoo and not resected.',
                     'The lesion in the ascending colon was originally marked with tattoo and not resected.',
                     'The lesion in the ascending colon was initially marked with tattoo and not resected.',
                     'The lesion in the ascending colon was once marked with tattoo and not resected.',
                     'Ascending colon lesion already marked with tattoo and not resected.',
                     'Ascending colon lesion originally marked with tattoo and not resected.',
                     'The lesion in the ascending colon was earlier marked with tattoo and not resected.',
                     'The lesion in the ascending colon was formerly marked with tattoo and not resected.',
                     'The lesion in the ascending colon was previously marked with tattoo and not resected.',
                     # an adverb of manner: held on the safe side
                     'The lesion in the ascending colon was carefully marked with tattoo and not resected.'):
            for primary in ((), (('45378', CECUM),)):
                with self.subTest(line, primary=bool(primary)):
                    by_corti, by_astra = both(COLON + line + '\n', '45381', line, primary)
                    self.assertNotIn(READY, by_corti)
                    self.assertNotIn(READY, by_astra)

    def test_the_packages_own_forms_read_as_their_participle_form(self):
        # round 6 dropped the package's coordinated rule. Harness repair 3 (F-NEG S) gives the "not" to the resection
        # at the instrument shape only, so these read as "was tattooed and not resected" reads (READY); an adverb
        # before the participle stays outside it, held on the safe side, as at main
        for line in ('The lesion in the ascending colon was marked with tattoo and not resected.',
                     'Ascending colon lesion marked with tattoo and not resected.',
                     'Ascending colon polyp marked with India ink and not resected.'):
            with self.subTest(line):
                self.assertEqual(both(COLON + line + '\n', '45381', line), ([READY], [READY]))
        line = 'The lesion in the ascending colon was also marked with tattoo and not resected.'
        by_corti, by_astra = both(COLON + line + '\n', '45381', line)
        self.assertNotIn(READY, by_corti)
        self.assertNotIn(READY, by_astra)


class PackageSentenceTests(SimpleTestCase):
    """Round 4, lens A: the repair package's two releasing rules had been checked on a span, and the sentence around it
    said another time, place, provider, condition or doubt. Each now releases only inside one of the package's own
    whole sentences (PACKAGE_MARKED_SENTENCE, PACKAGE_PURPOSE_SENTENCE): never READY on the forms below, where main holds
    or excludes them, and READY on the package's own."""

    COORDINATED = (  # L4A-1
        'Prior to this procedure, the lesion in the ascending colon was marked with tattoo and not resected.',
        'Previously, the lesion in the ascending colon was marked with tattoo and not resected.',
        'At the referring facility, the lesion in the ascending colon was marked with tattoo and not resected.',
        'The lesion in the ascending colon was marked with tattoo and not resected at the referring facility.',
        'If the lesion in the ascending colon was marked with tattoo and not resected, surgery would follow.',
        'It is unknown whether the lesion in the ascending colon was marked with tattoo and not resected.',
        'The lesion in the ascending colon was marked with tattoo and not resected, but the tattoo was unsuccessful.',
        'Ascending colon lesion marked with tattoo and not resected before referral.',
        'Before referral, the lesion in the ascending colon was marked with tattoo and not resected.',
        'Elsewhere, the lesion in the ascending colon was marked with tattoo and not resected.',
        'Per outside report, the lesion in the ascending colon was marked with tattoo and not resected.',
        'The lesion in the ascending colon was marked with tattoo and not resected by Dr. Synthetic Surgeon.',
        'The lesion in the ascending colon was marked with tattoo and not resected (outside report).',
        'Referring endoscopist: ascending colon lesion marked with tattoo and not resected.',
        'The lesion in the ascending colon was marked with tattoo and not resected; the tattoo did not take.',
        'The lesion in the ascending colon was injected with India ink and not resected at the referring facility.',
        # round 5 (L5-1): a frame inside the engine's own sentence, past a stop the engine does not cut at
        'At the outside hosp. the lesion in the ascending colon was marked with tattoo and not resected.',
        'On the day before at 3 p.m. the lesion in the ascending colon was marked with tattoo and not resected.',
        'Last wk. the lesion in the ascending colon was marked with tattoo and not resected.',
        'The lesion in the ascending colon was marked with tattoo and not resected today. -- by the referring endoscopist.',
        'At the referring facility... the lesion in the ascending colon was marked with tattoo and not resected.',
        'Per Dr. Smith the lesion in the ascending colon was marked with tattoo and not resected.',
        'At the outside ctr. the lesion in the ascending colon was marked with tattoo and not resected.',
        'At the referring facility.\x0bthe lesion in the ascending colon was marked with tattoo and not resected.',
        'At the referring facility.\x0cthe lesion in the ascending colon was marked with tattoo and not resected.',
    )
    PURPOSE = (  # L4A-2
        'Ink not yet injected into the ascending colon for future localization.',
        'Ink never injected into the ascending colon for future localization.',
        'Tattoo ink needs to get injected into the ascending colon for future localization.',
        'India ink to get injected into the ascending colon for future localization at surgery.',
        'Tattoo ink could get injected into the ascending colon for future localization.',
        'At the referring facility, India ink was injected adjacent to the lesion in the ascending colon for future '
        'localization.',
        'If India ink was injected adjacent to the lesion in the ascending colon for future localization, surgery is '
        'easier.',
        'Saline not yet injected into the ascending colon for future localization.',
        'Ink has to get injected into the ascending colon for future localization.',
        'India ink got injected into the ascending colon for future localization at the referring hospital.',
        'Before this procedure, the lesion in the ascending colon was tattooed for future localization and not resected.',
        # round 5 (L5-1)
        'At the outside hosp. tattoo ink was injected into the transverse colon submucosa for future localization.',
        'Per Dr. Smith tattoo ink was injected into the transverse colon submucosa for future localization.',
    )

    def test_a_form_outside_the_packages_whole_sentence_is_never_ready(self):
        for line in self.COORDINATED + self.PURPOSE:
            for primary in ((), (('45378', CECUM),)):
                with self.subTest(line, primary=bool(primary)):
                    by_corti, by_astra = both(COLON + line + '\n', '45381', line, primary)
                    self.assertNotIn(READY, by_corti)
                    self.assertNotIn(READY, by_astra)

    def test_under_a_heading_the_package_sentence_reads_as_a_plain_act_sentence(self):
        # round 5: the sentence is the engine's own (_sentences), which ends a heading line that ends in a colon. What a
        # heading says is then another sentence's context, which no reader reads for a plain act sentence either: under
        # every heading the package's sentence reads exactly as the plain "India ink was injected ..." does, never
        # better (D1), and under the section headings the readers know it is held or excluded with it
        line = 'The lesion in the ascending colon was marked with tattoo and not resected.'
        plain = 'India ink was injected adjacent to the lesion in the ascending colon.'
        for heading in ('Outside report:', 'Referral letter:', 'Per outside endoscopist:', 'Prior to this procedure:',
                        'History:', 'Prior procedures:', 'Plan:', 'Impression:', 'Findings:'):
            with self.subTest(heading):
                package = both(COLON + heading + '\n' + line + '\n', '45381', line)
                as_plain = both(COLON + heading + '\n' + plain + '\n', '45381', plain)
                for got, base in zip(package, as_plain):
                    if READY in got:
                        self.assertIn(READY, base)
        for heading in ('History:', 'Prior procedures:'):
            with self.subTest(heading):
                for got in both(COLON + heading + '\n' + line + '\n', '45381', line):
                    self.assertNotIn(READY, got)

    def test_the_packages_own_sentences_read_as_their_plain_forms(self):
        # round 6 dropped both package rules (the whole-sentence form failed its second cycle, L6-1). Harness repair 3
        # reads the same sentences by two narrower rules through every other reading. F-NEG S stands: the coordinated
        # forms are READY as a completed marking today is. F-TIME R was refuted in two cycles and is dropped (HARNESS.md
        # "Harness repair 3, refutation cycle 2"): the purpose forms read as main reads them - Corti's code excluded,
        # never READY (a recorded residual, a false exclusion: the readers' U5). Moved by the completion repair (owner
        # directive 2026-11-06, item 3: equal eligibility; builder Q1): a participant's explicit code reads as Corti's
        # does, excluded with the passage and reinstatable, where it was listed
        for line in ('The lesion in the ascending colon was marked with tattoo and not resected.',
                     'The transverse colon lesion was marked with tattoo and not resected today.'):
            with self.subTest(line):
                self.assertEqual(both(COLON + line + '\n', '45381', line), ([READY], [READY]))
        # Completion repair (2026-11-06, U5; builder A): the purpose forms are completed markings today (the recorded
        # residual closed by studio.gi.purpose: the purpose's "future" is never the done act's time) - READY as the
        # coordinated forms above, never better
        for line in ('India ink was injected adjacent to the lesion in the ascending colon for future localization.',
                     'Tattoo ink was injected into the transverse colon submucosa for future localization.',
                     'Tattoo ink injected into the transverse colon submucosa for future localization.',
                     # L6-1 and L6-2
                     'The transverse colon lesion was tattooed for future localization.'):
            with self.subTest(line):
                self.assertEqual(both(COLON + line + '\n', '45381', line), ([READY], [READY]))
        # L6-1's bodies: never better than the participle form of the same sentence under the same heading (D1) -
        # held where it is held ("Indication:" over the line, no "today"), READY only where it is READY
        for body in ('Indication: Referred after an outside colonoscopy on 2026-09-01.\n'
                     'The transverse colon lesion was marked with tattoo and not resected.',
                     'Indication:\nThe transverse colon lesion was marked with tattoo and not resected today.',
                     'Indication:\nThe transverse colon lesion was marked with tattoo and not resected.'):
            with self.subTest(body):
                line = body.split('\n')[-1]
                plain = line.replace('marked with tattoo', 'tattooed')
                self.assertEqual(both(COLON + body + '\n', '45381', line),
                                 both(COLON + body.replace(line, plain) + '\n', '45381', plain))
        line = 'The transverse colon lesion was marked with tattoo and not resected.'
        for got in both(COLON + 'Indication:\n' + line + '\n', '45381', line):
            self.assertNotIn(READY, got)

    def test_88d9db32s_shapes_read_as_done(self):
        # the encounter's own shapes: the injection stated in the findings, and the impression's coordinated form
        # wrapped across a line ("... and\nnot resected today."). Round 6 had left the impression's denial on its tattoo,
        # a false conflict with the injection that held 45381. Harness repair 3's F-NEG S gives the denial to the
        # resection: no conflict, and 45381 is READY on both paths on the findings' injection. With F-TIME R dropped
        # (refutation cycle 2) the impression's own tattoo reads planned by its "future", which contradicts nothing
        body = ('To facilitate subsequent\nlocalization, sterile carbon-based tattoo ink was injected into the submucosa '
                'approximately 3 cm distal to this\ntransverse-colon abnormality, on the opposite wall.\nImpression\n'
                'Distal rectal mucosal\nabnormality biopsied. Separate transverse-colon lesion marked with submucosal '
                'tattoo for future localization and\nnot resected today.')
        quote = 'sterile carbon-based tattoo ink was injected into the submucosa'
        self.assertEqual(both(COLON + body + '\n', '45381', quote), ([READY], [READY]))
        from tests.test_advanced_gi_binding import colon, inventory
        inv = inventory(body)
        self.assertEqual(inv.conflicts, ())
        # Completion repair (2026-11-06, U5; builder A): the impression's marking "for future localization" is the
        # completed marking it restates, read performed by its own predicate (studio.gi.purpose), no longer planned -
        # so it merges into the findings' act (one act, both passages)
        tattoos = [a for a in colon(inv).acts if a.kind == 'tattoo']
        self.assertEqual([a.status for a in tattoos], ['performed'])
        self.assertTrue(any('marked with submucosal' in ev.text for ev in tattoos[0].evidence))


class ExcisedTests(SimpleTestCase):
    """Rounds 4 and 5 (L4B-2, L5-2): the package's patch had made "excised" a bare act participle that no not-done list
    of the readers or of routing reads, so its denials and failures read as a removal done. It failed two cycles and is
    dropped: the bare list is main's again, and these read as main reads them."""

    def test_a_bare_denied_excision_is_never_ready(self):
        # round 5 (L5-2): and the not-done frames of "excised", now that the package's bare participle is dropped
        for head, which, line, primary in (
                (COLON, '45385', 'Sigmoid polyp not excised with hot snare.', (('45378', CECUM),)),
                (COLON, '45385', 'Sigmoid polyp never excised with hot snare.', (('45378', CECUM),)),
                (COLON, '45380', 'Sigmoid polyp not excised with cold biopsy forceps.', (('45378', CECUM),)),
                (COLON, '45390', 'Transverse colon lesion not excised by EMR.', (('45378', CECUM),)),
                (COLON, '45385', 'Sigmoid polyp was unable to be excised with hot snare.', (('45378', CECUM),)),
                (COLON, '45380', 'Sigmoid polyp not able to be excised with cold biopsy forceps.', (('45378', CECUM),)),
                (COLON, '45390', 'Transverse colon lesion failed to be excised with endoscopic mucosal resection.',
                 (('45378', CECUM),)),
                (EGD, '43251', 'Gastric polyp not to be excised with hot snare.', ()),
                (COLON, '45385', 'Attempts were made, but the sigmoid polyp was unable to be excised with hot snare.',
                 (('45378', CECUM),))):
            for prim in ((), primary):
                with self.subTest(line, primary=bool(prim)):
                    by_corti, by_astra = both(head + line + '\n', which, line, prim)
                    self.assertNotIn(READY, by_corti)
                    self.assertNotIn(READY, by_astra)


class LesionOwnershipTests(SimpleTestCase):
    """own-1 and own-2: a distance names a landmark, never the act's site (round 2, esc-5: a number and a unit in a
    relation to it); a comparison aside closes before the subject's own predicate; a sized anaphor refers back only to
    a lesion of its size, compared as numbers (round 2, over-9)."""
    BIOPSY = 'A 12 mm polyp in the sigmoid colon was biopsied with cold forceps.'

    def test_a_distance_from_a_landmark_keeps_the_snare_at_its_polyp(self):
        for snare in ('The polyp was then removed with a hot snare at 25 cm from the anal verge.',
                      'The polyp was then removed with a hot snare.',
                      'The polyp was then removed with a hot snare at 25-cm from the anal verge.',
                      'The polyp was then removed with a hot snare at the 25 cm mark from the anal verge.',
                      'The polyp was then removed with a hot snare at 25 cm, measured from the anal verge.',
                      'The polyp was then removed with a hot snare at 25 cm (from the anal verge).',
                      'The polyp was then removed with a hot snare at 25 cm proximal of the anal verge.',
                      'The polyp was then removed with a hot snare at twenty-five cm from the anal verge.'):
            with self.subTest(snare):
                text = COLON + self.BIOPSY + '\n' + snare + '\n'
                by_corti, by_astra = both(text, '45380', self.BIOPSY, primary=[('45385', snare)])
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_an_anaphor_of_the_same_size_however_written_is_its_lesion(self):
        for biopsy, snare in (('An 8 mm polyp in the sigmoid colon was biopsied with cold forceps.',
                               'The 0.8 cm polyp was then removed with a hot snare.'),
                              ('An 8-mm polyp in the sigmoid colon was biopsied with cold forceps.',
                               'The 8 mm polyp was then removed with a hot snare.')):
            with self.subTest(snare):
                text = COLON + biopsy + '\n' + snare + '\n'
                by_corti, by_astra = both(text, '45380', biopsy, primary=[('45385', snare)])
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_another_polyps_snare_is_never_moved_onto_the_biopsied_one(self):
        biopsy = 'A 7 mm polyp in the cecum was biopsied with cold forceps.'
        for snare in ('The 8 mm polyp, separate from the cecal polyp and located in the sigmoid colon, was removed with '
                      'a hot snare.',
                      'The 8 mm polyp, distinct from the surrounding normal sigmoid mucosa, was removed with a hot '
                      'snare.'):
            with self.subTest(snare):
                text = COLON + biopsy + '\n' + snare + '\n'
                result = run(text, corti(('45385', span(text, snare))), [read('astra', [code(text, '45380', biopsy)])])
                self.assertEqual(outcome(result, '45380'), [READY])  # the cecal polyp's biopsy is separately codable
                (snared,) = [p for p in result.proposals if p.code == '45385']
                self.assertNotIn('snare removal (hot snare) of the 7 mm', snared.rationale)
                if 'separate from' in snare:
                    self.assertIn('snare removal (hot snare) of the 8 mm polyp in the sigmoid colon', snared.rationale)


class OtherRoleTests(SimpleTestCase):
    """own-3, the owner's other-provider protection, as round 2 left it: an act documented only in another role's
    entry never lets a participant's code account for a whole service (the reconciliation's own role rule, applied to
    admission); Corti's own selection reads as main reads it, because the role reader takes an impression after
    "Pathology results: pending." as the pathology entry (over-6), recorded."""

    def test_a_participant_code_on_another_roles_act_alone_is_never_ready(self):
        for body, which, quote in (
                ('A 6 mm polyp was seen in the sigmoid colon.\n\nPATHOLOGY ADDENDUM - 2026-10-16\nSpecimen A, sigmoid '
                 'colon polyp, removed by cold snare polypectomy: tubular adenoma.\n', '45385',
                 'Specimen A, sigmoid colon polyp, removed by cold snare polypectomy: tubular adenoma.'),
                ('A 15 mm lesion was seen in the transverse colon.\n\nNursing note\nTattoo ink was injected into the '
                 'transverse colon submucosa by the endoscopist.\n', '45381',
                 'Tattoo ink was injected into the transverse colon submucosa by the endoscopist.'),
                ('A 6 mm polyp was seen in the sigmoid colon.\n\nAnesthesia record\nThe 6 mm sigmoid polyp was removed '
                 'with a cold snare during propofol sedation.\n', '45385',
                 'The 6 mm sigmoid polyp was removed with a cold snare during propofol sedation.'),
                ('A 6 mm polyp was seen in the sigmoid colon.\n\nRadiology report\nCT colonography: the 6 mm sigmoid '
                 'polyp was removed with a cold snare at colonoscopy.\n', '45385',
                 'CT colonography: the 6 mm sigmoid polyp was removed with a cold snare at colonoscopy.')):
            with self.subTest(which, body=body[:40]):
                _, by_astra = both(COLON + body, which, quote)
                self.assertNotIn(READY, by_astra)

    def test_the_physicians_own_impression_after_a_pathology_line_is_held_on_both_paths(self):
        # moved by the completion repair (owner directive 2026-11-06, item 3: equal eligibility; builder Q1): the role
        # rule is one per-code rule now, applied whoever proposed the code (engine._another_roles_hold), so Corti's
        # selection of an act documented only in another role's entry is held with the question naming that entry, as a
        # participant's is - it fixes the base's false READY on a pathology addendum (corpus R1|L5-2). Its cost is this
        # input: the role reader still reads an Impression after "Pathology results: pending." as the pathology entry
        # (over-6, a reader's residual), so the physician's own polypectomy is held on both paths, where Corti's was
        # READY - a false hold, the safe side, recorded (it is held, never excluded, for exactly this reason)
        line = 'Impression: A 6 mm polyp in the sigmoid colon was removed with a cold snare.'
        by_corti, by_astra = both(COLON + 'Pathology results: pending.\n' + line + '\n', '45385', line)
        self.assertEqual(by_corti, [('selected', 'needs_clarification')])
        self.assertEqual(by_astra, by_corti)


class InjectionTests(SimpleTestCase):
    """own-4 and round 2's cost-4: the EMR's lift injection told apart is part of the EMR; an injection at another site
    never is."""

    def test_a_lift_told_apart_is_held_as_part_of_the_emr(self):
        lift = 'In the ascending colon, a 17 mm flat lesion was lifted by a submucosal injection of saline.'
        emr = 'The lesion was then removed by snare-based endoscopic mucosal resection.'
        text = COLON + lift + '\n' + emr + '\n'
        result = run(text, corti(('45390', span(text, emr)), ('45381', span(text, lift))))
        self.assertEqual(outcome(result, '45390'), [READY])
        (injection,) = [p for p in result.proposals if p.code == '45381']
        self.assertEqual((injection.bucket, injection.status), ('selected', 'needs_clarification'))
        (status,) = [c for c in injection.checks if c.id == 'service.status']
        self.assertIn('is part of another documented act', status.detail)

    def test_an_injection_at_another_site_keeps_its_code(self):
        emr = 'A 20 mm flat lesion in the cecum was removed by endoscopic mucosal resection.'
        steroid = ('In the rectum, the anastomotic stricture received a submucosal injection of triamcinolone 40 mg in '
                   'four quadrants.')
        text = COLON + emr + '\n' + steroid + '\n'
        result = run(text, corti(('45390', span(text, emr)), ('45381', span(text, steroid))))
        self.assertEqual(outcome(result, '45381'), [READY])


class DecompressionTests(SimpleTestCase):
    """compl-1 and round 2's esc-7 and cost-5: a decompression no code of its family accounts for is listed whatever its
    outcome - done, attempted, or a failed attempt read as a denial - never a mere denial or a counterfactual."""
    DILATION = 'The esophageal stricture was dilated with a 15 mm through-the-scope balloon.'

    def unresolved(self, line):
        text = EGD + self.DILATION + '\n' + line + '\n'
        result = run(text, corti(('43249', span(text, self.DILATION))))
        return result.completeness['state'], [(u['act'], u['reason'])
                                              for u in result.completeness['unresolved_items']]

    def test_a_done_attempted_or_failed_decompression_is_listed(self):
        for line in ('Decompression of the stomach was attempted but failed.',
                     'Gastric decompression was attempted but failed.',
                     'Decompression of the gastric volvulus was attempted, without success.',
                     # round 3, as round 4 (L4B-1) left it: the verb's bare form only in a failure frame
                     'We were unable to decompress the stomach.',
                     'Gastric decompression could not be achieved.', 'The stomach could not be decompressed.',
                     'Decompression of the stomach was not successful.', 'The stomach was decompressed.'):
            with self.subTest(line):
                state, items = self.unresolved(line)
                self.assertNotEqual(state, 'complete_pending_review')
                self.assertIn(('decompression', 'unsupported'), items)

    def test_a_denied_or_counterfactual_decompression_is_never_listed(self):
        for line in ('Decompression of the stomach was not attempted.',
                     'Decompression would have been performed had the stomach been distended.',
                     'If the stomach becomes distended, decompression will be performed.'):
            with self.subTest(line):
                self.assertNotIn(('decompression', 'unsupported'), self.unresolved(line)[1])

    def test_an_attempt_to_decompress_never_makes_a_decompression_code_ready(self):
        # round 4 (L4B-1): "Attempts to decompress the colon were made but failed." had read as a decompression done,
        # READY on both paths where main holds it; an attempt's bare verb is no act (as at main)
        sig = COLON.replace('Colonoscopy report', 'Flexible sigmoidoscopy report').replace(
            'Procedure: Colonoscopy', 'Procedure: Flexible sigmoidoscopy').replace(
            'The colonoscope was advanced to the cecum and the examination was completed.',
            'The sigmoidoscope was advanced to the descending colon.')
        for head, which, line in ((COLON, '45393', 'Attempts to decompress the colon were made but failed.'),
                                  (COLON, '45393', 'Attempts to decompress the colon were made, without success.'),
                                  (COLON, '45393', 'Attempts to decompress the colon were made.'),
                                  (COLON, '45393', 'A second attempt to decompress the colon was made.'),
                                  (COLON, '45393', 'Attempts to decompress the colon were performed by the nurse with a '
                                                   'rectal tube.'),
                                  (sig, '45337', 'Attempts to decompress the colon were made but failed.'),
                                  (sig, '45337', 'Multiple attempts to decompress the colon were performed.')):
            for primary in ((), (('45378', CECUM),) if head is COLON else ()):
                with self.subTest(line, code=which, primary=bool(primary)):
                    by_corti, by_astra = both(head + line + '\n', which, line, primary)
                    self.assertNotIn(READY, by_corti)
                    self.assertNotIn(READY, by_astra)

    def test_the_verbs_bare_forms_never_make_a_decompression_code_ready(self):
        # round 3, LENS-1: reading "to decompress" made 45393 and 45337 READY where main held them (a plan, a drug, a
        # rectal tube); the bare forms are not read, and "We were unable to decompress the stomach." is recorded
        sig = COLON.replace('Colonoscopy report', 'Flexible sigmoidoscopy report').replace(
            'Procedure: Colonoscopy', 'Procedure: Flexible sigmoidoscopy').replace(
            'The colonoscope was advanced to the cecum and the examination was completed.',
            'The sigmoidoscope was advanced to the descending colon.')
        for head, which, line in ((COLON, '45393', 'We elected to decompress the colon at a later date.'),
                                  (COLON, '45393', 'The patient was sent for surgery to decompress the colon.'),
                                  (COLON, '45393', 'Neostigmine was given to decompress the colon.'),
                                  (COLON, '45393', 'The nurse placed a rectal tube to decompress the colon.'),
                                  (sig, '45337', 'Neostigmine was given to decompress the colon.')):
            with self.subTest(line, code=which):
                by_corti, by_astra = both(head + line + '\n', which, line)
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_a_stent_placed_for_biliary_decompression_opens_nothing(self):
        stent = 'A 10 Fr plastic biliary stent was placed for biliary decompression.'
        text = ERCP + 'The bile duct was cannulated.\n' + stent + '\n'
        result = run(text, corti(('43274', span(text, stent))))
        self.assertEqual(result.completeness['state'], 'complete_pending_review')


class ProcedureLineTests(SimpleTestCase):
    """fa-1, the owner's failed and planned protection: a procedure line lists what its report documents; where the
    report says the listed act was not done, failed, is planned or is in doubt, the listing alone never makes it READY.
    Round 2: hedges of the act's own clause count (esc-8); a removal stated done keeps the listing (over-7); a report of
    one procedure is its own scope (cost-2); a removal planned for another occurrence of a service is no statement
    about today's (cost-3)."""
    HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy report (fictional)\n'
            'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
            'Procedure: Colonoscopy with hot snare polypectomy\n'
            'The colonoscope was advanced to the cecum and the examination was completed.\n'
            'A 9 mm pedunculated polyp in the sigmoid colon was seen.\n')
    LINE = 'Colonoscopy with hot snare polypectomy'

    def test_a_listed_removal_the_report_denies_defers_doubts_or_fails_is_never_ready(self):
        untitled = self.HEAD.replace('Colonoscopy report (fictional)\n', '')
        for head in (self.HEAD, untitled):
            for last in ('Hot snare polypectomy failed.',
                         'The polyp will be removed by hot snare at a later date.',
                         'Plan: the polyp will be removed by hot snare at a later date.',
                         'Polypectomy will be performed at a later date.',
                         'It is unclear whether hot snare polypectomy was performed.',
                         'Hot snare polypectomy may have been performed.'):
                with self.subTest(last, titled=head == self.HEAD):
                    text = head + last + '\n'
                    by_corti, by_astra = both(text, '45385', self.LINE, primary=[('45378', CECUM)])
                    self.assertNotIn(READY, by_corti)
                    self.assertNotIn(READY, by_astra)

    def test_a_removal_with_no_technique_reads_as_main_reads_it(self):
        # refutation round 7 (L7-1): the withheld listing's kindless branch read another lesion's or another date's
        # "not removed" as today's listed removal and made 45378 READY; it failed two cycles and is dropped. A removal
        # stated not done with no technique named now leaves the listing as main reads it (ACCURACY-RESIDUALS.md,
        # round 7): pinned under the equivalent standard
        untitled = self.HEAD.replace('Colonoscopy report (fictional)\n', '')
        for head in (self.HEAD, untitled):
            for last in ('No polyps were removed.', 'The polyp was not removed.',
                         'The polyp will be removed at a later date.'):
                with self.subTest(last, titled=head == self.HEAD):
                    by_corti, by_astra = both(head + last + '\n', '45385', self.LINE, primary=[('45378', CECUM)])
                    if READY in by_astra:
                        self.assertIn(READY, by_corti)

    def test_another_lesions_or_dates_removal_never_withholds_todays_listing(self):
        # L7-1 itself: the listed polypectomy stays listed and the diagnostic code stays held, as at main
        text = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy report (fictional)\n'
                'Date of service: 2026-10-14\nProcedure: Colonoscopy with hot snare polypectomy\n'
                'The colonoscope was advanced to the cecum and the examination was completed.\n')
        for body in ('Indication: Prior colonoscopy in 2021; no polyps were removed.\n'
                     'Findings: A 9 mm polyp in the sigmoid colon.\n',
                     'Findings: A 9 mm polyp in the sigmoid colon.\nTwo diminutive rectal polyps were not removed.\n',
                     'Findings: A 9 mm polyp in the sigmoid colon.\nA 30 mm rectal lesion was not resected; it was '
                     'referred for surgery.\n'):
            with self.subTest(body):
                result = run(text + body, corti(('45378', span(text + body, CECUM))))
                self.assertNotIn(READY, outcome(result, '45378'))
                self.assertIn('snare', ' '.join(u['label'] for u in result.completeness['unresolved_items']))

    def test_a_listed_stent_the_report_says_failed_is_never_ready(self):
        text = ERCP.replace('Procedure: ERCP', 'Procedure: ERCP with biliary stent placement') \
            + 'Biliary stent placement failed.\n'
        by_corti, by_astra = both(text, '43274', 'ERCP with biliary stent placement')
        self.assertNotIn(READY, by_corti)
        self.assertNotIn(READY, by_astra)

    def test_a_listing_the_report_does_not_contradict_stays_ready(self):
        head = self.HEAD.replace('A 9 mm pedunculated polyp in the sigmoid colon was seen.\n', '')
        for body in ('A 9 mm pedunculated polyp in the sigmoid colon was seen.\nThe polyp was removed with a hot snare.',
                     # round 2, over-7 and cost-3: a removal stated done; another polyp's removal planned for the next
                     # colonoscopy
                     'A 9 mm polyp in the sigmoid colon was removed and retrieved. A 4 cm mass in the cecum was not '
                     'resected.',
                     'A 9 mm pedunculated polyp in the sigmoid colon was removed.\nA 3 mm flat polyp in the rectum was not '
                     'removed.',
                     'A 9 mm pedunculated polyp in the sigmoid colon was removed in one piece and retrieved.\nA second 3 mm '
                     'polyp in the rectum will be removed at the next colonoscopy.'):
            with self.subTest(body):
                by_corti, _ = both(head + body + '\n', '45385', self.LINE, primary=[('45378', CECUM)])
                self.assertEqual(by_corti, [READY])
        # Refutation cycle 2 (acts A7, admission D3): the procedure line supplies a technique, never a performance - a
        # listed removal stands only beside a lesion the report states removed today. A polyp only seen, beside a future
        # polypectomy or another polyp's removal at the next colonoscopy, states none removed: held (recorded holds where
        # the installed release read READY), never excluded
        for body in ('A 9 mm pedunculated polyp in the sigmoid colon was seen.\n'
                     'Plan: repeat colonoscopy with snare polypectomy in 3 years.',
                     'A 9 mm pedunculated polyp in the sigmoid colon was seen.\n'
                     'Surveillance colonoscopy with polypectomy as needed is recommended in 3 years.',
                     # cost-3 alone: no removal stated done, a removal planned for another occurrence of the service
                     'A 9 mm pedunculated polyp in the sigmoid colon was seen.\nA second 3 mm polyp in the rectum will be '
                     'removed at the next colonoscopy.'):
            with self.subTest(body):
                by_corti, _ = both(head + body + '\n', '45385', self.LINE, primary=[('45378', CECUM)])
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(('excluded', 'excluded'), by_corti)


class RecordedResidualTests(SimpleTestCase):
    """The readers' recorded residuals the refutation lenses reached (ACCURACY-RESIDUALS.md, "Harness repair,
    refutation rounds 1 to 4"): not repaired here - each was a phrase-level rule that did not converge in two cycles,
    or the same at main on Corti's path. What is pinned is the directive's equivalent standard: a participant's code is
    READY only where Corti's selection of the same passages is READY, so admission adds no false READY of its own."""
    EMR = 'A 25 mm flat lesion in the ascending colon was removed by endoscopic mucosal resection.'
    INPUTS = (
        # multi-2 and esc-2: a lesion named by a site adjective is not recorded (LESION_SITED dropped)
        (COLON + 'Cold forceps biopsies were taken from a 10 mm sigmoid polyp, which was then removed with a hot snare.\n',
         '45380', 'Cold forceps biopsies were taken from a 10 mm sigmoid polyp, which was then removed with a hot snare.',
         [('45385', 'Cold forceps biopsies were taken from a 10 mm sigmoid polyp, which was then removed with a hot '
                    'snare.')]),
        (COLON + 'A 10 mm sigmoid polyp was sampled with cold biopsy forceps for histology. The same polyp was '
                 'subsequently resected with a hot snare.\n',
         '45380', 'A 10 mm sigmoid polyp was sampled with cold biopsy forceps for histology.',
         [('45385', 'The same polyp was subsequently resected with a hot snare.')]),
        # neg-1: an outcome of nothing obtained, with no other act's denial (NO_YIELD_AFTER dropped)
        (COLON + 'In the distal rectum, a 5 mm sessile polyp was seen; it was sampled with cold biopsy forceps, which '
                 'yielded no tissue.\n', '45380', 'it was sampled with cold biopsy forceps, which yielded no tissue.', []),
        # esc-1: an EMR named only on the procedure line, or in another sentence than its snare
        (COLON.replace('Procedure: Colonoscopy', 'Procedure: Colonoscopy with endoscopic mucosal resection')
         + 'A 25 mm flat lesion in the ascending colon was resected with a hot snare after a saline lift.\n', '45385',
         'A 25 mm flat lesion in the ascending colon was resected with a hot snare after a saline lift.', []),
        (COLON + 'Endoscopic mucosal resection of a 25 mm flat lesion in the ascending colon was performed. A hot snare '
                 'was used.\n', '45385', 'A hot snare was used.',
         [('45390', 'Endoscopic mucosal resection of a 25 mm flat lesion in the ascending colon was performed.')]),
        # esc-4: a tattoo after a place preposition the reader does not list
        (COLON + 'A 5 mm polyp at the level of the tattoo was removed with a cold snare.\n', '45381',
         'A 5 mm polyp at the level of the tattoo was removed with a cold snare.', []),
        (COLON + 'The tattoo mark in the ascending colon was biopsied.\n', '45381',
         'The tattoo mark in the ascending colon was biopsied.', []),
        # esc-6: a role heading the role reader does not know
        (COLON + 'A 6 mm polyp was seen in the sigmoid colon.\n\nHistopathology report - 2026-10-16\nSpecimen A, '
                 'sigmoid colon polyp, removed by cold snare polypectomy: tubular adenoma.\n', '45385',
         'Specimen A, sigmoid colon polyp, removed by cold snare polypectomy: tubular adenoma.', []),
        # esc-8: a denial of the listed removal the readers leave unread
        (ProcedureLineTests.HEAD + 'The snare could not capture the polyp.\n', '45385', ProcedureLineTests.LINE,
         [('45378', CECUM)]),
        (ProcedureLineTests.HEAD + 'Polyps removed: none.\n', '45385', ProcedureLineTests.LINE, [('45378', CECUM)]),
        # neg-2: a relative-clause denial of the marker, with no coordinated denial
        (COLON + 'The lesion was marked with tattoo ink that was unavailable.\n', '45381',
         'The lesion was marked with tattoo ink that was unavailable.', []),
        # compl-2: a decompression in a family whose act list has none (reverted in round 2, over-11)
        (ERCP + 'A biliary sphincterotomy was performed.\nThe distended stomach was decompressed for a gastric volvulus '
                'before withdrawal.\n', '43262', 'A biliary sphincterotomy was performed.', []),
        # round 4 (L4B-1, L4B-3): an attempt to decompress, or a failure worded outside the readers' failure
        # phrases, is no decompression act; the upper endoscopy's completeness does not list it (as at main)
        (EGD + 'An attempt to decompress the stomach was unsuccessful.\n', '43249',
         'An attempt to decompress the stomach was unsuccessful.', []),
        (EGD + 'We tried to decompress the stomach but could not.\n', '43249',
         'We tried to decompress the stomach but could not.', []),
        (COLON + 'Decompression of the colon failed.\n', '45393', 'Decompression of the colon failed.', []),
        # round 4: an injection or tattoo predicate after an adverb of another time reads as done today, READY on
        # Corti's path at main and at the live revision as here (a reader residual this change neither made nor
        # repairs; ACCURACY-RESIDUALS.md "Harness repair, refutation round 4")
        (COLON + 'The lesion in the ascending colon was already tattooed and not resected.\n', '45381',
         'The lesion in the ascending colon was already tattooed and not resected.', []),
        (COLON + 'India ink was already injected adjacent to the lesion in the ascending colon.\n', '45381',
         'India ink was already injected adjacent to the lesion in the ascending colon.', []),
        (COLON + 'Tattoo ink had already been injected into the ascending colon.\n', '45381',
         'Tattoo ink had already been injected into the ascending colon.', []),
    )

    def test_a_participants_code_is_ready_only_where_cortis_is(self):
        for text, which, quote, primary in self.INPUTS:
            with self.subTest(quote[:60]):
                by_corti, by_astra = both(text, which, quote, primary=primary)
                if READY in by_astra:
                    self.assertEqual(by_corti, [READY])

    def test_two_dilations_told_in_one_sentence_compete_and_hold_nothing_ready(self):
        # esc-10: both codes' passages show both dilations, so they compete (conservative: the EGD is left uncoded)
        line = ('The distal esophageal stricture was dilated with an 18 mm balloon, and a separate pyloric stricture '
                'was dilated with a 15 mm balloon.')
        text = EGD + line + '\n'
        result = run(text, corti(), [read('astra', [code(text, '43249', line)]), read('fable', [code(text, '43245', line)])])
        self.assertNotIn(READY, outcome(result, '43249') + outcome(result, '43245'))


class CompetingWordingTests(SimpleTestCase):
    def test_the_competing_reason_names_readings_not_participants(self):
        self.assertTrue(engine.PARTICIPANT_COMPETING.startswith('independent readings propose'))
