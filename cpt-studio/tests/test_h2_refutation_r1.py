"""Harness repair 2026-11-05: the refutation pass over the finished P-ADMIT diff (six lenses) and its repairs, pinned
on both paths - a Corti selection and an independent participant's first reading - with the controls that must stay
READY. Every input is a lens's own counterexample, verbatim. Real engine, no provider or database calls.

Under D14 a reader gap that left a false open act beside Corti's correct code was a conservative failure (an
alternative, coding incomplete); P-ADMIT lets a participant fill that gap READY, so the gaps are repaired in the shared
readers, which both paths read (HARNESS.md "GI core and harness repair (2026-11-05)", refutation round 1)."""
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


def outcome(result, which):
    return [(p.bucket, p.status) for p in result.proposals if p.code == which]


def both(text, which, quote, primary=()):
    """(Corti selecting ``which`` beside ``primary``, a participant's first reading proposing it beside ``primary``)."""
    selected = [(c, span(text, q)) for c, q in primary]
    by_corti = run(text, corti(*selected, (which, span(text, quote))))
    by_astra = run(text, corti(*selected), [read('astra', [code(text, which, quote)])])
    return outcome(by_corti, which), outcome(by_astra, which)


class EmrComponentsTests(SimpleTestCase):
    """multi-1: an EMR is a snare-based resection; its own snare is never a second removal (45385) charged beside it."""
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
        line = self.FORMS[0]
        text = COLON + line + '\n'
        result = run(text, corti(), [read('astra', [code(text, '45390', line)]),
                                     read('fable', [code(text, '45385', line)])])
        self.assertEqual(outcome(result, '45390'), [READY])
        self.assertEqual(outcome(result, '45385'), [('alternative', 'informational')])

    def test_a_snare_at_another_lesion_keeps_its_code(self):
        emr = 'A 25 mm flat lesion in the ascending colon was removed by endoscopic mucosal resection.'
        snare = 'A separate 6 mm polyp in the sigmoid colon was removed with a cold snare.'
        text = COLON + emr + '\n' + snare + '\n'
        by_corti, by_astra = both(text, '45385', snare, primary=[('45390', emr)])
        self.assertEqual(by_corti, [READY])
        self.assertEqual(by_astra, [READY])


