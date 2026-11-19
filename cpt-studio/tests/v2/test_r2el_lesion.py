"""DECISIONS D305 P4-ONLESION and D302 RF2C-L1, RF2C-L2, RF2C-L3 (round r2e, builder e-lesion). TEXT-ONLY and SYNTHETIC:
every note here is written for these tests (fictional clinicians), every pass-1 answer is built by hand with
test_settle's builders and every pass-2 answer by an oracle; nothing is sent anywhere.

Each rule is shown on an input it must change - red on the tree before round r2e (int2, commit 21e79eff7), green after -
and on a boundary it must leave alone, end to end (extract_read -> checks -> claims -> pass 2 -> settle -> store ->
assess) where the rule reaches a code:
- P4-ONLESION (R2ELOnLesion*Tests; D296's pattern extended): a statement whose single or listed target names a lesion,
  beside an act of its session whose target names NO lesion and whose places are compatible with the lesion's, asks
  "This act was not done on lesion {L}." with its contrary "This act was done on lesion {L}." (a group lesion: D300's
  membership form, "... on any of the lesions of {L}." / "... on one of the lesions of {L}."), worded kind-neutrally,
  citing the act's anchor and the lesion's description runs; settle establishes "not on" only when the claim is
  supported and the control rejected; the target row reads it as setting the act apart from that lesion. Pair 4's L04
  shape (a denial that a lifting injection was used for the resection of a polyp, a tattoo placed near the site that
  names no lesion: catalogue.covers reads a tattoo and an injection as one act) is the motivating input; a set over the
  bound drops these with the lesion pairs, the last pair-type claim asked first.
- RF2C-L1 (R2ELWrittenDistinctTests): one reading of a distinctness, written or appraised - "different lesions" sets two
  lesions apart only when both are established single; for a group or a multiplicity not established single only an
  established non-membership does, in every reader of facts.established_distinct.
- RF2C-L2 (R2ELUnnamedMemberTests): a same_as member, in any state, whose value is empty (S2's breach) opens its
  holder's component as an id the answer has no lesion of does - at claim time, in facts.possibly_one_finding, in
  coverage's join (and in the finding E1j and the site rules read).
- RF2C-L3 (R2ELStoreOutcomeTests): the store re-derives a pair-type record's releasing (supported) outcome from every
  input settle reads, 3.2.5's attachment included, and refuses a row whose supported result it does not give; an
  unresolved record is read whatever its verdicts (D300 RF-L4's boundary).
"""
from __future__ import annotations

import json
import math
from dataclasses import replace

from django.test import SimpleTestCase

from studio import interpretation, jobs
from studio.interpretation import store
from studio.interpretation.contract import appraise_read, checks, segment, settle
from studio.interpretation.contract import claims as CL
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import combination, coverage, pairing
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Attribute, Id
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_lesion_pair as LP
from tests.v2 import test_r2cl_lesion as R2CL
from tests.v2.test_settle import USAGE, colonoscopy, doubt, event, fact, faithful, roles_of, src, verdict

V3 = interpretation.APPRAISAL_VERSION_V3
A = Attribute
E2, E3, E4, E5 = (Id.parse(name) for name in ('E2', 'E3', 'E4', 'E5'))
L1, L2, L3 = (Id.parse(name) for name in ('L1', 'L2', 'L3'))
note, entry, removal, run, outcomes, status = R2CL.note, R2CL.entry, R2CL.removal, R2CL.run, R2CL.outcomes, R2CL.status
FAITHFUL = R2CL.FAITHFUL

# --- P4-ONLESION: pair 4's shape, synthetic ---------------------------------------------------------------------------

P4_REMOVED = 'A 7 mm polyp in the transverse colon was removed with a cold snare.'
P4_DENIAL = 'No lifting injection was used for the resection.'
P4_TATTOO = 'The transverse colon was tattooed 3 cm distal to the polypectomy site.'
P4 = note(P4_REMOVED,                                                                          # S5: E2 on L1
          P4_DENIAL,                                                                           # S6: E3 denies, on L1
          P4_TATTOO)                                                                           # S7: E4, no lesion
P4_CODES = (('45381', P4_TATTOO), ('45385', P4_REMOVED))
# The listed shape: two removed polyps, a denial naming both, a tattoo that names neither.
LISTED_FIRST = 'A 7 mm polyp in the transverse colon was removed with a cold snare.'
LISTED_TATTOO = 'The transverse colon was tattooed 3 cm distal to the polypectomy sites.'
LISTED = note(LISTED_FIRST,                                                                    # S5: E2 on L1
              'A 5 mm polyp in the transverse colon was removed with a cold snare.',           # S6: E3 on L2
              'No lifting injection was used for either polyp.',                               # S7: E4 denies, L1, L2
              LISTED_TATTOO)                                                                   # S8: E5, no lesion


def injection_denial(eid, unit, lid, words, *, breadth='single_target', places=('transverse_colon',)):
    """A denial that a lifting injection was used, on ``lid`` (single target), placed where its lesion is - pass 1
    places it from the removal's sentence (a placing source), as pair 4's L04 places E10 at L1's place."""
    over = dict(session=[fact('X1', src([unit]))], scope__breadth=[fact(breadth, src([unit], words))],
                target__lesion=[fact(lid, src([unit], words))])
    if places:
        over['target__places'] = [fact(place, src(['S5'], 'transverse colon', 'placing')) for place in places]
    return event(eid, [unit], 'lifting injection', 'was used', 'injection', state='negated',
                 status_source=src([unit], 'was used'), **over)


def tattoo(eid, unit, *, lesion_value=None, places=('transverse_colon',), place_words='transverse colon'):
    """A tattoo at ``unit`` that names no lesion (``lesion_value`` writes one), in ``places``."""
    over = dict(session=[fact('X1', src([unit]))])
    if places:
        over['target__places'] = [fact(place, src([unit], place_words)) for place in places]
    if lesion_value is not None:
        over['target__lesion'] = [fact(lesion_value, src([unit], 'the polypectomy site'))]
    return event(eid, [unit], 'tattooed', 'was tattooed', 'tattoo', **over)


