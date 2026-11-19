"""DECISIONS D88 and D93 (the integration of round 3, 732d172d2), SYNTHETIC, each pinned from the round-3 EUS-sessions
review's own inputs (its probes P1, P2, P4 and P7, which it ran against D69-D73 as 62d5bf0dd carries them):
- D88: C-4 reads the lower tract from every DONE EUS event - its acts' verified places as well as its examinations' -
  and never from a POSSIBLE examination.
  * 'REGRESSION CAUSED BY D69' (P1): a radial EUS naming no place, whose done FNA samples a perirectal node in the
    rectum, is a lower EUS - today's EGD keeps its own no_proposal item and second-review mark, and 43235 alone is never
    held base_included (62d5bf0dd dropped the item and held it, as D69 read the examinations alone);
  * 'STILL A WRONG READY IN D70'S OWN DOMAIN' (P7, and the review's P4): a possibly current rectal EUS aside never
    cancels D70's doubt - 43235 beside today's possible upper EUS-FNA (43242) is held base_included, never READY, at
    assess time and in the read-time overlay (62d5bf0dd read the aside as lower and made it READY in both).
- D93 ("D73'S SIBLING", P2): a reach entry naming no landmark keeps its 'incomplete' completion - after a stated entry
  the examination takes it, unverified (second_reach), and 43259 is held on its class with D56's question (62d5bf0dd
  dropped it: READY with no question).
The reviewer's P2 input in the other order (the unplaced entry FIRST) is not pinned here: at 732d172d2 the stated entry
attached after it replaces the kept completion and 43259 is READY - reported as a finding, not a pin.
Each test asserts in independent subtests - the outcome, the read-time overlay, the structure - so a regression shows
every one it breaks. Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import combination, coverage, events, mapping, overlay
from studio.types import to_jsonable
from tests.test_interpretation_assess import participant
from tests.test_interpretation_events import EUS_LINES, asked, check, exam, inventory, proposal, reached, run
from tests.test_interpretation_identity import a, act, tg
from tests.test_interpretation_r3_eus import (DUODENUM, EGD_LINE, GASTRO, INDEX_EUS, LONG, P9_INCOMPLETE, SEPARATELY,
                                              carried, class_held, egd_item, signals)

BASE_INCLUDED = 'services.base_included'


def reviewed(result, code: str):
    """The read-time overlay's view of ``code``: overlay.review_view re-runs the base rules over the STORED event coding
    and releases a stored base_included hold they no longer give."""
    stored = [overlay.stored_from(p) for p in result.proposals]
    return overlay.review_view(stored, {}, completeness=to_jsonable(result.completeness))[proposal(result, code).key]


def items(result) -> list:
    return [(item['service'], item['reason'], item['second_review'])
            for item in result.completeness['unresolved_items']]


def egd_coding(result) -> tuple:
    coding = result.completeness['event_coding']['sessions']['gi.egd']
    return coding['part_of'], coding['possibly_part_of']


def questions(p) -> list:
    return [spec.question for spec in p.clarifications]


def base_held(test, p, others: tuple, question: str) -> None:
    """``p`` (43235) is held with C-4's base_included question and base_within_hold's own check and clarification."""
    test.assertEqual((p.status, asked(p), questions(p)), ('needs_clarification', ['base_included'], [question]))
    held, spec = combination.base_within_hold('43235', 'gi.egd', p.key, others, 'upper endoscopy')
    test.assertEqual((check(p, BASE_INCLUDED), list(p.clarifications)), (held, [spec]))


# --- D88, 'REGRESSION CAUSED BY D69' (the review's P1) ---------------------------------------------------------------

RECTAL_FNA = 'Radial EUS was then performed; a perirectal lymph node in the rectum was sampled with a 22-gauge needle.'


def rectal_fna():
    """The review's P1 document: the gastroscope to the second portion of the duodenum (E1), and a radial EUS (E2, an
    examination naming no place and no reach) whose FNA (E3, done) samples a perirectal node - its target the rectum,
    verified."""
    lines = {'P1': GASTRO, 'P2': RECTAL_FNA}
    found = [exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1'])),
             exam('E2', 'P2', words='Radial EUS', status_words='was then performed',
                  procedure=a('eus', 'Radial EUS', ['P2'])),
             act('E3', 'P2', 'fna', 'sampled', status_words='was sampled', procedure=a('eus', 'Radial EUS', ['P2']),
                 technique=a('needle', '22-gauge needle', ['P2']), target=tg('', 'rectum', 'rectum', ['P2']))]
    return inventory(lines, events=found, reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P1')])


class LowerEusReadsEveryDoneEvent(SimpleTestCase):
    """D88: the lower tract is read from the done EUS acts' places too - here the examination alone names none."""

    def test_d88_a_radial_eus_whose_done_fna_samples_the_rectum_leaves_the_egd_its_own_item(self):
        inv, text = rectal_fna()
        reading = events.Reading.of(inv)
        examination, fna = reading.events['E2'], reading.events['E3']
        with self.subTest(part='fixture'):  # the review's: the examination is done today and placed nowhere
            self.assertEqual((examination['family'], examination['catalogue_kind'], events.done(examination),
                              mapping.target_landmark(examination), examination['extent']),
                             ('gi.eus', 'eus_exam', True, '', None))
            self.assertEqual((fna['family'], fna['catalogue_kind'], events.done(fna), fna['target']['state'],
                              mapping.target_landmark(fna)), ('gi.eus', 'fna', True, 'verified', 'rectum'))
        result = run(inv, text, [])
        with self.subTest(part='completeness'):
            # with no proposal, the EGD's own item with its second-review mark (a4dcbea72 and the installed release list
            # it; 62d5bf0dd read the EGD as the EUS's endoscopic portion and dropped it)
            self.assertEqual(egd_item(result), ('no_proposal', True))
            self.assertEqual(items(result), [('gi.egd', 'no_proposal', True), ('gi.eus', 'no_proposal', True)])
            self.assertEqual(result.completeness['included_by'], {})
        with self.subTest(part='sessions'):
            sessions = coverage.sessions(reading)
            self.assertEqual((sessions['gi.eus'].event, sessions['gi.egd'].event, sessions['gi.egd'].part_of,
                              sessions['gi.egd'].possibly_part_of), ('E2', 'E1', '', ''))
            self.assertEqual(egd_coding(result), ('', ''))

    def test_d88_43235_alone_is_never_held_base_included(self):
        inv, text = rectal_fna()
        result = run(inv, text, [('43235', GASTRO)])
        p = proposal(result, '43235')
        with self.subTest(part='assess'):  # a4dcbea72's READY; 62d5bf0dd held it base_included
            self.assertIsNone(check(p, BASE_INCLUDED))
            self.assertEqual((p.status, asked(p), questions(p)), ('ready', [], []))
        with self.subTest(part='overlay'):
            view = reviewed(result, '43235')
            self.assertEqual((view.status, view.released, view.recomputed), ('ready', (), ()))
        with self.subTest(part='event_coding'):
            self.assertEqual(egd_coding(result), ('', ''))


