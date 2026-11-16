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

The refutation of repair r4a (build-v2/w56r/refute-r4a-r1), round 2: F1 (an unlisted doubt read as a possibly performed
act by every absence condition: UnlistedDoubts, Properties.test_p_mono_an_unlisted_act_told_as_a_doubt_never_releases),
F4 (every witness under its own fact's attribute: OwnAttribute), F7 (LOWER's approach beside its reach: LowerApproach,
CodeRows.test_lower), the same-duct question about the counterpart whose status is unknown (SameDuctCounterpart, beside
F6), F5's unit-less entry still held with one item (UnitlessEntries); r4a2_fixtures() feeds every shape to OneItem and
P-MONO; the sentences are tests/v2/test_questions.py RefutedSentences.

Repair r4a of round w7r (DECISIONS D232, D240; refute-r4a-r2 N1, 6c B): row 7 reads a synthetic examination only in an
act-only session - p41's unlisted doubt of kind examination, carded to the colonoscopy or to none, leaves 45385 READY
beside the colonoscopy's done examination and holds nothing beside an EGD's, while the base code keeps 3.2.6 rule 4's
pair (D232Row7); evaluate's code rows read only the supporting acts within the code's SITE class - "The distal
esophageal stricture was dilated with a balloon. The duodenal bulb stricture was dilated with a balloon." gives 43249 on
the esophageal act and 43245 on the duodenal one (D240SiteFit). w7r_fixtures() feeds every shape to OneItem and P-MONO;
the sentences (D232's naming, D246's items) are tests/v2/test_questions.py D232Sentences and D246Items. Its refutation
refute-r4a-r1 (repair r4a-2): P1, a digital examination (FINAL 5.6 E13) never makes a session non-act-only, its device
weakened neither (P-MONO), and P5, act_only read per session (R4a2Repairs; their shapes join w7r_fixtures()); the
sentences are tests/v2/test_questions.py R4a2Sentences.

Repair r4a of round w8r (DECISIONS D253, D258): row 7's ``done`` excepts the digital examination as ``act_only`` does -
refute-r4a-r2 A2's shapes (a2, a2b, a2c, a2d: a DRE filed as the colonoscopy's examination beside the history or a
plan filed in it) hold 45385 with the DRE line exactly as without it, through assess too, and a device claiming manual
stays digital under weakening (D253Row7, QE13 option (a)); R4a2Repairs' no-card doubt is restated for D258
(UNLISTED_SCOPE, the DRE's sentence never quoted as the colonoscopy's). w8r_fixtures() feeds A2's, D258's and r4c Q1's
shapes to OneItem and P-MONO; the sentences are tests/v2/test_questions.py D258UnlistedScope, D253Items, D254Fill and
D257BaseWithin. Its refutation refute-r4a-r1 (repair r4a-2 of round w8r): P1 (critical), a digital examination (FINAL
5.6 E13) never supports an examination group - the DRE alone no longer makes 45378 or 45330 READY, the code is held
with the item the same document gets without the DRE line, a device claiming manual never supports either, and the
DRE stays a candidate so 4.6 reads what it read (DigitalSupport); w8r_refuted_fixtures() feeds its shapes, P3's and
P4's to OneItem and P-MONO; the sentences are tests/v2/test_questions.py D253Items and RefutedW8rItems.
"""
from __future__ import annotations

import ast
import dataclasses
import itertools
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
from studio.interpretation.engine.types import (Cover, Evaluation, Fact, FactSet, HeldFact, Id, ItemKind, Span,
                                                UnlistedStatement)
from tests.v2.evaluate_fixtures import (DC, DRE_CLAIMING, DRE_KEPT, DRE_OTHERS, DRE_REACHES, DRE_SESSIONS,
                                        DRE_STATEMENTS, EARLIER, ON, TEAM, Doc, E, L, Landmark, Owner, Performer,
                                        SessionKind, Status, X, Y, colonoscopy, contra, doubted, dre_grid, egd, neg,
                                        statement_source, sup, unit, unlisted, unres, without_events)
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
        """Restated for DECISIONS D267 (repair r4a of round w9r; r4a-2 Q1 QK option (b): "test_evaluate's pin follows"):
        the contradicted kind's conflict is keyed conflict:other - an act whose kind is not supported is "another act",
        never "the snare removal" (before: conflict:snare, the code's group's kind)."""
        cases = {
            'umbrella': (sup(Kind.REMOVAL), [('act_method', 9, QUESTION, rule(Q.Rule.UMBRELLA))]),
            'unresolved': (unres(Kind.SNARE), [('performed_status', 4, QUESTION, 'appraisal:unclear')]),
            'doubted': (doubted(Kind.SNARE, Kind.BIOPSY), [('performed_status', 4, QUESTION, 'reading_unknown')]),
            'contradicted': (contra(Kind.SNARE, Kind.BIOPSY), [('conflict:other', 1, QUESTION,
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
        # an unlisted denial: performed_status at RANK row 2, cause unlisted (3.2.6 rule 4; DECISIONS D228 DQ3)
        doc = colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DENIAL, Kind.SNARE, None, Span(900, 950)))
        self.assertEqual(keys(self.held('45385', doc.build())), [('performed_status', 2, QUESTION, 'unlisted')])

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
        # D225 (refute-4a-r2 P5): with the reach met, the stoma class's approach is asked as the approach - RANK row 8,
        # procedure ("approach for a class") - never as R6's extent question
        for name, R in {'no stoma entry': lower(sup(Extent.STOMA), approach=sup(ct.Approach.THROUGH_STOMA)),
                        'the approach not stated': lower(sup(Extent.STOMA), stoma=True),
                        'the approach not established': lower(sup(Extent.STOMA), approach=unres(ct.Approach.ORAL),
                                                              stoma=True)}.items():
            with self.subTest(name):
                self.assertEqual([entry[:3] for entry in keys(decide('44406', R))], [('procedure', 8, QUESTION)])
                self.assertEqual(item('44406', R).message, Q.MessageId.EXAMINATION_ROUTE)
        # the refutation's F4: an approach established otherwise is the misfit - named as the approach (P5) when one is
        # supported; through a stoma denied names none, and stays the class explanation (the step's NOTES, Q6)
        R = lower(sup(Extent.STOMA), approach=sup(ct.Approach.ORAL), stoma=True)
        self.assertEqual(keys(decide('44406', R)), [('procedure', 8, EXPLANATION, rule(Q.Rule.LOWER))])
        self.assertEqual(item('44406', R).message, Q.MessageId.EXAMINATION_APPROACH)
        R = lower(sup(Extent.STOMA), approach=neg(ct.Approach.THROUGH_STOMA), stoma=True)
        self.assertEqual(keys(decide('44406', R)), [('extent', 14, EXPLANATION, rule(Q.Rule.LOWER))])
        self.assertEqual(item('44406', R).message, Q.MessageId.EXAMINATION_CLASS)
        # the reach not established is still R6's extent question (the reach IS what is unknown), recorded beside the
        # approach's when that is unknown too (refute-r4a-r1 F7: HO-8, every unresolved fact held; RANK then asks the
        # approach, row 8) - and alone once the approach is established through the documented stoma
        self.assertEqual([entry[:3] for entry in keys(decide('44406', lower(unres(Extent.STOMA), stoma=True)))],
                         [('extent', 14, QUESTION), ('procedure', 8, QUESTION)])
        R = lower(unres(Extent.STOMA), stoma=True, approach=sup(ct.Approach.THROUGH_STOMA))
        self.assertEqual([entry[:3] for entry in keys(decide('44406', R))], [('extent', 14, QUESTION)])

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

    def test_ho8_case_2_the_esophageal_dilation_with_an_unstated_device_is_asked_and_the_duodenal_one_is_not_read(self):
        """HO-8's second case under D240 (D29's installed reading): the esophageal dilation with an unstated device is
        asked about its device; the duodenal one with a balloon, established outside the esophageal class beside an act
        established within it, is no supporting act of 43249 - it leaves E* and its another-site explanation is no longer
        raised (it was the second held fact before D240). The item is the same."""
        doc = dilation(sup(Landmark.DISTAL_ESOPHAGUS), device=None)
        dilation(sup(Landmark.DUODENUM), number=3, doc=doc)
        R = doc.build()
        evaluation = decide('43249', R)
        self.assertEqual(evaluation.supporting, (E(2),))
        self.assertEqual(keys(evaluation), [('technique', 10, QUESTION, 'reading_unknown')])
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
        """Rule 2's hold, and since D216 XCHG's: the unlisted removal is a synthetic counterpart of the placement in its
        session. The item is rule 2's, worded as the unlisted entry (D225 P11: its own kind and unit)."""
        R = self.exchange()
        evaluation = decide('43274', R, kept=(unit(2),))
        self.assertEqual(evaluation.supporting, (E(2),))
        self.assertEqual(keys(evaluation), [('act_target', 11, QUESTION, rule(Q.Rule.EXCHANGE)),
                                            ('performed_status', 2, QUESTION, 'unlisted')])
        self.assertEqual((evaluation.held_facts[1].spans, evaluation.held_facts[1].result), ((unit(2),), None))
        found = item('43274', R, kept=(unit(2),))
        self.assertEqual((found.held.rank, found.message, found.fill.statements, found.fill.unlisted_what,
                          found.fill.unlisted_kind),
                         (2, Q.MessageId.UNLISTED_EVIDENCE, ((unit(2),),), ct.UnlistedWhat.ACT, Kind.STENT_REMOVAL))
        # evidence elsewhere: rule 2 reads none, and XCHG still reads the synthetic removal (D216): never READY
        evaluation = decide('43274', R, kept=(unit(1),))
        self.assertEqual(keys(evaluation), [('act_target', 11, QUESTION, rule(Q.Rule.EXCHANGE))])
        self.assertEqual(item('43274', R, kept=(unit(1),)).message, Q.MessageId.SAME_DUCT)

    def test_every_entry_on_the_evidence_holds_whatever_its_nature_or_kind(self):
        for what in ct.UnlistedWhat:
            for kind in (Kind.STENT_REMOVAL, Kind.BIOPSY, None):
                with self.subTest(what=what, kind=kind):
                    keys_ = keys(decide('43274', self.exchange(what, kind), kept=(Span(220, 230),)))
                    self.assertIn(('performed_status', 2, QUESTION, 'unlisted'), keys_)

    def test_an_unlisted_unit_on_a_cited_denial_is_asked_never_excluded(self):
        """"No polyps were removed." cited by 45385 excludes; an unlisted doubt of another kind (no doubt of the code's
        kinds: condition 5 holds) found in that very sentence holds it instead - the denial's scope asked, and rule 2's
        doubt, worded as the unlisted entry: its own nature and kind, its own unit (D225, refute-4a-r2 P11)."""
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
        self.assertEqual((found.held.rank, found.message, found.fill.statements, found.fill.unlisted_what,
                          found.fill.unlisted_kind),
                         (2, Q.MessageId.UNLISTED_EVIDENCE, ((unit(3),),), ct.UnlistedWhat.DOUBT, Kind.BIOPSY))

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


# --- repair r4a (refute-4a-r2; DECISIONS D216, D225's engine half, D226, D229's 4a P2, P3, P4, P8, P9) -----------------


def stent_placement(removal=None, *, duct=sup(ct.Duct.BILIARY), session=X(1)) -> Doc:
    """refute-4a-r2 p10: "The existing biliary stent was removed. A new 10 Fr plastic stent was placed." - an ERCP X1
    (its examination E1), the placement E2 filed (its duct ``duct``), 43274 citing only unit 2. ``removal``: the
    removal kept as an unlisted ACT (unit 5) with this session card, or filed (E5) with these facts."""
    doc = Doc()
    doc.session(1, SessionKind.ERCP)
    doc.exam(1)
    doc.act(2, Kind.STENT, duct=duct)
    if isinstance(removal, dict):
        doc.act(5, Kind.STENT_REMOVAL, **removal)
    elif removal is not None:
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, removal, session, unit(5)))
    return doc


def act_only_colonoscopy() -> Doc:
    """A colonoscopy X1 with no examination filed: its cold snare E2 only (row 7's act-only arm)."""
    doc = Doc()
    doc.session(1, SessionKind.COLONOSCOPY, reached=[sup(Extent.CECUM)])
    doc.act(2, Kind.SNARE, places=[sup(Landmark.SIGMOID_COLON)], device=sup(Device.COLD_SNARE))
    return doc


