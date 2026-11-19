"""DECISIONS D171 (the Gemini migration's round 5g, narrowing only: refute6 families findings 4 and 5, judges findings 11,
12 and 13), SYNTHETIC, each built from its source's own input (refute6/eus/cases cases_b2.py and cases_b3.py,
refute6/verify-eus-0's and verify-eus-1's own constructions, refute6/gate-eus/cases cases_w5, w6 and w7, and the
committed FRESH-2 recordings of fb12 and fb14 with the one line those lenses edited). Nothing is sent.
- (1) families finding 4: an FNA that is a STEP of a transmural drainage (its part_of names the drainage, or it is of the
  drainage's own verified lesion) holds 43242 [target], as c2e53f8e holds it - never READY beside 43240 on the same
  lesion; an FNA of another lesion stays READY. Recorded stop: the aspiration is NOT bundled into the drainage for
  coverage (bundled_reason), which would drop its not_covered listing where 43240 is proposed alone.
- (2) families finding 5: an upper endoscopy's EUS code on a lower-tract EUS (a rectal or sigmoid reach, an act it
  stands on placed in the rectum) is held [extent]; an upper EUS's codes are not, whatever act Gemini files beside it.
  Recorded stop: 45341's base question beside 43253 is combination.base_included's and is unchanged.
- (3) judges findings 11 and 13: 43259 and 43242 need the esophagus, the stomach and the duodenum examined - a station
  line naming one station only, or an examination of the session stated not performed at a station, holds them
  [extent]; the limited codes' question (43237, 43238) states CPT's class.
- (4) judges finding 12: 43253, the EUS-guided TRANSMURAL injection, is held [target] on a submucosal injection or an
  ink tattoo made through the echoendoscope; 43236's hold stays.
Each test asserts in independent subtests, labelled by what each varies, so a regression shows every one it breaks."""
from __future__ import annotations

import copy
import json

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.interpretation import assess, mapping, normalize, wording
from tests.test_interpretation_events import asked, check, proposal, run
from tests.test_interpretation_identity import accepted
from tests.test_interpretation_r3_integration_d88_d93 import reviewed
from tests.test_interpretation_replay import FIXTURES, MANIFEST

DATE_LINE = 'Date of service: 11/09/2026.'
EUS_ACT_CHECK = 'facts.eus_act'
CLASS_CHECK = 'facts.examination_class'
HELD = 'needs_clarification'


def a(value, words='', passages=()):
    return {'value': value, 'words': words, 'passages': list(passages)}


def tg(lesion='', landmark='not_stated', words='', passages=()):
    return {'lesion': lesion, 'landmark': landmark, 'words': words, 'passages': list(passages)}


def sc(value='not_applicable', words='', passages=(), targets=()):
    return {'value': value, 'targets': list(targets), 'words': words, 'passages': list(passages)}


def ev(eid, passage, kind, kind_words, *, procedure, status='performed', status_words='', technique=None, target=None,
       time=None, purpose=None, part_of='', sequence=0, scope=None):
    """refute6/eus cases_b1.ev: an event of ``kind`` stated in ``passage``, of this encounter by the documenting team."""
    return {'id': eid, 'procedure': procedure, 'kind': a(kind, kind_words, [passage]),
            'technique': technique or a('not_stated'), 'target': target or tg(), 'time': time or a('current_encounter'),
            'performer': a('documenting_team'), 'status': a(status, status_words or kind_words, [passage]),
            'scope': scope or sc(), 'purpose': purpose or a('not_stated'), 'part_of': part_of, 'sequence': sequence,
            'contradicts': []}


def les(lid, words, passages, landmark='not_stated', site_words='', size_words='', multiplicity='single'):
    return {'id': lid, 'words': words, 'landmark': landmark, 'site_words': site_words, 'size_words': size_words,
            'multiplicity': multiplicity, 'passages': list(passages)}


def reach(eid, landmark, words, passage, completion=None):
    return {'event': eid, 'landmark': landmark, 'words': words, 'passages': [passage],
            'completion': completion or a('not_stated')}


def answer(lines, events, lesions=(), reach_=(), endoscopist=None, date_line=DATE_LINE):
    """refute6/eus cases_b1.answer: the raw answer over DATE_LINE (P0) then ``lines``, and the document's text."""
    passages = {'P0': date_line, **lines}
    enc = {'date_of_service': {'value': '2026-11-09', 'state': 'stated', 'words': '11/09/2026', 'passages': ['P0'],
                               'other_dates': []},
           'documenting_endoscopist': endoscopist or {'words': '', 'passages': []}, 'team': [], 'anatomy': [],
           'reach': list(reach_), 'visit_facts': []}
    value = {'passages': [{'id': pid, 'text': text} for pid, text in passages.items()], 'encounter': enc,
             'lesions': list(lesions), 'events': list(events), 'open_questions': []}
    return value, '\n'.join(passages.values()) + '\n'


def inv_of(value, text):
    return normalize.normalize(accepted(value), text), text


def outcome(p) -> tuple:
    return (p.status, asked(p), [item['id'] for item in p.support.get('acts') or ()])


ENDO = {'words': 'Ana Ruiz, MD (fictional)', 'passages': ['P2']}

# --- (1) the drainage's step: refute6/eus cases_b2 F1 (families finding 4's input) -------------------------------------
F1_LINES = {
    'P1': 'UPPER ENDOSCOPIC ULTRASOUND (EUS) REPORT',
    'P2': 'Endoscopist: Ana Ruiz, MD (fictional)',
    'P3': 'Indication: Symptomatic 9 cm pancreatic pseudocyst after acute pancreatitis; drainage requested.',
    'P4': 'Procedure: The linear echoendoscope was advanced to the second portion of the duodenum.',
    'P5': 'EUS imaging was performed from the esophagus, stomach and duodenum.',
    'P6': ('EUS findings: a 9 cm unilocular pancreatic pseudocyst abutting the posterior gastric wall, without solid '
           'debris.'),
    'P7': ('Under EUS guidance, the pseudocyst was punctured from the gastric body with a 19-gauge needle and 20 mL of '
           'clear fluid was aspirated and sent for amylase and CEA.'),
    'P8': 'A 0.035-inch guidewire was coiled within the pseudocyst.',
    'P9': 'EUS-guided transmural drainage of the pseudocyst was then performed with a 15 mm lumen-apposing metal stent.',
    'P10': 'Impression: 9 cm pancreatic pseudocyst, drained transgastrically with a lumen-apposing metal stent.',
    'P11': 'Plan: Clear liquids today; CT in 4 weeks.',
}
F1_PC = les('L1', 'a 9 cm unilocular pancreatic pseudocyst', ['P6', 'P10'], landmark='pancreas', site_words='pancreatic',
            size_words='9 cm')
