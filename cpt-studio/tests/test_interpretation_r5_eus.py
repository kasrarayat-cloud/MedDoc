"""DECISIONS D120-D123 (the Gemini migration's round 5: the round-4 EUS parity audit's gaps 0, 1 and 2, and the round-4
review of D96's problems 0, 1 and 2), SYNTHETIC, each built from its source's own input. Nothing is sent.
- D121 (gap 1): an EUS told only through its done act - an FNA, an injection or a drainage, with no EUS examination
  event - placed nowhere lower is an upper EUS for C-4: today's EGD is its endoscopic portion, so 43235 is held
  base_included beside 43242, 43238, 43253 or 43240, and alone, as the installed release (c2e53f8e) holds it; with no
  proposal the EGD asks no code of its own, as there. An act whose family is in doubt (D87), or that is only possibly of
  this encounter (D62), is a possible upper EUS.
- D123 (problem 0): an act verified at an organ of its own is placed at that organ, whatever its target words name beside
  it - 'pancreatic pseudocyst abutting the transverse colon' no longer makes the EUS lower (d353e64df: 43235 READY
  beside 43240).
- D123 (problems 1 and 2): a done act filed under the EUS that is not the EUS's own - a forceps biopsy, or an FNA whose
  procedure words are missing - placed lower where nothing else places the EUS is a doubt: the EGD keeps its own items
  and second-review mark, and 43235 is held (D70's possibly_part_of), never READY.
- D120 (gap 0): 43240's defining-target requirement - a drainage supports it only where its verified target words or its
  verified lesion's words name a pancreatic fluid collection, never at the gallbladder, a bile duct or the liver. The
  requirement is mapping.defining_target; within this repair's files nothing reads it yet (see DECISIONS D120), so these
  pins hold the requirement itself, not an engine outcome.
Each test asserts in independent subtests - the outcome, the read-time overlay, the structure - so a regression shows
every one it breaks."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import coverage, events, identity, mapping
from tests.test_interpretation_events import exam, inventory, reached, run
from tests.test_interpretation_identity import a, act, les, tg
from tests.test_interpretation_r3_eus import DUODENUM, GASTRO, SEPARATELY, egd_item
from tests.test_interpretation_r3_integration_d88_d93 import BESIDE_43242, egd_coding, items
from tests.test_interpretation_r4_eus_lower import held_beside, lower_ids, ready_unheld, sessions_of


def beside(code: str) -> str:
    return f'Is 43235 reported separately from {code} for this examination?'


# --- D121 (the parity audit, EUS gap 1): an EUS told only through its done act ---------------------------------------

REPORT = 'UPPER ENDOSCOPY REPORT'
UPPER = ('The gastroscope was advanced to the second portion of the duodenum; the esophagus, stomach and duodenum were '
         'normal.')
UPPER_Q = 'The gastroscope was advanced to the second portion of the duodenum'
FNA_ONLY = 'EUS-FNA of a 22 mm hypoechoic mass in the pancreatic body was performed with a 22-gauge needle.'
CELIAC = 'An EUS-guided celiac plexus block was then performed with bupivacaine and triamcinolone.'
DRAIN_ONLY = ('EUS-guided transmural drainage of a 9 cm pancreatic pseudocyst was then performed from the stomach with a '
              '15 mm lumen-apposing metal stent.')
RECTAL_ONLY = 'EUS-FNA of a 2 cm mass in the rectal wall was performed with a 22-gauge needle.'
BODY_MASS = les('L1', '22 mm hypoechoic mass', 'P3', landmark='pancreas', site_words='pancreatic body',
                size_words='22 mm')


def eus_act_event(kind: str, procedure=None) -> tuple:
    """(E2, its line, its lesions): the gap's act told on its own line (P3) - its procedure 'eus' from its own words
    unless ``procedure`` says otherwise."""
    if kind == 'fna':
        return act('E2', 'P3', 'fna', 'EUS-FNA', status_words='was performed',
                   procedure=procedure or a('eus', 'EUS-FNA', ['P3']), technique=a('needle', '22-gauge needle', ['P3']),
                   target=tg('L1', 'pancreas', 'a 22 mm hypoechoic mass in the pancreatic body', ['P3'])), FNA_ONLY, \
            (BODY_MASS,)
    if kind == 'injection':
        return act('E2', 'P3', 'injection', 'celiac plexus block', status_words='was then performed',
                   procedure=procedure or a('eus', 'EUS-guided', ['P3']),
                   target=tg('', 'other', 'celiac plexus', ['P3'])), CELIAC, ()
    if kind == 'drainage':
        return act('E2', 'P3', 'drainage', 'transmural drainage', status_words='was then performed',
                   procedure=procedure or a('eus', 'EUS-guided', ['P3']),
                   technique=a('stent', 'lumen-apposing metal stent', ['P3']),
                   target=tg('', 'pancreas', 'pancreatic pseudocyst', ['P3'])), DRAIN_ONLY, ()
    return act('E2', 'P3', 'fna', 'EUS-FNA', status_words='was performed', procedure=procedure or a('eus', 'EUS-FNA', ['P3']),
               technique=a('needle', '22-gauge needle', ['P3']),
               target=tg('', 'rectum', 'mass in the rectal wall', ['P3'])), RECTAL_ONLY, ()


def egd_and_eus_act(kind: str = 'fna', *, procedure=None, examination: bool = False):
    """The gap's document (audit battery 4, g2b/g2c): the report heading (P1), the EGD to the second portion of the
    duodenum (E1, its procedure from the heading) and the EUS's one act (E2, P3) of ``kind`` ('fna': the pancreatic body
    mass; 'injection': the celiac plexus block; 'drainage': a pancreatic pseudocyst; 'rectal': an FNA of the rectal
    wall) - no EUS examination event, unless ``examination`` (the control: E3, the EUS examination named by the act's
    line)."""
    found_act, line, lesions = eus_act_event(kind, procedure)
    found = [exam('E1', 'P2', words='gastroscope', procedure=a('egd', 'UPPER ENDOSCOPY', ['P1'])), found_act]
    if examination:
        found.append(act('E3', 'P3', 'examination', 'EUS', status_words='was performed',
                         procedure=a('eus', 'EUS', ['P3'])))
    return inventory({'P1': REPORT, 'P2': UPPER, 'P3': line}, events=found, lesions=list(lesions),
                     reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2')])


CODES_BESIDE = {'fna': (('43242', FNA_ONLY), ('43238', FNA_ONLY)), 'injection': (('43253', CELIAC),),
                'drainage': (('43240', DRAIN_ONLY),)}


class AnEusToldOnlyByItsActIsAnUpperEus(SimpleTestCase):
    """D121 (gap 1): c2e53f8e holds 43235 base_included beside the EUS code and alone; d353e64df READYs it, and lists
    the EGD's own no_proposal item with no proposal (the installed release does not)."""

    def test_d121_43235_beside_the_eus_code_of_its_act_is_held_base_included(self):
        for kind, codes in CODES_BESIDE.items():
            inv, text = egd_and_eus_act(kind)
            reading = events.Reading.of(inv)
            with self.subTest(kind=kind, part='fixture'):  # the gap's: a done EUS act, and no EUS examination event
                self.assertTrue(coverage.eus_act(reading.events['E2']))
                self.assertEqual([event['id'] for event in reading.events.values()
                                  if event.get('family') == 'gi.eus' and event['catalogue_kind'] == 'eus_exam'], [])
            for code, line in codes:
                result = run(inv, text, [('43235', UPPER_Q), (code, line)])
                with self.subTest(kind=kind, code=code, part='assess'):  # d353e64df: READY
                    held_beside(self, result, '43235', (code,), beside(code))
                with self.subTest(kind=kind, code=code, part='event_coding'):
                    self.assertEqual(egd_coding(result), ('gi.eus', ''))
                    self.assertEqual(result.completeness['included_by'], {'gi.egd': [code]})
            with self.subTest(kind=kind, part='alone'):  # d353e64df: READY
                held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)
            with self.subTest(kind=kind, part='structure'):
                sessions = coverage.sessions(reading)
                self.assertEqual((sessions['gi.eus'].event, sessions['gi.eus'].examinations, sessions['gi.eus'].done),
                                 ('', (), True))
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('gi.eus', ''))

    def test_d121_with_no_proposal_the_egd_asks_no_code_of_its_own(self):
        """The installed release marks the EGD included in the EUS service its act makes and lists the EUS's item alone;
        d353e64df listed the EGD's own no_proposal item with its second-review mark too."""
        for kind in CODES_BESIDE:
            with self.subTest(kind=kind):
                result = run(*egd_and_eus_act(kind), [])
                self.assertEqual(items(result), [('gi.eus', 'no_proposal', True)])
                self.assertIsNone(egd_item(result))

    def test_d121_controls_an_examination_event_and_a_rectal_act(self):
        """The audit's control (g2b_withexam: an EUS examination event beside the act) holds 43235 as before. An act-only
        EUS placed in the rectum is a lower EUS: the EGD is a service of its own and 43235 is READY (as with a rectal
        examination, D88)."""
        inv, text = egd_and_eus_act('fna', examination=True)
        with self.subTest(control='examination'):
            self.assertEqual(sessions_of(inv)['gi.eus'].event, 'E3')
            held_beside(self, run(inv, text, [('43235', UPPER_Q), ('43242', FNA_ONLY)]), '43235', ('43242',),
                        BESIDE_43242)
        inv, text = egd_and_eus_act('rectal')
        with self.subTest(control='rectal', part='structure'):
            self.assertEqual(lower_ids(inv), ['E2'])
            self.assertEqual((sessions_of(inv)['gi.egd'].part_of, sessions_of(inv)['gi.egd'].possibly_part_of), ('', ''))
        with self.subTest(control='rectal', part='assess'):
            ready_unheld(self, run(inv, text, [('43235', UPPER_Q)]), '43235')
        with self.subTest(control='rectal', part='items'):
            self.assertEqual(items(run(inv, text, [])), [('gi.egd', 'no_proposal', True), ('gi.eus', 'no_proposal', True)])

    def test_d121_an_act_whose_family_is_in_doubt_is_a_possible_upper_eus(self):
        """D87 on D121's own input: the FNA filed under 'eus' with no procedure words (procedure_unsettled beside the EGD)
        is a doubt, never the session - the EGD keeps its own item, and 43235 is held base_included through D70's doubt,
        never READY (d353e64df: READY)."""
        inv, text = egd_and_eus_act('fna', procedure=a('eus'))
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            fna = reading.events['E2']
            self.assertEqual((fna['procedure']['state'], fna['procedure']['reasons'], events.done(fna),
                              coverage.eus_act(fna)), ('unverified', ['procedure_unsettled'], True, False))
            self.assertEqual([event['id'] for event in coverage.doubted_eus_acts(reading)], ['E2'])
        with self.subTest(part='structure'):
            sessions = coverage.sessions(reading)
            self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
        with self.subTest(part='alone'):
            held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)
        with self.subTest(part='items'):
            self.assertEqual(egd_item(run(inv, text, [])), ('no_proposal', True))

    def test_d121_an_act_only_possibly_of_this_encounter_is_a_possible_upper_eus(self):
        """D62 on D121's own input (the build's sibling probe): 'After the EGD, EUS-FNA of ...' - the FNA's time
        unanchored, so possibly current and not done - is a doubt: 43235 is held base_included through D70's doubt and
        the EGD keeps its own item (d353e64df: READY beside 43242 and alone; c2e53f8e: held base_included)."""
        line = f'After the EGD, {FNA_ONLY}'
        found_act, _, lesions = eus_act_event('fna')
        found_act = dict(found_act, time=a('current_encounter', 'After the EGD', ['P3']))
        inv, text = inventory({'P1': REPORT, 'P2': UPPER, 'P3': line}, events=[
            exam('E1', 'P2', words='gastroscope', procedure=a('egd', 'UPPER ENDOSCOPY', ['P1'])), found_act],
            lesions=list(lesions), reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2')])
        reading = events.Reading.of(inv)
        with self.subTest(part='fixture'):
            fna = reading.events['E2']
            self.assertEqual((fna['time']['state'], fna['time']['reasons'], events.done(fna),
                              coverage.possibly_current(fna)), ('unverified', ['current_unanchored'], False, True))
            self.assertEqual([event['id'] for event in coverage.possible_eus_acts(reading)], ['E2'])
        with self.subTest(part='structure'):
            sessions = coverage.sessions(reading)
            self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
        with self.subTest(part='assess'):  # the EUS session has no done event, so 43242 is matched to none
            held_beside(self, run(inv, text, [('43235', UPPER_Q), ('43242', line)]), '43235', (), SEPARATELY)
        with self.subTest(part='alone'):
            held_beside(self, run(inv, text, [('43235', UPPER_Q)]), '43235', (), SEPARATELY)
        with self.subTest(part='items'):
            self.assertEqual(egd_item(run(inv, text, [])), ('no_proposal', True))


# --- D123, problem 0: an act verified at an organ of its own is at that organ ------------------------------------------

EGD = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
EUS = 'EUS: a linear echoendoscope was then advanced to the stomach and the duodenum.'
EUS_AFTER = 'After the EGD, a linear echoendoscope was advanced to the stomach and the duodenum.'
TRANSVERSE = ('Transgastric drainage of a 10 cm pancreatic pseudocyst abutting the transverse colon was performed with a '
              'lumen-apposing metal stent.')
TRANSVERSE_E = ('A 10 cm pancreatic pseudocyst abutting the transverse colon was drained transgastrically with a '
                'lumen-apposing metal stent.')
NECROSIS = ('Transgastric drainage of walled-off necrosis in the pancreatic tail abutting the splenic flexure was performed '
            'with a lumen-apposing metal stent.')
TAIL = 'A 28 mm hypoechoic mass in the pancreatic tail adjacent to the splenic flexure was sampled with a 22-gauge needle.'
TAIL_EUS = ('EUS-guided fine-needle aspiration of a 28 mm hypoechoic mass in the pancreatic tail adjacent to the splenic '
            'flexure was performed with a 22-gauge needle.')
TAIL_WORDS = 'mass in the pancreatic tail adjacent to the splenic flexure'


def upper_eus(line: str, found_act: dict, *, after_egd: bool = False):
    """The review's document: the EGD (E1, P1), the upper EUS examination (E2, P2: the stomach and the duodenum, reach
    the duodenum; 'After the EGD, ...' with ``after_egd``: its time unanchored, D70's doubt) and one act (E3, P3)."""
    options = dict(procedure=a('eus', 'linear echoendoscope' if after_egd else 'EUS', ['P2']),
                   technique=a('endoscope', 'linear echoendoscope', ['P2']))
    if after_egd:
        options['time'] = a('current_encounter', 'After the EGD', ['P2'])
    found = [exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'EGD', ['P1'])),
             act('E2', 'P2', 'examination', 'linear echoendoscope',
                 status_words='was advanced' if after_egd else 'was then advanced', **options), found_act]
    return inventory({'P1': EGD, 'P2': EUS_AFTER if after_egd else EUS, 'P3': line}, events=found,
                     reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P1'),
                            reached('E2', 'duodenum', 'duodenum', 'P2')])


