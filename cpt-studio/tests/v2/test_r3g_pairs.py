"""Round r3, round 5's lane "pairs2" (DECISIONS D330 (2), finding RP-1, high) - the lane's own tests. SYNTHETIC
FactSets (tests/v2 fixtures: invented ids, kinds and places); nothing is sent anywhere.

D330 (2) - A PAIR'S RELATION IS ONE PROPOSITION ACROSS EVERY ANSWER THAT CAN SET IT APART, Q-FACT INCLUDED. The fold
may set a pair apart through a row (session, timing, performer, breadth, target, technique), or drop a kept entry's
pair from unlisted_pairs; either release stands only when every pair-family question asked of the same pair, in any
request or round, read AFFIRMED in an answered, healthy request (D328 (2)'s condition); otherwise the pair keeps its
R_base relation. Built in the fold (engine/facts._answered -> ``_kept``: AnsweredFactSet's kept pairs, which
engine/pairing's paired, relation and unlisted_pairs read at R_base's relation), with ONE record reader shared with
contract/settle (engine/facts.answer_reading = settle._reading) and settle's fail-closed scopes (``_contest_of``):
- RowReleaseClassTests: the finding's own input (the refuter's test_refute_r3f_pairs, ported) - an EGD X1 and a
  colonoscopy X2, an established denial of a biopsy in the EGD (or a kept unlisted denial entry), a biopsy whose session
  is doubted; round 1 asks the pair's Q-REL beside the biopsy's session; Fable says the denial denies the biopsy (or is
  unclear, or incoherent) AND that the biopsy was taken in the colonoscopy - 45380 READY on int6 (RED there), held now.
- VariantTests: the class end to end through the stage beyond the finding's input - each row the planner asks beside
  the pair (session, performer, timing) x every answer that is not the release; the Q-REL in a refused (calibration
  breach) or failed request beside a healthy releasing row answer; the same pair in separate requests of one round; the
  reverse order across rounds; a kept unlisted entry; the flexible-sigmoidoscopy scene (45335); a different pair that
  must stay independent; and the consistent release, which stays READY.
- RowCensusTests: THE CENSUS (D328 (2)'s, extended over rows x pair-family verdict states, D330 (2)): every row a
  Q-FACT answer releases through (session, performer, timing, target, technique; a kept entry's session) x the pair's
  Q-REL in each of 22 states (absent; every claim x control verdict pair from supports, contradicts, unclear and
  missing; the release with its proof unlocated; the release in a request refused for its calibration item - breached
  (H2) or none drawn (H5) - or with no answer - failed, or cut at its output limit), and beside it a Q-ONLESION of the
  act and another pair's Q-REL; at the fold - and at READY - the pair is released exactly when every asked
  proposition about it reads AFFIRMED, the other pair by its own answer alone; P-MONO-Q: no single verdict change from
  matching to not matching grows the released set or READY. And at the rule itself (``_kept``) over EVERY row of 4.5 -
  breadth included, which no answer the fold folds can reach today - the which-pairs drop and each kept-entry drop.
- ReadingPinTests: the one record reader (engine/facts.answer_reading; settle._reading reads it) equals int6's settle
  reading on every record shape; StoredReason's values are settle's and contract/proof's.
- ScopePinTests: the fold reads a record's pairs exactly as settle.pair_scopes without a FactSet (production's
  exclusivity, D330 (3)) on every record settle_questions writes, and fail-closed beyond them.
- PlanTimeRefusalTests: the stored records are the fold's whole input because a question refused at plan time never
  stands beside an answer - every request of a stage gets its calibration item or none does.
- AnsweredFactSetTests: the kept pairs are R_q's only change; dataclasses.replace keeps them; pairing reads them in
  paired, relation, pairs_of, pairs and unlisted_pairs; no answer, or nothing contested, leaves the fold as on int6.
"""
from __future__ import annotations

import itertools
from dataclasses import fields, replace
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio.interpretation.contract import proof, settle
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, pairing
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import FactSet
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_properties as TP
from tests.v2 import test_r3f_pairs as T

A = ct.Attribute
V = ct.VerdictValue
Kind, Landmark = ct.Kind, ct.Landmark
sup, X, E, L = EF.sup, EF.X, EF.E, EF.L
FAM = asking.Family
THIS = ct.EncounterRelation.THIS_ENCOUNTER
NOT_RELEASE = (('holding', T.HOLD), ('unclear', T.UNCLEAR), ('incoherent', T.INCOHERENT))
EVERY_NOT_RELEASE = (*NOT_RELEASE, ('missing', T.MISSING), ('both supported', T.BOTH_SUPPORTED))


def _status(R_q, codes):
    return {item.code: item.status.value for item in TP.assessed(R_q, codes).codes}


def _held(R_q, codes):
    return {item.code: (item.status.value, sorted({(h.fact, h.cause, str(h.subject)) for h in item.held_facts}))
            for item in TP.assessed(R_q, codes).codes}


def relation_of(R, statement, act):
    """The pair's relation on ``R`` ('not paired' when 4.5 pairs nothing)."""
    if not pairing.paired(R, statement, act):
        return 'not paired'
    return pairing.relation(R, statement, act).relation.value


def unlisted_of(R, act):
    return tuple(pair.index for pair in pairing.unlisted_pairs(R, act))


def fact_spec(subject, attribute, value, form):
    return asking.QuestionSpec(FAM.Q_FACT, form, (subject,), attribute, value, False, (subject,), census='K')


# --- the scenes -----------------------------------------------------------------------------------------------------


def egd_and_colonoscopy():
    """An EGD X1 (E1) and a colonoscopy X2 (E5) of this encounter."""
    doc = EF.egd(encounter=sup(THIS))
    doc.session(2, ct.SessionKind.COLONOSCOPY, encounter=sup(THIS), reached=[sup(ct.Extent.CECUM)])
    doc.exam(5, session=X(2))
    return doc


def bidirectional_denial():
    """RP-1's scene: an EGD X1 and a colonoscopy X2 of this encounter (E1, E5 their examinations); E3 an ESTABLISHED
    denial that a biopsy was taken during the EGD; E4 a biopsy whose session is doubted (X1 | X2)."""
    doc = egd_and_colonoscopy()
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), session=X(1))
    doc.act(4, Kind.BIOPSY, session=EF.doubted(X(1), X(2)))
    return TA.dated(TP.paired(doc.build())), {}


def bidirectional_unlisted_denial():
    """The same visit with the denial kept as an UNLISTED entry ("no biopsies were taken", session X1) instead of E3."""
    doc = egd_and_colonoscopy()
    doc.act(4, Kind.BIOPSY, session=EF.doubted(X(1), X(2)))
    doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.DENIAL, Kind.BIOPSY, X(1), EF.unit(9)))
    return TA.dated(TP.paired(doc.build())), {}