class BiopsyOfRemovedLesionTests(SimpleTestCase):
    """multi-2: a lesion named with a site adjective ("a 10 mm sigmoid polyp") is recorded, so its biopsy is part of
    its removal."""

    def test_the_biopsy_of_a_polyp_then_removed_is_never_ready(self):
        for biopsy, snare in (
                ('Cold forceps biopsies were taken from a 10 mm sigmoid polyp, which was then removed with a hot snare.',
                 'Cold forceps biopsies were taken from a 10 mm sigmoid polyp, which was then removed with a hot snare.'),
                ('A 10 mm sigmoid polyp was sampled with cold biopsy forceps for histology.',
                 'The same polyp was subsequently resected with a hot snare.')):
            with self.subTest(biopsy):
                text = COLON + (biopsy if biopsy == snare else biopsy + ' ' + snare) + '\n'
                by_corti, by_astra = both(text, '45380', biopsy, primary=[('45385', snare)])
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_a_restatement_with_its_size_and_site_is_the_lesion_it_restates(self):
        # the full suite's narrowing: a sized, sited mention binds the recorded lesion of its size at its site, so the
        # impression's snare is at the polyp the findings biopsied, and the biopsy is part of its removal
        biopsy = 'A 10 mm polyp in the sigmoid colon was biopsied with cold forceps.'
        snare = 'Impression: a 10 mm sigmoid polyp was removed with a hot snare.'
        text = COLON + biopsy + '\n' + snare + '\n'
        by_corti, by_astra = both(text, '45380', biopsy, primary=[('45385', snare)])
        self.assertNotIn(READY, by_corti)
        self.assertNotIn(READY, by_astra)

    def test_a_lesion_only_observed_binds_no_act_beside_it(self):
        # the full suite's narrowing: "A 6 mm sigmoid polyp was seen." is no lesion an act names, so a separate
        # biopsy on a line beside the snare's is never read as a biopsy of the polyp then removed
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
    bleeding was controlled. Not a prophylaxis word list (round 4b's R4c was refuted): no purpose word is read."""
    EMR = 'A 25 mm flat lesion in the ascending colon was lifted with saline and removed by endoscopic mucosal resection.'

    def test_a_hemostatic_clip_named_alone_is_never_control_of_bleeding(self):
        for clip in ('Two hemostatic clips were placed prophylactically to close the resection defect.',
                     'Two hemostatic clips were placed at the resection site.',
                     'A hemostatic clip was deployed.'):
            with self.subTest(clip):
                text = COLON + self.EMR + '\n' + clip + '\n'
                by_corti, by_astra = both(text, '45382', clip, primary=[('45390', self.EMR)])
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_bleeding_control_stated_stays_ready(self):
        for clip in ('Hemostasis was achieved with two hemostatic clips.', 'Hemostasis was achieved with two clips.'):
            with self.subTest(clip):
                text = COLON + self.EMR + '\n' + clip + '\n'
                by_corti, by_astra = both(text, '45382', clip, primary=[('45390', self.EMR)])
                self.assertEqual(by_corti, [READY])
                self.assertEqual(by_astra, [READY])

    def test_control_the_inventory_does_not_establish_is_read_by_the_codes_own_passage(self):
        # the inventory leaves it in doubt ("hemostatic" alone) or reads no act at all (a pre-existing gap, the same at
        # the committed head 3907cd59); Corti's code stands on the routing-era reading of its own passage (the
        # own-passage release), and a participant's fills no open item, so it stays an alternative (recorded)
        for clip in ('Oozing at the resection site was controlled with two hemostatic clips.',
                     'Active bleeding was controlled with two hemostatic clips.', 'Bleeding was stopped with two clips.'):
            with self.subTest(clip):
                text = COLON + self.EMR + '\n' + clip + '\n'
                by_corti, by_astra = both(text, '45382', clip, primary=[('45390', self.EMR)])
                self.assertEqual(by_corti, [READY])
                self.assertEqual(by_astra, [('alternative', 'informational')])


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
        text = EGD + self.D1 + '\n'
        result = run(text, corti(), [read('astra', [code(text, '43249', self.D1), code(text, '43245', self.D1)])])
        for which in ('43249', '43245'):
            (item,) = [p for p in result.proposals if p.code == which]
            self.assertEqual((item.bucket, item.status), ('alternative', 'informational'))
            self.assertIn('independent readings propose different codes for the same documented act',
                          item.exclusion_reason)
            self.assertNotIn('participants propose', item.exclusion_reason)


class NegativeQuantifierTests(SimpleTestCase):
    """neg-1 and neg-3: "nothing", the zero numeral, a negated infinitive and a negative object deny the act, so the
    routing-era hold is never released beside another act's denial and no participant fills the gap."""
    LEAD = 'In the distal rectum, a 5 mm sessile polyp was seen; '

    def test_a_denied_biopsy_is_never_ready(self):
        for body in ('nothing was biopsied; it was not snared.', 'nothing was biopsied.',
                     'zero biopsies were taken; it was not snared.', '0 biopsies were obtained; it was not snared.',
                     'the decision was made not to biopsy it; it was not snared.',
                     'biopsies were obtained from none of the polyps; it was not snared.',
                     'it was sampled with cold biopsy forceps, which yielded no tissue; it was not snared.',
                     'it was sampled with cold biopsy forceps, which yielded no tissue.'):
            with self.subTest(body):
                line = self.LEAD + body
                by_corti, by_astra = both(COLON + line + '\n', '45380', line)
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_a_limit_beyond_the_documented_acts_is_no_denial(self):
        for line in ('Cold forceps biopsies were taken from the 5 mm rectal polyp; nothing else was sampled.',
                     'Nothing abnormal was seen in the rectum; cold forceps biopsies were taken from the rectal mucosa.',
                     'Cold forceps biopsies were taken from the rectal mucosa; the stool culture yielded no growth.'):
            with self.subTest(line):
                by_corti, by_astra = both(COLON + line + '\n', '45380', line)
                self.assertEqual(by_corti, [READY])
                self.assertEqual(by_astra, [READY])


class TattooPlaceTests(SimpleTestCase):
    """neg-2: "marked" names a tattoo placed only as its instrument, and a tattoo named as a place is no tattoo act."""

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
                     # "marked" alone decides these: the tattoo is the marking's subject, a quoted label, "tattoo-free"
                     'The tattoo in the ascending colon was marked with a clip and not resected.',
                     'Specimen jar A was marked "tattoo" and not resected.',
                     'The lesion in the ascending colon was marked as tattoo-free and not resected.',
                     'A 5 mm polyp adjacent to the tattoo was removed with a cold snare.',
                     'The tattoo site was biopsied.'):
            with self.subTest(line):
                by_corti, by_astra = both(COLON + line + '\n', '45381', line)
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)

    def test_a_tattoo_placed_stays_ready(self):
        for line in ('The lesion in the ascending colon was marked with tattoo for localization and not resected.',
                     'A tattoo was placed distal to the lesion in the ascending colon.',
                     'India ink was injected adjacent to the polyp in the ascending colon.'):
            with self.subTest(line):
                by_corti, by_astra = both(COLON + line + '\n', '45381', line)
                self.assertEqual(by_corti, [READY])
                self.assertEqual(by_astra, [READY])


