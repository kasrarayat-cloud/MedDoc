"""9.4's property tests over the repaired engine (docs/gemini-migration/FINAL-V2.md 9.4; 5.7 measure 6; step 6a of its
8.1), and D246's P-WORDED. TEXT-ONLY and SYNTHETIC: every FactSet is built in code (tests/v2/test_assess.py's settled
fixtures, its EF.Doc builders), every answer by hand (tests/v2/test_settle.py's builders); nothing reads a document or
sends anything.

The step modules prove each property over their own module (test_evaluate, test_coverage, test_classes, test_combination,
test_pairing, test_facts, test_settle, test_claims, test_requirements: their docstrings name them). Here they run over
the ENGINE AS ASSEMBLED - engine/assess.assess_facts, every rule together - and over settle as the pipeline calls it:

- P-MONO (PMonoTests): for settled FactSets and every single 9.4 weakening of them - an established fact made
  unresolved; an established control made not rejected (a pair control, an EUS completeness claim); an added doubt
  (stated, unclear or conflict) on an established fact; a deleted ESTABLISHED member of a multi-valued list - a lesion's
  places, an act's target.places (REFUTATIONS-V2 SC-B's list), a session's stations or reached - the completeness claim
  and the pair controls left as they were (DECISIONS D245, repair r2d-2's Q3 option (b): 9.4's deletion weakens an
  established member only; deleting a member that was not established removes a doubt, and the release that follows is
  that doubt's own); an event's established status made unresolved, which makes it a possible statement - over every
  table of the FactSet, the encounter's, the people's and the sections' facts included (refutation 6a-r2b P4) - the
  READY and EXCLUDED sets never grow and the claims (combination.claims, each member's) never shrink; and the same for
  two weakenings drawn by hypothesis, with pass 2's verdicts on the pair controls drawn too (not every control
  rejected), each release named by the weakening that released it (refutation 6a-r2b P3). The harness never re-dates a
  weakened FactSet: the fixtures are dated once, when they are built, and ``assessed`` reads the date of service from
  the FactSet itself (P4). The fixtures carry what SC-B's weakenings act on (refutation 6a-r1 F1): the pair controls
  contract/claims makes from each FactSet's FULL lists (``paired``: claims.pair()'s rule, every one rejected), an EUS
  session's completeness claim, a session's stations, D218's enteroscopy, and the encounter's, people's and sections'
  facts; and D220's case (refutation 6a-r2b P1): a pair control NOT rejected beside the member a weakening deletes - a
  fixture holding one, and ``beside_unrejected_controls``, which makes each control asking about an established list
  member unrejected beside that member's deletion, on the act-act path (engine/coverage) and the statement-act path
  (engine/pairing) - so a D220-class release on any path turns PMonoTests red. A release a ruling accepts is a NAMED
  exception (ACCEPTED_RELEASES), checked by its own predicate, never a silent skip: DECISIONS D218's deleted beyond point
  of a jejunal enteroscopy; D245's r2d-2 Q2 (option (a)) - a deleted target.places member that overlapped the other
  object's place, every pair control between the two rejected (the remaining controls reject the deleted place, so this
  is not a false READY); and D245's r3d Q1 case (b), under D228 and D238 - beside an act-filed possible statement, a
  deleted member compatible with the other's place, no pair control between the two left unrejected (none was generated
  for that pair under D211, or every one that was is rejected). DECISIONS D262 and D264 name five more, each checked by
  its own predicate and met by a fixture of its own input: D228_STATUS (repair r3d's R3D-ST option (a), 6a's Q1; D264's
  Q7) - a status weakening to unresolved, to a doubt that keeps the value or to a conflict doubt (a contradicted
  status: D264 reads the three alike, the act's performance left unestablished; D262_STATUS names the three results)
  moves an act of another date or performer, inherited from a section, into D228's arm, which sets the pair apart with
  no pair control between the two left unrejected (D238); r4a's QM (r4a's request R7) as D264 narrows it to what D262
  accepted (6a's Q4) - D240's site fit under weakening, 4.4's class it extends: ONE OF THE LEAVING ACT'S OWN SUPPORT
  FACTS weakened moves it out of the supporting acts BY ITS SUPPORT while it held the code only by a code row, and the
  acts left, each supporting before, make the code READY; D264_CLEAN - the states that narrowing no longer accepts
  (refute-6a-r2 F2), a class of their own: an act leaves failing EXACTLY its clean row (4.3 row 8) after ANY 9.4
  weakening - another event's status, a pair control, or the leaving act's own place, weakened or deleted - any other
  leaving act being the weakened act out by its own support fact, the rest as QM, their count pinned (DECISIONS D288,
  ruling B QA (a): the class D264's sentence names, of which F2's 36 states - another event's status, a pair control
  made not rejected - are the measured instance; read literally, P-MONO's verdict on one FactSet would depend on the
  order of two commuting weakenings, refute-6a-r1 p06's 20 order-twins); D264_SITE (with D240: D29's installed site fit, whose exception D240's preamble names here; w7r's
  O13, repair r4d's R2) - a deleted member of an act's target.places, or of its target lesion's places, sets the act
  outside a code's SITE class, so the act leaves a code's supporting acts by its SITE row (evaluate's site fit) or a
  code's claims (combination's site fit) and so a competition, releasing that code or its rival, and the claims that
  drop the act shrink - each accepted under that name, the shrunk claims too; and repair r3d's R3D-NC - D238's
  production shape of r3d's case (b): a pair claims never controls (D211) with no pair control between the two at all,
  measured at D1-D3 (case (b) where controls exist, every one rejected, stays D245's). R3D-ST's input meets D228's
  corner kept as built too (DQ2, 3d's Q4): weakening the inherited performer takes the act out of 4.5's which pairs, a
  release named by that ruling (test_pairing leaves that weakening out of its generator, named). EVERY NAMED RELEASE IS
  ACCEPTED ONLY WHEN EVERY ACT STILL SUPPORTING THE RELEASED CODE MEETS EVERY ROW OF EVALUATE'S READING AFTER THE
  WEAKENING (DECISIONS D264; ``every_row_met``: engine/evaluate's support rows and code rows read act by act, never the
  engine's own held facts), so a named release never accepts a false READY: a release a name's shape takes that fails
  this fails P-MONO, naming its ruling and the rows. ANY OTHER RELEASE FAILS, its message naming the ruling that
  governs it (``_open_question``: D220's unrejected control, D238's arm, D262's and D264's conditions) - a release no
  ruling names goes to the owner, never into a pass. The single-weakening census runs under every pattern of pass 2's
  verdicts the random states can draw too (PMonoVerdicts0Tests-PMonoVerdicts5Tests, ``drawn_verdicts``: refute-6a-r1
  F2 - P-MONO was green only by its seed), so whatever the seed, no single weakening's release escapes it.
  OPEN_RELEASES - the releases a design question governs that the owner has not ruled - was emptied by D264 (it ruled
  refute-6a-r1 F3 and F5); it stays, with OpenQuestionsTests, as the guard for the next unruled release: such a release
  is never accepted - the other tests route it to OpenQuestionsTests, which fails on every one a single weakening under a
  fixture's own verdicts reaches, RED BY DESIGN until the owner rules (DECISIONS D245: "A release no ruling names still
  fails"), and each test that routes says in a comment what it then discards. AMENDMENT-2's build (step f3e) found 4.4's
  value-erasing contradictions (ERASING, which 9.4's generator gains) releasing, on two fixtures, the codes D262_QM,
  D262_STATUS and D228_DQ2 name for the classic weakening of the same fact, by the same transition (question Q-ERASE);
  DECISIONS D293 ruled them option (a): accepted under D293_ERASE, held to D264's every-row rule like every named
  release, their states pinned (ERASING_ACCEPTED), so OPEN_RELEASES is empty again. DECISIONS D294 (repair r2) adds two
  fixtures that release nothing under any weakening - an add-on whose only primary a cited denial excludes (RD-2) and an
  established denial of a kind (RD-3); D264's every-row check reads assess's ADDON row for a READY add-on
  (``addon_row_met``); and the generator keeps a negated claim negated, as settle does: a conflict doubt on a denial is
  a contradicted denial, and a denial has no pass-1 contradiction of its value (its sides would be stated).
- P-INDEP (IndependenceTests): perturbing any fact outside requirements.dependencies(code) leaves the code's status,
  its item (the held fact it asks and its message) and its held facts unchanged - test_assess's perturbation harness
  (repair 5a's R5), over every fixture here.
- P-INDEP-SETTLE, P-DEMOTE (SettleTests): test_settle's IndependenceTests.independence and DemotionTests's oracle over
  its notes, as repair r3a's R-E names them the reference (DECISIONS D201 and D224's coupling table).
- P-TEXTFREE (TextFreeTests; 5.7 measure 6): with R1's results and the kept spans given, every character of the
  revision text and of every stored slice replaced by 'x' (same lengths) leaves every outcome, item fact key, held fact
  and witness of the per-code rule, the combination, the coverage and the questions byte-identical; only rendered text
  changes. Its positive control: a planted rule that reads the text turns it red.
- P-DET (DeterminismTests): identical inputs give byte-identical assessments (sha256 of engine/assess.jsonable): the
  same FactSet twice, and one rebuilt from its tables (pass 1's order is part of the input, 1.7, so a reordered
  FactSet is another input).
- P-READSET (ReadSetTests): every (object class, attribute) a rule reads - a recording proxy over engine/facts' fact and
  members, questions.fill's display reads left out (repair 4a's R6) - is claimed for that object class
  (requirements.CLAIMED).
- P-CONTROLLED (ControlledTests): every (object class, attribute) a READY or exclusion path reads has a control
  generator (contract/claims' CONTROLS) or is on UNCONTROLLED.
- P-UNKNOWN-TARGET, P-UNKNOWN-KIND, P-ANY-ROW (PairingTests): over test_pairing's generated FactSets (random_factset)
  and its proving scenes, through engine/pairing as the engine calls it - held to the rulings as P-MONO is
  (``ruled_named_release``): D245 accepts r2d-2's Q2 (option (a), every place pair control between the two rejected),
  reads r2d-2's Q3 as no weakening (option (b): a deleted member that was not established), and accepts r3d's Q1 case
  (b), D228_PLACE, under D228 and D238 (no place pair control between the two left unrejected), and DECISIONS D262
  accepts D228_STATUS (repair r3d's R3D-ST option (a), 6a's Q1) for an inherited act of another date or performer on
  the same condition; a D228_PLACE or D228_STATUS release beside an unrejected control fails, naming D238 (built by
  repair r3d: the arm reads the controls that exist). P-UNKNOWN-TARGET excepts in D228's arm only what D228 and D238
  rule - a pair control NOT generated (a missing one is not required) - never a control generated and not rejected
  (r3d's Q1 case (a), D238: an unrejected one holds).
- P-WORDED (WordedTests; DECISIONS D246, a merge-gate property; the lead's seam finding L1): every item the engine makes
  is worded by the renderer (studio/jobs.word_item, the function _render_code words each held code's one item with)
  without a refusal, and a TEXT_FREE item (overlay.TEXT_FREE; a date item only when it quotes no statement, overlay's
  own rule) is worded identically by read time (overlay._words); the renderer never raises on an engine item, and a
  refusal fails naming its message id. Over every fixture scene of test_assess, test_combination, test_evaluate,
  test_refutation_cases, test_gate6 and test_failure_classes (``harvest``, in a fresh process so that nothing this
  process ran before hides a scene: their own tests run there, each assess_facts call recorded as made, and each per-code
  rule or combination scene a test hands the engine directly - evaluate.decide, combination.combine - assessed there with
  its codes proposed on the scene's own kept spans or supporting acts), and over P-MONO's FactSets: every fixture, every
  single weakening, D220's unrejected-control states and hypothesis's random states.
- P-SLOTS (SlotsTests; DECISIONS D254 rule 4, beside P-WORDED - P-WORDED words what the engine makes, this what it
  could make): for every Message and every combination of present and absent optional slots - the slots its builder
  reads (recorded to a fixpoint, and proved to be the only ones whose presence changes its words) - with values drawn
  from each slot's own type (wording._SLOT_TYPES: every member of an enumeration and every grouping of members the
  modules' own tables make - every subset of a small enumeration or table, UPPER_STATIONS, STENT_KINDS; spans of the
  synthetic text; every catalogue code), the slots wording declares as always carried (MESSAGES' needs, each with its
  reason in CARRIED) always given, wording.build returns a question and a reason, each a sentence; every value of every
  slot a builder reads, every pair of values of two slots of one type or of small pools, and random slots over every
  field, the same. And the builds execute every line of every builder (sys.monitoring; refute-6a-r1 F1: a branch no
  build reaches - STATIONS' two-station form, STATION_CLASS's three upper stations, SAME_DUCT's exchange, the limited
  class of 43237 and 43238 - is a branch whose refusal P-SLOTS cannot see), the measure's own control naming the
  branches the first build never reached. Its positive controls put A1's refusal back for the call, and the refuter's
  mutants MS1-MS4, and the property names each message alone.
- D254's six refusing shapes (SixShapesTests; D254 rule 4: "regression cases through jobs.word_item"): A1's enteroscopy
  approach established only by a denial, R3C1-01's act of contradicted kind, 5b F1's upper EUS act of kind other, r4d S1
  and S2c's kindless unlisted act carded to a session - ten FactSets, each as its refuter's probe builds it - are held
  and worded by studio/jobs.word_item without a refusal (read time agreeing, P-WORDED's check), A1's without naming a
  route (rule 3) and the act no kind names as 'another act' (rule 2).
"""
from __future__ import annotations

import ast
import collections
import contextlib
import datetime
import functools
import hashlib
import inspect
import itertools
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import types
import unittest
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from pathlib import Path
from unittest import mock

import hypothesis
from hypothesis import strategies as st
from django.test import SimpleTestCase

from studio import jobs
from studio.interpretation import overlay, wording
from studio.interpretation.contract import claims as CL
from studio.interpretation.contract import types as ct
from studio.interpretation.contract.types import Attribute as A
from studio.interpretation.contract.types import Result as Res
from studio.interpretation.engine import anatomy
from studio.interpretation.engine import assess as AS
from studio.interpretation.engine import catalogue as engine_catalogue
from studio.interpretation.engine import facts as F
from studio.interpretation.engine import pairing as P
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine import requirements as RQ
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import (Fact, FactSet, HeldFact, Id, IdFamily, IsoDate, ItemKind, Outcome, Span,
                                               UnlistedStatement)
from studio.types import EvidenceSpan, NormalizedResponse, ProviderCode
from tests.v2 import evaluate_fixtures as EF
from tests.v2 import test_assess as TA
from tests.v2 import test_classes as TC
from tests.v2 import test_settle as TS

SETTINGS = dict(max_examples=40, deadline=None, derandomize=True, database=None,
                suppress_health_check=list(hypothesis.HealthCheck))
ESTABLISHED = (Res.SUPPORTED, Res.NEGATED)
# 9.4's multi-valued lists whose member a weakening deletes ("places, stations, reached"): a lesion's places AND an act's
# target.places - the list REFUTATIONS-V2 SC-B is about, which the first round never deleted (refutation 6a-r1 F1)
LISTS = (A.PLACES, A.TARGET_PLACES, A.STATIONS, A.REACHED)
# Every table of the FactSet a weakening acts on (9.4: "on any fact"), the encounter's facts as one object (subject None),
# the people's and the sections' included (refutation 6a-r2b P4)
TABLES = {None: 'encounter', IdFamily.PERSON: 'people', IdFamily.SECTION: 'sections', IdFamily.EVENT: 'events',
          IdFamily.SESSION: 'sessions', IdFamily.LESION: 'lesions', IdFamily.ANATOMY: 'anatomy'}
HOWS = ('unresolved', 'doubt stated', 'doubt unclear', 'doubt conflict')
# AMENDMENT-2 4.4's value-erasing contradictions, which 9.4's generator gains [R:truth-T1]: an established single fact
# turned into (i) pass 1's own contradiction of its value and another (its settled value empty, the two its sides), and
# (ii) - on a slot attribute (facts.SLOTS) - an overfilled slot of its value plus another value written supported, or
# negated, read as engine/facts reads one (the merged view: unresolved, value None, state contradicted, slot_overfull,
# the written values its options, those only denied its negated_values). Each erases the claimed value, which no HOWS
# weakening does, so P-MONO runs on both (AMENDMENT-2 4.4): no HELD becomes READY or EXCLUDED and no rival is released.
ERASING = ('contradiction', 'overfilled stated', 'overfilled denied')
Kind, Landmark, Extent, Station = ct.Kind, ct.Landmark, ct.Extent, ct.Station
sup, unres, L = EF.sup, EF.unres, EF.L
P1, P2, N1 = Id(IdFamily.PERSON, 1), Id(IdFamily.PERSON, 2), Id(IdFamily.SECTION, 1)
EGD_CODES = (('43251', 2), ('43239', 3), ('43235', 1))
ONE_DILATION = (('43249', 2), ('43233', 2), ('43235', 1))  # test_assess's one balloon dilation: two codes compete
COLON_CODES = (('45385', 2), ('45380', 3), ('45378', 1))


# --- the pair controls as contract/claims makes them (3.2.3 [R:SC-B]; refutation 6a-r1 F1, repair r2d-2's R2) ----------

def _claimable(members) -> list:
    """The values claims names of a list: every member pass 1 filed supported, whatever settle made of it (claims are
    made from pass 1's answer, before the appraisal)."""
    return [member.value for member in members if member.state is ct.FactState.SUPPORTED]


def claims_rule_controls(R, rejected=lambda key: True) -> dict:
    """The pair controls contract/claims.pair_controls() makes for ``R`` from its FULL lists, by claims.pair()'s rule:
    each statement of a targeted breadth (single, listed, segment) against every act of a compatible or sibling kind in
    its session (any session when either is not stated), and every pair of acts a rule of identity by place reads
    together (claims._place_identity_pair, DECISIONS D211) not stated in different sessions; each object asked, both
    ways, about every place of the other none of its own places is compatible with (a segment's whole range, D223), and
    about the other's lesions when their lesions differ. ``rejected(key)``: pass 2's verdict on each (True:
    contradicted, as settle stores a rejected control)."""
    def first(event, attribute):
        members = R.events[event].get(attribute, ())
        return members[0].value if len(members) == 1 and members[0].state is ct.FactState.SUPPORTED else None

    def statement(event):
        members = R.events[event].get(A.STATUS, ())
        return len(members) == 1 and members[0].state is ct.FactState.NEGATED

    def places(event):
        own = _claimable(R.events[event].get(A.TARGET_PLACES, ()))
        segment = _claimable(R.events[event].get(A.SCOPE_SEGMENT, ()))
        return own + (list(CL.segment_range(segment[0], segment[1])) if len(segment) == 2 else segment)

    def lesions(event):
        return ([first(event, A.TARGET_LESION)] if first(event, A.TARGET_LESION) is not None else []) + [
            value for value in _claimable(R.events[event].get(A.SCOPE_TARGETS, ()))
            if getattr(value, 'family', None) is IdFamily.LESION]

    def apart(one, other):
        return one is not None and other is not None and one != other

    out = {}

    def pair(one, two):
        for asked, other in ((one, two), (two, one)):
            own, theirs = places(asked), places(other)
            if own and theirs:
                for place in CL._distinct(theirs):
                    if not any(anatomy.compatible(place, mine) for mine in own):
                        out[(asked, A.TARGET_PLACES, place)] = rejected((asked, A.TARGET_PLACES, place))
            own_lesions, their_lesions = lesions(asked), lesions(other)
            if own_lesions and their_lesions and set(own_lesions) != set(their_lesions):
                for lesion in sorted(set(their_lesions) - set(own_lesions), key=repr):
                    out[(asked, A.TARGET_LESION, lesion)] = rejected((asked, A.TARGET_LESION, lesion))

    events = [event for event in R.events if first(event, A.KIND) in RQ.CODABLE_KINDS]
    acts = [event for event in events if not statement(event)]
    for event in events:
        breadth = first(event, A.SCOPE_BREADTH)
        if not statement(event) or breadth not in CL._TARGETED:
            continue
        for act in acts:
            if CL._compatible(first(event, A.KIND), first(act, A.KIND)) and not apart(first(event, A.SESSION),
                                                                                     first(act, A.SESSION)):
                pair(event, act)
    for index, one in enumerate(acts):
        for two in acts[index + 1:]:
            if not apart(first(one, A.SESSION), first(two, A.SESSION)) and \
                    CL._place_identity_pair(first(one, A.KIND), first(two, A.KIND)):
                pair(one, two)
    return out


def paired(R, unrejected=()):
    """``R`` with the pair controls claims makes from its full lists (``claims_rule_controls``), every one rejected but
    the keys ``unrejected`` (pass 2 left them unclear: settle stores such a control as not rejected)."""
    controls = {**claims_rule_controls(R), **R.pair_controls}
    missing = [key for key in unrejected if key not in controls]
    if missing:
        raise ValueError(f'no pair control {missing} is made for this FactSet')
    return replace(R, pair_controls={**controls, **{key: False for key in unrejected}})


# --- the fixtures -------------------------------------------------------------------------------------------------------

def egd_snare_and_biopsy():
    """Repair r2d-2's question Q2 (NOTES section 7): an EGD X1 (E1) with a cold snare E2 of L1 in the esophagus and a
    biopsy E3 in the duodenum and the stomach (the stomach overlaps the esophagus without being compatible with it)."""
    doc = EF.egd()
    doc.lesion(1, lesion_places=[sup(Landmark.ESOPHAGUS)])
    doc.act(2, Kind.SNARE, places=[sup(Landmark.ESOPHAGUS)], lesion=sup(L(1)), device=sup(ct.Device.COLD_SNARE))
    doc.act(3, Kind.BIOPSY, places=[sup(Landmark.DUODENUM), sup(Landmark.STOMACH)])
    return doc.build()


def egd_body_and_antrum():
    """Refutation 6a-r2b P1's input (its probe p03): an EGD X1 (E1), a cold snare E2 of L1 in the gastric body and a
    biopsy E3 in the duodenum and the gastric antrum - places disjoint, so every control rejected sets the two apart."""
    doc = EF.egd()
    doc.lesion(1, lesion_places=[sup(Landmark.GASTRIC_BODY)])
    doc.act(2, Kind.SNARE, places=[sup(Landmark.GASTRIC_BODY)], lesion=sup(L(1)), device=sup(ct.Device.COLD_SNARE))
    doc.act(3, Kind.BIOPSY, places=[sup(Landmark.DUODENUM), sup(Landmark.GASTRIC_ANTRUM)])
    return doc.build()


# the control D220's case leaves unrejected in refutation 6a-r2b P1's fixture: the snare asked about the biopsy's antrum
P1_UNREJECTED = (EF.E(2), A.TARGET_PLACES, Landmark.GASTRIC_ANTRUM)


def colonoscopy_snare_and_biopsy():
    """Repair r2d-2's question Q3: EF.colonoscopy's cold snare E2 of L1 in the sigmoid colon and a biopsy E3 in the
    cecum (supported) and the rectum (unresolved)."""
    doc = EF.colonoscopy()
    doc.act(3, Kind.BIOPSY, places=[sup(Landmark.CECUM), unres(Landmark.RECTUM)])
    return doc.build()


def targeted_denial_beside_a_biopsy():
    """A statement - "No biopsies were taken from the rectum." (E3: biopsy, negated, single target, the rectum) - beside
    a biopsy E4 in the transverse colon, in EF.colonoscopy (its cold snare E2 of L1 in the sigmoid colon)."""
    doc = EF.colonoscopy()
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
            places=[sup(Landmark.RECTUM)], kind_words=EF.Span(300, 330), status_words=EF.Span(330, 360))
    doc.act(4, Kind.BIOPSY, places=[sup(Landmark.TRANSVERSE_COLON)])
    return doc.build()


def two_place_denial_beside_a_biopsy():
    """D220's case on the statement-act path (refutation 6a-r2b P1): "No biopsies were taken from the rectum or the
    cecum." (E3: biopsy, negated, single target, two places) beside a biopsy E4 in the transverse colon and the
    descending colon, in EF.colonoscopy without its snare - every place of one disjoint from every place of the other."""
    doc = EF.colonoscopy(snare=False)
    doc.act(3, Kind.BIOPSY, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
            places=[sup(Landmark.RECTUM), sup(Landmark.CECUM)], kind_words=EF.Span(300, 330),
            status_words=EF.Span(330, 360))
    doc.act(4, Kind.BIOPSY, places=[sup(Landmark.TRANSVERSE_COLON), sup(Landmark.DESCENDING_COLON)],
            device=sup(ct.Device.COLD_FORCEPS))
    return doc.build()


def possible_statement_beside_a_biopsy():
    """Repair r3d's question Q1 case (b), at the engine: in a colonoscopy (E1, no snare) a biopsy E2 whose status is
    unresolved - an act-filed possible statement, D228's arm - filed in the sigmoid colon and the transverse colon,
    beside an established biopsy E3 in the transverse colon. Two biopsies: no rule of identity by place reads a
    same-kind pair, so claims makes no pair control for them (D211)."""
    doc = EF.colonoscopy(snare=False)
    doc.act(2, Kind.BIOPSY, status=unres(ct.Status.PERFORMED),
            places=[sup(Landmark.SIGMOID_COLON), sup(Landmark.TRANSVERSE_COLON)])
    doc.act(3, Kind.BIOPSY, places=[sup(Landmark.TRANSVERSE_COLON)], device=sup(ct.Device.COLD_FORCEPS))
    return doc.build()


def ileocolic_anastomosis():
    """test_assess's COLFULL scene (DECISIONS D38): a colonoscopy X1 reaching an ileocolic anastomosis Y1 (its
    reached_anatomy) with a cold snare E2 in the sigmoid colon - 45385 READY by the anastomosis reached; the anatomy
    table's facts for P-MONO to weaken (refutation 6a-r2b P4)."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.COLONOSCOPY)
    doc.exam(1)
    doc.act(2, Kind.SNARE, places=[sup(Landmark.SIGMOID_COLON)], device=sup(ct.Device.COLD_SNARE))
    doc.sessions[EF.X(1)] = {**doc.sessions[EF.X(1)], A.REACHED_ANATOMY: (sup(EF.Y(1)),)}
    doc.entry(1, type=sup(ct.AnatomyType.ANASTOMOSIS), subtype=sup(ct.AnastomosisSubtype.ILEOCOLIC))
    return doc.build()


def eus_fna(stations=(), complete=None):
    """An upper EUS session X1 to the duodenum (its examination E1) with an FNA E2: its stations, and its completeness
    claim's settled result (``complete``), as tests/v2/test_evaluate.eus_fna builds it."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.EUS, tract=sup(ct.Tract.UPPER), stations=list(stations),
                reached=[sup(Extent.DUODENUM)])
    if complete is not None:
        doc.completeness[EF.X(1)] = complete
    doc.exam(1)
    doc.act(2, Kind.FNA)
    return doc.build()


def sections_and_people():
    """Refutation 6a-r2b P4: EF.colonoscopy told in a procedure section, so the encounter's, the people's and the
    sections' facts are there to weaken - the encounter's date of service and documenting clinician (P1); P1 the
    documenting clinician and P2 a trainee; the section N1 (owner the documenting clinician, role procedure, occasion
    the date of service, performer the documenting team, performer_person P1), whose occasion and performer the cold
    snare E2 inherits (inherited_from N1, as settle stores an inherited fact per act, 1.5). Dated here, once."""
    R = EF.colonoscopy().build()
    people = {P1: {A.ROLE: (sup(ct.PersonRole.DOCUMENTING_CLINICIAN),)}, P2: {A.ROLE: (sup(ct.PersonRole.TRAINEE),)}}
    sections = {N1: {A.OWNER: (sup(ct.Owner.DOCUMENTING_CLINICIAN),), A.ROLE: (sup(ct.SectionRole.PROCEDURE),),
                     A.OCCASION: (sup(ct.DateRelation.ON_DATE_OF_SERVICE),), A.PERFORMER: (sup(EF.TEAM),),
                     A.PERFORMER_PERSON: (sup(P1),)}}
    snare = {**R.events[EF.E(2)], A.DATE_RELATION: (sup(EF.ON, inherited_from=N1),),
             A.PERFORMER: (sup(EF.TEAM, inherited_from=N1),)}
    encounter = {A.DATE_OF_SERVICE: (sup(IsoDate(TA.DAY, ct.Precision.DAY)),), A.DOCUMENTING_CLINICIAN: (sup(P1),)}
    return replace(R, encounter=encounter, people=people, sections=sections, events={**R.events, EF.E(2): snare})


def inherited_other_clinician_beside_a_biopsy(*, own=False):
    """DECISIONS D262's D228_STATUS (repair r3d's R3D-ST, option (a); 6a's Q1), its input: in a colonoscopy (E1, no
    snare) a biopsy E2 in the rectum told under another clinician - its performer inherited from a section (N1), which the
    performer row reads as the team's (D188; D228: DQ2 as built), so the pair is held UNRESOLVED - beside the team's
    biopsy E3 in the sigmoid colon. Two biopsies: claims makes no pair control for them (D211). ``own``: the other
    clinician stated in E2's own sentence instead (the performer row then sets the two apart: nothing is held)."""
    doc = EF.colonoscopy(snare=False)
    other = sup(ct.Performer.OTHER_CLINICIAN) if own else sup(ct.Performer.OTHER_CLINICIAN, inherited_from=N1)
    doc.act(2, Kind.BIOPSY, places=[sup(Landmark.RECTUM)], performer=other)
    doc.act(3, Kind.BIOPSY, places=[sup(Landmark.SIGMOID_COLON)], device=sup(ct.Device.COLD_FORCEPS))
    return doc.build()


def two_esophageal_dilations_and_a_duodenal_one(*, duodenal=True):
    """DECISIONS D262's r4a QM (r4a's request R7; w7r/r4a-2's NOTES, its probe pmono_w7r_copy): an EGD X1 (its
    examination E3), E1 a distal-esophageal dilation of unstated device, E2 a mid-esophageal balloon dilation and E4 a
    duodenal-bulb balloon dilation. 43249 is held on E1's technique (E1 meets its support and fails a code row); D240's
    site fit drops E4, established outside the esophageal class, beside E2 within it. ``duodenal``: False leaves E4 out
    (4.4's pre-existing class, which D240 extends)."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(3)
    doc.act(1, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS)], device=None)
    doc.act(2, Kind.DILATION, places=[sup(Landmark.MID_ESOPHAGUS)], device=sup(ct.Device.BALLOON))
    if duodenal:
        doc.act(4, Kind.DILATION, places=[sup(Landmark.DUODENAL_BULB)], device=sup(ct.Device.BALLOON))
    return doc.build()


def a_dilation_filed_in_two_classes_beside_one_within(*, on_its_lesion=False):
    """refute-6a-r1 F3's input (its probe p06; 6a's Q6): an EGD X1 (its examination E3), E1 a dilation of unstated device
    filed [distal esophagus, duodenal bulb] - its site open for either site class - and E2 a mid-esophageal balloon
    dilation; 43249 (the esophageal class) is held on E1's technique and 43245 (the gastric or duodenal class) on E1's
    site, the two competing for E1. Deleting E1's distal esophagus reads the short list as E1's site (D29 and D240's site
    fit): 43249 READY on E2, 43245 READY on E1, 43249's claim drops E1; deleting the duodenal bulb drops E1 from 43245's
    claim - DECISIONS D264's D264_SITE, accepted (Q6 option (a)). ``on_its_lesion``: the two places filed on E1's target
    lesion (a stricture L1), E1 with no place of its own - D264's "or of its target lesion's places" (repair r4d's R2,
    w7r's O13); the pair controls claims makes ask an act's own places only, so this form has none."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(3)
    places = [sup(Landmark.DISTAL_ESOPHAGUS), sup(Landmark.DUODENAL_BULB)]
    if on_its_lesion:
        doc.lesion(1, lesion_places=places)
        doc.act(1, Kind.DILATION, places=[], lesion=sup(L(1)), device=None)
    else:
        doc.act(1, Kind.DILATION, places=places, device=None)
    doc.act(2, Kind.DILATION, places=[sup(Landmark.MID_ESOPHAGUS)], device=sup(ct.Device.BALLOON))
    return doc.build()


def doubted_snare_filed_in_full_beside_a_snare():
    """DECISIONS D262's r3d R3D-NC (D238's production shape; refute-r3d-r1's D1): a colonoscopy, its cold snare E2 of L1
    in the transverse colon, and E3 a cold snare whose status a stated doubt names (an act-filed possible statement:
    D228's arm) filed in full, [rectum, transverse colon]: 45385 held. Two snares: claims makes no pair control for them
    (D211), so deleting E3's transverse colon - the place D1's production filing omits - sets the two apart with no
    control to read (D238: a missing one is not required)."""
    doc = EF.colonoscopy(places=[sup(Landmark.TRANSVERSE_COLON)])
    doc.lesions[EF.L(1)] = EF.facts_of(lesion_places=[sup(Landmark.TRANSVERSE_COLON)])
    doc.act(3, Kind.SNARE, status=EF.doubted(ct.Status.PERFORMED),
            places=[sup(Landmark.RECTUM), sup(Landmark.TRANSVERSE_COLON)], device=sup(ct.Device.COLD_SNARE))
    return doc.build()


