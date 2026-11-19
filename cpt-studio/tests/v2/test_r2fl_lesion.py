"""DECISIONS D309 RFE-L1 and RFE-L2 (round r2f, builder f-lesion; the refutation of round r2e's e-lesion, its findings
RFE-L1 and RFE-L2). TEXT-ONLY and SYNTHETIC: every note here is written for these tests (fictional clinicians), every
pass-1 answer is built by hand with test_settle's builders and every pass-2 answer by an oracle; every FactSet is built
in code (evaluate_fixtures' Doc); nothing is sent anywhere.

Each rule is shown on an input it must change - red on the tree it repairs (int2 + r2e's e-lesion), green after - and on
a boundary it must leave alone:
- RFE-L1 (R2FLListed*Tests): a listed target's relation to an act whose target names no lesion is a function of each
  lesion's own established apartness from the act - an established not-on (D305's act-lesion claim), or, for a lesion the
  act was never asked about, its places established and disjoint from the act's with the act asked about each of them by
  a rejected place pair control - read over every listed lesion and every lesion the act was asked about or controlled
  against, with every place pair control asked of the act rejected (fail-closed). The refutation's input (its q01): a
  denial that a lifting injection was used for either of two removed polyps, one in the cecum and one in the transverse
  colon, beside a tattoo in the transverse colon that names no lesion - the cecal polyp is never asked (its place is not
  compatible with the tattoo's), so r2e's arm held the full listing and released when that polyp was deleted from the
  list (its q02). Now the full listing is apart, and deleting a listed lesion leaves its claim or control read.
- RFE-L2 (R2FLPresumptionTests): every fact a pair-type release presumes - the act-lesion single form's multiplicity,
  the lesion-pair forms' multiplicities - moves with 9.4's weakenings in the property harness: test_properties re-derives
  each pair-type outcome from the weakened FactSet through engine/facts' own readers (``rederived``), so the weakenings
  the refutation showed surviving (its q04: L1's multiplicity weakened, 45381 still READY) now take the release away.

Round r2f's refutation of this build (rf-f-lesion; its findings reproduced by independent verifiers), repaired here,
each shown red on the tree it repairs (the build above) and green after:
- RF2F-L1 (R2FLFinding*Tests): the place reading reads the listed lesion's FINDING (facts.finding_places: every entry
  its same_as component may join, in any state, an id the FactSet does not hold included - DECISIONS D294 G1, D297
  ENGB-1), never one entry's own place list: an entry whose places are not established, or an unknown id, sets nothing
  apart; every entry is established single; the disjointness and the rejected place pair controls cover every place of
  every entry. A polyp filed as two entries joined by same_as - one of them at the act's place - is held as the
  one-entry filing of the same polyp is.
- RF2F-L2 (R2FLStatementControl*Tests): the listed arm's every-control scan reads every place pair control asked of
  EITHER object - the statement asked about the act's places as well as the act about the statement's - as
  facts.apart_by_controls' D220 scan does; one not rejected keeps the pair together (4.11, P-UNKNOWN-TARGET).
"""
from __future__ import annotations

from dataclasses import replace
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import pairing
from studio.interpretation.engine.types import Attribute, Fact, Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2 import test_r2el_lesion as R2EL
from tests.v2.test_settle import event, fact, src, verdict

A, LM = Attribute, ct.Landmark
E3, E4, E5 = (Id.parse(name) for name in ('E3', 'E4', 'E5'))
L1, L2, L3, L5 = (Id.parse(name) for name in ('L1', 'L2', 'L3', 'L5'))
SINGLE, GROUP = ct.Multiplicity.SINGLE, ct.Multiplicity.GROUP
sup, unres = EF.sup, EF.unres


def properties():
    """tests/v2/test_properties (imported when a test needs it: it builds its fixtures and its harness)."""
    from tests.v2 import test_properties
    return test_properties


# --- RFE-L1: the listed arm, on settled FactSets ----------------------------------------------------------------------

def listed(*, l1_places=(LM.TRANSVERSE_COLON,), l2_places=(LM.CECUM,), denial_places=None, tattoo=(LM.TRANSVERSE_COLON,),
           targets=(L1, L2), controls=None, lesions=None):
    """A colonoscopy X1 (E1) with the cold snare E2 of L1, E3 a denial that a lifting injection was used for each of
    ``targets`` (listed targets; its places ``denial_places``, by default every place of its lesions), and E4 a tattoo
    in ``tattoo`` whose target names no lesion. L1 (single) in ``l1_places``, L2 (single) in ``l2_places``; ``lesions``
    adds more entries. ``controls``: FactSet.pair_controls - by default the act-lesion pair (E4, L1) established, as a
    settled claim pass 2 supported and whose control it rejected, and the place pair control asking the tattoo about
    L2's cecum rejected, as contract/claims makes it from the denial's places."""
    doc = EF.colonoscopy(places=[sup(place) for place in l1_places])
    doc.lesions[L1] = EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(place) for place in l1_places])
    doc.lesion(2, multiplicity=sup(SINGLE), lesion_places=[sup(place) for place in l2_places])
    for lid, facts in (lesions or {}).items():
        doc.lesions[lid] = facts
    places = denial_places if denial_places is not None else (*l1_places, *l2_places)
    doc.act(3, ct.Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.LISTED_TARGETS),
            targets=[sup(lesion) for lesion in targets], places=[sup(place) for place in places])
    doc.act(4, ct.Kind.TATTOO, places=[place if isinstance(place, Fact) else sup(place) for place in tattoo])
    doc.controls.update(controls if controls is not None
                        else {(E4, A.DISTINCT_FROM, L1): True, (E4, A.TARGET_PLACES, LM.CECUM): True})
    return doc.build()


def target(R, statement=E3, act=E4):
    return dict(pairing.rows(R, statement, act))[pairing.Row.TARGET]


def without_target(R, lesion, statement=E3):
    """9.4's deleted member, on the statement's listed targets: ``lesion`` deleted, everything else as it was."""
    facts = dict(R.events[statement])
    facts[A.SCOPE_TARGETS] = tuple(member for member in facts[A.SCOPE_TARGETS] if member.value != lesion)
    return replace(R, events={**R.events, statement: facts})


def without_place(R, lesion, place):
    """9.4's deleted member, on a lesion's places: ``place`` deleted, the pair controls left as they were."""
    facts = dict(R.lesions[lesion])
    facts[A.PLACES] = tuple(member for member in facts[A.PLACES] if member.value is not place)
    return replace(R, lesions={**R.lesions, lesion: facts})


INDEPENDENT, SAME, UNRESOLVED = pairing.RowResult.INDEPENDENT, pairing.RowResult.SAME, pairing.RowResult.UNRESOLVED


