"""Round r3's build continued, lane "ask" of the repair after the mandatory adversarial pass over int4 (DECISIONS D324:
items (3), (8) and (11)). Every input is SYNTHETIC (invented ids, spans and facts: tests/v2/evaluate_fixtures' builders,
r2f's q04 bound scene seeded as its refuter seeded it, and the L1-01 verifier's fictional note): no document is read and
nothing is sent. Red on int4: each class pins a rule int4's planner does not have.

- AbsorbActsTests, AbsorbEligibleTests, AbsorbProofTests, AbsorbPipelineTests (D324 (3), L1-01): Q-ABSORB names only
  PERFORMED acts - its act list holds only acts for which asking.performed_act holds (the predicate _acts_of applies to
  denials); an entry that tells or doubts a planned, attempted or in-doubt act then reads as an act none of the listed
  acts are, and its answer cannot absorb it; where no such list can be built the question is not asked and the entry
  holds. Settle's re-check (asking.eligible) refuses a stored question whose list names any other act. The finding's
  own inputs (the planned and the attempted worlds; the verifier's unlisted DOUBT beside an established attempt), at
  the engine, through the locator, and through the whole pipeline (test_question_stage's scripted harness).
- WorldTests, PairReadTests, OnLesionMemoTests, SilentReachTests, PlanCostTests (D324 (8), L7-A7-PLAN-COST): every
  what-if the planner repeats per value or per witness reads ONE evaluation per FactSet (each what-if world built once
  with one Reader, each candidate evaluated over it once; the Q-ONLESION what-if once per pair; a relation witness's
  pairs read from the plan's one Reader, so the base FactSet's pairs are computed once per plan); no per-value what-if
  for a filter that cannot drop a value - A3's silent reach (ASK2-1's moves filter) is gone, its values read from the
  code's own reach tables, the enteroscopy class's included, pinned over every code by the filter's own what-if; and a
  MEASURED cost test at FINAL-V2 1.8's bound scene (100 listed denials, 99 tattoos, 64 lesions with dense same_as) for
  the round-1 plan and the post-send child's two plans, each with its 1-minute load.
- RequirementsVersionTests (D324 (11)): REQUIREMENTS_VERSION is cpt-requirements@3.
"""
from __future__ import annotations

import dataclasses
import os
import random
import sys
import time
from collections import Counter
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from studio.interpretation import REQUIREMENTS_VERSION
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, catalogue, coverage, pairing, whatif
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Attribute as A
from studio.interpretation.engine.types import HeldFact, Id, IdFamily, ItemKind
from tests.v2 import test_assess as TA
from tests.v2 import test_pairing as TP
from tests.v2.evaluate_fixtures import (L, X, Doc, Kind, SessionKind, Status, colonoscopy, doubted, neg, sup, unit,
                                        unlisted, unres)

LM = ct.Landmark
SIG = LM.SIGMOID_COLON
QF = asking.Family


# --- D324 (3): Q-ABSORB names only performed acts (L1-01) ---------------------------------------------------------------


def absorb_world(name: str, what: ct.UnlistedWhat = ct.UnlistedWhat.ACT, entry_session: Id | None = X(1)):
    """The L1-01 verifier's probe A worlds (its a_engine.py and a2_doubt.py, rebuilt here): a colonoscopy X1 (its
    examination E1), one single sigmoid lesion L1, the done cold-forceps biopsy E3 of L1, and pass 2's kept unlisted
    entry U (kind snare, session ``entry_session``) - "The polyp was then removed with a hot snare." for an ACT, "It is
    unclear whether any of the polyp was removed." for a DOUBT. E2, the snare act of L1 pass 1 filed, varies by world."""
    doc = Doc()
    doc.session(1, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(ct.Extent.CECUM)])
    doc.exam(1)
    doc.lesion(1, lesion_places=[sup(SIG)], multiplicity=sup(ct.Multiplicity.SINGLE))
    doc.act(3, Kind.BIOPSY, places=[sup(SIG)], lesion=sup(L(1)), device=sup(ct.Device.COLD_FORCEPS))
    snare = dict(places=[sup(SIG)], lesion=sup(L(1)))
    statuses = {'planned': sup(Status.PLANNED), 'attempted': sup(Status.ATTEMPTED_NOT_COMPLETED),
                'unresolved': unres(Status.ATTEMPTED_NOT_COMPLETED),
                'doubted': doubted(Status.PERFORMED, Status.PERFORMED, Status.PLANNED),
                'denied': neg(Status.PERFORMED), 'performed': sup(Status.PERFORMED),
                'unresolved_performed': unres(Status.PERFORMED)}
    if name in statuses:
        doc.act(2, Kind.SNARE, status=statuses[name], device=sup(ct.Device.HOT_SNARE), **snare)
    doc.unlisted.append(unlisted(what, Kind.SNARE, entry_session, unit(9)))
    return doc.build()


def performed_elsewhere(kind: Kind):
    """E2 alone: a PERFORMED act of ``kind`` in the ascending colon (no lesion), for the boundary scenes."""
    doc = Doc()
    doc.act(2, kind, places=[sup(LM.ASCENDING_COLON)])
    return doc


def absorb_specs(R) -> list[asking.QuestionSpec]:
    return [spec for spec in asking.plan(R, ()).specs if spec.family is QF.Q_ABSORB]


def established(spec: asking.QuestionSpec) -> dict:
    """The record settle writes for an ESTABLISHED question (its claim supported, located, control rejected)."""
    return {'family': spec.family.value, 'form': spec.form, 'subjects': list(spec.subjects),
            'attribute': spec.attribute.value if spec.attribute else None, 'value': spec.value,
            'unlisted': asking.unlisted_index(spec.subjects), 'negated': spec.negated, 'result': 'supported',
            'reasons': [], 'proof': [{'start': 900, 'end': 944}, {'start': 200, 'end': 250}]}