def drained(words: str, kind_words: str = 'drainage', status_words: str = 'was performed') -> dict:
    return act('E3', 'P3', 'drainage', kind_words, status_words=status_words, procedure=a('eus', 'EUS', ['P2']),
               technique=a('stent', 'lumen-apposing metal stent', ['P3']), target=tg('', 'pancreas', words, ['P3']))


def sampled(words: str, procedure=None, kind_words: str = 'sampled', status_words: str = 'was sampled') -> dict:
    return act('E3', 'P3', 'fna', kind_words, status_words=status_words,
               procedure=procedure or a('eus', 'EUS', ['P2']), technique=a('needle', '22-gauge needle', ['P3']),
               target=tg('', 'pancreas', words, ['P3']))


PROBLEM_0 = {  # the review's inputs (A3, its two rewordings, and the FNA forms)
    'pseudocyst_transverse': (TRANSVERSE, drained('pancreatic pseudocyst abutting the transverse colon'), '43240'),
    'reworded': (TRANSVERSE_E, drained('pancreatic pseudocyst abutting the transverse colon', 'drained',
                                       'was drained'), '43240'),
    'necrosis_splenic': (NECROSIS, drained('walled-off necrosis in the pancreatic tail abutting the splenic flexure'),
                         '43240'),
    'fna_splenic': (TAIL, sampled(TAIL_WORDS), '43242'),
}