def p4_answer(*, multiplicity='single', lesion_value=None, places=('transverse_colon',), place_words='transverse colon',
              breadth='single_target', lesion_place='transverse_colon', second_denial=False, lesion_placed=True):
    """P4's answer: E2 removes L1 (``multiplicity``, in ``lesion_place``; ``lesion_placed`` False files L1 with no
    place); E3 denies a lifting injection on L1 (single target; ``breadth`` its breadth); E4 a tattoo naming no lesion
    (``lesion_value`` names one) in ``places``; ``second_denial`` files the denial twice (E5 restating E3 at S6)."""
    events = [removal('E2', 'S5', 'L1', 'A 7 mm polyp', lesion_place, lesion_place.replace('_', ' ')),
              injection_denial('E3', 'S6', 'L1', 'the resection', breadth=breadth),
              tattoo('E4', 'S7', lesion_value=lesion_value, places=places, place_words=place_words)]
    if second_denial:
        events.append(injection_denial('E5', 'S6', 'L1', 'the resection'))
    return colonoscopy(P4, *events, lesions=[entry('L1', 'S5', 'A 7 mm polyp', multiplicity,
                                                   place=lesion_place if lesion_placed else None,
                                                   place_words=lesion_place.replace('_', ' '))])


def listed_answer():
    """LISTED's answer: E2 and E3 remove L1 and L2 (single, transverse colon); E4 denies a lifting injection on both
    (listed targets); E5 a tattoo naming no lesion in the transverse colon."""
    denial = event('E4', ['S7'], 'lifting injection', 'was used', 'injection', state='negated',
                   status_source=src(['S7'], 'was used'), session=[fact('X1', src(['S7']))],
                   scope__breadth=[fact('listed_targets', src(['S7'], 'either polyp'))],
                   scope__targets=['L1', 'L2'])
    return colonoscopy(LISTED, removal('E2', 'S5', 'L1', 'A 7 mm polyp', 'transverse_colon', 'transverse colon'),
                       removal('E3', 'S6', 'L2', 'A 5 mm polyp', 'transverse_colon', 'transverse colon'), denial,
                       tattoo('E5', 'S8'),
                       lesions=[entry('L1', 'S5', 'A 7 mm polyp', place='transverse_colon',
                                      place_words='transverse colon'),
                                entry('L2', 'S6', 'A 5 mm polyp', place='transverse_colon',
                                      place_words='transverse colon')])


def act_forms(claim_set):
    """Each act-lesion claim as (act, lesion, its claim's template, its control's template, both sentences)."""
    return [(pair.act, pair.lesion, claim_set.claim(pair.claim).template, claim_set.claim(pair.control).template,
             claim_set.sentences[pair.claim], claim_set.sentences[pair.control]) for pair in acts_of(claim_set)]


def acts_of(claim_set):
    """The claim set's act-lesion claims (none from a tree before D305, so the tests fail there by their assertions)."""
    return getattr(claim_set, 'act_lesions', ())


def card(claim_set, family, name):
    return next(card_id for card_id, found in claim_set.objects.items() if found == (family, name))


def act_oracle(claim_value='supports', control_value='contradicts'):
    """Pass 2: the act-lesion claims and their controls answered as given (None leaves them without a verdict), every
    other claim faithfully (test_settle.faithful, roles_of knowing the act-lesion roles)."""
    def oracle(claim, role, claim_set):
        pairs = acts_of(claim_set)
        for value, found in ((claim_value, {pair.claim for pair in pairs}),
                             (control_value, {pair.control for pair in pairs})):
            if claim.id in found:
                return None if value is None else verdict(claim, value)
        return faithful(claim, role, claim_set)
    return oracle


def p4_status(data, oracle=FAITHFUL, code='45381'):
    quote = dict(P4_CODES)[code]
    return status(P4, data, oracle, code, quote)