# any held fact: the census row of an entry with no act to re-tell does not read it
TA_HELD = HeldFact(fact='performed_status', attribute=None, subject=X(1), result=None, kind=ItemKind.QUESTION,
                   cause='unlisted', reason=None, spans=(), rank=2)


def codes(R, proposals=(('45380', 3), ('45385', 2))) -> dict:
    found = TA.by_code(TA.run(R, *proposals))
    return {code: found[code].status.value for code, _ in proposals}


class AbsorbActsTests(SimpleTestCase):
    """The planner's act list (asking._acts_of, _absorb_spec)."""

    def test_l1_01_the_findings_own_worlds_list_no_planned_or_attempted_act(self):
        # L1-01: E2 established PLANNED (pass 2 supporting a plan for an act the note says was done) or ATTEMPTED (the
        # failed cold attempt, the hot-snare removal unfiled), beside U "The polyp was then removed with a hot snare." -
        # int4 asked "This statement tells or doubts no act other than acts A1, A2 and A3." with A2 = E2, so a TRUE
        # answer ("U re-tells A2") absorbed U and 45380 went READY where the true world holds it
        # (coding_rule:biopsy_of_removed_lesion). Built: only the performed E1 and E3 are listed
        for name in ('planned', 'attempted'):
            R = absorb_world(name)
            with self.subTest(world=name):
                specs = absorb_specs(R)
                self.assertEqual([spec.acts for spec in specs], [('E1', 'E3')])
                self.assertFalse(asking.performed_act(R, Id.parse('E2')))
                self.assertEqual(specs[0].census, 'U3')

    def test_l1_01_the_verifiers_doubt_beside_an_established_attempt(self):
        # the verifier's strongest case: every filed fact true as worded (E2 an established attempt), pass 2's kept
        # unlisted DOUBT "It is unclear whether any of the polyp was removed." - int4's list named the attempt, so the
        # true answer "it doubts A2's removal" absorbed it while 45385 stayed held for that very doubt
        for name in ('attempted', 'planned'):
            R = absorb_world(name, ct.UnlistedWhat.DOUBT)
            with self.subTest(world=name):
                self.assertEqual([spec.acts for spec in absorb_specs(R)], [('E1', 'E3')])

    def test_variants_every_act_not_established_performed_is_left_out(self):
        # generality, at the rule itself (_acts_of: the list every absorb question is built with): every status that is
        # not ESTABLISHED performed - an attempt or a plan, established or unresolved, a pass-1 doubt of the act, an
        # unresolved performed claim, a denial - whatever the entry is (an act, a doubt) and its scope (its session, or
        # the document when it names none); and where the plan asks, its spec carries exactly that list
        for name in ('planned', 'attempted', 'unresolved', 'doubted', 'unresolved_performed', 'denied'):
            for what in (ct.UnlistedWhat.ACT, ct.UnlistedWhat.DOUBT):
                for scope in (X(1), None):
                    R = absorb_world(name, what, scope)
                    with self.subTest(world=name, what=what.value, scope=str(scope)):
                        self.assertEqual(asking._acts_of(R, scope), ('E1', 'E3'))
                        for spec in absorb_specs(R):
                            self.assertEqual(spec.acts, ('E1', 'E3'))
        # a document-scope entry (no session named) beside an attempt in ANOTHER session: only performed acts anywhere
        doc = Doc()
        doc.session(1, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                    reached=[sup(ct.Extent.CECUM)])
        doc.session(2, SessionKind.EGD, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                    reached=[sup(ct.Extent.SECOND_PORTION_DUODENUM)])
        doc.exam(1)
        doc.exam(4, session=X(2))
        doc.act(5, Kind.BIOPSY, session=X(2), status=sup(Status.ATTEMPTED_NOT_COMPLETED), places=[sup(LM.STOMACH)])
        doc.act(6, Kind.SNARE, session=X(2), status=unres(Status.PERFORMED), places=[sup(LM.STOMACH)])
        doc.act(3, Kind.BIOPSY, places=[sup(SIG)])
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.SNARE, None, unit(9)))
        R = doc.build()
        self.assertEqual(asking._acts_of(R, None), ('E1', 'E4', 'E3'))
        self.assertEqual(asking._acts_of(R, X(2)), ('E4',))
        self.assertEqual(asking._acts_of(R, X(1)), ('E1', 'E3'))

    def test_no_performed_act_to_re_tell_asks_nothing_and_the_entry_holds(self):
        # "where the list cannot be built so, the absorb question is not asked and the entry holds": the session's only
        # act beside the entry is a planned one and its examination is planned too - no act established performed
        doc = Doc()
        doc.session(1, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                    reached=[sup(ct.Extent.CECUM)])
        doc.exam(1, status=sup(Status.PLANNED))
        doc.act(2, Kind.SNARE, status=sup(Status.PLANNED), places=[sup(SIG)])
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.SNARE, X(1), unit(9)))
        R = doc.build()
        self.assertEqual(asking._acts_of(R, X(1)), ())
        found = asking.plan(R, ())
        self.assertEqual([spec for spec in found.specs if spec.family is QF.Q_ABSORB], [])
        self.assertEqual(asking._absorb_spec(R, '45380', TA_HELD, 0).blocked, 'U3 (no act to re-tell)')

    def test_boundary_every_act_performed_or_a_denial_keeps_the_list(self):
        # the boundary the rule must leave alone: where E2 is a denial (a statement: always left out) or there is no E2
        # at all, the list is exactly what int4 listed (the L1-01 verifier's 'denied' and 'none' worlds: E1, E3); a
        # PERFORMED act beside them - a tattoo, a clip, a biopsy of another place - is listed, in pass 1's order
        for name in ('none', 'denied'):
            with self.subTest(world=name):
                self.assertEqual([spec.acts for spec in absorb_specs(absorb_world(name))], [('E1', 'E3')])
        for kind in (Kind.TATTOO, Kind.CLIP, Kind.BIOPSY):
            R = dataclasses.replace(absorb_world('none'), events={
                **absorb_world('none').events, **performed_elsewhere(kind).events})
            R = dataclasses.replace(R, anchors={**R.anchors, **performed_elsewhere(kind).anchors})
            with self.subTest(performed=kind.value):
                self.assertEqual([spec.acts for spec in absorb_specs(R)], [('E1', 'E3', 'E2')])

    def test_the_finding_s_engine_consequence(self):
        # the engine reads an established absorb answer as before (the fold: facts._answered) - what changes is the
        # claim it can be established for. Over int4's list (A2 the plan) an answer TRUE as worded absorbed U and
        # released 45380; over the built list (A1, A3) the same entry is "an act that is none of" them, so the true
        # answer is contradicts and nothing folds: 45380 stays held, as in the true world
        R = absorb_world('planned')
        self.assertEqual(codes(R)['45380'], 'needs_clarification')
        [spec] = absorb_specs(R)
        self.assertEqual(spec.acts, ('E1', 'E3'))
        unresolved = {**established(spec), 'result': 'unresolved', 'reasons': ['question_contradicts']}
        self.assertEqual(codes(F._answered(R, {'questions': [unresolved]}))['45380'], 'needs_clarification')


