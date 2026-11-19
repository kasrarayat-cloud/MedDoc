"""Round 5h of the Gemini migration (narrowing only), the ERCP repair D173 (refute6 families findings 7 and 8, judges
findings 8 and 9; round 5g's review:ercp7 problems 0-2), SYNTHETIC and REPLAYED: nothing is sent. Each pin is built from
its source's own input - the refute6 ercp lens's case files (refute6/ercp/cases/c01-c05: finding 25's ERCP with the
sweep's line changed, tests.test_interpretation_r5_ercp.sweep), the gate-ercp lens's (refute6/gate-ercp/cases: x1c, x1,
x4, x3, x2, s1, s2), review:ercp7's generated rows (round5g/review-ercp7/cases/gen.json) - or, where named, this
repair's own constructed variants (round5h/ercp8/cases2/own.json).

- (1) D168's whose-denial condition covers D155's own arm, for the acts of a code still READY (E*) only: a rival's
  denial clause never takes out of E* a sweep whose own sentence states its yield; the hold is decided as before.
- (2) D159's rule (3) reads a later sentence after a rival's sentence: only a sentence that itself holds a rival's own
  words is the rival's.
- (3), (4), (6) 43264 never stands on acts that state no yield: no act of its E* states a stone yield of its own or is
  done to a finding the inventory lists (with no statement of its own that nothing was retrieved) - held.
- (4) the yield across an appositive ("Three stones, the largest 9 mm, were extracted") is read only for whose a denial
  is and for whether an act E* keeps states a yield, never as a clearance of D106's hold.
- (5) a READY 43276 whose every exchange is named only in a title, apart from the sentence that states it done, with no
  stent removal or placement D105 pairs beside it, is held [performed_status].
- (7) a yield whose clause holds another occasion's time words (another event's, the time reader's) is no yield.

The installed release c2e53f8e's outcome on each input (jobs._assess_child, as the head-to-head runs it, with no
participant and with Astra and Fable read: the same in both settings unless quoted apart) and the outcomes of e5628be56
(round 5c), f9013e12e (round 5e) and 1b4ca399 (round 5g, the base) are quoted in each pin's docstring
(round5h/ercp8/out2/, census2/).
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import ercp, events
from tests.test_interpretation_events import asked, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, les, tg
from tests.test_interpretation_r4_ercp import EXCHANGE, PARTICIPANTS, ercp_act
from tests.test_interpretation_r5_ercp import SWEEP, duodenoscope, held_nothing_retrieved, ready_on, sweep
from tests.test_interpretation_r5g_ercp import REMOVED, SW, SWEPT_ONCE, stent

SPHINCTEROTOMY = SWEEP['P4']
FB13 = 'Three stones, the largest 9 mm, were extracted from the bile duct with an extraction balloon.'
FB13_WORDS = dict(kind_words='were extracted', status_words='were extracted',
                  target=('bile_duct', 'Three stones, the largest 9 mm, were extracted from the bile duct'))
CLEARED = ('The bile duct was swept with an extraction balloon and several small stones were removed; no stones '
           'remained on the final cholangiogram.')


def proposals(p5: str, cited=None, participants=(), more=(), codes=(), **options):
    """The 43264 proposal on finding 25's ERCP with ``p5`` for the sweep's line (E4), Corti citing 43262 at the
    sphincterotomy and 43264 at ``cited`` (default: the whole of P5)."""
    inv, text, doc = sweep(p5, more=list(more), **options)
    return proposal(run(inv, text, [('43262', doc['P4']), ('43264', cited or p5), *codes], participants=participants),
                    '43264')


def every(cites=(None,)):
    return [(cited, chosen) for cited in cites for chosen in PARTICIPANTS]


def held_no_yield(test, p, question_events) -> None:
    """``p`` (43264) held with D173's NO_YIELD performed_status question naming ``question_events``: never READY, never
    excluded."""
    test.assertEqual((p.bucket, p.status, asked(p), p.support['reason'], p.support['acts'],
                      p.support.get('question_events')),
                     ('selected', 'needs_clarification', ['performed_status'], ercp.NO_YIELD, [],
                      list(question_events)))
    test.assertTrue(p.clarifications[0].question.startswith('Was any stone, calculus, debris or sludge removed with '),
                    p.clarifications[0].question)
    test.assertIn('states no stone, calculus, debris or sludge removed', p.clarifications[0].reason)


def rival(duct=('pancreatic_duct', 'The pancreatic duct'), words='swept with a balloon', status='was then swept',
          device=('balloon', 'balloon'), passage='P5', lesion=''):
    """The second performed stone extraction (E5) of the refute6 ercp lens's cases (c01's second(), c02's basket())."""
    return ercp_act('E5', passage, 'stone_extraction', words, status, target=tg(lesion, duct[0], duct[1], [passage]),
                    technique=a(device[0], device[1], [passage]))


def reading_of(p5: str, **options):
    inv, text, doc = sweep(p5, **options)
    return events.Reading.of(inv)


# --- (1) whose denial, for E*: a rival's denial clause never sets apart the sweep that removed the stones ------------

WA = {  # refute6 families finding 7 (refute6/ercp/cases/c01_wrong_act_dropped_denial_clause.py, c03_wrong_act_lines.py)
    'WA1': (f'{REMOVED} The pancreatic duct was then swept with a balloon; no stones were seen.', rival(), REMOVED),
    'WA2': (f'{REMOVED} The pancreatic duct was then swept with a balloon, and no stones were seen.', rival(), REMOVED),
    'WA3': (f'{REMOVED} The duct was then swept with a basket; no stones were seen.',
            rival(('bile_duct', 'The duct'), 'swept with a basket', device=('basket', 'basket')), REMOVED),
    'WA4': (f'{REMOVED} The duct was then swept with a basket; no stones remained.',
            rival(('bile_duct', 'The duct'), 'swept with a basket', device=('basket', 'basket')), REMOVED),
    'WA5': ('The bile duct was swept with an extraction balloon and sludge was removed. The pancreatic duct was then '
            'swept with a basket; no stones were seen.',
            rival(words='swept with a basket', device=('basket', 'basket')),
            'The bile duct was swept with an extraction balloon and sludge was removed.'),
    'WA6': (f'{REMOVED} A final sweep with a basket was performed; no stones were seen.',
            rival(('not_stated', ''), 'final sweep with a basket', 'was performed', ('basket', 'basket')), REMOVED),
}


