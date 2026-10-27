"""Repair round ec5, cluster REPORTFACTS: how facts, coverage and completeness are described. Synthetic data only; the
provider is an in-process fake (no network).

Each class reproduces a finding of refutation round r1 (ledger verdicts at 8f8a3b48, re-checked at 8985dde42) with its
smallest input and asserts the wording that is true of the persisted state, beside a control that must not change.
"""
import json
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from tests.test_pipeline_api import OFFICE_NOTE
from tests.test_repairs_pipeline import LIVE
from tests.test_repairs_status_r2_validation_api import ApiCase
from tests.test_services_reconcile import check, proposal, run, sel, span

APP = Path(settings.BASE_DIR) / 'studio' / 'static' / 'studio' / 'app.js'


def browser(expression, data):
    """The value of a JavaScript ``expression`` over ``app`` (app.js's exports) and ``data`` (JSON), as the page
    computes it - node runs the file itself, so a screen is checked as it renders."""
    node = shutil.which('node')
    if node is None:
        raise AssertionError('node is not installed; the screen checks need it')
    script = (f'const app = require({json.dumps(str(APP))}); const data = JSON.parse(process.argv[1]); '
              f'process.stdout.write(JSON.stringify({expression}));')
    done = subprocess.run([node, '-e', script, json.dumps(data)], capture_output=True, text=True, timeout=60)
    if done.returncode:
        raise AssertionError(done.stderr[-2000:])
    return json.loads(done.stdout)


def section(text, title):
    """The body of a report section: the lines after its title, up to the blank line that ends it."""
    lines = text.split('\n')
    body = []
    for line in lines[lines.index(title) + 1:]:
        if not line:
            break
        body.append(line)
    return '\n'.join(body)

VISIT_TIME = 'Total time on the date of the encounter was 24 minutes.'
SCHEDULED = 'A colonoscopy is scheduled for 2026-12-01.\n'
PLACE = 'Place of service: Office, in-person outpatient visit\n'
ENTERED = 'Entered by a workspace member as encounter metadata (not clinical documentation): '


class MemberEnteredValuesAreNeverDocumentedTests(SimpleTestCase):
    """context-7: a member's setting (origin 'user', stored with the note "not clinical documentation") was listed under
    "Documented:" in the facts.required check and under "Documented facts:" in the proposal rationale, which the TXT
    report prints. A member value supplies a fact the document does not give (ARCHITECTURE 5.2): it is named as
    entered by a member, never as documented."""

    def visit(self, text, **user_values):
        result = run(text, [sel('99213', span(text, VISIT_TIME))], user_values=user_values)
        return proposal(result, '99213')

    def test_a_member_setting_is_named_as_entered_never_as_documented(self):
        text = OFFICE_NOTE.replace(PLACE, '').replace(SCHEDULED, '')
        item = self.visit(text, setting='office')
        self.assertEqual(item.status, 'ready')  # unchanged: a member value supplies a fact the document does not give
        detail = check(item, 'facts.required').detail
        self.assertEqual(check(item, 'facts.required').status, 'pass')
        self.assertIn(f'{ENTERED}place of service = office.', detail)
        self.assertNotIn('place of service = office', detail.split(ENTERED)[0])
        self.assertIn('Documented: new or established patient status = established', detail)
        self.assertIn(f'{ENTERED}place of service = office.', item.rationale)
        documented = item.rationale.split('Documented facts: ', 1)[1].split('.', 1)[0]
        self.assertNotIn('place of service', documented)
        self.assertIn('new or established patient status = established', documented)

    def test_control_a_documented_setting_stays_documented(self):
        item = self.visit(OFFICE_NOTE.replace(SCHEDULED, ''))
        detail = check(item, 'facts.required').detail
        self.assertIn('Documented: place of service = office;', detail)
        self.assertNotIn(ENTERED, detail)
        self.assertIn('Documented facts: place of service = office;', item.rationale)
        self.assertNotIn(ENTERED, item.rationale)


STATUS_LINE = 'Patient status: Established patient, last seen 2026-03-02.\n'


class VisitQuestionNamesADocumentedConflictTests(SimpleTestCase):
    """context-6: with no E/M proposal (the provider selects nothing, fails, or nothing is sent while a member date
    conflict holds), the visit's own question said "The documented office / outpatient visit does not state its patient
    status" while the stored context fact is a conflict between two documented values. A conflict is asked as one, both
    sides quoted, as the E/M proposal's own question words it (checks.fact_clarifications)."""

    def visit_question(self, text, fact, **user_values):
        result = run(text, [], user_values=user_values)
        found = [c for c in result.clarifications if c.fact == fact and c.family == 'gi.office_em']
        self.assertEqual(len(found), 1, [(c.fact, c.reason) for c in result.clarifications])
        return found[0]

    def test_two_documented_patient_statuses_are_asked_as_a_conflict(self):
        text = OFFICE_NOTE.replace(SCHEDULED, '').replace(STATUS_LINE, STATUS_LINE + 'New patient to this clinician.\n')
        asked = self.visit_question(text, 'patient_status')
        self.assertEqual(asked.reason, 'The document gives conflicting values for the new or established patient '
                                       'status: “Patient status: Established”, “New patient”.')
        self.assertEqual(asked.question, 'Was the patient new or established to this clinician and group?')

    def test_two_documented_settings_are_asked_as_a_conflict(self):
        text = OFFICE_NOTE.replace(SCHEDULED, '').replace(PLACE, PLACE + 'This was a telehealth visit.\n')
        asked = self.visit_question(text, 'setting')
        self.assertTrue(asked.reason.startswith('The document gives conflicting values for the place of service: “'),
                        asked.reason)
        self.assertNotIn('does not state', asked.reason)

    def test_controls_a_missing_status_and_a_member_conflict_keep_their_wording(self):
        text = OFFICE_NOTE.replace(SCHEDULED, '').replace(STATUS_LINE, '')
        self.assertEqual(self.visit_question(text, 'patient_status').reason,
                         'The documented office / outpatient visit does not state its patient status.')
        # a member's value unlike the document's single one is asked once, as that conflict (encounter question)
        result = run(OFFICE_NOTE.replace(SCHEDULED, ''), [], user_values={'patient_status': 'new'})
        reasons = [c.reason for c in result.clarifications if c.fact == 'patient_status']
        self.assertEqual(len(reasons), 1, reasons)
        self.assertTrue(reasons[0].startswith('The new or established patient status is in conflict. Encounter '
                                              'metadata entered by a workspace member gives new; the document gives '
                                              'established.'), reasons[0])


SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
EUS = (SYNTHETIC + 'Date of service: 2026-10-14\nIndication: EUS for evaluation of a pancreatic head mass.\n'
       'Procedure: Upper endoscopic ultrasound.\nFindings: The echoendoscope was advanced to the second portion of the '
       'duodenum. A 2 cm hypoechoic mass in the pancreatic head was sampled by fine-needle aspiration with three '
       'passes. Cold forceps biopsies were taken from the gastric antrum.\n')
FNA = 'was sampled by fine-needle aspiration with three passes'
ANTRUM = ' Cold forceps biopsies were taken from the gastric antrum.'
UPPER_GI = 'read under the upper GI family'


class EusForcepsBiopsyIsNeverHiddenTests(SimpleTestCase):
    """report-0: in an EUS-only report a forceps biopsy of the gastric antrum was filed as "not separately reported - A
    forceps biopsy at the same upper examination is read under the upper GI family" although the inventory holds no
    upper GI service, so nothing read it: UNRESOLVED said none and coding reached "reviewed". The EUS profile's rule is
    applied only when an upper GI service of the encounter documents such a biopsy; otherwise the biopsy is listed for
    the reviewer, never bundled. The needle sampling the reader also read as a "biopsy" (technique needle) is the
    fine-needle aspiration itself, reconciled as that act - never a forceps biopsy read under another family."""

    def assess(self, text, code='43242', quote=FNA):
        result = run(text, [sel(code, span(text, quote))])
        return result, result.completeness

    def test_a_forceps_biopsy_with_no_upper_endoscopy_is_listed_for_the_reviewer(self):
        result, done = self.assess(EUS)
        self.assertEqual([(s['family'], s['status']) for s in result.services['services']], [('gi.eus', 'performed')])
        self.assertEqual([(u['service'], u['act'], u['reason']) for u in done['unresolved_items']],
                         [('S1', 'biopsy', 'unsupported')])
        self.assertTrue(done['unresolved_items'][0]['label'].startswith(
            'forceps biopsy at the gastric antrum in the endoscopic ultrasound: '), done['unresolved_items'][0]['label'])
        self.assertEqual([b for b in done['bundled'] if UPPER_GI in b['why']], [])
        self.assertEqual(done['state'], 'incomplete')
        self.assertEqual(next(c for c in result.encounter_checks if c.id == 'services.unresolved').status, 'warn')
        self.assertEqual(proposal(result, '43242').status, 'ready')  # unchanged: the FNA code reads its own act

    def test_the_needle_sampling_is_the_fine_needle_aspiration_never_a_forceps_biopsy(self):
        text = EUS.replace(ANTRUM, '')
        result, done = self.assess(text)
        self.assertEqual((done['bundled'], done['unresolved_items'], done['state']), ([], [], 'complete_pending_review'))
        # with no code for the needle sampling, it is listed once, as the fine-needle aspiration
        result, done = self.assess(text, '43259', 'The echoendoscope was advanced to the second portion of the duodenum')
        self.assertEqual([(u['act'], u['reason']) for u in done['unresolved_items']], [('fna', 'not_covered')])
        self.assertTrue(done['unresolved_items'][0]['label'].startswith('fine-needle aspiration or biopsy of the 2 cm '
                                                                       'hypoechoic mass in the pancreatic head'),
                        done['unresolved_items'][0]['label'])
        self.assertEqual(done['bundled'], [])

    def test_control_an_egd_with_the_eus_still_reconciles_the_biopsy_under_the_egd(self):
        text = EUS.replace('Procedure: Upper endoscopic ultrasound.', 'Procedure: EGD and upper endoscopic ultrasound.')
        result, done = self.assess(text)
        self.assertEqual([(s['family'], s['included_in']) for s in result.services['services']],
                         [('gi.eus', ''), ('gi.egd', 'S1')])
        self.assertEqual([(u['service'], u['label'], u['reason']) for u in done['unresolved_items']],
                         [('S2', 'forceps biopsy at the gastric antrum in the upper endoscopy', 'not_covered')])

    def test_the_rule_bundles_only_what_an_upper_gi_service_of_the_encounter_documents(self):
        from studio.gi.services import Act, DocumentedService, ServiceInventory
        from studio.validation import reconcile
        biopsy = Act('S1-A1', 'S1', 'biopsy', 'performed', 'physician', ('gastric antrum',), technique='forceps')
        fna = Act('S1-A2', 'S1', 'fna', 'performed', 'physician', ('pancreatic head',), technique='needle')
        eus = DocumentedService('S1', 'gi.eus', 'eus', 'performed', acts=(biopsy, fna))
        alone = ServiceInventory('test', services=(eus,))
        unresolved, bundled, _ = reconcile.reconcile(alone, [('43242', 'gi.eus')])
        self.assertEqual(([(u.act, u.reason) for u in unresolved], bundled), ([('biopsy', 'unsupported')], []))
        egd_biopsy = Act('S2-A1', 'S2', 'biopsy', 'performed', 'physician', ('gastric body',), technique='forceps')
        egd = DocumentedService('S2', 'gi.egd', 'egd', 'performed', acts=(egd_biopsy,), included_in='S1')
        both = ServiceInventory('test', services=(eus, egd))
        unresolved, bundled, _ = reconcile.reconcile(both, [('43242', 'gi.eus')])
        self.assertEqual([(b.service, b.act) for b in bundled], [('S1', 'biopsy')])
        self.assertIn(UPPER_GI, bundled[0].why)
        self.assertEqual([(u.service, u.act, u.reason) for u in unresolved], [('S2', 'biopsy', 'not_covered')])
        # an upper GI service that documents no biopsy reads none: the EUS biopsy is listed, never bundled
        empty = ServiceInventory('test', services=(eus, DocumentedService('S2', 'gi.egd', 'egd', 'performed',
                                                                          included_in='S1')))
        unresolved, bundled, _ = reconcile.reconcile(empty, [('43242', 'gi.eus')])
        self.assertEqual(([(u.service, u.act, u.reason) for u in unresolved], bundled),
                         ([('S1', 'biopsy', 'unsupported')], []))


