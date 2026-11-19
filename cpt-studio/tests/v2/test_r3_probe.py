"""Round r3's probe prototype (DECISIONS D306-D308; build-v2/a2b/r3/design/DESIGN-v2.md, PROBE-v2.md section 3 item 1):
the question planner, the question request, the proof location, the question settle and the R_q fold. Every input is
SYNTHETIC (invented ids, spans and words; tests/v2/evaluate_fixtures' builders): no document is read and nothing is
sent. On int2 (the base) every test is red: the modules it exercises do not exist there.

What each class asks of the prototype:
- ProofTests: contract/proof.locate - a quote locates only inside its own object's passage, one per named object, never
  overlapping, never across a heading's words, never a paraphrase, a unit label, under 12 characters or one token.
- QuestionRequestTests: contract/question_claims - every control is the claim's EXACT negation (R3D-01), the body is
  effort max at 128,000 tokens with LOCAL_SCHEMA_Q, the connector recognizes it, the fact instruction is int2's
  byte for byte, the request is byte-stable.
- SettleTests: contract/settle.settle_questions - establishment needs the claim supported with a located proof AND its
  exact negation rejected AND a healthy, calibrated request (H1-H5); a holding answer is recorded and read by nothing.
- ExclusiveTests, PartitionTests: exclusivity, P-NODROP, the calibration quota, the split.
- PlanTests: engine/asking - READING witnesses asked, FABLE / CODER / BILLING witnesses never, the releasable filter.
- OverlayTests, FoldTests: R_q releases through answers and never excludes (4.6 reads R_base); the fold applies an
  answer only where the base leaves its fact open.
- The fix round's (DECISIONS D310): StomaRouteTests (1), the colonoscopy route table both ways; CalibrationSourceTests
  (4), K3's second source, the same-family item and the refill; HealthRulingTests (5), H2 and H4 as ruled; RowSevenTests
  (5), G1; and the killing tests of the surviving mutants (6): PassageHeadingTests (M19), DenialPairTests (M10),
  QuotesBoundTests, CompletenessTests (H1) and CalibrationSourceTests' K3-without-K1.
- The repair round's (DECISIONS D313, after step 1 short's hollow proof): QuestionWordingTests - one pin per question
  form (test_form_<form>): the reviewed claim and control, the positive sentence equal to the fact pass's CURRENT
  sentence under gemini-appraisal@2 and bound to that one source, the control its exact negation; RED on the unrepaired
  prototype for the reach and the reached anatomy - and QuestionBoundTests, e.2's QUESTION_BOUND from the measured t_q.
- The second repair round's (DECISIONS D314, after step 1 long's request 2 asked a TRUE sentence of a denial as a known
  false calibration item): QuestionClassTests - every form's reviewed declared sets (EXACT), its sentence the fact pass's
  own form for its object class, Unbuildable for every subject outside (pin c: the request builder and the planner, the
  held fact held with its census reason; G1 the one named exception); CalibrationClassTests - K1, K2 and K4 only of an
  act established performed, never of a denial, a plan, an attempt or an act in doubt of any K form (pin b), every drawn
  claim false as worded on a constructed FactSet (pin a, constructed), the one predicate on the class _acts_of reads;
  EntryAnchorTests - the entry bound to the act's anchor units, with the restated-act case where D313's sentence is true
  and the anchored one false. A stub spec reaches the request DESCRIBED (``described``) as the planner hands it.
- The third repair round's (DECISIONS D315, after the lead's first-hand read of step 1 long's keyed items found K2 items
  naming a session that never took place and K4 items of an act that is a part of another): a calibration item is known
  false only if it is false under every reading of EACH object it names. K2SessionTests - K2's alternative drawn only
  between two exclusive sessions that took place (asking.exclusive_sessions, the one predicate, read by the K2 draw
  only): a session whose only examination is denied, a planned future session, a sedation service, an office visit of
  the same encounter, an unsettled or non-GI session and a part of another session give no K2; two procedure sessions
  that took place give it both ways. K4PartTests - K4 only of an act whose part_of is silent (a lift, an adjunct, a
  step, an access or a component takes its object from the whole). StatusPinTests - the unit pins of the D314
  checker's surviving mutants: an unestablished status is IN_DOUBT (D), the class is pass 1's filed state (E), an
  unlisted denial DENIES (P)."""
from __future__ import annotations

import dataclasses
import json
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from studio import interpretation
from studio.interpretation import fable_adapter
from studio.interpretation.contract import appraise_prompt, appraise_read, appraise_schema, claims, proof, question_claims
from studio.interpretation.contract import settle
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import asking, coverage, evaluate, pairing
from studio.interpretation.engine import facts as F
from studio.interpretation.engine.types import Id, Span
from tests.v2.evaluate_fixtures import (DC, ON, TEAM, Doc, E, L, Kind, Landmark, SessionKind, Status, X, colonoscopy,
                                        contra, doubted, fact, neg, sup, unit, unlisted, unres)

A = ct.Attribute
TEXT = ('Colonoscopy report. [The heading line]\n'
        'The scope was advanced to the cecum without difficulty today.\n'
        'A small polyp in the sigmoid colon was removed with a cold snare.\n'
        'No biopsies of the rectum were taken during this procedure.\n')


def passage(text: str, words: str) -> question_claims.PassageSet:
    at = text.index(words)
    return question_claims.PassageSet(((at, at + len(words)),))


# getattr: the RED run on the D313 prototype (which has no declared sets) imports this module too, so its D314 tests
# fail one by one while every older test still runs (NOTES, Repair round 2)
SC = getattr(question_claims, 'SubjectClass', None)
SS = getattr(question_claims, 'SubjectStatus', None)


def typical(exact) -> tuple:
    """A (class, status) the declared set admits: an act established performed, a session, a single lesion or an
    unlisted doubt where it admits one (DECISIONS D314)."""
    for found in ((SC.ACT, SS.PERFORMED), (SC.SESSION, SS.NONE), (SC.LESION, SS.SINGLE), (SC.UNLISTED, SS.DOUBTS)):
        if found in exact.pairs:
            return found
    return sorted(exact.pairs, key=lambda pair: (pair[0].value, pair[1].value))[0]


def described(spec):
    """DECISIONS D314: a stub spec as the planner hands it to the request - each subject described (engine/asking.
    describe) as one its form is exact for (``typical``) - when the test gave it no description; the request builder
    writes no sentence for an undescribed spec (QuestionClassTests pins that)."""
    if getattr(spec, 'described', None):
        return spec
    source = question_claims.QUESTION_SOURCES.get(spec.form)
    if source is None or not hasattr(source, 'exact'):
        return spec
    return dataclasses.replace(spec, described=tuple(typical(exact) for exact in source.exact))


# --- the proof ---------------------------------------------------------------------------------------------------------


class ProofTests(SimpleTestCase):
    """contract/proof.locate (DESIGN-v2 c.3, b.0)."""

    def setUp(self) -> None:
        self.scope = passage(TEXT, 'The scope was advanced to the cecum without difficulty today.')
        self.snare = passage(TEXT, 'A small polyp in the sigmoid colon was removed with a cold snare.')
        self.denial = passage(TEXT, 'No biopsies of the rectum were taken during this procedure.')

    def test_a_quote_in_each_named_objects_passage_locates(self) -> None:
        found = proof.locate(TEXT, (self.denial, self.snare), None,
                             ['No biopsies of the rectum were taken', 'removed with a cold snare'])
        self.assertTrue(found.located, found)
        self.assertEqual(len(found.spans), 2)

    def test_the_quotes_may_come_in_either_order(self) -> None:
        found = proof.locate(TEXT, (self.denial, self.snare), None,
                             ['removed with a cold snare', 'No biopsies of the rectum were taken'])
        self.assertTrue(found.located, found)

    def test_one_quote_for_a_two_object_claim_never_locates(self) -> None:
        found = proof.locate(TEXT, (self.denial, self.snare), None, ['No biopsies of the rectum were taken'])
        self.assertFalse(found.located)

    def test_a_quote_from_another_objects_passage_never_locates(self) -> None:
        found = proof.locate(TEXT, (self.denial, self.snare), None,
                             ['No biopsies of the rectum were taken', 'advanced to the cecum without difficulty'])
        self.assertFalse(found.located)

    def test_overlapping_quotes_never_locate(self) -> None:
        both = question_claims.PassageSet(self.snare.ranges)
        found = proof.locate(TEXT, (both, both), None, ['small polyp in the sigmoid colon', 'in the sigmoid colon was'])
        self.assertFalse(found.located)

    def test_a_fabricated_or_paraphrased_quote_never_locates(self) -> None:
        for quote in ('The polyp was taken out with a snare', 'removed with a hot snare'):
            with self.subTest(quote=quote):
                self.assertFalse(proof.locate(TEXT, (self.snare,), None, [quote]).located)

    def test_a_short_or_one_token_quote_never_locates(self) -> None:
        self.assertEqual(proof.locate(TEXT, (self.snare,), None, ['cold snare']).reason, proof.PROOF_SHORT)
        self.assertEqual(proof.locate(TEXT, (self.snare,), None, ['sigmoidcolonwas']).reason, proof.PROOF_SHORT)

    def test_a_unit_label_or_a_page_line_inside_never_locates(self) -> None:
        for quote in ('[S3] A small polyp in the sigmoid colon', '[Page 1] A small polyp in the sigmoid colon'):
            with self.subTest(quote=quote):
                self.assertFalse(proof.locate(TEXT, (self.snare,), None, [quote]).located)

    def test_whitespace_runs_read_as_one_space(self) -> None:
        found = proof.locate(TEXT, (self.snare,), None, ['A small   polyp\nin the sigmoid colon'])
        self.assertTrue(found.located, found)

    def test_no_quote_never_locates_and_extra_quotes_inside_the_passage_do(self) -> None:
        # DECISIONS D318 (1): a proof is void only by a quote outside the claim's passages, an overlap or a short quote -
        # three quotes inside the one passage the claim names locate (the two-quote bound voided right answers); more
        # than proof.QUOTES_MAX never locate (tests/v2/test_r3_claims.py pins the cap)
        self.assertEqual(proof.locate(TEXT, (self.snare,), None, []).reason, proof.PROOF_MISSING)
        self.assertTrue(proof.locate(TEXT, (self.snare,), None, ['A small polyp in the', 'sigmoid colon was removed',
                                                                 'with a cold snare.']).located)

    def test_a_heading_cut_from_a_passage_never_carries_the_quote(self) -> None:
        line = TEXT.index('Colonoscopy report.')
        heading = TEXT.index('[The heading line]')
        cut = question_claims.PassageSet(((line, heading),))  # the act's passage less the heading's words
        self.assertFalse(proof.locate(TEXT, (cut,), None, ['[The heading line]']).located)
        self.assertTrue(proof.locate(TEXT, (cut,), None, ['Colonoscopy report.']).located)

    def test_a_session_reach_needs_every_quote_inside_its_alternatives(self) -> None:
        alternatives = (self.scope, self.snare)
        self.assertTrue(proof.locate(TEXT, (), None, ['advanced to the cecum without'], alternatives).located)
        self.assertTrue(proof.locate(TEXT, (), None, ['in the sigmoid colon was'], alternatives).located)
        self.assertTrue(proof.locate(TEXT, (), None, ['advanced to the cecum', 'in the sigmoid colon'],
                                     alternatives).located)
        # DECISIONS D318 (1): a second quote inside the same alternative never voids the proof (step 1 long's reach)
        self.assertTrue(proof.locate(TEXT, (), None, ['advanced to the cecum', 'without difficulty today'],
                                     alternatives).located)
        self.assertFalse(proof.locate(TEXT, (), None, ['advanced to the cecum', 'No biopsies of the rectum'],
                                      alternatives).located)  # a quote outside both alternatives voids it


# --- the question request ----------------------------------------------------------------------------------------------


def stub_request(specs: list, calibration: list = (), seed: str = 'seed',
                 events: tuple = (), extra_cards: tuple = ()) -> question_claims.QuestionRequest:
    """A question request built over a synthetic fact request: four act cards (A1-A4 for E1-E4) on units S1-S4, one
    session card X1, one lesion card L1, the four units of TEXT; ``events`` the view's stored event records (a frame
    value's sources: frame_source)."""
    units = []
    at = 0
    for number, line in enumerate(TEXT.split('\n')[:4], start=1):
        start = TEXT.index(line, at)
        units.append({'id': f'S{number}', 'start': start, 'end': start + len(line)})
        at = start + len(line)
    cards = [ct.Card(f'A{n}', ct.CardType.ACT, (f'S{n}',), None, None) for n in range(1, 5)]
    cards += [ct.Card('X1', ct.CardType.SESSION, ('S2',), None, None), ct.Card('L1', ct.CardType.LESION, ('S3',), None,
                                                                                None)]
    objects = {f'A{n}': ('event', f'E{n}') for n in range(1, 5)}
    objects.update({'X1': ('session', 'X1'), 'L1': ('lesion', 'L1')})
    for card_id, card_type, card_units in extra_cards:  # DECISIONS D313's reach tests: an anatomy entry's card
        cards.append(ct.Card(card_id, card_type, card_units, None, None))
        objects[card_id] = (card_type.value, card_id)
    claim_set = SimpleNamespace(cards=tuple(cards), objects=objects)
    built = SimpleNamespace(framed='<<<DOCUMENT-0000000000000000 BEGIN>>>\nsynthetic\n<<<DOCUMENT-0000000000000000 END>>>',
                            claim_set=claim_set)
    view = {'units': units, 'events': list(events), 'sessions': [], 'sections': [], 'unlisted': []}
    plan = asking.RequestPlan(tuple(described(spec) for spec in specs), tuple(described(item) for item in calibration),
                              seed)
    return question_claims.build_question_request_fable(built, TEXT, (), view, plan, 1, 1)


REL = described(asking.QuestionSpec(asking.Family.Q_REL, 'rel', ('E4', 'E3'), None, '', False, ('E4', 'E3'),
                                     census='R2'))
DATE = described(asking.QuestionSpec(asking.Family.Q_FACT, 'fact.date_relation', ('E3',), A.DATE_RELATION,
                                     'on_date_of_service', False, ('E3',), census='F1'))
SESSION_NOT = described(asking.QuestionSpec(asking.Family.Q_FACT, 'fact.session.not', ('E1',), A.SESSION, 'X1', True,
                                            ('E1', 'X1'), census='G1'))
K1 = described(asking.CalibrationSpec('K1', asking.Family.Q_FACT, 'fact.performer', ('E2',), A.PERFORMER,
                                      'documenting_team', True, ('E2',)))
K2 = described(asking.CalibrationSpec('K2', asking.Family.Q_FACT, 'fact.session', ('E3',), A.SESSION, 'X1', False,
                                      ('E3', 'X1')))
K4 = described(asking.CalibrationSpec('K4', asking.Family.Q_ONLESION, 'onlesion', ('E3', 'L1'), A.TARGET_LESION, 'L1',
                                      True, ('E3', 'L1')))


class QuestionRequestTests(SimpleTestCase):
    """contract/question_claims (DESIGN-v2 b, c.2, e.1)."""

    def test_every_control_is_the_claims_exact_negation(self) -> None:
        built = stub_request([REL, DATE, SESSION_NOT], [K1, K2, K4])
        found = {item.spec.key: (item.claim_sentence, item.control_sentence) for item in built.items}
        self.assertEqual(found[REL.key], ('This statement does not concern act A3.', 'This statement concerns act A3.'))
        self.assertEqual(found[DATE.key], ('This act was done on the date of service.',
                                           'This act was not done on the date of service.'))
        self.assertEqual(found[SESSION_NOT.key], ('This act was not done during session X1.',
                                                  'This act was done during session X1.'))
        self.assertEqual(found[K1.key][0], 'This act was not done by the documenting clinician or a member of their team.')
        for claim, control in found.values():  # one sentence, its negation: exactly one is true of any document
            self.assertTrue(claim.replace(' not ', ' ') == control or control.replace(' not ', ' ') == claim
                            or claim.replace('does not concern', 'concerns') == control, (claim, control))

    def test_the_body_is_effort_max_at_the_connectors_output_with_the_quotes_schema(self) -> None:
        body = stub_request([REL], [K1, K2]).request.body
        self.assertEqual(body['output_config']['effort'], 'max')
        self.assertEqual(body['max_tokens'], 128000)
        self.assertEqual(body['output_config']['format']['schema'], appraise_schema.LOCAL_SCHEMA_Q)
        self.assertIn('quotes', appraise_schema.LOCAL_SCHEMA_Q['properties']['verdicts']['items']['required'])
        self.assertNotIn('quotes', appraise_schema.LOCAL_SCHEMA['properties']['verdicts']['items']['required'])
        system = body['system'][0]['text']
        self.assertTrue(system.startswith(question_claims.FACT_INSTRUCTIONS))
        self.assertIn('The absence of a statement is never a passage', system)

    def test_the_fact_instruction_is_the_products_byte_for_byte(self) -> None:
        self.assertEqual(question_claims.FACT_INSTRUCTIONS, appraise_prompt.INSTRUCTIONS)

    def test_the_connector_sends_it_as_an_appraisal_and_nothing_altered(self) -> None:
        built = stub_request([REL], [K1, K2])
        self.assertEqual(fable_adapter.body_kind(built.request.body), (fable_adapter.APPRAISAL, ''))
        altered = json.loads(json.dumps(built.request.body))
        altered['output_config']['effort'] = 'high'
        self.assertEqual(fable_adapter.body_kind(altered)[0], '')

    def test_every_claim_line_is_marked_proof_and_both_members_are_asked(self) -> None:
        built = stub_request([REL, DATE], [K1, K2])
        self.assertEqual(len(built.lines), 2 * len(built.items))
        self.assertTrue(all('; proof): ' in line for line in built.lines))
        self.assertEqual(sorted(built.roles), sorted(f'K{n}' for n in range(1, 2 * len(built.items) + 1)))

    def test_the_request_is_byte_stable(self) -> None:
        first = stub_request([REL, DATE, SESSION_NOT], [K1, K2, K4])
        second = stub_request([REL, DATE, SESSION_NOT], [K1, K2, K4])
        self.assertEqual(first.request.canonical_sha256, second.request.canonical_sha256)
        self.assertNotEqual(first.request.canonical_sha256,
                            stub_request([REL, DATE, SESSION_NOT], [K1, K2, K4], seed='other').request.canonical_sha256)

    def test_each_item_names_its_claim_and_its_controls(self) -> None:  # replay_v2's question_pool reads these names
        built = stub_request([REL, DATE], [K1, K2])
        for item in built.items:
            self.assertEqual(item.controls, (item.control,))
        found = settled(built, answer_of(built, {}))
        self.assertTrue(all(record['controls'] == [record['control']] for record in found.questions))

    def test_a_two_object_claim_needs_two_passages(self) -> None:
        built = stub_request([REL], [K1, K2])
        item = next(found for found in built.items if found.spec.key == REL.key)
        self.assertEqual(len(item.required), 2)


