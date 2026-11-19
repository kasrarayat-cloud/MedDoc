"""Round 5e of the Gemini migration (narrowing only), the ERCP repair D155 (the review of D147: round5d
results-missing-reviews.json 'review:ercp4' problems 0 and 6, and the round-5d ercp4 builder's disagreements 2 and 5),
SYNTHETIC and REPLAYED: nothing is sent. Each pin is built from its source's own input - the reviewer's probe texts
and answers (finding 25's ERCP with the sweep's passage changed: tests.test_interpretation_r5_ercp.sweep) - or, where
named, this repair's own constructed variants.

- (1) D147 (3) is WITHDRAWN: D140's following-sentence condition is restored - the sentence after the act's own is read
  when it holds no other event's own words OR holds the words of an event that is not performed (a denial, an uncertain
  statement, a plan, an act begun and not completed), whatever performed events' words it also holds. Every input D147
  (3) released returns to e5628be56's hold.
- (2) A sentence after the act's own that is dropped as another act's is read for its DENIAL CLAUSE: a clause of it (cut
  at ercp.CLAUSE_BREAKS) that holds no other event's own words and, read with the act's own sentence, denies the
  retrieval or the stones' presence (ercp._denial) is the act's statement, whatever the sentence's other clauses hold.
  It only adds a hold.

The installed release c2e53f8e's outcome on each input (jobs._assess_child, as the head-to-head runs it, with no
participant and with Astra and Fable read: the same on every input here) is quoted in each pin's docstring, as are the
outcomes of e5628be56 and of 4f82e5056 (round 5d).
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import ercp, events
from tests.test_interpretation_events import proposal, run
from tests.test_interpretation_identity import a, sc, tg
from tests.test_interpretation_r4_ercp import PARTICIPANTS, ercp_act
from tests.test_interpretation_r5_ercp import held_nothing_retrieved, ready_on, sweep

SW = dict(kind_words='swept with an extraction balloon', status_words='was swept')
SWEPT_ONCE = 'The bile duct was swept with an extraction balloon.'


def assessed(p5: str, cited=None, participants=(), **options):
    """43264 on finding 25's ERCP (tests.test_interpretation_r5_ercp.sweep) with ``p5`` for the sweep (E4), Corti citing
    43262 at the sphincterotomy and 43264 at ``cited`` (default: the whole of P5)."""
    inv, text, doc = sweep(p5, **options)
    return proposal(run(inv, text, [('43262', doc['P4']), ('43264', cited or p5)], participants=participants), '43264')


def statement(p5: str, **options):
    """E4's statement that nothing was retrieved (ercp.nothing_retrieved, the inventory alone), as its texts; else
    None."""
    inv, text, doc = sweep(p5, **options)
    reading = events.Reading.of(inv)
    found = ercp.nothing_retrieved(reading, reading.events['E4'])
    return None if found is None else [place['text'] for place in found]


def held_in_both(test, p5: str, said: str, more, citations=(SWEPT_ONCE, None), **options) -> None:
    """43264 held with D106's question quoting ``said``, Corti citing each of ``citations`` (None: the whole passage),
    with no participant and with Astra and Fable read."""
    for cited in citations:
        for chosen in PARTICIPANTS:
            with test.subTest(p5=p5[len(SWEPT_ONCE):][:60], cited=bool(cited), participants=len(chosen)):
                held_nothing_retrieved(test, assessed(p5, cited, chosen, **dict(SW, **options), more=more), said)


def stent(eid='E5', kind_words='plastic biliary stent', status_words='was placed', **changes):
    return ercp_act(eid, 'P5', 'stent', kind_words, status_words, **changes)


def plan(eid='E6'):
    return ercp_act(eid, 'P5', 'examination', 'a repeat ERCP', 'is planned', status='planned',
                    time=a('future', 'is planned', ['P5']))


def denial(eid='E6', kind='other', words='No stones were retrieved'):
    """The denial Gemini files as its own not_performed event (prompt.py), its words the denial itself, its scope word
    the denial's first word."""
    return ercp_act(eid, 'P5', kind, words, words, status='not_performed',
                    scope=sc('single_target', words.split()[0], ['P5']))


def basket(status='were extracted', **changes):
    return ercp_act('E5', 'P5', 'stone_extraction', 'extracted', status, technique=a('basket', 'basket', ['P5']),
                    **changes)