class D173WhoseDenial(SimpleTestCase):
    def test_d173_1_a_rivals_denial_clause_never_sets_apart_the_sweep_that_removed_the_stones(self):
        """refute6 families finding 7 (high; constructed, on contract): "The bile duct was swept with an extraction
        balloon and two stones were removed. The pancreatic duct was then swept with a balloon; no stones were seen."
        (E4 the bile-duct sweep, status 'was swept'; E5 the pancreatic sweep, a performed stone extraction), and its
        members WA2-WA6 (', and', the duct swept again with a basket, 'none remained', sludge, a final basket sweep)
        and the lines layout (WA-L2, the pancreatic sweep on its own line). D155 (2) read the pancreatic sweep's free
        denial clause as E4's statement, so 43264 was READY on E5 ALONE at f9013e12e and 1b4ca399 (the act that
        retrieved nothing; 'stone removal (balloon) at the pancreatic duct'). Now D168's whose-denial condition covers
        D155's arm for E*: E4's own sentence states its yield (_clause_yield), so the denial is E5's - READY on E4 and
        E5, as at e5628be56 (ACTS-ADDED, e5628be56's acts), both citations, both settings. c2e53f8e READY on the
        sweep's act (S1-A3) for WA1, WA2 and WA-L2, and on both acts for WA3-WA6. The reader: for E* (``whose``,
        ``widened`` False) E4 states nothing; for the hold, D155's reading is unchanged (the clause is E4's statement
        there, and E5 still supports the code)."""
        for name, (p5, second, own) in WA.items():
            for cited, chosen in every((own, None)):
                with self.subTest(wa=name, cited=bool(cited), participants=len(chosen)):
                    ready_on(self, proposals(p5, cited, chosen, [second], **SW), ('E4', 'E5'))
            reading = reading_of(p5, more=[second], **SW)
            with self.subTest(reader=name):
                self.assertIsNone(ercp.nothing_retrieved(reading, reading.events['E4'], (), ('E4', 'E5'),
                                                         widened=False, whose=True))
                self.assertIsNotNone(ercp.nothing_retrieved(reading, reading.events['E4'], (), ('E4', 'E5'),
                                                            widened=False))
        lines = rival(passage='P6')
        for chosen in PARTICIPANTS:
            with self.subTest(wa='WA-L2', participants=len(chosen)):
                ready_on(self, proposals(REMOVED, None, chosen, [lines], more_lines={
                    'P6': 'The pancreatic duct was then swept with a balloon; no stones were seen.'}, **SW),
                    ('E4', 'E5'))

    def test_d173_1_the_hold_is_decided_by_d155s_reading_as_before(self):
        """D168's disagreement 3 (constructed): applied to the hold, the condition would RELEASE "... and two stones
        were removed. The pancreatic duct was then swept with an extraction balloon, and no stones were retrieved."
        (both sweeps state nothing retrieved: E5 in its own sentence, E4 by D155's reading of E5's clause) - HELD
        nothing_retrieved at 1b4ca399 and f9013e12e, READY on E4 at e5628be56; c2e53f8e READY on the sweep's act with
        its sentence cited, HELD readings_disagree with the passage cited. It stays held: the hold reads D155's arm
        without ``whose``. And with the fb13 sentence for E4 (this repair's own AP4, constructed): held too, the
        appositive never read for the hold."""
        second = rival(words='swept with an extraction balloon', device=('extraction_balloon', 'extraction balloon'))
        p5 = f'{REMOVED} The pancreatic duct was then swept with an extraction balloon, and no stones were retrieved.'
        for cited, chosen in every((REMOVED, None)):
            with self.subTest(cited=bool(cited), participants=len(chosen)):
                held_nothing_retrieved(self, proposals(p5, cited, chosen, [second], **SW),
                                       f'{REMOVED} and no stones were retrieved')
        p5 = f'{FB13} The pancreatic duct was then swept with an extraction balloon, and no stones were retrieved.'
        for cited, chosen in every((FB13, None)):
            with self.subTest(fb13=True, cited=bool(cited), participants=len(chosen)):
                p = proposals(p5, cited, chosen, [second], **FB13_WORDS)
                self.assertEqual((p.status, p.support['reason']), ('needs_clarification', ercp.NOTHING_RETRIEVED))


# --- (2) the later sentence after a rival's sentence ----------------------------------------------------------------

