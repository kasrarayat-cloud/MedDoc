"""DECISIONS D177 (the Gemini migration's round 5h, narrowing only: round5g/results-round5g-b.json 'review:eus7' problems
0, 2, 3, 4, 5 and 7, on D171), SYNTHETIC, each built from its source's own input - the review's own constructions
(round5g/review-eus7/tools rv_build.py and rv_build2.py: X1, X2, X3 and X6) and D171's builders
(tests/test_interpretation_r5g_eus_class.py: refute6's F1, F2, cases_w5, w6 and w7, and the committed FRESH-2 recording
of fb12 with one line edited) - and mine. Nothing is sent.
- (1) problem 0 (D171's recorded stop): the base question names only codes of the base code's own tract - 45341 beside
  43253 on a rectal EUS is asked about the act ('... from fiducial markers ...'), never about 43253; the hold itself is
  unchanged, and where nothing of its own tract is left to name the old naming stays (the recorded residual).
- (2) problem 2 (critical, pre-existing): 43253 is held [target] on a tattoo whose own place is in the wall of the tract,
  whatever its material ('A carbon-particle tattoo was placed in the gastric wall ...'): by its kind and its place.
- (3) problem 3 (critical, pre-existing): a drainage in doubt - its status words not binding (X6), its target tied to no
  lesion (X3) - still makes the same lesion's FNA a possible step: 43242 held [target].
- (4) problem 4 (critical, pre-existing): a station line naming two of the three stations ('EUS imaging was performed from
  the stomach and duodenum.') holds 43259 and 43242 [extent].
- (5) problem 5 (residual): R8_row's off-contract answer stays READY (D73's control) - recorded, unchanged.
- (7) problem 7 (wording): the step hold's reason says 'of the same structure' only where both targets are verified to
  one lesion.
Each test asserts in independent subtests, labelled by what each varies, so a regression shows every one it breaks."""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from studio.interpretation import assess, mapping, normalize
from tests.test_interpretation_events import asked, check, proposal, run
from tests.test_interpretation_identity import accepted
from tests.test_interpretation_r3_integration_d88_d93 import reviewed
from tests import test_interpretation_r5g_eus_class as R
from tests.test_interpretation_r5g_eus_class import (ENDO, F1_EXAM, F1_LINES, F1_PC, F1_REACH, F2_EXAM, F2_LINES, F2_MASS,
                                                     FB12_FNA, P2, P3, U_LINES, W5_EXAM_LINE, a, answer, ev, f1, f1_drainage,
                                                     les, reach, sc, tg)

EUS_ACT_CHECK = 'facts.eus_act'
CLASS_CHECK = 'facts.examination_class'
BASE_CHECK = 'services.base_included'
HELD = 'needs_clarification'


def inv_of(value, text):
    return normalize.normalize(accepted(value), text), text


def outcome(p) -> tuple:
    return (p.status, asked(p), [item['id'] for item in p.support.get('acts') or ()])


def question(p, fact: str) -> str:
    found = [spec.question for spec in p.clarifications if spec.fact == fact]
    assert len(found) == 1, (fact, asked(p))
    return found[0]


def reason(p, fact: str) -> str:
    found = [spec.reason for spec in p.clarifications if spec.fact == fact]
    assert len(found) == 1, (fact, asked(p))
    return found[0]


# --- (1) the base question names its own tract: refute6/eus cases_b2 F2 and F2b (review:eus7 problem 0) ---------------

def rectal_exam_only():
    """Mine: F2's rectal EUS with its examination only (no act): the recorded residual's input."""
    lines = {pid: line for pid, line in F2_LINES.items() if pid != 'P6'}
    lines['P7'] = 'Impression: uT2N0 rectal cancer.'
    value, text = answer(lines, [F2_EXAM], [F2_MASS], reach_=[reach('E1', 'sigmoid_colon', 'sigmoid colon', 'P4')],
                         endoscopist=ENDO)
    return inv_of(value, text)


