"""Round 5c of the Gemini migration, the ERCP repair D140 (the review of D127: review_ercp2.json problems 0-5),
SYNTHETIC and REPLAYED: nothing is sent. Each pin is built from its source's own input - the reviewer's probe texts and
answers (rvprobe_ercp.py: finding 25's ERCP with the sweep's sentence changed) - or, where named, this repair's own.

- (1) problems 0 and 2: the yield that clears D106's hold is the act's OWN statement - in the act's own attribute words
  (kind, status, target, technique; the structural reading), or in a clause of the act's own whose subject is a stone
  word with a past yield verb and that holds no purpose, condition or doubt, or other-time word (the clause reading,
  which keeps D127's pinned clearances). A purpose clause, a device as the subject, a doubt and an earlier yield are no
  yield, so the denial holds; a false yield no longer stops the read of the sentence after.
- (2) problem 1: the sentence that follows the act's own is never dropped as another act's when it holds the words of
  an event that is not performed - the denial Gemini files as its own not_performed event, an uncertain statement, a
  plan, an act begun and not completed.

The installed release c2e53f8e's outcome on each input (jobs._assess_child, as the head-to-head runs it, with no
participant and with Astra and Fable read: the same on every input here) is quoted in each pin's docstring.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import ercp, events
from tests.test_interpretation_events import asked, proposal, run
from tests.test_interpretation_identity import a, sc, tg
from tests.test_interpretation_r4_ercp import PARTICIPANTS, ercp_act
from tests.test_interpretation_r5_ercp import NONE_RETRIEVED, SWEEP, SWEPT, held_nothing_retrieved, ready_on, sweep

SW = dict(kind_words='swept with an extraction balloon', status_words='was swept')
FOR_STONES = dict(kind_words='swept for stones with an extraction balloon', status_words='was swept',
                  target=('bile_duct', 'the bile duct'))
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


# --- (1), problem 0: a purpose clause, a device as the subject, a doubt or an earlier yield is no yield ---------------

PURPOSE = ('The bile duct was swept with an extraction balloon to ensure all stones had been removed; no stones '
           'remained.')


class D140OwnYield(SimpleTestCase):
    def test_d140_problem_0_a_purpose_clause_is_no_yield(self):
        """The review's problem 0 (critical, introduced by D127): finding 25's document with P5 a sweep 'to ensure all
        stones had been removed; no stones remained.' made 43264 READY on E4 (1caaf0609: held nothing_retrieved) - and
        its variants: Balloon sweeps 'performed to ensure that all stones had been removed', 'to confirm that all stones
        had been removed, and no stones were found', the earlier ERCP named in the purpose clause, and Corti citing only
        the first clause. Each is held with D106's question again (c2e53f8e, in order: HELD act_missing, HELD
        act_missing, HELD readings_disagree, EXCLUDED, HELD act_missing). This repair's own three are held too: the
        denial across a period (READY at 1caaf0609, which read no next sentence, and at 46e461e7f; c2e53f8e HELD
        act_missing), and a purpose clause in the simple past ('to ensure that all stones were removed') and 'so that' -
        fail-closed holds where c2e53f8e is READY on both (recorded costs)."""
        two = ('The bile duct was swept with an extraction balloon to ensure all stones had been removed. No stones '
               'remained.')
        simple = ('The bile duct was swept with an extraction balloon to ensure that all stones were removed; no '
                  'stones remained.')
        so_that = ('The bile duct was swept repeatedly with an extraction balloon so that all stones were removed; no '
                   'stones remained.')
        sweeps = dict(kind_words='Balloon sweeps', status_words='were performed', target=('bile_duct', 'bile duct'),
                      technique=('extraction_balloon', 'Balloon'))
        common = dict(kind_words='swept with a 12 mm extraction balloon', status_words='was swept',
                      target=('common_bile_duct', 'The common bile duct'))
        shapes = {
            'to ensure all stones had been removed': (PURPOSE, None, SW, PURPOSE),
            'Balloon sweeps were performed to ensure': (
                'Balloon sweeps of the bile duct were performed to ensure that all stones had been removed; no stones '
                'remained.', None, sweeps,
                'Balloon sweeps of the bile duct were performed to ensure that all stones had been removed; no stones '
                'remained.'),
            'to confirm, and no stones were found': (
                'The common bile duct was swept with a 12 mm extraction balloon to confirm that all stones had been '
                'removed, and no stones were found.', None, common,
                'The common bile duct was swept with a 12 mm extraction balloon to confirm that all stones had been '
                'removed, and no stones were found.'),
            'to ensure ... at the prior ERCP': (
                'The bile duct was swept with an extraction balloon to ensure all stones had been removed at the prior '
                'ERCP; no stones remained.', None, SW,
                'The bile duct was swept with an extraction balloon to ensure all stones had been removed at the prior '
                'ERCP; no stones remained.'),
            'Corti cites the first clause': (PURPOSE, PURPOSE.split(';')[0], SW, PURPOSE),
            'the denial across a period': (two, None, SW, two),
            'to ensure that all stones were removed (own)': (simple, None, SW, simple),
            'so that all stones were removed (own)': (
                so_that, None, dict(kind_words='swept repeatedly with an extraction balloon', status_words='was swept'),
                so_that),
        }
        held_each(self, shapes)

    def test_d140_problem_0_a_device_as_the_subject_is_no_yield(self):
        """The review's problem 0, the device subjects: "The sphincterotome was removed and the bile duct was swept for
        stones ...", "...with a stone extraction balloon and the balloon was then removed", "...and the guidewire was
        removed", "An extraction balloon was delivered over the guidewire ..." and "...for suspected stones and the
        balloon was removed", each with "no stones were found / were seen / remained" after: READY at 46e461e7f (D127),
        held again (1caaf0609: held nothing_retrieved). c2e53f8e READYs all but the last (HELD act_missing) -
        fail-closed holds of what the document does not state, as the review reads them (recorded costs)."""
        stone_balloon = dict(kind_words='swept with a stone extraction balloon', status_words='was swept')
        shapes = {}
        for denial in ('no stones were found.', 'no stones were seen.', 'no stones remained.'):
            p5 = ('The sphincterotome was removed and the bile duct was swept for stones with an extraction balloon; '
                  f'{denial}')
            shapes[f'the sphincterotome was removed; {denial}'] = (p5, None, FOR_STONES, p5)
            p5 = f'The bile duct was swept with a stone extraction balloon and the balloon was then removed; {denial}'
            shapes[f'the balloon was then removed; {denial}'] = (p5, None, stone_balloon, p5)
        guidewire = ('The bile duct was swept for retained stones with an extraction balloon and the guidewire was '
                     'removed; no stones were found.')
        delivered = ('An extraction balloon was delivered over the guidewire and the bile duct was swept for stones; '
                     'no stones were found.')
        suspected = ('The bile duct was swept with an extraction balloon for suspected stones and the balloon was '
                     'removed; no stones were found.')
        shapes.update({
            'the guidewire was removed': (
                guidewire, None,
                dict(kind_words='swept for retained stones with an extraction balloon', status_words='was swept'),
                guidewire),
            'a balloon was delivered': (delivered, None, dict(kind_words='swept for stones', status_words='was swept',
                                                              target=('bile_duct', 'the bile duct')), delivered),
            'suspected stones, the balloon was removed': (suspected, None, SW, suspected),
        })
        held_each(self, shapes, participants=((),))

    def test_d140_problem_0_a_doubt_or_an_earlier_yield_is_no_yield(self):
        """The review's problem 0: "It is unclear whether any stones were removed when the bile duct was swept with an
        extraction balloon; no stones were seen on the final cholangiogram." (c2e53f8e: HELD act_missing) and "...swept
        with an extraction balloon after stones were removed at the prior ERCP; no stones were found." (c2e53f8e:
        EXCLUDED) - READY at 46e461e7f, held again."""
        unclear = ('It is unclear whether any stones were removed when the bile duct was swept with an extraction '
                   'balloon; no stones were seen on the final cholangiogram.')
        prior = ('The bile duct was swept with an extraction balloon after stones were removed at the prior ERCP; no '
                 'stones were found.')
        held_each(self, {'a doubt': (unclear, None, dict(SW, target=('bile_duct', 'the bile duct')), unclear),
                         'an earlier yield': (prior, None, SW, prior)})

    def test_d140_the_past_perfect_is_no_yield(self):
        """This repair's own inputs: the past perfect is not the act's own yield - "Several stones had been removed from
        the bile duct with an extraction balloon; no stones remained on the final cholangiogram." (READY at 46e461e7f;
        c2e53f8e: HELD act_missing) - in the clause reading and in the structural one (Gemini's kind words "all stones
        had been removed" inside the purpose clause, or "stones had been removed" in the Balloon sweeps sentence:
        c2e53f8e HELD act_missing on both)."""
        perfect = ('Several stones had been removed from the bile duct with an extraction balloon; no stones remained '
                   'on the final cholangiogram.')
        sweeps = ('Balloon sweeps of the bile duct were performed to ensure that all stones had been removed; no '
                  'stones remained.')
        held_each(self, {
            'had been removed (clause)': (perfect, None, dict(kind_words='removed', status_words='had been removed',
                                                               target=('bile_duct', 'bile duct')), perfect),
            "had been removed (Gemini's kind words, a purpose clause)": (
                PURPOSE, None, dict(kind_words='all stones had been removed', status_words='had been removed'),
                PURPOSE),
            "had been removed (Gemini's kind words, Balloon sweeps)": (
                sweeps, None, dict(kind_words='stones had been removed', status_words='had been removed',
                                   target=('bile_duct', 'bile duct'), technique=('extraction_balloon', 'Balloon')),
                sweeps),
        }, participants=((),))
        self.assertTrue(ercp.states_nothing_retrieved(perfect))
        self.assertFalse(ercp.states_nothing_retrieved('All stones have been removed; no stones remained.'))

    def test_d140_the_clause_readings_words_one_by_one(self):
        """The clause reading, through the sentence reader alone (states_nothing_retrieved: every clause the act's): a
        stone word the subject of a past yield verb is a clearance ("Stones were removed; no stones remained." states no
        denial), and each purpose, condition or doubt, or other-time word the spec names, in the yield's clause, makes
        it no yield - so the presence denial stands. The subject: a device, an adverb before the verb, a negated subject
        ("No fragments were removed") or the past perfect is no yield; "Stone fragments were removed", "Two stones
        extracted" and "All stones have been removed" are."""
        self.assertFalse(ercp.states_nothing_retrieved('Stones were removed; no stones remained.'))
        guarded = {
            'to': 'The duct was swept to ensure stones were removed; no stones remained.',
            'so that': 'The duct was swept so that stones were removed; no stones remained.',
            'whether': 'Whether stones were removed is not stated; no stones remained.',
            'if': 'If stones were removed, none were seen; no stones remained.',
            'unclear': 'It is unclear how many stones were removed; no stones remained.',
            'possible': 'Possible stones were removed; no stones remained.',
            'possibly': 'Possibly stones were removed; no stones remained.',
            'may': 'It may be that stones were removed; no stones remained.',
            'might': 'It might be that stones were removed; no stones remained.',
            'suspected': 'Suspected stones were removed; no stones remained.',
            'any': 'Any stones were removed; no stones remained.',
            'prior': 'Stones were removed at the prior ERCP; no stones remained.',
            'previous': 'Stones were removed at the previous ERCP; no stones remained.',
            'previously': 'Previously stones were removed; no stones remained.',
            'earlier': 'Stones were removed earlier; no stones remained.',
            'index': 'Stones were removed at the index ERCP; no stones remained.',
            'last': 'Stones were removed at the last ERCP; no stones remained.',
        }
        for word, sentence in guarded.items():
            with self.subTest(guard=word):
                self.assertTrue(ercp.states_nothing_retrieved(sentence), sentence)
        no_yield = ('The balloon was removed; no stones remained.', 'Stones were then removed; no stones remained.',
                    'No fragments were removed; no stones remained.', 'Stones had been removed; no stones remained.')
        for sentence in no_yield:
            with self.subTest(no_yield=sentence):
                self.assertTrue(ercp.states_nothing_retrieved(sentence))
        for sentence in ('Stone fragments were removed; no stones remained.',
                         'Two stones extracted; no stones remained.',
                         'All stones have been removed; no stones remained.',
                         'A stone was removed; no stones remained.'):
            with self.subTest(yields=sentence):
                self.assertFalse(ercp.states_nothing_retrieved(sentence))


# --- (1), problem 2: a false yield no longer stops the next sentence's read ------------------------------------------

class D140NextSentence(SimpleTestCase):
    def test_d140_problem_2_a_false_yield_no_longer_stops_the_next_sentence(self):
        """The review's problem 2 (present before D127's patch): "The sphincterotome was removed and the bile duct was
        swept for stones with an extraction balloon. No stones or sludge were retrieved." - Corti citing both sentences
        or the first - was READY (c2e53f8e: HELD conflict:stone_extraction, both). The device's "was removed" read as a
        yield stopped the next sentence's read; it is no yield now, so the next sentence is read and 43264 is held with
        the question quoting both. So are this repair's two more: the balloon removed, then "No stones were found."
        (c2e53f8e: HELD act_missing) and then "No stones or sludge were retrieved." (c2e53f8e: HELD
        conflict:stone_extraction)."""
        device = ('The sphincterotome was removed and the bile duct was swept for stones with an extraction balloon. '
                  'No stones or sludge were retrieved.')
        found = ('The bile duct was swept with an extraction balloon for suspected stones and the balloon was then '
                 'removed. No stones were found.')
        retrieved = ('The bile duct was swept with a stone extraction balloon and the balloon was then removed. No '
                     'stones or sludge were retrieved.')
        held_each(self, {
            'Corti cites both sentences': (device, None, FOR_STONES, device),
            'Corti cites the first sentence': (device, device.split(' No ')[0], FOR_STONES, device),
            'the balloon removed. No stones were found. (own)': (found, None, SW, found),
            'the balloon removed. No stones or sludge were retrieved. (own)': (
                retrieved, None, dict(kind_words='swept with a stone extraction balloon', status_words='was swept'),
                retrieved),
        })


# --- (2), problem 1: the next sentence holds the words of an event that is not performed -----------------------------

def denial_event(kind: str, passage: str = 'P5') -> dict:
    """The review's problem 1: the denial filed by Gemini as its own event (finding 25's verifier listed this reading;
    prompt.py asks for an event for each statement that an act was not done) - kind removal or other, not_performed,
    its words the denial itself."""
    return ercp_act('E5', passage, kind, 'No stones or sludge were retrieved', 'No stones or sludge were retrieved',
                    status='not_performed', scope=sc('single_target', 'No', [passage]))


class D140DenialEvent(SimpleTestCase):
    def test_d140_problem_1_the_denial_filed_as_its_own_event_continues_the_act(self):
        """The review's problem 1 (critical by the rubric, not introduced): "The bile duct was swept several times with
        an extraction balloon. No stones or sludge were retrieved." as one passage, with E5 (kind removal or other,
        not_performed, 'No stones or sludge were retrieved') - and the denial on its own line as E5's passage - made
        43264 READY on E4: the next sentence held another event's words, so it was dropped. It holds the words of an
        event that is not performed, so it is read: 43264 held with the question quoting both sentences, Corti citing
        both or the first, with no participant and with Astra and Fable read (c2e53f8e: EXCLUDED act_denied, one passage
        and Corti citing both; HELD readings_disagree in every other shape)."""
        said = f'{SWEPT} {NONE_RETRIEVED}'
        for kind in ('other', 'removal'):
            for cited in (None, SWEPT):
                for chosen in PARTICIPANTS:
                    with self.subTest(kind=kind, shape='one passage', cited=bool(cited), participants=len(chosen)):
                        held_nothing_retrieved(self, assessed(said, cited, chosen, more=[denial_event(kind)]), said)
                    with self.subTest(kind=kind, shape='its own line', cited=bool(cited), participants=len(chosen)):
                        p = assessed(SWEPT, cited or (SWEPT, NONE_RETRIEVED), chosen,
                                     more_lines={'P6': NONE_RETRIEVED}, more=[denial_event(kind, 'P6')])
                        held_nothing_retrieved(self, p, said)
        inv, text, doc = sweep(said, more=[denial_event('other')])
        reading = events.Reading.of(inv)
        statement = ercp.nothing_retrieved(reading, reading.events['E4'])
        self.assertIsNotNone(statement)
        self.assertEqual([place['text'] for place in statement], [SWEPT, NONE_RETRIEVED])

    def test_d140_problem_1_controls(self):
        """The review's controls, unchanged: the semicolon form holds 43264 nothing_retrieved (c2e53f8e EXCLUDED); E5
        filed as stone_extraction holds it statement_scope (c2e53f8e EXCLUDED). D127's own pin stands: the next sentence
        another act's (the pancreatic duct's sweep, performed, E5) does not continue the act - 43264 READY on E4
        (c2e53f8e: HELD readings_disagree, recorded by D127). The same sentence with a denial event of its own (E6) as
        well holds the words of an event that is not performed, so it is read: held (c2e53f8e: HELD
        readings_disagree)."""
        semicolon = ('The bile duct was swept several times with an extraction balloon; no stones or sludge were '
                     'retrieved.')
        e5 = ercp_act('E5', 'P5', 'other', 'no stones or sludge were retrieved', 'no stones or sludge were retrieved',
                      status='not_performed', scope=sc('single_target', 'no', ['P5']))
        held_nothing_retrieved(self, assessed(semicolon, more=[e5]), semicolon)
        two = f'{SWEPT} {NONE_RETRIEVED}'
        e5x = ercp_act('E5', 'P5', 'stone_extraction', 'No stones or sludge were retrieved',
                       'No stones or sludge were retrieved', status='not_performed',
                       scope=sc('single_target', 'No', ['P5']))
        p = assessed(two, more=[e5x])
        self.assertEqual((p.status, asked(p), p.support['reason']),
                         ('needs_clarification', ['statement_scope'], events.UNRESOLVED))
        both = ('The bile duct was swept with an extraction balloon. The pancreatic duct was then swept with a '
                'balloon; no stones were retrieved.')
        pancreatic = ercp_act('E5', 'P5', 'stone_extraction', 'swept with a balloon', 'was then swept',
                              target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                              technique=a('balloon', 'balloon', ['P5']))
        ready_on(self, assessed(both, SWEPT_ONCE, **SW, more=[pancreatic]))
        denial = ercp_act('E6', 'P5', 'other', 'no stones were retrieved', 'no stones were retrieved',
                          status='not_performed', scope=sc('single_target', 'no', ['P5']))
        held_nothing_retrieved(self, assessed(both, SWEPT_ONCE, **SW, more=[pancreatic, denial]), both)

    def test_d140_problem_1_an_event_not_performed_planned_begun_or_uncertain(self):
        """'An event that is not performed' read as its status value: every value but 'performed', in any verification
        state. This repair's own inputs, each the denial in the next sentence beside the words of an event Gemini files
        for it: a plan (a repeat ERCP, a biliary stent placement), an act begun and not completed (a basket extraction,
        a stent placement) and an uncertain statement of another kind - each READY at 46e461e7f (the sentence was
        dropped), held now (c2e53f8e: HELD readings_disagree on the first four, HELD act_missing on the last)."""
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
            'an uncertain statement of another kind': (
                'The bile duct was swept with an extraction balloon. It is unclear whether any stones were retrieved; '
                'no stones were seen.',
                ercp_act('E5', 'P5', 'other', 'whether any stones were retrieved', 'whether any stones were retrieved',
                         status='uncertain', scope=sc('single_target', 'whether', ['P5']))),
        }
        for name, (p5, other) in shapes.items():
            with self.subTest(shape=name):
                held_nothing_retrieved(self, assessed(p5, SWEPT_ONCE, **SW, more=[other]), p5)


