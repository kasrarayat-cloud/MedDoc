"""Repair round ec5, cluster REPORTRUNS: how provider runs and readiness are described.

Owner decision 2026-10-27 (narrow, install-first), must-fix class 3: a report, export or screen that misstates
persisted state. Refutation r1 findings re-checked at this branch's head, each through the real endpoints:
- sends-3, context-4: a run held on purpose while the member's date conflicts with the document read "The provider
  request failed" (readiness, the UI's "Still needed", the draft's Review status, the reviewed report's 409);
- report-7: a run read "requested <time> · used by this assessment" although nothing was requested (held, stopped before
  sending) or nothing usable came back (a failed request, an unknown outcome);
- sends-5: an unreconciled unknown second review left the encounter's state and the review queue saying nothing waited
  on a reconciliation, while the same runs left by a worker that died read "Provider outcome unknown";
- report-10: the UI's provider runs did not say which run was the second review;
- the second review a reviewer asks for (8985dde42): described truthfully while it waits, runs, was stopped or failed,
  and once it was not sent, skipped or its outcome is unknown; a stage of it that failed before sending never reads
  "Provider not run";
- found in this territory: the provider state cards explain themselves with the run or stage the state reads (the
  latest predict; the run in use), never with an earlier one.
Synthetic data only; no network: an in-process provider stands in for the live adapter.
"""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.test import Client, TestCase, override_settings

from studio import jobs, models, reports, review
from studio.providers.base import ProviderUnavailable
from studio.types import RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain
from tests.test_services_second_review import TwoPassProvider, ask

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
APP = Path(settings.BASE_DIR) / 'studio' / 'static' / 'studio' / 'app.js'
HELD = 'Nothing was sent: the service date entered as encounter metadata conflicts with the document'
VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')
# A colonoscopy whose snare removal is ready for review and whose separate forceps biopsy has no supported proposal,
# so a reviewer may ask for the one bounded second review of it.
COLONOSCOPY = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Colonoscopy report (fictional)
Date of service: 2026-10-16
Procedure: Colonoscopy
The colonoscope was advanced to the cecum and the examination was completed.
A 6 mm polyp in the rectum was removed with a cold snare.
A separate 10 mm flat lesion in the transverse colon was sampled with cold biopsy forceps; it was not removed.
"""
SNARE = ('45385', 'was removed with a cold snare')
BIOPSY = ('45380', 'was sampled with cold biopsy forceps')
# The shipped app.js, run under node on the API's own JSON: what the page says.
NODE = r"""
const app = require(process.argv[1]);
let input = '';
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const doc = JSON.parse(input);
  const text = html => html.replace(/<[^>]+>/g, ' | ').replace(/(\s*\|\s*)+/g, ' | ');
  const codes = app.reviewView(doc, app.documentLayout(doc), 'codes', false);
  process.stdout.write(JSON.stringify({
    exportStatus: app.exportStatusText(doc),
    timeline: text(app.reviewView(doc, app.documentLayout(doc), 'timeline', false)),
    codes: text(codes),
    codesHtml: codes,
  }));
});
"""


def page(detail):
    node = shutil.which('node')
    if node is None:
        raise AssertionError('node is not installed; the page is checked by running the shipped app.js')
    done = subprocess.run([node, '-e', NODE, str(APP)], input=json.dumps(detail), capture_output=True, text=True,
                          timeout=60, check=False)
    if done.returncode:
        raise AssertionError(done.stderr[-2000:])
    return json.loads(done.stdout)


def usage_lines(txt):
    """The run lines of a TXT report's PROVIDER USAGE section."""
    block = txt[txt.index('\nPROVIDER USAGE\n'):txt.index('\nREFERENCE SOURCES\n')]
    return [line for line in block.split('\n') if line.startswith('  - ')]


def review_status(txt):
    lines = txt.split('\n')
    start = next(i for i, line in enumerate(lines) if line.startswith('Review status:'))
    end = next(i for i in range(start + 1, len(lines)) if not lines[i].startswith('  - '))
    return lines[start:end]


class FailingProvider(FakeProvider):
    """The provider answers an error: a request that was sent and failed."""

    def send(self, request, *, deadline_s):
        self.sent.append(request.canonical_sha256)
        return RawExchange(outcome='failed', sent=True, http_status=500,
                           error='HTTP 500 from the provider (synthetic).')


