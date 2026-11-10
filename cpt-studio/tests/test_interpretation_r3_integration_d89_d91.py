"""DECISIONS D89 and D91 (the integration of the Gemini migration's round 3, 732d172d2), pinned from the inputs the
independent reviewers of round 3 reproduced on the commit before it (62d5bf0dd).

- D89 (reviews of D75 and D86): a merged unresolved item keeps every in_doubt event's question, and a code's question
  suppresses a service question only when it is the same question - its fact and its words, which name the act; the
  same fact about another act is still asked. Two reviewer inputs:
  - the CLAIMS-BASE review's DROPPED GENUINE QUESTION: an EGD and a colonoscopy, 45378 proposed alone; the antrum
    biopsies E2 ("Cold forceps biopsies were taken from the gastric antrum.", procedure 'egd' with no words:
    procedure_unsettled) and the body biopsies E3 ("Earlier that day, cold forceps biopsies were taken from the gastric
    body.", its current time unverified: other_occasion) are one in_doubt item per (session, act kind). Kept only for the
    item that survived the merge, the act listed first took the other's service question: E2 first asked E2's procedure
    alone, E3 first E3's "done at this encounter?" alone. Both are asked, in either listing order.
  - the QUESTIONS review's "Break": the colonoscopy and the sigmoid snare 45385 cites; "No polypectomy was performed in
    the prior segment." (UNRESOLVED(target) on the snare, so 45385 asks statement_scope, D86); "Rectal biopsies were taken
    with cold forceps." (a biopsy whose status words do not bind: in_doubt, read by no code); "Biopsies were not taken."
    (UNRESOLVED(scope) on that biopsy). The service statement_scope question about the biopsy shared (family, fact) with
    45385's own and was dropped; it is asked beside it. The boundary is pinned too: the same question (fact and words)
    still suppresses the service question.
- D91 (review of D86): D86 - an UNRESOLVED relation whose statement is a denial asks statement_scope - reaches only a
  TARGET relation; any other attribute keeps the question of the attribute (events.RELATION_FACTS):
  - the QUESTIONS review's historical denial: the snare's time unknown beside "History: No polypectomy was performed in
    2024." (verified earlier_encounter), an UNRESOLVED(time) relation. 45385 asks the act's own time (event_time), never
    whether the 2024 denial applies;
  - the two recorded rows the same review's FRESH-2 re-score moved (C1CL2-002 r1 and C2CL-008 r1 45385, an
    UNRESOLVED(status) relation): performed_status, a question the registry's expectation names (conflict:snare or
    performed_status), not statement_scope.

RECORDED: the committed FRESH-2 run 1 of each row (tests/fixtures/interpretation; byte-equal to the frozen r1.body), read
and assessed as score_fresh.py does (test_interpretation_r3_questions.recorded), with the registry's own citations.
SYNTHETIC: the shared S08 builders (tests.test_interpretation_events, tests.test_interpretation_identity), fictional
documents. Nothing is sent."""
from __future__ import annotations

from unittest import mock

from django.test import SimpleTestCase

from studio.interpretation import coverage, events
from tests.test_interpretation_events import POLYP, asked, colonoscopy, exam, inventory, proposal, reached, removed, run
from tests.test_interpretation_identity import a, act, sc, tg
from tests.test_interpretation_r3_questions import recorded, sources, unresolved

# --- D89 (a): the claims-base review's input --------------------------------------------------------------------------

GASTRIC = {'G1': 'EGD: the gastroscope was advanced to the second portion of the duodenum.',
           'G2': 'Cold forceps biopsies were taken from the gastric antrum.',
           'G3': 'Earlier that day, cold forceps biopsies were taken from the gastric body.',
           'P1': 'Colonoscopy: The colonoscope was advanced to the cecum.'}
ANTRUM_PROCEDURE = 'In which procedure was the forceps biopsy (cold forceps) at the gastric antrum (“were taken”) done?'
BODY_TIME = 'Was the forceps biopsy (cold forceps) at the gastric body (“were taken”) done at this encounter?'