class D173LaterSentence(SimpleTestCase):
    def test_d173_2_a_later_retrieval_denial_after_a_rivals_sentence_is_read_again(self):
        """review:ercp7 problem 0 (HIGH, a spec deviation; the outcome pre-existing and critical by the rubric;
        constructed; round5g/review-ercp7/cases/gen.json 'G O2|M1|F5' and 'G O2s|M1|F5'): "The bile duct was swept with
        an extraction balloon and two stones were removed. The pancreatic duct was then swept with a balloon. No stones
        were retrieved from the bile duct." (E4 status 'was swept' or 'were removed', E5 the pancreatic sweep): READY
        on E4 at e5628be56, f9013e12e and 1b4ca399 - D168 read every sentence past the rival's as the rival's, so E4
        stated nothing and E5's own continuation took E5 out of E*; c2e53f8e HELD conflict:stone_extraction. Now only a
        sentence that itself holds a rival's words is the rival's: the later denial is E4's statement too, both sweeps
        state nothing retrieved, and 43264 is held nothing_retrieved, the question quoting E4's statement, in both
        settings and citations."""
        p5 = (f'{REMOVED} The pancreatic duct was then swept with a balloon. No stones were retrieved from the bile '
              'duct.')
        for status in ('was swept', 'were removed'):
            for cited, chosen in every((REMOVED, None)):
                with self.subTest(status=status, cited=bool(cited), participants=len(chosen)):
                    p = proposals(p5, cited, chosen, [rival()], **dict(SW, status_words=status))
                    held_nothing_retrieved(self, p, f'{REMOVED} No stones were retrieved from the bile duct')
            reading = reading_of(p5, more=[rival()], **dict(SW, status_words=status))
            with self.subTest(reader=status):
                found = ercp.nothing_retrieved(reading, reading.events['E4'], (), ('E4', 'E5'))
                self.assertIsNotNone(found)
                self.assertEqual([place['text'] for place in found or ()],
                                 [REMOVED, 'No stones were retrieved from the bile duct'])

    def test_d173_2_the_rivals_own_sentence_stays_the_rivals(self):
        """The bound, as specified (constructed; D168's own control): a later sentence that ITSELF holds the rival's
        words - "... The pancreatic duct was then swept with a retrieval balloon and no stones were retrieved." - is the
        rival's when E4's own sentence states its yield: READY on E4, as on every new-path tree (c2e53f8e READY on the
        sweep's act with its sentence cited, HELD readings_disagree with the passage cited)."""
        second = rival(words='swept with a retrieval balloon', device=('balloon', 'retrieval balloon'))
        p5 = f'{REMOVED} The pancreatic duct was then swept with a retrieval balloon and no stones were retrieved.'
        for cited, chosen in every((REMOVED, None)):
            with self.subTest(cited=bool(cited), participants=len(chosen)):
                ready_on(self, proposals(p5, cited, chosen, [second], **SW), ('E4',))


# --- (3), (4), (6): 43264 never stands on acts that state no yield ---------------------------------------------------

