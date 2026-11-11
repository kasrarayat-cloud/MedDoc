"""DECISIONS D128 (the review of D99, problems 0, 1 and 2): where a current time no date has checked yet pairs as
current.

D99 (round 4, finding 8) read a current_encounter time whose ONLY failure is date_unchecked - D67(a): a day literal no
service date could check yet, unopened; here "a pending check" - as current on BOTH sides of the pairing table. The
pairing is made once, at normalize, before any date decides the day, and assess re-judges the times but reuses the
stored relations (D67's residual). The review found:
- (0) the undated note's snare 'On 06/02/2025, a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
  beside 'Impression: No polypectomy was performed.' stayed a CONTRADICTION after the member's 2026-11-09 made it another
  day's: 45385 asked conflict:snare, the conflicts check said warn and completeness '1 conflict in the record', where the
  act's own time is the question (event_time; the installed release c2e53f8e asks performed_status, conflicts pass);
- (1) beside 'As previously noted, no polypectomy was performed.' (Gemini: earlier_encounter, verified only by the C1
  marker 'previously'), the pending snare was INDEPENDENT and READY once the member's date equalled its day, where the
  installed release asks conflict:snare;
- (2) the examination Counter (the pairing's unresolved sessions) never read D99.

D128 (relations.time_row) keeps D99's reading only where it can only hold. Beside a DENIAL, only the denial's own
pending check pairs as current, and only against an act whose time is verified current; the act's pending check (and
two) is UNKNOWN, as before D99: it is its own code's question. So with the member's equal date the re-judged act's time
is usable and the denial's UNRESOLVED(time) relation asks the contradiction as the statement's scope (D102), and with
another date or none the act's time. A pending check never sets a pair apart. Beside a doubt, a planned act a claim
names or a claim's other act, D99's reading stands: a DOUBT keeps the codes of its kinds from an exclusion
(events._doubted), and withdrawn it let a colonoscopy denial exclude 45385. The Counter is not changed, and the reason
is recorded with pins: counting a pending examination makes every all_of_kind pair of its family session_unresolved
before any date, which takes a contradiction's question and a doubt's exclusion guard (D87, D89).

SYNTHETIC: the S08 builders and the round-4 currency module's answers; the chain is built like
tests.test_pipeline_assess_events (the replay interpreter, the in-process Corti fake, the legacy entry points failing if
called). Nothing is sent. The installed release's outputs quoted here were run first-hand on the same texts (with a
'PROCEDURE: Colonoscopy' header so that its routing finds the colonoscopy; jobs._assess_child as h2h/run_registry.py
builds it)."""
from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase

from studio import jobs, models
from studio.interpretation import adapter, events, normalize, relations, verify
from tests.support import factories as f
from tests.test_interpretation_events import POLYP, asked, exam, proposal, reached, run
from tests.test_interpretation_identity import a, accepted, act, les, sc, snare, tg
from tests.test_interpretation_r3_currency import DATE_LINE, NOT_STATED, STATED
from tests.test_interpretation_r4_currency_pairing import (CONTRADICTED, DATED_POLYP, DENIAL, UNDATED, conflicts_check,
                                                           denial_answer, denial_document, stored_relations)
from tests.test_pipeline_assess_events import HEAD, EventsCase, envelope

UNRESOLVED_TIME = [('unresolved', 'E3', 'E2', 'time', 'time_unresolved')]
OLD_POLYP = 'On 06/02/2025, a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
NOTED = 'As previously noted, no polypectomy was performed.'
PREVIOUSLY = 'Previously, no polyp was removed.'
DATED_DENIAL = 'On 11/09/2026, no polypectomy was performed.'
SECOND = 'On 11/09/2026, the colonoscope was reinserted to the cecum.'
STATED_10 = {'value': '2026-11-10', 'state': 'stated', 'words': '11/10/2026', 'passages': ['P0'], 'other_dates': []}
DATE_LINE_10 = 'Date of service: 11/10/2026.'


def normalized(value: dict, lines: dict) -> tuple:
    """(the normalized inventory, the document's text) of a synthetic answer over ``lines``."""
    text = '\n'.join(lines.values()) + '\n'
    return normalize.normalize(accepted(value), text), text


def with_line(value: dict, lines: dict, pid: str, line: str, event: dict) -> None:
    lines[pid] = line
    value['passages'].append({'id': pid, 'text': line})
    value['events'].append(event)


def member(day):
    return {'service_date': day} if day else {}


def held(test, result, code: str, facts: list, *, conflict: bool):
    """``code`` is selected and held asking exactly ``facts``; the conflicts check and completeness state a conflict
    exactly when ``conflict``."""
    p = proposal(result, code)
    test.assertEqual((p.bucket, p.status, asked(p)), ('selected', 'needs_clarification', facts))
    test.assertEqual(conflicts_check(result).status, 'warn' if conflict else 'pass')
    test.assertEqual('1 conflict in the record' in result.completeness['reasons'], conflict)
    return p


