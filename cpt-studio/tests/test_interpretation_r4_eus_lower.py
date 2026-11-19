"""DECISIONS D96 and D97 (the Gemini migration's round-4 refutation, findings 0, 2, 10 and 12), SYNTHETIC, each built from
its finding's own input:
- D96: C-4 reads the lower tract only from today's DONE endoscopic EUS examinations (never a digital or manual
  examination, FINAL 5.6 E13) and today's DONE EUS ACTS of the EUS's own kinds (the catalogue's gi.eus acts: the
  fine-needle aspiration or biopsy, an injection, a drainage) whose procedure is usable as 'eus' - and an act's place is
  its verified target landmark or a lower-tract landmark its own verified target words name:
  * finding 0: a digital rectal examination filed under the EUS heading (the attested C2MEM-029 r1 E9 form), or a
    rectal medication read as an EUS event of kind 'other', made the EUS session lower - 43235 was READY beside 43242
    where the installed release (c2e53f8e) and the control hold it base_included;
  * finding 2: a done rectal act whose family is in doubt (its procedure 'eus' unsettled) did the same;
  * finding 12: D88's own sentence with the FNA's target at the verified landmark 'lymph_node' and the words 'a
    perirectal lymph node in the rectum' read nowhere lower - today's EGD lost its own no_proposal item and
    second-review mark, and 43235 alone was held base_included on a false premise.
- D97 (finding 10): an EUS examination whose KIND is not usable (kind words that do not locate) was skipped by C-4 - the
  EUS session had no examination and 43235 was READY beside 43242. It is a POSSIBLE upper EUS examination (D70's doubt,
  possibly_part_of 'gi.eus') unless it is itself placed lower: 43235 is held base_included, never READY.
Each test asserts in independent subtests - the outcome, the read-time overlay, the structure - so a regression shows
every one it breaks. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.gi import catalogue
from studio.interpretation import coverage, events, mapping
from tests.test_interpretation_events import asked, check, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, les, tg
from tests.test_interpretation_r3_eus import DUODENUM, GASTRO, SEPARATELY, egd_item
from tests.test_interpretation_r3_integration_d88_d93 import (BASE_INCLUDED, BESIDE_43242, RECTAL_FNA, base_held,
                                                              egd_coding, items, reviewed)


def sessions_of(inv) -> dict:
    return coverage.sessions(events.Reading.of(inv))


def lower_ids(inv) -> list:
    return [event['id'] for event in coverage.lower_evidence(events.Reading.of(inv))]


def held_beside(test, result, code: str, others: tuple, question: str) -> None:
    """``code`` (43235) is held with C-4's base_included question at assess time, and the read-time overlay keeps it
    held with the same question, releasing nothing."""
    base_held(test, proposal(result, code), others, question)
    view = reviewed(result, code)
    test.assertEqual((view.status, view.released, view.recomputed), ('needs_clarification', (), ()))
    test.assertEqual([q['question'] for q in view.questions], [question])


def ready_unheld(test, result, code: str) -> None:
    """``code`` is READY with no question and no base-within check, at assess time and in the read-time overlay."""
    p = proposal(result, code)
    test.assertIsNone(check(p, BASE_INCLUDED))
    test.assertEqual((p.status, asked(p)), ('ready', []))
    view = reviewed(result, code)
    test.assertEqual((view.status, view.released, view.recomputed), ('ready', (), ()))


class EusActs(SimpleTestCase):
    def test_d96_the_eus_acts_are_the_catalogues_gi_eus_acts_besides_the_examination(self):
        self.assertEqual(coverage.EUS_ACTS, tuple(kind for kind in catalogue.CATALOGUE['gi.eus'].acts
                                                  if kind not in mapping.EXAMINATION_KINDS))
        self.assertEqual(set(coverage.EUS_ACTS), {'fna', 'injection', 'drainage'})


# --- D96, finding 0: a digital rectal examination or a rectal medication filed under the EUS -------------------------

HEAD = 'EGD AND ENDOSCOPIC ULTRASOUND (EUS) REPORT'
EGD = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
EUS = 'EUS: the linear echoendoscope was then advanced to the second portion of the duodenum.'
EUS_AFTER = 'After the EGD, the linear echoendoscope was advanced to the second portion of the duodenum.'
FNA = 'EUS-guided fine-needle aspiration of the pancreatic head mass: 22-gauge needle, 3 passes.'
DRE = 'Pre-procedure examination: digital rectal examination showed brown stool and no palpable mass.'
DRE_PLAIN = 'Digital rectal examination showed brown stool and no palpable mass.'
INDO = 'Rectal indomethacin 100 mg was administered before the procedure.'


def dre(line: str = DRE, procedure=None) -> dict:
    """Finding 0's E4, in the attested C2MEM-029 r1 E9 form: an examination worded as the digital rectal examination,
    technique manual, target the rectum ('rectal'), time current_encounter with no words and the documenting team (the
    frame defaults), performed - its procedure 'eus', named by the report heading (P1)."""
    words = 'digital rectal examination' if line == DRE else 'Digital rectal examination'
    return act('E4', 'P5', 'examination', words, status_words=f'{words} showed',
               procedure=procedure if procedure is not None else a('eus', 'EUS', ['P1']),
               technique=a('manual', 'digital' if line == DRE else 'Digital', ['P5']),
               target=tg('', 'rectum', 'rectal', ['P5']))


def indomethacin() -> dict:
    """Finding 0's second route, contract-following: the rectal medication as an EUS event of kind 'other' targeting the
    rectum."""
    return act('E5', 'P6', 'other', 'indomethacin', status_words='was administered', procedure=a('eus', 'EUS', ['P1']),
               target=tg('', 'rectum', 'Rectal', ['P6']))


def egd_eus_report(*more, after_egd: bool = False, lines=None, egd_part_of: str = ''):
    """Finding 0's document: the report heading (P1), the EGD to the second portion of the duodenum (E1, its part_of
    ``egd_part_of``: '' as the finding gives it), the EUS examination (E2: 'After the EGD, ...' with ``after_egd``, its
    time current_unanchored - D70's doubt) and its FNA of the pancreatic head mass (E3), plus ``more`` events on
    ``lines``."""
    found = {'P1': HEAD, 'P2': EGD, 'P3': EUS_AFTER if after_egd else EUS, 'P4': FNA, **(lines or {})}
    options = dict(procedure=a('eus', 'linear echoendoscope' if after_egd else 'EUS', ['P3']),
                   technique=a('endoscope', 'linear echoendoscope', ['P3']))
    if after_egd:
        options['time'] = a('current_encounter', 'After the EGD', ['P3'])
    return inventory(found, events=[
        exam('E1', 'P2', words='gastroscope', procedure=a('egd', 'EGD', ['P2']), part_of=egd_part_of),
        act('E2', 'P3', 'examination', 'linear echoendoscope',
            status_words='was advanced' if after_egd else 'was then advanced', **options),
        act('E3', 'P4', 'fna', 'fine-needle aspiration', status_words='fine-needle aspiration',
            procedure=a('eus', 'EUS-guided', ['P4']), technique=a('needle', '22-gauge needle', ['P4']),
            target=tg('', 'pancreas', 'pancreatic head mass', ['P4'])), *more],
        reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P2'),
               reached('E2', 'second_portion_duodenum', DUODENUM, 'P3')])


FINDING_0 = {'control': ((), {}), 'dre': ((dre(),), {'P5': DRE}), 'dre_plain_line': ((dre(DRE_PLAIN),), {'P5': DRE_PLAIN}),
             'dre_procedure_words_empty': ((dre(procedure=a('eus')),), {'P5': DRE}),
             'indomethacin': ((indomethacin(),), {'P6': INDO})}


class DigitalExaminationAndOtherKindsAreNoLowerEvidence(SimpleTestCase):
    """D96 (finding 0): c2e53f8e holds 43235 base_included on every text; 437b708bb made it READY on all but the
    control."""

    def test_d96_a_digital_rectal_examination_or_a_rectal_medication_never_frees_43235_beside_43242(self):
        for name, (more, lines) in FINDING_0.items():
            inv, text = egd_eus_report(*more, lines=lines)
            reading = events.Reading.of(inv)
            with self.subTest(variant=name, part='fixture'):  # the finding's: attested, every attribute it reads usable
                if name.startswith('dre') and name != 'dre_procedure_words_empty':
                    rectal = reading.events['E4']
                    self.assertEqual((rectal['family'], rectal['catalogue_kind'], events.done(rectal),
                                      events.endoscopic_examination(rectal), mapping.target_landmark(rectal),
                                      events.usable(rectal, 'procedure')),
                                     ('gi.eus', 'eus_exam', True, False, 'rectum', True))
                if name == 'indomethacin':
                    medication = reading.events['E5']
                    self.assertEqual((medication['family'], medication['catalogue_kind'], events.done(medication),
                                      mapping.target_landmark(medication), events.usable(medication, 'procedure')),
                                     ('gi.eus', '', True, 'rectum', True))
            result = run(inv, text, [('43235', EGD), ('43242', FNA)])
            with self.subTest(variant=name, part='assess'):  # 437b708bb: READY, no question, on every non-control text
                held_beside(self, result, '43235', ('43242',), BESIDE_43242)
                self.assertEqual(proposal(result, '43242').status, 'ready')
            with self.subTest(variant=name, part='structure'):
                sessions = coverage.sessions(reading)
                self.assertEqual((sessions['gi.eus'].event, sessions['gi.eus'].examinations), ('E2', ('E2',)))
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('gi.eus', ''))
                self.assertEqual(lower_ids(inv), ['E2', 'E3'])
                self.assertEqual(egd_coding(result), ('gi.eus', ''))

    def test_d96_with_no_proposal_the_digital_examination_leaves_the_items_of_the_control(self):
        """437b708bb listed the EGD's own no_proposal item with a second-review mark beside the DRE (inviting a second
        review to add 43235); the control - and now every variant - lists the EUS's item alone."""
        control = items(run(*egd_eus_report(), []))
        self.assertEqual(control, [('gi.eus', 'no_proposal', True)])
        for name, (more, lines) in FINDING_0.items():
            with self.subTest(variant=name):
                inv, text = egd_eus_report(*more, lines=lines)
                self.assertEqual(items(run(inv, text, [])), control)

    def test_d96_the_digital_examination_never_cancels_d70s_doubt(self):
        """Finding 0 in D70's domain: today's EUS only possibly current ('After the EGD, ...'). The DRE beside it is no
        lower evidence, so the doubt holds 43235 base_included (437b708bb: READY)."""
        for name in ('control', 'dre', 'indomethacin'):
            more, lines = FINDING_0[name]
            inv, text = egd_eus_report(*more, after_egd=True, lines=lines)
            result = run(inv, text, [('43235', EGD), ('43242', FNA)])
            with self.subTest(variant=name, part='assess'):
                held_beside(self, result, '43235', ('43242',), BESIDE_43242)
            with self.subTest(variant=name, part='structure'):
                sessions = sessions_of(inv)
                self.assertEqual((sessions['gi.eus'].examinations, sessions['gi.eus'].possible), ((), ('E2',)))
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
                self.assertEqual(lower_ids(inv), ['E3'])

    def test_d96_controls_the_dre_elsewhere_and_c3(self):
        """The finding's boundaries, unchanged: the DRE filed under 'egd' or 'unknown', or worded 'Pre-procedure'
        (unanchored, not done), and the EGD's part_of naming the EUS (C3) all hold 43235 base_included."""
        variants = {'egd': (dre(procedure=a('egd', 'EGD', ['P1'])),), 'unknown': (dre(procedure=a('unknown')),)}
        worded = dre()
        worded['time'] = a('current_encounter', 'Pre-procedure', ['P5'])
        variants['pre_procedure'] = (worded,)
        for name, more in variants.items():
            inv, text = egd_eus_report(*more, lines={'P5': DRE})
            with self.subTest(variant=name):
                held_beside(self, run(inv, text, [('43235', EGD), ('43242', FNA)]), '43235', ('43242',), BESIDE_43242)
        inv, text = egd_eus_report(dre(), lines={'P5': DRE}, egd_part_of='E2')
        with self.subTest(variant='c3'):
            self.assertEqual(sessions_of(inv)['gi.egd'].part_of, 'gi.eus')
            held_beside(self, run(inv, text, [('43235', EGD), ('43242', FNA)]), '43235', ('43242',), BESIDE_43242)


