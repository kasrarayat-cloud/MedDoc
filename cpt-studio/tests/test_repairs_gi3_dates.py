"""GI round 3 (session 7c8d38da, 2026-10-29), repair agent "dates": the shared date/section binding, the owner's first
priority (h2-08; interpretations 41 and 42).

At 90377ec6f413 a plan or history section dropped every date-of-service label it held, and the section reader opens
sections only at headings it can place. h2-08's charge block ("Charge information" / "Date of service: 2026-10-06")
therefore inherited the "Assessment and plan" section: 2026-10-06 was dropped with nothing left behind and the header's
2026-10-05 was sent (encounter e084b793). A plan or history section now governs a label only within its reach
(studio/gi/context.py, _binding):
- part 1: a heading the section reader cannot place ends the reach, unless its words name a plan, a history, another
  occurrence, a service, an act or another document, or it ends on an occurrence noun;
- part 2 and B4: inside a plan with no block heading, a field of the encounter's own date-of-service label speaks, and
  so does a visit or procedure date field unless the plan item right before it names a later occurrence and its date
  is later than every date the note labels as its own;
- a label no section governs any longer speaks but is never the note's own by itself: asked, a member's answer equal
  to it taken ('aside' and 'empty' stay dropped);
- part 3: a planned procedure's own heading after the plan, documenting nothing, is asked (gi2 dates-planned-no-part);
- part 4: a plan date earlier than the visit, or a history date later than it, is asked;
- X3: the date-of-service label broken over one line break ("Date of" / "service: 2026-10-06") is read, never as the
  note's own date by itself;
- RC5: a plan section the document's own follow-up title opens ("GI clinic follow-up") governs no label;
- RC6: the setting and patient-status readers share the binding.

The expected answers live outside the reader: the corpus (tests/corpus/gi3_dates) holds each text with its
source-reviewed expectation, and the known-case texts are under tests/fixtures/gi3. Synthetic text only (every
document opens with the synthetic banner); pure functions - no database, no provider, no network.
"""
import contextlib
import json
import random
import re
import time
from datetime import date
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from studio.gi import context
from studio.providers import corti

TESTS = Path(__file__).resolve().parent
CORPUS = TESTS / 'corpus' / 'gi3_dates'
FIXTURES = TESTS / 'fixtures' / 'gi3'
STRANGER = '2026-10-01'  # a date no text here documents
BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
H208 = ('live-text/h2-08__e084b793__2026-10-29.txt', 'h2/h2-08-hepatology-note.txt')
H207 = ('live-text/h2-07__fbdd6d27__2026-10-29.txt', 'h2/h2-07-clinic-note.txt')
HEADER = (BANNER + 'Synthetic GI clinic (fictional)\nClinic note\nPatient: Synthetic Patient (fictional)\n'
          'Date of service: 2026-10-05\nPlace of service: office (POS 11)\nEstablished patient\n\nSubjective\n'
          'Follow-up of anemia.\n\n')
UNDATED = HEADER.replace('Date of service: 2026-10-05\n', '')


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding='utf-8')


def facts(text: str) -> dict:
    return context.extract_context(text)


def date_fact(text: str):
    return facts(text)['service_date']


def sent(text: str):
    """The date the provider request carries: a documented date (a conflict or a question carries none)."""
    fact = date_fact(text)
    return fact.value if fact.origin == 'document' else None


def member(text: str, value: str) -> str:
    """What a member's answer ``value`` does: 'taken', 'held' (a member conflict) or 'agrees' with the document."""
    merged = context.merge_user_values(facts(text), {'service_date': value})['service_date']
    if context.is_member_conflict(merged):
        return 'held'
    if merged.origin == 'user' and merged.value == value:
        return 'taken'
    if merged.origin == 'document' and merged.value == value:
        return 'agrees'
    return f'{merged.origin}:{merged.value}'


def fact_text(fact) -> str:
    return f'{fact.origin}:{fact.value}' if fact.origin in ('document', 'user') else fact.origin


def _clear_caches():
    # gi3 fix round 2: and the title's line and the visit-note reading, cached per text the same way
    for cached in (context._context, context._governance, context._title_start, context._title_line,
                   context._visit_note):
        cached.cache_clear()


@contextlib.contextmanager
def binding_disabled():
    """The reading with this repair switched off: every label or statement a plan or history section holds is governed
    (dropped), no part 3 or part 4 doubt, no broken label, no title's section - the reading of 90377ec6f413, as the
    measurement confirmed over the stress corpus (identical facts, evidence and member outcomes)."""
    def installed(text, lay, start, end, label=''):
        return context._GOVERNED if lay.section_at(start).kind in context.NOT_CURRENT_SECTIONS else context._READ

    _clear_caches()
    with mock.patch.object(context, '_binding', installed), \
            mock.patch.object(context, '_plans_procedure', lambda *args: False), \
            mock.patch.object(context, '_time_directed', lambda *args: []), \
            mock.patch.object(context, 'BROKEN_SERVICE_DATE', re.compile('(?!)')), \
            mock.patch.object(context, '_title_start', lambda text: None):
        try:
            yield
        finally:
            for cached in (context._context, context._governance, context._title_line, context._visit_note):
                cached.cache_clear()  # (_title_start is the patch here)
    _clear_caches()