class R2FLListedArmTests(SimpleTestCase):
    def test_rfl_a_listed_lesion_never_asked_is_set_apart_by_its_places(self):
        # L1 (transverse colon) by its established act-lesion pair; L2 (cecum) - never asked, the tattoo's transverse
        # colon not compatible with it - by its place, disjoint from the tattoo's and asked of it by a rejected control
        R = listed()
        self.assertEqual(target(R), INDEPENDENT)
        self.assertEqual(pairing.relation(R, E3, E4).relation, pairing.Relation.INDEPENDENT)

    def test_rfl_deleting_a_listed_lesion_never_releases_a_held_listing(self):
        # each listing is held, and so is each deletion of a listed lesion: a lesion the act was asked about or
        # controlled against is read whether or not it is still listed (r2e's arm released each of these deletions)
        cases = {
            "L2's place control not rejected": listed(controls={(E4, A.DISTINCT_FROM, L1): True,
                                                               (E4, A.TARGET_PLACES, LM.CECUM): False}),
            "L2 at an anastomosis, which overlaps the tattoo's place": listed(
                l2_places=(LM.ANASTOMOSIS,), controls={(E4, A.DISTINCT_FROM, L1): True,
                                                       (E4, A.TARGET_PLACES, LM.ANASTOMOSIS): True}),
            "one of L2's places asked of the tattoo, the other never": listed(
                l2_places=(LM.CECUM, LM.ASCENDING_COLON), denial_places=(LM.TRANSVERSE_COLON, LM.CECUM)),
            "L1's act-lesion pair not established": listed(controls={(E4, A.DISTINCT_FROM, L1): False,
                                                                    (E4, A.TARGET_PLACES, LM.CECUM): True}),
        }
        for name, R in cases.items():
            for lesion in (None, L1, L2):
                with self.subTest(case=name, deleted=str(lesion)):
                    found = target(R if lesion is None else without_target(R, lesion))
                    self.assertNotEqual(found, INDEPENDENT)

    def test_rfl_every_place_pair_control_asked_of_the_act_is_read(self):
        # both listed lesions established not-on, but a place pair control asked of the tattoo (here about the rectum,
        # a place another pair asked) is not rejected: the every-control scan holds the pair (DECISIONS D220, D236)
        controls = {(E4, A.DISTINCT_FROM, L1): True, (E4, A.DISTINCT_FROM, L2): True,
                    (E4, A.TARGET_PLACES, LM.RECTUM): False}
        R = listed(l2_places=(LM.TRANSVERSE_COLON,), controls=controls)
        self.assertNotEqual(target(R), INDEPENDENT)
        self.assertEqual(target(listed(l2_places=(LM.TRANSVERSE_COLON,),
                                       controls={**controls, (E4, A.TARGET_PLACES, LM.RECTUM): True})), INDEPENDENT)

    def test_rfl_a_lesion_the_act_was_controlled_against_is_read_listed_or_not(self):
        # L5, listed by nothing, at an anastomosis the tattoo was asked about: not set apart (an anastomosis is never
        # disjoint from anything), so it holds the pair as a deleted listed lesion would; placed in the rectum, apart
        controls = {(E4, A.DISTINCT_FROM, L1): True, (E4, A.DISTINCT_FROM, L2): True}
        for place, expected in ((LM.ANASTOMOSIS, False), (LM.RECTUM, True)):
            with self.subTest(place=place.value):
                R = listed(l2_places=(LM.TRANSVERSE_COLON,), lesions={
                    L5: EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(place)])},
                    controls={**controls, (E4, A.TARGET_PLACES, place): True})
                self.assertIs(target(R) is INDEPENDENT, expected)

    def test_rfl_a_lesion_the_act_was_asked_about_is_read_by_its_pair_alone(self):
        # the boundary: L1 was asked (its act-lesion pair not established: pass 2 left it unclear), so it is never set
        # apart by its places, though they would read apart (its transverse colon denied, its cecum disjoint from the
        # tattoo's and asked of it by a rejected control); with its pair established, apart
        R = listed(l2_places=(LM.TRANSVERSE_COLON,), controls={
            (E4, A.DISTINCT_FROM, L1): False, (E4, A.DISTINCT_FROM, L2): True, (E4, A.TARGET_PLACES, LM.CECUM): True})
        R = replace(R, lesions={**R.lesions, L1: {**R.lesions[L1], A.PLACES: (sup(LM.CECUM),
                                                                              EF.neg(LM.TRANSVERSE_COLON))}})
        self.assertNotEqual(target(R), INDEPENDENT)
        self.assertEqual(target(replace(R, pair_controls={**R.pair_controls, (E4, A.DISTINCT_FROM, L1): True})),
                         INDEPENDENT)

    def test_rfl_a_lesion_not_established_single_is_never_set_apart_by_its_places(self):
        # the boundary: L2 a group in the cecum - its place list may omit where one of its members lies, and nothing asks
        # the tattoo about such a member - or L2 with its multiplicity unresolved or never filed: only an established
        # not-on (D305's membership form) would set it apart, as D300 RF-L3 and D302 RF2C-L1 read a group
        R = listed()  # single, L2 is set apart by its place (test_rfl_a_listed_lesion_never_asked_is_set_apart_...)
        facts = dict(R.lesions[L2])
        for name, multiplicity in (('a group', (sup(GROUP),)), ('unresolved', (unres(SINGLE),)), ('none filed', None)):
            changed = {**facts, A.MULTIPLICITY: multiplicity} if multiplicity is not None else {
                attribute: found for attribute, found in facts.items() if attribute is not A.MULTIPLICITY}
            with self.subTest(multiplicity=name):
                self.assertNotEqual(target(replace(R, lesions={**R.lesions, L2: changed})), INDEPENDENT)

    def test_rfl_a_deleted_lesion_place_leaves_its_unrejected_control_read(self):
        # the boundary of 9.4's own deletion (a lesion's places): L2 in the cecum and the ascending colon, the tattoo
        # asked about both and the ascending colon's control not rejected - deleting the ascending colon from L2's
        # places leaves that control read, so the pair stays together
        R = listed(l2_places=(LM.CECUM, LM.ASCENDING_COLON),
                   controls={(E4, A.DISTINCT_FROM, L1): True, (E4, A.TARGET_PLACES, LM.CECUM): True,
                             (E4, A.TARGET_PLACES, LM.ASCENDING_COLON): False})
        self.assertNotEqual(target(R), INDEPENDENT)
        self.assertNotEqual(target(without_place(R, L2, LM.ASCENDING_COLON)), INDEPENDENT)

    def test_rfl_a_lesion_no_claim_or_control_asks_about_holds_the_listing(self):
        # the boundary: L2 in the cecum, the denial placed only at L1's place - no claim and no control asks the tattoo
        # about L2 - so nothing sets L2 apart (an omitted place, 4.11); and L2 with no place at all, likewise
        for name, R in (('unplaced', listed(denial_places=(LM.TRANSVERSE_COLON,), controls={
                            (E4, A.DISTINCT_FROM, L1): True})),
                        ('no place', listed(l2_places=(), controls={(E4, A.DISTINCT_FROM, L1): True}))):
            with self.subTest(case=name):
                self.assertNotEqual(target(R), INDEPENDENT)

    def test_rfl_an_unestablished_place_reading_sets_nothing_apart(self):
        # the boundary: L2's place or the tattoo's place unresolved, or L2's control never generated
        R = listed()
        cases = {
            "L2's place unresolved": replace(R, lesions={**R.lesions, L2: {**R.lesions[L2],
                                                                          A.PLACES: (unres(LM.CECUM),)}}),
            "the tattoo's place unresolved": listed(tattoo=(unres(LM.TRANSVERSE_COLON),)),
            "L2's control never generated": listed(controls={(E4, A.DISTINCT_FROM, L1): True}),
        }
        for name, found in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(target(found), INDEPENDENT)

    def test_rfl_a_listing_asked_in_full_is_read_as_before(self):
        # the boundary: both lesions in the tattoo's segment, each asked and established (e-lesion's own shape), and
        # one of them not established
        both = {(E4, A.DISTINCT_FROM, L1): True, (E4, A.DISTINCT_FROM, L2): True}
        self.assertEqual(target(listed(l2_places=(LM.TRANSVERSE_COLON,), controls=both)), INDEPENDENT)
        self.assertNotEqual(target(listed(l2_places=(LM.TRANSVERSE_COLON,),
                                          controls={**both, (E4, A.DISTINCT_FROM, L2): False})), INDEPENDENT)

    def test_rfl_a_single_target_is_read_as_before(self):
        # the boundary: the place reading is the listed arm's; a single target on L2 (cecum, the denial unplaced)
        # beside the tattoo, its place control rejected but no act-lesion pair, is set apart by nothing new
        doc = EF.colonoscopy(places=[sup(LM.TRANSVERSE_COLON)])
        doc.lesions[L1] = EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(LM.TRANSVERSE_COLON)])
        doc.lesion(2, multiplicity=sup(SINGLE), lesion_places=[sup(LM.CECUM)])
        doc.act(3, ct.Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
                lesion=sup(L2))
        doc.act(4, ct.Kind.TATTOO, places=[sup(LM.TRANSVERSE_COLON)])
        doc.controls[(E4, A.TARGET_PLACES, LM.CECUM)] = True
        self.assertNotEqual(target(doc.build()), INDEPENDENT)