class AnActVerifiedAtAnOrganIsAtThatOrgan(SimpleTestCase):
    """D123 (problem 0): d353e64df read the colon landmark named beside the act's own organ landmark - the EUS became
    lower and 43235 was READY (complete_pending_review); 437b708bb and c2e53f8e hold it base_included."""

    def test_d123_words_naming_a_colon_landmark_beside_the_pancreas_never_free_43235(self):
        for name, (line, found_act, code) in PROBLEM_0.items():
            inv, text = upper_eus(line, found_act)
            reading = events.Reading.of(inv)
            with self.subTest(case=name, part='fixture'):  # the review's: the act verified at the pancreas
                event = reading.events['E3']
                self.assertEqual((event['target']['state'], mapping.target_landmark(event)), ('verified', 'pancreas'))
                self.assertEqual(coverage.eus_places(event), ['pancreas'])
            result = run(inv, text, [('43235', EGD), (code, line)])
            with self.subTest(case=name, part='assess'):  # d353e64df: READY with no question
                held_beside(self, result, '43235', (code,), beside(code))
            with self.subTest(case=name, part='structure'):
                self.assertEqual(lower_ids(inv), ['E2', 'E3'])
                self.assertEqual(egd_coding(result), ('gi.eus', ''))
            with self.subTest(case=name, part='alone'):  # d353e64df: READY
                held_beside(self, run(inv, text, [('43235', EGD)]), '43235', (), SEPARATELY)

    def test_d123_the_same_words_never_cancel_d70s_doubt(self):
        """The review's second route: today's EUS only possibly current ('After the EGD, ...'), its done FNA's words
        naming the splenic flexure beside the pancreas (d353e64df: READY; 437b708bb: held)."""
        inv, text = upper_eus(TAIL_EUS, sampled(TAIL_WORDS, a('eus', 'EUS-guided', ['P3']), 'fine-needle aspiration',
                                                'was performed'), after_egd=True)
        with self.subTest(part='structure'):
            sessions = sessions_of(inv)
            self.assertEqual((sessions['gi.eus'].examinations, sessions['gi.eus'].possible), ((), ('E2',)))
            self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
        with self.subTest(part='assess'):
            held_beside(self, run(inv, text, [('43235', EGD), ('43242', TAIL_EUS)]), '43235', ('43242',), BESIDE_43242)

    def test_d123_controls_words_are_still_read_at_a_node(self):
        """Finding 12's repair stands (D96): at the verified landmark 'lymph_node' the act's own words are read, and 'in
        the rectum' places it lower; at an organ of the lower tract the landmark itself does."""
        for name, landmark in (('lymph_node', 'lymph_node'), ('rectum', 'rectum')):
            event = act('E3', 'P3', 'fna', 'sampled', status_words='was sampled', procedure=a('eus', 'EUS', ['P2']),
                        target=tg('', landmark, 'a perirectal lymph node in the rectum', ['P3']))
            inv, _ = upper_eus('Radial EUS: a perirectal lymph node in the rectum was sampled with a 22-gauge needle.',
                               event)
            with self.subTest(landmark=name):
                fna = events.Reading.of(inv).events['E3']
                self.assertEqual(fna['target']['state'], 'verified')
                self.assertIn('rectum', coverage.eus_places(fna))
                self.assertEqual(sessions_of(inv)['gi.egd'].part_of, '')


