"""Release 1's integrated refutation, round 1: the installer's repairs (repair builder I). Offline, under test_install's
host guard; the in-image scripts run on the disposable test database (test_install_harness2's DatabaseTest: skipped,
never passed, without one). Synthetic data only.

  I1  rollback-0, rollback-3: every session is ended when the site moves between a revision before release 1's session
      policy and one with it (the blue/green switch at S2, the swap once the old pair is stopped, the switch-back at
      B4), in this revision's image, with one SecurityEvent; never between two revisions that both have it.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1_repair -v
"""
import datetime as dt
import io
import json
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_install  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host  # noqa: E402
from test_install_bluegreen import (ACTS, IMAGE, KINDS_OLD, NEXT, OLD, OLD_IMAGE, REVISION, WEB, WORKER,  # noqa: E402
                                    BlueGreenWorld, run_app, switch_back_args)
from test_install_harness2 import DatabaseTest, run_in_image  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
# the revision live before release 1 (R0, 2026-11-23): its tree has no studio/sessions.py
R0_REVISION = '36e550ab7301c28d8a453e82674c78c46ff41c27'
EVENT_ID = '0f8fad5b-d9cb-469f-a165-70867728950e'
SESSION_ACTS = ACTS + ('end_sessions',)


def setUpModule():
    guard_host()


def tearDownModule():
    try:
        harness2 = sys.modules.get('test_install_harness2')
        if harness2 is not None and 'connection' in harness2._DATABASE:  # this module's database tests made it
            connection = harness2._DATABASE.pop('connection')
            connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)
    finally:
        release_host()


# --- I1: the sessions at a switch between revisions that do not share release 1's session policy ---------------------

class SessionPolicyReadTests(unittest.TestCase):
    def test_the_policy_is_read_from_the_revisions_tree_and_an_unreadable_revision_is_refused(self):
        real, seen = test_install.REAL_HAS_SESSION_POLICY, []

        def git(answer_commit, answer_file):
            def fake_run(argv, **kwargs):
                seen.append(argv[-1])
                code = answer_commit if argv[-1].endswith('^{commit}') else answer_file
                return SimpleNamespace(returncode=code, stdout=b'', stderr=b'')
            return fake_run
        with mock.patch.object(install, 'run', git(0, 0)):
            self.assertIs(real(REVISION), True)
        self.assertEqual(seen[-1], f'{REVISION}:cpt-studio/studio/sessions.py')
        with mock.patch.object(install, 'run', git(0, 128)):
            self.assertIs(real(REVISION), False)
        with mock.patch.object(install, 'run', git(128, 0)), self.assertRaisesRegex(install.InstallError, 'cannot read'):
            real(REVISION)
        for value in ('abc', None, 'A' * 40):
            with self.subTest(value=value), self.assertRaisesRegex(install.InstallError, '40-character'):
                real(value)

    def test_on_this_tree_release_1_has_it_and_the_revision_before_it_does_not(self):
        real = test_install.REAL_HAS_SESSION_POLICY
        head = install.run(['git', '-C', str(REPO_ROOT), 'rev-parse', 'HEAD']).stdout.decode().strip()
        self.assertIs(real(head), True)
        known = install.run(['git', '-C', str(REPO_ROOT), 'cat-file', '-e', f'{R0_REVISION}^{{commit}}'], check=False)
        if known.returncode:
            raise unittest.SkipTest(f'{R0_REVISION[:12]} is not in this clone')
        self.assertIs(real(R0_REVISION), False)

    def test_a_session_end_is_needed_exactly_when_one_of_the_two_has_the_policy(self):
        with mock.patch.object(test_install, 'PRE_SESSION_POLICY_REVISIONS', {OLD}):
            self.assertTrue(install.sessions_end_needed(OLD, REVISION))   # the switch forward from R0
            self.assertTrue(install.sessions_end_needed(REVISION, OLD))   # the switch-back to it
            self.assertFalse(install.sessions_end_needed(REVISION, REVISION))
            self.assertFalse(install.sessions_end_needed('c' * 40, REVISION))  # a later release over release 1


