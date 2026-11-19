"""The derived context and the routing stand-in over facts (docs/gemini-migration/FINAL-V2.md 4.7, 5.5, 1.1; step 2d of
its 8.1), TEXT-ONLY and SYNTHETIC.

What is proved here:
- the done-when of 8.1 step 2d: engine/derive.py's derive equals v1's facts.derive on fact-equivalent fixtures for the
  date of service and the member values - v1's computed in the test (a test-only import of the retired module), over
  every member_date_state row: no member value, agrees, conflict_birth, conflict_elsewhere, conflict_differs, settles,
  conflict_listed, conflict_unverifiable and supplies - the whole record compared, evidence, quotes and notes included,
  with document_date, the effective date and member_date's record; the member values and their refusals alike;
- the fact-equivalence itself (date_record): each state, the readings L1 stored, a negated date of service, and the
  other dates under 3.2.1's "an omission can only hold" (an unappraised birth role holds a member's birth date); a
  contradicted date's sides are candidates only when its result is contradicted and its stored integrity and L1 checks
  passed, and a several date reads no readings (triage 2d#3 and the refutation of its first repair, over the literals
  L1 stores: a side that failed integrity or L1, or a conflict doubt over a failed side, releases nothing v1 holds, and
  a weakened date releases nothing its contradicted twin holds, P6); another date possibly given for this encounter
  leaves a stated date unverified (triage 2d#4, v1's date_mismatch); the quotes are the dates' located words
  (Cited.at), as v1's (triage 2d:D3), the fixtures' v1 records holding the words v1 located - narrower than their
  units;
- every row is store.textfree_v2's view of a stored row, as the engine reads it (DECISIONS D188);
- the text-free boundary: derive never quotes; without a quote every text is '' and nothing decided changes, and with
  every character of the revision replaced by x only the quoted texts change (P-TEXTFREE's form);
- context_of equals v1's; the copied member vocabularies and missing notes equal gi.context's (a test-only import);
- the gemini-routing@2 stand-in: statuses from established facts over effective(), family slugs in FAMILY_ORDER.
Every document here is written for this test: no real patient, no development or acceptance document.
"""
from __future__ import annotations

import copy

from django.test import SimpleTestCase

from studio import types as studio_types
from studio.interpretation import ROUTING_VERSION_V2, dates
from studio.interpretation.contract import types as ct
from studio.interpretation.engine import derive as D
from studio.interpretation.engine import facts as F
from tests.v2.test_facts import (LINES, TEXT, Ledger, at, colonoscopy, content, encounter, est, event, fact, silent, src,
                                 unit_span, view)

ROLES = ('birth', 'other_occurrence', 'other_document', 'report_time', 'unclear')


def quote(start: int, end: int) -> str:
    return TEXT[start:end]


def words(n: int) -> dict:
    """S<n> as v1 stores a located span: its offsets and its own text."""
    span = unit_span(n)
    return {'start': span.start, 'end': span.end, 'text': TEXT[span.start:span.end]}


def v1_other(value: str, located: str) -> dict:
    """A verified other date as v1 stores it: its words are the date v1 located in the document (``located``)."""
    return {'value': value, 'verified': True, 'words': at(located), 'passages': [], 'reasons': []}


def v1_record(state, value=None, *, verified=False, words_=None, passages=(), candidates=(), readings=(),
              **others) -> dict:
    """A v1 date_of_service record (contract 8.1, the shape normalize stores)."""
    return {'state': state, 'value': value, 'verified': verified, 'words': words_, 'passages': list(passages),
            'reasons': [], 'candidates': list(candidates), 'readings': list(readings),
            'others': {role: list(others.get(role, ())) for role in ROLES}}


def v1_inventory(record, passages=()) -> dict:
    return {'events': {'passages': list(passages), 'lesions': [], 'events': [], 'relations': []},
            'encounter_facts': {'date_of_service': record}}


BIRTH, ELSEWHERE = '1960-01-02', '2026-11-04'


def v2_others() -> list:
    """The other dates as pass 1 files them and settle stores them: other_dates.role is outside CLAIMED (3.2.1), so
    each role is unresolved(unappraised)."""
    return [{'value': BIRTH, 'role': fact('birth', [src(['S9'], words=at('01/02/1960'))])},
            {'value': ELSEWHERE, 'role': fact('other_occurrence', [src(['S10'], words=at('11/04/2026'))])}]


def v2_row(date_of_service=None, others=None, ledger=None):
    """The encounter's dates written and read back by the store, as the engine reads them: store.textfree_v2's view."""
    k = ledger or Ledger()
    return view(content(k, encounter_=encounter(date_of_service, v2_others() if others is None else others)))


