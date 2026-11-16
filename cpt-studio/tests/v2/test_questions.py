"""The one-question policy (docs/gemini-migration/FINAL-V2.md 4.8, 4.4; DECISIONS D182, D189; step 4a of its 8.1),
TEXT-ONLY and SYNTHETIC: held facts and FactSets hand-built from engine/types' records (tests/v2/evaluate_fixtures.py,
tests/v2/test_evaluate.py's fixtures). The one revision text here is a synthetic filler of the right length, so
wording.build can slice the spans an item quotes; no document is read and nothing is sent.

Proved here: RANK applied (``order``: rank, a question before an explanation, document order); the binding (``choose``:
each of 4.8's five rules alone deciding); the item ON the binding (``select``: an unbound candidate's witness never
asked, a witness the bound candidate shares asked); each held code carries EXACTLY ONE item (D182) over every fixture of
tests/v2/test_evaluate.py, and every item's sentence builds with wording.build from its message id and Fill, its fact
key, kind and rank equal to wording.MESSAGES'; the message ids and the Fill mirror wording.Message and wording.Slots
value for value; held_facts carry their witness's result (D189); the causes of 4.4; 5.7 measure 4. The refutation of
round 1: Choose.test_rule_3_before_rule_4 (T1) and Worded (F2, F3, F4, F5 and 3.2.6 rule 2's item, D1). D225's engine
half: D225Items. Repair r4a's refutation (refute-r4a-r1): RefutedSentences (F1's unlisted doubt named and quoted, F4's
conflict about the contradicted fact, F7's approach beside an open reach, the same-duct question about the counterpart
whose status is unknown, step 4c's synthetic witness on an unlisted doubt). Repair r4a of round w7r: D232Sentences (an
unlisted doubt never names a session's examination as left in doubt unless its card names that session: row 7's
synthetic doubt and 3.2.6 rule 4's pair, p41's inputs) and D246Items (the synthetic act's witness is SYNTHETIC_ACT,
mirrored; a base-within hold is BASE_WITHIN; the bundling and enteroscopy class items get every slot wording asks).
Its refutation refute-r4a-r1 (repair r4a-2): R4a2Sentences - the enteroscopy class items name the reach the class rule
read and quote its words (P3), the approach's words where it cites none (P4), the documented stoma (P11); with no reach
supported the item is the reach's own question (the step's NOTES, QR); read time words a synthetic hold as assess
does (P10); a card naming a session the FactSet does not hold names none (P9).
Repair r4a of round w8r (DECISIONS D253, D254, D257, D258): D258UnlistedScope - a statement that names no procedure
session (a doubt or a denial with no card, or a card naming a session the FactSet does not hold) held against a
session's examination is UNLISTED_SCOPE (mirrored), the held session's examination asked, never "leaves ... in doubt":
QP2's p41 through assess with the members' answers, QD's no-card denial, r4c Q1's ileal input (rule 4's pair and step
4c's synthetic witness); D253Items - QX (ii)'s route part asked by ENTEROSCOPY_THROUGH (mirrored), never PROCEDURE, and
A3's pouchoscopy reaching the for-else's EXTENT fallback (mutant MX5NOEXTENT); D254Fill - rule 2's Kind.OTHER in
every act slot, rule 3's A1 shapes worded by the renderer with no route named; D257BaseWithin - the whole's family and
its "only possibly done" slot. D232Sentences, R4a2Sentences' P9 and D225Items' D216 pin are restated where D258 and
D254 changed what they pinned (the step's NOTES, deviation DV1). Its refutation refute-r4a-r1 (repair r4a-2 of round
w8r): D253Items - the oral classes' two-route doubt is ENTEROSCOPY_ROUTE, never ENTEROSCOPY_THROUGH (P2; the first
QX (ii) test's oral case moved to its own test); RefutedW8rItems - a digital examination's sentence and device are
never named as the session's examination (P3: UNLISTED_SCOPE and the carded rule-4 pair), D254 rule 2 reaches
SAME_DUCT's two act slots (P4), and rule 4's pair is found by its spans and its cause (P8).
"""
from __future__ import annotations

import dataclasses
import enum
import itertools
from types import SimpleNamespace
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import wording
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import classes as CL
from studio.interpretation.engine import combination as CB
from studio.interpretation.engine import coverage as CV
from studio.interpretation.engine import evaluate as EV
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import Fact, HeldFact, Id, IdFamily, ItemKind, Span
from tests.v2 import test_assess as TA
from tests.v2 import test_evaluate as TE
from tests.v2.evaluate_fixtures import (EARLIER, SILENT, Doc, E, L, Status, X, colonoscopy, contra, doubted, fact, neg,
                                        sup, unit, unres, without_events)
from tests.v2.test_types import measure_4

APP = Path(__file__).resolve().parents[2]
MODULE = APP / 'studio' / 'interpretation' / 'engine' / 'questions.py'
QUESTION, EXPLANATION = ItemKind.QUESTION, ItemKind.EXPLANATION
# A synthetic revision text long enough for every span the fixtures quote (wording.build slices it after the decision).
FILLER = ('Synthetic filler words for the item sentences. ' * 60)[:2400]


def held(fact='performed_status', rank=4, kind=QUESTION, subject=None, spans=(), cause='reading_unknown',
         attribute=None, result=None) -> HeldFact:
    return HeldFact(fact=fact, attribute=attribute, subject=subject, result=result, kind=kind, cause=cause,
                    reason=None, spans=tuple(spans), rank=rank)


def slots(fill: Q.Fill) -> wording.Slots:
    """The wording.Slots a caller builds from an item's Fill (questions' module docstring)."""
    values = {field.name: getattr(fill, field.name) for field in dataclasses.fields(Q.Fill)}
    values['bundling'] = wording.Bundling(fill.bundling.value) if fill.bundling is not None else None
    return wording.Slots(**values)


class Mirrors(SimpleTestCase):
    """The engine cannot import wording (studio.gi; no mypy --strict module), so its message ids, Bundling and Fill
    restate step 3c's wording.Message, Bundling and Slots: pinned equal here, member for member and field for field."""

    def test_message_ids_equal_wordings(self):
        self.assertEqual([(member.name, member.value) for member in Q.MessageId],
                         [(member.name, member.value) for member in wording.Message])

    def test_bundling_equals_wordings(self):
        self.assertEqual([(member.name, member.value) for member in Q.Bundling],
                         [(member.name, member.value) for member in wording.Bundling])

    def test_fill_equals_slots_field_for_field(self):
        ours = [(field.name, field.default) for field in dataclasses.fields(Q.Fill)]
        theirs = [(field.name, field.default) for field in dataclasses.fields(wording.Slots)]
        self.assertEqual(ours, theirs)
        def annotations(cls):
            out = {}
            for field in dataclasses.fields(cls):
                text = str(field.type)
                for old in ('engine_catalogue.', 'catalogue.', 'engine_requirements.', 'rq.'):  # the modules' aliases
                    text = text.replace(old, '')
                out[field.name] = text
            return out

        self.assertEqual(annotations(Q.Fill), annotations(wording.Slots))


class Causes(SimpleTestCase):
    """4.4's causes [R:MO-2]: from the fact's result and first reason; a coding rule's for an established failure."""

    def test_cause_of(self):
        cases = {
            'reading_unknown': [doubted(Status.PERFORMED), SILENT],
            'reading_contradicted': [contra(Status.PERFORMED, Status.PLANNED)],
            'appraisal:unclear': [unres(Status.PERFORMED, ct.Reason.APPRAISAL_UNCLEAR)],
            'appraisal:contradicts': [unres(Status.PERFORMED, ct.Reason.APPRAISAL_CONTRADICTS)],
            'appraisal:qualified': [unres(Status.PERFORMED, ct.Reason.APPRAISAL_QUALIFIED_HEDGED),
                                    unres(Status.PERFORMED, ct.Reason.APPRAISAL_QUALIFIED)],
            'appraisal:control_incoherent': [unres(Status.PERFORMED, ct.Reason.CONTROL_INCOHERENT)],
            'appraisal:detached': [unres(Status.PERFORMED, ct.Reason.APPRAISAL_DETACHED)],
            'appraisal:missing': [unres(Status.PERFORMED, ct.Reason.APPRAISAL_MISSING)],
            'unestablished:literal_mismatch': [unres(Status.PERFORMED, ct.Reason.LITERAL_MISMATCH)],
            'unestablished:unappraised': [unres(Status.PERFORMED, ct.Reason.UNAPPRAISED)],
        }
        for cause, found in cases.items():
            for fact in found:
                with self.subTest(cause=cause, fact=fact.reasons):
                    self.assertEqual(Q.cause_of(fact), cause)
        self.assertEqual(Q.coding_rule(Q.Rule.ROUTE_B), 'coding_rule:route_b')

    def test_no_cause_names_a_vendor(self):
        names = ('gemini', 'google', 'corti', 'astra', 'fable', 'anthropic', 'claude', 'openai')
        causes = [Q.coding_rule(rule) for rule in Q.Rule] + sorted(Q.RELATION_CAUSES) + [
            Q.READING_UNKNOWN, Q.READING_CONTRADICTED, Q.UNESTABLISHED, Q.UNLISTED, Q.CONTEXT_MISSING, Q.DATE_UNKNOWN]
        for cause in causes:
            with self.subTest(cause=cause):
                self.assertFalse(any(name in cause.lower() for name in names))

    def test_held_facts_carry_their_witness_result(self):
        """D189: a fact's witness carries its settled result; a relation's (no single fact) None."""
        evaluation = TE.decide('45385', colonoscopy(status=doubted(Status.PERFORMED)).build())
        self.assertEqual(evaluation.held_facts[0].result, ct.Result.UNKNOWN)
        evaluation = TE.decide('45385', colonoscopy(date=unres(TE.ON)).build())
        self.assertEqual(evaluation.held_facts[0].result, ct.Result.UNRESOLVED)
        self.assertEqual(evaluation.held_facts[0].reason, ct.Reason.APPRAISAL_UNCLEAR)
        doc = colonoscopy()
        doc.event(3, kind=sup(ct.Kind.REMOVAL), status=TE.neg(Status.PERFORMED), session=sup(X(1)), date=sup(TE.ON),
                  breadth=sup(ct.Breadth.ALL_OF_KIND))
        self.assertIsNone(TE.decide('45385', doc.build()).held_facts[0].result)


class Rank(SimpleTestCase):
    """RANK applied (4.8): rank first, a question before an explanation at an equal rank, then document order."""

    def test_order(self):
        R = colonoscopy().build()
        facts = [held('extent', 14, spans=(Span(5, 9),)), held('performed_status', 4, EXPLANATION, spans=(Span(1, 2),)),
                 held('performed_status', 4, QUESTION, spans=(Span(50, 60),)), held('conflict:snare', 1),
                 held('service_date', None), held('event_time', 6, spans=(Span(30, 40),)),
                 held('event_time', 6, spans=(Span(10, 20),))]
        found = Q.ranked(facts, R)
        self.assertEqual([(item.fact, item.rank, item.kind) for item in found],
                         [('conflict:snare', 1, QUESTION), ('performed_status', 4, QUESTION),
                          ('performed_status', 4, EXPLANATION), ('event_time', 6, QUESTION),
                          ('event_time', 6, QUESTION), ('extent', 14, QUESTION), ('service_date', None, QUESTION)])
        self.assertEqual(found[3].spans, (Span(10, 20),))  # document order at an equal rank and kind

    def test_rank_for_every_pair_of_ranks(self):
        R = colonoscopy().build()
        for one in rq.Rank:
            for other in rq.Rank:
                if one.value >= other.value:
                    continue
                with self.subTest(one=one.name, other=other.name):
                    first = held(rq.fact_key(rq.RANK[one][0], ct.Kind.SNARE if one is rq.Rank.CONFLICT else None),
                                 one.value, EXPLANATION)
                    second = held(rq.fact_key(rq.RANK[other][0], None), other.value, QUESTION)
                    self.assertEqual(Q.ranked([second, first], R)[0], first)


class Choose(SimpleTestCase):
    """4.8's binding, each rule deciding alone (the others tied)."""

    def setUp(self):
        self.R = colonoscopy().build()

    def candidate(self, event, rank=6, unmet=1, kind=QUESTION):
        return Q.Candidate(event, (held('event_time', rank, kind, subject=event),), unmet)

    def test_rule_1_kept_span_overlap(self):
        doc = colonoscopy()
        doc.act(3, ct.Kind.SNARE)
        R = doc.build()
        candidates = [self.candidate(E(2), rank=1), self.candidate(E(3), rank=9)]
        self.assertEqual(Q.choose((unit(3),), candidates, R), E(3))
        self.assertEqual(Q.choose((), candidates, R), E(2))

    def test_rule_2_the_top_items_rank(self):
        candidates = [self.candidate(E(2), rank=7), self.candidate(E(3), rank=2)]
        self.assertEqual(Q.choose((), candidates, self.R), E(3))

    def test_rule_3_the_fewest_non_t_requirements(self):
        candidates = [self.candidate(E(2), unmet=3), self.candidate(E(3), unmet=1)]
        self.assertEqual(Q.choose((), candidates, self.R), E(3))

    def test_rule_4_a_question_before_an_explanation(self):
        candidates = [self.candidate(E(2), kind=EXPLANATION), self.candidate(E(3), kind=QUESTION)]
        self.assertEqual(Q.choose((), candidates, self.R), E(3))

    def test_rule_3_before_rule_4(self):
        """The refutation's T1: (3) the fewest non-T requirements decide before (4) a question before an explanation -
        E3, an explanation with one row not T, is bound over E2, a question with three (and first in document
        order)."""
        candidates = [self.candidate(E(2), unmet=3, kind=QUESTION), self.candidate(E(3), unmet=1, kind=EXPLANATION)]
        self.assertEqual(Q.choose((), candidates, self.R), E(3))

    def test_rule_5_document_order(self):
        doc = colonoscopy()
        doc.act(3, ct.Kind.SNARE, anchor=(Span(50, 60),))
        R = doc.build()
        candidates = [self.candidate(E(2)), self.candidate(E(3))]
        self.assertEqual(Q.choose((), candidates, R), E(3))  # E3's anchor (50) precedes E2's (200)

    def test_no_candidate_is_refused(self):
        with self.assertRaises(ValueError):
            Q.choose((), [], self.R)


class Select(SimpleTestCase):
    """The item ON the binding: an unbound candidate's witness is never the item; a witness it shares with the bound
    candidate is."""

    def test_on_binding(self):
        R = colonoscopy().build()
        shared = held('event_performer', 7, subject=E(1))
        bound = Q.Candidate(E(2), (held('event_time', 6, subject=E(2)), shared), 2)
        other = Q.Candidate(E(3), (held('conflict:snare', 1, subject=E(3)), shared), 2)
        group = Q.Group((ct.Kind.SNARE,), (bound, other), E(2))
        facts = (*bound.witnesses, *other.witnesses)
        self.assertEqual(Q.on_binding(facts, [group]), (bound.witnesses[0], shared, shared))
        self.assertEqual(Q.select(facts, [group], R).fact, 'event_time')
        code_level = held('extent', 14)
        self.assertEqual(Q.select((*facts, code_level), [group], R).fact, 'event_time')
        self.assertIsNone(Q.select((), [group], R))


def every_held_code():
    """Every fixture of tests/v2/test_evaluate.py that holds its code (all_fixtures), with its evaluation."""
    for code, R, kept in TE.all_fixtures():
        evaluation = EV.decide(code, kept, R)
        if evaluation.held_facts:
            yield code, R, kept, evaluation


class OneItem(SimpleTestCase):
    """D182: each held code carries EXACTLY ONE item - over every fixture of tests/v2/test_evaluate.py - and every item
    is worded: wording.build succeeds from its message id and Fill, with the held fact's fact key, kind and rank."""

    def test_exactly_one_item_and_its_sentence_builds(self):
        count = 0
        for code, R, kept, evaluation in every_held_code():
            with self.subTest(code=code, held=[entry.fact for entry in evaluation.held_facts]):
                found = EV.item(code, kept, R, evaluation)
                self.assertIsNotNone(found)
                self.assertIn(found.held, evaluation.held_facts)
                spec = wording.MESSAGES[wording.Message(found.message.value)]
                key, _ = Q.fact_of(found.held)
                if found.message is Q.MessageId.DIGITAL_SCOPE:  # D280.3 (step f3w): the held fact's own key, kind, rank
                    self.assertEqual((found.fill.held, wording.fact_key(wording.Message.DIGITAL_SCOPE,
                                                                        slots(found.fill)), found.kind),
                                     (rq.Rank(found.held.rank), found.held.fact, found.held.kind))
                else:
                    self.assertEqual((spec.fact, spec.kind, spec.rank), (key.value, found.kind, found.held.rank))
                worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
                self.assertEqual(worded.fact, found.held.fact)
                self.assertTrue(worded.question and worded.reason)
                count += 1
        self.assertGreaterEqual(count, 35)

    def test_no_item_for_a_ready_or_excluded_code(self):
        R = colonoscopy().build()
        self.assertIsNone(EV.item('45385', (), R, EV.decide('45385', (), R)))
        R = TE.shared_sentence()
        evaluation = EV.decide('45386', (Span(327, 372),), R)
        self.assertIsNotNone(evaluation.exclusion)
        self.assertIsNone(EV.item('45386', (Span(327, 372),), R, evaluation))

    def test_held_facts_the_caller_appends_are_ranked_with_the_codes_own(self):
        """4.4: assess appends the R6 facts, the class and code checks and the combination; the one item is still the
        highest-ranked on the binding."""
        R = colonoscopy(status=doubted(Status.PERFORMED)).build()
        evaluation = EV.decide('45385', (), R)
        extent = held('extent', 14, subject=X(1), cause='reading_unknown')
        self.assertEqual(EV.item('45385', (), R, evaluation, extra=(extent,)).held.rank, 2)
        R = colonoscopy().build()
        ready = EV.decide('45385', (), R)
        found = EV.item('45385', (), R, ready, extra=(extent,))
        self.assertEqual((found.held, found.message), (extent, Q.MessageId.EXTENT))

    def test_question_or_explanation(self):
        """4.8: a question when the requirement is unresolved, an explanation when an established fact fails it."""
        cases = {QUESTION: colonoscopy(entry=unres(TE.DC)).build(), EXPLANATION: colonoscopy(entry=sup(ct.Owner.NURSING))
                 .build()}
        for kind, R in cases.items():
            with self.subTest(kind=kind):
                found = EV.item('45385', (), R, EV.decide('45385', (), R))
                self.assertEqual((found.held.fact, found.kind), ('event_entry', kind))
                self.assertEqual(found.message, Q.MessageId.ENTRY if kind is QUESTION else Q.MessageId.ANOTHER_ENTRY)


class Worded(SimpleTestCase):
    """The refutation's round-1 wording findings: each held code's one item names what its rule read, and its sentence
    builds (D182: a held code with no sentence has no item)."""

    def item(self, code, R, kept=()):
        found = EV.item(code, tuple(kept), R, EV.decide(code, tuple(kept), R))
        self.assertIsNotNone(found)
        worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
        return found, worded

    def test_an_unlisted_statement_in_the_acts_own_sentence_is_quoted(self):
        """F2: pass 2's unlisted doubt found in the snare's own unit pairs with it (3.2.6 rule 4); the pair asks
        performed_status at RANK row 2 (DECISIONS D228 DQ3, pairing.item: the act's status in doubt) and the question
        quotes that unit, which is the act's anchor too - never an empty statements slot."""
        doc = colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.SNARE, X(1), unit(2)))
        found, worded = self.item('45385', doc.build())
        self.assertEqual((found.message, found.fill.statements, found.fill.words),
                         (Q.MessageId.DOUBT, ((unit(2),),), (unit(2),)))
        self.assertEqual(worded.fact, 'performed_status')

    def test_another_site_names_the_place_the_rule_read_on_the_lesion(self):
        """F3: "A 15 mm stricture (L1) was seen in the distal esophagus. Balloon dilation of the stricture to 15 mm was
        performed." - SITE reads the lesion's place (D29), so another-site's explanation names it."""
        doc = TE.dilation(lesion=sup(TE.L(1)))
        doc.lesion(1, lesion_places=[sup(ct.Landmark.DISTAL_ESOPHAGUS)])
        found, worded = self.item('43245', doc.build())
        self.assertEqual((found.message, found.fill.place), (Q.MessageId.ANOTHER_SITE, ct.Landmark.DISTAL_ESOPHAGUS))
        self.assertEqual(worded.kind, EXPLANATION)

    def test_the_stoma_class_misfit_by_approach_names_the_approach(self):
        """F4, and D225's P5: 44406 with its approach established oral is the class's explanation - RANK row 8, naming
        the route (examination_approach) - never the extent question."""
        doc = TE.Doc()
        doc.session(1, ct.SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=[sup(ct.Extent.STOMA)],
                    approach=sup(ct.Approach.ORAL))
        doc.entry(1, type=sup(ct.AnatomyType.STOMA))
        doc.exam(1)
        found, worded = self.item('44406', doc.build())
        self.assertEqual((found.message, found.fill.approach, found.held.rank, worded.kind),
                         (Q.MessageId.EXAMINATION_APPROACH, ct.Approach.ORAL, 8, EXPLANATION))
        self.assertIn('was passed through the mouth', worded.question)
        self.assertNotIn('extent', worded.question + worded.reason)

    def test_the_station_class_names_only_an_upper_station(self):
        """F5: the jejunum negated is never named. 43237 with the three upper stations examined: the limited class's
        explanation, no station named as not examined; 43242 with the stomach negated beside the jejunum: the
        stomach."""
        every = [sup(ct.Station.ESOPHAGUS), sup(ct.Station.STOMACH), sup(ct.Station.DUODENUM)]
        found, worded = self.item('43237', TE.eus_fna([TE.neg(ct.Station.JEJUNUM), *every]))
        self.assertEqual((found.message, found.fill.denied), (Q.MessageId.STATION_CLASS, ()))
        self.assertNotIn('jejunum', worded.question + worded.reason)
        R = TE.eus_fna([TE.neg(ct.Station.JEJUNUM), sup(ct.Station.ESOPHAGUS), TE.neg(ct.Station.STOMACH),
                        sup(ct.Station.DUODENUM)])
        found, worded = self.item('43242', R)
        self.assertEqual((found.message, found.fill.denied), (Q.MessageId.STATION_CLASS, (ct.Station.STOMACH,)))
        self.assertNotIn('jejunum', worded.question + worded.reason)

    def test_rule_2_names_the_unlisted_entry_and_quotes_its_own_unit(self):
        """D1 (3.2.6 rule 2) and D225's P11: rule 2's rank-2 item names the unlisted entry's own nature and kind and
        quotes its own unit (unlisted_evidence) - never the code's act said to be in doubt. 43274 citing the exchange
        sentence: "documents a stent removal"; Worded's second case - a cited "No polyps were removed." with an unlisted
        biopsy doubt in its unit, 45385 - "leaves a forceps biopsy in doubt", never the snare removal."""
        found, worded = self.item('43274', TE.UnlistedOnEvidence.exchange(), (unit(2),))
        self.assertEqual((found.message, found.fill.unlisted_what, found.fill.unlisted_kind, found.fill.statements),
                         (Q.MessageId.UNLISTED_EVIDENCE, ct.UnlistedWhat.ACT, ct.Kind.STENT_REMOVAL, ((unit(2),),)))
        self.assertIn('The evidence passage of 43274', worded.question)
        self.assertIn('documents a stent removal', worded.question)
        self.assertNotIn('stent placement', worded.question + worded.reason)
        doc = colonoscopy(snare=False)
        TE.denial_event(doc, kind=ct.Kind.REMOVAL)
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.BIOPSY, X(1), unit(3)))
        found, worded = self.item('45385', doc.build(), (Span(300, 325),))
        self.assertEqual((found.message, found.fill.unlisted_what, found.fill.unlisted_kind, found.fill.statements),
                         (Q.MessageId.UNLISTED_EVIDENCE, ct.UnlistedWhat.DOUBT, ct.Kind.BIOPSY, ((unit(3),),)))
        self.assertIn('leaves a forceps biopsy in doubt', worded.question)
        self.assertNotIn('snare', worded.question + worded.reason)
        self.assertEqual(worded.question.count(_quote(unit(3))), 1)


def _quote(span):
    """The filler's words a span quotes, as wording quotes them (the synthetic FILLER only)."""
    return wording.quote(wording.span_text(FILLER, (span,)), 120)


