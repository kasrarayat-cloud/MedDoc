"""DECISIONS D300 (round r2c, builder r2c-lesion): the first refutation of P1-LESION (DECISIONS D296; round r2b's
rf-lesion, its findings reproduced) repaired as class rules, RF-L1 to RF-L7, on FINAL-V2 4.2's lesion pair claim.
TEXT-ONLY and SYNTHETIC: every note here is written for these tests (fictional clinicians), every pass-1 answer is
built by hand with test_settle's builders and every pass-2 answer by an oracle; nothing is sent anywhere. Two stored
rows are fixtures (tests/fixtures/interpretation_v2/r2cl/): the same synthetic note settled and stored by the tree of
image de28c5187 and by the tree of round r2's int1 (b424db551), each written by that tree's own code.

Each rule is shown on an input it must change - red on the tree before round r2c (int1), green after - and on a
boundary it must leave alone, end to end (extract_read -> checks -> claims -> pass 2 -> settle -> store -> assess) where
the rule reaches a code:
- RF-L1 (R2CLJoinTests): no lesion pair is asked, and no arm sets two lesions apart by lesion, while same_as members, in
  any state that leaves them possible, may join them directly or through other entries (the P5 component,
  engine/coverage._SameAs.join): a chain or a hub of same_as through an entry no act names holds the polypectomy a
  denial on the chain's far end may cover, and so does a written distinct_from beside such a chain; two polyps with no
  identity written stay READY; engine/facts.possibly_one_finding answers as the coverage join does on every pair of
  every FactSet tried.
- RF-L3 (R2CLMembershipTests): where either lesion is not established as one lesion the pair asks membership - "Lesion
  {M} is not one of the lesions of {L}." / "... is one of ..." (the act's lesion claimed single), or "No lesion of {M}
  is one of the lesions of {L}." / "A lesion of {M} ..." - and only an established non-membership sets the two apart;
  two single lesions keep the distinctness; a form is read only with the multiplicity it presumes established.
- RF-L2 (R2CLReaderTests): every reader of an established distinctness reads an established lesion pair as a written
  distinct_from - the target row, bundling (coverage._apart), D118 (combination.one_stricture) and the 59/XS review
  (combination.lesions_distinct) - one test per reader, with the written form as the reference.
- RF-L4 (R2CLStoreTests): the store refuses a row whose supported lesion pair its stored claim and control verdicts
  refute, and reads the established and the unresolved ones.
- RF-L5 (R2CLBoundTests): a set that would pass CLAIM_BOUND_V3 drops its lesion pairs first, never the document, each
  drop recorded and stored unappraised; a set over the bound without them is still refused.
- RF-L6 (R2CLOlderRowTests): at the @3 pair a row stored without lesion_pairs - the de28c5187-era tree's - reads as the
  empty list; a row int1 stored (distinctness asked of a group) reads as not established.
- RF-L7 (R2CLPropertyFixtureTests): a P-MONO/P-INDEP fixture of tests/v2/test_properties.py carries an established
  lesion pair the release rests on.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import math
import uuid
from dataclasses import replace
from pathlib import Path

from django.test import SimpleTestCase

from studio import interpretation, jobs
from studio.interpretation import store
from studio.interpretation.contract import appraise_prompt, appraise_read, checks, segment, settle
from studio.interpretation.contract import claims as CL
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import assess as engine_assess
from studio.interpretation.engine import combination, coverage, derive, pairing
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Attribute, Id
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_lesion_pair as LP
from tests.v2.test_settle import USAGE, colonoscopy, doubt, event, fact, faithful, lesion, roles_of, src, verdict

V3 = interpretation.APPRAISAL_VERSION_V3
A = Attribute
FIXTURES = Path(__file__).resolve().parents[1] / 'fixtures' / 'interpretation_v2' / 'r2cl'

HEAD = ('SYNTHETIC COLONOSCOPY NOTE\n'                                                        # S1: N0
        'Date of service: 03/14/2031\n'                                                       # S2
        'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                       # S3
        '\n'
        'Findings: The colonoscope was advanced to the cecum.\n')                             # S4: N1, E1


def note(*lines: str) -> str:
    """HEAD and one unit per line: the first line is S5."""
    return HEAD + ''.join(line + '\n' for line in lines)


def ids(*names: str) -> tuple:
    return tuple(Id.parse(name) for name in names)


def removal(eid, unit, lid, words, place=None, place_words='', *, kind='snare', device='cold_snare',
            device_words='cold snare', kind_words='cold snare', status_words='was removed'):
    over = dict(session=[fact('X1', src([unit]))], target__lesion=[fact(lid, src([unit], words))],
                technique__device=[fact(device, src([unit], device_words))])
    if place is not None:
        over['target__places'] = [fact(place, src([unit], place_words))]
    return event(eid, [unit], kind_words, status_words, kind, **over)


def biopsy(eid, unit, lid, words, place=None, place_words=''):
    over = dict(session=[fact('X1', src([unit]))], target__lesion=[fact(lid, src([unit], words))],
                technique__device=[fact('cold_forceps', src([unit], 'cold biopsy forceps'))])
    if place is not None:
        over['target__places'] = [fact(place, src([unit], place_words))]
    return event(eid, [unit], 'sampled', 'was sampled', 'biopsy', **over)


def denial(eid, unit, kind, kind_words, status_words, lid, lesion_words, breadth_words=None):
    return event(eid, [unit], kind_words, status_words, kind, state='negated',
                 status_source=src([unit], status_words), session=[fact('X1', src([unit]))],
                 scope__breadth=[fact('single_target', src([unit], breadth_words or lesion_words))],
                 target__lesion=[fact(lid, src([unit], lesion_words))])


def entry(lid, unit, words, multiplicity='single', place=None, place_words='', **fields):
    """A lesion entry described at ``unit`` by ``words``; ``multiplicity`` None writes none."""
    if multiplicity is not None:
        fields['multiplicity'] = [fact(multiplicity, src([unit], words))]
    if place is not None:
        fields['places'] = [fact(place, src([unit], place_words))]
    return lesion(lid, src([unit], words), **fields)


# --- the pipeline: LP's (claims @2, settle @2, the row at the product's pair, the text-free view), assessed ----------

def run(text, data, oracle):
    """(claim set, settled, FactSet, text-free view) of ``data`` under ``oracle``."""
    claim_set, out = LP.settled(text, data, oracle)
    view = LP.view(text, LP.row(text, out))
    return claim_set, out, F.factset(view), view


def outcomes(text, data, oracle, *codes):
    """{code: (status, held causes, considerations)} for the codes proposed on their quotes - ``codes`` as (code,
    quote) - end to end."""
    _claim_set, _out, _R, view = run(text, data, oracle)
    effective = derive.derive(view, {}).effective
    proposed = []
    for code, quote in codes:
        at = text.index(quote)
        proposed.append(ProviderCode('selected', 'cpt', code, 'UNVERIFIED PROVIDER WORDING',
                                     (EvidenceSpan(0, at, at + len(quote), quote, True),)))
    found = engine_assess.assess(
        inventory=view, date_of_service=datetime.date.fromisoformat(effective) if effective else None, text=text,
        pages=(), integrity=jobs._Integrity(), provider_status='succeeded',
        proposals=NormalizedResponse('replay', 'test@1', tuple(proposed)), reference=LP._NoReference(),
        member=engine_assess.MemberContext(), label=lambda session: str(session.id))
    out = {}
    for item in found.codes:
        assert item.code not in out, item.code
        out[item.code] = (item.status.value, tuple(sorted({str(held.cause) for held in item.held_facts})),
                          tuple(found.value for found in item.considerations))
    return out


def status(text, data, oracle, code, quote):
    return outcomes(text, data, oracle, (code, quote))[code][0]


def pair_ids(claim_set):
    return ({pair.claim for pair in claim_set.lesion_pairs}, {pair.control for pair in claim_set.lesion_pairs})


def oracle(*, member=None, contradicted=(), pair_claim=None):
    """Pass 2: test_settle.faithful (every real claim supported, every control and pair control rejected), except -
    ``member`` (True or False) given - each lesion pair answered as an honest reader that knows whether the act's
    lesion is, or shares, one of the statement's lesions: D296's distinctness literally (a group and one of its members
    ARE different entries: "different lesions" supported, "the same lesion" rejected, whatever the membership - the
    defect RF-L3 names) and the membership forms by the membership; ``pair_claim`` answers every lesion pair claim
    (its control rejected); ``contradicted``: the subjects whose multiplicity claim is rejected and its contrary control
    supported."""
    def answer(claim, role, claim_set):
        claims_, controls = pair_ids(claim_set)
        if claim.id in claims_ and pair_claim is not None:
            return verdict(claim, pair_claim)
        if member is not None and (claim.id in claims_ or claim.id in controls):
            if claim.template in ('lesion.distinct_from', 'lesion.same_as'):
                return verdict(claim, 'supports' if claim.id in claims_ else 'contradicts')
            outside = claim.id in claims_  # the claim says "not one of"; its control "one of"
            return verdict(claim, 'supports' if outside is not member else 'contradicts')
        if claim.template == 'lesion.multiplicity' and claim.subject in contradicted:
            return verdict(claim, 'contradicts' if role == 'claim' else 'supports')
        return faithful(claim, role, claim_set)
    return answer


FAITHFUL = oracle()

# --- RF-L1: the same_as component ------------------------------------------------------------------------------------

# One polyp told three times: removed (L1), "the polyp" restated (L2, joined to L1 by same_as, no act names it), and
# "this polyp" (L3, joined to L2) denied. The document contradicts itself about one polyp.
REMOVED = 'A 6 mm polyp in the ascending colon was removed with a cold snare.'
CHAIN = note(REMOVED,                                                                          # S5: E2 on L1
             'The polyp had a smooth surface.',                                                # S6: L2
             'No snare polypectomy was performed on this polyp.')                              # S7: E3 denies, on L3
TWO = note(REMOVED,                                                                            # S5: E2 on L1
           'Another polyp was seen in the transverse colon.',                                  # S6: L3
           'No snare polypectomy was performed on the other polyp.')                           # S7: E3 denies, on L3


def chain_answer(*, links=(('L2', 'L1'), ('L3', 'L2')), written=False):
    """CHAIN's answer: E2 removes L1 (single, ascending colon); L2 (S6) and L3 (S7) single; E3 denies a snare
    polypectomy on L3; ``links`` the same_as members written, each (holder, value), cited at the holder's description;
    ``written``: L3 distinct_from L1 written too (pass 1 contradicting itself)."""
    units = {'L1': ('S5', 'A 6 mm polyp'), 'L2': ('S6', 'The polyp'), 'L3': ('S7', 'this polyp')}
    same = {name: [] for name in units}
    for holder, value in links:
        unit, words = units[holder]
        same[holder].append(fact(value, src([unit], words)))
    lesions = [entry('L1', 'S5', 'A 6 mm polyp', place='ascending_colon', place_words='ascending colon',
                     same_as=same['L1']),
               entry('L2', 'S6', 'The polyp', same_as=same['L2']),
               entry('L3', 'S7', 'this polyp', same_as=same['L3'],
                     distinct_from=[fact('L1', src(['S7'], 'this polyp'))] if written else [])]
    return colonoscopy(CHAIN, removal('E2', 'S5', 'L1', 'A 6 mm polyp', 'ascending_colon', 'ascending colon'),
                       denial('E3', 'S7', 'snare', 'snare polypectomy', 'was performed', 'L3', 'this polyp'),
                       lesions=lesions)


def two_answer(*, l3='single'):
    """TWO's answer: E2 removes L1 (single, ascending colon); E3 denies a snare polypectomy on L3 (``l3``: its claimed
    multiplicity, None for none, transverse colon); no identity written - D296's intended release."""
    return colonoscopy(TWO, removal('E2', 'S5', 'L1', 'A 6 mm polyp', 'ascending_colon', 'ascending colon'),
                       denial('E3', 'S7', 'snare', 'snare polypectomy', 'was performed', 'L3', 'the other polyp'),
                       lesions=[entry('L1', 'S5', 'A 6 mm polyp', place='ascending_colon',
                                      place_words='ascending colon'),
                                entry('L3', 'S6', 'Another polyp', l3, place='transverse_colon',
                                      place_words='transverse colon')])