def dos_source():
    return src(['S2'], 'document_frame', at('11/09/2026'))


DAY = [{'value': '2026-11-09', 'precision': 'day'}]
# v1's words are the dates it located: '11/09/2026' inside 'Date of service: 11/09/2026', '01/02/1960' inside 'DOB:
# 01/02/1960', '11/04/2026' inside 'Next procedure: 11/04/2026' - each narrower than its unit (triage 2d:D3)
DOS_WORDS = '11/09/2026'
OTHERS_V1 = {'birth': [v1_other(BIRTH, '01/02/1960')], 'other_occurrence': [v1_other(ELSEWHERE, '11/04/2026')]}


def cases() -> dict:
    """{name: (v1 inventory, v2 row, member values to try)}: the fact-equivalent fixtures (module docstring)."""
    k = Ledger()
    verified = est(k, '', 'date_of_service', '2026-11-09', [dos_source()], literals=DAY)
    unverified = fact('2026-11-08', [dos_source()], reasons=['literal_mismatch'], literals=DAY)
    # its literals are what L1 stores for its sides' whole units ('11/09/2026' in S2, '11/04/2026' in S10)
    several = fact('', [src(['S2']), src(['S10'])], state='contradicted', result='contradicted',
                   reasons=['contradicted_by_pass1'], options=[{'value': '2026-11-09', 'sources': [src(['S2'])]},
                                                               {'value': ELSEWHERE, 'sources': [src(['S10'])]}],
                   literals=DAY + [{'value': ELSEWHERE, 'precision': 'day'}])
    located = [{'id': 'P2', 'state': 'located', 'spans': [words(2)], 'reason': '', 'chars': len(LINES[1]),
                'extended': ''}]
    # triage 2d#4: a second date for this encounter (role this_encounter, unappraised: outside CLAIMED); v1's
    # normalize left the stated date unverified (date_mismatch), its readings the full dates in its own words
    second = est(k, '', 'date_of_service', '2026-11-09', [dos_source()], literals=DAY)
    this_encounter = [{'value': BIRTH, 'role': fact('birth', [src(['S9'], words=at('01/02/1960'))])},
                      {'value': ELSEWHERE, 'role': fact('this_encounter', [src(['S10'], words=at('11/04/2026'))])}]
    return {
        'stated and verified': (
            v1_inventory(v1_record('stated', '2026-11-09', verified=True, words_=at(DOS_WORDS),
                                   readings=['2026-11-09'], **OTHERS_V1)),
            v2_row(verified, ledger=k), ('', '2026-11-09', '2026-11-08', BIRTH, ELSEWHERE)),
        'stated, not verified': (
            v1_inventory(v1_record('stated', words_=at(DOS_WORDS), readings=['2026-11-09'], **OTHERS_V1)),
            v2_row(unverified), ('', '2026-11-09', '2026-11-01', BIRTH, ELSEWHERE)),
        'stated beside another date for this encounter': (
            v1_inventory(v1_record('stated', words_=at(DOS_WORDS), readings=['2026-11-09'],
                                   birth=[v1_other(BIRTH, '01/02/1960')])),
            v2_row(second, others=this_encounter, ledger=k), ('', '2026-11-09', ELSEWHERE, BIRTH, '2026-11-01')),
        'several': (
            v1_inventory(v1_record('several', passages=['P2'], candidates=[ELSEWHERE, '2026-11-09']), located),
            v2_row(several, others=[]), ('', ELSEWHERE, '2026-11-09', '2026-11-07')),
        'not stated': (
            v1_inventory(v1_record('not_stated', **OTHERS_V1)),
            v2_row(None), ('', '2026-11-01', BIRTH, ELSEWHERE)),
    }


# --- a contradicted date of service, its sides checked or not (triage 2d#3 and its refutation) ---------------------------

# A side as pass 1 writes it: (value, [(units, words)]), words the exact words, or None for a citation that does not
# locate - S8 with S10 are not consecutive (I3: units_not_consecutive) - which L1 reads nothing of (consistency.Words)
# and settle stores with no words
DOS_A, MISREAD = '2026-11-09', '2026-11-05'
A_SIDE = (DOS_A, [(['S2'], '11/09/2026')])
B_SIDE = (ELSEWHERE, [(['S10'], '11/04/2026')])
B_FAILED = (ELSEWHERE, [(['S10'], '11/04/2026'), (['S8', 'S10'], None)])  # one citation located, one failed I3
# a side read as 2026-11-05 from words that state 2026-11-04: L1 fails it (v1's verify.date_words would not verify it)
B_MISREAD = (MISREAD, [(['S10'], '11/04/2026')])
B_MISREAD_FAILED = (MISREAD, [(['S10'], '11/04/2026'), (['S8', 'S10'], None)])