class D225Items(SimpleTestCase):
    """D225's engine half (refute-4a-r2 P5, P6, P7, P10, P11; repair r3c's ids): every held code's one item names the
    act and the fact that is actually unknown, its sentence true for its state. The inputs are the refuter's probes
    (p10, p13, p15, p17) and their variants."""

    def item(self, code, R, kept=()):
        found = EV.item(code, tuple(kept), R, EV.decide(code, tuple(kept), R))
        self.assertIsNotNone(found)
        worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
        self.assertEqual(worded.fact, found.held.fact)
        return found, worded

    def test_p5_the_stoma_class_asks_its_approach_never_the_extent(self):
        """p13: 44406, the reach supported at the sigmoid colon. (a) The approach silent or unresolved with a stoma
        entry: the approach question, through the documented stoma. (b) The approach supported through_stoma with no
        stoma entry: the stoma question. Never R6's "could not find how far the examination reached"."""
        def eus(approach, stoma):
            doc = TE.Doc()
            doc.session(1, ct.SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=[sup(ct.Extent.SIGMOID_COLON)],
                        approach=approach)
            if stoma:
                doc.entry(1, type=sup(ct.AnatomyType.STOMA))
            doc.exam(1)
            return doc.build()

        for name, approach in {'silent': None, 'unresolved': unres(ct.Approach.THROUGH_STOMA)}.items():
            with self.subTest(name):
                found, worded = self.item('44406', eus(approach, True))
                self.assertEqual((found.message, found.held.rank, found.fill.approach, found.fill.approaches,
                                  found.fill.reached),
                                 (Q.MessageId.EXAMINATION_ROUTE, 8, None, (ct.Approach.THROUGH_STOMA,),
                                  ct.Extent.SIGMOID_COLON))
                self.assertIn('reached the sigmoid colon; CPT Studio could not confirm from the document whether it '
                              'was passed through the documented stoma', worded.question)
                self.assertNotIn('how far', worded.question + worded.reason)
        found, worded = self.item('44406', eus(sup(ct.Approach.THROUGH_STOMA), False))
        self.assertEqual((found.message, found.fill.approach, found.fill.approaches),
                         (Q.MessageId.EXAMINATION_ROUTE, ct.Approach.THROUGH_STOMA, ()))
        self.assertIn('could not confirm from the document that the patient has a stoma', worded.question)
        self.assertNotIn('how far', worded.question + worded.reason)

    def test_p6_the_duct_question_names_the_act_whose_duct_is_unknown(self):
        """p10 and its mirror: the placement's duct supported and the removal's silent - the removal named, the
        placement its counterpart; the placement's silent and the removal's supported - the placement named. The held
        fact rests on the unknown duct (its result unknown), never on the supported one; an unlisted removal (no duct,
        no id) is named by its own unit."""
        cases = {'the removal filed, its duct silent': (TE.stent_placement({}), ct.Kind.STENT_REMOVAL, unit(5),
                                                        ct.Kind.STENT, unit(2), ct.Result.UNKNOWN),
                 'the removal unlisted': (TE.stent_placement(ct.Kind.STENT_REMOVAL), ct.Kind.STENT_REMOVAL, unit(5),
                                          ct.Kind.STENT, unit(2), None),
                 'the placement\'s duct silent': (TE.stent_placement(dict(duct=sup(ct.Duct.BILIARY)), duct=None),
                                                  ct.Kind.STENT, unit(2), ct.Kind.STENT_REMOVAL, unit(5),
                                                  ct.Result.UNKNOWN)}
        for name, (doc, act, words, whole, whole_words, result) in cases.items():
            with self.subTest(name):
                found, worded = self.item('43274', doc.build(), (unit(2),))
                self.assertEqual((found.message, found.fill.act, found.fill.words, found.fill.whole,
                                  found.fill.whole_words, found.held.result),
                                 (Q.MessageId.SAME_DUCT, act, (words,), whole, (whole_words,), result))
                label = 'stent removal' if act is ct.Kind.STENT_REMOVAL else 'stent placement'
                self.assertIn(f'could not confirm from the document in which duct the {label} was done', worded.reason)
                self.assertIn('done in the same duct?', worded.question)

    def test_p7_a_contradicted_attribute_is_named_never_performed_and_not_performed(self):
        """p15: a contradicted date relation (HO-8's first case, free binding; and within the snare's own sentence) and a
        contradicted device are each a conflict about that attribute, the one sentence quoted once - never "both as
        performed and as not performed". A status contradicted within one sentence: whether it was done; across two
        sentences: conflict_fact quoting both. A session's fact names its examination."""
        cases = {'HO-8 case 1': ('45385', TE.two_snares(), 'when the snare removal at the rectum was done'),
                 'a date in one sentence': ('45385', colonoscopy(date=contra(TE.ON, TE.EARLIER, spans=(unit(2),)))
                                            .build(), 'when the snare removal (cold snare) at the sigmoid colon was '
                                                      'done'),
                 'a device in one sentence': ('43249', TE.dilation(sup(ct.Landmark.DISTAL_ESOPHAGUS),
                                                                   device=contra(ct.Device.BALLOON, ct.Device.BOUGIE,
                                                                                 spans=(unit(2),))).build(),
                                              'which device was used for the dilation at the distal esophagus'),
                 'a status in one sentence': ('45385', colonoscopy(status=contra(Status.PERFORMED, Status.PLANNED,
                                                                                spans=(unit(2),))).build(),
                                              'whether the snare removal (cold snare) at the sigmoid colon was done'),
                 'a session\'s stations': ('43242', TE.eus_fna([sup(ct.Station.ESOPHAGUS),
                                                                contra(ct.Station.STOMACH, ct.Station.DUODENUM,
                                                                       spans=(unit(1),))]),
                                           'which parts the endoscopic ultrasound examined')}
        for name, (code, R, about) in cases.items():
            with self.subTest(name):
                found, worded = self.item(code, R)
                self.assertEqual(found.message, Q.MessageId.CONFLICT_ATTRIBUTE)
                self.assertIn(f'The document is not consistent about {about} (', worded.question)
                self.assertNotIn('as not performed', worded.question + worded.reason)
                self.assertNotIn('another states it was not done', worded.reason)
        found, worded = self.item('43242', cases['a session\'s stations'][1])
        self.assertEqual((found.held.fact, found.fill.act), ('conflict:examination', ct.Kind.EXAMINATION))
        found, worded = self.item('45385', colonoscopy(status=contra(Status.PERFORMED, Status.PLANNED,
                                                                      spans=(unit(2), unit(7)))).build())
        self.assertEqual((found.message, found.fill.statements), (Q.MessageId.CONFLICT_FACT, ((unit(7),), (unit(2),))))
        doc = colonoscopy(date=contra(TE.ON, TE.EARLIER, spans=(unit(2), unit(7))))
        found, worded = self.item('45385', doc.build())
        self.assertEqual(found.message, Q.MessageId.CONFLICT_ATTRIBUTE)
        self.assertIn('Statements in the document disagree about when the snare removal', worded.question)

    def test_p10_another_structure_names_the_place_the_rule_read(self):
        """p17: 43240, structure supported pancreatic_fluid_collection, places [pancreas, bile duct] in either order:
        the explanation names the bile duct (the place that sets the drainage apart), never the pancreas."""
        for places in ([ct.Landmark.PANCREAS, ct.Landmark.BILE_DUCT], [ct.Landmark.BILE_DUCT, ct.Landmark.PANCREAS]):
            with self.subTest(places=places):
                doc = TE.Doc()
                doc.session(1, ct.SessionKind.EUS, tract=sup(ct.Tract.UPPER), reached=[sup(ct.Extent.DUODENUM)])
                doc.exam(1)
                doc.act(2, ct.Kind.DRAINAGE, structure=sup(ct.Structure.PANCREATIC_FLUID_COLLECTION),
                        places=[sup(place) for place in places], route=sup(ct.Route.EUS_TRANSMURAL))
                found, worded = self.item('43240', doc.build())
                self.assertEqual((found.message, found.fill.place),
                                 (Q.MessageId.STRUCTURE_PLACE, ct.Landmark.BILE_DUCT))
                self.assertIn('places this drainage at the bile duct', worded.reason)
                self.assertNotIn('at the pancreas', worded.reason)
        # the structure established otherwise stays another_structure (repair r3c's question Q2)
        doc = TE.Doc()
        doc.session(1, ct.SessionKind.EUS, tract=sup(ct.Tract.UPPER))
        doc.exam(1)
        doc.act(2, ct.Kind.DRAINAGE, structure=sup(ct.Structure.GALLBLADDER), places=[sup(ct.Landmark.GALLBLADDER)])
        self.assertEqual(self.item('43240', doc.build())[0].message, Q.MessageId.ANOTHER_STRUCTURE)

    def test_d216_a_synthetic_act_is_named_by_its_own_kind_and_unit(self):
        """D216 with D246 (r4a R4 (a)): row 7's synthetic examination act - a kept unlisted ACT - is named by its own
        kind (an examination, or with no kind "another act": D254 rule 2, repair r3c of round w8r's label, restated
        from "an act") in SYNTHETIC_ACT's words, quoting its own unit, never "left in doubt"; 43276's synthetic removal
        by its own kind. Never the code's own act."""
        doc = TE.act_only_colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.ACT, ct.Kind.EXAMINATION, X(1), unit(5)))
        found, worded = self.item('45385', doc.build())
        self.assertEqual((found.message, found.fill.act, found.fill.words),
                         (Q.MessageId.SYNTHETIC_ACT, ct.Kind.EXAMINATION, (unit(5),)))
        self.assertTrue(worded.question.startswith(f'The document documents an examination ({_quote(unit(5))}), '))
        self.assertNotIn('in doubt', worded.question + worded.reason)
        doc = TE.act_only_colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.ACT, None, X(1), unit(5)))
        found, worded = self.item('45385', doc.build())
        self.assertEqual(found.fill.act, ct.Kind.OTHER)
        self.assertTrue(worded.question.startswith('The document documents another act ('))
        self.assertNotIn('snare', worded.question + worded.reason)
        found, worded = self.item('43276', TE.stent_placement(ct.Kind.STENT_REMOVAL).build())
        self.assertTrue(worded.question.startswith('The document documents a stent removal ('))

    def test_d216_a_sentence_telling_two_unlisted_acts_names_the_one_the_rule_read(self):
        """A sentence telling two acts that pass 2 keeps unlisted in one unit ("advanced ... and removed", A6), the act
        no rule read listed first: row 7's witness names the examination it read, never the snare beside it; 43276's
        synthetic part names the removal it paired, never the placement told in the same unit."""
        doc = TE.act_only_colonoscopy()
        doc.unlisted += [TE.unlisted(ct.UnlistedWhat.ACT, ct.Kind.SNARE, X(1), unit(5)),
                         TE.unlisted(ct.UnlistedWhat.ACT, ct.Kind.EXAMINATION, X(1), unit(5))]
        found, worded = self.item('45385', doc.build())
        self.assertEqual((found.message, found.fill.act), (Q.MessageId.SYNTHETIC_ACT, ct.Kind.EXAMINATION))
        self.assertTrue(worded.question.startswith('The document documents an examination ('))
        doc = TE.stent_placement(None)
        doc.unlisted += [TE.unlisted(ct.UnlistedWhat.ACT, ct.Kind.STENT, X(1), unit(5)),
                         TE.unlisted(ct.UnlistedWhat.ACT, ct.Kind.STENT_REMOVAL, X(1), unit(5))]
        found, worded = self.item('43276', doc.build())
        self.assertEqual((found.message, found.fill.act), (Q.MessageId.SYNTHETIC_ACT, ct.Kind.STENT_REMOVAL))
        self.assertTrue(worded.question.startswith('The document documents a stent removal ('))

    def test_a_synthetic_examination_step_4c_raises_is_named_by_its_own_kind(self):
        """repair r4c's R3: classes.enteroscopy_hold's synthetic examination witness (performed_status at rank 2, cause
        unlisted, about no single fact, its subject the SESSION, its spans the entry's units), appended by assess as
        ``extra``, is named by the kept unlisted act's own kind (SYNTHETIC_ACT: D246) - never the code's supporting act
        in that session, nor the session's service, which the act's card (another session) does not name (D232)."""
        doc = colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.ACT, ct.Kind.EXAMINATION, X(2), unit(5)))
        doc.session(2, ct.SessionKind.EGD)
        R = doc.build()
        evaluation = EV.decide('45385', (), R)
        extra = HeldFact(fact='performed_status', attribute=None, subject=X(1), result=None, kind=QUESTION,
                         cause='unlisted', reason=None, spans=(unit(5),), rank=2)
        found = EV.item('45385', (), R, evaluation, extra=(extra,))
        worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
        self.assertEqual((found.held, found.message, found.fill.act, found.fill.words),
                         (extra, Q.MessageId.SYNTHETIC_ACT, ct.Kind.EXAMINATION, (unit(5),)))
        self.assertTrue(worded.question.startswith('The document documents an examination ('))
        self.assertNotIn('colonoscopy', worded.question + worded.reason)


class RefutedSentences(SimpleTestCase):
    """refute-r4a-r1, worded (D225: every sentence true for its state, naming the act and the fact actually unknown):
    F1's unlisted doubt is named by its own kind and quoted; F4's contradicted purpose, reach and target lesion are each
    the conflict's attribute; F7's approach is asked beside an open reach; the same-duct question names the counterpart
    whose status is unknown. Each sentence is built by wording.build, its fact key equal to the held fact's."""

    def item(self, code, R, kept=()):
        found = EV.item(code, tuple(kept), R, EV.decide(code, tuple(kept), R))
        self.assertIsNotNone(found)
        worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
        self.assertEqual(worded.fact, found.held.fact)
        return found, worded

    def test_f1_an_unlisted_doubt_is_named_by_its_kind_and_quoted(self):
        """p20: 43274 asks whether the doubted removal and the placement were done in the same duct, the removal's own
        sentence quoted; 43276's item is the doubt itself - "leaves the stent removal in doubt", true of a doubt."""
        doc = TE.stent_placement(None)
        doc.unlisted.append(TE.stent_doubt())
        found, worded = self.item('43274', doc.build(), (unit(2),))
        self.assertEqual(found.message, Q.MessageId.SAME_DUCT)
        self.assertIn(f'Were the stent removal ({_quote(unit(5))}) and the stent placement ({_quote(unit(2))}) done '
                      'in the same duct?', worded.question)
        self.assertIn('could not confirm from the document in which duct the stent removal was done', worded.reason)
        found, worded = self.item('43276', doc.build())
        self.assertEqual((found.message, found.held.cause), (Q.MessageId.DOUBT, Q.UNLISTED))
        self.assertTrue(worded.question.startswith(f'Confirm whether the stent removal ({_quote(unit(5))}) was done'))
        self.assertTrue(worded.reason.startswith('The document leaves the stent removal in doubt: '))

    def test_f4_the_conflict_names_the_contradicted_fact(self):
        """p22, p26: the purpose (never the cause), the reach (never the stations), the target lesion and the lesion's
        place (never where the act was done) - each the attribute the conflict is about."""
        hemostasis = ct.Purpose.HEMOSTASIS
        cases = {
            'the purpose': ('43255', TE.bleeding(purpose=contra(hemostasis, ct.Purpose.PROPHYLAXIS, spans=(unit(2),)),
                                                 cause=sup(ct.Cause.PRE_EXISTING_LESION)),
                            'why the bleeding control', 'what caused'),
            'the cause': ('43255', TE.bleeding(purpose=sup(hemostasis),
                                               cause=contra(ct.Cause.PRE_EXISTING_LESION, ct.Cause.SPONTANEOUS,
                                                            spans=(unit(2),))),
                          'what caused the bleeding the bleeding control', 'why the'),
            'the reach (43259)': ('43259', TE.eus_fna([sup(ct.Station.ESOPHAGUS), sup(ct.Station.STOMACH),
                                                       sup(ct.Station.DUODENUM)],
                                                      reached=(contra(ct.Extent.SECOND_PORTION_DUODENUM,
                                                                      ct.Extent.STOMACH, spans=(unit(1),)),)),
                                  'how far the endoscopic ultrasound reached', 'which parts'),
            'the reach (43237)': ('43237', TE.eus_fna([sup(ct.Station.ESOPHAGUS), sup(ct.Station.STOMACH)],
                                                      reached=(contra(ct.Extent.SECOND_PORTION_DUODENUM,
                                                                      ct.Extent.STOMACH, spans=(unit(1),)),)),
                                  'how far the endoscopic ultrasound reached', 'which parts'),
        }
        doc = TE.dilation(sup(ct.Landmark.DISTAL_ESOPHAGUS), lesion=contra(TE.L(1), TE.L(2), spans=(unit(2),)))
        doc.lesion(1, lesion_places=[sup(ct.Landmark.DISTAL_ESOPHAGUS)])
        doc.lesion(2, lesion_places=[sup(ct.Landmark.DISTAL_ESOPHAGUS)])
        cases['the target lesion'] = ('43249', doc.build(), 'which lesion the dilation', 'where the dilation')
        doc = TE.dilation(sup(ct.Landmark.DISTAL_ESOPHAGUS), lesion=sup(TE.L(1)))
        doc.lesion(1, lesion_places=[contra(ct.Landmark.DISTAL_ESOPHAGUS, ct.Landmark.STOMACH, spans=(unit(2),))])
        cases['the lesion\'s place'] = ('43249', doc.build(), 'where the lesion of the dilation', 'where the dilation')
        for name, (code, R, about, never) in cases.items():
            with self.subTest(name):
                found, worded = self.item(code, R)
                self.assertEqual(found.message, Q.MessageId.CONFLICT_ATTRIBUTE)
                self.assertIn(f'The document is not consistent about {about}', worded.question)
                self.assertNotIn(never, worded.question + worded.reason)

    def test_f7_the_approach_is_asked_beside_an_open_reach(self):
        """p29: 44406, the reach partly open and the approach silent - the approach question (row 8), the supported
        point named, never R6's "how far"."""
        R = TE.lower_eus(sup(ct.Extent.SIGMOID_COLON), unres(ct.Extent.DESCENDING_COLON))
        found, worded = self.item('44406', R)
        self.assertEqual((found.message, found.held.rank), (Q.MessageId.EXAMINATION_ROUTE, 8))
        self.assertIn('reached the sigmoid colon; CPT Studio could not confirm from the document whether it was passed '
                      'through the documented stoma', worded.question)
        self.assertNotIn('how far', worded.question + worded.reason)

    def test_a_synthetic_examination_doubt_raised_elsewhere_is_named_by_its_own_kind(self):
        """F1 beside repair r4c's R3: a synthetic examination witness appended as ``extra`` (performed_status at rank 2,
        cause unlisted, its subject the session X1, its spans an unlisted DOUBT's units) is named by its own kind and
        quotes the doubt (questions.synthetic_entry reads both natures, an act first). D232: the doubt's card names the
        EGD X2, not X1, so it never names the colonoscopy "left in doubt" - "the examination"; carded to X1, "the
        colonoscopy"."""
        for card, named in ((X(2), 'examination'), (X(1), 'colonoscopy')):
            with self.subTest(card=card):
                doc = colonoscopy()
                doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, card, unit(5)))
                doc.session(2, ct.SessionKind.EGD)
                R = doc.build()
                extra = HeldFact(fact='performed_status', attribute=None, subject=X(1), result=None, kind=QUESTION,
                                 cause='unlisted', reason=None, spans=(unit(5),), rank=2)
                found = EV.item('45385', (), R, EV.decide('45385', (), R), extra=(extra,))
                worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
                self.assertEqual((found.held, found.message, found.fill.act, found.fill.words),
                                 (extra, Q.MessageId.DOUBT, ct.Kind.EXAMINATION, (unit(5),)))
                # D281 (B6): the held session's examination, named by its service, is asked by row 7's done
                verb = DONE if named == 'colonoscopy' else 'was done'
                self.assertTrue(worded.question.startswith(f'Confirm whether the {named} ({_quote(unit(5))}) '
                                                           f'{"is " if verb == DONE else ""}{verb}'), worded.question)
                self.assertTrue(worded.reason.startswith(f'The document leaves the {named} in doubt: '))

    def test_the_same_duct_question_names_the_counterpart_whose_status_is_unknown(self):
        """A filed removal in doubt in the placement's duct: whether the removal was done - never "could not confirm
        that the stent placement was done" of the supported placement."""
        R = TE.stent_placement(dict(status=doubted(Status.PERFORMED), duct=sup(ct.Duct.BILIARY))).build()
        found, worded = self.item('43274', R, (unit(2),))
        self.assertEqual((found.message, found.held.subject), (Q.MessageId.STATUS, E(5)))
        self.assertEqual(worded.question, f'Was the stent removal ({_quote(unit(5))}) done on the date of service?')
        self.assertEqual(worded.reason,
                         'CPT Studio could not confirm from the document that the stent removal was done.')


class D232Sentences(SimpleTestCase):
    """D232 (refute-r4a-r2 N1): an unlisted doubt never names a session's examination as left in doubt unless its card
    names that session - row 7's synthetic examination doubt in an act-only session, and 3.2.6 rule 4's pair of the doubt
    with a session's examination (row 8, RANK row 2) - p41's inputs and the act-only variants. Each sentence true for
    its state and built by wording.build."""

    def item(self, code, R, kept=()):
        found = EV.item(code, tuple(kept), R, EV.decide(code, tuple(kept), R))
        self.assertIsNotNone(found)
        worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
        self.assertEqual(worded.fact, found.held.fact)
        return found, worded

    def test_row_7s_synthetic_doubt_names_the_sessions_examination_only_when_its_card_names_it(self):
        """An act-only colonoscopy and one unlisted doubt of its examination: carded X1, DOUBT naming "the colonoscopy",
        quoting the doubt's own unit. Restated for D258 (repair r4a of round w8r): with no card, or a card naming a
        session the FactSet does not hold, the statement names no procedure session, so the item is UNLISTED_SCOPE -
        the held session's examination asked by its service ("Is the colonoscopy documented as done ...", no words of
        its own: the session is act-only), the doubt quoted as the statement - never "leaves ... in doubt" (D232's
        "the examination" form is gone with it)."""
        doc = TE.act_only_colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, X(1), unit(9)))
        found, worded = self.item('45385', doc.build())
        self.assertEqual((found.message, found.fill.act, found.fill.words, found.held.subject),
                         (Q.MessageId.DOUBT, ct.Kind.EXAMINATION, (unit(9),), X(1)))
        self.assertEqual(worded.question,  # D281 (B6): the held session's examination asked by row 7's done
                         f'Confirm whether the colonoscopy ({_quote(unit(9))}) is {DONE}.')
        self.assertTrue(worded.reason.startswith('The document leaves the colonoscopy in doubt: '))
        for card in (None, TE.X(9)):
            with self.subTest(card=card):
                doc = TE.act_only_colonoscopy()
                doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, card, unit(9)))
                found, worded = self.item('45385', doc.build())
                self.assertEqual((found.message, found.fill.act, found.fill.words, found.fill.statements,
                                  found.fill.family, found.held.subject),
                                 (Q.MessageId.UNLISTED_SCOPE, ct.Kind.EXAMINATION, (), ((unit(9),),),
                                  ct.SessionKind.COLONOSCOPY, X(1)))
                self.assertEqual(worded.question, f'Is the colonoscopy {DONE}?')  # D281 (B6)
                self.assertEqual(worded.reason, scope_reason(unit(9), 'colonoscopy'))

    def test_rule_4s_pair_names_the_examination_only_when_the_doubts_card_names_its_session(self):
        """p41: the base codes beside one unlisted doubt of kind examination. Carded X1: 45378's item names the
        colonoscopy (its card names the session E1 is established in). Restated for D258 (QP2): with no card, 45378 and
        43235 are UNLISTED_SCOPE - each its own session's examination asked by its service and quoted by its own
        anchor, whether it is documented as done on the date of service, the doubt quoted as a statement naming no
        procedure session - never "The document leaves ... in doubt", and never the other session's service. The held
        fact is rule 4's, unchanged (performed_status, rank 2, cause unlisted, subject the examination)."""
        R = TE.p41(card=X(1), egd_beside=True).build()
        found, worded = self.item('45378', R)
        self.assertEqual((found.message, found.held.subject, found.fill.words), (Q.MessageId.DOUBT, E(1), (unit(1),)))
        self.assertTrue(worded.reason.startswith('The document leaves the colonoscopy in doubt: '))
        R = TE.p41(card=None, egd_beside=True).build()
        for code, examination, family, service, other in (
                ('45378', E(1), ct.SessionKind.COLONOSCOPY, 'colonoscopy', 'upper endoscopy'),
                ('43235', E(3), ct.SessionKind.EGD, 'upper endoscopy', 'colonoscopy')):
            with self.subTest(code=code):
                found, worded = self.item(code, R)
                self.assertEqual((found.message, found.held.fact, found.held.rank, found.held.subject, found.held.cause,
                                  found.fill.act, found.fill.words, found.fill.statements, found.fill.family),
                                 (Q.MessageId.UNLISTED_SCOPE, 'performed_status', 2, examination, Q.UNLISTED,
                                  ct.Kind.EXAMINATION, Q.anchor_units(R, examination), ((unit(9),),), family))
                self.assertEqual(worded.question, f'Is the {service} ({_quote(Q.anchor_units(R, examination)[0])}) '
                                                  f'{DONE}?')  # D281 (B6)
                self.assertEqual(worded.reason, scope_reason(unit(9), service))
                self.assertNotIn('in doubt', worded.question + worded.reason)
                self.assertNotIn(other, worded.question + worded.reason)

    def test_beside_the_done_examinations_nothing_is_held_with_an_untrue_sentence(self):
        """p41's done-when: the doubt (card X1 or none) leaves 45385 READY beside the colonoscopy's done examination,
        and beside the EGD holds 43239 and 45385 READY; every code it still holds (the base codes, by rule 4) names only
        its own session's examination - the colonoscopy as left in doubt only where the doubt's card names X1, and with
        no card asked as UNLISTED_SCOPE, never "in doubt" (restated for D258)."""
        for card in (X(1), None):
            with self.subTest(card=card):
                R = TE.p41(card=card, egd_beside=True).build()
                for code in ('45385', '43239'):
                    self.assertIsNone(EV.item(code, (), R, EV.decide(code, (), R)))
                for code, other in (('45378', 'upper endoscopy'), ('43235', 'colonoscopy')):
                    found = EV.item(code, (), R, EV.decide(code, (), R))
                    if found is None:
                        continue
                    worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
                    self.assertNotIn(other, worded.question + worded.reason)
                    if card is None:
                        self.assertEqual(found.message, Q.MessageId.UNLISTED_SCOPE)
                        self.assertNotIn('in doubt', worded.question + worded.reason)

    def test_a_doubt_of_another_kind_is_unchanged_and_a_no_card_denial_is_unlisted_scope(self):
        """D232 is about a session's examination: a rule-4 pair with a snare names the snare removal as before (D258 is
        about the session's examination too). An unlisted DENIAL with no card is no longer worded "The document leaves
        the colonoscopy in doubt: <denial>" (r4a's QD): D258 words it as UNLISTED_SCOPE, the held fact unchanged
        (restated); carded X1, it keeps its DOUBT item."""
        doc = colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.SNARE, None, unit(9)))
        found, worded = self.item('45385', doc.build())
        self.assertEqual((found.message, found.held.subject, found.fill.act), (Q.MessageId.DOUBT, E(2), ct.Kind.SNARE))
        self.assertTrue(worded.reason.startswith('The document leaves the snare removal (cold snare) at the sigmoid '
                                                 'colon in doubt: '))
        found, worded = self.item('45378', TE.p41(ct.UnlistedWhat.DENIAL, None).build())
        self.assertEqual((found.message, found.held.subject, found.held.rank, found.fill.words, found.fill.statements),
                         (Q.MessageId.UNLISTED_SCOPE, E(1), 2, (unit(1),), ((unit(9),),)))
        self.assertNotIn('in doubt', worded.question + worded.reason)
        found, worded = self.item('45378', TE.p41(ct.UnlistedWhat.DENIAL, X(1)).build())
        self.assertEqual((found.message, found.held.subject, found.fill.words), (Q.MessageId.DOUBT, E(1), (unit(1),)))


