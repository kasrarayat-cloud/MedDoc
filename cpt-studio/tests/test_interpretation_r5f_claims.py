"""Round 5f of the Gemini migration, D163 (narrowing only): a hold never releases a rival. SYNTHETIC and constructed:
nothing is sent.

A held code's evaluation supports nothing, so assess._claims claimed no act for it; combination.competition then found
no pair, and a RIVAL that competed with it for the same act lost its competing_codes hold and went READY - a release
through the next reader (round5e colon4's STOP and its disagreements 1-3; review:ercp5 problems 0-1). D163: a code HELD
by any hold keeps, as its claims, the acts its evaluation names or read that it could account for (assess._claims'
docstring), added to what D55, D74 and D118 claim. c2e53f8e with its participants configured (Astra and Fable read and
proposing nothing, tests.test_interpretation_r3_claims.READ_NOTHING) holds 43265 on every rival input pinned here - with
competing_codes, or with its own conflict or readings_disagree question - and holds both codes of the fb07 shape; with
none configured it READYs both on most of them. Every assessed pin runs in both settings: the new path gives one
outcome in both.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

from django.test import SimpleTestCase

from studio.interpretation import assess, combination, ercp, events
from tests.test_interpretation_events import POLYP, asked, colonoscopy, exam, inventory, proposal, run
from tests.test_interpretation_identity import a, act, sc, tg
from tests.test_interpretation_r3_claims import READ_NOTHING, STONE, claims
from tests.test_interpretation_r4_ercp import ercp_act, stent_exchange
from tests.test_interpretation_r5_ercp import sweep
from tests.test_interpretation_r5_egd import C_ANASTOMOSIS, C_HISTORY, C_PYLORUS, C_TWO_BALLOONS, assessed, held, ready
from tests.test_interpretation_r5d_colon import ercp_report

SETTINGS = (('no participant', ()), ('Astra and Fable read and proposing nothing', READ_NOTHING))
# tests.test_interpretation_coverage's bleeding control beside the polypectomy (AdjunctBesideARemoval), copied
HEMOCLIPS = 'Immediate oozing from the polypectomy site was controlled with two hemoclips for hemostasis.'


def hemoclips(line: str = HEMOCLIPS, **changes) -> dict:
    """A bleeding control (E3): two clips whose hemostasis purpose is verified, in its own line (P3)."""
    options = {'technique': a('clip', 'hemoclips', ['P3']), 'purpose': a('hemostasis', 'for hemostasis', ['P3']),
               **changes}
    return act('E3', 'P3', 'clip', 'hemoclips', status_words='was controlled', **options)


def rivals_held(test, result, held_reason: str, rival_facts=('competing_codes',), rival_reason=events.SUPPORTED):
    """43264 held by its own hold with competing_codes beside it, naming 43265; 43265 held with competing_codes (after
    its own question, if any), naming 43264 - never READY."""
    extraction, lithotripsy = proposal(result, '43264'), proposal(result, '43265')
    test.assertEqual((extraction.status, asked(extraction), extraction.support['reason'],
                      extraction.support.get('competes')),
                     ('needs_clarification', ['performed_status', 'competing_codes'], held_reason, ['43265']))
    test.assertEqual((lithotripsy.status, asked(lithotripsy), lithotripsy.support['reason'],
                      lithotripsy.support.get('competes')),
                     ('needs_clarification', list(rival_facts), rival_reason, ['43264']))


# --- the another-role hold (D124, D146; colon4's STOP) ----------------------------------------------------------------

NURSE = 'Nurse: The stone fragments were extracted from the bile duct with an extraction balloon.'
ONE_LINE = 'Documented by Jo Rowe, RN: The stone fragments were extracted from the bile duct with an extraction balloon.'
WRAPPED = 'Documented by Jo Rowe, RN: The stone fragments from the bile duct\nwere extracted with an extraction balloon.'


def clearance(p4: str) -> tuple:
    """Finding 5's stone clearance (tests.test_interpretation_r3_claims.STONE) with the extraction line ``p4`` (E4, 43264)
    and the physician's lithotripsy (E3, 43265): (inventory, text, codes), as round5e/colon4's probes built it."""
    lines = dict(STONE, P4=p4)
    inv, text = inventory(lines, events=[
        exam('E1', 'P1', words='duodenoscope', procedure=a('ercp')),
        act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
            target=tg('', 'bile_duct', 'biliary', ['P2']), technique=a('sphincterotome', 'sphincterotome', ['P2'])),
        act('E3', 'P3', 'lithotripsy', 'lithotripsy', status_words='was fragmented', procedure=a('ercp'),
            target=tg('', 'common_bile_duct', 'common bile duct', ['P3']),
            technique=a('lithotripter', 'lithotripsy', ['P3'])),
        act('E4', 'P4', 'stone_extraction', 'extracted', status_words='were extracted', procedure=a('ercp'),
            target=tg('', 'bile_duct', 'bile duct', ['P4']),
            technique=a('extraction_balloon', 'extraction balloon', ['P4']))])
    return inv, text, [('43264', p4), ('43265', STONE['P3'])]


class D163AnotherRolesHoldKeepsItsActs(SimpleTestCase):
    def test_d163_an_extraction_told_in_a_nursing_line_holds_the_lithotripsys_43265(self):
        """colon4's disagreement 2: 'Nurse: The stone fragments were extracted ...' (D124's label; 43265 READY on
        e5628be56 and f9013e12e) and D146's one-line signature line (a round-5d release: e5628be56 held both). 43264 is
        held another_role and asks competing_codes beside it; 43265 is held competing_codes, as c2e53f8e with its
        participants holds both."""
        for name, line in (('Nurse: label', NURSE), ('one-line signature', ONE_LINE)):
            inv, text, codes = clearance(line)
            for setting, participants in SETTINGS:
                with self.subTest(line=name, setting=setting):
                    rivals_held(self, run(inv, text, codes, participants=participants), events.ANOTHER_ROLE)

    def test_d163_d146s_nursing_headings_hold_the_lithotripsys_43265(self):
        """D146 problem 4's ERCP report under each nursing heading, and the colon3 review's "Recovery nurse's note"
        (D146's own new heading: a round-5d release). Each was READY on f9013e12e (the four on e5628be56 too); 43265 is
        held competing_codes now. D146's pin of the release (test_d146_its_rival_for_the_same_act_is_ready) is changed
        with this module."""
        for heading in ('Nursing note', 'Nursing note - recovery', 'Nursing note, recovery room', 'Procedure checklist',
                        "Recovery nurse's note"):
            inv, text, codes = ercp_report(heading)
            for setting, participants in SETTINGS:
                with self.subTest(heading=heading, setting=setting):
                    rivals_held(self, run(inv, text, codes, participants=participants), events.ANOTHER_ROLE)

    def test_d163_a_held_another_role_code_claims_its_own_act(self):
        """The mechanism, whatever reader decides the hold: 43264 held another_role claims its extraction (E4), which
        43265 claims through D74, so the two compete. Read on the one-line signature line (held on this tree) and on
        colon4's hard-wrapped signature line with the hold another_role_hold gives it once D152's rules read the label
        (round5f colon5): the Evaluation is made here, since this tree's reader does not hold it."""
        inv, text, _ = clearance(ONE_LINE)
        evaluation = events.evaluate('43264', (), events.Reading.of(inv))
        self.assertEqual((evaluation.reason, evaluation.supporting), (events.ANOTHER_ROLE, ()))
        self.assertEqual(claims(inv, text, '43264', ONE_LINE), ('E4',))
        inv, text, _ = clearance(WRAPPED)
        reading = events.Reading.of(inv)
        held_one = dataclasses.replace(  # whatever this tree's reader decides, the hold D152's rules give it
            events.evaluate('43264', (), reading), state='uncertain', reason=events.ANOTHER_ROLE, supporting=(),
            question=events.Question('performed_status', 'q', 'r', ('E4',), ()))
        mine = assess._claims(SimpleNamespace(evaluation=held_one), reading)
        theirs = assess._claims(SimpleNamespace(evaluation=events.evaluate('43265', (), reading)), reading)
        self.assertEqual((mine, theirs), (('E4',), ('E3', 'E4')))
        self.assertEqual(combination.competition([('a', '43264', 'primary', mine), ('b', '43265', 'primary', theirs)]),
                         {'a': ('43265',), 'b': ('43264',)})


# --- D106's retrieval hold (D155; review:ercp5 problems 0-1) ----------------------------------------------------------

LITHO_P3 = 'A 15 mm stone in the common bile duct was fragmented with mechanical lithotripsy.'  # finding 5's own P3
SWEPT_ONCE = 'The bile duct was swept with an extraction balloon.'
UNCLEAR = ('It is unclear from the record whether the 15 mm stone in the common bile duct was fragmented with '
           'mechanical lithotripsy.')
DENIALS = {  # review:ercp5's problem-0 wordings (its cases_refute.py F group), each after the sweep's own sentence
    'R1': 'No stones were retrieved, and a plastic biliary stent was placed.',
    'semicolon': 'No stones were retrieved; a plastic biliary stent was placed.',
    'nothing': 'Nothing was retrieved, and a plastic biliary stent was placed.',
    'seen': 'No stones were seen, and a plastic biliary stent was placed.',
    'after the stent': 'A plastic biliary stent was placed; no stones were retrieved.',
    'remained': 'No stones remained, and a plastic biliary stent was placed.',
    'final cholangiogram': 'No stones were seen on the final cholangiogram, and a plastic biliary stent was placed.',
}


def lithotripsy(eid: str = 'E8', status: str = 'performed', status_words: str = 'was fragmented', **changes) -> dict:
    return ercp_act(eid, 'P3', 'lithotripsy', 'lithotripsy', status_words, status=status,
                    target=tg('', 'common_bile_duct', 'common bile duct', ['P3']),
                    technique=a('lithotripter', 'lithotripsy', ['P3']), **changes)


def sweep_beside_lithotripsy(second: str, *, p3: str = LITHO_P3, litho=None, more=()) -> tuple:
    """Finding 25's sweep document (tests.test_interpretation_r5_ercp.sweep) with P5 the one sweep sentence and
    ``second``, the stent filed (E5), and finding 5's lithotripsy at P3 (E8): (inventory, text, document lines)."""
    stent = ercp_act('E5', 'P5', 'stent', 'plastic biliary stent', 'was placed')
    return sweep(f'{SWEPT_ONCE} {second}', more_lines={'P3': p3}, more=[stent, litho or lithotripsy(), *more],
                 kind_words='swept with an extraction balloon', status_words='was swept')


class D163RetrievalHoldKeepsItsActs(SimpleTestCase):
    def test_d163_a_sweep_that_retrieved_nothing_holds_the_lithotripsys_43265(self):
        """review:ercp5 problem 0: the sweep D106 holds (nothing retrieved) beside the performed lithotripsy, 43265
        cited: 43265 was READY on f9013e12e with the competing question gone from both codes (e5628be56 held both
        competing_codes). Now 43264 asks its own question and competing_codes, and 43265 competing_codes, whether
        Corti cites the sweep's sentence or the whole passage."""
        for name, second in DENIALS.items():
            inv, text, doc = sweep_beside_lithotripsy(second)
            for cited in (SWEPT_ONCE, doc['P5']):
                for setting, participants in SETTINGS:
                    with self.subTest(denial=name, cited='sweep' if cited == SWEPT_ONCE else 'passage',
                                      setting=setting):
                        result = run(inv, text, [('43262', doc['P4']), ('43264', cited), ('43265', LITHO_P3)],
                                     participants=participants)
                        rivals_held(self, result, ercp.NOTHING_RETRIEVED)

    def test_d163_finding_11s_uncertain_lithotripsy_keeps_its_competing_question(self):
        """review:ercp5 problem 1: finding 11's uncertain lithotripsy (D104) beside R1's sweep. 43265 was held on every
        tree, but f9013e12e dropped its competing_codes question (e5628be56: [performed_status, competing_codes]);
        it is asked again."""
        doubted = lithotripsy(status='uncertain', status_words='It is unclear',
                              scope=sc('single_target', 'the 15 mm stone in the common bile duct', ['P3']))
        inv, text, doc = sweep_beside_lithotripsy(DENIALS['R1'], p3=UNCLEAR, litho=doubted)
        for cited in (SWEPT_ONCE, doc['P5']):
            for setting, participants in SETTINGS:
                with self.subTest(cited='sweep' if cited == SWEPT_ONCE else 'passage', setting=setting):
                    result = run(inv, text, [('43262', doc['P4']), ('43264', cited), ('43265', UNCLEAR)],
                                 participants=participants)
                    rivals_held(self, result, ercp.NOTHING_RETRIEVED,
                                rival_facts=('performed_status', 'competing_codes'), rival_reason=events.DOUBT)

    def test_d163_d140s_hold_beside_a_lithotripsy_holds_43265_too(self):
        """The same release before round 5d (D140's hold; review:ercp5's L group): the pancreatic sweep with its denial
        event, and the basket with a planned repeat ERCP, beside the lithotripsy - 43265 READY on e5628be56 and on
        f9013e12e; c2e53f8e with its participants holds it competing_codes (the sweep cited). Held now."""
        both = ('The bile duct was swept with an extraction balloon. The pancreatic duct was then swept with a balloon; '
                'no stones were retrieved.')
        pancreatic = ercp_act('E5', 'P5', 'stone_extraction', 'swept with a balloon', 'was then swept',
                              target=tg('', 'pancreatic_duct', 'The pancreatic duct', ['P5']),
                              technique=a('balloon', 'balloon', ['P5']))
        denial = ercp_act('E6', 'P5', 'other', 'no stones were retrieved', 'no stones were retrieved',
                          status='not_performed', scope=sc('single_target', 'no', ['P5']))
        basket_plan = ('The bile duct was swept with an extraction balloon. Two stones were extracted with a basket; no '
                       'stones were seen on the final cholangiogram and a repeat ERCP is planned.')
        basket = ercp_act('E5', 'P5', 'stone_extraction', 'extracted', 'were extracted',
                          technique=a('basket', 'basket', ['P5']))
        plan = ercp_act('E6', 'P5', 'examination', 'a repeat ERCP', 'is planned', status='planned',
                        time=a('future', 'is planned', ['P5']))
        for name, p5, more in (('D140 control', both, [pancreatic, denial]), ('basket and plan', basket_plan,
                                                                             [basket, plan])):
            inv, text, doc = sweep(p5, more_lines={'P3': LITHO_P3}, more=[*more, lithotripsy()],
                                   kind_words='swept with an extraction balloon', status_words='was swept')
            for setting, participants in SETTINGS:
                with self.subTest(document=name, setting=setting):
                    result = run(inv, text, [('43262', doc['P4']), ('43264', SWEPT_ONCE), ('43265', LITHO_P3)],
                                 participants=participants)
                    rivals_held(self, result, ercp.NOTHING_RETRIEVED)


# --- the general form: every held code, and only the acts it could account for -----------------------------------------

UNBOUND = 'The stone fragments were extracted from the bile duct with an extraction balloon.'
AGAIN = 'During the procedure, the bile duct was swept again with the extraction balloon.'


def two_extractions(cite: str = 'P4') -> tuple:
    """Finding 5's stone clearance with the extraction E4 whose status words do not bind ('were removed' is not in its
    passage) and a second sweep E5 whose time is worded and unanchored; 43264 cites ``cite``'s line, 43265 the
    lithotripsy: (inventory, text, codes). Constructed."""
    lines = dict(STONE, P4=UNBOUND, P5=AGAIN)
    inv, text = inventory(lines, events=[
        exam('E1', 'P1', words='duodenoscope', procedure=a('ercp')),
        act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
            target=tg('', 'bile_duct', 'biliary', ['P2']), technique=a('sphincterotome', 'sphincterotome', ['P2'])),
        act('E3', 'P3', 'lithotripsy', 'lithotripsy', status_words='was fragmented', procedure=a('ercp'),
            target=tg('', 'common_bile_duct', 'common bile duct', ['P3']),
            technique=a('lithotripter', 'lithotripsy', ['P3'])),
        act('E4', 'P4', 'stone_extraction', 'extracted', status_words='were removed', procedure=a('ercp'),
            target=tg('', 'bile_duct', 'bile duct', ['P4']),
            technique=a('extraction_balloon', 'extraction balloon', ['P4'])),
        act('E5', 'P5', 'stone_extraction', 'swept again', status_words='was swept again', procedure=a('ercp'),
            target=tg('', 'bile_duct', 'the bile duct', ['P5']),
            technique=a('extraction_balloon', 'extraction balloon', ['P5']),
            time=a('current_encounter', 'During the procedure', ['P5']))])
    return inv, text, [('43264', lines[cite]), ('43265', STONE['P3'])]


