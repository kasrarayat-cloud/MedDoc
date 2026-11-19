"""The round 5f integration's own change (assess.py, the service questions), SYNTHETIC. Nothing is sent.

Two reviews of round 5f found a question that both earlier heads ask dropped through D89's suppression and D157 (3)'s
service slot. The integration reads both AFTER the member answers:
- review:egd6 problem 0: D157 (3)'s ``holding`` covered every proposal's question, so the whole act a bundling-identity
  question names (act_target) yielded its service slot. 43239 held act_target on the group lesion's biopsy beside the
  timed snare and the timed biopsy then asked the biopsy's question, and nobody asked the snare's, whose answer decides
  the missing 43251. ``holding`` is now the acts named by the question of a code held NOT DOCUMENTED (D157's title): its
  first clarification, 7.4's.
- review:eus6 problem 0: D89's ``asked`` was built from the proposals BEFORE the answers. When a member's answer to
  43240's target question excluded the code, its 7.4 question, the same words as the service question, left with it,
  and the act in doubt was asked about nowhere. ``asked`` is now the questions the proposals ask or a member answered (an
  excluded code keeps the questions its answers closed), so the act in doubt takes its slot again, as f9013e12e asks it.
  ``holding`` is still read from the proposals before the answers (recorded residual: a code held not documented that an
  answer to ANOTHER of its questions excludes keeps its acts yielding the slot; no input in the suites or the gate
  corpus reaches it).
Answers here take the engine path (assess's member_answers, a fingerprinted answer to the tree's own question, the
review's tools/verify_engine_answer.py). The read-time overlay never re-asks a service question, a recorded residual of
the integration entry. On these inputs c2e53f8e asks no service question and lists the act not covered."""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from studio.interpretation import assess
from studio.validation import questions
from tests import test_interpretation_r5_egd as e5
from tests import test_interpretation_r5c_egd as e5c
from tests.test_interpretation_events import proposal, run
from tests.test_interpretation_identity import a, tg
from tests.test_interpretation_r5e_eus import LATER_PFC, LATER_Q, two_drainages
from tests.test_interpretation_r5f_eus import drainage, drainages

at, tgt, event, lesion, report = e5.at, e5.tgt, e5.event, e5.lesion, e5.report
TIMED_SNARE = 'At that time, the polyps were removed with a cold snare.'
TIMED_TATTOO = 'At that time, the cecum was tattooed with India ink.'
G_BIOPSIED = 'In the gastric body three 3 to 5 mm sessile polyps were biopsied with cold forceps.'
C_BIOPSIED = 'In the rectum three 3 to 5 mm sessile polyps were biopsied with cold forceps.'
LATER = dict(time=a('current_encounter', 'Later', ['P3']))
LATER_GB = ('Later, EUS-guided transmural drainage of the gallbladder was performed from the duodenal bulb with a 15 mm '
            'lumen-apposing metal stent.')
GB_Q = 'Was the drainage (stent) at the gallbladder (“was performed”) done at this encounter?'


def snare_question(where: str) -> str:
    return (f'Was the snare removal (cold snare) of the three 3 to 5 mm sessile polyps in the {where} (“were removed”) '
            'done at this encounter?')


def service(result) -> list:
    return [(spec.fact, spec.question) for spec in result.clarifications if spec.scope == 'service']


def group(landmark: str, words: str) -> dict:
    item = lesion('L1', 'three 3 to 5 mm sessile polyps', landmark, words, '3 to 5 mm', ['P6', 'P7'])
    item['multiplicity'] = 'group'
    return item


def biopsy_and_snare(procedure, landmark: str) -> list:
    """The review's r2 shape: the group lesion biopsied (E2, P6), then 'At that time' snared (E3, P7)."""
    return [event('E2', procedure, at('biopsy', 'biopsied', ['P6']), status=at('performed', 'were biopsied', ['P6']),
                  technique=at('cold_forceps', 'cold forceps', ['P6']),
                  target=tgt('L1', landmark, 'three 3 to 5 mm sessile polyps', ['P6'])),
            event('E3', procedure, at('snare', 'removed with a cold snare', ['P7']),
                  status=at('performed', 'were removed', ['P7']), technique=at('cold_snare', 'cold snare', ['P7']),
                  target=tgt('L1', landmark, 'the polyps', ['P7']),
                  time=at('current_encounter', 'At that time', ['P7']))]


def r2b() -> str:
    """review:egd6's rv6_r2b_43239_act_target_names_the_timed_snare_then_timed_biopsy."""
    second = copy.deepcopy(e5c.TIMED_BIOPSY)
    second['id'] = 'E4'
    return e5.case('r5f_int_r2b', report(P5=e5.ADV, P6=G_BIOPSIED, P7=TIMED_SNARE, P8=e5c.TIMED_BIOPSY_LINE,
                                         P9=e5.NORMAL),
                   [e5.examination()] + biopsy_and_snare(e5.EGD, 'gastric_body') + [second],
                   [('43239', (G_BIOPSIED,))], lesions=[group('gastric_body', 'gastric body')])