# --- D96, finding 2: a done rectal act whose family is in doubt ------------------------------------------------------

EGD_2 = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
EUS_2 = 'EUS: a linear echoendoscope was then introduced and advanced to the duodenum.'
FNA_2 = 'A 2.5 cm hypoechoic mass in the pancreatic head was sampled with a 22-gauge needle.'
COLO = 'Colonoscopy: the colonoscope was advanced to the cecum.'
RANDOM = 'Random biopsies were taken from the rectum.'
INJECTED = 'A submucosal saline injection was made in the rectum.'


def colonoscopy_act(kind: str, procedure: dict) -> tuple:
    """Finding 2 (a)'s rectal act (P5): the random biopsies (the finding's own) or - the same shape of an EUS kind - a
    submucosal injection, with Gemini's ``procedure``."""
    if kind == 'biopsy':
        return act('E5', 'P5', 'biopsy', 'biopsies', status_words='were taken', procedure=procedure,
                   target=tg('', 'rectum', 'rectum', ['P5'])), RANDOM
    return act('E5', 'P5', 'injection', 'injection', status_words='was made', procedure=procedure,
               target=tg('', 'rectum', 'rectum', ['P5'])), INJECTED


def upper_eus_and_colonoscopy(kind: str = '', procedure=None):
    """Finding 2 (a)'s document: the EGD (E1), an upper EUS (E2) whose FNA samples the pancreatic head (E3) and - with
    ``kind`` - 'Colonoscopy: the colonoscope was advanced to the cecum.' (E4, the colonoscopy's examination) and the
    rectal act (E5)."""
    lines = {'P1': EGD_2, 'P2': EUS_2, 'P3': FNA_2}
    found = [exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'EGD', ['P1'])),
             exam('E2', 'P2', words='linear echoendoscope', status_words='was then introduced',
                  procedure=a('eus', 'EUS', ['P2'])),
             act('E3', 'P3', 'fna', 'sampled', status_words='was sampled', procedure=a('eus', 'EUS', ['P2']),
                 technique=a('needle', '22-gauge needle', ['P3']), target=tg('', 'pancreas', 'pancreatic head', ['P3']))]
    reach = [reached('E1', 'second_portion_duodenum', DUODENUM, 'P1'), reached('E2', 'duodenum', 'duodenum', 'P2')]
    if kind:
        rectal, line = colonoscopy_act(kind, procedure)
        lines.update({'P4': COLO, 'P5': line})
        found += [exam('E4', 'P4', words='colonoscope', procedure=a('colonoscopy', 'Colonoscopy', ['P4'])), rectal]
        reach.append(reached('E4', 'cecum', 'cecum', 'P4'))
    return inventory(lines, events=found, reach=reach)


