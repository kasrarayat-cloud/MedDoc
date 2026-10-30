"""CPT Studio GI round 3, fix round 2 (STATE2-1): a pre-install encounter read again while sending is disabled.

gi-context@2 is an earlier context version (interpretation 49), so the next stage that runs on such a context remakes it
under the current rules. With sending disabled - an install's or an incident's provider-mode switch - the remake could
not tell that the recorded answer still answers the remade context's request, so it queued the upgrade's predict, and
that predict assessed with no answer: every proposal of a reviewed encounter was dropped and the reviewer's decisions on
it invalidated ("99214 is no longer proposed"), on a Resume and with no member action at all (the stale-stage sweep).
Second refutation of the integrated third round, lens state. Now the request is compared without an enabled provider
(the adapter's own builder, jobs._request_for), and the upgrade's predict stops rather than assess with no answer.

Each test records the installed pair's rows under 90377ec6f413's labels (and, for h2-08, its own facts: the fixture of
test_repairs_gi3_upgrade); then the swap - the patches end - and this revision's code runs every later stage with
sending disabled. Synthetic data only; FakeProvider stands in for the provider while sending is enabled.
"""
import contextlib
import json
from datetime import timedelta
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings
from django.utils import timezone

from studio import jobs, models, review
from studio.types import Fact, from_jsonable
from tests.support import factories as f
from tests.test_pipeline_api import FakeProvider

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'gi3'
H206 = (FIXTURES / 'live-text' / 'h2-06__8d5aa436__2026-10-29.txt').read_text(encoding='utf-8')
H206_TIME = 'Time spent on the date of the encounter: 33 minutes'
H208 = (FIXTURES / 'live-text' / 'h2-08__e084b793__2026-10-29.txt').read_text(encoding='utf-8')
H208_INSTALLED = json.loads((FIXTURES / 'upgrade' / 'h2-08-context-90377ec6.json').read_text(encoding='utf-8'))
H208_PLAN = 'Cirrhosis with new ascites, now decompensated.'
LIVE_SETTINGS = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
INSTALLED_LABELS = {'CONTEXT_VERSION': 'gi-context@2', 'EARLIER_CONTEXT_VERSIONS': ('gi-context@1',)}


