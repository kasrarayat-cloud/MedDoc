"""GI round 3, fix round 2 (session 7c8d38da, 2026-10-30), fix owner "dates": the second independent refutation of the
integrated candidate b6997c39d found the date binding wrong by the source in ten shapes (dates2-1 to dates2-10) and two
quadratic patterns of the integration's own code (cost-r2-1, cost-r2-2). Interpretation 51(c) binds the fixes - an
uncertain binding asks: a date is never sent, never dropped so that another is sent, and never the only answer
(studio/gi/context.py, "gi3 fix round 2"):
- 51(c)(1), dates2-2, dates2-3, dates2-7, dates2-8: the encounter's own date-of-service label is never dropped by its
  surroundings - under any block heading, joined to one on its line, or in a table it speaks against the note's own
  date, unless a heading of the closed class names another occurrence explicitly ("Next appointment", "Prior visit",
  h2-07's "Results reviewed today"); no list of kinds of service or CPT code is needed any more (H1 and 48(f) are gone);
- 51(c)(2) and (3), dates2-1, dates2-4, dates2-5, dates2-10: the title's section has a head, read as an untitled header
  reads it - the title never its qualifier - and past its first clinical line, or a stacked heading that does not name
  this visit positively, the plan rules govern;
- 51(c)(2), dates2-6: a procedure date is never the own date of a note that documents no procedure, and B4 reads the
  plan item or statement before a visit date past the section headings between them;
- 51(c)(3), dates2-9: a label's separator is any short run of punctuation and blanks, and its words may be joined by any
  horizontal blank; only the installed revision's own forms are ever sent by themselves;
- cost-r2-1, cost-r2-2: the head is one pass over the section's lines, and the CPT pattern is gone.
The fix owner's self-attack (header and layout variants of every input, run against the installed revision) found six
shapes where these rules themselves sent a date the installed revision asked, or left a planned or results date the
only answer; each is pinned beside the rule it corrects ("self-attack" in the test's comment).

The expected answers live outside the reader: tests/fixtures/gi3/fix2-dates/cases.json holds the reviewer's inputs
(texts copied verbatim) and the fix owner's own shapes beside each finding, each with its source-reviewed expectation;
variants.json holds the reviewer's variant batches, read here by their family's rule. Synthetic text only; pure
functions - no database, no provider, no network.
"""
import json
import time
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context
from studio.gi.sections import layout
from tests.test_repairs_gi3_dates import BANNER, STRANGER, binding_disabled, date_fact, fact_text, facts, member, sent
from tests.test_repairs_gi3_integration import run

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi3' / 'fix2-dates'
LETTERHEAD = 'Northgate Gastroenterology (fictional)\n'
PATIENT = 'Patient: Ivo Brandmere (fictional)\n'
HISTORY = 'Interval history:\nDoing well on mesalamine. No rectal bleeding.\nAssessment:\nUlcerative colitis in remission.\n'


def cases() -> dict:
    return {case['id']: case for case in json.loads((FIXTURES / 'cases.json').read_text(encoding='utf-8'))['cases']}


def variants() -> list:
    return json.loads((FIXTURES / 'variants.json').read_text(encoding='utf-8'))['rows']


def follow_up(title: str, body: str) -> str:
    return BANNER + LETTERHEAD + title + '\n' + body


def answers(text: str, probes) -> dict:
    return {p: member(text, p) for p in probes}


class CaseAsserts:
    def assert_case(self, case):
        """The case's source-reviewed expectation: 'document' - that date is sent, a stranger's held; 'conflict' - no
        date is sent, each listed date is a member's answer that is taken, a stranger's held; 'asked' - no date is sent,
        each date in ``taken`` is taken, each in ``held`` held, and a date in ``never`` is never sent and never the only
        answer a member may give (when it is taken, so is a date the document never states)."""
        text, expected = case['text'], case['expected']
        found = facts(text)
        fact = found['service_date']
        kind = expected['kind']
        if kind == 'document':
            self.assertEqual((fact.origin, fact.value), ('document', expected['value']), [e.text for e in fact.evidence])
            self.assertEqual(member(text, STRANGER), 'held')
        elif kind == 'conflict':
            self.assertEqual(fact.origin, 'conflict', [e.text for e in fact.evidence])
            self.assertIsNone(sent(text))
            for value in expected['values']:
                self.assertEqual(member(text, value), 'taken', value)
        else:
            self.assertIsNone(sent(text), fact.value)
            for value in expected.get('taken', ()):
                self.assertEqual(member(text, value), 'taken', value)
            for value in expected.get('never', ()):
                if member(text, value) == 'taken':  # then some other date is an answer too: never the only one
                    others = {d.isoformat() for d in (context.date_from_match(m) for m in context.FULL_DATE.finditer(text))
                              if d} | {STRANGER}
                    self.assertTrue(any(member(text, other) == 'taken' for other in others - {value}),
                                    f'{value} is the only answer')
        for value in expected.get('held', ()):
            self.assertEqual(member(text, value), 'held', value)
        for name in ('setting', 'patient_status'):
            if name in expected:
                self.assertEqual(fact_text(found[name]), expected[name], name)

    def assert_cases(self, *ids):
        known = cases()
        for name in ids:
            with self.subTest(case=name):
                self.assert_case(known[name])


class FixtureTests(CaseAsserts, SimpleTestCase):
    def test_every_case_reads_right_by_its_source(self):
        known = cases()
        self.assertEqual(len(known), 90)
        for name, case in known.items():
            self.assertTrue(case['text'].startswith(BANNER), name)
            self.assertGreater(len(case['review']), 30, name)
            with self.subTest(case=name):
                self.assert_case(case)