def _quote_reason(span):
    """The filler's words a span quotes in a reason (wording.doubt_reason cuts at 140)."""
    return wording.quote(wording.span_text(FILLER, (span,)), 140)


# D281 (step f3w; build list B6, G3-27): row 7's done, as every question about the held session's examination says it
DONE = 'documented as performed, in full or in part, on the date of service'


def scope_reason(span, service):
    """UNLISTED_SCOPE's reason over the filler (DECISIONS D258; repair r3c of round w8r's sentence): the statement
    quoted (cut at 140), said to name no procedure session, and the held session's examination named by ``service``."""
    return (f'The document states {_quote_reason(span)}, which names no procedure session; CPT Studio could not '
            f'confirm from the document whether it is about the {service}. Held for the reviewer, not excluded.')


def biopsied(multiplicity):
    """A colonoscopy X1 (its examination E1): a cold-snare removal E2 and a cold-forceps biopsy E3 of one lesion L1 in the
    rectum, in two units; ``multiplicity`` L1's (single: the biopsy of the removed lesion, bundled; not established: its
    identity asked, coverage's C-2 / D196)."""
    doc = TE.Doc()
    doc.session(1, ct.SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(ct.Extent.CECUM)])
    doc.exam(1)
    doc.lesion(1, lesion_places=[sup(ct.Landmark.RECTUM)], multiplicity=multiplicity)
    doc.act(2, ct.Kind.SNARE, lesion=sup(TE.L(1)), places=[sup(ct.Landmark.RECTUM)], device=sup(ct.Device.COLD_SNARE))
    doc.act(3, ct.Kind.BIOPSY, lesion=sup(TE.L(1)), places=[sup(ct.Landmark.RECTUM)],
            device=sup(ct.Device.COLD_FORCEPS))
    return doc.build()


def injected(**injection):
    """A colonoscopy X1 (its examination E1): an EMR E2 of the cecal lesion L1, and an injection E3 (``injection`` its
    facts) beside it - its lift possible (coverage's LIFT_INJECTION)."""
    doc = TE.Doc()
    doc.session(1, ct.SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(ct.Extent.CECUM)])
    doc.exam(1)
    doc.lesion(1, lesion_places=[sup(ct.Landmark.CECUM)])
    doc.act(2, ct.Kind.EMR, lesion=sup(TE.L(1)), places=[sup(ct.Landmark.CECUM)])
    doc.act(3, ct.Kind.INJECTION, **injection)
    return doc.build()


def enteroscopy(approach, reached, completion=None, **session):
    """An enteroscopy X1 (its examination E1): its approach, reach and completion as given."""
    doc = TE.Doc()
    doc.session(1, ct.SessionKind.ENTEROSCOPY, approach=approach, reached=reached, completion=completion, **session)
    doc.exam(1)
    return doc.build()


class D246Items(SimpleTestCase):
    """D246's 4a half (the lead's L1; 5c's R8; r4a R4 (a)): questions.fill gives every slot wording asks of 4a's items -
    the bundling items (PART and BUNDLING_TARGET: the part, ``whole_words`` its whole's anchor units, the rule; BUNDLED:
    the rule), each from the coverage bundle that raised the hold; the enteroscopy class items (``enteroscopy_class``,
    the session's supported approach, the incomplete form); a base-within hold is BASE_WITHIN; the synthetic act's
    witness is SYNTHETIC_ACT. The holds are those assess appends as ``extra`` (coverage.bundling,
    classes.enteroscopy_hold, combination's base-within), and every item is built by wording.build."""

    def item(self, code, R, extra_of):
        evaluation = EV.decide(code, (), R)
        extra = tuple(extra_of(evaluation.supporting))
        found = EV.item(code, (), R, evaluation, extra=extra)
        self.assertIsNotNone(found)
        self.assertIn(found.held, (*evaluation.held_facts, *extra))
        worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
        self.assertEqual(worded.fact, found.held.fact)
        return found, worded

    @staticmethod
    def bundling(code, R):
        return lambda supporting: CV.bundling(code, supporting, CV.Reader(R))

    @staticmethod
    def enteroscopy_hold(code, R):
        return lambda supporting: CL.enteroscopy_hold(code, supporting, R)

    def test_the_synthetic_acts_witness_is_synthetic_act_and_a_doubts_stays_doubt(self):
        """r4a R4 (a): the witness of a kept unlisted ACT is SYNTHETIC_ACT (the same fact key, kind and rank as DOUBT,
        mirrored in MessageId: Mirrors), the act's own kind and unit; a kept unlisted DOUBT stays DOUBT."""
        spec = wording.MESSAGES[wording.Message.SYNTHETIC_ACT]
        self.assertEqual((spec.fact, spec.kind, spec.rank), ('performed_status', QUESTION, 2))
        self.assertEqual(Q.MessageId.SYNTHETIC_ACT.value, wording.Message.SYNTHETIC_ACT.value)
        for what, message in ((ct.UnlistedWhat.ACT, Q.MessageId.SYNTHETIC_ACT), (ct.UnlistedWhat.DOUBT,
                                                                                  Q.MessageId.DOUBT)):
            with self.subTest(what=what):
                doc = TE.act_only_colonoscopy()
                doc.unlisted.append(TE.unlisted(what, ct.Kind.EXAMINATION, X(1), unit(5)))
                found, worded = self.item('45385', doc.build(), lambda supporting: ())
                self.assertEqual((found.message, found.fill.act, found.fill.words, found.fill.statements),
                                 (message, ct.Kind.EXAMINATION, (unit(5),), ()))
                self.assertEqual('in doubt' in worded.reason, what is ct.UnlistedWhat.DOUBT)

    def test_a_within_hold_is_base_within(self):
        """5c's R8: combination's base-within hold (fact base_included, cause coding_rule:base_within) is BASE_WITHIN,
        an established whole's explanation and a possible whole's question alike (the step's NOTES, question QW); a
        base_included hold keeps BASE_INCLUDED and BASE_EXPLAINED; the sentence builds over item_slots' slots (the code,
        its family, the within codes)."""
        code = EV.code_facts('43235')
        for kind in (EXPLANATION, QUESTION):
            with self.subTest(kind=kind):
                within = held('base_included', 21, kind, subject=X(1), cause=CB.WITHIN_CAUSE)
                self.assertEqual(Q.message_of(within, code), Q.MessageId.BASE_WITHIN)
                base = held('base_included', 21, kind, subject=X(1), cause=CB.BASE_CAUSE)
                self.assertEqual(Q.message_of(base, code), Q.MessageId.BASE_EXPLAINED if kind is EXPLANATION
                                 else Q.MessageId.BASE_INCLUDED)
                found = Q.item((within,), (), code, colonoscopy().build())
                self.assertEqual((found.message, found.held), (Q.MessageId.BASE_WITHIN, within))
        worded = wording.build(wording.Message.BASE_WITHIN, wording.Slots(code='43235', family=ct.SessionKind.EGD,
                                                                          codes=('43242',)), FILLER)
        self.assertEqual(worded.question, 'Is 43235 reported separately from 43242 for this examination?')

    def test_the_bundled_explanation_names_its_rule(self):
        """A biopsy of the snared single lesion: bundled (coverage's BIOPSY_OF_REMOVED_LESION, T) - BUNDLED with the
        rule, the biopsy's own words."""
        R = biopsied(sup(ct.Multiplicity.SINGLE))
        found, worded = self.item('45380', R, self.bundling('45380', R))
        self.assertEqual((found.message, found.fill.bundling, found.fill.act, found.fill.words),
                         (Q.MessageId.BUNDLED, Q.Bundling.BIOPSY_OF_REMOVED_LESION, ct.Kind.BIOPSY, (unit(3),)))
        self.assertIn('A biopsy of a lesion that is then removed at the same session', worded.reason)

    def test_the_bundling_target_names_the_part_its_whole_and_the_rule_whichever_object_it_rests_on(self):
        """The lesion's multiplicity not established: the identity asked - BUNDLING_TARGET resting on the LESION (its
        multiplicity), named as the biopsy (the part: its kind, its words) beside the removal (the whole: its anchor
        units), the biopsy rule."""
        R = biopsied(TE.doubted(ct.Multiplicity.GROUP, ct.Multiplicity.SINGLE))
        found, worded = self.item('45380', R, self.bundling('45380', R))
        self.assertEqual((found.message, found.held.subject, found.held.attribute), (Q.MessageId.BUNDLING_TARGET,
                                                                                    TE.L(1), ct.Attribute.MULTIPLICITY))
        self.assertEqual((found.fill.act, found.fill.words, found.fill.whole, found.fill.whole_words,
                          found.fill.bundling),
                         (ct.Kind.BIOPSY, (unit(3),), ct.Kind.SNARE, (unit(2),), Q.Bundling.BIOPSY_OF_REMOVED_LESION))
        self.assertEqual(worded.question, f'Was the forceps biopsy ({_quote(unit(3))}) taken from the lesion that was '
                                          f'removed ({_quote(unit(2))}), or from another lesion?')

    def test_the_part_question_names_the_part_its_whole_and_the_rule(self):
        """An injection beside the EMR, its relation to it doubted: PART (act_part) - the injection, the EMR's words, the
        lift rule; with nothing stated of the injection, BUNDLING_TARGET (act_target) the same."""
        for name, R, message in (('part_of doubted', injected(part_of=TE.doubted(E(2))), Q.MessageId.PART),
                                 ('nothing stated', injected(), Q.MessageId.BUNDLING_TARGET)):
            with self.subTest(name):
                found, worded = self.item('45381', R, self.bundling('45381', R))
                self.assertEqual((found.message, found.fill.act, found.fill.words, found.fill.whole_words,
                                  found.fill.bundling),
                                 (message, ct.Kind.INJECTION, (unit(3),), (unit(2),), Q.Bundling.LIFT_INJECTION))
                self.assertTrue(worded.question.startswith(f'Was the submucosal injection ({_quote(unit(3))}) made to '
                                                           f'lift the lesion that was resected ({_quote(unit(2))})'))

    def test_the_enteroscopy_approach_names_the_class_and_the_approach(self):
        """A jejunal code on an enteroscopy entered through a stoma (its approach supported, quoted): the approach's
        explanation (ENTEROSCOPY_APPROACH, RANK row 8) - the jejunal class, the reach, the approach and its words."""
        R = enteroscopy(sup(ct.Approach.THROUGH_STOMA, spans=(unit(4),)), [sup(ct.Extent.JEJUNUM, spans=(unit(5),))])
        found, worded = self.item('44360', R, self.enteroscopy_hold('44360', R))
        self.assertEqual((found.message, found.fill.enteroscopy_class, found.fill.reached, found.fill.approach,
                          found.fill.approach_words),
                         (Q.MessageId.ENTEROSCOPY_APPROACH, EV.catalogue.EnteroscopyClass.JEJUNAL, ct.Extent.JEJUNUM,
                          ct.Approach.THROUGH_STOMA, (unit(4),)))
        self.assertIn('reached the jejunum', worded.question)

    def test_the_enteroscopy_class_names_the_class_and_its_form(self):
        """An ileal code on an enteroscopy reaching the ileum whose completion is stated incomplete: ENTEROSCOPY_CLASS
        in the incomplete form (classes.misfit_form: v1's "stated to be incomplete"); a jejunal code on one reaching
        the ileum: the class form, naming the reach."""
        oral = sup(ct.Approach.ORAL, spans=(unit(4),))
        ileum = [sup(ct.Extent.ILEUM, spans=(unit(5),))]
        R = enteroscopy(oral, ileum, completion=sup(ct.Completion.INCOMPLETE, spans=(unit(6),)))
        found, worded = self.item('44376', R, self.enteroscopy_hold('44376', R))
        self.assertEqual((found.message, found.fill.enteroscopy_class, found.fill.incomplete),
                         (Q.MessageId.ENTEROSCOPY_CLASS, EV.catalogue.EnteroscopyClass.ILEAL, True))
        self.assertIn('is stated to be incomplete', worded.question)
        R = enteroscopy(oral, ileum)
        found, worded = self.item('44360', R, self.enteroscopy_hold('44360', R))
        self.assertEqual((found.message, found.fill.enteroscopy_class, found.fill.reached, found.fill.incomplete),
                         (Q.MessageId.ENTEROSCOPY_CLASS, EV.catalogue.EnteroscopyClass.JEJUNAL, ct.Extent.ILEUM, False))
        self.assertIn('reached the ileum', worded.question)

    def test_every_d246_item_of_the_scenes_is_worded(self):
        """D182 and D246 over the scenes above: each held code carries exactly one item, and wording builds it."""
        scenes = [('45380', biopsied(sup(ct.Multiplicity.SINGLE)), 'bundling'),
                  ('45380', biopsied(TE.doubted(ct.Multiplicity.GROUP, ct.Multiplicity.SINGLE)), 'bundling'),
                  ('45381', injected(), 'bundling'), ('45381', injected(part_of=TE.doubted(E(2))), 'bundling'),
                  ('44360', enteroscopy(sup(ct.Approach.THROUGH_STOMA, spans=(unit(4),)),
                                        [sup(ct.Extent.JEJUNUM, spans=(unit(5),))]), 'enteroscopy'),
                  ('44376', enteroscopy(sup(ct.Approach.ORAL, spans=(unit(4),)), [sup(ct.Extent.ILEUM, spans=(unit(5),))],
                                        completion=sup(ct.Completion.INCOMPLETE, spans=(unit(6),))), 'enteroscopy'),
                  ('44360', enteroscopy(sup(ct.Approach.ORAL, spans=(unit(4),)),
                                        [sup(ct.Extent.ILEUM, spans=(unit(5),))]), 'enteroscopy')]
        for code, R, source in scenes:
            with self.subTest(code=code, source=source):
                extra_of = self.bundling(code, R) if source == 'bundling' else self.enteroscopy_hold(code, R)
                found, _ = self.item(code, R, extra_of)
                self.assertIsNotNone(found)


J5, I6 = sup(ct.Extent.JEJUNUM, spans=(unit(5),)), sup(ct.Extent.ILEUM, spans=(unit(6),))
ORAL4, STOMA4 = sup(ct.Approach.ORAL, spans=(unit(4),)), sup(ct.Approach.THROUGH_STOMA, spans=(unit(4),))


def enteroscopy_act(approach, reached, act=ct.Kind.BIOPSY, **session):
    """``enteroscopy`` with an act E2 of ``act`` at the jejunum (its own sentence unit 2)."""
    doc = TE.Doc()
    doc.session(1, ct.SessionKind.ENTEROSCOPY, approach=approach, reached=reached, **session)
    doc.exam(1)
    doc.act(2, act, places=[sup(ct.Landmark.JEJUNUM)])
    return doc


class R4a2Sentences(SimpleTestCase):
    """Repair r4a-2 of round w7r, questions.py's half of refute-r4a-r1 and of the repair's own check: the enteroscopy class
    items name the reach the class rule read and quote that reach's own words (P3), the approach's words where it cites
    none (P4) and the documented stoma of the route question (P11); an enteroscopy class item whose session has no
    supported reach gives way to the reach's own question, so the code always has a sentence (the step's NOTES, QR);
    read time, which passes no Raised, words a synthetic hold as assess does (P10); a card naming a session the FactSet
    does not hold names no session (P9)."""

    item = D246Items.item
    enteroscopy_hold = staticmethod(D246Items.enteroscopy_hold)

    def test_p3_the_class_item_names_the_reach_the_rule_read_and_quotes_its_words(self):
        """P3's input: an oral enteroscopy reaching [jejunum, ileum] (either order), 44360: the jejunal class is F on the
        ileum, the point past it - "reached the ileum", quoting the ileum's own words (unit 6), never "reached the
        jejunum" (the first patch: the first supported point, the examination's anchor quoted)."""
        for name, reached in (('[jejunum, ileum]', [J5, I6]), ('[ileum, jejunum]', [I6, J5])):
            with self.subTest(reached=name):
                R = enteroscopy(ORAL4, reached)
                found, worded = self.item('44360', R, self.enteroscopy_hold('44360', R))
                self.assertEqual((found.message, found.fill.reached, found.fill.words),
                                 (Q.MessageId.ENTEROSCOPY_CLASS, ct.Extent.ILEUM, (unit(6),)))
                self.assertEqual(worded.question,
                                 f'The documented enteroscopy ({_quote(unit(6))}) reached the ileum. Was a small-bowel '
                                 'enteroscopy past the second portion of the duodenum that stops short of the ileum '
                                 'performed on the date of service?')

    def test_p3_an_act_codes_class_item_quotes_the_reach_never_the_acts_own_sentence(self):
        """P3's second input: a jejunal biopsy E2 on an enteroscopy reaching the ileum - 44361 (jejunal class: the class
        explanation) and, entered through a stoma, 44377 (ileal: the approach's explanation) - quote the reach's words
        (unit 6), never the biopsy's sentence (unit 2) as the evidence of the enteroscopy's reach; 44377's route is its
        approach's own words (unit 4)."""
        R = enteroscopy_act(ORAL4, [I6]).build()
        found, worded = self.item('44361', R, self.enteroscopy_hold('44361', R))
        self.assertEqual((found.message, found.fill.act, found.fill.reached, found.fill.words),
                         (Q.MessageId.ENTEROSCOPY_CLASS, ct.Kind.BIOPSY, ct.Extent.ILEUM, (unit(6),)))
        self.assertNotIn(_quote(unit(2)), worded.question + worded.reason)
        R = enteroscopy_act(STOMA4, [I6]).build()
        found, worded = self.item('44377', R, self.enteroscopy_hold('44377', R))
        self.assertEqual((found.message, found.fill.reached, found.fill.words, found.fill.approach,
                          found.fill.approach_words),
                         (Q.MessageId.ENTEROSCOPY_APPROACH, ct.Extent.ILEUM, (unit(6),), ct.Approach.THROUGH_STOMA,
                          (unit(4),)))
        self.assertEqual(worded.question,
                         f'The documented enteroscopy ({_quote(unit(6))}) reached the ileum through a stoma '
                         f'({_quote(unit(4))}). Was a small-bowel enteroscopy past the second portion of the duodenum '
                         'that reaches the ileum performed on the date of service?')

    def test_p4_a_reach_or_approach_citing_no_words_is_quoted_as_the_enteroscopys_own_statement(self):
        """P4 (the done-when's enteroscopy_approach refusals): a hand-built supported approach and reach with no spans
        (a settled fact always cites its sources) - the item quotes the enteroscopy's own statement, its examination's
        anchor (unit 1), for the reach and for the route, and is worded; never the act's own sentence (unit 2)."""
        R = enteroscopy_act(sup(ct.Approach.TRANSANAL), [sup(ct.Extent.ILEUM)]).build()
        for code in ('44376', '44377'):
            with self.subTest(code=code):
                found, worded = self.item(code, R, self.enteroscopy_hold(code, R))
                self.assertEqual((found.message, found.fill.approach, found.fill.approach_words, found.fill.words),
                                 (Q.MessageId.ENTEROSCOPY_APPROACH, ct.Approach.TRANSANAL, (unit(1),), (unit(1),)))
                self.assertNotIn(_quote(unit(2)), worded.question)

    def test_p11_the_route_question_names_the_documented_stoma(self):
        """P11: the jejunal code on an oral enteroscopy that went through a stoma entry (its through supported, the
        entry's type supported stoma): the route question names "the documented stoma", as v1's class_hold did - never
        only "a stoma or pouch"."""
        doc = TE.Doc()
        doc.session(1, ct.SessionKind.ENTEROSCOPY, approach=ORAL4, reached=[J5], through=sup(TE.Y(1)))
        doc.entry(1, type=sup(ct.AnatomyType.STOMA))
        doc.exam(1)
        R = doc.build()
        found, worded = self.item('44360', R, self.enteroscopy_hold('44360', R))
        self.assertEqual((found.message, found.fill.approaches, found.fill.reached),
                         (Q.MessageId.ENTEROSCOPY_ROUTE, (ct.Approach.THROUGH_STOMA,), ct.Extent.JEJUNUM))
        self.assertIn('whether it was passed through the mouth or through the documented stoma.', worded.question)

    def test_qr_with_no_reach_supported_the_item_is_the_reachs_own_question(self):
        """The repair's own check (QR): the approach established as another route (an explanation at RANK row 8) beside a
        reach not established - unresolved, doubted, or none filed. No class sentence can name the reach, and wording
        refuses ENTEROSCOPY_APPROACH without one (the document would fail to assess); the item is the reach's own
        question (extent, rank 14), worded, the class hold kept in held_facts - v1's class_misfit gave no class hold
        while the reach was not verified. Through the whole engine (assess) and with classes' holds alone."""
        for name, reached in (('unresolved', [unres(ct.Extent.JEJUNUM, spans=(unit(5),))]),
                              ('doubted', [TE.doubted(ct.Extent.JEJUNUM, spans=(unit(5),))]), ('none', None)):
            with self.subTest(reached=name):
                R = enteroscopy(STOMA4, reached)
                found, worded = self.item('44360', R, self.enteroscopy_hold('44360', R))
                self.assertEqual((found.message, found.held.fact, found.held.rank, found.kind),
                                 (Q.MessageId.EXTENT, 'extent', 14, QUESTION))
                assessment = TA.run(R, ('44360', 1))
                code = TA.by_code(assessment)['44360']
                self.assertEqual(code.item.message, Q.MessageId.EXTENT)
                self.assertIn(('procedure', 'coding_rule:enteroscopy_class'),
                              [(held.fact, held.cause) for held in code.held_facts])
                worded = wording.build(wording.Message(code.item.message.value), slots(code.item.fill), TA.TEXT)
                self.assertTrue(worded.question)
        R = enteroscopy(STOMA4, [J5])
        found, _ = self.item('44360', R, self.enteroscopy_hold('44360', R))
        self.assertEqual(found.message, Q.MessageId.ENTEROSCOPY_APPROACH)  # a reach supported: the class item, as before

    def test_qr_when_every_class_hold_names_no_reach_the_reach_is_asked(self):
        """QR's residual (deviation DV2): 44376 on an enteroscopy whose ileal reach is denied whole with no reached point
        supported and whose completion is stated incomplete (R6:extent met) - every held fact is a class explanation
        that would name a reach. The item rests on classes' REACH explanation and is worded as the extent question
        (v1's class_hold EXTENT form; classes.misfit_form gives EXTENT) - never a wording refusal. Through assess too."""
        R = enteroscopy(ORAL4, [TE.neg(ct.Extent.ILEUM, spans=(unit(7),))],
                        completion=sup(ct.Completion.INCOMPLETE, spans=(unit(8),)))
        self.assertIs(CL.misfit_form('44376', X(1), R), CL.ClassForm.EXTENT)
        evaluation = EV.decide('44376', (), R)
        extra = tuple(CL.enteroscopy_hold('44376', evaluation.supporting, R))
        found = EV.item('44376', (), R, evaluation, extra=extra)
        self.assertEqual((found.message, found.held.fact, found.held.kind, found.held.attribute, found.held.cause),
                         (Q.MessageId.EXTENT, 'extent', EXPLANATION, ct.Attribute.REACHED, CL.CLASS_CAUSE))
        worded = wording.build(wording.Message.EXTENT, slots(found.fill), FILLER)
        self.assertEqual(worded.question, 'Small-bowel enteroscopy: confirm the furthest extent reached.')
        code = TA.by_code(TA.run(R, ('44376', 1)))['44376']
        self.assertEqual((code.item.message, code.item.held), (Q.MessageId.EXTENT, found.held))
        wording.build(wording.Message.EXTENT, slots(code.item.fill), TA.TEXT)

    def test_p10_read_time_words_the_synthetic_hold_as_assess_does(self):
        """P10: an act-only colonoscopy and two kept unlisted entries on ONE unit - a doubt of kind examination and an act
        of no kind, carded X1 - in either order. Read time (questions.item with no Raised, overlay's call) names the entry
        evaluate.py records first, as assess (with evaluate's Raised) does: DOUBT when the doubt is told first,
        SYNTHETIC_ACT when the act is (the first patch: SYNTHETIC_ACT at read time for both)."""
        for order, message in ((('doubt', 'act'), Q.MessageId.DOUBT), (('act', 'doubt'), Q.MessageId.SYNTHETIC_ACT)):
            with self.subTest(order=order):
                doc = TE.act_only_colonoscopy()
                entries = {'doubt': TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, X(1), unit(9)),
                           'act': TE.unlisted(ct.UnlistedWhat.ACT, None, X(1), unit(9))}
                doc.unlisted += [entries[name] for name in order]
                R = doc.build()
                evaluation = EV.decide('45385', (), R)
                assess_item = EV.item('45385', (), R, evaluation)
                read_item = Q.item(evaluation.held_facts, EV.groups('45385', (), R, evaluation),
                                   EV.code_facts('45385'), R, evaluation.supporting)
                self.assertEqual(assess_item.message, message)
                self.assertEqual(read_item, assess_item)

    def test_p9_a_card_naming_a_session_the_factset_does_not_hold_names_none(self):
        """P9: a synthetic examination doubt raised about a session the FactSet does not hold (X9), its entry carded X9 -
        the card names no session the FactSet holds (4.11), so the examination is "the examination", never the code's
        family's service. Restated for D258: such a statement names no procedure session, so the item is UNLISTED_SCOPE
        (the held session's examination asked) - and the held session, X9, is no session the FactSet holds, so no
        service is named and nothing of the colonoscopy is quoted."""
        doc = TE.act_only_colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, TE.X(9), unit(9)))
        R = doc.build()
        witness = held(rank=2, subject=TE.X(9), spans=(unit(9),), cause=Q.UNLISTED)
        found = Q.item((witness,), (), EV.code_facts('45385'), R)
        self.assertEqual((found.message, found.fill.act, found.fill.family, found.fill.words, found.fill.statements),
                         (Q.MessageId.UNLISTED_SCOPE, ct.Kind.EXAMINATION, None, (), ((unit(9),),)))
        worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
        self.assertEqual(worded.question, f'Is the examination {DONE}?')  # D281 (B6)
        self.assertEqual(worded.reason, scope_reason(unit(9), 'examination'))
        self.assertNotIn('colonoscopy', worded.question + worded.reason)