def performer_scene():
    """The PERFORMER row: a colonoscopy X1; E3 a denial of a biopsy by ANOTHER clinician ("the fellow took no
    biopsies"); E4 a biopsy whose performer is doubted (the documenting team | another clinician)."""
    doc = EF.colonoscopy(snare=False)
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), performer=sup(ct.Performer.OTHER_CLINICIAN))
    doc.act(4, Kind.BIOPSY, performer=EF.doubted(EF.TEAM, ct.Performer.OTHER_CLINICIAN))
    return TA.dated(TP.paired(doc.build())), {}


def timing_scene():
    """The TIMING row: a colonoscopy X1; E3 a historical denial (its date relation the earlier date: "no biopsies at the
    prior colonoscopy"); E4 a biopsy whose date relation is doubted (the date of service | earlier)."""
    doc = EF.colonoscopy(snare=False)
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), date=sup(EF.EARLIER))
    doc.act(4, Kind.BIOPSY, date=EF.doubted(EF.ON, EF.EARLIER))
    return TA.dated(TP.paired(doc.build())), {}


def technique_scene():
    """The TECHNIQUE row: a colonoscopy X1, L1 a single sigmoid polyp; E3 a denial that L1 was removed with a HOT snare;
    E4 a snare removal of L1 whose device is doubted (cold | hot snare)."""
    doc = EF.colonoscopy(snare=False)
    doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
    doc.act(3, Kind.SNARE, status=EF.neg(ct.Status.PERFORMED), device=sup(ct.Device.HOT_SNARE),
            breadth=sup(ct.Breadth.SINGLE_TARGET), lesion=sup(L(1)), places=[sup(Landmark.SIGMOID_COLON)])
    doc.act(4, Kind.SNARE, device=EF.doubted(ct.Device.COLD_SNARE, ct.Device.HOT_SNARE), lesion=sup(L(1)),
            places=[sup(Landmark.SIGMOID_COLON)])
    return TA.dated(TP.paired(doc.build())), {}


def target_scene():
    """The TARGET row: a colonoscopy X1; E3 a denial of a biopsy in the sigmoid colon (a single target naming no
    lesion); E4 a biopsy whose place is doubted (the descending | the sigmoid colon)."""
    doc = EF.colonoscopy(snare=False)
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
            places=[sup(Landmark.SIGMOID_COLON)])
    doc.act(4, Kind.BIOPSY, places=[EF.doubted(Landmark.DESCENDING_COLON, Landmark.SIGMOID_COLON)])
    return TA.dated(TP.paired(doc.build())), {}


# each row a Q-FACT answer releases through: (the scene, the releasing answer, the pair's statement (an event, or a kept
# entry's index) and act, the code the pair holds)
ROWS = {
    'session': (bidirectional_denial, fact_spec('E4', A.SESSION, 'X2', 'fact.session'), E(3), '45380'),
    'performer': (performer_scene, fact_spec('E4', A.PERFORMER, 'documenting_team', 'fact.performer'), E(3), '45380'),
    'timing': (timing_scene, fact_spec('E4', A.DATE_RELATION, 'on_date_of_service', 'fact.date_relation'), E(3),
               '45380'),
    'target': (target_scene, fact_spec('E4', A.TARGET_PLACES, 'descending_colon', 'fact.target.places'), E(3),
               '45380'),
    'technique': (technique_scene, fact_spec('E4', A.TECHNIQUE_DEVICE, 'cold_snare', 'fact.technique.device'), E(3),
                  '45385'),
    'kept entry session': (bidirectional_unlisted_denial, fact_spec('E4', A.SESSION, 'X2', 'fact.session'), 0, '45380'),
}


def rel_spec(statement, act):
    """The pair's Q-REL: a kept entry (its index: 'u:<index>') in its concern form, an event (an Id) in its deny
    form."""
    if isinstance(statement, int):
        return T.rel_spec(f'{asking.UNLISTED_PREFIX}{statement}', act, form='rel')
    return T.rel_spec(str(statement), act)


def pool_of(R):
    """The calibration pool of ``R`` as the stage draws it (its established K1 facts controlled)."""
    controlled = frozenset((event, attribute) for event in R.events for attribute in asking._K1_ATTRIBUTES
                           if F.fact(R, event, attribute).result is ct.Result.SUPPORTED) | R.controlled
    return asking.calibration_pool(replace(R, controlled=controlled))


# --- the records, as settle_questions writes them ----------------------------------------------------------------------


def settled(R, asked, *, health='answered', round_=1, batch=1, located=True):
    """The records settle_questions writes for ONE request asking ``asked`` [(spec, (claim, control))] beside one
    calibration item answered right - ``health`` 'breach': the item answered wrong (H2 refuses the request);
    'uncalibrated': no item (H5); 'failed' or 'too_long': no answer, that outcome - every supported claim's proof
    located unless ``located`` is False (the lane's test_r3f_pairs.settled, with these health states added)."""
    pool = pool_of(R)
    items, verdicts, locations = [], {}, {}
    for number, (spec, pattern) in enumerate(asked, start=1):
        claim, control = f'q{number}', f'q{number}n'
        items.append(SimpleNamespace(role='question', spec=spec, claim=claim, control=control, controls=(control,)))
        for key, value in zip((claim, control), pattern):
            if value is not None:
                verdicts[key] = T._verdict(value)
        locations[claim] = (SimpleNamespace(located=True, spans=((100 * number, 100 * number + 20),), reason='')
                            if located else
                            SimpleNamespace(located=False, spans=(), reason=proof.ProofReason.UNLOCATED.value))
    if health != 'uncalibrated':
        items.append(SimpleNamespace(role='calibration', spec=pool[0], claim='c1', control='c1n', controls=('c1n',)))
        verdicts['c1'] = T._verdict(V.CONTRADICTS if health != 'breach' else V.SUPPORTS)
        verdicts['c1n'] = T._verdict(V.SUPPORTS if health != 'breach' else V.CONTRADICTS)
    answered = health not in ('failed', 'too_long')
    read = SimpleNamespace(verdicts=verdicts, missing=(), repeated=()) if answered else None
    found = settle.settle_questions(SimpleNamespace(items=tuple(items), round=round_, batch=batch), read,
                                    locations if answered else {}, R, 'answered' if answered else health)
    return [dict(item) for item in found.questions]


VERDICTS = (V.SUPPORTS, V.CONTRADICTS, V.UNCLEAR, None)
# a pair-family question's states: (claim, control) patterns in an answered request, the release with its proof
# unlocated, the release in a refused request (its calibration item breached, H2, or none drawn, H5) or one with no
# answer (failed, or cut at its output limit); 'absent' asks nothing
STATES = {**{f'{claim and claim.value}/{control and control.value}': ((claim, control), 'answered', True)
             for claim, control in itertools.product(VERDICTS, VERDICTS)},
          'release unlocated': (T.RELEASE, 'answered', False),
          'release refused': (T.RELEASE, 'breach', True),
          'release uncalibrated': (T.RELEASE, 'uncalibrated', True),
          'release failed': (T.RELEASE, 'failed', True),
          'release too long': (T.RELEASE, 'too_long', True)}
