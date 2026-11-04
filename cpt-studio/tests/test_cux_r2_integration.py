"""Refutation round 2, integration: the owners' cross-file requests that change behaviour (2026-11-04).

- The approved export waits while the date row asks the member to confirm an upload date that chose between the
  document's own dates (L7-02 hardening): a readiness blocker with its customer sentence; confirmed, it is gone.
- "Action needed" names a conflict with the document's own date only where the document states one (L7-03's class).
- A re-check that could not be completed is said in the activity (L5-5), with no provider's name.
- The page titles a step waiting its turn after a finished one "Waiting for the next step" (L5-7), as the server's
  message says.

Synthetic data only; the provider is an in-process fake (no network).
"""
import json
import shutil
import subprocess
from pathlib import Path

from django.test import SimpleTestCase

from studio import answers, customer_api, models, progress, review
from tests.test_cux_flow import ELSEWHERE
from tests.test_cux_r2_details import NO_DATE, TWO_DATES, PipelineCase

APP = Path(__file__).resolve().parents[1] / 'studio' / 'static' / 'studio' / 'app.js'


class DateConfirmationHoldsTheApprovedExportTests(PipelineCase):
    def test_the_approved_export_waits_for_the_confirmation_and_not_after(self):
        encounter_id = self.upload(TWO_DATES, '2026-10-21')
        encounter = self.encounter(encounter_id)
        self.assertTrue(answers.date_confirmation_open(encounter))
        self.assertIn(review.DATE_CONFIRMATION_BLOCKER, review.readiness(encounter)['blockers'])
        doc = self.doc(encounter_id)
        self.assertFalse(doc['readiness']['approved'])
        self.assertIn('Confirm the date of service under "A few details needed".', doc['readiness']['blockers'])
        self.assertEqual(self.save(encounter_id, self.date_row(doc), '2026-10-21').status_code, 201)
        encounter = self.encounter(encounter_id)
        self.assertNotIn(review.DATE_CONFIRMATION_BLOCKER, review.readiness(encounter)['blockers'])
        self.assertNotIn('Confirm the date of service under "A few details needed".',
                         self.doc(encounter_id)['readiness']['blockers'])

    def test_no_confirmation_no_blocker(self):
        for text, entered in ((TWO_DATES, ''), (NO_DATE, '2026-10-02')):
            with self.subTest(entered=entered):
                encounter = self.encounter(self.upload(text, entered))
                self.assertNotIn(review.DATE_CONFIRMATION_BLOCKER, review.readiness(encounter)['blockers'])


class ActionNeededWordingTests(PipelineCase):
    def test_a_conflict_is_named_only_where_the_document_states_its_own_date(self):
        conflicted = self.encounter(self.upload(TWO_DATES.replace('Date of service: 2026-10-21\n', ''), '1998-01-01'))
        out = progress.encounter_progress(conflicted)
        self.assertEqual((out['phase'], out['message']), ('action_needed', progress.MESSAGES['action_needed']))
        # the document's only date is another occasion's (L7-03's class): there is no document date to differ from
        undated = self.encounter(self.upload(ELSEWHERE, '2026-10-20'))
        self.assertIsNone(answers.service_date_block(undated)['document_value'])
        out = progress.encounter_progress(undated)
        self.assertEqual((out['phase'], out['message']), ('action_needed', progress.MESSAGES['action_needed_undated']))
        self.assertNotIn('differs from the date in the document', out['message'])


class RecheckOutcomeActivityTests(PipelineCase):
    def test_a_re_check_that_did_not_complete_is_said_and_a_completed_one_is_not(self):
        encounter_id = self.upload(TWO_DATES, '')
        encounter = self.encounter(encounter_id)
        from studio import audit
        for state in ('failed', 'unknown', 'not_sent', 'succeeded'):
            audit.record(encounter.workspace, 'provider.finished', encounter=encounter, run='r', state=state,
                         http_status=None, usage={}, latency_ms=1.0, purpose='second_review')
        audit.record(encounter.workspace, 'provider.finished', encounter=encounter, run='r', state='failed',
                     http_status=None, usage={}, latency_ms=1.0, purpose='primary')
        said = [entry for entry in customer_api.activity(encounter) if entry['event'] == 'check_not_completed']
        self.assertEqual(len(said), 3)  # failed, unknown, not sent - never the succeeded one, never the primary run
        self.assertEqual({entry['summary'] for entry in said}, {customer_api.RECHECK_NOT_COMPLETED[1]})
        for word in ('Corti', 'provider', 'second review'):
            self.assertNotIn(word.lower(), customer_api.RECHECK_NOT_COMPLETED[1].lower())


class QueuedTitleTests(SimpleTestCase):
    def render(self, doc):
        node = shutil.which('node')
        self.assertIsNotNone(node)
        script = ('const app = require(process.argv[1]); let input = ""; process.stdin.on("data", d => input += d);'
                  'process.stdin.on("end", () => process.stdout.write(app.progressPanel(JSON.parse(input), {})));')
        return subprocess.run([node, '-e', script, str(APP)], input=json.dumps(doc), capture_output=True, text=True,
                              timeout=60, check=True).stdout

    def doc(self, first_state):
        """A queued document with the message the server serves for its steps (progress.queued_message; refutation r3,
        C-R3-4: the title is checked against a served message, never one the server would not send)."""
        steps = [{'key': key, 'label': label, 'state': state, 'started_at': None, 'finished_at': None}
                 for (key, label), state in zip(progress.STEPS, (first_state, 'waiting', 'not_started', 'not_started'))]
        return {'id': 'e1', 'state': 'processing', 'permissions': {'can_review': True}, 'progress': {
            'phase': 'queued', 'busy': True, 'steps': steps, 'active_detail': '', 'started_at': None, 'finished_at': None,
            'server_time': '2026-11-04T10:00:00Z', 'slow': False, 'message': progress.queued_message(steps, None),
            'can_stop': True, 'can_resume': False, 'can_leave': True, 'error': None}}

    def test_a_step_waiting_after_a_finished_one_is_not_waiting_to_start(self):
        after, before = self.doc('done'), self.doc('waiting')
        self.assertEqual((after['progress']['message'], before['progress']['message']),
                         (progress.NEXT_STEP_QUEUED, progress.MESSAGES['queued']))
        self.assertIn('<h2 id="progressTitle">Waiting for the next step</h2>'
                      f'<p class="progress-message">{progress.NEXT_STEP_QUEUED}</p>', self.render(after))
        self.assertIn('<h2 id="progressTitle">Waiting to start</h2>'
                      f'<p class="progress-message">{progress.MESSAGES["queued"]}</p>', self.render(before))