class AbsorbEligibleTests(SimpleTestCase):
    """Settle's re-check (d.2 row 1: asking.eligible over R_base) of a Q-ABSORB question's act list."""

    def spec(self, acts):
        return asking.QuestionSpec(QF.Q_ABSORB, 'absorb', ('u:0',), None, '', False, ('u:0', 'acts:X1'), acts=acts,
                                   census='U3')

    def test_l1_01_a_list_naming_a_planned_or_attempted_act_is_never_established(self):
        # int4's planner named E2 (the plan, the attempt): settle's re-check accepted any held entry, so its supported
        # answer was established; now a list naming any act not established performed is not eligible
        for name in ('planned', 'attempted'):
            R = absorb_world(name)
            with self.subTest(world=name):
                self.assertFalse(asking.eligible(self.spec(('E1', 'E3', 'E2')), R))
                self.assertTrue(asking.eligible(self.spec(('E1', 'E3')), R))

    def test_variants_every_other_name_is_refused(self):
        R = absorb_world('performed')
        for acts, expected in ((('E1', 'E3', 'E2'), True), ((), False), (('E9',), False), (('X1',), False),
                               (('L1',), False), (('u:0',), False), (('E1', 'not-an-id'), False)):
            with self.subTest(acts=acts):
                self.assertIs(asking.eligible(self.spec(acts), R), expected)
        for name in ('denied', 'unresolved', 'doubted', 'unresolved_performed'):
            with self.subTest(world=name):
                self.assertFalse(asking.eligible(self.spec(('E1', 'E2')), absorb_world(name)))

    def test_boundary_the_entry_index_is_still_read(self):
        R = absorb_world('none')
        out_of_range = asking.QuestionSpec(QF.Q_ABSORB, 'absorb', ('u:1',), None, '', False, ('u:1', 'acts:X1'),
                                           acts=('E1', 'E3'))
        self.assertFalse(asking.eligible(out_of_range, R))
        self.assertTrue(asking.eligible(self.spec(('E1', 'E3')), R))


# --- the proof of an absorb answer (contract/proof.locate over the product's request builder) ----------------------------

PLANNED_NOTE = ('SYNTHETIC COLONOSCOPY REPORT\n'                                                  # S1
                'Date of service: 03/14/2031\n'                                                    # S2
                'Endoscopist: Corvin Ashdale, MD (fictional)\n'                                    # S3
                'Findings: The colonoscope was advanced to the cecum.\n'                          # S4
                'Plan: hot snare polypectomy of the 8 mm sigmoid polyp.\n'                        # S5: E2, the plan
                'Cold forceps biopsies of the sigmoid polyp were taken first.\n'                  # S6: E3, the biopsy
                'The polyp was then removed with a hot snare.\n')                                 # S7: U, unlisted
U_WORDS = 'The polyp was then removed with a hot snare.'
PLAN_WORDS = 'hot snare polypectomy of the 8 mm sigmoid polyp'
BIOPSY_WORDS = 'Cold forceps biopsies of the sigmoid polyp'


class AbsorbProofTests(SimpleTestCase):
    """The proof an absorb answer needs: one quote in the entry's own units and one in the units of one of the LISTED
    acts (b.0, contract/question_claims and contract/proof as built) - so with the plan no longer listed, a 'supports'
    answer quoting the plan (the L1-01 attacker's answer, true as worded over int4's list) does not locate."""

    def item(self, R):
        from tests.v2 import test_r3_claims as RC

        [spec] = absorb_specs(R)
        cards, objects = RC._cards(('A1', ct.CardType.ACT, 'event', 'E1', ('S4',)),
                                   ('A2', ct.CardType.ACT, 'event', 'E2', ('S5',)),
                                   ('A3', ct.CardType.ACT, 'event', 'E3', ('S6',)))
        built = RC.built_request(PLANNED_NOTE, cards, objects, [spec],
                                 unlisted_=[{'units': ['S7'], 'what': 'act', 'kind': 'snare', 'session': 'X1'}])
        return built.items[0], RC.located

    def test_l1_01_a_quote_of_the_plan_no_longer_proves_the_absorb_claim(self):
        for name in ('planned', 'attempted'):
            item, located = self.item(absorb_world(name))
            with self.subTest(world=name):
                self.assertFalse(located(PLANNED_NOTE, item, [U_WORDS, PLAN_WORDS]).located)  # int4: located
                # the boundary: the mechanism still proves the claim from a LISTED act's own words
                self.assertTrue(located(PLANNED_NOTE, item, [U_WORDS, BIOPSY_WORDS]).located)
                self.assertFalse(located(PLANNED_NOTE, item, [BIOPSY_WORDS]).located)  # the entry's own words needed


# --- the whole pipeline (the L1-01 verifier's test_verify_l1_01, its assertions made) -------------------------------------