# --- the question settle -------------------------------------------------------------------------------------------------


def answer_of(built: question_claims.QuestionRequest, choices: dict, default: str = 'contradicts') -> str:
    """An answer: ``choices`` maps (spec key, 'claim'|'control') to (verdict, quotes); every other claim gets
    ``default`` (a calibration claim contradicts, its control supports, unless chosen)."""
    verdicts = []
    for item in built.items:
        for member, claim_id in (('claim', item.claim), ('control', item.control)):
            if item.role == 'calibration' and (item.spec.key, member) not in choices:
                value, quotes = ('contradicts', []) if member == 'claim' else ('supports', [])
            else:
                value, quotes = choices.get((item.spec.key, member), (default, []))
            verdicts.append({'claim': claim_id, 'verdict': value, 'attached': 'yes', 'qualifiers': [],
                             'evidence': list(item.cited[:1]), 'quotes': list(quotes)})
    return json.dumps({'verdicts': verdicts, 'unlisted': []})


def settled(built: question_claims.QuestionRequest, answer: str, eligible: bool = True,
            outcome: str = 'answered') -> settle.QuestionSettlement:
    cited = {}
    for item in built.items:
        cited[item.claim] = item.cited
        cited[item.control] = item.cited
    read = appraise_read.read_questions(answer, built.claim_ids, cited, 4)
    assert hasattr(read, 'verdicts'), read
    locations = {}
    for item in built.items:
        verdict = read.verdicts.get(item.claim)
        locations[item.claim] = proof.locate(TEXT, item.required, item.optional,
                                             verdict.quotes if verdict else (), item.alternatives)
    with mock.patch.object(asking, 'eligible', return_value=eligible):
        return settle.settle_questions(built, read, locations, None, outcome)


PROOF = ['No biopsies of the rectum were taken', 'removed with a cold snare']


class SettleTests(SimpleTestCase):
    """contract/settle.settle_questions (DESIGN-v2 d)."""

    def setUp(self) -> None:
        self.built = stub_request([REL], [K1, K2, K4, dataclasses.replace(K1, subjects=('E1',), names=('E1',))])

    def result(self, choices: dict, **kw) -> dict:
        return settled(self.built, answer_of(self.built, choices), **kw).questions[0]

    def test_supported_with_a_located_proof_and_the_negation_rejected_establishes(self) -> None:
        found = self.result({(REL.key, 'claim'): ('supports', PROOF), (REL.key, 'control'): ('contradicts', [])})
        self.assertEqual((found['result'], found['reasons']), ('supported', []))
        self.assertEqual(len(found['proof']), 2)

    def test_one_wrong_supports_meets_the_negations_correct_supports_and_holds(self) -> None:  # R3D-01's mechanism
        found = self.result({(REL.key, 'claim'): ('supports', PROOF), (REL.key, 'control'): ('supports', [])})
        self.assertEqual(found['reasons'], ['question_incoherent'])

    def test_both_contradicted_holds(self) -> None:
        found = self.result({(REL.key, 'claim'): ('contradicts', []), (REL.key, 'control'): ('contradicts', [])})
        self.assertEqual(found['reasons'], ['question_contradicts'])

    def test_a_fabricated_quote_holds(self) -> None:
        found = self.result({(REL.key, 'claim'): ('supports', ['No biopsies of the colon were taken',
                                                               'removed with a cold snare']),
                             (REL.key, 'control'): ('contradicts', [])})
        self.assertEqual(found['reasons'], [proof.PROOF_UNLOCATED])

    def test_a_missing_proof_holds(self) -> None:
        found = self.result({(REL.key, 'claim'): ('supports', []), (REL.key, 'control'): ('contradicts', [])})
        self.assertEqual(found['reasons'], [proof.PROOF_MISSING])

    def test_a_holding_answer_is_recorded_and_establishes_nothing(self) -> None:
        found = self.result({(REL.key, 'claim'): ('contradicts', []), (REL.key, 'control'): ('supports', [])})
        self.assertEqual(found['result'], 'unresolved')
        self.assertTrue(found['held_by_answer'])

    def test_a_question_no_longer_eligible_holds(self) -> None:
        found = self.result({(REL.key, 'claim'): ('supports', PROOF), (REL.key, 'control'): ('contradicts', [])},
                            eligible=False)
        self.assertEqual(found['reasons'], ['question_not_eligible'])

    def test_a_calibration_item_established_the_release_way_refuses_the_whole_request(self) -> None:  # H2, P-CAL
        """K2 ("This act was done during session X1." where the act's session is another) answered supports with a
        located proof and its negation rejected: a release-biased answer - the request's every question is refused,
        a sound one included."""
        k2 = next(item for item in self.built.items if item.role == 'calibration' and item.spec.kind == 'K2')
        found = settled(self.built, answer_of(self.built, {
            (REL.key, 'claim'): ('supports', PROOF), (REL.key, 'control'): ('contradicts', []),
            (k2.spec.key, 'claim'): ('supports', ['removed with a cold snare', 'advanced to the cecum without']),
            (k2.spec.key, 'control'): ('contradicts', [])}))
        self.assertTrue(any(item['breach'] for item in found.calibration))
        self.assertIn('question_health:calibration', found.health['refused'])
        self.assertEqual(found.questions[0]['result'], 'unresolved')

    def test_a_calibration_lean_refuses_the_whole_request(self) -> None:  # H3: supports above 1/4 of the items
        calibration = [item for item in self.built.items if item.role == 'calibration']
        choices = {(REL.key, 'claim'): ('supports', PROOF), (REL.key, 'control'): ('contradicts', [])}
        for item in calibration[:2]:
            choices[(item.spec.key, 'claim')] = ('supports', [])
        found = settled(self.built, answer_of(self.built, choices))
        self.assertIn('question_health:calibration_lean', found.health['refused'])
        self.assertEqual(found.questions[0]['result'], 'unresolved')

    def test_control_acceptance_above_half_refuses_the_whole_request(self) -> None:  # H4
        built = stub_request([REL, DATE, SESSION_NOT, dataclasses.replace(DATE, subjects=('E2',), names=('E2',))],
                             [K1, K2, K4, dataclasses.replace(K1, subjects=('E1',), names=('E1',))])
        choices = {(spec.key, 'control'): ('unclear', []) for spec in (DATE, SESSION_NOT)}
        choices.update({(REL.key, 'claim'): ('supports', PROOF), (REL.key, 'control'): ('contradicts', [])})
        for item in built.items:  # a calibration claim (known false) left unrejected counts as H4's not-rejected member
            if item.role == 'calibration':
                choices[(item.spec.key, 'claim')] = ('unclear', [])
        found = settled(built, answer_of(built, choices, default='unclear'))
        self.assertIn('question_health:controls', found.health['refused'])
        self.assertNotIn('question_health:calibration_lean', found.health['refused'])
        self.assertEqual(found.questions[0]['result'] if found.questions[0]['subjects'] == ['E4', 'E3']
                         else 'unresolved', 'unresolved')

    def test_a_request_with_no_calibration_item_is_uncalibrated(self) -> None:  # H5, DECISIONS D319: one item a request
        choices = {(REL.key, 'claim'): ('supports', PROOF), (REL.key, 'control'): ('contradicts', [])}
        built = stub_request([REL], [])
        found = settled(built, answer_of(built, choices))
        self.assertIn('question_health:uncalibrated', found.health['refused'])
        self.assertEqual(found.questions[0]['result'], 'unresolved')
        built = stub_request([REL], [K1])  # the one item D319 draws: calibrated
        found = settled(built, answer_of(built, choices))
        self.assertNotIn('question_health:uncalibrated', found.health['refused'])
        self.assertEqual(found.questions[0]['result'], 'supported')

    def test_a_failed_request_leaves_its_questions_unresolved(self) -> None:
        found = settle.settle_questions(self.built, None, {}, None, 'too_long')
        self.assertEqual(found.questions[0]['reasons'], ['question_request_failed:too_long'])


class ExclusiveTests(SimpleTestCase):
    """d.2 row 5: two established values of one single-valued slot establish neither."""

    def record(self, attribute: str, value: str, subject: str = 'E3') -> dict:
        return {'family': 'Q-FACT', 'subjects': [subject], 'attribute': attribute, 'value': value, 'negated': False,
                'result': 'supported', 'reasons': [], 'proof': [{'start': 0, 'end': 5}]}

    def test_two_values_of_a_single_valued_slot_conflict(self) -> None:
        found = settle.exclusive([self.record('session', 'X1'), self.record('session', 'X2')])
        self.assertEqual([item['reasons'] for item in found], [['question_conflict'], ['question_conflict']])

    def test_a_list_attribute_takes_each_value(self) -> None:
        found = settle.exclusive([self.record('reached', 'cecum', 'X1'), self.record('reached', 'ileum', 'X1')])
        self.assertEqual([item['result'] for item in found], ['supported', 'supported'])


# --- the partition and the calibration draw -------------------------------------------------------------------------------


def specs_of(count: int) -> list:
    return [dataclasses.replace(REL, subjects=(f'E{n + 10}', 'E3'), names=(f'E{n + 10}', 'E3')) for n in range(count)]


POOL = [dataclasses.replace(K1, subjects=(f'E{n}',), names=(f'E{n}',)) for n in range(1, 30)] + [
    dataclasses.replace(K2, subjects=(f'E{n}',), names=(f'E{n}', 'X1')) for n in range(1, 30)]


class PartitionTests(SimpleTestCase):
    """e.3, e.4, b.9."""

    def test_every_question_is_in_exactly_one_request_within_the_bound(self) -> None:  # P-NODROP
        specs = specs_of(130)
        requests = asking.partition(specs, POOL, 1)
        asked = [spec.key for request in requests for spec in request.questions]
        self.assertEqual(sorted(asked), sorted(spec.key for spec in specs))
        self.assertTrue(all(request.claims <= asking.QUESTION_BOUND for request in requests))
        self.assertGreater(len(requests), 1)

    def test_each_request_draws_one_negative_item(self) -> None:
        # DECISIONS D319 (the owner's): ONE calibration item a request, whatever its questions (b.9's max(4, ceil(q/4))
        # superseded); b.9's polarity quota keeps it negative-form wherever the pool has one
        for count in (1, 3, 17, 40):
            with self.subTest(count=count):
                drawn = asking.draw(POOL, specs_of(count), 'seed')
                self.assertEqual(len(drawn), 1)
                self.assertGreaterEqual(2 * sum(1 for item in drawn if item.negative), len(drawn))

    def test_the_draw_is_deterministic(self) -> None:
        self.assertEqual(asking.draw(POOL, specs_of(9), 'a'), asking.draw(POOL, specs_of(9), 'a'))

    def test_an_overrun_splits_in_halves_and_one_question_stays(self) -> None:
        # DECISIONS D318 (2) and D319: the measured bound (18 claims) carries 8 questions and their one item a request,
        # so the first request of ten questions holds eight and splits 4 + 4 (D313's 20 claims and four items held six)
        request = asking.partition(specs_of(10), POOL, 1)[0]
        count = len(request.questions)
        self.assertEqual(count, 8)
        halves = asking.split(request, POOL, 1)
        self.assertEqual([len(half.questions) for half in halves], [count // 2, count - count // 2])
        self.assertEqual(asking.split(asking.partition(specs_of(1), POOL, 1)[0], POOL, 1), ())


# --- the planner ------------------------------------------------------------------------------------------------------------


def plan_of(R) -> asking.Plan:
    return asking.plan(R, ())


class PlanTests(SimpleTestCase):
    """engine/asking.plan (DESIGN-v2 a.4; CENSUS-v2)."""

    def test_a_possible_statement_against_the_act_is_asked_as_q_rel(self) -> None:
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.SNARE), status=unres(Status.PERFORMED, ct.Reason.UNAPPRAISED), session=sup(X(1)))
        found = plan_of(doc.build())
        self.assertIn(('Q-REL', ('E3', 'E2')), {(spec.family.value, spec.subjects) for spec in found.specs})

    def test_a_status_witness_is_never_asked(self) -> None:  # C3: whether the act happened
        doc = colonoscopy(status=unres(Status.PERFORMED, ct.Reason.UNAPPRAISED))
        found = plan_of(doc.build())
        self.assertFalse([spec for spec in found.specs if spec.attribute is A.STATUS])

    def test_a_fact_fable_already_judged_is_never_re_asked(self) -> None:  # C2b
        doc = colonoscopy(date=unres(ON, ct.Reason.APPRAISAL_CONTRADICTS))
        found = plan_of(doc.build())
        self.assertFalse([spec for spec in found.specs if spec.attribute is A.DATE_RELATION])

    def test_a_fact_whose_check_failed_is_asked_with_its_one_value(self) -> None:  # F1
        doc = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION))
        found = plan_of(doc.build())
        self.assertIn(('E2', A.DATE_RELATION, 'on_date_of_service'),
                      {(spec.subjects[0], spec.attribute, spec.value) for spec in found.specs})

    def test_a_silent_entry_is_asked_with_its_one_satisfying_value(self) -> None:  # F2
        doc = colonoscopy(entry=F.SILENT)
        found = plan_of(doc.build())
        self.assertIn(('E2', A.ENTRY, 'documenting_clinician'),
                      {(spec.subjects[0], spec.attribute, spec.value) for spec in found.specs})

    def test_a_candidate_a_billing_rule_holds_asks_nothing_through_it(self) -> None:  # the releasable filter
        """The snare's entry established as nursing staff's (an established value failing the row: B5) beside its
        date that failed a check (F1): no answer can release 45385 through it, so its date is not asked for it."""
        doc = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION), entry=sup(ct.Owner.NURSING))
        found = plan_of(doc.build())
        self.assertFalse([spec for spec in found.specs if '45385' in found.serves.get(spec.key, ())])
        self.assertTrue(any(reason.startswith('BILLING') for reason in found.blocked))

    def test_a_pair_whose_statement_does_not_locate_is_never_asked(self) -> None:  # C4: anchor_invalid
        doc = colonoscopy()
        doc.event(3, kind=unres(Kind.SNARE, ct.Reason.ANCHOR_INVALID), status=unres(Status.PERFORMED,
                                                                                    ct.Reason.ANCHOR_INVALID),
                  session=unres(X(1), ct.Reason.ANCHOR_INVALID))
        found = plan_of(doc.build())
        self.assertFalse([spec for spec in found.specs if 'E3' in spec.subjects])
        located = colonoscopy()
        located.event(3, kind=sup(Kind.SNARE), status=unres(Status.PERFORMED, ct.Reason.UNAPPRAISED), session=sup(X(1)))
        self.assertTrue([spec for spec in plan_of(located.build()).specs if 'E3' in spec.subjects])

    def test_a_question_naming_an_object_with_no_card_is_never_planned(self) -> None:  # the stage's card guard
        doc = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION))
        R = doc.build()
        self.assertTrue(asking.plan(R, (), carded=lambda stored: True).specs)
        found = asking.plan(R, (), carded=lambda stored: stored != 'E2')
        self.assertFalse([spec for spec in found.specs if 'E2' in spec.names])
        self.assertIn(asking.C4_NO_CARD, found.blocked)

    def test_the_plan_is_empty_when_nothing_is_open(self) -> None:  # the fixed point
        self.assertEqual(plan_of(colonoscopy().build()).specs, ())

    def test_the_plan_reads_no_member_value_and_is_deterministic(self) -> None:
        doc = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION))
        self.assertEqual(plan_of(doc.build()).specs, plan_of(doc.build()).specs)


# --- R_q, R_base and the fold ------------------------------------------------------------------------------------------------


class OverlayTests(SimpleTestCase):
    """DESIGN-v2 f.1: answers release and never exclude."""

    def test_a_q_rel_answer_sets_the_pair_apart_on_r_q_only(self) -> None:
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.SNARE), status=unres(Status.PERFORMED, ct.Reason.UNAPPRAISED), session=sup(X(1)))
        base = doc.build()
        self.assertIsNot(pairing.relation(base, E(3), E(2)).relation, pairing.Relation.INDEPENDENT)
        R_q = dataclasses.replace(base, independent=frozenset({(E(3), E(2))}), base=base)
        self.assertIs(pairing.relation(R_q, E(3), E(2)).relation, pairing.Relation.INDEPENDENT)
        held = evaluate.decide('45385', (), base).held_facts
        self.assertTrue(held)
        self.assertFalse(evaluate.decide('45385', (), R_q).held_facts)

    def test_an_answer_never_excludes(self) -> None:  # ExclusionReadsBase: 4.6 reads R_base
        """A clip whose purpose is silent is a positive candidate of 45382 (possibly hemostasis), so the cited denial
        of bleeding control never excludes it on R_base. An answer "not done for hemostasis" takes the clip out of the
        group on R_q - and still 4.6 reads R_base, where the clip is a candidate: held, never excluded. The same facts
        read as if they were the base would exclude."""
        doc = colonoscopy(snare=False)
        doc.act(2, Kind.CLIP, purpose=F.SILENT)
        from tests.v2.test_evaluate import denial_event
        denial_event(doc, 3, Kind.BLEEDING_CONTROL)
        base = doc.build()
        kept = (Span(300, 325),)
        self.assertIsNone(evaluate.decide('45382', kept, base).exclusion)
        answered = dict(base.events)
        answered[E(2)] = {**answered[E(2)], A.PURPOSE: (F._answered_fact(F.SILENT, ct.Purpose.HEMOSTASIS, True, ()),)}
        R_q = dataclasses.replace(base, events=answered, base=base)
        decided = evaluate.decide('45382', kept, R_q)
        self.assertIsNone(decided.exclusion)
        self.assertTrue(decided.held_facts)
        as_base = dataclasses.replace(base, events=answered)
        self.assertIsNotNone(evaluate.decide('45382', kept, as_base).exclusion)

    def test_r_q_carries_its_base_through_the_bundling_readers_virtual_factset(self) -> None:
        doc = colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.CLIP, X(1), Span(900, 960)))
        base = doc.build()
        R_q = dataclasses.replace(base, independent=frozenset({(E(9), E(2))}), base=base)
        virtual, _ = coverage.Reader(R_q)._synthetic_wholes()
        self.assertIs(virtual.base, base)
        self.assertEqual(virtual.independent, R_q.independent)


