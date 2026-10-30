"""CPT Studio GI round 3, the upgrade: encounters 90377ec6f413 recorded before the third round's install.

The third round's binding reads h2-08's two dates of service as a conflict, where 90377ec6f413 recorded its context
(gi-context@2) with the header's 2026-10-05 as documented. Kept current after the install, that context was sent again
by a predict queued or stopped at the swap, a reconciliation and a reviewer-asked second review, and assessed as
documented (refutation of the integrated third round, STATE-1 and STATE-2). gi-context@2 is now an earlier version
(jobs.EARLIER_CONTEXT_VERSIONS): every stage remakes such a context under the current rules before it sends or assesses
anything, and no second review is offered or sent on one.

Each test records the installed pair's rows exactly: its extract and analyze run with 90377ec6f413's own facts
(tests/fixtures/gi3/upgrade/, copied from the synthetic live dump) under its own labels; then the swap - the patches
end - and this revision's code runs every later stage. Synthetic data only; FakeProvider stands in for the provider.
"""
import json
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from studio import jobs, models
from studio.types import Fact, from_jsonable
from tests.support import factories as f
from tests.test_pipeline_api import FakeProvider

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi3'
H208 = (FIXTURES / 'live-text' / 'h2-08__e084b793__2026-10-29.txt').read_text(encoding='utf-8')
H208_INSTALLED = json.loads((FIXTURES / 'upgrade' / 'h2-08-context-90377ec6.json').read_text(encoding='utf-8'))
PROC = (FIXTURES / 'upgrade' / 'proc-charge-block.txt').read_text(encoding='utf-8')
PROC_INSTALLED = json.loads((FIXTURES / 'upgrade' / 'proc-context-90377ec6.json').read_text(encoding='utf-8'))
LIVE_SETTINGS = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
INSTALLED_LABELS = {'CONTEXT_VERSION': 'gi-context@2', 'EARLIER_CONTEXT_VERSIONS': ('gi-context@1',)}


class DateLines(FakeProvider):
    """Records each request's date lines (everything after the document text)."""

    def __init__(self):
        super().__init__()
        self.date_lines = []

    def send(self, request, *, deadline_s):
        self.date_lines.append(list(request.contexts[1:]))
        return super().send(request, deadline_s=deadline_s)


@override_settings(**LIVE_SETTINGS)
class RecordedBeforeTheInstallTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = DateLines()
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def upload(self, text):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes'})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def post(self, path, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def run_one(self, kind):
        job = jobs.claim_next()
        self.assertEqual(job.kind, kind)
        jobs.run_job(job)
        return job

    def drain(self):
        while (job := jobs.claim_next()) is not None:
            jobs.run_job(job)

    def installed_rows(self, text, facts):
        """90377ec6f413's extract and analyze for ``text``: its own facts, recorded under its own labels."""
        encounter_id = self.upload(text)
        installed = {name: from_jsonable(Fact, value) for name, value in facts.items()}
        with mock.patch.multiple(jobs, **INSTALLED_LABELS):
            self.run_one(models.Job.EXTRACT)
            with mock.patch('studio.gi.context.extract_context', return_value=installed):
                self.run_one(models.Job.ANALYZE)
        context = models.Encounter.objects.get(pk=encounter_id).current_context
        self.assertEqual((context.version, context.facts['service_date']['value']), ('gi-context@2', '2026-10-05'))
        return encounter_id

    def assert_read_again(self, encounter_id):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(encounter.current_context.version, jobs.CONTEXT_VERSION)
        self.assertEqual(encounter.current_context.facts['service_date']['origin'], 'conflict')
        self.assertTrue(models.AuditEvent.objects.filter(encounter_id=encounter_id, event='context.remade').exists())

    def test_a_predict_queued_before_the_swap_reads_the_document_again(self):
        encounter_id = self.installed_rows(H208, H208_INSTALLED)
        self.drain()  # the swap: this revision's worker claims the installed pair's queued predict
        self.assert_read_again(encounter_id)
        self.assertEqual(self.provider.date_lines, [[]])  # one request, and no date line in it
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertIn('service_date', [q['fact'] for q in detail['clarifications']])

    def test_a_predict_stopped_before_the_swap_and_resumed_after_it(self):
        encounter_id = self.installed_rows(H208, H208_INSTALLED)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        self.drain()
        self.assert_read_again(encounter_id)
        self.assertEqual(self.provider.date_lines, [[]])

    def test_an_unknown_outcome_reconciled_after_the_swap(self):
        encounter_id = self.installed_rows(H208, H208_INSTALLED)
        self.provider.outcome = 'unknown'
        with mock.patch.multiple(jobs, **INSTALLED_LABELS):
            self.run_one(models.Job.PREDICT)  # the installed pair's send, with its date line
            self.drain()  # and what it queued, before the swap
        self.assertEqual(self.provider.date_lines, [['Date of service: 2026-10-05']])
        self.provider.outcome = 'succeeded'
        unknown = models.ProviderRun.objects.get(encounter_id=encounter_id, state=models.ProviderRun.UNKNOWN)
        reply = self.post(f'/api/encounters/{encounter_id}/reconcile',
                          {'provider_run_id': str(unknown.pk), 'note': 'Checked with the provider: nothing billed.'})
        self.assertEqual(reply.status_code, 201, reply.content)
        self.drain()
        self.assert_read_again(encounter_id)
        self.assertEqual(self.provider.date_lines[1:], [[]])  # the attempt reconciliation releases carries no date

    def test_an_assess_resumed_after_the_swap_assesses_nothing_on_the_old_date(self):
        encounter_id = self.installed_rows(H208, H208_INSTALLED)
        with mock.patch.multiple(jobs, **INSTALLED_LABELS):
            self.run_one(models.Job.PREDICT)  # the installed pair's send (2026-10-05)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)  # its assess, stopped
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        self.drain()
        self.assert_read_again(encounter_id)
        self.assertEqual(len(self.provider.date_lines), 1)  # nothing sent after the swap
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertNotEqual((encounter.current_assessment.summary or {}).get('service_date')
                            if encounter.current_assessment else None, '2026-10-05')

    def test_no_second_review_is_offered_or_sent_on_the_old_context(self):
        encounter_id = self.installed_rows(PROC, PROC_INSTALLED)
        with mock.patch.multiple(jobs, **INSTALLED_LABELS):
            self.drain()  # the installed pair's predict and assess, before the swap
        sent = len(self.provider.date_lines)
        offer = jobs.second_review_status(models.Encounter.objects.get(pk=encounter_id))
        self.assertFalse(offer['available'], offer)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/second-review').status_code, 409)
        self.drain()
        self.assertEqual(len(self.provider.date_lines), sent)