def two_gastric_biopsies(first: str) -> tuple:
    """The claims-base review's input (its probes/p2_question_swap.py): an EGD to the second portion of the duodenum (E1)
    and a colonoscopy to the cecum (E4); the antrum biopsies E2, whose procedure 'egd' cites no words (unsettled between
    the two current families), and the body biopsies E3, "Earlier that day" (other_occasion). ``first``: 'E2' or 'E3',
    the biopsy listed first."""
    antrum = act('E2', 'G2', 'biopsy', 'biopsies', status_words='were taken', procedure=a('egd'),
                 technique=a('cold_forceps', 'cold forceps', ['G2']),
                 target=tg('', 'gastric_antrum', 'gastric antrum', ['G2']))
    body = act('E3', 'G3', 'biopsy', 'biopsies', status_words='were taken', procedure=a('egd', 'EGD', ['G1']),
               technique=a('cold_forceps', 'cold forceps', ['G3']), target=tg('', 'gastric_body', 'gastric body', ['G3']),
               time=a('current_encounter', 'Earlier that day', ['G3']))
    biopsies = [antrum, body] if first == 'E2' else [body, antrum]
    return inventory(GASTRIC,
                     events=[exam('E1', 'G1', words='gastroscope', procedure=a('egd', 'EGD', ['G1'])), *biopsies,
                             exam('E4', 'P1', words='colonoscope', procedure=a('colonoscopy', 'Colonoscopy', ['P1']))],
                     reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'G1'),
                            reached('E4', 'cecum', 'cecum', 'P1')])


class D89MergedItemKeepsEveryQuestion(SimpleTestCase):
    """coverage.reconcile: every in_doubt event of a merged item keeps its question (the claims-base review)."""

    def test_d89_both_biopsies_keep_their_service_question_in_either_listing_order(self):
        for first, listed in (('E2', ['E2', 'E3']), ('E3', ['E3', 'E2'])):
            with self.subTest(listed_first=first):
                inv, text = two_gastric_biopsies(first)
                reading = events.Reading.of(inv)
                antrum, body = reading.events['E2'], reading.events['E3']
                # the two doubts the review names, each a different fact: E2's procedure, E3's time
                self.assertEqual((antrum['procedure']['state'], antrum['procedure']['reasons']),
                                 ('unverified', ['procedure_unsettled']))
                self.assertEqual((body['time']['state'], body['time']['reasons']), ('unverified', ['other_occasion']))
                self.assertTrue(coverage.doubted(reading, antrum))
                self.assertTrue(coverage.doubted(reading, body))
                result = run(inv, text, [('45378', GASTRIC['P1'])])
                p = proposal(result, '45378')
                self.assertEqual((p.status, asked(p)), ('ready', []))  # no code asks anything, so nothing suppresses
                # the merge D89 reads through: one in_doubt item per (session, act kind), both biopsies in it
                self.assertEqual([(item['service'], item['act'], item['events'])
                                  for item in result.completeness['unresolved_items'] if item['reason'] == 'in_doubt'],
                                 [('gi.egd', 'biopsy', listed)])
                self.assertEqual(sorted((c.scope, c.family, c.fact, c.question) for c in result.clarifications),
                                 sorted([('service', 'gi.egd', 'procedure', ANTRUM_PROCEDURE),
                                         ('service', 'gi.egd', 'event_time', BODY_TIME)]))
                self.assertIn('2 open questions', result.completeness['reasons'])


# --- D89 (b): the questions review's input ----------------------------------------------------------------------------

PRIOR = 'No polypectomy was performed in the prior segment.'
RECTAL = 'Rectal biopsies were taken with cold forceps.'
NOT_TAKEN = 'Biopsies were not taken.'
SNARE_SCOPE = ('Does “No polypectomy was performed” apply to the snare removal (cold snare) of the 6 mm sessile polyp in '
               'the sigmoid colon (“was removed with a cold snare”)?')
BIOPSY_SCOPE = 'Does “were not taken” apply to the forceps biopsy (cold forceps) at the rectum (“biopsies”)?'