F1_EXAM = ev('E1', 'P5', 'examination', 'EUS imaging', procedure=a('eus', 'UPPER ENDOSCOPIC ULTRASOUND (EUS)', ['P1']),
             status_words='was performed', technique=a('endoscope', 'linear echoendoscope', ['P4']))
F1_REACH = reach('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P4')


def f1_drainage(status='performed', status_words='was then performed', time=None, lesion='L1'):
    return ev('E3', 'P9', 'drainage', 'transmural drainage', procedure=a('eus', 'EUS-guided', ['P9']), status=status,
              status_words=status_words, technique=a('stent', 'lumen-apposing metal stent', ['P9']),
              target=tg(lesion, 'pancreas', 'the pseudocyst', ['P9']), sequence=2, time=time)


def f1(part_of='E3', target_lesion='L1', lines=None, fna_words=('aspirated', 'was aspirated', 'Under EUS guidance'),
       drainage=None):
    """cases_b2.f1 (F1: part_of E3; F1b: part_of ''), its wording twin (verify-eus-0's F1w) and the twins below."""
    kind_words, status_words, procedure_words = fna_words
    fna = ev('E2', 'P7', 'fna', kind_words, procedure=a('eus', procedure_words, ['P7']), status_words=status_words,
             technique=a('needle', '19-gauge needle', ['P7']),
             target=tg(target_lesion, 'pancreas', 'the pseudocyst', ['P7']),
             purpose=a('diagnostic', 'sent for amylase and CEA', ['P7']), part_of=part_of, sequence=1)
    value, text = answer(lines or F1_LINES, [F1_EXAM, fna, drainage or f1_drainage()], [F1_PC], reach_=[F1_REACH],
                         endoscopist=ENDO)
    return inv_of(value, text)


F1W_LINES = dict(F1_LINES, P7=('EUS-guided fine-needle aspiration of the pseudocyst was performed with a 19-gauge needle '
                               'and 20 mL of clear fluid was sent for amylase and CEA.'))
F1W_WORDS = ('fine-needle aspiration', 'was performed', 'EUS-guided')
F1C_LINES = dict(F1_LINES,
                 P6=('EUS findings: a 9 cm unilocular pancreatic pseudocyst abutting the posterior gastric wall, and a '
                     'separate 18 mm hypoechoic mass in the pancreatic tail.'),
                 P7=('EUS-guided fine-needle aspiration of the pancreatic tail mass was performed with a 22-gauge needle, '
                     '3 passes.'))


def f1_control():
    """cases_b2.f1_control (F1c): the FNA of ANOTHER lesion (a pancreatic tail mass) beside the pseudocyst's drainage."""
    mass = les('L2', 'a separate 18 mm hypoechoic mass in the pancreatic tail', ['P6'], landmark='pancreas',
               site_words='pancreatic tail', size_words='18 mm')
    fna = ev('E2', 'P7', 'fna', 'fine-needle aspiration', procedure=a('eus', 'EUS-guided', ['P7']),
             status_words='was performed', technique=a('needle', '22-gauge needle', ['P7']),
             target=tg('L2', 'pancreas', 'the pancreatic tail mass', ['P7']))
    drain = ev('E3', 'P9', 'drainage', 'transmural drainage', procedure=a('eus', 'EUS-guided', ['P9']),
               status_words='was then performed', technique=a('stent', 'lumen-apposing metal stent', ['P9']),
               target=tg('L1', 'pancreas', 'the pseudocyst', ['P9']))
    value, text = answer(F1C_LINES, [F1_EXAM, fna, drain], [F1_PC, mass], reach_=[F1_REACH], endoscopist=ENDO)
    return inv_of(value, text)


STEP_Q = ('Was the fine-needle aspiration (“Under EUS guidance, the pseudocyst was punctured from the gastric body with a '
          '19-gauge needle and 20 mL of clear fluid was aspirated and sent for amylase and CEA.”) a separate sampling, '
          'or a step of the transmural drainage (“EUS-guided transmural drainage of the pseudocyst was then performed '
          'with a 15 mm lumen-apposing metal stent.”)?')


