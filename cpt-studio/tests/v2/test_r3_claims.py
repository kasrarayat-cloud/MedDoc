"""Round r3's build, lane "claims" (DECISIONS D320's scope, D323's rulings): the question claims, the proof, the question
reader and the question settle - every input SYNTHETIC (invented ids, spans and words; tests/v2/evaluate_fixtures'
builders): no document is read and nothing is sent.

What each class pins:
- ProofClassTests (D318 (1), THE PROOF CLASS): a proof is void only when a quote lies outside the claim's own passages,
  overlaps another located quote, or is too short - never because of extra quotes inside them; every required passage
  set receives a quote of its own; a further quote lies inside a required set or the optional set; a reach's quotes lie
  inside its alternatives; at most proof.QUOTES_MAX quotes; the search is complete; a proof the probe's one-to-one rule
  located locates at the same spans. The three SHAPES step 1 long's old rule voided (r3-probe-2: q1.1.2, a statement's
  quote and an act's sentence a line break splits, quoted per unit; q1.1.5, one object quoted twice; q1.3.1, a reach's
  three true quotes) - the recorded answers themselves are pinned by the lane's re-check (r3b/claims NOTES 6).
- ProofInstructionTests (D318 (1)): the instruction states the rule as the locator reads it - its numbers are the
  locator's and the reader's constants, one constant each - and a proof that follows it is never voided.
- InstructionReadingTests (the repair pass, refutation RC-2): PROOF names every passage by the claim line's own fields -
  the units it cites and the cards it names, and (DECISIONS D324 (9), RF2-CLM-1; tests/v2/test_r3c_claims) a frame
  claim's value units - never by a place where the document says something; read clause by clause from what a reader
  sees (the card lines and the claim line), over every question form and the calibration kinds, every proof it permits
  locates, some proof does wherever one can, and the passages are not widened.
- RelationFormTests (D318 (3) and its second addendum): Q-REL asks the NARROWEST relation that settles the hold it
  serves, by the statement's class and status (question_claims.relation_form), derived per census row and witness cause
  from the engine's own plan; QB's lesson (D316: a denial whose umbrella place holds the act's is answerable "denies").
- RouteFormTests (D312): the stoma route's own question forms (a session's approach, an anatomy entry's type).
- DenialArmTests (D312 (1), mutant M10b): C7b-denial's filed-denial and doubt arms.
- CalibrationFloorTests (D319): one calibration item per request - H5's floor 1, H2 unchanged.
- SessionNotTests (D315 (6)): G1's exact set excludes an attempt and an act in doubt (probe-check4's ck4_g1.py scene).
- GuardTests (D323 F3): FINAL-V2 5.7 measure 4 holds for the lane's modules, with a planted control.
- OneVocabularyTests: the family vocabulary question_claims holds is asking's, member for member."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import random
import re
from collections.abc import Sequence
from itertools import permutations, product
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation.contract import appraise_read, appraise_schema, claims, proof, question_claims, settle
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, evaluate, pairing
from studio.interpretation.engine import facts as F
from tests.v2 import test_pairing as TPG
from tests.v2.evaluate_fixtures import (DC, ON, TEAM, E, Kind, L, Landmark, SessionKind, Status, X, Y, colonoscopy,
                                        fact, neg, sup, unit, unlisted, unres)

A = ct.Attribute
QC = question_claims
SC, SS = QC.SubjectClass, QC.SubjectStatus
PS = QC.PassageSet
FAM = asking.Family


def ranges_of(text: str, *words: str) -> PS:
    """The passage set of each ``words``' one occurrence in ``text`` (a maximal range each)."""
    out = []
    for item in words:
        assert text.count(item) == 1, item
        at = text.index(item)
        out.append((at, at + len(item)))
    return PS(tuple(out))


def units_of(text: str) -> list:
    """The units of ``text``: one per line, S1.. in order (their [start, end) offsets)."""
    out, at = [], 0
    for number, line in enumerate(text.split('\n')[:-1], start=1):
        start = text.index(line, at)
        out.append({'id': f'S{number}', 'start': start, 'end': start + len(line)})
        at = start + len(line)
    return out


def built_request(text: str, cards: Sequence[ct.Card], objects: dict, specs: Sequence, calibration: Sequence = (),
                  *, events: Sequence = (), sessions: Sequence = (), sections: Sequence = (), unlisted_: Sequence = (),
                  seed: str = 'seed') -> QC.QuestionRequest:
    """A question request built by the product's builder over a synthetic fact request (``cards``, ``objects``) and
    view (the units of ``text``, the stored records given)."""
    claim_set = SimpleNamespace(cards=tuple(cards), objects=objects)
    built = SimpleNamespace(framed='<<<DOCUMENT-0000000000000000 BEGIN>>>\nsynthetic\n<<<DOCUMENT-0000000000000000 END>>>',
                            claim_set=claim_set)
    view = {'units': units_of(text), 'events': list(events), 'sessions': list(sessions), 'sections': list(sections),
            'unlisted': list(unlisted_)}
    plan = asking.RequestPlan(tuple(specs), tuple(calibration), seed)
    return QC.build_question_request_fable(built, text, (), view, plan, 1, 1)


def located(text: str, item: QC.Item, quotes: Sequence[str]) -> proof.ProofLocation:
    return proof.locate(text, item.required, item.optional, quotes, item.alternatives)


# a hard-wrapped report: the cold-snare removal's sentence (E2) runs across S2 and S3 - one sentence, two units
WRAPPED = ('Colonoscopy report.\n'
           'A small sessile polyp in the sigmoid colon was removed with a\n'
           'cold snare and retrieved for histology without electrocautery.\n'
           'No biopsies of the rectum were taken during this procedure.\n'
           'The scope was advanced to the cecum without difficulty today.\n')
DENIAL_Q = 'No biopsies of the rectum were taken'
FIRST_HALF_Q = 'polyp in the sigmoid colon was removed'
SECOND_HALF_Q = 'retrieved for histology without electrocautery'
SCOPE_Q = 'advanced to the cecum without difficulty'


def _prototype_locate(text, required, optional, quotes, alternatives=()):
    """The probe prototype's locator, as step 1 long was read with it (QUOTES_MAX 2, the one-to-one assignment):
    kept here only as the reference a proof it located must still locate against, at the same spans."""
    if not quotes:
        return proof.ProofLocation(False, (), proof.PROOF_MISSING)
    if len(quotes) > 2:
        return proof.ProofLocation(False, (), proof.PROOF_UNLOCATED)
    if not all(proof.long_enough(quote) for quote in quotes):
        return proof.ProofLocation(False, (), proof.PROOF_SHORT)
    sets = [tuple(getattr(found, 'ranges', ())) for found in required]
    if any(not ranges for ranges in sets):
        return proof.ProofLocation(False, (), proof.PROOF_UNLOCATED)
    choices = [tuple(getattr(found, 'ranges', ())) for found in alternatives if getattr(found, 'ranges', ())]
    if not sets and not choices:
        return proof.ProofLocation(False, (), proof.PROOF_UNLOCATED)
    extra = tuple(getattr(optional, 'ranges', ())) if optional is not None else ()
    collapsed, offsets = proof._collapsed(text)
    found_at = [proof._occurrences(collapsed, offsets, proof.normalized(quote)) for quote in quotes]
    if any(not spans for spans in found_at):
        return proof.ProofLocation(False, (), proof.PROOF_UNLOCATED)

    def hit(index, ranges, chosen):
        return next((span for span in found_at[index] if proof._inside(span, ranges)
                     and all(span[1] <= other[0] or other[1] <= span[0] for other in chosen)), None)

    if choices:
        if sets:
            return proof.ProofLocation(False, (), proof.PROOF_UNLOCATED)
        for order in permutations(range(len(quotes))):
            for first in range(len(choices)):
                one = hit(order[0], choices[first], ())
                if one is None:
                    continue
                if len(order) == 1:
                    return proof.ProofLocation(True, (one,), '')
                for second in range(len(choices)):
                    if second == first:
                        continue
                    two = hit(order[1], choices[second], (one,))
                    if two is not None:
                        return proof.ProofLocation(True, (one, two), '')
        return proof.ProofLocation(False, (), proof.PROOF_UNLOCATED)
    if len(quotes) < len(sets) or len(quotes) > len(sets) + (1 if extra else 0):
        return proof.ProofLocation(False, (), proof.PROOF_UNLOCATED)
    targets = list(sets) + ([extra] if len(quotes) > len(sets) else [])
    for order in permutations(range(len(quotes))):
        chosen = []
        for quote_index, ranges in zip(order, targets):
            span = hit(quote_index, ranges, chosen)
            if span is None:
                break
            chosen.append(span)
        else:
            return proof.ProofLocation(True, tuple(chosen), '')
    return proof.ProofLocation(False, (), proof.PROOF_UNLOCATED)


# --- D318 (1): the proof class ------------------------------------------------------------------------------------------


class ProofClassTests(SimpleTestCase):
    """contract/proof.locate under DECISIONS D318 (1)."""

    def setUp(self) -> None:
        self.act = ranges_of(WRAPPED, 'A small sessile polyp in the sigmoid colon was removed with a\n'
                                      'cold snare and retrieved for histology without electrocautery.')
        self.denial = ranges_of(WRAPPED, 'No biopsies of the rectum were taken during this procedure.')
        self.scope = ranges_of(WRAPPED, 'The scope was advanced to the cecum without difficulty today.')

    def test_a_sentence_a_line_break_splits_may_be_quoted_per_unit(self) -> None:  # q1.1.2's shape (a Q-REL)
        found = proof.locate(WRAPPED, (self.denial, self.act), None, [DENIAL_Q, FIRST_HALF_Q, SECOND_HALF_Q])
        self.assertTrue(found.located, found)
        self.assertEqual([WRAPPED[start:end] for start, end in found.spans], [DENIAL_Q, FIRST_HALF_Q, SECOND_HALF_Q])
        whole = 'polyp in the sigmoid colon was removed with a cold snare'  # the sentence across the break, one quote
        self.assertTrue(proof.locate(WRAPPED, (self.denial, self.act), None, [DENIAL_Q, whole]).located)
        # the probe's rule voided the per-unit proof - the three right answers of step 1 long (D318 (1))
        self.assertFalse(_prototype_locate(WRAPPED, (self.denial, self.act), None,
                                           [DENIAL_Q, FIRST_HALF_Q, SECOND_HALF_Q]).located)

    def test_one_object_quoted_twice_locates(self) -> None:  # q1.1.5's shape (the part link, one object)
        self.assertTrue(proof.locate(WRAPPED, (self.act,), None, [FIRST_HALF_Q, SECOND_HALF_Q]).located)
        self.assertFalse(_prototype_locate(WRAPPED, (self.act,), None, [FIRST_HALF_Q, SECOND_HALF_Q]).located)

    def test_a_reachs_quotes_lie_inside_its_alternatives(self) -> None:  # q1.3.1's shape (three true quotes)
        alternatives = (self.scope, self.act)
        quotes = ['advanced to the cecum', 'without difficulty today', FIRST_HALF_Q]
        self.assertTrue(proof.locate(WRAPPED, (), None, quotes, alternatives).located)
        self.assertFalse(_prototype_locate(WRAPPED, (), None, quotes, alternatives).located)
        self.assertFalse(proof.locate(WRAPPED, (), None, [SCOPE_Q, DENIAL_Q], alternatives).located)  # one outside

    def test_a_further_quote_outside_the_claims_passages_voids_the_proof(self) -> None:
        found = proof.locate(WRAPPED, (self.denial, self.act), None, [DENIAL_Q, FIRST_HALF_Q, SCOPE_Q])
        self.assertEqual((found.located, found.reason), (False, proof.PROOF_UNLOCATED))
        self.assertFalse(proof.locate(WRAPPED, (self.denial, self.act), None,
                                      [DENIAL_Q, FIRST_HALF_Q, 'removed with a hot snare']).located)  # a paraphrase

    def test_an_overlapping_quote_voids_the_proof(self) -> None:
        found = proof.locate(WRAPPED, (self.denial, self.act), None,
                             [DENIAL_Q, FIRST_HALF_Q, 'the sigmoid colon was removed with'])
        self.assertEqual((found.located, found.reason), (False, proof.PROOF_UNLOCATED))
        # the same words twice need two occurrences: here there is one
        self.assertFalse(proof.locate(WRAPPED, (self.denial, self.act), None,
                                      [DENIAL_Q, FIRST_HALF_Q, FIRST_HALF_Q]).located)

    def test_a_short_quote_among_good_ones_voids_the_proof(self) -> None:
        found = proof.locate(WRAPPED, (self.denial, self.act), None, [DENIAL_Q, FIRST_HALF_Q, 'cold snare'])
        self.assertEqual((found.located, found.reason), (False, proof.PROOF_SHORT))

    def test_every_required_set_receives_a_quote_of_its_own(self) -> None:
        # two quotes of the act alone prove nothing of the statement it is paired with (b.0, R3D-06)
        self.assertFalse(proof.locate(WRAPPED, (self.denial, self.act), None, [FIRST_HALF_Q, SECOND_HALF_Q]).located)
        self.assertFalse(proof.locate(WRAPPED, (self.denial, self.act), None, [DENIAL_Q]).located)
        # two required sets that coincide (a frame value inside the act's own passage) need two distinct quotes
        self.assertFalse(proof.locate(WRAPPED, (self.act, self.act), None, [FIRST_HALF_Q]).located)
        self.assertTrue(proof.locate(WRAPPED, (self.act, self.act), None, [FIRST_HALF_Q, SECOND_HALF_Q]).located)
        self.assertFalse(proof.locate(WRAPPED, (self.act, PS(())), None, [FIRST_HALF_Q, SECOND_HALF_Q]).located)

    def test_a_further_quote_may_lie_in_the_optional_set(self) -> None:
        found = proof.locate(WRAPPED, (self.act,), self.scope, [FIRST_HALF_Q, SCOPE_Q, SECOND_HALF_Q])
        self.assertTrue(found.located, found)
        self.assertFalse(proof.locate(WRAPPED, (self.act,), self.scope, [SCOPE_Q]).located)  # the required one first

    def test_the_cap_is_eight_and_one_more_is_a_flood(self) -> None:
        words = ['withdrawal', 'inspection', 'proceeded', 'carefully', 'throughout', 'everything', 'remarkable',
                 'otherwise', 'satisfactory', 'preparation', 'excellent', 'visualization', 'complete', 'mucosal',
                 'surfaces', 'examined', 'thoroughly', 'retroflexion']
        text = ' '.join(words) + '\n'
        passage = PS(((0, len(text) - 1),))
        pieces = [' '.join(words[index:index + 2]) for index in range(0, len(words), 2)]  # nine quotes, none overlapping
        self.assertEqual((proof.QUOTES_MAX, len(pieces)), (8, 9))
        self.assertTrue(proof.locate(text, (passage,), None, pieces[:8]).located)
        found = proof.locate(text, (passage,), None, pieces)
        self.assertEqual((found.located, found.reason), (False, proof.PROOF_BOUND))
        self.assertGreaterEqual(proof.QUOTES_MAX, 6)  # D318 (1): a flood cap of at least 6

    def test_the_search_is_complete(self) -> None:
        """A first fit is not enough: the quote the act's set needs occurs twice, its first occurrence overlapping the
        nested value passage's only quote; the second occurrence fits. The probe's first-fit rule voided it."""
        text = 'cold snare removal of the polyp was done; later a cold snare removal of the stalk.\n'
        act = PS(((0, len(text) - 1),))
        value = ranges_of(text, 'removal of the polyp')
        quotes = ['cold snare removal', 'removal of the polyp']
        self.assertTrue(proof.locate(text, (act, value), None, quotes).located)
        self.assertFalse(_prototype_locate(text, (act, value), None, quotes).located)

    def test_the_search_bound_fails_closed(self) -> None:
        with mock.patch.object(proof, 'SEARCH_STEPS_MAX', 0):
            found = proof.locate(WRAPPED, (self.denial, self.act), None, [DENIAL_Q, FIRST_HALF_Q])
        self.assertEqual((found.located, found.reason), (False, proof.PROOF_UNLOCATED))

    def test_a_proof_the_one_to_one_rule_located_locates_at_the_same_spans(self) -> None:
        """Every proof the prototype's rule located (step 1 short and long were read with it) still locates, at the same
        spans, in the same order - over constructed cases of every shape it admitted (one, two or three objects, an
        optional set, a reach's alternatives), each quote occurring once in the text."""
        rng = random.Random(20261117)
        vocabulary = ['ascending', 'transverse', 'descending', 'sigmoid', 'rectal', 'cecal', 'hepatic', 'splenic',
                      'polypectomy', 'retrieval', 'withdrawal', 'inspection', 'biopsies', 'specimen', 'mucosa', 'lumen']
        checked = 0
        for _ in range(1200):
            words = [f'{rng.choice(vocabulary)}{index}' for index in range(24)]
            text = ' '.join(words) + '\n'
            cuts = sorted(rng.sample(range(1, 24), 3))
            bounds = [0, *cuts, 24]
            spans = []
            for low, high in zip(bounds, bounds[1:]):
                start = len(' '.join(words[:low])) + (1 if low else 0)
                spans.append((start, start + len(' '.join(words[low:high]))))
            sets = [PS((span,)) for span in spans]
            pick = rng.sample(range(4), rng.choice((1, 2, 3)))
            required = [sets[index] for index in pick[:max(1, len(pick) - rng.choice((0, 1)))]]
            optional = rng.choice([None] + [found for found in sets if found not in required])
            quotes = []
            for index in rng.sample(range(24), 2):
                quotes.append(' '.join(words[index:index + 2]))
            for alternatives in ((), tuple(required[:2])):
                req = () if alternatives else tuple(required)
                old = _prototype_locate(text, req, None if alternatives else optional, quotes, alternatives)
                if not old.located:
                    continue
                checked += 1
                new = proof.locate(text, req, None if alternatives else optional, quotes, alternatives)
                with self.subTest(text=text, quotes=quotes):
                    self.assertTrue(new.located)
                    self.assertEqual(new.spans, old.spans)
        self.assertGreater(checked, 100)