class AnActWhoseFamilyIsInDoubtIsNoLowerEvidence(SimpleTestCase):
    """D96 (finding 2): c2e53f8e and 62d5bf0dd hold 43235 base_included; 437b708bb made it READY."""

    def test_d96_a_rectal_act_whose_procedure_is_unsettled_never_frees_43235_beside_43242(self):
        for kind in ('biopsy', 'injection'):  # the finding's biopsies, and the same act of an EUS kind
            inv, text = upper_eus_and_colonoscopy(kind, a('eus'))
            rectal = events.Reading.of(inv).events['E5']
            with self.subTest(kind=kind, part='fixture'):  # done today, placed in the rectum, its family in doubt
                self.assertEqual((rectal['family'], rectal['catalogue_kind'], events.done(rectal),
                                  rectal['procedure']['state'], rectal['procedure']['reasons'],
                                  mapping.target_landmark(rectal)),
                                 ('gi.eus', kind, True, 'unverified', ['procedure_unsettled'], 'rectum'))
            for codes in ([('43235', EGD_2), ('43242', FNA_2)],) + (
                    ([('43235', EGD_2), ('43242', FNA_2), ('45380', RANDOM)],) if kind == 'biopsy' else ()):
                with self.subTest(kind=kind, codes=len(codes), part='assess'):
                    held_beside(self, run(inv, text, codes), '43235', ('43242',), BESIDE_43242)
            with self.subTest(kind=kind, part='structure'):
                sessions = sessions_of(inv)
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('gi.eus', ''))
                self.assertEqual(lower_ids(inv), ['E2', 'E3'])

    def test_d96_controls_the_contracts_answers_and_a_settled_eus_act(self):
        """The finding's controls hold 43235 base_included (no colonoscopy lines; the act's procedure 'colonoscopy'
        worded; 'egd' with no words - there D75 asks it beside the doubted biopsy). The same injection with its
        procedure stated 'EUS' is a done EUS act placed in the rectum, and is lower evidence (D88's arm, kept): the EGD
        is part of no EUS and 43235 is READY."""
        for name, kind, procedure in (('none', '', None),
                                      ('colonoscopy', 'biopsy', a('colonoscopy', 'Colonoscopy', ['P4'])),
                                      ('egd_no_words', 'biopsy', a('egd'))):
            inv, text = upper_eus_and_colonoscopy(kind, procedure)
            result = run(inv, text, [('43235', EGD_2), ('43242', FNA_2)])
            with self.subTest(control=name):
                if name == 'egd_no_words':
                    p = proposal(result, '43235')
                    self.assertEqual((p.status, asked(p)), ('needs_clarification', ['base_included']))
                    self.assertEqual(sessions_of(inv)['gi.egd'].part_of, 'gi.eus')
                else:
                    held_beside(self, result, '43235', ('43242',), BESIDE_43242)
        inv, text = upper_eus_and_colonoscopy('injection', a('eus', 'EUS', ['P2']))
        with self.subTest(control='settled_eus_act'):
            self.assertTrue(events.usable(events.Reading.of(inv).events['E5'], 'procedure'))
            self.assertEqual(lower_ids(inv), ['E2', 'E3', 'E5'])
            self.assertEqual(sessions_of(inv)['gi.egd'].part_of, '')
            ready_unheld(self, run(inv, text, [('43235', EGD_2), ('43242', FNA_2)]), '43235')