def scope_asked(test, p, statement: str):
    """The statement_scope question of D102 (D103: the statement quoted whole) about the snare of the polyp."""
    act_label = 'snare removal (cold snare) of the 6 mm sessile polyp in the sigmoid colon'
    test.assertEqual(p.clarifications[0].question,
                     f'Does “{statement}” apply to the {act_label} (“was removed with a cold snare”)?')


# --- the time row ------------------------------------------------------------------------------------------------------

PENDING = dict(state='unverified', reasons=['date_unchecked'], found={'dates': [{'value': '2026-11-09',
                                                                                 'precision': 'day'}]})


def side(value: str = 'current_encounter', state: str = 'verified', reasons=(), opened: bool = False,
         basis: str = 'stated', found=None, status: str = 'performed') -> dict:
    """An event as time_row reads it: its time record as normalize stores it, and its status."""
    return {'time': {'value': value, 'state': state, 'reasons': list(reasons), 'open': opened, 'basis': basis,
                     'literals': found or {}},
            'status': {'value': status, 'state': 'verified'}}


PENDING_10 = dict(state='unverified', reasons=['date_unchecked'], found={'dates': [{'value': '2026-11-10',
                                                                                    'precision': 'day'}]})


class D128TimeRow(SimpleTestCase):
    """relations.time_row: beside a DENIAL only the denial's own pending check pairs, against an act whose time is
    verified current; beside a doubt, a planned act a claim names or a claim's other act, D99's reading stands; and a
    pending check never sets a pair apart."""
    UNKNOWN = relations.Row('time', relations.UNKNOWN, 'time_unresolved')
    SAME = relations.Row('time', relations.SAME)

    def test_d128_a_statements_pending_check_pairs_against_a_verified_current_act(self):
        acts = {'a default time': side(basis='default'), 'a time framed as today': side(),
                'an act begun and not completed': side(basis='default', status='attempted_not_completed')}
        for status in ('not_performed', 'uncertain', 'planned'):
            for name, act_side in acts.items():
                with self.subTest(status=status, act=name):
                    self.assertEqual(relations.time_row(side(**PENDING, status=status), act_side), self.SAME)

    def test_d128_beside_a_denial_an_acts_pending_check_never_pairs_and_no_pending_check_sets_a_pair_apart(self):
        earlier = side('earlier_encounter', found={'markers': ['previously']}, status='not_performed')
        cases = {
            # (0): the act's own time is the question until a date decides it
            "the act's pending check beside a denial's default time": (side(basis='default', status='not_performed'),
                                                                        side(**PENDING)),
            "the act's pending check beside a denial's time framed as today": (side(status='not_performed'),
                                                                               side(**PENDING)),
            'both pending, the same day': (side(**PENDING, status='not_performed'), side(**PENDING)),
            'both pending, another day': (side(**PENDING, status='not_performed'), side(**PENDING_10)),
            # (1): never set apart by a day no date has checked
            "the act's pending check beside a denial dated earlier by its marker": (earlier, side(**PENDING)),
            "the act's pending check beside a denial set in the future by its marker": (
                side('future', found={'markers': ['next']}, status='not_performed'), side(**PENDING)),
            "a statement's pending check beside an act dated earlier by its marker": (
                side(**PENDING, status='not_performed'), side('earlier_encounter', found={'markers': ['previously']})),
            "the act's pending check beside a doubt dated earlier by its marker": (
                side('earlier_encounter', found={'markers': ['previously']}, status='uncertain'), side(**PENDING)),
            "a claim's pending act beside an act dated earlier by its marker": (
                side(**PENDING), side('earlier_encounter', found={'markers': ['previously']})),
            "a statement's pending check beside an act whose own time is unanchored": (
                side(**PENDING, status='not_performed'), side(state='unverified', reasons=['current_unanchored'])),
            "a statement's pending check beside an act whose time is unknown": (
                side(**PENDING, status='not_performed'), side('unknown', 'absent', basis='absent')),
        }
        for name, (statement, act_side) in cases.items():
            with self.subTest(name):
                self.assertEqual(relations.time_row(statement, act_side), self.UNKNOWN)

    def test_d128_beside_a_doubt_a_planned_act_or_a_claim_d99_stands(self):
        """Not a denial: the pair is a DOUBT or a claim's UNRESOLVED, which only holds - and a DOUBT keeps the codes of
        its kinds from an exclusion (D128DoubtKept) - so a pending check on either side pairs as current, against a
        current time or another pending check, as at D99 (whose day comparison reads the values only)."""
        for status in ('uncertain', 'planned', 'performed'):
            cases = {"the act's pending check beside a default time": (side(basis='default', status=status),
                                                                        side(**PENDING)),
                     "the act's pending check beside a time framed as today": (side(status=status), side(**PENDING)),
                     'both pending, the same day': (side(**PENDING, status=status), side(**PENDING)),
                     'both pending, another day': (side(**PENDING, status=status), side(**PENDING_10))}
            for name, (statement, act_side) in cases.items():
                with self.subTest(status=status, case=name):
                    self.assertEqual(relations.time_row(statement, act_side), self.SAME)

    def test_d128_control_every_other_unverified_statement_time_stays_unknown(self):
        """D99's control, with a statement's status on that side - a denial's, and a doubt's (round 4's control reads
        sides with no status): only date_unchecked ALONE, on an unopened current_encounter time, is a pending
        check."""
        others = {
            'date_unchecked with current_unanchored': dict(state='unverified',
                                                           reasons=['date_unchecked', 'current_unanchored']),
            'date_unchecked with other_occasion': dict(state='unverified', reasons=['date_unchecked', 'other_occasion']),
            'date_unchecked, opened by an open question': dict(state='unverified', reasons=['date_unchecked'],
                                                                opened=True),
            'date_mismatch': dict(state='unverified', reasons=['date_mismatch']),
            'current_unanchored': dict(state='unverified', reasons=['current_unanchored']),
            'an earlier time date_unchecked': dict(value='earlier_encounter', state='unverified',
                                                   reasons=['date_unchecked']),
            'a future time date_unchecked': dict(value='future', state='unverified', reasons=['date_unchecked']),
            'unknown': dict(value='unknown', state='absent', basis='absent'),
            'discarded': dict(state='discarded', reasons=['date_unchecked']),
        }
        for status in ('not_performed', 'uncertain'):
            for name, options in others.items():
                with self.subTest(status=status, time=name):
                    self.assertEqual(relations.time_row(side(**options, status=status), side(basis='default')),
                                     self.UNKNOWN)
                    self.assertEqual(relations.time_row(side(basis='default', status=status), side(**options)),
                                     self.UNKNOWN)

    def test_d128_control_two_usable_times_pair_as_before(self):
        default = side(basis='default')
        self.assertEqual(relations.time_row(side(basis='default', status='not_performed'), default),
                         relations.Row('time', relations.SAME))
        self.assertEqual(relations.time_row(side('earlier_encounter', found={'markers': ['previously']},
                                                 status='not_performed'), default),
                         relations.Row('time', relations.DIFFERENT, 'another_time', False))
        self.assertEqual(relations.time_row(side('earlier_encounter', found={'dates': [{'value': '2024-03-14',
                                                                                         'precision': 'day'}]},
                                                 status='not_performed'), default),
                         relations.Row('time', relations.DIFFERENT, 'another_time', True))
        self.assertEqual(verify.exclusion_basis('time', side(**PENDING)['time']), '')  # a pending day is no literal