def _pipeline():
    """The verifier's pipeline worlds over test_question_stage's harness (imported only by the DB tests below)."""
    from studio import models
    from studio.interpretation import fable_adapter
    from studio.providers.base import request_sha256
    from tests.v2 import test_jobs as TJ
    from tests.v2 import test_question_stage as QS
    from tests.v2.test_settle import colonoscopy as settle_colonoscopy
    from tests.v2.test_settle import event, fact, faithful, lesion, src, unlisted_entry

    head = ('SYNTHETIC COLONOSCOPY REPORT\nDate of service: 03/14/2031\nEndoscopist: Corvin Ashdale, MD (fictional)\n\n'
            'Findings: The colonoscope was advanced to the cecum.\n')
    planned = head + ('Plan: hot snare polypectomy of the 8 mm sigmoid polyp.\n'
                      'Cold forceps biopsies of the sigmoid polyp were taken first.\n'
                      'The polyp was then removed with a hot snare.\n')
    doubted_text = head + ('Cold forceps biopsies of the 8 mm sigmoid polyp were taken.\n'
                           'Cold snare polypectomy of the sigmoid polyp was attempted but could not be completed.\n'
                           'It is unclear whether any of the polyp was removed.\n')

    def l1(unit_, words):
        return lesion('L1', src([unit_], words), multiplicity=[fact('single', src([unit_], words))],
                      places=[fact('sigmoid_colon', src([unit_], 'sigmoid'))])

    def of_l1(unit_, words):
        return dict(session=[fact('X1', src([unit_]))], target__lesion=[fact('L1', src([unit_], words))],
                    target__places=[fact('sigmoid_colon', src([unit_], 'sigmoid'))])

    def planned_misfiled():
        return settle_colonoscopy(planned,
                                  event('E2', ['S5'], 'hot snare polypectomy', 'Plan', 'snare', status='planned',
                                        technique__device=[fact('hot_snare', src(['S5'], 'hot snare'))],
                                        **of_l1('S5', '8 mm sigmoid polyp')),
                                  event('E3', ['S6'], 'Cold forceps biopsies', 'were taken', 'biopsy',
                                        technique__device=[fact('cold_forceps', src(['S6'], 'Cold forceps'))],
                                        **of_l1('S6', 'sigmoid polyp')),
                                  lesions=[l1('S5', '8 mm sigmoid polyp')])

    def doubted_pass1():
        attempt = event('E2', ['S6'], 'Cold snare polypectomy', 'was attempted', 'snare',
                        status='attempted_not_completed',
                        technique__device=[fact('cold_snare', src(['S6'], 'Cold snare'))], **of_l1('S6', 'sigmoid polyp'))
        biopsy = event('E3', ['S5'], 'Cold forceps biopsies', 'were taken', 'biopsy',
                       technique__device=[fact('cold_forceps', src(['S5'], 'Cold forceps'))],
                       **of_l1('S5', '8 mm sigmoid polyp'))
        return settle_colonoscopy(doubted_text, attempt, biopsy, lesions=[l1('S5', '8 mm sigmoid polyp')])

    class Interpreter(QS.QuestionInterpreter):
        """QuestionInterpreter with pass 2's unlisted entry and the L1-01 attacker's answer to every question request:
        the absorb claim supported with a quote from U and one from E2 (true as worded over int4's list), its exact
        negation contradicted; the calibration item in its holding direction; any other question unclear."""

        def __init__(self, answers, *, built, unlisted, quotes):
            super().__init__(answers, oracle=faithful, built=built)
            self.unlisted, self.quotes, self.absorb_lines = unlisted, quotes, []

        def _exchange(self, body_dict, deadline, purpose):
            kind = fable_adapter.request_kind(body_dict)[0]
            if kind == fable_adapter.QUESTION:
                sha = request_sha256(body_dict)
                with self.guard:
                    self.question_sent.append(sha)
                return TJ.answered(TJ.body(self.answer(self.built[sha])))
            if purpose == TJ.APPRAISAL:
                sha = request_sha256(body_dict)
                self.sent.append((purpose, sha))
                text = self._request.contexts[0]
                built = TJ.appraisal_for(*self._document(text), self.answers[text]())
                card = next(card for card, item in built.built.claim_set.objects.items() if str(item[1]) == 'X1')
                entries = [unlisted_entry(units, what, kind_, card) for units, what, kind_ in self.unlisted]
                return TJ.answered(TJ.oracle_answer(built, self.oracle, unlisted=entries))
            return super()._exchange(body_dict, deadline, purpose)

        def answer(self, question):
            verdicts = []
            for item in question.items:
                unit_ = [item.cited[0]] if item.cited else []
                if item.role == 'calibration':
                    pairs = [(item.claim, 'contradicts', []), (item.control, 'supports', [])]
                elif item.spec.family is QF.Q_ABSORB:
                    self.absorb_lines.append(item.claim_sentence)
                    pairs = [(item.claim, 'supports', list(self.quotes)), (item.control, 'contradicts', [])]
                    unit_ = ['S7'] if 'S7' in item.cited else unit_
                else:
                    pairs = [(item.claim, 'unclear', []), (item.control, 'unclear', [])]
                for claim_id, value, quotes in pairs:
                    verdicts.append({'claim': claim_id, 'verdict': value, 'attached': 'yes', 'qualifiers': [],
                                     'evidence': unit_, 'quotes': quotes})
            verdicts.sort(key=lambda node: int(node['claim'][1:]))
            return {'verdicts': verdicts, 'unlisted': []}

    selections = {planned: [('45380', 'Cold forceps biopsies of the sigmoid polyp were taken first.'),
                            ('45385', 'The polyp was then removed with a hot snare.')],
                  doubted_text: [('45380', 'Cold forceps biopsies of the 8 mm sigmoid polyp were taken.'),
                                 ('45385', 'Cold snare polypectomy of the sigmoid polyp was attempted but could not be '
                                           'completed.')]}
    worlds = {'planned': (planned, planned_misfiled, [(['S7'], 'act', 'snare')],
                          (U_WORDS, PLAN_WORDS)),
              'doubted': (doubted_text, doubted_pass1, [(['S7'], 'doubt', 'snare')],
                          ('It is unclear whether any of the polyp was removed.',
                           'Cold snare polypectomy of the sigmoid polyp was attempted'))}
    return models, fable_adapter, TJ, QS, Interpreter, selections, worlds