class D173NoYield(SimpleTestCase):
    def test_d173_3_wv4_the_denial_stays_the_sweeps_statement(self):
        """review:ercp7 problem 1 (MEDIUM, a spec deviation; constructed; gen.json 'G O1|M2|F0'): WV4 "The bile duct was
        swept with an extraction balloon. The pancreatic duct was then swept with a balloon and no stones were seen."
        (E4 and E5 performed stone extractions): READY on E4 and E5 at e5628be56, f9013e12e and 1b4ca399, though the
        reader gave E4 the denial (E4 states no yield, so the denial in E5's clause stays E4's); c2e53f8e HELD
        readings_disagree. E5 states nothing either, so no act carries 43264: held nothing_retrieved, the question
        quoting E4's statement. The comma form ('G O1|M3|F0', "..., and no stones were seen.": READY on E5 ALONE at
        f9013e12e and 1b4ca399, on E4 and E5 at e5628be56; c2e53f8e HELD readings_disagree) is held too - no_yield,
        naming the pancreatic sweep left in E* and the bile-duct sweep D155's reading set apart."""
        p5 = f'{SWEPT_ONCE} The pancreatic duct was then swept with a balloon and no stones were seen.'
        comma = f'{SWEPT_ONCE} The pancreatic duct was then swept with a balloon, and no stones were seen.'
        for cited, chosen in every((SWEPT_ONCE, None)):
            with self.subTest(form='WV4', cited=bool(cited), participants=len(chosen)):
                held_nothing_retrieved(self, proposals(p5, cited, chosen, [rival()], **SW), p5[:-1])
            with self.subTest(form='comma', cited=bool(cited), participants=len(chosen)):
                held_no_yield(self, proposals(comma, cited, chosen, [rival()], **SW), ('E5', 'E4'))

    def test_d173_4_never_ready_on_the_silent_second_act_alone(self):
        """refute6 families finding 8 (high; refute6/ercp/cases/c05, c02, c03): FRESH-2 fb13's ATTESTED sentence with
        Gemini's attested words for it (kind and status 'were extracted', target 'Three stones, the largest 9 mm, were
        extracted from the bile duct'), then "No stones remained.", with a basket sweep filed as its own extraction -
        after it (WF1) or first (WF2); and D127's pinned clearance with the status words 'was swept' (CLEARED) beside a
        basket sweep after it (WB1), first (WB2), or on its own line (WB-L1). D155's reading sets the extraction apart
        (its yield unread: across the appositive's commas, or in a second simple clause), so 43264 was READY on the
        basket ALONE at f9013e12e and 1b4ca399 (and at e5628be56 for WF1 and WF2) - the act whose result the document
        never states. The basket states no yield and is done to no finding, so no act carries 43264: held no_yield,
        naming the basket and the extraction D155 set apart, never READY. c2e53f8e READY: on the fb13 act and the basket
        (WF1, WB1, WB-L1), on the fb13 act alone (WF2), on the balloon act alone (WB2) - COSTS."""
        basket = rival(('bile_duct', 'The duct'), 'swept with a basket', device=('basket', 'basket'))
        line = rival(('not_stated', ''), 'basket sweep', 'was then performed', ('basket', 'basket'), passage='P7')
        first = rival(('bile_duct', 'The duct'), 'swept with a basket', 'was first swept', ('basket', 'basket'),
                      passage='P3')
        shapes = {
            'WF1': (FB13, dict(FB13_WORDS, more_lines={'P6': 'No stones remained.',
                                                       'P7': 'A basket sweep was then performed.'}), line),
            'WF2': (FB13, dict(FB13_WORDS, more_lines={'P6': 'No stones remained.',
                                                       'P3': 'The duct was first swept with a basket.'}), first),
            'WB1': (f'{CLEARED} The duct was then swept with a basket.', SW, basket),
            'WB2': (f'The duct was first swept with a basket. {CLEARED}', SW,
                    rival(('bile_duct', 'The duct'), 'swept with a basket', 'was first swept', ('basket', 'basket'))),
            'WB-L1': (CLEARED, dict(SW, more_lines={'P6': 'A basket sweep was then performed.'}),
                      rival(('not_stated', ''), 'basket sweep', 'was then performed', ('basket', 'basket'), 'P6')),
        }
        for name, (p5, options, second) in shapes.items():
            for chosen in PARTICIPANTS:
                with self.subTest(shape=name, participants=len(chosen)):
                    held_no_yield(self, proposals(p5, None, chosen, [second], **options), ('E5', 'E4'))

    def test_d173_4_the_appositive_decides_whose_denial_for_e_star_and_never_clears_a_hold(self):
        """The yield across an appositive (this repair's own, constructed; the fb13 sentence's attested words): beside a
        rival's sentence whose free clause denies - "Three stones, the largest 9 mm, were extracted from the bile duct
        with an extraction balloon. The duct was then swept with a basket; no stones remained." (AP1) and "... The
        pancreatic duct was then swept with a balloon; no stones were seen." (AP3) - the denial is the rival's, so the
        extraction stays in E*: READY on E4 and E5 (1b4ca399 and f9013e12e READY on E5 alone; e5628be56 READY on E4 and
        E5; c2e53f8e READY on both acts on AP1, on the fb13 act on AP3). Never a clearance: WF0 (the fb13 sentence, then
        "No stones remained.", one act) stays held nothing_retrieved, as on every new-path tree (c2e53f8e READY: D147's
        recorded cost). The reader on its own: the fb13 sentence states a yield across its appositive; "The balloon,
        used for the stones, was removed." states none (its subject is the device), nor does "Three stones, if any,
        were extracted" (a doubt word)."""
        basket = rival(('bile_duct', 'The duct'), 'swept with a basket', device=('basket', 'basket'))
        for name, second, other in (('AP1', 'The duct was then swept with a basket; no stones remained.', basket),
                                    ('AP3', 'The pancreatic duct was then swept with a balloon; no stones were seen.',
                                     rival())):
            for cited, chosen in every((FB13, None)):
                with self.subTest(shape=name, cited=bool(cited), participants=len(chosen)):
                    ready_on(self, proposals(f'{FB13} {second}', cited, chosen, [other], **FB13_WORDS), ('E4', 'E5'))
        for chosen in PARTICIPANTS:
            with self.subTest(shape='WF0', participants=len(chosen)):
                held_nothing_retrieved(self, proposals(FB13, None, chosen, more_lines={'P6': 'No stones remained.'},
                                                       **FB13_WORDS), f'{FB13} No stones remained.')

        def clauses(text):
            return ercp._clauses({'start': 0, 'end': len(text), 'text': text})

        self.assertTrue(ercp._appositive_yield(clauses(FB13)))
        self.assertFalse(ercp._appositive_yield(clauses('The balloon, used for the stones, was removed.')))
        self.assertFalse(ercp._appositive_yield(clauses('Three stones, if any, were extracted from the bile duct.')))
        self.assertFalse(ercp._clause_yield(clauses(FB13), []))  # D168's reading cannot cross the commas

    def test_d173_6_a_sweep_that_states_no_yield_after_a_negative_cholangiogram(self):
        """refute6 judges finding 9 (critical; refute6/gate-ercp/cases/s1, s2; the verifier's template wordings): on
        finding 25's ERCP ("Cholangiogram showed a mildly dilated bile duct without filling defects."), s1 "The bile
        duct was swept several times with an extraction balloon." (E4 alone), "The bile duct was swept with an
        extraction balloon.", "The biliary tree was swept with a 12 mm balloon starting at the bifurcation." and
        "Balloon sweeps of the common bile duct were performed." - READY on E4 at e5628be56, f9013e12e and 1b4ca399;
        c2e53f8e HELD act_missing on each. And s2, the gate row (tests.test_interpretation_r5_ercp's 'the other act
        filed'): "The pancreatic duct was swept with a balloon; no stones were retrieved. The bile duct was then swept
        with an extraction balloon." (E5 the pancreatic sweep, set apart by its own denial) - READY on E4 on every
        new-path tree; c2e53f8e HELD readings_disagree. By structure: the sweep's own statement states no yield and the
        sweep is done to no finding the examination lists, so 43264 is held no_yield, both citations, both settings;
        43262 stays READY."""
        shapes = {
            's1': ('The bile duct was swept several times with an extraction balloon.', {}),
            's1b': (SWEPT_ONCE, SW),
            'template 12 mm': ('The biliary tree was swept with a 12 mm balloon starting at the bifurcation.',
                               dict(kind_words='swept with a 12 mm balloon', status_words='was swept',
                                    target=('bile_duct', 'The biliary tree'), technique=('balloon', 'balloon'))),
            'template sweeps': ('Balloon sweeps of the common bile duct were performed.',
                                dict(kind_words='Balloon sweeps', status_words='were performed',
                                     target=('common_bile_duct', 'the common bile duct'),
                                     technique=('balloon', 'Balloon'))),
        }
        for name, (p5, options) in shapes.items():
            for cited, chosen in every((p5, None)):
                with self.subTest(shape=name, cited=bool(cited), participants=len(chosen)):
                    inv, text, doc = sweep(p5, **options)
                    result = run(inv, text, [('43262', doc['P4']), ('43264', cited or p5)], participants=chosen)
                    held_no_yield(self, proposal(result, '43264'), ('E4',))
                    self.assertIn(f'({p5})', proposal(result, '43264').clarifications[0].question.replace(
                        '“', '').replace('”', ''))
                    self.assertEqual(proposal(result, '43262').status, 'ready')
        pancreatic = 'The pancreatic duct was swept with a balloon; no stones were retrieved.'
        swept = 'The bile duct was then swept with an extraction balloon.'
        second = ercp_act('E5', 'P5', 'stone_extraction', 'swept with a balloon', 'was swept',
                          target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                          technique=a('balloon', 'balloon', ['P5']))
        for cited, chosen in every((swept, None)):
            with self.subTest(shape='s2', cited=bool(cited), participants=len(chosen)):
                held_no_yield(self, proposals(f'{pancreatic} {swept}', cited, chosen, [second],
                                              kind_words='swept with an extraction balloon',
                                              status_words='was then swept'), ('E4', 'E5'))

    def test_d173_6_controls_an_act_that_states_its_yield_or_is_done_to_a_finding(self):
        """Controls, each READY on E4 as at 1b4ca399 (constructed, this repair's own, but the fb13 shape): the act's own
        sentence states its yield - "... two small stones were retrieved." (D106's control; c2e53f8e READY), "... and
        two stones were removed." with the status words 'was swept' (SY1; c2e53f8e READY), the next sentence "Two
        stones were removed." (SY2; c2e53f8e READY), the next sentence "A plastic biliary stent was placed and sludge
        was retrieved." (SY3, a free clause, the stent filed; c2e53f8e READY on the stone act); the fb13 sentence alone
        (AP6, its yield across the appositive; c2e53f8e READY); and an act done to the finding the cholangiogram lists -
        FRESH-2 fb13's attested shape (the extraction's target the lesion 'three filling defects (stones)'), and
        "Balloon extraction of the stone was performed." done to 'a 10 mm stone' (SY12; c2e53f8e READY)."""
        for p5, options, more in (
                ('The bile duct was swept several times with an extraction balloon; two small stones were retrieved.',
                 {}, ()),
                ('The bile duct was swept with an extraction balloon and two stones were removed.', SW, ()),
                ('The bile duct was swept with an extraction balloon. Two stones were removed.', SW, ()),
                ('The bile duct was swept with an extraction balloon. A plastic biliary stent was placed and sludge '
                 'was retrieved.', SW, (stent(),)),
                (FB13, FB13_WORDS, ())):
            for chosen in PARTICIPANTS:
                with self.subTest(p5=p5[:60], participants=len(chosen)):
                    ready_on(self, proposals(p5, None, chosen, more, **options), ('E4',))
        for p5, finding, kind, status, words in (
                (FB13, 'three filling defects (stones)', 'were extracted', 'were extracted',
                 'Three stones, the largest 9 mm, were extracted from the bile duct'),
                ('Balloon extraction of the stone was performed.', 'a 10 mm stone', 'Balloon extraction',
                 'was performed',
                 'the stone')):
            inv, text = done_to_a_finding(p5, finding, kind, status, words)
            for chosen in PARTICIPANTS:
                with self.subTest(finding=finding, participants=len(chosen)):
                    ready_on(self, proposal(run(inv, text, [('43262', SPHINCTEROTOMY), ('43264', p5)],
                                                participants=chosen), '43264'), ('E4',))

    def test_d173_6_a_finding_never_carries_an_act_that_states_nothing_retrieved(self):
        """The finding's bound (this repair's own, constructed): WV4 with the bile-duct sweep done to the
        cholangiogram's 'a 10 mm stone' - the sweep states no yield and the denial in the pancreatic sweep's clause
        stays its statement, so its finding does not carry it, and the pancreatic sweep states nothing: held
        nothing_retrieved (1b4ca399 READY on E4 and E5)."""
        p5 = f'{SWEPT_ONCE} The pancreatic duct was then swept with a balloon and no stones were seen.'
        inv, text = done_to_a_finding(p5, 'a 10 mm stone', 'swept with an extraction balloon', 'was swept',
                                      'The bile duct', more=[rival()])
        for chosen in PARTICIPANTS:
            with self.subTest(participants=len(chosen)):
                held_nothing_retrieved(self, proposal(run(inv, text, [('43262', SPHINCTEROTOMY), ('43264', p5)],
                                                          participants=chosen), '43264'), p5[:-1])

    def test_d173_6_recorded_costs(self):
        """COSTS (holds where c2e53f8e is READY; constructed, this repair's own): a sweep whose own words state no yield
        by D140's subject rule, done to no listed finding - "The bile duct was swept for stones with an extraction
        balloon." (SY5), "Stone extraction was performed with an extraction balloon." (SY6) and "... and two stones were
        then extracted." (SY8, an adverb between the auxiliary and the verb: D140's recorded limit) - READY on E4 at
        e5628be56, f9013e12e and 1b4ca399, and at c2e53f8e; held no_yield now. Fail-closed holds of a code the document
        may support: for the owner."""
        for p5, options in (('The bile duct was swept for stones with an extraction balloon.',
                             dict(kind_words='swept for stones with an extraction balloon', status_words='was swept')),
                            ('Stone extraction was performed with an extraction balloon.',
                             dict(kind_words='Stone extraction', status_words='was performed',
                                  target=('not_stated', ''))),
                            ('The bile duct was swept with an extraction balloon and two stones were then extracted.',
                             SW)):
            for chosen in PARTICIPANTS:
                with self.subTest(p5=p5[:60], participants=len(chosen)):
                    held_no_yield(self, proposals(p5, None, chosen, **options), ('E4',))


