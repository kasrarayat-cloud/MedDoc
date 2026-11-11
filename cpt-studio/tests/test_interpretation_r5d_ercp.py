"""Round 5d of the Gemini migration, the ERCP repair D147 (the review of D140: review_ercp3.json problems 0-3 and 5),
SYNTHETIC and REPLAYED: nothing is sent. Each pin is built from its source's own input - the reviewer's probe texts and
answers (rvcases.py: finding 25's ERCP with the sweep's sentence changed) - or, where named, this repair's own.

- (1) problem 0: "fragments" is a yield subject only directly after a stone word ("stone fragments", "calculus
  fragments"); stent, plastic or tissue fragments retrieved are no stones retrieved, so the denial holds 43264.
- (2) problems 1 and 2: a yield is the act's own only in the act's own SIMPLE clause - the clause cut before each word
  that opens a new one (ercp.CLAUSE_OPENERS). The clause reading takes a yield only from a simple clause that holds one
  of the act's own words, the guard words still read over the whole clause; the structural reading takes the act's
  attribute words as its yield only where no clause of a located passage that holds them carries a guard word.
- (3) problem 3: the sentence after the act's own is dropped as another act's when it holds the own words of another
  event that is performed, and read when the only other events whose words it holds are not performed.

The installed release c2e53f8e's outcome on each input (jobs._assess_child, as the head-to-head runs it, with no
participant and with Astra and Fable read: the same on every input here) is quoted in each pin's docstring.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import ercp, events
from tests.test_interpretation_events import asked, proposal, run
from tests.test_interpretation_identity import a, sc, tg
from tests.test_interpretation_r4_ercp import PARTICIPANTS, ercp_act
from tests.test_interpretation_r5_ercp import held_nothing_retrieved, ready_on, sweep

SW = dict(kind_words='swept with an extraction balloon', status_words='was swept')
THEN = dict(kind_words='swept with an extraction balloon', status_words='was then swept')
SWEPT_ONCE = 'The bile duct was swept with an extraction balloon.'


def assessed(p5: str, cited=None, participants=(), **options):
    """43264 on finding 25's ERCP (tests.test_interpretation_r5_ercp.sweep) with ``p5`` for the sweep (E4), Corti citing
    43262 at the sphincterotomy and 43264 at ``cited`` (default: the whole of P5)."""
    inv, text, doc = sweep(p5, **options)
    return proposal(run(inv, text, [('43262', doc['P4']), ('43264', cited or p5)], participants=participants), '43264')


def held_each(test, shapes: dict, participants=PARTICIPANTS) -> None:
    """Each shape {name: (p5, cited, options, said)} holds 43264 with D106's question quoting ``said``."""
    for name, (p5, cited, options, said) in shapes.items():
        for chosen in participants:
            with test.subTest(shape=name, participants=len(chosen)):
                held_nothing_retrieved(test, assessed(p5, cited, chosen, **options), said)


def snare(words: str) -> dict:
    """The stent removed with a snare, filed as its own stent_removal (E5) - the review's problem-0 documents."""
    return ercp_act('E5', 'P5', 'stent_removal', words, 'was removed', technique=a('snare', 'snare', ['P5']))


# --- (1), problem 0: "fragments" is a yield subject only after a stone word ----------------------------------------

