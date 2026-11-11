"""Round 5 of the Gemini migration, the ERCP repair D127 (the review of D104-D107, problems 0-4, and the family parity
audit's ERCP notes 1 and 2), SYNTHETIC and REPLAYED: nothing is sent. Each pin is built from its source's own input:
the reviewer's probe texts (finding 25's sweep with a period, the exchange filed as stent_exchange, the clearances),
D106's builder's recorded wordings (disagreement 1, parity note 2) and the parity audit's cannulation documents.

- (0) D106 reads the act's own sentence AND the sentence that immediately follows it when that one continues the act (it
  names no other act), the sentences of the code's own exact evidence that hold the act's words, "nothing was
  retrieved" and "no stones were found".
- (1) An exchange Gemini files as stent_exchange beside the stent_removal (or the placement) it includes is a possible
  exchange: 43275 (or 43274) is never READY beside it.
- (2) Another act's sentence of the act's own passage is never read (the surviving mutant of the review, killed).
- (3) A clearance - a sentence that states a yield and denies only the stones' presence ("Multiple stones were
  extracted ... until no stones remained.") - supports 43264; a denied retrieval still holds it.
- (4) D107's warn quotes the sentence that states the failure, as the installed release does.
- (5) A cannulation stated both achieved and begun and not completed, of ducts nothing sets apart, is the installed
  release's conflict: every ERCP code asks the cannulation, and D107's signals stay.

The installed release c2e53f8e's outcomes on these inputs (jobs._assess_child, as the head-to-head runs it) are quoted
in each pin's docstring.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import assess, coverage, ercp, events, normalize, wording
from tests.test_interpretation_events import asked, check, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import DATE_LINE, a, accepted, act, answer, sc, tg
from tests.test_interpretation_r3_eus import INCOMPLETE, carried, signals
from tests.test_interpretation_r4_ercp import FAILED, PARTICIPANTS, ercp_act

ERCP_HEAD = 'ERCP REPORT'


def built(doc: dict, events_, reach=(), passages=None):
    """(inventory, text) of a synthetic answer whose document is DATE_LINE then ``doc``'s lines and whose passages are
    ``passages`` (each a substring of the document; default: every line of ``doc``) - Gemini lists only the passages it
    cites, so a line of the document may be no passage at all."""
    value, _ = answer(dict(doc) if passages is None else dict(passages), events=list(events_),
                      **({'reach': list(reach)} if reach else {}))
    text = '\n'.join([DATE_LINE, *doc.values()]) + '\n'
    return normalize.normalize(accepted(value), text), text


def duodenoscope(passage: str = 'P1', **changes) -> dict:
    return exam('E1', passage, words='duodenoscope', procedure=a('ercp'), **changes)


# --- (0), (2), (3): D106's sweep -------------------------------------------------------------------------------------

SWEEP = {'H1': ERCP_HEAD,
         'P1': 'The duodenoscope was advanced to the major papilla.',
         'P2': 'Deep biliary cannulation was achieved with a sphincterotome.',
         'P3': 'Cholangiogram showed a mildly dilated bile duct without filling defects.',
         'P4': 'A biliary sphincterotomy was performed.'}
SWEPT = 'The bile duct was swept several times with an extraction balloon.'
NONE_RETRIEVED = 'No stones or sludge were retrieved.'
CLAUSE = 'The bile duct was swept several times with an extraction balloon'
FINDING_25 = 'The bile duct was swept several times with an extraction balloon; no stones or sludge were retrieved.'


def sweep(p5: str, *, more_lines=None, passages=None, kind_words='swept several times with an extraction balloon',
          status_words='was swept several times', technique=('extraction_balloon', 'extraction balloon'),
          target=('bile_duct', 'The bile duct'), more=()):
    """Finding 25's ERCP with ``p5`` for the sweep (the reviewer's probe, cases_r5): the duodenoscope (E1), the
    cannulation (E2), the sphincterotomy (E3) and the act Gemini reads as a performed stone_extraction in P5 (E4)."""
    doc = dict(SWEEP, P5=p5, **(more_lines or {}))
    events_ = [duodenoscope('P1'),
               ercp_act('E2', 'P2', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                        target=tg('', 'bile_duct', 'biliary', ['P2'])),
               ercp_act('E3', 'P4', 'sphincterotomy', 'biliary sphincterotomy', 'was performed',
                        target=tg('', 'bile_duct', 'biliary', ['P4'])),
               ercp_act('E4', 'P5', 'stone_extraction', kind_words, status_words,
                        target=tg('', target[0], target[1], ['P5']), technique=a(technique[0], technique[1], ['P5'])),
               *more]
    passages = None if passages is None else dict(SWEEP, **passages)
    inv, text = built(doc, events_, [reached('E1', 'ampulla', 'major papilla', 'P1')], passages)
    return inv, text, doc


def held_nothing_retrieved(test, p, said: str) -> None:
    """``p`` (43264) is held with D106's performed_status question quoting ``said``, never READY, never excluded."""
    test.assertEqual((p.bucket, p.status, asked(p), p.support['reason'], p.support['acts'],
                      p.support.get('question_events')),
                     ('selected', 'needs_clarification', ['performed_status'], ercp.NOTHING_RETRIEVED, [], ['E4']))
    test.assertIn(f'({wording.quote(said, 120)})', p.clarifications[0].question)
    test.assertIn('nothing was retrieved', p.clarifications[0].reason)


def ready_on(test, p, acts=('E4',)) -> None:
    test.assertEqual((p.status, asked(p), [item['id'] for item in p.support['acts']]), ('ready', [], list(acts)))