# --- D88, 'STILL A WRONG READY IN D70'S OWN DOMAIN' (the review's P7 and P4) ------------------------------------------

AFTER_EGD = ('After the EGD, a linear echoendoscope was introduced and advanced to the duodenum; the pancreatic head '
             'mass was sampled with a 22-gauge needle.')
INDEX_RECTAL = 'These were the findings at her index rectal EUS: a 1 cm rectal carcinoid.'
RECTAL_ASIDE_WORDS = 'These were the findings at her index rectal EUS'
BESIDE_43242 = 'Is 43235 reported separately from 43242 for this examination?'


def rectal_aside(eid: str, passage: str) -> dict:
    """The review's rectal EUS aside: an examination of the rectum Gemini labels current_encounter worded with the
    aside's own words (D54: unverified, current_unanchored) - only possibly this encounter's (D62)."""
    return act(eid, passage, 'examination', 'index rectal EUS', status_words='These were the findings',
               procedure=a('eus', 'rectal EUS', [passage]), technique=a('endoscope', 'rectal EUS', [passage]),
               target=tg('', 'rectum', 'rectal', [passage]), time=a('current_encounter', RECTAL_ASIDE_WORDS, [passage]))


def unanchored_upper_eus(rectal: bool):
    """The review's P7 document: the gastroscope line (E1, done), today's upper EUS worded 'After the EGD' (E2, its time
    current_unanchored, so only possible) with its done FNA of the pancreatic head mass (E3), and - with ``rectal`` -
    the index rectal EUS aside (E5, also possible)."""
    lines = {'P1': GASTRO, 'P2': AFTER_EGD}
    target = tg('', 'pancreas', 'pancreatic head mass', ['P2'])
    found = [exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1'])),
             act('E2', 'P2', 'examination', 'linear echoendoscope', status_words='was introduced',
                 procedure=a('eus', 'linear echoendoscope', ['P2']), target=target,
                 technique=a('endoscope', 'linear echoendoscope', ['P2']),
                 time=a('current_encounter', 'After the EGD', ['P2'])),
             act('E3', 'P2', 'fna', 'sampled', status_words='was sampled',
                 procedure=a('eus', 'linear echoendoscope', ['P2']), technique=a('needle', '22-gauge needle', ['P2']),
                 target=target)]
    if rectal:
        lines['P3'] = INDEX_RECTAL
        found.append(rectal_aside('E5', 'P3'))
    return inventory(lines, events=found, reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P1'),
                                                 reached('E2', 'duodenum', 'duodenum', 'P2')])