class TheBaseQuestionNamesItsOwnTract(SimpleTestCase):
    """D177 (1): on 1b4ca399, 05a881a75 and e5628be56, 45341 beside 43253 on F2 and F2b is held [base_included, target]
    with 'Is 45341 reported separately from 43253 for this examination?'; c2e53f8e holds 45341 [performed_status,
    target]."""

    def test_d177_45341_beside_an_upper_code_is_asked_about_the_act(self):
        """Problem 0's input: F2 (the fiducials read as 'tattoo') and F2b ('injection'), 45341 on P4 and 43253 on P6. The
        hold is kept (its facts unchanged); its question names the act, as 45341 alone is asked; 43253 keeps D171's."""
        for kind, label in (('tattoo', 'fiducial markers'), ('injection', 'submucosal injection')):
            inv, text = R.f2(kind)
            result = run(inv, text, [('45341', F2_LINES['P4']), ('43253', F2_LINES['P6'])])
            p = proposal(result, '45341')
            with self.subTest(kind=kind):
                self.assertEqual((p.status, asked(p)), (HELD, ['base_included', 'target']))
                self.assertEqual(question(p, 'base_included'),
                                 f'Is 45341 reported separately from {label} for this examination?')
                self.assertNotIn('43253', question(p, 'base_included') + reason(p, 'base_included'))
                self.assertEqual(check(p, BASE_CHECK).status, 'warn')
                self.assertEqual(asked(proposal(result, '43253')), ['extent'])
                self.assertEqual(reviewed(result, '45341').status, HELD)
                alone = proposal(run(inv, text, [('45341', F2_LINES['P4'])]), '45341')
                self.assertEqual(question(alone, 'base_included'), question(p, 'base_included'))

    def test_d177_a_code_of_its_own_tract_is_still_named(self):
        """Mine: F2 with 45342 (the lower-tract FNA code) proposed beside them: 45341 names 45342, never 43253."""
        inv, text = R.f2('tattoo')
        result = run(inv, text, [('45341', F2_LINES['P4']), ('45342', F2_LINES['P6']), ('43253', F2_LINES['P6'])])
        p = proposal(result, '45341')
        self.assertEqual(p.status, HELD)
        self.assertEqual(question(p, 'base_included'), 'Is 45341 reported separately from 45342 for this examination?')

    def test_d177_an_upper_base_code_beside_a_lower_code_names_its_own(self):
        """Mine: row 26's upper EUS (cases_w7, the full station line) with 45342 proposed for its FNA: 43259 names its own
        tract's 43242 where it is proposed, else the act - never 45342; 45342 keeps D43's class hold."""
        inv, text = R.w7('full', True)
        result = run(inv, text, [('43259', P2), ('45342', P3)])
        p = proposal(result, '43259')
        with self.subTest(codes='43259, 45342'):
            self.assertEqual(p.status, HELD)
            self.assertIn('base_included', asked(p))
            self.assertNotIn('45342', question(p, 'base_included'))
            self.assertEqual(proposal(result, '45342').status, HELD)
        result = run(inv, text, [('43259', P2), ('43242', P3), ('45342', P3)])
        with self.subTest(codes='43259, 43242, 45342'):
            self.assertEqual(question(proposal(result, '43259'), 'base_included'),
                             'Is 43259 reported separately from 43242 for this examination?')

    def test_d177_stop_nothing_of_its_own_tract_left_to_name_keeps_the_hold(self):
        """The recorded residual (a STOP): a rectal EUS examination only, 45341 and 43259 proposed. Nothing of 45341's tract
        is left to name - no code, no act - and naming nothing would drop its base hold (a QUESTION-DROPPED here, where
        competing_codes and target hold it too; a RELEASE where nothing else does), so the question names 43259 as on the
        head. 45341 is held, never READY."""
        inv, text = rectal_exam_only()
        result = run(inv, text, [('45341', F2_LINES['P4']), ('43259', F2_LINES['P4'])])
        p = proposal(result, '45341')
        self.assertEqual(p.status, HELD)
        self.assertEqual(question(p, 'base_included'), 'Is 45341 reported separately from 43259 for this examination?')
        self.assertEqual(reviewed(result, '45341').status, HELD)


# --- (2) a tattoo in the wall: review:eus7 problem 2 (rv_build.py X1, on cases_w5's upper EUS) ---------------------------

def w5_act(act_line: str, act: dict, exam_target: bool = False):
    """cases_w5's upper EUS (R.w5's document and examination) with ``act_line`` as its act sentence and ``act`` (E2,
    passages '@' for the act line) as Gemini's act - review:eus7's w5_custom. ``exam_target``: the examination's own
    target placed at the gastric body by the findings line (so the code's 'target' fact is documented by it, and R6 asks
    nothing of an act whose own target is unplaced)."""
    lines = [line.replace('{act}', act_line) for line in R.W5_LINES]
    pid = {line: f'P{i + 1}' for i, line in enumerate(lines)}
    P = pid.__getitem__
    exam = {'id': 'E1', 'procedure': a('eus', 'UPPER ENDOSCOPIC ULTRASOUND (EUS)', [P(R.W5_HEAD)]),
            'kind': a('examination', 'EUS imaging', [P(R.W5_HEAD), P(lines[4]), P(lines[5])]),
            'technique': a('endoscope', 'linear echoendoscope', [P(lines[4])]),
            'target': tg('', 'gastric_body', 'the gastric body', [P(lines[6])]) if exam_target else tg(),
            'time': a('current_encounter'), 'performer': a('documenting_team'),
            'status': a('performed', 'was performed', [P(lines[5])]), 'scope': sc(), 'purpose': a('diagnostic'),
            'part_of': '', 'sequence': 0, 'contradicts': []}
    act = copy.deepcopy(act)
    for record in act.values():
        if isinstance(record, dict) and record.get('passages') == ['@']:
            record['passages'] = [P(act_line)]
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
    return inv_of(value, '\n'.join(lines) + '\n')


def tattoo(kind_words, target_words, *, landmark='stomach', lesion='', technique=None, purpose=None,
           status_words='was placed', kind='tattoo'):
    """review:eus7's tattoo_event: E2, an act of ``kind`` filed under the upper EUS heading, stated in the act line."""
    return {'id': 'E2', 'procedure': a('eus', 'UPPER ENDOSCOPIC ULTRASOUND (EUS)', ['P1']),
            'kind': a(kind, kind_words, ['@']), 'technique': technique or a('not_stated'),
            'target': tg(lesion, landmark, target_words, ['@']), 'time': a('current_encounter'),
            'performer': a('documenting_team'), 'status': a('performed', status_words, ['@']), 'scope': sc(),
            'purpose': purpose or a('not_stated'), 'part_of': '', 'sequence': 0, 'contradicts': []}


