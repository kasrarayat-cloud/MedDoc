"""The per-code rule of design v2 (docs/gemini-migration/FINAL-V2.md 4.3, 4.4, 4.6, 4.10, 4.11; step 4a of its 8.1),
TEXT-ONLY and SYNTHETIC: every FactSet is hand-built (tests/v2/evaluate_fixtures.py) from engine/types' records -
enumeration members, ids, results and integer spans, the engine's whole input (4.1). No document is read, no provider is
called, nothing touches the network.

The done-when of 8.1 step 4a, each proved here (the item itself, its binding and message: tests/v2/test_questions.py):
- "v1's per-code rule tests re-expressed over settled fixtures": V1RuleRows, ExaminationIsTheSession, DefiningKinds,
  DilationSite, AnastomosisSite, Focused, Exclusion and SessionQuestion re-express tests/test_interpretation_events.py
  class by class (each docstring names what v2 changed and why: the readers' cases become facts; D31 and EB3 retire);
- "the C-10 shared-sentence fixture": Exclusion.test_c10_*, with ``kept_words`` (v1's within_words) and without;
- "Q1's act choice" and "the binding by rank and every candidate's witnesses (HO-8's two cases)": Binding;
- "a doubted act positive (HO-1's documents A and B held)": DoubtedActs;
- "no early return before the code rules (Q2)": NoEarlyReturn;
- "each held code carries exactly one item (D182)": tests/v2/test_questions.py OneItem, over every fixture here;
- "mypy --strict on both modules": Boundary.
Also: every row of 4.3 met, unmet and established otherwise (SupportRows, CodeRows); 4.6's five conditions (Exclusion);
D197's route (b) item; the never-READY holds; determinism; 5.7 measure 4.

The refutation of round 1 (build-v2/w34/refute-4a-r1), each finding pinned by a test that fails without its repair:
F1 (row 7's plans and histories: SupportRows.test_row_7_a_plan_or_a_history_*, its fail-closed side
test_row_7_an_examination_that_may_be_*, the office variant test_row_7_an_office_*), F4 (CodeRows.test_lower), F5
(CodeRows.test_limited_and_stations_read_only_the_upper_stations), D1 (3.2.6 rule 2: UnlistedOnEvidence), D2
(Exclusion.test_condition_5_an_unlisted_act_*), T1 (Binding.test_rule_3_*), T2
(SupportRows.test_row_6_route_b_needs_every_*); F2, F3 and the items' sentences: tests/v2/test_questions.py Worded;
repair_fixtures() feeds every shape to OneItem and P-MONO.
"""
from __future__ import annotations

import ast
import dataclasses
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation.contract import types as ct
from studio.interpretation.engine import catalogue
from studio.interpretation.engine import evaluate as EV
from studio.interpretation.engine import facts as facts_module
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import Cover, Evaluation, FactSet, HeldFact, Id, ItemKind, Span
from tests.v2.evaluate_fixtures import (DC, EARLIER, ON, TEAM, Doc, E, L, Landmark, Owner, Performer, SessionKind,
                                        Status, X, Y, colonoscopy, contra, doubted, egd, neg, statement_source, sup,
                                        unit, unlisted, unres)
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'engine' / 'evaluate.py'
Kind, Breadth, Device, Extent, Station = ct.Kind, ct.Breadth, ct.Device, ct.Extent, ct.Station
A, Res = ct.Attribute, ct.Result
QUESTION, EXPLANATION = ItemKind.QUESTION, ItemKind.EXPLANATION


def decide(code: str, R: FactSet, kept=(), kept_words=None) -> Evaluation:
    return EV.decide(code, tuple(kept), R, kept_words=kept_words)


def ready(evaluation: Evaluation) -> bool:
    return bool(evaluation.supporting) and not evaluation.held_facts and evaluation.exclusion is None


def keys(evaluation: Evaluation) -> list:
    """(fact, rank, kind, cause) of every held fact, in the evaluation's order."""
    return [(held.fact, held.rank, held.kind, held.cause) for held in evaluation.held_facts]


def item(code: str, R: FactSet, kept=()) -> Q.Item | None:
    return EV.item(code, tuple(kept), R, decide(code, R, kept))


def rule(name: Q.Rule) -> str:
    return Q.coding_rule(name)


def truths(code: str, R: FactSet, event: Id, group=None) -> dict:
    group = group if group is not None else catalogue.requirements(catalogue.code_link(code))[0]
    support = EV.support(code, group, R, event)
    return {row.requirement: row.truth for row in support.rows}


T, U, F = EV.Truth.T, EV.Truth.U, EV.Truth.F


# --- SUPPORT, rows 1-8 (4.3), met, unmet and established otherwise -----------------------------------------------------


