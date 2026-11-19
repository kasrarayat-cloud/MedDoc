"""The gemini-context@1 facts, the document date and the gemini-routing@1 stand-in (Gemini migration slice S08; design/
FINAL.md 4.3, 6.4, 6.5 and 6.10; design/contract.md 8.1-8.3; DECISIONS D2, D3, D8; design/ADJUDICATION.md C-3),
SYNTHETIC: the date of service through every member_date_state row that changes the record (the legacy note texts, so
the one shared is_member_conflict holds the encounter), the member-only facts (D3), the refusals, the shape answers.py
reads, checks.service_date_state over the derived context, the same date of service (C-3) and the routing stand-in
read back as a types.RoutingResult. The copied legacy constants are pinned equal through a test-only import."""
from __future__ import annotations

from datetime import date

from django.test import SimpleTestCase

from studio import context_facts
from studio.gi import context as gi_context
from studio.interpretation import ROUTING_VERSION, dates, facts
from studio.types import Fact, RoutingResult, from_jsonable
from studio.validation import checks
from tests.test_interpretation_events import COLONOSCOPE, POLYP, colonoscopy, exam, inventory, removed
from tests.test_interpretation_identity import a, act

SEVERAL = {'value': '', 'state': 'several', 'words': '', 'passages': ['P0'],
           'other_dates': [{'value': '2026-11-09', 'role': 'this_encounter', 'words': '11/09/2026', 'passages': ['P0']},
                           {'value': '2026-11-02', 'role': 'this_encounter', 'words': '11/02/2026', 'passages': ['P8']}]}


def dated(**encounter):
    return colonoscopy(lines={'P8': 'Previous visit: 11/02/2026.', 'P7': 'Date of birth: 01/01/1998.'}, **encounter)