def renderer_words(R, *codes):
    """engine/assess over ``R`` (tests/v2/test_assess.run, each code selected on its event's unit) and each held code's
    ONE item worded by the renderer's own call, jobs.word_item (DECISIONS D246, D254): {code: (Assessed, spec)}; a
    wording refusal raises, as the renderer does."""
    from studio import jobs
    assessment = TA.run(R, *codes)
    out = {}
    for found in assessment.codes:
        spec = None
        if found.item is not None:
            spec = jobs.word_item(found.item, found.key, assessment.combination, R, TA.TEXT)
        out[found.code] = (found, spec)
    return out


class D258UnlistedScope(SimpleTestCase):
    """DECISIONS D258 (r4a QP2, high; QD; r4c Q1): a statement that names no procedure session - a kept unlisted doubt
    or denial with no card, or a card naming a session the FactSet does not hold - held against a session's examination
    (3.2.6 rule 4's pair with it; a synthetic examination act's doubt about it) is asked about that examination's
    performance, never about the statement: UNLISTED_SCOPE (repair r3c of round w8r's message, mirrored: Mirrors), the
    held fact unchanged (performed_status, RANK row 2, cause unlisted). Its question names the held session's
    examination by its service and asks whether it is documented as done on the date of service; its reason quotes the
    statement and says it names no procedure session - never that the document leaves that examination in doubt or
    denies it. A member's "not documented" (or "cannot confirm") bound to the item excludes the code, as any bound
    answer does, and moves nothing else; the reviewer's "documented" is an approval of the held code, unchanged."""

    item = D232Sentences.item

    def test_the_message_has_doubts_fact_kind_and_rank(self):
        spec = wording.MESSAGES[wording.Message.UNLISTED_SCOPE]
        self.assertEqual((spec.fact, spec.kind, spec.rank), ('performed_status', QUESTION, 2))
        doubt = wording.MESSAGES[wording.Message.DOUBT]
        self.assertEqual((spec.fact, spec.kind, spec.rank), (doubt.fact, doubt.kind, doubt.rank))
        self.assertEqual(Q.MessageId.UNLISTED_SCOPE.value, wording.Message.UNLISTED_SCOPE.value)

    def test_qp2_p41s_no_card_doubt_through_assess_and_the_members_answers(self):
        """QP2's p41: a colonoscopy whose examination E1 is established done, the snare E2, and "It is not known whether
        she had a colonoscopy before." kept unlisted with no card. Through assess: 45385 READY; 45378 held by rule 4's
        pair, worded by the renderer as UNLISTED_SCOPE ("Is the colonoscopy (...) documented as done ..."), never
        "leaves ... in doubt". "Not documented" or "cannot confirm" given to that question excludes 45378 and leaves
        45385 as it was; with no answer 45378 stays selected, held for the reviewer (never excluded)."""
        R = TE.p41(card=None).build()
        before = renderer_words(R, ('45385', 2), ('45378', 1))
        found, spec = before['45378']
        self.assertEqual((found.status.value, found.item.message, found.item.held.fact, found.item.held.rank,
                          found.item.held.cause, found.item.held.subject),
                         ('needs_clarification', Q.MessageId.UNLISTED_SCOPE, 'performed_status', 2, Q.UNLISTED, E(1)))
        self.assertTrue(spec.question.startswith('Is the colonoscopy ('))
        self.assertTrue(spec.question.endswith(f') {DONE}?'))  # D281 (B6)
        self.assertIn('which names no procedure session', spec.reason)
        self.assertNotIn('in doubt', spec.question + spec.reason)
        self.assertEqual(before['45385'][0].status.value, 'ready')
        for value in ('not_documented', 'cannot_confirm'):
            with self.subTest(value=value):
                after = TA.by_code(TA.run(R, ('45385', 2), ('45378', 1), answers=(TA.answer(found, value=value),)))
                self.assertEqual((after['45378'].status.value, after['45378'].answered.fact),
                                 ('excluded', 'performed_status'))
                self.assertEqual(after['45385'], before['45385'][0])

    def test_qd_a_no_card_denial_is_asked_the_same_way(self):
        """QD: "No colonoscopy was performed." kept unlisted with no card, beside the colonoscopy's done examination
        (and an EGD's): 45378 and 43235 are UNLISTED_SCOPE, each its own session's examination asked, the denial quoted
        as a statement naming no procedure session - never "leaves the colonoscopy in doubt", which is untrue of a
        denial, and never the word denial."""
        R = TE.p41(ct.UnlistedWhat.DENIAL, None, egd_beside=True).build()
        for code, examination, service in (('45378', E(1), 'colonoscopy'), ('43235', E(3), 'upper endoscopy')):
            with self.subTest(code=code):
                found, worded = self.item(code, R)
                self.assertEqual((found.message, found.held.subject, found.held.rank, found.held.cause,
                                  found.fill.statements),
                                 (Q.MessageId.UNLISTED_SCOPE, examination, 2, Q.UNLISTED, ((unit(9),),)))
                self.assertEqual(worded.reason, scope_reason(unit(9), service))
                for never in ('in doubt', 'deni', 'leaves'):
                    self.assertNotIn(never, worded.question + worded.reason)

    def test_r4c_q1_the_ileal_input(self):
        """r4c Q1: an ileal enteroscopy X1 whose examination E1 is established begun and not completed, beside a done
        EGD X2, and an unlisted doubt of kind examination. With no card it pairs with E1 (rule 4: 44376 held, E1 the
        held act); with a card naming a session the FactSet does not hold it is step 4c's synthetic examination act of
        X1 (classes.enteroscopy_hold's witness, subject X1). Either way the item is UNLISTED_SCOPE - "Is the enteroscopy
        (E1's words) documented as done ..." - never "The document leaves the enteroscopy in doubt", true only if the
        doubt were about X1's examination; carded X1, it is (DOUBT, the enteroscopy named). Through assess too."""
        for card, subject in ((None, E(1)), (TE.X(9), X(1))):
            with self.subTest(card=card):
                R = TE.ileal_attempt(card).build()
                evaluation = EV.decide('44376', (), R)
                extra = tuple(CL.enteroscopy_hold('44376', evaluation.supporting, R))
                found = EV.item('44376', (), R, evaluation, extra=extra)
                worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
                self.assertEqual((found.message, found.held.fact, found.held.rank, found.held.cause, found.held.subject,
                                  found.fill.family, found.fill.words, found.fill.statements),
                                 (Q.MessageId.UNLISTED_SCOPE, 'performed_status', 2, Q.UNLISTED, subject,
                                  ct.SessionKind.ENTEROSCOPY, (unit(1),), ((unit(9),),)))
                self.assertEqual(worded.question, f'Is the enteroscopy ({_quote(unit(1))}) {DONE}?')  # D281 (B6)
                self.assertEqual(worded.reason, scope_reason(unit(9), 'enteroscopy'))
                code, spec = renderer_words(R, ('44376', 1))['44376']
                self.assertEqual(code.item.message, Q.MessageId.UNLISTED_SCOPE)
                self.assertNotIn('in doubt', spec.question + spec.reason)
        found, worded = self.item('44376', TE.ileal_attempt(X(1)).build())
        self.assertEqual((found.message, found.fill.family), (Q.MessageId.DOUBT, ct.SessionKind.ENTEROSCOPY))
        self.assertTrue(worded.reason.startswith('The document leaves the enteroscopy in doubt: '))

    def test_never_for_an_act_a_held_card_another_kind_or_an_entry_of_no_kind(self):
        """D258 is about a statement naming no session held against a session's examination: an unlisted ACT is
        SYNTHETIC_ACT (the document states it, whatever its card); a doubt carded to another session the FactSet holds
        stays DOUBT, the examination its own unit speaks of (D232); a pair with an act of another kind stays DOUBT (the
        snare, as before); an entry of no kind read as a synthetic act stays DOUBT ("another act"), which may be
        another rule's possible act - XCHG's removal doubt with no card keeps 43276's DOUBT."""
        doc = TE.act_only_colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.ACT, ct.Kind.EXAMINATION, None, unit(9)))
        self.assertEqual(self.item('45385', doc.build())[0].message, Q.MessageId.SYNTHETIC_ACT)
        doc = colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, X(2), unit(5)))
        doc.session(2, ct.SessionKind.EGD)
        R = doc.build()
        witness = held(rank=2, subject=X(1), spans=(unit(5),), cause=Q.UNLISTED)
        found = Q.item((witness,), (), EV.code_facts('45385'), R)
        self.assertEqual((found.message, found.fill.family), (Q.MessageId.DOUBT, None))
        doc = colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.SNARE, None, unit(9)))
        self.assertEqual(self.item('45385', doc.build())[0].message, Q.MessageId.DOUBT)
        doc = TE.act_only_colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, None, None, unit(9)))
        R = doc.build()
        found = Q.item((held(rank=2, subject=X(1), spans=(unit(9),), cause=Q.UNLISTED),), (), EV.code_facts('45385'), R)
        self.assertEqual((found.message, found.fill.act), (Q.MessageId.DOUBT, ct.Kind.OTHER))  # row 7's witness alone
        found, worded = self.item('45385', R)  # beside it rule 4's pair with the snare ranks first: DOUBT, the snare
        self.assertEqual((found.message, found.held.subject, found.fill.act), (Q.MessageId.DOUBT, E(2), ct.Kind.SNARE))
        doc = TE.stent_placement(None)
        doc.unlisted.append(TE.stent_doubt(session=None))
        found, worded = self.item('43276', doc.build())
        self.assertEqual((found.message, found.fill.act), (Q.MessageId.DOUBT, ct.Kind.STENT_REMOVAL))

    def test_read_time_words_it_as_assess_does(self):
        """Read time (questions.item with no Raised, as before overlay's I3) names the same item as assess for the
        rule-4 pair and for the synthetic examination doubt: UNLISTED_SCOPE, the same Fill."""
        doc = TE.act_only_colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, None, unit(9)))
        for code, R in (('45378', TE.p41(card=None).build()), ('45385', doc.build())):
            with self.subTest(code=code):
                evaluation = EV.decide(code, (), R)
                assess_item = EV.item(code, (), R, evaluation)
                read_item = Q.item(evaluation.held_facts, EV.groups(code, (), R, evaluation), EV.code_facts(code), R,
                                   evaluation.supporting)
                self.assertEqual(assess_item.message, Q.MessageId.UNLISTED_SCOPE)
                self.assertEqual(read_item, assess_item)


def pouchoscopy():
    """refute-r4a-r2 A3: an enteroscopy X1 through Y1, an anatomy entry whose type is supported ileal_pouch, its
    approach supported through_pouch, its ileal reach denied whole ("The neo-terminal ileum was not reached.") and its
    completion stated incomplete - for the stoma class (44380) the route and the approach are established otherwise (two
    PROCEDURE-keyed explanations at RANK row 8) and the reach fits no class (REACH F, EXTENT-keyed, rank 14)."""
    doc = TE.Doc()
    doc.session(1, ct.SessionKind.ENTEROSCOPY, approach=sup(ct.Approach.THROUGH_POUCH, spans=(unit(4),)),
                reached=[TE.neg(ct.Extent.ILEUM, spans=(unit(7),))],
                completion=sup(ct.Completion.INCOMPLETE, spans=(unit(9),)), through=sup(TE.Y(1), spans=(unit(3),)))
    doc.entry(1, type=sup(ct.AnatomyType.ILEAL_POUCH, spans=(unit(8),)))
    doc.exam(1)
    return doc.build()


def stoma_route(approach=sup(ct.Approach.TRANSANAL, spans=(unit(4),)), through=None, entry_type=None, reached=I6):
    """D253 QX (ii): an enteroscopy X1 reaching ``reached`` (the ileum, unit 6) with ``approach``; ``through`` the
    session's through (None: not filed) and ``entry_type`` the type fact of Y1, the entry it names (None: no entry)."""
    doc = TE.Doc()
    doc.session(1, ct.SessionKind.ENTEROSCOPY, approach=approach, reached=[reached], through=through)
    if entry_type is not None:
        doc.entry(1, type=entry_type)
    doc.exam(1)
    return doc.build()


class D253Items(SimpleTestCase):
    """DECISIONS D253's questions.py half: QX (ii) - an enteroscopy route part U whose only unknown is the anatomy
    passed through is asked by the route's own question (ENTEROSCOPY_THROUGH, repair r3c of round w8r's form, mirrored,
    for the stoma and pouch classes; the oral classes' two-route doubt by ENTEROSCOPY_ROUTE, refute-r4a-r1 P2), never
    "In which procedure was the enteroscopy done?"; A3 - when every held fact on the binding is an enteroscopy
    class item with no reach and the first of them is PROCEDURE-keyed, ``item``'s for-else takes the EXTENT-keyed entry
    (mutant MX5NOEXTENT killed here)."""

    item = D246Items.item
    enteroscopy_hold = staticmethod(D246Items.enteroscopy_hold)

    def test_qx_ii_the_route_part_whose_only_unknown_is_the_anatomy_is_the_routes_own_question(self):
        """44380 (the stoma class) on an enteroscopy passed transanally (APPROACH F, an explanation at rank 8) whose
        through is not filed (ROUTE U, a question at rank 8 carrying the through's reading cause): the item is the route
        part's question - before it, PROCEDURE "In which procedure was the enteroscopy (...) done?" - now
        ENTEROSCOPY_THROUGH, the class, the reach and its words, the approach and its words. The same for a through
        naming Y1 whose type is not established (ROUTE U on the type). Through assess and the renderer's own call too.
        Restated after refute-r4a-r1 P2 of round w8r: the oral classes' two-route doubt (44360) is no longer here - its
        own question is ENTEROSCOPY_ROUTE (``test_qx_ii_the_oral_classes_two_route_doubt_*``)."""
        cases = [
            ('44380', 'through not filed', stoma_route(), ct.Attribute.THROUGH, X(1), ct.Approach.TRANSANAL,
             ct.Extent.ILEUM, unit(6)),
            ('44380', 'entry type unresolved', stoma_route(sup(ct.Approach.THROUGH_STOMA, spans=(unit(4),)),
                                                           through=sup(TE.Y(1), spans=(unit(3),)),
                                                           entry_type=unres(ct.AnatomyType.STOMA, spans=(unit(8),))),
             ct.Attribute.TYPE, TE.Y(1), ct.Approach.THROUGH_STOMA, ct.Extent.ILEUM, unit(6)),
        ]
        for code, name, R, attribute, subject, approach, reached, words in cases:
            with self.subTest(code=code, case=name):
                found, worded = self.item(code, R, self.enteroscopy_hold(code, R))
                self.assertEqual((found.message, found.held.fact, found.held.rank, found.held.kind,
                                  found.held.attribute, found.held.subject),
                                 (Q.MessageId.ENTEROSCOPY_THROUGH, 'procedure', 8, QUESTION, attribute, subject))
                self.assertNotEqual(found.held.cause, CL.CLASS_CAUSE)
                self.assertEqual((found.fill.enteroscopy_class, found.fill.reached, found.fill.words,
                                  found.fill.approach, found.fill.approach_words),
                                 (EV.catalogue.code_class(code), reached, (words,), approach, (unit(4),)))
                self.assertIn('CPT Studio could not confirm from the document the altered anatomy', worded.question)
                self.assertNotIn('In which procedure', worded.question + worded.reason)
                assessed, spec = renderer_words(R, (code, 1))[code]
                self.assertEqual(assessed.item.message, Q.MessageId.ENTEROSCOPY_THROUGH)
                self.assertNotIn('In which procedure', spec.question)

    def test_qx_ii_only_a_route_part_question_with_a_reading_cause_moves(self):
        """message_of: the route part's question carrying a reading cause on a stoma or pouch class code (44380, 44385)
        is ENTEROSCOPY_THROUGH (the through of a session, the type of an anatomy entry), and on an oral class code
        (44360, 44376: the two-route doubt, on the session's through) ENTEROSCOPY_ROUTE (refute-r4a-r1 P2 of round
        w8r); the class rule's own doubt (coding_rule:enteroscopy_class) stays ENTEROSCOPY_ROUTE (P11's documented
        stoma); the family's question and any other code's stay PROCEDURE; LOWER's stoma entry for the EUS stoma class
        stays EXAMINATION_ROUTE. Restated for DECISIONS D267 (r4a QA option (b); repair r4a of round w9r): the approach
        part's question with a reading cause - on a session's approach, any enteroscopy class - is the route's own
        question too, ENTEROSCOPY_ROUTE (before: PROCEDURE); on an anatomy entry, or for another family's code, it
        stays PROCEDURE."""
        ent, egd, eus = EV.code_facts('44380'), EV.code_facts('43235'), EV.code_facts('44406')
        pouch, jejunal, ileal = EV.code_facts('44385'), EV.code_facts('44360'), EV.code_facts('44376')
        through = held('procedure', 8, attribute=ct.Attribute.THROUGH, subject=X(1), cause='reading_unknown')
        entry_type = held('procedure', 8, attribute=ct.Attribute.TYPE, subject=TE.Y(1), cause='appraisal:unclear')
        cases = [
            (through, ent, Q.MessageId.ENTEROSCOPY_THROUGH), (entry_type, ent, Q.MessageId.ENTEROSCOPY_THROUGH),
            (dataclasses.replace(through, cause=CL.CLASS_CAUSE), ent, Q.MessageId.ENTEROSCOPY_ROUTE),
            (dataclasses.replace(through, attribute=ct.Attribute.APPROACH), ent, Q.MessageId.ENTEROSCOPY_ROUTE),
            (dataclasses.replace(through, attribute=ct.Attribute.KIND), ent, Q.MessageId.PROCEDURE),
            (dataclasses.replace(entry_type, subject=X(1)), ent, Q.MessageId.PROCEDURE),
            (through, egd, Q.MessageId.PROCEDURE),
            (dataclasses.replace(entry_type, subject=X(1)), eus, Q.MessageId.EXAMINATION_ROUTE),
            (through, pouch, Q.MessageId.ENTEROSCOPY_THROUGH), (entry_type, pouch, Q.MessageId.ENTEROSCOPY_THROUGH),
            (through, jejunal, Q.MessageId.ENTEROSCOPY_ROUTE), (through, ileal, Q.MessageId.ENTEROSCOPY_ROUTE),
            (dataclasses.replace(through, cause='appraisal:unclear'), jejunal, Q.MessageId.ENTEROSCOPY_ROUTE),
            (dataclasses.replace(through, attribute=ct.Attribute.APPROACH), jejunal, Q.MessageId.ENTEROSCOPY_ROUTE),
            (dataclasses.replace(through, attribute=ct.Attribute.APPROACH), pouch, Q.MessageId.ENTEROSCOPY_ROUTE),
            (dataclasses.replace(through, attribute=ct.Attribute.APPROACH, cause='appraisal:unclear'), ileal,
             Q.MessageId.ENTEROSCOPY_ROUTE),
            (dataclasses.replace(through, attribute=ct.Attribute.APPROACH, subject=TE.Y(1)), ileal,
             Q.MessageId.PROCEDURE),
            (dataclasses.replace(through, attribute=ct.Attribute.APPROACH), egd, Q.MessageId.PROCEDURE),
            (dataclasses.replace(through, subject=TE.Y(1)), jejunal, Q.MessageId.PROCEDURE),
        ]
        for found, code, message in cases:
            with self.subTest(attribute=found.attribute, cause=found.cause, code=code.code):
                self.assertEqual(Q.message_of(found, code), message)
        spec = wording.MESSAGES[wording.Message.ENTEROSCOPY_THROUGH]
        self.assertEqual((spec.fact, spec.kind, spec.rank), ('procedure', QUESTION, 8))

    def test_a3_procedure_keyed_class_holds_first_reach_the_extent_fallback(self):
        """refute-r4a-r2 A3: 44380 on a pouchoscopy - the route (the ileal pouch entry's type) and the approach
        explanations, PROCEDURE-keyed at rank 8, rank before the reach's explanation (EXTENT-keyed, rank 14), and no
        reached point is supported, so every held fact is an enteroscopy class item with no reach. The for-else takes
        the EXTENT-keyed entry, worded as the extent question (v1's EXTENT form) - never the first-ranked approach
        explanation (mutant MX5NOEXTENT: ENTEROSCOPY_APPROACH). Through assess too."""
        R = pouchoscopy()
        evaluation = EV.decide('44380', (), R)
        extra = tuple(CL.enteroscopy_hold('44380', evaluation.supporting, R))
        ranked = Q.ranked((*evaluation.held_facts, *extra), R)
        self.assertEqual([Q.fact_of(entry)[0].value for entry in ranked], ['procedure', 'procedure', 'extent'])
        found = EV.item('44380', (), R, evaluation, extra=extra)
        self.assertEqual((found.message, found.held.fact, found.held.kind, found.held.attribute, found.held.cause),
                         (Q.MessageId.EXTENT, 'extent', EXPLANATION, ct.Attribute.REACHED, CL.CLASS_CAUSE))
        worded = wording.build(wording.Message.EXTENT, slots(found.fill), FILLER)
        self.assertEqual(worded.question, 'Small-bowel enteroscopy: confirm the furthest extent reached.')
        assessed, spec = renderer_words(R, ('44380', 1))['44380']
        self.assertEqual((assessed.item.message, assessed.item.held), (Q.MessageId.EXTENT, found.held))
        self.assertEqual(spec.question, 'Small-bowel enteroscopy: confirm the furthest extent reached.')

    def test_qx_ii_the_oral_classes_two_route_doubt_is_enteroscopy_route(self):
        """refute-r4a-r1 P2 of round w8r: an oral class enteroscopy (44360 reaching the jejunum, 44376 the ileum) whose
        approach is supported oral and whose through - doubted or unresolved - may name Y1, an entry whose type is
        supported stoma (classes._route U, the oral classes' two-route doubt, a reading cause on the session's through).
        The round's first patch: ENTEROSCOPY_THROUGH, "passed through the mouth (...); CPT Studio could not confirm from
        the document the altered anatomy it was passed through" - the oral route stated and the altered anatomy
        presupposed, the very thing in doubt. Now the route's own question, ENTEROSCOPY_ROUTE, as the same state with
        the through supported is asked: "whether it was passed through the mouth or through the documented stoma" (the
        routes the anatomy may open, ``approaches``), the class, the reach and its words; never PROCEDURE. Through
        assess and the renderer's own call too. Restated for DECISIONS D267 (refute-r4a-r2 F5; repair r3c of round w9r's
        request R1): a through only doubted or unresolved opens the stoma's route only possibly - ``approaches`` holds
        the routes the anatomy establishes (none), ``possible_approaches`` the route it may open, worded "or possibly
        through a stoma", never "the documented stoma"; the supported through keeps "through the documented stoma"."""
        stoma = sup(ct.AnatomyType.STOMA, spans=(unit(8),))
        for code, reached, point in (('44360', J5, ct.Extent.JEJUNUM), ('44376', I6, ct.Extent.ILEUM)):
            for name, through, opened, possible, words in (
                    ('doubted', TE.doubted(TE.Y(1), spans=(unit(3),)), (), (ct.Approach.THROUGH_STOMA,),
                     'whether it was passed through the mouth or possibly through a stoma'),
                    ('unresolved', unres(TE.Y(1), spans=(unit(3),)), (), (ct.Approach.THROUGH_STOMA,),
                     'whether it was passed through the mouth or possibly through a stoma'),
                    ('supported (the class rule own doubt)', sup(TE.Y(1), spans=(unit(3),)),
                     (ct.Approach.THROUGH_STOMA,), (), 'whether it was passed through the mouth or through the '
                                                     'documented stoma')):
                with self.subTest(code=code, through=name):
                    R = stoma_route(ORAL4, through=through, entry_type=stoma, reached=reached)
                    found, worded = self.item(code, R, self.enteroscopy_hold(code, R))
                    self.assertEqual((found.message, found.held.fact, found.held.rank, found.held.kind,
                                      found.held.attribute, found.held.subject),
                                     (Q.MessageId.ENTEROSCOPY_ROUTE, 'procedure', 8, QUESTION, ct.Attribute.THROUGH,
                                      X(1)))
                    self.assertEqual((found.fill.enteroscopy_class, found.fill.reached, found.fill.words,
                                      found.fill.approaches, found.fill.possible_approaches),
                                     (EV.catalogue.code_class(code), point, (reached.spans[0],), opened, possible))
                    self.assertIn(words, worded.question)
                    if possible:
                        self.assertNotIn('documented stoma', worded.question + worded.reason)
                    for never in ('altered anatomy', 'In which procedure', 'passed through the mouth (', 'mouth ('):
                        self.assertNotIn(never, worded.question + worded.reason)
                    assessed, spec = renderer_words(R, (code, 1))[code]
                    self.assertEqual(assessed.item.message, Q.MessageId.ENTEROSCOPY_ROUTE)
                    self.assertNotIn('altered anatomy', spec.question + spec.reason)