class TitleHeadTests(CaseAsserts, SimpleTestCase):
    """dates2-1, dates2-4, dates2-5, dates2-10 (51(c)(2) and (3)): the head of the section the document's own follow-up
    title opens is read as an untitled header reads it; past its first clinical line the plan rules govern."""

    def test_the_header_under_the_title_is_never_lost(self):
        self.assert_cases('F1a', 'F1b', 'F1c', 'F1d', 's1-hep-dos', 's1-ibd-encounter-last', 's1-table-dob-dos',
                          's1-lower-label', 's1-blank-between', 's1-visit-type-field', 's1-next-only')

    def test_the_title_never_qualifies_the_label_under_it(self):
        text = follow_up('GI clinic follow-up', 'Visit date: 2026-10-21\n' + PATIENT + HISTORY)
        self.assertEqual((date_fact(text).origin, date_fact(text).value), ('document', '2026-10-21'))
        start = text.index('Visit date')
        self.assertEqual(context._line_above(text, start), context._title_line(text))
        self.assertTrue(context._governance(text).in_head(start))

    def test_a_clinical_line_ends_the_head(self):
        self.assert_cases('F5a', 'F5b', 'F5c', 's4-liver-will-see', 's4-soap-nostop', 's4-prose-nostop', 's4-phone-proc',
                          's4-dos-after-plan')
        text = follow_up('GI clinic follow-up', PATIENT + 'Doing well on mesalamine.\nVisit date: 01/05/2027\n')
        self.assertFalse(context._governance(text).in_head(text.index('Visit date')))

    def test_a_stacked_heading_names_this_visit_only_positively(self):
        self.assert_cases('F9a', 'F9-ctrl', 's5-initial-direct', 's5-first-clinic-dos', 's5-consultation',
                          's5-new-patient-visit', 's5-ctrl-office-visit')
        for stacked in ('Office visit', 'Clinic note - return visit', 'Return visit note', 'Office follow-up visit',
                        "Today's visit"):
            text = follow_up('Gastroenterology follow-up', stacked + '\nDate of service: 2026-10-21\n' + HISTORY)
            with self.subTest(stacked=stacked):
                self.assertEqual(sent(text), '2026-10-21')
        for stacked in ('Initial office visit', 'Baseline clinic visit', 'Original clinic visit', 'Referral clinic visit',
                        'Last office visit', 'First follow-up visit'):
            text = follow_up('Gastroenterology follow-up', stacked + '\nDate of service: 2026-06-01\n' + HISTORY)
            with self.subTest(stacked=stacked):
                self.assertIsNone(sent(text))
                self.assertEqual(member(text, STRANGER), 'taken')  # never the only answer

    def test_the_setting_is_read_only_from_the_head_and_never_from_another_occurrence(self):
        self.assert_cases('F8a', 'F8b', 's10-hopd-sentence', 's10-location-next', 's10-asc-planned-field',
                          's10-ctrl-site-pos')

    def test_a_title_in_the_head_speaks_only_against_the_heads_labelled_date(self):
        # self-attack: a stacked dated title its words do not qualify ("Return visit: 01/05/2027") read as the head's
        # titled heading was the only answer when the head labels no date of its own; the installed reading read none
        # of the section, so it is dropped there - and beside the head's own label it agrees or is asked, as an untitled
        # header's is
        for line, value in (('Return visit: 01/05/2027', '2027-01-05'), ('Office visit - 01/05/2027', '2027-01-05'),
                            ('Date: 10/07/2026', '2026-10-07'), ('Re: clinic visit 10/07/2026', '2026-10-07')):
            alone = follow_up('GI clinic follow-up', PATIENT + line + '\n' + HISTORY)
            with self.subTest(line=line, header=False):
                self.assertIsNone(sent(alone))
                self.assertEqual(answers(alone, (value, '2026-10-05')), {value: 'taken', '2026-10-05': 'taken'})
            beside = follow_up('GI clinic follow-up', 'Date of service: 10/05/2026\n' + PATIENT + line + '\n' + HISTORY)
            with self.subTest(line=line, header=True):
                self.assertIsNone(sent(beside))
                self.assertEqual(answers(beside, (value, '2026-10-05', STRANGER)),
                                 {value: 'taken', '2026-10-05': 'taken', STRANGER: 'held'})
        agrees = follow_up('GI clinic follow-up', 'Date of service: 10/05/2026\n' + PATIENT + 'Office visit - 10/05/2026\n'
                           + HISTORY)
        self.assertEqual(sent(agrees), '2026-10-05')
        for qualified in ('Next visit: 01/05/2027', 'Last visit: 08/27/2026'):  # another occurrence's: never read
            text = follow_up('GI clinic follow-up', 'Date of service: 10/05/2026\n' + PATIENT + qualified + '\n' + HISTORY)
            with self.subTest(qualified=qualified):
                self.assertEqual(sent(text), '2026-10-05')

    def test_a_qualified_stacked_title_in_the_head_is_asked_never_dropped(self):
        # mutation proof M26: the head reads a stacked "Follow-up visit - 01/05/2027" under "GI clinic follow-up" as this
        # visit's title, whatever its follow-up qualifier says - so beside the header's date it is asked, and with no
        # labelled date it is dropped; skipped as another occurrence's, the header's date was sent over it
        for line in ('Follow-up visit - 01/05/2027', 'Follow-up visit 01/05/2027'):
            beside = follow_up('GI clinic follow-up', 'Date of service: 10/05/2026\n' + PATIENT + line + '\n' + HISTORY)
            alone = follow_up('GI clinic follow-up', PATIENT + line + '\n' + HISTORY)
            with self.subTest(line=line):
                self.assertEqual(date_fact(beside).origin, 'conflict')
                self.assertEqual(answers(beside, ('2026-10-05', '2027-01-05', STRANGER)),
                                 {'2026-10-05': 'taken', '2027-01-05': 'taken', STRANGER: 'held'})
                self.assertEqual(answers(alone, ('2027-01-05', STRANGER)), {'2027-01-05': 'taken', STRANGER: 'taken'})

    def test_a_head_label_its_own_words_qualify_is_never_the_only_answer(self):
        # mutation proof M27: "Next DOS", "Initial visit DOS", "Prior service date" in the head name another occurrence
        # by their own words: with no labelled date of the note's own they are dropped, never the only answer
        for line in ('Next DOS: 01/05/2027', 'Initial visit DOS: 06/01/2026', 'Prior service date: 06/01/2026'):
            text = follow_up('GI clinic follow-up', PATIENT + line + '\n' + HISTORY)
            value = '2027-01-05' if '2027' in line else '2026-06-01'
            with self.subTest(line=line):
                self.assertIsNone(sent(text))
                self.assertEqual(answers(text, (value, STRANGER)), {value: 'taken', STRANGER: 'taken'})

    def test_a_row_of_cells_in_the_head_is_a_table_whatever_the_table_model_reads(self):
        # self-attack: a results table whose rows blank lines (or a PDF wrap) separate is no table to the table model,
        # so its column label read as the head's own and the results' date was the only answer; its row's own cells say
        # it is a column (_Governance.column_label), and only the patient's header table is read as the head's
        for spacing in ('\n', '\n\n'):
            text = follow_up('Hepatology follow-up', PATIENT + spacing.join(
                ('Test | Date of service | Result', 'ALT | 2026-09-30 | 41 U/L', 'AST | 2026-09-30 | 38 U/L')) + '\n'
                + HISTORY)
            with self.subTest(spacing=repr(spacing)):
                self.assertIsNone(sent(text))
                self.assertEqual(answers(text, ('2026-09-30', STRANGER)), {'2026-09-30': 'taken', STRANGER: 'taken'})
            header = follow_up('GI clinic follow-up', spacing.join(
                ('Patient | Date of birth | Visit date | Provider',
                 'Ivo Brandmere (fictional) | 1961-03-14 | 10/05/2026 | Priya Halvorsen-Mbeki, MD (fictional)')) + '\n'
                + HISTORY)
            with self.subTest(spacing=repr(spacing), table='patient header'):
                self.assertEqual(answers(header, ('2026-10-05', STRANGER)), {'2026-10-05': 'taken', STRANGER: 'held'})

    def test_a_follow_up_title_names_a_visit_never_a_procedure(self):
        text = follow_up('GI clinic follow-up', PATIENT + 'Procedure date: 11/04/2026\n' + HISTORY)
        self.assertIsNone(sent(text))
        self.assertEqual(member(text, STRANGER), 'taken')

    def test_a_results_table_under_the_title_is_never_the_only_answer(self):
        text = follow_up('Hepatology follow-up', PATIENT + 'Test | Date of service | Result\nALT | 2026-09-30 | 41 U/L\n'
                         'AST | 2026-09-30 | 38 U/L\n' + HISTORY)
        self.assertIsNone(sent(text))
        self.assertEqual(member(text, STRANGER), 'taken')