class EndEverySessionOnTheDatabaseTests(DatabaseTest):
    """END_EVERY_SESSION on real rows: the input of rollback-0 - Bob's release-1 session (its keys) left in a shared
    browser across a switch-back, beside Carol's session of the older revision (none of them) - is ended whole, and one
    SecurityEvent says how many, in the same transaction."""

    def sessions(self):
        from importlib import import_module
        from django.conf import settings
        from studio import models, request_meta
        store = import_module(settings.SESSION_ENGINE).SessionStore
        bob = models.User.objects.create(username=f'synthetic-bob-{uuid.uuid4().hex[:8]}')
        carol = models.User.objects.create(username=f'synthetic-carol-{uuid.uuid4().hex[:8]}')
        now = request_meta.epoch_seconds()
        release1 = store()
        release1.update({'_auth_user_id': str(bob.pk), request_meta.SESSION_DOOR: request_meta.CPT,
                         request_meta.SESSION_AUTH_AT: now, request_meta.SESSION_LAST_ACTIVE: now,
                         request_meta.SESSION_SIGN_IN_REF: str(uuid.uuid4())})
        release1.save()
        older = store()
        older['_auth_user_id'] = str(carol.pk)  # a session of a revision before release 1: no keys of release 1
        older.save()
        anonymous = store()
        anonymous['synthetic'] = 1
        anonymous.save()
        return store, [release1.session_key, older.session_key, anonymous.session_key]

    def params(self):
        return {'event': install.SESSIONS_ENDED_EVENT, 'actor_label': install.SESSIONS_ENDED_ACTOR,
                'from_revision': OLD, 'to_revision': REVISION}

    def test_every_session_is_ended_with_one_event_that_holds_a_count_and_the_two_revisions(self):
        from django.contrib.sessions.models import Session
        from studio import models
        store, keys = self.sessions()
        before = Session.objects.count()
        self.assertGreaterEqual(before, 3)
        answer = run_in_image(install.END_EVERY_SESSION, self.params())
        self.assertEqual(answer['ended'], before)
        self.assertEqual(Session.objects.count(), 0)
        for key in keys:
            self.assertFalse(store().exists(key))
            self.assertEqual(store(session_key=key).load(), {})  # the cookie signs nobody in
        (event,) = models.SecurityEvent.objects.filter(event=install.SESSIONS_ENDED_EVENT)
        self.assertEqual(str(event.pk), answer['event'])
        self.assertEqual(event.actor_label, install.SESSIONS_ENDED_ACTOR)
        self.assertEqual(event.data, {'count': before, 'from_revision': OLD, 'to_revision': REVISION})
        self.assertIsNone(event.actor_id)
        self.assertIsNone(event.workspace_id)

    def test_nothing_is_ended_when_its_event_cannot_be_written(self):
        from django.contrib.sessions.models import Session
        from studio import models, security_events
        self.sessions()
        before = Session.objects.count()
        with mock.patch.object(security_events, 'record', side_effect=RuntimeError('synthetic: no record')), \
                self.assertRaisesRegex(RuntimeError, 'no record'):
            run_in_image(install.END_EVERY_SESSION, self.params())
        self.assertEqual(Session.objects.count(), before)
        self.assertFalse(models.SecurityEvent.objects.filter(event=install.SESSIONS_ENDED_EVENT).exists())

    def test_the_event_and_its_actor_label_are_what_security_events_accepts(self):
        from studio import security_events
        self.assertTrue(security_events.EVENT_RE.fullmatch(install.SESSIONS_ENDED_EVENT))
        self.assertLessEqual(len(install.SESSIONS_ENDED_EVENT), security_events.EVENT_CHARS)
        self.assertLessEqual(len(install.SESSIONS_ENDED_ACTOR), security_events.LABEL_CHARS)