# --- what the yield still clears -------------------------------------------------------------------------------------

def basket(**words) -> dict:
    """D127's two-act shape: the basket extraction (E5) in the clause it shares with the sweep."""
    return ercp_act('E5', 'P5', 'stone_extraction', words.get('kind', 'removed'), words.get('status', 'were removed'),
                    target=tg('', 'bile_duct', words.get('target', 'the duct'), ['P5']),
                    technique=a('basket', words.get('technique', 'basket'), ['P5']))


SHARED = ('Two stones were removed with a basket and the duct was then swept with an extraction balloon; no stones '
          'were seen.')
TWO_ACTS = dict(kind_words='swept with an extraction balloon', status_words='was then swept',
                target=('bile_duct', 'the duct'))


class D140Clearances(SimpleTestCase):
    def test_d140_the_d127_clearances_kept_by_the_clause_reading(self):
        """The structural reading alone loses every clearance D127 pinned - none's yield is in the act's attribute words
        (the kind words "extracted", the status words "were removed") - and c2e53f8e READYs each, so the clause reading
        keeps them: "Multiple stones were extracted ... until no stones remained.", "...and several small stones were
        removed; no stones remained / were seen on the final cholangiogram.", "Two stones were extracted ... . No stones
        remained." (D127's four) - and this repair's: "were extracted", "have been removed", "has been removed", "was
        removed", "Two stones extracted" and "stone fragments were removed" (c2e53f8e READY on each). READY on E4, with
        no participant and with Astra and Fable read."""
        clearances = {
            'until no stones remained': ('Multiple stones were extracted from the bile duct with an extraction balloon '
                                         'until no stones remained.', dict(kind_words='extracted',
                                                                          status_words='were extracted',
                                                                          target=('bile_duct', 'bile duct'))),
            'no stones remained on the final cholangiogram': (
                'The bile duct was swept with an extraction balloon and several small stones were removed; no stones '
                'remained on the final cholangiogram.', dict(kind_words='swept with an extraction balloon',
                                                             status_words='were removed')),
            'no stones were seen on the final cholangiogram': (
                'The bile duct was swept with an extraction balloon and several small stones were removed; no stones '
                'were seen on the final cholangiogram.', dict(kind_words='swept with an extraction balloon',
                                                              status_words='were removed')),
            'across a period': ('Two stones were extracted from the bile duct with an extraction balloon. No stones '
                                'remained.', dict(kind_words='extracted', status_words='were extracted',
                                                  target=('bile_duct', 'bile duct'))),
        }
        for name, (p5, options) in clearances.items():
            for chosen in PARTICIPANTS:
                with self.subTest(clearance=name, participants=len(chosen)):
                    ready_on(self, assessed(p5, None, chosen, **options))
        own = {
            'were extracted': ('Two stones were extracted from the bile duct with an extraction balloon; no stones '
                               'remained.', 'extracted', 'were extracted'),
            'have been removed': ('All stones have been removed from the bile duct with an extraction balloon; no '
                                  'stones remained.', 'removed', 'have been removed'),
            'has been removed': ('The stone has been removed from the bile duct with an extraction balloon; no stones '
                                 'remained.', 'removed', 'has been removed'),
            'was removed': ('A large stone was removed from the bile duct with an extraction balloon; no stones '
                            'remained.', 'removed', 'was removed'),
            'telegraphic': ('Two stones extracted from the bile duct with an extraction balloon; no stones remained.',
                            'extracted', 'extracted'),
        }
        for name, (p5, kind_words, status_words) in own.items():
            with self.subTest(own=name):
                ready_on(self, assessed(p5, kind_words=kind_words, status_words=status_words,
                                        target=('bile_duct', 'bile duct')))
        fragments = ('The bile duct was swept with an extraction balloon and stone fragments were removed; no stones '
                     'remained.')
        ready_on(self, assessed(fragments, kind_words='swept with an extraction balloon', status_words='were removed'))

    def test_d140_the_structural_reading_the_acts_own_words_state_the_yield(self):
        """The structural reading (EB1): the act's own attribute words state its yield. Gemini's kind words "Multiple
        stones were extracted", and the kind or status words "Two stones were extracted" with the presence denial in a
        later sentence of the act's own (it holds the target's words) - READY on E4 (c2e53f8e READY on each). D127's
        two-act shape with the basket's yield in its own words - kind, status, technique or target - is READY on the
        basket (E5): 46e461e7f held it (a clause the two acts share is neither's), c2e53f8e READYs it - the one release
        here. The sweep's own words reaching into the basket's yield are no yield of the sweep's - "Two stones were
        removed from the bile duct with a basket; the duct was then swept with an extraction balloon and no stones were
        seen." with the sweep's kind words reaching from "Two stones" to "balloon" and the basket's words ("removed",
        "were removed", "bile duct") in the first clause: held, never READY on the sweep (the wrong act); c2e53f8e: HELD
        conflict:stone_extraction."""
        ready_on(self, assessed('Multiple stones were extracted from the bile duct with an extraction balloon until no '
                                'stones remained.', kind_words='Multiple stones were extracted',
                                status_words='were extracted', target=('bile_duct', 'bile duct')))
        later = ('Two stones were extracted with an extraction balloon. On a final sweep of the bile duct no stones '
                 'were seen.')
        for kind_words, status_words in (('Two stones were extracted', 'were extracted'),
                                         ('extracted', 'Two stones were extracted')):
            with self.subTest(later=kind_words):
                ready_on(self, assessed(later, kind_words=kind_words, status_words=status_words,
                                        target=('bile_duct', 'bile duct')))
        for name, words in {'kind': dict(kind='Two stones were removed'),
                            'status': dict(status='Two stones were removed'),
                            'technique': dict(technique='Two stones were removed with a basket'),
                            'target': dict(target='Two stones were removed')}.items():
            for chosen in PARTICIPANTS:
                with self.subTest(attribute=name, participants=len(chosen)):
                    ready_on(self, assessed(SHARED, None, chosen, **TWO_ACTS, more=[basket(**words)]), ('E5',))
        reaching = ('Two stones were removed from the bile duct with a basket; the duct was then swept with an '
                    'extraction balloon and no stones were seen.')
        reach = reaching.split(' and no stones')[0]
        p = assessed(reaching, kind_words=reach, status_words='was then swept', target=('bile_duct', 'the duct'),
                     more=[basket(target='bile duct')])
        held_nothing_retrieved(self, p, reaching)

    def test_d140_controls_d127s_holds_stand(self):
        """D127's held controls stand (each held at 46e461e7f): the sweep "until no stones remained" and "no stones were
        seen" with no yield, "no stones were retrieved and none remained", a yield in a clause none of the act's words
        are in ("Stones were extracted at the index ERCP in 2024; today ..."), D106's recorded cost "no stones were
        seen; sludge was retrieved", and D127's two-act sentences with the basket's words "removed" (c2e53f8e, in order:
        HELD readings_disagree, READY, EXCLUDED, HELD readings_disagree, READY, HELD conflict:stone_extraction,
        READY)."""
        shapes = {
            'until no stones remained': 'The bile duct was swept with an extraction balloon until no stones remained.',
            'no stones were seen': 'The bile duct was swept with an extraction balloon; no stones were seen on the '
                                   'final cholangiogram.',
            'none remained': 'The bile duct was swept with an extraction balloon; no stones were retrieved and none '
                             'remained.',
            'an earlier extraction': ('Stones were extracted at the index ERCP in 2024; today the duct was swept with '
                                      'an extraction balloon and no stones were seen.'),
            'sludge was retrieved': ('The bile duct was swept with an extraction balloon; no stones were seen; sludge '
                                     'was retrieved.'),
        }
        for name, p5 in shapes.items():
            target = ('bile_duct', 'the duct') if 'today the duct' in p5 else ('bile_duct', 'The bile duct')
            with self.subTest(control=name):
                held_nothing_retrieved(self, assessed(p5, **SW, target=target), p5)
        for p5 in ('Two stones were removed with a basket; the duct was then swept with an extraction balloon and no '
                   'stones were seen.', SHARED):
            with self.subTest(two_acts=p5):
                held_nothing_retrieved(self, assessed(p5, **TWO_ACTS, more=[basket()]), p5)
        self.assertEqual(SWEEP['P4'], 'A biliary sphincterotomy was performed.')
