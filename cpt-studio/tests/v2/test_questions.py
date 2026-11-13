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
round 1: Choose.test_rule_3_before_rule_4 (T1) and Worded (F2, F3, F4, F5 and 3.2.6 rule 2's item, D1).
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import wording
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import evaluate as EV
from studio.interpretation.engine import questions as Q
from studio.interpretation.engine import requirements as rq
from studio.interpretation.engine.requirements_table import Tag
from studio.interpretation.engine.types import HeldFact, ItemKind, Span
from tests.v2 import test_evaluate as TE
from tests.v2.evaluate_fixtures import SILENT, E, Status, X, colonoscopy, contra, doubted, sup, unit, unres
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
                for old in ('engine_catalogue.', 'catalogue.'):
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
        """F2: pass 2's unlisted doubt found in the snare's own unit pairs with it (3.2.6 rule 4); the scope question
        quotes that unit, which is the act's anchor too - never an empty statements slot."""
        doc = colonoscopy()
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.SNARE, X(1), unit(2)))
        found, worded = self.item('45385', doc.build())
        self.assertEqual((found.message, found.fill.statements, found.fill.words),
                         (Q.MessageId.STATEMENT_SCOPE, ((unit(2),),), (unit(2),)))
        self.assertEqual(worded.fact, 'statement_scope')

    def test_another_site_names_the_place_the_rule_read_on_the_lesion(self):
        """F3: "A 15 mm stricture (L1) was seen in the distal esophagus. Balloon dilation of the stricture to 15 mm was
        performed." - SITE reads the lesion's place (D29), so another-site's explanation names it."""
        doc = TE.dilation(lesion=sup(TE.L(1)))
        doc.lesion(1, lesion_places=[sup(ct.Landmark.DISTAL_ESOPHAGUS)])
        found, worded = self.item('43245', doc.build())
        self.assertEqual((found.message, found.fill.place), (Q.MessageId.ANOTHER_SITE, ct.Landmark.DISTAL_ESOPHAGUS))
        self.assertEqual(worded.kind, EXPLANATION)

    def test_the_stoma_class_misfit_by_approach_is_the_examination_class_explanation(self):
        """F4: 44406 with its approach established oral is the class's explanation, never the extent question."""
        doc = TE.Doc()
        doc.session(1, ct.SessionKind.EUS, tract=sup(ct.Tract.LOWER), reached=[sup(ct.Extent.STOMA)],
                    approach=sup(ct.Approach.ORAL))
        doc.entry(1, type=sup(ct.AnatomyType.STOMA))
        doc.exam(1)
        found, worded = self.item('44406', doc.build())
        self.assertEqual((found.message, found.fill.reached, worded.kind),
                         (Q.MessageId.EXAMINATION_CLASS, ct.Extent.STOMA, EXPLANATION))

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

    def test_rule_2_names_the_supporting_act_or_quotes_the_unit(self):
        """D1 (3.2.6 rule 2): 43274 citing the exchange sentence - the doubt names the placement and quotes the unit;
        beside a cited denial with no act, the doubt's words are the unit itself."""
        found, worded = self.item('43274', TE.UnlistedOnEvidence.exchange(), (unit(2),))
        self.assertEqual((found.message, found.fill.act, found.fill.words), (Q.MessageId.DOUBT, ct.Kind.STENT,
                                                                             (unit(2),)))
        doc = colonoscopy(snare=False)
        TE.denial_event(doc, kind=ct.Kind.REMOVAL)
        doc.unlisted.append(TE.unlisted(ct.UnlistedWhat.DOUBT, ct.Kind.BIOPSY, X(1), unit(3)))
        found, worded = self.item('45385', doc.build(), (Span(300, 325),))
        self.assertEqual((found.message, found.fill.words, found.fill.statements),
                         (Q.MessageId.DOUBT, (unit(3),), ((unit(3),),)))


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
