"""Round r3's build continued (DECISIONS D324), lane "claims" - the repair round's own tests. Every input SYNTHETIC
(invented reports, ids, spans and words; a fictional clinician): no document of the development set is read and nothing
is sent anywhere (the pipeline classes script the production connector's exchanges).

D324 (2) - EXCLUSIVITY READS EVERY PROPOSITION OF A SLOT (finding L4-1, high; lane item ASK2-3 its hold side):
- ExclusivityL41Tests: L4-1's own input at the settle level - a session doubted X1|X2 asked at X1 in one request and at
  X2 in another, X1 answered WRONG but consistently, X2 answered right; every routine weakening of the right answer (its
  proof unlocated, its control unclear, its claim unclear, qualified or missing, its request breached, failed, cut,
  uncalibrated or unhealthy) left X1 established alone on int4. Now each holds the slot (question_conflict).
- ExclusivityVariantTests: the class beyond the finding's own form - a negation (G1's fact.session.not) beside a value,
  the purpose slot (fact.lift.not beside a purpose value - L2-2's answer pattern), the visit's basis (two values, one
  qualified), across ROUNDS, a plan-time refusal (``refused``); and the boundaries the rule leaves alone - a right
  answer to a doubt (the rival's claim contradicted) still releases, a value beside its own negation contradicted, a
  list attribute's members, a lone proposition, the other families' relations (two Q-ONLESION answers of one act),
  different slots of one act, idempotence.
- Ask23HoldSideTests: ASK2-3's two negations of one slot (not to lift, not for bleeding), both supported, hold each
  other; the act's part link and cause - other slots - are established.
- ExclusivityMonotoneTests (P-MONO-Q / P-SPLIT over exclusivity, f.2 and f.4): every single weakening of every record of
  the L4-1 scene - and of each variant scene - never makes a record 'supported' that was not.
- L41PipelineTests, L41OneRequestTests, L41SilentSessionTests, L41CensusTests: the verifier's own reproduction (attack/
  verify-L4-properties-L4-1, test_verify_l41) through the WHOLE live pipeline (upload ... question ... assess) with the
  assertions of the rule: 45380 (a colonoscopy biopsy code on a gastric biopsy) is never READY, and no single weakening
  of the answer set grows READY over the baseline.

D324 (9) - NO PROOF CLAUSE FORBIDS A PASSAGE THE LOCATOR REQUIRES (lane item RF2-CLM-1, medium):
- ValueFieldTests: the claim line names the frame value passage by its own field ("value at"), exactly the locator's
  value set; a frame claim whose value passage is empty says "no unit"; every other claim's line is int4's format.
- HeadedFrameTests: the refuter's two shapes (a part's heading line opening the act's own card; the heading listed by a
  lesion's card) and the variants (an anatomy entry's card, a two-line heading, the act's own unit as its value, a frame
  calibration item, an empty value passage) - read by the literal reader (test_r3_claims.InstructionReader: the heading
  clause read over EVERY card of the request), every proof the instruction permits locates, some proof is permitted
  wherever one locates, and settle establishes a right answer that follows it; the r3b instruction (its 'rf2' clause
  forms, int4's text byte for byte) permits none there while one locates.
- HeadedLongNoteTests: a headed long note in A-note8's format (parts headed by their own short lines, each heading listed
  by a lesion's card; acts below them inheriting their entry, date and performer): every frame question of every act.
- ActPassageHeadingTests: a heading never serves as the quote for an act's own passage - the locator's cut, and the
  per-object sentence load-bearing (the repaired PROOF without it permits proofs the locator voids)."""
from __future__ import annotations

import dataclasses
import json
from unittest import mock

from django.test import SimpleTestCase

from studio import models
from studio.interpretation import fable_adapter
from studio.interpretation.contract import appraise_read, appraise_schema, jsonschema, proof, settle
from studio.interpretation.contract import question_claims as QC
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking
from studio.providers.base import request_sha256
from tests.support import factories as f
from tests.test_pipeline_api import FakeProvider
from tests.v2 import test_jobs as TJ
from tests.v2 import test_question_stage as TQS
from tests.v2 import test_r3_claims as TRC
from tests.v2 import test_r3_probe as TRP
from tests.v2.test_settle import answer, doubt, event, fact, frame, labelled, lesion, opening, session, src

A = ct.Attribute
FAM = asking.Family
SC, SS = QC.SubjectClass, QC.SubjectStatus
DONE = (SC.ACT, SS.PERFORMED)

# --- D324 (2): exclusivity, at the settle level --------------------------------------------------------------------------

X2_CARD = (('X2', ct.CardType.SESSION, ('S1',)),)  # a second session's card on TRP.TEXT's first unit
WORDS = {'E3': 'A small polyp in the sigmoid colon', 'X1': 'The scope was advanced to the cecum',
         'X2': 'Colonoscopy report. [The heading', 'E1': 'Colonoscopy report. [The heading',
         'E4': 'No biopsies of the rectum were taken'}  # each named object's own words on TRP.TEXT
PARAPHRASE = 'the polyp was taken from the stomach'  # in no passage of TRP.TEXT


def fact_spec(form: str, attribute, value: str, negated: bool = False, subject: str = 'E3', names: tuple = (),
              census: str = 'F3') -> asking.QuestionSpec:
    return TRP.described(asking.QuestionSpec(FAM.Q_FACT, form, (subject,), attribute, value, negated,
                                             names or (subject,), census=census))


def at_session(session_id: str, negated: bool = False, subject: str = 'E3') -> asking.QuestionSpec:
    return fact_spec('fact.session.not' if negated else 'fact.session', A.SESSION, session_id, negated, subject,
                     (subject, session_id), 'G1' if negated else 'F3')


def request(*specs, calibration=(TRP.K1,), seed: str = 'seed') -> QC.QuestionRequest:
    return TRP.stub_request(list(specs), list(calibration), seed=seed, extra_cards=X2_CARD)


def quotes_of(spec) -> list[str]:
    return [WORDS[name] for name in spec.names]


def answered(built: QC.QuestionRequest, answers: dict, breach: bool = False, outcome: str = 'answered',
             missing: tuple = ()) -> list[dict]:
    """The stored question records of ``built`` as settle_questions writes them: ``answers`` maps a spec's key to its
    pattern - 'release' (claim supports with a quote of each named object's own words, control contradicts), 'hold'
    (claim contradicts, control supports), 'unlocated' (the release pattern quoting a paraphrase), 'control_unclear',
    'claim_unclear', 'claim_qualified' - every other question 'hold'; ``breach`` the calibration item's known-false claim
    supported (H2); ``missing`` the spec keys whose claim gets no verdict at all; ``outcome`` a request that did not
    answer."""
    if outcome != 'answered':
        return list(settle.settle_questions(built, None, {}, None, outcome).questions)
    choices = {}
    for item in built.items:
        if item.role == 'calibration':
            if breach:
                choices[(item.spec.key, 'claim')] = ('supports', [])
            continue
        pattern = answers.get(item.spec.key, 'hold')
        release = ('supports', quotes_of(item.spec)), ('contradicts', [])
        claim, control = {
            'release': release, 'hold': (('contradicts', []), ('supports', [])),
            'unlocated': (('supports', [PARAPHRASE]), ('contradicts', [])),
            'control_unclear': (release[0], ('unclear', [])),
            'claim_unclear': (('unclear', []), ('contradicts', [])),
            'claim_qualified': (('qualified', []), ('contradicts', []))}[pattern]
        choices[(item.spec.key, 'claim')] = claim
        choices[(item.spec.key, 'control')] = control
    raw = json.loads(TRP.answer_of(built, choices))
    if missing:
        claims_missing = {item.claim for item in built.items if item.spec.key in missing}
        raw['verdicts'] = [row for row in raw['verdicts'] if row['claim'] not in claims_missing]
    return list(TRP.settled(built, json.dumps(raw)).questions)


def by_value(records: list[dict]) -> dict:
    return {(record['value'], record['negated']): (record['result'], record['reasons']) for record in records}


X1, X2 = at_session('X1'), at_session('X2')
NOT_X1, NOT_X2 = at_session('X1', negated=True), at_session('X2', negated=True)
CONFLICT = ('unresolved', ['question_conflict'])  # settle.QUESTION_CONFLICT (a literal: the module imports on int4)
SUPPORTED = ('supported', [])