def possible_statement_beside_a_biopsy_and_a_snare():
    """D245's case (b) where pair controls exist (6a's Q2 breadth, as built by D262): r3d's case (b) - a biopsy E2 whose
    status is unresolved filed [sigmoid colon, transverse colon] beside an established biopsy E3 in the transverse colon
    - and a cold snare E4 of L1 in the descending colon, which claims pairs with each biopsy (a biopsy of a removed
    lesion, D211): place pair controls are asked of E2 and of E3, every one rejected."""
    doc = EF.colonoscopy(snare=False)
    doc.act(2, Kind.BIOPSY, status=unres(ct.Status.PERFORMED),
            places=[sup(Landmark.SIGMOID_COLON), sup(Landmark.TRANSVERSE_COLON)])
    doc.act(3, Kind.BIOPSY, places=[sup(Landmark.TRANSVERSE_COLON)], device=sup(ct.Device.COLD_FORCEPS))
    doc.lesion(1, lesion_places=[sup(Landmark.DESCENDING_COLON)])
    doc.act(4, Kind.SNARE, places=[sup(Landmark.DESCENDING_COLON)], lesion=sup(L(1)), device=sup(ct.Device.COLD_SNARE))
    return doc.build()


def addon_beside_its_excluded_primary():
    """DECISIONS D294 RD-2's P-MONO fixture (repair r2, builder R2A): test_assess's ERCP - an examination E1, a biliary
    cannulation E2 achieved, a cholangioscopy E3 and a sphincterotomy E4 of the bile duct - with a stone-extraction
    denial E6 (status negated performed, breadth all_of_kind) whose kind and status words 43264 is cited on: 43264
    EXCLUDED and the add-on 43273 (on E3) held by ADDON, its only primary excluded. No weakening of any fact of that
    exclusion may release the add-on (engine/assess.addon_uncounted: a primary a statement may exclude is not counted)."""
    doc = TA.ercp(stone=False)
    doc.act(6, Kind.STONE_EXTRACTION, status=EF.neg(ct.Status.PERFORMED), breadth=sup(ct.Breadth.ALL_OF_KIND),
            kind_words=Span(600, 630), status_words=Span(630, 660))
    return doc.build()


ADDON_CODES = (('43264', EvidenceSpan(0, 600, 660, TA.TEXT[600:660], True)), ('43273', 3))


def denial_of_a_kind():
    """DECISIONS D294 RD-3's P-MONO fixture (repair r2, builder R2A): test_assess's enriched() two sessions with the
    colonoscopy's examination E1 an established denial of its kind (result and state negated: "E1 is not an
    examination", FillTests' own perturbation) - every other kind is what E1 may be (coverage.may_be), so 45385 is held
    beside it - and no weakening of that denial may narrow what E1 may be to the denied kind."""
    R = TA.enriched().build()
    found = R.events[EF.E(1)][A.KIND][0]
    denial = replace(found, result=Res.NEGATED, state=ct.FactState.NEGATED, value=Kind.EXAMINATION)
    return replace(R, events={**R.events, EF.E(1): {**R.events[EF.E(1)], A.KIND: (denial,)}})


def fixtures():
    """(name, the settled FactSet, the proposals) the properties run over: test_assess's assess fixtures, and the SC-B
    fixtures (refutation 6a-r1 F1) - two_sessions and r2d-2's Q2 and Q3 shapes and two targeted denials, each with the
    pair controls claims makes from its full lists; refutation 6a-r2b P1's snare and biopsy with the control about the
    antrum NOT rejected (D220's case); r3d's Q1 case (b); an EUS FNA on its completeness claim and one through its three
    stations; D218's oral enteroscopy reaching the jejunum and the ileum; the encounter's, people's and sections' facts
    and an anatomy entry (P4); and the shapes of DECISIONS D262's named releases - R3D-ST's inherited act of another
    clinician (D228_STATUS), r4a QM's three dilations (D240's site fit under weakening), R3D-NC's doubted snare filed in
    full (D238's production shape) - with D245's case (b) where pair controls exist; and DECISIONS D264's D264_SITE:
    refute-6a-r1 F3's dilation filed in two site classes (6a's Q6), on its own places and on its target lesion's places
    (D264_CLEAN's states are r4a QM's fixture under drawn verdicts); and DECISIONS D294's two (repair r2): an add-on whose
    only primary a cited denial excludes (RD-2) and an established denial of a kind (RD-3). Each is dated here, once
    (``assessed`` never re-dates a FactSet)."""
    return (
        ('two sessions', TA.dated(TA.two_sessions().build()), TA.TWO),
        ('enriched', TA.dated(TA.enriched().build()), TA.TWO),
        ('egd dilation', TA.dated(TA.egd_dilation().build()), (('43249', 2), ('43239', 3), ('43235', 1))),
        ('one balloon dilation', TA.dated(TA.one_dilation().build()), ONE_DILATION),
        ('office and sigmoidoscopy', TA.dated(TA.office_and_sigmoidoscopy().build()), (('99213', 1), ('45330', 2))),
        ('denial beside a snare', TA.dated(TA.denial_beside_a_snare().build()),
         (('45385', 2), ('45380', TA.DENIAL_SPAN), ('45378', 1))),
        ('two sessions, paired', TA.dated(paired(TA.two_sessions().build())), TA.TWO),
        ('a snare beside a biopsy of two places (EGD)', TA.dated(paired(egd_snare_and_biopsy())), EGD_CODES),
        ('a snare beside a biopsy, one place unresolved', TA.dated(paired(colonoscopy_snare_and_biopsy())),
         COLON_CODES),
        ('a targeted denial beside a biopsy elsewhere', TA.dated(paired(targeted_denial_beside_a_biopsy())),
         (('45385', 2), ('45380', 4), ('45378', 1))),
        ('a two-place denial beside a biopsy of two places', TA.dated(paired(two_place_denial_beside_a_biopsy())),
         (('45380', 4), ('45378', 1))),
        ('a snare beside a biopsy of the antrum, its control not rejected (D220)',
         TA.dated(paired(egd_body_and_antrum(), unrejected=(P1_UNREJECTED,))), EGD_CODES),
        ('a possible statement beside a biopsy (D228)', TA.dated(paired(possible_statement_beside_a_biopsy())),
         (('45380', 3), ('45378', 1))),
        ('an EUS FNA on its completeness claim', TA.dated(eus_fna(complete=Res.SUPPORTED)), (('43242', 2),)),
        ('an EUS FNA through its three stations',
         TA.dated(eus_fna(stations=[sup(Station.ESOPHAGUS), sup(Station.STOMACH), sup(Station.DUODENUM)])),
         (('43242', 2),)),
        ('an oral enteroscopy to the jejunum and the ileum (D218)', TA.dated(TC.ent(Extent.JEJUNUM, Extent.ILEUM)),
         (('44361', 14),)),
        ('the encounter, people and sections (P4)', paired(sections_and_people()), (('45385', 2), ('45378', 1))),
        ('an ileocolic anastomosis reached (D38)', TA.dated(ileocolic_anastomosis()), (('45385', 2),)),
        ("another clinician's biopsy (inherited) beside the team's (D262, R3D-ST)",
         TA.dated(paired(inherited_other_clinician_beside_a_biopsy())), (('45380', 3), ('45378', 1))),
        ('two esophageal dilations and a duodenal one (D262, r4a QM)',
         TA.dated(paired(two_esophageal_dilations_and_a_duodenal_one())), (('43249', 2),)),
        ('a doubted snare filed in full beside a snare (D262, R3D-NC)',
         TA.dated(paired(doubted_snare_filed_in_full_beside_a_snare())), (('45385', 2), ('45378', 1))),
        ('a possible statement beside a biopsy and a snare, its controls rejected (D245)',
         TA.dated(paired(possible_statement_beside_a_biopsy_and_a_snare())), (('45380', 3), ('45385', 4), ('45378', 1))),
        ('a dilation filed in two site classes beside one within (refute-6a-r1 F3)',
         TA.dated(paired(a_dilation_filed_in_two_classes_beside_one_within())), (('43249', 2), ('43245', 1))),
        (LESION_SITE_FIXTURE, TA.dated(paired(a_dilation_filed_in_two_classes_beside_one_within(on_its_lesion=True))),
         (('43249', 2), ('43245', 1))),
        (ADDON_FIXTURE, TA.dated(addon_beside_its_excluded_primary()), ADDON_CODES),
        (KIND_DENIAL_FIXTURE, TA.dated(denial_of_a_kind()), TA.TWO),
    )


F3_FIXTURE = 'a dilation filed in two site classes beside one within (refute-6a-r1 F3)'
LESION_SITE_FIXTURE = 'a dilation of a stricture filed in two site classes beside one within (D264, its lesion places)'
QM_FIXTURE = 'two esophageal dilations and a duodenal one (D262, r4a QM)'
ADDON_FIXTURE = 'an add-on whose only primary a cited denial excludes (D294 RD-2)'
KIND_DENIAL_FIXTURE = 'an established denial of a kind (D294 RD-3)'


def fixture(name):
    return next((R, codes) for found, R, codes in fixtures() if found == name)


# --- the harness ---------------------------------------------------------------------------------------------------------

def service_date(R):
    """The date of service a FactSet itself gives (engine/derive.date_record's verified reading): its encounter's date
    of service supported at day precision; None otherwise - then R7 holds every code (assess.r7_row). Read from the
    FactSet, never set from outside, so a weakened date of service reaches the engine (refutation 6a-r2b P4)."""
    found = F.fact(R, None, A.DATE_OF_SERVICE)
    value = found.value
    if found.result is Res.SUPPORTED and isinstance(value, IsoDate) and value.precision is ct.Precision.DAY:
        return value.value
    return None


def assessed(R, codes, *, text=TA.TEXT, provider=None) -> AS.Assessment:
    """engine/assess.assess_facts over ``R`` AS GIVEN - never re-dated (refutation 6a-r2b P4: test_assess.run replaces
    the encounter) - its date of service read from ``R`` (``service_date``), the proposal provider selecting ``codes``
    (or ``provider``'s answer), with test_assess.run's other inputs."""
    return AS.assess_facts(R, date_of_service=service_date(R), text=text, pages=(), integrity=TA.Integrity(),
                           provider_status='succeeded',
                           proposals=provider if provider is not None else TA.corti(*codes, text=text),
                           reference=TA.Lookup(), member=TA.ENTERED, label=lambda session: str(session.id),
                           participants=(), second=None, answers=())


def ready(assessment) -> frozenset:
    return frozenset(found.code for found in assessment.codes if found.status is Outcome.READY)


def excluded(assessment) -> frozenset:
    return frozenset(found.code for found in assessment.codes if found.status is Outcome.EXCLUDED)


def claims(assessment) -> dict:
    """Each member's claims (combination.claims) by its CODE: a member's key is its position among the counted codes,
    which moves when a weakening changes which codes are counted."""
    code_of = {found.key: found.code for found in assessment.codes}
    return {code_of[key]: frozenset(acts) for key, acts in assessment.combination.claims.items()}


# --- 9.4's weakenings --------------------------------------------------------------------------------------------------

def _weakened_fact(found: Fact, how: str) -> Fact | None:
    """``found`` weakened as 9.4 names it, or None when the weakening does not apply (it is not established)."""
    if found.result not in ESTABLISHED:
        return None
    if how == 'unresolved':
        return replace(found, result=Res.UNRESOLVED, options=(), reasons=(ct.Reason.APPRAISAL_UNCLEAR,))
    if how in ('doubt stated', 'doubt unclear'):
        reason = ct.Reason.DOUBT_STATED if how == 'doubt stated' else ct.Reason.DOUBT_UNCLEAR
        return replace(found, result=Res.UNKNOWN, options=(), reasons=(reason,))
    if how == 'doubt conflict':  # 3.3 row 1: a conflict doubt contradicts, keeping the claimed value
        # and pass 1's claim: settle keeps the claim's state, which the FactSet reads, so a conflict doubt on a denial
        # is a contradicted DENIAL - never a stated side, which would erase the negation (no weakening of it: the ready
        # lens's RD-3 artifacts, DECISIONS D294); any other claim keeps the generator's contradicted state
        state = ct.FactState.NEGATED if found.state is ct.FactState.NEGATED else ct.FactState.CONTRADICTED
        return replace(found, result=Res.CONTRADICTED, state=state, options=(found.value,),
                       reasons=(ct.Reason.DOUBT_UNCLEAR,))
    raise ValueError(how)


def another_value(found: Fact, family, attribute, R):
    """The other value a value-erasing contradiction writes beside ``found``'s (ERASING), deterministic: for an
    enumeration the first member of the attribute's domain (facts.DOMAINS) that is not its value; for an id the first
    object of the same family the FactSet holds that is not it, else an id of that family the FactSet does not hold; for a
    date the next day at its precision; None when the attribute has no domain or no other value."""
    domain = F.DOMAINS.get((family, attribute))
    if domain is None or domain.many:
        return None
    value = found.value
    if domain.enum is not None:
        return next((member for member in domain.enum if member != value), None)
    if domain.family is not None:
        held = {IdFamily.EVENT: R.events, IdFamily.SESSION: R.sessions, IdFamily.SECTION: R.sections,
                IdFamily.LESION: R.lesions, IdFamily.ANATOMY: R.anatomy, IdFamily.PERSON: R.people}[domain.family]
        return next((other for other in held if other != value), Id(domain.family, 99))
    if isinstance(value, IsoDate):
        return IsoDate(value.value + datetime.timedelta(days=1), value.precision)
    return None


def erased_fact(found: Fact, how: str, other) -> Fact | None:
    """``found`` turned into AMENDMENT-2 4.4's value-erasing contradiction ``how`` (ERASING) with ``other``, or None when
    it does not apply (not established, or no other value)."""
    if found.result not in ESTABLISHED or other is None or other == found.value:
        return None
    if how == 'contradiction' and found.state is ct.FactState.NEGATED:
        # pass 1's own contradiction STATES each side: of a denial ("not X") it would state X - erasing the negation,
        # no weakening of the denial (the ready lens's RD-3 artifacts, DECISIONS D294); a denial's value-erasing
        # contradictions are its two overfilled views (a slot), none for a required fact
        return None
    if how == 'contradiction':  # pass 1's own contradiction (3.3 row 1): the settled value empty, the sides its options
        return Fact(result=Res.CONTRADICTED, value=None, state=ct.FactState.CONTRADICTED, options=(found.value, other),
                    reasons=(ct.Reason.CONTRADICTED_BY_PASS1,), spans=found.spans, cited=found.cited,
                    inherited_from=found.inherited_from)
    if how in ('overfilled stated', 'overfilled denied'):  # facts._overfilled's merged view of the two written facts
        written = ((found.state, found.value),
                   (ct.FactState.SUPPORTED if how == 'overfilled stated' else ct.FactState.NEGATED, other))
        stated = {value for state, value in written if state is not ct.FactState.NEGATED}
        return Fact(result=Res.UNRESOLVED, value=None, state=ct.FactState.CONTRADICTED,
                    options=(found.value, other), reasons=(ct.Reason.SLOT_OVERFULL,), spans=found.spans,
                    cited=found.cited, inherited_from=found.inherited_from,
                    negated_values=tuple(value for state, value in written
                                         if state is ct.FactState.NEGATED and value not in stated))
    raise ValueError(how)


def _erasings(R, subject, attribute, found):
    """The value-erasing contradictions (ERASING) of one established single fact: (how, the erased fact) - the
    contradiction for every single-valued attribute, the two overfilled slots for a slot attribute (facts.SLOTS)."""
    family = subject.family if subject is not None else None
    other = another_value(found, family, attribute, R)
    for how in ERASING:
        if how != 'contradiction' and (family, attribute) not in F.SLOTS:
            continue
        new = erased_fact(found, how, other)
        if new is not None:
            yield how, new


def _objects(R, name):
    """(subject, its facts by attribute) of one table: the encounter's facts are one object, subject None."""
    table = getattr(R, name)
    return [(None, table)] if name == 'encounter' else list(table.items())


def _with(R, name, subject, attributes):
    """``R`` with ``subject``'s facts in table ``name`` replaced by ``attributes``."""
    if name == 'encounter':
        return replace(R, encounter=attributes)
    return replace(R, **{name: {**getattr(R, name), subject: attributes}})


def _subject(subject) -> str:
    return 'encounter' if subject is None else str(subject)


def weakenings(R, *, erasing: bool = True):
    """Every single 9.4 weakening of ``R``: (label, the weakened FactSet, what was weakened) - ``what`` is (subject,
    attribute, position, the fact as it was) for a fact, the key for a pair control, the session for a completeness
    claim. Over every table (TABLES); a list member is deleted only when it is established (DECISIONS D245); and
    AMENDMENT-2 4.4's value-erasing contradictions of every established single fact (ERASING; ``erasing=False`` leaves
    them out, for a census pinned before them)."""
    for name in TABLES.values():
        for subject, attributes in _objects(R, name):
            for attribute, members in attributes.items():
                for position, found in enumerate(members):
                    for how in HOWS:
                        new = _weakened_fact(found, how)
                        if new is None:
                            continue
                        changed = {**attributes, attribute: members[:position] + (new,) + members[position + 1:]}
                        yield (f'{how} {_subject(subject)} {attribute.value}[{position}]',
                               _with(R, name, subject, changed), (subject, attribute, position, found))
                    family = subject.family if subject is not None else None
                    domain = F.DOMAINS.get((family, attribute))
                    if not erasing or domain is None or domain.many:
                        continue
                    for how, new in _erasings(R, subject, attribute, found):
                        changed = {**attributes, attribute: members[:position] + (new,) + members[position + 1:]}
                        yield (f'{how} {_subject(subject)} {attribute.value}[{position}]',
                               _with(R, name, subject, changed), (subject, attribute, position, found))
                if attribute not in LISTS:
                    continue
                for position, found in enumerate(members):
                    if found.result not in ESTABLISHED:
                        continue  # D245 (r2d-2's Q3, option (b)): 9.4's deletion weakens an established member only
                    changed = {**attributes, attribute: members[:position] + members[position + 1:]}
                    yield (f'deleted {_subject(subject)} {attribute.value}[{position}]',
                           _with(R, name, subject, changed), (subject, attribute, position, found))
    for key, rejected in R.pair_controls.items():
        if rejected:
            yield f'pair control {key} not rejected', replace(R, pair_controls={**R.pair_controls, key: False}), key
    for session, result in R.completeness.items():
        if result in ESTABLISHED:
            yield (f'completeness {session} unresolved', replace(R, completeness={**R.completeness,
                                                                                  session: Res.UNRESOLVED}), session)


def beside_unrejected_controls(R):
    """D220's case (refutation 6a-r2b P1; repair r2d-2's R2): for each pair control of ``R`` that asks an object O about
    a place an established target.places member of another object S holds, (label, ``R`` with that control NOT rejected,
    9.4's deletion of that member from S, the controls left as they were, what was deleted, the path): the deleted
    member's unrejected control keeps the pair together (DECISIONS D220), so no code may be released. ``path``: 'act-act'
    (engine/coverage's identity by place) or 'statement-act' (engine/pairing), as either object is a statement."""
    for key, rejected in R.pair_controls.items():
        asked, attribute, value = key
        if attribute is not A.TARGET_PLACES or not rejected:
            continue
        unrejected = replace(R, pair_controls={**R.pair_controls, key: False})
        for subject, attributes in R.events.items():
            members = attributes.get(A.TARGET_PLACES, ())
            if subject == asked or len(members) < 2:
                continue  # a list of one member deleted is empty, and an empty list sets nothing apart
            for position, found in enumerate(members):
                if found.value is not value or found.result not in ESTABLISHED:
                    continue
                changed = {**attributes, A.TARGET_PLACES: members[:position] + members[position + 1:]}
                path = 'statement-act' if P.is_statement(R, subject) or P.is_statement(R, asked) else 'act-act'
                yield (f'pair control {key} not rejected; deleted {subject} target.places[{position}]', unrejected,
                       replace(unrejected, events={**unrejected.events, subject: changed}),
                       (subject, A.TARGET_PLACES, position, found), path)


# --- the releases a ruling accepts (named exceptions, each checked by its own predicate - never a silent skip) --------

def _deleted_place(label, what):
    """The deleted target.places member's (subject, member), or None for any other weakening."""
    if label.split('; ')[-1].startswith('deleted ') and isinstance(what, tuple) and what[1] is A.TARGET_PLACES:
        return what[0], what[3]
    return None


def places_named(R, subject) -> set:
    """Every place ``subject``'s target place list names, in any state, and its segment's whole range."""
    found = R.events.get(subject, {})
    out = {item.value for item in found.get(A.TARGET_PLACES, ()) if isinstance(item.value, Landmark)}
    ends = [item.value for item in found.get(A.SCOPE_SEGMENT, ()) if isinstance(item.value, Landmark)]
    return out | (set(CL.segment_range(ends[0], ends[1])) if len(ends) == 2 else set())


def place_controls_between(R, one, other) -> dict:
    """Every place pair control between two objects as facts.apart_by_controls reads it (DECISIONS D220, repair r2d's
    reading D1): every target.places control asked of either - which pair a control was made for cannot be told."""
    return {key: rejected for key, rejected in R.pair_controls.items()
            if key[1] is A.TARGET_PLACES and key[0] in (one, other)}


def every_place_control_rejected(R, one, other) -> bool:
    return all(place_controls_between(R, one, other).values())


def _d228_arm(R, one, other) -> bool:
    """Either object is an act-filed possible statement paired with the other (engine/pairing's D228 arm)."""
    return any(not P.filed_as_statement(R, x) and P.possible(R, x) and P.paired(R, x, y)
               for x, y in ((one, other), (other, one)))


def _overlaps(member, place) -> bool:
    return not anatomy.compatible(member, place) and not anatomy.disjoint(member, place)


def _jejunal_beyond_deletion(label, what, code, R, transition=None) -> bool:
    """DECISIONS D218, as repair r4c's NOTES name it with that ruling (section 7 and its R2; engine/classes.py's REACH
    paragraph): 9.4's deleted-member weakening releases a jejunal enteroscopy code (44360-44373) when the deleted REACHED
    member was the beyond point - a member NOT established negated whose value or an option is in
    engine/classes.BEYOND[JEJUNAL]: a supported beyond point (D245: only an established member is deleted, so it is a
    supported one). Nothing else: a negated member, a member of another list, another code."""
    from studio.interpretation.engine import classes

    if not label.split('; ')[-1].startswith('deleted ') or not isinstance(what, tuple) or what[1] is not A.REACHED:
        return False
    member = what[3]
    if member.result is Res.NEGATED:
        return False
    beyond = classes.BEYOND[classes.EnteroscopyClass.JEJUNAL]
    values = {member.value, *member.options}
    return code.isdigit() and 44360 <= int(code) <= 44373 and bool(values & set(beyond))


def _overlap_deletion(label, what, code, R, transition=None) -> bool:
    """DECISIONS D245 (repair r2d-2's Q2, option (a)): 9.4's deletion of an established target.places member of S
    releases a code when the member overlapped a place another object O names - neither compatible nor disjoint
    (engine/anatomy) - and every place pair control between S and O was rejected: the remaining controls reject the
    deleted place, so the release is no false READY. Nothing else: an unrejected control between the two (D220: it keeps
    the pair together), a member compatible with the other's place or disjoint from it, a member not established."""
    deleted = _deleted_place(label, what)
    if deleted is None:
        return False
    subject, member = deleted
    if member.result not in ESTABLISHED or not isinstance(member.value, Landmark):
        return False
    return any(other != subject and any(_overlaps(member.value, place) for place in places_named(R, other))
               and every_place_control_rejected(R, subject, other) for other in R.events)


def _d228_compatible_deletion(label, what, code, R, transition=None) -> bool:
    """DECISIONS D245 with D228 and D238 (repair r3d's Q1, case (b)): beside an act-filed possible statement (pairing's
    D228 arm: set apart by target without pair controls), 9.4's deletion of an established target.places member that
    is compatible with a place the other object names - a place no pair control asks about (claims asks only about
    places none of one's own is compatible with) - releases the pair when no place pair control between the two is left
    unrejected (D238: the arm reads the controls that exist, an unrejected one holds, a missing one is not required -
    none at all for a pair of acts no identity rule reads together, D211)."""
    deleted = _deleted_place(label, what)
    if deleted is None:
        return False
    subject, member = deleted
    if member.result not in ESTABLISHED or not isinstance(member.value, Landmark):
        return False
    return any(other != subject and _d228_arm(R, subject, other)
               and any(anatomy.compatible(member.value, place) for place in places_named(R, other))
               and every_place_control_rejected(R, subject, other) for other in R.events)


def _how(label) -> str | None:
    """The 9.4 weakening the label's last segment names: one of HOWS, or 'deleted'; None for a pair control made not
    rejected or a completeness claim made unresolved (their ``what`` is a key or a session, not a fact)."""
    last = label.split('; ')[-1]
    return next((how for how in ('deleted',) + HOWS + ERASING if last.startswith(how + ' ')), None)


def reweakened(label, what, R):
    """The FactSet the label's last weakening made of ``R`` - the fact ``what`` names weakened as the label says, or the
    member deleted - rebuilt as ``weakenings`` builds it; None for a pair control or a completeness claim."""
    how = _how(label)
    if how is None or not isinstance(what, tuple) or len(what) != 4:
        return None
    subject, attribute, position, found = what
    name = TABLES[subject.family if subject is not None else None]
    attributes = R.encounter if subject is None else getattr(R, name)[subject]
    members = attributes[attribute]
    if members[position] != found:
        raise ValueError(f'{label}: {found} is not member {position} of {attribute.value}')
    if how in ERASING:
        new = erased_fact(found, how, another_value(found, subject.family if subject is not None else None, attribute,
                                                    R))
    else:
        new = None if how == 'deleted' else _weakened_fact(found, how)
    changed = members[:position] + ((() if how == 'deleted' else (new,))) + members[position + 1:]
    return _with(R, name, subject, {**attributes, attribute: changed})


def weakened_state(label, what, R):
    """The FactSet the label's last weakening made of ``R``: a fact weakened or a member deleted (``reweakened``), a pair
    control made not rejected, a completeness claim made unresolved - as ``weakenings`` builds each."""
    last = label.split('; ')[-1]
    if last.startswith('pair control '):
        return replace(R, pair_controls={**R.pair_controls, what: False})
    if last.startswith('completeness '):
        return replace(R, completeness={**R.completeness, what: Res.UNRESOLVED})
    return reweakened(label, what, R)


def _inherited_statement(R, event) -> bool:
    """An act of another date or performer - its status established and not negated - whose other date or performer
    (the fact that makes it a statement: pairing.is_statement) is inherited from a section: DECISIONS D262's "inherited
    act". The performer row reads only an event's own performer (D188; D228: DQ2 as built), so such an act holds the
    team's act of its kind until a pair control sets them apart; with its own other performer the row sets them apart."""
    status = F.fact(R, event, A.STATUS)
    if not F.established(status) or status.result is Res.NEGATED:
        return False
    return ((P.other_performer(R, event) and F.fact(R, event, A.PERFORMER).inherited_from is not None)
            or (P.other_date(R, event) and F.fact(R, event, A.DATE_RELATION).inherited_from is not None))


def _held_pairs(R, statement) -> list:
    """The acts ``statement`` pairs with in ``R`` (engine/pairing), each held by the pair: its relation not
    INDEPENDENT."""
    return [act_ for act_ in R.events if P.paired(R, statement, act_)
            and P.relation(R, statement, act_).relation is not P.Relation.INDEPENDENT]


# D262's D228_STATUS weakens the status "to unresolved"; the class it names (test_pairing's D228_STATUS) weakens it to
# unresolved or to a doubt that keeps the value (unknown); and DECISIONS D264 (6a's Q7, option (a); refute-6a-r1 F5) adds
# the conflict doubt: a CONTRADICTED status leaves the act's performance unestablished as UNRESOLVED and UNKNOWN do, D228's
# arm reads the three alike, and D262_STATUS names the three results
D228_STATUS_RESULTS = (Res.UNRESOLVED, Res.UNKNOWN, Res.CONTRADICTED)


def _d228_status_shape(label, what, code, R, results) -> bool:
    """9.4's weakening of the STATUS of an inherited act of another date or performer (``_inherited_statement``) to a
    status whose result is one of ``results`` moves it into D228's arm (an act-filed possible statement, set apart by
    its own target without pair controls), which sets apart a pair it held, with no pair control D228's arm reads
    between the two left unrejected (test_pairing.unrejected_read: a place control asked of either, a lesion control
    about the other's lesion; D238: an unrejected one holds, a missing one is not required)."""
    if _how(label) not in HOWS or not isinstance(what, tuple) or len(what) != 4 or what[1] is not A.STATUS:
        return False
    subject = what[0]
    if getattr(subject, 'family', None) is not IdFamily.EVENT or not _inherited_statement(R, subject):
        return False
    weak = reweakened(label, what, R)
    if F.fact(weak, subject, A.STATUS).result not in results:
        return False
    in_arm = not P.filed_as_statement(weak, subject) and P.possible(weak, subject)  # D228's arm, after the weakening
    return in_arm and any(P.paired(weak, subject, other)
                          and P.relation(weak, subject, other).relation is P.Relation.INDEPENDENT
                          and not TPAIR.unrejected_read(weak, subject, other)
                          and every_place_control_rejected(R, subject, other) for other in _held_pairs(R, subject))


def _d228_status_weakening(label, what, code, R, transition=None) -> bool:
    """DECISIONS D262 (repair r3d's R3D-ST, option (a); 6a's Q1) with D264 (6a's Q7, option (a)): D228_STATUS -
    ``_d228_status_shape`` for a status weakened to unresolved (D262's words), to a doubt that keeps its value, stated or
    unclear (unknown: the weakenings of test_pairing's D228_STATUS, the class D262 names), or to a conflict doubt (a
    contradicted status, refute-6a-r1 F5: D264 reads it as the other two, the act's performance left unestablished) -
    D228_STATUS_RESULTS - accepted "as case (b) is" (D245) under D228 and D238. Nothing else: an act of today's team, an
    act of another performer stated in its own sentence (never held: the performer row sets it apart), another
    attribute."""
    return _d228_status_shape(label, what, code, R, D228_STATUS_RESULTS)


def _which_pairs_corner(label, what, code, R, transition=None) -> bool:
    """DECISIONS D228 ("DQ2 stays as built", 3d's Q4 - one corner seen from two sides, 3d-2's NOTES): 9.4's weakening of
    the inherited other PERFORMER or DATE RELATION that makes an act of established status a statement
    (``_inherited_statement``) takes it out of 4.5's "which pairs" altogether, so the pair it held is gone. 3d's Q4 as
    built: "literal; P-MONO's generator leaves that weakening out, named" (test_pairing's generator skips it, its
    question Q4); here the weakening is made, and its release named. Nothing else: the act's status weakened (D262's
    D228_STATUS), an act still a statement after the weakening, an act of the team."""
    if _how(label) not in HOWS or not isinstance(what, tuple) or len(what) != 4:
        return False
    subject, attribute = what[0], what[1]
    if getattr(subject, 'family', None) is not IdFamily.EVENT or not _inherited_statement(R, subject):
        return False
    made_by = ((A.PERFORMER,) if P.other_performer(R, subject) else ()) + (
        (A.DATE_RELATION,) if P.other_date(R, subject) else ())
    if attribute not in made_by or F.fact(R, subject, attribute).inherited_from is None:
        return False
    weak = reweakened(label, what, R)
    return not P.is_statement(weak, subject) and bool(_held_pairs(R, subject))


def left_by_support(code, R, act_) -> bool:
    """``act_`` supports ``code`` in no requirement group of it in ``R``: in each group it is no candidate, or its
    support (engine/evaluate.support, rows 1-8) is not met - it left the supporting acts by its support, never by D240's
    site fit (which drops an act whose support is met)."""
    from studio.interpretation.engine import evaluate

    groups = engine_catalogue.requirements(engine_catalogue.code_link(code))
    return bool(groups) and all(act_ not in evaluate.candidates(R, group)
                                or not evaluate.support(code, group, R, act_).met for group in groups)


def _support_reads(code, R, act_) -> list:
    """Every reading of ``act_`` evaluate makes for ``code`` in ``R``: for each requirement group it is a candidate of,
    its support rows (engine/evaluate.support: 4.3 rows 1-8, the E/M encounter, YIELD) and the code-specific rows
    (engine/evaluate.code_rows: TECH, SITE, ...), as one tuple per group."""
    from studio.interpretation.engine import evaluate

    groups = engine_catalogue.requirements(engine_catalogue.code_link(code))
    return [evaluate.support(code, group, R, act_).rows + evaluate.code_rows(code, group, R, act_)
            for group in groups if act_ in evaluate.candidates(R, group)]


