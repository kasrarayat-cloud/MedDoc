"""The date of service against a member's entered date (Gemini migration slice S03; design/contract.md 8.1-8.2; design/
FINAL.md 4.3; DECISIONS D1, D2, D8), TEXT-ONLY: every member_date_state row and its precedence; the held rows' notes,
equal to the legacy constants and to what the legacy merge_user_values writes for the same two sides (a TEST-ONLY import
of studio.gi.context: the module itself never imports it); the copied legacy notes pinned equal to gi.context's; Corti's
date (D2); "use the document date"; and the record read off a normalized inventory. Nothing is sent."""
from __future__ import annotations

import json
import sys

from django.test import SimpleTestCase

from studio import context_facts
from studio.interpretation import dates, normalize
from tests.test_interpretation_identity import accepted, answer, normalized

WORDS = {'start': 17, 'end': 27, 'text': '11/09/2026', 'match': 'exact'}


def span(text: str, start: int = 100) -> dict:
    return {'start': start, 'end': start + len(text), 'text': text, 'match': 'exact'}


def other(value: str, text: str, verified: bool = True, located: bool = True) -> dict:
    """An other date as normalize stores it: unverified with its words when they located and its literal failed."""
    return {'value': value, 'verified': verified, 'words': span(text) if located else None, 'passages': ['P5'],
            'reasons': [] if verified else ['date_mismatch' if located else 'words_unlocated']}


def dos(state: str = 'stated', value=None, *, verified: bool = False, words=None, passages=(), candidates=(),
        readings=(), **others) -> dict:
    """A date_of_service record in the shape normalize stores (contract 8.1)."""
    roles = {role: list(others.get(role, ())) for role in ('birth', 'other_occurrence', 'other_document',
                                                             'report_time', 'unclear')}
    return {'state': state, 'value': value, 'verified': verified, 'words': words, 'passages': list(passages),
            'reasons': [], 'candidates': list(candidates), 'readings': list(readings), 'others': roles}


STATED = dos('stated', '2026-11-09', verified=True, words=WORDS, passages=['P1'])
PASSAGES = [{'id': 'P1', 'state': 'located', 'spans': [{'start': 0, 'end': 27, 'text': 'Date of service: 11/09/2026'}],
             'reason': '', 'chars': 27, 'extended': ''},
            {'id': 'P2', 'state': 'unlocated', 'spans': [], 'reason': 'not found', 'chars': 30, 'extended': ''}]


def row(record: dict, member, passages=PASSAGES) -> tuple:
    found = dates.member_date_state(record, member, passages)
    return found.state, found.hold, found.effective, found.origin