# --- D318 (1): the instruction states the rule as the locator reads it -------------------------------------------------


def _cards(*items: tuple) -> tuple[list, dict]:
    cards, objects = [], {}
    for card_id, card_type, family, stored, units in items:
        cards.append(ct.Card(card_id, card_type, tuple(units), None, None))
        objects[card_id] = (family, stored)
    return cards, objects


def described(spec, *found):
    return dataclasses.replace(spec, described=tuple(found))


DONE = (SC.ACT, SS.PERFORMED)


class ProofInstructionTests(SimpleTestCase):
    """DECISIONS D318 (1): PROOF states the rule exactly as the locator and the reader read it."""

    def test_the_numbers_are_the_locators_and_the_readers_constants(self) -> None:
        # QUOTES_MAX is ONE constant - appraise_schema's - read by the locator and the reader, never a copy
        for module in (proof, appraise_read):
            source = Path(module.__file__).read_text()
            with self.subTest(module=module.__name__):
                self.assertNotIn('\nQUOTES_MAX =', source)
                self.assertNotIn('QUOTES_MAX = ', source.replace('**QUOTES_MAX = 8, THE flood cap', ''))
        self.assertIn('from studio.interpretation.contract.appraise_schema import QUOTES_MAX\n',
                      Path(proof.__file__).read_text())
        self.assertIs(proof.QUOTES_MAX, appraise_schema.QUOTES_MAX)
        with mock.patch.object(appraise_schema, 'QUOTES_MAX', 1):  # the reader reads it where it is held
            read = appraise_read.read_questions(json.dumps({'verdicts': [
                {'claim': 'K1', 'verdict': 'supports', 'attached': 'yes', 'qualifiers': [], 'evidence': [],
                 'quotes': [DENIAL_Q, FIRST_HALF_Q]}], 'unlisted': []}), ['K1'], {'K1': ()}, 5)
            self.assertTrue(read.verdicts['K1'].quotes_bound)
        text = QC.PROOF
        self.assertIn(f'Give at most {appraise_schema.QUOTES_MAX} passages.', text)
        self.assertIn(f'at most {appraise_read.QUOTE_MAX_CHARS} characters long', text)
        self.assertIn(f'at least {proof.MIN_TOKENS} words and {proof.MIN_CHARS} characters other than spaces', text)
        self.assertIn('{cap}', QC.PROOF_TEMPLATE)  # the instruction is rendered from it, never a copy
        self.assertEqual(QC.PROOF, QC.PROOF_TEMPLATE.format(tokens=proof.MIN_TOKENS, chars=proof.MIN_CHARS,
                                                           longest=appraise_read.QUOTE_MAX_CHARS,
                                                           cap=appraise_schema.QUOTES_MAX))
        self.assertTrue(QC.APPRAISAL_INSTRUCTIONS_Q.endswith(text + '\n'))

    def test_every_clause_of_the_rule_is_stated(self) -> None:
        text = ' '.join(QC.PROOF.split())
        for clause in INSTRUCTION_CLAUSES + ('for a list of acts, from the units of one of them',
                                             'no two passages overlap',
                                             'The absence of a statement is never a passage'):
            with self.subTest(clause=clause):
                self.assertIn(clause, text)
        # the probe's words, which no locator ever read so: one passage per object, "from inside one unit"
        self.assertNotIn('Each passage is the exact words from inside one unit', text)

    def test_a_proof_that_follows_the_instruction_is_never_voided(self) -> None:
        """Through the request builder: each form's passages, and a proof copied as the instruction says - one passage
        per named object (a split sentence per unit), one more from the cited units beyond the act's card for the
        author's part, any further passage from the cited units (a place's section head among them).
        InstructionReadingTests reads every form so."""
        text = ('PROCEDURE NOTE by the documenting clinician\n'
                'A small sessile polyp in the sigmoid colon was removed with a\n'
                'cold snare and retrieved for histology without electrocautery.\n'
                'No biopsies of the rectum were taken during this procedure.\n'
                'The scope was advanced to the cecum without difficulty today.\n'
                'The cecum was identified by the appendiceal orifice and valve.\n')
        cards, objects = _cards(('A2', ct.CardType.ACT, 'event', 'E2', ('S2', 'S3')),
                                ('A4', ct.CardType.ACT, 'event', 'E4', ('S4',)),
                                ('X1', ct.CardType.SESSION, 'session', 'X1', ('S5',)))
        section = {'id': 'N0', 'start': {'units': ['S1']}}
        event = {'id': 'E2', 'entry': {'claim': {'value': 'documenting_clinician', 'inherited_from': 'N0'},
                                       'sources': [{'units': ['S1']}], 'checks': {'integrity': 'passed'},
                                       'reasons': []}}
        session = {'id': 'X1', 'reached': [{'claim': {'value': 'cecum'}, 'sources': [{'units': ['S6']}],
                                            'checks': {'integrity': 'passed'}, 'reasons': []}]}
        rel = described(asking.QuestionSpec(FAM.Q_REL, 'rel.deny', ('E4', 'E2'), None, '', False, ('E4', 'E2'),
                                            census='R1'), (SC.STATEMENT, SS.DENIED), DONE)
        entry = described(asking.QuestionSpec(FAM.Q_FACT, 'fact.entry', ('E2',), A.ENTRY, 'documenting_clinician',
                                              False, ('E2',), value_passage='frame', census='F1'), DONE)
        reach = described(asking.QuestionSpec(FAM.Q_FACT, 'fact.reached', ('X1',), A.REACHED, 'cecum', False, ('X1',),
                                              value_passage='source', census='F8'), (SC.SESSION, SS.NONE))
        place = described(asking.QuestionSpec(FAM.Q_FACT, 'fact.target.places', ('E2',), A.TARGET_PLACES,
                                              'sigmoid_colon', False, ('E2',), value_passage='section_head',
                                              census='F1'), DONE)
        built = built_request(text, cards, objects, [rel, entry, reach, place], events=[event], sessions=[session],
                              sections=[section])
        by_form = {item.spec.form: item for item in built.items}
        heading = 'PROCEDURE NOTE by the documenting'
        follows = {
            'rel.deny': [DENIAL_Q, FIRST_HALF_Q, SECOND_HALF_Q],  # the statement, then the act's sentence per unit
            'fact.entry': [FIRST_HALF_Q, heading, SECOND_HALF_Q],  # the act, the author's place, a further act unit
            'fact.reached': [SCOPE_Q, 'identified by the appendiceal orifice'],  # the session, where it says the reach
            'fact.target.places': [FIRST_HALF_Q, heading],  # the act, and the heading of its part
        }
        for form, quotes in follows.items():
            with self.subTest(form=form):
                self.assertTrue(located(text, by_form[form], quotes).located, (form, quotes))
        breaks = {  # each a quote from a place the instruction never allows
            'rel.deny': [DENIAL_Q, FIRST_HALF_Q, SCOPE_Q],
            'fact.entry': [FIRST_HALF_Q, heading, DENIAL_Q],
            'fact.reached': [SCOPE_Q, DENIAL_Q],
            'fact.target.places': [heading],  # the act's own passage gets no quote
        }
        for form, quotes in breaks.items():
            with self.subTest(form=form, broken=True):
                self.assertFalse(located(text, by_form[form], quotes).located, (form, quotes))

    def test_a_list_of_acts_is_proven_from_one_of_them(self) -> None:  # Q-ABSORB: "from the units of one of them"
        text = WRAPPED + 'All of the above was done by an earlier clinician.\n'
        cards, objects = _cards(('A2', ct.CardType.ACT, 'event', 'E2', ('S2', 'S3')),
                                ('A4', ct.CardType.ACT, 'event', 'E4', ('S4',)))
        absorb = described(asking.QuestionSpec(FAM.Q_ABSORB, 'absorb', ('u:0',), None, '', False, ('u:0', 'acts:X1'),
                                               acts=('E2', 'E4'), census='U3'), (SC.UNLISTED, SS.DOUBTS))
        built = built_request(text, cards, objects, [absorb], unlisted_=[{'units': ['S6'], 'what': 'doubt'}])
        item = built.items[0]
        self.assertTrue(located(text, item, ['All of the above was done by', FIRST_HALF_Q]).located)
        self.assertTrue(located(text, item, ['All of the above was done by', FIRST_HALF_Q, DENIAL_Q]).located)
        self.assertFalse(located(text, item, [FIRST_HALF_Q, DENIAL_Q]).located)  # the entry's own words are needed


# --- the repair pass (refutation RC-2): the instruction read as a reader reads it ---------------------------------------
#
# RC-2 (the lane's refutation, reproduced by its verifier): PROOF named two passages by "where the document says it" - a
# reach's ("the units where the document says it count as the session's") and the date of service's, the author's or
# the part's ("at least one more from where the document says it") - wider than what the locator reads (the value
# passage: pass 1's integrity-passed sources of that value, the inherited section's start and its own fact's sources),
# and it never named a performer's value passage at all. A proof that followed it - an impression that restates the
# reach, a signature, a "Date of service" header - was voided (proof_unlocated) and a right answer held. THE CLASS RULE:
# every passage the instruction names is named by the claim line's own fields - the units it cites (exactly the union of
# the claim's passages) and the cards it names (their card lines list their units) - so a proof that follows it always
# lies inside the locator's sets. The passages are NOT widened: a place that merely restates a value is not where pass 1
# established it for this fact, and a quote there would be a hollow proof (DECISIONS D313).
#
# ``InstructionReader`` reads PROOF clause by clause - each clause must be stated in exactly one form it knows: the
# repaired one, or the one RC-2 refuted - and builds every proof that set of clauses permits from what a reader of the
# request sees: the document's words, the card lines (each card's kind and units) and the claim line (the cards it names,
# the units it cites). ``says`` - where a test document says a value - exists only for the refuted form's reading; the
# repaired form never names such a place.