class FoldTests(SimpleTestCase):
    """facts._answered: an established answer applies only where the base leaves its fact open."""

    def question(self, family: str, subjects: list, attribute=None, value: str = '', negated: bool = False,
                 form: str = '') -> dict:
        return {'family': family, 'form': form, 'subjects': subjects, 'attribute': attribute, 'value': value,
                'unlisted': asking.unlisted_index(tuple(subjects)), 'negated': negated, 'result': 'supported',
                'reasons': [], 'proof': [{'start': 200, 'end': 230}]}

    def test_a_fact_answer_fills_an_open_fact_and_never_an_established_one(self) -> None:
        base = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION)).build()
        events = {'questions': [self.question('Q-FACT', ['E2'], 'date_relation', 'on_date_of_service'),
                                self.question('Q-FACT', ['E1'], 'performer', 'other_clinician')]}
        R_q = F._answered(base, events)
        self.assertTrue(F.holds(F.fact(R_q, E(2), A.DATE_RELATION), ON))
        self.assertTrue(F.holds(F.fact(R_q, E(1), A.PERFORMER), TEAM))  # the established fact stays
        self.assertIs(R_q.base, base)
        self.assertFalse(F.holds(F.fact(base, E(2), A.DATE_RELATION), ON))

    def test_a_q_rel_answer_and_a_session_negation_fold(self) -> None:
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.EXAMINATION), status=sup(Status.PLANNED), session=F.SILENT)
        base = doc.build()
        R_q = F._answered(base, {'questions': [self.question('Q-REL', ['E3', 'E2']),
                                               self.question('Q-FACT', ['E3'], 'session', 'X1', True,
                                                             'fact.session.not')]})
        self.assertIn((E(3), E(2)), R_q.independent)
        self.assertFalse(F.possibly(F.fact(R_q, E(3), A.SESSION), X(1)))

    def test_a_lesion_answer_needs_the_multiplicity_its_form_presumes(self) -> None:
        doc = colonoscopy()
        doc.lesion(2, lesion_places=[sup(Landmark.RECTUM)])
        base = doc.build()
        R_q = F._answered(base, {'questions': [self.question('Q-LESION', ['L1', 'L2'], 'distinct_from', 'L2',
                                                             form='lesion.distinct_from')]})
        self.assertEqual(R_q.distinct, frozenset())  # neither lesion established single
        doc.lesions[L(1)][A.MULTIPLICITY] = (sup(ct.Multiplicity.SINGLE),)
        doc.lesions[L(2)][A.MULTIPLICITY] = (sup(ct.Multiplicity.SINGLE),)
        R_q = F._answered(doc.build(), {'questions': [self.question('Q-LESION', ['L1', 'L2'], 'distinct_from', 'L2',
                                                                    form='lesion.distinct_from')]})
        self.assertEqual(R_q.distinct, frozenset({(L(1), L(2))}))

    def test_an_unresolved_answer_folds_nothing(self) -> None:
        base = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION)).build()
        record = {**self.question('Q-FACT', ['E2'], 'date_relation', 'on_date_of_service'), 'result': 'unresolved'}
        self.assertIs(F._answered(base, {'questions': [record]}), base)

    def test_an_unlisted_entry_is_read_by_its_typed_index_never_by_its_subject_string(self) -> None:
        doc = colonoscopy()
        doc.unlisted.append(unlisted(ct.UnlistedWhat.ACT, Kind.CLIP, X(1), Span(900, 960)))
        base = doc.build()
        absorb = self.question('Q-ABSORB', ['u:0'], form='absorb')
        rel = self.question('Q-REL', ['u:0', 'E2'], form='rel')
        R_q = F._answered(base, {'questions': [absorb, rel]})
        self.assertEqual((R_q.absorbed, R_q.unlisted_independent), (frozenset({0}), frozenset({(0, E(2))})))
        untyped = [{**absorb, 'unlisted': None}, {**rel, 'unlisted': None}]  # the subject string alone: nothing
        self.assertEqual(F._answered(base, {'questions': untyped}).absorbed, frozenset())
        self.assertEqual(F._answered(base, {'questions': untyped}).unlisted_independent, frozenset())
        out_of_range = [{**absorb, 'unlisted': 1}]
        self.assertEqual(F._answered(base, {'questions': out_of_range}).absorbed, frozenset())

    def test_a_fact_answer_on_an_unparsed_subject_never_reaches_the_encounter(self) -> None:
        base = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION)).build()
        record = self.question('Q-FACT', ['u:0'], 'date_relation', 'on_date_of_service')
        R_q = F._answered(base, {'questions': [record]})
        self.assertEqual(R_q.encounter, base.encounter)
        self.assertEqual(R_q.events, base.events)


# --- R3D-01's four counterexamples, P-SPLIT, the silent-link rule, b.3's narrowing, the integrity rule -------------------


def frame_source(subject: str, attribute: str, units: tuple, integrity: str = 'passed') -> dict:
    """A stored event record whose frame-inherited fact ``attribute`` cites pass 1's sources on ``units``."""
    return {'id': subject, attribute: {'claim': {'value': 'stated'}, 'sources': [{'units': list(units)}],
                                       'checks': {'integrity': integrity}, 'reasons': []}}


def only(plan: asking.Plan, attribute) -> asking.QuestionSpec:
    found = [spec for spec in plan.specs if spec.attribute is attribute]
    assert len(found) == 1, found
    return found[0]


def held_of(R, code: str) -> list:
    return [held.fact for held in evaluate.decide(code, (), R).held_facts]


def bundling_of(R, code: str) -> set:
    from studio.interpretation.engine import whatif
    return {(witness.held.fact, str(witness.held.subject)) for candidate in whatif.witnesses(R, code)
            for witness in candidate.witnesses if witness.source == 'bundling'}


def pattern(built: question_claims.QuestionRequest, specs: list, quotes: list, control: str) -> settle.QuestionSettlement:
    """Every question's claim answered supports with ``quotes`` (located in its passages), its control ``control``."""
    choices = {}
    for spec in specs:
        choices[(spec.key, 'claim')] = ('supports', quotes)
        choices[(spec.key, 'control')] = (control, [])
    return settled(built, answer_of(built, choices))


class R3D01Tests(SimpleTestCase):
    """REFUTE-NOTES R3D-01 (DESIGN-v2 k.3, M15): with CONTROLS_V3's single alternative as the control, ONE wrong
    judgment established a value. Each counterexample now meets its question's EXACT negation: the finding's answer
    pattern - the claim supported wrongly with a located quote, the true side answered correctly (the negation
    SUPPORTED) - holds; only a second wrong judgment (the negation rejected) could establish, which the teeth check
    shows the question can then do (D306 (d): two judgments in opposite directions plus a located quote)."""

    def test_r3d01_an_outside_record_entry_holds(self) -> None:
        R = colonoscopy(entry=F.SILENT).build()  # truth: the act is told in a copied-in outside report
        spec = only(plan_of(R), A.ENTRY)
        self.assertEqual((spec.value, spec.negated, spec.census), ('documenting_clinician', False, 'F2'))
        built = stub_request([spec], [K1, K2], events=(frame_source('E2', 'entry', ('S1',)),))
        item = next(found for found in built.items if found.spec.key == spec.key)
        # DECISIONS D313: the entry's owner is the documenting clinician (Owner's label), never "or a member of their
        # team" (the PERFORMER's label, which the unrepaired sentence carried); D314 (2): bound to the act's anchor (its
        # card's unit S2), the owner alone negated
        self.assertEqual(item.control_sentence, 'This act is told at S2, in a part of the document not written by the '
                                                'documenting clinician.')
        quotes = ['advanced to the cecum without', 'Colonoscopy report']  # the act's passage, the value passage
        wrong = pattern(built, [spec], quotes, 'supports')
        self.assertEqual(wrong.questions[0]['reasons'], ['question_incoherent'])
        self.assertIs(F._answered(R, {'questions': list(wrong.questions)}), R)
        self.assertIn('event_entry', held_of(R, '45385'))
        teeth = pattern(built, [spec], quotes, 'contradicts')
        self.assertEqual(teeth.questions[0]['result'], 'supported')
        self.assertNotIn('event_entry', held_of(F._answered(R, {'questions': list(teeth.questions)}), '45385'))

    def test_r3d01_hot_forceps_under_removal_is_never_asked(self) -> None:
        R = colonoscopy(kind=Kind.REMOVAL, device=F.SILENT).build()  # truth: hot biopsy forceps (45384, not 45385)
        found = plan_of(R)
        self.assertEqual(found.specs, ())  # F7 (Q-KIND) is not built: no kind is ever refined by an answer here
        self.assertIn('F7 (Q-KIND: not built in the prototype)', found.blocked)
        self.assertEqual(held_of(R, '45385'), ['act_method'])

    def test_r3d01_procedure_caused_bleeding_holds_under_f12(self) -> None:
        doc = colonoscopy()  # truth: the injection treated oozing the snare (E2) caused
        doc.act(3, Kind.INJECTION, purpose=F.SILENT,
                cause=unres(ct.Cause.ACT_OF_THIS_SESSION, ct.Reason.GEOMETRY_SECTION),
                cause_event=unres(E(2), ct.Reason.GEOMETRY_SECTION))
        R = doc.build()
        found = plan_of(R)
        specs = [spec for spec in found.specs if '45381' in found.serves.get(spec.key, ())]
        self.assertEqual(sorted(spec.form for spec in specs),
                         ['fact.cause.not', 'fact.hemostasis.not', 'fact.part_link.any'])
        # four calibration items beside the three questions, so that three accepted negations stay under H4's half
        # and each question meets its own negation (with two, H4 refuses the whole request first: also a hold)
        built = stub_request(specs, [K1, K2, K4, dataclasses.replace(K1, subjects=('E1',), names=('E1',))])
        sentences = {item.spec.form: (item.claim_sentence, item.control_sentence) for item in built.items
                     if item.role == 'question'}
        self.assertEqual(sentences['fact.cause.not'],
                         ('The bleeding this act treated was not caused by another act of this procedure.',
                          'The bleeding this act treated was caused by another act of this procedure.'))
        self.assertEqual(sentences['fact.hemostasis.not'],
                         ('This act was not done for treatment of bleeding present at this encounter.',
                          'This act was done for treatment of bleeding present at this encounter.'))
        quotes = ['removed with a cold snare']  # the act's own passage (A3 on S3 in the stub)
        before = bundling_of(R, '45381')
        self.assertTrue({('act_cause', 'E3'), ('act_part', 'E3')} <= before)
        wrong = pattern(built, specs, quotes, 'supports')
        self.assertEqual({record['reasons'][0] for record in wrong.questions}, {'question_incoherent'})
        self.assertEqual(bundling_of(F._answered(R, {'questions': list(wrong.questions)}), '45381'), before)
        teeth = pattern(built, specs, quotes, 'contradicts')
        self.assertEqual({record['result'] for record in teeth.questions}, {'supported'})
        self.assertEqual(bundling_of(F._answered(R, {'questions': list(teeth.questions)}), '45381'), set())

    def test_r3d01_a_bleeding_control_code_is_never_released_by_the_cause_question(self) -> None:
        """The same reading on a clip for hemostasis (45382): its CAUSE row needs a stated cause of the bleeding, which
        no question template asks - the candidate is blocked whole and nothing is asked through it."""
        doc = colonoscopy()
        doc.act(3, Kind.CLIP, purpose=sup(ct.Purpose.HEMOSTASIS),
                cause=unres(ct.Cause.ACT_OF_THIS_SESSION, ct.Reason.GEOMETRY_SECTION), cause_event=F.SILENT)
        found = plan_of(doc.build())
        self.assertFalse([spec for spec in found.specs if '45382' in found.serves.get(spec.key, ())])
        self.assertIn('F1 (no value template for cause: asked only in its separation form)', found.blocked)

    def test_r3d01_a_next_day_date_holds(self) -> None:
        R = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION)).build()  # truth: done the following day
        spec = only(plan_of(R), A.DATE_RELATION)
        built = stub_request([spec], [K1, K2], events=(frame_source('E2', 'date_relation', ('S4',)),))
        item = next(found for found in built.items if found.spec.key == spec.key)
        self.assertEqual(item.control_sentence, 'This act was not done on the date of service.')
        quotes = ['advanced to the cecum without', 'No biopsies of the rectum']
        wrong = pattern(built, [spec], quotes, 'supports')
        self.assertEqual(wrong.questions[0]['reasons'], ['question_incoherent'])
        self.assertIn('event_time', held_of(F._answered(R, {'questions': list(wrong.questions)}), '45385'))
        teeth = pattern(built, [spec], quotes, 'contradicts')
        self.assertNotIn('event_time', held_of(F._answered(R, {'questions': list(teeth.questions)}), '45385'))


class SplitTests(SimpleTestCase):
    """P-SPLIT (DESIGN-v2 f.4, M20): health is per request - a breach, a lean or a failure in one request never moves
    another request's outcome."""

    def test_p_split_another_requests_answer_never_moves_this_ones_outcome(self) -> None:
        pool = [K1, K2, K4, dataclasses.replace(K1, subjects=('E1',), names=('E1',))]
        first, second = stub_request([REL], pool), stub_request([DATE], pool, seed='second',
                                                                events=(frame_source('E3', 'date_relation', ('S4',)),))
        good = answer_of(first, {(REL.key, 'claim'): ('supports', PROOF), (REL.key, 'control'): ('contradicts', [])})
        alone = settled(first, good)
        self.assertEqual(alone.questions[0]['result'], 'supported')
        k2 = next(item for item in second.items if item.role == 'calibration' and item.spec.kind == 'K2')
        perturbations = [
            answer_of(second, {(k2.spec.key, 'claim'): ('supports', ['removed with a cold snare',
                                                                     'advanced to the cecum without']),
                               (k2.spec.key, 'control'): ('contradicts', [])}),  # a breach in the other request
            answer_of(second, {(item.spec.key, member): ('supports', []) for item in second.items
                               for member in ('claim', 'control')}),  # a lean and accepted controls there
        ]
        for answer in perturbations:
            other = settled(second, answer)
            self.assertTrue(other.health['refused'])
            self.assertEqual(settled(first, good), alone)
        self.assertEqual(settle.settle_questions(second, None, {}, None, 'too_long').questions[0]['result'],
                         'unresolved')
        self.assertEqual(settled(first, good), alone)


class SilentLinkTests(SimpleTestCase):
    """DESIGN-v2 b.8 (M23): a pure-silent link reads as a doubt in the three arms with no identity arm - the tattoo's
    lift by part, the procedural adjunct's part arm, and its cause arm when the part treats bleeding - asked in the
    release direction; a negated link stays no bundle."""

    def test_a_tattoo_with_a_silent_part_of_beside_an_emr_is_held_and_asked(self) -> None:
        doc = colonoscopy(kind=Kind.EMR, device=F.SILENT)
        doc.act(3, Kind.TATTOO, part_of=F.SILENT, purpose=sup(ct.Purpose.MARKING))
        R = doc.build()
        self.assertIn(('act_part', 'E3'), bundling_of(R, '45381'))  # int2: no bundle (F) at the silent exit
        found = plan_of(R)
        self.assertEqual([(spec.form, spec.census) for spec in found.specs], [('fact.part_link.any', 'F11')])
        negated = colonoscopy(kind=Kind.EMR, device=F.SILENT)
        negated.act(3, Kind.TATTOO, part_of=neg(E(2)), purpose=sup(ct.Purpose.MARKING))
        self.assertNotIn(('act_part', 'E3'), bundling_of(negated.build(), '45381'))

    def test_an_adjunct_with_silent_links_is_held_on_both_arms_and_released_only_by_proven_answers(self) -> None:
        doc = colonoscopy()
        doc.act(3, Kind.INJECTION, purpose=F.SILENT, part_of=F.SILENT, cause=F.SILENT)
        R = doc.build()
        self.assertTrue({('act_part', 'E3'), ('act_cause', 'E3')} <= bundling_of(R, '45381'))
        found = plan_of(R)
        specs = [spec for spec in found.specs if '45381' in found.serves.get(spec.key, ())]
        built = stub_request(specs, [K1, K2])
        released = pattern(built, specs, ['removed with a cold snare'], 'contradicts')
        self.assertEqual(bundling_of(F._answered(R, {'questions': list(released.questions)}), '45381'), set())

    def test_the_cause_arm_stays_closed_when_the_part_cannot_treat_bleeding(self) -> None:
        doc = colonoscopy()
        doc.act(3, Kind.INJECTION, purpose=sup(ct.Purpose.MARKING), part_of=neg(E(2)), cause=F.SILENT)
        self.assertNotIn(('act_cause', 'E3'), bundling_of(doc.build(), '45381'))


class NarrowingTests(SimpleTestCase):
    """DESIGN-v2 b.3 (D308 Q-D, M11) - REVERTED by DECISIONS D323 O1 (round r3's build, lane engine): Q-LESION was never
    sent to Fable and D320 ships only the families the probe validated, so D296's fact-pass lesion pair establishes on
    R_base as on int3 (L01-shaped: tests/v2/test_lesion_pair's note, whose established pair int3 reads as apart) and no
    answer is needed for it; tests/v2/test_r3b_engine.LesionPairRevertTests carries the revert's pins."""

    def test_a_fact_pass_pair_sets_its_lesions_apart_as_on_int3(self) -> None:
        from tests.v2 import test_lesion_pair as LP
        _claims, out = LP.settled(LP.NOTE, LP.note_answer(), LP.lesion_oracle())
        fields = LP.row(LP.NOTE, out)
        R = F.factset(LP.view(LP.NOTE, fields))
        self.assertTrue(F.apart_by_lesion(R, E(4), E(2)))
        self.assertIsNone(R.base)


class IntegrityTests(SimpleTestCase):
    """b.0 (M18): a source whose integrity check failed is never a passage - a frame value's proof cannot come from
    it, so the question cannot establish through it."""

    def test_an_integrity_failed_source_is_never_the_value_passage(self) -> None:
        quotes = ['advanced to the cecum without', 'No biopsies of the rectum']
        for integrity, located in (('passed', True), ('failed', False)):
            with self.subTest(integrity=integrity):
                spec = dataclasses.replace(DATE, subjects=('E2',), names=('E2',), value_passage='frame')
                built = stub_request([spec], [K1, K2], events=(frame_source('E2', 'date_relation', ('S4',), integrity),))
                found = pattern(built, [spec], quotes, 'contradicts').questions[0]
                self.assertEqual(found['result'] == 'supported', located, found['reasons'])