def joins_agree(test, R, names):
    """facts.possibly_one_finding against coverage._SameAs.join, every ordered pair of ``names``."""
    same = coverage._SameAs(R)
    for one in names:
        for other in names:
            with test.subTest(one=str(one), other=str(other)):
                test.assertEqual(F.possibly_one_finding(R, one, other),
                                 same.join((one,), (other,)) is not None)


class R2CLJoinTests(SimpleTestCase):
    def test_rcl_a_chain_or_a_hub_asks_no_lesion_pair(self):
        for name, links in (('chain', (('L2', 'L1'), ('L3', 'L2'))), ('hub', (('L1', 'L2'), ('L3', 'L2'))),
                            ('reversed', (('L1', 'L2'), ('L2', 'L3')))):
            with self.subTest(shape=name):
                claim_set = LP.request(CHAIN, chain_answer(links=links))[2].claim_set
                self.assertEqual(claim_set.lesion_pairs, ())

    def test_rcl_a_chain_or_a_hub_holds_the_polypectomy(self):
        for name, links in (('chain', (('L2', 'L1'), ('L3', 'L2'))), ('hub', (('L1', 'L2'), ('L3', 'L2')))):
            with self.subTest(shape=name):
                self.assertEqual(status(CHAIN, chain_answer(links=links), FAITHFUL, '45385', REMOVED),
                                 'needs_clarification')

    def test_rcl_a_written_distinct_from_beside_a_chain_sets_nothing_apart(self):
        # pass 1 writes L3 distinct_from L1 beside the chain that joins them: no arm sets the two apart (the chain may
        # join them; before D300 the direct-only guard let the written distinct_from release 45385)
        claim_set, _out, R, _view = run(CHAIN, chain_answer(written=True), FAITHFUL)
        self.assertEqual(claim_set.lesion_pairs, ())
        L1, L3, E2, E3 = ids('L1', 'L3', 'E2', 'E3')
        self.assertTrue(F.possibly_one_finding(R, L3, L1))
        self.assertFalse(F.established_distinct(R, L3, L1))
        self.assertFalse(F.apart_by_lesion(R, E3, E2))
        self.assertNotEqual(pairing.relation(R, E3, E2).relation, pairing.Relation.INDEPENDENT)
        self.assertEqual(status(CHAIN, chain_answer(written=True), FAITHFUL, '45385', REMOVED), 'needs_clarification')

    def test_rcl_two_polyps_with_no_identity_written_stay_ready(self):
        claim_set = LP.request(TWO, two_answer())[2].claim_set
        self.assertEqual([(pair.lesion, pair.other) for pair in claim_set.lesion_pairs], [('L3', 'L1')])
        self.assertEqual(status(TWO, two_answer(), FAITHFUL, '45385', REMOVED), 'ready')

    def test_rcl_the_engine_join_answers_as_the_coverage_join(self):
        L1, L2, L3, L4, L9 = ids('L1', 'L2', 'L3', 'L4', 'L9')
        names = (L1, L2, L3, L4, L9)
        cases = {
            'chain': {L2: [EF.unres(L1)], L3: [EF.sup(L2)]},
            'hub': {L1: [EF.sup(L2)], L3: [EF.sup(L2)]},
            'negated link': {L2: [EF.neg(L1)], L3: [EF.sup(L2)]},
            'negated left open': {L2: [EF.unres(L1)], L3: [EF.fact(ct.Result.UNRESOLVED, L2, ct.FactState.NEGATED)]},
            'doubted': {L3: [EF.doubted(L4, L1)]},
            'contradicted': {L3: [EF.contra(L2, L4)]},
            'silent': {L2: [EF.fact(ct.Result.UNKNOWN, None, None)]},
            'one unknown id': {L3: [EF.sup(L9)]},
            'two unknown ids': {L4: [EF.sup(L9), EF.sup(Id.parse('L8'))]},
            'nothing': {},
        }
        for name, same_as in cases.items():
            doc = EF.Doc()
            for lid in (L1, L2, L3, L4):
                doc.lesions[lid] = EF.facts_of(same_as=same_as.get(lid, ()))
            with self.subTest(case=name):
                joins_agree(self, doc.build(), names)

    def test_rcl_an_established_negation_leaves_the_two_apart(self):
        # the boundary: a same_as member pass 2 established negated names nothing (possibly), so a chain broken by it
        # joins nothing and a written distinct_from with its pair controls rejected still sets the pair apart.
        # DECISIONS D302 RF2C-L1 (round r2e): a written distinct_from sets two lesions apart only when both are
        # established single, so L1 and L3 are filed single (no multiplicity was filed before r2e)
        doc = EF.colonoscopy()
        doc.lesions[EF.L(1)] = {**doc.lesions[EF.L(1)], A.MULTIPLICITY: (EF.sup(ct.Multiplicity.SINGLE),)}
        doc.lesion(2, same_as=[EF.neg(EF.L(1))])
        doc.lesion(3, same_as=[EF.sup(EF.L(2))], distinct_from=[EF.sup(EF.L(1))],
                   multiplicity=EF.sup(ct.Multiplicity.SINGLE))
        doc.act(3, ct.Kind.SNARE, status=EF.neg(ct.Status.PERFORMED), breadth=EF.sup(ct.Breadth.SINGLE_TARGET),
                lesion=EF.sup(EF.L(3)))
        doc.controls.update({(EF.E(3), A.TARGET_LESION, EF.L(1)): True, (EF.E(2), A.TARGET_LESION, EF.L(3)): True})
        R = doc.build()
        self.assertFalse(F.possibly_one_finding(R, EF.L(3), EF.L(1)))
        self.assertTrue(F.apart_by_lesion(R, EF.E(3), EF.E(2)))
        # and the same with the negation not established: the chain may join them, nothing sets them apart
        doc.lesion(2, same_as=[EF.unres(EF.L(1))])
        R = doc.build()
        self.assertTrue(F.possibly_one_finding(R, EF.L(3), EF.L(1)))
        self.assertFalse(F.apart_by_lesion(R, EF.E(3), EF.E(2)))

    def test_rcl_no_arm_sets_a_joined_pair_apart(self):
        # the listed arm: "No snare polypectomy was performed on L3 or L4." against the snare E2 on L1, L3 joined to L1
        # through L2, each listed lesion written distinct from L1, every lesion pair control rejected
        def listed(chain):
            # DECISIONS D302 RF2C-L1 (round r2e): the polyps filed single, which a written distinct_from now needs
            doc = EF.colonoscopy()
            doc.lesions[EF.L(1)] = {**doc.lesions[EF.L(1)], A.MULTIPLICITY: (EF.sup(ct.Multiplicity.SINGLE),)}
            doc.lesion(2, same_as=[EF.unres(EF.L(1))] if chain else [])
            doc.lesion(3, same_as=[EF.sup(EF.L(2))] if chain else [], distinct_from=[EF.sup(EF.L(1))],
                       multiplicity=EF.sup(ct.Multiplicity.SINGLE))
            doc.lesion(4, distinct_from=[EF.sup(EF.L(1))], multiplicity=EF.sup(ct.Multiplicity.SINGLE))
            doc.act(3, ct.Kind.SNARE, status=EF.neg(ct.Status.PERFORMED), breadth=EF.sup(ct.Breadth.LISTED_TARGETS),
                    targets=[EF.sup(EF.L(3)), EF.sup(EF.L(4))], lesion=None, places=None)
            doc.controls.update({(EF.E(3), A.TARGET_LESION, EF.L(1)): True, (EF.E(2), A.TARGET_LESION, EF.L(3)): True,
                                 (EF.E(2), A.TARGET_LESION, EF.L(4)): True})
            return doc.build()

        self.assertEqual(pairing.relation(listed(False), EF.E(3), EF.E(2)).relation, pairing.Relation.INDEPENDENT)
        self.assertNotEqual(pairing.relation(listed(True), EF.E(3), EF.E(2)).relation,
                            pairing.Relation.INDEPENDENT)

    def test_rcl_the_claim_time_join_reads_unknown_ids_and_doubts(self):
        # an id the answer has no lesion of in L3's same_as may be L1 (4.11): no pair; a doubt about L2's same_as
        # whose readings name L1 and L3 joins them through L2: no pair; the same doubt naming L4 only asks the pair
        unknown = chain_answer(links=(('L3', 'L9'),))
        self.assertEqual(LP.request(CHAIN, unknown)[2].claim_set.lesion_pairs, ())
        for readings, pairs in ((('L1', 'L3'), []), (('L1',), [('L3', 'L1')])):
            data = chain_answer(links=())
            data['doubts'] = [doubt('identity', ['L2'], ['S6'], 'unclear', readings)]
            with self.subTest(readings=readings):
                found = LP.request(CHAIN, data)[2].claim_set.lesion_pairs
                self.assertEqual([(pair.lesion, pair.other) for pair in found], pairs)


