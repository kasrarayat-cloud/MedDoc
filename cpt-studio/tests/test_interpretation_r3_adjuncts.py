"""A removal's procedural adjunct after the round-3 refutation (DECISIONS D76-D79; the adjunct-chains lens, findings 8
to 12), SYNTHETIC: what sets an ablation or a bleeding control apart from the removal beside it, and which removals it
can belong to. Each pin is a finding's own input, read by read.read, normalized with the real linked steps and assessed
through assess.assess with a synthetic Corti response citing the document's own words. Nothing is sent.

- D76: two distinct verified lesions set the adjunct apart only through the place test - their verified sites are both on
  the tract's chains and neither compatible nor adjacent. A distinctness by landmarks that are adjacent or on no chain
  (finding 8), by sizes or by passage (finding 9) never does.
- D77: a junction landmark is not a full step: the two segments meeting at it are adjacent, and the stomach's cardia,
  fundus and body border one another; two places are apart only with a full segment strictly between them (finding 10).
- D78: a removal done at several places is read at each of them (Context.places with ``every``); its adjunct is apart
  only when it is apart from every one (finding 11).
- D79: a removal attempted and not completed is a whole its adjunct can belong to: asked beside it, and bundled by a
  verified part_of naming it or by its verified lesion (finding 12).
The controls D41 and D58 keep: a bleeding diverticulum apart from the polypectomy is its own act, READY; a part_of naming
a biopsy sets the adjunct apart."""
from __future__ import annotations

import itertools

from django.test import SimpleTestCase

from studio.interpretation import coverage, events, identity, lexicon, relations, schema
from tests.test_interpretation_coverage import CECAL, RS_CLIP, RS_POLYP, hemoclips, hot_snared
from tests.test_interpretation_events import asked, colonoscopy, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, les, snare, tg


def assert_asked(case: SimpleTestCase, result, code: str) -> None:
    """``code`` is held with the procedural_adjunct question (act_target), never READY."""
    p = proposal(result, code)
    case.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                     ('selected', 'needs_clarification', ['act_target'], events.BUNDLING_IDENTITY))
    case.assertIn('done as part of the removal', p.clarifications[0].question)


def assert_bundled(case: SimpleTestCase, result, code: str) -> None:
    """``code`` is held as part of another documented act (R5), never READY."""
    p = proposal(result, code)
    case.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                     ('selected', 'needs_clarification', ['performed_status'], events.BUNDLED))
    case.assertIn(coverage.PROCEDURAL_ADJUNCT, ' '.join(check.detail for check in p.checks))


def statuses(result, *codes) -> list:
    return [proposal(result, code).status for code in codes]


def clips(line: str, status_words: str = 'was controlled', passage: str = 'P3', **changes) -> dict:
    """A bleeding control (E3): two hemoclips whose hemostasis purpose is verified, stated in ``passage`` with
    ``status_words`` (tests.test_interpretation_coverage.hemoclips, its status words free)."""
    options = {'technique': a('clip', 'hemoclips', [passage]), 'purpose': a('hemostasis', 'for hemostasis', [passage]),
               **changes}
    return act('E3', passage, 'clip', 'hemoclips', status_words=status_words, **options)


def hot_snare_beside(clip: dict, clip_line: str, polyp_line: str = RS_POLYP, landmark: str = 'rectosigmoid',
                     site_words: str = 'rectosigmoid junction', lesions=(), polyp: str = '12 mm sessile polyp',
                     size_words: str = '12 mm'):
    """(inventory, text, result) of a colonoscopy to the cecum (E1) whose polyp L1 at ``landmark`` is removed with a hot
    snare (E2, ``polyp_line``, P2) beside ``clip`` (``clip_line``, P3), with ``lesions`` after L1; Corti proposes 45385
    and 45382. tests.test_interpretation_coverage.hot_snared, with lesions of the clip's own."""
    lesion = les('L1', polyp, 'P2', landmark=landmark, site_words=site_words, size_words=size_words)
    removal = snare('E2', 'P2', technique=a('hot_snare', 'hot snare', ['P2']), status_words='was removed with a hot snare',
                    target=tg('L1', landmark, polyp_line[2:polyp_line.index(' was removed')], ['P2']))
    inv, text = colonoscopy(clip, polyp=removal, lesions=(lesion, *lesions), lines={'P2': polyp_line, 'P3': clip_line})
    return inv, text, run(inv, text, [('45385', polyp_line), ('45382', clip_line)])


# --- D76: two distinct verified lesions set an adjunct apart only by their places ------------------------------------

OOZING = les('L2', 'Immediate oozing from the polypectomy site', 'P3', landmark='sigmoid_colon',
             site_words='distal sigmoid colon')
IC_POLYP = 'A 12 mm sessile polyp at the ileocecal valve was removed with a hot snare.'
IC_CLIP = ('Immediate oozing from the polypectomy site on the ileal side was controlled with two hemoclips for '
           'hemostasis.')
