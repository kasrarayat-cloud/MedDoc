"""Round 5g of the Gemini migration (narrowing only), the ERCP repair D168 (round 5f's ercp6, D159, NOT integrated:
round5f/ercp6/patch.diff and DECISIONS' D159 record; round5f/results-wf_78933804-741.json 'review:ercp6' problems 0-4
and 'review:colon5' problem 0), SYNTHETIC and REPLAYED: nothing is sent. Each pin is built from its source's own input -
finding 25's ERCP with the sweep's passage changed (tests.test_interpretation_r5_ercp.sweep), finding 22's and finding
25's documents (tests.test_interpretation_r4_ercp), the review:ercp6 W1 cases (round5f/review-ercp6/tools/
build_cases.py) and the ercp6 builder's and reviewers' texts - or, where named, this repair's own constructed variants.

- (1) D159's rules rebuilt WITHOUT review:ercp6 problem 1 (W1, a READY on the wrong act). D155's reading runs first,
  unchanged; only where it states nothing do the widened reads run: D159's rule (1) (a clause of the dropped sentence
  that holds another event's own words) and rule (3) (a later sentence of the act's own passage, read for a denial).
  Whose denial: where the sentence that holds it - or, for rule (3), a sentence between the act's own and it - holds the
  own words of ANOTHER performed stone extraction that supports the same code, the denial is that act's when this act's
  own sentence states its own yield (ercp._clause_yield: "... and two stones were removed."), else this act's. A
  statement only the widened reads give only ever HOLDS 43264 (retrieval_hold): where another act still supports the
  code, E* stays as D155 leaves it, so no READY code's acts change.
- (2) review:ercp6 problem 3: after an own sentence that states the act's yield, a later RETRIEVAL denial is still read.
- (3) review:colon5 problem 0: the another_role hold of a code D105 or D106 would hold keeps its question, and the ERCP
  question is its SECOND clarification (events.Evaluation.second), so neither is dropped.
- (4) review:ercp6 problem 4: on D159's shapes beside finding 5's lithotripsy, 43265 is held competing_codes (D163, as
  integrated: G4), never READY.

The installed release c2e53f8e's outcome on each input (jobs._assess_child, as the head-to-head runs it, with no
participant and with Astra and Fable read: the same in both settings unless quoted apart) and the outcomes of e5628be56
(round 5c), f9013e12e (round 5e) and 05a881a75 (round 5f, the base) are quoted in each pin's docstring
(round5g/ercp7/out/, census/).
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import ercp, events
from tests.test_interpretation_events import asked, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, sc, tg
from tests.test_interpretation_r4_ercp import EXCHANGE, PARTICIPANTS, balloon_sweep, ercp_act
from tests.test_interpretation_r5_ercp import held_nothing_retrieved, ready_on, sweep

SW = dict(kind_words='swept with an extraction balloon', status_words='was swept')
OWN_YIELD = dict(SW, status_words='were removed')  # the own sentence's yield in its status words (D147 reads it)
SWEPT_ONCE = 'The bile duct was swept with an extraction balloon.'
REMOVED = 'The bile duct was swept with an extraction balloon and two stones were removed.'
LITHO_P3 = 'A 15 mm stone in the common bile duct was fragmented with mechanical lithotripsy.'
SIGNED = 'Documented by Jo Rowe, RN: '


def assessed(p5: str, cited=None, participants=(), codes=(), **options):
    """The proposals on finding 25's ERCP (tests.test_interpretation_r5_ercp.sweep) with ``p5`` for the sweep (E4),
    Corti citing 43262 at the sphincterotomy, 43264 at ``cited`` (default: the whole of P5) and each of ``codes``."""
    inv, text, doc = sweep(p5, **options)
    return run(inv, text, [('43262', doc['P4']), ('43264', cited or p5), *codes], participants=participants)


def statement(p5: str, beside=(), **options):
    """E4's statement that nothing was retrieved (ercp.nothing_retrieved, the inventory alone; ``beside``: the code's
    other supporting acts, as retrieval_hold passes them), as its texts; else None."""
    inv, text, doc = sweep(p5, **options)
    reading = events.Reading.of(inv)
    found = ercp.nothing_retrieved(reading, reading.events['E4'], (), beside)
    return None if found is None else [place['text'] for place in found]


def held_in_both(test, p5: str, said: str, more, citations=(SWEPT_ONCE, None), **options) -> None:
    """43264 held with D106's question quoting ``said``, Corti citing each of ``citations`` (None: the whole passage),
    with no participant and with Astra and Fable read."""
    for cited in citations:
        for chosen in PARTICIPANTS:
            with test.subTest(p5=p5[len(SWEPT_ONCE):][:70], cited=bool(cited), participants=len(chosen)):
                result = assessed(p5, cited, chosen, **dict(SW, **options), more=more)
                held_nothing_retrieved(test, proposal(result, '43264'), said)


def ready_in_both(test, p5: str, more, acts=('E4',), citations=(SWEPT_ONCE, None), **options) -> None:
    for cited in citations:
        for chosen in PARTICIPANTS:
            with test.subTest(p5=p5[len(SWEPT_ONCE):][:70], cited=bool(cited), participants=len(chosen)):
                ready_on(test, proposal(assessed(p5, cited, chosen, **dict(SW, **options), more=more), '43264'), acts)


def stent(eid='E5', kind_words='plastic biliary stent', status_words='was placed', **changes):
    return ercp_act(eid, 'P5', 'stent', kind_words, status_words, **changes)


def pancreatic_stent(eid='E5'):
    return stent(eid, kind_words='5 Fr pancreatic stent', target=tg('', 'pancreatic_duct', 'pancreatic', ['P5']))


def pancreatic_sweep():
    return ercp_act('E5', 'P5', 'stone_extraction', 'swept with a balloon', 'was then swept',
                    target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                    technique=a('balloon', 'balloon', ['P5']))


def second_sweep(words='swept with a basket', device=('basket', 'basket'),
                 duct=('pancreatic_duct', 'The pancreatic duct'), status='was then swept'):
    """review:ercp6's W cases' second sweep (round5f/review-ercp6/tools/build_cases.py basket_sweep): E5, a performed
    stone extraction at P5."""
    return ercp_act('E5', 'P5', 'stone_extraction', words, status, target=tg('', duct[0], duct[1], ['P5']),
                    technique=a(device[0], device[1], ['P5']))


def basket(status='were extracted', **changes):
    return ercp_act('E5', 'P5', 'stone_extraction', 'extracted', status, technique=a('basket', 'basket', ['P5']),
                    **changes)


def plan(eid='E6'):
    return ercp_act(eid, 'P5', 'examination', 'a repeat ERCP', 'is planned', status='planned',
                    time=a('future', 'is planned', ['P5']))


def denial(eid='E6', kind='other', words='No stones were retrieved'):
    """The denial Gemini files as its own not_performed event (prompt.py), its words the denial itself."""
    return ercp_act(eid, 'P5', kind, words, words, status='not_performed',
                    scope=sc('single_target', words.split()[0], ['P5']))


def lithotripsy(eid='E8'):
    """Finding 5's lithotripsy (tests.test_interpretation_r3_claims.STONE's P3), as its own performed event at P3."""
    return ercp_act(eid, 'P3', 'lithotripsy', 'lithotripsy', 'was fragmented',
                    target=tg('', 'common_bile_duct', 'common bile duct', ['P3']),
                    technique=a('lithotripter', 'lithotripsy', ['P3']))


# --- (1) whose denial: a sentence of another supporting stone extraction ----------------------------------------------

W = {  # review:ercp6 problem 1's W1 and its members (round5f/review-ercp6/cases/cases-w.json), and Q4 (W7)
    'W1': (f'{REMOVED} The pancreatic duct was then swept with a balloon and no stones were seen.',
           lambda: second_sweep('swept with a balloon', ('balloon', 'balloon'))),
    'W2': ('The bile duct was swept with an extraction balloon and sludge was removed. The pancreatic duct was then '
           'swept with a basket and no stones were seen.', second_sweep),
    'W3': (f'{REMOVED} The duct was then swept again with a basket and no stones were seen.',
           lambda: second_sweep('swept again with a basket', duct=('bile_duct', 'The duct'))),
    'W4': (f'{REMOVED} The pancreatic duct was then swept with a basket. No stones remained.', second_sweep),
    'W5': ('The bile duct was swept with an extraction balloon, and two stones were removed. The pancreatic duct was '
           'then swept with a basket and no stones were seen.', second_sweep),
    'W7': (f'{REMOVED} The pancreatic duct was then swept with a basket and no stones were seen.', second_sweep),
}


class D168WhoseDenial(SimpleTestCase):
    def test_d168_1_w1_and_its_members_stay_ready_on_the_sweep_that_removed_the_stones(self):
        """review:ercp6 problem 1 (critical by the registry rule's 'READY on the wrong act' class, introduced by D159,
        constructed): W1 "The bile duct was swept with an extraction balloon and two stones were removed. The pancreatic
        duct was then swept with a balloon and no stones were seen." (E4 the bile-duct sweep, E5 the pancreatic sweep,
        both performed stone extractions), the sludge wording (W2), the basket's "no stones were seen" after the same
        duct swept again (W3), rule (3)'s "... two stones were removed. The pancreatic duct was then swept with a
        basket. No stones remained." (W4), the comma form (W5) and the basket on the pancreatic duct (W7, the review's
        Q4): READY
        on E4 and E5, Corti citing the passage or the sweep's own sentence, in both settings - as e5628be56, f9013e12e
        and 05a881a75 are; D159 was READY on E5 alone (W1-W5). c2e53f8e is READY on the sweep's act ('stone removal at
        the bile duct') on W1, on both acts on W2, W4, W5 and W7, and HELD conflict:stone_extraction on W3. The reader,
        beside E5: E4's own sentence states its yield (_clause_yield), so the denial in E5's words is E5's - no
        statement; read alone (no other act beside it), it is the sweep's statement, as D159 read it. DECISIONS D173 (2)
        (round 5h; review:ercp7 problem 0) changes W4's reader beside E5 only: "No stones remained." stands in a later
        sentence that holds no rival's words, so it is read again as the sweep's statement (D168 read every sentence
        past the rival's as the rival's); the outcome is unchanged - a widened statement only holds, and E4, whose own
        sentence states its yield, carries 43264 (D173 (3)), so READY on E4 and E5."""
        for name, (p5, second) in W.items():
            for cited in (REMOVED if p5.startswith(REMOVED) else p5.split('. ')[0] + '.', None):
                for chosen in PARTICIPANTS:
                    with self.subTest(w=name, cited=bool(cited), participants=len(chosen)):
                        ready_on(self, proposal(assessed(p5, cited, chosen, **SW, more=[second()]), '43264'),
                                 ('E4', 'E5'))
            with self.subTest(reader=name):
                if name == 'W4':  # DECISIONS D173 (2): the later sentence after the rival's is read again
                    self.assertEqual(statement(p5, ('E4', 'E5'), **SW, more=[second()]),
                                     [REMOVED, 'No stones remained'])
                else:
                    self.assertIsNone(statement(p5, ('E4', 'E5'), **SW, more=[second()]))
                self.assertIsNotNone(statement(p5, (), **SW, more=[second()]))

    def test_d168_1_the_other_sweeps_own_denial_leaves_the_code_ready_on_this_one(self):
        """This repair's own variants (constructed): the second sweep states its own retrieval denial, so it leaves E*
        by D155's reading, and the denial is never the bile-duct sweep's, whose own sentence states its yield - READY on
        E4, as at e5628be56, f9013e12e and 05a881a75 (D159's reads would hold the code: both acts 'retrieved nothing'):
        "... and two stones were removed. The pancreatic duct was then swept with a retrieval balloon and no stones were
        retrieved." (rule (1); c2e53f8e READY on the sweep's act with its sentence cited, HELD readings_disagree with
        the passage cited) and "... and two stones were removed. The pancreatic duct was then swept with a balloon. No
        stones were retrieved." (rule (3); c2e53f8e HELD conflict:stone_extraction), the second with the yield in the
        status words too (D147's reading; the same outcomes). DECISIONS D173 (2) (round 5h; review:ercp7 problem 0)
        changes the rule (3) form: its later sentence "No stones were retrieved." holds no rival's words, so it is read
        again, and a RETRIEVAL denial is read after an own yield (D168 (2)) - the sweep's statement too, so both sweeps
        state nothing retrieved and 43264 is held nothing_retrieved, as c2e53f8e holds it (conflict:stone_extraction);
        the rule (1) form, whose denial stands in the rival's own sentence, stays READY on E4."""
        retrieval = second_sweep('swept with a retrieval balloon', ('balloon', 'retrieval balloon'))
        p5 = f'{REMOVED} The pancreatic duct was then swept with a retrieval balloon and no stones were retrieved.'
        later = f'{REMOVED} The pancreatic duct was then swept with a balloon. No stones were retrieved.'
        balloon = second_sweep('swept with a balloon', ('balloon', 'balloon'))
        for text, more, options in ((p5, retrieval, SW), (later, balloon, SW), (later, balloon, OWN_YIELD)):
            for cited in (REMOVED, None):
                for chosen in PARTICIPANTS:
                    with self.subTest(p5=text[len(REMOVED):][:60], status=options['status_words'], cited=bool(cited),
                                      participants=len(chosen)):
                        p = proposal(assessed(text, cited, chosen, **options, more=[more]), '43264')
                        if text == later:  # DECISIONS D173 (2)
                            held_nothing_retrieved(self, p, f'{REMOVED} No stones were retrieved')
                        else:
                            ready_on(self, p, ('E4',))

    def test_d168_1_with_no_yield_of_its_own_the_denial_stays_the_acts(self):
        """Where this act's own sentence states no yield, a denial in another supporting stone extraction's words stays
        this act's statement, as D159 reads it: "The bile duct was swept with an extraction balloon. The pancreatic duct
        was then swept with a balloon and no stones were retrieved." (D159's rule (1) input, the pancreatic sweep filed)
        is held nothing_retrieved, the question quoting the sweep's sentence and the clause - READY on E4 at e5628be56,
        f9013e12e and 05a881a75; c2e53f8e HELD readings_disagree with the sweep's sentence cited, EXCLUDED with the
        passage cited. The reader, beside E5: the sweep's statement."""
        p5 = f'{SWEPT_ONCE} The pancreatic duct was then swept with a balloon and no stones were retrieved.'
        held_in_both(self, p5, p5[:-1], [pancreatic_sweep()])
        self.assertEqual(statement(p5, ('E4', 'E5'), **SW, more=[pancreatic_sweep()]),
                         [SWEPT_ONCE, p5[len(SWEPT_ONCE) + 1:-1]])

    def test_d168_1_the_conditions_bounds_recorded(self):
        """The condition as specified, its two bounds recorded (this repair's own inputs, constructed):
        - COST: the second sweep by ANOTHER performer ("... and two stones were removed. The pancreatic duct was then
          swept with a balloon by the referring physician and no stones were seen.", its performer verified another
          clinician) supports no code, so its words are no other supporting act's and the denial stays the bile-duct
          sweep's: held nothing_retrieved - READY on E4 at e5628be56, f9013e12e and 05a881a75; c2e53f8e READY on the
          sweep's act with its sentence cited, HELD readings_disagree with the passage cited.
        - RECORDED RESIDUAL: the own-yield reading takes D140's guards only, so a yield in a clause that tells another
          place ("The bile duct was swept with an extraction balloon after two stones were removed at an outside
          hospital.") is the sweep's own there, and the second sweep's denial is the second sweep's: READY on E4, as at
          e5628be56, f9013e12e and 05a881a75, where D159 held it and c2e53f8e HOLDS (readings_disagree) with the sweep's
          sentence cited and EXCLUDES with the passage cited - a pre-existing READY this repair leaves as it was, never
          one it makes."""
        other = ercp_act('E5', 'P5', 'stone_extraction', 'swept with a balloon', 'was then swept',
                         target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                         performer=a('other_clinician', 'the referring physician', ['P5']))
        p5 = (f'{REMOVED} The pancreatic duct was then swept with a balloon by the referring physician and no stones '
              'were seen.')
        held_in_both(self, p5, f'{REMOVED} The pancreatic duct was then swept with a balloon by the referring '
                     'physician and no stones were seen', [other], citations=(REMOVED, None))
        after = ('The bile duct was swept with an extraction balloon after two stones were removed at an outside '
                 'hospital.')
        retrieval = second_sweep('swept with a retrieval balloon', ('balloon', 'retrieval balloon'))
        ready_in_both(self, f'{after} The pancreatic duct was then swept with a retrieval balloon and no stones were '
                      'retrieved.', [retrieval], citations=(after, None))

    def test_d168_1_a_widened_statement_only_holds_the_code(self):
        """A statement only the widened reads give never takes an act out of E* while another act supports the code -
        a READY whose acts change is a move this round's rule forbids. "The bile duct was swept with an extraction
        balloon. Two stones were extracted with a basket and no stones were seen on the final cholangiogram." (the
        ercp6 builder's control, the basket filed) and "The bile duct was swept with an extraction balloon. The
        pancreatic duct was then swept with a balloon and no stones were seen." (this repair's own): the sweep's own
        sentence states no yield, so the denial in the other act's clause is the sweep's statement (the reader), but
        43264 stays READY on E4 and E5, as at e5628be56, f9013e12e and 05a881a75. D159 was READY on E5 alone on both.
        c2e53f8e: READY on its act 'stone removal (basket)' on the first; HELD readings_disagree on the second.
        DECISIONS D173 (3) (round 5h; review:ercp7 problem 1, WV4) changes the second's outcome: the pancreatic sweep
        states nothing either (no yield, no finding), so no act E* keeps carries 43264, and the denial stays the
        bile-duct sweep's statement - held nothing_retrieved, the question quoting it, as c2e53f8e holds it. The first
        stays READY on E4 and E5: the basket's own sentence states its yield. E* still moves only by D155's reading."""
        seen = (f'{SWEPT_ONCE} Two stones were extracted with a basket and no stones were seen on the final '
                'cholangiogram.')
        none_seen = f'{SWEPT_ONCE} The pancreatic duct was then swept with a balloon and no stones were seen.'
        for p5, other in ((seen, basket()), (none_seen, second_sweep('swept with a balloon', ('balloon', 'balloon')))):
            if p5 == none_seen:  # DECISIONS D173 (3)
                held_in_both(self, p5, p5[:-1], [other])
            else:
                ready_in_both(self, p5, [other], acts=('E4', 'E5'))
            with self.subTest(reader=p5[len(SWEPT_ONCE):][:40]):
                self.assertEqual(statement(p5, ('E4', 'E5'), **SW, more=[other]),
                                 [SWEPT_ONCE, p5[len(SWEPT_ONCE) + 1:-1]])
                inv, text, doc = sweep(p5, **SW, more=[other])
                reading = events.Reading.of(inv)
                self.assertIsNone(ercp.nothing_retrieved(reading, reading.events['E4'], (), ('E4', 'E5'),
                                                         widened=False))


# --- (1) D159's rule (1): the dropped sentence's denial clause, whatever other events' words it holds -----------------

NO_BREAK = 'No stones were retrieved and a plastic biliary stent was placed.'
BECAUSE = 'A plastic biliary stent was placed because no stones were retrieved.'
PANCREATIC_AND = 'The pancreatic duct was then swept with a balloon and no stones were retrieved.'


class D168DenialClause(SimpleTestCase):
    def test_d168_1_ercp5s_three_no_break_forms_hold_as_the_semicolon_forms_do(self):
        """Carried over from D159 (round5f/ercp6's test_d159_1_ercp5s_three_no_break_forms_hold_as_the_semicolon_forms
        _do): "...No stones were retrieved and a plastic biliary stent was placed.", "...A plastic biliary stent was
        placed because no stones were retrieved." (the stent filed) and "...The pancreatic duct was then swept with a
        balloon and no stones were retrieved." (the pancreatic sweep filed). D155 never read a clause that holds another
        act's words; now it is the sweep's statement (its own sentence states no yield): 43264 held nothing_retrieved,
        the question quoting the sweep's sentence and the clause whole, Corti citing the sweep's sentence or the whole
        passage. READY on E4 at e5628be56, f9013e12e and 05a881a75; c2e53f8e HOLDS each (readings_disagree) with the
        sweep's sentence cited and EXCLUDES each with the passage cited."""
        held_in_both(self, f'{SWEPT_ONCE} {NO_BREAK}', f'{SWEPT_ONCE} {NO_BREAK[:-1]}', [stent()])
        held_in_both(self, f'{SWEPT_ONCE} {BECAUSE}', f'{SWEPT_ONCE} {BECAUSE[:-1]}', [stent()])
        held_in_both(self, f'{SWEPT_ONCE} {PANCREATIC_AND}', f'{SWEPT_ONCE} {PANCREATIC_AND[:-1]}',
                     [pancreatic_sweep()])
        for second, more in ((NO_BREAK, [stent()]), (BECAUSE, [stent()]), (PANCREATIC_AND, [pancreatic_sweep()])):
            with self.subTest(reader=second):
                self.assertEqual(statement(f'{SWEPT_ONCE} {second}', **SW, more=more), [SWEPT_ONCE, second[:-1]])

    def test_d168_1_the_other_no_break_forms(self):
        """Carried over from D159: review:ercp5 problem 5's second input, "...A plastic biliary stent was placed but no
        stones were retrieved." (the stent filed), and the ercp6 builder's variants (constructed): "No stones were seen
        and a plastic biliary stent was placed.", "A plastic biliary stent was placed and no stones remained." and "No
        stones were extracted and a 5 Fr pancreatic stent was placed for prophylaxis." (the pancreatic stent filed).
        Each held nothing_retrieved. READY on E4 at e5628be56, f9013e12e and 05a881a75; c2e53f8e HOLDS the 'but' form
        (readings_disagree; EXCLUDED with the passage cited), the first presence form (act_missing) and the second
        (readings_disagree), and the pancreatic stent (readings_disagree; EXCLUDED with the passage cited)."""
        shapes = (('A plastic biliary stent was placed but no stones were retrieved.', [stent()]),
                  ('No stones were seen and a plastic biliary stent was placed.', [stent()]),
                  ('A plastic biliary stent was placed and no stones remained.', [stent()]),
                  ('No stones were extracted and a 5 Fr pancreatic stent was placed for prophylaxis.',
                   [pancreatic_stent()]))
        for second, more in shapes:
            held_in_both(self, f'{SWEPT_ONCE} {second}', f'{SWEPT_ONCE} {second[:-1]}', more)

    def test_d168_1_controls(self):
        """Carried over from D159's controls (constructed), each as on every new-path tree: the dropped sentence's
        clause with no denial ("A plastic biliary stent was placed and sludge was retrieved.") or an exceptive one ("No
        further stones were seen and a plastic biliary stent was placed.") states nothing - READY on E4 (c2e53f8e
        READY, and HELD act_missing / READY on the exceptive form); the denial also filed as its own event is D140's
        (the sentence read whole) - held, as at e5628be56, f9013e12e and 05a881a75 (c2e53f8e HELD readings_disagree with
        the sweep's sentence cited, EXCLUDED with the passage cited). DECISIONS D173 (6) (round 5h; refute6 judges
        finding 9) changes the exceptive form's outcome: the sweep states no yield (an exceptive denial states none
        either) and is done to no finding, so 43264 is held no_yield - c2e53f8e HELD act_missing with the sweep's
        sentence cited, READY with the passage cited (a COST there). "... and sludge was retrieved." states the sweep's
        yield in the sentence that continues it (a free clause, as D155 reads one for a denial), so it stays READY."""
        for second in ('A plastic biliary stent was placed and sludge was retrieved.',
                       'No further stones were seen and a plastic biliary stent was placed.'):
            if second.startswith('No further'):  # DECISIONS D173 (6)
                for cited in (SWEPT_ONCE, None):
                    for chosen in PARTICIPANTS:
                        with self.subTest(p5=second[:40], cited=bool(cited), participants=len(chosen)):
                            p = proposal(assessed(f'{SWEPT_ONCE} {second}', cited, chosen, **SW, more=[stent()]),
                                         '43264')
                            self.assertEqual((p.status, asked(p), p.support['reason']),
                                             ('needs_clarification', ['performed_status'], ercp.NO_YIELD))
            else:
                ready_in_both(self, f'{SWEPT_ONCE} {second}', [stent()])
            with self.subTest(reader=second):
                self.assertIsNone(statement(f'{SWEPT_ONCE} {second}', **SW, more=[stent()]))
        held_in_both(self, f'{SWEPT_ONCE} {NO_BREAK}', f'{SWEPT_ONCE} {NO_BREAK}', [stent(), denial()])

    def test_d168_1_recorded_costs(self):
        """Carried over from D159's COSTS (constructed; c2e53f8e READY, HELD readings_disagree on the second with the
        passage cited; e5628be56, f9013e12e and 05a881a75 READY on E4): the dropped sentence states a yield, but in a
        clause that holds another act's words or that D140's subject rule does not read, and denies the stones' presence
        in a clause rule (1) now reads - "Two stones were then extracted with a basket and no stones were seen on the
        final cholangiogram." (the basket's status words 'were then extracted': no yield read across 'then', so the
        basket's own sentence states nothing retrieved too, and the sweep's own sentence states no yield), "Two stones
        were retrieved; no stones remained and a plastic biliary stent was placed." and "A plastic biliary stent was
        placed after two stones were retrieved and no stones remained." Held nothing_retrieved: fail-closed holds of the
        right code."""
        then = basket('were then extracted')
        held_in_both(self, f'{SWEPT_ONCE} Two stones were then extracted with a basket and no stones were seen on the '
                     'final cholangiogram.', f'{SWEPT_ONCE} Two stones were then extracted with a basket and no stones '
                     'were seen on the final cholangiogram', [then])
        held_in_both(self, f'{SWEPT_ONCE} Two stones were retrieved; no stones remained and a plastic biliary stent '
                     'was placed.', f'{SWEPT_ONCE} no stones remained and a plastic biliary stent was placed',
                     [stent()])
        held_in_both(self, f'{SWEPT_ONCE} A plastic biliary stent was placed after two stones were retrieved and no '
                     'stones remained.', f'{SWEPT_ONCE} A plastic biliary stent was placed after two stones were '
                     'retrieved and no stones remained', [stent()])


# --- (1) D159's rule (3): a denial clause in a later sentence of the act's own passage --------------------------------

TWO_ON = ('The bile duct was swept with an extraction balloon. A plastic biliary stent was placed. No stones were '
          'retrieved.')


class D168LaterSentence(SimpleTestCase):
    def test_d168_1_review_ercp5_problem_5_the_denial_two_sentences_on(self):
        """Carried over from D159: review:ercp5 problem 5 (pre-existing, critical by the rubric): "The bile duct was
        swept with an extraction balloon. A plastic biliary stent was placed. No stones were retrieved." with the stent
        filed - the sweep's statement: 43264 held nothing_retrieved, the question quoting the sweep's sentence and the
        denial. READY on E4 at e5628be56, f9013e12e and 05a881a75; c2e53f8e HOLDS it (readings_disagree) with the
        sweep's sentence cited and EXCLUDES it with the passage cited."""
        held_in_both(self, TWO_ON, f'{SWEPT_ONCE} No stones were retrieved', [stent()])
        self.assertEqual(statement(TWO_ON, **SW, more=[stent()]), [SWEPT_ONCE, 'No stones were retrieved'])

    def test_d168_1_the_later_denial_wherever_it_stands(self):
        """Carried over from D159 (the ercp6 builder's variants, constructed), each READY on E4 at e5628be56, f9013e12e
        and 05a881a75 and held nothing_retrieved now: the presence denials "No stones remained." (c2e53f8e HELD
        act_missing) and "No stones were seen on the final cholangiogram." (HELD act_missing) two sentences on; the
        retrieval denied three sentences on, after a second stent (c2e53f8e HELD readings_disagree; EXCLUDED with the
        passage cited); the denial clause of a later sentence beside another act's clause ("No stones were retrieved,
        and a 5 Fr pancreatic stent was placed.", c2e53f8e HELD readings_disagree; EXCLUDED); a later denial naming
        another duct ("No stones were retrieved from the pancreatic duct.", the pancreatic stent filed: c2e53f8e HELD
        readings_disagree; EXCLUDED - a fail-closed hold); and the denial after a sentence that names no act ("The duct
        was irrigated.", the sweep alone filed: c2e53f8e HELD readings_disagree; EXCLUDED)."""
        second_stent = stent('E6', kind_words='5 Fr pancreatic stent',
                             target=tg('', 'pancreatic_duct', 'pancreatic', ['P5']))
        shapes = (('A plastic biliary stent was placed. No stones remained.', 'No stones remained', [stent()]),
                  ('A plastic biliary stent was placed. No stones were seen on the final cholangiogram.',
                   'No stones were seen on the final cholangiogram', [stent()]),
                  ('A plastic biliary stent was placed. A 5 Fr pancreatic stent was placed for prophylaxis. No stones '
                   'were retrieved.', 'No stones were retrieved', [stent(), second_stent]),
                  ('A plastic biliary stent was placed. No stones were retrieved, and a 5 Fr pancreatic stent was '
                   'placed.', 'No stones were retrieved', [stent(), second_stent]),
                  ('A 5 Fr pancreatic stent was placed. No stones were retrieved from the pancreatic duct.',
                   'No stones were retrieved from the pancreatic duct', [pancreatic_stent()]),
                  ('The duct was irrigated. No stones were retrieved.', 'No stones were retrieved', []))
        for rest, clause, more in shapes:
            held_in_both(self, f'{SWEPT_ONCE} {rest}', f'{SWEPT_ONCE} {clause}', more)
            with self.subTest(reader=rest):
                self.assertEqual(statement(f'{SWEPT_ONCE} {rest}', **SW, more=more), [SWEPT_ONCE, clause])

    def test_d168_1_controls_and_residuals(self):
        """Carried over from D159's controls (constructed), each READY on E4 as on every new-path tree: the denial in
        ANOTHER passage (its own line: c2e53f8e HELD readings_disagree), the denial BEFORE the act's own sentence
        (c2e53f8e HELD act_missing / READY), an exceptive later denial ("No further stones were seen.", c2e53f8e HELD
        act_missing), and - the clause condition as specified, a RECORDED RESIDUAL - a later denial in a clause that
        holds another event's words: the plan's ("No stones were retrieved and a repeat ERCP is planned.", the plan
        filed), the denial Gemini files as its own event, and another act's with no clause break ("No stones were
        retrieved and a 5 Fr pancreatic stent was placed."): c2e53f8e HOLDS each (readings_disagree) with the sweep's
        sentence cited and EXCLUDES each with the passage cited. And only the act's OWN passage is read (EB1): with
        Gemini's passage for the sweep its sentence alone and the stent's passage the whole line, the later denial is
        in no passage of the sweep's - a RECORDED RESIDUAL, READY on E4 as on every new-path tree (c2e53f8e HELD
        readings_disagree; EXCLUDED with the passage cited). DECISIONS D173 (6) (round 5h; refute6 judges finding 9)
        changes every outcome here, never the reader: in each the sweep's own sentence ("The bile duct was swept with an
        extraction balloon.") states no yield, nothing after it does, and the sweep is done to no finding the inventory
        lists, so 43264 is held no_yield - as c2e53f8e holds each (act_missing or readings_disagree), but for the
        denial before the sweep's sentence, which it READYs with the passage cited (a COST there)."""
        def no_yield_in_both(p5: str, more, citations=(SWEPT_ONCE, None), **options) -> None:
            for cited in citations:
                for chosen in PARTICIPANTS:
                    with self.subTest(p5=p5[len(SWEPT_ONCE):][:70], cited=bool(cited), participants=len(chosen)):
                        p = proposal(assessed(p5, cited, chosen, **dict(SW, **options), more=more), '43264')
                        self.assertEqual((p.bucket, p.status, asked(p), p.support['reason'], p.support['acts']),
                                         ('selected', 'needs_clarification', ['performed_status'], ercp.NO_YIELD, []))

        no_yield_in_both(f'{SWEPT_ONCE} A plastic biliary stent was placed.', [stent()],
                         more_lines={'P6': 'No stones were retrieved.'})
        overlapping = dict(passages={'P5': SWEPT_ONCE, 'P7': TWO_ON})
        no_yield_in_both(TWO_ON, [ercp_act('E5', 'P7', 'stent', 'plastic biliary stent', 'was placed')], **overlapping)
        with self.subTest(reader='overlapping passage'):
            self.assertIsNone(statement(TWO_ON, **SW, **overlapping,
                                        more=[ercp_act('E5', 'P7', 'stent', 'plastic biliary stent', 'was placed')]))
        no_yield_in_both(f'No stones were seen. {SWEPT_ONCE}', [])
        no_yield_in_both(f'{SWEPT_ONCE} A plastic biliary stent was placed. No further stones were seen.', [stent()])
        second_stent = stent('E6', kind_words='5 Fr pancreatic stent',
                             target=tg('', 'pancreatic_duct', 'pancreatic', ['P5']))
        for rest, more in (('A plastic biliary stent was placed. No stones were retrieved and a repeat ERCP is '
                             'planned.', [stent(), plan()]),
                           ('A plastic biliary stent was placed. No stones were retrieved.', [stent(), denial()]),
                           ('A plastic biliary stent was placed. No stones were retrieved and a 5 Fr pancreatic stent '
                            'was placed.', [stent(), second_stent])):
            no_yield_in_both(f'{SWEPT_ONCE} {rest}', more)
            with self.subTest(reader=rest):
                self.assertIsNone(statement(f'{SWEPT_ONCE} {rest}', **SW, more=more))

    def test_d168_1_later_sentence_recorded_costs(self):
        """Carried over from D159's COSTS (constructed; c2e53f8e READY, HELD conflict:stone_extraction on the last; READY
        on E4 at e5628be56, f9013e12e and 05a881a75): a yield stated outside the act's own sentence never clears the
        later denial - the sentences after the act's own are read for a denial only - so "A plastic biliary stent was
        placed. Two stones were retrieved; no stones remained.", "Two stones were retrieved. A plastic biliary stent was
        placed. No stones remained." and "Two stones were retrieved, and a plastic biliary stent was placed. No stones
        remained." are held nothing_retrieved, and so is "Two stones were retrieved. A plastic biliary stent was placed.
        No sludge was retrieved.". And this repair's own (constructed): "The bile duct was swept with an extraction
        balloon and two stones were removed. A plastic biliary stent was placed. No stones remained." with the sweep's
        status words 'was swept' - D147's simple-clause reading states no yield there, and the clause reading
        (_clause_yield) is read only beside another supporting stone extraction, so the later presence denial holds it:
        a COST (c2e53f8e READY on the sweep's act; READY on E4 at e5628be56, f9013e12e and 05a881a75). With the yield in
        the status words ('were removed') it is the clearance, READY (D168YieldGuard)."""
        for rest, clause in (('A plastic biliary stent was placed. Two stones were retrieved; no stones remained.',
                              'no stones remained'),
                             ('Two stones were retrieved. A plastic biliary stent was placed. No stones remained.',
                              'No stones remained'),
                             ('Two stones were retrieved, and a plastic biliary stent was placed. No stones remained.',
                              'No stones remained'),
                             ('Two stones were retrieved. A plastic biliary stent was placed. No sludge was retrieved.',
                              'No sludge was retrieved')):
            held_in_both(self, f'{SWEPT_ONCE} {rest}', f'{SWEPT_ONCE} {clause}', [stent()])
        held_in_both(self, f'{REMOVED} A plastic biliary stent was placed. No stones remained.',
                     f'{REMOVED} No stones remained', [stent()], citations=(REMOVED, None))


class D168ClearanceNotBuilt(SimpleTestCase):
    def test_d168_1_the_free_yield_clearance_is_still_not_built(self):
        """Carried over from D159's stopped (2) (round5f/ercp6 and review:ercp6 problem 2: justified): a clearance of
        the dropped sentence's presence denial beside a yield clause that holds no other event's own words would release
        43264 where the document states an earlier, another performer's or a doubted yield - "Two stones were retrieved
        at an outside hospital in 2023; no stones remained, and ..." (c2e53f8e HELD act_missing), "Stones were removed
        two weeks ago; no stones were found, and ..." (HELD act_missing; EXCLUDED with the passage cited), "Stones were
        removed by the referring gastroenterologist; no stones were seen, and ..." (HELD act_missing) and "Presumed
        stones were removed; no stones remained, and ..." (HELD act_missing). It is not built, so each stays held, as
        at f9013e12e and 05a881a75 (READY on E4 at e5628be56), and so do review:ercp5 problem 2's six documents
        (RECORDED COSTS: c2e53f8e READY with the sweep's sentence cited)."""
        tail = ', and a plastic biliary stent was placed.'
        for first, clause in (('Two stones were retrieved at an outside hospital in 2023; no stones remained',
                               'no stones remained'),
                              ('Stones were removed two weeks ago; no stones were found', 'no stones were found'),
                              ('Stones were removed by the referring gastroenterologist; no stones were seen',
                               'no stones were seen'),
                              ('Presumed stones were removed; no stones remained', 'no stones remained'),
                              ('Two stones were retrieved; no stones remained', 'no stones remained'),
                              ('Sludge was retrieved; no stones were seen', 'no stones were seen')):
            held_in_both(self, f'{SWEPT_ONCE} {first}{tail}', f'{SWEPT_ONCE} {clause}', [stent()])
        for second, clause in (('Several small stones were removed, no stones remained, and a plastic biliary stent '
                                'was placed.', 'no stones remained'),
                               ('Three stones were removed, no stones were seen on the final cholangiogram, and a '
                                'plastic biliary stent was placed.', 'no stones were seen on the final cholangiogram'),
                               ('Several stones were extracted and no stones remained; a plastic biliary stent was '
                                'placed.', 'Several stones were extracted and no stones remained')):
            held_in_both(self, f'{SWEPT_ONCE} {second}', f'{SWEPT_ONCE} {clause}', [stent()])
        basket_sweep = ercp_act('E5', 'P5', 'stone_extraction', 'swept with a basket', 'was then swept',
                                target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                                technique=a('basket', 'basket', ['P5']))
        held_in_both(self, f'{SWEPT_ONCE} The pancreatic duct was then swept with a basket, and two stones were '
                     'removed; no stones were seen on the final cholangiogram.',
                     f'{SWEPT_ONCE} no stones were seen on the final cholangiogram', [basket_sweep])


# --- (2) the yield guard: a later RETRIEVAL denial after an own yield (review:ercp6 problem 3) ------------------------

class D168YieldGuard(SimpleTestCase):
    def test_d168_2_a_later_retrieval_denial_after_an_own_yield_holds(self):
        """review:ercp6 problem 3 (pre-existing, critical by the rubric, constructed): "The bile duct was swept with an
        extraction balloon and two stones were removed. A plastic biliary stent was placed. No stones were retrieved."
        (status words 'were removed', the stent filed, the passage cited): READY on E4 at e5628be56, f9013e12e and
        05a881a75 (and at D159, which read nothing after an own yield); c2e53f8e HELD conflict:stone_extraction. Now the
        later RETRIEVAL denial is read, as D127 reads one in the own sentence (review-ercp6/variants/ercp-review-
        yieldguard.py): held nothing_retrieved, in both settings, Corti citing the passage or the sweep's sentence; and
        so is "No sludge was retrieved." there (c2e53f8e HELD conflict:stone_extraction)."""
        for last in ('No stones were retrieved', 'No sludge was retrieved'):
            held_in_both(self, f'{REMOVED} A plastic biliary stent was placed. {last}.', f'{REMOVED} {last}', [stent()],
                         citations=(None, REMOVED), status_words='were removed')

    def test_d168_2_the_clearance_and_the_next_sentence_stay_ready(self):
        """Controls (constructed): after the same own yield, a later PRESENCE denial is still a clearance - "... two
        stones were removed. A plastic biliary stent was placed. No stones remained." READY on E4 (c2e53f8e READY, as
        every new-path tree) - and an exceptive later retrieval denial states nothing ("No further stones were
        retrieved.": READY on every new-path tree; c2e53f8e HELD readings_disagree with the passage cited, READY with
        the sweep's sentence cited). RECORDED RESIDUAL, D127's design and
        outside (2): the retrieval denied in the sentence IMMEDIATELY after an own yield ("... two stones were removed.
        No stones were retrieved.") is not read - READY on E4 on every new-path tree; c2e53f8e HELD
        conflict:stone_extraction."""
        for rest, more in (('A plastic biliary stent was placed. No stones remained.', [stent()]),
                           ('A plastic biliary stent was placed. No further stones were retrieved.', [stent()]),
                           ('No stones were retrieved.', [])):
            ready_in_both(self, f'{REMOVED} {rest}', more, citations=(None, REMOVED), status_words='were removed')


# --- (3) the ERCP question beside the another_role hold (review:colon5 problem 0) -------------------------------------

PLACED = {'one-line': SIGNED + EXCHANGE['P5'],
          'wrapped': SIGNED + 'A new 10 Fr x 9 cm plastic\nbiliary stent was placed into the common bile duct.'}
SWEPT = {'one-line': SIGNED + 'The bile duct was swept several times with an extraction balloon; no stones or sludge '
                              'were retrieved.',
         'wrapped': SIGNED + 'The bile duct\nwas swept several times with an extraction balloon; no stones or sludge '
                             'were retrieved.'}


def signed_exchange(p5: str, p3: str = EXCHANGE['P3']):
    """Finding 22's document (tests.test_interpretation_r4_ercp.EXCHANGE) with ``p5`` for the placement line and ``p3``
    for the removal's, as review-colon5's tools/cases.py builds it: the duodenoscope (E1), the snare removal (E2), the
    cannulation (E3) and the placement (E4, its kind 'stent' and status 'was placed')."""
    lines = dict(EXCHANGE, P3=p3, P5=p5)
    built = [exam('E1', 'P2', words='duodenoscope', procedure=a('ercp')),
             act('E2', 'P3', 'stent_removal', 'removed', status_words='was removed with a snare', procedure=a('ercp'),
                 technique=a('snare', 'snare', ['P3']), target=tg('', 'bile_duct', 'biliary', ['P3'])),
             act('E3', 'P4', 'cannulation', 'Deep biliary cannulation', status_words='was achieved',
                 procedure=a('ercp'), target=tg('', 'bile_duct', 'biliary', ['P4']),
                 technique=a('sphincterotome', 'sphincterotome', ['P4'])),
             act('E4', 'P5', 'stent', 'stent', status_words='was placed', procedure=a('ercp'),
                 technique=a('stent', 'plastic', ['P5']),
                 target=tg('', 'common_bile_duct', 'common bile duct', ['P5']))]
    inv, text = inventory(lines, events=built, reach=[reached('E1', 'ampulla', 'major papilla', 'P2')])
    return inv, text, lines


def role_held_with_second(test, p, starts: str, events_=('E4',)) -> None:
    """``p`` held another_role (its own question first, naming the nursing entry) with the ERCP rule's question second,
    which starts ``starts``."""
    test.assertEqual((p.bucket, p.status, p.support['reason'], [item['id'] for item in p.support['acts']],
                      p.support.get('question_events')),
                     ('selected', 'needs_clarification', events.ANOTHER_ROLE, list(events_), list(events_)))
    test.assertEqual(asked(p), ['performed_status', 'performed_status'])
    test.assertIn('documented only in the nursing entry', p.clarifications[0].question)
    test.assertTrue(p.clarifications[1].question.startswith(starts), p.clarifications[1].question)


class D168RoleSecond(SimpleTestCase):
    def test_d168_3_the_exchange_question_is_the_role_holds_second(self):
        """review:colon5 problem 0 (medium; the class on f9013e12e for the one-line signed form, D158 extends it to the
        wrapped one), (a): finding 22's document with the placement line "Documented by Jo Rowe, RN: A 10 Fr x 9 cm
        plastic biliary stent was placed into the common bile duct." (one line) or "Documented by Jo Rowe, RN: A new 10
        Fr x 9 cm plastic" / "biliary stent was placed into the common bile duct." (wrapped), 43274 cited at it alone,
        beside 43275 or 43276, in both settings. 05a881a75 holds 43274 another_role and asks the exchange question
        nowhere; e5628be56 holds it possible_exchange (both forms), f9013e12e another_role (one line) and
        possible_exchange (wrapped); c2e53f8e READY. Now: held another_role, its question first, and D105's exchange
        question ("Were the stent removal (snare) ... one stent exchange (43276), or separate services ...?") second;
        43275 and 43276 keep the exchange hold, as on every new-path tree (c2e53f8e HELD act_missing). And with the
        REMOVAL line signed and wrapped (this repair's own), 43275 is held another_role with the exchange question
        second (e5628be56 and f9013e12e: possible_exchange)."""
        for form, p5 in PLACED.items():
            inv, text, lines = signed_exchange(p5)
            for chosen in (('43274',), ('43275', '43274'), ('43274', '43276')):
                phrases = {'43275': lines['P3'], '43274': lines['P5'], '43276': lines['P1']}
                for participants in PARTICIPANTS:
                    with self.subTest(form=form, codes=chosen, participants=len(participants)):
                        result = run(inv, text, [(code, phrases[code]) for code in chosen], participants=participants)
                        role_held_with_second(self, proposal(result, '43274'), 'Were the stent removal (snare)')
                        second = proposal(result, '43274').clarifications[1].question
                        self.assertIn('one stent exchange (43276)', second)
                        for code in chosen[:1] if chosen[0] != '43274' else chosen[1:]:
                            other = proposal(result, code)
                            self.assertEqual((other.support['reason'], asked(other)),
                                             (ercp.POSSIBLE_EXCHANGE, ['performed_status']))
        removal = SIGNED + 'The existing biliary stent\nwas removed with a snare.'
        inv, text, lines = signed_exchange(EXCHANGE['P5'], removal)
        for participants in PARTICIPANTS:
            with self.subTest(form='removal signed', participants=len(participants)):
                result = run(inv, text, [('43275', lines['P3'])], participants=participants)
                role_held_with_second(self, proposal(result, '43275'), 'Were the stent removal (snare)', ('E2',))

    def test_d168_3_the_retrieval_question_is_the_role_holds_second(self):
        """review:colon5 problem 0 (b): finding 25's sweep (tests.test_interpretation_r4_ercp.balloon_sweep) with P5
        "Documented by Jo Rowe, RN: The bile duct was swept several times with an extraction balloon; no stones or
        sludge were retrieved." (one line) or hard-wrapped after "The bile duct", 43264 cited at P5, in both settings.
        05a881a75 holds 43264 another_role and asks D106's question nowhere; e5628be56 holds it nothing_retrieved (both
        forms), f9013e12e another_role (one line) and nothing_retrieved (wrapped); c2e53f8e EXCLUDES it (act_denied).
        Now: held another_role, its question first, and D106's "Was any stone, calculus, debris or sludge removed with
        the stone removal ...?" second, quoting the statement; the sphincterotomy's 43262 stays READY."""
        for form, p5 in SWEPT.items():
            inv, text, lines = balloon_sweep(p5)
            for participants in PARTICIPANTS:
                with self.subTest(form=form, participants=len(participants)):
                    result = run(inv, text, [('43262', lines['P4']), ('43264', p5)], participants=participants)
                    held = proposal(result, '43264')
                    role_held_with_second(self, held, 'Was any stone, calculus, debris or sludge removed with the '
                                                      'stone removal')
                    self.assertIn('no stones or sludge were r', held.clarifications[1].question)
                    self.assertIn('nothing was retrieved', held.clarifications[1].reason)
                    self.assertEqual(proposal(result, '43262').status, 'ready')

    def test_d168_3_controls_and_the_evaluation(self):
        """Controls, each as on every new-path tree: the unsigned forms keep the ERCP hold as their ONE question
        (possible_exchange, nothing_retrieved; c2e53f8e: 43274 READY, 43264 EXCLUDED); a signed sweep that states its
        yield ("...; two stones were retrieved.") and a signed placement with no removal beside it (finding 22's
        document without P3's removal) ask no ERCP question - the another_role question is their one performed_status
        question, beside the cannulation fact the documents leave open (05a881a75 alike; e5628be56 READY on the sweep
        and HELD cannulation on the placement; c2e53f8e HELD readings_disagree on the sweep, READY on the placement).
        The evaluation (events.evaluate, every reader's): the hold's reason, question, read events and empty E* are the
        another_role hold's; ``second`` is the ERCP rule's question."""
        inv, text, lines = signed_exchange(EXCHANGE['P5'])
        p = proposal(run(inv, text, [('43274', lines['P5'])]), '43274')
        self.assertEqual((p.support['reason'], asked(p)), (ercp.POSSIBLE_EXCHANGE, ['performed_status']))
        inv, text, lines = balloon_sweep()
        p = proposal(run(inv, text, [('43264', lines['P5'])]), '43264')
        self.assertEqual((p.support['reason'], asked(p)), (ercp.NOTHING_RETRIEVED, ['performed_status']))
        yielded = SIGNED + ('The bile duct was swept several times with an extraction balloon; two stones were '
                            'retrieved.')
        inv, text, lines = balloon_sweep(yielded)
        p = proposal(run(inv, text, [('43264', yielded)]), '43264')
        self.assertEqual((p.support['reason'], asked(p).count('performed_status')), (events.ANOTHER_ROLE, 1))
        self.assertFalse(any(spec.question.startswith('Was any stone') for spec in p.clarifications))
        alone = SIGNED + EXCHANGE['P5']
        lines = dict(EXCHANGE, P5=alone)
        lines.pop('P3')
        built = [exam('E1', 'P2', words='duodenoscope', procedure=a('ercp')),
                 act('E4', 'P5', 'stent', 'stent', status_words='was placed', procedure=a('ercp'),
                     technique=a('stent', 'plastic', ['P5']),
                     target=tg('', 'common_bile_duct', 'common bile duct', ['P5']))]
        inv, text = inventory(lines, events=built, reach=[reached('E1', 'ampulla', 'major papilla', 'P2')])
        p = proposal(run(inv, text, [('43274', alone)]), '43274')
        self.assertEqual((p.support['reason'], asked(p).count('performed_status')), (events.ANOTHER_ROLE, 1))
        self.assertFalse(any('one stent exchange' in spec.question for spec in p.clarifications))
        inv, text, lines = signed_exchange(PLACED['wrapped'])
        reading = events.Reading.of(inv)
        reading.text = text  # as assess.assess hands it over (DECISIONS D124)
        evaluation = events.evaluate('43274', (), reading)
        self.assertEqual((evaluation.reason, evaluation.supporting, evaluation.read, evaluation.question.events),
                         (events.ANOTHER_ROLE, (), ('E4',), ('E4',)))
        self.assertEqual((evaluation.second.fact, evaluation.second.events), (ercp.EXCHANGE_FACT, ('E2', 'E4')))
        self.assertTrue(evaluation.second.question.startswith('Were the stent removal (snare)'))


# --- (4) the rival 43265 beside the 43264 these rules hold (review:ercp6 problem 4; D163 as integrated, G4) -----------

class D168Rival(SimpleTestCase):
    def test_d168_4_43265_is_held_competing_codes_beside_the_held_43264(self):
        """review:ercp6 problem 4 (low, test strength): D159Rival asserted only that 43265 was not excluded. On D159's
        shapes - finding 5's lithotripsy (P3 'A 15 mm stone in the common bile duct was fragmented with mechanical
        lithotripsy.', E8 performed) beside the sweep, 43265 cited at P3, and the denial in a no-break clause (rule (1):
        "No stones were retrieved and a plastic biliary stent was placed."), with 'because' (rule (1)) or two sentences
        on (rule (3)) - 43265 is HELD with the competing_codes question, never READY, in both settings and citations,
        and 43264 held nothing_retrieved asks performed_status and competing_codes: the held code keeps its acts as
        claims (assess._claims, D163 as integrated: G4). e5628be56, f9013e12e and 05a881a75 hold both codes
        competing_codes (43264 is READY on E4 for the per-code rule there); D159 alone released 43265 (review:ercp6
        problem 0); c2e53f8e HOLDS both conflict:stone_extraction (and competing_codes too, in the read setting with the
        sweep's sentence cited, on the no-break and two-on forms and the 'because' form)."""
        for p5 in (f'{SWEPT_ONCE} {NO_BREAK}', f'{SWEPT_ONCE} {BECAUSE}', TWO_ON):
            for cited in (SWEPT_ONCE, None):
                for chosen in PARTICIPANTS:
                    with self.subTest(p5=p5[len(SWEPT_ONCE):][:60], cited=bool(cited), participants=len(chosen)):
                        result = assessed(p5, cited, chosen, codes=[('43265', LITHO_P3)], **SW,
                                          more_lines={'P3': LITHO_P3}, more=[stent(), lithotripsy()])
                        p = proposal(result, '43264')
                        self.assertEqual((p.bucket, p.status, p.support['reason'], p.support['acts']),
                                         ('selected', 'needs_clarification', ercp.NOTHING_RETRIEVED, []))
                        self.assertEqual(sorted(asked(p)), ['competing_codes', 'performed_status'])
                        rival = proposal(result, '43265')
                        self.assertEqual((rival.bucket, rival.status), ('selected', 'needs_clarification'))
                        self.assertIn('competing_codes', asked(rival))