# --- D96, finding 12: the FNA's verified target words name the rectum -------------------------------------------------

NODE_IN_RECTUM = 'a perirectal lymph node in the rectum'


def radial_eus_fna(target: dict, lesions=()):
    """D88's pinned document (the review's P1: the gastroscope line and RECTAL_FNA): the EGD (E1), the radial EUS naming
    no place (E2) and its done FNA (E3) with ``target``."""
    found = [exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1'])),
             exam('E2', 'P2', words='Radial EUS', status_words='was then performed',
                  procedure=a('eus', 'Radial EUS', ['P2'])),
             act('E3', 'P2', 'fna', 'sampled', status_words='was sampled', procedure=a('eus', 'Radial EUS', ['P2']),
                 technique=a('needle', '22-gauge needle', ['P2']), target=target)]
    return inventory({'P1': GASTRO, 'P2': RECTAL_FNA}, events=found, lesions=list(lesions),
                     reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P1')])


NODE_TARGETS = {
    'lymph_node': (tg('', 'lymph_node', NODE_IN_RECTUM, ['P2']), ()),
    'lesion_at_lymph_node': (tg('L1', 'lymph_node', NODE_IN_RECTUM, ['P2']),
                             (les('L1', 'a perirectal lymph node', 'P2', landmark='lymph_node',
                                  site_words='perirectal'),)),
}


class AnActsTargetWordsPlaceItLower(SimpleTestCase):
    """D96 (finding 12): c2e53f8e lists both no_proposal items and reads 43235 alone READY; 437b708bb dropped the EGD's
    item and held 43235 base_included, stating the EGD is the EUS's endoscopic portion."""

    def test_d96_a_lymph_node_target_whose_words_name_the_rectum_leaves_the_egd_its_own_item(self):
        for name, (target, lesions) in NODE_TARGETS.items():
            inv, text = radial_eus_fna(target, lesions)
            fna = events.Reading.of(inv).events['E3']
            with self.subTest(target=name, part='fixture'):  # on contract: the landmark where the act was done, verified
                self.assertEqual((fna['target']['state'], mapping.target_landmark(fna),
                                  mapping.region(mapping.target_landmark(fna))), ('verified', 'lymph_node', 'node'))
                self.assertEqual(coverage.eus_places(fna), ['lymph_node', 'lymph_node', 'rectum'])
            result = run(inv, text, [])
            with self.subTest(target=name, part='completeness'):
                self.assertEqual(egd_item(result), ('no_proposal', True))
                self.assertEqual(items(result), [('gi.egd', 'no_proposal', True), ('gi.eus', 'no_proposal', True)])
                self.assertEqual(result.completeness['included_by'], {})
            with self.subTest(target=name, part='43235'):  # 437b708bb: held base_included on a false premise
                ready_unheld(self, run(inv, text, [('43235', GASTRO)]), '43235')
            with self.subTest(target=name, part='structure'):
                sessions = sessions_of(inv)
                self.assertEqual((sessions['gi.eus'].event, sessions['gi.egd'].part_of,
                                  sessions['gi.egd'].possibly_part_of), ('E2', '', ''))
                self.assertEqual(egd_coding(result), ('', ''))

    def test_d96_target_words_naming_no_lower_landmark_are_read_as_before(self):
        """Only a landmark the words NAME is read - no word list: 'a perirectal lymph node' names the lymph node alone,
        so the EUS stays upper and 43235 alone is held base_included (fail-closed; the recorded legacy residual
        ACCURACY-RESIDUALS 'p2 reports2-0c', which c2e53f8e shares); an unverified target (the rectum at those words,
        or the pancreas at words that name the rectum: landmark_conflict) gives no words to read - they do not state
        Gemini's value; an EXAMINATION's words are not read (its place is its landmark and its reach)."""
        for name, target in (('words_name_no_lower_place', tg('', 'lymph_node', 'a perirectal lymph node', ['P2'])),
                             ('target_unverified', tg('', 'rectum', 'a perirectal lymph node', ['P2'])),
                             ('unverified_words_name_the_rectum', tg('', 'pancreas', NODE_IN_RECTUM, ['P2']))):
            inv, text = radial_eus_fna(target)
            fna = events.Reading.of(inv).events['E3']
            with self.subTest(case=name):
                if name != 'words_name_no_lower_place':
                    self.assertEqual((fna['target']['state'], fna['target']['reasons']),
                                     ('unverified', ['landmark_conflict']))
                self.assertEqual(sessions_of(inv)['gi.egd'].part_of, 'gi.eus')
                base_held(self, proposal(run(inv, text, [('43235', GASTRO)]), '43235'), (), SEPARATELY)
        fna = events.Reading.of(radial_eus_fna(tg('', 'lymph_node', NODE_IN_RECTUM, ['P2']))[0]).events['E3']
        with self.subTest(case='examination_words'):  # the same target on an examination: its landmark alone
            self.assertEqual(coverage.eus_places({**fna, 'catalogue_kind': 'eus_exam'}), ['lymph_node'])


# --- D97, finding 10: an EUS examination whose kind is not usable ---------------------------------------------------

HEADER = 'Procedure: EGD; EUS with fine-needle aspiration'
EGD_10 = 'The gastroscope was advanced to the second portion of the duodenum and the examination was completed.'
NORMAL = 'The esophagus, stomach and duodenum were normal.'
EUS_10 = 'A linear echoendoscope was then advanced to the duodenum and the pancreatic head was examined.'
FNA_10 = 'EUS-guided fine-needle aspiration of the 24 mm pancreatic head mass was performed with a 22-gauge needle.'
EUS_A = 'A linear echoendoscope was then advanced to the duodenum.'
EUS_B = 'The pancreatic head was examined.'
RADIAL = 'A radial echoendoscope was then advanced into the rectum and the rectal wall was examined.'
PLANNED = 'Plan: EUS of the pancreas in 2 weeks.'
KIND_WORDS = {'eus_word': ('EUS', ['P4']), 'composed': ('endoscopic ultrasound', ['P4']),
              'joined': (f'{EUS_A} {EUS_B}', ['P4', 'P5'])}


def egd_and_eus_kind(kind_words: str, kind_passages, split: bool = False):
    """Finding 10's document: the header (P1), the EGD (E1, part_of ''), the normal line (P3), the EUS examination (E2:
    performed, current, the documenting team, the linear echoendoscope, the pancreatic head, reaching the duodenum - its
    KIND words Gemini's ``kind_words``) told in one line or, ``split``, in two (the attested slip's shape), and its FNA
    (E3) of the 24 mm pancreatic head mass (L1)."""
    lines = {'P1': HEADER, 'P2': EGD_10, 'P3': NORMAL}
    if split:
        lines.update({'P4': EUS_A, 'P5': EUS_B, 'P6': FNA_10})
        own, fna, target = 'P4', 'P6', ['P5']
    else:
        lines.update({'P4': EUS_10, 'P5': FNA_10})
        own, fna, target = 'P4', 'P5', ['P4']
    lesion = les('L1', '24 mm pancreatic head mass', fna, landmark='pancreas', site_words='pancreatic head',
                 size_words='24 mm')
    examination = act('E2', own, 'examination', 'x', status_words='was then advanced',
                      procedure=a('eus', 'linear echoendoscope', [own]),
                      technique=a('endoscope', 'linear echoendoscope', [own]),
                      target=tg('', 'pancreas', 'pancreatic head', target))
    examination['kind'] = a('examination', kind_words, kind_passages)
    found = [exam('E1', 'P2', words='gastroscope', procedure=a('egd', 'gastroscope', ['P2'])), examination,
             act('E3', fna, 'fna', 'fine-needle aspiration', status_words='was performed',
                 procedure=a('eus', 'EUS-guided', [fna]), technique=a('needle', '22-gauge needle', [fna]),
                 target=tg('L1', 'pancreas', '24 mm pancreatic head mass', [fna]))]
    return inventory(lines, events=found, lesions=[lesion], reach=[
        reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P2'),
        reached('E2', 'duodenum', 'duodenum', own)])


def egd_beside_unsettled_eus(variant: str):
    """D97's controls: the EGD (E1) and one EUS examination (E2) whose kind words ('EUS', cited from the EGD line) do not
    locate - 'rectal': a radial EUS of the rectal wall today (its target the rectum, verified); 'planned': the plan
    line (planned, in 2 weeks: no examination of this encounter, D69)."""
    if variant == 'rectal':
        examination = act('E2', 'P4', 'examination', 'x', status_words='was then advanced',
                          procedure=a('eus', 'radial echoendoscope', ['P4']),
                          technique=a('endoscope', 'radial echoendoscope', ['P4']),
                          target=tg('', 'rectum', 'rectal wall', ['P4']))
        line = RADIAL
    else:
        examination = act('E2', 'P4', 'examination', 'x', status='planned', status_words='Plan',
                          procedure=a('eus', 'EUS', ['P4']), target=tg('', 'pancreas', 'pancreas', ['P4']),
                          time=a('future', 'in 2 weeks', ['P4']))
        line = PLANNED
    examination['kind'] = a('examination', 'EUS', ['P2'])
    return inventory({'P1': HEADER, 'P2': EGD_10, 'P3': NORMAL, 'P4': line}, events=[
        exam('E1', 'P2', words='gastroscope', procedure=a('egd', 'gastroscope', ['P2'])), examination],
        reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P2')])


def finding_10(name: str):
    kind_words, passages = KIND_WORDS[name]
    return egd_and_eus_kind(kind_words, passages, split=name == 'joined')


class AnExaminationWhoseKindIsNotUsableIsAPossibleUpperEus(SimpleTestCase):
    """D97 (finding 10): c2e53f8e holds 43235 base_included and READYs 43242; 437b708bb (and a4dcbea72) READY 43235 with
    no question."""

    def test_d97_an_eus_examination_with_unlocated_kind_words_holds_43235_beside_43242(self):
        for name in KIND_WORDS:
            inv, text = finding_10(name)
            reading = events.Reading.of(inv)
            examination = reading.events['E2']
            with self.subTest(kind_words=name, part='fixture'):  # the finding's: only the kind is not usable
                self.assertEqual((examination['family'], examination['catalogue_kind'], examination['kind']['state'],
                                  examination['kind']['reasons'], events.done(examination)),
                                 ('gi.eus', 'eus_exam', 'unverified', ['words_unlocated'], True))
                self.assertEqual([event['id'] for event in coverage.unsettled_eus_examinations(reading)], ['E2'])
            for others, codes in ((('43242',), [('43235', EGD_10), ('43242', FNA_10)]),
                                  (('43259',), [('43235', EGD_10), ('43259', EUS_A if name == 'joined' else EUS_10)])):
                result = run(inv, text, codes)
                with self.subTest(kind_words=name, beside=others[0], part='assess'):  # 437b708bb: READY
                    held_beside(self, result, '43235', others, f'Is 43235 reported separately from {others[0]} for '
                                                               'this examination?')
            with self.subTest(kind_words=name, part='alone'):
                held_beside(self, run(inv, text, [('43235', EGD_10)]), '43235', (), SEPARATELY)
            with self.subTest(kind_words=name, part='structure'):
                sessions = coverage.sessions(reading)
                self.assertEqual((sessions['gi.eus'].event, sessions['gi.eus'].examinations,
                                  sessions['gi.eus'].possible), ('', (), ()))
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))

    def test_d97_the_egd_keeps_its_own_item_and_second_review_mark(self):
        """D70's doubt drops nothing: with no proposal, the EGD's own no_proposal item and its mark stay, and nothing is
        read as included."""
        for name in KIND_WORDS:
            inv, text = finding_10(name)
            result = run(inv, text, [])
            with self.subTest(kind_words=name):
                self.assertEqual(egd_item(result), ('no_proposal', True))
                self.assertEqual(result.completeness['included_by'], {})
                self.assertEqual(egd_coding(result), ('', 'gi.eus'))

    def test_d97_controls_located_kind_words_a_lower_place_and_a_plan(self):
        """Located kind words: the examination is the session and C-4 includes the EGD, as before (43242 READY). The
        unusable-kind examination placed in the rectum is no upper EUS (D70's lower control), and a planned one is no
        examination of this encounter (D69): neither raises the doubt, and 43235 alone is READY."""
        inv, text = egd_and_eus_kind('linear echoendoscope', ['P4'])
        result = run(inv, text, [('43235', EGD_10), ('43242', FNA_10)])
        with self.subTest(control='located'):
            self.assertEqual(sessions_of(inv)['gi.egd'].part_of, 'gi.eus')
            held_beside(self, result, '43235', ('43242',), BESIDE_43242)
            self.assertEqual(proposal(result, '43242').status, 'ready')
        for name in ('rectal', 'planned'):
            inv, text = egd_beside_unsettled_eus(name)
            reading = events.Reading.of(inv)
            with self.subTest(control=name, part='fixture'):
                self.assertEqual((reading.events['E2']['kind']['state'], reading.events['E2']['kind']['reasons']),
                                 ('unverified', ['words_unlocated']))
                self.assertEqual([event['id'] for event in coverage.unsettled_eus_examinations(reading)],
                                 ['E2'] if name == 'rectal' else [])
            with self.subTest(control=name, part='structure'):
                sessions = coverage.sessions(reading)
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', ''))
                ready_unheld(self, run(inv, text, [('43235', EGD_10)]), '43235')
