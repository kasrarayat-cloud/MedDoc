"""DECISIONS D311 R2F2-L1 and R2F2-L2 (round r2f's second refutation of lane f-lesion, rf2-f-lesion; built by lane
f-lesion2). TEXT-ONLY and SYNTHETIC: every note here is written for these tests (a fictional clinician, R2CL's head),
every pass-1 answer is built by hand with test_settle's builders and every pass-2 answer by an oracle; every FactSet is
built in code (evaluate_fixtures' Doc, test_pairing's builders); nothing is sent anywhere.

Each rule is shown on an input it must change - red on the tree it repairs (int2 + r2e's e-lesion + r2f's f-lesion), green
after - and on a boundary it must leave alone:
- R2F2-L1 (R2FMStatementSide*Tests, R2FMMonotoneTests): an act whose target names no lesion is set apart from a statement
  listing lesions (a listed target, its asked reading, and D305's single target) only as 3.2.3 [R:SC-B] sets two objects
  apart, in BOTH directions - the lesions' side as built (a lesion's finding's places asked of the act by rejected
  controls, or the lesion's established not-on), AND each place of the act (its place set established) asked of the
  statement by a rejected place pair control, unless it is an established place of one of the statement's own lesions
  read by an established not-on. A statement whose own places hold an act place no such lesion holds - a denial placed
  beyond its lesions, a lesion filed with a short place list - is set apart by nothing there: contract/claims.pair never
  asks an object about a place compatible with one of its own, so no truthful pass 2 could hold the pair apart, and the
  build released it (the refutation's Inputs 1-3, its asked-only and single-target twin).
- R2F2-L2 (R2FMReadCostTests): what the listed arm reads of an act - the lesions it was asked about or controlled
  against, its place set, each lesion's place reading - is computed once per FactSet and act, never per (statement, act)
  pair (counted, not timed, as test_coverage.SameAsWalkCost), output-identical to the per-pair reading it replaces.
- The repair pass (round r2f's refutation of lane f-lesion2, RFL2-1 and RFL2-2, both reproduced; R2FMSingleArmScan*
  classes, tests test_rfmr_*): the every-control scan belongs to D311's class rule in EVERY arm - every place pair
  control asked of EITHER object rejected (facts.apart_by_controls, DECISIONS D220 and D236) - so the single arm reads
  it as the listed arm does: a control asked of the act and not rejected holds the single target (RFL2-1: the build
  read the statement's side alone), and 9.4's deletion of an act place leaves its unrejected statement control read
  (RFL2-2: the build read that control only while the place was in the act's list, a P-MONO breach of D220's class).
"""
from __future__ import annotations

import copy
from dataclasses import replace
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import anatomy, pairing
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Attribute, Fact, Id, IdFamily
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2 import test_r2fl_lesion as R2FL
from tests.v2.test_settle import colonoscopy, event, fact, src, verdict

A, LM = Attribute, ct.Landmark
E3, E4, E5 = (Id.parse(name) for name in ('E3', 'E4', 'E5'))
L1, L2, L3, L5 = (Id.parse(name) for name in ('L1', 'L2', 'L3', 'L5'))
SINGLE = ct.Multiplicity.SINGLE
INJECTION, TATTOO = ct.Kind.INJECTION, ct.Kind.TATTOO
LISTED, SINGLE_TARGET = ct.Breadth.LISTED_TARGETS, ct.Breadth.SINGLE_TARGET
sup, unres, neg = EF.sup, EF.unres, EF.neg
INDEPENDENT, SAME = pairing.RowResult.INDEPENDENT, pairing.RowResult.SAME
target = R2FL.target


def properties():
    """tests/v2/test_properties (imported when a test needs it: it builds its fixtures and its harness)."""
    from tests.v2 import test_properties
    return test_properties


def _facts(found):
    return [place if isinstance(place, Fact) else sup(place) for place in found]


def _claimable(found):
    """The places contract/claims.places names of a place list: the members claimed supported (test_pairing.claimable)."""
    return tuple(item.value for item in _facts(found) if item.state is ct.FactState.SUPPORTED)


def scene(*, l1_places=(LM.TRANSVERSE_COLON,), l2_places=(LM.CECUM,), denial_places=None,
          act_places=(LM.TRANSVERSE_COLON,), targets=(L1, L2), breadth=LISTED, act_kind=TATTOO,
          denial_kind=INJECTION, not_on=(), verdict_of=lambda subject, place: True, extra=None, lesions=None, l1=None):
    """A colonoscopy X1 (E1) with the cold snare E2 of L1; E3 a denial of ``denial_kind`` - a listed target on
    ``targets``, or a single target on L1 (``breadth``) - placed at ``denial_places`` (by default every place of its
    lesions, as pass 1 places it from the removals' sentences); E4 an act of ``act_kind`` at ``act_places`` (places or
    Facts) whose target names no lesion. L1 (single) in ``l1_places`` (``l1`` replaces its facts), L2 (single) in
    ``l2_places``; ``lesions`` adds entries. The place pair controls are the ones contract/claims.pair makes from the
    two objects' claimable places (each asked about every place of the other none of its own is compatible with),
    ``verdict_of(subject, place)`` pass 2's answer (True: rejected); ``not_on``: the act-lesion pairs (E4, L) settled
    established (pass 2 supported "This act was not done on lesion L." and rejected its control), each where
    contract/claims.act_lesion asks it - an act place compatible with one of L's places (asserted); ``extra`` adds or
    changes FactSet.pair_controls."""
    doc = EF.colonoscopy(places=_facts(l1_places))
    doc.lesions[L1] = l1 if l1 is not None else EF.facts_of(multiplicity=sup(SINGLE), lesion_places=_facts(l1_places))
    doc.lesion(2, multiplicity=sup(SINGLE), lesion_places=_facts(l2_places))
    doc.lesions.update(lesions or {})
    if denial_places is None:
        denial_places = (*l1_places, *l2_places) if breadth is LISTED else tuple(l1_places)
    over = dict(targets=[sup(lesion) for lesion in targets]) if breadth is LISTED else dict(lesion=sup(L1))
    doc.act(3, denial_kind, status=EF.neg(ct.Status.PERFORMED), breadth=sup(breadth), places=_facts(denial_places),
            **over)
    doc.act(4, act_kind, places=_facts(act_places))
    doc.controls.update(R2FL.claims_controls(E3, _claimable(denial_places), E4, _claimable(act_places), verdict_of))
    for lesion in not_on:
        named = [member.value for member in doc.lesions[lesion].get(A.PLACES, ())]
        assert any(anatomy.compatible(mine, theirs) for mine in _claimable(act_places) for theirs in named), lesion
        doc.controls[(E4, A.DISTINCT_FROM, lesion)] = True
    doc.controls.update(extra or {})
    return doc.build()


def relation(R):
    return pairing.relation(R, E3, E4).relation


# --- R2F2-L1: SC-B's second direction, on settled FactSets --------------------------------------------------------------