class EncounterLabelTests(CaseAsserts, SimpleTestCase):
    """dates2-2, dates2-3, dates2-7, dates2-8 (51(c)(1)): the encounter's own label speaks wherever it stands."""

    def test_the_reviewers_shapes(self):
        self.assert_cases('F2a', 'F2b', 'F2c', 'F2-ctrl', 'F3a', 'F3-ctrl', 'F4a', 'F4b', 'F4c', 'F4-ctrl', 'F7a', 'F7b',
                          'F7c', 'F7-ctrl')

    def test_the_fix_owners_shapes(self):
        self.assert_cases('s2-appt-today', 's2-sched-billing-dos', 's2-history-med-schedule', 's2-x3-broken',
                          's2-ctrl-next-appt', 's3-cpt-dos-units', 's3-history-table', 's3-pdf-wrapped-row',
                          's3-ctrl-results-reviewed', 's7-return-level3', 's7-code-on-line', 's7-report-biopsy-hcpcs',
                          's7-ctrl-prior-visit', 's7-ctrl-prior-visit-later', 's8-emdash', 's8-bracket-dos',
                          's8-after-next-steps', 's8-ctrl-next-appt-joined')

    def test_only_the_closed_class_names_another_occurrence_explicitly(self):
        for words in ('Next appointment', 'Prior visit', 'Scheduled procedure', 'Outside records',
                      'History of present illness', 'Results reviewed today', 'Seen 3 weeks ago'):
            with self.subTest(words=words):
                self.assertTrue(context._names_occurrence_explicitly(words, 0, len(words)))
        for words in ("Today's appointment", 'Billing and scheduling', 'Taper schedule', 'Follow-up visit, level 4',
                      'Return visit', 'Recall', 'Labs', 'Results', 'Pathology', 'Assessment and plan', 'Charge information'):
            with self.subTest(words=words):
                self.assertFalse(context._names_occurrence_explicitly(words, 0, len(words)))

    def test_with_no_own_date_the_label_is_never_the_only_answer_where_it_only_speaks_against_it(self):
        head = BANNER + 'Clinic note\n' + PATIENT + 'Assessment and plan\nStable. Return in 4 weeks.\n'
        for block in ("Today's appointment\nDate of service: 2026-10-06\n", 'CPT | DOS\n99214 | 2026-10-06\n',
                      'Charges — Date of Service: 2026-10-06\n'):
            text = head + block
            with self.subTest(block=block):
                self.assertEqual(date_fact(text).origin, 'missing')
                self.assertEqual(member(text, STRANGER), 'taken')

    def test_a_block_heading_naming_today(self):
        # mutation proof M23: "Today's visit" names this visit's block, so the encounter's own label under it speaks - with
        # no other date its date is the answer - and a visit date under it speaks against the header's date (asked);
        # read as another block, the visit date was dropped and the header's contradicted date sent
        plan = BANNER + LETTERHEAD + 'Clinic note\n' + PATIENT + '{own}Assessment and plan\nStable.\n'
        alone = plan.format(own='') + "Today's visit\nDate of service: 10/06/2026\n"
        self.assertEqual(answers(alone, ('2026-10-06', STRANGER)), {'2026-10-06': 'taken', STRANGER: 'held'})
        text = plan.format(own='Date of service: 10/05/2026\n') + "Today's visit\nVisit date: 10/06/2026\n"
        self.assertEqual(date_fact(text).origin, 'conflict')
        self.assertEqual(answers(text, ('2026-10-05', '2026-10-06')), {'2026-10-05': 'taken', '2026-10-06': 'taken'})

    def test_a_visits_own_title_heads_that_visits_block(self):
        # mutation proof M24 (dates2-5): "Initial clinic note" as a block heading heads the initial visit's block, so the
        # encounter's own label under it is never the only answer with no date of the note's own (read as a neutral
        # heading, the earlier visit's date was the only answer a member could give)
        for heading in ('Initial clinic note', 'Baseline clinic visit'):
            text = (BANNER + LETTERHEAD + 'Clinic note\n' + PATIENT + 'Plan:\nContinue.\n' + heading
                    + '\nDate of service: 06/01/2026\n')
            with self.subTest(heading=heading):
                self.assertIsNone(sent(text))
                self.assertEqual(answers(text, ('2026-06-01', STRANGER)), {'2026-06-01': 'taken', STRANGER: 'taken'})

    def test_h2_08_stays_a_conflict(self):
        for name in ('live-text/h2-08__e084b793__2026-10-29.txt', 'h2/h2-08-hepatology-note.txt'):
            text = (Path(__file__).resolve().parent / 'fixtures' / 'gi3' / name).read_text(encoding='utf-8')
            with self.subTest(text=name):
                self.assertEqual(date_fact(text).origin, 'conflict')
                self.assertEqual(answers(text, ('2026-10-05', '2026-10-06', STRANGER)),
                                 {'2026-10-05': 'taken', '2026-10-06': 'taken', STRANGER: 'held'})