class AbsenceConditions(SimpleTestCase):
    """D216 (refute-4a-r2 P1, critical): every rule whose condition is the ABSENCE of a possibly performed act reads
    3.2.6 rule 3's synthetic doubted act - a kept unlisted ACT - as possibly performed, as the same act filed in doubt
    reads. The absence conditions of evaluate.py (the step's NOTES list each): XCHG's counterparts (43274, 43275);
    43276's pair candidates; row 7's possible examinations; 4.6 condition 5 (its clip or injection as a possible bleeding
    control, and a possible exchange of two synthetic acts). An unlisted doubt reads as a possibly performed act too
    (refute-r4a-r1 F1: UnlistedDoubts); an unlisted denial does not (question Q1)."""

    def test_xchg_reads_an_unlisted_removal_never_ready(self):
        """p10: 43274 is held with one item, the duct question naming the unlisted removal - as the removal filed in
        doubt, or with its duct unknown, holds it; never READY."""
        for name, removal in {'unlisted, card X1': Kind.STENT_REMOVAL,
                              'filed in doubt': dict(status=doubted(Status.PERFORMED)),
                              'filed, its duct unknown': {}}.items():
            with self.subTest(name):
                R = stent_placement(removal).build()
                evaluation = decide('43274', R, kept=(unit(2),))
                self.assertFalse(ready(evaluation))
                self.assertEqual(keys(evaluation), [('act_target', 11, QUESTION, rule(Q.Rule.EXCHANGE))])
                found = item('43274', R, kept=(unit(2),))
                self.assertEqual((found.message, found.fill.act, found.fill.words, found.fill.whole,
                                  found.fill.whole_words),
                                 (Q.MessageId.SAME_DUCT, Kind.STENT_REMOVAL, (unit(5),), Kind.STENT, (unit(2),)))
        self.assertTrue(ready(decide('43274', stent_placement(None).build(), kept=(unit(2),))))  # the control

    def test_xchg_reads_an_unlisted_act_of_every_session_it_may_be_in(self):
        """No session card, or a card the FactSet does not hold (4.11), is possibly the placement's session; a card
        naming another session the FactSet holds sets the act apart, as two supported sessions set filed acts apart. An
        act of umbrella kind covering the removal may be the removal; so may an act of no kind - beside the ERCP's
        examination established done it adds nothing to row 7 (D232), so the placement supports and XCHG asks the duct
        about it as about any counterpart. An unlisted DOUBT is a possibly performed act too (refute-r4a-r1 F1: 4.2, a
        doubt is never an absence); an unlisted DENIAL is a statement only (the step's NOTES, question Q1)."""
        for name, (entry, held) in {
                'no card': (unlisted(ct.UnlistedWhat.ACT, Kind.STENT_REMOVAL, None, unit(5)), True),
                'a card naming no session': (unlisted(ct.UnlistedWhat.ACT, Kind.STENT_REMOVAL, X(9), unit(5)), True),
                'no kind': (unlisted(ct.UnlistedWhat.ACT, None, X(1), unit(5)), True),
                'an intervention': (unlisted(ct.UnlistedWhat.ACT, Kind.INTERVENTION, X(1), unit(5)), True),
                'a stent exchange': (unlisted(ct.UnlistedWhat.ACT, Kind.STENT_EXCHANGE, X(1), unit(5)), True),
                'another session': (unlisted(ct.UnlistedWhat.ACT, Kind.STENT_REMOVAL, X(2), unit(5)), False),
                'a biopsy': (unlisted(ct.UnlistedWhat.ACT, Kind.BIOPSY, X(1), unit(5)), False),
                'an unlisted denial': (unlisted(ct.UnlistedWhat.DENIAL, Kind.STENT_REMOVAL, X(1), unit(5)), False),
                'an unlisted doubt': (unlisted(ct.UnlistedWhat.DOUBT, Kind.STENT_REMOVAL, X(1), unit(5)), True),
        }.items():
            with self.subTest(name):
                doc = stent_placement(None)
                doc.session(2, SessionKind.ERCP)
                doc.unlisted.append(entry)
                evaluation = decide('43274', doc.build(), kept=(unit(2),))
                self.assertEqual(not ready(evaluation), held)
                if held:
                    self.assertEqual(keys(evaluation), [('act_target', 11, QUESTION, rule(Q.Rule.EXCHANGE))])
                    duct = evaluation.held_facts[0]
                    self.assertEqual((duct.subject, duct.result, duct.spans), (None, None, (unit(2), unit(5))))

    def test_xchg_43275_reads_an_unlisted_placement(self):
        doc = Doc()
        doc.session(1, SessionKind.ERCP)
        doc.exam(1)
        doc.act(2, Kind.STENT_REMOVAL, duct=sup(ct.Duct.BILIARY))
        self.assertTrue(ready(decide('43275', doc.build())))
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.STENT, X(1), unit(5)))
        found = item('43275', doc.build())
        self.assertEqual((found.message, found.fill.act, found.fill.whole), (Q.MessageId.SAME_DUCT, Kind.STENT,
                                                                            Kind.STENT_REMOVAL))

    def test_43276_reads_a_synthetic_part_as_a_pair_candidate(self):
        """43276's pair candidates: a filed placement beside an unlisted removal is a possible exchange - held, bound
        on the placement, its one item the synthetic removal's witness (rank 2; SYNTHETIC_ACT for a kept unlisted act,
        D246) - never "not documented", and never excluded by a cited exchange denial (as with the removal filed in
        doubt)."""
        R = stent_placement(Kind.STENT_REMOVAL).build()
        evaluation = decide('43276', R)
        self.assertEqual(evaluation.supporting, ())
        self.assertEqual(evaluation.bindings, {(Kind.STENT_EXCHANGE,): E(2)})
        self.assertIn(('performed_status', 2, QUESTION, 'unlisted'), keys(evaluation))
        self.assertIn(('act_target', 11, QUESTION, rule(Q.Rule.EXCHANGE)), keys(evaluation))
        found = item('43276', R)
        self.assertEqual((found.message, found.fill.act, found.fill.words),
                         (Q.MessageId.SYNTHETIC_ACT, Kind.STENT_REMOVAL, (unit(5),)))
        for removal in (Kind.STENT_REMOVAL, dict(status=doubted(Status.PERFORMED))):
            with self.subTest(removal=removal):
                doc = stent_placement(removal)
                denial_event(doc, number=6, kind=Kind.STENT_EXCHANGE)
                evaluation = decide('43276', doc.build(), kept=(Span(600, 625),))
                self.assertIsNone(evaluation.exclusion)
                self.assertFalse(ready(evaluation))

    def test_condition_5_reads_two_synthetic_parts_and_an_unlisted_clip(self):
        """Condition 5: two kept unlisted acts that may be a removal and a placement of one session doubt 43276 (a
        possible exchange with no id to bind: no exclusion, held); one alone does not (excluded, as one filed part
        alone is). An unlisted clip or injection, whose purpose no card states, may be a bleeding control (D157(2)):
        a cited bleeding-control denial is asked, never decided, beside it."""
        def exchange_denied(*entries):
            doc = Doc()
            doc.session(1, SessionKind.ERCP)
            doc.exam(1)
            denial_event(doc, number=6, kind=Kind.STENT_EXCHANGE)
            doc.unlisted.extend(entries)
            return decide('43276', doc.build(), kept=(Span(600, 625),))

        both = exchange_denied(unlisted(ct.UnlistedWhat.ACT, Kind.STENT_REMOVAL, X(1), unit(4)),
                               unlisted(ct.UnlistedWhat.ACT, Kind.STENT, X(1), unit(5)))
        self.assertIsNone(both.exclusion)
        self.assertFalse(ready(both))
        alone = exchange_denied(unlisted(ct.UnlistedWhat.ACT, Kind.STENT_REMOVAL, X(1), unit(4)))
        self.assertIsNotNone(alone.exclusion)

        def bleeding_denied(*entries):
            doc = egd()
            denial_event(doc, number=6, kind=Kind.BLEEDING_CONTROL)
            doc.unlisted.extend(entries)
            return decide('43255', doc.build(), kept=(Span(600, 625),))

        self.assertIsNotNone(bleeding_denied().exclusion)
        for kind in (Kind.CLIP, Kind.INJECTION):
            with self.subTest(kind=kind):
                evaluation = bleeding_denied(unlisted(ct.UnlistedWhat.ACT, kind, X(1), unit(5)))
                self.assertIsNone(evaluation.exclusion)
                self.assertEqual([entry[:3] for entry in keys(evaluation)], [('statement_scope', 3, QUESTION)])

    def test_row_7_reads_a_synthetic_examination(self):
        """Row 7: an act-only session beside a kept unlisted examination act of it (or of no session, or of no kind) is
        not done - held, its one item the synthetic act's witness naming the act's own kind and quoting its own unit
        (SYNTHETIC_ACT for a kept unlisted act: D246) - as beside the same examination filed in doubt; a card naming
        another session, or an office visit's session (no examination), holds nothing."""
        for name, entry in {'card X1': unlisted(ct.UnlistedWhat.ACT, Kind.EXAMINATION, X(1), unit(5)),
                            'no card': unlisted(ct.UnlistedWhat.ACT, Kind.EXAMINATION, None, unit(5)),
                            'no kind': unlisted(ct.UnlistedWhat.ACT, None, X(1), unit(5))}.items():
            with self.subTest(name):
                doc = act_only_colonoscopy()
                doc.unlisted.append(entry)
                evaluation = self.held_by_row_7(doc.build())
                self.assertEqual(keys(evaluation), [('performed_status', 2, QUESTION, 'unlisted')])
                self.assertEqual((evaluation.held_facts[0].subject, evaluation.held_facts[0].spans), (X(1), (unit(5),)))
                found = item('45385', doc.build())
                self.assertEqual((found.message, found.fill.words),
                                 (Q.MessageId.SYNTHETIC_ACT, (unit(5),)))
                self.assertEqual(found.fill.act, Kind.EXAMINATION if entry.kind else Kind.OTHER)
        doc = act_only_colonoscopy()  # the filed analog: the same examination filed in doubt holds too
        doc.event(5, kind=sup(Kind.EXAMINATION), status=doubted(Status.PERFORMED), session=sup(X(1)))
        self.assertFalse(ready(decide('45385', doc.build())))
        doc = act_only_colonoscopy()
        doc.session(2, SessionKind.EGD)
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.EXAMINATION, X(2), unit(5)))
        self.assertTrue(ready(decide('45385', doc.build())))
        doc = Doc()
        doc.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.TOTAL_TIME))
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.EXAMINATION, X(1), unit(5)))
        self.assertEqual(EV.synthetic_examinations(doc.build(), X(1)), ())
        self.assertEqual(truths('99213', doc.build(), E(1))[rq.Requirement.SUP_SESSION_DONE], T)

    def test_row_7_a_synthetic_examination_beside_the_sessions_done_one_adds_nothing(self):
        """D232 (rules the earlier NOTES' question Q2, option (b)): beside an examination established as the session's,
        a synthetic examination adds nothing - row 7 reads it only in an act-only session - so 45385 is READY, row 7
        T. (The base code keeps 3.2.6 rule 3's base_included hold: step 4d's combination.)"""
        doc = colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.EXAMINATION, X(1), unit(5)))
        self.assertTrue(ready(decide('45385', doc.build())))
        self.assertEqual(truths('45385', doc.build(), E(2))[rq.Requirement.SUP_SESSION_DONE], T)

    def held_by_row_7(self, R):
        evaluation = decide('45385', R)
        self.assertFalse(ready(evaluation))
        self.assertEqual(truths('45385', R, E(2))[rq.Requirement.SUP_SESSION_DONE], U)
        return evaluation


class BindingCount(SimpleTestCase):
    """4a P2 (step 1f's hand-off R9(e)): the binding's "fewest non-T requirements" counts over requirements_of(code) -
    the code-specific rows (TECH, SITE, ...) included - so the item names the act closest to READY."""

    def test_p11_the_act_that_can_never_support_is_not_bound(self):
        """p11: two balloon dilations under 43249, neither supporting. E2 (distal esophagus): its date relation and
        performer unresolved, TECH and SITE met - 2 rows not T. E3 (duodenum): its date relation unresolved, SITE F -
        2 rows not T, counted over requirements_of('43249'). Rank and kind tie, so document order binds E2."""
        doc = egd()
        doc.act(2, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS)], device=sup(Device.BALLOON), date=unres(ON),
                performer=unres(TEAM))
        doc.act(3, Kind.DILATION, places=[sup(Landmark.DUODENUM)], device=sup(Device.BALLOON), date=unres(ON))
        R = doc.build()
        group = (Kind.DILATION,)
        self.assertEqual([EV.unmet('43249', group, R, EV.support('43249', group, R, event)) for event in (E(2), E(3))],
                         [2, 2])
        self.assertEqual(decide('43249', R).bindings, {group: E(2)})
        found = item('43249', R)
        self.assertEqual((found.held.subject, found.fill.place), (E(2), Landmark.DISTAL_ESOPHAGUS))
        # E3's SITE failure alone (its date established) still counts: 1 against E2's 2 - E3 is closer to READY
        doc.act(3, Kind.DILATION, places=[sup(Landmark.DUODENUM)], device=sup(Device.BALLOON), date=sup(ON),
                performer=unres(TEAM))
        self.assertEqual(EV.unmet('43249', group, doc.build(), EV.support('43249', group, doc.build(), E(3))), 2)


class Row7Repairs(SimpleTestCase):
    """4a P3, P8, P9: row 7's family gate on the established arm (P-MONO), "done" by an examination established as the
    session's (MR3), and the dangling-id arm of _may_be_in (MR4)."""

    @staticmethod
    def office(tie):
        """p12b: an office visit E1 (99213) and "Colonoscopy in 2019 was normal." filed as an examination E2 (performed,
        an earlier date), its session tie ``tie``."""
        doc = Doc()
        doc.session(1, SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.TOTAL_TIME))
        over = dict(kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), date=sup(EARLIER))
        if tie is not None:
            over['session'] = tie
        doc.event(2, **over)
        return doc.build()

    def test_p3_an_office_visits_session_holds_no_examination_whatever_its_tie(self):
        """P3 (P-MONO): the established tie is gated by the family too, so the visit is READY with the tie supported,
        weakened or silent - never HELD on the supported tie and READY on its weakening. The feeding-tube family the
        same (p12: an examination in doubt filed in a tube replacement's session)."""
        for tie in (sup(X(1)), unres(X(1)), None):
            with self.subTest(tie=tie and tie.result):
                R = self.office(tie)
                self.assertEqual(EV.examinations(R, X(1)), ())
                self.assertTrue(ready(decide('99213', R)))
        for tie in (sup(X(1)), unres(X(1))):
            with self.subTest(family='feeding_tube', tie=tie.result):
                doc = Doc()
                doc.session(1, SessionKind.FEEDING_TUBE)
                doc.act(1, Kind.TUBE_REPLACEMENT)
                doc.event(2, kind=sup(Kind.EXAMINATION), session=tie, status=unres(Status.PERFORMED), date=sup(ON),
                          performer=sup(TEAM), entry=sup(DC))
                self.assertTrue(ready(decide('43762', doc.build())))
        # the session's kind not established leaves an examination possible, whatever its tie: held (fail-closed)
        doc = Doc()
        doc.session(1, unres(SessionKind.OFFICE_EM), encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.TOTAL_TIME))
        doc.event(2, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), date=sup(EARLIER), session=sup(X(1)))
        self.assertEqual(EV.examinations(doc.build(), X(1)), (E(2),))

    def test_p8_done_needs_an_examination_established_as_the_sessions(self):
        """p16 (MR3): an act-only colonoscopy X1, a sessionless examination E5 done today by the team (it may be X1's or
        another session's) and a sessionless plan E4. E5 passing rows 2-5 is not X1's own done examination, so the
        plan may be X1's only one: held, every witness on the plan."""
        doc = act_only_colonoscopy()
        doc.event(5, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), date=sup(ON), performer=sup(TEAM),
                  entry=sup(DC))
        doc.event(4, kind=sup(Kind.EXAMINATION), status=sup(Status.PLANNED), date=sup(ct.DateRelation.LATER_DATE))
        R = doc.build()
        self.assertEqual(EV.examinations(R, X(1)), (E(5), E(4)))
        evaluation = decide('45385', R)
        self.assertFalse(ready(evaluation))
        self.assertEqual({held.subject for held in evaluation.held_facts}, {E(4)})
        doc.event(5, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), date=sup(ON), performer=sup(TEAM),
                  entry=sup(DC), session=sup(X(1)))  # the control: E5 established as X1's own done examination
        self.assertTrue(ready(decide('45385', doc.build())))

    def test_p9_an_examination_tied_to_a_missing_session_may_be_any_sessions(self):
        """MR4 (4.11): K2 leaves a tie naming a session the FactSet does not hold unresolved, still claiming it. Such an
        examination may be any session's: in an act-only session it holds; beside the session's done examination,
        in doubt, it holds too."""
        for name, base in {'act-only': act_only_colonoscopy, 'beside its done examination': colonoscopy}.items():
            with self.subTest(name):
                doc = base()
                doc.event(5, kind=sup(Kind.EXAMINATION), status=doubted(Status.PERFORMED), session=unres(X(9)),
                          date=sup(ON), performer=sup(TEAM), entry=sup(DC))
                R = doc.build()
                self.assertIn(E(5), EV.examinations(R, X(1)))
                evaluation = decide('45385', R)
                self.assertFalse(ready(evaluation))
                self.assertIn(E(5), {held.subject for held in evaluation.held_facts})


class UpperStations(SimpleTestCase):
    """4a P4: STATIONS and LIMITED read only the members that may name an upper station; an unestablished station
    outside the upper tract (the jejunum) holds nothing."""

    @staticmethod
    def eus(extra, kind=None, reached=(sup(Extent.SECOND_PORTION_DUODENUM),)):
        """p14: an upper EUS X1, its three upper stations supported examined and ``extra`` members, reaching the second
        portion of the duodenum (its examination E1; with ``kind``, an act E2 of it)."""
        doc = Doc()
        doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.UPPER), reached=list(reached),
                    stations=[sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM), *extra])
        doc.exam(1, places=[sup(Landmark.PANCREAS)])
        if kind is not None:
            doc.act(2, kind, places=[sup(Landmark.PANCREAS)])
        return doc.build()

    def test_p14_an_unestablished_jejunum_holds_nothing(self):
        for name, jejunum in {'unresolved': unres(Station.JEJUNUM), 'doubted': doubted(Station.JEJUNUM),
                              'supported': sup(Station.JEJUNUM), 'negated': neg(Station.JEJUNUM)}.items():
            with self.subTest(name):
                self.assertTrue(ready(decide('43259', self.eus([jejunum]))))
                self.assertTrue(ready(decide('43242', self.eus([jejunum], Kind.FNA))))
        # a member that may name an upper station is still read: the stomach's doubted reading holds
        self.assertFalse(ready(decide('43259', self.eus([doubted(Station.JEJUNUM, Station.STOMACH)]))))

    def test_limited_never_rests_on_the_jejunum(self):
        """43231 (a reach short of the duodenum needed) with no reach stated: its question rests on no station outside
        the upper tract - before, the unresolved jejunum was the witness."""
        R = eus_fna([unres(Station.JEJUNUM)], reached=())
        evaluation = decide('43231', R)
        self.assertEqual([entry[:3] for entry in keys(evaluation)], [('exam_stations', 13, QUESTION)])
        self.assertIsNone(evaluation.held_facts[0].result)