CARBON = 'A carbon-particle tattoo was placed in the gastric wall 2 cm proximal to the lesion for surgical localization.'
CARBON_TARGET = 'the gastric wall 2 cm proximal to the lesion'
MARKING = a('marking', 'for surgical localization', ['@'])
TATTOOED = 'The gastric wall 2 cm proximal to the lesion was tattooed for surgical localization.'
LESION_TATTOO = 'The lesion was marked with a carbon-particle tattoo for surgical localization.'
WALL_OTHER = 'A carbon-particle tattoo was placed in the gastric wall beside the lesion for surgical localization.'
ANASTOMOSIS_TATTOO = 'A carbon-particle tattoo was placed at the gastrojejunal anastomosis for surgical localization.'
NODE_TATTOO = 'EUS-guided tattooing of the 12 mm perigastric lymph node was performed for surgical localization.'
ESOPHAGEAL_FIDUCIAL = 'Two gold fiducial markers were placed into the distal esophageal tumor for radiation planning.'
# review:eus7 problem 2's three X1 shapes (rv_build.py) and its X1d
X1_SHAPES = {
    'X1 technique not stated': (CARBON, tattoo('carbon-particle tattoo', CARBON_TARGET, purpose=MARKING)),
    'X1b technique injection': (CARBON, tattoo('carbon-particle tattoo', CARBON_TARGET, purpose=MARKING,
                                               technique=a('injection', 'carbon-particle tattoo', ['@']))),
    'X1c no purpose': (CARBON, tattoo('carbon-particle tattoo', CARBON_TARGET)),
    'X1d tattooed': (TATTOOED, tattoo('tattooed', 'The gastric wall 2 cm proximal to the lesion', purpose=MARKING,
                                      status_words='was tattooed')),
}


class ATattooInTheWallIsNoTransmuralInjection(SimpleTestCase):
    """D177 (2): on 1b4ca399, 05a881a75 and e5628be56, 43253 is READY on every X1 shape, alone (coding complete) and
    beside 43259; c2e53f8e holds it [performed_status, target]."""

    def assert_wall(self, result, line):
        p = proposal(result, '43253')
        self.assertEqual(outcome(p), (HELD, ['target'], ['E2']))
        self.assertEqual(check(p, EUS_ACT_CHECK).status, 'warn')
        self.assertIn(f'(“{line}”)', p.clarifications[0].question)
        self.assertIn('in the wall of the tract', p.clarifications[0].reason)
        self.assertIn('a submucosal injection rather than a transmural one', p.clarifications[0].reason)
        self.assertEqual(reviewed(result, '43253').status, HELD)
        self.assertNotEqual(result.completeness['state'], 'complete_pending_review')

    def test_d177_a_carbon_particle_tattoo_of_the_gastric_wall_holds_43253(self):
        """Problem 2's inputs (X1, X1b, X1c, X1d), alone and beside 43259; 43236 beside 43259 keeps its hold."""
        for label, (line, act) in X1_SHAPES.items():
            inv, text = w5_act(line, act)
            for picks in ([('43253', line)], [('43253', line), ('43259', W5_EXAM_LINE)]):
                with self.subTest(case=label, codes=[code for code, _ in picks]):
                    self.assert_wall(run(inv, text, picks), line)
            with self.subTest(case=label, codes=['43236', '43259']):
                p = proposal(run(inv, text, [('43236', line), ('43259', W5_EXAM_LINE)]), '43236')
                self.assertEqual((p.status, asked(p)), (HELD, ['performed_status', 'extent']))

    def test_d177_the_tattoos_place_through_its_lesion_or_its_own_words(self):
        """Mine: the tattoo's target names the lesion with no landmark of its own (its lesion's site places it), or gives
        the landmark 'other' with words that name the stomach (its own target words place it), or an anastomosis. The
        examination's own target documents the code's 'target' fact, so R6 asks nothing first: the EUS act check holds."""
        for label, line, act in (
                ('through its lesion', LESION_TATTOO,
                 tattoo('carbon-particle tattoo', 'The lesion', landmark='not_stated', lesion='L1', purpose=MARKING,
                        status_words='was marked')),
                ('its own words', WALL_OTHER,
                 tattoo('carbon-particle tattoo', 'the gastric wall beside the lesion', landmark='other',
                        purpose=MARKING)),
                ('an anastomosis', ANASTOMOSIS_TATTOO,
                 tattoo('carbon-particle tattoo', 'the gastrojejunal anastomosis', landmark='anastomosis',
                        purpose=MARKING))):
            inv, text = w5_act(line, act, exam_target=True)
            result = run(inv, text, [('43253', line)])
            with self.subTest(case=label):
                self.assert_wall(result, line)
            inv, text = w5_act(line, act)
            p = proposal(run(inv, text, [('43253', line)]), '43253')
            with self.subTest(case=label, examination='its target not placed'):
                if label == 'an anastomosis':  # its own target is placed, so R6 asks nothing: the wall holds it
                    self.assertEqual((asked(p), check(p, EUS_ACT_CHECK).status), (['target'], 'warn'))
                else:  # R6 asks the structure examined: held by it, and no second 'target' question
                    self.assertEqual((p.status, asked(p), check(p, EUS_ACT_CHECK)), (HELD, ['target'], None))

    def test_d177_controls_a_placement_beside_the_tract(self):
        """Controls, unchanged: D145's fiducials into the pancreatic head (verify-eus-1's U, read as 'tattoo') and a
        tattoo of a perigastric lymph node (its place beside the tract) stay READY; the celiac block gets no EUS act
        check."""
        inv, text = R.upper_fiducial('tattoo')
        with self.subTest(control='fiducials into the pancreatic head'):
            self.assertEqual(outcome(proposal(run(inv, text, [('43253', U_LINES['P6'])]), '43253')),
                             ('ready', [], ['E2']))
        inv, text = w5_act(NODE_TATTOO, tattoo('tattooing', 'the 12 mm perigastric lymph node', landmark='lymph_node',
                                               purpose=MARKING, status_words='was performed'))
        with self.subTest(control='lymph node'):
            self.assertEqual(outcome(proposal(run(inv, text, [('43253', NODE_TATTOO)]), '43253')),
                             ('ready', [], ['E2']))
        inv, text, line = R.w5('C1')
        with self.subTest(control='celiac block'):
            self.assertIsNone(check(proposal(run(inv, text, [('43253', line)]), '43253'), EUS_ACT_CHECK))

    def test_d177_a_fiducial_placement_into_a_tumour_of_the_wall_is_held(self):
        """Mine, a recorded hold against the expected outcome: fiducials placed into a distal esophageal tumour, read as
        'tattoo' (D145) - the act's kind and its place are those of a wall tattoo, so 43253 is held (no word of the
        material or the device sets it apart)."""
        inv, text = w5_act(ESOPHAGEAL_FIDUCIAL, tattoo('fiducial markers', 'the distal esophageal tumor',
                                                       landmark='distal_esophagus', status_words='were placed',
                                                       purpose=a('marking', 'for radiation planning', ['@'])))
        p = proposal(run(inv, text, [('43253', ESOPHAGEAL_FIDUCIAL)]), '43253')
        self.assertEqual(outcome(p), (HELD, ['target'], ['E2']))

    def test_d177_wall_place_reads_the_acts_own_place(self):
        """mapping.wall_place and submucosal_act's D177 arm over an act's kind and place, in any state."""
        def act(kind='tattoo', landmark='', words='', state='verified', lesion_site=''):
            event = {'kind': {'value': kind, 'words': {'text': ''}}, 'catalogue_kind': kind,
                     'target': {'value': landmark, 'state': state, 'words': {'text': words}}}
            lesion = {'site': {'value': lesion_site, 'state': 'unverified'}} if lesion_site else None
            return event, lesion

        for label, (event, lesion), place, held in (
                ('stomach', act(landmark='stomach'), 'stomach', True),
                ('unverified gastric body', act(landmark='gastric_body', state='unverified'), 'gastric_body', True),
                ('rectum', act(landmark='rectum'), 'rectum', True),
                ('anastomosis', act(landmark='anastomosis'), 'anastomosis', True),
                ('lesion site', act(landmark='not_stated', lesion_site='gastric_antrum'), 'gastric_antrum', True),
                ('own words', act(landmark='other', words='the esophageal wall'), 'esophagus', True),
                ('pancreas', act(landmark='pancreas', words='the gastric wall'), '', False),
                ('unverified pancreas, its words the stomach',
                 act(landmark='pancreas', words='the gastric wall', state='unverified'), 'stomach', True),
                ('lymph node', act(landmark='lymph_node'), '', False),
                ('liver', act(landmark='liver'), '', False),
                ('unplaced', act(landmark='not_stated'), '', False),
                ('an injection in the wall', act('injection', landmark='stomach'), 'stomach', False)):
            with self.subTest(case=label):
                self.assertEqual(mapping.wall_place(event, lesion), place)
                self.assertEqual(mapping.submucosal_act(event, lesion), held)
                self.assertFalse(mapping.submucosal_act(event, lesion, place=False))