class ExclusivityL41Tests(SimpleTestCase):
    """L4-1's own input, at the settle level: E3's session doubted X1|X2, X1 asked in request 1 and answered WRONG but
    consistently (claim supported with E3's and X1's own words, its exact negation contradicted), X2 asked in request 2
    and answered right - then each routine weakening of the right X2 answer or of its request. int4 established X1 alone
    (a false READY); the rule holds the slot in every one."""

    def scene(self, x2: str = 'release', **request_2) -> dict:
        first = answered(request(X1), {X1.key: 'release'})
        second = answered(request(X2), {X2.key: x2}, **request_2)
        return by_value(settle.exclusive(first + second))

    def test_both_values_supported_conflict_as_before(self) -> None:
        self.assertEqual(self.scene(), {('X1', False): CONFLICT, ('X2', False): CONFLICT})

    def test_every_weakening_of_the_right_answer_holds_the_slot(self) -> None:
        weakenings = {
            'proof unlocated': ({'x2': 'unlocated'}, 'proof_unlocated'),
            'control unclear': ({'x2': 'control_unclear'}, 'question_incoherent'),
            'claim unclear': ({'x2': 'claim_unclear'}, 'question_unclear'),
            'claim qualified': ({'x2': 'claim_qualified'}, 'question_qualified:other'),
            'claim missing': ({'missing': (X2.key,)}, 'question_missing'),
            'request breached (H2)': ({'breach': True}, 'question_health:calibration'),
            'request failed': ({'outcome': 'failed'}, 'question_request_failed:failed'),
            'request cut at its output limit': ({'outcome': 'too_long'}, 'question_request_failed:too_long'),
        }
        for name, (kwargs, reason) in weakenings.items():
            with self.subTest(weakening=name):
                found = self.scene(**kwargs)
                self.assertEqual(found[('X1', False)], CONFLICT, name)  # int4: ('supported', []) - the false READY
                self.assertEqual(found[('X2', False)], ('unresolved', [reason]), name)

    def test_a_contradicting_verdict_counts_only_in_a_healthy_request(self) -> None:
        # the RIGHT answer would hold X2 (its claim contradicted) - inside a breached request no verdict of it counts
        healthy = self.scene(x2='hold')
        self.assertEqual(healthy[('X1', False)], SUPPORTED)  # the boundary: a rejected rival leaves the value
        breached = self.scene(x2='hold', breach=True)
        self.assertEqual(breached[('X1', False)], CONFLICT)

    def test_an_uncalibrated_or_unhealthy_request_holds_the_slot(self) -> None:
        first = answered(request(X1), {X1.key: 'release'})
        uncalibrated = answered(request(X2, calibration=()), {X2.key: 'hold'})
        self.assertEqual(uncalibrated[0]['reasons'], ['question_health:uncalibrated'])
        self.assertEqual(by_value(settle.exclusive(first + uncalibrated))[('X1', False)], CONFLICT)
        # H4: four pairs, three controls not rejected - X2 answered "hold" (its claim contradicted) yet unhealthy
        others = [fact_spec('fact.date_relation', A.DATE_RELATION, 'on_date_of_service', subject=subject,
                            census='F1') for subject in ('E1', 'E4')]
        built = request(X2, *others)
        unhealthy = answered(built, {X2.key: 'hold', **{spec.key: 'control_unclear' for spec in others}})
        x2 = next(record for record in unhealthy if record['value'] == 'X2')
        self.assertEqual(x2['reasons'], ['question_health:controls'])
        self.assertEqual(x2['verdicts']['claim'], 'contradicts')
        self.assertEqual(by_value(settle.exclusive(first + [x2]))[('X1', False)], CONFLICT)

    def test_the_held_value_keeps_its_verdicts_and_loses_its_proof(self) -> None:
        first = answered(request(X1), {X1.key: 'release'})
        second = answered(request(X2), {X2.key: 'unlocated'})
        x1 = next(record for record in settle.exclusive(first + second) if record['value'] == 'X1')
        self.assertEqual((x1['result'], x1['reasons'], x1['proof']), ('unresolved', ['question_conflict'], []))
        self.assertEqual(x1['verdicts'], {'claim': 'supports', 'control': 'contradicts'})


class ExclusivityVariantTests(SimpleTestCase):
    """The class rule beyond L4-1's own form (other forms, values, rounds, families and weakenings), and the boundaries
    it leaves alone."""

    def test_a_negation_beside_a_value_g1_and_f2(self) -> None:
        """G1's "not during X1" (true) beside F2's "during X2" (true, its proof unlocated): the negation is not the verdict
        X2's supported claim implies is absent - held (int4: "not X1" established alone; L2-1's shape)."""
        records = answered(request(NOT_X1, X2), {NOT_X1.key: 'release', X2.key: 'unlocated'})
        found = by_value(settle.exclusive(records))
        self.assertEqual(found[('X1', True)], CONFLICT)
        self.assertEqual(found[('X2', False)], ('unresolved', ['proof_unlocated']))

    def test_the_negation_stands_where_every_other_claim_is_contradicted(self) -> None:
        """G1 for two sessions, answered right (E3 is X2's examination): "not X1" supported, "not X2" contradicted - the
        other proposition's claim contradicted, so "not X1" is established (L2-1's kind-doubt variant: only the two G1
        questions asked)."""
        records = answered(request(NOT_X1, NOT_X2), {NOT_X1.key: 'release', NOT_X2.key: 'hold'})
        found = by_value(settle.exclusive(records))
        self.assertEqual(found[('X1', True)], SUPPORTED)
        self.assertEqual(found[('X2', True)], ('unresolved', ['question_contradicts']))

    def test_the_purpose_slot_a_negation_beside_an_unclear_value(self) -> None:
        """L2-2's answer pattern: "not done to lift a lesion" supported (true), "done for hemostasis" unclear - the
        hemostasis reading open, so the negation is held (int4: established alone, 45381 READY)."""
        lift_not = fact_spec('fact.lift.not', A.PURPOSE, 'lift_for_resection', True, census='F11')
        hemostasis = fact_spec('fact.purpose', A.PURPOSE, 'hemostasis')
        lift = fact_spec('fact.purpose', A.PURPOSE, 'lift_for_resection')
        records = answered(request(lift_not, hemostasis, lift),
                           {lift_not.key: 'release', hemostasis.key: 'claim_unclear', lift.key: 'hold'})
        found = by_value(settle.exclusive(records))
        self.assertEqual(found[('lift_for_resection', True)], CONFLICT)
        # boundary: the same negation beside its own value contradicted and the other value contradicted stands
        records = answered(request(lift_not, hemostasis, lift),
                           {lift_not.key: 'release', hemostasis.key: 'hold', lift.key: 'hold'})
        self.assertEqual(by_value(settle.exclusive(records))[('lift_for_resection', True)], SUPPORTED)

    def test_two_values_of_the_visits_basis_one_qualified(self) -> None:
        mdm = fact_spec('fact.visit.basis', A.VISIT_BASIS, 'medical_decision_making', census='C6')
        time_ = fact_spec('fact.visit.basis', A.VISIT_BASIS, 'total_time', census='C6')
        records = answered(request(mdm, time_), {mdm.key: 'release', time_.key: 'claim_qualified'})
        self.assertEqual(by_value(settle.exclusive(records))[('medical_decision_making', False)], CONFLICT)
        records = answered(request(mdm, time_), {mdm.key: 'release', time_.key: 'hold'})
        self.assertEqual(by_value(settle.exclusive(records))[('medical_decision_making', False)], SUPPORTED)

    def test_across_rounds(self) -> None:
        """A proposition asked in round 1 (its claim unclear) blocks a value of the same slot answered in round 2: the
        stage's records of every round are read (studio/jobs._question_state_child keeps them all)."""
        round_1 = answered(request(X2), {X2.key: 'claim_unclear'})
        round_2 = [{**record, 'round': 2, 'id': record['id'].replace('q1.', 'q2.', 1)}
                   for record in answered(request(X1, seed='round-2'), {X1.key: 'release'})]
        found = by_value(settle.exclusive(round_1 + round_2))
        self.assertEqual(found[('X1', False)], CONFLICT)
        once = settle.exclusive(round_1 + round_2)
        self.assertEqual(settle.exclusive(once), once)  # the next round's call reads it the same (idempotent)

    def test_a_plan_time_refusal_holds_its_slot(self) -> None:
        """``refused`` (studio/jobs._refused_questions' entries: a question refused at plan time, never sent, so no
        record): today's entry names its subjects and no attribute - every single-valued slot of the subject is held;
        an entry naming its attribute holds that slot only; another family's entry holds nothing."""
        records = answered(request(X1), {X1.key: 'release'})
        self.assertEqual(by_value(settle.exclusive(records))[('X1', False)], SUPPORTED)
        today = {'round': 1, 'key': X2.key, 'family': 'Q-FACT', 'form': 'fact.session', 'subjects': ['E3'],
                 'census': 'F3', 'reason': asking.UNCALIBRATED}
        self.assertEqual(by_value(settle.exclusive(records, [today]))[('X1', False)], CONFLICT)
        named = {**today, 'attribute': 'session', 'value': 'X2', 'negated': False}
        self.assertEqual(by_value(settle.exclusive(records, [named]))[('X1', False)], CONFLICT)
        other_slot = {**today, 'attribute': 'purpose', 'value': 'hemostasis', 'negated': False}
        self.assertEqual(by_value(settle.exclusive(records, [other_slot]))[('X1', False)], SUPPORTED)
        other_subject = {**today, 'subjects': ['E4']}
        self.assertEqual(by_value(settle.exclusive(records, [other_subject]))[('X1', False)], SUPPORTED)
        rel = {**today, 'family': 'Q-REL', 'subjects': ['E4', 'E3']}
        self.assertEqual(by_value(settle.exclusive(records, [rel]))[('X1', False)], SUPPORTED)

    def test_boundaries_left_alone(self) -> None:
        # a lone proposition
        alone = answered(request(X2), {X2.key: 'release'})
        self.assertEqual(by_value(settle.exclusive(alone))[('X2', False)], SUPPORTED)
        # a right answer to the doubt: the rival's claim contradicted (held_by_answer) - the value is established
        right = answered(request(X1), {X1.key: 'hold'}) + answered(request(X2), {X2.key: 'release'})
        self.assertEqual(by_value(settle.exclusive(right)), {('X1', False): ('unresolved', ['question_contradicts']),
                                                            ('X2', False): SUPPORTED})
        # a value beside its own negation contradicted (G1 "not X2" answered: it IS X2's)
        own = answered(request(NOT_X2, X2), {NOT_X2.key: 'hold', X2.key: 'release'})
        self.assertEqual(by_value(settle.exclusive(own))[('X2', False)], SUPPORTED)
        # a list attribute takes each member (X1's reached points)
        cecum = fact_spec('fact.reached', A.REACHED, 'cecum', subject='X1', census='A3')
        ileum = fact_spec('fact.reached', A.REACHED, 'terminal_ileum', subject='X1', census='A3')
        listed = answered(request(cecum, ileum), {cecum.key: 'release', ileum.key: 'release'})
        self.assertEqual([record['result'] for record in listed], ['supported', 'supported'])
        self.assertEqual(settle.exclusive(listed), listed)
        # different slots of one act are independent (the session and the purpose)
        purpose = fact_spec('fact.purpose', A.PURPOSE, 'removal')
        apart = answered(request(X2, purpose), {X2.key: 'release', purpose.key: 'release'})
        self.assertEqual([record['result'] for record in settle.exclusive(apart)], ['supported', 'supported'])

    def test_the_other_families_are_relations_never_slots(self) -> None:
        """Q-ONLESION answers fold into the act-lesion relation (FactSet.off_lesion, a set: an act may be apart from
        several lesions); Q-REL's into the independent pairs - exclusivity reads neither (two answers of one act, both
        supported, stand)."""
        onlesion = [{'family': 'Q-ONLESION', 'subjects': ['E3', lesion_id], 'attribute': 'target.lesion',
                     'value': lesion_id, 'negated': True, 'result': 'supported', 'reasons': [],
                     'verdicts': {'claim': 'supports', 'control': 'contradicts'}, 'proof': [{'start': 0, 'end': 5}]}
                    for lesion_id in ('L1', 'L2')]
        rel = [{'family': 'Q-REL', 'subjects': [statement, 'E3'], 'attribute': None, 'value': '', 'negated': False,
                'result': 'supported', 'reasons': [], 'verdicts': {'claim': 'supports', 'control': 'contradicts'},
                'proof': [{'start': 0, 'end': 5}]} for statement in ('E1', 'E4')]
        self.assertEqual(settle.exclusive(onlesion + rel), onlesion + rel)