# --- D123, problems 1 and 2: a done act filed under the EUS that is not the EUS's own -----------------------------------

RADIAL_FORCEPS = 'Radial EUS was then performed; forceps biopsies of the rectal mass were taken.'
RECTAL_FNA = 'Radial EUS was then performed; a perirectal lymph node in the rectum was sampled with a 22-gauge needle.'


def radial(line: str, found_act: dict):
    """D88's document shape (the review's B1 and C1): the gastroscope (E1, P1), a radial EUS naming no place (E2, P2)
    and its act (E3, P2)."""
    return inventory({'P1': GASTRO, 'P2': line}, events=[
        exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1'])),
        exam('E2', 'P2', words='Radial EUS', status_words='was then performed', procedure=a('eus', 'Radial EUS', ['P2'])),
        found_act], reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P1')])


def forceps() -> dict:
    """Problem 1's E3: forceps biopsies of the rectal mass, filed under the EUS ('Radial EUS'), target the rectum."""
    return act('E3', 'P2', 'biopsy', 'biopsies', status_words='were taken', procedure=a('eus', 'Radial EUS', ['P2']),
               technique=a('forceps', 'forceps', ['P2']), target=tg('', 'rectum', 'rectal mass', ['P2']))


def rectal_fna(procedure: dict) -> dict:
    """Problem 2's E3 (D88's pinned FNA): the perirectal node in the rectum, its procedure ``procedure``."""
    return act('E3', 'P2', 'fna', 'sampled', status_words='was sampled', procedure=procedure,
               technique=a('needle', '22-gauge needle', ['P2']), target=tg('', 'rectum', 'rectum', ['P2']))


DOUBTED_LOWER = {'forceps_biopsy': (RADIAL_FORCEPS, forceps), 'fna_procedure_unworded': (RECTAL_FNA,
                                                                                         lambda: rectal_fna(a('eus')))}


class ADoubtedLowerActIsADoubtNeverAFact(SimpleTestCase):
    """D123 (problems 1 and 2): with no proposal, c2e53f8e and 437b708bb list the EGD's own no_proposal item with its
    second-review mark; d353e64df read the EGD as the radial EUS's endoscopic portion and dropped them (included_by
    {gi.egd: []}), holding 43235 alone base_included on that premise."""

    def test_d123_the_egd_keeps_its_own_item_and_second_review_mark(self):
        for name, (line, build) in DOUBTED_LOWER.items():
            inv, text = radial(line, build())
            reading = events.Reading.of(inv)
            with self.subTest(case=name, part='fixture'):  # the review's: a done act at the rectum, no EUS act
                event = reading.events['E3']
                self.assertEqual((events.done(event), mapping.target_landmark(event), coverage.eus_act(event)),
                                 (True, 'rectum', False))
                self.assertEqual([item['id'] for item in coverage.doubted_eus_acts(reading)], ['E3'])
                self.assertEqual(lower_ids(inv), ['E2'])
            result = run(inv, text, [])
            with self.subTest(case=name, part='completeness'):
                self.assertEqual(egd_item(result), ('no_proposal', True))
                self.assertEqual(result.completeness['included_by'], {})
            with self.subTest(case=name, part='structure'):
                sessions = coverage.sessions(reading)
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
                self.assertEqual(egd_coding(result), ('', 'gi.eus'))

    def test_d123_43235_stays_held_never_ready(self):
        """43235 alone is held with C-4's question through D70's doubt - never READY: c2e53f8e holds it (performed_status
        and extent), and the act may be the radial EUS's."""
        for name, (line, build) in DOUBTED_LOWER.items():
            inv, text = radial(line, build())
            with self.subTest(case=name):
                held_beside(self, run(inv, text, [('43235', GASTRO)]), '43235', (), SEPARATELY)

    def test_d123_controls_a_settled_act_and_an_eus_placed_upper(self):
        """The same FNA with its procedure worded ('Radial EUS') is the EUS's own act and places it lower (D88): the EGD
        keeps its items and 43235 is READY, as before. A doubted rectal act beside an EUS its own done events place in the
        upper tract (D96's finding 2) leaves C-4's reading as it was: the EGD is the EUS's endoscopic portion."""
        inv, text = radial(RECTAL_FNA, rectal_fna(a('eus', 'Radial EUS', ['P2'])))
        with self.subTest(control='settled'):
            self.assertEqual(lower_ids(inv), ['E2', 'E3'])
            self.assertEqual((sessions_of(inv)['gi.egd'].part_of, sessions_of(inv)['gi.egd'].possibly_part_of), ('', ''))
            ready_unheld(self, run(inv, text, [('43235', GASTRO)]), '43235')
        placed = act('E4', 'P3', 'biopsy', 'biopsies', status_words='were taken', procedure=a('eus', 'EUS', ['P2']),
                     technique=a('forceps', 'forceps', ['P3']), target=tg('', 'rectum', 'rectal mass', ['P3']))
        inv, text = inventory({'P1': EGD, 'P2': EUS, 'P3': 'Forceps biopsies of the rectal mass were taken.'}, events=[
            exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'EGD', ['P1'])),
            act('E2', 'P2', 'examination', 'linear echoendoscope', status_words='was then advanced',
                procedure=a('eus', 'EUS', ['P2']), technique=a('endoscope', 'linear echoendoscope', ['P2'])), placed],
            reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P1'), reached('E2', 'duodenum', 'duodenum', 'P2')])
        with self.subTest(control='placed_upper'):
            self.assertEqual([item['id'] for item in coverage.doubted_eus_acts(events.Reading.of(inv))], ['E4'])
            self.assertEqual((sessions_of(inv)['gi.egd'].part_of, sessions_of(inv)['gi.egd'].possibly_part_of),
                             ('gi.eus', ''))
            held_beside(self, run(inv, text, [('43235', EGD)]), '43235', (), SEPARATELY)

    def test_d123_no_kind_and_no_examination_are_doubted_acts(self):
        """D96's finding 0 stays as pinned: a rectal medication read as 'other' (no catalogue kind) and a digital rectal
        examination are no acts here, and leave C-4's reading of the upper EUS unchanged."""
        medication = act('E3', 'P3', 'other', 'indomethacin', status_words='was administered',
                         procedure=a('eus', 'EUS', ['P2']), target=tg('', 'rectum', 'Rectal', ['P3']))
        inv, _ = upper_eus('Rectal indomethacin 100 mg was administered before the procedure.', medication)
        reading = events.Reading.of(inv)
        self.assertEqual(coverage.doubted_eus_acts(reading), [])
        self.assertEqual(sessions_of(inv)['gi.egd'].part_of, 'gi.eus')


