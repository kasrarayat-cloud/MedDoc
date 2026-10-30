"""GI round 3, fix round 1 (session 7c8d38da, 2026-10-30), fix owner "dates": the independent refutation of the
integrated candidate 543bae72a found the date/section binding wrong by the source in nine shapes (studio/gi/context.py,
"gi3 fix round 1"). Each fix only asks, or reads as the installed revision 90377ec6f413 read:
- dates-1: RC5 took a plan heading for the document's own follow-up title ("Follow-up appointment", "Follow-up
  procedures", "Pending follow-up", "Recall follow-up", a heading after prose) and sent the planned visit's date;
- dates-2: RC5 read its whole section as an untitled header, so a procedure date (an index, scheduled or recalled
  procedure's), a "Return visit date" or a results table's column was sent, or became the only member answer;
- dates-3 and cost-3, dates-4 and cost-2: B4's item reading and part 3's account reading rescanned per label
  (quadratic: 100 s at 80,000 characters, 72 s at 128,000);
- dates-5: a heading booking the plan item ("Scheduling", "Appointment details") was read as neutral, so the planned
  date became the only answer;
- dates-6: H1 refused a charge heading worded like its CPT descriptor ("Colonoscopy with biopsy", "Endoscopic
  ultrasound", "Evaluation and management, level 4"), so the contradicted header date was sent;
- dates-7: a results table's column inside a plan with no block heading spoke;
- dates-8: a Title Case or capitals heading joined to its field on one line ("Charge Information Date of Service:")
  dropped the field;
- dates-9: an em dash, a full stop or a full-width colon after the label left no candidate at all.

The expected answers live outside the reader: tests/fixtures/gi3/fix1-dates/cases.json holds the reviewer's inputs
(copied texts) with their source-reviewed expectations. Synthetic text only; pure functions - no database, no provider,
no network.
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import context
from tests.test_repairs_gi3_dates import (BANNER, STRANGER, _fill, _process_seconds, date_fact, fact_text, facts, member,
                                          sent)

CASES = Path(__file__).resolve().parent / 'fixtures' / 'gi3' / 'fix1-dates' / 'cases.json'
CLINIC = (BANNER + 'Synthetic GI clinic (fictional)\nClinic note\nPatient: Synthetic Patient (fictional)\n{own}'
          'Place of service: office (POS 11)\n\nSubjective\nFollow-up of anemia.\n\nAssessment and plan\n'
          'Iron deficiency anemia. Continue oral iron.\n')
OWN = 'Date of service: 2026-10-05\n'


def cases() -> dict:
    return {case['id']: case for case in json.loads(CASES.read_text(encoding='utf-8'))['cases']}


def clinic(block: str, own: str = OWN) -> str:
    return CLINIC.format(own=own) + block


class CaseAsserts:
    def assert_case(self, case):
        """The case's source-reviewed expectation (cases.json): 'document' - that date is sent and a stranger's held;
        'conflict' - no date is sent, each listed date is a member's answer that is taken, a stranger's held; 'asked' -
        no date is sent, each date in ``taken`` is a member answer that is taken (so no planned or other date is the
        only answer), or only the date ``only`` is (each in ``held`` held)."""
        text, expected = case['text'], case['expected']
        found = facts(text)
        fact = found['service_date']
        kind = expected['kind']
        if kind == 'document':
            self.assertEqual((fact.origin, fact.value), ('document', expected['value']), [e.text for e in fact.evidence])
            self.assertEqual(member(text, STRANGER), 'held')
        elif kind == 'conflict':
            self.assertEqual(fact.origin, 'conflict', [e.text for e in fact.evidence])
            self.assertEqual(set(context.documented_values(fact)), set(expected['values']), fact.note)
            for value in expected['values']:
                self.assertEqual(member(text, value), 'taken', value)
            self.assertEqual(member(text, STRANGER), 'held')
        else:
            self.assertIsNone(sent(text), fact.value)
            for value in expected.get('taken', ()):
                self.assertEqual(member(text, value), 'taken', value)
            if 'only' in expected:
                self.assertEqual(member(text, expected['only']), 'taken')
                self.assertEqual(member(text, STRANGER), 'held')
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
        self.assertEqual(len(known), 57)
        for name, case in known.items():
            self.assertTrue(case['text'].startswith(BANNER), name)
            with self.subTest(case=name):
                self.assert_case(case)


class TitleTests(CaseAsserts, SimpleTestCase):
    """dates-1: the document's own follow-up title opens the document and names the follow-up visit itself."""

    def test_a_heading_after_a_field_or_prose_is_no_title(self):
        self.assert_cases('d1-phone-provider', 'd1-phone-location-proc', 'd1-phone-provider-own', 'd1-portal-msg',
                          'd1-phone-nodate')
        field = BANNER + 'Patient: Synthetic Patient (fictional)\nGI clinic follow-up\nVisit date: 2026-11-16\n'
        self.assertIsNone(context._title_start(field))
        self.assertIsNone(sent(field))

    def test_the_follow_up_is_what_the_title_names(self):
        self.assert_cases('d1-fu-appointment', 'd1-fu-procedures', 'd1-fu-care', 'd1-fu-appointments')

    def test_no_pending_recalled_or_return_follow_up(self):
        self.assert_cases('d1-pending-fu', 'd1-recall-fu')
        text = cases()['d1-pending-fu']['text'].replace('Pending follow-up', 'Return follow-up')
        self.assertIsNone(context._title_start(text))

    def test_the_rulings_titles_still_read(self):
        self.assert_cases('d1-ctrl-telephone-fu', 'd1-ctrl-body-plan', 'd1-ctrl-next-appointment', 'd1-preproc-fu')
        for title in ('GI clinic follow-up', 'Hepatology follow-up', 'Liver clinic follow up', 'Office follow-up',
                      'Post-procedure follow-up', 'Telephone follow-up', 'IBD follow-up'):
            text = (BANNER + 'Synthetic GI clinic (fictional)\n' + title + '\nPatient: Synthetic Patient (fictional)\n'
                    'Visit date: 2026-10-21\nPlace of service: office (POS 11)\n')
            with self.subTest(title=title):
                self.assertIsNotNone(context._title_start(text))
                self.assertEqual(sent(text), '2026-10-21')