class Ask23HoldSideTests(SimpleTestCase):
    """ASK2-3 (D324 (2): its two-negation case is the rule's HOLD side): an injection beside an EMR of the same lesion,
    answered true as worded for a marking injection - "not part of another act", "not to lift a lesion", "not for
    hemostasis" and "the bleeding not caused by another act" all supported. The two purpose negations are two
    propositions of ONE single-valued slot, neither the verdict the other implies: both held (question_conflict), so the
    act's purpose stays open and its code held for the coder; the part link and the cause - other slots - stand."""

    def test_two_negations_of_one_slot_hold_each_other(self) -> None:
        part = fact_spec('fact.part_link.any', A.PART_OF, '', True, census='F11')
        lift_not = fact_spec('fact.lift.not', A.PURPOSE, 'lift_for_resection', True, census='F11')
        hemostasis_not = fact_spec('fact.hemostasis.not', A.PURPOSE, 'hemostasis', True, census='F12')
        cause_not = fact_spec('fact.cause.not', A.CAUSE, 'act_of_this_session', True, census='F12')
        records = answered(request(part, lift_not, hemostasis_not, cause_not),
                           {spec.key: 'release' for spec in (part, lift_not, hemostasis_not, cause_not)})
        found = {(record['attribute'], record['value']): (record['result'], record['reasons'])
                 for record in settle.exclusive(records)}
        self.assertEqual(found, {('part_of', ''): SUPPORTED, ('cause', 'act_of_this_session'): SUPPORTED,
                                 ('purpose', 'lift_for_resection'): CONFLICT, ('purpose', 'hemostasis'): CONFLICT})
        # either negation alone stands
        alone = answered(request(part, lift_not), {part.key: 'release', lift_not.key: 'release'})
        self.assertEqual([record['result'] for record in settle.exclusive(alone)], ['supported', 'supported'])


def _weakenings(record: dict) -> list[tuple[str, dict]]:
    """Every single weakening of one stored record DESIGN-v2 f.2 lists, as settle_questions would store it: its claim
    demoted (unclear, qualified, missing), its control not rejected, its proof unlocated, its request made unhealthy or
    unanswered (every record of that request then carries the request's reason)."""
    out = []
    claim = record['verdicts']['claim']
    if claim == 'supports':
        for verdict, reason in (('unclear', 'question_unclear'), ('qualified', 'question_qualified:other'),
                                (None, 'question_missing')):
            out.append((f'claim {verdict}', {**record, 'result': 'unresolved', 'reasons': [reason], 'proof': [],
                                             'held_by_answer': False,
                                             'verdicts': {**record['verdicts'], 'claim': verdict}}))
        out.append(('proof unlocated', {**record, 'result': 'unresolved', 'reasons': ['proof_unlocated'],
                                        'proof': []}))
        out.append(('control unclear', {**record, 'result': 'unresolved', 'reasons': ['question_incoherent'],
                                        'proof': [], 'verdicts': {**record['verdicts'], 'control': 'unclear'}}))
    if claim == 'contradicts':
        for verdict, reason in (('unclear', 'question_unclear'), (None, 'question_missing')):
            out.append((f'rejection made {verdict}', {**record, 'result': 'unresolved', 'reasons': [reason],
                                                      'proof': [], 'held_by_answer': False,
                                                      'verdicts': {**record['verdicts'], 'claim': verdict}}))
    for reason in ('question_health:calibration', 'question_health:controls', 'question_health:uncalibrated',
                   'question_request_failed:failed', 'question_request_failed:too_long'):
        out.append((reason, {**record, 'result': 'unresolved', 'reasons': [reason], 'proof': []}))
    return out


class ExclusivityMonotoneTests(SimpleTestCase):
    """P-MONO-Q and P-SPLIT over exclusivity (DESIGN-v2 f.2, f.4; D324 (2): "a weakening can only add a blocker"): for
    every scene below and every single weakening of any one of its records, no record is 'supported' after exclusivity
    that was not 'supported' before it - and a weakening of request j never establishes a record of request i."""

    def scenes(self) -> dict[str, list[dict]]:
        lift_not = fact_spec('fact.lift.not', A.PURPOSE, 'lift_for_resection', True, census='F11')
        hemostasis = fact_spec('fact.purpose', A.PURPOSE, 'hemostasis')
        lift = fact_spec('fact.purpose', A.PURPOSE, 'lift_for_resection')
        mdm = fact_spec('fact.visit.basis', A.VISIT_BASIS, 'medical_decision_making', census='C6')
        time_ = fact_spec('fact.visit.basis', A.VISIT_BASIS, 'total_time', census='C6')
        return {
            'L4-1: X1 wrong-consistent, X2 right, two requests':
                answered(request(X1), {X1.key: 'release'}) + answered(request(X2), {X2.key: 'release'}),
            'L4-1 in one request': answered(request(X1, X2), {X1.key: 'release', X2.key: 'release'}),
            'a doubt answered right': answered(request(X1), {X1.key: 'hold'})
                + answered(request(X2), {X2.key: 'release'}),
            'G1 and F2 of one examination': answered(request(NOT_X1, NOT_X2, X2),
                                                    {NOT_X1.key: 'release', NOT_X2.key: 'hold', X2.key: 'release'}),
            'the purpose slot': answered(request(lift_not, hemostasis, lift),
                                         {lift_not.key: 'release', hemostasis.key: 'hold', lift.key: 'hold'}),
            "the visit's basis": answered(request(mdm, time_), {mdm.key: 'release', time_.key: 'hold'}),
        }

    def test_no_single_weakening_establishes_a_record(self) -> None:
        for name, records in self.scenes().items():
            before = settle.exclusive(records)
            established = {index for index, record in enumerate(before) if record['result'] == 'supported'}
            for index, record in enumerate(records):
                for kind, weakened in _weakenings(record):
                    after = settle.exclusive(records[:index] + [weakened] + records[index + 1:])
                    grown = {position for position, found in enumerate(after)
                             if found['result'] == 'supported' and position not in established}
                    with self.subTest(scene=name, record=index, weakening=kind):
                        self.assertEqual(grown, set(), (name, record['value'], kind))

    def test_the_census_finds_a_growth_on_the_rule_int4_ran(self) -> None:
        """The property is no tautology: int4's rule (only established values counted per slot), applied to the same
        scenes, grows an established record under single weakenings - the L4-1 class."""
        def slot(record: dict):  # int4's single(): a Q-FACT record of a single-valued slot
            from studio.interpretation.engine import facts
            from studio.interpretation.engine.types import Id
            subject = record['subjects'][0]
            domain = facts.DOMAINS.get((Id.parse(subject).family, A(record['attribute'])))
            return (subject, record['attribute']) if domain is not None and not domain.many else None

        def int4_exclusive(records: list[dict]) -> list[dict]:  # int4's rule: only established values counted
            counts: dict = {}
            for record in records:
                if record.get('result') == 'supported' and slot(record) is not None:
                    counts.setdefault(slot(record), set()).add((record['value'], record.get('negated')))
            return [{**record, 'result': 'unresolved', 'reasons': ['question_conflict'], 'proof': []}
                    if record.get('result') == 'supported' and slot(record) is not None
                    and len(counts.get(slot(record), ())) > 1 else record for record in records]

        grown = []
        for name, records in self.scenes().items():
            established = {index for index, record in enumerate(int4_exclusive(records))
                           if record['result'] == 'supported'}
            for index, record in enumerate(records):
                for kind, weakened in _weakenings(record):
                    after = int4_exclusive(records[:index] + [weakened] + records[index + 1:])
                    if {position for position, found in enumerate(after)
                            if found['result'] == 'supported'} - established:
                        grown.append((name, index, kind))
        self.assertTrue([item for item in grown if item[0].startswith('L4-1')], grown)


