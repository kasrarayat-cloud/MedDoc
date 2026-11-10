"""Refutation round 3 of the core repair (2026-11-04), the progress owner: each step says what its stages recorded, and
the page's title and the server's message read a queued step by one rule.

- C-R3-5: a document review whose request did not give the document an answer - it failed, was not sent, or sending is
  disabled - never reads its step "Done", whatever the checks after it did; one whose outcome is unknown, or a check
  whose own outcome is unknown, reads as an outcome still being confirmed reads (stopped: never done, never a failure).
  A check's own failure blocks only itself (HARNESS.md I10): the document's processing goes on and its step stays done,
  while the checks say what was unavailable.
- C-R3-4: a queued step after one the panel shows done - one of this run, or one a member's save, Resume, detail,
  reconciliation or re-check keeps from an earlier run - is "Waiting for the next step" in the page's title and
  progress.NEXT_STEP_QUEUED in the server's message, by one rule (progress.next_step_queued) over the steps the server
  serves; with no step done both say "Waiting to start". A retry or a long wait keeps its own message, and the title
  still reads the steps.

DB-backed; synthetic data only; nothing is sent (the in-process fakes of the pipeline and harness suites). The page is
the shipped app.js, drawn in node.
"""
import html
import itertools
import json
import shutil
import subprocess
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import Client, SimpleTestCase, TestCase, override_settings

from studio import jobs, models, progress
from studio.gi.context import _USER_CONFLICT_PREFIX
from studio.providers.base import ProviderUnavailable
from tests.legacy_chain import applied
from tests.support import factories as f
from tests.support import pipeline_factories as pf
from tests.support.operator import OperatorReads
from tests.test_cux_flow import ProgressCase, run_stages
from tests.test_cux_r2_progress import LIVE, NOTE, TIME_QUOTE, CustomerReads
from tests.test_harness_pipeline import BOTH, FakeParticipant, HarnessCase, ScriptedCorti
from tests.test_pipeline_api import OFFICE_INTERPRETATION, OFFICE_NOTE, FakeProvider, RecordedInterpretation, drain
from tests.test_repairs_7c8_p1reports import COLONOSCOPY_INTERPRETATIONS
from tests.test_repairs_gi2_present import BIOPSY, SNARE, Harness
from tests.test_services_second_review import TwoPassProvider

APP = Path(__file__).resolve().parents[1] / 'studio' / 'static' / 'studio' / 'app.js'
NO_PATIENT_STATUS = OFFICE_NOTE.replace('Patient status: Established patient, last seen 2026-03-02.\n', '')
# Gemini's synthetic answer to NO_PATIENT_STATUS (design/FINAL.md 14.6): OFFICE_NOTE's, which cites no patient-status
# line (a member value on the production chain, DECISIONS D3), so it is this note's own.
NO_PATIENT_STATUS_INTERPRETATIONS = ((OFFICE_NOTE, OFFICE_INTERPRETATION), (NO_PATIENT_STATUS, OFFICE_INTERPRETATION))
TO_START, NEXT_STEP = 'Waiting to start', 'Waiting for the next step'
STEP_TEXT = {'done': 'Done', 'active': 'In progress', 'waiting': 'Waiting to start', 'not_started': 'Not started',
             'failed': 'Did not finish', 'stopped': 'Stopped', 'skipped': 'Not needed'}
# Draws each served document's progress panel with the shipped page, and reads back its title, the message it draws
# and each step as drawn (key, state, text).
DRAW = r"""
const app = require(process.argv[1]);
let input = '';
process.stdin.on('data', d => input += d);
process.stdin.on('end', () => {
  const out = JSON.parse(input).map(doc => {
    const html = app.progressPanel(doc, { nowMs: Date.parse(doc.progress.server_time) });
    const title = /<h2 id="progressTitle">([^<]*)<\/h2>/.exec(html);
    const message = /<p class="progress-message[^"]*">([^<]*)<\/p>/.exec(html);
    const steps = [...html.matchAll(/<li class="progress-step[^"]*" data-step="(\w+)" data-state="(\w+)">.*?<strong>[^<]*<\/strong><small>([^<]*)<\/small>/g)].map(m => [m[1], m[2], m[3]]);
    return { title: title ? title[1] : null, message: message ? message[1] : null, steps };
  });
  process.stdout.write(JSON.stringify({ out, title: app.QUEUED_AFTER_DONE_TITLE }));
});
"""