def r2() -> str:
    """review:egd6's colonoscopy twin, rv6_r2_45380_act_target_names_the_timed_snare_then_timed_tattoo."""
    tattoo = event('E4', e5c.COLON, at('tattoo', 'tattooed', ['P8']), status=at('performed', 'was tattooed', ['P8']),
                   technique=at('injection', 'India ink', ['P8']), target=tgt('', 'cecum', 'the cecum', ['P8']),
                   time=at('current_encounter', 'At that time', ['P8']), purpose=at('marking', 'tattooed', ['P8']))
    return e5.case('r5f_int_r2', report('COLONOSCOPY REPORT', P5='The colonoscope was advanced to the cecum.',
                                        P6=C_BIOPSIED, P7=TIMED_SNARE, P8=TIMED_TATTOO),
                   [copy.deepcopy(e5c.COLON_EXAM)] + biopsy_and_snare(e5c.COLON, 'rectum') + [tattoo],
                   [('45380', (C_BIOPSIED,))], lesions=[group('rectum', 'rectum')], reach=('E1', 'cecum', 'cecum', 'P5'))


def later_gallbladder():
    """review:eus6's twin with a second act in doubt: S0_later_cbd plus the gallbladder drainage told 'Later' (E4)."""
    return drainages({'P2': 'A 9 cm pancreatic pseudocyst was seen abutting the posterior gastric wall.',
                      'P3': LATER_PFC,
                      'P4': 'EUS-guided transmural drainage of the common bile duct was performed from the duodenal '
                            'bulb with a 6 mm lumen-apposing metal stent.',
                      'P5': LATER_GB},
                     [drainage('E2', 'P3', tg('L1', 'pancreas', 'the pseudocyst', ['P3']), **LATER),
                      drainage('E3', 'P4', tg('', 'common_bile_duct', 'the common bile duct', ['P4'])),
                      drainage('E4', 'P5', tg('', 'gallbladder', 'the gallbladder', ['P5']),
                               time=a('current_encounter', 'Later', ['P5']))])


def with_answer(inv, text, picks, fact: str):
    """Re-assess with a member's 'cannot_confirm' answer to 43240's own ``fact`` question (fingerprinted)."""
    first = run(inv, text, picks)
    asked = assess._MemberAnswers((), text)._proposal_questions(first.proposals)
    key = questions.member_key('43240', 'gi.eus', fact)
    assert key in asked, (fact, sorted(asked))
    answer = questions.MemberAnswerInput(code='43240', family='gi.eus', fact=fact, value='cannot_confirm',
                                         question=asked[key], answer_id='m1')
    return run(inv, text, picks, member_answers=(answer,))


class TheServiceSlotYieldsOnlyToANotDocumentedQuestion(SimpleTestCase):
    """review:egd6 problem 0. f9013e12e and e5628be56 ask the snare's question on both inputs; round 5f's egd6 patch
    asked the timed biopsy's (r2b) or the tattoo's (r2); c2e53f8e asks none."""

    def test_r5f_int_a_bundling_identity_question_never_takes_the_snares_slot(self):
        for name, code, where in ((r2b(), '43239', 'gastric body'), (r2(), '45380', 'rectum')):
            result = e5.assessed(name)
            with self.subTest(case=name, part='the code'):
                p = proposal(result, code)
                self.assertEqual(([s.fact for s in p.clarifications], p.support['question_events'],
                                  p.support['reason'] == 'not_documented'), (['act_target'], ['E2', 'E3'], False))
            with self.subTest(case=name, part='service'):
                self.assertEqual(service(result), [('event_time', snare_question(where))])


class AskedAndHoldingAreReadAfterTheAnswers(SimpleTestCase):
    """review:eus6 problem 0, the engine path. f9013e12e asks the pseudocyst drainage's time at service scope with no
    answer and with each answer. The eus6 patch asked it nowhere once a target answer excluded 43240 (S0_later_cbd), or
    asked the gallbladder's beside it. e5628be56 and c2e53f8e ask no service question."""

    def test_r5f_int_a_target_answer_gives_the_act_its_question_back(self):
        inv, text = two_drainages(LATER_PFC, LATER)
        picks = [('43240', LATER_PFC)]
        with self.subTest(answer='none'):  # asked through 43240, word for word (D161): not twice
            self.assertEqual(service(run(inv, text, picks)), [])
        result = with_answer(inv, text, picks, 'target')
        with self.subTest(answer='target', part='the code'):
            self.assertEqual((proposal(result, '43240').bucket, [s.fact for s in proposal(result, '43240').clarifications]),
                             ('excluded', ['target', 'target']))
        with self.subTest(answer='target', part='service'):
            self.assertEqual(service(result), [('event_time', LATER_Q)])
        with self.subTest(answer='event_time'):  # the member answered that very question: never asked again
            self.assertEqual(service(with_answer(inv, text, picks, 'event_time')), [])

    def test_r5f_int_a_question_that_left_unanswered_holds_no_slot(self):
        """With a second act in doubt (the gallbladder drainage told 'Later'): with no answer the pseudocyst drainage's
        question is asked through 43240 word for word (D89), so the slot asks the gallbladder's; once a target answer
        excludes 43240, that question left with it unanswered, and its act takes the slot back in the reading's order
        (f9013e12e's question; 43240's hold is 'unverified', so ``holding`` names none of its acts). Answered itself,
        it stays asked, and the slot asks the gallbladder's."""
        inv, text = later_gallbladder()
        picks = [('43240', LATER_PFC)]
        for answer, expected in (('none', GB_Q), ('target', LATER_Q), ('event_time', GB_Q)):
            result = run(inv, text, picks) if answer == 'none' else with_answer(inv, text, picks, answer)
            with self.subTest(answer=answer):
                self.assertEqual(service(result), [('event_time', expected)])
