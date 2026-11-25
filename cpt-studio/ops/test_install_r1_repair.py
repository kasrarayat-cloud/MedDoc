"""Release 1's integrated refutation, round 1: the installer's repairs (repair builder I). Offline, under test_install's
host guard; the in-image scripts run on the disposable test database (test_install_harness2's DatabaseTest: skipped,
never passed, without one). Synthetic data only.

  I1  rollback-0, rollback-3: every session is ended when the site moves between a revision before release 1's session
      policy and one with it (the blue/green switch at S2, the swap once the old pair is stopped, the switch-back at
      B4), in this revision's image, with one SecurityEvent; never between two revisions that both have it.
  I2  rollback-1, rollback-2: no way back to a revision without release 1's disposal (switch-back, rollback-app in the
      keep layout, rollback-app's removal when the next pair is such a revision or not known) while a practice is closed
      or a document destroyed; refused before anything starts or stops, and again at the switch-back's B4.
  I3  installer-0: a re-grant is approved only by a line of the committed declaration that is exactly
      `--regrant <username>` (optionally in backticks), whitespace-trimmed - since repair round 2 (I2-6,
      installer-3) only by the line 'Approved: --regrant <username>', the words named nowhere else.
  I4  installer-1: every manage step refuses an argument it does not pass to its command (dispose execute's
      --workspace-id and --encounter-id), and --address is refused outside manage.
  I5  installer-2: the database's swap-off decision counts memory.swap.peak (memory peak plus swap peak), and skips the
      change when the swap peak cannot be read.
  I6  phileak-1, dataloss-3 (the installer's half): once an act has run, a secret or the reason's text in its output
      never discards its record - each is redacted before the log and the receipt are written, and counted.
  I7  dataloss-1: a receipt says whether an act's stdout was cut and how long it was; the ledger step keeps the ledger
      whole in a log of its own and records its sha256, size and line count.
  I8  installer-5 (judged no defect; the one call): the app phase's converter precondition holds the seal too.
  I9  installer-6: the ids-only copy of a retired web keeps the access line of the format before release 1 too.
  I10 installer-3: a SIGTERM, SIGHUP or Ctrl-C that lands while a RAM folder is wiped is acted on once the wipe has
      finished: the reason never stays in /dev/shm.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1_repair -v
"""
import datetime as dt
import hashlib
import io
import json
import os
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

    def test_a_container_not_ours_is_left_to_parks_own_refusal(self):
        foreign = {'Id': 'other-1', 'Image': 'sha256:' + 'e' * 64, 'State': {'Running': False},
                   'Config': {'Labels': {}}, 'HostConfig': {}}
        ctx = install.Context(SimpleNamespace(phase='app', revision=REVISION), self.tmp)
        with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: foreign if name == WEB else None), \
                mock.patch.object(install, 'has_session_policy', test_install.REAL_HAS_SESSION_POLICY), \
                mock.patch.object(install, 'docker') as docker, \
                self.assertRaisesRegex(install.InstallError, 'is not a CPT Studio web container'):
            install.swap_services(ctx, IMAGE, b'', 'disabled', '')
        docker.assert_not_called()

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


# --- I2: no way back to a revision without release 1's disposal while a practice is closed or a document destroyed ----

class DisposalReadTests(unittest.TestCase):
    def test_disposal_is_read_from_the_revisions_tree_and_an_unreadable_revision_is_refused(self):
        real, seen = test_install.REAL_HAS_DISPOSAL, []

        def git(answer_commit, answer_file):
            def fake_run(argv, **kwargs):
                seen.append(argv[-1])
                code = answer_commit if argv[-1].endswith('^{commit}') else answer_file
                return SimpleNamespace(returncode=code, stdout=b'', stderr=b'')
            return fake_run
        with mock.patch.object(install, 'run', git(0, 0)):
            self.assertIs(real(REVISION), True)
        self.assertEqual(seen[-1], f'{REVISION}:cpt-studio/studio/disposal.py')
        with mock.patch.object(install, 'run', git(0, 128)):
            self.assertIs(real(REVISION), False)
        with mock.patch.object(install, 'run', git(128, 0)), self.assertRaisesRegex(install.InstallError, 'cannot read'):
            real(REVISION)
        with self.assertRaisesRegex(install.InstallError, '40-character'):
            real('abc')

    def test_on_this_tree_release_1_has_it_and_the_revision_before_it_does_not(self):
        real = test_install.REAL_HAS_DISPOSAL
        head = install.run(['git', '-C', str(REPO_ROOT), 'rev-parse', 'HEAD']).stdout.decode().strip()
        self.assertIs(real(head), True)
        known = install.run(['git', '-C', str(REPO_ROOT), 'cat-file', '-e', f'{R0_REVISION}^{{commit}}'], check=False)
        if known.returncode:
            raise unittest.SkipTest(f'{R0_REVISION[:12]} is not in this clone')
        self.assertIs(real(R0_REVISION), False)

    def test_the_counts_are_judged_and_an_answer_that_is_not_two_counts_is_never_read_as_none(self):
        real = test_install.REAL_DISPOSAL_COUNTS
        for answer in ({'closed': 1}, {'closed': -1, 'destroyed': 0}, {'closed': True, 'destroyed': 0},
                       {'closed': '1', 'destroyed': 0}, [], None):
            with self.subTest(answer=answer), mock.patch.object(install, 'app_script', return_value=answer), \
                    self.assertRaisesRegex(install.InstallError, 'no answer it could be judged by'):
                real(IMAGE, b'')
        with mock.patch.object(install, 'app_script', return_value={'closed': 2, 'destroyed': 0}) as script:
            self.assertEqual(real(IMAGE, b''), {'closed': 2, 'destroyed': 0})
        self.assertIs(script.call_args.args[2], install.DISPOSAL_COUNTS)

    def test_the_refusal_names_how_many_of_each_and_why(self):
        with mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', {OLD}), \
                mock.patch.object(test_install, 'DISPOSAL_COUNTS_ANSWER', {'closed': 1, 'destroyed': 2}):
            refusal, counts = install.disposal_refusal(IMAGE, b'', OLD)
            self.assertEqual(counts, {'closed': 1, 'destroyed': 2})
            self.assertIn('1 practice(s) are closed and 2 document(s) destroyed', refusal)
            self.assertIn(f'revision {OLD[:12]} has no disposal', refusal)
            self.assertIn('fix forward', refusal)
            unknown, _ = install.disposal_refusal(IMAGE, b'', None)
            self.assertIn('is not known', unknown)
            self.assertEqual(install.disposal_refusal(IMAGE, b'', REVISION), ('', None))  # it has disposal: no read
        with mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', {OLD}):
            self.assertEqual(install.disposal_refusal(IMAGE, b'', OLD), ('', {'closed': 0, 'destroyed': 0}))


class DisposalCountsOnTheDatabaseTests(DatabaseTest):
    """DISPOSAL_COUNTS on real rows: a closed practice and a destroyed document's tombstone (rollback-1's input) are
    counted, through the base managers; open practices and live documents are not; counts only."""

    def test_closed_practices_and_destroyed_documents_are_counted(self):
        from django.utils import timezone
        from studio import models
        before = run_in_image(install.DISPOSAL_COUNTS, {})
        kept = self.encounter('kept')
        tombstone = self.encounter('tombstone')
        models.Encounter.objects.filter(pk=tombstone.pk).update(title='', destroyed_at=timezone.now(), state='destroyed')
        models.Workspace.objects.filter(pk=tombstone.workspace_id).update(closed_at=timezone.now())
        after = run_in_image(install.DISPOSAL_COUNTS, {})
        self.assertEqual(sorted(after), ['closed', 'destroyed'])
        self.assertEqual(after['closed'] - before['closed'], 1)
        self.assertEqual(after['destroyed'] - before['destroyed'], 1)
        self.assertIsNone(models.Encounter.objects.get(pk=kept.pk).destroyed_at)