class RefutedW8rItems(SimpleTestCase):
    """refute-r4a-r1 of round w8r, questions.py's half: P3 - a digital examination's sentence (FINAL 5.6 E13: no
    session's examination) is never quoted as the session's examination, nor its device named - UNLISTED_SCOPE's words
    (a statement with no card) and the carded rule-4 pair's DOUBT; P4 - D254 rule 2 in SAME_DUCT's two act slots (an act
    no kind names is "another act", never "the stent removal"); P8 - 3.2.6 rule 4's pair is found by its spans AND its
    cause (DV4), so a relation's doubt on the same spans keeps its own form."""

    item = D232Sentences.item

    def test_p3_unlisted_scope_never_quotes_the_digital_examination(self):
        """refute-r4a-r1 P3: the DRE E1 filed as the colonoscopy's examination (device manual), the snare E2, and pass
        2's ONE unlisted doubt or denial of kind examination with no card. Restated for DECISIONS D265 (repair r4a of
        round w9r: the DRE never takes the binding, and an examination statement never pairs with it): 45378's item is
        the item of the same FactSet without E1 - its group has no other positive candidate, so 4.6's own item, the
        code-level not-documented question (before: rule 4's pair with E1, UNLISTED_SCOPE). Beside an endoscopic
        examination E3 of X1, with the kept evidence on E1's unit, the binding is E3 - UNLISTED_SCOPE quoting E3, the
        session's own examination - as without E1; the DRE's sentence is never quoted."""
        for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.DENIAL):
            with self.subTest(what=what):
                R = TE.digital_colonoscopy(what, None).build()
                found, worded = self.item('45378', R)
                self.assertEqual((found.message, found.held.subject, found.fill.words),
                                 (Q.MessageId.NOT_DOCUMENTED, None, ()))
                self.assertEqual(found, EV.item('45378', (), without_events(R, E(1)),
                                                EV.decide('45378', (), without_events(R, E(1)))))
                self.assertNotIn(_quote(unit(1)), worded.question + worded.reason)
                doc = TE.digital_colonoscopy(what, None)
                doc.exam(3)
                R = doc.build()
                found, worded = self.item('45378', R, (unit(1),))
                self.assertEqual((found.message, found.held.subject, found.fill.words, found.fill.unlisted_what),
                                 (Q.MessageId.UNLISTED_SCOPE, E(3), (unit(3),), what))
                gone = without_events(R, E(1))
                self.assertEqual(found, EV.item('45378', (unit(1),), gone, EV.decide('45378', (unit(1),), gone)))
                self.assertNotIn(_quote(unit(1)), worded.question + worded.reason)

    def test_p3_the_carded_pair_never_names_the_digital_examination_as_the_session(self):
        """The same with the statement carded X1 (D232: the card names the session E1 is filed in). Restated for
        DECISIONS D265 and D266: with the DRE the only positive candidate, the item of the same FactSet without it
        (the code-level not-documented question; before: the rule-4 pair's DOUBT on E1, the session's words); beside
        E3, the carded DOUBT on E3 - its words, the statement quoted, and the entry's nature (``unlisted_what``: a
        denial is worded as a statement that the colonoscopy was not done, never "leaves ... in doubt"). A colonoscopy
        whose own examination is E1 (p41, carded X1) keeps E1's words (D232, unchanged)."""
        for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.DENIAL):
            with self.subTest(what=what):
                R = TE.digital_colonoscopy(what, X(1)).build()
                found, worded = self.item('45378', R)
                self.assertEqual((found.message, found.held.subject, found.fill.words, found.fill.device),
                                 (Q.MessageId.NOT_DOCUMENTED, None, (), None))
                for never in ('manual', _quote(unit(1))):
                    self.assertNotIn(never, worded.question + worded.reason)
                doc = TE.digital_colonoscopy(what, X(1))
                doc.exam(3)
                R = doc.build()
                found, worded = self.item('45378', R, (unit(1),))
                self.assertEqual((found.message, found.held.subject, found.fill.words, found.fill.device,
                                  found.fill.statements, found.fill.unlisted_what),
                                 (Q.MessageId.DOUBT, E(3), (unit(3),), None, ((unit(9),),), what))
                gone = without_events(R, E(1))
                self.assertEqual(found, EV.item('45378', (unit(1),), gone, EV.decide('45378', (unit(1),), gone)))
                self.assertEqual('in doubt' in worded.reason, what is ct.UnlistedWhat.DOUBT)
                for never in ('manual', _quote(unit(1))):
                    self.assertNotIn(never, worded.question + worded.reason)
        found, worded = self.item('45378', TE.p41(card=X(1)).build())
        self.assertEqual((found.message, found.held.subject, found.fill.words), (Q.MessageId.DOUBT, E(1), (unit(1),)))

    def test_p4_same_duct_names_a_counterpart_no_kind_names_another_act(self):
        """refute-r4a-r1 P4 (D254 rule 2 in every Fill act slot): XCHG's two-act duct question beside a filed
        counterpart E5 whose kind is silent or contradicted (stent removal or biopsy) - SAME_DUCT's act Kind.OTHER, "Were
        another act (...) and the stent placement (...) done in the same duct?", no exchange reason (the round's first
        patch: "the stent removal", a kind no fact gives it); E5 a stent removal keeps it (control). Through assess and
        the renderer's own call too."""
        for name, kind, act in (('silent', SILENT, ct.Kind.OTHER),
                                ('contradicted', contra(ct.Kind.STENT_REMOVAL, ct.Kind.BIOPSY, spans=(unit(5),)),
                                 ct.Kind.OTHER),
                                ('stent removal', sup(ct.Kind.STENT_REMOVAL), ct.Kind.STENT_REMOVAL)):
            with self.subTest(kind=name):
                doc = TE.stent_placement(None)
                doc.act(5, kind)
                R = doc.build()
                found, worded = self.item('43274', R, (unit(2),))
                self.assertEqual((found.message, found.held.subject, found.fill.act, found.fill.whole),
                                 (Q.MessageId.SAME_DUCT, E(5), act, ct.Kind.STENT))
                assessed, spec = renderer_words(R, ('43274', 2))['43274']
                self.assertEqual(assessed.item.fill.act, act)
                if act is ct.Kind.OTHER:
                    self.assertTrue(spec.question.startswith('Were another act ('))
                    self.assertNotIn('stent exchange', spec.reason)
                    self.assertNotIn('the stent removal', spec.question + spec.reason)

    def test_p4_the_known_side_and_an_unlisted_counterpart_of_no_kind(self):
        """The whole slot too: the placement's duct not established and E5's supported (the placement the act, E5 the
        whole), E5's kind silent - whole Kind.OTHER; a kept unlisted act of no kind as the counterpart - act Kind.OTHER
        ("another act", its own unit), while one of kind stent removal keeps it."""
        doc = TE.stent_placement(dict(duct=sup(ct.Duct.BILIARY)), duct=None)
        doc.act(5, SILENT, duct=sup(ct.Duct.BILIARY))
        found, worded = self.item('43274', doc.build())
        self.assertEqual((found.message, found.held.subject, found.fill.act, found.fill.whole),
                         (Q.MessageId.SAME_DUCT, E(2), ct.Kind.STENT, ct.Kind.OTHER))
        for kind, act in ((None, ct.Kind.OTHER), (ct.Kind.STENT_REMOVAL, ct.Kind.STENT_REMOVAL)):
            with self.subTest(unlisted_kind=kind):
                doc = TE.stent_placement(None)
                doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.ACT, kind, X(1), unit(5)))
                found, worded = self.item('43274', doc.build(), (unit(2),))
                self.assertEqual((found.message, found.fill.act, found.fill.words),
                                 (Q.MessageId.SAME_DUCT, act, (unit(5),)))
                self.assertEqual(worded.question.startswith('Were another act ('), act is ct.Kind.OTHER)

    def test_p8_a_relations_doubt_on_the_pairs_spans_keeps_its_own_form(self):
        """refute-r4a-r1 P8 (DV4: ``_unlisted_pair`` matches the pair's cause, as ``_statement_of`` reads a relation's):
        the colonoscopy's examination E1 of an unresolved status, a filed denial E3 of the colonoscopy ("The colonoscopy
        was not performed.", established: a DOUBT relation with E1, rank 2, cause relation:doubt) and a kept unlisted
        doubt of kind examination with no card on E3's own unit - the relation's hold and rule 4's pair record the same
        spans. 45378's item is the relation's hold, worded DOUBT quoting the filed statement; without the cause match it
        would be taken for rule 4's pair and asked as UNLISTED_SCOPE (mutant N5 of the refutation)."""
        doc = colonoscopy(snare=False)
        doc.exam(1, status=unres(Status.PERFORMED))
        TE.denial_event(doc, number=3, kind=ct.Kind.EXAMINATION)
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, None, unit(3)))
        R = doc.build()
        evaluation = EV.decide('45378', (), R)
        relation = [entry for entry in evaluation.held_facts if entry.cause == 'relation:doubt']
        unlisted = [entry for entry in evaluation.held_facts if entry.cause == Q.UNLISTED]
        self.assertEqual(len(relation), 1)
        self.assertEqual([entry.spans for entry in unlisted], [relation[0].spans])
        found, worded = self.item('45378', R)
        self.assertEqual((found.held, found.message, found.fill.statements),
                         (relation[0], Q.MessageId.DOUBT, ((unit(3),),)))
        self.assertNotIn('which names no procedure session', worded.reason)


class D265Items(SimpleTestCase):
    """DECISIONS D265's questions.py half (repair r4a of round w9r; refute-r4a-r2 F1; r4a QD2, held as built by D271):
    the DRE's sentence is never quoted as "the colonoscopy" and its device never named as the session's examination's -
    also where the hold rests on the digital examination's own rows 2-5, read on another act's row 7: the item names
    the session's examination by its service with the words of the session's examination that may be quoted (an
    endoscopic examination possibly done on the date of service), else none. The binding and the grids:
    tests/v2/test_evaluate.py D265DigitalNeverWords."""

    item = D232Sentences.item

    def test_qd2_the_digital_examinations_own_rows_never_name_it_as_the_session(self):
        """QD2's input: a colonoscopy, E1 the DRE (device manual) whose status is unresolved or doubted, or whose date
        relation or performer is open, and the snare E2. Restated for DECISIONS D280.1 (step f3w; build list B1): the
        DRE's device is SUPPORTED manual, so it is established as a digital examination and row 7 reads none of it -
        each of the eight rows is READY, with no held fact and no item, exactly the same document without the DRE line
        (before: 45385 held, its item the colonoscopy named by its service). Through the renderer's own call too. The
        claimed-device rows keep QD2's hold, worded by D280.3: D280ResidualItems."""
        for name, over in (('status unresolved', dict(status=unres(Status.PERFORMED))),
                           ('status doubted', dict(status=doubted(Status.PERFORMED))),
                           ('date open', dict(date=unres(TE.ON))), ('performer open', dict(performer=unres(TE.TEAM)))):
            for beside in (False, True):
                with self.subTest(dre=name, beside=beside):
                    doc = colonoscopy()
                    doc.exam(1, device=sup(ct.Device.MANUAL), **over)
                    if beside:
                        doc.exam(3)
                    R = doc.build()
                    evaluation = EV.decide('45385', (), R)
                    self.assertEqual((evaluation.supporting, evaluation.held_facts), ((E(2),), ()))
                    self.assertIsNone(EV.item('45385', (), R, evaluation))
                    assessed, spec = renderer_words(R, ('45385', 2))['45385']
                    without, _ = renderer_words(without_events(R, E(1)), ('45385', 2))['45385']
                    self.assertEqual((assessed.status.value, assessed.held_facts, assessed.item, spec),
                                     ('ready', (), None, None))
                    self.assertEqual((without.status.value, without.held_facts), ('ready', ()))

    def test_f1_the_claimed_device_never_words_the_session_examination_question(self):
        """refute-r4a-r2 F1: the DRE alone, its device claiming manual without establishing it (unresolved, doubted,
        contradicted) - before, "Was the colonoscopy (<the DRE's sentence>) done on the date of service?" (its open
        device row at the status row). Through engine/assess and the renderer's own call, 45378 kept on the DRE's unit:
        the question and the reason of the same document without the DRE line (the code-level not-documented
        question)."""
        for name, device in (('unresolved', unres(ct.Device.MANUAL)), ('doubted', doubted(ct.Device.MANUAL)),
                             ('contradicted', contra(ct.Device.MANUAL, ct.Device.ENDOSCOPE))):
            with self.subTest(device=name):
                worded = []
                for dre in (True, False):
                    found, spec = renderer_words(TE.dre_alone(device=device, dre=dre).build(), ('45378', 1))['45378']
                    worded.append((found.item, spec.question, spec.reason))
                self.assertEqual(worded[0], worded[1])
                self.assertEqual(worded[0][0].message, Q.MessageId.NOT_DOCUMENTED)


class D266Quotes(SimpleTestCase):
    """DECISIONS D266 (repair r4a of round w9r; refute-r4a-r2 F2; refute-r3c-r1 F3; r4a-2 Q2; TRIAGE G1-03, G2-16):
    UNLISTED_SCOPE and the carded DOUBT quote an examination statement only when that examination is possibly done on
    the date of service - not of another date, not planned, not by another performer, not negated - else the question
    names the examination by its service with no quote; and ``unlisted_what`` names the entry's nature for a carded
    entry as for one with no card, so step r3c's DOUBT words a denial as a denial."""

    item = D232Sentences.item

    STATES = (('done', {}, True), ('status unresolved', dict(status=unres(Status.PERFORMED)), True),
              ('begun', dict(status=sup(Status.ATTEMPTED_NOT_COMPLETED)), True),
              ('date open', dict(date=unres(TE.ON)), True), ('performer open', dict(performer=unres(TE.TEAM)), True),
              ('date negated', dict(date=TE.neg(TE.ON)), False), ('performer negated', dict(performer=TE.neg(TE.TEAM)),
                                                                   False))

    def test_the_held_examination_is_quoted_only_when_possibly_done_today(self):
        """The colonoscopy's examination E1 in each state, beside pass 2's unlisted doubt or denial of kind examination
        with no card (UNLISTED_SCOPE) or carded X1 (the carded DOUBT): E1's sentence quoted when it is possibly done on
        the date of service (done, begun, its status, date or performer open), never when its date or its performer is
        established otherwise (before: quoted, the QP2 mechanism - "not documented", the truthful answer about the
        quoted sentence, excludes 45378); the entry's nature in ``unlisted_what``, carded or not."""
        for name, over, quoted in self.STATES:
            for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.DENIAL):
                for card, message in ((None, Q.MessageId.UNLISTED_SCOPE), (X(1), Q.MessageId.DOUBT)):
                    with self.subTest(examination=name, what=what, card=card):
                        doc = colonoscopy(snare=False)
                        doc.exam(1, **over)
                        doc.unlisted.append(TE.unlisted(what, ct.Kind.EXAMINATION, card, unit(9)))
                        found, worded = self.item('45378', doc.build())
                        self.assertEqual((found.message, found.held.subject, found.fill.words, found.fill.unlisted_what,
                                          found.fill.device),
                                         (message, E(1), (unit(1),) if quoted else (), what, None))
                        self.assertEqual(_quote(unit(1)) in worded.question, quoted)

    def test_beside_it_the_sessions_examination_possibly_done_today_is_quoted(self):
        """E1's date established otherwise beside E3, the colonoscopy's examination done, 45378 kept on E1's unit (E1
        bound): the held session's examination quoted is E3, never E1 - UNLISTED_SCOPE and the carded DOUBT alike."""
        for card, message in ((None, Q.MessageId.UNLISTED_SCOPE), (X(1), Q.MessageId.DOUBT)):
            with self.subTest(card=card):
                doc = colonoscopy(snare=False)
                doc.exam(1, date=TE.neg(TE.ON))
                doc.exam(3)
                doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, card, unit(9)))
                found, worded = self.item('45378', doc.build(), (unit(1),))
                self.assertEqual((found.message, found.held.subject, found.fill.words), (message, E(1), (unit(3),)))
                self.assertNotIn(_quote(unit(1)), worded.question)

    def test_a_synthetic_examination_doubt_never_quotes_an_examination_of_another_occasion(self):
        """UNLISTED_SCOPE for a synthetic examination act's doubt about the held session (row 7's or step 4c's witness,
        held fact performed_status rank 2, cause unlisted, its subject the session): the session's examination is
        quoted only when possibly done on the date of service - "Colonoscopy in 2019 was normal." filed as X1's
        examination never (before: quoted, refute-r4a-r2 F2's mechanism), a done one always."""
        for name, over, quoted in (('earlier', dict(date=sup(TE.EARLIER)), False),
                                   ('planned', dict(status=sup(Status.PLANNED)), False),
                                   ('negated', dict(status=TE.neg(Status.PERFORMED)), False), ('done', {}, True)):
            with self.subTest(examination=name):
                doc = colonoscopy(snare=False)
                doc.exam(1, **over)
                doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, None, unit(9)))
                R = doc.build()
                witness = held(rank=2, subject=X(1), spans=(unit(9),), cause=Q.UNLISTED)
                found = Q.item((witness,), (), EV.code_facts('45378'), R)
                self.assertEqual((found.message, found.fill.words, found.fill.statements, found.fill.unlisted_what),
                                 (Q.MessageId.UNLISTED_SCOPE, (unit(1),) if quoted else (), ((unit(9),),),
                                  ct.UnlistedWhat.DOUBT))

    def test_f2s_grid_never_quotes_an_examination_of_another_occasion_or_the_dre(self):
        """refute-r4a-r2 F2's grid (384 rows quoting E2, planned or of an earlier date, as the colonoscopy asked
        "documented as done on the date of service"): E2 planned or earlier, every unlisted statement (doubt or denial,
        no card or carded X1), every DRE - claiming or none -, both session slots, the snare or not, both reaches and
        every kept unit, through engine/assess: no UNLISTED_SCOPE or DOUBT item quotes E2 or the DRE, and every item is
        the same FactSet's without the DRE (D265)."""
        rows = 0
        for dre, where, other, snare, statement, reach, kept in itertools.product(
                ('none',) + TE.DRE_CLAIMING, TE.DRE_SESSIONS, ('planned', 'earlier'), (False, True),
                ('doubt_nocard', 'denial_nocard', 'doubt_X1', 'denial_X1'), TE.DRE_REACHES, TE.DRE_KEPT):
            if dre == 'none' and where == 'silent':
                continue
            R = TE.dre_grid(dre, where, other, snare, statement, reach)
            found = TE.assessed(R, *TE.dre_codes(snare, kept))
            without = TE.assessed(TE.dre_grid('none', 'X1', other, snare, statement, reach), *TE.dre_codes(snare, kept))
            for code, (status, item) in found.items():
                rows += 1
                with self.subTest(shape=(dre, where, other, snare, statement, reach, kept), code=code):
                    if item is not None and item.message in (Q.MessageId.UNLISTED_SCOPE, Q.MessageId.DOUBT):
                        self.assertFalse({unit(1), unit(2)} & set(item.fill.words))
                    self.assertEqual((status, item), without[code])
        self.assertEqual(rows, 1152 + 576)

    def test_g2_16_a_denial_carded_or_not_is_worded_as_a_denial(self):
        """refute-r3c-r1 F3 = r4a-2 Q2 (TRIAGE G2-16), its three inputs through the renderer's own call: (i) 45385 on
        the snare beside a kept unlisted denial carded X1, of no kind or kind snare; (ii) 45378 beside a kindless denial
        carded X1 (p41's); (iii) 45385 beside a denial of kind snare with no card. Each a DOUBT on the act with
        ``unlisted_what`` DENIAL - restated for D281 (step f3w; build list B5, G3-10): "The document states <the denial>, a
        statement that an act was not done; CPT Studio could not confirm from the document whether it is about <the act>"
        (before: "The document states that <the act> was not done: <the denial>"), never "leaves ... in doubt" (before
        that: the doubt form). The same entry told as a doubt keeps it (``unlisted_what`` DOUBT)."""
        cases = []
        for kind in (None, ct.Kind.SNARE):
            doc = colonoscopy()
            doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DENIAL, kind, X(1), unit(9)))
            cases.append((f'(i) kind {kind}', doc.build(), ('45385', 2), E(2), 'the snare removal'))
        cases.append(('(ii)', TE.p41(ct.UnlistedWhat.DENIAL, X(1), kind=None).build(), ('45378', 1), E(1),
                      'the colonoscopy'))
        doc = colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DENIAL, ct.Kind.SNARE, None, unit(9)))
        cases.append(('(iii)', doc.build(), ('45385', 2), E(2), 'the snare removal'))
        for name, R, code, subject, act in cases:
            with self.subTest(case=name):
                found, spec = renderer_words(R, code)[code[0]]
                self.assertEqual((found.item.message, found.item.held.subject, found.item.fill.unlisted_what),
                                 (Q.MessageId.DOUBT, subject, ct.UnlistedWhat.DENIAL))
                head, middle, tail = spec.reason.partition('”, a statement that an act was not done; CPT Studio could '
                                                           'not confirm from the document whether it is about ')
                self.assertTrue(middle and head.startswith('The document states “'), spec.reason)
                self.assertTrue(tail.startswith(act) and tail.endswith('.'), spec.reason)  # the act as its form names it
                for never in ('in doubt', 'leaves', 'was not done: ', f'that {act} was not done'):
                    self.assertNotIn(never, spec.reason)
        doc = colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.SNARE, X(1), unit(9)))
        found, spec = renderer_words(doc.build(), ('45385', 2))['45385']
        self.assertEqual((found.item.message, found.item.fill.unlisted_what),
                         (Q.MessageId.DOUBT, ct.UnlistedWhat.DOUBT))
        self.assertTrue(spec.reason.startswith('The document leaves the snare removal'))


