"""Refutation r1, cluster M (upgrade and restore paths). Synthetic data only; no network.

migrate-4: a member-entered service date that conflicts with the document's is held (session interpretation 19), but the
  hold was decided only inside this revision's predict stage. Every member action queued a plain predict for the
  conflicted context, so the installed revision's worker - restored after a failed replacement, or reinstalled -
  read the stored conflict as "no date" and sent a paid request without one, at once or on a later Resume. The hold is
  now recorded where it is decided: no path queues a job that can send for such a context.
"""
import json
from datetime import date
from unittest import mock

from django.test import TestCase, override_settings

from studio import jobs, models, review
from studio.gi import context as gi_context
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, FakeProvider, drain

LIVE = dict(PROVIDER_MODE='live', AUTHORIZATION_REF='docs/foundation/rulings/2026-10-23-cpt-studio-gi.md')
DOCUMENTED = date(2026, 10, 20)  # OFFICE_NOTE's own date
TWO_DATES = OFFICE_NOTE.replace('Date of service: 2026-10-20\n',
                                'Date of service: 2026-10-20\nDate of service: 2026-10-23\n')
UNDATED = OFFICE_NOTE.replace('Date of service: 2026-10-20\n', '')
REPORT = """SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE
Colonoscopy report (fictional) M1
Date of service: 2026-10-16
Place of service: Hospital outpatient department
The colonoscope was advanced to the cecum and the examination was completed.
A 6 mm polyp in the rectum was removed with a cold snare.
"""
VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')
SNARE = ('45385', 'was removed with a cold snare')