# --- D324 (2): the finding's own input through the WHOLE pipeline (the verifier's reproduction, ported) ------------------
#
# The scene (attack/verify-L4-properties-L4-1 test_verify_l41, its own synthetic report): one encounter, a colonoscopy X1
# (E1) and an upper endoscopy X2 (E2); four cold-forceps biopsies E3-E6, each of its own nodule L1-L4, whose session
# pass 1 DOUBTED between X1 and X2 (or, in the silent variant, left silent). The truth by the scene's design: all four
# biopsies are gastric (X2). The planner asks each biopsy's session at X1 (for 45380) and at X2 (for 43239); one more
# question (pass 2 leaves E1's session without a verdict: C2a) is planned first, so the round's nine questions cut 8 + 1
# at QUESTION_BOUND 18 with one calibration item a request: E6's X1 in request 1, E6's X2 alone in request 2. Every
# question answered right EXCEPT E6 at X1, answered WRONG but consistently.

BODY = ('Date of service: 03/14/2031\n'
        'Endoscopist: Corvin Ashdale, MD (fictional)\n'
        '\n'
        'Colonoscopy: The colonoscope was advanced to the cecum.\n'
        'Upper endoscopy: The gastroscope was advanced to the duodenum.\n'
        'Biopsies: Cold forceps biopsies were taken of a 3 mm nodule.\n'
        'Cold forceps biopsies were taken of a 4 mm nodule.\n'
        'Cold forceps biopsies were taken of a 5 mm nodule.\n'
        'Cold forceps biopsies were taken of a 6 mm nodule.\n')
TEXT = 'SYNTHETIC COMBINED ENDOSCOPY REPORT R3C\n' + BODY
TEXT_SILENT = 'SYNTHETIC COMBINED ENDOSCOPY REPORT R3C B\n' + BODY
BIOPSY_UNITS = {'E3': 'S6', 'E4': 'S7', 'E5': 'S8', 'E6': 'S9'}
SIZES = {'E3': '3', 'E4': '4', 'E5': '5', 'E6': '6'}
LAST = 'E6'
LAST_X1 = ('Q-FACT', (LAST,), 'session', 'X1', False)
LAST_X2 = ('Q-FACT', (LAST,), 'session', 'X2', False)