class AStepOfTheDrainageHolds43242(SimpleTestCase):
    """D171 (1): head 05a881a75, f9013e12e and e5628be56 READY 43242 beside 43240 READY (coding complete) and alone;
    c2e53f8e holds 43242 [target] and 43240 [performed_status, target]."""

    def assert_step(self, result, question=STEP_Q):
        p = proposal(result, '43242')
        self.assertEqual(outcome(p), (HELD, ['target'], ['E2']))
        self.assertEqual((p.clarifications[0].question, check(p, EUS_ACT_CHECK).status), (question, 'warn'))
        self.assertIn('as a step of the transmural drainage of the same structure', p.clarifications[0].reason)
        view = reviewed(result, '43242')
        self.assertEqual((view.status, view.released), (HELD, ()))

    def test_d171_the_aspiration_gemini_gives_as_the_drainages_step_holds_43242(self):
        """Families finding 4's own input (F1, part_of E3): beside 43240, alone, and beside 43240 and 43259."""
        inv, text = f1()
        for label, picks in (('beside 43240', [('43240', F1_LINES['P9']), ('43242', F1_LINES['P7'])]),
                             ('alone', [('43242', F1_LINES['P7'])]),
                             ('beside 43240 and 43259', [('43240', F1_LINES['P9']), ('43242', F1_LINES['P7']),
                                                         ('43259', F1_LINES['P5'])])):
            result = run(inv, text, picks)
            with self.subTest(picks=label):
                self.assert_step(result)
                if '43240' in dict(picks):
                    self.assertEqual(outcome(proposal(result, '43240')), ('ready', [], ['E3']))  # D27's, unchanged
                    self.assertNotEqual(result.completeness['state'], 'complete_pending_review')

    def test_d171_the_same_lesions_aspiration_with_no_part_of_holds_43242(self):
        """F1b (part_of '') and verify-eus-0's F1w twins ('EUS-guided fine-needle aspiration of the pseudocyst ...'),
        with and without the part_of: the aspiration of the drainage's own verified lesion is its access step."""
        for label, (inv, text), lines in (('F1b', f1(part_of=''), F1_LINES),
                                          ('F1w part_of', f1(lines=F1W_LINES, fna_words=F1W_WORDS), F1W_LINES),
                                          ('F1w no part_of', f1('', lines=F1W_LINES, fna_words=F1W_WORDS), F1W_LINES)):
            for picks in ([('43240', lines['P9']), ('43242', lines['P7'])], [('43242', lines['P7'])]):
                with self.subTest(case=label, codes=[code for code, _ in picks]):
                    p = proposal(run(inv, text, picks), '43242')
                    self.assertEqual(outcome(p), (HELD, ['target'], ['E2']))
                    self.assertEqual(check(p, EUS_ACT_CHECK).status, 'warn')

    def test_d171_control_an_fna_of_another_lesion_stays_ready(self):
        """F1c (the spec's control): both codes are right, and both stay READY, as on every head (c2e53f8e READY 43242)."""
        inv, text = f1_control()
        result = run(inv, text, [('43240', F1C_LINES['P9']), ('43242', F1C_LINES['P7'])])
        self.assertEqual(outcome(proposal(result, '43242')), ('ready', [], ['E2']))
        self.assertEqual(outcome(proposal(result, '43240')), ('ready', [], ['E3']))
        self.assertIsNone(check(proposal(result, '43242'), EUS_ACT_CHECK))

    def test_d171_a_drainage_begun_or_only_possibly_current_is_still_its_whole(self):
        """Mine: the drainage attempted and failed (adjunct_whole), or told 'Later, ...' (its time unanchored, D62)."""
        attempted = f1_drainage('attempted_not_completed', 'was then attempted but the stent could not be deployed')
        later = f1_drainage(status_words='was performed', time=a('current_encounter', 'Later', ['P9']))
        for label, drain, p9 in (
                ('attempted', attempted, 'EUS-guided transmural drainage of the pseudocyst was then attempted but the '
                                         'stent could not be deployed.'),
                ('later', later, 'Later, EUS-guided transmural drainage of the pseudocyst was performed with a 15 mm '
                                 'lumen-apposing metal stent.')):
            lines = dict(F1_LINES, P9=p9)
            inv, text = f1(part_of='', lines=lines, drainage=drain)
            with self.subTest(drainage=label):
                p = proposal(run(inv, text, [('43242', lines['P7'])]), '43242')
                self.assertEqual(outcome(p)[:2], (HELD, ['target']))

    def test_d171_controls_another_occasions_drainage_and_none(self):
        """Mine: the drainage verified at another occasion, and no drainage at all: 43242 READY, as on the head."""
        other = dict(F1_LINES, P9=('At her index EUS on 01/14/2024, transmural drainage of the pseudocyst was performed '
                                   'with a 15 mm lumen-apposing metal stent.'))
        drain = f1_drainage(status_words='was performed',
                            time=a('earlier_encounter', 'At her index EUS on 01/14/2024', ['P9']))
        inv, text = f1(part_of='', lines=other, drainage=drain)
        with self.subTest(control='another occasion'):
            self.assertEqual(outcome(proposal(run(inv, text, [('43242', other['P7'])]), '43242')), ('ready', [], ['E2']))
        none = dict(F1_LINES, P8='No drainage was performed; the cyst will be re-imaged in 3 months.')
        del none['P9']
        fna = ev('E2', 'P7', 'fna', 'aspirated', procedure=a('eus', 'Under EUS guidance', ['P7']),
                 status_words='was aspirated', technique=a('needle', '19-gauge needle', ['P7']),
                 target=tg('L1', 'pancreas', 'the pseudocyst', ['P7']),
                 purpose=a('diagnostic', 'sent for amylase and CEA', ['P7']), sequence=1)
        inv, text = inv_of(*answer(none, [F1_EXAM, fna], [F1_PC], reach_=[F1_REACH], endoscopist=ENDO))
        with self.subTest(control='no drainage'):
            self.assertEqual(outcome(proposal(run(inv, text, [('43242', none['P7'])]), '43242')), ('ready', [], ['E2']))

    def test_d171_the_part_of_alone_makes_a_step(self):
        """Mine: Gemini's part_of names the drainage, whose own target it ties to no lesion (so the lesions do not meet):
        held by the part_of arm alone."""
        inv, text = f1(drainage=f1_drainage(lesion=''))
        p = proposal(run(inv, text, [('43242', F1_LINES['P7'])]), '43242')
        self.assertEqual(outcome(p), (HELD, ['target'], ['E2']))
        self.assertEqual(check(p, EUS_ACT_CHECK).status, 'warn')

    def test_d171_no_second_target_question_where_r6_asks_it(self):
        """verify-eus-0's F1e (the aspiration tied to no lesion, part_of E3): R6 asks the structure examined already, so
        the step adds no second 'target' question - [target], as on the head and c2e53f8e."""
        inv, text = f1(target_lesion='')
        p = proposal(run(inv, text, [('43240', F1_LINES['P9']), ('43242', F1_LINES['P7'])]), '43242')
        self.assertEqual((p.status, asked(p), check(p, EUS_ACT_CHECK)), (HELD, ['target'], None))

    def test_d171_the_aspirations_listing_is_kept_with_43240_alone(self):
        """The recorded stop: with 43240 alone the aspiration is still listed not covered (second review), as on the
        head - bundling it into the drainage (bundled_reason) would drop that listing item, a forbidden move."""
        inv, text = f1()
        result = run(inv, text, [('43240', F1_LINES['P9'])])
        self.assertEqual(outcome(proposal(result, '43240')), ('ready', [], ['E3']))
        self.assertEqual([(item['service'], item['reason'], item['events'], item['second_review'])
                          for item in result.completeness['unresolved_items']],
                         [('gi.eus', 'not_covered', ['E2'], True)])


# --- (2) the tract: refute6/eus cases_b2 F2 (families finding 5's input) and verify-eus-1's twins ----------------------
F2_LINES = {
    'P1': 'RECTAL ENDOSCOPIC ULTRASOUND REPORT',
    'P2': 'Endoscopist: Ana Ruiz, MD (fictional)',
    'P3': 'Indication: Staging of a biopsy-proven rectal adenocarcinoma before chemoradiation.',
    'P4': 'Procedure: The radial echoendoscope was advanced to the sigmoid colon and withdrawn through the rectum.',
    'P5': ('EUS findings: a 3 cm hypoechoic mass in the mid rectum invading the muscularis propria (uT2); no perirectal '
           'lymphadenopathy.'),
    'P6': 'Three gold fiducial markers were then placed into the rectal mass under EUS guidance for radiation planning.',
    'P7': 'Impression: uT2N0 rectal cancer; fiducial markers placed.',
    'P8': 'Plan: Radiation oncology referral.',
}
F2_MASS = les('L1', 'a 3 cm hypoechoic mass in the mid rectum', ['P5'], landmark='rectum', site_words='mid rectum',
              size_words='3 cm')
F2_EXAM = ev('E1', 'P4', 'examination', 'radial echoendoscope', procedure=a('eus', 'RECTAL ENDOSCOPIC ULTRASOUND', ['P1']),
             status_words='was advanced', technique=a('endoscope', 'radial echoendoscope', ['P4']))


def f2(kind='tattoo', with_reach=True, with_exam=True):
    """cases_b2.f2 (F2: the fiducial act read as 'tattoo'; F2b: 'injection'); verify-eus-1's R_tattoo_no_reach (no
    reach); and mine, the act alone (no examination event)."""
    fid = ev('E2', 'P6', kind, 'fiducial markers', procedure=a('eus', 'under EUS guidance', ['P6']),
             status_words='were then placed', target=tg('L1', 'rectum', 'the rectal mass', ['P6']),
             purpose=a('marking', 'for radiation planning', ['P6']))
    value, text = answer(F2_LINES, ([F2_EXAM] if with_exam else []) + [fid], [F2_MASS],
                         reach_=[reach('E1', 'sigmoid_colon', 'sigmoid colon', 'P4')] if with_reach and with_exam else [],
                         endoscopist=ENDO)
    return inv_of(value, text)