class Rows(SimpleTestCase):
    def test_no_member_value(self):
        self.assertEqual(row(STATED, ''), ('no_member_value', False, '2026-11-09', 'document'))
        self.assertEqual(row(STATED, None), ('no_member_value', False, '2026-11-09', 'document'))
        self.assertEqual(row(STATED, '   '), ('no_member_value', False, '2026-11-09', 'document'))
        several = dos('several', candidates=['2026-11-08', '2026-11-09'])
        self.assertEqual(row(several, ''), ('no_member_value', False, None, 'conflict'))
        self.assertEqual(dates.member_date_state(several, '').note,
                         'Conflicting documented values: 2026-11-08, 2026-11-09.')
        self.assertEqual(row(dos('not_stated'), ''), ('no_member_value', False, None, 'missing'))
        self.assertEqual(dates.member_date_state(dos('not_stated'), '').note, dates.MISSING_NOTE)
        self.assertEqual(row(dos('stated', words=WORDS), ''), ('no_member_value', False, None, 'missing'))

    def test_agrees_and_the_origin_stays_the_documents(self):
        found = dates.member_date_state(STATED, '2026-11-09', PASSAGES)
        self.assertEqual((found.state, found.hold, found.effective, found.origin, found.note),
                         ('agrees', False, '2026-11-09', 'document', ''))

    def test_conflict_birth(self):
        record = dos('stated', '2026-11-09', verified=True, words=WORDS, birth=[other('1960-01-02', 'DOB: 01/02/1960')])
        self.assertEqual(row(record, '1960-01-02'), ('conflict_birth', True, None, 'conflict'))
        for located in (True, False):  # an unverified other date takes part in no comparison (contract 8.1)
            unverified = dos('not_stated', birth=[other('1960-01-02', 'DOB: 01/02/1961', verified=False,
                                                        located=located)])
            with self.subTest(located=located):
                self.assertEqual(row(unverified, '1960-01-02'), ('supplies', False, '1960-01-02', 'user'))

    def test_conflict_elsewhere(self):
        for role in ('other_occurrence', 'other_document'):
            record = dos('not_stated', **{role: [other('2026-11-04', 'Next procedure: 11/04/2026')]})
            with self.subTest(role):
                self.assertEqual(row(record, '2026-11-04'), ('conflict_elsewhere', True, None, 'conflict'))
        for role in ('report_time', 'unclear'):  # not another occurrence's or another document's date
            record = dos('not_stated', **{role: [other('2026-11-04', 'Signed: 11/04/2026')]})
            with self.subTest(role):
                self.assertEqual(row(record, '2026-11-04'), ('supplies', False, '2026-11-04', 'user'))

    def test_conflict_differs(self):
        self.assertEqual(row(STATED, '2026-11-08'), ('conflict_differs', True, None, 'conflict'))

    def test_several_settled_or_listed(self):
        several = dos('several', candidates=['2026-11-08', '2026-11-09'], passages=['P1'])
        self.assertEqual(row(several, '2026-11-08'), ('settles', False, '2026-11-08', 'user'))
        self.assertEqual(row(several, '2026-11-07'), ('conflict_listed', True, None, 'conflict'))

    def test_stated_unverified_or_opened(self):
        record = dos('stated', words=WORDS, passages=['P1'], readings=['2026-11-09'])
        self.assertEqual(row(record, '2026-11-09'), ('settles', False, '2026-11-09', 'user'))
        self.assertEqual(row(record, '2026-11-10'), ('conflict_unverifiable', True, None, 'conflict'))

    def test_an_unverified_date_holds_whether_or_not_anything_is_quotable(self):
        # contract 8.2: a stated, unverified (or opened) date holds every member value outside its readings. Whether a
        # span of it can be quoted decides only the evidence and the note, never the hold (review finding 1: a date
        # with nothing quotable had let the member's date supply it and go to Corti - the 2026-10-27 incident class).
        quotable = dos('stated', passages=['P1'])  # words did not bind, the passage located
        self.assertEqual(row(quotable, '2026-11-10'), ('conflict_unverifiable', True, None, 'conflict'))
        self.assertEqual(dates.member_date_state(quotable, '2026-11-10', PASSAGES).evidence,
                         ({'start': 0, 'end': 27, 'text': 'Date of service: 11/09/2026'},))
        for name, record in (('its only passage unlocated', dos('stated', passages=['P2'])),
                             ('no passage at all', dos('stated')),
                             ('several, no candidate, nothing located', dos('several', passages=['P2']))):
            found = dates.member_date_state(record, '1998-01-01', PASSAGES)
            with self.subTest(name):
                self.assertEqual((found.state, found.hold, found.effective, found.origin, found.corti_date),
                                 ('conflict_unverifiable', True, None, 'conflict', None))
                self.assertEqual(found.evidence, ())
                self.assertEqual(found.note, dates.USER_CONFLICT_NOTE.format(
                    user='1998-01-01', document=dates.UNCHECKED_DOCUMENT_DATE))
                self.assertFalse(found.offer_document_date)

    def test_the_published_two_argument_call_holds_as_the_three_argument_call_does(self):
        # FINAL and the contract publish member_date_state(date_of_service, member_value): leaving the passages out may
        # change what is quoted, never whether the encounter is held or which date is taken
        records = [STATED, dos('stated', passages=['P1']), dos('stated', passages=['P1'], readings=['2026-11-09']),
                   dos('stated', words=WORDS, passages=['P1']), dos('stated', passages=['P2']), dos('stated'),
                   dos('several', candidates=['2026-11-08', '2026-11-09'], passages=['P1']),
                   dos('several', passages=['P1'], readings=['2026-11-09']), dos('several'), dos('not_stated'),
                   dos('not_stated', birth=[other('1960-01-02', 'DOB: 01/02/1960')])]
        for index, record in enumerate(records):
            for member in ('', '2026-11-09', '2026-11-08', '1998-01-01', '1960-01-02'):
                three = dates.member_date_state(record, member, PASSAGES)
                two = dates.member_date_state(record, member)
                with self.subTest(index=index, member=member):
                    self.assertEqual((two.state, two.hold, two.effective, two.corti_date, two.origin),
                                     (three.state, three.hold, three.effective, three.corti_date, three.origin))
        two = dates.member_date_state(dos('stated', passages=['P1']), '1998-01-01')
        self.assertEqual((two.state, two.hold, two.corti_date), ('conflict_unverifiable', True, None))

    def test_refinement_several_with_no_verified_candidate_reads_its_readings(self):
        record = dos('several', passages=['P1'], readings=['2026-11-09'])
        self.assertEqual(row(record, '2026-11-09'), ('settles', False, '2026-11-09', 'user'))
        self.assertEqual(row(record, '2026-11-01'), ('conflict_unverifiable', True, None, 'conflict'))

    def test_not_stated_supplies(self):
        self.assertEqual(row(dos('not_stated'), '2026-11-09'), ('supplies', False, '2026-11-09', 'user'))

    def test_precedence(self):
        everything = dos('stated', '2026-11-09', verified=True, words=WORDS, passages=['P1'],
                         birth=[other('2026-11-09', 'DOB: 11/09/2026'), other('1960-01-02', 'DOB: 01/02/1960')],
                         other_occurrence=[other('1960-01-02', 'Last visit: 01/02/1960'),
                                           other('2026-11-04', 'Next procedure: 11/04/2026')])
        self.assertEqual(row(everything, '2026-11-09')[0], 'agrees')  # the stated value first, even as a birth date
        self.assertEqual(row(everything, '1960-01-02')[0], 'conflict_birth')  # birth before elsewhere
        self.assertEqual(row(everything, '2026-11-04')[0], 'conflict_elsewhere')  # elsewhere before differs
        self.assertEqual(row(everything, '2026-11-05')[0], 'conflict_differs')
        self.assertEqual(dates.STATES, ('no_member_value', 'agrees', 'conflict_birth', 'conflict_elsewhere',
                                        'conflict_differs', 'settles', 'conflict_listed', 'conflict_unverifiable',
                                        'supplies'))

    def test_a_member_value_is_a_date(self):
        with self.assertRaises(ValueError):
            dates.member_date_state(STATED, '11/09/2026')
        with self.assertRaises(ValueError):
            dates.member_date_state(STATED, '2026-02-30')
        with self.assertRaises(TypeError):
            dates.member_date_state(STATED, 20261109)
        self.assertEqual(row(STATED, ' 2026-11-09 '), ('agrees', False, '2026-11-09', 'document'))