def pancreatic_sweep():
    return ercp_act('E5', 'P5', 'stone_extraction', 'swept with a balloon', 'was then swept',
                    target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                    technique=a('balloon', 'balloon', ['P5']))


def pancreatic_stent():
    return stent(kind_words='5 Fr pancreatic stent', target=tg('', 'pancreatic_duct', 'pancreatic', ['P5']))


def earlier_extraction():
    """The review's earlier extraction at another hospital, filed as its own stone_extraction (E5) of an earlier
    encounter by another facility."""
    return ercp_act('E5', 'P5', 'stone_extraction', 'stone extraction', 'stone extraction',
                    time=a('earlier_encounter', 'in 2023', ['P5']),
                    performer=a('other_facility', 'another hospital', ['P5']))


BASKET_PLAN = ('The bile duct was swept with an extraction balloon. Two stones were extracted with a basket; no stones '
               'were seen on the final cholangiogram and a repeat ERCP is planned.')
THEN_PLAN = ('The bile duct was swept with an extraction balloon. Two stones were then extracted with a basket; no '
             'stones were seen on the final cholangiogram and a repeat ERCP is planned.')
BOTH = ('The bile duct was swept with an extraction balloon. The pancreatic duct was then swept with a balloon; no '
        'stones were retrieved.')
R1 = ('The bile duct was swept with an extraction balloon. No stones were retrieved, and a plastic biliary stent was '
      'placed.')
R2 = ('The bile duct was swept with an extraction balloon. No stones were retrieved; a plastic biliary stent was '
      'placed and a repeat ERCP is planned.')
R3 = ('The bile duct was swept with an extraction balloon. No stones were extracted, and a 5 Fr pancreatic stent was '
      'placed for prophylaxis.')
R4 = ('The bile duct was swept several times with an extraction balloon. No stones or sludge were retrieved; a plastic '
      'biliary stent was placed for drainage and a repeat ERCP is planned in 8 weeks.')
R4_FIRST = 'The bile duct was swept several times with an extraction balloon.'
R4_SWEEP = dict(kind_words='swept several times with an extraction balloon', status_words='was swept several times')
R6 = ('The bile duct was swept with an extraction balloon. No stones were retrieved; she had stone extraction at '
      'another hospital in 2023.')


# --- (1): D147 (3) withdrawn - D140's following-sentence condition restored -------------------------------------------