RELEASE_STATES = frozenset({f'{V.SUPPORTS.value}/{V.CONTRADICTS.value}', 'release unlocated'})  # read AFFIRMED
STATE_NAMES = ('absent', *STATES)


def record_of(R, spec, state, *, round_=1, batch=1):
    """The records of ``spec`` asked alone in its own request, in ``state`` ([] for 'absent')."""
    if state == 'absent':
        return []
    pattern, health, located = STATES[state]
    return settled(R, [(spec, pattern)], health=health, round_=round_, batch=batch, located=located)


def stored(records):
    """The records as the stage stores them: exclusivity over every round's (studio/jobs.py's call)."""
    return settle.exclusive(records, [])


def changes(state):
    """Every state one verdict change away from ``state`` (claim or control, in an answered request), and its request
    refused or failed (P-MONO-Q's steps)."""
    if state not in STATES or STATES[state][1] != 'answered' or not STATES[state][2]:
        return ()
    (claim, control), _health, _located = STATES[state]
    out = [f'{other and other.value}/{control and control.value}' for other in VERDICTS if other != claim]
    out += [f'{claim and claim.value}/{other and other.value}' for other in VERDICTS if other != control]
    if state in RELEASE_STATES:
        out += ['release refused', 'release uncalibrated', 'release failed', 'release too long']
    return tuple(out)


# --- RP-1: the finding's input (the session row) ----------------------------------------------------------------------


BIDIRECTIONAL_CODES = (('43239', 4), ('45380', 4))


def session_answers(rel):
    """The pair's Q-REL answered ``rel``; E4's session answered X2 (X1 rejected, X2 established); the rest released."""
    def answer(spec):
        if spec.family is FAM.Q_REL:
            return rel
        if spec.attribute is A.SESSION and spec.subjects == ('E4',):
            return T.HOLD if spec.value == 'X1' else T.RELEASE
        return T.RELEASE
    return answer


class RowReleaseClassTests(SimpleTestCase):
    """RP-1 (high), the finding's input: the pair (E3, E4) - or (u:0, E4) - is asked through Q-REL beside E4's session in
    ONE round; Fable says the denial denies the biopsy (or is unclear, or incoherent) AND that the biopsy was taken in the
    colonoscopy. On int6 the session row set the pair apart and 45380 went READY on the pair Fable said the denial
    denies (6 subtests RED there); the pair now keeps its R_base relation."""

    def test_the_round_asks_the_pair_and_the_row_together(self) -> None:
        for build in (bidirectional_denial, bidirectional_unlisted_denial):
            with self.subTest(scene=build.__name__):
                R, events = build()
                families = sorted(spec.family.value for spec in asking.plan(R, (), events).specs)
                self.assertEqual(families, ['Q-FACT', 'Q-FACT', 'Q-REL'])

    def test_a_non_release_rel_answer_holds_the_pair_the_session_row_sets_apart(self) -> None:
        for build in (bidirectional_denial, bidirectional_unlisted_denial):
            for name, rel in NOT_RELEASE:
                with self.subTest(scene=build.__name__, rel=name):
                    R, events = build()
                    records, _plans = T.stage(R, events, session_answers(rel))
                    R_q = F._answered(R, {**events, 'questions': records})
                    self.assertNotEqual(_status(R_q, BIDIRECTIONAL_CODES)['45380'], 'ready')

    def test_the_consistent_answers_still_release(self) -> None:
        for build in (bidirectional_denial, bidirectional_unlisted_denial):
            with self.subTest(scene=build.__name__):
                R, events = build()
                records, _plans = T.stage(R, events, session_answers(T.RELEASE))
                R_q = F._answered(R, {**events, 'questions': records})
                self.assertEqual(_status(R_q, BIDIRECTIONAL_CODES)['45380'], 'ready')


# --- the class end to end through the stage ----------------------------------------------------------------------------


def rel_answers(rel, **by_pair):
    """Every Q-REL answered ``rel`` (or as ``by_pair`` names its subjects, joined by '_'); E4's (and E7's) session X1
    rejected; every other question in the release direction."""
    def answer(spec):
        named = by_pair.get('_'.join(spec.subjects))
        if named is not None:
            return named
        if spec.family is FAM.Q_REL:
            return rel
        if spec.attribute is A.SESSION and spec.value == 'X1':
            return T.HOLD
        return T.RELEASE
    return answer


def breach_rel(round_, questions):
    return 'breach' if any(spec.family is FAM.Q_REL for spec in questions) else 'answered'


def fail_rel(round_, questions):
    return 'failed' if any(spec.family is FAM.Q_REL for spec in questions) else 'answered'


STAGE_ROWS = {  # the rows the planner asks beside the pair's Q-REL: (scene, codes, the hold the pair keeps)
    'session': (bidirectional_denial, BIDIRECTIONAL_CODES, ('procedure', 'relation:unresolved', 'E4')),
    'kept entry session': (bidirectional_unlisted_denial, BIDIRECTIONAL_CODES, ('performed_status', 'unlisted', 'E4')),
    'performer': (performer_scene, (('45380', 4),), ('event_performer', 'relation:unresolved', 'E4')),
    'timing': (timing_scene, (('45380', 4),), ('event_time', 'relation:unresolved', 'E4')),
}


def two_pair_scene():
    """RP-1's visit with a SECOND pair of another statement and another act: E6 an established denial of a snare
    removal in the EGD; E7 a snare removal of L1 (a polyp named in the colon) whose session is doubted (X1 | X2). The
    biopsy E4 is placed in the cecum (with a polyp named, a biopsy naming no place has no target: act_target)."""
    doc = egd_and_colonoscopy()
    doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), session=X(1))
    doc.act(4, Kind.BIOPSY, session=EF.doubted(X(1), X(2)), places=[sup(Landmark.CECUM)])
    doc.act(6, Kind.SNARE, status=EF.neg(ct.Status.PERFORMED), session=X(1))
    doc.act(7, Kind.SNARE, session=EF.doubted(X(1), X(2)), lesion=sup(L(1)), places=[sup(Landmark.SIGMOID_COLON)],
            device=sup(ct.Device.COLD_SNARE))
    return TA.dated(TP.paired(doc.build())), {}


def flex_sig_scene():
    """The refuter's p03 scene (a): the lane's tattoo scene (pairs' base_doc: E3 an established denial of an injection
    for L1, E4 a tattoo of L1's place naming no lesion, its performer the team) beside a flexible sigmoidoscopy X2 (E5),
    the tattoo's session doubted (X1 | X2)."""
    doc = T.base_doc(e4_performer=sup(EF.TEAM))
    doc.session(2, ct.SessionKind.FLEX_SIG, reached=[sup(ct.Extent.SIGMOID_COLON)])
    doc.exam(5, session=X(2))
    doc.events[E(4)] = {**doc.events[E(4)], A.SESSION: (EF.doubted(X(1), X(2)),)}
    return T.finish(doc)