class SwitchBackDisposalTests(TemporaryDirectoryTest):
    def world(self, *, counts=None, pre_disposal=(OLD,)):
        world = SessionWorld(self.tmp, live=9151, serving=(REVISION, IMAGE), pre_policy=())
        install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
            'replaced': {'web': {'id': 'web-old', 'image': OLD_IMAGE, 'revision': OLD},
                         'worker': {'id': 'worker-old', 'image': OLD_IMAGE, 'revision': OLD}}}})
        world.disposal = dict(counts or {'closed': 0, 'destroyed': 0})
        world.pre_disposal = set(pre_disposal)
        return world

    def switch_back(self, world, counts_side_effect=None):
        patches = world.patches() + [
            mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', world.pre_disposal),
            mock.patch.object(test_install, 'DISPOSAL_COUNTS_ANSWER', world.disposal),
            mock.patch.object(test_install, 'DISPOSAL_COUNTS_READ', [])]
        if counts_side_effect is not None:
            patches.append(mock.patch.object(install, 'disposal_counts', side_effect=counts_side_effect))
        for patcher in patches:
            patcher.start()
        try:
            result = install.phase_switch_back(install.Context(switch_back_args(self.tmp), self.tmp)), None
        except install.InstallError as error:
            result = None, error
        finally:
            world.disposal_reads = list(test_install.DISPOSAL_COUNTS_READ)
            for patcher in reversed(patches):
                patcher.stop()
        return result

    def test_a_closed_practice_or_a_destroyed_document_refuses_before_anything_starts(self):
        for counts in ({'closed': 1, 'destroyed': 0}, {'closed': 0, 'destroyed': 3}, {'closed': 2, 'destroyed': 5}):
            with self.subTest(counts=counts):
                for path in self.tmp.glob('*.json'):
                    path.unlink()
                world = self.world(counts=counts)
                details, error = self.switch_back(world)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn(f'{counts["closed"]} practice(s) are closed and {counts["destroyed"]} document(s) '
                              'destroyed', str(error))
                self.assertIn(f'revision {OLD[:12]} has no disposal', str(error))
                self.assertIn('fix forward', str(error))
                self.assertIn('nothing was started or stopped', str(error))
                self.assertEqual(error.details, {'disposal': counts})
                self.assertEqual(world.acts('run', 'stop', 'rename', 'close', 'vhost', 'end_sessions'), [])
                self.assertEqual(world.disposal_reads, [IMAGE])  # read in this revision's image

    def test_with_neither_it_goes_on_and_reads_again_at_b4(self):
        world = self.world()
        details, error = self.switch_back(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.disposal_reads, [IMAGE, IMAGE])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})

    def test_one_closed_since_the_first_read_refuses_at_b4_and_this_revisions_pair_resumes(self):
        world = self.world()
        details, error = self.switch_back(world, counts_side_effect=[{'closed': 0, 'destroyed': 0},
                                                                     {'closed': 1, 'destroyed': 0}])
        self.assertIsInstance(error, install.InstallError)
        self.assertEqual(error.details['failed_at'], 'B4')
        self.assertIn('before anything was closed, 1 practice(s) are closed', str(error))
        self.assertEqual(world.closes, [])
        self.assertEqual(world.acts('vhost'), [])
        self.assertEqual(world.names(), {WEB: (IMAGE, 9151, True), WORKER: (IMAGE, None, True)})

    def test_a_revision_with_disposal_is_switched_back_to_whatever_was_disposed(self):
        world = self.world(counts={'closed': 4, 'destroyed': 9}, pre_disposal=())
        details, error = self.switch_back(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.disposal_reads, [])  # never read: that revision lists and refuses them itself


class KeepLayoutDisposalTests(TemporaryDirectoryTest):
    def keep(self):
        from test_install_r2 import World, named
        world = World(self.tmp)
        world.unhealthy.add(WORKER)
        world.close_answer = named({'e1': ['member_answer']})
        details, failure = run_app(world)
        self.assertIn('the new web keeps serving on 9151', str(failure))
        world.unhealthy.discard(WORKER)
        world.close_answer = named({})
        world.inflight = {}
        world.events.clear()
        world.closes.clear()
        return world

    def run_rollback(self, world, counts, pre_disposal=(OLD,)):
        from test_install_r2 import run_rollback_app
        with mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', set(pre_disposal)), \
                mock.patch.object(test_install, 'DISPOSAL_COUNTS_ANSWER', counts):
            return run_rollback_app(world)

    def test_rollback_app_does_not_return_an_older_web_while_a_document_is_destroyed(self):
        world = self.keep()
        before = world.names()
        details, failure = self.run_rollback(world, {'closed': 0, 'destroyed': 1})
        self.assertIsInstance(failure, install.InstallError)
        self.assertIn('0 practice(s) are closed and 1 document(s) destroyed', str(failure))
        self.assertIn('nothing was stopped or removed', str(failure))
        self.assertEqual(world.names(), before)
        self.assertEqual(world.acts('stop', 'rm', 'close', 'vhost', 'reload'), [])

    def test_with_neither_or_to_a_web_with_disposal_it_switches_back(self):
        for counts, pre in (({'closed': 0, 'destroyed': 0}, (OLD,)), ({'closed': 1, 'destroyed': 1}, ())):
            with self.subTest(counts=counts, pre=pre):
                world = self.keep()
                details, failure = self.run_rollback(world, counts, pre)
                self.assertIsNone(failure, failure and str(failure))
                self.assertEqual(details['outcome'], 'switched')


class RollbackRemovalDisposalTests(TemporaryDirectoryTest):
    """rollback-app's removal of this revision's pair: the pair that runs next is the parked one, or not known."""

    def containers(self, parked=None):
        def container(role, image, revision, running=True):
            return {'Id': f'{role}-{revision[:4]}', 'Image': image, 'Created': '2026-11-01T12:00:00.000000Z',
                    'State': {'Running': running},
                    'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role,
                                          install.REVISION_LABEL: revision}}}
        live = {install.SERVICES[role]: container(role, IMAGE, REVISION) for role in ('web', 'worker')}
        if parked is not None:
            live.update({install.SERVICES[role] + '-previous': container(role, OLD_IMAGE, parked, running=False)
                         for role in ('web', 'worker')})
        return live

    def run_phase(self, live, counts, pre_disposal=(OLD,)):
        calls = []

        def fake_docker(*args, **kwargs):
            calls.append(args[:3])
            if args[0] == 'rm':
                for name in [name for name, c in live.items() if c['Id'] == args[-1]]:
                    del live[name]
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def coded(image_id, env_bytes, body, params, **kwargs):
            if body == install.END_EVERY_SESSION:  # repair round 2, sessions-2: no pair parked, or one before the
                calls.append(('end_sessions', params['to_revision']))  # session policy: ended before the removal
                return {'ended': 1, 'event': EVENT_ID}
            assert body == install.CODING_MADE, body[:60]
            return {'coding': {'encounters': [], 'created': [], 'rounds': 0, 'answers': 0,
                               'decisions': {'approve': 0, 'reject': 0, 'revoke': 0}, 'approved': 0,
                               'exports': {'draft': 0, 'approved': 0}}}
        ctx = install.Context(SimpleNamespace(phase='rollback-app', revision=REVISION), self.tmp)
        with mock.patch.multiple(install, inspect=lambda kind, name: live.get(name), docker=fake_docker,
                                 read_protected_env=mock.Mock(return_value=b''), require_db=mock.Mock(),
                                 undo_hazards=mock.Mock(return_value={}),
                                 close_undone_stages=mock.Mock(return_value={'closed': 0, 'kinds': [], 'hazards': {},
                                                                             'relabel': []}),
                                 put_back_states=mock.Mock(return_value={'encounters': 0, 'changed': {}}),
                                 stage_kinds_of=mock.Mock(return_value=list(install.COMMON_STAGE_KINDS)),
                                 app_script=coded, keep_container_log=mock.Mock(return_value={'kept': 0})), \
                mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', set(pre_disposal)), \
                mock.patch.object(test_install, 'DISPOSAL_COUNTS_ANSWER', counts):
            try:
                return install.phase_rollback_app(ctx), None, calls
            except install.InstallError as error:
                return None, error, calls

    def test_a_parked_pair_without_disposal_or_none_known_is_refused_before_anything_stops(self):
        for parked, said in ((OLD, f'revision {OLD[:12]} has no disposal'), (None, 'is not known')):
            with self.subTest(parked=parked):
                details, error, calls = self.run_phase(self.containers(parked), {'closed': 1, 'destroyed': 1})
                self.assertIsInstance(error, install.InstallError)
                self.assertIn('1 practice(s) are closed and 1 document(s) destroyed', str(error))
                self.assertIn(said, str(error))
                self.assertIn('nothing was stopped or removed', str(error))
                self.assertEqual(calls, [])

    def test_with_neither_or_a_parked_pair_with_disposal_the_pair_is_removed(self):
        for parked, counts, pre in ((None, {'closed': 0, 'destroyed': 0}, (OLD,)),
                                    (OLD, {'closed': 3, 'destroyed': 3}, ())):
            with self.subTest(parked=parked, counts=counts):
                details, error, calls = self.run_phase(self.containers(parked), counts, pre)
                self.assertIsNone(error, error and str(error))
                self.assertIn(('rm', '--force', 'web-aaaa'), calls)


# --- I3: a re-grant is named by a line of its own -----------------------------------------------------------------------

# installer-0's input: the declaration names alice inside a sentence
ALICE_SENTENCE = ('# Ruled act\n\nApproved by the owner: `--regrant alice` (alice was revoked in error).\nRevision '
                  + 'a' * 40 + '\n')


