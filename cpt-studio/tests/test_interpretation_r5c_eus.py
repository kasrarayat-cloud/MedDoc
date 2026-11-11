"""DECISIONS D135-D138 (the Gemini migration's round 5c: the round-5 review of the eus2 repair D120-D123, problems 0-3),
SYNTHETIC, each built from its source's own input (round5b/review-committed_eus2.json). Nothing is sent.
- D135 (problem 0): an EUS told only through its done EUS-guided act takes that act WHATEVER its kind - an EUS-guided
  through-the-needle microforceps biopsy, a radiofrequency ablation, a gastroenterostomy's lumen-apposing stent, a coil
  embolization read as 'other' - not only an FNA, an injection or a drainage (D121): today's EGD is its endoscopic
  portion, so 43235 is held base_included beside the EUS code and alone, as the installed release (c2e53f8e) holds it;
  the same act told 'After the EGD, ...' (only possibly of this encounter) is a possible upper EUS. Such an act is
  never lower evidence (D96), and an act-only session's own act placed lower is a doubt about its place (D123).
- D136 (problem 1): 43240 is supported only by a drainage whose verified target is a pancreatic fluid collection (D120's
  mapping.defining_target, read in events.supports): a drainage of the gallbladder, a bile duct or a liver abscess, or
  one whose target is not verified, holds 43240 - never READY.
- D137 (problem 2): an examination-only EUS code beside a done EUS-guided act of a kind the EUS's catalogue entry does
  not list (the gastroenterostomy's stent, an ablation, a coil embolization) is held base_included: the act is recorded
  among the EUS session's reportable entries (coverage.event_coding), which combination.base_included and the
  read-time overlay read.
- D138 (problem 3): an act whose performer is verified as another clinician is no possible upper EUS (as
  coverage.doubted reads a doubt): 43235 is READY beside it, as on d353e64df and c2e53f8e.
Each test asserts in independent subtests - the outcome, the read-time overlay, the structure - so a regression shows
every one it breaks."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import combination, coverage, events, mapping
from tests.test_interpretation_events import asked, check, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, les, tg
from tests.test_interpretation_r3_eus import DUODENUM, SEPARATELY, egd_item
from tests.test_interpretation_r3_integration_d88_d93 import egd_coding, items, reviewed
from tests.test_interpretation_r4_eus_lower import held_beside, lower_ids, ready_unheld, sessions_of
from tests.test_interpretation_r5_eus import DRAINAGE_LINES, REPORT, UPPER, UPPER_Q, beside, drainage_case


def gap1(line: str, found_act: dict, lesions=(), **options):
    """Gap 1's document (audit battery 4, g2b), as problem 0 builds it: the heading (P1), the EGD to the second portion
    of the duodenum (E1) and one EUS-guided act (E2, P3) - no EUS examination event."""
    found = [exam('E1', 'P2', words='gastroscope', procedure=a('egd', 'UPPER ENDOSCOPY', ['P1'])), found_act]
    return inventory({'P1': REPORT, 'P2': UPPER, 'P3': line}, events=found, lesions=list(lesions),
                     reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2')], **options)


# --- D135 (problem 0): an EUS told only through an EUS-guided act of another kind ------------------------------------

TTNB = 'EUS-guided through-the-needle microforceps biopsy of the 3 cm cyst in the pancreatic body was performed.'
RFA = 'EUS-guided radiofrequency ablation of the 15 mm insulinoma in the pancreatic tail was performed.'
EUSGE = ('EUS-guided gastroenterostomy was performed: a 20 mm lumen-apposing metal stent was deployed from the gastric '
         'body into a distended jejunal loop.')
COIL = 'EUS-guided coil embolization of the gastric fundal varix was performed.'
RFA_AFTER = f'After the EGD, {RFA}'
CYST = les('L1', '3 cm cyst', 'P3', landmark='pancreas', site_words='pancreatic body', size_words='3 cm')
INSULINOMA = les('L1', '15 mm insulinoma', 'P3', landmark='pancreas', site_words='pancreatic tail', size_words='15 mm')


def ttnb() -> dict:
    return act('E2', 'P3', 'biopsy', 'microforceps biopsy', status_words='was performed',
               procedure=a('eus', 'EUS-guided', ['P3']), technique=a('forceps', 'microforceps', ['P3']),
               target=tg('L1', 'pancreas', 'the 3 cm cyst in the pancreatic body', ['P3']))


def rfa(**changes) -> dict:
    return act('E2', 'P3', 'ablation', 'radiofrequency ablation', status_words='was performed',
               procedure=a('eus', 'EUS-guided', ['P3']), technique=a('radiofrequency', 'radiofrequency', ['P3']),
               target=tg('L1', 'pancreas', 'the 15 mm insulinoma in the pancreatic tail', ['P3']), **changes)


def eusge_stent() -> dict:
    return act('E2', 'P3', 'stent', 'lumen-apposing metal stent', status_words='was deployed',
               procedure=a('eus', 'EUS-guided', ['P3']), technique=a('stent', 'lumen-apposing metal stent', ['P3']),
               target=tg('', 'jejunum', 'a distended jejunal loop', ['P3']))


def coil() -> dict:
    return act('E2', 'P3', 'other', 'coil embolization', status_words='was performed',
               procedure=a('eus', 'EUS-guided', ['P3']),
               target=tg('', 'gastric_fundus', 'the gastric fundal varix', ['P3']))


# name: (the act's line, the act, its lesions, the EUS code Corti proposes beside 43235) - problem 0's inputs
PROBLEM_0 = {'microforceps_biopsy': (TTNB, ttnb, (CYST,), '43242'),
             'radiofrequency_ablation': (RFA, rfa, (INSULINOMA,), '43259'),
             'gastroenterostomy_stent': (EUSGE, eusge_stent, (), '43259'),
             'coil_embolization': (COIL, coil, (), '43259')}


class AnEusToldOnlyByAnActOfAnyKindIsAnUpperEus(SimpleTestCase):
    """D135 (problem 0, critical): c2e53f8e holds 43235 base_included on each of these inputs, beside the code and
    alone; 46e461e7f READYs it, its act-only session built from EUS_ACTS kinds alone."""

    def test_d135_43235_beside_the_eus_code_and_alone_is_held_base_included(self):
        for name, (line, build, lesions, code) in PROBLEM_0.items():
            inv, text = gap1(line, build(), lesions)
            reading = events.Reading.of(inv)
            with self.subTest(act=name, part='fixture'):  # the review's: a done EUS-guided act of no EUS kind
                event = reading.events['E2']
                self.assertEqual((events.done(event), events.usable(event, 'procedure'), coverage.eus_act(event),
                                  coverage.eus_guided_act(event)), (True, True, False, True))
            result = run(inv, text, [('43235', UPPER_Q), (code, line)])
            with self.subTest(act=name, part='assess'):  # 46e461e7f: READY
                held_beside(self, result, '43235', (code,), beside(code))
            with self.subTest(act=name, part='event_coding'):
                self.assertEqual(egd_coding(result), ('gi.eus', ''))
                self.assertEqual(result.completeness['included_by'], {'gi.egd': [code]})
            with self.subTest(act=name, part='alone'):  # 46e461e7f: READY
                held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)
            with self.subTest(act=name, part='structure'):
                sessions = coverage.sessions(reading)
                self.assertEqual((sessions['gi.eus'].event, sessions['gi.eus'].examinations, sessions['gi.eus'].done),
                                 ('', (), True))
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('gi.eus', ''))

    def test_d135_the_act_is_never_lower_evidence(self):
        """D96 kept: only an act of the EUS's own kinds (eus_act) is lower evidence - the act-only session reads these
        acts as the EUS's, never as facts about its place."""
        for name, (line, build, lesions, _) in PROBLEM_0.items():
            with self.subTest(act=name):
                self.assertEqual(lower_ids(gap1(line, build(), lesions)[0]), [])

    def test_d135_with_no_proposal_the_egd_asks_no_code_of_its_own(self):
        """As D121's: the EGD is the EUS's endoscopic portion, so the EUS's no_proposal item is listed and the EGD's is
        not - c2e53f8e marks the EGD included in the EUS too (its listing of the act itself is the egd3 repair's)."""
        for name, (line, build, lesions, _) in PROBLEM_0.items():
            with self.subTest(act=name):
                result = run(*gap1(line, build(), lesions), [])
                self.assertEqual(items(result), [('gi.eus', 'no_proposal', True)])
                self.assertIsNone(egd_item(result))

    def test_d135_an_act_only_possibly_of_this_encounter_is_a_possible_upper_eus(self):
        """The RFA told 'After the EGD, ...' (its time unanchored: possibly current, not done) is a doubt, never the
        session: 43235 is held base_included through D70's doubt and the EGD keeps its own item (46e461e7f: READY
        beside 43259 and alone; c2e53f8e: held base_included)."""
        inv, text = gap1(RFA_AFTER, rfa(time=a('current_encounter', 'After the EGD', ['P3'])), (INSULINOMA,))
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            event = reading.events['E2']
            self.assertEqual((event['time']['state'], events.done(event), coverage.possibly_current(event)),
                             ('unverified', False, True))
            self.assertEqual([item['id'] for item in coverage.possible_eus_acts(reading)], ['E2'])
        with self.subTest(part='structure'):
            sessions = coverage.sessions(reading)
            self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
        with self.subTest(part='assess'):  # the EUS session has no done event, so 43259 is matched to none
            held_beside(self, run(inv, text, [('43235', UPPER_Q), ('43259', RFA_AFTER)]), '43235', (), SEPARATELY)
        with self.subTest(part='alone'):
            held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)
        with self.subTest(part='items'):
            self.assertEqual(egd_item(run(inv, text, [])), ('no_proposal', True))

    def test_d135_control_the_same_biopsy_beside_an_eus_examination(self):
        """The problem's control: an EUS examination event (E3) beside the biopsy is the session, as before (all three
        engines hold 43235)."""
        found = [exam('E1', 'P2', words='gastroscope', procedure=a('egd', 'UPPER ENDOSCOPY', ['P1'])), ttnb(),
                 act('E3', 'P3', 'examination', 'EUS', status_words='was performed', procedure=a('eus', 'EUS', ['P3']))]
        inv, text = inventory({'P1': REPORT, 'P2': UPPER, 'P3': TTNB}, events=found, lesions=[CYST],
                              reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2')])
        with self.subTest(part='structure'):
            self.assertEqual(sessions_of(inv)['gi.eus'].event, 'E3')
            self.assertEqual(sessions_of(inv)['gi.egd'].part_of, 'gi.eus')
        with self.subTest(part='assess'):
            held_beside(self, run(inv, text, [('43235', UPPER_Q), ('43242', TTNB)]), '43235', ('43242',),
                        beside('43242'))
        with self.subTest(part='alone'):
            held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)