def draw(docs):
    """[{title, message, steps}] for ``docs`` as the shipped page draws them, and the page's QUEUED_AFTER_DONE_TITLE."""
    node = shutil.which('node')
    assert node, 'node is needed to draw the page'
    reply = subprocess.run([node, '-e', DRAW, str(APP)], input=json.dumps(docs), capture_output=True, text=True,
                           timeout=300, check=True)
    data = json.loads(reply.stdout)
    for item in data['out']:
        item['title'] = html.unescape(item['title']) if item['title'] is not None else None
        item['message'] = html.unescape(item['message']) if item['message'] is not None else None
        item['steps'] = [(key, state, html.unescape(text)) for key, state, text in item['steps']]
    return data['out'], data['title']


def states(doc):
    return [step['state'] for step in doc['progress']['steps']]


class Unbuildable(FakeProvider):
    """The coding service's request cannot be built (the live adapter's ProviderUnavailable): nothing is sent."""

    def build_request(self, text, service_date):
        raise ProviderUnavailable('The coding service is not configured (synthetic); nothing was sent.')


class DrawnSteps:
    def drawn(self, doc):
        (page,), title = draw([doc])
        self.assertEqual(title, NEXT_STEP)
        self.assertEqual([(key, state) for key, state, _ in page['steps']],
                         [(step['key'], step['state']) for step in doc['progress']['steps']])
        for key, state, text in page['steps']:
            self.assertTrue(text.startswith(STEP_TEXT[state]), (key, state, text))
        return page


# --- C-R3-5: a document review that did not give an answer never reads its step done ----------------------------------