class SessionWorld(BlueGreenWorld):
    """BlueGreenWorld whose serving revision OLD is before release 1's session policy (REVISION has it), and whose
    in-image END_EVERY_SESSION is answered (``session_answer``: an exception raises)."""

    def __init__(self, tmp, *, ended=3, pre_policy=(OLD,), **kwargs):
        super().__init__(tmp, **kwargs)
        self.session_answer = {'ended': ended, 'event': EVENT_ID}
        self.session_ends = []
        self.pre_policy = set(pre_policy)

    def app_script(self, image_id, env_bytes, body, params, **kwargs):
        if body == install.END_EVERY_SESSION:
            self.act('end_sessions', image_id, params['from_revision'], params['to_revision'])
            self.session_ends.append(dict(params))
            if isinstance(self.session_answer, BaseException):
                raise self.session_answer
            return self.done(dict(self.session_answer))
        return super().app_script(image_id, env_bytes, body, params, **kwargs)

    def patches(self):
        return super().patches() + [mock.patch.object(test_install, 'PRE_SESSION_POLICY_REVISIONS', self.pre_policy)]


class SwitchForwardSessionTests(TemporaryDirectoryTest):
    def failed(self, world):
        details, error = run_app(world)
        self.assertIsNone(details, 'the phase passed')
        self.assertIsInstance(error, install.InstallError)
        world.invariant()
        return str(error), error.details or {}

    def test_from_a_revision_before_the_policy_every_session_is_ended_after_s2_and_before_s3(self):
        world = SessionWorld(self.tmp)
        details, error = run_app(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.acts(*SESSION_ACTS), [
            ('recorder', 'start'),
            ('run', 'web', NEXT, 9151, IMAGE), ('wait', 'web', NEXT, 9151), ('smoke', 9151),          # S1
            ('stop', WORKER, '3600'), ('rename', WORKER, WORKER + '-previous'),                           # S2
            ('end_sessions', IMAGE, OLD, REVISION),                                                       # S2: sessions
            ('vhost', 'replace', 9151), ('reload', 9151), ('https', 9151, REVISION),                     # S3
            ('run', 'worker', WORKER, None, IMAGE), ('wait', 'worker', WORKER, None),                    # S4
            ('drain', 9150), ('stop', WEB, '30'), ('rename', WEB, WEB + '-previous'), ('rename', NEXT, WEB),  # S5
            ('recorder', 'stop'),
            ('recompute', IMAGE, 'all'), ('rm', WORKER + '-previous'), ('rm', WEB + '-previous')])     # S6
        (params,) = world.session_ends
        self.assertEqual(params, {'event': install.SESSIONS_ENDED_EVENT, 'actor_label': install.SESSIONS_ENDED_ACTOR,
                                  'from_revision': OLD, 'to_revision': REVISION})
        ended = details['sessions_ended']
        self.assertEqual((ended['ended'], ended['event'], ended['from_revision'], ended['to_revision']),
                         (3, EVENT_ID, OLD, REVISION))
        self.assertTrue(ended['started_at'])
        self.assertIn('every session ended (3', details['summary'])
        self.assertEqual(sorted(details['steps']), ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'done'])

    def test_between_two_revisions_that_have_the_policy_no_session_is_ended(self):
        world = SessionWorld(self.tmp, pre_policy=())  # a later release over release 1
        details, error = run_app(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.acts('end_sessions'), [])
        self.assertNotIn('sessions_ended', details)
        self.assertNotIn('every session ended', details['summary'])

    def test_a_serving_revision_whose_policy_cannot_be_read_refuses_before_anything_starts(self):
        world = SessionWorld(self.tmp)
        refusal = install.InstallError(f'Cannot tell whether {OLD[:12]} has release 1\'s session policy: this checkout '
                                       'cannot read that revision.')
        patches = world.patches() + [mock.patch.object(install, 'has_session_policy', side_effect=refusal)]
        for patcher in patches:
            patcher.start()
        try:
            with self.assertRaises(install.InstallError) as caught:
                install.phase_app(install.Context(SimpleNamespace(
                    phase='app', revision=REVISION, receipts=str(self.tmp), coding_mode='disabled',
                    authorization_ref=''), self.tmp))
        finally:
            for patcher in reversed(patches):
                patcher.stop()
        self.assertIn('nothing was started or stopped', str(caught.exception))
        self.assertIn('cannot read', str(caught.exception))
        self.assertEqual(world.acts('run', 'stop', 'rename', 'vhost', 'end_sessions'), [])

    def test_an_end_that_fails_is_undone_as_at_s2_and_says_it_may_have_ended_them(self):
        for label, failure in (('refused', install.InstallError('Ending every session failed (exit 1).')),
                               ('no answer', {'ended': 'three', 'event': EVENT_ID}),
                               ('no event', {'ended': 3})):
            with self.subTest(label):
                world = SessionWorld(self.tmp)
                world.session_answer = failure
                message, details = self.failed(world)
                self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
                self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
                self.assertEqual(details['failed_at'], 'S2')
                self.assertEqual(world.acts('vhost', 'reload'), [])  # nothing switched
                self.assertIn(('start', WORKER), world.events)  # the old worker runs again
                self.assertNotIn(NEXT, world.containers)
                self.assertIn('nothing else changed but the sessions', message)
                self.assertIn('it may have ended every session', message)
                self.assertTrue(details['sessions_ended']['started_at'])
                self.assertNotIn('ended', details['sessions_ended'])

    def test_a_failure_after_the_end_says_every_session_was_ended(self):
        world = SessionWorld(self.tmp)
        world.fail[('https', 9151)] = install.InstallError('https://cpt.quillmd.com/health/ did not serve it')
        message, details = self.failed(world)
        self.assertEqual(details['failed_at'], 'S3')
        self.assertIn('Every session was ended (3; SecurityEvent sessions.ended_at_install)', message)
        self.assertEqual(details['sessions_ended']['ended'], 3)

    def test_an_interrupt_at_any_call_leaves_a_served_site_and_says_what_is_left(self):
        clean = SessionWorld(self.tmp)
        self.assertIsNone(run_app(clean)[1])
        total = clean.calls
        at = clean.events.index(('end_sessions', IMAGE, OLD, REVISION)) + 1
        outcomes = {'refused before acting': 0, 'undone or reported': 0, 'installed': 0}
        for k in range(1, total + 1):
            for path in list(self.tmp.glob('*.json')) + list(self.tmp.glob('*.log')):
                path.unlink()
            world = SessionWorld(self.tmp)
            world.interrupt_at = k
            with self.subTest(call=k):
                try:
                    details, error = run_app(world)
                except KeyboardInterrupt:
                    self.assertFalse([event for event in world.events if event[0] == 'run'], world.events[-3:])
                    outcomes['refused before acting'] += 1
                    world.invariant()
                    continue
                world.invariant()
                if error is None:
                    outcomes['installed'] += 1
                    continue
                outcomes['undone or reported'] += 1
                if k >= at:  # the end was started: the receipt's message says so
                    self.assertIn('every session', str(error).lower(), str(error))
        self.assertEqual(outcomes['installed'], 0)
        self.assertGreater(outcomes['undone or reported'], 20)