class R2FMStatementSideTests(SimpleTestCase):
    def test_rfm_a_denial_placed_beyond_its_lesions_at_the_acts_place_is_held(self):
        # the refutation's Input 2 (its q01; the verifier's w1-w4): L1 in the cecum, L2 in the ascending colon, the
        # denial placed at both and at the act's own place - the sigmoid colon, the left colon that contains it, or the
        # whole colon - beside a tattoo or an injection in the sigmoid colon naming no lesion. claims.pair asks the act
        # about the cecum and the ascending colon (rejected) and the denial about nothing: no truthful verdict holds the
        # pair apart, and none sets it apart - held, SAME by the overlapping places (the build released every one)
        for act_kind in (TATTOO, INJECTION):
            for beyond in (LM.SIGMOID_COLON, LM.LEFT_COLON, LM.COLON):
                with self.subTest(act=act_kind.value, denial_adds=beyond.value):
                    R = scene(l1_places=(LM.CECUM,), l2_places=(LM.ASCENDING_COLON,), act_kind=act_kind,
                              denial_places=(LM.CECUM, LM.ASCENDING_COLON, beyond), act_places=(LM.SIGMOID_COLON,))
                    self.assertNotIn((E3, A.TARGET_PLACES, LM.SIGMOID_COLON), R.pair_controls)
                    self.assertTrue(all(R.pair_controls.values()))
                    self.assertEqual(target(R), SAME)
                    self.assertIs(relation(R), pairing.Relation.CONTRADICTION)

    def test_rfm_the_denial_at_its_lesions_places_only_stays_apart(self):
        # the boundary: the same denial placed at its lesions' places only - claims.pair asks it whether it is about the
        # tattoo's sigmoid colon, rejected: apart (4.2's place arm and the listed arm alike); with the denial's place
        # set not established (one member unresolved, so only the listed arm can set it apart): apart too; that
        # control not rejected: held
        R = scene(l1_places=(LM.CECUM,), l2_places=(LM.ASCENDING_COLON,), act_places=(LM.SIGMOID_COLON,))
        self.assertIs(R.pair_controls[(E3, A.TARGET_PLACES, LM.SIGMOID_COLON)], True)
        self.assertEqual(target(R), INDEPENDENT)
        listed_only = scene(l1_places=(LM.CECUM,), l2_places=(LM.ASCENDING_COLON,), act_places=(LM.SIGMOID_COLON,),
                            denial_places=(unres(LM.CECUM), LM.ASCENDING_COLON))
        self.assertIsNone(pairing._target(listed_only, E3, pairing._Mode.LISTED).places)
        self.assertEqual(target(listed_only), INDEPENDENT)
        held = replace(listed_only, pair_controls={**listed_only.pair_controls,
                                                    (E3, A.TARGET_PLACES, LM.SIGMOID_COLON): False})
        self.assertNotEqual(target(held), INDEPENDENT)

    def test_rfm_the_asked_listing_and_the_single_target_hold_a_place_the_denial_holds(self):
        # the refutation's asked-only twin and its single-target twin (its q01c): every lesion the denial names in the
        # tattoo's transverse colon, asked and established not-on, the denial placed in the sigmoid colon too, where
        # the tattoo also is - nothing asks the denial about the sigmoid colon, and no lesion of it is there: held (the
        # build released both; D305's established not-on for every lesion is necessary, no longer sufficient)
        cases = {
            'the asked listing': scene(l2_places=(LM.TRANSVERSE_COLON,), not_on=(L1, L2),
                                       denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                                       act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON)),
            'the single target': scene(breadth=SINGLE_TARGET, not_on=(L1,),
                                       denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                                       act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON)),
        }
        for name, R in cases.items():
            with self.subTest(case=name):
                self.assertEqual([key for key in R.pair_controls if key[1] is A.TARGET_PLACES], [])
                self.assertEqual(target(R), SAME)
                self.assertIs(relation(R), pairing.Relation.CONTRADICTION)

    def test_rfm_an_act_at_its_not_on_lesions_place_stays_apart(self):
        # the boundary, the ruled releases: the tattoo at the place of the lesion pass 2 established it was not done
        # on - the asked listing, the single target (pair 4's L04: the tattoo in the transverse colon where the resected
        # polyp is) and the first refutation's q01 (L1 not-on at the tattoo's place, L2 in the cecum by its place) -
        # and the tattoo also in the sigmoid colon with the denial placed at its lesions only, asked about the sigmoid
        # colon and rejected: apart
        two_places = (LM.TRANSVERSE_COLON, LM.SIGMOID_COLON)
        cases = {
            'the asked listing': scene(l2_places=(LM.TRANSVERSE_COLON,), not_on=(L1, L2)),
            'the single target': scene(breadth=SINGLE_TARGET, not_on=(L1,)),
            "the first refutation's q01": scene(not_on=(L1,)),
            'the asked listing, the sigmoid asked of the denial': scene(l2_places=(LM.TRANSVERSE_COLON,),
                                                                       not_on=(L1, L2), act_places=two_places),
            'the single target, the sigmoid asked of the denial': scene(breadth=SINGLE_TARGET, not_on=(L1,),
                                                                       act_places=two_places),
        }
        for name, R in cases.items():
            with self.subTest(case=name):
                self.assertEqual(target(R), INDEPENDENT)
                self.assertIs(relation(R), pairing.Relation.INDEPENDENT)

    def test_rfm_a_statement_control_not_rejected_holds_the_single_target(self):
        # the single arm reads SC-B's second direction too: the denial (single target L1, transverse colon) asked
        # whether it is about the tattoo's descending colon - rejected, apart; supported, unclear or unanswered (not
        # rejected), held (the build released it: the single arm read the act-lesion pair alone)
        for rejected, apart in ((True, True), (False, False)):
            with self.subTest(statement_control_rejected=rejected):
                R = scene(breadth=SINGLE_TARGET, not_on=(L1,), act_places=(LM.TRANSVERSE_COLON, LM.DESCENDING_COLON),
                          verdict_of=lambda subject, place, rejected=rejected: rejected if subject == E3 else True)
                self.assertIn((E3, A.TARGET_PLACES, LM.DESCENDING_COLON), R.pair_controls)
                self.assertIs(target(R) is INDEPENDENT, apart)

    def test_rfm_only_an_established_place_of_a_not_on_lesion_answers(self):
        # L1 asked and established not-on, the tattoo in the transverse colon, which L1's place list names but pass 2
        # left unresolved or rejected: nothing answers the tattoo's transverse colon - one of the denial's own places,
        # asked of it by no control - so the pair is held (the build read the not-on alone and released); L1's
        # transverse colon supported: apart
        for name, member, apart in (('supported', sup(LM.TRANSVERSE_COLON), True),
                                    ('unresolved', unres(LM.TRANSVERSE_COLON), False),
                                    ('negated', neg(LM.TRANSVERSE_COLON), False)):
            with self.subTest(l1_transverse=name):
                l1 = EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(LM.HEPATIC_FLEXURE), member])
                R = scene(l1=l1, l1_places=(LM.HEPATIC_FLEXURE,), not_on=(L1,),
                          denial_places=(LM.HEPATIC_FLEXURE, LM.TRANSVERSE_COLON, LM.CECUM))
                self.assertIs(F.established_not_on(R, E4, L1), True)
                self.assertIs(target(R) is INDEPENDENT, apart)

    def test_rfm_an_act_place_is_answered_only_by_the_not_on_lesions_own_place(self):
        # the single target L1 (transverse colon), established not-on; the denial placed at L1's place and in the
        # sigmoid colon; the tattoo "in the colon" - a place holding both: only the very place of the lesion is
        # answered by its not-on, never a place that merely contains it (the tattoo may be in the sigmoid colon the
        # denial names), so held (the build released it); the tattoo at the transverse colon itself: apart
        for act_place, apart in ((LM.COLON, False), (LM.TRANSVERSE_COLON, True)):
            with self.subTest(act_place=act_place.value):
                R = scene(breadth=SINGLE_TARGET, not_on=(L1,), denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                          act_places=(act_place,))
                self.assertTrue(anatomy.compatible(act_place, LM.TRANSVERSE_COLON))
                self.assertIs(target(R) is INDEPENDENT, apart)

    def test_rfm_a_lesion_the_statement_does_not_list_answers_nothing(self):
        # L3 (sigmoid colon), no target of this denial, was asked of the tattoo for another statement and established
        # not-on; the denial (L1 cecum, L2 ascending colon) is placed in the sigmoid colon too, where the tattoo is: L3's
        # not-on answers nothing for this denial - held (the build released it, L3 in its read set); with L3 one of the
        # denial's own listed targets, its not-on answers the sigmoid colon - apart
        l3 = {L3: EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(LM.SIGMOID_COLON)])}
        for listed_l3, apart in ((False, False), (True, True)):
            with self.subTest(l3_listed=listed_l3):
                R = scene(l1_places=(LM.CECUM,), l2_places=(LM.ASCENDING_COLON,), lesions=l3, not_on=(L3,),
                          targets=(L1, L2, L3) if listed_l3 else (L1, L2), act_places=(LM.SIGMOID_COLON,),
                          denial_places=(LM.CECUM, LM.ASCENDING_COLON, LM.SIGMOID_COLON))
                self.assertIn(L3, pairing._asked_about(R, E4))
                self.assertIs(target(R) is INDEPENDENT, apart)

    def test_rfm_another_entry_of_a_not_on_lesions_finding_answers_nothing(self):
        # L1 (transverse colon), asked and established not-on, joined by same_as - supported, unresolved or negated - to
        # L5 in the sigmoid colon; the denial (L1, L2 in the cecum) placed at the transverse colon, the cecum and the
        # sigmoid colon; the tattoo in the transverse and the sigmoid colon. same_as is UNCONTROLLED (it only joins, so
        # it may hold and never release), so L5's sigmoid colon answers nothing: held (the build released each); the
        # boundary: L5 at L1's own transverse colon, the tattoo there alone - apart
        for state in (sup(L5), unres(L5), neg(L5)):
            with self.subTest(same_as=state.result.value):
                l1 = EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(LM.TRANSVERSE_COLON)], same_as=[state])
                R = scene(l1=l1, lesions={L5: EF.facts_of(multiplicity=sup(SINGLE),
                                                          lesion_places=[sup(LM.SIGMOID_COLON)])},
                          not_on=(L1,), denial_places=(LM.TRANSVERSE_COLON, LM.CECUM, LM.SIGMOID_COLON),
                          act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON))
                self.assertIn(L5, F.finding(R, L1))
                self.assertEqual(target(R), SAME)
        l1 = EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(LM.TRANSVERSE_COLON)], same_as=[sup(L5)])
        R = scene(l1=l1, not_on=(L1,), lesions={L5: EF.facts_of(multiplicity=sup(SINGLE),
                                                                 lesion_places=[sup(LM.TRANSVERSE_COLON)])})
        self.assertEqual(target(R), INDEPENDENT)

    def test_rfm_an_act_whose_places_are_not_established_is_set_apart_by_nothing(self):
        # every lesion asked and established not-on (the asked listing, the single target), but the tattoo's place left
        # unresolved, or its place list empty: the act may be anywhere, so nothing establishes that the denial does not
        # cover it (4.11) - held (the build released both arms); its place supported: apart (the boundary above)
        pairs = {(E4, A.DISTINCT_FROM, L1): True, (E4, A.DISTINCT_FROM, L2): True}
        for act_places in ((unres(LM.TRANSVERSE_COLON),), ()):
            for name, breadth in (('the asked listing', LISTED), ('the single target', SINGLE_TARGET)):
                with self.subTest(case=name, act_places=len(act_places)):
                    R = scene(l2_places=(LM.TRANSVERSE_COLON,), breadth=breadth, act_places=act_places, extra=pairs)
                    self.assertIsNone(pairing._target(R, E4, pairing._Mode.SINGLE).places)
                    self.assertNotEqual(target(R), INDEPENDENT)

    def test_rfm_p_unknown_target_reads_the_statement_control_of_the_unnamed_arm(self):
        # 9.4's P-UNKNOWN-TARGET on test_pairing's own scene of the place reading (_apart_by_unnamed, restated with the
        # statement asked about the act's sigmoid colon), every one of its pair controls in turn - not rejected, or
        # never generated - never leaves the pair apart (the build left it apart with the statement's control never
        # generated: nothing asked the statement about the act's place)
        from tests.v2 import test_pairing as TPG
        events, lesions, controls, _arm = TPG._apart_by_unnamed()
        statement_side = (TPG.E1, A.TARGET_PLACES, LM.SIGMOID_COLON)
        self.assertIs(controls[statement_side], True)
        self.assertEqual(TPG.row_of(TPG.build(events, lesions=lesions, controls=controls), pairing.Row.TARGET),
                         INDEPENDENT)
        for key in sorted(controls, key=lambda key: (str(key[0]), key[2].value)):
            for how, changed in (('not rejected', {**controls, key: False}),
                                 ('never generated', {other: value for other, value in controls.items()
                                                      if other != key})):
                with self.subTest(control=(str(key[0]), key[2].value), how=how):
                    found = TPG.row_of(TPG.build(events, lesions=lesions, controls=changed), pairing.Row.TARGET)
                    self.assertNotEqual(found, INDEPENDENT)

    def test_rfm_the_verifiers_scenes_without_the_acts_place_on_the_denial_stay_apart(self):
        # the boundary of the restated K and J (R2FLFindingTests): the same scenes with the denial not placed at the
        # act's splenic flexure - claims.pair asks the denial about it, rejected: apart
        cases = {'K': R2FL.verifier_scene(denial_places=(LM.SIGMOID_COLON, LM.DESCENDING_COLON)),
                 'J': R2FL.verifier_scene(l2_same_as=[sup(L3)], extra={L3: R2FL.entry_at(sup(LM.TRANSVERSE_COLON))},
                                          denial_places=(LM.SIGMOID_COLON, LM.DESCENDING_COLON, LM.TRANSVERSE_COLON))}
        for name, R in cases.items():
            with self.subTest(scene=name):
                self.assertIs(R.pair_controls[(E3, A.TARGET_PLACES, LM.SPLENIC_FLEXURE)], True)
                self.assertEqual(target(R), INDEPENDENT)