class VariantTests(SimpleTestCase):
    """The class end to end through the stage (the REAL planner, partition, settle_questions, exclusivity as jobs.py
    calls it, the fold and assess), beyond the finding's input."""

    def walk(self, build, codes, answer, **kwargs):
        R, events = build()
        records, plans = T.stage(R, events, answer, **kwargs)
        R_q = F._answered(R, {**events, 'questions': records})
        return _held(R_q, codes), records, plans, R_q

    def test_each_row_the_planner_asks_beside_the_pair(self) -> None:
        """Session, a kept entry's session, performer and timing: the pair's Q-REL answered holding, unclear,
        incoherent, missing or both supported beside the row's releasing answer - the pair keeps its R_base relation,
        its code is held with that relation's existing hold, and round 2 asks nothing."""
        for row, (build, codes, hold) in STAGE_ROWS.items():
            code = codes[-1][0]
            for name, rel in EVERY_NOT_RELEASE:
                with self.subTest(row=row, rel=name):
                    found, records, plans, R_q = self.walk(build, codes, rel_answers(rel))
                    self.assertEqual(found[code][0], 'needs_clarification')
                    self.assertIn(hold, found[code][1])
                    self.assertEqual(T.families(plans)[1:], [[]])
                    self.assertTrue(F.kept_pairs(R_q) or F.kept_unlisted(R_q))
            with self.subTest(row=row, rel='release'):
                found, records, plans, R_q = self.walk(build, codes, rel_answers(T.RELEASE))
                self.assertEqual(found[code], ('ready', []))
                self.assertEqual((F.kept_pairs(R_q), F.kept_unlisted(R_q)), (frozenset(), frozenset()))

    def test_the_rel_in_a_refused_or_failed_request_beside_a_healthy_row_answer(self) -> None:
        """Each question in a request of its own (bound 4): the Q-REL answered in the release direction but its request
        refused (its calibration item breached) or failed, the row's answers established in healthy requests of the
        same round - the release is not AFFIRMED in a healthy request, so the pair holds."""
        for row, (build, codes, hold) in STAGE_ROWS.items():
            code = codes[-1][0]
            for name, health in (('refused', breach_rel), ('failed', fail_rel)):
                with self.subTest(row=row, request=name):
                    found, records, plans, _R_q = self.walk(build, codes, rel_answers(T.RELEASE), bound=4,
                                                           health=health)
                    self.assertGreaterEqual(len({item['batch'] for item in records}), 2)
                    self.assertEqual(found[code][0], 'needs_clarification')
                    self.assertIn(hold, found[code][1])

    def test_the_same_pair_in_separate_healthy_requests_of_one_round(self) -> None:
        """The contradiction across independent responses of ONE round (bound 4: the Q-REL and each session question in
        a healthy request of its own - three requests), not inside one response."""
        for build in (bidirectional_denial, bidirectional_unlisted_denial):
            for name, rel in NOT_RELEASE:
                with self.subTest(scene=build.__name__, rel=name):
                    found, records, plans, _R_q = self.walk(build, BIDIRECTIONAL_CODES, rel_answers(rel), bound=4)
                    self.assertEqual(len({(item['round'], item['batch']) for item in records}), 3)
                    self.assertEqual({item['round'] for item in records}, {1})
                    self.assertEqual(found['45380'][0], 'needs_clarification')
            with self.subTest(scene=build.__name__, rel='release'):
                found, _records, _plans, _R_q = self.walk(build, BIDIRECTIONAL_CODES, rel_answers(T.RELEASE), bound=4)
                self.assertEqual(found['45380'], ('ready', []))

    def test_the_reverse_order_across_rounds(self) -> None:
        """The pair's Q-REL in round 1 and the row's answer in round 2, and the reverse - in either stored order: the
        fold reads every record of every round, so the pair holds the same way."""
        for row, (build, spec, statement, code) in ROWS.items():
            R, _events = build()
            for name, rel in NOT_RELEASE:
                with self.subTest(row=row, rel=name):
                    seen = set()
                    for rel_round, row_round in ((1, 2), (2, 1)):
                        rel_records = settled(R, [(rel_spec(statement, 'E4'), rel)], round_=rel_round)
                        row_records = settled(R, [(spec, T.RELEASE)], round_=row_round)
                        for records in (rel_records + row_records, row_records + rel_records):
                            R_q = F._answered(R, {'questions': stored(records)})
                            seen.add((_status(R_q, ((code, 4),))[code], F.kept_pairs(R_q), F.kept_unlisted(R_q)))
                    self.assertEqual(len(seen), 1, seen)
                    status, kept, kept_entries = seen.pop()
                    self.assertEqual(status, 'needs_clarification')
                    if isinstance(statement, int):
                        self.assertEqual((kept, kept_entries), (frozenset(), frozenset({(statement, E(4))})))
                    else:
                        self.assertEqual((kept, kept_entries), (frozenset({(statement, E(4))}), frozenset()))

    def test_a_kept_unlisted_entry(self) -> None:
        """RP-1's unlisted variant (the refuter's p07): the entry's pair keeps its R_base pairing - performed_status at
        RANK row 2, cause unlisted - under every answer that is not the release, and is dropped by the consistent one."""
        R, events = bidirectional_unlisted_denial()
        for name, rel in EVERY_NOT_RELEASE:
            with self.subTest(rel=name):
                found, _records, _plans, R_q = self.walk(bidirectional_unlisted_denial, BIDIRECTIONAL_CODES,
                                                        rel_answers(rel))
                self.assertEqual(unlisted_of(R_q, E(4)), (0,))
                self.assertEqual(F.kept_unlisted(R_q), frozenset({(0, E(4))}))
                self.assertIn(('performed_status', 'unlisted', 'E4'), found['45380'][1])
        found, _records, _plans, R_q = self.walk(bidirectional_unlisted_denial, BIDIRECTIONAL_CODES,
                                                rel_answers(T.RELEASE))
        self.assertEqual((unlisted_of(R_q, E(4)), found['45380']), ((), ('ready', [])))
        self.assertEqual(unlisted_of(R, E(4)), (0,))

    def test_the_flexible_sigmoidoscopy_scene(self) -> None:
        """The refuter's p03 scene (a): 45335 (a flexible sigmoidoscopy with a tattoo) was READY on int6 beside the
        pair's holding, unclear or incoherent Q-REL; held now, READY under the consistent release."""
        codes = (('45381', 4), ('45335', 4))
        for name, rel in NOT_RELEASE:
            with self.subTest(rel=name):
                found, _records, _plans, R_q = self.walk(flex_sig_scene, codes, rel_answers(rel))
                self.assertEqual(found['45335'][0], 'needs_clarification')
                self.assertEqual(relation_of(R_q, E(3), E(4)), 'unresolved')
        found, _records, _plans, R_q = self.walk(flex_sig_scene, codes, rel_answers(T.RELEASE))
        self.assertEqual((found['45335'], relation_of(R_q, E(3), E(4))), (('ready', []), 'independent'))

    def test_a_different_pair_stays_independent(self) -> None:
        """Two pairs of the visit, of two statements and two acts, each released by its own act's session answer and
        each asked through its own Q-REL (records as settle_questions writes them, each in its own request, stored
        through exclusivity): (E3, E4)'s answer that is not the release holds its own pair only - (E6, E7) stays
        INDEPENDENT and 45385 READY while 45380 is held - and the reverse; with no Q-REL asked of the other pair, or its
        Q-REL the release, alike."""
        R, _events = two_pair_scene()
        codes = (('45380', 4), ('45385', 7))
        answers = (settled(R, [(fact_spec('E4', A.SESSION, 'X2', 'fact.session'), T.RELEASE)], batch=3)
                   + settled(R, [(fact_spec('E7', A.SESSION, 'X2', 'fact.session'), T.RELEASE)], batch=4))
        for held, other in ((E(3), E(6)), (E(6), E(3))):
            act, other_act = E(held.number + 1), E(other.number + 1)
            for name, rel in EVERY_NOT_RELEASE:
                for other_name, other_rel in (('not asked', None), ('release', T.RELEASE)):
                    with self.subTest(held=str(held), rel=name, other=other_name):
                        records = settled(R, [(rel_spec(held, str(act)), rel)], batch=1) + answers
                        if other_rel is not None:
                            records += settled(R, [(rel_spec(other, str(other_act)), other_rel)], batch=2)
                        R_q = F._answered(R, {'questions': stored(records)})
                        found = _held(R_q, codes)
                        self.assertEqual((relation_of(R_q, held, act), relation_of(R_q, other, other_act)),
                                         ('unresolved', 'independent'))
                        self.assertEqual(F.kept_pairs(R_q), frozenset({(held, act)}))
                        self.assertEqual(found[{E(4): '45385', E(7): '45380'}[act]], ('ready', []))
                        self.assertEqual(found[{E(4): '45380', E(7): '45385'}[act]][0], 'needs_clarification')
        R_q = F._answered(R, {'questions': stored(answers)})
        self.assertEqual(_held(R_q, codes), {'45380': ('ready', []), '45385': ('ready', [])})

    def test_no_pair_family_question_asked_releases_as_on_int6(self) -> None:
        """A pair no pair-family question was asked of is contested by nothing: the row's answer alone releases it, as
        on int6 (the census's 'absent' state; the fold leaves R_q a plain FactSet)."""
        for row, (build, spec, statement, code) in ROWS.items():
            with self.subTest(row=row):
                R, _events = build()
                R_q = F._answered(R, {'questions': stored(settled(R, [(spec, T.RELEASE)]))})
                self.assertIs(type(R_q), FactSet)
                self.assertEqual(_status(R_q, ((code, 4),))[code], 'ready')


