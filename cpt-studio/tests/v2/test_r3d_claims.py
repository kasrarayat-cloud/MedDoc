"""Round r3's build, the third repair (DECISIONS D325), lane "claims" - the repair round's own tests. Every input SYNTHETIC
(invented reports, ids, spans and words; a fictional clinician): no document of the development set is read and nothing is
sent anywhere (the pipeline classes script the production connector's exchanges).

D325 (1) - EXCLUSIVITY BY THE TRUTH TABLE (findings L2C-1, L2C-2, R3C-L1-1, L4R-1, high). A positive value v of a
single-valued slot is established only when its own claim is supported with a located proof and its control contradicted
in an answered, healthy request, AND every other proposition asked of the slot, in any request or round, has BOTH its
claim and its control verdicts exactly as "the slot is v" implies: another value's claim "w" contradicted / control
supported; another value's negation "not w" supported / contradicted; v's own negation contradicted / supported. Anything
else holds the slot (question_conflict). A negation never establishes a value:
- L2C1PurposeSlotTests, L2C1PipelineTests: the finding's own inputs (engine level and END TO END) - "not done for
  lifting" answered CONTRADICTS (it WAS a lift) beside "done for hemostasis" supported no longer establishes hemostasis;
  the session slot's twin (G1 "not X1" contradicted beside F2 "X2" supported);
- L2C2IncoherentRivalTests, L2C2PipelineTests: a rival whose claim AND exact negation were both contradicted (or its
  negation unclear or missing) is no longer read as rejected;
- R3C1SessionSlotTests, R3C1PipelineTests: the by-words answers to a sentence telling both procedures (E9 "not during
  X1" and "not during X2" both contradicted, "during X2" supported) hold 45385;
- L4R1Tests: the product's builder, reader, locator and settle over the K1-masked purpose scene;
- TruthTableCensusTests: THE EXHAUSTIVE CENSUS D325 (1) orders - every slot of two and of three values, every set of asked
  propositions (each value positive, negated, both or neither), every claim and control verdict pair from supported,
  contradicted, unclear and missing (each record written by the real request builder, reader, locator and
  settle_questions): v is established exactly when every proposition matches v's truth table; no single verdict change
  from matching to not matching grows the established set or READY (P-MONO-Q); a negation never establishes a value;
- TruthTableVariantTests: the class beyond the findings' own forms (other values, slots, sessions, families, rounds,
  weakenings) and the boundaries the rule leaves alone.

D325 (4) - EVERY QUESTION'S PASSAGES HOLD WHERE THE ASKED VALUE WAS ESTABLISHED (finding L3P-2, medium): the second half
of this module."""
from __future__ import annotations

import dataclasses
import datetime
import itertools
import json
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio import models
from studio.interpretation import fable_adapter
from studio.interpretation.contract import appraise_read, proof, settle
from studio.interpretation.contract import question_claims as QC
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, evaluate
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import IsoDate, Outcome
from studio.providers.base import request_sha256
from tests.test_pipeline_api import FakeProvider
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_jobs as TJ
from tests.v2 import test_properties as TP
from tests.v2 import test_question_stage as TQS
from tests.v2 import test_r3_claims as TRC
from tests.v2 import test_r3_probe as TRP
from tests.v2 import test_r3c_claims as TRCC
from tests.v2.test_settle import (answer, colonoscopy, doubt, event, fact, faithful, frame, labelled, lesion, opening,
                                  session, src)

A = ct.Attribute
P, C = ct.Purpose, ct.Cause
Kind, Status, Landmark = ct.Kind, ct.Status, ct.Landmark
sup, X, E, L = EF.sup, EF.X, EF.E, EF.L
V = ct.VerdictValue
FAM = asking.Family
DAY = datetime.date(2026, 11, 9)
GEOM = ct.Reason.GEOMETRY_SECTION
S_, C_, U_, M_ = 'supports', 'contradicts', 'unclear', None  # a member's verdict; None: no verdict at all (missing)
VERDICTS = (S_, C_, U_, M_)
AFFIRMED_PAIR, REJECTED_PAIR = (S_, C_), (C_, S_)
CONFLICT = ('unresolved', ['question_conflict'])
SUPPORTED = ('supported', [])


# --- engine-level scenes and helpers (the L2 lens's test_l2c_refute, ported; FactSets from evaluate_fixtures) ------------


def dated(R):
    return replace(R, encounter={A.DATE_OF_SERVICE: (sup(IsoDate(DAY, ct.Precision.DAY)),)})


def _verdict(value):
    return SimpleNamespace(verdict=SimpleNamespace(verdict=value, qualifiers=(), attached=ct.Attached.YES),
                           quotes_bound=False, quotes=())


def settle_request(R, questions, answers):
    """One request of ``questions`` and ONE calibration item (the pool's first, answered rightly), each question answered
    ``answers[spec.key]`` = (claim, control) - a VerdictValue or None (no verdict) - every supported claim's proof
    located; then exclusivity as studio/jobs applies it. settle_questions' eligibility is the real one over ``R``."""
    controlled = frozenset((event_, A.SESSION) for event_ in R.events
                           if F.fact(R, event_, A.SESSION).result is ct.Result.SUPPORTED)
    pool = asking.calibration_pool(replace(R, controlled=controlled))
    items, verdicts, locations = [], {}, {}
    for number, spec in enumerate(questions, start=1):
        claim, control = f'q{number}', f'q{number}n'
        items.append(SimpleNamespace(role='question', spec=spec, claim=claim, control=control, controls=(control,)))
        for key, value in ((claim, answers[spec.key][0]), (control, answers[spec.key][1])):
            if value is not None:
                verdicts[key] = _verdict(value)
        locations[claim] = SimpleNamespace(located=True, spans=((100 * number, 100 * number + 20),), reason='')
    items.append(SimpleNamespace(role='calibration', spec=pool[0], claim='c1', control='c1n', controls=('c1n',)))
    verdicts['c1'], verdicts['c1n'] = _verdict(V.CONTRADICTS), _verdict(V.SUPPORTS)
    request = SimpleNamespace(items=tuple(items), round=1, batch=1)
    found = settle.settle_questions(request, SimpleNamespace(verdicts=verdicts, missing=(), repeated=()), locations, R,
                                    'answered')
    return settle.exclusive(list(found.questions), ()), found.health


def assess(R, *codes):
    return TA.by_code(AS.assess_facts(R, date_of_service=DAY, text=TA.TEXT, pages=(), integrity=TA.Integrity(),
                                      provider_status='succeeded', proposals=TA.corti(*codes), reference=TA.Lookup(),
                                      member=TA.ENTERED, label=lambda session_: str(session_.id)))


def run(R, answer_, codes):
    """The REAL plan of ``R``, one request settled with ``answer_(spec)`` per question, exclusivity, the fold, assess."""
    plan = asking.plan(R, ())
    records, health = settle_request(R, list(plan.specs), {spec.key: answer_(spec) for spec in plan.specs})
    R_q = F._answered(R, {'questions': records})
    return plan, records, health, R_q, assess(R, *codes), assess(R_q, *codes)


def injection_scene(purpose, part_of=None, cause=None, kind=Kind.INJECTION, place=Landmark.SIGMOID_COLON):
    """X1 colonoscopy to the cecum (E1); E2 an EMR of L1 in ``place``; E3 an act of ``kind`` at L1 with ``purpose``,
    ``part_of`` and ``cause`` (None: an empty slot)."""
    doc = EF.colonoscopy(snare=False)
    doc.lesion(1, lesion_places=[sup(place)])
    doc.act(2, Kind.EMR, places=[sup(place)], lesion=sup(L(1)))
    over = dict(places=[sup(place)], lesion=sup(L(1)), purpose=purpose)
    if part_of is not None:
        over['part_of'] = part_of
    if cause is not None:
        over['cause'] = cause
    doc.act(3, kind, **over)
    return dated(doc.build())


def two_session_exam():
    """TA.two_sessions (X1 colonoscopy: E1 exam, E2 cold snare, E3 biopsy; X2 EGD: E4 exam, E5 biopsy) with E2's session,
    date relation and performer claimed but their checks failed (three F1 questions whose true answer releases), and E6
    an examination done today in the documenting clinician's entry whose SESSION and PERFORMER are not stated."""
    doc = TA.two_sessions()
    doc.events[E(2)] = {**doc.events[E(2)], A.SESSION: (EF.unres(X(1), GEOM),), A.DATE_RELATION: (EF.unres(EF.ON, GEOM),),
                        A.PERFORMER: (EF.unres(EF.TEAM, GEOM),)}
    doc.event(6, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), session=F.SILENT, date=sup(EF.ON),
              entry=sup(EF.DC))
    return dated(doc.build())