class TitleSectionTests(CaseAsserts, SimpleTestCase):
    """dates-2: in the title's section only the header's own field dating this visit reads as an untitled header's."""

    def test_a_procedure_date_dates_a_procedure(self):
        self.assert_cases('d2-surveillance-block', 'd2-proc-only', 'd2-proc-sched', 'd2-hx-block', 'd2-last-colo',
                          'd1-preproc-fu')

    def test_a_qualified_visit_date_is_never_the_only_answer(self):
        self.assert_cases('d2-return-only')

    def test_a_tables_column_dates_its_rows(self):
        self.assert_cases('d2-labs-table')

    def test_a_heading_naming_another_block_governs_there_too(self):
        self.assert_cases('d2-last-colo-dos', 'd2-block-heading-dos')

    def test_the_headers_own_date_still_reads(self):
        self.assert_cases('d2-ctrl-intended')


class BookingHeadingTests(CaseAsserts, SimpleTestCase):
    """dates-5: a heading booking the plan item governs; this encounter's own administrative block still speaks."""

    def test_a_booking_heading_governs_the_planned_date(self):
        self.assert_cases('d5-noown-scheduling', 'd5-noown-sched-details', 'd5-noown-appt-details', 'd5-noown-visit-sched',
                          'd5-own-scheduling', 'd5-own-appt-details', 'd5-own-visit-sched')

    def test_a_booking_heading_names_no_kind_of_service(self):
        text = clinic('Appointment details\nDate of service: 2026-11-04\n')
        self.assertEqual(sent(text), '2026-10-05')
        self.assertEqual(member(text, '2026-11-04'), 'held')

    def test_an_administrative_block_of_this_encounter_still_speaks(self):
        text = clinic('Billing\nProcedure date: 2026-10-15\n', own='')
        self.assertEqual(date_fact(text).origin, 'missing')
        self.assertEqual(member(text, '2026-10-15'), 'taken')
        self.assertEqual(member(text, STRANGER), 'held')
        text = clinic('Encounter summary\nVisit date: 2026-10-06\n')
        self.assertEqual(date_fact(text).origin, 'conflict')
        # a surgery named in a heading may be this encounter's own place: the facility block's date still speaks
        report = (BANNER + 'Northgate Endoscopy Center (fictional)\nColonoscopy report\nPatient: Ivo Brandmere '
                  '(fictional)\nDate of service: 10/14/2026\nIndication: surveillance.\nTechnique: The colonoscope was '
                  'advanced to the cecum.\nFindings: Normal to the cecum.\nImpression: normal colonoscopy.\n'
                  'Recommendations:\nRepeat colonoscopy in 5 years.\nAmbulatory surgery center\n'
                  'Date of service: 10/15/2026\n')
        self.assertEqual(date_fact(report).origin, 'conflict')
        for heading in ('Recall details', 'Referral information'):  # a booking's block governs its fields
            with self.subTest(heading=heading):
                self.assertEqual(sent(report.replace('Ambulatory surgery center', heading)), '2026-10-14')