class RegrantDeclarationTests(TemporaryDirectoryTest):
    def names(self, text, words):
        root = self.tmp / f'repo-{uuid.uuid4().hex[:8]}'
        (root / 'docs').mkdir(parents=True)
        (root / 'docs' / 'declaration.md').write_bytes(text.encode('utf-8'))
        ctx = SimpleNamespace(door={'declaration': 'docs/declaration.md', 'declaration_commit': 'd' * 40})
        with mock.patch.object(install, 'ROOT', root):
            return install.declaration_names(ctx, words)

    def test_another_name_that_starts_with_it_or_a_sentence_names_nothing(self):
        for words in ('--regrant ali', '--regrant al', '--regrant alice'):
            with self.subTest(words=words):
                self.assertIs(self.names(ALICE_SENTENCE, words), False)
        for text in ('do not --regrant ali\n', 'We decided: --regrant ali\n', '- `--regrant ali`\n',
                     '* --regrant ali\n', '`--regrant ali` (approved)\n', '--regrant alice\n', '`--regrant alice`\n',
                     '--regrant ali, bob\n', '"--regrant ali"\n', '``--regrant ali``\n', '--regrant  ali\n',
                     'do not\u2028--regrant ali\n', '--regrant ali --regrant bob\n', ''):
            with self.subTest(text=text):
                self.assertIs(self.names(text, '--regrant ali'), False)

    def test_the_approval_line_names_it_bare_or_in_backticks(self):
        # repair round 2 (I2-6, installer-3): the words on a line of their own no longer approve - a list of re-grants
        # NOT approved holds exactly such lines; the approval is the line 'Approved: --regrant <name>'
        for text in ('Approved: --regrant ali\n', 'Approved: `--regrant ali`\n', 'Approved: --regrant ali\t\n',
                     'x\r\nApproved: `--regrant ali`\r\ny\r\n', ALICE_SENTENCE + '\nApproved: `--regrant ali`\n',
                     'Approved: --regrant ali'):
            with self.subTest(text=text):
                self.assertIs(self.names(text, '--regrant ali'), True)
        self.assertIs(self.names('Approved: `--regrant alice`\n', '--regrant alice'), True)
        for text in ('--regrant ali\n', '`--regrant ali`\n', '  --regrant ali\t\n', 'x\r\n`--regrant ali`\r\ny\r\n'):
            with self.subTest(old_form=text):
                self.assertIs(self.names(text, '--regrant ali'), False)

    def test_a_declaration_that_cannot_be_read_names_nothing(self):
        ctx = SimpleNamespace(door={'declaration': 'docs/missing.md', 'declaration_commit': 'd' * 40})
        with mock.patch.object(install, 'ROOT', self.tmp):
            self.assertIs(install.declaration_names(ctx, '--regrant ali'), False)
        (self.tmp / 'docs').mkdir()
        (self.tmp / 'docs' / 'undecodable.md').write_bytes(b'\xff\xfe\n--regrant ali\n')
        ctx = SimpleNamespace(door={'declaration': 'docs/undecodable.md', 'declaration_commit': 'd' * 40})
        with mock.patch.object(install, 'ROOT', self.tmp):
            self.assertIs(install.declaration_names(ctx, '--regrant ali'), False)


class RegrantAtTheDoorTests(TemporaryDirectoryTest):
    """installer-0 through the real phase_manage: ali, revoked, is never granted again on a declaration naming alice."""

    def run_grant(self, text, username='ali'):
        import test_install_r1 as r1
        world = r1.ManageWorld(self.tmp, grant={'exists': True, 'operator': False, 'revoked': True})
        root = self.tmp / 'repo'
        (root / r1.DECLARATION).parent.mkdir(parents=True, exist_ok=True)
        (root / r1.DECLARATION).write_text(text)
        reason = self.tmp / 'reason.txt'
        reason.write_bytes(b'Ticket 991: re-grant.\n')
        args = r1.parse('--phase', 'manage', '--command', 'grant-operator', '--username', username, '--regrant',
                        username, '--reason-file', str(reason), '--by', 'Ada Lovelace', '--review-by', r1.REVIEW_BY)
        args.receipts = str(self.tmp)
        ctx = install.Context(args, self.tmp)
        ctx.door = {'declaration': r1.DECLARATION, 'declaration_commit': r1.COMMIT}
        with mock.patch.multiple(install, ROOT=root, installed_image=mock.Mock(return_value='sha256:' + 'c' * 64),
                                 require_db=mock.Mock(), oneshot=world.oneshot, inspect=world.inspect,
                                 root_file=world.root, run_helper=world.run_helper, read_protected_env=mock.Mock(
                                     return_value=f'CPT_STUDIO_SECRET_KEY={r1.SECRET_VALUE}\n'.encode()),
                                 app_script=world.app_script):
            try:
                return install.phase_manage(ctx), None, world
            except install.InstallError as error:
                return None, error, world

    def test_a_declaration_naming_alice_never_grants_ali_again(self):
        details, error, world = self.run_grant(ALICE_SENTENCE)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('stays revoked', str(error))
        self.assertEqual(world.acts(), [])

    def test_the_approval_line_grants_it_again(self):
        details, error, world = self.run_grant(ALICE_SENTENCE + '\nApproved: `--regrant ali`\n')
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.acts()[0][:2], ['manage', 'grant_operator'])
        self.assertEqual(world.acts()[0][-1], '--regrant')


# --- I4: what was typed is what ran ---------------------------------------------------------------------------------

WORKSPACE = '0f8fad5b-d9cb-469f-a165-70867728950e'
DOCUMENT = '1f8fad5b-d9cb-469f-a165-70867728950e'
PLAN = '2f8fad5b-d9cb-469f-a165-70867728950e'
ARGUMENT_FLAGS = {'workspace_id': ('--workspace-id', WORKSPACE), 'encounter_id': ('--encounter-id', DOCUMENT),
                  'plan_id': ('--plan-id', PLAN), 'approved_by': ('--approved-by', 'Grace Hopper'),
                  'reason_file': ('--reason-file', '/r'), 'ledger_file': ('--ledger-file', '/l'),
                  'execute': ('--execute', None)}
# each argument's trace on the command line manage_argv builds (the RAM-only files are mounted, never named as typed)
ARGUMENT_TRACES = {'workspace_id': WORKSPACE, 'encounter_id': DOCUMENT, 'plan_id': PLAN, 'approved_by': 'Grace Hopper',
                   'reason_file': '--reason-file', 'ledger_file': '--replay-ledger', 'execute': '--execute'}
STEP_BASE = {'close': ('workspace_id', 'reason_file'), 'plan': ('workspace_id', 'reason_file'),
             'execute': ('plan_id', 'approved_by'), 'ledger': (), 'replay-ledger': ('ledger_file',)}