class TractD226(SimpleTestCase):
    """D226: an EUS session filed pancreatobiliary fits every upper EUS code's TRACT row; the lower EUS codes still need
    lower."""

    def test_pancreatobiliary_is_upper_for_an_eus(self):
        every = [sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)]
        R = eus_fna(every, tract=sup(ct.Tract.PANCREATOBILIARY))
        for code in ('43259', '43242'):
            with self.subTest(code=code):
                self.assertTrue(ready(decide(code, R)))
        self.assertEqual([row.truth for row in EV.code_rows('43259', (Kind.EXAMINATION,), R, E(1))
                          if row.requirement is Tag.TRACT], [T])
        doc = Doc()
        doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.PANCREATOBILIARY), reached=[sup(Extent.SIGMOID_COLON)])
        doc.exam(1)
        self.assertEqual(keys(decide('45341', doc.build())), [('procedure', 8, EXPLANATION, rule(Q.Rule.TRACT))])
        R = eus_fna(every, tract=unres(ct.Tract.PANCREATOBILIARY))
        self.assertEqual([entry[:3] for entry in keys(decide('43259', R))], [('procedure', 8, QUESTION)])


# --- repair r4a, round 2 (refute-r4a-r1: F1, F4, F7; F6's doubted counterpart; F5's unit-less entry) ------------------


def stent_doubt(kind=Kind.STENT_REMOVAL, session=X(1), number=5):
    """p20: "It is unclear whether the old biliary stent was removed." kept as an unlisted DOUBT (kind ``kind``, card
    ``session``) in its own unit."""
    return unlisted(ct.UnlistedWhat.DOUBT, kind, session, unit(number))


def bleeding(**over) -> FactSet:
    """An EGD X1 with a bleeding control E2 (its kind supported) and ``over``'s facts: 43255."""
    doc = egd()
    doc.act(2, Kind.BLEEDING_CONTROL, places=[sup(Landmark.STOMACH)], **over)
    return doc.build()


def lower_eus(*reached, approach=None, stoma=True) -> FactSet:
    """refute-r4a-r1 p29: a lower EUS X1 (its examination E1) of the stoma class's code 44406, its reach ``reached``,
    its approach ``approach``, an anatomy entry of type stoma supported (``stoma``)."""
    doc = Doc()
    doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=list(reached), approach=approach)
    if stoma:
        doc.entry(1, type=sup(ct.AnatomyType.STOMA))
    doc.exam(1)
    return doc.build()


class UnlistedDoubts(SimpleTestCase):
    """refute-r4a-r1 F1 (critical; built fail-closed, the step's NOTES question Q1): an unlisted DOUBT about an act
    leaves the act possibly performed (4.2 [R:HO-1]: a doubt is never an absence), so every absence condition reads it
    as it reads the stated act (D216) - the weaker statement never releases what the stated act holds (P6). An unlisted
    DENIAL is a statement only (3.2.6 rule 4; condition 5)."""

    def test_p20_an_unlisted_doubt_of_the_removal_holds_43274_never_ready(self):
        """p20: the placement E2 (biliary) filed and "It is unclear whether the old biliary stent was removed." kept as
        an unlisted doubt (card X1, no card, or a card naming no session): 43274 held with one item - the duct question
        naming the removal it doubts, quoting its own unit - as the stated act holds it; never READY. A card naming
        another session the FactSet holds sets the doubt apart, as it sets a filed act apart."""
        for name, entry in {'card X1': stent_doubt(), 'no card': stent_doubt(session=None),
                            'a card naming no session': stent_doubt(session=X(9)),
                            'the stated act': unlisted(ct.UnlistedWhat.ACT, Kind.STENT_REMOVAL, X(1), unit(5))}.items():
            with self.subTest(name):
                doc = stent_placement(None)
                doc.unlisted.append(entry)
                R = doc.build()
                evaluation = decide('43274', R, kept=(unit(2),))
                self.assertFalse(ready(evaluation))
                self.assertEqual(keys(evaluation), [('act_target', 11, QUESTION, rule(Q.Rule.EXCHANGE))])
                found = item('43274', R, kept=(unit(2),))
                self.assertEqual((found.message, found.fill.act, found.fill.words, found.fill.whole),
                                 (Q.MessageId.SAME_DUCT, Kind.STENT_REMOVAL, (unit(5),), Kind.STENT))
        doc = stent_placement(None)
        doc.session(2, SessionKind.ERCP)
        doc.unlisted.append(stent_doubt(session=X(2)))
        self.assertTrue(ready(decide('43274', doc.build(), kept=(unit(2),))))
        doc = Doc()  # 43275: an unlisted doubt of the placement beside the filed removal
        doc.session(1, SessionKind.ERCP)
        doc.exam(1)
        doc.act(2, Kind.STENT_REMOVAL, duct=sup(ct.Duct.BILIARY))
        doc.unlisted.append(stent_doubt(Kind.STENT))
        self.assertEqual(keys(decide('43275', doc.build())), [('act_target', 11, QUESTION, rule(Q.Rule.EXCHANGE))])

    def test_an_unlisted_denial_is_no_possibly_performed_act(self):
        """Question Q1's built reading: "The old stent was not removed." kept as an unlisted DENIAL leaves 43274 READY
        (4.3 XCHG's X1: the removal negated, 43274 can be READY); condition 5 still reads it, so 43276 is never excluded
        beside it."""
        doc = stent_placement(None)
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DENIAL, Kind.STENT_REMOVAL, X(1), unit(5)))
        R = doc.build()
        self.assertEqual(EV.synthetic_possible(R), ())
        self.assertTrue(ready(decide('43274', R, kept=(unit(2),))))
        self.assertEqual(EV.synthetic_possible(stent_placement(Kind.STENT_REMOVAL).build()),
                         (unlisted(ct.UnlistedWhat.ACT, Kind.STENT_REMOVAL, X(1), unit(5)),))

    def test_every_absence_condition_reads_an_unlisted_doubt(self):
        """43276's pair candidates: a filed placement beside an unlisted doubt of the removal is a possible exchange -
        bound on the placement, its one item the doubt (rank 2) naming the removal, true for a doubt - and a cited
        exchange denial beside them excludes nothing (p31: the first patch EXCLUDED 43276 there). 4.6 condition 5:
        two unlisted doubts that may be one session's removal and placement keep a cited exchange denial from excluding
        43276. Row 7: an act-only colonoscopy beside an unlisted doubt of its examination (or of no kind) is not done;
        a doubt carded to another session holds nothing."""
        doc = stent_placement(None)
        doc.unlisted.append(stent_doubt())
        evaluation = decide('43276', doc.build())
        self.assertEqual(evaluation.bindings, {(Kind.STENT_EXCHANGE,): E(2)})
        self.assertIn(('performed_status', 2, QUESTION, 'unlisted'), keys(evaluation))
        found = item('43276', doc.build())
        self.assertEqual((found.message, found.fill.act, found.fill.words), (Q.MessageId.DOUBT, Kind.STENT_REMOVAL,
                                                                            (unit(5),)))
        denial_event(doc, number=6, kind=Kind.STENT_EXCHANGE)
        evaluation = decide('43276', doc.build(), kept=(Span(600, 625),))
        self.assertIsNone(evaluation.exclusion)
        self.assertFalse(ready(evaluation))
        doc = Doc()
        doc.session(1, SessionKind.ERCP)
        doc.exam(1)
        denial_event(doc, number=6, kind=Kind.STENT_EXCHANGE)
        doc.unlisted += [stent_doubt(number=4), stent_doubt(Kind.STENT)]
        evaluation = decide('43276', doc.build(), kept=(Span(600, 625),))
        self.assertIsNone(evaluation.exclusion)
        self.assertFalse(ready(evaluation))
        for name, kind in {'kind examination': Kind.EXAMINATION, 'no kind': None}.items():
            with self.subTest(name):
                doc = act_only_colonoscopy()
                doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, kind, X(1), unit(5)))
                R = doc.build()
                self.assertEqual(truths('45385', R, E(2))[rq.Requirement.SUP_SESSION_DONE], U)
                self.assertIn(('performed_status', 2, QUESTION, 'unlisted'), keys(decide('45385', R)))
        doc = act_only_colonoscopy()
        doc.session(2, SessionKind.EGD)
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.EXAMINATION, X(2), unit(5)))
        self.assertTrue(ready(decide('45385', doc.build())))

    def test_row_7_beside_the_sessions_done_examination_adds_nothing_for_an_act_or_a_doubt(self):
        """F2 / question Q2, ruled by D232 (option (b)): beside the session's own done examination a synthetic
        examination adds nothing - the stated act and the doubt alike (the doubt still never releases what the act
        holds: neither holds row 7 here, and both do in an act-only session, test_every_absence_condition_*)."""
        for what in (ct.UnlistedWhat.ACT, ct.UnlistedWhat.DOUBT):
            with self.subTest(what=what):
                doc = colonoscopy()
                doc.unlisted.append(unlisted(what, Kind.EXAMINATION, X(1), unit(7)))
                self.assertTrue(ready(decide('45385', doc.build())))


class OwnAttribute(SimpleTestCase):
    """refute-r4a-r1 F4 (D225 P7; r3c-2's request R5): every witness rests on the fact that is not T under that fact's
    own attribute - a contradicted purpose is no conflict about the cause, a contradicted reach none about the stations,
    a contradicted target lesion none about where the act was done (p22, p26)."""

    def witnesses(self, code, R):
        return [(held.fact, held.attribute, held.subject, held.result) for held in decide(code, R).held_facts]

    def test_cause_rests_on_the_purpose_or_the_cause(self):
        """p22 (1): 43255, the bleeding control's purpose contradicted hemostasis / prophylaxis and its cause supported:
        the conflict is about the purpose; the cause contradicted: about the cause."""
        hemostasis = ct.Purpose.HEMOSTASIS
        R = bleeding(purpose=contra(hemostasis, ct.Purpose.PROPHYLAXIS), cause=sup(ct.Cause.PRE_EXISTING_LESION))
        self.assertEqual(self.witnesses('43255', R),
                         [('conflict:bleeding_control', A.PURPOSE, E(2), Res.CONTRADICTED)])
        R = bleeding(purpose=sup(hemostasis), cause=contra(ct.Cause.PRE_EXISTING_LESION, ct.Cause.SPONTANEOUS))
        self.assertEqual(self.witnesses('43255', R), [('conflict:bleeding_control', A.CAUSE, E(2), Res.CONTRADICTED)])

    def test_stations_and_limited_rest_on_the_reach_or_the_station(self):
        """p22 (2), p26 (43237): the three stations supported and the reach contradicted - the conflict is about the
        reach (the session's, its examination's key); a station contradicted - about the stations; a reach not
        established (no conflict) - its question rests on the reach too."""
        every = [sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)]
        reach = (contra(Extent.SECOND_PORTION_DUODENUM, Extent.STOMACH),)
        for code, stations in (('43259', every), ('43242', every), ('43237', every[:2])):
            with self.subTest(code=code):
                R = eus_fna(stations, reached=reach)
                self.assertEqual(self.witnesses(code, R), [('conflict:examination', A.REACHED, X(1), Res.CONTRADICTED)])
        R = eus_fna([sup(Station.ESOPHAGUS), contra(Station.STOMACH, Station.DUODENUM)])
        self.assertEqual(self.witnesses('43242', R), [('conflict:examination', A.STATIONS, X(1), Res.CONTRADICTED)])
        R = eus_fna(every, reached=(unres(Extent.SECOND_PORTION_DUODENUM),))
        self.assertEqual([(fact, attribute) for fact, attribute, _, _ in self.witnesses('43242', R)],
                         [('exam_stations', A.REACHED)])
        R = eus_fna([sup(Station.ESOPHAGUS), unres(Station.STOMACH)], reached=())
        self.assertEqual([(fact, attribute) for fact, attribute, _, _ in self.witnesses('43231', R)],
                         [('exam_stations', A.STATIONS)])

    def test_site_rests_on_the_lesion_the_acts_places_or_the_lesions_places(self):
        """p26: 43249, a balloon dilation at the distal esophagus whose target lesion is contradicted L1 / L2 (both at
        the distal esophagus): the conflict is about the lesion; the act's own place contradicted - about where it was
        done; its supported lesion's place contradicted - about where the lesion lies."""
        doc = dilation(sup(Landmark.DISTAL_ESOPHAGUS), lesion=contra(L(1), L(2)))
        doc.lesion(1, lesion_places=[sup(Landmark.DISTAL_ESOPHAGUS)])
        doc.lesion(2, lesion_places=[sup(Landmark.DISTAL_ESOPHAGUS)])
        self.assertEqual(self.witnesses('43249', doc.build()),
                         [('conflict:dilation', A.TARGET_LESION, E(2), Res.CONTRADICTED)])
        R = dilation(contra(Landmark.DISTAL_ESOPHAGUS, Landmark.STOMACH)).build()
        self.assertEqual(self.witnesses('43249', R), [('conflict:dilation', A.TARGET_PLACES, E(2), Res.CONTRADICTED)])
        doc = dilation(sup(Landmark.DISTAL_ESOPHAGUS), lesion=sup(L(1)))
        doc.lesion(1, lesion_places=[contra(Landmark.DISTAL_ESOPHAGUS, Landmark.STOMACH)])
        self.assertEqual(self.witnesses('43249', doc.build()),
                         [('conflict:dilation', A.PLACES, E(2), Res.CONTRADICTED)])


class LowerApproach(SimpleTestCase):
    """refute-r4a-r1 F7 (HO-8, 4.8): LOWER records the stoma class's approach beside its reach whenever either is not
    T, so an unestablished reach never hides the RANK row 8 approach - the item asks the approach first."""

    def test_p29_the_approach_is_recorded_beside_an_open_reach(self):
        """p29: 44406, reached [sigmoid colon supported, descending colon unresolved], the approach silent, a stoma
        entry supported: the extent question AND the approach question are held; the item is the approach (row 8)."""
        R = lower_eus(sup(Extent.SIGMOID_COLON), unres(Extent.DESCENDING_COLON))
        evaluation = decide('44406', R)
        self.assertEqual([(held.fact, held.rank, held.kind, held.attribute) for held in evaluation.held_facts],
                         [('extent', 14, QUESTION, A.REACHED), ('procedure', 8, QUESTION, A.APPROACH)])
        self.assertEqual(item('44406', R).message, Q.MessageId.EXAMINATION_ROUTE)

    def test_every_reach_beside_every_approach(self):
        """The reach's witness and the approach's are each recorded when not T; the row is F when either rests on an
        established failure. A reach outside the class beside an approach established oral: two explanations, the
        approach's asked first (row 8); no reach stated beside through_stoma with no stoma entry: two questions; the
        reach met beside through_stoma and a stoma entry: READY."""
        R = lower_eus(sup(Extent.DUODENUM), approach=sup(ct.Approach.ORAL))
        self.assertEqual(keys(decide('44406', R)), [('extent', 14, EXPLANATION, rule(Q.Rule.LOWER)),
                                                    ('procedure', 8, EXPLANATION, rule(Q.Rule.LOWER))])
        self.assertEqual([row.truth for row in EV.code_rows('44406', (Kind.EXAMINATION,), R, E(1))
                          if row.requirement is Tag.LOWER], [F])
        self.assertEqual(item('44406', R).message, Q.MessageId.EXAMINATION_APPROACH)
        R = lower_eus(approach=sup(ct.Approach.THROUGH_STOMA), stoma=False)
        self.assertEqual([entry[:3] for entry in keys(decide('44406', R))],
                         [('extent', 14, QUESTION), ('procedure', 8, QUESTION)])
        self.assertEqual([row.truth for row in EV.code_rows('44406', (Kind.EXAMINATION,), R, E(1))
                          if row.requirement is Tag.LOWER], [U])
        self.assertTrue(ready(decide('44406', lower_eus(sup(Extent.STOMA), approach=sup(ct.Approach.THROUGH_STOMA)))))
        # a non-stoma class reads no approach (45341: the sigmoidoscopic class)
        doc = Doc()
        doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=[unres(Extent.SIGMOID_COLON)],
                    approach=sup(ct.Approach.ORAL))
        doc.exam(1)
        self.assertEqual([entry[:3] for entry in keys(decide('45341', doc.build()))], [('extent', 14, QUESTION)])