class VisitNoteTests(CaseAsserts, SimpleTestCase):
    """dates2-6 (51(c)(2)): a procedure date is never the own date of a note that documents no procedure, and B4 reads
    the plan item or statement before a visit date past the section headings between them."""

    def test_the_reviewers_shapes(self):
        self.assert_cases('F10a', 'F10b', 'F10-ctrl')

    def test_the_fix_owners_shapes(self):
        self.assert_cases('s6-progress-sedation', 's6-consent-dateofproc', 's6-meds-visit', 's6-header-proc-date',
                          's6-ctrl-documented', 's6-ctrl-own-dos')

    def test_a_documented_procedure_or_a_report_keeps_its_procedure_date(self):
        self.assertFalse(context._visit_note(cases()['s6-ctrl-documented']['text']))
        report = BANNER + 'Colonoscopy report\n' + PATIENT + 'Procedure date: 10/14/2026\nFindings: Normal colon.\n'
        self.assertFalse(context._visit_note(report))
        self.assertEqual(sent(report), '2026-10-14')
        self.assertTrue(context._visit_note(cases()['F10a']['text']))

    def test_b4_reads_past_a_section_heading_never_past_a_block_heading(self):
        for heading in ('Bowel preparation', 'Procedure details', 'Sedation'):  # headings the section reader knows
            for header in ('Date of service: 10/05/2026\n', ''):
                text = (BANNER + 'Clinic note\n' + PATIENT + header + 'Plan:\nReturn to clinic in 6 weeks.\n' + heading
                        + '\nVisit date: 11/16/2026\n')
                with self.subTest(heading=heading, header=bool(header)):
                    self.assertIsNone(sent(text))  # never the booked visit's date (the installed revision sent it)
                    if header:
                        # outside the plan section it speaks against the header's date: asked, as the installed
                        # revision asked - never dropped so that the header's date is sent (51(c)(1))
                        self.assertEqual(date_fact(text).origin, 'conflict')
                    else:  # never the only answer, and every other answer held as the installed revision held it
                        self.assertEqual(answers(text, ('2026-11-16', '2026-10-05', STRANGER)),
                                         {'2026-11-16': 'held', '2026-10-05': 'held', STRANGER: 'held'})
        # a neutral block heading ends the plan's reach (interpretation 42): the report's own billing block still speaks
        report = cases()['s7-report-biopsy-hcpcs']['text']
        self.assertEqual(date_fact(report).origin, 'conflict')

    def test_b4_reads_past_a_section_heading_in_a_report_too(self):
        # mutation proof M8 survived the visit-note shapes (there the visit date after the plan asks by itself): in a
        # procedure's report only B4 reading past the heading keeps the booked clinic visit's date from being sent (the
        # installed revision and the candidate sent 11/16)
        body = ('Findings:\nThe colonoscope was advanced to the cecum. A 5 mm polyp in the sigmoid colon was removed with '
                'a cold snare.\nRecommendations:\nReturn to clinic in 6 weeks.\n')
        for heading in ('Bowel preparation', 'Procedure details', 'Sedation'):
            text = BANNER + 'Colonoscopy report\n' + PATIENT + body + heading + '\nVisit date: 11/16/2026\n'
            with self.subTest(heading=heading):
                self.assertIsNone(sent(text))
                # with no date of the report's own the booked visit's date is quoted as another occurrence's: never an
                # answer, and no other answer taken (the installed revision held them beside its date, _ASKED)
                self.assertEqual(answers(text, ('2026-11-16', STRANGER)), {'2026-11-16': 'held', STRANGER: 'held'})
                own = text.replace(PATIENT, PATIENT + 'Date of service: 10/14/2026\n')
                self.assertEqual(date_fact(own).origin, 'conflict')  # beside the report's own date: asked, as installed

    def test_outside_a_plan_a_later_date_is_never_dropped_so_the_own_date_is_sent(self):
        # B4's drop is the installed reading's own inside a plan section; outside one the installed reading read the
        # label, so a later date after a later item or statement speaks against the header's date: a conflict, as
        # installed (51(c)(1)) - an earlier or equal date reads as before
        own = 'Date of service: 10/05/2026\n'
        shapes = {
            'findings': (LETTERHEAD + PATIENT + own + 'Findings:\nRepeat EGD in 3 months.\nVisit date: 10/06/2026\n',
                         ('2026-10-05', '2026-10-06')),
            'statement': (LETTERHEAD + 'Clinic note\n' + PATIENT + own + 'Return to clinic in 3 months.\n'
                          'Visit date: 01/05/2027\n' + HISTORY, ('2026-10-05', '2027-01-05')),
            'after the plan': (LETTERHEAD + 'Clinic note\n' + PATIENT + own + 'Plan:\nReturn in 6 weeks.\nMedications\n'
                               'Continue iron.\nVisit date: 11/16/2026\n', ('2026-10-05', '2026-11-16')),
            'procedure': (LETTERHEAD + 'Clinic note\n' + PATIENT + own + 'Plan:\nColonoscopy with possible polypectomy.\n'
                          'Bowel preparation\nProcedure date: 11/04/2026\n', ('2026-10-05', '2026-11-04')),
            'earlier': (LETTERHEAD + PATIENT + own + 'Findings:\nRepeat EGD in 3 months.\nVisit date: 09/01/2026\n',
                        ('2026-10-05', '2026-09-01')),
        }
        for name, (body, values) in shapes.items():
            text = BANNER + body
            with self.subTest(shape=name):
                fact = date_fact(text)
                self.assertEqual((fact.origin, set(context.documented_values(fact))), ('conflict', set(values)))
                with binding_disabled():
                    self.assertEqual(date_fact(text).origin, 'conflict')
        text = BANNER + LETTERHEAD + PATIENT + own + 'Findings:\nRepeat EGD in 3 months.\nVisit date: 10/05/2026\n'
        self.assertEqual(sent(text), '2026-10-05')  # an equal date agrees, as installed

    def test_evidence_the_installed_reading_held_answers_with_stays(self):
        # full suite (tests.test_repairs_7c8_dfd): outside a plan only a date read as the note's own or unplaced speaks
        # against it (_ASKED); a label its words read as another occurrence's, one beside a date of birth, or an unread
        # one was evidence that held every member's answer, and dropped with no own date it let the planned procedure's
        # date be taken and sent - the installed revision held them, and so does this one
        # 51(c)(2): an office visit's own procedure date ("Procedure date: 11/04/2026" under "GI office visit", sent by the
        # installed revision) is never its own date - asked, every answer held; a CRLF note is a visit's note too (its
        # title line's carriage return is no part of the title)
        for eol in ('\n', '\r\n'):
            text = (BANNER + 'GI office visit\nProcedure date: 11/04/2026\nAssessment and plan: colonoscopy will be '
                    'scheduled.\n').replace('\n', eol)
            with self.subTest(eol=repr(eol)):
                self.assertIsNone(sent(text))
                self.assertEqual(answers(text, ('2026-11-04', STRANGER)), {'2026-11-04': 'held', STRANGER: 'held'})
                self.assertIn(context.ASKED_DATE_NOTE, date_fact(text).note)
        head = BANNER + 'GI office visit\n'
        for line in ('Repeat colonoscopy for Synthetic, Alex (DOB 01/01/1998) Procedure date: 11/04/2026',
                     'Next procedure date: 11/04/2026', 'Procedure date: 11/04/2026 (scheduled)',
                     'Procedure date: 11-04-26'):
            text = head + line + '\nAssessment and plan: colonoscopy will be scheduled.\n'
            with self.subTest(line=line):
                self.assertIsNone(sent(text))
                self.assertEqual(answers(text, ('2026-11-04', '2026-10-05', STRANGER)),
                                 {'2026-11-04': 'held', '2026-10-05': 'held', STRANGER: 'held'})
                with binding_disabled():
                    self.assertEqual(member(text, '2026-11-04'), 'held')

    def test_a_dated_procedure_line_speaks_only_against_the_notes_own_date(self):
        # self-attack: dropped outright, a letter's subject line beside the header's date ("Re: Colonoscopy on
        # 11/04/2026") left the header's date sent where the installed reading asked; it is kept beside a labelled own
        # date, as installed, and dropped only where the note labels none (never the only answer)
        for line, beside in (('Re: Colonoscopy on 11/04/2026', 'conflict'), ('Subject: colonoscopy 11/04/2026', 'conflict'),
                             ('Procedure: Colonoscopy    Procedure date: 11/04/2026', 'conflict'),
                             ('Colonoscopy 11/04/2026', 'document')):
            for header in ('Date of service: 10/05/2026\n', ''):
                text = BANNER + LETTERHEAD + 'Clinic note\n' + PATIENT + header + line + '\n' + HISTORY
                with self.subTest(line=line, header=bool(header)):
                    if header:
                        self.assertEqual(date_fact(text).origin, beside)
                        with binding_disabled():
                            self.assertEqual(date_fact(text).origin, beside)
                    else:  # quoted as the procedure's own (_elsewhere): never an answer, every other answer held
                        self.assertIsNone(sent(text))
                        self.assertEqual(answers(text, ('2026-11-04', '2026-10-05', STRANGER)),
                                         {'2026-11-04': 'held', '2026-10-05': 'held', STRANGER: 'held'})

    def test_a_plan_statement_heads_the_fields_after_it(self):
        # self-attack: the booking's other fields between the statement and the visit date ("Appointment: 01/05/2027
        # 10:30", "Location: main clinic") left the visit date read as the note's own, and the booked visit's date sent
        # (as installed); the walk reads past the block's fields, and a field's own value may state the plan
        for block, booked in (('Return to clinic in 3 months.\nAppointment: 01/05/2027 10:30\nVisit date: 01/05/2027\n',
                               '2027-01-05'),
                              ('She will keep her clinic appointment.\nLocation: main clinic\nProvider: Priya '
                               'Halvorsen-Mbeki, MD (fictional)\nVisit date: 11/16/2026\n', '2026-11-16'),
                              ('Disposition: Return to clinic in 3 months.\nVisit date: 01/05/2027\n', '2027-01-05'),
                              ('Return to clinic in 3 months.\nVisit date: 01/05/2027\nVisit date: 01/05/2027\n',
                               '2027-01-05')):
            text = BANNER + LETTERHEAD + 'Clinic note\n' + PATIENT + HISTORY + block
            with self.subTest(block=block):
                self.assertIsNone(sent(text))
                self.assertEqual(answers(text, (booked, STRANGER)), {booked: 'held', STRANGER: 'held'})  # _ASKED
        # a statement naming no later occurrence ends the block: the footer's visit date reads as before
        for block in ('Continue mesalamine.\nProvider: Priya Halvorsen-Mbeki, MD (fictional)\nVisit date: 10/05/2026\n',
                      'Date of birth: 1961-03-14\nVisit date: 10/05/2026\n'):
            text = BANNER + LETTERHEAD + 'Clinic note\n' + PATIENT + HISTORY + block
            with self.subTest(block=block):
                self.assertEqual(sent(text), '2026-10-05')

    def test_a_plan_statement_in_a_visit_notes_untitled_section(self):
        for statement in ('She will keep her clinic appointment.', 'Return to clinic in 3 months.',
                          'Follow-up visit to be scheduled.', 'P: Continue mesalamine. Return to clinic in 3 months.'):
            text = BANNER + LETTERHEAD + 'Clinic note\n' + PATIENT + statement + '\nVisit date: 01/05/2027\n' + HISTORY
            with self.subTest(statement=statement):
                self.assertIsNone(sent(text))
                # the installed revision sent the booked visit's date and held every other answer: now none is sent,
                # the booked date is no answer, and every other answer is still held (_ASKED)
                self.assertEqual(answers(text, ('2027-01-05', STRANGER)), {'2027-01-05': 'held', STRANGER: 'held'})
        for field in ('Next visit: 01/05/2027', 'Visit type: Follow-up'):  # a field is no statement of the plan
            text = BANNER + LETTERHEAD + 'Clinic note\n' + PATIENT + field + '\nVisit date: 10/05/2026\n' + HISTORY
            with self.subTest(field=field):
                self.assertNotEqual(member(text, '2026-10-05'), 'held')


