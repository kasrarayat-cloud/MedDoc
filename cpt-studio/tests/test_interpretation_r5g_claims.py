"""Round 5g of the Gemini migration, D167 (narrowing only): D74's extras also read the acts of a narrowed code's other
kinds that are only doubted. SYNTHETIC and constructed: nothing is sent.

review:claims6 problem 1 (round 5f; pre-existing on e5628be56, f9013e12e and 05a881a75): finding 5's stone clearance
(tests.test_interpretation_r3_claims.STONE) with Gemini's status words for the extraction E4 'were removed', which its
passage P4 does not hold (status performed, unverified, words_unlocated: the attribute state FRESH-2 C/C2MEM-023 r1
attests on E35 and E36). D163 gave the held 43264 its act (E4), but D74's extras read only the current performed acts
(coverage.current_performed: a usable status), so 43265 claimed its lithotripsy (E3) alone, combination.competition
found no pair, and 43265 was READY with no competing_codes beside the held 43264 of one stone clearance. c2e53f8e with
its participants configured (Astra and Fable read and proposing nothing, test_interpretation_r3_claims.READ_NOTHING)
holds both [competing_codes]; with none configured it READYs both. D167: the extras also read the acts of the code's
other kinds that D163's own() keeps - stated positive or uncertain in ANY verification state, possibly current (D62),
not verified as another performer's - and still every current performed act, so the change only ever adds a
competition pair. Every assessed pin runs in both settings: the new path gives one outcome in both. review:claims6
problem 2 is the D163 docstring's wording (no behaviour, so no pin).
"""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import coverage, events
from tests.test_interpretation_events import asked, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_claims import READ_NOTHING, STONE, claims

SETTINGS = (('no participant', ()), ('Astra and Fable read and proposing nothing', READ_NOTHING))
UNBOUND = {'status_words': 'were removed'}  # not in P4: status performed, unverified (words_unlocated)
RUIZ = 'Dr. Ruiz extracted the stone fragments from the bile duct with an extraction balloon.'
PATEL = 'Dr. Patel extracted the stone fragments from the bile duct with an extraction balloon.'
ATTEMPTED = 'Extraction of the stone fragments with an extraction balloon was attempted and abandoned.'
EARLIER = 'In 2024 the stone fragments were extracted from the bile duct with an extraction balloon.'
DURING = 'During the procedure, the stone fragments were extracted from the bile duct with an extraction balloon.'
BOTH_HELD = ['performed_status', 'competing_codes']


def clearance(p4: str = STONE['P4'], *, p3: str = STONE['P3'], e4=None, e3=None, named: bool = False,
              open_questions=(), without=()) -> tuple:
    """Finding 5's stone clearance: the duodenoscope (E1), the biliary cannulation (E2), the mechanical lithotripsy of
    the 15 mm stone (E3, 43265's defining act) in ``p3`` and the balloon extraction of its fragments (E4, 43264's act)
    in ``p4``; ``e4`` and ``e3`` change those events' attributes and ``without`` drops events. (inventory, text,
    codes), 43264 citing P4 and 43265 P3: review:claims6's probe input as it built it
    (round5f/review-claims6/tools/provider_refute.py), and round5g/claims7/tools/provider_d167.py's."""
    lines = dict(STONE, P3=p3, P4=p4)
    extraction = {'status_words': 'were extracted', 'procedure': a('ercp'),
                  'target': tg('', 'bile_duct', 'bile duct', ['P4']),
                  'technique': a('extraction_balloon', 'extraction balloon', ['P4']), **(e4 or {})}
    lithotripsy = {'status_words': 'was fragmented', 'procedure': a('ercp'),
                   'target': tg('', 'common_bile_duct', 'common bile duct', ['P3']),
                   'technique': a('lithotripter', 'lithotripsy', ['P3']), **(e3 or {})}
    found = [exam('E1', 'P1', words='duodenoscope', procedure=a('ercp')),
             act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved', procedure=a('ercp'),
                 target=tg('', 'bile_duct', 'biliary', ['P2']),
                 technique=a('sphincterotome', 'sphincterotome', ['P2'])),
             act('E3', 'P3', 'lithotripsy', 'lithotripsy', **lithotripsy),
             act('E4', 'P4', 'stone_extraction', extraction.pop('kind_words', 'extracted'), **extraction)]
    inv, text = inventory(lines, named=named, open_questions=list(open_questions),
                          events=[item for item in found if item['id'] not in without])
    return inv, text, [('43264', lines['P4']), ('43265', lines['P3'])]