def prior_segment_and_rectal_biopsies() -> tuple:
    """The questions review's input (its tools/probe_dedup2.py), over the colonoscopy to the cecum (E1) and the sigmoid
    snare (E2, POLYP): the prior-segment denial E3, whose target the sigmoid colon its words ("the prior segment") never
    name; the rectal biopsies E4, whose status words ('were obtained') are not in the document; and the denial E5
    ("Biopsies were not taken.", all_of_kind 'Biopsies')."""
    denial = act('E3', 'P3', 'removal', 'polypectomy', status='not_performed',
                 status_words='No polypectomy was performed',
                 scope=sc('single_target', 'No polypectomy was performed in the prior segment', ['P3']),
                 target=tg('', 'sigmoid_colon', 'the prior segment', ['P3']))
    biopsy = act('E4', 'P4', 'biopsy', 'biopsies', status_words='were obtained',
                 technique=a('cold_forceps', 'cold forceps', ['P4']), target=tg('', 'rectum', 'Rectal', ['P4']))
    no_biopsy = act('E5', 'P5', 'biopsy', 'Biopsies', status='not_performed', status_words='were not taken',
                    scope=sc('all_of_kind', 'Biopsies', ['P5']))
    return colonoscopy(denial, biopsy, no_biopsy, lines={'P3': PRIOR, 'P4': RECTAL, 'P5': NOT_TAKEN})


class D89SameFactAnotherAct(SimpleTestCase):
    """coverage.in_doubt_questions: a code's question suppresses a service question only when it is the same question
    (the questions review)."""

    def test_d89_the_biopsy_denials_service_question_is_asked_beside_45385s_own_statement_scope(self):
        inv, text = prior_segment_and_rectal_biopsies()
        self.assertEqual(unresolved(inv), [('E3', 'E2', 'target', 'site_unresolved', 'not_performed'),
                                           ('E5', 'E4', 'scope', 'scope_unresolved', 'not_performed')])
        status = events.Reading.of(inv).events['E4']['status']
        self.assertEqual((status['state'], status['reasons']), ('unverified', ['words_unlocated']))
        result = run(inv, text, [('45385', POLYP)])
        p = proposal(result, '45385')
        # the code asks statement_scope of its snare (D86 on a target relation): the service question's (family, fact)
        self.assertEqual((p.status, [(c.family, c.fact, c.question) for c in p.clarifications], p.support['reason']),
                         ('needs_clarification', [('gi.colonoscopy', 'statement_scope', SNARE_SCOPE)], events.UNRESOLVED))
        self.assertEqual([(item['service'], item['act'], item['reason'], item['events'])
                          for item in result.completeness['unresolved_items']],
                         [('gi.colonoscopy', 'biopsy', 'in_doubt', ['E4'])])
        self.assertEqual([(c.scope, c.family, c.fact, c.question) for c in result.clarifications],
                         [('service', 'gi.colonoscopy', 'statement_scope', BIOPSY_SCOPE)])
        self.assertIn('2 open questions', result.completeness['reasons'])

    def test_d89_only_the_same_question_its_fact_and_its_words_suppresses_a_service_question(self):
        # the boundary, on the same reading and coverage: assess's one call of in_doubt_questions, then the same call
        # with a code's question that IS the service question
        inv, text = prior_segment_and_rectal_biopsies()
        with mock.patch.object(coverage, 'in_doubt_questions', wraps=coverage.in_doubt_questions) as spy:
            run(inv, text, [('45385', POLYP)])
        self.assertEqual(spy.call_count, 1)
        reading, final, codes_asked = spy.call_args.args
        # what assess hands it: (family, fact, question) of every proposal's question
        self.assertEqual(set(codes_asked), {('gi.colonoscopy', 'statement_scope', SNARE_SCOPE)})

        def service(given) -> list:
            return [(c.family, c.fact, c.question) for c in coverage.in_doubt_questions(reading, final, given)]

        same = ('gi.colonoscopy', 'statement_scope', BIOPSY_SCOPE)
        self.assertEqual(service(codes_asked), [same])  # the same fact about another act: asked
        self.assertEqual(service(set(codes_asked) | {same}), [])  # the same question: never asked twice
        self.assertEqual(service({same}), [])


# --- D91: the questions review's historical denial, and the recorded rows ---------------------------------------------