# --- (0): the member's date decides the day after the pairing was made ----------------------------------------------

class D128MemberDates(SimpleTestCase):
    """Problem 0's inputs: the undated note's dated snare beside the impression's denial is UNRESOLVED(time) at
    normalize; whichever date decides the day afterwards, 45385 is held on the question that day leaves - never READY,
    never excluded."""

    def test_d128_another_day_asks_the_acts_time_and_never_a_conflict(self):
        """The member's date makes the snare another day's: 45385 asks its time (event_time), the conflicts check is
        pass and completeness states no conflict. D99 asked conflict:snare with warn on each; the installed release asks
        performed_status with pass on each (with a report header)."""
        several = UNDATED["'several' dates on one line"][0]  # 'Date of service: 11/08/2026 or 11/09/2026.'
        cases = {
            "'On 06/02/2025' and the member's 2026-11-09 (the review's input)": (
                denial_document(OLD_POLYP, 'On 06/02/2025'), '2026-11-09'),
            "'On 11/09/2026' and the member's 2026-11-10": (denial_document(), '2026-11-10'),
            "'On 11/09/2026' and the member's 2026-11-08": (denial_document(), '2026-11-08'),
            "'several' dates (11/08 or 11/09), the member choosing 2026-11-08": (denial_document(**several),
                                                                                 '2026-11-08'),
        }
        for name, ((inv, text, line), day) in cases.items():
            with self.subTest(name):
                self.assertEqual(stored_relations(inv), UNRESOLVED_TIME)
                held(self, run(inv, text, [('45385', line)], user_values=member(day)), '45385', ['event_time'],
                     conflict=False)

    def test_d128_with_no_date_the_act_is_asked_its_time(self):
        """No date decides the day: 45385 asks its time, and the encounter's date question stands beside it. D99 asked
        conflict:snare with warn; the installed release asks performed_status with pass."""
        inv, text, line = denial_document()
        result = run(inv, text, [('45385', line)])
        held(self, result, '45385', ['event_time'], conflict=False)
        self.assertIn('service_date', [item.fact for item in result.clarifications])

    def test_d128_the_members_equal_date_asks_the_contradiction_as_the_statements_scope(self):
        """The member's date equals the snare's day (the five undated variants of round 4, and 'several' settled on
        11/09): the re-judged time is usable, so the denial's UNRESOLVED(time) relation asks the contradiction as the
        statement's scope (D102), quoting the impression whole (D103). D99 asked conflict:snare with warn; the installed
        release asks conflict:snare with warn on the note with no date line - the statement_scope question asks that
        contradiction (the scoring adjudication of 2026-11-10) - and performed_status on 'several' dates (one line)
        settled on 11/09, where its context leaves the day None (the other variants were not run there). The conflicts
        check is pass (the recorded cost: assess reuses the relation)."""
        for name, (options, line, words) in UNDATED.items():
            inv, text, line = denial_document(line, words, **options)
            with self.subTest(name):
                self.assertEqual(stored_relations(inv), UNRESOLVED_TIME)
                p = held(self, run(inv, text, [('45385', line)], user_values=member('2026-11-09')), '45385',
                         ['statement_scope'], conflict=False)
                scope_asked(self, p, DENIAL)

    def test_d128_control_the_documents_own_date_decides_at_normalize(self):
        """The reference: with the document's own date the pairing is made with the day decided. 11/09/2026 (the
        snare's day): CONTRADICTION, conflict:snare, warn - as the installed release. 11/10/2026: UNRESOLVED(time),
        event_time, pass (the installed release asks performed_status)."""
        inv, text, line = denial_document(date_lines={'P0': DATE_LINE}, date_of_service=STATED)
        self.assertEqual(stored_relations(inv), CONTRADICTED)
        held(self, run(inv, text, [('45385', line)]), '45385', ['conflict:snare'], conflict=True)
        inv, text, line = denial_document(date_lines={'P0': DATE_LINE_10}, date_of_service=STATED_10)
        self.assertEqual(stored_relations(inv), UNRESOLVED_TIME)
        held(self, run(inv, text, [('45385', line)]), '45385', ['event_time'], conflict=False)


