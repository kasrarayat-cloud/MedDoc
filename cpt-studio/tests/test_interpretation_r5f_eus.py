"""DECISIONS D161 (the Gemini migration's round 5f, narrowing only: the round-5e review of the eus5 repair D156,
round5e/results-wf_ec2ec26b-bed.json 'review:eus5' problems 0-4), SYNTHETIC, each built from its source's own input
(the reviewer's review-eus5/tools/cases_review.py builders, re-built here on the test modules' own). Nothing is sent.
- (1) problem 0 (a fact dropped by key): where no supporting drainage meets 43240's defining target and 7.4 reads a
  candidate, 7.4's question and the target hold's question are TWO clarifications (events.Evaluation.second, asked by
  assess as its own clarification): with the EUS examination's own target given as the landmark it was advanced to,
  R6 asks no structure examined, and 43240 asks [performed_status, target] - e5628be56's performed_status and
  4f82e5056's target, both kept, each a member row of its own (code, family, fact).
- (2) problem 1 (pre-existing; the claim broken): with no candidate that meets the target, 7.4 reads the candidates
  whose target is not usable (unverified, unlocated or absent), so the failed drainage of 'the pseudocyst' tied to no
  lesion is asked about, with the 52/53 consideration, as e5628be56 and the installed release ask; never beside one
  that meets the target (7.4 asks one question, which would then name the other act); one whose target is verified
  elsewhere is not read.
- (3) problem 2: 7.4's passages are kept as 7.4 gave them (D143's STATEMENT and LEAD marks), never re-spanned.
Each test asserts in independent subtests, labelled by what each varies, so a regression shows every one it breaks."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import events, mapping, overlay
from studio.interpretation.assess import SERVICES_STUB
from studio.types import to_jsonable
from studio.validation import questions
from tests.test_interpretation_events import asked, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, les, sc, tg
from tests.test_interpretation_r3_integration_d88_d93 import reviewed
from tests.test_interpretation_r5_eus import DRAINAGE_LINES
from tests.test_interpretation_r5c_eus import GB, gallbladder
from tests.test_interpretation_r5d_eus import R6_TARGET
from tests.test_interpretation_r5e_eus import (ATTEMPTED, ATTEMPTED_PFC, ATTEMPTED_Q, ATTEMPTED_REASON, INCOMPLETE,
                                               LATER_PFC, LATER_Q, PSEUDOCYST, target_question, two_drainages)

EXAM_LINE = 'The linear echoendoscope was advanced to the stomach.'
PFC_SEEN = 'A 9 cm pancreatic pseudocyst was seen abutting the posterior gastric wall.'
CBD = tg('', 'common_bile_duct', 'the common bile duct', ['P4'])
GB_TARGET = tg('', 'gallbladder', 'the gallbladder', ['P4'])
LATER = dict(time=a('current_encounter', 'Later', ['P3']))
# e5628be56's 7.4 question about the failed drainage whose target is not verified (no lesion named in its label)
UNTIED_Q = ('The drainage was begun and not completed. Confirm whether 43240 describes what was done on the date of '
            'service.')
COLLECTION_Q = ('The drainage of the A 9 cm fluid collection was begun and not completed. Confirm whether 43240 '
                'describes what was done on the date of service.')


def drainage(eid: str, passage: str, target: dict, **changes) -> dict:
    """The review's drainage(): an EUS-guided transmural drainage with a stent, done unless ``changes`` say so."""
    options = dict(status_words='was performed', procedure=a('eus', 'EUS-guided', [passage]),
                   technique=a('stent', 'stent', [passage]), target=target)
    options.update(changes)
    return act(eid, passage, 'drainage', 'transmural drainage', **options)


def drainages(lines: dict, found: list, lesions=(PSEUDOCYST,), exam_target=None):
    """The review's drainages(): the EUS examination (E1, P1, its own target ``exam_target`` - none by default), then
    ``lines`` and the drainages ``found``."""
    first = exam('E1', 'P1', words='linear echoendoscope', procedure=a('eus', 'echoendoscope', ['P1']),
                 **({'target': exam_target} if exam_target is not None else {}))
    return inventory({'P1': EXAM_LINE, **lines}, events=[first] + list(found), lesions=list(lesions),
                     reach=[reached('E1', 'stomach', 'stomach', 'P1')])