# --- RFE-L1: the refutation's input, end to end -----------------------------------------------------------------------

Q01_FIRST = 'A 7 mm polyp in the cecum was removed with a cold snare.'
Q01_TATTOO = 'The transverse colon was tattooed 3 cm distal to the second polypectomy site.'
Q01 = R2EL.note(Q01_FIRST,                                                                     # S5: E2 on L1 (cecum)
                'A 5 mm polyp in the transverse colon was removed with a cold snare.',         # S6: E3 on L2
                'No lifting injection was used for either polyp.',                             # S7: E4 denies L1, L2
                Q01_TATTOO)                                                                    # S8: E5, no lesion


def q01_answer(*, placed=True):
    """The refutation's q01 answer: E2 and E3 remove L1 (cecum) and L2 (transverse colon); E4 denies a lifting
    injection on both (listed targets; ``placed``: placed at both polyps' places, as pass 1 places it from the removals'
    sentences); E5 a tattoo in the transverse colon naming no lesion."""
    over = dict(session=[fact('X1', src(['S7']))],
                scope__breadth=[fact('listed_targets', src(['S7'], 'either polyp'))], scope__targets=['L1', 'L2'])
    if placed:
        over['target__places'] = [fact('cecum', src(['S5'], 'cecum', 'placing')),
                                  fact('transverse_colon', src(['S6'], 'transverse colon', 'placing'))]
    denial = event('E4', ['S7'], 'lifting injection', 'was used', 'injection', state='negated',
                   status_source=src(['S7'], 'was used'), **over)
    return R2EL.colonoscopy(Q01, R2EL.removal('E2', 'S5', 'L1', 'A 7 mm polyp', 'cecum', 'cecum'),
                            R2EL.removal('E3', 'S6', 'L2', 'A 5 mm polyp', 'transverse_colon', 'transverse colon'),
                            denial, R2EL.tattoo('E5', 'S8'),
                            lesions=[R2EL.entry('L1', 'S5', 'A 7 mm polyp', place='cecum', place_words='cecum'),
                                     R2EL.entry('L2', 'S6', 'A 5 mm polyp', place='transverse_colon',
                                                place_words='transverse colon')])


class R2FLListedPipelineTests(SimpleTestCase):
    def test_rfl_the_refutations_listed_denial_releases_the_tattoo(self):
        claim_set, _out, R, _view = R2EL.run(Q01, q01_answer(), R2EL.FAITHFUL)
        # the claim set as r2e built it (no request change): only the transverse polyp asked, the cecum controlled
        self.assertEqual([(pair.act, pair.lesion) for pair in claim_set.act_lesions], [('E5', 'L2')])
        self.assertIs(R.pair_controls[(E5, A.TARGET_PLACES, LM.CECUM)], True)
        self.assertEqual(target(R, Id.parse('E4'), E5), INDEPENDENT)
        found = R2EL.outcomes(Q01, q01_answer(), R2EL.FAITHFUL, ('45381', Q01_TATTOO))
        self.assertEqual(found['45381'][:2], ('ready', ()))

    def test_rfl_deleting_either_listed_polyp_releases_nothing_the_listing_does_not(self):
        # the refutation's q02: no deletion of an established listed member releases what the listing holds - the
        # listing and the deletion of the cecal polyp L1 answer alike (apart). DECISIONS D311 R2F2-L1 (restated by its
        # owner, lane f-lesion2; L2's deletion INDEPENDENT -> held): only the statement's OWN lesions read by an
        # established not-on answer its places, so with the transverse polyp L2 deleted from the list the tattoo's
        # transverse colon - one of the denial's own places, asked of it by no control - is answered by nothing: the
        # deletion holds (a weakening that holds, never one that releases)
        _claim_set, _out, R, _view = R2EL.run(Q01, q01_answer(), R2EL.FAITHFUL)
        denial = Id.parse('E4')
        for lesion, apart in ((None, True), (L1, True), (L2, False)):
            with self.subTest(deleted=str(lesion)):
                found = R if lesion is None else without_target(R, lesion, statement=denial)
                self.assertIs(target(found, denial, E5) is INDEPENDENT, apart)

    def test_rfl_a_tattoo_on_the_cecal_polyps_place_stays_held(self):
        # the boundary: pass 2 does not reject that the tattoo was done in the cecum (the place control supported):
        # the cecal polyp is set apart by nothing, and the denial contradicts the tattoo as before
        def oracle(claim, role, claim_set):
            if role == 'pair_control' and claim.subject == 'E5' and claim.value == 'cecum':
                return verdict(claim, 'supports')
            return R2EL.FAITHFUL(claim, role, claim_set)
        found = R2EL.outcomes(Q01, q01_answer(), oracle, ('45381', Q01_TATTOO))
        self.assertEqual(found['45381'][:2], ('needs_clarification', ('relation:contradiction',)))

    def test_rfl_an_unplaced_listing_stays_held(self):
        # the boundary: the denial unplaced, nothing asks the tattoo about the cecal polyp (no claim, no control), so
        # nothing sets it apart: held as before
        found = R2EL.outcomes(Q01, q01_answer(placed=False), R2EL.FAITHFUL, ('45381', Q01_TATTOO))
        self.assertEqual(found['45381'][:2], ('needs_clarification', ('relation:unresolved',)))


# --- RFE-L2: the presumed multiplicities move with 9.4's weakenings in the property harness ----------------------------

def presumed_weakenings(TP, R, lesion):
    """Every single 9.4 weakening of ``lesion``'s multiplicity in ``R``, as the property harness makes it."""
    return [(label, weak) for label, weak, what in TP.weakenings(R)
            if isinstance(what, tuple) and len(what) == 4 and what[:2] == (lesion, A.MULTIPLICITY)]