class D127NextSentence(SimpleTestCase):
    def test_d127_problem_0_finding_25_with_a_period_the_next_sentence_continues_the_sweep(self):
        """The review's problem 0: finding 25's document with a period where the semicolon was - one passage, two
        sentences - with Corti citing both sentences or the first, with no participant and with Astra and Fable read
        and proposing nothing: 43264 is held with the question quoting both sentences (it was READY; c2e53f8e EXCLUDES
        it when Corti cites both, and HOLDS it, performed_status, when Corti cites the first). 43262 stays READY."""
        two = f'{SWEPT} {NONE_RETRIEVED}'
        inv, text, doc = sweep(two)
        self.assertEqual(events.Reading.of(inv).events['E4']['status']['value'], 'performed')
        for cited in (two, SWEPT):
            for participants in PARTICIPANTS:
                with self.subTest(cited=cited, participants=len(participants)):
                    result = run(inv, text, [('43262', doc['P4']), ('43264', cited)], participants=participants)
                    held_nothing_retrieved(self, proposal(result, '43264'), two)
                    sphincterotomy = proposal(result, '43262')
                    self.assertEqual((sphincterotomy.status, asked(sphincterotomy)), ('ready', []))

    def test_d127_problem_0_the_denial_on_its_own_line(self):
        """The review's problem 0, the negation on its own line: a separate passage of Gemini's (cited by nothing of the
        sweep), or no passage at all with Corti citing both lines - 43264 is held with the question quoting both lines
        (it was READY; c2e53f8e HOLDS it, performed_status, in each shape)."""
        shapes = {
            'a passage, Corti cites both lines': (None, (SWEPT, NONE_RETRIEVED)),
            'a passage, Corti cites the first line': (None, (SWEPT,)),
            'no passage, Corti cites both lines': ({'P5': SWEPT}, (SWEPT, NONE_RETRIEVED)),
        }
        for name, (passages, cited) in shapes.items():
            inv, text, doc = sweep(SWEPT, more_lines={'P6': NONE_RETRIEVED}, passages=passages)
            reading = events.Reading.of(inv)
            self.assertEqual('P6' in reading.passages, passages is None)
            self.assertEqual(reading.events['E4']['kind']['passages'], ['P5'])
            for participants in PARTICIPANTS:
                with self.subTest(shape=name, participants=len(participants)):
                    result = run(inv, text, [('43264', cited)], participants=participants)
                    held_nothing_retrieved(self, proposal(result, '43264'), f'{SWEPT} {NONE_RETRIEVED}')

    def test_d127_disagreement_1_the_wordings_the_installed_release_holds_or_excludes(self):
        """D106's builder's disagreement 1 (= the parity audit's note 2), each with no participant and with Astra and
        Fable read: "nothing was retrieved" (no stone word; c2e53f8e HOLDS, act_missing), "no stones were found" (no
        retrieval word; c2e53f8e HELD it on the builder's document, and READYs it on this one), and Gemini's passage
        only the sentence's first clause with Corti citing the sentence (c2e53f8e EXCLUDES) - 43264 held, never READY
        (each was READY) - and each wording as two sentences (c2e53f8e HOLDS, act_missing)."""
        nothing = 'The bile duct was swept several times with an extraction balloon; nothing was retrieved.'
        found = 'The bile duct was swept several times with a balloon; no stones were found.'
        found_two = 'The bile duct was swept several times with a balloon. No stones were found.'
        nothing_two = 'The bile duct was swept with an extraction balloon. Nothing was retrieved.'
        balloon = dict(kind_words='swept several times with a balloon', technique=('balloon', 'balloon'))
        shapes = {
            'nothing was retrieved': (dict(p5=nothing), nothing, nothing),
            'no stones were found': (dict(p5=found, **balloon), found, found),
            "Gemini's passage the first clause": (dict(p5=FINDING_25, passages={'P5': CLAUSE}), FINDING_25,
                                                  FINDING_25),
            'nothing was retrieved, two sentences': (dict(p5=nothing_two, kind_words='swept with an extraction balloon',
                                                          status_words='was swept'), nothing_two, nothing_two),
            'no stones were found, two sentences': (dict(p5=found_two, **balloon),
                                                    'The bile duct was swept several times with a balloon.', found_two),
        }
        for name, (options, cited, said) in shapes.items():
            options = dict(options)
            inv, text, doc = sweep(options.pop('p5'), **options)
            for participants in PARTICIPANTS:
                with self.subTest(wording=name, participants=len(participants)):
                    result = run(inv, text, [('43264', cited)], participants=participants)
                    held_nothing_retrieved(self, proposal(result, '43264'), said)
        # the sentence reader alone (one sentence)
        self.assertTrue(ercp.states_nothing_retrieved(nothing))
        self.assertTrue(ercp.states_nothing_retrieved(found))
        self.assertFalse(ercp.states_nothing_retrieved('Nothing abnormal was seen; the duct was swept with a balloon.'))
        self.assertFalse(ercp.states_nothing_retrieved('Two stones were extracted; nothing else was retrieved.'))