class ServiceDate(SimpleTestCase):
    def derived(self, member='', **encounter):
        inv, _ = dated(**encounter)
        return facts.derive(inv, {'service_date': member} if member else {})

    def test_a_verified_stated_date(self):
        found = self.derived()
        record = found.facts['service_date']
        self.assertEqual((record['value'], record['origin'], record['state']), ('2026-11-09', 'document',
                                                                                 dates.NO_MEMBER_VALUE))
        self.assertEqual(record['evidence'], [{'start': 17, 'end': 27, 'text': '11/09/2026'}])
        self.assertEqual(found.effective, '2026-11-09')
        self.assertEqual(found.member_date.corti_date, '2026-11-09')

    def test_a_member_value_that_agrees_keeps_the_documents_origin(self):
        record = self.derived('2026-11-09').facts['service_date']
        self.assertEqual((record['origin'], record['state']), ('document', dates.AGREES))

    def test_a_member_value_that_differs_is_held_with_the_legacy_note(self):
        found = self.derived('2026-10-01')
        record = found.facts['service_date']
        self.assertEqual((record['value'], record['origin'], record['state']), (None, 'conflict',
                                                                                 dates.CONFLICT_DIFFERS))
        self.assertEqual(record['note'], context_facts.USER_CONFLICT_NOTE.format(user='2026-10-01',
                                                                                 document='2026-11-09'))
        self.assertTrue(context_facts.is_member_conflict(record))
        self.assertIsNone(found.effective)
        state = checks.service_date_state(facts.context_of(found.facts), None)
        self.assertEqual((state.value, state.origin), (None, 'conflict'))

    def test_a_member_birth_date_is_held_as_such(self):
        inv, _ = dated(date_of_service={'value': '2026-11-09', 'state': 'stated', 'words': '11/09/2026',
                                        'passages': ['P0'], 'other_dates': [
                                            {'value': '1998-01-01', 'role': 'birth', 'words': '01/01/1998',
                                             'passages': ['P7']}]})
        record = facts.derive(inv, {'service_date': '1998-01-01'}).facts['service_date']
        self.assertEqual(record['state'], dates.CONFLICT_BIRTH)
        self.assertTrue(record['note'].startswith(context_facts.USER_CONFLICT_NOTE.split('{', 1)[0]))

    def test_several_dates_are_the_documents_conflict_and_a_member_settles_them(self):
        found = self.derived(date_of_service=SEVERAL)
        record = found.facts['service_date']
        self.assertEqual((record['origin'], record['note']),
                         ('conflict', context_facts.DOCUMENT_CONFLICT_NOTE + '2026-11-02, 2026-11-09.'))
        self.assertEqual(context_facts.documented_values(facts.context_of(found.facts)['service_date']),
                         ('2026-11-02', '2026-11-09'))
        self.assertEqual(found.document_date['values'], ['2026-11-02', '2026-11-09'])
        settled = self.derived('2026-11-02', date_of_service=SEVERAL).facts['service_date']
        self.assertEqual((settled['value'], settled['origin'], settled['state']), ('2026-11-02', 'user',
                                                                                   dates.SETTLES))

    def test_no_stated_date(self):
        missing = {'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []}
        record = self.derived(date_of_service=missing).facts['service_date']
        self.assertEqual((record['value'], record['origin'], record['note']),
                         (None, 'missing', facts.MISSING_NOTES['service_date']))
        supplied = self.derived('2026-11-09', date_of_service=missing).facts['service_date']
        self.assertEqual((supplied['value'], supplied['origin'], supplied['state']), ('2026-11-09', 'user',
                                                                                      dates.SUPPLIES))


class MemberFacts(SimpleTestCase):
    def test_setting_billing_and_status_come_only_from_member_values(self):
        inv, _ = colonoscopy()
        found = facts.derive(inv, {'setting': 'office', 'patient_status': ' established '}).facts
        self.assertEqual(found['setting'], {'name': 'setting', 'value': 'office', 'origin': 'user', 'evidence': [],
                                            'note': dates.USER_NOTE})
        self.assertEqual(found['patient_status']['value'], 'established')
        self.assertEqual(found['billing_context'], {'name': 'billing_context', 'value': None, 'origin': 'missing',
                                                    'evidence': [], 'note': facts.MISSING_NOTES['billing_context']})
        context = facts.context_of(found)
        self.assertIsInstance(context['setting'], Fact)
        self.assertEqual(context['setting'].origin, 'user')

    def test_values_that_are_not_valid_are_refused(self):
        inv, _ = colonoscopy()
        for values in ({'colour': 'red'}, {'setting': 'garage'}, {'setting': 1}, {'service_date': '11/09/2026'},
                       {'patient_status': 'returning'}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                facts.derive(inv, values)

    def test_the_copied_constants_are_the_legacy_ones(self):
        self.assertEqual((facts.SETTINGS, facts.BILLING_CONTEXTS, facts.PATIENT_STATUSES),
                         (gi_context.SETTINGS, gi_context.BILLING_CONTEXTS, gi_context.PATIENT_STATUSES))
        self.assertEqual(facts.MISSING_NOTES, gi_context.MISSING_NOTES)


class DocumentDate(SimpleTestCase):
    def test_the_shape_answers_reads(self):
        inv, text = colonoscopy()
        found = facts.document_date(inv)
        self.assertEqual(set(found), {'origin', 'value', 'single', 'values', 'asked', 'quote', 'evidence'})
        self.assertEqual((found['origin'], found['value'], found['single'], found['values']),
                         ('document', '2026-11-09', True, ['2026-11-09']))
        self.assertEqual(text[found['quote']['start']:found['quote']['end']], found['quote']['text'])
        missing, _ = colonoscopy(date_of_service={'value': '', 'state': 'not_stated', 'words': '', 'passages': [],
                                                  'other_dates': []})
        self.assertEqual(facts.document_date(missing)['origin'], 'missing')


class SameDay(SimpleTestCase):
    """C-3: the date of service, never the encounter, decides a procedure day."""
    LINE = 'An upper endoscopy was performed earlier today.'

    def day(self, time, line=LINE, effective='2026-11-09', **encounter):
        inv, _ = inventory({'P1': line}, events=[act('E1', 'P1', 'examination', 'upper endoscopy',
                                                    status_words='was performed', procedure=a('egd'), time=time)],
                           **encounter)
        return facts.day_of(inv.events['events'][0], effective)

    def test_on_the_date(self):
        self.assertEqual(self.day(a('current_encounter')), facts.ON)
        self.assertEqual(self.day(a('earlier_encounter', 'earlier today', ['P1'])), facts.ON)
        self.assertEqual(self.day(a('earlier_encounter', 'on 11/09/2026', ['P1']),
                                  'An upper endoscopy was performed on 11/09/2026.'), facts.ON)

    def test_off_the_date(self):
        self.assertEqual(self.day(a('earlier_encounter', 'in 2024', ['P1']),
                                  'An upper endoscopy was performed in 2024.'), facts.OFF)
        self.assertEqual(self.day(a('earlier_encounter', 'previously', ['P1']),
                                  'An upper endoscopy was performed previously.'), facts.OFF)

    def test_undatable(self):
        self.assertEqual(self.day(a('unknown')), facts.UNDATABLE)
        # with no verified date of service a date literal compares with nothing: the time stays unverified
        missing = {'value': '', 'state': 'not_stated', 'words': '', 'passages': [], 'other_dates': []}
        self.assertEqual(self.day(a('earlier_encounter', 'in 2024', ['P1']), 'An upper endoscopy was performed in 2024.',
                                  effective=None, date_of_service=missing), facts.UNDATABLE)


class RoutingStandIn(SimpleTestCase):
    def test_the_stand_in_is_derived_and_readable_as_a_routing_result(self):
        historical = act('E3', 'P3', 'examination', 'EGD', status_words='EGD',
                         procedure=a('egd', 'EGD', ['P3']), time=a('earlier_encounter', '2024', ['P3']))
        inv, _ = colonoscopy(historical, lines={'P3': 'EGD 2024 was normal.'})
        found = facts.routing_stand_in(inv, date(2026, 11, 9), inventory_id='inv-1', inventory_sha256='a' * 64)
        self.assertEqual(found['version'], ROUTING_VERSION)
        self.assertEqual(found['findings'], [
            {'family': 'gi.egd', 'status': 'historical', 'mentions': [], 'facts': [], 'missing': []},
            {'family': 'gi.colonoscopy', 'status': 'performed', 'mentions': [], 'facts': [], 'missing': []}])
        self.assertEqual((found['inventory'], found['inventory_sha256'], found['document_kind']),
                         ('inv-1', 'a' * 64, ''))
        routed = from_jsonable(RoutingResult, found)
        self.assertEqual(routed.finding('gi.colonoscopy').status, 'performed')
        self.assertEqual(facts.routing_stand_in(inv, '2026-11-09', inventory_id='inv-1', inventory_sha256='a' * 64),
                         found)