LANDMARK = tg('', 'stomach', 'stomach', ['P1'])  # the examination's own target given as its landmark (R6 established)


def landmark_pfc(p3: str = ATTEMPTED_PFC, pfc_changes: dict = ATTEMPTED, other: str = 'bile_duct'):
    """Problem 0's input (the review's R_attempted_pfc_exam_landmark_stomach) and its twins: the examination's own
    target its landmark, the pseudocyst (L1), the pseudocyst drainage in doubt (E2, P3) and the done drainage of another
    structure (E3, P4)."""
    return drainages({'P2': PFC_SEEN, 'P3': p3, 'P4': DRAINAGE_LINES[other]},
                     [drainage('E2', 'P3', tg('L1', 'pancreas', 'the pseudocyst', ['P3']), **pfc_changes),
                      drainage('E3', 'P4', CBD if other == 'bile_duct' else GB_TARGET)], exam_target=LANDMARK)


def untied(target: dict, lesions=(PSEUDOCYST,), p2: str = PFC_SEEN, p3: str = ATTEMPTED_PFC):
    """Problem 1's inputs (the review's attempted_pfc_with_target and attempted_collection_beside_cbd): the attempted
    drainage's target given as ``target`` - not usable - beside the done drainage of the common bile duct."""
    return drainages({'P2': p2, 'P3': p3, 'P4': DRAINAGE_LINES['bile_duct']},
                     [drainage('E2', 'P3', target, **ATTEMPTED), drainage('E3', 'P4', CBD)], lesions=lesions)


COLLECTION_SEEN = 'A 9 cm fluid collection was seen abutting the posterior gastric wall.'
COLLECTION = les('L1', 'A 9 cm fluid collection', 'P2', landmark='pancreas', site_words='', size_words='9 cm')
COLLECTION_ATTEMPTED = 'EUS-guided transmural drainage of the collection was attempted but failed.'
UNTIED = {  # the review's four inputs: (inventory, the line 43240 cites, 7.4's question)
    'no_lesion_pancreas': (lambda: untied(tg('', 'pancreas', 'the pseudocyst', ['P3'])), ATTEMPTED_PFC, UNTIED_Q),
    'target_unlocated': (lambda: untied(tg('L1', 'pancreas', 'the pancreatic pseudocyst', ['P3'])), ATTEMPTED_PFC,
                         UNTIED_Q),
    'no_lesion_landmark_missing': (lambda: untied(tg('', 'not_stated', 'the pseudocyst', ['P3'])), ATTEMPTED_PFC,
                                   UNTIED_Q),
    'collection': (lambda: untied(tg('L1', 'pancreas', 'the collection', ['P3']), lesions=(COLLECTION,),
                                  p2=COLLECTION_SEEN, p3=COLLECTION_ATTEMPTED), COLLECTION_ATTEMPTED, COLLECTION_Q),
}


def standing(code: str, fact: str) -> dict:
    """A member's standing answer in the installed release's earlier form (no fingerprint: bound by its key)."""
    return {'code': code, 'family': 'gi.eus', 'fact': fact, 'value': 'not_documented', 'question': '',
            'answer_id': f'a-{fact}'}


def view_with(result, code: str, answers=()):
    stored = [overlay.stored_from(p) for p in result.proposals]
    return overlay.review_view(stored, {}, completeness=to_jsonable(result.completeness),
                               answers=answers)[proposal(result, code).key]