RECTAL_OTHER = 'EUS-guided injection of the rectal varix was performed.'
UNSETTLED_COIL = 'Coil embolization of the gastric fundal varix was performed.'
PLAIN_TTNB = 'Through-the-needle microforceps biopsy of the 3 cm cyst in the pancreatic body was performed.'
DRE_LINE = 'EUS: digital rectal examination showed brown stool and no palpable mass.'


class AnActOfAnyKindIsADoubtWhereItIsInDoubt(SimpleTestCase):
    """D135's siblings: an act-only session's own act of no EUS kind placed lower, and an act of no catalogue kind whose
    procedure is unsettled - each a doubt, never a fact."""

    def test_d135_an_act_of_no_eus_kind_placed_lower_is_a_doubt_about_the_eus(self):
        """'EUS-guided injection of the rectal varix was performed.' read as 'other' at the rectum: no lower evidence
        (D96), so placed lower it makes C-4's upper reading a doubt - the EGD keeps its own item and 43235 is held, as
        c2e53f8e holds it (base_included) and lists both no_proposal items; read as the fact, the EGD would have been
        the EUS's endoscopic portion and its own item dropped."""
        other = act('E2', 'P3', 'other', 'injection of the rectal varix', status_words='was performed',
                    procedure=a('eus', 'EUS-guided', ['P3']), target=tg('', 'rectum', 'the rectal varix', ['P3']))
        inv, text = gap1(RECTAL_OTHER, other)
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            event = reading.events['E2']
            self.assertEqual((event['catalogue_kind'], mapping.target_landmark(event), coverage.eus_guided_act(event)),
                             ('', 'rectum', True))
            self.assertEqual((lower_ids(inv), coverage.doubted_eus_acts(reading)), ([], []))
        with self.subTest(part='structure'):
            sessions = coverage.sessions(reading)
            self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
        with self.subTest(part='assess'):  # 46e461e7f: READY
            held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)
        with self.subTest(part='items'):
            self.assertEqual(items(run(inv, text, [])),
                             [('gi.egd', 'no_proposal', True), ('gi.eus', 'no_proposal', True)])

    def test_d135_an_act_of_no_kind_whose_procedure_is_unsettled_is_a_possible_upper_eus(self):
        """The coil filed under 'eus' with no procedure words beside the EGD (procedure_unsettled): its family is in
        doubt (D87), so it is a possible upper EUS of every kind (D123's upper doubts, D135) - 43235 held through D70's
        doubt, the EGD keeping its item (46e461e7f and c2e53f8e: READY; a cost, recorded in D135)."""
        unsettled = act('E2', 'P3', 'other', 'Coil embolization', status_words='was performed', procedure=a('eus'),
                        target=tg('', 'gastric_fundus', 'the gastric fundal varix', ['P3']))
        inv, text = gap1(UNSETTLED_COIL, unsettled)
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            event = reading.events['E2']
            self.assertEqual((event['catalogue_kind'], event['procedure']['state'], events.done(event),
                              coverage.eus_guided_act(event)), ('', 'unverified', True, False))
            self.assertEqual(coverage.doubted_eus_acts(reading), [])
            self.assertEqual([item['id'] for item in coverage.doubted_eus_acts(reading, unnamed=True)], ['E2'])
        with self.subTest(part='structure'):
            sessions = coverage.sessions(reading)
            self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
        with self.subTest(part='assess'):
            held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)
        with self.subTest(part='items'):
            self.assertEqual(egd_item(run(inv, text, [])), ('no_proposal', True))

    def test_d135_a_doubted_act_of_no_eus_kind_is_a_possible_upper_eus(self):
        """D123's upper doubts take every kind (D135): the microforceps biopsy whose kind words do not locate ('tissue
        acquisition'), or filed under 'eus' with no procedure words, is a doubted act - a possible upper EUS, never the
        session: 43235 held through D70's doubt, the EGD keeping its own item (46e461e7f: READY, its upper doubts
        EUS_ACTS kinds alone; c2e53f8e: held base_included)."""
        unlocated = act('E2', 'P3', 'biopsy', 'tissue acquisition', status_words='was performed',
                        procedure=a('eus', 'EUS-guided', ['P3']), technique=a('forceps', 'microforceps', ['P3']),
                        target=tg('L1', 'pancreas', 'the 3 cm cyst in the pancreatic body', ['P3']))
        unsettled = act('E2', 'P3', 'biopsy', 'microforceps biopsy', status_words='was performed', procedure=a('eus'),
                        technique=a('forceps', 'microforceps', ['P3']),
                        target=tg('L1', 'pancreas', 'the 3 cm cyst in the pancreatic body', ['P3']))
        for name, (line, found_act, unusable) in {'kind_unlocated': (TTNB, unlocated, 'kind'),
                                                  'procedure_unsettled': (PLAIN_TTNB, unsettled, 'procedure')}.items():
            inv, text = gap1(line, found_act, (CYST,))
            reading = events.Reading.of(inv)
            with self.subTest(case=name, part='fixture'):
                event = reading.events['E2']
                self.assertEqual((events.done(event), events.usable(event, unusable), coverage.eus_guided_act(event)),
                                 (True, False, False))
                self.assertEqual([item['id'] for item in coverage.doubted_eus_acts(reading)], ['E2'])
            with self.subTest(case=name, part='structure'):
                sessions = coverage.sessions(reading)
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
            with self.subTest(case=name, part='assess'):  # 46e461e7f: READY
                held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)
            with self.subTest(case=name, part='items'):
                self.assertEqual(egd_item(run(inv, text, [])), ('no_proposal', True))

    def test_d135_control_an_examination_filed_under_the_eus_is_no_act(self):
        """A digital rectal examination filed under the EUS (FINAL 5.6 E13), with no EUS examination or act, is no
        EUS-guided act: the EGD is a service of its own and 43235 is READY, as on 46e461e7f and c2e53f8e."""
        dre = act('E2', 'P3', 'examination', 'digital rectal examination', status_words='showed',
                  procedure=a('eus', 'EUS', ['P3']), technique=a('manual', 'digital', ['P3']),
                  target=tg('', 'rectum', 'rectal', ['P3']))
        inv, text = gap1(DRE_LINE, dre)
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            event = reading.events['E2']
            self.assertEqual((event['catalogue_kind'], events.done(event), coverage.eus_guided_act(event)),
                             ('eus_exam', True, False))
        with self.subTest(part='structure'):
            sessions = coverage.sessions(reading)
            self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', ''))
        with self.subTest(part='assess'):
            ready_unheld(self, run(inv, text, [('43235', UPPER_Q)]), '43235')