INSTRUCTION_CLAUSES = (  # the repaired form of each passage clause, literally (whitespace runs read as one space)
    'copy passages of the document that show the claim is true, every one from the units the claim cites.',
    'Copy at least one passage from the units of each act, statement, lesion, session, anatomy entry or unlisted entry '
    'the claim names',
    # DECISIONS D324 (9) (RF2-CLM-1): the per-object clause now states the act's own passage's heading rule (a heading
    # never serves as the quote for an act's own passage), and the frame and heading clauses name the frame value passage
    # by the claim line's value field and exempt it from the heading ban. Moved by the r3c claims lane (old -> new): the
    # 'session', 'frame' and 'heading' repaired forms; the r3b repair pass's forms kept as their 'rf2' forms below.
    # DECISIONS D325 (4) (L3P-2: every Q-FACT form takes the asked fact's own sources as a value passage, so a claim that
    # names a session may carry value units): the 'session' clause leaves the claim's value units out of the session's
    # passage. Moved by the r3d claims lane (old -> new): '...that no other card it names lists; for an act, ...' ->
    # '...that no other card it names lists and that is not one of the claim's value units; for an act, ...'; the r3c
    # form kept as its 'd324' form below.
    'the units its card lists, and, for a session, every other unit the claim cites that no other card it names lists '
    "and that is not one of the claim's value units; for an act, a statement, a lesion or an anatomy entry, that "
    'passage never holds the words of a heading.',
    "Where the claim's line gives value units (\"value at\"), copy at least one more passage from those units, which "
    'may hold the words of a heading; if it gives no unit there, the claim cannot be proven.',
    'Copy any further passage from the units the claim cites.',
    "Never copy the words of a heading from the units an act's, a statement's, a lesion's or an anatomy entry's card "
    "lists, except from the claim's value units, and except that, for a claim about where an act was done, a further "
    'passage may be the heading of the part of the document the act is told in, which the claim cites.',
    'a sentence that a line break splits across two units may be copied as one passage from each unit, or as one '
    'passage when one card the claim names lists both units.',
)
_CLAUSE_FORMS = {  # each clause's known forms: the repaired (INSTRUCTION_CLAUSES) and the one RC-2 refuted - and, for the
    # three clauses DECISIONS D324 (9) moved, the r3b repair pass's form RF2-CLM-1 refuted ('rf2', int4's text)
    'bound': {'repaired': INSTRUCTION_CLAUSES[0],
              'refuted': 'copy passages of the document that show the claim is true. Copy at least one passage'},
    'objects': {'repaired': INSTRUCTION_CLAUSES[1],
                'refuted': 'Copy at least one passage from the units of each act, statement, lesion, session or '
                           'unlisted entry the claim names'},
    'session': {'repaired': INSTRUCTION_CLAUSES[2],
                # the r3c claims lane's form (DECISIONS D324 (9); int5's text): a session's passage took every other
                # unit the claim cites that no other card it names lists - value units included
                'd324': 'the units its card lists, and, for a session, every other unit the claim cites that no other '
                        'card it names lists; for an act, a statement, a lesion or an anatomy entry, that passage '
                        'never holds the words of a heading.',
                'rf2': 'the units its card lists, and, for a session, every other unit the claim cites that no other card '
                       'it names lists. Where',
                'refuted': "for what a session reached or examined, the units where the document says it count as the "
                           "session's"},
    'frame': {'repaired': INSTRUCTION_CLAUSES[3],
              'rf2': 'Where the claim says on what date an act was done, who did it or who wrote the part of the '
                     "document it is told in, copy at least one more: from the units the claim cites beyond those the "
                     "act's card lists, or, if it cites none beyond them, from the act's own units, where they say it.",
              'refuted': 'where the claim refers to the date of service, the author of the document or the part of the '
                         'document an act is told in, at least one more from where the document says it.'},
    'further': {'repaired': INSTRUCTION_CLAUSES[4],
                'refuted': 'Copy any further passage only from those same units, or, for a claim about where an act '
                           'was done, from the heading of the part of the document it is told in.'},
    'heading': {'repaired': INSTRUCTION_CLAUSES[5],
                'rf2': "Never copy the words of a heading from the units an act's, a statement's, a lesion's or an "
                       "anatomy entry's card lists, except that, for a claim about where an act was done, a further "
                       'passage may be the heading of the part of the document the act is told in, which the claim '
                       'cites.',
                'refuted': 'never the words of a heading above an act, a statement or a lesion',
                # the repair pass's own first wording, never shipped: its exception reads as lifting the ban for the
                # act's OWN passage of a place claim (test_the_first_repaired_heading_clause_...)
                'first-repair': "Never copy the words of a heading from the units an act's, a statement's, a lesion's or "
                                "an anatomy entry's card lists, except that heading for a claim about where the act was "
                                'done.'},
    'split': {'repaired': INSTRUCTION_CLAUSES[6],
              'refuted': 'a sentence that a line break splits across two units may be copied as one passage or as one '
                         'passage from each unit.'},
}
# what a claim's sentence says, as a reader tells it from the sentence (the forms that render it)
_SAYS_DATE_DOER_OR_AUTHOR = frozenset({'fact.date_relation', 'fact.performer', 'fact.performer_person', 'fact.entry'})
_REFERS_TO_DATE_AUTHOR_OR_PART = frozenset({'fact.date_relation', 'fact.entry'})  # the refuted clause's three
_ABOUT_A_REACH = frozenset({'fact.reached', 'fact.reached_anatomy', 'fact.stations'})  # what a session reached/examined
_ABOUT_A_PLACE = frozenset({'fact.target.places'})  # where an act was done
_CARD_LINE = re.compile(r'^(?P<card>[A-Z]+\d+): (?P<phrase>.+?) (?:told|described|beginning) at '
                        r'(?P<units>S\d+(?:(?:, | and )S\d+)*)(?:, in its own words .*)?\.$')
_CLAIM_LINE = re.compile(r'^(?P<claim>K\d+) \(about (?P<about>.+?); names (?P<names>.+?); cites (?P<cites>.+?)'
                         r'(?:; value at (?P<value>.+?))?; proof\): (?P<sentence>.+)$')
_CUT_KINDS = {'repaired': frozenset({'act', 'lesion', 'anatomy'}), 'refuted': frozenset({'act', 'lesion'}),
              'first-repair': frozenset({'act', 'lesion', 'anatomy'}), 'rf2': frozenset({'act', 'lesion', 'anatomy'})}


def phrase_units(phrase: str) -> list[str]:
    """claims.units_phrase (and claims.joined) read back: 'S1, S2 and S5' -> ['S1', 'S2', 'S5']."""
    return [part for chunk in phrase.split(', ') for part in chunk.split(' and ')]


def _card_kind(phrase: str) -> str:
    for start, kind in (('a session', 'session'), ('a lesion', 'lesion'), ('an anatomy entry', 'anatomy'),
                        ('a part of the document', 'section'), ('a statement no other card', 'unlisted'),
                        ('an act', 'act')):
        if phrase.startswith(start):
            return kind
    raise AssertionError(phrase)


@dataclasses.dataclass(frozen=True)
class Seen:
    """What a reader sees of one built request: the document, its units in order, the heading words (each part's start),
    each card's kind and units (its card line), each claim line's fields (about, names, cites, sentence) and - DECISIONS
    D324 (9) - its value units (``values``: claim id -> the units its "value at" field gives, () for "no unit"; a line
    with no such field has no entry)."""
    text: str
    units: dict
    order: tuple
    cards: dict
    lines: dict
    headings: tuple
    values: dict = dataclasses.field(default_factory=dict)


def seen_of(built: QC.QuestionRequest, text: str, headings: Sequence[tuple[int, int]]) -> Seen:
    turn = built.request.body['messages'][0]['content'][0]['text']
    cards_part = turn.split('\n\n' + claims.CARDS_HEADING + '\n', 1)[1]
    cards_part, claims_part = cards_part.split('\n\n' + QC.QUESTIONS_HEADING + '\n', 1)
    cards = {}
    for line in cards_part.split('\n'):
        found = _CARD_LINE.match(line)
        assert found, line
        cards[found['card']] = (_card_kind(found['phrase']), tuple(phrase_units(found['units'])))
    lines, values = {}, {}
    for line in claims_part.split('\n'):
        found = _CLAIM_LINE.match(line)
        assert found, line
        lines[found['claim']] = (found['about'], phrase_units(found['names']), phrase_units(found['cites']),
                                 found['sentence'])
        if found['value'] is not None:
            values[found['claim']] = (() if found['value'] == QC.VALUE_NONE else tuple(phrase_units(found['value'])))
    units = {unit['id']: (unit['start'], unit['end']) for unit in units_of(text)}
    return Seen(text, units, tuple(units), cards, lines, tuple(headings), values)


@dataclasses.dataclass(frozen=True)
class Marks:
    """A test document's own marks: ``says`` - (subject, attribute) or ('reach', value) -> the units where the document
    says that value (pass 1's source or a restatement), read ONLY by the refuted form ("where the document says it");
    ``say_it`` - (subject, attribute) -> the span of the words inside the act's own units that say its date, its doer or
    its author (the repaired form's "where they say it"); ``part_heading`` - subject -> the units of the heading of the
    part of the document it is told in."""
    says: dict = dataclasses.field(default_factory=dict)
    say_it: dict = dataclasses.field(default_factory=dict)
    part_heading: dict = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(frozen=True)
class Role:
    """One passage a proof needs: the units it may come from, whether heading words may be in it, the words it must
    hold (``must``) - or, for "where they say it", that it must hold words that say it (``says_it``) - and the named
    cards whose units a split sentence may span."""
    units: frozenset
    headings_allowed: bool
    must: tuple | None = None
    says_it: bool = False
    cards: tuple = ()
    heading_units: frozenset = frozenset()  # units whose heading words this role may copy


def _tokens(text: str, start: int, end: int) -> list[tuple[int, int]]:
    return [(start + found.start(), start + found.end()) for found in re.finditer(r'\S+', text[start:end])]


def _apart(spans: Sequence[tuple[int, int]]) -> bool:
    ordered = sorted(spans)
    return all(first[1] <= second[0] for first, second in zip(ordered, ordered[1:]))