class D127OwnSentence(SimpleTestCase):
    def test_d127_problem_2_another_acts_sentence_in_the_acts_own_passage_is_never_read(self):
        """The review's problem 2 (its surviving mutant read every sentence of the act's passages): the sweep of the bile
        duct shares its passage with ANOTHER act's sentence that states 'no stones were retrieved' - the pancreatic
        duct's sweep filed as its own stone_extraction (E5), or not filed at all; the bile duct's sweep (E4) or a basket
        extraction is the act's own sentence. 43264 stays READY on E4 alone: E5's own sentence states nothing retrieved,
        so E5 leaves E* and is still read (c2e53f8e: HELD, performed_status, with E5 filed - its reader reads the
        passage; READY on the basket shape)."""
        pancreatic = 'The pancreatic duct was swept with a balloon; no stones were retrieved.'
        swept = 'The bile duct was then swept with an extraction balloon.'
        basket = 'Two stones were extracted from the bile duct with a basket.'
        e5 = ercp_act('E5', 'P5', 'stone_extraction', 'swept with a balloon', 'was swept',
                      target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                      technique=a('balloon', 'balloon', ['P5']))
        shapes = {
            'the other act filed': (dict(p5=f'{pancreatic} {swept}', kind_words='swept with an extraction balloon',
                                         status_words='was then swept', more=[e5]), swept, ('E4',), ('E4', 'E5')),
            'the other act not filed, a basket extraction': (
                dict(p5=f'{pancreatic} {basket}', kind_words='extracted', status_words='were extracted',
                     technique=('basket', 'basket'), target=('bile_duct', 'bile duct')), basket, ('E4',), ('E4',)),
        }
        for name, (options, cited, acts, read) in shapes.items():
            options = dict(options)
            inv, text, doc = sweep(options.pop('p5'), **options)
            reading = events.Reading.of(inv)
            with self.subTest(shape=name):
                self.assertIsNone(ercp.nothing_retrieved(reading, reading.events['E4']))
                ready_on(self, proposal(run(inv, text, [('43264', cited)]), '43264'), acts)
                self.assertEqual(events.evaluate('43264', (), reading).read, read)
                if 'E5' in reading.events:
                    statement = ercp.nothing_retrieved(reading, reading.events['E5'])
                    self.assertIsNotNone(statement)
                    self.assertEqual([place['text'] for place in statement], [pancreatic])

    def test_d127_problem_2_the_next_sentence_names_another_act_and_does_not_continue(self):
        """The sentence after the act's own is another act's - the pancreatic duct's sweep, filed as E5 - so it does not
        continue the act: 43264 READY on E4 alone (c2e53f8e HOLDS it, performed_status). The cost, recorded: the same
        sentence with no event of Gemini's for it names no act, so it is read as the sweep's continuation and 43264 is
        held (fail-closed, never READY, never excluded; c2e53f8e HOLDS it too)."""
        p5 = 'The bile duct was swept with an extraction balloon. The pancreatic duct was then swept with a balloon; no ' \
             'stones were retrieved.'
        first = 'The bile duct was swept with an extraction balloon.'
        e5 = ercp_act('E5', 'P5', 'stone_extraction', 'swept with a balloon', 'was then swept',
                      target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                      technique=a('balloon', 'balloon', ['P5']))
        options = dict(kind_words='swept with an extraction balloon', status_words='was swept')
        inv, text, doc = sweep(p5, more=[e5], **options)
        ready_on(self, proposal(run(inv, text, [('43264', first)]), '43264'))
        inv, text, doc = sweep(p5, **options)
        held_nothing_retrieved(self, proposal(run(inv, text, [('43264', first)]), '43264'), p5)