def l1(sides) -> tuple:
    """(passed, literals): what L1 stores with a contradicted date of service of ``sides`` and whether it passes - the
    claim-time rule whose result settle stores as checks.literals and checks.literal (contract/consistency, a test-only
    import of its _transcription) - each citation read by its located words (the revision's own slice), and nothing for
    one that does not locate."""
    from studio.interpretation.contract import consistency, extract_read, extract_schema  # test-only

    texts, pass_1 = {}, []
    for value, citations in sides:
        sources = []
        for units, words_ in citations:
            source = ct.Source(tuple(units), words_ or '', ct.Link.DOCUMENT_FRAME)
            texts[source] = None if words_ is None else TEXT[at(words_)['start']:at(words_)['end']]
            sources.append(source)
        pass_1.append((value, tuple(sources)))
    out = consistency._Out()
    key = extract_read.FactKey(extract_schema.Family.ENCOUNTER, '', ct.Attribute.DATE_OF_SERVICE, 0)
    passed = consistency._transcription(key, pass_1, texts.__getitem__, out)
    return passed, [{'value': literal.value, 'precision': literal.precision.value} for literal in out.literals[key]]


def two_sided(sides, *, result='contradicted', reasons=('contradicted_by_pass1',), doubts=()):
    """The row of a contradicted date of service of ``sides`` as settle stores it, viewed as the engine reads it: its
    literals and its literal check L1's (``l1``), its integrity check failed when a citation does not locate, and
    ``result`` with ``reasons`` (3.3 row 1: contradicted when every side passed I1-I3 or a conflict doubt names it,
    else unresolved)."""
    passed, literals = l1(sides)
    options, every = [], []
    for value, citations in sides:
        stored_ = [src(units, 'document_frame', at(words_) if words_ else None) for units, words_ in citations]
        options.append({'value': value, 'sources': stored_})
        every += stored_
    item = fact('', every, state='contradicted', result=result, reasons=reasons, options=options, literals=literals)
    located = all(words_ is not None for _, citations in sides for _, words_ in citations)
    item['checks'].update(integrity='ok' if located else 'failed', literal='ok' if passed else 'failed')
    return view(content(Ledger(), encounter_=encounter(item, []), doubts=list(doubts)))


def v1_several(candidates) -> dict:
    """v1's record of a several date of service whose VERIFIED sides are ``candidates`` (normalize._bind_date)."""
    located = [{'id': 'P2', 'state': 'located', 'spans': [words(2)], 'reason': '', 'chars': len(LINES[1]),
                'extended': ''}]
    return v1_inventory(v1_record('several', passages=['P2'], candidates=list(candidates)), located)


def held(row, member) -> bool:
    return D.derive(row, {'service_date': member}, quote=quote).member_date.hold


class ParityTests(SimpleTestCase):
    """derive equals v1's on fact-equivalent fixtures for the date of service and the member values (8.1 step 2d)."""

    def test_every_member_date_row_equals_v1s(self):
        from studio.interpretation import facts as v1  # test-only: the retired module, for its values

        seen = set()
        for name, (inventory, row, members) in cases().items():
            for member in members:
                values = {'service_date': member, 'setting': ' office ', 'billing_context': 'facility'}
                theirs = v1.derive(inventory, values)
                mine = D.derive(row, values, quote=quote)
                with self.subTest(case=name, member=member):
                    self.assertEqual(mine.facts, theirs.facts)
                    self.assertEqual(mine.document_date, theirs.document_date)
                    self.assertEqual(mine.document_date, v1.document_date(inventory))
                    self.assertEqual(mine.effective, theirs.effective)
                    self.assertEqual(mine.member_date.as_record(), theirs.member_date.as_record())
                    self.assertEqual(D.context_of(mine.facts), v1.context_of(theirs.facts))
                seen.add(mine.member_date.state)
        self.assertEqual(seen, set(dates.STATES))  # every row of the precedence was compared

    def test_the_member_values_and_their_refusals_equal_v1s(self):
        from studio.interpretation import facts as v1  # test-only

        inventory, row, _ = cases()['stated and verified']
        for values in ({}, {'setting': 'office', 'patient_status': ' established '}, {'billing_context': '  '},
                       {'setting': 'telehealth', 'billing_context': 'professional', 'patient_status': 'new'}):
            with self.subTest(values=values):
                self.assertEqual(D.derive(row, values, quote=quote).facts, v1.derive(inventory, values).facts)
        for values in ({'colour': 'red'}, {'setting': 'garage'}, {'setting': 1}, {'service_date': '11/09/2026'},
                       {'service_date': '2026-02-30'}, {'patient_status': 'returning'}, {'service_date': None}):
            with self.subTest(values=values):
                with self.assertRaises(ValueError) as mine:
                    D.derive(row, values)
                with self.assertRaises(ValueError) as theirs:
                    v1.derive(inventory, values)
                self.assertEqual(str(mine.exception), str(theirs.exception))

    def test_the_copied_vocabularies_and_notes_are_the_legacy_ones(self):
        from studio.gi import context as gi_context  # test-only

        self.assertEqual(tuple(member.value for member in D.ContextFact), studio_types.CONTEXT_FACTS)
        self.assertEqual((tuple(m.value for m in D.Setting), tuple(m.value for m in D.BillingContext),
                          tuple(m.value for m in D.PatientStatus)),
                         (gi_context.SETTINGS, gi_context.BILLING_CONTEXTS, gi_context.PATIENT_STATUSES))
        self.assertEqual({name.value: D.missing_note(name) for name in D.ContextFact}, gi_context.MISSING_NOTES)
        self.assertEqual(tuple(name.value for name in D.MEMBER_FACTS), ('setting', 'billing_context',
                                                                         'patient_status'))
        from studio.interpretation import facts as v1  # test-only: v1's RANK, strongest first

        self.assertEqual(tuple(m.value for m in D.ServiceStatus), tuple(v1.RANK))
        self.assertEqual(set(m.value for m in D.ServiceStatus), set(studio_types.SERVICE_STATUSES))