class SwapSessionTests(TemporaryDirectoryTest):
    def world(self):
        world = SessionWorld(self.tmp)
        world.checking = False  # nothing is served through the vhost: the swap
        world.containers[WEB]['running'] = False  # the HTTPS stage, no running web
        return world

    def test_the_swap_of_a_pair_before_the_policy_ends_every_session_once_both_are_stopped(self):
        world = self.world()
        details, error = run_app(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['replacement']['mode'], 'fresh')
        acts = world.acts('stop', 'rename', 'end_sessions', 'run')
        self.assertEqual(acts[:5], [('stop', WORKER, '3600'), ('rename', WORKER, WORKER + '-previous'),
                                    ('stop', WEB, '30'), ('rename', WEB, WEB + '-previous'),
                                    ('end_sessions', IMAGE, OLD, REVISION)])
        self.assertEqual(acts[5][:2], ('run', 'web'))
        self.assertEqual(details['sessions_ended']['ended'], 3)
        self.assertIn('every session ended (3', details['summary'])

    def test_an_end_that_fails_restores_the_old_pair_and_says_it_may_have_ended_them(self):
        world = self.world()
        world.session_answer = install.InstallError('Ending every session failed (exit 1).')
        details, error = run_app(world)
        self.assertIsInstance(error, install.InstallError)
        self.assertEqual(world.acts('run'), [])  # nothing new was started
        self.assertEqual({name: c['Image'] for name, c in world.containers.items()},
                         {WEB: OLD_IMAGE, WORKER: OLD_IMAGE})
        self.assertIn('the previous pair was restored', str(error))
        self.assertIn('it may have ended every session', str(error))
        self.assertTrue(error.details['sessions_ended']['started_at'])

    def test_a_later_release_swaps_with_no_session_ended(self):
        world = self.world()
        world.pre_policy = set()
        details, error = run_app(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.acts('end_sessions'), [])
        self.assertNotIn('sessions_ended', details)