class DateAsserts:
    def assert_conflict(self, text, *values):
        """A documented conflict: no date is sent, each listed date is a member's answer that is taken, and a date the
        document never states is held."""
        fact = date_fact(text)
        self.assertEqual(fact.origin, 'conflict', [e.text for e in fact.evidence])
        self.assertEqual(set(context.documented_values(fact)), set(values), fact.note)
        self.assertIsNone(sent(text))
        for value in values:
            self.assertEqual(member(text, value), 'taken', value)
        self.assertEqual(member(text, STRANGER), 'held')

    def assert_document(self, text, value):
        fact = date_fact(text)
        self.assertEqual((fact.origin, fact.value), ('document', value), [e.text for e in fact.evidence])
        self.assertEqual(member(text, STRANGER), 'held')

    def assert_asked(self, text, *never):
        fact = date_fact(text)
        self.assertNotEqual(fact.origin, 'document', fact.value)
        self.assertNotIn(fact.value, never)


# --- the corpus ------------------------------------------------------------------------------------------------------

def corpus_rows():
    return json.loads((CORPUS / 'variants.json').read_text(encoding='utf-8'))['rows']


def known_limits():
    return json.loads((CORPUS / 'known_limits.json').read_text(encoding='utf-8'))['limits']


def row_text(row) -> str:
    return row['text'] if 'text' in row else (TESTS / row['fixture']).read_text(encoding='utf-8')


def row_output(text: str) -> dict:
    """A row's whole output, as known_limits.json pins it."""
    found = facts(text)
    fact = found['service_date']
    probes = sorted({d.isoformat() for d in (context.date_from_match(m) for m in context.FULL_DATE.finditer(text)) if d}
                    | {STRANGER})
    return {'service_date': f'{fact.origin}:{fact.value}', 'sent': fact.value if fact.origin == 'document' else None,
            'member': {p: member(text, p) for p in probes}, 'setting': fact_text(found['setting']),
            'patient_status': fact_text(found['patient_status'])}


def by_source(expected: dict, out: dict) -> bool:
    """Whether an output is right by the row's source-reviewed expectation (README.md)."""
    kind, got, answers = expected['kind'], out['sent'], out['member']
    if any(out[name] != expected[name] for name in ('setting', 'patient_status') if name in expected and kind != 'facts'):
        return False
    if kind == 'document':
        return got == expected['value'] and answers[STRANGER] == 'held'
    if kind == 'conflict':
        return got is None and answers[STRANGER] == 'held' and all(answers.get(v) == 'taken' for v in expected['values'])
    if kind == 'asked':
        return got is None
    if kind == 'uncertain':
        return (f'document:{got}' if got else 'asked') in expected['acceptable']
    if kind == 'facts':
        named = [name for name in ('service_date', 'setting', 'patient_status') if name in expected]
        right = all(out[name] == expected[name] for name in named)
        if expected.get('service_date', '').startswith('document:'):
            right = right and answers[STRANGER] == 'held'
        return right
    raise ValueError(kind)


class CorpusTests(SimpleTestCase):
    """Every source-reviewed row reads right by its source, or is a known limit pinned by its exact output."""

    def test_every_row_reads_right_or_is_a_pinned_known_limit(self):
        limits = known_limits()
        rows = corpus_rows()
        self.assertEqual(len(rows), 136)
        for row in rows:
            text = row_text(row)
            self.assertTrue(text.startswith(BANNER), row['id'])
            out = row_output(text)
            with self.subTest(row=row['id']):
                if row['id'] in limits:
                    self.assertFalse(by_source(row['expected'], out), 'a known limit now reads right: update the pin')
                    self.assertEqual(out, limits[row['id']]['output'], limits[row['id']]['reason'])
                else:
                    self.assertTrue(by_source(row['expected'], out), (row['expected'], out, row['review']))

    def test_the_pins_name_rows_and_say_why(self):
        ids = {row['id'] for row in corpus_rows()}
        for name, limit in known_limits().items():
            self.assertIn(name, ids)
            self.assertGreater(len(limit['reason']), 40, name)

    def test_no_known_limit_sends_a_date_the_source_contradicts_but_the_separator_rule(self):
        """The pinned limits ask where the source sends - except the broken label without its separator, which X3 as
        ruled does not read (the installed reading's send, unchanged)."""
        rows = {row['id']: row for row in corpus_rows()}
        for name, limit in known_limits().items():
            got = limit['output']['sent']
            with self.subTest(row=name):
                if name == 'R-X3-no-separator':
                    self.assertEqual(got, '2026-10-05')
                else:
                    self.assertIsNone(got, rows[name]['expected'])


# --- the known cases -------------------------------------------------------------------------------------------------