class LesionOwnershipTests(SimpleTestCase):
    """own-1 and own-2: a distance names a landmark, never the act's site; a comparison aside closes before the
    subject's own predicate; a sized anaphor refers back only to a lesion of its size."""
    BIOPSY = 'A 12 mm polyp in the sigmoid colon was biopsied with cold forceps.'

    def test_a_distance_from_the_anal_verge_keeps_the_snare_at_its_polyp(self):
        for snare in ('The polyp was then removed with a hot snare at 25 cm from the anal verge.',
                      'The polyp was then removed with a hot snare.'):
            with self.subTest(snare):
                text = COLON + self.BIOPSY + '\n' + snare + '\n'
                by_corti, by_astra = both(text, '45380', self.BIOPSY, primary=[('45385', snare)])
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
                    # the aside closes before "and located in the sigmoid colon": the polyp keeps its own site
                    self.assertIn('snare removal (hot snare) of the 8 mm polyp in the sigmoid colon', snared.rationale)


class OtherRoleTests(SimpleTestCase):
    """own-3, the owner's other-provider protection: an act documented only in another role's entry never makes a
    code READY, through either path."""

    def test_an_act_only_another_role_documents_is_never_ready(self):
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
                by_corti, by_astra = both(COLON + body, which, quote)
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)


class SplitLiftTests(SimpleTestCase):
    """own-4: the EMR's lift injection told in a sentence of its own is still part of the EMR."""

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


class DecompressionTests(SimpleTestCase):
    """compl-1 and compl-2: a decompression no code of its family accounts for is listed whatever its outcome and in
    every endoscopic family, so coding completeness never reads complete over it."""

    def assert_listed(self, text, primary):
        result = run(text, corti(*[(c, span(text, q)) for c, q in primary]))
        self.assertNotEqual(result.completeness['state'], 'complete_pending_review')
        self.assertIn(('decompression', 'unsupported'),
                      [(u['act'], u['reason']) for u in result.completeness['unresolved_items']])

    def test_a_failed_or_attempted_decompression_is_listed(self):
        dilation = 'The esophageal stricture was dilated with a 15 mm through-the-scope balloon.'
        for line in ('Decompression of the stomach was attempted but failed.',
                     'Gastric decompression was attempted but failed.',
                     'Decompression of the gastric volvulus was attempted, without success.'):
            with self.subTest(line):
                self.assert_listed(EGD + dilation + '\n' + line + '\n', [('43249', dilation)])

    def test_a_decompression_in_an_ercp_an_eus_or_an_enteroscopy_is_listed(self):
        decompressed = 'The distended stomach was decompressed for a gastric volvulus before withdrawal.\n'
        head = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n{title} report (fictional)\n' \
            'Date of service: 2026-10-14\nProcedure: {title}\n{scope}\n'
        for text, which, act in (
                (ERCP, '43262', 'A biliary sphincterotomy was performed.'),
                (head.format(title='EUS', scope='The linear echoendoscope was advanced to the second portion of the '
                                                'duodenum.'),
                 '43242', 'A 22 gauge needle was passed into the pancreatic head mass with three passes.'),
                (head.format(title='Push enteroscopy', scope='The enteroscope was advanced into the proximal jejunum.'),
                 '44361', 'Cold forceps biopsies were taken from the jejunum.')):
            with self.subTest(which):
                self.assert_listed(text + act + '\n' + decompressed, [(which, act)])