class TheTargetHoldsQuestionIsItsOwnClarification(SimpleTestCase):
    """D161 (1), problem 0: f9013e12e asked one question of 7.4's fact (performed_status) carrying the hold's words, so
    where R6 asks no structure examined 4f82e5056's 'target' row was gone; e5628be56 [performed_status], 4f82e5056
    [target], c2e53f8e [performed_status, target]."""

    def assert_two(self, result, first_q: str, first_reason: str, other: str, facts: list, attempted: bool):
        p = proposal(result, '43240')
        reason, question = target_question(other)
        self.assertEqual((p.status, p.bucket, asked(p)), ('needs_clarification', 'selected', facts))
        self.assertEqual([(spec.scope, spec.fact, spec.question, spec.reason) for spec in p.clarifications[:2]],
                         [('proposal', facts[0], first_q, first_reason), ('proposal', 'target', question, reason)])
        self.assertEqual((p.support['acts'], p.support['question_events']), ([], ['E2', 'E3']))
        self.assertEqual(any(text.startswith(INCOMPLETE) for text in p.modifier_considerations), attempted)
        view = reviewed(result, '43240')
        self.assertEqual((view.status, view.released, [q['fact'] for q in view.questions][:2]),
                         ('needs_clarification', (), facts[:2]))

    def test_d161_problem0_the_examinations_landmark_target_asks_both_facts(self):
        """The review's R_attempted_pfc_exam_landmark_stomach, 43240 cited on P3 and separately on P4."""
        inv, text = landmark_pfc()
        for cited, line in (('P3 the attempted pseudocyst drainage', ATTEMPTED_PFC),
                            ('P4 the bile duct drainage', DRAINAGE_LINES['bile_duct'])):
            result = run(inv, text, [('43240', line)])
            with self.subTest(cited=cited, part='assess'):  # f9013e12e: [performed_status], the hold's words inside it
                self.assert_two(result, ATTEMPTED_Q, ATTEMPTED_REASON, 'bile_duct', ['performed_status', 'target'],
                                True)
                self.assertEqual(proposal(result, '43240').support['reason'], events.ATTEMPTED)
            with self.subTest(cited=cited, part='member rows'):  # each (code, family, fact) its own row
                p = proposal(result, '43240')
                self.assertEqual({questions.member_key(p.code, spec.family or p.family, spec.fact)
                                  for spec in p.clarifications},
                                 {('43240', 'gi.eus', 'performed_status'), ('43240', 'gi.eus', 'target')})
            for fact in ('performed_status', 'target'):  # f9013e12e: the target answer bound nothing (held)
                with self.subTest(cited=cited, part='standing answer', fact=fact):
                    self.assertEqual(view_with(result, '43240', (standing('43240', fact),)).status, 'excluded')
            with self.subTest(cited=cited, part='completeness'):
                self.assertEqual(result.completeness['state'], 'incomplete')

    def test_d161_its_twins_ask_both_facts(self):
        """The same with the gallbladder's drainage; with the examination's own target the pseudocyst, verified (the
        round-5e builder's recorded residual and the review's twin); and with the pseudocyst drainage told 'Later, ...'
        (event_time, e5628be56's fact)."""
        examined = {other: two_drainages(ATTEMPTED_PFC, ATTEMPTED, other=other, examined=True)
                    for other in ('gallbladder', 'bile_duct')}
        cases = (('landmark, gallbladder', landmark_pfc(other='gallbladder'), 'gallbladder', ATTEMPTED_Q,
                  ATTEMPTED_REASON, ['performed_status', 'target'], True),
                 ('lesion, gallbladder', examined['gallbladder'], 'gallbladder', ATTEMPTED_Q, ATTEMPTED_REASON,
                  ['performed_status', 'target'], True),
                 ('lesion, bile duct', examined['bile_duct'], 'bile_duct', ATTEMPTED_Q, ATTEMPTED_REASON,
                  ['performed_status', 'target'], True),
                 ('landmark, later', landmark_pfc(LATER_PFC, LATER), 'bile_duct', LATER_Q,
                  'CPT Studio could not confirm from the document when the drainage (stent) of the A 9 cm pancreatic '
                  'pseudocyst in the pancreas was done.', ['event_time', 'target'], False))
        for name, (inv, text), other, first_q, first_reason, facts, attempted in cases:
            cited = LATER_PFC if name.endswith('later') else ATTEMPTED_PFC
            with self.subTest(twin=name):  # f9013e12e: facts[:1] alone
                self.assert_two(run(inv, text, [('43240', cited)]), first_q, first_reason, other, facts, attempted)

    def test_d161_where_r6_asks_the_structure_examined_both_targets_are_asked(self):
        """The round-5e source (the review's mix_attempted_pfc_beside_cbd): 7.4's, the hold's, then R6's."""
        inv, text = two_drainages(ATTEMPTED_PFC, ATTEMPTED)
        for cited, line in (('P3 the attempted pseudocyst drainage', ATTEMPTED_PFC),
                            ('P4 the bile duct drainage', DRAINAGE_LINES['bile_duct'])):
            with self.subTest(cited=cited):  # f9013e12e: [performed_status, target], the hold's words inside the first
                result = run(inv, text, [('43240', line)])
                self.assert_two(result, ATTEMPTED_Q, ATTEMPTED_REASON, 'bile_duct',
                                ['performed_status', 'target', 'target'], True)
                self.assertEqual(proposal(result, '43240').clarifications[2].question, R6_TARGET)

    def test_d161_controls_a_hold_with_no_candidate_asks_its_own_question_alone(self):
        """Unchanged: g1_gallbladder_43240 - no candidate, the hold's question and R6's ([target, target])."""
        inv, text = gallbladder()
        p = proposal(run(inv, text, [('43240', GB['P4'])]), '43240')
        _, question = target_question('gallbladder')
        self.assertEqual((asked(p), [spec.question for spec in p.clarifications], p.support['question_events'],
                          p.support['reason']), (['target', 'target'], [question, R6_TARGET], ['E2'],
                                                 events.ANOTHER_SITE))

    def test_d161_a_service_question_the_code_asks_word_for_word_is_asked_once(self):
        """D89 (a code's question suppresses a service question only when it is the same question, fact and words): the
        review's mix_later_pfc_beside_cbd - 43240 asks the drainage's time with e5628be56's words, so the in-doubt
        listing f9013e12e and 4f82e5056 give stays and its service question is the code's (e5628be56 asked no
        service question). Beside a second act in doubt (the gallbladder's, told 'Later, ...') that (family, fact)
        slot asks the other act's time."""
        inv, text = two_drainages(LATER_PFC, LATER)
        result = run(inv, text, [('43240', LATER_PFC)])
        with self.subTest(part='assess'):
            self.assertEqual((asked(proposal(result, '43240')), proposal(result, '43240').clarifications[0].question),
                             (['event_time', 'target', 'target'], LATER_Q))
        with self.subTest(part='listing'):
            self.assertEqual([(item['service'], item['reason'], item['events'])
                              for item in result.completeness['unresolved_items']], [('gi.eus', 'in_doubt', ['E2'])])
            self.assertEqual([(spec.scope, spec.fact) for spec in result.clarifications], [])
        later_gb = ('Later, EUS-guided transmural drainage of the gallbladder was performed from the duodenal bulb '
                    'with a 15 mm lumen-apposing metal stent.')
        inv, text = drainages({'P2': PFC_SEEN, 'P3': LATER_PFC, 'P4': DRAINAGE_LINES['bile_duct'], 'P5': later_gb},
                              [drainage('E2', 'P3', tg('L1', 'pancreas', 'the pseudocyst', ['P3']), **LATER),
                               drainage('E3', 'P4', CBD),
                               drainage('E4', 'P5', tg('', 'gallbladder', 'the gallbladder', ['P5']),
                                        time=a('current_encounter', 'Later', ['P5']))])
        result = run(inv, text, [('43240', LATER_PFC)])
        with self.subTest(part='second act in doubt'):  # f9013e12e: the pseudocyst drainage's time at service scope
            self.assertEqual([(item['reason'], item['events']) for item in result.completeness['unresolved_items']],
                             [('in_doubt', ['E2', 'E4'])])
            self.assertEqual([(spec.scope, spec.fact, spec.question) for spec in result.clarifications],
                             [('service', 'event_time', 'Was the drainage (stent) at the gallbladder (“was performed”) '
                                                        'done at this encounter?')])