class InstructionReader:
    """PROOF read clause by clause (``forms``: clause -> 'repaired' | 'refuted'), and the proofs it permits for an item
    from what the reader sees (``proofs``)."""

    def __init__(self, proof_text: str) -> None:
        text = ' '.join(proof_text.split())
        self.forms = {}
        for clause, forms in _CLAUSE_FORMS.items():
            stated = [name for name, words in forms.items() if words in text]
            if len(stated) != 1:
                raise AssertionError(f'PROOF states its {clause!r} clause in no form this reader knows ({stated}): a '
                                     'change of the instruction needs its reading here')
            self.forms[clause] = stated[0]

    def repaired(self, clause: str) -> bool:
        return self.forms[clause] == 'repaired'

    def roles(self, seen: Seen, item: QC.Item, groups: Sequence[tuple[str, ...]],
              marks: Marks) -> tuple[list[Role], frozenset]:
        """Every passage the instruction requires of ``item``'s claim, and the units a further passage may come from."""
        about, names, cites, sentence = seen.lines[item.claim][:4]
        cited = frozenset(cites)
        listed = {card: frozenset(seen.cards[card][1]) for group in groups for card in group}
        form, subject = item.spec.form, item.spec.subjects[0]
        attribute = item.spec.attribute.value if item.spec.attribute is not None else ''
        out = []
        for group in groups:
            if len(group) > 1:  # a list of acts: from the units of one of them
                units = frozenset().union(*(listed[card] for card in group))
                out.append(Role(units & cited if self.repaired('bound') else units, False, cards=group))
                continue
            card = group[0]
            kind = seen.cards[card][0]
            if kind == 'anatomy' and not self.repaired('objects'):
                continue  # the refuted form names no anatomy entry
            units = listed[card] & cited if self.repaired('bound') else listed[card]
            if kind == 'session':
                if self.forms['session'] in ('repaired', 'd324', 'rf2'):  # rf2: the same reading, less the act's rule
                    others = frozenset().union(*(found for name, found in listed.items() if name != card))
                    # DECISIONS D325 (4): the repaired clause leaves the claim's value units out of the session's passage
                    values = frozenset(seen.values.get(item.claim, ())) if self.repaired('session') else frozenset()
                    units = (listed[card] | (cited - others - values)) & cited
                elif form in _ABOUT_A_REACH:
                    units = listed[card] | frozenset(marks.says.get(('reach', item.spec.value), ()))
            lifted = (frozenset(marks.part_heading.get(subject, ())) if self.forms['heading'] == 'first-repair'
                      and form in _ABOUT_A_PLACE else frozenset())
            if self.forms['heading'] == 'repaired' and self.forms['session'] not in ('repaired', 'd324'):
                # DECISIONS D324 (9): the heading clause's exemption of the claim's value units reaches the object's own
                # passage too unless the per-object clause says that passage never holds a heading's words
                lifted |= frozenset(seen.values.get(item.claim, ()))
            out.append(Role(units, kind in ('session', 'unlisted'), cards=(card,), heading_units=lifted))
        if self.repaired('frame'):
            # DECISIONS D324 (9): the frame value passage is named by the claim line's own "value at" field, and the
            # clause lets that passage hold a heading's words; "no unit" there: the claim cannot be proven (no passage)
            if item.claim in seen.values:
                out.append(Role(frozenset(seen.values[item.claim]), True))
        elif self.forms['frame'] == 'rf2' and form in _SAYS_DATE_DOER_OR_AUTHOR:
            # the r3b repair pass's clause, read LITERALLY (RF2-CLM-1): its "beyond" units fall under the heading clause
            # like any other unit a card lists - the r3b reader exempted them (``Role(beyond, True)``), which is why its
            # every-proof-locates property could not see the class
            act = groups[0][0]
            beyond = cited - listed[act]
            if beyond:
                out.append(Role(beyond, False))
            else:
                out.append(Role(listed[act] & cited, False, marks.say_it.get((subject, attribute)), True, (act,)))
        elif self.forms['frame'] == 'refuted' and form in _REFERS_TO_DATE_AUTHOR_OR_PART:
            out.append(Role(frozenset(marks.says.get((subject, attribute), ())), True))
        further = cited if self.repaired('further') else frozenset().union(*(role.units for role in out))
        if form in _ABOUT_A_PLACE and not self.repaired('further'):
            further |= frozenset(marks.part_heading.get(subject, ()))
        return out, further

    def _avoid(self, seen: Seen, unit: str, allowed: bool) -> list[tuple[int, int]]:
        """The heading words a passage inside ``unit`` must leave out."""
        if allowed:
            return []
        cut = _CUT_KINDS[self.forms['heading']]
        if not any(unit in units for kind, units in seen.cards.values() if kind in cut):
            return []
        low, high = seen.units[unit]
        return [span for span in seen.headings if span[0] < high and span[1] > low]

    def candidates(self, seen: Seen, role: Role, heading_units: frozenset = frozenset()) -> list[tuple[int, int]]:
        """Passages a reader could copy for ``role``: windows of 3 and 5 words at each unit's start, middle and end (or
        around the words it must hold), and sentences split across two units where the split clause allows one passage;
        each the document's own words, long enough, at most QUOTE_MAX_CHARS, clear of the heading words it must leave
        out, and occurring once in the document."""
        text, collapsed = seen.text, proof._collapsed(seen.text)[0]
        if role.says_it and role.must is None:
            return []  # no words inside the act's own units say it: the instruction cannot be followed
        spans = []
        for unit in sorted(role.units, key=seen.order.index):
            start, end = seen.units[unit]
            tokens = _tokens(text, start, end)
            if role.must is not None:
                if not (start <= role.must[0] and role.must[1] <= end):
                    continue
                first = next(index for index, token in enumerate(tokens) if token[1] > role.must[0])
                last = max(index for index, token in enumerate(tokens) if token[0] < role.must[1])
                for back in (0, 1):
                    for ahead in (0, 2, 4):
                        low, high = max(0, first - back), min(len(tokens) - 1, last + ahead)
                        spans.append((tokens[low][0], tokens[high][1]))
                continue
            for size in (3, 5):
                if len(tokens) < size:
                    continue
                for at in sorted({0, (len(tokens) - size) // 2, len(tokens) - size}):
                    spans.append((tokens[at][0], tokens[at + size - 1][1]))
        ordered = [unit for unit in seen.order if unit in role.units]
        for first, second in zip(ordered, ordered[1:]):
            if seen.order.index(second) != seen.order.index(first) + 1 or role.must is not None:
                continue
            if self.repaired('split') and not any(first in seen.cards[card][1] and second in seen.cards[card][1]
                                                  for card in role.cards):
                continue
            head, tail = _tokens(text, *seen.units[first]), _tokens(text, *seen.units[second])
            # a heading is no part of a sentence a line break splits (DECISIONS D324 (9)'s headed shapes: a part's
            # heading line opening the card of the act told below it)
            if len(head) >= 2 and len(tail) >= 2 and all(head[-2][0] >= high or tail[1][1] <= low
                                                         for low, high in seen.headings):
                spans.append((head[-2][0], tail[1][1]))
        by_unit: dict[str, list] = {}
        for span in dict.fromkeys(spans):
            quote = ' '.join(text[span[0]:span[1]].split())
            units = [unit for unit, (low, high) in seen.units.items() if low < span[1] and high > span[0]]
            exempt = heading_units | role.heading_units  # per unit: a passage's other unit keeps the ban (D324 (9))
            clear = all(all(span[1] <= low or high <= span[0]
                            for low, high in self._avoid(seen, unit, role.headings_allowed or unit in exempt))
                        for unit in units)
            if (proof.long_enough(quote) and len(quote) <= appraise_read.QUOTE_MAX_CHARS and clear
                    and collapsed.count(quote) == 1):
                by_unit.setdefault(units[0], []).append(span)
        # every unit the role allows is drawn on before any unit's second passage (a capped draw reaches them all)
        out = []
        for depth in range(max((len(found) for found in by_unit.values()), default=0)):
            out += [found[depth] for found in by_unit.values() if depth < len(found)]
        return out

    def proofs(self, seen: Seen, item: QC.Item, groups: Sequence[tuple[str, ...]], marks: Marks,
               limit: int = 96) -> list[list[str]]:
        """Proofs that follow the instruction: one passage per required role (none shared, none overlapping), alone and
        with one and two further passages - [] when some role has no passage a reader could copy. The combinations are
        drawn in a seeded order over the whole product (every role's every candidate reachable under the cap), the
        further passages in turn over every unit the further clause allows."""
        roles, further = self.roles(seen, item, groups, marks)
        lists = [self.candidates(seen, role)[:8] for role in roles]
        if not roles or any(not found for found in lists):
            return []
        place_heading = frozenset(marks.part_heading.get(item.spec.subjects[0], ())) if (
            item.spec.form in _ABOUT_A_PLACE) else frozenset()
        # DECISIONS D324 (9): the repaired heading clause exempts the claim's value units from the ban
        value = frozenset(seen.values.get(item.claim, ())) if self.forms['heading'] == 'repaired' else frozenset()
        extra = self.candidates(seen, Role(further, False), place_heading | value)
        quote = lambda span: ' '.join(seen.text[span[0]:span[1]].split())  # noqa: E731
        combos = list(product(*lists))
        random.Random(f'{item.spec.key}|{item.role}').shuffle(combos)
        out = []
        for number, chosen in enumerate(combos):
            if len(set(chosen)) != len(chosen) or not _apart(chosen):
                continue
            out.append([quote(span) for span in chosen])
            more = [span for span in extra if _apart((*chosen, span))]
            if more:
                first = more[number % len(more)]
                out.append([quote(span) for span in (*chosen, first)])
                second = more[(number + len(more) // 2) % len(more)]
                if second != first and _apart((*chosen, first, second)):
                    out.append([quote(span) for span in (*chosen, first, second)])
            if len(out) >= limit:
                break
        return out


def _span_of(text: str, words: str) -> tuple[int, int]:
    assert text.count(words) == 1, words
    at = text.index(words)
    return at, at + len(words)


def _cited_units(item: QC.Item, units: Sequence[dict]) -> list[str]:
    """The units overlapping the claim's passages - every PassageSet the locator reads."""
    found = []
    for passage in (*item.required, *item.alternatives, *((item.optional,) if item.optional else ())):
        for start, end in passage.ranges:
            found += [unit['id'] for unit in units if unit['start'] < end and unit['end'] > start]
    return [unit['id'] for unit in units if unit['id'] in set(found)]


# One synthetic report (invented words; one unit per line) holding every shape a question's passages take: an act told
# across a line break (E1), a denial (E2), a session with its examination (X1, E3) and pass 1's reach source, the part's
# start (N0, S1: the entry's source) with its performer and occasion sources, two lesions, an anatomy entry, a kept
# unlisted doubt, an earlier session (X2, E5), a part whose heading is one short line (N1) and one whose heading is the
# first words of a unit (N2, S28), a plan (E6), acts whose own words carry their date (E7, E8) or their doer (E10), a
# visit (E9), a session whose card and reach source are one sentence split by a line break (X3), an anatomy entry whose
# unit begins with a part's heading (Y2, N3) - and three units that RESTATE a value elsewhere (S18 the reach, S19 the
# author, S20 the date of service): never a passage of any claim.
DOC = ('PROCEDURE NOTE written by the documenting clinician for this visit\n'                # S1  N0's start
       'A small sessile polyp in the sigmoid colon was removed with a\n'                     # S2  E1
       'cold snare and retrieved for histology without any electrocautery.\n'               # S3  E1
       'No biopsies of the rectum were taken at any point of this procedure.\n'              # S4  E2 (a denial)
       'The colonoscope was advanced through the whole colon to the cecum.\n'               # S5  X1's card
       'The appendiceal orifice and the ileocecal valve were both identified.\n'            # S6  X1's reach source
       'This surveillance colonoscopy was performed because of earlier adenomas.\n'         # S7  E3, X1's examination
       'Every step was carried out personally by the documenting clinician.\n'              # S8  N0's performer source
       'The sedation and every procedure took place earlier this same morning.\n'          # S9  N0's occasion source
       'A 6 mm sessile polyp was seen in the mid sigmoid colon at 25 centimeters.\n'        # S10 L1
       'A second 4 mm polyp was seen in the distal rectum near the dentate line.\n'         # S11 L2
       'The patient has an end colostomy sited in the left lower quadrant.\n'              # S12 Y1
       'All of the above was done by an earlier gastroenterologist elsewhere.\n'           # S13 u:0 (a doubt)
       'A colonoscopy in January 2024 removed two small adenomas at that time.\n'          # S14 X2's card
       'That earlier colonoscopy in 2024 was also completed to its end.\n'                 # S15 E5, X2's examination
       'FINDINGS:\n'                                                                       # S16 N1's start
       'Cold forceps biopsies of the ascending colon were taken for histology.\n'          # S17 E4 (card S16-S17)
       'IMPRESSION: a complete colonoscopy, the cecum was reached and seen.\n'            # S18 restates the reach
       'Electronically signed by the documenting clinician, A. Current.\n'                 # S19 restates the author
       'Date of service: November 9, 2026, at this encounter only.\n'                      # S20 restates the date
       'Dr. A. Current, the attending gastroenterologist, led the whole procedure.\n'      # S21 P1
       'A follow-up colonoscopy is recommended in three years for surveillance.\n'         # S22 E6 (a plan)
       'Today I also clipped the polypectomy site in the sigmoid colon once.\n'           # S23 E7 (its own date)
       'A tattoo of carbon particles was injected beside the site, and this\n'             # S24 E8
       'marking was placed during this same procedure on the date of service.\n'           # S25 E8 (its own date)
       'An office visit for the bowel symptoms preceded the procedure this morning.\n'     # S26 E9 (a visit)
       'Dr. A. Current removed a second polyp from the descending colon herself.\n'        # S27 E10 (its own doer)
       'OPERATIVE FINDINGS The stalk of the polyp was ligated with an endoloop first.\n'   # S28 E11, N2's start words
       'The colonoscope was then advanced with gentle pressure all the way to the\n'       # S29 X3's card
       'terminal ileum, which was intubated for about five centimeters.\n'                # S30 X3's reach source
       'HISTORY The patient had a sigmoid colectomy with a primary anastomosis.\n')      # S31 Y2, N3's start words
_PASSED = {'checks': {'integrity': 'passed'}, 'reasons': []}


def _source(value: str, *units: str, inherited: str | None = None) -> dict:
    return {'claim': {'value': value, **({'inherited_from': inherited} if inherited else {})},
            'sources': [{'units': list(units)}] if units else [], **_PASSED}


DOC_CARDS = (('A1', ct.CardType.ACT, 'event', 'E1', ('S2', 'S3')), ('A2', ct.CardType.ACT, 'event', 'E2', ('S4',)),
             ('A3', ct.CardType.ACT, 'event', 'E3', ('S7',)), ('A4', ct.CardType.ACT, 'event', 'E4', ('S16', 'S17')),
             ('A5', ct.CardType.ACT, 'event', 'E5', ('S15',)), ('A6', ct.CardType.ACT, 'event', 'E6', ('S22',)),
             ('A7', ct.CardType.ACT, 'event', 'E7', ('S23',)), ('A8', ct.CardType.ACT, 'event', 'E8', ('S24', 'S25')),
             ('A9', ct.CardType.ACT, 'event', 'E9', ('S26',)), ('A10', ct.CardType.ACT, 'event', 'E10', ('S27',)),
             ('A11', ct.CardType.ACT, 'event', 'E11', ('S28',)), ('A12', ct.CardType.ACT, 'event', 'P1', ('S21',)),
             ('X1', ct.CardType.SESSION, 'session', 'X1', ('S5',)), ('X2', ct.CardType.SESSION, 'session', 'X2', ('S14',)),
             ('X3', ct.CardType.SESSION, 'session', 'X3', ('S29',)), ('L1', ct.CardType.LESION, 'lesion', 'L1', ('S10',)),
             ('L2', ct.CardType.LESION, 'lesion', 'L2', ('S11',)), ('Y1', ct.CardType.ANATOMY, 'anatomy', 'Y1', ('S12',)),
             ('Y2', ct.CardType.ANATOMY, 'anatomy', 'Y2', ('S31',)))
DOC_EVENTS = (
    {'id': 'E1', 'entry': _source('documenting_clinician', 'S1', inherited='N0'),
     'date_relation': _source('on_date_of_service', inherited='N0'),
     'performer': _source('documenting_team', inherited='N0')},
    {'id': 'E3'}, {'id': 'E5'},  # the two sessions' examinations: their units are their sessions' passages too
    {'id': 'E4', 'date_relation': _source('on_date_of_service', inherited='N1'),  # its part's start alone: "FINDINGS:"
     'performer': {'claim': {'value': '', 'state': None, 'inherited_from': None}, 'sources': [], **_PASSED}},  # silent
    {'id': 'E7', 'date_relation': _source('on_date_of_service', 'S23')},  # the act's own words ("Today")
    {'id': 'E8', 'date_relation': _source('on_date_of_service', 'S25')},  # inside the act's own two units
    {'id': 'E10', 'performer': _source('documenting_team', 'S27')},  # the act's own words name its doer
    {'id': 'E11', 'entry': _source('documenting_clinician', inherited='N2')})  # told in its part's first unit
DOC_SESSIONS = (
    {'id': 'X1', 'examination': {'claim': {'value': 'E3'}}, 'reached': [_source('cecum', 'S6')],
     'reached_anatomy': [_source('Y1', 'S12')], 'stations': [_source('ileum', 'S6')]},
    {'id': 'X2', 'examination': {'claim': {'value': 'E5'}}},
    {'id': 'X3', 'reached': [_source('terminal_ileum', 'S30')]})
DOC_SECTIONS = (
    {'id': 'N0', 'start': {'units': ['S1']}, 'owner': _source('documenting_clinician', 'S1'),
     'occasion': _source('on_date_of_service', 'S9'), 'performer': _source('documenting_team', 'S8')},
    {'id': 'N1', 'start': {'units': ['S16']}},
    {'id': 'N2', 'start': {'units': ['S28'], 'at': dict(zip(('start', 'end'), _span_of(DOC, 'OPERATIVE FINDINGS')))}},
    {'id': 'N3', 'start': {'units': ['S31'], 'at': dict(zip(('start', 'end'), _span_of(DOC, 'HISTORY')))}})
DOC_HEADINGS = (_span_of(DOC, 'PROCEDURE NOTE written by the documenting clinician for this visit'),
                _span_of(DOC, 'FINDINGS:\n')[:1] + (_span_of(DOC, 'FINDINGS:\n')[0] + len('FINDINGS:'),),
                _span_of(DOC, 'OPERATIVE FINDINGS'), _span_of(DOC, 'HISTORY'))
DOC_MARKS = Marks(
    says={('reach', 'cecum'): ('S6', 'S18'), ('reach', 'terminal_ileum'): ('S30',), ('reach', 'Y1'): ('S12',),
          ('reach', 'ileum'): ('S6',), ('E1', 'date_relation'): ('S9', 'S20'), ('E1', 'entry'): ('S1', 'S19'),
          ('E7', 'date_relation'): ('S23', 'S20'), ('E8', 'date_relation'): ('S25', 'S20'),
          ('E4', 'date_relation'): ('S16', 'S20')},
    say_it={('E7', 'date_relation'): _span_of(DOC, 'Today'), ('E8', 'date_relation'): _span_of(DOC, 'on the date of'),
            ('E10', 'performer'): _span_of(DOC, 'Dr. A. Current removed'),
            ('E10', 'performer_person'): _span_of(DOC, 'Dr. A. Current removed')},
    part_heading={'E1': ('S1',), 'E11': ('S28',)})
RESTATING = frozenset({'S18', 'S19', 'S20'})


def _planned(family, form: str, subjects: tuple, attribute=None, value: str = '', negated: bool = False,
             names: tuple | None = None, acts: tuple = (), kind: str = '') -> object:
    """A spec as the planner hands it: the value passage asking's own rule gives its attribute, each subject described
    as one its form is exact for (an act done, a session, a single lesion, a kept unlisted doubt, an anatomy entry).
    Moved by the r3d claims lane (DECISIONS D325 (4)): the rule is asking.value_passage_of's own - every Q-FACT form
    with no frame, reach or place rule now 'own' (was '')."""
    passage = asking.value_passage_of(attribute) if attribute is not None and family is FAM.Q_FACT else ''
    found = []
    for exact in QC.QUESTION_SOURCES[form].exact:
        for pair in (DONE, (SC.SESSION, SS.NONE), (SC.LESION, SS.SINGLE), (SC.UNLISTED, SS.DOUBTS),
                     (SC.ANATOMY, SS.NONE)):
            if pair in exact.pairs:
                found.append(pair)
                break
        else:
            found.append(sorted(exact.pairs, key=lambda pair: (pair[0].value, pair[1].value))[0])
    names = names if names is not None else subjects
    if kind:
        return asking.CalibrationSpec(kind, family, form, subjects, attribute, value, negated, names, passage,
                                      described=tuple(found))
    return asking.QuestionSpec(family, form, subjects, attribute, value, negated, names, value_passage=passage,
                               acts=acts, described=tuple(found))


def doc_shapes() -> list[tuple[str, object, str]]:
    """(name, spec, degenerate) for every question form on DOC - several shapes for the frame and reach forms - and the
    calibration kinds. ``degenerate`` names a shape no proof can ever locate (an empty or a too-short required passage:
    not this repair's class), where the instruction must not be followable either."""
    QF, P = FAM.Q_FACT, _planned
    return [
        ('rel', P(FAM.Q_REL, 'rel', ('E2', 'E1')), ''),
        ('rel.deny', P(FAM.Q_REL, 'rel.deny', ('E2', 'E1')), ''),
        ('rel.deny_or_doubt', P(FAM.Q_REL, 'rel.deny_or_doubt', ('E2', 'E1')), ''),
        ('rel.plan', P(FAM.Q_REL, 'rel.plan', ('E6', 'E1')), ''),
        ('onlesion', P(FAM.Q_ONLESION, 'onlesion', ('E1', 'L1'), A.TARGET_LESION, 'L1', True), ''),
        ('onlesion.group', P(FAM.Q_ONLESION, 'onlesion.group', ('E1', 'L1'), A.TARGET_LESION, 'L1', True), ''),
        ('lesion.distinct_from', P(FAM.Q_LESION, 'lesion.distinct_from', ('L1', 'L2'), A.DISTINCT_FROM, 'L2'), ''),
        ('lesion.not_member', P(FAM.Q_LESION, 'lesion.not_member', ('L1', 'L2'), A.DISTINCT_FROM, 'L2'), ''),
        ('lesion.not_member.any', P(FAM.Q_LESION, 'lesion.not_member.any', ('L1', 'L2'), A.DISTINCT_FROM, 'L2'), ''),
        ('absorb', P(FAM.Q_ABSORB, 'absorb', ('u:0',), names=('u:0', 'acts:X1'), acts=('E1', 'E4')), ''),
        ('date, the part and its occasion', P(QF, 'fact.date_relation', ('E1',), A.DATE_RELATION, 'on_date_of_service'),
         ''),
        ('date, the act\'s own unit', P(QF, 'fact.date_relation', ('E7',), A.DATE_RELATION, 'on_date_of_service'), ''),
        ('date, inside the act\'s two units', P(QF, 'fact.date_relation', ('E8',), A.DATE_RELATION,
                                                'on_date_of_service'), ''),
        ('entry, the part\'s start', P(QF, 'fact.entry', ('E1',), A.ENTRY, 'documenting_clinician'), ''),
        ('performer, the part and its source', P(QF, 'fact.performer', ('E1',), A.PERFORMER, 'documenting_team'), ''),
        ('performer, the act\'s own words', P(QF, 'fact.performer', ('E10',), A.PERFORMER, 'documenting_team'), ''),
        ('performer_person', P(QF, 'fact.performer_person', ('E10',), A.PERFORMER_PERSON, 'P1'), ''),
        ('date under a one-word heading', P(QF, 'fact.date_relation', ('E4',), A.DATE_RELATION, 'on_date_of_service'),
         'its value passage is the part\'s start alone, "FINDINGS:", shorter than any passage'),
        ('a silent performer', P(QF, 'fact.performer', ('E4',), A.PERFORMER, 'documenting_team'),
         'its value passage is empty (pass 1 filed nothing, nothing inherited)'),
        ('session', P(QF, 'fact.session', ('E1',), A.SESSION, 'X1', names=('E1', 'X1')), ''),
        ('session.not', P(QF, 'fact.session.not', ('E6',), A.SESSION, 'X1', True, names=('E6', 'X1')), ''),
        ('target.lesion', P(QF, 'fact.target.lesion', ('E1',), A.TARGET_LESION, 'L1'), ''),
        ('target.places', P(QF, 'fact.target.places', ('E1',), A.TARGET_PLACES, 'sigmoid_colon'), ''),
        ('target.places, its part\'s heading inside its own unit', P(QF, 'fact.target.places', ('E11',),
                                                                   A.TARGET_PLACES, 'sigmoid_colon'), ''),
        ('device, under a heading in its unit', P(QF, 'fact.technique.device', ('E11',), A.TECHNIQUE_DEVICE,
                                                  'cold_snare'), ''),
        ('device, under a one-line heading', P(QF, 'fact.technique.device', ('E4',), A.TECHNIQUE_DEVICE,
                                               'cold_forceps'), ''),
        ('purpose', P(QF, 'fact.purpose', ('E1',), A.PURPOSE, 'removal'), ''),
        ('duct', P(QF, 'fact.target.duct', ('E1',), A.TARGET_DUCT, 'biliary'), ''),
        ('part_link.any', P(QF, 'fact.part_link.any', ('E1',), A.PART_OF, '', True), ''),
        ('cause.not', P(QF, 'fact.cause.not', ('E1',), A.CAUSE, 'act_of_this_session', True), ''),
        ('lift.not', P(QF, 'fact.lift.not', ('E8',), A.PURPOSE, 'lift_for_resection', True), ''),
        ('hemostasis.not', P(QF, 'fact.hemostasis.not', ('E7',), A.PURPOSE, 'hemostasis', True), ''),
        ('visit.basis', P(QF, 'fact.visit.basis', ('E9',), A.VISIT_BASIS, 'medical_decision_making'), ''),
        ('reach, its examination and source', P(QF, 'fact.reached', ('X1',), A.REACHED, 'cecum'), ''),
        ('reach, a sentence split across card and source', P(QF, 'fact.reached', ('X3',), A.REACHED,
                                                             'terminal_ileum'), ''),
        ('reached_anatomy', P(QF, 'fact.reached_anatomy', ('X1',), A.REACHED_ANATOMY, 'Y1'), ''),
        ('stations', P(QF, 'fact.stations', ('X1',), A.STATIONS, 'ileum'), ''),
        ('approach', P(QF, 'fact.approach', ('X1',), A.APPROACH, 'through_stoma'), ''),
        ('type', P(QF, 'fact.type', ('Y1',), A.TYPE, 'stoma'), ''),
        ('type, under a heading in its unit', P(QF, 'fact.type', ('Y2',), A.TYPE, 'anastomosis'), ''),
        ('K1 date', P(QF, 'fact.date_relation', ('E1',), A.DATE_RELATION, 'on_date_of_service', True, kind='K1'), ''),
        ('K1 performer', P(QF, 'fact.performer', ('E1',), A.PERFORMER, 'documenting_team', True, kind='K1'), ''),
        ('K2 session', P(QF, 'fact.session', ('E1',), A.SESSION, 'X2', names=('E1', 'X2'), kind='K2'), ''),
        ('K4 onlesion', P(FAM.Q_ONLESION, 'onlesion', ('E1', 'L1'), A.TARGET_LESION, 'L1', True, kind='K4'), ''),
    ]


def doc_request(spec) -> tuple[QC.QuestionRequest, QC.Item]:
    cards, objects = _cards(*DOC_CARDS)
    questions, calibration = ([], [spec]) if isinstance(spec, asking.CalibrationSpec) else ([spec], [])
    built = built_request(DOC, cards, objects, questions, calibration, events=DOC_EVENTS, sessions=DOC_SESSIONS,
                          sections=DOC_SECTIONS, unlisted_=[{'units': ['S13'], 'what': 'doubt'}])
    return built, built.items[0]


def groups_of(spec, objects: dict) -> list[tuple[str, ...]]:
    """The cards a claim names, in order - a list of acts as one group (the reader tells it from the sentence)."""
    card_of = {stored: card for card, (family, stored) in objects.items()}
    card_of.update({'u:0': 'U1'})
    return [tuple(card_of[act] for act in spec.acts) if name.startswith('acts:') else (card_of[name],)
            for name in spec.names]


class InstructionReadingTests(SimpleTestCase):
    """The repair pass (refutation RC-2): PROOF names every passage by the claim line's cited units and the cards it
    names, so a proof that follows it is never voided - read by InstructionReader from what a reader sees, over every
    question form and the calibration kinds; and the passages are not widened."""

    def setUp(self) -> None:
        self.reader = InstructionReader(QC.PROOF)
        self.objects = _cards(*DOC_CARDS)[1]

    def follows(self, built, item, text, headings, marks, groups) -> tuple[list, list]:
        """(the proofs the instruction permits for ``item``, those the locator voids)."""
        seen = seen_of(built, text, headings)
        proofs = self.reader.proofs(seen, item, groups, marks)
        return proofs, [quotes for quotes in proofs if not located(text, item, quotes).located]

    def test_every_clause_is_stated_in_its_repaired_form(self) -> None:
        self.assertEqual(self.reader.forms, {clause: 'repaired' for clause in _CLAUSE_FORMS})
        text = ' '.join(QC.PROOF.split())
        self.assertNotIn('where the document says', text)  # no passage is named by a place in the document

    def test_every_form_a_proof_that_follows_the_instruction_locates(self) -> None:
        """Every question form (QuestionFamily x Form: all of QUESTION_TEMPLATES) and the calibration kinds, through the
        product's request builder over DOC: every proof the instruction permits locates, and some proof does wherever a
        proof can ever locate."""
        shapes = doc_shapes()
        self.assertEqual({spec.form for _, spec, _ in shapes}, set(QC.QUESTION_TEMPLATES))
        units = units_of(DOC)
        for name, spec, degenerate in shapes:
            built, item = doc_request(spec)
            with self.subTest(shape=name):
                proofs, voided = self.follows(built, item, DOC, DOC_HEADINGS, DOC_MARKS, groups_of(spec, self.objects))
                self.assertEqual(voided, [], (name, item.claim_sentence))
                if degenerate:
                    self.assertEqual(proofs, [], (name, degenerate))  # no passage can be followed, as none can locate
                else:
                    self.assertTrue(proofs, (name, item.claim_sentence))
                # the units the claim line cites are exactly its passages' - the instruction's bound is the locator's
                self.assertEqual(seen_of(built, DOC, DOC_HEADINGS).lines[item.claim][2], _cited_units(item, units))
                # a place that merely restates a value is never cited, so never named
                self.assertFalse(set(seen_of(built, DOC, DOC_HEADINGS).lines[item.claim][2]) & RESTATING, name)

    def test_a_quote_where_the_document_restates_a_value_is_still_void(self) -> None:
        """The boundary the repair leaves alone: the passages are not widened. A proof quoting the impression, the
        signature or the date-of-service line beside a right proof is voided, as before."""
        # each a right proof from the claim's own passages (pass 1's units), and the restating words beside it
        restated = {'reach, its examination and source': (['advanced through the whole colon',
                                                            'the ileocecal valve were both identified'],
                                                           'the cecum was reached and seen'),
                    "entry, the part's start": (['sessile polyp in the sigmoid colon',
                                                 'PROCEDURE NOTE written by the documenting clinician'],
                                                'Electronically signed by the documenting clinician'),
                    'date, the part and its occasion': (['sessile polyp in the sigmoid colon',
                                                         'took place earlier this same morning'],
                                                        'Date of service: November 9, 2026')}
        shapes = {name: spec for name, spec, _ in doc_shapes()}
        for name, (right, words) in restated.items():
            built, item = doc_request(shapes[name])
            with self.subTest(shape=name):
                self.assertTrue(located(DOC, item, right).located)
                self.assertFalse(located(DOC, item, [*right, words]).located)
                self.assertFalse(located(DOC, item, [right[0], words]).located)

    def test_a_place_claims_heading_is_a_further_passage_never_the_acts_own(self) -> None:
        """The heading clause's one exception, as the locator reads it: for a claim about where an act was done, the
        heading of its part may be a FURTHER passage (the optional passage); where that heading is the first words of
        the act's own unit (S28), the act's passage is the unit less the heading - so the heading alone never proves the
        act, and the reader, given the repaired clause, uses it only beside the act's own words."""
        spec = next(spec for name, spec, _ in doc_shapes() if name.startswith('target.places, its part'))
        built, item = doc_request(spec)
        heading, act = 'OPERATIVE FINDINGS The stalk', 'ligated with an endoloop first.'
        self.assertFalse(located(DOC, item, [heading]).located)
        self.assertTrue(located(DOC, item, [act, heading]).located)
        proofs = self.reader.proofs(seen_of(built, DOC, DOC_HEADINGS), item, groups_of(spec, self.objects), DOC_MARKS)
        self.assertTrue([quotes for quotes in proofs if any('OPERATIVE FINDINGS' in quote for quote in quotes)])
        self.assertFalse([quotes for quotes in proofs if 'OPERATIVE FINDINGS' in quotes[0]])  # never the act's own

    def test_the_first_repaired_heading_clause_let_a_place_claims_heading_be_the_acts_own_passage(self) -> None:
        """The repair pass's own first wording of the heading clause ("..., except that heading for a claim about where
        the act was done"), never shipped: read as a reader may read it, it lifts the ban for the act's OWN passage of a
        place claim, and where the part's heading is the first words of the act's unit a proof whose act passage is the
        heading's words is void. The shipped wording scopes the exception to a further passage."""
        first = _CLAUSE_FORMS['heading']['first-repair']
        text = ' '.join(QC.PROOF.split())
        reader = InstructionReader(text.replace(_CLAUSE_FORMS['heading']['repaired'], first))
        self.assertEqual(reader.forms['heading'], 'first-repair')
        spec = next(spec for name, spec, _ in doc_shapes() if name.startswith('target.places, its part'))
        built, item = doc_request(spec)
        seen = seen_of(built, DOC, DOC_HEADINGS)
        void = [quotes for quotes in reader.proofs(seen, item, groups_of(spec, self.objects), DOC_MARKS)
                if not located(DOC, item, quotes).located]
        self.assertTrue(void)
        self.assertTrue(all('OPERATIVE FINDINGS' in quotes[0] for quotes in void))
        self.assertFalse([quotes for quotes in self.reader.proofs(seen, item, groups_of(spec, self.objects), DOC_MARKS)
                          if not located(DOC, item, quotes).located])

    def test_rc2_the_refuters_report(self) -> None:
        """RC-2's own input (the refutation's InstructionVsLocator d6-d8): a reach whose impression restates it (S7), an
        entry whose signature restates the author (S8), a date relation resting on the act's "today" (S5) beside a
        date-of-service line (S9). Under the refuted instruction the proofs it invited there were voided."""
        text = ('PROCEDURE NOTE by the documenting clinician\n'                       # S1: the part's start
                'A small sessile polyp in the sigmoid colon was removed with a\n'     # S2
                'cold snare and retrieved for histology without electrocautery.\n'   # S3
                'No biopsies of the rectum were taken during this procedure.\n'      # S4
                'The scope was advanced to the cecum without difficulty today.\n'    # S5: the session's card
                'The cecum was identified by the appendiceal orifice and valve.\n'   # S6: pass 1's source of the reach
                'IMPRESSION: complete colonoscopy, the cecum was reached and seen.\n'  # S7
                'Electronically signed by the documenting clinician, A. Current.\n'   # S8
                'Date of service: November 9, 2026, at this encounter.\n')            # S9
        cards, objects = _cards(('A2', ct.CardType.ACT, 'event', 'E2', ('S2', 'S3')),
                                ('A4', ct.CardType.ACT, 'event', 'E4', ('S4',)),
                                ('X1', ct.CardType.SESSION, 'session', 'X1', ('S5',)))
        event = {'id': 'E2', 'entry': _source('documenting_clinician', 'S1', inherited='N0'),
                 'date_relation': _source('on_date_of_service', 'S5')}
        specs = [_planned(FAM.Q_FACT, 'fact.reached', ('X1',), A.REACHED, 'cecum'),
                 _planned(FAM.Q_FACT, 'fact.entry', ('E2',), A.ENTRY, 'documenting_clinician'),
                 _planned(FAM.Q_FACT, 'fact.date_relation', ('E2',), A.DATE_RELATION, 'on_date_of_service')]
        built = built_request(text, cards, objects, specs, events=[event],
                              sessions=[{'id': 'X1', 'reached': [_source('cecum', 'S6')]}],
                              sections=[{'id': 'N0', 'start': {'units': ['S1']}}])
        marks = Marks(says={('reach', 'cecum'): ('S6', 'S7'), ('E2', 'entry'): ('S1', 'S8'),
                            ('E2', 'date_relation'): ('S5', 'S9')})
        headings = (_span_of(text, 'PROCEDURE NOTE by the documenting clinician'),)
        for item in built.items:
            with self.subTest(form=item.spec.form):
                proofs, voided = self.follows(built, item, text, headings, marks, groups_of(item.spec, objects))
                self.assertTrue(proofs)
                self.assertEqual(voided, [], item.spec.form)
                quoted = {unit for quotes in proofs for quote in quotes for unit in _units_quoted(text, quote)}
                self.assertFalse(quoted & {'S7', 'S8', 'S9'}, item.spec.form)

    def test_rc2_an_independent_report_and_the_performer_the_instruction_never_named(self) -> None:
        """RC-2's verifier's own input (eight units: the reach restated by an impression S6, the author by a signature
        S7, the date of service by a header S8), with a PERFORMER question beside it: its value passage (the part's start
        and the part's performer source) is a required passage the refuted instruction never named, so a proof that
        followed it - the act's words alone - was always void."""
        text = ('ENDOSCOPY REPORT written by the documenting clinician\n'                # S1
                'The patient was prepared and sedated for the colonoscopy today.\n'     # S2
                'The colonoscope was advanced through the colon to the cecum.\n'        # S3
                'The appendiceal orifice and ileocecal valve were seen clearly.\n'      # S4
                'A 6 mm ascending colon polyp was removed with a cold snare.\n'         # S5
                'Impression: a complete colonoscopy to the cecum was performed.\n'      # S6
                'Report signed by the documenting clinician after the procedure.\n'     # S7
                'Date of service: November 9, 2026, for this encounter.\n'              # S8
                'All procedures were personally carried out by the documenting team.\n')  # S9: the part's performer
        cards, objects = _cards(('A1', ct.CardType.ACT, 'event', 'E1', ('S5',)),
                                ('X1', ct.CardType.SESSION, 'session', 'X1', ('S3',)))
        section = {'id': 'N0', 'start': {'units': ['S1']}, 'owner': _source('documenting_clinician', 'S1'),
                   'occasion': _source('on_date_of_service', 'S2'), 'performer': _source('documenting_team', 'S9')}
        event = {'id': 'E1', 'entry': _source('documenting_clinician', 'S1', inherited='N0'),
                 'date_relation': _source('on_date_of_service', 'S2', inherited='N0'),
                 'performer': _source('documenting_team', inherited='N0')}
        specs = [_planned(FAM.Q_FACT, 'fact.reached', ('X1',), A.REACHED, 'cecum'),
                 _planned(FAM.Q_FACT, 'fact.entry', ('E1',), A.ENTRY, 'documenting_clinician'),
                 _planned(FAM.Q_FACT, 'fact.date_relation', ('E1',), A.DATE_RELATION, 'on_date_of_service'),
                 _planned(FAM.Q_FACT, 'fact.performer', ('E1',), A.PERFORMER, 'documenting_team')]
        built = built_request(text, cards, objects, specs, events=[event],
                              sessions=[{'id': 'X1', 'reached': [_source('cecum', 'S4')]}], sections=[section])
        marks = Marks(says={('reach', 'cecum'): ('S4', 'S6'), ('E1', 'entry'): ('S1', 'S7'),
                            ('E1', 'date_relation'): ('S2', 'S8')})
        headings = (_span_of(text, 'ENDOSCOPY REPORT written by the documenting clinician'),)
        performer = next(item for item in built.items if item.spec.form == 'fact.performer')
        self.assertEqual([_unit_ids_of(found, text) for found in performer.required], [['S5'], ['S1', 'S9']])
        for item in built.items:
            with self.subTest(form=item.spec.form):
                proofs, voided = self.follows(built, item, text, headings, marks, groups_of(item.spec, objects))
                self.assertTrue(proofs)
                self.assertEqual(voided, [], item.spec.form)
                quoted = {unit for quotes in proofs for quote in quotes for unit in _units_quoted(text, quote)}
                self.assertFalse(quoted & {'S6', 'S7', 'S8'}, item.spec.form)

    def test_the_refuted_instruction_invited_proofs_the_locator_voids(self) -> None:
        """The reader is no tautology: the instruction RC-2 refuted, read by the same reader, permits proofs the locator
        voids on DOC (the reach's impression, the signature, the date-of-service line, the performer never named, the
        anatomy entry never named, a sentence split across a session's card and its reach source as one passage)."""
        # the refuted text itself: the lane's PROOF before the repair pass, byte for byte (its sha256, read there)
        self.assertEqual(hashlib.sha256(_REFUTED_PROOF.encode()).hexdigest(),
                         'a149bfb0b70a6c900c34dc3a148b479ab489d53952e4f5ef92b6526ff6acfa06')
        reader = InstructionReader(_REFUTED_PROOF)
        self.assertEqual(reader.forms, {clause: 'refuted' for clause in _CLAUSE_FORMS})
        shapes = {name: spec for name, spec, _ in doc_shapes()}
        expected_void = ('reach, its examination and source', "entry, the part's start", 'date, the part and its occasion',
                         'performer, the part and its source', 'reach, a sentence split across card and source')
        for name in expected_void:
            built, item = doc_request(shapes[name])
            proofs = reader.proofs(seen_of(built, DOC, DOC_HEADINGS), item, groups_of(shapes[name], self.objects),
                                   DOC_MARKS)
            with self.subTest(shape=name):
                self.assertTrue([quotes for quotes in proofs if not located(DOC, item, quotes).located], name)
        built, item = doc_request(shapes['type'])  # no anatomy entry named: nothing a reader may copy
        self.assertEqual(reader.proofs(seen_of(built, DOC, DOC_HEADINGS), item, groups_of(shapes['type'], self.objects),
                                       DOC_MARKS), [])

    def test_each_clause_alone_in_its_refuted_form_permits_a_proof_the_locator_voids(self) -> None:
        """Clause by clause: the repaired PROOF with ONE clause put back in the form RC-2 refuted, read by the same reader
        over DOC - each such instruction permits a proof the locator voids (or, for the anatomy entry, permits none
        where one locates), on the shapes named. Two clauses change nothing alone, and say why: a card's units are
        cited unless wholly a heading (the bound), and the units one role or another allows are every cited unit (the
        further passages) - each is pinned literally (ProofInstructionTests)."""
        expected = {'session': {'reach, its examination and source'},
                    'frame': {'date, the part and its occasion', "entry, the part's start",
                              'performer, the part and its source', 'K1 date', 'K1 performer'},
                    'objects': {'type', 'type, under a heading in its unit'},
                    'heading': {'type, under a heading in its unit'},
                    'split': {'rel', 'reach, a sentence split across card and source'},
                    'bound': set(), 'further': set()}
        text = ' '.join(QC.PROOF.split())
        for clause, shapes in expected.items():
            forms = _CLAUSE_FORMS[clause]
            reader = InstructionReader(text.replace(forms['repaired'], forms['refuted']))
            self.assertEqual([name for name, form in reader.forms.items() if form == 'refuted'], [clause])
            moved = set()
            for name, spec, degenerate in doc_shapes():
                built, item = doc_request(spec)
                proofs = reader.proofs(seen_of(built, DOC, DOC_HEADINGS), item, groups_of(spec, self.objects),
                                       DOC_MARKS)
                if any(not located(DOC, item, quotes).located for quotes in proofs) or (not proofs and not degenerate):
                    moved.add(name)
            with self.subTest(clause=clause):
                self.assertTrue(shapes <= moved, (clause, sorted(moved)))
                if not shapes:
                    self.assertEqual(moved, set(), clause)


def _unit_ids_of(passage: QC.PassageSet, text: str) -> list[str]:
    units = units_of(text)
    return [unit['id'] for unit in units if any(unit['start'] < end and unit['end'] > start
                                                for start, end in passage.ranges)]


def _units_quoted(text: str, quote: str) -> set[str]:
    collapsed, offsets = proof._collapsed(text)
    spans = proof._occurrences(collapsed, offsets, proof.normalized(quote))
    return {unit['id'] for unit in units_of(text) for start, end in spans if unit['start'] < end and unit['end'] > start}


# The PROOF paragraph as RC-2 refuted it (the lane's text before the repair pass), kept only as the reader's
# counter-example: the same reader, given it, permits proofs the locator voids.
_REFUTED_PROOF = """\
PROOF
quotes: for a claim marked proof that you answer supports, copy passages of the document that show the claim is true.
Copy at least one passage from the units of each act, statement, lesion, session or unlisted entry the claim names
(the card it is about included; for a list of acts, from the units of one of them; for what a session reached or
examined, the units where the document says it count as the session's), never the words of a heading above an act, a
statement or a lesion; and, where the claim refers to the date of service, the author of the document or the part of
the document an act is told in, at least one more from where the document says it. Copy any further passage only from
those same units, or, for a claim about where an act was done, from the heading of the part of the document it is
told in. Each passage is the exact words of the document (a line break or a run of spaces may be written as one
space), at least 2 words and 12 characters other than spaces long and at most 300 characters long,
without unit labels or [Page N] lines; no two passages overlap; and a sentence that a line break splits across two
units may be copied as one passage or as one passage from each unit. Give at most 8 passages.
The absence of a statement is never a passage: for a claim that something was not done or was not caused by
something, or that a statement does not concern, deny, cast doubt on, plan or recommend an act, copy the words that
say what was done or caused, or what the statement says, instead. If you cannot point to such words, do not answer
supports. For every other verdict, and for a claim without the mark, write an empty list."""


# --- D318 (3): Q-REL's narrowest relation ------------------------------------------------------------------------------


EVERY_EVENT_SUBJECT = [(SC.ACT, status) for status in (SS.PERFORMED, SS.PLANNED, SS.ATTEMPTED, SS.IN_DOUBT)] + [
    (SC.STATEMENT, SS.DENIED), (SC.STATEMENT, SS.IN_DOUBT)]


class _Cards:
    def card(self, stored: str) -> str:
        return {'E2': 'A2', 'E3': 'A3', 'E4': 'A4', 'u:0': 'U1', 'X1': 'X1', 'Y1': 'Y1'}[stored]

    def units(self, stored: str) -> tuple:
        return ('S6',)


def rel_spec_of(plan: asking.Plan, statement: str, act: str) -> asking.QuestionSpec:
    found = [spec for spec in plan.specs if spec.family is FAM.Q_REL and spec.subjects == (statement, act)]
    assert len(found) == 1, [spec.key for spec in plan.specs]
    return found[0]


def narrowed(spec: asking.QuestionSpec) -> asking.QuestionSpec:
    """The spec the planner asks once it reads relation_form (the asking lane's wiring: NOTES, question Q1)."""
    form = QC.relation_form(spec.described)
    assert form is not None, spec.described
    return dataclasses.replace(spec, form=form)


def answered(built: QC.QuestionRequest, text: str, claim: tuple, control: tuple) -> settle.QuestionSettlement:
    """``built`` answered: every question's claim ``claim`` (verdict, quotes), its control ``control``; every
    calibration item in the holding direction."""
    verdicts = []
    for item in built.items:
        for member, claim_id in (('claim', item.claim), ('control', item.control)):
            if item.role == 'calibration':
                value, quotes = ('contradicts', []) if member == 'claim' else ('supports', [])
            else:
                value, quotes = claim if member == 'claim' else control
            verdicts.append({'claim': claim_id, 'verdict': value, 'attached': 'yes', 'qualifiers': [],
                             'evidence': list(item.cited[:1]), 'quotes': list(quotes)})
    answer = json.dumps({'verdicts': verdicts, 'unlisted': []})
    cited = {}
    for item in built.items:
        cited[item.claim] = item.cited
        cited[item.control] = item.cited
    read = appraise_read.read_questions(answer, built.claim_ids, cited, len(units_of(text)))
    assert hasattr(read, 'verdicts'), read
    locations = {item.claim: located(text, item, read.verdicts[item.claim].quotes if read.verdicts.get(item.claim)
                                     else ()) for item in built.items}
    with mock.patch.object(asking, 'eligible', return_value=True):
        return settle.settle_questions(built, read, locations, None)


K1_ITEM = described(asking.CalibrationSpec('K1', FAM.Q_FACT, 'fact.performer', ('E2',), A.PERFORMER,
                                           'documenting_team', True, ('E2',)), DONE)


class RelationFormTests(SimpleTestCase):
    """DECISIONS D318 (3) and its second addendum."""

    def test_the_narrowest_form_by_the_statements_class_and_status(self) -> None:
        expected = {(SC.STATEMENT, SS.DENIED): 'rel.deny', (SC.STATEMENT, SS.IN_DOUBT): 'rel.deny_or_doubt',
                    (SC.ACT, SS.PLANNED): 'rel.plan', (SC.ACT, SS.PERFORMED): 'rel', (SC.ACT, SS.ATTEMPTED): 'rel',
                    (SC.ACT, SS.IN_DOUBT): 'rel', (SC.UNLISTED, SS.DENIES): 'rel', (SC.UNLISTED, SS.DOUBTS): 'rel'}
        for statement, form in expected.items():
            for act in EVERY_EVENT_SUBJECT:
                with self.subTest(statement=statement, act=act):
                    self.assertEqual(QC.relation_form((statement, act)), form)
        for statement in ((SC.UNLISTED, SS.TELLS), (SC.SESSION, SS.NONE), None):  # no Q-REL of these: never asked
            self.assertIsNone(QC.relation_form((statement, DONE)))
        self.assertIsNone(QC.relation_form(((SC.STATEMENT, SS.DENIED), None)))
        # the concern form stays exact for every statement side: a K3 calibration item keeps it (its known-false
        # ground - covers supported, every row SAME - is "concerns"; a denial that applies to an act's site does not
        # deny the act, so a narrow K3 would not be known false)
        for statement in expected:
            self.assertIsNone(QC.inexact('rel', (statement, DONE)))

    def test_each_narrow_form_names_its_relation_and_its_exact_negation(self) -> None:
        spec = asking.QuestionSpec(FAM.Q_REL, 'rel', ('E3', 'E2'), None, '', False, ('E3', 'E2'))
        sentences = {}
        for form, statement in (('rel.deny', (SC.STATEMENT, SS.DENIED)), ('rel.deny_or_doubt', (SC.STATEMENT, SS.IN_DOUBT)),
                                ('rel.plan', (SC.ACT, SS.PLANNED)), ('rel', (SC.ACT, SS.PERFORMED))):
            sentences[form] = QC._sentences(described(dataclasses.replace(spec, form=form), statement, DONE), _Cards())
        self.assertEqual(sentences, {
            'rel.deny': ('A3', 'This statement does not deny act A2.', 'This statement denies act A2.'),
            'rel.deny_or_doubt': ('A3', 'This statement does not deny act A2 or cast doubt on it.',
                                  'This statement denies act A2 or casts doubt on it.'),
            'rel.plan': ('A3', 'This statement does not plan or recommend act A2.',
                         'This statement plans or recommends act A2.'),
            'rel': ('A3', 'This statement does not concern act A2.', 'This statement concerns act A2.')})
        # the narrow forms are never handed a statement outside their side: never a wrong sentence
        with self.assertRaises(QC.Unbuildable):
            QC._sentences(described(dataclasses.replace(spec, form='rel.deny'), (SC.STATEMENT, SS.IN_DOUBT), DONE),
                          _Cards())
        with self.assertRaises(QC.Unbuildable):
            QC._sentences(described(dataclasses.replace(spec, form='rel.plan'), (SC.ACT, SS.IN_DOUBT), DONE), _Cards())
        # PLANNED's own definition is what the plan form says ("planned or recommended"): a changed label fails here
        self.assertEqual(claims.LABELS[Status.PLANNED], 'is planned or recommended, not done')
        # a form is written only for its own family: a Q-FACT spec handed a Q-REL form is never built
        with self.assertRaises(QC.Unbuildable):
            QC._sentences(described(dataclasses.replace(spec, family=FAM.Q_FACT, form='rel.deny'),
                                    (SC.STATEMENT, SS.DENIED), DONE), _Cards())

    def test_the_form_is_derived_per_census_row_from_the_engines_plan(self) -> None:
        """For each Q-REL census row and witness cause, the planner's own spec (its census row, its witness's cause and
        fact, its statement's class and status) and the narrowest form relation_form derives for it."""
        rows = {}
        # R1, relation:unresolved - an ESTABLISHED denial whose target row cannot tell (no place control asked)
        r1 = colonoscopy()
        r1.event(3, kind=sup(Kind.SNARE), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                 entry=sup(DC), breadth=sup(ct.Breadth.SINGLE_TARGET), places=[sup(Landmark.RECTUM)])
        rows['R1 denial'] = (r1.build(), 'E3', '45385')
        # R1, relation:unresolved - an established PLAN (a later date): the timing row cannot tell (the act's date open)
        plan = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION))
        plan.event(3, kind=sup(Kind.SNARE), status=sup(Status.PLANNED), session=F.SILENT,
                   date=sup(ct.DateRelation.LATER_DATE), entry=sup(DC))
        rows['R1 plan'] = (plan.build(), 'E3', '45385')
        # R2, relation:possible_statement - an OPEN denial (filed negated, not established) of a clip, its kind open
        r2 = colonoscopy()
        r2.event(3, kind=unres(Kind.CLIP), status=fact(ct.Result.UNRESOLVED, Status.PERFORMED, ct.FactState.NEGATED,
                                                       reasons=(ct.Reason.APPRAISAL_UNCLEAR,)),
                 session=sup(X(1)), date=sup(ON), entry=sup(DC))
        rows['R2 open denial'] = (r2.build(), 'E3', '45385')
        # R2, relation:possible_statement - an act-filed statement whose status is not established
        act_filed = colonoscopy()
        act_filed.event(3, kind=sup(Kind.SNARE), status=unres(Status.PERFORMED, ct.Reason.UNAPPRAISED),
                        session=sup(X(1)), date=sup(ON), entry=sup(DC), places=[unres(Landmark.SIGMOID_COLON)])
        rows['R2 act-filed'] = (act_filed.build(), 'E3', '45385')
        # C7b-other - a claimed pair (the plan's covers names the act) the fact pass did not support, no denial
        claimed = colonoscopy()
        claimed.event(3, kind=sup(Kind.SNARE), status=sup(Status.PLANNED), session=F.SILENT,
                      date=sup(ct.DateRelation.LATER_DATE), entry=sup(DC), covers=[unres(E(2), ct.Reason.UNAPPRAISED)])
        rows['C7b-other plan'] = (claimed.build(), 'E3', '45385')
        expected = {'R1 denial': ('R1', 'relation:unresolved', (SC.STATEMENT, SS.DENIED), 'rel.deny'),
                    'R1 plan': ('R1', 'relation:unresolved', (SC.ACT, SS.PLANNED), 'rel.plan'),
                    'R2 open denial': ('R2', 'relation:possible_statement', (SC.STATEMENT, SS.IN_DOUBT),
                                       'rel.deny_or_doubt'),
                    'R2 act-filed': ('R2', 'relation:possible_statement', (SC.ACT, SS.IN_DOUBT), 'rel'),
                    'C7b-other plan': ('C7b-other', 'relation:unresolved', (SC.ACT, SS.PLANNED), 'rel.plan')}
        for name, (R, statement, code) in rows.items():
            with self.subTest(row=name):
                spec = rel_spec_of(asking.plan(R, ()), statement, 'E2')
                row, cause, statement_side, form = expected[name]
                self.assertEqual((spec.census, spec.witnesses[0].cause, spec.described[0]), (row, cause, statement_side))
                self.assertIn(code, {witness.code for witness in spec.witnesses})
                self.assertEqual(QC.relation_form(spec.described), form)
        # U1, unlisted (rule 4) - a kept unlisted denial and a doubt: the concern form (their what is one report)
        for what, status in ((ct.UnlistedWhat.DENIAL, SS.DENIES), (ct.UnlistedWhat.DOUBT, SS.DOUBTS)):
            doc = colonoscopy()
            doc.unlisted.append(unlisted(what, None, None, unit(9)))
            spec = rel_spec_of(asking.plan(doc.build(), ()), 'u:0', 'E2')
            with self.subTest(row='U1', what=what):
                self.assertEqual((spec.census, spec.witnesses[0].cause, spec.described[0]),
                                 ('U1', 'unlisted', (SC.UNLISTED, status)))
                self.assertEqual(QC.relation_form(spec.described), 'rel')

    def test_an_open_denial_at_an_acts_site_asks_deny_or_cast_doubt_and_releases_only_by_proof(self) -> None:
        """The step-1-long scene's SHAPE (an open denial of clips or cautery at a cold-snare removal's site, no kind of
        its own): asked whether it denies the removal or casts doubt on it - the concern form, which the probe asked,
        was answered "concerns" (it is about the removal's site), so the hold stood."""
        text = ('Colonoscopy report.\n'
                'A small sessile polyp in the sigmoid colon was removed with a\n'
                'cold snare and retrieved for histology without electrocautery.\n'
                'No clip or cautery was needed at this site after the removal.\n')
        doc = colonoscopy()
        doc.event(3, kind=unres(Kind.CLIP), status=fact(ct.Result.UNRESOLVED, Status.PERFORMED, ct.FactState.NEGATED,
                                                        reasons=(ct.Reason.APPRAISAL_UNCLEAR,)),
                  session=sup(X(1)), date=sup(ON), entry=sup(DC))
        R = doc.build()
        spec = narrowed(rel_spec_of(asking.plan(R, ()), 'E3', 'E2'))
        self.assertEqual(spec.form, 'rel.deny_or_doubt')
        cards, objects = _cards(('A2', ct.CardType.ACT, 'event', 'E2', ('S2', 'S3')),
                                ('A3', ct.CardType.ACT, 'event', 'E3', ('S4',)))
        built = built_request(text, cards, objects, [spec], [K1_ITEM])
        item = next(found for found in built.items if found.role == 'question')
        self.assertEqual((item.claim_sentence, item.control_sentence),
                         ('This statement does not deny act A2 or cast doubt on it.',
                          'This statement denies act A2 or casts doubt on it.'))
        quotes = ['No clip or cautery was needed', FIRST_HALF_Q, SECOND_HALF_Q]
        right = answered(built, text, ('supports', quotes), ('contradicts', []))
        self.assertEqual((right.questions[0]['result'], right.questions[0]['form']), ('supported', 'rel.deny_or_doubt'))
        self.assertTrue(evaluate.decide('45385', (), R).held_facts)
        self.assertFalse(evaluate.decide('45385', (), F._answered(R, {'questions': list(right.questions)})).held_facts)
        wrong = answered(built, text, ('supports', quotes), ('supports', []))  # R3D-01: one wrong supports holds
        self.assertEqual(wrong.questions[0]['reasons'], ['question_incoherent'])
        self.assertTrue(evaluate.decide('45385', (), F._answered(R, {'questions': list(wrong.questions)})).held_facts)

    def test_qb_a_denial_whose_own_umbrella_place_holds_the_act_is_answerable_denies(self) -> None:
        """DECISIONS D316's QB scene: a DENIED injection of lesion L1, placed at L1's place and at the whole colon (an
        umbrella it names for itself), beside a tattoo naming no lesion in the transverse colon - the note contradicts
        itself, 45381 must be held. Asked, the statement is an established denial: "does not deny the tattoo", whose
        holding answer ("denies") the sentence admits, and which holds the code."""
        LM = Landmark
        doc = colonoscopy(places=[sup(LM.TRANSVERSE_COLON)])
        doc.lesions[L(1)] = {A.MULTIPLICITY: (sup(ct.Multiplicity.SINGLE),),
                             A.PLACES: (sup(LM.TRANSVERSE_COLON),)}
        doc.act(3, Kind.INJECTION, status=neg(Status.PERFORMED), breadth=sup(ct.Breadth.SINGLE_TARGET),
                places=[sup(LM.TRANSVERSE_COLON), sup(LM.COLON)], lesion=sup(L(1)))
        doc.act(4, Kind.TATTOO, places=[sup(LM.TRANSVERSE_COLON)])
        doc.controls.update(TPG.claims_pair_controls(E(3), (LM.TRANSVERSE_COLON, LM.COLON), E(4),
                                                     (LM.TRANSVERSE_COLON,), lambda subject, place: True))
        R = doc.build()
        self.assertEqual(asking.describe(R, 'E3'), (SC.STATEMENT, SS.DENIED))
        form = QC.relation_form((asking.describe(R, 'E3'), asking.describe(R, 'E4')))
        self.assertEqual(form, 'rel.deny')
        spec = asking.QuestionSpec(FAM.Q_REL, form, ('E3', 'E4'), None, '', False, ('E3', 'E4'), census='R4',
                                   described=(asking.describe(R, 'E3'), asking.describe(R, 'E4')))
        text = ('Colonoscopy report.\n'
                'No injection was used for the resection or anywhere in the colon.\n'
                'A tattoo was placed in the transverse colon to mark the site.\n')
        cards, objects = _cards(('A3', ct.CardType.ACT, 'event', 'E3', ('S2',)),
                                ('A4', ct.CardType.ACT, 'event', 'E4', ('S3',)))
        built = built_request(text, cards, objects, [spec], [dataclasses.replace(K1_ITEM, subjects=('E4',),
                                                                                 names=('E4',))])
        item = next(found for found in built.items if found.role == 'question')
        self.assertEqual((item.claim_sentence, item.control_sentence),
                         ('This statement does not deny act A4.', 'This statement denies act A4.'))
        held_before = evaluate.decide('45381', (), R).held_facts
        holding = answered(built, text, ('contradicts', []), ('supports', ['No injection was used for the resection',
                                                                         'A tattoo was placed in the']))
        record = holding.questions[0]
        self.assertEqual((record['result'], record['held_by_answer']), ('unresolved', True))
        self.assertEqual(evaluate.decide('45381', (), F._answered(R, {'questions': list(holding.questions)})).held_facts,
                         held_before)
        self.assertTrue(held_before)


# --- D312: the stoma route's own question forms --------------------------------------------------------------------------


class RouteFormTests(SimpleTestCase):
    """DECISIONS D312 (with D310 (1)): the route is a reading Fable may be asked - a session's approach and an anatomy
    entry's type, each the fact pass's own sentence and its one-"not" negation; an established answer reaches the
    route table through the fold."""

    def test_the_approach_and_the_type_are_the_fact_passs_sentences(self) -> None:
        approach = asking.QuestionSpec(FAM.Q_FACT, 'fact.approach', ('X1',), A.APPROACH, 'through_stoma', False,
                                       ('X1',))
        anus = dataclasses.replace(approach, negated=True)  # a colonoscopy code through the anus: through_stoma denied
        kind = asking.QuestionSpec(FAM.Q_FACT, 'fact.type', ('Y1',), A.TYPE, 'stoma', False, ('Y1',))
        session, entry = (SC.SESSION, SS.NONE), (SC.ANATOMY, SS.NONE)
        self.assertEqual(QC._sentences(described(approach, session), _Cards())[1:],
                         ('In session X1 the scope was passed through a stoma.',
                          'In session X1 the scope was not passed through a stoma.'))
        self.assertEqual(QC._sentences(described(anus, session), _Cards())[1:],
                         ('In session X1 the scope was not passed through a stoma.',
                          'In session X1 the scope was passed through a stoma.'))
        self.assertEqual(QC._sentences(described(kind, entry), _Cards()),
                         ('Y1', 'The patient has a surgical opening (a stoma) (described at S6).',
                          'The patient does not have a surgical opening (a stoma) (described at S6).'))
        positive = claims.template(claims.TemplateId.SESSION_APPROACH, interpretation.APPRAISAL_VERSION_V3)
        self.assertEqual(QC.QUESTION_TEMPLATES['fact.approach'][0], positive)  # the ONE source
        self.assertEqual(QC.QUESTION_SOURCES['fact.type'].positive, claims.TemplateId.ANATOMY_TYPE)
        for wrong, found in ((approach, entry), (kind, session), (kind, DONE)):
            with self.subTest(form=wrong.form, found=found), self.assertRaises(QC.Unbuildable):
                QC._sentences(described(wrong, found), _Cards())
        with self.assertRaises(QC.Unbuildable):  # a value that is no Approach
            QC._sentences(described(dataclasses.replace(approach, value='stoma'), session), _Cards())

    def test_an_established_route_answer_reaches_the_route_table(self) -> None:
        doc = colonoscopy()
        doc.sessions[X(1)][A.APPROACH] = (unres(ct.Approach.THROUGH_STOMA, ct.Reason.GEOMETRY_SECTION),)
        R = doc.build()
        self.assertTrue(evaluate.stoma_possible(R, X(1)))
        record = {'family': 'Q-FACT', 'form': 'fact.approach', 'subjects': ['X1'], 'unlisted': None,
                  'attribute': 'approach', 'value': 'through_stoma', 'negated': True, 'result': 'supported',
                  'reasons': [], 'proof': [{'start': 0, 'end': 10}]}
        self.assertFalse(evaluate.stoma_possible(F._answered(R, {'questions': [record]}), X(1)))
        self.assertTrue(evaluate.stoma_possible(F._answered(R, {'questions': [{**record, 'result': 'unresolved'}]}),
                                                X(1)))


# --- D312 (1): mutant M10b's killing test ---------------------------------------------------------------------------------


class DenialArmTests(SimpleTestCase):
    """DECISIONS D312 (1), mutant M10b (probe-check2): a claimed pair whose statement is a FILED denial (its status
    claimed negated, not established) or a DOUBTED statement is C7b-denial - whether the act happened, the coder's -
    never asked as Q-REL: asking._denies_or_doubts reads all three arms, not only an established negation."""

    def scene(self, status) -> object:
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.SNARE), status=status, session=sup(X(1)), date=unres(ON, ct.Reason.GEOMETRY_SECTION),
                  breadth=sup(ct.Breadth.ALL_OF_KIND), covers=[unres(E(2), ct.Reason.UNAPPRAISED)])
        return doc.build()

    def test_a_filed_denial_and_a_doubt_are_c7b_denial(self) -> None:
        for name, status in (('filed', fact(ct.Result.UNRESOLVED, Status.PERFORMED, ct.FactState.NEGATED,
                                            reasons=(ct.Reason.APPRAISAL_UNCLEAR,))),
                             ('doubted', unres(Status.PERFORMED, ct.Reason.DOUBT_STATED)),
                             ('established', neg(Status.PERFORMED))):
            R = self.scene(status)
            with self.subTest(arm=name):
                self.assertTrue(pairing.relation(R, E(3), E(2)).claimed)
                found = asking.plan(R, ())
                self.assertFalse([spec for spec in found.specs if spec.family is FAM.Q_REL and spec.subjects[0] == 'E3'])
                self.assertIn('C7b-denial', found.blocked)