COLONOSCOPY = (SYNTHETIC + 'Procedure report\nDate of service: 2026-10-14\nProcedure: Colonoscopy.\n'
               'Findings: The colonoscope was advanced to the cecum. A 7 mm sessile polyp in the sigmoid colon was '
               'removed with a cold snare.\nImpression: Polyp removed.\n')
POLYP = 'A 7 mm sessile polyp in the sigmoid colon was removed with a cold snare.'


@override_settings(**LIVE)
class RejectedCodeAccountsForNothingTests(ApiCase, TestCase):
    """report-6: a colonoscopy with a cold-snare polypectomy, 45385 selected and rejected by the reviewer. The reviewed
    report printed "accounted for by: 45385" under DOCUMENTED SERVICES (and the screen "Accounted for by: 45385.")
    beside "REJECTED: 45385" and "APPROVED SELECTIONS: None.": the assessment-time reconciliation was printed as if the
    rejected code still accounted for the service. A code the reviewer rejected is printed as rejected, never as
    accounting for the service."""

    def screen(self, encounter_id):
        return browser('app.documentedServices(data)', self.detail(encounter_id))

    def test_a_rejected_code_never_accounts_for_the_service(self):
        encounter_id = self.run_note(COLONOSCOPY, ('45385', POLYP))
        self.assertEqual(self.proposal(encounter_id, '45385')['status'], 'ready')
        self.assertEqual(self.decide(encounter_id, '45385', 'reject').status_code, 201)
        for kind in ('draft', 'reviewed'):
            with self.subTest(kind=kind):
                documented = section(self.report_text(encounter_id, kind), 'DOCUMENTED SERVICES')
                self.assertNotIn('accounted for by: 45385', documented)
                self.assertIn('      rejected by the reviewer: 45385 — no other selected code accounts for this '
                              'service', documented)
        shown = self.screen(encounter_id)
        self.assertNotIn('Accounted for by: 45385', shown)
        self.assertIn('Rejected by the reviewer: 45385; no other selected code accounts for this service.', shown)

    def test_control_an_approved_or_undecided_code_still_accounts_for_the_service(self):
        encounter_id = self.run_note(COLONOSCOPY, ('45385', POLYP))
        self.assertIn('      accounted for by: 45385', section(self.report_text(encounter_id, 'draft'),
                                                                'DOCUMENTED SERVICES'))
        self.assertIn('Accounted for by: 45385.', self.screen(encounter_id))
        self.assertEqual(self.decide(encounter_id, '45385', 'approve').status_code, 201)
        documented = section(self.report_text(encounter_id, 'reviewed'), 'DOCUMENTED SERVICES')
        self.assertIn('      accounted for by: 45385', documented)
        self.assertNotIn('rejected by the reviewer', documented)
        self.assertNotIn('Rejected by the reviewer', self.screen(encounter_id))


TWO_DATES = OFFICE_NOTE.replace('Date of service: 2026-10-20\n', 'Date of service: 2026-10-20\nDate of service: 2026-10-23\n')
MEMBER_SIDE = 'member-entered encounter metadata differs from the document'
SCREEN = ('[app.factValue(data.facts.service_date, null, true), app.metaFact(data.facts.service_date, null, '
          '"Service date", true), app.factValue(data.facts.setting, {office: "Office", telehealth: "Telehealth"}), '
          'app.metaFact(data.facts.setting, {office: "Office"}, "Setting"), app.documentRow(data.row), '
          'app.inviteMarkup([data.row])]')