# --- (1): an earlier denial verified by its marker never sets the pending act apart -----------------------------------

def earlier_denial(line: str, words: str, status_words: str, scope_words: str, **options) -> tuple:
    """Round 4's dated snare (E2, 'On 11/09/2026') beside an earlier denial ``line`` (E3: removal, not_performed,
    all_of_kind; time earlier_encounter worded ``words``)."""
    value, lines = denial_answer(denied=False, **options)
    with_line(value, lines, 'P3', line, act('E3', 'P3', 'removal', 'removed' if 'removed' in line else 'polypectomy',
                                            status='not_performed', status_words=status_words,
                                            scope=sc('all_of_kind', scope_words, ['P3']),
                                            time=a('earlier_encounter', words, ['P3'])))
    return normalized(value, lines)


EARLIER = {
    "'As previously noted, ...' (the review's input)": (NOTED, 'As previously noted', 'no polypectomy was performed',
                                                        'no polypectomy'),
    "'Previously, no polyp was removed.' (round 4's)": (PREVIOUSLY, 'Previously', 'no polyp was removed', 'no polyp'),
}


class D128EarlierDenial(SimpleTestCase):
    """Problem 1's input: a denial Gemini dates earlier_encounter, its time verified only by the C1 marker 'previously',
    beside the undated note's pending snare is UNRESOLVED(time), never INDEPENDENT: once the member's date equals the
    snare's day, 45385 is held, the denial asked as its scope - never READY."""

    def test_d128_an_earlier_denial_verified_by_its_marker_never_sets_the_pending_act_apart(self):
        """Installed c2e53f8e: 'As previously noted': no date performed_status, 2026-11-09 conflict:snare (warn),
        2026-11-10 performed_status; 'Previously': no date performed_status, 2026-11-09 READY, 2026-11-10 EXCLUDED as
        historical. D99 made 45385 READY with 2026-11-09 on both (437b708bb held it, event_time)."""
        for name, (line, words, status_words, scope_words) in EARLIER.items():
            inv, text = earlier_denial(line, words, status_words, scope_words)
            denial = events.Reading.of(inv).events['E3']
            with self.subTest(name):
                self.assertEqual((denial['time']['value'], denial['time']['state'],
                                  denial['time']['literals'].get('markers')),
                                 ('earlier_encounter', 'verified', ['previously']))
                self.assertEqual(stored_relations(inv), UNRESOLVED_TIME)
                p = held(self, run(inv, text, [('45385', DATED_POLYP)], user_values=member('2026-11-09')), '45385',
                         ['statement_scope'], conflict=False)
                scope_asked(self, p, line)
                for day in (None, '2026-11-10'):
                    held(self, run(inv, text, [('45385', DATED_POLYP)], user_values=member(day)), '45385',
                         ['event_time'], conflict=False)

    def test_d128_control_the_documents_own_date_still_sets_it_apart(self):
        """D128 is the pending check's: with the document's own date the snare's time is verified at normalize, and the
        marker-verified earlier denial is another time (INDEPENDENT), 45385 READY - as at 437b708bb. The installed
        release is READY beside 'Previously' and asks conflict:snare beside 'As previously noted' (recorded, outside
        D128)."""
        for name, (line, words, status_words, scope_words) in EARLIER.items():
            inv, text = earlier_denial(line, words, status_words, scope_words, date_lines={'P0': DATE_LINE},
                                       date_of_service=STATED)
            with self.subTest(name):
                self.assertEqual(stored_relations(inv), [('independent', 'E3', 'E2', 'time', 'another_time')])
                self.assertEqual(proposal(run(inv, text, [('45385', DATED_POLYP)]), '45385').status, 'ready')


