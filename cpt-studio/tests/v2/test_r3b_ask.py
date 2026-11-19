"""Round r3's build, lane "ask" (DECISIONS D320, D323): engine/asking.py and engine/whatif.py as the build ships them -
the rulings D317-D319 and the port's findings F1, F3, F4, L1 and O1 on the planner. Every input is SYNTHETIC (invented
ids, spans and facts; tests/v2/evaluate_fixtures' builders, tests/v2/test_lesion_pair's fictional note): no document
is read and nothing is sent. Red on the port (base): each class pins a rule the port's planner does not have.

- OneItemTests (D319, item a): exactly ONE calibration item a request (calibration_count is 1; CALIBRATION_MIN and
  CALIBRATION_POOL_MIN 1), negative-form wherever the pool has one, the first asked family's where it has one.
- BoundTests (D318 (2) and its first addendum, item b): QUESTION_BOUND from the four measured requests (t_q 5,936),
  rounded by a PAIR: 18 claims, 8 questions and their one item a request.
- MemberLineTests (D317 (1), item c): no item whose truth may turn on a statement that gives another performer or author
  to the acts on one side of it - read from the fact pass's representation (a section whose performer or owner reads
  another; pass 2's kept unlisted entry beyond it), never a word of the note.
- KindsAndOccasionsTests (D317 (4), item d): PROCEDURE_SESSION_KINDS IS catalogue.ENDOSCOPIC_FAMILIES; K2's two
  sessions of established different dates or separate encounters.
- G1StatusTests (D315 (6), item e): G1 only of an examination established performed or planned (the D315 checker's
  ck4_g1 case: an ATTEMPTED examination is never asked; nor one whose status is in doubt).
- CoversK3Tests (D312, item f): the killing test of K3b - a covers K3 (pass 1's claimed pair) is drawn only beside a
  K1, so with one item a request it is never drawn.
- TypedReadingTests (D323 F3, item g): FINAL-V2 5.7 measure 4's two guards find nothing in asking and whatif; every
  typed reading equals the prototype's word reading on every label it can meet.
- InvariantTests (D323 F4, item h): a request without its item is refused at plan time (UncalibratedRequest), never
  returned; the killing test of M2 through facts.factset of a STORED row.
- ContextRowTests (D323 L1, item i): R6's member-context row read by its requirement through the Enum.
- NoLesionQuestionTests (D323 O1, item j): the planner asks no lesion-pair question.
- OnLesionPlanTests (D323 F1, item k): Q-ONLESION asked only where the SAME it serves rests on the statement's lesions'
  places alone - the port's probes q01/q04 scenes (D316's QB, RFL2-1) ask nothing; P4's shape asks.
- NarrowestFormTests (D318 (3) and its second addendum; the repair pass's RA-4): every question is handed the NARROWEST
  form exact for its subjects' descriptions, derived by contract/question_claims (one source: relation_form for Q-REL) -
  never "does not concern" where a narrower exact form exists; the planner's own spec reaches the request in that
  form; a pair no form is exact for is never asked; calibration items keep their own form. Red on the ask lane's
  delivered planner beside the claims lane's question_claims (the repair's integration preview), whose relation_form
  the planner never read; on the port's question_claims alone (no relation_form) these tests cannot pass."""
from __future__ import annotations

import dataclasses
import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation.contract import appraise_read, proof, settle
from studio.interpretation.contract import question_claims as QC
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, assess, catalogue, evaluate, questions, whatif
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import Id, IsoDate, Span
from tests.v2.evaluate_fixtures import (DC, EARLIER, ON, TEAM, Doc, E, Kind, L, SessionKind, Status, X, colonoscopy,
                                        doubted, fact, neg, sup, unit, unlisted, unres)

A = ct.Attribute
LM = ct.Landmark
# getattr: the RED run on the port (base), which has neither, imports this module too, so each test fails on its own
CK = getattr(asking, 'CalibrationKind', None)
QF = asking.Family


def k1(n: int, **over) -> asking.CalibrationSpec:
    base = dict(kind='K1', family=QF.Q_FACT, form='fact.session', subjects=(f'E{n}',), attribute=A.SESSION,
                value='X1', negated=True, names=(f'E{n}', 'X1'))
    base.update(over)
    return asking.CalibrationSpec(**base)


def k2(n: int) -> asking.CalibrationSpec:
    return asking.CalibrationSpec('K2', QF.Q_FACT, 'fact.session', (f'E{n}',), A.SESSION, 'X2', False, (f'E{n}', 'X2'))


def k4(n: int) -> asking.CalibrationSpec:
    return asking.CalibrationSpec('K4', QF.Q_ONLESION, 'onlesion', (f'E{n}', 'L1'), A.TARGET_LESION, 'L1', True,
                                  (f'E{n}', 'L1'))


def covers_k3(n: int) -> asking.CalibrationSpec:
    return asking.CalibrationSpec('K3', QF.Q_REL, 'rel', (f'E{n}', 'E2'), None, '', False, (f'E{n}', 'E2'),
                                  source='covers')


def rel(n: int) -> asking.QuestionSpec:
    return asking.QuestionSpec(QF.Q_REL, 'rel', (f'E{n + 40}', 'E3'), None, '', False, (f'E{n + 40}', 'E3'))


def onlesion_q(n: int) -> asking.QuestionSpec:
    return asking.QuestionSpec(QF.Q_ONLESION, 'onlesion', (f'E{n + 60}', 'L1'), A.TARGET_LESION, 'L1', True,
                               (f'E{n + 60}', 'L1'))


POOL = [k1(n) for n in range(1, 13)] + [k2(n) for n in range(1, 13)]


# --- D319: one calibration item a request ---------------------------------------------------------------------------

class OneItemTests(SimpleTestCase):
    """DECISIONS D319 (item a)."""

    def test_the_count_is_one_whatever_the_number_of_questions(self) -> None:
        self.assertEqual((asking.CALIBRATION_COUNT, asking.CALIBRATION_MIN, asking.CALIBRATION_POOL_MIN), (1, 1, 1))
        self.assertEqual({asking.calibration_count(q) for q in range(0, 60)}, {1})

    def test_every_request_carries_exactly_one_item(self) -> None:
        for count in (1, 2, 8, 9, 17, 40):
            with self.subTest(questions=count):
                requests = asking.partition([rel(n) for n in range(count)], POOL, 1)
                self.assertEqual([len(request.calibration) for request in requests], [1] * len(requests))
                self.assertTrue(all(request.calibrated for request in requests))

    def test_the_one_item_is_negative_form_wherever_the_pool_has_one(self) -> None:
        for seed in range(40):  # the K2s outnumber nothing: half the pool is positive-form
            with self.subTest(seed=seed):
                drawn = asking.draw(POOL, [rel(0)], f'seed-{seed}')
                self.assertEqual(len(drawn), 1)
                self.assertTrue(drawn[0].negative)
        only_positive = [k2(n) for n in range(1, 6)]  # the boundary: a pool of positive items still gives its one
        self.assertEqual([item.kind for item in asking.draw(only_positive, [rel(0)], 'seed')], [CK.K2])

    def test_a_family_with_both_polarities_gives_its_negative_item(self) -> None:
        # a Q-FACT question: its family holds K1 (negative) and K2 (positive) items - the one item is a K1, every seed
        date = asking.QuestionSpec(QF.Q_FACT, 'fact.date_relation', ('E50',), A.DATE_RELATION, 'on_date_of_service',
                                   False, ('E50',))
        for seed in range(40):
            with self.subTest(seed=seed):
                self.assertIs(asking.draw(POOL, [date], f'p{seed}')[0].kind, CK.K1)

    def test_the_first_asked_family_with_a_negative_source_gives_the_item(self) -> None:
        pool = POOL + [k4(n) for n in range(20, 24)]
        for seed in range(20):
            with self.subTest(seed=seed):
                self.assertIs(asking.draw(pool, [onlesion_q(0), rel(0)], f's{seed}')[0].kind, CK.K4)
                self.assertIs(asking.draw(pool, [rel(0), onlesion_q(0)], f's{seed}')[0].kind, CK.K4)  # Q-REL: none
                # a request whose families have no source draws a negative item of another family
                self.assertTrue(asking.draw(pool, [rel(0)], f's{seed}')[0].negative)

    def test_a_plain_kind_or_source_is_read_into_its_enum(self) -> None:
        item = asking.CalibrationSpec('K3', QF.Q_REL, 'rel', ('E1', 'E2'), None, '', False, ('E1', 'E2'),
                                      source='same')
        self.assertIs(item.kind, CK.K3)
        self.assertIs(item.source, asking.K3Source.SAME)
        self.assertEqual(item.key, 'K3|Q-REL|rel|E1,E2|||')  # the stored key keeps its words
        self.assertEqual(json.dumps({'kind': item.kind}), '{"kind": "K3"}')