class R2FLPresumptionTests(SimpleTestCase):
    def setUp(self):
        self.TP = properties()

    def test_rfl_a_weakened_presumed_multiplicity_takes_the_release_away(self):
        # the refutation's q04, and D300's fixture alike: the release rests on L1 established single (the act-lesion
        # single form; the membership of the act's lesion), so each weakening of L1's multiplicity takes it away
        TP = self.TP
        for name, key, code in ((TP.ACT_LESION_FIXTURE, (E4, A.DISTINCT_FROM, L1), '45381'),
                                (TP.LESION_PAIR_FIXTURE, (L3, A.DISTINCT_FROM, L1), '45385')):
            R, codes = TP.fixture(name)
            self.assertIn(code, TP.ready(TP.assessed(R, codes)))
            weakened = presumed_weakenings(TP, R, L1)
            self.assertEqual(len(weakened), 7, name)  # the four of 9.4 and AMENDMENT-2 4.4's three
            for label, weak in weakened:
                with self.subTest(fixture=name, weakening=label):
                    self.assertIs(weak.pair_controls[key], False)
                    self.assertNotIn(code, TP.ready(TP.assessed(weak, codes)))

    def test_rfl_a_multiplicity_the_form_does_not_presume_leaves_the_release(self):
        # the boundary: D300's group L3 (its membership form presumes nothing of the group) and an act-lesion pair of
        # the membership form (L1 a group: "This act was not done on any of the lesions of L1.") - weakening that
        # multiplicity leaves the outcome and the release as they were
        TP = self.TP
        R, codes = TP.fixture(TP.LESION_PAIR_FIXTURE)
        for label, weak in presumed_weakenings(TP, R, L3):
            with self.subTest(fixture='D300', weakening=label):
                self.assertIs(weak.pair_controls[(L3, A.DISTINCT_FROM, L1)], True)
                self.assertIn('45385', TP.ready(TP.assessed(weak, codes)))
        R, codes = TP.fixture(TP.ACT_LESION_FIXTURE)
        group = replace(R, lesions={**R.lesions, L1: {**R.lesions[L1], A.MULTIPLICITY: (sup(GROUP),)}})
        self.assertIn('45381', TP.ready(TP.assessed(group, codes)))
        weakened = presumed_weakenings(TP, group, L1)
        self.assertTrue(weakened)
        for label, weak in weakened:
            with self.subTest(fixture='D305, membership form', weakening=label):
                self.assertIs(weak.pair_controls[(E4, A.DISTINCT_FROM, L1)], True)
                self.assertIn('45381', TP.ready(TP.assessed(weak, codes)))

    def test_rfl_the_harness_reads_the_presumption_through_engine_facts(self):
        # the positive control: engine/facts' presumption readers presuming nothing for the call, the harness's
        # re-derived outcome stands under the same weakening - it reads the engine's presumption, not a copy of it
        TP = self.TP
        R, codes = TP.fixture(TP.ACT_LESION_FIXTURE)
        with mock.patch.object(F, '_act_lesion_presumes', lambda claim, where: False):
            for label, weak in presumed_weakenings(TP, R, L1):
                with self.subTest(weakening=label):
                    self.assertIs(weak.pair_controls[(E4, A.DISTINCT_FROM, L1)], True)
        R, codes = TP.fixture(TP.LESION_PAIR_FIXTURE)
        with mock.patch.object(F, '_lesion_pair_presumes', lambda claim, where: 0):
            for label, weak in presumed_weakenings(TP, R, L1):
                with self.subTest(weakening=label):
                    self.assertIs(weak.pair_controls[(L3, A.DISTINCT_FROM, L1)], True)

    def test_rfl_the_harness_names_the_form_the_claim_set_asked(self):
        # rederived's form - the one presuming most under which engine/facts reads the stored outcome - is the form
        # contract/claims asked, on rows settled end to end: P4's act-lesion pair (L1 single, then a group) and r2c's
        # membership pair (L1 a group, L2 removed)
        TP = self.TP
        rederived = getattr(TP, 'rederived', None)
        self.assertIsNotNone(rederived, 'the property harness re-derives no pair-type outcome')
        cases = [(R2EL.P4, R2EL.p4_answer(multiplicity=multiplicity), (E4, A.DISTINCT_FROM, L1), R2CL.FAITHFUL)
                 for multiplicity in ('single', 'group')]
        cases.append((R2CL.MEMBER, R2CL.member_answer(), (L1, A.DISTINCT_FROM, L2), R2CL.oracle(member=False)))
        for text, data, key, oracle in cases:
            claim_set, _out, R, _view = R2CL.run(text, data, oracle)
            pairs = list(getattr(claim_set, 'act_lesions', ())) + list(claim_set.lesion_pairs)
            [asked] = [claim_set.claim(pair.claim).template for pair in pairs]
            with self.subTest(key=str(key), asked=asked):
                self.assertIs(R.pair_controls[key], True)
                forms = TP.PAIR_TYPE_FORMS[key[0].family]
                named = next(form for form in forms if TP.pair_type_outcome(key, form, R.lesions))
                self.assertEqual(named, asked)

    def test_rfl_the_listed_fixture_carries_both_readings(self):
        # RFE-L1's fixture in the property harness: 45381 READY by the act-lesion pair and the place reading together,
        # each of them not established taking it away, and no single weakening releasing anything
        TP = self.TP
        R, codes = TP.fixture(TP.LISTED_FIXTURE)
        self.assertIn('45381', TP.ready(TP.assessed(R, codes)))
        for key in ((E4, A.DISTINCT_FROM, L1), (E4, A.TARGET_PLACES, LM.CECUM)):
            with self.subTest(key=str(key)):
                self.assertIs(R.pair_controls[key], True)
                weak = replace(R, pair_controls={**R.pair_controls, key: False})
                self.assertNotIn('45381', TP.ready(TP.assessed(weak, codes)))
        for label, weak in presumed_weakenings(TP, R, L1):  # the single form presumes L1 single (RFE-L2)
            with self.subTest(weakening=label):
                self.assertNotIn('45381', TP.ready(TP.assessed(weak, codes)))
        before = TP.assessed(R, codes)
        checked = 0
        for label, weak, _what in TP.weakenings(R):
            after = TP.assessed(weak, codes)
            checked += 1
            with self.subTest(weakening=label):
                self.assertLessEqual(TP.ready(after), TP.ready(before))
                self.assertLessEqual(TP.excluded(after), TP.excluded(before))
        self.assertGreater(checked, 100)


# --- round r2f's refutation, RF2F-L1: the place reading reads the listed lesion's FINDING -----------------------------

L7, L9 = Id.parse('L7'), Id.parse('L9')
# A same_as member whose value is empty (DECISIONS D302 RF2C-L2: it may name any one lesion, an id the FactSet does not
# hold): left unresolved by pass 2, its value never readable.
UNNAMED = Fact(result=ct.Result.UNRESOLVED, value=None, state=ct.FactState.SUPPORTED, options=(),
               reasons=(ct.Reason.APPRAISAL_UNCLEAR,), spans=(), cited=(), inherited_from=None)


def claims_controls(statement, statement_places, act, act_places, verdict_of=lambda subject, place: True):
    """The place pair controls contract/claims.pair makes between ``statement`` and ``act`` (test_pairing's
    claims_pair_controls: each object asked about every place of the other none of its own places is compatible with),
    ``verdict_of(subject, place)`` pass 2's answer (True: rejected)."""
    from tests.v2 import test_pairing
    return test_pairing.claims_pair_controls(statement, statement_places, act, act_places, verdict_of)


def finding(*, l2_places=(LM.CECUM,), same_as=None, entries=None, denial_places=None, extra_controls=None):
    """listed() with L2's FINDING varied: L1 (single, transverse colon) set apart by its established act-lesion pair;
    L2 (single) in ``l2_places`` with ``same_as`` its same_as members; ``entries`` further lesion entries (an entry of
    L2's finding, or a lesion of its own); E3 the listed denial on L1 and L2, placed at ``denial_places`` (by default
    every place of L1 and L2); E4 the tattoo in the transverse colon naming no lesion. The place pair controls are the
    ones contract/claims.pair makes from the two objects' places, every one rejected; ``extra_controls`` adds or
    changes some."""
    places = denial_places if denial_places is not None else (LM.TRANSVERSE_COLON, *l2_places)
    controls = {(E4, A.DISTINCT_FROM, L1): True,
                **claims_controls(E3, places, E4, (LM.TRANSVERSE_COLON,)), **(extra_controls or {})}
    R = listed(l2_places=l2_places, denial_places=places, controls=controls, lesions=entries)
    if same_as is not None:
        R = replace(R, lesions={**R.lesions, L2: {**R.lesions[L2], A.SAME_AS: tuple(same_as)}})
    return R


def entry_at(*places, multiplicity=sup(SINGLE), same_as=None):
    """One lesion entry's facts: ``places`` (Facts), ``multiplicity`` (a Fact, or None for none filed)."""
    return EF.facts_of(multiplicity=multiplicity, lesion_places=list(places), same_as=same_as)


def verifier_scene(*, l2_places=(LM.DESCENDING_COLON,), denial_places=(LM.SIGMOID_COLON, LM.DESCENDING_COLON,
                   LM.SPLENIC_FLEXURE), extra=None, l2_same_as=None, act_kind=ct.Kind.TATTOO):
    """The verifier's engine scene for RF2F-L1 (its v01): E2 a cold snare of L1 (sigmoid colon, single); L2 a flat
    polyp (single) in ``l2_places``; E3 a listed denial that an injection was performed on L1 and L2, placed at
    ``denial_places`` (so 4.2's statement-place arm cannot set it apart); E4 an act of ``act_kind`` at the splenic
    flexure naming no lesion; the place pair controls claims.pair makes, rejected; no act-lesion claim."""
    doc = EF.colonoscopy(places=[sup(LM.SIGMOID_COLON)])
    doc.lesions[L1] = EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(LM.SIGMOID_COLON)])
    doc.lesions[L2] = EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(place) for place in l2_places],
                                  same_as=l2_same_as)
    doc.lesions.update(extra or {})
    doc.act(3, ct.Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.LISTED_TARGETS),
            targets=[sup(L1), sup(L2)], places=[sup(place) for place in denial_places])
    doc.act(4, act_kind, places=[sup(LM.SPLENIC_FLEXURE)])
    doc.controls.update(claims_controls(E3, denial_places, E4, (LM.SPLENIC_FLEXURE,)))
    return doc.build()