class R2FMMonotoneTests(SimpleTestCase):
    """P-MONO (9.4) over the rule's own inputs: from each held input above, no single weakening of the harness
    (test_properties.weakenings: every fact of every table, every list member deleted, every pair control unrejected,
    the pair-type outcomes re-derived) sets the pair apart - in particular no deletion of a statement place, of a listed
    target or of a lesion place releases. Named, never silent: 9.4's deletion of an ACT place member that no control
    asks either object about - the place the denial's own places hold, so contract/claims made no control for it in
    either direction - removes a requirement no reading could meet and may release, as any deleted member whose control
    was never generated does (refute-r2d-r2 RD1; DECISIONS D245, D228's own-target arm); checked by its own predicate."""

    @staticmethod
    def never_asked(R, what):
        """The weakening deleted an act place of E4 that no place pair control asks the denial or the act about."""
        if not (isinstance(what, tuple) and len(what) == 4 and what[:2] == (E4, A.TARGET_PLACES)):
            return False
        place = what[3].value
        return (E3, A.TARGET_PLACES, place) not in R.pair_controls and (E4, A.TARGET_PLACES, place) not in R.pair_controls

    def test_rfm_no_weakening_of_a_held_input_releases_it(self):
        TP = properties()
        held = {
            'the denial beyond its lesions': scene(l1_places=(LM.CECUM,), l2_places=(LM.ASCENDING_COLON,),
                                                   denial_places=(LM.CECUM, LM.ASCENDING_COLON, LM.SIGMOID_COLON),
                                                   act_places=(LM.SIGMOID_COLON,)),
            'the asked listing': scene(l2_places=(LM.TRANSVERSE_COLON,), not_on=(L1, L2),
                                       denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                                       act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON)),
            'the single target': scene(breadth=SINGLE_TARGET, not_on=(L1,),
                                       denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                                       act_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON)),
            'the verifier scene K': R2FL.verifier_scene(),
        }
        named = []
        for name, R in held.items():
            self.assertNotEqual(target(R), INDEPENDENT, name)
            count = 0
            for label, weak, what in TP.weakenings(R):
                count += 1
                if target(weak) is not INDEPENDENT:
                    continue
                with self.subTest(case=name, weakening=label):
                    self.assertTrue(self.never_asked(R, what), label)
                named.append((name, label))
            self.assertGreater(count, 50, name)
        # exactly the act place the denial's own places hold, deleted from the act's two places, in the two twins
        self.assertEqual(sorted(named), [('the asked listing', 'deleted E4 target.places[1]'),
                                         ('the single target', 'deleted E4 target.places[1]')])


# --- R2F2-L1 end to end: synthetic notes of their own, recorded-shape pass 1, an oracle pass 2 --------------------------

SHORT_TATTOO = 'India ink was injected at the polypectomy site at the splenic flexure.'
SHORT_REMOVED = 'A 20 mm polyp in the transverse colon extending to the splenic flexure was removed with a cold snare.'
SHORT = R2CL.note('A 4 mm polyp in the hepatic flexure was removed with a cold snare.',      # S5: E2 on L1
                  SHORT_REMOVED,                                                            # S6: E3 on L2
                  'No injection was given at either polypectomy site.',                     # S7: E4 on L1, L2
                  SHORT_TATTOO)                                                             # S8: E5, no lesion


