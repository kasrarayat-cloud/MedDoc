"""Round 4 of the Gemini migration's refutation, the ERCP repairs (DECISIONS D104, D105, D106 and D107), SYNTHETIC and
REPLAYED: nothing is sent. Each pin is built from its finding's own input.

- D104 (finding 11): a defining act stated 'uncertain' may have been done, so it is a doubt about the narrowed code,
  never an absence of it - 43264 and 43265 proposed for one stone clearance compete whenever the lithotripsy is stated
  positive OR uncertain and possibly current (D74 read positive only, so 43264 was READY beside a held 43265).
- D105 (finding 22): an ERCP with a positive stent removal and a positive stent placement whose ducts nothing sets apart
  is a possible stent exchange - 43275 and 43274 are each held with one question naming the exchange (43276), and 43276
  is held with that question, never "not documented". A removal and a placement verified in different ducts stay
  separate acts.
- D106 (finding 25): a stone_extraction whose own sentence states that nothing was retrieved ("no stones or sludge were
  retrieved") does not support 43264: held with the performed_status question naming that statement, never READY (the
  installed release excludes it; the hold is the fail-closed answer).
- D107 (finding 26): an ERCP whose cannulation, done at this encounter, was begun and not completed gives every code of
  the session D61's service.incomplete warn and the 52/53 consideration, as the installed release gives them: 43260 keeps
  READY and gains both.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import assess, coverage, ercp, events
from tests.test_interpretation_events import asked, check, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, sc, tg
from tests.test_interpretation_r3_claims import READ_NOTHING, claims, stone_clearance
from tests.test_interpretation_r3_eus import INCOMPLETE, carried, signals

PARTICIPANTS = ((), READ_NOTHING)  # no participant, and Astra and Fable read and proposing nothing (production's)


def ercp_act(eid: str, passage: str, kind: str, kind_words: str, status_words: str = '', target=None,
             status: str = 'performed', **changes) -> dict:
    """An ERCP act of this encounter by the documenting team (performed unless ``status`` says otherwise), stated in
    ``passage``."""
    return act(eid, passage, kind, kind_words, status=status, status_words=status_words, procedure=a('ercp'),
               target=target if target is not None else tg(), **changes)


def duodenoscope(passage: str = 'P1', **changes) -> dict:
    return exam('E1', passage, words='duodenoscope', procedure=a('ercp'), **changes)


# --- D104: the round-4 refutation, finding 11 --------------------------------------------------------------------------

# Finding 11's P3 wordings: the lithotripsy stated uncertain, with its status words and its scope words.
UNCERTAIN = {
    'unclear': ('It is unclear from the record whether the 15 mm stone in the common bile duct was fragmented with '
                'mechanical lithotripsy.', 'It is unclear', 'the 15 mm stone in the common bile duct'),
    'unclear, no scope words': ('It is unclear from the record whether the 15 mm stone in the common bile duct was '
                                'fragmented with mechanical lithotripsy.', 'It is unclear from the record whether', ''),
    'may have been required': ('Mechanical lithotripsy of the 15 mm stone in the common bile duct may have been '
                               'required.', 'may have been required', 'the 15 mm stone in the common bile duct'),
}


def uncertain_clearance(name: str):
    p3, status_words, scope_words = UNCERTAIN[name]
    return stone_clearance(p3, status='uncertain', status_words=status_words,
                           scope=sc('single_target', scope_words, ['P3'] if scope_words else []))


class D104UncertainDefiningAct(SimpleTestCase):
    def test_d104_finding_11_an_uncertain_lithotripsy_competes_for_the_stone_clearance(self):
        """Finding 11's texts, with no participant and with Astra and Fable read and proposing nothing: 43264 is held
        with competing_codes (it was READY), and 43265 keeps its own doubt question beside competing_codes - as the
        installed release, configured as in production, holds both with competing_codes."""
        for name in UNCERTAIN:
            inv, text, lines = uncertain_clearance(name)
            lithotripsy = events.Reading.of(inv).events['E3']
            self.assertEqual((lithotripsy['status']['value'], lithotripsy['time']['state']),
                             ('uncertain', 'verified'))
            for participants in PARTICIPANTS:
                with self.subTest(text=name, participants=len(participants)):
                    result = run(inv, text, [('43264', lines['P4']), ('43265', lines['P3'])],
                                 participants=participants)
                    extraction, held = proposal(result, '43264'), proposal(result, '43265')
                    self.assertEqual((extraction.status, asked(extraction), extraction.support.get('competes')),
                                     ('needs_clarification', ['competing_codes'], ['43265']))
                    self.assertEqual((held.status, asked(held), held.support.get('competes'), held.support['reason']),
                                     ('needs_clarification', ['performed_status', 'competing_codes'], ['43264'],
                                      events.DOUBT))
                    self.assertEqual([item['id'] for item in extraction.support['acts']], ['E4'])  # E* unchanged

    def test_d104_claims_read_an_uncertain_defining_act_and_still_not_a_denied_or_planned_one(self):
        """_claims(43265) is the extraction (E4) for every uncertain wording; nothing for a denied, planned or earlier
        lithotripsy (D74's unclaimed shapes, unchanged). DECISIONS D163 (round 5f): and the held 43265's own uncertain
        lithotripsy (E3), as a held code keeps the acts its evaluation read; no rival claims E3, so no outcome moves."""
        for name in UNCERTAIN:
            inv, text, lines = uncertain_clearance(name)
            with self.subTest(claimed=name):
                self.assertEqual(claims(inv, text, '43265', lines['P3']), ('E4', 'E3'))  # D163: E3 too
        unclaimed = {
            'denied': stone_clearance('No lithotripsy was performed for the 15 mm stone in the common bile duct.',
                                      status='not_performed', status_words='No lithotripsy was performed'),
            'planned': stone_clearance('Mechanical lithotripsy of the 15 mm stone in the common bile duct is planned.',
                                       status='planned', status_words='is planned'),
            'uncertain at an earlier encounter': stone_clearance(
                'In 2024 it was unclear whether the 15 mm stone in the common bile duct was fragmented with '
                'mechanical lithotripsy.', status='uncertain', status_words='it was unclear',
                time=a('earlier_encounter', 'In 2024', ['P3'])),
        }
        for name, (inv, text, lines) in unclaimed.items():
            with self.subTest(unclaimed=name):
                self.assertEqual(claims(inv, text, '43265', lines['P3']), ())

    def test_d104_controls_43264_alone_stays_ready_and_a_denied_lithotripsy_claims_nothing(self):
        """43264 proposed alone beside the uncertain lithotripsy stays READY (the installed release READYs it too: there
        is no rival); beside a denied lithotripsy, 43265 is held not documented and 43264 is READY, as before."""
        inv, text, lines = uncertain_clearance('unclear')
        for participants in PARTICIPANTS:
            p = proposal(run(inv, text, [('43264', lines['P4'])], participants=participants), '43264')
            self.assertEqual((p.status, asked(p)), ('ready', []))
        inv, text, lines = stone_clearance('No lithotripsy was performed for the 15 mm stone in the common bile duct.',
                                           status='not_performed', status_words='No lithotripsy was performed')
        result = run(inv, text, [('43264', lines['P4']), ('43265', lines['P3'])])
        self.assertEqual({code: (proposal(result, code).status, proposal(result, code).support.get('competes'))
                          for code in ('43264', '43265')},
                         {'43264': ('ready', None), '43265': ('needs_clarification', None)})


# --- D105: the round-4 refutation, finding 22 --------------------------------------------------------------------------

EXCHANGE = {'P1': 'Procedure: ERCP with biliary stent exchange.',
            'P2': 'The duodenoscope was advanced to the major papilla.',
            'P3': 'The existing biliary stent was removed with a snare.',
            'P4': 'Deep biliary cannulation was achieved with a sphincterotome.',
            'P5': 'A 10 Fr x 9 cm plastic biliary stent was placed into the common bile duct.'}
BILIARY_REMOVAL = tg('', 'bile_duct', 'biliary', ['P3'])
CBD_PLACEMENT = tg('', 'common_bile_duct', 'common bile duct', ['P5'])


def stent_exchange(lines=None, removal=None, placement=None, more=()):
    """Finding 22's document (cases/xch_x1_new.json): the duodenoscope (E1), the snare removal of the existing biliary
    stent (E2), the cannulation (E3) and the new plastic stent placed in the common bile duct (E4); ``removal`` and
    ``placement`` replace E2's and E4's changes."""
    lines = dict(EXCHANGE, **(lines or {}))
    removed = dict(status_words='was removed with a snare', technique=a('snare', 'snare', ['P3']),
                   target=BILIARY_REMOVAL)
    removed.update(removal or {})
    placed = dict(status_words='was placed', technique=a('stent', 'plastic biliary stent', ['P5']),
                  target=CBD_PLACEMENT)
    placed.update(placement or {})
    events_ = [duodenoscope('P2'),
               ercp_act('E2', 'P3', 'stent_removal', 'removed', **removed),
               ercp_act('E3', 'P4', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                        target=tg('', 'bile_duct', 'biliary', ['P4']),
                        technique=a('sphincterotome', 'sphincterotome', ['P4'])),
               ercp_act('E4', 'P5', 'stent', 'stent', **placed),
               *more]
    inv, text = inventory(lines, events=events_, reach=[reached('E1', 'ampulla', 'major papilla', 'P2')])
    return inv, text, lines


def exchange_held(test, p, question_events=('E2', 'E4')) -> None:
    """``p`` is held with D105's one exchange question, never READY and never "not documented"."""
    test.assertEqual((p.bucket, p.status, asked(p), p.support['reason']),
                     ('selected', 'needs_clarification', ['performed_status'], ercp.POSSIBLE_EXCHANGE))
    test.assertEqual(p.support.get('question_events'), list(question_events))
    question = p.clarifications[0].question
    test.assertIn('one stent exchange (43276)', question)
    test.assertTrue(question.startswith('Were the stent removal'), question)
    test.assertNotIn('records no stent exchange', p.support['detail'])
    test.assertEqual(check(p, 'service.status').status, 'warn')


class D105PossibleStentExchange(SimpleTestCase):
    def test_d105_finding_22_a_removal_and_a_placement_in_one_duct_are_never_both_ready(self):
        """Finding 22's document, with no participant and with Astra and Fable read and proposing nothing: 43275 and
        43274 (each alone too) are held with the exchange question, never READY (both were READY), and 43276 on the
        Procedure line is held with that question, never "not documented" (it was)."""
        inv, text, lines = stent_exchange()
        reading = events.Reading.of(inv)
        self.assertEqual([(removal['id'], placement['id']) for removal, placement in ercp.exchange_pairs(reading)],
                         [('E2', 'E4')])
        proposals = {'43275': lines['P3'], '43274': lines['P5'], '43276': lines['P1']}
        for chosen in (('43275', '43274'), ('43275', '43274', '43276'), ('43276',), ('43274',), ('43275',)):
            for participants in PARTICIPANTS:
                with self.subTest(codes=chosen, participants=len(participants)):
                    result = run(inv, text, [(code, proposals[code]) for code in chosen], participants=participants)
                    for code in chosen:
                        exchange_held(self, proposal(result, code))
                    self.assertNotEqual(result.completeness['state'], 'complete_pending_review')

    def test_d105_finding_22_the_second_document_with_its_impression(self):
        """Finding 22's second document (cases/ercp_exchange_two_events.json, my own construction): the removal and the
        placement in separate sentences and 'Impression: Biliary stent exchange.' - 43275, 43274 and 43276 held with the
        exchange question; 43260 keeps its base_included hold."""
        lines = {'P1': 'Impression: Biliary stent exchange.',
                 'P3': 'The indwelling biliary stent was grasped with a snare and removed.',
                 'P5': 'A new 10 Fr x 9 cm plastic biliary stent was placed across the stricture.'}
        inv, text, lines = stent_exchange(lines, removal=dict(status_words='was grasped with a snare and removed',
                                                              target=tg('', 'bile_duct', 'biliary', ['P3'])),
                                          placement=dict(target=tg('', 'bile_duct', 'biliary', ['P5'])))
        result = run(inv, text, [('43275', lines['P3']), ('43274', lines['P5']), ('43276', lines['P1']),
                                 ('43260', lines['P2'])])
        for code in ('43275', '43274', '43276'):
            exchange_held(self, proposal(result, code))
        base = proposal(result, '43260')
        self.assertEqual((base.status, asked(base)), ('needs_clarification', ['base_included']))

    def test_d105_a_stent_exchange_event_beside_the_removal_and_the_placement_holds_all_three(self):
        """The refuter's three-event shape (stent_exchange, stent_removal and stent): all three codes were READY. Each is
        held with the exchange question: 43276 'when proposed, is held with that question'."""
        summary = ercp_act('E5', 'P1', 'stent_exchange', 'biliary stent exchange', 'ERCP with biliary stent exchange',
                           target=tg('', 'bile_duct', 'biliary', ['P1']))
        inv, text, lines = stent_exchange(more=[summary])
        result = run(inv, text, [('43275', lines['P3']), ('43274', lines['P5']), ('43276', lines['P1'])])
        for code in ('43275', '43274', '43276'):
            exchange_held(self, proposal(result, code))

    def test_d105_controls_ducts_set_apart_stay_separate_acts(self):
        """A removal and a placement verified in different ducts - the bile duct and the pancreatic duct, either way
        round - stay separate acts: 43275 and 43274 READY, 43276 held not documented, as before."""
        pancreatic = {'P5': 'A 5 Fr x 3 cm pancreatic stent was placed into the pancreatic duct.'}
        inv, text, lines = stent_exchange(pancreatic,
                                          placement=dict(target=tg('', 'pancreatic_duct', 'pancreatic duct', ['P5'])))
        result = run(inv, text, [('43275', lines['P3']), ('43274', lines['P5']), ('43276', lines['P1'])])
        self.assertEqual(ercp.exchange_pairs(events.Reading.of(inv)), [])
        self.assertEqual({code: (proposal(result, code).status, proposal(result, code).support['reason'])
                          for code in ('43275', '43274', '43276')},
                         {'43275': ('ready', events.SUPPORTED), '43274': ('ready', events.SUPPORTED),
                          '43276': ('needs_clarification', events.NOT_DOCUMENTED)})
        reverse = {'P3': 'The existing pancreatic duct stent was removed with a snare.'}
        inv, text, lines = stent_exchange(reverse,
                                          removal=dict(target=tg('', 'pancreatic_duct', 'pancreatic duct', ['P3'])))
        result = run(inv, text, [('43275', lines['P3']), ('43274', lines['P5'])])
        self.assertEqual([proposal(result, code).status for code in ('43275', '43274')], ['ready', 'ready'])

    def test_d105_a_duct_not_verified_or_the_ampulla_never_sets_them_apart(self):
        """D45's reading of the ducts: a removal whose duct is not stated, or a placement whose stated duct does not
        verify, or the ampulla (it opens on both), leaves the pair a possible exchange."""
        shapes = {
            'removal duct not stated': dict(removal=dict(target=tg())),
            'placement at the ampulla': dict(lines={'P5': 'A 10 Fr x 9 cm plastic stent was placed across the major '
                                                          'papilla.'},
                                             placement=dict(target=tg('', 'ampulla', 'major papilla', ['P5']))),
        }
        for name, options in shapes.items():
            inv, text, lines = stent_exchange(**options)
            with self.subTest(shape=name):
                self.assertEqual(len(ercp.exchange_pairs(events.Reading.of(inv))), 1)
                result = run(inv, text, [('43275', lines['P3']), ('43274', lines['P5'])])
                for code in ('43275', '43274'):
                    exchange_held(self, proposal(result, code))

    def test_d105_a_doubted_removal_is_a_side_and_a_held_code_keeps_its_own_question(self):
        """The removal's time worded and unanchored ('During the procedure', D54): 43275 keeps its own event_time
        question (D89: never displaced), 43274 and 43276 are held with the exchange question - the doubted removal may be
        today's (D62, D87). Controls: a removal verified at an earlier encounter, or denied, is no side - 43274 READY."""
        during = {'P3': 'During the procedure the existing biliary stent was removed with a snare.'}
        inv, text, lines = stent_exchange(during, removal=dict(time=a('current_encounter', 'During the procedure',
                                                                      ['P3'])))
        self.assertEqual(events.Reading.of(inv).events['E2']['time']['state'], 'unverified')
        result = run(inv, text, [('43275', lines['P3']), ('43274', lines['P5']), ('43276', lines['P1'])])
        removal = proposal(result, '43275')
        self.assertEqual((removal.status, asked(removal), removal.support['reason']),
                         ('needs_clarification', ['event_time'], events.UNVERIFIED))
        for code in ('43274', '43276'):
            exchange_held(self, proposal(result, code))
        controls = {
            'earlier': ({'P3': 'At the prior ERCP in 2025 the previous biliary stent was removed with a snare.'},
                        dict(time=a('earlier_encounter', 'At the prior ERCP in 2025', ['P3']))),
            'denied': ({'P3': 'The existing biliary stent was not removed.'},
                       dict(status='not_performed', status_words='was not removed')),
        }
        for name, (changed, removal_changes) in controls.items():
            inv, text, lines = stent_exchange(changed, removal=removal_changes)
            with self.subTest(control=name):
                self.assertEqual(ercp.exchange_pairs(events.Reading.of(inv)), [])
                p = proposal(run(inv, text, [('43274', lines['P5'])]), '43274')
                self.assertEqual((p.status, asked(p)), ('ready', []))


# --- D106: the round-4 refutation, finding 25 --------------------------------------------------------------------------

SWEEP = {'P1': 'The duodenoscope was advanced to the major papilla.',
         'P2': 'Deep biliary cannulation was achieved with a sphincterotome.',
         'P3': 'Cholangiogram showed a mildly dilated bile duct without filling defects.',
         'P4': 'A biliary sphincterotomy was performed.',
         'P5': 'The bile duct was swept several times with an extraction balloon; no stones or sludge were retrieved.'}


def balloon_sweep(p5: str = SWEEP['P5'], status_words: str = 'was swept several times',
                  kind_words: str = 'swept several times with an extraction balloon', more=(), lines=None):
    """Finding 25's ERCP (cases/ercp_sweep_performed.json): the duodenoscope (E1), the cannulation (E2), the
    sphincterotomy (E3) and the balloon sweep read as a performed stone_extraction (E4)."""
    lines = dict(SWEEP, P5=p5, **(lines or {}))
    events_ = [duodenoscope('P1'),
               ercp_act('E2', 'P2', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                        target=tg('', 'bile_duct', 'biliary', ['P2'])),
               ercp_act('E3', 'P4', 'sphincterotomy', 'biliary sphincterotomy', 'was performed',
                        target=tg('', 'bile_duct', 'biliary', ['P4'])),
               ercp_act('E4', 'P5', 'stone_extraction', kind_words, status_words,
                        target=tg('', 'bile_duct', 'The bile duct' if 'The bile duct' in p5 else 'bile duct', ['P5']),
                        technique=a('extraction_balloon', 'extraction balloon', ['P5'])),
               *more]
    inv, text = inventory(lines, events=events_, reach=[reached('E1', 'ampulla', 'major papilla', 'P1')])
    return inv, text, lines


class D106NothingRetrieved(SimpleTestCase):
    def test_d106_finding_25_a_sweep_that_retrieved_nothing_holds_43264(self):
        """Finding 25's reading - the sweep a performed stone_extraction - with Corti citing the whole sentence or only
        its first clause, with no participant and with Astra and Fable read and proposing nothing: 43264 is held with the
        performed_status question naming the statement (it was READY; the installed release excludes it), and the
        sphincterotomy's 43262 stays READY."""
        inv, text, lines = balloon_sweep()
        record = events.Reading.of(inv).events['E4']
        self.assertEqual((record['status']['value'], record['status']['state']), ('performed', 'verified'))
        cites = {'the whole sentence': lines['P5'],
                 'the first clause': 'The bile duct was swept several times with an extraction balloon'}
        for name, cited in cites.items():
            for participants in PARTICIPANTS:
                with self.subTest(cited=name, participants=len(participants)):
                    result = run(inv, text, [('43262', lines['P4']), ('43264', cited)], participants=participants)
                    held, sphincterotomy = proposal(result, '43264'), proposal(result, '43262')
                    self.assertEqual((held.bucket, held.status, asked(held), held.support['reason'],
                                      held.support['acts'], held.support.get('question_events')),
                                     ('selected', 'needs_clarification', ['performed_status'], ercp.NOTHING_RETRIEVED,
                                      [], ['E4']))
                    self.assertIn('no stones or sludge were retrieved', held.clarifications[0].question)
                    self.assertIn('nothing was retrieved', held.clarifications[0].reason)
                    self.assertEqual((sphincterotomy.status, asked(sphincterotomy)), ('ready', []))

    def test_d106_the_negation_read_in_the_acts_own_sentence(self):
        """states_nothing_retrieved over one sentence: a negator over stones, calculi, debris or sludge (at most three
        words between, no clause break) and a retrieval or extraction word; an exceptive or partial negation is not
        'nothing retrieved' (C-7)."""
        said = ('The bile duct was swept several times with an extraction balloon; no stones or sludge were retrieved.',
                'Balloon sweeps retrieved no stones.', 'No stone fragments or debris were extracted.',
                'Neither calculi nor sludge could be removed with the basket.',
                'The duct was swept without retrieval of any stones.')
        not_said = ('Two small stones were retrieved with an extraction balloon.',
                    'Two stones were extracted; a final sweep retrieved no further stones.',
                    'Not all stones could be extracted.', 'No residual stones were retrieved after the extraction.',
                    'No stones or sludge were seen.')
        for sentence in said:
            with self.subTest(said=sentence):
                self.assertTrue(ercp.states_nothing_retrieved(sentence))
        for sentence in not_said:
            with self.subTest(not_said=sentence):
                self.assertFalse(ercp.states_nothing_retrieved(sentence))
        # the recorded cost of reading the act's whole SENTENCE (D106 as specified): a negation over stones in one clause
        # and a retrieval in another are read together. DECISIONS D127 (the review's problem 3): read ALONE, every clause
        # the act's, the sentence states a yield ("sludge was retrieved"), so its "no stones were seen" is a clearance -
        # False here; in the sweep's own reading the yield's clause holds none of the sweep's words, so the sweep is
        # still held, never READY and never excluded (fail-closed; tests.test_interpretation_r5_ercp pins it)
        self.assertFalse(ercp.states_nothing_retrieved(
            'The bile duct was swept with an extraction balloon; no stones were seen; sludge was retrieved.'))

    def test_d106_controls_a_retrieval_and_another_supporting_extraction_keep_43264_ready(self):
        """Controls: 'two small stones were retrieved' and an exceptive 'no further stones' keep 43264 READY; beside a
        basket extraction that did retrieve stones, 43264 stays READY on that act alone - the sweep that retrieved
        nothing leaves E*, and the decision still read it."""
        retrieved = 'The bile duct was swept several times with an extraction balloon; two small stones were retrieved.'
        further = 'Two stones were extracted with an extraction balloon; a final sweep retrieved no further stones.'
        for p5, status_words, kind_words in ((retrieved, 'was swept several times',
                                              'swept several times with an extraction balloon'),
                                             (further, 'were extracted', 'extracted')):
            inv, text, lines = balloon_sweep(p5, status_words, kind_words)
            with self.subTest(p5=p5):
                p = proposal(run(inv, text, [('43264', lines['P5'])]), '43264')
                self.assertEqual((p.status, asked(p), [item['id'] for item in p.support['acts']]),
                                 ('ready', [], ['E4']))
        basket = ercp_act('E5', 'P6', 'stone_extraction', 'extracted', 'were extracted',
                          target=tg('', 'common_bile_duct', 'common bile duct', ['P6']),
                          technique=a('basket', 'basket', ['P6']))
        inv, text, lines = balloon_sweep(more=[basket],
                                         lines={'P6': 'Two stones were extracted from the common bile duct with a '
                                                      'basket.'})
        result = run(inv, text, [('43264', (lines['P5'], lines['P6']))])
        p = proposal(result, '43264')
        self.assertEqual((p.status, [item['id'] for item in p.support['acts']]), ('ready', ['E5']))
        self.assertNotIn('extraction balloon', p.support['detail'])
        evaluation = events.evaluate('43264', (), events.Reading.of(inv))
        self.assertEqual((evaluation.supporting, evaluation.read), (('E5',), ('E4', 'E5')))
        self.assertFalse([item for item in result.completeness['unresolved_items'] if 'E4' in item['events']])


# --- D107: the round-4 refutation, finding 26 --------------------------------------------------------------------------

FAILED = {'P1': 'The duodenoscope was advanced to the second portion of the duodenum.',
          'P2': 'The major papilla was located within a large periampullary diverticulum.',
          'P3': 'Multiple attempts at biliary cannulation were unsuccessful.',
          'P4': 'The procedure was terminated; no sphincterotomy and no stent placement were performed.'}
# DECISIONS D127 (the review's problem 4): the warn quotes the sentence that states the failure, as the installed release
# quotes it, no longer the bare failure-marker words ('were unsuccessful')
FAILURE = FAILED['P3']


def failed_cannulation(p4: str = FAILED['P4'], examination=None, cannulation=None, completion=None):
    """Finding 26's ERCP (cases/ercp_failed_exam_performed.json): the duodenoscope advanced (E1, performed), the biliary
    cannulation begun and not completed (E2), the sphincterotomy (E3) and the stent placement (E4) denied, all of kind."""
    lines = dict(FAILED, P4=p4)
    terminated = p4.startswith('The procedure was terminated')
    denial = 'no sphincterotomy and no stent placement were performed' if terminated else \
        'No sphincterotomy and no stent placement were performed'
    events_ = [examination or duodenoscope('P1'),
               cannulation or ercp_act('E2', 'P3', 'cannulation', 'biliary cannulation', 'were unsuccessful',
                                       status='attempted_not_completed', target=tg('', 'bile_duct', 'biliary', ['P3'])),
               ercp_act('E3', 'P4', 'sphincterotomy', 'sphincterotomy', denial, status='not_performed',
                        scope=sc('all_of_kind', 'no' if terminated else 'No', ['P4'])),
               ercp_act('E4', 'P4', 'stent', 'stent placement', 'no stent placement were performed',
                        status='not_performed', scope=sc('all_of_kind', 'no stent', ['P4']))]
    reach = reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')
    if completion is not None:
        reach['completion'] = completion
    inv, text = inventory(lines, events=events_, reach=[reach])
    codes = [('43260', lines['P3']), ('43262', 'no sphincterotomy' if terminated else 'No sphincterotomy'),
             ('43274', 'no stent placement were performed'), ('43261', lines['P2'])]
    return inv, text, codes


class D107AccessNotCompleted(SimpleTestCase):
    def test_d107_finding_26_a_failed_cannulation_gives_every_code_of_the_ercp_both_signals(self):
        """Finding 26's text, and the stronger variant without 'The procedure was terminated;', with no participant and
        with Astra and Fable read and proposing nothing: 43260 keeps READY and gains the service.incomplete warn (in the
        sentence of the cannulation's failure-marker words, D127) and the installed release's 52/53 consideration; a held
        code of the session (43261, no biopsy documented) carries both; the excluded 43262 and 43274 carry neither."""
        for p4 in (FAILED['P4'], 'No sphincterotomy and no stent placement were performed.'):
            inv, text, codes = failed_cannulation(p4)
            record = events.Reading.of(inv).events['E2']
            self.assertEqual((record['status']['value'], record['status']['state']),
                             ('attempted_not_completed', 'verified'))
            for participants in PARTICIPANTS:
                with self.subTest(p4=p4, participants=len(participants)):
                    result = run(inv, text, codes[:3], participants=participants)
                    base = proposal(result, '43260')
                    self.assertEqual((base.status, asked(base), carried(base)),
                                     ('ready', [], signals('43260', FAILURE)))
                    self.assertEqual(check(base, INCOMPLETE).status, 'warn')
                    for code in ('43262', '43274'):
                        p = proposal(result, code)
                        self.assertEqual((p.status, carried(p)), ('excluded', ((), [])))
                    # a held code of the session carries both too (whatever its own state, D61), and so does the
                    # base code its presence holds
                    result = run(inv, text, codes, participants=participants)
                    for code in ('43261', '43260'):
                        p = proposal(result, code)
                        self.assertEqual((p.status, carried(p)),
                                         ('needs_clarification', signals(code, FAILURE)), code)

    def test_d107_the_examination_stated_terminated_keeps_its_own_words_first(self):
        """The examination's own statement is read first (D61's completion, then D71's status): stated begun and not
        completed ('The procedure was terminated') or its reach's completion 'incomplete', the warn quotes those words,
        once, beside the failed cannulation."""
        attempted = duodenoscope('P1')
        attempted['status'] = a('attempted_not_completed', 'The procedure was terminated', ['P4'])
        for name, options in (('status', dict(examination=attempted)),
                              ('completion', dict(completion=a('incomplete', 'The procedure was terminated', ['P4'])))):
            inv, text, codes = failed_cannulation(**options)
            with self.subTest(stated=name):
                base = proposal(run(inv, text, codes[:3]), '43260')
                self.assertEqual((base.status, carried(base)), ('ready', signals('43260', 'The procedure was terminated')))
                # a code whose signals come from the session alone (43261, held not documented): the examination's
                # words, not the cannulation's
                held = proposal(run(inv, text, codes), '43261')
                self.assertEqual(carried(held), signals('43261', 'The procedure was terminated'))

    def test_d107_controls_a_cannulation_achieved_or_of_another_occasion_gives_nothing(self):
        """Controls: a cannulation achieved, and a failed cannulation at an earlier encounter, give no signal; the
        rule reads the ERCP family only (access_not_completed is None for any other)."""
        achieved = ercp_act('E2', 'P3', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                            target=tg('', 'bile_duct', 'biliary', ['P3']))
        earlier = ercp_act('E2', 'P3', 'cannulation', 'biliary cannulation', 'were unsuccessful',
                           status='attempted_not_completed', target=tg('', 'bile_duct', 'biliary', ['P3']),
                           time=a('earlier_encounter', 'At the prior ERCP in 2025', ['P3']))
        shapes = {'achieved': ({'P3': 'Deep biliary cannulation was achieved with a sphincterotome.'}, achieved),
                  'earlier': ({'P3': 'At the prior ERCP in 2025 multiple attempts at biliary cannulation were '
                                     'unsuccessful.'}, earlier)}
        for name, (changed, cannulation) in shapes.items():
            lines = dict(FAILED, **changed)
            inv, text = inventory(lines, events=[duodenoscope('P1'), cannulation], reach=[
                reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')])
            with self.subTest(control=name):
                reading = events.Reading.of(inv)
                self.assertIsNone(ercp.access_not_completed(reading, 'gi.ercp'))
                base = proposal(run(inv, text, [('43260', lines['P1'])]), '43260')
                # the earlier cannulation leaves today's cannulation outcome undocumented: asked, as before
                self.assertEqual((asked(base), carried(base)),
                                 (['cannulation'] if name == 'earlier' else [], ((), [])))
        inv, text, _codes = failed_cannulation()
        reading = events.Reading.of(inv)
        self.assertEqual(ercp.access_not_completed(reading, 'gi.ercp'), FAILURE)
        self.assertIsNone(ercp.access_not_completed(reading, 'gi.egd'))
        self.assertIsNone(assess._incomplete_session('gi.egd', reading, coverage.sessions(reading)))

    def test_d107_the_defining_access_act_a_pancreatic_failure_beside_the_biliary_access_achieved(self):
        """The session's DEFINING access act: the pancreatic duct's cannulation begun and not completed beside the bile
        duct's achieved gives nothing - the installed release's pancreatic avoidance ("a deliberate choice, not a failed
        ERCP"), measured on c2e53f8e: READY with neither signal. A biliary attempt that failed before the biliary access
        was achieved still gives both, as the installed release gives them."""
        lines = {'P1': 'The duodenoscope was advanced to the major papilla.',
                 'P2': 'Deep biliary cannulation was achieved with a sphincterotome.'}
        achieved = ercp_act('E2', 'P2', 'cannulation', 'Deep biliary cannulation', 'was achieved',
                            target=tg('', 'bile_duct', 'biliary', ['P2']))
        # DECISIONS D127: the biliary attempt beside the access achieved is the cannulation stated both achieved and not
        # (the parity audit's note 1): 43260 is held with the cannulation question, as the installed release holds it,
        # and keeps both signals, quoting the failure's sentence (the review's problem 4)
        shapes = {'pancreatic': ('Pancreatic duct cannulation was unsuccessful.',
                                 tg('', 'pancreatic_duct', 'Pancreatic duct', ['P3']), 'was unsuccessful', None),
                  'biliary, before': ('Initial attempts at biliary cannulation were unsuccessful.',
                                      tg('', 'bile_duct', 'biliary', ['P3']), 'were unsuccessful',
                                      'Initial attempts at biliary cannulation were unsuccessful.')}
        for name, (p3, target, words, expected) in shapes.items():
            failed = ercp_act('E3', 'P3', 'cannulation', 'cannulation', words, status='attempted_not_completed',
                              target=target)
            inv, text = inventory(dict(lines, P3=p3), events=[duodenoscope('P1'), achieved, failed],
                                  reach=[reached('E1', 'ampulla', 'major papilla', 'P1')])
            with self.subTest(failed=name):
                reading = events.Reading.of(inv)
                self.assertEqual(reading.events['E3']['target']['state'], 'verified')
                self.assertEqual(ercp.access_not_completed(reading, 'gi.ercp'), expected)
                base = proposal(run(inv, text, [('43260', lines['P1'])]), '43260')
                self.assertEqual((base.status, asked(base), carried(base)),
                                 ('needs_clarification', ['cannulation'], signals('43260', expected)) if expected else
                                 ('ready', [], ((), [])))