class DateRecordTests(SimpleTestCase):
    def record(self, date_of_service, others=None):
        return D.date_record(F.encounter_dates(v2_row(date_of_service, others)))

    def test_each_state(self):
        k = Ledger()
        verified = D.date_record(F.encounter_dates(v2_row(est(k, '', 'date_of_service', '2026-11-09', [dos_source()],
                                                              literals=DAY), ledger=k)))
        # its words: the located words of its source (Cited.at), narrower than the unit (triage 2d:D3)
        self.assertEqual((verified['state'], verified['value'], verified['verified'], verified['readings'],
                          verified['words']), ('stated', '2026-11-09', True, [],
                                               {'start': TEXT.index(DOS_WORDS),
                                                'end': TEXT.index(DOS_WORDS) + len(DOS_WORDS)}))
        self.assertNotEqual(verified['words'], {'start': unit_span(2).start, 'end': unit_span(2).end})
        silent_ = self.record(None)
        self.assertEqual((silent_['state'], silent_['value'], silent_['verified'], silent_['words']),
                         ('not_stated', None, False, None))

    def test_the_readings_are_l1s_stored_literals_less_the_other_dates(self):
        literals = DAY + [{'value': BIRTH, 'precision': 'day'}, {'value': '2026-11', 'precision': 'month'}]
        found = self.record(fact('2026-11-08', [dos_source()], reasons=['literal_mismatch'], literals=literals))
        self.assertEqual((found['state'], found['verified'], found['readings']), ('stated', False, ['2026-11-09']))
        # a doubted date (3.3 row 2) is read by its readings too; a negated one never settles anything
        doubted = self.record(fact('2026-11-09', [dos_source()], result='unknown', reasons=['doubt_unclear'],
                                   literals=DAY))
        self.assertEqual(doubted['readings'], ['2026-11-09'])
        k = Ledger()
        negated = D.date_record(F.encounter_dates(v2_row(est(k, '', 'date_of_service', '2026-11-09', [dos_source()],
                                                             state='negated', literals=DAY), ledger=k)))
        self.assertEqual((negated['state'], negated['verified'], negated['readings']), ('stated', False, []))
        self.assertEqual(dates.member_date_state(negated, '2026-11-09', quote=quote).state,
                         dates.CONFLICT_UNVERIFIABLE)
        with self.assertRaises(KeyError):  # a v2 record's spans carry no text: it is quoted by the caller's slice
            dates.member_date_state(negated, '2026-11-09')

    def test_a_doubts_reading_is_never_a_candidate(self):
        # possibly() reads a date_of_service doubt's reading; the record's candidates are the sides pass 1 reported
        several = fact('', [src(['S2']), src(['S10'])], state='contradicted', result='contradicted',
                       reasons=['contradicted_by_pass1'], options=[{'value': '2026-11-09', 'sources': [src(['S2'])]},
                                                                   {'value': ELSEWHERE, 'sources': [src(['S10'])]}])
        row = view(content(Ledger(), encounter_=encounter(several, []), doubts=[{
            'about': 'date_of_service', 'objects': [], 'units': ['S2'], 'basis': 'unclear',
            'readings': ['2026-11-07']}]))
        found = F.encounter_dates(row)
        self.assertIn(F.iso_value('2026-11-07'), found.date_of_service.options)
        self.assertEqual(found.sides, (F.iso_value('2026-11-09'), F.iso_value(ELSEWHERE)))
        self.assertEqual(D.date_record(found)['candidates'], [ELSEWHERE, '2026-11-09'])
        self.assertEqual(D.derive(row, {'service_date': '2026-11-07'}, quote=quote).member_date.state,
                         dates.CONFLICT_LISTED)

    def test_an_unappraised_birth_role_holds_a_members_birth_date(self):
        # other_dates.role is outside CLAIMED, so it never settles established: read as v1's "verified" only when
        # established, the birth date would be supplied as the date of service. 3.2.1: an omission can only hold.
        found = self.record(None)
        self.assertEqual([entry['value'] for entry in found['others']['birth']], [BIRTH])
        derived = D.derive(v2_row(None), {'service_date': BIRTH}, quote=quote)
        self.assertEqual((derived.member_date.state, derived.member_date.hold, derived.effective),
                         (dates.CONFLICT_BIRTH, True, None))
        # an other date whose role is established as another role takes no part in the birth row
        k = Ledger()
        established = [{'value': BIRTH, 'role': est(k, '', 'other_dates.role', 'report_time',
                                                    [src(['S9'], words=at('01/02/1960'))])}]
        derived = D.derive(v2_row(None, established, ledger=k), {'service_date': BIRTH}, quote=quote)
        self.assertEqual(derived.member_date.state, dates.SUPPLIES)

    def test_the_two_sided_fixtures_store_what_l1_stores(self):
        # the rows below hold the literals settle stores (the refutation of 2d#3's first repair: its row held none,
        # which L1 never leaves for sides whose words state their dates). A citation that does not locate is read for
        # nothing; a side whose words state another date fails L1
        day = [{'value': DOS_A, 'precision': 'day'}, {'value': ELSEWHERE, 'precision': 'day'}]
        self.assertEqual(l1([A_SIDE, B_SIDE]), (True, day))
        self.assertEqual(l1([A_SIDE, B_FAILED]), (True, day))
        self.assertEqual(l1([A_SIDE, B_MISREAD]), (False, day))
        self.assertEqual(l1([A_SIDE, B_MISREAD_FAILED]), (False, day))
        weak = two_sided([A_SIDE, B_FAILED], result='unresolved', reasons=('units_not_consecutive',))
        found = F.encounter_dates(weak)
        self.assertEqual((found.date_of_service.result, found.checks_passed, [lit.iso for lit in found.literals]),
                         (ct.Result.UNRESOLVED, False, [DOS_A, ELSEWHERE]))

    def test_a_side_that_failed_integrity_is_no_candidate(self):
        # triage 2d#3, the reviewer's input as settle stores it: side B (2026-11-04) cites S10's '11/04/2026', which
        # locates, and S8 with S10, which are not consecutive (I3), so the fact settled unresolved, its integrity check
        # failed, and L1 stored both sides' dates. Which side failed is not stored, so neither side is a candidate and
        # no literal is a reading: a member's date of the side that failed is held, as v1 holds it (conflict_listed: it
        # kept only the verified side), where the first repair settled it by its readings - and so is every date
        from studio.interpretation import facts as v1  # test-only: the retired module, for its values

        weak = two_sided([A_SIDE, B_FAILED], result='unresolved', reasons=('units_not_consecutive',))
        record = D.date_record(F.encounter_dates(weak))
        self.assertEqual((record['state'], record['candidates'], record['readings']), ('several', [], []))
        theirs = v1.derive(v1_several([DOS_A]), {'service_date': ELSEWHERE})
        self.assertEqual((theirs.member_date.state, theirs.member_date.hold, theirs.effective),
                         (dates.CONFLICT_LISTED, True, None))
        for member in (ELSEWHERE, DOS_A, '2026-11-07'):
            mine = D.derive(weak, {'service_date': member}, quote=quote)
            with self.subTest(member=member):
                self.assertEqual((mine.member_date.state, mine.member_date.hold, mine.effective,
                                  mine.facts['service_date']['value']), (dates.CONFLICT_UNVERIFIABLE, True, None, None))
        # with no member value it offers no documented date, as v1's several date with no verified candidate does
        self.assertEqual((D.derive(weak, {}, quote=quote).effective, D.document_date(weak, quote=quote)['origin'],
                          v1.document_date(v1_several([]))['origin']), (None, dates.MISSING, dates.MISSING))
        # the twin whose every side passed (result contradicted, its checks ok): both candidates, and either settles
        strong = two_sided([A_SIDE, B_SIDE])
        self.assertEqual(D.date_record(F.encounter_dates(strong))['candidates'], [ELSEWHERE, DOS_A])
        for member in (DOS_A, ELSEWHERE):
            with self.subTest(twin='contradicted', member=member):
                self.assertEqual(D.derive(strong, {'service_date': member}, quote=quote).member_date.state,
                                 dates.SETTLES)

    def test_a_weakened_date_of_service_releases_nothing_its_contradicted_twin_holds(self):
        # P6 (the refutation of 2d#3's first repair, its critical finding): one side's citation failing I3 weakens the
        # contradicted date of service to unresolved, and that never releases a member's date the contradicted twin
        # holds. The first repair read the weak twin's readings - every side's literals - so it took 2026-11-04, which
        # the misread side's words name and no side gives, while the contradicted twin and v1 held it
        pairs = {'every side checked': ([A_SIDE, B_SIDE], [A_SIDE, B_FAILED], ('units_not_consecutive',)),
                 'a side whose words state another date': ([A_SIDE, B_MISREAD], [A_SIDE, B_MISREAD_FAILED],
                                                           ('units_not_consecutive', 'literal_mismatch'))}
        released, weak = set(), {}
        for name, (strong_sides, weak_sides, reasons) in pairs.items():
            strong = two_sided(strong_sides)
            weak[name] = two_sided(weak_sides, result='unresolved', reasons=reasons)
            members = {DOS_A, ELSEWHERE, MISREAD, '2026-11-07'} | {item['value'] for item in l1(weak_sides)[1]}
            for member in sorted(members):
                with self.subTest(pair=name, member=member):
                    self.assertTrue(held(weak[name], member) or not held(strong, member))
                if not held(strong, member):
                    released.add((name, member))
        # not vacuous: the contradicted twin whose every side was checked takes its sides
        self.assertEqual(released, {('every side checked', DOS_A), ('every side checked', ELSEWHERE)})
        # the refuted case itself: 2026-11-04, a date no side gives, is held by the weak twin
        self.assertTrue(held(weak['a side whose words state another date'], ELSEWHERE))

    def test_a_side_whose_words_state_another_date_is_no_candidate(self):
        # v1 verified each candidate (verify.date_words: the full dates in its words equal its value); v2's L1 judges
        # every side's words, stored per fact. A side read as 2026-11-05 from words stating 2026-11-04 fails L1 although
        # the fact is contradicted (3.3 row 1 comes before L1's row 4): no side is a candidate, and the misread value is
        # held as v1 holds it (conflict_listed), where it had settled
        from studio.interpretation import facts as v1  # test-only

        row = two_sided([A_SIDE, B_MISREAD])
        found = F.encounter_dates(row)
        self.assertEqual((found.date_of_service.result, found.checks_passed), (ct.Result.CONTRADICTED, False))
        self.assertEqual(D.date_record(found)['candidates'], [])
        for member in (MISREAD, ELSEWHERE):
            theirs = v1.derive(v1_several([DOS_A]), {'service_date': member})
            mine = D.derive(row, {'service_date': member}, quote=quote)
            with self.subTest(member=member):
                self.assertEqual((theirs.member_date.state, theirs.member_date.hold), (dates.CONFLICT_LISTED, True))
                self.assertEqual((mine.member_date.state, mine.member_date.hold, mine.effective),
                                 (dates.CONFLICT_UNVERIFIABLE, True, None))
        # fail-closed where v1 kept its verified side: which side failed is not stored, so 2026-11-09 is held as well
        self.assertEqual(v1.derive(v1_several([DOS_A]), {'service_date': DOS_A}).member_date.state, dates.SETTLES)
        self.assertTrue(held(row, DOS_A))

    def test_a_conflict_doubt_never_makes_a_failed_side_a_candidate(self):
        # 3.3 row 1's second clause: a doubt with basis conflict naming the date of service makes it contradicted
        # whatever its sides' integrity, so a contradicted result does not mean every side passed I1-I3 (the
        # refutation's problem 3). With side B's citation failed, no side is a candidate and B's date is held, as v1
        # holds it; with every side checked, the same doubt leaves both sides candidates
        conflict = [{'about': 'date_of_service', 'objects': [], 'units': ['S2'], 'basis': 'conflict', 'readings': []}]
        failed = two_sided([A_SIDE, B_FAILED], doubts=conflict)
        found = F.encounter_dates(failed)
        self.assertEqual((found.date_of_service.result, found.checks_passed), (ct.Result.CONTRADICTED, False))
        self.assertEqual(D.date_record(found)['candidates'], [])
        self.assertEqual([held(failed, member) for member in (ELSEWHERE, DOS_A)], [True, True])
        checked = two_sided([A_SIDE, B_SIDE], doubts=conflict)
        self.assertEqual(D.date_record(F.encounter_dates(checked))['candidates'], [ELSEWHERE, DOS_A])
        self.assertEqual([held(checked, member) for member in (ELSEWHERE, DOS_A)], [False, False])

    def test_another_date_for_this_encounter_leaves_a_stated_date_unverified(self):
        # triage 2d#4, the reviewer's input: the date of service established as 2026-11-09 beside an other date
        # 2026-11-04 whose role is this_encounter, unappraised as 3.2.1 settles it (other_dates.role is outside
        # CLAIMED, so it is never established and an omission can only hold): the document gives this encounter a
        # second date, so the stated one is unverified, as v1's normalize._bind_date left it (date_mismatch)
        k = Ledger()
        verified = est(k, '', 'date_of_service', '2026-11-09', [dos_source()], literals=DAY)

        def derived(role, value=ELSEWHERE):
            return D.derive(v2_row(verified, [{'value': value, 'role': role}], ledger=k), {}, quote=quote)

        source = [src(['S10'], words=at('11/04/2026'))]
        both = fact('', source, state='contradicted', result='contradicted', reasons=['contradicted_by_pass1'],
                    options=[{'value': 'birth', 'sources': source}, {'value': 'this_encounter', 'sources': source}])
        for role in (fact('this_encounter', source), est(k, '', 'other_dates.role', 'this_encounter', source), both):
            with self.subTest(role=role['claim']['value'], result=role['result']):
                found = derived(role)
                self.assertEqual((found.effective, found.facts['service_date']['origin'],
                                  found.document_date['origin']), (None, dates.MISSING, dates.MISSING))
        # possibly this_encounter only: a role established as another one, or the same date, leaves it verified
        for role, value in ((est(k, '', 'other_dates.role', 'report_time', source), ELSEWHERE),
                            (fact('this_encounter', source), '2026-11-09')):
            with self.subTest(role=role['claim']['value'], value=value):
                found = derived(role, value)
                self.assertEqual((found.effective, found.facts['service_date']['origin']),
                                 ('2026-11-09', dates.DOCUMENT))

    def test_the_quote_is_the_dates_located_words_as_v1s(self):
        # triage 2d:D3 (DECISIONS D188): the date's words '11/09/2026' are narrower than their unit ('Date of service:
        # 11/09/2026'); derive quotes them (Cited.at), as v1 quoted its located words, not the whole unit
        from studio.interpretation import facts as v1  # test-only

        inventory, row, _ = cases()['stated and verified']
        for member in ('', '2026-11-08'):
            mine, theirs = D.derive(row, {'service_date': member}, quote=quote), v1.derive(inventory, {
                'service_date': member})
            with self.subTest(member=member):
                self.assertEqual([span['text'] for span in mine.facts['service_date']['evidence']], [DOS_WORDS])
                self.assertEqual(mine.facts['service_date'], theirs.facts['service_date'])
        self.assertEqual(D.document_date(row, quote=quote)['quote']['text'], DOS_WORDS)
        # a held row's note quotes the other date's located words: 'DOB: 01/02/1960' gives '01/02/1960'
        birth = D.derive(row, {'service_date': BIRTH}, quote=quote).member_date
        self.assertIn('“01/02/1960”', birth.note)
        self.assertEqual(birth.as_record(), v1.derive(inventory, {'service_date': BIRTH}).member_date.as_record())
        # a source that cites its whole units is quoted whole: the several date's first side cites S2 with no words
        several = cases()['several'][1]
        self.assertEqual(D.document_date(several, quote=quote)['evidence'][0]['text'], LINES[1])