class SwitchBackSessionTests(TemporaryDirectoryTest):
    def world(self, *, pre_policy=(OLD,)):
        world = SessionWorld(self.tmp, live=9151, serving=(REVISION, IMAGE), pre_policy=pre_policy)
        install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
            'replaced': {'web': {'id': 'web-old', 'image': OLD_IMAGE, 'revision': OLD},
                         'worker': {'id': 'worker-old', 'image': OLD_IMAGE, 'revision': OLD}}}})
        return world

    def switch_back(self, world):
        patches = world.patches()
        for patcher in patches:
            patcher.start()
        try:
            return install.phase_switch_back(install.Context(switch_back_args(self.tmp), self.tmp)), None
        except install.InstallError as error:
            return None, error
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def test_a_switch_back_to_a_revision_before_the_policy_ends_every_session_at_b4(self):
        world = self.world()
        details, error = self.switch_back(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.acts(*SESSION_ACTS), [
            ('recorder', 'start'),
            ('run', 'web', NEXT, 9150, OLD_IMAGE), ('wait', 'web', NEXT, 9150), ('smoke', 9150),        # B2
            ('stop', WORKER, '3600'), ('rename', WORKER, WORKER + '-previous'),                            # B3
            ('close', IMAGE, tuple(KINDS_OLD)), ('put_back', OLD_IMAGE),                                  # B4
            ('end_sessions', IMAGE, REVISION, OLD),                                                       # B4: sessions
            ('vhost', 'replace', 9150), ('reload', 9150), ('https', 9150, OLD),                           # B5
            ('drain', 9151), ('stop', WEB, '30'), ('rename', WEB, WEB + '-previous'), ('rename', NEXT, WEB),  # B6
            ('close', IMAGE, tuple(KINDS_OLD)), ('put_back', OLD_IMAGE),                                  # B7
            ('run', 'worker', WORKER, None, OLD_IMAGE), ('wait', 'worker', WORKER, None),                 # B8
            ('rm', WORKER + '-previous'), ('rm', WEB + '-previous'),                                      # B9
            ('recorder', 'stop')])
        self.assertEqual(details['sessions_ended']['ended'], 3)
        self.assertIn('every session ended (3', details['summary'])

    def test_an_end_that_fails_at_b4_resumes_this_revisions_pair_and_says_so(self):
        world = self.world()
        world.session_answer = install.InstallError('Ending every session failed (exit 1).')
        details, error = self.switch_back(world)
        self.assertIsInstance(error, install.InstallError)
        self.assertEqual(error.details['failed_at'], 'B4')
        self.assertEqual(world.names(), {WEB: (IMAGE, 9151, True), WORKER: (IMAGE, None, True)})
        self.assertEqual(world.acts('vhost'), [])
        self.assertIn('nothing was switched', str(error))
        self.assertIn('it may have ended every session', str(error))

    def test_a_switch_back_between_two_revisions_that_have_the_policy_ends_none(self):
        world = self.world(pre_policy=())
        details, error = self.switch_back(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.acts('end_sessions'), [])
        self.assertNotIn('sessions_ended', details)


class SessionScriptImportTests(unittest.TestCase):
    def test_the_end_runs_in_this_revisions_image_with_what_it_has(self):
        from test_install_fable_scripts import REMOVED, imported
        modules = imported(install.END_EVERY_SESSION)
        self.assertEqual(sorted(module for module in modules if module.startswith(REMOVED)), [])
        self.assertIn('studio.security_events', modules)
        self.assertIn("lock_timeout = '30s'", install.END_EVERY_SESSION)


if __name__ == '__main__':
    unittest.main()