class FailsThenRefusesToSend(FakeProvider):
    """The first request is sent and fails; the next is refused before sending (the adapter's not-sent exchange, as
    when its credentials cannot be read at send time)."""

    def send(self, request, *, deadline_s):
        self.sent.append(request.canonical_sha256)
        if len(self.sent) == 1:
            return RawExchange(outcome='failed', sent=True, http_status=500,
                               error='HTTP 500 from the provider (synthetic).')
        return RawExchange(outcome='not_sent', sent=False, error='The credentials could not be read; nothing was sent.')


class UnbuildableProvider(FakeProvider):
    """The adapter cannot build any request: a run recorded as not sent, without a held reason."""

    def build_request(self, text, service_date):
        raise ProviderUnavailable('The provider adapter could not build this request (synthetic).')


class SecondUnbuildable(TwoPassProvider):
    """The primary request is built and answered; the second review's request cannot be built (not sent)."""

    def build_request(self, text, service_date):
        if self.requests:
            raise ProviderUnavailable('The provider adapter could not build this request (synthetic).')
        return super().build_request(text, service_date)


@override_settings(**LIVE)
class Pipeline(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)

    def use(self, provider):
        patcher = mock.patch('studio.jobs.get_provider', return_value=provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.provider = provider
        return provider

    def create(self, text, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(reply.status_code, 201, reply.content)
        return reply.json()['id']

    def post(self, path, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def detail(self, encounter_id):
        return self.client.get(f'/api/encounters/{encounter_id}').json()

    def draft(self, encounter_id):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        return reports.render_txt(reports.snapshot(encounter, 'draft')).decode('utf-8')

    def runs(self, encounter_id):
        return list(models.ProviderRun.objects.filter(encounter_id=encounter_id).order_by('created_at', 'pk'))

    def approve(self, encounter_id, code):
        proposal = next(p for p in self.detail(encounter_id)['assessment']['proposals'] if p['code'] == code)
        acknowledgement = self.client.get('/api/session').json()['acknowledgement']
        reply = self.post(f'/api/encounters/{encounter_id}/decisions',
                          {'proposal_id': proposal['id'], 'action': 'approve', 'acknowledgement': acknowledgement})
        self.assertEqual(reply.status_code, 201, reply.content)

    def queue_count(self):
        return self.client.get('/api/session').json()['counts']['queue']


# --- sends-3, context-4: a held run is never "The provider request failed" ------------------------------------------

class HeldRunReadsAsHeldTests(Pipeline):
    """Re-checked at the head: repaired by WIP 8j (e9b7c5e23) in readiness and the report; pinned here end to end,
    including the page's "Still needed" and the reviewed report's refusal, for both shapes the finding named."""

    def assert_held(self, encounter_id):
        (held,) = [run for run in self.runs(encounter_id) if run.scope.get('held')]
        self.assertEqual((held.state, held.sent, held.request_sha256), (models.ProviderRun.NOT_SENT, False, ''))
        detail = self.detail(encounter_id)
        self.assertEqual(detail['state'], 'needs_clarification')
        blockers = detail['readiness']['blockers']
        self.assertIn(HELD, blockers)
        self.assertNotIn('The provider request failed', blockers)
        reviewed = self.post(f'/api/encounters/{encounter_id}/reports', {'kind': 'reviewed', 'fmt': 'txt'})
        self.assertEqual(reviewed.status_code, 409, reviewed.content)
        self.assertNotIn('The provider request failed', reviewed.json()['details']['blockers'])
        draft = self.draft(encounter_id)
        status = review_status(draft)
        self.assertIn(f'  - {HELD}', status)
        self.assertFalse([line for line in status if 'failed' in line], status)
        shown = page(detail)['exportStatus']
        self.assertIn(f'Still needed: {HELD}', shown)
        self.assertNotIn('failed', shown)
        return draft

    def test_a_member_date_held_at_upload_is_held_not_failed(self):
        self.use(FakeProvider(selections=[VISIT]))
        encounter_id = self.create(OFFICE_NOTE, service_date='1998-01-01')
        drain()
        self.assertEqual(self.provider.sent, [])  # nothing was ever requested
        self.assert_held(encounter_id)

    def test_a_member_date_held_after_a_finished_request_is_held_not_failed(self):
        self.use(FakeProvider(selections=[VISIT]))
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        reply = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-22'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        draft = self.assert_held(encounter_id)
        first, held = usage_lines(draft)
        self.assertNotIn('by this assessment', first)  # the earlier run is not the one this assessment read

    def test_control_a_request_that_could_not_be_built_still_reads_failed(self):
        """The generic not-sent run (no held reason) keeps its wording (tests/test_review.py pins it)."""
        self.use(UnbuildableProvider(selections=[VISIT]))
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        (run,) = self.runs(encounter_id)
        self.assertEqual((run.state, run.scope), (models.ProviderRun.NOT_SENT, {}))
        self.assertEqual(self.detail(encounter_id)['readiness']['blockers'][:1], ['The provider request failed'])


# --- report-7: "requested" only of a request that was made, "used" only of a response that was read ----------------

class ProviderUsageWordingTests(Pipeline):
    """ARCHITECTURE 5.12: each provider run is "used by this assessment" only when its own provider check did not fail.
    At the head a failed request and an unknown outcome still read "used by this assessment" (the "not used" wording
    was gated on a succeeded run), and a run stopped before sending read "requested <time>"."""

    def only_line(self, encounter_id):
        (line,) = usage_lines(self.draft(encounter_id))
        return line

    def provider_check(self, encounter_id):
        assessment = models.Encounter.objects.get(pk=encounter_id).current_assessment
        return next(c for c in assessment.encounter_checks if c['id'] == 'provider.status')

    def test_a_failed_request_is_never_reported_used(self):
        self.use(FailingProvider(selections=[VISIT]))
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        self.assertEqual(self.provider_check(encounter_id)['status'], 'fail')
        line = self.only_line(encounter_id)
        self.assertIn(' · failed · HTTP 500 · revision 1 · requested ', line)
        self.assertNotIn('used by this assessment', line)
        self.assertTrue(line.endswith(' · read by this assessment; it returned no usable response, so nothing from it '
                                      'was used'), line)

    def test_an_unknown_outcome_is_never_reported_used(self):
        self.use(FakeProvider(selections=[VISIT], outcome='unknown'))
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        line = self.only_line(encounter_id)
        self.assertIn(' · unknown · revision 1 · requested ', line)  # it was sent: its outcome is what is unknown
        self.assertNotIn('used by this assessment', line)
        self.assertTrue(line.endswith(' · read by this assessment; its outcome is unknown, so nothing from it '
                                      'was used'), line)

    def test_a_request_stopped_before_sending_is_never_reported_requested(self):
        """A Stop recorded while the predict stage ran: the run is reserved, sees the Stop and is cancelled before any
        byte is sent (jobs._send). Resumed, the request is made once. The cancelled run was never requested."""
        self.use(FakeProvider(selections=[VISIT]))
        encounter_id = self.create(OFFICE_NOTE)
        while True:
            job = jobs.claim_next()
            if job.kind == models.Job.PREDICT:
                break
            jobs.run_job(job)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        jobs.run_job(models.Job.objects.get(pk=job.pk))
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        cancelled, sent = usage_lines(self.draft(encounter_id))
        self.assertEqual([r.state for r in self.runs(encounter_id)], ['cancelled', 'succeeded'])
        self.assertIn(' · cancelled · revision 1 · recorded ', cancelled)
        self.assertTrue(cancelled.endswith(' · nothing was sent'), cancelled)
        self.assertNotIn('requested', cancelled)
        self.assertNotIn('by this assessment', cancelled)
        self.assertIn(' · succeeded · HTTP 200 · revision 1 · requested ', sent)
        self.assertTrue(sent.endswith(' · used by this assessment'), sent)

    def test_control_a_succeeded_request_is_used(self):
        self.use(FakeProvider(selections=[VISIT]))
        encounter_id = self.create(OFFICE_NOTE)
        drain()
        line = self.only_line(encounter_id)
        self.assertIn(' · succeeded · HTTP 200 · revision 1 · requested ', line)
        self.assertTrue(line.endswith(' · used by this assessment'), line)


# --- sends-5: an unreconciled unknown second review is what the encounter waits on ----------------------------------

QUEUE_NODE = r"""
const app = require(process.argv[1]);
let input = '';
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => process.stdout.write(app.listDescription('queue', JSON.parse(input).encounters)));
"""


class UnknownSecondReviewStateTests(Pipeline):
    """A second review a reviewer asked for whose outcome is unknown blocks every further send until a member reconciles
    it (ARCHITECTURE 5.11), and the page shows the reconciliation card. At the head the encounter's state followed the
    primary run only when the provider never answered ("Ready for review", then "Reviewed": off the review queue, whose
    page then said no document waited for a reconciliation), while the same runs left by a worker that died mid-send
    read "Provider outcome unknown"."""

    def setUp(self):
        super().setUp()
        self.use(TwoPassProvider(first=[SNARE], later=[BIOPSY], outcomes=['succeeded', 'unknown']))

    def unknown_second_review(self):
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(self.detail(encounter_id)['state'], 'ready_for_review')
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        self.assertEqual([(r.purpose, r.state, r.reconciled_at) for r in self.runs(encounter_id)],
                         [('primary', 'succeeded', None), ('second_review', 'unknown', None)])
        return encounter_id

    def queue_page(self):
        node = shutil.which('node')
        self.assertIsNotNone(node, 'node is not installed; the queue page is checked by running the shipped app.js')
        listed = self.client.get('/api/encounters').json()
        done = subprocess.run([node, '-e', QUEUE_NODE, str(APP)], input=json.dumps(listed), capture_output=True,
                              text=True, timeout=60, check=True)
        return done.stdout

    def test_an_unknown_second_review_keeps_the_encounter_waiting_on_its_reconciliation(self):
        encounter_id = self.unknown_second_review()
        self.assertEqual(self.detail(encounter_id)['state'], 'provider_unknown')
        self.approve(encounter_id, '45385')
        detail = self.detail(encounter_id)
        self.assertEqual(detail['state'], 'provider_unknown')
        self.assertEqual(self.queue_count(), 1)
        self.assertEqual(self.queue_page(),
                         'One document needs a clarification, a review decision or a reconciliation.')
        unknown = models.ProviderRun.objects.get(encounter_id=encounter_id, state='unknown')
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(unknown.pk), 'note': 'Checked the provider console: no response.'})
        self.assertIn(reply.status_code, (200, 201), reply.content)
        drain()
        self.assertEqual(len(self.provider.requests), 2)  # reconciling sends nothing by itself
        self.assertEqual(self.detail(encounter_id)['state'], 'reviewed')  # the carried approval; nothing waits now

    def test_control_the_same_runs_left_by_a_worker_that_died_read_the_same(self):
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        job = jobs.claim_next()
        self.assertEqual(job.kind, models.Job.REVIEW2)

        def dies(request, *, deadline_s):
            raise SystemExit('the worker died while the request was in flight (synthetic)')
        with mock.patch.object(self.provider, 'send', dies), self.assertRaises(SystemExit):
            jobs.run_job(job)
        models.Job.objects.filter(pk=job.pk).update(started_at=job.started_at.replace(year=2000))
        jobs.mark_stale()
        drain()
        self.assertEqual([(r.purpose, r.state) for r in self.runs(encounter_id)],
                         [('primary', 'succeeded'), ('second_review', 'unknown')])
        self.assertEqual(self.detail(encounter_id)['state'], 'provider_unknown')
        self.approve(encounter_id, '45385')
        self.assertEqual(self.detail(encounter_id)['state'], 'provider_unknown')

    def test_control_without_an_unknown_outcome_the_review_decides_the_state(self):
        self.provider.outcomes = []
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        drain()
        self.assertEqual([r.state for r in self.runs(encounter_id)], ['succeeded', 'succeeded'])
        self.assertEqual(self.detail(encounter_id)['state'], 'ready_for_review')
        self.approve(encounter_id, '45385')
        self.approve(encounter_id, '45380')
        self.assertEqual(self.detail(encounter_id)['state'], 'reviewed')
        self.assertEqual(self.queue_count(), 0)


# --- report-10 and the second review a reviewer asks for (8985dde42): what the page and the report say --------------

def provider_rows(timeline):
    """The Provider runs card of the Activity tab, as text."""
    start = timeline.index('| Provider runs |')
    return timeline[start:timeline.index('| Activity |', start)]


class SecondReviewDescribedTests(Pipeline):
    """The page renders what the report renders: a second-review run is named as one, with what it asked about
    (report-10: the Activity tab showed two identical "Corti · live · Succeeded" rows). A second review a reviewer asked
    for is described as asked for until its own outcome is recorded: never "wait ... before asking", never offered
    again once its request is used, and a stage that failed before sending never reads "Provider not run"."""

    ITEM = 'forceps biopsy (cold forceps) of the 10 mm flat lesion in the transverse colon in the colonoscopy'

    def asked(self, provider):
        self.use(provider)
        encounter_id = self.create(COLONOSCOPY)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 201)
        return encounter_id

    def test_each_provider_run_says_which_request_it_was(self):
        encounter_id = self.asked(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        drain()
        rows = provider_rows(page(self.detail(encounter_id))['timeline'])
        self.assertEqual(rows.count('Second review'), 1, rows)
        self.assertIn('| Corti · live · Succeeded |', rows)  # the primary request, unlabelled as in the report
        self.assertIn('| Corti · live · Second review · Succeeded |', rows)
        self.assertIn(f'Asked about: {self.ITEM}.', rows)
        primary, second = usage_lines(self.draft(encounter_id))
        self.assertNotIn('second review', primary)
        self.assertIn(' · bounded second review · ', second)

    def test_a_second_review_that_was_not_sent(self):
        encounter_id = self.asked(SecondUnbuildable(first=[SNARE], later=[BIOPSY]))
        drain()
        self.assertEqual([(r.purpose, r.state) for r in self.runs(encounter_id)],
                         [('primary', 'succeeded'), ('second_review', 'not_sent')])
        rows = provider_rows(page(self.detail(encounter_id))['timeline'])
        self.assertIn('| Corti · live · Second review · Not sent |', rows)
        second = usage_lines(self.draft(encounter_id))[1]
        self.assertIn(' · not_sent · revision 1 · bounded second review · recorded ', second)
        self.assertTrue(second.endswith(' · nothing was sent'), second)

    def test_an_unknown_second_review_is_named_where_it_must_be_reconciled(self):
        encounter_id = self.asked(TwoPassProvider(first=[SNARE], later=[BIOPSY], outcomes=['succeeded', 'unknown']))
        drain()
        shown = page(self.detail(encounter_id))
        self.assertIn('| Corti · live · Second review · Outcome unknown |', provider_rows(shown['timeline']))
        self.assertIn('Unreconciled request | Second review · ', shown['codes'])
        second = usage_lines(self.draft(encounter_id))[1]
        self.assertIn(' · unknown · revision 1 · bounded second review · requested ', second)
        self.assertNotIn('by this assessment', second)  # the assessment never read it

    def test_a_requested_second_review_is_described_as_requested_until_it_runs(self):
        encounter_id = self.asked(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        detail = self.detail(encounter_id)
        self.assertIn('Processing has not finished', detail['readiness']['blockers'])
        shown = page(detail)
        self.assertIn('Second provider review requested | A reviewer asked for it; it is waiting to run, and nothing '
                      'has been sent yet.', shown['codes'])
        self.assertNotIn('before asking for a second review', shown['codes'])
        self.assertNotIn('data-action="second-review"', shown['codesHtml'])
        self.assertIn('Second provider review (asked for by a reviewer) | Waiting', shown['codes'])  # the progress card
        self.assertEqual(len(self.runs(encounter_id)), 1)  # nothing was sent yet

    def test_a_stopped_second_review_is_never_offered_again(self):
        encounter_id = self.asked(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        drain()
        self.assertEqual(ask(self.client, encounter_id).status_code, 409)  # its request is used: asking is refused
        shown = page(self.detail(encounter_id))
        self.assertIn('Second provider review stopped | It was stopped before anything was sent: Stopped by a '
                      'workspace member. Resume processing runs it once.', shown['codes'])
        self.assertNotIn('data-action="second-review"', shown['codesHtml'])
        self.assertIn('data-action="resume"', shown['codesHtml'])
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        drain()
        self.assertEqual(len(self.provider.requests), 2)  # resumed, it runs once

    def test_a_second_review_stage_that_failed_never_reads_provider_not_run(self):
        """The reviewer who asked lost the reviewer role before the worker ran it: the live gate refuses the stage
        before anything is built or sent. The primary request succeeded and its proposal stands."""
        encounter_id = self.asked(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        models.Membership.objects.filter(user=self.reviewer).update(role=models.Membership.VIEWER)
        drain()
        models.Membership.objects.filter(user=self.reviewer).update(role=models.Membership.REVIEWER)
        self.assertEqual(models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.REVIEW2).state,
                         models.Job.FAILED)
        self.assertEqual([(r.purpose, r.state) for r in self.runs(encounter_id)], [('primary', 'succeeded')])
        detail = self.detail(encounter_id)
        self.assertEqual(detail['state'], 'ready_for_review')
        shown = page(detail)
        self.assertNotIn('No proposals were', shown['codes'])
        self.assertNotIn('did not run for this revision', shown['codes'])
        self.assertIn('Second provider review did not complete | It did not complete: Only an owner or reviewer of '
                      'this workspace can start a live provider request.', shown['codes'])
        self.assertNotIn('data-action="second-review"', shown['codesHtml'])
        self.assertEqual(ask(self.client, encounter_id).status_code, 409)

    def test_control_a_second_review_skipped_as_a_repeat_says_why(self):
        """Another encounter's primary request answered the same excerpt after the reviewer asked: the stage sends
        nothing (it would repeat an answered request). No run is listed and the card says why."""
        encounter_id = self.asked(TwoPassProvider(first=[SNARE], later=[BIOPSY]))
        encounter = models.Encounter.objects.get(pk=encounter_id)
        _, (start, end) = jobs._second_review_items(encounter.current_assessment)
        excerpt = encounter.current_revision.text[start:end]
        primary = encounter.current_assessment.provider_run
        request = self.provider.build_request(excerpt, primary.service_date)
        other = f.encounter(self.ws, self.reviewer, title='Another synthetic note')
        revision = f.pasted_revision(other, self.reviewer, excerpt)
        models.ProviderRun.objects.create(
            encounter=other, revision=revision, provider=self.provider.name,
            adapter_version=self.provider.adapter_version, request_sha256=request.canonical_sha256,
            request_body=request.body, contexts=list(request.contexts), state=models.ProviderRun.SUCCEEDED, sent=True,
            response_bytes=b'{"codes": []}', response_sha256=hashlib.sha256(b'{"codes": []}').hexdigest(),
            service_date=primary.service_date)
        drain()
        job = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.REVIEW2)
        self.assertIn('would repeat a primary request', job.result['skipped'])
        self.assertEqual(len(self.provider.requests), 1)
        shown = page(self.detail(encounter_id))
        self.assertNotIn('Second review', provider_rows(shown['timeline']))
        self.assertIn('a request the provider already answered, so a second review would ask nothing new',
                      shown['codes'])
        self.assertNotIn('data-action="second-review"', shown['codesHtml'])
        self.assertEqual(len(usage_lines(self.draft(encounter_id))), 1)


class LatestStageExplainsTests(Pipeline):
    """The "No proposals were requested" card explains itself with the stage that did not run: the LATEST predict. A
    date change re-requests proposals; when that predict fails (here the reviewer who changed the date lost the role
    before the worker ran it), the card had shown the first predict - which ran - and said "The provider step did not
    run for this revision"."""

    def test_the_card_gives_the_failed_predicts_own_reason(self):
        self.use(FakeProvider(selections=[VISIT]))
        undated = OFFICE_NOTE.replace('Date of service: 2026-10-20\n', '')
        encounter_id = self.create(undated, service_date='2026-10-20')
        drain()
        reply = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-22'})
        self.assertEqual(reply.status_code, 201, reply.content)
        models.Membership.objects.filter(user=self.reviewer).update(role=models.Membership.VIEWER)
        drain()
        models.Membership.objects.filter(user=self.reviewer).update(role=models.Membership.REVIEWER)
        predicts = models.Job.objects.filter(encounter_id=encounter_id, kind=models.Job.PREDICT).order_by('created_at')
        self.assertEqual([j.state for j in predicts], [models.Job.SUCCEEDED, models.Job.FAILED])
        detail = self.detail(encounter_id)
        self.assertEqual(detail['state'], 'provider_not_run')
        shown = page(detail)['codes']
        self.assertIn('No proposals were | requested. | Only an owner or reviewer of this workspace can start a live '
                      'provider request.', shown)
        self.assertNotIn('did not run for this revision', shown)


class FailedCardNamesTheRunInUseTests(Pipeline):
    """The "provider request failed" card explains itself with the run the current assessment read. It took the
    encounter's last FAILED run instead, so after a date change whose request was refused before sending it showed the
    earlier request's error for another date."""

    def test_the_card_gives_the_reason_of_the_run_in_use(self):
        self.use(FailsThenRefusesToSend(selections=[VISIT]))
        undated = OFFICE_NOTE.replace('Date of service: 2026-10-20\n', '')
        encounter_id = self.create(undated, service_date='2026-10-20')
        drain()
        reply = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': '2026-10-22'})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        self.assertEqual([r.state for r in self.runs(encounter_id)], ['failed', 'not_sent'])
        detail = self.detail(encounter_id)
        self.assertEqual(detail['state'], 'provider_failed')
        shown = page(detail)['codes']
        self.assertIn('The provider request | failed. | Error: The credentials could not be read; nothing was sent.',
                      shown)
        self.assertNotIn('HTTP 500 from the provider', shown)