class D267Items(SimpleTestCase):
    """DECISIONS D267's r4a half (repair r4a of round w9r; refute-5c-r1 P2, r4a-2 Q1 QK, refute-r4a-r2 F5, r4a QA):
    act_kind gives Kind.OTHER for every kind that is not SUPPORTED, so a conflict over such an act is keyed
    conflict:other; the Fill marks a route only possibly opened with step r3c's possible-route marker; and an
    enteroscopy approach part whose only unknown is the route is asked by ENTEROSCOPY_ROUTE, never PROCEDURE."""

    item = D232Sentences.item

    def test_act_kind_gives_kind_other_for_every_kind_not_supported(self):
        """refute-5c-r1 P2's four inputs - the snare E2's kind negated, unresolved with its state negated, doubted
        between snare and biopsy, unresolved - and a contradicted and a silent kind: Kind.OTHER, "another act" (before:
        the snare for the first four, the kind the document denies for the first, and the code's group's first kind
        for the last two); an item that names E2 names it "another act", never "the snare removal" (a negated or other
        kind is no candidate of the snare: the code-level not-documented question names the code's own kind, true of
        it). A supported kind is its catalogue kind, a supported other is Kind.OTHER, and no act is the code's group's
        first kind."""
        group = (ct.Kind.SNARE,)
        for name, kind in (('negated', TE.neg(ct.Kind.SNARE)),
                           ('unresolved, state negated', dataclasses.replace(unres(ct.Kind.SNARE),
                                                                            state=ct.FactState.NEGATED)),
                           ('doubted', doubted(ct.Kind.SNARE, ct.Kind.BIOPSY)), ('unresolved', unres(ct.Kind.SNARE)),
                           ('contradicted', contra(ct.Kind.SNARE, ct.Kind.BIOPSY)), ('silent', SILENT),
                           ('other', sup(ct.Kind.OTHER))):
            with self.subTest(kind=name):
                R = colonoscopy(kind=kind).build()
                self.assertIs(Q.act_kind(R, E(2), group), ct.Kind.OTHER)
                found, worded = self.item('45385', R)
                if found.held.subject == E(2):  # a contradicted kind's conflict names what was done, no act
                    self.assertIs(found.fill.act, ct.Kind.OTHER)
                    self.assertNotIn('snare removal', worded.question + worded.reason)
                else:
                    self.assertEqual((found.message, found.held.subject), (Q.MessageId.NOT_DOCUMENTED, None))
        doc = colonoscopy()
        doc.act(3, ct.Kind.CLIP, purpose=sup(ct.Purpose.HEMOSTASIS))
        R = doc.build()
        self.assertEqual((Q.act_kind(R, E(2), group), Q.act_kind(R, E(3), group), Q.act_kind(R, None, group),
                          Q.act_kind(R, None, ())), (ct.Kind.SNARE, ct.Kind.BLEEDING_CONTROL, ct.Kind.SNARE, None))

    def test_qk_a_conflict_over_an_act_no_kind_names_is_keyed_conflict_other(self):
        """r4a-2 Q1 (QK) option (b): the snare E2 of a silent kind, its status contradicted (performed, planned): the
        held fact conflict:other (before: conflict:snare - "the snare removal" beside "another act" for one act), the
        item's act Kind.OTHER; and a relation's conflict over it - "No polyp was removed." (a snare denial, all of its
        kind, today) beside the act of silent kind performed - conflict:other too. Through the renderer's own call:
        "another act", never "the snare removal"."""
        doc = colonoscopy(kind=SILENT)
        TE.denial_event(doc, number=3, kind=ct.Kind.SNARE)
        for name, R, cause in (('own status', colonoscopy(kind=SILENT, status=contra(Status.PERFORMED, Status.PLANNED))
                                .build(), 'reading_contradicted'), ('relation', doc.build(), 'relation:contradiction')):
            with self.subTest(conflict=name):
                evaluation = EV.decide('45385', (), R)
                conflicts = [entry for entry in evaluation.held_facts if entry.fact.startswith('conflict:')]
                self.assertEqual([(entry.fact, entry.cause) for entry in conflicts], [('conflict:other', cause)])
                found, worded = self.item('45385', R)
                self.assertEqual((found.held.fact, found.fill.act), ('conflict:other', ct.Kind.OTHER))
                assessed, spec = renderer_words(R, ('45385', 2))['45385']
                self.assertEqual(assessed.item.held.fact, 'conflict:other')
                self.assertIn('another act', spec.question)
                self.assertNotIn('snare removal', spec.question + spec.reason)

    def test_f5_a_route_only_possibly_opened_is_marked_possible(self):
        """refute-r4a-r2 F5: 44360 (and 44376), the approach supported oral, reaching the jejunum (the ileum), its
        through doubted or unresolved naming Y1, an entry whose type is silent: ENTEROSCOPY_ROUTE with no established
        route (``approaches``) and the pouch and the stoma only possible (``possible_approaches``: step r3c's marker) -
        "... or possibly through a pouch or a stoma", never "the documented pouch" or "the documented stoma". Through
        engine/assess and the renderer's own call."""
        for code, reached in (('44360', J5), ('44376', I6)):
            for name, through in (('doubted', TE.doubted(TE.Y(1), spans=(unit(3),))),
                                  ('unresolved', unres(TE.Y(1), spans=(unit(3),)))):
                with self.subTest(code=code, through=name):
                    doc = TE.Doc()
                    doc.session(1, ct.SessionKind.ENTEROSCOPY, approach=ORAL4, reached=[reached], through=through)
                    doc.exam(1)
                    doc.entry(1)
                    R = doc.build()
                    found, spec = renderer_words(R, (code, 1))[code]
                    self.assertEqual((found.item.message, found.item.fill.approaches,
                                      found.item.fill.possible_approaches),
                                     (Q.MessageId.ENTEROSCOPY_ROUTE, (),
                                      (ct.Approach.THROUGH_STOMA, ct.Approach.THROUGH_POUCH)))
                    self.assertIn('passed through the mouth or possibly through a pouch or a stoma', spec.question)
                    self.assertNotIn('documented', spec.question.replace('The documented enteroscopy', ''))

    def test_qa_the_approach_part_is_asked_by_the_routes_own_question(self):
        """r4a QA option (b), D253 QX (ii): 44376 on an enteroscopy reaching the ileum whose approach is silent, and
        44380 (the stoma class) on one reaching the ileum through a stoma entry with its approach silent - the approach
        part U, a reading cause, PROCEDURE-keyed at rank 8: ENTEROSCOPY_ROUTE, "whether it was passed through the mouth
        or ...", never "In which procedure was the enteroscopy done?" (before: PROCEDURE). Through engine/assess and
        the renderer's own call."""
        for code, through, entry_type in (('44376', None, None),
                                          ('44380', sup(TE.Y(1), spans=(unit(3),)), sup(ct.AnatomyType.STOMA,
                                                                                        spans=(unit(8),)))):
            with self.subTest(code=code):
                R = stoma_route(SILENT, through=through, entry_type=entry_type)
                found, worded = self.class_item(code, R)
                self.assertEqual((found.message, found.held.fact, found.held.rank, found.held.attribute,
                                  found.held.subject), (Q.MessageId.ENTEROSCOPY_ROUTE, 'procedure', 8,
                                                        ct.Attribute.APPROACH, X(1)))
                self.assertIn('whether it was passed through the mouth or', worded.question)
                self.assertNotIn('In which procedure', worded.question + worded.reason)
                assessed, spec = renderer_words(R, (code, 1))[code]
                self.assertEqual(assessed.item.message, Q.MessageId.ENTEROSCOPY_ROUTE)
                self.assertNotIn('In which procedure', spec.question)

    def class_item(self, code, R):
        evaluation = EV.decide(code, (), R)
        extra = tuple(CL.enteroscopy_hold(code, evaluation.supporting, R))
        found = EV.item(code, (), R, evaluation, extra=extra)
        worded = wording.build(wording.Message(found.message.value), slots(found.fill), FILLER)
        return found, worded


class SideSlotW4(SimpleTestCase):
    """DECISIONS D271 (TRIAGE G3-01; refute-r4a-r2 F4): ``_side_slot`` names an unlisted counterpart "another act" only
    when EVERY possibly-performed entry with the side's units names no kind - mutant W4 (``all`` -> ``any``) survived
    every test before. Two kept unlisted entries on the removal's unit 5, one of no kind and one of kind stent removal
    (either order), beside the filed placement E2: SAME_DUCT names the counterpart by the stent kind, never "another
    act"; the entry of no kind alone is "another act"."""

    item = D232Sentences.item

    def test_two_entries_on_the_sides_units_name_it_by_the_kind_one_names(self):
        for order in ((None, ct.Kind.STENT_REMOVAL), (ct.Kind.STENT_REMOVAL, None)):
            with self.subTest(order=order):
                doc = TE.stent_placement(None)
                for kind in order:
                    doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.ACT, kind, X(1), unit(5)))
                found, worded = self.item('43274', doc.build(), (unit(2),))
                self.assertEqual((found.message, found.fill.words), (Q.MessageId.SAME_DUCT, (unit(5),)))
                self.assertIs(found.fill.act, ct.Kind.STENT_REMOVAL)
                self.assertFalse(worded.question.startswith('Were another act ('), worded.question)
        doc = TE.stent_placement(None)
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.ACT, None, X(1), unit(5)))
        found, worded = self.item('43274', doc.build(), (unit(2),))
        self.assertEqual((found.message, found.fill.act), (Q.MessageId.SAME_DUCT, ct.Kind.OTHER))


class D254Fill(SimpleTestCase):
    """DECISIONS D254's questions.py half: rule 2 - an act no kind names reaches the Fill's act slots as Kind.OTHER
    ("another act", as 5c's item_slots names it), never the code's group's kind; rule 3's mapping - an
    ENTEROSCOPY_APPROACH item with no supported approach (refute-r4a-r2 A1: a route established only by a denial) gives
    the class form naming no route, worded by the renderer."""

    item = D246Items.item
    enteroscopy_hold = staticmethod(D246Items.enteroscopy_hold)

    def test_rule_2_an_act_no_kind_names_is_another_act(self):
        """The snare E2's kind silent, or unresolved as other: 45385's status item names "another act" (the first
        patch: "the snare removal", the code's group's kind); the colonoscopy's examination E1 of a silent kind: 45378's
        item names "another act"; an unlisted entry of no kind on the evidence: unlisted_kind Kind.OTHER. A code-level
        hold keeps the code's group (no act). Restated for DECISIONS D267 (repair r4a of round w9r): a doubted snare is
        "another act" too - every kind that is not SUPPORTED (before: "the snare removal", its claimed kind)."""
        other = fact(ct.Result.UNRESOLVED, ct.Kind.OTHER, ct.FactState.SUPPORTED, options=(ct.Kind.SNARE,),
                        reasons=(ct.Reason.APPRAISAL_UNCLEAR,))
        for name, kind in (('silent', SILENT), ('other, unresolved', other)):
            with self.subTest(kind=name):
                found, worded = self.item('45385', colonoscopy(kind=kind).build(), lambda supporting: ())
                self.assertEqual((found.message, found.held.subject, found.fill.act),
                                 (Q.MessageId.STATUS, E(2), ct.Kind.OTHER))
                self.assertTrue(worded.question.startswith('Was another act (cold snare) at the sigmoid colon ('))
                self.assertNotIn('snare removal', worded.question + worded.reason)
        doc = colonoscopy()
        doc.act(1, SILENT)
        found, worded = self.item('45378', doc.build(), lambda supporting: ())
        self.assertEqual((found.held.subject, found.fill.act), (E(1), ct.Kind.OTHER))
        self.assertEqual(worded.question, f'Was another act ({_quote(unit(1))}) done on the date of service?')
        doc = colonoscopy(snare=False)
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, None, X(1), unit(1)))
        evaluation = EV.decide('45378', (unit(1),), doc.build())
        found = EV.item('45378', (unit(1),), doc.build(), evaluation)
        self.assertEqual((found.message, found.fill.unlisted_kind), (Q.MessageId.UNLISTED_EVIDENCE, ct.Kind.OTHER))
        found, _ = self.item('45385', colonoscopy(kind=doubted(ct.Kind.SNARE, ct.Kind.BIOPSY)).build(),
                             lambda supporting: ())
        self.assertEqual(found.fill.act, ct.Kind.OTHER)  # D267: a doubted kind is not established - "another act"
        found, _ = self.item('45385', colonoscopy(snare=False).build(), lambda supporting: ())
        self.assertEqual((found.message, found.fill.act), (Q.MessageId.NOT_DOCUMENTED, ct.Kind.SNARE))
        R = colonoscopy(kind=SILENT).build()
        code, spec = renderer_words(R, ('45385', 2))['45385']
        self.assertEqual(code.item.fill.act, ct.Kind.OTHER)
        self.assertTrue(spec.question.startswith('Was another act'))

    def test_rule_2_the_act_slot(self):
        """``_act_slot``: an act's catalogue kind (a clip for hemostasis is the bleeding control it is); an act of kind
        other, silent or contradicted (no value) Kind.OTHER; no act the code's group's first kind (or none)."""
        doc = colonoscopy()
        doc.act(3, ct.Kind.CLIP, purpose=sup(ct.Purpose.HEMOSTASIS))
        doc.act(4, ct.Kind.OTHER)
        doc.act(5, SILENT)
        doc.act(6, contra(ct.Kind.SNARE, ct.Kind.BIOPSY))
        R = doc.build()
        group = (ct.Kind.SNARE,)
        cases = {E(2): ct.Kind.SNARE, E(3): ct.Kind.BLEEDING_CONTROL, E(4): ct.Kind.OTHER, E(5): ct.Kind.OTHER,
                 E(6): ct.Kind.OTHER, None: ct.Kind.SNARE}
        for event, kind in cases.items():
            with self.subTest(event=event):
                self.assertEqual(Q._act_slot(R, event, group), kind)
        self.assertIsNone(Q._act_slot(R, None, ()))
        for event in (E(4), E(5), E(6)):  # D267: act_kind gives Kind.OTHER for an act no kind names (overlay reads it)
            with self.subTest(act_kind=event):
                self.assertIs(Q.act_kind(R, event, group), ct.Kind.OTHER)

    def test_rule_3_a1s_four_shapes_name_no_route(self):
        """refute-r4a-r2 A1: an enteroscopy approach established only by a denial ("The enteroscope was not passed
        orally." for 44360, 44376 and 44361 on a biopsy; "The scope was not passed through the stoma." for 44380 beside
        a supported stoma entry) - APPROACH F, the only held fact. The item is ENTEROSCOPY_APPROACH with no approach and
        no approach words, so wording gives the class form naming no route ("the route this code describes"); the
        renderer words it (the final tree of round w7r refused all four: "enteroscopy_approach needs the slot
        approach")."""
        def shape(approach, reached, biopsy=False, stoma=False):
            doc = TE.Doc()
            doc.session(1, ct.SessionKind.ENTEROSCOPY, approach=approach, reached=[reached],
                        through=sup(TE.Y(1), spans=(unit(3),)) if stoma else None)
            if stoma:
                doc.entry(1, type=sup(ct.AnatomyType.STOMA, spans=(unit(8),)))
            doc.exam(1)
            if biopsy:
                doc.act(2, ct.Kind.BIOPSY, places=[sup(ct.Landmark.JEJUNUM)])
            return doc.build()
        oral = TE.neg(ct.Approach.ORAL, spans=(unit(4),))
        cases = [('44360', 1, shape(oral, J5), ct.Extent.JEJUNUM), ('44376', 1, shape(oral, I6), ct.Extent.ILEUM),
                 ('44361', 2, shape(oral, J5, biopsy=True), ct.Extent.JEJUNUM),
                 ('44380', 1, shape(TE.neg(ct.Approach.THROUGH_STOMA, spans=(unit(4),)), I6, stoma=True),
                  ct.Extent.ILEUM)]
        for code, number, R, reached in cases:
            with self.subTest(code=code):
                found, worded = self.item(code, R, self.enteroscopy_hold(code, R))
                self.assertEqual((found.message, found.held.kind, found.held.cause, found.fill.approach,
                                  found.fill.approach_words, found.fill.reached),
                                 (Q.MessageId.ENTEROSCOPY_APPROACH, EXPLANATION, CL.CLASS_CAUSE, None, (), reached))
                self.assertIn('CPT Studio could not confirm from the document the route this code describes',
                              worded.question)
                asked = worded.question.split(' Was ')[0]  # what is said of the enteroscopy, before the class asked
                for route in ('orally', 'through the mouth', 'through a stoma', 'through the documented stoma'):
                    self.assertNotIn(route, asked)
                assessed, spec = renderer_words(R, (code, number))[code]
                self.assertEqual(assessed.item.message, Q.MessageId.ENTEROSCOPY_APPROACH)
                self.assertTrue(spec.question and spec.reason)


def egd_within(part_of=None, whole=ct.SessionKind.EUS, tract=sup(ct.Tract.UPPER), second=None):
    """refute-r4a-r1 PD / refute-r4d-r2 P5 (D257): an EGD X1 (its examination E1, its part_of_session ``part_of``)
    beside a ``whole`` session X2 (its examination E2, an FNA E3 for an EUS); ``second`` another session X3 of that kind
    the part_of claim may name too."""
    doc = TE.Doc()
    doc.session(1, ct.SessionKind.EGD, reached=[sup(ct.Extent.SECOND_PORTION_DUODENUM)], part_of_session=part_of)
    doc.exam(1)
    doc.session(2, whole, tract=tract, reached=[sup(ct.Extent.DUODENUM)])
    doc.exam(2, session=X(2))
    if whole is ct.SessionKind.EUS:
        doc.act(3, ct.Kind.FNA, session=X(2))
    if second is not None:
        doc.session(3, second, tract=tract)
        doc.exam(4, session=X(3))
    return doc.build()


class D257BaseWithin(SimpleTestCase):
    """DECISIONS D257's questions.py half (r4a QW): a base-within hold's Fill carries the whole's own family
    (``whole_family``, combination.wholes' supported kind when the wholes are one family) and whether the whole is only
    possibly done (``whole_possible``: the hold a question, combination.base_within_hold's possible whole - an
    established one is its explanation). Repair r3c of round w8r's BASE_WITHIN words both."""

    def test_the_fill_names_the_wholes_family_and_whether_it_is_only_possible(self):
        """43235 beside 43242 through assess (refute-r4a-r1 PD's shapes): the EGD's part_of_session supported naming the
        EUS X2 (C3, an established whole: an explanation, ``whole_possible`` False, "is the endoscopic portion of the
        endoscopic ultrasound"), or no part_of and the EUS's tract unresolved upper (C-4 by possibly: a question, True,
        "may be ..., possibly performed on the date of service (its performance is not established)"); the family the
        EUS either way."""
        for name, part_of, tract, kind, possible in (
                ('established', sup(X(2)), sup(ct.Tract.UPPER), EXPLANATION, False),
                ('possible', None, unres(ct.Tract.UPPER), QUESTION, True)):
            with self.subTest(whole=name):
                R = egd_within(part_of, tract=tract)
                found = TA.by_code(TA.run(R, ('43235', 1), ('43242', 3)))['43235']
                item = found.item
                self.assertEqual((item.message, item.held.kind, item.fill.whole_family, item.fill.whole_possible),
                                 (Q.MessageId.BASE_WITHIN, kind, ct.SessionKind.EUS, possible))
                worded = wording.build(wording.Message.BASE_WITHIN, slots(item.fill), TA.TEXT)
                self.assertIn('the endoscopic portion of the endoscopic ultrasound documented with it', worded.reason)
                self.assertEqual('possibly performed on the date of service' in worded.reason, possible)

    def test_the_wholes_family_is_its_own_and_none_for_several(self):
        """refute-r4d-r2 P5: a whole that is a colonoscopy is named as the colonoscopy, never "the endoscopic
        ultrasound"; wholes of several families (the part_of claim's value and its reading naming an EUS and a
        colonoscopy) name none - wording then says "another procedure", never a whole the session may not be part of."""
        within = held('base_included', 21, EXPLANATION, subject=X(1), cause=CB.WITHIN_CAUSE)
        code = EV.code_facts('43235')
        R = egd_within(sup(X(2)), whole=ct.SessionKind.COLONOSCOPY)
        found = Q.item((within,), (), code, R)
        self.assertEqual((found.message, found.fill.whole_family, found.fill.whole_possible),
                         (Q.MessageId.BASE_WITHIN, ct.SessionKind.COLONOSCOPY, False))
        worded = wording.build(wording.Message.BASE_WITHIN, slots(found.fill), FILLER)
        self.assertIn('part of the colonoscopy documented with it', worded.reason)
        self.assertNotIn('endoscopic ultrasound', worded.question + worded.reason)
        mixed = fact(ct.Result.UNRESOLVED, X(2), ct.FactState.SUPPORTED, options=(X(3),),
                        reasons=(ct.Reason.APPRAISAL_UNCLEAR,))
        R = egd_within(mixed, second=ct.SessionKind.COLONOSCOPY)
        found = Q.item((dataclasses.replace(within, kind=QUESTION),), (), code, R)
        self.assertEqual((found.fill.whole_family, found.fill.whole_possible), (None, True))
        worded = wording.build(wording.Message.BASE_WITHIN, slots(found.fill), FILLER)
        self.assertIn('part of another procedure documented with it', worded.reason)


class Messages(SimpleTestCase):
    """message_of: for every item RULES can raise (rank, fact key, question or explanation), an id of the same fact
    key, kind and rank in wording.MESSAGES."""

    # The coding rule whose cause each requirement's holds carry (engine/evaluate.py; step 4c's ENT); the rest carry a
    # reading's cause.
    CAUSES = {rq.Requirement.SUP_STATUS: Q.Rule.ATTEMPTED, rq.Requirement.ROUTE_B: Q.Rule.ROUTE_B,
              rq.Requirement.ROUTE_D: Q.Rule.UNPROFILED, Tag.D80: Q.Rule.RECOGNISED_ONLY, Tag.TECH: Q.Rule.TECHNIQUE,
              Tag.SITE: Q.Rule.SITE, Tag.STRUCT_PFC: Q.Rule.STRUCTURE, Tag.ROUTE: Q.Rule.ROUTE, Tag.TRACT: Q.Rule.TRACT,
              Tag.XCHG: Q.Rule.EXCHANGE, Tag.CAUSE: Q.Rule.CAUSE, Tag.LIMITED: Q.Rule.LIMITED,
              Tag.STATIONS: Q.Rule.STATIONS, Tag.LOWER: Q.Rule.LOWER, Tag.ENT: Q.Rule.ENTEROSCOPY_CLASS,
              rq.Requirement.SUP_ENTRY: Q.Rule.ENTRY, Tag.YIELD: Q.Rule.YIELD}
    # RULES' explanations no step-3c message words: engine/evaluate.py raises each as its requirement's question (the
    # step's NOTES, question Q4; request R3 to step 3c).
    UNWORDED = {(rq.Requirement.SUP_SESSION_DONE, rq.FactKey.PERFORMED_STATUS)}

    def test_every_rules_item_has_a_message_of_its_rank_fact_and_kind(self):
        code = EV.code_facts('43249')
        for requirement, entry in rq.RULES.items():
            for kind, items in ((QUESTION, entry.asks), (EXPLANATION, entry.explains)):
                for found in items:
                    if found.fact is rq.FactKey.SERVICE_DATE or found.rank is None:
                        continue
                    key = rq.fact_key(found.fact, ct.Kind.SNARE if found.fact is rq.FactKey.CONFLICT else None)
                    rule = self.CAUSES.get(requirement)
                    cause = Q.coding_rule(rule) if rule is not None else 'reading_unknown'
                    with self.subTest(requirement=requirement.value, fact=key, kind=kind.value):
                        message = Q.message_of(held(key, found.rank.value, kind, cause=cause), code)
                        spec = wording.MESSAGES[wording.Message(message.value)]
                        if kind is EXPLANATION and (requirement, found.fact) in self.UNWORDED:
                            self.assertEqual((spec.fact, spec.kind), (found.fact.value, QUESTION))
                            continue
                        self.assertEqual((spec.fact, spec.kind, spec.rank), (found.fact.value, kind, found.rank.value))

    def test_the_code_facts_name_what_the_code_accounts_for(self):
        """Step 1e's hand-off #5: catalogue.accounted is called, never forked: the D27-narrowed code names its
        defining act, an EUS code its act beside the examination, a base code the examination."""
        from studio.interpretation.engine import catalogue
        for code in ('43265', '43242', '45378', '46221', '99152', '43249'):
            with self.subTest(code=code):
                self.assertEqual(EV.code_facts(code).group, catalogue.accounted(catalogue.code_link(code)))
        self.assertEqual(EV.code_facts('43265').group, (ct.Kind.LITHOTRIPSY,))
        self.assertEqual(EV.code_facts('43249').technique, EV.catalogue.TechniqueClass.BALLOON)

    def test_the_messages_chosen_by_rule(self):
        code = EV.code_facts('43249')
        cases = {
            Q.MessageId.ATTEMPTED: held(kind=EXPLANATION, cause=Q.coding_rule(Q.Rule.ATTEMPTED)),
            Q.MessageId.UNRECONCILED: held(kind=EXPLANATION, cause=Q.coding_rule(Q.Rule.ROUTE_B)),
            Q.MessageId.NOT_DOCUMENTED: held(cause=Q.coding_rule(Q.Rule.NOT_DOCUMENTED)),
            Q.MessageId.DOUBT: held(rank=2),
            Q.MessageId.CONFLICT: held('conflict:snare', 1, cause='relation:contradiction'),
            Q.MessageId.CONFLICT_FACT: held('conflict:snare', 1, cause='reading_contradicted'),
            Q.MessageId.TECHNIQUE: held('technique', 10, cause=Q.coding_rule(Q.Rule.TECHNIQUE)),
            Q.MessageId.STATED_TECHNIQUE: held('technique', 10, cause='relation:unresolved'),
            Q.MessageId.WALL_INJECTION: held('technique', 10, EXPLANATION, cause=Q.coding_rule(Q.Rule.ROUTE)),
            Q.MessageId.SITE: held('act_target', 11, cause=Q.coding_rule(Q.Rule.SITE)),
            Q.MessageId.DUCT: held('act_target', 11, cause=Q.coding_rule(Q.Rule.EXCHANGE)),
            Q.MessageId.ANOTHER_TRACT: held('procedure', 8, EXPLANATION, cause=Q.coding_rule(Q.Rule.TRACT)),
            Q.MessageId.STRUCTURE: held('target', 12, cause=Q.coding_rule(Q.Rule.STRUCTURE)),
            Q.MessageId.BUNDLED: held('performed_status', 18, EXPLANATION, cause=Q.coding_rule(Q.Rule.CAUSE)),
        }
        for message, entry in cases.items():
            with self.subTest(message=message):
                self.assertEqual(Q.message_of(entry, code), message)
        with self.assertRaises(ValueError):
            Q.fact_of(held('not_a_fact_key'))


class Boundary(SimpleTestCase):
    def test_measure_4(self):
        self.assertEqual(measure_4(MODULE.read_text(encoding='utf-8'), engine=True), [])

    def test_the_engine_never_imports_wording(self):
        source = MODULE.read_text(encoding='utf-8') + (APP / 'studio' / 'interpretation' / 'engine' /
                                                       'evaluate.py').read_text(encoding='utf-8')
        self.assertNotIn('import wording', source)
        self.assertNotIn('interpretation.wording', source)


# --- step f3w of AMENDMENT-2's build round (DECISIONS D280.3, D281, D284, D287; build list B1, B3-B7, B9) -------------


def _ta_words(n):
    """The synthetic revision's characters at unit ``n`` (tests/v2/test_assess.TEXT: the text the renderer quotes)."""
    return wording.span_text(TA.TEXT, (unit(n),))