# --- D136 (problem 1): 43240's defining target, read by the engine ----------------------------------------------------

GB = {'P1': 'Procedure: EUS-guided gallbladder drainage.',
      'P2': 'The linear echoendoscope was advanced to the duodenal bulb.',
      'P3': 'The gallbladder was distended with sludge and a thickened wall, consistent with acute cholecystitis.',
      'P4': 'EUS-guided transmural drainage of the gallbladder was performed from the duodenal bulb with a 15 mm '
            'lumen-apposing metal stent.'}


def gallbladder(examination_target=None):
    """Problem 1's input (audit b3 g1_gallbladder_43240): the EUS examination to the duodenal bulb (E1) and the
    transmural drainage of the gallbladder (E2), its target verified at the gallbladder - with ``examination_target``,
    the examination's own target too."""
    options = {'target': examination_target} if examination_target is not None else {}
    found = [act('E1', 'P2', 'examination', 'linear echoendoscope', status_words='was advanced',
                 procedure=a('eus', 'EUS-guided', ['P1']), technique=a('endoscope', 'linear echoendoscope', ['P2']),
                 **options),
             act('E2', 'P4', 'drainage', 'transmural drainage', status_words='was performed',
                 procedure=a('eus', 'EUS-guided', ['P4']), technique=a('stent', 'lumen-apposing metal stent', ['P4']),
                 target=tg('', 'gallbladder', 'the gallbladder', ['P4']))]
    return inventory(GB, events=found, reach=[reached('E1', 'duodenal_bulb', 'duodenal bulb', 'P2')])