@applied
@override_settings(**LIVE)
class DocumentReviewStepTests(DrawnSteps, CustomerReads, TestCase):
    """The lens's input and its siblings, through the real pipeline and the shipped page: Corti answers HTTP 503 after
    sending, its read times out after sending, its request cannot be built, or sending is disabled. No check is
    configured."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)

    def upload(self, provider):
        with mock.patch('studio.jobs.get_provider', return_value=provider):
            with self.captureOnCommitCallbacks(execute=True):
                reply = self.client.post('/api/encounters', {'text': OFFICE_NOTE, 'synthetic_attestation': 'yes'})
            self.assertEqual(reply.status_code, 201, reply.content)
            drain()
            return self.customer(reply.json()['id'])

    def test_a_document_review_whose_request_failed_did_not_finish_its_step(self):
        provider = ScriptedCorti(selections=[('99213', TIME_QUOTE)], outcomes=['failed'])
        doc = self.upload(provider)
        self.assertEqual(len(provider.requests), 1)
        predict = models.Job.objects.get(encounter_id=doc['id'], kind='predict')
        self.assertEqual((predict.state, predict.result['provider']), (models.Job.SUCCEEDED, 'failed'))
        block = doc['progress']
        error = {'text': progress.ERRORS['provider_failed'][0], 'action': 'new_document'}
        self.assertEqual((doc['state'], block['phase'], block['error']), ('failed', 'failed', error))
        self.assertEqual(states(doc), ['done', 'done', 'failed', 'done'])
        self.assertEqual(doc['checks'][0]['state'], 'unavailable')
        page = self.drawn(doc)
        self.assertEqual(page['steps'][2], ('checking', 'failed', 'Did not finish'))
        self.assertEqual(page['title'], 'Processing could not finish')

    def test_a_document_review_whose_outcome_is_unknown_reads_as_being_confirmed(self):
        provider = FakeProvider(selections=[('99213', TIME_QUOTE)], outcome='unknown')
        doc = self.upload(provider)
        self.assertEqual(len(provider.sent), 1)
        self.assertEqual((doc['state'], doc['progress']['phase'], doc['progress']['message']),
                         ('being_confirmed', 'being_confirmed', progress.MESSAGES['being_confirmed']))
        self.assertEqual(states(doc), ['done', 'done', 'stopped', 'done'])  # never done, never called a failure
        self.assertEqual(self.drawn(doc)['steps'][2], ('checking', 'stopped', 'Stopped'))

    def test_a_request_never_made_did_not_finish_its_step_either(self):
        for label, provider, state in (('not built', Unbuildable(), 'provider_failed'),
                                       ('sending disabled', None, 'provider_not_run')):
            with self.subTest(label):
                doc = self.upload(provider)
                encounter = models.Encounter.objects.get(pk=doc['id'])
                self.assertEqual((encounter.state, doc['progress']['phase']), (state, 'failed'))
                self.assertEqual(doc['progress']['error']['text'], progress.ERRORS[state][0])
                self.assertEqual(states(doc), ['done', 'done', 'failed', 'done'])
                self.assertEqual(self.drawn(doc)['steps'][2][2], 'Did not finish')

    def test_control_a_document_review_that_was_answered_is_done(self):
        doc = self.upload(FakeProvider(selections=[('99213', TIME_QUOTE)]))
        self.assertIn(doc['progress']['phase'], ('completed', 'partial'))
        self.assertEqual(states(doc), ['done'] * 4)
        self.assertEqual(doc['checks'][0]['state'], 'done')


@applied
@override_settings(**BOTH)
class CheckedStepTests(DrawnSteps, CustomerReads, OperatorReads, HarnessCase):
    """With both checks configured (the committed failed fixture's shape): the checks that run after a document review
    never make its failure done; an unknown outcome a check records reads stopped; a check's own failure blocks only
    itself."""

    def test_a_failed_document_review_is_not_made_done_by_the_checks_after_it(self):
        self.corti.outcomes = ['failed']
        encounter_id = self.create()
        drain()
        kinds = [(job.kind, job.state) for job in self.jobs_of(encounter_id)]
        self.assertIn(('astra', models.Job.SUCCEEDED), kinds)  # the checks ran after it
        self.assertIn(('fable', models.Job.SUCCEEDED), kinds)
        doc = self.customer(encounter_id)
        self.assertEqual((doc['state'], doc['progress']['phase']), ('failed', 'failed'))
        self.assertEqual([check['state'] for check in doc['checks']][:2], ['unavailable', 'done'])
        self.assertEqual(states(doc), ['done', 'done', 'failed', 'done'])
        self.assertEqual(self.drawn(doc)['steps'][2][2], 'Did not finish')

    @override_settings(FABLE_MODE='disabled')
    def test_an_unknown_outcome_a_check_recorded_reads_as_being_confirmed(self):
        self.adapters['astra'].outcome = 'unknown'
        encounter_id = self.create()
        drain()
        (astra,) = self.runs_of(encounter_id, 'astra')
        self.assertEqual((astra.state, astra.sent), (models.ProviderRun.UNKNOWN, True))
        doc = self.customer(encounter_id)
        self.assertEqual(doc['progress']['phase'], 'being_confirmed')
        self.assertEqual(states(doc), ['done', 'done', 'stopped', 'done'])
        self.assertEqual(self.drawn(doc)['steps'][2][2], 'Stopped')

    def test_control_a_check_s_own_failure_blocks_only_itself(self):
        self.adapters['astra'] = FakeParticipant('astra', codes=self.astra_codes, outcome='failed')
        encounter_id = self.create()
        drain()
        doc = self.customer(encounter_id)
        self.assertEqual(doc['progress']['phase'], 'partial')
        self.assertEqual(doc['checks'][1]['state'], 'unavailable')  # the checks say what was unavailable
        self.assertEqual(states(doc), ['done'] * 4)


class StepRecordTests(ProgressCase):
    """What one finished stage gives its step, over rows - every outcome each stage records (jobs.stage_predict,
    stage_review2, stage_participant, stage_peer, and the stale sweep's settled results) - and the fold of a step's
    stages, every one of them read."""

    def fold(self, kind, result, state='succeeded'):
        return progress._fold([self.job(kind, state, 4, result=result)])

    def test_each_recorded_outcome_of_a_document_review(self):
        for value, expected in (('succeeded', 'done'), ('reused', 'done'), ('failed', 'failed'),
                                ('not_sent', 'failed'), ('not_resent', 'failed'), ('disabled', 'failed'),
                                ('unknown', 'stopped')):
            with self.subTest(value):
                self.assertEqual(self.fold('predict', {'provider': value, 'run': None}), expected)
                settled = {'provider': value, 'run': None, 'settled': 'the worker stopped after the outcome'}
                self.assertEqual(self.fold('predict', settled), expected)
                if value not in ('disabled', 'not_resent'):  # a re-check records neither
                    self.assertEqual(self.fold('review2', {'second_review': value, 'run': None}), expected)
                    self.assertEqual(self.fold('review2', settled), expected)  # the sweep's, under 'provider'
        self.assertEqual(self.fold('predict', {'blocked': 'a previous request has an unknown outcome'}), 'stopped')
        self.assertEqual(self.fold('predict', {}), 'done')  # a row that records no outcome reads as before

    def test_a_check_s_own_failure_blocks_only_itself_and_an_unknown_one_is_being_confirmed(self):
        for kind, key in (('astra', 'participant'), ('fable', 'participant'), ('astra_peer', 'peer'),
                          ('fable_peer', 'peer')):
            for value, expected in (('succeeded', 'done'), ('reused', 'done'), ('failed', 'done'),
                                    ('not_sent', 'done'), ('not_resent', 'done'), ('not_attempted_again', 'done'),
                                    ('not_run', 'done'), ('disabled', 'done'), ('unknown', 'stopped'),
                                    ('blocked', 'stopped')):
                with self.subTest(kind=kind, value=value):
                    self.assertEqual(self.fold(kind, {key: kind, 'state': value, 'run': None}), expected)

    def test_a_stage_s_own_state(self):
        for state, expected in (('failed', 'failed'), ('cancelled', 'stopped'), ('unknown', 'stopped')):
            with self.subTest(state):
                self.assertEqual(self.fold('predict', {}, state=state), expected)
                self.assertEqual(self.fold('astra', {}, state=state), expected)

    def test_every_stage_of_the_step_is_read_and_a_wait_outranks_a_failure(self):
        def step(*made):
            return progress._fold([self.job(kind, state, 4 + 2 * index, result=result)
                                   for index, (kind, state, result) in enumerate(made)])
        ok = ('succeeded', {'participant': 'astra', 'state': 'succeeded', 'run': None})
        failed_review = ('predict', 'succeeded', {'provider': 'failed', 'run': None})
        self.assertEqual(step(failed_review, ('astra', *ok), ('fable', *ok)), 'failed')
        self.assertEqual(step(('predict', 'succeeded', {'provider': 'unknown', 'run': None}),
                              ('astra', 'succeeded', {'participant': 'astra', 'state': 'blocked', 'run': None})),
                         'stopped')
        self.assertEqual(step(failed_review, ('astra', 'succeeded', {'participant': 'astra', 'state': 'unknown'})),
                         'stopped')  # the document waits on the unknown outcome (being_confirmed outranks failed)
        self.assertEqual(step(failed_review, ('astra', 'cancelled', {})), 'stopped')  # and a stop reads stopped
        self.assertEqual(step(('predict', 'succeeded', {'provider': 'succeeded', 'run': None}), ('astra', *ok),
                              ('fable', 'succeeded', {'participant': 'fable', 'state': 'unknown', 'run': None})),
                         'stopped')  # the last stage counts as much as the first
        self.assertEqual(step(('predict', 'succeeded', {'skipped': 'nothing was sent'})), 'skipped')

    def test_a_send_a_member_date_conflict_held_did_nothing(self):
        held = pf.context(self.enc, self.rev, fact_values={'service_date': {
            'origin': 'conflict', 'note': f'{_USER_CONFLICT_PREFIX}2026-10-01 (synthetic)'}})
        job = self.job('predict', 'succeeded', 4, result={'provider': 'not_sent', 'reason': 'member-entered service '
                                                                                            'date conflicts'})
        models.Job.objects.filter(pk=job.pk).update(context=held)
        job.refresh_from_db()
        self.assertEqual(progress._fold([job]), 'skipped')  # as the held step with no stage reads

    def test_a_step_kept_from_an_earlier_run_reads_what_its_stages_recorded(self):
        pf.provider_run(self.enc, self.rev, state=models.ProviderRun.UNKNOWN)
        self.chain('extract', 'analyze')
        self.job('predict', 'succeeded', 4, result={'provider': 'unknown', 'run': None})
        self.job('assess', 'succeeded', 6)
        self.job('assess', 'queued', 600)  # a member's save that re-assesses with the run in use: a run of its own
        out = self.progress()
        self.assertEqual(self.states(out), ['done', 'done', 'stopped', 'waiting'])


# --- C-R3-4: the page's title and the server's message read a queued step by one rule ---------------------------------

def queued_doc(steps, message, *, slow=False):
    return {'id': 'e1', 'state': 'processing', 'permissions': {'can_review': True}, 'progress': {
        'phase': 'queued', 'busy': True, 'steps': steps, 'active_detail': '', 'started_at': None, 'finished_at': None,
        'server_time': '2026-11-04T10:00:00Z', 'slow': slow, 'message': message, 'can_stop': True,
        'can_resume': False, 'can_leave': True, 'error': None}}


class QueuedAgreementMatrixTests(SimpleTestCase):
    """The agreement itself, over every combination of served step states: the server's rule
    (progress.next_step_queued, through progress.queued_message) and the page's title decide each the same way."""

    def test_the_title_and_the_message_agree_for_every_combination_of_steps(self):
        requeued = SimpleNamespace(result={'requeued': 'the provider lock is busy'})
        docs, rule = [], []
        for combo in itertools.product(progress.STEP_STATES, repeat=len(progress.STEPS)):
            steps = [{'key': key, 'label': label, 'state': state, 'started_at': None, 'finished_at': None}
                     for (key, label), state in zip(progress.STEPS, combo)]
            after = progress.next_step_queued(steps)
            for message, slow in ((progress.queued_message(steps, None), False),
                                  (progress.queued_message(steps, requeued), False), (progress.QUEUE_SLOW, True)):
                docs.append(queued_doc(steps, message, slow=slow))
                rule.append(after)
        drawn, title = draw(docs)
        self.assertEqual(title, NEXT_STEP)
        after_done = 0
        for doc, page, after in zip(docs, drawn, rule):
            message = doc['progress']['message']
            self.assertEqual(page['message'], message)  # the page draws the server's message as served
            self.assertEqual(page['title'], NEXT_STEP if after else TO_START, doc['progress']['steps'])
            if message in (progress.NEXT_STEP_QUEUED, progress.MESSAGES['queued']):
                self.assertEqual(message == progress.NEXT_STEP_QUEUED, page['title'] == NEXT_STEP)
            after_done += after
        # both readings occur: the rule is not one that never (or always) fires
        self.assertTrue(0 < after_done < len(docs), after_done)
        self.assertEqual(len(docs), 3 * len(progress.STEP_STATES) ** len(progress.STEPS))

    def test_the_rule_is_a_step_the_panel_shows_done(self):
        def steps(*values):
            return [{'key': key, 'state': value} for (key, _), value in zip(progress.STEPS, values)]
        self.assertTrue(progress.next_step_queued(steps('done', 'waiting', 'not_started', 'not_started')))
        self.assertTrue(progress.next_step_queued(steps('done', 'done', 'done', 'waiting')))
        self.assertFalse(progress.next_step_queued(steps('waiting', 'not_started', 'not_started', 'not_started')))
        self.assertFalse(progress.next_step_queued(steps('stopped', 'skipped', 'failed', 'waiting')))
        self.assertEqual(progress.queued_message(steps('done', 'waiting'), None), progress.NEXT_STEP_QUEUED)
        self.assertEqual(progress.queued_message(steps('waiting'), None), progress.MESSAGES['queued'])
        requeued = SimpleNamespace(result={'requeued': 'x'})
        self.assertEqual(progress.queued_message(steps('done', 'waiting'), requeued), progress.TAKING_TURN)


class QueuedReading:
    def assertQueued(self, doc, after_done):
        """``doc`` is queued, and the server's message, the page's title and the message the page draws all read it the
        same way: after a step the panel shows done, or before any."""
        block = doc['progress']
        self.assertEqual((block['phase'], block['busy'], block['slow']), ('queued', True, False))
        self.assertEqual(any(step['state'] == 'done' for step in block['steps']), after_done, states(doc))
        (page,), _ = draw([doc])
        expected = (NEXT_STEP, progress.NEXT_STEP_QUEUED) if after_done else (TO_START, progress.MESSAGES['queued'])
        self.assertEqual((page['title'], block['message']), expected)
        self.assertEqual(page['message'], block['message'])  # the page draws the server's message as served
        return page


@override_settings(**LIVE)
class QueuedTitleFlowTests(RecordedInterpretation, QueuedReading, CustomerReads, OperatorReads, TestCase):
    """The lens's inputs and the member's other re-runs of a revision, through the real endpoints: the first step each
    queues, drawn by the shipped page before the worker runs it."""
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads both notes from their recorded synthetic
    # interpretations; the run reconciled is Corti's, beside the interpretation's own.
    interpretations = NO_PATIENT_STATUS_INTERPRETATIONS

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider(selections=[('99213', TIME_QUOTE)])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        jobs.beat()  # a worker that is responding: a waiting step is queued, never paused

    def upload(self, text=OFFICE_NOTE):
        with self.captureOnCommitCallbacks(execute=True):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(reply.status_code, 201, reply.content)
        return reply.json()['id']

    def post(self, path, data):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data), content_type='application/json')

    def test_control_a_new_upload_waits_to_start_and_its_own_next_step_waits_after_the_first(self):
        encounter_id = self.upload()
        self.assertQueued(self.customer(encounter_id), after_done=False)
        run_stages(1)  # the extract: the analyze waits its turn
        doc = self.customer(encounter_id)
        self.assertEqual(states(doc)[:2], ['done', 'waiting'])
        self.assertQueued(doc, after_done=True)

    def test_a_member_s_save_after_a_finished_run_waits_for_the_next_step(self):
        encounter_id = self.upload()
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'}).status_code, 201)
        doc = self.customer(encounter_id)
        self.assertEqual(states(doc), ['done', 'done', 'done', 'waiting'])
        self.assertQueued(doc, after_done=True)

    def test_stop_then_resume_waits_for_the_next_step(self):
        encounter_id = self.upload()
        drain()
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'asc'}).status_code, 201)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop', {}).status_code, 200)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume', {}).status_code, 201)
        doc = self.customer(encounter_id)
        self.assertEqual(states(doc), ['done', 'done', 'done', 'waiting'])
        self.assertQueued(doc, after_done=True)

    def test_a_saved_detail_waits_for_the_next_step(self):
        encounter_id = self.upload(NO_PATIENT_STATUS)
        drain()
        (row,) = [row for row in self.customer(encounter_id)['details_needed'] if row['fact'] == 'patient_status']
        saved = self.post(f'/api/encounters/{encounter_id}/details', {'answers': [
            {'id': row['id'], 'fact': 'patient_status', 'value': row['choices'][0]['value']}]})
        self.assertEqual(saved.status_code, 201, saved.content)
        self.assertTrue(saved.json()['reassessing'])
        doc = self.customer(encounter_id)
        self.assertEqual(states(doc)[:3], ['done', 'done', 'done'])
        self.assertQueued(doc, after_done=True)

    def test_a_reconciliation_waits_for_the_next_step(self):
        self.provider.outcome = 'unknown'
        encounter_id = self.upload()
        drain()
        (run,) = models.ProviderRun.objects.filter(encounter_id=encounter_id, purpose=models.ProviderRun.PRIMARY)
        self.provider.outcome = 'succeeded'
        reply = self.post(f'/ops/api/encounters/{encounter_id}/reconcile', {'provider_run_id': str(run.pk),
                                                                           'note': NOTE})
        self.assertEqual(reply.status_code, 201, reply.content)
        doc = self.customer(encounter_id)
        self.assertEqual(states(doc)[:2], ['done', 'done'])
        self.assertQueued(doc, after_done=True)
        drain()
        self.assertEqual(len(self.provider.sent), 2)  # the one attempt it released, sent once