class SupportRows(SimpleTestCase):
    """Every row of 4.3's SUPPORT table, T, U and F, with the witness each records (fact key, rank, kind, cause)."""

    def held(self, code, R):
        evaluation = decide(code, R)
        self.assertFalse(ready(evaluation))
        self.assertIsNone(evaluation.exclusion)
        return evaluation

    def test_the_control_every_row_met_is_ready(self):
        evaluation = decide('45385', colonoscopy().build())
        self.assertTrue(ready(evaluation))
        self.assertEqual(evaluation.supporting, (E(2),))
        self.assertEqual(set(truths('45385', colonoscopy().build(), E(2)).values()), {T})

    def test_row_1_kind(self):
        cases = {
            'umbrella': (sup(Kind.REMOVAL), [('act_method', 9, QUESTION, rule(Q.Rule.UMBRELLA))]),
            'unresolved': (unres(Kind.SNARE), [('performed_status', 4, QUESTION, 'appraisal:unclear')]),
            'doubted': (doubted(Kind.SNARE, Kind.BIOPSY), [('performed_status', 4, QUESTION, 'reading_unknown')]),
            'contradicted': (contra(Kind.SNARE, Kind.BIOPSY), [('conflict:snare', 1, QUESTION,
                                                                'reading_contradicted')]),
        }
        for name, (kind, expected) in cases.items():
            with self.subTest(name):
                R = colonoscopy(kind=kind).build()
                self.assertEqual(truths('45385', R, E(2))[rq.Requirement.SUP_KIND], U)
                self.assertEqual(keys(self.held('45385', R)), expected)

    def test_row_1_a_clip_is_a_bleeding_control_only_with_its_purpose_supported_hemostasis(self):
        def clip(purpose):
            doc = egd()
            doc.act(2, Kind.CLIP, purpose=purpose, cause=sup(ct.Cause.PRE_EXISTING_LESION))
            return doc.build()

        self.assertTrue(ready(decide('43255', clip(sup(ct.Purpose.HEMOSTASIS)))))
        for purpose in (unres(ct.Purpose.HEMOSTASIS), doubted(ct.Purpose.HEMOSTASIS), None):
            with self.subTest(purpose=purpose and purpose.result):
                evaluation = decide('43255', clip(purpose))
                self.assertEqual(keys(evaluation)[0][:3], ('performed_status', 4, QUESTION))
                self.assertEqual(evaluation.bindings, {(Kind.BLEEDING_CONTROL,): E(2)})
        # a purpose established as another is no bleeding control, so no candidate: not documented, never excluded
        evaluation = decide('43255', clip(sup(ct.Purpose.MARKING)))
        self.assertEqual(keys(evaluation), [('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED))])

    def test_row_1_an_injection_for_hemostasis_is_a_bleeding_control_never_an_injection_codes_act(self):
        """catalogue.catalogue_kind: an injection whose purpose is supported hemostasis is a bleeding control (45382),
        never 45381's submucosal injection; one that claims hemostasis without establishing it is asked; one whose
        purpose is silent or another is an injection."""
        def injection(purpose):
            doc = colonoscopy(snare=False)
            doc.act(2, Kind.INJECTION, purpose=purpose, cause=sup(ct.Cause.PRE_EXISTING_LESION),
                    places=[sup(Landmark.SIGMOID_COLON)])
            return doc.build()

        hemostasis = injection(sup(ct.Purpose.HEMOSTASIS))
        self.assertEqual(EV.candidates(hemostasis, (Kind.INJECTION, Kind.TATTOO)), ())
        self.assertEqual(keys(decide('45381', hemostasis)), [('performed_status', 4, QUESTION,
                                                               rule(Q.Rule.NOT_DOCUMENTED))])
        self.assertTrue(ready(decide('45382', hemostasis)))
        for purpose in (None, sup(ct.Purpose.LIFT_FOR_RESECTION), sup(ct.Purpose.MARKING)):
            with self.subTest(purpose=purpose and purpose.value):
                self.assertTrue(ready(decide('45381', injection(purpose))))
        for purpose in (unres(ct.Purpose.HEMOSTASIS), doubted(ct.Purpose.LIFT_FOR_RESECTION, ct.Purpose.HEMOSTASIS)):
            with self.subTest(purpose=purpose.result):
                evaluation = decide('45381', injection(purpose))
                self.assertEqual([entry[:3] for entry in keys(evaluation)], [('performed_status', 4, QUESTION)])
                self.assertEqual(evaluation.bindings, {(Kind.INJECTION, Kind.TATTOO): E(2)})
        self.assertFalse(ready(decide('45382', injection(None))))  # a silent purpose: possibly a bleeding control

    def test_row_2_status_and_att(self):
        attempted = colonoscopy(status=sup(Status.ATTEMPTED_NOT_COMPLETED)).build()
        self.assertEqual(keys(self.held('45385', attempted)),
                         [('performed_status', 4, EXPLANATION, rule(Q.Rule.ATTEMPTED))])  # C-9
        self.assertEqual(truths('45385', attempted, E(2))[rq.Requirement.SUP_STATUS], F)
        doc = colonoscopy(snare=False)  # ATT: an examination begun and not completed supports its base code
        doc.events[E(1)][A.STATUS] = (sup(Status.ATTEMPTED_NOT_COMPLETED),)
        self.assertTrue(ready(decide('45378', doc.build())))
        self.assertFalse(ready(decide('45385', doc.build())))
        cases = {'doubted': (doubted(Status.PERFORMED), ('performed_status', 2, QUESTION, 'reading_unknown')),
                 'unresolved': (unres(Status.PERFORMED), ('performed_status', 4, QUESTION, 'appraisal:unclear')),
                 'contradicted': (contra(Status.PERFORMED, Status.PLANNED),
                                  ('conflict:snare', 1, QUESTION, 'reading_contradicted'))}
        for name, (status, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(keys(self.held('45385', colonoscopy(status=status).build())), [expected])

    def test_row_2_the_att_tag_not_examination_code_decides(self):
        """Step 1f's hand-off R9(a): catalogue.examination_code also answers the office E/M codes; the ATT tag does
        not, so an E/M visit stated attempted is a C-9 hold."""
        self.assertTrue(catalogue.examination_code(catalogue.code_link('99213')))
        self.assertNotIn(Tag.ATT, rq.spec('99213').tags)
        doc = Doc()
        doc.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        doc.act(1, Kind.EM_VISIT, status=sup(Status.ATTEMPTED_NOT_COMPLETED))
        self.assertEqual(keys(decide('99213', doc.build()))[0], ('performed_status', 4, EXPLANATION,
                                                                 rule(Q.Rule.ATTEMPTED)))

    def test_rows_3_and_4_timing_and_performer(self):
        cases = {
            'date unresolved': (dict(date=unres(ON)), ('event_time', 6, QUESTION, 'appraisal:unclear')),
            'date silent': (dict(date=None), ('event_time', 6, QUESTION, 'reading_unknown')),
            'date doubted': (dict(date=doubted(ON, EARLIER)), ('event_time', 6, QUESTION, 'reading_unknown')),
            'date on the date of service negated': (dict(date=neg(ON)), ('event_time', 6, QUESTION,
                                                                         rule(Q.Rule.TIMING))),
            'performer unknown': (dict(performer=None), ('event_performer', 7, QUESTION, 'reading_unknown')),
            'performer contradicted': (dict(performer=contra(TEAM, Performer.OTHER_CLINICIAN)),
                                       ('conflict:snare', 1, QUESTION, 'reading_contradicted')),
        }
        for name, (over, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(keys(self.held('45385', colonoscopy(**over).build())), [expected])

    def test_an_act_of_another_date_or_performer_is_no_positive_candidate(self):
        for over in (dict(date=sup(EARLIER)), dict(performer=sup(Performer.OTHER_FACILITY))):
            with self.subTest(over=over):
                evaluation = decide('45385', colonoscopy(**over).build())
                self.assertEqual(evaluation.bindings, {})
                self.assertEqual(keys(evaluation), [('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED))])

    def test_row_5_entry(self):
        nursing = colonoscopy(entry=sup(Owner.NURSING)).build()
        self.assertEqual(keys(self.held('45385', nursing)), [('event_entry', 5, EXPLANATION, rule(Q.Rule.ENTRY))])
        self.assertEqual(truths('45385', nursing, E(2))[rq.Requirement.SUP_ENTRY], F)
        self.assertEqual(keys(self.held('45385', colonoscopy(entry=unres(DC)).build())),
                         [('event_entry', 5, QUESTION, 'appraisal:unclear')])

    def test_row_6_session(self):
        doc = colonoscopy()
        doc.session(1, SessionKind.EGD)  # the act's session established as another family's
        evaluation = self.held('45385', doc.build())
        self.assertIn(('procedure', 8, QUESTION, rule(Q.Rule.SESSION)), keys(evaluation))
        self.assertEqual(keys(self.held('45385', colonoscopy(session=unres(X(1))).build()))[0],
                         ('procedure', 8, QUESTION, 'appraisal:unclear'))
        doc = colonoscopy()
        doc.session(1, unres(SessionKind.COLONOSCOPY))
        self.assertIn(('procedure', 8, QUESTION, 'appraisal:unclear'), keys(self.held('45385', doc.build())))

    def test_row_6_route_b_reads_the_places_in_the_codes_regions(self):
        def banding(*places):
            doc = colonoscopy(snare=False)
            doc.act(2, Kind.BAND_LIGATION, places=list(places))
            return doc.build()

        self.assertEqual(truths('46221', banding(sup(Landmark.ANAL_CANAL)), E(2))[rq.Requirement.SUP_SESSION], T)
        self.assertEqual(truths('46221', banding(sup(Landmark.SIGMOID_COLON)), E(2))[rq.Requirement.SUP_SESSION], F)
        self.assertEqual(truths('46221', banding(unres(Landmark.RECTUM)), E(2))[rq.Requirement.SUP_SESSION], U)
        self.assertEqual(truths('46221', banding(), E(2))[rq.Requirement.SUP_SESSION], U)

    def test_row_6_route_b_needs_every_supported_place_in_the_regions(self):
        """4.3 row 6's route (b): the act's supported places in the code's regions, every one, at least one (the
        refutation's T2: no test told "every" from "any"). A banding at the anal canal and the sigmoid colon does not
        support 46221 - E* empty, the act's place held; the anal canal alone supports it (D197 then holds the code)."""
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.BAND_LIGATION, places=[sup(Landmark.ANAL_CANAL), sup(Landmark.SIGMOID_COLON)])
        R = doc.build()
        self.assertEqual(truths('46221', R, E(2))[rq.Requirement.SUP_SESSION], F)
        evaluation = decide('46221', R)
        self.assertEqual(evaluation.supporting, ())
        self.assertIn(('act_target', 11, QUESTION, rule(Q.Rule.SESSION)), keys(evaluation))
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.BAND_LIGATION, places=[sup(Landmark.ANAL_CANAL)])
        self.assertEqual(decide('46221', doc.build()).supporting, (E(2),))

    def test_row_7_the_sessions_examination_by_its_own_facts(self):
        cases = {
            "the examination's performer another": (dict(performer=sup(Performer.OTHER_CLINICIAN)),
                                                    ('event_performer', 7, QUESTION, rule(Q.Rule.EXAMINATION))),
            "the examination's status doubted": (dict(status=doubted(Status.PERFORMED)),
                                                 ('performed_status', 2, QUESTION, 'reading_unknown')),
            "the examination's entry another role": (dict(entry=sup(Owner.ANESTHESIA)),
                                                     ('event_entry', 5, EXPLANATION, rule(Q.Rule.ENTRY))),
            "the examination planned": (dict(status=sup(Status.PLANNED)),
                                        ('performed_status', 4, QUESTION, rule(Q.Rule.EXAMINATION))),
        }
        for name, (over, expected) in cases.items():
            with self.subTest(name):
                doc = colonoscopy()
                doc.exam(1, **over)
                evaluation = self.held('45385', doc.build())
                self.assertIn(expected, keys(evaluation))
                self.assertTrue(all(held.subject == E(1) for held in evaluation.held_facts))
        doc = colonoscopy()  # an examination begun and not completed is done (v1's done)
        doc.exam(1, status=sup(Status.ATTEMPTED_NOT_COMPLETED))
        self.assertTrue(ready(decide('45385', doc.build())))
        doc = Doc()  # a session with no examination: the act's own
        doc.session(1, SessionKind.FEEDING_TUBE)
        doc.act(1, Kind.TUBE_REPLACEMENT)
        self.assertTrue(ready(decide('43762', doc.build())))

    def test_row_7_a_plan_or_a_history_beside_the_sessions_done_examination_holds_nothing(self):
        """The refutation's F1: "Repeat colonoscopy in 3 years." (planned, a later date), "Colonoscopy in 2019 was
        normal." (performed, an earlier date) and an examination by another facility, each filed as an examination
        with its session slot empty - or its session not established, or even established - beside the session's own
        done examination E1: READY, as with the plan in a session of its own. Bidirectional: the EGD's codes too."""
        plan = dict(kind=sup(Kind.EXAMINATION), status=sup(Status.PLANNED), date=sup(ct.DateRelation.LATER_DATE))
        history = dict(kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), date=sup(EARLIER))
        elsewhere = dict(kind=sup(Kind.EXAMINATION), performer=sup(Performer.OTHER_FACILITY))
        for name, over in {'a plan': plan, 'a history': history, 'another performer': elsewhere,
                           'a plan, its session not established': dict(plan, session=unres(X(1))),
                           'a plan filed in the session': dict(plan, session=sup(X(1)))}.items():
            with self.subTest(name):
                doc = colonoscopy()
                doc.event(4, **over)
                R = doc.build()
                self.assertTrue(ready(decide('45385', R)))
                self.assertTrue(ready(decide('45378', R)))
        doc = colonoscopy()  # bidirectional: an EGD X2 beside the colonoscopy, the plan's session slot empty
        doc.session(2, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(5, session=X(2))
        doc.act(6, Kind.BIOPSY, session=X(2), places=[sup(Landmark.STOMACH)])
        doc.event(7, **plan)
        R = doc.build()
        for code in ('45385', '45378', '43239', '43235'):
            with self.subTest(code=code):
                self.assertTrue(ready(decide(code, R)))

    def test_row_7_an_examination_that_may_be_the_sessions_holds_without_its_own_done_one(self):
        """The F1 repair's fail-closed side (P-MONO): with no examination established as the session's and done (an
        act-only session), a plan that may be its examination may be its only one - held, every witness on the plan;
        beside the session's done examination, one that may be it and is in doubt (its status doubted) or denied holds
        too: only an event established as of another occasion (a plan, another date, another performer) adds nothing."""
        doc = Doc()
        doc.session(1, SessionKind.COLONOSCOPY, reached=[sup(Extent.CECUM)])
        doc.act(2, Kind.SNARE, places=[sup(Landmark.SIGMOID_COLON)], device=sup(Device.COLD_SNARE))
        doc.event(4, kind=sup(Kind.EXAMINATION), status=sup(Status.PLANNED), date=sup(ct.DateRelation.LATER_DATE))
        evaluation = self.held('45385', doc.build())
        self.assertEqual({held.subject for held in evaluation.held_facts}, {E(4)})
        self.assertIn(('performed_status', 4, QUESTION, rule(Q.Rule.EXAMINATION)), keys(evaluation))
        for name, status in {'doubted': doubted(Status.PERFORMED), 'denied': neg(Status.PERFORMED)}.items():
            with self.subTest(name):
                doc = colonoscopy()
                doc.event(4, kind=sup(Kind.EXAMINATION), status=status, session=sup(X(1)), date=sup(ON),
                          performer=sup(TEAM), entry=sup(DC))
                self.held('45385', doc.build())

    def test_row_7_an_office_visits_session_holds_no_examination(self):
        """The refutation's F1, its office variant: "Colonoscopy in 2019 was normal." filed as an examination with its
        session slot empty is no examination of the office visit's session (FAMILY_KINDS, D191: the office E/M family
        holds none) - 99213 READY, as with the history in a session of its own. The visit's session kind not
        established leaves an examination possible: held (fail-closed)."""
        def office(kind):
            doc = Doc()
            doc.session(1, kind, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
            doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.TOTAL_TIME))
            doc.event(2, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), date=sup(EARLIER))
            return doc.build()

        self.assertTrue(ready(decide('99213', office(sup(SessionKind.OFFICE_EM)))))
        done = rq.Requirement.SUP_SESSION_DONE
        self.assertEqual(truths('99213', office(sup(SessionKind.OFFICE_EM)), E(1))[done], T)
        self.assertEqual(truths('99213', office(unres(SessionKind.OFFICE_EM)), E(1))[done], U)

    def test_row_7_k2_another_acts_performer_never_touches_the_examination(self):
        """HO-7: a surgeon called in to place clips holds nothing of the endoscopist's snare."""
        doc = colonoscopy()
        doc.act(3, Kind.CLIP, performer=sup(Performer.OTHER_CLINICIAN), places=[sup(Landmark.SIGMOID_COLON)])
        self.assertTrue(ready(decide('45385', doc.build())))
        self.assertTrue(ready(decide('45378', doc.build())))

    def test_row_8_the_relations_of_the_pairing_table(self):
        doc = colonoscopy()  # 4.10's broad denial against the snare: CONTRADICTION, conflict:snare
        doc.event(3, kind=sup(Kind.REMOVAL), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                  breadth=sup(Breadth.ALL_OF_KIND))
        evaluation = self.held('45385', doc.build())
        self.assertEqual(keys(evaluation), [('conflict:snare', 1, QUESTION, 'relation:contradiction')])
        self.assertEqual(set(evaluation.held_facts[0].spans), {unit(2), unit(3)})  # both statements quoted
        self.assertIsNone(evaluation.held_facts[0].result)  # a relation is about no single fact (D189)
        doc = colonoscopy()  # a doubted removal of the same polyp: a possible statement, every row SAME: DOUBT
        doc.event(3, kind=sup(Kind.REMOVAL), status=doubted(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                  lesion=sup(L(1)), places=[sup(Landmark.SIGMOID_COLON)])
        self.assertEqual(keys(self.held('45385', doc.build()))[0],
                         ('performed_status', 2, QUESTION, 'relation:possible_statement'))
        doc = colonoscopy()  # a doubted removal of no stated target: a possible statement, its target row UNRESOLVED
        doc.event(3, kind=sup(Kind.REMOVAL), status=doubted(Status.PERFORMED), session=sup(X(1)), date=sup(ON))
        self.assertEqual(keys(self.held('45385', doc.build()))[0],
                         ('statement_scope', 3, QUESTION, 'relation:possible_statement'))
        doc = colonoscopy()  # an unlisted denial: statement_scope, cause unlisted (3.2.6 rule 4)
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DENIAL, Kind.SNARE, None, Span(900, 950)))
        self.assertEqual(keys(self.held('45385', doc.build())), [('statement_scope', 3, QUESTION, 'unlisted')])

    def test_row_8_an_independent_statement_holds_nothing(self):
        """HO-2: one established difference sets a statement apart ("At the 2024 colonoscopy ... no dilation was
        performed." beside today's dilation)."""
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.DILATION, places=[sup(Landmark.ANASTOMOSIS)], device=sup(Device.BALLOON))
        doc.event(3, kind=sup(Kind.DILATION), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(EARLIER),
                  breadth=sup(Breadth.ALL_OF_KIND))
        self.assertTrue(ready(decide('45386', doc.build())))

    def test_the_em_encounter(self):
        def visit(encounter):
            doc = Doc()
            doc.session(1, SessionKind.OFFICE_EM, encounter=encounter)
            doc.act(1, Kind.EM_VISIT)
            return doc.build()

        self.assertTrue(ready(decide('99213', visit(sup(ct.EncounterRelation.THIS_ENCOUNTER)))))
        self.assertEqual(keys(decide('99213', visit(unres(ct.EncounterRelation.THIS_ENCOUNTER)))),
                         [('event_time', 6, QUESTION, 'appraisal:unclear')])
        self.assertEqual(keys(decide('99213', visit(sup(ct.EncounterRelation.SEPARATE_ENCOUNTER)))),
                         [('event_time', 6, QUESTION, rule(Q.Rule.ENCOUNTER))])


# --- the code-specific rows (4.3's second table) ------------------------------------------------------------------------


def dilation(*places, device=sup(Device.BALLOON), lesion=None, number=2, doc=None):
    doc = doc if doc is not None else egd()
    doc.act(number, Kind.DILATION, places=list(places), device=device, lesion=lesion)
    return doc


def eus_fna(stations=(), reached=(sup(Extent.DUODENUM),), tract=sup(ct.Tract.UPPER), complete=None) -> FactSet:
    """An EUS session X1 (its examination E1) with an FNA E2: its tract, stations, reach and completeness claim."""
    doc = Doc()
    doc.session(1, SessionKind.EUS, tract=tract, stations=list(stations), reached=list(reached))
    if complete is not None:
        doc.completeness[X(1)] = complete
    doc.exam(1)
    doc.act(2, Kind.FNA)
    return doc.build()


def ercp_doc(*acts) -> FactSet:
    """An ERCP session X1 (its examination E1) with ``acts``: (number, kind, facts) each."""
    doc = Doc()
    doc.session(1, SessionKind.ERCP)
    doc.exam(1)
    for number, kind, over in acts:
        doc.act(number, kind, **over)
    return doc.build()


def denial_event(doc, number=3, kind=Kind.DILATION, **over):
    """A current broad denial (status negated, all of its kind, today, in X1) with its kind and status words."""
    base = dict(kind=sup(kind), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                breadth=sup(Breadth.ALL_OF_KIND), kind_words=Span(100 * number + 3, 100 * number + 11),
                status_words=Span(100 * number, 100 * number + 25))
    base.update(over)
    return doc.event(number, **base)


def shared_sentence() -> FactSet:
    """C-10's shared-sentence fixture: "The anastomotic stricture, which had not been dilated at the 2024
    colonoscopy, was dilated today to 15 mm with a through-the-scope balloon." (offsets 300-420). Gemini dropped
    today's dilation; the only dilation statement is the historical denial in the very sentence the code cites: its
    target words 300-325, its kind and status words 327-348, its timing words 348-372 (each a statement source located
    in the sentence's unit, D188)."""
    doc = colonoscopy(snare=False)
    sentence = Span(300, 420)
    doc.event(3, anchor=(sentence,), kind=sup(Kind.DILATION), status=neg(Status.PERFORMED), session=sup(X(1)),
              date=sup(EARLIER, cited=statement_source(sentence, Span(348, 372))),
              breadth=sup(Breadth.SINGLE_TARGET),
              places=[sup(Landmark.ANASTOMOSIS, cited=statement_source(sentence, Span(300, 325)))],
              kind_words=Span(341, 348), status_words=Span(327, 348))
    return doc.build()


def two_snares() -> FactSet:
    """HO-8's first case: E2's performer not established (rank 7), E3's date contradicted (rank 1)."""
    doc = colonoscopy(performer=unres(TEAM))
    doc.act(3, Kind.SNARE, date=contra(ON, EARLIER), places=[sup(Landmark.RECTUM)])
    return doc.build()


class CodeRows(SimpleTestCase):
    """4.3's code-specific rows over every supporting act (4.4's code_requirements), met, unmet and established
    otherwise."""

    def test_tech(self):
        esophageal = sup(Landmark.DISTAL_ESOPHAGUS)
        self.assertTrue(ready(decide('43249', dilation(esophageal).build())))
        cases = {Device.WIRE_BOUGIE: ('technique', 10, EXPLANATION, rule(Q.Rule.TECHNIQUE)),
                 Device.OTHER: ('technique', 10, QUESTION, rule(Q.Rule.TECHNIQUE))}
        for device, expected in cases.items():
            with self.subTest(device=device):
                self.assertEqual(keys(decide('43249', dilation(esophageal, device=sup(device)).build())), [expected])
        self.assertEqual(keys(decide('43249', dilation(esophageal, device=unres(Device.BALLOON)).build())),
                         [('technique', 10, QUESTION, 'appraisal:unclear')])
        self.assertEqual(keys(decide('43249', dilation(esophageal, device=None).build())),
                         [('technique', 10, QUESTION, 'reading_unknown')])
        evaluation = decide('43249', dilation(esophageal, device=sup(Device.WIRE_BOUGIE)).build())
        self.assertEqual(evaluation.supporting, (E(2),))  # the act stays in E*; the code is held, never excluded
        self.assertIsNone(evaluation.exclusion)

    def test_site(self):
        self.assertTrue(ready(decide('43249', dilation(sup(Landmark.DISTAL_ESOPHAGUS)).build())))
        self.assertTrue(ready(decide('43245', dilation(sup(Landmark.PYLORUS)).build())))
        self.assertEqual(keys(decide('43245', dilation(sup(Landmark.DISTAL_ESOPHAGUS)).build())),
                         [('act_target', 11, EXPLANATION, rule(Q.Rule.SITE))])
        for places in ((sup(Landmark.ANASTOMOSIS),), (), (unres(Landmark.PYLORUS),),
                       (sup(Landmark.DISTAL_ESOPHAGUS), sup(Landmark.STOMACH)),
                       (sup(Landmark.DISTAL_ESOPHAGUS), sup(Landmark.ANASTOMOSIS))):
            with self.subTest(places=[place.value for place in places]):
                found = keys(decide('43249', dilation(*places).build()))
                self.assertEqual([entry[:3] for entry in found], [('act_target', 11, QUESTION)])

    def test_site_reads_the_supported_place_of_the_supported_lesion(self):
        doc = dilation(lesion=sup(L(1)))
        doc.lesion(1, lesion_places=[sup(Landmark.DISTAL_ESOPHAGUS)])
        self.assertTrue(ready(decide('43249', doc.build())))
        self.assertEqual([entry[:3] for entry in keys(decide('43245', doc.build()))],
                         [('act_target', 11, EXPLANATION)])
        doc = dilation(lesion=unres(L(1)))  # a lesion not established: which structure, a question
        doc.lesion(1, lesion_places=[sup(Landmark.DISTAL_ESOPHAGUS)])
        self.assertEqual([entry[:3] for entry in keys(decide('43249', doc.build()))], [('act_target', 11, QUESTION)])

    def test_structure_43240(self):
        def drainage(structure, *places):
            doc = Doc()
            doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.UPPER))
            doc.exam(1)
            doc.act(2, Kind.DRAINAGE, structure=structure, places=list(places))
            return doc.build()

        pfc = sup(ct.Structure.PANCREATIC_FLUID_COLLECTION)
        self.assertTrue(ready(decide('43240', drainage(pfc, sup(Landmark.PANCREAS)))))
        self.assertEqual(keys(decide('43240', drainage(sup(ct.Structure.GALLBLADDER), sup(Landmark.GALLBLADDER)))),
                         [('target', 12, EXPLANATION, rule(Q.Rule.STRUCTURE))])
        self.assertEqual(keys(decide('43240', drainage(pfc, sup(Landmark.BILE_DUCT)))),
                         [('target', 12, EXPLANATION, rule(Q.Rule.STRUCTURE))])  # D120: a place set apart
        self.assertEqual(keys(decide('43240', drainage(unres(ct.Structure.PANCREATIC_FLUID_COLLECTION)))),
                         [('target', 12, QUESTION, 'appraisal:unclear')])

    def test_route_43253(self):
        def injection(route):
            doc = Doc()
            doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.UPPER))
            doc.exam(1)
            doc.act(2, Kind.INJECTION, route=route)
            return doc.build()

        self.assertTrue(ready(decide('43253', injection(sup(ct.Route.EUS_TRANSMURAL)))))
        self.assertEqual(keys(decide('43253', injection(sup(ct.Route.SUBMUCOSAL)))),
                         [('technique', 10, EXPLANATION, rule(Q.Rule.ROUTE))])
        self.assertEqual(keys(decide('43253', injection(unres(ct.Route.EUS_TRANSMURAL)))),
                         [('technique', 10, QUESTION, 'appraisal:unclear')])

    def eus(self, *args, **kw):
        return eus_fna(*args, **kw)

    def test_tract(self):
        every = [sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)]
        self.assertTrue(ready(decide('43259', self.eus(every))))
        self.assertEqual(keys(decide('43259', self.eus(every, tract=sup(ct.Tract.LOWER)))),
                         [('procedure', 8, EXPLANATION, rule(Q.Rule.TRACT))])
        self.assertEqual(keys(decide('43259', self.eus(every, tract=unres(ct.Tract.UPPER)))),
                         [('procedure', 8, QUESTION, 'appraisal:unclear')])

    def test_stations(self):
        every = [sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)]
        self.assertTrue(ready(decide('43242', self.eus(every))))
        self.assertTrue(ready(decide('43242', self.eus((), complete=Res.SUPPORTED))))  # [R:SC-B]: the completeness claim
        for name, R in {'an empty list alone (BF6)': self.eus(()),
                        'an empty list, completeness rejected': self.eus((), complete=Res.UNRESOLVED),
                        'the esophagus left out': self.eus(every[1:]),
                        'no reach to the duodenum': self.eus(every, reached=(sup(Extent.STOMACH),))}.items():
            with self.subTest(name):
                self.assertEqual([entry[:3] for entry in keys(decide('43242', R))], [('exam_stations', 13, QUESTION)])
        denied = [sup(Station.ESOPHAGUS), neg(Station.STOMACH), sup(Station.DUODENUM)]
        self.assertEqual(keys(decide('43242', self.eus(denied))),
                         [('exam_stations', 13, EXPLANATION, rule(Q.Rule.STATIONS))])

    def test_limited_reads_the_egd_in_the_codes_profile(self):
        """Step 1f's hand-off #7: 43231/43232 need a reach short of the duodenum; 43237/43238 (their profile includes the
        EGD) a station negated or a reach short; all three examined is the class explanation."""
        self.assertTrue(catalogue.includes_examination('43237', SessionKind.EGD))
        self.assertFalse(catalogue.includes_examination('43231', SessionKind.EGD))
        short = (sup(Extent.STOMACH),)
        self.assertTrue(ready(decide('43231', self.eus((), reached=short))))
        self.assertEqual(keys(decide('43231', self.eus(()))),
                         [('exam_stations', 13, QUESTION, rule(Q.Rule.LIMITED))])  # reached the duodenum: no message
        self.assertTrue(ready(decide('43237', self.eus((neg(Station.DUODENUM),)))))
        self.assertTrue(ready(decide('43237', self.eus((), reached=short))))
        every = [sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)]
        self.assertEqual(keys(decide('43237', self.eus(every))),
                         [('exam_stations', 13, EXPLANATION, rule(Q.Rule.LIMITED))])
        # all three examined beside a reach stated short: the class explanation still (fail-closed)
        self.assertEqual(keys(decide('43237', self.eus(every, reached=short))),
                         [('exam_stations', 13, EXPLANATION, rule(Q.Rule.LIMITED))])
        self.assertEqual([entry[:3] for entry in keys(decide('43237', self.eus(every[:2])))],
                         [('exam_stations', 13, QUESTION)])

    def test_limited_and_stations_read_only_the_upper_stations(self):
        """The refutation's F5: a negated station outside the upper tract (the jejunum) is no station of either class.
        43237 with the three upper stations examined is the limited class's explanation, resting on an examined
        station (D189: its result supported, never the jejunum's negated); 43242 with them is READY."""
        every = [sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)]
        R = self.eus([neg(Station.JEJUNUM), *every])
        evaluation = decide('43237', R)
        self.assertEqual(keys(evaluation), [('exam_stations', 13, EXPLANATION, rule(Q.Rule.LIMITED))])
        self.assertEqual(evaluation.held_facts[0].result, Res.SUPPORTED)
        self.assertTrue(ready(decide('43242', R)))

    def test_lower(self):
        def lower(*reached, approach=None, stoma=False):
            doc = Doc()
            doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=list(reached), approach=approach)
            if stoma:
                doc.entry(1, type=sup(ct.AnatomyType.STOMA))
            doc.exam(1)
            return doc.build()

        self.assertTrue(ready(decide('45341', lower(sup(Extent.SIGMOID_COLON)))))
        self.assertEqual(keys(decide('45341', lower(sup(Extent.CECUM)))),
                         [('extent', 14, EXPLANATION, rule(Q.Rule.LOWER))])
        self.assertEqual([entry[:3] for entry in keys(decide('45341', lower()))], [('extent', 14, QUESTION)])
        self.assertTrue(ready(decide('44406', lower(sup(Extent.STOMA), approach=sup(ct.Approach.THROUGH_STOMA),
                                                    stoma=True))))
        for name, R in {'no stoma entry': lower(sup(Extent.STOMA), approach=sup(ct.Approach.THROUGH_STOMA)),
                        'the approach not stated': lower(sup(Extent.STOMA), stoma=True),
                        'the approach not established': lower(sup(Extent.STOMA), approach=unres(ct.Approach.ORAL),
                                                              stoma=True)}.items():
            with self.subTest(name):
                self.assertEqual([entry[:3] for entry in keys(decide('44406', R))], [('extent', 14, QUESTION)])
        # the refutation's F4: an approach established otherwise is the misfit, the class explanation (4.3 LOWER)
        for name, approach in {'oral supported': sup(ct.Approach.ORAL),
                               'through a stoma denied': neg(ct.Approach.THROUGH_STOMA)}.items():
            with self.subTest(name):
                R = lower(sup(Extent.STOMA), approach=approach, stoma=True)
                self.assertEqual(keys(decide('44406', R)), [('extent', 14, EXPLANATION, rule(Q.Rule.LOWER))])
                self.assertEqual(item('44406', R).message, Q.MessageId.EXAMINATION_CLASS)

    def ercp(self, *acts):
        return ercp_doc(*acts)

    def test_yield_is_a_filter_of_support(self):
        stones = dict(yield_=sup(ct.Material.STONES))
        self.assertTrue(ready(decide('43264', self.ercp((2, Kind.STONE_EXTRACTION, stones)))))
        nothing = dict(yield_=neg(ct.Material.ANYTHING))
        self.assertEqual(keys(decide('43264', self.ercp((2, Kind.STONE_EXTRACTION, nothing)))),
                         [('act_yield', 15, EXPLANATION, rule(Q.Rule.YIELD))])
        # 4.3: "negated: no support from that act" - the other sweep supports, READY on it alone
        evaluation = decide('43264', self.ercp((2, Kind.STONE_EXTRACTION, nothing), (3, Kind.STONE_EXTRACTION, stones)))
        self.assertTrue(ready(evaluation))
        self.assertEqual(evaluation.supporting, (E(3),))
        conflict = dict(yield_=contra(ct.Material.STONES, ct.Material.ANYTHING))
        self.assertEqual(keys(decide('43264', self.ercp((2, Kind.STONE_EXTRACTION, conflict)))),
                         [('conflict:stone_extraction', 1, QUESTION, 'reading_contradicted')])
        self.assertEqual([entry[:3] for entry in keys(decide('43264', self.ercp((2, Kind.STONE_EXTRACTION, {}))))],
                         [('act_yield', 15, QUESTION)])

    def test_cause(self):
        def bleeding(**over):
            doc = egd()
            doc.act(2, Kind.BLEEDING_CONTROL, **over)
            return doc.build()

        lesion = dict(purpose=sup(ct.Purpose.HEMOSTASIS), cause=sup(ct.Cause.PRE_EXISTING_LESION))
        self.assertTrue(ready(decide('43255', bleeding(**lesion))))
        self.assertEqual(keys(decide('43255', bleeding(purpose=sup(ct.Purpose.HEMOSTASIS),
                                                       cause=sup(ct.Cause.ACT_OF_THIS_SESSION)))),
                         [('performed_status', 18, EXPLANATION, rule(Q.Rule.CAUSE))])
        self.assertEqual(keys(decide('43255', bleeding(purpose=sup(ct.Purpose.PROPHYLAXIS)))),
                         [('performed_status', 18, EXPLANATION, rule(Q.Rule.CAUSE))])
        self.assertEqual([entry[:3] for entry in keys(decide('43255', bleeding(purpose=sup(ct.Purpose.HEMOSTASIS))))],
                         [('act_cause', 17, QUESTION)])

    def test_xchg_a_placement_beside_a_possible_removal(self):
        """D105: a stent removal and a placement nothing sets apart are a possible exchange; 43274 is held (the duct,
        or whether the two were one exchange), never READY; set apart by duct, READY."""
        biliary, pancreatic = sup(ct.Duct.BILIARY), sup(ct.Duct.PANCREATIC)
        for removal_duct, expected in ((biliary, ('performed_status', 4, QUESTION, rule(Q.Rule.EXCHANGE))),
                                       (None, ('act_target', 11, QUESTION, rule(Q.Rule.EXCHANGE)))):
            with self.subTest(duct=removal_duct):
                R = self.ercp((2, Kind.STENT, dict(duct=biliary)), (3, Kind.STENT_REMOVAL, dict(duct=removal_duct)))
                self.assertEqual(keys(decide('43274', R)), [expected])
                self.assertEqual(keys(decide('43275', R)), [expected])
        R = self.ercp((2, Kind.STENT, dict(duct=biliary)), (3, Kind.STENT_REMOVAL, dict(duct=pancreatic)))
        self.assertTrue(ready(decide('43274', R)))
        R = self.ercp((2, Kind.STENT, dict(duct=biliary)),
                      (3, Kind.STENT_REMOVAL, dict(duct=biliary, status=neg(Status.PERFORMED))))
        self.assertTrue(ready(decide('43274', R)))  # X1: the removal negated - 43274 can be READY

    def test_xchg_43276_by_an_exchange_or_by_a_removal_and_a_placement_in_one_duct(self):
        biliary = sup(ct.Duct.BILIARY)
        self.assertTrue(ready(decide('43276', self.ercp((2, Kind.STENT_EXCHANGE, {})))))
        R = self.ercp((2, Kind.STENT, dict(duct=biliary)), (3, Kind.STENT_REMOVAL, dict(duct=biliary)))
        evaluation = decide('43276', R)
        self.assertTrue(ready(evaluation))
        self.assertEqual(set(evaluation.supporting), {E(2), E(3)})
        R = self.ercp((2, Kind.STENT, dict(duct=biliary)), (3, Kind.STENT_REMOVAL, {}))
        evaluation = decide('43276', R)
        self.assertEqual(keys(evaluation), [('act_target', 11, QUESTION, rule(Q.Rule.EXCHANGE))])
        self.assertEqual(evaluation.bindings, {(Kind.STENT_EXCHANGE,): E(3)})
        R = self.ercp((2, Kind.STENT, dict(duct=biliary)),
                      (3, Kind.STENT_REMOVAL, dict(duct=biliary, status=neg(Status.PERFORMED))))
        self.assertEqual(keys(decide('43276', R)), [('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED))])


# --- v1's per-code rule tests, re-expressed (tests/test_interpretation_events.py) ---------------------------------------


class V1RuleRows(SimpleTestCase):
    """RuleRows: R2-R4 of v1's 7.2. R1 (scope, exact evidence) is assess's (step 5a), before the rule; R5's bundling
    is coverage's (step 4b); R6, R7 and R9 are assess's (4.4)."""

    def test_r2_a_code_with_no_profile_is_held_never_ready(self):
        """C-6: 45305 (an unprofiled code) beside a performed examination and a biopsy denial: held, one explanation."""
        doc = Doc()
        doc.session(1, SessionKind.OTHER_GI)
        doc.exam(1)
        doc.event(2, kind=sup(Kind.BIOPSY), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                  breadth=sup(Breadth.ALL_OF_KIND))
        evaluation = decide('45305', doc.build(), kept=(unit(1),))
        self.assertEqual(keys(evaluation), [('performed_status', 4, EXPLANATION, rule(Q.Rule.UNPROFILED))])
        self.assertEqual((evaluation.supporting, evaluation.exclusion), ((), None))

    def test_r3_a_supporting_event_makes_the_act_code_ready(self):
        evaluation = decide('45385', colonoscopy().build(), kept=(unit(2),))
        self.assertTrue(ready(evaluation))
        self.assertEqual(evaluation.supporting, (E(2),))

    def test_r4_the_device_class_of_a_technique_code(self):
        esophageal = sup(Landmark.DISTAL_ESOPHAGUS)
        self.assertTrue(ready(decide('43249', dilation(esophageal).build())))
        self.assertEqual(keys(decide('43249', dilation(esophageal, device=None).build()))[0][:3],
                         ('technique', 10, QUESTION))
        savary = decide('43249', dilation(esophageal, device=sup(Device.WIRE_BOUGIE)).build())
        self.assertEqual(keys(savary)[0][:3], ('technique', 10, EXPLANATION))
        self.assertIsNone(savary.exclusion)  # h6: never excluded


EUS_ACT_CODES = tuple(code for code, row in catalogue.CODES.items()
                      if row.family is SessionKind.EUS and len(row.covers) > 1)
EUS_EXAM_CODES = tuple(code for code, row in catalogue.CODES.items()
                       if row.family is SessionKind.EUS and row.covers == (Kind.EXAMINATION,))


class ExaminationIsTheSession(SimpleTestCase):
    """C-1: every EUS code covers the examination (the session); a code covering it beside another kind needs a
    supporting act of that other kind. One test per EUS code. v1 counted E* before the class checks; here E* is
    SUPPORT's (rows 1-8), so the FNA codes are read through their E* and their acts, never their class."""

    def eus(self, *more, tract=ct.Tract.UPPER):
        doc = Doc()
        doc.session(1, SessionKind.EUS, tract=sup(tract), reached=[sup(Extent.DUODENUM)],
                    stations=[sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)])
        doc.exam(1, places=[sup(Landmark.PANCREAS)])
        for number, kind, over in more:
            doc.act(number, kind, **over)
        return doc.build()

    def test_the_eus_codes_are_all_covered_here(self):
        self.assertEqual(len(EUS_ACT_CODES) + len(EUS_EXAM_CODES), 14)

    def test_every_act_code_on_an_examination_only_document_is_never_ready(self):
        R = self.eus()
        for code in EUS_ACT_CODES:
            with self.subTest(code=code):
                evaluation = decide(str(code), R, kept=(unit(1),))
                self.assertFalse(ready(evaluation))
                self.assertNotIn(E(1), evaluation.supporting)

    def test_every_act_code_beside_its_acts_denial_is_never_ready(self):
        R = self.eus((2, Kind.FNA, dict(status=neg(Status.PERFORMED), breadth=sup(Breadth.ALL_OF_KIND))))
        for code in EUS_ACT_CODES:
            with self.subTest(code=code):
                self.assertFalse(ready(decide(str(code), R, kept=(unit(1),))))

    def test_an_fna_code_with_the_sampling_is_supported_by_it(self):
        for code in EUS_ACT_CODES:
            if Kind.FNA not in catalogue.CODES[code].covers:
                continue
            tract = ct.Tract.LOWER if code in catalogue.LOWER_EUS_CLASS else ct.Tract.UPPER
            with self.subTest(code=code):
                self.assertEqual(decide(str(code), self.eus((2, Kind.FNA, {}), tract=tract)).supporting, (E(2),))

    def test_an_injection_or_drainage_code_needs_its_own_act_not_the_fna(self):
        R = self.eus((2, Kind.FNA, {}))
        for code in EUS_ACT_CODES:
            if Kind.FNA in catalogue.CODES[code].covers:
                continue
            with self.subTest(code=code):
                evaluation = decide(str(code), R)
                self.assertFalse(ready(evaluation))
                self.assertEqual(evaluation.supporting, ())

    def test_every_examination_only_code_is_supported_by_the_examination(self):
        for code in EUS_EXAM_CODES:
            tract = ct.Tract.LOWER if code in catalogue.LOWER_EUS_CLASS else ct.Tract.UPPER
            with self.subTest(code=code):
                self.assertEqual(decide(str(code), self.eus(tract=tract)).supporting, (E(1),))

    def test_the_requirement_groups(self):
        self.assertEqual(catalogue.requirements(catalogue.code_link('43242')), ((Kind.FNA,),))
        self.assertEqual(catalogue.requirements(catalogue.code_link('43259')), ((Kind.EXAMINATION,),))
        self.assertEqual(catalogue.requirements(catalogue.code_link('45378')), ((Kind.EXAMINATION,),))
        self.assertEqual(catalogue.requirements(catalogue.code_link('45381')), ((Kind.INJECTION, Kind.TATTOO),))
        self.assertEqual(catalogue.requirements(catalogue.code_link('46221')), ((Kind.BAND_LIGATION,),))
        self.assertEqual(catalogue.requirements(catalogue.code_link('45305')), ())


class DefiningKinds(SimpleTestCase):
    """D27 (fb13: 43265 READY on a balloon extraction): a code D27 narrows is matched only by an act of its defining
    kind. accounted() is catalogue's (step 1e's hand-off #5: called, never forked)."""

    def ercp(self, *acts):
        doc = Doc()
        doc.session(1, SessionKind.ERCP)
        doc.exam(1)
        for number, kind, over in acts:
            doc.act(number, kind, **over)
        return doc.build()

    def test_the_lithotripsy_code_on_a_balloon_extraction_is_held_not_documented_and_43264_stays_ready(self):
        R = self.ercp((3, Kind.STONE_EXTRACTION, dict(yield_=sup(ct.Material.STONES))))
        self.assertEqual(decide('43264', R).supporting, (E(3),))
        self.assertEqual(keys(decide('43265', R)), [('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED))])

    def test_the_lithotripsy_code_with_its_lithotripsy_is_supported(self):
        R = self.ercp((4, Kind.LITHOTRIPSY, {}))
        self.assertEqual(decide('43265', R).supporting, (E(4),))

    def test_r3s_failure_path_reads_the_defining_kinds_only(self):
        """A denial of the defining act the code cites excludes it; a denial of the act another code accounts for alone
        no longer concerns it."""
        denial = dict(status=neg(Status.PERFORMED), breadth=sup(Breadth.ALL_OF_KIND), kind_words=Span(400, 460))
        R = self.ercp((4, Kind.LITHOTRIPSY, denial))
        evaluation = decide('43265', R, kept=(Span(400, 460),))
        self.assertEqual(evaluation.exclusion.event, E(4))
        R = self.ercp((3, Kind.STONE_EXTRACTION, dict(denial, kind_words=Span(300, 360))))
        self.assertIsNotNone(decide('43264', R, kept=(Span(300, 360),)).exclusion)
        self.assertEqual(keys(decide('43265', R, kept=(Span(300, 360),))),
                         [('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED))])

    def test_the_hot_forceps_and_gastrostomy_codes_need_their_defining_act(self):
        doc = Doc()
        doc.session(1, SessionKind.ENTEROSCOPY)
        doc.exam(1)
        doc.act(2, Kind.ABLATION)
        R = doc.build()
        self.assertEqual(keys(decide('44365', R)), [('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED))])
        doc.act(3, Kind.HOT_BIOPSY)
        self.assertEqual(decide('44365', doc.build()).supporting, (E(3),))
        doc = Doc()
        doc.session(1, SessionKind.FEEDING_TUBE)
        doc.act(1, Kind.TUBE_PLACEMENT)
        self.assertTrue(ready(decide('49441', doc.build())))
        self.assertEqual(keys(decide('49440', doc.build()))[0][:3], ('performed_status', 4, QUESTION))

    def test_the_requirement_groups_of_the_narrowed_codes(self):
        self.assertEqual([catalogue.requirements(catalogue.code_link(code)) for code in ('43265', '44365', '49440')],
                         [((Kind.LITHOTRIPSY,),), ((Kind.HOT_BIOPSY,),), ((Kind.PEG,),)])
        self.assertEqual(catalogue.accounted(catalogue.code_link('43265')), (Kind.LITHOTRIPSY,))
        self.assertEqual(catalogue.accounted(catalogue.code_link('43242')), (Kind.FNA,))


class DilationSite(SimpleTestCase):
    """D29 (fb07: 43249 READY on a gastrojejunal anastomotic stricture): a site-specific dilation code is met only by a
    dilation established in its class - directly or through its supported lesion's places. One established outside the
    class is the another-site explanation; one whose place is not settled asks which structure was dilated. Never
    excluded; every other dilation code is unaffected."""

    def test_an_esophageal_dilation_meets_the_esophageal_code_only(self):
        R = dilation(sup(Landmark.DISTAL_ESOPHAGUS)).build()
        self.assertTrue(ready(decide('43249', R)))
        self.assertEqual(keys(decide('43245', R))[0][:3], ('act_target', 11, EXPLANATION))

    def test_a_pyloric_dilation_meets_the_gastric_or_duodenal_code_only(self):
        R = dilation(sup(Landmark.PYLORUS)).build()
        self.assertTrue(ready(decide('43245', R)))
        self.assertEqual(keys(decide('43249', R))[0][:3], ('act_target', 11, EXPLANATION))

    def test_an_anastomotic_or_unplaced_dilation_asks_which_structure_was_dilated(self):
        for places in ((sup(Landmark.ANASTOMOSIS),), ()):
            for code in ('43249', '43245'):
                with self.subTest(places=len(places), code=code):
                    evaluation = decide(code, dilation(*places).build())
                    self.assertEqual(keys(evaluation)[0][:3], ('act_target', 11, QUESTION))
                    self.assertIsNone(evaluation.exclusion)

    def test_codes_not_in_the_table_are_unaffected(self):
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.DILATION, places=[sup(Landmark.ANASTOMOSIS)], device=sup(Device.BALLOON))
        self.assertTrue(ready(decide('45386', doc.build())))
        self.assertIsNone(rq.spec('45386').row.site)


class AnastomosisSite(SimpleTestCase):
    """D34 placed an anastomosis by the encounter's one anatomy entry's type words. v2's act has no claimed
    target.anatomy (CLAIMED, 3.2.1) and SITE reads its places and its lesion's only (requirements.RULES), so an
    anastomotic dilation's site stays unsettled - asked, never READY, never excluded (fail-closed; the step's NOTES,
    question Q5)."""

    def test_an_anastomosis_entry_does_not_place_the_dilation(self):
        doc = dilation(sup(Landmark.ANASTOMOSIS))
        doc.entry(1, type=sup(ct.AnatomyType.ANASTOMOSIS), subtype=sup(ct.AnastomosisSubtype.GASTROJEJUNAL))
        for code in ('43249', '43245'):
            with self.subTest(code=code):
                self.assertEqual(keys(decide(code, doc.build()))[0][:3], ('act_target', 11, QUESTION))


class Focused(SimpleTestCase):
    """v1's 7.4 h1-h5 and C-9, each now a witness at its RANK row; the one question is RANK's (tests/v2/
    test_questions.py)."""

    def test_h1_a_contradiction_quotes_both_sides(self):
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.REMOVAL), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                  breadth=sup(Breadth.ALL_OF_KIND))
        found = item('45385', doc.build())
        self.assertEqual((found.held.fact, found.held.rank, found.message), ('conflict:snare', 1, Q.MessageId.CONFLICT))
        self.assertEqual(found.fill.statements, ((unit(3),),))

    def test_h2_a_doubt_and_the_candidates_own_doubted_status(self):
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.REMOVAL), status=doubted(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                  lesion=sup(L(1)), places=[sup(Landmark.SIGMOID_COLON)])
        self.assertEqual(item('45385', doc.build()).held.rank, 2)
        found = item('45385', colonoscopy(status=doubted(Status.PERFORMED)).build())
        self.assertEqual((found.held.fact, found.held.rank, found.message), ('performed_status', 2,
                                                                             Q.MessageId.DOUBT))

    def test_h3_an_unresolved_relation_asks_its_rows_fact(self):
        """4.5: an established denial whose timing is not established asks event_time (the timing row); one whose
        breadth is not established asks statement_scope."""
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.REMOVAL), status=neg(Status.PERFORMED), session=sup(X(1)), date=unres(ON),
                  breadth=sup(Breadth.ALL_OF_KIND))
        self.assertEqual(keys(decide('45385', doc.build())), [('event_time', 6, QUESTION, 'relation:unresolved')])
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.REMOVAL), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON))
        self.assertEqual(keys(decide('45385', doc.build())), [('statement_scope', 3, QUESTION, 'relation:unresolved')])

    def test_h4_each_unestablished_fact_of_rows_1_to_6(self):
        cases = {'event_time': dict(date=unres(ON)), 'event_performer': dict(performer=unres(TEAM)),
                 'performed_status': dict(status=unres(Status.PERFORMED)), 'procedure': dict(session=unres(X(1)))}
        for fact, over in cases.items():
            with self.subTest(fact=fact):
                found = item('45385', colonoscopy(**over).build())
                self.assertEqual(found.held.fact, fact)
                self.assertEqual(found.kind, QUESTION)

    def test_h5_a_removal_of_unstated_method_asks_the_method(self):
        found = item('45385', colonoscopy(kind=sup(Kind.REMOVAL)).build())
        self.assertEqual((found.held.fact, found.message), ('act_method', Q.MessageId.METHOD))

    def test_c9_an_act_begun_and_not_completed_is_held_never_excluded(self):
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.EMR, status=sup(Status.ATTEMPTED_NOT_COMPLETED), places=[sup(Landmark.ASCENDING_COLON)])
        doc.event(3, kind=sup(Kind.EMR), status=sup(Status.ATTEMPTED_NOT_COMPLETED), session=sup(X(1)),
                  date=sup(ON), kind_words=unit(3))
        evaluation = decide('45390', doc.build(), kept=(unit(3),))
        self.assertIsNone(evaluation.exclusion)
        self.assertEqual(item('45390', doc.build(), kept=(unit(3),)).message, Q.MessageId.ATTEMPTED)

    def test_an_examination_begun_and_not_completed_supports_its_base_code(self):
        doc = colonoscopy(snare=False)
        doc.exam(1, status=sup(Status.ATTEMPTED_NOT_COMPLETED))
        self.assertTrue(ready(decide('45378', doc.build())))

    def test_rule_order_a_contradiction_wins_over_an_unusable_attribute(self):
        """The sigmoid snare E2 has only an unresolved time; the rectal snare E4 is the positive side of a
        CONTRADICTION (the rectal polyp stated not removed). The one question is the conflict - never E2's time."""
        doc = colonoscopy(date=unres(ON))
        doc.lesion(2, lesion_places=[sup(Landmark.RECTUM)], distinct_from=[sup(L(1))])
        doc.act(4, Kind.SNARE, lesion=sup(L(2)), places=[sup(Landmark.RECTUM)])
        doc.event(5, kind=sup(Kind.REMOVAL), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                  breadth=sup(Breadth.SINGLE_TARGET), lesion=sup(L(2)), places=[sup(Landmark.RECTUM)])
        doc.controls.update({(E(2), A.TARGET_LESION, L(2)): True, (E(5), A.TARGET_LESION, L(1)): True,
                             (E(2), A.TARGET_PLACES, Landmark.RECTUM): True,
                             (E(5), A.TARGET_PLACES, Landmark.SIGMOID_COLON): True})
        R = doc.build()
        evaluation = decide('45385', R)
        self.assertEqual(evaluation.bindings, {(Kind.SNARE,): E(4)})
        found = item('45385', R)
        self.assertEqual((found.held.fact, found.held.subject), ('conflict:snare', E(4)))
        self.assertIn(('event_time', 6, QUESTION, 'appraisal:unclear'), keys(evaluation))  # E2's witness kept


class Exclusion(SimpleTestCase):
    """4.6: the only path to EXCLUDED besides R1 and member answers. v1's bases (a negator, a planning or time
    marker, a titled name: EB3) retire: the deciding fact is an ESTABLISHED one."""

    def denial(self, doc, number=3, kind=Kind.DILATION, **over):
        return denial_event(doc, number, kind, **over)

    def excluded(self, evaluation, attribute):
        self.assertIsNotNone(evaluation.exclusion)
        self.assertEqual((evaluation.exclusion.fact, evaluation.exclusion.cover), (attribute, Cover.CITATION))
        self.assertEqual((evaluation.supporting, evaluation.held_facts), ((), ()))

    def scope(self, evaluation):
        self.assertIsNone(evaluation.exclusion)
        self.assertEqual([entry[:3] for entry in keys(evaluation)], [('statement_scope', 3, QUESTION)])

    def test_status_negated_cited_within_its_own_words(self):
        doc = colonoscopy(snare=False)
        self.denial(doc)
        self.excluded(decide('45386', doc.build(), kept=(Span(300, 325),)), A.STATUS)

    def test_status_planned(self):
        doc = colonoscopy(snare=False)
        self.denial(doc, status=sup(Status.PLANNED), breadth=None, date=sup(ct.DateRelation.LATER_DATE))
        self.excluded(decide('45386', doc.build(), kept=(Span(300, 325),)), A.STATUS)

    def test_another_date_established(self):
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.BIOPSY)
        self.denial(doc, kind=Kind.SNARE, status=sup(Status.PERFORMED), date=sup(EARLIER), breadth=None)
        self.excluded(decide('45385', doc.build(), kept=(Span(300, 325),)), A.DATE_RELATION)

    def test_another_performer_established_and_c10_reaching_the_performers_words(self):
        """The code cites the statement's own act words: excluded by the established other clinician. C-10's union is
        the statement's kind, status, target and timing words, so a citation reaching the performer's name gives
        statement_scope instead - never an exclusion."""
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.BIOPSY)
        self.denial(doc, kind=Kind.SNARE, status=sup(Status.PERFORMED), breadth=None,
                    performer=sup(Performer.OTHER_CLINICIAN), kind_words=Span(315, 321), status_words=Span(315, 321))
        self.excluded(decide('45385', doc.build(), kept=(Span(315, 321),)), A.PERFORMER)
        self.scope(decide('45385', doc.build(), kept=(Span(300, 321),)))

    def test_c7_a_broad_current_denial_excludes_only_the_code_citing_it(self):
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.OTHER)
        self.denial(doc, kind=Kind.REMOVAL)
        self.scope(decide('45385', doc.build(), kept=(unit(2),)))
        self.excluded(decide('45385', doc.build(), kept=(Span(300, 325),)), A.STATUS)

    def test_c7_a_broad_denial_beside_an_omitted_act_asks_its_scope(self):
        """C-7 (c): Gemini drops the snare and records only the broad denial; the proposer cites the snare's own
        sentence: statement_scope, never excluded by a statement it does not cite."""
        doc = colonoscopy(snare=False)
        self.denial(doc, kind=Kind.REMOVAL)
        self.scope(decide('45385', doc.build(), kept=(Span(200, 260),)))

    def shared_sentence(self):
        return shared_sentence()

    def test_c10_the_shared_sentence_cited_whole_asks_its_scope_never_excluded(self):
        R = self.shared_sentence()
        self.scope(decide('45386', R, kept=(Span(300, 420),)))
        # the same with the letter-or-digit runs given (v1's within_words): the runs past 372 are no word of the denial
        runs = (Span(300, 303), Span(304, 315), Span(316, 325), Span(374, 377), Span(378, 385), Span(386, 391))
        self.scope(decide('45386', R, kept=(Span(300, 420),), kept_words=runs))

    def test_c10_a_citation_within_the_statements_words_excludes(self):
        R = self.shared_sentence()
        self.excluded(decide('45386', R, kept=(Span(327, 372),)), A.STATUS)  # its status, kind and timing words
        self.excluded(decide('45386', R, kept=(Span(300, 372),),
                             kept_words=(Span(300, 325), Span(327, 348), Span(348, 372))), A.STATUS)

    def test_c10_without_the_runs_a_gap_between_two_covering_words_is_partial(self):
        """The fail-closed reading the engine applies without kept_words: offset 326 (a space or a comma between the
        target and the status words) lies in no covering span, so the cover is partial - a question, never an
        exclusion. With the runs (v1's within_words skipped it), the same citation excludes."""
        R = self.shared_sentence()
        self.scope(decide('45386', R, kept=(Span(300, 348),)))
        self.excluded(decide('45386', R, kept=(Span(300, 348),), kept_words=(Span(300, 325), Span(327, 348))),
                      A.STATUS)

    def test_c10_a_whole_unit_source_adds_no_cover(self):
        """D188: a source citing its whole units (no located words) is no statement-linked word: fail-closed."""
        doc = colonoscopy(snare=False)
        sentence = Span(300, 420)
        doc.event(3, anchor=(sentence,), kind=sup(Kind.DILATION), status=neg(Status.PERFORMED), session=sup(X(1)),
                  date=sup(EARLIER, cited=statement_source(sentence, None)), kind_words=Span(341, 347),
                  status_words=Span(327, 347))
        self.scope(decide('45386', doc.build(), kept=(Span(327, 372),)))

    def test_p4_the_omission_case_is_held_never_excluded(self):
        """P4: Gemini drops a current act; the proposer cites the act's own passage (unit 2); only a historical denial
        exists (unit 3). Not cited: not documented. Cited beside the denial: partial, statement_scope. The denial alone:
        excluded."""
        doc = colonoscopy(snare=False)
        self.denial(doc, date=sup(EARLIER), breadth=None)
        R = doc.build()
        self.assertEqual(keys(decide('45386', R, kept=(unit(2),))),
                         [('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED))])
        self.scope(decide('45386', R, kept=(unit(2), Span(300, 325))))
        self.excluded(decide('45386', R, kept=(Span(300, 325),)), A.STATUS)

    def test_c7_an_exceptive_statement_never_excludes(self):
        doc = colonoscopy(snare=False)
        self.denial(doc, kind=Kind.INTERVENTION, breadth=sup(Breadth.EXCEPTIVE))
        evaluation = decide('45386', doc.build(), kept=(Span(300, 325),))
        self.assertIsNone(evaluation.exclusion)

    def test_an_unestablished_deciding_fact_or_breadth_never_excludes(self):
        for over in (dict(status=unres(Status.PERFORMED)), dict(breadth=unres(Breadth.ALL_OF_KIND)),
                     dict(breadth=None), dict(status=sup(Status.ATTEMPTED_NOT_COMPLETED))):
            with self.subTest(over=over):
                doc = colonoscopy(snare=False)
                self.denial(doc, **over)
                self.assertIsNone(decide('45386', doc.build(), kept=(Span(300, 325),)).exclusion)

    def test_condition_5_a_doubt_of_the_kind_prevents_the_exclusion(self):
        """An act of the colonoscopy whose kind is not established (claimed a biopsy: no candidate of 45386) is possibly
        a dilation by its session's family (4.2's widened arm), done today: the cited denial never excludes - asked
        instead (statement_scope). A doubted dilation established as of an earlier date doubts nothing today (v2's
        condition 5: "possibly today's act"; v1 counted any uncertain candidate): excluded."""
        doc = colonoscopy(snare=False)
        self.denial(doc)
        doc.act(4, unres(Kind.BIOPSY))
        R = doc.build()
        self.assertEqual(EV.candidates(R, (Kind.DILATION,)), ())
        self.scope(decide('45386', R, kept=(Span(300, 325),)))
        doc = colonoscopy(snare=False)
        self.denial(doc)
        doc.event(4, kind=sup(Kind.DILATION), status=doubted(Status.PERFORMED), session=sup(X(1)), date=sup(EARLIER))
        self.excluded(decide('45386', doc.build(), kept=(Span(300, 325),)), A.STATUS)
        doc = colonoscopy(snare=False)  # an unlisted doubt of the kind
        self.denial(doc)
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.DILATION, None, Span(900, 950)))
        self.assertIsNone(decide('45386', doc.build(), kept=(Span(300, 325),)).exclusion)

    def test_condition_5_an_unlisted_act_of_the_kind_prevents_the_exclusion(self):
        """The refutation's D2, built fail-closed: 3.2.6 rule 3 makes an unlisted act a synthetic doubted act, so an
        unlisted act of the code's kinds (or of no kind) doubts them as an unlisted denial or doubt does - "No polyps
        were removed." cited by 45385 beside pass 2's unlisted snare act is asked (statement_scope), never excluded. An
        unlisted act of another kind doubts nothing: excluded."""
        for what in (ct.UnlistedWhat.ACT, ct.UnlistedWhat.DOUBT):
            for kind in (Kind.SNARE, None):
                with self.subTest(what=what, kind=kind):
                    doc = colonoscopy(snare=False)
                    self.denial(doc, kind=Kind.REMOVAL)
                    doc.unlisted.append(unlisted(what, kind, X(1), unit(5)))
                    self.scope(decide('45385', doc.build(), kept=(Span(300, 325),)))
        doc = colonoscopy(snare=False)
        self.denial(doc, kind=Kind.REMOVAL)
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.BIOPSY, X(1), unit(5)))
        self.excluded(decide('45385', doc.build(), kept=(Span(300, 325),)), A.STATUS)

    def test_76_no_candidate_at_all_is_not_documented(self):
        evaluation = decide('45386', colonoscopy().build(), kept=(unit(2),))
        self.assertEqual(keys(evaluation), [('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED))])
        self.assertEqual(evaluation.held_facts[0].spans, (unit(2),))

    def test_a_denial_of_the_codes_kind_whose_session_is_not_established_asks_its_scope(self):
        doc = colonoscopy(snare=False)
        self.denial(doc, session=unres(X(1)))
        self.scope(decide('45386', doc.build(), kept=(unit(1),)))
        doc = colonoscopy(snare=False)  # its date relation not established, in a session possibly of the family
        self.denial(doc, date=unres(ON))
        self.scope(decide('45386', doc.build(), kept=(unit(1),)))
        doc = colonoscopy(snare=False)  # the same denial in a session established as another family's: nothing asked
        doc.session(2, SessionKind.EGD)
        self.denial(doc, session=sup(X(2)), date=unres(ON))
        self.assertEqual(keys(decide('45386', doc.build(), kept=(unit(1),))),
                         [('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED))])

    def test_route_b_is_excluded_by_a_denial_at_its_places(self):
        doc = colonoscopy(snare=False)
        self.denial(doc, kind=Kind.BAND_LIGATION, places=[sup(Landmark.ANAL_CANAL)])
        self.excluded(decide('46221', doc.build(), kept=(Span(300, 325),)), A.STATUS)


class SessionQuestion(SimpleTestCase):
    """D31 (Gemini's open question on a session's examination held every code of the session) retires (D180: each
    doubt holds only the facts it names). Its v2 form: a doubt on the examination's own performer, time or status is
    row 7's witness, so the session's codes are held on that fact; a doubt on another attribute of the examination, or
    on an act only, holds nothing of the session."""

    def test_a_doubt_on_the_examinations_performer_time_or_status_holds_the_sessions_act_code(self):
        expected = {'performer': ('event_performer', 7), 'date': ('event_time', 6), 'status': ('performed_status', 2)}
        values = {'performer': TEAM, 'date': ON, 'status': Status.PERFORMED}
        for name, (fact, rank) in expected.items():
            with self.subTest(name):
                doc = colonoscopy()
                doc.exam(1, **{name: doubted(values[name])})
                found = item('45385', doc.build())
                self.assertEqual((found.held.fact, found.held.rank, found.held.subject), (fact, rank, E(1)))

    def test_a_doubt_on_another_attribute_of_the_examination_holds_nothing(self):
        doc = colonoscopy()
        doc.exam(1, places=[doubted(Landmark.CECUM)])
        self.assertTrue(ready(decide('45385', doc.build())))

    def test_a_doubt_on_an_earlier_examination_holds_nothing(self):
        doc = colonoscopy()
        doc.session(2, SessionKind.COLONOSCOPY)
        doc.exam(3, session=X(2), date=sup(EARLIER), performer=doubted(TEAM))
        self.assertTrue(ready(decide('45385', doc.build())))


# --- the done-when items: binding, doubts, Q2, never READY ---------------------------------------------------------------


class DoubtedActs(SimpleTestCase):
    """HO-1 (critical): a doubted act is a POSITIVE candidate (4.2: a status not established leaves every status
    possible). Document A: "It is unclear whether the polyp was removed with the cold snare." - 45385 is held at rank 2
    on the doubted snare (45378's base_included over it is the combination's, step 4d; the predicate it reads is
    ``positive``). Document B: "A flexible sigmoidoscopy may have been performed in the office today" - 45330 is held at
    rank 2 on the doubted examination, and the doubted act is positive for the same-day rule (step 4d's procedure day,
    which reads ``positive``) that holds 99214."""

    def test_document_a(self):
        R = colonoscopy(status=doubted(Status.PERFORMED, Status.PERFORMED)).build()
        self.assertTrue(EV.positive(R, E(2)))
        evaluation = decide('45385', R)
        self.assertEqual(evaluation.bindings, {(Kind.SNARE,): E(2)})
        self.assertIsNone(evaluation.exclusion)
        found = item('45385', R)
        self.assertEqual((found.held.fact, found.held.rank, found.held.subject, found.message),
                         ('performed_status', 2, E(2), Q.MessageId.DOUBT))
        self.assertTrue(ready(decide('45378', R)))  # the per-code rule alone; base_included is step 4d's

    def test_document_b(self):
        doc = Doc()
        doc.session(1, SessionKind.FLEX_SIG)
        doc.exam(1, status=doubted(Status.PERFORMED))
        doc.session(2, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        doc.act(2, Kind.EM_VISIT, session=X(2), basis=sup(ct.EmBasis.TOTAL_TIME))
        R = doc.build()
        self.assertTrue(EV.positive(R, E(1)))
        found = item('45330', R)
        self.assertEqual((found.held.fact, found.held.rank, found.held.subject), ('performed_status', 2, E(1)))
        self.assertTrue(ready(decide('99214', R)))  # the per-code rule alone; the same-day hold is step 4d's

    def test_a_status_pass_2_did_not_establish_is_positive_too(self):
        R = colonoscopy(status=unres(Status.PERFORMED)).build()
        self.assertTrue(EV.positive(R, E(2)))
        self.assertEqual(decide('45385', R).bindings, {(Kind.SNARE,): E(2)})


class NoEarlyReturn(SimpleTestCase):
    """Q2: every hold carries ALL its unresolved facts - every non-T row of every positive candidate, and the
    code-specific rows of every supporting act - never only the first rule that applies (v1's _focused and its early
    returns)."""

    def test_every_row_of_a_positive_candidate_records_its_witness(self):
        R = colonoscopy(status=doubted(Status.PERFORMED), date=unres(ON), performer=None, entry=unres(DC)).build()
        self.assertEqual([entry[:2] for entry in keys(decide('45385', R))],
                         [('performed_status', 2), ('event_time', 6), ('event_performer', 7), ('event_entry', 5)])

    def test_the_code_specific_rows_of_every_supporting_act_are_read(self):
        R = dilation(sup(Landmark.PYLORUS), device=sup(Device.WIRE_BOUGIE)).build()
        self.assertEqual(keys(decide('43249', R)), [('technique', 10, EXPLANATION, rule(Q.Rule.TECHNIQUE)),
                                                    ('act_target', 11, EXPLANATION, rule(Q.Rule.SITE))])

    def test_a_contradiction_on_a_candidate_the_item_does_not_name_stays_held(self):
        doc = colonoscopy(performer=unres(TEAM))
        doc.act(3, Kind.SNARE, date=contra(ON, EARLIER), places=[sup(Landmark.RECTUM)])
        R = doc.build()
        evaluation = decide('45385', R, kept=(unit(2),))
        self.assertIn(('conflict:snare', 1, QUESTION, 'reading_contradicted'), keys(evaluation))
        self.assertEqual(evaluation.bindings, {(Kind.SNARE,): E(2)})


class Binding(SimpleTestCase):
    """4.8's binding (Q1, HO-8): kept-span overlap, then rank across the candidates, then the fewest non-T rows, a
    question before an explanation, document order - never simply the first act in reading order; every candidate's
    witnesses kept."""

    def two_snares(self):
        return two_snares()

    def test_ho8_case_1_a_contradicted_date_on_the_act_the_item_does_not_name_stays_held(self):
        R = self.two_snares()
        selected = decide('45385', R, kept=(unit(2),))
        self.assertEqual(selected.bindings, {(Kind.SNARE,): E(2)})  # (1) the kept span selects E2
        self.assertEqual(item('45385', R, kept=(unit(2),)).held.fact, 'event_performer')
        self.assertIn('conflict:snare', [held.fact for held in selected.held_facts])  # E3's witness kept
        free = decide('45385', R)
        self.assertEqual(free.bindings, {(Kind.SNARE,): E(3)})  # (2) no kept span: rank across the candidates
        self.assertEqual(item('45385', R).held.fact, 'conflict:snare')

    def test_ho8_case_2_the_esophageal_dilation_with_an_unstated_device_is_asked_before_the_duodenal_explained(self):
        doc = dilation(sup(Landmark.DISTAL_ESOPHAGUS), device=None)
        dilation(sup(Landmark.DUODENUM), number=3, doc=doc)
        R = doc.build()
        evaluation = decide('43249', R)
        self.assertEqual(evaluation.supporting, (E(2), E(3)))
        self.assertEqual(keys(evaluation), [('technique', 10, QUESTION, 'reading_unknown'),
                                            ('act_target', 11, EXPLANATION, rule(Q.Rule.SITE))])
        found = item('43249', R)
        self.assertEqual((found.held.fact, found.kind, found.held.subject), ('technique', QUESTION, E(2)))

    def test_rule_3_the_fewest_non_t_rows_before_rule_4_a_question(self):
        """4.8 (D182): at an equal top rank the fewest non-T rows (3) decide before a question beats an explanation (4)
        - the refutation's T1: no test told the two apart. E2's entry is another role's (an explanation at rank 5, one
        row not T); E3's entry is not established (a question at rank 5) and its date neither (two rows): E2 bound."""
        doc = colonoscopy(entry=sup(Owner.NURSING))
        doc.act(3, Kind.SNARE, entry=unres(DC), date=unres(ON), places=[sup(Landmark.RECTUM)])
        R = doc.build()
        self.assertEqual(decide('45385', R).bindings, {(Kind.SNARE,): E(2)})
        found = item('45385', R)
        self.assertEqual((found.held.fact, found.kind, found.held.subject), ('event_entry', EXPLANATION, E(2)))

    def test_q1_never_simply_the_first_act_in_reading_order(self):
        doc = colonoscopy(date=unres(ON))  # E2 first in reading order: rank 6
        doc.act(3, Kind.SNARE, status=doubted(Status.PERFORMED), places=[sup(Landmark.RECTUM)])  # E3: rank 2
        R = doc.build()
        self.assertEqual(decide('45385', R).bindings, {(Kind.SNARE,): E(3)})
        self.assertEqual(decide('45385', R, kept=(unit(2),)).bindings, {(Kind.SNARE,): E(2)})


class UnlistedOnEvidence(SimpleTestCase):
    """3.2.6 rule 2 (the refutation's D1, built fail-closed; its owner a question for the integration owner): a code
    whose kept evidence overlaps the unit of a kept unlisted entry - an act, a denial or a doubt, of any kind - is held:
    performed_status at RANK 2 ("an unlisted unit on its evidence", h2), a question, cause unlisted, quoting the unit,
    about no single fact (D189: result None); and none of its groups is excluded (a citation beside it is asked)."""

    @staticmethod
    def exchange(what=ct.UnlistedWhat.ACT, kind=Kind.STENT_REMOVAL) -> FactSet:
        """3.2.6's own case: "The existing biliary stent was removed and replaced with a new plastic stent." with only
        the placement filed (E2) and pass 2's unlisted removal act kept in its unit."""
        doc = Doc()
        doc.session(1, SessionKind.ERCP)
        doc.exam(1)
        doc.act(2, Kind.STENT, duct=sup(ct.Duct.BILIARY))
        doc.unlisted.append(unlisted(what, kind, X(1), unit(2)))
        return doc.build()

    def test_the_exchange_sentence_cited_holds_43274(self):
        R = self.exchange()
        evaluation = decide('43274', R, kept=(unit(2),))
        self.assertEqual(evaluation.supporting, (E(2),))
        self.assertEqual(keys(evaluation), [('performed_status', 2, QUESTION, 'unlisted')])
        self.assertEqual((evaluation.held_facts[0].spans, evaluation.held_facts[0].result), ((unit(2),), None))
        found = item('43274', R, kept=(unit(2),))
        self.assertEqual((found.held.rank, found.message, found.fill.statements), (2, Q.MessageId.DOUBT, ((unit(2),),)))
        self.assertTrue(ready(decide('43274', R, kept=(unit(1),))))  # evidence elsewhere: rule 2 reads none

    def test_every_entry_on_the_evidence_holds_whatever_its_nature_or_kind(self):
        for what in ct.UnlistedWhat:
            for kind in (Kind.STENT_REMOVAL, Kind.BIOPSY, None):
                with self.subTest(what=what, kind=kind):
                    keys_ = keys(decide('43274', self.exchange(what, kind), kept=(Span(220, 230),)))
                    self.assertIn(('performed_status', 2, QUESTION, 'unlisted'), keys_)

    def test_an_unlisted_unit_on_a_cited_denial_is_asked_never_excluded(self):
        """"No polyps were removed." cited by 45385 excludes; an unlisted doubt of another kind (no doubt of the code's
        kinds: condition 5 holds) found in that very sentence holds it instead - the denial's scope asked, and rule 2's
        doubt, worded with the unit as its words (no act)."""
        doc = colonoscopy(snare=False)
        denial_event(doc, kind=Kind.REMOVAL)
        self.assertIsNotNone(decide('45385', doc.build(), kept=(Span(300, 325),)).exclusion)
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.BIOPSY, X(1), unit(3)))
        R = doc.build()
        evaluation = decide('45385', R, kept=(Span(300, 325),))
        self.assertIsNone(evaluation.exclusion)
        self.assertEqual(sorted(entry[:4] for entry in keys(evaluation)),
                         [('performed_status', 2, QUESTION, 'unlisted'),
                          ('statement_scope', 3, QUESTION, rule(Q.Rule.STATEMENT_SCOPE))])
        found = item('45385', R, kept=(Span(300, 325),))
        self.assertEqual((found.held.rank, found.message, found.fill.words), (2, Q.MessageId.DOUBT, (unit(3),)))

    def test_route_d_and_d80_keep_their_one_explanation(self):
        """Route (d) and D80 return before any group (4.4): never READY already, their item their own explanation."""
        doc = colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, None, X(1), unit(2)))
        for code in ('45305', '99152'):
            with self.subTest(code=code):
                self.assertEqual([entry[:3] for entry in keys(decide(code, doc.build(), kept=(unit(2),)))],
                                 [('performed_status', 4, EXPLANATION)])


class NeverReady(SimpleTestCase):
    """Route (d), D80 and route (b) (D197): held, never READY, each with exactly one item at the status row."""

    def test_route_d_and_d80(self):
        R = colonoscopy().build()
        for code, cause in (('45305', rule(Q.Rule.UNPROFILED)), ('99152', rule(Q.Rule.RECOGNISED_ONLY)),
                            ('99153', rule(Q.Rule.RECOGNISED_ONLY)), ('G0105', rule(Q.Rule.UNPROFILED)),
                            ('00000', rule(Q.Rule.UNPROFILED))):
            with self.subTest(code=code):
                evaluation = decide(code, R)
                self.assertEqual(keys(evaluation), [('performed_status', 4, EXPLANATION, cause)])
                self.assertEqual(evaluation.bindings, {})

    def test_route_b_is_never_ready_with_one_item(self):
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.BAND_LIGATION, places=[sup(Landmark.ANAL_CANAL)])
        evaluation = decide('46221', doc.build())
        self.assertEqual(evaluation.supporting, (E(2),))
        self.assertEqual(keys(evaluation), [('performed_status', 4, EXPLANATION, rule(Q.Rule.ROUTE_B))])
        self.assertEqual(item('46221', doc.build()).message, Q.MessageId.UNRECONCILED)


class Determinism(SimpleTestCase):
    def test_identical_inputs_give_an_identical_evaluation(self):
        doc = colonoscopy(date=unres(ON))
        doc.act(3, Kind.SNARE, status=doubted(Status.PERFORMED))
        for code in ('45385', '45378', '45386', '46221', '43249'):
            with self.subTest(code=code):
                self.assertEqual(decide(code, doc.build(), kept=(unit(2),)), decide(code, doc.build(),
                                                                                     kept=(unit(2),)))


class Boundary(SimpleTestCase):
    """5.7 measures 4 and 5 over engine/evaluate.py: no retired module, text module, re, wording or word list; no text
    read; mypy --strict passes on both modules (the done-when)."""

    def test_measure_4(self):
        self.assertEqual(measure_4(MODULE.read_text(encoding='utf-8'), engine=True), [])

    def test_imports(self):
        names = [node.module for node in ast.walk(ast.parse(MODULE.read_text(encoding='utf-8')))
                 if isinstance(node, ast.ImportFrom)]
        self.assertTrue(all(name.startswith(('studio.interpretation.contract.types', 'studio.interpretation.engine'))
                            or not name.startswith('studio') for name in names), names)
        code = ('import sys\nimport studio.interpretation.engine.evaluate\n'
                'print(",".join(sorted(m for m in sys.modules if m.startswith("studio"))))\n')
        result = subprocess.run([sys.executable, '-I', '-B', '-c', f'import sys; sys.path.insert(0, {str(APP)!r})\n'
                                 + code], capture_output=True, text=True, timeout=120, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stderr)
        loaded = result.stdout.strip().split(',')
        self.assertFalse([name for name in loaded if name.startswith('studio.gi') or name.endswith('.wording')
                          or name.split('.')[-1] in ('events', 'ercp', 'mapping', 'lexicon', 'verify')], loaded)

    def test_mypy_strict_on_both_modules(self):
        result = subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--cache-dir', os.devnull,
                                 'studio/interpretation/engine/evaluate.py', 'studio/interpretation/engine/questions.py'],
                                capture_output=True, text=True, timeout=900, cwd=APP)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Success: no issues found in 2 source files', result.stdout)