# --- RF-L3: membership where either lesion is not established as one ------------------------------------------------

# The removed 5 mm polyp IS one of the two polyps the denial covers (an honest reader answers "is one of" yes).
MEMBER_REMOVED = 'The 5 mm polyp in the transverse colon was removed with a cold snare.'
MEMBER = note('Two polyps, 5 mm and 8 mm, were seen in the transverse colon.',                  # S5: L1, a group
              MEMBER_REMOVED,                                                                   # S6: E2 on L2
              'Polypectomy was not performed on the polyps because of anticoagulation.')        # S7: E3 denies, on L1
# The removed polyp lies outside the group the denial covers (the boundary: D296's intended release).
OUTSIDE_REMOVED = 'A 5 mm polyp in the transverse colon was removed with a cold snare.'
OUTSIDE = note('Two polyps were seen in the rectum.',                                           # S5: L1, a group
               OUTSIDE_REMOVED,                                                                 # S6: E2 on L2
               'Polypectomy was not performed on the rectal polyps because of anticoagulation.')  # S7: E3, on L1
# The act's lesion is the group: three removed polyps, a denial on one polyp that is one of them.
REVERSE_REMOVED = 'Three polyps in the sigmoid colon were removed with a cold snare.'
REVERSE = note(REVERSE_REMOVED,                                                                 # S5: E2 on L1, a group
               'No snare polypectomy was performed on the 9 mm sigmoid polyp.')                 # S6: E3 denies, on L2