class R2FLFindingTests(SimpleTestCase):
    def test_rflr_a_listed_lesions_finding_at_the_acts_place_holds_as_one_entry_does(self):
        # the refutation's input: L2 (cecum) filed as one entry reaching the tattoo's transverse colon, or as two
        # entries joined by same_as (either list), or with an entry whose places are not established or that the
        # FactSet does not hold: the one-entry filing holds, and so does every two-entry filing (the build released
        # each: L2's own place list, the cecum, read apart)
        one = finding(l2_places=(LM.CECUM, LM.TRANSVERSE_COLON))
        self.assertEqual(target(one), SAME)
        cases = {
            'two entries, same_as in L2': finding(same_as=[sup(L3)], entries={L3: entry_at(sup(LM.TRANSVERSE_COLON))}),
            "two entries, same_as in L3's list": finding(entries={L3: entry_at(sup(LM.TRANSVERSE_COLON),
                                                                               same_as=[sup(L2)])}),
            'same_as an id the FactSet does not hold': finding(same_as=[sup(L9)]),
            "the other entry's place unresolved": finding(same_as=[sup(L3)],
                                                          entries={L3: entry_at(unres(LM.TRANSVERSE_COLON))}),
            'the other entry filed with no place': finding(same_as=[sup(L3)], entries={L3: entry_at()}),
            'same_as an unnamed member': finding(same_as=[UNNAMED]),
            'same_as established negated (any state joins)': finding(same_as=[EF.neg(L3)],
                                                                     entries={L3: entry_at(sup(LM.TRANSVERSE_COLON))}),
            'same_as left unresolved': finding(same_as=[unres(L3)], entries={L3: entry_at(sup(LM.TRANSVERSE_COLON))}),
            'the other entry at a place no control asks the tattoo about': finding(
                same_as=[sup(L3)], entries={L3: entry_at(sup(LM.ASCENDING_COLON))}),
        }
        for name, R in cases.items():
            with self.subTest(case=name):
                self.assertNotEqual(target(R), INDEPENDENT)
                self.assertNotEqual(pairing.relation(R, E3, E4).relation, pairing.Relation.INDEPENDENT)

    def test_rflr_the_verifiers_scene_holds_every_finding_the_class_rule_holds(self):
        # the verifier's v01, case by case: held wherever L2's finding reaches the act's place, has an entry without
        # established places, an unknown id, or a place no control asks; apart (J, K) where every place of every entry
        # is disjoint and asked by a rejected control
        L3_SPLENIC = {L3: entry_at(sup(LM.SPLENIC_FLEXURE))}
        cases = [
            ('A one entry', verifier_scene(l2_places=(LM.DESCENDING_COLON, LM.SPLENIC_FLEXURE)), False),
            ('B two entries', verifier_scene(l2_same_as=[sup(L3)], extra=L3_SPLENIC), False),
            ("C in L3's list", verifier_scene(extra={L3: entry_at(sup(LM.SPLENIC_FLEXURE), same_as=[sup(L2)])}), False),
            ('D an id not held', verifier_scene(l2_same_as=[sup(L7)]), False),
            ("E L3's place unresolved", verifier_scene(l2_same_as=[sup(L3)],
                                                       extra={L3: entry_at(unres(LM.SPLENIC_FLEXURE))}), False),
            ('F L3 with no place', verifier_scene(l2_same_as=[sup(L3)], extra={L3: entry_at()}), False),
            ('G an unnamed member', verifier_scene(l2_same_as=[UNNAMED]), False),
            ('H a negated member', verifier_scene(l2_same_as=[EF.neg(L3)], extra=L3_SPLENIC), False),
            ('I an uncontrolled finding place', verifier_scene(l2_same_as=[sup(L3)],
                                                               extra={L3: entry_at(sup(LM.TRANSVERSE_COLON))}), False),
            # DECISIONS D311 R2F2-L1 (round r2f's second refutation; restated by their owner, lane f-lesion2): J and K
            # were pinned apart (True) on the first verifier's class rule, which read the lesions' side only; the
            # denial is placed at the act's splenic flexure too, so claims.pair never asks it about that place and no
            # listed lesion is there by an established not-on - SC-B's second direction is unmet, held (True -> False).
            # Their twins without the splenic flexure on the denial stay apart (R2FMStatementSideTests).
            ('J every place controlled', verifier_scene(
                l2_same_as=[sup(L3)], extra={L3: entry_at(sup(LM.TRANSVERSE_COLON))},
                denial_places=(LM.SIGMOID_COLON, LM.DESCENDING_COLON, LM.TRANSVERSE_COLON, LM.SPLENIC_FLEXURE)), False),
            ('K the base', verifier_scene(), False),
            ('L as B, an injection', verifier_scene(l2_same_as=[sup(L3)], extra=L3_SPLENIC,
                                                    act_kind=ct.Kind.INJECTION), False),
            ('M as A, an injection', verifier_scene(l2_places=(LM.DESCENDING_COLON, LM.SPLENIC_FLEXURE),
                                                    act_kind=ct.Kind.INJECTION), False),
        ]
        for name, R, apart in cases:
            with self.subTest(case=name):
                self.assertIs(target(R) is INDEPENDENT, apart)

    def test_rflr_a_finding_apart_at_every_place_of_every_entry_is_set_apart(self):
        # the boundary: L2's finding of two entries, the other one in the ascending colon, the denial placed there too
        # (so the tattoo is asked about it, rejected): every place of every entry disjoint and controlled - apart, as
        # before; and the base (one entry, no same_as)
        R = finding(same_as=[sup(L3)], entries={L3: entry_at(sup(LM.ASCENDING_COLON))},
                    denial_places=(LM.TRANSVERSE_COLON, LM.CECUM, LM.ASCENDING_COLON))
        self.assertEqual(target(R), INDEPENDENT)
        self.assertEqual(target(finding()), INDEPENDENT)
        # one of those controls not rejected, or the ascending colon's never generated: held
        for change in ({(E4, A.TARGET_PLACES, LM.ASCENDING_COLON): False},):
            with self.subTest(change=str(change)):
                self.assertNotEqual(target(replace(R, pair_controls={**R.pair_controls, **change})), INDEPENDENT)
        missing = {key: value for key, value in R.pair_controls.items()
                   if key != (E4, A.TARGET_PLACES, LM.ASCENDING_COLON)}
        self.assertNotEqual(target(replace(R, pair_controls=missing)), INDEPENDENT)

    def test_rflr_every_entry_of_the_finding_is_established_single(self):
        # the boundary of the single condition over a finding: L2 (single) joined by same_as to L3, a group (or with its
        # multiplicity unresolved), in the ascending colon - disjoint and asked of the tattoo, rejected - and L3 itself
        # established not-on (its membership form): the finding's place list may omit where one of L3's members lies, so
        # L2 is set apart by its places only when every entry of its finding is established single (the build read L2's
        # own multiplicity and released)
        for name, multiplicity in (('a group', sup(GROUP)), ('unresolved', unres(SINGLE)), ('none filed', None)):
            with self.subTest(multiplicity=name):
                R = finding(same_as=[sup(L3)],
                            entries={L3: entry_at(sup(LM.ASCENDING_COLON), multiplicity=multiplicity)},
                            denial_places=(LM.TRANSVERSE_COLON, LM.CECUM, LM.ASCENDING_COLON),
                            extra_controls={(E4, A.DISTINCT_FROM, L3): True})
                self.assertNotEqual(target(R), INDEPENDENT)
        single = finding(same_as=[sup(L3)], entries={L3: entry_at(sup(LM.ASCENDING_COLON))},
                         denial_places=(LM.TRANSVERSE_COLON, LM.CECUM, LM.ASCENDING_COLON),
                         extra_controls={(E4, A.DISTINCT_FROM, L3): True})
        self.assertEqual(target(single), INDEPENDENT)

    def test_rflr_an_entry_read_by_its_own_pair_still_lends_its_places_to_the_finding(self):
        # L3, joined to L2 by same_as, is itself established not-on (an act-lesion pair) and so read by that pair; L2 is
        # still read by its FINDING's places, L3's among them: L3 in the ascending colon never asked of the tattoo, or
        # at an anastomosis (asked and rejected, but never disjoint from the tattoo's place) - held (the build read L2's
        # own cecum and released); L3's ascending colon asked and rejected - apart
        pair = {(E4, A.DISTINCT_FROM, L3): True}
        cases = [('never asked', LM.ASCENDING_COLON, (LM.TRANSVERSE_COLON, LM.CECUM), False),
                 ('an anastomosis', LM.ANASTOMOSIS, (LM.TRANSVERSE_COLON, LM.CECUM, LM.ANASTOMOSIS), False),
                 ('asked and rejected', LM.ASCENDING_COLON, (LM.TRANSVERSE_COLON, LM.CECUM, LM.ASCENDING_COLON), True)]
        for name, place, denial_places, apart in cases:
            with self.subTest(l3=name):
                R = finding(same_as=[sup(L3)], entries={L3: entry_at(sup(place))}, denial_places=denial_places,
                            extra_controls=pair)
                self.assertIs(target(R) is INDEPENDENT, apart)

    def test_rflr_deleting_a_listed_lesion_leaves_its_finding_read(self):
        # 9.4's deleted member: L2 (listed, ascending colon, never asked of the tattoo) joined by same_as to L3 (listed
        # by nothing; transverse and descending colon - established not-on by its act-lesion pair, its descending colon
        # asked of the tattoo and rejected): the listing is held (L2's finding reaches the tattoo's place), and so is
        # the listing with L2 deleted - L2 is still read, its finding's descending colon controlled (the build dropped
        # it from the read set and released the deletion)
        R = finding(l2_places=(LM.ASCENDING_COLON,), same_as=[sup(L3)],
                    entries={L3: entry_at(sup(LM.TRANSVERSE_COLON), sup(LM.DESCENDING_COLON))},
                    denial_places=(LM.TRANSVERSE_COLON, LM.DESCENDING_COLON),
                    extra_controls={(E4, A.DISTINCT_FROM, L3): True})
        self.assertIs(R.pair_controls[(E4, A.TARGET_PLACES, LM.DESCENDING_COLON)], True)
        self.assertNotIn((E4, A.TARGET_PLACES, LM.ASCENDING_COLON), R.pair_controls)
        for lesion in (None, L2):
            with self.subTest(deleted=str(lesion)):
                self.assertNotEqual(target(R if lesion is None else without_target(R, lesion)), INDEPENDENT)

    def test_rflr_the_place_reading_and_the_read_set_read_one_finding(self):
        # the reading itself: facts.finding_places' entries, every place of every entry, and every entry read where one
        # of the finding's places was asked of the act (_controlled_against)
        R = finding(same_as=[sup(L3)], entries={L3: entry_at(sup(LM.ASCENDING_COLON))},
                    denial_places=(LM.TRANSVERSE_COLON, LM.CECUM, LM.ASCENDING_COLON))
        other = pairing._target(R, E4, pairing._Mode.SINGLE)
        self.assertEqual(F.finding(R, L2), (L2, L3))
        self.assertTrue(pairing._apart_by_lesion_places(R, E4, L2, other.places))
        self.assertEqual(pairing._controlled_against(R, E4), frozenset({L2, L3}))
        # the same finding with L3 also in the tattoo's transverse colon: neither entry is set apart by its places
        R = finding(same_as=[sup(L3)], entries={L3: entry_at(sup(LM.ASCENDING_COLON), sup(LM.TRANSVERSE_COLON))},
                    denial_places=(LM.TRANSVERSE_COLON, LM.CECUM, LM.ASCENDING_COLON))
        self.assertFalse(pairing._apart_by_lesion_places(R, E4, L2, other.places))
        self.assertFalse(pairing._apart_by_lesion_places(R, E4, L3, other.places))


