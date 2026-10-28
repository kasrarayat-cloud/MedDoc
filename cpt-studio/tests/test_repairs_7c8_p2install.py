"""Refutation phase 2 over 20568b077, cluster P2INSTALL: rollback safety and report truth around an install (must-fix
class 3, a screen misstating persisted state, reached through the documented rollback and recovery paths; class 5).
Synthetic data only; no network: the provider is an in-process stand-in with the live adapter's name and version, the
installer's in-image scripts run here, on this test database, exactly as `manage shell -c` runs them, and Docker is a
stand-in that records every call.

Every document opens with the synthetic banner.

- install2:1: after rollback-app and the documented reinstall, the installed revision 057a7d39 listed a response this
  revision refused whole as 'Provider request failed' ('The provider request failed. / The provider did not return
  proposals.') although its only request succeeded (HTTP 200). This revision stores provider_failed for it and words
  its label from the run ('Provider response not used'); the upgrade's RECOMPUTE_STATES rewrote 057a7d39's own
  no_codes to it; 057a7d39 labels a stored state by its name alone and never recomputes one. The failure path of `app`
  handed the same rows to the restored pair.
- install2:2: when `app` stopped between the swap and RECOMPUTE_STATES (a failed `docker rm` of the parked pair, an
  interrupted installer), the receipt said only that the removal failed (nothing at all after a Ctrl-C), and the
  documented recovery - "to keep the new pair, remove them by hand" - kept the replaced revision's states: a response
  refused whole listed 'No CPT codes proposed', an unreconciled unknown outcome 'Ready for review'.

What 057a7d39 shows for these rows was measured with its real code (git archive of 057a7d398, its web and worker on a
scratch copy of this database, a socket guard): the repair's cross-revision probes. Here its list label is its
STATE_LABELS entry for the stored state - byte-identical to this revision's - and its own derivation of a list state is
INSTALLED_STATES, the port those probes proved equal to its review._derive_state.
"""
import hashlib
import io
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from django.test import Client, SimpleTestCase, TestCase, override_settings

from studio import models, review
from studio.types import RawExchange
from tests.support import factories as f
from tests.test_pipeline_api import OFFICE_NOTE, drain
from tests.test_repairs_r1_m import NEW_REVISION, OLD_REVISION, DockerWorld, install, run_app_script
from tests.test_services_second_review import LIVE, TwoPassProvider

BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE'
VISIT = ('99213', 'Total time on the date of the encounter was 24 minutes.')
MEMBER_CONFLICT = '2026-09-01'  # differs from OFFICE_NOTE's documented 2026-10-20
REPORT = f"""{BANNER}
Colonoscopy report (fictional)
Date of service: 2026-10-16
Place of service: Hospital outpatient department
The colonoscope was advanced to the cecum and the examination was completed.
A 6 mm polyp in the rectum was removed with a cold snare.
A separate 10 mm flat lesion in the transverse colon was sampled with cold biopsy forceps; it was not removed.
"""  # the provider proposes the snare only: the biopsy is a documented service without one, so a second review may be asked
SNARE = ('45385', 'was removed with a cold snare')
OLD_IMAGE, NEW_IMAGE = 'sha256:' + 'b' * 64, 'sha256:' + 'a' * 64
SCRIPTS = ('UNDO_HAZARDS_READ', 'CLOSE_STAGES', 'UNRUNNABLE_STAGES', 'RECOMPUTE_STATES', 'INSTALLED_STATES')
WEB, WORKER = install.SERVICES['web'], install.SERVICES['worker']
assert OFFICE_NOTE.startswith(BANNER) and REPORT.startswith(BANNER)


def installed_label(encounter):
    """What the installed revision 057a7d39's list and document view say for the stored state: its serializer serves
    review.state_label(encounter.state), and its STATE_LABELS are this revision's (byte-identical)."""
    return review.STATE_LABELS[encounter.state]