def addon_row_met(code, R, assessment) -> bool:
    """engine/assess's ADDON row of the add-on ``code`` over ``R`` (DECISIONS D294 RD-2), read apart from the engine's
    held facts: one of its primaries (engine/assess.addon_hold, the function assess's row calls) among the codes
    ``assessment`` proposed is counted - admitted by R1, not excluded by engine/evaluate over ``R`` with its kept spans,
    and no statement able to exclude it (engine/assess.addon_uncounted). False without the proposals (fail-closed)."""
    from studio.interpretation.engine import evaluate

    if assessment is None:
        return False
    counted = set()
    for found in assessment.codes:
        if found.code == code or found.evaluation is None:  # R1 refused it: never counted
            continue
        kept, runs = found.evidence.kept, found.evidence.runs
        if evaluate.decide(found.code, kept, R, kept_words=runs).exclusion is not None:
            continue
        if AS.addon_uncounted(found.code, kept, R, runs):
            continue
        counted.add(found.code)
    return AS.addon_hold(code, counted, ()) is None


def every_row_met(code, R, *, ready=True, assessment=None) -> tuple:
    """DECISIONS D264's rule for every named release: every act still supporting ``code`` in ``R`` - engine/evaluate's
    supporting acts after the weakening (E*, D240's site fit applied) - meets every row of evaluate's reading: in some
    requirement group it is a candidate of, its support rows and code-specific rows are all T (``_support_reads``, read
    act by act through evaluate.support and code_rows, never from the engine's own held facts or outcome); and a READY
    release (``ready``) has a supporting act. An act a candidate of no group of the code (43276's two-act pair is read by
    its parts' groups) fails, fail-closed. And a READY add-on meets assess's ADDON row too (DECISIONS D294 RD-2:
    ``addon_row_met`` over the codes ``assessment`` - the assessment of ``R`` - proposed beside it; without it an add-on
    fails, fail-closed). Returns (met, {act or 'ADDON': the rows it fails} or the reason)."""
    from studio.interpretation.engine import evaluate

    supporting = evaluate.decide(code, (), R).supporting
    if ready and not supporting:
        return False, 'READY with no supporting act'
    failing = {}
    for act_ in supporting:
        reads = _support_reads(code, R, act_)
        if not any(all(row.truth is evaluate.Truth.T for row in rows) for rows in reads):
            failing[act_] = sorted({str(row.requirement.value) for rows in reads for row in rows
                                    if row.truth is not evaluate.Truth.T}) or ['a candidate of no group of the code']
    if ready and AS.primaries(code) and not addon_row_met(code, R, assessment):
        failing['ADDON'] = ['its primary counted (engine/assess.addon_hold over the codes proposed beside it)']
    return not failing, failing


def fails_only_clean(code, R, act_) -> bool:
    """``act_`` fails EXACTLY its clean row (4.3 row 8, SUP_CLEAN: a relation of a paired statement, or an unlisted
    denial or doubt pairing with it) among its support rows, in every requirement group of ``code`` it is a candidate of
    in ``R`` - and it is a candidate of one (D264_CLEAN's leaving act)."""
    from studio.interpretation.engine import evaluate

    groups = engine_catalogue.requirements(engine_catalogue.code_link(code))
    supports = [evaluate.support(code, group, R, act_) for group in groups if act_ in evaluate.candidates(R, group)]
    return bool(supports) and all([row.requirement for row in found.rows if row.truth is not evaluate.Truth.T]
                                  == [RQ.Requirement.SUP_CLEAN] for found in supports)


def _released_by_evaluate(code, R, weak):
    """(the acts that left ``code``'s supporting acts, evaluate's Evaluation of ``R``) when the weakening ``R`` -> ``weak``
    makes the code READY by evaluate's reading - the acts left each supporting before, none newly (no act newly supports
    it), and evaluate holding nothing and excluding nothing after - else None."""
    from studio.interpretation.engine import evaluate

    before, after = evaluate.decide(code, (), R), evaluate.decide(code, (), weak)
    left = [act_ for act_ in before.supporting if act_ not in after.supporting]
    remaining = set(after.supporting)
    if not remaining or not remaining <= set(before.supporting) or after.held_facts or after.exclusion is not None:
        return None
    return left, before


def _site_fit_weakening(label, what, code, R, transition=None) -> bool:
    """DECISIONS D262 (r4a's QM, its request R7 to 6a) as D264 narrows it (6a's Q4, refute-6a-r2 F2, option (c)): D240's
    site fit under weakening, 4.4's release class it extends (r4a: "an act failing only a code row moves out of E* when
    weakened"; engine/evaluate's E*: positive candidates are not read when a group is met), bound to what D262 accepted -
    ONE OF THE LEAVING ACT'S OWN SUPPORT ROWS WEAKENED: the 9.4 weakening is of a support fact of the act S (its kind,
    status, session, date, performer or entry: SUPPORT_ATTRIBUTES), S is the one act that leaves the code's supporting
    acts, and it leaves BY ITS SUPPORT (``left_by_support``), while it held the code only by failing a code row (every
    held fact before on S, S supporting before); the acts left make the code READY: each a supporting act before the
    weakening, no held fact and no exclusion after (``_released_by_evaluate``). Read through engine/evaluate over the
    FactSet before and after the weakening (``weakened_state``). Nothing else: another object's weakening that puts a
    relation on S's clean row (F2's states, D264_CLEAN: ``_clean_row_release``), S dropped by D240's site fit with its
    support met (D264_SITE), a code no act held by a code row, a release onto an act that did not support it before."""
    if _how(label) not in HOWS or not isinstance(what, tuple) or len(what) != 4 or what[1] not in SUPPORT_ATTRIBUTES:
        return False
    subject = what[0]
    if getattr(subject, 'family', None) is not IdFamily.EVENT:
        return False
    weak = weakened_state(label, what, R)
    released = _released_by_evaluate(code, R, weak)
    if released is None:
        return False
    left, before = released
    return (left == [subject] and bool(before.held_facts) and all(held.subject == subject for held in before.held_facts)
            and left_by_support(code, weak, subject))


def _clean_row_release(label, what, code, R, transition=None) -> bool:
    """DECISIONS D264 (6a's Q4, refute-6a-r2 F2, option (c) then named): D264_CLEAN - "the states the narrowed binding no
    longer accepts", a class of their own: what QM's widened binding of repair 6a-2 took (a 9.4 weakening, of any kind,
    moves acts out of the code's supporting acts by their support, while they held the code only by failing a code row -
    every held fact before on an act that left, each such act supporting before - and the acts left make the code READY:
    each a supporting act before, no held fact and no exclusion after, ``_released_by_evaluate``) and QM's narrowed binding
    does not (``_site_fit_weakening``: the one leaving act's own support fact weakened), where an act leaves failing
    EXACTLY its clean row (``fails_only_clean``: 4.3 row 8, every other support row met: F2's "the leaving act fails
    exactly SUP_CLEAN") and every other leaving act is the weakened act itself, out by the support fact weakened (QM's
    mechanism beside it). F2's states: beside an unrejected place control, E4's status weakened makes E4 a possible
    statement that holds E1; at depth 2, a pair control made not rejected, or E1's only place deleted or weakened, beside
    E4's weakened status; and E4's place no longer established, then E1's status weakened: E1 out by its status, E4 held
    by E1 as a possible statement. Nothing else: QM's own states, an act leaving by any other row (or dropped by D240's
    site fit, D264_SITE's), a release onto an act that did not support it before. Its count on r4a QM's fixture is pinned
    (DRAWN_RELEASES: the drawn-verdict census)."""
    if _site_fit_weakening(label, what, code, R):
        return False
    weak = weakened_state(label, what, R)
    if weak is None:
        return False
    released = _released_by_evaluate(code, R, weak)
    if released is None:
        return False
    left, before = released
    own = (what[0] if _how(label) in HOWS and isinstance(what, tuple) and len(what) == 4
           and what[1] in SUPPORT_ATTRIBUTES else None)
    clean = [act_ for act_ in left if fails_only_clean(code, weak, act_)]
    return (bool(clean) and bool(before.held_facts) and all(held.subject in left for held in before.held_facts)
            and all(act_ in clean or (act_ == own and left_by_support(code, weak, act_)) for act_ in left))


# the codes with a SITE row (D29: the site-specific dilation codes), read from the catalogue and the requirements table:
# "a code's SITE class" (D264_SITE) is one of theirs
SITE_CODES = tuple(sorted(str(code) for code in engine_catalogue.CODES if Tag.SITE in RQ.spec(str(code)).tags))


def site_truths(code, R, act_) -> list:
    """engine/evaluate's SITE row of ``act_`` for ``code`` (D29) in each requirement group ``act_`` is a candidate of."""
    from studio.interpretation.engine import evaluate

    groups = engine_catalogue.requirements(engine_catalogue.code_link(code))
    return [row.truth for group in groups if act_ in evaluate.candidates(R, group)
            for row in evaluate.code_rows(code, group, R, act_) if row.requirement is Tag.SITE]


def site_witnesses(code, R, act_) -> set:
    """The held facts the SITE row of ``act_`` for ``code`` raises in ``R``, as (fact, attribute, subject)."""
    from studio.interpretation.engine import evaluate

    groups = engine_catalogue.requirements(engine_catalogue.code_link(code))
    return {(held.fact, held.attribute, held.subject) for group in groups if act_ in evaluate.candidates(R, group)
            for row in evaluate.code_rows(code, group, R, act_) if row.requirement is Tag.SITE
            for held in row.witnesses}


def set_outside(code, before, after, act_) -> bool:
    """D264_SITE's "sets the act outside a code's SITE class": ``act_``'s SITE row for ``code`` open (U) in ``before`` and
    failing (F: D29, its target established outside the class - combination.site_outside's reading too) in ``after``."""
    from studio.interpretation.engine import evaluate

    was, now = site_truths(code, before, act_), site_truths(code, after, act_)
    return bool(was) and bool(now) and all(truth is evaluate.Truth.U for truth in was) and all(
        truth is evaluate.Truth.F for truth in now)


def _target_lesion(R, event):
    """The lesion ``event`` targets as evaluate's SITE row reads it (evaluate._places_of: its target lesion supported)."""
    found = F.fact(R, event, A.TARGET_LESION)
    return found.value if found.result is Res.SUPPORTED and isinstance(found.value, Id) else None


def _site_deletion(label, what, R):
    """D264_SITE's weakening: 9.4's deletion of an ESTABLISHED member of an act's target.places, or of a lesion's places
    (the places of every act whose target lesion it is, as evaluate's SITE row and combination.site_outside read them),
    that sets one of the acts whose places it shortened outside a code's SITE class (``set_outside`` for one of
    SITE_CODES). (the acts whose places it shortened, the weakened FactSet), or None for any other weakening."""
    if _how(label) != 'deleted' or not isinstance(what, tuple) or len(what) != 4 or what[3].result not in ESTABLISHED:
        return None
    subject, attribute = what[0], what[1]
    family = getattr(subject, 'family', None)
    if attribute is A.TARGET_PLACES and family is IdFamily.EVENT:
        shortened = [subject]
    elif attribute is A.PLACES and family is IdFamily.LESION:
        shortened = [event for event in R.events if _target_lesion(R, event) == subject]
    else:
        return None
    weak = weakened_state(label, what, R)
    if not any(set_outside(site_code, R, weak, act_) for act_ in shortened for site_code in SITE_CODES):
        return None
    return shortened, weak


def _rests_on(code, R, act_, outside) -> bool:
    """D118's claim resting on an act set outside (repair r4d's R2: "may drop that act, and D118's claims resting on it,
    from the code's claims"): ``code`` is a technique code, ``act_`` is no act it may account for in ``R`` (only D118's
    arm claimed it) and it was on one stricture with an act of ``outside`` (combination.one_stricture)."""
    from studio.interpretation.engine import combination

    return (engine_catalogue.code_link(code).technique is not None and not combination.may_account_for(code, R, act_)
            and any(combination.one_stricture(R, mine, act_) for mine in outside if mine != act_))


def _site_class_shrink(label, what, code, lost, R, transition=None) -> bool:
    """DECISIONS D264 (6a's Q6, option (a)): D264_SITE's shrunk claims ("check accepts the shrunk claims under that
    name"): the weakening is D264_SITE's deletion (``_site_deletion``) and every act ``lost`` from ``code``'s claims is an
    act whose places it shortened and set outside ``code``'s SITE class (combination's D29 site fit drops it), or a claim
    of D118 resting on such an act (``_rests_on``). Nothing else: an act lost from the claims whose own places the
    deletion did not set outside the code's class, a lost act that rested on nothing set outside."""
    found = _site_deletion(label, what, R)
    if found is None or not lost:
        return False
    shortened, weak = found
    outside = [act_ for act_ in shortened if set_outside(code, R, weak, act_)]
    return bool(outside) and all(act_ in outside or _rests_on(code, R, act_, outside) for act_ in lost)


def _site_class_release(label, what, code, R, transition=None) -> bool:
    """DECISIONS D264 (6a's Q6, option (a); D240's named release - its preamble: "the installed reading is kept and the
    exception is named in 6a's property tests"; w7r's O13 and repair r4d's R2 built by it): D264_SITE. D264_SITE's
    deletion (``_site_deletion``: a deleted member of an act's target.places, or of its target lesion's places, that sets
    the act outside a code's SITE class) releases ``code`` through D29's site fit, read over engine/evaluate and the
    assessments before and after the weakening (``transition``):
    - every act that left the code's supporting acts left BY ITS SITE ROW (evaluate's site fit, D240: its support met,
      its SITE row failing after), no act newly supports it, and evaluate holds nothing and excludes nothing after
      (``_released_by_evaluate``);
    - every hold the code had before is the site fit's: a held fact on an act that left by its SITE row; a witness of
      the SITE row of an act whose places the deletion shortened (the short list read as its site: D240's installed
      reading); or the competition (competing_codes) with each code it shared an act with, those claims sharing none
      after, every shared act having left one of the two claims as D264_SITE's shrunk claims leave
      (``_site_class_shrink``: combination's site fit, "and so a competition" - repair r4d's R2) - so that code's
      rival is released too;
    - and an act is DROPPED by the site fit - one leaving the code's supporting acts by its SITE row, or a claim of a
      competition the code was held by (the routing D264 states: "the dropped act leaves by the SITE row").
    Nothing else: a deletion that sets no act outside a SITE class (a short list read inside one only, or a place of no
    class), a release with no act dropped (a short list read as an act's site within the code's class, and nothing
    else, 6a's question QS1), an act leaving by its support or by a pairing relation, an act newly supporting, a hold of
    any other kind, a release with no ``transition`` to read."""
    from studio.interpretation.engine import combination, evaluate

    found = _site_deletion(label, what, R)
    if found is None or transition is None:
        return False
    shortened, weak = found
    before_a, after_a = transition
    item = next((found_ for found_ in before_a.codes if found_.code == code), None)
    released = _released_by_evaluate(code, R, weak)
    if item is None or released is None:
        return False
    left, _before = released
    if not all(not left_by_support(code, weak, act_) and site_truths(code, weak, act_)
               and all(truth is evaluate.Truth.F for truth in site_truths(code, weak, act_)) for act_ in left):
        return False
    shortened_sites = {key for act_ in shortened for key in site_witnesses(code, R, act_)}
    claims_before, claims_after = claims(before_a), claims(after_a)

    def competition_ended(rival):
        mine, theirs = claims_before.get(code, frozenset()), claims_before.get(rival, frozenset())
        if not mine & theirs or rival not in claims_after or claims_after.get(code, frozenset()) & claims_after[rival]:
            return False
        return all((act_ not in claims_after.get(code, frozenset())
                    and _site_class_shrink(label, what, code, frozenset({act_}), R))
                   or (act_ not in claims_after[rival] and _site_class_shrink(label, what, rival, frozenset({act_}), R))
                   for act_ in mine & theirs)

    through_competition = False
    for held in item.held_facts:
        if held.subject in left or (held.fact, held.attribute, held.subject) in shortened_sites:
            continue
        if held.cause == combination.COMPETING_CAUSE and item.competes and all(
                competition_ended(rival) for rival in item.competes):
            through_competition = True
            continue
        return False
    return bool(left) or through_competition  # "the dropped act leaves by the SITE row": E* or a claim, never neither


def _d211_production_deletion(label, what, code, R, transition=None) -> bool:
    """DECISIONS D262 (repair r3d's R3D-NC, option (a): "a named release, as Q1 (b) is"): D238's production shape - D245's
    case (b) (``_d228_compatible_deletion``: beside an act-filed possible statement, a deleted established target.places
    member compatible with the other's place) for a pair claims never makes a pair control for (D211: two acts whose
    kinds no rule of identity by place reads together, contract/claims._place_identity_pair) with no place pair control
    between the two at all. D1's production filing omits the place; D238 reads only the controls that exist, so nothing
    holds the pair. A named release, measured at D1-D3. Where controls exist between the two (every one rejected), the
    release is D245's case (b) alone."""
    if not _d228_compatible_deletion(label, what, code, R):
        return False
    subject, member = _deleted_place(label, what)

    def kind(event):
        found = F.fact(R, event, A.KIND)
        return found.value if found.result is Res.SUPPORTED and isinstance(found.value, Kind) else None

    return any(other != subject and _d228_arm(R, subject, other)
               and any(anatomy.compatible(member.value, place) for place in places_named(R, other))
               and not place_controls_between(R, subject, other)
               and not CL._place_identity_pair(kind(subject), kind(other)) for other in R.events)


D218 = 'DECISIONS D218'
D245_Q2 = "DECISIONS D245 (repair r2d-2's Q2, option (a))"
D245_B = "DECISIONS D245 with D228 and D238 (repair r3d's Q1, case (b))"
D262_STATUS = "DECISIONS D262: D228_STATUS (repair r3d's R3D-ST, option (a); 6a's Q1; D264's Q7, a contradicted status)"
D262_QM = "DECISIONS D262: r4a's QM (D240's site fit under weakening; r4a's request R7), as D264 narrows it (6a's Q4)"
D262_NC = "DECISIONS D262: repair r3d's R3D-NC (D238's production shape, measured at D1-D3)"
D228_DQ2 = "DECISIONS D228: DQ2 stays as built (3d's Q4, the which-pairs corner)"
D264_CLEAN = "DECISIONS D264: D264_CLEAN (6a's Q4; refute-6a-r2 F2's states, the leaving act failing only its clean row)"
D264_SITE = "DECISIONS D264: D264_SITE with D240 (6a's Q6; D29's site fit read from a deleted place member; w7r's O13)"
D293_ERASE = ("DECISIONS D293: Q-ERASE option (a) - a value-erasing contradiction of a fact whose classic weakening a "
              "named release takes, accepted under that class and held to D264's every-row rule")
ACCEPTED_RELEASES = (
    ('the deleted beyond point of a jejunal enteroscopy', D218, _jejunal_beyond_deletion),
    ('a deleted place member that overlapped the other object\'s place, every control between them rejected', D245_Q2,
     _overlap_deletion),
    ("D238's production shape: a deleted place member compatible with the other's place beside an act-filed possible "
     'statement, a pair claims never controls and no control between them', D262_NC, _d211_production_deletion),
    ("a deleted place member compatible with the other's place beside an act-filed possible statement, no control "
     'between them unrejected', D245_B, _d228_compatible_deletion),
    ("an inherited act of another date or performer moved into D228's arm by its status weakened to unresolved, a doubt "
     'that keeps its value or a conflict doubt, no control between the two unrejected', D262_STATUS,
     _d228_status_weakening),
    ("an inherited other date or performer weakened, taking the act out of 4.5's which pairs", D228_DQ2,
     _which_pairs_corner),
    ("an act out of the supporting acts by one of its own support facts weakened, which it held by a code row only; the "
     'acts left, each supporting before, meet every row', D262_QM, _site_fit_weakening),
    ("acts out of the supporting acts, one failing only its clean row and any other the weakened act out by that support "
     "fact (not QM's one act), which they held by a code row only; the acts left, each supporting before", D264_CLEAN,
     _clean_row_release),
    ("a deleted member of an act's target.places or of its target lesion's places setting the act outside a code's SITE "
     'class: the act leaves by its SITE row, or a claim and so a competition', D264_SITE, _site_class_release),
)
# DECISIONS D264: every named release is accepted only when every act still supporting the released code meets every row
# of evaluate's reading after the weakening (``every_row_met``) - D264 names D262_STATUS, D262_QM, D262_NC, D228_DQ2,
# D264_SITE and D264_CLEAN; D218's and D245's two are held to it too, a named release never being a false READY
ROW_RULED = frozenset(ruling for _description, ruling, _predicate in ACCEPTED_RELEASES)
# The shrunk claims a ruling accepts (D264: "`check` accepts the shrunk claims under that name"), each by its predicate
ACCEPTED_SHRINKS = (
    ("the claims dropping an act a deleted member of its target.places or of its target lesion's places set outside the "
     "code's SITE class (or a claim of D118 resting on it)", D264_SITE, _site_class_shrink),
)
# The releases a design question governs that the owner has not ruled: never accepted. P-MONO's tests route each to
# OpenQuestionsTests.test_no_release_waits_on_an_open_question, which fails naming its question until the owner rules -
# (a) accepted: the entry moves to ACCEPTED_RELEASES under its ruling; (b) the engine repaired: the release is gone - so
# the other tests keep guarding every other release (DECISIONS D245: "A release no ruling names still fails"). EMPTY:
# DECISIONS D264 ruled both entries it held (refute-6a-r1 F3, 6a's Q6: D264_SITE; F5, Q7: D262_STATUS), and DECISIONS
# D293 the one AMENDMENT-2's build added (step f3e's Q-ERASE: the value-erasing contradictions of a fact whose classic
# weakening a ruling names, option (a), D293_ERASE); it stays as the guard for the next unruled release - an entry is
# (description, question, predicate(label, what, code, R)), and its predicate also routes a shrunk claim (the claim's
# code in place of a released one).


def _classic_label(label: str) -> str:
    """The label of the classic 9.4 weakening ('unresolved') of the fact a value-erasing label names: the same subject,
    attribute and position."""
    head, _sep, last = label.rpartition('; ')
    how = _how(last) or ''
    return (head + '; ' if head else '') + 'unresolved' + last[len(how):]


def _erasing_in_a_named_class(label, what, code, R, transition=None) -> bool:
    """D293_ERASE's states: a value-erasing contradiction (ERASING) whose release of ``code`` a ruled shape takes - the
    fact's classic weakening ('unresolved') named by a ruled predicate (D262_QM's site-fit weakening, D262_STATUS's
    status weakening, D228_DQ2's which-pairs corner), or the erasing state itself taken by a predicate that reads any
    9.4 weakening (D264_CLEAN's clean-row release). DECISIONS D293 (Q-ERASE option (a)) accepts them under D293_ERASE,
    held to D264's every-row rule (``PMonoTests.check``: ROW_RULED); the other rulings' predicates only, never this
    entry's own."""
    if _how(label) not in ERASING or not isinstance(what, tuple) or len(what) != 4:
        return False
    classic = _classic_label(label)
    return any(predicate(classic, what, code, R) or predicate(label, what, code, R, transition)
               for _description, ruling, predicate in ACCEPTED_RELEASES if ruling != D293_ERASE)


ACCEPTED_RELEASES = (*ACCEPTED_RELEASES,
                     ("a value-erasing contradiction (pass 1's own contradiction of a fact's value and another, or an "
                      "overfilled slot) of a fact whose classic 9.4 weakening a named release takes, by the same "
                      "transition (AMENDMENT-2 4.4; step f3e's question Q-ERASE)", D293_ERASE,
                      _erasing_in_a_named_class))
ROW_RULED = frozenset(ruling for _description, ruling, _predicate in ACCEPTED_RELEASES)
OPEN_RELEASES: tuple = ()
# D293_ERASE's states under the fixtures' own verdicts, (code, label), pinned - r4a QM's fixture (43249: E1's support
# facts, as D262_QM names their classic weakening) and R3D-ST's (45380: E2's status, as D262_STATUS, and its inherited
# performer, as D228_DQ2); no other fixture's value-erasing contradiction releases
ERASING_ACCEPTED: list = [
    ('43249', 'contradiction E1 date_relation[0]'), ('43249', 'contradiction E1 entry[0]'),
    ('43249', 'contradiction E1 kind[0]'), ('43249', 'contradiction E1 performer[0]'),
    ('43249', 'contradiction E1 session[0]'), ('43249', 'contradiction E1 status[0]'),
    ('43249', 'overfilled denied E1 date_relation[0]'), ('43249', 'overfilled denied E1 performer[0]'),
    ('43249', 'overfilled denied E1 session[0]'), ('43249', 'overfilled stated E1 date_relation[0]'),
    ('43249', 'overfilled stated E1 performer[0]'), ('43249', 'overfilled stated E1 session[0]'),
    ('45380', 'contradiction E2 performer[0]'), ('45380', 'contradiction E2 status[0]'),
    ('45380', 'overfilled denied E2 performer[0]'), ('45380', 'overfilled stated E2 performer[0]')]


def _waiting(label, what, code, R) -> str | None:
    """The open question (OPEN_RELEASES) that governs the release of ``code`` under this weakening of ``R``, or None."""
    return next((question for _description, question, predicate in OPEN_RELEASES
                 if predicate(label, what, code, R)), None)


SUPPORT_ATTRIBUTES = (A.KIND, A.STATUS, A.SESSION, A.DATE_RELATION, A.PERFORMER, A.ENTRY)  # r4a QM's "SUPPORT rows"


D264_SITE_TERMS = ("DECISIONS D264 names D264_SITE only for a deleted member of an act's target.places or of its target "
                   "lesion's places that sets the act outside a code's SITE class, the code released through D29's site "
                   'fit alone - the act leaving its supporting acts by its SITE row, or a claim and so a competition - '
                   'its shrunk claims dropping only that act (or a claim of D118 resting on it)')
D264_CLEAN_TERMS = ("DECISIONS D264 names D264_CLEAN only for acts that held the code by a code row alone leaving the "
                    "supporting acts, one failing exactly its clean row after any 9.4 weakening (another event's "
                    "status, a pair control, or the leaving act's own place weakened or deleted: DECISIONS D288's "
                    'class, refute-6a-r2 F2 its measured instance, read so that two commuting weakenings give one '
                    'verdict) and any other the weakened act out by that support fact, the acts left - each supporting '
                    'before - making it READY')


def _open_question(label, what, R=None) -> str:
    """The ruling that governs a release of this weakening's shape - never an acceptance: the release still fails P-MONO,
    and the failure names the ruling (DECISIONS D245: "6a's _open_question names these rulings. A release no ruling names
    still fails."; D262's and D264's named releases, each accepted only by its own predicate). '' when no ruling or
    question names the shape."""
    deleted = _deleted_place(label, what)
    lesion_deleted = (_how(label) == 'deleted' and isinstance(what, tuple) and len(what) == 4 and what[1] is A.PLACES
                      and getattr(what[0], 'family', None) is IdFamily.LESION)
    if deleted is not None or lesion_deleted:
        member = what[3]
        if member.result not in ESTABLISHED:
            return ("DECISIONS D245 (r2d-2's Q3, option (b)): 9.4's deletion weakens an established member only - a "
                    'deleted member that was not established is no weakening, and P-MONO generates none')
        if lesion_deleted:
            return D264_SITE_TERMS
        subject = deleted[0]
        unrejected = R is not None and any(not all(place_controls_between(R, subject, other).values())
                                           for other in R.events if other != subject)
        if unrejected:
            return ("DECISIONS D220: the deleted member's unrejected pair control keeps the pair together (D245 accepts a "
                    "deleted place member's release only with every control between the two rejected); in D228's arm "
                    "D238 (built by repair r3d): the arm reads the controls that exist and an unrejected one holds; "
                    + D264_SITE_TERMS)
        return ("DECISIONS D245 accepts a deleted place member's release only as r2d-2's Q2 (it overlapped the other "
                "object's place, every control between them rejected) or as r3d's Q1 case (b) (compatible, beside an "
                "act-filed possible statement), and D262 names R3D-NC's production shape of case (b) (a pair claims "
                f"never controls, no control between them); {D264_SITE_TERMS}")
    last = label.split('; ')[-1]
    if last.startswith('pair control '):
        return D264_CLEAN_TERMS
    if not isinstance(what, tuple) or len(what) != 4 or _how(label) not in HOWS:
        return ''
    subject, attribute = what[0], what[1]
    inherited = R is not None and getattr(subject, 'family', None) is IdFamily.EVENT and _inherited_statement(R, subject)
    if attribute is A.STATUS and inherited:
        return ("DECISIONS D262 accepts D228_STATUS (repair r3d's R3D-ST, option (a); D264's Q7) - an inherited act of "
                "another date or performer moved into D228's arm by its status weakened to unresolved, unknown or "
                'contradicted - only when the arm sets the pair apart with no pair control it reads between the two left '
                'unrejected (D238: an unrejected one holds)')
    if attribute in (A.PERFORMER, A.DATE_RELATION) and inherited:
        return ("DECISIONS D228 (DQ2 as built, 3d's Q4) names the which-pairs corner only when the weakened date or "
                'performer is the inherited one that made the act a statement and the act leaves 4.5\'s which pairs')
    if attribute in SUPPORT_ATTRIBUTES and getattr(subject, 'family', None) is IdFamily.EVENT:
        return ("DECISIONS D262 accepts r4a's QM (D240's site fit under weakening), as D264 narrows it, only when the one "
                'act that leaves the supporting acts is the weakened one, by its support, it held the code by a code row '
                'alone, and the acts left - each supporting before - make it READY (no false READY)'
                + ('; ' + D264_CLEAN_TERMS if attribute is A.STATUS else ''))
    return ''


def _release(before, after) -> tuple:
    return (ready(after) - ready(before), excluded(after) - excluded(before),
            {key: acts - claims(after).get(key, frozenset()) for key, acts in claims(before).items()
             if key in claims(after) and acts - claims(after)[key]})


def _named(label, what, code, R, transition=None) -> str | None:
    """The ruling whose shape takes the release of ``code`` under the weakening (``label``, ``what``) of ``R`` - the first
    of ACCEPTED_RELEASES whose predicate holds - or None. ``transition``: the assessments before and after that weakening
    (D264_SITE reads the competition there). A value-erasing contradiction (ERASING) is named D293_ERASE when its
    release is in a ruled class (``_erasing_in_a_named_class``: DECISIONS D293, Q-ERASE option (a)) and nothing
    otherwise - never under another ruling's name, so the census counts these states apart."""
    if _how(label) in ERASING:
        return D293_ERASE if _erasing_in_a_named_class(label, what, code, R, transition) else None
    return next((ruling for _, ruling, predicate in ACCEPTED_RELEASES if predicate(label, what, code, R, transition)),
                None)


def _accepted(label, what, released, R, transition=None) -> list:
    """The ruling whose shape takes each code of ``released`` (READY or EXCLUDED newly) under the weakening (``label``,
    ``what``) of ``R`` (``_named``), None for one no ruling's shape takes. The shape alone: ``PMonoTests.check`` also holds
    each named release to D264's rule (``every_row_met``) over the state it reads."""
    return [_named(label, what, code, R, transition) for code in released]


def _accepted_shrink(label, what, code, lost, R, transition=None) -> str | None:
    """The ruling that accepts ``code``'s claims losing the acts ``lost`` under the weakening (``label``, ``what``) of
    ``R`` (ACCEPTED_SHRINKS), or None."""
    return next((ruling for _, ruling, predicate in ACCEPTED_SHRINKS
                 if predicate(label, what, code, lost, R, transition)), None)


def transition_of(R, codes, label, what):
    """The assessments before and after the weakening (``label``, ``what``) of ``R`` (``weakened_state``), for a test
    naming a release outside ``PMonoTests.check``."""
    return assessed(R, codes), assessed(weakened_state(label, what, R), codes)


def verdicts(data, R):
    """``R`` with pass 2's verdicts on its pair controls drawn (refutation 6a-r2b P1: not every control rejected): every
    one rejected but at most one, or - one draw in three - each drawn on its own (test_pairing.verdicts' shape)."""
    keys = sorted(R.pair_controls, key=repr)
    if not keys:
        return R
    if data.draw(st.integers(0, 2), label='verdicts drawn each') == 0:
        drawn = {key: data.draw(st.booleans(), label=f'rejected {key}') for key in keys}
    else:
        unrejected = data.draw(st.sampled_from(keys + [None]), label='unrejected')
        drawn = {key: key != unrejected for key in keys}
    return replace(R, pair_controls={**R.pair_controls, **drawn})


def random_states(data):
    """P-MONO's random settled FactSets: a fixture, pass 2's verdicts on its pair controls drawn (``verdicts``), and two
    weakenings drawn one after the other: ((name, base, codes), (label, what, once), (label2, what2, twice) or None)."""
    name, R, codes = data.draw(st.sampled_from(fixtures()), label='fixture')
    base = verdicts(data, R)
    first = list(weakenings(base))
    label, once, what = data.draw(st.sampled_from(first), label='first')
    second = list(weakenings(once))
    if not second:
        return (name, base, codes), (label, what, once), None
    label2, twice, what2 = data.draw(st.sampled_from(second), label='second')
    return (name, base, codes), (label, what, once), (label2, what2, twice)