class SameDuctCounterpart(SimpleTestCase):
    """D225 beside refute-r4a-r1 F6: a stent act beside a filed counterpart in the same duct whose status is not
    established is held by whether the two were one exchange, ABOUT THE COUNTERPART - the act whose performance is
    unknown - never about the code's own act, whose status is supported. Both established (F6's p28) stays about the
    code's own act (question Q7: no id words "the two are one exchange")."""

    def test_the_doubted_removal_is_named(self):
        R = stent_placement(dict(status=doubted(Status.PERFORMED), duct=sup(ct.Duct.BILIARY))).build()
        evaluation = decide('43274', R, kept=(unit(2),))
        self.assertEqual([(held.fact, held.rank, held.subject, held.result) for held in evaluation.held_facts],
                         [('performed_status', 4, E(5), Res.UNKNOWN)])
        found = item('43274', R, kept=(unit(2),))
        self.assertEqual((found.message, found.fill.act, found.fill.words), (Q.MessageId.STATUS, Kind.STENT_REMOVAL,
                                                                            (unit(5),)))
        R = stent_placement(dict(duct=sup(ct.Duct.BILIARY))).build()  # p28: both established
        self.assertEqual([(held.subject, held.result) for held in decide('43274', R, kept=(unit(2),)).held_facts],
                         [(E(2), None)])


class UnitlessEntries(SimpleTestCase):
    """refute-r4a-r1 F5: a kept unlisted act or doubt with no units (pass 2 named no unit the reader knows) is still
    read by every absence condition - fail-closed, never READY - and its held code still carries exactly one item; that
    item quotes nothing of the entry (it has no words), which wording's SYNTHETIC_ACT, DOUBT and SAME_DUCT name without
    a quote since D246 (repair r3c; D160 (3)'s rule; tests/v2/test_questions.py OneItem builds each)."""

    def test_a_unitless_entry_still_holds_with_one_item(self):
        doc = act_only_colonoscopy()
        doc.unlisted.append(UnlistedStatement(units=(), what=ct.UnlistedWhat.ACT, kind=Kind.EXAMINATION, session=X(1)))
        R = doc.build()
        self.assertFalse(ready(decide('45385', R)))
        found = item('45385', R)
        self.assertEqual((found.message, found.fill.act, found.fill.words),
                         (Q.MessageId.SYNTHETIC_ACT, Kind.EXAMINATION, ()))
        doc = stent_placement(None)
        doc.unlisted.append(UnlistedStatement(units=(), what=ct.UnlistedWhat.DOUBT, kind=Kind.STENT_REMOVAL,
                                              session=X(1)))
        R = doc.build()
        self.assertFalse(ready(decide('43274', R, kept=(unit(2),))))
        found = item('43274', R, kept=(unit(2),))
        self.assertEqual((found.message, found.fill.act, found.fill.words), (Q.MessageId.SAME_DUCT, Kind.STENT_REMOVAL,
                                                                            ()))


# --- repair r4a of round w7r (DECISIONS D232, D240) -------------------------------------------------------------------


def p41(what=ct.UnlistedWhat.DOUBT, card=X(1), egd_beside=False, kind=Kind.EXAMINATION) -> Doc:
    """refute-r4a-r2 p41 (N1): a colonoscopy X1 to the cecum, its examination E1 established done, the cold snare E2 of
    L1 at the sigmoid colon, every fact established; pass 2's ONE kept unlisted entry of kind examination in unit 9 -
    with card X1 (e.g. "It is unclear whether the colonoscopy was complete.") or none (e.g. "It is not known whether
    she had a colonoscopy before."). ``egd_beside``: also an EGD X2 (its examination E3 done, a biopsy E4 at the
    stomach)."""
    doc = colonoscopy()
    if egd_beside:
        doc.session(2, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(3, session=X(2))
        doc.act(4, Kind.BIOPSY, session=X(2), places=[sup(Landmark.STOMACH)])
    if what is not None:
        doc.unlisted.append(unlisted(what, kind, card, unit(9)))
    return doc


class D232Row7(SimpleTestCase):
    """D232 (refute-r4a-r2 N1, high; the earlier NOTES' question Q2, option (b)): beside an examination established as
    the session's, a synthetic examination adds nothing - row 7 reads it only in an act-only session (``act_only``:
    combination.session_done's act-only arm, D227's one derivation). The base code keeps 3.2.6 rule 3's base_included
    hold (step 4d's) and an unlisted doubt keeps 3.2.6 rule 4's pairing with the possibly positive acts of its kinds
    (row 8); F1's reading of a removal doubt (XCHG, 43274 and 43276) stays (UnlistedDoubts). The sentences
    (D232's naming): tests/v2/test_questions.py D232Sentences."""

    def test_p41_an_unlisted_doubt_beside_the_colonoscopys_done_examination_leaves_45385_ready(self):
        """p41: one kept unlisted doubt (or act) of kind examination, card X1 or none, beside the colonoscopy's done
        examination - 45385 READY, row 7 T (the first patch's outcome; r4a round 2 held it). An act of no kind adds
        nothing either; a doubt of no kind still holds 45385, through 3.2.6 rule 4 alone (row 8: it pairs with every
        possibly positive act of every session, the snare E2 included), never through row 7."""
        for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.ACT):
            for card in (X(1), None):
                for kind in (Kind.EXAMINATION, None):
                    with self.subTest(what=what, card=card, kind=kind):
                        R = p41(what, card, kind=kind).build()
                        self.assertEqual(truths('45385', R, E(2))[rq.Requirement.SUP_SESSION_DONE], T)
                        if what is ct.UnlistedWhat.DOUBT and kind is None:
                            self.assertEqual(truths('45385', R, E(2))[rq.Requirement.SUP_CLEAN], U)
                            self.assertEqual([(held.rank, held.cause, held.subject)
                                              for held in decide('45385', R).held_facts], [(2, 'unlisted', E(2))])
                            continue
                        self.assertTrue(ready(decide('45385', R)))
                        self.assertIsNone(item('45385', R))

    def test_p41_beside_an_egd_the_unlisted_doubt_holds_nothing_through_row_7(self):
        """p41's no-card variant: beside an EGD X2 whose examination E3 is done, 43239 (the biopsy E4) and 45385 are
        READY - row 7 no longer names "the upper endoscopy" in doubt for a sentence about another examination."""
        R = p41(card=None, egd_beside=True).build()
        for code, act in (('43239', E(4)), ('45385', E(2))):
            with self.subTest(code=code):
                self.assertTrue(ready(decide(code, R)))
                self.assertEqual(truths(code, R, act)[rq.Requirement.SUP_SESSION_DONE], T)

    def test_the_base_code_keeps_3_2_6_rule_4s_pair_with_the_examination(self):
        """An unlisted doubt keeps 3.2.6 rule 4: of kind examination, it pairs with each session's examination
        (card X1: the colonoscopy's E1; no card: every session's) - 45378 (and, with no card, 43235) held, its item
        rule 4's pair at RANK row 2 (D228), cause unlisted, about the examination, never row 7's synthetic doubt; never
        READY. (The other session's examination is a candidate of another family, row 6: its witness is kept, HO-8.)
        Carded X1, the doubt never pairs with the EGD's examination: 43235 READY. An unlisted act is no rule-4
        statement (row 8 reads denials and doubts), so beside the done examination it holds 45378 only through step
        4d's base_included."""
        for card in (X(1), None):
            with self.subTest(card=card):
                R = p41(card=card, egd_beside=True).build()
                for code, examination in (('45378', E(1)), ('43235', E(3))):
                    evaluation = decide(code, R)
                    self.assertFalse([held for held in evaluation.held_facts
                                      if held.cause == 'unlisted' and held.subject in (X(1), X(2))])
                    if code == '43235' and card == X(1):
                        self.assertTrue(ready(evaluation))
                        continue
                    found = item(code, R)
                    self.assertEqual((found.held.fact, found.held.rank, found.held.cause, found.held.subject),
                                     ('performed_status', 2, 'unlisted', examination))
        self.assertTrue(ready(decide('45378', p41(ct.UnlistedWhat.ACT, None).build())))

    def test_an_examination_established_but_not_done_reads_no_synthetic_one(self):
        """"Row 7 reads it only in an act-only session": beside an examination established as the session's that is not
        done (its date not established), the session is held by that examination's own witness, never by the synthetic
        act's doubt (no ``unlisted`` cause)."""
        doc = colonoscopy()
        doc.exam(1, date=unres(ON))
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.EXAMINATION, X(1), unit(9)))
        evaluation = decide('45385', doc.build())
        self.assertEqual(keys(evaluation), [('event_time', 6, QUESTION, 'appraisal:unclear')])
        self.assertEqual(evaluation.held_facts[0].subject, E(1))

    def test_an_act_only_session_still_reads_it_and_a_weakened_tie_makes_a_session_act_only(self):
        """The act-only arm: no event established as the session's examination - a colonoscopy whose examination's kind
        or session is not established (weakened) is act-only, so the synthetic examination holds again (monotone under
        9.4: weakening never establishes an examination)."""
        doc = act_only_colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.EXAMINATION, None, unit(9)))
        self.assertTrue(EV.act_only(doc.build(), X(1)))
        self.assertIn(('performed_status', 2, QUESTION, 'unlisted'), keys(decide('45385', doc.build())))
        R = p41(ct.UnlistedWhat.DOUBT, X(1)).build()
        self.assertFalse(EV.act_only(R, X(1)))
        for name, kind, session in (('kind', unres(Kind.EXAMINATION), sup(X(1))),
                                    ('session', sup(Kind.EXAMINATION), unres(X(1)))):
            with self.subTest(weakened=name):
                doc = p41(ct.UnlistedWhat.DOUBT, X(1))
                doc.act(1, kind, session=session)
                self.assertTrue(EV.act_only(doc.build(), X(1)))
                self.assertFalse(ready(decide('45385', doc.build())))


def site_fit(second=sup(Landmark.DUODENAL_BULB), device=sup(Device.BALLOON)) -> FactSet:
    """6c B (D240): "The distal esophageal stricture was dilated with a balloon. The duodenal bulb stricture was dilated
    with a balloon." - an EGD X1 (its examination E3), the esophageal dilation E1 (balloon, the distal esophagus) and the
    duodenal one E2 (``device``, ``second`` its place), every fact established."""
    doc = Doc()
    doc.session(1, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(3)
    doc.act(1, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS)], device=sup(Device.BALLOON))
    doc.act(2, Kind.DILATION, places=[second] if second is not None else [], device=device)
    return doc.build()


class D240SiteFit(SimpleTestCase):
    """D240 (6c B, high; D29's installed reading kept: "A verified target outside the class does not support"):
    evaluate's code rows read only the supporting acts within the code's SITE class - beside an act established within
    the class, one established outside it leaves E* and no code row reads it (``_site_fit``). Combination's half (the
    claims, step r4d) and gate 6's CORPUS entry (6c) are not this step's."""

    def test_the_site_fit_input_gives_43249_on_the_esophageal_act_and_43245_on_the_duodenal_one(self):
        R = site_fit()
        for code, act in (('43249', E(1)), ('43245', E(2))):
            with self.subTest(code=code):
                evaluation = decide(code, R)
                self.assertTrue(ready(evaluation))
                self.assertEqual(evaluation.supporting, (act,))
                self.assertIsNone(item(code, R))

    def test_an_act_outside_the_class_holds_nothing_through_the_codes_other_rows(self):
        """The duodenal dilation with a wire-guided bougie: its another-technique misfit is never read for 43249 (it is
        no supporting act of 43249, whose rows read the esophageal act alone: READY); 43245, which has no technique
        row, is READY on it."""
        R = site_fit(device=sup(Device.WIRE_BOUGIE))
        self.assertIsNone(rq.spec('43245').row.technique)
        for code, act in (('43249', E(1)), ('43245', E(2))):
            with self.subTest(code=code):
                evaluation = decide(code, R)
                self.assertTrue(ready(evaluation))
                self.assertEqual(evaluation.supporting, (act,))

    def test_an_act_whose_site_is_not_established_stays_and_is_read(self):
        """The step's NOTES, question QB (built: the design's SITE row, and monotone): a dilation whose place is not
        established beside the esophageal one stays in E* and asks which structure was dilated - held, never READY;
        an anastomosis likewise (a surgically made place is never "outside")."""
        for second in (None, unres(Landmark.DUODENAL_BULB), sup(Landmark.ANASTOMOSIS)):
            with self.subTest(second=second.value if second is not None else None):
                evaluation = decide('43249', site_fit(second=second))
                self.assertEqual(evaluation.supporting, (E(1), E(2)))
                self.assertEqual([(held.fact, held.rank, held.kind, held.subject) for held in evaluation.held_facts],
                                 [('act_target', 11, QUESTION, E(2))])

    def test_with_no_act_within_the_class_every_act_stays_as_before(self):
        """No act established within the class: every supporting act is read, as before D240 - the another-site
        explanation of the one outside it, and the site question of one not established (asked first)."""
        doc_only_outside = Doc()
        doc_only_outside.session(1, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        doc_only_outside.exam(3)
        doc_only_outside.act(2, Kind.DILATION, places=[sup(Landmark.DUODENAL_BULB)], device=sup(Device.BALLOON))
        evaluation = decide('43249', doc_only_outside.build())
        self.assertEqual((evaluation.supporting, keys(evaluation)),
                         ((E(2),), [('act_target', 11, EXPLANATION, rule(Q.Rule.SITE))]))
        doc = Doc()
        doc.session(1, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(3)
        doc.act(1, Kind.DILATION, places=[unres(Landmark.DISTAL_ESOPHAGUS)], device=sup(Device.BALLOON))
        doc.act(2, Kind.DILATION, places=[sup(Landmark.DUODENAL_BULB)], device=sup(Device.BALLOON))
        evaluation = decide('43249', doc.build())
        self.assertEqual(evaluation.supporting, (E(1), E(2)))
        self.assertEqual([(held.fact, held.kind, held.subject) for held in evaluation.held_facts],
                         [('act_target', QUESTION, E(1)), ('act_target', EXPLANATION, E(2))])
        self.assertEqual((item('43249', doc.build()).held.kind, item('43249', doc.build()).held.subject),
                         (QUESTION, E(1)))

    def test_codes_with_no_site_row_keep_every_supporting_act(self):
        """A code with no SITE row reads every supporting act, as before (45386's balloon dilations at two places)."""
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.DILATION, places=[sup(Landmark.ANASTOMOSIS)], device=sup(Device.BALLOON))
        doc.act(3, Kind.DILATION, places=[sup(Landmark.SIGMOID_COLON)], device=sup(Device.BALLOON))
        self.assertEqual(decide('45386', doc.build()).supporting, (E(2), E(3)))


def digital_colonoscopy(what=ct.UnlistedWhat.DOUBT, card=X(1), device=sup(Device.MANUAL)) -> Doc:
    """refute-r4a-r1 P1: a colonoscopy X1 to the cecum told through its acts - the digital rectal examination E1 filed as
    its examination (kind examination, ``device`` - manual: FINAL 5.6 E13 - session X1, every fact established: D100's
    attested filing) and the cold snare E2 of L1 at the sigmoid colon - and pass 2's ONE kept unlisted ``what`` of kind
    examination in unit 9 with ``card`` (the D216 shape: "The colonoscope was advanced to the cecum." missed by pass 1,
    kept by pass 2); ``what`` None: no unlisted entry."""
    doc = colonoscopy(snare=True)
    doc.exam(1, device=device)
    if what is not None:
        doc.unlisted.append(unlisted(what, Kind.EXAMINATION, card, unit(9)))
    return doc


def act_only_egd_beside(what=ct.UnlistedWhat.DOUBT, card=X(2)) -> Doc:
    """refute-r4a-r1 P5: the colonoscopy X1 (its examination E1 done, the snare E2) beside an EGD X2 told only through
    its biopsy E4 (no examination filed: act-only), and pass 2's ONE kept unlisted ``what`` of kind examination in unit
    9 with ``card``."""
    doc = colonoscopy()
    doc.session(2, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.act(4, Kind.BIOPSY, session=X(2), places=[sup(Landmark.STOMACH)])
    doc.unlisted.append(unlisted(what, Kind.EXAMINATION, card, unit(9)))
    return doc


class R4a2Repairs(SimpleTestCase):
    """Repair r4a-2 of round w7r, evaluate.py's half of refute-r4a-r1: P1 (critical) - a digital examination (FINAL 5.6
    E13: device manual) never makes a session non-act-only, as combination.session_done's act-only arm excepts it
    (D227's one derivation), and its device weakened never does either (P-MONO); P5 - act_only is read per session."""

    def test_p1_a_digital_examination_beside_the_acts_leaves_the_session_act_only(self):
        """P1's input: the digital rectal examination E1 is no examination of the colonoscopy, so X1 is act-only and
        pass 2's unlisted examination (a doubt or an act, carded X1 or none) holds 45385 with its own item - as the
        same document without the DRE line does (the first patch: READY in all four, a false READY). With no unlisted
        entry the DRE holds nothing (the snare's session is the act's own: READY). The item (restated for D258, repair
        r4a of round w8r): the act SYNTHETIC_ACT, the doubt carded X1 DOUBT - each quoting its own unit - and the doubt
        with no card UNLISTED_SCOPE, the colonoscopy's examination asked with no words of its own: the DRE's sentence is
        never quoted as the colonoscopy's (E13: no session's examination, questions.digital_examination)."""
        self.assertTrue(ready(decide('45385', digital_colonoscopy(what=None).build())))
        for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.ACT):
            for card in (X(1), None):
                with self.subTest(what=what, card=card):
                    R = digital_colonoscopy(what, card).build()
                    self.assertTrue(EV.act_only(R, X(1)))
                    evaluation = decide('45385', R)
                    self.assertFalse(ready(evaluation))
                    self.assertIn(('performed_status', 2, QUESTION, 'unlisted'), keys(evaluation))
                    found = item('45385', R)
                    scope = what is ct.UnlistedWhat.DOUBT and card is None
                    self.assertEqual((found.held.subject, found.fill.act, found.fill.words),
                                     (X(1), Kind.EXAMINATION, () if scope else (unit(9),)))
                    self.assertEqual(found.message, Q.MessageId.SYNTHETIC_ACT if what is ct.UnlistedWhat.ACT
                                     else Q.MessageId.UNLISTED_SCOPE if scope else Q.MessageId.DOUBT)
                    if scope:
                        self.assertEqual(found.fill.statements, ((unit(9),),))

    def test_p1_a_weakened_manual_device_still_claims_it_and_another_device_does_not(self):
        """P-MONO (9.4): the DRE's device weakened - unresolved, doubted, contradicted - keeps its manual claim, so the
        session stays act-only and 45385 held (combination's reading of a SUPPORTED manual device alone would make the
        weakened DRE the session's done examination and release 45385). A device silent - the endoscopic examination's
        usual filing, D232's N1 shape -, established as another device, or manual negated claims none: that examination
        is the session's, and the unlisted examination adds nothing (READY)."""
        for name, device in (('unresolved', unres(Device.MANUAL)), ('doubted', doubted(Device.MANUAL)),
                             ('contradicted', contra(Device.MANUAL, Device.ENDOSCOPE))):
            with self.subTest(device=name):
                R = digital_colonoscopy(device=device).build()
                self.assertTrue(EV.act_only(R, X(1)))
                self.assertFalse(ready(decide('45385', R)))
        for name, device in (('silent', None), ('endoscope', sup(Device.ENDOSCOPE)), ('manual negated',
                                                                                      neg(Device.MANUAL))):
            with self.subTest(device=name):
                R = digital_colonoscopy(device=device).build()
                self.assertFalse(EV.act_only(R, X(1)))
                self.assertTrue(ready(decide('45385', R)))

    def test_p5_act_only_is_read_per_session(self):
        """P5's input: an established examination of the colonoscopy X1 never makes the EGD X2 - told only through its
        biopsy - non-act-only: pass 2's unlisted examination carded X2, or with no card, holds 43239 (row 7 on the
        biopsy E4: the synthetic doubt, its subject X2); 45385 stays READY beside X1's done examination."""
        for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.ACT):
            for card in (X(2), None):
                with self.subTest(what=what, card=card):
                    R = act_only_egd_beside(what, card).build()
                    self.assertEqual((EV.act_only(R, X(1)), EV.act_only(R, X(2))), (False, True))
                    self.assertEqual(truths('43239', R, E(4))[rq.Requirement.SUP_SESSION_DONE], U)
                    self.assertFalse(ready(decide('43239', R)))
                    self.assertEqual(item('43239', R).held.subject, X(2))
                    self.assertTrue(ready(decide('45385', R)))