class D147Fragments(SimpleTestCase):
    def test_d147_problem_0_stent_plastic_or_tissue_fragments_are_no_yield(self):
        """The review's problem 0 (critical, introduced by D140): every act filed, the sweep (E4, 'was then swept')
        beside the stent removed with a snare (E5) - "...; the bile duct was then swept with an extraction balloon and
        the remaining stent fragments were retrieved; no stones were found.", its two-sentence form, "...and plastic
        fragments were removed; no stones or sludge were seen.", the biopsy's "...and the tissue fragments were
        retrieved; no stones were found." - and E4 alone ("...and stent fragments were retrieved; no stones or sludge
        were seen.", "...and the stent fragments were removed; no stones were found."): READY on E4 at e5628be56; held
        with D106's question again, as 46e461e7f held them per the review (c2e53f8e: HELD act_missing on every one). The
        review's inputs give the sweep words outside the fragments' simple clause, so the simple-clause rule holds them
        too; this repair's own two variants of the E4-alone inputs put Gemini's status words for the sweep in that
        clause ("were retrieved", "were removed"), which only the 'fragments' rule holds (READY at e5628be56; c2e53f8e
        HELD act_missing)."""
        snared = ('The fractured stent was removed with a snare; the bile duct was then swept with an extraction '
                  'balloon and the remaining stent fragments were retrieved; no stones were found.')
        period = ('The fractured biliary stent was removed with a snare. The bile duct was then swept with an '
                  'extraction balloon and stent fragments were retrieved; no stones were found.')
        plastic = ('The migrated stent was removed with a snare; the duct was then swept with an extraction balloon '
                   'and plastic fragments were removed; no stones or sludge were seen.')
        tissue = ('Intraductal biopsies were taken with forceps; the bile duct was swept with an extraction balloon '
                  'and the tissue fragments were retrieved; no stones were found.')
        alone_seen = ('The bile duct was swept with an extraction balloon and stent fragments were retrieved; no '
                      'stones or sludge were seen.')
        alone_found = ('The bile duct was swept with an extraction balloon and the stent fragments were removed; no '
                       'stones were found.')
        biopsy = ercp_act('E5', 'P5', 'biopsy', 'Intraductal biopsies', 'were taken',
                          technique=a('forceps', 'forceps', ['P5']))
        held_each(self, {
            'the remaining stent fragments were retrieved': (
                snared, None, dict(THEN, target=('bile_duct', 'the bile duct'), more=[snare('The fractured stent')]),
                snared),
            'its two-sentence form': (
                period, None, dict(THEN, target=('bile_duct', 'The bile duct'),
                                   more=[snare('The fractured biliary stent')]),
                period.split('snare. ')[1]),
            'plastic fragments were removed': (
                plastic, None, dict(THEN, target=('bile_duct', 'the duct'), more=[snare('The migrated stent')]),
                plastic),
            'the tissue fragments were retrieved': (tissue, None, dict(SW, more=[biopsy]), tissue),
            'E4 alone, stent fragments were retrieved': (alone_seen, None, SW, alone_seen),
            'E4 alone, the stent fragments were removed': (alone_found, None, SW, alone_found),
            # this repair's own: Gemini's status words for the sweep in the fragments' simple clause, so only the
            # 'fragments' rule reads these (READY at e5628be56; c2e53f8e HELD act_missing, as on the same text above)
            'E4 alone, its status words "were retrieved"': (
                alone_seen, None, dict(kind_words='swept with an extraction balloon', status_words='were retrieved'),
                alone_seen),
            'E4 alone, its status words "were removed"': (
                alone_found, None, dict(kind_words='swept with an extraction balloon', status_words='were removed'),
                alone_found),
        })

    def test_d147_stone_or_calculus_fragments_still_state_a_yield(self):
        """'stone fragments were removed' still states a yield: READY on E4 with the status words in its simple clause
        ("...and stone fragments were removed; no stones remained.", and this repair's "calculus fragments were
        retrieved"; c2e53f8e READY on both). The sentence reader alone (every clause the act's): "Stone fragments" and
        "Calculus fragments" state a yield; "Stent", "Plastic", "The tissue", "Clot" and bare "Fragments" do not, so the
        presence denial stands."""
        for fragments, status_words in (('stone fragments were removed', 'were removed'),
                                        ('calculus fragments were retrieved', 'were retrieved')):
            for chosen in PARTICIPANTS:
                with self.subTest(fragments=fragments, participants=len(chosen)):
                    ready_on(self, assessed(f'The bile duct was swept with an extraction balloon and {fragments}; no '
                                            'stones remained.', None, chosen,
                                            kind_words='swept with an extraction balloon', status_words=status_words))
        for sentence in ('Stone fragments were removed; no stones remained.',
                         'Calculus fragments were removed; no stones remained.'):
            with self.subTest(yields=sentence):
                self.assertFalse(ercp.states_nothing_retrieved(sentence))
        for sentence in ('Stent fragments were removed; no stones remained.',
                         'Plastic fragments were removed; no stones or sludge were seen.',
                         'The tissue fragments were retrieved; no stones were found.',
                         'Clot fragments were removed; no stones were found.',
                         'Fragments were removed; no stones remained.'):
            with self.subTest(no_yield=sentence):
                self.assertTrue(ercp.states_nothing_retrieved(sentence))


# --- (2), problems 1 and 2: the act's own simple clause --------------------------------------------------------------