class KnownCaseTests(DateAsserts, SimpleTestCase):
    """h2-08 (the owner's first priority), h2-07 and every other known text."""

    def test_h2_08_is_a_date_conflict(self):
        for name in H208:
            with self.subTest(text=name):
                text = fixture(name)
                self.assert_conflict(text, '2026-10-05', '2026-10-06')
                for other in ('1959-06-02', '2026-09-28', '2025-03-10'):
                    self.assertEqual(member(text, other), 'held', other)

    def test_h2_08_sends_no_date_line(self):
        """The request built for the fact's date carries the document text alone (jobs.py builds it from the
        effective date: a conflict has none)."""
        for name in H208:
            with self.subTest(text=name):
                text = fixture(name)
                request = corti.build_coding_request('corti', 'gi3-dates', text, context.service_date_of(text), 10 ** 7)
                self.assertEqual(request.contexts, (text,))
                self.assertFalse(any(item.startswith('Date of service:') for item in request.contexts))
                answered = context.merge_user_values(facts(text), {'service_date': '2026-10-06'})['service_date']
                self.assertEqual((answered.origin, answered.value), ('user', '2026-10-06'))

    def test_h2_08_charge_block_is_the_only_new_speaker(self):
        """Its evidence is the two labels; the time statement ("Physician time on the service date: 44 minutes") is no
        date field, and the plan's own prose stays governed."""
        for name in H208:
            with self.subTest(text=name):
                quoted = sorted(' '.join(e.text.split()) for e in date_fact(fixture(name)).evidence)
                self.assertEqual(quoted, ['Date of service: 2026-10-05', 'Date of service: 2026-10-06'])

    def test_h2_07_keeps_its_visit_date(self):
        for name in H207:
            with self.subTest(text=name):
                self.assert_document(fixture(name), '2026-10-21')

    # Read as the installed revision reads them (each checked against its source; h2-09's "Date of examination:" is no
    # label of the closed list - a known limit of the label grammar, outside this binding: asked, never sent).
    UNCHANGED = {
        'h2/h2-01-endoscopy-report.txt': ('document:2026-10-16', 'document:asc', 'missing'),
        'h2/h2-02-colonoscopy-report.txt': ('document:2026-10-09', 'document:hospital_outpatient', 'missing'),
        'h2/h2-03-sigmoidoscopy-note.txt': ('document:2026-10-13', 'document:office', 'missing'),
        'h2/h2-04-upper-endoscopy-report.txt': ('document:2026-10-07', 'document:asc', 'missing'),
        'h2/h2-05-pre-procedure-note.txt': ('document:2026-10-20', 'document:asc', 'missing'),
        'h2/h2-06-office-visit.txt': ('document:2026-10-14', 'document:office', 'document:established'),
        'h2/h2-07-clinic-note.txt': ('document:2026-10-21', 'document:office', 'document:established'),
        'h2/h2-09-eus-report.txt': ('missing', 'document:hospital_outpatient', 'missing'),
        'h2/h2-10-ercp-note.txt': ('document:2026-10-23', 'document:hospital_outpatient', 'missing'),
        'ho/ho-01-egd-colonoscopy-tattoo-conflict.txt': ('document:2026-10-20', 'document:asc', 'missing'),
        'ho/ho-02-colonoscopy-complete-deferred-emr.txt': ('document:2026-10-19', 'document:hospital_outpatient',
                                                           'missing'),
        'ho/ho-03-colonoscopy-incomplete-stricture.txt': ('document:2026-10-08', 'document:asc', 'missing'),
        'ho/ho-04-office-visit-dysphagia-egd-scheduled.txt': ('document:2026-10-22', 'document:office',
                                                              'document:established'),
        'ho/ho-05-sparse-gi-note.txt': ('missing', 'missing', 'missing'),
        'ho/ho-06-eus-fnb-pancreatic-tail-mass.txt': ('document:2026-10-15', 'document:hospital_outpatient', 'missing'),
        'ho/ho-07-ercp-biliary-metal-stent.txt': ('document:2026-10-21', 'document:hospital_outpatient', 'missing'),
        'ho/ho-08-esophageal-hrm-interpretation.txt': ('document:2026-10-13', 'document:hospital_outpatient', 'missing'),
        'ho/ho-09-flex-sig-hemorrhoid-band-ligation.txt': ('document:2026-10-14', 'document:office', 'missing'),
        'live-text/h2-01__9468f9c1__2026-10-29.txt': ('document:2026-10-16', 'document:asc', 'missing'),
        'live-text/h2-02__683c3e35__2026-10-29.txt': ('document:2026-10-09', 'document:hospital_outpatient', 'missing'),
        'live-text/h2-03__5c1bbf3a__2026-10-29.txt': ('document:2026-10-13', 'document:office', 'missing'),
        'live-text/h2-04__3af9d4ce__2026-10-29.txt': ('document:2026-10-07', 'document:asc', 'missing'),
        'live-text/h2-05__5e21f16b__2026-10-29.txt': ('document:2026-10-20', 'document:asc', 'missing'),
        'live-text/h2-06__8d5aa436__2026-10-29.txt': ('document:2026-10-14', 'document:office', 'document:established'),
        'live-text/h2-07__fbdd6d27__2026-10-29.txt': ('document:2026-10-21', 'document:office', 'document:established'),
        'live-text/h2-09__9630d149__2026-10-29.txt': ('missing', 'document:hospital_outpatient', 'missing'),
        'live-text/h2-10__f514e436__2026-10-29.txt': ('document:2026-10-23', 'document:hospital_outpatient', 'missing'),
        'live-text/ho-01__30d3f32d__2026-10-29.txt': ('document:2026-10-20', 'document:asc', 'missing'),
        'live-text/ho-01__a8e50085__2026-10-28.txt': ('document:2026-10-20', 'document:asc', 'missing'),
        'live-text/ho-02__d2f11d16__2026-10-29.txt': ('document:2026-10-19', 'document:hospital_outpatient', 'missing'),
        'live-text/ho-02__d8b06708__2026-10-28.txt': ('document:2026-10-19', 'document:hospital_outpatient', 'missing'),
        'live-text/ho-03__a866597c__2026-10-29.txt': ('document:2026-10-08', 'document:asc', 'missing'),
        'live-text/ho-03__b1b1edf2__2026-10-28.txt': ('document:2026-10-08', 'document:asc', 'missing'),
        'live-text/ho-04__5e02eb08__2026-10-29.txt': ('document:2026-10-22', 'document:office', 'document:established'),
        'live-text/ho-04__cf961ec4__2026-10-28.txt': ('document:2026-10-22', 'document:office', 'document:established'),
        'live-text/ho-06__c158bce7__2026-10-28.txt': ('document:2026-10-15', 'document:hospital_outpatient', 'missing'),
        'live-text/ho-07__ea3e0e74__2026-10-28.txt': ('document:2026-10-21', 'document:hospital_outpatient', 'missing'),
        'live-text/ho-08__89fc48e5__2026-10-28.txt': ('document:2026-10-13', 'document:hospital_outpatient', 'missing'),
        'live-text/ho-09__03c600f4__2026-10-28.txt': ('document:2026-10-14', 'document:office', 'missing'),
        'live-text/ho-10__c68fb110__2026-10-28.txt': ('document:2026-10-23', 'document:asc', 'missing'),
    }

    def test_every_other_known_text_reads_as_installed(self):
        # this module's own fixture folders; other lenses keep theirs beside them (tests/fixtures/gi3/scope/)
        on_disk = {f'{p.parent.name}/{p.name}' for folder in ('h2', 'ho', 'live-text')
                   for p in (FIXTURES / folder).glob('*.txt')}
        self.assertEqual(on_disk - set(self.UNCHANGED), set(H208))
        for name, (service_date, setting, status) in self.UNCHANGED.items():
            text = fixture(name)
            found = facts(text)
            with self.subTest(text=name):
                self.assertEqual((fact_text(found['service_date']), fact_text(found['setting']),
                                  fact_text(found['patient_status'])), (service_date, setting, status))
                with binding_disabled():
                    before = facts(text)
                self.assertEqual(found, before)