A2_OTHERS = ('history', 'plan', 'plan, session empty')


def dre_colonoscopy(other, *, dre=True, what=None, card=X(1), device=sup(Device.MANUAL)) -> Doc:
    """refute-r4a-r2 A2 (DECISIONS D253): a colonoscopy X1 to the cecum told through its cold snare E2 of L1 at the
    sigmoid colon; with ``dre`` its digital rectal examination E1 filed as X1's examination (kind examination,
    ``device`` - manual: FINAL 5.6 E13 -, done today, every fact established); ``other`` an examination E3 of another
    occasion: 'history' - "Colonoscopy in 2019 was normal." filed in X1, its session supported and its date established
    earlier (a2, a2b); 'plan' - "Repeat colonoscopy in 3 years." filed in X1, its session supported and its status
    planned (a2c; F1's 'a plan filed in the session'); 'plan, session empty' - the same with its session slot empty and
    a later date (a2d, the builder's QX (i)); and pass 2's kept unlisted ``what`` of kind examination in unit 9 with
    ``card`` (D216's missed "The colonoscope was advanced to the cecum."; ``what`` None: no entry)."""
    doc = Doc()
    doc.session(1, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(Extent.CECUM)])
    if dre:
        doc.exam(1, device=device)
    doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)])
    doc.act(2, Kind.SNARE, places=[sup(Landmark.SIGMOID_COLON)], lesion=sup(L(1)), device=sup(Device.COLD_SNARE))
    if other == 'history':
        doc.exam(3, date=sup(EARLIER))
    elif other == 'plan':
        doc.exam(3, status=sup(Status.PLANNED))
    else:
        doc.event(3, kind=sup(Kind.EXAMINATION), status=sup(Status.PLANNED), date=sup(ct.DateRelation.LATER_DATE))
    if what is not None:
        doc.unlisted.append(unlisted(what, Kind.EXAMINATION, card, unit(9)))
    return doc


A2_ENTRIES = ((None, None), (ct.UnlistedWhat.DOUBT, X(1)), (ct.UnlistedWhat.DOUBT, None), (ct.UnlistedWhat.ACT, X(1)),
              (ct.UnlistedWhat.ACT, None))


class D253Row7(SimpleTestCase):
    """DECISIONS D253 (refute-r4a-r2 A2, critical; QE13 option (a)): row 7's ``done`` excepts the digital examination
    (``_digital``: FINAL 5.6 E13, a device CLAIMING manual) as ``act_only`` does, so a digital examination never counts
    as the session's done examination - beside it an examination of another occasion filed in (or possibly in) the
    session holds the code exactly as it does without the DRE line, and row 7's two readings of "the session's
    examination" agree with D227's session_done. A fact E13 says never counts releases nothing. The sentences of the
    unlisted entries (D258): tests/v2/test_questions.py D258UnlistedScope."""

    def test_a2_45385_is_held_with_the_dre_line_as_without_it(self):
        """refute-r4a-r2's a2, a2c and a2d shapes (A2_OTHERS) with no unlisted entry, an unlisted doubt or act of kind
        examination carded X1 or none: 45385 HELD in every DRE variant (the final tree of round w7r: READY, a false
        READY), with the same held facts and the same item as the same document without the DRE line; row 7 is not T
        on the snare."""
        for other in A2_OTHERS:
            for what, card in A2_ENTRIES:
                with self.subTest(other=other, what=what, card=card):
                    with_dre = dre_colonoscopy(other, what=what, card=card).build()
                    without = dre_colonoscopy(other, dre=False, what=what, card=card).build()
                    evaluation = decide('45385', with_dre)
                    self.assertFalse(ready(evaluation))
                    self.assertIsNone(evaluation.exclusion)
                    self.assertNotEqual(truths('45385', with_dre, E(2))[rq.Requirement.SUP_SESSION_DONE], T)
                    self.assertEqual(evaluation.held_facts, decide('45385', without).held_facts)
                    self.assertEqual(item('45385', with_dre), item('45385', without))

    def test_a2_row_7_agrees_with_d227s_session_done(self):
        """Row 7's two readings of the session's examination - ``done`` and ``act_only`` - read E13 as D227's
        session_done does: on a2 and a2c (the examination of another occasion filed in X1) the DRE is no done
        examination of X1 for either, so neither says the session is done, with the DRE line or without it."""
        from studio.interpretation.engine import combination
        for other in ('history', 'plan'):
            for dre in (True, False):
                with self.subTest(other=other, dre=dre):
                    R = dre_colonoscopy(other, dre=dre).build()
                    self.assertFalse(combination.session_done(R, X(1)))
                    self.assertFalse(EV.act_only(R, X(1)))
                    self.assertEqual(truths('45385', R, E(2))[rq.Requirement.SUP_SESSION_DONE], F)

    def test_a2b_through_assess_45385_is_held_with_the_same_item(self):
        """a2b: the history shape through engine/assess (the proposal provider selecting 45385 on the snare's unit):
        needs_clarification with the DRE line and without it, the one item the same (the history's own question)."""
        from tests.v2 import test_assess as TA
        for what, card in A2_ENTRIES[:4]:
            with self.subTest(what=what, card=card):
                found = [TA.by_code(TA.run(dre_colonoscopy('history', dre=dre, what=what, card=card).build(),
                                           ('45385', 2)))['45385'] for dre in (True, False)]
                self.assertEqual([entry.status.value for entry in found], ['needs_clarification'] * 2)
                self.assertEqual(found[0].item, found[1].item)
                self.assertEqual(found[0].item.held.subject, E(3))

    def test_qe13_a_device_claiming_manual_is_never_the_done_examination_and_another_device_is(self):
        """QE13 option (a), in ``done`` as in ``act_only``: the DRE's device weakened - unresolved, doubted,
        contradicted - still claims manual, so beside the plan or the history 45385 stays held (P-MONO; a supported-only
        reading would release it). A device silent (the endoscopic examination's usual filing), established as another
        device, or manual negated claims none: E1 is the session's own done examination, and the examination of another
        occasion adds nothing (READY, F1's reading)."""
        for other in ('history', 'plan'):
            for name, device in (('unresolved', unres(Device.MANUAL)), ('doubted', doubted(Device.MANUAL)),
                                 ('contradicted', contra(Device.MANUAL, Device.ENDOSCOPE))):
                with self.subTest(other=other, device=name):
                    self.assertFalse(ready(decide('45385', dre_colonoscopy(other, device=device).build())))
            for name, device in (('silent', None), ('endoscope', sup(Device.ENDOSCOPE)),
                                 ('manual negated', neg(Device.MANUAL))):
                with self.subTest(other=other, device=name):
                    R = dre_colonoscopy(other, device=device).build()
                    self.assertTrue(ready(decide('45385', R)))
                    self.assertEqual(truths('45385', R, E(2))[rq.Requirement.SUP_SESSION_DONE], T)


def dre_alone(family=SessionKind.COLONOSCOPY, reach=Extent.CECUM, *, device=sup(Device.MANUAL), dre=True,
              endoscopic=None) -> Doc:
    """refute-r4a-r1 P1 of round w8r: a session X1 of ``family`` (a colonoscopy to the cecum, or a flexible
    sigmoidoscopy to the sigmoid colon) whose only filed event is E1, kind examination, ``device`` (manual: FINAL 5.6
    E13's digital rectal examination, D100's attested filing), done today by the documenting team, every fact
    established; ``dre`` False: no event at all. ``endoscopic``: also E2, an examination of X1 with these facts (its
    device silent: the endoscopic examination's usual filing, "The colonoscope was advanced to the cecum.")."""
    doc = Doc()
    doc.session(1, family, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER), reached=[sup(reach)])
    if dre:
        doc.exam(1, device=device)
    if endoscopic is not None:
        doc.exam(2, **endoscopic)
    return doc


class DigitalSupport(SimpleTestCase):
    """refute-r4a-r1 P1 of round w8r (critical; FINAL 5.6 E13, DECISIONS D253: "A fact E13 says never counts can never
    release a code"; v1's events.supports, D100): a digital examination - its device claiming manual - is no session's
    examination, so it never supports an examination group (45378, 45330, every code of catalogue.requirements'
    (examination,)): row 1 is never T on it. The digital rectal examination filed as the colonoscopy's only examination
    no longer makes 45378 READY (nor 45330 for a flexible sigmoidoscopy): the code is held with the item the same
    document gets without the DRE line. The DRE stays a candidate, so 4.6's exclusion reads what it read (9.4)."""

    CASES = ((SessionKind.COLONOSCOPY, Extent.CECUM, '45378'), (SessionKind.FLEX_SIG, Extent.SIGMOID_COLON, '45330'))

    def test_p1_a_digital_examination_alone_never_supports_the_base_code(self):
        """P1's input: 45378 (45330) on the DRE alone - the round's first patch: READY, a false READY. Now held, never
        excluded, nothing supporting; row 1 F on E1 (its device established manual), its witness the not-documented
        question, kept among the held facts. Restated for DECISIONS D265 (repair r4a of round w9r): the DRE never takes
        the binding, so the one item IS the item without the DRE line - the code-level not-documented question (no
        subject, no attribute, the kept spans), held fact, message and Fill alike (before: the DRE's own witness, subject
        E1, attribute technique.device, with the same message and Fill)."""
        for family, reach, code in self.CASES:
            with self.subTest(code=code):
                R = dre_alone(family, reach).build()
                evaluation = decide(code, R)
                self.assertFalse(ready(evaluation))
                self.assertIsNone(evaluation.exclusion)
                self.assertEqual(evaluation.supporting, ())
                self.assertEqual(dict(evaluation.bindings), {})
                self.assertEqual(truths(code, R, E(1))[rq.Requirement.SUP_KIND], F)
                self.assertIn(('performed_status', 4, QUESTION, rule(Q.Rule.NOT_DOCUMENTED)), keys(evaluation))
                found, without = item(code, R), item(code, dre_alone(family, reach, dre=False).build())
                self.assertEqual((found.message, without.message), (Q.MessageId.NOT_DOCUMENTED,) * 2)
                self.assertEqual(found, without)
                self.assertEqual((found.held.subject, found.held.attribute), (None, None))

    def test_p1_a_device_claiming_manual_never_supports_and_another_device_does(self):
        """QE13 option (a), the one predicate (questions.digital_examination): a device that claims manual without
        establishing it - unresolved, doubted, contradicted - never supports either (row 1 U: the device's own
        question; P-MONO: a weakened manual device keeps its claim); a device silent, established as another device,
        or manual negated claims none: E1 is the session's examination and supports the code (READY)."""
        for family, reach, code in self.CASES:
            for name, device in (('unresolved', unres(Device.MANUAL)), ('doubted', doubted(Device.MANUAL)),
                                 ('contradicted', contra(Device.MANUAL, Device.ENDOSCOPE))):
                with self.subTest(code=code, device=name):
                    R = dre_alone(family, reach, device=device).build()
                    self.assertFalse(ready(decide(code, R)))
                    self.assertEqual(truths(code, R, E(1))[rq.Requirement.SUP_KIND], U)
            for name, device in (('silent', None), ('endoscope', sup(Device.ENDOSCOPE)),
                                 ('manual negated', neg(Device.MANUAL))):
                with self.subTest(code=code, device=name):
                    evaluation = decide(code, dre_alone(family, reach, device=device).build())
                    self.assertTrue(ready(evaluation))
                    self.assertEqual(evaluation.supporting, (E(1),))

    def test_p1_beside_an_endoscopic_examination_only_that_one_supports(self):
        """The common report: the DRE E1 and the colonoscope's examination E2 both filed as X1's examination - 45378
        READY on E2 alone (the DRE never in E*); E2 established not done (status planned) leaves 45378 held, never
        READY on the DRE."""
        R = dre_alone(endoscopic={}).build()
        evaluation = decide('45378', R)
        self.assertTrue(ready(evaluation))
        self.assertEqual(evaluation.supporting, (E(2),))
        evaluation = decide('45378', dre_alone(endoscopic=dict(status=sup(Status.PLANNED))).build())
        self.assertFalse(ready(evaluation))
        self.assertEqual(evaluation.supporting, ())

    def test_p1_a_cited_denial_beside_the_dre_is_read_as_before(self):
        """The DRE stays a candidate (row 1 only), so 4.6 reads what it read: a positive DRE holds the code beside a
        denial of the colonoscopy that 45378 cites (never excluded beside a possibly performed examination), and the
        DRE established of another date leaves the exclusion to the cited denial, as without the DRE line."""
        for dre, expected in (({}, 'held'), (dict(date=sup(EARLIER)), 'excluded')):
            with self.subTest(dre=dre):
                doc = dre_alone(device=sup(Device.MANUAL), dre=False)
                doc.exam(1, device=sup(Device.MANUAL), **dre)
                denial_event(doc, number=3, kind=Kind.EXAMINATION)
                evaluation = decide('45378', doc.build(), (Span(300, 325),))
                status = 'excluded' if evaluation.exclusion is not None else 'ready' if ready(evaluation) else 'held'
                self.assertEqual(status, expected)

    def test_p1_through_assess_the_renderer_words_it_as_without_the_dre_line(self):
        """Through engine/assess (45378 selected on the DRE's unit) and the renderer's own call, jobs.word_item: held
        needs_clarification, the question and the reason those of the same document without the DRE line."""
        from studio import jobs
        from tests.v2 import test_assess as TA
        for family, reach, code in self.CASES:
            with self.subTest(code=code):
                worded = []
                for dre in (True, False):
                    R = dre_alone(family, reach, dre=dre).build()
                    assessment = TA.run(R, (code, 1))
                    found = TA.by_code(assessment)[code]
                    self.assertEqual(found.status.value, 'needs_clarification')
                    spec = jobs.word_item(found.item, found.key, assessment.combination, R, TA.TEXT)
                    worded.append((spec.question, spec.reason))
                self.assertEqual(worded[0], worded[1])