class D147SimpleClause(SimpleTestCase):
    def test_d147_problem_1_an_earlier_yield_or_a_doubt_in_another_simple_clause(self):
        """The review's problem 1 (critical by the rubric, present at 46e461e7f): the sweep's words in the clause's
        first simple clause and a yield in the next - "The bile duct was swept with an extraction balloon after stones
        were removed at an outside hospital; no stones were found." (and "... no stones remained."), "two weeks ago",
        the "since ...; no stones were seen on the final cholangiogram." form, "in September", "by the referring
        gastroenterologist", and "Presumed" / "Questionable stones were removed when the bile duct was swept with an
        extraction balloon; ..." - READY on E4 at e5628be56; held with D106's question now. c2e53f8e: EXCLUDED on the
        "at an outside hospital", "two weeks ago" and "since" forms; HELD readings_disagree on "in September"; HELD
        act_missing on "by the referring gastroenterologist", "Presumed" and "Questionable"."""
        shapes = {}
        for when in ('at an outside hospital', 'two weeks ago', 'in September', 'by the referring gastroenterologist'):
            for denial in ('no stones were found.', 'no stones remained.'):
                p5 = f'The bile duct was swept with an extraction balloon after stones were removed {when}; {denial}'
                shapes[f'after stones were removed {when}; {denial}'] = (p5, None, SW, p5)
        since = ('The bile duct was swept with an extraction balloon since stones were removed at an outside hospital; '
                 'no stones were seen on the final cholangiogram.')
        shapes['since ...'] = (since, None, SW, since)
        for word in ('Presumed', 'Questionable'):
            p5 = (f'{word} stones were removed when the bile duct was swept with an extraction balloon; no stones were '
                  'seen on the final cholangiogram.')
            shapes[f'{word} ... when the bile duct was swept'] = (
                p5, None, dict(SW, target=('bile_duct', 'the bile duct')), p5)
        held_each(self, shapes)

    def test_d147_problem_2_the_structural_reading_in_a_guarded_clause(self):
        """The review's problem 2 (introduced by D140; it needs Gemini to file a doubt or an earlier act as performed):
        E4's kind words "stones were removed" (status words "were removed") inside "It is unclear whether any stones
        were removed when the bile duct was swept with an extraction balloon and a plastic stent was placed; no stones
        were seen on the final cholangiogram." and its sibling "...and a plastic stent was placed after stones were
        removed at the prior ERCP; no stones were found.", the stent filed (E5) - and D140's own N1 and N2, the same
        words with no stent - READY on E4 at e5628be56; held now, the passage's clause holding the words carrying a
        guard word (c2e53f8e: HELD act_missing, EXCLUDED, HELD act_missing, EXCLUDED)."""
        stent = ercp_act('E5', 'P5', 'stent', 'plastic stent', 'was placed')
        words = dict(kind_words='stones were removed', status_words='were removed')
        unclear = ('It is unclear whether any stones were removed when the bile duct was swept with an extraction '
                   'balloon and a plastic stent was placed; no stones were seen on the final cholangiogram.')
        prior = ('The bile duct was swept with an extraction balloon and a plastic stent was placed after stones were '
                 'removed at the prior ERCP; no stones were found.')
        n1 = ('It is unclear whether any stones were removed when the bile duct was swept with an extraction balloon; '
              'no stones were seen on the final cholangiogram.')
        n2 = ('The bile duct was swept with an extraction balloon after stones were removed at the prior ERCP; no '
              'stones were found.')
        held_each(self, {
            'unclear, the stent in the clause': (unclear, None, dict(words, target=('bile_duct', 'the bile duct'),
                                                                     more=[stent]), unclear),
            'the prior ERCP, the stent in the clause': (prior, None, dict(words, target=('bile_duct', 'The bile duct'),
                                                                          more=[stent]), prior),
            "D140's N1": (n1, None, dict(words, target=('bile_duct', 'the bile duct')), n1),
            "D140's N2": (n2, None, dict(words, target=('bile_duct', 'The bile duct')), n2),
        })
        # the structural reading alone, on N1's reading: no yield of the act's
        inv, text, doc = sweep(n1, **words, target=('bile_duct', 'the bile duct'))
        reading = events.Reading.of(inv)
        located = [place for record in reading.passages.values() if record['state'] != 'unlocated'
                   for place in record['spans']]
        self.assertFalse(ercp._own_yield(reading.events['E4'], (), located))

    def test_d147_each_opener_cuts_the_clause(self):
        """Each word of CLAUSE_OPENERS opens a new simple clause: "The bile duct was swept with an extraction balloon
        <word> stones were removed; no stones were found." with the sweep's words in the first simple clause is a
        statement that nothing was retrieved (c2e53f8e READY on all 18 - a cost on the constructed battery), and with
        the act's status words "were removed" in the yield's simple clause it is the act's yield (no statement; READY,
        as c2e53f8e) - the cut is about the act's own words. This repair's own battery, through the reader."""
        self.assertEqual(len(ercp.CLAUSE_OPENERS), 18)
        for word in ercp.CLAUSE_OPENERS:
            p5 = f'The bile duct was swept with an extraction balloon {word} stones were removed; no stones were found.'
            for status_words, nothing in (('was swept', True), ('were removed', False)):
                inv, text, doc = sweep(p5, kind_words='swept with an extraction balloon', status_words=status_words)
                reading = events.Reading.of(inv)
                with self.subTest(opener=word, status_words=status_words):
                    statement = ercp.nothing_retrieved(reading, reading.events['E4'])
                    self.assertEqual(statement is not None, nothing)
                    if nothing:
                        self.assertEqual([place['text'] for place in statement], [p5])

    def test_d147_the_guard_words_are_read_over_the_whole_clause(self):
        """The guard words are still read over the WHOLE clause, not over the yield's simple clause: "The bile duct was
        swept with an extraction balloon to clear the duct and several small stones were removed; no stones remained."
        with the status words "were removed" in the yield's simple clause stays held (as at e5628be56; c2e53f8e READY: a
        cost of D140's purpose word "to", read over the whole clause), while the same sentence with no purpose word is
        READY on E4 (c2e53f8e READY)."""
        options = dict(kind_words='swept with an extraction balloon', status_words='were removed')
        purpose = ('The bile duct was swept with an extraction balloon to clear the duct and several small stones were '
                   'removed; no stones remained.')
        held_each(self, {'a purpose word in the sweep\'s simple clause': (purpose, None, options, purpose)},
                  participants=((),))
        ready_on(self, assessed('The bile duct was swept with an extraction balloon and several small stones were '
                                'removed; no stones remained.', **options))

    def test_d147_the_releases_kept(self):
        """D127's four pinned releases stay READY on E4, through the clause reading (c2e53f8e READY on each): "Multiple
        stones were extracted ... until no stones remained.", "...and several small stones were removed; no stones
        remained / were seen on the final cholangiogram." (the status words "were removed" in the yield's simple clause)
        and "Two stones were extracted ... . No stones remained." D140's structural release stays READY on the basket
        (E5) of D127's two-act sentence with the basket's own kind, status, technique or target words "Two stones were
        removed" (c2e53f8e READY), and the structural shapes - Gemini's kind words "Multiple stones were extracted", and
        "Two stones were extracted" with the presence denial in a later own sentence - stay READY on E4 (c2e53f8e
        READY)."""
        clearances = {
            'until no stones remained': ('Multiple stones were extracted from the bile duct with an extraction balloon '
                                         'until no stones remained.',
                                         dict(kind_words='extracted', status_words='were extracted',
                                              target=('bile_duct', 'bile duct'))),
            'no stones remained on the final cholangiogram': (
                'The bile duct was swept with an extraction balloon and several small stones were removed; no stones '
                'remained on the final cholangiogram.',
                dict(kind_words='swept with an extraction balloon', status_words='were removed')),
            'no stones were seen on the final cholangiogram': (
                'The bile duct was swept with an extraction balloon and several small stones were removed; no stones '
                'were seen on the final cholangiogram.',
                dict(kind_words='swept with an extraction balloon', status_words='were removed')),
            'across a period': ('Two stones were extracted from the bile duct with an extraction balloon. No stones '
                                'remained.', dict(kind_words='extracted', status_words='were extracted',
                                                  target=('bile_duct', 'bile duct'))),
        }
        for name, (p5, options) in clearances.items():
            for chosen in PARTICIPANTS:
                with self.subTest(clearance=name, participants=len(chosen)):
                    ready_on(self, assessed(p5, None, chosen, **options))
        shared = ('Two stones were removed with a basket and the duct was then swept with an extraction balloon; no '
                  'stones were seen.')
        for attribute in ('kind', 'status', 'technique', 'target'):
            words = dict(kind='removed', status='were removed', technique='basket', target='the duct')
            words[attribute] = ('Two stones were removed with a basket' if attribute == 'technique'
                                else 'Two stones were removed')
            basket = ercp_act('E5', 'P5', 'stone_extraction', words['kind'], words['status'],
                              target=tg('', 'bile_duct', words['target'], ['P5']),
                              technique=a('basket', words['technique'], ['P5']))
            for chosen in PARTICIPANTS:
                with self.subTest(basket=attribute, participants=len(chosen)):
                    ready_on(self, assessed(shared, None, chosen, **THEN, target=('bile_duct', 'the duct'),
                                            more=[basket]), ('E5',))
        ready_on(self, assessed('Multiple stones were extracted from the bile duct with an extraction balloon until no '
                                'stones remained.', kind_words='Multiple stones were extracted',
                                status_words='were extracted', target=('bile_duct', 'bile duct')))
        ready_on(self, assessed('Two stones were extracted with an extraction balloon. On a final sweep of the bile '
                                'duct no stones were seen.', kind_words='Two stones were extracted',
                                status_words='were extracted', target=('bile_duct', 'bile duct')))

    def test_d147_the_words_reader_reads_the_clause_tokens(self):
        """_words gives the same folded words as _tokens, with their offsets: on every clause of this module's inputs
        and a few edge shapes (an apostrophe, a negator "n't", a dash, a soft hyphen, curly quotes)."""
        texts = ("The bile duct was swept with an extraction balloon after stones were removed at an outside "
                 "hospital; no stones were found.",
                 "Stones weren't removed - the patient's duct was swept, and ‘two’ stones were ex­tracted.",
                 "Three stones, the largest 9 mm, were extracted from the bile duct; no stones remained.")
        for text in texts:
            for clause in ercp._clauses({'start': 7, 'end': 7 + len(text), 'text': text}):
                with self.subTest(clause=clause['text']):
                    words = ercp._words(clause)
                    self.assertEqual([word[0] for word in words], clause['tokens'])
                    for token, start, end in words:
                        self.assertTrue(clause['start'] <= start < end <= clause['end'])