def member_answer(text=MEMBER, group_words='Two polyps', place='transverse_colon', place_words='transverse colon',
                  removed_words='The 5 mm polyp', denied_words='the polyps'):
    """MEMBER's (or OUTSIDE's) answer: L1 the group the denial E3 covers (S5), E2 the cold-snare removal of L2 (S6),
    single, in the transverse colon; no identity written - the faithful filing of a group and a member, for which the
    contract has no link."""
    return colonoscopy(text, removal('E2', 'S6', 'L2', removed_words, 'transverse_colon', 'transverse colon'),
                       denial('E3', 'S7', 'snare', 'Polypectomy', 'was not performed', 'L1', denied_words),
                       lesions=[entry('L1', 'S5', group_words, 'group', place=place, place_words=place_words),
                                entry('L2', 'S6', removed_words, place='transverse_colon',
                                      place_words='transverse colon')])


def outside_answer():
    return member_answer(OUTSIDE, 'Two polyps', 'rectum', 'rectum', 'A 5 mm polyp', 'the rectal polyps')


def reverse_answer():
    """REVERSE's answer: E2 removes L1, a group of three in the sigmoid colon; E3 denies a snare polypectomy on L2, one
    polyp (S6)."""
    return colonoscopy(REVERSE, removal('E2', 'S5', 'L1', 'Three polyps', 'sigmoid_colon', 'sigmoid colon',
                                        status_words='were removed'),
                       denial('E3', 'S6', 'snare', 'snare polypectomy', 'was performed', 'L2', 'the 9 mm sigmoid polyp'),
                       lesions=[entry('L1', 'S5', 'Three polyps', 'group', place='sigmoid_colon',
                                      place_words='sigmoid colon'),
                                entry('L2', 'S6', 'the 9 mm sigmoid polyp')])