class FamilyFoldTests(SimpleTestCase):
    """The fold per built family (DESIGN-v2 f.1): Q-ONLESION, Q-LESION's other two forms, F11 and F12 - each only where
    the base leaves its fact open."""

    def question(self, family: str, subjects: list, **fields) -> dict:
        return {'family': family, 'form': fields.pop('form', ''), 'subjects': subjects,
                'unlisted': asking.unlisted_index(tuple(subjects)), 'attribute': fields.pop('attribute', None),
                'value': fields.pop('value', ''), 'negated': fields.pop('negated', False), 'result': 'supported',
                'reasons': [], 'proof': [{'start': 100, 'end': 130}]}

    def test_q_onlesion_sets_an_act_apart_from_a_lesion_only_when_its_target_is_not_established(self) -> None:
        doc = colonoscopy()
        doc.lesion(2, lesion_places=[sup(Landmark.RECTUM)])
        doc.act(3, Kind.TATTOO, lesion=F.SILENT)
        base = doc.build()
        record = self.question('Q-ONLESION', ['E3', 'L1'], form='onlesion')
        self.assertEqual(F._answered(base, {'questions': [record]}).off_lesion, frozenset({(E(3), L(1))}))
        on_l1 = [self.question('Q-ONLESION', ['E2', 'L1'], form='onlesion')]  # the snare's lesion is established
        self.assertEqual(F._answered(base, {'questions': on_l1}).off_lesion, frozenset())

    def test_q_lesion_not_member_presumes_the_second_single_and_not_member_any_nothing(self) -> None:
        doc = colonoscopy()
        doc.lesion(2, lesion_places=[sup(Landmark.RECTUM)], multiplicity=sup(ct.Multiplicity.GROUP))
        doc.lesions[L(1)][A.MULTIPLICITY] = (sup(ct.Multiplicity.SINGLE),)
        base = doc.build()
        member = self.question('Q-LESION', ['L2', 'L1'], form='lesion.not_member')
        self.assertEqual(F._answered(base, {'questions': [member]}).distinct, frozenset({(L(2), L(1))}))
        reversed_ = self.question('Q-LESION', ['L1', 'L2'], form='lesion.not_member')  # L2 is no single lesion
        self.assertEqual(F._answered(base, {'questions': [reversed_]}).distinct, frozenset())
        anyone = self.question('Q-LESION', ['L1', 'L2'], form='lesion.not_member.any')
        self.assertEqual(F._answered(base, {'questions': [anyone]}).distinct, frozenset({(L(1), L(2))}))

    def test_f11_and_f12_negations_fold_as_negated_links(self) -> None:
        doc = colonoscopy()
        doc.act(3, Kind.INJECTION, purpose=F.SILENT, part_of=F.SILENT, cause=F.SILENT)
        base = doc.build()
        records = [self.question('Q-FACT', ['E3'], form='fact.part_link.any', attribute='part_of', negated=True),
                   self.question('Q-FACT', ['E3'], form='fact.cause.not', attribute='cause',
                                 value='act_of_this_session', negated=True)]
        R_q = F._answered(base, {'questions': records})
        self.assertIs(F.fact(R_q, E(3), A.PART_OF).result, ct.Result.NEGATED)
        # DECISIONS D324 (1) (round r3c's fold lane; was: F.denied(cause, act_of_this_session), an established negation
        # with no options): the cause's negated form rules act_of_this_session out and nothing else
        cause = F.fact(R_q, E(3), A.CAUSE)
        self.assertFalse(F.established(cause))
        self.assertEqual(F.ruled_out(cause), (ct.Cause.ACT_OF_THIS_SESSION,))
        self.assertFalse(F.possibly(cause, ct.Cause.ACT_OF_THIS_SESSION))
        self.assertTrue(F.possibly(cause, ct.Cause.PRE_EXISTING_LESION))
        established = colonoscopy()
        established.act(3, Kind.INJECTION, purpose=F.SILENT, part_of=sup(E(2)), cause=F.SILENT)
        kept = F._answered(established.build(), {'questions': records[:1]})
        self.assertIs(F.fact(kept, E(3), A.PART_OF).result, ct.Result.SUPPORTED)  # never an established fact


# --- the fix round (DECISIONS D310) ----------------------------------------------------------------------------------


def with_approach(doc, approach) -> object:
    doc.sessions[X(1)][A.APPROACH] = (approach,)
    return doc


class StomaRouteTests(SimpleTestCase):
    """D310 (1): the colonoscopy route table (evaluate._row_colon_route; a billing table, D306). A through-stoma code
    (44388-44405, 44408) is READY only with the approach established through_stoma AND an anatomy entry established a
    stoma; a colonoscopy code (45378-45398) is never READY when through_stoma is established and is held when it is
    possible. Red on the unfixed prototype: both ranges' rows were row for row the same, so both codes went READY on
    either note."""

    def test_a_stoma_note_makes_the_stoma_code_ready_and_never_the_transanal_one(self) -> None:
        doc = with_approach(colonoscopy(), sup(ct.Approach.THROUGH_STOMA))
        doc.entry(1, type=sup(ct.AnatomyType.STOMA))
        R = doc.build()
        self.assertEqual(held_of(R, '44394'), [])
        held = evaluate.decide('45385', (), R).held_facts
        self.assertEqual([(h.fact, h.cause, h.attribute, h.kind.value) for h in held],
                         [('procedure', 'coding_rule:stoma_route', A.APPROACH, 'explanation')])

    def test_a_transanal_note_makes_the_transanal_code_ready_and_never_the_stoma_one(self) -> None:
        for approach in (sup(ct.Approach.TRANSANAL), F.SILENT):
            with self.subTest(approach=approach.result.value):
                R = with_approach(colonoscopy(), approach).build()
                self.assertEqual(held_of(R, '45385'), [])
                self.assertTrue(held_of(R, '44394'))
                plan = plan_of(R)
                self.assertFalse([spec for spec in plan.specs if '44394' in plan.serves.get(spec.key, ())])

    def test_a_possible_stoma_holds_the_transanal_code_on_its_approach(self) -> None:
        doc = colonoscopy()
        doc.entry(1, type=F.SILENT)  # an anatomy entry whose type may be a stoma, the approach not stated
        held = evaluate.decide('45385', (), doc.build()).held_facts
        # DECISIONS D325 (2) (round r3's third repair; was ('procedure', A.APPROACH, 'question'), the approach
        # question): an entry whose type is silent may also file the colon surgically absent or be an ileal pouch, so
        # no colon may remain - the route table's own hold (about the session's anatomy) holds it, whatever the approach
        self.assertEqual([(h.fact, h.attribute, h.kind.value) for h in held], [('procedure', A.TYPE, 'question')])
        claimed = with_approach(colonoscopy(), unres(ct.Approach.THROUGH_STOMA, ct.Reason.GEOMETRY_SECTION)).build()
        self.assertTrue(held_of(claimed, '45385'))  # pass 1 read through_stoma: possible without any entry

    def test_through_stoma_with_no_stoma_entry_holds_both_codes(self) -> None:
        R = with_approach(colonoscopy(), sup(ct.Approach.THROUGH_STOMA)).build()
        held = evaluate.decide('44394', (), R).held_facts
        self.assertEqual([(h.cause, h.attribute, h.kind.value) for h in held],
                         [('coding_rule:stoma_route', A.TYPE, 'question')])
        self.assertTrue(held_of(R, '45385'))

    def test_a_twin_on_a_note_naming_no_stoma_is_never_asked_about(self) -> None:
        """The planner: the date question that releases 45385 serves no through-stoma twin, whose route holds are
        ABSENT (no anatomy entry may be a stoma) and so block it - true answers can never release 44394 here."""
        R = colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION)).build()
        found = plan_of(R)
        date = only(found, A.DATE_RELATION)
        self.assertEqual(sorted(found.serves[date.key]), ['45385'])
        self.assertIn('ABSENT (no anatomy entry may be a stoma: the route table)', found.blocked)
        released = pattern(stub_request([date], [K1, K2], events=(frame_source('E2', 'date_relation', ('S4',)),)),
                           [date], ['advanced to the cecum without', 'No biopsies of the rectum'], 'contradicts')
        R_q = F._answered(R, {'questions': list(released.questions)})
        self.assertEqual(held_of(R_q, '45385'), [])
        self.assertTrue(held_of(R_q, '44394'))


class RowSevenTests(SimpleTestCase):
    """D310 (5): G1 - a candidate held only by row 7's possible examination (an event that MAY be the session's
    examination, its session open, failing rows 2-5) is a READING row, asked as the tie's session negation with its
    exact negation, and an established answer takes the event out of the session."""

    def test_g1_the_possible_examinations_tie_is_asked_and_released_by_its_exact_negation(self) -> None:
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.EXAMINATION), status=sup(Status.PERFORMED), session=F.SILENT, date=sup(ON),
                  entry=sup(DC))  # its performer not stated: it fails row 4 and may be X1's examination
        R = doc.build()
        self.assertTrue(any(fact.startswith(('performed_status', 'event_performer')) for fact in held_of(R, '45385')))
        found = plan_of(R)
        g1 = [spec for spec in found.specs if spec.census == 'G1']
        self.assertEqual([(spec.form, spec.subjects, spec.value, spec.negated, spec.names) for spec in g1],
                         [('fact.session.not', ('E3',), 'X1', True, ('E3', 'X1'))])
        self.assertIn('45385', found.serves[g1[0].key])
        built = stub_request(g1, [K1, K2])
        item = next(found for found in built.items if found.spec.key == g1[0].key)
        self.assertEqual((item.claim_sentence, item.control_sentence),
                         ('This act was not done during session X1.', 'This act was done during session X1.'))
        quotes = ['removed with a cold snare', 'advanced to the cecum without']  # E3's own unit (S3) and X1's (S2)
        wrong = pattern(built, g1, quotes, 'supports')
        self.assertEqual(wrong.questions[0]['reasons'], ['question_incoherent'])
        self.assertTrue(held_of(F._answered(R, {'questions': list(wrong.questions)}), '45385'))
        right = pattern(built, g1, quotes, 'contradicts')
        self.assertEqual(right.questions[0]['result'], 'supported')
        self.assertEqual(held_of(F._answered(R, {'questions': list(right.questions)}), '45385'), [])


class HealthRulingTests(SimpleTestCase):
    """D310 (5): H2 - a calibration breach is the false claim SUPPORTED, whatever its control's verdict; H4 as the
    prototype resolved it - each pair's member a release bias would wrongly accept: a question's control or a
    calibration item's CLAIM not rejected, never a calibration item's control (known true)."""

    def setUp(self) -> None:
        self.built = stub_request([REL], [K1, K2, K4, dataclasses.replace(K1, subjects=('E1',), names=('E1',))])
        self.good = {(REL.key, 'claim'): ('supports', PROOF), (REL.key, 'control'): ('contradicts', [])}

    def test_h2_a_calibration_claim_supported_breaches_whatever_its_control_says(self) -> None:
        k2 = next(item for item in self.built.items if item.role == 'calibration' and item.spec.kind == 'K2')
        for control in ('supports', 'unclear', 'contradicts'):
            with self.subTest(control=control):
                found = settled(self.built, answer_of(self.built, {
                    **self.good, (k2.spec.key, 'claim'): ('supports', []), (k2.spec.key, 'control'): (control, [])}))
                self.assertTrue(next(item for item in found.calibration if item['kind'] == 'K2')['breach'])
                self.assertIn('question_health:calibration', found.health['refused'])
                self.assertEqual(found.questions[0]['result'], 'unresolved')

    def test_h4_never_counts_a_calibration_items_known_true_control(self) -> None:
        """Every calibration item answered rightly (its false claim contradicted, its true control supported) beside a
        sound question: H4 refuses nothing - counting the four supported controls would make 4 of 5 pairs."""
        found = settled(self.built, answer_of(self.built, self.good))
        self.assertEqual(found.health['refused'], [])
        self.assertEqual(found.health['measures']['controls_not_rejected'], 0)
        self.assertEqual(found.questions[0]['result'], 'supported')

    def test_h4_counts_a_calibration_items_claim_left_unrejected(self) -> None:
        choices = dict(self.good)
        calibration = [item for item in self.built.items if item.role == 'calibration']
        for item in calibration[:3]:
            choices[(item.spec.key, 'claim')] = ('unclear', [])
        found = settled(self.built, answer_of(self.built, choices))
        self.assertEqual(found.health['measures']['controls_not_rejected'], 3)
        self.assertIn('question_health:controls', found.health['refused'])
        self.assertNotIn('question_health:calibration', found.health['refused'])


def stub_heading_request(specs: list, calibration: list = ()) -> question_claims.QuestionRequest:
    """stub_request's request with card A1 spanning S1 and S2 and section N1 starting at S1 (S1 its heading unit)."""
    units = []
    at = 0
    for number, line in enumerate(TEXT.split('\n')[:4], start=1):
        start = TEXT.index(line, at)
        units.append({'id': f'S{number}', 'start': start, 'end': start + len(line)})
        at = start + len(line)
    cards = [ct.Card('A1', ct.CardType.ACT, ('S1', 'S2'), None, None)]
    cards += [ct.Card(f'A{n}', ct.CardType.ACT, (f'S{n}',), None, None) for n in range(2, 5)]
    cards += [ct.Card('X1', ct.CardType.SESSION, ('S2',), None, None)]
    objects = {f'A{n}': ('event', f'E{n}') for n in range(1, 5)}
    objects['X1'] = ('session', 'X1')
    built = SimpleNamespace(framed='<<<DOCUMENT-0000000000000000 BEGIN>>>\nsynthetic\n<<<DOCUMENT-0000000000000000 END>>>',
                            claim_set=SimpleNamespace(cards=tuple(cards), objects=objects))
    view = {'units': units, 'events': [], 'sessions': [], 'sections': [{'id': 'N1', 'start': {'units': ['S1']}}],
            'unlisted': []}
    plan = asking.RequestPlan(tuple(described(spec) for spec in specs), tuple(described(item) for item in calibration),
                              'seed')
    return question_claims.build_question_request_fable(built, TEXT, (), view, plan, 1, 1)


class PassageHeadingTests(SimpleTestCase):
    """D310 (6), mutant M19: the question request's passage builder (question_claims._Geometry.ranges) cuts a heading's
    words out of an act's own passage, so an act's quote is always act-specific - built from a view, not a hand-cut
    passage."""

    def test_the_heading_unit_is_cut_from_the_acts_passage_the_request_builds(self) -> None:
        rel = dataclasses.replace(REL, subjects=('E4', 'E1'), names=('E4', 'E1'))
        built = stub_heading_request([rel], [K1, K2])
        item = next(found for found in built.items if found.spec.key == rel.key)
        heading_start, heading_end = TEXT.index('Colonoscopy report.'), TEXT.index('\n')
        second = TEXT.index('The scope was advanced')
        second_end = second + len('The scope was advanced to the cecum without difficulty today.')
        self.assertTrue(item.required[1].ranges)
        self.assertTrue(all(high <= heading_start or low >= heading_end for low, high in item.required[1].ranges))
        self.assertTrue(any(low <= second and second_end <= high for low, high in item.required[1].ranges))
        denial = 'No biopsies of the rectum were taken'
        self.assertFalse(proof.locate(TEXT, item.required, item.optional, [denial, 'Colonoscopy report.']).located)
        self.assertTrue(proof.locate(TEXT, item.required, item.optional, [denial, 'advanced to the cecum']).located)


class DenialPairTests(SimpleTestCase):
    """D310 (6), mutant M10: a claimed pair (the statement's covers names the act) whose covers claim the fact pass did
    not support and whose statement DENIES or doubts the act is C7b-denial - whether the act happened, the coder's - and
    is never asked as Q-REL."""

    def test_a_claimed_denial_is_never_asked_as_q_rel(self) -> None:
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.SNARE), status=neg(Status.PERFORMED), session=sup(X(1)),
                  date=unres(ON, ct.Reason.GEOMETRY_SECTION), breadth=sup(ct.Breadth.ALL_OF_KIND),
                  covers=[unres(E(2), ct.Reason.UNAPPRAISED)])
        R = doc.build()
        self.assertTrue(pairing.relation(R, E(3), E(2)).claimed)
        found = plan_of(R)
        self.assertFalse([spec for spec in found.specs if spec.family is asking.Family.Q_REL])
        self.assertIn('C7b-denial', found.blocked)


class QuotesBoundTests(SimpleTestCase):
    """D310 (6): quotes_bound - a quote over 300 characters (or more than proof.QUOTES_MAX quotes: DECISIONS D318 (1))
    voids the claim's proof (appraise_read.read_questions; settle d.2 row 3), even when the long quote lies inside its
    passage and locates."""

    LONG = ('The ascending colon, transverse colon and descending colon were each examined carefully on withdrawal '
            'with high-definition white light and then again with narrow-band imaging, and no polyp, mass, ulcer, '
            'stricture, angioectasia, diverticulum or other mucosal abnormality was seen anywhere along that length '
            'of colon during either pass of the examination today.')

    def built(self) -> tuple:
        text = TEXT + self.LONG + '\n'
        start = text.index(self.LONG)
        units = []
        at = 0
        for number, line in enumerate(text.split('\n')[:5], start=1):
            begin = text.index(line, at)
            units.append({'id': f'S{number}', 'start': begin, 'end': begin + len(line)})
            at = begin + len(line)
        cards = [ct.Card(f'A{n}', ct.CardType.ACT, (f'S{n}',), None, None) for n in range(1, 6)]
        built = SimpleNamespace(framed='<<<DOCUMENT-0000000000000000 BEGIN>>>\nsynthetic\n'
                                       '<<<DOCUMENT-0000000000000000 END>>>',
                                claim_set=SimpleNamespace(cards=tuple(cards),
                                                          objects={f'A{n}': ('event', f'E{n}') for n in range(1, 6)}))
        rel = dataclasses.replace(REL, subjects=('E5', 'E3'), names=('E5', 'E3'))
        calibration = tuple(dataclasses.replace(K1, subjects=(f'E{n}',), names=(f'E{n}',)) for n in (1, 2, 3, 4))
        plan = asking.RequestPlan((rel,), calibration, 'seed')
        view = {'units': units, 'events': [], 'sessions': [], 'sections': [], 'unlisted': []}
        request = question_claims.build_question_request_fable(built, text, (), view, plan, 1, 1)
        return text, request, rel, start

    def settle_with(self, quote: str) -> dict:
        text, request, rel, _ = self.built()
        answer = answer_of(request, {(rel.key, 'claim'): ('supports', [quote, 'removed with a cold snare']),
                                     (rel.key, 'control'): ('contradicts', [])})
        cited = {}
        for item in request.items:
            cited[item.claim] = item.cited
            cited[item.control] = item.cited
        read = appraise_read.read_questions(answer, request.claim_ids, cited, 5)
        locations = {item.claim: proof.locate(text, item.required, item.optional,
                                              read.verdicts[item.claim].quotes if read.verdicts.get(item.claim) else (),
                                              item.alternatives) for item in request.items}
        with mock.patch.object(asking, 'eligible', return_value=True):
            return settle.settle_questions(request, read, locations, None).questions[0]

    def test_a_301_character_quote_inside_its_passage_voids_the_proof(self) -> None:
        self.assertGreater(len(self.LONG), 301)
        long_quote, fits = self.LONG[:301], self.LONG[:300]
        self.assertEqual(self.settle_with(fits)['result'], 'supported')  # the 300-character quote locates and counts
        found = self.settle_with(long_quote)
        self.assertEqual((found['result'], found['reasons']), ('unresolved', ['quotes_bound']))