IC_OOZING = les('L2', 'Immediate oozing from the polypectomy site', 'P3', landmark='ileum', site_words='ileal side')
VESSEL_POLYP = 'A 12 mm pedunculated polyp in the sigmoid colon was removed with a hot snare.'
VESSEL_CLIP = 'A 2 mm visible vessel in the polypectomy base was treated with two hemoclips for hemostasis.'
ONE_LINE = ('A 10 mm sessile polyp in the sigmoid colon was removed with a hot snare, and oozing from the polypectomy '
            'site was controlled with two hemoclips for hemostasis.')
DIVERTICULUM = 'A bleeding diverticulum in the ascending colon was controlled with two hemoclips for hemostasis.'


def vessel(lesion: dict, target: dict, **changes):
    """Finding 9 (a): the 12 mm sigmoid polyp's hot snare removal (E2, P2) beside two hemoclips (E3, P3) on a 2 mm
    visible vessel in the polypectomy base, registered as its own lesion L2."""
    clip = clips(VESSEL_CLIP, 'was treated', target=target, **changes)
    return hot_snare_beside(clip, VESSEL_CLIP, VESSEL_POLYP, 'sigmoid_colon', 'sigmoid colon', lesions=(lesion,),
                            polyp='12 mm pedunculated polyp')


def one_line(lesion: dict):
    """Finding 9 (b): one sentence states the 10 mm sigmoid polyp's hot snare removal (E2) and the hemoclips (E3) on the
    oozing from its site, which Gemini registers as its own lesion L2 in the same passage."""
    l1 = les('L1', '10 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon', size_words='10 mm')
    removal = snare('E2', 'P2', technique=a('hot_snare', 'hot snare', ['P2']), status_words='was removed with a hot snare',
                    target=tg('L1', 'sigmoid_colon', '10 mm sessile polyp in the sigmoid colon', ['P2']))
    clip = act('E3', 'P2', 'clip', 'hemoclips', status_words='was controlled', technique=a('clip', 'hemoclips', ['P2']),
               purpose=a('hemostasis', 'for hemostasis', ['P2']),
               target=tg('L2', 'not_stated', 'oozing from the polypectomy site', ['P2']))
    inv, text = colonoscopy(clip, polyp=removal, lesions=(l1, lesion), lines={'P2': ONE_LINE})
    return inv, text, run(inv, text, [
        ('45385', 'A 10 mm sessile polyp in the sigmoid colon was removed with a hot snare'),
        ('45382', 'oozing from the polypectomy site was controlled with two hemoclips for hemostasis')])