class D163WhatAHeldCodeClaims(SimpleTestCase):
    def test_d163_g3_a_technique_code_held_for_its_site_adds_no_claim(self):
        """D163 as integrated (variant G3, the integration owner's choice): a held TECHNIQUE code (a dilation code) adds
        no claim - D118 governs technique codes, 'an act is never paired with itself' - so FRESH-2 fb07's shape (D118's
        C_ANASTOMOSIS) keeps f9013e12e's outcome: 43249 held for its site (the anastomosis is unsettled for the
        esophageal class: an altered landmark is never outside it, D29) with its site question alone, and 43245, which
        the gastrojejunal anastomosis fits, READY with no competition. The general form G2 held 43245 competing_codes
        here, a cost on an attested document (3 FRESH-2 false holds; h2h run 1 214 -> 213) that G3 avoids while
        closing every rival input."""
        result = assessed(C_ANASTOMOSIS)
        self.assertEqual(proposal(result, '43249').support['reason'], events.SITE)
        held(self, result, '43249', ['act_target'])
        ready(self, result, '43245')  # no base_included and no competing_codes check: no competition

    def test_d163_a_7_4_hold_of_two_acts_holds_the_rival_on_the_act_its_question_does_not_name(self):
        """The class beyond the two holds the sources name (constructed): finding 5's stone clearance with the
        extraction's status words unbound (E4: 'were removed' is not in its passage) and a second sweep whose time is
        worded and unanchored (E5). 43264 is held by 7.4 (unverified), its question naming E4; 43265 claims E5 through
        D74 (E4's status is not usable). e5628be56 and f9013e12e: 43265 READY. c2e53f8e with its participants: both
        held [competing_codes]. The held code keeps every act its evaluation read (E4 and E5), so 43265 is held
        competing_codes - c2e53f8e's outcome - whichever line 43264 cites."""
        for cite in ('P4', 'P5'):
            inv, text, codes = two_extractions(cite)
            for setting, participants in SETTINGS:
                with self.subTest(cited=cite, setting=setting):
                    result = run(inv, text, codes, participants=participants)
                    extraction = proposal(result, '43264')
                    self.assertEqual((extraction.support['reason'], extraction.support.get('question_events')),
                                     (events.UNVERIFIED, ['E4']))
                    rivals_held(self, result, events.UNVERIFIED)

    def test_d163_a_held_code_claims_the_acts_its_question_names(self):
        """The 'names' half: D156 (2)'s combined hold of 43240 (round5e eus5's input: a failed pseudocyst drainage E2
        beside a done bile duct drainage E3) reads E3 and names E2 and E3 in its question; it claims both. No other
        code covers a drainage today, so this pins the claim, not an outcome."""
        from tests.test_interpretation_r5e_eus import ATTEMPTED, ATTEMPTED_PFC, two_drainages
        inv, text = two_drainages(ATTEMPTED_PFC, ATTEMPTED)
        self.assertEqual(claims(inv, text, '43240', ATTEMPTED_PFC), ('E2', 'E3'))

    def test_d163_controls_an_act_verified_as_not_the_codes_is_never_claimed(self):
        """What a held code could NOT account for is never its claim, so these stay as before (c2e53f8e: a dilation of
        another technique is no act the code accounts for): a dilation of another technique than every dilation
        (C_TWO_BALLOONS: 43249 READY, 43248 held technique) or at another encounter (C_HISTORY), a dilation verified
        outside the code's site class (C_PYLORUS: 43245 READY, 43249 held for its site), the polypectomy a bleeding
        control may be part of (45385 READY beside 45382's bundling-identity hold), and the other side of a possible
        stent exchange (D105: each side asks only the exchange question)."""
        result = assessed(C_TWO_BALLOONS)
        ready(self, result, '43249')
        held(self, result, '43248', ['technique'])
        result = assessed(C_HISTORY)
        ready(self, result, '43249')
        self.assertNotIn('competing_codes', asked(proposal(result, '43248')))
        result = assessed(C_PYLORUS)
        ready(self, result, '43245')
        held(self, result, '43249', ['act_target'])
        inv, text = colonoscopy(hemoclips(), lines={'P3': HEMOCLIPS})
        result = run(inv, text, [('45385', POLYP), ('45382', HEMOCLIPS)])
        self.assertEqual((proposal(result, '45385').status, asked(proposal(result, '45382')),
                          proposal(result, '45382').support['reason']),
                         ('ready', ['act_target'], events.BUNDLING_IDENTITY))
        inv, text, lines = stent_exchange()
        result = run(inv, text, [('43275', lines['P3']), ('43274', lines['P5']), ('43276', lines['P1'])])
        self.assertEqual({code: (asked(proposal(result, code)), proposal(result, code).support['reason'])
                          for code in ('43275', '43274', '43276')},
                         {code: (['performed_status'], ercp.POSSIBLE_EXCHANGE) for code in ('43275', '43274', '43276')})

    def test_d163_controls_an_act_that_is_no_doubt_is_never_claimed(self):
        """A held code claims an act only as a doubt about itself - stated positive or uncertain, possibly current
        (D62) and not verified as another performer's - never one its hold read as an absence: two codes for one
        stricture dilated at another hospital in 2024 (each held, not documented) do not compete, and D74's 43265 for
        a denied lithotripsy still claims nothing (43264 READY)."""
        lines = {'P5': 'The gastroscope was advanced to the second portion of the duodenum.',
                 'P6': 'A benign-appearing peptic stricture was seen in the distal esophagus at 37 cm.',
                 'P7': 'In 2024 the stricture had been dilated with a through-the-scope balloon at another hospital.'}
        inv, text = inventory(lines, events=[
            exam('E1', 'P5', words='gastroscope', procedure=a('egd')),
            act('E2', 'P7', 'dilation', 'dilated', status_words='had been dilated', procedure=a('egd'),
                technique=a('balloon', 'through-the-scope balloon', ['P7']),
                target=tg('', 'distal_esophagus', 'the stricture', ['P7']),
                time=a('earlier_encounter', 'In 2024', ['P7']),
                performer=a('other_facility', 'at another hospital', ['P7']))])
        for setting, participants in SETTINGS:
            with self.subTest(setting=setting):
                result = run(inv, text, [('43249', lines['P7']), ('43245', lines['P7'])], participants=participants)
                for code in ('43249', '43245'):
                    p = proposal(result, code)
                    self.assertNotIn('competing_codes', asked(p))
                    self.assertIsNone(p.support.get('competes'))
        lines = {pid: STONE[pid] for pid in ('P1', 'P2', 'P4')}
        lines['P3'] = 'No lithotripsy was performed for the 15 mm stone in the common bile duct.'
        inv, text = inventory(lines, events=[
            exam('E1', 'P1', words='duodenoscope', procedure=a('ercp')),
            act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
                target=tg('', 'bile_duct', 'biliary', ['P2'])),
            act('E3', 'P3', 'lithotripsy', 'lithotripsy', status='not_performed',
                status_words='No lithotripsy was performed', procedure=a('ercp')),
            act('E4', 'P4', 'stone_extraction', 'extracted', status_words='were extracted', procedure=a('ercp'),
                target=tg('', 'bile_duct', 'bile duct', ['P4']),
                technique=a('extraction_balloon', 'extraction balloon', ['P4']))])
        self.assertEqual(claims(inv, text, '43265', lines['P3']), ())
        result = run(inv, text, [('43264', lines['P4']), ('43265', lines['P3'])], participants=READ_NOTHING)
        self.assertEqual(proposal(result, '43264').status, 'ready')