# --- (3) a drainage in doubt: review:eus7 problem 3 (rv_build.py X3, rv_build2.py X6, on F1) ------------------------------

def f1_with(p9: str, drain: dict, part_of: str = '', p7: str = '', fna_target=None):
    """F1 (refute6/eus cases_b2; D171's f1) with its drainage line ``p9`` and drainage ``drain``; the FNA (E2) of the
    pseudocyst (L1) - or ``fna_target`` in its line ``p7`` - its part_of ``part_of``."""
    lines = dict(F1_LINES, P9=p9, **({'P7': p7} if p7 else {}))
    fna = ev('E2', 'P7', 'fna', 'aspirated', procedure=a('eus', 'Under EUS guidance', ['P7']), status_words='was aspirated',
             technique=a('needle', '19-gauge needle', ['P7']),
             target=fna_target or tg('L1', 'pancreas', 'the pseudocyst', ['P7']),
             purpose=a('diagnostic', 'sent for amylase and CEA', ['P7']), part_of=part_of, sequence=1)
    value, text = answer(lines, [F1_EXAM, fna, drain], [F1_PC], reach_=[F1_REACH], endoscopist=ENDO)
    return inv_of(value, text)


def drainage(status='performed', status_words='was then performed', lesion='L1', landmark='pancreas',
             target_words='the pseudocyst', time=None):
    """F1's drainage (E3, D171's f1_drainage) with its status, its target and its time given."""
    return ev('E3', 'P9', 'drainage', 'transmural drainage', procedure=a('eus', 'EUS-guided', ['P9']), status=status,
              status_words=status_words, technique=a('stent', 'lumen-apposing metal stent', ['P9']),
              target=tg(lesion, landmark, target_words, ['P9']), sequence=2, time=time)