U_LINES = {
    'P1': 'UPPER ENDOSCOPIC ULTRASOUND (EUS) REPORT', 'P2': 'Endoscopist: Ana Ruiz, MD (fictional)',
    'P3': 'Indication: Pancreatic head adenocarcinoma; fiducials for stereotactic radiotherapy.',
    'P4': 'Procedure: The linear echoendoscope was advanced to the second portion of the duodenum.',
    'P5': 'EUS findings: a 30 mm hypoechoic mass in the pancreatic head.',
    'P6': 'Three gold fiducial markers were then placed into the pancreatic head mass under EUS guidance.'}


def upper_fiducial(kind='tattoo'):
    """verify-eus-1's U control: an UPPER EUS (reach D2) with fiducial markers placed into a pancreatic head mass."""
    mass = les('L1', 'a 30 mm hypoechoic mass in the pancreatic head', ['P5'], landmark='pancreas',
               site_words='pancreatic head', size_words='30 mm')
    fid = ev('E2', 'P6', kind, 'fiducial markers', procedure=a('eus', 'under EUS guidance', ['P6']),
             status_words='were then placed', target=tg('L1', 'pancreas', 'the pancreatic head mass', ['P6']),
             purpose=a('marking', 'fiducial markers', ['P6']))
    exam = ev('E1', 'P4', 'examination', 'linear echoendoscope', procedure=a('eus', 'UPPER ENDOSCOPIC ULTRASOUND (EUS)',
                                                                               ['P1']),
              status_words='was advanced', technique=a('endoscope', 'linear echoendoscope', ['P4']))
    value, text = answer(U_LINES, [exam, fid], [mass], reach_=[reach('E1', 'second_portion_duodenum',
                                                                     'second portion of the duodenum', 'P4')],
                         endoscopist=ENDO)
    return inv_of(value, text)


class AnUpperEusCodeNeedsAnUpperTractSession(SimpleTestCase):
    """D171 (2): head, f9013e12e and e5628be56 READY 43253 on the rectal EUS's fiducials (coding complete alone);
    c2e53f8e holds it [performed_status, target]."""

    def assert_tract(self, p, place, words):
        self.assertEqual(outcome(p), (HELD, ['extent'], ['E2']))
        self.assertEqual(check(p, CLASS_CHECK).status, 'warn')
        self.assertEqual(p.clarifications[0].question,
                         f'The documented endoscopic ultrasound is placed in the lower tract (the {place}: “{words}”). '
                         f'Was {assess.UPPER_TRACT_WORDS} performed on the date of service?')

    def test_d171_43253_on_a_rectal_eus_is_held(self):
        """Families finding 5's input, both kinds, alone and beside 45341; with no reach (verify-eus-1's
        R_tattoo_no_reach) and with no examination event (mine): the act 43253 stands on is in the rectum."""
        for label, (inv, text) in (('tattoo', f2('tattoo')), ('injection', f2('injection')),
                                   ('no reach', f2('tattoo', with_reach=False)),
                                   ('no examination', f2('tattoo', with_exam=False))):
            for picks in ([('43253', F2_LINES['P6'])], [('45341', F2_LINES['P4']), ('43253', F2_LINES['P6'])]):
                if label == 'no examination' and len(picks) == 2:
                    continue
                result = run(inv, text, picks)
                with self.subTest(case=label, codes=[code for code, _ in picks]):
                    # the act 43253 stands on is read first: in the rectum, wherever the examination reached
                    self.assert_tract(proposal(result, '43253'), 'rectum', 'the rectal mass')
                    view = reviewed(result, '43253')
                    self.assertEqual((view.status, view.released), (HELD, ()))
                    self.assertNotEqual(result.completeness['state'], 'complete_pending_review')

    def test_d171_beside_45341_its_base_hold_is_kept(self):
        """The recorded stop: 45341's base_included hold beside 43253 is combination.base_included's and is unchanged
        (its facts as on the head); the tract hold never removes a question of another code."""
        inv, text = f2('tattoo')
        result = run(inv, text, [('45341', F2_LINES['P4']), ('43253', F2_LINES['P6'])])
        self.assertEqual(asked(proposal(result, '45341')), ['base_included', 'target'])

    def test_d171_controls_an_upper_fiducial_and_the_lower_code(self):
        """verify-eus-1's U control (fiducials into the pancreatic head, reach D2): READY, both kinds; 45341 alone on the
        rectal EUS keeps its own outcome; the class codes keep D28's reading (43242 on the rectal EUS: its reach)."""
        for kind in ('tattoo', 'injection'):
            inv, text = upper_fiducial(kind)
            with self.subTest(control=f'upper fiducial {kind}'):
                self.assertEqual(outcome(proposal(run(inv, text, [('43253', U_LINES['P6'])]), '43253')),
                                 ('ready', [], ['E2']))
        inv, text = f2('tattoo')
        with self.subTest(control='45341 alone'):
            self.assertEqual(asked(proposal(run(inv, text, [('45341', F2_LINES['P4'])]), '45341')),
                             ['base_included', 'target'])

    def test_d171_a_rectal_act_filed_under_an_upper_eus_makes_no_lower_eus(self):
        """D96's settled control (tests.test_interpretation_r4_eus_lower): an upper EUS reaching the duodenum whose FNA
        samples the pancreatic head, beside a colonoscopy whose rectal injection Gemini files under the EUS - 43242
        stays READY (the session's places include the upper tract), and 43235 READY as D96 pins it."""
        from tests.test_interpretation_r4_eus_lower import EGD_2, FNA_2, upper_eus_and_colonoscopy
        inv, text = upper_eus_and_colonoscopy('injection', a('eus', 'EUS', ['P2']))
        result = run(inv, text, [('43235', EGD_2), ('43242', FNA_2)])
        self.assertEqual(outcome(proposal(result, '43242')), ('ready', [], ['E3']))
        self.assertEqual(proposal(result, '43235').status, 'ready')

    def test_d171_the_upper_codes_are_the_catalogues_eus_codes_less_d43s(self):
        eus = {code for code, profile in catalogue.CODES.items() if profile.family == 'gi.eus'}
        self.assertEqual(mapping.UPPER_EUS_CODES, eus - set(mapping.LOWER_EUS_CLASS))
        self.assertEqual({code: mapping.eus_tract(code) for code in ('43253', '43240', '45341', '45392', '43235')},
                         {'43253': 'upper', '43240': 'upper', '45341': 'lower', '45392': 'lower', '43235': ''})
        self.assertEqual(mapping.EGD_LIMITED_EUS_CODES,
                         {code for code in eus if catalogue.CODES[code].exam == 'limited'
                          and 'egd' in catalogue.CODES[code].includes})