def done_to_a_finding(p5: str, finding: str, kind: str, status: str, words: str, more=()):
    """(inventory, text): finding 25's ERCP with P3 a cholangiogram that finds ``finding`` (lesion L1, as FRESH-2 fb13's
    'three filling defects (stones)') and the act E4 in ``p5`` done to L1 (its target)."""
    lines = dict(SWEEP, P3=f'Cholangiogram showed {finding} in the bile duct.', P5=p5)
    built = [duodenoscope('P1'),
             ercp_act('E2', 'P2', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                      target=tg('', 'bile_duct', 'biliary', ['P2'])),
             ercp_act('E3', 'P4', 'sphincterotomy', 'biliary sphincterotomy', 'was performed',
                      target=tg('', 'bile_duct', 'biliary', ['P4'])),
             ercp_act('E4', 'P5', 'stone_extraction', kind, status, target=tg('L1', 'bile_duct', words, ['P5']),
                      technique=a('extraction_balloon', 'extraction balloon', ['P5'])), *more]
    return inventory(lines, events=built, lesions=[les('L1', finding, 'P3', landmark='bile_duct')],
                     reach=[reached('E1', 'ampulla', 'major papilla', 'P1')])


# --- (5) the exchange named only in a title ---------------------------------------------------------------------------

def exchange(kind_words='biliary stent exchange', kind_passages=('P1',), status=('performed', 'was placed', ('P5',)),
             target=('common_bile_duct', 'common bile duct', ('P5',))):
    """D127 problem 1's filing (tests.test_interpretation_r5_ercp.exchange_event): the exchange E5 with the 'Procedure:'
    line's kind words and the placement's status and target, unless changed."""
    item = act('E5', kind_passages[0], 'stent_exchange', kind_words, procedure=a('ercp'))
    item['kind']['passages'] = list(kind_passages)
    item.update(technique=a('stent', 'plastic biliary stent', ['P5']), status=a(status[0], status[1], list(status[2])),
                target=tg('', target[0], target[1], list(target[2])))
    return item