# --- the binding, rule by rule ---------------------------------------------------------------------------------------

class NeutralHeadingTests(DateAsserts, SimpleTestCase):
    """Part 1: a heading the section reader cannot place ends a plan's or a history's reach."""

    def test_neutral_headings_end_the_plan(self):
        for heading in ('Charge information', 'CHARGE  INFORMATION', 'Billing', 'Coding summary', 'Superbill',
                        'Visit details', 'Encounter', "Today's visit", '## Charge information', 'Diagnostic codes'):
            with self.subTest(heading=heading):
                self.assert_conflict(HEADER + 'Assessment and plan\nContinue iron.\n\n' + heading
                                     + '\nDate of service: 2026-10-06\n', '2026-10-05', '2026-10-06')

    def test_a_numbered_sibling_heading_ends_the_plan(self):
        self.assert_conflict(HEADER + '4. Assessment and plan\nContinue iron.\n5. Charge information\n'
                             'Date of service: 2026-10-06\n', '2026-10-05', '2026-10-06')

    def test_a_numbered_item_is_no_heading(self):
        # an earlier date: the history governs it unless a neutral heading ended its reach
        history = HEADER.replace('Subjective\nFollow-up of anemia.\n\n', '') + '4. Interval history\nDoing well.\n'
        self.assert_document(history + '1. Charge information\nDate of service: 2025-03-10\n', '2026-10-05')
        self.assert_conflict(history + '5. Charge information\nDate of service: 2025-03-10\n', '2026-10-05',
                             '2025-03-10')

    def test_headings_naming_another_block_still_govern(self):
        for heading in ('Return visit', 'Next appointment', 'Scheduled procedure', 'Recall', 'Follow-up visit',
                        'Outside records', 'Prior colonoscopy', 'Colonoscopy', 'Labs', 'Results reviewed today',
                        'Transplant evaluation', 'Office visit', 'Surveillance ultrasound'):
            with self.subTest(heading=heading):
                self.assert_document(HEADER + 'Assessment and plan\nContinue iron.\n' + heading
                                     + '\nVisit date: 2026-11-18\n', '2026-10-05')

    def test_a_lower_case_field_under_a_neutral_heading(self):
        self.assert_conflict(HEADER + 'Assessment and plan\nContinue iron.\n\nCharge information\n'
                             'date of service: 2026-10-06\n', '2026-10-05', '2026-10-06')
        # in a history, where no field speaks by itself: the heading still ends the reach (an earlier date, so part 4
        # does not ask it either)
        self.assert_conflict(HEADER.replace('Subjective\nFollow-up of anemia.\n\n', '') + 'Interval history\n'
                             'Doing well.\n\nCoding\ndate of service: 2025-03-10\n', '2026-10-05', '2025-03-10')

    def test_a_heading_continuing_the_line_above_is_no_heading(self):
        history = HEADER.replace('Subjective\nFollow-up of anemia.\n\n', '') + 'Interval history\n'
        self.assert_document(history + 'Doing well and will return to the\nCoding\nDate of service: 2025-03-10\n',
                             '2026-10-05')
        self.assert_conflict(history + 'Doing well and will return.\nCoding\nDate of service: 2025-03-10\n',
                             '2026-10-05', '2025-03-10')

    def test_the_history_reach_ends_too(self):
        self.assert_conflict(HEADER.replace('Subjective\nFollow-up of anemia.\n\n', '') + 'Interval history\n'
                             'Doing well since the last visit.\n\nCoding\nDate of service: 2026-10-06\n\n'
                             'Examination\nAbdomen soft.\n', '2026-10-05', '2026-10-06')