def short_answer(*, full):
    """SHORT's answer: E2 and E3 remove L1 (hepatic flexure) and L2 - filed at the transverse colon only (a short list)
    or, ``full``, at the transverse colon and the splenic flexure, as S6 tells it; E4 denies an injection at either site
    (listed targets), placed at every place S5 and S6 give; E5 a tattoo at the splenic flexure naming no lesion."""
    denial = event('E4', ['S7'], 'injection', 'was given', 'injection', state='negated',
                   status_source=src(['S7'], 'was given'), session=[fact('X1', src(['S7']))],
                   scope__breadth=[fact('listed_targets', src(['S7'], 'either polypectomy site'))],
                   scope__targets=['L1', 'L2'],
                   target__places=[fact('hepatic_flexure', src(['S5'], 'hepatic flexure', 'placing')),
                                   fact('transverse_colon', src(['S6'], 'transverse colon', 'placing')),
                                   fact('splenic_flexure', src(['S6'], 'splenic flexure', 'placing'))])
    tattoo = event('E5', ['S8'], 'India ink was injected', 'was injected', 'tattoo', session=[fact('X1', src(['S8']))],
                   target__places=[fact('splenic_flexure', src(['S8'], 'splenic flexure'))])
    l2 = R2CL.entry('L2', 'S6', 'A 20 mm polyp', place='transverse_colon', place_words='transverse colon')
    if full:
        l2['places'].append(fact('splenic_flexure', src(['S6'], 'splenic flexure')))
    return colonoscopy(SHORT, R2CL.removal('E2', 'S5', 'L1', 'A 4 mm polyp', 'hepatic_flexure', 'hepatic flexure'),
                       R2CL.removal('E3', 'S6', 'L2', 'A 20 mm polyp', 'transverse_colon', 'transverse colon'),
                       denial, tattoo,
                       lesions=[R2CL.entry('L1', 'S5', 'A 4 mm polyp', place='hepatic_flexure',
                                           place_words='hepatic flexure'), l2])


BEYOND_TATTOO = 'The rectum was tattooed with India ink.'
BEYOND_DENIAL = 'No injection was given at either polypectomy site or in the rectum.'


def beyond(*, rectum):
    """A note of its own: two removed polyps (cecum, descending colon); a denial of an injection at either site -
    ``rectum``: "or in the rectum", placed there too; else at the sites only - and a tattoo in the rectum naming no
    lesion. (text, answer)."""
    deny = BEYOND_DENIAL if rectum else 'No injection was given at either polypectomy site.'
    text = R2CL.note('A 5 mm polyp in the cecum was removed with a cold snare.',               # S5: E2 on L1
                     'A 9 mm polyp in the descending colon was removed with a cold snare.',    # S6: E3 on L2
                     deny,                                                                     # S7: E4 on L1, L2
                     BEYOND_TATTOO)                                                            # S8: E5, no lesion
    places = [fact('cecum', src(['S5'], 'cecum', 'placing')),
              fact('descending_colon', src(['S6'], 'descending colon', 'placing'))]
    if rectum:
        places.append(fact('rectum', src(['S7'], 'rectum')))
    denial = event('E4', ['S7'], 'injection', 'was given', 'injection', state='negated',
                   status_source=src(['S7'], 'was given'), session=[fact('X1', src(['S7']))],
                   scope__breadth=[fact('listed_targets', src(['S7'], 'either polypectomy site'))],
                   scope__targets=['L1', 'L2'], target__places=places)
    tattoo = event('E5', ['S8'], 'tattooed', 'was tattooed', 'tattoo', session=[fact('X1', src(['S8']))],
                   target__places=[fact('rectum', src(['S8'], 'rectum'))])
    data = colonoscopy(text, R2CL.removal('E2', 'S5', 'L1', 'A 5 mm polyp', 'cecum', 'cecum'),
                       R2CL.removal('E3', 'S6', 'L2', 'A 9 mm polyp', 'descending_colon', 'descending colon'),
                       denial, tattoo,
                       lesions=[R2CL.entry('L1', 'S5', 'A 5 mm polyp', place='cecum', place_words='cecum'),
                                R2CL.entry('L2', 'S6', 'A 9 mm polyp', place='descending_colon',
                                           place_words='descending colon')])
    return text, data


SINGLE_REMOVED = 'A 7 mm polyp in the transverse colon was removed with a cold snare.'
SINGLE_TATTOO = 'The transverse colon and the descending colon were tattooed beside the polypectomy site.'


def single(*, descending):
    """A note of its own, the single-target twin: one removed polyp (transverse colon); a denial that a lifting
    injection was used for the resection - ``descending``: "or anywhere in the descending colon", placed there too; else
    at the polyp's place only; a tattoo in the transverse and the descending colon naming no lesion. (text, answer)."""
    deny = ('No lifting injection was used for the resection or anywhere in the descending colon.' if descending
            else 'No lifting injection was used for the resection.')
    text = R2CL.note(SINGLE_REMOVED, deny, SINGLE_TATTOO)                                        # S5, S6, S7
    places = [fact('transverse_colon', src(['S5'], 'transverse colon', 'placing'))]
    if descending:
        places.append(fact('descending_colon', src(['S6'], 'descending colon')))
    denial = event('E3', ['S6'], 'lifting injection', 'was used', 'injection', state='negated',
                   status_source=src(['S6'], 'was used'), session=[fact('X1', src(['S6']))],
                   scope__breadth=[fact('single_target', src(['S6'], 'the resection'))],
                   target__lesion=[fact('L1', src(['S6'], 'the resection'))], target__places=places)
    tattoo = event('E4', ['S7'], 'tattooed', 'were tattooed', 'tattoo', session=[fact('X1', src(['S7']))],
                   target__places=[fact('transverse_colon', src(['S7'], 'transverse colon')),
                                   fact('descending_colon', src(['S7'], 'descending colon'))])
    data = colonoscopy(text, R2CL.removal('E2', 'S5', 'L1', 'A 7 mm polyp', 'transverse_colon', 'transverse colon'),
                       denial, tattoo, lesions=[R2CL.entry('L1', 'S5', 'A 7 mm polyp', place='transverse_colon',
                                                           place_words='transverse colon')])
    return text, data


EXTENT_REMOVED = 'A 30 mm flat polyp in the ascending colon extending to the hepatic flexure was removed with a cold snare.'
EXTENT_TATTOO = 'The hepatic flexure was tattooed beside the flat polyp.'
EXTENT = R2CL.note('A 5 mm polyp in the cecum was removed with a cold snare.',                 # S5: E2 on L1
                   EXTENT_REMOVED,                                                            # S6: E3 on L2
                   'No lifting injection was used for either removed polyp.',                 # S7: E4 on L1, L2
                   EXTENT_TATTOO)                                                             # S8: E5, no lesion


def extent_answer():
    """EXTENT's answer: R2FL's FINDING_NOTE one-entry shape with the flat polyp's extent in its OWN sentence: L2 filed
    at the ascending colon and the hepatic flexure from S6; the denial (listed L1, L2) placed at every place of both; the
    tattoo at the hepatic flexure naming no lesion."""
    denial = event('E4', ['S7'], 'lifting injection', 'was used', 'injection', state='negated',
                   status_source=src(['S7'], 'was used'), session=[fact('X1', src(['S7']))],
                   scope__breadth=[fact('listed_targets', src(['S7'], 'either removed polyp'))],
                   scope__targets=['L1', 'L2'],
                   target__places=[fact('cecum', src(['S5'], 'cecum', 'placing')),
                                   fact('ascending_colon', src(['S6'], 'ascending colon', 'placing')),
                                   fact('hepatic_flexure', src(['S6'], 'hepatic flexure', 'placing'))])
    tattoo = event('E5', ['S8'], 'tattooed', 'was tattooed', 'tattoo', session=[fact('X1', src(['S8']))],
                   target__places=[fact('hepatic_flexure', src(['S8'], 'hepatic flexure'))])
    flat = R2CL.entry('L2', 'S6', 'A 30 mm flat polyp', place='ascending_colon', place_words='ascending colon')
    flat['places'].append(fact('hepatic_flexure', src(['S6'], 'hepatic flexure')))
    return colonoscopy(EXTENT, R2CL.removal('E2', 'S5', 'L1', 'A 5 mm polyp', 'cecum', 'cecum'),
                       R2CL.removal('E3', 'S6', 'L2', 'A 30 mm flat polyp', 'ascending_colon', 'ascending colon'),
                       denial, tattoo,
                       lesions=[R2CL.entry('L1', 'S5', 'A 5 mm polyp', place='cecum', place_words='cecum'), flat])


def done_on(lesion):
    """Pass 2 FAITHFUL, except the act-lesion claim about ``lesion`` answered as a reader who judges the act WAS done on
    it (the claim contradicted, its control supported)."""
    def oracle(claim, role, claim_set):
        for pair in getattr(claim_set, 'act_lesions', ()):
            if pair.lesion == lesion and claim.id == pair.claim:
                return verdict(claim, 'contradicts')
            if pair.lesion == lesion and claim.id == pair.control:
                return verdict(claim, 'supports')
        return R2CL.FAITHFUL(claim, role, claim_set)
    return oracle


