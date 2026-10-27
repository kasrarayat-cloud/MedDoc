"""Repair round 7c8, cluster CONTEXT round 3 (studio/gi/context.py): the service date sent to Corti.

Owner decision 2026-10-27 (narrow, install-first), must-fix classes 1 (a wrong or member-supplied service date in a
provider request), 2 (stage time) and 4 (a code excluded on a dated check without a reviewer's decision). The skeptic of
round 2 (0e639e79f, 486763512) demonstrated seven issues, sk:1 .. sk:7 below, each re-checked here at its smallest
input. The rule stays the round-2 rule - the reader may be unsure, but it is never silently wrong - and each repair is a
structural one:

sk:1  a member date agrees only with a date some candidate states as its own value (a date of birth beside it does not);
sk:2  a qualifier in another field before a label that opens its own field still holds the date (it is asked);
sk:3  the service-date fact is linear in the number of the note's labelled dates;
sk:4  a title naming another discipline is never the note's heading, whatever its title word;
sk:5  a field on the line above naming another occurrence, or a phrase attached after the date naming one (also on the
      line it wraps to), holds the date;
sk:6  a dated line naming the service beside a bare "Date:" line makes the date a question;
sk:7  a date label or a "Date:" line may name the time ("DOS/Time", "Date & Time"), and a clock may follow a date.

An over-hold (the date asked although a coder would know it) is a known limit; a wrong or member-supplied date where the
document states another is not. Synthetic text only; no network (the suite's FakeProvider).
"""
import json
import time
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from studio import bounded, jobs, models
from studio.gi import context
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain
from tests.test_repairs_7c8_context import DateAssertions

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
OFFICE_BODY = OFFICE_NOTE.split('\n', 1)[1].replace('Date of service: 2026-10-20\n', '')
VISIT_BODY = ('Established patient office visit for chronic constipation.\n'
              'Total time on the date of the encounter was 24 minutes.\n')
EGD_BODY = ('PROCEDURE NOTE: EGD\nTechnique: The upper endoscope was advanced to the second portion of the duodenum.\n'
            'Findings: On 10/14/2026 biopsies were taken from the antrum.\n')
COLO_BODY = ('PROCEDURE NOTE: Colonoscopy\nTechnique: The colonoscope was advanced to the cecum.\n'
             'Findings: On 10/14/2026 a 5 mm sigmoid polyp was removed with a cold snare.\n')
COLO_PLAIN = ('PROCEDURE NOTE: Colonoscopy\nTechnique: The colonoscope was advanced to the cecum.\n'
              'Findings: A 5 mm sigmoid polyp was removed with a cold snare.\n')
ELENA_DATE = '1998-01-01'  # a member-entered date far from any documented one (the Elena incident)
BIRTH = '01/01/1998'  # the same day written as a date of birth beside the date of service


def date_fact(text):
    return context.extract_context(text)['service_date']


def evidence_text(text):
    return [' '.join(e.text.split()) for e in date_fact(text).evidence]