def index_asides(upper: bool):
    """The review's P4 document: today's EGD (E1) beside finding 3's index EUS aside (E2, upper: the gastric body) when
    ``upper``, and the index rectal EUS aside (E3) - each only possibly current, no EUS event done."""
    lines = {'P1': EGD_LINE}
    found = [exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1']))]
    if upper:
        lines['P2'] = INDEX_EUS
        found.append(act('E2', 'P2', 'examination', 'index EUS', status_words='These were the findings',
                         procedure=a('eus', 'EUS', ['P2']), technique=a('endoscope', 'EUS', ['P2']),
                         target=tg('', 'gastric_body', 'gastric body', ['P2']),
                         time=a('current_encounter', 'These were the findings at her index EUS', ['P2'])))
    lines['P3'] = INDEX_RECTAL
    found.append(rectal_aside('E3', 'P3'))
    return inventory(lines, events=found, reach=[reached('E1', 'second_portion_duodenum', DUODENUM, 'P1')])


class PossibleExaminationIsNeverLowerEvidence(SimpleTestCase):
    """D88: D70's doubt stands while some possible EUS examination is not itself placed lower and no done EUS event
    is."""

    def test_d88_a_possible_rectal_aside_never_makes_43235_ready_beside_43242(self):
        for rectal in (True, False):  # False: the review's control - the same hold without the aside
            inv, text = unanchored_upper_eus(rectal)
            reading = events.Reading.of(inv)
            with self.subTest(rectal_aside=rectal, part='fixture'):
                upper, fna = reading.events['E2'], reading.events['E3']
                self.assertEqual((upper['time']['state'], upper['time']['reasons'], events.done(upper),
                                  coverage.possibly_current(upper), events.done(fna), mapping.target_landmark(fna)),
                                 ('unverified', ['current_unanchored'], False, True, True, 'pancreas'))
                if rectal:  # the review's aside: a rectal EUS examination, placed, only possibly current
                    aside = reading.events['E5']
                    self.assertEqual((aside['family'], aside['catalogue_kind'], mapping.target_landmark(aside),
                                      events.done(aside), coverage.possibly_current(aside)),
                                     ('gi.eus', 'eus_exam', 'rectum', False, True))
            result = run(inv, text, [('43235', GASTRO), ('43242', AFTER_EGD)])
            with self.subTest(rectal_aside=rectal, part='assess'):  # 62d5bf0dd, with the aside: READY
                base_held(self, proposal(result, '43235'), ('43242',), BESIDE_43242)
            with self.subTest(rectal_aside=rectal, part='overlay'):  # 62d5bf0dd, with the aside: 'ready' here too
                view = reviewed(result, '43235')
                self.assertEqual((view.status, view.released, view.recomputed), ('needs_clarification', (), ()))
                self.assertEqual([q['question'] for q in view.questions], [BESIDE_43242])
            with self.subTest(rectal_aside=rectal, part='sessions'):
                sessions = coverage.sessions(reading)
                self.assertEqual((sessions['gi.eus'].examinations, sessions['gi.eus'].possible,
                                  sessions['gi.eus'].unresolved), ((), ('E2', 'E5') if rectal else ('E2',), rectal))
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
                self.assertEqual(egd_coding(result), ('', 'gi.eus'))

    def test_d88_an_upper_and_a_rectal_index_aside_hold_43235_and_a_lone_rectal_one_does_not(self):
        """The review's P4: finding 3's index EUS aside (upper) beside an index rectal EUS aside, both possible - the
        rectal one is no lower evidence, so 43235 is held with C-4's question (62d5bf0dd: READY). A lone possible rectal
        aside raises no doubt: C-4 would include no EGD in a lower EUS (D70's control)."""
        for upper in (True, False):
            inv, text = index_asides(upper)
            result = run(inv, text, [('43235', EGD_LINE)])
            p, view = proposal(result, '43235'), reviewed(result, '43235')
            with self.subTest(upper_aside=upper, part='assess'):
                if upper:
                    base_held(self, p, (), SEPARATELY)
                else:
                    self.assertEqual((p.status, asked(p), check(p, BASE_INCLUDED)), ('ready', [], None))
            with self.subTest(upper_aside=upper, part='overlay'):
                self.assertEqual((view.status, [q['question'] for q in view.questions]),
                                 ('needs_clarification', [SEPARATELY]) if upper else ('ready', []))
            with self.subTest(upper_aside=upper, part='sessions'):
                sessions = coverage.sessions(events.Reading.of(inv))
                self.assertEqual((sessions['gi.eus'].examinations, sessions['gi.eus'].possible),
                                 ((), ('E2', 'E3') if upper else ('E3',)))
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of),
                                 ('', 'gi.eus' if upper else ''))
                self.assertEqual(egd_item(run(inv, text, [])), ('no_proposal', True))