class CortiAndOffer(SimpleTestCase):
    """D2: the member's date when supplies, settles or agrees; else the verified stated value; else none; nothing when
    held. "Use the document date" only on a held row whose document side is stated and verified."""

    def test_cortis_date(self):
        self.assertEqual(dates.corti_date(STATED, ''), '2026-11-09')
        self.assertEqual(dates.corti_date(STATED, '2026-11-09'), '2026-11-09')
        self.assertEqual(dates.corti_date(dos('not_stated'), '2026-11-01'), '2026-11-01')
        self.assertEqual(dates.corti_date(dos('several', candidates=['2026-11-08', '2026-11-09']), '2026-11-08'),
                         '2026-11-08')
        self.assertIsNone(dates.corti_date(STATED, '2026-11-08'))  # held: nothing is sent
        self.assertIsNone(dates.corti_date(dos('not_stated'), ''))
        self.assertEqual(dates.effective_date(STATED, '2026-11-08'), None)

    def test_the_offer(self):
        self.assertTrue(dates.member_date_state(STATED, '2026-11-08').offer_document_date)
        self.assertFalse(dates.member_date_state(STATED, '2026-11-09').offer_document_date)
        self.assertFalse(dates.member_date_state(dos('several', candidates=['2026-11-08', '2026-11-09']),
                                                 '2026-11-07').offer_document_date)

    def test_the_record_is_json(self):
        found = dates.member_date_state(STATED, '2026-11-08', PASSAGES)
        record = json.loads(json.dumps(found.as_record()))
        self.assertEqual((record['state'], record['hold'], record['corti_date'], record['document_value']),
                         ('conflict_differs', True, None, '2026-11-09'))