@override_settings(**LIVE)
class MemberConflictIsNeverConflictingDocumentationTests(ApiCase, TestCase):
    """context-5: a member's service date (or setting) unlike the document's single value is stored as a member
    conflict (context.is_member_conflict). The readers outside checks, engine and reconcile never asked that predicate:
    the TXT's ENCOUNTER CONTEXT said "Service date: conflicting documentation", the source paper said "Conflicting
    values documented", the review header "Service date not documented" and the documents list "Not documented" - while
    the document gives exactly one date. Every reader now words a member conflict as one; a conflict within the
    document stays "conflicting documentation", and a conflict is never shown as not documented."""

    def readings(self, encounter_id):
        detail = self.detail(encounter_id)
        rows = self.client.get('/api/encounters').json()['encounters']
        (row,) = [r for r in rows if r['id'] == encounter_id]
        return detail, row, browser(SCREEN, {'facts': detail['context']['facts'], 'row': row})

    def context_lines(self, encounter_id):
        return section(self.report_text(encounter_id, 'draft'), 'ENCOUNTER CONTEXT')

    def test_a_member_service_date_conflict_is_worded_as_one_everywhere(self):
        encounter_id = self.create(OFFICE_NOTE, service_date='1998-01-01')
        from tests.test_pipeline_api import drain
        drain()
        context = self.context_lines(encounter_id)
        self.assertIn(f'  Service date: {MEMBER_SIDE} — Encounter metadata entered by a workspace member gives '
                      '1998-01-01; the document gives 2026-10-20.', context)
        self.assertNotIn('conflicting documentation', context)
        detail, row, (paper, header, _, _, listed, invite) = self.readings(encounter_id)
        self.assertTrue(detail['context']['facts']['service_date']['member_conflict'])
        self.assertFalse(detail['context']['facts']['setting']['member_conflict'])
        self.assertEqual((row['service_date'], row['service_date_conflict']), (None, True))
        self.assertEqual(paper, 'Member entry differs from the document')
        self.assertEqual(header, 'Service date: member entry differs from the document')
        self.assertIn('<span class="doc-row-date">In conflict</span>', listed)
        self.assertIn('service date in conflict', invite)
        self.assertNotIn('ot documented', listed + invite + paper + header)

    def test_a_member_setting_conflict_is_worded_as_one(self):
        encounter_id = self.run_note(OFFICE_NOTE, ('99213', VISIT_TIME))
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'telehealth'})
        self.assertEqual(response.status_code, 201, response.content)
        from tests.test_pipeline_api import drain
        drain()
        context = self.context_lines(encounter_id)
        self.assertIn(f'  Setting: {MEMBER_SIDE} — Encounter metadata entered by a workspace member gives telehealth; '
                      'the document gives office.', context)
        self.assertNotIn('conflicting documentation', context)
        _, _, (_, _, paper, header, _, _) = self.readings(encounter_id)
        self.assertEqual((paper, header), ('Member entry differs from the document',
                                           'Setting: member entry differs from the document'))

    def test_controls_a_documented_conflict_and_a_single_documented_date(self):
        encounter_id = self.run_note(TWO_DATES, ('99213', VISIT_TIME))
        context = self.context_lines(encounter_id)
        self.assertIn('  Service date: conflicting documentation — Conflicting documented values: 2026-10-20, '
                      '2026-10-23.', context)
        detail, row, (paper, header, _, _, listed, invite) = self.readings(encounter_id)
        self.assertFalse(detail['context']['facts']['service_date']['member_conflict'])
        self.assertEqual((row['service_date'], row['service_date_conflict']), (None, True))
        self.assertEqual((paper, header), ('Conflicting values documented', 'Service date conflict'))
        self.assertIn('<span class="doc-row-date">In conflict</span>', listed)
        encounter_id = self.run_note(OFFICE_NOTE, ('99213', VISIT_TIME))
        self.assertIn('  Service date: 2026-10-20 (documented)', self.context_lines(encounter_id))
        detail, row, (paper, header, _, _, listed, _) = self.readings(encounter_id)
        self.assertEqual((row['service_date'], row['service_date_conflict']), ('2026-10-20', False))
        self.assertEqual((paper, header), ('20 October 2026', '20 Oct 2026'))
        self.assertIn('<span class="doc-row-date">20 Oct 2026</span>', listed)


SEGMENTS = ', '.join(f'segment {i} of the colon showed normal vascular pattern without erythema' for i in range(1, 17))
LONG_FINDINGS = ('Findings: The colonoscope was advanced to the cecum and on careful withdrawal ' + SEGMENTS
                 + ', and a 4 mm polyp in the transverse colon was removed with cold forceps biopsy.')
READ_IN_PART = (SYNTHETIC + 'Procedure report\nDate of service: 2026-10-14\nProcedure: Colonoscopy.\n' + POLYP + '\n'
                + LONG_FINDINGS + '\nImpression: Polyps removed.\n')
UNRESOLVED_TITLE = 'UNRESOLVED DOCUMENTED SERVICES — NO SUPPORTED PROPOSAL'


@override_settings(**LIVE)
class ReadInPartSpeaksForWhatWasReadTests(ApiCase, TestCase):
    """report-8: a findings sentence over the 1,200-character act-reading bound, whose unread tail documents a cold-forceps
    removal inside the colonoscopy that WAS read. The reading recorded the problem (state 'partial'), but UNRESOLVED
    closed with "none among the services read: ... so a service it did not read is not listed" and the services.unresolved
    check passed with "Every documented act that the coverage catalogue reconciles has a selected proposal": both false
    of a service that was read in part. They now speak for what was read, and say that a service or act in the part not
    read is not listed."""

    def test_a_reading_problem_inside_a_read_service_is_not_hidden_by_the_closing_line(self):
        self.assertGreater(len(LONG_FINDINGS), 1200)
        encounter_id = self.run_note(READ_IN_PART, ('45385', POLYP))
        detail = self.detail(encounter_id)
        problems = detail['assessment']['services']['problems']
        self.assertTrue(any('was read for acts only in its first 1,200 characters' in p for p in problems), problems)
        text = self.report_text(encounter_id, 'draft')
        self.assertEqual(section(text, UNRESOLVED_TITLE),
                         '  - none among what was read: the documented-service reading reported a problem, listed under '
                         'DOCUMENTED SERVICES, so a service or act in the part it did not read is not listed')
        self.assertEqual(section(text, 'CONFLICTS IN THE RECORD'),
                         '  - none among what was read: the documented-service reading reported a problem')
        (check_row,) = [c for c in detail['assessment']['encounter_checks'] if c['id'] == 'services.unresolved']
        self.assertEqual(check_row['status'], 'warn')
        self.assertTrue(check_row['detail'].startswith('Among what was read, every documented act'), check_row['detail'])
        self.assertIn('so a service or act in the part it did not read is not covered by this check',
                      check_row['detail'])

    def test_control_a_reading_without_a_problem_keeps_its_wording(self):
        encounter_id = self.run_note(COLONOSCOPY, ('45385', POLYP))
        detail = self.detail(encounter_id)
        self.assertEqual(detail['assessment']['services']['problems'], [])
        text = self.report_text(encounter_id, 'draft')
        self.assertEqual(section(text, UNRESOLVED_TITLE), '  - none: every documented act the catalogue reconciles has '
                                                          'a selected proposal or is not separately reported')
        (check_row,) = [c for c in detail['assessment']['encounter_checks'] if c['id'] == 'services.unresolved']
        self.assertEqual(check_row['status'], 'pass')
        self.assertTrue(check_row['detail'].startswith('Every documented act that the coverage catalogue reconciles'))