class DistinctLesions(SimpleTestCase):
    """DECISIONS D76 (findings 8 and 9): a distinctness that is no place never sets a removal's adjunct apart."""

    def assert_distinct_and_asked(self, inv, result, why: str):
        reading = events.Reading.of(inv)
        clip = reading.events['E3']
        self.assertEqual((identity.verified_lesion(reading.events['E2']), identity.verified_lesion(clip)),
                         ('L1', 'L2'))
        self.assertEqual(reading.context.distinct('L1', 'L2'), why)  # the distinctness is real: it decides nothing
        self.assertEqual((clip['catalogue_kind'], clip['part_of']['value'], coverage.bundled_reason(reading, clip)),
                         ('bleeding_control', '', ''))
        self.assertEqual((coverage.bundling_doubt(reading, clip) or {}).get('reason'), 'procedural_adjunct')
        self.assertEqual(proposal(result, '45385').status, 'ready')
        assert_asked(self, result, '45382')

    def test_d76_finding_8_an_oozing_registered_as_its_own_lesion_beside_a_rectosigmoid_polypectomy_is_asked(self):
        """D58's own pin with the oozing registered as lesion L2 at the sigmoid colon (as Gemini does on FRESH-2): L1 and
        L2 are distinct by landmarks, but the rectosigmoid and the sigmoid colon are adjacent (it was READY)."""
        for words in ('polypectomy site in the distal sigmoid colon',
                      'Immediate oozing from the polypectomy site in the distal sigmoid colon'):
            with self.subTest(words=words):
                clip = hemoclips(RS_CLIP, target=tg('L2', 'sigmoid_colon', words, ['P3']))
                inv, text, result = hot_snare_beside(clip, RS_CLIP, lesions=(OOZING,))
                reading = events.Reading.of(inv)
                self.assertEqual((reading.context.places(reading.events['E2']),
                                  reading.context.places(reading.events['E3'])),
                                 (frozenset({'rectosigmoid'}), frozenset({'sigmoid_colon'})))
                self.assert_distinct_and_asked(inv, result, 'landmarks')

    def test_d76_finding_8_the_ileum_variant_is_asked(self):
        """The polyp at the ileocecal valve, the oozing L2 'on the ileal side': distinct by landmarks, but the ileum is
        on no chain (D58 amended), so it never sets the adjunct apart (it was READY)."""
        clip = hemoclips(IC_CLIP, target=tg('L2', 'ileum', 'polypectomy site on the ileal side', ['P3']))
        inv, text, result = hot_snare_beside(clip, IC_CLIP, IC_POLYP, 'ileocecal_valve', 'ileocecal valve',
                                             lesions=(IC_OOZING,))
        self.assertNotIn('ileum', relations.TRACT_POSITION)
        self.assert_distinct_and_asked(inv, result, 'landmarks')

    def test_d76_finding_9a_a_visible_vessel_distinct_by_size_alone_is_asked(self):
        """The 2 mm visible vessel in the polypectomy base, its own lesion with no site: distinct from the 12 mm polyp
        by sizes alone (it was READY)."""
        for name, lesion, target in (
                ('no site', les('L2', '2 mm visible vessel', 'P3', size_words='2 mm'),
                 tg('L2', 'not_stated', '2 mm visible vessel', ['P3'])),
                ('site words naming no landmark',
                 les('L2', '2 mm visible vessel in the polypectomy base', 'P3', site_words='polypectomy base',
                     size_words='2 mm'),
                 tg('L2', 'not_stated', '2 mm visible vessel in the polypectomy base', ['P3']))):
            with self.subTest(name):
                inv, text, result = vessel(lesion, target)
                self.assert_distinct_and_asked(inv, result, 'sizes')

    def test_d76_finding_9b_an_oozing_distinct_by_its_passage_alone_is_asked(self):
        """One sentence: the polyp and 'oozing from the polypectomy site' (or the site named after the act) are two
        single lesions apart in one passage - distinct by passage alone (it was READY)."""
        for words in ('oozing from the polypectomy site', 'polypectomy site'):
            with self.subTest(words=words):
                inv, text, result = one_line(les('L2', words, 'P2'))
                self.assert_distinct_and_asked(inv, result, 'passage')

    def test_d76_control_distinct_lesions_at_places_apart_stay_their_own_acts(self):
        """D41's control in its lesion form: the bleeding diverticulum (L2) in the ascending colon beside the sigmoid
        polypectomy - distinct by landmarks that are apart on the tract - is its own act, READY."""
        lesion = les('L2', 'bleeding diverticulum', 'P3', landmark='ascending_colon', site_words='ascending colon')
        clip = hemoclips(DIVERTICULUM, target=tg('L2', 'ascending_colon', 'bleeding diverticulum in the ascending colon',
                                                 ['P3']))
        inv, text, result = hot_snare_beside(clip, DIVERTICULUM, VESSEL_POLYP, 'sigmoid_colon', 'sigmoid colon',
                                             lesions=(lesion,), polyp='12 mm pedunculated polyp')
        reading = events.Reading.of(inv)
        self.assertEqual(reading.context.distinct('L1', 'L2'), 'landmarks')
        self.assertIsNone(coverage.bundling_doubt(reading, reading.events['E3']))
        self.assertEqual(statuses(result, '45385', '45382'), ['ready', 'ready'])

    def test_d76_control_a_part_of_naming_a_biopsy_still_sets_it_apart(self):
        """Finding 9 (a)'s clip, its part_of a biopsy of the session: the part_of names an ACT, which sets the adjunct
        apart from the removal (D58) - the lesions no longer decide, the part_of still does. READY."""
        biopsy_line = 'Cold forceps biopsies were taken from the sigmoid colon.'
        biopsy = act('E4', 'P4', 'biopsy', 'biopsies', status_words='were taken',
                     technique=a('cold_forceps', 'Cold forceps', ['P4']),
                     target=tg('', 'sigmoid_colon', 'sigmoid colon', ['P4']))
        lesion = les('L2', '2 mm visible vessel', 'P3', size_words='2 mm')
        clip = clips(VESSEL_CLIP, 'was treated', part_of='E4', target=tg('L2', 'not_stated', '2 mm visible vessel',
                                                                          ['P3']))
        l1 = les('L1', '12 mm pedunculated polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                 size_words='12 mm')
        removal = snare('E2', 'P2', technique=a('hot_snare', 'hot snare', ['P2']),
                        status_words='was removed with a hot snare',
                        target=tg('L1', 'sigmoid_colon', '12 mm pedunculated polyp in the sigmoid colon', ['P2']))
        inv, text = colonoscopy(clip, biopsy, polyp=removal, lesions=(l1, lesion),
                                lines={'P2': VESSEL_POLYP, 'P3': VESSEL_CLIP, 'P4': biopsy_line})
        reading = events.Reading.of(inv)
        self.assertEqual((reading.events['E3']['part_of']['value'], reading.events['E3']['part_of']['state'],
                          reading.context.distinct('L1', 'L2')), ('E4', 'verified', 'sizes'))
        self.assertIsNone(coverage.bundling_doubt(reading, reading.events['E3']))
        result = run(inv, text, [('45385', VESSEL_POLYP), ('45382', VESSEL_CLIP)])
        self.assertEqual(statuses(result, '45385', '45382'), ['ready', 'ready'])


# --- D77: a junction is no full step ------------------------------------------------------------------------------------

def d58_apart(first: str, second: str) -> bool:
    """D58's rule as it stood (a4dcbea72): apart when both are on one chain more than one step apart (or on two chains),
    and not compatible - frozen here so D77's only direction is pinned."""
    one, two = relations.TRACT_POSITION.get(first), relations.TRACT_POSITION.get(second)
    if one is None or two is None or lexicon.compatible(first, second):
        return False
    return one[0] != two[0] or abs(one[1] - two[1]) > 1


NEWLY_ADJACENT = {frozenset(pair) for pair in (
    ('rectum', 'sigmoid_colon'), ('descending_colon', 'transverse_colon'), ('transverse_colon', 'ascending_colon'),
    ('distal_esophagus', 'gastric_cardia'), ('gastric_antrum', 'duodenal_bulb'), ('gastric_cardia', 'gastric_body'))}


def clip_line(site: str) -> str:
    return f'Immediate oozing from the polypectomy site in the {site} was controlled with two hemoclips for hemostasis.'


EGD_REACH = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'


def egd_snare_beside(polyp_words: str, landmark: str, site_words: str, clip_site: str, clip_landmark: str):
    """(inventory, text, result) of an EGD to the second portion of the duodenum (E1, G1) whose 12 mm polyp L1 at
    ``landmark`` is removed with a hot snare (E2, G2) beside two hemoclips (E3, P3) on the oozing from the polypectomy
    site at ``clip_landmark``, naming no lesion and no part_of; Corti proposes 43251 and 43255."""
    polyp_line = f'A 12 mm sessile polyp {polyp_words} was removed with a hot snare.'
    line = clip_line(clip_site)
    lesion = les('L1', '12 mm sessile polyp', 'G2', landmark=landmark, site_words=site_words, size_words='12 mm')
    removal = snare('E2', 'G2', procedure=a('egd'), technique=a('hot_snare', 'hot snare', ['G2']),
                    status_words='was removed with a hot snare',
                    target=tg('L1', landmark, polyp_line[2:polyp_line.index(' was removed')], ['G2']))
    clip = hemoclips(line, procedure=a('egd'), target=tg('', clip_landmark, f'polypectomy site in the {clip_site}',
                                                         ['P3']))
    inv, text = inventory({'G1': EGD_REACH, 'G2': polyp_line, 'P3': line}, lesions=[lesion],
                          events=[exam('E1', 'G1', words='gastroscope', procedure=a('egd')), removal, clip],
                          reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'G1')])
    return inv, text, run(inv, text, [('43251', polyp_line), ('43255', line)])