class PMonoTests(SimpleTestCase):
    """9.4 P-MONO over the engine as assembled (module docstring)."""

    def check(self, base, after, label, what, R, by=None, waiting=None, claims_from=None, shrinks=None):
        """P-MONO between ``base`` and ``after``: no code newly READY or EXCLUDED but those a ruling accepts, no claim
        shrunk but as a ruling accepts; returns the rulings that accepted a release. The weakening (``label``, ``what``)
        was applied to ``R``. ``by``: for a twice-weakened state, each released code's own weakening (code -> (label,
        what, R) or (label, what, R, (the assessment before it, the one after it)): the weakening that released it,
        refutation 6a-r2b P3; D264_SITE reads the competition in that pair of assessments and takes nothing without
        it); ``claims_from``: the assessment the claims are compared from (the once-weakened one, for the second
        weakening's own shrink; ``base`` by default) - with ``after``, the pair a code the last weakening released is
        read in. DECISIONS D264: a release a ruling's shape takes is accepted only when every act still supporting the
        released code meets every row of evaluate's reading after the weakening (``every_row_met``, over ``R`` with the
        last weakening applied - the state ``after`` reads); one that fails it fails here, its ruling and the rows named
        ("a routed state that fails this ... fails P-MONO"). A shrunk claim a ruling accepts (ACCEPTED_SHRINKS:
        D264_SITE's) passes, and is appended to ``shrinks`` (a list, when given) as (code, ruling, label). A release or a
        shrunk claim an open question governs (OPEN_RELEASES; empty since D293) is never accepted: given ``waiting`` (a
        list), it is appended there as (code, question, label) for OpenQuestionsTests to fail on - and so DISCARDED by
        this check, which a caller passing ``waiting`` says in a comment; without it, it fails here, its question
        named."""
        grown_ready, grown_excluded, _shrunk = _release(base, after)
        claims_base = base if claims_from is None else claims_from
        shrunk = _release(claims_base, after)[2]
        released = sorted(grown_ready | grown_excluded)
        weakening = {}
        for code in released:
            found = (by or {}).get(code, (label, what, R, (claims_base, after)))
            weakening[code] = tuple(found) if len(found) == 4 else (*found, None)
        rulings = [_named(weakening[code][0], weakening[code][1], code, weakening[code][2], weakening[code][3])
                   for code in released]
        unaccepted = [code for code, ruling in zip(released, rulings) if ruling is None]
        questions = {code: _waiting(weakening[code][0], weakening[code][1], code, weakening[code][2])
                     for code in unaccepted}
        if waiting is not None:
            waiting += [(code, questions[code], weakening[code][0]) for code in unaccepted if questions[code]]
            unaccepted = [code for code in unaccepted if not questions[code]]
        named = {code: questions[code] or _open_question(*weakening[code][:3])
                 or 'no ruling accepts it, and no open question names it' for code in unaccepted}
        self.assertEqual(unaccepted, [], (label, 'READY grew' if grown_ready else 'EXCLUDED grew', named))
        final = weakened_state(label, what, R)
        if final is None and released:
            raise ValueError(f'{label}: no FactSet to hold the release to D264\'s rule')
        rows = {code: (ruling, every_row_met(code, final, ready=code in grown_ready, assessment=after))
                for code, ruling in zip(released, rulings) if ruling in ROW_RULED}
        failed = {code: (ruling, found[1]) for code, (ruling, found) in rows.items() if not found[0]}
        self.assertEqual(failed, {}, (label, "a named release fails DECISIONS D264's rule - an act still supporting the "
                                             "released code fails a row of evaluate's reading (a false READY)", failed))
        accepted = {code: _accepted_shrink(label, what, code, acts, R, (claims_base, after))
                    for code, acts in shrunk.items()}
        if shrinks is not None:
            shrinks += [(code, ruling, label) for code, ruling in sorted(accepted.items()) if ruling]
        shrunk = {code: acts for code, acts in shrunk.items() if not accepted[code]}
        held = {code: _waiting(label, what, code, R) for code in shrunk}
        if waiting is not None:
            waiting += [(code, held[code], f'{label} (a claim shrank)') for code in shrunk if held[code]]
            shrunk = {code: acts for code, acts in shrunk.items() if not held[code]}
        self.assertEqual(shrunk, {}, (label, 'a claim shrank', {code: held[code] or D264_SITE_TERMS for code in shrunk}))
        return [ruling for ruling in rulings if ruling]

    def test_every_single_weakening_of_every_fixture(self):
        counted, named, waiting, shrinks, erasing = 0, [], [], [], []
        for name, R, codes in fixtures():
            base = assessed(R, codes)
            for label, changed, what in weakenings(R):
                with self.subTest(fixture=name, weakening=label):
                    counted += 1
                    after = assessed(changed, codes)
                    named += self.check(base, after, label, what, R, waiting=waiting, shrinks=shrinks)
                    grown_ready, grown_excluded, _shrunk = _release(base, after)
                    erasing += [(code, label) for code in sorted(grown_ready | grown_excluded)
                                if _named(label, what, code, R, (base, after)) == D293_ERASE]
        self.assertGreater(counted, 2500)
        # every accepted release met, each named by its own ruling: D218's fixture, r2d-2's Q2 shape, r3d's case (b) where
        # pair controls exist, and DECISIONS D262's and D264's - R3D-NC's production shape (the D228 fixture's two
        # biopsies and the doubted snare), D228_STATUS's four status weakenings of R3D-ST's inherited act (unresolved, two
        # doubts that keep the value, and the conflict doubt D264's Q7 adds; beside them D228's which-pairs corner, its
        # inherited performer's four), r4a QM's 24 (E1's six support facts, four ways each, the narrowed binding's own;
        # test_evaluate's weakening, two ways, counted r4a's 12) and D264_SITE's four (43249 and 43245 released when the
        # dilation's distal esophagus is deleted, from its own places and from its target lesion's). D264_CLEAN is met
        # only under drawn verdicts (an unrejected control): DRAWN_RELEASES pins its count on r4a QM's fixture. DECISIONS
        # D292's E1j removes D245_Q2's one: r2d-2 Q2's base is READY (a biopsy done elsewhere than the snare, every place
        # control rejected - D245's own reasoning), so deleting its stomach releases nothing; D245's ruling and its
        # predicate stay, met directly by test_the_rulings_accept_their_shapes_alone
        # DECISIONS D293: D293_ERASE's sixteen (ERASING_ACCEPTED), each held to D264's rule by the check
        self.assertEqual(collections.Counter(named), {D218: 1, D245_B: 1, D262_NC: 2, D262_STATUS: 4,
                                                      D228_DQ2: 4, D262_QM: 24, D264_SITE: 4, D293_ERASE: 16})
        self.assertEqual(set(named) | {D264_CLEAN, D245_Q2},
                         {ruling for _description, ruling, _predicate in ACCEPTED_RELEASES})
        # the shrunk claims a ruling accepts, pinned: D264_SITE's - 43249's claim drops the dilation when its distal
        # esophagus is deleted, and 43245's when its duodenal bulb is, on its own places and on its target lesion's
        self.assertEqual(collections.Counter(ruling for _code, ruling, _label in shrinks), {D264_SITE: 4})
        self.assertEqual(sorted((code, label) for code, _ruling, label in shrinks),
                         [('43245', 'deleted E1 target.places[1]'), ('43245', 'deleted L1 places[1]'),
                          ('43249', 'deleted E1 target.places[0]'), ('43249', 'deleted L1 places[0]')])
        # nothing waits on an open question (DECISIONS D293 emptied OPEN_RELEASES); D293_ERASE's states pinned
        self.assertEqual(waiting, [])
        self.assertEqual(sorted(set(erasing)), ERASING_ACCEPTED)

    def test_a_deleted_members_unrejected_control_keeps_the_pair_on_every_path(self):
        """Refutation 6a-r2b P1 (DECISIONS D220): beside every deletion of an established place member, the control that
        asked the other object about that member NOT rejected - on the act-act path (engine/coverage's identity by
        place) and the statement-act path (engine/pairing) - releases nothing a ruling does not accept: the deleted
        member's unrejected control keeps the pair together. Refutation 6a-r2b's mutants A (facts.apart_by_controls
        before D220) and F (coverage's identity before D220) each release a code here. The one release met is D264_SITE's
        on refute-6a-r1 F3's dilation (D29's site fit reads the act's own places and no pair control, so the control left
        unrejected about the deleted distal esophagus holds nothing there), accepted by name and held to D264's rule. At
        least three of the states hold a code the fixture's every-control-rejected state made READY - the unrejected
        control is what holds it, so the generator reaches D220's state rather than pairs held by something else."""
        paths, cases, held, named = collections.Counter(), 0, 0, []
        for name, R, codes in fixtures():
            plain = assessed(R, codes)
            for label, base_R, after_R, what, path in beside_unrejected_controls(R):
                with self.subTest(fixture=name, weakening=label):
                    base = assessed(base_R, codes)
                    # waiting=[]: a release or shrunk claim an OPEN_RELEASES entry governs is routed into this list and
                    # DISCARDED here; each state here (one control left unrejected, then the deletion) is also a state
                    # of the drawn census, which fails on a question the fixture's own verdicts do not show and leaves
                    # one they show to OpenQuestionsTests (red on its own-verdict state; this drawn-only state goes
                    # unfailed); DECISIONS D293 accepted Q-ERASE's states (D293_ERASE), held to D264's rule
                    named += self.check(base, assessed(after_R, codes), label, what, base_R, waiting=[])
                    paths[path] += 1
                    cases += 1
                    held += bool(ready(plain) - ready(base))  # the unrejected control held a code apart before
        self.assertGreaterEqual(paths['act-act'], 2, paths)
        self.assertGreaterEqual(paths['statement-act'], 2, paths)
        self.assertGreaterEqual(held, 3, (held, cases))
        self.assertEqual(collections.Counter(named), {D264_SITE: D220_SITE_RELEASES}, named)

    def test_the_weakenings_reach_sc_b_and_every_table(self):
        """Refutation 6a-r1 F1 and 6a-r2b P4: the generators reach every kind 9.4 names on these fixtures - a deleted
        member of an act's target.places (SC-B's list), of a lesion's places, of a session's stations and of its
        reached; a pair control made not rejected; a completeness claim made unresolved - and every table: the
        encounter's, the people's and the sections' facts too; and no member that was not established is ever deleted
        (D245, r2d-2's Q3 option (b)). A fixture holds a pair control NOT rejected beside the member a weakening deletes
        (D220's case, refutation 6a-r2b P1)."""
        kinds, tables, unestablished = collections.Counter(), collections.Counter(), []
        for name, R, codes in fixtures():
            for label, changed, what in weakenings(R):
                head = label.split(' ')[0]
                kinds[(head, what[1]) if head == 'deleted' else head] += 1
                if isinstance(what, tuple) and len(what) == 4:
                    subject = what[0]
                    tables[TABLES[subject.family if subject is not None else None]] += 1
                    if head == 'deleted' and what[3].result not in ESTABLISHED:
                        unestablished.append((name, label))
        for kind in (('deleted', A.TARGET_PLACES), ('deleted', A.PLACES), ('deleted', A.STATIONS),
                     ('deleted', A.REACHED), 'pair', 'completeness'):
            with self.subTest(kind=kind):
                self.assertGreater(kinds[kind], 0, dict(kinds))
        for table in TABLES.values():
            with self.subTest(table=table):
                self.assertGreater(tables[table], 0, dict(tables))
        self.assertEqual(unestablished, [])
        self.assertGreaterEqual(sum(1 for _, R, _ in fixtures() if R.pair_controls), 6)
        self.assertTrue(any(R.completeness for _, R, _ in fixtures()))
        R, _codes = fixture('a snare beside a biopsy of the antrum, its control not rejected (D220)')
        self.assertIs(R.pair_controls[P1_UNREJECTED], False)
        self.assertTrue(any(label.startswith('deleted E3 target.places') and what[3].value is Landmark.GASTRIC_ANTRUM
                            for label, _changed, what in weakenings(R)))

    def test_the_harness_never_re_dates_a_weakened_factset(self):
        """Refutation 6a-r2b P4: a weakened date of service reaches the engine as it is - unresolved, doubted or
        contradicted, R7 holds every code on the date (assess.r7_row) - where test_assess.run would have replaced the
        encounter with a supported date; the documenting clinician the encounter holds stays too."""
        R, codes = fixture('the encounter, people and sections (P4)')
        self.assertEqual(service_date(R), TA.DAY)
        base = assessed(R, codes)
        self.assertIn('45385', ready(base))
        dated = [(label, changed) for label, changed, what in weakenings(R)
                 if what[:2] == (None, A.DATE_OF_SERVICE) and _how(label) in HOWS]  # the classic four (9.4)
        self.assertEqual(len(dated), len(HOWS))
        for label, changed in dated:
            with self.subTest(weakening=label):
                self.assertIsNone(service_date(changed))
                self.assertEqual(changed.encounter[A.DOCUMENTING_CLINICIAN], R.encounter[A.DOCUMENTING_CLINICIAN])
                after = assessed(changed, codes)
                self.assertEqual(ready(after), frozenset())
                self.assertTrue(all(any(held.fact == RQ.fact_key(RQ.FactKey.SERVICE_DATE) for held in found.held_facts)
                                    for found in after.codes), [found.held_facts for found in after.codes])
                self.assertNotEqual(ready(TA.run(changed, *codes)), frozenset())  # what re-dating would have hidden

    def test_the_pair_controls_are_claims_rule(self):
        """``claims_rule_controls`` asks what claims.pair() asks of r2d-2's Q2 shape, both ways: the snare about the
        duodenum and the stomach (neither compatible with its esophagus), the biopsy about the esophagus; nothing of
        a pair claims does not make (the examination pairs with nothing); and no control for two acts of one kind
        (r3d's case (b): D211)."""
        R = egd_snare_and_biopsy()
        E = EF.E
        self.assertEqual(set(claims_rule_controls(R)), {(E(2), A.TARGET_PLACES, Landmark.DUODENUM),
                                                        (E(2), A.TARGET_PLACES, Landmark.STOMACH),
                                                        (E(3), A.TARGET_PLACES, Landmark.ESOPHAGUS)})
        self.assertTrue(all(claims_rule_controls(R).values()))
        self.assertFalse(any(claims_rule_controls(R, rejected=lambda key: False).values()))
        R = targeted_denial_beside_a_biopsy()  # a targeted statement against a biopsy of its session, both ways
        found = set(claims_rule_controls(R))
        self.assertIn((E(3), A.TARGET_PLACES, Landmark.TRANSVERSE_COLON), found)
        self.assertIn((E(4), A.TARGET_PLACES, Landmark.RECTUM), found)
        self.assertEqual(claims_rule_controls(possible_statement_beside_a_biopsy()), {})
        self.assertEqual(paired(egd_body_and_antrum(), unrejected=(P1_UNREJECTED,)).pair_controls[P1_UNREJECTED], False)
        with self.assertRaises(ValueError):
            paired(egd_body_and_antrum(), unrejected=((E(9), A.TARGET_PLACES, Landmark.CECUM),))

    def test_an_unaccepted_release_is_seen_and_named_never_skipped(self):
        """P-MONO's positive control (refutation 6a-r2b P1): refutation 6a-r2b's mutant A planted for the call -
        facts.apart_by_controls read as before DECISIONS D220 (only the controls asking about the CURRENT members) - on
        P1's fixture. The deletion of the biopsy's antrum, its control not rejected, then releases 43239; no ruling
        accepts that release, and the checker reports it, naming D220. Unplanted, the same deletion releases nothing."""
        from tests.v2 import test_pairing

        R, codes = fixture('a snare beside a biopsy of the antrum, its control not rejected (D220)')
        [(label, changed, what)] = [(label, changed, what) for label, changed, what in weakenings(R)
                                    if label.startswith('deleted E3 target.places')
                                    and what[3].value is Landmark.GASTRIC_ANTRUM]
        base = assessed(R, codes)
        self.assertNotIn('43239', ready(base))
        self.assertEqual(_release(base, assessed(changed, codes))[0], frozenset())  # D220 holds it
        with mock.patch.object(F, 'apart_by_controls', test_pairing.before_d220):
            planted_base, planted = assessed(R, codes), assessed(changed, codes)
        self.assertNotIn('43239', ready(planted_base))
        self.assertEqual(_release(planted_base, planted)[0], {'43239'})
        self.assertEqual(_accepted(label, what, ['43239'], R), [None])
        self.assertIn('D220', _open_question(label, what, R))
        with self.assertRaises(AssertionError) as caught:
            self.check(planted_base, planted, label, what, R)
        self.assertIn('43239', str(caught.exception))
        self.assertIn('D220', str(caught.exception))

    def test_the_rulings_accept_their_shapes_alone(self):
        """DECISIONS D245, through the engine as assembled. r2d-2's Q2 (option (a)), re-pinned by DECISIONS D292 (E1j)
        on D245's own reasoning: the biopsy names no lesion and one of its places, the duodenum, is disjoint from every
        place of the esophageal snare and of its lesion, asked of the snare by a rejected control with every place
        control rejected, so it was done elsewhere than the removal - 43239 is READY as filed, and deleting its stomach
        (overlapping the snare's esophagus) releases nothing; D245's predicate still names that deletion, the shape it
        accepts. With the control asking the snare about the stomach NOT rejected, E1j does not apply: 43239 is held as
        filed and the deletion releases nothing (D220), and the predicate refuses that state anyway. r3d's Q1 case (b): the possible statement's transverse colon deleted releases 45380, named
        D245's with D228 and D238; beside a place control between them not rejected the predicate refuses it (D238: an
        unrejected one holds) - two biopsies, a pair claims never controls with no control between them, is the production
        shape DECISIONS D262 names R3D-NC's (D245's case (b) where controls exist: test_d262_r3d_nc_...). No predicate
        names a member that was not established, nor another list."""
        R, codes = fixture('a snare beside a biopsy of two places (EGD)')
        [(label, changed, what)] = [found for found in weakenings(R) if found[0].startswith('deleted E3 target.places')
                                    and found[2][3].value is Landmark.STOMACH]
        base = assessed(R, codes)
        self.assertIn('43239', ready(base))  # D292 E1j: READY as filed (a biopsy elsewhere than the snare)
        self.assertEqual(_release(base, assessed(changed, codes))[0], frozenset())
        self.assertEqual(_accepted(label, what, ['43239'], R), [D245_Q2])
        self.assertIn("r2d-2's Q2", _open_question(label, what, R))
        open_ = replace(R, pair_controls={**R.pair_controls, (EF.E(2), A.TARGET_PLACES, Landmark.STOMACH): False})
        self.assertNotIn('43239', ready(assessed(open_, codes)))  # an unrejected place control: E1j does not apply
        self.assertEqual(_accepted(label, what, ['43239'], open_), [None])
        self.assertIn('D220', _open_question(label, what, open_))
        self.assertEqual(_release(assessed(open_, codes), assessed(replace(changed, pair_controls=open_.pair_controls),
                                                                   codes))[0], frozenset())
        R, codes = fixture('a possible statement beside a biopsy (D228)')
        [(label, changed, what)] = [found for found in weakenings(R) if found[0].startswith('deleted E2 target.places')
                                    and found[2][3].value is Landmark.TRANSVERSE_COLON]
        base = assessed(R, codes)
        self.assertNotIn('45380', ready(base))
        self.assertEqual(_release(base, assessed(changed, codes))[0], {'45380'})
        self.assertEqual(_accepted(label, what, ['45380'], R), [D262_NC])
        self.assertTrue(_d228_compatible_deletion(label, what, '45380', R))  # D245's case (b) too: R3D-NC is its shape
        with_control = replace(R, pair_controls={(EF.E(3), A.TARGET_PLACES, Landmark.SIGMOID_COLON): False})
        self.assertEqual(_accepted(label, what, ['45380'], with_control), [None])
        self.assertIn('D238', _open_question(label, what, with_control))
        unestablished = (what[0], what[1], what[2], unres(Landmark.TRANSVERSE_COLON))
        for predicate in (_overlap_deletion, _d228_compatible_deletion, _d211_production_deletion):
            with self.subTest(predicate=predicate.__name__):
                self.assertFalse(predicate(label, unestablished, '45380', R))
                self.assertFalse(predicate(label.replace('target.places', 'places'), (what[0], A.PLACES) + what[2:],
                                           '45380', R))
        self.assertIn("r2d-2's Q3", _open_question(label, unestablished, R))

    @hypothesis.settings(**SETTINGS)
    @hypothesis.given(st.data())
    def test_two_weakenings_drawn_together(self, data):
        """Two weakenings drawn one after the other over a fixture whose pair control verdicts are drawn too (refutation
        6a-r2b P1: pass 2's verdicts not all rejected). The twice-weakened state is checked against the base with each
        released code named by the weakening that released it (refutation 6a-r2b P3): a code the first weakening
        released, by the first (read in the assessments before and after it); any other, by the second, over the
        once-weakened FactSet it was applied to (read in the once- and twice-weakened assessments)."""
        (name, base_R, codes), (label, what, once), drawn = random_states(data)
        base, first = assessed(base_R, codes), assessed(once, codes)
        # waiting=[] in both checks: a release or shrunk claim an OPEN_RELEASES entry governs is routed into the list
        # and DISCARDED here - OpenQuestionsTests fails on the single weakenings of the fixtures' own verdicts, and the
        # drawn census on a single weakening under drawn verdicts whose question the own verdicts do not show, so only a
        # state at depth 2, or a drawn-only state of a question the own verdicts show (OpenQuestionsTests then red on
        # it), goes unfailed (the census in step 6a's NOTES counts what each name accepts there); DECISIONS D293
        # accepted Q-ERASE's states (D293_ERASE), held to D264's rule like every named release
        self.check(base, first, label, what, base_R, waiting=[])
        if drawn is None:
            return
        label2, what2, twice = drawn
        released_first = set(_release(base, first)[0] | _release(base, first)[1])
        after = assessed(twice, codes)
        released = _release(base, after)
        by = {code: (label, what, base_R, (base, first)) if code in released_first
              else (f'{label}; {label2}', what2, once, (first, after)) for code in released[0] | released[1]}
        # the second weakening's own shrink: what the first shrank was checked above
        self.check(base, after, f'{label}; {label2}', what2, once, by=by, waiting=[], claims_from=first)

    def test_a_twice_weakened_release_is_named_by_the_weakening_that_released_it(self):
        """Refutation 6a-r2b P3 (its probe p05): D218's fixture; the ileum deleted first (44361 released, D218's), then a
        second weakening that leaves 44361 READY. The twice-weakened release is named by the FIRST weakening, D218's,
        never read against the second one's attribute; a code only the second weakening releases would be read
        against the second, over the once-weakened FactSet."""
        R, codes = fixture('an oral enteroscopy to the jejunum and the ileum (D218)')
        base = assessed(R, codes)
        [(label, once, what)] = [found for found in weakenings(R) if found[0].startswith('deleted X1 reached')
                                 and found[2][3].value is Extent.ILEUM]
        first = assessed(once, codes)
        self.assertEqual(_release(base, first)[0], {'44361'})
        self.assertEqual(self.check(base, first, label, what, R), [D218])
        checked = 0
        for label2, twice, what2 in weakenings(once):
            after = assessed(twice, codes)
            if '44361' not in ready(after):
                continue
            checked += 1
            with self.subTest(second=label2):
                by = {'44361': (label, what, R)}
                self.assertEqual(self.check(base, after, f'{label}; {label2}', what2, once, by=by), [D218])
                # read against the second weakening alone, as the first round did, the same release is unaccepted
                self.assertEqual(_accepted(f'{label}; {label2}', what2, ['44361'], once), [None])
        self.assertGreater(checked, 5)

    def test_the_accepted_jejunal_release_is_its_rulings_shape_alone(self):
        """D218's named release, as repair r4c's NOTES name it with that ruling, through the engine as assembled:
        tests/v2/test_classes.ent's oral enteroscopy reaching the jejunum and the ileum holds 44361. Deleting the
        supported ileum - the beyond point - releases it, and the predicate names it D218's. A member that is not
        established is never deleted (D245), so an unresolved or doubted ileum gives no deletion. Nothing else is
        accepted: deleting the jejunum releases nothing and the predicate names nothing for it; a negated ileum is no
        beyond point (44361 READY before, nothing released, and the predicate refuses it); a deleted target.places
        member and another code are never D218's."""
        codes = (('44361', 14),)

        def deletions(*reached):
            R = TA.dated(TC.ent(*reached))
            base = assessed(R, codes)
            found = {}
            for label, changed, what in weakenings(R):
                if label.startswith('deleted ') and what[1] is A.REACHED:
                    found[what[2]] = (label, what, _release(base, assessed(changed, codes)), R)
            return base, found

        base, found = deletions(ct.Extent.JEJUNUM, ct.Extent.ILEUM)
        self.assertNotIn('44361', ready(base))
        label, what, (grown_ready, grown_excluded, shrunk), R = found[1]
        self.assertEqual(grown_ready, {'44361'})  # the release ...
        self.assertEqual(_accepted(label, what, sorted(grown_ready), R), [D218])  # ... D218's, named
        label, what, released, R = found[0]  # the jejunum
        self.assertEqual(released, (frozenset(), frozenset(), {}))
        self.assertEqual(_accepted(label, what, ['44361'], R), [None])  # the predicate names nothing else
        for name, beyond in {'unresolved': TC.unresolved(ct.Extent.ILEUM),
                             'doubted, read as the ileum': TC.doubted(ct.Extent.JEJUNUM, (ct.Extent.ILEUM,))}.items():
            with self.subTest(beyond=name):
                base, found = deletions(ct.Extent.JEJUNUM, beyond)
                self.assertNotIn(1, found)  # D245: a member that was not established is never deleted
        base, found = deletions(ct.Extent.JEJUNUM, TC.neg(ct.Extent.ILEUM))
        self.assertIn('44361', ready(base))  # a negated ileum: no point beyond the class is reached
        label, what, released, R = found[1]
        self.assertEqual(released, (frozenset(), frozenset(), {}))
        self.assertEqual(_accepted(label, what, ['44361'], R), [None])  # a negated member is never D218's beyond point
        member = sup(Landmark.CECUM)  # a beyond point's place, but a target.places member: never D218's
        self.assertFalse(_jejunal_beyond_deletion('deleted E3 target.places[0]', (EF.E(3), A.TARGET_PLACES, 0, member),
                                                  '44361', R))
        self.assertFalse(_jejunal_beyond_deletion(label, (what[0], A.REACHED, 1, sup(ct.Extent.ILEUM)), '44376', R))

    def test_d262_d228_status_is_its_shape_alone(self):
        """DECISIONS D262's D228_STATUS (repair r3d's R3D-ST, option (a); 6a's Q1) with D264's Q7, through the engine as
        assembled: R3D-ST's input holds 45380 (another clinician's biopsy in the rectum, its performer inherited, beside
        the team's in the sigmoid colon; two biopsies, no pair control: D211). Each of the four 9.4 weakenings of the
        inherited act's status - unresolved, two doubts that keep the value, and the conflict doubt that makes it
        CONTRADICTED (refute-6a-r1 F5, which D264 rules into the class: D228's arm reads the three results alike) - moves
        it into D228's arm and releases 45380, named D262's, every act still supporting 45380 meeting every row (D264's
        rule). Beside a place pair control asked of the team's biopsy about the rectum NOT rejected, the status weakening
        releases nothing (D238: an unrejected one holds) and the predicate refuses that state. The other clinician stated
        in the act's own sentence holds nothing (the performer row sets them apart): no release to name, and the
        predicate names none. The inherited performer's own weakening is not D228_STATUS: D228's which-pairs corner (DQ2
        as built, 3d's Q4) names it."""
        R, codes = fixture("another clinician's biopsy (inherited) beside the team's (D262, R3D-ST)")
        base = assessed(R, codes)
        self.assertNotIn('45380', ready(base))
        self.assertTrue(_inherited_statement(R, EF.E(2)))
        self.assertEqual(D228_STATUS_RESULTS, (Res.UNRESOLVED, Res.UNKNOWN, Res.CONTRADICTED))
        statuses = [(label, changed, what) for label, changed, what in weakenings(R)
                    if what[:2] == (EF.E(2), A.STATUS) and _how(label) in HOWS]  # the classic four (9.4)
        self.assertEqual(len(statuses), len(HOWS))
        results = []
        for label, changed, what in statuses:
            with self.subTest(weakening=label):
                after = assessed(changed, codes)
                self.assertEqual(_release(base, after)[0], {'45380'})
                self.assertFalse(_which_pairs_corner(label, what, '45380', R))
                results.append(F.fact(changed, EF.E(2), A.STATUS).result)
                self.assertEqual(_accepted(label, what, ['45380'], R), [D262_STATUS])
                self.assertIsNone(_waiting(label, what, '45380', R))
                self.assertEqual(every_row_met('45380', changed), (True, {}))
                self.assertEqual(self.check(base, after, label, what, R), [D262_STATUS])
        self.assertEqual(results, [Res.UNRESOLVED, Res.UNKNOWN, Res.UNKNOWN, Res.CONTRADICTED])  # Q7's is the fourth
        label, changed, what = statuses[0]  # 'unresolved': R3D-ST's own weakening
        held = replace(R, pair_controls={(EF.E(3), A.TARGET_PLACES, Landmark.RECTUM): False})
        held_base = assessed(held, codes)
        self.assertNotIn('45380', ready(held_base))
        weak = replace(changed, pair_controls=held.pair_controls)
        self.assertEqual(_release(held_base, assessed(weak, codes))[0], frozenset())  # D238: the control holds the pair
        self.assertFalse(_d228_status_weakening(label, what, '45380', held))
        self.assertEqual(_accepted(label, what, ['45380'], held), [None])
        self.assertIn('D238', _open_question(label, what, held))
        own = TA.dated(paired(inherited_other_clinician_beside_a_biopsy(own=True)))
        self.assertIn('45380', ready(assessed(own, codes)))  # the performer row sets them apart: nothing held
        self.assertFalse(_inherited_statement(own, EF.E(2)))
        own_status = (EF.E(2), A.STATUS, 0, own.events[EF.E(2)][A.STATUS][0])
        self.assertFalse(_d228_status_weakening(label, own_status, '45380', own))
        performers = [(label, what) for label, _changed, what in weakenings(R)
                      if what[:2] == (EF.E(2), A.PERFORMER) and _how(label) in HOWS]  # the classic four (9.4)
        self.assertEqual(len(performers), len(HOWS))
        for label, what in performers:
            with self.subTest(weakening=label):
                self.assertFalse(_d228_status_weakening(label, what, '45380', R))
                self.assertEqual(_accepted(label, what, ['45380'], R), [D228_DQ2])
        team = [(label, what) for label, _changed, what in weakenings(R) if what[:2] == (EF.E(3), A.STATUS)]
        self.assertTrue(team)
        for label, what in team:  # the team's own biopsy: never D228_STATUS nor the corner
            self.assertFalse(_d228_status_weakening(label, what, '45380', R))
            self.assertFalse(_which_pairs_corner(label, what, '45380', R))

    def test_d262_qm_is_its_shape_alone(self):
        """DECISIONS D262's r4a QM (r4a's request R7; option (a): the class named in P-MONO), through the engine as
        assembled: the three dilations hold 43249 on E1's technique (E1 supporting, its device unstated). Every weakening
        of E1's support - kind, status, session, date, performer, entry, four ways each - moves E1 out of the supporting
        acts and releases 43249 onto E2 alone (a supporting act before, every row met: no false READY), named D262's;
        without the duodenal act (4.4's pre-existing class, which D240 extends) the same. The predicate names nothing
        else: a weakening of E2 (it held nothing), a deletion of E1's place, a release left with an act still holding
        the code (both dilations of unstated device)."""
        from studio.interpretation.engine import evaluate

        for duodenal in (True, False):
            with self.subTest(duodenal=duodenal):
                R = TA.dated(paired(two_esophageal_dilations_and_a_duodenal_one(duodenal=duodenal)))
                codes = (('43249', 2),)
                base = assessed(R, codes)
                self.assertNotIn('43249', ready(base))
                self.assertEqual(set(evaluate.decide('43249', (), R).supporting), {EF.E(1), EF.E(2)})
                support = [(label, changed, what) for label, changed, what in weakenings(R)
                           if what[0] == EF.E(1) and what[1] in SUPPORT_ATTRIBUTES and _how(label) in HOWS]
                self.assertEqual(len(support), len(SUPPORT_ATTRIBUTES) * len(HOWS))
                for label, changed, what in support:
                    self.assertEqual(_release(base, assessed(changed, codes))[0], {'43249'}, label)
                    self.assertEqual(_accepted(label, what, ['43249'], R), [D262_QM], label)
                    self.assertEqual(evaluate.decide('43249', (), changed).supporting, (EF.E(2),), label)
                for label, changed, what in weakenings(R):
                    if isinstance(what, tuple) and len(what) == 4 and (
                            what[0] == EF.E(2) or (what[0] == EF.E(1) and _how(label) == 'deleted')):
                        self.assertFalse(_site_fit_weakening(label, what, '43249', R), label)
        doc = EF.Doc()  # both esophageal dilations of unstated device: E1 weakened out, E2 still holds 43249
        doc.session(1, ct.SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(3)
        doc.act(1, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS)], device=None)
        doc.act(2, Kind.DILATION, places=[sup(Landmark.MID_ESOPHAGUS)], device=None)
        R = TA.dated(paired(doc.build()))
        kinds = [(label, what) for label, _changed, what in weakenings(R) if what[:2] == (EF.E(1), A.KIND)]
        self.assertTrue(kinds)
        for label, what in kinds:
            self.assertFalse(_site_fit_weakening(label, what, '43249', R), label)

    def test_d264_clean_names_f2s_states_and_qm_keeps_its_own(self):
        """DECISIONS D264 (6a's Q4, refute-6a-r2 F2; its probe q01): QM is narrowed to what D262 accepted - one of the
        leaving act's own support facts weakened - and the states the narrowed binding no longer accepts are D264_CLEAN.
        The three dilations, every pair control rejected but the one asking E1 about E4's duodenal bulb (a verdicts()
        draw): E4's status weakened, any of the four ways, makes E4 a possible statement that holds E1 by its clean row
        (row 8), so E1 leaves the supporting acts failing EXACTLY that row and 43249 is READY on E2 - never QM's (E4's
        status is no support fact of E1's), named D264_CLEAN, every act still supporting 43249 meeting every row (D264's
        rule). Under the fixture's own verdicts, at depth 2, the same: E1's only place deleted, then E4's status (the
        status releases); E4's conflict doubt, then E1's only place deleted (the deletion releases); q01's E4 status
        doubted, then the control asking E1 about the mid esophagus made not rejected (the control releases); E4's place
        deleted, then E1's status weakened - two acts leave, E1 by its own status and E4 by its clean row (the census of
        step 6a's NOTES found this shape; the narrowed binding takes one leaving act only). QM's own states stay QM's
        (E1's kind weakened). Neither names a state where an act still holds the code, nor F3's deletion (E1 dropped by
        D240's site fit with its support met: D264_SITE's)."""
        from studio.interpretation.engine import evaluate

        R0, codes = fixture(QM_FIXTURE)
        key = (EF.E(1), A.TARGET_PLACES, Landmark.DUODENAL_BULB)
        R = replace(R0, pair_controls={**R0.pair_controls, key: False})
        base = assessed(R, codes)
        self.assertNotIn('43249', ready(base))
        statuses = [(label, changed, what) for label, changed, what in weakenings(R)
                    if what[:2] == (EF.E(4), A.STATUS) and _how(label) in HOWS]  # the classic four (9.4)
        self.assertEqual(len(statuses), len(HOWS))
        for label, changed, what in statuses:
            with self.subTest(weakening=label):
                after = assessed(changed, codes)
                self.assertEqual(_release(base, after)[0], {'43249'})
                self.assertEqual(evaluate.decide('43249', (), changed).supporting, (EF.E(2),))
                self.assertTrue(left_by_support('43249', changed, EF.E(1)))
                self.assertTrue(fails_only_clean('43249', changed, EF.E(1)))
                self.assertFalse(_site_fit_weakening(label, what, '43249', R))  # QM narrowed: not E1's own fact
                self.assertTrue(_clean_row_release(label, what, '43249', R))
                self.assertEqual(_accepted(label, what, ['43249'], R), [D264_CLEAN])
                self.assertEqual(every_row_met('43249', changed), (True, {}))
                self.assertEqual(self.check(base, after, label, what, R), [D264_CLEAN])
        base0 = assessed(R0, codes)
        twice_over = (('deleted E1 target.places[0]', 'unresolved E4 status[0]'),
                      ('doubt conflict E4 status[0]', 'deleted E1 target.places[0]'),
                      ('doubt unclear E4 status[0]', f'pair control {(EF.E(1), A.TARGET_PLACES, Landmark.MID_ESOPHAGUS)} '
                                                     'not rejected'),
                      # E4's place deleted (its site open, so D240's site fit keeps it), then E1's status weakened: E1 out
                      # by its own status (QM's mechanism) and E4, held by E1 as a possible statement, out by its clean row
                      ('deleted E4 target.places[0]', 'unresolved E1 status[0]'))
        for first_label, second_label in twice_over:
            with self.subTest(first=first_label, second=second_label):
                [(label, once, what)] = [found for found in weakenings(R0) if found[0] == first_label]
                first = assessed(once, codes)
                self.assertEqual(_release(base0, first)[0], frozenset())
                [(label2, twice, what2)] = [found for found in weakenings(once) if found[0] == second_label]
                after = assessed(twice, codes)
                self.assertEqual(_release(base0, after)[0], {'43249'})
                full = f'{label}; {label2}'
                self.assertFalse(_site_fit_weakening(full, what2, '43249', once))
                self.assertEqual(_accepted(full, what2, ['43249'], once), [D264_CLEAN])
                by = {'43249': (full, what2, once, (first, after))}
                self.assertEqual(self.check(base0, after, full, what2, once, by=by, claims_from=first), [D264_CLEAN])
        [(label, changed, what)] = [found for found in weakenings(R0) if found[0] == 'unresolved E1 kind[0]']
        self.assertEqual(_accepted(label, what, ['43249'], R0), [D262_QM])  # QM's own: E1's support fact
        self.assertFalse(_clean_row_release(label, what, '43249', R0))
        # never: an act still holding the code (both esophageal dilations of unstated device, E4's status weakened)
        doc = EF.Doc()
        doc.session(1, ct.SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(3)
        doc.act(1, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS)], device=None)
        doc.act(2, Kind.DILATION, places=[sup(Landmark.MID_ESOPHAGUS)], device=None)
        doc.act(4, Kind.DILATION, places=[sup(Landmark.DUODENAL_BULB)], device=sup(ct.Device.BALLOON))
        both = TA.dated(paired(doc.build()))
        both = replace(both, pair_controls={**both.pair_controls, key: False})
        for label, changed, what in weakenings(both):
            if what[:2] == (EF.E(4), A.STATUS):
                self.assertNotIn('43249', ready(assessed(changed, codes)), label)
                self.assertFalse(_site_fit_weakening(label, what, '43249', both), label)
                self.assertFalse(_clean_row_release(label, what, '43249', both), label)
        # never: F3's deletion, E1 dropped by D240's site fit with its support met
        R, codes = fixture(F3_FIXTURE)
        [(label, changed, what)] = [found for found in weakenings(R) if found[0] == 'deleted E1 target.places[0]']
        self.assertFalse(left_by_support('43249', changed, EF.E(1)))
        for predicate in (_site_fit_weakening, _clean_row_release):
            self.assertFalse(predicate(label, what, '43249', R), predicate.__name__)

    def test_d264_site_names_f3s_releases_and_shrunk_claims(self):
        """DECISIONS D264 (6a's Q6, option (a): D240's named release; refute-6a-r2 F1; w7r's O13, repair r4d's R2): E1, a
        dilation of unstated device filed [distal esophagus, duodenal bulb], beside E2, a mid-esophageal balloon
        dilation: 43249 held on E1's technique and site, 43245 on E1's site and E2's misfit, both competing for E1.
        Deleting E1's distal esophagus sets E1 outside the esophageal class (its SITE row open, then failing): E1 leaves
        43249's supporting acts by its SITE row (43249 READY on E2) and 43249's claim (so the competition ends), while E2,
        established outside the gastric or duodenal class, leaves 43245's (43245 READY on E1) - both releases D264_SITE's,
        read in the assessments before and after (never without them), every act still supporting each code meeting every
        row, and 43249's shrunk claim accepted under that name. Deleting the duodenal bulb sets E1 outside the gastric or
        duodenal class: nothing released, 43245's claim drops E1, accepted. The same with the two places on E1's target
        lesion (D264's "or of its target lesion's places"). At depth 2 the competition alone: E1's kind weakened first (E1
        supporting neither code, both still claiming it), then either place deleted - 43249 READY because one code's claim
        drops E1. Never D264_SITE: a deletion that sets no act outside a SITE class (r4a QM's E1, its only place
        deleted), an act lost from a claim whose own places the deletion did not set outside the class, a release whose
        assessments are not given."""
        from studio.interpretation.engine import combination, evaluate

        for name, deleted in ((F3_FIXTURE, 'deleted E1 target.places'), (LESION_SITE_FIXTURE, 'deleted L1 places')):
            with self.subTest(fixture=name):
                R, codes = fixture(name)
                base = assessed(R, codes)
                self.assertEqual(ready(base), frozenset())
                self.assertEqual(set(evaluate.decide('43249', (), R).supporting), {EF.E(1), EF.E(2)})
                [(label, changed, what)] = [found for found in weakenings(R) if found[0] == f'{deleted}[0]']
                after = assessed(changed, codes)
                self.assertEqual(_release(base, after)[0], {'43249', '43245'})
                self.assertEqual(evaluate.decide('43249', (), changed).supporting, (EF.E(2),))
                self.assertEqual(evaluate.decide('43245', (), changed).supporting, (EF.E(1),))
                self.assertTrue(set_outside('43249', R, changed, EF.E(1)))
                self.assertTrue(combination.site_outside('43249', changed, EF.E(1)))
                transition = (base, after)
                for code in ('43249', '43245'):
                    self.assertEqual(_accepted(label, what, [code], R, transition), [D264_SITE], code)
                    self.assertEqual(_accepted(label, what, [code], R), [None], code)  # no assessments, no D264_SITE
                    self.assertEqual(every_row_met(code, changed), (True, {}), code)
                shrinks = []
                self.assertEqual(self.check(base, after, label, what, R, shrinks=shrinks), [D264_SITE, D264_SITE])
                self.assertEqual(shrinks, [('43249', D264_SITE, label)])
                self.assertFalse(_site_class_shrink(label, what, '43249', frozenset({EF.E(2)}), R))
                [(label, changed, what)] = [found for found in weakenings(R) if found[0] == f'{deleted}[1]']
                after = assessed(changed, codes)
                self.assertEqual(_release(base, after), (frozenset(), frozenset(), {'43245': frozenset({EF.E(1)})}))
                self.assertTrue(set_outside('43245', R, changed, EF.E(1)))
                shrinks = []
                self.assertEqual(self.check(base, after, label, what, R, shrinks=shrinks), [])
                self.assertEqual(shrinks, [('43245', D264_SITE, label)])
        R, codes = fixture(F3_FIXTURE)
        base = assessed(R, codes)
        [(label, once, what)] = [found for found in weakenings(R) if found[0] == 'unresolved E1 kind[0]']
        first = assessed(once, codes)
        self.assertEqual(_release(base, first)[0], frozenset())  # 43249 held by the competition for E1 alone
        self.assertEqual(evaluate.decide('43249', (), once).supporting, (EF.E(2),))
        self.assertEqual(evaluate.decide('43249', (), once).held_facts, ())
        for position in (0, 1):
            with self.subTest(second=f'deleted E1 target.places[{position}]'):
                [(label2, twice, what2)] = [found for found in weakenings(once)
                                            if found[0] == f'deleted E1 target.places[{position}]']
                after = assessed(twice, codes)
                self.assertEqual(_release(base, after)[0], {'43249'})
                full = f'{label}; {label2}'
                self.assertEqual(_accepted(full, what2, ['43249'], once, (first, after)), [D264_SITE])
                by = {'43249': (full, what2, once, (first, after))}
                self.assertEqual(self.check(base, after, full, what2, once, by=by, claims_from=first), [D264_SITE])
        R, codes = fixture(QM_FIXTURE)  # E1's only place deleted: an empty list sets nothing outside a class
        [(label, changed, what)] = [found for found in weakenings(R) if found[0] == 'deleted E1 target.places[0]']
        self.assertIsNone(_site_deletion(label, what, R))
        self.assertFalse(_site_class_release(label, what, '43249', R, transition_of(R, codes, label, what)))
        self.assertFalse(_site_class_shrink(label, what, '43249', frozenset({EF.E(1)}), R))
        # 6a's question QS1: F3's dilation alone, 43245 alone - deleting its distal esophagus sets it outside the esophageal
        # class and reads the short list as its site within 43245's, so 43245 is READY on it with NO act dropped (none
        # leaves its supporting acts, no competition ends): not D264_SITE's routing, refused (fail-closed)
        doc = EF.Doc()
        doc.session(1, ct.SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(3)
        doc.act(1, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS), sup(Landmark.DUODENAL_BULB)], device=None)
        R, codes = TA.dated(paired(doc.build())), (('43245', 1),)
        [(label, changed, what)] = [found for found in weakenings(R) if found[0] == 'deleted E1 target.places[0]']
        self.assertEqual(_release(assessed(R, codes), assessed(changed, codes))[0], {'43245'})
        self.assertIsNotNone(_site_deletion(label, what, R))
        self.assertFalse(_site_class_release(label, what, '43245', R, transition_of(R, codes, label, what)))

    def test_d264_site_takes_a_claim_of_d118_resting_on_the_act_set_outside(self):
        """DECISIONS D264 with repair r4d's R2 ("may drop that act, and D118's claims resting on it, from the code's
        claims"): beside F3's two dilations, E5 a bougie dilation at the distal esophagus - no act 43249 (a balloon code)
        may account for, claimed only by D118 as on one stricture with E1 (their distal esophagus shared). Deleting E1's
        distal esophagus sets E1 outside 43249's class, and 43249's claim drops E1 and E5, D118's claim that rested on E1:
        accepted under D264_SITE. A lost act that rested on no act set outside is refused (E2, an act 43249 may account
        for)."""
        from studio.interpretation.engine import combination

        doc = EF.Doc()
        doc.session(1, ct.SessionKind.EGD, reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(3)
        doc.act(1, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS), sup(Landmark.DUODENAL_BULB)], device=None)
        doc.act(2, Kind.DILATION, places=[sup(Landmark.MID_ESOPHAGUS)], device=sup(ct.Device.BALLOON))
        doc.act(5, Kind.DILATION, places=[sup(Landmark.DISTAL_ESOPHAGUS)], device=sup(ct.Device.BOUGIE))
        R = TA.dated(paired(doc.build()))
        codes = (('43249', 2), ('43245', 1))
        base = assessed(R, codes)
        self.assertFalse(combination.may_account_for('43249', R, EF.E(5)))
        self.assertIn(EF.E(5), claims(base)['43249'])  # D118's claim: on one stricture with E1
        [(label, changed, what)] = [found for found in weakenings(R) if found[0] == 'deleted E1 target.places[0]']
        after = assessed(changed, codes)
        lost = _release(base, after)[2].get('43249', frozenset())
        self.assertEqual(lost, frozenset({EF.E(1), EF.E(5)}))
        self.assertTrue(_site_class_shrink(label, what, '43249', lost, R))
        self.assertTrue(_rests_on('43249', R, EF.E(5), [EF.E(1)]))
        self.assertFalse(_rests_on('43249', R, EF.E(2), [EF.E(1)]))  # E2 is an act 43249 may account for
        self.assertFalse(_site_class_shrink(label, what, '43249', frozenset({EF.E(1), EF.E(2)}), R))
        shrinks = []
        self.check(base, after, label, what, R, shrinks=shrinks)
        self.assertIn(('43249', D264_SITE, label), shrinks)

    def test_a_named_release_is_held_to_every_row_never_a_false_ready(self):
        """DECISIONS D264's rule (its positive control): a named release is accepted only when every act still
        supporting the released code meets every row of evaluate's reading after the weakening. R3D-ST's status weakening
        releases 45380 onto the team's biopsy, D262_STATUS's shape; planted for the call, an engine that also counts the
        weakened act - its status unresolved, its performer another clinician - among 45380's supporting acts (a false
        READY under D262_STATUS's name): the shape still takes the release, and the check fails naming D264's rule, the
        ruling and the act's failing rows. A READY with no supporting act at all fails the rule too. Unplanted, the same
        release passes."""
        from studio.interpretation.engine import evaluate

        R, codes = fixture("another clinician's biopsy (inherited) beside the team's (D262, R3D-ST)")
        base = assessed(R, codes)
        [(label, changed, what)] = [found for found in weakenings(R) if found[0] == 'unresolved E2 status[0]']
        after = assessed(changed, codes)
        self.assertEqual(self.check(base, after, label, what, R), [D262_STATUS])
        real = evaluate.decide

        def counting_the_weakened_act(code, kept, state, **kw):
            found = real(code, kept, state, **kw)
            return replace(found, supporting=(EF.E(2),) + found.supporting) if code == '45380' else found

        with mock.patch.object(evaluate, 'decide', counting_the_weakened_act):
            self.assertEqual(_accepted(label, what, ['45380'], R), [D262_STATUS])  # the shape reads no outcome
            met, failing = every_row_met('45380', changed)
            self.assertFalse(met)
            self.assertIn(EF.E(2), failing)
            self.assertIn(RQ.Requirement.SUP_STATUS.value, failing[EF.E(2)])
            with self.assertRaises(AssertionError) as caught:
                self.check(base, after, label, what, R)
        self.assertIn('D264', str(caught.exception))
        self.assertIn(D262_STATUS, str(caught.exception))

        def supporting_nothing(code, kept, state, **kw):
            found = real(code, kept, state, **kw)
            return replace(found, supporting=()) if code == '45380' else found

        with mock.patch.object(evaluate, 'decide', supporting_nothing):
            self.assertEqual(every_row_met('45380', changed), (False, 'READY with no supporting act'))
            self.assertEqual(every_row_met('45380', changed, ready=False), (True, {}))
            with self.assertRaises(AssertionError):
                self.check(base, after, label, what, R)
        self.assertEqual(every_row_met('45380', changed), (True, {}))

    def test_d262_r3d_nc_names_the_production_shape_and_d245_case_b_the_rest(self):
        """DECISIONS D262's R3D-NC (D238's production shape) beside D245's case (b): the doubted snare filed in full holds
        45385; deleting its transverse colon releases it - two snares, a pair claims never controls (D211), no control
        between them - named D262's R3D-NC. With place pair controls between the two (the snare E4 claims pairs with both
        biopsies), every one rejected, r3d's case (b) is D245's alone (6a's Q2 breadth, as built by D262); with one of
        them not rejected nothing is accepted (D220, D238), and the deletion releases nothing."""
        R, codes = fixture('a doubted snare filed in full beside a snare (D262, R3D-NC)')
        base = assessed(R, codes)
        self.assertNotIn('45385', ready(base))
        self.assertEqual(R.pair_controls, {})
        [(label, changed, what)] = [found for found in weakenings(R) if found[0].startswith('deleted E3 target.places')
                                    and found[2][3].value is Landmark.TRANSVERSE_COLON]
        self.assertEqual(_release(base, assessed(changed, codes))[0], {'45385'})
        self.assertEqual(_accepted(label, what, ['45385'], R), [D262_NC])
        R, codes = fixture('a possible statement beside a biopsy and a snare, its controls rejected (D245)')
        between = place_controls_between(R, EF.E(2), EF.E(3))
        self.assertTrue(between)
        self.assertTrue(all(between.values()))
        base = assessed(R, codes)
        self.assertNotIn('45380', ready(base))
        [(label, changed, what)] = [found for found in weakenings(R) if found[0].startswith('deleted E2 target.places')
                                    and found[2][3].value is Landmark.TRANSVERSE_COLON]
        self.assertEqual(_release(base, assessed(changed, codes))[0], {'45380'})
        self.assertFalse(_d211_production_deletion(label, what, '45380', R))
        self.assertEqual(_accepted(label, what, ['45380'], R), [D245_B])
        key = next(iter(sorted(between, key=repr)))
        open_ = replace(R, pair_controls={**R.pair_controls, key: False})
        self.assertEqual(_accepted(label, what, ['45380'], open_), [None])
        self.assertIn('D220', _open_question(label, what, open_))
        self.assertEqual(_release(assessed(open_, codes), assessed(replace(changed, pair_controls=open_.pair_controls),
                                                                   codes))[0], frozenset())