class SevenFourReadsACandidateWhoseTargetIsNotUsable(SimpleTestCase):
    """D161 (2), problem 1: f9013e12e (and 4f82e5056) [target, target], the failed drainage in no question and no
    52/53 consideration; e5628be56 [performed_status, target] with it; c2e53f8e [performed_status, target]."""

    def test_d161_problem1_the_failed_drainage_of_an_untied_collection_is_asked(self):
        """The review's R_attempted_pfc_no_lesion_pancreas, _target_unlocated, _no_lesion_landmark_missing and
        R_attempted_collection_beside_cbd."""
        link = mapping.code_link('43240')
        reason, question = target_question('bile_duct')
        for name, (build, cited, first_q) in UNTIED.items():
            inv, text = build()
            reading = events.Reading.of(inv)
            with self.subTest(input=name, part='fixture'):  # E2: no support, misses the target, its target not usable
                event = reading.events['E2']
                self.assertEqual((events.supports(reading, link, ('drainage',), event),
                                  events.defining_fit(reading, link, event), events.usable(event, 'target')),
                                 (False, False, False))
            result = run(inv, text, [('43240', cited)])
            p = proposal(result, '43240')
            with self.subTest(input=name, part='assess'):
                self.assertEqual((p.status, asked(p), p.support['reason']),
                                 ('needs_clarification', ['performed_status', 'target', 'target'], events.ATTEMPTED))
                self.assertEqual([(spec.fact, spec.question) for spec in p.clarifications[:2]],
                                 [('performed_status', first_q), ('target', question)])
                self.assertEqual(p.clarifications[1].reason, reason)
                self.assertTrue(any(text.startswith(INCOMPLETE) for text in p.modifier_considerations))
            with self.subTest(input=name, part='overlay'):
                self.assertEqual(reviewed(result, '43240').status, 'needs_clarification')

    def test_d161_never_beside_a_candidate_that_meets_the_target(self):
        """Constructed (D161's narrowing form): the pseudocyst drainage told 'Later, ...' whose target words Gemini tied
        to no lesion (E2, P3) beside the bile duct drainage and the failed drainage of the verified pseudocyst (E4, P5).
        Read with E4, 7.4's one question would be E2's time (its rule comes first), and the failed drainage's
        performed_status and 52/53 consideration, which f9013e12e asks, would be gone; so 7.4 reads E4 alone, as
        f9013e12e does, and E2 stays listed in doubt with its service question."""
        failed = 'EUS-guided transmural drainage of the pseudocyst was attempted but failed.'
        inv, text = drainages({'P2': PFC_SEEN, 'P3': LATER_PFC, 'P4': DRAINAGE_LINES['bile_duct'], 'P5': failed},
                              [drainage('E2', 'P3', tg('', 'pancreas', 'the pseudocyst', ['P3']), **LATER),
                               drainage('E3', 'P4', CBD),
                               drainage('E4', 'P5', tg('L1', 'pancreas', 'the pseudocyst', ['P5']), **ATTEMPTED)])
        result = run(inv, text, [('43240', LATER_PFC)])
        p = proposal(result, '43240')
        with self.subTest(part='assess'):  # f9013e12e: [performed_status, target], E4's question with 52/53
            self.assertEqual((asked(p), p.clarifications[0].question, p.support['reason']),
                             (['performed_status', 'target', 'target'], ATTEMPTED_Q, events.ATTEMPTED))
            self.assertEqual(p.support['question_events'], ['E4', 'E3'])
            self.assertTrue(any(text.startswith(INCOMPLETE) for text in p.modifier_considerations))
        with self.subTest(part='listing'):  # E2 in doubt, its time asked at service scope, as on f9013e12e
            self.assertEqual([(item['reason'], item['events']) for item in result.completeness['unresolved_items']],
                             [('in_doubt', ['E2'])])
            self.assertEqual([(spec.scope, spec.fact) for spec in result.clarifications], [('service', 'event_time')])

    def test_d161_controls_a_candidate_whose_target_is_verified_elsewhere_is_not_read(self):
        """Unchanged from f9013e12e: a failed GALLBLADDER drainage (its target verified: 43240 cannot describe it) and
        an untied failed drainage verified at another occasion are no 7.4 candidates - the hold's question alone, on the
        bile duct drainage; and an untied drainage that SUPPORTS (done, its target not verified) is the hold's own
        (reason SITE), as on f9013e12e. e5628be56 asked the failed gallbladder drainage's 7.4 question (D145's
        recorded move); c2e53f8e holds every one [performed_status, target]."""
        gb_failed = 'EUS-guided transmural drainage of the gallbladder was attempted but failed.'
        other_time = ('At her index EUS on 01/14/2024, EUS-guided transmural drainage of the pseudocyst was attempted '
                      'but failed.')
        _, bile_duct = target_question('bile_duct')
        gb_lines = {'P2': PFC_SEEN, 'P3': gb_failed, 'P4': DRAINAGE_LINES['bile_duct']}
        cases = (('gallbladder failed', drainages(gb_lines, [
                     drainage('E2', 'P3', tg('', 'gallbladder', 'the gallbladder', ['P3']), **ATTEMPTED),
                     drainage('E3', 'P4', CBD)]), gb_failed, events.ANOTHER_SITE, ['E3'], bile_duct),
                 ('untied, another occasion', drainages(
                     {'P2': PFC_SEEN, 'P3': other_time, 'P4': DRAINAGE_LINES['bile_duct']},
                     [drainage('E2', 'P3', tg('', 'pancreas', 'the pseudocyst', ['P3']),
                               time=a('earlier_encounter', 'At her index EUS on 01/14/2024', ['P3']), **ATTEMPTED),
                      drainage('E3', 'P4', CBD)]), DRAINAGE_LINES['bile_duct'], events.ANOTHER_SITE, ['E3'],
                  bile_duct),
                 ('untied, supporting', drainages({'P2': PFC_SEEN, 'P3': DRAINAGE_LINES['pseudocyst']},
                                                  [drainage('E2', 'P3', tg('', 'pancreas', 'the pseudocyst', ['P3']))]),
                  DRAINAGE_LINES['pseudocyst'], events.SITE, ['E2'], None))
        for name, (inv, text), cited, why, events_asked, first_q in cases:
            with self.subTest(control=name):
                p = proposal(run(inv, text, [('43240', cited)]), '43240')
                self.assertEqual((asked(p), p.support['reason'], p.support['question_events']),
                                 (['target', 'target'], why, events_asked))
                if first_q is not None:
                    self.assertEqual([spec.question for spec in p.clarifications], [first_q, R6_TARGET])
                self.assertFalse(any(text.startswith(INCOMPLETE) for text in p.modifier_considerations))