# --- (3) the full class's stations: refute6/gate-eus cases_w7 (judges finding 11) and cases_w6 (finding 13) ------------
P1 = 'A linear echoendoscope was advanced to the second portion of the duodenum.'
P2 = 'The pancreatic head was examined; a 2.5 cm hypoechoic mass in the pancreatic head was seen.'
P3 = 'The mass was sampled with a 22-gauge needle, three passes.'
STATIONS = {'full': 'EUS imaging was performed from the esophagus, stomach and duodenum.',
            'duodenum_only': 'EUS imaging was performed from the duodenum only.'}


def w7(station: str, fna: bool):
    """cases_w7.build: worklist rows 33 (no FNA) and 26 (the FNA) with fb12/fb14's station line, cited as fb14 r1 cites
    it (procedure, kind and status), never as the reach."""
    return inv_of(*w7_raw(station, fna))


def w7_raw(station: str, fna: bool, extra=None, denial=None, fna_denied=False):
    """w7's raw answer and text; ``extra`` {pid: line} added after P2; ``denial`` (pid, landmark, words, time): an
    examination stated not performed there; ``fna_denied``: the FNA (E2) stated not performed in ``extra``'s P3."""
    lines = [DATE_LINE, P1, STATIONS[station], P2] + ([P3] if fna else [])
    ids = ['P0', 'P1', 'P5', 'P2'] + (['P3'] if fna else [])
    for pid, line in (extra or {}).items():
        lines.append(line)
        ids.append(pid)
    exam = {'id': 'E1', 'procedure': a('eus', 'EUS', ['P5']), 'kind': a('examination', 'EUS imaging', ['P1', 'P5']),
            'technique': a('endoscope', 'linear echoendoscope', ['P1']),
            'target': {'lesion': '', 'landmark': 'pancreas', 'words': 'pancreatic head', 'passages': ['P2']},
            'time': a('current_encounter'), 'performer': a('documenting_team'),
            'status': a('performed', 'was performed', ['P5']), 'scope': sc(), 'purpose': a('not_stated'), 'part_of': '',
            'sequence': 0, 'contradicts': []}
    events = [exam]
    if fna:
        events.append({'id': 'E2', 'procedure': a('eus'), 'kind': a('fna', 'sampled', ['P3']),
                       'technique': a('needle', '22-gauge needle', ['P3']), 'target': tg(),
                       'time': a('current_encounter'), 'performer': a('documenting_team'),
                       'status': a('performed', 'was sampled with a 22-gauge needle', ['P3']), 'scope': sc(),
                       'purpose': a('not_stated'), 'part_of': '', 'sequence': 0, 'contradicts': []})
    if fna_denied:
        events.append({'id': 'E2', 'procedure': a('eus'), 'kind': a('fna', 'fine-needle aspiration', ['P3']),
                       'technique': a('not_stated'), 'target': tg(), 'time': a('current_encounter'),
                       'performer': a('documenting_team'),
                       'status': a('not_performed', 'No fine-needle aspiration was performed', ['P3']),
                       'scope': sc(), 'purpose': a('not_stated'), 'part_of': '', 'sequence': 0, 'contradicts': []})
    if denial:
        pid, landmark, words, time = denial
        events.append({'id': 'E9', 'procedure': a('eus'), 'kind': a('examination', 'examined', [pid]),
                       'technique': a('not_stated'), 'target': tg('', landmark, words, [pid]), 'time': time,
                       'performer': a('documenting_team'), 'status': a('not_performed', 'was not examined', [pid]),
                       'scope': sc('single_target', words, [pid]), 'purpose': a('not_stated'), 'part_of': '',
                       'sequence': 0, 'contradicts': []})
    value = {'passages': [{'id': i, 'text': t} for i, t in zip(ids, lines)],
             'encounter': {'date_of_service': {'value': '2026-11-09', 'state': 'stated', 'words': '11/09/2026',
                                               'passages': ['P0'], 'other_dates': []},
                           'documenting_endoscopist': {'words': '', 'passages': []}, 'team': [], 'anatomy': [],
                           'reach': [reach('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')],
                           'visit_facts': []},
             'lesions': [], 'events': events, 'open_questions': []}
    return value, '\n'.join(lines) + '\n'


P9_ROW8 = 'The examination was incomplete: the esophagus and the stomach were not examined.'
P9_V1 = 'The esophagus and the stomach were not examined.'


def w6(p9: str, denials: bool, completion=None):
    """cases_w6.answer: worklist row 8's document (R8_*) and V1's (P9 without 'incomplete'); ``denials``: the two
    not_performed examination events the contract asks for (fb07 E3's attested shape)."""
    def event(eid, kind_words, kind_pass, status, status_words, status_pass, target, scope=None, technique=None):
        return {'id': eid, 'procedure': a('eus'), 'kind': a('examination', kind_words, kind_pass),
                'technique': technique or a('not_stated'), 'target': target, 'time': a('current_encounter'),
                'performer': a('documenting_team'), 'status': a(status, status_words, status_pass),
                'scope': scope or sc(), 'purpose': a('not_stated'), 'part_of': '', 'sequence': 0, 'contradicts': []}

    events = [event('E1', 'echoendoscope', ['P1'], 'performed', 'was advanced', ['P1'],
                    tg('', 'pancreas', 'pancreatic head', ['P2']), technique=a('endoscope', 'echoendoscope', ['P1']))]
    if denials:
        events.append(event('E2', 'examined', ['P9'], 'not_performed', 'were not examined', ['P9'],
                            tg('', 'esophagus', 'esophagus', ['P9']), scope=sc('single_target', 'the esophagus', ['P9'])))
        events.append(event('E3', 'examined', ['P9'], 'not_performed', 'were not examined', ['P9'],
                            tg('', 'stomach', 'stomach', ['P9']), scope=sc('single_target', 'the stomach', ['P9'])))
    value = {'passages': [{'id': 'P0', 'text': DATE_LINE}, {'id': 'P1', 'text': P1}, {'id': 'P2', 'text': P2},
                          {'id': 'P9', 'text': p9}],
             'encounter': {'date_of_service': {'value': '2026-11-09', 'state': 'stated', 'words': '11/09/2026',
                                               'passages': ['P0'], 'other_dates': []},
                           'documenting_endoscopist': {'words': '', 'passages': []}, 'team': [], 'anatomy': [],
                           'reach': [reach('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1',
                                           completion)], 'visit_facts': []},
             'lesions': [], 'events': events, 'open_questions': []}
    return inv_of(value, '\n'.join((DATE_LINE, P1, P2, p9)) + '\n')


