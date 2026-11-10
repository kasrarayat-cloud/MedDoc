"""DECISIONS D69-D73 (the Gemini migration's round-3 refutation, findings 2, 3, 4, 6 and 7), SYNTHETIC, each built from
its finding's own input:
- D69: C-4's lower-EUS reader reads only today's DONE EUS examinations - a planned, historical or denied rectal EUS line
  never makes the EUS session lower, so it never frees 43235 beside 43242;
- D70: C-4's upper EUS is the gi.eus session's DONE examinations only - another occasion's EUS that D62 reads as only
  possibly current leaves today's EGD its own items (its no_proposal item and second-review mark), and holds 43235 with
  C-4's base_included question through a doubt the base-within rule reads, at assess time and in the read-time overlay;
- D71: a session left unresolved by a possible examination keeps D61's 52/53 consideration and service.incomplete warn
  from its done examination, and an examination begun and not completed gives every code of its session both;
- D72: a full-class EUS code never fits an examination whose STATUS is attempted_not_completed;
- D73: a second reach entry's 'incomplete' completion is never dropped with the entry.
Nothing is sent."""
from __future__ import annotations

from django.test import SimpleTestCase

from studio.interpretation import combination, coverage, events, mapping, overlay, wording
from studio.types import to_jsonable
from studio.validation import checks
from tests.test_interpretation_assess import eus_reaching, participant, stated_incomplete
from tests.test_interpretation_events import (EUS_LINES, FNA, POLYP, ROWS, asked, check, exam, inventory, proposal,
                                              reached, run)
from tests.test_interpretation_identity import a, act, tg

INCOMPLETE = 'service.incomplete'
EXAMINATION_CLASS = 'facts.examination_class'


def carried(p) -> tuple:
    """(the code's 52/53 considerations, the details of its service.incomplete checks)."""
    return (p.modifier_considerations, [item.detail for item in p.checks if item.id == INCOMPLETE])


def signals(code: str, words: str) -> tuple:
    """What D61 gives a code of a session stated incomplete: the installed release's consideration, and the warn worded
    from ``words``."""
    return ((checks.incomplete_consideration(code, ROWS.get(code), 'RVU26D'),),
            [wording.incomplete_check(words).detail])


def done_examinations_pinned(test, reading) -> None:
    """coverage.done_examinations repeats sessions' own ``exams``: the session lists them first, then D62's possible ones,
    and its one ``event`` is the one done examination when nothing possible stands beside it."""
    for family, session in coverage.sessions(reading).items():
        ids = [event['id'] for event in coverage.done_examinations(reading, family)]
        test.assertEqual(ids, list(session.examinations), family)  # D87: the done ones alone
        test.assertFalse(any(events.done(reading.events[eid]) for eid in session.possible), family)
        test.assertEqual(session.event, ids[0] if len(ids) == 1 and not session.possible else '', family)


# --- D69: the round-3 refutation, finding 2 ----------------------------------------------------------------------------

GASTRO = 'A standard gastroscope was advanced to the second portion of the duodenum.'
UPPER_EUS = ('A linear echoendoscope was then introduced and advanced to the duodenum; the pancreatic head mass was '
             'sampled with a 22-gauge needle.')
RECTAL = {'plan': 'Plan: rectal EUS for staging of the rectal mass in 2 weeks.',
          'history': 'History: a radial EUS of the rectum in 2024 showed a 1 cm rectal carcinoid.',
          'denied': 'No rectal EUS was performed.'}