class QueuedRecheckTests(RecordedInterpretation, QueuedReading, CustomerReads, Harness):
    # On the production chain (design/FINAL.md 14.6; slice S15): Gemini reads every document the class uploads from its
    # recorded synthetic interpretation.
    interpretations = COLONOSCOPY_INTERPRETATIONS
    def test_a_re_check_of_what_is_still_open_waits_for_the_next_step(self):
        self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        encounter_id = self.create()
        drain()
        self.approve(encounter_id, '45385')
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 201)
        doc = self.customer(encounter_id)
        self.assertEqual(states(doc)[:2], ['done', 'done'])
        self.assertQueued(doc, after_done=True)


class QueuedOwnWordsTests(ProgressCase):
    """A retry and a long wait keep their own messages; the page's title still reads the steps."""

    def assertTitle(self, out, title):
        (page,), _ = draw([{'id': 'e1', 'state': 'processing', 'permissions': {'can_review': True}, 'progress': out}])
        self.assertEqual((page['title'], page['message']), (title, out['message']))

    def test_a_retry_and_a_long_wait_after_a_finished_step_are_titled_the_next_step(self):
        made = self.chain('extract', 'analyze', 'predict', last='queued')
        models.Job.objects.filter(pk=made[-1].pk).update(result={'requeued': 'the provider lock is busy'})
        out = self.progress(now=made[-1].created_at + timedelta(seconds=5))
        self.assertEqual((out['phase'], out['message']), ('queued', progress.TAKING_TURN))
        self.assertTitle(out, NEXT_STEP)
        late = made[-1].created_at + timedelta(seconds=0.7 * jobs.QUEUE_DEADLINE.total_seconds())
        out = self.progress(now=late)
        self.assertEqual((out['slow'], out['message']), (True, progress.QUEUE_SLOW))
        self.assertTitle(out, NEXT_STEP)

    def test_control_a_long_wait_before_any_step_waits_to_start(self):
        first = self.job('extract', 'queued', 0)
        out = self.progress(now=first.created_at + timedelta(seconds=0.7 * jobs.QUEUE_DEADLINE.total_seconds()))
        self.assertEqual((out['phase'], out['slow'], out['message']), ('queued', True, progress.QUEUE_SLOW))
        self.assertTitle(out, TO_START)