# --- findings that no longer reproduce at 8985dde42: kept as guards ---------------------------------------------------

EUS_BESIDE_COLONOSCOPY = (SYNTHETIC + 'Date of service: 2026-10-14\nEUS: Normal pancreas and common bile duct; no mass.\n'
                          'Colonoscopy: The colonoscope was advanced to the cecum. ' + POLYP + '\n')


@override_settings(**LIVE)
class UnestablishedServiceKeepsCodingIncompleteTests(ApiCase, TestCase):
    """report-1 (repaired by WIP 8p, 9086a4271; re-checked here): a findings-only EUS (or ERCP) section beside a coded
    colonoscopy is read 'uncertain' with no proposal and no question. Coding completeness had said "Every documented
    service has a proposal" in the draft, the reviewed TXT, the CSV and the screen. It says incomplete, naming the
    service no proposal reads."""

    def test_an_uncertain_service_no_proposal_reads_keeps_coding_incomplete(self):
        for first in ('EUS: Normal pancreas and common bile duct; no mass.', 'ERCP: Normal cholangiogram; no stones.'):
            with self.subTest(first=first):
                text = EUS_BESIDE_COLONOSCOPY.replace('EUS: Normal pancreas and common bile duct; no mass.', first)
                encounter_id = self.run_note(text, ('45385', POLYP))
                services = self.detail(encounter_id)['assessment']['services']['services']
                self.assertEqual([s['status'] for s in services], ['uncertain', 'performed'])
                self.assertEqual(self.decide(encounter_id, '45385', 'approve').status_code, 201)
                for kind in ('draft', 'reviewed'):
                    coding = section(self.report_text(encounter_id, kind), 'CODING COMPLETENESS')
                    self.assertIn('State: incomplete', coding)
                    self.assertIn('1 documented service not established as performed and read by no proposal', coding)
                    self.assertNotIn('Every documented service has a proposal', coding)
                response = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'csv'})
                csv_text = self.client.get(f'/api/reports/{response.json()["id"]}/download')
                body = b''.join(csv_text.streaming_content if csv_text.streaming else [csv_text.content]).decode()
                (row,) = [line for line in body.split('\r\n') if '"coding_completeness"' in line]
                self.assertIn('"incomplete"', row)
                banner = browser('app.codingBanner(data)', self.detail(encounter_id))
                self.assertIn('Coding for this encounter is incomplete', banner)


class CoverageClaimsOnlyWhatRunsTests(SimpleTestCase):
    """report-4 and report-9 (repaired by WIP 8j, e9b7c5e23; re-checked here). COVERAGE.md had listed the EUS stations as
    verification evidence "which separate limited from full examinations" while no code reads CodeProfile.exam; and the
    catalogue's docstrings cited tests/fixtures/services and tests/test_services_catalogue.py, which never existed."""

    def test_no_limited_against_full_verification_is_claimed_while_nothing_reads_the_exam_class(self):
        from studio.gi import catalogue
        studio = Path(settings.BASE_DIR) / 'studio'
        readers = [str(path.relative_to(studio)) for path in studio.rglob('*.py')
                   if path.name != 'catalogue.py' and '.exam' in path.read_text(encoding='utf-8').replace('.example', '')]
        if readers:
            self.skipTest(f'a module reads the examination class now: {readers}')  # then the claim may be checked there
        coverage = catalogue.render_markdown()
        self.assertNotIn('separate limited from full', coverage)
        self.assertIn("whether the examination was limited or full is the reviewer's to judge; this catalogue does not "
                      'check it', coverage)

    def test_every_artifact_the_catalogue_cites_exists(self):
        import re
        from studio.gi import catalogue
        root = Path(settings.BASE_DIR)
        cited = set(re.findall(r'tests/[\w/.-]*\w', (catalogue.__doc__ or '') + (catalogue.render_markdown.__doc__ or '')))
        self.assertTrue(cited)
        self.assertEqual(sorted(path for path in cited if not (root / path).exists()), [])


MANOMETRY = (SYNTHETIC + 'Date of service: 2026-10-14\nPlace of service: Hospital outpatient department\n'
             'Billing: professional\nProcedure: High-resolution esophageal manometry.\n'
             'Findings: Esophageal manometry was performed and showed normal peristalsis.\n')
STUDY = 'Esophageal manometry was performed and showed normal peristalsis.'