def rectal_eus(variant: str) -> dict:
    """Finding 2's E5, as Gemini faithfully reads each line: an EUS examination of the rectum planned in 2 weeks, done
    in 2024, or denied."""
    procedure = a('eus', 'rectal EUS', ['P3'])
    if variant == 'plan':
        return act('E5', 'P3', 'examination', 'rectal EUS', status='planned', status_words='Plan', procedure=procedure,
                   target=tg('', 'rectum', 'rectal mass', ['P3']), time=a('future', 'in 2 weeks', ['P3']))
    if variant == 'history':
        return act('E5', 'P3', 'examination', 'radial EUS', status_words='showed', procedure=a('eus', 'radial EUS',
                                                                                               ['P3']),
                   target=tg('', 'rectum', 'rectum', ['P3']), time=a('earlier_encounter', 'in 2024', ['P3']))
    return act('E5', 'P3', 'examination', 'rectal EUS', status='not_performed',
               status_words='No rectal EUS was performed', procedure=procedure,
               target=tg('', 'rectum', 'rectal', ['P3']))


def egd_with_upper_eus(variant: str = ''):
    """Finding 2's document: an EGD (E1) to the second portion of the duodenum, an upper EUS (E2, the pancreatic head
    mass, reaching the duodenum) with its FNA (E3), and - with ``variant`` - the rectal EUS line (P3, E5)."""
    lines = {'P1': GASTRO, 'P2': UPPER_EUS}
    target = tg('', 'pancreas', 'pancreatic head mass', ['P2'])
    found = [exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1'])),
             act('E2', 'P2', 'examination', 'linear echoendoscope', status_words='was then introduced',
                 procedure=a('eus', 'linear echoendoscope', ['P2']), target=target,
                 technique=a('endoscope', 'linear echoendoscope', ['P2'])),
             act('E3', 'P2', 'fna', 'sampled', status_words='was sampled',
                 procedure=a('eus', 'linear echoendoscope', ['P2']), technique=a('needle', '22-gauge needle', ['P2']),
                 target=target)]
    if variant:
        lines['P3'] = RECTAL[variant]
        found.append(rectal_eus(variant))
    return inventory(lines, events=found, reach=[
        reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1'),
        reached('E2', 'duodenum', 'duodenum', 'P2')])