HELD = ('needs_clarification', ('relation:contradiction',))
READY = ('ready', ())


class R2FMStatementSidePipelineTests(SimpleTestCase):
    def outcome(self, text, data, oracle, quote):
        return R2CL.outcomes(text, data, oracle, ('45381', quote))['45381'][:2]

    def test_rfm_a_short_lesion_list_beside_a_tattoo_at_its_unfiled_place_is_held(self):
        # the refutation's Input 1, a note of its own: L2 "in the transverse colon extending to the splenic flexure"
        # filed at the transverse colon only; the denial placed at every place the two sites cover; a tattoo at the
        # polypectomy site at the splenic flexure. No act-lesion claim (the tattoo's place meets no filed lesion place),
        # no control asks the denial about the splenic flexure (its own place): held under a faithful pass 2 and under
        # one that also judges the tattoo was on L2 (the build released both)
        for name, oracle in (('faithful', R2CL.FAITHFUL), ('done on L2', done_on('L2'))):
            with self.subTest(pass2=name):
                claim_set, _out, R, _view = R2CL.run(SHORT, short_answer(full=False), oracle)
                self.assertEqual(list(getattr(claim_set, 'act_lesions', ())), [])
                self.assertNotIn((E4, A.TARGET_PLACES, LM.SPLENIC_FLEXURE), R.pair_controls)
                self.assertEqual(self.outcome(SHORT, short_answer(full=False), oracle, SHORT_TATTOO), HELD)

    def test_rfm_the_full_list_reads_the_act_lesion_claim(self):
        # the boundary: L2 filed at both places - the tattoo asked whether it was done on L2: pass 2 judging it was not
        # (its splenic flexure is then one of L2's established places, which the not-on answers), READY; judging it
        # was, held (as before)
        for name, oracle, expected in (('faithful', R2CL.FAITHFUL, READY), ('done on L2', done_on('L2'), HELD)):
            with self.subTest(pass2=name):
                claim_set, _out, _R, _view = R2CL.run(SHORT, short_answer(full=True), oracle)
                self.assertEqual([(pair.act, pair.lesion) for pair in claim_set.act_lesions], [('E5', 'L2')])
                self.assertEqual(self.outcome(SHORT, short_answer(full=True), oracle, SHORT_TATTOO), expected)

    def test_rfm_a_denial_placed_beyond_its_lesions_beside_a_tattoo_there_is_held(self):
        # the refutation's Input 2, a note of its own: "No injection was given at either polypectomy site or in the
        # rectum." beside "The rectum was tattooed with India ink." - the note contradicts itself; a faithful pass 2
        # (no pass-1 error at all) leaves nothing that sets the two apart: held (the build released it); the boundary:
        # the denial of the sites only - claims asks it whether it is about the rectum, rejected: READY
        for rectum, expected in ((True, HELD), (False, READY)):
            with self.subTest(denial_names_the_rectum=rectum):
                text, data = beyond(rectum=rectum)
                _claim_set, _out, R, _view = R2CL.run(text, data, R2CL.FAITHFUL)
                self.assertIs((E4, A.TARGET_PLACES, LM.RECTUM) in R.pair_controls, not rectum)
                self.assertEqual(self.outcome(text, data, R2CL.FAITHFUL, BEYOND_TATTOO), expected)

    def test_rfm_the_single_target_reads_the_statements_side_too(self):
        # D305's single target (pair 4's shape) with the denial placed in the descending colon too, where the tattoo
        # also is: the act-lesion claim is asked and established, yet nothing asks the denial about the descending
        # colon - held (the build released it); the boundary: the denial of the resection only - asked about the
        # descending colon, rejected: READY (pair 4's L04 release, a second tattoo place included)
        Ed = Id.parse('E3')
        for descending, expected in ((True, HELD), (False, READY)):
            with self.subTest(denial_names_the_descending_colon=descending):
                text, data = single(descending=descending)
                claim_set, _out, R, _view = R2CL.run(text, data, R2CL.FAITHFUL)
                self.assertEqual([(pair.act, pair.lesion) for pair in claim_set.act_lesions], [('E4', 'L1')])
                self.assertIs((Ed, A.TARGET_PLACES, LM.DESCENDING_COLON) in R.pair_controls, not descending)
                self.assertEqual(self.outcome(text, data, R2CL.FAITHFUL, SINGLE_TATTOO), expected)

    def test_rfm_a_tattoo_beside_a_polyp_whose_extent_its_own_sentence_states(self):
        # the boundary of R2FL's restated FINDING_NOTE: the flat polyp's extent in its own sentence, so its hepatic
        # flexure is established - the tattoo there, judged not done on it, READY; judged done on it, held
        for name, oracle, expected in (('faithful', R2CL.FAITHFUL, READY), ('done on L2', done_on('L2'), HELD)):
            with self.subTest(pass2=name):
                claim_set, _out, R, _view = R2CL.run(EXTENT, extent_answer(), oracle)
                self.assertEqual([(pair.act, pair.lesion) for pair in claim_set.act_lesions], [('E5', 'L2')])
                self.assertIn(LM.HEPATIC_FLEXURE, {member.value for member in F.members(R, L2, A.PLACES)
                                                   if member.result is ct.Result.SUPPORTED})
                self.assertEqual(self.outcome(EXTENT, extent_answer(), oracle, EXTENT_TATTOO), expected)


# --- R2F2-L2: the reads of an act, once per FactSet ---------------------------------------------------------------------

def unmemoized(R, act):
    """The per-pair reading the memo replaces (round r2f's f-lesion, as the refutation measured it): the lesions the act
    was asked about, the lesions it was controlled against (every lesion's finding re-read), and each lesion's place
    reading against the act's whole place set - (asked, controlled, {lesion: apart})."""
    asked = frozenset(value for subject, attribute, value in R.pair_controls
                      if subject == act and attribute is A.DISTINCT_FROM and isinstance(value, Id))
    places = frozenset(value for subject, attribute, value in R.pair_controls
                       if subject == act and attribute is A.TARGET_PLACES)
    controlled = frozenset() if not places else frozenset(
        lesion for lesion in R.lesions
        if any(value in places for member in F.finding_places(R, lesion).members
               for value in (member.value, *member.options)))
    act_places = pairing._target(R, act, pairing._Mode.SINGLE).places
    apart = {lesion: pairing._apart_by_lesion_places(R, act, lesion, act_places) for lesion in R.lesions}
    return asked, controlled, apart


def bound_scene(*, statements=8, acts=8, lesions=24, seed=20261117):
    """The refutation's bound input in small (its q04's shape): ``lesions`` lesions, each single with 8 places and 8
    same_as members left unresolved (3 options each; 1 in 10 an id the FactSet does not hold); ``statements`` listed
    injection denials (12 targets, 8 places each); ``acts`` tattoos naming no lesion (8 places each), each asked about 6
    places no lesion has by rejected place pair controls."""
    import random
    from tests.v2 import test_pairing as TPG
    rng = random.Random(seed)
    colon = [LM.CECUM, LM.ASCENDING_COLON, LM.HEPATIC_FLEXURE, LM.TRANSVERSE_COLON, LM.SPLENIC_FLEXURE,
             LM.DESCENDING_COLON, LM.SIGMOID_COLON, LM.RECTUM, LM.RECTOSIGMOID, LM.ILEOCECAL_VALVE]
    lesion_places = colon[:7] + colon[-1:]
    asked = [LM.RECTUM, LM.RECTOSIGMOID, LM.APPENDICEAL_ORIFICE, LM.TERMINAL_ILEUM, LM.JEJUNUM, LM.ILEUM]
    ids = [Id(IdFamily.LESION, n) for n in range(1, lesions + 1)]
    missing = [Id(IdFamily.LESION, 100 + n) for n in range(1, 4)]
    table = {}
    for lesion in ids:
        others = [other for other in ids if other != lesion]
        members = [unres(rng.choice(missing) if rng.random() < 0.1 else rng.choice(others),
                         options=tuple(rng.sample(others, 3))) for _ in range(8)]
        table[lesion] = {A.PLACES: tuple(sup(place) for place in lesion_places), A.DISTINCT_FROM: (),
                         A.SAME_AS: tuple(members), A.MULTIPLICITY: (sup(SINGLE),)}
    events = {Id(IdFamily.EVENT, 1): TPG.act(kind=sup(ct.Kind.EXAMINATION), lesion=None, places=())}
    for number in range(2, 2 + statements):
        events[Id(IdFamily.EVENT, number)] = TPG.denial(
            kind=sup(INJECTION), breadth=sup(LISTED), targets=tuple(sup(lesion) for lesion in rng.sample(ids, 12)),
            places=tuple(sup(place) for place in rng.sample(colon, 8)))
    controls = {}
    for number in range(2 + statements, 2 + statements + acts):
        act = Id(IdFamily.EVENT, number)
        events[act] = TPG.act(kind=sup(TATTOO), lesion=None, device=None,
                              places=tuple(sup(place) for place in rng.sample(colon, 8)))
        for place in asked:
            controls[(act, A.TARGET_PLACES, place)] = True
    return TPG.build(events, lesions=table, controls=controls)


