"""DECISIONS D67 and D68 (the round-3 refutation of a4dcbea72, findings 0, 1 and 18), SYNTHETIC: a current time's date
literal judged against the date that decides it, and a current time's own reasons never read as proof of another
occasion. Every input is a synthetic Gemini answer over a synthetic document, read by read.read and normalized with the
real linked steps, then assessed through assess.assess (and, for the chain, the production pipeline with the replay
interpreter and the in-process Corti fake). Nothing is sent.

D67 (finding 0). With no verified, unopened date of service, a current time worded "On 03/14/2024" verified through
D54's dated arm with nothing to compare it to, and nothing re-judged it once a member's date existed (verify.time_state
had no caller): 45390 on a 2024 EMR was READY on the member-date path, where the document's own date holds it
(event_time) and the installed release excludes it as historical.
- (a) At normalize time a current_encounter time whose verification would rest on a date at day precision is
  unverified while no service date is established (date_unchecked, one of verify.REEVALUATED). A time anchored by
  whole frames, and one with no words, is unaffected.
- (b) assess re-judges every stored time with the effective date (verify.time_state over a COPY of the inventory's
  event records: verify.rejudged), and recomputes each event's ``current`` as normalize._current does. The stored
  inventory is never changed.

D68 (findings 1 and 18). D62's carve-out read D35's marker (other_occasion) and any date_mismatch as proof that a
current time places its event on another occasion. But D35's markers include sequence words within one procedure
("Next", "Later in the procedure", "At that time") and a clock time ("At 2030") reads as the year 2030: a removal, an
EMR, a stent or an EUS examination worded so released the part it holds - 45380, 45381, 43262 and 43235 READY where the
installed release holds them. coverage.possibly_current and relations._possibly_current now count a current_encounter
time as possibly current whatever its reasons: the part stays held (bundled, or its base question), never READY."""
from __future__ import annotations

import copy
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio import jobs, models
from studio.interpretation import adapter, coverage, events, normalize, relations, verify
from tests.support import factories as f
from tests.test_interpretation_coverage import hemoclips
from tests.test_interpretation_events import (COLONOSCOPE, asked, check, colonoscopy, exam, inventory, proposal,
                                              reached, run)
from tests.test_interpretation_identity import a, accepted, act, les, snare, tg
from tests.test_interpretation_slips import inventory_of
from tests.test_pipeline_assess_events import HEAD, EventsCase, envelope

SERVICE = date(2026, 11, 9)

# --- finding 0: the 2024 EMR worded as a current time, on a document whose date no check establishes ------------------