# --- D93, "D73'S SIBLING" (the review's P2) ---------------------------------------------------------------------------

UNPLACED = 'encounter.reach[{}] gives a reach that names no landmark; its incomplete completion is kept.'


def stated_reach() -> dict:
    """The D56 pin's reach: the second portion of the duodenum, its completion not stated."""
    return reached('E1', 'second_portion_duodenum', DUODENUM, 'P1')


def unplaced_reach() -> dict:
    """The review's other entry: no landmark, its completion 'incomplete' worded 'The examination was incomplete'
    (P9)."""
    return {'event': 'E1', 'landmark': 'not_stated', 'words': '', 'passages': [], 'completion': dict(LONG)}


def d56_text(*reaches):
    """D56's text (the D73 pin's): the linear echoendoscope to the second portion of the duodenum (P1), the pancreatic
    head examined (P2), and 'The examination was incomplete: the esophagus and the stomach were not examined.' (P9)."""
    lines = {'P1': f'A linear echoendoscope was advanced to the {DUODENUM}.', 'P2': EUS_LINES['P2'],
             'P9': P9_INCOMPLETE}
    examination = exam(words='echoendoscope', procedure=a('eus'), target=tg('', 'pancreas', 'pancreatic head', ['P2']))
    examination['target']['passages'] = ['P2']
    return inventory(lines, events=[examination], reach=list(reaches))