# --- THE CENSUS: rows x pair-family verdict states, with P-MONO-Q ---------------------------------------------------------


def released(R_q, statement, act):
    """Whether R_q leaves the pair NOT held: an event pair (``statement`` an Id) INDEPENDENT or not paired; a kept
    entry's pair (``statement`` its index) not paired."""
    if isinstance(statement, int):
        return statement not in unlisted_of(R_q, act)
    return relation_of(R_q, statement, act) in ('independent', 'not paired')


class RowCensusTests(SimpleTestCase):
    """D328 (2)'s census extended over rows x pair-family verdict states (DECISIONS D330 (2)), with P-MONO-Q."""

    def test_each_row_by_its_q_fact_answer_x_every_rel_state(self) -> None:
        """Each row a Q-FACT answer releases through (session, performer, timing, target, technique, a kept entry's
        session) x the pair's Q-REL in every state: the pair is released - and its code READY - exactly when the Q-REL
        was not asked or reads AFFIRMED (the release on both members in an answered, healthy request, its proof
        located or not); P-MONO-Q: no single verdict change from the release to anything else releases the pair or
        makes the code READY."""
        for row, (build, spec, statement, code) in ROWS.items():
            R, _events = build()
            self.assertFalse(released(R, statement, E(4)), row)
            answer = settled(R, [(spec, T.RELEASE)], batch=2)
            outcome = {}
            for state in STATE_NAMES:
                with self.subTest(row=row, rel=state):
                    records = record_of(R, rel_spec(statement, 'E4'), state, batch=1) + answer
                    R_q = F._answered(R, {'questions': stored(records)})
                    outcome[state] = (released(R_q, statement, E(4)), _status(R_q, ((code, 4),))[code] == 'ready')
                    expected = state == 'absent' or state in RELEASE_STATES
                    self.assertEqual(outcome[state], (expected, expected))
            for state in STATE_NAMES:
                for other in changes(state):
                    with self.subTest(row=row, mono=f'{state} -> {other}'):
                        if state in RELEASE_STATES and other not in RELEASE_STATES:
                            self.assertTrue(all(after <= before for after, before in zip(outcome[other],
                                                                                         outcome[state])))

    def test_the_pair_beside_a_q_onlesion_of_its_act_and_another_pair(self) -> None:
        """The session row with THREE pair-family records beside the two releasing session answers (E4's and E7's): the
        pair's Q-REL (every state), a Q-ONLESION of its act "E4 was not done to L1" (absent, the release, holding,
        unclear, the release refused) - asked, without a FactSet, of every event statement of E4 (DECISIONS D330 (3)) -
        and ANOTHER pair's Q-REL (E6, E7) (absent, the release, holding, the release failed). (E3, E4) is released
        exactly when its Q-REL and the Q-ONLESION are each absent or AFFIRMED; (E6, E7) exactly when its own Q-REL is -
        whatever the other two say; P-MONO-Q over every single verdict change of every record."""
        R, _events = two_pair_scene()
        onlesion_states = ('absent', f'{V.SUPPORTS.value}/{V.CONTRADICTS.value}',
                           f'{V.CONTRADICTS.value}/{V.SUPPORTS.value}', f'{V.UNCLEAR.value}/{V.UNCLEAR.value}',
                           'release refused')
        other_states = ('absent', f'{V.SUPPORTS.value}/{V.CONTRADICTS.value}', f'{V.CONTRADICTS.value}/{V.SUPPORTS.value}',
                        'release failed')
        specs = (rel_spec(E(3), 'E4'), T.onlesion_spec('E4', 'L1'), rel_spec(E(6), 'E7'))
        answers = (settled(R, [(fact_spec('E4', A.SESSION, 'X2', 'fact.session'), T.RELEASE)], batch=4)
                   + settled(R, [(fact_spec('E7', A.SESSION, 'X2', 'fact.session'), T.RELEASE)], batch=5))
        cache = {}

        def record(index, state):
            if (index, state) not in cache:
                cache[(index, state)] = record_of(R, specs[index], state, batch=index + 1)
            return cache[(index, state)]

        def outcome(states):
            records = [item for index, state in enumerate(states) for item in record(index, state)] + answers
            R_q = F._answered(R, {'questions': stored(records)})
            return (released(R_q, E(3), E(4)), released(R_q, E(6), E(7)))

        def agrees(state):
            return state == 'absent' or state in RELEASE_STATES

        found = {}
        for states in itertools.product(STATE_NAMES, onlesion_states, other_states):
            with self.subTest(states=states):
                found[states] = outcome(states)
                self.assertEqual(found[states], (agrees(states[0]) and agrees(states[1]), agrees(states[2])))
        steps = 0
        for states, result in found.items():
            for index, state in enumerate(states):
                for other in changes(state):
                    changed = states[:index] + (other,) + states[index + 1:]
                    if changed not in found or not agrees(state) or agrees(other):
                        continue
                    steps += 1
                    with self.subTest(mono=f'{states} -> {changed}'):
                        self.assertTrue(all(after <= before for after, before in zip(found[changed], result)))
        self.assertGreater(steps, 100)

    def test_the_rule_over_every_row_and_every_drop(self) -> None:
        """The rule itself (facts._kept) over EVERY row of 4.5 - the breadth row too, which no answer the fold folds can
        reach today (it never folds a statement's scope facts) - the drop out of "which pairs" (a possible statement's
        status), and each drop of a kept entry's pair (the act's session, kind and status): R_q released by the row's
        facts as an answer would leave them, the pair's Q-REL in every state - kept at R_base's relation exactly when the
        Q-REL is asked and not AFFIRMED; with nothing released, nothing is kept."""
        for name, (base, R, statement) in rule_scenes().items():
            self.assertFalse(released(base, statement, E(4)), name)
            self.assertTrue(released(R, statement, E(4)), name)
            self.assertTrue(asking.eligible(rel_spec(statement, 'E4'), base), name)
            for state in STATE_NAMES:
                with self.subTest(scene=name, rel=state):
                    events = {'questions': stored(record_of(base, rel_spec(statement, 'E4'), state))}
                    kept = F._kept(base, R, events)
                    expected = not (state == 'absent' or state in RELEASE_STATES)
                    self.assertEqual(not released(kept, statement, E(4)), expected)
                    pins = F.kept_unlisted(kept) if isinstance(statement, int) else F.kept_pairs(kept)
                    self.assertEqual(bool(pins), expected)
                    if expected and not isinstance(statement, int):
                        self.assertEqual(pairing.relation(kept, statement, E(4)), pairing.relation(base, statement, E(4)))
                    self.assertIs(F._kept(base, replace(base, base=base), events).__class__, FactSet)