def status_of(evaluation: Evaluation) -> str:
    """A per-code decision's status: excluded, ready or held."""
    if evaluation.exclusion is not None:
        return 'excluded'
    return 'ready' if ready(evaluation) else 'held'


def assessed(R: FactSet, *codes) -> dict:
    """engine/assess over ``R`` (tests/v2/test_assess.run, each code selected on its unit): {code: (status, item)}."""
    from tests.v2 import test_assess as TA
    return {found.code: (found.status.value, found.item) for found in TA.run(R, *codes).codes}


def dre_codes(snare: bool, kept: int) -> tuple:
    """The grid's codes: 45378 kept on ``kept``'s unit, and 45385 on the snare E3's when there is one."""
    return (('45378', kept),) + ((('45385', 3),) if snare else ())


class D265DigitalNeverWords(SimpleTestCase):
    """DECISIONS D265 (repair r4a of round w9r; refute-r4a-r2 F1, F3, Q4+; r4a-2 Q4 QDRE; TRIAGE G1-02, G1-04, G2-19): a
    digital examination (FINAL 5.6 E13: its device claiming manual) never words, binds or changes an item - every
    code's status and item, and the binding that chooses it, equal the same FactSet's without the digital examination's
    events and the relations that pair it, over refute-r4a-r2's grids (its probes/: F1's 104 rows, F3's 20, Q4's and
    Q4+'s shapes, D253's A2 shapes). The DRE stays a candidate (repair r4a-2's DV1), so D253 stays: it never releases
    a code, and a positive one is never excluded beside; a digital examination statement concerns no group."""

    def test_the_whole_grid_through_assess_gives_every_code_the_item_without_the_dre(self):
        """Every row of refute-r4a-r2's grid with a claiming DRE (8,064 rows, every code), through engine/assess: each
        code's status and ONE item are the same FactSet's without E1. Where F1 (the claimed-manual DRE's device question
        as "Was the colonoscopy (<the DRE's sentence>) done ...", 104 rows) and F3 (the DRE's rank-4 witness taking the
        binding from the colonoscope's examination E2, 20 rows) were found - E2 with its performer open, planned or of an
        earlier date (2,304 rows of 45378, 1,152 of 45385) - exactly equal; elsewhere exactly equal too, assess's R6
        extent hold included: its spans quote the session's examinations (step 5a's _session_spans), never the digital
        examination (engine/assess._examinations excepts it: this step's request R1, applied by the integration of
        round w9r, which restated this test from "equal but for the DRE's unit" to exactly equal on every row)."""
        rows = strict = 0
        cache: dict = {}
        for dre, where, other, snare, statement, reach, kept in itertools.product(
                DRE_CLAIMING, DRE_SESSIONS, DRE_OTHERS, (False, True), DRE_STATEMENTS, DRE_REACHES, DRE_KEPT):
            codes = dre_codes(snare, kept)
            found = assessed(dre_grid(dre, where, other, snare, statement, reach), *codes)
            key = (other, snare, statement, reach, kept)
            if key not in cache:
                cache[key] = assessed(dre_grid('none', 'X1', other, snare, statement, reach), *codes)
            without = cache[key]
            for code in found:
                rows += 1
                ours, theirs = found[code], without[code]
                if other in ('performer_unres', 'planned', 'earlier'):  # F1's and F3's rows
                    strict += 1
                if ours != theirs:  # every row exactly equal
                    with self.subTest(shape=(dre, where, other, snare, statement, reach, kept), code=code):
                        self.assertEqual(ours, theirs)
        self.assertEqual((rows, strict), (8064, 2304 + 1152))

    def test_the_whole_grid_at_the_per_code_rule_gives_the_item_and_binding_without_the_dre(self):
        """Every row of refute-r4a-r2's grid with a claiming DRE (8,064 rows, every code): engine/evaluate's decision -
        its status, its supporting acts, its bindings - and its ONE item (questions.item over its held facts) equal the
        same FactSet's without E1, held fact, message and Fill alike."""
        rows = 0
        cache: dict = {}

        def decided(R, code, kept):
            evaluation = decide(code, R, kept)
            return (status_of(evaluation), evaluation.supporting, dict(evaluation.bindings),
                    EV.item(code, tuple(kept), R, evaluation))

        for dre, where, other, snare, statement, reach, kept in itertools.product(
                DRE_CLAIMING, DRE_SESSIONS, DRE_OTHERS, (False, True), DRE_STATEMENTS, DRE_REACHES, DRE_KEPT):
            R = dre_grid(dre, where, other, snare, statement, reach)
            key = (other, snare, statement, reach)
            if key not in cache:
                cache[key] = dre_grid('none', 'X1', other, snare, statement, reach)
            for code, at in dre_codes(snare, kept):
                rows += 1
                ours, theirs = decided(R, code, (unit(at),)), decided(cache[key], code, (unit(at),))
                if ours != theirs:
                    with self.subTest(shape=(dre, where, other, snare, statement, reach, kept), code=code):
                        self.assertEqual(ours, theirs)
        self.assertEqual(rows, 8064)

    def test_f3_the_colonoscopes_examination_takes_the_binding(self):
        """F3's shape: the DRE E1 (device manual, done) and E2, the colonoscope's examination, its performer (or date
        relation, or entry, or status) open; 45378 kept on E2's unit, the DRE's or unit 7: the binding is E2 and the
        item E2's own question - never "records no colonoscopy documented as done" on E1."""
        for name, over in (('performer', dict(performer=unres(TEAM))), ('date', dict(date=unres(ON))),
                           ('entry', dict(entry=unres(DC))), ('status', dict(status=unres(Status.PERFORMED)))):
            for kept in (2, 1, 7):
                with self.subTest(open=name, kept=kept):
                    R = dre_alone(endoscopic=over).build()
                    evaluation = decide('45378', R, (unit(kept),))
                    self.assertEqual(dict(evaluation.bindings), {(Kind.EXAMINATION,): E(2)})
                    found = EV.item('45378', (unit(kept),), R, evaluation)
                    self.assertEqual(found.held.subject, E(2))
                    self.assertNotEqual(found.message, Q.MessageId.NOT_DOCUMENTED)
                    self.assertEqual(found, item('45378', without_events(R, E(1)), (unit(kept),)))

    def test_q4_and_q4plus_an_examination_statement_never_pairs_with_the_dre(self):
        """r4a-2 Q4: the DRE E1 as the colonoscopy's only examination beside "No colonoscopy was performed today." (E3:
        examination, negated, all of its kind, today, X1) or the same statement doubted - before, the CONFLICT "The
        record states the colonoscopy (manual) both as performed and as not performed". refute-r4a-r2 Q4+: the DRE
        beside E2, whose status is unresolved - before, STATEMENT_SCOPE "Does <E2> apply to the colonoscopy (manual)
        (<the DRE's sentence>)?". engine/pairing pairs neither statement with the DRE (the examination is no kind of a
        digital act), and through engine/assess every code's status and item are the document's without E1, 45378
        kept on the DRE's unit, the statement's or unit 7."""
        from studio.interpretation.engine import pairing
        shapes = []
        for name, status in (('denial', neg(Status.PERFORMED)), ('doubted', doubted(Status.PERFORMED))):
            for dre in (True, False):
                doc = dre_alone(dre=dre)
                denial_event(doc, number=3, kind=Kind.EXAMINATION, status=status)
                shapes.append((f'Q4 {name}', dre, doc.build(), E(3)))
        for dre in (True, False):
            shapes.append(('Q4+', dre, dre_alone(dre=dre, endoscopic=dict(status=unres(Status.PERFORMED))).build(),
                           E(2)))
        found: dict = {}
        for name, dre, R, statement in shapes:
            if dre:
                self.assertFalse(pairing.paired(R, statement, E(1)))
                self.assertEqual(pairing.pairs_of(R, E(1)), ())
            for kept in (1, 3, 7):
                found[(name, dre, kept)] = assessed(R, ('45378', kept))
        for name, dre, R, statement in shapes:
            for kept in (1, 3, 7):
                with self.subTest(shape=name, kept=kept):
                    self.assertEqual(found[(name, True, kept)], found[(name, False, kept)])
                    self.assertNotEqual(found[(name, True, kept)]['45378'][1].message, Q.MessageId.CONFLICT)

    def test_d253_a2_shapes_every_code_has_the_item_without_the_dre(self):
        """D253's A2 shapes (``dre_colonoscopy``: the DRE filed as the colonoscopy's examination beside "Colonoscopy in
        2019 was normal." or a planned repeat filed in the session, with no unlisted entry or pass 2's doubt or act of
        kind examination, carded X1 or none) through engine/assess: 45385 on the snare and 45378 on the DRE's, the
        snare's or the other examination's unit - every status and item the same document's without the DRE line (D253
        tested 45385 alone)."""
        for other in A2_OTHERS:
            for what, card in A2_ENTRIES:
                for kept in (1, 2, 3):
                    with self.subTest(other=other, what=what, card=card, kept=kept):
                        codes = (('45385', 2), ('45378', kept))
                        self.assertEqual(assessed(dre_colonoscopy(other, what=what, card=card).build(), *codes),
                                         assessed(dre_colonoscopy(other, dre=False, what=what, card=card).build(),
                                                  *codes))

    def test_a_digital_examination_statement_never_excludes_nor_asks_its_scope(self):
        """A digital examination is no session's examination as a statement either (``_concerns``, ``possibly_here``):
        "No digital rectal examination was performed." (E1: examination, device manual, status negated, all of its
        kind, today, X1) cited by 45378's kept evidence beside the colonoscopy's snare - before, 45378 EXCLUDED by it;
        a digital rectal examination of an earlier date cited - before, EXCLUDED by its date; the denial with its
        session not established - before, its statement_scope question. Each is the document's without the DRE line:
        held, the code-level not-documented question."""
        cases = (('denial', dict(status=neg(Status.PERFORMED), breadth=sup(Breadth.ALL_OF_KIND))),
                 ('earlier', dict(date=sup(EARLIER))),
                 ('denial, session open', dict(status=neg(Status.PERFORMED), breadth=sup(Breadth.ALL_OF_KIND),
                                              session=unres(X(1)))))
        for name, over in cases:
            with self.subTest(case=name):
                doc = colonoscopy(snare=True)
                doc.act(1, Kind.EXAMINATION, device=sup(Device.MANUAL), kind_words=Span(103, 111),
                        status_words=Span(100, 125), **over)
                R = doc.build()
                kept = (Span(100, 125),)
                evaluation = decide('45378', R, kept)
                self.assertIsNone(evaluation.exclusion)
                self.assertEqual(status_of(evaluation), 'held')
                found = EV.item('45378', kept, R, evaluation)
                self.assertEqual(found, item('45378', without_events(R, E(1)), kept))
                self.assertEqual(found.message, Q.MessageId.NOT_DOCUMENTED)

    def test_a_positive_dre_beside_a_statement_4_6_would_exclude_by_asks_its_scope(self):
        """The fail-closed side (repair r4a-2's DV1, P-MONO; the step's NOTES, question Q-R4A-EXCL): the DRE alone is a
        positive candidate - its date on the date of service negated, so it doubts no exclusion through 4.6 condition
        5 - beside "No colonoscopy was performed today." cited exactly: the same document without the DRE line
        EXCLUDES 45378, and with it 45378 is held, never excluded, its item the statement's scope question (the
        citation beside a doubt), never the DRE's. With the DRE possibly done today, condition 5 gives the same item."""
        for name, over in (('date negated', dict(date=neg(ON))), ('done today', {})):
            with self.subTest(dre=name):
                doc = dre_alone(dre=False)
                doc.exam(1, device=sup(Device.MANUAL), **over)
                denial_event(doc, number=3, kind=Kind.EXAMINATION)
                R = doc.build()
                kept = (Span(300, 325),)
                self.assertEqual(status_of(decide('45378', without_events(R, E(1)), kept)), 'excluded')
                evaluation = decide('45378', R, kept)
                self.assertEqual(status_of(evaluation), 'held')
                found = EV.item('45378', kept, R, evaluation)
                self.assertEqual((found.message, found.held.subject, found.held.cause),
                                 (Q.MessageId.STATEMENT_SCOPE, E(3), rule(Q.Rule.STATEMENT_SCOPE)))


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

    def test_p_mono_an_unlisted_act_told_as_a_doubt_never_releases(self):
        """refute-r4a-r1 F1 (P6; 4.2 [R:HO-1]): every fixture's kept unlisted ACT told as a DOUBT instead - the weaker
        statement - never turns HELD into READY or EXCLUDED: every absence condition reads the doubt as it reads the
        act."""
        count = 0
        for code, R, kept in all_fixtures():
            before = self.status(decide(code, R, kept))
            for index, entry in enumerate(R.unlisted):
                if entry.what is not ct.UnlistedWhat.ACT:
                    continue
                doubt = dataclasses.replace(entry, what=ct.UnlistedWhat.DOUBT)
                weaker = dataclasses.replace(R, unlisted=(*R.unlisted[:index], doubt, *R.unlisted[index + 1:]))
                after = self.status(decide(code, weaker, kept))
                count += 1
                if before == 'held':
                    with self.subTest(code=code, entry=index):
                        self.assertEqual(after, 'held')
        self.assertGreaterEqual(count, 10)

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
    out += r4a_fixtures()
    out += r4a2_fixtures()
    out += w7r_fixtures()
    out += w8r_fixtures()
    out += w8r_refuted_fixtures()
    out += w9r_fixtures()
    out += f3w_fixtures()
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


