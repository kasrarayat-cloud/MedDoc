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