VERDICTS_ENUMERATED = 6  # the most pair controls a fixture has whose every pattern of verdicts the census enumerates
VERDICT_PARTS = 6  # the drawn-verdict census runs as this many test classes, one process each in the gate
# the drawn-verdict census's pins (DRAWN_RELEASES, below): on r4a QM's fixture, over its 64 patterns, QM's narrowed states
# (E1's six support facts, four ways each, where E1 alone leaves) and D264_CLEAN's - refute-6a-r2 F2's twelve single
# weakenings: E4's status, four ways, under the three patterns leaving a control between E1 and E4 not rejected; on
# refute-6a-r1 F3's, over its 8 patterns, D264_SITE's two releases and two shrunk claims each
DRAWN_QM, DRAWN_CLEAN, DRAWN_SITE, DRAWN_SITE_SHRINKS = 1296, 12, 16, 16
# DECISIONS D293 (Q-ERASE option (a)): on r4a QM's fixture, over its 64 patterns, the value-erasing contradictions of E1's
# support facts whose classic weakening D262_QM names (and the erasing states D264_CLEAN's predicate takes), every one
# held to D264's every-row rule by the census's own check (measured on the lead's tree, 2026-11-16)
DRAWN_ERASE = 711
# D220's unrejected-control states beside a deletion: the D264_SITE releases among them (F3's dilation: 43249 and 43245
# when its distal esophagus is deleted beside the control asking E2 about it, left unrejected)
D220_SITE_RELEASES = 2


def drawn_verdicts(R):
    """Every pattern of pass 2's verdicts on ``R``'s pair controls that ``verdicts`` can draw - each subset of them left
    not rejected, the rest rejected (refute-6a-r1 F2: P-MONO's random states reach these, so the census takes them all):
    (label, the FactSet), the fixture's own pattern first."""
    keys = sorted(R.pair_controls, key=repr)
    out = [('as filed', R)]
    for size in range(len(keys) + 1):
        for unrejected in itertools.combinations(keys, size):
            pattern = {key: key not in unrejected for key in keys}
            if pattern != R.pair_controls:
                out.append((f'not rejected: {[str(key) for key in unrejected]}', replace(R, pair_controls=pattern)))
    return out


def verdict_parts() -> tuple:
    """The fixtures with pair controls, by name, in VERDICT_PARTS parts of near-equal work (patterns x weakenings,
    largest first onto the lightest part): the drawn-verdict census's classes, each one process in the gate."""
    work = sorted(((2 ** len(R.pair_controls) * len(list(weakenings(R))), name) for name, R, _codes in fixtures()
                   if R.pair_controls), reverse=True)
    sizes: list[int] = [0] * VERDICT_PARTS
    names: list[list[str]] = [[] for _ in range(VERDICT_PARTS)]
    for size, name in work:
        lightest = sizes.index(min(sizes))
        sizes[lightest] += size
        names[lightest].append(name)
    return tuple(tuple(part) for part in names)


# What the drawn-verdict census accepts under each name, per fixture, pinned (DECISIONS D264: "their count is pinned";
# refute-6a-r2 F4: what the census absorbs is reported): over every pattern of verdicts and every single weakening - the
# releases each name accepts and, for D264_SITE, the shrunk claims it accepts. A fixture with pair controls not listed
# here accepts nothing under any name. Step 6a's NOTES give the same per pattern, at depth 1 and depth 2.
DRAWN_RELEASES = {
    QM_FIXTURE: {D262_QM: DRAWN_QM, D264_CLEAN: DRAWN_CLEAN, D293_ERASE: DRAWN_ERASE},
    F3_FIXTURE: {D264_SITE: DRAWN_SITE},
    # DECISIONS D292's E1j: r2d-2 Q2's fixture accepts nothing - its base is READY as filed (a biopsy elsewhere than the
    # snare, every place control rejected), and with any control left unrejected the biopsy is held as before
    'a snare beside a biopsy of two places (EGD)': {},
    'a possible statement beside a biopsy and a snare, its controls rejected (D245)': {D245_B: 1},  # likewise
}
DRAWN_SHRINKS = {F3_FIXTURE: {D264_SITE: DRAWN_SITE_SHRINKS}}


def drawn_verdict_census(part: int):
    """refute-6a-r1 F2: P-MONO's single-weakening census under every pattern of verdicts ``verdicts`` can draw
    (``drawn_verdicts``), so a release its random states can reach is seen whatever the seed - the test of the
    PMonoVerdicts<part>Tests class, whose fixtures with pair controls are ``verdict_parts()[part]``."""

    def test_every_single_weakening_under_every_drawn_verdict(self: SimpleTestCase) -> None:
        """Each release named by its ruling and held to D264's rule; what each name accepts per fixture pinned
        (DRAWN_RELEASES, DRAWN_SHRINKS); a release an open question governs is seen here only where the fixture's own
        verdicts show that question too (OpenQuestionsTests fails on those) - one seen only under drawn verdicts fails
        here, named."""
        names = verdict_parts()[part]
        check = PMonoTests.check  # P-MONO's own check, on this case
        counted, named = 0, []
        for name, R, codes in fixtures():
            if name not in names:
                continue
            self.assertLessEqual(len(R.pair_controls), VERDICTS_ENUMERATED, name)
            own, accepted, shrinks = None, [], []
            for pattern, drawn in drawn_verdicts(R):
                base, waiting = assessed(drawn, codes), []
                for label, changed, what in weakenings(drawn):
                    with self.subTest(fixture=name, verdicts=pattern, weakening=label):
                        counted += 1
                        after = assessed(changed, codes)
                        accepted += check(self, base, after, label, what, drawn, waiting=waiting, shrinks=shrinks)
                # the routed releases are DISCARDED here but for their question: one whose question the fixture's own
                # verdicts also show is left to OpenQuestionsTests, which fails on the own-verdict states alone (the
                # drawn-only states of that question go unfailed); a question seen only under drawn verdicts fails here.
                # (DECISIONS D293 accepted Q-ERASE's states under D293_ERASE: they are counted in DRAWN_RELEASES)
                questions = {question for _code, question, _label in waiting}
                own = questions if own is None else own  # 'as filed' comes first: the fixture's own verdicts
                with self.subTest(fixture=name, verdicts=pattern):
                    self.assertLessEqual(questions, own, [(code, label, question) for code, question, label in waiting
                                                          if question not in own])
            with self.subTest(fixture=name, pinned='what each name accepts'):
                self.assertEqual(dict(collections.Counter(accepted)), DRAWN_RELEASES.get(name, {}))
                self.assertEqual(dict(collections.Counter(ruling for _code, ruling, _label in shrinks)),
                                 DRAWN_SHRINKS.get(name, {}))
            named += accepted
        self.assertGreater(counted, 500 if names else -1)
        self.assertLessEqual(set(named), {ruling for _description, ruling, _predicate in ACCEPTED_RELEASES})

    test_every_single_weakening_under_every_drawn_verdict.part = part  # type: ignore[attr-defined]
    return test_every_single_weakening_under_every_drawn_verdict


class PMonoVerdicts0Tests(SimpleTestCase):
    test_every_single_weakening_under_every_drawn_verdict = drawn_verdict_census(0)


class PMonoVerdicts1Tests(SimpleTestCase):
    test_every_single_weakening_under_every_drawn_verdict = drawn_verdict_census(1)


class PMonoVerdicts2Tests(SimpleTestCase):
    test_every_single_weakening_under_every_drawn_verdict = drawn_verdict_census(2)


class PMonoVerdicts3Tests(SimpleTestCase):
    test_every_single_weakening_under_every_drawn_verdict = drawn_verdict_census(3)


class PMonoVerdicts4Tests(SimpleTestCase):
    test_every_single_weakening_under_every_drawn_verdict = drawn_verdict_census(4)


class PMonoVerdicts5Tests(SimpleTestCase):
    test_every_single_weakening_under_every_drawn_verdict = drawn_verdict_census(5)


class ExemptionMonoTests(SimpleTestCase):
    """DECISIONS D285 ruling A (r4d's mono_probe; refute-r4d-r1 V9R4D1-3): the exemption's P-MONO census over random
    EGD and upper EUS shapes, beside P-MONO's other censuses: in test_combination, P-WORDED's harvest of that module
    (WORDED_MODULES) worded each of its 32,000 combinations one by one and the census tripled the gate's longest unit;
    the member sentences of P-MONO's states are P-WORDED's here, through p_mono_scenes (every fixture's single
    weakenings, the value-erasing contradictions included). The scenes, the seed and the calls are test_combination's
    D285Count probes', unchanged."""

    def test_mono_probe_no_whole_side_release(self):
        """mono_probe.py's census (seeded; the exemption's P-MONO): an EGD beside an upper EUS of several shapes, 0-3
        more events and 0-2 kept unlisted entries; no single weakening (``weakenings``, the value-erasing contradictions
        included) loses a whole of X1, turns session_possibly_done(X2) from True to False, or releases 43235's
        combination hold."""
        import random as random_

        from tests.v2 import test_combination as T

        members = [T.member('sel:0', '43235', T.X1, (T.E1,), procedural=True, supported=True)]
        rng = random_.Random(20261116)
        checked = 0
        for _ in range(250):
            events = {T.E1: T.act(T.Kind.EXAMINATION, T.X1)}
            shape = rng.choice(['planned', 'planned', 'earlier', 'denied', 'today', 'date open', None])
            if shape == 'planned':
                events[T.E2] = T.act(T.Kind.EXAMINATION, T.X2, status=T.sup(T.PLANNED),
                                     date=rng.choice([T.sup(T.LATER_), None]))
            elif shape == 'earlier':
                events[T.E2] = T.act(T.Kind.EXAMINATION, T.X2, date=T.sup(T.EARLIER))
            elif shape == 'denied':
                events[T.E2] = T.act(T.Kind.EXAMINATION, T.X2, status=T.neg(T.PERFORMED))
            elif shape == 'today':
                events[T.E2] = T.act(T.Kind.EXAMINATION, T.X2)
            elif shape == 'date open':
                events[T.E2] = T.act(T.Kind.EXAMINATION, T.X2, date=T.unres(T.ON))
            for number in range(3, 3 + rng.randint(0, 3)):
                kind = rng.choice([T.sup(T.Kind.EXAMINATION), T.sup(T.Kind.EXAMINATION), None, T.sup(T.Kind.FNA),
                                   T.sup(T.Kind.EM_VISIT)])
                made = T.act(kind if kind is not None else T.Kind.EXAMINATION,
                             status=rng.choice([T.sup(T.PERFORMED), T.sup(T.PERFORMED), T.doubted(T.PERFORMED),
                                                T.sup(T.PLANNED)]),
                             session=rng.choice([None, T.sup(T.X2), T.sup(T.X2), T.unres(T.X2), T.doubted(T.X1, T.X2),
                                                 T.sup(T.X1)]),
                             date=rng.choice([None, T.sup(T.ON), T.sup(T.ON), T.unres(T.ON), T.sup(T.EARLIER),
                                              T.sup(T.LATER_)]),
                             device=rng.choice([None, None, T.sup(T.Device.ENDOSCOPE), T.sup(T.Device.MANUAL)]))
                if kind is None:
                    del made[T.A.KIND]
                events[T.Id(T.IdFamily.EVENT, number)] = made
            entries = tuple(T.entry_of(rng.choice([T.Kind.EXAMINATION, T.Kind.FNA, None, T.Kind.EM_VISIT]),
                                       rng.choice([None, T.X2, T.X1, T.X9]), rng.choice([T.ACT_, T.DOUBT_]),
                                       at=900 + 50 * index)
                            for index in range(rng.choice([0, 0, 1, 2])))
            R = T.build(events, {T.X1: T.session_of(T.SessionKind.EGD),
                                 T.X2: T.session_of(T.SessionKind.EUS, tract=T.UPPER)}, unlisted=entries)

            def answer(S):
                return ({whole.session for whole in T.C.wholes(S, T.X1)}, T.C.session_possibly_done(S, T.X2),
                        bool(T.C.combine(members, T.coding_of(S), S).held['sel:0']))

            before = answer(R)
            for label, W, _what in weakenings(R):
                after = answer(W)
                checked += 1
                self.assertFalse((not before[0] <= after[0]) or (before[1] and not after[1])
                                 or (before[2] and not after[2]), label)
        self.assertGreater(checked, 5000)


class ViewAloneTests(SimpleTestCase):
    """AMENDMENT-2 4.4's first property for the merged view, over F1's class (refute-f3e-r1 F1, critical): "never
    stronger than any single written fact read alone, for any reader". Over every fixture, every ESTABLISHED single
    slot fact (facts.SLOTS) of value v is replaced by the merged view of v written stated and v written denied (in both
    orders) - tests/v2/test_combination.overfilled's form, to which tests/v2/test_facts pins engine/facts._overfilled -
    and by each of its written facts read alone (unresolved for slot_overfull, v claimed, supported or negated): no code
    is READY or EXCLUDED under the view that is not READY, resp. EXCLUDED, under each written fact alone. 4.4's
    generator writes [v, another value] only, so it never wrote one value both ways; as built, four states released
    (43239 three times, beside a competing_codes rival; 45380 once), where the view's empty negated_values left each
    possibility reader reading v alone. The step's NOTES, question Q1R."""

    def test_no_view_of_one_value_written_both_ways_is_stronger_than_a_written_fact(self):
        from tests.v2.test_combination import overfilled

        S_, N_ = ct.FactState.SUPPORTED, ct.FactState.NEGATED

        def written(state, found):
            return Fact(result=Res.UNRESOLVED, value=found.value, state=state, options=(),
                        reasons=(ct.Reason.SLOT_OVERFULL,), spans=found.spans, cited=found.cited,
                        inherited_from=found.inherited_from)

        checked = 0
        for name, R, codes in fixtures():
            for table in TABLES.values():
                for subject, attributes in _objects(R, table):
                    family = subject.family if subject is not None else None
                    for attribute, members in attributes.items():
                        if (family, attribute) not in F.SLOTS or len(members) != 1:
                            continue
                        found = members[0]
                        if found.result is not Res.SUPPORTED or found.value is None:
                            continue

                        def outcome(new):
                            got = assessed(_with(R, table, subject, {**attributes, attribute: (new,)}), codes)
                            return ready(got), excluded(got)

                        alone = [outcome(written(state, found)) for state in (S_, N_)]
                        for order in ((S_, N_), (N_, S_)):
                            view = replace(overfilled(*((state, found.value) for state in order)), spans=found.spans,
                                           cited=found.cited, inherited_from=found.inherited_from)
                            got = outcome(view)
                            where = f'{name} | {_subject(subject)} {attribute.value} = {found.value} | {order}'
                            for each in alone:
                                self.assertLessEqual(got[0], each[0], where)
                                self.assertLessEqual(got[1], each[1], where)
                            checked += 1
        self.assertGreater(checked, 500)