class TextFreeTests(SimpleTestCase):
    def test_derive_never_quotes_and_without_a_quote_every_text_is_empty(self):
        inventory, row, _ = cases()['stated and verified']
        for member in ('', '2026-11-08', BIRTH):
            values = {'service_date': member}
            plain, quoted = D.derive(row, values), D.derive(row, values, quote=quote)
            with self.subTest(member=member):
                self.assertEqual((plain.effective, plain.member_date.state, plain.member_date.hold,
                                  plain.member_date.origin), (quoted.effective, quoted.member_date.state,
                                                              quoted.member_date.hold, quoted.member_date.origin))
                self.assertTrue(all(span['text'] == '' for span in plain.facts['service_date']['evidence']))
                self.assertEqual([{k: v for k, v in span.items() if k != 'text'} for span in
                                  plain.facts['service_date']['evidence']],
                                 [{k: v for k, v in span.items() if k != 'text'} for span in
                                  quoted.facts['service_date']['evidence']])

    def test_replacing_every_character_of_the_revision_changes_only_the_quoted_text(self):
        hidden = ''.join(character if character == '\n' else 'x' for character in TEXT)

        def blind(start: int, end: int) -> str:
            return hidden[start:end]

        for name, (_, row, members) in cases().items():
            for member in members:
                seen, blinded = D.derive(row, {'service_date': member}, quote=quote), D.derive(
                    row, {'service_date': member}, quote=blind)
                with self.subTest(case=name, member=member):
                    first, second = seen.member_date.as_record(), blinded.member_date.as_record()
                    for record in (first, second):
                        record.pop('note'), record.pop('evidence')
                    self.assertEqual(first, second)
                    self.assertEqual(seen.effective, blinded.effective)
                    for key in ('value', 'origin', 'state'):
                        self.assertEqual(seen.facts['service_date'][key], blinded.facts['service_date'][key])
                    self.assertEqual([(s['start'], s['end']) for s in seen.facts['service_date']['evidence']],
                                     [(s['start'], s['end']) for s in blinded.facts['service_date']['evidence']])