# --- the statement's side, kept; two pending checks; a model's claim between two acts ---------------------------------

def dated_denial_document(**options) -> tuple:
    """The snare with no time words (POLYP, the frame default) beside 'On 11/09/2026, no polypectomy was performed.'
    (E3: removal, not_performed, all_of_kind; current_encounter worded 'On 11/09/2026')."""
    value, lines = denial_answer(POLYP, '', denied=False, **options)
    with_line(value, lines, 'P3', DATED_DENIAL,
              act('E3', 'P3', 'removal', 'polypectomy', status='not_performed',
                  status_words='no polypectomy was performed', scope=sc('all_of_kind', 'no polypectomy', ['P3']),
                  time=a('current_encounter', 'On 11/09/2026', ['P3'])))
    return normalized(value, lines)


class D128StatementSide(SimpleTestCase):

    def test_d128_a_statements_pending_check_beside_a_verified_current_act_is_the_contradiction(self):
        """The spec's kept direction: the act's own time is verified (the frame default), so no question of its code is
        displaced, and the stored CONTRADICTION asks conflict:snare whatever the date - exactly as the installed release
        asks it on that text with no date, 2026-11-09 and 2026-11-10 (conflicts warn on each)."""
        inv, text = dated_denial_document()
        denial = events.Reading.of(inv).events['E3']
        self.assertEqual((denial['time']['state'], denial['time']['reasons']), ('unverified', ['date_unchecked']))
        self.assertEqual(stored_relations(inv), CONTRADICTED)
        for day in (None, '2026-11-09', '2026-11-10'):
            with self.subTest(member=day):
                held(self, run(inv, text, [('45385', POLYP)], user_values=member(day)), '45385', ['conflict:snare'],
                     conflict=True)

    def test_d128_two_pending_checks_never_pair(self):
        """The dated snare beside the dated denial, both 'On 11/09/2026' on the undated note: D99 paired them (SAME) and
        45385 asked conflict:snare with every date. Now UNRESOLVED(time): with 2026-11-10 (both another day's) the act's
        time, with no date the act's time, and with 2026-11-09 the denial as its scope. Installed: performed_status with
        2026-11-10 and with no date, conflict:snare (warn) with 2026-11-09."""
        value, lines = denial_answer(denied=False)
        with_line(value, lines, 'P3', DATED_DENIAL,
                  act('E3', 'P3', 'removal', 'polypectomy', status='not_performed',
                      status_words='no polypectomy was performed', scope=sc('all_of_kind', 'no polypectomy', ['P3']),
                      time=a('current_encounter', 'On 11/09/2026', ['P3'])))
        inv, text = normalized(value, lines)
        self.assertEqual(stored_relations(inv), UNRESOLVED_TIME)
        for day, facts in ((None, ['event_time']), ('2026-11-10', ['event_time']), ('2026-11-09', ['statement_scope'])):
            with self.subTest(member=day):
                held(self, run(inv, text, [('45385', DATED_POLYP)], user_values=member(day)), '45385', facts,
                     conflict=False)

    def test_d128_a_pending_denial_never_sets_an_earlier_act_apart(self):
        """'Previously, a 6 mm sessile polyp ... was removed with a cold snare.' (earlier, verified by its marker) beside
        the pending dated denial: D99 stored INDEPENDENT (another_time); now UNRESOLVED(time). 45385, cited on the
        earlier snare, is asked the denial's scope either way (the exclusion arm, 7.5); installed: performed_status."""
        line = 'Previously, a 6 mm sessile polyp in the sigmoid colon was removed with a cold snare.'
        value, lines = denial_answer(line, '', denied=False)
        value['events'][1]['time'] = a('earlier_encounter', 'Previously', ['P2'])
        with_line(value, lines, 'P3', DATED_DENIAL,
                  act('E3', 'P3', 'removal', 'polypectomy', status='not_performed',
                      status_words='no polypectomy was performed', scope=sc('all_of_kind', 'no polypectomy', ['P3']),
                      time=a('current_encounter', 'On 11/09/2026', ['P3'])))
        inv, text = normalized(value, lines)
        self.assertEqual(stored_relations(inv), UNRESOLVED_TIME)
        for day in (None, '2026-11-09'):
            with self.subTest(member=day):
                p = proposal(run(inv, text, [('45385', line)], user_values=member(day)), '45385')
                self.assertEqual((p.status, asked(p)), ('needs_clarification', ['statement_scope']))