class R2ELOnLesionClaimTests(SimpleTestCase):
    def test_rel_a_denial_on_a_lesion_beside_an_act_naming_none_asks_not_on(self):
        claim_set = LP.request(P4, p4_answer())[2].claim_set
        act, lesion = card(claim_set, LP.xs.Family.EVENT, 'E4'), card(claim_set, LP.xs.Family.LESION, 'L1')
        self.assertEqual(act_forms(claim_set), [
            ('E4', 'L1', 'act.not_on_lesion', 'act.on_lesion', f'This act was not done on lesion {lesion}.',
             f'This act was done on lesion {lesion}.')])
        pair = acts_of(claim_set)[0]
        claim, control = claim_set.claim(pair.claim), claim_set.claim(pair.control)
        self.assertEqual((claim.subject, claim.value, control.subject, control.value), ('E4', 'L1', 'E4', 'L1'))
        self.assertEqual((claim_set.about[pair.claim], claim_set.about[pair.control]), (act, act))
        self.assertIn(pair.control, claim_set.controls)
        self.assertNotIn(pair.claim, claim_set.controls)
        # the act's anchor run and the lesion's description run, nothing of the statement's; no kind is named
        self.assertEqual(set(claim.units), {'S5', 'S7'})
        self.assertEqual(claim_set.lesion_pairs, ())
        self.assertFalse(any(word in claim_set.sentences[pair.claim].lower() for word in ('tattoo', 'injection')))

    def test_rel_a_group_lesion_reads_the_membership_form(self):
        for multiplicity in ('group', None):
            with self.subTest(multiplicity=multiplicity):
                claim_set = LP.request(P4, p4_answer(multiplicity=multiplicity))[2].claim_set
                lesion = card(claim_set, LP.xs.Family.LESION, 'L1')
                self.assertEqual(act_forms(claim_set), [
                    ('E4', 'L1', 'act.not_on_lesion.any', 'act.on_lesion.any',
                     f'This act was not done on any of the lesions of {lesion}.',
                     f'This act was done on one of the lesions of {lesion}.')])

    def test_rel_a_listed_statement_asks_each_listed_lesion(self):
        claim_set = LP.request(LISTED, listed_answer())[2].claim_set
        self.assertEqual([(found[0], found[1], found[2]) for found in act_forms(claim_set)],
                         [('E5', 'L1', 'act.not_on_lesion'), ('E5', 'L2', 'act.not_on_lesion')])

    def test_rel_each_act_lesion_is_asked_once(self):
        claim_set = LP.request(P4, p4_answer(second_denial=True))[2].claim_set
        self.assertEqual([(pair.act, pair.lesion) for pair in acts_of(claim_set)], [('E4', 'L1')])

    def test_rel_none_where_the_act_names_a_lesion_or_its_places_do_not_meet_the_lesions(self):
        cases = {
            'the act names the lesion': p4_answer(lesion_value='L1'),
            'the act has no place': p4_answer(places=()),
            'the act lies elsewhere': p4_answer(places=('rectum',), place_words='transverse colon'),
            'the lesion has no place': p4_answer(lesion_placed=False),
            'the statement breadth is all of its kind': p4_answer(breadth='all_of_kind'),
        }
        doubted = p4_answer()
        doubted['doubts'] = [doubt('target', ['E4'], ['S7'], 'unclear')]
        cases["a doubt names the act's target"] = doubted
        for name, data in cases.items():
            with self.subTest(case=name):
                self.assertEqual(acts_of(LP.request(P4, data)[2].claim_set), ())

    def test_rel_none_under_gemini_appraisal_at_1(self):
        claim_set = LP.request(P4, p4_answer(), version=interpretation.APPRAISAL_VERSION)[2].claim_set
        self.assertEqual(acts_of(claim_set), ())
        self.assertFalse(any(claim.template.startswith('act.not_on') or claim.template.startswith('act.on_')
                             for claim in claim_set.claims))


class R2ELOnLesionSettleTests(SimpleTestCase):
    def outcomes(self, oracle):
        _claim_set, out = LP.settled(P4, p4_answer(), oracle)
        return {(item['act'], item['lesion']): (item['result'], tuple(item['reasons']))
                for item in out.events.get('act_lesions', [])}

    def test_rel_established_only_when_the_claim_is_supported_and_its_control_rejected(self):
        self.assertEqual(self.outcomes(act_oracle()), {('E4', 'L1'): ('supported', ())})

    def test_rel_every_other_verdict_pattern_leaves_it_unresolved(self):
        for name, oracle in (('on the lesion: the control supported', act_oracle('contradicts', 'supports')),
                             ('incoherent: both supported', act_oracle('supports', 'supports')),
                             ('uninformative: both rejected', act_oracle('contradicts', 'contradicts')),
                             ('the control unanswered', act_oracle('supports', None)),
                             ('unclear', act_oracle('unclear', 'contradicts'))):
            with self.subTest(case=name):
                found = self.outcomes(oracle)
                self.assertEqual({result for result, _reasons in found.values()}, {'unresolved'})
                self.assertTrue(all(reasons for _result, reasons in found.values()))

    def test_rel_the_pair_is_stored_as_a_claim_and_a_control_about_the_acts_lesion(self):
        claim_set, out = LP.settled(P4, p4_answer(), act_oracle())
        stored = {item.id: item for item in out.events['claims']}
        self.assertEqual(len(acts_of(claim_set)), 1)
        for pair in acts_of(claim_set):
            self.assertEqual((stored[pair.claim].role.value, stored[pair.control].role.value), ('claim', 'control'))
            self.assertEqual((stored[pair.claim].attribute, stored[pair.control].attribute),
                             (A.TARGET_LESION, A.TARGET_LESION))
            self.assertEqual((stored[pair.claim].subject, stored[pair.claim].value), ('E4', 'L1'))


def forged(text, out, change):
    return R2CL.forged(text, out, change)


class R2ELOnLesionStoreTests(SimpleTestCase):
    def setUp(self):
        self.claim_set, self.out = LP.settled(P4, p4_answer(), act_oracle())

    def test_rel_the_at_3_row_keeps_the_pairs_bound_to_their_claims(self):
        fields = LP.row(P4, self.out)
        self.assertEqual([(item['act'], item['lesion'], item['result'])
                          for item in fields['events'].get('act_lesions', [])], [('E4', 'L1', 'supported')])
        R = F.factset(LP.view(P4, fields))
        self.assertIs(R.pair_controls[(E4, A.DISTINCT_FROM, L1)], True)
        self.assertTrue(F.established_not_on(R, E4, L1))

    def test_rel_a_pair_naming_no_stored_claim_of_its_form_or_object_is_refused(self):
        pair = self.out.events.get('act_lesions', [])[0]

        def own_control(events):
            events['act_lesions'][0]['control'] = events['act_lesions'][0]['claim']

        def another_act(events):
            events['act_lesions'][0]['act'] = 'E2'

        def unknown_act(events):
            events['act_lesions'][0]['act'] = 'E9'

        def repeated(events):
            events['act_lesions'].append(dict(events['act_lesions'][0]))

        def lesion_pair_form(events):
            R2CL.claim_of(events, pair['claim'])['template'] = 'lesion.not_member'
        for change in (own_control, another_act, unknown_act, repeated, lesion_pair_form):
            with self.subTest(forgery=change.__name__), self.assertRaises(store.StoreError):
                forged(P4, self.out, change)

    def test_rel_an_older_pair_drops_an_empty_list_and_refuses_a_held_one(self):
        with self.assertRaises(store.StoreError):
            LP.row(P4, self.out, versions=store.READ_VERSIONS[0])
        read, checked, built = LP.request(P4, p4_answer(), version=interpretation.APPRAISAL_VERSION)
        found = roles_of(built.claim_set)
        answer = {'verdicts': [faithful(claim, found[claim.id], built.claim_set) for claim in built.claim_set.claims],
                  'unlisted': []}
        appraisal = appraise_read.read(json.dumps(answer), built.claim_set, len(segment.units(P4)))
        older = settle.settle(read, checked, built.claim_set, built.indistinct, appraisal, USAGE, appraisal_version=V3)
        self.assertEqual(older.events['act_lesions'], [])
        fields = LP.row(P4, older, versions=store.READ_VERSIONS[0])
        self.assertNotIn('act_lesions', fields['events'])

    def test_rel_a_row_stored_without_act_lesions_reads_as_none_asked(self):
        def stored_before(events):
            del events['act_lesions']
        fields = forged(P4, self.out, stored_before)
        self.assertNotIn('act_lesions', fields['events'])
        R = F.factset(LP.view(P4, fields))
        self.assertFalse(F.established_not_on(R, E4, L1))
        self.assertNotIn((E4, A.DISTINCT_FROM, L1), R.pair_controls)