H3_P5 = 'No stent was placed in the pseudocyst.'
H3_P6 = 'The pseudocyst was not drained.'


def two_denials():
    """Problem 2's input (the review's R_pfc_two_denials_beside_cbd): a done pseudocyst drainage (E2, P3) with two
    denials of it, scoped by their own words (E4, P5; E5, P6: two UNRESOLVED relations - D143's question about several
    statements), beside the done bile duct drainage (E3, P4: supports 43240 and misses its target)."""
    lines = {'P2': PFC_SEEN, 'P3': DRAINAGE_LINES['pseudocyst'], 'P4': DRAINAGE_LINES['bile_duct'], 'P5': H3_P5,
             'P6': H3_P6}
    found = [drainage('E2', 'P3', tg('L1', 'pancreas', 'the pseudocyst', ['P3'])), drainage('E3', 'P4', CBD),
             drainage('E4', 'P5', tg('L1', 'pancreas', 'the pseudocyst', ['P5']), status='not_performed',
                      status_words='No stent was placed', technique=a('stent', 'stent', ['P5']),
                      scope=sc('single_target', 'the pseudocyst', ['P5'])),
             drainage('E5', 'P6', tg('L1', 'pancreas', 'The pseudocyst', ['P6']), status='not_performed',
                      status_words='was not drained', technique=a('not_stated'),
                      scope=sc('single_target', 'The pseudocyst', ['P6']))]
    return drainages(lines, found)