class D127Clearance(SimpleTestCase):
    def test_d127_problem_3_a_complete_clearance_supports_43264(self):
        """The review's problem 3 (a cost D106 introduced): a sentence that states a yield and then denies only the
        stones' presence is a clearance - 43264 READY on the extraction, with no participant and with Astra and Fable
        read (each was held nothing_retrieved; c2e53f8e READYs each)."""
        clearances = {
            'until no stones remained': ('Multiple stones were extracted from the bile duct with an extraction balloon '
                                         'until no stones remained.', 'extracted', 'were extracted', 'bile duct'),
            'no stones remained on the final cholangiogram': (
                'The bile duct was swept with an extraction balloon and several small stones were removed; no stones '
                'remained on the final cholangiogram.', 'swept with an extraction balloon', 'were removed',
                'The bile duct'),
            'no stones were seen on the final cholangiogram': (
                'The bile duct was swept with an extraction balloon and several small stones were removed; no stones '
                'were seen on the final cholangiogram.', 'swept with an extraction balloon', 'were removed',
                'The bile duct'),
        }
        for name, (p5, kind_words, status_words, duct) in clearances.items():
            inv, text, doc = sweep(p5, kind_words=kind_words, status_words=status_words, target=('bile_duct', duct))
            for participants in PARTICIPANTS:
                with self.subTest(clearance=name, participants=len(participants)):
                    ready_on(self, proposal(run(inv, text, [('43264', p5)], participants=participants), '43264'))
        # across a period: the yield in the act's own sentence, the presence denial in the next
        p5 = 'Two stones were extracted from the bile duct with an extraction balloon. No stones remained.'
        inv, text, doc = sweep(p5, kind_words='extracted', status_words='were extracted',
                               target=('bile_duct', 'bile duct'))
        ready_on(self, proposal(run(inv, text, [('43264', p5)]), '43264'))
        for sentence in ('Multiple stones were extracted from the bile duct with an extraction balloon until no stones '
                         'remained.', 'Several stones were extracted with an extraction balloon; no residual stones were '
                         'seen.', 'Several stones were extracted with an extraction balloon, leaving no residual stones.'):
            with self.subTest(sentence=sentence):
                self.assertFalse(ercp.states_nothing_retrieved(sentence))

    def test_d127_problem_3_controls_a_denied_retrieval_or_no_yield_still_holds(self):
        """Controls: the clearance needs the act's own yield, stated in a clause that holds the act's own words, and it
        releases only a denial of the stones' presence. A denied retrieval beside a stated extraction (c2e53f8e: held,
        conflict:stone_extraction), a denial with no yield ("until no stones remained" alone, "no stones were seen",
        "none remained" after "no stones were retrieved"), a yield never done ("were to be extracted"), a yield in a
        clause none of the act's words are in - an extraction at an earlier ERCP Gemini filed no event for, and D106's
        recorded cost "no stones were seen; sludge was retrieved", which stays (c2e53f8e READYs it) - and a retrieval
        denied four words after the stones each keep 43264 held (c2e53f8e, in order: conflict:stone_extraction,
        performed_status, READY, EXCLUDED, performed_status, performed_status, READY, conflict:stone_extraction). A
        sentence of two acts is D106's own sentence read whole, so the clearance never releases it: the basket's yield
        beside the sweep's "no stones were seen" in a clause of the sweep's, and a yield in a clause the two acts share
        (neither act's), keep 43264 held (1caaf0609 holds both; c2e53f8e: conflict:stone_extraction on the first)."""
        held = {
            'a stone extracted; no stones were retrieved': (
                'A stone was extracted with a basket and the duct was then swept with an extraction balloon; no stones '
                'were retrieved.', 'extracted', 'was extracted', 'the duct'),
            'until no stones remained, no yield': (
                'The bile duct was swept with an extraction balloon until no stones remained.',
                'swept with an extraction balloon', 'was swept', 'The bile duct'),
            'no stones were seen, no yield': (
                'The bile duct was swept with an extraction balloon; no stones were seen on the final cholangiogram.',
                'swept with an extraction balloon', 'was swept', 'The bile duct'),
            'no stones were retrieved and none remained': (
                'The bile duct was swept several times with an extraction balloon; no stones were retrieved and none '
                'remained.', 'swept several times with an extraction balloon', 'was swept several times',
                'The bile duct'),
            'to be extracted, none retrieved': (
                'The stones were to be extracted from the bile duct with an extraction balloon, but none were '
                'retrieved.', 'extracted', 'were to be extracted', 'bile duct'),
            "an earlier extraction, the yield's clause not the sweep's": (
                'Stones were extracted at the index ERCP in 2024; today the duct was swept with an extraction balloon '
                'and no stones were seen.', 'swept with an extraction balloon', 'was swept', 'the duct'),
            'no stones were seen; sludge was retrieved (D106 recorded cost)': (
                'The bile duct was swept with an extraction balloon; no stones were seen; sludge was retrieved.',
                'swept with an extraction balloon', 'was swept', 'The bile duct'),
            'a yield, then a retrieval denied four words on': (
                'Two stones were extracted from the bile duct with an extraction balloon; no stones or sludge could '
                'ultimately be retrieved.', 'extracted', 'were extracted', 'bile duct'),
        }
        for name, (p5, kind_words, status_words, duct) in held.items():
            inv, text, doc = sweep(p5, kind_words=kind_words, status_words=status_words, target=('bile_duct', duct))
            with self.subTest(held=name):
                held_nothing_retrieved(self, proposal(run(inv, text, [('43264', p5)]), '43264'), p5)
        # no yield: an intent ("were to be extracted"), or a yield verb a negator governs ("were not removed")
        for sentence in ('The stones were to be extracted with an extraction balloon; no stones were seen.',
                         'Stones were not removed; no stones were seen on the final cholangiogram.'):
            with self.subTest(no_yield=sentence):
                self.assertTrue(ercp.states_nothing_retrieved(sentence))
        # a sentence of two acts, the sweep (E4) and the basket extraction (E5): the clearance releases neither
        basket = ercp_act('E5', 'P5', 'stone_extraction', 'removed', 'were removed',
                          target=tg('', 'bile_duct', 'the duct', ['P5']), technique=a('basket', 'basket', ['P5']))
        two_acts = {
            "the basket's yield, the sweep's denial": 'Two stones were removed with a basket; the duct was then swept '
                                                      'with an extraction balloon and no stones were seen.',
            'a yield in a clause the two acts share': 'Two stones were removed with a basket and the duct was then '
                                                      'swept with an extraction balloon; no stones were seen.',
        }
        for name, p5 in two_acts.items():
            inv, text, doc = sweep(p5, kind_words='swept with an extraction balloon', status_words='was then swept',
                                   target=('bile_duct', 'the duct'), more=[basket])
            reading = events.Reading.of(inv)
            with self.subTest(two_acts=name):
                held_nothing_retrieved(self, proposal(run(inv, text, [('43264', p5)]), '43264'), p5)
                for eid in ('E4', 'E5'):
                    statement = ercp.nothing_retrieved(reading, reading.events[eid])
                    self.assertIsNotNone(statement, eid)
                    self.assertEqual([place['text'] for place in statement], [p5])


# --- (1): D105's exchange, filed as stent_exchange ------------------------------------------------------------------

EXCHANGE = {'H1': ERCP_HEAD,
            'P1': 'Procedure: ERCP with biliary stent exchange.',
            'P2': 'The duodenoscope was advanced to the major papilla.',
            'P3': 'The existing biliary stent was removed with a snare.',
            'P4': 'Deep biliary cannulation was achieved with a sphincterotome.',
            'P5': 'A 10 Fr x 9 cm plastic biliary stent was placed into the common bile duct.'}


def removal(**changes) -> dict:
    options = dict(technique=a('snare', 'snare', ['P3']), target=tg('', 'bile_duct', 'biliary', ['P3']))
    options.update(changes)
    return ercp_act('E2', 'P3', 'stent_removal', 'removed', options.pop('status_words', 'was removed with a snare'),
                    **options)