class D128PositiveClaim(SimpleTestCase):

    def test_d128_a_claim_between_two_acts_keeps_d99s_reading(self):
        """Gemini claims the dated snare (E2, 'On 11/09/2026') and a second snare of the polyp (E4, the frame default)
        cannot both be true, the claim listed on either event. No denial is paired, so D99's reading stands: "no
        difference" (UNRESOLVED(status), claim_no_difference) both ways, and 45385 is held asking performed_status with
        every date - as at 1caaf0609. Installed: performed_status with no date and with 2026-11-10, READY with
        2026-11-09."""
        second = 'The polyp was removed with a cold snare.'
        for listed_on in ('E2', 'E4'):
            value, lines = denial_answer(denied=False)
            with_line(value, lines, 'P4', second, snare('E4', 'P4', target=tg('L1', 'sigmoid_colon', 'The polyp',
                                                                               ['P4'])))
            claimed = 'E4' if listed_on == 'E2' else 'E2'
            next(item for item in value['events'] if item['id'] == listed_on)['contradicts'] = [
                {'event': claimed, 'passages': ['P2', 'P4']}]
            inv, text = normalized(value, lines)
            with self.subTest(listed_on=listed_on):
                self.assertEqual(sorted(stored_relations(inv)),
                                 [('unresolved', 'E2', 'E4', 'status', 'claim_no_difference'),
                                  ('unresolved', 'E4', 'E2', 'status', 'claim_no_difference')])
                for day in (None, '2026-11-10', '2026-11-09'):
                    p = proposal(run(inv, text, [('45385', DATED_POLYP)], user_values=member(day)), '45385')
                    self.assertEqual((p.status, asked(p)), ('needs_clarification', ['performed_status']), day)


# --- a doubt keeps D99's reading: its DOUBT keeps the codes of its kinds from an exclusion ----------------------------

def two_families(dated: bool = False, doubt_time=None) -> tuple:
    """An EGD and a colonoscopy, each family verified by its own words: the EGD to the duodenum (E0), its cold snare of
    a 5 mm gastric body polyp worded 'On 11/09/2026' (E5, a pending check on the undated note), 'EGD: It is unclear
    whether the gastric body polyp was removed.' (E6: removal, uncertain, that polyp; its time ``doubt_time`` when
    given), the colonoscopy to the cecum (E1) and 'Colonoscopy: No polyp was removed.' (E2: removal, not_performed,
    all_of_kind); the document's own 11/09/2026 when ``dated``. (The input an earlier, interrupted build of this repair
    recorded, repair5/currency2.)"""
    lines = {**({'P0': DATE_LINE} if dated else {}), 'P0b': 'EGD: the gastroscope was advanced to the duodenum.',
             'P5': 'EGD: On 11/09/2026, a 5 mm polyp in the gastric body was removed with a cold snare.',
             'P6': 'EGD: It is unclear whether the gastric body polyp was removed.',
             'P1': 'Colonoscopy: The colonoscope was advanced to the cecum.',
             'P2': 'Colonoscopy: No polyp was removed.'}
    egd, colon = (lambda pid: a('egd', 'EGD', [pid])), (lambda pid: a('colonoscopy', 'Colonoscopy', [pid]))
    doubt = act('E6', 'P6', 'removal', 'removed', status='uncertain', procedure=egd('P6'),
                status_words='It is unclear whether the gastric body polyp was removed',
                target=tg('L2', 'gastric_body', 'gastric body polyp', ['P6']),
                scope=sc('single_target', 'the gastric body polyp', ['P6']))
    if doubt_time is not None:
        doubt['time'] = doubt_time
    found = [exam('E0', 'P0b', words='gastroscope', procedure=egd('P0b')),
             snare('E5', 'P5', procedure=egd('P5'), time=a('current_encounter', 'On 11/09/2026', ['P5']),
                   target=tg('L2', 'gastric_body', '5 mm polyp in the gastric body', ['P5'])),
             doubt, exam('E1', 'P1', procedure=colon('P1')),
             act('E2', 'P2', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                 procedure=colon('P2'), scope=sc('all_of_kind', 'No polyp', ['P2']))]
    value = {'passages': [{'id': pid, 'text': text} for pid, text in lines.items()],
             'encounter': {'date_of_service': STATED if dated else NOT_STATED,
                           'documenting_endoscopist': {'words': '', 'passages': []}, 'team': [], 'anatomy': [],
                           'reach': [reached('E1', passage='P1'),
                                     reached('E0', 'second_portion_duodenum', 'duodenum', 'P0b')], 'visit_facts': []},
             'lesions': [les('L2', '5 mm polyp', 'P5', landmark='gastric_body', site_words='gastric body',
                             size_words='5 mm')],
             'events': found, 'open_questions': []}
    return normalized(value, lines)


CODES = [('45385', 'No polyp was removed'), ('43251', 'was removed with a cold snare')]