class R2ELOnLesionEngineTests(SimpleTestCase):
    def target(self, R, statement=E3, act=E4):
        return dict(pairing.rows(R, statement, act))[pairing.Row.TARGET]

    def test_rel_an_established_pair_sets_the_act_apart_from_the_lesion(self):
        _claim_set, _out, R, _view = run(P4, p4_answer(), FAITHFUL)
        self.assertTrue(F.established_not_on(R, E4, L1))
        self.assertEqual(self.target(R), pairing.RowResult.INDEPENDENT)
        self.assertEqual(pairing.relation(R, E3, E4).relation, pairing.Relation.INDEPENDENT)

    def test_rel_an_unestablished_pair_sets_nothing_apart(self):
        # the boundary: the tattoo WAS on the polyp (pass 2 supports the control): the overlapping places keep the
        # target row SAME, and the denial contradicts the tattoo as before
        _claim_set, _out, R, _view = run(P4, p4_answer(), act_oracle('contradicts', 'supports'))
        self.assertIsNot(R.pair_controls.get((E4, A.DISTINCT_FROM, L1)), True)
        self.assertEqual(self.target(R), pairing.RowResult.SAME)
        self.assertEqual(pairing.relation(R, E3, E4).relation, pairing.Relation.CONTRADICTION)

    def test_rel_the_single_form_presumes_the_lesion_established_single(self):
        # pass 2 rejects that L1 is one lesion: "This act was not done on lesion L1." no longer reads, though the pair
        # itself is established; the membership form (L1 claimed a group) presumes nothing
        oracle = R2CL.oracle(contradicted=('L1',))
        claim_set, out, R, _view = run(P4, p4_answer(), oracle)
        self.assertEqual([(item['act'], item['result']) for item in out.events.get('act_lesions', [])],
                         [('E4', 'supported')])
        self.assertIs(R.pair_controls[(E4, A.DISTINCT_FROM, L1)], False)
        self.assertNotEqual(self.target(R), pairing.RowResult.INDEPENDENT)
        _claim_set, _out, R, _view = run(P4, p4_answer(multiplicity='group'), FAITHFUL)
        self.assertIs(R.pair_controls[(E4, A.DISTINCT_FROM, L1)], True)
        self.assertEqual(self.target(R), pairing.RowResult.INDEPENDENT)

    def test_rel_a_listed_target_needs_every_lesion_and_reads_every_pair_of_the_act(self):
        def listed(*, l1=True, l2=True, deleted=False):
            doc = EF.colonoscopy(places=[EF.sup(ct.Landmark.TRANSVERSE_COLON)])
            doc.lesions[L1] = EF.facts_of(multiplicity=EF.sup(ct.Multiplicity.SINGLE),
                                          lesion_places=[EF.sup(ct.Landmark.TRANSVERSE_COLON)])
            doc.lesion(2, multiplicity=EF.sup(ct.Multiplicity.SINGLE),
                       lesion_places=[EF.sup(ct.Landmark.TRANSVERSE_COLON)])
            targets = [EF.sup(L1)] if deleted else [EF.sup(L1), EF.sup(L2)]
            doc.act(3, ct.Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=EF.sup(ct.Breadth.LISTED_TARGETS),
                    targets=targets, places=[EF.sup(ct.Landmark.TRANSVERSE_COLON)])
            doc.act(4, ct.Kind.TATTOO, places=[EF.sup(ct.Landmark.TRANSVERSE_COLON)])
            doc.controls.update({(E4, A.DISTINCT_FROM, L1): l1, (E4, A.DISTINCT_FROM, L2): l2})
            return doc.build()
        self.assertEqual(self.target(listed()), pairing.RowResult.INDEPENDENT)
        self.assertEqual(self.target(listed(l2=False)), pairing.RowResult.SAME)
        # 9.4's deletion of the listed L2 leaves its unestablished pair read: the pair stays together
        self.assertEqual(self.target(listed(l2=False, deleted=True)), pairing.RowResult.SAME)
        self.assertEqual(self.target(listed(deleted=True)), pairing.RowResult.INDEPENDENT)

    def test_rel_an_act_naming_a_lesion_is_never_read_so(self):
        # the boundary: a pair keyed for the act is read only while its target names no lesion (an act with a lesion
        # is apart by D296's lesion pair and the pair controls, never by this)
        doc = EF.colonoscopy(places=[EF.sup(ct.Landmark.TRANSVERSE_COLON)])
        doc.lesions[L1] = EF.facts_of(multiplicity=EF.sup(ct.Multiplicity.SINGLE),
                                      lesion_places=[EF.sup(ct.Landmark.TRANSVERSE_COLON)])
        doc.act(3, ct.Kind.INJECTION, status=EF.neg(ct.Status.PERFORMED), breadth=EF.sup(ct.Breadth.SINGLE_TARGET),
                lesion=EF.sup(L1), places=[EF.sup(ct.Landmark.TRANSVERSE_COLON)])
        doc.act(4, ct.Kind.TATTOO, places=[EF.sup(ct.Landmark.TRANSVERSE_COLON)], lesion=EF.unres(L1))
        doc.controls[(E4, A.DISTINCT_FROM, L1)] = True
        self.assertNotEqual(self.target(doc.build()), pairing.RowResult.INDEPENDENT)