BIOPSY_LINE = 'A 4 mm polyp in the rectum was biopsied with cold forceps.'
EMR_2024 = 'On 03/14/2024, a 25 mm flat polyp in the cecum was resected by EMR.'
EMR_SAME_DAY = 'On 11/09/2026, a 25 mm flat polyp in the cecum was resected by EMR.'
EMR_FRAMED = 'During this procedure, a 25 mm flat polyp in the cecum was resected by EMR.'
DATE_LINE = 'Date of service: 11/09/2026.'
NOT_STATED = {'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []}
STATED = {'value': '2026-11-09', 'state': 'stated', 'words': '11/09/2026', 'passages': ['P0'], 'other_dates': []}
OPENED = ({'about': 'date_of_service', 'events': [], 'lesions': [], 'passages': ['P0']},)


def this_encounter(value: str, words: str, passage: str) -> dict:
    return {'value': value, 'role': 'this_encounter', 'words': words, 'passages': [passage]}


# 'several': the date line naming two dates, and the date line beside a procedure date line (the finding's two variants)
SEVERAL_ONE_LINE = ({'P0': 'Date of service: 11/08/2026 or 11/09/2026.'},
                    {'value': '', 'state': 'several', 'words': '', 'passages': ['P0'],
                     'other_dates': [this_encounter('2026-11-08', '11/08/2026', 'P0'),
                                     this_encounter('2026-11-09', '11/09/2026', 'P0')]})
SEVERAL_TWO_LINES = ({'P0': DATE_LINE, 'P9': 'Procedure date: 11/08/2026.'},
                     {'value': '', 'state': 'several', 'words': '', 'passages': ['P0', 'P9'],
                      'other_dates': [this_encounter('2026-11-09', '11/09/2026', 'P0'),
                                      this_encounter('2026-11-08', '11/08/2026', 'P9')]})


def emr_answer(emr_line: str = EMR_2024, time_words: str = 'On 03/14/2024', *, date_lines=None,
               date_of_service=NOT_STATED, open_questions=()) -> tuple:
    """(Gemini's synthetic answer, the document's lines) of finding 0: a colonoscopy to the cecum (E1), a cold forceps
    biopsy of a 4 mm rectal polyp (E2, L2) and an EMR of a 25 mm cecal polyp (E3, L1) whose time Gemini gives as
    current_encounter with ``time_words``; no date line unless ``date_lines`` gives one."""
    lines = {**(date_lines or {}), 'P1': COLONOSCOPE, 'P2': BIOPSY_LINE, 'P3': emr_line}
    biopsy = act('E2', 'P2', 'biopsy', 'biopsied', status_words='was biopsied with cold forceps',
                 technique=a('cold_forceps', 'cold forceps', ['P2']),
                 target=tg('L2', 'rectum', '4 mm polyp in the rectum', ['P2']))
    resection = act('E3', 'P3', 'emr', 'EMR', status_words='was resected by EMR',
                    target=tg('L1', 'cecum', '25 mm flat polyp in the cecum', ['P3']),
                    time=a('current_encounter', time_words, ['P3']) if time_words else a('current_encounter'))
    value = {'passages': [{'id': pid, 'text': text} for pid, text in lines.items()],
             'encounter': {'date_of_service': date_of_service, 'documenting_endoscopist': {'words': '', 'passages': []},
                           'team': [], 'anatomy': [], 'reach': [reached()], 'visit_facts': []},
             'lesions': [les('L1', '25 mm flat polyp', 'P3', landmark='cecum', site_words='cecum', size_words='25 mm'),
                         les('L2', '4 mm polyp', 'P2', landmark='rectum', site_words='rectum', size_words='4 mm')],
             'events': [exam(), biopsy, resection], 'open_questions': list(open_questions)}
    return value, lines


def emr_document(emr_line: str = EMR_2024, time_words: str = 'On 03/14/2024', **options) -> tuple:
    """(the normalized inventory, the document's text, the EMR line) of emr_answer."""
    value, lines = emr_answer(emr_line, time_words, **options)
    text = '\n'.join(lines.values()) + '\n'
    return normalize.normalize(accepted(value), text), text, emr_line


def time_of(inv, eid: str = 'E3') -> dict:
    return next(item for item in inv.events['events'] if item['id'] == eid)['time']


def assessed(inv, text: str, emr_line: str, member_date=None):
    return run(inv, text, [('45380', BIOPSY_LINE), ('45390', emr_line)],
               user_values={'service_date': member_date} if member_date else {})


class D67DayLiteralWithNoServiceDate(SimpleTestCase):
    """D67(a), in the attribute's own words: a day-precision literal is what anchors a current time (D54's dated arm,
    D64), and with no service date it anchors nothing (date_unchecked) until a date decides it."""

    def test_d67_a_day_literal_with_no_service_date_anchors_nothing(self):
        day = [{'value': '2024-03-14', 'precision': 'day'}]
        self.assertEqual(verify._date_reasons('current_encounter', day, None), ('date_unchecked',))
        self.assertEqual(verify._date_reasons('current_encounter', day, SERVICE), ('date_mismatch',))
        self.assertEqual(verify._date_reasons('current_encounter', [{'value': '2026-11-09', 'precision': 'day'}],
                                              SERVICE), ())
        self.assertIn('date_unchecked', verify.REEVALUATED)
        for text in ('On 03/14/2024', 'On 11/09/2026', 'today, 11/09/2026', 'on November 9, 2026'):
            with self.subTest(text):
                verdict = verify.time_words('current_encounter', text, None)
                self.assertEqual(tuple(verdict.reasons), ('date_unchecked',))
                record = {'value': 'current_encounter', 'state': 'unverified', 'basis': 'stated',
                          'literals': dict(verdict.literals), 'reasons': list(verdict.reasons)}
                self.assertEqual(verify.exclusion_basis('time', record), '')  # a time question, never an exclusion

    def test_d67_whole_frames_no_words_and_a_month_or_year_are_unaffected(self):
        for text in ('today', 'During this procedure', 'during the present encounter', 'On withdrawal', ''):
            with self.subTest(text):
                self.assertEqual(tuple(verify.time_words('current_encounter', text, None).reasons), ())
        # a month or a year anchors nothing already (D54): unanchored, and no day to leave unchecked
        self.assertEqual(tuple(verify.time_words('current_encounter', 'in March 2024', None).reasons),
                         ('current_unanchored',))
        self.assertEqual(verify._date_reasons('current_encounter', [{'value': '2024-03', 'precision': 'month'}], None),
                         ())
        # the earlier and future values, and a service date's own decision, are as before
        self.assertEqual(tuple(verify.time_words('earlier_encounter', 'on 03/14/2024', None).reasons),
                         ('date_unchecked',))
        self.assertEqual(tuple(verify.time_words('current_encounter', 'On 11/09/2026', SERVICE).reasons), ())
        self.assertEqual(tuple(verify.time_words('current_encounter', 'On 03/14/2024', SERVICE).reasons),
                         ('date_mismatch',))

    def test_d67_time_state_decides_the_unchecked_day_with_the_effective_date(self):
        verdict = verify.time_words('current_encounter', 'On 03/14/2024', None)
        record = {'value': 'current_encounter', 'basis': 'stated', 'state': 'unverified', 'open': False,
                  'literals': dict(verdict.literals), 'reasons': list(verdict.reasons)}
        judged = [verify.time_state(record, when) for when in (SERVICE, '2024-03-14', None)]
        self.assertEqual([(item['state'], item['reasons']) for item in judged],
                         [('unverified', ['date_mismatch']), ('verified', []), ('unverified', ['date_unchecked'])])


class D67Normalize(SimpleTestCase):
    def test_d67_the_undated_documents_day_worded_current_time_is_unchecked(self):
        inv, _, _ = emr_document()
        self.assertEqual(inv.encounter_facts['date_of_service']['value'], None)
        stored = time_of(inv)
        self.assertEqual((stored['state'], stored['reasons'], stored['literals']['dates']),
                         ('unverified', ['date_unchecked'], [{'value': '2024-03-14', 'precision': 'day'}]))
        self.assertEqual(next(item for item in inv.events['events'] if item['id'] == 'E3')['current'], 'unresolved')

    def test_d67_a_framed_or_wordless_current_time_on_the_undated_document_stays_verified(self):
        for line, words in ((EMR_FRAMED, 'During this procedure'), (EMR_2024.replace('On 03/14/2024, a', 'A'), '')):
            inv, _, _ = emr_document(line, words)
            with self.subTest(words=words):
                self.assertEqual((time_of(inv)['state'], time_of(inv)['reasons']), ('verified', []))
                self.assertEqual(next(item for item in inv.events['events'] if item['id'] == 'E3')['current'], 'yes')


class D67Rejudged(SimpleTestCase):
    """D67(b), the engine: finding 0's EMR, 45390, is never READY on the 2024 act whichever row the effective date
    comes from - held with the time question exactly as the document's own verified date holds it."""

    def assert_held_on_its_time(self, result):
        p = proposal(result, '45390')
        self.assertEqual(p.status, 'needs_clarification')
        self.assertIn('event_time', asked(p))
        self.assertEqual(proposal(result, '45380').status, 'ready')  # the rectal biopsy is today's: no new hold

    def test_d67_control_the_documents_own_verified_date_holds_the_2024_emr(self):
        inv, text, line = emr_document(date_lines={'P0': DATE_LINE}, date_of_service=STATED)
        self.assertEqual(time_of(inv)['reasons'], ['date_mismatch'])
        self.assert_held_on_its_time(assessed(inv, text, line))
        self.assert_held_on_its_time(assessed(inv, text, line, '2026-11-09'))  # the member agrees

    def test_d67_a_members_date_supplied_for_an_undated_document_holds_the_2024_emr(self):
        inv, text, line = emr_document()
        self.assert_held_on_its_time(assessed(inv, text, line, '2026-11-09'))

    def test_d67_a_members_date_settling_geminis_own_date_question_holds_the_2024_emr(self):
        inv, text, line = emr_document(date_lines={'P0': DATE_LINE}, date_of_service=STATED, open_questions=OPENED)
        self.assertEqual(inv.encounter_facts['date_of_service']['value'], None)  # opened: no service date
        self.assert_held_on_its_time(assessed(inv, text, line, '2026-11-09'))

    def test_d67_a_members_date_settling_several_dates_holds_the_2024_emr(self):
        for name, (lines, several) in (('one line', SEVERAL_ONE_LINE), ('two lines', SEVERAL_TWO_LINES)):
            inv, text, line = emr_document(date_lines=lines, date_of_service=several)
            with self.subTest(name):
                self.assertEqual(inv.encounter_facts['date_of_service']['state'], 'several')
                self.assert_held_on_its_time(assessed(inv, text, line, '2026-11-09'))

    def test_d67_control_a_members_date_equal_to_the_day_verifies_the_time(self):
        """No new false hold when the dates agree: the same-day EMR on an undated document is READY once the member's
        date equals its day - and held on its time when the member's date differs."""
        inv, text, line = emr_document(EMR_SAME_DAY, 'On 11/09/2026')
        self.assertEqual(time_of(inv)['reasons'], ['date_unchecked'])
        self.assertEqual(proposal(assessed(inv, text, line, '2026-11-09'), '45390').status, 'ready')
        self.assert_held_on_its_time(assessed(inv, text, line, '2026-11-10'))

    def test_d67_the_stored_inventory_is_never_changed(self):
        inv, text, line = emr_document()
        before = copy.deepcopy((inv.events, inv.encounter_facts, inv.open_questions))
        assessed(inv, text, line, '2026-11-09')
        self.assertEqual((inv.events, inv.encounter_facts, inv.open_questions), before)
        self.assertEqual(time_of(inv)['reasons'], ['date_unchecked'])
        records = inv.events['events']
        copied = verify.rejudged(records, SERVICE)
        self.assertEqual([item['id'] for item in copied], [item['id'] for item in records])
        self.assertTrue(all(new is not old and new['time'] is not old['time'] for new, old in zip(copied, records)))
        self.assertEqual((copied[2]['time']['reasons'], copied[2]['current']), (['date_mismatch'], 'unresolved'))
        self.assertEqual((inv.events, inv.encounter_facts, inv.open_questions), before)
        # each copy's ``current`` follows its re-judged time: the same-day EMR is this encounter's once a date agrees
        same_day, _, _ = emr_document(EMR_SAME_DAY, 'On 11/09/2026')
        stored = next(item for item in same_day.events['events'] if item['id'] == 'E3')
        judged = verify.rejudged(same_day.events['events'], SERVICE)[2]
        self.assertEqual((stored['current'], judged['time']['state'], judged['current']), ('unresolved', 'verified',
                                                                                           'yes'))

    def test_d67_currency_is_normalizes_own_rule_and_rejudging_with_the_inventorys_date_changes_nothing(self):
        """The drift guards: verify.currency equals normalize._current on every time it can meet, and re-judging a
        normalized inventory with the date its normalization used gives back exactly its stored event records."""
        times = [{'value': value, 'state': state, 'open': opened}
                 for value in ('current_encounter', 'earlier_encounter', 'future', 'unknown')
                 for state in ('verified', 'unverified', 'discarded', 'absent') for opened in (False, True)]
        for time in times:
            with self.subTest(time=time):
                self.assertEqual(verify.currency(time), normalize._current(time))
        names = sorted(path.stem for path in (Path(__file__).resolve().parent / 'fixtures' / 'interpretation'
                                              / 'synthetic').glob('*.json'))
        self.assertGreater(len(names), 5)
        inventories = [(name, inventory_of(name)) for name in names]
        inventories += [('finding 0', emr_document()[0]), ('several', emr_document(
            date_lines=SEVERAL_ONE_LINE[0], date_of_service=SEVERAL_ONE_LINE[1])[0])]
        for name, inv in inventories:
            with self.subTest(name):
                own = inv.encounter_facts['date_of_service']['value']  # the verified, unopened date, or None
                self.assertEqual(verify.rejudged(inv.events['events'], own), inv.events['events'])


# --- findings 1 and 18: a whole worded with a sequence word or a clock time keeps holding its part --------------------

SEQUENCE_LEADS = ('Later in the procedure', 'Next', 'At that time', 'At 2030')


def worded(words: str) -> dict:
    return a('current_encounter', words, ['P3']) if words else a('current_encounter')


class D68BiopsyBesideARemoval(SimpleTestCase):
    """Finding 1's first shape: a 6 mm sigmoid polyp biopsied, then removed with a cold snare whose time words are a
    sequence word or a clock time: the biopsy of the lesion removed stays bundled into the removal."""

    BIOPSY = 'A 6 mm sessile polyp in the sigmoid colon was biopsied.'

    def snared(self, words: str):
        line = f'{words}, the polyp was removed with a cold snare.'
        lesion = les('L1', '6 mm sessile polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                     size_words='6 mm')
        biopsy = act('E3', 'P2', 'biopsy', 'biopsied', status_words='was biopsied', technique=a('not_stated'),
                     target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp', ['P2']))
        removal = snare('E2', 'P3', status_words='was removed with a cold snare',
                        technique=a('cold_snare', 'cold snare', ['P3']), target=tg('L1', 'sigmoid_colon', 'the polyp',
                                                                                     ['P3']), time=worded(words))
        inv, text = inventory({'P1': COLONOSCOPE, 'P2': self.BIOPSY, 'P3': line}, events=[exam(), removal, biopsy],
                              lesions=[lesion], reach=[reached()])
        return inv, run(inv, text, [('45380', self.BIOPSY), ('45385', line)])

    def test_d68_a_sequence_word_or_a_clock_time_on_the_removal_keeps_the_biopsy_bundled(self):
        reasons = {'Later in the procedure': ['other_occasion'], 'Next': ['other_occasion'],
                   'At that time': ['other_occasion'], 'At 2030': ['date_mismatch', 'current_unanchored']}
        for words in SEQUENCE_LEADS:
            inv, result = self.snared(words)
            reading = events.Reading.of(inv)
            with self.subTest(words):
                self.assertEqual(reading.events['E2']['time']['reasons'], reasons[words])  # the finding's input
                self.assertTrue(coverage.current_performed(reading.events['E2']))
                self.assertEqual(coverage.bundled_reason(reading, reading.events['E3']),
                                 coverage.COMMON['biopsy_of_removed_lesion'])
                p = proposal(result, '45380')
                self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.BUNDLED))
                self.assertEqual(proposal(result, '45385').status, 'needs_clarification')  # its own time asked


class D68InjectionBesideAnEmr(SimpleTestCase):
    """Finding 1's second shape: a submucosal injection in the cecum beneath the 20 mm flat polyp, then 'Next, the
    polyp was resected by EMR en bloc.': the injection stays the EMR's lift, 45381 held."""

    INJECTION = ('A submucosal injection of saline with methylene blue was given in the cecum beneath the 20 mm flat '
                 'polyp.')

    def test_d68_a_sequence_word_on_the_emr_keeps_its_injection_bundled(self):
        for target_name, target in (('the cecum, no lesion', tg('', 'cecum', 'in the cecum', ['P2'])),
                                    ('the polyp', tg('L1', 'cecum', 'beneath the 20 mm flat polyp', ['P2']))):
            for words in ('Next', 'Later in the procedure'):
                line = f'{words}, the polyp was resected by EMR en bloc.'
                lesion = les('L1', '20 mm flat polyp', 'P2', landmark='cecum', site_words='cecum', size_words='20 mm')
                injection = act('E3', 'P2', 'injection', 'submucosal injection', status_words='was given',
                                target=target)
                resection = act('E2', 'P3', 'emr', 'EMR', status_words='was resected by EMR',
                                target=tg('L1', 'cecum', 'the polyp', ['P3']), time=worded(words))
                inv, text = inventory({'P1': COLONOSCOPE, 'P2': self.INJECTION, 'P3': line},
                                      events=[exam(), resection, injection], lesions=[lesion], reach=[reached()])
                result = run(inv, text, [('45381', self.INJECTION), ('45390', line)])
                with self.subTest(injection=target_name, words=words):
                    p = proposal(result, '45381')
                    self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.BUNDLED))