class D155Withdrawal(SimpleTestCase):
    def test_d155_withdrawal_d140s_control_with_the_denial_event_holds_again(self):
        """The round-5d ercp4 builder's disagreement 2 (a release D147 (3) introduced): D140's control, "The bile duct
        was swept with an extraction balloon. The pancreatic duct was then swept with a balloon; no stones were
        retrieved." with the pancreatic sweep (E5, performed) and the denial filed as its own event (E6, not_performed),
        Corti citing the sweep's sentence or the whole passage. The next sentence holds the not-performed denial's
        words, so it is read: 43264 held nothing_retrieved, the question quoting both sentences - as e5628be56 (held)
        and c2e53f8e (HELD readings_disagree with the sweep's sentence cited; EXCLUDED with the passage cited).
        4f82e5056: READY on E4."""
        held_in_both(self, BOTH, BOTH, [pancreatic_sweep(), denial(words='no stones were retrieved')])
        self.assertEqual(statement(BOTH, **SW, more=[pancreatic_sweep(), denial(words='no stones were retrieved')]),
                         [SWEPT_ONCE, BOTH[len(SWEPT_ONCE) + 1:]])

    def test_d155_withdrawal_the_basket_and_the_planned_repeat_ercp_return_to_held(self):
        """The round-5c review's problem 3 input 1 (review:ercp4 problem 2's): "The bile duct was swept with an
        extraction balloon. Two stones were extracted with a basket; no stones were seen on the final cholangiogram and
        a repeat ERCP is planned." with the basket (E5, performed) and the repeat ERCP (E6, planned), Corti citing the
        sweep's sentence or the whole passage, and the reviewer's "Two stones were then extracted" form. The next
        sentence holds the planned event's words, so it is read, and the basket's own sentence denies the stones'
        presence in a clause that holds the plan's words (D127's sentence of two acts): 43264 held nothing_retrieved,
        the question quoting both sentences, as at e5628be56. 4f82e5056: READY on E4 (D147 (3)). A RETURNING COST:
        c2e53f8e is READY with the sweep's sentence cited (on the basket act) and READY on the "then extracted" form;
        it HOLDS (readings_disagree) with the whole passage cited."""
        then_basket = basket('were then extracted', target=tg('', 'bile_duct', 'The bile duct', ['P5']))
        held_in_both(self, BASKET_PLAN, BASKET_PLAN, [basket(), plan()])
        held_in_both(self, THEN_PLAN, THEN_PLAN, [then_basket, plan()], citations=(SWEPT_ONCE,))
        inv, text, doc = sweep(BASKET_PLAN, **SW, more=[basket(), plan()])
        reading = events.Reading.of(inv)
        self.assertEqual(events.evaluate('43264', (), reading).read, ('E4', 'E5'))

    def test_d155_problem_0_inputs_with_a_denial_event_or_a_plan(self):
        """review:ercp4 problem 0 (critical, introduced by D147 (3)): the sentence after the sweep both denies the
        retrieval and names a performed act, beside a denial event or a planned event Gemini files for it - "No stones
        were retrieved, and a plastic biliary stent was placed." (the denial filed as other or removal), "No stones were
        retrieved; a plastic biliary stent was placed and a repeat ERCP is planned." (the plan; with and without the
        denial event too), "No stones were extracted, and a 5 Fr pancreatic stent was placed for prophylaxis." (the
        denial), finding 25's own wording "...No stones or sludge were retrieved; a plastic biliary stent was placed for
        drainage and a repeat ERCP is planned in 8 weeks." (the plan), and an earlier extraction at another hospital
        named in the denial sentence (the denial). Each, Corti citing the sweep's sentence or the whole passage, was
        READY on E4 at 4f82e5056; each is held nothing_retrieved, the question quoting both sentences, as at e5628be56.
        c2e53f8e HOLDS each (readings_disagree) with the sweep's sentence cited and EXCLUDES each with the passage
        cited."""
        for kind in ('other', 'removal'):
            held_in_both(self, R1, R1, [stent(), denial(kind=kind)])
        held_in_both(self, R2, R2, [stent(), plan()])
        held_in_both(self, R2, R2, [stent(), plan(), denial('E7')])
        held_in_both(self, R3, R3, [pancreatic_stent(), denial(words='No stones were extracted')])
        for cited in (R4_FIRST, None):
            for chosen in PARTICIPANTS:
                with self.subTest(p5='finding 25 with the stent and the plan', cited=bool(cited),
                                  participants=len(chosen)):
                    held_nothing_retrieved(self, assessed(R4, cited, chosen, **R4_SWEEP, more=[stent(), plan()]), R4)
        held_in_both(self, R6, R6, [earlier_extraction(), denial()])


# --- (2): the denial clause of a sentence dropped as another act's ----------------------------------------------------