# --- D318: the bound ----------------------------------------------------------------------------------------------------

class BoundTests(SimpleTestCase):
    """DECISIONS D318 (2) and its first addendum (item b): QUESTION_BOUND_MEASURED holds step 1 short's request and step
    1 long's three, as recorded in anthropic-project/pairs/r3-probe-1 and r3-probe-2 (their MANIFEST question runs:
    output tokens, claims); t_q 5,936; the rounding a pair of claims; 18 claims a request."""

    def test_the_bound_is_derived_from_the_four_measured_requests(self) -> None:
        self.assertEqual(asking.QUESTION_BOUND_MEASURED, ((55_219, 12), (105_999, 20), (71_896, 20), (94_976, 16)))
        derived = asking.question_bound_derivation()
        self.assertEqual((derived.tokens_per_claim, derived.capacity, derived.bound), (5_936, 18, 18))
        self.assertEqual((asking.QUESTION_BOUND, asking.QUESTION_BOUND_ROUNDING), (18, 2))
        document = asking.question_bound_document()
        self.assertEqual((document['question_bound'], document['tokens_per_claim'], document['rounding'],
                          document['measured']), (18, 5_936, 2, [[55_219, 12], [105_999, 20], [71_896, 20],
                                                                  [94_976, 16]]))

    def test_the_bound_is_the_largest_pair_within_85_percent(self) -> None:
        margin = 128_000 * 85 // 100
        self.assertLessEqual(asking.QUESTION_BOUND * 5_936, margin)
        self.assertGreater((asking.QUESTION_BOUND + asking.QUESTION_BOUND_ROUNDING) * 5_936, margin)
        # the rounding is a pair: an odd capacity rounds down to the pair below, an even one stays
        self.assertEqual(asking.question_bound_derivation(((108_800 // 19, 1),)).bound, 18)
        self.assertEqual(asking.question_bound_derivation(((108_800 // 20, 1),)).bound, 20)

    def test_a_request_holds_eight_questions_and_its_item(self) -> None:
        for count, sizes in ((8, [8]), (9, [8, 1]), (16, [8, 8]), (18, [8, 8, 2])):
            with self.subTest(questions=count):
                requests = asking.partition([rel(n) for n in range(count)], POOL, 1)
                self.assertEqual([len(request.questions) for request in requests], sizes)
                self.assertTrue(all(request.claims <= 18 for request in requests))
        self.assertEqual(asking.partition([rel(n) for n in range(8)], POOL, 1)[0].claims, 18)

    def test_t_q_is_rounded_up(self) -> None:
        # 10,881 tokens over 2 claims: 5,440.5 a claim - up to 5,441 (19 claims within the margin, 18 by the pair), never
        # down to 5,440 (which would give 20)
        derived = asking.question_bound_derivation(((10_881, 2),))
        self.assertEqual((derived.tokens_per_claim, derived.capacity, derived.bound), (5_441, 19, 18))

    def test_one_question_and_its_item_is_the_floor(self) -> None:
        with self.assertRaises(RuntimeError):
            asking.question_bound_derivation(((108_800 // 3, 1),))  # capacity 3 -> bound 2: no room for a pair of pairs
        self.assertEqual(asking.question_bound_derivation(((108_800 // 4, 1),)).bound, 4)


# --- D317 (1): the member line ------------------------------------------------------------------------------------------

def section_facts(start: int, *, performer=None, owner=None) -> dict:
    """A section as the fact pass holds it: its role (the heading, whose source places it at ``start``), its owner and
    its performer."""
    out = {A.ROLE: (sup(ct.SectionRole.FINDINGS, spans=(Span(start, start + 20),)),),
           A.OWNER: ((owner if owner is not None else unres(DC, ct.Reason.UNAPPRAISED)),)}
    if performer is not None:
        out[A.PERFORMER] = (performer,)
    return out


DOUBTED_TEAM = doubted(TEAM, ct.Performer.OTHER_CLINICIAN)


def member_doc(*, line: str = 'after', section_performer=DOUBTED_TEAM, section_owner=None) -> object:
    """A colonoscopy X1 told in three parts: N1 (a history part from 50) with E1, an earlier colonoscopy's examination in
    X2 (an earlier date); N2 (the procedure part from 250, whose performer pass 1 doubts toward another clinician -
    ``section_performer``) with E3, X1's examination, and E4, a biopsy; then the member line - pass 2's kept unlisted
    DOUBT at 480 (``line='after'``), at 230 before the part (``'before'``) or none (``'none'``); N3 (the findings part
    from 550) with E6, a cold snare of L1 (described at 600), and E7, a biopsy. Every act's frame and session facts and
    E6's target lesion established AND controlled."""
    doc = Doc()
    doc.session(1, SessionKind.COLONOSCOPY)
    doc.session(2, SessionKind.COLONOSCOPY)
    doc.sessions[X(1)][A.EXAMINATION] = (sup(E(3)),)
    doc.sessions[X(2)][A.EXAMINATION] = (sup(E(1)),)
    doc.exam(1, session=X(2), date=sup(EARLIER))
    doc.exam(3)
    doc.act(4, Kind.BIOPSY, places=[sup(LM.RECTUM)])
    doc.lesion(1, lesion_places=[sup(LM.SIGMOID_COLON, spans=(Span(600, 640),))],
               multiplicity=sup(ct.Multiplicity.SINGLE, spans=(Span(600, 640),)))
    doc.act(6, Kind.SNARE, places=[sup(LM.SIGMOID_COLON)], lesion=sup(L(1)))
    doc.act(7, Kind.BIOPSY, places=[sup(LM.CECUM)])
    if line == 'after':
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, None, X(1), Span(480, 520)))
    elif line == 'before':
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, None, X(1), Span(230, 245)))
    R = doc.build()
    sections = {Id.parse('N1'): section_facts(50), Id.parse('N2'): section_facts(250, performer=section_performer,
                                                                                   owner=section_owner),
                Id.parse('N3'): section_facts(550)}
    controlled = {(E(n), attribute) for n in (1, 3, 4, 6, 7)
                  for attribute in (A.DATE_RELATION, A.ENTRY, A.PERFORMER, A.SESSION, A.TARGET_LESION)}
    return dataclasses.replace(R, sections=sections, controlled=frozenset(controlled))


def pool_keys(R) -> set:
    return {item.key for item in asking.calibration_pool(R)}


def acts_of(keys) -> set:
    return {key.split('|')[3].split(',')[0] for key in keys}


class MemberLineTests(SimpleTestCase):
    """DECISIONS D317 (1) (item c): a calibration item is drawn only where its truth turns on no member line - no
    statement that gives another performer or author to the acts on one side of it (C-C2MEM-023's "All of the above was
    done by her previous gastroenterologist.": scripts/ml_pin.py pins its 24 contested items on the recorded row)."""

    def test_no_item_names_an_object_told_on_the_lines_side(self) -> None:  # the must-change input
        R = member_doc()
        keys = pool_keys(R)
        self.assertEqual(acts_of(keys), {'E6', 'E7'})  # E1, E3, E4 are told above the line: none of their items
        # E6's and E7's session items name X1, told at E3 (above the line): not drawn; their frame items are
        self.assertFalse([key for key in keys if '|fact.session|' in key])
        self.assertEqual({key.split('|')[2] for key in keys}, {'fact.date_relation', 'fact.entry', 'fact.performer',
                                                                'onlesion'})
        # the same document with no member line draws every one of them (the guard is the only difference)
        plain = member_doc(section_performer=sup(TEAM))
        self.assertLess(keys, pool_keys(plain))
        self.assertTrue({'E1', 'E3', 'E4'} <= acts_of(pool_keys(plain)))
        self.assertTrue([key for key in pool_keys(plain) if '|fact.session|' in key])

    def test_the_side_is_read_from_the_representation_never_the_words(self) -> None:
        R = member_doc()
        side = asking.member_line_side(R)
        self.assertIn((0, 480), side)  # the nearest kept unlisted entry after the contested part: the side before it
        self.assertIn((250, 550), side)  # the contested part itself, to the next section's start
        self.assertEqual(asking.member_line_side(member_doc(section_performer=sup(TEAM))), ())

    def test_with_no_entry_locating_the_line_the_part_alone_is_the_side(self) -> None:
        keys = pool_keys(member_doc(line='none'))
        self.assertIn('E1', acts_of(keys))  # told in N1, outside the contested part: drawn
        self.assertFalse({'E3', 'E4'} & acts_of(keys))
        self.assertFalse([key for key in keys if '|fact.session|' in key and key.endswith('|X1|not')])

    def test_a_line_before_the_part_contests_the_side_after_it(self) -> None:
        keys = pool_keys(member_doc(line='before'))
        self.assertIn('E1', acts_of(keys))  # above the line: untouched
        self.assertFalse({'E3', 'E4', 'E6', 'E7'} & acts_of(keys))  # the part and everything after the line

    def test_a_doubted_author_is_a_member_line_and_an_established_one_is_not(self) -> None:
        author = member_doc(section_performer=sup(TEAM), section_owner=doubted(DC, ct.Owner.OTHER_CLINICIAN))
        self.assertEqual(acts_of(pool_keys(author)), {'E6', 'E7'})
        settled = member_doc(section_performer=sup(TEAM), section_owner=sup(ct.Owner.NURSING))
        self.assertEqual(asking.member_line_side(settled), ())  # the fact pass settled it: its acts' facts say so
        contradicted = member_doc(section_performer=fact(ct.Result.CONTRADICTED, None, ct.FactState.CONTRADICTED,
                                                         options=(ct.Performer.OTHER_CLINICIAN, TEAM),
                                                         reasons=(ct.Reason.CONTRADICTED_BY_PASS1,)))
        self.assertEqual(acts_of(pool_keys(contradicted)), {'E6', 'E7'})

    def test_a_plain_claim_of_another_performer_or_author_is_no_member_line(self) -> None:  # the boundary kept
        # pass 2 never appraises a section's facts: an outside-history part claimed other_facility, an administrative
        # footer, stay unresolved with NO reading beside the claim - nothing contests them (pair 2's L02 shape)
        outside = member_doc(section_performer=unres(ct.Performer.OTHER_FACILITY, ct.Reason.UNAPPRAISED),
                             section_owner=unres(ct.Owner.ADMINISTRATIVE, ct.Reason.UNAPPRAISED))
        self.assertEqual(asking.member_line_side(outside), ())
        self.assertEqual(pool_keys(outside), pool_keys(member_doc(section_performer=sup(TEAM))))

    def test_readings_that_are_all_anothers_are_no_member_line(self) -> None:  # the boundary kept
        # an outside act filed both other_clinician and other_facility (an overfilled slot: D2low's B-fb05 in the
        # faithful world) was done by someone else either way: no documenting reading is contested
        overfull = fact(ct.Result.UNRESOLVED, None, ct.FactState.CONTRADICTED,
                        options=(ct.Performer.OTHER_CLINICIAN, ct.Performer.OTHER_FACILITY),
                        reasons=(ct.Reason.SLOT_OVERFULL,))
        R = member_doc(section_performer=sup(TEAM), line='none')
        events = dict(R.events)
        events[E(1)] = {**events[E(1)], A.PERFORMER: (overfull,)}
        outside = dataclasses.replace(R, events=events)
        self.assertEqual(asking.member_line_side(outside), ())
        doubted_act = {**events, E(1): {**events[E(1)], A.PERFORMER: (doubted(TEAM, ct.Performer.OTHER_CLINICIAN),)}}
        self.assertEqual(asking.member_line_side(dataclasses.replace(R, events=doubted_act)), ((100, 160),))

    def test_a_denial_entry_never_locates_the_line(self) -> None:
        R = member_doc(line='none')
        denial = dataclasses.replace(R, unlisted=(unlisted(ct.UnlistedWhat.DENIAL, Kind.CLIP, X(1), Span(480, 520)),))
        self.assertEqual(asking.member_line_side(denial), asking.member_line_side(R))  # the part alone, as with none

    def test_an_established_reading_is_no_member_line_whatever_its_options(self) -> None:
        settled = member_doc(section_performer=sup(TEAM),
                             section_owner=fact(ct.Result.SUPPORTED, DC, ct.FactState.SUPPORTED,
                                                options=(ct.Owner.OTHER_CLINICIAN,)))
        self.assertEqual(asking.member_line_side(settled), ())

    def test_an_unplaced_part_contests_the_whole_document_beside_a_placed_one(self) -> None:
        R = member_doc()
        sections = dict(R.sections)
        sections[Id.parse('N4')] = {A.PERFORMER: (DOUBTED_TEAM,)}  # a second contested part, placed nowhere
        self.assertEqual(asking.member_line_side(dataclasses.replace(R, sections=sections)), ((0, asking._END),))

    def test_an_unplaced_contested_part_contests_the_whole_document(self) -> None:
        R = member_doc()
        sections = dict(R.sections)
        sections[Id.parse('N2')] = {A.PERFORMER: (DOUBTED_TEAM,)}  # no source anywhere: placed nowhere
        self.assertEqual(asking.member_line_side(dataclasses.replace(R, sections=sections)), ((0, asking._END),))
        self.assertEqual(asking.calibration_pool(dataclasses.replace(R, sections=sections)), ())


# --- D317 (4): one kinds table; K2's dates and encounters ---------------------------------------------------------------

def two_sessions(*, kind2=SessionKind.EGD, exam2=None, encounters=(None, None)) -> object:
    """A colonoscopy X1 (its examination E1 and the snare E2 of L1, both done today) and a second procedure session X2
    of ``kind2`` that TOOK PLACE (its examination E3, done; ``exam2`` its facts), each session's encounter fact as
    ``encounters`` gives it; every act's frame and session facts established AND controlled."""
    doc = colonoscopy()
    del doc.sessions[X(1)][A.ENCOUNTER]
    doc.session(2, kind2)
    for session, encounter in zip((X(1), X(2)), encounters):
        if encounter is not None:
            doc.sessions[session][A.ENCOUNTER] = (encounter,)
    doc.exam(3, session=X(2), **(exam2 or {}))
    R = doc.build()
    controlled = {(E(n), attribute) for n in (1, 2, 3) for attribute in (A.DATE_RELATION, A.ENTRY, A.PERFORMER,
                                                                          A.SESSION)}
    return dataclasses.replace(R, controlled=frozenset(controlled))


def k2_of(R) -> set:
    return {(item.subjects[0], item.value) for item in asking.calibration_pool(R) if item.kind is CK.K2}


THIS, SEPARATE = sup(ct.EncounterRelation.THIS_ENCOUNTER), sup(ct.EncounterRelation.SEPARATE_ENCOUNTER)


def on(year: int, month: int, precision=ct.Precision.MONTH) -> object:
    import datetime
    return sup(IsoDate(datetime.date(year, month, 1), precision))


class KindsAndOccasionsTests(SimpleTestCase):
    """DECISIONS D317 (4) (item d)."""

    def test_the_procedure_kinds_are_the_one_table(self) -> None:
        self.assertIs(asking.PROCEDURE_SESSION_KINDS, catalogue.ENDOSCOPIC_FAMILIES)

    def test_two_procedure_sessions_of_one_examination_give_no_k2(self) -> None:  # the must-change input
        same = two_sessions(kind2=SessionKind.COLONOSCOPY)  # two colonoscopy sessions filed for one examination today
        self.assertTrue(asking.procedure_session(same, X(2)))
        self.assertEqual(k2_of(same), set())
        self.assertEqual(k2_of(two_sessions(encounters=(THIS, THIS))), set())  # the same day, one encounter
        self.assertFalse(asking.separate_occasions(same, X(1), X(2)))

    def test_established_different_dates_or_separate_encounters_give_k2(self) -> None:  # the boundary kept
        both = {('E1', 'X2'), ('E2', 'X2'), ('E3', 'X1')}
        self.assertEqual(k2_of(two_sessions(exam2=dict(date=sup(EARLIER)))), both)
        self.assertEqual(k2_of(two_sessions(encounters=(THIS, SEPARATE))), both)
        later = two_sessions(exam2=dict(date=sup(ct.DateRelation.LATER_DATE)))
        self.assertEqual(k2_of(later), both)

    def test_two_earlier_dates_are_apart_only_when_their_periods_are(self) -> None:
        def earlier_pair(first, second) -> object:
            doc = colonoscopy(snare=False)
            del doc.sessions[X(1)][A.ENCOUNTER]
            doc.exam(1, date=sup(EARLIER))
            doc.events[E(1)][A.DATE] = (first,)
            doc.session(2, SessionKind.EGD)
            doc.exam(3, session=X(2), date=sup(EARLIER))
            doc.events[E(3)][A.DATE] = (second,)
            R = doc.build()
            return dataclasses.replace(R, controlled=frozenset({(E(n), A.SESSION) for n in (1, 3)}))
        self.assertTrue(asking.separate_occasions(earlier_pair(on(2024, 1), on(2023, 3)), X(1), X(2)))
        self.assertFalse(asking.separate_occasions(earlier_pair(on(2024, 1), on(2024, 1)), X(1), X(2)))
        year = on(2024, 1, ct.Precision.YEAR)  # 2024 as a year holds January 2024: not apart
        self.assertFalse(asking.separate_occasions(earlier_pair(year, on(2024, 3)), X(1), X(2)))
        self.assertTrue(asking.separate_occasions(earlier_pair(year, on(2023, 12)), X(1), X(2)))

    def test_an_unestablished_occasion_or_encounter_separates_nothing(self) -> None:
        open_date = two_sessions(exam2=dict(date=unres(EARLIER)))
        self.assertEqual(k2_of(open_date), set())
        self.assertEqual(k2_of(two_sessions(encounters=(THIS, unres(ct.EncounterRelation.SEPARATE_ENCOUNTER)))), set())


# --- D315 (6): G1's statuses --------------------------------------------------------------------------------------------

# G1's census reason (round r3's integration, this lane's Q3 with the claims lane's SessionNotTests): ONE source -
# question_claims' declared exact set for fact.session.not (act/performed, act/planned), read by D314's check; the
# planner's own copy of the set (G1_STATUSES, its reason G1_NOT_EXACT) is removed, so an attempt and an act in doubt
# carry D314's reason, as a denial always did
G1_D314 = 'D314 (fact.session.not is not exact for act/{} (subject 1; declared act/performed, act/planned))'


class G1StatusTests(SimpleTestCase):
    """DECISIONS D315 (6) (item e): the D315 checker's constructed case (probe-check4/scripts/ck4_g1.py) - a colonoscopy
    X1 whose ONLY examination E1 has the status given, its session left open (silent) and its performer not stated (it
    fails row 4), beside the cold snare E2: G1 ("This act was not done during session X1.") is asked of an examination
    established performed or planned, never of one attempted or whose status is in doubt."""

    def g1_of(self, status) -> tuple:
        doc = colonoscopy()
        doc.exam(1, status=status, session=F.SILENT, performer=F.SILENT)
        found = asking.plan(doc.build())
        return [spec for spec in found.specs if spec.census == 'G1'], found.blocked

    def test_an_attempted_examination_is_never_asked(self) -> None:  # the must-change input (ck4_g1's case)
        g1, blocked = self.g1_of(sup(Status.ATTEMPTED_NOT_COMPLETED))
        self.assertEqual(g1, [])
        self.assertIn(G1_D314.format('attempted'), blocked)

    def test_an_examination_whose_status_is_in_doubt_is_never_asked(self) -> None:
        for status in (unres(Status.PERFORMED, ct.Reason.UNAPPRAISED), doubted(Status.PERFORMED, Status.PLANNED)):
            with self.subTest(status=status.result):
                g1, blocked = self.g1_of(status)
                self.assertEqual(g1, [])
                self.assertIn(G1_D314.format('in_doubt'), blocked)

    def test_the_planner_keeps_no_second_copy_of_g1s_set(self) -> None:  # the integration's one-source rule
        self.assertFalse(hasattr(asking, 'G1_STATUSES') or hasattr(asking, 'G1_NOT_EXACT'))
        self.assertEqual(QC.QUESTION_SOURCES["fact.session.not"].exact[0].names(), ["act/performed", "act/planned"])

    def test_a_performed_or_planned_examination_is_asked(self) -> None:  # the boundary kept
        for status in (sup(Status.PERFORMED), sup(Status.PLANNED)):
            with self.subTest(status=status.value):
                g1, _ = self.g1_of(status)
                self.assertEqual([(spec.form, spec.subjects, spec.value) for spec in g1],
                                 [('fact.session.not', ('E1',), 'X1')])

    def test_a_denied_examination_keeps_d314s_reason(self) -> None:
        g1, blocked = self.g1_of(neg(Status.PERFORMED))
        self.assertEqual(g1, [])
        self.assertTrue([reason for reason in blocked if reason.startswith('D314 (fact.session.not is not exact for '
                                                                           'statement/denied')], blocked)


# --- D312: K3b ---------------------------------------------------------------------------------------------------------

class CoversK3Tests(SimpleTestCase):
    """DECISIONS D312 (item f): the killing test of K3b (the K1 companion of a covers K3 and the final drop both off). A
    K3 from pass 1's covers is UNCONTROLLED, so it is drawn only beside a K1; one item a request leaves no room beside
    it, so it is never drawn - its K1 takes its place - and with no K1 in the pool it is not usable at all."""

    def test_a_covers_k3_never_stands_as_the_one_item(self) -> None:
        pool = [covers_k3(n) for n in range(10, 20)] + [k1(30)]
        for seed in range(60):
            with self.subTest(seed=seed):
                drawn = asking.draw(pool, [rel(0)], f'k3b-{seed}')  # a Q-REL question: the K3s are its family
                self.assertEqual([item.kind for item in drawn], [CK.K1])

    def test_a_covers_k3_with_no_k1_is_not_usable(self) -> None:
        pool = [covers_k3(n) for n in range(10, 14)] + [k2(n) for n in range(20, 24)]
        for seed in range(20):
            with self.subTest(seed=seed):
                self.assertEqual([item.kind for item in asking.draw(pool, [rel(0)], f'x{seed}')], [CK.K2])
        self.assertEqual(asking.draw([covers_k3(10)], [rel(0)], 'alone'), ())

    def test_a_same_rows_k3_needs_no_companion(self) -> None:
        same = asking.CalibrationSpec('K3', QF.Q_REL, 'rel', ('E9', 'E2'), None, '', False, ('E9', 'E2'),
                                      source='same')
        self.assertEqual(asking.draw([same, k1(30)], [rel(0)], 'seed'), (same,))


# --- D323 F3: the typed readings ----------------------------------------------------------------------------------------

def _old_family(cause: str) -> str:
    """The prototype's word reading of a cause's family (engine/asking.classify before D323 F3), for the comparison."""
    for prefix in ('relation:', 'appraisal:', 'coding_rule:', 'unestablished:'):
        if cause.startswith(prefix):
            return prefix[:-1]
    return cause


class TypedReadingTests(SimpleTestCase):
    """DECISIONS D323 F3 (item g): FINAL-V2 5.7 measure 4 over this lane's files - tests.test_guard_static's own rules
    find nothing - and each typed reading equals the prototype's word reading wherever that reading could be met."""

    def test_the_guards_find_nothing_in_asking_and_whatif(self) -> None:
        from tests import test_guard_static as guard
        values, sources = guard._design_values(), guard._v2_modules()
        for module in ('engine/asking', 'engine/whatif', 'engine/requirements'):
            with self.subTest(module=module):
                self.assertEqual(guard.no_word_lists(sources[module], module, values), [])
                self.assertEqual(guard.words_never_decide(sources[module], module, set()), [])

    def test_every_cause_label_reads_as_its_family(self) -> None:
        for label, cause in whatif.CAUSES.items():
            with self.subTest(label=label):
                self.assertEqual(cause.family.value, _old_family(label))
        self.assertIs(whatif.cause_of(dataclasses.replace(next(iter(_held())), cause='no_such:cause')).family,
                      whatif.CauseFamily.OTHER)

    def test_the_typed_reason_sets_equal_the_word_sets(self) -> None:
        reasons = list(ct.Reason)
        self.assertEqual(asking._C2B, frozenset(
            reason for reason in reasons if reason.value in ('appraisal_contradicts', 'appraisal_unclear',
                                                             'control_incoherent')
            or reason.value.startswith('appraisal_qualified')))
        self.assertEqual(asking._QUALIFIED, frozenset(reason for reason in reasons
                                                      if reason.value.startswith('qualified')))
        self.assertEqual(asking.INTEGRITY, frozenset(reason for reason in reasons if reason.value in (
            'unit_unknown', 'words_not_in_units', 'words_not_bounded', 'units_not_consecutive', 'source_too_long',
            'anchor_words', 'reference_invalid')))

    def test_the_engine_digest_is_the_prototypes_formula(self) -> None:
        import hashlib
        from pathlib import Path
        names = ('contract/question_claims', 'contract/settle', 'engine/anatomy', 'engine/asking', 'engine/assess',
                 'engine/catalogue', 'engine/classes', 'engine/combination', 'engine/coverage', 'engine/evaluate',
                 'engine/facts', 'engine/pairing', 'engine/questions', 'engine/reading', 'engine/requirements',
                 'engine/requirements_table', 'engine/types', 'engine/whatif', 'store')
        root = Path(asking.__file__).resolve().parents[1]
        digest = hashlib.sha256()
        for name in sorted(names):
            digest.update(name.encode('utf-8') + b'\0' + hashlib.sha256((root / f'{name}.py').read_bytes()).digest())
        self.assertEqual(asking.engine_digest(), digest.hexdigest())

    def test_a_cause_the_table_does_not_read_is_blocked_first(self) -> None:  # fail-closed (whatif.CauseFamily.OTHER)
        R = colonoscopy(date=unres(ON, ct.Reason.UNAPPRAISED)).build()
        ctx = asking._Context(R)
        candidate = next(found for found in whatif.witnesses(R, '45385') if found.witnesses)
        witness = candidate.witnesses[0]
        self.assertTrue(asking.classify(ctx, candidate, witness).specs)  # the date question is asked as it is ...
        unread = dataclasses.replace(witness, held=dataclasses.replace(witness.held, cause='coding_rule_x:date'))
        found = asking.classify(ctx, candidate, unread)  # ... and never under a label the table does not name
        self.assertEqual((found.specs, found.blocked), ((), 'unclassified (coding_rule_x:date)'))
        self.assertTrue(asking._rule_or_unread(unread.held))  # the value rule reads it as a rule's failure

    def test_an_unread_cause_on_a_row_7_witness_is_never_asked(self) -> None:
        # a cause the table does not read, on the possible examination's tie (row 7): blocked before the tie is read -
        # the G1 question the witness would otherwise reach is never asked under a label nothing reads
        doc = colonoscopy()
        doc.exam(1, status=sup(Status.PERFORMED), session=F.SILENT, performer=F.SILENT)
        R = doc.build()
        ctx = asking._Context(R)
        for candidate in whatif.witnesses(R, '45385'):
            for witness in candidate.witnesses:
                if witness.held.subject == E(1) and asking._row7_tie(ctx, candidate, witness.held) is not None:
                    unread = dataclasses.replace(witness, held=dataclasses.replace(witness.held, cause='no_such'))
                    self.assertEqual(asking.classify(ctx, candidate, unread).specs, ())
                    return
        self.fail('no row-7 witness about E1')

    def test_the_stored_names_read_through_their_enums(self) -> None:
        self.assertEqual([asking.unlisted_index((name,)) for name in ('u:0', 'u:12', 'u:', 'u:x', 'acts:X1', 'E3')],
                         [0, 12, None, None, None, None])
        self.assertTrue(asking.names_carded(('document', 'acts:X1'), ('E1',), lambda name: name == 'E1'))
        self.assertFalse(asking.names_carded(('acts:X1',), ('E1', 'E2'), lambda name: name == 'E1'))
        R = colonoscopy().build()
        self.assertEqual(asking.describe(R, 'document'), (asking.qc.SubjectClass.ENCOUNTER, asking.qc.SubjectStatus.NONE))


def _held() -> tuple:
    R = colonoscopy(date=unres(ON, ct.Reason.UNAPPRAISED)).build()
    return tuple(witness.held for candidate in whatif.witnesses(R, '45385') for witness in candidate.witnesses)


# --- D323 F4: the planner's invariant ------------------------------------------------------------------------------------

class InvariantTests(SimpleTestCase):
    """DECISIONS D323 F4 (item h): a question request without its calibration item is refused at plan time and never
    returned - so never sent - and the calibration pool of a STORED row is non-empty (the killing test of the mutant
    that drops facts' controlled=, M2, which before survived every test)."""

    def test_a_request_without_its_item_is_refused_at_plan_time(self) -> None:  # the must-change input
        questions = [rel(n) for n in range(10)]
        with self.assertRaises(asking.UncalibratedRequest) as raised:
            asking.partition(questions, [], 1)
        self.assertEqual([len(chunk) for chunk in raised.exception.refused], [8, 2])
        self.assertEqual(raised.exception.requests, ())
        self.assertEqual(raised.exception.reason, 'question_health:uncalibrated')
        with self.assertRaises(asking.UncalibratedRequest):
            asking.split(asking.RequestPlan(tuple(questions[:4]), (k1(1),), 'seed'), [covers_k3(9)], 1)
        with self.assertRaises(asking.UncalibratedRequest):
            asking.check_calibrated(asking.RequestPlan((rel(0),), (), 'seed'))

    def test_a_request_with_its_item_passes(self) -> None:  # the boundary kept
        request = asking.partition([rel(0)], [k1(1)], 1)[0]
        self.assertIs(asking.check_calibrated(request), request)
        self.assertEqual(asking.split(request, [k1(1)], 1), ())  # one question: stays unresolved, never split

    def test_a_stored_rows_pool_feeds_every_request(self) -> None:  # M2's killing test, through facts.factset
        from tests.v2 import test_lesion_pair as LP
        _, out = LP.settled(LP.NOTE, LP.note_answer(), LP.lesion_oracle())
        R = F.factset(LP.view(LP.NOTE, LP.row(LP.NOTE, out)))
        self.assertTrue(R.controlled)
        pool = asking.calibration_pool(R)
        self.assertTrue([item for item in pool if item.kind is CK.K1])
        self.assertEqual([len(request.calibration) for request in asking.partition([rel(0)], pool, 1)], [1])


# --- D323 L1: the member-context row --------------------------------------------------------------------------------

class ContextRowTests(SimpleTestCase):
    """DECISIONS D323 L1 (item i): R6's member-context row (member-entered setting and patient status, D3: never read from
    the document, census A2) is skipped by the what-if - read by its requirement through the Enum. assess's R6 rows
    carry the Tag's VALUE (assess._Row.requirement is a str), so an identity test of the raw value with Tag.R6_CONTEXT
    would never hold and would leave every office E/M candidate an A2 witness that blocks it whole."""

    def office(self) -> object:
        doc = Doc()
        doc.session(1, SessionKind.OFFICE_EM)
        doc.act(1, Kind.EM_VISIT, session=X(1))
        return doc.build()

    def test_the_context_row_is_skipped_for_an_office_visit(self) -> None:
        R = self.office()
        rows = assess.r6_rows('99213', (E(1),), R, assess.MemberContext())
        self.assertIn(Tag.R6_CONTEXT.value, [row.requirement for row in rows])  # the row exists, as its value
        causes = {witness.held.cause for candidate in whatif.witnesses(R, '99213') for witness in candidate.witnesses}
        self.assertNotIn(questions.CONTEXT_MISSING, causes)

    def test_the_requirement_is_read_through_the_enum(self) -> None:
        self.assertIs(whatif._tag_of('R6:context'), Tag.R6_CONTEXT)
        self.assertIs(whatif._tag_of(Tag.R6_CONTEXT), Tag.R6_CONTEXT)
        self.assertIsNone(whatif._tag_of('R7'))


# --- D312's M10b (C7b-denial), on this lane's file -------------------------------------------------------------------

class DenialPairTests(SimpleTestCase):
    """DECISIONS D312: the killing test of M10b - C7b-denial (asking._denies_or_doubts) reads a claimed pair's statement
    as a denial or a doubt when pass 1 FILED its status negated (state negated, whatever its settled result) or doubted
    it, not only when its negation is established: such a claimed pair is never asked as Q-REL."""

    def test_a_filed_denial_and_a_doubted_status_are_c7b_denial(self) -> None:
        open_denial = fact(ct.Result.UNRESOLVED, Status.PERFORMED, ct.FactState.NEGATED,
                           reasons=(ct.Reason.APPRAISAL_UNCLEAR,))
        for status in (open_denial, doubted(Status.PERFORMED, Status.PLANNED)):  # doubted: DOUBT_STATED
            with self.subTest(status=status.result):
                doc = colonoscopy()
                doc.event(3, kind=sup(Kind.SNARE), status=status, session=sup(X(1)), date=sup(ON),
                          covers=[sup(E(2))])
                R = doc.build()
                self.assertTrue(asking._denies_or_doubts(R, E(3)))
        settled = colonoscopy()  # an established negation is one too, and a status established performed is none
        settled.event(3, kind=sup(Kind.SNARE), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON))
        settled.event(4, kind=sup(Kind.SNARE), status=sup(Status.PERFORMED), session=sup(X(1)), date=sup(ON))
        R = settled.build()
        self.assertEqual((asking._denies_or_doubts(R, E(3)), asking._denies_or_doubts(R, E(4))), (True, False))


# --- D323 O1: no lesion-pair question -----------------------------------------------------------------------------------

class NoLesionQuestionTests(SimpleTestCase):
    """DECISIONS D323 O1 (item j): Q-LESION is not shipped - the planner asks no lesion-pair question, whatever the fact
    request's lesion pairs (b.3's re-ask off)."""

    def test_the_planner_asks_no_lesion_pair_question(self) -> None:
        events = {'claims': [{'id': 'K9', 'template': 'lesion.distinct_from'}],
                  'lesion_pairs': [{'lesion': 'L1', 'other': 'L2', 'result': 'supported', 'claim': 'K9', 'reasons': []}]}
        doc = colonoscopy()
        doc.lesion(1, lesion_places=[sup(LM.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
        doc.lesion(2, lesion_places=[sup(LM.RECTUM)], multiplicity=sup(ct.Multiplicity.SINGLE))
        R = doc.build()
        self.assertTrue(asking.lesion_pair_specs(events, R))  # the pair the prototype would have asked
        found = asking.plan(R, (), events=events)
        self.assertFalse([spec for spec in found.specs if spec.family is QF.Q_LESION])
        self.assertEqual(found, asking.plan(R, ()))


# --- D323 F1: the planner's side of Q-ONLESION ---------------------------------------------------------------------------

def onlesion_scene(*, denial_places, act_places, rejected=lambda subject, place: True) -> object:
    """The port's probes q01/q04 scenes (tests.v2.test_pairing helpers): the statement E3 a DENIED injection with a single
    target L1 in the transverse colon at ``denial_places``; the act E4 a tattoo naming no lesion at ``act_places``; the
    place pair controls claims.pair() makes, answered by ``rejected``."""
    from tests.v2 import test_pairing as TPG
    doc = colonoscopy(places=[sup(LM.TRANSVERSE_COLON)])
    doc.lesions[L(1)] = {A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),), A.PLACES: (sup(LM.TRANSVERSE_COLON),)}
    doc.lesion(2, multiplicity=sup(ct.Multiplicity.SINGLE), lesion_places=[sup(LM.CECUM)])
    doc.act(3, Kind.INJECTION, status=neg(Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
            places=[sup(place) for place in denial_places], lesion=sup(L(1)))
    doc.act(4, Kind.TATTOO, places=[sup(place) for place in act_places])
    doc.controls.update(TPG.claims_pair_controls(E(3), denial_places, E(4), act_places, rejected))
    return doc.build()


def onlesion_asked(R) -> list:
    return [(spec.form, spec.subjects) for spec in asking.plan(R).specs if spec.family is QF.Q_ONLESION]


class OnLesionPlanTests(SimpleTestCase):
    """DECISIONS D323 F1 (item k), the planner's side: Q-ONLESION is asked only where the SAME it serves rests on the
    statement's lesions' places alone - no place of the statement beyond its lesions' places holds the act's place,
    and no place pair control of either object left unrejected (asking._onlesion_unanswerable). The engine lane builds
    the reading side (one release arm under D311's class rule and D316's QB)."""

    def test_qbs_scene_asks_nothing(self) -> None:  # the must-change input: D316's QB, the port's q01/q04
        R = onlesion_scene(denial_places=(LM.TRANSVERSE_COLON, LM.COLON), act_places=(LM.TRANSVERSE_COLON,))
        self.assertEqual(onlesion_asked(R), [])
        self.assertIn(asking.ONLESION_BEYOND, asking.plan(R).blocked)

    def test_rfl2_1s_scene_asks_nothing(self) -> None:
        R = onlesion_scene(denial_places=(LM.TRANSVERSE_COLON, LM.DESCENDING_COLON), act_places=(LM.TRANSVERSE_COLON,),
                           rejected=lambda subject, place: not (subject == E(4) and place is LM.DESCENDING_COLON))
        self.assertEqual(onlesion_asked(R), [])
        self.assertIn(asking.ONLESION_CONTROL, asking.plan(R).blocked)

    def test_p4s_shape_is_asked(self) -> None:  # the boundary kept: the denial at its lesion's place alone
        R = onlesion_scene(denial_places=(LM.TRANSVERSE_COLON,), act_places=(LM.TRANSVERSE_COLON,))
        self.assertEqual(onlesion_asked(R), [('onlesion', ('E4', 'L1'))])
        # a place of the statement beyond its lesion that does NOT hold the act's place leaves it asked
        far = onlesion_scene(denial_places=(LM.TRANSVERSE_COLON, LM.CECUM), act_places=(LM.TRANSVERSE_COLON,))
        self.assertEqual(onlesion_asked(far), [('onlesion', ('E4', 'L1'))])

    def test_an_act_whose_places_are_not_established_is_not_asked(self) -> None:
        # the tattoo's place list not established (a second place unresolved beside the supported one): the target row
        # is still SAME on the supported place, and no answer could set the act apart - it may be anywhere (4.11)
        R = onlesion_scene(denial_places=(LM.TRANSVERSE_COLON,), act_places=(LM.TRANSVERSE_COLON,))
        events = dict(R.events)
        events[E(4)] = {**events[E(4)], A.TARGET_PLACES: (sup(LM.TRANSVERSE_COLON), unres(LM.SIGMOID_COLON))}
        R = dataclasses.replace(R, events=events)
        self.assertEqual(onlesion_asked(R), [])
        self.assertIn(asking.ONLESION_ACT_PLACES, asking.plan(R).blocked)

    def test_a_statement_whose_places_are_not_established_is_not_asked(self) -> None:
        R = onlesion_scene(denial_places=(LM.TRANSVERSE_COLON,), act_places=(LM.TRANSVERSE_COLON,))
        events = dict(R.events)
        events[E(3)] = {**events[E(3)], A.TARGET_PLACES: (sup(LM.TRANSVERSE_COLON), unres(LM.CECUM))}
        R = dataclasses.replace(R, events=events)
        self.assertEqual(onlesion_asked(R), [])
        self.assertIn(asking.ONLESION_STATEMENT_PLACES, asking.plan(R).blocked)


# --- D318 (3), the repair pass's RA-4: the narrowest exact form, derived by question_claims ---------------------------

OPEN_DENIAL = fact(ct.Result.UNRESOLVED, Status.PERFORMED, ct.FactState.NEGATED, reasons=(ct.Reason.APPRAISAL_UNCLEAR,))
SC_, SS_ = QC.SubjectClass, QC.SubjectStatus


def _beside_the_snare(open_act_date: bool = False, **e3) -> object:
    """colonoscopy()'s cold snare E2 of L1 in the sigmoid colon (its date left open when ``open_act_date``, so a
    statement of another date stays paired) with the event E3 of ``e3``."""
    doc = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION)) if open_act_date else colonoscopy()
    doc.event(3, **e3)
    return doc.build()


def _beside_an_entry(what: ct.UnlistedWhat) -> object:
    doc = colonoscopy()
    doc.unlisted.append(unlisted(what, None, None, unit(9)))
    return doc.build()


# every Q-REL census row and statement class/status the planner meets (SYNTHETIC scenes): (R, the statement's stored
# name) and what the plan must show - the census row, the witness's cause, the statement's description, and whether
# DECISIONS D318 (3) names a NARROWER relation than "concern" for that statement (an established denial, an open denial,
# an established plan: True). Which narrow form is question_claims' (relation_form, the claims lane's - as delivered:
# rel.deny, rel.deny_or_doubt, rel.plan); these tests pin the planner's WIRING to it, never a copy of its table.
REL_SCENES = {
    "the finding: an open denial at the snare's site": (
        lambda: (_beside_the_snare(kind=sup(Kind.SNARE), status=OPEN_DENIAL, session=sup(X(1)), date=sup(ON),
                                   places=[sup(LM.SIGMOID_COLON)]), 'E3'),
        ('R2', 'relation:possible_statement', (SC_.STATEMENT, SS_.IN_DOUBT), True)),
    "the finding: an established denial at the snare's site": (
        lambda: (_beside_the_snare(kind=sup(Kind.SNARE), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                                   places=[sup(LM.SIGMOID_COLON)]), 'E3'),
        ('R1', 'relation:unresolved', (SC_.STATEMENT, SS_.DENIED), True)),
    'R1 an established denial elsewhere (its target row open)': (
        lambda: (_beside_the_snare(kind=sup(Kind.SNARE), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                                   entry=sup(DC), breadth=sup(ct.Breadth.SINGLE_TARGET), places=[sup(LM.RECTUM)]),
                 'E3'),
        ('R1', 'relation:unresolved', (SC_.STATEMENT, SS_.DENIED), True)),
    'R1 an established plan of a later date': (
        lambda: (_beside_the_snare(True, kind=sup(Kind.SNARE), status=sup(Status.PLANNED), session=sup(X(1)),
                                   date=sup(ct.DateRelation.LATER_DATE), entry=sup(DC)), 'E3'),
        ('R1', 'relation:unresolved', (SC_.ACT, SS_.PLANNED), True)),
    'R1 a told act of an earlier date': (
        lambda: (_beside_the_snare(True, kind=sup(Kind.SNARE), status=sup(Status.PERFORMED), session=sup(X(1)),
                                   date=sup(EARLIER), entry=sup(DC)), 'E3'),
        ('R1', 'relation:unresolved', (SC_.ACT, SS_.PERFORMED), False)),
    'R1 an attempt of an earlier date': (
        lambda: (_beside_the_snare(True, kind=sup(Kind.SNARE), status=sup(Status.ATTEMPTED_NOT_COMPLETED),
                                   session=sup(X(1)), date=sup(EARLIER), entry=sup(DC)), 'E3'),
        ('R1', 'relation:unresolved', (SC_.ACT, SS_.ATTEMPTED), False)),
    'R2 an open denial of a clip (its kind open)': (
        lambda: (_beside_the_snare(kind=unres(Kind.CLIP), status=OPEN_DENIAL, session=sup(X(1)), date=sup(ON),
                                   entry=sup(DC)), 'E3'),
        ('R2', 'relation:possible_statement', (SC_.STATEMENT, SS_.IN_DOUBT), True)),
    'R2 an act-filed possible statement': (
        lambda: (_beside_the_snare(kind=sup(Kind.SNARE), status=unres(Status.PERFORMED, ct.Reason.UNAPPRAISED),
                                   session=sup(X(1)), date=sup(ON), entry=sup(DC), places=[unres(LM.SIGMOID_COLON)]),
                 'E3'),
        ('R2', 'relation:possible_statement', (SC_.ACT, SS_.IN_DOUBT), False)),
    'C7b-other a claimed plan': (
        lambda: (_beside_the_snare(kind=sup(Kind.SNARE), status=sup(Status.PLANNED), session=sup(X(1)),
                                   date=sup(ct.DateRelation.LATER_DATE), entry=sup(DC),
                                   covers=[unres(E(2), ct.Reason.UNAPPRAISED)]), 'E3'),
        ('C7b-other', 'relation:unresolved', (SC_.ACT, SS_.PLANNED), True)),
    'U1 a kept unlisted denial': (
        lambda: (_beside_an_entry(ct.UnlistedWhat.DENIAL), 'u:0'),
        ('U1', 'unlisted', (SC_.UNLISTED, SS_.DENIES), False)),
    'U1 a kept unlisted doubt': (
        lambda: (_beside_an_entry(ct.UnlistedWhat.DOUBT), 'u:0'),
        ('U1', 'unlisted', (SC_.UNLISTED, SS_.DOUBTS), False)),
}

# the end-to-end request (the product's builder, question_claims.build_question_request_fable, over a SYNTHETIC fact
# request): the examination E1 told at S2, the cold snare E2 at S3, the statement E3 at S4
E2E_TEXT = ('Colonoscopy report.\n'
            'The colonoscope was advanced to the cecum without difficulty.\n'
            'A small sigmoid polyp was removed with a cold snare without electrocautery.\n'
            'No clip or cautery was needed at this site after the removal.\n')
E2E_QUOTES = ['No clip or cautery was needed at this site', 'removed with a cold snare without electrocautery']
E2E_K1 = asking.CalibrationSpec('K1', QF.Q_FACT, 'fact.performer', ('E2',), A.PERFORMER, 'documenting_team', True,
                                ('E2',), described=((SC_.ACT, SS_.PERFORMED),))


def e2e_request(specs: list, calibration: list) -> object:
    units, at = [], 0
    for number, line in enumerate(E2E_TEXT.split('\n')[:4], start=1):
        start = E2E_TEXT.index(line, at)
        units.append({'id': f'S{number}', 'start': start, 'end': start + len(line)})
        at = start + len(line)
    cards = tuple(ct.Card(card, card_type, (where,), None, None) for card, card_type, where in (
        ('A1', ct.CardType.ACT, 'S2'), ('A2', ct.CardType.ACT, 'S3'), ('A3', ct.CardType.ACT, 'S4'),
        ('X1', ct.CardType.SESSION, 'S2'), ('L1', ct.CardType.LESION, 'S3')))
    objects = {'A1': ('event', 'E1'), 'A2': ('event', 'E2'), 'A3': ('event', 'E3'), 'X1': ('session', 'X1'),
               'L1': ('lesion', 'L1')}
    framed = '<<<DOCUMENT-0000000000000000 BEGIN>>>\nsynthetic\n<<<DOCUMENT-0000000000000000 END>>>'
    built = SimpleNamespace(framed=framed, claim_set=SimpleNamespace(cards=cards, objects=objects))
    view = {'units': units, 'events': [], 'sessions': [], 'sections': [], 'unlisted': []}
    plan = asking.RequestPlan(tuple(specs), tuple(calibration), 'seed')
    return QC.build_question_request_fable(built, E2E_TEXT, (), view, plan, 1, 1)


def e2e_settled(built, claim: tuple, control: tuple) -> object:
    """``built`` answered - every question's claim ``claim`` (verdict, quotes) and its control ``control``, every
    calibration item in the holding direction - read, located and settled by the product's own functions."""
    verdicts = []
    for item in built.items:
        for member, claim_id in (('claim', item.claim), ('control', item.control)):
            if item.role == 'calibration':
                value, quotes = ('contradicts', []) if member == 'claim' else ('supports', [])
            else:
                value, quotes = claim if member == 'claim' else control
            verdicts.append({'claim': claim_id, 'verdict': value, 'attached': 'yes', 'qualifiers': [],
                             'evidence': list(item.cited[:1]), 'quotes': list(quotes)})
    cited = {}
    for item in built.items:
        cited[item.claim] = item.cited
        cited[item.control] = item.cited
    read = appraise_read.read_questions(json.dumps({'verdicts': verdicts, 'unlisted': []}), built.claim_ids, cited, 4)
    assert hasattr(read, 'verdicts'), read
    locations = {item.claim: proof.locate(E2E_TEXT, item.required, item.optional,
                                          read.verdicts[item.claim].quotes if read.verdicts.get(item.claim) else (),
                                          item.alternatives) for item in built.items}
    with mock.patch.object(asking, 'eligible', return_value=True):
        return settle.settle_questions(built, read, locations, None)


class NarrowestFormTests(SimpleTestCase):
    """DECISIONS D318 (3) and its second addendum, the repair pass's RA-4: the planner hands EVERY question the
    narrowest form exact for its subjects' descriptions, derived by contract/question_claims - one source, never a form
    the planner fixes: Q-REL's forms are several readings of one fact (the pair INDEPENDENT), so a denial asks whether
    it denies the act, an open denial whether it denies it or casts doubt on it, a plan whether it plans or recommends
    it, and only where nothing narrower is exact whether it concerns it (question_claims.relation_form)."""

    def rel_spec(self, R, statement: str):
        plan = asking.plan(R, ())
        found = [spec for spec in plan.specs if spec.family is QF.Q_REL and spec.subjects == (statement, 'E2')]
        self.assertEqual(len(found), 1, [spec.key for spec in plan.specs])
        return plan, found[0]

    def test_the_findings_scene_asks_the_narrowest_form(self) -> None:  # the must-change input (RA-4's r06)
        for name in ("the finding: an open denial at the snare's site",
                     "the finding: an established denial at the snare's site"):
            scene, _ = REL_SCENES[name]
            with self.subTest(scene=name):
                plan, spec = self.rel_spec(*scene())
                self.assertEqual(spec.form, QC.relation_form(spec.described))  # rel.deny_or_doubt / rel.deny today
                self.assertNotEqual(spec.form, 'rel')  # was the concern form ("... does not concern act A2.")
                self.assertEqual(sorted(plan.serves[spec.key]), ['45385'])

    def test_every_census_row_asks_the_form_question_claims_derives(self) -> None:  # the class
        for name, (scene, (row, cause, statement_side, narrower)) in REL_SCENES.items():
            R, statement = scene()
            with self.subTest(scene=name):
                _, spec = self.rel_spec(R, statement)
                self.assertEqual((spec.census, spec.witnesses[0].cause, spec.described[0]),
                                 (row, cause, statement_side))
                self.assertEqual(spec.form, QC.relation_form(spec.described))
                if narrower:  # D318 (3): never the concern form where the ruling names a narrower relation
                    self.assertNotEqual(spec.form, 'rel')
                # the narrowest exact form: the concern form only where no narrower form is exact
                exact = [member.value for member in QC.RELATION_FORMS
                         if QC.inexact(member.value, spec.described) is None]
                self.assertEqual(exact[0], spec.form)

    def test_the_planners_form_is_question_claims_relation_form_for_every_description(self) -> None:
        rel_q = asking.QuestionSpec(QF.Q_REL, 'rel', ('E3', 'E2'), None, '', False, ('E3', 'E2'))
        every = [(klass, status) for klass in SC_ for status in SS_] + [None]
        for statement in every:
            for act in every:
                self.assertEqual(asking.question_form(rel_q, (statement, act)), QC.relation_form((statement, act)),
                                 (statement, act))

    def test_every_other_family_keeps_its_own_form(self) -> None:  # the boundary of question_form
        act, single = (SC_.ACT, SS_.PERFORMED), (SC_.LESION, SS_.SINGLE)
        for spec, described in ((onlesion_q(0), (act, single)), (onlesion_q(0), (act, (SC_.LESION, SS_.NOT_SINGLE))),
                                (asking.QuestionSpec(QF.Q_FACT, 'fact.session.not', ('E1',), A.SESSION, 'X1', True,
                                                     ('E1', 'X1')), (act,)),
                                (asking.QuestionSpec(QF.Q_ABSORB, 'absorb', ('u:0',), None, '', False,
                                                     ('u:0', 'acts:X1')), ((SC_.UNLISTED, SS_.DOUBTS),))):
            with self.subTest(form=spec.form, described=described):
                self.assertEqual(asking.question_form(spec, described), spec.form)

    def test_q_onlesion_asks_its_narrower_form_where_it_is_exact(self) -> None:  # the class's other member, kept
        single = onlesion_scene(denial_places=(LM.TRANSVERSE_COLON,), act_places=(LM.TRANSVERSE_COLON,))
        lesions = dict(single.lesions)
        lesions[L(1)] = {**lesions[L(1)], A.MULTIPLICITY: (unres(ct.Multiplicity.SINGLE),)}
        group = dataclasses.replace(single, lesions=lesions)
        for R, form in ((single, 'onlesion'), (group, 'onlesion.group')):
            specs = [spec for spec in asking.plan(R).specs if spec.family is QF.Q_ONLESION]
            with self.subTest(form=form):
                self.assertEqual([spec.form for spec in specs], [form])
                exact = [name for name in ('onlesion', 'onlesion.group')
                         if QC.inexact(name, specs[0].described) is None]
                self.assertEqual(exact[0], form)

    def test_a_pair_no_form_is_exact_for_is_never_asked(self) -> None:  # fail-closed: the held fact stays held
        doc = colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.SNARE, X(1), unit(9)))  # an unlisted ACT: no Q-REL side
        R = doc.build()
        for subjects in (('u:0', 'E2'), ('E9', 'E2'), ('E3', 'u:0')):
            spec = asking.QuestionSpec(QF.Q_REL, 'rel', subjects, None, '', False, subjects)
            with self.subTest(subjects=subjects):
                self.assertIsNone(QC.relation_form(tuple(asking.describe(R, stored) for stored in subjects)))
                found, why = asking.described_spec(R, spec)
                self.assertIsNone(found)
                self.assertTrue(why.startswith('D314 (rel is not exact for '), why)  # the census reason, as before

    def test_the_key_the_serves_and_asked_before_carry_the_narrowed_form(self) -> None:
        scene, _ = REL_SCENES["the finding: an established denial at the snare's site"]
        R, _ = scene()
        plan, spec = self.rel_spec(R, 'E3')
        self.assertNotEqual(spec.form, 'rel')
        self.assertEqual(spec.key, f'Q-REL|{QC.relation_form(spec.described)}|E3,E2|||')  # rel.deny today
        self.assertEqual(set(plan.serves), {found.key for found in plan.specs})
        again = asking.plan(R, (spec.key,))  # asked before: never asked again
        self.assertFalse([found for found in again.specs
                          if found.family is QF.Q_REL and found.subjects == ('E3', 'E2')])

    def test_the_request_asks_the_planners_narrow_sentence_and_releases_only_by_proof(self) -> None:
        """The recorded hold's shape (DECISIONS D318 (b): r3-probe-2's (E35, A31), an open denial of clips or cautery at
        a cold-snare removal's site, was asked whether it concerns the removal, truthfully answered "concerns", and
        45385 stayed held): the PLANNER'S own spec, built by the product's request builder, asks the narrow sentence;
        a truthful answer establishes it and releases 45385; one wrong "supports" meets the exact negation and holds."""
        concern = QC.QUESTION_TEMPLATES['rel'][1].replace('{act}', 'A2')  # "This statement does not concern act A2."
        for label, status in (('open denial', OPEN_DENIAL), ('established denial', neg(Status.PERFORMED))):
            R = _beside_the_snare(kind=unres(Kind.CLIP), status=status, session=sup(X(1)), date=sup(ON), entry=sup(DC))
            with self.subTest(statement=label):
                _, spec = self.rel_spec(R, 'E3')
                built = e2e_request([spec], [E2E_K1])
                item = next(found for found in built.items if found.role == 'question')
                # the sentence pair question_claims renders for the planner's own form (today: "This statement does
                # not deny act A2 or cast doubt on it." / "This statement does not deny act A2." and their negations)
                positive, negative = QC.QUESTION_TEMPLATES[spec.form]
                self.assertEqual(item.spec.form, spec.form)
                self.assertEqual((item.claim_sentence, item.control_sentence),
                                 (negative.replace('{act}', 'A2'), positive.replace('{act}', 'A2')))
                self.assertNotEqual(item.claim_sentence, concern)
                self.assertTrue(evaluate.decide('45385', (), R).held_facts)
                right = e2e_settled(built, ('supports', E2E_QUOTES), ('contradicts', []))
                self.assertEqual((right.questions[0]['result'], right.questions[0]['form']), ('supported', spec.form))
                self.assertFalse(evaluate.decide('45385', (), F._answered(R, {'questions': list(right.questions)}))
                                 .held_facts)
                wrong = e2e_settled(built, ('supports', E2E_QUOTES), ('supports', []))
                self.assertEqual(wrong.questions[0]['reasons'], ['question_incoherent'])
                self.assertTrue(evaluate.decide('45385', (), F._answered(R, {'questions': list(wrong.questions)}))
                                .held_facts)

    def test_calibration_items_keep_their_own_form(self) -> None:  # the boundary kept
        # a K3 (pass 1's covers supported) of an established denial: its known-false ground is "concerns", so it keeps
        # the concern form where a QUESTION of the same pair would be asked "does not deny" (question_claims)
        R = _beside_the_snare(kind=sup(Kind.SNARE), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                              entry=sup(DC), covers=[sup(E(2))])
        k3 = [item for item in asking.calibration_pool(R) if item.kind is CK.K3]
        self.assertEqual([(item.form, item.subjects) for item in k3], [('rel', ('E3', 'E2'))])
        self.assertNotEqual(QC.relation_form(k3[0].described), 'rel')  # a question of the pair is asked narrower