def biopsy_scene(session_fact=None, third=False):
    """A colonoscopy X1 (E1, to the cecum) and an EGD X2 (E4, to the second portion) in one encounter - with ``third``,
    a flexible sigmoidoscopy X3 too (E8) - and E7 a cold-forceps biopsy of its own nodule L3 (no place filed) whose
    session is ``session_fact`` (default: pass 1 DOUBTED between X2 and X1)."""
    doc = EF.colonoscopy(snare=False)
    doc.session(2, ct.SessionKind.EGD, reached=[sup(ct.Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(4, session=X(2))
    if third:
        doc.session(3, ct.SessionKind.FLEX_SIG, reached=[sup(ct.Extent.SIGMOID_COLON)])
        doc.exam(8, session=X(3))
    doc.lesion(3, multiplicity=sup(ct.Multiplicity.SINGLE))
    doc.act(7, Kind.BIOPSY, session=session_fact if session_fact is not None else EF.doubted(X(2), X(1)),
            lesion=sup(L(3)), device=sup(ct.Device.COLD_FORCEPS))
    return dated(doc.build())


MINIMAL = dict(purpose=EF.doubted(P.HEMOSTASIS, P.LIFT_FOR_RESECTION), part_of=EF.neg(E(2)),
               cause=sup(C.PRE_EXISTING_LESION))
THREE = dict(purpose=EF.doubted(P.LIFT_FOR_RESECTION, P.HEMOSTASIS), part_of=EF.neg(E(2)),
             cause=sup(C.PRE_EXISTING_LESION))
INJECTION_CODES = (('45381', 3), ('45382', 3), ('45390', 2))
BIOPSY_CODES = (('45380', 7), ('43239', 7))
OPPOSITE = {V.SUPPORTS: V.CONTRADICTS, V.CONTRADICTS: V.SUPPORTS, V.UNCLEAR: V.UNCLEAR}


def purpose_answers(rival, hemostasis=(V.SUPPORTS, V.CONTRADICTS)):
    """"done for hemostasis" ``hemostasis`` (default: supported, its negation contradicted); "not done for lifting tissue"
    ``rival`` (its control the opposite); every other question in the holding direction."""
    def answer_(spec):
        if spec.attribute is A.PURPOSE and spec.value == P.HEMOSTASIS.value and not spec.negated:
            return hemostasis
        if spec.form == 'fact.lift.not':
            return rival if isinstance(rival, tuple) else (rival, OPPOSITE[rival])
        return V.CONTRADICTS, V.SUPPORTS
    return answer_


def record_of(records, form, value=None, subject=None, negated=None):
    for record in records:
        if (record['form'] == form and (value is None or record['value'] == value)
                and (subject is None or record['subjects'] == [subject])
                and (negated is None or record['negated'] is negated)):
            return record
    raise AssertionError((form, value, subject, negated))


class L2C1PurposeSlotTests(SimpleTestCase):
    """L2C-1 (high), the finding's own input at the engine level: E3's purpose claimed hemostasis with a doubt reading a
    lift; the plan asks "done for hemostasis" and "not done for lifting tissue for a resection" of the one purpose slot.
    By the scene E3 LIFTED the lesion: Fable answers hemostasis wrongly but consistently, and "not lift" RIGHTLY (claim
    contradicted: it was a lift). int5 read the contradicted "not lift" as agreeing with hemostasis: 45382 READY."""

    def test_the_finding_a_contradicted_negation_of_another_value_holds_the_value(self) -> None:
        plan, records, health, _R_q, base, after = run(injection_scene(**MINIMAL), purpose_answers(V.CONTRADICTS),
                                                       INJECTION_CODES)
        self.assertEqual(sorted((s.form, s.value, s.negated) for s in plan.specs),
                         [('fact.lift.not', 'lift_for_resection', True), ('fact.purpose', 'hemostasis', False)])
        self.assertEqual(health['refused'], [])
        hemostasis = record_of(records, 'fact.purpose', 'hemostasis')
        self.assertEqual((hemostasis['result'], hemostasis['reasons']), CONFLICT)  # int5: ('supported', [])
        self.assertIsNot(base['45382'].status, Outcome.READY)
        self.assertIsNot(after['45382'].status, Outcome.READY)  # int5: READY on a lifting injection

    def test_the_three_proposition_filing(self) -> None:
        # pass 1 claimed the lift, read hemostasis: hemostasis S/C (wrong), the lift C/S (wrong), "not lift" C/S (right)
        _plan, records, health, _R_q, base, after = run(injection_scene(**THREE), purpose_answers(V.CONTRADICTS),
                                                        INJECTION_CODES)
        self.assertEqual(health['refused'], [])
        self.assertEqual(record_of(records, 'fact.purpose', 'hemostasis')['result'], 'unresolved')
        self.assertIsNot(after['45382'].status, Outcome.READY)  # int5: READY on two wrong answers and one right

    def test_the_session_slot_twin(self) -> None:
        # E6's session: F2 "X2" S/C (wrong), G1 "not X2" C/S (wrong), F2 "X1" C/S (wrong), G1 "not X1" C/S (RIGHT: E6 is
        # X1's examination); E2's three F1 questions released (true)
        def answer_(spec):
            if spec.subjects != ('E6',):
                return V.SUPPORTS, V.CONTRADICTS
            if spec.attribute is A.SESSION and spec.value == 'X2' and not spec.negated:
                return V.SUPPORTS, V.CONTRADICTS
            return V.CONTRADICTS, V.SUPPORTS
        _plan, records, health, R_q, base, after = run(two_session_exam(), answer_,
                                                       (('45385', 2), ('45380', 3), ('43239', 5)))
        self.assertEqual(health['refused'], [])
        x2 = record_of(records, 'fact.session', 'X2', 'E6', False)
        self.assertEqual((x2['result'], x2['reasons']), CONFLICT)  # int5: supported - E6 dropped from X1
        self.assertIn(E(6), evaluate.examinations(R_q, X(1)))
        self.assertIsNot(base['45385'].status, Outcome.READY)
        self.assertIsNot(after['45385'].status, Outcome.READY)  # int5: READY

    def test_the_rival_unclear_still_holds_and_the_consistent_world_is_the_one_that_releases(self) -> None:
        """The boundary the table draws: "not lift" UNCLEAR holds (as on int5); "not lift" SUPPORTED with its exact
        negation contradicted - the answer "the slot is hemostasis" implies - is the ONE rival answer that lets
        hemostasis stand (int5 held it and released the contradicting one: the inversion, now the right way round)."""
        _plan, records, _health, _R_q, _base, unclear = run(injection_scene(**MINIMAL), purpose_answers(V.UNCLEAR),
                                                            INJECTION_CODES)
        self.assertEqual(record_of(records, 'fact.purpose', 'hemostasis')['result'], 'unresolved')
        self.assertIsNot(unclear['45382'].status, Outcome.READY)
        _plan, records, health, R_q, _base, consistent = run(injection_scene(**MINIMAL), purpose_answers(V.SUPPORTS),
                                                             INJECTION_CODES)
        self.assertEqual(health['refused'], [])
        hemostasis = record_of(records, 'fact.purpose', 'hemostasis')
        self.assertEqual((hemostasis['result'], hemostasis['reasons']), SUPPORTED)
        # the negation is held by D324 (2)'s hold side (a negation stands only beside rejected propositions); the value
        # it agrees with is established, and the fold reads the value
        self.assertEqual(record_of(records, 'fact.lift.not')['result'], 'unresolved')
        self.assertTrue(F.holds(F.fact(R_q, E(3), A.PURPOSE), P.HEMOSTASIS))
        self.assertIs(consistent['45382'].status, Outcome.READY)


class L2C2IncoherentRivalTests(SimpleTestCase):
    """L2C-2 (high), engine level: a colonoscopy X1 and an EGD X2; E7 a biopsy of its own nodule whose session pass 1
    doubted (X2 | X1); the plan asks X1 and X2 (F3). X1 answered supported / contradicted (WRONG: a gastric biopsy). int5
    read X2's record by its claim alone: X2 answered contradicts / contradicts (incoherent) counted as rejected - 45380
    READY. Each rival pattern below holds X1 but the coherent rejection (claim contradicted, control supported)."""

    def answer(self, x2):
        def answer_(spec):
            if spec.attribute is A.SESSION and spec.subjects == ('E7',) and spec.value == 'X1' and not spec.negated:
                return V.SUPPORTS, V.CONTRADICTS
            if spec.attribute is A.SESSION and spec.subjects == ('E7',) and spec.value == 'X2' and not spec.negated:
                return x2
            return V.CONTRADICTS, V.SUPPORTS
        return answer_

    def test_the_finding_and_every_incoherent_or_open_rival_hold_x1(self) -> None:
        rivals = {'C/C (the finding)': (V.CONTRADICTS, V.CONTRADICTS), 'C/U': (V.CONTRADICTS, V.UNCLEAR),
                  'C/- (control missing)': (V.CONTRADICTS, None), 'S/S': (V.SUPPORTS, V.SUPPORTS),
                  'U/C': (V.UNCLEAR, V.CONTRADICTS), 'U/U': (V.UNCLEAR, V.UNCLEAR), '-/S': (None, V.SUPPORTS),
                  '-/-': (None, None), 'S/C (both values)': (V.SUPPORTS, V.CONTRADICTS),
                  'U/S': (V.UNCLEAR, V.SUPPORTS)}
        for name, rival in rivals.items():
            with self.subTest(rival=name):
                plan, records, health, _R_q, base, after = run(biopsy_scene(), self.answer(rival), BIOPSY_CODES)
                self.assertEqual(sorted((s.subjects, s.value, s.negated) for s in plan.specs if s.subjects == ('E7',)),
                                 [(('E7',), 'X1', False), (('E7',), 'X2', False)])
                self.assertEqual(health['refused'], [])
                x1 = record_of(records, 'fact.session', 'X1', 'E7')
                self.assertEqual((x1['result'], x1['reasons']), CONFLICT, name)  # int5 C/C, C/U, C/-: supported
                self.assertIsNot(base['45380'].status, Outcome.READY)
                self.assertIsNot(after['45380'].status, Outcome.READY, name)

    def test_the_coherent_rejection_lets_the_value_stand(self) -> None:
        # the boundary: X2 rejected on both members ("E7 was done during X2" false, its negation true) - X1 stands
        _plan, records, health, R_q, _base, after = run(biopsy_scene(), self.answer((V.CONTRADICTS, V.SUPPORTS)),
                                                        BIOPSY_CODES)
        self.assertEqual(health['refused'], [])
        self.assertEqual(record_of(records, 'fact.session', 'X1', 'E7')['result'], 'supported')
        self.assertTrue(F.holds(F.fact(R_q, E(7), A.SESSION), X(1)))
        self.assertIs(after['45380'].status, Outcome.READY)


# --- R3C-L1-1: a sentence telling both procedures (the L1 lens's verifier probe v01, Part S) -------------------------------


def both_procedures_scene():
    """A colonoscopy X1 (E1 exam, E2 cold snare of a rectal lesion: 45385) and an EGD X2 (E4 exam, E5 antral biopsy:
    43239); E9 an examination performed today in the documenting clinician's entry - "Upper endoscopy and colonoscopy were
    performed at this sitting." - its performer silent, its session claimed X2 and unresolved for appraisal:missing with
    X1 an option (C2a: pass 2 gave no verdict on the claim or its control)."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(ct.Extent.CECUM)])
    doc.exam(1)
    doc.lesion(1, lesion_places=[sup(Landmark.RECTUM)])
    doc.act(2, Kind.SNARE, places=[sup(Landmark.RECTUM)], lesion=sup(L(1)), device=sup(ct.Device.COLD_SNARE))
    doc.session(2, ct.SessionKind.EGD, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(ct.Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(4, session=X(2))
    doc.act(5, Kind.BIOPSY, session=X(2), places=[sup(Landmark.GASTRIC_ANTRUM)])
    doc.event(9, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED),
              session=EF.unres(X(2), ct.Reason.APPRAISAL_MISSING, options=(X(1),)), date=sup(EF.ON), entry=sup(EF.DC))
    return dated(doc.build())


def stored(spec, pair, proof_=True):
    """A record as settle_questions stores one of an answered, healthy request: ``pair`` (claim, control) verdicts;
    the claim supported with its control contradicted and ``proof_`` located is established."""
    claim, control = pair
    if claim == S_ and control == C_ and proof_:
        result, reasons = 'supported', []
    elif claim == S_:
        reasons = ['proof_unlocated'] if control == C_ else (
            ['question_control_missing'] if control is None else ['question_incoherent'])
        result = 'unresolved'
    else:
        result = 'unresolved'
        reasons = [{C_: 'question_contradicts', U_: 'question_unclear', None: 'question_missing'}[claim]]
    return {'id': f'q-{spec.key}', 'family': spec.family.value, 'form': spec.form, 'subjects': list(spec.subjects),
            'attribute': spec.attribute.value if spec.attribute else None, 'value': spec.value,
            'unlisted': asking.unlisted_index(spec.subjects), 'negated': spec.negated, 'result': result,
            'reasons': reasons, 'verdicts': {'claim': claim, 'control': control},
            'proof': [{'start': 900, 'end': 930}] if result == 'supported' else [], 'held_by_answer': (claim, control)
            == REJECTED_PAIR}


class R3C1SessionSlotTests(SimpleTestCase):
    """R3C-L1-1 (high), engine level: the REAL planner over both_procedures_scene asks of E9's session G1 "not during X1",
    G1 "not during X2" and C2a "during X2". By the words E9 was done during BOTH sessions: both G1 claims contradicted,
    "during X2" supported. int5 counted "not X1" contradicted as agreeing with X2: E9 ruled out of X1 and 45385 READY,
    against Fable's own answer that E9 was done during X1."""

    def setUp(self) -> None:
        self.R = both_procedures_scene()
        self.plan = asking.plan(self.R, ())
        self.specs = {('not ' if s.negated else '') + s.value: s for s in self.plan.specs
                      if s.subjects == ('E9',) and s.attribute is A.SESSION}

    def walk(self, pattern):
        records = settle.exclusive([stored(self.specs[key], pair) for key, pair in pattern.items()])
        R_q = F._answered(self.R, {'questions': records})
        return records, R_q, TA.by_code(TA.run(R_q, ('45385', 2)))['45385']

    def test_the_plan_asks_both_negations_and_the_claimed_value(self) -> None:
        self.assertEqual(sorted(self.specs), ['X2', 'not X1', 'not X2'])

    def test_the_by_words_answers_hold_45385(self) -> None:
        records, R_q, found = self.walk({'not X1': REJECTED_PAIR, 'not X2': REJECTED_PAIR, 'X2': AFFIRMED_PAIR})
        x2 = next(record for record in records if record['value'] == 'X2' and not record['negated'])
        self.assertEqual((x2['result'], x2['reasons']), CONFLICT)  # int5: supported
        self.assertIn(E(9), evaluate.examinations(R_q, X(1)))  # int5: examinations(X1) == (E1,)
        self.assertIsNot(found.status, Outcome.READY)  # int5: READY

    def test_the_consistent_answers_release_and_one_wrong_negation_holds(self) -> None:
        # Fable: E9 not during X1, during X2 (and "not during X2" false) - consistent; the table establishes X2
        records, R_q, found = self.walk({'not X1': AFFIRMED_PAIR, 'not X2': REJECTED_PAIR, 'X2': AFFIRMED_PAIR})
        self.assertEqual(next(r for r in records if r['value'] == 'X2' and not r['negated'])['result'], 'supported')
        self.assertTrue(F.holds(F.fact(R_q, E(9), A.SESSION), X(2)))
        self.assertNotIn(E(9), evaluate.examinations(R_q, X(1)))
        # "not during X2" answered supported too (incoherent with "during X2"): nothing stands
        records, _R_q, found = self.walk({'not X1': AFFIRMED_PAIR, 'not X2': AFFIRMED_PAIR, 'X2': AFFIRMED_PAIR})
        self.assertEqual({r['result'] for r in records}, {'unresolved'})
        self.assertIsNot(found.status, Outcome.READY)

    def test_the_purpose_slot_twin_lift_scene(self) -> None:
        """The verifier's Part P: the injection's purpose doubted (hemostasis, lift); "not lift" held (it WAS a lift)
        beside hemostasis released gave 45382 READY on int5."""
        R = injection_scene(**MINIMAL)
        plan = asking.plan(R, ())
        specs = {('not ' if s.negated else '') + s.value: s for s in plan.specs
                 if s.subjects == ('E3',) and s.attribute is A.PURPOSE}
        records = settle.exclusive([stored(specs['not lift_for_resection'], REJECTED_PAIR),
                                    stored(specs['hemostasis'], AFFIRMED_PAIR)])
        R_q = F._answered(R, {'questions': records})
        self.assertIsNot(TA.by_code(TA.run(R_q, ('45382', 3)))['45382'].status, Outcome.READY)


# --- L4R-1: the K1-masked purpose scene through the product's builder, reader, locator and settle (test_l4r_findings) ---

L4R_TEXT = ('Colonoscopy report.\n'
            'The colonoscope was advanced to the cecum.\n'
            'A 20 mm sessile polyp in the sigmoid colon was removed by EMR.\n'
            'Dilute epinephrine was injected into the base of the polyp.\n')


def l4r_scene():
    R = injection_scene(purpose=EF.doubted(P.HEMOSTASIS, P.LIFT_FOR_RESECTION), part_of=EF.neg(E(2)),
                        cause=sup(C.PRE_EXISTING_LESION))
    return dataclasses.replace(R, controlled=frozenset({(E(1), A.DATE_RELATION), (E(1), A.PERFORMER),
                                                         (E(2), A.DATE_RELATION), (E(2), A.PERFORMER),
                                                         (E(2), A.ENTRY)}))


def l4r_stub():
    units, at = [], 0
    for number, line in enumerate(L4R_TEXT.split('\n')[:4], start=1):
        start = L4R_TEXT.index(line, at)
        units.append({'id': f'S{number}', 'start': start, 'end': start + len(line)})
        at = start + len(line)
    cards = [ct.Card('A1', ct.CardType.ACT, ('S2',), None, None), ct.Card('A2', ct.CardType.ACT, ('S3',), None, None),
             ct.Card('A3', ct.CardType.ACT, ('S4',), None, None), ct.Card('X1', ct.CardType.SESSION, ('S2',), None, None),
             ct.Card('L1', ct.CardType.LESION, ('S3',), None, None)]
    objects = {'A1': ('event', 'E1'), 'A2': ('event', 'E2'), 'A3': ('event', 'E3'), 'X1': ('session', 'X1'),
               'L1': ('lesion', 'L1')}
    built = SimpleNamespace(framed='<<<DOCUMENT-0000000000000000 BEGIN>>>\nsynthetic\n<<<DOCUMENT-0000000000000000 END>>>',
                            claim_set=SimpleNamespace(cards=tuple(cards), objects=objects))
    return built, {'units': units, 'events': [], 'sessions': [], 'sections': [], 'unlisted': []}


def l4r_run(hemostasis: bool, not_a_lift: bool):
    """The plan, partition, request builder, reader, locator and settle (real eligibility) of l4r_scene; a released
    member quotes the start of each required passage; every other member in the holding direction."""
    R = l4r_scene()
    plan = asking.plan(R, ())
    requests = asking.partition(plan.specs, asking.calibration_pool(R), 1)
    built, view = l4r_stub()
    records = []
    for number, request_plan in enumerate(requests):
        question = QC.build_question_request_fable(built, L4R_TEXT, (), view, request_plan, 1, number + 1)
        verdicts = []
        for item in question.items:
            hold = (('contradicts', []), ('supports', []))
            quotes = [L4R_TEXT[found.ranges[0][0]:min(found.ranges[0][1], found.ranges[0][0] + 40)].strip()
                      for found in item.required] if item.role == 'question' else []
            if item.role == 'calibration':
                pair = hold
            elif item.spec.form == 'fact.purpose' and item.spec.value == 'hemostasis':
                pair = (('supports', quotes), ('contradicts', [])) if hemostasis else hold
            elif item.spec.form == 'fact.lift.not':
                pair = (('supports', quotes), ('contradicts', [])) if not_a_lift else hold
            else:
                pair = hold
            for claim_id, (verdict_, quoted) in zip((item.claim, item.control), pair):
                verdicts.append({'claim': claim_id, 'verdict': verdict_, 'attached': 'yes', 'qualifiers': [],
                                 'evidence': list(item.cited[:1]), 'quotes': list(quoted)})
        cited = {}
        for item in question.items:
            cited[item.claim] = cited[item.control] = item.cited
        read = appraise_read.read_questions(json.dumps({'verdicts': verdicts, 'unlisted': []}), question.claim_ids,
                                            cited, 4)
        locations = {item.claim: proof.locate(L4R_TEXT, item.required, item.optional, read.verdicts[item.claim].quotes,
                                              item.alternatives) for item in question.items}
        settled_ = settle.settle_questions(question, read, locations, R, 'answered')
        assert settled_.health['refused'] == [], settled_.health
        records.extend(settled_.questions)
    after = settle.exclusive(records)
    status = {found.code: found.status for found in TP.assessed(F._answered(R, {'questions': after}),
                                                                INJECTION_CODES).codes}
    return plan, after, status


class L4R1Tests(SimpleTestCase):
    """L4R-1 (high): through the product's request builder, reader, locator and settle - hemostasis supported (its
    proof located) beside "not done to lift" REJECTED (its exact negation "done to lift" supported) affirmed both
    readings and released 45382 on int5; the consistent sets were held."""

    def test_the_plan(self) -> None:
        plan, _after, _status = l4r_run(True, False)
        self.assertEqual([spec.key for spec in plan.specs], ['Q-FACT|fact.lift.not|E3|purpose|lift_for_resection|not',
                                                             'Q-FACT|fact.purpose|E3|purpose|hemostasis|'])

    def test_answers_affirming_hemostasis_and_a_lift_hold_the_slot(self) -> None:
        _plan, after, status = l4r_run(True, False)
        purpose = {(r['form'], r['value']): (r['result'], r['reasons']) for r in after}
        self.assertEqual(purpose[('fact.purpose', 'hemostasis')], CONFLICT)  # int5: ('supported', [])
        self.assertIsNot(status['45382'], Outcome.READY)  # int5: READY

    def test_the_consistent_hemostasis_set_releases_and_the_lift_set_holds(self) -> None:
        # hemostasis supported, "not done to lift" supported: the table's own pattern (int5 held it: question_conflict)
        _plan, after, status = l4r_run(True, True)
        purpose = {(r['form'], r['value']): (r['result'], r['reasons']) for r in after}
        self.assertEqual(purpose[('fact.purpose', 'hemostasis')], SUPPORTED)
        self.assertIs(status['45382'], Outcome.READY)
        # a lift affirmed, hemostasis rejected: nothing established, 45382 held
        _plan, _after, status = l4r_run(False, False)
        self.assertIsNot(status['45382'], Outcome.READY)


# --- the findings END TO END (studio/jobs: extract ... question ... assess, the production connector's exchanges scripted) -

L2C_TEXT = ('SYNTHETIC COLONOSCOPY REPORT\n'                                                           # S1
            'Date of service: 03/14/2031\n'                                                            # S2
            'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                            # S3
            '\n'
            'Findings: The colonoscope was advanced to the cecum.\n'                                   # S4
            'A 20 mm flat lesion was found in the sigmoid colon.\n'                                    # S5
            'The lesion was removed by endoscopic mucosal resection.\n'                                # S6
            'Dilute epinephrine was injected beneath the lesion to lift it; that injection was separate from the '
            'resection.\n')                                                                            # S7
L2C_INJECTION = 'Dilute epinephrine was injected beneath the lesion to lift it'
L2C_EMR = 'The lesion was removed by endoscopic mucosal resection.'


def l2c_pass1():
    """Pass 1 (the L2 lens's test_l2c_pipeline): X1 (E1), the EMR E2 of L1 in the sigmoid colon, and the injection E3 at
    L1 - part_of negated E2 (S7's 'separate from the resection'), cause pre_existing_lesion, purpose CLAIMED hemostasis
    with a purpose doubt (basis unclear) reading lift_for_resection."""
    def build():
        e3 = dict(session=[fact('X1', src(['S7']))],
                  target__lesion=[fact('L1', src(['S7'], 'the lesion'))],
                  target__places=[fact('sigmoid_colon', src(['S5'], 'sigmoid colon'))],
                  part_of=[fact('E2', src(['S7'], 'separate from the resection'), state='negated')],
                  cause=[fact('pre_existing_lesion', src(['S7'], 'beneath the lesion'))],
                  purpose=[fact('hemostasis', src(['S7'], 'Dilute epinephrine'))])
        doubts = [doubt('purpose', ['E3'], ['S7'], 'unclear', ['lift_for_resection'])]
        return colonoscopy(
            L2C_TEXT,
            event('E2', ['S6'], 'endoscopic mucosal resection', 'was removed', 'emr',
                  session=[fact('X1', src(['S6']))], target__lesion=[fact('L1', src(['S6'], 'The lesion'))],
                  target__places=[fact('sigmoid_colon', src(['S5'], 'sigmoid colon'))]),
            event('E3', ['S7'], 'injected', 'was injected', 'injection', **e3),
            lesions=[lesion('L1', src(['S5'], 'A 20 mm flat lesion'),
                            multiplicity=[fact('single', src(['S5'], 'A 20 mm flat lesion'))],
                            places=[fact('sigmoid_colon', src(['S5'], 'sigmoid colon'))])],
            doubts=doubts)
    return build


def l2c_responder(log, lift_not):
    """The question request's answer over the request the stage built: "done for hemostasis" - claim SUPPORTS (wrong by
    the words) with the note's words of each required passage as its quotes, control contradicts; "not done for lifting
    tissue" - claim ``lift_not``, control its opposite; every other question unclear both ways; the calibration item
    answered RIGHT."""
    opposite = {'contradicts': 'supports', 'supports': 'contradicts', 'unclear': 'unclear'}

    def respond(sha, question):
        text = question.request.contexts[0]
        verdicts = []
        for item in question.items:
            if item.role == 'calibration':
                pairs = [(item.claim, 'contradicts', []), (item.control, 'supports', [])]
            else:
                spec = item.spec
                log.append((spec.form, spec.value, spec.negated))
                passages = list(item.required) or list(item.alternatives[:1])
                quotes = [found for found in (TQS.oracle_quote(text, passage) for passage in passages) if found]
                if spec.attribute is A.PURPOSE and spec.value == 'hemostasis' and not spec.negated:
                    pairs = [(item.claim, 'supports', quotes), (item.control, 'contradicts', [])]
                elif spec.form == 'fact.lift.not':
                    pairs = [(item.claim, lift_not, quotes if lift_not == 'supports' else []),
                             (item.control, opposite[lift_not], [])]
                else:
                    pairs = [(item.claim, 'unclear', []), (item.control, 'unclear', [])]
            for claim_id, value, quotes_ in pairs:
                verdicts.append({'claim': claim_id, 'verdict': value, 'attached': 'yes', 'qualifiers': [],
                                 'evidence': list(item.cited[:1]), 'quotes': quotes_})
        verdicts.sort(key=lambda node: int(node['claim'][1:]))
        return TJ.answered(TJ.body({'verdicts': verdicts, 'unlisted': []}))
    return respond


class L2C1PipelineTests(TQS.QuestionCase):
    """L2C-1 END TO END (the L2 lens's ExclusivityInversionPipelineTests): by the note's words the injection LIFTED the
    lesion; Fable answers "done for hemostasis" wrong but consistently, with located quotes, and "not done for lifting"
    right (claim contradicted). int5: hemostasis established, 45382 'ready'."""

    def setUp(self):
        super().setUp()
        self.provider = TJ.FakeProvider([('45381', L2C_INJECTION), ('45382', L2C_INJECTION), ('45390', L2C_EMR)])

    def run_document(self, lift_not):
        log = []
        answers = {**TJ.ANSWERS, L2C_TEXT: l2c_pass1()}
        interpreter = TQS.QuestionInterpreter(answers, oracle=TQS.leaving(), built=self.built,
                                              question_script=[l2c_responder(log, lift_not) for _ in range(6)])
        patcher = mock.patch.object(fable_adapter, 'get_interpreter_v2', return_value=interpreter)
        patcher.start()
        self.addCleanup(patcher.stop)
        encounter, revision = self.upload(L2C_TEXT)
        self.drain()
        encounter.refresh_from_db()
        inventory = models.EventInventory.objects.get(revision=revision)
        statuses = {proposal.code: proposal.status for proposal in encounter.current_assessment.proposals.all()}
        return {'records': inventory.events.get('questions', []), 'log': log, 'statuses': statuses,
                'health': inventory.verification.get('question_health')}

    def test_the_right_rival_answer_holds_the_wrong_value(self):
        found = self.run_document('contradicts')
        self.assertIn(('fact.lift.not', 'lift_for_resection', True), found['log'])
        self.assertEqual([entry['refused'] for entry in found['health']], [[]])
        hemostasis = record_of(found['records'], 'fact.purpose', 'hemostasis')
        self.assertEqual((hemostasis['result'], hemostasis['reasons']), CONFLICT)  # int5: supported, proof [263, 373]
        self.assertNotEqual(found['statuses']['45382'], 'ready')  # int5: 'ready'

    def test_the_rival_answered_unclear_holds(self):
        found = self.run_document('unclear')
        self.assertEqual(record_of(found['records'], 'fact.purpose', 'hemostasis')['result'], 'unresolved')
        self.assertNotEqual(found['statuses']['45382'], 'ready')


class L2C2PipelineTests(TRCC.VerifyCase):
    """L2C-2 END TO END, on the claims lane's own L4-1 pipeline scene (four gastric biopsies E3-E6 whose session pass 1
    doubted X1|X2; every answer right but E6:X1, answered WRONG consistently; E6:X2 alone in request 2) with E6:X2's right
    answer turned INCOHERENT: its claim contradicted while its exact negation stays contradicted. int5: E6:X1 supported,
    45380 'ready'."""

    @staticmethod
    def rows_with_claim_contradicted(original):
        def rows(question, text, weaken=None, breach=False):
            if weaken is None or weaken[1] != 'claim_contradicted':
                return original(question, text, weaken, breach)
            data = original(question, text, None, breach)
            claims_ = {item.claim for item in question.items if item.role != 'calibration'
                       and TRCC.spec_of(item) == weaken[0]}
            for node in data['verdicts']:
                if node['claim'] in claims_:
                    node['verdict'], node['quotes'] = 'contradicts', []
            return data
        return rows

    def test_the_rivals_claim_contradicted_beside_its_negation_contradicted_holds(self):
        with mock.patch.object(TRCC, 'verdict_rows', self.rows_with_claim_contradicted(TRCC.verdict_rows)):
            out = self.walk(weaken=(TRCC.LAST_X2, 'claim_contradicted'))
        self.assertEqual(self.last(out), [('X1', 'unresolved', ['question_conflict']),
                                          ('X2', 'unresolved', ['question_contradicts'])])  # int5: X1 supported
        self.assertEqual(out['statuses']['45380'], 'needs_clarification')  # int5: 'ready'

    def test_the_rivals_claim_unclear_holds_as_before(self):
        out = self.walk(weaken=(TRCC.LAST_X2, 'claim_unclear'))
        self.assertEqual(out['statuses']['45380'], 'needs_clarification')


R3C_TEXT = ('SYNTHETIC BIDIRECTIONAL ENDOSCOPY REPORT R3D\n'                       # S1
            'Date of service: 03/14/2031\n'                                       # S2
            'Endoscopist: Corvin Ashdale, MD (fictional)\n'                       # S3
            '\n'
            'Procedures: Upper endoscopy and colonoscopy were performed at this sitting.\n'   # S4 (E9)
            'Colonoscopy: The colonoscope was advanced to the cecum.\n'           # S5 (E1, X1)
            'A 4 mm polyp in the rectum was removed with a cold snare.\n'         # S6 (E2)
            'Upper endoscopy: The gastroscope was advanced to the duodenum.\n'    # S7 (E4, X2)
            'Cold forceps biopsies of the gastric antrum were taken.\n')          # S8 (E5)
R3C_SNARE = 'A 4 mm polyp in the rectum was removed with a cold snare.'
R3C_BIOPSY = 'Cold forceps biopsies of the gastric antrum were taken.'


def r3c_pass1():
    """Pass 1 (the L1 lens's test_l1r3c_attack): a colonoscopy X1 (E1) with a cold-snare removal E2, an EGD X2 (E4) with
    an antral biopsy E5, and E9 - the one sentence telling both procedures - an examination whose session pass 1 claimed
    X2 and whose performer a doubt leaves open."""
    return answer(
        sections=[opening(), labelled('N1', 'S4', 'Procedures:', 'procedure'),
                  labelled('N2', 'S5', 'Colonoscopy:', 'procedure'),
                  labelled('N3', 'S7', 'Upper endoscopy:', 'procedure')],
        sessions=[session('X1', fact('colonoscopy', src(['S5'], 'colonoscope')), examination=[fact('E1', src(['S5']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('cecum', src(['S5'], 'advanced to the cecum'))]),
                  session('X2', fact('egd', src(['S7'], 'gastroscope')), examination=[fact('E4', src(['S7']))],
                          encounter=[fact('this_encounter', frame(['S2']))],
                          reached=[fact('duodenum', src(['S7'], 'advanced to the duodenum'))])],
        events=[
            event('E9', ['S4'], 'Upper endoscopy and colonoscopy', 'were performed', 'examination',
                  session=[fact('X2', src(['S4']))]),
            event('E1', ['S5'], 'colonoscope', 'was advanced', 'examination', session=[fact('X1', src(['S5']))]),
            event('E2', ['S6'], 'cold snare', 'was removed', 'snare', session=[fact('X1', src(['S6']))],
                  target__places=[fact('rectum', src(['S6'], 'rectum'))],
                  technique__device=[fact('cold_snare', src(['S6'], 'cold snare'))]),
            event('E4', ['S7'], 'gastroscope', 'was advanced', 'examination', session=[fact('X2', src(['S7']))]),
            event('E5', ['S8'], 'biopsies', 'were taken', 'biopsy', session=[fact('X2', src(['S8']))],
                  target__places=[fact('gastric_antrum', src(['S8'], 'gastric antrum'))],
                  technique__device=[fact('cold_forceps', src(['S8'], 'Cold forceps'))])],
        doubts=[doubt('performer', ['E9'], ['S4'], 'unclear', readings=['documenting_team', 'other_clinician'])])


def leaving_claim_and_control(keys, claims_only=()):
    """A faithful pass 2 with NO verdict for each fact claim of ``keys`` (object, attribute) AND its contrary control (C2a,
    the unrejected control's value an option), and with no verdict for the claim alone of each of ``claims_only``."""
    def oracle(claim, role, claim_set):
        missing = set()
        for item in claim_set.appraised:
            if (item.key.object, item.key.attribute) in keys:
                missing.add(item.claim)
                if item.control is not None:
                    missing.add(item.control)
            elif (item.key.object, item.key.attribute) in claims_only:
                missing.add(item.claim)
        return None if claim.id in missing else faithful(claim, role, claim_set)
    return oracle


def by_words(g1_pattern):
    """The question answers by the note's words for E9 (one sentence telling BOTH procedures): "E9 was not done during
    session X1/X2" false (claim contradicts, control supports) unless ``g1_pattern`` == 'release'; "E9 was done during
    session X2" true; E9's performer in doubt (holding); the calibration item answered right."""
    def rows(question, text):
        out = []
        for item in question.items:
            spec = item.spec
            if item.role == 'calibration':
                pairs = [(item.claim, 'contradicts', []), (item.control, 'supports', [])]
            else:
                release = ((spec.form == 'fact.session.not' and g1_pattern == 'release')
                           or (spec.attribute in (A.SESSION, A.TECHNIQUE_DEVICE) and not spec.negated))
                if release:
                    passages = list(item.required) or list(item.alternatives[:1])
                    quotes = [found for found in (TQS.oracle_quote(text, passage) for passage in passages) if found]
                    pairs = [(item.claim, 'supports', quotes), (item.control, 'contradicts', [])]
                else:
                    pairs = [(item.claim, 'contradicts', []), (item.control, 'supports', [])]
            for claim_id, value, quotes_ in pairs:
                out.append({'claim': claim_id, 'verdict': value, 'attached': 'yes', 'qualifiers': [],
                            'evidence': list(item.cited[:1]), 'quotes': quotes_})
        out.sort(key=lambda node: int(node['claim'][1:]))
        return {'verdicts': out, 'unlisted': []}
    return rows


class ByWordsInterpreter(TQS.QuestionInterpreter):
    def __init__(self, *args, rows=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rows = rows

    def _exchange(self, body_dict, deadline, purpose):
        if fable_adapter.request_kind(body_dict)[0] != fable_adapter.QUESTION:
            return super()._exchange(body_dict, deadline, purpose)
        sha = request_sha256(body_dict)
        question = self.built[sha]
        with self.guard:
            self.question_sent.append(sha)
        return TJ.answered(TJ.body(self.rows(question, question.request.contexts[0])))


class R3C1PipelineTests(TQS.QuestionCase):
    """R3C-L1-1 through the whole pipeline (the L1 lens's ExclusiveNegationContradictedTests): upload, both passes, the
    QUESTION stage with the real planner, partition, draw, request builder, reader, locator, settle and exclusivity, the
    fold, assess."""

    def setUp(self):
        super().setUp()
        self.provider = FakeProvider([('45385', R3C_SNARE), ('43239', R3C_BIOPSY)])

    def walk(self, g1_pattern):
        interpreter = ByWordsInterpreter({**TQS.ANSWERS, R3C_TEXT: r3c_pass1}, oracle=leaving_claim_and_control(
            (('E9', A.SESSION),), claims_only=(('E1', A.SESSION), ('E4', A.SESSION), ('E2', A.TECHNIQUE_DEVICE),
                                                      ('E5', A.TECHNIQUE_DEVICE))),
            built=self.built, rows=by_words(g1_pattern))
        patcher = mock.patch.object(fable_adapter, 'get_interpreter_v2', return_value=interpreter)
        patcher.start()
        try:
            encounter, revision = self.upload(R3C_TEXT)
            self.drain()
        finally:
            patcher.stop()
        encounter.refresh_from_db()
        inventory = models.EventInventory.objects.get(revision=revision)
        records = [(r['form'], r['value'], r['negated'], r['result'], r['reasons'])
                   for r in inventory.events.get('questions') or []]
        health = [h.get('refused') for h in inventory.verification.get('question_health') or []]
        statuses = {p.code: p.status for p in encounter.current_assessment.proposals.all()}
        return {'records': records, 'health': health, 'statuses': statuses}

    def test_the_by_words_answers_hold_45385(self):
        held = self.walk('hold')
        self.assertIn(('fact.session.not', 'X1', True, 'unresolved', ['question_contradicts']), held['records'])
        self.assertIn(('fact.session', 'X2', False, 'unresolved', ['question_conflict']), held['records'])  # int5: supported
        self.assertEqual(held['health'], [[]] * len(held['health']))
        self.assertEqual(held['statuses']['45385'], 'needs_clarification')  # int5: 'ready'
        self.assertEqual(held['statuses']['43239'], 'needs_clarification')

    def test_both_negations_released_beside_the_value_hold_too(self):
        # "not X1" and "not X2" both supported beside "during X2": "not X2" contradicts the value - nothing stands
        released = self.walk('release')
        self.assertEqual(released['statuses']['45385'], 'needs_clarification')


# --- THE EXHAUSTIVE CENSUS (DECISIONS D325 (1)) ------------------------------------------------------------------------------
#
# A slot of two or three values (E3's session at X1, X2[, X3]); every set of asked propositions - each value positive,
# negated, both, or neither (289 configurations a value: none; one proposition with each of 16 verdict pairs, positive or
# negated; both with 16 x 16); every claim and control verdict pair from supported, contradicted, unclear and missing.
# Each record is the one the REAL request builder, reader, locator and settle_questions write for that verdict pair
# (``census_records``), relabelled only in its value. The oracle is the table written out here (``table``), independent of
# settle's code: v is established exactly when its own pair is (supported, contradicted) and every other proposition's
# pair is the one "the slot is v" implies; a negation exactly when every other proposition is rejected (D324 (2)'s hold
# side, read on both members). Three values are enumerated up to a relabelling of the values (every multiset of three
# configurations: 4,064,785), with the relabelling itself measured (``test_relabelling_and_order``); two values in full.

PAIRS = tuple(itertools.product(VERDICTS, VERDICTS))
CONFIGS = ([()] + [((negated, pair),) for negated in (False, True) for pair in PAIRS]
           + [((False, positive), (True, negative)) for positive in PAIRS for negative in PAIRS])


def table(own, other):
    """D325 (1)'s truth table, written out: the (claim, control) pair "the slot is ``own``" implies of another
    proposition ``other`` of its slot - each (value index, negated). Beside a value, another value's negation is TRUE;
    every other proposition (another value, the value's own negation, and anything beside a negation) is FALSE."""
    (value, negated), (other_value, other_negated) = own, other
    return AFFIRMED_PAIR if (not negated and other_negated and other_value != value) else REJECTED_PAIR


_CENSUS: dict = {}


def census_records() -> dict:
    """{(negated, (claim, control)): the record settle_questions writes} - ONE question about E3's session at X1, positive
    ("This act was done during session X1.") or G1's negation, beside the one calibration item answered right; a member
    with no verdict has no row at all; a supported claim quotes each named object's own words (located)."""
    if _CENSUS:
        return _CENSUS
    for negated in (False, True):
        spec = TRCC.at_session('X1', negated=negated)
        for pair in PAIRS:
            built = TRCC.request(spec)
            rows = []
            for item in built.items:
                members = (((item.claim, C_), (item.control, S_)) if item.role == 'calibration'
                           else ((item.claim, pair[0]), (item.control, pair[1])))
                for claim_id, verdict_ in members:
                    if verdict_ is None:
                        continue
                    quotes = (TRCC.quotes_of(spec) if item.role == 'question' and claim_id == item.claim
                              and verdict_ == S_ else [])
                    rows.append({'claim': claim_id, 'verdict': verdict_, 'attached': 'yes', 'qualifiers': [],
                                 'evidence': list(item.cited[:1]), 'quotes': quotes})
            rows.sort(key=lambda node: int(node['claim'][1:]))
            found = TRP.settled(built, json.dumps({'verdicts': rows, 'unlisted': []}))
            assert found.health['refused'] == [], found.health
            (record,) = found.questions
            _CENSUS[(negated, pair)] = record
    return _CENSUS


class _Census:
    """The census over ``n`` values: each value's configuration records (relabelled) and the oracle's per-configuration
    agreement with every target proposition."""

    def __init__(self, n: int, subject: str = 'E3') -> None:
        base = census_records()
        self.n = n
        self.targets = [(value, negated) for value in range(n) for negated in (False, True)]
        self.records = [[[{**base[(negated, pair)], 'value': f'X{value + 1}', 'subjects': [subject],
                           'id': f'q.{value}.{int(negated)}'} for negated, pair in config] for config in CONFIGS]
                        for value in range(n)]
        self.match = [[{target: all(pair == table(target, (value, negated)) for negated, pair in config
                                    if (value, negated) != target) for target in self.targets} for config in CONFIGS]
                      for value in range(n)]

    def expected(self, assignment) -> tuple:
        """The oracle: for each record of ``assignment`` (in order), whether it is established after exclusivity."""
        out = []
        for value, index in enumerate(assignment):
            for negated, pair in CONFIGS[index]:
                target = (value, negated)
                out.append(pair == AFFIRMED_PAIR and all(self.match[other][at][target]
                                                         for other, at in enumerate(assignment)))
        return tuple(out)

    def listed(self, assignment) -> list:
        records = []
        for value, index in enumerate(assignment):
            records += self.records[value][index]
        return records

    def propositions(self, assignment) -> list:
        return [(value, negated) for value, index in enumerate(assignment) for negated, _pair in CONFIGS[index]]

    def established(self, assignment) -> frozenset:
        """The established propositions exclusivity leaves (the REAL settle.exclusive), checked against the oracle."""
        records = self.listed(assignment)
        out = settle.exclusive(records)
        got = tuple(record['result'] == 'supported' for record in out)
        if got != self.expected(assignment):
            raise AssertionError(('census', assignment, [(CONFIGS[i], ) for i in assignment], got,
                                  self.expected(assignment)))
        for before, after in zip(records, out):  # a record not established before is returned as it is
            if before['result'] != 'supported' and after is not before:
                raise AssertionError(('a record not established was changed', assignment, before))
        found = frozenset(prop for prop, flag in zip(self.propositions(assignment), got) if flag)
        if len(found) > 1:  # one proposition of a slot at most: so the fold reads one answer of it, never two
            raise AssertionError(('two propositions of one slot established', assignment, found))
        return found


def single_changes(assignment):
    """Every assignment one member's verdict away from ``assignment``, with the changed proposition and whether the
    change goes from a pattern some table accepts (AFFIRMED or REJECTED) to one none accepts (D325 (1)'s "from matching
    to not matching")."""
    for value, index in enumerate(assignment):
        config = CONFIGS[index]
        for position, (negated, pair) in enumerate(config):
            for member in (0, 1):
                for verdict_ in VERDICTS:
                    if verdict_ == pair[member]:
                        continue
                    changed = (verdict_, pair[1]) if member == 0 else (pair[0], verdict_)
                    new_config = tuple((n_, changed if p == position else pr)
                                       for p, (n_, pr) in enumerate(config))
                    new = list(assignment)
                    new[value] = _CONFIG_INDEX[new_config]
                    away = pair in (AFFIRMED_PAIR, REJECTED_PAIR) and changed not in (AFFIRMED_PAIR, REJECTED_PAIR)
                    yield tuple(new), (value, negated), away


_CONFIG_INDEX = {config: index for index, config in enumerate(CONFIGS)}


class TruthTableCensusTests(SimpleTestCase):
    """THE EXHAUSTIVE CENSUS of D325 (1) (module comment above), at the level of settle.exclusive over the records
    settle_questions writes, and at the fold and READY level on scenes of two and three sessions."""

    def test_the_census_records_are_settles_own(self) -> None:
        base = census_records()
        self.assertEqual(len(base), 32)
        for (negated, pair), record in base.items():
            claim, control = pair
            expected = ('supported' if pair == AFFIRMED_PAIR else 'unresolved')
            self.assertEqual(record['result'], expected, (negated, pair))
            self.assertEqual(record['verdicts'], {'claim': claim, 'control': control})
            self.assertIs(record['negated'], negated)
        self.assertEqual(base[(False, (S_, S_))]['reasons'], ['question_incoherent'])
        self.assertEqual(base[(False, (S_, M_))]['reasons'], ['question_control_missing'])
        self.assertEqual(base[(True, (C_, C_))]['reasons'], ['question_contradicts'])
        self.assertEqual(base[(True, (M_, S_))]['reasons'], ['question_missing'])
        self.assertEqual(base[(False, (U_, C_))]['reasons'], ['question_unclear'])
        self.assertEqual(len(CONFIGS), 289)

    def test_two_values_every_assignment(self) -> None:
        census = _Census(2)
        seen = {}
        for assignment in itertools.product(range(len(CONFIGS)), repeat=2):
            seen[assignment] = census.established(assignment)
            records = census.listed(assignment)
            once = settle.exclusive(records)
            self.assertEqual(settle.exclusive(once), once)  # idempotent (the stage re-runs it after every round)
        self.assertEqual(len(seen), 289 ** 2)
        # the table is not vacuous: each kind of record is established somewhere, and held somewhere
        established = set().union(*seen.values())
        self.assertEqual(established, {(0, False), (0, True), (1, False), (1, True)})
        # the findings' own shapes, by the census: v beside "not w" contradicted (L2C-1) or w incoherent (L2C-2) holds
        v, not_w_rejected = ((False, AFFIRMED_PAIR),), ((True, REJECTED_PAIR),)
        self.assertEqual(seen[(_CONFIG_INDEX[v], _CONFIG_INDEX[not_w_rejected])], frozenset())
        self.assertEqual(seen[(_CONFIG_INDEX[v], _CONFIG_INDEX[((False, (C_, C_)),)])], frozenset())
        self.assertEqual(seen[(_CONFIG_INDEX[v], _CONFIG_INDEX[((True, AFFIRMED_PAIR),)])], frozenset({(0, False)}))
        self.assertEqual(seen[(_CONFIG_INDEX[v], _CONFIG_INDEX[((False, REJECTED_PAIR),)])], frozenset({(0, False)}))
        _TWO_VALUES.update(seen)

    def test_two_values_no_single_change_from_matching_to_not_matching_grows(self) -> None:
        """P-MONO-Q at exclusivity (f.2): over every assignment of the two-value census and every single verdict change
        from a pattern some table accepts to one none accepts, the established set never gains a proposition."""
        if not _TWO_VALUES:
            self.test_two_values_every_assignment()
        changes = 0
        for assignment, before in _TWO_VALUES.items():
            for new, changed, away in single_changes(assignment):
                if not away:
                    continue
                changes += 1
                after = _TWO_VALUES[new]
                self.assertLessEqual(after, before, (assignment, new))
                self.assertNotIn(changed, after)
        # every record whose pair a table accepts (AFFIRMED or REJECTED: 68 of a value's 289 configurations' records,
        # in each of the other value's 289) has six such changes, three per member
        self.assertEqual(changes, 2 * 68 * 289 * 6)

    def test_relabelling_and_order(self) -> None:
        """The three-value census enumerates multisets of configurations: exclusivity reads values only by equality, so
        a relabelling of the values relabels its result - measured on every two-value assignment (swapped) and on
        every 61st three-value multiset under all six relabellings; and the records' order changes nothing."""
        census = _Census(2)
        for assignment in itertools.product(range(len(CONFIGS)), repeat=2):
            swapped = census.established(assignment[::-1])
            self.assertEqual(census.established(assignment), frozenset((1 - value, negated)
                                                                       for value, negated in swapped))
            records = census.listed(assignment)
            reverse = settle.exclusive(records[::-1])[::-1]
            self.assertEqual([r['result'] for r in reverse], [r['result'] for r in settle.exclusive(records)])
        census = _Census(3)
        for number, assignment in enumerate(itertools.combinations_with_replacement(range(len(CONFIGS)), 3)):
            if number % 61:
                continue
            found = census.established(assignment)
            for order in itertools.permutations(range(3)):
                moved = tuple(assignment[order[value]] for value in range(3))
                relabelled = census.established(moved)
                self.assertEqual(frozenset((order[value], negated) for value, negated in relabelled), found)

    def test_three_values_every_multiset(self) -> None:
        census = _Census(3)
        count = 0
        established = set()
        for assignment in itertools.combinations_with_replacement(range(len(CONFIGS)), 3):
            established |= census.established(assignment)
            count += 1
        self.assertEqual(count, 4_064_785)  # multisets of three of the 289 configurations: C(291, 3)
        self.assertEqual(established, set(census.targets))

    def test_three_values_matching_assignments_and_their_single_changes(self) -> None:
        """For every set of asked propositions of three values and every established target in it, the assignment where
        every proposition has the pair the target's table names: the target is established, alone; and every single
        verdict change from matching to not matching holds it and establishes nothing else."""
        census = _Census(3)
        checked = 0
        for forms in itertools.product(('neither', 'positive', 'negated', 'both'), repeat=3):
            asked = [(value, negated) for value, form in enumerate(forms)
                     for negated in ((False,) if form == 'positive' else (True,) if form == 'negated'
                                     else (False, True) if form == 'both' else ())]
            for target in asked:
                config = []
                for value in range(3):
                    own = tuple((negated, AFFIRMED_PAIR if (value, negated) == target else table(target, (value, negated)))
                                for negated in (False, True) if (value, negated) in asked)
                    config.append(_CONFIG_INDEX[own])
                assignment = tuple(config)
                self.assertEqual(census.established(assignment), frozenset({target}), (forms, target))
                for new, _changed, away in single_changes(assignment):
                    if away:
                        checked += 1
                        self.assertEqual(census.established(new), frozenset(), (assignment, new))
        self.assertGreater(checked, 1_000)

    def test_the_fold_and_ready_level(self) -> None:
        """At the fold and READY level (scenes of two and three sessions: E7 a biopsy whose session pass 1 doubted): the
        slot's value is SUPPORTED on R_q exactly when a positive record is established; a negation never establishes a
        value - every set of established negations, folded together, leaves the session unestablished; and READY never
        shrinks when an established record is added, so no single change from matching to not matching (which only
        removes established records: the census above) grows READY."""
        codes = {2: (('45380', 7), ('43239', 7)), 3: (('45380', 7), ('43239', 7), ('45331', 7))}
        for n in (2, 3):
            readings = [X(2), X(1)] + ([X(3)] if n == 3 else [])
            R = biopsy_scene(session_fact=EF.doubted(*readings), third=n == 3)
            census = _Census(n, subject='E7')
            props = [(value, negated) for value in range(n) for negated in (False, True)]
            ready = {}
            for size in range(0, len(props) + 1):
                for chosen in itertools.combinations(props, size):
                    records = []
                    for value, negated in chosen:
                        records += census.records[value][_CONFIG_INDEX[((negated, AFFIRMED_PAIR),)]]
                    R_q = F._answered(R, {'questions': records})
                    found = F.fact(R_q, E(7), A.SESSION)
                    positives = [value for value, negated in chosen if not negated]
                    if not positives:
                        self.assertIsNot(found.result, ct.Result.SUPPORTED, (n, chosen))  # never a value from negations
                    elif len(chosen) == 1:
                        self.assertTrue(F.holds(found, X(positives[0] + 1)), (n, chosen))
                    ready[frozenset(chosen)] = frozenset(
                        item.code for item in TP.assessed(R_q, codes[n]).codes if item.status is Outcome.READY)
            for chosen, found in ready.items():
                for smaller, below in ready.items():
                    if smaller <= chosen and len(chosen) <= 1:
                        self.assertLessEqual(below, found, (n, smaller, chosen))
            self.assertEqual(ready[frozenset()], frozenset())  # nothing READY without an answer
            self.assertIn('45380', ready[frozenset({(0, False)})])  # X1 established: the colonoscopy's code


_TWO_VALUES: dict = {}


# --- the class beyond the findings' forms, and the boundaries (the real builder, reader, locator and settle) ---------------

CARDS3 = (('X2', ct.CardType.SESSION, ('S1',)), ('X3', ct.CardType.SESSION, ('S4',)),
          ('L2', ct.CardType.LESION, ('S4',)))
WORDS3 = {**TRCC.WORDS, 'X3': 'No biopsies of the rectum were taken', 'L2': 'No biopsies of the rectum were taken'}


def request3(*specs, calibration=(TRP.K1,), seed: str = 'seed') -> QC.QuestionRequest:
    """A question request over test_r3_probe's stub (cards A1-A4 for E1-E4, X1, L1) with sessions X2 (S1) and X3 (S4)
    and a second lesion L2 (S4) carded too."""
    return TRP.stub_request(list(specs), list(calibration), seed=seed, extra_cards=CARDS3)


def _row(claim_id, member, item, quotes):
    """One verdict row: ``member`` a verdict string, None (no row), or a dict of the row's fields (verdict, qualifiers,
    attached)."""
    if member is None:
        return None
    member = {'verdict': member} if isinstance(member, str) else member
    return {'claim': claim_id, 'verdict': member['verdict'], 'attached': member.get('attached', 'yes'),
            'qualifiers': list(member.get('qualifiers', ())), 'evidence': list(item.cited[:1]),
            'quotes': list(quotes) if member['verdict'] == S_ else []}


def settled3(built, answers: dict, breach: bool = False, outcome: str = 'answered', unlocated=()) -> list:
    """The stored question records of ``built`` as settle_questions writes them: ``answers`` maps a spec key to its
    (claim member, control member) - every other question in the holding direction; a supported claim quotes each named
    object's own words (a paraphrase, in no passage, for the keys of ``unlocated``); ``breach`` the calibration item's
    known-false claim supported (H2); ``outcome`` a request that did not answer."""
    if outcome != 'answered':
        return list(settle.settle_questions(built, None, {}, None, outcome).questions)
    rows = []
    for item in built.items:
        if item.role == 'calibration':
            pairs = ((item.claim, S_ if breach else C_), (item.control, S_))
            quotes = []
        else:
            claim, control = answers.get(item.spec.key, (C_, S_))
            pairs = ((item.claim, claim), (item.control, control))
            quotes = ([TRCC.PARAPHRASE] if item.spec.key in unlocated
                      else [WORDS3[name] for name in item.spec.names])
        for claim_id, member in pairs:
            row = _row(claim_id, member, item, quotes if claim_id == item.claim else [])
            if row is not None:
                rows.append(row)
    rows.sort(key=lambda node: int(node['claim'][1:]))
    return list(TRP.settled(built, json.dumps({'verdicts': rows, 'unlisted': []})).questions)


def results(records) -> dict:
    return {(record['attribute'], record['value'], record['negated']): (record['result'], record['reasons'])
            for record in settle.exclusive(records)}


def spec_of(form, attribute, value, negated=False, subject='E3', names=(), census='F3'):
    return TRCC.fact_spec(form, attribute, value, negated, subject, names, census)


def session_spec(value, negated=False):
    return TRCC.at_session(value, negated=negated)


class TruthTableVariantTests(SimpleTestCase):
    """D325 (1)'s rule on forms, values, slots and weakenings beyond the findings' own, each holding or releasing exactly
    as the table says; and the boundaries it leaves alone."""

    def test_three_sessions(self) -> None:
        """A slot of three values: X1 supported beside "not X2" and "not X3" - each negation must be TRUE (supported,
        its negation contradicted); one rejected ("not X3" contradicted: it WAS X3) holds X1."""
        x1, not_x2, not_x3 = session_spec('X1'), session_spec('X2', True), session_spec('X3', True)
        first = settled3(request3(x1), {x1.key: AFFIRMED_PAIR})
        for not_x3_pair, expected in ((AFFIRMED_PAIR, SUPPORTED), (REJECTED_PAIR, CONFLICT), ((C_, C_), CONFLICT),
                                      ((S_, S_), CONFLICT)):
            with self.subTest(not_x3=not_x3_pair):
                others = settled3(request3(not_x2, not_x3, seed='b'), {not_x2.key: AFFIRMED_PAIR,
                                                                       not_x3.key: not_x3_pair})
                self.assertEqual(results(first + others)[('session', 'X1', False)], expected)
        # another value asked positively beside them: rejected stands, affirmed holds (two values)
        x3 = session_spec('X3')
        for x3_pair, expected in ((REJECTED_PAIR, SUPPORTED), (AFFIRMED_PAIR, CONFLICT), ((C_, U_), CONFLICT)):
            with self.subTest(x3=x3_pair):
                others = settled3(request3(not_x2, x3, seed='c'), {not_x2.key: AFFIRMED_PAIR, x3.key: x3_pair})
                self.assertEqual(results(first + others)[('session', 'X1', False)], expected)

    def test_the_visits_basis_another_value_domain(self) -> None:
        mdm = spec_of('fact.visit.basis', A.VISIT_BASIS, 'medical_decision_making', census='C6')
        not_time = spec_of('fact.visit.basis', A.VISIT_BASIS, 'total_time', negated=True, census='C6')
        for pair, expected in ((AFFIRMED_PAIR, SUPPORTED), (REJECTED_PAIR, CONFLICT), ((U_, C_), CONFLICT),
                               ((C_, M_), CONFLICT)):
            with self.subTest(not_total_time=pair):
                records = settled3(request3(mdm, not_time), {mdm.key: AFFIRMED_PAIR, not_time.key: pair})
                self.assertEqual(results(records)[('visit.basis', 'medical_decision_making', False)], expected)

    def test_the_target_lesion_another_slot(self) -> None:
        l1 = spec_of('fact.target.lesion', A.TARGET_LESION, 'L1')
        not_l2 = spec_of('fact.target.lesion', A.TARGET_LESION, 'L2', negated=True)
        l2 = spec_of('fact.target.lesion', A.TARGET_LESION, 'L2')
        for others, expected in (({not_l2.key: AFFIRMED_PAIR}, SUPPORTED), ({not_l2.key: REJECTED_PAIR}, CONFLICT),
                                 ({l2.key: REJECTED_PAIR}, SUPPORTED), ({l2.key: (C_, C_)}, CONFLICT)):
            with self.subTest(others=others):
                specs = [l1] + [spec for spec in (not_l2, l2) if spec.key in others]
                records = settled3(request3(*specs), {l1.key: AFFIRMED_PAIR, **others})
                self.assertEqual(results(records)[('target.lesion', 'L1', False)], expected)

    def test_a_rivals_claim_is_read_as_settle_reads_a_claim(self) -> None:
        """"not w" must be SUPPORTED as settle reads a claim (attached yes, no lowering qualifier): hedged or detached it
        holds the value; approximate never lowers (D186/D224), so it agrees; its proof is not asked (a rival's own
        verdicts are what the table reads - its proof unlocated still agrees)."""
        x1, not_x2 = session_spec('X1'), session_spec('X2', True)
        cases = {'hedged': ({'verdict': S_, 'qualifiers': ['hedged']}, CONFLICT),
                 'detached': ({'verdict': S_, 'attached': 'no'}, CONFLICT),
                 'qualified verdict': ({'verdict': 'qualified', 'qualifiers': ['hedged']}, CONFLICT),
                 'approximate': ({'verdict': S_, 'qualifiers': ['approximate']}, SUPPORTED)}
        for name, (claim, expected) in cases.items():
            with self.subTest(case=name):
                records = settled3(request3(x1, not_x2), {x1.key: AFFIRMED_PAIR, not_x2.key: (claim, C_)})
                self.assertEqual(results(records)[('session', 'X1', False)], expected, name)
        records = settled3(request3(x1, not_x2), {x1.key: AFFIRMED_PAIR, not_x2.key: AFFIRMED_PAIR},
                           unlocated=(not_x2.key,))
        rival = next(record for record in records if record['negated'])
        self.assertEqual(rival['reasons'], ['proof_unlocated'])
        self.assertEqual(results(records)[('session', 'X1', False)], SUPPORTED)

    def test_a_rivals_control_is_read_as_settle_reads_a_supported_member(self) -> None:
        """"w" rejected needs its control SUPPORTED as settle reads a supported member (attached yes, no lowering
        qualifier): its negation supported with a hedge, or detached, is a qualified verdict and holds the value (settle
        writes the reading into held_by_answer, which the record keeps); approximate never lowers; the control
        contradicted or unclear holds it."""
        x1, x2 = session_spec('X1'), session_spec('X2')
        cases = {'clean': (S_, SUPPORTED), 'hedged': ({'verdict': S_, 'qualifiers': ['hedged']}, CONFLICT),
                 'detached': ({'verdict': S_, 'attached': 'no'}, CONFLICT),
                 'approximate': ({'verdict': S_, 'qualifiers': ['approximate']}, SUPPORTED),
                 'qualified verdict': ({'verdict': 'qualified', 'qualifiers': ['hedged']}, CONFLICT),
                 'unclear': (U_, CONFLICT), 'contradicts': (C_, CONFLICT)}
        for name, (control, expected) in cases.items():
            with self.subTest(control=name):
                records = settled3(request3(x1, x2), {x1.key: AFFIRMED_PAIR, x2.key: (C_, control)})
                rival = next(record for record in records if record['value'] == 'X2')
                self.assertEqual(rival['held_by_answer'], expected == SUPPORTED, name)
                self.assertEqual(results(records)[('session', 'X1', False)], expected, name)

    def test_a_verdict_counts_only_in_an_answered_healthy_request(self) -> None:
        """The matching "not w" in a request breached (H2), failed, cut at its output limit or uncalibrated (H5) holds
        the value - its verdicts do not count; the same answers in a healthy request let it stand."""
        x1, not_x2 = session_spec('X1'), session_spec('X2', True)
        first = settled3(request3(x1), {x1.key: AFFIRMED_PAIR})
        healthy = settled3(request3(not_x2, seed='b'), {not_x2.key: AFFIRMED_PAIR})
        self.assertEqual(results(first + healthy)[('session', 'X1', False)], SUPPORTED)
        for name, kwargs in (('breached', {'breach': True}), ('failed', {'outcome': 'failed'}),
                             ('too long', {'outcome': 'too_long'})):
            with self.subTest(request=name):
                rival = settled3(request3(not_x2, seed='b'), {not_x2.key: AFFIRMED_PAIR}, **kwargs)
                self.assertEqual(results(first + rival)[('session', 'X1', False)], CONFLICT, name)
        uncalibrated = settled3(request3(not_x2, calibration=(), seed='b'), {not_x2.key: AFFIRMED_PAIR})
        self.assertEqual(uncalibrated[0]['reasons'], ['question_health:uncalibrated'])
        self.assertEqual(results(first + uncalibrated)[('session', 'X1', False)], CONFLICT)

    def test_across_rounds(self) -> None:
        """Round 1 asked "not X2" and Fable said it WAS X2 (rejected); round 2's X1, answered supported, is held - the
        records of every round are read; and the next round's call reads the result the same (idempotent)."""
        x1, not_x2 = session_spec('X1'), session_spec('X2', True)
        round_1 = settled3(request3(not_x2), {not_x2.key: REJECTED_PAIR})
        round_2 = [{**record, 'round': 2, 'id': record['id'].replace('q1.', 'q2.', 1)}
                   for record in settled3(request3(x1, seed='round-2'), {x1.key: AFFIRMED_PAIR})]
        once = settle.exclusive(round_1 + round_2)
        self.assertEqual(results(round_1 + round_2)[('session', 'X1', False)], CONFLICT)
        self.assertEqual(settle.exclusive(once), once)

    def test_a_negations_rivals_are_read_on_both_members(self) -> None:
        """A negation stands only beside rejected propositions (D324 (2)'s hold side), each now read on BOTH members:
        its own value answered incoherently (claim contradicted, negation contradicted too - the same sentence answered
        both ways) holds it; rejected coherently, it stands."""
        not_x1, x1, x2 = session_spec('X1', True), session_spec('X1'), session_spec('X2')
        for rival, pair, expected in ((x1, (C_, C_), CONFLICT), (x1, (C_, U_), CONFLICT), (x1, REJECTED_PAIR, SUPPORTED),
                                      (x2, (C_, M_), CONFLICT), (x2, REJECTED_PAIR, SUPPORTED),
                                      (x2, AFFIRMED_PAIR, CONFLICT)):
            with self.subTest(rival=rival.key, pair=pair):
                records = settled3(request3(not_x1, rival), {not_x1.key: AFFIRMED_PAIR, rival.key: pair})
                self.assertEqual(results(records)[('session', 'X1', True)], expected)

    def test_the_universal_negation_reads_as_the_slots_no_value(self) -> None:
        """fact.part_link.any ("not part of another act", stored value '') says the slot holds no value: beside a named
        negation "not part of act E2" (no planned form asks one; records written as settle writes them) it stands when
        that negation is TRUE and is held when it is false (part of E2 after all); beside a named value, rejected stands."""
        universal = stored(spec_of('fact.part_link.any', A.PART_OF, '', negated=True, census='F11'), AFFIRMED_PAIR)
        named = {**universal, 'id': 'q-named', 'form': 'fact.part_link.any', 'value': 'E2'}
        for pair, expected in ((AFFIRMED_PAIR, SUPPORTED), (REJECTED_PAIR, CONFLICT), ((C_, C_), CONFLICT)):
            with self.subTest(named_negation=pair):
                other = {**named, 'verdicts': {'claim': pair[0], 'control': pair[1]},
                         'result': 'supported' if pair == AFFIRMED_PAIR else 'unresolved',
                         'reasons': [] if pair == AFFIRMED_PAIR else ['question_contradicts'],
                         'held_by_answer': pair == REJECTED_PAIR}
                self.assertEqual(results([universal, other])[('part_of', '', True)], expected)
        positive = {**named, 'negated': False, 'verdicts': {'claim': C_, 'control': S_}, 'result': 'unresolved',
                    'reasons': ['question_contradicts'], 'held_by_answer': True}
        self.assertEqual(results([universal, positive])[('part_of', '', True)], SUPPORTED)

    def test_boundaries_left_alone(self) -> None:
        # a lone proposition
        x2, x1 = session_spec('X2'), session_spec('X1')
        self.assertEqual(results(settled3(request3(x2), {x2.key: AFFIRMED_PAIR})), {('session', 'X2', False): SUPPORTED})
        # a right answer to a doubt: the rival rejected on both members - the value stands (as on int5)
        right = settled3(request3(x1), {x1.key: REJECTED_PAIR}) + settled3(request3(x2, seed='b'), {x2.key: AFFIRMED_PAIR})
        self.assertEqual(results(right)[('session', 'X2', False)], SUPPORTED)
        # both values supported: both held (as on int5)
        both = settled3(request3(x1, x2), {x1.key: AFFIRMED_PAIR, x2.key: AFFIRMED_PAIR})
        self.assertEqual(list(results(both).values()), [CONFLICT, CONFLICT])
        # ASK2-3's two negations of one slot, both supported, still hold each other (D324 (2)'s hold side)
        lift_not = spec_of('fact.lift.not', A.PURPOSE, 'lift_for_resection', True, census='F11')
        hemostasis_not = spec_of('fact.hemostasis.not', A.PURPOSE, 'hemostasis', True, census='F12')
        two = settled3(request3(lift_not, hemostasis_not), {lift_not.key: AFFIRMED_PAIR, hemostasis_not.key: AFFIRMED_PAIR})
        self.assertEqual(list(results(two).values()), [CONFLICT, CONFLICT])
        # "not X1" beside "X2" whose proof did not locate: the negation held, as D324 (2) built it (claims Q4)
        not_x1 = session_spec('X1', True)
        records = settled3(request3(not_x1, x2), {not_x1.key: AFFIRMED_PAIR, x2.key: AFFIRMED_PAIR},
                           unlocated=(x2.key,))
        self.assertEqual(results(records)[('session', 'X1', True)], CONFLICT)
        # a list attribute's members and two slots of one act are no conflict
        cecum = spec_of('fact.reached', A.REACHED, 'cecum', subject='X1', census='A3')
        ileum = spec_of('fact.reached', A.REACHED, 'terminal_ileum', subject='X1', census='A3')
        listed = settled3(request3(cecum, ileum), {cecum.key: AFFIRMED_PAIR, ileum.key: AFFIRMED_PAIR})
        self.assertEqual(settle.exclusive(listed), listed)
        purpose = spec_of('fact.purpose', A.PURPOSE, 'removal')
        apart = settled3(request3(x2, purpose), {x2.key: AFFIRMED_PAIR, purpose.key: AFFIRMED_PAIR})
        self.assertEqual(list(results(apart).values()), [SUPPORTED, SUPPORTED])
        # the other families are relations, never slots (two Q-REL answers of one act, the second incoherent)
        rel = [{'family': 'Q-REL', 'subjects': [statement, 'E3'], 'attribute': None, 'value': '', 'negated': False,
                'result': result, 'reasons': reasons, 'verdicts': verdicts, 'proof': []}
               for statement, result, reasons, verdicts in
               (('E1', 'supported', [], {'claim': S_, 'control': C_}),
                ('E4', 'unresolved', ['question_contradicts'], {'claim': C_, 'control': C_}))]
        self.assertEqual(settle.exclusive(rel), rel)


# =========================================================================================================================
# D325 (4) - EVERY QUESTION'S PASSAGES HOLD WHERE THE ASKED VALUE WAS ESTABLISHED (finding L3P-2, medium; D324 (9)'s class).
# A Q-FACT form with no frame, reach or place rule takes the asked fact's own integrity-passed sources as a REQUIRED value
# passage, named by the claim line's value field ("value at") and exempt from the heading ban as the frame's is; a value
# with no source outside the subject's card changes nothing. Through the product's request builder
# (question_claims.build_question_request_fable), reader (appraise_read.read_questions), locator (proof.locate) and settle
# (settle_questions; asking.eligible held True, as the claims lanes' own helpers do: a synthetic view has no FactSet).
# =========================================================================================================================

_PASSED = TRC._PASSED


def _span(text: str, words: str) -> dict:
    assert text.count(words) == 1, words
    at = text.index(words)
    return {'start': at, 'end': at + len(words)}


def _fact(value: str, *units: str, **extra) -> dict:
    """A stored fact record with integrity-passed sources at ``units``."""
    return {'claim': {'value': value, 'state': 'supported', 'options': [], 'qualifiers': [], 'inherited_from': None},
            'sources': [{'units': list(units)}] if units else [], **_PASSED, 'result': 'unknown', **extra}


def settled_with(built, text, quotes, k1_holding=True):
    """``built``'s question answered supports with ``quotes`` and its exact negation contradicted; the calibration item
    in the holding direction. The product's reader, locator and settle."""
    verdicts = []
    for item in built.items:
        if item.role == 'calibration':
            pairs = [(item.claim, C_ if k1_holding else S_, []), (item.control, S_, [])]
        else:
            pairs = [(item.claim, S_, list(quotes)), (item.control, C_, [])]
        for claim_id, value, found in pairs:
            verdicts.append({'claim': claim_id, 'verdict': value, 'attached': 'yes', 'qualifiers': [],
                             'evidence': list(item.cited[:1]), 'quotes': found})
    cited = {}
    for item in built.items:
        cited[item.claim] = item.cited
        cited[item.control] = item.cited
    read = appraise_read.read_questions(json.dumps({'verdicts': verdicts, 'unlisted': []}), built.claim_ids, cited,
                                        len(TRC.units_of(text)))
    assert hasattr(read, 'verdicts'), read
    locations = {item.claim: proof.locate(text, item.required, item.optional,
                                          read.verdicts[item.claim].quotes if read.verdicts.get(item.claim) else (),
                                          item.alternatives) for item in built.items}
    with mock.patch.object(asking, 'eligible', return_value=True):
        found = settle.settle_questions(built, read, locations, None)
    question = found.questions[0]
    return found.health['refused'], question['result'], question['reasons']


def _k1(event: str):
    """The request's one calibration item (DECISIONS D319): a K1 about ``event``'s date relation (a frame form)."""
    return TRC._planned(FAM.Q_FACT, 'fact.date_relation', (event,), A.DATE_RELATION, 'on_date_of_service', True,
                        kind='K1')


def _question(built):
    return next(item for item in built.items if item.role == 'question')


def _line(built, item) -> str:
    return next(line for line in built.lines if line.startswith(item.claim + ' '))


# --- the finding's own input: a visit note shaped like B-fb10 (the L3 lens's test_l3p_r3c / test_l3p_r3c_rule) -----------

VISIT = ('OFFICE VISIT AND COLONOSCOPY NOTE\n'                                            # S1  title, no start
         'Seen today in the office for follow-up of chronic reflux symptoms.\n'           # S2  E1; N1 starts at its words
         'GERD E/M: medical decision making of moderate complexity, 30 minutes.\n')       # S3  N2 (label); E1's basis source
VISIT_SECTIONS = ({'id': 'N0', 'start': {'units': []}},
                  {'id': 'N1', 'start': {'units': ['S2'], 'at': _span(VISIT, 'Seen today in the office')}},
                  {'id': 'N2', 'start': {'units': ['S3'], 'at': _span(VISIT, 'GERD E/M:')}})
VISIT_EVENTS = ({'id': 'E1', 'anchor': {'units': ['S2']},
                 'visit': {'basis': _fact('medical_decision_making', 'S3', reasons=['doubt_unclear'])}},)
VISIT_CARDS = (('A1', ct.CardType.ACT, 'event', 'E1', ('S1', 'S2')),
               ('N0', ct.CardType.SECTION, 'section', 'N0', ('S1',)), ('N1', ct.CardType.SECTION, 'section', 'N1', ('S2',)),
               ('N2', ct.CardType.SECTION, 'section', 'N2', ('S3',)))


def visit_request(value: str = 'medical_decision_making', spec=None):
    cards, objects = TRC._cards(*VISIT_CARDS)
    spec = spec or TRC._planned(FAM.Q_FACT, 'fact.visit.basis', ('E1',), A.VISIT_BASIS, value)
    built = TRC.built_request(VISIT, cards, objects, [spec], [_k1('E1')], events=VISIT_EVENTS, sections=VISIT_SECTIONS)
    return built, _question(built)


class L3P2VisitBasisTests(SimpleTestCase):
    """L3P-2 (medium), the finding's own shape (B-fb10: the visit's basis stated on a labelled line of its own, S3, pass
    1's source; E1's card S1-S2). On int5 the claim line cited S1 and S2 only: the right proof (quoting S3) was
    proof_unlocated and a hollow one (the visit's own words) established medical_decision_making and total_time alike."""

    RIGHT_ACT = 'for follow-up of chronic reflux symptoms.'  # the act's own words, past N1's start words (cut)
    RIGHT_VALUE = 'medical decision making of moderate complexity, 30 minutes.'

    def test_the_planner_gives_the_form_its_own_sources(self) -> None:
        self.assertEqual(asking.value_passage_of(A.VISIT_BASIS), 'own')
        built, item = visit_request()
        self.assertEqual(item.spec.value_passage, 'own')  # int5: ''
        self.assertIn('(about A1; names A1; cites S1, S2 and S3; value at S3; proof): ', _line(built, item))
        self.assertEqual([TRC._unit_ids_of(found, VISIT) for found in item.required], [['S1', 'S2'], ['S3']])

    def test_the_right_proof_locates_and_a_hollow_proof_does_not_for_either_value(self) -> None:
        for value in ('medical_decision_making', 'total_time'):
            built, _item = visit_request(value)
            with self.subTest(value=value):
                self.assertEqual(settled_with(built, VISIT, [self.RIGHT_ACT, self.RIGHT_VALUE]), ([], 'supported', []))
                # int5: ([], 'supported', []) - words that say nothing of how the visit's level was chosen
                self.assertEqual(settled_with(built, VISIT, [self.RIGHT_ACT]), ([], 'unresolved', ['proof_unlocated']))
                # the value's words alone leave the act's own passage without a quote
                self.assertEqual(settled_with(built, VISIT, [self.RIGHT_VALUE]), ([], 'unresolved', ['proof_unlocated']))

    def test_the_start_words_cut_is_left_as_it_was(self) -> None:
        """L3P-1 (a recorded low, not this round's): the act's passage is still cut of the part's start words - the act's
        sentence quoted from its first word, beside the value's words, is voided as on int5 (with the value's words now
        required beside it); quoted past the start words, it locates."""
        built, item = visit_request()
        whole = 'Seen today in the office for follow-up of chronic reflux symptoms.'
        self.assertEqual(TRC.located(VISIT, item, [whole, self.RIGHT_VALUE]).reason, proof.PROOF_UNLOCATED)
        self.assertTrue(TRC.located(VISIT, item, [self.RIGHT_ACT, self.RIGHT_VALUE]).located)


CLINIC = ('SYNTHETIC GI CLINIC NOTE\n'                                                   # S1
          'The patient was seen today in clinic for intermittent dysphagia.\n'           # S2  E1 (the visit)
          'Level of service: total time of 40 minutes on the date of the visit.\n')      # S3  E1's basis source
INJECTION_NOTE = ('SYNTHETIC COLONOSCOPY REPORT\n'                                       # S1
                  'A submucosal injection of saline was given at the base of the polyp.\n'   # S2  E3 (the injection)
                  'The injection lifted the polyp so that it could be removed.\n')          # S3  E3's purpose source
STENT_NOTE = ('SYNTHETIC ERCP REPORT\n'                                                  # S1
              'A 5 Fr plastic stent was placed after deep cannulation.\n'                # S2  E2 (the stent)
              'The stent was placed in the pancreatic duct to prevent pancreatitis.\n')  # S3  E2's duct source
DEVICE_NOTE = ('SYNTHETIC COLONOSCOPY REPORT\n'                                          # S1
               'A 6 mm polyp in the sigmoid colon was removed.\n'                        # S2  E2
               'A hot snare was used for the removal of that polyp.\n')                  # S3  E2's device source
SECTIONS_N0 = ({'id': 'N0', 'start': {'units': []}},)


def one_act_request(text, event, record_path, record, form, attribute, value, negated=False):
    """One act carded at S2, its stored fact ``record`` at ``record_path`` ('purpose' or 'visit.basis'), and the
    question as the planner writes it; the K1 about the act's date relation."""
    cards, objects = TRC._cards((f'A{event[1:]}', ct.CardType.ACT, 'event', event, ('S2',)),
                                ('N0', ct.CardType.SECTION, 'section', 'N0', ('S1',)))
    stored_event: dict = {'id': event}
    head, _, tail = record_path.partition('.')
    stored_event[head] = {tail: record} if tail else record
    spec = TRC._planned(FAM.Q_FACT, form, (event,), attribute, value, negated)
    built = TRC.built_request(text, cards, objects, [spec], [_k1(event)], events=(stored_event,), sections=SECTIONS_N0)
    return built, _question(built)


class L3P2OwnSentenceTests(SimpleTestCase):
    """The L3P-2 verifier's own scenes (a visit basis on its own line, a purpose and a duct stated in the sentence after the
    act's) and the L3 lens's device twin: the value's own words are now a required passage, so the right proof is
    established and the act's words alone are not."""

    CASES = (
        ('visit basis', CLINIC, 'E1', 'visit.basis', _fact('total_time', 'S3', reasons=['doubt_unclear']),
         'fact.visit.basis', A.VISIT_BASIS, ('total_time', 'medical_decision_making'),
         'seen today in clinic for intermittent dysphagia.', 'total time of 40 minutes on the date of the visit.'),
        ('purpose', INJECTION_NOTE, 'E3', 'purpose', _fact('lift_for_resection', 'S3', reasons=['unappraised']),
         'fact.purpose', A.PURPOSE, ('lift_for_resection', 'hemostasis'),
         'injection of saline was given at the base of the polyp.',
         'The injection lifted the polyp so that it could be removed.'),
        ('duct', STENT_NOTE, 'E2', 'target.duct', _fact('pancreatic', 'S3', reasons=['unappraised']),
         'fact.target.duct', A.TARGET_DUCT, ('pancreatic', 'biliary'),
         'plastic stent was placed after deep cannulation.', 'placed in the pancreatic duct to prevent pancreatitis.'),
        ('device', DEVICE_NOTE, 'E2', 'technique.device', _fact('hot_snare', 'S3', reasons=['unappraised']),
         'fact.technique.device', A.TECHNIQUE_DEVICE, ('hot_snare',),
         'polyp in the sigmoid colon was removed', 'A hot snare was used for the removal'),
    )

    def test_each_value_stated_outside_the_acts_card(self) -> None:
        for name, text, event, path, record, form, attribute, values, act_words, value_words in self.CASES:
            for value in values:
                built, item = one_act_request(text, event, path, record, form, attribute, value)
                with self.subTest(case=name, value=value):
                    self.assertIn('; value at S3; proof): ', _line(built, item))  # int5: no field, S3 not cited
                    self.assertTrue(TRC.located(text, item, [act_words, value_words]).located)  # int5: proof_unlocated
                    self.assertEqual(settled_with(built, text, [act_words, value_words]), ([], 'supported', []))
                    self.assertEqual(settled_with(built, text, [act_words]),  # int5: supported (a hollow proof)
                                     ([], 'unresolved', ['proof_unlocated']))


# --- the class beyond the finding: every Q-FACT form with no frame, reach or place rule, on one synthetic note ------------
#
# Each asked fact's pass-1 source lies OUTSIDE its subject's card (a heading line for the session, a separate sentence for
# the rest). Read by test_r3_claims.InstructionReader - the instruction read literally from what a reader sees (the card
# lines, the claim line's names, cites and value fields) - every proof the instruction permits locates, some proof is
# permitted, and settle establishes a right answer that follows it.

DOC2 = ('SYNTHETIC ENDOSCOPY NOTE R3D FOR ONE FICTIONAL PATIENT\n'                          # S1
        'COLONOSCOPY FINDINGS FROM THIS PROCEDURE TODAY AT THE CENTER:\n'                 # S2  N1's start; E3's session source
        'The colonoscope was advanced to the cecum without any difficulty.\n'            # S3  X1's card, E1 (X1's exam)
        'A 9 mm sessile polyp was seen in the sigmoid colon at 30 cm.\n'                 # S4  L1's card; E3's lesion source
        'Dilute epinephrine was injected into the base of that polyp.\n'                  # S5  E2 (the injection)
        'The injection was given only to stop the oozing from the polyp base.\n'         # S6  E2's purpose source
        'The polyp was then removed in one piece after that injection.\n'                # S7  E3 (the removal)
        'A hot snare was used for the removal of the sigmoid polyp.\n'                    # S8  E3's device source
        'The bleeding at the site came from the polyp itself before any snare.\n'        # S9  E10's cause source
        'A clip was placed on the polypectomy site at the end of the procedure.\n'       # S10 E10 (the clip)
        'The clip was placed only to close the mucosal defect after the removal.\n'      # S11 E10's purpose source
        'The clip was placed on its own and was not a step of the polyp removal.\n'      # S12 E10's part link source
        'Upper endoscopy was then performed with a standard adult gastroscope.\n'        # S13 E6's session source
        'The gastroscope was advanced to the second portion of the duodenum.\n'          # S14 X2's card, E5 (X2's exam)
        'An examination of the stomach was documented here in a short line.\n'           # S15 E6 (an examination)
        'A plastic stent was placed after deep cannulation of the papilla.\n'            # S16 E7 (the stent)
        'The stent went into the pancreatic duct to prevent pancreatitis.\n'             # S17 E7's duct source
        'An office visit for the reflux symptoms preceded the procedures.\n'             # S18 E8 (the visit)
        'Level of service: medical decision making of moderate complexity.\n'            # S19 E8's basis source
        'Dr. Ada Fictional performed the polyp removal herself in this session.\n')     # S20 P1 (a person); E3's person source
DOC2_CARDS = (('A1', ct.CardType.ACT, 'event', 'E1', ('S3',)), ('A2', ct.CardType.ACT, 'event', 'E2', ('S5',)),
              ('A3', ct.CardType.ACT, 'event', 'E3', ('S7',)), ('A5', ct.CardType.ACT, 'event', 'E5', ('S14',)),
              ('A6', ct.CardType.ACT, 'event', 'E6', ('S15',)), ('A7', ct.CardType.ACT, 'event', 'E7', ('S16',)),
              ('A8', ct.CardType.ACT, 'event', 'E8', ('S18',)), ('A10', ct.CardType.ACT, 'event', 'E10', ('S10',)),
              ('A12', ct.CardType.ACT, 'event', 'P1', ('S20',)), ('X1', ct.CardType.SESSION, 'session', 'X1', ('S3',)),
              ('X2', ct.CardType.SESSION, 'session', 'X2', ('S14',)), ('L1', ct.CardType.LESION, 'lesion', 'L1', ('S4',)))
DOC2_EVENTS = (
    {'id': 'E1'}, {'id': 'E5'},
    {'id': 'E2', 'purpose': _fact('hemostasis', 'S6', reasons=['doubt_unclear'])},
    {'id': 'E3', 'session': _fact('X1', 'S2', reasons=['geometry_section']), 'technique': {'device': _fact('hot_snare', 'S8')},
     'target': {'lesion': _fact('L1', 'S4')}, 'performer_person': _fact('P1', 'S20')},
    {'id': 'E6', 'session': _fact('X2', 'S13', reasons=['appraisal_missing'])},
    {'id': 'E7', 'target': {'duct': _fact('pancreatic', 'S17')}},
    {'id': 'E8', 'visit': {'basis': _fact('medical_decision_making', 'S19', reasons=['doubt_unclear'])}},
    {'id': 'E10', 'cause': _fact('pre_existing_lesion', 'S9'), 'purpose': _fact('closure', 'S11'),
     'part_of': {**_fact('E3', 'S12'), 'claim': {'value': 'E3', 'state': 'negated', 'options': [], 'qualifiers': [],
                                                  'inherited_from': None}}})
DOC2_SESSIONS = ({'id': 'X1', 'examination': {'claim': {'value': 'E1'}}},
                 {'id': 'X2', 'examination': {'claim': {'value': 'E5'}}})
DOC2_SECTIONS = ({'id': 'N0', 'start': {'units': []}}, {'id': 'N1', 'start': {'units': ['S2']}})
DOC2_HEADING = 'COLONOSCOPY FINDINGS FROM THIS PROCEDURE TODAY AT THE CENTER:'
DOC2_HEADINGS = (_span(DOC2, DOC2_HEADING)['start'], _span(DOC2, DOC2_HEADING)['end'])


def doc2_shapes() -> list:
    """(name, spec, the value units the line must name) - every Q-FACT form with no frame, reach or place rule the
    planner asks (and the session calibration kinds), each asked fact's source outside its subject's card."""
    QF, P = FAM.Q_FACT, TRC._planned
    return [
        ('device', P(QF, 'fact.technique.device', ('E3',), A.TECHNIQUE_DEVICE, 'hot_snare'), 'S8'),
        ('target lesion', P(QF, 'fact.target.lesion', ('E3',), A.TARGET_LESION, 'L1'), 'S4'),
        ('performer_person', P(QF, 'fact.performer_person', ('E3',), A.PERFORMER_PERSON, 'P1'), 'S20'),
        ('session, its part\'s heading line', P(QF, 'fact.session', ('E3',), A.SESSION, 'X1'), 'S2'),
        ('lift.not', P(QF, 'fact.lift.not', ('E2',), A.PURPOSE, 'lift_for_resection', True), 'S6'),
        ('hemostasis.not', P(QF, 'fact.hemostasis.not', ('E10',), A.PURPOSE, 'hemostasis', True), 'S11'),
        ('cause.not', P(QF, 'fact.cause.not', ('E10',), A.CAUSE, 'act_of_this_session', True), 'S9'),
        ('part_link.any', P(QF, 'fact.part_link.any', ('E10',), A.PART_OF, '', True), 'S12'),
        ('G1 session.not, naming the session', P(QF, 'fact.session.not', ('E6',), A.SESSION, 'X1', True,
                                                 names=('E6', 'X1')), 'S13'),
        ('duct', P(QF, 'fact.target.duct', ('E7',), A.TARGET_DUCT, 'pancreatic'), 'S17'),
        ('visit basis', P(QF, 'fact.visit.basis', ('E8',), A.VISIT_BASIS, 'medical_decision_making'), 'S19'),
        ('K1 session', P(QF, 'fact.session', ('E3',), A.SESSION, 'X1', True, names=('E3', 'X1'), kind='K1'), 'S2'),
        ('K2 session', P(QF, 'fact.session', ('E3',), A.SESSION, 'X2', names=('E3', 'X2'), kind='K2'), 'S2'),
    ]


def doc2_request(spec, events=DOC2_EVENTS):
    cards, objects = TRC._cards(*DOC2_CARDS)
    questions, calibration = ([], [spec]) if isinstance(spec, asking.CalibrationSpec) else ([spec], [_k1('E1')])
    built = TRC.built_request(DOC2, cards, objects, questions, calibration, events=events, sessions=DOC2_SESSIONS,
                              sections=DOC2_SECTIONS)
    item = next(found for found in built.items if found.spec is spec or found.spec == spec)
    return built, item, objects


def follows(built, item, objects, proof_text=None):
    """(the proofs the instruction - QC.PROOF, or ``proof_text`` - permits for ``item``, those the locator voids)."""
    reader = TRC.InstructionReader(proof_text if proof_text is not None else QC.PROOF)
    seen = TRC.seen_of(built, DOC2, (DOC2_HEADINGS,))
    proofs = reader.proofs(seen, item, TRC.groups_of(item.spec, objects), TRC.Marks())
    return proofs, [quotes for quotes in proofs if not TRC.located(DOC2, item, quotes).located]


class ValueSourceFormTests(SimpleTestCase):
    """D325 (4) on every form it reaches (beyond the finding's visit basis): the value field names the asked fact's own
    source units, the locator requires a quote there, the literal reader of PROOF permits proofs and every one it permits
    locates, and settle establishes a right answer that follows the instruction."""

    def test_every_form_names_and_requires_its_own_source(self) -> None:
        for name, spec, units in doc2_shapes():
            built, item, objects = doc2_request(spec)
            with self.subTest(shape=name):
                self.assertEqual(spec.value_passage, 'own')
                line = _line(built, item)
                self.assertIn(f'; value at {units}; proof): ', line)
                self.assertEqual(TRC._unit_ids_of(item.required[-1], DOC2), [units])
                proofs, voided = follows(built, item, objects)
                self.assertTrue(proofs, name)
                self.assertEqual(voided, [], name)

    def test_a_right_answer_that_follows_the_instruction_is_established(self) -> None:
        for name, spec, _units in doc2_shapes():
            if isinstance(spec, asking.CalibrationSpec):
                continue
            built, item, objects = doc2_request(spec)
            with self.subTest(shape=name):
                proofs, _voided = follows(built, item, objects)
                self.assertEqual(settled_with(built, DOC2, proofs[0]), ([], 'supported', []), name)
                # the named objects' own words alone (no quote of the value's source) are not enough
                bare = proofs[0][:len(item.required) - 1]
                self.assertEqual(settled_with(built, DOC2, bare)[1:], ('unresolved', ['proof_unlocated']), name)

    def test_the_value_units_may_hold_a_headings_words(self) -> None:
        """E3's session source is its part's heading line (S2, N1's start): exempt from the heading ban as the frame's
        value passage is - the value set is uncut, and, with that heading listed by another card (the lesion's: the ban
        then reads it), the reader still permits the heading's words as the value passage and every such proof
        locates."""
        spec = TRC._planned(FAM.Q_FACT, 'fact.session', ('E3',), A.SESSION, 'X1')
        built, item, _objects = doc2_request(spec)
        start = DOC2.index(DOC2_HEADING)
        self.assertEqual(item.required[-1].ranges, ((start, start + len(DOC2_HEADING)),))
        self.assertTrue(TRC.located(DOC2, item, ['polyp was then removed in one piece', DOC2_HEADING]).located)
        cards, objects = TRC._cards(*(card if card[0] != 'L1' else ('L1', ct.CardType.LESION, 'lesion', 'L1', ('S2', 'S4'))
                                      for card in DOC2_CARDS))
        built = TRC.built_request(DOC2, cards, objects, [spec], [_k1('E1')], events=DOC2_EVENTS,
                                  sessions=DOC2_SESSIONS, sections=DOC2_SECTIONS)
        item = _question(built)
        proofs, voided = follows(built, item, objects)
        self.assertTrue(any(any(word in quote for quote in quotes for word in ('FINDINGS', 'CENTER')) for quotes in proofs))
        self.assertEqual(voided, [])

    def test_the_session_clause_is_load_bearing(self) -> None:
        """A claim naming a session with value units (G1; a session's K1 or K2 item): the instruction leaves the value
        units out of the session's passage. Read with the session clause in its r3c form ('d324', int5's text, which
        took every other cited unit no other card lists as the session's), the reader permits proofs the locator voids
        (the session's quote taken from the value units)."""
        old = ' '.join(QC.PROOF.split()).replace(TRC._CLAUSE_FORMS['session']['repaired'],
                                                TRC._CLAUSE_FORMS['session']['d324'])
        self.assertEqual(TRC.InstructionReader(old).forms['session'], 'd324')
        named_session = [(name, spec) for name, spec, _units in doc2_shapes() if len(spec.names) == 2]
        self.assertEqual(len(named_session), 3)
        for name, spec in named_session:
            built, item, objects = doc2_request(spec)
            with self.subTest(shape=name):
                self.assertTrue(follows(built, item, objects, old)[1], name)  # some permitted proof voided
                self.assertEqual(follows(built, item, objects)[1], [], name)  # the shipped wording: none


class ValueSourceBoundaryTests(SimpleTestCase):
    """What D325 (4) leaves alone: a value whose sources lie inside the subject's card (the line and the passages are
    int5's byte for byte), a source whose integrity check failed, a silent fact, and the frame, reach and place forms."""

    def lines_and_passages(self, spec, events):
        built, item, _objects = doc2_request(spec, events)
        int5_built, int5_item, _ = doc2_request(dataclasses.replace(spec, value_passage=''), events)
        return (_line(built, item), item.required, item.cited), (_line(int5_built, int5_item), int5_item.required,
                                                                 int5_item.cited)

    def test_a_source_inside_the_subjects_card_changes_nothing(self) -> None:
        inside = tuple({**event, 'technique': {'device': _fact('hot_snare', 'S7')}} if event['id'] == 'E3' else event
                       for event in DOC2_EVENTS)
        spec = TRC._planned(FAM.Q_FACT, 'fact.technique.device', ('E3',), A.TECHNIQUE_DEVICE, 'hot_snare')
        mine, int5 = self.lines_and_passages(spec, inside)
        self.assertEqual(mine, int5)
        self.assertNotIn('value at', mine[0])

    def test_an_integrity_failed_source_and_a_silent_fact_change_nothing(self) -> None:
        failed = {**_fact('hot_snare', 'S8'), 'checks': {'integrity': 'failed'}, 'reasons': ['words_not_in_units']}
        for name, record in (('integrity failed', failed), ('silent', {**_fact('', ), 'claim': {'value': '',
                                                                                               'state': None}})):
            events = tuple({**event, 'technique': {'device': record}} if event['id'] == 'E3' else event
                           for event in DOC2_EVENTS)
            spec = TRC._planned(FAM.Q_FACT, 'fact.technique.device', ('E3',), A.TECHNIQUE_DEVICE, 'hot_snare')
            with self.subTest(case=name):
                mine, int5 = self.lines_and_passages(spec, events)
                self.assertEqual(mine, int5)

    def test_the_frame_reach_and_place_forms_keep_their_own_rules(self) -> None:
        self.assertEqual({attribute: asking.value_passage_of(attribute)
                          for attribute in (A.ENTRY, A.DATE_RELATION, A.PERFORMER, A.REACHED, A.REACHED_ANATOMY,
                                            A.STATIONS, A.TARGET_PLACES)},
                         {A.ENTRY: 'frame', A.DATE_RELATION: 'frame', A.PERFORMER: 'frame', A.REACHED: 'source',
                          A.REACHED_ANATOMY: 'source', A.STATIONS: 'source', A.TARGET_PLACES: 'section_head'})
        self.assertEqual({attribute for attribute in asking.FACT_ATTRIBUTES if asking.value_passage_of(attribute) == 'own'},
                         {A.PERFORMER_PERSON, A.SESSION, A.TARGET_LESION, A.TECHNIQUE_DEVICE, A.PURPOSE, A.TARGET_DUCT,
                          A.VISIT_BASIS, A.PART_OF, A.CAUSE})
        # a frame claim whose value passage is empty still says so ("no unit"); a frame claim is untouched by 'own'
        spec = TRC._planned(FAM.Q_FACT, 'fact.performer', ('E3',), A.PERFORMER, 'documenting_team')
        built, item, _objects = doc2_request(spec)
        self.assertIn('; value at no unit; proof): ', _line(built, item))

    def test_the_planner_writes_own_where_the_rule_reaches(self) -> None:
        """The real planner (asking.plan) over L2C-1's FactSet: both purpose questions carry the 'own' value passage; the
        calibration pool's session items too (rendered as their questions are, DECISIONS D324 (9)'s b.9 reading)."""
        plan = asking.plan(injection_scene(**MINIMAL), ())
        self.assertEqual({spec.form: spec.value_passage for spec in plan.specs},
                         {'fact.lift.not': 'own', 'fact.purpose': 'own'})
        # a colonoscopy X1 of this encounter and an EGD X2 of a separate one (DECISIONS D317 (4): K2's sessions apart),
        # every established session CONTROLLED (the pool's source): K1 and K2 session items, both rendered 'own'
        doc = EF.Doc()
        doc.session(1, ct.SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                    reached=[sup(ct.Extent.CECUM)])
        doc.exam(1)
        doc.lesion(1, lesion_places=[sup(Landmark.RECTUM)])
        doc.act(2, Kind.SNARE, places=[sup(Landmark.RECTUM)], lesion=sup(L(1)), device=sup(ct.Device.COLD_SNARE))
        doc.session(2, ct.SessionKind.EGD, encounter=sup(ct.EncounterRelation.SEPARATE_ENCOUNTER),
                    reached=[sup(ct.Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(4, session=X(2))
        R = dated(doc.build())
        controlled = frozenset((event_, A.SESSION) for event_ in R.events
                               if F.fact(R, event_, A.SESSION).result is ct.Result.SUPPORTED)
        pool = asking.calibration_pool(replace(R, controlled=controlled))
        sessions = {(item.kind.value, item.value_passage) for item in pool if item.attribute is A.SESSION}
        self.assertEqual(sessions, {('K1', 'own'), ('K2', 'own')})  # int5: ('K1', ''), ('K2', '')


class ValueSourcePinTests(SimpleTestCase):
    """The instruction's pin moved by its owner (question_claims.pins): PROOF's session clause leaves the claim's value
    units out of a session's passage. APPRAISAL_INSTRUCTIONS_Q_SHA256_V3 6a798464... -> 35fb05df...; the templates' pin
    (the claim line, VALUE_FIELD, VALUE_NONE) unchanged."""

    def test_the_pins(self) -> None:
        found = QC.pins()
        self.assertEqual(found['APPRAISAL_INSTRUCTIONS_Q_SHA256_V3'],
                         '35fb05df356d56b165979b44e5bd7381e0f7b36205a5d432e41d50fe439e7ef7')
        self.assertEqual(found['QUESTION_TEMPLATES_SHA256_V3'],
                         'a79716271cfb7cdfc4627e15db149bac820af1f164f4151a21697ddf24144a94')
        text = ' '.join(QC.PROOF.split())
        self.assertEqual(text.count("every other unit the claim cites that no other card it names lists and that is not "
                                    "one of the claim's value units;"), 1)