class Provider(TwoPassProvider):
    """The live adapter's name and version, each outcome scripted: 'refused' - an answer (HTTP 200) whose body is not a
    JSON object, which the adapter refuses whole; 'unknown' - sent, no answer recorded. A response names only the quotes
    the request's own text contains."""

    def send(self, request, *, deadline_s):
        if self.outcomes and self.outcomes[0] == 'refused':
            self.outcomes.pop(0)
            self.requests.append(request)
            data = b'[]'
            return RawExchange(outcome='succeeded', sent=True, http_status=200, response_bytes=data,
                               response_sha256=hashlib.sha256(data).hexdigest(), latency_ms=11.0,
                               usage={'creditsConsumed': 0.02}, usage_basis='provider_reported_credits_not_usd')
        if self.outcomes and self.outcomes[0] == 'failed':  # the provider answered HTTP 500
            self.outcomes.pop(0)
            self.requests.append(request)
            data = b'{"error":"synthetic internal server error"}'
            return RawExchange(outcome='failed', sent=True, http_status=500, response_bytes=data,
                               response_sha256=hashlib.sha256(data).hexdigest(),
                               error='HTTP 500 from the provider (synthetic).')
        first, later = self.first, self.later
        self.first = [q for q in first if q[1] in request.contexts[0]]
        self.later = [q for q in later if q[1] in request.contexts[0]]
        try:
            return super().send(request, deadline_s=deadline_s)
        finally:
            self.first, self.later = first, later


class RmFails(DockerWorld):
    """DockerWorld in which removing the container ``failing_id`` fails (a daemon error), or raises ``error``."""

    def __init__(self, failing_id, error=None, **kwargs):
        super().__init__(**kwargs)
        self.failing_id, self.error = failing_id, error

    def docker(self, *args, **kwargs):
        if args[:2] == ('rm', '--force') and args[2] == self.failing_id:
            self.record(*args)
            raise self.error or install.InstallError('docker rm failed (exit 1): the daemon did not answer')
        return super().docker(*args, **kwargs)


def scripts(world, older=None, fail=None, interrupt=None):
    """install.app_script for these tests: each in-image script runs here, on this database, as `manage shell -c` runs it
    in an image of this revision - except in the parked image (OLD_IMAGE) when ``older`` is 'installed': the installed
    revision 057a7d39 answers there, with its stage kinds (the common four) and its own derivation of a list state
    (review.refresh_state), which INSTALLED_STATES ports. ``fail`` names a script that fails (exit 1), ``interrupt`` one
    interrupted (Ctrl-C) as it starts. Each call is recorded in ``world.calls``."""
    def app_script(image_id, env_bytes, body, params, *, what, timeout=180):
        name = next((n for n in SCRIPTS if getattr(install, n, None) == body), 'other')
        world.record('script', image_id, name, tuple(params.get('encounters') or ()))
        if name == fail:
            raise install.InstallError(f'{what} failed (exit 1).')
        if name == interrupt:
            raise KeyboardInterrupt()
        if image_id == OLD_IMAGE and older == 'installed':
            if name == 'UNRUNNABLE_STAGES':
                return {'known': list(install.COMMON_STAGE_KINDS), 'stuck': 0, 'kinds': []}
            if name == 'RECOMPUTE_STATES':
                return run_app_script(install.INSTALLED_STATES, params)
        return run_app_script(body, params)
    return mock.patch.object(install, 'app_script', app_script)