class ProcedureLineTests(SimpleTestCase):
    """fa-1, the owner's failed and planned protection: a procedure line lists what its report documents; where the
    report says the listed act was not done, failed or is planned, the listing alone never makes it READY."""
    HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nColonoscopy report (fictional)\n'
            'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
            'Procedure: Colonoscopy with hot snare polypectomy\n'
            'The colonoscope was advanced to the cecum and the examination was completed.\n'
            'A 9 mm pedunculated polyp in the sigmoid colon was seen.\n')
    LINE = 'Colonoscopy with hot snare polypectomy'

    def test_a_listed_removal_the_report_denies_defers_or_fails_is_never_ready(self):
        for last in ('No polyps were removed.', 'Hot snare polypectomy failed.',
                     'The polyp will be removed by hot snare at a later date.',
                     'Plan: the polyp will be removed by hot snare at a later date.',
                     'Polypectomy will be performed at a later date.'):
            with self.subTest(last):
                text = self.HEAD + last + '\n'
                by_corti, by_astra = both(text, '45385', self.LINE, primary=[('45378', CECUM)])
                self.assertNotIn(READY, by_corti)
                self.assertNotIn(READY, by_astra)
                result = run(text, corti(('45378', span(text, CECUM))), [read('astra', [code(text, '45385', self.LINE)])])
                self.assertEqual(outcome(result, '45378'), [READY])  # never held as included in a code not done

    def test_a_listed_stent_the_report_says_failed_is_never_ready(self):
        text = ERCP.replace('Procedure: ERCP', 'Procedure: ERCP with biliary stent placement') \
            + 'Biliary stent placement failed.\n'
        by_corti, by_astra = both(text, '43274', 'ERCP with biliary stent placement')
        self.assertNotIn(READY, by_corti)
        self.assertNotIn(READY, by_astra)

    def test_a_future_service_or_a_form_question_never_withholds_a_listing(self):
        # the full suite's narrowing: a repeat colonoscopy planned in 3 years is another occurrence of the service at no
        # lesion of today's, so the listing reads as installed (a plan at today's lesion still withholds it: recorded)
        for last in ('Plan: repeat colonoscopy with snare polypectomy in 3 years.',
                     'Surveillance colonoscopy with polypectomy as needed is recommended in 3 years.'):
            with self.subTest(last):
                text = self.HEAD + last + '\n'
                by_corti, _ = both(text, '45385', self.LINE, primary=[('45378', CECUM)])
                self.assertEqual(by_corti, [READY])

    def test_a_listed_removal_the_report_documents_stays_ready(self):
        text = self.HEAD + 'The polyp was removed with a hot snare.\n'
        by_corti, by_astra = both(text, '45385', 'The polyp was removed with a hot snare.', primary=[('45378', CECUM)])
        self.assertEqual(by_corti, [READY])
        self.assertEqual(by_astra, [READY])


class CompetingWordingTests(SimpleTestCase):
    def test_the_competing_reason_names_readings_not_participants(self):
        self.assertTrue(engine.PARTICIPANT_COMPETING.startswith('independent readings propose'))