def _with(R, subject, **facts_):
    """``R`` with ``subject``'s facts replaced (short names: evaluate_fixtures.NAMES), R_base as its base."""
    objects = R.events if subject in R.events else R.lesions
    changed = {**objects[subject], **EF.facts_of(**facts_)}
    key = 'events' if subject in R.events else 'lesions'
    return replace(R, **{key: {**objects, subject: changed}}, base=R)


def rule_scenes():
    """(R_base, R released by the facts an answer would leave, the pair's statement) for every row of 4.5, the
    which-pairs drop and each kept-entry drop (``RowCensusTests.test_the_rule_over_every_row_and_every_drop``)."""
    out = {}
    R, _ = bidirectional_denial()
    out['session'] = (R, _with(R, E(4), session=sup(X(2))), E(3))
    R, _ = timing_scene()
    out['timing'] = (R, _with(R, E(4), date=sup(EF.ON)), E(3))
    R, _ = performer_scene()
    out['performer'] = (R, _with(R, E(4), performer=sup(EF.TEAM)), E(3))
    doc = EF.colonoscopy(snare=False)
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.EXCEPTIVE),
            excepts=[EF.unres(E(4), reason=ct.Reason.APPRAISAL_MISSING)])
    doc.act(4, Kind.BIOPSY)
    R = TA.dated(TP.paired(doc.build()))
    out['breadth'] = (R, _with(R, E(3), excepts=[sup(E(4))]), E(3))
    R, _ = target_scene()
    out['target'] = (R, _with(R, E(4), places=[sup(Landmark.DESCENDING_COLON)]), E(3))
    R, _ = technique_scene()
    out['technique'] = (R, _with(R, E(4), device=sup(ct.Device.COLD_SNARE)), E(3))
    doc = EF.colonoscopy(snare=False)
    doc.act(3, Kind.BIOPSY, status=EF.doubted(ct.Status.PERFORMED, ct.Status.PLANNED))
    doc.act(4, Kind.BIOPSY)
    R = TA.dated(TP.paired(doc.build()))
    out['which pairs (a possible statement performed)'] = (R, _with(R, E(3), status=sup(ct.Status.PERFORMED)), E(3))
    R, _ = bidirectional_unlisted_denial()
    out['kept entry: session'] = (R, _with(R, E(4), session=sup(X(2))), 0)
    for name, over, to in (('kind', dict(kind=EF.doubted(Kind.BIOPSY, Kind.INJECTION)), dict(kind=sup(Kind.INJECTION))),
                           ('status', dict(status=EF.doubted(ct.Status.PERFORMED, ct.Status.PLANNED)),
                            dict(status=sup(ct.Status.PLANNED)))):
        doc = egd_and_colonoscopy()
        doc.act(4, over.pop('kind', Kind.BIOPSY), session=X(2), **over)
        doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.DENIAL, Kind.BIOPSY, None, EF.unit(9)))
        R = TA.dated(TP.paired(doc.build()))
        out[f'kept entry: {name}'] = (R, _with(R, E(4), **to), 0)
    return out


# --- the one record reader -------------------------------------------------------------------------------------------------


def int6_reading(record):
    """int6's contract/settle._reading, as it stood (the oracle the one reader must equal on every record settle writes):
    REJECTED - claim contradicts, control supports, held_by_answer, reasons exactly [question_contradicts] or
    [question_not_eligible]; AFFIRMED - claim supports, control contradicts, and no reason, question_conflict or one
    ProofReason; OTHER - anything else."""
    verdicts = record.get('verdicts')
    if not isinstance(verdicts, dict):
        return 'other'
    claim, control = verdicts.get('claim'), verdicts.get('control')
    reasons = list(record.get('reasons') or ())
    if (claim == 'contradicts' and control == 'supports' and record.get('held_by_answer') is True
            and reasons in (['question_contradicts'], ['question_not_eligible'])):
        return 'rejected'
    proof_reasons = {'proof_missing', 'proof_short', 'proof_unlocated', 'quotes_bound'}
    supported = not reasons or (len(reasons) == 1 and (reasons[0] == 'question_conflict' or reasons[0] in proof_reasons))
    if claim == 'supports' and control == 'contradicts' and supported:
        return 'affirmed'
    return 'other'