class LegacyNotes(SimpleTestCase):
    """The held rows write the legacy note text, so the one shared is_member_conflict holds the encounter in both images
    (FINAL 4.3), pinned against the legacy constants and the legacy writer (test-only import of studio.gi.context)."""

    def test_the_constants_are_the_legacy_objects(self):
        from studio.gi import context as legacy  # test-only
        for name in ('USER_CONFLICT_NOTE', 'USER_ELSEWHERE_NOTE', 'USER_BIRTH_NOTE', 'DOCUMENT_CONFLICT_NOTE'):
            with self.subTest(name):
                self.assertIs(getattr(dates, name), getattr(context_facts, name))
                self.assertIs(getattr(dates, name), getattr(legacy, name))
        self.assertEqual(dates.USER_NOTE, legacy.USER_NOTE)
        self.assertEqual(dates.MISSING_NOTE, legacy.MISSING_NOTES['service_date'])

    def legacy(self, documented, member: str):
        from studio.gi import context as legacy  # test-only
        return legacy.merge_user_values({'service_date': documented}, {'service_date': member})['service_date']

    def test_equal_to_what_merge_user_values_writes(self):
        from studio.gi import context as legacy  # test-only
        from studio.types import Fact, Span
        line = Span(0, 27, 'Date of service: 11/09/2026')
        own = Span(17, 27, '11/09/2026')
        elsewhere = legacy._ElsewhereSpan(100, 126, 'Next procedure: 11/04/2026')
        birth = legacy._BirthSpan(100, 122, 'Visit date: 01/02/1960')
        unreadable = Span(17, 27, '11/09/2026')
        cases = [
            ('conflict_differs', Fact('service_date', '2026-11-09', 'document', (own,)), STATED, '2026-11-08'),
            ('conflict_listed', Fact('service_date', None, 'conflict', (line,),
                                     'Conflicting documented values: 2026-11-08, 2026-11-09.'),
             dos('several', candidates=['2026-11-08', '2026-11-09']), '2026-11-07'),
            ('conflict_unverifiable', Fact('service_date', None, 'missing', (unreadable,), ''),
             dos('stated', words=WORDS, passages=['P1']), '2026-11-10'),
            ('conflict_elsewhere', Fact('service_date', None, 'missing', (elsewhere,), ''),
             dos('not_stated', other_occurrence=[other('2026-11-04', 'Next procedure: 11/04/2026')]), '2026-11-04'),
            ('conflict_birth', Fact('service_date', None, 'missing', (birth,), ''),
             dos('not_stated', birth=[other('1960-01-02', 'Visit date: 01/02/1960')]), '1960-01-02'),
            ('settles', Fact('service_date', None, 'conflict', (line,),
                             'Conflicting documented values: 2026-11-08, 2026-11-09.'),
             dos('several', candidates=['2026-11-08', '2026-11-09']), '2026-11-08'),
            ('supplies', Fact('service_date', None, 'missing', (), dates.MISSING_NOTE), dos('not_stated'),
             '2026-11-01'),
        ]
        for state, documented, record, member in cases:
            mine = dates.member_date_state(record, member, PASSAGES)
            theirs = self.legacy(documented, member)
            with self.subTest(state):
                self.assertEqual(mine.state, state)
                self.assertEqual(mine.note, theirs.note)
                self.assertEqual(mine.origin, theirs.origin)
                self.assertEqual(mine.effective, theirs.value)
                self.assertEqual(context_facts.is_member_conflict({'origin': mine.origin, 'note': mine.note}),
                                 mine.hold)
                self.assertEqual(legacy.is_member_conflict(theirs), mine.hold)

    def test_agrees_departs_from_the_legacy_provenance_on_purpose(self):
        from studio.types import Fact, Span
        theirs = self.legacy(Fact('service_date', '2026-11-09', 'document', (Span(17, 27, '11/09/2026'),)),
                             '2026-11-09')
        mine = dates.member_date_state(STATED, '2026-11-09', PASSAGES)
        self.assertEqual((theirs.origin, mine.origin), ('user', 'document'))  # the trace's provenance defect, fixed
        self.assertEqual(theirs.value, mine.effective)

    def test_the_note_of_a_date_with_nothing_quotable_holds_in_both_images(self):
        # merge_user_values has no such row (a fact with no evidence limits no answer there), so the note is written
        # with USER_CONFLICT_NOTE and a fixed phrase: the one shared is_member_conflict - and the rollback image's
        # copy - holds the encounter by its prefix
        from studio.gi import context as legacy  # test-only
        from studio.types import Fact
        found = dates.member_date_state(dos('stated', passages=['P2']), '1998-01-01', PASSAGES)
        self.assertEqual(found.note, 'Encounter metadata entered by a workspace member gives 1998-01-01; the document '
                                     'gives a date of service this service could not check. Both are kept and neither '
                                     'is used until they agree: correct the metadata, clear it, or add an addendum to '
                                     'the document.')
        self.assertTrue(context_facts.is_member_conflict({'origin': found.origin, 'note': found.note}))
        self.assertTrue(legacy.is_member_conflict(Fact('service_date', None, found.origin, (), found.note)))
        self.assertEqual(context_facts.documented_values(Fact('service_date', None, found.origin, (), found.note)), ())

    def test_the_document_conflict_note_reads_back_its_candidates(self):
        from studio.types import Fact
        note = dates.member_date_state(dos('several', candidates=['2026-11-08', '2026-11-09']), '').note
        self.assertEqual(context_facts.documented_values(Fact('service_date', None, 'conflict', (), note)),
                         ('2026-11-08', '2026-11-09'))

    def test_quoting(self):
        long = 'Date of service:   ' + 'x' * 80
        self.assertEqual(dates.quoted([{'text': long}] * 4), ', '.join(['“Date of service: ' + 'x' * 43 +
                                                                       '”'] * 3))