def r4a_fixtures() -> list:
    """(code, FactSet, kept) for repair r4a's shapes (refute-4a-r2 p10-p17, D216, D225, D226): OneItem builds each held
    code's one item (D182) and P-MONO weakens each - READY shapes included, whose weakenings must stay out of
    EXCLUDED."""
    out = []
    for removal in (Kind.STENT_REMOVAL, None, dict(status=doubted(Status.PERFORMED)), {}):  # p10, P6
        if removal is None:
            doc = stent_placement(None)
            doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, None, X(1), unit(5)))
        else:
            doc = stent_placement(removal)
        out += [('43274', doc.build(), (unit(2),)), ('43276', doc.build(), (unit(2),))]
    doc = stent_placement(dict(duct=sup(ct.Duct.BILIARY)), duct=None)  # P6: the placement's duct the unknown one
    out.append(('43274', doc.build(), ()))
    doc = egd()  # p11, P2
    doc.act(2, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS)], device=sup(Device.BALLOON), date=unres(ON),
            performer=unres(TEAM))
    doc.act(3, Kind.DILATION, places=[sup(Landmark.DUODENUM)], device=sup(Device.BALLOON), date=unres(ON))
    out.append(('43249', doc.build(), ()))
    for tie in (sup(X(1)), unres(X(1))):  # p12b, P3
        out.append(('99213', Row7Repairs.office(tie), ()))
    for kind, stations in (('43259', [unres(Station.JEJUNUM)]), ('43242', [doubted(Station.JEJUNUM)])):  # p14, P4
        out.append((kind, UpperStations.eus(stations, Kind.FNA if kind == '43242' else None), ()))
    for approach, stoma in ((None, True), (unres(ct.Approach.THROUGH_STOMA), True), (sup(ct.Approach.THROUGH_STOMA),
                                                                                    False)):  # p13, P5
        doc = Doc()
        doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=[sup(Extent.SIGMOID_COLON)],
                    approach=approach)
        if stoma:
            doc.entry(1, type=sup(ct.AnatomyType.STOMA))
        doc.exam(1)
        out.append(('44406', doc.build(), ()))
    doc = colonoscopy(date=contra(ON, EARLIER, spans=(unit(2),)))  # p15, P7
    out.append(('45385', doc.build(), ()))
    doc = colonoscopy(status=contra(Status.PERFORMED, Status.PLANNED, spans=(unit(2),)))
    out.append(('45385', doc.build(), ()))
    doc = dilation(sup(Landmark.DISTAL_ESOPHAGUS), device=contra(Device.BALLOON, Device.BOUGIE, spans=(unit(2),)))
    out.append(('43249', doc.build(), ()))
    out.append(('43242', eus_fna([sup(Station.ESOPHAGUS), contra(Station.STOMACH, Station.DUODENUM,
                                                                 spans=(unit(1),))]), ()))
    doc = act_only_colonoscopy()  # p16, P8
    doc.event(5, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), date=sup(ON), performer=sup(TEAM),
              entry=sup(DC))
    doc.event(4, kind=sup(Kind.EXAMINATION), status=sup(Status.PLANNED), date=sup(ct.DateRelation.LATER_DATE))
    out.append(('45385', doc.build(), ()))
    doc = act_only_colonoscopy()  # P9: a tie naming a missing session
    doc.event(5, kind=sup(Kind.EXAMINATION), status=doubted(Status.PERFORMED), session=unres(X(9)), date=sup(ON),
              performer=sup(TEAM), entry=sup(DC))
    out.append(('45385', doc.build(), ()))
    for places in ([Landmark.PANCREAS, Landmark.BILE_DUCT], [Landmark.BILE_DUCT, Landmark.PANCREAS]):  # p17, P10
        doc = Doc()
        doc.session(1, SessionKind.EUS, tract=sup(ct.Tract.UPPER), reached=[sup(Extent.DUODENUM)])
        doc.exam(1)
        doc.act(2, Kind.DRAINAGE, structure=sup(ct.Structure.PANCREATIC_FLUID_COLLECTION),
                places=[sup(place) for place in places], route=sup(ct.Route.EUS_TRANSMURAL))
        out.append(('43240', doc.build(), ()))
    for entry in (unlisted(ct.UnlistedWhat.ACT, Kind.EXAMINATION, X(1), unit(5)),
                  unlisted(ct.UnlistedWhat.ACT, None, None, unit(5))):  # D216, row 7
        doc = act_only_colonoscopy()
        doc.unlisted.append(entry)
        out.append(('45385', doc.build(), ()))
        doc = colonoscopy()
        doc.unlisted.append(entry)
        out.append(('45385', doc.build(), ()))
    doc = egd()  # D216, condition 5: an unlisted clip beside a cited bleeding-control denial
    denial_event(doc, number=6, kind=Kind.BLEEDING_CONTROL)
    doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.CLIP, X(1), unit(5)))
    out.append(('43255', doc.build(), (Span(600, 625),)))
    doc = Doc()  # D216, condition 5: two synthetic parts beside a cited exchange denial
    doc.session(1, SessionKind.ERCP)
    doc.exam(1)
    denial_event(doc, number=6, kind=Kind.STENT_EXCHANGE)
    doc.unlisted += [unlisted(ct.UnlistedWhat.ACT, Kind.STENT_REMOVAL, X(1), unit(4)),
                     unlisted(ct.UnlistedWhat.ACT, Kind.STENT, X(1), unit(5))]
    out.append(('43276', doc.build(), (Span(600, 625),)))
    out.append(('43259', eus_fna([sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)],
                                 tract=sup(ct.Tract.PANCREATOBILIARY)), ()))  # D226
    return out


def r4a2_fixtures() -> list:
    """(code, FactSet, kept) for repair r4a round 2's shapes (refute-r4a-r1 p20, p22, p25, p26, p29 and their variants):
    OneItem builds each held code's one item (D182) and P-MONO weakens each - READY shapes included."""
    out = []
    for session in (X(1), None):  # p20, F1: the removal kept as an unlisted doubt
        doc = stent_placement(None)
        doc.unlisted.append(stent_doubt(session=session))
        out += [('43274', doc.build(), (unit(2),)), ('43276', doc.build(), (unit(2),))]
    doc = stent_placement(None)  # F1, p31: the placement and the doubt beside a cited exchange denial
    doc.unlisted.append(stent_doubt())
    denial_event(doc, number=6, kind=Kind.STENT_EXCHANGE)
    out.append(('43276', doc.build(), (Span(600, 625),)))
    doc = Doc()  # F1: 43275 beside an unlisted doubt of the placement
    doc.session(1, SessionKind.ERCP)
    doc.exam(1)
    doc.act(2, Kind.STENT_REMOVAL, duct=sup(ct.Duct.BILIARY))
    doc.unlisted.append(stent_doubt(Kind.STENT))
    out.append(('43275', doc.build(), ()))
    doc = Doc()  # F1: two unlisted doubts beside a cited exchange denial
    doc.session(1, SessionKind.ERCP)
    doc.exam(1)
    denial_event(doc, number=6, kind=Kind.STENT_EXCHANGE)
    doc.unlisted += [stent_doubt(number=4), stent_doubt(Kind.STENT)]
    out.append(('43276', doc.build(), (Span(600, 625),)))
    for kind in (Kind.EXAMINATION, None):  # F1, row 7: an unlisted doubt of the examination (or of no kind)
        doc = act_only_colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, kind, X(1), unit(5)))
        out.append(('45385', doc.build(), ()))
    doc = colonoscopy()  # F2 / Q2, ruled by D232: beside the session's done examination (READY)
    doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.EXAMINATION, X(1), unit(7)))
    out.append(('45385', doc.build(), ()))
    hemostasis = ct.Purpose.HEMOSTASIS  # F4: p22 (1), the purpose and the cause
    out += [('43255', bleeding(purpose=contra(hemostasis, ct.Purpose.PROPHYLAXIS, spans=(unit(2),)),
                               cause=sup(ct.Cause.PRE_EXISTING_LESION)), ()),
            ('43255', bleeding(purpose=sup(hemostasis), cause=contra(ct.Cause.PRE_EXISTING_LESION, ct.Cause.SPONTANEOUS,
                                                                     spans=(unit(2),))), ())]
    every = [sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)]
    reach = (contra(Extent.SECOND_PORTION_DUODENUM, Extent.STOMACH, spans=(unit(1),)),)
    out += [('43259', eus_fna(every, reached=reach), ()), ('43237', eus_fna(every[:2], reached=reach), ()),
            ('43242', eus_fna(every, reached=(unres(Extent.SECOND_PORTION_DUODENUM),)), ())]  # F4: p22 (2), p26
    doc = dilation(sup(Landmark.DISTAL_ESOPHAGUS), lesion=contra(L(1), L(2), spans=(unit(2),)))  # F4: p26
    doc.lesion(1, lesion_places=[sup(Landmark.DISTAL_ESOPHAGUS)])
    doc.lesion(2, lesion_places=[sup(Landmark.DISTAL_ESOPHAGUS)])
    out.append(('43249', doc.build(), ()))
    doc = dilation(sup(Landmark.DISTAL_ESOPHAGUS), lesion=sup(L(1)))
    doc.lesion(1, lesion_places=[contra(Landmark.DISTAL_ESOPHAGUS, Landmark.STOMACH, spans=(unit(2),))])
    out.append(('43249', doc.build(), ()))
    out += [('44406', lower_eus(sup(Extent.SIGMOID_COLON), unres(Extent.DESCENDING_COLON)), ()),  # F7: p29
            ('44406', lower_eus(sup(Extent.DUODENUM), approach=sup(ct.Approach.ORAL)), ()),
            ('44406', lower_eus(approach=sup(ct.Approach.THROUGH_STOMA), stoma=False), ())]
    out.append(('43274', stent_placement(dict(status=doubted(Status.PERFORMED), duct=sup(ct.Duct.BILIARY))).build(),
                (unit(2),)))  # D225 beside F6: the doubted removal in the same duct
    return out


def w7r_fixtures() -> list:
    """(code, FactSet, kept) for repair r4a of round w7r (D232, D240): OneItem builds each held code's one item (D182) and
    P-MONO weakens each - the READY shapes included, whose weakenings must stay out of READY-from-HELD and EXCLUDED."""
    out = []
    for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.ACT):  # D232: p41 beside the colonoscopy's done examination
        for card in (X(1), None):
            R = p41(what, card).build()
            out += [('45385', R, ()), ('45378', R, ())]
    R = p41(card=None, egd_beside=True).build()  # p41's EGD variant: 43239 READY, 43235 held by rule 4's pair
    out += [('43239', R, ()), ('43235', R, ()), ('45385', R, ())]
    for card in (X(1), None):  # D232: the act-only session still reads the synthetic examination (doubt)
        doc = act_only_colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.EXAMINATION, card, unit(9)))
        out.append(('45385', doc.build(), ()))
    doc = colonoscopy()  # D232: an examination established but not done beside a synthetic one
    doc.exam(1, date=unres(ON))
    doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.EXAMINATION, X(1), unit(9)))
    out.append(('45385', doc.build(), ()))
    R = site_fit()  # D240: the site-fit input (before D240 its weakenings released 43249: the step's NOTES, QM)
    out += [('43249', R, ()), ('43245', R, ())]
    out.append(('43249', site_fit(device=sup(Device.WIRE_BOUGIE)), ()))
    for what, card in ((ct.UnlistedWhat.DOUBT, X(1)), (ct.UnlistedWhat.ACT, None)):  # refute-r4a-r1 P1: E13's DRE
        out.append(('45385', digital_colonoscopy(what, card).build(), ()))
    out.append(('45385', digital_colonoscopy(device=unres(Device.MANUAL)).build(), ()))
    for card in (X(2), None):  # refute-r4a-r1 P5: act_only read per session
        R = act_only_egd_beside(card=card).build()
        out += [('43239', R, ()), ('45385', R, ())]
    # Not here: D240's shapes in which a supporting act holds the code only through its code-specific rows beside an
    # act that meets every row (site_fit(second=None), a second esophageal dilation of an unstated device) - 9.4's
    # weakening of that act's SUPPORT rows moves it out of E* and releases the code, a class of 4.4's outcome function
    # that predates this repair (measured on the base tree: the step's NOTES, question QM); D240SiteFit pins them.
    return out


def ileal_attempt(card=None) -> Doc:
    """r4c-2's question Q1 (DECISIONS D258): an ileal enteroscopy X1 (oral, reaching the ileum) whose examination E1 is
    established begun and not completed, beside an EGD X2 whose examination E3 is done; pass 2's ONE kept unlisted
    DOUBT of kind examination in unit 9 with ``card`` (none, or a session the FactSet does not hold)."""
    doc = Doc()
    doc.session(1, SessionKind.ENTEROSCOPY, approach=sup(ct.Approach.ORAL, spans=(unit(4),)),
                reached=[sup(Extent.ILEUM, spans=(unit(6),))])
    doc.exam(1, status=sup(Status.ATTEMPTED_NOT_COMPLETED))
    doc.session(2, SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(3, session=X(2))
    doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.EXAMINATION, card, unit(9)))
    return doc


def w8r_fixtures() -> list:
    """(code, FactSet, kept) for repair r4a of round w8r (D253, D258): OneItem builds each held code's one item (D182)
    and P-MONO weakens each - the READY shapes included, whose weakenings must stay out of READY-from-HELD and
    EXCLUDED."""
    out = []
    for other in A2_OTHERS:  # D253: refute-r4a-r2 A2's shapes, with and without the DRE line
        for what, card in A2_ENTRIES[:3]:
            for dre in (True, False):
                out.append(('45385', dre_colonoscopy(other, dre=dre, what=what, card=card).build(), ()))
    out.append(('45385', dre_colonoscopy('plan', device=unres(Device.MANUAL)).build(), ()))  # QE13 (a)
    out.append(('45385', dre_colonoscopy('history', device=None).build(), ()))  # READY: E1 the session's own
    R = p41(ct.UnlistedWhat.DENIAL, None, egd_beside=True).build()  # D258, QD: the no-card denial
    out += [('45378', R, ()), ('43235', R, ()), ('45385', R, ())]
    for card in (None, X(9)):  # D258: the act-only session's synthetic examination doubt naming no held session
        doc = act_only_colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.DOUBT, Kind.EXAMINATION, card, unit(9)))
        out.append(('45385', doc.build(), ()))
        out.append(('45385', digital_colonoscopy(ct.UnlistedWhat.DOUBT, card).build(), ()))
    for card in (None, X(9), X(1)):  # D258, r4c Q1: the ileal input
        R = ileal_attempt(card).build()
        out += [('44376', R, ()), ('43235', R, ())]
    return out


def w8r_refuted_fixtures() -> list:
    """(code, FactSet, kept) for the shapes of repair r4a of round w8r's refutation (refute-r4a-r1): OneItem builds each
    held code's one item (D182) and P-MONO weakens each - the READY shapes included (a weakened manual-negated device
    claims manual and holds: never READY-from-HELD, never EXCLUDED)."""
    out = []
    for family, reach, code in DigitalSupport.CASES:  # P1: the DRE alone, its device established, claimed or not
        for device in (sup(Device.MANUAL), unres(Device.MANUAL), neg(Device.MANUAL), None):
            out.append((code, dre_alone(family, reach, device=device).build(), ()))
    out.append(('45378', dre_alone(endoscopic={}).build(), ()))  # READY on the colonoscope's examination alone
    for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.DENIAL):  # P3: the DRE held against a statement
        for card in (None, X(1)):
            R = digital_colonoscopy(what, card).build()
            out += [('45378', R, ()), ('45378', R, (unit(1),))]
    for kind in (None, contra(Kind.STENT_REMOVAL, Kind.BIOPSY, spans=(unit(5),))):  # P4: a counterpart no kind names
        doc = stent_placement(None)
        doc.act(5, kind if kind is not None else facts_module.SILENT)
        out.append(('43274', doc.build(), (unit(2),)))
    return out