class ReadingPinTests(SimpleTestCase):
    """ONE record reader (engine/facts.answer_reading; contract/settle._reading reads it), equal to int6's settle reading
    on every record shape settle writes, its vocabulary pinned to settle's and contract/proof's."""

    def test_the_vocabulary_is_settles_and_proofs(self) -> None:
        self.assertEqual({member.value for member in F.StoredReason},
                         {settle.QUESTION_CONFLICT, settle.QUESTION_CONTRADICTS, settle.QUESTION_NOT_ELIGIBLE}
                         | {reason.value for reason in proof.ProofReason})
        self.assertIs(settle.Reading, F.AnswerReading)

    def test_the_one_reader_equals_int6s_on_every_record(self) -> None:
        claims = ('supports', 'contradicts', 'unclear', 'qualified', None, 'other')
        reasons = [None, [], *[[member.value] for member in F.StoredReason],
                   *[[reason] for reason in ('question_unclear', 'question_missing', 'question_incoherent',
                                             'question_control_missing', 'question_detached',
                                             'question_qualified:hedged', 'question_health:calibration',
                                             'question_health:uncalibrated', 'question_request_failed:failed',
                                             'question_request_failed:too_long')],
                   ['question_conflict', 'proof_unlocated'], ['question_contradicts', 'question_conflict'],
                   ('question_conflict',), ('proof_short',), 'question_conflict', 'proof_missing', '']
        count = 0
        for claim, control, reason, held in itertools.product(claims, claims, reasons, (True, False, None)):
            record = {'verdicts': {'claim': claim, 'control': control}, 'reasons': reason, 'held_by_answer': held}
            with self.subTest(record=record):
                self.assertEqual(F.answer_reading(record).value, int6_reading(record))
                self.assertIs(settle._reading(record), F.answer_reading(record))
                count += 1
        for record in ({}, {'verdicts': None}, {'verdicts': {'claim': 'supports', 'control': 'contradicts'}},
                       {'verdicts': ['supports', 'contradicts'], 'reasons': []}):
            self.assertEqual(F.answer_reading(record).value, int6_reading(record))
        # a reasons value that is no list is read as no reading at all (fail-closed): never laxer than int6's
        for odd in ({'question_conflict': 1}, 5):
            record = {'verdicts': {'claim': 'supports', 'control': 'contradicts'}, 'reasons': odd}
            self.assertIs(F.answer_reading(record), F.AnswerReading.OTHER)
        self.assertGreater(count, 2000)


# --- the scopes: settle's, without a FactSet ------------------------------------------------------------------------------


def scope_scene():
    """Events E3..E7 (two denials and three acts), lesions L1 and L2, one kept unlisted entry (u:0)."""
    doc = egd_and_colonoscopy()
    doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
    doc.lesion(2, lesion_places=[sup(Landmark.CECUM)], multiplicity=sup(ct.Multiplicity.SINGLE))
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), session=X(1))
    doc.act(4, Kind.BIOPSY, session=EF.doubted(X(1), X(2)))
    doc.act(6, Kind.SNARE, status=EF.neg(ct.Status.PERFORMED), session=X(1))
    doc.act(7, Kind.SNARE, session=X(2), lesion=sup(L(1)))
    doc.unlisted.append(EF.unlisted(ct.UnlistedWhat.DENIAL, Kind.BIOPSY, X(1), EF.unit(9)))
    return TA.dated(TP.paired(doc.build()))


class ScopePinTests(SimpleTestCase):
    """The fold reads which pairs a pair-family record is asked of exactly as contract/settle.pair_scopes reads it
    WITHOUT a FactSet (production's exclusivity, DECISIONS D330 (3)), on every record settle_questions writes: a Q-REL
    its two subjects (a kept entry by its index), a Q-ONLESION every event statement of its act, a Q-LESION every event
    pair; and fail-closed on a record settle never writes (subjects that are not two names: every pair)."""

    def candidates(self, R):
        statements = [*R.events, *range(len(R.unlisted))]
        return [(statement, act) for statement in statements for act in R.events if statement != act]

    def settles(self, record, statement, act):
        name = f'{asking.UNLISTED_PREFIX}{statement}' if isinstance(statement, int) else str(statement)
        return settle._about_one_pair(settle.pair_scopes(record),
                                      frozenset({settle.PairScope(name, str(act))}))

    def folds(self, R, record, statement, act):
        family = F._member(F.QuestionFamily, record.get('family'))
        contest = F._contest_of(record, family, R)
        return contest is not None and F._contested([contest], statement, act)

    def test_every_record_settle_writes(self) -> None:
        R = scope_scene()
        records = [
            {'family': 'Q-REL', 'form': 'rel.deny', 'subjects': ['E3', 'E4'], 'unlisted': None},
            {'family': 'Q-REL', 'form': 'rel.deny', 'subjects': ['E6', 'E7'], 'unlisted': None},
            {'family': 'Q-REL', 'form': 'rel', 'subjects': ['u:0', 'E4'], 'unlisted': 0},
            {'family': 'Q-ONLESION', 'form': 'onlesion', 'subjects': ['E4', 'L1'], 'unlisted': None},
            {'family': 'Q-ONLESION', 'form': 'onlesion', 'subjects': ['E7', 'L2'], 'unlisted': None},
            {'family': 'Q-LESION', 'form': 'lesion.distinct_from', 'subjects': ['L1', 'L2'], 'unlisted': None},
        ]
        checked = 0
        for record in records:
            for statement, act in self.candidates(R):
                with self.subTest(record=record['subjects'], pair=(statement, act)):
                    self.assertEqual(self.folds(R, record, statement, act), self.settles(record, statement, act))
                    checked += 1
        self.assertGreater(checked, 100)

    def test_a_record_settle_never_writes_is_about_every_pair(self) -> None:
        R = scope_scene()
        for subjects in (['E3'], ['E3', 'E4', 'E5'], [3, 4], None):
            for family in ('Q-REL', 'Q-ONLESION', 'Q-LESION'):
                record = {'family': family, 'subjects': subjects, 'unlisted': None}
                for statement, act in self.candidates(R):
                    with self.subTest(record=(family, subjects), pair=(statement, act)):
                        self.assertTrue(self.folds(R, record, statement, act))
                        if self.settles(record, statement, act):  # never laxer than settle
                            self.assertTrue(self.folds(R, record, statement, act))

    def test_other_families_contest_nothing(self) -> None:
        R = scope_scene()
        for family in ('Q-FACT', 'Q-ABSORB', 'Q-GROUP', 'Q-KIND', 'no family'):
            record = {'family': family, 'subjects': ['E3', 'E4'], 'verdicts': {'claim': 'unclear', 'control': None},
                      'reasons': ['question_unclear']}
            self.assertEqual(F._contests([record], R), ())


# --- plan-time refusals: none stands beside an answer --------------------------------------------------------------------