class D68SphincterotomyBesideAStent(SimpleTestCase):
    """Finding 1's third shape: a biliary sphincterotomy, then 'Next, a 10 Fr by 7 cm plastic biliary stent was placed
    in the common bile duct.': the sphincterotomy stays part of the stent of its duct (D45), 43262 held."""

    LINES = {'P1': 'The duodenoscope was advanced to the major papilla.',
             'P2': 'Deep biliary cannulation was achieved with a sphincterotome and a guidewire.',
             'P3': 'A biliary sphincterotomy was performed with blended current.'}

    def test_d68_a_sequence_word_on_the_stent_keeps_the_sphincterotomy_part_of_it(self):
        for words in ('Next', 'Later in the procedure'):
            line = f'{words}, a 10 Fr by 7 cm plastic biliary stent was placed in the common bile duct.'
            ercp = exam(words='duodenoscope', procedure=a('ercp'))
            cannulation = act('E2', 'P2', 'cannulation', 'cannulation', status_words='was achieved',
                              procedure=a('ercp'), target=tg('', 'bile_duct', 'biliary', ['P2']))
            sphincterotomy = act('E3', 'P3', 'sphincterotomy', 'sphincterotomy', status_words='was performed',
                                 procedure=a('ercp'), target=tg('', 'bile_duct', 'biliary', ['P3']))
            stent = act('E4', 'P4', 'stent', 'stent', status_words='was placed', procedure=a('ercp'),
                        technique=a('stent', 'plastic biliary stent', ['P4']),
                        target=tg('', 'common_bile_duct', 'common bile duct', ['P4']),
                        time=a('current_encounter', words, ['P4']))
            inv, text = inventory({**self.LINES, 'P4': line}, events=[ercp, cannulation, sphincterotomy, stent])
            result = run(inv, text, [('43262', self.LINES['P3']), ('43274', line)])
            with self.subTest(words):
                self.assertEqual(time_of(inv, 'E4')['reasons'], ['other_occasion'])
                p = proposal(result, '43262')
                self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.BUNDLED))
                self.assertIn(coverage.STENT_INCLUDED, check(p, 'service.status').detail)