class Properties(SimpleTestCase):
    """P-MONO and P-READSET at the per-code rule's level (9.4; step 6a owns the engine-wide properties), over every
    fixture of all_fixtures(): weakening one established fact to unresolved, or adding a doubt to one fact, never makes a
    code READY or EXCLUDED that was not (the deleted-member weakening releases 4.3's "every supported X within ..., at
    least one" rows by construction: the step's NOTES, question Q12); and decide reads no attribute outside
    requirements.reads_of(code) - the pairing's and the predicates' reads included."""

    @staticmethod
    def status(evaluation):
        if evaluation.exclusion is not None:
            return 'excluded'
        return 'ready' if ready(evaluation) else 'held'

    @staticmethod
    def weakened(R):
        for family in ('events', 'sessions', 'lesions', 'anatomy'):
            objects = getattr(R, family)
            for subject, found in objects.items():
                for attribute, members in found.items():
                    for index, member in enumerate(members):
                        for result, reasons in ((Res.UNRESOLVED, (ct.Reason.APPRAISAL_UNCLEAR,)),
                                                (Res.UNKNOWN, (ct.Reason.DOUBT_UNCLEAR,))):
                            if result is Res.UNRESOLVED and member.result not in (Res.SUPPORTED, Res.NEGATED):
                                continue
                            if result is Res.UNKNOWN and member.result is Res.CONTRADICTED:
                                continue
                            weaker = dataclasses.replace(member, result=result, reasons=reasons)
                            changed = {key: dict(value) for key, value in objects.items()}
                            changed[subject][attribute] = members[:index] + (weaker,) + members[index + 1:]
                            yield (subject, attribute, index, result), dataclasses.replace(R, **{family: changed})

    def test_p_mono_a_weakened_fact_never_makes_a_code_ready_or_excluded(self):
        count = 0
        for code, R, kept in all_fixtures():
            before = self.status(decide(code, R, kept))
            for name, W in self.weakened(R):
                after = self.status(decide(code, W, kept))
                count += 1
                if after != before:
                    with self.subTest(code=code, weakened=str(name)):
                        self.assertNotIn(after, ('ready', 'excluded'))
        self.assertGreater(count, 1000)

    def test_p_readset_decide_reads_only_what_the_codes_requirements_read(self):
        real_fact, real_members = facts_module.fact, facts_module.members
        for code, R, kept in all_fixtures():
            read = set()

            def fact(R_, subject, attribute):
                read.add(attribute)
                return real_fact(R_, subject, attribute)

            def members(R_, subject, attribute):
                read.add(attribute)
                return real_members(R_, subject, attribute)

            with mock.patch.object(facts_module, 'fact', fact), mock.patch.object(facts_module, 'members', members):
                decide(code, R, kept)
            allowed = {entry.attribute for entry in rq.reads_of(code) if entry.attribute is not None}
            with self.subTest(code=code):
                self.assertEqual(read - allowed, set())