def colon_snare_beside(polyp_words: str, landmark: str, site_words: str, clip_site: str, clip_landmark: str):
    """Finding 10's colon shape: the 12 mm polyp at ``landmark`` removed with a hot snare, the hemoclips on the oozing
    from the polypectomy site at ``clip_landmark``, naming no lesion and no part_of (tests.test_interpretation_coverage.
    hot_snared)."""
    polyp_line = f'A 12 mm sessile polyp {polyp_words} was removed with a hot snare.'
    line = clip_line(clip_site)
    clip = hemoclips(line, target=tg('', clip_landmark, f'polypectomy site in the {clip_site}', ['P3']))
    return hot_snared(clip, line, polyp_line, landmark, site_words)


class Junctions(SimpleTestCase):
    """DECISIONS D77 (finding 10): two places are apart only with a full segment strictly between them."""

    def test_d77_the_junctions_and_the_stomach(self):
        self.assertEqual(relations.JUNCTIONS, frozenset({
            'rectosigmoid', 'splenic_flexure', 'hepatic_flexure', 'ileocecal_valve', 'gastroesophageal_junction',
            'pylorus'}))
        self.assertLessEqual(relations.JUNCTIONS, set(relations.TRACT_POSITION))
        self.assertEqual(relations.MUTUALLY_ADJACENT, (frozenset({'gastric_cardia', 'gastric_fundus', 'gastric_body'}),))
        apart = {
            # two segments meeting at a junction, and the stomach's three: adjacent (D58 read each as apart)
            ('ascending_colon', 'transverse_colon'): False, ('sigmoid_colon', 'rectum'): False,
            ('transverse_colon', 'descending_colon'): False, ('gastric_cardia', 'gastric_body'): False,
            ('distal_esophagus', 'gastric_cardia'): False, ('gastric_antrum', 'duodenal_bulb'): False,
            # a junction and each segment it joins, and D58's adjacent pairs: adjacent as before
            ('hepatic_flexure', 'ascending_colon'): False, ('hepatic_flexure', 'transverse_colon'): False,
            ('rectosigmoid', 'rectum'): False, ('ileocecal_valve', 'terminal_ileum'): False,
            ('ileocecal_valve', 'ascending_colon'): False, ('cecum', 'terminal_ileum'): False,
            ('gastric_fundus', 'gastric_body'): False, ('gastric_cardia', 'gastric_fundus'): False,
            ('second_portion_duodenum', 'jejunum'): False,
            # a full segment strictly between: apart as before
            ('rectosigmoid', 'descending_colon'): True, ('anal_canal', 'rectosigmoid'): True,
            ('splenic_flexure', 'hepatic_flexure'): True, ('descending_colon', 'hepatic_flexure'): True,
            ('sigmoid_colon', 'splenic_flexure'): True, ('hepatic_flexure', 'cecum'): True,
            ('transverse_colon', 'cecum'): True, ('ascending_colon', 'terminal_ileum'): True,
            ('mid_esophagus', 'gastroesophageal_junction'): True, ('gastroesophageal_junction', 'gastric_fundus'): True,
            ('gastroesophageal_junction', 'gastric_body'): True, ('distal_esophagus', 'gastric_fundus'): True,
            ('gastric_cardia', 'gastric_antrum'): True, ('gastric_fundus', 'gastric_antrum'): True,
            ('gastric_body', 'pylorus'): True, ('pylorus', 'second_portion_duodenum'): True,
            ('gastric_body', 'duodenal_bulb'): True,
        }
        for (one, two), expected in apart.items():
            with self.subTest(one=one, two=two):
                self.assertEqual((relations.adjunct_apart(one, two), relations.adjunct_apart(two, one)),
                                 (expected, expected))

    def test_d77_only_adds_adjacencies(self):
        """Over every pair of landmarks: D77 never sets apart a pair D58 did not (it only adds questions), and the pairs
        it no longer sets apart are exactly the six that meet at a junction or in the stomach."""
        newly = set()
        for one, two in itertools.combinations(sorted(schema.LANDMARKS), 2):
            now, before = relations.adjunct_apart(one, two), d58_apart(one, two)
            with self.subTest(one=one, two=two):
                self.assertFalse(now and not before)
            if before and not now:
                newly.add(frozenset((one, two)))
        self.assertEqual(newly, NEWLY_ADJACENT)

    def test_d77_finding_10_the_colon_pairs_meeting_at_a_flexure_or_junction_are_asked(self):
        """The polyp on one side of a junction, the clip on its own polypectomy site on the other: each was READY (the
        junction counted as a full step). Read from either side."""
        for polyp, clip in (
                (('in the distal ascending colon', 'ascending_colon', 'distal ascending colon'),
                 ('proximal transverse colon', 'transverse_colon')),
                (('in the distal sigmoid colon', 'sigmoid_colon', 'distal sigmoid colon'), ('proximal rectum', 'rectum')),
                (('in the distal transverse colon', 'transverse_colon', 'distal transverse colon'),
                 ('proximal descending colon', 'descending_colon')),
                (('in the proximal transverse colon', 'transverse_colon', 'proximal transverse colon'),
                 ('distal ascending colon', 'ascending_colon'))):
            with self.subTest(polyp=polyp[1], clip=clip[1]):
                inv, text, result = colon_snare_beside(*polyp, *clip)
                reading = events.Reading.of(inv)
                self.assertEqual((reading.context.places(reading.events['E2']),
                                  reading.context.places(reading.events['E3'])),
                                 (frozenset({polyp[1]}), frozenset({clip[1]})))
                self.assertEqual(proposal(result, '45385').status, 'ready')
                assert_asked(self, result, '45382')

    def test_d77_finding_10_the_stomach_pair_is_asked(self):
        """A gastric cardia polyp, the clip on its polypectomy site in the proximal gastric body: the cardia borders the
        body along the lesser curve (43255 was READY)."""
        inv, text, result = egd_snare_beside('in the gastric cardia', 'gastric_cardia', 'gastric cardia',
                                             'proximal gastric body', 'gastric_body')
        reading = events.Reading.of(inv)
        self.assertEqual((reading.context.places(reading.events['E2']), reading.context.places(reading.events['E3'])),
                         (frozenset({'gastric_cardia'}), frozenset({'gastric_body'})))
        self.assertEqual(proposal(result, '43251').status, 'ready')
        assert_asked(self, result, '43255')

    def test_d77_control_a_full_segment_between_still_sets_it_apart(self):
        """The control: a bleeding control with a full segment between it and the removal is its own act - the hepatic
        flexure beyond the transverse colon from a splenic flexure polypectomy, the antrum beyond the body from a
        cardia polypectomy. READY."""
        inv, text, result = colon_snare_beside('at the splenic flexure', 'splenic_flexure', 'splenic flexure',
                                               'hepatic flexure', 'hepatic_flexure')
        self.assertIsNone(coverage.bundling_doubt(events.Reading.of(inv), events.Reading.of(inv).events['E3']))
        self.assertEqual(statuses(result, '45385', '45382'), ['ready', 'ready'])
        inv, text, result = egd_snare_beside('in the gastric cardia', 'gastric_cardia', 'gastric cardia',
                                             'gastric antrum', 'gastric_antrum')
        self.assertIsNone(coverage.bundling_doubt(events.Reading.of(inv), events.Reading.of(inv).events['E3']))
        self.assertEqual(statuses(result, '43251', '43255'), ['ready', 'ready'])