def recorded(item_id: str, line: str):
    """The committed FRESH-2 run 1 of fb12 or fb14 (byte-identical to fresh2-frozen B/<id>/r1) with ONE line edited,
    in the document and in the answer's copy of it - refute6/gate-eus cases_w3 and cases_w4 (r1)."""
    entry = next(item for item in MANIFEST['documents'] if item['id'] == item_id)
    body = json.loads((FIXTURES / entry['runs']['r1']['body']).read_text(encoding='utf-8'))
    value = json.loads(body['candidates'][0]['content']['parts'][0]['text'])
    full = STATIONS['full']
    text = (FIXTURES / entry['document']).read_text(encoding='utf-8')
    assert text.count(full) == 1
    value = copy.deepcopy(value)
    hits = [p for p in value['passages'] if p['text'] == full]
    assert len(hits) == 1
    hits[0]['text'] = line
    return inv_of(value, text.replace(full, line))


FB12_FNA = 'EUS-guided fine-needle aspiration of the pancreatic head mass: 22-gauge needle, 3 passes.'
FB14_EXAM = 'Procedure: The linear echoendoscope was advanced to the second portion of the duodenum.'


def station_question(code: str, region: str, line: str) -> str:
    return (f'The documented endoscopic ultrasound examination (“{line}”) names one station only, the {region}. Was '
            f'{assess.FULL_STATIONS_WORDS} performed on the date of service?')


class TheFullClassNeedsTheEsophagusTheStomachAndTheDuodenum(SimpleTestCase):
    """D171 (3): head, f9013e12e and e5628be56 READY 43259 on row 33 and 43242 on row 26 'duodenum only', and 43259 on
    R8_denials and V1_denials; c2e53f8e holds every one."""

    def test_d171_a_station_line_naming_the_duodenum_only_holds_43259_and_43242(self):
        """Judges finding 11's rows 33 and 26 (cases_w7), and fb12's attested answer with the same edit (cases_w4 r1:
        c2e53f8e READY there - a hold against its READY, which the document does not support)."""
        line = STATIONS['duodenum_only']
        for label, (inv, text), code, cited in (('row33', w7('duodenum_only', False), '43259', P2),
                                                ('row26', w7('duodenum_only', True), '43242', P3),
                                                ('fb12 r1', recorded('fb12', line), '43242', FB12_FNA)):
            result = run(inv, text, [(code, cited)])
            with self.subTest(case=label):
                p = proposal(result, code)
                self.assertEqual((p.status, asked(p)), (HELD, ['extent']))
                self.assertEqual(p.clarifications[0].question, station_question(code, 'duodenum', line))
                self.assertEqual(check(p, CLASS_CHECK).status, 'warn')
                self.assertEqual(reviewed(result, code).status, HELD)

    def test_d171_controls_the_full_station_line(self):
        """The same rows with the full station line, and fb12/fb14's own recordings: the class fits, as on the head."""
        for label, (inv, text), code, cited, expected in (
                ('row33 full', w7('full', False), '43259', P2, ('ready', [])),
                ('row26 full', w7('full', True), '43242', P3, ('ready', [])),
                ('fb12 r1', recorded('fb12', STATIONS['full']), '43242', FB12_FNA, ('ready', [])),
                ('fb14 r1', recorded('fb14', STATIONS['full']), '43259', FB14_EXAM, (HELD, ['target']))):
            with self.subTest(case=label):
                p = proposal(run(inv, text, [(code, cited)]), code)
                self.assertEqual((p.status, asked(p)), expected)
                self.assertIsNone(check(p, CLASS_CHECK))

    def test_d171_a_station_denied_holds_the_full_code_whether_cited_or_not(self):
        """Judges finding 13's R8_denials and V1_denials (cases_w6): 43259 cited on P2, and on the denial itself."""
        for label, p9 in (('R8_denials', P9_ROW8), ('V1_denials', P9_V1)):
            inv, text = w6(p9, denials=True)
            for cited in (P2, p9):
                result = run(inv, text, [('43259', cited)])
                with self.subTest(case=label, cited='denial' if cited == p9 else 'P2'):
                    p = proposal(result, '43259')
                    self.assertEqual((p.status, p.bucket, asked(p)), (HELD, 'selected', ['extent']))
                    self.assertEqual(p.clarifications[0].question,
                                     f'The document states that the esophagus was not examined (“{p9}”). Was '
                                     f'{assess.FULL_STATIONS_WORDS} performed on the date of service?')

    def test_d171_controls_another_occasions_denial(self):
        """Mine: the stomach's denial verified as another occasion's ('At her EUS on 03/02/2025 the stomach was not
        examined.') beside the full station line: 43242 READY, as on the head."""
        line = 'At her EUS on 03/02/2025 the stomach was not examined.'
        raw, raw_text = w7_raw('full', True, extra={'P9': line}, denial=('P9', 'stomach', 'stomach',
                                                                       a('earlier_encounter', 'At her EUS on 03/02/2025',
                                                                         ['P9'])))
        inv, text = inv_of(raw, raw_text)
        p = proposal(run(inv, text, [('43242', P3)]), '43242')
        self.assertEqual(outcome(p), ('ready', [], ['E2']))

    def test_d171_an_excluded_code_keeps_its_waits(self):
        """Mine: 43242 excluded by its cited denial ('No fine-needle aspiration was performed.') on row 26's 'duodenum
        only' document: no EUS code check is read for a code the rule does not support - its reinstatement waits are the
        head's (none)."""
        line = 'No fine-needle aspiration was performed.'
        raw, raw_text = w7_raw('duodenum_only', False, extra={'P3': line}, fna_denied=True)
        inv, text = inv_of(raw, raw_text)
        p = proposal(run(inv, text, [('43242', line)]), '43242')
        self.assertEqual((p.bucket, p.support.get('reinstatement_waits', [])), ('excluded', []))

    def test_d171_controls_d73s_one_reach_and_the_completion(self):
        """R8_row (no denial event: D73's control, READY as the head pins it) and D56's controls R8_full and
        V1_completion (completion 'incomplete'): unchanged."""
        inv, text = w6(P9_ROW8, denials=False)
        with self.subTest(case='R8_row'):
            self.assertEqual(proposal(run(inv, text, [('43259', P2)]), '43259').status, 'ready')
        for label, p9, words in (('R8_full', P9_ROW8, 'The examination was incomplete'), ('V1_completion', P9_V1, P9_V1)):
            inv, text = w6(p9, denials=True, completion=a('incomplete', words, ['P9']))
            p = proposal(run(inv, text, [('43259', P2)]), '43259')
            with self.subTest(case=label):
                self.assertEqual((p.status, asked(p)), (HELD, ['extent']))
                self.assertIn('is stated to be incomplete', p.clarifications[0].question)

    def test_d171_the_limited_codes_question_states_their_class(self):
        """43237 and 43238 on rows 33 and 26 'duodenum only' (held by D28's reach, as before): the question names CPT's
        class - limited to the esophagus, the stomach or the duodenum - never 'short of the duodenum'."""
        for label, (inv, text), code, cited in (('row33', w7('duodenum_only', False), '43237', P2),
                                                ('row26', w7('duodenum_only', True), '43238', P3)):
            p = proposal(run(inv, text, [(code, cited)]), code)
            with self.subTest(case=label):
                self.assertEqual((p.status, asked(p)), (HELD, ['extent']))
                self.assertEqual(p.clarifications[0].question,
                                 'The documented endoscopic ultrasound examination (“second portion of the duodenum”) '
                                 'reached the second portion duodenum. Was an endoscopic ultrasound examination limited '
                                 'to the esophagus, the stomach or the duodenum (and adjacent structures) performed on '
                                 'the date of service?')
                self.assertNotIn('short of the duodenum', p.clarifications[0].question + p.clarifications[0].reason)
        self.assertNotIn('43231', mapping.EGD_LIMITED_EUS_CODES)  # an esophagoscopy's limited code keeps D28's words