def all_fixtures() -> list:
    """(code, FactSet, kept) for every fixture shape of this module that holds its code: tests/v2/test_questions.py's
    OneItem runs questions.item over each (D182: exactly one item) and builds each item's sentence."""
    out = []
    shapes = [
        ('45385', colonoscopy(status=doubted(Status.PERFORMED)).build(), ()),
        ('45385', colonoscopy(status=sup(Status.ATTEMPTED_NOT_COMPLETED)).build(), ()),
        ('45385', colonoscopy(kind=sup(Kind.REMOVAL)).build(), ()),
        ('45385', colonoscopy(kind=contra(Kind.SNARE, Kind.BIOPSY)).build(), ()),
        ('45385', colonoscopy(entry=sup(Owner.NURSING)).build(), ()),
        ('45385', colonoscopy(entry=unres(DC)).build(), ()),
        ('45385', colonoscopy(date=unres(ON)).build(), ()),
        ('45385', colonoscopy(performer=None).build(), ()),
        ('45385', colonoscopy(session=unres(X(1))).build(), ()),
        ('45386', colonoscopy().build(), (unit(2),)),
        ('45305', colonoscopy().build(), (unit(1),)),
        ('99152', colonoscopy().build(), (unit(1),)),
        ('43249', dilation(sup(Landmark.DISTAL_ESOPHAGUS), device=None).build(), ()),
        ('43249', dilation(sup(Landmark.DISTAL_ESOPHAGUS), device=sup(Device.WIRE_BOUGIE)).build(), ()),
        ('43245', dilation(sup(Landmark.DISTAL_ESOPHAGUS)).build(), ()),
        ('43249', dilation(sup(Landmark.ANASTOMOSIS)).build(), ()),
    ]
    out.extend(shapes)
    doc = colonoscopy()
    doc.event(3, kind=sup(Kind.REMOVAL), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
              breadth=sup(Breadth.ALL_OF_KIND))
    out.append(('45385', doc.build(), ()))
    doc = colonoscopy()
    doc.event(3, kind=sup(Kind.REMOVAL), status=doubted(Status.PERFORMED), session=sup(X(1)), date=sup(ON))
    out.append(('45385', doc.build(), ()))
    doc = colonoscopy()
    doc.event(3, kind=sup(Kind.REMOVAL), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON))
    out.append(('45385', doc.build(), ()))
    doc = colonoscopy()
    doc.unlisted.append(unlisted(ct.UnlistedWhat.DENIAL, Kind.SNARE, None, Span(900, 950)))
    out.append(('45385', doc.build(), ()))
    doc = colonoscopy(snare=False)
    doc.act(2, Kind.BAND_LIGATION, places=[sup(Landmark.ANAL_CANAL)])
    out.append(('46221', doc.build(), ()))
    out.append(('45386', shared_sentence(), (Span(300, 420),)))
    out.append(('45385', two_snares(), ()))
    out.append(('45385', two_snares(), (unit(2),)))
    doc = dilation(sup(Landmark.DISTAL_ESOPHAGUS), device=None)
    dilation(sup(Landmark.DUODENUM), number=3, doc=doc)
    out.append(('43249', doc.build(), ()))
    every = [sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)]
    out += [('43242', eus_fna(()), ()), ('43242', eus_fna([sup(Station.ESOPHAGUS), neg(Station.STOMACH)]), ()),
            ('43237', eus_fna(every), ()), ('43259', eus_fna(every, tract=sup(ct.Tract.LOWER)), ()),
            ('43231', eus_fna(()), ())]
    biliary = sup(ct.Duct.BILIARY)
    out += [('43274', ercp_doc((2, Kind.STENT, dict(duct=biliary)), (3, Kind.STENT_REMOVAL, dict(duct=biliary))), ()),
            ('43274', ercp_doc((2, Kind.STENT, dict(duct=biliary)), (3, Kind.STENT_REMOVAL, {})), ()),
            ('43276', ercp_doc((2, Kind.STENT, dict(duct=biliary)), (3, Kind.STENT_REMOVAL, {})), ()),
            ('43264', ercp_doc((2, Kind.STONE_EXTRACTION, dict(yield_=neg(ct.Material.ANYTHING)))), ()),
            ('43264', ercp_doc((2, Kind.STONE_EXTRACTION, {})), ())]
    doc = egd()
    doc.act(2, Kind.BLEEDING_CONTROL, purpose=sup(ct.Purpose.HEMOSTASIS), cause=sup(ct.Cause.ACT_OF_THIS_SESSION))
    out.append(('43255', doc.build(), ()))
    doc = egd()
    doc.act(2, Kind.BLEEDING_CONTROL, purpose=sup(ct.Purpose.HEMOSTASIS))
    out.append(('43255', doc.build(), ()))
    doc = Doc()
    doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.UPPER))
    doc.exam(1)
    doc.act(2, Kind.INJECTION, route=sup(ct.Route.SUBMUCOSAL))
    out.append(('43253', doc.build(), ()))
    doc = Doc()
    doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.UPPER))
    doc.exam(1)
    doc.act(2, Kind.DRAINAGE, structure=sup(ct.Structure.GALLBLADDER), places=[sup(Landmark.GALLBLADDER)])
    out.append(('43240', doc.build(), ()))
    doc = Doc()
    doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=[sup(Extent.CECUM)])
    doc.exam(1)
    out.append(('45341', doc.build(), ()))
    doc = Doc()
    doc.session(1, SessionKind.OFFICE_EM, encounter=unres(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, Kind.EM_VISIT)
    out.append(('99213', doc.build(), ()))
    doc = colonoscopy()
    doc.exam(1, entry=sup(Owner.ANESTHESIA))
    out.append(('45385', doc.build(), ()))
    doc = colonoscopy()
    doc.exam(1, performer=doubted(TEAM))
    out.append(('45385', doc.build(), ()))
    doc = colonoscopy(snare=False)
    denial_event(doc, session=unres(X(1)))
    out.append(('45386', doc.build(), (unit(1),)))
    out += repair_fixtures()
    return out


def repair_fixtures() -> list:
    """(code, FactSet, kept) for the shapes of the refutation's round-1 findings that hold their code: OneItem builds each
    item's sentence (F2, F3, F4, F5, D1) and P-MONO weakens each (F1's fail-closed side, D1, D2, T1, T2)."""
    out = []
    doc = colonoscopy()  # F2: an unlisted doubt found in the snare's own sentence
    doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.SNARE, X(1), unit(2)))
    out.append(('45385', doc.build(), ()))
    doc = dilation(lesion=sup(L(1)))  # F3: the act's place told only on its lesion
    doc.lesion(1, lesion_places=[sup(Landmark.DISTAL_ESOPHAGUS)])
    out.append(('43245', doc.build(), ()))
    doc = Doc()  # F4: a stoma-class code, its approach established oral
    doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=[sup(Extent.STOMA)],
                approach=sup(ct.Approach.ORAL))
    doc.entry(1, type=sup(ct.AnatomyType.STOMA))
    doc.exam(1)
    out.append(('44406', doc.build(), ()))
    every = [sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)]
    out.append(('43237', eus_fna([neg(Station.JEJUNUM), *every]), ()))  # F5
    out.append(('43242', eus_fna([neg(Station.JEJUNUM), sup(Station.ESOPHAGUS), neg(Station.STOMACH),
                                  sup(Station.DUODENUM)]), ()))
    doc = Doc()  # F1's fail-closed side: an act-only session beside a plan that may be its examination
    doc.session(1, SessionKind.COLONOSCOPY, reached=[sup(Extent.CECUM)])
    doc.act(2, Kind.SNARE, places=[sup(Landmark.SIGMOID_COLON)], device=sup(Device.COLD_SNARE))
    doc.event(4, kind=sup(Kind.EXAMINATION), status=sup(Status.PLANNED), date=sup(ct.DateRelation.LATER_DATE))
    out.append(('45385', doc.build(), ()))
    doc = colonoscopy()  # F1: a doubted examination beside the session's done one
    doc.event(4, kind=sup(Kind.EXAMINATION), status=doubted(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
              performer=sup(TEAM), entry=sup(DC))
    out.append(('45385', doc.build(), ()))
    out.append(('43274', UnlistedOnEvidence.exchange(), (unit(2),)))  # D1
    doc = colonoscopy(snare=False)  # D1 beside a cited denial: no act, its words the unit
    denial_event(doc, kind=Kind.REMOVAL)
    doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.BIOPSY, X(1), unit(3)))
    out.append(('45385', doc.build(), (Span(300, 325),)))
    doc = colonoscopy(snare=False)  # D2: a cited broad denial beside an unlisted act of the kind
    denial_event(doc, kind=Kind.REMOVAL)
    doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.SNARE, X(1), unit(5)))
    out.append(('45385', doc.build(), (Span(300, 325),)))
    doc = colonoscopy(entry=sup(Owner.NURSING))  # T1
    doc.act(3, Kind.SNARE, entry=unres(DC), date=unres(ON), places=[sup(Landmark.RECTUM)])
    out.append(('45385', doc.build(), ()))
    doc = colonoscopy(snare=False)  # T2
    doc.act(2, Kind.BAND_LIGATION, places=[sup(Landmark.ANAL_CANAL), sup(Landmark.SIGMOID_COLON)])
    out.append(('46221', doc.build(), ()))
    return out