# The refutation's shape end to end, a note of its own (fictional clinician): one flat polyp reaching the hepatic
# flexure, filed by pass 1 as ONE entry (two places) or as TWO entries joined by same_as.
FINDING_FLAT = 'A 30 mm flat polyp in the ascending colon was removed with a cold snare.'
FINDING_TATTOO = 'The hepatic flexure was tattooed beside the flat polyp.'
FINDING_NOTE = R2CL.note('A 3 mm polyp in the rectum was left in place.',                    # S5: L1
                         'A 4 mm polyp in the descending colon was left in place.',          # S6: L2
                         'A 5 mm polyp in the cecum was removed with a cold snare.',         # S7: E2 on L3
                         FINDING_FLAT,                                                       # S8: E3 on L4
                         'The flat polyp reached the hepatic flexure.',                      # S9
                         'No lifting injection was used for either removed polyp.',          # S10: E4 on L3, L4
                         FINDING_TATTOO)                                                     # S11: E5, no lesion


def finding_answer(*, two_entries):
    """FINDING_NOTE's answer: E2 and E3 remove L3 (cecum) and L4 (the flat polyp); E4 denies a lifting injection on both
    (listed targets), placed at every place of the polyps; E5 a tattoo at the hepatic flexure naming no lesion. The flat
    polyp is one entry (L4: ascending colon and hepatic flexure) or two (L4: ascending colon; L5 "The flat polyp": the
    hepatic flexure, same_as L4)."""
    denial = event('E4', ['S10'], 'lifting injection', 'was used', 'injection', state='negated',
                   status_source=src(['S10'], 'was used'), session=[fact('X1', src(['S10']))],
                   scope__breadth=[fact('listed_targets', src(['S10'], 'either removed polyp'))],
                   scope__targets=['L3', 'L4'],
                   target__places=[fact('cecum', src(['S7'], 'cecum', 'placing')),
                                   fact('ascending_colon', src(['S8'], 'ascending colon', 'placing')),
                                   fact('hepatic_flexure', src(['S9'], 'hepatic flexure', 'placing'))])
    tattoo = event('E5', ['S11'], 'tattooed', 'was tattooed', 'tattoo', session=[fact('X1', src(['S11']))],
                   target__places=[fact('hepatic_flexure', src(['S11'], 'hepatic flexure'))])
    lesions = [R2CL.entry('L1', 'S5', 'A 3 mm polyp', place='rectum', place_words='rectum'),
               R2CL.entry('L2', 'S6', 'A 4 mm polyp', place='descending_colon', place_words='descending colon'),
               R2CL.entry('L3', 'S7', 'A 5 mm polyp', place='cecum', place_words='cecum')]
    flat = R2CL.entry('L4', 'S8', 'A 30 mm flat polyp', place='ascending_colon', place_words='ascending colon')
    if two_entries:
        member = fact('L4', src(['S9'], 'The flat polyp'))
        lesions += [flat, R2CL.entry('L5', 'S9', 'The flat polyp', place='hepatic_flexure',
                                     place_words='hepatic flexure', same_as=[member])]
    else:
        flat['places'].append(fact('hepatic_flexure', src(['S9'], 'hepatic flexure')))
        lesions.append(flat)
    return R2CL.colonoscopy(FINDING_NOTE,
                            R2CL.removal('E2', 'S7', 'L3', 'A 5 mm polyp', 'cecum', 'cecum'),
                            R2CL.removal('E3', 'S8', 'L4', 'A 30 mm flat polyp', 'ascending_colon', 'ascending colon'),
                            denial, tattoo, lesions=lesions)