class Provider(FakeProvider):
    """FakeProvider whose response names only the selections the request's own text contains."""

    def send(self, request, *, deadline_s):
        every = self.selections
        self.selections = [(code, quote) for code, quote in every if quote in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.selections = every


def member_conflict(context):
    return gi_context.is_member_conflict((context.facts or {}).get('service_date'))


@override_settings(**LIVE)
class MemberDateConflictIsHeldWhereDecidedTests(TestCase):
    """migrate-4: whichever path would start the request for a context whose service date is a member conflict records
    the not-sent held run itself and queues only the assess that reads it - never a predict that a worker reading the
    conflict under other rules would send."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(selections=[VISIT, SNARE])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- helpers ---------------------------------------------------------------------------------------------------

    def upload(self, text=OFFICE_NOTE, **extra):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()['id']

    def finished(self, text=OFFICE_NOTE, **extra):
        encounter_id = self.upload(text, **extra)
        drain()
        return encounter_id

    def post(self, path, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def set_date(self, encounter_id, value):
        response = self.post(f'/api/encounters/{encounter_id}/context', {'service_date': value})
        self.assertEqual(response.status_code, 201, response.content)

    def run_one(self):
        job = jobs.claim_next()
        self.assertIsNotNone(job)
        jobs.run_job(job)
        return job

    def assert_held_at_queue(self, encounter_id):
        """Nothing that can send is queued for the conflicted context: one assess whose run is the recorded hold."""
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertTrue(member_conflict(encounter.current_context))
        queued = list(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED))
        self.assertEqual([job.kind for job in queued], [models.Job.ASSESS])
        self.assertEqual(queued[0].context_id, encounter.current_context_id)
        held = queued[0].provider_run
        self.assertIsNotNone(held)
        self.assertEqual((held.state, held.sent, held.service_date, held.request_sha256, held.contexts),
                         (models.ProviderRun.NOT_SENT, False, None, '', []))
        self.assertEqual(held.scope, {'held': models.ProviderRun.HELD_MEMBER_DATE_CONFLICT})
        self.assertEqual(held.error, jobs.MEMBER_DATE_CONFLICT_MESSAGE)
        self.assert_no_predict_for_a_member_conflict(encounter_id)
        return held

    def assert_no_predict_for_a_member_conflict(self, encounter_id):
        """No predict for a member-conflicted context is queued, or left as the stage a Resume would run again."""
        predicts = (models.Job.objects.select_related('context')
                    .filter(encounter_id=encounter_id, kind=models.Job.PREDICT,
                            state__in=(models.Job.QUEUED, models.Job.RUNNING)))
        self.assertEqual([job.idempotency_key for job in predicts if job.context and member_conflict(job.context)], [])
        latest = review.latest_job(models.Encounter.objects.get(pk=encounter_id))
        self.assertFalse(latest.kind == models.Job.PREDICT and latest.state == models.Job.CANCELLED
                         and member_conflict(latest.context), latest.idempotency_key)

    def assert_settled_on_the_date_question(self, encounter_id, held):
        encounter = models.Encounter.objects.get(pk=encounter_id)
        self.assertEqual(encounter.state, 'needs_clarification')
        self.assertEqual(encounter.current_assessment.provider_run_id, held.pk)
        self.assertIn('Nothing was sent: the service date entered as encounter metadata conflicts with the document',
                      review.readiness(encounter)['blockers'])
        detail = self.client.get(f'/api/encounters/{encounter_id}').json()
        self.assertTrue([q for q in detail['clarifications'] if q['fact'] == 'service_date'])

    # --- the member's own change, the finding's input and its paraphrases ------------------------------------------

    def test_a_conflicting_member_date_queues_only_the_assess_of_a_recorded_hold(self):
        for text, value in ((OFFICE_NOTE, '1998-01-01'), (OFFICE_NOTE, '2026-10-22'), (REPORT, '1998-01-01')):
            with self.subTest(document=text.splitlines()[2][:40], value=value):
                encounter_id = self.finished(text)
                sent = len(self.provider.sent)
                self.set_date(encounter_id, value)
                held = self.assert_held_at_queue(encounter_id)
                self.assertEqual(held.requested_by_id, self.reviewer.pk)
                drain()
                self.assertEqual(len(self.provider.sent), sent)
                self.assert_settled_on_the_date_question(encounter_id, held)

    def test_controls_a_member_date_beside_dates_the_document_disputes_rechecks_the_run_in_use(self):
        # a third side to the document's own conflict: the request in use was already made without a date, so the
        # change re-checks that run - and no predict is queued for the member conflict either way
        encounter_id = self.finished(TWO_DATES)
        sent = len(self.provider.sent)
        self.set_date(encounter_id, '2026-10-22')
        self.assertTrue(member_conflict(models.Encounter.objects.get(pk=encounter_id).current_context))
        self.assert_no_predict_for_a_member_conflict(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), sent)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'needs_clarification')

    def test_a_member_date_conflict_entered_at_upload_is_held_by_the_analysis(self):
        encounter_id = self.upload(OFFICE_NOTE, service_date='1998-01-01')
        self.assertEqual(self.run_one().kind, models.Job.EXTRACT)
        self.assertEqual(self.run_one().kind, models.Job.ANALYZE)
        held = self.assert_held_at_queue(encounter_id)
        drain()
        self.assertEqual(self.provider.sent, [])
        self.assert_settled_on_the_date_question(encounter_id, held)

    # --- a Stop, a Resume and a reconciliation on the conflicted context ---------------------------------------------

    def test_a_stopped_hold_resumes_as_the_same_hold(self):
        encounter_id = self.finished()
        self.set_date(encounter_id, '1998-01-01')
        held = self.assert_held_at_queue(encounter_id)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        self.assertEqual(self.assert_held_at_queue(encounter_id).pk, held.pk)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    def stopped_with_latest(self, encounter_id, kind, context):
        """Leave ``kind`` for ``context`` as the encounter's latest stage, cancelled by a member's Stop."""
        encounter = models.Encounter.objects.get(pk=encounter_id)
        jobs.enqueue(kind, encounter=encounter, revision=encounter.current_revision, context=context,
                     key=f'{kind}:{context.pk}:left-cancelled', requested_by=self.reviewer)
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/stop').status_code, 200)
        self.assertEqual(review.latest_job(encounter).kind, kind)
        self.assertTrue(review.can_resume(encounter))

    def test_resuming_a_cancelled_predict_on_a_conflicted_context_records_the_hold(self):
        # a predict an earlier state of this code queued for the conflicted context, then stopped
        encounter_id = self.finished()
        self.set_date(encounter_id, '1998-01-01')
        drain()
        context = models.Encounter.objects.get(pk=encounter_id).current_context
        self.stopped_with_latest(encounter_id, models.Job.PREDICT, context)
        holds = models.ProviderRun.objects.filter(encounter_id=encounter_id, state=models.ProviderRun.NOT_SENT).count()
        response = self.post(f'/api/encounters/{encounter_id}/resume')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json(), {'resumed': models.Job.ASSESS})
        held = self.assert_held_at_queue(encounter_id)
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                           state=models.ProviderRun.NOT_SENT).count(), holds + 1)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    def test_resuming_an_assess_whose_context_changed_while_stopped_records_the_hold(self):
        # the cancelled assess was for the documented context; the current one is a member conflict, so a Resume
        # starts again from the request - which is held, not queued
        encounter_id = self.finished()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        documented = encounter.current_context
        self.stopped_with_latest(encounter_id, models.Job.ASSESS, documented)
        encounter.user_values = {'service_date': '1998-01-01'}
        encounter.save(update_fields=['user_values', 'updated_at'])
        conflicted = jobs.make_context(encounter, encounter.current_revision)
        models.Encounter.objects.filter(pk=encounter_id).update(current_context=conflicted)
        self.assertTrue(member_conflict(conflicted))
        self.assertEqual(self.post(f'/api/encounters/{encounter_id}/resume').status_code, 201)
        held = self.assert_held_at_queue(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    def test_reconciling_an_unknown_outcome_under_a_conflict_records_the_hold(self):
        self.provider.outcome = 'unknown'
        encounter_id = self.finished()
        unknown = models.ProviderRun.objects.get(encounter_id=encounter_id, state=models.ProviderRun.UNKNOWN)
        self.provider.outcome = 'succeeded'
        self.set_date(encounter_id, '1998-01-01')
        first = self.assert_held_at_queue(encounter_id)
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/reconcile',
                             {'provider_run_id': str(unknown.pk), 'note': 'Checked with the provider: nothing billed.'})
        self.assertEqual(response.status_code, 201, response.content)
        held = self.assert_held_at_queue(encounter_id)
        self.assertNotEqual(held.pk, first.pk)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    # --- the upgrade remake of an earlier context -----------------------------------------------------------------

    def test_an_earlier_context_remade_into_a_member_conflict_is_held_at_the_remake(self):
        encounter_id = self.finished()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        facts = dict(encounter.current_context.facts)
        facts['service_date'] = {'name': 'service_date', 'value': '1998-01-01', 'origin': 'user', 'evidence': [],
                                 'note': gi_context.USER_NOTE}
        earlier = models.EncounterContext.objects.create(
            encounter=encounter, revision=encounter.current_revision, facts=facts,
            user_values={'service_date': '1998-01-01'}, version='gi-context@1', sha256='0' * 64)
        encounter.user_values = {'service_date': '1998-01-01'}
        encounter.current_context = earlier
        encounter.save(update_fields=['user_values', 'current_context', 'updated_at'])
        jobs.enqueue(models.Job.PREDICT, encounter=encounter, revision=encounter.current_revision, context=earlier,
                     key=f'predict:{earlier.pk}', requested_by=self.reviewer)  # as the installed revision queued it
        remake = self.run_one()
        self.assertIn('remade', remake.result.get('skipped', ''))
        held = self.assert_held_at_queue(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assert_settled_on_the_date_question(encounter_id, held)

    # --- what keeps reading as it did -------------------------------------------------------------------------------

    def test_controls_every_other_date_still_queues_its_predict(self):
        cases = (
            # a document whose own dates conflict: the request goes without a date, as before, on both revisions
            ('internal conflict', TWO_DATES, {}, None, 1),
            # an undated document: the member's date supplies the date and is sent
            ('member date for an undated note', UNDATED, {'service_date': '2026-10-22'}, '2026-10-22', 1),
            # the member's date agrees with the document's
            ('agreeing member date', OFFICE_NOTE, {'service_date': '2026-10-20'}, '2026-10-20', 1),
        )
        for label, text, extra, sent_date, sends in cases:
            with self.subTest(label):
                encounter_id = self.upload(text, **extra)
                self.run_one()
                self.run_one()
                queued = list(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED))
                self.assertEqual([job.kind for job in queued], [models.Job.PREDICT])
                before = len(self.provider.sent)
                drain()
                self.assertEqual(len(self.provider.sent) - before, sends)
                run = models.ProviderRun.objects.filter(encounter_id=encounter_id).latest('created_at')
                self.assertEqual(run.service_date, date.fromisoformat(sent_date) if sent_date else None)
                self.assertFalse(models.ProviderRun.objects.filter(encounter_id=encounter_id,
                                                                   scope__held__isnull=False).exists())

    def test_controls_clearing_the_conflict_queues_the_predict_for_the_documented_date(self):
        """Clearing the conflict answers the documented date's request with its retained result and sends nothing.
        Since the ec5 integration a held run is no request's outcome (jobs._run_in_use skips it: standing as the run
        in use it had let a cleared conflict re-send a request that FAILED), so the re-check meets the documented run
        itself and re-assesses with it, where it queued a predict that reused that run; nothing is sent either way."""
        encounter_id = self.finished()
        self.set_date(encounter_id, '1998-01-01')
        drain()
        self.set_date(encounter_id, '')
        queued = list(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED))
        self.assertEqual([job.kind for job in queued], [models.Job.ASSESS])
        drain()
        self.assertEqual(len(self.provider.sent), 1)  # the documented request's retained result answers it
        assessment = models.Encounter.objects.get(pk=encounter_id).current_assessment
        run = assessment.provider_run
        self.assertEqual((run.state, run.service_date, (run.scope or {}).get('held')),
                         (models.ProviderRun.SUCCEEDED, DOCUMENTED, None))

    def test_a_setting_change_beside_the_conflict_is_held_at_the_change(self):
        encounter_id = self.finished()
        self.set_date(encounter_id, '1998-01-01')
        drain()
        response = self.post(f'/api/encounters/{encounter_id}/context', {'setting': 'office'})
        self.assertEqual(response.status_code, 201, response.content)
        self.assert_no_predict_for_a_member_conflict(encounter_id)
        drain()
        self.assertEqual(len(self.provider.sent), 1)
        self.assertEqual(models.Encounter.objects.get(pk=encounter_id).state, 'needs_clarification')

    def test_without_a_provider_the_conflict_queues_the_assess_and_records_nothing(self):
        encounter_id = self.finished()
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id).count()
        with mock.patch('studio.jobs.get_provider', return_value=None):
            self.set_date(encounter_id, '1998-01-01')
            queued = list(models.Job.objects.filter(encounter_id=encounter_id, state=models.Job.QUEUED))
            self.assertEqual([(job.kind, job.provider_run_id) for job in queued], [(models.Job.ASSESS, None)])
            drain()
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id).count(), runs)
        self.assert_no_predict_for_a_member_conflict(encounter_id)

    def test_controls_a_context_that_is_no_longer_current_is_never_held(self):
        # a predict for a superseded context records nothing: every revision's predict stage skips it
        encounter_id = self.finished()
        encounter = models.Encounter.objects.get(pk=encounter_id)
        encounter.user_values = {'service_date': '1998-01-01'}
        encounter.save(update_fields=['user_values', 'updated_at'])
        superseded = jobs.make_context(encounter, encounter.current_revision)
        self.assertTrue(member_conflict(superseded))
        runs = models.ProviderRun.objects.filter(encounter_id=encounter_id).count()
        job = jobs._queue_predict(encounter, encounter.current_revision, superseded, key='predict:superseded',
                                  requested_by=self.reviewer)
        self.assertEqual(job.kind, models.Job.PREDICT)
        self.assertEqual(models.ProviderRun.objects.filter(encounter_id=encounter_id).count(), runs)
        drain()
        job.refresh_from_db()
        self.assertEqual(job.result, {'skipped': 'the context is not the current one for this revision; nothing was '
                                                 'sent'})
        self.assertEqual(len(self.provider.sent), 1)


# --- migrate-3 and migrate-4, the installer's undo: what the new pair left open never runs under another revision ----
#
# install.py starts the new web before the new worker, and its failure path restarted the parked installed pair on the
# queue and records the new pair had written: the installed worker ended on a second review it has no stage for
# (KeyError outside run_job's try; its Resume re-queued it), and read what the new rules record under its own. Every
# undo - the app phase's failure path and rollback-app - now closes, as failed with the revision named, every stage
# the undone pair queued, ran or left resumable before any other pair runs; and the app phase refuses to start a pair
# while a stage its worker cannot run is open.

import datetime as dt  # noqa: E402
import importlib.util  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from django.test import SimpleTestCase  # noqa: E402
from django.utils import timezone  # noqa: E402

_SPEC = importlib.util.spec_from_file_location('cpt_studio_install_r1_m',
                                               Path(__file__).resolve().parents[1] / 'ops' / 'install.py')
install = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(install)

NEW_REVISION, OLD_REVISION = 'a' * 40, 'b' * 40


class DockerWorld:
    """Containers by name, and every docker call (and the undo) recorded in order with the moment it was made."""

    def __init__(self, *, previous=True, created='2026-10-27T12:00:00.123456789Z'):
        self.live, self.calls, self.fail, self.runs, self.failing_run, self.started = {}, [], {}, 0, None, []
        if previous:
            for role in ('web', 'worker'):
                self.live[install.SERVICES[role]] = self.container(f'old-{role}', role, 'old', OLD_REVISION, created)

    @staticmethod
    def container(cid, role, image, revision, created):
        return {'Id': cid, 'Image': image, 'Created': created, 'State': {'Running': True},
                'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role, install.REVISION_LABEL: revision}}}

    def record(self, *call):
        self.calls.append((*call, dt.datetime.now(dt.timezone.utc)))

    def inspect(self, kind, name):
        return self.live.get(name)

    def docker(self, *args, **kwargs):
        self.record(*args)
        self.runs += args[0] == 'run'
        if self.fail.get(args[:2]) or (args[0] == 'run' and self.runs == self.failing_run):
            raise install.InstallError(f'docker {args[0]} failed')
        if args[0] == 'rename':
            self.live[args[2]] = self.live.pop(args[1])
        elif args[0] == 'run':
            name = args[args.index('--name') + 1]
            role = 'web' if name == install.SERVICES['web'] else 'worker'
            self.live[name] = self.container(f'new-{role}', role, 'new', NEW_REVISION, '2026-10-27T12:30:00.5Z')
            self.started.append(name)
        elif args[0] == 'rm':
            for name, container in list(self.live.items()):
                if container['Id'] == args[2]:
                    del self.live[name]
        return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

    def close(self, image_id, env_bytes, since, revision, reason, kinds=None):
        self.record('close', image_id, revision)
        self.closed = {'image': image_id, 'env': env_bytes, 'since': since, 'revision': revision, 'reason': reason,
                       'kinds': kinds}
        if self.fail.get(('close',)):
            raise install.InstallError('the database did not answer')
        return {'closed': 3, 'hazards': {}}  # nothing an older revision would act on wrongly (7c8 p1install)

    def index(self, *call):
        return next(n for n, made in enumerate(self.calls) if made[:len(call)] == call)

    def ids(self):
        return {name: container['Id'] for name, container in self.live.items()}


class UndoClosesTheNewPairsStagesTests(SimpleTestCase):
    def replace(self, world, failing_role=None):
        def wait(role, revision, image_id):
            if role == failing_role:
                raise install.InstallError(f'{role} did not become ready')
            return {'id': f'new-{role}'}
        ctx = SimpleNamespace(revision=NEW_REVISION, log=lambda label, data: None)
        with mock.patch.object(install, 'inspect', world.inspect), mock.patch.object(install, 'docker', world.docker), \
                mock.patch.object(install, 'wait_service', wait), \
                mock.patch.object(install, 'close_undone_stages', world.close), \
                mock.patch.object(install, 'oneshot', side_effect=AssertionError('no real container in a test')):
            return install.replace_services(ctx, 'new', b'ENV=1\n', 'live', 'ruling.md')

    def test_a_failed_replacement_closes_the_new_pairs_stages_before_restoring_the_old_pair(self):
        # the worker fails readiness after the web served (the finding's path); the web itself fails; the worker's
        # container cannot even be started - each time the web had started, so it may have queued stages
        for label, failing_role, failing_run in (('worker not ready', 'worker', None), ('web not ready', 'web', None),
                                                 ('worker not started', None, 2)):
            with self.subTest(label):
                world = DockerWorld()
                world.failing_run = failing_run
                with self.assertRaises(install.InstallError) as caught:
                    self.replace(world, failing_role)
                self.assertNotIn('could not then be closed', str(caught.exception))  # the original failure is raised
                self.assertEqual(world.ids(), {install.SERVICES['web']: 'old-web',
                                               install.SERVICES['worker']: 'old-worker'})
                close = world.index('close')
                self.assertEqual((world.closed['image'], world.closed['env'], world.closed['revision']),
                                 ('new', b'ENV=1\n', NEW_REVISION))
                # the cut-off: after both old containers were parked, before the new web was created
                parked = world.calls[world.index('rename', install.SERVICES['web'])][-1]
                first_run = world.calls[world.index('run')][-1]
                self.assertLessEqual(parked, world.closed['since'])
                self.assertLessEqual(world.closed['since'], first_run)
                # stopped before the close, removed and restored only after it
                for role in ('web', 'worker'):
                    previous = install.SERVICES[role] + '-previous'
                    self.assertLess(close, world.index('rename', previous))
                    self.assertLess(close, world.index('start', install.SERVICES[role]))
                # every container the new pair started is stopped before the close (removed only after it)
                self.assertTrue(world.started)
                for name in world.started:
                    first_stop = next(n for n, made in enumerate(world.calls)
                                      if made[0] == 'stop' and made[3] == name and n > world.index('run'))
                    self.assertLess(first_stop, close)
                self.assertLess(close, world.index('rm', '--force', 'new-web'))

    def test_a_pair_whose_stages_cannot_be_closed_is_never_restored_over_them(self):
        world = DockerWorld()
        world.fail[('close',)] = True
        with self.assertRaises(install.InstallError) as caught:
            self.replace(world, 'worker')
        message = str(caught.exception)
        self.assertIn('worker did not become ready', message)
        self.assertIn('could not then be closed (the database did not answer)', message)
        self.assertIn('--phase rollback-app', message)
        self.assertEqual(world.ids(), {install.SERVICES['web'] + '-previous': 'old-web',
                                       install.SERVICES['worker'] + '-previous': 'old-worker',
                                       install.SERVICES['web']: 'new-web', install.SERVICES['worker']: 'new-worker'})
        self.assertFalse([call for call in world.calls if call[0] in ('start', 'rm')])
        self.assertTrue([call for call in world.calls if call[0] == 'stop' and call[-2] == install.SERVICES['web']])

    def test_controls_nothing_is_closed_when_no_new_pair_ran_or_no_old_pair_returns(self):
        # the web's park fails: no new container was ever started, and the parked worker comes back
        world = DockerWorld()
        world.fail[('rename', install.SERVICES['web'])] = True
        with self.assertRaises(install.InstallError):
            self.replace(world)
        self.assertFalse(hasattr(world, 'closed'))
        self.assertEqual(world.ids(), {install.SERVICES['web']: 'old-web', install.SERVICES['worker']: 'old-worker'})
        # a first install that fails: nothing is restored, so nothing is closed (its own revision runs it next)
        world = DockerWorld(previous=False)
        with self.assertRaises(install.InstallError):
            self.replace(world, 'worker')
        self.assertFalse(hasattr(world, 'closed'))
        self.assertEqual(world.ids(), {})
        # a replacement that succeeds closes nothing and removes the parked pair
        world = DockerWorld()
        self.replace(world)
        self.assertFalse(hasattr(world, 'closed'))
        self.assertEqual(world.ids(), {install.SERVICES['web']: 'new-web', install.SERVICES['worker']: 'new-worker'})


class RollbackAppClosesTheRemovedPairsStagesTests(SimpleTestCase):
    def rollback(self, world):
        ctx = SimpleNamespace(revision=NEW_REVISION)
        with mock.patch.object(install, 'inspect', world.inspect), mock.patch.object(install, 'docker', world.docker), \
                mock.patch.object(install, 'close_undone_stages', world.close), \
                mock.patch.object(install, 'undo_hazards', return_value={}), \
                mock.patch.object(install, 'require_db', lambda: world.record('require_db')), \
                mock.patch.object(install, 'read_protected_env', return_value=b'ENV=2\n'), \
                mock.patch.object(install, 'oneshot', side_effect=AssertionError('no real container in a test')):
            return install.phase_rollback_app(ctx)

    def running_new_pair(self):
        world = DockerWorld(previous=False)
        world.live[install.SERVICES['web']] = world.container('new-web', 'web', 'sha256:new', NEW_REVISION,
                                                              '2026-10-27T12:30:00.700000001Z')
        world.live[install.SERVICES['worker']] = world.container('new-worker', 'worker', 'sha256:new', NEW_REVISION,
                                                                 '2026-10-27T12:30:41.25Z')
        world.live[install.SERVICES['web'] + '-previous'] = world.container('old-web', 'web', 'old', OLD_REVISION,
                                                                            '2026-10-01T00:00:00Z')
        return world

    def test_rollback_app_closes_the_removed_pairs_stages_before_removing_it(self):
        world = self.running_new_pair()
        result = self.rollback(world)
        self.assertEqual(world.closed['image'], 'sha256:new')
        self.assertEqual(world.closed['env'], b'ENV=2\n')
        self.assertEqual(world.closed['revision'], NEW_REVISION)
        self.assertEqual(world.closed['since'], dt.datetime(2026, 10, 27, 12, 30, 0, 700000, tzinfo=dt.timezone.utc))
        close = world.index('close')
        stop_worker = world.index('stop', '--time', str(install.STOP_SECONDS['worker']), install.SERVICES['worker'])
        self.assertLess(stop_worker, close)
        self.assertLess(world.index('stop', '--time', str(install.STOP_SECONDS['web']), install.SERVICES['web']),
                        close)
        self.assertLess(world.index('require_db'), close)
        self.assertLess(close, world.index('rm', '--force', 'new-web'))
        self.assertLess(close, world.index('rm', '--force', 'new-worker'))
        self.assertEqual(world.ids(), {install.SERVICES['web'] + '-previous': 'old-web'})
        self.assertEqual(result['stages_closed'], {'closed': 3, 'hazards': {}})
        self.assertEqual(result['parked_left_in_place'], [install.SERVICES['web'] + '-previous'])

    def test_rollback_app_leaves_a_pair_it_cannot_close_stopped_and_in_place(self):
        world = self.running_new_pair()
        world.fail[('close',)] = True
        with self.assertRaises(install.InstallError) as caught:
            self.rollback(world)
        self.assertIn('stopped, not removed', str(caught.exception))
        self.assertIn('Rerun --phase rollback-app', str(caught.exception))
        self.assertFalse([call for call in world.calls if call[0] == 'rm'])
        self.assertEqual(set(world.ids()), {install.SERVICES['web'], install.SERVICES['worker'],
                                            install.SERVICES['web'] + '-previous'})

    def test_controls_rollback_app_without_a_pair_closes_nothing_and_refuses_a_foreign_one_untouched(self):
        world = DockerWorld(previous=False)
        result = self.rollback(world)
        self.assertFalse(hasattr(world, 'closed'))
        self.assertEqual((result['stages_closed'], result['removed']),
                         (None, {install.SERVICES['worker']: False, install.SERVICES['web']: False}))
        world = self.running_new_pair()
        world.live[install.SERVICES['web']]['Config']['Labels'][install.ROLE_LABEL] = 'other'
        with self.assertRaises(install.InstallError):
            self.rollback(world)
        self.assertEqual(world.calls, [])


class AppPhaseRefusesStagesItCannotRunTests(SimpleTestCase):
    def app(self, answer):
        ctx = SimpleNamespace(revision=NEW_REVISION, log=lambda label, data: 'log',
                              args=SimpleNamespace(provider_mode='disabled', authorization_ref=''))
        scripts = []

        def app_script(image_id, env, body, params, **kwargs):
            scripts.append(body)
            return {'encounters': []} if body == install.UNKNOWN_OUTCOMES else answer  # none unknown (7c8 p1install)
        with mock.patch.object(install, 'installed_image', return_value='sha256:image'), \
                mock.patch.object(install, 'require_db'), \
                mock.patch.object(install, 'read_protected_env', return_value=b''), \
                mock.patch.object(install, 'oneshot',
                                  return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')), \
                mock.patch.object(install, 'app_script', app_script), \
                mock.patch.object(install, 'replace_services', return_value={'started': {}}) as replace:
            try:
                return install.phase_app(ctx), replace, scripts
            except install.InstallError as error:
                return error, replace, scripts

    def test_the_app_phase_refuses_while_a_stage_its_worker_cannot_run_is_open(self):
        error, replace, scripts = self.app({'known': ['assess'], 'stuck': 2, 'kinds': ['review2']})
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('2 stage(s) of a kind this revision cannot run (review2)', str(error))
        self.assertIn('nothing was replaced', str(error))
        self.assertEqual(scripts, [install.UNRUNNABLE_STAGES])
        replace.assert_not_called()

    def test_controls_an_empty_answer_installs(self):
        details, replace, _ = self.app({'known': ['assess', 'review2'], 'stuck': 0, 'kinds': []})
        replace.assert_called_once()
        self.assertEqual(details['unrunnable_stages']['stuck'], 0)


class AppScriptTests(SimpleTestCase):
    def test_parameters_travel_as_data_and_exactly_one_answer_is_read(self):
        params = {'since': '2026-10-27T12:00:00+00:00', 'note': 'it\'s "closed"\nline two; `rm -rf`'}
        seen = {}

        def oneshot(image_id, command, env, **kwargs):
            seen['command'] = command
            namespace, lines = {}, []
            exec(compile(command[-1].split('\nANSWER = ')[0] + '\n', '<prelude>', 'exec'), namespace)
            seen['P'] = namespace['P']
            return SimpleNamespace(returncode=0, stderr=b'', stdout=b'5 objects imported automatically\n'
                                   + install.APP_SCRIPT_ANSWER.encode() + b'{"closed": 1}\n')
        with mock.patch.object(install, 'oneshot', oneshot):
            self.assertEqual(install.app_script('img', b'', 'pass\n', params, what='x'), {'closed': 1})
        self.assertEqual(seen['P'], params)
        self.assertEqual(seen['command'][:3], ['manage', 'shell', '-c'])
        self.assertNotIn('rm -rf', seen['command'][-1])  # only base64 of it
        for returncode, stdout in ((1, install.APP_SCRIPT_ANSWER.encode() + b'{}\n'), (0, b'nothing\n'),
                                   (0, (install.APP_SCRIPT_ANSWER + '{}\n').encode() * 2)):
            with self.subTest(returncode=returncode, stdout=stdout), self.assertRaises(install.InstallError), \
                    mock.patch.object(install, 'oneshot',
                                      return_value=SimpleNamespace(returncode=returncode, stdout=stdout, stderr=b'')):
                install.app_script('img', b'', 'pass\n', params, what='x')

    def test_docker_creation_times_are_read_to_the_microsecond_and_never_later(self):
        self.assertEqual(install.created_at({'Created': '2026-10-27T13:26:42.840047999Z'}),
                         dt.datetime(2026, 10, 27, 13, 26, 42, 840047, tzinfo=dt.timezone.utc))
        self.assertEqual(install.created_at({'Created': '2026-10-27T13:26:42Z'}),
                         dt.datetime(2026, 10, 27, 13, 26, 42, tzinfo=dt.timezone.utc))
        for raw in ('', '2026-10-27 13:26:42', '2026-10-27T13:26:42+02:00'):
            with self.subTest(raw=raw), self.assertRaises(install.InstallError):
                install.created_at({'Created': raw})


def run_app_script(body, params):
    """``body`` as `manage shell -c` runs it in the image (the installer's prelude first), here and on this database."""
    import base64
    payload = base64.b64encode(json.dumps(params).encode()).decode()
    lines = []
    namespace = {'print': lambda *args, **kwargs: lines.append(' '.join(str(a) for a in args))}
    exec(compile(install.APP_SCRIPT_PRELUDE.format(payload=payload, answer=install.APP_SCRIPT_ANSWER) + body,
                 '<app-script>', 'exec'), namespace)
    answers = [line for line in lines if line.startswith(install.APP_SCRIPT_ANSWER)]
    assert len(answers) == 1, lines
    return json.loads(answers[0][len(install.APP_SCRIPT_ANSWER):])


@override_settings(**LIVE)
class TheUndoScriptsOnTheDatabaseTests(TestCase):
    """The installer's in-image scripts, run against real rows: what the undone pair left open is closed as failed
    with its revision named; nothing else moves and nothing is removed."""

    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = self.client_class(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(selections=[VISIT, SNARE])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def encounter(self, tag):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/encounters', {'text': REPORT.replace('M1', tag),
                                                            'synthetic_attestation': 'yes'})
        drain()
        return models.Encounter.objects.get(pk=response.json()['id'])

    def stage(self, encounter, kind, state, *, created, started=None, tag=''):
        job = jobs.enqueue(kind, encounter=encounter, revision=encounter.current_revision,
                           context=encounter.current_context, key=f'{kind}:{encounter.pk}:{tag or state}',
                           requested_by=self.reviewer)
        models.Job.objects.filter(pk=job.pk).update(state=state, created_at=created, started_at=started)
        return models.Job.objects.get(pk=job.pk)

    def run_row(self, encounter, state, created):
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider='corti', adapter_version='test',
            request_sha256='f' * 64, request_body={}, contexts=[], state=state, requested_by=self.reviewer)
        models.ProviderRun.objects.filter(pk=run.pk).update(created_at=created)
        return run

    def test_the_close_fails_every_stage_the_undone_pair_left_open_and_nothing_else(self):
        swap = timezone.now() + dt.timedelta(minutes=1)  # every row below is placed on either side of it
        before, after = swap - dt.timedelta(seconds=30), swap + dt.timedelta(seconds=5)
        installed, queued2, stopped2, running, finished = (self.encounter(tag) for tag in 'ABCDE')
        # the installed pair's own work, queued before the park, runs under it
        old_queued = self.stage(installed, models.Job.ASSESS, models.Job.QUEUED, created=before)
        old_cancelled = self.stage(installed, models.Job.PREDICT, models.Job.CANCELLED, created=before, tag='c')
        # what the new pair left: a queued second review, one a member stopped, a predict cut mid-send, an assess the
        # new worker had claimed from the installed queue, and work it finished
        new_review2 = self.stage(queued2, models.Job.REVIEW2, models.Job.QUEUED, created=after)
        new_stopped = self.stage(stopped2, models.Job.REVIEW2, models.Job.CANCELLED, created=after)
        new_running = self.stage(running, models.Job.PREDICT, models.Job.RUNNING, created=after, started=after)
        claimed = self.stage(running, models.Job.ASSESS, models.Job.RUNNING, created=before, started=after, tag='cl')
        new_done = self.stage(finished, models.Job.ASSESS, models.Job.SUCCEEDED, created=after)
        sending = self.run_row(running, models.ProviderRun.SENDING, after)
        reserved = self.run_row(running, models.ProviderRun.RESERVED, after)
        old_sending = self.run_row(installed, models.ProviderRun.SENDING, before)
        self.assertTrue(review.can_resume(stopped2))
        counts = {model.__name__: model.objects.count() for model in (
            models.Job, models.ProviderRun, models.EncounterContext, models.Assessment, models.Decision,
            models.AuditEvent)}
        user_values = {e.pk: e.user_values for e in models.Encounter.objects.all()}

        note = 'Closed by the installer: undone (revision aaaaaaaaaaaa), so this stage will not run.'
        answer = run_app_script(install.CLOSE_STAGES, {'since': swap.isoformat(), 'note': note})

        # (7c8 p1install) the answer also names what an older revision would act on wrongly: here the send the undone
        # pair had in flight, now an unknown outcome that must be reconciled on this revision's web first
        self.assertEqual(answer, {'closed': 4, 'kinds': ['assess', 'predict', 'review2'], 'encounters': 3,
                                  'runs_unknown': 1, 'runs_not_sent': 1, 'hazards': {str(running.pk): ['unknown']}})
        for job in (new_review2, new_stopped, new_running, claimed):
            job.refresh_from_db()
            self.assertEqual((job.kind, job.state, job.error), (job.kind, models.Job.FAILED, note))
            self.assertIsNotNone(job.finished_at)
        for job, state in ((old_queued, models.Job.QUEUED), (old_cancelled, models.Job.CANCELLED),
                           (new_done, models.Job.SUCCEEDED)):
            job.refresh_from_db()
            self.assertEqual(job.state, state)
        for run, state in ((sending, models.ProviderRun.UNKNOWN), (reserved, models.ProviderRun.NOT_SENT),
                           (old_sending, models.ProviderRun.SENDING)):
            run.refresh_from_db()
            self.assertEqual(run.state, state)
        # failed, not cancelled: no Resume re-queues what was closed, and the encounters' state is recomputed
        for encounter in (queued2, stopped2, running):
            encounter.refresh_from_db()
            self.assertFalse(review.can_resume(encounter))
            self.assertNotEqual(encounter.state, 'processing')
        self.assertEqual(counts, {model.__name__: model.objects.count() for model in (
            models.Job, models.ProviderRun, models.EncounterContext, models.Assessment, models.Decision,
            models.AuditEvent)})
        self.assertEqual(user_values, {e.pk: e.user_values for e in models.Encounter.objects.all()})

    def test_the_queue_read_names_only_stages_this_revision_cannot_run(self):
        now = timezone.now()
        a, b, c = (self.encounter(tag) for tag in 'FGH')
        self.assertEqual(run_app_script(install.UNRUNNABLE_STAGES, {})['stuck'], 0)
        self.stage(a, 'review9', models.Job.QUEUED, created=now)
        self.stage(b, 'review9', models.Job.CANCELLED, created=now + dt.timedelta(seconds=1))  # b's latest stage
        older = self.stage(c, 'review9', models.Job.CANCELLED, created=now - dt.timedelta(days=1))
        self.stage(c, models.Job.ASSESS, models.Job.CANCELLED, created=now, tag='later')  # c's latest is known
        self.stage(c, 'review9', models.Job.FAILED, created=now - dt.timedelta(hours=1), tag='failed')
        answer = run_app_script(install.UNRUNNABLE_STAGES, {})
        self.assertEqual((answer['stuck'], answer['kinds']), (2, ['review9']))
        self.assertEqual(answer['known'], sorted(jobs.STAGES))
        self.assertNotEqual(review.latest_job(c).pk, older.pk)