class R2ELOnLesionPipelineTests(SimpleTestCase):
    def test_rel_the_tattoo_near_the_site_is_ready(self):
        found = outcomes(P4, p4_answer(), FAITHFUL, *P4_CODES)
        self.assertEqual(found['45381'][:2], ('ready', ()))
        self.assertEqual(found['45385'][0], 'ready')

    def test_rel_a_tattoo_on_the_lesion_stays_held(self):
        for name, oracle in (('on the lesion', act_oracle('contradicts', 'supports')),
                             ('incoherent', act_oracle('supports', 'supports')),
                             ('uninformative', act_oracle('contradicts', 'contradicts'))):
            with self.subTest(case=name):
                found = outcomes(P4, p4_answer(), oracle, *P4_CODES)
                self.assertEqual(found['45381'][:2], ('needs_clarification', ('relation:contradiction',)))

    def test_rel_a_tattoo_naming_the_lesion_stays_held(self):
        # the boundary: an act whose target names the denied lesion is the denial's very act (no act-lesion claim)
        found = outcomes(P4, p4_answer(lesion_value='L1'), FAITHFUL, *P4_CODES)
        self.assertEqual(found['45381'][:2], ('needs_clarification', ('relation:contradiction',)))

    def test_rel_a_listed_denial_beside_a_tattoo_naming_neither_polyp(self):
        found = outcomes(LISTED, listed_answer(), FAITHFUL, ('45381', LISTED_TATTOO))
        self.assertEqual(found['45381'][:2], ('ready', ()))


# --- the bound: the pair-type claims dropped first, the last asked first ----------------------------------------------

def dense(removals, denials):
    """A synthetic colonoscopy of ``removals`` cold-snare removals, each of its own single polyp in the transverse
    colon, ``denials`` denials, each of a removal on its own group of diminutive polyps in the transverse colon, and one
    snare resection in the transverse colon that names no lesion: every denial meets every removal (a lesion pair each,
    D296/D300) and the unnamed resection (an act-lesion claim each, D305), so each denial asks its lesion pairs and then
    its act-lesion claim."""
    lines, events, lesions, unit = [], [], [], 5
    for index in range(removals):
        lines.append(f'Polyp {index + 1}, 5 mm, in the transverse colon was removed with a cold snare.')
        lesions.append(entry(f'L{index + 1}', f'S{unit}', f'Polyp {index + 1}', place='transverse_colon',
                             place_words='transverse colon'))
        events.append(removal(f'E{index + 2}', f'S{unit}', f'L{index + 1}', f'Polyp {index + 1}', 'transverse_colon',
                              'transverse colon'))
        unit += 1
    for index in range(denials):
        lines.append(f'Group {index + 1} of diminutive polyps in the transverse colon was not removed.')
        lid = f'L{removals + index + 1}'
        lesions.append(entry(lid, f'S{unit}', f'Group {index + 1}', 'group', place='transverse_colon',
                             place_words='transverse colon'))
        events.append(R2CL.denial(f'E{removals + index + 2}', f'S{unit}', 'removal', 'removed', 'was not removed', lid,
                                  f'Group {index + 1}'))
        unit += 1
    lines.append('A snare resection was performed in the transverse colon.')
    events.append(event(f'E{removals + denials + 2}', [f'S{unit}'], 'snare resection', 'was performed', 'snare',
                        session=[fact('X1', src([f'S{unit}']))],
                        target__places=[fact('transverse_colon', src([f'S{unit}'], 'transverse colon'))]))
    text = note(*lines)
    return text, colonoscopy(text, *events, lesions=lesions)


class R2ELBoundTests(SimpleTestCase):
    def test_rel_a_set_over_the_bound_drops_the_pair_type_claims_last_asked_first(self):
        # 20 removals x 8 denials (160 lesion pairs) and 8 act-lesion claims (the unnamed resection E30 against each
        # denial's group): the set is sent with the pair-type claims that fit, the last asked dropped first across both
        text, data = dense(20, 8)
        read, checked, request = R2CL.built(text, data)
        claim_set, bound = request.claim_set, CL.claim_bound(V3)
        self.assertLessEqual(len(claim_set.claims), bound)
        self.assertGreater(len(claim_set.claims) + 2, bound)  # one more pair-type claim would pass it
        asked = []  # the asking order: each denial's lesion pairs, then its act-lesion claim
        for index in range(8):
            mine = f'L{21 + index}'
            asked += [('lesion_pair', (mine, f'L{other}')) for other in range(1, 21)] + [('act_lesion', ('E30', mine))]
        kept = [('lesion_pair', (pair.lesion, pair.other)) for pair in claim_set.lesion_pairs]
        kept += [('act_lesion', (pair.act, pair.lesion)) for pair in acts_of(claim_set)]
        dropped = [('lesion_pair', pair) for pair in claim_set.dropped_lesion_pairs]
        dropped += [('act_lesion', pair) for pair in getattr(claim_set, 'dropped_act_lesions', ())]
        self.assertEqual(len(kept) + len(dropped), len(asked))
        self.assertEqual(set(dropped), set(asked[len(asked) - len(dropped):]))
        self.assertEqual(set(kept), set(asked[:len(asked) - len(dropped)]))
        self.assertTrue(getattr(claim_set, 'dropped_act_lesions', ()) and acts_of(claim_set))  # both kinds, both sides
        # settle records each drop unappraised, the store keeps it, the FactSet reads it as not established
        roles = roles_of(claim_set)
        appraisal = appraise_read.read(json.dumps({'verdicts': [faithful(claim, roles[claim.id], claim_set)
                                                                for claim in claim_set.claims], 'unlisted': []}),
                                       claim_set, len(segment.units(text)))
        out = settle.settle(read, checked, claim_set, request.indistinct, appraisal, USAGE, appraisal_version=V3)
        stored = {(item['act'], item['lesion']): item for item in out.events.get('act_lesions', [])}
        for act, lesion in getattr(claim_set, 'dropped_act_lesions', ()):
            self.assertEqual(stored[(act, lesion)], {'act': act, 'lesion': lesion, 'claim': None, 'control': None,
                                                     'result': 'unresolved', 'reasons': ['unappraised']})
        R = F.factset(LP.view(text, LP.row(text, out)))
        for act, lesion in getattr(claim_set, 'dropped_act_lesions', ()):
            self.assertFalse(F.established_not_on(R, Id.parse(act), Id.parse(lesion)))
        for pair in acts_of(claim_set):
            self.assertTrue(F.established_not_on(R, Id.parse(pair.act), Id.parse(pair.lesion)))

    def test_rel_a_set_within_the_bound_keeps_every_pair_type_claim(self):
        text, data = dense(4, 3)
        claim_set = R2CL.built(text, data)[2].claim_set
        self.assertEqual((len(acts_of(claim_set)), getattr(claim_set, 'dropped_act_lesions', ())), (3, ()))
        self.assertEqual((len(claim_set.lesion_pairs), claim_set.dropped_lesion_pairs), (12, ()))
        self.assertEqual({claim_set.claim(pair.claim).template for pair in acts_of(claim_set)},
                         {'act.not_on_lesion.any'})  # each denial's lesion a group: D300's membership form