def held_on_the_drainage(test, result, facts: list) -> None:
    """43240 is held, never READY, at assess time and in the read-time overlay, as a positive candidate: the drainage
    (E2) supports nothing, and the question CPT Studio asks of it quotes its own words."""
    p = proposal(result, '43240')
    test.assertEqual((p.status, asked(p), p.support['reason']), ('needs_clarification', facts, events.UNVERIFIED))
    test.assertEqual((p.support['acts'], p.support['question_events']), ([], ['E2']))
    test.assertIn('(“was performed”)', p.clarifications[0].question)
    view = reviewed(result, '43240')
    test.assertEqual((view.status, view.released), ('needs_clarification', ()))


class TheDefiningTargetIsRead(SimpleTestCase):
    """D136 (problem 1, critical): c2e53f8e holds every 43240 [performed_status, target]; 46e461e7f READYs it on a
    drainage of any target, with coding complete_pending_review."""

    def test_d136_a_drainage_of_the_gallbladder_never_supports_43240(self):
        inv, text = gallbladder()
        reading = events.Reading.of(inv)
        link = mapping.code_link('43240')
        with self.subTest(part='fixture'):
            drainage = reading.events['E2']
            self.assertEqual((mapping.target_landmark(drainage), events.defining_fit(reading, link, drainage)),
                             ('gallbladder', False))
            self.assertFalse(events.supports(reading, link, ('drainage',), drainage))
        result = run(inv, text, [('43240', GB['P4'])])
        with self.subTest(part='assess'):  # 46e461e7f: READY
            held_on_the_drainage(self, result, ['performed_status', 'target'])
        with self.subTest(part='completeness'):
            self.assertEqual(result.completeness['state'], 'incomplete')

    def test_d136_a_drainage_of_a_bile_duct_or_a_liver_abscess_never_supports_43240(self):
        for name in ('bile_duct', 'hepatic_duct', 'liver_abscess'):
            inv, text = drainage_case(name)
            with self.subTest(target=name):  # 46e461e7f: READY
                held_on_the_drainage(self, run(inv, text, [('43240', DRAINAGE_LINES[name])]),
                                     ['performed_status', 'target'])

    def test_d136_a_drainage_whose_target_is_not_verified_holds_43240(self):
        """'the walled-off necrosis' with no lesion: its target is not verified, so it meets no requirement (46e461e7f
        held it on the target fact alone, supported)."""
        inv, text = drainage_case('necrosis', with_lesion=False)
        with self.subTest(part='fixture'):
            self.assertEqual(events.Reading.of(inv).events['E2']['target']['state'], 'unverified')
        held_on_the_drainage(self, run(inv, text, [('43240', DRAINAGE_LINES['necrosis'])]),
                             ['performed_status', 'target'])

    def test_d136_the_examinations_own_target_never_releases_it(self):
        """With the examination's target verified at the gallbladder the structure examined is documented, and 43240 is
        still held on its drainage (performed_status)."""
        inv, text = gallbladder(tg('', 'gallbladder', 'the gallbladder', ['P3']))
        held_on_the_drainage(self, run(inv, text, [('43240', GB['P4'])]), ['performed_status'])

    def test_d136_controls_a_pancreatic_fluid_collection_supports_43240(self):
        """A verified pseudocyst, walled-off necrosis, or a lesion verified to be a pseudocyst: READY, as at 46e461e7f.
        c2e53f8e holds every 43240 (D27's recorded difference, FINAL 7.3)."""
        for name in ('pseudocyst', 'necrosis', 'by_lesion'):
            inv, text = drainage_case(name)
            result = run(inv, text, [('43240', DRAINAGE_LINES[name])])
            with self.subTest(target=name):
                p = proposal(result, '43240')
                self.assertEqual((p.status, asked(p), [item['id'] for item in p.support['acts']]),
                                 ('ready', [], ['E2']))
                self.assertEqual(reviewed(result, '43240').status, 'ready')

    def test_d136_every_other_code_has_no_defining_target(self):
        inv, _ = gallbladder()
        reading = events.Reading.of(inv)
        for code in ('43242', '43253', '43259', '43235', '43237'):
            with self.subTest(code=code):
                self.assertTrue(events.defining_fit(reading, mapping.code_link(code), reading.events['E2']))