class D68Finding18(SimpleTestCase):
    """Finding 18's three shapes, 'Next' (and 'Later in the procedure') as the whole's time words: the part's code is
    held - the polyp head's biopsies bundled into its hot snare removal, the lift injection into its EMR, the EGD the
    endoscopic portion of the EUS - while the whole's own code is asked its time."""

    HEAD_POLYP = 'At 30 cm, in the sigmoid colon, there was an 18 mm pedunculated polyp with an irregular head.'
    HEAD_BIOPSY = 'Two cold forceps samples were taken from the polyp head and sent separately.'

    def test_d68_the_polyp_heads_biopsies_stay_bundled_into_a_next_hot_snare_removal(self):
        for words in ('Next', 'Later in the procedure'):
            line = f'{words}, the polyp was removed with a hot snare and retrieved.'
            lesion = les('L1', '18 mm pedunculated polyp', 'P2', landmark='sigmoid_colon', site_words='sigmoid colon',
                         size_words='18 mm')
            biopsy = act('E2', 'P3', 'biopsy', 'cold forceps samples', status_words='were taken',
                         technique=a('cold_forceps', 'cold forceps', ['P3']),
                         target=tg('L1', 'sigmoid_colon', 'the polyp head', ['P3']))
            removal = snare('E3', 'P4', status_words='was removed with a hot snare',
                            technique=a('hot_snare', 'hot snare', ['P4']),
                            target=tg('L1', 'sigmoid_colon', 'the polyp', ['P4']),
                            time=a('current_encounter', words, ['P4']))
            inv, text = inventory({'P1': COLONOSCOPE, 'P2': self.HEAD_POLYP, 'P3': self.HEAD_BIOPSY, 'P4': line},
                                  events=[exam(), biopsy, removal], lesions=[lesion], reach=[reached()])
            result = run(inv, text, [('45380', self.HEAD_BIOPSY), ('45385', line)])
            with self.subTest(words):
                p = proposal(result, '45380')
                self.assertEqual((p.status, p.support['reason'], asked(p)),
                                 ('needs_clarification', events.BUNDLED, ['performed_status']))
                self.assertEqual(asked(proposal(result, '45385')), ['event_time'])

    def test_d68_the_lift_injection_stays_bundled_into_a_next_emr(self):
        polyp = 'In the ascending colon there was a 25 mm flat polyp.'
        lift = 'A submucosal injection of saline with methylene blue was given to lift the lesion.'
        line = 'Next, the lesion was removed by endoscopic mucosal resection in three pieces.'
        lesion = les('L1', '25 mm flat polyp', 'P2', landmark='ascending_colon', site_words='ascending colon',
                     size_words='25 mm')
        injection = act('E2', 'P3', 'injection', 'submucosal injection', status_words='was given',
                        target=tg('L1', 'ascending_colon', 'the lesion', ['P3']),
                        purpose=a('lift_for_resection', 'to lift the lesion', ['P3']))
        resection = act('E3', 'P4', 'emr', 'endoscopic mucosal resection',
                        status_words='was removed by endoscopic mucosal resection',
                        target=tg('L1', 'ascending_colon', 'the lesion', ['P4']), time=a('current_encounter', 'Next',
                                                                                         ['P4']))
        inv, text = inventory({'P1': COLONOSCOPE, 'P2': polyp, 'P3': lift, 'P4': line},
                              events=[exam(), injection, resection], lesions=[lesion], reach=[reached()])
        result = run(inv, text, [('45381', lift), ('45390', line)])
        p = proposal(result, '45381')
        self.assertEqual((p.status, p.support['reason']), ('needs_clarification', events.BUNDLED))
        self.assertEqual(proposal(result, '45390').status, 'needs_clarification')

    def test_d68_the_egd_stays_the_endoscopic_portion_of_a_next_eus(self):
        egd_line = 'EGD: the gastroscope was advanced to the second portion of the duodenum.'
        eus_line = 'Next, the linear echoendoscope was introduced and advanced to the second portion of the duodenum.'
        fna_line = 'A 2.5 cm hypoechoic mass in the pancreatic head was sampled with a 22-gauge needle, three passes.'
        egd = exam('E1', 'P1', words='gastroscope', procedure=a('egd', 'gastroscope', ['P1']))
        eus = exam('E2', 'P2', words='linear echoendoscope', status_words='was introduced and advanced',
                   procedure=a('eus', 'linear echoendoscope', ['P2']), time=a('current_encounter', 'Next', ['P2']))
        fna = act('E3', 'P3', 'fna', 'sampled', status_words='was sampled with a 22-gauge needle',
                  procedure=a('eus', 'needle', ['P3']), technique=a('needle', '22-gauge needle', ['P3']),
                  target=tg('', 'pancreas', 'pancreatic head', ['P3']))
        inv, text = inventory({'P1': egd_line, 'P2': eus_line, 'P3': fna_line}, events=[egd, eus, fna],
                              reach=[reached('E1', 'second_portion_duodenum', 'second portion of the duodenum', 'P1'),
                                     reached('E2', 'second_portion_duodenum', 'second portion of the duodenum', 'P2')])
        sessions_ = coverage.sessions(events.Reading.of(inv))
        # D87/D70: the 'Next' EUS examination is possible, never done: the EGD may be its endoscopic portion
        self.assertEqual((sessions_['gi.eus'].examinations, sessions_['gi.eus'].possible, sessions_['gi.egd'].part_of,
                          sessions_['gi.egd'].possibly_part_of), ((), ('E2',), '', 'gi.eus'))
        result = run(inv, text, [('43235', egd_line), ('43242', fna_line)])
        p = proposal(result, '43235')
        self.assertEqual(p.status, 'needs_clarification')
        self.assertIn('base_included', asked(p))