class DescriptorHeadingTests(CaseAsserts, SimpleTestCase):
    """dates-6: a charge heading worded like its billing descriptor names a kind of service (H1)."""

    def test_a_procedure_descriptor_names_its_service(self):
        self.assert_cases('d6-colo-biopsy', 'd6-colo-biopsy-desc', 'd6-egd-biopsy', 'd6-egd-biopsies', 'd6-eus-bare',
                          'd6-eus-fna', 'd6-flex-sig-biopsy', 'd6-specimen-collection', 'd6-cytology-brushing',
                          'd6-anoscopy-biopsy')

    def test_the_em_services_name_is_its_own(self):
        self.assert_cases('d6-em-level', 'd6-em-visit')

    def test_a_sample_or_document_alone_still_governs(self):
        for heading in ('Biopsy', 'Biopsies', 'Colonoscopy pathology', 'Surveillance ultrasound', 'Pathology'):
            with self.subTest(heading=heading):
                self.assertEqual(sent(clinic(heading + '\nDate of service: 2026-10-16\n')), '2026-10-05')

    def test_another_occurrence_still_governs_inside_a_service_name(self):
        """Interpretation 48(a): a follow-up names another occurrence, as "Return visit" does, where nothing marks the
        block as this encounter's charge. The integration owner's 48(f) (a CPT code in the block) decides the charge
        line this owner reported ("Follow-up visit, level 4" / "CPT: 99214"): a conflict, asked, never the header's date
        sent (tests.test_repairs_gi3_integration.ChargeLineTests)."""
        for heading in ('Follow-up visit, level 4', 'Established patient follow-up visit'):
            with self.subTest(heading=heading):
                self.assertEqual(sent(clinic('Charges\n' + heading + '\nDate of service: 2026-10-06\n')), '2026-10-05')
                charge = clinic('Charges\n' + heading + '\nCPT: 99214\nDate of service: 2026-10-06\n')
                self.assertIsNone(sent(charge))
                self.assertEqual(date_fact(charge).origin, 'conflict')


class TableColumnTests(CaseAsserts, SimpleTestCase):
    """dates-7: a table's column label inside a plan with no block heading dates its rows; the plan governs it."""

    def test_the_results_column_is_governed(self):
        self.assert_cases('d7-nohead-own', 'd7-nohead-noown')

    def test_past_a_neutral_heading_a_charge_table_still_speaks(self):
        text = clinic('Charge information\nDate of service | Diagnosis | CPT\n2026-10-06 | anemia | 99214\n')
        self.assertEqual(date_fact(text).origin, 'conflict')