# --- (3), problem 3: a performed act's sentence that also names a plan is another act's -----------------------------

BASKET = ercp_act('E5', 'P5', 'stone_extraction', 'extracted', 'were extracted',
                  technique=a('basket', 'basket', ['P5']))
REPEAT = ercp_act('E6', 'P5', 'examination', 'a repeat ERCP', 'is planned', status='planned',
                  time=a('future', 'is planned', ['P5']))


class D147NextSentence(SimpleTestCase):
    def test_d147_problem_3_a_performed_acts_sentence_that_names_a_plan(self):
        """The review's problem 3 (introduced by D140), its input 1: "The bile duct was swept with an extraction
        balloon. Two stones were extracted with a basket; no stones were seen on the final cholangiogram and a repeat
        ERCP is planned." with the basket (E5, performed) and the repeat ERCP (E6, planned) filed, Corti citing the
        sweep's sentence: held nothing_retrieved at e5628be56; READY now, as c2e53f8e (READY; 46e461e7f READY on E4, per
        the review). So is the reviewer's "Two stones were then extracted" form (c2e53f8e READY) - and Corti citing the
        whole passage, where c2e53f8e HOLDS (readings_disagree): a release where the installed release holds, the
        document stating two stones extracted. 43264 rests on the sweep (E4): the basket's own sentence denies the
        stones' presence in a clause that holds the plan's words (D127's sentence of two acts), so E5 leaves E* and the
        decision still reads it."""
        p5 = ('The bile duct was swept with an extraction balloon. Two stones were extracted with a basket; no stones '
              'were seen on the final cholangiogram and a repeat ERCP is planned.')
        then = ('The bile duct was swept with an extraction balloon. Two stones were then extracted with a basket; no '
                'stones were seen on the final cholangiogram and a repeat ERCP is planned.')
        then_basket = ercp_act('E5', 'P5', 'stone_extraction', 'extracted', 'were then extracted',
                               technique=a('basket', 'basket', ['P5']),
                               target=tg('', 'bile_duct', 'The bile duct', ['P5']))
        for name, (text_, cited, more) in {'input 1, Corti cites the sweep': (p5, SWEPT_ONCE, [BASKET, REPEAT]),
                                           'input 1, Corti cites the passage': (p5, None, [BASKET, REPEAT]),
                                           'then extracted': (then, SWEPT_ONCE, [then_basket, REPEAT])}.items():
            for chosen in PARTICIPANTS:
                with self.subTest(shape=name, participants=len(chosen)):
                    ready_on(self, assessed(text_, cited, chosen, **SW, more=more))
        inv, text, doc = sweep(p5, **SW, more=[BASKET, REPEAT])
        reading = events.Reading.of(inv)
        self.assertIsNone(ercp.nothing_retrieved(reading, reading.events['E4']))
        self.assertEqual(events.evaluate('43264', (), reading).read, ('E4', 'E5'))

    def test_d147_problem_3_a_performed_act_beside_a_denial_event_is_another_acts(self):
        """D140's control (tests.test_interpretation_r5c_ercp, test_d140_problem_1_controls), its expectation changed by
        this repair: "The bile duct was swept with an extraction balloon. The pancreatic duct was then swept with a
        balloon; no stones were retrieved." with the pancreatic sweep (E5, performed) and the denial filed as its own
        event (E6, not_performed) - the next sentence holds a performed act's words, so it is that act's and is dropped,
        and 43264 is READY on E4 as on D127's own pin without E6. Held at e5628be56; c2e53f8e HOLDS both forms
        (readings_disagree). A release where the installed release holds, recorded (the document states no stone
        retrieved anywhere)."""
        both = ('The bile duct was swept with an extraction balloon. The pancreatic duct was then swept with a '
                'balloon; no stones were retrieved.')
        pancreatic = ercp_act('E5', 'P5', 'stone_extraction', 'swept with a balloon', 'was then swept',
                              target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                              technique=a('balloon', 'balloon', ['P5']))
        denial = ercp_act('E6', 'P5', 'other', 'no stones were retrieved', 'no stones were retrieved',
                          status='not_performed', scope=sc('single_target', 'no', ['P5']))
        for chosen in PARTICIPANTS:
            with self.subTest(participants=len(chosen)):
                ready_on(self, assessed(both, SWEPT_ONCE, chosen, **SW, more=[pancreatic, denial]))

    def test_d147_problem_3_only_events_not_performed_the_sentence_is_read(self):
        """D140's disagreement-4 inputs stay held - each next sentence holds only the words of an event that is not
        performed, so it is read: "No stones were retrieved; a repeat ERCP is planned.", "...; biliary stent placement
        is planned.", "Basket extraction was attempted but was unsuccessful; no stones were retrieved." and "Stent
        placement was attempted but was unsuccessful; no stones were retrieved." (c2e53f8e: HELD readings_disagree on
        each). And the review's input 2, "Sludge was retrieved but no stones were seen, and a repeat ERCP is planned."
        with only the plan filed (E6), Corti citing the sweep's sentence: its next sentence holds only a planned event's
        words, so it is read, and D106's reader reads "retrieved but no stones" as a denied retrieval - held, as at
        e5628be56. c2e53f8e READYs it: a recorded cost, not the READY the design expected."""
        shapes = {
            'a planned repeat ERCP': (
                'The bile duct was swept with an extraction balloon. No stones were retrieved; a repeat ERCP is '
                'planned.',
                ercp_act('E5', 'P5', 'examination', 'a repeat ERCP', 'is planned', status='planned',
                         time=a('future', 'a repeat ERCP is planned', ['P5']))),
            'a planned stent placement': (
                'The bile duct was swept with an extraction balloon. No stones were retrieved; biliary stent placement '
                'is planned.',
                ercp_act('E5', 'P5', 'stent', 'biliary stent placement', 'is planned', status='planned',
                         time=a('future', 'is planned', ['P5']))),
            'a basket extraction begun and not completed': (
                'The bile duct was swept with an extraction balloon. Basket extraction was attempted but was '
                'unsuccessful; no stones were retrieved.',
                ercp_act('E5', 'P5', 'stone_extraction', 'Basket extraction', 'was attempted but was unsuccessful',
                         status='attempted_not_completed', technique=a('basket', 'Basket', ['P5']),
                         target=tg('', 'bile_duct', 'The bile duct', ['P5']))),
            'a stent placement begun and not completed': (
                'The bile duct was swept with an extraction balloon. Stent placement was attempted but was '
                'unsuccessful; no stones were retrieved.',
                ercp_act('E5', 'P5', 'stent', 'Stent placement', 'was attempted but was unsuccessful',
                         status='attempted_not_completed')),
            'input 2: sludge retrieved, a repeat ERCP planned': (
                'The bile duct was swept with an extraction balloon. Sludge was retrieved but no stones were seen, and '
                'a repeat ERCP is planned.', REPEAT),
        }
        for name, (p5, other) in shapes.items():
            with self.subTest(shape=name):
                held_nothing_retrieved(self, assessed(p5, SWEPT_ONCE, **SW, more=[other]), p5)
        p = assessed(shapes['a planned repeat ERCP'][0], SWEPT_ONCE, **SW, more=[shapes['a planned repeat ERCP'][1]])
        self.assertEqual((p.status, asked(p)), ('needs_clarification', ['performed_status']))
