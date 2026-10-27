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
- the second review a reviewer asks for (8985dde42): described truthfully while it waits, and once it was not sent or
  its outcome is unknown.
Synthetic data only; no network: an in-process provider stands in for the live adapter.
"""
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
  process.stdout.write(JSON.stringify({
    exportStatus: app.exportStatusText(doc),
    timeline: text(app.reviewView(doc, app.documentLayout(doc), 'timeline', false)),
    codes: text(app.reviewView(doc, app.documentLayout(doc), 'codes', false)),
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