class D68AdjunctBesideARemoval(SimpleTestCase):
    """The relations step's half of D68 (relations._possibly_current): D41's procedural_adjunct bundling identity is
    recorded beside a removal whose time words are a sequence word, so the bleeding control that names nothing is asked
    (act_target), never READY alone beside it."""

    def test_d68_a_bleeding_control_beside_a_next_polypectomy_is_asked(self):
        line = 'Next, a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
        removal = snare('E2', 'P2', target=tg('L1', 'sigmoid_colon', '6 mm sessile polyp in the sigmoid colon', ['P2']),
                        time=a('current_encounter', 'Next', ['P2']))
        clips = 'Immediate oozing from the polypectomy site was controlled with two hemoclips for hemostasis.'
        inv, text = colonoscopy(hemoclips(), polyp=removal, lines={'P2': line, 'P3': clips})
        self.assertEqual(time_of(inv, 'E2')['reasons'], ['other_occasion'])
        self.assertIn(('bundling_identity', 'procedural_adjunct'),
                      [(item['type'], item['reason']) for item in inv.events['relations'] if item['event'] == 'E3'])
        p = proposal(run(inv, text, [('45385', line), ('45382', clips)]), '45382')
        self.assertEqual((p.status, asked(p), p.support['reason']),
                         ('needs_clarification', ['act_target'], events.BUNDLING_IDENTITY))