# --- (4) an injection of the wall: refute6/gate-eus cases_w5 (judges finding 12) -----------------------------------------
W5_HEAD = 'UPPER ENDOSCOPIC ULTRASOUND (EUS) REPORT'
W5_LINES = [W5_HEAD, 'Date of service: November 9, 2026', 'Endoscopist: Ana Ruiz, MD (fictional)',
            'Indication: Gastric subepithelial lesion on EGD; planned laparoscopic wedge resection.',
            'Procedure: The linear echoendoscope was advanced to the second portion of the duodenum.',
            'EUS imaging was performed from the esophagus, stomach and duodenum.',
            'EUS findings: a 22 mm hypoechoic lesion arising from the muscularis propria of the gastric body, consistent '
            'with a gastrointestinal stromal tumor.', '{act}',
            'Impression: 22 mm gastric subepithelial lesion, likely a gastrointestinal stromal tumor.']
W5_ACTS = {
    'T1': 'The gastric wall 2 cm proximal to the lesion was tattooed with a submucosal injection of 2 mL of India ink '
          'for surgical localization.',
    'T2': 'A submucosal tattoo was placed 2 cm proximal to the lesion with India ink for surgical localization.',
    'T4': 'A submucosal injection of 5 mL of saline was made beside the lesion; the lesion did not lift, and surgical '
          'resection is planned.',
    'C1': 'EUS-guided celiac plexus block was performed with 20 mL of 0.25% bupivacaine and 80 mg of triamcinolone '
          'through a 22-gauge needle.',
    'LIFT': 'Saline was injected beneath the lesion to lift it; the lesion did not lift.',  # mine
}
W5_EXAM_LINE = W5_LINES[4]


def w5(name: str):
    """cases_w5.build / build_t4: the upper EUS (fb12/fb14's examination shape, no target) and the act of ``name``."""
    act_line = W5_ACTS[name]
    lines = [line.replace('{act}', act_line) for line in W5_LINES]
    pid = {line: f'P{i + 1}' for i, line in enumerate(lines)}
    P = pid.__getitem__
    exam = {'id': 'E1', 'procedure': a('eus', 'UPPER ENDOSCOPIC ULTRASOUND (EUS)', [P(W5_HEAD)]),
            'kind': a('examination', 'EUS imaging', [P(W5_HEAD), P(lines[4]), P(lines[5])]),
            'technique': a('endoscope', 'linear echoendoscope', [P(lines[4])]), 'target': tg(),
            'time': a('current_encounter'), 'performer': a('documenting_team'),
            'status': a('performed', 'was performed', [P(lines[5])]), 'scope': sc(), 'purpose': a('diagnostic'),
            'part_of': '', 'sequence': 0, 'contradicts': []}
    heading = a('eus', 'UPPER ENDOSCOPIC ULTRASOUND (EUS)', [P(W5_HEAD)])
    base = {'time': a('current_encounter'), 'performer': a('documenting_team'), 'scope': sc(), 'part_of': '',
            'sequence': 0, 'contradicts': [], 'id': 'E2'}
    if name == 'T1':
        act = dict(base, procedure=heading, kind=a('tattoo', 'tattooed', [P(act_line)]),
                   technique=a('injection', 'submucosal injection', [P(act_line)]),
                   target=tg('', 'stomach', 'The gastric wall 2 cm proximal to the lesion', [P(act_line)]),
                   status=a('performed', 'was tattooed', [P(act_line)]),
                   purpose=a('marking', 'for surgical localization', [P(act_line)]))
    elif name == 'T2':
        act = dict(base, procedure=heading, kind=a('tattoo', 'submucosal tattoo', [P(act_line)]),
                   technique=a('injection', 'India ink', [P(act_line)]),
                   target=tg('L1', 'gastric_body', 'the lesion', [P(act_line)]),
                   status=a('performed', 'was placed', [P(act_line)]),
                   purpose=a('marking', 'for surgical localization', [P(act_line)]))
    elif name == 'LIFT':
        act = dict(base, procedure=heading, kind=a('injection', 'injected', [P(act_line)]),
                   technique=a('not_stated'), target=tg('L1', 'gastric_body', 'beneath the lesion', [P(act_line)]),
                   status=a('performed', 'was injected', [P(act_line)]),
                   purpose=a('lift_for_resection', 'to lift it', [P(act_line)]))
    elif name == 'T4':
        act = dict(base, procedure=heading, kind=a('injection', 'submucosal injection', [P(act_line)]),
                   technique=a('injection', 'submucosal injection', [P(act_line)]),
                   target=tg('L1', 'gastric_body', 'beside the lesion', [P(act_line)]),
                   status=a('performed', 'was made', [P(act_line)]),
                   purpose=a('lift_for_resection', 'did not lift', [P(act_line)]))
    else:
        act = dict(base, procedure=a('eus', 'EUS-guided', [P(act_line)]),
                   kind=a('injection', 'celiac plexus block', [P(act_line)]),
                   technique=a('needle', '22-gauge needle', [P(act_line)]),
                   target=tg('', 'not_stated', 'celiac plexus', [P(act_line)]),
                   status=a('performed', 'was performed', [P(act_line)]), purpose=a('treatment'))
    value = {'passages': [{'id': f'P{i + 1}', 'text': line} for i, line in enumerate(lines)],
             'encounter': {'date_of_service': {'value': '2026-11-09', 'state': 'stated', 'words': 'November 9, 2026',
                                               'passages': [P(lines[1])], 'other_dates': []},
                           'documenting_endoscopist': {'words': 'Ana Ruiz, MD', 'passages': [P(lines[2])]},
                           'team': [], 'anatomy': [],
                           'reach': [reach('E1', 'second_portion_duodenum', 'second portion of the duodenum',
                                           P(lines[4]))], 'visit_facts': []},
             'lesions': [les('L1', 'a 22 mm hypoechoic lesion arising from the muscularis propria of the gastric body',
                             [P(lines[6])], landmark='gastric_body', site_words='gastric body', size_words='22 mm')],
             'events': [exam, act], 'open_questions': []}
    inv, text = inv_of(value, '\n'.join(lines) + '\n')
    return inv, text, act_line