# --- D319: one calibration item per request -------------------------------------------------------------------------------


class CalibrationFloorTests(SimpleTestCase):
    """DECISIONS D319: every question request carries ONE calibration item; H5 refuses only a request with none
    (CALIBRATION_FLOOR 1 - at 2, every one-item request would be refused as uncalibrated); H2 unchanged."""

    def setUp(self) -> None:
        cards, objects = _cards(('A2', ct.CardType.ACT, 'event', 'E2', ('S2', 'S3')),
                                ('A4', ct.CardType.ACT, 'event', 'E4', ('S4',)))
        self.spec = described(asking.QuestionSpec(FAM.Q_REL, 'rel.deny', ('E4', 'E2'), None, '', False, ('E4', 'E2'),
                                                  census='R1'), (SC.STATEMENT, SS.DENIED), DONE)
        self.make = lambda calibration: built_request(WRAPPED, cards, objects, [self.spec], calibration)
        self.good = ('supports', [DENIAL_Q, FIRST_HALF_Q]), ('contradicts', [])

    def test_one_item_calibrates_and_none_does_not(self) -> None:
        self.assertEqual(settle.CALIBRATION_FLOOR, 1)
        one = answered(self.make([K1_ITEM]), WRAPPED, *self.good)
        self.assertEqual((one.health['refused'], one.questions[0]['result']), ([], 'supported'))
        none = answered(self.make([]), WRAPPED, *self.good)
        self.assertEqual(none.health['refused'], ['question_health:uncalibrated'])
        self.assertEqual(none.questions[0]['reasons'], ['question_health:uncalibrated'])

    def test_h2_the_one_item_supported_refuses_its_request(self) -> None:
        built = self.make([K1_ITEM])
        verdicts = json.loads(json.dumps({'unlisted': []}))
        rows = []
        for item in built.items:
            for member, claim_id in (('claim', item.claim), ('control', item.control)):
                if item.role == 'calibration':
                    value = 'supports'  # the known-false claim AND its control supported: a release-biased answer
                else:
                    value = self.good[0][0] if member == 'claim' else self.good[1][0]
                quotes = [DENIAL_Q, FIRST_HALF_Q] if (item.role == 'question' and member == 'claim') else []
                rows.append({'claim': claim_id, 'verdict': value, 'attached': 'yes', 'qualifiers': [],
                             'evidence': list(item.cited[:1]), 'quotes': quotes})
        verdicts['verdicts'] = rows
        cited = {}
        for item in built.items:
            cited[item.claim] = item.cited
            cited[item.control] = item.cited
        read = appraise_read.read_questions(json.dumps(verdicts), built.claim_ids, cited, len(units_of(WRAPPED)))
        locations = {item.claim: located(WRAPPED, item, read.verdicts[item.claim].quotes) for item in built.items}
        with mock.patch.object(asking, 'eligible', return_value=True):
            found = settle.settle_questions(built, read, locations, None)
        self.assertIn('question_health:calibration', found.health['refused'])
        self.assertEqual(found.questions[0]['result'], 'unresolved')
        self.assertTrue(found.calibration[0]['breach'])


