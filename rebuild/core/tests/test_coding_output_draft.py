"""Focused draft status checks using isolated decisions and retained output only."""
from copy import deepcopy
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from core.coding_draft_export import TITLE, draft_review
from core.models import CodingOutputDecision
from core.tests import test_coding_output as output_fixture
from core.tests.test_coding_export import texts


@override_settings(CODING_PROVIDER='corti', CORTI_CODING_MODE='replay',
                   CODING_ALLOW_TEST_FIXTURES=True, CORTI_REPLAY_FIXTURE=output_fixture.workflow.FIXTURE,
                   SYNTHETIC_ONLY=True, ADMIN_SITE=False, STORAGES=output_fixture.workflow.STORAGES,
                   CPT_ENTITLEMENT_MANIFEST='/missing-corti-output-draft-entitlement.json')
class BoundedOutputDraftTests(TestCase):
    # Fixture construction only: the completed approval/replay campaign is not
    # inherited or rerun. No decision can reach the installed synthetic account.
    setUp = output_fixture.BoundedOutputReviewTests.setUp
    install = output_fixture.BoundedOutputReviewTests.install
    review = output_fixture.BoundedOutputReviewTests.review
    decide = output_fixture.BoundedOutputReviewTests.decide
    download = output_fixture.BoundedOutputReviewTests.download
    assert_original_state = output_fixture.BoundedOutputReviewTests.assert_original_state

    def current_draft(self):
        _, _, rows, paragraphs = draft_review(self.encounter)
        return rows, '\n'.join(text for text, _ in paragraphs)

    def test_pending_supported_number_has_honest_status_and_keeps_all_seven_spans(self):
        rows, content = self.current_draft()
        self.assertEqual([row['valid_evidence_count'] for row in rows], [2, 2, 3])
        self.assertIn('clinician acceptance pending', rows[2]['decision_status'])
        self.assertIn('excluded from approved export', rows[2]['decision_status'])
        self.assertIn('Selection-source assessment:', content)
        self.assertIn('API-output permission basis:', content)
        self.assertIn('upstream description and terminology version remain unresolved', content)
        self.assertNotIn('15 MINUTES', content)
        self.assertNotIn('E/M selection criteria, with source attribution', content)
        self.assertIn(TITLE, content)
        for suggestion in self.run.result['suggestions']:
            for span in suggestion['evidence_spans']:
                self.assertIn(span['text'], content)
        self.assertEqual(CodingOutputDecision.objects.count(), 0)
        self.assert_original_state()

    def test_accepted_number_changes_new_draft_status_but_preserves_historical_draft(self):
        old = self.download('export_synthetic_coding_draft')
        old_path = next((self.root / 'exports/coding-draft').rglob('*.docx'))
        self.decide()
        new = self.download('export_synthetic_coding_draft')
        rows, content = self.current_draft()
        self.assertIn('accepted in the separate saved review', rows[2]['decision_status'])
        self.assertIn('This draft remains unapproved', rows[2]['decision_status'])
        self.assertNotIn('Held', rows[2]['decision_status'])
        self.assertNotIn('15 MINUTES', content)
        self.assertEqual(texts(new).count(TITLE), 1)
        self.assertIn('not an approved coding document', '\n'.join(texts(new)))
        self.assertNotEqual(new, old)
        self.assertEqual(old_path.read_bytes(), old)
        self.assertEqual(len(list((self.root / 'exports/coding-draft').rglob('*.docx'))), 2)
        self.assertEqual(self.download('export_synthetic_coding_draft'), new)
        self.assertEqual(CodingOutputDecision.objects.count(), 1)
        self.assert_original_state()

    def test_rejected_number_is_explicit_while_prior_icd_decisions_remain_intact(self):
        self.decide('rejected', False)
        rows, content = self.current_draft()
        self.assertEqual(rows[0]['decision_status'], 'Accepted in the separate saved approval.')
        self.assertEqual(rows[1]['decision_status'], 'Rejected in the saved review.')
        self.assertIn('rejected in the supplemental review', rows[2]['decision_status'])
        self.assertIn('excluded from approved export', rows[2]['decision_status'])
        self.assertNotIn('15 MINUTES', content)
        self.assert_original_state()

    def test_missing_or_changed_assessment_never_claims_current_acceptance(self):
        self.decide()
        with override_settings(CORTI_OUTPUT_REVIEW_FILE=''):
            rows, _ = self.current_draft()
            self.assertEqual(rows[2]['decision_status'], 'Held — excluded from approved export.')
        changed = deepcopy(self.assessment)
        changed['permission']['contradictory_restriction'] = 'Explicit isolated-test restriction'
        self.install(changed)
        rows, content = self.current_draft()
        self.assertEqual(rows[2]['decision_status'], 'Held — excluded from approved export.')
        self.assertNotIn('Code number and note evidence accepted', content)
        self.assertEqual(CodingOutputDecision.objects.count(), 1)
        self.assert_original_state()

    def test_mismatched_saved_decision_cannot_make_draft_claim_acceptance(self):
        decision = self.decide()
        altered = deepcopy(decision)
        altered.review['code'] = '99999'
        with patch('core.coding_draft_export.CodingOutputDecision.objects.filter') as query:
            query.return_value.first.return_value = altered
            rows, content = self.current_draft()
        self.assertEqual(rows[2]['decision_status'], 'Held — excluded from approved export.')
        self.assertNotIn('99999', content)
        self.assertNotIn('Code number and note evidence accepted', content)
        self.assert_original_state()

    def test_unavailable_assessment_reason_is_visible_without_acceptance_controls(self):
        with override_settings(CORTI_OUTPUT_REVIEW_SHA256='0' * 64):
            response = self.client.get(reverse('coding_status', args=[self.encounter.pk]),
                                       HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 200)
        html = response.json()['html']
        self.assertIn('data-output-review-unavailable', html)
        self.assertIn('The output assessment failed its integrity check.', html)
        self.assertNotIn('name="confirm_note_facts"', html)
        self.assertEqual(CodingOutputDecision.objects.count(), 0)
        self.assert_original_state()