class LowerEusReadsDoneExaminations(SimpleTestCase):
    """D69: the installed release holds 43235 on all four texts, and the new path's own control holds it
    (base_included); a4dcbea72 made it READY on the planned, historical and denied ones."""

    def test_d69_a_planned_historical_or_denied_rectal_eus_never_frees_43235_beside_43242(self):
        for variant in ('', 'plan', 'history', 'denied'):
            inv, text = egd_with_upper_eus(variant)
            reading = events.Reading.of(inv)
            sessions = coverage.sessions(reading)
            result = run(inv, text, [('43235', GASTRO), ('43242', UPPER_EUS)])
            base, fna = proposal(result, '43235'), proposal(result, '43242')
            with self.subTest(variant=variant or 'control'):
                if variant:  # the fixture is the finding's: a rectal EUS examination, read faithfully, not done today
                    rectal = reading.events['E5']
                    self.assertEqual((rectal['family'], rectal['catalogue_kind'], mapping.target_landmark(rectal),
                                      rectal['status']['state'], events.done(rectal),
                                      'E5' in sessions['gi.eus'].examinations + sessions['gi.eus'].possible),
                                     ('gi.eus', 'eus_exam', 'rectum', 'verified', False, False))
                self.assertEqual((sessions['gi.eus'].event, sessions['gi.egd'].part_of,
                                  sessions['gi.egd'].possibly_part_of), ('E2', 'gi.eus', ''))
                self.assertEqual((base.status, asked(base)), ('needs_clarification', ['base_included']))
                held, question = combination.base_within_hold('43235', 'gi.egd', base.key, ('43242',),
                                                              'upper endoscopy')
                self.assertEqual((check(base, 'services.base_included'), base.clarifications[0]), (held, question))
                self.assertEqual(fna.status, 'ready')
                done_examinations_pinned(self, reading)

    def test_d69_a_rectal_eus_done_today_still_includes_no_egd(self):
        """The control D69 keeps (test_interpretation_combination's lower EUS, with the planned line beside it): an EUS
        examination done today in the rectum is a lower EUS, of which no EGD is the endoscopic portion."""
        lines = {'P1': GASTRO, 'P2': 'A radial echoendoscope was then introduced; the rectal mass was sampled with a '
                                     '22-gauge needle.', 'P3': RECTAL['plan']}
        target = tg('', 'rectum', 'rectal', ['P2'])
        inv, text = inventory(lines, events=[
            exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1'])),
            exam('E2', 'P2', words='echoendoscope', status_words='was then introduced',
                 procedure=a('eus', 'echoendoscope', ['P2']), target=target),
            act('E3', 'P2', 'fna', 'sampled', status_words='was sampled', procedure=a('eus', 'echoendoscope', ['P2']),
                technique=a('needle', '22-gauge needle', ['P2']), target=target), rectal_eus('plan')],
            reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')])
        sessions = coverage.sessions(events.Reading.of(inv))
        self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', ''))
        self.assertEqual(proposal(run(inv, text, [('43235', GASTRO), ('45392', lines['P2'])]), '43235').status,
                         'ready')


# --- D70: the round-3 refutation, finding 3 ----------------------------------------------------------------------------

EGD_LINE = 'The gastroscope was advanced to the second portion of the duodenum.'
INDEX_EUS = 'These were the findings at her index EUS: a 2 cm subepithelial lesion in the gastric body.'
INDEX_TIMES = {'unanchored': a('current_encounter', 'These were the findings at her index EUS', ['P2']),
               'default': a('current_encounter'), 'earlier': a('earlier_encounter', 'at her index EUS', ['P2'])}
SEPARATELY = 'Is 43235 reported separately from the endoscopic ultrasound for this examination?'


def egd_beside_index_eus(time: str = '', target=('gastric_body', 'gastric body'), line: str = INDEX_EUS):
    """Finding 3's document: an EGD done today (E1) and - with ``time`` - the index EUS's examination (E2), which Gemini
    labels current_encounter worded with the aside's own words ('unanchored', D54: unverified), with no words
    ('default': EB2, verified), or as an earlier encounter."""
    lines = {'P1': EGD_LINE}
    found = [exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1']))]
    if time:
        lines['P2'] = line
        found.append(act('E2', 'P2', 'examination', 'index EUS', status_words='These were the findings',
                         procedure=a('eus', 'EUS', ['P2']), technique=a('endoscope', 'EUS', ['P2']),
                         target=tg('', target[0], target[1], ['P2']), time=INDEX_TIMES[time]))
    return inventory(lines, events=found,
                     reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1')])


def egd_item(result):
    """The EGD's no_proposal item with its second-review mark, or None."""
    items = [item for item in result.completeness['unresolved_items'] if item['service'] == 'gi.egd']
    return (items[0]['reason'], items[0]['second_review']) if items else None


class PossibleUpperEus(SimpleTestCase):
    """D70: C-4 reads the gi.eus session's DONE examinations, never D62's possible ones; a possible upper EUS is a doubt
    the base-within rule reads."""

    def test_d70_another_occasions_eus_leaves_todays_egd_its_own_item_and_second_review_mark(self):
        inv, text = egd_beside_index_eus('unanchored')
        reading = events.Reading.of(inv)
        index = reading.events['E2']
        self.assertEqual((index['time']['state'], index['time']['reasons'], events.done(index),
                          coverage.possibly_current(index)), ('unverified', ['current_unanchored'], False, True))
        sessions = coverage.sessions(reading)
        self.assertEqual((sessions['gi.eus'].event, sessions['gi.eus'].examinations, sessions['gi.eus'].possible,
                          sessions['gi.eus'].done), ('', (), ('E2',), False))  # D87
        self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', 'gi.eus'))
        result = run(inv, text, [])
        self.assertEqual(egd_item(result), ('no_proposal', True))  # installed and b3f3bedba keep it
        self.assertEqual(result.completeness['included_by'], {})
        self.assertEqual(result.completeness['state'], 'incomplete')
        done_examinations_pinned(self, reading)

    def test_d70_43235_beside_a_possible_eus_is_held_with_c4s_question_never_ready(self):
        inv, text = egd_beside_index_eus('unanchored')
        result = run(inv, text, [('43235', EGD_LINE)])
        p = proposal(result, '43235')
        self.assertEqual((p.status, asked(p), p.clarifications[0].question),
                         ('needs_clarification', ['base_included'], SEPARATELY))
        held, question = combination.base_within_hold('43235', 'gi.egd', p.key, (), 'upper endoscopy')
        self.assertEqual((check(p, 'services.base_included'), p.clarifications[0]), (held, question))
        coding = result.completeness['event_coding']['sessions']
        self.assertEqual((coding['gi.egd']['part_of'], coding['gi.egd']['possibly_part_of']), ('', 'gi.eus'))

    def test_d70_the_read_time_overlay_holds_it_from_the_stored_record(self):
        """The overlay re-runs the base rules over the STORED event coding on every read and releases a stored
        base_included hold they no longer give: the doubt lives in the record the base-within rule reads, so the
        review view keeps 43235 held - a hold only the assess step added would be released there and read READY."""
        inv, text = egd_beside_index_eus('unanchored')
        result = run(inv, text, [('43235', EGD_LINE)])
        stored = [overlay.stored_from(p) for p in result.proposals]
        view = overlay.review_view(stored, {}, completeness=to_jsonable(result.completeness))[
            proposal(result, '43235').key]
        self.assertEqual((view.status, view.released, view.recomputed), ('needs_clarification', (), ()))
        self.assertEqual([q['question'] for q in view.questions], [SEPARATELY])

    def test_d70_controls(self):
        """No EUS line, or the index EUS placed at an earlier encounter: the EGD's own item, 43235 READY. Its time
        verified by default (EB2): the EUS session is done and C-4 holds as designed. A possibly current LOWER EUS: C-4
        would include no EGD in it, so nothing is held."""
        for time in ('', 'earlier'):
            inv, text = egd_beside_index_eus(time)
            sessions = coverage.sessions(events.Reading.of(inv))
            with self.subTest(time=time or 'none'):
                self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', ''))
                self.assertEqual(egd_item(run(inv, text, [])), ('no_proposal', True))
                self.assertEqual(proposal(run(inv, text, [('43235', EGD_LINE)]), '43235').status, 'ready')
        inv, text = egd_beside_index_eus('default')
        sessions = coverage.sessions(events.Reading.of(inv))
        self.assertEqual((sessions['gi.eus'].event, sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of),
                         ('E2', 'gi.eus', ''))
        self.assertEqual(asked(proposal(run(inv, text, [('43235', EGD_LINE)]), '43235')), ['base_included'])
        rectal = 'These were the findings at her index EUS: a 2 cm mass in the rectum.'
        inv, text = egd_beside_index_eus('unanchored', target=('rectum', 'rectum'), line=rectal)
        sessions = coverage.sessions(events.Reading.of(inv))
        self.assertEqual((sessions['gi.egd'].part_of, sessions['gi.egd'].possibly_part_of), ('', ''))
        self.assertEqual(proposal(run(inv, text, [('43235', EGD_LINE)]), '43235').status, 'ready')


# --- D71: the round-3 refutation, finding 4 ----------------------------------------------------------------------------

ASIDE_LINE = 'These were the findings at her index colonoscopy: diverticulosis.'
ASIDE_WORDS = 'These were the findings at her index colonoscopy'
TRANSVERSE = 'The colonoscope was advanced to the transverse colon.'


def asides() -> dict:
    """Finding 4's aside examination, in the claim's construction (no device) and in D62's own pin's (the device
    named)."""
    time = a('current_encounter', ASIDE_WORDS, ['P6'])
    return {'act': act('E5', 'P6', 'examination', 'index colonoscopy', status_words='were the findings',
                       technique=a('not_stated'), time=time),
            'exam': exam('E5', 'P6', words='index colonoscopy', status_words='were the findings', time=time)}


EUS_INCOMPLETE = {'P1': EUS_LINES['P1'], 'P2': EUS_LINES['P2'],
                  'P3': 'The pancreatic head mass was injected with a fiducial marker through a 22-gauge needle.',
                  'P5': 'The examination was incomplete because of patient intolerance.'}
EUS_ASIDE = 'These were the findings at her index EUS: a 2.0 cm mass in the pancreatic head.'


def eus_incomplete(aside: bool):
    """Finding 4's EUS probe: an upper EUS to the duodenum stated incomplete through its completion, with a fiducial
    injection (43253 needs only the target, so no extent holds it), and - with ``aside`` - the index EUS's examination."""
    examination = exam(words='echoendoscope', procedure=a('eus'), target=tg('', 'pancreas', 'pancreatic head', ['P2']))
    examination['target']['passages'] = ['P2']
    injection = act('E2', 'P3', 'injection', 'injected', status_words='was injected', procedure=a('eus'),
                    technique=a('needle', '22-gauge needle', ['P3']),
                    target=tg('', 'pancreas', 'pancreatic head mass', ['P3']))
    lines, more = dict(EUS_INCOMPLETE), []
    if aside:
        lines['P6'] = EUS_ASIDE
        more.append(exam('E5', 'P6', words='index EUS', status_words='were the findings', procedure=a('eus'),
                         time=a('current_encounter', 'These were the findings at her index EUS', ['P6'])))
    reach = reached('E1', 'duodenum', 'duodenum', 'P1')
    reach['completion'] = {'value': 'incomplete', 'words': 'incomplete because of patient intolerance',
                           'passages': ['P5']}
    return inventory(lines, events=[examination, injection, *more], reach=[reach])


class DoneExaminationsCarryD61(SimpleTestCase):
    """D71: _incomplete_session reads every DONE examination of the session, not only its one resolved examination."""

    def test_d71_a_possible_aside_examination_keeps_d61s_signals_on_every_code(self):
        for name, aside in asides().items():
            inv, text = stated_incomplete('transverse_colon', 'transverse colon', aside, lines={'P6': ASIDE_LINE})
            reading = events.Reading.of(inv)
            session = coverage.sessions(reading)['gi.colonoscopy']
            result = run(inv, text, [('45385', POLYP), ('45378', TRANSVERSE)])
            with self.subTest(aside=name):
                self.assertEqual((reading.events['E5']['time']['reasons'], session.event, session.unresolved,
                                  session.examinations, session.possible),
                                 (['current_unanchored'], '', True, ('E1',), ('E5',)))  # D87
                for code in ('45385', '45378'):
                    p = proposal(result, code)
                    self.assertEqual(carried(p), signals(code, 'incomplete'), code)
                    self.assertNotEqual(p.status, 'ready')  # held as before (the session's extent is unresolved)
                done_examinations_pinned(self, reading)

    def test_d71_a_ready_code_beside_a_possible_aside_carries_them(self):
        """Finding 4's probe 4: a READY, approvable 43253 carried neither signal beside the aside EUS."""
        for aside in (False, True):
            inv, text = eus_incomplete(aside)
            p = proposal(run(inv, text, [('43253', EUS_INCOMPLETE['P3'])]), '43253')
            with self.subTest(aside=aside):
                self.assertEqual(coverage.sessions(events.Reading.of(inv))['gi.eus'].unresolved, aside)
                self.assertEqual((p.status, carried(p)),
                                 ('ready', signals('43253', 'incomplete because of patient intolerance')))

    def test_d71_an_examination_begun_and_not_completed_gives_every_code_of_its_session_both(self):
        """D61's recorded residual, as D71 reads the status: finding 10's cecum text with the examination stated begun
        and not completed and no completion - the act code (45385, READY) carries both signals in the status's
        failure-marker words, and the base code keeps its own one check and one consideration."""
        examination = exam()
        examination['status'] = a('attempted_not_completed', 'was incomplete', ['P3'])
        inv, text = stated_incomplete('cecum', 'cecum', examination=examination, completion=a('not_stated'))
        self.assertEqual(inv.events['events'][0]['completion']['state'], 'absent')
        result = run(inv, text, [('45385', POLYP), ('45378', 'The colonoscope was advanced to the cecum.')])
        act_code, base = proposal(result, '45385'), proposal(result, '45378')
        self.assertEqual((act_code.status, carried(act_code)), ('ready', signals('45385', 'was incomplete')))
        self.assertEqual((base.support['state'], carried(base)), ('incomplete', signals('45378', 'was incomplete')))


# --- D72: the round-3 refutation, finding 6 ----------------------------------------------------------------------------

P9_INCOMPLETE = 'The examination was incomplete: the esophagus and the stomach were not examined.'
P9_ABORTED = ('The examination was aborted because of oxygen desaturation before the pancreatic body and tail were '
              'examined.')
DUODENUM = 'second portion of the duodenum'


def stated_on_the_status(p9: str, status_words: str, *more):
    """The D56 pin's EUS (the echoendoscope advanced to the second portion of the duodenum, the pancreatic head examined)
    with its incompleteness stated through the examination's STATUS - attempted_not_completed, ``status_words`` in P9 -
    and the reach's completion not stated."""
    lines = {'P1': f'A linear echoendoscope was advanced to the {DUODENUM}.', 'P2': EUS_LINES['P2']}
    for event in more:
        lines[event['status']['passages'][0]] = EUS_LINES[event['status']['passages'][0]]
    lines['P9'] = p9
    examination = exam(words='echoendoscope', procedure=a('eus'), target=tg('', 'pancreas', 'pancreatic head', ['P2']))
    examination['target']['passages'] = ['P2']
    examination['status'] = a('attempted_not_completed', status_words, ['P9'])
    return inventory(lines, events=[examination, *more], reach=[reached('E1', 'second_portion_duodenum', DUODENUM,
                                                                        'P1')])


def class_held(test, p, code: str) -> None:
    """``p`` is held on its class with D56's 'stated to be incomplete' question (D43's form)."""
    reason, question = wording.examination_class_hold(code, mapping.FULL, 'second portion duodenum', DUODENUM,
                                                      incomplete=True)
    test.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', ['extent']))
    test.assertEqual((check(p, EXAMINATION_CLASS).status, check(p, EXAMINATION_CLASS).detail,
                      p.clarifications[0].question), ('warn', reason, question))


class AttemptedStatusClass(SimpleTestCase):
    """D72: _examination_class reads the status as D56 reads the completion."""

    def test_d72_43259_on_the_d56_text_with_the_incompleteness_on_the_status_is_held(self):
        inv, text = stated_on_the_status(P9_INCOMPLETE, 'was incomplete')
        record = inv.events['events'][0]
        self.assertEqual((record['status']['state'], 'failure_marker' in record['status']['checks'],
                          record['completion']['state'], record['extent']['state']),
                         ('verified', True, 'absent', 'verified'))
        astra = participant('astra', text, codes=[('43259', EUS_LINES['P2'])])
        for participants in ((), (astra, participant('fable', text))):
            p = proposal(run(inv, text, [('43259', EUS_LINES['P2'])], participants=participants), '43259')
            with self.subTest(participants=len(participants)):
                class_held(self, p, '43259')
        control, control_text = eus_reaching('second_portion_duodenum', DUODENUM)
        self.assertEqual(proposal(run(control, control_text, [('43259', EUS_LINES['P2'])]), '43259').status, 'ready')

    def test_d72_the_aborted_eus_fna_holds_43242(self):
        inv, text = stated_on_the_status(P9_ABORTED, 'was aborted', FNA)
        p = proposal(run(inv, text, [('43242', EUS_LINES['P3'])]), '43242')
        class_held(self, p, '43242')
        self.assertEqual(carried(p), signals('43242', 'was aborted'))  # D71 gives the session's codes both
        limited = proposal(run(inv, text, [('43238', EUS_LINES['P3'])]), '43238')
        self.assertEqual((limited.status, asked(limited)), ('needs_clarification', ['extent']))  # by its reach, as before


# --- D73: the round-3 refutation, finding 7 ----------------------------------------------------------------------------

LONG = {'value': 'incomplete', 'words': 'The examination was incomplete', 'passages': ['P9']}
SHORT = {'value': 'incomplete', 'words': 'incomplete', 'passages': ['P9']}
SECOND = 'encounter.reach[1] gives a second reach for one examination; the first is kept.'


def reach_entry(completion=None) -> dict:
    entry = reached('E1', 'second_portion_duodenum', DUODENUM, 'P1')
    if completion is not None:
        entry['completion'] = dict(completion)
    return entry


def two_reaches(*reaches):
    """Finding 7's document, the D56 pin's: the EUS to the second portion of the duodenum, the pancreatic head examined,
    and 'The examination was incomplete: the esophagus and the stomach were not examined.' (P9)."""
    lines = {'P1': f'A linear echoendoscope was advanced to the {DUODENUM}.', 'P2': EUS_LINES['P2'], 'P9': P9_INCOMPLETE}
    examination = exam(words='echoendoscope', procedure=a('eus'), target=tg('', 'pancreas', 'pancreatic head', ['P2']))
    examination['target']['passages'] = ['P2']
    return inventory(lines, events=[examination], reach=list(reaches))


class SecondReachCompletion(SimpleTestCase):
    """D73: normalize's reach merge keeps a dropped second entry's 'incomplete', unverified (second_reach)."""

    def test_d73_a_second_reach_entrys_incomplete_completion_holds_43259(self):
        for name, completion in (('long words', LONG), ('short words', SHORT)):
            inv, text = two_reaches(reach_entry(), reach_entry(completion))
            record = inv.events['events'][0]['completion']
            with self.subTest(words=name):
                self.assertEqual((record['value'], record['state'], record['reasons']),
                                 ('incomplete', 'unverified', ['second_reach']))
                self.assertEqual([(entry['state'], entry['attached']) for entry in inv.encounter_facts['reach']],
                                 [('verified', True), ('verified', False)])
                self.assertIn(SECOND, inv.verification['problems'])  # the problem stays recorded
                self.assertEqual(inv.verification['reasons'].get('second_reach'), 1)
                for participants in ((), (participant('astra', text), participant('fable', text))):
                    p = proposal(run(inv, text, [('43259', EUS_LINES['P2'])], participants=participants), '43259')
                    class_held(self, p, '43259')

    def test_d73_controls_one_reach_and_a_kept_incomplete(self):
        """One reach, not stated: READY. The incomplete entry first, either second entry after it: its own verified
        completion is kept - so D61's signals stay - and second_reach is never given."""
        inv, text = two_reaches(reach_entry())
        self.assertEqual(proposal(run(inv, text, [('43259', EUS_LINES['P2'])]), '43259').status, 'ready')
        for second in (reach_entry(), reach_entry(SHORT)):
            inv, text = two_reaches(reach_entry(LONG), second)
            record = inv.events['events'][0]['completion']
            p = proposal(run(inv, text, [('43259', EUS_LINES['P2'])]), '43259')
            with self.subTest(second=second['completion']['value']):
                self.assertEqual((record['state'], record['words']['text']), ('verified', LONG['words']))
                self.assertNotIn('second_reach', inv.verification['reasons'])
                self.assertIn(SECOND, inv.verification['problems'])
                class_held(self, p, '43259')
                self.assertEqual(carried(p), signals('43259', LONG['words']))