def _ta_quote(n, cut=120):
    """Unit ``n`` of tests/v2/test_assess.TEXT as wording quotes it (a question cuts at 120, a reason at 140)."""
    return wording.quote(_ta_words(n), cut)


def dre_shape(over=None, *, e3=True, biopsy=True):
    """refute-safety's qd2_steer and refute-r4a-r1's v9_dre_own_rows, v9_dre_own_rows2 and v9_dre_conflict shapes,
    ported and synthetic: a colonoscopy X1 to the cecum; E1 filed as its examination with ``over`` (its device among
    them; None: no E1 - the same document without the DRE line); the cold snare E2 of L1 at the sigmoid colon; the
    colonoscope's examination E3 done today (``e3``); a cold-forceps biopsy E4 at the ascending colon (``biopsy``)."""
    doc = Doc()
    doc.session(1, ct.SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER),
                reached=[sup(ct.Extent.CECUM)])
    if over is not None:
        over = dict(over)
        doc.act(1, over.pop('kind', ct.Kind.EXAMINATION), **over)
    doc.lesion(1, lesion_places=[sup(ct.Landmark.SIGMOID_COLON)])
    doc.act(2, ct.Kind.SNARE, places=[sup(ct.Landmark.SIGMOID_COLON)], lesion=sup(L(1)),
            device=sup(ct.Device.COLD_SNARE))
    if e3:
        doc.exam(3)
    if biopsy:
        doc.act(4, ct.Kind.BIOPSY, places=[sup(ct.Landmark.ASCENDING_COLON)], device=sup(ct.Device.COLD_FORCEPS))
    return doc.build()


def overfilled_device(*written) -> Fact:
    """An overfilled device slot's merged view as engine/facts builds it (AMENDMENT-2 4.3.3; tests/v2/test_pairing's
    form): ``written`` its written facts as (state, value)."""
    values = tuple(dict.fromkeys(value for _state, value in written))
    stated = {value for state, value in written if state is not ct.FactState.NEGATED}
    denied = tuple(dict.fromkeys(value for state, value in written
                                 if state is ct.FactState.NEGATED and value not in stated))
    return Fact(result=ct.Result.UNRESOLVED, value=None, state=ct.FactState.CONTRADICTED, options=values,
                reasons=(ct.Reason.SLOT_OVERFULL,), spans=(), negated_values=denied)


# A device that CLAIMS manual without establishing it (D280.3; AMENDMENT-2 4.3.3 c's overfilled slot included)
CLAIMED_DEVICES = (('unresolved', unres(ct.Device.MANUAL)), ('doubted', doubted(ct.Device.MANUAL)),
                   ('contradicted', contra(ct.Device.MANUAL, ct.Device.ENDOSCOPE)),
                   ('overfilled', overfilled_device((ct.FactState.SUPPORTED, ct.Device.MANUAL),
                                                    (ct.FactState.SUPPORTED, ct.Device.ENDOSCOPE))))
# The DRE's own rows (v9_dre_own_rows, v9_dre_own_rows2, v9_dre_conflict, qd2_steer) and, for a claimed device, the
# fact key 45385's hold rests on E1 by beside E3 (None: E1 adds no hold beside the session's done examination - an
# event of another occasion, or the control - so the code is the document's without the DRE line)
DRE_OWN = (
    ('status negated', dict(status=neg(Status.PERFORMED)), 'performed_status'),
    ('status unresolved', dict(status=unres(Status.PERFORMED)), 'performed_status'),
    ('status doubted', dict(status=doubted(Status.PERFORMED)), 'performed_status'),
    ('status contradicted, two sides', dict(status=contra(Status.PERFORMED, Status.PLANNED,
                                                          spans=(unit(1), Span(950, 990)))), 'conflict:examination'),
    ('status contradicted', dict(status=contra(Status.PERFORMED, Status.PLANNED)), 'conflict:examination'),
    ('entry nursing', dict(entry=sup(ct.Owner.NURSING)), 'event_entry'),
    ('entry anesthesia', dict(entry=sup(ct.Owner.ANESTHESIA)), 'event_entry'),
    ('entry another clinician', dict(entry=sup(ct.Owner.OTHER_CLINICIAN)), 'event_entry'),
    ('entry unresolved', dict(entry=unres(ct.Owner.DOCUMENTING_CLINICIAN)), 'event_entry'),
    ('performer unresolved', dict(performer=unres(TE.TEAM)), 'event_performer'),
    ('date unresolved', dict(date=unres(TE.ON)), 'event_time'),
    ('status planned', dict(status=sup(Status.PLANNED)), None),
    ('date earlier', dict(date=sup(EARLIER)), None),
    ('performer other', dict(performer=sup(ct.Performer.OTHER_CLINICIAN)), None),
    ('done (control)', {}, None),
)
DRE_CODES = (('45385', 2), ('45380', 4), ('45378', 3))


class D280ResidualItems(SimpleTestCase):
    """DECISIONS D280.1 and D280.3 (build list B1; G3-09, G1-05 (iii), G1-06), questions.py's and the renderer's half
    (the per-code rule: tests/v2/test_evaluate.py D280Row7): over refute-safety's qd2_steer and refute-r4a-r1's
    v9_dre_own_rows, v9_dre_own_rows2 and v9_dre_conflict shapes, every row whose DRE is ESTABLISHED (kind supported
    examination, device supported manual) is the document without the DRE line, every code's status and item; every
    row whose device only CLAIMS manual keeps its hold, its held fact, rank and key, and every item resting on the
    claimed examination is DIGITAL_SCOPE: its question names the held session's examination by its service and quotes
    none of the claimed examination's words (the session's examination E3's when it may be quoted), its reason quotes
    them, and the clarification keeps the held fact's key (an answer binds as today)."""

    @staticmethod
    def assessed(R, *codes):
        return {code: (found.status.value, found.item, spec)
                for code, (found, spec) in renderer_words(R, *codes).items()}

    def check_digital_scope(self, found, spec, R, *, e3):
        self.assertEqual(found.status.value, 'needs_clarification')
        item = found.item
        self.assertEqual(item.message, Q.MessageId.DIGITAL_SCOPE)
        self.assertIn(item.held, found.held_facts)
        self.assertEqual((item.fill.act, item.fill.family, item.fill.held),
                         (ct.Kind.EXAMINATION, ct.SessionKind.COLONOSCOPY, rq.Rank(item.held.rank)))
        self.assertEqual(item.fill.statements[0], (unit(1),))  # the claimed examination's own words, first
        self.assertEqual(item.fill.words, (unit(3),) if e3 else ())  # the session's examination that may be quoted
        self.assertEqual(spec.fact, item.held.fact)  # the clarification keeps the held fact's key
        self.assertNotIn(_ta_words(1), spec.question)
        self.assertIn(_ta_quote(1, 140), spec.reason)
        self.assertIn('a statement whose technique CPT Studio could not confirm from the document', spec.reason)
        self.assertEqual(_ta_words(3) in spec.question, e3)
        self.assertTrue(spec.question.startswith('Is the colonoscopy '), spec.question)
        self.assertTrue(spec.question.endswith(f'{DONE}?'), spec.question)

    def test_every_established_dre_row_is_the_document_without_the_dre_line(self):
        rows = 0
        for e3 in (True, False):
            codes = DRE_CODES if e3 else DRE_CODES[:2] + (('45378', 1),)
            without = self.assessed(dre_shape(None, e3=e3), *codes)
            for name, over, _key in DRE_OWN:
                with self.subTest(e3=e3, dre=name):
                    R = dre_shape(dict(over, device=sup(ct.Device.MANUAL)), e3=e3)
                    found = self.assessed(R, *codes)
                    self.assertEqual({code: (status, item) for code, (status, item, _spec) in found.items()},
                                     {code: (status, item) for code, (status, item, _spec) in without.items()})
                    self.assertEqual(found['45385'][0], 'ready')
                    rows += 1
        self.assertEqual(rows, 2 * len(DRE_OWN))

    def test_every_claimed_device_row_keeps_its_hold_worded_digital_scope(self):
        held = 0
        for e3 in (True, False):
            codes = DRE_CODES if e3 else DRE_CODES[:2] + (('45378', 1),)
            without = renderer_words(dre_shape(None, e3=e3), *codes)
            for name, over, key in DRE_OWN:
                for device_name, device in CLAIMED_DEVICES:
                    with self.subTest(e3=e3, dre=name, device=device_name):
                        R = dre_shape(dict(over, device=device), e3=e3)
                        found = renderer_words(R, *codes)
                        snare, spec = found['45385']
                        if (key is None and e3) or not over:  # beside the session's done examination, or done
                            self.assertEqual((snare.status.value, snare.item), ('ready', None))
                        else:
                            self.check_digital_scope(snare, spec, R, e3=e3)
                            self.assertEqual(snare.item.held.subject, E(1))
                            if key is not None:
                                self.assertEqual(snare.item.held.fact, key)
                            held += 1
                        for code, (other, worded) in found.items():  # every other code: DIGITAL_SCOPE or unchanged
                            if other.item is not None and other.item.message is Q.MessageId.DIGITAL_SCOPE:
                                self.check_digital_scope(other, worded, R, e3=e3)
                            else:
                                self.assertEqual((other.status, other.item), (without[code][0].status,
                                                                              without[code][0].item))
        self.assertEqual(held, len(CLAIMED_DEVICES) * (len(DRE_OWN) - 1 + len(DRE_OWN) - 4))

    def test_each_open_fact_reaches_its_reason(self):
        """The reason states the claimed examination's open fact by the held fact's RANK row: the four own-row forms and
        the conflict's sides, beside E3 (qd2_steer's E3)."""
        for name, over, words in (
                ('status unresolved', dict(status=unres(Status.PERFORMED)),
                 'it is not established as done on the date of service'),
                ('status doubted', dict(status=doubted(Status.PERFORMED)), 'the document leaves it in doubt'),
                ('entry nursing', dict(entry=sup(ct.Owner.NURSING)), 'it is told only in the nursing entry'),
                ('entry unresolved', dict(entry=unres(ct.Owner.DOCUMENTING_CLINICIAN)),
                 'CPT Studio could not confirm from the document whose entry it is told in'),
                ('performer unresolved', dict(performer=unres(TE.TEAM)),
                 'CPT Studio could not confirm from the document who performed it'),
                ('date unresolved', dict(date=unres(TE.ON)),
                 'CPT Studio could not confirm from the document when it was done'),
                ('status contradicted, two sides', dict(status=contra(Status.PERFORMED, Status.PLANNED,
                                                                      spans=(unit(1), Span(950, 990)))),
                 'statements in the document disagree about whether it was done'),
                ('status contradicted', dict(status=contra(Status.PERFORMED, Status.PLANNED)),
                 'the document is not consistent about whether it was done')):
            with self.subTest(dre=name):
                R = dre_shape(dict(over, device=unres(ct.Device.MANUAL)), biopsy=False)
                found, spec = renderer_words(R, ('45385', 2))['45385']
                self.assertEqual(found.item.message, Q.MessageId.DIGITAL_SCOPE)
                self.assertEqual(spec.question, f'Is the colonoscopy ({_ta_quote(3)}) {DONE}?')
                self.assertTrue(spec.reason.startswith(f'The document states {_ta_quote(1, 140)}, a statement whose '
                                                       f'technique CPT Studio could not confirm from the document; '
                                                       f'{words}'), spec.reason)
                self.assertTrue(spec.reason.endswith(f'. {wording.HELD}'), spec.reason)

    def test_g2_28_a_colonoscope_examination_whose_device_is_doubted_stays_held(self):
        """G2-28's input pinned held (build list B1): the colonoscope's examination E1, its device doubted (endoscope or
        manual) and its status open, the snare E2 - with or without E3. Held, the item DIGITAL_SCOPE on E1's status
        (performed_status, RANK row 4); never READY (mutant: row 7 skipping the claimed digital examination)."""
        for e3 in (False, True):
            with self.subTest(e3=e3):
                R = dre_shape(dict(device=doubted(ct.Device.ENDOSCOPE, ct.Device.ENDOSCOPE, ct.Device.MANUAL),
                                   status=unres(Status.PERFORMED)), e3=e3, biopsy=False)
                evaluation = EV.decide('45385', (), R)
                self.assertNotEqual(evaluation.held_facts, ())
                found, spec = renderer_words(R, ('45385', 2))['45385']
                self.check_digital_scope(found, spec, R, e3=e3)
                self.assertEqual((found.item.held.fact, found.item.held.rank, found.item.held.subject),
                                 ('performed_status', 4, E(1)))

    def test_a_claimed_digital_statement_beside_the_sessions_examination(self):
        """refute-safety's dre_statement (D280.2's claimed side, option (a)): a claimed DRE E1 that is a statement - its
        status negated or unresolved - beside the colonoscope's done examination E2, 45378 on E2's unit: the pair's
        hold (statement_scope, RANK row 3, on E2) worded DIGITAL_SCOPE with no attribute - "whether it is about the
        colonoscopy" - quoting E2 in the question and E1 in the reason. Established: READY, as without E1."""
        for name, status in (('negated', neg(Status.PERFORMED)), ('unresolved', unres(Status.PERFORMED))):
            for device_name, device in CLAIMED_DEVICES:
                with self.subTest(status=name, device=device_name):
                    doc = TE.dre_alone(endoscopic={}, dre=False)
                    doc.exam(1, device=device, status=status)
                    R = doc.build()
                    found, spec = renderer_words(R, ('45378', 2))['45378']
                    self.assertEqual((found.item.message, found.item.held.fact, found.item.held.rank,
                                      found.item.held.subject, found.item.fill.attribute),
                                     (Q.MessageId.DIGITAL_SCOPE, 'statement_scope', 3, E(2), None))
                    self.assertEqual(spec.question, f'Is the colonoscopy ({_ta_quote(2)}) {DONE}?')
                    self.assertIn('whether it is about the colonoscopy', spec.reason)
                    self.assertIn(_ta_quote(1, 140), spec.reason)
                    self.assertEqual(spec.fact, 'statement_scope')
            with self.subTest(status=name, device='established'):
                doc = TE.dre_alone(endoscopic={}, dre=False)
                doc.exam(1, device=sup(ct.Device.MANUAL), status=status)
                found, spec = renderer_words(doc.build(), ('45378', 2))['45378']
                self.assertEqual((found.status.value, found.item, spec), ('ready', None, None))

    def test_a_supported_manual_device_with_its_kind_not_established_keeps_d265s_form(self):
        """The step's NOTES, question Q-DRE-KIND: E1's device SUPPORTED manual and its kind unresolved examination is
        neither established (D280.1: its kind is not supported) nor device-claimed (D280.3: "device not supported
        manual") - its technique is confirmed, so DIGITAL_SCOPE's reason would be untrue; its hold keeps the item it had
        (45385 held on E1's status, never DIGITAL_SCOPE)."""
        R = dre_shape(dict(kind=unres(ct.Kind.EXAMINATION), device=sup(ct.Device.MANUAL),
                           status=unres(Status.PERFORMED)), biopsy=False)
        self.assertFalse(Q.claimed_digital(R, E(1)))
        found, spec = renderer_words(R, ('45385', 2))['45385']
        self.assertEqual(found.status.value, 'needs_clarification')
        self.assertNotEqual(found.item.message, Q.MessageId.DIGITAL_SCOPE)
        self.assertNotIn('technique', spec.reason)

    def test_claimed_digital_reads_the_device_and_the_claimed_kind(self):
        """``claimed_digital``: the claimed kind the examination (supported, unresolved, doubted) and a device that claims
        manual without being supported manual; never a supported manual device, a negated or silent kind, an endoscope,
        manual negated, or an overfilled slot whose written facts deny manual."""
        for kind_name, kind in (('supported', sup(ct.Kind.EXAMINATION)), ('unresolved', unres(ct.Kind.EXAMINATION)),
                                ('doubted', doubted(ct.Kind.EXAMINATION, ct.Kind.EXAMINATION, ct.Kind.SNARE)),
                                ('negated', neg(ct.Kind.EXAMINATION)), ('silent', SILENT)):
            for device_name, device, claims in (
                    *((name, device, True) for name, device in CLAIMED_DEVICES),
                    ('supported manual', sup(ct.Device.MANUAL), False), ('endoscope', sup(ct.Device.ENDOSCOPE), False),
                    ('manual negated', neg(ct.Device.MANUAL), False), ('silent', None, False),
                    ('overfilled [endoscope, manual denied]',
                     overfilled_device((ct.FactState.SUPPORTED, ct.Device.ENDOSCOPE),
                                       (ct.FactState.NEGATED, ct.Device.MANUAL)), False)):
                with self.subTest(kind=kind_name, device=device_name):
                    R = dre_shape(dict(kind=kind, device=device), biopsy=False)
                    expected = claims and kind_name in ('supported', 'unresolved', 'doubted')
                    self.assertEqual(Q.claimed_digital(R, E(1)), expected)


class D281Routing(SimpleTestCase):
    """DECISIONS D281 (build list B4, G1-07; B3, G1-05; B6, G3-27), questions.py's half: refute-r4a-r1's
    v9_scope_kind_states and the lead's g107_carded_kind_states grid - E1, the colonoscopy's examination done today,
    its kind supported, unresolved, doubted (examination|snare) or silent, beside pass 2's unlisted doubt or denial of
    kind examination with no card or carded X1, 45378 kept on E1's unit. A rank-2 unlisted hold is routed by the act's
    CLAIMED kind: UNLISTED_SCOPE (no card) or the session's DOUBT (carded) for the first three, the examination asked by
    row 7's done; DOUBT naming "another act" for the silent kind (D267's label, D271). E1 is quoted as the session's
    examination only when its kind is supported, and where it is not quoted its owner, device, place and lesion are
    not carried (B3). A carded denial reads B5's form (mutant: routing by act_kind)."""

    KINDS = (('supported', sup(ct.Kind.EXAMINATION)), ('unresolved', unres(ct.Kind.EXAMINATION)),
             ('doubted examination|snare', doubted(ct.Kind.EXAMINATION, ct.Kind.EXAMINATION, ct.Kind.SNARE)),
             ('silent', SILENT))

    def test_the_grid(self):
        rows = 0
        for name, kind in self.KINDS:
            for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.DENIAL):
                for card in (None, X(1)):
                    with self.subTest(kind=name, what=what, card=card):
                        doc = colonoscopy(snare=False)
                        doc.act(1, kind)
                        doc.unlisted.append(TE.unlisted(what, ct.Kind.EXAMINATION, card, unit(9)))
                        found, spec = renderer_words(doc.build(), ('45378', 1))['45378']
                        item = found.item
                        self.assertEqual((item.held.fact, item.held.rank, item.held.cause, item.held.subject),
                                         ('performed_status', 2, Q.UNLISTED, E(1)))
                        self.assertEqual(item.fill.unlisted_what, what)
                        denial = 'a statement that an act was not done; CPT Studio could not confirm from the ' \
                                 'document whether it is about'
                        if name == 'silent':
                            self.assertEqual((item.message, item.fill.act, item.fill.words),
                                             (Q.MessageId.DOUBT, ct.Kind.OTHER, (unit(1),)))
                            self.assertEqual(spec.question, f'Confirm whether another act ({_ta_quote(1)}) was done '
                                                            'on the date of service.')
                            self.assertEqual(spec.reason, f'The document states {_ta_quote(9, 140)}, {denial} another '
                                                          'act.' if what is ct.UnlistedWhat.DENIAL else
                                             f'The document leaves another act in doubt: {_ta_quote(9, 140)}.')
                            rows += 1
                            continue
                        quoted = name == 'supported'
                        self.assertEqual((item.fill.act, item.fill.family, item.fill.words),
                                         (ct.Kind.EXAMINATION, ct.SessionKind.COLONOSCOPY,
                                          (unit(1),) if quoted else ()))
                        if not quoted:  # B3: no Fill carries one event's facts beside another's (or no) words
                            self.assertEqual((item.fill.owner, item.fill.device, item.fill.place, item.fill.lesion),
                                             (None, None, None, ()))
                        named = f'the colonoscopy ({_ta_quote(1)})' if quoted else 'the colonoscopy'
                        if card is None:
                            self.assertEqual(item.message, Q.MessageId.UNLISTED_SCOPE)
                            self.assertEqual(spec.question, f'Is {named} {DONE}?')
                            self.assertEqual(spec.reason, f'The document states {_ta_quote(9, 140)}, which names no '
                                                          'procedure session; CPT Studio could not confirm from the '
                                                          f'document whether it is about the colonoscopy. '
                                                          f'{wording.HELD}')
                        else:
                            self.assertEqual(item.message, Q.MessageId.DOUBT)
                            self.assertEqual(spec.question, f'Confirm whether {named} is {DONE}.')
                            self.assertEqual(spec.reason, f'The document states {_ta_quote(9, 140)}, {denial} the '
                                                          'colonoscopy.' if what is ct.UnlistedWhat.DENIAL else
                                             f'The document leaves the colonoscopy in doubt: {_ta_quote(9, 140)}.')
                        rows += 1
        self.assertEqual(rows, 16)

    def test_the_route_reads_the_claimed_kind_never_act_kind(self):
        """``_claims_examination`` against act_kind (D267's label): an unresolved or doubted examination is Kind.OTHER by
        act_kind and is routed as the session's examination; a contradicted, negated or silent kind claims none."""
        for name, kind, claims in (('supported', sup(ct.Kind.EXAMINATION), True),
                                   ('unresolved', unres(ct.Kind.EXAMINATION), True),
                                   ('doubted', doubted(ct.Kind.EXAMINATION, ct.Kind.EXAMINATION, ct.Kind.SNARE), True),
                                   ('doubted, snare claimed', doubted(ct.Kind.SNARE, ct.Kind.SNARE,
                                                                      ct.Kind.EXAMINATION), False),
                                   ('contradicted', contra(ct.Kind.EXAMINATION, ct.Kind.SNARE), False),
                                   ('negated', neg(ct.Kind.EXAMINATION), False), ('silent', SILENT, False),
                                   ('a snare', sup(ct.Kind.SNARE), False)):
            with self.subTest(kind=name):
                doc = colonoscopy(snare=False)
                doc.act(1, kind)
                R = doc.build()
                self.assertEqual(Q._claims_examination(R, E(1)), claims)
                self.assertEqual(Q._quotable(R, E(1)), name == 'supported')

    def test_b3_the_owner_goes_with_the_words_over_the_d265_and_d266_grids(self):
        """Build list B3's property, over this class's grid, D265Items' and D266Quotes' shapes and the DRE shapes: whenever
        a Fill's words are not its held event's anchor, its owner, device, place and lesion are empty - except
        DIGITAL_SCOPE, whose owner states its first statement, the held examination's own words (the step's NOTES, the
        B3 property's exemption)."""
        scenes = []
        for _name, kind in self.KINDS:
            for what in (ct.UnlistedWhat.DOUBT, ct.UnlistedWhat.DENIAL):
                for card in (None, X(1)):
                    doc = colonoscopy(snare=False)
                    doc.act(1, kind, entry=sup(ct.Owner.NURSING))
                    doc.unlisted.append(TE.unlisted(what, ct.Kind.EXAMINATION, card, unit(9)))
                    scenes.append((doc.build(), ('45378', 1)))
        for _name, over, _key in DRE_OWN:
            for _device_name, device in CLAIMED_DEVICES + (('established', sup(ct.Device.MANUAL)),):
                scenes.append((dre_shape(dict(over, device=device)), ('45385', 2)))
                scenes.append((dre_shape(dict(over, device=device), e3=False), ('45385', 2)))
        for other in TE.A2_OTHERS:
            for what, card in TE.A2_ENTRIES:
                for kept in (1, 2, 3):
                    scenes.append((TE.dre_colonoscopy(other, what=what, card=card).build(), ('45378', kept)))
        checked = 0
        for R, code in scenes:
            found, _spec = renderer_words(R, code)[code[0]]
            item = found.item
            if item is None or item.message is Q.MessageId.DIGITAL_SCOPE:
                continue
            subject = item.held.subject
            if subject is None or subject.family.value != 'E':  # the property is about a held event
                continue
            if item.fill.words != R.anchors[subject].units:
                with self.subTest(code=code, message=item.message, subject=subject):
                    self.assertEqual((item.fill.owner, item.fill.device, item.fill.place, item.fill.lesion),
                                     (None, None, None, ()))
                checked += 1
        self.assertGreater(checked, 8)