class SeparatorTests(CaseAsserts, SimpleTestCase):
    """dates2-9 (51(c)(3)): any short run of punctuation and blanks separates a label from its date."""

    SEPARATORS = ('........ ', ' ..... ', '… ', ' ‒ ', ' ― ', ' − ', '－', ' ﹘ ',
                  ' : ', ': ', ': ', ':　', ': ', ':: ', ': - ', ' -> ', '\t........\t')

    def test_the_reviewers_shapes(self):
        self.assert_cases('F6a', 'F6b', 'F6c', 'F6d', 'F6-ctrl')

    def test_the_fix_owners_shapes(self):
        self.assert_cases('s9-dots-charge', 's9-dos-nbsp', 's9-double-emdash', 's9-dots-unread-form', 's9-ctrl-prose-comma',
                          's9-dos-bracket', 's9-dos-bracket-charge', 's9-bracket-reverse', 's9-paren-date')

    def test_every_run_is_read_and_asked_never_sent(self):
        for separator in self.SEPARATORS:
            text = BANNER + 'Clinic note\n' + PATIENT + 'Date of service' + separator + '10/05/2026\nAssessment: anemia.\n'
            with self.subTest(separator=repr(separator)):
                self.assertIsNone(sent(text))
                self.assertEqual(answers(text, ('2026-10-05', '1998-01-01')),
                                 {'2026-10-05': 'taken', '1998-01-01': 'held'})

    def test_the_installed_separators_are_still_sent(self):
        for separator in (': ', ' - ', ' – ', ' # ', ' = ', ' ', ' (DOS): '):
            text = BANNER + 'Clinic note\n' + PATIENT + 'Date of service' + separator + '10/05/2026\nAssessment: anemia.\n'
            with self.subTest(separator=repr(separator)):
                self.assertEqual(sent(text), '2026-10-05')

    def test_a_separator_read_in_part_never_agrees_so_that_the_own_date_is_sent(self):
        # self-attack: where the installed revision read the label and its own separator character and then no date, it
        # kept unread date text that spoke against the header's date (asked); read now, an agreeing date sent the
        # header's date. It still speaks: asked, the header's date a member's answer that is taken
        header = BANNER + 'Clinic note\n' + PATIENT + 'Date of service: 10/05/2026\n' + HISTORY
        for separator in (':\u00a0', ':: ', ': - ', ' -> ', ': (', ': ........ ', ':\u3000', ' - \u2014 '):
            text = header + 'Date of service' + separator + '10/05/2026\n'
            with self.subTest(separator=repr(separator)):
                self.assertEqual(date_fact(text).origin, 'conflict')
                self.assertEqual(date_fact(text).note, context.FORM_DATE_NOTE)
                self.assertEqual(answers(text, ('2026-10-05', '2026-10-06')), {'2026-10-05': 'taken', '2026-10-06': 'held'})
        # where the installed revision read no separator character at all it kept nothing there: an agreeing date
        # changes nothing, and a disagreeing one is asked
        for separator in (' \u2014 ', '........ ', '. ', '\u00a0: ', '\uff1a'):
            with self.subTest(separator=repr(separator)):
                self.assertEqual(sent(header + 'Date of service' + separator + '10/05/2026\n'), '2026-10-05')
                self.assertEqual(date_fact(header + 'Date of service' + separator + '10/06/2026\n').origin, 'conflict')

    def test_label_words_joined_by_any_blank(self):
        for blank in (' ', ' ', ' '):
            text = (BANNER + 'Clinic note\n' + PATIENT + 'Date' + blank + 'of' + blank + 'service: 10/05/2026\n'
                    'Assessment: anemia.\n')
            with self.subTest(blank=repr(blank)):
                self.assertIsNone(sent(text))
                self.assertEqual(answers(text, ('2026-10-05', '1998-01-01')),
                                 {'2026-10-05': 'taken', '1998-01-01': 'held'})

    def test_prose_punctuation_opens_no_field(self):
        text = (BANNER + 'Clinic note\n' + PATIENT + 'Assessment: anemia.\nPlan:\n'
                'Labs drawn on the date of service, results pending.\n')
        self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
        self.assertEqual(member(text, STRANGER), 'taken')