class JoinedHeadingTests(CaseAsserts, SimpleTestCase):
    """dates-8: a neutral heading joined to its field on one line, in Title Case or capitals."""

    def test_a_joined_heading_lets_the_field_speak(self):
        self.assert_cases('d8-sameline-title', 'd8-sameline-caps', 'd8-sameline-billing', 'd8-ctrl-sameline-lower')

    def test_a_joined_heading_naming_another_block_still_governs(self):
        for line in ('Follow Up Date of Service: 11/16/2026', 'Next Appointment Date of Service: 11/16/2026',
                     'Labs Date of Service: 09/30/2026'):
            with self.subTest(line=line):
                self.assertEqual(sent(clinic(line + '\n')), '2026-10-05')

    def test_with_no_own_date_it_is_never_the_only_answer(self):
        """A joined heading cannot be told from a word qualifying the date, so the field speaks only against the note's
        own date: with none it stays dropped as installed, and every member answer is taken."""
        for line in ('Charge Information Date of Service: 2026-10-06', 'Expected Date of Service: 11/04/2026'):
            text = clinic(line + '\n', own='')
            with self.subTest(line=line):
                self.assertEqual((date_fact(text).origin, date_fact(text).evidence), ('missing', ()))
                for answer in ('2026-10-06', '2026-11-04', STRANGER):
                    self.assertEqual(member(text, answer), 'taken', answer)

    def test_a_label_in_prose_stays_governed(self):
        self.assertEqual(sent(clinic('Labs on the date of service: normal.\n')), '2026-10-05')


class SeparatorTests(CaseAsserts, SimpleTestCase):
    """dates-9: an em dash, a full stop or a full-width colon after the label is read, and asked."""

    def test_the_labelled_date_is_documented_and_asked(self):
        self.assert_cases('d9-emdash-only', 'd9-emdash-nospace', 'd9-dot-only', 'd9-fullwidth-colon')
        for name in ('d9-emdash-only', 'd9-dot-only', 'd9-fullwidth-colon'):
            with self.subTest(case=name):
                self.assertEqual(date_fact(cases()[name]['text']).note, context.FORM_DATE_NOTE)

    def test_it_speaks_against_the_notes_own_date(self):
        self.assert_cases('d9-emdash-noplan', 'd9-emdash-plan', 'd9-ctrl-endash')

    def test_the_note_names_the_form(self):
        for words in ('em dash', 'full stop', 'full-width colon', 'broken over two lines'):
            self.assertIn(words, context.FORM_DATE_NOTE)

    def test_a_time_statements_run_reads_as_installed(self):
        """The elapsed-time rule reads a run with a day in it as installed: a label the installed revision did not read
        still states that day there (it is asked), so the time field's question is never silenced into a send."""
        text = (BANNER + 'Synthetic GI clinic (fictional)\nClinic note\nDate of service: 10/23/2026\nAssessment: anemia.\n'
                'Total time on the date of service: 34 minutes, counseling and\nDate of service — 10/23/2026\n')
        self.assertEqual(date_fact(text).origin, 'conflict')
        self.assertIsNone(sent(text))