def _pipeline_case():
    from tests.v2 import test_question_stage as QS

    class AbsorbPipelineTests(QS.QuestionCase):
        """The L1-01 verifier's whole-pipeline reproduction on its fictional note (upload, both passes, settle keeping
        pass 2's unlisted entry, the QUESTION stage - plan, pool, draw, partition, builder, reader, locator, health - the
        one row, then analyze, predict and assess), every provider exchange scripted (nothing is sent)."""

        def world(self, name):
            models, fable_adapter, TJ, QS_, Interpreter, selections, worlds = _pipeline()
            text, pass1, unlisted_, quotes = worlds[name]
            self.provider = TJ.FakeProvider(selections[text])
            interpreter = Interpreter({text: pass1}, built=self.built, unlisted=unlisted_, quotes=quotes)
            patcher = QS_.mock.patch.object(fable_adapter, 'get_interpreter_v2', return_value=interpreter)
            patcher.start()
            self.addCleanup(patcher.stop)
            self.interpreter = interpreter
            encounter, revision = self.upload(text)
            done = self.drain()
            encounter.refresh_from_db()
            inventory = models.EventInventory.objects.get(revision=revision)
            statuses = {p.code: p.status for p in encounter.current_assessment.proposals.all()}
            absorbs = [record for record in inventory.events.get('questions') or ()
                       if record.get('family') == QF.Q_ABSORB.value]
            self.assertEqual([job.kind for job in done][-1], 'assess', [(job.kind, job.state) for job in done])
            return statuses, absorbs, interpreter.absorb_lines

        def test_l1_01_the_planned_world_end_to_end(self):
            # int4: the absorb line named A2 (the plan), the attacker's quotes located, the record was supported and
            # 45380 went READY (its true world holds it: coding_rule:biopsy_of_removed_lesion)
            statuses, absorbs, lines = self.world('planned')
            self.assertEqual(lines, ['This statement tells or doubts no act other than acts A1 and A3.'])
            self.assertEqual([record['result'] for record in absorbs], ['unresolved'])
            self.assertNotEqual(statuses['45380'], 'ready')

        def test_l1_01_the_verifiers_doubt_beside_an_established_attempt_end_to_end(self):
            # the cards follow the note's order: the biopsy E3 (S5) is A2, the attempt E2 (S6) A3 - int4 listed all three
            statuses, absorbs, lines = self.world('doubted')
            self.assertEqual(lines, ['This statement tells or doubts no act other than acts A1 and A2.'])
            self.assertEqual([record['result'] for record in absorbs], ['unresolved'])
            self.assertNotEqual(statuses['45380'], 'ready')

    return AbsorbPipelineTests


AbsorbPipelineTests = _pipeline_case()


# --- D324 (8): the plan's cost (L7-A7-PLAN-COST) -------------------------------------------------------------------------

COLON = [LM.CECUM, LM.ASCENDING_COLON, LM.HEPATIC_FLEXURE, LM.TRANSVERSE_COLON, LM.SPLENIC_FLEXURE,
         LM.DESCENDING_COLON, LM.SIGMOID_COLON, LM.RECTUM, LM.RECTOSIGMOID, LM.ILEOCECAL_VALVE]
LESION_PLACES = [LM.CECUM, LM.ASCENDING_COLON, LM.HEPATIC_FLEXURE, LM.TRANSVERSE_COLON, LM.SPLENIC_FLEXURE,
                 LM.DESCENDING_COLON, LM.SIGMOID_COLON, LM.ILEOCECAL_VALVE]
ASKED = [LM.RECTUM, LM.RECTOSIGMOID, LM.APPENDICEAL_ORIFICE, LM.TERMINAL_ILEUM, LM.JEJUNUM, LM.ILEUM]


def bound_scene(S: int, T: int):
    """r2f's q04 scene (rf2-f-lesion/probes/q04_cost.py; FINAL-V2 1.8's bounds), seeded as its refuter and the L7-A7
    verifier seeded it (random.Random(20261114)): 64 lesions, each single with 8 places and 16 unresolved same_as members
    (3 options each); S listed denials of an injection (32 targets, 8 places each); T tattoos naming no lesion (8 places
    each), each asked about 6 places by rejected place pair controls (at most 640). S=100, T=99 is the 200-event bound."""
    rng = random.Random(20261114)
    lesion_ids = [Id(IdFamily.LESION, n) for n in range(1, 65)]
    missing = [Id(IdFamily.LESION, 100 + n) for n in range(1, 9)]
    lesions = {}
    for lesion_id in lesion_ids:
        others = [other for other in lesion_ids if other != lesion_id]
        members = []
        for _ in range(16):
            value = rng.choice(missing) if rng.random() < 0.1 else rng.choice(others)
            members.append(unres(value, options=tuple(rng.sample(others, 3))))
        lesions[lesion_id] = {A.PLACES: tuple(sup(place) for place in LESION_PLACES), A.DISTINCT_FROM: (),
                              A.SAME_AS: tuple(members), A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),)}
    events = {Id(IdFamily.EVENT, 1): TP.act(kind=sup(ct.Kind.EXAMINATION), lesion=None, places=())}
    for number in range(2, 2 + S):
        events[Id(IdFamily.EVENT, number)] = TP.denial(
            kind=sup(ct.Kind.INJECTION), breadth=sup(ct.Breadth.LISTED_TARGETS),
            targets=tuple(sup(lesion) for lesion in rng.sample(lesion_ids, 32)),
            places=tuple(sup(place) for place in rng.sample(COLON, 8)))
    controls = {}
    for number in range(2 + S, 2 + S + T):
        act = Id(IdFamily.EVENT, number)
        places = rng.sample(COLON, 8)
        events[act] = TP.act(kind=sup(ct.Kind.TATTOO), lesion=None, device=None, places=tuple(sup(p) for p in places))
        for place in ASKED:
            if len(controls) < 640:
                controls[(act, A.TARGET_PLACES, place)] = True
    return TP.build(events, lesions=lesions, controls=controls)