class BillingContextIsWordedByItsOriginTests(SimpleTestCase):
    """new (found in this cluster's territory, the context-5 class inside the engine): the professional/technical
    component consideration said "which one applies depends on the billing context (not documented)" when the billing
    context is a member conflict ("Billing: professional" against a member's facility) or a conflict within the
    document. It words the billing context by its stored origin, and names a member's value as entered by a member."""

    def considerations(self, text, **user_values):
        from datetime import date
        from studio.gi import context as gi_context
        from studio.gi import detect
        from studio.reference.store import InMemoryReferenceLookup
        from studio.types import NormalizedResponse
        from studio.validation.engine import assess
        from tests.test_validation import PFS_INFO, pfs
        rows = {('91010', ''): pfs('A', 'XXX', '0', pctc='1'), ('91010', '26'): pfs('A', 'XXX', '0', pctc='1'),
                ('91010', 'TC'): pfs('A', 'XXX', '0', pctc='1')}
        facts = gi_context.merge_user_values(gi_context.extract_context(text), user_values)
        day = date(2026, 10, 14)
        result = assess(text=text, pages=(), context=facts, routing=detect.route(text, day),
                        normalized=NormalizedResponse('replay', 'test@1', (sel('91010', span(text, STUDY)),)),
                        reference=InMemoryReferenceLookup([PFS_INFO], {PFS_INFO.key: rows}), service_date=day,
                        provider_status='succeeded')
        (consideration,) = proposal(result, '91010').modifier_considerations
        return consideration.split('depends on the billing context (', 1)[1].split('). No modifier', 1)[0]

    def test_a_billing_conflict_is_never_called_not_documented(self):
        self.assertEqual(self.considerations(MANOMETRY, billing_context='facility'),
                         'in conflict: member-entered encounter metadata differs from the document')
        both = MANOMETRY.replace('Billing: professional\n', 'Billing: professional\nBilling: facility\n')
        self.assertEqual(self.considerations(both), 'conflicting documented values')

    def test_a_member_value_is_named_as_entered_and_the_controls_keep_their_wording(self):
        alone = MANOMETRY.replace('Billing: professional\n', '')
        self.assertEqual(self.considerations(alone, billing_context='facility'),
                         'facility, entered by a workspace member as encounter metadata')
        self.assertEqual(self.considerations(MANOMETRY), 'professional')
        self.assertEqual(self.considerations(alone), 'not documented')


# --- the skeptic round on these repairs (ec5): what the repairs above left out -----------------------------------------

GASTROSCOPY = ('Upper endoscopy report\nThe gastroscope was advanced to the second portion of the duodenum. Cold forceps '
               'biopsies were taken from the gastric antrum.\n')
RECTAL_EUS = ('Rectal endoscopic ultrasound report\nThe radial echoendoscope was advanced into the rectum. A 3 cm rectal '
              'mass was staged as uT2N0. A 9 mm perirectal lymph node was sampled by fine-needle aspiration with two '
              'passes. Cold forceps biopsies were taken from the rectal mass.\n')
UPPER_EUS = ('Endoscopic ultrasound report\nThe linear echoendoscope was advanced to the second portion of the duodenum. '
             'A 2 cm hypoechoic mass in the pancreatic head was sampled by fine-needle aspiration with three passes. Cold '
             'forceps biopsies were taken from the duodenal bulb.\n')
SESSION = SYNTHETIC + 'Date of service: 2026-10-14\nPlace of service: Ambulatory surgery center\n'
ANTRAL = 'Cold forceps biopsies were taken from the gastric antrum.'
NODE_FNA = 'was sampled by fine-needle aspiration with two passes'
NOT_UPPER = ('the document does not place it at an upper GI site of an upper GI examination, so no upper GI endoscopy of '
             'this encounter reads it, and no code profile of this service accounts for it')


@override_settings(**LIVE)
class LowerEusBiopsyIsNeverReadUnderTheUpperFamilyTests(ApiCase, TestCase):
    """skeptic of the report-0 repair (9d9fb8e17): an upper endoscopy report (antral forceps biopsy, 43239 selected) beside
    a rectal EUS (perirectal node FNA, 45392 selected, and cold forceps biopsies of the rectal mass). The rectal biopsy
    was filed as "not separately reported - A forceps biopsy at the same upper examination is read under the upper GI
    family ..." because the rule asked only whether SOME upper GI service documented a biopsy: UNRESOLVED said none and
    coding reached "reviewed" - false of the persisted inventory (a biopsy at the rectum, during a lower EUS; no upper
    GI service reads it). The rule holds only for an act at an upper GI site of an upper examination, beside an upper
    endoscopy that documents a biopsy of its own; any other is listed for the reviewer."""

    def test_a_forceps_biopsy_at_a_rectal_eus_is_listed_never_read_under_the_upper_family(self):
        encounter_id = self.run_note(SESSION + GASTROSCOPY + RECTAL_EUS, ('43239', ANTRAL), ('45392', NODE_FNA))
        assessment = self.detail(encounter_id)['assessment']
        (eus,) = [s for s in assessment['services']['services'] if s['family'] == 'gi.eus']
        self.assertIn((['rectum'], 'forceps', 'performed'), [(a['anatomy'], a['technique'], a['status'])
                                                              for a in eus['acts'] if a['kind'] == 'biopsy'])
        done = assessment['completeness']
        self.assertEqual(done['bundled'], [])
        self.assertEqual([(u['service'], u['act'], u['reason'], u['label']) for u in done['unresolved_items']],
                         [(eus['id'], 'biopsy', 'unsupported',
                           f'forceps biopsy at the rectum in the endoscopic ultrasound: {NOT_UPPER}')])
        self.assertEqual(done['state'], 'incomplete')
        (row,) = [c for c in assessment['encounter_checks'] if c['id'] == 'services.unresolved']
        self.assertEqual(row['status'], 'warn')
        for code in ('43239', '45392'):
            self.assertEqual(self.proposal(encounter_id, code)['status'], 'ready', code)  # unchanged
            self.assertEqual(self.decide(encounter_id, code, 'approve').status_code, 201)
        reviewed = self.report_text(encounter_id, 'reviewed')
        self.assertNotIn('read under the upper GI family', section(reviewed, 'DOCUMENTED SERVICES'))
        self.assertIn(f'  - forceps biopsy at the rectum in the endoscopic ultrasound: {NOT_UPPER} [unsupported]',
                      section(reviewed, UNRESOLVED_TITLE))
        coding = section(reviewed, 'CODING COMPLETENESS')
        self.assertIn('State: incomplete', coding)
        self.assertNotIn('State: reviewed', coding)
        self.assertNotIn('read under the upper GI family', browser('app.documentedServices(data)',
                                                                   self.detail(encounter_id)))