# --- D78: a removal done at several places is at each of them ------------------------------------------------------

POLYPS = ('Three sessile polyps, 4 to 6 mm, in the cecum, the ascending colon and the transverse colon were removed '
          'with a cold snare.')
TRANSVERSE_CLIP = ('Immediate oozing from the transverse colon polypectomy site was controlled with two hemoclips for '
                   'hemostasis.')
GROUP_WORDS = 'Three sessile polyps, 4 to 6 mm, in the cecum, the ascending colon and the transverse colon'
GROUP_SITE = 'in the cecum, the ascending colon and the transverse colon'
THREE = frozenset({'cecum', 'ascending_colon', 'transverse_colon'})


def group_removal(clip: dict, clip_text: str = TRANSVERSE_CLIP, *, lesion_words: str = GROUP_WORDS,
                  target_words: str = GROUP_WORDS, multiplicity: str = 'group'):
    """Finding 11: one cold snare event (E2) removing a group lesion L1 named at three places, which Gemini places at the
    first-named, the cecum; beside ``clip`` (E3, P3)."""
    lesion = les('L1', lesion_words, 'P2', landmark='cecum', site_words=GROUP_SITE, size_words='4 to 6 mm',
                 multiplicity=multiplicity)
    removal = snare('E2', 'P2', status_words='were removed with a cold snare',
                    technique=a('cold_snare', 'cold snare', ['P2']), target=tg('L1', 'cecum', target_words, ['P2']))
    inv, text = colonoscopy(clip, polyp=removal, lesions=(lesion,), lines={'P2': POLYPS, 'P3': clip_text})
    return inv, text, run(inv, text, [('45385', POLYPS), ('45382', clip_text)])