def waiting_releases() -> list:
    """Every release and shrunk claim an open question governs (OPEN_RELEASES) that a single weakening of a fixture
    reaches under the fixture's own verdicts, as (code, question, label) - what OpenQuestionsTests fails on."""
    waiting: list = []
    case = PMonoTests('test_every_single_weakening_of_every_fixture')
    for _name, R, codes in fixtures():
        base = assessed(R, codes)
        for label, changed, what in weakenings(R):
            PMonoTests.check(case, base, assessed(changed, codes), label, what, R, waiting=waiting)
    return waiting


class OpenQuestionsTests(SimpleTestCase):
    """The releases a design question governs that the owner has not ruled (OPEN_RELEASES), RED BY DESIGN while one is
    seen (DECISIONS D245: "A release no ruling names still fails"; P6), so the gate goes to the owner rather than into a
    pass; the other P-MONO tests route these releases here and keep guarding every other. DECISIONS D264 emptied
    OPEN_RELEASES (refute-6a-r1 F3: D264_SITE; F5: D262_STATUS), and DECISIONS D293 emptied it again (step f3e's
    question Q-ERASE, 4.4's value-erasing contradictions in a ruled class: option (a), D293_ERASE); its positive control
    plants one more."""
    maxDiff = None  # the failure names every waiting release, with its question

    def test_every_drawn_verdict_part_is_a_class_and_every_fixture_with_controls_is_in_one(self):
        parts = verdict_parts()
        classes = [cls for cls in globals().values() if isinstance(cls, type) and issubclass(cls, SimpleTestCase)
                   and hasattr(cls, 'test_every_single_weakening_under_every_drawn_verdict')]
        self.assertEqual(sorted(cls.test_every_single_weakening_under_every_drawn_verdict.part for cls in classes),
                         list(range(VERDICT_PARTS)))
        self.assertEqual(sorted(name for part in parts for name in part),
                         sorted(name for name, R, _codes in fixtures() if R.pair_controls))
        self.assertTrue(all(len(R.pair_controls) <= VERDICTS_ENUMERATED for _name, R, _codes in fixtures()))
        R, _codes = fixture('two esophageal dilations and a duodenal one (D262, r4a QM)')
        patterns = drawn_verdicts(R)
        self.assertEqual(len(patterns), 2 ** len(R.pair_controls))
        self.assertTrue(any(drawn.pair_controls[(EF.E(1), A.TARGET_PLACES, Landmark.DUODENAL_BULB)] is False
                            and sum(not value for value in drawn.pair_controls.values()) == 1
                            for _label, drawn in patterns))  # refute-6a-r1 F2's state is one of them

    def test_no_release_waits_on_an_open_question(self):
        """Every single weakening of every fixture under its own verdicts: a release or a shrunk claim an open question
        governs fails here, named with its question and its weakening, until the owner rules - (a) accepted: the entry
        moves from OPEN_RELEASES to ACCEPTED_RELEASES under its ruling; (b) the engine repaired: the release is gone.
        OPEN_RELEASES is empty on this tree (DECISIONS D293 ruled Q-ERASE, option (a))."""
        self.assertEqual([f'{code} under {label}: {question}' for code, question, label in waiting_releases()], [])
        self.assertEqual(OPEN_RELEASES, ())  # D264: empty; checked after the routing, so a failure names what waits

    def test_the_guard_still_fails_on_an_unruled_release(self):
        """The guard's positive control: with D264_SITE taken out of the rulings and planted as an open question for the
        call (its own predicate standing for the question's), the single weakenings of the fixtures' own verdicts route
        F3's and its lesion form's releases and shrunk claims to the question - exactly the eight D264 ruled - and
        P-MONO's check, told nothing to route, fails on them naming the question. So an empty OPEN_RELEASES is a ruled
        state, not a guard that cannot fire."""
        question = 'OPEN (planted for the guard\'s control): a site code released or a claim shrunk by a deleted place'

        def planted(label, what, code, R):
            return _site_deletion(label, what, R) is not None

        accepted = tuple(entry for entry in ACCEPTED_RELEASES if entry[1] != D264_SITE)
        with mock.patch(f'{__name__}.ACCEPTED_RELEASES', accepted), mock.patch(f'{__name__}.ACCEPTED_SHRINKS', ()), \
                mock.patch(f'{__name__}.OPEN_RELEASES', (('planted', question, planted), *OPEN_RELEASES)):
            waiting = waiting_releases()
            self.assertEqual(sorted((code, label) for code, found, label in waiting if found == question),
                             [('43245', 'deleted E1 target.places[0]'), ('43245', 'deleted E1 target.places[1] (a claim '
                                                                                   'shrank)'),
                              ('43245', 'deleted L1 places[0]'), ('43245', 'deleted L1 places[1] (a claim shrank)'),
                              ('43249', 'deleted E1 target.places[0]'), ('43249', 'deleted E1 target.places[0] (a '
                                                                                   'claim shrank)'),
                              ('43249', 'deleted L1 places[0]'), ('43249', 'deleted L1 places[0] (a claim shrank)')])
            R, codes = fixture(F3_FIXTURE)
            [(label, changed, what)] = [found for found in weakenings(R) if found[0] == 'deleted E1 target.places[0]']
            with self.assertRaises(AssertionError) as caught:
                PMonoTests.check(self, assessed(R, codes), assessed(changed, codes), label, what, R)
            self.assertIn(question, str(caught.exception))


class IndependenceTests(SimpleTestCase):
    """9.4 P-INDEP over the engine as assembled: test_assess's harness over every fixture here."""

    def test_a_fact_outside_a_codes_dependencies_never_moves_it(self):
        checked = 0
        for name, R, codes in fixtures():
            base = assessed(R, codes)
            for family, subject, attribute, index, changed in TA.perturbations(R):
                after = assessed(changed, codes)
                for before in base.codes:
                    if (family, attribute) in TA.closure(before.code):
                        continue
                    checked += 1
                    with self.subTest(fixture=name, code=before.code, subject=str(subject), attribute=attribute.value,
                                      variant=index):
                        self.assertEqual(TA.outcome(after.code(before.key)), TA.outcome(before))
        self.assertGreater(checked, 600)


class SettleTests(TS.Case):
    """9.4 P-INDEP-SETTLE and P-DEMOTE through settle, with test_settle's reference helpers (repair r3a's R-E)."""

    def test_p_indep_settle_over_the_notes(self):
        independence = TS.IndependenceTests.independence
        counted = independence(self, TS.NOTE, TS.note_answer())
        self.assertTrue(all(count > 10 for count in counted.values()), counted)
        counted = independence(self, TS.NOTE, TS.identical_answer())
        self.assertGreater(sum(counted.values()), 50)

    @hypothesis.settings(max_examples=20, deadline=None, derandomize=True, database=None,
                         suppress_health_check=list(hypothesis.HealthCheck))
    @hypothesis.given(st.lists(st.one_of(st.none(), TS.VERDICT), min_size=200, max_size=200))
    def test_p_demote(self, answers):
        TS.DemotionTests.test_p_demote_pass_two_never_creates_changes_or_upgrades_a_fact.hypothesis.inner_test(
            self, answers)


# --- P-TEXTFREE (5.7 measure 6) ------------------------------------------------------------------------------------------

def _x(text: str) -> str:
    return 'x' * len(text)


def _decision(assessment) -> str:
    """Everything P-TEXTFREE keeps byte-identical, as canonical JSON: per code its status, item fact key and message,
    held facts and witnesses (the per-code rule's evaluation trace and support), the combination, the coverage and the
    service questions - never a rendered sentence."""
    codes = [{'code': found.code, 'key': found.key, 'status': AS.jsonable(found.status),
              'item': AS.jsonable((found.item.held, found.item.message)) if found.item is not None else None,
              'held': AS.jsonable(found.held_facts),
              'evaluation': AS.jsonable(found.evaluation) if getattr(found, 'evaluation', None) is not None else None}
             for found in assessment.codes]
    body = {'codes': codes, 'combination': AS.jsonable(assessment.combination),
            'coverage': AS.jsonable(assessment.coverage),
            'questions': AS.jsonable(assessment.service_questions)}
    return json.dumps(body, sort_keys=True, default=repr)


def _x_proposals(codes, text: str):
    """The proposals of ``codes`` with each quote's text replaced by x (same lengths, same spans): R1's results given."""
    found = TA.corti(*codes, text=text)
    return replace(found, codes=tuple(replace(code, evidence=tuple(replace(span, text=_x(span.text))
                                                                   for span in code.evidence))
                                      for code in found.codes))


class TextFreeTests(SimpleTestCase):
    """5.7 measure 6, P-TEXTFREE: the engine reads no text (module docstring)."""

    def textfree(self, R, codes):
        text = TA.TEXT
        plain = TA.run(R, *codes, text=text)
        blind = TA.run(R, *codes, text=_x(text), provider=_x_proposals(codes, text))
        return plain, blind

    def test_every_outcome_is_byte_identical_over_an_x_text(self):
        compared = 0
        for name, R, codes in fixtures():
            with self.subTest(fixture=name):
                plain, blind = self.textfree(R, codes)
                self.assertEqual(_decision(blind), _decision(plain))
                self.assertEqual([found.status for found in blind.codes], [found.status for found in plain.codes])
                compared += len(plain.codes)
        self.assertGreater(compared, 10)

    def test_the_positive_control_a_rule_that_reads_the_text_turns_it_red(self):
        from studio.interpretation.engine import evaluate

        name, R, codes = fixtures()[0]
        seen = {}
        real_assess, real_decide = AS.assess_facts, evaluate.decide

        def remember(*args, **kwargs):
            seen['text'] = kwargs.get('text', '')
            return real_assess(*args, **kwargs)

        def reads_the_text(code, kept, R, **kwargs):  # the planted reader: x's anywhere hold the code
            found = real_decide(code, kept, R, **kwargs)
            if seen.get('text', '').startswith('x'):
                return replace(found, supporting=())
            return found

        with mock.patch.object(AS, 'assess_facts', remember), mock.patch.object(evaluate, 'decide', reads_the_text):
            plain = TA.run(R, *codes, text=TA.TEXT)
            remember(TA.dated(R), date_of_service=TA.DAY, text=_x(TA.TEXT), pages=(), integrity=TA.Integrity(),
                     provider_status='succeeded', proposals=_x_proposals(codes, TA.TEXT), reference=TA.Lookup(),
                     member=TA.ENTERED, label=lambda session: str(session.id), participants=(), second=None,
                     answers=())
            blind = TA.run(R, *codes, text=_x(TA.TEXT), provider=_x_proposals(codes, TA.TEXT))
        self.assertNotEqual(_decision(blind), _decision(plain))  # the property sees a rule that reads the text


class DeterminismTests(SimpleTestCase):
    """9.4 P-DET: identical inputs give byte-identical assessments."""

    def digest(self, assessment) -> str:
        return hashlib.sha256(json.dumps(AS.jsonable(assessment), sort_keys=True).encode()).hexdigest()

    def test_identical_inputs_give_byte_identical_assessments(self):
        for name, R, codes in fixtures():
            with self.subTest(fixture=name):
                rebuilt = replace(R, **{table: dict(getattr(R, table)) for table in ('events', 'sessions', 'lesions',
                                                                                     'anatomy')})
                first, second = self.digest(assessed(R, codes)), self.digest(assessed(rebuilt, codes))
                self.assertEqual(first, second)
                self.assertEqual(self.digest(assessed(R, codes)), first)  # and again, the same objects


# --- P-READSET and P-CONTROLLED ----------------------------------------------------------------------------------------

def recorded_reads(R, codes) -> tuple[set, AS.Assessment]:
    """Every (object family, attribute) the engine reads through engine/facts' fact and members while it assesses ``R``
    - questions.fill's display reads left out (repair 4a's R6: they are made after the decision, for its sentence)."""
    reads, filling = set(), []
    real_fact, real_members, real_fill = F.fact, F.members, Q.fill

    def family_of(subject):
        family = getattr(subject, 'family', None)
        return family if family is not None else None

    def fact(R_, subject, attribute, *args, **kwargs):
        if not filling:
            reads.add((family_of(subject), attribute))
        return real_fact(R_, subject, attribute, *args, **kwargs)

    def members(R_, subject, attribute, *args, **kwargs):
        if not filling:
            reads.add((family_of(subject), attribute))
        return real_members(R_, subject, attribute, *args, **kwargs)

    def fill(*args, **kwargs):
        filling.append(1)
        try:
            return real_fill(*args, **kwargs)
        finally:
            filling.pop()

    with mock.patch.object(F, 'fact', fact), mock.patch.object(F, 'members', members), \
            mock.patch.object(Q, 'fill', fill):
        found = assessed(R, codes)
    return reads, found


def claimed() -> set:
    """(object family, attribute) of every claim CLAIMED makes (requirements.CLAIMED, by its object class: an act's and
    a statement's on the event family, the encounter's on no family)."""
    families = {RQ.ObjectClass.ACT: IdFamily.EVENT, RQ.ObjectClass.STATEMENT: IdFamily.EVENT,
                RQ.ObjectClass.SESSION: IdFamily.SESSION, RQ.ObjectClass.LESION: IdFamily.LESION,
                RQ.ObjectClass.ANATOMY: IdFamily.ANATOMY, RQ.ObjectClass.ENCOUNTER: None}
    return {(families[object_class], entry.attribute) for object_class, entries in RQ.CLAIMED.items()
            for entry in entries}


class ReadSetTests(SimpleTestCase):
    def test_every_attribute_a_rule_reads_is_claimed_for_its_object_class(self):
        allowed = claimed()
        self.assertTrue(allowed)
        unread = set()
        for name, R, codes in fixtures():
            reads, _ = recorded_reads(R, codes)
            self.assertTrue(reads, name)  # the proxy saw the rules' reads
            outside = {(family, attribute) for family, attribute in reads
                       if (family, attribute) not in allowed and family is not None}
            unread |= outside
        self.assertEqual(unread, set())


_CLASS_FAMILY = {'act': IdFamily.EVENT, 'statement': IdFamily.EVENT, 'session': IdFamily.SESSION,
                 'lesion': IdFamily.LESION, 'anatomy': IdFamily.ANATOMY, 'encounter': None}


def controlled() -> set:
    """(object family, attribute) of every claim a control generator covers (contract/claims' CONTROLS), the pair
    controls (target.places and target.lesion, 3.2.3 [R:SC-B]) and the completeness claim (an upper EUS session's
    stations), or UNCONTROLLED names with its reason."""
    out = {(_CLASS_FAMILY[rule.object_class.value], rule.attribute) for rule in CL.CONTROLS}
    out |= {(_CLASS_FAMILY[item.object_class.value], item.attribute) for item in CL.UNCONTROLLED}
    out |= {(IdFamily.EVENT, A.TARGET_PLACES), (IdFamily.EVENT, A.TARGET_LESION), (IdFamily.SESSION, A.STATIONS)}
    return out


class ControlledTests(SimpleTestCase):
    def test_every_attribute_a_ready_or_exclusion_path_reads_has_a_control_or_its_reason(self):
        """9.4 P-CONTROLLED [R:SC-C], engine-wide: each fixture assessed again with only the codes its assessment made
        READY or EXCLUDED proposed, and every (object family, attribute) the engine read meanwhile (P-READSET's
        recording) is controlled or on UNCONTROLLED - test_claims holds the finer check per kind and value."""
        allowed = controlled()
        missing, paths = set(), 0
        for name, R, codes in fixtures():
            base = assessed(R, codes)
            decided = {found.code for found in base.codes if found.status in (Outcome.READY, Outcome.EXCLUDED)}
            chosen = tuple(item for item in codes if item[0] in decided)
            if not chosen:
                continue
            paths += 1
            reads, _ = recorded_reads(R, chosen)
            missing |= {item for item in reads if item[0] is not None and item not in allowed}
        self.assertGreaterEqual(paths, 4)
        self.assertEqual(missing, set())


from tests.v2 import test_pairing as TPAIR  # noqa: E402 - the pairing properties, below


def own_wrapper(method):
    """test_pairing's @given test ``method`` under a wrapper of its own: the same inner test, the same strategies and the
    same settings object. Hypothesis refuses one wrapped test run by two executors (HealthCheck.differing_executors),
    which an inherited wrapper is whenever test_pairing and this module run in one process (the merge gate's tests.v2)."""
    handle = method.hypothesis
    return method._hypothesis_internal_use_settings(hypothesis.given(**handle._given_kwargs)(handle.inner_test))


# The pairing-level releases the rulings accept (DECISIONS D245, D262), each with the condition its ruling states, checked
# per pair (``pair_ruling``): r2d-2's Q2 (option (a)) and r3d's Q1 case (b) (D228_PLACE, under D228 and D238 - its shape
# with no control at all being R3D-NC's, D262) only when no place pair control between the two objects is left
# unrejected; r2d-2's Q3 (option (b)) is no 9.4 weakening at all; D228_STATUS (D262: repair r3d's R3D-ST option (a),
# 6a's Q1; "An inherited act whose status is weakened to unresolved moves into D228's arm") only for an inherited act of
# another date or performer, no place pair control between the two left unrejected (D238), as case (b) is.
NOT_A_WEAKENING = "DECISIONS D245 (repair r2d-2's Q3, option (b)): a deleted member that was not established, no weakening"
RULED_PAIR_RELEASES = {TPAIR.R2D_Q2: D245_Q2, TPAIR.R2D_Q3: NOT_A_WEAKENING, TPAIR.D228_PLACE: D245_B,
                       TPAIR.D228_STATUS: D262_STATUS}
PAIR_QUESTIONS = {
    TPAIR.D228_STATUS: "DECISIONS D262 (D228_STATUS, repair r3d's R3D-ST option (a)): accepted only for an inherited act "
                       'of another date or performer, with no place pair control between the two left unrejected '
                       '(D238: an unrejected one holds)',
    TPAIR.D228_PLACE: "DECISIONS D238 (built by repair r3d): beside a place pair control not rejected D228's arm holds",
    TPAIR.R2D_Q2: "DECISIONS D220 and D245 (repair r2d-2's Q2): accepted only with every place pair control between the "
                  'two rejected',
}


def pair_ruling(name, R, how, statement, act_):
    """The ruling that accepts the release test_pairing names ``name`` for the pair (``statement``, ``act_``) under the
    weakening ``how`` of ``R`` (DECISIONS D245), None when no ruling does."""
    if name == TPAIR.R2D_Q3 and how[0] == 'place' and not F.established(how[3]):
        return NOT_A_WEAKENING
    if name in (TPAIR.R2D_Q2, TPAIR.D228_PLACE) and how[0] == 'place':
        return RULED_PAIR_RELEASES[name] if every_place_control_rejected(R, statement, act_) else None
    if name == TPAIR.D228_STATUS and how[0] == 'status':
        accepted = _inherited_statement(R, statement) and every_place_control_rejected(R, statement, act_)
        return RULED_PAIR_RELEASES[name] if accepted else None
    return None


def ruled_named_release(R, weak, how, released):
    """test_pairing.named_release held to the rulings (DECISIONS D245, ``pair_ruling``), pair by pair: a deletion of a
    member that was not established is no weakening (r2d-2's Q3, option (b)), so whatever it releases is that doubt's
    own; a release test_pairing names that its ruling does not accept for that pair raises, naming the ruling that
    governs it (never a silent pass); a release test_pairing cannot name stays None, as there."""
    if how[0] == 'place' and not F.established(how[3]):
        return frozenset({NOT_A_WEAKENING})
    if P.unlisted_pairs(R, released):
        return None
    names, unruled = set(), []
    for pair in P.pairs_of(R, released):
        if pair.relation is P.Relation.INDEPENDENT:
            continue
        name = TPAIR._pair_release(R, weak, how, pair.statement, released)
        if name is None:
            return None
        if pair_ruling(name, R, how, pair.statement, released) is None:
            unruled.append(name)
        names.add(name)
    if unruled:
        governing = sorted({PAIR_QUESTIONS.get(name, 'no ruling names it') for name in unruled})
        raise AssertionError(f'{released!r} released by {how!r}: test_pairing names {sorted(set(unruled))}, which no '
                             f'ruling accepts for this pair ({governing})')
    return frozenset(names) or None


OVERRIDDEN = ('test_p_unknown_target',)  # held to the rulings in PairingTests itself (below)


class PairingTests(TPAIR.PropertyTests):
    """9.4 P-ANY-ROW, P-UNKNOWN-TARGET and P-UNKNOWN-KIND through engine/pairing as the engine calls it: test_pairing's
    PropertyTests, run here as 9.4's (its generated FactSets, its proving scenes); each @given test under its own
    wrapper (``own_wrapper``, set below the class). Held to the rulings: its P-MONO releases through
    ``ruled_named_release`` (DECISIONS D245), and P-UNKNOWN-TARGET (overridden here) excepts in D228's arm only a pair
    control NOT GENERATED - D228 sets that arm apart "without pair controls" and D238 does not require a missing one -
    never a control generated and not rejected (9.4's clause; D238, built by repair r3d: an unrejected one holds -
    repair r3d's Q1 case (a))."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(TPAIR, 'named_release', ruled_named_release)
        patcher.start()
        self.addCleanup(patcher.stop)

    @hypothesis.settings(**TPAIR.SETTINGS)
    @hypothesis.given(st.sampled_from(sorted(TPAIR.APART, key=repr)), st.data())
    def test_p_unknown_target(self, base, data):
        """P-UNKNOWN-TARGET (9.4) as test_pairing states it - an unknown, unresolved, doubted or contradicted target on
        either side, or a pair control not rejected, never makes the target row yield INDEPENDENT, for every combination
        of the other rows' states - with D228's arm excepted only as DECISIONS D228 and D238 rule it: there a pair
        control NOT GENERATED leaves the pair apart, while a control generated and NOT REJECTED must not (D238, repair
        r3d's Q1 case (a): repair r3d built the arm that reads the controls that exist)."""
        T = TPAIR
        arm, mode = base
        events, lesions, controls, facts_of_arm = T.APART[base]()
        other = data.draw(T.other_rows(T.P.Row.TARGET))
        events[T.E1] = {**events[T.E1], **T.event(**other)}
        events[T.E2] = {**events[T.E2], **T.event(**{k: v for k, v in data.draw(T.other_rows(T.P.Row.TARGET)).items()})}
        R = T.build(events, lesions=lesions, controls=controls)
        self.assertEqual(T.row_of(R, T.P.Row.TARGET), T.INDEPENDENT, (arm, mode))
        what = data.draw(st.sampled_from(sorted(facts_of_arm, key=repr) + sorted(controls, key=repr)))
        if what in controls:
            if data.draw(st.booleans()):
                controls = {**controls, what: False}  # generated and not rejected: never INDEPENDENT (9.4, D238)
            else:
                controls = {key: value for key, value in controls.items() if key != what}
                if mode == 'act-filed':  # D228 and D238: that arm is set apart without a missing control
                    self.assertEqual(T.row_of(T.build(events, lesions=lesions, controls=controls), T.P.Row.TARGET),
                                     T.INDEPENDENT, (arm, mode, what))
                    return
        else:
            table, subject, attribute, index = what
            source = events if table == 'event' else lesions
            members = list(source[subject][attribute])
            if attribute in (A.TARGET_PLACES, A.SCOPE_SEGMENT) and data.draw(st.booleans()):
                del members[index]  # a short list is never evidence (SC-B); a listed target deleted is a narrower list
            else:
                found = members[index]
                members[index] = T.in_state(data.draw(st.sampled_from(T.NOT_ESTABLISHED)), found.value, found.value)
            source[subject] = {**source[subject], attribute: tuple(members)}
        R = T.build(events, lesions=lesions, controls=controls)
        self.assertIsNot(T.row_of(R, T.P.Row.TARGET), T.INDEPENDENT, (
            arm, mode, what, "DECISIONS D238 (repair r3d's Q1, case (a)): D228's arm set apart beside a pair control not "
            'rejected - D238, built by repair r3d, holds the pair there' if mode == 'act-filed'
            else 'no ruling and no open question names it'))

    def test_every_given_test_runs_under_its_own_wrapper_of_the_same_test(self):
        given = [name for name, method in vars(TPAIR.PropertyTests).items()
                 if getattr(method, 'is_hypothesis_test', False)]
        self.assertGreaterEqual(len(given), 5)  # P-ANY-ROW, P-UNKNOWN-TARGET, the two P-MONO, no independent row
        self.assertLessEqual(set(OVERRIDDEN), set(given))
        for name in given:
            theirs, ours = vars(TPAIR.PropertyTests)[name], vars(PairingTests)[name]
            with self.subTest(test=name):
                self.assertIsNot(ours, theirs)
                if name in OVERRIDDEN:  # this module's own test, held to the rulings
                    self.assertIsNot(ours.hypothesis.inner_test, theirs.hypothesis.inner_test)
                    continue
                self.assertIs(ours.hypothesis.inner_test, theirs.hypothesis.inner_test)
                self.assertEqual(ours.hypothesis._given_kwargs, theirs.hypothesis._given_kwargs)
                self.assertIs(ours._hypothesis_internal_use_settings, theirs._hypothesis_internal_use_settings)

    def test_the_rulings_accept_each_named_release_by_its_own_condition(self):
        """DECISIONS D245 at the pairing level, through test_pairing's own builders. r2d-2's Q3 (option (b)): its minimal
        input (ScBTests: a single-target denial filed [rectum, cecum (unresolved)] beside a biopsy in the sigmoid colon,
        every control rejected) - deleting the cecum releases the biopsy, test_pairing names it R2D_Q3, and it is no
        weakening (accepted without asking test_pairing). r2d-2's Q2 and D228_PLACE are accepted for a pair only when
        every place pair control between the two is rejected, and refused (None) beside one that is not. D228_STATUS
        (DECISIONS D262: repair r3d's R3D-ST option (a), 6a's Q1) is accepted only for an inherited act of another date
        or performer, no place pair control between the two left unrejected: R3D-ST's input - a status weakening that
        moves an act of another clinician (inherited) into D228's arm with no pair control at all (D211) - releases its
        pair, test_pairing names it D228_STATUS, and D262 accepts it; a denial's status (no inherited act), the same act
        beside a place control not rejected (D238), and the other clinician stated in the act's own sentence are refused
        (None)."""
        T = TPAIR
        statement = T.denial(kind=T.sup(Kind.BIOPSY), breadth=T.sup(ct.Breadth.SINGLE_TARGET),
                             places=(T.sup(Landmark.RECTUM), T.unres(Landmark.CECUM)))
        controls = T.claims_pair_controls(T.E1, (Landmark.RECTUM, Landmark.CECUM), T.E2, (Landmark.SIGMOID_COLON,),
                                          lambda subject, place: True)
        R = T.build({T.E1: statement, T.E2: T.sc_b_act((Landmark.SIGMOID_COLON,))}, controls=controls)
        weak = T.build({T.E1: {**statement, A.TARGET_PLACES: (T.sup(Landmark.RECTUM),)}, T.E2: R.events[T.E2]},
                       controls=controls)
        how = ('place', T.E1, 1, T.unres(Landmark.CECUM))
        self.assertEqual(T.held(R) - T.held(weak), {T.E2})
        self.assertEqual(ruled_named_release(R, weak, how, T.E2), frozenset({NOT_A_WEAKENING}))
        self.assertIsNone(ruled_named_release(R, weak, ('fact', T.E1, A.KIND, 0), T.E2))
        # Q2 and D228_PLACE by their condition: every place control between the two rejected, or None
        place = ('place', T.E1, 0, T.sup(Landmark.RECTUM))
        rejected = {key: True for key in controls}
        unrejected = {**rejected, next(iter(sorted(controls, key=repr))): False}
        for name in (T.R2D_Q2, T.D228_PLACE):
            with self.subTest(name=name):
                self.assertEqual(pair_ruling(name, T.build(R.events, controls=rejected), place, T.E1, T.E2),
                                 RULED_PAIR_RELEASES[name])
                self.assertIsNone(pair_ruling(name, T.build(R.events, controls=unrejected), place, T.E1, T.E2))
                self.assertIsNone(pair_ruling(name, T.build(R.events, controls=rejected), ('status', T.E1), T.E1,
                                              T.E2))
        self.assertIsNone(pair_ruling(T.D228_STATUS, T.build(R.events, controls=rejected), ('status', T.E1), T.E1,
                                      T.E2))  # E1 a denial: no inherited act of another date or performer
        # D228_STATUS with no pair control at all (D211), R3D-ST's input: released, named, and accepted by D262
        other = T.act(kind=T.sup(Kind.BIOPSY), performer=T.sup(T.OTHER_CLINICIAN, inherited_from=T.N1),
                      lesion=T.SILENT, device=T.SILENT, places=(T.sup(Landmark.RECTUM),))
        R = T.build({T.E1: other, T.E2: T.sc_b_act((Landmark.SIGMOID_COLON,))})
        weak = T.build({T.E1: {**other, A.STATUS: (T.unres(T.PERFORMED),)}, T.E2: R.events[T.E2]})
        self.assertEqual(T.held(R) - T.held(weak), {T.E2})
        self.assertEqual(TPAIR._pair_release(R, weak, ('status', T.E1), T.E1, T.E2), T.D228_STATUS)
        self.assertEqual(pair_ruling(T.D228_STATUS, R, ('status', T.E1), T.E1, T.E2), D262_STATUS)
        self.assertEqual(ruled_named_release(R, weak, ('status', T.E1), T.E2), frozenset({T.D228_STATUS}))
        # beside a place control not rejected: refused by the ruling's condition (and D238 holds the pair: case (c)'s test)
        held = T.build(R.events, controls={(T.E2, A.TARGET_PLACES, Landmark.RECTUM): False})
        self.assertIsNone(pair_ruling(T.D228_STATUS, held, ('status', T.E1), T.E1, T.E2))
        # the other clinician in the act's own sentence: no inherited act, refused
        own = T.build({T.E1: {**other, A.PERFORMER: (T.sup(T.OTHER_CLINICIAN),)}, T.E2: R.events[T.E2]})
        self.assertIsNone(pair_ruling(T.D228_STATUS, own, ('status', T.E1), T.E1, T.E2))

    def case_b(self, rejected):
        """Repair r3d's Q1 case (b) (its NOTES' input): a possible statement E1 filed [sigmoid colon, transverse colon]
        beside a biopsy E2 in the transverse colon, with the one pair control claims makes - "This act was done in the
        sigmoid colon." asked of E2 - rejected or not; and the same with the statement's transverse colon deleted, the
        control left as it was. (R, weak, how)."""
        T = TPAIR
        statement = T.act(kind=T.sup(Kind.BIOPSY), status=T.unres(T.PERFORMED), lesion=T.SILENT, device=T.SILENT,
                          places=(T.sup(Landmark.SIGMOID_COLON), T.sup(Landmark.TRANSVERSE_COLON)))
        controls = T.claims_pair_controls(T.E1, (Landmark.SIGMOID_COLON, Landmark.TRANSVERSE_COLON), T.E2,
                                          (Landmark.TRANSVERSE_COLON,), lambda subject, place: rejected)
        self.assertEqual(set(controls), {(T.E2, A.TARGET_PLACES, Landmark.SIGMOID_COLON)})
        R = T.build({T.E1: statement, T.E2: T.sc_b_act((Landmark.TRANSVERSE_COLON,))}, controls=controls)
        weak = T.build({T.E1: {**statement, A.TARGET_PLACES: (T.sup(Landmark.SIGMOID_COLON),)}, T.E2: R.events[T.E2]},
                       controls=controls)
        return R, weak, ('place', T.E1, 1, T.sup(Landmark.TRANSVERSE_COLON))

    def test_d245_case_b_a_place_deletion_in_d228s_arm_is_accepted_when_no_control_is_left_unrejected(self):
        """DECISIONS D245 (r3d's Q1 case (b), accepted under D228 and D238): with the one pair control rejected (or none
        generated: D211 makes none for two acts of one kind), deleting the statement's transverse colon releases the
        biopsy; test_pairing names it D228_PLACE, and the ruling accepts it."""
        T = TPAIR
        for controls in ('rejected', 'none generated'):
            with self.subTest(controls=controls):
                R, weak, how = self.case_b(rejected=True)
                if controls == 'none generated':
                    R, weak = replace(R, pair_controls={}), replace(weak, pair_controls={})
                self.assertIn(T.E2, T.held(R))
                self.assertNotIn(T.E2, T.held(weak))
                self.assertEqual(ruled_named_release(R, weak, how, T.E2), frozenset({T.D228_PLACE}))

    def test_d238_a_place_deletion_beside_an_unrejected_control_in_d228s_arm_releases_nothing(self):
        """DECISIONS D238 (its own defect's shape: a place left out of a possible statement's list): r3d's case (b) with
        the pair control "This act was done in the sigmoid colon." NOT rejected - D228's arm reads the pair controls that
        exist and an unrejected one holds, so deleting the statement's transverse colon leaves the biopsy held (D238's
        arm, built by repair r3d)."""
        T = TPAIR
        R, weak, how = self.case_b(rejected=False)
        self.assertIn(T.E2, T.held(R))
        self.assertIn(T.E2, T.held(weak), "DECISIONS D238 (repair r3d's Q1): D228's arm set the pair apart beside a pair "
                                          'control not rejected - D238, built by repair r3d, holds the pair there')

    def test_d238_case_c_a_status_weakening_beside_an_unrejected_control_releases_nothing(self):
        """DECISIONS D245 and D238 (repair r3d's Q1, case (c), its NOTES' input): an act told under another clinician
        (inherited) in the rectum beside the team's biopsy in the sigmoid colon, held, with "This act was done in the
        rectum." asked of the team's biopsy NOT rejected; weakening the first act's status moves it into D228's arm,
        which reads the pair controls that exist (D238, built by repair r3d), so the unrejected one keeps the biopsy
        held."""
        T = TPAIR
        other = T.act(kind=T.sup(Kind.BIOPSY), performer=T.sup(T.OTHER_CLINICIAN, inherited_from=T.N1),
                      lesion=T.SILENT, device=T.SILENT, places=(T.sup(Landmark.RECTUM),))
        controls = T.claims_pair_controls(T.E1, (Landmark.RECTUM,), T.E2, (Landmark.SIGMOID_COLON,),
                                          lambda subject, place: True)
        controls[(T.E2, A.TARGET_PLACES, Landmark.RECTUM)] = False
        R = T.build({T.E1: other, T.E2: T.sc_b_act((Landmark.SIGMOID_COLON,))}, controls=controls)
        weak = T.build({T.E1: {**other, A.STATUS: (T.unres(T.PERFORMED),)}, T.E2: R.events[T.E2]}, controls=controls)
        self.assertIn(T.E2, T.held(R))
        self.assertIn(T.E2, T.held(weak), "DECISIONS D238 (repair r3d's Q1, case (c)): D228's arm set the pair apart "
                                          'beside a pair control not rejected - D238, built by repair r3d, holds the '
                                          'pair there')


for _name, _method in list(vars(TPAIR.PropertyTests).items()):
    if getattr(_method, 'is_hypothesis_test', False) and _name not in OVERRIDDEN:
        setattr(PairingTests, _name, own_wrapper(_method))


# --- P-WORDED (DECISIONS D246, a merge-gate property; the lead's seam finding L1) ------------------------------------

WORDED_MODULES = ('tests.v2.test_assess', 'tests.v2.test_combination', 'tests.v2.test_evaluate',
                  'tests.v2.test_refutation_cases', 'tests.v2.test_gate6', 'tests.v2.test_failure_classes')


@dataclass(frozen=True)
class Scene:
    """One assessment the renderer must word: where it came from (``source``: a test module, or 'p-mono'), how
    (``how``: 'assess' for an assess_facts call a test made, 'decide' or 'combine' for a per-code rule or combination
    scene a test handed the engine directly, assessed here, or P-MONO's label), the FactSet assess_facts read, the
    revision text it was given, and the Assessment."""
    source: str
    how: str
    R: FactSet
    text: str
    assessment: AS.Assessment


def pattern_text(length: int) -> str:
    """test_assess.TEXT's synthetic characters (no words at all), as long as ``length``."""
    return ''.join(chr(97 + (index * 7) % 26) for index in range(max(length, len(TA.TEXT))))


def scene_assessment(R, proposed):
    """(the FactSet, the text, the Assessment) of a scene a test handed the engine directly: assess_facts over ``R`` -
    dated as test_assess.run dates a scene, when it carries no date of service (its other encounter facts kept) - the
    proposal provider selecting each (code, spans) of ``proposed`` on exactly those spans of a synthetic text long
    enough to hold them."""
    text = pattern_text(max([0] + [span.end for _code, spans in proposed for span in spans]))
    if A.DATE_OF_SERVICE not in R.encounter:
        R = replace(R, encounter={**R.encounter, A.DATE_OF_SERVICE: (sup(IsoDate(TA.DAY, ct.Precision.DAY)),)})
    response = NormalizedResponse('corti', 'synthetic@1', codes=tuple(
        ProviderCode('selected', 'CPT', code, '', tuple(EvidenceSpan(0, span.start, span.end, text[span.start:span.end],
                                                                     True) for span in spans))
        for code, spans in proposed))
    return R, text, assessed(R, (), text=text, provider=response)


def harvest(modules=WORDED_MODULES):
    """Every scene the named test modules hand the engine (module docstring, P-WORDED), and the nested run's result:
    their own tests run in this process (unittest, quietly), each OUTERMOST engine/assess.assess_facts call recorded as
    made (its FactSet, text and Assessment), and each evaluate.decide or combination.combine call a test makes itself
    (outside assess_facts) recorded as a scene, then assessed here (``scene_assessment``) - a decide scene with its code
    proposed on its kept spans, a combine scene with each member's code proposed on its supporting acts' anchor units -
    once per distinct (FactSet, proposals). The nested tests' own results are theirs (the gate runs them); what is read
    here is what they handed the engine."""
    from studio.interpretation.engine import combination as CO
    from studio.interpretation.engine import evaluate as EV

    scenes, direct, current, depth = [], [], {'module': ''}, []
    real_assess, real_decide, real_combine = AS.assess_facts, EV.decide, CO.combine
    decide_signature = inspect.signature(real_decide)

    def assess(*args, **kwargs):
        outermost = not depth
        depth.append(1)
        try:
            result = real_assess(*args, **kwargs)
        finally:
            depth.pop()
        if outermost:
            R = args[0] if args else kwargs['R']
            scenes.append(Scene(current['module'], 'assess', R, kwargs.get('text', ''), result))
        return result

    def decide(*args, **kwargs):
        result = real_decide(*args, **kwargs)
        if not depth:
            bound = decide_signature.bind(*args, **kwargs).arguments
            direct.append((current['module'], 'decide', bound['R'], ((bound['code'], tuple(bound['kept'])),)))
        return result

    def combine(members, coding, R):
        result = real_combine(members, coding, R)
        if not depth:
            direct.append((current['module'], 'combine', R, tuple(
                (member.code, tuple(span for event in member.supporting if event in R.anchors
                                    for span in R.anchors[event].units)) for member in members)))
        return result

    class Result(unittest.TestResult):
        def startTest(self, test):  # noqa: N802 - unittest's naming
            current['module'] = type(test).__module__
            super().startTest(test)

    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in modules)
    result = Result()
    with mock.patch.object(AS, 'assess_facts', assess), mock.patch.object(EV, 'decide', decide), \
            mock.patch.object(CO, 'combine', combine):
        suite.run(result)
    seen = set()
    for module, how, R, proposed in direct:
        key = (repr(R), tuple((code, tuple((span.start, span.end) for span in spans)) for code, spans in proposed))
        if key in seen:
            continue
        seen.add(key)
        dated, text, assessment = scene_assessment(R, proposed)
        scenes.append(Scene(module, how, dated, text, assessment))
    return scenes, result