class SettleTests(DateAsserts, SimpleTestCase):
    """A label no section governs any longer speaks, never by itself; 'aside' and 'empty' stay dropped."""

    def test_the_only_label_is_asked_and_its_date_answers(self):
        text = UNDATED + 'Assessment and plan\nContinue iron.\n\nCharge information\nDate of service: 2026-10-06\n'
        self.assertEqual(date_fact(text).origin, 'missing')
        self.assertIsNone(sent(text))
        self.assertEqual(member(text, '2026-10-06'), 'taken')
        self.assertEqual(member(text, STRANGER), 'held')

    def test_another_occurrences_label_stays_dropped(self):
        text = HEADER + 'Assessment and plan\nContinue iron.\n\nCharge information\nNext visit date: 2026-11-16\n'
        self.assert_document(text, '2026-10-05')
        self.assertEqual(member(text, '2026-11-16'), 'held')
        # with no date of the note's own it holds no member's answer either (kept, it would hold every one)
        undated = UNDATED + 'Assessment and plan\nContinue iron.\n\nCharge information\nNext visit date: 2026-11-16\n'
        self.assertEqual((date_fact(undated).origin, date_fact(undated).evidence), ('missing', ()))
        self.assertEqual(member(undated, STRANGER), 'taken')

    def test_an_empty_field_stays_dropped(self):
        text = UNDATED + 'Assessment and plan\nContinue iron.\n\nCharge information\nDate of service: N/A\n'
        self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
        self.assertEqual(member(text, STRANGER), 'taken')


class PlanFieldTests(DateAsserts, SimpleTestCase):
    """Part 2 and B4: fields inside a plan with no block heading."""

    def test_the_encounters_own_field_speaks(self):
        for field in ('Date of service: 2026-10-06', 'DOS: 10/06/2026', 'Encounter date: 2026-10-06',
                      'Service date: 2026-10-06', 'Electronically signed. Date of service: 2026-10-06'):
            with self.subTest(field=field):
                self.assert_conflict(HEADER + 'Assessment and plan\nContinue iron.\n' + field + '\n',
                                     '2026-10-05', '2026-10-06')

    def test_a_visit_or_procedure_field_speaks(self):
        for field in ('Visit date: 2026-10-06', 'Procedure date: 2026-10-06', 'Date of visit: 2026-10-06'):
            with self.subTest(field=field):
                self.assert_conflict(HEADER + 'Assessment and plan\nContinue iron.\n' + field + '\n',
                                     '2026-10-05', '2026-10-06')

    def test_a_later_item_keeps_its_later_date_governed(self):
        for item in ('Follow up in 6 weeks.', 'Return to clinic in 6 weeks.', 'Repeat EGD in 3 months.',
                     'We will see her back after the holidays.'):
            with self.subTest(item=item):
                self.assert_document(HEADER + 'Plan:\n' + item + '\nVisit date: 2026-11-16\n', '2026-10-05')

    def test_after_a_neutral_heading_too(self):
        self.assert_document(HEADER + 'Assessment and plan\nVisit details\nReturn in 6 weeks.\nVisit date: 2026-11-16\n',
                             '2026-10-05')

    def test_a_denied_item_names_no_later_occurrence(self):
        self.assert_conflict(HEADER + 'Assessment and plan\nRepeat colonoscopy is not needed.\nVisit date: 2026-10-06\n',
                             '2026-10-05', '2026-10-06')

    def test_an_earlier_date_is_no_later_occurrences(self):
        self.assert_conflict(HEADER + 'Plan:\nFollow up in 6 weeks.\nVisit date: 2026-09-01\n', '2026-10-05',
                             '2026-09-01')

    def test_with_no_own_date_the_later_item_keeps_it_governed(self):
        text = UNDATED + 'Plan:\nReturn to clinic in 6 weeks.\nVisit date: 2026-11-16\n'
        self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))

    def test_the_plan_heading_is_no_item(self):
        self.assert_conflict(HEADER + 'Plan:\nVisit date: 2026-11-16\n', '2026-10-05', '2026-11-16')

    def test_a_section_naming_an_occurrence_governs_its_fields(self):
        for heading in ('Follow-up:', 'Next appointment:', 'Pending procedures:', 'Referral:'):
            with self.subTest(heading=heading):
                self.assert_document(HEADER + heading + '\nDate of service: 2026-10-06\nVisit date: 2026-10-06\n',
                                     '2026-10-05')

    def test_a_label_in_prose_stays_governed(self):
        self.assert_document(HEADER + 'Plan:\nColonoscopy with polypectomy, procedure date 11/04/2026.\n', '2026-10-05')
        self.assert_document(HEADER + 'Plan:\nLabs on the date of service: normal.\n', '2026-10-05')