def exchange_case(more=(), lines=None, codes=('43276',)):
    """(inventory, text, doc, cites): finding 22's document (tests.test_interpretation_r4_ercp.EXCHANGE) with ``lines``
    changed, the duodenoscope (E1), the cannulation (E3) and ``more``; Corti citing each of ``codes`` at its line."""
    doc = dict(EXCHANGE, **(lines or {}))
    built = [exam('E1', 'P2', words='duodenoscope', procedure=a('ercp')),
             ercp_act('E3', 'P4', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                      target=tg('', 'bile_duct', 'biliary', ['P4'])), *more]
    inv, text = inventory(doc, events=built, reach=[reached('E1', 'ampulla', 'major papilla', 'P2')])
    cited = {'43275': doc['P3'], '43274': doc['P5'], '43276': doc['P1']}
    return inv, text, doc, [(code, cited[code]) for code in codes]


X = {  # refute6 judges finding 8 (refute6/gate-ercp/cases/x1c, x1, x4, x3, x2): the body states no stent removed today
    'x1c left in place': ({'P3': 'The existing biliary stent was left in place.'},
                          [ercp_act('E2', 'P3', 'stent_removal', 'left in place', 'was left in place',
                                    status='not_performed', target=tg('', 'bile_duct', 'biliary', ['P3']))]),
    'x1 not removed': ({'P3': 'The existing biliary stent was not removed.'},
                       [ercp_act('E2', 'P3', 'stent_removal', 'removed', 'was not removed', status='not_performed',
                                 target=tg('', 'bile_duct', 'biliary', ['P3']))]),
    'x4 migrated': ({'P3': 'The previously placed biliary stent had migrated and was not seen in the duodenum.'}, []),
    'x3 an earlier ERCP': ({'P3': 'At the prior ERCP in 2025 the previous biliary stent was removed with a snare.'},
                           [ercp_act('E2', 'P3', 'stent_removal', 'removed', 'was removed with a snare',
                                     target=tg('', 'bile_duct', 'biliary', ['P3']),
                                     time=a('earlier_encounter', 'At the prior ERCP in 2025', ['P3']))]),
    'x2 the pancreatic duct': ({'P3': 'The existing pancreatic duct stent was removed with a snare.'},
                               [ercp_act('E2', 'P3', 'stent_removal', 'removed', 'was removed with a snare',
                                         target=tg('', 'pancreatic_duct', 'pancreatic duct', ['P3']),
                                         technique=a('snare', 'snare', ['P3']))]),
}


def held_named_apart(test, p) -> None:
    test.assertEqual((p.bucket, p.status, asked(p), p.support['reason'], p.support['acts'],
                      p.support.get('question_events')),
                     ('selected', 'needs_clarification', ['performed_status'], ercp.EXCHANGE_TITLE, [], ['E5']))
    test.assertIn('one stent exchange (43276)', p.clarifications[0].question)
    test.assertIn('Procedure: ERCP with biliary stent exchange.', p.clarifications[0].question)