class KnownLimitTests(SimpleTestCase):
    """Residuals of this round, pinned by input and exact output with the reason (a change that fixes one fails here
    and is updated deliberately)."""

    def outcome(self, text, probes):
        fact = date_fact(text)
        return f'{fact.origin}:{fact.value}', {p: member(text, p) for p in probes}

    def test_a_logistics_heading_names_no_occurrence(self):
        """dates-5 residual: "Logistics" names no occurrence by its words (interpretation 42's vocabulary), so the
        planned date after it is asked as interpretation 42 asks a label under a neutral heading - the only answer
        with no own date."""
        known = cases()
        noown = known['d5-noown-scheduling']['text'].replace('Scheduling\n', 'Logistics\n')
        self.assertEqual(self.outcome(noown, ('2026-11-04', '2026-10-05', STRANGER)),
                         ('missing:None', {'2026-11-04': 'taken', '2026-10-05': 'held', STRANGER: 'held'}))

    def test_a_results_table_past_a_neutral_heading(self):
        """dates-7 residual: past a neutral heading ("Data reviewed") the plan's reach has ended (interpretation 42)
        and a table there speaks, as the corpus's charge table does (A20): its date is the only answer with no own."""
        text = (BANNER + 'Synthetic GI clinic (fictional)\nClinic note\nPatient: Synthetic Patient (fictional)\n'
                'Chief complaint: cirrhosis follow-up\nAssessment and plan\nCirrhosis, compensated. Continue current '
                'care.\nData reviewed\nTest | Date of service | Result\nALT | 2026-09-30 | 41 U/L\n')
        self.assertEqual(self.outcome(text, ('2026-09-30', '2026-10-05', STRANGER)),
                         ('missing:None', {'2026-09-30': 'taken', '2026-10-05': 'held', STRANGER: 'held'}))

    def test_a_title_section_label_that_speaks_against_the_header(self):
        """dates-2 residual: a return visit or procedure date in a follow-up title's header speaks against the
        header's visit date (asked, never sent: the installed revision sent neither)."""
        text = (BANNER + 'Synthetic GI clinic (fictional)\nGI clinic follow-up\nPatient: Synthetic Patient (fictional)\n'
                'Visit date: 10/05/2026\nReturn visit date: 01/05/2027\nInterval history:\nDoing well.\n')
        self.assertEqual(self.outcome(text, ('2026-10-05', '2027-01-05', STRANGER)),
                         ('conflict:None', {'2026-10-05': 'taken', '2027-01-05': 'taken', STRANGER: 'held'}))

    def test_a_visit_date_right_under_the_title(self):
        """dates-2 residual: a visit date on the line right under the title reads the title's follow-up as its own
        qualifier ('unplaced'), so it is asked as installed (every answer taken)."""
        text = BANNER + 'Synthetic GI clinic (fictional)\nGI clinic follow-up\nVisit date: 2026-10-21\n'
        self.assertEqual(self.outcome(text, ('2026-10-21', STRANGER)),
                         ('missing:None', {'2026-10-21': 'taken', STRANGER: 'taken'}))


class CostTests(SimpleTestCase):
    """dates-3, cost-3, dates-4, cost-2: each reading once per line, per item sentence and per section."""

    SHAPES = {
        'dates-3: lower-case visit labels wrapped into one plan sentence': (
            BANNER + 'Clinic note\nPlan:\n', 'visit date: 11/16/2026 x\n'),
        'cost-3: visit labels on one line under a long blank run': None,
        'dates-4: own labels in a procedure section after a plan': (
            BANNER + 'Clinic note\nPlan:\nColonoscopy with possible polypectomy.\nProcedure: Colonoscopy\n',
            'Date of service: 10/14/2026\n'),
        'cost-2: own labels after a later-occurrence plan item': (
            BANNER + 'Plan:\nReturn to clinic in 6 weeks.\nProcedure: Colonoscopy\n', 'Date of service: 10/05/2026\n'),
    }

    def paste(self, name, size):
        if self.SHAPES[name] is None:
            half = size // 2
            return BANNER + 'Plan:\n' + '\n' * half + _fill(size - half - 80, '', 'Visit date: 11/16/2026. ') + '\n'
        return _fill(size, *self.SHAPES[name])

    def test_the_reading_grows_linearly(self):
        for name in self.SHAPES:
            small, large = (_process_seconds(self.paste(name, size)) for size in (25_000, 100_000))
            with self.subTest(shape=name):
                self.assertLess(large, 8 * max(small, 0.02))  # four times the text: about 4x, 16x if quadratic

    def test_cap_size_pastes_fit_a_members_context_request(self):
        for name in self.SHAPES:
            with self.subTest(shape=name):
                self.assertLess(_process_seconds(self.paste(name, 400_000)), 15.0)  # measured at most 2.9 s