class SevenFoursPassagesAreKeptAsTheyAre(SimpleTestCase):
    """D161 (3), problem 2: f9013e12e re-spanned 7.4's passages, dropping D143's STATEMENT and LEAD marks, so the
    statement_scope row on the bile duct citation showed three passages without 'The pseudocyst was not drained.';
    e5628be56 showed both denials."""

    def test_d161_problem2_the_statement_marks_are_kept(self):
        inv, text = two_denials()
        for cited, line in (('P3 the pseudocyst drainage', DRAINAGE_LINES['pseudocyst']),
                            ('P4 the bile duct drainage', DRAINAGE_LINES['bile_duct'])):
            result = run(inv, text, [('43240', line)])
            p = proposal(result, '43240')
            source = p.support['source']
            with self.subTest(cited=cited, part='assess'):
                self.assertEqual(asked(p), ['statement_scope', 'target', 'target'])
            with self.subTest(cited=cited, part='marks'):  # 7.4's passages as given, then the hold's drainage's
                self.assertEqual([(item['text'], item.get(questions.STATEMENT), item.get(questions.LEAD))
                                  for item in source],
                                 [(H3_P5, 'E4', True), (DRAINAGE_LINES['pseudocyst'], None, True), (H3_P6, 'E5', True),
                                  (DRAINAGE_LINES['bile_duct'], None, None)])
            with self.subTest(cited=cited, part='row'):  # the statement_scope row shows both denials
                shown = [quoted for _, _, quoted in questions.question_passages(
                    SERVICES_STUB, 'gi.eus', 'statement_scope', p.evidence, p.support, text, {})]
                self.assertIn(H3_P5, shown)
                self.assertIn(H3_P6, shown)