def combined_answer(session_mode='doubted'):
    lesions, events, doubts = [], [], []
    for number, (eid, unit) in enumerate(sorted(BIOPSY_UNITS.items()), start=1):
        words = f'a {SIZES[eid]} mm nodule'
        lesions.append(lesion(f'L{number}', src([unit], words), multiplicity=[fact('single', src([unit], words))]))
        fields = {'target__lesion': [fact(f'L{number}', src([unit], words))],
                  'technique__device': [fact('cold_forceps', src([unit], 'Cold forceps'))]}
        if session_mode == 'doubted':
            fields['session'] = [fact('X1', src([unit]))]
            doubts.append(doubt('session', [eid], [unit], 'unclear', readings=['X1', 'X2']))
        events.append(event(eid, [unit], 'Cold forceps biopsies', 'were taken', 'biopsy', **fields))
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'Colonoscopy:', 'procedure'),
                  labelled('N2', 'S5', 'Upper endoscopy:', 'procedure'), labelled('N3', 'S6', 'Biopsies:', 'findings')],
        sessions=[session('X1', fact('colonoscopy', src(['S4'], 'colonoscope')), examination=[fact('E1', src(['S4']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('cecum', src(['S4'], 'advanced to the cecum'))]),
                  session('X2', fact('egd', src(['S5'], 'gastroscope')), examination=[fact('E2', src(['S5']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('duodenum', src(['S5'], 'advanced to the duodenum'))])],
        events=[event('E1', ['S4'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S4']))]),
                event('E2', ['S5'], 'gastroscope', 'was advanced', 'examination', session=[fact('X2', src(['S5']))]),
                *events],
        lesions=lesions, doubts=doubts)


ANSWERS = {**TQS.ANSWERS, TEXT: combined_answer, TEXT_SILENT: lambda: combined_answer('silent')}
UNLOCATED = 'the gastric nodules were sampled in the stomach'  # a paraphrase: in no passage of the note


def spec_of(item):
    spec = item.spec
    return (spec.family.value, tuple(spec.subjects), spec.attribute.value if spec.attribute is not None else None,
            spec.value, spec.negated)


def right_release(spec):
    """Whether the RIGHT answer is the release pattern: every question but a biopsy's session at X1."""
    family, subjects, attribute, value, negated = spec
    return not (attribute == 'session' and value == 'X1' and subjects[0] in BIOPSY_UNITS)


def verdict_rows(question, text, weaken=None, breach=False):
    """One question request's answer: right answers but E6 at X1 (WRONG, consistently); ``weaken`` = (spec, kind) that
    one question's answer weakened ('claim_unclear', 'control_unclear', 'unlocated'); ``breach`` the calibration
    item's claim supported (H2)."""
    rows = []
    for item in question.items:
        if item.role == 'calibration':
            pairs = [(item.claim, 'supports' if breach else 'contradicts', []), (item.control, 'supports', [])]
        else:
            spec = spec_of(item)
            passages = list(item.required) or list(item.alternatives[:1])
            quotes = [found for found in (TQS.oracle_quote(text, passage) for passage in passages) if found][:2]
            release = right_release(spec) or spec == LAST_X1
            claim, control = ('supports', 'contradicts') if release else ('contradicts', 'supports')
            if not release:
                quotes = []
            kind = weaken[1] if weaken is not None and weaken[0] == spec else ''
            if kind == 'claim_unclear':
                claim = 'unclear'
            elif kind == 'control_unclear':
                control = 'unclear'
            elif kind == 'unlocated':
                quotes = [UNLOCATED]
            pairs = [(item.claim, claim, quotes), (item.control, control, [])]
        for claim_id, value_, quotes_ in pairs:
            rows.append({'claim': claim_id, 'verdict': value_, 'attached': 'yes', 'qualifiers': [],
                         'evidence': list(item.cited[:1]), 'quotes': quotes_})
    rows.sort(key=lambda node: int(node['claim'][1:]))
    return {'verdicts': rows, 'unlisted': []}


class VerifyInterpreter(TQS.QuestionInterpreter):
    """test_question_stage's connector, the question answers built by ``verdict_rows``; the ONE request holding the
    question ``request_target`` answered as ``request_variant`` says ('' answered; 'breach'; 'failed' HTTP 500;
    'too_long' cut at max_tokens)."""

    def __init__(self, *args, weaken=None, request_target=LAST_X2, request_variant='', **kwargs):
        super().__init__(*args, **kwargs)
        self.weaken, self.request_target, self.request_variant = weaken, request_target, request_variant
        self.log = []

    def _exchange(self, body_dict, deadline, purpose):
        if fable_adapter.request_kind(body_dict)[0] != fable_adapter.QUESTION:
            return super()._exchange(body_dict, deadline, purpose)
        sha = request_sha256(body_dict)
        question = self.built[sha]
        text = question.request.contexts[0]
        targeted = any(item.role != 'calibration' and spec_of(item) == self.request_target for item in question.items)
        data = verdict_rows(question, text, self.weaken, breach=targeted and self.request_variant == 'breach')
        with self.guard:
            self.question_sent.append(sha)
            self.log.append((sha[:12], sorted(spec_of(item)[1:4] for item in question.items
                                              if item.role != 'calibration'), targeted))
        if targeted and self.request_variant == 'failed':
            return TJ.answered(TJ.HTTP_500, status=500)
        if targeted and self.request_variant == 'too_long':
            return TJ.answered(TJ.stream_of(json.dumps(data), stop_reason='max_tokens'))
        return TJ.answered(TJ.body(data))


class VerifyCase(TQS.QuestionCase):
    def setUp(self):
        super().setUp()
        self.walks = []
        self.provider = FakeProvider([('45380', 'Cold forceps biopsies were taken of a 6 mm nodule.'),
                                      ('43239', 'Cold forceps biopsies were taken of a 3 mm nodule.')])

    def walk(self, text=TEXT, leave=(('E1', A.SESSION),), **kwargs):
        interpreter = VerifyInterpreter(ANSWERS, oracle=TQS.leaving(*leave), built=self.built, **kwargs)
        patcher = mock.patch.object(fable_adapter, 'get_interpreter_v2', return_value=interpreter)
        patcher.start()
        try:
            # a FRESH workspace per walk: every reuse lookup is scoped by workspace
            workspace = f.workspace(name=f'Synthetic GI r3c {len(self.walks)}')
            f.member(workspace, self.user, role=models.Membership.REVIEWER)
            self.walks.append(workspace)
            encounter, revision = self.upload(text, workspace=workspace)
            self.drain()
        finally:
            patcher.stop()
        encounter.refresh_from_db()
        inventory = models.EventInventory.objects.get(revision=revision)
        records = inventory.events.get('questions') or []
        statuses = {proposal.code: proposal.status for proposal in encounter.current_assessment.proposals.all()}
        runs = inventory.verification.get('question_runs') or []
        sent = [run for run in runs if run['outcome'] in ('answered', 'failed', 'too_long')]
        self.assertEqual(len(interpreter.log), len(sent))
        return {'records': records, 'statuses': statuses, 'log': list(interpreter.log)}

    def last(self, out):
        return [(record['value'], record['result'], record['reasons']) for record in out['records']
                if record['subjects'] == [LAST]]

    def check_held(self, out, base, x2_reason):
        """The rule: E6's X1 held (question_conflict), its X2 unresolved for the weakening's own reason, 45380 held and
        no status moved from the baseline's."""
        self.assertEqual(self.last(out), [('X1', 'unresolved', ['question_conflict']), ('X2', 'unresolved', [x2_reason])])
        self.assertEqual(out['statuses']['45380'], 'needs_clarification')  # int4: 'ready' (a colonoscopy code, gastric)
        self.assertEqual(out['statuses'], base['statuses'])


class L41PipelineTests(VerifyCase):
    """The finding's input, its request variants and its single-answer variants, each through the pipeline."""

    def test_the_baseline_and_every_weakening_hold_45380(self):
        base = self.walk()
        requests = {targeted: questions for _sha, questions, targeted in base['log']}
        self.assertEqual(len(base['log']), 2)  # the partition: E6's X1 in request 1, its X2 alone in request 2
        self.assertIn(((LAST,), 'session', 'X1'), requests[False])
        self.assertEqual(requests[True], [((LAST,), 'session', 'X2')])
        self.assertEqual(self.last(base), [('X1', 'unresolved', ['question_conflict']),
                                           ('X2', 'unresolved', ['question_conflict'])])
        self.assertEqual(base['statuses'], {'45380': 'needs_clarification', '43239': 'needs_clarification'})
        variants = {
            'request 2 breaches its calibration item': ({'request_variant': 'breach'}, 'question_health:calibration'),
            'request 2 failed (HTTP 500)': ({'request_variant': 'failed'}, 'question_request_failed:failed'),
            'request 2 cut at max_tokens': ({'request_variant': 'too_long'}, 'question_request_failed:too_long'),
            "E6:X2's proof unlocated": ({'weaken': (LAST_X2, 'unlocated')}, 'proof_unlocated'),
            "E6:X2's control unclear": ({'weaken': (LAST_X2, 'control_unclear')}, 'question_incoherent'),
            "E6:X2's claim unclear": ({'weaken': (LAST_X2, 'claim_unclear')}, 'question_unclear'),
        }
        for name, (kwargs, reason) in variants.items():
            with self.subTest(variant=name):
                self.check_held(self.walk(**kwargs), base, reason)


class L41OneRequestTests(VerifyCase):
    """The same answers with no E1 question (eight questions: ONE request holds both of E6's values)."""

    def test_one_request_baseline_and_weakenings(self):
        base = self.walk(leave=())
        self.assertEqual(len(base['log']), 1)
        self.assertEqual(base['statuses']['45380'], 'needs_clarification')
        for kind, reason in (('unlocated', 'proof_unlocated'), ('control_unclear', 'question_incoherent'),
                             ('claim_unclear', 'question_unclear')):
            with self.subTest(weakening=kind):
                self.check_held(self.walk(leave=(), weaken=(LAST_X2, kind)), base, reason)


class L41SilentSessionTests(VerifyCase):
    """The class on a SILENT session (A3/F2: each code's family session asked), not only a doubt's readings."""

    def test_silent_session(self):
        base = self.walk(text=TEXT_SILENT)
        self.assertEqual(base['statuses']['45380'], 'needs_clarification')
        for kwargs in ({'request_variant': 'breach'}, {'weaken': (LAST_X2, 'control_unclear')}):
            with self.subTest(**{key: str(value) for key, value in kwargs.items()}):
                out = self.walk(text=TEXT_SILENT, **kwargs)
                self.assertEqual(out['statuses']['45380'], 'needs_clarification')  # int4: 'ready'
                self.assertEqual(out['statuses'], base['statuses'])


class L41CensusTests(VerifyCase):
    """Every SINGLE weakening of the answer set (each question's claim demoted, its control not rejected, its proof
    unlocated; each of E6's two requests breached or failed) through the pipeline: none grows READY over the baseline
    (int4: 8 of 31 did, all on E6's session slot)."""

    def test_no_single_weakening_grows_ready(self):
        base = self.walk()
        ready0 = {code for code, status in base['statuses'].items() if status == 'ready'}
        specs = sorted({tuple(q) for _sha, questions, _t in base['log'] for q in questions})
        grown = []
        for subjects, attribute, value in specs:
            spec = ('Q-FACT', subjects, attribute, value, False)
            for kind in ('claim_unclear', 'control_unclear', 'unlocated'):
                ready = {code for code, status in self.walk(weaken=(spec, kind))['statuses'].items()
                         if status == 'ready'}
                if ready - ready0:
                    grown.append((subjects, value, kind, sorted(ready - ready0)))
        for target in (LAST_X1, LAST_X2):
            for variant in ('breach', 'failed'):
                ready = {code for code, status in self.walk(request_target=target, request_variant=variant)[
                    'statuses'].items() if status == 'ready'}
                if ready - ready0:
                    grown.append(('request of', target[1:4], variant, sorted(ready - ready0)))
        self.assertEqual(grown, [])


# --- D324 (9): the frame value passage named by its own field, exempt from the heading ban ------------------------------

# int4's PROOF paragraph (the r3b repair pass's, which RF2-CLM-1 refuted), byte for byte - its instruction's sha256 is int4's
# pin (APPRAISAL_INSTRUCTIONS_Q_SHA256_V3 993fa47c..., test_rf2_instruction_is_int4s_byte_for_byte), kept only as the
# reader's counter-example: read literally, it permits no proof where the locator requires a heading.
_RF2_PROOF = """\
PROOF
quotes: for a claim marked proof that you answer supports, copy passages of the document that show the claim is true,
every one from the units the claim cites. Copy at least one passage from the units of each act, statement, lesion,
session, anatomy entry or unlisted entry the claim names (the card it is about included; for a list of acts, from the
units of one of them): the units its card lists, and, for a session, every other unit the claim cites that no other
card it names lists. Where the claim says on what date an act was done, who did it or who wrote the part of the
document it is told in, copy at least one more: from the units the claim cites beyond those the act's card lists, or,
if it cites none beyond them, from the act's own units, where they say it. Copy any further passage from the units the
claim cites. Never copy the words of a heading from the units an act's, a statement's, a lesion's or an anatomy
entry's card lists, except that, for a claim about where an act was done, a further passage may be the heading of
the part of the document the act is told in, which the claim cites. Each passage is the exact words of the
document (a line break or a run of spaces may be written as one space),
at least {tokens} words and {chars} characters other than spaces long and at most {longest} characters long, without
unit labels or [Page N] lines; no two passages overlap; and a sentence that a line break splits across two units may
be copied as one passage from each unit, or as one passage when one card the claim names lists both units.
Give at most {cap} passages.
The absence of a statement is never a passage: for a claim that something was not done or was not caused by
something, or that a statement does not concern, deny, cast doubt on, plan or recommend an act, copy the words that
say what was done or caused, or what the statement says, instead. If you cannot point to such words, do not answer
supports. For every other verdict, and for a claim without the mark, write an empty list.""".format(
    tokens=proof.MIN_TOKENS, chars=proof.MIN_CHARS, longest=appraise_read.QUOTE_MAX_CHARS,
    cap=appraise_schema.QUOTES_MAX)
INT4_CLAIM_LINE = '{claim} (about {card}; names {names}; cites {units}; proof): {sentence}'
FRAME_FORMS = (('fact.entry', A.ENTRY, 'documenting_clinician'),
               ('fact.date_relation', A.DATE_RELATION, 'on_date_of_service'),
               ('fact.performer', A.PERFORMER, 'documenting_team'))


def inherited(section: str, *forms) -> dict:
    """An act's frame facts, each inherited from ``section`` (no source of its own: the value passage is the section's
    start and its own fact's sources)."""
    return {attribute.value: TRC._source(value, inherited=section) for _, attribute, value in (forms or FRAME_FORMS)}


@dataclasses.dataclass(frozen=True)
class Scene:
    """One synthetic headed report: its text (one unit per line), cards, view records, the heading spans (each part's
    start: its whole start units, or its 'at' words) and the reader's marks."""
    text: str
    cards: tuple
    events: tuple
    sections: tuple
    anatomy: tuple = ()
    marks: TRC.Marks = TRC.Marks()

    @property
    def headings(self) -> tuple:
        units = {unit['id']: (unit['start'], unit['end']) for unit in TRC.units_of(self.text)}
        out = []
        for section in self.sections:
            at = section['start'].get('at')
            out += [(at['start'], at['end'])] if at else [units[unit] for unit in section['start']['units']]
        return tuple(out)

    def built(self, specs, calibration=()):
        cards, objects = TRC._cards(*self.cards)
        return TRC.built_request(self.text, cards, objects, list(specs), list(calibration), events=self.events,
                                 sections=self.sections), objects

    def frame(self, event: str, form: str, attribute, value: str):
        return TRC._planned(FAM.Q_FACT, form, (event,), attribute, value)

    def follows(self, item, built, objects, proof_text: str = ''):
        """(the proofs the instruction ``proof_text`` - QC.PROOF by default - permits for ``item``, read literally over
        every card of the request; those the locator voids)."""
        reader = TRC.InstructionReader(proof_text or QC.PROOF)
        seen = TRC.seen_of(built, self.text, self.headings)
        proofs = reader.proofs(seen, item, TRC.groups_of(item.spec, objects), self.marks)
        return proofs, [quotes for quotes in proofs if not TRC.located(self.text, item, quotes).located]


def _section_cards(*sections: tuple) -> tuple:
    return tuple((card, ct.CardType.SECTION, 'section', card, units) for card, units in sections)


# THE REFUTER'S FIRST SHAPE (refute2 NestedHeadingFrame; my own words): the part's heading is its own line, S2, and opens
# the act's own card (S2-S3); the act's date, doer and author are inherited from that part - the value passage is S2
# alone, a heading the act's card lists
NESTED = Scene(
    text=('SYNTHETIC COLONOSCOPY NOTE, R3C\n'                                          # S1  N0
          'POLYPECTOMY DETAILS AND FINDINGS FROM THIS PROCEDURE TODAY\n'                # S2  N1's start: A1's card
          'A 7 mm sessile polyp in the sigmoid colon was removed with a cold snare.\n'  # S3  A1
          'The scope was then withdrawn and the procedure was ended.\n'),               # S4
    cards=(('A1', ct.CardType.ACT, 'event', 'E1', ('S2', 'S3')), ('A2', ct.CardType.ACT, 'event', 'E2', ('S4',)),
           *_section_cards(('N0', ('S1',)), ('N1', ('S2',)))),
    events=({'id': 'E1', **inherited('N1')}, {'id': 'E2', **inherited('N1')}),
    sections=({'id': 'N0', 'start': {'units': ['S1']}}, {'id': 'N1', 'start': {'units': ['S2']}}))
NESTED_HEADING = 'POLYPECTOMY DETAILS AND FINDINGS FROM THIS PROCEDURE TODAY'
NESTED_ACT = 'polyp in the sigmoid colon was removed'

# THE REFUTER'S SECOND SHAPE (refute2 HeadingListedByAnotherCard): the part's heading S2 opens a LESION's card (S2-S3);
# the act is told at S4; its frame inherited from the part - the value passage S2 alone, a heading a lesion's card lists
BY_LESION = Scene(
    text=('SYNTHETIC COLONOSCOPY NOTE, R3C LESION\n'                                  # S1  N0
          'Hepatic flexure lesion findings\n'                                           # S2  N1's start: L1's card
          'A 12 mm flat lesion was seen at the hepatic flexure.\n'                     # S3  L1
          'The lesion was lifted with saline and resected by EMR in one piece.\n'),    # S4  A1
    cards=(('L1', ct.CardType.LESION, 'lesion', 'L1', ('S2', 'S3')), ('A1', ct.CardType.ACT, 'event', 'E1', ('S4',)),
           *_section_cards(('N0', ('S1',)), ('N1', ('S2',)))),
    events=({'id': 'E1', **inherited('N1')},),
    sections=({'id': 'N0', 'start': {'units': ['S1']}}, {'id': 'N1', 'start': {'units': ['S2']}}))
BY_LESION_HEADING = 'Hepatic flexure lesion findings'

# VARIANTS: an anatomy entry's card lists the heading; a heading of two lines (the part's start two units, both on a
# lesion's card) with the part's performer source a third heading line; the act's own unit as its value (its own words
# carry its date); and a performer with no source and nothing inherited (an empty value passage)
BY_ANATOMY = Scene(
    text=('SYNTHETIC POUCHOSCOPY NOTE, R3C\n'                                           # S1  N0
          'Ileal pouch anastomosis survey\n'                                            # S2  N1's start: Y1's card
          'The ileal pouch anal anastomosis was patent and healthy.\n'                  # S3  Y1
          'Two cold forceps biopsies of the pouch body were taken.\n'),                 # S4  A1
    cards=(('Y1', ct.CardType.ANATOMY, 'anatomy', 'Y1', ('S2', 'S3')), ('A1', ct.CardType.ACT, 'event', 'E1', ('S4',)),
           *_section_cards(('N0', ('S1',)), ('N1', ('S2',)))),
    events=({'id': 'E1', **inherited('N1')},),
    sections=({'id': 'N0', 'start': {'units': ['S1']}}, {'id': 'N1', 'start': {'units': ['S2']}}))
TWO_LINES = Scene(
    text=('SYNTHETIC COLONOSCOPY NOTE, R3C TWO LINES\n'                                 # S1  N0
          'Descending colon findings and\n'                                             # S2  N1's start (1 of 2)
          'therapy performed by the attending\n'                                        # S3  N1's start (2 of 2)
          'A 15 mm pedunculated polyp was seen in the descending colon.\n'             # S4  L1 (S2-S4)
          'Its stalk was transected with a hot snare after an endoloop.\n'             # S5  A1
          'PROCEDURALIST OF RECORD FOR THIS PART\n'),                                   # S6  N1's performer source: L2
    cards=(('L1', ct.CardType.LESION, 'lesion', 'L1', ('S2', 'S3', 'S4')),
           ('L2', ct.CardType.LESION, 'lesion', 'L2', ('S6',)), ('A1', ct.CardType.ACT, 'event', 'E1', ('S5',)),
           *_section_cards(('N0', ('S1',)), ('N1', ('S2', 'S3')), ('N2', ('S6',)))),
    events=({'id': 'E1', **inherited('N1')},),
    sections=({'id': 'N0', 'start': {'units': ['S1']}},
              {'id': 'N1', 'start': {'units': ['S2', 'S3']},
               'performer': TRC._source('documenting_team', 'S6')},
              {'id': 'N2', 'start': {'units': ['S6']}}))
OWN_UNIT = Scene(
    text=('SYNTHETIC COLONOSCOPY NOTE, R3C OWN UNIT\n'                                  # S1  N0
          'Clip placement in the cecum\n'                                               # S2  N1's start: A1's card
          'Today I placed two clips on the cecal polypectomy site myself.\n'),         # S3  A1, its own date and doer
    cards=(('A1', ct.CardType.ACT, 'event', 'E1', ('S2', 'S3')), *_section_cards(('N0', ('S1',)), ('N1', ('S2',)))),
    events=({'id': 'E1', 'date_relation': TRC._source('on_date_of_service', 'S3'),
             'performer': TRC._source('documenting_team', 'S3'),
             'entry': TRC._source('documenting_clinician', inherited='N1')},),
    sections=({'id': 'N0', 'start': {'units': ['S1']}}, {'id': 'N1', 'start': {'units': ['S2']}}))
SILENT = Scene(
    text=('SYNTHETIC COLONOSCOPY NOTE, R3C SILENT\n'                                    # S1  N0
          'A 3 mm polyp in the rectum was removed with cold forceps today.\n'),        # S2  A1
    cards=(('A1', ct.CardType.ACT, 'event', 'E1', ('S2',)), *_section_cards(('N0', ('S1',)),)),
    events=({'id': 'E1', 'performer': {'claim': {'value': '', 'state': None, 'inherited_from': None}, 'sources': [],
                                       **TRC._PASSED}},),
    sections=({'id': 'N0', 'start': {'units': ['S1']}},))
HEADED = {'the heading opens the act\'s own card': (NESTED, 'E1', 'S2'),
          'the heading on a lesion\'s card': (BY_LESION, 'E1', 'S2'),
          'the heading on an anatomy entry\'s card': (BY_ANATOMY, 'E1', 'S2')}


def _value_units(item: QC.Item, text: str) -> list[str]:
    """The units of the locator's value set (``_passages``' last required set of a frame claim)."""
    return TRC._unit_ids_of(item.required[-1], text)


def _line_of(built: QC.QuestionRequest, item: QC.Item) -> str:
    return next(line for line in built.lines if line.startswith(item.claim + ' '))


def _k1(event: str, beside: str = ''):
    """A frame K1 calibration item about ``event`` - its performer, or its date relation beside a performer question
    (``beside``: the question's form), so the item never repeats the question's own sentence."""
    if beside == 'fact.performer':
        return TRC._planned(FAM.Q_FACT, 'fact.date_relation', (event,), A.DATE_RELATION, 'on_date_of_service', True,
                            kind='K1')
    return TRC._planned(FAM.Q_FACT, 'fact.performer', (event,), A.PERFORMER, 'documenting_team', True, kind='K1')


class ValueFieldTests(SimpleTestCase):
    """DECISIONS D324 (9): the claim line names the frame value passage by its own field ("value at"), exactly the units
    of the locator's value set; "no unit" when that set is empty; every other claim's line is int4's, byte for byte."""

    def test_the_field_names_the_locators_value_set(self) -> None:
        shapes = {**HEADED, 'a heading of two lines and a performer source': (TWO_LINES, 'E1', None),
                  "the act's own unit": (OWN_UNIT, 'E1', None)}
        for name, (scene, event, _) in shapes.items():
            for form, attribute, value in FRAME_FORMS:
                built, _objects = scene.built([scene.frame(event, form, attribute, value)])
                item = built.items[0]
                with self.subTest(shape=name, form=form):
                    units = _value_units(item, scene.text)
                    self.assertTrue(units)
                    self.assertIn(f'; value at {TRC.claims.units_phrase(units)}; proof): ', _line_of(built, item))
                    seen = TRC.seen_of(built, scene.text, scene.headings)
                    self.assertEqual(seen.values[item.claim], tuple(units))
                    # the value units are cited too (the cites field is the union of the claim's passages, unchanged)
                    self.assertTrue(set(units) <= set(seen.lines[item.claim][2]))

    def test_the_refuters_shapes_value_units(self) -> None:
        for name, (scene, event, unit) in HEADED.items():
            built, _objects = scene.built([scene.frame(event, 'fact.entry', A.ENTRY, 'documenting_clinician')])
            with self.subTest(shape=name):
                self.assertEqual(_value_units(built.items[0], scene.text), [unit])
        built, _ = TWO_LINES.built([TWO_LINES.frame('E1', 'fact.performer', A.PERFORMER, 'documenting_team')])
        self.assertEqual(_value_units(built.items[0], TWO_LINES.text), ['S2', 'S3', 'S6'])
        built, _ = OWN_UNIT.built([OWN_UNIT.frame('E1', 'fact.date_relation', A.DATE_RELATION, 'on_date_of_service')])
        self.assertEqual(_value_units(built.items[0], OWN_UNIT.text), ['S3'])  # the act's own unit

    def test_an_empty_value_passage_says_no_unit_and_nothing_is_permitted(self) -> None:
        spec = SILENT.frame('E1', 'fact.performer', A.PERFORMER, 'documenting_team')
        built, objects = SILENT.built([spec])
        item = built.items[0]
        self.assertIn('; value at no unit; proof): ', _line_of(built, item))
        self.assertEqual(TRC.seen_of(built, SILENT.text, SILENT.headings).values[item.claim], ())
        proofs, voided = SILENT.follows(item, built, objects)
        self.assertEqual((proofs, voided), ([], []))  # the claim cannot be proven, as the instruction says
        self.assertFalse(TRC.located(SILENT.text, item, ['A 3 mm polyp in the rectum', 'removed with cold forceps'])
                         .located)  # and no proof locates: the value set has no words (the locator is unchanged)

    def test_a_frame_calibration_item_carries_the_field_too(self) -> None:
        built, _ = NESTED.built([], [_k1('E2')])
        item = built.items[0]
        self.assertEqual(item.role, 'calibration')
        self.assertIn('; value at S2; proof): ', _line_of(built, item))  # indistinguishable from a question (b.9)

    def test_every_other_claim_line_is_int4s(self) -> None:
        self.assertEqual(QC.CLAIM_LINE_Q.format(claim='K1', card='A1', names='A1', units='S1', value='', sentence='x'),
                         INT4_CLAIM_LINE.format(claim='K1', card='A1', names='A1', units='S1', sentence='x'))
        for name, spec, _degenerate in TRC.doc_shapes():
            if spec.form in ('fact.entry', 'fact.date_relation', 'fact.performer'):
                continue
            built, item = TRC.doc_request(spec)
            with self.subTest(shape=name):
                self.assertNotIn('; value at ', ''.join(built.lines))
                # moved by the r3d claims lane (DECISIONS D325 (4)): an 'own' claim's field reads its own sources' geometry
                # (here no source outside its subject's card, so no field: the line above); was read for frame claims only
                if spec.value_passage != 'own':
                    self.assertEqual(QC._value_field(spec, None), '')  # read for frame and own claims only


class HeadedFrameTests(SimpleTestCase):
    """RF2-CLM-1's own inputs and their variants, read literally: every proof the instruction permits locates, some
    proof is permitted wherever one locates, and settle establishes a right answer that follows it. int4's instruction
    permitted none on these shapes (test_the_r3b_instruction_permitted_none_where_one_locates)."""

    def check_frame(self, scene: Scene, event: str, form: str, attribute, value: str, name: str) -> list:
        built, objects = scene.built([scene.frame(event, form, attribute, value)], [_k1(event, form)])
        item = next(found for found in built.items if found.role == 'question')
        proofs, voided = scene.follows(item, built, objects)
        self.assertTrue(proofs, (name, form))  # int4: [] - the instruction forbade the passage the locator requires
        self.assertEqual(voided, [], (name, form))
        return proofs

    def test_the_refuters_shapes_and_the_variants(self) -> None:
        shapes = {**HEADED, 'a heading of two lines': (TWO_LINES, 'E1', None),
                  "the act's own unit (its own date and doer)": (OWN_UNIT, 'E1', None)}
        for name, (scene, event, _) in shapes.items():
            for form, attribute, value in FRAME_FORMS:
                with self.subTest(shape=name, form=form):
                    self.check_frame(scene, event, form, attribute, value, name)

    def test_a_permitted_proof_copies_the_heading_as_the_value_passage(self) -> None:
        for name, (scene, event, unit) in HEADED.items():
            proofs = self.check_frame(scene, event, 'fact.entry', A.ENTRY, 'documenting_clinician', name)
            heading = NESTED_HEADING if scene is NESTED else BY_LESION_HEADING if scene is BY_LESION else None
            with self.subTest(shape=name):
                if heading is not None:
                    self.assertTrue(any(any(part in heading for part in quotes) for quotes in proofs), name)

    def test_a_right_answer_that_follows_the_instruction_is_established(self) -> None:
        for name, (scene, event, _) in HEADED.items():
            for form, attribute, value in FRAME_FORMS:
                built, objects = scene.built([scene.frame(event, form, attribute, value)], [_k1(event, form)])
                item = next(found for found in built.items if found.role == 'question')
                proofs, _ = scene.follows(item, built, objects)
                found = TRC.answered(built, scene.text, ('supports', proofs[0]), ('contradicts', []))
                with self.subTest(shape=name, form=form):
                    self.assertEqual(found.health['refused'], [])
                    self.assertEqual((found.questions[0]['result'], found.questions[0]['reasons']), ('supported', []))

    def test_the_r3b_instruction_permitted_none_where_one_locates(self) -> None:
        """The class, kept as evidence: int4's PROOF (byte for byte), read literally - its "beyond" units under the heading
        clause like every unit a card lists - permits NO proof on the refuter's shapes, while the locator locates a
        right one (the act's words beside the heading); so a right answer that followed it was always voided."""
        reader = TRC.InstructionReader(_RF2_PROOF)
        self.assertEqual({clause: form for clause, form in reader.forms.items() if form != 'repaired'},
                         {'session': 'rf2', 'frame': 'rf2', 'heading': 'rf2'})
        cases = (('the heading opens the act\'s own card', NESTED, NESTED_ACT, NESTED_HEADING),
                 ('the heading on a lesion\'s card', BY_LESION, 'lifted with saline and resected by EMR',
                  BY_LESION_HEADING))
        for name, scene, act_words, heading in cases:
            event = 'E1'
            for form, attribute, value in FRAME_FORMS:
                built, objects = scene.built([scene.frame(event, form, attribute, value)])
                item = built.items[0]
                with self.subTest(shape=name, form=form):
                    self.assertEqual(scene.follows(item, built, objects, _RF2_PROOF)[0], [])
                    self.assertTrue(TRC.located(scene.text, item, [act_words, heading]).located)

    def test_rf2_instruction_is_int4s_byte_for_byte(self) -> None:
        instructions = QC.FACT_INSTRUCTIONS + '\n' + QC.MARKER + '\n\n' + _RF2_PROOF + '\n'
        self.assertEqual(jsonschema.sha256_of(instructions),
                         '993fa47c713f518961e04b6fa49d343678dc5ecaca90f9ac52550b5a944b4780')


# A HEADED LONG NOTE in A-note8's format (invented words): each part headed by its own short line, the heading listed by a
# lesion's card (S3, S6), the act's own card (S9) or an anatomy entry's (S14) - or by no card at all (S11, the control);
# every act below a heading inherits its entry, date and performer from that part
LONG = Scene(
    text=('SYNTHETIC COLONOSCOPY REPORT - SURVEILLANCE, R3C LONG\n'                    # S1  N0
          'The procedure was performed today by the documenting clinician.\n'          # S2  N0's occasion/performer
          'Hepatic flexure findings\n'                                                  # S3  N1 (L1's card)
          'A 5 mm sessile polyp was seen at the hepatic flexure.\n'                    # S4  L1
          'The polyp was removed with a cold snare and retrieved.\n'                   # S5  A1
          'Transverse colon findings\n'                                                 # S6  N2 (L2's card)
          'A 9 mm flat lesion was seen in the mid transverse colon.\n'                 # S7  L2
          'The lesion was lifted with saline and resected by EMR.\n'                   # S8  A2
          'Tattoo placement in the descending colon\n'                                  # S9  N3 (A3's card)
          'Carbon particle ink was injected in three quadrants as a marker.\n'        # S10 A3
          'Rectal retroflexion views\n'                                                 # S11 N4 (no card)
          'Retroflexion in the rectum showed small internal hemorrhoids only.\n'      # S12 A4
          'Two cold forceps biopsies of normal rectal mucosa were taken.\n'           # S13 A5
          'Sigmoid colon anastomosis survey\n'                                          # S14 N5 (Y1's card)
          'A healed colorectal anastomosis was seen at 20 cm from the anal verge.\n'  # S15 Y1
          'Two cold forceps biopsies of the anastomosis were taken.\n'),              # S16 A6
    cards=(('L1', ct.CardType.LESION, 'lesion', 'L1', ('S3', 'S4')), ('A1', ct.CardType.ACT, 'event', 'E1', ('S5',)),
           ('L2', ct.CardType.LESION, 'lesion', 'L2', ('S6', 'S7')), ('A2', ct.CardType.ACT, 'event', 'E2', ('S8',)),
           ('A3', ct.CardType.ACT, 'event', 'E3', ('S9', 'S10')), ('A4', ct.CardType.ACT, 'event', 'E4', ('S12',)),
           ('A5', ct.CardType.ACT, 'event', 'E5', ('S13',)),
           ('Y1', ct.CardType.ANATOMY, 'anatomy', 'Y1', ('S14', 'S15')), ('A6', ct.CardType.ACT, 'event', 'E6', ('S16',)),
           *_section_cards(('N0', ('S1',)), ('N1', ('S3',)), ('N2', ('S6',)), ('N3', ('S9',)), ('N4', ('S11',)),
                           ('N5', ('S14',)))),
    events=tuple({'id': event, **inherited(section)} for event, section in (
        ('E1', 'N1'), ('E2', 'N2'), ('E3', 'N3'), ('E4', 'N4'), ('E5', 'N4'), ('E6', 'N5'))),
    sections=({'id': 'N0', 'start': {'units': ['S1']}, 'occasion': TRC._source('on_date_of_service', 'S2'),
               'performer': TRC._source('documenting_team', 'S2')},
              *({'id': section, 'start': {'units': [unit]}} for section, unit in (
                  ('N1', 'S3'), ('N2', 'S6'), ('N3', 'S9'), ('N4', 'S11'), ('N5', 'S14')))))
LONG_HEADING_VALUED = ('E1', 'E2', 'E3', 'E6')  # each act whose value passage is a heading some card lists


class HeadedLongNoteTests(SimpleTestCase):
    """Every frame question of every act of the headed long note, read literally over every card of the request: every
    proof the instruction permits locates and some proof is permitted; under int4's instruction the four acts whose
    value passage is a heading a card lists had none (the 33 of 126 of A-note8, the 31 of 123 of C-C2MEM-023)."""

    def test_every_frame_question_of_every_act(self) -> None:
        for event in ('E1', 'E2', 'E3', 'E4', 'E5', 'E6'):
            for form, attribute, value in FRAME_FORMS:
                built, objects = LONG.built([LONG.frame(event, form, attribute, value)], [_k1(event, form)])
                item = next(found for found in built.items if found.role == 'question')
                proofs, voided = LONG.follows(item, built, objects)
                rf2 = LONG.follows(item, built, objects, _RF2_PROOF)[0]
                with self.subTest(event=event, form=form):
                    self.assertTrue(proofs)
                    self.assertEqual(voided, [])
                    if event in LONG_HEADING_VALUED:  # int4's instruction: no permitted proof (the class)
                        self.assertEqual(rf2, [])
                    else:  # the control: a heading no act's, lesion's or anatomy entry's card lists
                        self.assertTrue(rf2)


class ActPassageHeadingTests(SimpleTestCase):
    """D324 (9): a heading never serves as the quote for an act's own passage."""

    def test_the_locator_never_gives_the_acts_set_a_heading(self) -> None:
        built, _ = NESTED.built([NESTED.frame('E1', 'fact.entry', A.ENTRY, 'documenting_clinician')])
        item = built.items[0]
        self.assertTrue(TRC.located(NESTED.text, item, [NESTED_ACT, NESTED_HEADING]).located)
        # two passages, both from the heading: the value set gets one, the act's set none - void
        self.assertFalse(TRC.located(NESTED.text, item, ['POLYPECTOMY DETAILS AND FINDINGS',
                                                         'FROM THIS PROCEDURE TODAY']).located)
        self.assertEqual(TRC._unit_ids_of(item.required[0], NESTED.text), ['S3'])  # the act's set: S2's heading cut

    def test_the_per_object_sentence_is_load_bearing(self) -> None:
        """The repaired PROOF with its per-object clause put back in its r3b form (no "that passage never holds the words
        of a heading"): the heading clause's exemption of the value units then reaches the act's own passage, and the
        reader permits proofs the locator voids (both passages from the heading) on the nested shape."""
        text = ' '.join(QC.PROOF.split())
        repaired = TRC._CLAUSE_FORMS['session']['repaired']
        self.assertEqual(text.count(repaired), 1)
        without = text.replace(repaired, TRC._CLAUSE_FORMS['session']['rf2'][:-len(' Where')])
        self.assertEqual(TRC.InstructionReader(without).forms['session'], 'rf2')
        built, objects = NESTED.built([NESTED.frame('E1', 'fact.entry', A.ENTRY, 'documenting_clinician')])
        item = built.items[0]
        proofs, voided = NESTED.follows(item, built, objects, without)
        self.assertTrue(voided)
        self.assertEqual(NESTED.follows(item, built, objects)[1], [])  # the shipped wording: none voided

    def test_the_clauses_are_stated(self) -> None:
        text = ' '.join(QC.PROOF.split())
        for clause in ("for an act, a statement, a lesion or an anatomy entry, that passage never holds the words of a "
                       'heading.',
                       "Where the claim's line gives value units (\"value at\"), copy at least one more passage from "
                       'those units, which may hold the words of a heading; if it gives no unit there, the claim cannot '
                       'be proven.',
                       "except from the claim's value units"):
            with self.subTest(clause=clause):
                self.assertEqual(text.count(clause), 1)
        self.assertEqual(QC.VALUE_FIELD, '; value at {units}')
        self.assertEqual(QC.VALUE_NONE, 'no unit')
        self.assertIn(f'if it gives {QC.VALUE_NONE} there', text)