class VariantFamilyTests(SimpleTestCase):
    """The reviewer's variant batches, each read by its family's source-reviewed rule (variants.json)."""

    # pre-existing, outside the title's section, and read as the installed revision reads them: a qualified dated title
    # under "Clinic note" with no labelled date ("Next visit: 01/05/2027") is the only answer (the title reader's rule
    # N1). Under the document's own follow-up title the head skips such a title (b2's GI:* rows read right).
    LIMITS = {('b2', 'Clinic:next'): '2027-01-05', ('b2', 'Clinic:last-next'): '2026-08-27'}

    def only(self, text):
        probes = ('2026-06-01', '2026-08-27', '2026-10-05', '2026-10-06', '2026-11-04', '2026-11-16', '2027-01-05',
                  '2027-04-05', STRANGER)
        got = answers(text, probes)
        taken = [p for p, v in got.items() if v == 'taken']
        return taken[0] if len(taken) == 1 else None

    def test_every_family(self):
        rows = variants()
        self.assertEqual(len(rows), 340)
        for row in rows:
            text, family, key = row['text'], row['family'], (row['batch'], row['case'])
            with self.subTest(batch=row['batch'], case=row['case']):
                self.assertTrue(text.startswith(BANNER))
                got = sent(text)
                if family == 'charge':  # the charge's date against the header's: a conflict, neither date sent
                    self.assertIsNone(got)
                elif family in ('earlier', 'planned', 'statement', 'header'):
                    never = {'earlier': ('2026-06-01', '2026-08-27'), 'planned': ('2026-11-04', '2026-11-16'),
                             'statement': ('2026-11-16', '2026-11-04', '2027-01-05'),
                             'header': ('2027-01-05', '2026-08-27', '2027-04-05')}[family]
                    self.assertNotIn(got, never)
                    if key in self.LIMITS:
                        self.assertEqual(self.only(text), self.LIMITS[key])
                    else:
                        self.assertNotIn(self.only(text), never)
                elif family == 'separator':
                    self.assertNotEqual(got, '2026-10-06')
                    self.assertNotEqual(member(text, '1998-01-01'), 'taken')
                elif family == 'setting':
                    found = facts(text)
                    self.assertNotIn(fact_text(found['setting']), ('document:asc', 'document:hospital_outpatient'))