class ManageArgumentTests(unittest.TestCase):
    def argv(self, step, names):
        argv = ['--revision', REVISION, '--receipts', '/nonexistent/receipts', '--phase', 'manage', '--command',
                'dispose', '--dispose-step', step, '--by', 'Ada Lovelace']
        for name in names:
            flag, value = ARGUMENT_FLAGS[name]
            argv += [flag] if value is None else [flag, value]
        return argv

    def parse(self, argv):
        stderr = io.StringIO()
        with mock.patch('sys.stderr', stderr):
            try:
                return install.parse_args(argv), ''
            except SystemExit:
                return None, stderr.getvalue().strip().splitlines()[-1]

    def test_execute_refuses_a_workspace_or_a_document_it_never_passes(self):
        for name in ('workspace_id', 'encounter_id'):
            with self.subTest(name=name):
                args, refusal = self.parse(self.argv('execute', ('plan_id', 'approved_by', 'reason_file', name)))
                self.assertIsNone(args, f'{name} was accepted')
                self.assertIn(f'{ARGUMENT_FLAGS[name][0]} is not used by --dispose-step execute', refusal)
                self.assertIn('nothing was run', refusal)

    def test_every_dispose_step_refuses_every_argument_it_does_not_pass(self):
        self.assertEqual(set(install.DISPOSE_STEP_ARGUMENTS), set(install.DISPOSE_STEPS))
        for step, allowed in install.DISPOSE_STEP_ARGUMENTS.items():
            for name in install.DISPOSE_ARGUMENTS:
                if name in allowed:
                    continue
                with self.subTest(step=step, name=name):
                    args, refusal = self.parse(self.argv(step, (*STEP_BASE[step], name)))
                    self.assertIsNone(args, f'{step} took {name}')
                    self.assertIn(ARGUMENT_FLAGS[name][0], refusal)

    def test_what_each_step_takes_reaches_its_command_line(self):
        combinations = {'close': [()], 'plan': [()], 'execute': [()], 'ledger': [()],
                        'replay-ledger': [(), ('execute', 'approved_by')]}
        cases = [(step, (*STEP_BASE[step], *extra)) for step, extras in combinations.items() for extra in extras]
        cases.append(('plan', ('encounter_id', 'reason_file')))  # one document
        for step, names in cases:
            with self.subTest(step=step, names=names):
                args, refusal = self.parse(self.argv(step, names))
                self.assertIsNotNone(args, refusal)
                ctx = SimpleNamespace(args=args, door={'declaration': 'docs/d.md', 'declaration_commit': 'd' * 40})
                argv = install.manage_argv(ctx, args, install.MANAGE_COMMANDS['dispose'])
                for name in names:
                    self.assertIn(ARGUMENT_TRACES[name], argv, f'{name} was dropped')
                # the reason reaches the command exactly where it reads one (refutation round 1, builder D's point)
                self.assertEqual('--reason-file' in argv, step in ('close', 'plan'))

    def test_the_reason_is_required_exactly_where_the_command_reads_it(self):
        # studio/management/commands/dispose.py reads --reason-file at --close and --plan, and refuses either without one
        self.assertEqual(install.DISPOSE_REASON_REQUIRED, ('close', 'plan'))
        for step in install.DISPOSE_STEPS:
            with self.subTest(step=step):
                base = tuple(name for name in STEP_BASE[step] if name != 'reason_file')
                args, refusal = self.parse(self.argv(step, base))
                if step in install.DISPOSE_REASON_REQUIRED:
                    self.assertIsNone(args)
                    self.assertIn(f'--dispose-step {step} needs --reason-file', refusal)
                    self.assertIn('reason_file', install.DISPOSE_STEP_ARGUMENTS[step])
                else:
                    self.assertIsNotNone(args, refusal)
                    args, refusal = self.parse(self.argv(step, (*base, 'reason_file')))
                    self.assertIsNone(args)
                    self.assertIn(f'--reason-file is not used by --dispose-step {step}', refusal)
        args, refusal = self.parse(self.argv('plan', ('workspace_id', 'encounter_id', 'reason_file')))
        self.assertIsNone(args)
        self.assertIn('not both', refusal)

    def test_address_is_refused_by_every_phase_but_manage(self):
        for phase, extra in (('operators', ()), ('provision', ('--owner-username', 'dr-owner', '--by', 'Ada Lovelace')),
                             ('preflight', ()), ('verify', ())):
            with self.subTest(phase=phase):
                args, refusal = self.parse(['--revision', REVISION, '--receipts', '/nonexistent/receipts', '--phase',
                                            phase, *extra, '--address', '203.0.113.7'])
                self.assertIsNone(args)
                self.assertIn(f'--address is not used by --phase {phase}', refusal)
        args, refusal = self.parse(['--revision', REVISION, '--receipts', '/nonexistent/receipts', '--phase', 'manage',
                                    '--command', 'clear-signin-failures', '--address', '203.0.113.7', '--reason-file',
                                    '/r', '--by', 'Ada Lovelace'])
        self.assertIsNotNone(args, refusal)

    def test_every_parser_argument_is_bound_to_the_phases_that_use_it(self):
        parser_names = {'pfs_zip', 'mue_zip', 'pfs_retrieved_at', 'mue_retrieved_at', 'coding_mode', 'authorization_ref',
                        'provider_mode', 'astra_mode', 'fable_mode', 'interpreter_mode', 'owner_username',
                        'owner_display_name', 'agent_username', 'agent_display_name', 'workspace_name', 'specialty',
                        'reset_passwords', 'by', 'review_by', 'regrant', 'command', 'username', 'address',
                        'reason_file', 'approved_by', 'execute', 'workspace_id', 'encounter_id', 'dispose_step',
                        'ledger_file', 'plan_id', 'all_human_accounts'}
        with mock.patch('sys.stderr', io.StringIO()), mock.patch.object(install, 'argument_problem', return_value=''):
            args = install.parse_args(['--revision', REVISION, '--receipts', '/r', '--phase', 'verify'])
        given = set(vars(args)) - {'phase', 'revision', 'receipts'}
        self.assertEqual(given, parser_names)
        self.assertEqual(sorted(given - set(install.PHASE_ARGUMENTS)), [])


# --- I5: the swap the database used earlier counts --------------------------------------------------------------------

MIB = 2 ** 20


class CgroupScriptWorld:
    """test_install_r1.DbWorld whose container answers the cgroup script for exactly the files it names (installer-2's
    probe): a file the installer does not name is never read, whatever the cgroup holds."""

    @staticmethod
    def make(cgroup, **container):
        import re
        import test_install_r1 as r1

        class World(r1.DbWorld):
            def docker(self, *args, **kwargs):
                if args[:3] == ('exec', install.DB_CONTAINER, 'sh'):
                    self.calls.append(args)
                    names = re.search(r'for f in ([^;]+);', args[-1]).group(1).split()
                    out = ''.join(f'{name}={cgroup[name]}\n' for name in names if name in cgroup)
                    return SimpleNamespace(returncode=0, stdout=out.encode(), stderr=b'')
                if args[0] == 'update':
                    cgroup.update({'memory.max': str(512 * MIB), 'memory.swap.max': '0'})
                return super().docker(*args, **kwargs)
        return World(r1.db_container(**container))


class DatabaseSwapPeakTests(TemporaryDirectoryTest):
    def test_swap_used_earlier_and_paged_back_counts_into_the_peak(self):
        # installer-2's input: 300 MiB RAM high-water, 300 MiB swap high-water, nothing in swap today, 8 days up
        cgroup = {'memory.max': 'max', 'memory.swap.max': 'max', 'memory.peak': str(300 * MIB),
                  'memory.swap.current': '0', 'memory.swap.peak': str(300 * MIB)}
        world = CgroupScriptWorld.make(cgroup, swap=-1, uptime_days=8)
        details, error = world.run(self.tmp)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('600.0 MiB together', str(error))
        self.assertIn('memory.swap.peak', str(error))
        self.assertIn('limits were left as they are', str(error))
        self.assertEqual(world.acts('update'), [])
        self.assertEqual(error.details['swap_peak'], 300 * MIB)

    def test_a_swap_peak_under_the_share_updates_and_is_recorded(self):
        cgroup = {'memory.max': 'max', 'memory.swap.max': 'max', 'memory.peak': str(300 * MIB),
                  'memory.swap.current': '0', 'memory.swap.peak': str(100 * MIB)}  # 400 MiB, under 409.6
        world = CgroupScriptWorld.make(cgroup, swap=-1, uptime_days=8)
        details, error = world.run(self.tmp)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['memory']['state'], 'updated')
        self.assertEqual(details['memory']['swap_peak'], 100 * MIB)
        self.assertEqual(len(world.acts('update')), 1)

    def test_what_sits_in_swap_now_still_counts_when_the_peak_reads_lower(self):
        cgroup = {'memory.max': 'max', 'memory.swap.max': 'max', 'memory.peak': str(300 * MIB),
                  'memory.swap.current': str(200 * MIB), 'memory.swap.peak': '0'}  # an inconsistent reading
        world = CgroupScriptWorld.make(cgroup, swap=-1, uptime_days=8)
        details, error = world.run(self.tmp)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('500.0 MiB together', str(error))

    def test_a_swap_peak_that_cannot_be_read_skips_the_change_and_says_why(self):
        for value in (None, 'max', '', '12 kB'):
            with self.subTest(value=value):
                cgroup = {'memory.max': 'max', 'memory.swap.max': 'max', 'memory.peak': str(100 * MIB),
                          'memory.swap.current': '0'}
                if value is not None:
                    cgroup['memory.swap.peak'] = value
                world = CgroupScriptWorld.make(cgroup, swap=-1, uptime_days=8)
                details, error = world.run(self.tmp)
                self.assertIsNone(error, error and str(error))
                self.assertEqual(details['memory']['state'], 'skipped')
                self.assertIn('no readable memory.swap.peak', details['memory']['why'])
                self.assertIn('memory limits left as they are', details['summary'])
                self.assertEqual(world.acts('update'), [])

    def test_the_cgroup_script_names_the_swap_peak(self):
        self.assertIn('memory.swap.peak', install.DB_CGROUP_FILES)


# --- I6: an act that ran keeps its record, its secrets and the reason redacted -----------------------------------------

# dataloss-3's input: the plan's reason, given again to execute; before builder D's repair the certificate's ledger line
# repeated it, and since it the certificate names the reason by its digest alone (sha256:<hex>)
PLAN_REASON = b'Misfiled upload: the document belongs to another practice (incident 4521).\n'
CERTIFICATE_PLAN = '2f8fad5b-d9cb-469f-a165-70867728950e'


def certificate(reason_text=None, *, approved_by='Grace Hopper'):
    """A destruction certificate as `dispose --execute` prints it: with ``reason_text``, the shape before builder D's
    repair (its ledger line carries the reason); without, the shape since (the reason's sha256 alone)."""
    reason = reason_text if reason_text is not None else 'sha256:' + hashlib.sha256(PLAN_REASON).hexdigest()
    line = json.dumps({'event': 'completed', 'plan': CERTIFICATE_PLAN, 'reason': reason, 'rows': 12, 'files': 3,
                       'approved_by': approved_by}, sort_keys=True)
    return (f'Destruction certificate\nPlan {CERTIFICATE_PLAN}: completed\nRun by: Ada Lovelace; approved by: '
            f'{approved_by}\nRows destroyed: 12\nFiles remaining: 0\nLedger line: {line}\n').encode()


