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