class D128DoubtKept(SimpleTestCase):
    """Beside a doubt, D99's reading stands, because it can only hold: the EGD's doubted gastric snare, a pending check
    on the undated note, is a DOUBT as on the dated document, and events._doubted (FINAL 7.5 (4): a DOUBT relation from
    a statement of the code's kinds) keeps the colonoscopy's 'No polyp was removed.' from excluding 45385, which cites
    it. Read UNKNOWN there - D128's denial arm applied to every statement - the pair was UNRESOLVED(time) and 45385 went
    from held to EXCLUDED with every date. The installed release excludes 45385 on all of these texts (FINAL 7.5 (4)'s
    own difference from it, which this repair does not reopen: it only adds holds)."""

    def test_d128_a_doubt_beside_a_pending_act_still_keeps_its_kinds_from_an_exclusion(self):
        variants = {'the undated note': (dict(), (None, '2026-11-09', '2026-11-10')),
                    "the doubt worded 'On 11/09/2026' too (two pending checks)": (
                        dict(doubt_time=a('current_encounter', 'On 11/09/2026', ['P6'])),
                        (None, '2026-11-09', '2026-11-10')),
                    "the document's own 11/09/2026": (dict(dated=True), (None,))}
        for name, (options, days) in variants.items():
            inv, text = two_families(**options)
            self.assertIn(('doubt', 'E6', 'E5', 'status', 'in_doubt'), stored_relations(inv))
            for day in days:
                result = run(inv, text, CODES, user_values=member(day))
                with self.subTest(name, member=day):
                    p = proposal(result, '45385')
                    self.assertEqual((p.bucket, p.status, asked(p)),
                                     ('selected', 'needs_clarification', ['performed_status']))
                    own = proposal(result, '43251')
                    self.assertEqual((own.status, asked(own)), ('needs_clarification', ['performed_status', 'extent']))


# --- (2): the examination Counter ---------------------------------------------------------------------------------------

class D128Counter(SimpleTestCase):
    """relations.Context's examination Counter does not read D99, and D128 records why rather than applying it: D128
    keeps D99's reading only where it can only hold, and counting a pending examination can release - it makes every
    all_of_kind pair of the family session_unresolved before any date (D87: the pairing's unresolved sessions count
    VERIFIED current examinations). A second examination Gemini calls current, dated in its own words on the undated
    note, is a possible examination at normalize, never a second examination of the pairing's session."""

    def test_d128_a_pending_examination_is_no_second_examination_of_the_pairings_session(self):
        """'On 11/09/2026, the colonoscope was reinserted to the cecum.' (E4, current_encounter worded 'On 11/09/2026')
        beside the snare and the impression's denial. The pairing's session is resolved, the denial a CONTRADICTION, and
        45385 asks conflict:snare (with the extent the possible examination leaves open) whatever the member's date - as
        the installed release asks conflict:snare with no date, 2026-11-09 and 2026-11-10, and as the document's own
        11/10/2026 asks. Counted as current (D99 carried into the Counter), the pair would be session_unresolved with
        every date, and the denial would be asked as its scope even when the second colonoscope is another day's."""
        value, lines = denial_answer(POLYP, '')
        with_line(value, lines, 'P4', SECOND, exam('E4', 'P4', status_words='was reinserted',
                                                   time=a('current_encounter', 'On 11/09/2026', ['P4'])))
        inv, text = normalized(value, lines)
        reading = events.Reading.of(inv)
        second = reading.events['E4']
        self.assertEqual((second['time']['state'], second['time']['reasons'], second['current']),
                         ('unverified', ['date_unchecked'], 'unresolved'))
        self.assertEqual(reading.context.unresolved_sessions, frozenset())
        self.assertEqual(stored_relations(inv), CONTRADICTED)
        for day in (None, '2026-11-09', '2026-11-10'):
            with self.subTest(member=day):
                held(self, run(inv, text, [('45385', POLYP)], user_values=member(day)), '45385',
                     ['conflict:snare', 'extent'], conflict=True)

    def test_d128_control_the_documents_own_date_counts_a_verified_second_examination(self):
        """The reference: with the document's own 11/09/2026 the second colonoscope is verified current at normalize, so
        D87's rule makes the pairing's session unresolved (asked as the statement's scope); with 11/10/2026 it is
        another day's and the denial is the contradiction. The installed release asks conflict:snare on both."""
        for line, stated, relation, facts, conflict in (
                (DATE_LINE, STATED, [('unresolved', 'E3', 'E2', 'procedure', 'session_unresolved')],
                 ['statement_scope', 'extent'], False),
                (DATE_LINE_10, STATED_10, CONTRADICTED, ['conflict:snare', 'extent'], True)):
            value, lines = denial_answer(POLYP, '', date_lines={'P0': line}, date_of_service=stated)
            with_line(value, lines, 'P4', SECOND, exam('E4', 'P4', status_words='was reinserted',
                                                       time=a('current_encounter', 'On 11/09/2026', ['P4'])))
            inv, text = normalized(value, lines)
            with self.subTest(line):
                self.assertEqual(stored_relations(inv), relation)
                held(self, run(inv, text, [('45385', POLYP)]), '45385', facts, conflict=conflict)

    def test_d128_a_pending_examination_never_takes_a_doubts_exclusion_guard(self):
        """The second reason, a hold counting would release: an EGD with 'EGD: On 11/09/2026, the gastroscope was
        reinserted to the duodenum.' (E7, current_encounter worded 'On 11/09/2026'), a snare of a gastric polyp and the
        all_of_kind doubt 'EGD: It is unclear whether any polyp was removed.' (E6); a colonoscopy whose 'Colonoscopy: No
        polyp was removed.' 45385 cites. Not counted, the doubt's pair is a DOUBT and events._doubted keeps 45385 held
        with every date, as the document's own 11/10/2026 does. Counted (mutant M5), the pair is session_unresolved,
        the guard goes and 45385 is EXCLUDED with every date, 2026-11-10 included. (With the document's own 11/09/2026
        the second gastroscope is verified, and D87's rule already does so: recorded, outside D128. The installed
        release excludes 45385 on all of these texts.)"""
        def document(**options):
            lines = {**({'P0': options['line']} if options else {}),
                     'P0b': 'EGD: the gastroscope was advanced to the duodenum.',
                     'P7': 'EGD: On 11/09/2026, the gastroscope was reinserted to the duodenum.',
                     'P5': 'EGD: A 5 mm polyp in the gastric body was removed with a cold snare.',
                     'P6': 'EGD: It is unclear whether any polyp was removed.',
                     'P1': 'Colonoscopy: The colonoscope was advanced to the cecum.',
                     'P2': 'Colonoscopy: No polyp was removed.'}
            egd, colon = (lambda pid: a('egd', 'EGD', [pid])), (lambda pid: a('colonoscopy', 'Colonoscopy', [pid]))
            found = [exam('E0', 'P0b', words='gastroscope', procedure=egd('P0b')),
                     exam('E7', 'P7', words='gastroscope', status_words='was reinserted', procedure=egd('P7'),
                          time=a('current_encounter', 'On 11/09/2026', ['P7'])),
                     snare('E5', 'P5', procedure=egd('P5'),
                           target=tg('L2', 'gastric_body', '5 mm polyp in the gastric body', ['P5'])),
                     act('E6', 'P6', 'removal', 'removed', status='uncertain', procedure=egd('P6'),
                         status_words='It is unclear whether any polyp was removed',
                         scope=sc('all_of_kind', 'any polyp', ['P6'])),
                     exam('E1', 'P1', procedure=colon('P1')),
                     act('E2', 'P2', 'removal', 'removed', status='not_performed', status_words='No polyp was removed',
                         procedure=colon('P2'), scope=sc('all_of_kind', 'No polyp', ['P2']))]
            value = {'passages': [{'id': pid, 'text': text} for pid, text in lines.items()],
                     'encounter': {'date_of_service': options.get('stated', NOT_STATED),
                                   'documenting_endoscopist': {'words': '', 'passages': []}, 'team': [], 'anatomy': [],
                                   'reach': [reached('E1', passage='P1'),
                                             reached('E0', 'second_portion_duodenum', 'duodenum', 'P0b')],
                                   'visit_facts': []},
                     'lesions': [les('L2', '5 mm polyp', 'P5', landmark='gastric_body', site_words='gastric body',
                                     size_words='5 mm')],
                     'events': found, 'open_questions': []}
            return normalized(value, lines)

        for name, options, days in (('the undated note', {}, (None, '2026-11-09', '2026-11-10')),
                                    ("the document's own 11/10/2026", dict(line=DATE_LINE_10, stated=STATED_10),
                                     (None,))):
            inv, text = document(**options)
            self.assertEqual(events.Reading.of(inv).context.unresolved_sessions, frozenset())
            self.assertIn(('doubt', 'E6', 'E5', 'status', 'in_doubt'), stored_relations(inv))
            for day in days:
                with self.subTest(name, member=day):
                    p = proposal(run(inv, text, CODES, user_values=member(day)), '45385')
                    self.assertEqual((p.bucket, p.status, asked(p)),
                                     ('selected', 'needs_clarification', ['performed_status']))