# --- D315 (6): G1's exact set ------------------------------------------------------------------------------------------


class SessionNotTests(SimpleTestCase):
    """DECISIONS D315 (6) with probe-check4's ck4_g1.py scene: a colonoscopy X1 whose ONLY examination E1 has its
    session left open. "This act was not done during session X1." is exact for an examination done (in another session)
    or planned (never done): never for an ATTEMPT - begun, not completed, so "not done" while it WAS X1's examination,
    and an established answer would release 45385 - nor for one whose status is in doubt (it may be an attempt)."""

    def scene(self, status) -> object:
        doc = colonoscopy()
        doc.exam(1, status=status, session=F.SILENT, performer=F.SILENT)
        return doc.build()

    def test_g1_is_asked_of_an_act_done_or_planned_and_never_of_an_attempt_or_one_in_doubt(self) -> None:
        for name, status, asked in (('attempted', sup(Status.ATTEMPTED_NOT_COMPLETED), False),
                                    ('in doubt', unres(Status.PERFORMED, ct.Reason.UNAPPRAISED), False),
                                    ('planned', sup(Status.PLANNED), True), ('performed', sup(Status.PERFORMED), True)):
            R = self.scene(status)
            plan = asking.plan(R, ())
            g1 = [spec for spec in plan.specs if spec.census == 'G1']
            with self.subTest(status=name):
                self.assertEqual(bool(g1), asked)
                if not asked:
                    self.assertTrue([why for why in plan.blocked if why.startswith('D314 (fact.session.not is not exact')],
                                    plan.blocked)
                    self.assertTrue(evaluate.decide('45385', (), R).held_facts)
        self.assertEqual(QC.QUESTION_SOURCES['fact.session.not'].exact[0].names(), ['act/performed', 'act/planned'])