def forms(claim_set):
    """Each lesion pair as (lesion, other, its claim's template, its control's template, both sentences)."""
    out = []
    for pair in claim_set.lesion_pairs:
        claim, control = claim_set.claim(pair.claim), claim_set.claim(pair.control)
        out.append((pair.lesion, pair.other, claim.template, control.template, claim_set.sentences[pair.claim],
                    claim_set.sentences[pair.control]))
    return out


def card(claim_set, name):
    return next(card_id for card_id, found in claim_set.objects.items() if found == (LP.xs.Family.LESION, name))


class R2CLMembershipTests(SimpleTestCase):
    def test_rcl_a_group_statement_asks_the_membership_of_the_acts_lesion(self):
        claim_set = LP.request(MEMBER, member_answer())[2].claim_set
        group, removed = card(claim_set, 'L1'), card(claim_set, 'L2')
        self.assertEqual(forms(claim_set), [
            ('L1', 'L2', 'lesion.not_member', 'lesion.member', f'Lesion {removed} is not one of the lesions of {group}.',
             f'Lesion {removed} is one of the lesions of {group}.')])
        pair = claim_set.lesion_pairs[0]
        self.assertIn(pair.control, claim_set.controls)
        self.assertNotIn(pair.claim, claim_set.controls)
        self.assertEqual(set(claim_set.claim(pair.claim).units), {'S5', 'S6'})  # both description runs, no act's

    def test_rcl_a_group_act_asks_whether_any_of_its_lesions_is_one_of_the_statements(self):
        claim_set = LP.request(REVERSE, reverse_answer())[2].claim_set
        group, denied = card(claim_set, 'L1'), card(claim_set, 'L2')
        self.assertEqual(forms(claim_set), [
            ('L2', 'L1', 'lesion.not_member.any', 'lesion.member.any',
             f'No lesion of {group} is one of the lesions of {denied}.',
             f'A lesion of {group} is one of the lesions of {denied}.')])

    def test_rcl_a_multiplicity_not_claimed_asks_membership(self):
        claim_set = LP.request(TWO, two_answer(l3=None))[2].claim_set
        self.assertEqual([found[2:4] for found in forms(claim_set)], [('lesion.not_member', 'lesion.member')])

    def test_rcl_two_single_lesions_keep_the_distinctness(self):
        for text, data in ((TWO, two_answer()), (LP.SPLIT, LP.split_answer())):
            with self.subTest(note=text.splitlines()[5]):
                found = forms(LP.request(text, data)[2].claim_set)
                self.assertEqual([item[2:4] for item in found], [('lesion.distinct_from', 'lesion.same_as')])

    def test_rcl_a_member_of_the_denied_group_is_held(self):
        # an honest pass 2: the removed polyp is one of the two; "different lesions" stays honestly supported of a group
        # and its member (the release before D300), "is not one of" honestly rejected (D300)
        self.assertEqual(status(MEMBER, member_answer(), oracle(member=True), '45385', MEMBER_REMOVED),
                         'needs_clarification')

    def test_rcl_a_group_act_holding_the_denied_polyp_is_held(self):
        self.assertEqual(status(REVERSE, reverse_answer(), oracle(member=True), '45385', REVERSE_REMOVED),
                         'needs_clarification')

    def test_rcl_a_polyp_outside_the_denied_group_stays_ready(self):
        # the boundary: the honest reader rejects the membership, and the removal stays READY - D296's release kept
        self.assertEqual(status(OUTSIDE, outside_answer(), oracle(member=False), '45385', OUTSIDE_REMOVED), 'ready')
        self.assertEqual(status(LP.NOTE, LP.note_answer(), FAITHFUL, '45385', REMOVED), 'ready')
        self.assertEqual(status(REVERSE, reverse_answer(), oracle(member=False), '45385', REVERSE_REMOVED), 'ready')

    def test_rcl_the_distinctness_presumes_both_lesions_established_single(self):
        # pass 2 rejects that L3 is a single lesion: the distinctness asked of two lesions pass 1 called single no
        # longer tests membership, so it sets nothing apart (the pair itself established)
        claim_set, out, R, _view = run(TWO, two_answer(), oracle(contradicted=('L3',)))
        self.assertEqual([(item['lesion'], item['result']) for item in out.events['lesion_pairs']],
                         [('L3', 'supported')])
        self.assertIs(R.pair_controls[(Id.parse('L3'), A.DISTINCT_FROM, Id.parse('L1'))], False)
        self.assertEqual(status(TWO, two_answer(), oracle(contradicted=('L3',)), '45385', REMOVED),
                         'needs_clarification')

    def test_rcl_the_membership_presumes_the_acts_lesion_established_single(self):
        # pass 2 rejects that the removed L1 and L2 are single lesions: "Lesion {L1} is not one of the lesions of {L3}."
        # no longer tests membership, so neither removal is set apart from the denials (one removal kept single keeps
        # 45385 READY on that removal alone: the code is READY on any act it may rest on)
        found = outcomes(LP.NOTE, LP.note_answer(), oracle(contradicted=('L1', 'L2')), ('45385', REMOVED))
        self.assertEqual(found['45385'][0], 'needs_clarification')
        self.assertEqual(status(LP.NOTE, LP.note_answer(), oracle(contradicted=('L1',)), '45385', REMOVED), 'ready')
        # the third form presumes neither: REVERSE's group act lesion contradicted single changes nothing
        self.assertEqual(status(REVERSE, reverse_answer(), oracle(member=False, contradicted=('L1', 'L2')), '45385',
                                REVERSE_REMOVED), 'ready')


# --- RF-L2: every reader of an established distinctness ------------------------------------------------------------