# --- the production chain ----------------------------------------------------------------------------------------------

class D128Chain(EventsCase):
    """D128 through the production chain (extract, interpret by replay, analyze, predict with the Corti fake, assess),
    the legacy reader's entry points failing if called: both member-date outcomes on the one frozen inventory - the
    member's 2026-11-10 at upload asks the snare's time, and 2026-11-09 saved afterwards (jobs.change_context) asks the
    denial as its scope."""
    corti_groups = ((('45385', DATED_POLYP),),)

    def upload_with(self, user_values):
        value, lines = denial_answer()
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
        return assessment, models.EventInventory.objects.get(pk=assessment.event_inventory_id)

    def assert_asked(self, assessment, stored, facts):
        self.assertEqual(assessment.context.facts['service_date']['state'], 'supplies')
        self.assertEqual(stored_relations(stored), UNRESOLVED_TIME)
        p = self.proposal(assessment, '45385')
        self.assertEqual((p.status, [spec.fact for spec in p.clarifications.all()]), ('needs_clarification', facts))
        found = next(item for item in assessment.encounter_checks if item['id'] == 'services.conflicts')
        self.assertEqual(found['status'], 'pass')
        self.assertNotIn('1 conflict in the record', assessment.completeness['reasons'])

    def test_d128_both_member_dates_through_the_chain(self):
        encounter = self.upload_with({'service_date': '2026-11-10'})
        first, stored = self.drained(encounter)
        self.assert_asked(first, stored, ['event_time'])
        with self.legacy_reader_fails():
            jobs.change_context(encounter, self.user, {'service_date': '2026-11-09'})
        saved, stored = self.drained(encounter)
        self.assertNotEqual(saved.pk, first.pk)
        self.assert_asked(saved, stored, ['statement_scope'])