class CompletenessTests(SimpleTestCase):
    """D310 (6): H1 - missing or repeated verdicts above 1/10 of the request's claims (with at least 10 claims) refuse
    every question of the request, a fully answered sound one included."""

    def answer_without(self, built, drop: int) -> str:
        data = json.loads(answer_of(built, {(REL.key, 'claim'): ('supports', PROOF),
                                            (REL.key, 'control'): ('contradicts', [])}))
        controls = [item.control for item in built.items if item.role == 'calibration']
        data['verdicts'] = [verdict for verdict in data['verdicts'] if verdict['claim'] not in controls[:drop]]
        return json.dumps(data)

    def test_two_missing_verdicts_of_ten_claims_refuse_the_request(self) -> None:
        built = stub_request([REL], [K1, K2, K4, dataclasses.replace(K1, subjects=('E1',), names=('E1',))])
        self.assertEqual(len(built.claim_ids), 10)
        one = settled(built, self.answer_without(built, 1))  # 1 of 10: not above a tenth
        self.assertEqual((one.health['refused'], one.questions[0]['result']), ([], 'supported'))
        two = settled(built, self.answer_without(built, 2))
        self.assertEqual(two.health['refused'], ['question_health:missing'])
        self.assertEqual(two.questions[0]['reasons'], ['question_health:missing'])


class CalibrationSourceTests(SimpleTestCase):
    """D310 (4): b.9's second K3 source (a statement SAME on every row against an act, from established facts), one
    same-family holding item per family a request asks where a source exists, a K1 beside a covers K3 - and a draw that
    would leave a covers K3 alone drops it and REFILLS (mutant K3-without-K1)."""

    def test_a_pair_same_on_every_row_from_established_facts_gives_a_k3_item(self) -> None:
        doc = colonoscopy()
        doc.event(3, kind=sup(Kind.SNARE), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                  performer=sup(TEAM), entry=sup(DC), breadth=sup(ct.Breadth.SINGLE_TARGET), lesion=sup(L(1)),
                  places=[sup(Landmark.SIGMOID_COLON)])
        R = doc.build()
        self.assertEqual(asking.same_pairs(R), ((E(3), E(2)),))
        k3 = [item for item in asking.calibration_pool(R) if item.kind == 'K3']
        self.assertEqual([(item.source, item.subjects, item.negative) for item in k3], [('same', ('E3', 'E2'), True)])
        loose = colonoscopy()  # the statement's session not established: no row may be SAME by a default
        loose.event(3, kind=sup(Kind.SNARE), status=neg(Status.PERFORMED), session=F.SILENT, date=sup(ON),
                    performer=sup(TEAM), entry=sup(DC), breadth=sup(ct.Breadth.SINGLE_TARGET), lesion=sup(L(1)),
                    places=[sup(Landmark.SIGMOID_COLON)])
        self.assertEqual(asking.same_pairs(loose.build()), ())

    def test_a_pair_that_pairs_only_through_one_act_kind_gives_no_k3_item(self) -> None:
        """A tattoo denial against a lift INJECTION at the same place is SAME on every row of 4.5 (a tattoo and an
        injection share one act), but the two kinds differ: whether it concerns the lift is not established, so it
        is no calibration item (a right "does not concern" would read as a breach)."""
        doc = colonoscopy(snare=False)
        doc.lesion(1, lesion_places=[sup(Landmark.TRANSVERSE_COLON)])
        doc.act(2, Kind.INJECTION, places=[sup(Landmark.TRANSVERSE_COLON)], lesion=sup(L(1)))
        doc.event(3, kind=sup(Kind.TATTOO), status=neg(Status.PERFORMED), session=sup(X(1)), date=sup(ON),
                  performer=sup(TEAM), entry=sup(DC), breadth=sup(ct.Breadth.SINGLE_TARGET), lesion=sup(L(1)),
                  places=[sup(Landmark.TRANSVERSE_COLON)])
        R = doc.build()
        relation = pairing.relation(R, E(3), E(2))
        self.assertTrue(all(found is pairing.RowResult.SAME for _, found in relation.rows), relation.rows)
        self.assertEqual(asking.same_pairs(R), ())
        self.assertFalse([item for item in asking.calibration_pool(R) if item.kind == 'K3'])

    def covers_k3(self, n: int) -> asking.CalibrationSpec:
        return asking.CalibrationSpec('K3', asking.Family.Q_REL, 'rel', (f'E{n}', 'E2'), None, '', False,
                                      (f'E{n}', 'E2'), source='covers')

    def test_a_covers_k3_is_never_drawn_without_a_k1_and_the_draw_refills(self) -> None:
        pool = [self.covers_k3(n) for n in range(10, 16)] + [dataclasses.replace(K2, subjects=(f'E{n}',),
                                                                                  names=(f'E{n}', 'X1'))
                                                             for n in range(20, 26)]
        drawn = asking.draw(pool, specs_of(3), 'seed')
        self.assertEqual(len(drawn), 1)  # DECISIONS D319: one item
        self.assertFalse([item for item in drawn if item.kind == 'K3'])

    def test_a_covers_k3_gives_way_to_its_k1_with_one_item(self) -> None:
        # DECISIONS D319: one item a request leaves no room beside a covers K3, so its K1 is drawn in its place
        pool = [self.covers_k3(n) for n in range(10, 13)] + [dataclasses.replace(K2, subjects=(f'E{n}',),
                                                                                  names=(f'E{n}', 'X1'))
                                                             for n in range(20, 23)] + [K1]
        drawn = asking.draw(pool, specs_of(3), 'seed')
        self.assertEqual(drawn, (K1,))

    def test_the_one_item_is_the_first_asked_familys_where_a_source_exists(self) -> None:
        # DECISIONS D319: one item, so b.9's same-family item is the FIRST family the request asks that has a source
        same = asking.CalibrationSpec('K3', asking.Family.Q_REL, 'rel', ('E30', 'E2'), None, '', False, ('E30', 'E2'),
                                      source='same')
        pool = POOL + [same, K4]
        onlesion = asking.QuestionSpec(asking.Family.Q_ONLESION, 'onlesion', ('E5', 'L1'), A.TARGET_LESION, 'L1', True,
                                       ('E5', 'L1'), census='R3/R4')
        for seed in ('a', 'b', 'c', 'd'):
            with self.subTest(seed=seed):
                self.assertEqual(asking.draw(pool, specs_of(2) + [DATE, onlesion], seed), (same,))
                self.assertEqual(asking.draw(pool, [onlesion, DATE], seed), (K4,))


# --- DECISIONS D313: the question wording, every form pinned to its source; QUESTION_BOUND from the measured t_q ---------

QS = asking.Family


class _WordingCards:
    """A stand-in for the request's cards (question_claims._Cards): each stored object's card id, and the units a person
    is named at - so a form's sentences are rendered by the request's own _sentences."""
    CARDS = {'E1': 'A1', 'E2': 'A2', 'E3': 'A3', 'E4': 'A4', 'X1': 'X1', 'Y1': 'Y1', 'L1': 'L1', 'L2': 'L2',
             'u:0': 'U1', 'P1': 'P1'}

    def card(self, stored: str) -> str:
        return self.CARDS[stored]

    def units(self, stored: str) -> tuple:
        return ('S7', 'S8') if stored == 'P1' else ('S1',)


def wording_spec(form: str, family: asking.Family = QS.Q_FACT, subjects: tuple = ('E3',), attribute=None,
                 value: str = '', negated: bool = False, acts: tuple = ()) -> asking.QuestionSpec:
    return asking.QuestionSpec(family, form, subjects, attribute, value, negated, subjects, acts=acts)


def rendered(spec: asking.QuestionSpec) -> tuple:
    """(the claim sentence, the control sentence) the request writes for ``spec`` (question_claims._sentences)."""
    _, claim, control = question_claims._sentences(described(spec), _WordingCards())
    return claim, control


def contract(template_id, **fields) -> str:
    """The fact pass's CURRENT sentence of ``template_id`` under gemini-appraisal@2 (claims.TEMPLATES_V3 /
    STATEMENT_TEMPLATES_V3, the @2 override where one exists), filled."""
    return claims.template(template_id, interpretation.APPRAISAL_VERSION_V3).format(**fields)


T = claims.TemplateId
LABEL = claims.label
# One row per QUESTION_TEMPLATES form (DECISIONS D313): the spec the planner (or the calibration pool) asks; the claim and
# control sentences as REVIEWED against the contract's definition of the fact (literal, so a source changed under a
# derived sentence fails here); the positive sentence's contract source (template id and its fill, or None for a
# family's own sentence); and the exact negation - the contract's negated template, or the one declared edit (old, new)
# that turns the positive sentence into it.
WORDING = {
    'rel': (wording_spec('rel', QS.Q_REL, ('E4', 'E3')),
            ('This statement does not concern act A3.', 'This statement concerns act A3.'),
            None, ('concerns', 'does not concern')),
    'onlesion': (wording_spec('onlesion', QS.Q_ONLESION, ('E3', 'L1'), A.TARGET_LESION, 'L1', True),
                 ('This act was not done to lesion L1.', 'This act was done to lesion L1.'),
                 (T.ACT_TARGET_LESION, {'lesion': 'L1'}), ('This act was done', 'This act was not done')),
    'onlesion.group': (wording_spec('onlesion.group', QS.Q_ONLESION, ('E3', 'L1'), A.TARGET_LESION, 'L1', True),
                       ('This act was not done to any of the lesions of L1.',
                        'This act was done to one of the lesions of L1.'),
                       None, ('was done to one of', 'was not done to any of')),
    'lesion.distinct_from': (wording_spec('lesion.distinct_from', QS.Q_LESION, ('L1', 'L2'), A.DISTINCT_FROM, 'L2'),
                             ('Lesions L1 and L2 are different lesions.', 'Lesions L1 and L2 are the same lesion.'),
                             (T.LESION_DISTINCT, {'lesion': 'L1', 'other': 'L2'}),
                             (T.LESION_SAME, {'lesion': 'L1', 'other': 'L2'})),
    'lesion.not_member': (wording_spec('lesion.not_member', QS.Q_LESION, ('L1', 'L2'), A.DISTINCT_FROM, 'L2'),
                          ('Lesion L2 is not one of the lesions of L1.', 'Lesion L2 is one of the lesions of L1.'),
                          (T.LESION_NOT_MEMBER, {'lesion': 'L1', 'other': 'L2'}),
                          (T.LESION_MEMBER, {'lesion': 'L1', 'other': 'L2'})),
    'lesion.not_member.any': (wording_spec('lesion.not_member.any', QS.Q_LESION, ('L1', 'L2'), A.DISTINCT_FROM, 'L2'),
                              ('No lesion of L2 is one of the lesions of L1.',
                               'A lesion of L2 is one of the lesions of L1.'),
                              (T.LESION_NONE_MEMBER, {'lesion': 'L1', 'other': 'L2'}),
                              (T.LESION_SOME_MEMBER, {'lesion': 'L1', 'other': 'L2'})),
    'absorb': (wording_spec('absorb', QS.Q_ABSORB, ('u:0',), acts=('E1', 'E2')),
               ('This statement tells or doubts no act other than acts A1 and A2.',
                'This statement tells or doubts an act that is none of acts A1 and A2.'),
               None, ('tells or doubts no act other than', 'tells or doubts an act that is none of')),
    'fact.date_relation': (wording_spec('fact.date_relation', attribute=A.DATE_RELATION, value='on_date_of_service'),
                           ('This act was done on the date of service.', 'This act was not done on the date of service.'),
                           (T.ACT_DATE_RELATION, {'date_relation': 'was done on the date of service'}),
                           ('This act was done', 'This act was not done')),
    # DECISIONS D314 (2): bound to the act's anchor - the units its card names (S1 here) - and negating the owner alone
    'fact.entry': (wording_spec('fact.entry', attribute=A.ENTRY, value='documenting_clinician'),
                   ('This act is told at S1, in a part of the document written by the documenting clinician.',
                    'This act is told at S1, in a part of the document not written by the documenting clinician.'),
                   None, ('in a part of the document written by', 'in a part of the document not written by')),
    'fact.performer': (wording_spec('fact.performer', attribute=A.PERFORMER, value='documenting_team'),
                       ('This act was done by the documenting clinician or a member of their team.',
                        'This act was not done by the documenting clinician or a member of their team.'),
                       (T.ACT_PERFORMER, {'performer': 'the documenting clinician or a member of their team'}),
                       ('This act was done', 'This act was not done')),
    'fact.performer_person': (wording_spec('fact.performer_person', attribute=A.PERFORMER_PERSON, value='P1'),
                              ('This act was done by the person named at S7 and S8.',
                               'This act was not done by the person named at S7 and S8.'),
                              (T.ACT_PERFORMER_PERSON, {'person': 'S7 and S8'}),
                              ('This act was done', 'This act was not done')),
    'fact.session': (wording_spec('fact.session', attribute=A.SESSION, value='X1'),
                     ('This act was done during session X1.', 'This act was not done during session X1.'),
                     (T.ACT_SESSION, {'session': 'X1'}), ('This act was done', 'This act was not done')),
    'fact.session.not': (wording_spec('fact.session.not', attribute=A.SESSION, value='X1', negated=True),
                         ('This act was not done during session X1.', 'This act was done during session X1.'),
                         (T.ACT_SESSION, {'session': 'X1'}), ('This act was done', 'This act was not done')),
    'fact.target.lesion': (wording_spec('fact.target.lesion', attribute=A.TARGET_LESION, value='L1'),
                           ('This act was done to lesion L1.', 'This act was not done to lesion L1.'),
                           (T.ACT_TARGET_LESION, {'lesion': 'L1'}), ('This act was done', 'This act was not done')),
    'fact.target.places': (wording_spec('fact.target.places', attribute=A.TARGET_PLACES, value='sigmoid_colon'),
                           ('This act was done in the sigmoid colon.', 'This act was not done in the sigmoid colon.'),
                           (T.ACT_TARGET_PLACE, {'place': 'sigmoid colon'}),
                           ('This act was done', 'This act was not done')),
    'fact.technique.device': (wording_spec('fact.technique.device', attribute=A.TECHNIQUE_DEVICE, value='cold_snare'),
                              ('This act used a cold snare.', 'This act did not use a cold snare.'),
                              (T.ACT_DEVICE, {'device': 'a cold snare'}), ('This act used', 'This act did not use')),
    'fact.purpose': (wording_spec('fact.purpose', attribute=A.PURPOSE, value='diagnostic'),
                     ('This act was done for diagnosis.', 'This act was not done for diagnosis.'),
                     (T.ACT_PURPOSE, {'purpose': 'diagnosis'}), ('This act was done', 'This act was not done')),
    'fact.target.duct': (wording_spec('fact.target.duct', attribute=A.TARGET_DUCT, value='biliary'),
                         ('This act was done in the bile duct.', 'This act was not done in the bile duct.'),
                         (T.ACT_TARGET_DUCT, {'duct': 'bile'}), ('This act was done', 'This act was not done')),
    'fact.part_link.any': (wording_spec('fact.part_link.any', attribute=A.PART_OF, value='', negated=True),
                           ('This act was not a step of, a lift done to enable, access gained to enable, an adjunct '
                            'done with or one part of another act.',
                            'This act was a step of, a lift done to enable, access gained to enable, an adjunct done '
                            'with or one part of another act.'),
                           None, ('This act was ', 'This act was not ')),
    'fact.cause.not': (wording_spec('fact.cause.not', attribute=A.CAUSE, value='act_of_this_session', negated=True),
                       ('The bleeding this act treated was not caused by another act of this procedure.',
                        'The bleeding this act treated was caused by another act of this procedure.'),
                       None, ('was caused', 'was not caused')),
    'fact.lift.not': (wording_spec('fact.lift.not', attribute=A.PURPOSE, value='lift_for_resection', negated=True),
                      ('This act was not done for lifting tissue for a resection.',
                       'This act was done for lifting tissue for a resection.'),
                      (T.ACT_PURPOSE, {'purpose': 'lifting tissue for a resection'}),
                      ('This act was done', 'This act was not done')),
    'fact.hemostasis.not': (wording_spec('fact.hemostasis.not', attribute=A.PURPOSE, value='hemostasis', negated=True),
                            ('This act was not done for treatment of bleeding present at this encounter.',
                             'This act was done for treatment of bleeding present at this encounter.'),
                            (T.ACT_PURPOSE, {'purpose': 'treatment of bleeding present at this encounter'}),
                            ('This act was done', 'This act was not done')),
    'fact.reached': (wording_spec('fact.reached', subjects=('X1',), attribute=A.REACHED, value='cecum'),
                     ('In session X1 the endoscope itself reached the cecum.',
                      'In session X1 the endoscope did not reach the cecum.'),
                     (T.SESSION_REACHED, {'session': 'X1', 'point': 'cecum'}),
                     (T.SESSION_REACHED_NEGATED, {'session': 'X1', 'point': 'cecum'})),
    'fact.reached_anatomy': (wording_spec('fact.reached_anatomy', subjects=('X1',), attribute=A.REACHED_ANATOMY,
                                          value='Y1'),
                             ('In session X1 the endoscope itself reached anatomy Y1.',
                              'In session X1 the endoscope did not reach anatomy Y1.'),
                             (T.SESSION_REACHED_ANATOMY, {'session': 'X1', 'anatomy': 'Y1'}),
                             ('the endoscope itself reached', 'the endoscope did not reach')),
    'fact.stations': (wording_spec('fact.stations', subjects=('X1',), attribute=A.STATIONS, value='ileum'),
                      ('In session X1 the ileum was examined.', 'In session X1 the ileum was not examined.'),
                      (T.SESSION_STATION, {'session': 'X1', 'station': 'ileum'}),
                      (T.SESSION_STATION_NEGATED, {'session': 'X1', 'station': 'ileum'})),
    'fact.visit.basis': (wording_spec('fact.visit.basis', subjects=('E1',), attribute=A.VISIT_BASIS,
                                      value='medical_decision_making'),
                         ("The visit's level is based on medical decision making.",
                          "The visit's level is not based on medical decision making."),
                         (T.VISIT_BASIS, {'basis': 'medical decision making'}),
                         ("The visit's level is based", "The visit's level is not based")),
    # DECISIONS D318 (3): Q-REL's narrowest relation, by the statement's class and status (question_claims.relation_form:
    # an established denial, an open denial, an established plan); tests/v2/test_r3_claims.py derives each per census row
    'rel.deny': (wording_spec('rel.deny', QS.Q_REL, ('E4', 'E3')),
                 ('This statement does not deny act A3.', 'This statement denies act A3.'),
                 None, ('denies', 'does not deny')),
    'rel.deny_or_doubt': (wording_spec('rel.deny_or_doubt', QS.Q_REL, ('E4', 'E3')),
                          ('This statement does not deny act A3 or cast doubt on it.',
                           'This statement denies act A3 or casts doubt on it.'),
                          None, ('denies act A3 or casts', 'does not deny act A3 or cast')),
    'rel.plan': (wording_spec('rel.plan', QS.Q_REL, ('E4', 'E3')),
                 ('This statement does not plan or recommend act A3.', 'This statement plans or recommends act A3.'),
                 None, ('plans or recommends', 'does not plan or recommend')),
    # DECISIONS D312: the stoma route's own questions (the colonoscopy route table, D310 (1))
    'fact.approach': (wording_spec('fact.approach', subjects=('X1',), attribute=A.APPROACH, value='through_stoma'),
                      ('In session X1 the scope was passed through a stoma.',
                       'In session X1 the scope was not passed through a stoma.'),
                      (T.SESSION_APPROACH, {'session': 'X1', 'approach': 'through a stoma'}),
                      ('the scope was passed', 'the scope was not passed')),
    'fact.type': (wording_spec('fact.type', subjects=('Y1',), attribute=A.TYPE, value='stoma'),
                  ('The patient has a surgical opening (a stoma) (described at S1).',
                   'The patient does not have a surgical opening (a stoma) (described at S1).'),
                  (T.ANATOMY_TYPE, {'type': 'a surgical opening (a stoma)', 'units': 'S1'}),
                  ('The patient has', 'The patient does not have')),
}
# each form's binding to the contract (QUESTION_SOURCES): (the positive's template, the negative's template, whether it
# is the family's own sentence) - the forms whose fact the fact pass claims are bound to its templates
SOURCE_BINDING = {
    'rel': (None, None, True), 'onlesion': (T.ACT_TARGET_LESION, None, False), 'onlesion.group': (None, None, True),
    'lesion.distinct_from': (T.LESION_DISTINCT, T.LESION_SAME, False),
    'lesion.not_member': (T.LESION_NOT_MEMBER, T.LESION_MEMBER, False),
    'lesion.not_member.any': (T.LESION_NONE_MEMBER, T.LESION_SOME_MEMBER, False), 'absorb': (None, None, True),
    'fact.date_relation': (T.ACT_DATE_RELATION, None, False), 'fact.entry': (T.ACT_ENTRY, None, False),
    'fact.performer': (T.ACT_PERFORMER, None, False), 'fact.performer_person': (T.ACT_PERFORMER_PERSON, None, False),
    'fact.session': (T.ACT_SESSION, None, False), 'fact.session.not': (T.ACT_SESSION, None, False),
    'fact.target.lesion': (T.ACT_TARGET_LESION, None, False), 'fact.target.places': (T.ACT_TARGET_PLACE, None, False),
    'fact.technique.device': (T.ACT_DEVICE, None, False), 'fact.purpose': (T.ACT_PURPOSE, None, False),
    'fact.target.duct': (T.ACT_TARGET_DUCT, None, False), 'fact.part_link.any': (T.ACT_PART_OF, None, False),
    'fact.cause.not': (None, T.ACT_CAUSE_NEGATED, False), 'fact.lift.not': (T.ACT_PURPOSE, None, False),
    'fact.hemostasis.not': (T.ACT_PURPOSE, None, False),
    'fact.reached': (T.SESSION_REACHED, T.SESSION_REACHED_NEGATED, False),
    'fact.reached_anatomy': (T.SESSION_REACHED_ANATOMY, None, False),
    'fact.stations': (T.SESSION_STATION, T.SESSION_STATION_NEGATED, False), 'fact.visit.basis': (T.VISIT_BASIS, None, False),
    'rel.deny': (None, None, True), 'rel.deny_or_doubt': (None, None, True), 'rel.plan': (None, None, True),
    'fact.approach': (T.SESSION_APPROACH, None, False), 'fact.type': (T.ANATOMY_TYPE, None, False),
}
# the declared negation edits a question pair may differ by (each inserts or removes the one "not" - or, for a reach,
# the contract's own reach negation; for a family's own pair, the pair's own contrary words), never a hedge ("The
# document states ...", R3D-01) and never a second difference
NEGATION_EDITS = frozenset({
    ('This act was done', 'This act was not done'),
    ('in a part of the document written by', 'in a part of the document not written by'),  # D314 (2): the entry's owner
    ('This act used', 'This act did not use'), ("The visit's level is based", "The visit's level is not based"),
    ('This act was ', 'This act was not '), ('was caused', 'was not caused'),
    ('the endoscope itself reached', 'the endoscope did not reach'), ('concerns', 'does not concern'),
    ('was done to one of', 'was not done to any of'),
    ('tells or doubts no act other than', 'tells or doubts an act that is none of'),
    # DECISIONS D318 (3): the narrow Q-REL pairs' own contrary words; D312: the route's one "not"
    ('denies', 'does not deny'), ('denies act A3 or casts', 'does not deny act A3 or cast'),
    ('plans or recommends', 'does not plan or recommend'), ('the scope was passed', 'the scope was not passed'),
    ('The patient has', 'The patient does not have')})


