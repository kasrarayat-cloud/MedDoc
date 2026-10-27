"""Repair round ec5, cluster REPORTFACTS: how facts, coverage and completeness are described. Synthetic data only; the
provider is an in-process fake (no network).

Each class reproduces a finding of refutation round r1 (ledger verdicts at 8f8a3b48, re-checked at 8985dde42) with its
smallest input and asserts the wording that is true of the persisted state, beside a control that must not change.
"""
from django.test import SimpleTestCase

from tests.test_pipeline_api import OFFICE_NOTE
from tests.test_services_reconcile import check, proposal, run, sel, span

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