# --- D137 (problem 2): an examination-only EUS code beside an EUS-guided act no EUS code accounts for -----------------

GE = {'P1': 'Procedure: EUS-guided gastroenterostomy.',
      'P2': 'The linear echoendoscope was advanced to the second portion of the duodenum.',
      'P3': 'The pancreatic head mass causing the duodenal obstruction was examined.',
      'P4': 'From the gastric body, a 20 mm lumen-apposing metal stent was deployed into a distended jejunal loop.'}
MASS = les('L1', 'pancreatic head mass', 'P3', landmark='pancreas', site_words='pancreatic head')


def examination() -> dict:
    """Problem 2's E1: the EUS examination to D2, its target the pancreatic head mass (L1)."""
    return act('E1', 'P2', 'examination', 'linear echoendoscope', status_words='was advanced',
               procedure=a('eus', 'EUS-guided', ['P1']), technique=a('endoscope', 'linear echoendoscope', ['P2']),
               target=tg('L1', 'pancreas', 'The pancreatic head mass', ['P3']))


def with_examination(lines: dict, *more: dict):
    """Problem 2's shape (audit b3 g4_eusge_stent_43259): the EUS examination (E1) and one EUS-guided act (E2, P4)."""
    return inventory(lines, events=[examination(), *more], lesions=[MASS],
                     reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2')])


def lams() -> dict:
    return act('E2', 'P4', 'stent', 'lumen-apposing metal stent', status_words='was deployed',
               procedure=a('eus', 'EUS-guided', ['P1']), technique=a('stent', 'lumen-apposing metal stent', ['P4']),
               target=tg('', 'jejunum', 'a distended jejunal loop', ['P4']))


COIL_GE = dict(GE, P1='Procedure: EUS-guided coil embolization.', P4=COIL)
RFA_GE = dict(GE, P1='Procedure: EUS-guided radiofrequency ablation.',
              P4='EUS-guided radiofrequency ablation of the pancreatic head mass was performed.')
# name: (lines, the act, the label the base question names)
UNLISTED = {
    'gastroenterostomy_stent': (GE, lams, 'stent placement'),
    'coil_embolization': (COIL_GE, lambda: act('E2', 'P4', 'other', 'coil embolization', status_words='was performed',
                                               procedure=a('eus', 'EUS-guided', ['P4']),
                                               target=tg('', 'gastric_fundus', 'the gastric fundal varix', ['P4'])),
                          'coil embolization'),
    'radiofrequency_ablation': (RFA_GE, lambda: act('E2', 'P4', 'ablation', 'radiofrequency ablation',
                                                    status_words='was performed',
                                                    procedure=a('eus', 'EUS-guided', ['P4']),
                                                    technique=a('radiofrequency', 'radiofrequency', ['P4']),
                                                    target=tg('L1', 'pancreas', 'the pancreatic head mass', ['P4'])),
                                'ablation'),
}


def base_question(code: str, label: str) -> str:
    return f'Is {code} reported separately from {label} for this examination?'


class AnExaminationOnlyCodeBesideAnUnlistedEusGuidedAct(SimpleTestCase):
    """D137 (problem 2, critical): c2e53f8e holds 43259 [performed_status, target] on problem 2's input; 46e461e7f
    READYs it with coding complete_pending_review."""

    def test_d137_43259_beside_the_gastroenterostomy_stent_is_held_base_included(self):
        inv, text = with_examination(GE, lams())
        result = run(inv, text, [('43259', GE['P2'])])
        p = proposal(result, '43259')
        with self.subTest(part='assess'):  # 46e461e7f: READY, no question
            self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
            held, spec = combination.base_hold('43259', 'gi.eus', p.key, ('stent placement',), 'endoscopic ultrasound')
            self.assertEqual((check(p, 'services.base_included'), list(p.clarifications)), (held, [spec]))
            self.assertEqual(spec.question, base_question('43259', 'stent placement'))
        with self.subTest(part='overlay'):
            view = reviewed(result, '43259')
            self.assertEqual((view.status, view.released, [q['question'] for q in view.questions]),
                             ('needs_clarification', (), [base_question('43259', 'stent placement')]))
        with self.subTest(part='event_coding'):
            entries = result.completeness['event_coding']['sessions']['gi.eus']['reportable']
            self.assertEqual([(entry['event'], entry['kind'], entry['label']) for entry in entries],
                             [('E2', 'stent', 'stent placement')])
        with self.subTest(part='completeness'):
            self.assertEqual(result.completeness['state'], 'incomplete')

    def test_d137_every_examination_only_code_and_every_unlisted_kind(self):
        """43237 too (its D28 reach question kept), and a coil embolization read as 'other' (labelled by its own kind
        words) and an EUS-guided ablation beside the same examination."""
        for name, (lines, build, label) in UNLISTED.items():
            inv, text = with_examination(lines, build())
            for code in ('43259', '43237'):
                p = proposal(run(inv, text, [(code, lines['P2'])]), code)
                with self.subTest(act=name, code=code):  # 46e461e7f: 43259 READY; 43237 asked its reach alone
                    self.assertEqual(p.status, 'needs_clarification')
                    self.assertEqual([spec.question for spec in p.clarifications if spec.fact == 'base_included'],
                                     [base_question(code, label)])

    def test_d137_an_act_begun_and_not_completed_is_done_too(self):
        """A done act is performed or begun (events.done): the gastroenterostomy's stent 'attempted but failed' holds
        43259 the same way (46e461e7f: READY; c2e53f8e: held)."""
        stent = act('E2', 'P4', 'stent', 'lumen-apposing metal stent', status='attempted_not_completed',
                    status_words='was attempted but failed', procedure=a('eus', 'EUS-guided', ['P1']),
                    technique=a('stent', 'lumen-apposing metal stent', ['P4']),
                    target=tg('', 'jejunum', 'the jejunal loop', ['P4']))
        lines = dict(GE, P4=('Deployment of a 20 mm lumen-apposing metal stent from the gastric body into the jejunal '
                             'loop was attempted but failed.'))
        inv, text = with_examination(lines, stent)
        with self.subTest(part='fixture'):
            event = events.Reading.of(inv).events['E2']
            self.assertEqual((events.value(event, 'status'), events.done(event)), ('attempted_not_completed', True))
        p = proposal(run(inv, text, [('43259', lines['P2'])]), '43259')
        with self.subTest(part='assess'):  # 46e461e7f: READY
            self.assertEqual((p.status, asked(p), [spec.question for spec in p.clarifications]),
                             ('needs_clarification', ['base_included'], [base_question('43259', 'stent placement')]))

    def test_d137_control_a_clip_is_never_an_unlisted_act(self):
        """A clip is never separately reported (catalogue.NOT_REPORTED: bundled_reason), so it is recorded nowhere and
        holds no examination-only code, as on 46e461e7f."""
        clip = act('E2', 'P4', 'clip', 'hemoclip', status_words='was placed', procedure=a('eus', 'EUS', ['P1']),
                   target=tg('', 'duodenum', 'the puncture site', ['P4']))
        lines = dict(GE, P1='Procedure: EUS.', P4='A hemoclip was placed at the puncture site.')
        inv, text = with_examination(lines, clip)
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            self.assertTrue(coverage.eus_guided_act(reading.events['E2']))
            self.assertEqual(coverage.eus_unprofiled_entries(reading, list(reading.events.values())), [])
        p = proposal(run(inv, text, [('43259', lines['P2'])]), '43259')
        with self.subTest(part='assess'):
            self.assertIsNone(check(p, 'services.base_included'))

    def test_d137_controls_a_plain_fna_and_the_examination_alone(self):
        """A plain EUS FNA beside the examination is unchanged (43242 READY, 43259 beside it held as before), and the
        examination alone leaves 43259 READY."""
        fna = act('E2', 'P4', 'fna', 'fine-needle aspiration', status_words='was performed',
                  procedure=a('eus', 'EUS-guided', ['P4']), technique=a('needle', '22-gauge needle', ['P4']),
                  target=tg('L1', 'pancreas', 'the pancreatic head mass', ['P4']))
        lines = dict(GE, P1='Procedure: EUS with fine-needle aspiration.',
                     P4='EUS-guided fine-needle aspiration of the pancreatic head mass was performed with a 22-gauge '
                        'needle.')
        inv, text = with_examination(lines, fna)
        with self.subTest(control='fna'):
            ready_unheld(self, run(inv, text, [('43242', lines['P4'])]), '43242')
            p = proposal(run(inv, text, [('43242', lines['P4']), ('43259', lines['P2'])]), '43259')
            self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
            reading = events.Reading.of(inv)
            self.assertEqual(coverage.eus_unprofiled_entries(reading, list(reading.events.values())), [])
        alone = dict(list(GE.items())[:3])
        inv, text = with_examination(alone)
        with self.subTest(control='examination_alone'):
            ready_unheld(self, run(inv, text, [('43259', GE['P2'])]), '43259')

    def test_d137_an_act_another_code_profile_reads_is_not_recorded(self):
        """A drainage is an act of the EUS's own kinds: it is reportable as before (recorded once), never an unlisted
        act; the base rule reads it already (46e461e7f holds 43259 beside it)."""
        drainage = act('E2', 'P4', 'drainage', 'transmural drainage', status_words='was performed',
                       procedure=a('eus', 'EUS-guided', ['P4']),
                       technique=a('stent', 'lumen-apposing metal stent', ['P4']),
                       target=tg('', 'gallbladder', 'the gallbladder', ['P4']))
        lines = dict(GE, P1='Procedure: EUS-guided gallbladder drainage.',
                     P4='EUS-guided transmural drainage of the gallbladder was performed with a lumen-apposing metal '
                        'stent.')
        inv, text = with_examination(lines, drainage)
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.eus_unprofiled_entries(reading, list(reading.events.values())), [])
        result = run(inv, text, [('43259', lines['P2'])])
        entries = result.completeness['event_coding']['sessions']['gi.eus']['reportable']
        self.assertEqual([(entry['event'], entry['kind']) for entry in entries], [('E2', 'drainage')])
        self.assertEqual([spec.question for spec in proposal(result, '43259').clarifications
                          if spec.fact == 'base_included'], [base_question('43259', 'drainage')])


