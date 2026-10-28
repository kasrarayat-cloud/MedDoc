"""HANDOFF (cluster SENDS, ec5; not committed: the rule belongs in studio/review.py, outside SENDS territory).

new:failed-review2-state - a second-review stage that ends FAILED without a second-review run (the requesting
reviewer's role was withdrawn before it ran, so jobs._live_gate refused it; an unexpected error; or the installer's
undo, ops/install.py CLOSE_STAGES, closing a queued review2 that a reinstalled revision then reads) makes
review._failed_stage_state answer 'provider_not_run', and the encounter screen says "No proposals were requested."
while the primary request succeeded and the current assessment's proposals stand (must-fix class 3: a screen that
misstates persisted state).

Suggested general rule (review._failed_stage_state): a failed second-review stage is a failure of that optional
request only; with no second-review run made after it, the encounter's state is its current assessment's own state
(the failed stage stays listed with its error); a second-review run that failed or is unknown is said as such.
Both tests below fail at 8985dde42 and at the SENDS head (state 'provider_not_run').
"""
from django.test import override_settings
from django.utils import timezone

from studio import models, review
from tests.test_pipeline_api import drain
from tests.test_repairs_ec5_sends import Base, LIVE


@override_settings(**LIVE)
class FailedSecondReviewStateTests(Base):
    def assert_states_the_assessment(self, encounter_id):
        encounter = self.encounter(encounter_id)
        review.refresh_state(encounter)
        self.assertNotEqual(encounter.state, 'provider_not_run')
        self.assertEqual(encounter.state, 'needs_clarification')  # the current assessment's own state
        self.assertTrue(encounter.current_assessment.proposals.filter(bucket='selected', code='45385').exists())

    def test_a_second_review_refused_at_its_stage_never_reads_as_no_request(self):
        encounter_id = self.create()
        drain()
        self.assertEqual(self.encounter(encounter_id).state, 'needs_clarification')
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        models.Membership.objects.filter(user=self.reviewer).update(active=False)  # the requester lost the role
        drain()
        models.Membership.objects.filter(user=self.reviewer).update(active=True)
        job = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.REVIEW2)
        self.assertEqual(job.state, models.Job.FAILED)
        self.assert_states_the_assessment(encounter_id)

    def test_a_second_review_the_installer_closed_never_reads_as_no_request(self):
        from tests.test_repairs_r1_m import install, run_app_script
        encounter_id = self.create()
        drain()
        swap = timezone.now()
        self.assertEqual(self.ask(encounter_id).status_code, 201)
        run_app_script(install.CLOSE_STAGES, {'since': swap.isoformat(), 'note': 'Closed by the installer: undone.'})
        self.assert_states_the_assessment(encounter_id)