def placement() -> dict:
    return ercp_act('E4', 'P5', 'stent', 'stent', 'was placed', technique=a('stent', 'plastic biliary stent', ['P5']),
                    target=tg('', 'common_bile_duct', 'common bile duct', ['P5']))


def exchange_event(side: str = 'placement') -> dict:
    """The review's problem 1: the exchange as Gemini files it - the Procedure line's kind words ('biliary stent
    exchange'), with the placement's sentence (or, mirrored, the removal's) giving its status and target."""
    item = act('E5', 'P1', 'stent_exchange', 'biliary stent exchange', procedure=a('ercp'))
    if side == 'placement':
        item.update(technique=a('stent', 'plastic biliary stent', ['P5']), status=a('performed', 'was placed', ['P5']),
                    target=tg('', 'common_bile_duct', 'common bile duct', ['P5']))
    else:
        item.update(technique=a('snare', 'snare', ['P3']), status=a('performed', 'was removed with a snare', ['P3']),
                    target=tg('', 'bile_duct', 'biliary', ['P3']))
    return item


CANNULATED = ercp_act('E3', 'P4', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                      target=tg('', 'bile_duct', 'biliary', ['P4']), technique=a('sphincterotome', 'sphincterotome',
                                                                                 ['P4']))


def exchange_document(events_, lines=None):
    doc = dict(EXCHANGE, **(lines or {}))
    inv, text = built(doc, [duodenoscope('P2'), *events_], [reached('E1', 'ampulla', 'major papilla', 'P2')])
    return inv, text, doc


def held_as_part(test, p, part: str, question_events) -> None:
    """``p`` is held with D127's exchange question: whether the ``part`` (removal or placement) was part of the stent
    exchange (43276), never READY and never "not documented"."""
    test.assertEqual((p.bucket, p.status, asked(p), p.support['reason'], p.support.get('question_events')),
                     ('selected', 'needs_clarification', ['performed_status'], ercp.POSSIBLE_EXCHANGE,
                      list(question_events)))
    question = p.clarifications[0].question
    test.assertTrue(question.startswith(f'Was the stent {part}'), question)
    test.assertIn('part of the stent exchange', question)
    test.assertIn('one stent exchange (43276)', question)
    test.assertEqual(check(p, 'service.status').status, 'warn')