def done_on_the_flat_polyp(claim, role, claim_set):
    """Pass 2 FAITHFUL, except an act-lesion claim about L4 answered as a reader who judges the tattoo WAS done on the
    flat polyp (the claim contradicted, its control supported)."""
    for pair in getattr(claim_set, 'act_lesions', ()):
        if pair.lesion == 'L4' and claim.id == pair.claim:
            return verdict(claim, 'contradicts')
        if pair.lesion == 'L4' and claim.id == pair.control:
            return verdict(claim, 'supports')
    return R2CL.FAITHFUL(claim, role, claim_set)


class R2FLFindingPipelineTests(SimpleTestCase):
    def test_rflr_a_polyp_filed_as_two_entries_is_held_as_one_entry_is(self):
        # the same note and the same pass-2 judgment: the one-entry filing is asked (the act-lesion claim about L4)
        # and holds when pass 2 judges the tattoo was done on the flat polyp; the two-entry filing is asked nothing
        # (claims reads L4's own place, r2e's claim set, unchanged), and its finding reaches the tattoo's place through
        # L5 - held under either judgment (the build released both from L4's own place)
        # DECISIONS D311 R2F2-L1 (restated by its owner, lane f-lesion2; the one-entry faithful READY -> held): the flat
        # polyp's hepatic flexure place settles unresolved (geometry_statement: its source is S9, not L4's own sentence),
        # so it answers nothing on the statement's side - the tattoo's hepatic flexure is one of the denial's own
        # places, asked of it by no control: held (an unnecessary hold, the lane's NOTES question; the same tattoo
        # beside a polyp whose extent its own sentence states is READY, R2FMStatementSidePipelineTests)
        expected = {(False, 'faithful'): ('needs_clarification', ('relation:contradiction',)),
                    (False, 'done on it'): ('needs_clarification', ('relation:contradiction',)),
                    (True, 'faithful'): ('needs_clarification', ('relation:contradiction',)),
                    (True, 'done on it'): ('needs_clarification', ('relation:contradiction',))}
        for (two, name), outcome in expected.items():
            oracle = R2CL.FAITHFUL if name == 'faithful' else done_on_the_flat_polyp
            with self.subTest(two_entries=two, pass2=name):
                data = finding_answer(two_entries=two)
                claim_set, _out, R, _view = R2CL.run(FINDING_NOTE, data, oracle)
                asked = [(pair.act, pair.lesion) for pair in getattr(claim_set, 'act_lesions', ())]
                self.assertEqual(asked, [] if two else [('E5', 'L4')])
                if two:
                    self.assertEqual(F.finding(R, Id.parse('L4'))[:2], (Id.parse('L4'), Id.parse('L5')))
                found = R2CL.outcomes(FINDING_NOTE, data, oracle, ('45381', FINDING_TATTOO), ('45385', FINDING_FLAT))
                self.assertEqual(found['45381'][:2], outcome)
                self.assertEqual(found['45385'][0], 'ready')


# --- round r2f's refutation, RF2F-L2: the every-control scan reads the controls asked of EITHER object ----------------

def statement_scene(*, statement_verdict=True, l1_places=(LM.ASCENDING_COLON,), l2_places=(LM.CECUM,),
                    tattoo=(LM.TRANSVERSE_COLON,), act_lesion=None, extra_controls=None):
    """listed() with the denial placed at its lesions' places and the controls claims.pair makes both ways: the tattoo
    asked about each place of the denial (rejected), the DENIAL asked about each place of the tattoo none of its places
    is compatible with (``statement_verdict``: True rejected, False not); ``act_lesion`` the act-lesion pair (E4, L1)
    when given; ``extra_controls`` adds or changes some."""
    places = (*l1_places, *l2_places)
    controls = claims_controls(E3, places, E4, tattoo, lambda subject, place: True if subject == E4
                               else statement_verdict)
    if act_lesion is not None:
        controls[(E4, A.DISTINCT_FROM, L1)] = act_lesion
    controls.update(extra_controls or {})
    return listed(l1_places=l1_places, l2_places=l2_places, denial_places=places, tattoo=tattoo, controls=controls)


class R2FLStatementControlTests(SimpleTestCase):
    def test_rflr_a_statement_control_not_rejected_holds_the_listed_arm(self):
        # the refutation's input: L1 (ascending colon) and L2 (cecum), both apart by their places from the tattoo's
        # transverse colon, the denial asked whether it is about the transverse colon: rejected - apart (4.2's place arm
        # too); not rejected (supported, unclear or unanswered) - held, as 4.2's place arm holds it (the build released)
        rejected = statement_scene()
        self.assertIs(rejected.pair_controls[(E3, A.TARGET_PLACES, LM.TRANSVERSE_COLON)], True)
        self.assertEqual(target(rejected), INDEPENDENT)
        held = statement_scene(statement_verdict=False)
        self.assertEqual(target(held), UNRESOLVED)
        self.assertEqual(pairing.relation(held, E3, E4).relation, pairing.Relation.UNRESOLVED)

    def test_rflr_the_mixed_listing_reads_the_statement_control_too(self):
        # the refutation's mixed shape: L1 (transverse colon) set apart by its established act-lesion pair, L2 (cecum)
        # by its place; the tattoo in the transverse and the descending colon, the denial asked about the descending
        # colon (none of its places compatible with it): rejected - apart; not rejected - held (the build released)
        for verdict_, expected in ((True, True), (False, False)):
            with self.subTest(statement_control_rejected=verdict_):
                R = statement_scene(statement_verdict=verdict_, l1_places=(LM.TRANSVERSE_COLON,),
                                    tattoo=(LM.TRANSVERSE_COLON, LM.DESCENDING_COLON), act_lesion=True)
                self.assertIn((E3, A.TARGET_PLACES, LM.DESCENDING_COLON), R.pair_controls)
                self.assertIs(target(R) is INDEPENDENT, expected)

    def test_rflr_every_place_pair_control_asked_of_the_statement_is_read(self):
        # the scan reads EVERY place pair control asked of either object, whichever pair made it
        # (facts.apart_by_controls, D220, kept by D236): one asked of the denial about the rectum (another act's place)
        # not rejected holds the pair; rejected, apart
        for verdict_, expected in ((False, False), (True, True)):
            with self.subTest(rejected=verdict_):
                R = statement_scene(extra_controls={(E3, A.TARGET_PLACES, LM.RECTUM): verdict_})
                self.assertIs(target(R) is INDEPENDENT, expected)

    def test_rflr_the_verifiers_scene_reads_the_statement_control(self):
        # the verifier's v01: E3 denies an injection on L1 (descending colon) and L2 (rectum), placed at their places;
        # E4 a tattoo at the splenic flexure naming no lesion; the tattoo asked about both places, rejected, and the
        # statement asked about the splenic flexure
        def scene(controls, statement_places=(LM.DESCENDING_COLON, LM.RECTUM)):
            doc = EF.colonoscopy(places=[sup(LM.DESCENDING_COLON)])
            doc.lesions[L1] = EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(LM.DESCENDING_COLON)])
            doc.lesion(2, multiplicity=sup(SINGLE), lesion_places=[sup(LM.RECTUM)])
            doc.act(3, ct.Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.LISTED_TARGETS),
                    targets=[sup(L1), sup(L2)], places=[sup(place) for place in statement_places])
            doc.act(4, ct.Kind.TATTOO, places=[sup(LM.SPLENIC_FLEXURE)])
            doc.controls.update(controls)
            return doc.build()

        act_side = {(E4, A.TARGET_PLACES, LM.DESCENDING_COLON): True, (E4, A.TARGET_PLACES, LM.RECTUM): True}
        statement = (E3, A.TARGET_PLACES, LM.SPLENIC_FLEXURE)
        cases = [
            ('(a) every control rejected', scene({**act_side, statement: True}), True),
            ('(b) the statement control not rejected', scene({**act_side, statement: False}), False),
            ('(d) an act control not rejected', scene({**act_side, (E4, A.TARGET_PLACES, LM.RECTUM): False,
                                                       statement: True}), False),
            # DECISIONS D311 R2F2-L1 (restated by their owner, lane f-lesion2; True -> False): an unplaced statement is
            # asked about no place of the act (claims.pair asks only between two placed objects), so nothing
            # establishes that it does not cover the tattoo's splenic flexure - held (4.11)
            ('(e) the statement unplaced', scene(dict(act_side), statement_places=()), False),
            ('(f) an unrelated act control not rejected', scene({**act_side, statement: True,
                                                                 (E4, A.TARGET_PLACES, LM.CECUM): False}), False),
            ('(g) (b) beside an unrelated act control rejected', scene({**act_side, statement: False,
                                                                        (E4, A.TARGET_PLACES, LM.CECUM): True}), False),
        ]
        for name, R, apart in cases:
            with self.subTest(case=name):
                self.assertIs(target(R) is INDEPENDENT, apart)

    def test_rflr_p_unknown_target_on_the_place_reading_with_the_statement_placed(self):
        # 9.4's P-UNKNOWN-TARGET, each pair control claims.pair makes flipped to not rejected, on test_pairing's own
        # builders: the place reading's scene (L1 rectum, L3 cecum, both single, beside an act in the sigmoid colon
        # naming no lesion) with the denial placed at its lesions' places, so the statement is asked about the act's
        # place
        from tests.v2 import test_pairing as TPG
        single = (TPG.sup(ct.Multiplicity.SINGLE),)
        lesions = {TPG.L1: {A.PLACES: (TPG.sup(LM.RECTUM),), A.MULTIPLICITY: single},
                   TPG.L3: {A.PLACES: (TPG.sup(LM.CECUM),), A.MULTIPLICITY: single}}
        statement_places, act_places = (LM.RECTUM, LM.CECUM), (LM.SIGMOID_COLON,)
        events = {TPG.E1: TPG.denial(breadth=TPG.sup(ct.Breadth.LISTED_TARGETS),
                                     targets=(TPG.sup(TPG.L1), TPG.sup(TPG.L3)),
                                     places=tuple(TPG.sup(place) for place in statement_places)),
                  TPG.E2: TPG.act(lesion=TPG.SILENT, places=tuple(TPG.sup(place) for place in act_places))}
        controls = TPG.claims_pair_controls(TPG.E1, statement_places, TPG.E2, act_places, lambda subject, place: True)
        self.assertIn((TPG.E1, A.TARGET_PLACES, LM.SIGMOID_COLON), controls)
        built = TPG.build(events, lesions=lesions, controls=controls)
        self.assertEqual(TPG.row_of(built, pairing.Row.TARGET), INDEPENDENT)
        for key in sorted(controls, key=lambda key: (str(key[0]), key[2].value)):
            with self.subTest(not_rejected=(str(key[0]), key[2].value)):
                flipped = TPG.build(events, lesions=lesions, controls={**controls, key: False})
                self.assertNotEqual(TPG.row_of(flipped, pairing.Row.TARGET), INDEPENDENT)