class PlannedProcedureTests(DateAsserts, SimpleTestCase):
    """Part 3: a planned procedure's heading after the plan documents nothing (gi2 dates-planned-no-part)."""

    PLANNED = UNDATED + 'Plan:\nColonoscopy with possible polypectomy.\nProcedure: Colonoscopy    Procedure date: 11/04/2026\n'

    def test_its_date_is_asked_never_sent(self):
        # gi3 fix round 2 (interpretation 51(c)(2), dates2-6): a clinic note that documents no procedure has no procedure
        # date of its own, so the planned colonoscopy's date (its "Procedure:" field opens a procedure section, outside
        # the plan) speaks only against the note's own date - with none it is quoted as another occurrence's (_ASKED):
        # never the only answer (part 3 had asked it with its 'plan' doubt, the planned date the only answer a member
        # could give), and the stranger's date held as part 3 held it - never taken
        fact = date_fact(self.PLANNED)
        self.assertEqual(fact.origin, 'missing')
        self.assertIsNone(context.service_date_of(self.PLANNED))
        self.assertEqual(member(self.PLANNED, '2026-11-04'), 'held')
        self.assertEqual(member(self.PLANNED, STRANGER), 'held')
        self.assertIn(context.PLAN_PROC_DATE_NOTE, date_fact(self.PLANNED.replace(
            'Clinic note\n', 'Colonoscopy report\n')).note)  # in a procedure's report, part 3 still asks it

    def test_a_documented_procedure_keeps_its_date(self):
        self.assert_document(UNDATED + 'Plan: proceed.\n\nProcedure: Colonoscopy\nDate of procedure: 2026-10-14\n'
                             '\nFindings:\nA 6 mm polyp was removed with a cold snare.\n', '2026-10-14')


class TimeDirectionTests(DateAsserts, SimpleTestCase):
    """Part 4: a plan date before the visit, or a history date after it, cannot be the section's."""

    def test_a_plan_date_before_the_visit(self):
        self.assert_conflict(HEADER + 'Plan:\nContinue diuretics.\nRecall\nDate of service: 2026-09-01\n',
                             '2026-10-05', '2026-09-01')

    def test_a_history_date_after_the_visit(self):
        self.assert_conflict(HEADER + 'Interval history\nDate of service: 2026-10-06\nDoing well.\n',
                             '2026-10-05', '2026-10-06')

    def test_a_prior_date_in_the_history_stays_governed(self):
        self.assert_document(HEADER + 'Interval history\nDate of service: 2025-03-10\nVariceal screening.\n', '2026-10-05')


class BrokenLabelTests(DateAsserts, SimpleTestCase):
    """X3: the encounter's own date-of-service label broken over one line break."""

    def test_each_break_reads(self):
        for label in ('Date of\nservice: 2026-10-06', 'Date\nof service: 2026-10-06', 'Service\ndate: 2026-10-06',
                      'Encounter\ndate: 2026-10-06', 'Date of\nService - 2026-10-06'):
            with self.subTest(label=label):
                self.assert_conflict(HEADER + 'Assessment and plan\nContinue iron.\n\nCharge information\n' + label + '\n',
                                     '2026-10-05', '2026-10-06')

    def test_never_by_itself(self):
        text = UNDATED + 'Charge information:\nDate of\nservice: 2026-10-06\n'
        self.assertEqual(date_fact(text).origin, 'missing')
        self.assertEqual(member(text, '2026-10-06'), 'taken')
        self.assertEqual(member(text, STRANGER), 'held')

    def test_never_joined_to_prose(self):
        for tail in ('We will confirm the\nDate of\nservice: 2026-10-06\n', 'We discussed the date of\nservice: 2026-10-06\n',
                     'Charge information Date of\nservice: 2026-10-06\n'):
            with self.subTest(tail=tail[:24]):
                self.assert_document(HEADER + 'Charge information:\nItems below.\n' + tail, '2026-10-05')

    def test_the_separator_is_required(self):
        self.assert_document(HEADER + 'Charge information:\nDate of\nservice 2026-10-06\n', '2026-10-05')


class TitleTests(SimpleTestCase):
    """RC5: a plan section the document's own follow-up title opens governs no label."""

    TITLED = (BANNER + 'Synthetic GI clinic (fictional)\n{title}\nPatient: Synthetic Patient (fictional)\n'
              'Visit date: 2026-10-21\nPlace of service: office (POS 11)\nPatient status: established\nInterval history\n'
              'Doing well.\nPlan\nContinue.\n')

    def read(self, title):
        found = facts(self.TITLED.format(title=title))
        return tuple(fact_text(found[name]) for name in ('service_date', 'setting', 'patient_status'))

    def test_a_follow_up_title_is_no_plan(self):
        for title in ('GI clinic follow-up', 'Hepatology follow-up', 'Liver clinic follow up', 'Office follow-up',
                      'Post-procedure follow-up'):
            with self.subTest(title=title):
                self.assertEqual(self.read(title), ('document:2026-10-21', 'document:office', 'document:established'))

    def test_the_scope_investigations_a08_and_a17(self):
        rows = {row['id']: row for row in corpus_rows()}
        for name, status in (('RC5-A08', 'document:established'), ('RC5-A17', 'missing')):
            with self.subTest(row=name):
                found = facts(rows[name]['text'])
                self.assertEqual((fact_text(found['service_date']), fact_text(found['setting']),
                                  fact_text(found['patient_status'])), ('document:2026-10-21', 'document:office', status))

    def test_other_titles_still_govern(self):
        for title in ('Follow-up', 'Next follow-up', 'Scheduled follow-up', 'Hepatology follow-up:',
                      'Bowel prep instructions', 'Past endoscopic history', 'Follow-up and management'):
            with self.subTest(title=title):
                self.assertEqual(self.read(title)[0], 'missing')

    def test_only_the_documents_first_heading_in_its_head(self):
        late = BANNER + ''.join(f'Line {n}\n' for n in range(12)) + 'Hepatology follow-up\nVisit date: 2026-10-21\n'
        second = BANNER + 'Indication: anemia\nHepatology follow-up\nVisit date: 2026-11-21\n'
        for text in (late, second):
            with self.subTest(text=text[-40:]):
                self.assertEqual(date_fact(text).origin, 'missing')