class RedactOutputTests(unittest.TestCase):
    MARK = install.REDACTED_MARK

    def test_a_secret_is_replaced_wherever_it_occurs_and_counted(self):
        secret = 'S' * 48
        out, counts = install.redact_output(f'a{secret}b {secret}\n'.encode(), [secret])
        self.assertEqual(out, b'a' + self.MARK + b'b ' + self.MARK + b'\n')
        self.assertEqual(counts, {'secret': 2, 'reason': 0})

    def test_the_reason_as_written_and_as_json_writes_it_is_replaced(self):
        reason = 'Dr M\u00fcller said "remove it"\nsecond line of the reason'
        values = install.reason_values(reason.encode())
        for shown in (reason, json.dumps(reason)[1:-1], json.dumps(reason, ensure_ascii=False)[1:-1],
                      'second line of the reason'):
            with self.subTest(shown=shown):
                out, counts = install.redact_output(f'x {shown} y'.encode(), reasons=values)
                self.assertEqual(out, b'x ' + self.MARK + b' y')
                self.assertEqual(counts, {'secret': 0, 'reason': 1})

    def test_a_short_reason_never_alters_an_id_or_a_digest_that_contains_it(self):
        values = install.reason_values(b'dead')
        digest = 'c0ffee' + 'dead' + 'beef' * 3
        out, counts = install.redact_output(f'sha256 {digest}; reason: dead.'.encode(), reasons=values)
        self.assertEqual(out, f'sha256 {digest}; reason: '.encode() + self.MARK + b'.')
        self.assertEqual(counts['reason'], 1)

    def test_one_pass_reads_no_replacement_again_and_nothing_given_changes_nothing(self):
        out, counts = install.redact_output(b'redacted by the installer', reasons=['redacted by the installer'])
        self.assertEqual((out, counts), (self.MARK, {'secret': 0, 'reason': 1}))
        self.assertEqual(install.redact_output(b'plain', [], []), (b'plain', {'secret': 0, 'reason': 0}))
        self.assertEqual(install.redact_output(b'plain', [''], ['']), (b'plain', {'secret': 0, 'reason': 0}))
        self.assertEqual(install.redaction_record({'secret': 0, 'reason': 0}), {})
        self.assertEqual(install.redaction_record({'secret': 1, 'reason': 0}, {'secret': 0, 'reason': 2}),
                         {'redacted': {'secret': 1, 'reason': 2}})


class ExecuteWithThePlansReasonTests(TemporaryDirectoryTest):
    """phileak-1 and dataloss-3 through the real phase_manage: execute given the plan's own reason file is refused
    before anything runs (the command never reads one: the plan's own reason is used), and once an act has run nothing
    in its output makes its record vanish (refutation round 1, builder D's point: a reason line that the output happens
    to repeat - 'Grace Hopper', the approver's own name - is redacted, never a lost certificate)."""

    def world(self, output, *, exit_code=0):
        import test_install_r1 as r1
        return r1, r1.ManageWorld(self.tmp, output=output, exit_code=exit_code)

    def test_execute_given_the_plans_reason_file_is_refused_before_anything_runs(self):
        r1, world = self.world(certificate(PLAN_REASON.decode().strip()))
        execute = ('--command', 'dispose', '--dispose-step', 'execute', '--plan-id', r1.PLAN, '--by', 'Ada Lovelace',
                   '--approved-by', 'Grace Hopper')
        with self.assertRaises(SystemExit):
            world.run(*execute, '--reason-file', 'REASON', reason=PLAN_REASON)
        self.assertEqual(world.oneshots, [])  # nothing ran, so nothing was destroyed
        self.assertIn('--reason-file is not used by --dispose-step execute',
                      r1.refused('--phase', 'manage', *execute, '--reason-file', '/r'))

    def test_the_certificate_is_kept_whole_with_the_plans_reason_as_its_digest(self):
        r1, world = self.world(certificate())
        details = world.run('--command', 'dispose', '--dispose-step', 'execute', '--plan-id', r1.PLAN, '--by',
                            'Ada Lovelace', '--approved-by', 'Grace Hopper')
        self.assertEqual(world.acts()[0][:3], ['manage', 'dispose', '--execute'])
        self.assertEqual((details['exit'], details['mode']), (0, 'executed'))
        self.assertNotIn('redacted', details)  # no reason given, no secret printed: nothing touched
        self.assertEqual(details['stdout'], certificate().decode())
        self.assertEqual(Path(details['log']).read_bytes(), certificate())

    def test_a_reason_line_the_output_happens_to_repeat_never_discards_the_record(self):
        # builder D's example: a reason file whose line is just the approver's name, which the act's output also says.
        # Since repair round 2 (I2-7, installer-5) it is refused before the act: a name alone is not a reason in words,
        # and its redaction took the approver's name out of the certificate's own record
        r1, world = self.world(certificate())
        with self.assertRaisesRegex(install.InstallError, 'must give the reason in words'):
            world.run('--command', 'dispose', '--dispose-step', 'plan', '--workspace-id', r1.WORKSPACE,
                      '--reason-file', 'REASON', '--by', 'Ada Lovelace', reason=b'Grace Hopper\n')
        self.assertEqual(world.acts(), [])
        # a reason in words that the output happens to repeat is redacted there, and the record is kept
        details = world.run('--command', 'dispose', '--dispose-step', 'plan', '--workspace-id', r1.WORKSPACE,
                            '--reason-file', 'REASON', '--by', 'Ada Lovelace', reason=b'approved by: Grace Hopper\n')
        self.assertEqual(details['exit'], 0)
        self.assertEqual(details['redacted'], {'secret': 0, 'reason': 1})
        self.assertIn(f'Plan {CERTIFICATE_PLAN}: completed', details['stdout'])
        self.assertIn('Rows destroyed: 12', details['stdout'])
        self.assertNotIn('approved by: Grace Hopper', details['stdout'])
        log = Path(details['log']).read_bytes()
        self.assertIn(b'Destruction certificate', log)
        self.assertNotIn(b'approved by: Grace Hopper', log)
        self.assertIn('1 occurrence(s) of the reason', details['summary'])

    def test_the_shape_before_builder_ds_repair_is_kept_with_the_reason_redacted(self):
        reason_text = PLAN_REASON.decode().strip()
        r1, world = self.world(certificate(reason_text))
        details = world.run('--command', 'dispose', '--dispose-step', 'plan', '--workspace-id', r1.WORKSPACE,
                            '--reason-file', 'REASON', '--by', 'Ada Lovelace', reason=PLAN_REASON)
        self.assertEqual(details['redacted'], {'secret': 0, 'reason': 1})
        self.assertIn('Destruction certificate', details['stdout'])
        self.assertNotIn('incident 4521', json.dumps(details))
        self.assertNotIn(b'incident 4521', Path(details['log']).read_bytes())

    def test_a_failed_act_keeps_its_certificate_too(self):
        r1, world = self.world(certificate() + b'Files remaining: 1\n', exit_code=1)
        with self.assertRaisesRegex(install.InstallError, 'failed \\(exit 1\\)') as caught:
            world.run('--command', 'dispose', '--dispose-step', 'execute', '--plan-id', r1.PLAN, '--by',
                      'Ada Lovelace', '--approved-by', 'Grace Hopper')
        self.assertIn('Files remaining: 1', caught.exception.details['stdout'])
        self.assertIn(b'Destruction certificate', Path(caught.exception.details['log']).read_bytes())

    def test_the_receipt_main_writes_holds_the_certificate(self):
        import test_install_r1 as r1
        receipts = self.tmp / 'receipts'
        receipts.mkdir(mode=0o700)
        world = r1.ManageWorld(self.tmp, output=certificate())
        printed = io.StringIO()
        with mock.patch.multiple(install, installed_image=mock.Mock(return_value='sha256:' + 'c' * 64),
                                 require_db=mock.Mock(), oneshot=world.oneshot, inspect=world.inspect,
                                 root_file=world.root, run_helper=world.run_helper, read_protected_env=mock.Mock(
                                     return_value=f'CPT_STUDIO_SECRET_KEY={r1.SECRET_VALUE}\n'.encode()),
                                 app_script=world.app_script,
                                 check_door=mock.Mock(return_value={'declaration': r1.DECLARATION,
                                                                    'declaration_commit': r1.COMMIT}),
                                 check_tree=mock.Mock(return_value={'mode': 'exact'})), \
                mock.patch('sys.stdout', printed):
            code = install.main(['--phase', 'manage', '--revision', REVISION, '--receipts', str(receipts), '--command',
                                 'dispose', '--dispose-step', 'execute', '--plan-id', r1.PLAN, '--by', 'Ada Lovelace',
                                 '--approved-by', 'Grace Hopper'])
        line = json.loads(printed.getvalue().strip().splitlines()[-1])
        self.assertEqual((code, line['ok']), (0, True), line)
        record = json.loads(Path(line['receipt']).read_text())
        self.assertEqual(record['details']['stdout'], certificate().decode())
        logs = [path for path in receipts.glob('*.log') if b'Destruction certificate' in path.read_bytes()]
        self.assertEqual(len(logs), 1)