class QuestionWordingTests(SimpleTestCase):
    """DECISIONS D313: every question sentence states its fact exactly as the contract defines it - one pin per form
    (test_form_<form>): the claim and control the request writes are the reviewed sentences; a form whose fact the fact
    pass claims takes the fact pass's CURRENT sentence under gemini-appraisal@2 (the @2 override where one exists); the
    control is the claim's exact negation (the contract's negated template, or one declared edit that inserts the one
    "not"). RED on the unrepaired prototype for the reach (its 'itself' dropped), the reached anatomy (gemini-appraisal@1's
    "furthest point" sentence: step 1 short's hollow proof), the entry, the universal part link and the lift purpose."""

    def check(self, form: str) -> None:
        spec, (claim, control), source, negation = WORDING[form]
        found = rendered(spec)
        self.assertEqual(found, (claim, control), form)  # the reviewed words, literally
        positive, negative = (control, claim) if (spec.negated or spec.family is QS.Q_REL) else (claim, control)
        if source is not None:  # its sentence equals its source: the fact pass's current @2 sentence
            self.assertEqual(positive, contract(source[0], **source[1]), form)
        if isinstance(negation[0], claims.TemplateId):  # the contract's own negated or control template
            self.assertEqual(negative, contract(negation[0], **negation[1]), form)
        else:  # one declared negation edit, applied once, and nothing else differs
            old, new = negation
            self.assertIn(negation, NEGATION_EDITS, form)
            self.assertEqual(positive.count(old), 1, form)
            self.assertEqual(positive.replace(old, new), negative, form)
        self.assertNotIn('The document states', claim + control, form)  # never the hedge (R3D-01)
        # derived from the ONE source, never a copy: the form is bound to its contract template (a copy of the same
        # words would not follow a change of the fact pass's sentence), or - a family's own sentence - to none
        bound = question_claims.QUESTION_SOURCES[form]
        self.assertEqual((bound.positive, bound.negative, bound.own is not None), SOURCE_BINDING[form], form)

    def test_every_form_has_its_pin(self) -> None:
        self.assertEqual(set(WORDING), set(question_claims.QUESTION_TEMPLATES))

    def test_the_questions_are_read_under_gemini_appraisal_2(self) -> None:  # D307 Q1, D313
        self.assertEqual(question_claims.QUESTION_APPRAISAL_VERSION, interpretation.APPRAISAL_VERSION_V3)
        self.assertNotEqual(contract(T.SESSION_REACHED_ANATOMY, session='X1', anatomy='Y1'),
                            claims.template(T.SESSION_REACHED_ANATOMY, interpretation.APPRAISAL_VERSION).format(
                                session='X1', anatomy='Y1'))  # @1's "furthest point" sentence is not the one asked

    def test_the_reach_negation_is_the_contracts_own(self) -> None:
        self.assertEqual(question_claims.REACH_NEGATION, ('the endoscope itself reached', 'the endoscope did not reach'))
        self.assertEqual(contract(T.SESSION_REACHED, session='X1', point='cecum').replace(*question_claims.REACH_NEGATION),
                         contract(T.SESSION_REACHED_NEGATED, session='X1', point='cecum'))

    def test_a_derivation_whose_source_changed_fails_loudly(self) -> None:
        with self.assertRaises(RuntimeError):
            question_claims._edited('In session {session} the scope got to anatomy {anatomy}.',
                                    question_claims.REACH_NEGATION)

    def test_a_value_is_rendered_from_the_spec_never_fixed_text(self) -> None:
        # before the repair the date relation, entry and performer sentences were fixed text whatever value was asked
        earlier = dataclasses.replace(WORDING['fact.date_relation'][0], value='earlier_date')
        self.assertEqual(rendered(earlier), ('This act was done on a date before the date of service.',
                                             'This act was not done on a date before the date of service.'))
        other = dataclasses.replace(WORDING['fact.performer'][0], value='other_clinician')
        self.assertEqual(rendered(other)[0], 'This act was done by a clinician other than the documenting clinician '
                                             'and their team.')
        nursing = dataclasses.replace(WORDING['fact.entry'][0], value='nursing')
        self.assertEqual(rendered(nursing)[0], 'This act is told at S1, in a part of the document written by nursing '
                                               'staff.')
        with self.assertRaises(question_claims.Unbuildable):  # no exact one-edit negation: never asked, never wrong
            rendered(dataclasses.replace(earlier, value='later_date'))
        with self.assertRaises(question_claims.Unbuildable):  # the lift negation asks one value only
            rendered(dataclasses.replace(WORDING['fact.lift.not'][0], value='hemostasis'))

    def test_the_cause_negation_is_the_contracts_own_sentence(self) -> None:
        claim, control = rendered(WORDING['fact.cause.not'][0])
        self.assertEqual(claim, contract(T.ACT_CAUSE_NEGATED))  # the fact pass's sentence of the cause negated

    def test_the_part_link_names_every_relation_of_a_part_to_its_whole(self) -> None:
        claim = rendered(WORDING['fact.part_link.any'][0])[0]
        for member in ct.PartRelation:  # the fold negates part_of for every whole and every relation
            self.assertIn(LABEL(member), claim)

    def test_the_entry_names_the_owner_never_the_team(self) -> None:
        claim, control = rendered(WORDING['fact.entry'][0])
        self.assertIn(LABEL(ct.Owner.DOCUMENTING_CLINICIAN), claim)
        self.assertNotIn('member of their team', claim + control)  # the performer's label, not the entry's owner
        # DECISIONS D314 (2): no section start (D313's edit stands) and bound to the act's anchor units
        self.assertEqual(claim, claims.template(T.ACT_ENTRY, interpretation.APPRAISAL_VERSION_V3).replace(
            'in the part of the document that begins at {start}, written by {owner}',
            'at {units}, in a part of the document written by {owner}').format(
                units='S1', owner=LABEL(ct.Owner.DOCUMENTING_CLINICIAN)))

    def test_step_1_shorts_reach_questions_now_ask_the_reach_as_the_fact_pass_does(self) -> None:
        # r3-probe-1's two questions (A-v3.F3all, census F8): q1.1.1 reached_anatomy Y1, q1.1.2 reached
        # neo_terminal_ileum - written through the request builder with a session and an anatomy entry carded
        anatomy = asking.QuestionSpec(QS.Q_FACT, 'fact.reached_anatomy', ('X1',), A.REACHED_ANATOMY, 'Y1', False,
                                      ('X1',), value_passage='source', census='F8')
        reach = asking.QuestionSpec(QS.Q_FACT, 'fact.reached', ('X1',), A.REACHED, 'neo_terminal_ileum', False,
                                    ('X1',), value_passage='source', census='F8')
        built = stub_request([anatomy, reach], [K1, K2], extra_cards=(('Y1', ct.CardType.ANATOMY, ('S2',)),))
        sentences = {item.spec.form: (item.claim_sentence, item.control_sentence) for item in built.items}
        self.assertEqual(sentences['fact.reached_anatomy'], ('In session X1 the endoscope itself reached anatomy Y1.',
                                                             'In session X1 the endoscope did not reach anatomy Y1.'))
        self.assertEqual(sentences['fact.reached'],
                         ('In session X1 the endoscope itself reached the ileum next to an ileocolic joining '
                          '(neo-terminal ileum).',
                          'In session X1 the endoscope did not reach the ileum next to an ileocolic joining '
                          '(neo-terminal ileum).'))
        self.assertFalse([line for line in built.lines if 'furthest point' in line])


def _wording_pin(form: str):
    def test(self: QuestionWordingTests) -> None:
        self.check(form)
    test.__doc__ = f'DECISIONS D313: the {form} form states its fact exactly, and its control is its exact negation.'
    return test


for _form in WORDING:
    setattr(QuestionWordingTests, 'test_form_' + _form.replace('.', '_'), _wording_pin(_form))
del _form