P9 = F1_LINES['P9']
P7_PANCREATIC = ('Under EUS guidance, the pancreatic pseudocyst was punctured from the gastric body with a 19-gauge needle and '
                 '20 mL of clear fluid was aspirated and sent for amylase and CEA.')
P9_UNCERTAIN = 'EUS-guided transmural drainage of the pseudocyst may have been performed with a 15 mm lumen-apposing metal stent.'
P9_COLLECTION = ('EUS-guided transmural drainage of the collection was then performed with a 15 mm lumen-apposing metal '
                 'stent.')
P9_PANCREATIC = ('EUS-guided transmural drainage of the pancreatic pseudocyst was then performed with a 15 mm '
                 'lumen-apposing metal stent.')
P9_PLANNED = 'EUS-guided transmural drainage of the pseudocyst is planned in 4 weeks.'
P9_NOT_DONE = 'EUS-guided transmural drainage of the pseudocyst was not performed; the cyst will be re-imaged.'
P9_INDEX = ('At her index EUS on 01/14/2024, EUS-guided transmural drainage of the pseudocyst was performed with a 15 mm '
            'lumen-apposing metal stent.')
NODE_FNA = 'EUS-guided fine-needle aspiration of the 12 mm celiac lymph node was performed with a 22-gauge needle.'
NODE = les('L2', 'a 12 mm celiac lymph node', ['P6'], landmark='lymph_node', site_words='lymph node', size_words='12 mm')
P6_NODE = ('EUS findings: a 9 cm unilocular pancreatic pseudocyst abutting the posterior gastric wall, without solid '
           'debris, and a 12 mm celiac lymph node.')


def f1c_unresolved():
    """Mine: F1c (the FNA of the separate pancreatic tail mass, L2) with the drainage's target naming the pseudocyst (L1)
    in words that do not tie to it ('the collection': its identity unresolved, its place unverified). L1 and L2 are
    distinct (their sizes), so the drainage is established apart from the FNA's lesion."""
    lines = dict(R.F1C_LINES, P9=P9_COLLECTION)
    mass = les('L2', 'a separate 18 mm hypoechoic mass in the pancreatic tail', ['P6'], landmark='pancreas',
               site_words='pancreatic tail', size_words='18 mm')
    fna = ev('E2', 'P7', 'fna', 'fine-needle aspiration', procedure=a('eus', 'EUS-guided', ['P7']),
             status_words='was performed', technique=a('needle', '22-gauge needle', ['P7']),
             target=tg('L2', 'pancreas', 'the pancreatic tail mass', ['P7']))
    value, text = answer(lines, [F1_EXAM, fna, drainage(target_words='the collection')], [F1_PC, mass],
                         reach_=[F1_REACH], endoscopist=ENDO)
    return inv_of(value, text)


P6B_COLLECTION = 'A 9 cm pancreatic fluid collection was also seen beside the gastric body.'
P9_FLUID = ('EUS-guided transmural drainage of the fluid collection was then performed with a 15 mm lumen-apposing metal '
            'stent.')