class D68PossiblyCurrent(SimpleTestCase):
    def test_d68_a_current_encounter_time_is_possibly_current_whatever_its_reasons(self):
        for reasons in (['other_occasion'], ['date_mismatch'], ['date_mismatch', 'current_unanchored'],
                        ['date_unchecked'], ['current_unanchored'], []):
            time = {'value': 'current_encounter', 'state': 'unverified' if reasons else 'verified', 'open': False,
                    'reasons': reasons}
            with self.subTest(reasons=reasons):
                self.assertTrue(coverage.possibly_current({'time': time}))
                self.assertTrue(relations._possibly_current({'time': time, 'current': verify.currency(time)}))
        for value in ('earlier_encounter', 'future'):
            for state in ('verified', 'unverified'):
                time = {'value': value, 'state': state, 'open': False, 'reasons': [] if state == 'verified'
                        else ['date_mismatch']}
                with self.subTest(value=value, state=state):
                    self.assertFalse(coverage.possibly_current({'time': time}))
                    self.assertFalse(relations._possibly_current({'time': time, 'current': verify.currency(time)}))


# --- the chain: the member's date at upload, and saved afterwards -----------------------------------------------------

class D67Chain(EventsCase):
    """D67 through the production chain (extract, interpret by replay, analyze, predict with the Corti fake, assess),
    the legacy reader's entry points failing if called: the 2024 EMR's 45390 is held on its time whether the member's
    date is entered at upload or saved afterwards (jobs.change_context, on the frozen inventory), and the same-day EMR
    is READY once the member's date agrees with its day."""
    corti_groups = ((('45380', BIOPSY_LINE), ('45390', EMR_2024)), (('45380', BIOPSY_LINE), ('45390', EMR_SAME_DAY)))

    def upload_with(self, user_values, emr_line=EMR_2024, time_words='On 03/14/2024'):
        value, lines = emr_answer(emr_line, time_words)
        text = HEAD + '\n'.join(lines.values()) + '\n'
        encounter = models.Encounter.objects.create(workspace=self.ws, title='Synthetic note', created_by=self.user,
                                                    user_values=user_values)
        revision = f.pasted_revision(encounter, self.user, text, extract=False)
        jobs.start_pipeline(revision, self.user)
        self.run_next(models.Job.EXTRACT)
        revision.refresh_from_db()
        kind = jobs._participant_document(revision)[0]
        request = adapter.build_request(revision.text, jobs._participant_pages(revision), kind)
        folder = Path(self.replay) / adapter.NAME
        folder.mkdir(exist_ok=True)
        (folder / f'{request.canonical_sha256}.json').write_bytes(envelope(value))
        return encounter

    def drained(self, encounter):
        with self.legacy_reader_fails():
            ran = self.drain()
        self.assertTrue(ran and all(job.state == models.Job.SUCCEEDED for job in ran),
                        [(job.kind, job.state, job.error) for job in ran])
        encounter.refresh_from_db()
        assessment = models.Assessment.objects.get(pk=encounter.current_assessment_id)
        self.assertEqual(assessment.engine_version, 'cpt-studio-events@1')
        stored = models.EventInventory.objects.get(pk=assessment.event_inventory_id)
        return assessment, next(item for item in stored.events['events'] if item['id'] == 'E3')['time']

    def save_date(self, encounter, value):
        with self.legacy_reader_fails():
            jobs.change_context(encounter, self.user, {'service_date': value})
        return self.drained(encounter)

    def test_d67_the_members_date_at_upload_and_saved_afterwards_holds_the_2024_emr(self):
        assessment, stored = self.drained(self.upload_with({'service_date': '2026-11-09'}))
        self.assertEqual(assessment.context.facts['service_date']['state'], 'supplies')
        self.assertEqual((stored['state'], stored['reasons']), ('unverified', ['date_unchecked']))  # never re-written
        held = self.proposal(assessment, '45390')
        self.assertEqual(held.status, 'needs_clarification')
        self.assertIn('event_time', [spec.fact for spec in held.clarifications.all()])
        self.assertEqual(self.proposal(assessment, '45380').status, 'ready')
        encounter = self.upload_with({})
        first, _ = self.drained(encounter)
        self.assertEqual(self.proposal(first, '45390').status, 'needs_clarification')
        saved, stored = self.save_date(encounter, '2026-11-09')
        self.assertNotEqual(saved.pk, first.pk)
        self.assertEqual((saved.context.facts['service_date']['state'], stored['reasons']),
                         ('supplies', ['date_unchecked']))
        held = self.proposal(saved, '45390')
        self.assertEqual(held.status, 'needs_clarification')
        self.assertIn('event_time', [spec.fact for spec in held.clarifications.all()])

    def test_d67_control_the_members_saved_date_equal_to_the_day_makes_the_same_day_emr_ready(self):
        encounter = self.upload_with({}, EMR_SAME_DAY, 'On 11/09/2026')
        first, stored = self.drained(encounter)
        self.assertEqual((stored['state'], stored['reasons']), ('unverified', ['date_unchecked']))
        self.assertEqual(self.proposal(first, '45390').status, 'needs_clarification')
        saved, _ = self.save_date(encounter, '2026-11-09')
        self.assertEqual(self.proposal(saved, '45390').status, 'ready')