class D155DenialClause(SimpleTestCase):
    def test_d155_problem_6_the_denial_clause_of_a_sentence_dropped_as_another_acts(self):
        """review:ercp4 problem 6 (pre-existing, critical by the rubric): "The bile duct was swept with an extraction
        balloon. No stones were retrieved, and a plastic biliary stent was placed." with only the stent filed (E5,
        performed). The next sentence holds the stent's words and no not-performed event's, so D140 drops it; its
        clause "No stones were retrieved" holds no other event's words and denies the retrieval, so it is the sweep's
        statement: 43264 held nothing_retrieved, the question quoting the sweep's sentence and that clause, Corti
        citing the sweep's sentence or the whole passage. It was READY on E4 at e5628be56 and at 4f82e5056; c2e53f8e
        HOLDS it (readings_disagree) with the sweep's sentence cited and EXCLUDES it with the passage cited."""
        held_in_both(self, R1, f'{SWEPT_ONCE} No stones were retrieved', [stent()])
        self.assertEqual(statement(R1, **SW, more=[stent()]), [SWEPT_ONCE, 'No stones were retrieved'])

    def test_d155_problem_0_inputs_without_a_denial_event(self):
        """review:ercp4 problem 0's inputs with no denial event (and no plan) filed - only the performed act Gemini
        files for the next sentence: the plastic biliary stent of "No stones were retrieved; a plastic biliary stent was
        placed and a repeat ERCP is planned.", the pancreatic stent of "No stones were extracted, and a 5 Fr pancreatic
        stent was placed for prophylaxis.", finding 25's own wording with the stent, and the earlier extraction at
        another hospital of "No stones were retrieved; she had stone extraction at another hospital in 2023." (the
        reviewer's own pre-existing check with the sweep's sentence cited; the rest are this repair's variants,
        constructed). Each is held nothing_retrieved, the question quoting the sweep's sentence
        and the denial clause, Corti citing the sweep's sentence or the whole passage. Each was READY on E4 at e5628be56
        and at 4f82e5056; c2e53f8e HOLDS each (readings_disagree) with the sweep's sentence cited and EXCLUDES each with
        the passage cited."""
        held_in_both(self, R2, f'{SWEPT_ONCE} No stones were retrieved', [stent()])
        held_in_both(self, R3, f'{SWEPT_ONCE} No stones were extracted', [pancreatic_stent()])
        for cited in (R4_FIRST, None):
            for chosen in PARTICIPANTS:
                with self.subTest(p5='finding 25 with the stent only', cited=bool(cited), participants=len(chosen)):
                    held_nothing_retrieved(self, assessed(R4, cited, chosen, **R4_SWEEP, more=[stent()]),
                                           f'{R4_FIRST} No stones or sludge were retrieved')
        held_in_both(self, R6, f'{SWEPT_ONCE} No stones were retrieved', [earlier_extraction()])

    def test_d155_the_denial_clause_wherever_it_stands(self):
        """This repair's own variants (constructed), only the performed act filed, Corti citing the sweep's sentence:
        "No stones were retrieved; a plastic biliary stent was placed." and "Nothing was retrieved, and ..." (c2e53f8e
        HELD readings_disagree; HELD act_missing), a presence denial "No stones were seen, and ..." and "No stones were
        seen on the final cholangiogram, and ..." (HELD act_missing), the denial after the stent's clause "A plastic
        biliary stent was placed; no stones were retrieved." (HELD readings_disagree), and the next sentence on its own
        line, a passage of its own (HELD readings_disagree). D127's own two-act shape, the pancreatic duct's sweep (E5)
        and "; no stones were retrieved" with no denial event, Corti citing the whole passage (c2e53f8e EXCLUDED; its
        sweep's-sentence citation is D127's pin, tests.test_interpretation_r5_ercp). Each was READY on E4 at e5628be56
        and at 4f82e5056, and each is held nothing_retrieved, the question quoting the sweep's sentence and the
        clause."""
        shapes = {
            'No stones were retrieved; a plastic biliary stent was placed.': 'No stones were retrieved',
            'Nothing was retrieved, and a plastic biliary stent was placed.': 'Nothing was retrieved',
            'No stones were seen, and a plastic biliary stent was placed.': 'No stones were seen',
            'No stones were seen on the final cholangiogram, and a plastic biliary stent was placed.':
                'No stones were seen on the final cholangiogram',
            'A plastic biliary stent was placed; no stones were retrieved.': 'no stones were retrieved',
        }
        for second, clause in shapes.items():
            held_in_both(self, f'{SWEPT_ONCE} {second}', f'{SWEPT_ONCE} {clause}', [stent()], citations=(SWEPT_ONCE,))
        for chosen in PARTICIPANTS:
            with self.subTest(shape='its own line', participants=len(chosen)):
                p = assessed(SWEPT_ONCE, None, chosen, **SW,
                             more_lines={'P6': 'No stones were retrieved, and a plastic biliary stent was placed.'},
                             more=[ercp_act('E5', 'P6', 'stent', 'plastic biliary stent', 'was placed')])
                held_nothing_retrieved(self, p, f'{SWEPT_ONCE} No stones were retrieved')
        held_in_both(self, BOTH, f'{SWEPT_ONCE} no stones were retrieved', [pancreatic_sweep()], citations=(None,))

    def test_d155_another_act_that_supports_43264_keeps_it(self):
        """The hold is the act's, not the code's: where another act supports 43264, the code keeps READY on that act and
        the sweep leaves E* (the decision still reads it). This repair's own inputs (constructed): "The bile duct was
        swept with an extraction balloon. Two stones were extracted with a basket; no stones were seen on the final
        cholangiogram." with the basket filed (E5, performed), Corti citing the sweep's sentence or the passage, and the
        same with ", and no stones remained." - READY on E5 (c2e53f8e READY; e5628be56 and 4f82e5056 READY on E4 and
        E5). A COST, recorded: the "Two stones were then extracted" form with no plan - D140's subject rule reads no
        yield across "then", so the basket's own sentence denies the stones' presence with no yield of its own, and
        both acts state that nothing was retrieved: held nothing_retrieved (c2e53f8e READY; e5628be56 and 4f82e5056
        READY on E4)."""
        seen = ('The bile duct was swept with an extraction balloon. Two stones were extracted with a basket; no '
                'stones were seen on the final cholangiogram.')
        remained = ('The bile duct was swept with an extraction balloon. Two stones were extracted with a basket, and '
                    'no stones remained.')
        for p5, cited in ((seen, SWEPT_ONCE), (seen, None), (remained, SWEPT_ONCE)):
            for chosen in PARTICIPANTS:
                with self.subTest(p5=p5[len(SWEPT_ONCE):][:60], cited=bool(cited), participants=len(chosen)):
                    ready_on(self, assessed(p5, cited, chosen, **SW, more=[basket()]), ('E5',))
        inv, text, doc = sweep(seen, **SW, more=[basket()])
        reading = events.Reading.of(inv)
        self.assertEqual(events.evaluate('43264', (), reading).read, ('E4', 'E5'))
        then = ('The bile duct was swept with an extraction balloon. Two stones were then extracted with a basket; no '
                'stones were seen on the final cholangiogram.')
        then_basket = basket('were then extracted', target=tg('', 'bile_duct', 'The bile duct', ['P5']))
        held_in_both(self, then, f'{SWEPT_ONCE} no stones were seen on the final cholangiogram', [then_basket],
                     citations=(SWEPT_ONCE,))

    def test_d155_the_clause_reading_reads_clauses_and_denials_only(self):
        """The reader (ercp.nothing_retrieved, the inventory alone), only the stent filed after the sweep's sentence.
        Controls, no denial in the dropped sentence's free clauses: "A plastic biliary stent was placed.", "A plastic
        biliary stent was placed, and sludge was retrieved." and the exceptive "No further stones were seen, and a
        plastic biliary stent was placed." state nothing (as at e5628be56 and 4f82e5056). D155 built clause-level
        ownership only, so "No stones were retrieved and a plastic biliary stent was placed." (no clause break) and "A
        plastic biliary stent was placed because no stones were retrieved." (one clause that holds the stent's own
        words) stated nothing of the sweep's: its RECORDED RESIDUAL, 43264 READY on E4 where c2e53f8e HOLDS
        (readings_disagree). DECISIONS D168 (1) (round 5g; D159's rule (1), rebuilt) closes it - where D155's reading
        states nothing, a clause of the dropped sentence that holds another event's own words is read too - so this
        pin's expectation for those two shapes CHANGED: each is now the sweep's statement, the clause quoted whole
        (pinned in tests.test_interpretation_r5g_ercp). The denial is read with the act's own sentence: the sweep's
        "extraction balloon" is the retrieval word a presence denial needs ("No stones were seen, and ...")."""
        for second in ('A plastic biliary stent was placed.',
                       'A plastic biliary stent was placed, and sludge was retrieved.',
                       'No further stones were seen, and a plastic biliary stent was placed.'):
            with self.subTest(second=second):
                self.assertIsNone(statement(f'{SWEPT_ONCE} {second}', **SW, more=[stent()]))
        for second in ('No stones were retrieved and a plastic biliary stent was placed.',
                       'A plastic biliary stent was placed because no stones were retrieved.'):
            with self.subTest(second=second):  # DECISIONS D168 (1): changed from None
                self.assertEqual(statement(f'{SWEPT_ONCE} {second}', **SW, more=[stent()]), [SWEPT_ONCE, second[:-1]])
        self.assertEqual(statement(f'{SWEPT_ONCE} No stones were seen, and a plastic biliary stent was placed.', **SW,
                                   more=[stent()]), [SWEPT_ONCE, 'No stones were seen'])