class SeveralPlaces(SimpleTestCase):
    """DECISIONS D78 (finding 11): the adjunct is apart from a removal done at several places only when it is apart from
    every one of them."""

    def test_d78_finding_11_a_clip_at_one_of_the_removals_places_is_asked(self):
        clip = hemoclips(TRANSVERSE_CLIP, target=tg('', 'transverse_colon', 'transverse colon polypectomy site', ['P3']))
        inv, text, result = group_removal(clip)
        reading = events.Reading.of(inv)
        removal = reading.events['E2']
        self.assertEqual((removal['target']['state'], identity.verified_lesion(removal)), ('verified', 'L1'))
        self.assertEqual(reading.context.places(removal), frozenset({'cecum'}))  # the other readers' places: unchanged
        self.assertEqual(reading.context.places(removal, every=True), THREE)
        self.assertEqual(reading.context.places(reading.events['E3']), frozenset({'transverse_colon'}))
        self.assertTrue(relations.adjunct_apart('cecum', 'transverse_colon'))  # the one chosen place alone: it was READY
        self.assertEqual((coverage.bundling_doubt(reading, reading.events['E3']) or {}).get('reason'),
                         'procedural_adjunct')
        self.assertEqual(proposal(result, '45385').status, 'ready')
        assert_asked(self, result, '45382')

    def test_d78_finding_11_its_variants_are_asked(self):
        """The verifier's variants that were READY: the snare's words name no place (its lesion's words do), the
        lesion's description names none (its site words do), a single lesion, and the clip at the hepatic flexure."""
        clip = hemoclips(TRANSVERSE_CLIP, target=tg('', 'transverse_colon', 'transverse colon polypectomy site', ['P3']))
        hepatic_line = TRANSVERSE_CLIP.replace('transverse colon', 'hepatic flexure')
        hepatic = hemoclips(hepatic_line, target=tg('', 'hepatic_flexure', 'hepatic flexure polypectomy site', ['P3']))
        for name, args, options in (
                ('the snare names no place', (clip,), {'target_words': 'Three sessile polyps'}),
                ('the lesion names no place', (clip,), {'lesion_words': 'Three sessile polyps, 4 to 6 mm'}),
                ('a single lesion', (clip,), {'multiplicity': 'single'}),
                ('the clip at the hepatic flexure', (hepatic, hepatic_line), {})):
            with self.subTest(name):
                inv, text, result = group_removal(*args, **options)
                assert_asked(self, result, '45382')

    def test_d78_the_places_its_words_name_never_set_apart_a_removal_with_no_place_of_its_own(self):
        """D78 only adds pairs to the place test: a removal Gemini placed nowhere (its target and its lesion's site
        'not_stated') whose words name the transverse colon is still never set apart by that place - the clip in the
        cecum, apart from the transverse colon, is asked, as before D78."""
        line = 'A 6 mm sessile polyp in the transverse colon was removed with a cold snare.'
        lesion = les('L1', '6 mm sessile polyp in the transverse colon', 'P2', size_words='6 mm')
        removal = snare('E2', 'P2', target=tg('L1', 'not_stated', '6 mm sessile polyp in the transverse colon', ['P2']))
        cecal = 'A bleeding angioectasia in the cecum was controlled with two hemoclips for hemostasis.'
        clip = hemoclips(cecal, target=tg('', 'cecum', 'cecum', ['P3']))
        inv, text = colonoscopy(clip, polyp=removal, lesions=(lesion,), lines={'P2': line, 'P3': cecal})
        reading = events.Reading.of(inv)
        whole = reading.events['E2']
        self.assertEqual((whole['target']['state'], identity.verified_lesion(whole)), ('verified', 'L1'))
        self.assertEqual((reading.context.places(whole), reading.context.places(whole, every=True)),
                         (frozenset(), frozenset({'transverse_colon'})))
        self.assertTrue(relations.adjunct_apart('transverse_colon', 'cecum'))
        self.assertEqual((coverage.bundling_doubt(reading, reading.events['E3']) or {}).get('reason'),
                         'procedural_adjunct')
        assert_asked(self, run(inv, text, [('45385', line), ('45382', cecal)]), '45382')

    def test_d78_control_a_clip_apart_from_every_place_is_its_own_act(self):
        """The control: a bleeding diverticulum in the sigmoid colon is apart from the cecum, the ascending and the
        transverse colon alike - its own act, READY."""
        line = 'A bleeding diverticulum in the sigmoid colon was controlled with two hemoclips for hemostasis.'
        clip = hemoclips(line, target=tg('', 'sigmoid_colon', 'sigmoid colon', ['P3']))
        inv, text, result = group_removal(clip, line)
        reading = events.Reading.of(inv)
        self.assertEqual(reading.context.places(reading.events['E2'], every=True), THREE)
        self.assertIsNone(coverage.bundling_doubt(reading, reading.events['E3']))
        self.assertEqual(statuses(result, '45385', '45382'), ['ready', 'ready'])