def full_read_scene(*, statements=8, acts=8, lesions=24, seed=20261117):
    """The bound input's variant in which the listed arm reads EVERYTHING (lane f-lesion2's probes/mine/c01, in small):
    ``lesions`` lesions, each single with 4 places in the right colon and 8 same_as members left unresolved (3 options
    each, every value a lesion the FactSet holds, so every finding is established); ``statements`` listed injection
    denials (12 targets) placed at those four places, the first left unresolved (so 4.2's own place arm reads nothing);
    ``acts`` tattoos naming no lesion in the descending and the sigmoid colon; claims.pair's controls both ways, every
    one rejected - every pair read in full and set apart."""
    import random
    from tests.v2 import test_pairing as TPG
    rng = random.Random(seed)
    right = [LM.CECUM, LM.ASCENDING_COLON, LM.HEPATIC_FLEXURE, LM.ILEOCECAL_VALVE]
    left = [LM.DESCENDING_COLON, LM.SIGMOID_COLON]
    ids = [Id(IdFamily.LESION, n) for n in range(1, lesions + 1)]
    table = {}
    for lesion in ids:
        others = [other for other in ids if other != lesion]
        table[lesion] = {A.PLACES: tuple(sup(place) for place in right), A.DISTINCT_FROM: (),
                         A.SAME_AS: tuple(unres(rng.choice(others), options=tuple(rng.sample(others, 3)))
                                          for _ in range(8)),
                         A.MULTIPLICITY: (sup(SINGLE),)}
    events = {Id(IdFamily.EVENT, 1): TPG.act(kind=sup(ct.Kind.EXAMINATION), lesion=None, places=())}
    controls = {}
    for number in range(2, 2 + statements):
        statement = Id(IdFamily.EVENT, number)
        events[statement] = TPG.denial(kind=sup(INJECTION), breadth=sup(LISTED),
                                       targets=tuple(sup(lesion) for lesion in rng.sample(ids, 12)),
                                       places=(unres(right[0]), *(sup(place) for place in right[1:])))
        controls.update({(statement, A.TARGET_PLACES, place): True for place in left})
    for number in range(2 + statements, 2 + statements + acts):
        act = Id(IdFamily.EVENT, number)
        events[act] = TPG.act(kind=sup(TATTOO), lesion=None, device=None, places=tuple(sup(place) for place in left))
        controls.update({(act, A.TARGET_PLACES, place): True for place in right})
    return TPG.build(events, lesions=table, controls=controls)


class R2FMReadCostTests(SimpleTestCase):
    def test_rfm_each_lesions_finding_is_read_once_per_factset_and_act_never_per_pair(self):
        # the refutation's R2F2-L2: the build re-read every lesion's finding for each (statement, act) pair (at FINAL-V2
        # 1.8's bounds an assessment took 314.9 s, past the assess job's 120 s deadline). Counted, not timed: over every
        # pair of the bound scene - and of its variant read in full, every pair set apart - twice, the findings are read
        # at most once per lesion for the FactSet's index and once per (act, lesion) for the place reading, never
        # statements x acts x lesions times
        for name, R, relations in (('the bound scene', bound_scene(), {pairing.Relation.CONTRADICTION}),
                                   ('read in full', full_read_scene(), {pairing.Relation.INDEPENDENT})):
            with self.subTest(scene=name):
                acts = [event for event in R.events if F.fact(R, event, A.KIND).value is TATTOO]
                reads = []
                real = F.finding_places

                def counting(R_, lesion, reads=reads, real=real):
                    reads.append(lesion)
                    return real(R_, lesion)

                with mock.patch.object(F, 'finding_places', counting):
                    first = pairing.pairs(R)
                    second = pairing.pairs(R)
                self.assertEqual(first, second)
                listed = [pair for pair in first if pair.act in acts]
                self.assertEqual(len(listed), 8 * 8)
                self.assertEqual({pair.relation for pair in listed}, relations)
                self.assertLessEqual(len(reads), len(R.lesions) * (1 + len(acts)))  # the build: >= 2 x 64 x 24

    def test_rfm_the_reads_equal_the_per_pair_reading_they_replace(self):
        # output-identical: on the bound scene and on every engine scene of this module's R2F2-L1 tests, the memoized
        # reads (_asked_about, _controlled_against, _lesion_apart) equal the per-pair reading of the build, act by act
        # and lesion by lesion; and a FactSet built equal but apart gets reads of its own
        scenes = [bound_scene(), bound_scene(seed=7), full_read_scene(),
                  scene(l1_places=(LM.CECUM,), l2_places=(LM.ASCENDING_COLON,), act_places=(LM.SIGMOID_COLON,),
                        denial_places=(LM.CECUM, LM.ASCENDING_COLON, LM.SIGMOID_COLON)),
                  scene(not_on=(L1,)), scene(l2_places=(LM.TRANSVERSE_COLON,), not_on=(L1, L2)),
                  R2FL.verifier_scene(), R2FL.listed(), R2FL.finding(same_as=[sup(L3)],
                                                                     entries={L3: R2FL.entry_at(sup(LM.ASCENDING_COLON))},
                                                                     denial_places=(LM.TRANSVERSE_COLON, LM.CECUM,
                                                                                    LM.ASCENDING_COLON))]
        for index, R in enumerate(scenes):
            for act in R.events:
                with self.subTest(scene=index, act=str(act)):
                    asked, controlled, apart = unmemoized(R, act)
                    self.assertEqual(pairing._asked_about(R, act), asked)
                    self.assertEqual(pairing._controlled_against(R, act), controlled)
                    self.assertEqual({lesion: pairing._lesion_apart(R, act, lesion) for lesion in R.lesions}, apart)
        R, first_act = scenes[0], Id.parse('E10')  # bound_scene's first tattoo
        self.assertIs(F.fact(R, first_act, A.KIND).value, TATTOO)
        twin = replace(R)
        self.assertIsNot(pairing._reads_of(twin), pairing._reads_of(R))
        self.assertEqual(pairing._controlled_against(twin, first_act), pairing._controlled_against(R, first_act))
        self.assertEqual(pairing._controlled_against(scenes[-1], E4), frozenset({L2, L3}))  # a read set not empty

    def test_rfm_the_memo_keeps_the_factsets_read_last(self):
        # the memo holds each FactSet with its reads (identity-checked: an id never names another FactSet while its
        # entry stands) and at most _READS_KEPT of them, the one read longest ago dropped first
        others = [scene() for _number in range(pairing._READS_KEPT + 2)]
        for R in others:
            pairing._controlled_against(R, E4)
        self.assertLessEqual(len(pairing._READS), pairing._READS_KEPT)
        self.assertTrue(all(id(entry[0]) == key for key, entry in pairing._READS.items()))
        self.assertNotIn(id(others[0]), pairing._READS)
        self.assertIs(pairing._READS[id(others[-1])][0], others[-1])
        # an entry whose id now names another FactSet (as a FactSet freed and its id reused would leave it) is never
        # read for this one: its reads are computed afresh
        R, other = scene(not_on=(L1,)), scene()
        stale = pairing._Reads()
        stale.acts[E4] = pairing._ActRead(frozenset({L5}), frozenset({L5}), None)
        pairing._READS[id(R)] = (other, stale)
        self.assertIsNot(pairing._reads_of(R), stale)
        self.assertEqual(pairing._asked_about(R, E4), frozenset({L1}))
        self.assertIs(pairing._READS[id(R)][0], R)


# --- The repair pass (round r2f's refutation of lane f-lesion2, RFL2-1, RFL2-2): the scan in every arm ---