def outcome(result, code: str) -> tuple:
    p = proposal(result, code)
    return p.status, asked(p), p.support['reason'], p.support.get('competes')


def acts(result, code: str) -> list:
    return [item['id'] for item in proposal(result, code).support['acts']]


def extraction_of(inv) -> dict:
    return events.Reading.of(inv).events['E4']


class D167DoubtedActOfTheOtherKind(SimpleTestCase):
    def test_d167_an_extraction_whose_status_words_do_not_locate_holds_the_lithotripsys_43265(self):
        """review:claims6 problem 1's own input: E4's status words 'were removed' are not in P4. 43264 is held by 7.4
        (unverified) and now asks competing_codes beside it; 43265 is held competing_codes, where e5628be56, f9013e12e
        and 05a881a75 READY it with no question; c2e53f8e with its participants holds both [competing_codes] (with none,
        READY both: the cost in that setting). E* is unchanged: 43265 stands on its lithotripsy, 43264 on no act."""
        inv, text, codes = clearance(e4=UNBOUND)
        status = extraction_of(inv)['status']
        self.assertEqual((status['value'], status['state'], status['reasons']),
                         ('performed', 'unverified', ['words_unlocated']))
        self.assertEqual(claims(inv, text, '43265', STONE['P3']), ('E3', 'E4'))  # D167: E4 is no absence
        self.assertEqual(claims(inv, text, '43264', STONE['P4']), ('E4',))  # D163, unchanged
        for setting, participants in SETTINGS:
            with self.subTest(setting=setting):
                result = run(inv, text, codes, participants=participants)
                self.assertEqual(outcome(result, '43264'),
                                 ('needs_clarification', BOTH_HELD, events.UNVERIFIED, ['43265']))
                self.assertEqual(outcome(result, '43265'), ('needs_clarification', ['competing_codes'],
                                                            events.SUPPORTED, ['43264']))
                self.assertEqual((acts(result, '43264'), acts(result, '43265')), ([], ['E3']))

    def test_d167_an_extraction_attempted_opened_or_by_an_unconfirmed_clinician_is_a_doubt_too(self):
        """The class's other members (constructed; round5g/claims7/tools/provider_d167.py S5-S9, S15): the extraction
        attempted and abandoned (verified, and with its status words unbound), its status opened by Gemini's own
        question, its time unanchored or unknown with its status words unbound, and done by a clinician the document
        does not establish as another (performer other_clinician unverified: name_not_other) with its status words
        unbound. Each is a doubt about the code that accounts for it: 43265 now claims E4 and is held competing_codes
        where every earlier new-path head READYs it; 43264, held by its own doubt, adds competing_codes. c2e53f8e with
        its participants holds both [competing_codes] on every one (with none, READY both)."""
        members = {
            'attempted, its status verified': (clearance(ATTEMPTED, e4={
                'status': 'attempted_not_completed', 'kind_words': 'Extraction',
                'status_words': 'was attempted and abandoned'}), events.ATTEMPTED),
            'attempted, its status words unbound': (clearance(ATTEMPTED, e4={
                'status': 'attempted_not_completed', 'kind_words': 'Extraction', 'status_words': 'was tried'}),
                events.UNVERIFIED),
            "its status opened by Gemini's own question": (clearance(open_questions=[
                {'about': 'status', 'events': ['E4'], 'lesions': [], 'passages': ['P4']}]), events.UNVERIFIED),
            'its time unanchored, its status words unbound': (clearance(
                DURING, e4={**UNBOUND, 'time': a('current_encounter', 'During the procedure', ['P4'])}),
                events.UNVERIFIED),
            'its time unknown, its status words unbound': (clearance(e4={**UNBOUND, 'time': a('unknown')}),
                                                          events.UNVERIFIED),
            'by a clinician not established as another, its status words unbound': (clearance(RUIZ, e4={
                **UNBOUND, 'performer': a('other_clinician', 'Dr. Ruiz', ['P4'])}), events.UNVERIFIED),
        }
        for name, ((inv, text, codes), reason) in members.items():
            extraction = extraction_of(inv)
            self.assertFalse(coverage.current_performed(extraction), name)  # never claimed before D167
            self.assertFalse(events.verified_other_performer(extraction), name)
            self.assertEqual(claims(inv, text, '43265', STONE['P3']), ('E3', 'E4'), name)
            for setting, participants in SETTINGS:
                with self.subTest(member=name, setting=setting):
                    result = run(inv, text, codes, participants=participants)
                    self.assertEqual(outcome(result, '43264'), ('needs_clarification', BOTH_HELD, reason, ['43265']))
                    self.assertEqual(outcome(result, '43265'), ('needs_clarification', ['competing_codes'],
                                                                events.SUPPORTED, ['43264']))
                    self.assertEqual(acts(result, '43265'), ['E3'])

    def test_d167_an_extraction_stated_uncertain_holds_43265_a_recorded_cost(self):
        """review:claims6's R2 and R3 (constructed): the extraction stated uncertain ('may have been extracted', 'It is
        unclear whether'). 43264 is held for its doubt and now asks competing_codes; 43265 is held competing_codes,
        where every earlier new-path head READYs it - and so does c2e53f8e, in both settings (it holds 43264
        readings_disagree): a RECORDED COST of the specified 'uncertain' (D104's reading of a doubt). The document
        supports 43265 alone (its lithotripsy was performed)."""
        wordings = {
            'may have been': ('The stone fragments may have been extracted from the bile duct with an extraction '
                              'balloon.', 'may have been extracted'),
            'it is unclear': ('It is unclear whether the stone fragments were extracted from the bile duct with an '
                              'extraction balloon.', 'It is unclear whether'),
        }
        for name, (line, words) in wordings.items():
            inv, text, codes = clearance(line, e4={'status': 'uncertain', 'status_words': words})
            self.assertEqual(claims(inv, text, '43265', STONE['P3']), ('E3', 'E4'))
            for setting, participants in SETTINGS:
                with self.subTest(wording=name, setting=setting):
                    result = run(inv, text, codes, participants=participants)
                    self.assertEqual(outcome(result, '43264'),
                                     ('needs_clarification', BOTH_HELD, events.DOUBT, ['43265']))
                    self.assertEqual(outcome(result, '43265'), ('needs_clarification', ['competing_codes'],
                                                                events.SUPPORTED, ['43264']))
                    self.assertEqual(acts(result, '43265'), ['E3'])

    def test_d167_a_doubted_lithotripsy_beside_a_doubted_extraction_asks_competing_codes_of_both(self):
        """review:claims6's related case (R7) and two more (constructed): the extraction's status words unbound beside a
        lithotripsy whose status words are unbound too ('was crushed'), stated uncertain (D104) or whose time is
        unanchored (D74). Both codes were held by their own doubts and neither asked competing_codes; each asks it now,
        as c2e53f8e with its participants asks it of both (with none, READY both). The held 43265 claims the extraction
        through D74's extras (its family's lithotripsy is stated positive or uncertain, possibly current) and its own
        doubted lithotripsy through D163."""
        shapes = {
            'lithotripsy status words unbound': (dict(e3={'status_words': 'was crushed'}),
                                                 ('performed_status', events.UNVERIFIED)),
            'lithotripsy stated uncertain': (dict(p3='It is unclear from the record whether the 15 mm stone in the '
                                                     'common bile duct was fragmented with mechanical lithotripsy.',
                                                  e3={'status': 'uncertain', 'status_words': 'It is unclear'}),
                                             ('performed_status', events.DOUBT)),
            'lithotripsy time unanchored': (dict(p3='During the procedure, a 15 mm stone in the common bile duct was '
                                                    'fragmented with mechanical lithotripsy.',
                                                 e3={'time': a('current_encounter', 'During the procedure', ['P3'])}),
                                            ('event_time', events.UNVERIFIED)),
        }
        for name, (options, (own_fact, reason)) in shapes.items():
            inv, text, codes = clearance(e4=UNBOUND, **options)
            self.assertEqual(claims(inv, text, '43265', codes[1][1]), ('E4', 'E3'), name)
            for setting, participants in SETTINGS:
                with self.subTest(shape=name, setting=setting):
                    result = run(inv, text, codes, participants=participants)
                    self.assertEqual(outcome(result, '43264'),
                                     ('needs_clarification', BOTH_HELD, events.UNVERIFIED, ['43265']))
                    self.assertEqual(outcome(result, '43265'),
                                     ('needs_clarification', [own_fact, 'competing_codes'], reason, ['43264']))

    def test_d167_the_other_narrowed_codes_compete_for_a_doubted_act_of_their_other_kind(self):
        """review:claims6's refute2 H1 and J1, and the same acts stated uncertain (constructed; the D74 pins' shapes,
        tests.test_interpretation_r3_claims): the ablation's status words ('were cauterized') or the jejunostomy tube's
        ('was inserted') do not bind, or the act is stated uncertain, beside the verified defining act of 44365 (hot
        forceps) or 49440 (gastrostomy). 44369 / 49441 are held by their own doubt and each pair now competes. 44365 is
        held competing_codes where c2e53f8e holds it too (readings_disagree, in both settings); 49440 is held
        competing_codes where c2e53f8e READYs it in both settings - a RECORDED COST, the one D55 gives the verified
        pair (both held on every new-path head, both READY on c2e53f8e)."""
        lines = {'P1': 'The enteroscope was advanced to the jejunum.',
                 'P2': 'Two gastric antral angioectasias were treated with argon plasma coagulation.',
                 'P3': 'A 5 mm jejunal polyp was removed with hot biopsy forceps.'}
        uncertain = 'Two gastric antral angioectasias may have been treated with argon plasma coagulation.'
        for name, (p2, status, words, reason) in {
                'ablation status words unbound': (lines['P2'], 'performed', 'were cauterized', events.UNVERIFIED),
                'ablation stated uncertain': (uncertain, 'uncertain', 'may have been treated', events.DOUBT)}.items():
            doc = dict(lines, P2=p2)
            inv, text = inventory(doc, reach=[reached(landmark='jejunum', words='jejunum')], events=[
                exam(words='enteroscope', procedure=a('enteroscopy')),
                act('E2', 'P2', 'ablation', 'argon plasma coagulation', status=status, status_words=words,
                    procedure=a('enteroscopy'), technique=a('argon_plasma', 'argon plasma coagulation', ['P2']),
                    target=tg('', 'gastric_antrum', 'gastric antral', ['P2'])),
                act('E3', 'P3', 'hot_biopsy', 'hot biopsy forceps', status_words='was removed',
                    procedure=a('enteroscopy'), technique=a('hot_forceps', 'hot biopsy forceps', ['P3']),
                    target=tg('', 'jejunum', 'jejunal', ['P3']))])
            self.assertEqual(claims(inv, text, '44365', doc['P3']), ('E3', 'E2'), name)
            for setting, participants in SETTINGS:
                with self.subTest(pair='44365 / 44369', shape=name, setting=setting):
                    result = run(inv, text, [('44365', doc['P3']), ('44369', doc['P2'])], participants=participants)
                    self.assertEqual(outcome(result, '44365'), ('needs_clarification', ['competing_codes'],
                                                                events.SUPPORTED, ['44369']))
                    self.assertEqual(outcome(result, '44369'), ('needs_clarification', BOTH_HELD, reason, ['44365']))
                    self.assertEqual(acts(result, '44365'), ['E3'])
        lines = {'P1': 'A 14 Fr jejunostomy tube was placed percutaneously under fluoroscopic guidance.',
                 'P2': 'A 20 Fr gastrostomy tube was placed percutaneously under fluoroscopic guidance.'}
        uncertain = 'A 14 Fr jejunostomy tube may have been placed percutaneously under fluoroscopic guidance.'
        for name, (p1, status, words, reason) in {
                'tube placement status words unbound': (lines['P1'], 'performed', 'was inserted', events.UNVERIFIED),
                'tube placement stated uncertain': (uncertain, 'uncertain', 'may have been placed',
                                                    events.DOUBT)}.items():
            doc = dict(lines, P1=p1)
            inv, text = inventory(doc, events=[
                act('E1', 'P1', 'tube_placement', 'jejunostomy tube', status=status, status_words=words,
                    procedure=a('feeding_tube')),
                act('E2', 'P2', 'peg', 'gastrostomy tube', status_words='was placed', procedure=a('feeding_tube'))])
            self.assertEqual(claims(inv, text, '49440', doc['P2']), ('E2', 'E1'), name)
            for setting, participants in SETTINGS:
                with self.subTest(pair='49440 / 49441', shape=name, setting=setting):
                    result = run(inv, text, [('49440', doc['P2']), ('49441', doc['P1'])], participants=participants)
                    self.assertEqual(outcome(result, '49440'), ('needs_clarification', ['competing_codes'],
                                                                events.SUPPORTED, ['49441']))
                    self.assertEqual(outcome(result, '49441'), ('needs_clarification', BOTH_HELD, reason, ['49440']))
                    self.assertEqual(acts(result, '49440'), ['E2'])

    def test_d167_controls_an_act_of_the_other_kind_that_is_no_doubt_is_never_claimed(self):
        """The extras read an act only doubted as a doubt about the code - stated positive or uncertain, possibly
        current (D62), not verified as another performer's (D87) - never one that is an absence (constructed;
        tools/provider_d167.py C2-C6, C8-C10): an extraction denied, planned, at an earlier encounter (its status words
        bound or not), done by a clinician verified as another with its status words unbound, or stated in another
        family adds no claim to 43265 (it claims its lithotripsy alone), and 43265 stays READY on its lithotripsy with
        43264 held as before, asking no competing_codes, in both settings, as on 05a881a75 and e5628be56. A denied
        lithotripsy, or none stated, still gives 43265 no claims at all: D74's gate is unchanged."""
        scope = ('needs_clarification', ['statement_scope'], events.STATEMENT_SCOPE, None)
        unclaimed = {
            'denied': (clearance('No stone fragments were extracted from the bile duct with an extraction balloon.',
                                 e4={'status': 'not_performed', 'status_words': 'No stone fragments were extracted'}),
                       scope),
            'planned': (clearance('Extraction of the stone fragments with an extraction balloon is planned.', e4={
                'status': 'planned', 'status_words': 'is planned', 'target': tg('', 'bile_duct', '', [])}),
                ('needs_clarification', ['performed_status'], events.NOT_DOCUMENTED, None)),
            'an earlier encounter': (clearance(EARLIER, e4={'time': a('earlier_encounter', 'In 2024', ['P4'])}),
                                     scope),
            'an earlier encounter, its status words unbound': (
                clearance(EARLIER, e4={**UNBOUND, 'time': a('earlier_encounter', 'In 2024', ['P4'])}), scope),
            'another clinician verified, its status words unbound': (
                clearance(PATEL, named=True, e4={**UNBOUND, 'performer': a('other_clinician', 'Dr. Patel', ['P4'])}),
                scope),
        }
        for name, ((inv, text, codes), held) in unclaimed.items():
            extraction = extraction_of(inv)
            self.assertFalse(coverage.current_performed(extraction), name)
            self.assertEqual(claims(inv, text, '43265', STONE['P3']), ('E3',), name)
            for setting, participants in SETTINGS:
                with self.subTest(unclaimed=name, setting=setting):
                    result = run(inv, text, codes, participants=participants)
                    self.assertEqual(outcome(result, '43264'), held)
                    self.assertEqual(outcome(result, '43265'), ('ready', [], events.SUPPORTED, None))
                    self.assertEqual(acts(result, '43265'), ['E3'])
        inv, _text, _codes = unclaimed['another clinician verified, its status words unbound'][0]
        self.assertTrue(events.verified_other_performer(extraction_of(inv)))
        inv, text, _codes = clearance(e4={**UNBOUND, 'procedure': a('egd')})
        self.assertEqual(extraction_of(inv)['family'], 'gi.egd')
        self.assertEqual(claims(inv, text, '43265', STONE['P3']), ('E3',))  # another family: never this code's act
        inv, text, codes = clearance(p3='A 15 mm stone in the common bile duct was not fragmented.', e4=UNBOUND,
                                     e3={'status': 'not_performed', 'status_words': 'was not fragmented'})
        self.assertEqual(claims(inv, text, '43265', codes[1][1]), ())
        inv, text, codes = clearance(p3='A 15 mm stone was seen in the common bile duct.', e4=UNBOUND, without=('E3',))
        self.assertEqual(claims(inv, text, '43265', codes[1][1]), ())
        self.assertEqual(outcome(run(inv, text, codes), '43265')[2], events.NOT_DOCUMENTED)

    def test_d167_the_current_performed_acts_are_claimed_as_before(self):
        """The extras keep every current performed act D74 claimed (coverage.current_performed), one verified as another
        performer's included, so the change only ever adds a competition pair: an extraction 'were extracted' by
        Dr. Patel (status verified, performer verified as another clinician) is still 43265's claim, beside 43264 held
        statement_scope, which claims nothing (D163's own(): a verified other performer's act is no act the code
        accounts for), so 43265 stays READY on its lithotripsy as on 05a881a75 and e5628be56 (c2e53f8e with its
        participants holds both [competing_codes]; with none, READY both). The verified control (finding 5's own text)
        keeps both codes held competing_codes in both settings, and either code proposed alone beside the unbound
        extraction is unchanged: 43265 READY, 43264 held by 7.4 without competing_codes."""
        inv, text, codes = clearance(PATEL[:-1] + '; the fragments were extracted.', named=True,
                                     e4={'performer': a('other_clinician', 'Dr. Patel', ['P4'])})
        extraction = extraction_of(inv)
        self.assertTrue(events.verified_other_performer(extraction))
        self.assertTrue(coverage.current_performed(extraction))
        self.assertEqual(claims(inv, text, '43265', STONE['P3']), ('E3', 'E4'))
        self.assertEqual(claims(inv, text, '43264', codes[0][1]), ())
        inv_control, text_control, codes_control = clearance()
        self.assertEqual(claims(inv_control, text_control, '43265', STONE['P3']), ('E3', 'E4'))
        inv_alone, text_alone, codes_alone = clearance(e4=UNBOUND)
        rivals = ('needs_clarification', ['competing_codes'], events.SUPPORTED)
        for setting, participants in SETTINGS:
            with self.subTest(setting=setting):
                result = run(inv, text, codes, participants=participants)
                self.assertEqual(outcome(result, '43264'), ('needs_clarification', ['statement_scope'],
                                                            events.STATEMENT_SCOPE, None))
                self.assertEqual(outcome(result, '43265'), ('ready', [], events.SUPPORTED, None))
                result = run(inv_control, text_control, codes_control, participants=participants)
                self.assertEqual(outcome(result, '43264'), rivals + (['43265'],))
                self.assertEqual(outcome(result, '43265'), rivals + (['43264'],))
                alone = run(inv_alone, text_alone, codes_alone[1:], participants=participants)
                self.assertEqual(outcome(alone, '43265'), ('ready', [], events.SUPPORTED, None))
                alone = run(inv_alone, text_alone, codes_alone[:1], participants=participants)
                self.assertEqual(outcome(alone, '43264'), ('needs_clarification', ['performed_status'],
                                                           events.UNVERIFIED, None))
