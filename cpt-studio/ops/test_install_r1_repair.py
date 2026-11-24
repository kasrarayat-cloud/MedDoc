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
      `--regrant <username>` (optionally in backticks), whitespace-trimmed.
  I4  installer-1: every manage step refuses an argument it does not pass to its command (dispose execute's
      --workspace-id and --encounter-id), and --address is refused outside manage.
  I5  installer-2: the database's swap-off decision counts memory.swap.peak (memory peak plus swap peak), and skips the
      change when the swap peak cannot be read.

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

    def test_a_line_of_its_own_names_it_bare_or_in_backticks_whitespace_trimmed(self):
        for text in ('--regrant ali\n', '`--regrant ali`\n', '  --regrant ali\t\n', 'x\r\n`--regrant ali`\r\ny\r\n',
                     ALICE_SENTENCE + '\n`--regrant ali`\n', '--regrant ali'):
            with self.subTest(text=text):
                self.assertIs(self.names(text, '--regrant ali'), True)
        self.assertIs(self.names('`--regrant alice`\n', '--regrant alice'), True)

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

    def test_a_line_of_its_own_grants_it_again(self):
        details, error, world = self.run_grant(ALICE_SENTENCE + '\n`--regrant ali`\n')
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
STEP_BASE = {'close': ('workspace_id', 'reason_file'), 'plan': ('workspace_id',),
             'execute': ('plan_id', 'approved_by', 'reason_file'), 'ledger': (),
             'replay-ledger': ('ledger_file', 'reason_file')}


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
        combinations = {'close': [()], 'plan': [(), ('encounter_id',), ('reason_file',)],
                        'execute': [()], 'ledger': [(), ('reason_file',)],
                        'replay-ledger': [(), ('execute', 'approved_by')]}
        for step, extras in combinations.items():
            for extra in extras:
                names = (*STEP_BASE[step], *extra)
                with self.subTest(step=step, names=names):
                    args, refusal = self.parse(self.argv(step, names))
                    self.assertIsNotNone(args, refusal)
                    ctx = SimpleNamespace(args=args, door={'declaration': 'docs/d.md', 'declaration_commit': 'd' * 40})
                    argv = install.manage_argv(ctx, args, install.MANAGE_COMMANDS['dispose'])
                    for name in names:
                        self.assertIn(ARGUMENT_TRACES[name], argv, f'{name} was dropped')

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


class SessionScriptImportTests(unittest.TestCase):
    def test_the_end_runs_in_this_revisions_image_with_what_it_has(self):
        from test_install_fable_scripts import REMOVED, imported
        modules = imported(install.END_EVERY_SESSION)
        self.assertEqual(sorted(module for module in modules if module.startswith(REMOVED)), [])
        self.assertIn('studio.security_events', modules)
        self.assertIn("lock_timeout = '30s'", install.END_EVERY_SESSION)


if __name__ == '__main__':
    unittest.main()