def plan_fields(found: asking.Plan) -> tuple:
    """Everything a plan gives: each spec whole (in order), the codes each serves, the census counts."""
    return (found.specs, dict(found.serves), dict(found.blocked), dict(found.releasable))


def unmemoized_plan(R, asked=(), events=None):
    """The plan as int4 computed its what-ifs - every world built afresh at every ask, each candidate re-evaluated with
    a Reader of its own, the Q-ONLESION what-if per witness, a relation witness's pairs recomputed by pairing.pairs_of
    and scanned per witness, nothing prefetched - the reference the memoized plan must equal."""
    def world(self, subject, attribute, value):
        changed = asking._established_at(self.R, subject, attribute, value)
        return (subject, attribute, asking._value_of(value)), (None if changed is None else (changed, None))

    def witnesses_in(self, key, made, candidate):
        return whatif.candidate_witnesses(made[0], candidate.code, candidate.group, candidate.event)

    def relation(self, held):
        return tuple(pair for pair in pairing.pairs_of(self.reader.R, self.event)
                     if pairing.cause(pair) == held.cause and pair.spans == held.spans)

    with mock.patch.object(asking._Context, 'prefetch', lambda self, candidates: None), \
            mock.patch.object(asking._Context, 'world', world), \
            mock.patch.object(asking._Context, 'witnesses_in', witnesses_in), \
            mock.patch.object(asking._Context, 'onlesion_unanswerable',
                              lambda self, statement, act, lesions: asking._onlesion_unanswerable(self.R, statement,
                                                                                                    act, lesions)), \
            mock.patch.object(whatif._EventPairs, 'relation', relation):
        return asking.plan(R, asked, events)


