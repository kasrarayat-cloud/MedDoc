"""Decision (j) of the core repair (2026-11-03): a dead worker never animates.

While a document waits on processing and the worker's newest heartbeat is older than jobs.WORKER_SILENT_SECONDS, the
progress block says processing is paused: phase 'paused', a message that promises nothing, nothing called slow, Stop
still offered. A fresh beat reads as processing; no beat ever recorded claims nothing (the phase is the stage's own).
An idle document never reads paused. The page draws 'paused' with no animated step and no running clock, and keeps
polling so it moves on by itself.

DB-backed; synthetic data only; nothing is sent.
"""
import json
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path

from django.test import SimpleTestCase
from django.utils import timezone

from studio import jobs, models, progress
from tests.test_cux_flow import ProgressCase

APP = Path(__file__).resolve().parents[1] / 'studio' / 'static' / 'studio' / 'app.js'


def beat(seconds_ago, now):
    models.WorkerBeat.objects.update_or_create(name=jobs.WORKER_NAME, defaults={
        'beat_at': now - timedelta(seconds=seconds_ago), 'revision': 'test', 'pid': 1})


class PausedTests(ProgressCase):
    def running(self):
        return self.chain(models.Job.EXTRACT, models.Job.ANALYZE, (models.Job.PREDICT, None), last='running')

    def test_a_busy_document_reads_paused_once_the_worker_has_not_beaten_for_the_silent_bound(self):
        self.running()
        now = timezone.now()
        beat(jobs.WORKER_SILENT_SECONDS + 1, now)
        out = progress.encounter_progress(self.enc, now=now)
        self.assertEqual((out['phase'], out['busy'], out['slow'], out['can_stop'], out['message']),
                         ('paused', True, False, True, progress.MESSAGES['paused']))
        self.assertIn(out['phase'], progress.PHASES)
        self.assertNotIn('continues', out['message'])  # promises nothing about when or whether
        self.assertEqual(out['active_detail'], progress.DOCUMENT_REVIEW)

    def test_a_fresh_beat_reads_processing_and_no_beat_ever_recorded_claims_nothing(self):
        self.running()
        now = timezone.now()
        self.assertEqual(progress.encounter_progress(self.enc, now=now)['phase'], 'processing')  # no row at all
        beat(jobs.WORKER_SILENT_SECONDS, now)  # at the bound: still responding
        self.assertEqual(progress.encounter_progress(self.enc, now=now)['phase'], 'processing')
        beat(0, now)
        self.assertEqual(progress.encounter_progress(self.enc, now=now)['phase'], 'processing')

    def test_a_queued_document_reads_paused_too_and_an_idle_one_never_does(self):
        self.job(models.Job.EXTRACT, 'queued', 0)
        now = timezone.now()
        beat(jobs.WORKER_SILENT_SECONDS + 60, now)
        self.assertEqual(progress.encounter_progress(self.enc, now=now)['phase'], 'paused')
        models.Job.objects.filter(encounter=self.enc).delete()
        self.chain(models.Job.EXTRACT, models.Job.ANALYZE, models.Job.PREDICT, models.Job.ASSESS)
        self.assertNotEqual(progress.encounter_progress(self.enc, now=now)['phase'], 'paused')


class PausedPageTests(SimpleTestCase):
    def render(self, doc):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'node is not installed; the page is checked by running the shipped app.js')
        script = ('const app = require(process.argv[1]); let input = ""; process.stdin.on("data", d => input += d);'
                  'process.stdin.on("end", () => { const doc = JSON.parse(input);'
                  'process.stdout.write(JSON.stringify({ html: app.progressPanel(doc, { nowMs: Date.parse(doc.progress.server_time) }),'
                  ' poll: app.shouldPoll(doc) })); });')
        done = subprocess.run([node, '-e', script, str(APP)], input=json.dumps(doc), capture_output=True, text=True,
                              timeout=60, check=True)
        return json.loads(done.stdout)

    def test_paused_draws_no_animated_step_and_no_running_clock_and_keeps_polling(self):
        doc = {'id': 'e1', 'state': 'processing', 'permissions': {'can_review': True}, 'progress': {
            'phase': 'paused', 'busy': True, 'active_detail': 'Document review', 'started_at': '2026-11-04T10:00:00Z',
            'finished_at': None, 'server_time': '2026-11-04T10:09:00Z', 'slow': False,
            'message': progress.MESSAGES['paused'], 'can_stop': True, 'can_resume': False, 'can_leave': True,
            'error': None, 'steps': [
                {'key': 'reading', 'label': 'Reading your document', 'state': 'done', 'started_at': None, 'finished_at': None},
                {'key': 'identifying', 'label': 'Identifying procedures', 'state': 'done', 'started_at': None, 'finished_at': None},
                {'key': 'checking', 'label': 'Checking suggested codes', 'state': 'active', 'started_at': None, 'finished_at': None},
                {'key': 'preparing', 'label': 'Preparing your results', 'state': 'not_started', 'started_at': None, 'finished_at': None}]}}
        out = self.render(doc)
        html = out['html']
        self.assertTrue(out['poll'])
        self.assertIn('data-phase="paused"', html)
        self.assertIn('Processing paused', html)
        self.assertIn(progress.MESSAGES['paused'], html.replace('&#x27;', "'"))
        self.assertNotIn('is-animated', html)
        self.assertNotIn('data-elapsed', html)
        self.assertIn('data-action="stop"', html)
        processing = json.loads(json.dumps(doc))
        processing['progress']['phase'] = 'processing'
        self.assertIn('is-animated', self.render(processing)['html'])  # the control: the same document, not paused