class FromAnInventory(SimpleTestCase):
    def test_the_date_of_an_inventory(self):
        inventory = normalized({'P1': 'Cold forceps biopsies were taken from the cecum.'})
        record = inventory.encounter_facts['date_of_service']
        passages = inventory.events['passages']
        self.assertEqual(row(record, '', passages), ('no_member_value', False, '2026-11-09', 'document'))
        found = dates.member_date_state(record, '2026-11-08', passages)
        self.assertEqual((found.state, found.evidence), ('conflict_differs', (
            {'start': 17, 'end': 27, 'text': '11/09/2026'},)))
        self.assertTrue(found.note.startswith('Encounter metadata entered by a workspace member gives 2026-11-08; '
                                              'the document gives 2026-11-09.'))

    def test_a_stated_date_whose_words_bind_nowhere_holds_a_members_other_date(self):
        # review finding 1's probes: Gemini states the date, but nothing of it binds - its quote differs from the
        # document in case (the Locator folds none), its words cite no passage, or its passage id is undefined. The
        # member's 1998-01-01 is held, never taken nor sent to Corti; the date its readings hold would still settle it
        def inventory(change) -> tuple:
            value, text = answer({'P1': 'Cold forceps biopsies were taken from the cecum.'})
            change(value)
            found = normalize.normalize(accepted(value), text)
            return found.encounter_facts['date_of_service'], found.events['passages']

        def case_differs(value):
            value['passages'][0]['text'] = 'Date of Service: 11/09/2026.'

        def no_passage(value):
            value['encounter']['date_of_service']['passages'] = []

        def undefined_passage(value):
            value['encounter']['date_of_service']['passages'] = ['P7']

        for change, reason in ((case_differs, 'passage_unlocated'), (no_passage, 'words_unlocated'),
                               (undefined_passage, 'passage_unknown')):
            record, passages = inventory(change)
            with self.subTest(reason):
                self.assertEqual((record['state'], record['verified'], record['words'], record['reasons'],
                                  record['readings']), ('stated', False, None, [reason], []))
                for found in (dates.member_date_state(record, '1998-01-01', passages),
                              dates.member_date_state(record, '1998-01-01')):
                    self.assertEqual((found.state, found.hold, found.effective, found.corti_date),
                                     ('conflict_unverifiable', True, None, None))
                self.assertEqual(dates.corti_date(record, '1998-01-01', passages), None)
                self.assertEqual(dates.effective_date(record, '1998-01-01'), None)
        # the positive twin: the date's words bind, though not to the date Gemini gave - its reading settles it
        record, passages = inventory(lambda value: value['encounter']['date_of_service'].update(value='2026-11-08'))
        self.assertEqual((record['verified'], record['readings']), (False, ['2026-11-09']))
        self.assertEqual(row(record, '2026-11-09', passages), ('settles', False, '2026-11-09', 'user'))
        self.assertEqual(row(record, '1998-01-01', passages), ('conflict_unverifiable', True, None, 'conflict'))


if __name__ == '__main__':  # pragma: no cover
    sys.exit('Run with manage.py test.')