# --- D323 F3: FINAL-V2 5.7 measure 4 for the lane's modules -------------------------------------------------------------


class GuardTests(SimpleTestCase):
    """DECISIONS D323 F3: tests.test_guard_static's NoWordLists and WordsNeverDecide find nothing in the lane's modules
    (typed Enums, never a word list) - each guard's own function over each module's own source - and a planted word
    list in question_claims is found (the positive control)."""

    MINE = ('contract/question_claims', 'contract/proof', 'contract/appraise_read', 'contract/appraise_schema',
            'contract/settle')

    def test_the_lanes_modules_hold_no_word_list(self) -> None:
        from tests import test_guard_static as T
        values = T._design_values()
        modules = T._v2_modules()
        scope = T._scope()
        for key in self.MINE:
            with self.subTest(module=key):
                self.assertEqual(T.no_word_lists(modules[key], key, values), [])
                if key in scope:
                    self.assertEqual(T.words_never_decide(scope[key], key, set()), [])
        planted = modules['contract/question_claims'] + "\n_PLANTED = ('was not done', 'was done')\n"
        self.assertTrue(T.no_word_lists(planted, 'contract/question_claims', values))


class QuestionPinTests(SimpleTestCase):
    """The two question-side pins this lane owns, written here so a change of the instruction or of a template, a
    declared set or the relation forms' order is deliberate (DECISIONS D313's "each form pinned"; question_claims.pins,
    their owning function). Moved by this lane: APPRAISAL_INSTRUCTIONS_Q_SHA256_V3 ef433f12... -> c6f8888d... (PROOF,
    D318 (1)) -> 993fa47c... (the repair pass, RC-2: every passage named by the claim line's cited units and named
    cards); QUESTION_TEMPLATES_SHA256_V3 55f9e27b... -> 24622b1c... (the narrow Q-REL forms, the route forms, G1's
    set, the relation forms' order). Moved by the r3c claims lane (DECISIONS D324 (9), RF2-CLM-1: the frame value
    passage named by the claim line's value field and exempt from the heading ban; the act's own passage never a
    heading): APPRAISAL_INSTRUCTIONS_Q_SHA256_V3 993fa47c... -> 6a798464...; QUESTION_TEMPLATES_SHA256_V3 24622b1c... ->
    a7971627... (CLAIM_LINE_Q's value field, VALUE_FIELD and VALUE_NONE). Moved by the r3d claims lane (DECISIONS D325
    (4), L3P-2: PROOF's session clause leaves the claim's value units out of a session's passage):
    APPRAISAL_INSTRUCTIONS_Q_SHA256_V3 6a798464... -> 35fb05df...; QUESTION_TEMPLATES_SHA256_V3 unchanged (the claim
    line, VALUE_FIELD and VALUE_NONE are the same strings). LOCAL_SCHEMA_Q and QUESTION_BOUND unchanged;
    QUESTION_ENGINE_SHA256_V3 is computed over every engine module (other lanes' too), so it is never written here."""

    def test_the_lanes_question_pins(self) -> None:
        found = QC.pins()
        self.assertEqual(found['APPRAISAL_INSTRUCTIONS_Q_SHA256_V3'],
                         '35fb05df356d56b165979b44e5bd7381e0f7b36205a5d432e41d50fe439e7ef7')
        self.assertEqual(found['QUESTION_TEMPLATES_SHA256_V3'],
                         'a79716271cfb7cdfc4627e15db149bac820af1f164f4151a21697ddf24144a94')
        self.assertEqual(found['APPRAISAL_LOCAL_SCHEMA_Q_SHA256_V3'],
                         'ef14862db84d7ae4671adb80497d1342b60d2ae848863ce0610dcaf85f7b44bc')


class OneVocabularyTests(SimpleTestCase):
    """question_claims holds the family names as an Enum (no word list) - the values asking.Family carries, member for
    member, so a spec's family always names a family the request knows."""

    def test_the_families_are_askings(self) -> None:
        self.assertEqual({member.name: member.value for member in QC.QuestionFamily},
                         {member.name: member.value for member in asking.Family})
        self.assertEqual(set(QC.FAMILY_SUBJECTS), set(QC.QuestionFamily))
        self.assertEqual({form.value for form in QC.Form}, set(QC.QUESTION_TEMPLATES))