# --- D120 (the parity audit, EUS gap 0): 43240's defining-target requirement -------------------------------------------

DRAINAGE_LINES = {
    'gallbladder': 'EUS-guided transmural drainage of the gallbladder was performed from the duodenal bulb with a 15 mm '
                   'lumen-apposing metal stent.',
    'bile_duct': 'EUS-guided transmural drainage of the common bile duct was performed from the duodenal bulb with a 6 mm '
                 'lumen-apposing metal stent.',
    'hepatic_duct': 'EUS-guided transmural drainage of the left hepatic duct was performed from the stomach with a fully '
                    'covered metal stent.',
    'liver_abscess': 'EUS-guided transmural drainage of the liver abscess was performed from the stomach with a 10 Fr '
                     'double pigtail stent.',
    'pseudocyst': 'EUS-guided transmural drainage of the pseudocyst was performed from the stomach with a 15 mm '
                  'lumen-apposing metal stent.',
    'necrosis': 'EUS-guided transmural drainage of the walled-off necrosis was performed with a 20 mm lumen-apposing '
                'metal stent.',
    'by_lesion': 'EUS-guided transmural drainage of the 9 cm lesion was performed with a 15 mm lumen-apposing metal '
                 'stent.',
}
DRAINAGE_FINDINGS = {'pseudocyst': 'A 9 cm pancreatic pseudocyst was seen abutting the posterior gastric wall.',
                     'liver_abscess': 'A 6 cm abscess was seen in the left lobe of the liver.',
                     'necrosis': 'A 12 cm walled-off pancreatic necrosis was seen abutting the posterior gastric wall.',
                     'by_lesion': 'A 9 cm pancreatic pseudocyst was seen abutting the posterior gastric wall.'}