# --- D79: an attempted removal is a whole its adjunct can belong to -------------------------------------------------

ATTEMPTED = ('Hot snare removal of a 12 mm sessile polyp in the sigmoid colon was attempted and not completed because '
             'of poor position.')
SNARE_SITE = 'Immediate oozing from the snare site was controlled with two hemoclips for hemostasis.'
SIGMOID_POLYP = les('L1', '12 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                    size_words='12 mm')


def attempted_snare(status: str = 'attempted_not_completed',
                    words: str = 'was attempted and not completed because of poor position', **changes) -> dict:
    """Finding 12's removal (E2, P2): the hot snare removal of L1 in the sigmoid colon, attempted and not completed -
    or of ``status`` stated by ``words``."""
    return act('E2', 'P2', 'snare', 'Hot snare removal', status=status, status_words=words,
               technique=a('hot_snare', 'Hot snare', ['P2']),
               target=tg('L1', 'sigmoid_colon', '12 mm sessile polyp in the sigmoid colon', ['P2']), **changes)


def beside_the_attempt(clip: dict, removal: dict = None, line: str = ATTEMPTED, clip_text: str = SNARE_SITE):
    """Finding 12: the hot snare removal of the 12 mm sigmoid polyp L1 attempted and not completed (E2, P2) - or
    ``removal`` - beside the hemoclips on the oozing from the snare site (E3, P3); Corti proposes 45385 and 45382."""
    inv, text = colonoscopy(clip, polyp=removal or attempted_snare(), lesions=(SIGMOID_POLYP,),
                            lines={'P2': line, 'P3': clip_text})
    return inv, text, run(inv, text, [('45385', line), ('45382', clip_text)])


EMR_ATTEMPTED = 'EMR of the 20 mm flat polyp in the cecum was attempted and not completed because of poor lift.'
MARGINS = 'The margins of the resection defect were treated with snare-tip soft coagulation.'


def beside_an_attempted_emr(part_of: str):
    emr = act('E2', 'P2', 'emr', 'EMR', status='attempted_not_completed',
              status_words='was attempted and not completed because of poor lift',
              target=tg('L1', 'cecum', '20 mm flat polyp in the cecum', ['P2']))
    ablation = act('E3', 'P3', 'ablation', 'snare-tip soft coagulation', status_words='were treated',
                   technique=a('electrocautery', 'snare-tip soft coagulation', ['P3']), part_of=part_of)
    inv, text = colonoscopy(ablation, polyp=emr, lesions=(CECAL,), lines={'P2': EMR_ATTEMPTED, 'P3': MARGINS})
    return inv, text, run(inv, text, [('45390', EMR_ATTEMPTED), ('45388', MARGINS)])


class AttemptedRemoval(SimpleTestCase):
    """DECISIONS D79 (finding 12): beside a removal attempted and not completed, an ablation or a bleeding control is
    asked or bundled exactly as beside a performed one - never READY alone. The attempted removal's own code keeps its
    own hold (performed_status)."""

    def test_d79_finding_12a_a_bleeding_control_beside_an_attempted_snare_is_asked(self):
        inv, text, result = beside_the_attempt(hemoclips(SNARE_SITE))
        reading = events.Reading.of(inv)
        removal, clip = reading.events['E2'], reading.events['E3']
        self.assertEqual((removal['status']['value'], removal['status']['state'], coverage.current_performed(removal),
                          coverage.adjunct_whole(removal)), ('attempted_not_completed', 'verified', False, True))
        self.assertEqual(coverage.bundled_reason(reading, clip), '')
        self.assertEqual((coverage.bundling_doubt(reading, clip) or {}).get('statement'), 'E2')
        self.assertEqual(asked(proposal(result, '45385')), ['performed_status'])  # the attempt's own hold
        assert_asked(self, result, '45382')

    def test_d79_finding_12b_a_part_of_naming_the_attempted_snare_bundles_it(self):
        inv, text, result = beside_the_attempt(hemoclips(SNARE_SITE, part_of='E2'))
        reading = events.Reading.of(inv)
        clip = reading.events['E3']
        self.assertEqual((clip['part_of']['value'], clip['part_of']['state']), ('E2', 'verified'))
        self.assertEqual(coverage.bundled_reason(reading, clip), coverage.PROCEDURAL_ADJUNCT)
        self.assertEqual(asked(proposal(result, '45385')), ['performed_status'])
        assert_bundled(self, result, '45382')
        self.assertEqual([item['event'] for item in result.completeness['bundled']], ['E3'])

    def test_d79_the_attempted_snares_verified_lesion_bundles_it_too(self):
        """The bleeding control on the attempted removal's own verified lesion (no part_of): D30's lesion arm."""
        line = 'Oozing from the snare site of the 12 mm sessile polyp was controlled with two hemoclips for hemostasis.'
        clip = hemoclips(line, target=tg('L1', 'sigmoid_colon', '12 mm sessile polyp', ['P3']))
        inv, text, result = beside_the_attempt(clip, clip_text=line)
        reading = events.Reading.of(inv)
        self.assertEqual(identity.verified_lesion(reading.events['E3']), 'L1')
        self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), coverage.PROCEDURAL_ADJUNCT)
        assert_bundled(self, result, '45382')

    def test_d79_an_ablation_of_an_attempted_resections_margins(self):
        """The ablation analog: snare-tip soft coagulation of the margins beside an attempted EMR - bundled by its
        part_of, asked with none (45388 was READY in both)."""
        inv, text, result = beside_an_attempted_emr('E2')
        assert_bundled(self, result, '45388')
        inv, text, result = beside_an_attempted_emr('')
        assert_asked(self, result, '45388')

    def test_d79_control_a_removal_never_begun_or_of_another_occasion_is_no_whole(self):
        """The controls: a planned removal, a statement that it was not done, and an attempt at an earlier encounter are
        no whole - the clip is its own act, READY - whatever its part_of names."""
        for name, removal, line, stated in (
                ('planned', attempted_snare('planned', 'is planned', time=a('future', 'at a later date', ['P2'])),
                 'Hot snare removal of a 12 mm sessile polyp in the sigmoid colon is planned at a later date.',
                 ('planned', 'future')),
                ('not performed', attempted_snare('not_performed', 'was not performed'),
                 'Hot snare removal of a 12 mm sessile polyp in the sigmoid colon was not performed.',
                 ('not_performed', 'current_encounter')),
                ('earlier encounter', attempted_snare(time=a('earlier_encounter', 'in 2024', ['P2'])),
                 'Hot snare removal of a 12 mm sessile polyp in the sigmoid colon was attempted and not completed '
                 'because of poor position in 2024.', ('attempted_not_completed', 'earlier_encounter'))):
            for part_of in ('', 'E2'):
                with self.subTest(name, part_of=part_of):
                    inv, text, result = beside_the_attempt(hemoclips(SNARE_SITE, part_of=part_of), removal, line)
                    reading = events.Reading.of(inv)
                    whole = reading.events['E2']
                    self.assertEqual((whole['status']['value'], whole['time']['value']), stated)
                    self.assertEqual(whole['status']['state'], 'verified')  # a stated status: no unverified one
                    self.assertFalse(coverage.adjunct_whole(whole))
                    self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']), '')
                    self.assertIsNone(coverage.bundling_doubt(reading, reading.events['E3']))
                    self.assertEqual(proposal(result, '45382').status, 'ready')