def unrejected(*subjects):
    """A ``verdict_of`` for ``scene``: pass 2 left every place pair control asked of ``subjects`` NOT rejected
    (supported, unclear or unanswered: settle stores each as not rejected) and rejected every other."""
    return lambda subject, place: subject not in subjects


class R2FMSingleArmScanTests(SimpleTestCase):
    def test_rfmr_an_act_control_not_rejected_holds_the_single_target(self):
        # RFL2-1 (the refutation's F1 / p01, the verifier's v02): the single target L1 (transverse colon), established
        # not-on; the denial placed at L1's place and beyond it in the sigmoid colon, or in the sigmoid colon alone; the
        # tattoo filed at the transverse colon only (pass 1 omitted its sigmoid colon). claims.pair asks the tattoo
        # "This act was done in the sigmoid colon." - rejected: apart; not rejected (supported, unclear or unanswered):
        # held, as its listed twin holds it - 4.11: a pair control not rejected never yields INDEPENDENT, in the act's
        # direction as in the statement's (the build's single arm never read a control asked of the act: released)
        for denial_places in ((LM.TRANSVERSE_COLON, LM.SIGMOID_COLON), (LM.SIGMOID_COLON,)):
            for arm, breadth in (('the single target', SINGLE_TARGET), ('its listed twin', LISTED)):
                for rejected in (True, False):
                    with self.subTest(denial=[place.value for place in denial_places], arm=arm,
                                      act_control_rejected=rejected):
                        R = scene(breadth=breadth, targets=(L1,), not_on=(L1,), denial_places=denial_places,
                                  verdict_of=(lambda subject, place: True) if rejected else unrejected(E4))
                        self.assertIs(R.pair_controls[(E4, A.TARGET_PLACES, LM.SIGMOID_COLON)], rejected)
                        self.assertIs(target(R) is INDEPENDENT, rejected)
                        if not rejected:
                            self.assertIsNot(relation(R), pairing.Relation.INDEPENDENT)

    def test_rfmr_every_control_of_the_single_arm_is_read_in_both_directions(self):
        # P-UNKNOWN-TARGET's form for the single arm, deterministic (the listed arm's twin is
        # test_rfm_p_unknown_target_reads_the_statement_control_of_the_unnamed_arm): the single target L1 (transverse
        # colon), established not-on; the denial at L1's place and in the sigmoid colon; the tattoo at the transverse
        # and the descending colon. claims.pair asks the tattoo about the sigmoid colon and the denial about the
        # descending colon, both rejected: apart (the tattoo's transverse colon answered by L1's not-on, its descending
        # colon by the statement's rejected control). Each of the arm's controls in turn NOT REJECTED holds it, in
        # either direction (the build released the act's); NEVER GENERATED, every control the arm requires holds it (the
        # act-lesion pair, the statement asked about the act's descending colon). Named: the act asked about the
        # statement's own sigmoid colon is not required - D311 reads the single target's side by its established not-on,
        # never the statement's deletable place list - so with no such control the pair stays apart (claims.pair makes
        # it between any two placed objects, so a settled FactSet lacks it only where the claim set did)
        R = scene(breadth=SINGLE_TARGET, not_on=(L1,), denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                  act_places=(LM.TRANSVERSE_COLON, LM.DESCENDING_COLON))
        act_side, statement_side = (E4, A.TARGET_PLACES, LM.SIGMOID_COLON), (E3, A.TARGET_PLACES, LM.DESCENDING_COLON)
        self.assertEqual(set(R.pair_controls), {act_side, statement_side, (E4, A.DISTINCT_FROM, L1)})
        self.assertEqual(target(R), INDEPENDENT)
        for key in sorted(R.pair_controls, key=repr):
            for how, controls in (('not rejected', {**R.pair_controls, key: False}),
                                  ('never generated', {other: value for other, value in R.pair_controls.items()
                                                       if other != key})):
                with self.subTest(control=(str(key[0]), key[1].value, str(getattr(key[2], 'value', key[2]))), how=how):
                    found = target(replace(R, pair_controls=controls))
                    if how == 'never generated' and key == act_side:
                        self.assertEqual(found, INDEPENDENT)  # named: not required (above)
                    else:
                        self.assertNotEqual(found, INDEPENDENT)

    def test_rfmr_a_control_another_pair_made_not_rejected_holds_the_single_target(self):
        # the scan's "whichever pair made it" (D236's hold class; the verifier of RFL2-2's v03): a second tattoo E5 in
        # the descending colon makes claims ask the single-target denial whether it is about the descending colon; the
        # tattoo E4 (transverse colon, established not-on L1) is asked about nothing. That control not rejected holds E3
        # against E4 too - a FactSet keys a control by the object asked and the place, never by the pair - as the listed
        # arm and 4.2's place arm read it; rejected: apart (the build's single arm set it apart either way)
        for rejected in (True, False):
            with self.subTest(statement_control_rejected=rejected):
                doc = EF.colonoscopy(places=[sup(LM.TRANSVERSE_COLON)])
                doc.lesions[L1] = EF.facts_of(multiplicity=sup(SINGLE), lesion_places=[sup(LM.TRANSVERSE_COLON)])
                doc.act(3, INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(SINGLE_TARGET), lesion=sup(L1),
                        places=[sup(LM.TRANSVERSE_COLON)])
                doc.act(4, TATTOO, places=[sup(LM.TRANSVERSE_COLON)])
                doc.act(5, TATTOO, places=[sup(LM.DESCENDING_COLON)])
                doc.controls.update(R2FL.claims_controls(E3, (LM.TRANSVERSE_COLON,), E5, (LM.DESCENDING_COLON,),
                                                         lambda subject, place: rejected or subject != E3))
                doc.controls[(E4, A.DISTINCT_FROM, L1)] = True
                R = doc.build()
                self.assertEqual(set(R.pair_controls), {(E3, A.TARGET_PLACES, LM.DESCENDING_COLON),
                                                        (E5, A.TARGET_PLACES, LM.TRANSVERSE_COLON),
                                                        (E4, A.DISTINCT_FROM, L1)})
                self.assertIs(target(R) is INDEPENDENT, rejected)