class PlanTimeRefusalTests(SimpleTestCase):
    """The stored records are the fold's whole input: a question refused at PLAN time (asking.UncalibratedRequest) leaves
    no record, and none stands beside an answer, because the stage draws its pool once (studio/jobs.py) and no question's
    key is ever a calibration item's - so every request of a stage gets its item or none does."""

    def test_no_question_key_is_a_calibration_key(self) -> None:
        self.assertFalse({kind.value for kind in asking.CalibrationKind} & {family.value for family in FAM})
        for build in (bidirectional_denial, two_pair_scene, performer_scene, timing_scene):
            R, events = build()
            pool = pool_of(R)
            keys = {spec.key for spec in asking.plan(R, (), events).specs}
            self.assertTrue(pool)
            self.assertFalse({item.key for item in pool} & keys)

    def test_every_request_gets_its_item_or_none_does(self) -> None:
        R, events = two_pair_scene()
        specs = list(asking.plan(R, (), events).specs)
        many = [*specs, *[replace(spec, census=f'{spec.census}+{n}') for n in range(3) for spec in specs]]
        pool = pool_of(R)
        pools = {'full': pool, 'one': pool[:1], 'empty': (),
                 'covers only': tuple(item for item in pool if asking._needs_k1(item))}
        for (name, given), bound, chosen in itertools.product(pools.items(), (4, 6, asking.QUESTION_BOUND),
                                                             (specs, many)):
            with self.subTest(pool=name, bound=bound, questions=len(chosen)):
                try:
                    requests = asking.partition(chosen, given, 1, bound)
                except asking.UncalibratedRequest as exc:
                    self.assertEqual(exc.requests, ())
                    self.assertEqual(sum(len(chunk) for chunk in exc.refused), len(chosen))
                    continue
                self.assertTrue(all(request.calibrated for request in requests))
                for request in requests:
                    try:
                        halves = asking.split(request, given, 1)
                    except asking.UncalibratedRequest as exc:
                        self.assertEqual(exc.requests, ())
                        continue
                    self.assertTrue(all(half.calibrated for half in halves))


# --- the kept pairs: R_q's only change ---------------------------------------------------------------------------------


class AnsweredFactSetTests(SimpleTestCase):
    """The fold keeps a contested pair's R_base relation and changes nothing else; dataclasses.replace keeps the kept
    pairs; engine/pairing reads them in paired, relation, pairs_of, pairs and unlisted_pairs."""

    def finding(self, rel=T.HOLD):
        R, _events = bidirectional_denial()
        answers = settled(R, [(fact_spec('E4', A.SESSION, 'X2', 'fact.session'), T.RELEASE)], batch=2)
        records = settled(R, [(rel_spec(E(3), 'E4'), rel)], batch=1) + answers
        return R, F._answered(R, {'questions': stored(records)}), F._answered(R, {'questions': stored(answers)})

    def test_only_the_pairs_relation_is_kept(self) -> None:
        R, R_q, raw = self.finding()
        self.assertIs(type(R_q), F.AnsweredFactSet)
        self.assertIs(type(raw), FactSet)
        for item in fields(FactSet):
            with self.subTest(field=item.name):
                self.assertEqual(getattr(R_q, item.name), getattr(raw, item.name))
        self.assertIs(R_q.base, R)
        self.assertEqual((F.kept_pairs(R_q), F.kept_unlisted(R_q)), (frozenset({(E(3), E(4))}), frozenset()))
        self.assertEqual(F.fact(R_q, E(4), A.SESSION).value, X(2))  # the answer stands for every other reader
        self.assertEqual(pairing.relation(R_q, E(3), E(4)), pairing.relation(R, E(3), E(4)))
        self.assertEqual(pairing.relation(raw, E(3), E(4)).relation, pairing.Relation.INDEPENDENT)

    def test_pairing_reads_the_kept_pairs(self) -> None:
        R, R_q, _raw = self.finding()
        self.assertTrue(pairing.paired(R_q, E(3), E(4)))
        self.assertEqual(pairing.pairs_of(R_q, E(4)), pairing.pairs_of(R, E(4)))
        self.assertEqual(pairing.pairs(R_q), pairing.pairs(R))
        derived = replace(R_q, controlled=R_q.controlled | {(E(4), A.SESSION)})
        self.assertIs(type(derived), F.AnsweredFactSet)
        self.assertEqual(F.kept_pairs(derived), F.kept_pairs(R_q))
        self.assertEqual(pairing.relation(derived, E(3), E(4)), pairing.relation(R, E(3), E(4)))
        self.assertEqual(F.kept_pairs(R), frozenset())

    def test_a_kept_entry_reads_as_on_r_base(self) -> None:
        R, _events = bidirectional_unlisted_denial()
        records = (settled(R, [(rel_spec(0, 'E4'), T.UNCLEAR)], batch=1)
                   + settled(R, [(fact_spec('E4', A.SESSION, 'X2', 'fact.session'), T.RELEASE)], batch=2))
        R_q = F._answered(R, {'questions': stored(records)})
        self.assertEqual(pairing.unlisted_pairs(R_q, E(4)), pairing.unlisted_pairs(R, E(4)))
        self.assertEqual(F.kept_unlisted(R_q), frozenset({(0, E(4))}))
        self.assertEqual(pairing.unlisted_pairs(R_q, E(1)), pairing.unlisted_pairs(R, E(1)))

    def test_no_answer_or_nothing_contested_is_as_on_int6(self) -> None:
        R, _R_q, raw = self.finding()
        self.assertIs(F._answered(R, {}), R)
        self.assertIs(F._answered(R, {'questions': []}), R)
        _R, released_q, _raw = self.finding(T.RELEASE)
        self.assertIs(type(released_q), FactSet)
        # contested, but nothing released (no row answer): nothing kept
        R, _events = bidirectional_denial()
        R_q = F._answered(R, {'questions': stored(settled(R, [(rel_spec(E(3), 'E4'), T.HOLD)]))})
        self.assertIs(R_q, R)

    def test_idempotent_and_order_free(self) -> None:
        R, _events = two_pair_scene()
        records = (settled(R, [(rel_spec(E(3), 'E4'), T.HOLD)], batch=1)
                   + settled(R, [(rel_spec(E(6), 'E7'), T.UNCLEAR)], batch=2)
                   + settled(R, [(fact_spec('E4', A.SESSION, 'X2', 'fact.session'), T.RELEASE)], batch=3)
                   + settled(R, [(fact_spec('E7', A.SESSION, 'X2', 'fact.session'), T.RELEASE)], batch=4))
        seen = set()
        for order in itertools.permutations(stored(records)):
            R_q = F._answered(R, {'questions': list(order)})
            seen.add((F.kept_pairs(R_q), F.kept_unlisted(R_q)))
        self.assertEqual(seen, {(frozenset({(E(3), E(4)), (E(6), E(7))}), frozenset())})