# --- the property fixture: P-MONO and P-INDEP run over the release path -----------------------------------------------

class R2ELPropertyFixtureTests(SimpleTestCase):
    def setUp(self):
        from tests.v2 import test_properties as TP
        self.TP = TP
        self.R, self.codes = TP.fixture(TP.ACT_LESION_FIXTURE)

    def test_rel_the_fixture_carries_an_established_act_lesion_its_release_rests_on(self):
        key = (EF.E(4), A.DISTINCT_FROM, EF.L(1))
        self.assertIs(self.R.pair_controls[key], True)
        self.assertIn('45381', self.TP.ready(self.TP.assessed(self.R, self.codes)))
        unestablished = replace(self.R, pair_controls={**self.R.pair_controls, key: False})
        self.assertNotIn('45381', self.TP.ready(self.TP.assessed(unestablished, self.codes)))
        self.assertIn(self.TP.ACT_LESION_FIXTURE, [name for name, _R, _codes in self.TP.fixtures()])
        self.assertIn(key, [what for _label, _weak, what in self.TP.weakenings(self.R)])

    def test_rel_no_single_weakening_of_it_releases(self):
        before = self.TP.assessed(self.R, self.codes)
        checked = 0
        for label, weak, _what in self.TP.weakenings(self.R):
            after = self.TP.assessed(weak, self.codes)
            checked += 1
            with self.subTest(weakening=label):
                self.assertLessEqual(self.TP.ready(after), self.TP.ready(before))
                self.assertLessEqual(self.TP.excluded(after), self.TP.excluded(before))
        self.assertGreater(checked, 40)


# --- RF2C-L1: one reading of a distinctness, written or appraised --------------------------------------------------

def member_written(direction=('L2', 'L1')):
    """R2CL's MEMBER answer (L1 a denied group of two polyps, L2 the removed one, a member) with pass 1 writing a
    distinct_from between them - the refuter's P01 and the verifier's G-b: a link the document does not state."""
    data = R2CL.member_answer()
    holder, other = direction
    unit, words = {'L1': ('S5', 'Two polyps'), 'L2': ('S6', 'The 5 mm polyp')}[holder]
    item = next(found for found in data['lesions'] if found['id'] == holder)
    item['distinct_from'] = [fact(other, src([unit], words))]
    return data


def two_written(l3='single'):
    """R2CL's TWO answer (two polyps) with pass 1 writing L3 distinct_from L1 - two single lesions (``l3`` L3's claimed
    multiplicity)."""
    data = R2CL.two_answer(l3=l3)
    item = next(found for found in data['lesions'] if found['id'] == 'L3')
    item['distinct_from'] = [fact('L1', src(['S6'], 'Another polyp'))]
    return data