@override_settings(**LIVE)
class Base(TestCase):
    def setUp(self):
        self.ws = f.workspace()
        self.reviewer = f.member(self.ws, f.user('reviewer'))
        self.client = Client(enforce_csrf_checks=False)
        self.client.force_login(self.reviewer)
        self.provider = Provider(first=[VISIT, SNARE], later=[VISIT, SNARE])
        patcher = mock.patch('studio.jobs.get_provider', return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def create(self, tag, text=OFFICE_NOTE, outcomes=(), **extra):
        self.provider.outcomes = list(outcomes)
        text = text.replace('(fictional)', f'(fictional) {tag}', 1)
        self.assertTrue(text.startswith(BANNER) and tag in text)
        with self.captureOnCommitCallbacks(execute=True):
            reply = self.client.post('/api/encounters', {'text': text, 'synthetic_attestation': 'yes', **extra})
        self.assertEqual(reply.status_code, 201, reply.content)
        drain()
        return reply.json()['id']

    def post(self, path, data=None):
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(path, data=json.dumps(data or {}), content_type='application/json')

    def encounter(self, encounter_id):
        return models.Encounter.objects.get(pk=encounter_id)

    def sent(self):
        return len(self.provider.requests)

    def listed(self, encounter_id):
        """(state, label) of the encounter's row in this revision's GET /api/encounters."""
        (row,) = [r for r in self.client.get('/api/encounters').json()['encounters'] if r['id'] == encounter_id]
        return row['state'], row['state_label']

    def refused(self, tag):
        """A response refused whole: its only request succeeded (HTTP 200), its answer was not a JSON object."""
        encounter_id = self.create(tag, outcomes=['refused'])
        (run,) = models.ProviderRun.objects.filter(encounter_id=encounter_id)
        self.assertEqual((run.state, run.http_status), (models.ProviderRun.SUCCEEDED, 200))
        self.assertEqual(self.listed(encounter_id), ('provider_failed', review.REFUSED_LABEL))
        return encounter_id

    def held(self, tag):
        """A member's service date that conflicts with the document's: a hold, nothing sent - a date question."""
        encounter_id = self.create(tag, service_date=MEMBER_CONFLICT)
        self.assertEqual(self.listed(encounter_id), ('needs_clarification', 'Needs clarification'))
        return encounter_id

    def closed_second_review(self, tag):
        """A second review a reviewer asked for, closed as failed by an undo before it ran (a kind 057a7d39 has no stage
        for): the latest stage of the encounter."""
        encounter_id = self.create(tag, text=REPORT)
        since = models.Job.objects.order_by('-created_at').first().created_at
        reply = self.post(f'/api/encounters/{encounter_id}/second-review')
        self.assertEqual(reply.status_code, 201, reply.content)
        closed = run_app_script(install.CLOSE_STAGES, {'since': since.isoformat(), 'note': 'Closed (synthetic).',
                                                        'kinds': list(install.COMMON_STAGE_KINDS)})
        self.assertEqual(closed['kinds'], ['review2'])
        self.assertEqual(review.latest_job(self.encounter(encounter_id)).state, models.Job.FAILED)
        return encounter_id

    # --- the undo phases, for real, over a Docker stand-in -------------------------------------------------------

    def rollback(self, parked=None, fail=None, fail_rm=None):
        """The REAL phase_rollback_app: this revision's pair runs (NEW_IMAGE); with ``parked`` an older pair's worker is
        parked (OLD_IMAGE) - 'installed': 057a7d39's, 'same': one of this revision; ``fail_rm`` names a container whose
        removal fails. Returns (answer or error, world)."""
        world = RmFails(fail_rm, previous=False) if fail_rm else DockerWorld(previous=False)
        world.live[WEB] = world.container('new-web', 'web', NEW_IMAGE, NEW_REVISION, '2026-10-27T12:30:00.7Z')
        world.live[WORKER] = world.container('new-worker', 'worker', NEW_IMAGE, NEW_REVISION, '2026-10-27T12:30:41.25Z')
        if parked:
            world.live[WORKER + '-previous'] = world.container('old-worker', 'worker', OLD_IMAGE, OLD_REVISION,
                                                                '2026-10-01T00:00:00Z')
        ctx = SimpleNamespace(revision=NEW_REVISION)
        with scripts(world, parked, fail), mock.patch.object(install, 'inspect', world.inspect), \
                mock.patch.object(install, 'docker', world.docker), \
                mock.patch.object(install, 'require_db', lambda: world.record('require_db')), \
                mock.patch.object(install, 'read_protected_env', return_value=b'ENV=2\n'), \
                mock.patch.object(install, 'oneshot', side_effect=AssertionError('no real container in a test')):
            try:
                return install.phase_rollback_app(ctx), world
            except install.InstallError as error:
                return error, world

    def fail_install(self, older, fail=None):
        """The REAL replace_services: the old pair (OLD_IMAGE - 057a7d39's when ``older`` is 'installed', one of this
        revision when 'same') is parked and the new pair started; the new worker never becomes ready, so the failure
        path closes what the new pair left open and restores the old pair. Returns (error, world)."""
        world = DockerWorld()
        for container in world.live.values():
            container['Image'] = OLD_IMAGE

        def wait(role, revision, image_id):
            if role == 'worker':
                raise install.InstallError('cpt-studio-worker did not become ready')
            return {'id': f'new-{role}'}
        ctx = SimpleNamespace(revision=NEW_REVISION, log=lambda label, data: None)
        with scripts(world, older, fail), mock.patch.object(install, 'inspect', world.inspect), \
                mock.patch.object(install, 'docker', world.docker), mock.patch.object(install, 'wait_service', wait), \
                mock.patch.object(install, 'oneshot', side_effect=AssertionError('no real container in a test')):
            with self.assertRaises(install.InstallError) as caught:
                install.replace_services(ctx, NEW_IMAGE, b'ENV=1\n', 'live', 'ruling.md')
        return caught.exception, world


class RefusedResponseHandedBackTests(Base):
    """install2:1. Before an undo hands the rows to an older revision - rollback-app, and the failure path of `app` - a
    stored state this revision labels from more than the state (a response refused whole: provider_failed, 'Provider
    response not used') is put back to the state the older revision derives for it, which it labels by the state alone:
    the parked image's own derivation when a pair is parked, else 057a7d39's. Every other stored state is one both
    revisions label alike and stays as this revision derived it: putting back 057a7d39's derivation there would list a
    held date question as 'Provider request failed' and a closed second review as 'Processing failed', both off its
    review queue (measured with its real code)."""

    def test_install2_1_rollback_app_puts_a_refused_response_back_to_the_installed_revisions_derivation(self):
        refused = self.refused('G1')  # made by this revision
        upgraded = self.refused('G1c')  # as 057a7d39 left it (no_codes), then rewritten by the upgrade's recompute
        models.Encounter.objects.filter(pk=upgraded).update(state='no_codes')
        self.assertEqual(run_app_script(install.RECOMPUTE_STATES, {})['changed'],
                         {upgraded: ['no_codes', 'provider_failed']})
        held, plain = self.held('H'), self.create('C')
        untouched = {pk: self.encounter(pk).updated_at for pk in (held, plain)}
        sent = self.sent()
        result, world = self.rollback()
        for pk in (refused, upgraded):
            self.assertEqual(self.encounter(pk).state, 'no_codes')
            self.assertEqual(installed_label(self.encounter(pk)), 'No CPT codes proposed')  # never 'Provider request failed'
        self.assertIsInstance(result, dict, result)
        self.assertEqual(result['states_put_back']['changed'], {refused: ['provider_failed', 'no_codes'],
                                                                upgraded: ['provider_failed', 'no_codes']})
        self.assertEqual(world.ids(), {})  # the pair was removed, after the put-back
        put_back = world.index('script', NEW_IMAGE, 'INSTALLED_STATES')
        self.assertEqual(sorted(world.calls[put_back][3]), sorted((refused, upgraded)))
        self.assertLess(world.index('script', NEW_IMAGE, 'CLOSE_STAGES'), put_back)
        self.assertLess(put_back, world.index('rm', '--force', 'new-worker'))
        # controls: a held date question keeps the state this revision derived (and labels as 057a7d39 does); nothing
        # else is written, and nothing is sent
        self.assertEqual(installed_label(self.encounter(held)), 'Needs clarification')
        self.assertEqual({pk: self.encounter(pk).updated_at for pk in untouched}, untouched)
        self.assertEqual(self.sent(), sent)

    def test_install2_1_with_a_pair_parked_its_own_image_derives_the_state_put_back(self):
        refused = self.refused('G1')
        result, world = self.rollback(parked='installed')
        self.assertEqual(self.encounter(refused).state, 'no_codes')
        self.assertEqual(world.calls[world.index('script', OLD_IMAGE, 'RECOMPUTE_STATES')][3], (refused,))
        self.assertFalse([call for call in world.calls if call[:3] == ('script', NEW_IMAGE, 'INSTALLED_STATES')])
        self.assertEqual(result['states_put_back']['changed'], {refused: ['provider_failed', 'no_codes']})
        # control: a parked pair of this same revision derives it as this revision does - nothing is put back
        run_app_script(install.RECOMPUTE_STATES, {})
        result, world = self.rollback(parked='same')
        self.assertEqual(self.listed(refused), ('provider_failed', review.REFUSED_LABEL))
        self.assertEqual(world.calls[world.index('script', OLD_IMAGE, 'RECOMPUTE_STATES')][3], (refused,))
        self.assertEqual(result['states_put_back']['changed'], {})

    def test_install2_1_the_failure_path_puts_them_back_before_the_parked_pair_is_restored(self):
        refused, held = self.refused('G1'), self.held('H')
        error, world = self.fail_install('installed')
        self.assertIn('cpt-studio-worker did not become ready', str(error))
        self.assertEqual(self.encounter(refused).state, 'no_codes')
        self.assertEqual(installed_label(self.encounter(refused)), 'No CPT codes proposed')
        put_back = world.index('script', OLD_IMAGE, 'RECOMPUTE_STATES')
        self.assertEqual(world.calls[put_back][3], (refused,))
        self.assertLess(world.index('script', NEW_IMAGE, 'CLOSE_STAGES'), put_back)
        self.assertLess(put_back, world.index('rename', WORKER + '-previous', WORKER))
        self.assertLess(put_back, world.index('start', WEB))
        self.assertEqual(world.ids(), {WEB: 'old-web', WORKER: 'old-worker'})
        self.assertEqual(self.encounter(held).state, 'needs_clarification')
        # control: a same-revision re-run's parked pair derives the state as this revision does
        run_app_script(install.RECOMPUTE_STATES, {})
        error, world = self.fail_install('same')
        self.assertEqual(self.listed(refused), ('provider_failed', review.REFUSED_LABEL))
        self.assertEqual(world.calls[world.index('script', OLD_IMAGE, 'RECOMPUTE_STATES')][3], (refused,))

    def test_a_put_back_that_cannot_be_made_hands_nothing_over(self):
        refused = self.refused('G1')
        error, world = self.rollback(fail='INSTALLED_STATES')
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('stopped, not removed', str(error))
        self.assertIn('Rerun --phase rollback-app', str(error))
        self.assertFalse([call for call in world.calls if call[0] == 'rm'])
        self.assertEqual(self.encounter(refused).state, 'provider_failed')
        # the failure path: the new pair is left stopped and the old one parked, for rollback-app
        error, world = self.fail_install('installed', fail='RECOMPUTE_STATES')
        self.assertIn('could not then be put back', str(error))
        self.assertIn('--phase rollback-app', str(error))
        self.assertFalse([call for call in world.calls if call[0] in ('start', 'rm')])
        self.assertEqual(world.ids(), {WEB + '-previous': 'old-web', WORKER + '-previous': 'old-worker',
                                       WEB: 'new-web', WORKER: 'new-worker'})

    def test_the_close_names_only_the_states_this_revision_labels_from_more_than_the_state(self):
        refused, held, plain = self.refused('G1'), self.held('H'), self.create('C')
        failed = self.create('F', outcomes=['failed'])  # a request that failed: 'Provider request failed' in both
        self.assertEqual(self.listed(failed), ('provider_failed', 'Provider request failed'))
        review2 = self.closed_second_review('R')
        closed = run_app_script(install.CLOSE_STAGES, {'since': models.Job.objects.order_by('-created_at').first()
                                                       .created_at.isoformat(), 'note': 'Closed (synthetic).',
                                                       'kinds': list(install.COMMON_STAGE_KINDS)})
        self.assertEqual(closed['relabel'], [refused])
        for pk in (held, plain, failed, review2):
            encounter = self.encounter(pk)
            self.assertEqual(review.encounter_state_label(encounter), review.state_label(encounter.state))

    def test_a_removal_that_fails_after_a_put_back_says_the_states_were_put_back(self):
        refused = self.refused('G1')
        error, world = self.rollback(fail_rm='new-worker')
        self.assertIsInstance(error, install.InstallError)
        self.assertEqual(self.encounter(refused).state, 'no_codes')
        message = str(error)
        self.assertIn('docker rm failed', message)
        self.assertIn('the list states of 1 encounter(s) were put back', message)
        self.assertIn('rerun --phase rollback-app', message)
        self.assertIn('rerun --phase app', message)
        self.assertEqual(error.details['states_put_back']['changed'], {refused: ['provider_failed', 'no_codes']})
        # control: with nothing to put back (the state is already the older derivation, labelled alike by both) the
        # removal's own failure is what is raised
        error, world = self.rollback(fail_rm='new-worker')
        self.assertFalse([call for call in world.calls if call[:3] == ('script', NEW_IMAGE, 'INSTALLED_STATES')])
        self.assertIsInstance(error, install.InstallError)
        self.assertEqual(str(error), 'docker rm failed (exit 1): the daemon did not answer')

    def test_a_state_on_the_review_queue_is_never_put_back_whatever_its_label(self):
        # A label worded from the run for a state on the review queue (none is today) never makes it a candidate:
        # 057a7d39's own derivation of a hold is a request that failed, which would take it off its review queue.
        held, refused = self.held('H'), self.refused('G1')
        worded = review.encounter_state_label
        since = models.Job.objects.order_by('-created_at').first().created_at.isoformat()
        with mock.patch.object(review, 'encounter_state_label',
                               side_effect=lambda encounter: f'{worded(encounter)} (worded from its run)'):
            closed = run_app_script(install.CLOSE_STAGES, {'since': since, 'note': 'Closed (synthetic).',
                                                           'kinds': list(install.COMMON_STAGE_KINDS)})
        self.assertEqual(closed['relabel'], [refused])
        self.assertEqual(self.encounter(held).state, 'needs_clarification')

    def test_installed_states_is_the_installed_revisions_derivation(self):
        # The values 057a7d398's own review._derive_state gives for these rows (the cross-revision probe's matrix): a
        # response refused whole is no_codes there, a hold a request that failed, a closed second review a failed stage.
        refused, held, plain = self.refused('G1'), self.held('H'), self.create('C')
        review2 = self.closed_second_review('R')
        expected = {refused: 'no_codes', held: 'provider_failed', plain: self.encounter(plain).state,
                    review2: 'processing_failed'}  # an ordinary encounter: both revisions derive it alike
        answer = run_app_script(install.INSTALLED_STATES, {'encounters': list(expected)})
        self.assertEqual({pk: self.encounter(pk).state for pk in expected}, expected)
        self.assertEqual(answer['encounters'], 4)
        self.assertEqual(set(answer['changed']), {refused, held, review2})

    def test_controls_a_copy_of_the_live_installation_has_nothing_to_put_back(self):
        # 2026-10-27 16:23Z: 11 encounters, 11 provider runs, all succeeded and sent, no stage active, none unknown
        for number in range(11):
            self.create(f'L{number}')
        runs = models.ProviderRun.objects.all()
        self.assertEqual((runs.count(), runs.filter(state=models.ProviderRun.SUCCEEDED, sent=True).count()), (11, 11))
        stored = {e.pk: (e.state, e.updated_at) for e in models.Encounter.objects.all()}
        for parked in (None, 'installed'):
            with self.subTest(parked=parked):
                result, world = self.rollback(parked=parked)
                self.assertIsInstance(result, dict, result)
                self.assertEqual(result['states_put_back'], {'encounters': 0, 'changed': {}})
                self.assertFalse([call for call in world.calls if call[0] == 'script'
                                  and call[2] in ('RECOMPUTE_STATES', 'INSTALLED_STATES')])
                self.assertEqual({e.pk: (e.state, e.updated_at) for e in models.Encounter.objects.all()}, stored)
        error, world = self.fail_install('installed')
        self.assertFalse([call for call in world.calls if call[0] == 'script'
                          and call[2] in ('RECOMPUTE_STATES', 'INSTALLED_STATES')])
        self.assertEqual({e.pk: (e.state, e.updated_at) for e in models.Encounter.objects.all()}, stored)


# --- install2:2: the app phase recomputes before it removes the parked pair, and says what it left -------------------

def app_phase(world, app_script):
    """The REAL phase_app and replace_services (provider disabled): Docker is ``world``, every service ready at once,
    ``app_script`` answering the in-image scripts. Returns the details, or what it raised (an interrupt included)."""
    ctx = SimpleNamespace(revision=NEW_REVISION, log=lambda label, data: 'log',
                          args=SimpleNamespace(provider_mode='disabled', authorization_ref=''))
    with mock.patch.object(install, 'installed_image', return_value=NEW_IMAGE), \
            mock.patch.object(install, 'require_db'), \
            mock.patch.object(install, 'read_protected_env', return_value=b''), \
            mock.patch.object(install, 'oneshot', return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')), \
            mock.patch.object(install, 'app_script', app_script), \
            mock.patch.object(install, 'inspect', world.inspect), mock.patch.object(install, 'docker', world.docker), \
            mock.patch.object(install, 'wait_service', lambda role, revision, image_id: {'id': f'new-{role}'}):
        try:
            return install.phase_app(ctx)
        except BaseException as error:  # noqa: BLE001 — a Ctrl-C that escapes the phase is what is being tested
            return error


def answering(world, recompute):
    """In-image answers for app_phase: the queue holds nothing this revision cannot run; RECOMPUTE_STATES answers
    ``recompute`` (or raises it). Each call is recorded in ``world.calls``."""
    def app_script(image_id, env_bytes, body, params, **kwargs):
        if body == install.UNRUNNABLE_STAGES:
            return {'known': ['analyze', 'assess', 'extract', 'predict', 'review2'], 'stuck': 0, 'kinds': []}
        if body == install.RECOMPUTE_STATES:
            world.record('recompute', image_id)
            if isinstance(recompute, BaseException):
                raise recompute
            return recompute
        raise AssertionError('an unexpected in-image script')
    return app_script


class AppPhaseRecomputesBeforeRemovingTheParkedPairTests(SimpleTestCase):
    """install2:2: the stored list states are recomputed once the new pair runs and BEFORE the parked pair is removed,
    so a removal that fails (the documented '*-previous' case) leaves them recomputed; whatever stops the phase once
    the new pair runs - the recompute, the removal, a Ctrl-C - is a receipt that says whether they were, and what is
    left to do."""
    CHANGED = {'encounters': 2, 'changed': {'e1': ['no_codes', 'provider_failed']}}

    def test_install2_2_the_parked_pair_is_removed_only_after_the_recompute(self):
        world = DockerWorld()
        details = app_phase(world, answering(world, self.CHANGED))
        self.assertIsInstance(details, dict, details)
        recompute = world.index('recompute')
        self.assertLess(recompute, world.index('rm', '--force', 'old-worker'))
        self.assertLess(recompute, world.index('rm', '--force', 'old-web'))
        self.assertEqual(world.ids(), {WEB: 'new-web', WORKER: 'new-worker'})
        self.assertEqual(details['states_recomputed'], self.CHANGED)

    def test_install2_2_a_removal_that_fails_after_the_recompute_says_they_were_recomputed(self):
        for failure in (install.InstallError('docker rm failed (exit 1)'), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                world = RmFails('old-worker', failure)
                error = app_phase(world, answering(world, self.CHANGED))
                self.assertIsInstance(error, install.InstallError)
                self.assertLess(world.index('recompute'), world.index('rm', '--force', 'old-worker'))
                message = str(error)
                self.assertIn('web and worker running', message)
                self.assertIn('the stored list states were recomputed (1 changed)', message)
                self.assertIn('could not be removed', message)
                self.assertIn('*-previous', message)
                self.assertNotIn('not recomputed', message)
                self.assertEqual(error.details['states_recomputed'], self.CHANGED)

    def test_install2_2_a_recompute_that_fails_or_is_interrupted_says_so_and_leaves_the_parked_pair(self):
        for failure in (install.InstallError('Recomputing the stored list states failed (exit 1).'),
                        KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                world = DockerWorld()
                error = app_phase(world, answering(world, failure))
                self.assertIsInstance(error, install.InstallError)
                message = str(error)
                self.assertIn('web and worker running', message)
                self.assertIn('the stored list states were not recomputed', message)
                self.assertIn('rerun --phase app', message)
                self.assertIn('*-previous', message)
                self.assertFalse([call for call in world.calls if call[0] == 'rm' and call[2].startswith('old-')])
                self.assertEqual(world.ids(), {WEB + '-previous': 'old-web', WORKER + '-previous': 'old-worker',
                                               WEB: 'new-web', WORKER: 'new-worker'})
                self.assertIsNone(error.details['states_recomputed'])

    def test_install2_2_the_receipt_of_an_interrupted_app_says_the_states_were_not_recomputed(self):
        world = DockerWorld()
        output = io.StringIO()
        umask = os.umask(0o077)  # main() sets 0o077 for its process; restored below for the rest of this suite
        os.umask(umask)
        with tempfile.TemporaryDirectory() as tmp:
            receipts = Path(tmp) / 'receipts'
            with mock.patch.object(install, 'check_door', return_value={'declaration_commit': OLD_REVISION}), \
                    mock.patch.object(install, 'check_tree', return_value={'mode': 'exact'}), \
                    mock.patch.object(install, 'installed_image', return_value=NEW_IMAGE), \
                    mock.patch.object(install, 'require_db'), \
                    mock.patch.object(install, 'read_protected_env', return_value=b''), \
                    mock.patch.object(install, 'oneshot',
                                      return_value=SimpleNamespace(returncode=0, stdout=b'', stderr=b'')), \
                    mock.patch.object(install, 'app_script', answering(world, KeyboardInterrupt())), \
                    mock.patch.object(install, 'inspect', world.inspect), \
                    mock.patch.object(install, 'docker', world.docker), \
                    mock.patch.object(install, 'wait_service', lambda role, revision, image_id: {'id': f'new-{role}'}), \
                    mock.patch('sys.stdout', output):
                try:
                    code = install.main(['--phase', 'app', '--revision', NEW_REVISION, '--receipts', str(receipts),
                                         '--provider-mode', 'disabled'])
                except KeyboardInterrupt:  # what main() let through before: the receipt then said nothing
                    code = 'interrupted'
                finally:
                    os.umask(umask)
            self.assertEqual(code, 1)
            record = json.loads(Path(json.loads(output.getvalue().splitlines()[-1])['receipt']).read_text())
        self.assertFalse(record['ok'])
        self.assertIn('the stored list states were not recomputed (KeyboardInterrupt)', record['error'])
        self.assertIn('rerun --phase app', record['error'])
        self.assertIsNone(record['details']['states_recomputed'])


class InterruptedAppRecoveryTests(Base):
    """install2:2 on real rows: the states the replaced revision derived, through this revision's web, before and after
    an `app` stopped once its new pair ran, and after the recovery ops/INSTALL.md documents."""

    def app(self, world, interrupt=False):
        """The REAL phase_app and replace_services over ``world``, every in-image script run here on this database;
        with ``interrupt`` the recompute is interrupted (Ctrl-C) as it starts."""
        def app_script(image_id, env_bytes, body, params, **kwargs):
            if interrupt and body == install.RECOMPUTE_STATES:
                raise KeyboardInterrupt()
            return run_app_script(body, params)
        return app_phase(world, app_script)

    def replaced(self):
        """Rows as the replaced revision 057a7d39 left them: I1 a response refused whole (it lists 'No CPT codes
        proposed'); I2 the migrate-2 shape - an answer ready for review beside a request whose outcome is unknown and
        unreconciled (there: a date change that came back unknown, the first answer reused; here the run is written as
        that leaves it, so the shape does not depend on how a date is read) - which it lists 'Ready for review'."""
        i1 = self.refused('I1')
        i2 = self.create('I2')
        encounter = self.encounter(i2)
        models.ProviderRun.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider='corti', adapter_version='test',
            request_sha256='e' * 64, request_body={}, contexts=[], state=models.ProviderRun.UNKNOWN,
            requested_by=self.reviewer)
        self.assertEqual(review._derive_state(self.encounter(i2)), 'provider_unknown')
        models.Encounter.objects.filter(pk=i1).update(state='no_codes')
        models.Encounter.objects.filter(pk=i2).update(state='ready_for_review')
        self.assertEqual((self.listed(i1), self.listed(i2)),
                         (('no_codes', 'No CPT codes proposed'), ('ready_for_review', 'Ready for review')))
        return i1, i2

    def running_new_pair(self):
        """A world in which this revision's pair runs and nothing is parked (the recovery's starting point)."""
        world = DockerWorld(previous=False)
        world.live[WEB] = world.container('cur-web', 'web', NEW_IMAGE, NEW_REVISION, '2026-10-27T12:30:00.7Z')
        world.live[WORKER] = world.container('cur-worker', 'worker', NEW_IMAGE, NEW_REVISION, '2026-10-27T12:30:41.25Z')
        return world

    def test_install2_2_a_failed_removal_of_the_parked_pair_leaves_the_states_recomputed(self):
        i1, i2 = self.replaced()
        sent = self.sent()
        world = RmFails('old-worker')
        error = self.app(world)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('the stored list states were recomputed (2 changed)', str(error))
        self.assertEqual(self.listed(i1), ('provider_failed', review.REFUSED_LABEL))
        self.assertEqual(self.listed(i2), ('provider_unknown', 'Provider outcome unknown'))
        # the documented recovery: remove the parked pair by hand; a rerun of app finds nothing left to change
        world.live.pop(WORKER + '-previous')
        world = self.running_new_pair()
        details = self.app(world)
        self.assertIsInstance(details, dict, details)
        self.assertEqual(details['states_recomputed']['changed'], {})
        self.assertEqual(self.sent(), sent)

    def test_install2_2_an_interrupted_recompute_says_so_and_the_documented_recovery_recomputes_them(self):
        i1, i2 = self.replaced()
        sent = self.sent()
        world = DockerWorld()
        error = self.app(world, interrupt=True)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('the stored list states were not recomputed', str(error))
        self.assertEqual(self.listed(i1), ('no_codes', 'No CPT codes proposed'))  # as the replaced revision left it
        # the recovery the receipt and ops/INSTALL.md name: remove the parked pair by hand, then rerun app
        self.assertIn(WORKER + '-previous', world.ids())
        world = self.running_new_pair()
        details = self.app(world)
        self.assertIsInstance(details, dict, details)
        self.assertEqual(details['states_recomputed']['changed'], {i1: ['no_codes', 'provider_failed'],
                                                                   i2: ['ready_for_review', 'provider_unknown']})
        self.assertEqual(self.listed(i1), ('provider_failed', review.REFUSED_LABEL))
        self.assertEqual(self.listed(i2), ('provider_unknown', 'Provider outcome unknown'))
        self.assertEqual(self.sent(), sent)