class AfterTheActTests(TemporaryDirectoryTest):
    """Refutation round 1 (builder D's point, phileak-1's class): once an act ran, what follows it - its RAM folder's
    wipe, an export's seal - failing never takes the act's record with it: the receipt's error carries the record (its
    exit, its log, its output), and says what did not finish."""

    def failing_world(self, failing_body, output):
        import test_install_r1 as r1

        class World(r1.ManageWorld):
            def run_helper(world, body, params, *, mounts, **kwargs):
                answer = super().run_helper(body, params, mounts=mounts, **kwargs)  # it ran (nothing is left behind)
                if body is failing_body:
                    raise install.InstallError('A root helper failed with exit 1.')
                return answer
        return r1, World(self.tmp, output=output)

    def test_a_wipe_that_fails_after_a_destruction_keeps_its_certificate(self):
        r1, world = self.failing_world(install.H_RAM_WIPE, certificate())
        with self.assertRaises(install.InstallError) as caught:
            world.run('--command', 'dispose', '--dispose-step', 'plan', '--workspace-id', r1.WORKSPACE,
                      '--reason-file', 'REASON', '--by', 'Ada Lovelace')
        details = caught.exception.details
        self.assertIn('ran (exit 0) and its record is kept', str(caught.exception))
        self.assertIn('A root helper failed with exit 1.', str(caught.exception))
        self.assertEqual(details['stdout'], certificate().decode())
        self.assertEqual(Path(details['log']).read_bytes(), certificate())
        self.assertEqual(details['after_act'], 'A root helper failed with exit 1.')

    def test_an_export_whose_seal_fails_keeps_its_record(self):
        r1, world = self.failing_world(install.H_SEAL_EXPORT, b'exported 2 documents\n')
        with self.assertRaises(install.InstallError) as caught:
            world.run('--command', 'export-workspace', '--workspace-id', r1.WORKSPACE, '--reason-file', 'REASON',
                      '--by', 'Ada Lovelace')
        self.assertEqual(caught.exception.details['stdout'], 'exported 2 documents\n')
        self.assertIn('what follows the act did not finish', str(caught.exception))

    def test_a_code_act_whose_wipe_fails_keeps_its_record_and_no_code(self):
        import test_install_r1 as r1
        world = r1.ManageWorld(self.tmp, output=b'reset the second factor of platform-operator\n')
        real_exit = install.RamFiles.__exit__

        def exit_then_fail(ram, *exc):
            real_exit(ram, *exc)  # wiped: nothing is left in /dev/shm by this test
            raise install.InstallError('the RAM folder could not be wiped (synthetic)')
        with mock.patch.object(install.RamFiles, '__exit__', exit_then_fail), \
                self.assertRaises(install.InstallError) as caught:
            world.run('--command', 'reset-second-factor', '--username', 'platform-operator', '--reason-file',
                      'REASON', '--by', 'Ada Lovelace')
        details = caught.exception.details
        self.assertEqual((details['exit'], details['setup_code_kept']), (0, False))
        self.assertIn('reset the second factor', details['stdout'])
        self.assertEqual(list(world.etc.iterdir()), [])  # the code was never committed

    def test_provision_whose_wipe_fails_after_the_hand_over_keeps_its_record(self):
        from test_install import no_grants
        args = SimpleNamespace(phase='provision', revision=REVISION, receipts=str(self.tmp), reset_passwords=None,
                               owner_username='owner-gi', agent_username=None, owner_display_name='',
                               agent_display_name='CPT Studio review agent', workspace_name='Gastroenterology',
                               specialty='gastroenterology', by='Ada Lovelace')
        finals = []
        real_exit = install.RamFiles.__exit__

        def exit_then_fail(ram, *exc):
            real_exit(ram, *exc)
            raise install.InstallError('the RAM folder could not be wiped (synthetic)')

        def fake_root_file(op, **params):
            finals.append(op)
            return {'final_exists': False, 'staged_exists': False} if op == 'state' else {}

        def fake_oneshot(image_id, command, env, **kwargs):
            return SimpleNamespace(returncode=0, stdout=b'created human account owner-gi (owner)\n', stderr=b'')
        with mock.patch.multiple(install, installed_image=mock.Mock(return_value='sha256:' + 'c' * 64),
                                 require_db=mock.Mock(), read_protected_env=mock.Mock(return_value=b''),
                                 root_file=fake_root_file, oneshot=fake_oneshot, app_script=no_grants), \
                mock.patch.object(install.RamFiles, '__exit__', exit_then_fail), \
                self.assertRaises(install.InstallError) as caught:
            install.phase_provision(install.Context(args, self.tmp))
        self.assertEqual(finals, ['state', 'stage', 'commit'])  # handed over before the wipe failed
        details = caught.exception.details
        self.assertEqual(details['accounts'], {'owner-gi': 'created'})
        self.assertIn('provision ran (exit 0) and its record is kept', str(caught.exception))
        self.assertTrue(Path(details['log']).exists())

    def test_an_operators_grant_whose_wipe_fails_keeps_its_record(self):
        from test_install_bluegreen import OperatorsPhaseTests
        harness = OperatorsPhaseTests('test_the_spec_holds_the_human_operator_alone_and_no_agent_login_is_written')
        harness.setUp()  # its own temporary folder, removed by its tearDown
        self.addCleanup(harness.tearDown)
        real_exit = install.RamFiles.__exit__

        def exit_then_fail(ram, *exc):
            real_exit(ram, *exc)  # wiped: nothing is left in /dev/shm by this test
            if ram.path.name.startswith('cpt-studio-operators-'):
                raise install.InstallError('the RAM folder could not be wiped (synthetic)')
            return False
        with mock.patch.object(install.RamFiles, '__exit__', exit_then_fail), \
                self.assertRaises(install.InstallError) as caught:
            harness.run_phase()
        details = caught.exception.details
        self.assertEqual(details['grants']['platform-operator']['exit'], 0)
        self.assertTrue(Path(details['grants']['platform-operator']['log']).exists())
        self.assertIn('manage grant_operator for platform-operator ran (exit 0) and its record is kept',
                      str(caught.exception))

    def test_a_signal_during_the_wipe_keeps_the_acts_record_beside_the_interrupt(self):
        import signal as signals
        case = SignalDuringWipeTests('test_a_ctrl_c_during_the_wipe_too')
        case.tmp = self.tmp
        exit_code, record, seen, shm = case.run_main(signals.SIGTERM)
        self.assertEqual((exit_code, record['interrupted']), (143, 'SIGTERM'))
        self.assertEqual(record['details']['stdout'], 'Plan 1 recorded: 3 rows.\n')
        self.assertEqual(record['details']['exit'], 0)
        self.assertFalse(seen['folder'].exists())


class ProvisionPrintedPasswordTests(TemporaryDirectoryTest):
    def test_a_printed_password_is_never_handed_over_and_the_act_is_recorded(self):
        from test_install import no_grants
        args = SimpleNamespace(phase='provision', revision=REVISION, receipts=str(self.tmp), reset_passwords=None,
                               owner_username='owner-gi', agent_username=None, owner_display_name='',
                               agent_display_name='CPT Studio review agent', workspace_name='Gastroenterology',
                               specialty='gastroenterology', by='Ada Lovelace')
        finals, printed = [], []

        def fake_root_file(op, **params):
            finals.append(op)
            return {'final_exists': False, 'staged_exists': False} if op == 'state' else {}

        def fake_oneshot(image_id, command, env, **kwargs):
            source = next(mount for mount in kwargs['mounts'] if 'owner-gi.pw' in mount).split('src=', 1)[1]
            password = Path(source.split(',', 1)[0]).read_text()
            printed.append(password)
            out = f'created human account owner-gi (owner)\nusing password {password}\n'
            return SimpleNamespace(returncode=0, stdout=out.encode(), stderr=b'')
        with mock.patch.multiple(install, installed_image=mock.Mock(return_value='sha256:' + 'c' * 64),
                                 require_db=mock.Mock(), read_protected_env=mock.Mock(return_value=b''),
                                 root_file=fake_root_file, oneshot=fake_oneshot, app_script=no_grants), \
                self.assertRaises(install.InstallError) as caught:
            install.phase_provision(install.Context(args, self.tmp))
        (password,) = printed
        self.assertIn('printed the password of 1 account(s)', str(caught.exception))
        self.assertEqual(finals, ['state', 'stage', 'discard'])  # never committed: no password handed over
        self.assertEqual(caught.exception.details['redacted'], {'secret': 1, 'reason': 0})
        log = Path(caught.exception.details['log']).read_text()
        self.assertIn('created human account owner-gi (owner)', log)
        self.assertNotIn(password, log)
        self.assertNotIn(password, json.dumps(caught.exception.details))