class D173ExchangeNamedApart(SimpleTestCase):
    def test_d173_5_an_exchange_named_only_in_the_title(self):
        """refute6 judges finding 8 (critical; constructed, D127 problem 1's pinned filing): "Procedure: ERCP with
        biliary stent exchange." over a body that states the old stent left in place (x1c), not removed (x1), migrated
        (x4, no removal event), removed at an earlier ERCP (x3) or the PANCREATIC duct's stent removed (x2), and "A 10
        Fr x 9 cm plastic biliary stent was placed into the common bile duct." - the exchange E5 filed with the title's
        kind words and the placement's status and target, no stent event. 43276 was READY on E5 at e5628be56, f9013e12e
        and 1b4ca399 (exchange_pairs gives no pair); c2e53f8e HELD act_missing on every member. Now held
        exchange_named_apart [performed_status], 43276 cited alone or beside 43274 (and 43275 on x2), in both settings;
        43274 stays held not documented, as on every new-path tree (c2e53f8e READY on x1c, x4, x3 and x2, HELD
        conflict:stent on x1: a pre-existing cost); x2's 43275 stays READY on the pancreatic removal (c2e53f8e HELD
        act_missing)."""
        for name, (lines, removal) in X.items():
            codes = ('43276', '43274', '43275') if name.startswith('x2') else ('43276', '43274')
            inv, text, doc, cites = exchange_case([*removal, exchange()], lines, codes)
            self.assertEqual(ercp.exchange_pairs(events.Reading.of(inv)), [])
            for chosen in PARTICIPANTS:
                for cited in (cites, cites[:1]):
                    with self.subTest(member=name, codes=len(cited), participants=len(chosen)):
                        result = run(inv, text, cited, participants=chosen)
                        held_named_apart(self, proposal(result, '43276'))
                        if len(cited) > 1:
                            self.assertEqual(proposal(result, '43274').support['reason'], events.NOT_DOCUMENTED)
                        if len(cited) > 2:
                            ready_on(self, proposal(result, '43275'), ('E2',))

    def test_d173_5_the_title_with_its_own_words_and_the_mirror(self):
        """This repair's own variants (constructed): the status words the title's own ("stent exchange", inside the kind
        words; the verifier's variant), and the mirror - the exchange with the REMOVAL's sentence as its status and
        target, nothing else filed: held exchange_named_apart (READY at e5628be56, f9013e12e and 1b4ca399; c2e53f8e HELD
        act_missing)."""
        for name, item in (('the title\'s own status words', exchange(status=('performed', 'stent exchange', ('P1',)))),
                           ('the mirror', exchange(status=('performed', 'was removed with a snare', ('P3',)),
                                                   target=('bile_duct', 'biliary', ('P3',))))):
            inv, text, doc, cites = exchange_case([item])
            for chosen in PARTICIPANTS:
                with self.subTest(variant=name, participants=len(chosen)):
                    held_named_apart(self, proposal(run(inv, text, cites, participants=chosen), '43276'))

    def test_d173_5_controls(self):
        """Controls (constructed), each as at 1b4ca399: an exchange stated in a body sentence - "The existing biliary
        stent was exchanged for a 10 Fr x 9 cm plastic biliary stent." (its kind words 'exchanged', status 'was
        exchanged') and "Biliary stent exchange was performed." - and the title exchange RESTATED in the body (its kind
        passages the title and "The biliary stent was exchanged.", its status words there) are READY (c2e53f8e HELD
        act_missing on each); the title exchange beside the removal or the placement filed keeps D127's
        possible_exchange hold. And the reader on each (_named_only_apart)."""
        body = 'The existing biliary stent was exchanged for a 10 Fr x 9 cm plastic biliary stent.'
        done = 'Biliary stent exchange was performed.'
        restated = 'The biliary stent was exchanged.'
        ready = {
            'stated in the body': ({'P5': body}, exchange('exchanged', ('P5',), ('performed', 'was exchanged', ('P5',)),
                                                          ('bile_duct', 'biliary', ('P5',))), body),
            'exchange was performed': ({'P5': done}, exchange('Biliary stent exchange', ('P5',),
                                                              ('performed', 'was performed', ('P5',)),
                                                              ('bile_duct', 'Biliary', ('P5',))), done),
            'restated': ({'P5': restated}, exchange(kind_passages=('P1', 'P5'),
                                                    status=('performed', 'was exchanged', ('P5',)),
                                                    target=('bile_duct', 'biliary', ('P5',))), EXCHANGE['P1']),
        }
        for name, (lines, item, cited) in ready.items():
            inv, text, doc, cites = exchange_case([item], lines)
            reading = events.Reading.of(inv)
            self.assertFalse(ercp._named_only_apart(reading, reading.events['E5']), name)
            for chosen in PARTICIPANTS:
                with self.subTest(control=name, participants=len(chosen)):
                    ready_on(self, proposal(run(inv, text, [('43276', cited)], participants=chosen), '43276'), ('E5',))
        removal = ercp_act('E2', 'P3', 'stent_removal', 'removed', 'was removed with a snare',
                           target=tg('', 'bile_duct', 'biliary', ['P3']))
        placement = ercp_act('E4', 'P5', 'stent', 'stent', 'was placed',
                             target=tg('', 'common_bile_duct', 'common bile duct', ['P5']))
        for name, more in (('beside the removal', [removal, exchange()]),
                           ('beside the placement', [exchange(status=('performed', 'was removed with a snare', ('P3',)),
                                                              target=('bile_duct', 'biliary', ('P3',))), placement])):
            inv, text, doc, cites = exchange_case(more)
            reading = events.Reading.of(inv)
            self.assertTrue(ercp._named_only_apart(reading, reading.events['E5']), name)
            with self.subTest(pair=name):
                p = proposal(run(inv, text, cites), '43276')
                self.assertEqual((p.status, p.support['reason']), ('needs_clarification', ercp.POSSIBLE_EXCHANGE))

    def test_d173_5_recorded_residual_a_title_with_a_status_word_of_its_own(self):
        """RECORDED RESIDUAL (constructed): a title that holds a status word of its own outside the kind words -
        "Procedure: ERCP with biliary stent exchange performed." (status words 'performed') - is a sentence that names
        the exchange and states it done, so it is not named only apart: READY on E5, as on every new-path tree
        (c2e53f8e HELD act_missing). Telling that title from a body sentence would need a word list of headings."""
        title = 'Procedure: ERCP with biliary stent exchange performed.'
        inv, text, doc, cites = exchange_case([exchange(status=('performed', 'performed', ('P1',)))], {'P1': title})
        ready_on(self, proposal(run(inv, text, [('43276', title)]), '43276'), ('E5',))


# --- (7) another occasion's time words in the yield's clause --------------------------------------------------------

O7 = 'The bile duct was swept with an extraction balloon and two stones were removed two weeks ago.'
HISTORY = 'History: ERCP with stone removal at an outside hospital.'


def earlier_removal(time_words='two weeks ago', value='earlier_encounter'):
    """The earlier removal filed as its own stone extraction (prompt.py: an act done at another time is its own event),
    told in a history line (P6) with its time words in the sweep's yield clause (P5)."""
    return ercp_act('E6', 'P6', 'stone_extraction', 'stone removal', 'stone removal',
                    target=tg('', 'bile_duct', '', []),
                    time=a(value, time_words, ['P5']))