# --- D138 (problem 3): an act verified as another clinician's is no possible upper EUS ------------------------------

OTHER_PERFORMER = ('EUS-FNA of a 22 mm hypoechoic mass in the pancreatic body was performed by Dr. Lena Ortiz '
                   '(fictional) of the advanced endoscopy service.')
BODY_MASS = les('L1', '22 mm hypoechoic mass', 'P3', landmark='pancreas', site_words='pancreatic body',
                size_words='22 mm')


def other_clinicians_fna(named: bool = True):
    """Problem 3's input: gap 1's document with the FNA performed by another named clinician - verified with the
    documenting endoscopist named (Ana Ruiz, P9), unverified without (the control)."""
    fna = act('E2', 'P3', 'fna', 'EUS-FNA', status_words='was performed', procedure=a('eus', 'EUS-FNA', ['P3']),
              performer=a('other_clinician', 'Dr. Lena Ortiz (fictional)', ['P3']),
              target=tg('L1', 'pancreas', 'a 22 mm hypoechoic mass in the pancreatic body', ['P3']))
    return gap1(OTHER_PERFORMER, fna, (BODY_MASS,), named=named)


class AnotherCliniciansActIsNoPossibleUpperEus(SimpleTestCase):
    """D138 (problem 3): 1caaf0609 held 43235 base_included beside 43242 and alone; d353e64df and c2e53f8e are READY."""

    def test_d138_43235_is_ready_beside_another_clinicians_fna(self):
        inv, text = other_clinicians_fna()
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            fna = reading.events['E2']
            self.assertEqual((events.verified_other_performer(fna), events.done(fna), coverage.possibly_current(fna)),
                             (True, False, True))
            self.assertEqual(coverage.possible_eus_acts(reading), [])
        with self.subTest(part='structure'):
            sessions = coverage.sessions(reading)
            self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', ''))
        with self.subTest(part='beside_43242'):  # 46e461e7f: held base_included
            ready_unheld(self, run(inv, text, [('43235', UPPER_Q), ('43242', OTHER_PERFORMER)]), '43235')
        with self.subTest(part='alone'):
            ready_unheld(self, run(inv, text, [('43235', UPPER_Q)]), '43235')

    def test_d138_control_a_performer_not_verified_is_still_a_doubt(self):
        """Without the documenting endoscopist named, the other performer is not verified: the FNA may be this
        encounter's own, so it stays a possible upper EUS (D62) and 43235 stays held (c2e53f8e: READY; D62's recorded
        cost)."""
        inv, text = other_clinicians_fna(named=False)
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            self.assertFalse(events.verified_other_performer(reading.events['E2']))
            self.assertEqual([item['id'] for item in coverage.possible_eus_acts(reading)], ['E2'])
        with self.subTest(part='assess'):
            held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)
