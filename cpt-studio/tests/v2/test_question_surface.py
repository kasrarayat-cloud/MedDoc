"""The question stage on the customer's progress panel and in the derived state, with NOTES' Q-SURFACE change to
studio/progress.py and studio/review.py applied (a variant of the pipe lane's work tree; this module is the question's
attachment, never in the lane's patch). TEXT-ONLY and SYNTHETIC, as tests/v2/test_question_stage.py."""
from __future__ import annotations

from studio import jobs, models, progress, review
from studio.interpretation import holds as interpretation_holds
from tests.v2 import test_question_stage as QS

Job = models.Job


class QuestionSurfaceTests(QS.QuestionCase):
    def test_a_running_question_stage_reads_as_the_check_of_the_reading_in_progress(self):
        encounter, revision, queued = self.to_questions(QS.SESSION_E2)
        seen = {}
        real = jobs._send_question_round

        def during(job, interpreter, wave, extraction, appraisal):
            encounter.refresh_from_db()
            seen['state'] = review._state_and_run(encounter)[0]
            seen['busy'] = review.busy_targets(encounter)
            seen['panel'] = progress.encounter_progress(encounter)
            return real(job, interpreter, wave, extraction, appraisal)
        from unittest import mock
        with mock.patch.object(jobs, '_send_question_round', side_effect=during):
            self.run_next(QS.QUESTION)
        self.assertEqual((seen['state'], seen['busy']), ('processing', True))
        panel = seen['panel']
        self.assertTrue(panel['busy'])
        self.assertEqual(panel['active_detail'], progress.APPRAISE_DETAIL)
        steps = {step['key']: step['state'] for step in panel['steps']}
        self.assertEqual(steps['identifying'], 'active')
        words = ' '.join(str(value) for value in panel.values()).lower()
        self.assertFalse([word for word in QS.FORBIDDEN if word in words], words)

    def test_a_paused_question_stage_reads_paused(self):
        encounter, revision, queued = self.to_questions(QS.SESSION_E2)
        held = models.ProviderRun.objects.filter(encounter=encounter, purpose='appraisal').first()
        models.InterpreterHold.objects.create(reason=models.InterpreterHold.QUOTA, http_status=402,
                                              vendor_status='billing_error', run=held)
        self.assertTrue(interpretation_holds.is_held())
        stopped = self.run_next(QS.QUESTION)
        self.assertEqual(stopped.state, Job.CANCELLED)
        encounter.refresh_from_db()
        self.assertTrue(progress.interpreter_paused(encounter))
        self.assertEqual(progress.encounter_progress(encounter)['phase'], 'paused')

    def test_without_the_change_the_running_stage_reads_stopped(self):
        """The reason for the question: review's READING_KINDS without 'question' reads a running question stage as
        nothing serving the saved state - 'stopped', with Resume offered - while it runs."""
        encounter, revision, queued = self.to_questions(QS.SESSION_E2)
        from unittest import mock
        with mock.patch.object(review, 'READING_KINDS', tuple(kind for kind in review.READING_KINDS
                                                              if kind != 'question')):
            Job.objects.filter(pk=queued.pk).update(state=Job.RUNNING)
            encounter.refresh_from_db()
            self.assertEqual(review._state_and_run(encounter)[0], 'stopped')