def w9r_fixtures() -> list:
    """(code, FactSet, kept) for repair r4a of round w9r (DECISIONS D265, D266, D267): OneItem builds each held code's one
    item (D182) and P-MONO weakens each - the DRE's shapes (a claimed device beside the colonoscope's examination with
    its performer open, the DRE alone beside a statement, Q4's and Q4+'s, a digital examination statement cited, a
    positive DRE beside a cited denial), D266's examinations of another occasion beside an unlisted statement, and
    D267's kinds not supported."""
    out = []
    for device in (sup(Device.MANUAL), unres(Device.MANUAL), doubted(Device.MANUAL)):  # F1, F3
        R = dre_alone(device=device, endoscopic=dict(performer=unres(TEAM))).build()
        out += [('45378', R, (unit(1),)), ('45378', R, (unit(2),))]
    for statement in ('doubt_nocard', 'denial_X1', 'filed_denial'):  # F1's DRE alone beside a statement; F2's E2
        for other in ('none', 'planned', 'earlier'):
            R = dre_grid('unres', 'X1', other, True, statement, 'cecum')
            out += [('45378', R, (unit(1),)), ('45385', R, (unit(3),))]
    for status in (neg(Status.PERFORMED), doubted(Status.PERFORMED)):  # Q4
        doc = dre_alone()
        denial_event(doc, number=3, kind=Kind.EXAMINATION, status=status)
        out.append(('45378', doc.build(), (unit(1),)))
    out.append(('45378', dre_alone(endoscopic=dict(status=unres(Status.PERFORMED))).build(), (unit(1),)))  # Q4+
    doc = colonoscopy(snare=True)  # a digital examination's denial cited
    doc.act(1, Kind.EXAMINATION, device=sup(Device.MANUAL), status=neg(Status.PERFORMED),
            breadth=sup(Breadth.ALL_OF_KIND), kind_words=Span(103, 111), status_words=Span(100, 125))
    out.append(('45378', doc.build(), (Span(100, 125),)))
    doc = dre_alone(dre=False)  # a positive DRE, its date negated, beside a cited denial (Q-R4A-EXCL)
    doc.exam(1, device=sup(Device.MANUAL), date=neg(ON))
    denial_event(doc, number=3, kind=Kind.EXAMINATION)
    out.append(('45378', doc.build(), (Span(300, 325),)))
    for over in (dict(date=neg(ON)), dict(performer=neg(TEAM))):  # D266: an examination not possibly done today
        for card in (None, X(1)):
            doc = colonoscopy(snare=False)
            doc.exam(1, **over)
            doc.unlisted.append(unlisted(ct.UnlistedWhat.DENIAL, Kind.EXAMINATION, card, unit(9)))
            out.append(('45378', doc.build(), ()))
    for kind in (neg(Kind.SNARE), doubted(Kind.SNARE, Kind.BIOPSY), unres(Kind.SNARE)):  # D267: refute-5c-r1 P2
        out.append(('45385', colonoscopy(kind=kind).build(), ()))
    out.append(('45385', colonoscopy(kind=facts_module.SILENT,  # QK: conflict:other
                                     status=contra(Status.PERFORMED, Status.PLANNED)).build(), ()))
    return out


# --- step f3w of AMENDMENT-2's build round (DECISIONS D280.1, D280.3, D287; build list B1, B9) -------------------------


def qd2_shape(over=None, *, beside=True) -> Doc:
    """refute-safety's qd2_steer and refute-r4a-r1's v9_dre_own_rows shapes (ported, synthetic): a colonoscopy X1 to the
    cecum, E1 filed as its examination with ``over`` (its device among them; None: no E1, the document without the DRE
    line), the cold snare E2 of L1 at the sigmoid colon, and (``beside``) the colonoscope's examination E3 done today."""
    doc = Doc()
    doc.session(1, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(Extent.CECUM)])
    if over is not None:
        over = dict(over)
        doc.act(1, over.pop('kind', Kind.EXAMINATION), **over)
    doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)])
    doc.act(2, Kind.SNARE, places=[sup(Landmark.SIGMOID_COLON)], lesion=sup(L(1)), device=sup(Device.COLD_SNARE))
    if beside:
        doc.exam(3)
    return doc


def overfilled(*written) -> Fact:
    """An overfilled slot's merged view as engine/facts builds it (AMENDMENT-2 4.3.3): ``written`` its written facts as
    (state, value)."""
    values = tuple(dict.fromkeys(value for _state, value in written))
    stated = {value for state, value in written if state is not ct.FactState.NEGATED}
    denied = tuple(dict.fromkeys(value for state, value in written
                                 if state is ct.FactState.NEGATED and value not in stated))
    return Fact(result=Res.UNRESOLVED, value=None, state=ct.FactState.CONTRADICTED, options=values,
                reasons=(ct.Reason.SLOT_OVERFULL,), spans=(), negated_values=denied)


# QD2's own rows of the DRE (D271's class) and v9_dre_own_rows': each leaves one of its rows 2-5 not met
QD2_ROWS = (('status unresolved', dict(status=unres(Status.PERFORMED))),
            ('status doubted', dict(status=doubted(Status.PERFORMED))),
            ('status negated', dict(status=neg(Status.PERFORMED))),
            ('status contradicted', dict(status=contra(Status.PERFORMED, Status.PLANNED))),
            ('date open', dict(date=unres(ON))), ('performer open', dict(performer=unres(TEAM))),
            ('entry nursing', dict(entry=sup(Owner.NURSING))), ('entry open', dict(entry=unres(DC))))
# A device that CLAIMS manual without establishing it (D280.3; the overfilled slot of AMENDMENT-2 4.3.3 c included)
CLAIMED = (('unresolved', unres(Device.MANUAL)), ('doubted', doubted(Device.MANUAL)),
           ('contradicted', contra(Device.MANUAL, Device.ENDOSCOPE)),
           ('overfilled', overfilled((ct.FactState.SUPPORTED, Device.MANUAL), (ct.FactState.SUPPORTED, Device.ENDOSCOPE))))


class D280Row7(SimpleTestCase):
    """DECISIONS D280.1 (build list B1; G3-09): row 7 reads no examination ESTABLISHED as a digital examination (kind
    supported examination, device supported manual: pairing.established_digital) - neither as the session's done
    examination nor as one whose rows 2-5 must pass - so the DRE's own open rows (QD2, held as built by D271) no longer
    hold 45385: READY, with no held fact and no item, the decision of the document without the DRE line. A device that
    only CLAIMS manual keeps QD2's hold (its witness on E1), worded by engine/questions (DIGITAL_SCOPE, D280.3); G2-28's
    input is pinned held (mutant: row 7 skipping the claimed digital examination). A 9.4 weakening never creates a
    supported device, so the reading never releases under one."""

    def test_an_established_dre_is_read_by_no_part_of_row_7(self):
        for name, over in QD2_ROWS:
            for beside in (True, False):
                with self.subTest(dre=name, beside=beside):
                    R = qd2_shape(dict(over, device=sup(Device.MANUAL)), beside=beside).build()
                    gone = without_events(R, E(1))
                    evaluation = decide('45385', R)
                    self.assertTrue(ready(evaluation))
                    self.assertEqual((evaluation.supporting, evaluation.held_facts, evaluation.exclusion),
                                     (decide('45385', gone).supporting, (), None))
                    self.assertIsNone(item('45385', R))
                    self.assertEqual(truths('45385', R, E(2))[rq.Requirement.SUP_SESSION_DONE], T)
                    if beside:
                        for kept in (1, 3):
                            self.assertEqual(status_of(decide('45378', R, (unit(kept),))),
                                             status_of(decide('45378', gone, (unit(kept),))))

    def test_a_claimed_device_keeps_qd2s_hold_on_e1(self):
        for name, over in QD2_ROWS:
            for device_name, device in CLAIMED:
                for beside in (True, False):
                    with self.subTest(dre=name, device=device_name, beside=beside):
                        R = qd2_shape(dict(over, device=device), beside=beside).build()
                        evaluation = decide('45385', R)
                        self.assertFalse(ready(evaluation))
                        self.assertIn(E(1), [entry.subject for entry in evaluation.held_facts])
                        self.assertNotEqual(truths('45385', R, E(2))[rq.Requirement.SUP_SESSION_DONE], T)
                        self.assertIs(item('45385', R).message, Q.MessageId.DIGITAL_SCOPE)

    def test_g2_28_pinned_held(self):
        """G2-28's input: the colonoscope's examination E1, its device doubted (endoscope or manual), its status open,
        beside the snare - held, its witness on E1's status, with or without another examination E3."""
        for beside in (False, True):
            with self.subTest(beside=beside):
                R = qd2_shape(dict(device=doubted(Device.ENDOSCOPE, Device.ENDOSCOPE, Device.MANUAL),
                                   status=unres(Status.PERFORMED)), beside=beside).build()
                evaluation = decide('45385', R)
                self.assertFalse(ready(evaluation))
                self.assertEqual([(entry.fact, entry.rank, entry.subject) for entry in evaluation.held_facts
                                  if entry.subject == E(1)], [('performed_status', 4, E(1))])

    def test_no_weakening_creates_an_established_digital_examination(self):
        """P-MONO's direction for D280.1: every 9.4 weakening of a supported manual device (unresolved, a doubt added,
        contradicted) or of a supported examination kind leaves the examination not established, so it is read again
        (held), never released; the established reading is reached only by strengthening."""
        from studio.interpretation.engine import pairing
        base = dict(status=unres(Status.PERFORMED))
        R = qd2_shape(dict(base, device=sup(Device.MANUAL))).build()
        self.assertTrue(pairing.established_digital(R, E(1)))
        for name, over in (('device unresolved', dict(device=unres(Device.MANUAL))),
                           ('device doubted', dict(device=doubted(Device.MANUAL, Device.MANUAL, Device.ENDOSCOPE))),
                           ('device contradicted', dict(device=contra(Device.MANUAL, Device.ENDOSCOPE))),
                           ('kind unresolved', dict(device=sup(Device.MANUAL), kind=unres(Kind.EXAMINATION))),
                           ('kind doubted', dict(device=sup(Device.MANUAL),
                                                 kind=doubted(Kind.EXAMINATION, Kind.EXAMINATION, Kind.SNARE)))):
            with self.subTest(weakened=name):
                R = qd2_shape(dict(base, **over)).build()
                self.assertFalse(pairing.established_digital(R, E(1)))
                self.assertFalse(ready(decide('45385', R)))


class D287ConflictKey(SimpleTestCase):
    """DECISIONS D287 (G3-28; build list B9), evaluate's half: the kind a conflict over an act is keyed by is
    facts.established_kind (questions.act_kind's derivation moved there, not copied) - Kind.OTHER for every kind not
    SUPPORTED, the catalogue kind of a supported kind with its supported purpose; with no act the code's group's first
    kind, Kind.OTHER for none."""

    def test_the_key_over_every_kind_state(self):
        group = (Kind.SNARE,)
        for name, kind, expected in (('silent', facts_module.SILENT, Kind.OTHER),
                                     ('unresolved', unres(Kind.SNARE), Kind.OTHER),
                                     ('doubted', doubted(Kind.SNARE, Kind.SNARE, Kind.BIOPSY), Kind.OTHER),
                                     ('contradicted', contra(Kind.SNARE, Kind.BIOPSY), Kind.OTHER),
                                     ('negated', neg(Kind.SNARE), Kind.OTHER), ('supported', sup(Kind.SNARE), Kind.SNARE),
                                     ('supported other', sup(Kind.OTHER), Kind.OTHER)):
            with self.subTest(kind=name):
                R = colonoscopy(kind=kind, status=contra(Status.PERFORMED, Status.PLANNED)).build()
                self.assertIs(facts_module.established_kind(R, E(2)), expected)
                self.assertIs(EV._conflict_kind(R, E(2), group), expected)
                self.assertIs(Q.act_kind(R, E(2), group), expected)
                held = [entry.fact for entry in decide('45385', R).held_facts if entry.fact.startswith('conflict:')]
                self.assertTrue(set(held) <= {f'conflict:{expected.value}'}, held)
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.CLIP, purpose=sup(ct.Purpose.HEMOSTASIS), cause=sup(ct.Cause.PRE_EXISTING_LESION),
                places=[sup(Landmark.SIGMOID_COLON)], status=contra(Status.PERFORMED, Status.PLANNED))
        R = doc.build()
        self.assertIs(EV._conflict_kind(R, E(2), (Kind.BLEEDING_CONTROL,)), Kind.BLEEDING_CONTROL)
        self.assertEqual([entry.fact for entry in decide('45382', R).held_facts if entry.fact.startswith('conflict:')],
                         ['conflict:bleeding_control'])
        self.assertIs(EV._conflict_kind(R, None, group), Kind.SNARE)
        self.assertIs(EV._conflict_kind(R, None, ()), Kind.OTHER)

    def test_b9_iii_the_population(self):
        """Build list B9 (iii): over every fixture of this module (all_fixtures), every per-code conflict held fact
        whose subject is an event is keyed conflict:<facts.established_kind(subject)> - its own row's and a relation's
        alike."""
        checked = 0
        for code, R, kept in all_fixtures():
            for held in decide(code, R, kept).held_facts:
                if held.fact.startswith('conflict:') and held.subject is not None \
                        and held.subject.family.value == 'E':
                    with self.subTest(code=code, held=held.fact, subject=str(held.subject)):
                        self.assertEqual(held.fact, f'conflict:{facts_module.established_kind(R, held.subject).value}')
                    checked += 1
        self.assertGreater(checked, 10)


def f3w_fixtures() -> list:
    """(code, FactSet, kept) for step f3w of AMENDMENT-2's build round (DECISIONS D280, D281, D287): OneItem builds each
    held code's one item (D182) and P-MONO weakens each - QD2's own rows with a claimed device (DIGITAL_SCOPE), G2-28's
    input, a claimed DRE statement beside the colonoscope's examination, G1-07's kind states beside an unlisted doubt or
    denial (no card, carded X1), and G3-28's kinds beside a broad denial with their status contradicted."""
    out = []
    for name, over in QD2_ROWS[:6]:
        for device_name, device in CLAIMED[::3]:
            out.append(('45385', qd2_shape(dict(over, device=device)).build(), ()))
    out.append(('45385', qd2_shape(dict(device=doubted(Device.ENDOSCOPE, Device.ENDOSCOPE, Device.MANUAL),
                                        status=unres(Status.PERFORMED)), beside=False).build(), ()))
    for status in (neg(Status.PERFORMED), unres(Status.PERFORMED)):
        doc = dre_alone(endoscopic={}, dre=False)
        doc.exam(1, device=unres(Device.MANUAL), status=status)
        out.append(('45378', doc.build(), (unit(2),)))
    for kind in (sup(Kind.EXAMINATION), unres(Kind.EXAMINATION), doubted(Kind.EXAMINATION, Kind.EXAMINATION, Kind.SNARE),
                 facts_module.SILENT):
        for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.DENIAL):
            for card in (None, X(1)):
                doc = colonoscopy(snare=False)
                doc.act(1, kind)
                doc.unlisted.append(unlisted(what, Kind.EXAMINATION, card, unit(9)))
                out.append(('45378', doc.build(), (unit(1),)))
    for kind in (facts_module.SILENT, unres(Kind.SNARE), sup(Kind.SNARE)):
        doc = colonoscopy(kind=kind, status=contra(Status.PERFORMED, Status.PLANNED))
        denial_event(doc, number=3, kind=Kind.SNARE)
        out.append(('45385', doc.build(), ()))
    return out