def silent_reach_scenes():
    """Every catalogue code (and route (b)'s) in a session of its family (each endoscopic family for a code no family
    routes), for each requirement group's first kind, with a SILENT reach list: the A3 branch's population."""
    families = [kind for kind in SessionKind if kind in catalogue.ENDOSCOPIC_FAMILIES]
    for number in (*catalogue.CODES, *whatif.ROUTE_B_CODES):
        code = str(number)
        link = catalogue.code_link(code)
        groups = catalogue.requirements(link)
        if not link.linked or not groups:
            continue
        for family in ([link.family] if isinstance(link.family, SessionKind) else families):
            for group in groups:
                doc = Doc()
                doc.session(1, family, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
                doc.exam(1)
                if group[0] is not Kind.EXAMINATION:
                    doc.act(2, group[0])
                yield f'{code}:{family.value}:{group[0].value}', code, doc.build()


def _counting(target, name, counter, key):
    real = getattr(target, name)

    def counted(*args, **kwargs):
        counter[key(*args, **kwargs)] += 1
        return real(*args, **kwargs)
    return mock.patch.object(target, name, counted)


class WorldTests(SimpleTestCase):
    """The value rule's what-ifs: one evaluation per FactSet."""

    def test_l7_a7_each_world_is_built_once_and_each_candidate_evaluated_once_over_it(self):
        # L7-A7: int4 built a what-if FactSet at every ask - per value, per witness, per candidate code (the bound
        # scene at S=6: some world built 12 times) - each evaluated with a Reader of its own
        R = bound_scene(6, 5)
        built: Counter = Counter()
        evaluated: Counter = Counter()
        held = []  # every FactSet counted is kept alive, so no id is reused by another FactSet during the count

        def candidate(R_, code, group, event, reader=None):
            held.append(R_)
            return (id(R_), code, tuple(group), event)
        with _counting(asking, '_established_at', built, lambda R_, subject, attribute, value: (subject, attribute,
                                                                                                  str(value))), \
                _counting(whatif, 'candidate_witnesses', evaluated, candidate):
            found = asking.plan(R, ())
        self.assertTrue(found.specs)
        self.assertTrue(built)
        self.assertEqual(max(built.values()), 1, built.most_common(3))
        self.assertEqual(max(evaluated.values()), 1, evaluated.most_common(3))
        served = Counter(key[0] for key in evaluated if key[0] != id(R))
        self.assertGreater(max(served.values()), 1)  # not vacuous: a world serves several candidates

    def test_l7_a7_each_worlds_engine_readings_are_built_once(self):
        # prefetch: every world the classification asks is evaluated for all its candidates in a row, so the engine's
        # per-FactSet readings of a world (facts' same_as components, built once per FactSet and kept for the eight read
        # last) are built ONCE per world - never again when a later code's candidate asks the same world after other
        # worlds were read (the bound scene at S=12: 12 worlds, each asked by two codes' candidates)
        R = bound_scene(12, 11)
        components: Counter = Counter()
        held = []  # every FactSet counted is kept alive, so no id is reused by another FactSet during the count

        def key(R_):
            held.append(R_)
            return id(R_)
        with _counting(F, '_components', components, key):
            found = asking.plan(R, ())
        self.assertTrue(found.specs)
        self.assertGreater(len(components), 12)  # the worlds, R and the arm's assumed FactSets
        self.assertEqual(max(components.values()), 1, components.most_common(3))

    def test_each_world_is_read_through_its_own_reader(self):
        R = bound_scene(3, 2)
        readers = []
        real = whatif.candidate_witnesses

        def recording(R_, code, group, event, reader=None):
            readers.append((R_, reader))
            return real(R_, code, group, event, reader)
        with mock.patch.object(whatif, 'candidate_witnesses', recording):
            asking.plan(R, ())
        self.assertTrue(readers)
        for R_, reader in readers:
            self.assertIsNotNone(reader)  # the plan always hands the world's own Reader
            self.assertIs(reader.R, R_)
        self.assertEqual(len({id(reader) for _R, reader in readers}), len({id(R_) for R_, _reader in readers}))

    def test_the_reader_is_never_another_factsets(self):
        R, other = bound_scene(3, 2), absorb_world('none')
        self.assertIs(whatif.reader_of(R, coverage.Reader(other)).R, R)
        own = coverage.Reader(R)
        self.assertIs(whatif.reader_of(R, own), own)


class PairReadTests(SimpleTestCase):
    """A relation witness's pairs: the plan's one Reader, indexed once per candidate."""

    def test_l7_a7_a_relation_witness_never_recomputes_its_acts_pairs(self):
        # L7-A7: int4's whatif._relation_pairs called pairing.pairs_of once per RELATION WITNESS - statements x statements
        # pair relations per candidate (1,800 recomputations at S=10, 46 % of the plan). Built: whatif never computes a
        # pair (every relation witness reads the plan's Reader), and the Reader computes an act's pairs once
        R = bound_scene(6, 5)
        callers: Counter = Counter()
        real = pairing.pairs_of

        held = []  # every FactSet counted is kept alive, so no id is reused by another FactSet during the count

        def recording(R_, act):
            frame = sys._getframe(1)
            held.append(R_)
            callers[(frame.f_globals.get('__name__'), frame.f_code.co_name, id(R_), act)] += 1
            return real(R_, act)
        with mock.patch.object(pairing, 'pairs_of', recording):
            found = asking.plan(R, ())
        self.assertTrue(found.specs)
        self.assertFalse([key for key in callers if key[0] == whatif.__name__], callers.most_common(3))
        by_reader = [count for (module, caller, _R, _act), count in callers.items()
                     if module == coverage.__name__ and caller == 'pairs']
        self.assertTrue(by_reader)
        self.assertEqual(max(by_reader), 1)  # coverage.Reader.pairs: once per (FactSet, act)

    def test_the_index_gives_each_witness_exactly_its_pairs_in_order(self):
        # generality: on the bound scene and on the frozen-free scenes of this module, every relation witness of every
        # candidate carries exactly the pairs a scan of pairing.pairs_of gives, in the same order
        for R in (bound_scene(4, 3), bound_scene(6, 5), absorb_world('planned'), absorb_world('doubted')):
            reader = coverage.Reader(R)
            for code in whatif.candidate_codes(R):
                for candidate in whatif.witnesses(R, code, reader):
                    for witness in candidate.witnesses:
                        if whatif.cause_of(witness.held).family is not whatif.CauseFamily.RELATION:
                            continue
                        scan = tuple(pair for pair in pairing.pairs_of(R, candidate.event)
                                     if pairing.cause(pair) == witness.held.cause
                                     and pair.spans == witness.held.spans)
                        self.assertEqual(witness.pairs, scan)


class OnLesionMemoTests(SimpleTestCase):
    """The Q-ONLESION what-if (pairing.not_on_sets_apart: the pair read with the not-on answers assumed, a FactSet of
    its own) once per (statement, act) per plan."""

    def test_l7_a7_the_onlesion_what_if_once_per_pair(self):
        R = bound_scene(6, 5)
        pairs: Counter = Counter()
        with _counting(pairing, 'not_on_sets_apart', pairs, lambda R_, statement, act: (statement, act)):
            asking.plan(R, ())
        self.assertTrue(pairs)  # not vacuous: the scene reaches the arm's what-if
        self.assertEqual(max(pairs.values()), 1, pairs.most_common(3))  # int4: twice (44404's and 45381's candidates)


class SilentReachTests(SimpleTestCase):
    """A3 (ASK2-1): no per-value what-if for a filter that cannot drop a value."""

    def test_l7_a7_no_what_if_world_for_a_silent_reach(self):
        # int4 built one world per reach value per candidate (210 of the 268 what-ifs at S=15, 70 % of the plan)
        doc = colonoscopy(snare=True)
        doc.sessions[X(1)] = {attribute: facts for attribute, facts in doc.sessions[X(1)].items()
                              if attribute is not A.REACHED}
        for R in (doc.build(), bound_scene(6, 5)):
            built: Counter = Counter()
            with _counting(asking, '_established_at', built,
                           lambda R_, subject, attribute, value: attribute):
                found = asking.plan(R, ())
            with self.subTest(events=len(R.events)):
                self.assertTrue([spec for spec in found.specs if spec.census == 'A3'])
                self.assertEqual(built[A.REACHED], 0)
                self.assertEqual(built[A.REACHED_ANATOMY], 0)

    def test_l7_a7_the_values_are_exactly_those_the_moves_filter_kept_for_every_code(self):
        # the equivalence the ruling's "its mutant A3 was equivalent" needs, pinned over the catalogue: for every A3
        # witness of every code, the filter's own what-if (_Context.moves) over the values ASK2-1 read from the family's
        # regions (COLFULL's full reach) keeps EXACTLY the values _silent_reach_values gives - the enteroscopy class's
        # reach table drops what the filter dropped (the jejunal class's ileal points and small bowel; the deeper
        # classes' jejunum and small bowel), and no other code loses or gains a value
        checked, narrowed = 0, set()
        for name, code, R in silent_reach_scenes():
            ctx = asking._Context(R)
            regions = catalogue.FAMILY_REACH.get(catalogue.family_for_code(code), frozenset())
            broad = (asking._reach_values(code) if asking.Tag.COLFULL in asking.rq.spec(code).tags
                     else tuple(extent for extent in ct.Extent if asking.anatomy.region(extent) in regions))
            given = asking._silent_reach_values(code)
            if set(broad) != set(given):
                narrowed.add(code)
            for candidate in whatif.witnesses(R, code, ctx.reader):
                for witness in candidate.witnesses:
                    held = witness.held
                    if held.attribute not in (A.REACHED, A.REACHED_ANATOMY) or held.subject is None \
                            or held.subject.family is not IdFamily.SESSION \
                            or F.members(R, held.subject, A.REACHED):
                        continue
                    kept = {value for value in broad if ctx.moves(candidate, held, held.subject, A.REACHED, value)}
                    checked += 1
                    with self.subTest(scene=name, fact=held.fact, cause=held.cause):
                        self.assertEqual(kept, set(given))
        self.assertGreater(checked, 100)
        self.assertTrue({str(code) for code in range(44360, 44387)} & narrowed)  # the class tables narrowed something

    def test_boundary_a_family_with_no_reach_table_asks_nothing(self):
        # ASK2-1's own boundary, unchanged: an EUS code (no FAMILY_REACH row) has no A3 value
        self.assertEqual(asking._silent_reach_values('45341'), ())
        self.assertEqual(asking._silent_reach_values('43237'), ())


class PlanEquivalenceTests(SimpleTestCase):
    """The memoized plan equals the plan as int4 computed its what-ifs (``unmemoized_plan``): the cost repairs change
    what is computed how often, never what the plan gives."""

    def test_l7_a7_every_plan_equals_its_unmemoized_reference(self):
        from tests.v2 import test_gate6 as G6
        import json

        scenes = [('bound 3x2', bound_scene(3, 2)), ('bound 6x5', bound_scene(6, 5)),
                  *((f'absorb {name}', absorb_world(name)) for name in ('planned', 'attempted', 'none', 'denied')),
                  *((name, R) for name, _code, R in list(silent_reach_scenes())[::7])]
        for path in sorted(G6.FROZEN.glob('*.json'))[::6]:
            scenes.append((path.name, G6.decode_factset(json.loads(path.read_text(encoding='utf-8'))['factset'])))
        for name, R in scenes:
            with self.subTest(scene=name):
                self.assertEqual(plan_fields(asking.plan(R, ())), plan_fields(unmemoized_plan(R, ())))
        # and a round-2 plan over R_q, the keys of round 1 asked
        R = bound_scene(6, 5)
        first = asking.plan(R, ())
        R_q = F._answered(R, {'questions': [established(spec) for spec in first.specs]})
        keys = tuple(spec.key for spec in first.specs)
        self.assertEqual(plan_fields(asking.plan(R_q, keys)), plan_fields(unmemoized_plan(R_q, keys)))


# --- the measured cost at FINAL-V2 1.8's bound scene ---------------------------------------------------------------------

BOUND = (100, 99)  # FINAL-V2 1.8: 200 events - the examination, 100 listed denials, 99 tattoos - and 64 lesions


def measured(label: str, fn):
    """``fn()`` timed: its wall clock, this process's CPU, and the 1-minute load before and after (a figure counts only
    with the load under 10; printed with it, the record of the run)."""
    before = os.getloadavg()[0]
    wall, cpu = time.perf_counter(), time.process_time()
    out = fn()
    wall, cpu = time.perf_counter() - wall, time.process_time() - cpu
    after = os.getloadavg()[0]
    print(f'\nR3C-ASK {label}: wall {wall:.2f} s, cpu {cpu:.2f} s; 1-min load {before:.2f} -> {after:.2f}', flush=True)
    return out, cpu


class PlanCostTests(SimpleTestCase):
    """DECISIONS D324 (8): QUESTION_CHILD_SECONDS holds FINAL-V2 1.8's bound scene - the round-1 plan (the appraise
    stage's child and the question stage's pre-send computation: one plan) and the post-send child's two plans (round 1
    replayed over the stored row - the same computation as the round-1 plan - then round 2 planned over R_q with every
    round-1 answer established in the release direction), each measured with its 1-minute load. CPU time is the figure
    asserted (a busy host lengthens the wall clock, not the work); the wall clock and the load are printed with it, and
    a figure counts only with the load under 10. PLAN_MARGIN leaves the child's other work beside its plans (the fact
    request rebuilt, the row read, the pool drawn, the requests built, read, located and settled)."""

    def test_l7_a7_the_round_1_plan_and_the_post_send_childs_two_plans_at_the_bound_scene(self):
        R = bound_scene(*BOUND)
        first, one = measured('round-1 plan at the bound scene (= the post-send child\'s plan 1)',
                              lambda: asking.plan(R, ()))
        self.assertTrue(first.specs)
        R_q = F._answered(R, {'questions': [established(spec) for spec in first.specs]})
        self.assertIsNot(R_q, R)
        _second, two = measured('post-send child, plan 2 (round 2 over R_q)',
                                lambda: asking.plan(R_q, tuple(spec.key for spec in first.specs)))
        print(f'R3C-ASK post-send two plans: cpu {one + two:.2f} s (x {PLAN_MARGIN} = {(one + two) * PLAN_MARGIN:.1f} s '
              f'against QUESTION_CHILD_SECONDS {settings.QUESTION_CHILD_SECONDS})', flush=True)
        self.assertLessEqual(one * PLAN_MARGIN, settings.QUESTION_CHILD_SECONDS)
        self.assertLessEqual((one + two) * PLAN_MARGIN, settings.QUESTION_CHILD_SECONDS)


# the child's other work beside its plans (the fact request rebuilt, the row read, the pool drawn, the requests built,
# read, located and settled): a quarter more
PLAN_MARGIN = 1.25


# --- D324 (11) -----------------------------------------------------------------------------------------------------------


class RequirementsVersionTests(SimpleTestCase):
    def test_requirements_version_is_cpt_requirements_3(self):
        # DECISIONS D324 (11): the label moves because its rules pin moved (round r3's route table and the QB clause's
        # reads) - a label kept would keep old records current
        self.assertEqual(REQUIREMENTS_VERSION, 'cpt-requirements@3')
        from tests.v2 import test_requirements as TR

        self.assertNotEqual(TR.REQUIREMENTS_PINS['cpt-requirements@2']['rules'],
                            TR.REQUIREMENTS_PINS['cpt-requirements@3']['rules'])