HISTORY = 'History: No polypectomy was performed in 2024.'
SNARE_TIME = ('Was the snare removal (cold snare) of the 6 mm sessile polyp in the sigmoid colon (“was removed with a cold '
              'snare”) done at this encounter?')
DATE_OF_SERVICE = ('Was the snare removal (cold snare) of the A 6 mm polyp in the sigmoid colon (“was removed”) done on the '
                   'date of service?')


class D91OnlyATargetRelation(SimpleTestCase):
    """events._h3_unresolved: a denial's UNRESOLVED relation asks statement_scope only when it rests on the target."""

    def test_d91_a_verified_2024_denial_leaves_the_snare_its_own_time_question(self):
        # the questions review's input (its tools/probe_time.py)
        history = act('E3', 'P3', 'removal', 'polypectomy', status='not_performed',
                      status_words='No polypectomy was performed', scope=sc('all_of_kind', 'No polypectomy', ['P3']),
                      time=a('earlier_encounter', 'in 2024', ['P3']))
        inv, text = colonoscopy(history, lines={'P3': HISTORY}, polyp=removed(time=a('unknown')))
        found = {item['id']: item for item in inv.events['events']}
        self.assertEqual((found['E2']['time']['value'], found['E2']['time']['state']), ('unknown', 'absent'))
        status, time = found['E3']['status'], found['E3']['time']
        # a denial by both of D86's arms (not_performed; a negator in its own words), verified as 2024's
        self.assertEqual((status['value'], status['state'], status['literals']),
                         ('not_performed', 'verified', {'negators': ['no']}))
        self.assertEqual((time['value'], time['state']), ('earlier_encounter', 'verified'))
        self.assertEqual(unresolved(inv), [('E3', 'E2', 'time', 'time_unresolved', 'not_performed')])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual((p.status, [(c.fact, c.question) for c in p.clarifications], p.support['reason']),
                         ('needs_clarification', [('event_time', SNARE_TIME)], events.UNRESOLVED))
        self.assertEqual(p.support['question_events'], ['E2', 'E3'])
        # the review's control: without the History line, the same code asks the same question of the same unknown
        inv, text = colonoscopy(polyp=removed(time=a('unknown')))
        self.assertEqual(unresolved(inv), [])
        p = proposal(run(inv, text, [('45385', POLYP)]), '45385')
        self.assertEqual((p.status, [(c.fact, c.question) for c in p.clarifications], p.support['reason']),
                         ('needs_clarification', [('event_time', SNARE_TIME)], events.UNVERIFIED))

    def assert_keeps_performed_status(self, item_id: str, statement: str, denial: list):
        """The recorded row's 45385 rests on UNRESOLVED(status) from ``statement`` (Gemini claimed the contradiction and
        opened both statuses) and asks performed_status, which the registry's expectation names; the denial's lines are
        shown; 45380, which nothing denies, is READY. Citations: registry-C's for both rows."""
        inventory, result = recorded(item_id, [('45380', 'Biopsies were taken from the rectum', 306),
                                               ('45385', 'was removed with a cold snare', 275)])
        self.assertEqual(unresolved(inventory), [(statement, 'E2', 'status', 'status_unresolved', 'not_performed')])
        p = proposal(result, '45385')
        self.assertEqual((p.bucket, p.status, [(c.fact, c.question) for c in p.clarifications], p.support['reason']),
                         ('selected', 'needs_clarification', [('performed_status', DATE_OF_SERVICE)], events.UNRESOLVED))
        for line in denial:
            self.assertIn(line, sources(p))
        self.assertEqual(proposal(result, '45380').status, 'ready')

    def test_d91_c1cl2_002_r1_45385_keeps_performed_status(self):
        self.assert_keeps_performed_status('C1CL2-002', 'E4',
                                           ['No polypectomy was performed on the polyp noted previously.'])

    def test_d91_c2cl_008_r1_45385_keeps_performed_status(self):
        self.assert_keeps_performed_status('C2CL-008', 'E5', ['No polypectomy was performed in 2024.',
                                                              'This was also the case on this occasion.'])