class StandInTests(SimpleTestCase):
    def events(self):
        events = colonoscopy()
        k = Ledger()
        k.claims = events['claims']
        events['events'].append(event(
            'E6', ['S10'], status=est(k, 'E6', 'status', 'planned', [src(['S10'])], control='performed'),
            kind=est(k, 'E6', 'kind', 'fna', [src(['S10'])], control='biopsy'),
            session=est(k, 'E6', 'session', 'X2', [src(['S10'])], control='X1')))
        events['events'].append(event(
            'E7', ['S4'], status=est(k, 'E7', 'status', 'performed', [src(['S4'])], control='performed'),
            kind=est(k, 'E7', 'kind', 'removal', [src(['S4'])], control='snare'),
            session=fact('X3', [src(['S4'])]),
            date_relation=est(k, 'E7', 'date_relation', 'earlier_date', [src(['S4'], 'section')],
                              control='on_date_of_service', literals=[{'value': '2023', 'precision': 'year'}])))
        return events

    def test_the_stand_in(self):
        found = D.routing_stand_in(view(self.events()), '2026-11-09', inventory_id='inv', inventory_sha256='a' * 64)
        self.assertEqual(found, {'version': ROUTING_VERSION_V2, 'document_kind': '', 'inventory': 'inv',
                                 'inventory_sha256': 'a' * 64, 'findings': [
                                     {'family': 'gi.eus', 'status': 'planned', 'mentions': [], 'facts': [],
                                      'missing': []},
                                     {'family': 'gi.colonoscopy', 'status': 'performed', 'mentions': [], 'facts': [],
                                      'missing': []}]})

    def test_each_status(self):
        R = F.factset(view(self.events()))
        E = [event_id for event_id in R.events]
        self.assertEqual([D.status_of(R, e) for e in E], [
            D.ServiceStatus.PERFORMED, D.ServiceStatus.PERFORMED, D.ServiceStatus.NEGATED, D.ServiceStatus.UNCERTAIN,
            D.ServiceStatus.UNCERTAIN, D.ServiceStatus.PLANNED, D.ServiceStatus.HISTORICAL])
        # a member's other date demotes the on-date relations: the colonoscopy family is only uncertain
        found = D.routing_stand_in(view(self.events()), '2026-11-08')
        self.assertEqual([(f['family'], f['status']) for f in found['findings']],
                         [('gi.eus', 'planned'), ('gi.colonoscopy', 'uncertain')])
        # E7's session names no stored session: no family
        self.assertIsNone(D.family_of(R, E[6]))

    def test_the_family_slugs_are_v1s(self):
        from studio.interpretation import lexicon  # test-only: v1's FAMILY_OF and FAMILY_ORDER

        self.assertEqual([D.family_slug(family) for family in D.catalogue.FAMILY_ORDER], list(lexicon.FAMILY_ORDER))
        self.assertEqual(D.RANK, {status: index for index, status in enumerate(D.ServiceStatus)})


class ContextOfTests(SimpleTestCase):
    def test_context_of_reads_stored_facts_as_v1s(self):
        from studio.interpretation import facts as v1  # test-only

        stored_facts = copy.deepcopy(D.derive(cases()['stated and verified'][1], {'service_date': '2026-11-08'},
                                              quote=quote).facts)
        self.assertEqual(D.context_of(stored_facts), v1.context_of(stored_facts))
        self.assertEqual(D.context_of(None), {})
        self.assertIsInstance(D.context_of(stored_facts)['service_date'], studio_types.Fact)