# The refutation's RF2F-L2 shape end to end, a note of its own (fictional clinician): a flat polyp filed at the
# transverse colon that extends to the splenic flexure, a listed denial placed at the removed polyps' filed places, and
# a tattoo at the splenic flexure naming no lesion; contract/claims asks the DENIAL whether it is about the splenic
# flexure.
STATEMENT_FLAT = ('A 20 mm flat polyp in the transverse colon extending to the splenic flexure was removed with a cold '
                  'snare.')
STATEMENT_TATTOO = 'The splenic flexure was tattooed.'
STATEMENT_NOTE = R2CL.note('A 3 mm polyp in the cecum was left in place.',                    # S5: L1
                           'A 4 mm polyp in the rectum was left in place.',                    # S6: L2
                           'A 6 mm polyp in the sigmoid colon was removed with a cold snare.',  # S7: E2 on L3
                           STATEMENT_FLAT,                                                     # S8: E3 on L4
                           'No lifting injection was used for either removed polyp.',          # S9: E4 on L3, L4
                           STATEMENT_TATTOO)                                                   # S10: E5, no lesion


def statement_answer():
    """STATEMENT_NOTE's answer: E2 and E3 remove L3 (sigmoid colon) and L4 (filed at the transverse colon only); E4 the
    listed denial placed at their filed places; E5 the tattoo at the splenic flexure, naming no lesion."""
    denial = event('E4', ['S9'], 'lifting injection', 'was used', 'injection', state='negated',
                   status_source=src(['S9'], 'was used'), session=[fact('X1', src(['S9']))],
                   scope__breadth=[fact('listed_targets', src(['S9'], 'either removed polyp'))],
                   scope__targets=['L3', 'L4'],
                   target__places=[fact('sigmoid_colon', src(['S7'], 'sigmoid colon', 'placing')),
                                   fact('transverse_colon', src(['S8'], 'transverse colon', 'placing'))])
    tattoo = R2EL.tattoo('E5', 'S10', places=('splenic_flexure',), place_words='splenic flexure')
    lesions = [R2CL.entry('L1', 'S5', 'A 3 mm polyp', place='cecum', place_words='cecum'),
               R2CL.entry('L2', 'S6', 'A 4 mm polyp', place='rectum', place_words='rectum'),
               R2CL.entry('L3', 'S7', 'A 6 mm polyp', place='sigmoid_colon', place_words='sigmoid colon'),
               R2CL.entry('L4', 'S8', 'A 20 mm flat polyp', place='transverse_colon', place_words='transverse colon')]
    return R2CL.colonoscopy(STATEMENT_NOTE,
                            R2CL.removal('E2', 'S7', 'L3', 'A 6 mm polyp', 'sigmoid_colon', 'sigmoid colon'),
                            R2CL.removal('E3', 'S8', 'L4', 'A 20 mm flat polyp', 'transverse_colon',
                                         'transverse colon'),
                            denial, tattoo, lesions=lesions)


def statement_control(answer):
    """Pass 2 FAITHFUL, except the DENIAL's place pair control about the splenic flexure answered ``answer`` (None: left
    without a verdict)."""
    def oracle(claim, role, claim_set):
        if role == 'pair_control' and claim.subject == 'E4' and claim.value == 'splenic_flexure':
            return None if answer is None else verdict(claim, answer)
        return R2CL.FAITHFUL(claim, role, claim_set)
    return oracle


class R2FLStatementControlPipelineTests(SimpleTestCase):
    def test_rflr_a_denial_pass_2_does_not_hold_apart_from_the_tattoos_place_stays_held(self):
        # end to end: claims asks the tattoo about the sigmoid and the transverse colon and the denial about the splenic
        # flexure (no act-lesion claim: no lesion place is compatible with the tattoo's); a faithful pass 2 releases
        # 45381, and a denial control pass 2 supports, leaves unclear or leaves unanswered holds it (the build released)
        data = statement_answer()
        claim_set, _out, R, _view = R2CL.run(STATEMENT_NOTE, data, R2CL.FAITHFUL)
        self.assertEqual(list(getattr(claim_set, 'act_lesions', ())), [])
        self.assertIs(R.pair_controls[(Id.parse('E4'), A.TARGET_PLACES, LM.SPLENIC_FLEXURE)], True)
        cases = {'faithful': (R2CL.FAITHFUL, ('ready', ())),
                 'supported': (statement_control('supports'), ('needs_clarification', ('relation:unresolved',))),
                 'unclear': (statement_control('unclear'), ('needs_clarification', ('relation:unresolved',))),
                 'unanswered': (statement_control(None), ('needs_clarification', ('relation:unresolved',)))}
        for name, (oracle, outcome) in cases.items():
            with self.subTest(statement_control=name):
                found = R2CL.outcomes(STATEMENT_NOTE, data, oracle, ('45381', STATEMENT_TATTOO),
                                      ('45385', STATEMENT_FLAT))
                self.assertEqual(found['45381'][:2], outcome)
                self.assertEqual(found['45385'][0], 'ready')