class R2ELWrittenDistinctTests(SimpleTestCase):
    def test_rel_a_written_distinctness_of_a_group_and_its_member_sets_nothing_apart(self):
        for direction in (('L2', 'L1'), ('L1', 'L2')):
            with self.subTest(written=direction):
                claim_set, _out, R, _view = run(R2CL.MEMBER, member_written(direction), R2CL.oracle(member=True))
                self.assertEqual(claim_set.lesion_pairs, ())  # pass 1 wrote it, so no pair asks it again
                self.assertFalse(F.established_distinct(R, L2, L1))
                self.assertEqual(status(R2CL.MEMBER, member_written(direction), R2CL.oracle(member=True), '45385',
                                        R2CL.MEMBER_REMOVED), 'needs_clarification')

    def test_rel_a_written_distinctness_of_a_lesion_not_established_single_sets_nothing_apart(self):
        # the refuter's P03 (b): the written twin of D300's appraised pair, L3's single multiplicity rejected by pass 2,
        # reads as the appraised one does: held
        _claim_set, _out, R, _view = run(R2CL.TWO, two_written(), R2CL.oracle(contradicted=('L3',)))
        self.assertFalse(F.established_distinct(R, L3, L1))
        self.assertEqual(status(R2CL.TWO, two_written(), R2CL.oracle(contradicted=('L3',)), '45385', R2CL.REMOVED),
                         'needs_clarification')
        # and a multiplicity pass 1 never claimed
        self.assertEqual(status(R2CL.TWO, two_written(l3=None), FAITHFUL, '45385', R2CL.REMOVED), 'needs_clarification')

    def test_rel_two_single_lesions_written_distinct_stay_apart(self):
        # the boundary: both established single - the written distinctness sets them apart, as before
        _claim_set, _out, R, _view = run(R2CL.TWO, two_written(), FAITHFUL)
        self.assertTrue(F.established_distinct(R, L3, L1))
        self.assertEqual(status(R2CL.TWO, two_written(), FAITHFUL, '45385', R2CL.REMOVED), 'ready')

    def test_rel_an_established_non_membership_still_sets_a_group_apart(self):
        # the boundary: D300's membership pair, the honest reader rejecting the membership
        self.assertEqual(status(R2CL.OUTSIDE, R2CL.outside_answer(), R2CL.oracle(member=False), '45385',
                                R2CL.OUTSIDE_REMOVED), 'ready')

    def test_rel_every_reader_reads_the_written_distinctness_of_a_group_as_not_established(self):
        # R2CL's BIOPSY shape with L2 (the biopsied flat lesion) filed a group: every reader of established_distinct
        # now reads the written link as nothing (the target row, bundling, D118, 59/XS); two singles still apart
        def answer(multiplicity):
            data = R2CL.biopsy_answer(written=True)
            item = next(found for found in data['lesions'] if found['id'] == 'L2')
            item['multiplicity'] = [] if multiplicity is None else [fact(multiplicity, src(['S6'], 'A flat lesion'))]
            return data
        for multiplicity, expected in (('single', True), ('group', False), (None, False)):
            with self.subTest(multiplicity=multiplicity):
                found = R2CL.readers(run(R2CL.BIOPSY, answer(multiplicity), FAITHFUL)[2])
                self.assertEqual({name: found[name] for name in ('established_distinct', 'apart_by_lesion', 'bundling',
                                                                  'lesions_distinct')},
                                 dict.fromkeys(('established_distinct', 'apart_by_lesion', 'bundling',
                                                'lesions_distinct'), expected))
                self.assertEqual(found['one stricture'], not expected)
                self.assertEqual(found['target row'] is pairing.Relation.INDEPENDENT, expected)

    def test_rel_the_listed_and_own_arms_read_it(self):
        # EF: a listed statement and an act-filed possible statement on L3 beside the snare E2 on L1, every lesion pair
        # control rejected, L3 distinct_from L1 written: apart only with both lesions established single
        for arm in ('listed', 'own'):
            results = {}
            for single in (True, False):
                doc = EF.colonoscopy()
                multiplicity = EF.sup(ct.Multiplicity.SINGLE) if single else EF.unres(ct.Multiplicity.SINGLE)
                doc.lesions[L1] = {**doc.lesions[L1], A.MULTIPLICITY: (multiplicity,)}
                doc.lesion(3, distinct_from=[EF.sup(L1)], multiplicity=EF.sup(ct.Multiplicity.SINGLE))
                if arm == 'listed':
                    doc.act(3, ct.Kind.SNARE, status=EF.neg(ct.Status.PERFORMED),
                            breadth=EF.sup(ct.Breadth.LISTED_TARGETS), targets=[EF.sup(L3)], places=None)
                else:
                    doc.act(3, ct.Kind.SNARE, status=EF.unres(ct.Status.PERFORMED), lesion=EF.sup(L3), places=None)
                doc.controls.update({(E3, A.TARGET_LESION, L1): True, (E2, A.TARGET_LESION, L3): True})
                results[single] = dict(pairing.rows(doc.build(), E3, E2))[pairing.Row.TARGET]
            with self.subTest(arm=arm):
                self.assertEqual(results[True], pairing.RowResult.INDEPENDENT)
                self.assertNotEqual(results[False], pairing.RowResult.INDEPENDENT)


# --- RF2C-L2: a same_as member whose value is empty opens its holder's component -------------------------------------

def two_same_as(value, state='supported'):
    """R2CL's TWO answer with L3's same_as holding one member of ``value`` ('' is S2's item-level breach)."""
    data = R2CL.two_answer()
    item = next(found for found in data['lesions'] if found['id'] == 'L3')
    item['same_as'] = [fact(value, src(['S6'], 'Another polyp'), state=state)]
    return data