T3_LINES = dict(F1_LINES, P3='Indication: Gastric subepithelial lesion on EGD; planned laparoscopic wedge resection.',
                P6=('EUS findings: a 22 mm hypoechoic lesion arising from the muscularis propria of the gastric body, '
                    'consistent with a GIST.'),
                P7=('The proximal margin of the gastric body lesion was tattooed with Spot ink in two quadrants for '
                    'surgical localization.'),
                P8='Impression: 22 mm gastric body subepithelial lesion; tattooed for surgery.')
for _pid in ('P9', 'P10', 'P11'):
    del T3_LINES[_pid]


def spot_ink():
    """refute6/eus cases_b3.tattoo_upper (families finding 6's input, the Spot-ink tattoo, its kind 'tattoo')."""
    lesion = les('L1', 'a 22 mm hypoechoic lesion arising from the muscularis propria of the gastric body', ['P6'],
                 landmark='gastric_body', site_words='gastric body', size_words='22 mm')
    tat = ev('E2', 'P7', 'tattoo', 'tattooed', procedure=a('eus', 'UPPER ENDOSCOPIC ULTRASOUND (EUS)', ['P1']),
             status_words='was tattooed', technique=a('injection', 'Spot ink', ['P7']),
             target=tg('L1', 'gastric_body', 'The proximal margin of the gastric body lesion', ['P7']),
             purpose=a('marking', 'for surgical localization', ['P7']))
    value, text = answer(T3_LINES, [F1_EXAM, tat], [lesion], reach_=[F1_REACH], endoscopist=ENDO)
    return inv_of(value, text)


class AnInjectionOfTheWallIsNoTransmuralInjection(SimpleTestCase):
    """D171 (4): head, f9013e12e and e5628be56 READY 43253 on T1, T2 and T4; c2e53f8e holds it ([target] on T1,
    [performed_status, target] on T2 and T4) and holds 43236 [performed_status, extent]."""

    def assert_wall(self, result, line):
        p = proposal(result, '43253')
        self.assertEqual(outcome(p), (HELD, ['target'], ['E2']))
        self.assertEqual(check(p, EUS_ACT_CHECK).status, 'warn')
        self.assertIn(f'(“{line}”)', p.clarifications[0].question)  # the act's whole sentence
        self.assertIn('a submucosal injection rather than a transmural one', p.clarifications[0].reason)
        self.assertEqual(reviewed(result, '43253').status, HELD)

    def test_d171_43253_on_a_submucosal_tattoo_or_injection_is_held(self):
        """Judges finding 12's T1 (the finding's input), T2 and T4, alone and beside 43259; 43236 beside 43259 keeps its
        hold, as on the head and c2e53f8e."""
        for name in ('T1', 'T2', 'T4'):
            inv, text, line = w5(name)
            for picks in ([('43253', line)], [('43253', line), ('43259', W5_EXAM_LINE)]):
                with self.subTest(case=name, codes=[code for code, _ in picks]):
                    self.assert_wall(run(inv, text, picks), line)
            with self.subTest(case=name, codes=['43236', '43259']):
                p = proposal(run(inv, text, [('43236', line), ('43259', W5_EXAM_LINE)]), '43236')
                self.assertEqual((p.status, asked(p)), (HELD, ['performed_status', 'extent']))

    def test_d171_with_the_participants(self):
        """cases_w5's T1p: Astra proposes 43259 and 43236, Fable 43253; Corti 43253."""
        from tests.test_interpretation_assess import participant
        inv, text, line = w5('T1')
        parts = (participant('astra', text, codes=[('43259', W5_EXAM_LINE), ('43236', line)]),
                 participant('fable', text, codes=[('43253', line)]))
        self.assert_wall(run(inv, text, [('43253', line)], participants=parts), line)

    def test_d171_an_ink_tattoo_is_held(self):
        """Families finding 6's Spot-ink tattoo of the gastric body lesion (no 'submucosal' word): held, as c2e53f8e."""
        inv, text = spot_ink()
        for picks in ([('43253', T3_LINES['P7'])], [('43259', T3_LINES['P5']), ('43253', T3_LINES['P7'])]):
            with self.subTest(codes=[code for code, _ in picks]):
                self.assert_wall(run(inv, text, picks), T3_LINES['P7'])

    def test_d171_a_lift_injection_is_held(self):
        """Mine: 'Saline was injected beneath the lesion to lift it; the lesion did not lift.' - no route word, its
        purpose a lift for resection (a submucosal injection by definition): held, as c2e53f8e holds it [target]."""
        inv, text, line = w5('LIFT')
        self.assert_wall(run(inv, text, [('43253', line)]), line)

    def test_d171_controls_the_fiducials_and_the_celiac_block(self):
        """The upper fiducial placement (D145: a fiducial read as 'tattoo' supports 43253) READY; the celiac block
        (cases_w5 C1) keeps the head's outcome (no EUS act check)."""
        inv, text = upper_fiducial('tattoo')
        with self.subTest(control='fiducial'):
            self.assertEqual(outcome(proposal(run(inv, text, [('43253', U_LINES['P6'])]), '43253')),
                             ('ready', [], ['E2']))
        inv, text, line = w5('C1')
        p = proposal(run(inv, text, [('43253', line)]), '43253')
        with self.subTest(control='celiac block'):
            self.assertIsNone(check(p, EUS_ACT_CHECK))

    def test_d171_submucosal_act_reads_the_acts_own_words(self):
        """mapping.submucosal_act over the act's own kind, technique, target and purpose words, in any state."""
        def act(kind='injection', kind_words='', **words):
            item = {'kind': {'value': kind, 'words': {'text': kind_words}}, 'catalogue_kind': kind}
            for name, text_ in words.items():
                item[name] = {'value': 'x', 'words': {'text': text_}}
            return item

        for label, event, expected in (
                ('technique submucosal', act(technique='submucosal injection'), True),
                ('kind sub-mucosal', act('tattoo', 'sub-mucosal tattoo'), True),
                ('target submucosa', act(target='the submucosa of the gastric wall'), True),
                ('purpose submucosal', act(purpose='submucosal lift'), True),
                ('ink tattoo', act('tattoo', technique='India ink'), True),
                ('Spot ink tattoo', act('tattoo', 'tattooed', technique='Spot ink'), True),
                ('ink, not a tattoo', act(technique='India ink'), False),
                ('fiducial tattoo', act('tattoo', 'fiducial markers'), False),
                ('celiac block', act(kind_words='celiac plexus block', target='celiac plexus'), False),
                ('a tattoo naming no ink', act('tattoo', 'tattooed', technique='injected'), False)):
            with self.subTest(case=label):
                self.assertEqual(mapping.submucosal_act(event), expected)