class D281DenialForm(SimpleTestCase):
    """DECISIONS D281 (build list B5, G3-10), engine to renderer: refute-r4a-r1's v9_denial_pairs (a kept unlisted
    denial of kind snare, removal or none beside the snare, no card or carded X1), v9_denial_same_unit (the denial in the
    snare's own unit, 45385 kept elsewhere) and refute-r3c-r1's two-session input (p41 beside an EGD, a kindless denial):
    every DOUBT item whose entry is a DENIAL reads "The document states “<denial>”, a statement that an act was not done;
    CPT Studio could not confirm from the document whether it is about <the act>." - quoting the denial, never "was not
    done" after the act's label; a DOUBT entry keeps "leaves ... in doubt" (mutant: DENIAL_STATED restored)."""

    def denial_items(self, R, *codes):
        out = []
        for code, (found, spec) in renderer_words(R, *codes).items():
            if found.item is not None and found.item.message is Q.MessageId.DOUBT \
                    and found.item.fill.unlisted_what is ct.UnlistedWhat.DENIAL:
                out.append((code, found, spec))
        return out

    def check(self, found, spec, statement):
        head, middle, tail = spec.reason.partition(', a statement that an act was not done; CPT Studio could not '
                                                   'confirm from the document whether it is about ')
        self.assertEqual(head, f'The document states {wording.quote(wording.span_text(TA.TEXT, statement), 140)}')
        self.assertTrue(middle and tail.endswith('.'), spec.reason)
        self.assertNotIn(' was not done:', spec.reason)
        self.assertNotIn(f'{tail[:-1]} was not done', spec.reason)
        self.assertNotIn('in doubt', spec.reason)

    def test_v9_denial_pairs(self):
        rows = 0
        for kind in (ct.Kind.SNARE, ct.Kind.REMOVAL, None):
            for card in (None, X(1)):
                with self.subTest(kind=kind, card=card):
                    doc = colonoscopy()
                    doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DENIAL, kind, card, unit(9)))
                    found = self.denial_items(doc.build(), ('45385', 2))
                    self.assertEqual([code for code, _found, _spec in found], ['45385'])
                    code, item, spec = found[0]
                    self.assertEqual(item.item.held.subject, E(2))
                    self.check(item, spec, (unit(9),))
                    self.assertTrue(spec.reason.endswith('whether it is about the snare removal (cold snare) at the '
                                                         'sigmoid colon.'), spec.reason)
                    rows += 1
                    doc = colonoscopy()
                    doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, kind, card, unit(9)))
                    doubt, worded = renderer_words(doc.build(), ('45385', 2))['45385']
                    self.assertEqual(worded.reason, 'The document leaves the snare removal (cold snare) at the sigmoid '
                                                    f'colon in doubt: {_ta_quote(9, 140)}.')
        self.assertEqual(rows, 6)

    def test_v9_denial_same_unit(self):
        """The denial in the snare's own unit (2), 45385 kept on unit 7 (a unit no event holds), so the entry is the
        rule-4 pair's statement and not the code's evidence passage: the DENIAL form quoting the snare's own words."""
        for kind in (ct.Kind.SNARE, None):
            for card in (None, X(1)):
                with self.subTest(kind=kind, card=card):
                    doc = colonoscopy()
                    doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DENIAL, kind, card, unit(2)))
                    R = doc.build()
                    evaluation = EV.decide('45385', (unit(7),), R)
                    found = EV.item('45385', (unit(7),), R, evaluation)
                    self.assertEqual((found.message, found.fill.unlisted_what, found.fill.statements),
                                     (Q.MessageId.DOUBT, ct.UnlistedWhat.DENIAL, ((unit(2),),)))
                    worded = wording.build(wording.Message(found.message.value), slots(found.fill), TA.TEXT)
                    self.check(found, worded, (unit(2),))

    def test_the_two_session_input(self):
        """p41 beside an EGD X2 (its examination E3, a biopsy E4 at the stomach), one kindless kept denial in unit 9: with
        no card it pairs with the snare and the biopsy (DOUBT, the DENIAL form) and is 45378's UNLISTED_SCOPE; carded X1,
        the snare's DOUBT and 45378's session DOUBT read the DENIAL form, and the EGD's biopsy is READY."""
        for card, denied in ((None, ['43239', '45385']), (X(1), ['45378', '45385'])):
            with self.subTest(card=card):
                R = TE.p41(ct.UnlistedWhat.DENIAL, card, egd_beside=True, kind=None).build()
                found = self.denial_items(R, ('45385', 2), ('45378', 1), ('43239', 4))
                self.assertEqual(sorted(code for code, _found, _spec in found), denied)
                for _code, item, spec in found:
                    self.check(item, spec, (unit(9),))


class D281Begun(SimpleTestCase):
    """DECISIONS D281 (build list B6, G3-27): refute-safety's begun_scope shape - the colonoscopy's examination E1 begun
    (status attempted_not_completed) beside a kept unlisted doubt of kind examination with no card, 45378 on E1's unit:
    UNLISTED_SCOPE quoting E1 and asking row 7's done, which says "in part" (an examination begun counts as done, as v1's
    done does) - never "documented as done" (mutant: that form restored for a begun examination)."""

    def test_begun_scope(self):
        doc = Doc()
        doc.session(1, ct.SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.THIS_ENCOUNTER))
        doc.exam(1, status=sup(Status.ATTEMPTED_NOT_COMPLETED))
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.EXAMINATION, None, unit(9)))
        found, spec = renderer_words(doc.build(), ('45378', 1))['45378']
        self.assertEqual((found.item.message, found.item.fill.words), (Q.MessageId.UNLISTED_SCOPE, (unit(1),)))
        self.assertEqual(spec.question, f'Is the colonoscopy ({_ta_quote(1)}) documented as performed, in full or in '
                                        'part, on the date of service?')
        self.assertNotIn('documented as done', spec.question)


class D284AddonItems(SimpleTestCase):
    """DECISIONS D284 (G3-15; build list B7), questions.py's half: a performed_status witness whose cause is
    engine/assess.ADDON_CAUSE is ADDON (message_of), its Fill the add-on code and no fact of its act; through engine/assess
    the add-on beside no counted primary (43273 alone; 99417 beside 99213) is held with ADDON's item, worded from codes
    alone - never "could not confirm ... done" and no quote. The primaries the sentence names are the caller's (the
    step's NOTES, request: engine/assess fills ``codes``); with none it reads its true absence form."""

    def test_the_cause_is_assess_s(self):
        from studio.interpretation.engine import assess
        self.assertEqual(Q.ADDON_CAUSE, assess.ADDON_CAUSE)
        self.assertEqual(Q.MessageId.ADDON.value, wording.Message.ADDON.value)

    def test_message_of(self):
        for number in ('43273', '99417', '91013', '99153'):
            code = EV.code_facts(number)
            with self.subTest(code=number):
                witness = held(fact='performed_status', rank=4, cause=Q.ADDON_CAUSE)
                self.assertIs(Q.message_of(witness, code), Q.MessageId.ADDON)
                for cause in ('reading_unknown', Q.coding_rule(Q.Rule.NOT_DOCUMENTED)):
                    with self.subTest(cause=cause):
                        self.assertIsNot(Q.message_of(held(fact='performed_status', rank=4, cause=cause), code),
                                         Q.MessageId.ADDON)

    def test_through_assess(self):
        from studio.interpretation.engine import assess
        for name, doc, codes, code in (('43273 alone', TA.ercp(stone=False), (('43273', 3),), '43273'),
                                       ('99417 beside 99213', TA.office_prolonged(), (('99213', 1), ('99417', 2)),
                                        '99417')):
            with self.subTest(case=name):
                found, spec = renderer_words(doc.build(), *codes)[code]
                self.assertEqual(found.status.value, 'needs_clarification')
                self.assertEqual((found.item.message, found.item.held.cause, found.item.held.fact,
                                  found.item.held.rank), (Q.MessageId.ADDON, Q.ADDON_CAUSE, 'performed_status', 4))
                self.assertEqual(found.item.fill.code, code)
                self.assertLessEqual(set(found.item.fill.codes), set(assess.primaries(code)))
                self.assertTrue(spec.question.startswith(f'{code} is reported only together with '), spec.question)
                self.assertTrue(spec.question.endswith('documented as performed on the date of service?'))
                self.assertEqual(spec.fact, 'performed_status')
                for sentence in (spec.question, spec.reason):
                    self.assertNotIn('could not confirm', sentence)
                    self.assertNotIn('“', sentence)


class D287Keys(SimpleTestCase):
    """DECISIONS D287 (G3-28; build list B9), questions.py's and evaluate.py's half: act_kind is facts.established_kind
    for an event (the derivation moved, never copied), and the per-code rule keys a conflict over an act
    conflict:<established_kind> - for an act E2 whose kind is silent, unresolved, doubted, contradicted, negated,
    supported, or a clip supported for hemostasis, each beside "No polyp was removed." (a broad snare denial) and with its
    own status contradicted. g3c's shape 4 through the renderer: the clip's conflict names "the bleeding control". (The
    keys of coverage.Reader, act_witnesses, the bundling verdict and classes' witnesses are their owner's: the step's
    NOTES, requests.)"""

    def shapes(self):
        for name, kind in (('silent', SILENT), ('unresolved', unres(ct.Kind.SNARE)),
                           ('doubted', doubted(ct.Kind.SNARE, ct.Kind.SNARE, ct.Kind.BIOPSY)),
                           ('contradicted', contra(ct.Kind.SNARE, ct.Kind.BIOPSY)), ('negated', neg(ct.Kind.SNARE)),
                           ('supported', sup(ct.Kind.SNARE))):
            doc = colonoscopy(kind=kind, status=contra(Status.PERFORMED, Status.PLANNED))
            TE.denial_event(doc, number=3, kind=ct.Kind.SNARE)
            yield name, doc.build(), '45385'
        doc = colonoscopy(snare=False)
        doc.act(2, ct.Kind.CLIP, purpose=sup(ct.Purpose.HEMOSTASIS), cause=sup(ct.Cause.PRE_EXISTING_LESION),
                places=[sup(ct.Landmark.SIGMOID_COLON)], status=contra(Status.PERFORMED, Status.PLANNED))
        yield 'clip for hemostasis', doc.build(), '45382'

    def test_act_kind_is_established_kind_and_every_per_code_key_names_it(self):
        from studio.interpretation.engine import facts as F
        expected = {'silent': ct.Kind.OTHER, 'unresolved': ct.Kind.OTHER, 'doubted': ct.Kind.OTHER,
                    'contradicted': ct.Kind.OTHER, 'negated': ct.Kind.OTHER, 'supported': ct.Kind.SNARE,
                    'clip for hemostasis': ct.Kind.BLEEDING_CONTROL}
        for name, R, code in self.shapes():
            with self.subTest(kind=name):
                label = F.established_kind(R, E(2))
                self.assertEqual(label, expected[name])
                self.assertEqual(Q.act_kind(R, E(2), (ct.Kind.SNARE,)), label)
                keys = {entry.fact for entry in EV.decide(code, (), R).held_facts if entry.fact.startswith('conflict:')}
                self.assertLessEqual(keys, {f'conflict:{label.value}'})
        self.assertIs(Q.act_kind(colonoscopy().build(), None, (ct.Kind.SNARE,)), ct.Kind.SNARE)  # no act: the group's

    def test_g3_28_shape_4_names_the_bleeding_control(self):
        *_, (_name, R, code) = self.shapes()
        found, spec = renderer_words(R, (code, 2))[code]
        self.assertEqual((found.item.held.fact, found.item.message),
                         ('conflict:bleeding_control', Q.MessageId.CONFLICT_ATTRIBUTE))
        self.assertIn('the bleeding control', spec.question)
        self.assertNotIn('clip placement', spec.question + spec.reason)

    def test_g3_28_shapes_2_to_4_through_the_renderers_calls(self):
        """g3c's shapes 2-4 (build list B9 (ii)), through jobs.word_item and the service questions' held-fact sentence
        (customer_api.held_fact_words): shape 2 - an act E2 whose kind is not established beside "No polyp was removed.",
        45385 on E2 (its item) and 45378 alone (the service question coverage keys); shape 3 - a lift injection E4 whose
        part_of names that E2, 45381 on E4; shape 4 - the clip for hemostasis, 45382 on it and 45378 alone. Each names
        "another act" or "the bleeding control", never "the snare removal" or "the clip placement"."""
        from studio.customer_api import held_fact_words
        for name, kind in (('silent', SILENT), ('unresolved', unres(ct.Kind.SNARE)),
                           ('doubted', doubted(ct.Kind.SNARE, ct.Kind.SNARE, ct.Kind.BIOPSY)),
                           ('contradicted', contra(ct.Kind.SNARE, ct.Kind.BIOPSY))):
            with self.subTest(shape=2, kind=name):
                doc = colonoscopy(kind=kind)
                TE.denial_event(doc, number=3, kind=ct.Kind.SNARE)
                R = doc.build()
                found, spec = renderer_words(R, ('45385', 2), ('45378', 1))['45385']
                self.assertEqual(found.item.held.fact, 'conflict:other')
                self.assertNotIn('snare removal', spec.question + spec.reason)
                assessment = TA.run(R, ('45378', 1))
                asked = [question.item.item.fact for question in assessment.service_questions]
                self.assertEqual(asked, ['conflict:other'])
                self.assertEqual(held_fact_words(asked[0]),
                                 'A detail is needed: which statement about another act is right for this date.')
            if name in ('silent', 'unresolved'):
                with self.subTest(shape=3, kind=name):
                    doc.act(4, ct.Kind.INJECTION, places=[sup(ct.Landmark.SIGMOID_COLON)], part_of=sup(E(2)),
                            part_relation=sup(ct.PartRelation.LIFT_FOR))
                    found, spec = renderer_words(doc.build(), ('45381', 4), ('45378', 1))['45381']
                    self.assertEqual((found.item.held.fact, found.item.held.subject), ('conflict:other', E(2)))
                    self.assertIn('another act', spec.question)
                    self.assertNotIn('snare removal', spec.question + spec.reason)
        *_, (_name, R, code) = self.shapes()
        with self.subTest(shape=4):
            found, spec = renderer_words(R, (code, 2), ('45378', 1))[code]
            self.assertIn('the bleeding control', spec.question)
            assessment = TA.run(R, ('45378', 1))
            asked = [question.item.item.fact for question in assessment.service_questions]
            self.assertEqual(asked, ['conflict:bleeding_control'])
            self.assertEqual(held_fact_words(asked[0]), 'A detail is needed: which statement about the bleeding '
                                                        'control is right for this date.')
            for sentence in (spec.question, spec.reason, held_fact_words(asked[0])):
                self.assertNotIn('clip placement', sentence)


# --- AMENDMENT-2 4.3.3 item 3's plant test, the member-sentence half (step f3e's request R7) ----------------------------

PLANT_TABLES = {'P': 'people', 'N': 'sections', 'X': 'sessions', 'Y': 'anatomy', 'L': 'lesions', 'E': 'events'}


def enriched_with_objects():
    """tests/v2/test_assess.enriched with a person P1, a section N1 and an anatomy entry Y1 of no facts of their own, so
    every family of the 38 slot attributes has an object to plant on (each table is read by coverage's Reader)."""
    R = TA.enriched().build()
    return dataclasses.replace(R, people={**R.people, Id(IdFamily.PERSON, 1): {}},
                               sections={**R.sections, Id(IdFamily.SECTION, 1): {}},
                               anatomy={**R.anatomy, Id(IdFamily.ANATOMY, 1): {}})


PLANT_SCENES = (('enriched, with a person, a section and an anatomy entry', enriched_with_objects, TA.TWO),
                ('egd_dilation', lambda: TA.egd_dilation().build(), (('43249', 2), ('43239', 3))),
                ('ercp', lambda: TA.ercp().build(), (('43262', 4), ('43264', 5), ('43273', 3))),
                ('push_enteroscopy', lambda: TA.push_enteroscopy().build(), (('44361', 2), ('44377', 2))),
                ('office_and_sigmoidoscopy', lambda: TA.office_and_sigmoidoscopy().build(), (('99213', 1),
                                                                                             ('45330', 2))))


def merged_view(written) -> Fact:
    """The ONE fact engine/facts gives a reader of an overfilled slot (AMENDMENT-2 4.3.3; tests/v2/test_facts'
    OverfilledSlotTests pins the builder to it): ``written`` its written facts as (state name, value)."""
    values = tuple(dict.fromkeys(value for _state, value in written))
    stated = {value for state, value in written if state != 'negated'}
    denied = tuple(dict.fromkeys(value for state, value in written if state == 'negated' and value not in stated))
    return Fact(result=ct.Result.UNRESOLVED, value=None, state=ct.FactState.CONTRADICTED, options=values,
                reasons=(ct.Reason.SLOT_OVERFULL,), spans=tuple(Span(3000 + 100 * n, 3060 + 100 * n)
                                                                 for n in range(len(written))),
                negated_values=denied)


def plant(R, family, subject, attribute, fact):
    """``R`` with ``subject``'s single-valued ``attribute`` the overfilled slot's merged view (``family`` None: the
    encounter's)."""
    if family is None:
        return dataclasses.replace(R, encounter={**R.encounter, attribute: (fact,)})
    name = PLANT_TABLES[family.value]
    table = dict(getattr(R, name))
    table[subject] = {**table[subject], attribute: (fact,)}
    return dataclasses.replace(R, **{name: table})


def unstated_members(item, before, kind, stated):
    """The members of the planted attribute's type ``kind`` (an enumeration) that ``item``'s Fill carries, outside the
    values the slot stated and outside what the same code's item carried without the plant (another event's or the
    catalogue's): each a value worded as stated that the slot denied or never wrote. Kind.OTHER is D254 rule 2's label
    for an act no kind names, never a value."""
    found = []
    for field in dataclasses.fields(item.fill):
        value = getattr(item.fill, field.name)
        prior = getattr(before.fill, field.name) if before is not None else None
        priors = prior if isinstance(prior, tuple) else (prior,)
        for member in value if isinstance(value, tuple) else (value,):
            if isinstance(member, kind) and member is not ct.Kind.OTHER and member not in priors \
                    and member not in stated:
                found.append((field.name, member))
    return found


class OverfilledSlotMemberSentences(SimpleTestCase):
    """AMENDMENT-2 4.3.3 item 3's plant test, the member-sentence half (step f3e's request R7; [R:truth-T2][R:truth-T5];
    4.4: "no member sentence words a value pass 1 did not state"): on five scenes of tests/v2/test_assess (two sessions
    enriched with the rarely-read attributes, an EGD dilation, an ERCP, a push enteroscopy, an office visit beside a
    flexible sigmoidoscopy), EVERY object of each family is given each of the 38 slot attributes (facts.SLOTS) as an
    overfilled slot in the three shapes - supported values only (A-v6), one supported beside negated others (A-v2),
    negated only - and every held code's ONE item is worded by the renderer's own call (jobs.word_item: a refusal
    raises). No Fill slot of the attribute's type carries a value the slot denied or did not write; a stated technique
    is the class of a stated device; the enteroscopy's incomplete form only where incomplete is stated (T5). Item 7: an
    item resting on the overfilled fact is that fact's own question, cause unestablished:slot_overfull, never "not
    documented" - for a device, which technique was used (T2)."""

    def test_every_slot_attribute_in_every_shape_on_every_object(self):
        from studio import jobs
        from studio.interpretation.engine import catalogue
        from studio.interpretation.engine import facts as F
        from tests.v2 import test_facts as TF

        runs = rested = moved = 0
        attributes = set()
        for name, build, codes in PLANT_SCENES:
            R0 = TA.dated(build())
            plain = {found.code: found.item for found in TA.run(R0, *codes).codes}
            for family, attribute in sorted(F.SLOTS, key=lambda key: (str(key[0]), key[1].value)):
                subjects = [None] if family is None else list(getattr(R0, PLANT_TABLES[family.value]))
                v1, v2, v3 = (TF.parsed(family, attribute, value) for value in TF.three_values(family, attribute))
                kind = type(v1) if isinstance(v1, enum.Enum) else None
                for subject in subjects:
                    for shape, written in (('supported only', [('supported', v1), ('supported', v2)]),
                                           ('one supported, others negated',
                                            [('supported', v1), ('negated', v2), ('negated', v3)]),
                                           ('negated only', [('negated', v1), ('negated', v2)])):
                        R = plant(R0, family, subject, attribute, merged_view(written))
                        stated = {value for state, value in written if state != 'negated'}
                        assessment = TA.run(R, *codes)
                        runs += 1
                        attributes.add((family, attribute))
                        for found in assessment.codes:
                            if found.item is None:
                                continue
                            with self.subTest(scene=name, attribute=attribute.value, subject=str(subject),
                                              shape=shape, code=found.code):
                                spec = jobs.word_item(found.item, found.key, assessment.combination, R, TA.TEXT)
                                before = plain[found.code]
                                moved += found.item != before
                                if kind is not None:
                                    self.assertEqual(unstated_members(found.item, before, kind, stated), [])
                                stated_class = found.item.fill.stated
                                if attribute is ct.Attribute.TECHNIQUE_DEVICE and stated_class is not None \
                                        and (before is None or before.fill.stated != stated_class):
                                    self.assertIn(stated_class, {catalogue.technique_class(device) for device in stated})
                                if attribute is ct.Attribute.COMPLETION and found.item.fill.incomplete \
                                        and not (before is not None and before.fill.incomplete):
                                    self.assertIn(ct.Completion.INCOMPLETE, stated)
                                if found.item.held.cause == 'unestablished:slot_overfull':
                                    rested += 1
                                    self.assertIsNot(found.item.message, Q.MessageId.NOT_DOCUMENTED)
                                    self.assertNotIn('not documented', (spec.question + spec.reason).lower())
        self.assertEqual(len(attributes), 38)
        self.assertGreater(runs, 1000)
        self.assertGreater(rested, 100)  # the plant reaches the member sentences, not only the FactSet
        self.assertGreater(moved, 100)

    def test_the_device_item_asks_which_technique(self):
        """Item 7 [R:truth-T2] on the dilation E2 of egd_dilation, its device overfilled - the plant test's three shapes
        and a balloon beside a bougie, stated or the bougie denied: 43249 and 43248 are held by the device's own hold
        (technique, cause unestablished:slot_overfull), asked "Which technique was used for the dilation ...", never
        "not documented"."""
        from studio import jobs
        D, S, N = ct.Device, 'supported', 'negated'
        for name, written in (('supported only', [(S, D.ENDOSCOPE), (S, D.COLD_SNARE)]),
                              ('one supported, others negated', [(S, D.ENDOSCOPE), (N, D.COLD_SNARE), (N, D.HOT_SNARE)]),
                              ('negated only', [(N, D.ENDOSCOPE), (N, D.COLD_SNARE)]),
                              ('balloon, bougie', [(S, D.BALLOON), (S, D.BOUGIE)]),
                              ('balloon, bougie denied', [(S, D.BALLOON), (N, D.BOUGIE)])):
            R = plant(TA.dated(TA.egd_dilation().build()), E(2).family, E(2), ct.Attribute.TECHNIQUE_DEVICE,
                      merged_view(written))
            assessment = TA.run(R, ('43249', 2), ('43248', 2))
            for found in assessment.codes:
                with self.subTest(device=name, code=found.code):
                    spec = jobs.word_item(found.item, found.key, assessment.combination, R, TA.TEXT)
                    self.assertEqual((found.item.held.fact, found.item.held.cause, found.item.message),
                                     ('technique', 'unestablished:slot_overfull', Q.MessageId.STATED_TECHNIQUE))
                    self.assertTrue(spec.question.startswith('Which technique was used for the dilation'))
                    self.assertNotIn('not documented', (spec.question + spec.reason).lower())

    def test_the_checker_finds_a_planted_value(self):
        """The checker's positive control: an item whose Fill carries a denied device, an unwritten one, or one only the
        unplanted item carried."""
        item = SimpleNamespace(fill=Q.Fill(code='45385', device=ct.Device.HOT_SNARE, group=(ct.Kind.SNARE,)))
        stated = {ct.Device.ENDOSCOPE}
        self.assertEqual(unstated_members(item, None, ct.Device, stated), [('device', ct.Device.HOT_SNARE)])
        self.assertEqual(unstated_members(item, item, ct.Device, stated), [])  # the unplanted item carried it
        self.assertEqual(unstated_members(item, None, ct.Device, {ct.Device.HOT_SNARE}), [])  # stated
        self.assertEqual(unstated_members(item, None, ct.Kind, set()), [('group', ct.Kind.SNARE)])
        self.assertEqual(unstated_members(SimpleNamespace(fill=Q.Fill(act=ct.Kind.OTHER)), None, ct.Kind, set()), [])


class OverfilledExaminationAlone(SimpleTestCase):
    """The step's NOTES, question Q-T2-ALONE, pinned as built: the colonoscopy's only examination E1 with its device slot
    overfilled, manual and endoscope both STATED, is a claimed digital examination (AMENDMENT-2 4.3.3 c: manual is
    written), so - as refute-r4a-r2 F1's ruling (D265) reads a claimed-manual examination alone - 45378's group has no
    positive candidate and its item is the code-level not-documented question, the device's own hold
    (unestablished:slot_overfull) beside it; AMENDMENT-2 4.3.7 says an overfilled device's item is never "not
    documented". With manual not stated (an endoscope written twice, or beside a denied manual) E1 is the colonoscopy's
    done examination and 45378 is READY (T2's refutation input, repaired)."""

    def test_as_built(self):
        D, S, N = ct.Device, 'supported', 'negated'
        for name, written, expected in (('manual, endoscope stated', [(S, D.MANUAL), (S, D.ENDOSCOPE)], 'held'),
                                        ('endoscope twice', [(S, D.ENDOSCOPE), (S, D.ENDOSCOPE)], 'ready'),
                                        ('endoscope, manual denied', [(S, D.ENDOSCOPE), (N, D.MANUAL)], 'ready'),
                                        ('both denied', [(N, D.MANUAL), (N, D.ENDOSCOPE)], 'ready')):
            with self.subTest(device=name):
                R = plant(colonoscopy(snare=False).build(), E(1).family, E(1), ct.Attribute.TECHNIQUE_DEVICE,
                          merged_view(written))
                found, spec = renderer_words(R, ('45378', 1))['45378']
                if expected == 'ready':
                    self.assertEqual((found.status.value, found.item), ('ready', None))
                    continue
                self.assertEqual(found.item.message, Q.MessageId.NOT_DOCUMENTED)
                self.assertIn(('performed_status', 'unestablished:slot_overfull'),
                              [(entry.fact, entry.cause) for entry in found.held_facts])