class D127ExchangeFiled(SimpleTestCase):
    def test_d127_problem_1_an_exchange_filed_beside_the_removal_it_includes(self):
        """The review's problem 1: finding 22's document with the exchange filed as stent_exchange (E5, the Procedure
        line's kind with the placement's status and target) beside the stent_removal (E2), and no stent event; Corti
        cites 43275 at the removal and 43276 at the Procedure line (43274 too, at the placement), with no participant and
        with Astra and Fable read. 43275 and 43276 are held with one question - was the removal part of the exchange -
        never both READY (both were; c2e53f8e holds both, act_missing, and READYs 43274); 43274 stays held not
        documented."""
        inv, text, doc = exchange_document([removal(), CANNULATED, exchange_event()])
        reading = events.Reading.of(inv)
        self.assertEqual([(first['id'], second['id']) for first, second in ercp.exchange_pairs(reading)],
                         [('E2', 'E5')])
        for codes in (('43275', '43276'), ('43275', '43274', '43276'), ('43275',)):
            cited = {'43275': doc['P3'], '43274': doc['P5'], '43276': doc['P1']}
            for participants in PARTICIPANTS:
                with self.subTest(codes=codes, participants=len(participants)):
                    result = run(inv, text, [(code, cited[code]) for code in codes], participants=participants)
                    for code in ('43275', '43276'):
                        if code in codes:
                            held_as_part(self, proposal(result, code), 'removal', ('E2', 'E5'))
                    if '43274' in codes:
                        p = proposal(result, '43274')
                        self.assertEqual((p.status, p.support['reason']), ('needs_clarification',
                                                                           events.NOT_DOCUMENTED))

    def test_d127_problem_1_the_mirror_an_exchange_filed_beside_the_placement_it_includes(self):
        """The mirror shape: the exchange filed with the removal's status and target (E5) beside the stent placement
        (E4): 43274 and 43276 are held - was the placement part of the exchange - never both READY (both were;
        c2e53f8e READYs 43274 and holds 43276, act_missing); 43275 stays held not documented."""
        inv, text, doc = exchange_document([exchange_event('removal'), CANNULATED, placement()])
        reading = events.Reading.of(inv)
        self.assertEqual([(first['id'], second['id']) for first, second in ercp.exchange_pairs(reading)],
                         [('E5', 'E4')])
        cited = {'43275': doc['P3'], '43274': doc['P5'], '43276': doc['P1']}
        for codes in (('43274', '43276'), ('43275', '43274', '43276'), ('43274',)):
            for participants in PARTICIPANTS:
                with self.subTest(codes=codes, participants=len(participants)):
                    result = run(inv, text, [(code, cited[code]) for code in codes], participants=participants)
                    for code in ('43274', '43276'):
                        if code in codes:
                            held_as_part(self, proposal(result, code), 'placement', ('E5', 'E4'))
                    if '43275' in codes:
                        self.assertEqual(proposal(result, '43275').support['reason'], events.NOT_DOCUMENTED)

    def test_d127_problem_1_a_held_code_keeps_its_own_question_and_three_events_keep_d105s(self):
        """D89: the removal's time worded and unanchored ('During the procedure') - 43275 keeps its own event_time
        question, and 43276 is held with the exchange question (the doubted removal may be today's). The refuter's three
        events (removal, placement and exchange) keep D105's question, its pair first (c2e53f8e: 43275 and 43276 held
        act_missing on both; 43274 READY on the three events)."""
        inv, text, doc = exchange_document(
            [removal(time=a('current_encounter', 'During the procedure', ['P3'])), CANNULATED, exchange_event()],
            lines={'P3': 'During the procedure the existing biliary stent was removed with a snare.'})
        result = run(inv, text, [('43275', doc['P3']), ('43276', doc['P1'])])
        self.assertEqual(asked(proposal(result, '43275')), ['event_time'])
        held_as_part(self, proposal(result, '43276'), 'removal', ('E2', 'E5'))
        inv, text, doc = exchange_document([removal(), CANNULATED, placement(), exchange_event()])
        self.assertEqual([(first['id'], second['id']) for first, second in
                          ercp.exchange_pairs(events.Reading.of(inv))], [('E2', 'E4'), ('E2', 'E5'), ('E5', 'E4')])
        result = run(inv, text, [('43275', doc['P3']), ('43274', doc['P5']), ('43276', doc['P1'])])
        for code in ('43275', '43274', '43276'):
            p = proposal(result, code)
            self.assertEqual((p.status, p.support.get('question_events')), ('needs_clarification', ['E2', 'E4']))
            self.assertTrue(p.clarifications[0].question.startswith('Were the stent removal'))

    def test_d127_problem_1_controls_the_exchange_alone_or_set_apart_stays_ready(self):
        """Controls: the exchange alone - 43276 READY, 43275 and 43274 held not documented, as before; a removal in the
        pancreatic duct (both ducts verified, apart), a removal denied, and a removal verified at an earlier ERCP pair
        with nothing - 43276 READY (43275 READY on the pancreatic removal). Unchanged from 1caaf0609; c2e53f8e holds
        43276 act_missing in each (its reader finds no exchange act), and READYs 43274 beside the exchange alone."""
        inv, text, doc = exchange_document([CANNULATED, exchange_event()])
        self.assertEqual(ercp.exchange_pairs(events.Reading.of(inv)), [])
        result = run(inv, text, [('43275', doc['P3']), ('43274', doc['P5']), ('43276', doc['P1'])])
        self.assertEqual({code: (proposal(result, code).status, proposal(result, code).support['reason'])
                          for code in ('43275', '43274', '43276')},
                         {'43275': ('needs_clarification', events.NOT_DOCUMENTED),
                          '43274': ('needs_clarification', events.NOT_DOCUMENTED),
                          '43276': ('ready', events.SUPPORTED)})
        apart = {
            'pancreatic removal': ({'P3': 'The existing pancreatic duct stent was removed with a snare.'},
                                   dict(target=tg('', 'pancreatic_duct', 'pancreatic duct', ['P3'])), ('43275', '43276')),
            'removal denied': ({'P3': 'The existing biliary stent was not removed.'},
                               dict(status='not_performed', status_words='was not removed'), ('43276',)),
            'removal at an earlier ERCP': (
                {'P3': 'At the prior ERCP in 2025 the previous biliary stent was removed with a snare.'},
                dict(time=a('earlier_encounter', 'At the prior ERCP in 2025', ['P3'])), ('43276',)),
        }
        for name, (lines, changes, codes) in apart.items():
            inv, text, doc = exchange_document([removal(**changes), CANNULATED, exchange_event()], lines=lines)
            with self.subTest(control=name):
                self.assertEqual(ercp.exchange_pairs(events.Reading.of(inv)), [])
                cited = {'43275': doc['P3'], '43276': doc['P1']}
                result = run(inv, text, [(code, cited[code]) for code in codes])
                for code in codes:
                    self.assertEqual((proposal(result, code).status, asked(proposal(result, code))), ('ready', []))


# --- (4) and (5): D107 and the cannulation conflict -----------------------------------------------------------------

def access(p3: str, failed_target, words: str = 'were unsuccessful', achieved_target=None, achieved_line=None,
           failed_changes=None, more_lines=None, more=()):
    """The parity audit's note 1 document: the duodenoscope (E1), the biliary access achieved (E2) and a cannulation
    begun and not completed (E3, in ``p3``)."""
    lines = {'H1': ERCP_HEAD, 'P1': 'The duodenoscope was advanced to the major papilla.',
             'P2': achieved_line or 'Deep biliary cannulation was achieved with a sphincterotome.', 'P3': p3,
             **(more_lines or {})}
    changes = dict(failed_changes or {})
    events_ = [duodenoscope('P1'),
               ercp_act('E2', 'P2', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                        target=achieved_target or tg('', 'bile_duct', 'biliary', ['P2'])),
               ercp_act('E3', 'P3', 'cannulation', 'cannulation', words,
                        status=changes.pop('status', 'attempted_not_completed'), target=failed_target, **changes),
               *more]
    inv, text = inventory(lines, events=events_, reach=[reached('E1', 'ampulla', 'major papilla', 'P1')])
    return inv, text, lines


INITIAL = 'Initial attempts at biliary cannulation were unsuccessful.'
BILIARY = tg('', 'bile_duct', 'biliary', ['P3'])
CONFLICTING = 'Conflicting values documented: cannulation outcome.'


def conflict_held(test, p, more=()) -> None:
    test.assertEqual((p.status, asked(p)), ('needs_clarification', [*more, 'cannulation']))
    test.assertEqual(p.clarifications[-1].question, 'ERCP: confirm whether, and which, duct was cannulated.')
    test.assertTrue(p.clarifications[-1].reason.startswith('The document gives conflicting values for the cannulation '
                                                           'outcome: “'), p.clarifications[-1].reason)
    test.assertIn(CONFLICTING, check(p, 'facts.required').detail)