class SettingStatusTests(SimpleTestCase):
    """RC6: the setting and patient-status readers share the binding."""

    def test_a_charge_blocks_place_of_service_speaks(self):
        found = facts(HEADER + 'Assessment and plan\nContinue.\n\nCharge information\nPlace of service: 22\n')
        self.assertEqual(found['setting'].origin, 'conflict')
        self.assertEqual(set(context.documented_values(found['setting'])), {'office', 'hospital_outpatient'})

    def test_a_charge_blocks_status_speaks(self):
        found = facts(HEADER + 'Assessment and plan\nContinue.\n\nCharge information\nPatient status: new\n')
        self.assertEqual(found['patient_status'].origin, 'conflict')

    def test_never_by_itself(self):
        found = facts(UNDATED.replace('Place of service: office (POS 11)\n', '').replace('Established patient\n', '')
                      + 'Assessment and plan\nContinue.\n\nCharge information\nPlace of service: 22\nPatient status: new\n')
        self.assertEqual((found['setting'].origin, found['setting'].evidence), ('missing', ()))
        self.assertEqual((found['patient_status'].origin, found['patient_status'].evidence), ('missing', ()))

    def test_the_plan_still_governs(self):
        found = facts(HEADER + 'Plan:\nReturn as a new patient to hepatology.\nPatient status: new\nPlace of service: 22\n')
        self.assertEqual(fact_text(found['patient_status']), 'document:established')
        self.assertEqual(fact_text(found['setting']), 'document:office')

    def test_a_history_status_is_read_as_before(self):
        found = facts(UNDATED.replace('Established patient\n', '') + 'Interval history\nEstablished patient, doing well.\n')
        self.assertEqual(fact_text(found['patient_status']), 'document:established')


class RuleUTests(SimpleTestCase):
    """Rule U beside a label the history no longer governs: a candidate a plan or history section holds is read only
    to be asked, so it never keeps an outside header the note's own."""

    def test_the_addendums_date_is_still_asked(self):
        rows = {row['id']: row for row in corpus_rows()}
        text = rows['R-ruleU']['text']
        self.assertIsNone(sent(text))
        with binding_disabled():
            self.assertIsNone(sent(text))


# --- the invariant ---------------------------------------------------------------------------------------------------

# The stress cross-product of the date investigation (5 headers x 15 sections x 8 lines between x 23 block headings x 15
# label forms x plain or PDF lines), with this repair's B4 items and X3 label: a seeded sample of it.
STRESS_HEADERS = {'none': '', 'same': 'Date of service: 2026-10-05\n', 'diff': 'Date of service: 2026-10-05\n',
                  'visit': 'Visit date: 10/05/2026\n', 'unread': 'Date of service: 05-Oct-26\n'}
STRESS_SECTIONS = ('Plan:', 'Assessment and plan', 'Recommendations:', 'Follow-up:', 'Discussion:', 'Next procedures:',
                   'Planned procedures', 'Patient education', 'History:', 'Past medical history:', 'Interval history',
                   'Prior procedures:', 'Social history:', 'Impression:', 'Findings:')
STRESS_BETWEEN = ('', 'Continue current therapy and return as needed.\n', 'Colonoscopy with possible polypectomy.\n',
                  'Physician time on the service date: 30 minutes, including counseling.\n', '\n', 'Repeat EGD in 3 months.\n',
                  'Return to clinic in 6 weeks.\n', 'Repeat EGD is not needed.\n')
STRESS_BLOCKS = ('', 'Charge information', 'Billing', 'Visit details', 'Encounter summary', 'Coding', 'Superbill',
                 'Return visit', 'Recall', 'Follow-up visit', 'Next appointment', 'Scheduled procedure', 'Outside records',
                 'Prior colonoscopy', 'Colonoscopy', 'Upper endoscopy', 'Results reviewed today', 'Labs',
                 'Transplant evaluation', 'Signature', 'Charge information:', "Today's visit", 'Office visit')
STRESS_LABELS = ('Date of service: {d}', 'DOS: {u}', 'Visit date: {d}', 'Procedure date: {u}', 'Encounter date: {d}',
                 'Service date: {u}', 'Date of procedure: {l}', 'Date of service | {d}', 'Date of service:\n{d}',
                 'Date of service: N/A', 'Date of service: 06-Oct-26', 'Next visit date: {d}',
                 'Date of service: {d} (pending)', 'Test | Date of service | Result\nFerritin | {d} | 41 ng/mL',
                 'Date of\nservice: {d}')


def _pdf(text: str, width: int = 90) -> str:
    import textwrap
    out = []
    for line in text.split('\n'):
        if line.strip():
            out.extend(textwrap.wrap(line, width=width, break_long_words=False, break_on_hyphens=False) or [line])
    return '\n'.join(out) + '\n'