class ReadUnderOnlyWhereTheOtherFamilyCouldReadTests(SimpleTestCase):
    """The same rule on the reading and on hand-built inventories: the act's own site (its anatomy, its lesion) and the
    sites its examination documents (the service's passages, extent, lesions and acts) decide whether the upper GI
    family could read it; with no site at all it is not placed there (fail closed: listed, never bundled)."""

    def test_control_a_biopsy_at_an_upper_site_of_an_upper_eus_is_still_read_under_the_egd(self):
        text = SESSION + GASTROSCOPY + UPPER_EUS
        result = run(text, [sel('43239', span(text, ANTRAL)),
                            sel('43242', span(text, 'was sampled by fine-needle aspiration with three passes'))])
        done = result.completeness
        self.assertEqual([(b['act'], b['label']) for b in done['bundled']],
                         [('biopsy', 'forceps biopsy at the duodenal bulb')])
        self.assertIn(UPPER_GI, done['bundled'][0]['why'])
        self.assertEqual(done['unresolved_items'], [])
        # the rectal EUS alone, and beside the upper endoscopy: listed, never bundled
        for text in (SESSION + RECTAL_EUS, SESSION + GASTROSCOPY + RECTAL_EUS):
            with self.subTest(text=text[len(SESSION):len(SESSION) + 30]):
                codes = [sel('45392', span(text, NODE_FNA))] + ([sel('43239', span(text, ANTRAL))] if ANTRAL in text
                                                                 else [])
                done = run(text, codes).completeness
                self.assertEqual(done['bundled'], [])
                self.assertEqual([(u['act'], u['reason'], u['label']) for u in done['unresolved_items']],
                                 [('biopsy', 'unsupported',
                                   f'forceps biopsy at the rectum in the endoscopic ultrasound: {NOT_UPPER}')])
                self.assertEqual(done['state'], 'incomplete')

    def test_the_act_and_its_examination_must_both_be_upper(self):
        from studio.gi.services import Act, DocumentedService, Lesion, ServiceInventory
        from studio.types import Span
        from studio.validation import reconcile

        def outcome(eus):
            egd = DocumentedService('S2', 'gi.egd', 'egd', 'performed', included_in='S1', acts=(
                Act('S2-A1', 'S2', 'biopsy', 'performed', 'physician', ('gastric antrum',), technique='forceps'),))
            unresolved, bundled, _ = reconcile.reconcile(ServiceInventory('test', services=(eus, egd)),
                                                         [('43239', 'gi.egd'), ('43242', 'gi.eus')])
            return ([(b.service, b.act) for b in bundled],
                    [(u.service, u.act, u.reason, u.label.split(': ', 1)[1]) for u in unresolved])

        def eus(*acts, evidence=(), lesions=()):
            return DocumentedService('S1', 'gi.eus', 'eus', 'performed', acts=acts, lesions=lesions,
                                     evidence=tuple(Span(0, len(t), t) for t in evidence))

        def biopsy(*anatomy, lesion=''):
            return Act('S1-A1', 'S1', 'biopsy', 'performed', 'physician', anatomy, technique='forceps', lesion=lesion)

        listed = ([], [('S1', 'biopsy', 'unsupported', NOT_UPPER)])
        held = ([('S1', 'biopsy')], [])
        upper = ('The echoendoscope was advanced to the second portion of the duodenum.',)
        rectal = ('The radial echoendoscope was advanced into the rectum.',)
        cases = {
            'an upper site, an upper examination': (eus(biopsy('gastric antrum'), evidence=upper), held),
            'a lower site': (eus(biopsy('rectum'), evidence=upper), listed),
            'an upper site and a lower one': (eus(biopsy('gastric antrum', 'rectum'), evidence=upper), listed),
            'an upper site, a lower examination': (eus(biopsy('gastric antrum'), evidence=rectal), listed),
            'an upper site, an examination with a lower act': (eus(biopsy('gastric antrum'), Act(
                'S1-A2', 'S1', 'snare', 'performed', 'physician', ('sigmoid colon',)), evidence=upper), listed),
            'no site, an upper examination': (eus(biopsy(), evidence=upper), held),
            'no site anywhere': (eus(biopsy()), listed),
            'a site off the upper GI lumen': (eus(biopsy('pancreatic head'), evidence=upper), listed),
            'a lesion at a lower site': (eus(biopsy(lesion='S1-L1'), evidence=upper, lesions=(
                Lesion('S1-L1', 'S1', 'mass', anatomy='rectum', region='rectum'),)), listed),
        }
        for name, (service, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(outcome(service), expected)


DENIAL = 'no tattoo or other submucosal injection was given at this session'
TATTOO = 'The polypectomy site in the sigmoid colon was tattooed with India ink.'
DENIED_LATE = ('Findings: The colonoscope was advanced to the cecum and on careful withdrawal ' + SEGMENTS + ', and '
               + DENIAL + '.')
DENIED_IN_TAIL = (SYNTHETIC + 'Procedure report\nDate of service: 2026-10-14\nProcedure: Colonoscopy.\n' + POLYP + ' '
                  + TATTOO + '\n' + DENIED_LATE + '\nImpression: Polyp removed.\n')
NONE_STATED = 'No act is stated both as done and as not done for the same service and site.'
NOT_READ = ('The documented-service reading reported a problem (see services.inventory), so an act in the part it did '
            'not read is not covered by this check.')


@override_settings(**LIVE)
class ConflictsCheckSpeaksForWhatWasReadTests(ApiCase, TestCase):
    """skeptic of the report-8 repair (e6601b1cf): a colonoscopy whose findings sentence (over 1,200 characters) is read
    for acts only in its first 1,200 characters, its unread tail denying the tattoo another sentence states done (45385
    and 45381 selected). The inventory recorded the problem and no conflict, yet services.conflicts passed with "No act
    is stated both as done and as not done for the same service and site." - in the draft TXT's CHECKS and on the
    screen's Checks panel - beside the repaired closing lines: false of a document whose unread part states the act not
    done (the same denial read whole is a conflict). A reading that recorded a problem speaks only for what it read: the
    check warns, "Among what was read, ...", and says an act in the part it did not read is not covered."""

    def conflicts(self, encounter_id):
        assessment = self.detail(encounter_id)['assessment']
        (row,) = [c for c in assessment['encounter_checks'] if c['id'] == 'services.conflicts']
        return assessment['services'], row

    def test_a_reading_read_in_part_never_claims_that_no_act_is_stated_both_ways(self):
        self.assertGreater(len(DENIED_LATE), 1200)
        encounter_id = self.run_note(DENIED_IN_TAIL, ('45385', POLYP), ('45381', TATTOO))
        services, row = self.conflicts(encounter_id)
        self.assertEqual(services['conflicts'], [])
        self.assertTrue(any('was read for acts only in its first 1,200 characters' in p for p in services['problems']),
                        services['problems'])
        self.assertEqual((row['status'], row['detail']),
                         ('warn', f'Among what was read, n{NONE_STATED[1:]} {NOT_READ}'))
        draft = self.report_text(encounter_id, 'draft')
        self.assertIn(f'[WARN] services.conflicts — Conflicting statements: Among what was read, n{NONE_STATED[1:]} '
                      f'{NOT_READ}', draft)
        self.assertNotIn(f'[PASS] services.conflicts', draft)
        self.assertEqual(section(draft, 'CONFLICTS IN THE RECORD'),  # unchanged (e6601b1cf)
                         '  - none among what was read: the documented-service reading reported a problem')

    def test_controls_a_whole_reading_keeps_its_pass_and_a_conflict_read_whole_its_items(self):
        # the same denial in a sentence of its own, read whole: a conflict, listed with both sides
        whole = DENIED_IN_TAIL.replace(DENIED_LATE, 'Findings: The colonoscope was advanced to the cecum. N'
                                       + DENIAL[1:] + '.')
        encounter_id = self.run_note(whole, ('45385', POLYP), ('45381', TATTOO))
        services, row = self.conflicts(encounter_id)
        self.assertEqual(services['problems'], [])
        self.assertEqual([c['subject'] for c in services['conflicts']], ['tattoo'])
        self.assertEqual(row['status'], 'warn')
        self.assertTrue(row['detail'].startswith('Kept with both sides, never resolved silently: '), row['detail'])
        self.assertNotIn(NOT_READ, row['detail'])
        encounter_id = self.run_note(COLONOSCOPY, ('45385', POLYP))
        services, row = self.conflicts(encounter_id)
        self.assertEqual((services['problems'], services['conflicts']), ([], []))
        self.assertEqual((row['status'], row['detail']), ('pass', NONE_STATED))


class ConflictsCheckOnAPartialReadingTests(SimpleTestCase):
    """The rule on hand-built inventories: a reading problem qualifies the check whether or not a conflict was read."""

    def test_the_check_is_qualified_by_the_inventory_s_problems(self):
        from studio.gi.services import Conflict, ConflictSide, DocumentedService, ServiceInventory
        from studio.types import Span
        from studio.validation import reconcile
        service = DocumentedService('S1', 'gi.colonoscopy', 'colonoscopy', 'performed')
        conflict = Conflict('C1', 'S1', 'tattoo', '', (ConflictSide('performed', 'physician', (Span(0, 6, 'inked.'),)),
                                                       ConflictSide('negated', 'physician', (Span(7, 15, 'no ink.'),))))
        problem = ('A sentence of 1,307 characters at offset 280 was read for acts only in its first 1,200 '
                   'characters.',)
        cases = {
            'no problem, no conflict': ((), (), 'pass', NONE_STATED),
            'a problem, no conflict': (problem, (), 'warn', f'Among what was read, n{NONE_STATED[1:]} {NOT_READ}'),
            'a problem and a conflict': (problem, (conflict,), 'warn', 'Kept with both sides, never resolved silently: '
                                         'submucosal tattoo in the colonoscopy: physician performed vs physician '
                                         f'negated. {NOT_READ}'),
            'a conflict, no problem': ((), (conflict,), 'warn', 'Kept with both sides, never resolved silently: '
                                       'submucosal tattoo in the colonoscopy: physician performed vs physician negated.'),
        }
        for name, (problems, conflicts, status, detail) in cases.items():
            with self.subTest(name):
                check = reconcile.conflicts_check(ServiceInventory('test', services=(service,), conflicts=conflicts,
                                                                   problems=problems))
                self.assertEqual((check.status, check.detail), (status, detail))