# The verifier's shape 1: a cold-snare removal of a placed polyp (L1), a cold-forceps biopsy of an unplaced flat lesion
# (L2) and a denial that L2 was removed. A: nothing written between L1 and L2 (the lesion pair asked); W: pass 1 writes
# L2 distinct_from L1 (the reference every reader must agree with); U: as A, the pair claim answered unclear.
BIOPSY_REMOVED = 'An 8 mm polyp in the descending colon was removed with a cold snare.'
BIOPSY_TAKEN = 'A flat lesion was sampled with cold biopsy forceps.'
BIOPSY = note(BIOPSY_REMOVED, BIOPSY_TAKEN, 'The flat lesion was not removed.')
BIOPSY_CODES = (('45385', BIOPSY_REMOVED), ('45380', BIOPSY_TAKEN))


def biopsy_answer(written=False):
    l2 = dict(distinct_from=[fact('L1', src(['S6'], 'A flat lesion'))]) if written else {}
    return colonoscopy(BIOPSY, removal('E2', 'S5', 'L1', 'An 8 mm polyp', 'descending_colon', 'descending colon'),
                       biopsy('E3', 'S6', 'L2', 'A flat lesion'),
                       denial('E4', 'S7', 'removal', 'removed', 'was not removed', 'L2', 'The flat lesion'),
                       lesions=[entry('L1', 'S5', 'An 8 mm polyp', place='descending_colon',
                                      place_words='descending colon'),
                                entry('L2', 'S6', 'A flat lesion', **l2)])


def readers(R):
    """What each reader of an established distinctness reads between the biopsy E3 (on L2) and the removal E2 (on L1),
    and between the denial E4 and E2."""
    E2, E3, E4, L1, L2 = ids('E2', 'E3', 'E4', 'L1', 'L2')
    return {'established_distinct': F.established_distinct(R, L2, L1), 'apart_by_lesion': F.apart_by_lesion(R, E4, E2),
            'target row': pairing.relation(R, E4, E2).relation, 'bundling': coverage._apart(R, E3, E2,
                                                                                           coverage._SameAs(R)),
            'one stricture': combination.one_stricture(R, E3, E2), 'lesions_distinct':
                combination.lesions_distinct(R, L2, L1)}


class R2CLReaderTests(SimpleTestCase):
    def setUp(self):
        self.appraised = run(BIOPSY, biopsy_answer(), FAITHFUL)
        self.written = run(BIOPSY, biopsy_answer(written=True), FAITHFUL)

    def test_rcl_the_pair_is_asked_in_one_shape_and_written_in_the_other(self):
        self.assertEqual([(pair.lesion, pair.other) for pair in self.appraised[0].lesion_pairs], [('L2', 'L1')])
        self.assertEqual(self.written[0].lesion_pairs, ())

    def test_rcl_each_reader_reads_the_appraised_distinctness_as_the_written_one(self):
        appraised, written = readers(self.appraised[2]), readers(self.written[2])
        for name in written:
            with self.subTest(reader=name):
                self.assertEqual(appraised[name], written[name])
        self.assertEqual(written, {'established_distinct': True, 'apart_by_lesion': True,
                                   'target row': pairing.Relation.INDEPENDENT, 'bundling': True,
                                   'one stricture': False, 'lesions_distinct': True})

    def test_rcl_the_modifier_review_reads_it(self):
        expected = {'45385': ('ready', (), ('59|XS',)), '45380': ('ready', (), ('59|XS',))}
        self.assertEqual(outcomes(BIOPSY, biopsy_answer(written=True), FAITHFUL, *BIOPSY_CODES), expected)
        self.assertEqual(outcomes(BIOPSY, biopsy_answer(), FAITHFUL, *BIOPSY_CODES), expected)

    def test_rcl_the_listed_and_own_arms_read_it(self):
        # EF: a listed statement (single listed lesion L3) and an act-filed possible statement (on L3), each beside the
        # snare E2 on L1, every lesion pair control between them rejected - the appraised pair reads as the written
        # DECISIONS D302 RF2C-L1 (round r2e): both lesions filed single - the one multiplicity under which a written
        # distinct_from, like D296's appraised distinctness, sets two lesions apart (none was filed before r2e)
        for arm in ('listed', 'own'):
            results = []
            for how in ('appraised', 'written'):
                doc = EF.colonoscopy()
                doc.lesions[EF.L(1)] = {**doc.lesions[EF.L(1)], A.MULTIPLICITY: (EF.sup(ct.Multiplicity.SINGLE),)}
                doc.lesion(3, distinct_from=[EF.sup(EF.L(1))] if how == 'written' else [],
                           multiplicity=EF.sup(ct.Multiplicity.SINGLE))
                if arm == 'listed':
                    doc.act(3, ct.Kind.SNARE, status=EF.neg(ct.Status.PERFORMED),
                            breadth=EF.sup(ct.Breadth.LISTED_TARGETS), targets=[EF.sup(EF.L(3))], places=None)
                else:
                    doc.act(3, ct.Kind.SNARE, status=EF.unres(ct.Status.PERFORMED), lesion=EF.sup(EF.L(3)),
                            places=None)
                doc.controls.update({(EF.E(3), A.TARGET_LESION, EF.L(1)): True,
                                     (EF.E(2), A.TARGET_LESION, EF.L(3)): True})
                if how == 'appraised':
                    doc.controls[(EF.L(3), A.DISTINCT_FROM, EF.L(1))] = True
                results.append(pairing.rows(doc.build(), EF.E(3), EF.E(2)))
            with self.subTest(arm=arm):
                self.assertEqual(results[0], results[1])
                self.assertIn((pairing.Row.TARGET, pairing.RowResult.INDEPENDENT), results[0])

    def test_rcl_an_unestablished_pair_sets_nothing_apart_in_any_reader(self):
        # the boundary: the pair claim answered unclear - no reader sets the two apart, no 59/XS
        _claim_set, _out, R, _view = run(BIOPSY, biopsy_answer(), oracle(pair_claim='unclear'))
        found = readers(R)
        self.assertEqual({name: found[name] for name in ('established_distinct', 'apart_by_lesion', 'bundling',
                                                          'lesions_distinct')},
                         {'established_distinct': False, 'apart_by_lesion': False, 'bundling': False,
                          'lesions_distinct': False})
        self.assertTrue(found['one stricture'])
        statuses = outcomes(BIOPSY, biopsy_answer(), oracle(pair_claim='unclear'), *BIOPSY_CODES)
        self.assertFalse(any(considerations for _status, _causes, considerations in statuses.values()))