# name: (target landmark, target words, the lesion (words, landmark, site words, size words) or None) - the audit's
# answers
DRAINAGE_TARGETS = {
    'gallbladder': ('gallbladder', 'the gallbladder', None),
    'bile_duct': ('common_bile_duct', 'the common bile duct', None),
    'hepatic_duct': ('bile_duct', 'the left hepatic duct', None),
    'liver_abscess': ('liver', 'the liver abscess', ('A 6 cm abscess', 'liver', 'left lobe of the liver', '6 cm')),
    'pseudocyst': ('pancreas', 'the pseudocyst', ('A 9 cm pancreatic pseudocyst', 'pancreas', 'pancreatic', '9 cm')),
    'necrosis': ('pancreas', 'the walled-off necrosis', ('A 12 cm walled-off pancreatic necrosis', 'pancreas',
                                                         'pancreatic', '12 cm')),
    'by_lesion': ('pancreas', 'the 9 cm lesion', ('A 9 cm pancreatic pseudocyst', 'pancreas', 'pancreatic', '9 cm')),
}


def drainage_case(name: str, with_lesion: bool = True):
    """The audit's battery-1/2/3 drainages (g1_gallbladder, drn_cds_bile_duct, drn_hgs_liver, drn_liver_abscess,
    g1_pseudocyst, drn_won_necrosis), each the EUS examination (E1, P1) and the drainage (E2, P3), with the finding
    line (P2) and its lesion L1 where the answer gives one (unless not ``with_lesion``); 'by_lesion': the pseudocyst's
    lesion, the drainage's own target words naming no collection ('the 9 cm lesion': a reference and a size, verified
    through the lesion)."""
    landmark, words, lesion = DRAINAGE_TARGETS[name]
    lesion = lesion if with_lesion else None
    lines = {'P1': 'The linear echoendoscope was advanced to the stomach.',
             'P2': DRAINAGE_FINDINGS.get(name, 'The structure was distended.'), 'P3': DRAINAGE_LINES[name]}
    lesions = [les('L1', lesion[0], 'P2', landmark=lesion[1], site_words=lesion[2], size_words=lesion[3])
               ] if lesion else []
    found = [exam('E1', 'P1', words='linear echoendoscope', procedure=a('eus', 'echoendoscope', ['P1'])),
             act('E2', 'P3', 'drainage', 'transmural drainage', status_words='was performed',
                 procedure=a('eus', 'EUS-guided', ['P3']), technique=a('stent', 'stent', ['P3']),
                 target=tg('L1' if lesion else '', landmark, words, ['P3']))]
    return inventory(lines, events=found, lesions=lesions, reach=[reached('E1', 'stomach', 'stomach', 'P1')])


