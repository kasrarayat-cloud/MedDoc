"""Round 4: a documentation check's exclusion is a recommendation the reviewer confirms or reverses, never a silent drop.

Routing's status reading can miss wording it does not recognise (four refutation rounds found new phrasings each time), so
a reinstatable exclusion needs a reviewer decision before a reviewed report exists: 'confirm' (agree, it stays excluded
with a named reviewer) or 'reinstate' (then approve or reject). Exclusions for scope or evidence need nothing. Synthetic
data only.
"""
import csv
import io

from django.core.exceptions import ValidationError
from django.test import TestCase

from studio import models, reports, review, serializers
from tests.support import pipeline_factories as pf

BLOCKER = '45378 was excluded by a documentation check: confirm the exclusion or reinstate it'


class ConfirmExclusionTests(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        self.assessment = pf.assess(self.s.encounter, pf.standard_result())

    def actions(self, key):
        return review.allowed_actions(self.s.proposal(key), self.assessment, self.s.membership(self.s.reviewer))

    def ready(self):
        return review.readiness(self.s.encounter)

    def approve_selected(self):
        self.s.decide('sel:0', 'approve')
        self.s.decide('sel:1', 'approve')

    def test_an_undecided_documentation_exclusion_blocks_the_reviewed_report(self):
        self.approve_selected()
        self.assertEqual(self.ready(), {'draft': True, 'reviewed': False, 'blockers': [BLOCKER]})

    def test_confirm_and_reinstate_are_offered_and_confirm_clears_the_blocker(self):
        self.assertEqual(self.actions('exc:0'), ['reinstate', 'confirm'])
        self.approve_selected()
        self.s.decide('exc:0', 'confirm', note='Planned for next month; not done today.')
        self.assertEqual(self.actions('exc:0'), ['revoke'])
        self.assertTrue(self.ready()['reviewed'])
        self.assertEqual(review.current_decisions(self.assessment)[self.s.proposal('exc:0').pk].action, 'confirm')

    def test_revoking_a_confirmation_restores_the_blocker_and_both_choices(self):
        self.approve_selected()
        self.s.decide('exc:0', 'confirm')
        self.s.decide('exc:0', 'revoke')
        self.assertEqual(self.actions('exc:0'), ['reinstate', 'confirm'])
        self.assertEqual(self.ready()['blockers'], [BLOCKER])

    def test_a_confirmed_exclusion_cannot_be_approved_or_rejected(self):
        self.s.decide('exc:0', 'confirm')
        for action in ('approve', 'reject', 'reinstate', 'confirm'):
            with self.subTest(action), self.assertRaises(ValidationError):
                self.s.decide('exc:0', action)

    def test_confirm_is_only_for_a_reinstatable_exclusion(self):
        for key in ('sel:0', 'alt:0'):
            with self.subTest(key), self.assertRaises(ValidationError):
                self.s.decide(key, 'confirm')

    def test_an_exclusion_for_scope_or_evidence_needs_no_decision(self):
        result = pf.result(pf.proposal('sel:0', '43239', [pf.EGD_PASSAGE]),
                           pf.proposal('exc:0', '45378', [pf.PLAN_PASSAGE], bucket='excluded', reinstatable=False))
        assessment = pf.assess(self.s.encounter, result)
        self.assertEqual(review.allowed_actions(self.s.proposal('exc:0', assessment), assessment,
                                                self.s.membership(self.s.reviewer)), [])
        self.s.decide('sel:0', 'approve', assessment=assessment)
        self.assertTrue(self.ready()['reviewed'])

    def test_reinstate_then_decide_still_works_and_a_revoked_reinstatement_is_not_a_confirmation(self):
        self.approve_selected()
        self.s.decide('exc:0', 'reinstate')
        self.s.decide('exc:0', 'revoke')
        self.s.decide('exc:0', 'confirm')
        proposal = self.s.proposal('exc:0')
        decision = review.current_decisions(self.assessment)[proposal.pk]
        self.assertIsNone(serializers._reinstated_by(proposal, decision))
        item = reports._item(proposal, decision, reports.REVIEWED, self.s.revision.text)
        self.assertEqual((item['list'], item['reinstated'], item['reinstated_by']), ('excluded', False, None))

    def test_only_excluded_proposals_are_ever_left_undecided_by_confirmation(self):
        # Every proposal a reviewer must decide is listed; nothing reaches a reviewed report undecided.
        self.approve_selected()
        self.s.decide('exc:0', 'confirm')
        snap = reports.snapshot(self.s.encounter, reports.REVIEWED)
        self.assertEqual(sorted(i['list'] for i in snap['proposals']), ['alternative', 'approved', 'approved', 'excluded'])


class ConfirmedExclusionInReportsTests(TestCase):
    def setUp(self):
        self.s = pf.scenario()
        pf.assess(self.s.encounter, pf.standard_result())
        self.s.decide('sel:0', 'approve')
        self.s.decide('sel:1', 'approve')

    def generate(self, kind, fmt):
        artifact = reports.generate(self.s.encounter, kind, fmt, self.s.reviewer)
        return bytes(artifact.content).decode('utf-8')

    def test_the_reviewed_txt_names_the_confirming_reviewer_in_the_excluded_list(self):
        self.s.decide('exc:0', 'confirm', note='Not done today.')
        text = self.generate(models.ReportArtifact.REVIEWED, 'txt')
        section = text.split('EXCLUDED CANDIDATES', 1)[1].split('\n\n', 1)[0]
        self.assertIn('45378', section)
        self.assertIn('Decision: exclusion confirmed by', section)
        self.assertIn(self.s.reviewer.label(), section)
        self.assertIn('Note: Not done today.', section)
        self.assertNotIn('no reviewer has confirmed this exclusion', section)

    def test_the_draft_txt_says_an_unconfirmed_exclusion_has_no_reviewer(self):
        text = self.generate(models.ReportArtifact.DRAFT, 'txt')
        section = text.split('EXCLUDED CANDIDATES', 1)[1].split('\n\n', 1)[0]
        self.assertIn('no reviewer has confirmed this exclusion', section)

    def test_the_csv_row_carries_the_confirmation(self):
        self.s.decide('exc:0', 'confirm')
        data = list(csv.DictReader(io.StringIO(self.generate(models.ReportArtifact.REVIEWED, 'csv'))))
        row = next(r for r in data if r['code'] == '45378')
        self.assertEqual((row['item_list'], row['decision'], row['reviewer_kind']), ('excluded', 'confirm', 'human'))
        self.assertIn('service.performed=not_verified', row['not_verified'])

    def test_every_report_states_that_service_status_is_not_verified(self):
        text = self.generate(models.ReportArtifact.DRAFT, 'txt')
        standing = text.split('Standing limitations (every code):', 1)[1].split('Per code:', 1)[0]
        self.assertIn('Whether each service was performed at this encounter is not verified', ' '.join(standing.split()))
        self.assertIn('can miss wording they do not recognise', ' '.join(standing.split()))