class R2FMSingleArmScanMonotoneTests(SimpleTestCase):
    def test_rfmr_no_weakening_of_an_input_held_by_an_unrejected_control_releases_it(self):
        # RFL2-2 (the refutation's F2 / p03 and p07, the verifier's v01): R2FMMonotoneTests' held inputs are held by a
        # MISSING control; these are held by one pass 2 left NOT REJECTED - this module's own held single input (the
        # denial, single target L1, asked whether it is about the tattoo's descending colon), RFL2-1's input (the
        # tattoo, filed at the transverse colon only, asked about the denial's sigmoid colon) and the listed twin of
        # each. No single 9.4 weakening (test_properties.weakenings) sets one of them apart - not even the deletion of
        # the very act place whose statement control was left unrejected (the build's single arm read that control only
        # while the place was in the act's list, so deleting it released: D220's class, outside the named one), and none
        # is the named class: every act place here is asked of an object, or answered by the not-on alone
        TP = properties()
        held = {}
        for arm, breadth in (('single', SINGLE_TARGET), ('listed', LISTED)):
            held[f'{arm}: the denial asked about the descending colon'] = scene(
                breadth=breadth, targets=(L1,), not_on=(L1,), denial_places=(LM.TRANSVERSE_COLON,),
                act_places=(LM.TRANSVERSE_COLON, LM.DESCENDING_COLON), verdict_of=unrejected(E3))
            held[f'{arm}: the tattoo asked about the sigmoid colon'] = scene(
                breadth=breadth, targets=(L1,), not_on=(L1,), denial_places=(LM.TRANSVERSE_COLON, LM.SIGMOID_COLON),
                verdict_of=unrejected(E4))
        for name, R in held.items():
            with self.subTest(case=name, weakening=None):
                self.assertEqual(sum(value is False for value in R.pair_controls.values()), 1)
                self.assertNotEqual(target(R), INDEPENDENT)  # held as filed
            if target(R) is INDEPENDENT:
                continue  # failed above; a weakening of an input set apart as filed proves nothing more
            count = 0
            for label, weak, _what in TP.weakenings(R):
                count += 1
                with self.subTest(case=name, weakening=label):
                    self.assertNotEqual(target(weak), INDEPENDENT)
            self.assertGreater(count, 50, name)

    def test_rfmr_p_mono_holds_the_harness_single_fixture_beside_an_unrejected_control(self):
        # RFL2-2 through P-MONO's own harness (test_properties): its fixture of the single arm's release with a second
        # act place (SINGLE_FIXTURE - the cold snare E2 of L1, single, in the sigmoid colon; E3 a denial that a lifting
        # injection was used for L1, at L1's place; E4 a tattoo in the sigmoid and the descending colon naming no
        # lesion; the act-lesion pair (E4, L1) established and claims' control asking the denial about the descending
        # colon rejected): 45381 READY by the two together, held by either not established; with that control NOT
        # rejected, 9.4's deletion of the tattoo's descending colon (the controls left as they were) releases nothing by
        # PMonoTests.check, every ruling's predicate (the build made 45381 READY, the check naming D220); and D220's
        # own generator (beside_unrejected_controls) makes exactly that state there, which the harness's
        # test_a_deleted_members_unrejected_control_keeps_the_pair_on_every_path and drawn-verdict census now reach
        TP = properties()
        R0, codes = TP.fixture(TP.SINGLE_FIXTURE)
        self.assertIn(TP.SINGLE_FIXTURE, [name for name, _R, _codes in TP.fixtures()])
        statement_side, not_on = (E3, A.TARGET_PLACES, LM.DESCENDING_COLON), (E4, A.DISTINCT_FROM, L1)
        self.assertEqual({key: R0.pair_controls[key] for key in R0.pair_controls}, {statement_side: True, not_on: True})
        self.assertIn('45381', TP.ready(TP.assessed(R0, codes)))
        for key in (statement_side, not_on):  # either reading not established holds 45381
            with self.subTest(not_established=key[1].value):
                self.assertNotIn('45381', TP.ready(TP.assessed(replace(R0, pair_controls={**R0.pair_controls,
                                                                                          key: False}), codes)))
        R = replace(R0, pair_controls={**R0.pair_controls, statement_side: False})
        base = TP.assessed(R, codes)
        [(label, weak, what)] = [(label, weak, what) for label, weak, what in TP.weakenings(R)
                                 if label.startswith('deleted E4 target.places')
                                 and what[3].value is LM.DESCENDING_COLON]
        self.assertIs(weak.pair_controls[statement_side], False)
        after = TP.assessed(weak, codes)
        self.assertNotIn('45381', TP.ready(after))
        self.assertEqual(TP.PMonoTests.check(self, base, after, label, what, R), [])
        states = list(TP.beside_unrejected_controls(R0))
        self.assertEqual([(state[3][0], state[3][3].value, state[4]) for state in states],
                         [(E4, LM.DESCENDING_COLON, 'statement-act')])
        for label, base_R, after_R, what, path in states:
            with self.subTest(state=label, path=path):
                self.assertIs(base_R.pair_controls[statement_side], False)
                self.assertEqual(TP.PMonoTests.check(self, TP.assessed(base_R, codes), TP.assessed(after_R, codes),
                                                     label, what, base_R), [])

def short_filing(data, act, place):
    """``data`` (a pass-1 answer) with ``place`` removed from ``act``'s target places: pass 1's short list (exactly one
    member removed, asserted)."""
    out = copy.deepcopy(data)
    removed = 0
    for item in out['events']:
        if item.get('id') == act:
            before = item['target']['places']
            item['target']['places'] = [member for member in before if member.get('value') != place]
            removed += len(before) - len(item['target']['places'])
    assert removed == 1, removed
    return out


def act_place_answered(act, place, answer):
    """Pass 2 FAITHFUL, except the place pair control asking ``act`` about ``place`` ("This act was done in the
    {place}.") answered ``answer``: 'supports' (as the note tells it), 'unclear', or None (no verdict)."""
    def oracle(claim, role, claim_set):
        if any(claim.id == control.claim and control.subject[1] == act and control.value == place
               for control in claim_set.pair_controls):
            return None if answer is None else verdict(claim, answer)
        return R2CL.FAITHFUL(claim, role, claim_set)
    return oracle


BEYOND_SITE_DENIAL = 'No injection was given at the polypectomy site or in the sigmoid colon.'
BEYOND_SITE_TATTOO = ('India ink was injected in the transverse colon beside the polypectomy site and in the sigmoid '
                      'colon.')


def beyond_site():
    """A note of its own (the refutation's p02, the verifier's v03): one removed polyp (transverse colon); a denial of
    an injection at its site or in the sigmoid colon (single target L1, placed at the transverse and the sigmoid
    colon); a tattoo in the transverse and the sigmoid colon naming no lesion, filed in full. (text, answer)."""
    text = R2CL.note(SINGLE_REMOVED, BEYOND_SITE_DENIAL, BEYOND_SITE_TATTOO)                    # S5, S6, S7
    denial = event('E3', ['S6'], 'injection', 'was given', 'injection', state='negated',
                   status_source=src(['S6'], 'was given'), session=[fact('X1', src(['S6']))],
                   scope__breadth=[fact('single_target', src(['S6'], 'the polypectomy site'))],
                   target__lesion=[fact('L1', src(['S6'], 'the polypectomy site'))],
                   target__places=[fact('transverse_colon', src(['S5'], 'transverse colon', 'placing')),
                                   fact('sigmoid_colon', src(['S6'], 'sigmoid colon'))])
    tattoo = event('E4', ['S7'], 'India ink was injected', 'was injected', 'tattoo', session=[fact('X1', src(['S7']))],
                   target__places=[fact('transverse_colon', src(['S7'], 'transverse colon')),
                                   fact('sigmoid_colon', src(['S7'], 'sigmoid colon'))])
    data = colonoscopy(text, R2CL.removal('E2', 'S5', 'L1', 'A 7 mm polyp', 'transverse_colon', 'transverse colon'),
                       denial, tattoo, lesions=[R2CL.entry('L1', 'S5', 'A 7 mm polyp', place='transverse_colon',
                                                           place_words='transverse colon')])
    return text, data


class R2FMSingleArmScanPipelineTests(SimpleTestCase):
    def outcome(self, text, data, oracle, quote):
        return R2CL.outcomes(text, data, oracle, ('45381', quote))['45381'][:2]

    def held_and_ready(self, text, full, place, quote):
        """The tattoo E4 filed in full (held, as the note contradicts itself) and short of ``place``: claims.pair asks
        it "This act was done in the {place}." - rejected, READY (SC-B met: pass 2 held the tattoo out of the place the
        denial names); supported as the note tells it, unclear or unanswered: held (the build made each READY)."""
        short = short_filing(full, 'E4', place)
        claim_set, _out, R, _view = R2CL.run(text, short, R2CL.FAITHFUL)
        self.assertEqual([(control.subject[1], control.value) for control in claim_set.pair_controls], [('E4', place)])
        self.assertEqual([(pair.act, pair.lesion) for pair in claim_set.act_lesions], [('E4', 'L1')])
        self.assertIs(F.established_not_on(R, E4, L1), True)
        self.assertEqual(self.outcome(text, full, R2CL.FAITHFUL, quote), HELD)
        for name, oracle, expected in (('faithful', R2CL.FAITHFUL, READY),
                                       ('truthful', act_place_answered('E4', place, 'supports'), HELD),
                                       ('unclear', act_place_answered('E4', place, 'unclear'), HELD),
                                       ('unanswered', act_place_answered('E4', place, None), HELD)):
            with self.subTest(pass2=name):
                self.assertEqual(self.outcome(text, short, oracle, quote), expected)

    def test_rfmr_the_single_target_note_with_the_tattoo_filed_short_is_held(self):
        # RFL2-1 end to end on this module's own note, single(descending=True) - "No lifting injection was used for the
        # resection or anywhere in the descending colon." beside "The transverse colon and the descending colon were
        # tattooed beside the polypectomy site." - pass 1 filing the tattoo at the transverse colon only
        text, full = single(descending=True)
        self.held_and_ready(text, full, 'descending_colon', SINGLE_TATTOO)

    def test_rfmr_a_denial_beyond_its_polyp_beside_a_tattoo_filed_short_is_held(self):
        # RFL2-1 end to end on a note of its own (the refutation's p02): "No injection was given at the polypectomy site
        # or in the sigmoid colon." beside "India ink was injected in the transverse colon beside the polypectomy site
        # and in the sigmoid colon.", pass 1 filing the tattoo at the transverse colon only
        text, full = beyond_site()
        self.held_and_ready(text, full, 'sigmoid_colon', BEYOND_SITE_TATTOO)