def meets(name: str) -> bool:
    reading = events.Reading.of(drainage_case(name)[0])
    drainage = reading.events['E2']
    return mapping.defining_target('43240', drainage, reading.lesions.get(identity.verified_lesion(drainage)))


class TheDefiningTargetOf43240(SimpleTestCase):
    """D120 (gap 0), the requirement itself: c2e53f8e holds every 43240 [performed_status, target]; d353e64df READYs it
    on any drainage. Nothing in this repair's files reads the requirement yet (DECISIONS D120)."""

    def test_d120_the_requirement_is_43240s_alone(self):
        self.assertEqual(dict(mapping.DEFINING_TARGETS), {'43240': mapping.PANCREATIC_FLUID_COLLECTION})
        self.assertEqual(mapping.DEFINING['43240'], ('drainage',))
        reading = events.Reading.of(drainage_case('gallbladder')[0])
        for code in ('43242', '43253', '43259', '43235'):
            with self.subTest(code=code):
                self.assertTrue(mapping.defining_target(code, reading.events['E2']))

    def test_d120_a_drainage_of_another_target_never_meets_it(self):
        for name in ('gallbladder', 'bile_duct', 'hepatic_duct', 'liver_abscess'):
            with self.subTest(target=name):
                self.assertFalse(meets(name))

    def test_d120_a_drainage_naming_a_pancreatic_fluid_collection_meets_it(self):
        """By its own target words ('the pseudocyst', 'the walled-off necrosis', problem 0's 'pancreatic pseudocyst
        abutting the transverse colon') or by the words of its verified lesion ('A 9 cm pancreatic pseudocyst'); a
        drainage whose words name none and whose lesion is not verified does not (fails closed)."""
        for name in ('pseudocyst', 'necrosis', 'by_lesion'):
            with self.subTest(target=name):
                self.assertTrue(meets(name))
        reading = events.Reading.of(upper_eus(TRANSVERSE, drained('pancreatic pseudocyst abutting the transverse colon'))
                                    [0])
        with self.subTest(target='problem_0'):
            self.assertTrue(mapping.defining_target('43240', reading.events['E3']))
        unverified = drainage_case('by_lesion')[0]
        reading = events.Reading.of(unverified)
        drainage = dict(reading.events['E2'], target={**reading.events['E2']['target'], 'identity': 'unresolved'})
        with self.subTest(target='lesion_not_verified'):
            self.assertEqual(identity.verified_lesion(drainage), '')
            self.assertFalse(mapping.defining_target('43240', drainage, None))
        reading = events.Reading.of(drainage_case('necrosis', with_lesion=False)[0])
        with self.subTest(target='target_unverified'):  # 'the walled-off necrosis' does not name the pancreas
            self.assertEqual(reading.events['E2']['target']['state'], 'unverified')
            self.assertFalse(mapping.defining_target('43240', reading.events['E2']))

    def test_d120_a_verified_place_at_the_biliary_tree_or_the_liver_sets_it_apart(self):
        """Words naming a pseudocyst never outweigh a verified place of another drainage (the gallbladder, a bile duct,
        the liver): held, never READY."""
        reading = events.Reading.of(drainage_case('gallbladder')[0])
        drainage = reading.events['E2']
        named = dict(drainage, target={**drainage['target'], 'words': {**drainage['target']['words'],
                                                                       'text': 'the pseudocyst beside the gallbladder'}})
        self.assertFalse(mapping.defining_target('43240', named))