# --- RF-L4: the store reads a supported pair only as its stored verdicts establish it ---------------------------------

def forged(text, out, change):
    """store.row_v2 of ``out`` (the product's pair) with ``change(events)`` applied to a deep copy of its events."""
    events = json.loads(json.dumps(store._v2_jsonable(out.events, 'events')))
    change(events)
    return LP.row(text, settle.Settled(events=events, verification=out.verification))


def claim_of(events, claim_id):
    return next(item for item in events['claims'] if item['id'] == claim_id)


class R2CLStoreTests(SimpleTestCase):
    def setUp(self):
        self.claim_set, self.out, _R, _view = run(LP.NOTE, LP.note_answer(), FAITHFUL)
        self.pair = self.out.events['lesion_pairs'][0]
        self.assertEqual(self.pair['result'], 'supported')

    def verdict_of(self, which, **values):
        def change(events):
            claim_of(events, self.pair[which])['verdict'].update(values)
        return change

    def test_rcl_a_supported_pair_its_stored_verdicts_refute_is_refused(self):
        def no_control_verdict(events):
            claim_of(events, self.pair['control'])['verdict'] = None

        def forged_supported(events):  # the refuter's E: an unresolved pair given supported, its verdicts unchanged
            item = events['lesion_pairs'][0]
            claim_of(events, item['claim'])['verdict'].update(verdict='contradicts')
            claim_of(events, item['control'])['verdict'].update(verdict='supports')
        for name, change in (('claim contradicted', self.verdict_of('claim', verdict='contradicts')),
                             ('claim unclear', self.verdict_of('claim', verdict='unclear')),
                             ('claim qualified hedged', self.verdict_of('claim', qualifiers=['hedged'])),
                             ('claim detached', self.verdict_of('claim', attached='no')),
                             ('no evidence', self.verdict_of('claim', evidence=[])),
                             ('evidence no unit of the row', self.verdict_of('claim', evidence=['S99'])),
                             ('control supported', self.verdict_of('control', verdict='supports')),
                             ('control unclear', self.verdict_of('control', verdict='unclear')),
                             ('control unanswered', no_control_verdict), ('refuter E', forged_supported)):
            with self.subTest(forgery=name), self.assertRaises(store.StoreError):
                forged(LP.NOTE, self.out, change)

    def test_rcl_a_pair_of_mixed_forms_is_refused(self):
        def mixed(events):
            claim_of(events, self.pair['control'])['template'] = 'lesion.same_as'
        with self.assertRaises(store.StoreError):
            forged(LP.NOTE, self.out, mixed)

    def test_rcl_an_established_pair_and_an_unresolved_one_are_read(self):
        # the boundaries: the row as settled; an approximate qualifier, which never lowers (D224), on the claim's verdict;
        # and an unresolved pair whatever its verdicts (it releases nothing)
        def unresolved(events):
            events['lesion_pairs'][0].update(result='unresolved', reasons=['appraisal_unclear'])
        for name, change in (('as settled', lambda events: None),
                             ('approximate', self.verdict_of('claim', qualifiers=['approximate'])),
                             ('unresolved', unresolved)):
            with self.subTest(row=name):
                fields = forged(LP.NOTE, self.out, change)
                self.assertEqual(len(fields['events']['lesion_pairs']), 2)


# --- RF-L5: the bound drops the lesion pairs first ------------------------------------------------------------------

PLACES = ('cecum', 'ascending_colon', 'hepatic_flexure', 'transverse_colon', 'splenic_flexure', 'descending_colon',
          'sigmoid_colon', 'rectum')


def dense(removals, denials):
    """A synthetic colonoscopy of ``removals`` cold-snare removals, each of its own single placed polyp, and ``denials``
    denials, each of a removal on its own group of diminutive polyps (the refuter's probe F): every denial meets every
    removal, so the lesion pairs number removals x denials."""
    lines, events, lesions, unit = [], [], [], 5
    for index in range(removals):
        place = PLACES[index % len(PLACES)]
        words = place.replace('_', ' ')
        lines.append(f'Polyp {index + 1}, 5 mm, in the {words} was removed with a cold snare.')
        lesions.append(entry(f'L{index + 1}', f'S{unit}', f'Polyp {index + 1}', place=place, place_words=words))
        events.append(removal(f'E{index + 2}', f'S{unit}', f'L{index + 1}', f'Polyp {index + 1}', place, words))
        unit += 1
    for index in range(denials):
        lines.append(f'Group {index + 1} of diminutive polyps was not removed.')
        lid = f'L{removals + index + 1}'
        lesions.append(entry(lid, f'S{unit}', f'Group {index + 1}', 'group'))
        events.append(denial(f'E{removals + index + 2}', f'S{unit}', 'removal', 'removed', 'was not removed', lid,
                             f'Group {index + 1}'))
        unit += 1
    text = note(*lines)
    return text, colonoscopy(text, *events, lesions=lesions)


def built(text, data):
    read = LP.read_answer(text, data)
    checked = checks.check(text, (), read)
    return read, checked, appraise_prompt.build_request_fable(text, (), 'txt', read, findings=checked.findings)