# --- I7: the ledger is kept whole, and a cut receipt copy says it was cut ---------------------------------------------

def synthetic_ledger(lines=14, width=1420):
    """A ledger as `dispose --ledger` prints it: one signed JSON line per DisposalEvent (synthetic ids and MACs), each
    about ``width`` characters - dataloss-1's 14 lines and 19,922 characters by default."""
    out = []
    for number in range(lines):
        entry = {'id': str(uuid.UUID(int=number + 1)), 'stage': 'completed', 'counts': {'rows': number},
                 'pad': 'x' * (width - 140)}
        out.append(json.dumps({'entry': entry, 'mac': f'{number:064x}'}, sort_keys=True))
    return ('\n'.join(out) + '\n').encode()


class LedgerKeptWholeTests(TemporaryDirectoryTest):
    def run_ledger(self, output, *extra, reason=None):
        import test_install_r1 as r1
        world = r1.ManageWorld(self.tmp, output=output)
        kwargs = {'reason': reason} if reason is not None else {}
        return world.run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace', *extra, **kwargs)

    def test_a_ledger_longer_than_the_receipt_keeps_is_whole_in_its_log_and_the_cut_is_said(self):
        ledger = synthetic_ledger()
        self.assertGreater(len(ledger), install.STDOUT_KEPT)
        details = self.run_ledger(ledger)
        printed = details['ledger_printed']
        self.assertEqual(Path(printed['log']).read_bytes(), ledger)  # whole: the copy to keep
        self.assertEqual(printed['sha256'], hashlib.sha256(ledger).hexdigest())
        self.assertEqual((printed['bytes'], printed['lines'], printed['redacted']), (len(ledger), 14, False))
        self.assertEqual(details['log'], printed['log'])
        self.assertIs(details['stdout_cut'], True)
        self.assertEqual(details['stdout_chars'], len(ledger.decode()))
        self.assertEqual(len(details['stdout']), install.STDOUT_KEPT)
        self.assertIn(f'the receipt keeps the last {install.STDOUT_KEPT} of its {len(ledger)} characters',
                      details['summary'])
        self.assertIn('is kept whole in', details['summary'])

    def test_a_short_output_is_not_cut_and_says_so(self):
        ledger = synthetic_ledger(lines=2, width=300)
        details = self.run_ledger(ledger)
        self.assertIs(details['stdout_cut'], False)
        self.assertEqual(details['stdout'], ledger.decode())
        self.assertNotIn('the receipt keeps the last', details['summary'])
        import test_install_r1 as r1
        world = r1.ManageWorld(self.tmp, output=b'revoked ops-agent\n')
        other = world.run('--command', 'revoke-operator', '--username', 'ops-agent', '--reason-file', 'REASON', '--by',
                          'Ada Lovelace')
        self.assertEqual((other['stdout_cut'], other['stdout_chars']), (False, len('revoked ops-agent\n')))
        self.assertNotIn('ledger_printed', other)

    def test_a_secret_in_stderr_alone_leaves_the_ledger_whole_and_verifiable(self):
        import test_install_r1 as r1
        ledger = synthetic_ledger(lines=2, width=300)

        class World(r1.ManageWorld):
            def oneshot(world, image_id, command, env, **kwargs):
                answer = super().oneshot(image_id, command, env, **kwargs)
                if command[:2] == ['manage', 'dispose']:
                    return SimpleNamespace(returncode=0, stdout=ledger,
                                           stderr=f'warning: settings {r1.SECRET_VALUE}\n'.encode())
                return answer
        details = World(self.tmp).run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')
        self.assertEqual(details['redacted'], {'secret': 1, 'reason': 0})
        self.assertIs(details['ledger_printed']['redacted'], False)
        self.assertEqual(Path(details['ledger_printed']['log']).read_bytes(), ledger)
        self.assertNotIn('no longer verifies', details['summary'])
        self.assertNotIn(r1.SECRET_VALUE.encode(), Path(details['stderr_log']).read_bytes())

    def test_a_secret_printed_in_the_ledger_is_a_finding_that_says_the_line_no_longer_verifies(self):
        import test_install_r1 as r1
        ledger = synthetic_ledger(lines=2, width=300).replace(b'"stage": "completed"',
                                                              f'"stage": "{r1.SECRET_VALUE}"'.encode(), 1)
        details = self.run_ledger(ledger)
        self.assertIs(details['ledger_printed']['redacted'], True)
        self.assertIn('FINDING: a secret it printed was redacted, so the line holding it no longer verifies',
                      details['summary'])
        self.assertNotIn(r1.SECRET_VALUE.encode(), Path(details['ledger_printed']['log']).read_bytes())

    def test_the_ledger_step_takes_no_reason(self):
        import test_install_r1 as r1
        self.assertIn('--reason-file is not used by --dispose-step ledger',
                      r1.refused('--phase', 'manage', '--command', 'dispose', '--dispose-step', 'ledger', '--by',
                                 'Ada Lovelace', '--reason-file', '/r'))


# --- I8: the app phase's converter precondition holds the seal --------------------------------------------------------

class AppConverterSealTests(TemporaryDirectoryTest):
    def test_an_unsealed_converter_refuses_the_app_phase_before_anything_starts(self):
        from test_install_converter import ConverterWorld, converter_container
        # installer-5's input: labelled, this revision and image, running and healthy - and on cpt-studio-net, with
        # the files volume and the application's secret names in its environment
        unsealed = converter_container(**{
            'HostConfig.NetworkMode': install.NETWORK,
            'Config.Env': ['CPT_STUDIO_SECRET_KEY=synthetic', 'CPT_STUDIO_DB_PASSWORD=synthetic'],
            'Mounts': [{'Type': 'volume', 'Name': install.CONVERT_VOLUME, 'Destination': install.CONVERT_DIR},
                       {'Type': 'volume', 'Name': install.FILES_VOLUME, 'Destination': install.STATE_DIR}]})
        world = ConverterWorld(self.tmp, converter=unsealed)
        details, error = run_app(world)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn("its network is 'cpt-studio-net', not none", str(error))
        self.assertIn('not the convert volume alone', str(error))
        self.assertIn('CPT_STUDIO_DB_PASSWORD, CPT_STUDIO_SECRET_KEY', str(error))
        self.assertIn('run --phase converter first', str(error))
        self.assertEqual(world.acts('run', 'stop', 'rename', 'oneshot', 'vhost'), [])

    def test_the_sealed_converter_passes(self):
        from test_install_converter import ConverterWorld
        world = ConverterWorld(self.tmp)
        details, error = run_app(world)
        self.assertIsNone(error, error and str(error))


# --- I9: the access line of the format before release 1 is kept ids only ---------------------------------------------

ACCESS_ID = '0f8fad5b-d9cb-469f-a165-70867728950e'