class QuestionBoundTests(SimpleTestCase):
    """DESIGN-v2 e.2 (DECISIONS D313, D318 (2) and its first addendum): QUESTION_BOUND from the measured t_q - the
    largest per-request output over claims of the four question requests sent at effort max: r3-probe-1's 55,219 over
    12 and r3-probe-2's 105,999 over 20, 71,896 over 20 and 94,976 over 16 (5,936 a claim) - rounded by a PAIR, so a
    request's expected output stays at or under 85% of 128,000; it sizes requests and never drops a question (P-NODROP,
    D306 (d))."""

    def test_the_bound_is_derived_from_the_measured_t_q(self) -> None:
        derived = asking.question_bound_derivation()
        self.assertEqual(asking.QUESTION_BOUND_MEASURED, ((55_219, 12), (105_999, 20), (71_896, 20), (94_976, 16)))
        self.assertEqual((derived.tokens_per_claim, derived.capacity, derived.bound), (5_936, 18, 18))
        self.assertEqual((asking.QUESTION_BOUND, asking.QUESTION_BOUND_ROUNDING), (18, 2))
        self.assertEqual(asking.question_bound_derivation(((94_976, 16),)).bound, 18)  # 8ac5eaf6's alone: the same
        self.assertEqual(asking.QUESTION_BOUND_PROVISIONAL, 100)  # the prototype's value before any measure, the record

    def test_a_request_at_the_bound_expects_at_most_85_percent_of_the_output(self) -> None:
        derived = asking.question_bound_derivation()
        self.assertLessEqual(asking.QUESTION_BOUND * derived.tokens_per_claim, 128_000 * 85 // 100)
        self.assertGreater((asking.QUESTION_BOUND + asking.QUESTION_BOUND_ROUNDING) * derived.tokens_per_claim,
                           128_000 * 85 // 100)

    def test_the_probes_long_documents_partition_and_drop_nothing(self) -> None:
        for count, sizes in ((2, [2]), (16, [8, 8]), (18, [8, 8, 2])):  # D318 (2), D319: 8 questions and one item
            with self.subTest(questions=count):
                specs = specs_of(count)
                requests = asking.partition(specs, POOL, 1)
                self.assertEqual([len(request.questions) for request in requests], sizes)
                self.assertTrue(all(request.claims <= asking.QUESTION_BOUND for request in requests))
                self.assertEqual(sorted(spec.key for request in requests for spec in request.questions),
                                 sorted(spec.key for spec in specs))

    def test_a_bound_that_cannot_carry_one_question_is_the_owners(self) -> None:
        with self.assertRaises(RuntimeError):
            asking.question_bound_derivation(((128_000, 1),))

    def test_the_bound_is_pinned_with_its_figures(self) -> None:
        document = asking.question_bound_document()
        self.assertEqual((document['question_bound'], document['tokens_per_claim'], document['measured']),
                         (18, 5_936, [[55_219, 12], [105_999, 20], [71_896, 20], [94_976, 16]]))
        self.assertIn('QUESTION_BOUND_SHA256_V3', question_claims.pins())


# --- DECISIONS D314: THE CLASS (every form's declared sets; the act-form calibration items' predicate) and the entry ----
# bound to its anchor. Step 1 long's request 2 asked as KNOWN FALSE "This act was not done on the date of service." of a
# DENIAL of an upper endoscopy that day: true as worded. An exact-negation pair is exact only under its presupposition.

# Each form's declared sets as REVIEWED (NOTES, Repair round 2; the reasons in question_claims.Source.why): per subject
# position, every (class/status) for which the form's sentence is true exactly when the engine's fact holds. Literal, so a
# widened declaration fails here.
DONE = ['act/performed']
ANY_ACT = ['act/attempted', 'act/in_doubt', 'act/performed', 'act/planned']
EVENT = ANY_ACT + ['statement/denied', 'statement/in_doubt']
STATEMENT_SIDE = EVENT + ['unlisted/denies', 'unlisted/doubts']
ENTRIES = ['unlisted/doubts', 'unlisted/tells']
SESSION = ['session/none']
SINGLE = ['lesion/single']
LESIONS = ['lesion/not_single', 'lesion/single']
EXACT = {
    'rel': [STATEMENT_SIDE, EVENT], 'onlesion': [DONE, SINGLE], 'onlesion.group': [DONE, LESIONS],
    'lesion.distinct_from': [SINGLE, SINGLE], 'lesion.not_member': [LESIONS, SINGLE],
    'lesion.not_member.any': [LESIONS, LESIONS], 'absorb': [ENTRIES], 'fact.date_relation': [DONE],
    'fact.entry': [ANY_ACT], 'fact.performer': [DONE], 'fact.performer_person': [DONE], 'fact.session': [DONE],
    # DECISIONS D315 (6): G1 never of an attempt or an act in doubt (probe-check4's ck4_g1.py)
    'fact.session.not': [['act/performed', 'act/planned']], 'fact.target.lesion': [DONE], 'fact.target.places': [DONE],
    'fact.technique.device': [DONE], 'fact.purpose': [DONE], 'fact.target.duct': [DONE], 'fact.part_link.any': [DONE],
    'fact.cause.not': [DONE], 'fact.lift.not': [DONE], 'fact.hemostasis.not': [DONE], 'fact.reached': [SESSION],
    'fact.reached_anatomy': [SESSION], 'fact.stations': [SESSION], 'fact.visit.basis': [DONE],
    # DECISIONS D318 (3): each narrow Q-REL form exact for one statement side; D312: the route's subjects
    'rel.deny': [['statement/denied'], EVENT], 'rel.deny_or_doubt': [['statement/in_doubt'], EVENT],
    'rel.plan': [['act/planned'], EVENT], 'fact.approach': [SESSION], 'fact.type': [['anatomy/none']],
}
EVERY_SUBJECT = [(klass, status) for klass in SC for status in SS] if SC is not None else []
OC = asking.rq.ObjectClass


class QuestionClassTests(SimpleTestCase):
    """DECISIONS D314 (1), THE CLASS, for the questions: every form takes its sentence from the fact pass's own form for
    (object class, attribute, state) - claims.FORMS for the class it is declared for, or claims.LESION_PAIR_FORMS - and
    declares the classes and statuses its sentence is exact for; a form handed a subject outside is Unbuildable (pin c),
    through the request builder and through the planner, which leaves the held fact held with its census reason; G1's
    fact.session.not is the one named exception (an act of any status: its fact is the not-done reading)."""

    def test_every_form_declares_its_reviewed_exact_set(self) -> None:
        self.assertEqual(set(EXACT), set(question_claims.QUESTION_SOURCES))
        for form, source in question_claims.QUESTION_SOURCES.items():
            with self.subTest(form=form):
                self.assertEqual([exact.names() for exact in source.exact], EXACT[form])
                self.assertTrue(source.why)
        self.assertEqual([form for form, source in question_claims.QUESTION_SOURCES.items() if source.exception],
                         ['fact.session.not'])

    def test_every_form_takes_the_fact_passs_own_form_for_its_class(self) -> None:
        for form, source in question_claims.QUESTION_SOURCES.items():
            key = source.fact or source.negative_fact
            if key is None:
                continue
            with self.subTest(form=form):
                self.assertEqual({klass for klass, _ in source.exact[0].pairs}, {SC(key[0].value)})
                self.assertIn(claims.FORMS[key], (source.positive, source.negative))
                # the fact pass words a statement's fact of that attribute otherwise ("This statement is about ...") or
                # not at all: never this sentence
                self.assertNotEqual(claims.FORMS.get((OC.STATEMENT, key[1], key[2])), claims.FORMS[key])
        for index, form in enumerate(('lesion.distinct_from', 'lesion.not_member', 'lesion.not_member.any')):
            source = question_claims.QUESTION_SOURCES[form]
            self.assertEqual((source.positive, source.negative), claims.LESION_PAIR_FORMS[index])
        self.assertEqual(question_claims.form_of('Q-FACT', OC.ACT, A.SESSION, ct.FactState.SUPPORTED), 'fact.session')
        self.assertIsNone(question_claims.form_of('Q-FACT', OC.STATEMENT, A.SESSION, ct.FactState.SUPPORTED))
        self.assertEqual(question_claims.form_of('Q-ONLESION', OC.ACT, A.TARGET_LESION, ct.FactState.SUPPORTED),
                         'onlesion')

    def test_a_form_is_unbuildable_for_every_subject_outside_its_declared_set(self) -> None:  # pin (c)
        for form, source in question_claims.QUESTION_SOURCES.items():
            for position, exact in enumerate(source.exact):
                for found in EVERY_SUBJECT:
                    subjects = [typical(item) for item in source.exact]
                    subjects[position] = found
                    with self.subTest(form=form, position=position, found=found):
                        if found in exact.pairs:
                            question_claims.check_exact(form, subjects)
                        else:
                            with self.assertRaises(question_claims.Unbuildable):
                                question_claims.check_exact(form, subjects)
            with self.assertRaises(question_claims.Unbuildable):  # a subject the facts do not hold
                question_claims.check_exact(form, [None] * len(source.exact))

    def test_the_request_writes_no_sentence_for_a_subject_outside_or_an_undescribed_spec(self) -> None:  # pin (c)
        for status in (SS.PLANNED, SS.ATTEMPTED, SS.IN_DOUBT):
            with self.subTest(status=status), self.assertRaises(question_claims.Unbuildable):
                question_claims._sentences(dataclasses.replace(DATE, described=((SC.ACT, status),)), _WordingCards())
        with self.assertRaises(question_claims.Unbuildable):  # a denial handed an act's sentence
            question_claims._sentences(dataclasses.replace(DATE, described=((SC.STATEMENT, SS.DENIED),)),
                                       _WordingCards())
        with self.assertRaises(question_claims.Unbuildable):  # no planner described it: never built
            question_claims._sentences(dataclasses.replace(DATE, described=()), _WordingCards())
        planned = dataclasses.replace(SESSION_NOT, described=((SC.ACT, SS.PLANNED),))  # G1: the named exception
        self.assertEqual(question_claims._sentences(planned, _WordingCards())[1:],
                         ('This act was not done during session X1.', 'This act was done during session X1.'))

    def test_the_planner_leaves_a_held_fact_held_when_the_form_is_not_exact(self) -> None:  # pin (c), the planner
        denial = colonoscopy()  # row 7's possible examination is a DENIAL (a statement): G1 is not its fact
        denial.event(3, kind=sup(Kind.EXAMINATION), status=neg(Status.PERFORMED), session=F.SILENT, date=sup(ON),
                     entry=sup(DC))
        R = denial.build()
        found = plan_of(R)
        self.assertFalse([spec for spec in found.specs if spec.census == 'G1'])
        self.assertTrue([reason for reason in found.blocked if reason.startswith('D314 (fact.session.not is not exact '
                                                                                 'for statement/denied')], found.blocked)
        self.assertTrue(held_of(R, '45385'))
        attempted = colonoscopy()  # the same tie on an ATTEMPTED examination (an act, begun, not completed): DECISIONS
        attempted.event(3, kind=sup(Kind.EXAMINATION), status=sup(Status.ATTEMPTED_NOT_COMPLETED), session=F.SILENT,
                        date=sup(ON), entry=sup(DC))  # D315 (6) - "not done during X" is true of an attempt that WAS
        found = plan_of(attempted.build())  # X's examination - so G1 is never asked of it, and the held fact stays held
        self.assertFalse([spec for spec in found.specs if spec.census == 'G1'])
        self.assertIn('D314 (fact.session.not is not exact for act/attempted (subject 1; declared act/performed, '
                      'act/planned))', found.blocked)
        # nor the act-phrased "This act was done by ..." / "... during session X"
        self.assertFalse([spec for spec in found.specs if spec.form in ('fact.performer', 'fact.session')])
        self.assertIn('D314 (fact.performer is not exact for act/attempted (subject 1; declared act/performed))',
                      found.blocked)

    def test_no_lesion_pair_form_is_asked_whatever_the_multiplicities(self) -> None:  # DECISIONS D323 O1
        # Q-LESION is not shipped (D320; never sent to Fable) and b.3 is reverted: the planner asks no lesion-pair
        # question of any multiplicity (the prototype asked one where both lesions were established single)
        events = {'claims': [{'id': 'K9', 'template': 'lesion.distinct_from'}],
                  'lesion_pairs': [{'lesion': 'L1', 'other': 'L2', 'result': 'supported', 'claim': 'K9', 'reasons': []}]}
        doc = colonoscopy()
        doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
        doc.lesion(2, lesion_places=[sup(Landmark.RECTUM)])  # its multiplicity not established
        found = asking.plan(doc.build(), (), events=events)
        self.assertFalse([spec for spec in found.specs if spec.family is QS.Q_LESION])
        self.assertFalse([reason for reason in found.blocked if reason.startswith('D314 (lesion.')], found.blocked)
        doc.lesion(2, lesion_places=[sup(Landmark.RECTUM)], multiplicity=sup(ct.Multiplicity.SINGLE))
        found = asking.plan(doc.build(), (), events=events)
        self.assertFalse([spec for spec in found.specs if spec.family is QS.Q_LESION])

    def test_every_spec_the_planner_asks_is_described_and_exact(self) -> None:
        for doc in (colonoscopy(date=unres(ON, ct.Reason.GEOMETRY_SECTION)), colonoscopy(entry=F.SILENT)):
            R = doc.build()
            for spec in plan_of(R).specs:
                with self.subTest(spec=spec.key):
                    self.assertEqual(spec.described, tuple(asking.describe(R, stored) for stored in spec.subjects))
                    question_claims.check_exact(spec.form, spec.described)


def _not_done_doc() -> object:
    """A colonoscopy X1 (E1 its examination) with the snare E2 of the single lesion L1 - both done - beside an event of
    every status that is NOT an act done: a denial E3, a planned act E4, an attempted act E5 and an act whose status is
    in doubt E6, each with E2's facts established AND controlled (date relation on the date of service, entry, performer,
    session X1, target lesion L1); E7, done, targets the group L2 (K4's group form); a second session X2 - an EGD that
    TOOK PLACE, its examination E8 done (DECISIONS D315 (1): a K2 alternative is a procedure session that took place) -
    gives K2 its alternative. Each of E3-E6 would give every K1, K2 and K4 form were its status not read."""
    doc = colonoscopy()
    doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
    doc.lesion(2, lesion_places=[sup(Landmark.RECTUM)], multiplicity=sup(ct.Multiplicity.GROUP))
    doc.session(2, SessionKind.EGD)
    statuses = {3: neg(Status.PERFORMED), 4: sup(Status.PLANNED), 5: sup(Status.ATTEMPTED_NOT_COMPLETED),
                6: unres(Status.PERFORMED, ct.Reason.UNAPPRAISED)}
    for number, status in statuses.items():
        doc.event(number, kind=sup(Kind.SNARE), status=status, session=sup(X(1)), date=sup(ON), performer=sup(TEAM),
                  entry=sup(DC), lesion=sup(L(1)), places=[sup(Landmark.SIGMOID_COLON)])
    doc.act(7, Kind.BIOPSY, places=[sup(Landmark.RECTUM)], lesion=sup(L(2)))
    # D315: X2 took place (E8 is its own examination, done; its facts not controlled); D317 (4): on an earlier date, so
    # the two sessions are of established different dates (K2's alternative)
    doc.exam(8, session=X(2), date=sup(ct.DateRelation.EARLIER_DATE))
    R = doc.build()
    controlled = {(E(number), attribute) for number in range(1, 8)
                  for attribute in (A.DATE_RELATION, A.ENTRY, A.PERFORMER, A.SESSION, A.TARGET_LESION)}
    return dataclasses.replace(R, controlled=frozenset(controlled))


K_FORMS = {('K1', 'fact.date_relation'), ('K1', 'fact.entry'), ('K1', 'fact.performer'), ('K1', 'fact.session'),
           ('K2', 'fact.session'), ('K4', 'onlesion'), ('K4', 'onlesion.group')}


def by_words(R, item) -> bool:
    """The constructed reader's answer to a calibration item's CLAIM as worded, on a FactSet whose facts ARE the truth:
    an act-form sentence "This act was (not) done <q>" (and K4's "... not done to lesion L") says the act was done (or
    not done) WITH that fact - so a negated claim is TRUE of an act not done whatever its fact (D314's flip), and a
    positive one is false of it; of an act done, the claim is true exactly when its words match the facts. The entry's
    sentence is about where the act is told, true exactly when its owner is the established one."""
    subject = Id.parse(item.subjects[0])
    done = F.holds(F.fact(R, subject, A.STATUS), Status.PERFORMED)
    if item.form == 'fact.entry':
        return F.fact(R, subject, A.ENTRY).value.value != item.value  # claim negated: "... not written by <owner>"
    attribute = item.attribute
    holds = str(getattr(F.fact(R, subject, attribute).value, 'value', F.fact(R, subject, attribute).value)) == item.value
    return (not done or not holds) if item.negated else (done and holds)


class CalibrationClassTests(SimpleTestCase):
    """DECISIONS D314 (1), THE CLASS, for the calibration items: K1, K2 and K4 - every act-form item - are drawn only from
    an event whose object class is ACT and whose status is ESTABLISHED performed (asking.performed_act, the one
    predicate, on the class reading asking._acts_of shares: asking.event_class), each in the fact pass's own form for
    (object class, attribute, state) (question_claims.form_of); K3 keeps its statement form and its sources. Pin (b): a
    denial, a planned act, an attempted act and an act whose status is in doubt - of every K1/K2/K4 form - give none."""

    def test_no_act_form_item_is_drawn_of_an_act_not_done(self) -> None:  # pin (b)
        R = _not_done_doc()
        pool = asking.calibration_pool(R)
        self.assertEqual({item.subjects[0] for item in pool if item.kind in ('K1', 'K2', 'K4')}, {'E1', 'E2', 'E7'})
        for number in (3, 4, 5, 6):
            with self.subTest(event=f'E{number}'):
                self.assertFalse([item.key for item in pool if item.subjects[0] == f'E{number}' and item.kind != 'K3'])
        drawn = {(item.kind, item.form) for item in pool if item.subjects[0] in ('E2', 'E7')}
        self.assertEqual(drawn, K_FORMS)  # the positive control: every K1/K2/K4 form IS drawn of an act done
        for item in pool:
            question_claims.check_exact(item.form, item.described)
            if item.kind in ('K1', 'K2', 'K4'):
                self.assertEqual(item.described[0], (SC.ACT, SS.PERFORMED))

    def test_every_drawn_item_states_a_false_claim_and_an_act_not_done_would_not(self) -> None:  # pin (a), constructed
        R = _not_done_doc()
        pool = asking.calibration_pool(R)
        for item in pool:
            with self.subTest(item=item.key):
                self.assertFalse(by_words(R, item))
        # the items an act not done would give (the D313 pool drew them): a negated act-form claim of each - the date
        # relation, the performer, the session and the target lesion - is TRUE as worded, so a correct answer breaches
        for number in (3, 4, 5, 6):
            for item in pool:
                if item.subjects[0] != 'E2' or not item.negated or item.form == 'fact.entry':
                    continue
                twin = dataclasses.replace(item, subjects=(f'E{number}', *item.subjects[1:]))
                with self.subTest(event=number, form=item.form):
                    self.assertTrue(by_words(R, twin))

    def test_the_predicate_is_one_function_on_the_class_acts_of_reads(self) -> None:
        R = _not_done_doc()
        self.assertIn('E2', asking._acts_of(R, None))
        self.assertNotIn('E3', asking._acts_of(R, None))  # a statement filed as one is no act an entry re-tells
        self.assertEqual((asking.event_class(R, E(3)), asking.event_class(R, E(4))), (OC.STATEMENT, OC.ACT))
        self.assertEqual([asking.performed_act(R, E(n)) for n in range(1, 8)], [True, True, False, False, False, False,
                                                                                True])
        with mock.patch.object(asking, 'event_class', return_value=OC.STATEMENT):  # ONE class reading: both follow it
            self.assertEqual(asking._acts_of(R, None), ())
            self.assertFalse([item for item in asking.calibration_pool(R) if item.kind != 'K3'])
        calls = []
        real = question_claims.form_of

        def recorded(*args):
            calls.append(args)
            return real(*args)

        with mock.patch.object(question_claims, 'form_of', side_effect=recorded):  # the K forms: by (class, attribute)
            asking.calibration_pool(R)
        self.assertIn(('Q-FACT', OC.ACT, A.SESSION, ct.FactState.SUPPORTED), calls)
        self.assertIn(('Q-ONLESION', OC.ACT, A.TARGET_LESION, ct.FactState.SUPPORTED), calls)

    def test_gate_3_8_holds_on_the_restricted_pool(self) -> None:
        # DECISIONS D319: gate 3.8 is one item a request, a known-false claim (negative-form wherever the pool has one)
        pool = asking.calibration_pool(_not_done_doc())
        for count in (1, 6, 17):
            with self.subTest(questions=count):
                drawn = asking.draw(pool, specs_of(count), 'seed')
                self.assertEqual(len(drawn), 1)
                self.assertGreaterEqual(2 * sum(1 for item in drawn if item.negative), len(drawn))


class EntryAnchorTests(SimpleTestCase):
    """DECISIONS D314 (2), ENTRY: D313's "This act is told in a part of the document written by {owner}." is existential -
    true of an act anchored in a nursing, anesthesia or outside entry that the documenting clinician merely restates -
    while the engine's fact is the owner of the part the act's ANCHOR is told in (evaluate._entry; pass 1: a line that
    only refers back to an act told in another entry does not move it). The sentence names the anchor's units (the
    act's card), keeps no section start (D313's edit stands), and its control negates the owner alone."""

    ENTRY = asking.QuestionSpec(QS.Q_FACT, 'fact.entry', ('E2',), A.ENTRY, 'documenting_clinician', False, ('E2',),
                                value_passage='frame', census='F1')

    def test_the_entry_is_bound_to_the_acts_anchor_units(self) -> None:
        built = stub_request([self.ENTRY], [K1, K2], events=(frame_source('E2', 'entry', ('S1',)),))
        item = next(found for found in built.items if found.role == 'question')
        self.assertEqual((item.claim_sentence, item.control_sentence),
                         ('This act is told at S2, in a part of the document written by the documenting clinician.',
                          'This act is told at S2, in a part of the document not written by the documenting '
                          'clinician.'))
        self.assertEqual(item.claim_sentence.replace(*question_claims.ENTRY_NEGATION), item.control_sentence)
        self.assertNotIn('begins at', item.claim_sentence + item.control_sentence)  # no section start (D313)

    def test_a_restated_act_the_old_sentence_holds_and_the_anchored_one_does_not(self) -> None:
        """The constructed restated-act case: a nursing entry (units S1-S2) tells the act at S2, its anchor; the
        documenting clinician's part (S3-S4) restates it at S4. The engine's fact - the owner of the part the anchor is
        told in - is NURSING (a held entry). D313's sentence is TRUE as worded (S4 tells the act in a part the
        documenting clinician wrote): a release with no fact under it. The anchored sentence is FALSE, as the fact is."""
        owner_of = {'S1': ct.Owner.NURSING, 'S2': ct.Owner.NURSING, 'S3': ct.Owner.DOCUMENTING_CLINICIAN,
                    'S4': ct.Owner.DOCUMENTING_CLINICIAN}
        telling, anchor = ('S2', 'S4'), ('S2',)
        asked = ct.Owner.DOCUMENTING_CLINICIAN
        old = 'This act is told in a part of the document written by the documenting clinician.'  # D313's words
        old_true = any(owner_of[unit] is asked for unit in telling)  # existential over every unit that tells the act
        built = stub_request([self.ENTRY], [K1, K2], events=(frame_source('E2', 'entry', ('S1',)),))
        claim = next(found for found in built.items if found.role == 'question').claim_sentence
        named = tuple(unit for unit in owner_of if f'at {unit},' in claim or f'at {unit} ' in claim)
        self.assertEqual(named, anchor)  # it names the anchor's units, never the restatement's
        self.assertNotIn('S4', claim)
        new_true = all(owner_of[unit] is asked for unit in named)
        self.assertEqual((old_true, new_true), (True, False))
        self.assertNotEqual(claim, old)
        # and the engine's fact agrees with the anchored sentence: the entry nursing's, the code held on it
        self.assertIn('event_entry', held_of(colonoscopy(entry=sup(ct.Owner.NURSING)).build(), '45385'))

    def test_an_act_with_no_told_units_is_unbuildable(self) -> None:
        class NoUnits(_WordingCards):
            def units(self, stored: str) -> tuple:
                return ()

        with self.assertRaises(question_claims.Unbuildable):
            question_claims._sentences(described(self.ENTRY), NoUnits())


# --- DECISIONS D315: every OBJECT a calibration item names, under every reading of it -----------------------------------

K2_NONE = ('denied', 'planned', 'sedation', 'office', 'part', 'part_open', 'session_open', 'unsettled', 'not_gi')
K_ATTRIBUTES = (A.DATE_RELATION, A.ENTRY, A.PERFORMER, A.SESSION)


def _k2_doc(shape: str) -> object:
    """DECISIONS D315 (1): a colonoscopy X1 (its examination E1 and the cold snare E2 of L1, both done today) beside a
    second session X2 of one ``shape`` with its event E3; every act's date relation, entry, performer and session
    established AND controlled - so a K2 item naming X2 (of E1 or E2) or X1 (of E3) is drawn wherever the predicate
    lets it be. Shapes: 'procedure' - an EGD that TOOK PLACE (E3 its examination, done): the positive control;
    'denied' - an EGD whose only examination E3 is DENIED (a session that never took place: "no upper endoscopic
    procedure was performed"); 'planned' - a future colonoscopy (its kind supported, its examination E3 planned for a
    later date); 'sedation' - a moderate sedation service, its act E3 established done; 'office' - an office visit of
    the SAME encounter, its visit E3 established done; 'part' - an EGD that took place but is a part of X1
    (part_of_session); 'part_open' - the same with its part_of_session claim unresolved (a claim, though not
    established); 'session_open' - an EGD whose one act E3 was done but whose session is not established as X2 (only
    possibly X2: no act is established done in it); 'unsettled' - a session whose colonoscopy kind is unresolved, E3
    done in it; 'not_gi' - a session of no GI kind, E3 done in it."""
    doc = colonoscopy()
    this = sup(ct.EncounterRelation.THIS_ENCOUNTER)
    if shape == 'procedure':
        doc.session(2, SessionKind.EGD, encounter=this)
        doc.exam(3, session=X(2))
    elif shape == 'denied':
        doc.session(2, SessionKind.EGD, encounter=this)
        doc.event(3, kind=sup(Kind.EXAMINATION), status=neg(Status.PERFORMED), session=sup(X(2)), date=sup(ON),
                  performer=sup(TEAM), entry=sup(DC))
    elif shape == 'planned':
        doc.session(2, SessionKind.COLONOSCOPY, encounter=sup(ct.EncounterRelation.SEPARATE_ENCOUNTER))
        doc.act(3, Kind.EXAMINATION, session=X(2), status=sup(Status.PLANNED), date=sup(ct.DateRelation.LATER_DATE))
    elif shape == 'sedation':
        doc.session(2, SessionKind.SEDATION, encounter=this)
        doc.act(3, Kind.MODERATE_SEDATION, session=X(2))
    elif shape == 'office':
        doc.session(2, SessionKind.OFFICE_EM, encounter=this)
        doc.act(3, Kind.EM_VISIT, session=X(2))
    elif shape == 'part':
        doc.session(2, SessionKind.EGD, encounter=this, part_of_session=sup(X(1)))
        doc.exam(3, session=X(2))
    elif shape == 'part_open':
        doc.session(2, SessionKind.EGD, encounter=this, part_of_session=unres(X(1)))
        doc.exam(3, session=X(2))
    elif shape == 'session_open':
        doc.session(2, SessionKind.EGD, encounter=this)
        doc.exam(3, session=unres(X(2)))
    elif shape == 'unsettled':
        doc.session(2, unres(SessionKind.COLONOSCOPY), encounter=this)
        doc.exam(3, session=X(2))
    elif shape == 'not_gi':
        doc.session(2, SessionKind.NOT_GI, encounter=sup(ct.EncounterRelation.SEPARATE_ENCOUNTER))
        doc.act(3, Kind.OTHER, session=X(2))
    else:
        raise AssertionError(shape)
    if shape != 'planned':  # DECISIONS D317 (4): X2's act on an earlier date - X1 and X2 of established different
        doc.events[E(3)][A.DATE_RELATION] = (sup(ct.DateRelation.EARLIER_DATE),)  # dates - so each shape differs
    R = doc.build()  # from 'procedure' only in the clause it names ('planned' keeps its later date)
    controlled = {(E(number), attribute) for number in (1, 2, 3) for attribute in K_ATTRIBUTES}
    return dataclasses.replace(R, controlled=frozenset(controlled))


def k2_of(R) -> set:
    return {(item.subjects[0], item.value) for item in asking.calibration_pool(R) if item.kind == 'K2'}


class K2SessionTests(SimpleTestCase):
    """DECISIONS D315 (1): "This act was done during session X." is known false only when X is ANOTHER session that
    TOOK PLACE and excludes the act's own - so K2's alternative is drawn only where asking.exclusive_sessions holds, the
    one predicate the K2 draw reads: the act's own established session and the alternative both procedure sessions
    (asking.procedure_session: kind supported among the six endoscopic kinds, an act established performed held in it,
    no part_of_session claim). A session that never took place makes the claim false only by its presupposition; a
    sedation service, an office visit of the same encounter, an unsettled or non-GI session or a part of a session may
    contain the act (pin b; the mutants of pin c are killed here)."""

    def test_no_k2_names_a_session_that_never_took_place_or_may_contain_the_act(self) -> None:  # pin (b)
        for shape in K2_NONE:
            with self.subTest(shape=shape):
                R = _k2_doc(shape)
                self.assertEqual(k2_of(R), set())
                # only K2's alternative is narrowed: the K1 session item of the act done in X1 is drawn as before
                self.assertIn(('K1', 'fact.session', ('E2',), 'X1'),
                              {(item.kind, item.form, item.subjects, item.value) for item in asking.calibration_pool(R)})

    def test_two_procedure_sessions_that_took_place_give_k2_both_ways(self) -> None:  # pin (b), the positive control
        self.assertEqual(k2_of(_k2_doc('procedure')), {('E1', 'X2'), ('E2', 'X2'), ('E3', 'X1')})

    def test_the_predicate_reads_each_clause_of_both_sessions(self) -> None:
        for shape in ('procedure', *K2_NONE):
            R = _k2_doc(shape)
            took_place = shape == 'procedure'
            with self.subTest(shape=shape):
                self.assertTrue(asking.procedure_session(R, X(1)))
                self.assertEqual(asking.procedure_session(R, X(2)), took_place)
                self.assertEqual((asking.exclusive_sessions(R, X(1), X(2)), asking.exclusive_sessions(R, X(2), X(1))),
                                 (took_place, took_place))  # BOTH sessions are read: the own side as the alternative
                self.assertFalse(asking.exclusive_sessions(R, X(1), X(1)))  # never the act's own session

    def test_the_procedure_kinds_are_the_six_endoscopic_kinds_and_no_other(self) -> None:
        six = {SessionKind.EGD, SessionKind.ENTEROSCOPY, SessionKind.COLONOSCOPY, SessionKind.FLEX_SIG, SessionKind.EUS,
               SessionKind.ERCP}
        self.assertEqual(set(asking.PROCEDURE_SESSION_KINDS), six)
        for kind in SessionKind:  # a session of each kind that took place (its examination E3 done in it)
            doc = colonoscopy()
            doc.session(2, kind)
            doc.exam(3, session=X(2))
            with self.subTest(kind=kind):
                self.assertEqual(asking.procedure_session(doc.build(), X(2)), kind in six)

    def test_the_k2_draw_reads_the_one_predicate_and_nothing_else_does(self) -> None:
        import ast
        from pathlib import Path

        R = _k2_doc('procedure')
        before = asking.calibration_pool(R)
        with mock.patch.object(asking, 'exclusive_sessions', return_value=False):  # the draw follows THE predicate
            after = asking.calibration_pool(R)
        self.assertEqual({item.key for item in before} - {item.key for item in after},
                         {item.key for item in before if item.kind == 'K2'})
        self.assertTrue([item for item in before if item.kind == 'K2'])
        callers: dict = {}
        root = Path(asking.__file__).resolve().parents[2]  # the studio package: every reader of the engine
        for path in sorted(root.rglob('*.py')):
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for function in ast.walk(tree):
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for node in ast.walk(function):
                    if isinstance(node, ast.Call):
                        name = getattr(node.func, 'id', None) or getattr(node.func, 'attr', None)
                        if name in ('exclusive_sessions', 'procedure_session'):
                            callers.setdefault(name, set()).add((path.name, function.name))
        self.assertEqual(callers, {'exclusive_sessions': {('asking.py', 'calibration_pool')},
                                   'procedure_session': {('asking.py', 'exclusive_sessions')}})


def _k4_doc() -> object:
    """DECISIONS D315 (2): a colonoscopy X1 (E1) with the EMR E2 of the single lesion L1, done to it in its own right
    (its part_of silent), and six acts targeting L1 that are each a PART of the EMR or may be - the lift E3 injected
    beneath L1 to enable it (lift_for), the snare-tip coagulation E4 of the defect's perimeter "as an adjunct to the same
    mucosal resection" (adjunct_of), a step E5 (step_of), an access E6 (access_for), a component E7 (component_of) and
    E8, whose part link is claimed but unresolved - every act's target and frame facts established AND controlled."""
    doc = colonoscopy(snare=False)
    doc.lesion(1, lesion_places=[sup(Landmark.SIGMOID_COLON)], multiplicity=sup(ct.Multiplicity.SINGLE))
    places = [sup(Landmark.SIGMOID_COLON)]
    doc.act(2, Kind.EMR, places=places, lesion=sup(L(1)))
    parts = {3: (Kind.INJECTION, ct.PartRelation.LIFT_FOR), 4: (Kind.ABLATION, ct.PartRelation.ADJUNCT_OF),
             5: (Kind.INTERVENTION, ct.PartRelation.STEP_OF), 6: (Kind.INJECTION, ct.PartRelation.ACCESS_FOR),
             7: (Kind.CLIP, ct.PartRelation.COMPONENT_OF)}
    for number, (kind, relation) in parts.items():
        doc.act(number, kind, places=places, lesion=sup(L(1)), part_of=sup(E(2)), part_relation=sup(relation))
    doc.act(8, Kind.INJECTION, places=places, lesion=sup(L(1)), part_of=unres(E(2)))
    R = doc.build()
    controlled = {(E(number), attribute) for number in range(1, 9) for attribute in (*K_ATTRIBUTES, A.TARGET_LESION)}
    return dataclasses.replace(R, controlled=frozenset(controlled))


class K4PartTests(SimpleTestCase):
    """DECISIONS D315 (2): "This act was not done to lesion L." is exact for an act done to the lesion in its own right;
    a part of another act - a lift, an adjunct, a step, an access, a component - takes its object from the whole, so
    whether the claim is true turns on the part link, not on the act. K4 is drawn only for an act whose part_of is
    SILENT (A-note8's E20 -> L8 and C-C2MEM-023's E20 -> L7 - lifts - and E23 -> L7 - the adjunct coagulation - are
    the documents' instances, NOTES Repair round 3)."""

    def test_k4_is_drawn_only_for_an_act_done_to_the_lesion_in_its_own_right(self) -> None:
        pool = asking.calibration_pool(_k4_doc())
        self.assertEqual({(item.subjects[0], item.value) for item in pool if item.kind == 'K4'}, {('E2', 'L1')})
        # a part keeps its other act-form items (K1): only the item whose object it takes from the whole is narrowed
        self.assertEqual({item.subjects[0] for item in pool if item.kind == 'K1'},
                         {f'E{number}' for number in range(1, 9)})

    def test_each_part_relation_and_an_unresolved_link_withhold_k4(self) -> None:
        R = _k4_doc()
        pool = asking.calibration_pool(R)
        for number in range(3, 9):
            with self.subTest(event=f'E{number}', part_of=F.fact(R, E(number), A.PART_OF).result):
                self.assertFalse(F.silent(F.fact(R, E(number), A.PART_OF)))
                self.assertFalse([item for item in pool if item.kind == 'K4' and item.subjects[0] == f'E{number}'])


class StatusPinTests(SimpleTestCase):
    """DECISIONS D315 (4): the unit pins of the D314 checker's surviving mutants (probe-check4/scripts/ck4_mutants.py):
    D - asking.event_status of an UNESTABLISHED status (unresolved, unknown, contradicted, silent, an open denial) is
    IN_DOUBT, never PERFORMED; E - asking.event_class reads pass 1's FILED state (pairing.filed_as_statement), never the
    settled result: an open denial stays a STATEMENT; P - a kept unlisted DENIAL is described as DENIES (so the absorb
    question, declared for an entry that tells or doubts an act, is never asked of it)."""

    OPEN_DENIAL = fact(ct.Result.UNRESOLVED, Status.PERFORMED, ct.FactState.NEGATED, reasons=(ct.Reason.APPRAISAL_UNCLEAR,))

    def doc(self) -> object:
        doc = colonoscopy(snare=False)
        statuses = {3: unres(Status.PERFORMED), 4: doubted(Status.PERFORMED, Status.PLANNED),
                    5: contra(Status.PERFORMED, Status.PLANNED), 6: None, 7: self.OPEN_DENIAL,
                    8: sup(Status.PERFORMED), 9: sup(Status.PLANNED), 10: sup(Status.ATTEMPTED_NOT_COMPLETED),
                    11: neg(Status.PERFORMED)}
        for number, status in statuses.items():
            doc.event(number, kind=sup(Kind.SNARE), status=status, session=sup(X(1)), date=sup(ON))
        return doc.build()

    def test_an_unestablished_status_is_in_doubt_never_performed(self) -> None:  # mutant D
        R = self.doc()
        found = {number: asking.event_status(R, E(number)) for number in range(3, 12)}
        self.assertEqual(found, {3: SS.IN_DOUBT, 4: SS.IN_DOUBT, 5: SS.IN_DOUBT, 6: SS.IN_DOUBT, 7: SS.IN_DOUBT,
                                 8: SS.PERFORMED, 9: SS.PLANNED, 10: SS.ATTEMPTED, 11: SS.DENIED})
        self.assertEqual(F.fact(R, E(6), A.STATUS), F.SILENT)  # E6's status is silent: no claim at all

    def test_the_class_is_pass_1s_filed_state_never_the_settled_result(self) -> None:  # mutant E
        R = self.doc()
        classes = {number: asking.event_class(R, E(number)) for number in range(3, 12)}
        self.assertEqual(classes, {3: OC.ACT, 4: OC.ACT, 5: OC.ACT, 6: OC.ACT, 7: OC.STATEMENT, 8: OC.ACT, 9: OC.ACT,
                                   10: OC.ACT, 11: OC.STATEMENT})
        self.assertEqual(asking.describe(R, 'E7'), (SC.STATEMENT, SS.IN_DOUBT))  # an open denial: a statement in doubt
        self.assertNotIn('E7', asking._acts_of(R, None))  # never an act an unlisted entry may re-tell
        # DECISIONS D324 (3) (L1-01): Q-ABSORB's list holds only acts ESTABLISHED performed (asking.performed_act) - so
        # E3 (in doubt: unresolved performed) is no longer listed, nor E4-E6, E9 and E10; was: E3 listed, its class ACT
        self.assertEqual(asking._acts_of(R, None), ('E1', 'E8'))

    def test_an_unlisted_denial_is_described_as_denies(self) -> None:  # mutant P
        doc = colonoscopy()
        for index, what in enumerate((ct.UnlistedWhat.ACT, ct.UnlistedWhat.DENIAL, ct.UnlistedWhat.DOUBT)):
            doc.unlisted.append(unlisted(what, Kind.BIOPSY, X(1), unit(20 + index)))
        R = doc.build()
        self.assertEqual([asking.describe(R, f'u:{index}') for index in range(3)],
                         [(SC.UNLISTED, SS.TELLS), (SC.UNLISTED, SS.DENIES), (SC.UNLISTED, SS.DOUBTS)])
        self.assertIsNotNone(question_claims.inexact('absorb', (asking.describe(R, 'u:1'),)))  # never asked of a denial
        self.assertIsNone(question_claims.inexact('absorb', (asking.describe(R, 'u:0'),)))
        self.assertIsNone(question_claims.inexact('absorb', (asking.describe(R, 'u:2'),)))