@override_settings(**LIVE_SETTINGS)
class SendingDisabledAfterTheInstallTests(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = FakeProvider()
        self.provider_patch = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        self.provider_patch.start()
        self.addCleanup(mock.patch.stopall)

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
        ran = []
        while (job := jobs.claim_next()) is not None:
            jobs.run_job(job)
            job.refresh_from_db()
            ran.append((job.kind, job.state))
        return ran

    @contextlib.contextmanager
    def installed(self, facts=None):
        """90377ec6f413's labels, and its own reader's facts where the reading differs (h2-08)."""
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.multiple(jobs, **INSTALLED_LABELS))
            if facts is not None:
                read = {name: from_jsonable(Fact, value) for name, value in facts.items()}
                stack.enter_context(mock.patch('studio.gi.context.extract_context', return_value=read))
            yield

    def reviewed_before_the_install(self, text, code, quote, facts=None):
        """The installed pair's whole chain, then a reviewer's rejection of ``code``: the live state of a reviewed
        encounter recorded before the install."""
        self.provider.selections = [(code, quote)]
        encounter_id = self.upload(text)
        with self.installed(facts):
            self.drain()
            encounter = models.Encounter.objects.get(pk=encounter_id)
            self.assertEqual(encounter.current_context.version, 'gi-context@2')
            proposal = encounter.current_assessment.proposals.get(code=code)
            reply = self.post(f'/api/encounters/{encounter_id}/decisions',
                              {'proposal_id': str(proposal.pk), 'action': models.Decision.REJECT,
                               'note': 'Synthetic reviewer note.'})
            self.assertEqual(reply.status_code, 201, reply.content)
        return encounter_id

    def the_swap(self):
        """The install's swap with sending disabled: the stand-in provider goes, and get_provider() answers None."""
        self.provider_patch.stop()
        return override_settings(PROVIDER_MODE='disabled')

    def current(self, encounter_id):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        decisions = review.current_decisions(encounter.current_assessment) if encounter.current_assessment else {}
        return encounter, {d.proposal.code: d.action for d in decisions.values()}

    def test_a_stopped_assess_resumed_with_sending_disabled_keeps_the_answer_and_the_decision(self):
        """The reviewer's u2: a billing save queued an assess with the run in use; the encounter was stopped for the
        install; the member resumes it after a swap that disabled sending."""
        encounter_id = self.reviewed_before_the_install(H206, '99214', H206_TIME)
        with self.installed():
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                       {'service_date': '2026-10-14'}).status_code, 201)
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        sent = len(self.provider.sent)
        with self.the_swap():
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
            self.drain()
        encounter, decisions = self.current(encounter_id)
        self.assertEqual(encounter.current_context.version, jobs.CONTEXT_VERSION)  # read again under this revision
        self.assertIsNotNone(encounter.current_assessment.provider_run_id)  # with the recorded answer, not with none
        self.assertEqual(encounter.current_assessment.context_id, encounter.current_context_id)  # re-assessed, not kept
        self.assertTrue(encounter.current_assessment.proposals.filter(code='99214').exists())
        self.assertEqual(decisions, {'99214': models.Decision.REJECT})  # the reviewer's decision carried
        self.assertFalse(models.DecisionInvalidation.objects.filter(decision__encounter=encounter).exists())
        self.assertEqual(len(self.provider.sent), sent)  # nothing sent

    def test_a_swept_predict_with_sending_disabled_is_assessed_with_its_answer(self):
        """The reviewer's w1, with no member action: the installed worker died after its predict's run was recorded and
        before it queued the assess; the stale-stage sweep settles the predict after a swap that disabled sending."""
        self.provider.selections = [('99214', H206_TIME)]
        encounter_id = self.upload(H206)
        with self.installed():
            self.run_one(models.Job.EXTRACT)
            self.run_one(models.Job.ANALYZE)
            predict = self.run_one(models.Job.PREDICT)
        models.Job.objects.filter(kind=models.Job.ASSESS, encounter_id=encounter_id).delete()
        models.Job.objects.filter(pk=predict.pk).update(state=models.Job.RUNNING, finished_at=None,
                                                        started_at=timezone.now() - timedelta(hours=1))
        with self.the_swap():
            jobs.mark_stale()
            self.drain()
        encounter, _ = self.current(encounter_id)
        self.assertEqual(encounter.current_context.version, jobs.CONTEXT_VERSION)
        self.assertIsNotNone(encounter.current_assessment.provider_run_id)
        self.assertTrue(encounter.current_assessment.proposals.filter(code='99214').exists())

    def test_the_upgrades_predict_stops_with_sending_disabled_and_the_decisions_stay(self):
        """h2-08: the remade context's request differs (its two dates conflict, so the request carries no date). With
        sending disabled the upgrade's predict stops - nothing is sent and nothing is assessed with no answer - and the
        recorded assessment and its decision stay current."""
        encounter_id = self.reviewed_before_the_install(H208, '99215', H208_PLAN, facts=H208_INSTALLED)
        with self.installed(H208_INSTALLED):
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                       {'billing_context': 'professional'}).status_code, 201)
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        before, _ = self.current(encounter_id)
        with self.the_swap():
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
            ran = self.drain()
        encounter, decisions = self.current(encounter_id)
        self.assertEqual(encounter.current_context.version, jobs.CONTEXT_VERSION)
        self.assertEqual(encounter.current_context.facts['service_date']['origin'], 'conflict')
        self.assertIn((models.Job.PREDICT, models.Job.CANCELLED), ran)
        stopped = models.Job.objects.get(encounter_id=encounter_id, kind=models.Job.PREDICT,
                                         idempotency_key=jobs._upgrade_predict_key(encounter.current_context))
        self.assertEqual((stopped.state, stopped.error), (models.Job.CANCELLED, jobs.REMADE_DISABLED_MESSAGE))
        self.assertEqual(encounter.current_assessment_id, before.current_assessment_id)  # nothing assessed with none
        self.assertEqual(decisions, {'99215': models.Decision.REJECT})
        self.assertFalse(models.DecisionInvalidation.objects.filter(decision__encounter=encounter).exists())
        self.assertEqual(len(self.provider.sent), 1)  # the installed pair's one request, nothing since

    def test_a_members_unchanged_save_with_sending_disabled_rechecks_with_the_recorded_answer(self):
        """A save that leaves the request unchanged re-checks with the run in use and never re-sends (ARCHITECTURE 5.4)
        - with sending disabled too, where the save used to assess with no answer. The documented date saved as the
        member's changes neither the request nor any fingerprint value, so the decision carries. (A billing or setting
        save changes an E/M's fingerprint and invalidates its decision whether or not sending is enabled.)"""
        encounter_id = self.reviewed_before_the_install(H206, '99214', H206_TIME)
        with self.the_swap():
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                       {'service_date': '2026-10-14'}).status_code, 201)
            self.drain()
        encounter, decisions = self.current(encounter_id)
        self.assertIsNotNone(encounter.current_assessment.provider_run_id)
        self.assertEqual(encounter.current_assessment.context_id, encounter.current_context_id)
        self.assertEqual(decisions, {'99214': models.Decision.REJECT})

    def test_controls_live_sending_is_unchanged(self):
        """Control: the same Resume as the first test with sending enabled re-assesses with the recorded answer, and the
        upgrade's predict for h2-08 stops where it would send, as before (test_repairs_gi3_upgrade)."""
        encounter_id = self.reviewed_before_the_install(H206, '99214', H206_TIME)
        with self.installed():
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/context',
                                       {'service_date': '2026-10-14'}).status_code, 201)
            self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        sent = len(self.provider.sent)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        self.drain()
        encounter, decisions = self.current(encounter_id)
        self.assertIsNotNone(encounter.current_assessment.provider_run_id)
        self.assertEqual(decisions, {'99214': models.Decision.REJECT})
        self.assertEqual(len(self.provider.sent), sent)


class RequestWithSendingDisabledTests(TestCase):
    """jobs._request_for with sending disabled builds only a request this revision's adapters build: an answer recorded
    by another adapter (an older one, another provider) is never taken as answering the current request."""

    def run_of(self, provider, adapter_version, request_sha256='x'):
        return mock.Mock(provider=provider, adapter_version=adapter_version, request_sha256=request_sha256)

    @override_settings(PROVIDER_MODE='disabled')
    def test_another_adapters_run_is_never_compared(self):
        revision = mock.Mock(text=H206)
        context = mock.Mock(facts={'service_date': {'origin': 'document', 'value': '2026-10-14'}})
        self.assertIsNone(jobs._request_for(self.run_of('corti', 'corti-coding-v1@older'), revision, context))
        self.assertIsNone(jobs._request_for(self.run_of('elsewhere', jobs.CortiProvider.adapter_version), revision,
                                            context))
        built = jobs._request_for(self.run_of('corti', jobs.CortiProvider.adapter_version), revision, context)
        self.assertEqual(built.canonical_sha256,
                         FakeProvider().build_request(H206, jobs.context_service_date(context)).canonical_sha256)