class D173OtherTime(SimpleTestCase):
    def test_d173_7_an_other_time_yield_is_no_yield_of_this_act(self):
        """review:ercp7 problem 2 (PRE-EXISTING, critical by the rubric; constructed, on contract): "The bile duct was
        swept with an extraction balloon and two stones were removed two weeks ago. The pancreatic duct was then swept
        with a balloon and no stones were retrieved." (and "... no stones were seen."), the earlier removal filed as its
        own earlier_encounter stone extraction told in a history line, its time words "two weeks ago" in the yield's
        clause. D168's own-yield reading counted the yield, so the denial was the pancreatic sweep's and 43264 READY on
        E4 (both forms: READY on E4, and on E4 and E5 with "seen", at e5628be56, f9013e12e and 1b4ca399); c2e53f8e HELD
        readings_disagree with the sweep's sentence cited (EXCLUDED with the passage cited on the first). The time
        reader places that event off this date, so the clause states no yield of the sweep's: the denial stays its
        statement - held nothing_retrieved. The reader: the clause yields without the time words, not with them."""
        for last, more, said in (('no stones were retrieved', [rival()],
                                  'The pancreatic duct was then swept with a balloon and no stones were retrieved'),
                                 ('no stones were seen', [rival()],
                                  'The pancreatic duct was then swept with a balloon and no stones were seen')):
            p5 = f'{O7} The pancreatic duct was then swept with a balloon and {last}.'
            for cited, chosen in every((O7, None)):
                with self.subTest(last=last, cited=bool(cited), participants=len(chosen)):
                    held_nothing_retrieved(self, proposals(p5, cited, chosen, [*more, earlier_removal()],
                                                           more_lines={'P6': HISTORY}, **SW), f'{O7} {said}')
        reading = reading_of(f'{O7} The pancreatic duct was then swept with a balloon and no stones were retrieved.',
                             more=[rival(), earlier_removal()], more_lines={'P6': HISTORY}, **SW)
        event = reading.events['E4']
        clauses = ercp._clauses({'start': reading.places(['P5'])[0]['start'], 'end': 0,
                                 'text': reading.places(['P5'])[0]['text'].split('. ')[0] + '.'})
        times = ercp._other_times(reading, event)
        self.assertEqual([item['text'] for item in times], ['two weeks ago'])
        self.assertTrue(ercp._clause_yield(clauses, []))
        self.assertFalse(ercp._clause_yield(clauses, [], times))

    def test_d173_7_controls_the_time_reader_decides(self):
        """Controls (constructed): the same filing with "this morning" for the time words (a same-day word: the time
        reader places the event ON the date, facts.day_of) states the sweep's yield - READY on E4, as on every
        new-path tree (c2e53f8e READY) - and so does the earlier removal's time words standing outside the clause
        (in the history line): READY on E4."""
        today = 'The bile duct was swept with an extraction balloon and two stones were removed this morning.'
        p5 = f'{today} The pancreatic duct was then swept with a balloon and no stones were retrieved.'
        for chosen in PARTICIPANTS:
            with self.subTest(form='this morning', participants=len(chosen)):
                ready_on(self, proposals(p5, today, chosen, [rival(), earlier_removal('this morning')],
                                         more_lines={'P6': HISTORY}, **SW), ('E4',))
        removed = REMOVED
        p5 = f'{removed} The pancreatic duct was then swept with a balloon and no stones were retrieved.'
        apart = ercp_act('E6', 'P6', 'stone_extraction', 'stone removal', 'stone removal',
                         target=tg('', 'bile_duct', '', []), time=a('earlier_encounter', 'History:', ['P6']))
        for chosen in PARTICIPANTS:
            with self.subTest(form='time words in the history line', participants=len(chosen)):
                ready_on(self, proposals(p5, removed, chosen, [rival(), apart], more_lines={'P6': HISTORY}, **SW),
                         ('E4',))


# --- the another_role hold's second (D168 (3)): D106's question only -----------------------------------------------

class D173RoleSecond(SimpleTestCase):
    def test_d173_the_role_holds_second_is_d106s_question_never_no_yields(self):
        """D168 (3) as it stands (role_second passes D105's and D106's questions only), constructed: WV4 signed by the
        nurse - "Documented by Jo Rowe, RN: The bile duct was swept with an extraction balloon. The pancreatic duct was
        then swept with a balloon and no stones were seen." - is held another_role, its question first, and now D106's
        question on the bile-duct sweep's statement second (D173 (3) holds the READY evaluation role_second builds;
        1b4ca399: the another_role question alone; e5628be56 READY on E4 and E5; c2e53f8e HELD act_missing): a
        QUESTION-ADDED. A signed sweep that states no yield at all ("Documented by Jo Rowe, RN: The bile duct was swept
        several times with an extraction balloon.") keeps the another_role question alone, as at 1b4ca399: D173's
        NO_YIELD question is no second (tests.test_interpretation_r5g_colon's D165 pin counts its questions). The holds
        themselves are unchanged: their reason, E* and read events are the another_role hold's."""
        signed = ('Documented by Jo Rowe, RN: The bile duct was swept with an extraction balloon. The pancreatic duct '
                  'was then swept with a balloon and no stones were seen.')
        silent = 'Documented by Jo Rowe, RN: The bile duct was swept several times with an extraction balloon.'
        for p5, more, options, seconds in ((signed, [rival()], SW, 2), (silent, [], {}, 1)):
            inv, text, doc = sweep(p5, more=more, **options)
            for chosen in PARTICIPANTS:
                with self.subTest(p5=p5[27:70], participants=len(chosen)):
                    p = proposal(run(inv, text, [('43262', doc['P4']), ('43264', p5)], participants=chosen), '43264')
                    self.assertEqual((p.status, p.support['reason'], asked(p)),
                                     ('needs_clarification', events.ANOTHER_ROLE, ['performed_status'] * seconds))
                    self.assertIn('documented only in the nursing entry', p.clarifications[0].question)
                    if seconds == 2:
                        self.assertTrue(p.clarifications[1].question.startswith(
                            'Was any stone, calculus, debris or sludge removed with the stone removal (extraction '
                            'balloon) at the bile duct'), p.clarifications[1].question)
                        self.assertIn('nothing was retrieved', p.clarifications[1].reason)
            reading = events.Reading.of(inv)
            reading.text = text  # as assess.assess hands it over (DECISIONS D124)
            evaluation = events.evaluate('43264', (), reading)
            with self.subTest(evaluation=p5[27:70]):
                self.assertEqual((evaluation.reason, evaluation.supporting), (events.ANOTHER_ROLE, ()))
                if seconds == 2:
                    self.assertIsNotNone(evaluation.second)
                    self.assertEqual((evaluation.second.fact, evaluation.second.events), ('performed_status', ('E4',)))
                else:
                    self.assertIsNone(evaluation.second)