def completion_of(record) -> tuple:
    """(value, state, reasons, words, passages) of the examination's completion; all None when it has none."""
    completion = record['completion'] or {}
    return (completion.get('value'), completion.get('state'), completion.get('reasons'),
            (completion.get('words') or {}).get('text'), completion.get('passages'))


class UnplacedReachKeepsIncomplete(SimpleTestCase):
    """D93: normalize's reach merge keeps the 'incomplete' completion of an entry whose landmark is not stated."""

    def test_d93_after_a_stated_reach_an_unplaced_entrys_incomplete_holds_43259(self):
        inv, text = d56_text(stated_reach(), unplaced_reach())
        for participants in ((), (participant('astra', text), participant('fable', text))):
            result = run(inv, text, [('43259', EUS_LINES['P2'])], participants=participants)
            with self.subTest(participants=len(participants), part='assess'):  # 62d5bf0dd: READY, no question
                class_held(self, proposal(result, '43259'), '43259')  # D56's 'stated to be incomplete' question
            with self.subTest(participants=len(participants), part='overlay'):
                self.assertEqual(reviewed(result, '43259').status, 'needs_clarification')
        record = inv.events['events'][0]
        with self.subTest(part='normalize'):
            self.assertEqual(completion_of(record),
                             ('incomplete', 'unverified', ['second_reach'], LONG['words'], ['P9']))
            self.assertEqual((record['extent']['value'], record['extent']['state']),
                             ('second_portion_duodenum', 'verified'))
            self.assertEqual([(entry['landmark'], entry['state'], entry['attached'])
                              for entry in inv.encounter_facts['reach']],
                             [('second_portion_duodenum', 'verified', True), ('not_stated', 'absent', False)])
            self.assertIn(UNPLACED.format(1), inv.verification['problems'])
            self.assertEqual(inv.verification['reasons'].get('second_reach'), 1)

    def test_d93_an_unplaced_entrys_incomplete_before_a_stated_reach_still_holds_43259(self):
        """D93 in the other order (the pins' review): the unplaced entry FIRST attaches its 'incomplete'; the stated
        reach after it attaches its extent and never overwrites that completion (732d172d2: READY, no question)."""
        inv, text = d56_text(unplaced_reach(), stated_reach())
        result = run(inv, text, [('43259', EUS_LINES['P2'])])
        class_held(self, proposal(result, '43259'), '43259')
        self.assertEqual(reviewed(result, '43259').status, 'needs_clarification')
        record = inv.events['events'][0]
        self.assertEqual(completion_of(record)[0], 'incomplete')
        self.assertEqual((record['extent']['value'], record['extent']['state']), ('second_portion_duodenum', 'verified'))

    def test_d93_a_lone_unplaced_entry_states_the_examination_incomplete(self):
        """D93's other arm, the review's entry alone: nothing attached before it, its completion is attached as bound -
        verified - so D61's signals read it; the reach itself is not stated, so 43259 asks the extent (62d5bf0dd kept no
        completion and gave neither signal)."""
        inv, text = d56_text(unplaced_reach())
        p = proposal(run(inv, text, [('43259', EUS_LINES['P2'])]), '43259')
        with self.subTest(part='assess'):
            self.assertEqual((p.status, asked(p)), ('needs_clarification', ['extent']))
            self.assertEqual(carried(p), signals('43259', LONG['words']))
        record = inv.events['events'][0]
        with self.subTest(part='normalize'):
            self.assertEqual(completion_of(record), ('incomplete', 'verified', [], LONG['words'], ['P9']))
            self.assertIsNone(record['extent'])
            self.assertIn(UNPLACED.format(0), inv.verification['problems'])
            self.assertNotIn('second_reach', inv.verification['reasons'])