def stress_sample(count: int, seed: int = 20261029):
    rng = random.Random(seed)
    for _ in range(count):
        header = rng.choice(sorted(STRESS_HEADERS))
        same = header == 'same'
        d, u, l = (('2026-10-05', '10/05/2026', 'October 5, 2026') if same
                   else ('2026-10-06', '10/06/2026', 'October 6, 2026'))
        block = rng.choice(STRESS_BLOCKS)
        between = rng.choice(STRESS_BETWEEN)
        text = (BANNER + 'Synthetic GI clinic (fictional)\nPatient: Synthetic Patient (fictional)\n' + STRESS_HEADERS[header]
                + 'Reason for visit\nFollow-up of iron deficiency anemia.\n\n' + rng.choice(STRESS_SECTIONS) + '\n'
                + between + (block + '\n' if block else '') + rng.choice(STRESS_LABELS).format(d=d, u=u, l=l) + '\n'
                + 'Electronically signed: Synthetic Physician, MD (fictional)\n')
        yield _pdf(text) if rng.random() < 0.2 else text


class InvariantTests(SimpleTestCase):
    """Outside a follow-up title's section the repair only ever asks: it never sends a date the installed reading does
    not send, nor documents a setting or a patient status it does not."""

    def test_never_a_date_or_setting_the_installed_reading_does_not_give(self):
        texts = list(stress_sample(600))
        repaired = []
        for text in texts:
            found = facts(text)
            repaired.append({name: (fact.origin, fact.value) for name, fact in found.items()})
        with binding_disabled():
            installed = [{name: (fact.origin, fact.value) for name, fact in facts(text).items()} for text in texts]
        moved = 0
        for text, new, old in zip(texts, repaired, installed):
            moved += new != old
            for name in ('service_date', 'setting', 'patient_status'):
                if new[name][0] == 'document':
                    self.assertEqual(old[name], new[name], (name, text))
        self.assertGreater(moved, 60)  # the sample reaches the repair: many readings move (each to a question)


# --- cost ------------------------------------------------------------------------------------------------------------

def _fill(size: int, prefix: str, unit: str, suffix: str = '') -> str:
    return prefix + unit * ((size - len(prefix) - len(suffix)) // len(unit)) + suffix


COST_HEAD = BANNER + 'Date of service: 2026-10-05\n'
COST_SHAPES = {  # the investigation's cap-size pastes and the repair's own (B4, X3, RC5, RC6)
    'plan + (neutral heading, DOS) x N': (COST_HEAD + 'Plan:\n', 'Billing\nDOS: 10/06/2026\n'),
    'plan + neutral headings x N, one DOS': (COST_HEAD + 'Plan:\n', 'Visit details\n', 'DOS: 10/06/2026\n'),
    'plan + DOS x N': (COST_HEAD + 'Assessment and plan\n', 'Date of service: 2026-10-06\n'),
    'history + (neutral heading, DOS) x N': (COST_HEAD + 'Past medical history:\n', 'Coding\nDOS: 10/06/2026\n'),
    'plan + bare label lines x N': (COST_HEAD + 'Plan:\n', 'Diet change\n'),
    'one long plan line of DOS': (COST_HEAD + 'Plan:\n', 'Charge information | DOS: 10/06/2026 | '),
    '4. A&P + numbered siblings x N': (COST_HEAD + '4. Assessment and plan\nContinue.\n', '5. Charge information\nDOS: 10/06/2026\n'),
    'plan + (later item, Visit date) x N': (COST_HEAD + 'Plan:\n', 'Return to clinic in 6 weeks.\nVisit date: 2026-11-16\n'),
    'plan + (blanks, Visit date) x N': (COST_HEAD + 'Plan:\nReturn in 6 weeks.\n', '\n\n\nVisit date: 2026-11-16\n'),
    'plan + broken label x N': (COST_HEAD + 'Plan:\nBilling\n', 'Date of\nservice: 2026-10-06\n'),
    'plan + (neutral heading, POS 22) x N': (COST_HEAD + 'Place of service: 11\nPlan:\n', 'Billing\nPlace of service: 22\n'),
    'title + header x N': (BANNER + 'GI clinic follow-up\n', 'Visit date: 2026-10-21\nPlace of service: 11\n'),
}


def _process_seconds(text: str) -> float:
    context.layout.cache_clear()
    for cached in (context._context, context._governance, context._title_start, context.find_dates,
                   context._date_starts):
        cached.cache_clear()
    started = time.process_time()
    context.extract_context(text)
    return time.process_time() - started


class CostTests(SimpleTestCase):
    """The binding reads each line once and every label bisects (refutation phase 2's cost rule)."""

    def test_the_reading_grows_linearly(self):
        for name, shape in COST_SHAPES.items():
            small, large = (_process_seconds(_fill(size, *shape)) for size in (25_000, 100_000))
            with self.subTest(shape=name):
                self.assertLess(large, 8 * max(small, 0.02))  # four times the text: about 4x, 16x if quadratic

    def test_cap_size_pastes_fit_a_members_context_request(self):
        for name in ('plan + (neutral heading, DOS) x N', 'plan + (blanks, Visit date) x N', 'plan + broken label x N'):
            with self.subTest(shape=name):
                self.assertLess(_process_seconds(_fill(400_000, *COST_SHAPES[name])), 15.0)  # measured at most 2.6 s