class EngineTests(SimpleTestCase):
    """dates2-10: the visit's place of service is asked, so 99214 is never ready on a plan sentence's ASC."""

    def test_no_place_of_service_from_a_plan_sentence_or_another_occurrences_field(self):
        for name in ('F8a', 'F8b'):
            text = cases()[name]['text']
            found = facts(text)
            with self.subTest(case=name):
                self.assertEqual(found['setting'].origin, 'missing')
                proposals, _ = run(text, [('99214', ('Ulcerative colitis in remission.',))], found, date(2026, 10, 5))
                self.assertNotEqual(proposals['99214'].status, 'ready')
                self.assertIn('setting', [c.fact for c in proposals['99214'].clarifications])
                self.assertNotIn('asc', proposals['99214'].rationale)


def _seconds(text: str) -> float:
    layout.cache_clear()
    for cached in (context._context, context._governance, context._title_start, context._title_line,
                   context._visit_note, context.find_dates, context._date_starts):
        cached.cache_clear()
    started = time.process_time()
    context.merge_user_values(context.extract_context(text), {})
    return time.process_time() - started


def _fill(size: int, prefix: str, unit: str, suffix: str = '') -> str:
    return prefix + unit * max(0, (size - len(prefix) - len(suffix)) // len(unit)) + suffix


class CostTests(SimpleTestCase):
    """cost-r2-1 and cost-r2-2, and every loop and pattern this round adds, read in time linear in the text."""

    @staticmethod
    def paste(name: str, size: int) -> str:
        half = size // 2
        if name == 'cost-r2-1: a padded stacked title over many labels':
            return _fill(size, BANNER + 'GI clinic follow-up\nOffice visit' + ' ' * half + '\n', 'Visit date: 10/05/2026\n')
        if name == 'cost-r2-2: "CPT" before a long blank run':
            head = (BANNER + 'Clinic note\nDate of service: 10/05/2026\nAssessment:\nStable.\nPlan:\n'
                    'Return to clinic in 6 weeks.\nLabs\nDate of service: 10/05/2026\n')
            return head + 'CPT' + ' ' * (size - len(head) - 6) + 'x\n'
        shapes = {
            'the head over many header fields': (BANNER + 'GI clinic follow-up\n', 'Provider: Synthetic MD\nDOS: 10/05/2026\n'),
            'separator runs': (BANNER + 'Clinic note\n', 'Date of service ........ 10/05/2026\n'),
            'separator runs before an unread form': (BANNER + 'Clinic note\n', 'Date of service ........ 05-Oct-26\n'),
            'column labels on one long row': (BANNER + 'Clinic note\nAssessment and plan\nStable.\n', 'Date of service | '),
            'explicit headings over labels': (BANNER + 'Clinic note\nPlan:\n', 'Prior visit\nDate of service: 10/06/2026\n'),
            'joined headings': (BANNER + 'Clinic note\nPlan:\n', 'Charge Information: Date of Service: 10/06/2026\n'),
            'plan statements before visit dates': (BANNER + 'Clinic note\n', 'Return in 3 months.\nVisit date: 01/05/2027\n'),
            'section headings before visit dates': (BANNER + 'Clinic note\nPlan:\nReturn in 6 weeks.\n',
                                                    'Bowel preparation\nVisit date: 11/16/2026\n'),
            'head setting lines naming another occurrence': (BANNER + 'GI clinic follow-up\n',
                                                             'Location: office for the next EGD, POS 11\n'),
        }
        return _fill(size, *shapes[name])

    NAMES = ('cost-r2-1: a padded stacked title over many labels', 'cost-r2-2: "CPT" before a long blank run',
             'the head over many header fields', 'separator runs', 'separator runs before an unread form',
             'column labels on one long row', 'explicit headings over labels', 'joined headings',
             'plan statements before visit dates', 'section headings before visit dates',
             'head setting lines naming another occurrence')

    def test_the_reading_grows_linearly(self):
        for name in self.NAMES:
            small, large = (_seconds(self.paste(name, size)) for size in (25_000, 100_000))
            with self.subTest(shape=name):
                self.assertLess(large, 8 * max(small, 0.02))  # four times the text: about 4x, 16x if quadratic

    def test_cap_size_pastes_fit_a_members_context_request(self):
        for name in self.NAMES[:2]:
            with self.subTest(shape=name):
                self.assertLess(_seconds(self.paste(name, 400_000)), 15.0)


class KnownLimitTests(SimpleTestCase):
    """Residuals of this round, pinned by input and exact output with the reason (a change that fixes one fails here)."""

    def test_a_header_table_without_a_birth_column_under_the_title(self):
        """No positive evidence that the table is the patient's header: its column speaks only against the note's own
        date (a results table looks the same), so with no own date the visit's date is not kept as evidence."""
        text = follow_up('GI clinic follow-up', 'Patient | Date of service | Provider\n'
                         'Ivo Brandmere (fictional) | 10/05/2026 | Priya Halvorsen-Mbeki, MD (fictional)\n' + HISTORY)
        self.assertEqual(answers(text, ('2026-10-05', '1998-01-01')), {'2026-10-05': 'taken', '1998-01-01': 'taken'})
        self.assertIsNone(sent(text))

    def test_a_terse_plan_field_in_the_head(self):
        """A header field whose label and value name no other occurrence and state no plan's clause ("RTC: 3 months")
        keeps the head, so a visit date after it reads as an untitled header reads it - as the installed revision reads
        the same lines under "Clinic note" (51(c)(3)): sent."""
        text = follow_up('GI clinic follow-up', PATIENT + 'RTC: 3 months\nVisit date: 01/05/2027\n' + HISTORY)
        self.assertEqual(sent(text), '2027-01-05')
        same = text.replace('GI clinic follow-up', 'Clinic note')
        self.assertEqual(sent(same), '2027-01-05')