class OlderAccessLineTests(unittest.TestCase):
    STAMP = '2026-11-24T14:56:09.123456789Z '

    def kept(self, line):
        return install.ids_only_lines('web', (self.STAMP + line).encode())

    def test_the_older_formats_access_line_is_kept_as_release_1s_is(self):
        # installer-6's input: R0's access_log_format, as gunicorn renders it
        for line in (f'[24/Nov/2026:14:56:09 +0000] 203.0.113.9 "GET /api/encounters/{ACCESS_ID} HTTP/1.1" 200 512 7ms',
                     '[24/Nov/2026:14:56:10 +0000] - "POST /login/ HTTP/1.0" 302 - 15ms',
                     '[24/Nov/2026:14:56:11 +0000] 2001:db8::1 "HEAD /health/ HTTP/1.1" 200 0 1ms',
                     f'[24/Nov/2026:14:56:12 +0000] 203.0.113.9 "GET /api/encounters/{ACCESS_ID} HTTP/1.1" 200 512 7ms '
                     f'0123456789abcdef0123456789abcdef {ACCESS_ID}'):  # release 1's, as before
            with self.subTest(line=line):
                kept, dropped = self.kept(line)
                self.assertEqual((len(kept), dropped), (1, 0))

    def test_nothing_more_than_its_fields_is_kept(self):
        for line in ('[24/Nov/2026:14:56:09 +0000] 203.0.113.9 "GET /api/encounters/?q=Jones HTTP/1.1" 200 512 7ms',
                     '[24/Nov/2026:14:56:09 +0000] 203.0.113.9 "GET /api/encounters/jones-notes HTTP/1.1" 200 512 7ms',
                     '[24/Nov/2026:14:56:09 +0000] 203.0.113.9 "GET /health/ HTTP/1.1" 200 512 7ms Dr Jones',
                     '[24/Nov/2026:14:56:09 +0000] Jones "GET /health/ HTTP/1.1" 200 512 7ms',
                     '[24/Nov/2026:14:56:09 +0000] 203.0.113.9 "GET /health/ HTTP/1.1" 200 512 7ms 0123456789abcdef0123456789abcdef',
                     '[24/Nov/2026:14:56:09 +0000] 203.0.113.9 "GET /health/ HTTP/1.1" 200 512'):
            with self.subTest(line=line):
                kept, dropped = self.kept(line)
                self.assertEqual((kept, dropped), ([], 1))

    def test_a_line_gunicorn_renders_with_the_older_revisions_own_format_is_kept(self):
        try:
            from gunicorn.config import Config
            from gunicorn.glogging import Logger
        except ImportError:
            raise unittest.SkipTest('gunicorn is not installed here')
        found = install.run(['git', '-C', str(REPO_ROOT), 'show', f'{R0_REVISION}:cpt-studio/deploy/gunicorn.conf.py'],
                            check=False)
        if found.returncode:
            raise unittest.SkipTest(f'{R0_REVISION[:12]} is not in this clone')
        namespace = {}
        exec(compile(found.stdout.decode(), 'gunicorn.conf.py', 'exec'), namespace)  # its settings: plain assignments
        config = Config()
        config.set('access_log_format', namespace['access_log_format'])
        environ = {'REQUEST_METHOD': 'GET', 'RAW_URI': f'/api/encounters/{ACCESS_ID}?view=1',
                   'PATH_INFO': f'/api/encounters/{ACCESS_ID}', 'QUERY_STRING': 'view=1', 'SERVER_PROTOCOL': 'HTTP/1.1',
                   'REMOTE_ADDR': '172.18.0.1', 'HTTP_X_FORWARDED_FOR': '203.0.113.9'}
        request = SimpleNamespace(headers=[('X-FORWARDED-FOR', '203.0.113.9')])
        response = SimpleNamespace(status='200 OK', response_length=512, sent=512,
                                   headers=[('Content-Type', 'application/json')])
        line = namespace['access_log_format'] % Logger(config).atoms(response, request, environ,
                                                                    dt.timedelta(milliseconds=7))
        self.assertNotIn('view=1', line)
        kept, dropped = self.kept(line)
        self.assertEqual((len(kept), dropped), (1, 0), line)

    def test_the_older_format_is_the_one_its_revision_configures(self):
        r0 = R0_REVISION
        found = install.run(['git', '-C', str(REPO_ROOT), 'show', f'{r0}:cpt-studio/deploy/gunicorn.conf.py'], check=False)
        if found.returncode:
            raise unittest.SkipTest(f'{r0[:12]} is not in this clone')
        self.assertIn("access_log_format = '%(t)s %({x-forwarded-for}i)s \"%(m)s %(U)s %(H)s\" %(s)s %(B)s %(M)sms'",
                      found.stdout.decode())


# --- I10: no signal stops a RAM folder's wipe half way ----------------------------------------------------------------

class SignalDuringWipeTests(TemporaryDirectoryTest):
    """installer-3's input through the real install.main(): --phase manage dispose --dispose-step plan, whose files
    act hands the RAM folder to the application's uid (give); the signal lands while the root helper's wipe starts."""

    def run_main(self, signum):
        import signal as signals
        from test_install import FakeOwnership, run_body
        shm = self.tmp / 'shm'
        shm.mkdir(mode=0o700)
        reason = self.tmp / 'reason.txt'
        reason.write_bytes(b'Ticket 4521: Dr Example asked us to remove the practice of Example Clinic.\n')
        owner, seen = FakeOwnership(), {}

        def ram_init(ram, prefix, *, owner=None):
            ram.path = shm / f'{prefix}{uuid.uuid4().hex}'
            ram.path.mkdir(mode=0o700)
            ram.owner, ram.given = owner, False

        def run_helper(body, params, *, mounts, **kwargs):
            assert mounts == [install.SHM_MOUNT], mounts
            if body is install.H_RAM_WIPE:
                seen['folder'] = shm / params['name']
                seen['before'] = sorted(path.name for path in seen['folder'].iterdir())
                expected = install.interrupt if signum != signals.SIGINT else signals.default_int_handler
                assert signals.getsignal(signum) is expected or signals.getsignal(signum) is install.held_ctrl_c, \
                    'refusing to signal this process without the handler that holds it'
                os.kill(os.getpid(), signum)  # the signal lands as the helper container starts
            return run_body(body, params, {'/host-shm': str(shm)}, fake_os=owner)

        def oneshot(image_id, command, env, **kwargs):
            if command == ['manage', 'migrate', '--check']:
                return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
            return SimpleNamespace(returncode=0, stdout=b'Plan 1 recorded: 3 rows.\n', stderr=b'')
        printed = io.StringIO()
        with mock.patch.multiple(install, installed_image=mock.Mock(return_value='sha256:' + 'c' * 64),
                                 require_db=mock.Mock(), oneshot=oneshot, inspect=mock.Mock(return_value=None),
                                 run_helper=run_helper, read_protected_env=mock.Mock(
                                     return_value=b'CPT_STUDIO_SECRET_KEY=' + b'S' * 48 + b'\n'),
                                 check_door=mock.Mock(return_value={'declaration': 'docs/d.md',
                                                                    'declaration_commit': 'd' * 40}),
                                 check_tree=mock.Mock(return_value={'mode': 'exact'})), \
                mock.patch.object(install.RamFiles, '__init__', ram_init), mock.patch('sys.stdout', printed):
            try:
                code = install.main(['--phase', 'manage', '--revision', REVISION, '--receipts',
                                     str(self.tmp / 'receipts'), '--command', 'dispose', '--dispose-step', 'plan',
                                     '--workspace-id', WORKSPACE, '--reason-file', str(reason), '--by',
                                     'Ada Lovelace'])
            except KeyboardInterrupt:
                code = 'KeyboardInterrupt'
        receipts = sorted((self.tmp / 'receipts').glob('manage-*.json'))
        record = json.loads(receipts[-1].read_text()) if receipts else None
        return code, record, seen, shm

    def test_a_sigterm_or_sighup_during_the_wipe_is_acted_on_once_the_folder_is_gone(self):
        import signal as signals
        for signum, code in ((signals.SIGTERM, 143), (signals.SIGHUP, 129)):
            with self.subTest(signal=signum.name):
                exit_code, record, seen, shm = self.run_main(signum)
                self.assertEqual(seen['before'], ['reason'])  # the reason was there when the wipe began
                self.assertFalse(seen['folder'].exists(), 'the RAM folder was left in /dev/shm')
                self.assertEqual(list(shm.iterdir()), [])
                self.assertEqual(exit_code, code)
                self.assertEqual((record['ok'], record['interrupted']), (False, signum.name))
                for path in [*shm.rglob('*'), *(shm.parent / 'receipts').rglob('*')]:  # never the input reason
                    if path.is_file():
                        self.assertNotIn(b'Dr Example', path.read_bytes())
                import shutil
                shutil.rmtree(shm.parent / 'receipts')
                shm.rmdir()
                (shm.parent / 'reason.txt').unlink()

    def test_a_ctrl_c_during_the_wipe_too(self):
        import signal as signals
        exit_code, record, seen, shm = self.run_main(signals.SIGINT)
        self.assertEqual(exit_code, 'KeyboardInterrupt')
        self.assertFalse(seen['folder'].exists(), 'the RAM folder was left in /dev/shm')
        self.assertEqual((record['ok'], record['interrupted']), (False, 'SIGINT'))
        self.assertIs(signals.getsignal(signals.SIGINT), signals.default_int_handler)  # put back as it was

    def test_the_hold_nests_and_says_nothing_when_no_signal_landed(self):
        with install.signals_deferred():
            with install.signals_deferred():
                self.assertEqual(install.SIGNALS_HELD['depth'], 2)
        self.assertEqual(install.SIGNALS_HELD, {'depth': 0, 'pending': None})
        with self.assertRaisesRegex(ValueError, 'the body'):
            with install.signals_deferred():
                raise ValueError('the body')
        self.assertEqual(install.SIGNALS_HELD, {'depth': 0, 'pending': None})


class SessionScriptImportTests(unittest.TestCase):
    def test_the_end_runs_in_this_revisions_image_with_what_it_has(self):
        from test_install_fable_scripts import REMOVED, imported
        modules = imported(install.END_EVERY_SESSION)
        self.assertEqual(sorted(module for module in modules if module.startswith(REMOVED)), [])
        self.assertIn('studio.security_events', modules)
        self.assertIn("lock_timeout = '30s'", install.END_EVERY_SESSION)


if __name__ == '__main__':
    unittest.main()