def failed_ercp(p4: str = FAILED['P4']):
    """Finding 26's document (D107's own pins' failed_cannulation) with its report heading, as the installed release's
    probe reads it: the duodenoscope advanced (E1), the biliary cannulation begun and not completed (E2), the
    sphincterotomy (E3) and the stent placement (E4) denied, all of kind; (inventory, text, codes)."""
    lines = {'H1': ERCP_HEAD, **FAILED, 'P4': p4}
    terminated = p4.startswith('The procedure was terminated')
    denial = ('no sphincterotomy and no stent placement were performed' if terminated
              else 'No sphincterotomy and no stent placement were performed')
    events_ = [duodenoscope('P1'),
               ercp_act('E2', 'P3', 'cannulation', 'biliary cannulation', 'were unsuccessful',
                        status='attempted_not_completed', target=tg('', 'bile_duct', 'biliary', ['P3'])),
               ercp_act('E3', 'P4', 'sphincterotomy', 'sphincterotomy', denial, status='not_performed',
                        scope=sc('all_of_kind', 'no' if terminated else 'No', ['P4'])),
               ercp_act('E4', 'P4', 'stent', 'stent placement', 'no stent placement were performed',
                        status='not_performed', scope=sc('all_of_kind', 'no stent', ['P4']))]
    inv, text = inventory(lines, events=events_,
                          reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')])
    return inv, text, [('43260', lines['P3']), ('43262', 'no sphincterotomy' if terminated else 'No sphincterotomy'),
                       ('43274', 'no stent placement were performed')]


class D127IncompleteWording(SimpleTestCase):
    def test_d127_problem_4_the_warn_quotes_the_sentence_that_states_the_failure(self):
        """The review's problem 4: on finding 26's document without 'The procedure was terminated;' the warn quotes the
        sentence c2e53f8e quotes, “Multiple attempts at biliary cannulation were unsuccessful.” (installed on this text:
        'Documented as incomplete: “Multiple attempts at biliary cannulation were unsuccessful.” (cue “incomplete:
        Multiple attempts at biliary cannulation were unsuccessful.”, documented service). Kept for review: ...',
        43260 READY), with the 52/53 consideration, for no participant and for Astra and Fable read. On finding 26's own
        text the same sentence, where c2e53f8e quotes “The procedure was terminated” - words no attribute of this
        reading verifies (recorded); the examination stated terminated still quotes them first (D107's own pin)."""
        installed = '“Multiple attempts at biliary cannulation were unsuccessful.”'
        for p4 in ('No sphincterotomy and no stent placement were performed.', FAILED['P4']):
            inv, text, codes = failed_ercp(p4)
            for participants in PARTICIPANTS:
                with self.subTest(p4=p4, participants=len(participants)):
                    base = proposal(run(inv, text, codes, participants=participants), '43260')
                    self.assertEqual((base.status, carried(base)),
                                     ('ready', signals('43260', 'Multiple attempts at biliary cannulation were '
                                                                'unsuccessful.')))
                    self.assertTrue(check(base, INCOMPLETE).detail.startswith(f'Documented as incomplete: {installed}'))
        reading = events.Reading.of(failed_ercp()[0])
        sentence = ercp.statement_sentence(reading, reading.events['E2'])
        self.assertIsNotNone(sentence)
        self.assertEqual(sentence['text'], 'Multiple attempts at biliary cannulation were unsuccessful.')


class D127CannulationConflict(SimpleTestCase):
    def test_d127_parity_1_the_cannulation_stated_achieved_and_unsuccessful_is_the_conflict(self):
        """The parity audit's note 1: 'Deep biliary cannulation was achieved with a sphincterotome.' beside 'Initial
        attempts at biliary cannulation were unsuccessful.' (E2 performed, E3 attempted_not_completed, both of the bile
        duct), 43260 citing the first line, with no participant and with Astra and Fable read: 43260 is held with the
        cannulation question and keeps D107's warn and 52/53 (it was READY; c2e53f8e: HELD [cannulation] with the warn
        and 52/53). With 43262 also proposed, both ask the cannulation."""
        inv, text, lines = access(INITIAL, BILIARY)
        for participants in PARTICIPANTS:
            with self.subTest(participants=len(participants)):
                base = proposal(run(inv, text, [('43260', lines['P1'])], participants=participants), '43260')
                conflict_held(self, base)
                self.assertEqual(carried(base), signals('43260', INITIAL))
        conflict = ercp.cannulation_conflict(events.Reading.of(inv), 'gi.ercp')
        self.assertIsNotNone(conflict)
        note, places = conflict
        self.assertEqual(note, 'Conflicting documented values: bile duct cannulated, bile duct not achieved.')
        self.assertEqual([place['text'] for place in places],
                         ['Deep biliary cannulation was achieved with a sphincterotome.', INITIAL])
        self.assertTrue(all(text[place['start']:place['end']] == place['text'] for place in places))
        sphincterotomy = ercp_act('E5', 'P6', 'sphincterotomy', 'biliary sphincterotomy', 'was performed',
                                  target=tg('', 'bile_duct', 'biliary', ['P6']))
        inv, text, lines = access(INITIAL, BILIARY, more_lines={'P6': 'A biliary sphincterotomy was performed.'},
                                  more=[sphincterotomy])
        result = run(inv, text, [('43260', lines['P1']), ('43262', lines['P6'])])
        conflict_held(self, proposal(result, '43260'), more=('base_included',))
        conflict_held(self, proposal(result, '43262'))

    def test_d127_parity_1_finding_26_with_the_access_achieved(self):
        """The parity audit's second input: finding 26's text plus 'Deep biliary cannulation was achieved with a
        precut sphincterotome.' - 43260 held with the cannulation question (c2e53f8e: HELD [cannulation]); the excluded
        43262 and 43274 stay excluded, the cannulation among what reinstating them would wait for."""
        lines_more = 'Deep biliary cannulation was achieved with a precut sphincterotome.'
        achieved = ercp_act('E5', 'P5', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                            target=tg('', 'bile_duct', 'biliary', ['P5']),
                            technique=a('sphincterotome', 'precut sphincterotome', ['P5']))
        lines = {'H1': ERCP_HEAD, **FAILED, 'P5': lines_more}
        events_ = [duodenoscope('P1'),
                   ercp_act('E2', 'P3', 'cannulation', 'biliary cannulation', 'were unsuccessful',
                            status='attempted_not_completed', target=tg('', 'bile_duct', 'biliary', ['P3'])),
                   ercp_act('E3', 'P4', 'sphincterotomy', 'sphincterotomy',
                            'no sphincterotomy and no stent placement were performed', status='not_performed',
                            scope=sc('all_of_kind', 'no', ['P4'])),
                   ercp_act('E4', 'P4', 'stent', 'stent placement', 'no stent placement were performed',
                            status='not_performed', scope=sc('all_of_kind', 'no stent', ['P4'])),
                   achieved]
        inv, text = inventory(lines, events=events_,
                              reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')])
        result = run(inv, text, [('43260', lines['P3']), ('43262', 'no sphincterotomy'),
                                 ('43274', 'no stent placement were performed')])
        conflict_held(self, proposal(result, '43260'))
        for code in ('43262', '43274'):
            p = proposal(result, code)
            self.assertEqual(p.status, 'excluded')
            self.assertIn('cannulation', [item['fact'] for item in p.support['reinstatement_waits']])

    def test_d127_parity_1_ducts_nothing_sets_apart_and_a_doubted_failure(self):
        """'Of one duct' as D45 reads ducts: the failure's duct not stated, or the ampulla, never sets the two apart
        (c2e53f8e: HELD [cannulation] on both); a failure whose failure words do not bind (status unverified, D87: a
        doubt is a question) is a side too (c2e53f8e: HELD [cannulation])."""
        shapes = {
            'duct not stated': ('Initial cannulation attempts were unsuccessful.', tg(), 'were unsuccessful'),
            'the ampulla': ('Initial attempts at cannulation of the papilla were unsuccessful.',
                            tg('', 'ampulla', 'papilla', ['P3']), 'were unsuccessful'),
            'failure words that do not bind': (INITIAL, BILIARY, 'could not be achieved'),
        }
        for name, (p3, target, words) in shapes.items():
            inv, text, lines = access(p3, target, words)
            with self.subTest(shape=name):
                self.assertIsNotNone(ercp.cannulation_conflict(events.Reading.of(inv), 'gi.ercp'))
                conflict_held(self, proposal(run(inv, text, [('43260', lines['P1'])]), '43260'))

    def test_d127_parity_1_controls_no_conflict(self):
        """Controls, no conflict: the pancreatic duct's failure beside the biliary access (D107's avoidance; c2e53f8e
        READY, no signal), a failure verified at an earlier ERCP (c2e53f8e READY), two cannulations achieved, and a
        biliary failure beside the PANCREATIC access - two ducts set apart: READY with D107's signals (recorded: c2e53f8e
        holds it [cannulation]); any other family: None."""
        shapes = {
            'pancreatic failure': (dict(p3='Pancreatic duct cannulation was unsuccessful.',
                                        failed_target=tg('', 'pancreatic_duct', 'Pancreatic duct', ['P3']),
                                        words='was unsuccessful'), ((), [])),
            'failed at an earlier ERCP': (dict(p3='At the prior ERCP in 2025 biliary cannulation was unsuccessful.',
                                               failed_target=BILIARY, words='was unsuccessful',
                                               failed_changes=dict(time=a('earlier_encounter',
                                                                          'At the prior ERCP in 2025', ['P3']))),
                                          ((), [])),
            'two achieved': (dict(p3='Deep biliary cannulation was confirmed with a guidewire.', failed_target=BILIARY,
                                  words='was confirmed', failed_changes=dict(status='performed')), ((), [])),
            'biliary failure beside the pancreatic access': (
                dict(p3='Biliary cannulation was unsuccessful.', failed_target=tg('', 'bile_duct', 'Biliary', ['P3']),
                     words='was unsuccessful',
                     achieved_line='Deep pancreatic duct cannulation was achieved with a sphincterotome.',
                     achieved_target=tg('', 'pancreatic_duct', 'pancreatic duct', ['P2'])),
                signals('43260', 'Biliary cannulation was unsuccessful.')),
        }
        for name, (options, carries) in shapes.items():
            inv, text, lines = access(**options)
            reading = events.Reading.of(inv)
            with self.subTest(control=name):
                self.assertIsNone(ercp.cannulation_conflict(reading, 'gi.ercp'))
                base = proposal(run(inv, text, [('43260', lines['P1'])]), '43260')
                self.assertEqual((base.status, asked(base), carried(base)), ('ready', [], carries))
        inv, text, lines = access(INITIAL, BILIARY)
        reading = events.Reading.of(inv)
        self.assertIsNone(ercp.cannulation_conflict(reading, 'gi.egd'))
        self.assertIsNone(assess._inventory_fact('cannulation', 'gi.egd', None, reading, coverage.sessions(reading)))