class R2ELUnnamedMemberTests(SimpleTestCase):
    def test_rel_an_empty_same_as_member_asks_no_pair_and_holds(self):
        for state in ('supported', 'negated'):
            with self.subTest(state=state):
                claim_set, _out, R, _view = run(R2CL.TWO, two_same_as('', state), FAITHFUL)
                self.assertEqual(claim_set.lesion_pairs, ())
                self.assertTrue(F.possibly_one_finding(R, L3, L1))
                self.assertIsNotNone(coverage._SameAs(R).join((L3,), (L1,)))
                self.assertFalse(F.established_distinct(R, L3, L1))
                self.assertEqual(status(R2CL.TWO, two_same_as('', state), FAITHFUL, '45385', R2CL.REMOVED),
                                 'needs_clarification')

    def test_rel_the_finding_holds_an_unknown_entry(self):
        _claim_set, _out, R, _view = run(R2CL.TWO, two_same_as(''), FAITHFUL)
        found = F.finding_places(R, L3)
        self.assertIsNotNone(found.unknown)
        self.assertNotIn(found.unknown, R.lesions)
        self.assertEqual(len(found.entries), 2)

    def test_rel_no_member_and_named_members_read_as_before(self):
        # the boundaries: no identity written - D296's release; an id the answer has no lesion of, and the act's own
        # lesion - held, as before
        claim_set, _out, R, _view = run(R2CL.TWO, R2CL.two_answer(), FAITHFUL)
        self.assertEqual([(pair.lesion, pair.other) for pair in claim_set.lesion_pairs], [('L3', 'L1')])
        self.assertFalse(F.possibly_one_finding(R, L3, L1))
        self.assertEqual(status(R2CL.TWO, R2CL.two_answer(), FAITHFUL, '45385', R2CL.REMOVED), 'ready')
        for value in ('L9', 'L1'):
            with self.subTest(value=value):
                self.assertEqual(status(R2CL.TWO, two_same_as(value), FAITHFUL, '45385', R2CL.REMOVED),
                                 'needs_clarification')

    def test_rel_the_engine_join_answers_as_the_coverage_join_with_unnamed_members(self):
        L4, L9 = Id.parse('L4'), Id.parse('L9')
        names = (L1, L2, L3, L4, L9)
        unnamed = EF.fact(ct.Result.UNRESOLVED, None, ct.FactState.SUPPORTED, reasons=(ct.Reason.SHAPE_INCONSISTENT,))
        negated = EF.fact(ct.Result.UNRESOLVED, None, ct.FactState.NEGATED, reasons=(ct.Reason.SHAPE_INCONSISTENT,))
        cases = {
            'one unnamed': {L3: [unnamed]},
            'one unnamed negation': {L3: [negated]},
            'two unnamed on one lesion': {L3: [unnamed, unnamed]},
            'an unnamed beside a chain': {L2: [EF.sup(L1)], L3: [unnamed]},
            'an unnamed and an unknown id': {L3: [unnamed], L4: [EF.sup(L9)]},
            'a contradiction naming ids': {L3: [EF.contra(L2, L4)]},
        }
        for name, same_as in cases.items():
            doc = EF.Doc()
            for lid in (L1, L2, L3, L4):
                doc.lesions[lid] = EF.facts_of(same_as=same_as.get(lid, ()))
            with self.subTest(case=name):
                R = doc.build()
                R2CL.joins_agree(self, R, names)
                if name.startswith('one unnamed'):
                    self.assertTrue(F.possibly_one_finding(R, L3, L1))
                    self.assertFalse(F.possibly_one_finding(R, L2, L1))
                if name == 'two unnamed on one lesion':
                    self.assertTrue(F.possibly_one_finding(R, L2, L1))  # they may be any two lesions


# --- RF2C-L3: the store re-derives a pair-type record's outcome from every input settle reads -------------------------

class R2ELStoreOutcomeTests(SimpleTestCase):
    def setUp(self):
        self.claim_set, self.out, _R, _view = run(LP.NOTE, LP.note_answer(), FAITHFUL)
        self.pair = self.out.events['lesion_pairs'][0]
        self.assertEqual(self.pair['result'], 'supported')

    def test_rel_a_supported_pair_on_evidence_detached_from_its_claim_is_refused(self):
        # the refuter's P02: the claim's verdict cites the date line (S2), a unit of the row outside the claim's units
        # and its card's - settle reads it appraisal_detached (3.2.5)
        claim_units = set(R2CL.claim_of(store._v2_jsonable(self.out.events, 'events'), self.pair['claim'])['units'])
        self.assertNotIn('S2', claim_units)

        def detached(events):
            R2CL.claim_of(events, self.pair['claim'])['verdict']['evidence'] = ['S2']
        with self.assertRaises(store.StoreError):
            forged(LP.NOTE, self.out, detached)

    def test_rel_a_supported_pair_qualified_or_unattached_is_refused(self):
        # every other input settle reads: a lowering qualifier, an attachment not yes, no evidence
        for name, values in (('hedged', dict(qualifiers=['hedged'])), ('attached no', dict(attached='no')),
                             ('no evidence', dict(evidence=[]))):
            def change(events, values=values):
                R2CL.claim_of(events, self.pair['claim'])['verdict'].update(values)
            with self.subTest(verdict=name), self.assertRaises(store.StoreError):
                forged(LP.NOTE, self.out, change)

    def test_rel_an_unresolved_pair_is_read_whatever_its_verdicts(self):
        # the boundary (D300 RF-L4's): an unresolved pair releases nothing, so its stored verdicts are not re-derived
        def unresolved(events):
            events['lesion_pairs'][0].update(result='unresolved', reasons=['appraisal_missing'])
        self.assertEqual(forged(LP.NOTE, self.out, unresolved)['events']['lesion_pairs'][0]['result'], 'unresolved')

    def test_rel_the_act_lesion_records_are_held_to_the_same_rule(self):
        _claim_set, out = LP.settled(P4, p4_answer(), act_oracle())
        pair = out.events.get('act_lesions', [])[0]

        def detached(events):
            R2CL.claim_of(events, pair['claim'])['verdict']['evidence'] = ['S2']

        def control_supported(events):
            R2CL.claim_of(events, pair['control'])['verdict']['verdict'] = 'supports'
        for change in (detached, control_supported):
            with self.subTest(forgery=change.__name__), self.assertRaises(store.StoreError):
                forged(P4, out, change)

        def unresolved(events):
            events['act_lesions'][0].update(result='unresolved', reasons=['appraisal_missing'])
        self.assertEqual(forged(P4, out, unresolved)['events']['act_lesions'][0]['result'], 'unresolved')

    def test_rel_the_settled_rows_are_read(self):
        # the boundaries: every outcome as settle stored it - established, unresolved, an evidence unit of the claim's
        # own units beside one that is not (3.2.5 needs one)
        fields = LP.row(LP.NOTE, self.out)
        self.assertTrue(F.factset(LP.view(LP.NOTE, fields)).pair_controls[(L3, A.DISTINCT_FROM, L1)])
        _claim_set, held = LP.settled(LP.NOTE, LP.note_answer(), LP.lesion_oracle('contradicts', 'supports'))
        self.assertEqual({item['result'] for item in LP.row(LP.NOTE, held)['events']['lesion_pairs']}, {'unresolved'})
        claim_units = R2CL.claim_of(store._v2_jsonable(self.out.events, 'events'), self.pair['claim'])['units']

        def one_attached(events):
            R2CL.claim_of(events, self.pair['claim'])['verdict']['evidence'] = ['S2', claim_units[0]]
        self.assertEqual(forged(LP.NOTE, self.out, one_attached)['events']['lesion_pairs'][0]['result'], 'supported')