def text_free(item) -> bool:
    """An item read time words afresh (overlay.TEXT_FREE; a date item only when it quotes no statement - overlay's own
    rule, item_slots)."""
    return item.message in overlay.TEXT_FREE and not (item.message is Q.MessageId.SERVICE_DATE and item.fill.statements)


def worded(scenes):
    """(refused, disagreed, counted), by message id: each engine item the renderer (studio/jobs.word_item, as
    _render_code calls it) refuses or raises on - the renderer never raises on an engine item (D246), so any exception
    is the finding -, each TEXT_FREE item read time (overlay._words) words otherwise or not at all, and every item
    counted."""
    refused, disagreed = collections.defaultdict(list), collections.defaultdict(list)
    counted = collections.Counter()
    for scene in scenes:
        combination = scene.assessment.combination
        for found in scene.assessment.codes:
            item = found.item
            if item is None:
                continue
            message = item.message.value
            counted[message] += 1
            where = f'{scene.source} ({scene.how}) {found.code}'
            try:
                spec = jobs.word_item(item, found.key, combination, scene.R, scene.text,
                                      family=AS.family_slug(found.family))
            except Exception as exc:  # noqa: BLE001 - every exception is a refusal the property names
                refused[message].append(f'{where}: {type(exc).__name__}: {exc}')
                continue
            if text_free(item):
                again = overlay._words(item, found.key, combination, scene.R)
                if again is None or (again.fact, again.question, again.reason) != (spec.fact, spec.question,
                                                                                  spec.reason):
                    disagreed[message].append(f'{where}: read time words '
                                              f'{None if again is None else again.question!r}, the renderer '
                                              f'{spec.question!r}')
    return refused, disagreed, counted


def _lines(refused, disagreed, counted) -> dict:
    out = {}
    for message in sorted(set(refused) | set(disagreed)):
        examples = refused.get(message, [])[:2] + disagreed.get(message, [])[:2]
        out[message] = (f'{message}: {len(refused.get(message, []))} of {counted[message]} items refused by the '
                        f'renderer, {len(disagreed.get(message, []))} TEXT_FREE items worded otherwise by read time; '
                        f'e.g. {examples}')
    return out


def findings(scenes) -> dict:
    """P-WORDED's findings by message id (``worded``): one line each, naming the message id, how many of its items the
    renderer refused and read time worded otherwise, and the first examples."""
    return _lines(*worded(scenes))


def _refuse_everything(message, slots, text):
    raise ValueError(f'{message.value} refused (planted).')


def harvest_report(modules=WORDED_MODULES, plant=False) -> dict:
    """P-WORDED over the six modules' scenes (``harvest``, ``worded``), as JSON-able counts and findings - what the
    fresh process hands back. ``plant``: wording planted to refuse every message, the property's own control."""
    scenes, result = harvest(modules)
    with mock.patch.object(wording, 'build', _refuse_everything) if plant else contextlib.nullcontext():
        refused, disagreed, counted = worded(scenes)
    return {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
            'by_module': dict(collections.Counter(scene.source for scene in scenes)),
            'by_how': dict(collections.Counter(scene.how for scene in scenes)), 'counted': dict(counted),
            'items': sum(counted.values()),
            'text_free': sum(1 for scene in scenes for found in scene.assessment.codes
                             if found.item is not None and text_free(found.item)),
            'refused': {key: len(value) for key, value in refused.items()},
            'disagreed': {key: len(value) for key, value in disagreed.items()},
            'findings': _lines(refused, disagreed, counted)}


APP = Path(__file__).resolve().parents[2]
FRESH = ('import json, sys\n'
         'import django\n'
         'django.setup()\n'
         'from django.test.utils import setup_test_environment\n'
         'setup_test_environment()\n'
         'from tests.v2 import test_properties as TP\n'
         'report = TP.harvest_report(tuple(sys.argv[3:]), plant=sys.argv[2] == "plant")\n'
         'with open(sys.argv[1], "w", encoding="utf-8") as out:\n'
         '    out.write(json.dumps(report))\n')


def harvest_in_a_fresh_process(modules=WORDED_MODULES, plant=False) -> dict:
    """``harvest_report`` computed in a FRESH Python process (this interpreter, the app's directory, this process's
    environment), so what the six modules hand the engine never depends on what this process ran before: in the merge
    gate they run first in the same process, and their own state then hides scenes from a second run there
    (test_failure_classes' lru_cached runs make no assess_facts call at all; test_refutation_cases' read them;
    test_combination's and test_gate6's scenes dropped too - the step's first gate, w7r/6a NOTES)."""
    with tempfile.TemporaryDirectory() as directory:
        out = os.path.join(directory, 'report.json')
        done = subprocess.run([sys.executable, '-B', '-c', FRESH, out, 'plant' if plant else 'plain', *modules], cwd=APP,
                              env=dict(os.environ), capture_output=True, text=True, timeout=5400)
        if done.returncode != 0 or not os.path.exists(out):
            raise AssertionError(f'the fresh process failed (exit {done.returncode}): {done.stderr[-3000:]}')
        with open(out, encoding='utf-8') as found:
            return json.load(found)


def p_mono_scenes():
    """P-MONO's FactSets as scenes: every fixture, every single weakening of it, and D220's unrejected-control states and
    their deletions (``beside_unrejected_controls``)."""
    out = []
    for name, R, codes in fixtures():
        out.append(Scene('p-mono', name, R, TA.TEXT, assessed(R, codes)))
        for label, changed, _what in weakenings(R):
            out.append(Scene('p-mono', f'{name}: {label}', changed, TA.TEXT, assessed(changed, codes)))
        for label, base_R, after_R, _what, _path in beside_unrejected_controls(R):
            out.append(Scene('p-mono', f'{name}: {label} (before)', base_R, TA.TEXT, assessed(base_R, codes)))
            out.append(Scene('p-mono', f'{name}: {label}', after_R, TA.TEXT, assessed(after_R, codes)))
    return out


class WordedTests(SimpleTestCase):
    """D246's P-WORDED (module docstring): a merge-gate property. A refusal fails naming its message id, one subtest per
    message id; a TEXT_FREE item read time words otherwise fails the same way."""

    def assert_worded(self, scenes):
        for message, line in findings(scenes).items():
            with self.subTest(message=message):
                self.fail(line)

    def test_every_item_of_the_six_modules_scenes_is_worded_and_read_time_agrees(self):
        report = harvest_in_a_fresh_process()
        context = {key: report[key] for key in ('by_module', 'by_how', 'items', 'tests_run', 'text_free')}
        for module in WORDED_MODULES:  # the harvest read every module: each handed the engine scenes
            with self.subTest(module=module):
                self.assertGreater(report['by_module'].get(module, 0), 0, context)
        self.assertGreater(report['tests_run'], 250, context)
        self.assertGreater(report['by_how'].get('decide', 0), 100, context)  # test_evaluate's scenes, assessed here
        self.assertGreater(report['by_how'].get('combine', 0), 20, context)  # test_combination's, assessed here
        self.assertGreater(report['items'], 3000, context)
        self.assertGreater(report['text_free'], 500, context)  # read time compared on TEXT_FREE items
        for message, line in report['findings'].items():
            with self.subTest(message=message):
                self.fail(line)

    def test_the_fresh_process_names_a_planted_refusal_by_message_id(self):
        """The fresh process's own control: test_refutation_cases' scenes harvested there with wording planted to refuse
        every message - the report names every message id its items hold, each with its count, and nothing passes."""
        report = harvest_in_a_fresh_process(('tests.v2.test_refutation_cases',), plant=True)
        self.assertGreater(report['by_module'].get('tests.v2.test_refutation_cases', 0), 0, report['by_module'])
        self.assertTrue(report['counted'])
        self.assertEqual(set(report['findings']), set(report['counted']))
        self.assertEqual(report['refused'], report['counted'])
        self.assertTrue(all('refused (planted)' in line for line in report['findings'].values()))

    def test_every_item_on_p_mono_factsets_is_worded_and_read_time_agrees(self):
        scenes = p_mono_scenes()
        self.assertGreater(len(scenes), 900)
        self.assertGreater(sum(1 for scene in scenes for found in scene.assessment.codes if found.item is not None),
                           900)
        self.assert_worded(scenes)

    # no shrinking: a refusal names its message id and the drawn states, and shrinking would assess the states again for
    # minutes while the gate waits (the deterministic P-MONO scenes above hold the minimal cases)
    @hypothesis.settings(**SETTINGS, phases=(hypothesis.Phase.explicit, hypothesis.Phase.reuse, hypothesis.Phase.generate))
    @hypothesis.given(st.data())
    def test_every_item_on_random_p_mono_factsets_is_worded_and_read_time_agrees(self, data):
        (name, base_R, codes), (label, what, once), drawn = random_states(data)
        states = [(name, base_R), (label, once)] + ([(f'{label}; {drawn[0]}', drawn[2])] if drawn else [])
        found = findings([Scene('p-mono', how, R, TA.TEXT, assessed(R, codes)) for how, R in states])
        self.assertEqual(found, {}, (name, [how for how, _R in states]))

    def test_a_refusal_fails_naming_its_message_id(self):
        """P-WORDED's positive control: wording planted to refuse one message id (competing, the lead's L1 example on
        test_assess's one balloon dilation) - the property names that message id and nothing else; the item's other
        codes are worded."""
        R, codes = fixture('one balloon dilation')
        scene = Scene('control', 'one balloon dilation', R, TA.TEXT, assessed(R, codes))
        messages = {found.item.message for found in scene.assessment.codes if found.item is not None}
        self.assertIn(Q.MessageId.COMPETING, messages)
        self.assertEqual(findings([scene]), {})  # unplanted: worded
        real_build = wording.build

        def refusing(message, slots, text):
            if message.value == Q.MessageId.COMPETING.value:
                raise ValueError(f'{message.value} needs the slot planted.')
            return real_build(message, slots, text)

        with mock.patch.object(wording, 'build', refusing):
            found = findings([scene])
        self.assertEqual(set(found), {Q.MessageId.COMPETING.value})
        self.assertIn('competing: 2 of 2 items refused', found[Q.MessageId.COMPETING.value])
        self.assertIn('needs the slot planted', found[Q.MessageId.COMPETING.value])

    def test_a_read_time_disagreement_and_a_raise_are_seen(self):
        """P-WORDED's second control: read time planted to word a TEXT_FREE item otherwise (overlay._words) - named by
        its message id; and a renderer that RAISES something other than wording's ValueError on an item is a refusal
        too (the renderer never raises on an engine item)."""
        R, codes = fixture('one balloon dilation')
        scene = Scene('control', 'one balloon dilation', R, TA.TEXT, assessed(R, codes))
        free = {found.item.message.value for found in scene.assessment.codes
                if found.item is not None and text_free(found.item)}
        self.assertTrue(free)
        real_words = overlay._words

        def otherwise(item, key, joined, R_):
            words = real_words(item, key, joined, R_)
            return None if words is None else replace(words, question=words.question + ' (planted)')

        with mock.patch.object(overlay, '_words', otherwise):
            found = findings([scene])
        self.assertEqual(set(found), free)
        self.assertTrue(all(', 0 TEXT_FREE' not in line and ' 0 of ' in line for line in found.values()), found)

        def raises(*args, **kwargs):
            raise KeyError('planted')

        with mock.patch.object(jobs, 'word_item', raises):
            found = findings([scene])
        self.assertEqual(set(found), messages_of(scene))
        self.assertTrue(all('KeyError' in line for line in found.values()))

    def test_text_free_follows_overlays_own_rule(self):
        """A date item is TEXT_FREE only when it quotes no statement (overlay.item_slots answers None otherwise, and read
        time asks no code the encounter's date)."""
        held = HeldFact(fact=RQ.fact_key(RQ.FactKey.SERVICE_DATE), attribute=A.DATE_OF_SERVICE, subject=None,
                        result=Res.UNKNOWN, kind=ItemKind.QUESTION, cause=Q.DATE_UNKNOWN, reason=None, spans=(),
                        rank=None)
        item = Q.Item(held=held, message=Q.MessageId.SERVICE_DATE, fill=Q.Fill())
        self.assertTrue(text_free(item))
        self.assertFalse(text_free(replace(item, fill=Q.Fill(statements=((EF.unit(3),),)))))
        self.assertFalse(text_free(replace(item, message=Q.MessageId.DOUBT)))


def messages_of(scene) -> set:
    return {found.item.message.value for found in scene.assessment.codes if found.item is not None}


# --- P-SLOTS (DECISIONS D254 rule 4, beside P-WORDED): every builder words every combination of its slots -------------
#
# D254: "A property test (6a, in tests/v2/test_properties beside P-WORDED) covers every Message and every combination of
# present and absent optional slots, with values drawn from the slots' own types. wording.build returns a sentence for
# each." P-WORDED words what the engine makes; this words what the engine could make: a builder that refuses a slot's
# absence (A1's "enteroscopy_approach needs the slot approach") fails here before any document meets it (rule 5: after
# rule 1 a refusal can only be a programming error, and this catches it at the gate).

SLOT_TEXT = TA.TEXT  # test_assess's synthetic letter cycle: no words, and every span below holds characters
SLOT_FIELDS = tuple(wording.Slots.__dataclass_fields__)
SLOT_UNITS = tuple(ct.Span(100 * n, 100 * n + 60) for n in (3, 5, 8))  # units as evaluate_fixtures anchors events
SLOT_LONG = ct.Span(1000, 1400)  # one passage longer than any quote's limit
SLOT_CODES = ('45378', '43235', '43259', '44380', '99213', '43273', '64530', '0001U')  # code-shaped: catalogue and not
SLOT_ENUMERATED = 13  # the most optional slots one builder's combinations are enumerated over (2 ** 13 combinations)
# refute-6a-r1 F1: the values that reach the branches a builder makes on several members or two slots together
SLOT_TOUCHING = (ct.Span(300, 360), ct.Span(360, 420))  # two units that touch: quoted as one run
SLOT_SUBSETS = 7  # a grouping of at most this many members gives every subset of it as a value of a tuple field
SLOT_PAIRS = 1000  # two slots whose value pools multiply to at most this are built over every pair of their values


def _enumeration(expected) -> bool:
    return isinstance(expected, type) and issubclass(expected, Enum)


@functools.lru_cache(maxsize=None)
def member_tables(enumeration) -> tuple:
    """wording's and the engine catalogue's own groupings of ``enumeration``'s members, each in the enumeration's order:
    every module-level frozenset or tuple of its members, and every one a module-level mapping holds - the tables a
    builder branches on (engine_catalogue.UPPER_STATIONS, wording.STENT_KINDS, ...), read from the modules, never
    listed here."""
    found = []
    for module in (wording, engine_catalogue):
        for value in vars(module).values():
            for table in (value, *(value.values() if isinstance(value, Mapping) else ())):
                if isinstance(table, (frozenset, tuple)) and table and all(isinstance(item, enumeration)
                                                                            for item in table):
                    ordered = tuple(member for member in enumeration if member in table)
                    if ordered not in found:
                        found.append(ordered)
    return tuple(found)


def member_tuples(members: tuple) -> tuple:
    """The values of a tuple of one enumeration's members: each member alone; the first and the last together, the last
    twice and the first twice; every subset of the members, in their order, when they are at most SLOT_SUBSETS; and every
    subset of each grouping ``member_tables`` finds of at most SLOT_SUBSETS members, a larger grouping whole - so a
    builder that branches on several members together (STATIONS' two-station form, STATION_CLASS's three upper
    stations: refute-6a-r1 F1) is built."""
    out = [(member,) for member in members] + [(members[0], members[-1]), (members[-1],) * 2, (members[0],) * 2]
    groups = ((members,) if len(members) <= SLOT_SUBSETS else ()) + member_tables(type(members[0]))
    for group in groups:
        if len(group) > SLOT_SUBSETS:
            out.append(group)
            continue
        out += [subset for size in range(2, len(group) + 1) for subset in itertools.combinations(group, size)]
    return tuple(dict.fromkeys(out))


def catalogue_codes() -> tuple:
    """Every code of the engine's catalogue (engine_catalogue.CODES), as a proposed code is written: a builder that
    branches on the code (the limited class of 43237 and 43238, EGD_LIMITED_EUS_CODES) meets each."""
    return tuple(str(code) for code in sorted(engine_catalogue.CODES))


@functools.lru_cache(maxsize=None)
def type_values(name: str) -> tuple:
    """Every value P-SLOTS draws for the Slots field ``name``, from the field's own type (wording._SLOT_TYPES, which
    Slots validates against): every member of an enumeration - for a tuple of members ``member_tuples``; spans of
    SLOT_TEXT - one unit, two, two that touch, a passage past every quote's limit; statements - one of one unit, two,
    three, one with no units (alone and beside one with), the same one twice, two touching units, the long passage; a
    code - code-shaped strings (two outside the GI catalogue) and every catalogue code; codes - one, two, the same twice;
    True for a flag (False is its absence)."""
    expected, many = wording._SLOT_TYPES[name]
    one, two, three = ((unit,) for unit in SLOT_UNITS)
    if expected == 'spans':
        return ((one,), (one, two), (one, two, three), ((),), ((), two), (one, one), (SLOT_TOUCHING,), ((SLOT_LONG,),))
    if expected is ct.Span:
        return (one, one + two, SLOT_TOUCHING, (SLOT_LONG,))
    if expected is bool:
        return (True,)
    if expected is str:
        return tuple((code,) for code in SLOT_CODES[:3]) + (('45385', '45386'), ('45385', '45385')) if many \
            else tuple(dict.fromkeys(SLOT_CODES + catalogue_codes()))
    members = tuple(expected)
    if not many:
        return members
    return member_tuples(members)


def slot_value(name: str, index: int):
    values = type_values(name)
    return values[index % len(values)]


def slot_fields(present, index: int) -> dict:
    """The Slots fields of one combination: each field of ``present`` with a value of its own type chosen by ``index``,
    offset per field, so the combinations walk every value of every field. The stride 11 keeps two fields of one type
    from holding one value in every combination (refute-6a-r1 F1: with 7, ``act`` and ``whole`` took the same kind in
    each); ``pair_builds`` gives every pair of their values."""
    return {name: slot_value(name, index + 11 * offset) for offset, name in enumerate(SLOT_FIELDS) if name in present}


def slot_combination(needs, optional, mask: int, shift: int = 0) -> dict:
    """The carried slots (``needs``: always given) and the optional ones ``mask`` marks present."""
    return slot_fields(set(needs) | {name for bit, name in enumerate(optional) if mask >> bit & 1}, mask + shift)


_READ: set = set()
_MUTED = [0]


class _Reading(wording.Slots):
    """wording.Slots that records which fields a builder reads (Slots' own validation in __post_init__ is not a read)."""
    __slots__ = ()

    def __post_init__(self) -> None:
        _MUTED[0] += 1
        try:
            wording.Slots.__post_init__(self)
        finally:
            _MUTED[0] -= 1

    def __getattribute__(self, name):
        if not _MUTED[0] and name in SLOT_FIELDS:
            _READ.add(name)
        return object.__getattribute__(self, name)


def _reads(message, fields) -> frozenset:
    """The fields ``message``'s build reads over ``fields`` (what it read before a refusal, if it refuses: the property
    reports the refusal)."""
    _READ.clear()
    with contextlib.suppress(Exception):
        wording.build(message, _Reading(**fields), SLOT_TEXT)
    return frozenset(_READ)


@functools.lru_cache(maxsize=None)
def builder_reads(message) -> frozenset:
    """The fields ``message``'s builder reads - the only ones whose presence can change its words (SlotsTests proves it):
    recorded over every value of every field (all given, and only the carried ones), then over every combination of
    present and absent fields it has read, again until no combination reads one more (a fixpoint)."""
    needs = set(wording.MESSAGES[message].needs)
    seen = set(needs)
    for index in range(max(len(type_values(name)) for name in SLOT_FIELDS)):
        for present in (SLOT_FIELDS, needs):
            seen |= _reads(message, slot_fields(present, index))
    while True:
        optional = sorted(seen - needs)
        if len(optional) > SLOT_ENUMERATED:
            return frozenset(seen)  # too many to enumerate: slot_findings names the message
        found = set(seen)
        for mask in range(2 ** len(optional)):
            found |= _reads(message, slot_combination(needs, optional, mask, 3))
        if found == seen:
            return frozenset(seen)
        seen = found


def sentence_faults(sentence) -> list:
    """What makes a built sentence no sentence: not a str or empty, untrimmed, not ended as a sentence (a closing quote
    aside), a placeholder left (a brace, a None), an empty quote or empty brackets, a doubled space."""
    if not isinstance(sentence, str) or not sentence.strip():
        return ['empty']
    faults = [] if sentence == sentence.strip() else ['untrimmed']
    if not sentence.rstrip('”').endswith(('.', '?', '…')):
        faults.append('unterminated')
    faults += [f'holds {fault!r}' for fault in ('{', '}', '“”', '()', '  ') if fault in sentence]
    if re.search(r'\bNone\b', sentence):
        faults.append('holds None')
    return faults


def built_problem(message, fields) -> str:
    """'' when wording.build words ``message`` over ``fields``: a Worded of that message and its kind, its question and
    reason each a sentence (``sentence_faults``); otherwise what went wrong - the refusal, named."""
    spec = wording.MESSAGES[message]
    try:
        item = wording.build(message, wording.Slots(**fields), SLOT_TEXT)
    except Exception as exc:  # noqa: BLE001 - a refusal of any kind is the finding
        return f'{type(exc).__name__}: {exc}'
    if (item.message, item.kind) != (message, spec.kind):
        return f'built {item.message} {item.kind}, not {message} {spec.kind}'
    for part, sentence in (('question', item.question), ('reason', item.reason)):
        faults = sentence_faults(sentence)
        if faults:
            return f'the {part} {faults}: {sentence!r}'
    return ''


def combination_builds(message):
    """Every combination of present and absent optional slots ``message``'s builder reads (``builder_reads``), its
    carried slots always given: the fields of each."""
    needs = wording.MESSAGES[message].needs
    optional = sorted(builder_reads(message) - set(needs))
    for mask in range(2 ** len(optional)):
        yield slot_combination(needs, optional, mask)


def value_builds(message):
    """Each value of each field ``message``'s builder reads (every enumeration member and grouping among them) beside
    every other field it reads, and beside its carried slots alone: the fields of each."""
    reads, needs = builder_reads(message), wording.MESSAGES[message].needs
    for name in sorted(reads):
        for index, value in enumerate(type_values(name)):
            for others in (reads, needs):
                fields = {other: slot_value(other, index + 3 + offset) for offset, other in enumerate(sorted(others))}
                fields[name] = value
                yield fields


def _one_type(one: str, other: str) -> bool:
    """Two fields of one enumeration's type, each one member or each a tuple of members of an enumeration of at most
    SLOT_SUBSETS members (every subset of which is drawn)."""
    expected, many = wording._SLOT_TYPES[one]
    return (wording._SLOT_TYPES[other] == (expected, many) and _enumeration(expected)
            and (not many or len(expected) <= SLOT_SUBSETS))


def value_pairs(message) -> tuple:
    """The pairs of fields ``message``'s builder reads that P-SLOTS builds over every pair of their values (refute-6a-r1
    F1): two of one enumeration's type (``_one_type``: two kinds - SAME_DUCT's exchange is two distinct stent kinds -
    or two lists of stations), and any two whose value pools multiply to at most SLOT_PAIRS (the code beside an
    examination class: the limited class of 43237 and 43238)."""
    reads = sorted(builder_reads(message))
    return tuple((one, other) for index, one in enumerate(reads) for other in reads[index + 1:]
                 if _one_type(one, other) or len(type_values(one)) * len(type_values(other)) <= SLOT_PAIRS)


def pair_builds(message):
    """Every pair of values of each pair of fields ``value_pairs`` names, beside the builder's carried slots alone and
    beside every field it reads: the fields of each."""
    reads, needs = sorted(builder_reads(message)), wording.MESSAGES[message].needs
    for one, other in value_pairs(message):
        for others in (needs, reads):
            base = {name: slot_value(name, 3 + offset) for offset, name in enumerate(sorted(others))}
            for first in type_values(one):
                for second in type_values(other):
                    yield {**base, one: first, other: second}


def slot_findings() -> tuple[dict, collections.Counter]:
    """P-SLOTS over every Message (the module docstring): (the first problem of each message id - every combination of
    its present and absent optional slots, the ones its builder reads, its carried slots always given - and the
    combinations counted per message id)."""
    found, counted = {}, collections.Counter()
    for message in wording.Message:
        optional = sorted(builder_reads(message) - set(wording.MESSAGES[message].needs))
        if len(optional) > SLOT_ENUMERATED:
            found[message.value] = (f'{message.value} reads {len(optional)} optional slots, more than the '
                                    f'{SLOT_ENUMERATED} P-SLOTS enumerates: {optional}')
            continue
        for fields in combination_builds(message):
            counted[message.value] += 1
            problem = built_problem(message, fields)
            if problem and message.value not in found:
                found[message.value] = f'{message.value} over {fields}: {problem}'
    return found, counted


def sweep_findings(builds, messages=tuple(wording.Message)) -> tuple[dict, collections.Counter]:
    """(the first problem of each message id, the builds counted per message id) over ``builds(message)`` - one of
    ``value_builds``, ``pair_builds``, ``combination_builds`` - for each of ``messages``."""
    found, counted = {}, collections.Counter()
    for message in messages:
        for fields in builds(message):
            counted[message.value] += 1
            problem = built_problem(message, fields)
            if problem and message.value not in found:
                found[message.value] = f'{message.value} over {fields}: {problem}'
    return found, counted


# The lines of wording.py's builders no P-SLOTS build executes by design, each with its reason (keyed by function and
# source line, never by line number)
NOT_DRAWN = {('_runs', 'continue'): 'an empty span: never a unit (segment trims every unit), so P-SLOTS draws none'}