class R2CLBoundTests(SimpleTestCase):
    def test_rcl_a_set_over_the_bound_drops_its_lesion_pairs_first(self):
        # 20 removals x 8 denials: 160 lesion pairs, 320 claims beside 859; the set is sent with the pairs that fit
        text, data = dense(20, 8)
        read, checked, request = built(text, data)
        claim_set, bound = request.claim_set, CL.claim_bound(V3)
        kept = [(pair.lesion, pair.other) for pair in claim_set.lesion_pairs]
        dropped = list(claim_set.dropped_lesion_pairs)
        self.assertLessEqual(len(claim_set.claims), bound)
        self.assertGreater(len(claim_set.claims) + 2, bound)  # one more pair would pass it
        self.assertEqual(len(kept) + len(dropped), 160)
        self.assertEqual(len(set(kept) | set(dropped)), 160)
        self.assertEqual(len(dropped), math.ceil((859 + 320 - bound) / 2))
        # settle records each drop unappraised, the store keeps it, the FactSet reads it as not established
        roles = roles_of(claim_set)
        appraisal = appraise_read.read(json.dumps({'verdicts': [faithful(claim, roles[claim.id], claim_set)
                                                                for claim in claim_set.claims], 'unlisted': []}),
                                       claim_set, len(segment.units(text)))
        out = settle.settle(read, checked, claim_set, request.indistinct, appraisal, USAGE, appraisal_version=V3)
        stored = {(item['lesion'], item['other']): item for item in out.events['lesion_pairs']}
        for lesion_id, other in dropped:
            self.assertEqual(stored[(lesion_id, other)], {'lesion': lesion_id, 'other': other, 'claim': None,
                                                          'control': None, 'result': 'unresolved',
                                                          'reasons': ['unappraised']})
        R = F.factset(LP.view(text, LP.row(text, out)))
        for lesion_id, other in dropped:
            self.assertIs(R.pair_controls[(Id.parse(lesion_id), A.DISTINCT_FROM, Id.parse(other))], False)
        for lesion_id, other in kept:
            self.assertIs(R.pair_controls[(Id.parse(lesion_id), A.DISTINCT_FROM, Id.parse(other))], True)

    def test_rcl_a_set_over_the_bound_without_its_pairs_is_still_refused(self):
        text, data = dense(24, 8)  # 1,007 claims without a lesion pair
        with self.assertRaises(appraise_prompt.OverBound):
            built(text, data)

    def test_rcl_a_set_within_the_bound_keeps_every_pair(self):
        text, data = dense(10, 2)
        claim_set = built(text, data)[2].claim_set
        self.assertEqual((len(claim_set.lesion_pairs), claim_set.dropped_lesion_pairs), (20, ()))


# --- RF-L6: a row stored before D296 reads as no pair asked ------------------------------------------------------------

def fixture_row(name):
    return json.loads((FIXTURES / name).read_text(encoding='utf-8'))['fields']


def load(fields):
    return store.load_v2(fields, text_sha256=hashlib.sha256(LP.NOTE.encode('utf-8')).hexdigest(),
                         response_sha256='3' * 64, appraisal_response_sha256='5' * 64)


class R2CLOlderRowTests(SimpleTestCase):
    def test_rcl_a_de28c5187_row_without_lesion_pairs_is_read_as_none_asked(self):
        fields = fixture_row('de28c5187-row.json')
        self.assertEqual((fields['interpretation_version'], fields['inventory_version']), jobs.V2_VERSIONS)
        self.assertNotIn('lesion_pairs', fields['events'])
        R = F.factset(store.textfree_v2(load(fields)))
        self.assertFalse([key for key in R.pair_controls if key[1] is A.DISTINCT_FROM])

    def test_rcl_an_int1_row_asking_distinctness_of_a_group_reads_not_established(self):
        fields = fixture_row('int1-b424db551-row.json')
        self.assertEqual({(item['lesion'], item['other'], item['result']) for item in fields['events']['lesion_pairs']},
                         {('L3', 'L1', 'supported'), ('L3', 'L2', 'supported')})
        templates = {claim_of(fields['events'], item['claim'])['template']
                     for item in fields['events']['lesion_pairs']}
        self.assertEqual(templates, {'lesion.distinct_from'})
        R = F.factset(store.textfree_v2(load(fields)))
        for other in ('L1', 'L2'):
            self.assertIs(R.pair_controls[(Id.parse('L3'), A.DISTINCT_FROM, Id.parse(other))], False)

    def test_rcl_a_lesion_pairs_field_is_still_checked_where_it_is_stored(self):
        # the boundaries: at the @3 pair a stored field is checked as before (a pair naming a lesion the inventory does
        # not hold is refused); at the @2 pair a held list is refused, an empty one dropped (D296)
        _claim_set, out, _R, _view = run(LP.NOTE, LP.note_answer(), FAITHFUL)

        def stranger(events):
            events['lesion_pairs'][0]['other'] = 'L9'
        with self.assertRaises(store.StoreError):
            forged(LP.NOTE, out, stranger)
        with self.assertRaises(store.StoreError):
            LP.row(LP.NOTE, out, versions=store.READ_VERSIONS[0])


# --- RF-L7: a property fixture carries the release path ---------------------------------------------------------------

class R2CLPropertyFixtureTests(SimpleTestCase):
    def setUp(self):
        from tests.v2 import test_properties as TP
        self.TP = TP
        self.R, self.codes = TP.fixture(TP.LESION_PAIR_FIXTURE)

    def test_rcl_the_fixture_carries_an_established_lesion_pair_its_release_rests_on(self):
        key = (EF.L(3), A.DISTINCT_FROM, EF.L(1))
        self.assertIs(self.R.pair_controls[key], True)
        self.assertEqual(self.TP.ready(self.TP.assessed(self.R, self.codes)), frozenset({'45385'}))
        unestablished = replace(self.R, pair_controls={**self.R.pair_controls, key: False})
        self.assertEqual(self.TP.ready(self.TP.assessed(unestablished, self.codes)), frozenset())
        # the gates run over it: P-MONO's and P-INDEP's fixture list holds it, and 9.4 weakens the pair
        self.assertIn(self.TP.LESION_PAIR_FIXTURE, [name for name, _R, _codes in self.TP.fixtures()])
        self.assertIn(key, [what for _label, _weak, what in self.TP.weakenings(self.R)])

    def test_rcl_no_single_weakening_of_it_releases(self):
        before = self.TP.assessed(self.R, self.codes)
        checked = 0
        for label, weak, _what in self.TP.weakenings(self.R):
            after = self.TP.assessed(weak, self.codes)
            checked += 1
            with self.subTest(weakening=label):
                self.assertLessEqual(self.TP.ready(after), self.TP.ready(before))
                self.assertLessEqual(self.TP.excluded(after), self.TP.excluded(before))
        self.assertGreater(checked, 50)