class Provider(FakeProvider):
    """FakeProvider whose response names only the selections the request's own text contains."""

    def send(self, request, *, deadline_s):
        every = self.selections
        self.selections = [(code, quote) for code, quote in every if quote in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.selections = every


@override_settings(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
class EndToEnd(TestCase):
    """End to end with the suite's FakeProvider: the date each provider request carries, and the dated checks."""

    BIOPSY = ('43239', 'biopsies were taken from the antrum')
    SNARE = ('45385', 'was removed with a cold snare')
    VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(selections=[self.VISIT, self.SNARE, self.BIOPSY])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def finished(self, text, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        drain()
        return response.json()['id']

    def set_context(self, encounter_id, values):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/api/encounters/{encounter_id}/context', data=json.dumps(values),
                                        content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        drain()

    def dates_sent(self, encounter_id):
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id, sent=True).order_by('created_at')
        return [list(run.contexts[1:]) for run in runs]

    def bucket(self, encounter_id, code):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        return encounter.current_assessment.proposals.get(code=code, bucket__in=('selected', 'excluded')).bucket

    def assert_not_excluded(self, encounter_id, code):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertFalse(encounter.current_assessment.proposals.filter(code=code, bucket='excluded').exists())

    def assert_held(self, encounter_id, runs=1):
        """Nothing sent for the member's date: the last run is held as a member date conflict."""
        held = models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at')
        self.assertEqual(held.count(), runs)
        last = held.last()
        self.assertEqual((last.sent, last.state, last.scope),
                         (False, models.ProviderRun.NOT_SENT, {'held': models.ProviderRun.HELD_MEMBER_DATE_CONFLICT}))
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'needs_clarification')

    def assert_never_sent(self, encounter_id, *dates):
        sent = [line for run in self.dates_sent(encounter_id) for line in run]
        for value in dates:
            self.assertNotIn(f'Date of service: {value}', sent)


class ManyLabelledDatesCostTests(SimpleTestCase):
    """sk:3 (a cost regression of 0e639e79f, class 2): the service-date fact set the note's own labelled dates apart from
    the others by a list membership test - one dataclass comparison per pair, quadratic in the number of labelled dates:
    'DOS: 10/14/2026' 24,000 times (384,067 characters, under the paste cap) overran the analyze stage's 60 s, and 12,000
    overran a member's POST /context (15 s). Every set is now kept by identity: both children read it in about a second
    (the doubling ratios are in the commit)."""

    TEXT = HEAD + 'DOS: 10/14/2026\n' * 24000

    def test_the_analyze_child_reads_it_within_the_stage_deadline(self):
        started = time.perf_counter()
        out = bounded.run_bounded(jobs._analyze_child, self.TEXT, {}, settings.MAX_SERVICE_MENTIONS,
                                  seconds=settings.JOB_DEADLINE_SECONDS['analyze'],
                                  memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertLess(time.perf_counter() - started, 20)
        self.assertEqual((out[0]['service_date'].origin, out[0]['service_date'].value), ('document', '2026-10-14'))

    def test_a_member_s_context_child_reads_it_within_its_bound(self):
        started = time.perf_counter()
        facts = bounded.run_bounded(context.extract_context, self.TEXT, seconds=settings.CONTEXT_REQUEST_SECONDS,
                                    memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertLess(time.perf_counter() - started, settings.CONTEXT_REQUEST_SECONDS)
        self.assertEqual(facts['service_date'].origin, 'document')


class MemberDateAgreesOnlyWithAStatedValueTests(DateAssertions, SimpleTestCase):
    """sk:1 (a regression of 0e639e79f, the Elena class): a member date agreed with any date found anywhere in a
    candidate's evidence span, and an unread label's span ran to the end of its value field - across a date of birth
    one space after the value, or across the earlier cells of a table row. A member's 1998-01-01 beside 'DOB:
    01/01/1998' was taken and sent, and an act done on the documented date was excluded against it. Each candidate's
    evidence now holds only its own value (the value's first date-shaped run; a table column's label and its cell), so a
    member date agrees only with a date some candidate states as its own."""

    BORN = (
        # title + a table whose date-of-birth column comes before the date-of-service column (T5)
        HEAD + 'Colonoscopy report - 10/14/2026\nPatient | DOB | Date of Service\nSynthetic, Alex | ' + BIRTH
        + ' | 10/14/2026\n' + COLO_BODY,
        # title + a flattened header row: an unread value one space before a date of birth (T4)
        HEAD + 'Colonoscopy report - 10/14/2026\nPatient: Synthetic, Alex    DOS: 10/14/26 DOB: ' + BIRTH + '\n'
        + COLO_BODY,
        # the note's own labelled date beside such a line or table
        HEAD + 'Date of service: 10/14/2026\nPatient: Synthetic, Alex    DOS: 10/14/26 DOB: ' + BIRTH + '\n'
        + COLO_PLAIN,
        HEAD + 'Date of service: 10/14/2026\nPatient | DOB | Visit Date\nSynthetic, Alex | ' + BIRTH
        + ' | 10/14/2026\n' + COLO_PLAIN,
        # a label above its value, the value one space before a date of birth
        HEAD + 'Colonoscopy report - 10/14/2026\nDate of service:\n10/14/2026 DOB: ' + BIRTH + '\n' + COLO_PLAIN,
        # tables without a title, the date-of-birth column first
        HEAD + 'Patient | DOB | Date of Service | Provider\nSynthetic, Alex | ' + BIRTH
        + ' | 10/14/2026 | Dr. A. Synthetic\n' + COLO_PLAIN,
        HEAD + '| Patient | DOB | Date of Service |\n| --- | --- | --- |\n| Synthetic, Alex | ' + BIRTH
        + ' | 10/14/2026 |\n' + COLO_PLAIN,
    )
    UNREAD_BORN = (
        HEAD + 'DOS: 10-20-26 DOB: ' + BIRTH + '\n' + VISIT_BODY,  # E1
        HEAD + 'Date of Service: 10/20/26 Date of Birth: ' + BIRTH + '\n' + VISIT_BODY,  # E2
        HEAD + 'Date of service: 20-Oct-26 (DOB ' + BIRTH + ')\n' + VISIT_BODY,
        HEAD + 'Visit date: 10.20.2026, DOB ' + BIRTH + '\n' + VISIT_BODY,
        HEAD + 'Date of service:\n10-20-26 DOB ' + BIRTH + '\n' + VISIT_BODY,
        HEAD + 'DOS: 10-20-26 MRN: 12345 DOB: ' + BIRTH + '\n' + VISIT_BODY,
        HEAD + 'Synthetic, Alex DOB ' + BIRTH + ' Colonoscopy 10/14/26\n' + COLO_PLAIN,
    )

    def test_a_member_date_a_date_of_birth_states_is_a_member_conflict(self):
        for text in self.BORN + self.UNREAD_BORN:
            with self.subTest(text=text.splitlines()[1][:60] + ' / ' + text.splitlines()[2][:40]):
                self.assertNotEqual(date_fact(text).origin, 'document')
                self.assert_member_conflict(text, ELENA_DATE)
                self.assertFalse(any(BIRTH in quoted for quoted in evidence_text(text)), evidence_text(text))

    def test_the_date_a_candidate_states_still_answers_the_question(self):
        for text in self.BORN:
            with self.subTest(text=text.splitlines()[1][:60] + ' / ' + text.splitlines()[2][:40]):
                self.assert_member_date(text, '2026-10-14')

    def test_a_table_column_keeps_its_label_and_its_cell(self):
        text = self.BORN[0]
        self.assertEqual(evidence_text(text), ['Colonoscopy report - 10/14/2026', 'Date of Service', '10/14/2026'])
        self.assertEqual(evidence_text(self.BORN[1]), ['Colonoscopy report - 10/14/2026', 'DOS: 10/14/26'])

    def test_controls_a_readable_value_s_own_forms(self):
        # the value's first date-shaped run, with a weekday, a month name or an ordinal, is still the label's own
        for header, value in (('Date of service: Tuesday, October 20, 2026 at 9:15', '2026-10-20'),
                              ('Date of service: see 10/20/2026', '2026-10-20'),
                              ('Date of Service | Provider | Location\n10/20/2026 | Dr. A. Synthetic | Office',
                               '2026-10-20'),
                              ('Date of service:\n\n\n20th October 2026, at the clinic', '2026-10-20')):
            with self.subTest(header=header[:40]):
                text = HEAD + header + '\n' + OFFICE_BODY
                self.assert_member_date(text, value)
                self.assert_member_conflict(text, ELENA_DATE)


class MemberDateAgreesOnlyWithAStatedValueRequestTests(EndToEnd):
    """sk:1 end to end: nothing is sent for the member's 1998-01-01, and no act is excluded against it."""

    def test_t5_created_with_the_member_date(self):
        text = (HEAD + 'Colonoscopy report - 10/14/2026\nPatient | DOB | Date of Service\nSynthetic, Alex | ' + BIRTH
                + ' | 10/14/2026\n' + COLO_BODY)
        encounter_id = self.finished(text, service_date=ELENA_DATE)
        self.assert_held(encounter_id)
        self.assert_not_excluded(encounter_id, '45385')

    def test_t4_the_member_date_entered_afterwards(self):
        text = (HEAD + 'Colonoscopy report - 10/14/2026\nPatient: Synthetic, Alex    DOS: 10/14/26 DOB: ' + BIRTH + '\n'
                + COLO_BODY)
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.set_context(encounter_id, {'service_date': ELENA_DATE})
        self.assert_never_sent(encounter_id, ELENA_DATE)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assertNotEqual(self.bucket(encounter_id, '45385'), 'excluded')

    def test_e1_and_e2_an_unread_date_of_service_beside_a_date_of_birth(self):
        e1 = self.finished(HEAD + 'DOS: 10-20-26 DOB: ' + BIRTH + '\n' + OFFICE_BODY, service_date=ELENA_DATE)
        self.assert_held(e1)
        e2 = self.finished(HEAD + 'Date of Service: 10/20/26 Date of Birth: ' + BIRTH + '\n' + OFFICE_BODY)
        self.set_context(e2, {'service_date': ELENA_DATE})
        self.assert_never_sent(e2, ELENA_DATE)
        self.assertEqual(self.dates_sent(e2), [[]])


class QualifierInAnotherFieldHoldsTests(DateAssertions, SimpleTestCase):
    """sk:2 (a regression of 0e639e79f's _opens_field): a capitalised date label one space after a lower-case word read
    nothing before it, so a qualifier in the field before it ('Colonoscopy status: scheduled', 'Prior colonoscopy: yes',
    'Next procedure: colonoscopy') was ignored and a planned or prior labelled date became the documented service date;
    it was sent and an act done on the note's date was excluded against it. The words before such a label belong to
    another field - they are not the label's own words, so they never make it another occurrence's date - but a
    qualifier there still holds the date, as one across a field break always did: the date is asked."""

    LINES = (
        ('Colonoscopy status: scheduled Procedure Date: 11/04/2026', '2026-11-04'),
        ('Prior colonoscopy: yes Procedure Date: 05/01/2019', '2019-05-01'),
        ('Appointment: scheduled Visit Date: 11/24/2026', '2026-11-24'),
        ('Scheduled: yes Procedure Date: 11/04/2026', '2026-11-04'),
        ('Status: scheduled Procedure Date: 11/04/2026', '2026-11-04'),
        ('Next procedure: colonoscopy Procedure Date: 10/14/2029', '2029-10-14'),
        ('Previous colonoscopy: normal Procedure Date: 05/01/2019', '2019-05-01'),
        ('Surveillance due: yes Procedure Date: 10/14/2029', '2029-10-14'),
        ('Next appointment: follow-up Visit Date: 11/24/2026', '2026-11-24'),
        ('Recall in 3 years, next Procedure Date: 10/14/2029', '2029-10-14'),
        ('Indication: s/p polypectomy Procedure Date: 05/01/2019', '2019-05-01'),
    )

    def test_the_planned_or_prior_date_is_asked_never_documented(self):
        for line, other in self.LINES:
            for title in ('', 'GI office visit\n', 'Colonoscopy report\n'):
                with self.subTest(line=line, title=title.strip()):
                    text = HEAD + title + line + '\n' + VISIT_BODY
                    self.assert_never(text, other)
                    self.assert_asked(text, ' '.join(line.split()[-3:]))

    def test_beside_a_dated_title_it_is_a_conflict(self):
        for line, other in self.LINES[:4]:
            with self.subTest(line=line):
                text = HEAD + 'GI office visit - 10/20/2026\n' + line + '\n' + VISIT_BODY
                self.assert_never(text, other)
                self.assert_conflict(text, '2026-10-20', other)

    def test_beside_another_labelled_date_it_is_a_conflict_never_set_aside(self):
        # the words before the label are another field's, never the label's own: the date is held as one this service
        # cannot place (a question beside the note's other labelled date), never set aside as another occurrence's
        text = (HEAD + 'Visit date: 10/27/2026\nIndication: Personal history of colon polyps Date of service: 10/14/2026\n'
                + COLO_PLAIN)
        self.assert_conflict(text, '2026-10-27', '2026-10-14')

    def test_a_history_word_in_the_field_before_holds_the_note_s_own_label_too(self):
        # an over-hold (a known limit): the indication's history words may not date anything, but the reader cannot tell
        for field, label in (('Indication: Personal history of colon polyps', 'Date of service: 10/14/2026'),
                             ('Indication: Recent rectal bleeding', 'Procedure date: 10/14/2026')):
            with self.subTest(field=field):
                text = HEAD + field + ' ' + label + '\n' + COLO_PLAIN
                self.assert_asked(text, label)
                self.assert_member_date(text, '2026-10-14')

    def test_controls_a_field_with_no_qualifier_or_about_something_else(self):
        for line, value in (('Indication: screening Date of service: 10/14/2026', '2026-10-14'),
                            ('Indication: abdominal pain Visit Date: 10/20/2026', '2026-10-20'),
                            ('Last name: synthetic Date of Service: 10/14/2026', '2026-10-14'),
                            ('Last colonoscopy: 05/01/2019 Procedure Date: 10/14/2026', '2026-10-14')):
            with self.subTest(line=line):
                text = HEAD + line + '\n' + COLO_PLAIN
                self.assert_document(text, value)
                self.assert_member_conflict(text, ELENA_DATE)


class QualifierInAnotherFieldRequestTests(EndToEnd):
    """sk:2 end to end (X1 .. X3): no planned or prior date is sent, and the act done on the note's date is never
    excluded against one."""

    def test_x1_a_scheduled_colonoscopy_s_date_under_an_egd_report(self):
        text = (HEAD + 'EGD report\nIndication: dyspepsia.\nColonoscopy status: scheduled Procedure Date: 11/04/2026\n'
                + EGD_BODY)
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assertNotEqual(self.bucket(encounter_id, '43239'), 'excluded')

    def test_x2_a_prior_colonoscopy_s_date(self):
        encounter_id = self.finished(HEAD + 'Colonoscopy report\nPrior colonoscopy: yes Procedure Date: 05/01/2019\n'
                                     + COLO_BODY)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assertNotEqual(self.bucket(encounter_id, '45385'), 'excluded')

    def test_x3_a_scheduled_appointment_s_date(self):
        encounter_id = self.finished(HEAD + 'GI office visit\nAppointment: scheduled Visit Date: 11/24/2026\n'
                                     + OFFICE_BODY)
        self.assertEqual(self.dates_sent(encounter_id), [[]])


class AnotherDisciplineTitleTests(DateAssertions, SimpleTestCase):
    """sk:4 (a regression of 0e639e79f's _title_names): every visit, encounter, consultation or consult title was the
    note's own heading, whatever discipline it named, so 'Surgical pathology consultation: 10/17/2026' above a
    colonoscopy gave the documented date 10/17; it was sent and the snare polypectomy done on 10/14 was excluded as
    historical. A title naming another discipline is never the note's heading, whatever its title word: it is kept as
    the evidence of the date asked, as 'Colonoscopy pathology report' already was."""

    TITLES = ('Surgical pathology consultation: 10/17/2026', 'Pathology consultation: 10/17/2026',
              'Pathology consult - 10/17/2026', 'Path consult: 10/17/2026', 'Pathology encounter - 10/17/2026',
              'Histology visit - 10/17/2026', 'Radiology consultation - 10/09/2026',
              'Anesthesia consultation - 10/13/2026', 'Surgical pathology consultation report: 10/17/2026')

    def test_the_other_discipline_s_date_is_never_documented(self):
        for title in self.TITLES:
            with self.subTest(title=title):
                text = HEAD + title + '\nSpecimen A: sigmoid polyp - tubular adenoma.\n\n' + COLO_BODY
                self.assert_never(text, '2026-10-17', '2026-10-09', '2026-10-13')
                self.assert_asked(text, title)

    def test_a_visit_title_naming_a_role_or_a_finding_of_another_discipline_is_asked(self):
        # an over-hold (a known limit; round 2 read these as the note's own): the member's date the title reads settles it
        for title in ('Nurse practitioner visit - 10/20/2026', 'Anemia and abnormal CT consultation - 10/20/2026'):
            with self.subTest(title=title):
                text = HEAD + title + '\n' + OFFICE_BODY
                self.assert_asked(text, title)
                self.assert_member_date(text, '2026-10-20')

    def test_controls_this_service_s_encounter_titles(self):
        for title, value in (('GI visit - 10/20/2026', '2026-10-20'), ('GI consultation - 10/20/2026', '2026-10-20'),
                             ('Office visit - 10/20/2026', '2026-10-20'),
                             ('Hepatology consult: 10/20/2026', '2026-10-20'),
                             ('Endoscopic ultrasound report: 10/14/2026', '2026-10-14'),
                             ('Colonoscopy encounter - 10/14/2026', '2026-10-14')):
            with self.subTest(title=title):
                text = HEAD + title + '\n' + VISIT_BODY
                self.assert_document(text, value)
                self.assert_member_conflict(text, ELENA_DATE)


class AnotherDisciplineTitleRequestTests(EndToEnd):
    """sk:4 end to end (E4): the pathology consultation's date is never sent and the snare polypectomy done on the
    colonoscopy's date is never excluded against it."""

    def test_e4_a_surgical_pathology_consultation_above_the_colonoscopy(self):
        text = (HEAD + 'Surgical pathology consultation: 10/17/2026\nSpecimen A: sigmoid polyp - tubular adenoma.\n\n'
                + COLO_BODY)
        encounter_id = self.finished(text)
        self.assertEqual(self.dates_sent(encounter_id), [[]])
        self.assertNotEqual(self.bucket(encounter_id, '45385'), 'excluded')