def possibly_same_case():
    """Mine: F1 with a second registered lesion (L2, its own line) that the identity rules cannot tell apart from the
    pseudocyst (L1: both pancreatic, both 9 cm, apart in two passages), the FNA verified to L1 and the done drainage verified
    to L2 ('the fluid collection')."""
    lines = dict(F1_LINES, P6b=P6B_COLLECTION, P9=P9_FLUID)
    lines = {pid: lines[pid] for pid in ('P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'P6b', 'P7', 'P8', 'P9', 'P10', 'P11')}
    second = les('L2', 'a 9 cm pancreatic fluid collection', ['P6b'], landmark='pancreas', site_words='pancreatic',
                 size_words='9 cm')
    fna = ev('E2', 'P7', 'fna', 'aspirated', procedure=a('eus', 'Under EUS guidance', ['P7']), status_words='was aspirated',
             technique=a('needle', '19-gauge needle', ['P7']), target=tg('L1', 'pancreas', 'the pseudocyst', ['P7']),
             purpose=a('diagnostic', 'sent for amylase and CEA', ['P7']), sequence=1)
    value, text = answer(lines, [F1_EXAM, fna, drainage(lesion='L2', target_words='the fluid collection')],
                         [F1_PC, second], reach_=[F1_REACH], endoscopist=ENDO)
    return inv_of(value, text)


def json_lists(inv):
    """(lesion id, distinct_from, possibly_same_as) of a normalized inventory's lesions."""
    return [(lesion['id'], list(lesion.get('distinct_from') or ()), list(lesion.get('possibly_same_as') or ()))
            for lesion in inv.events['lesions']]


def node_case(p9: str, drain: dict):
    lines = dict(F1_LINES, P6=P6_NODE, P7=NODE_FNA, P9=p9)
    fna = ev('E2', 'P7', 'fna', 'fine-needle aspiration', procedure=a('eus', 'EUS-guided', ['P7']),
             status_words='was performed', technique=a('needle', '22-gauge needle', ['P7']),
             target=tg('L2', 'lymph_node', 'the 12 mm celiac lymph node', ['P7']), sequence=1)
    pseudocyst = les('L1', 'a 9 cm unilocular pancreatic pseudocyst', ['P6', 'P10'], landmark='pancreas',
                     site_words='pancreatic', size_words='9 cm')
    value, text = answer(lines, [F1_EXAM, fna, drain], [pseudocyst, NODE], reach_=[F1_REACH], endoscopist=ENDO)
    return inv_of(value, text), lines


IN_DOUBT = {
    # review:eus7 problem 3's X6: the drainage verified to the FNA's lesion, its status words not binding
    'X6 status unbound': (P9, drainage(status_words='was successfully completed')),
    # review:eus7 problem 3's X3: the drainage's target tied to no lesion, unverified (landmark_missing)
    'X3 target untied': (P9, drainage(lesion='')),
    # mine: the drainage stated uncertain
    'status uncertain': (P9_UNCERTAIN, drainage(status='uncertain', status_words='may have been performed')),
    # mine: the drainage's target names the FNA's lesion, its identity not established (no lexical tie)
    'identity unresolved': (P9_COLLECTION, drainage(target_words='the collection')),
    # mine: the drainage's target tied to no lesion at a verified place ('pancreatic')
    'target untied verified': (P9_PANCREATIC, drainage(lesion='', target_words='the pancreatic pseudocyst')),
}


class ADrainageInDoubtStillMakesAStep(SimpleTestCase):
    """D177 (3): on 1b4ca399, 05a881a75 and e5628be56, 43242 is READY on X3 and X6, alone and beside 43240; c2e53f8e holds
    it [target]."""

    def assert_possible_step(self, p):
        self.assertEqual(outcome(p), (HELD, ['target'], ['E2']))
        self.assertEqual(check(p, EUS_ACT_CHECK).status, 'warn')
        self.assertIn('may be a step of the transmural drainage', reason(p, 'target'))
        self.assertIn('the document does not establish', reason(p, 'target'))
        self.assertTrue(question(p, 'target').startswith('Was the fine-needle aspiration ('))

    def test_d177_a_drainage_in_doubt_holds_the_same_lesions_fna(self):
        """Problem 3's X6 and X3, and mine (uncertain, an unresolved identity, a target tied to no lesion at a verified
        place): 43242 held [target], alone and beside 43240 (whose own outcome is the head's)."""
        for label, (p9, drain) in IN_DOUBT.items():
            inv, text = f1_with(p9, drain)
            for picks in ([('43242', F1_LINES['P7'])], [('43240', p9), ('43242', F1_LINES['P7'])]):
                result = run(inv, text, picks)
                with self.subTest(case=label, codes=[code for code, _ in picks]):
                    self.assert_possible_step(proposal(result, '43242'))
                    self.assertEqual(reviewed(result, '43242').status, HELD)

    def test_d177_the_reason_says_what_is_in_doubt(self):
        """X6 (both targets verified to L1): 'of the same structure' and the drainage done in doubt; X3: the structure in
        doubt, never 'the same structure'."""
        inv, text = f1_with(*IN_DOUBT['X6 status unbound'])
        said = reason(proposal(run(inv, text, [('43242', F1_LINES['P7'])]), '43242'), 'target')
        with self.subTest(case='X6'):
            self.assertIn('may be a step of the transmural drainage of the same structure', said)
            self.assertIn('whether that drainage was done', said)
        inv, text = f1_with(*IN_DOUBT['X3 target untied'])
        said = reason(proposal(run(inv, text, [('43242', F1_LINES['P7'])]), '43242'), 'target')
        with self.subTest(case='X3'):
            self.assertNotIn('same structure', said)
            self.assertIn('whether it was done on the structure this aspiration sampled', said)

    def test_d177_a_drainage_of_a_lesion_possibly_the_same_is_a_possible_step(self):
        """Mine: the done drainage verified to a second registered lesion (L2, 'a 9 cm pancreatic fluid collection')
        that nothing establishes apart from the FNA's pseudocyst (L1): possibly the same lesion (contract 6.3), so a
        possible step - held, where 1b4ca399 is READY."""
        inv, text = possibly_same_case()
        self.assertEqual(sorted(json_lists(inv)), [('L1', [], ['L2']), ('L2', [], ['L1'])])
        target = next(event for event in inv.events['events'] if event['id'] == 'E3')['target']
        self.assertEqual((target['lesion'], target['identity'], target['state']), ('L2', 'verified', 'verified'))
        p = proposal(run(inv, text, [('43242', F1_LINES['P7'])]), '43242')
        self.assert_possible_step(p)
        self.assertIn('whether it was done on the structure this aspiration sampled', reason(p, 'target'))

    def test_d177_the_part_of_names_a_drainage_in_doubt(self):
        """Mine: Gemini's part_of names the drainage (E3), whose status words do not bind; the FNA's own target tied to no
        lesion at a verified place ('the pancreatic pseudocyst'), so only the part_of ties the two: a possible step, held.
        Without the part_of it is READY, as on the head (the FNA's identity in doubt is D177's recorded residual)."""
        fna_target = tg('', 'pancreas', 'the pancreatic pseudocyst', ['P7'])
        drain = drainage(status_words='was successfully completed')
        inv, text = f1_with(P9, drain, part_of='E3', p7=P7_PANCREATIC, fna_target=fna_target)
        with self.subTest(case='part_of'):
            self.assert_possible_step(proposal(run(inv, text, [('43242', P7_PANCREATIC)]), '43242'))
        inv, text = f1_with(P9, drain, p7=P7_PANCREATIC, fna_target=fna_target)
        with self.subTest(case='no part_of (the residual)'):
            self.assertEqual(outcome(proposal(run(inv, text, [('43242', P7_PANCREATIC)]), '43242')),
                             ('ready', [], ['E2']))

    def test_d177_controls_a_drainage_not_done_or_apart(self):
        """Controls, READY as on the head: the drainage planned, stated not performed, or verified at another occasion
        with its status words unbound; F1c (verified to another lesion); and an FNA of a celiac lymph node beside a
        drainage tied to no lesion at a verified pancreas (the places disjoint)."""
        for label, p9, drain in (
                ('planned', P9_PLANNED, drainage(status='planned', status_words='is planned')),
                ('not performed', P9_NOT_DONE, drainage(status='not_performed', status_words='was not performed')),
                ('another occasion', P9_INDEX, drainage(status_words='was successfully completed',
                                                        time=a('earlier_encounter', 'At her index EUS on 01/14/2024',
                                                               ['P9'])))):
            inv, text = f1_with(p9, drain)
            with self.subTest(control=label):
                self.assertEqual(outcome(proposal(run(inv, text, [('43242', F1_LINES['P7'])]), '43242')),
                                 ('ready', [], ['E2']))
        inv, text = R.f1_control()
        with self.subTest(control='F1c'):
            self.assertEqual(outcome(proposal(run(inv, text, [('43242', R.F1C_LINES['P7'])]), '43242')),
                             ('ready', [], ['E2']))
        inv, text = f1c_unresolved()
        with self.subTest(control='F1c, the drainage naming the pseudocyst unresolved'):
            self.assertEqual(outcome(proposal(run(inv, text, [('43242', R.F1C_LINES['P7'])]), '43242')),
                             ('ready', [], ['E2']))
        (inv, text), lines = node_case(P9_PANCREATIC, drainage(lesion='', target_words='the pancreatic pseudocyst'))
        with self.subTest(control='lymph node beside a drainage at the pancreas'):
            self.assertEqual(outcome(proposal(run(inv, text, [('43242', lines['P7'])]), '43242')), ('ready', [], ['E2']))

    def test_d177_a_drainage_with_no_place_beside_another_lesions_fna_is_a_possible_step(self):
        """Mine, a recorded hold where the document supports 43242: the FNA of a celiac lymph node (L2) beside a drainage
        tied to no lesion whose own place is not verified (X3's drainage): nothing establishes it apart, so held."""
        (inv, text), lines = node_case(P9, drainage(lesion=''))
        self.assertEqual(outcome(proposal(run(inv, text, [('43242', lines['P7'])]), '43242')), (HELD, ['target'], ['E2']))


# --- (4) a station line that omits a station: review:eus7 problem 4 (rv_build.py X2, on cases_w7 rows 33 and 26) --------

def w7_line(line: str, fna: bool):
    """cases_w7 rows 33 and 26 (R.w7_raw's full station line) with ``line`` as the station line."""
    value, text = R.w7_raw('full', fna)
    full = R.STATIONS['full']
    value = copy.deepcopy(value)
    hits = [record for record in value['passages'] if record['text'] == full]
    assert len(hits) == 1 and text.count(full) == 1
    hits[0]['text'] = line
    return inv_of(value, text.replace(full, line))


TWO_STATIONS = {'stomach and duodenum': 'EUS imaging was performed from the stomach and duodenum.',
                'esophagus and stomach': 'EUS imaging was performed from the esophagus and stomach.',
                'esophagus and duodenum': 'EUS imaging was performed from the esophagus and duodenum only.'}
NAMED = {'stomach and duodenum': ('the stomach and the duodenum', 'the esophagus'),
         'esophagus and stomach': ('the esophagus and the stomach', 'the duodenum'),
         'esophagus and duodenum': ('the esophagus and the duodenum', 'the stomach')}


def f1_lines(lines: dict):
    """D171's F1 (part_of E3) over ``lines``."""
    fna = ev('E2', 'P7', 'fna', 'aspirated', procedure=a('eus', 'Under EUS guidance', ['P7']), status_words='was aspirated',
             technique=a('needle', '19-gauge needle', ['P7']), target=tg('L1', 'pancreas', 'the pseudocyst', ['P7']),
             purpose=a('diagnostic', 'sent for amylase and CEA', ['P7']), part_of='E3', sequence=1)
    value, text = answer(lines, [F1_EXAM, fna, f1_drainage()], [F1_PC], reach_=[F1_REACH], endoscopist=ENDO)
    return inv_of(value, text)


def two_station_question(line: str, named: str, missing: str) -> str:
    return (f'The documented endoscopic ultrasound examination (“{line}”) names {named}, not {missing}. Was '
            f'{assess.FULL_STATIONS_WORDS} performed on the date of service?')


class AStationLineThatOmitsAStationHoldsTheFullCodes(SimpleTestCase):
    """D177 (4): on 1b4ca399, 05a881a75 and e5628be56, 43259 (row 33) and 43242 (row 26, fb12 r1) are READY on
    'EUS imaging was performed from the stomach and duodenum.'; c2e53f8e holds rows 33 and 26 and READYs fb12 r1."""

    def test_d177_a_station_line_naming_two_stations_holds_43259_and_43242(self):
        """Problem 4's rows 33 and 26 and fb12 r1 (attested, its station line edited), and mine (the other two pairs)."""
        for label, line in TWO_STATIONS.items():
            named, missing = NAMED[label]
            for case, (inv, text), code, cited in (('row33', w7_line(line, False), '43259', P2),
                                                   ('row26', w7_line(line, True), '43242', P3)):
                result = run(inv, text, [(code, cited)])
                with self.subTest(stations=label, case=case):
                    p = proposal(result, code)
                    self.assertEqual((p.status, asked(p)), (HELD, ['extent']))
                    self.assertEqual(question(p, 'extent'), two_station_question(line, named, missing))
                    self.assertEqual(check(p, CLASS_CHECK).status, 'warn')
                    self.assertEqual(reviewed(result, code).status, HELD)
        line = TWO_STATIONS['stomach and duodenum']
        inv, text = R.recorded('fb12', line)
        p = proposal(run(inv, text, [('43242', FB12_FNA)]), '43242')
        with self.subTest(case='fb12 r1'):
            self.assertEqual((p.status, asked(p)), (HELD, ['extent']))
            self.assertEqual(question(p, 'extent'), two_station_question(line, *NAMED['stomach and duodenum']))

    def test_d177_a_two_station_line_never_takes_the_steps_question(self):
        """Mine: F1 (the FNA the drainage's step, part_of E3) with its station line naming the stomach and the duodenum:
        43242 keeps the step's [target], as on 1b4ca399 (the two-station hold is read last, never in place of a question
        the head asks); 43259 beside it, held by R6's 'target' and its base hold, gains [extent] (R6's question shares no
        member key with it)."""
        lines = dict(F1_LINES, P5=TWO_STATIONS['stomach and duodenum'])
        inv, text = f1_lines(lines)
        result = run(inv, text, [('43240', lines['P9']), ('43242', lines['P7']), ('43259', lines['P5'])])
        p = proposal(result, '43242')
        self.assertEqual(outcome(p), (HELD, ['target'], ['E2']))
        self.assertEqual(check(p, EUS_ACT_CHECK).status, 'warn')
        self.assertEqual(asked(proposal(result, '43259')), ['base_included', 'target', 'extent'])
        alone = proposal(run(inv, text, [('43242', lines['P7'])]), '43242')
        self.assertEqual(outcome(alone), (HELD, ['target'], ['E2']))

    def test_d177_one_station_and_a_denial_keep_d171s_words(self):
        """D171's holds come first and keep their words: one station named, and a station denied beside a two-station
        line (the denial's question, as on the head)."""
        inv, text = R.w7('duodenum_only', False)
        p = proposal(run(inv, text, [('43259', P2)]), '43259')
        with self.subTest(case='one station'):
            self.assertEqual(question(p, 'extent'),
                             R.station_question('43259', 'duodenum', R.STATIONS['duodenum_only']))
        line = TWO_STATIONS['stomach and duodenum']
        denied = 'The esophagus was not examined.'
        raw, raw_text = R.w7_raw('full', True, extra={'P9': denied},
                                 denial=('P9', 'esophagus', 'esophagus', a('current_encounter')))
        full = R.STATIONS['full']
        raw = copy.deepcopy(raw)
        next(record for record in raw['passages'] if record['text'] == full)['text'] = line
        inv, text = inv_of(raw, raw_text.replace(full, line))
        p = proposal(run(inv, text, [('43242', P3)]), '43242')
        with self.subTest(case='a denial beside two stations'):
            self.assertEqual((p.status, asked(p)), (HELD, ['extent']))
            self.assertTrue(question(p, 'extent').startswith('The document states that the esophagus was not examined'))

    def test_d177_controls_three_stations_and_d73s_reach(self):
        """Controls, unchanged: the full station line (rows 33 and 26) READY; R8_row - the recorded residual (problem 5:
        the off-contract answer, no denial event, its denial line never the examination's own words) - READY as D73's
        control pins it, where c2e53f8e holds it."""
        for case, (inv, text), code, cited in (('row33', R.w7('full', False), '43259', P2),
                                               ('row26', R.w7('full', True), '43242', P3)):
            with self.subTest(control=case):
                self.assertEqual(proposal(run(inv, text, [(code, cited)]), code).status, 'ready')
        inv, text = R.w6(R.P9_ROW8, denials=False)
        for cited in (P2, R.P9_ROW8):
            with self.subTest(control='R8_row', cited='P9' if cited == R.P9_ROW8 else 'P2'):
                self.assertEqual(proposal(run(inv, text, [('43259', cited)]), '43259').status, 'ready')


# --- (7) the step reason's claims: review:eus7 problem 7 -------------------------------------------------------------------

class TheStepReasonClaimsOnlyWhatIsEstablished(SimpleTestCase):
    """D177 (7): on 1b4ca399 the part_of-only step (the drainage's target tied to no lesion) is held [target] with a reason
    that calls the drainage 'of the same structure'."""

    def test_d177_the_part_of_alone_never_claims_the_same_structure(self):
        """Problem 7's input (D171's test_d171_the_part_of_alone_makes_a_step): no 'same structure'; F1 (both verified to
        L1) keeps D171's reason word for word."""
        inv, text = f1(drainage=f1_drainage(lesion=''))
        said = reason(proposal(run(inv, text, [('43242', F1_LINES['P7'])]), '43242'), 'target')
        with self.subTest(case='part_of alone'):
            self.assertTrue(said.startswith('The document gives this fine-needle aspiration ('))
            self.assertIn('as a step of the transmural drainage (“EUS-guided transmural drainage', said)
            self.assertNotIn('same structure', said)
        inv, text = f1()
        said = reason(proposal(run(inv, text, [('43242', F1_LINES['P7'])]), '43242'), 'target')
        with self.subTest(case='F1'):
            self.assertIn('as a step of the transmural drainage of the same structure (“', said)
            self.assertNotIn('may be a step', said)