def _code_objects(code):
    yield code
    for constant in code.co_consts:
        if isinstance(constant, types.CodeType):
            yield from _code_objects(constant)


def builder_lines() -> dict:
    """Every line of wording.py a builder can execute (line -> its function): MESSAGES' builders and build, and every
    wording.py function they name, transitively (nested code and closures through their own code) - but the lines of a
    raise statement, a refusal P-SLOTS never asks for (a carried slot is always given; a span past the text or holding
    no words is a binding failure it never draws), and NOT_DRAWN's."""
    functions = {name: value for name, value in vars(wording).items()
                 if isinstance(value, types.FunctionType) and value.__module__ == wording.__name__}
    source_file = os.path.realpath(wording.__file__)
    todo = [spec.words.__code__ for spec in wording.MESSAGES.values()] + [wording.build.__code__]
    seen, lines = set(), {}
    while todo:
        code = todo.pop()
        if code in seen or os.path.realpath(code.co_filename) != source_file:
            continue
        seen.add(code)
        todo += [inner for inner in _code_objects(code) if inner is not code]
        todo += [functions[name].__code__ for name in code.co_names if name in functions]
        for _start, _end, line in code.co_lines():
            if line is not None and line != code.co_firstlineno:
                lines.setdefault(line, code.co_name)
    source = Path(wording.__file__).read_text(encoding='utf-8')
    refusals = {line for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Raise)
                for line in range(node.lineno, (node.end_lineno or node.lineno) + 1)}
    text = source.splitlines()
    return {line: name for line, name in sorted(lines.items())
            if line not in refusals and (name, text[line - 1].strip()) not in NOT_DRAWN}


@contextlib.contextmanager
def executed_lines(path):
    """The lines of the source file ``path`` executed inside the block (sys.monitoring's LINE events; each location
    reported once, then disabled for this tool)."""
    monitoring = sys.monitoring
    tool = next((tool for tool in range(1, 5) if monitoring.get_tool(tool) is None), None)
    if tool is None:
        raise RuntimeError('every sys.monitoring tool id is in use: P-SLOTS cannot see the lines it builds')
    target, real, seen = os.path.realpath(path), {}, set()

    def line(code, number):
        name = code.co_filename
        if name not in real:
            real[name] = os.path.realpath(name)
        if real[name] == target:
            seen.add(number)
        return monitoring.DISABLE

    monitoring.use_tool_id(tool, 'tests.v2.test_properties P-SLOTS')
    try:
        monitoring.register_callback(tool, monitoring.events.LINE, line)
        monitoring.restart_events()
        monitoring.set_events(tool, monitoring.events.LINE)
        yield seen
    finally:
        monitoring.set_events(tool, monitoring.events.NO_EVENTS)
        monitoring.register_callback(tool, monitoring.events.LINE, None)
        monitoring.free_tool_id(tool)
        monitoring.restart_events()


def unbuilt_lines(messages=tuple(wording.Message)) -> dict:
    """The lines of ``builder_lines`` that P-SLOTS' builds - every combination, every value, every pair (each checked as
    the property checks it) - never execute, each with its function and its source; the recording reads come first,
    so only checked builds count."""
    for message in messages:
        builder_reads(message)
    with executed_lines(wording.__file__) as seen:
        for builds in (combination_builds, value_builds, pair_builds):
            sweep_findings(builds, messages)
    text = Path(wording.__file__).read_text(encoding='utf-8').splitlines()
    return {line: f'{name}: {text[line - 1].strip()}' for line, name in builder_lines().items() if line not in seen}


class SlotsTests(SimpleTestCase):
    """DECISIONS D254 rule 4's P-SLOTS (the module docstring): the renderer's sentences are total."""

    def test_every_carried_slot_is_declared_with_its_reason(self):
        """The slots wording declares carried (MESSAGES' needs: D254 rule 1, "listed per message in wording.py") are each
        given a reason (CARRIED), are Slots fields, and are the only slots P-SLOTS always gives; every message has its
        entry."""
        self.assertEqual(set(wording.MESSAGES), set(wording.Message))
        carried = {name for spec in wording.MESSAGES.values() for name in spec.needs}
        self.assertTrue(carried)
        self.assertLessEqual(carried, set(wording.CARRIED))
        self.assertLessEqual(carried, set(SLOT_FIELDS))
        self.assertEqual(set(wording._SLOT_TYPES), set(SLOT_FIELDS))  # every field has its type: type_values reads it

    def test_every_message_words_every_combination_of_present_and_absent_slots(self):
        found, counted = slot_findings()
        self.assertEqual(set(counted) | set(found), {message.value for message in wording.Message})
        self.assertGreater(sum(counted.values()), 3000, counted)  # never vacuous
        for message in wording.Message:
            with self.subTest(message=message.value):
                optional = builder_reads(message) - set(wording.MESSAGES[message].needs)
                self.assertLessEqual(len(optional), SLOT_ENUMERATED)
                if message.value in found:
                    self.fail(found[message.value])

    def test_every_value_of_every_slot_a_builder_reads_is_worded(self):
        """Each value of each field a builder reads - every enumeration member and every grouping of members among them
        (``member_tuples``), every catalogue code - beside every other field it reads, and beside its carried slots
        alone (``value_builds``)."""
        found, counted = sweep_findings(value_builds)
        self.assertEqual(found, {})
        self.assertGreater(sum(counted.values()), 20000, counted)  # never vacuous

    def test_a_slot_no_builder_reads_changes_no_sentence(self):
        """The combinations above cover every combination of all the slots: a field a builder does not read never
        changes what it builds, over random fields of every type."""
        rng = random.Random(254)
        for message in wording.Message:
            reads = builder_reads(message)
            for _ in range(20):
                full = {name: rng.choice(type_values(name)) for name in SLOT_FIELDS}
                read_only = {name: value for name, value in full.items() if name in reads}
                self.assertEqual(wording.build(message, wording.Slots(**full), SLOT_TEXT),
                                 wording.build(message, wording.Slots(**read_only), SLOT_TEXT), message)

    # no shrinking: a failure names its message and its drawn fields, and shrinking 36 drawn fields re-builds for minutes
    # while the gate waits (the exhaustive tests above hold the minimal cases)
    @hypothesis.settings(max_examples=300, deadline=None, derandomize=True, database=None,
                         suppress_health_check=list(hypothesis.HealthCheck),
                         phases=(hypothesis.Phase.explicit, hypothesis.Phase.reuse, hypothesis.Phase.generate))
    @hypothesis.given(st.sampled_from(list(wording.Message)), st.data())
    def test_random_slots_over_every_field_are_worded(self, message, data):
        """Any message, its carried slots given and every other field present or absent by a draw, each value drawn from
        its own type."""
        needs = wording.MESSAGES[message].needs
        fields = {name: data.draw(st.sampled_from(type_values(name)), label=name) for name in SLOT_FIELDS
                  if name in needs or data.draw(st.booleans(), label=f'{name} present')}
        self.assertEqual(built_problem(message, fields), '', (message.value, fields))

    def test_a_refusal_put_back_fails_naming_its_message(self):
        """P-SLOTS' positive control: A1's refusal put back for the call - ENTEROSCOPY_APPROACH refusing an item with no
        approach, as before D254 rule 3 - is named by its message id, and by nothing else; unplanted, nothing is found."""
        self.assertEqual(slot_findings()[0], {})
        real = wording.MESSAGES[wording.Message.ENTEROSCOPY_APPROACH]

        def refusing(slots, text):
            if slots.approach is None:
                raise ValueError('enteroscopy_approach needs the slot approach (planted).')
            return real.words(slots, text)

        planted = {**wording.MESSAGES, wording.Message.ENTEROSCOPY_APPROACH: replace(real, words=refusing)}
        with mock.patch.object(wording, 'MESSAGES', planted):
            found, _counted = slot_findings()
        self.assertEqual(set(found), {'enteroscopy_approach'})
        self.assertIn('needs the slot approach (planted)', found['enteroscopy_approach'])
        self.assertIn('approach', builder_reads(wording.Message.ENTEROSCOPY_APPROACH))

    def test_a_sentence_that_is_no_sentence_is_seen(self):
        """sentence_faults' own control: each fault it names is seen, and a sentence of CPT Studio's shape passes."""
        self.assertEqual(sentence_faults('Is 45378 reported separately from another act for this examination?'), [])
        self.assertEqual(sentence_faults('The document states “x.”'), [])
        for bad in ('', ' ', 'No stop', ' Untrimmed.', 'A {slot}.', 'A None value.', 'An empty quote “”.',
                    'Empty () brackets.', 'Two  spaces.', None):
            with self.subTest(sentence=bad):
                self.assertNotEqual(sentence_faults(bad), [])

    def test_every_pair_of_values_is_worded_and_every_builder_line_is_built(self):
        """refute-6a-r1 F1: every pair of values of two fields a builder reads that ``value_pairs`` names (two of one type;
        any two whose pools multiply to at most SLOT_PAIRS) is worded (``pair_builds``), and P-SLOTS' builds - every
        combination, every value, every pair, each checked as the property checks it - execute every line of every
        builder (``builder_lines``): a branch no build reaches is a branch whose refusal P-SLOTS cannot see (the
        refuter's MS1-MS4: STATIONS' two-station form, STATION_CLASS's three upper stations, SAME_DUCT's exchange rule,
        the limited class of 43237 and 43238). An unbuilt line is named with its function and its source."""
        found, counted = sweep_findings(pair_builds)
        self.assertEqual(found, {})
        self.assertGreater(sum(counted.values()), 100000, counted)  # never vacuous
        self.assertGreater(len(builder_lines()), 500)
        self.assertEqual(unbuilt_lines(), {})

    def test_the_line_measure_names_the_branches_the_first_draws_never_built(self):
        """The line measure's own control (refute-6a-r1 F1, its probe p03): with P-SLOTS drawing as its first build did -
        each member alone, the first and the last together, the last twice and the first twice, the codes SLOT_CODES, two
        units at most, fields stepping by 7 and no pairs - the lines the refuter found never built are named:
        STATIONS' two-station form, STATION_CLASS's three upper stations, SAME_DUCT's exchange rule and the limited class
        of 43237 and 43238."""
        module = sys.modules[__name__]

        def first_values(name):
            expected, many = wording._SLOT_TYPES[name]
            one, two, three = ((unit,) for unit in SLOT_UNITS)
            if expected == 'spans':
                return ((one,), (one, two), (one, two, three), ((),), ((), two), (one, one), ((SLOT_LONG,),))
            if expected is ct.Span:
                return (one, one + two, (SLOT_LONG,))
            if expected is bool:
                return (True,)
            if expected is str:
                return tuple((code,) for code in SLOT_CODES[:3]) + (('45385', '45386'), ('45385', '45385')) if many \
                    else SLOT_CODES
            members = tuple(expected)
            return tuple((member,) for member in members) + (
                (members[0], members[-1]), (members[-1],) * 2, (members[0],) * 2) if many else members

        def first_fields(present, index):
            return {name: first_values(name)[(index + 7 * offset) % len(first_values(name))]
                    for offset, name in enumerate(SLOT_FIELDS) if name in present}

        with mock.patch.object(module, 'type_values', first_values), \
                mock.patch.object(module, 'slot_fields', first_fields), \
                mock.patch.object(module, 'value_pairs', lambda message: ()):
            missing = unbuilt_lines()
        for function, fragment in (('_stations', 'named, missing = _named_stations(named_in)'),
                                   ('_station_class', 'named, _ = _named_stations(s.stations)'),
                                   ('_same_duct', 'EXCHANGE_PART_RULE if Kind.STENT_EXCHANGE in (kind, other)'),
                                   ('_eus_class_words', 'return EGD_LIMITED_WORDS')):
            with self.subTest(function=function):
                self.assertTrue(any(found.startswith(f'{function}: ') and fragment in found
                                    for found in missing.values()), missing)

    def test_a_refusal_in_a_branch_on_several_members_or_two_slots_is_seen(self):
        """P-SLOTS' control for refute-6a-r1 F1: the refuter's mutants put in for the call, each refusing only where its
        branch turns on several members or on two slots together - MS1, STATION_CLASS's three upper stations without
        words; MS3B, STATIONS' two-station form; MS2, SAME_DUCT's exchange with an act of no units; MS4, the limited
        class of 43237 and 43238 - are each named by P-SLOTS by its message id, and by nothing else."""
        up, stents = engine_catalogue.UPPER_STATIONS, wording.STENT_KINDS
        M = wording.Message

        def two_upper(s):
            named = [station for station in up if station in s.stations]
            return (s.exam_class or engine_catalogue.EusClass.FULL) is engine_catalogue.EusClass.FULL and \
                1 < len(named) < len(up)

        plants = {
            'MS1': ({M.STATION_CLASS}, lambda s: not [station for station in s.denied if station in up]
                    and all(station in s.stations for station in up) and not s.words),
            'MS3B': ({M.STATIONS}, two_upper),
            'MS2': ({M.SAME_DUCT}, lambda s: s.act is not None and s.whole is not None and s.act is not s.whole
                    and {s.act, s.whole} <= stents and not (s.words and s.whole_words)),
        }
        for name, (messages, refuses) in plants.items():
            planted = dict(wording.MESSAGES)
            for message in messages:
                def refusing(slots, text, real=wording.MESSAGES[message]):
                    if refuses(slots):
                        raise ValueError(f'{name}: planted refusal')
                    return real.words(slots, text)
                planted[message] = replace(wording.MESSAGES[message], words=refusing)
            with self.subTest(mutant=name), mock.patch.object(wording, 'MESSAGES', planted):
                found = {}
                for builds in (combination_builds, value_builds, pair_builds):
                    found.update(sweep_findings(builds, tuple(messages))[0])
                self.assertEqual(set(found), {message.value for message in messages})
                self.assertTrue(all('planted refusal' in problem for problem in found.values()), found)
        real_words = wording._eus_class_words

        def limited_refused(code, exam_class):
            if exam_class is engine_catalogue.EusClass.LIMITED and code in ('43237', '43238'):
                raise ValueError('MS4: planted refusal')
            return real_words(code, exam_class)

        eus = tuple(message for message in wording.Message if 'exam_class' in builder_reads(message))
        with self.subTest(mutant='MS4'), mock.patch.object(wording, '_eus_class_words', limited_refused):
            found = {}
            for builds in (combination_builds, value_builds, pair_builds):
                found.update(sweep_findings(builds, eus)[0])
            self.assertTrue(found, eus)
            self.assertTrue(all('MS4: planted refusal' in problem for problem in found.values()), found)

    def test_the_refuters_type_drawn_slots_are_drawn_and_worded(self):
        """refute-6a-r1 F1's inputs, each drawn by P-SLOTS and worded: STATION_CLASS over 43237 with the three upper
        stations; STATIONS over 43259 with the esophagus and the stomach; SAME_DUCT over a stent placement beside a stent
        removal, either with units or none; EXAMINATION_CLASS over 43238 of the limited class."""
        S, M, Station = wording.Slots, wording.Message, ct.Station
        upper = (Station.ESOPHAGUS, Station.STOMACH, Station.DUODENUM)
        self.assertIn(upper, type_values('stations'))
        self.assertIn(upper[:2], type_values('stations'))
        self.assertIn('43237', type_values('code'))
        self.assertIn(('act', 'whole'), value_pairs(M.SAME_DUCT))
        self.assertIn(('code', 'exam_class'), value_pairs(M.EXAMINATION_CLASS))
        one = (SLOT_UNITS[0],)
        cases = ((M.STATION_CLASS, dict(code='43237', stations=upper)),
                 (M.STATION_CLASS, dict(code='43237', stations=upper, words=one)),
                 (M.STATIONS, dict(code='43259', stations=upper[:2])),
                 (M.STATIONS, dict(code='43259', stations=upper[:2], words=one)),
                 (M.SAME_DUCT, dict(act=Kind.STENT, whole=Kind.STENT_REMOVAL)),
                 (M.SAME_DUCT, dict(act=Kind.STENT_REMOVAL, whole=Kind.STENT_EXCHANGE, words=one,
                                    whole_words=(SLOT_UNITS[1],))),
                 (M.EXAMINATION_CLASS, dict(code='43238', exam_class=engine_catalogue.EusClass.LIMITED)))
        for message, fields in cases:
            with self.subTest(message=message.value, fields=fields):
                self.assertEqual(built_problem(message, {**{name: slot_value(name, 0)
                                                            for name in wording.MESSAGES[message].needs}, **fields}),
                                 '')
        built = wording.build(M.STATION_CLASS, S(code='43237', stations=upper), SLOT_TEXT)
        self.assertIn(wording.EGD_LIMITED_WORDS, built.question)
        built = wording.build(M.SAME_DUCT, S(act=Kind.STENT, whole=Kind.STENT_REMOVAL), SLOT_TEXT)
        self.assertIn(wording.EXCHANGE_PAIR_RULE, built.reason)


# --- D254's six refusing shapes, regression cases through jobs.word_item (DECISIONS D254 rule 4) ---------------------

def _enteroscopy(reached, approach, *, through=None, entries=(), biopsy=False):
    """refute-r4a-r2's a1_negated_approach.ent: an enteroscopy X1 (its examination E1), its approach and reach, a stoma
    entry, a biopsy E2 of the jejunum."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.ENTEROSCOPY, approach=approach, reached=reached, through=through)
    for number, kind in entries:
        doc.entry(number, type=sup(kind, spans=(EF.unit(8),)))
    doc.exam(1)
    if biopsy:
        doc.act(2, Kind.BIOPSY, places=[sup(Landmark.JEJUNUM)])
    return doc.build()


def _contradicted_kind_colonoscopy():
    """refute-r3c-r1's p07_contra_record: a colonoscopy X1 (E1) and an act E2 whose kind pass 1 filed contradicted
    (snare or biopsy) in the sigmoid colon."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.COLONOSCOPY, reached=[sup(Extent.CECUM)])
    doc.exam(1)
    doc.act(2, EF.contra(Kind.SNARE, Kind.BIOPSY), places=[sup(Landmark.SIGMOID_COLON)])
    return doc.build()


def _office_and_contradicted_kind_sigmoidoscopy():
    """refute-r3c-r1's p06_separate_em: an office visit X1 (E1, medical decision making) and a same-day flexible
    sigmoidoscopy X2 (E2) with an act E3 of contradicted kind in the sigmoid colon."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.OFFICE_EM, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
    doc.act(1, Kind.EM_VISIT, basis=sup(ct.EmBasis.MEDICAL_DECISION_MAKING))
    doc.session(2, ct.SessionKind.FLEX_SIG, reached=[sup(Extent.SIGMOID_COLON)])
    doc.exam(2, session=EF.X(2))
    doc.act(3, EF.contra(Kind.SNARE, Kind.BIOPSY), session=EF.X(2), places=[sup(Landmark.SIGMOID_COLON)])
    return doc.build()


def _eus_act_of_kind_other():
    """refute-5b-r1's p2_other_act and p2b_other_act_pair: an upper EUS X1 (its stations established, E1 at the pancreas)
    and an act E2 of kind other at the pancreas."""
    doc = EF.Doc()
    doc.session(1, ct.SessionKind.EUS, tract=sup(ct.Tract.UPPER), encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                stations=[sup(station) for station in (Station.ESOPHAGUS, Station.STOMACH, Station.DUODENUM)],
                reached=[sup(Extent.SECOND_PORTION_DUODENUM)])
    doc.exam(1, places=[sup(Landmark.PANCREAS)])
    doc.act(2, Kind.OTHER, places=[sup(Landmark.PANCREAS)])
    return doc.build()


def _kindless_entry(session):
    """refute-r4d-r1's seam_render.entry(None, session): an unlisted act of no kind carded to ``session``."""
    return UnlistedStatement(units=(ct.Span(3000, 3040),), what=ct.UnlistedWhat.ACT, kind=None, session=session)


def _egd_beside_a_tube_session():
    """seam_render's S1: an EGD X1 (E1) and a feeding-tube session X3, a kindless unlisted act carded to X3."""
    doc = EF.egd()
    doc.session(3, ct.SessionKind.FEEDING_TUBE)
    doc.unlisted.append(_kindless_entry(EF.X(3)))
    return doc.build()


def _colonoscopy_beside_a_kindless_carded_act():
    """seam_render's S2c: a colonoscopy X1 (E1, no snare), a kindless unlisted act carded to X1."""
    doc = EF.colonoscopy(snare=False)
    doc.unlisted.append(_kindless_entry(EF.X(1)))
    return doc.build()


def six_shapes():
    """D254's six refusing shapes (the lead's w7r VERIFY.md), each FactSet as its refuter's own probe builds it, dated with
    test_assess's day as those probes' test_assess.run dates it: (label, the FactSet, the codes proposed, the code whose
    one item the renderer words, the probe). A1 (refute-r4a-r2): the enteroscopy approach established only by a denial;
    R3C1-01 (refute-r3c-r1): an act of contradicted kind; 5b F1 (refute-5b-r1): an upper EUS act of kind other; r4d S1
    and S2c (refute-r4d-r1/r2): a kindless unlisted act carded to a session."""
    jejunum, ileum = sup(Extent.JEJUNUM, spans=(EF.unit(5),)), sup(Extent.ILEUM, spans=(EF.unit(6),))
    not_oral = EF.neg(ct.Approach.ORAL, spans=(EF.unit(4),))
    not_stoma = EF.neg(ct.Approach.THROUGH_STOMA, spans=(EF.unit(4),))
    stoma = dict(through=sup(EF.Y(1), spans=(EF.unit(3),)), entries=((1, ct.AnatomyType.STOMA),))
    shapes = (
        ('A1 44360', _enteroscopy([jejunum], not_oral), (('44360', 1),), '44360', 'a1_negated_approach'),
        ('A1 44376', _enteroscopy([ileum], not_oral), (('44376', 1),), '44376', 'a1_negated_approach'),
        ('A1 44361', _enteroscopy([jejunum], not_oral, biopsy=True), (('44361', 2),), '44361', 'a1_negated_approach'),
        ('A1 44380', _enteroscopy([ileum], not_stoma, **stoma), (('44380', 1),), '44380', 'a1_negated_approach'),
        ('R3C1-01 45378', _contradicted_kind_colonoscopy(), (('45378', 1),), '45378', 'p07_contra_record'),
        ('R3C1-01 45330 beside 99213', _office_and_contradicted_kind_sigmoidoscopy(), (('99213', 1), ('45330', 2)),
         '45330', 'p06_separate_em'),
        ('5b F1 43259', _eus_act_of_kind_other(), (('43259', 1),), '43259', 'p2_other_act'),
        ('5b F1 43259 with 64530', _eus_act_of_kind_other(), (('43259', 1), ('64530', 2)), '43259',
         'p2b_other_act_pair'),
        ('r4d S1 43235', _egd_beside_a_tube_session(), (('43235', 1),), '43235', 'seam_render S1'),
        ('r4d S2c 45378', _colonoscopy_beside_a_kindless_carded_act(), (('45378', 1),), '45378', 'seam_render S2c'),
    )
    return tuple((label, TA.dated(R), codes, code, probe) for label, R, codes, code, probe in shapes)


ROUTE_PHRASES = tuple(sorted(set(wording.ROUTE_WORDS.values()) | set(wording.APPROACH_WORDS.values())))
NO_KIND_LABEL_FAULTS = re.compile(r'\b(?:[Tt]he|[Aa]n?|[Tt]his) another act\b|(?<!another )\bact \(stated in doubt\)|'
                                  r'\bfrom act\b')


def shape_words(label, R, codes, code):
    """(the Assessed of ``code``, the ClarificationSpec the renderer words its one item with) for one shape:
    engine/assess over R, then studio/jobs.word_item as _render_code calls it."""
    assessment = assessed(R, codes)
    found = next(item for item in assessment.codes if item.code == code)
    if found.item is None:
        return found, None
    return found, jobs.word_item(found.item, found.key, assessment.combination, R, TA.TEXT,
                                 family=AS.family_slug(found.family))


class SixShapesTests(SimpleTestCase):
    """DECISIONS D254 rule 4: "The six shapes above are regression cases through jobs.word_item." Each of the ten FactSets
    is held (its code reaches the renderer with its one item) and worded by studio/jobs.word_item without a refusal, read
    time words a TEXT_FREE item identically (P-WORDED's own check), and the words are true for the state (rules 2 and
    3). On the w7r final tree every one was refused (VERIFY.md); step r3c (wording.py: D254 rules 1-3) words them - this
    step's tree carries r3c's first patch, so all ten are green here. 5c (rule 2 in item_slots), r4a (rule 2 in the Fill,
    rule 3's mapping) and r4d (D256: no-card entries) change which slots carry the label or which entries hold, not these
    sentences' truth, so they stay green when those steps land (the step's NOTES record the measurement)."""

    def test_each_shape_is_held_and_worded_by_the_renderer(self):
        for label, R, codes, code, probe in six_shapes():
            with self.subTest(shape=label, probe=probe):
                found, spec = shape_words(label, R, codes, code)
                self.assertIsNotNone(spec, f'{label}: {code} is {found.status.value} - the shape no longer reaches the '
                                           'renderer, so it regresses nothing')
                self.assertEqual(spec.scope, 'proposal')
                for sentence in (spec.question, spec.reason):
                    self.assertEqual(sentence_faults(sentence), [], sentence)
                scene = Scene('six shapes', label, R, TA.TEXT, assessed(R, codes))
                self.assertEqual(findings([scene]), {})  # P-WORDED over the shape: the renderer and read time agree

    def test_each_shapes_words_are_true_for_its_state(self):
        """D254 rule 3: A1's items word the enteroscopy class without naming a route (the denied one or any); rule 2: an
        act no kind names is 'another act' with its article, never 'act' ("from act", "the act (stated in doubt)")."""
        for label, R, codes, code, probe in six_shapes():
            with self.subTest(shape=label):
                found, spec = shape_words(label, R, codes, code)
                said = f'{spec.question} {spec.reason}'
                self.assertIsNone(NO_KIND_LABEL_FAULTS.search(said), said)
                if label.startswith('A1'):
                    classes = [words for words in wording.ENTEROSCOPY_CLASS_WORDS.values() if words in said]
                    self.assertEqual(len(classes), 1, said)  # the code's class, named
                    rest = said.replace(classes[0], '')
                    self.assertEqual([phrase for phrase in ROUTE_PHRASES if phrase in rest], [], said)
                else:
                    self.assertIn(wording.NO_KIND_LABEL, said)

    def test_a_refusal_on_a_shape_is_seen(self):
        """The regression's positive control: wording planted to refuse the messages the shapes' items hold - the renderer
        then raises on every shape (as on the w7r final tree), and P-WORDED names each message id."""
        messages = set()
        for label, R, codes, code, probe in six_shapes():
            found, spec = shape_words(label, R, codes, code)
            messages.add(found.item.message.value)

        def refusing(message, slots, text):
            raise ValueError(f'{message.value} refused (planted).')

        with mock.patch.object(wording, 'build', refusing):
            for label, R, codes, code, probe in six_shapes():
                with self.subTest(shape=label), self.assertRaises(ValueError):
                    shape_words(label, R, codes, code)
            scenes = [Scene('six shapes', label, R, TA.TEXT, assessed(R, codes))
                      for label, R, codes, code, probe in six_shapes()]
            self.assertLessEqual(messages, set(findings(scenes)))


class R2APMonoFixtureTests(SimpleTestCase):
    """DECISIONS D294, repair r2 (builder R2A): P-MONO's two fixtures for RD-2 and RD-3, D264's every-row check reading
    assess's ADDON row (RD-2), and the generator keeping a negated claim negated, as settle does. The census itself
    (``PMonoTests.test_every_single_weakening_of_every_fixture``) runs over both fixtures with every other; here each
    fixture's own shape and its releases are asserted directly, so a mutant that brings one back fails by name."""

    def test_no_weakening_of_the_primarys_exclusion_releases_the_add_on(self):
        """RD-2: every single weakening of the ADDON fixture - the classic four, the value-erasing contradictions and
        views - leaves 43273 held: its primary 43264, which a statement still may exclude, is never counted (as built,
        29 states released it: E1's and E4's kind, E6's status, session and breadth, each weakened)."""
        R, codes = fixture(ADDON_FIXTURE)
        found = TA.by_code(assessed(R, codes))  # the fixture's shape: 43264 excluded, 43273 held by its row alone
        self.assertIsNotNone(found['43264'].evaluation.exclusion)
        self.assertEqual([held.cause for held in found['43273'].held_facts], [AS.ADDON_CAUSE])
        checked = 0
        for label, changed, _what in weakenings(R):
            with self.subTest(weakening=label):
                found = TA.by_code(assessed(changed, codes))
                self.assertNotEqual(found['43273'].status, Outcome.READY)
                if found['43264'].status is not Outcome.EXCLUDED and found['43264'].evaluation is not None:
                    self.assertTrue(AS.addon_uncounted('43264', found['43264'].evidence.kept, changed,
                                                       found['43264'].evidence.runs), label)
                checked += 1
        self.assertGreater(checked, 150)

    def test_no_weakening_of_the_denial_of_a_kind_narrows_or_releases(self):
        """RD-3: each 9.4 weakening of E1's established kind denial leaves every kind open for coverage.may_be and for
        both arms of facts.possible_kinds (every other kind before, every kind after - never the denied kind alone), and
        releases nothing (as built, 45385 went READY under each: E1 read as an examination only)."""
        from studio.interpretation.engine import coverage

        R, codes = fixture(KIND_DENIAL_FIXTURE)
        base = assessed(R, codes)
        kind = F.fact(R, EF.E(1), A.KIND)  # the fixture's shape: E1's kind an established denial, 45385 held
        self.assertEqual((kind.result, kind.state, kind.value), (Res.NEGATED, ct.FactState.NEGATED, Kind.EXAMINATION))
        self.assertEqual(TA.by_code(base)['45385'].status, Outcome.NEEDS_CLARIFICATION)
        before = coverage.may_be(F.fact(R, EF.E(1), A.KIND))
        self.assertNotIn(Kind.EXAMINATION, before)
        self.assertGreater(len(before), 30)  # every other kind, an umbrella read as its members
        checked = 0
        for label, changed, what in weakenings(R):
            if what[:2] != (EF.E(1), A.KIND):
                continue
            with self.subTest(weakening=label):
                found = F.fact(changed, EF.E(1), A.KIND)
                self.assertLessEqual(before | {Kind.EXAMINATION}, coverage.may_be(found))  # the denial may be wrong
                for of_family in (False, True):
                    self.assertEqual(F.possible_kinds(changed, EF.E(1), of_family=of_family), frozenset(Kind))
                after = assessed(changed, codes)
                self.assertEqual(_release(base, after)[:2], (frozenset(), frozenset()))
                checked += 1
        self.assertEqual(checked, len(HOWS))  # a required fact: no value-erasing contradiction of a denial

    def test_every_row_met_reads_assess_addon_row(self):
        """RD-2: D264's every-row check holds a READY add-on to assess's ADDON row over the codes proposed beside it - in
        the ADDON fixture 43273's support rows are all T but its only primary is excluded, so the check fails it there
        (naming the row) and without the proposals (fail-closed); beside 43264 held by YIELD (an act surely done) it
        meets the row."""
        R, codes = fixture(ADDON_FIXTURE)
        met, failing = every_row_met('43273', R, assessment=assessed(R, codes))
        self.assertFalse(met)
        self.assertEqual(list(failing), ['ADDON'])
        self.assertFalse(every_row_met('43273', R)[0])
        held = TA.dated(TA.ercp().build())
        proposals = (('43264', 5), ('43273', 3))
        self.assertEqual(every_row_met('43273', held, assessment=assessed(held, proposals)), (True, {}))
        self.assertEqual(every_row_met('45385', fixture('enriched')[0]), (True, {}))  # no add-on: no ADDON row

    def test_the_generator_keeps_a_negated_claim_negated(self):
        """A conflict doubt on a denial is a contradicted denial (settle keeps pass 1's claim and its state, which the
        FactSet reads), and a denial has no pass-1 contradiction of its value (its sides would be stated); a stated claim
        is weakened as before. The contradicted denial, read so, releases nothing (as built, 45385 went READY)."""
        R, codes = fixture(KIND_DENIAL_FIXTURE)
        denial = F.fact(R, EF.E(1), A.KIND)
        conflict = _weakened_fact(denial, 'doubt conflict')
        self.assertEqual((conflict.result, conflict.state, conflict.value), (Res.CONTRADICTED, ct.FactState.NEGATED,
                                                                             Kind.EXAMINATION))
        changed = _with(R, 'events', EF.E(1), {**R.events[EF.E(1)], A.KIND: (conflict,)})
        self.assertEqual(TA.by_code(assessed(changed, codes))['45385'].status, Outcome.NEEDS_CLARIFICATION)
        self.assertIsNone(erased_fact(denial, 'contradiction', Kind.BIOPSY))
        stated = F.fact(R, EF.E(2), A.KIND)
        self.assertEqual(_weakened_fact(stated, 'doubt conflict').state, ct.FactState.CONTRADICTED)
        self.assertEqual(erased_fact(stated, 'contradiction', Kind.BIOPSY).options, (stated.value, Kind.BIOPSY))
