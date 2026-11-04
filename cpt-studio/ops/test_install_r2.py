"""Offline tests of the round-2 refutation repairs of the installer (refute-r2, lenses L6 and L3; ops/install.py,
ops/INSTALL.md). No Docker, sudo, nginx, database or network: test_install's host guard refuses every one of them.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

Each class names the finding it holds. The worlds are test_install_bluegreen's BlueGreenWorld - the REAL phase_app,
switch_services, switch_upstream, publish_vhost, the undos, phase_switch_back and phase_rollback_app run against it -
with an invariant breach RECORDED instead of raised inside the fake: an undo that catches BaseException (the incoming
web's removal does) would otherwise swallow the breach, and the test would read a green that proves nothing.
"""
import datetime as dt
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host  # noqa: E402
from test_install_bluegreen import (APP_ROOT, IMAGE, NEXT, OLD, OLD_IMAGE, REVISION, WEB, WORKER,  # noqa: E402
                                    BlueGreenWorld, FakeRootFile, run_app, switch_back_args)


def setUpModule():
    guard_host()


def tearDownModule():
    release_host()


class World(BlueGreenWorld):
    """BlueGreenWorld whose I-web/I-worker breaches are recorded, with where they happened, and asserted empty by the
    test. ``after`` (1-based fake call) raises KeyboardInterrupt once that call has TAKEN EFFECT (BlueGreenWorld's own
    interrupt_at raises before it does; refute-r2 L6-1 was a Ctrl-C after systemd had taken the reload job)."""

    def __init__(self, *args, **kwargs):
        self.violations, self.after = [], None
        super().__init__(*args, **kwargs)

    def invariant(self):
        try:
            super().invariant()
        except AssertionError as error:
            self.violations.append(str(error))

    def done(self, value=None):
        value = super().done(value)
        if self.after is not None and self.calls == self.after:
            self.after = None
            self.events.append(('interrupted-after', self.events[-1]))
            raise KeyboardInterrupt()
        return value

    def serving(self):
        """The web nginx routes to: (image, port, revision), or None."""
        web = self.web_on(self.nginx_port)
        return None if web is None else (web['Image'], web['port'], web['revision'])


class ReloadActsThenRaises(World):
    """The reloads numbered in ``raising`` (1-based) take effect - systemd ran the job, nginx re-read the file - and
    then raise ``error``: a Ctrl-C while subprocess.run waited on systemctl, or run()'s 30 s timeout."""

    def __init__(self, *args, raising=(1,), error=KeyboardInterrupt, **kwargs):
        self.raising, self.error, self.reloads = set(raising), error, 0
        super().__init__(*args, **kwargs)

    def nginx_reload(self):
        self.reloads += 1
        result = super().nginx_reload()
        if self.reloads in self.raising:
            raise self.error() if isinstance(self.error, type) else self.error
        return result


class ReloadNotApplied(World):
    """`systemctl reload nginx` exits 0, and the master keeps the configuration it has (a listen on an address in use
    passes nginx -t and fails only in the master): no new worker, nginx's port unchanged."""

    def nginx_reload(self):
        self.act('reload', self.file_port())
        return self.done()


def switched_back_world(tmp, cls=World, **kwargs):
    """This revision serving on 9151 after a successful app that replaced the OLD pair (switch-back's precondition)."""
    world = cls(tmp, live=9151, serving=(REVISION, IMAGE), **kwargs)
    install.write_receipt(tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
        'replaced': {'web': {'id': 'web-old', 'image': OLD_IMAGE, 'revision': OLD},
                     'worker': {'id': 'worker-old', 'image': OLD_IMAGE, 'revision': OLD}}}})
    return world


def run_switch_back(world):
    patches = world.patches()
    for patcher in patches:
        patcher.start()
    try:
        return install.phase_switch_back(install.Context(switch_back_args(world.tmp), world.tmp)), None
    except install.InstallError as error:
        return None, error
    finally:
        for patcher in reversed(patches):
            patcher.stop()


def run_rollback_app(world):
    patches = world.patches()
    for patcher in patches:
        patcher.start()
    try:
        ctx = install.Context(SimpleNamespace(phase='rollback-app', revision=REVISION), world.tmp)
        return install.phase_rollback_app(ctx), None
    except install.InstallError as error:
        return None, error
    finally:
        for patcher in reversed(patches):
            patcher.stop()


def closes_answering(world, answers):
    """Make the world's close answer ``answers`` in turn (then nothing named)."""
    queue = list(answers)

    def close(image_id, env_bytes, since, revision, reason, kinds):
        world.act('close', image_id, tuple(kinds))
        world.closes.append({'image': image_id, 'since': since, 'revision': revision, 'reason': reason,
                             'kinds': list(kinds)})
        answer = queue.pop(0) if queue else {'closed': 0, 'kinds': [], 'hazards': {}, 'relabel': []}
        return world.done(json.loads(json.dumps(answer)))
    world.close = close


def named(hazards):
    return {'closed': 1, 'kinds': [], 'hazards': hazards, 'relabel': []}


# --- L6-1: a reload that was asked for may have been applied, whatever its call answered -------------------------------

class ReloadRaceTests(TemporaryDirectoryTest):
    def test_s3_a_ctrl_c_or_timeout_after_systemd_took_the_reload_keeps_the_site_served(self):
        timeout = install.InstallError('sudo /usr/bin/systemctl reload did not finish within 30 s.')
        for label, error in (('ctrl-c', KeyboardInterrupt), ('timeout', timeout)):
            with self.subTest(label):
                world = ReloadActsThenRaises(self.tmp, error=error)
                details, failure = run_app(world)
                self.assertIsInstance(failure, install.InstallError)
                self.assertEqual(world.violations, [])
                self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
                self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
                settle = failure.details['settle']
                self.assertTrue(settle['proven'], settle)
                # the restored file reloaded by publish_vhost, then once more by the undo, which proved where nginx
                # routes (the old revision answers the public /health/) before it drained and removed the incoming web
                self.assertEqual(world.acts('reload'), [('reload', 9151), ('reload', 9150), ('reload', 9150)])
                proven = world.events.index(('health', 9150, OLD))
                self.assertLess(proven, world.events.index(('drain', 9151)))
                self.assertLess(world.events.index(('drain', 9151)), world.events.index(('stop', NEXT, '30')))
                self.assertIn('nginx proven to run it again', str(failure))

    def test_s3_a_restore_nginx_is_not_proven_to_run_keeps_both_webs_and_parks_the_old_worker(self):
        # the forward reload, publish_vhost's restore reload and the undo's own each take effect and then raise
        world = ReloadActsThenRaises(self.tmp, raising=(1, 2, 3))
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertEqual(world.names()[NEXT], (IMAGE, 9151, True))     # never removed
        self.assertEqual(world.names()[WEB], (OLD_IMAGE, 9150, True))
        self.assertFalse(world.containers[WORKER + '-previous']['running'])
        self.assertNotIn(('drain', 9151), world.events)
        self.assertEqual(world.closes, [])
        self.assertIn('both webs were left running', str(failure))
        self.assertFalse(failure.details['settle']['proven'])

    def test_s3_an_attempted_reload_whose_new_workers_are_not_seen_yet_is_still_settled(self):
        # the forward reload moved nginx, but its new workers are not visible when the undo looks; the restore's reload
        # times out before systemd takes it: only the attempt says that nginx may route to the incoming web
        class UnseenThenRefused(World):
            def __init__(self, *args, **kwargs):
                self.reloads = 0
                super().__init__(*args, **kwargs)

            def nginx_reload(self):
                self.reloads += 1
                if self.reloads == 2:
                    self.act('reload', self.file_port())
                    raise install.InstallError('sudo /usr/bin/systemctl reload did not finish within 30 s.')
                result = super().nginx_reload()
                if self.reloads == 1:
                    self.generation -= 1  # nginx moved; its new workers are not seen yet
                    raise KeyboardInterrupt()
                return result
        world = UnseenThenRefused(self.tmp)
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertTrue(failure.details['settle']['proven'])
        self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})

    def test_s3_anyone_s_reload_while_the_file_named_the_incoming_web_is_settled_before_it_goes(self):
        # the TLS renewal hook (or a co-tenant) reloads nginx between the file's replacement and nginx -t's failure:
        # the installer asked for no reload, but nginx routes to the incoming web
        class ExternalReload(World):
            def nginx_test(self):
                answer = super().nginx_test()
                if self.file_port() == 9151 and self.nginx_port == 9150:
                    self.nginx_port, self.generation = 9151, self.generation + 1  # someone else's reload
                    self.inflight[9150] = self.inflight.get(9150, 0) + 2  # its old workers finish these
                    return {**answer, 'ok': False}
                return answer
        world = ExternalReload(self.tmp)
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
        self.assertEqual(world.acts('reload'), [('reload', 9150)])  # the undo's own: none was asked for before
        self.assertTrue(failure.details['settle']['proven'])
        self.assertLess(world.events.index(('drain', 9151)), world.events.index(('stop', NEXT, '30')))
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})

    def test_b5_a_restore_nginx_is_not_proven_to_run_keeps_both_webs_and_parks_this_worker(self):
        world = switched_back_world(self.tmp, cls=ReloadActsThenRaises, raising=(1, 2, 3))
        details, failure = run_switch_back(world)
        self.assertEqual(world.violations, [])
        self.assertTrue(world.containers[NEXT]['running'])
        self.assertTrue(world.containers[WEB]['running'])
        self.assertFalse(world.containers[WORKER + '-previous']['running'])
        self.assertNotIn(('drain', 9150), world.events)
        self.assertIn('both webs were left running', str(failure))

    def test_b5_a_ctrl_c_after_systemd_took_the_reload_resumes_this_revision_on_its_own_web(self):
        world = switched_back_world(self.tmp, cls=ReloadActsThenRaises)
        details, failure = run_switch_back(world)
        self.assertIsInstance(failure, install.InstallError)
        self.assertEqual(world.violations, [])
        self.assertEqual((world.nginx_port, world.file_port()), (9151, 9151))
        self.assertEqual(world.names(), {WEB: (IMAGE, 9151, True), WORKER: (IMAGE, None, True)})
        self.assertLess(world.events.index(('health', 9151, REVISION)), world.events.index(('drain', 9150)))
        self.assertLess(world.events.index(('drain', 9150)), world.events.index(('stop', NEXT, '30')))
        self.assertIn('nothing was switched', str(failure))

    def test_s4_a_switch_back_whose_reload_was_taken_says_which_web_serves_and_it_is_true(self):
        # S3's reload succeeds; the S4 undo's switch back reload takes effect, then raises
        world = ReloadActsThenRaises(self.tmp, raising=(2,))
        world.unhealthy.add(WORKER)
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        # publish_vhost put the new web's file back and reloaded; the undo proved nginx runs it: the new web serves
        self.assertEqual((world.nginx_port, world.file_port()), (9151, 9151))
        self.assertEqual(world.serving(), (IMAGE, 9151, REVISION))
        self.assertTrue(failure.details['settle']['proven'])
        self.assertIn('the new web keeps serving on 9151', str(failure))
        self.assertEqual(world.names()[WEB], (OLD_IMAGE, 9150, True))

    def test_s4_a_switch_back_that_cannot_be_proven_says_nginx_may_route_to_either_web(self):
        world = ReloadActsThenRaises(self.tmp, raising=(2, 3, 4))
        world.unhealthy.add(WORKER)
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertIn('nginx may route to either web', str(failure))
        self.assertNotIn('the new web keeps serving', str(failure))
        self.assertTrue(world.containers[NEXT]['running'] and world.containers[WEB]['running'])
        self.assertFalse(any(c['running'] for name, c in world.containers.items() if c['role'] == 'worker'))

    def test_publish_vhost_reloads_the_restored_file_after_an_interrupted_reload(self):
        ok = {'ok': True, 'warnings': [], 'output': 'test is successful'}
        calls, progress = [], {}

        def reload():
            calls.append('reload')
            if calls.count('reload') == 1:
                raise KeyboardInterrupt()
        ctx = install.Context(SimpleNamespace(phase='https-vhost', revision=REVISION), self.tmp)
        with mock.patch.object(install, 'nginx_test', return_value=ok), \
                mock.patch.object(install, 'nginx_reload', reload), self.assertRaises(KeyboardInterrupt):
            install.publish_vhost(ctx, lambda: calls.append('apply'), lambda: calls.append('undo'), mock.Mock(),
                                  progress=progress)
        self.assertEqual(calls, ['apply', 'reload', 'undo', 'reload'])
        self.assertEqual((progress.get('reload_attempted'), progress.get('reloaded'), progress.get('restore_reloaded')),
                         (True, None, True))

    def clear(self):
        for path in self.tmp.iterdir():
            path.unlink()

    def test_a_ctrl_c_after_any_call_took_effect_leaves_a_healthy_web_behind_both_ports(self):
        def failing(tmp):
            world = World(tmp)
            world.unhealthy.add(WORKER)
            return world
        scenarios = {'app': (World, run_app), 'app, S4 fails': (failing, run_app),
                     'switch-back': (switched_back_world, run_switch_back)}
        for label, (make, runner) in scenarios.items():
            self.clear()
            clean = make(self.tmp)
            runner(clean)
            total = clean.calls
            self.assertGreater(total, 30)
            for k in range(1, total + 1):
                self.clear()
                world = make(self.tmp)
                world.after = k
                with self.subTest(label, call=k):
                    try:
                        runner(world)
                    except KeyboardInterrupt:
                        pass  # interrupted before the phase had changed anything it undoes
                    world.invariant()
                    self.assertEqual(world.violations, [], (label, k, world.events[-6:]))


# --- L6-3: what the new web started until it stopped taking traffic is closed, and decides the hold -------------------

class Busy(World):
    """Members keep using the site: at every installer call a member action on the web nginx routes to may queue a
    stage tagged with that web's revision, and so may a request an old nginx worker still holds to a web that is not
    drained yet (BlueGreenWorld's inflight). The close closes every stage that exists when it runs. Read at the moment
    the OLD worker is started: the open stages the NEW revision's web queued (refute-r2 L6-3's measurement)."""

    def __init__(self, *args, **kwargs):
        self.stages, self.at_old_worker_start = [], None
        super().__init__(*args, **kwargs)

    def act(self, *event):
        super().act(*event)
        web = self.web_on(self.nginx_port)
        if web is not None and web['healthy'] and event[0] not in ('inspect', 'vhost-state', 'vhost-read'):
            self.stages.append([len(self.events), web['revision'], True])
        for port, held in self.inflight.items():
            other = self.web_on(port)
            if held and other is not None:
                self.stages.append([len(self.events), other['revision'], True])

    def close(self, image_id, env_bytes, since, revision, reason, kinds):
        answer = super().close(image_id, env_bytes, since, revision, reason, kinds)
        for stage in self.stages:
            stage[2] = False
        return answer

    def docker(self, *args, **kwargs):
        if args[0] == 'start' and args[1] == WORKER and self.containers.get(WORKER, {}).get('Image') == OLD_IMAGE:
            self.at_old_worker_start = [stage for stage in self.stages if stage[2] and stage[1] == REVISION]
        return super().docker(*args, **kwargs)


class SecondCloseTests(TemporaryDirectoryTest):
    def test_no_stage_the_new_web_queued_is_open_when_the_old_worker_starts(self):
        for label, setup in (('S4', lambda w: w.unhealthy.add(WORKER)),
                             ('S3', lambda w: w.fail.__setitem__(('https', 9151), install.InstallError('no')))):
            with self.subTest(label):
                world = Busy(self.tmp)
                setup(world)
                run_app(world)
                self.assertIn(('start', WORKER), world.events)
                self.assertEqual(world.at_old_worker_start, [])
                self.assertEqual(len(world.closes), 2)
                self.assertEqual(world.violations, [])

    def test_s4_a_record_the_new_web_wrote_after_the_first_close_holds_the_old_worker(self):
        for hazards, words in (({'e1': ['modifier']}, 'modifier 1 hold states the old web shows wrongly'),
                               ({'e1': ['unknown']}, 'unknown 1 hold records it would act on')):
            with self.subTest(hazards=hazards):
                world = World(self.tmp)
                world.unhealthy.add(WORKER)
                closes_answering(world, [named({}), named(hazards)])
                details, failure = run_app(world)
                self.assertEqual(world.violations, [])
                self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, False)})
                self.assertNotIn(('start', WORKER), world.events)
                closes = [index for index, event in enumerate(world.events) if event[0] == 'close']
                self.assertEqual(len(closes), 2)
                self.assertLess(world.events.index(('drain', 9151)), closes[1])
                self.assertLess(closes[1], world.events.index(('stop', NEXT, '30')))
                self.assertIn(words, str(failure))
                self.assertIn('It is held - nothing can be sent', str(failure))
                self.assertGreaterEqual(world.closes[1]['since'], world.closes[0]['since'])

    def test_s4_a_same_revision_pair_is_held_when_a_close_named_nothing_it_read(self):
        # a same-revision pair goes past the keep rule even when the close's hazards are unreadable: never read as none
        world = World(self.tmp, serving=(REVISION, IMAGE))
        world.unhealthy.add(WORKER)
        world.close_answer = {'closed': 1, 'kinds': [], 'hazards': None, 'relabel': []}
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertIn('the first close did not say which encounters it named', str(failure))
        self.assertNotIn(('start', WORKER), world.events)
        self.assertEqual(world.names(), {WEB: (IMAGE, 9150, True), WORKER: (IMAGE, None, False)})

    def test_s3_a_record_written_during_the_drain_holds_the_old_worker(self):
        world = World(self.tmp)
        world.fail[('https', 9151)] = install.InstallError('it did not serve')
        closes_answering(world, [named({}), named({'e1': ['outcome']})])
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, False)})
        self.assertIn('outcome 1 hold records the old revision would act on', str(failure))
        self.assertIn('stages_closed_after_drain', failure.details)

    def test_an_s3_failure_before_nginx_read_the_switched_file_closes_once_and_drains_nothing(self):
        world = World(self.tmp)
        world.nginx_answers = [{}, {'ok': False}]
        details, failure = run_app(world)
        self.assertEqual(len(world.closes), 1)
        self.assertNotIn(('drain', 9151), world.events)
        self.assertEqual(world.acts('reload'), [])
        self.assertIn('the vhost was put back before nginx read it', str(failure))


# --- L6-6: what only this revision's web writes is never said to have been shown by the old web ----------------------

class WebWrittenHazardTests(TemporaryDirectoryTest):
    def test_s3_a_member_answer_or_a_modifier_holds_the_old_worker_and_is_named_as_written_by_the_new_web(self):
        world = World(self.tmp)
        world.fail[('https', 9151)] = install.InstallError('a co-tenant answered differently')
        world.close_answer = named({'e1': ['member_answer'], 'e2': ['modifier']})
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, False)})
        message = str(failure)
        self.assertIn("2 encounter(s): member_answer 1, modifier 1 hold records only this revision's web writes",
                      message)
        self.assertNotIn('never stopped showing', message)
        self.assertIn('It is held - nothing can be sent', message)

    def test_a_worker_made_shown_state_is_still_named_only(self):
        world = World(self.tmp)
        world.fail[('https', 9151)] = install.InstallError('it did not serve')
        world.close_answer = named({'e1': ['participant']})
        details, failure = run_app(world)
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
        self.assertIn('1 encounter(s): participant 1 hold states an older revision shows wrongly; the old web never '
                      'stopped showing them', str(failure))

    def test_a_pair_of_this_same_revision_reads_them_and_is_not_held(self):
        world = World(self.tmp, serving=(REVISION, IMAGE))
        world.fail[('https', 9151)] = install.InstallError('it did not serve')
        world.close_answer = named({'e1': ['member_answer']})
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertIn(('start', WORKER), world.events)
        self.assertNotIn('only this revision', str(failure))

    def test_switch_back_b7_says_the_previous_web_shows_what_this_web_wrote(self):
        world = switched_back_world(self.tmp)
        closes_answering(world, [named({}), named({'e1': ['member_answer']})])
        details, failure = run_switch_back(world)
        self.assertEqual(world.violations, [])
        self.assertIn("member_answer 1 only this revision's web writes: it wrote them before it stopped taking traffic",
                      str(failure))
        self.assertFalse([name for name, c in world.containers.items() if c['role'] == 'worker' and c['running']])


# --- L6-4: the baseline is read before anything that cannot be undone ----------------------------------------------

DRIFT = ['app.quillmd.com /health/ changed']


class BaselineTests(TemporaryDirectoryTest):
    def test_switch_back_refuses_a_stale_baseline_before_anything_starts(self):
        world = switched_back_world(self.tmp)
        world.ingress_answers = [DRIFT]
        details, failure = run_switch_back(world)
        self.assertIn('app.quillmd.com /health/ changed since this install\'s preflight baseline', str(failure))
        self.assertIn('Run --phase preflight again', str(failure))
        self.assertIn('nothing was started or stopped', str(failure))
        self.assertEqual(world.acts('run', 'stop', 'rename', 'close', 'vhost', 'reload'), [])

    def test_switch_back_refuses_a_baseline_that_drifted_before_b4_closing_nothing(self):
        world = switched_back_world(self.tmp)
        world.ingress_answers = [[], DRIFT]
        details, failure = run_switch_back(world)
        self.assertEqual(world.closes, [])
        self.assertEqual(world.acts('vhost', 'reload'), [])
        self.assertEqual(world.names(), {WEB: (IMAGE, 9151, True), WORKER: (IMAGE, None, True)})
        self.assertIn('nothing was closed or switched', str(failure))
        self.assertIn('Nothing was closed.', str(failure))
        self.assertEqual(failure.details['failed_at'], 'B4')

    def test_switch_back_reads_the_hazards_again_before_closing(self):
        world = switched_back_world(self.tmp)
        answers = iter([{}, {'e1': ['member_answer']}])
        world.undo_hazards = lambda image_id, env_bytes, revision: (world.act('hazards', image_id),
                                                                    world.done(next(answers)))[1]
        details, failure = run_switch_back(world)
        self.assertEqual(world.closes, [])
        self.assertIn('before anything was closed, 1 encounter(s): member_answer 1', str(failure))
        self.assertEqual(world.names(), {WEB: (IMAGE, 9151, True), WORKER: (IMAGE, None, True)})

    def test_app_refuses_a_stale_baseline_before_s1(self):
        world = World(self.tmp)
        world.ingress_answers = [DRIFT]
        details, failure = run_app(world)
        self.assertIn('nothing was started or stopped', str(failure))
        self.assertEqual(world.acts('run', 'stop', 'rename', 'vhost', 'reload', 'close'), [])

    def test_app_a_baseline_that_drifts_before_s3_changes_no_vhost_and_closes_nothing(self):
        world = World(self.tmp)
        world.ingress_answers = [[], DRIFT]
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertEqual(world.acts('vhost', 'reload', 'close', 'drain'), [])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
        self.assertIn('the upstream was not switched', str(failure))
        self.assertIn('the vhost was not changed', str(failure))


# --- L6-7: a same-revision switch is verified to reach the incoming web ---------------------------------------------

class SameRevisionTests(TemporaryDirectoryTest):
    def test_a_same_revision_reload_nginx_did_not_apply_never_stops_the_serving_web(self):
        world = ReloadNotApplied(self.tmp, serving=(REVISION, IMAGE))
        details, failure = run_app(world)
        self.assertIsInstance(failure, install.InstallError)
        self.assertEqual(world.violations, [])
        self.assertEqual(world.serving(), (IMAGE, 9150, REVISION))
        self.assertNotIn(('stop', WEB, '30'), world.events)
        self.assertNotIn(('drain', 9150), world.events)
        self.assertIn('nginx was not seen loading the switched vhost', str(failure))
        self.assertIn('both webs were left running', str(failure))

    def test_a_same_revision_switch_nginx_applied_passes(self):
        world = World(self.tmp, serving=(REVISION, IMAGE))
        details, failure = run_app(world)
        self.assertIsNone(failure)
        self.assertEqual(world.serving(), (IMAGE, 9151, REVISION))
        self.assertIs(details['switch']['nginx_applied'], True)

    def test_another_revision_with_the_same_fault_is_caught_by_health_and_undone(self):
        world = ReloadNotApplied(self.tmp)
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
        self.assertIn('did not serve revision aaaaaaaaaaaa', str(failure))

    def proc(self, workers, master=100, extra=()):
        root = self.tmp / f'proc-{len(list(self.tmp.iterdir()))}'
        root.mkdir()
        (root / str(master)).mkdir()
        (root / str(master) / 'cmdline').write_bytes(b'nginx: master process /usr/sbin/nginx')
        (root / str(master) / 'stat').write_text(f'{master} (nginx) S 1 {master}\n')
        for pid, title in [(pid, b'nginx: worker process') for pid in workers] + list(extra):
            (root / str(pid)).mkdir()
            (root / str(pid) / 'cmdline').write_bytes(title)
            (root / str(pid) / 'stat').write_text(f'{pid} (nginx) S {master} {pid}\n')
        pid_file = root / 'nginx.pid'
        pid_file.write_text(f'{master}\n')
        return root, pid_file

    def test_the_generation_is_the_master_and_its_workers_not_shutting_down(self):
        root, pid_file = self.proc([101, 102], extra=[(103, b'nginx: worker process is shutting down'),
                                                      (104, b'nginx: cache manager process')])
        self.assertEqual(install.nginx_generation(root, pid_file), (100, frozenset({101, 102})))
        self.assertIsNone(install.nginx_generation(root, root / 'missing.pid'))
        empty, empty_pid = self.proc([])
        self.assertIsNone(install.nginx_generation(empty, empty_pid))
        before = (100, frozenset({101, 102}))
        self.assertIs(install.nginx_moved(before, (100, frozenset({101, 102}))), False)
        self.assertIs(install.nginx_moved(before, (100, frozenset({105, 106}))), True)
        self.assertIs(install.nginx_moved(before, (200, frozenset({101}))), True)
        self.assertIsNone(install.nginx_moved(None, before))
        self.assertIsNone(install.nginx_moved(before, None))

    def test_nginx_applied_polls_and_says_cannot_tell(self):
        readings = iter([(100, frozenset({1})), (100, frozenset({1})), (100, frozenset({7}))])
        with mock.patch.object(install, 'nginx_generation', lambda: next(readings)), \
                mock.patch.multiple(install, RELOAD_SEEN_ATTEMPTS=3, RELOAD_SEEN_INTERVAL=0):
            self.assertIs(install.nginx_applied((100, frozenset({1}))), True)
        with mock.patch.object(install, 'nginx_generation', return_value=(100, frozenset({1}))), \
                mock.patch.multiple(install, RELOAD_SEEN_ATTEMPTS=2, RELOAD_SEEN_INTERVAL=0):
            self.assertIs(install.nginx_applied((100, frozenset({1}))), False)
        with mock.patch.object(install, 'nginx_generation', return_value=None), \
                mock.patch.multiple(install, RELOAD_SEEN_ATTEMPTS=2, RELOAD_SEEN_INTERVAL=0):
            self.assertIsNone(install.nginx_applied((100, frozenset({1}))))
        self.assertIsNone(install.nginx_applied(None))


# --- L6-5: rollback-app in the S4 'keep' layout acts on the right containers, with this revision's image ------------

class KeepLayoutRollbackTests(TemporaryDirectoryTest):
    def keep(self):
        """The REAL phase_app leaves the S4 keep layout: its new worker never ready, its close naming a shown state."""
        world = World(self.tmp)
        world.unhealthy.add(WORKER)
        world.close_answer = named({'e1': ['member_answer']})
        details, failure = run_app(world)
        self.assertIn('the new web keeps serving on 9151', str(failure))
        self.assertEqual(world.names(), {NEXT: (IMAGE, 9151, True), WEB: (OLD_IMAGE, 9150, True),
                                         WORKER: (IMAGE, None, False), WORKER + '-previous': (OLD_IMAGE, None, False)})
        world.unhealthy.discard(WORKER)
        world.close_answer = named({})
        world.inflight = {}
        world.events.clear()
        world.closes.clear()
        return world

    def test_it_switches_back_to_the_old_web_reading_and_closing_with_this_revisions_image(self):
        world = self.keep()
        details, failure = run_rollback_app(world)
        self.assertIsNone(failure, failure and str(failure))
        self.assertEqual(world.violations, [])
        self.assertEqual(world.acts('hazards'), [('hazards', IMAGE)])
        self.assertEqual([close['image'] for close in world.closes], [IMAGE, IMAGE])
        self.assertEqual(world.closes[0]['since'], dt.datetime(2026, 11, 3, 10, 3, tzinfo=dt.timezone.utc))  # -next's
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
        self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
        self.assertLess(world.events.index(('reload', 9150)), world.events.index(('drain', 9151)))
        self.assertLess(world.events.index(('drain', 9151)), world.events.index(('stop', NEXT, '30')))
        self.assertIn('switched back to bbbbbbbbbbbb on 9150', details['summary'])
        self.assertEqual(details['outcome'], 'switched')

    def test_it_refuses_while_a_record_is_named_changing_nothing(self):
        world = self.keep()
        world.hazards_answer = {'e1': ['modifier']}
        before = world.names()
        details, failure = run_rollback_app(world)
        self.assertIn('1 encounter(s): modifier 1', str(failure))
        self.assertIn('nothing was stopped or removed', str(failure))
        self.assertEqual(world.names(), before)
        self.assertEqual(world.acts('stop', 'rm', 'close', 'vhost', 'reload'), [])
        self.assertEqual(world.acts('hazards'), [('hazards', IMAGE)])

    def test_a_close_naming_a_record_leaves_the_layout_as_it_was(self):
        world = self.keep()
        world.close_answer = named({'e2': ['unknown']})
        before = world.names()
        details, failure = run_rollback_app(world)
        self.assertIn('unknown 1 hold records an older revision would act on', str(failure))
        self.assertIn('the new web keeps serving on 9151', str(failure))
        self.assertEqual(world.names(), before)
        self.assertEqual(world.acts('vhost', 'reload', 'rm'), [])

    def test_any_other_layout_with_an_incoming_web_is_refused(self):
        changes = {
            'the old web stopped': lambda w: w.containers[WEB].update(running=False),
            'the new worker running': lambda w: w.containers[WORKER].update(running=True),
            'the vhost naming the old web': lambda w: setattr(w, 'vhost_text', w.confs[9150]['https']),
            'a parked web too': lambda w: w.add(WEB + '-previous', 'web', OLD_IMAGE, OLD, port=9150, running=False),
            'the incoming web another revision': lambda w: w.containers[NEXT].update(revision=OLD),
        }
        for label, change in changes.items():
            with self.subTest(label):
                world = self.keep()
                change(world)
                world.checking = False
                before = world.names()
                details, failure = run_rollback_app(world)
                self.assertIn('rollback-app cannot tell which web serves', str(failure))
                self.assertEqual(world.names(), before)
                self.assertEqual(world.acts('stop', 'rm', 'close', 'hazards'), [])

    def test_a_web_and_worker_of_different_images_are_refused(self):
        world = World(self.tmp)
        world.checking = False
        world.containers[WORKER].update(Image=IMAGE, revision=REVISION)
        details, failure = run_rollback_app(world)
        self.assertIn('run different images, so they are not one pair', str(failure))
        self.assertEqual(world.acts('stop', 'rm', 'close', 'hazards'), [])


# --- L6-8: the migration gate reads an index's class and condition ---------------------------------------------------

UNIQUE_MIGRATION = '''import studio.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('studio', '0012_cux_worker_beat')]
    operations = [
{operations}
    ]
'''


def gate(*operations):
    return install.migration_verdict(UNIQUE_MIGRATION.format(operations='\n'.join(f'        {op},'
                                                                                   for op in operations)))


class MigrationGateTests(unittest.TestCase):
    NEW_COLUMN = "migrations.AddField(model_name='decision', name='key', field=models.UUIDField(null=True))"

    def test_a_unique_index_on_an_existing_table_is_refused_unless_partial_over_a_new_nullable_column(self):
        refused = {
            'not partial': ["migrations.AddIndex(model_name='decision', index=studio.models.UniqueIndex("
                            "fields=['proposal'], name='one'))"],
            'partial over a column older revisions write': [
                "migrations.AddIndex(model_name='decision', index=studio.models.UniqueIndex(fields=['proposal'], "
                "condition=models.Q(action='approve'), name='one'))"],
            'partial over a new column the index does not hold': [
                self.NEW_COLUMN, "migrations.AddIndex(model_name='decision', index=studio.models.UniqueIndex("
                                 "fields=['proposal'], condition=models.Q(key__isnull=False), name='one'))"],
            'partial over an existing column': [
                "migrations.AddIndex(model_name='decision', index=studio.models.UniqueIndex(fields=['note'], "
                "condition=models.Q(note__isnull=False), name='one'))"],
            'a new column given a database default': [
                self.NEW_COLUMN, "migrations.RunSQL(sql=[\"ALTER TABLE studio_decision ALTER COLUMN key SET DEFAULT "
                                 "gen_random_uuid()\"])",
                "migrations.AddIndex(model_name='decision', index=studio.models.UniqueIndex(fields=['key'], "
                "condition=models.Q(key__isnull=False), name='one'))"],
            'a class the check does not read': [
                "migrations.AddIndex(model_name='decision', index=studio.models.OtherIndex(fields=['proposal'], "
                "name='one'))"],
            'a unique index whose arguments are not read': [
                self.NEW_COLUMN, "migrations.AddIndex(model_name='decision', index=studio.models.UniqueIndex("
                                 "['proposal', 'key'], condition=models.Q(key__isnull=False), name='one'))"],
        }
        for label, operations in refused.items():
            with self.subTest(label):
                found = gate(*operations)
                self.assertFalse(found['safe'], found)
        self.assertEqual(gate(*refused['not partial'])['why'], [
            "decision: a unique index on an existing table that is not partial over a column this migration adds as "
            "nullable, which can refuse an older pair's rows"])
        # the same rule written as a constraint, refused as before
        self.assertFalse(gate("migrations.AddConstraint(model_name='decision', constraint=models.UniqueConstraint("
                              "fields=['proposal'], name='one'))")['safe'])

    def test_the_safe_index_forms(self):
        accepted = {
            "Django's own index": ["migrations.AddIndex(model_name='decision', index=models.Index(fields=['proposal'], "
                                   "name='i'))"],
            "Django's own partial index": ["migrations.AddIndex(model_name='decision', index=models.Index(fields="
                                           "['proposal'], condition=models.Q(action='approve'), name='i'))"],
            'a unique index partial over a new nullable column (keyword form)': [
                self.NEW_COLUMN, "migrations.AddIndex(model_name='decision', index=studio.models.UniqueIndex(fields="
                                 "['proposal', 'key'], condition=models.Q(key__isnull=False), name='one'))"],
            'a unique index on a table this migration creates': [
                "migrations.CreateModel(name='Thing', fields=[('id', models.BigAutoField(primary_key=True))])",
                "migrations.AddIndex(model_name='thing', index=studio.models.UniqueIndex(fields=['id'], name='u'))"],
        }
        for label, operations in accepted.items():
            with self.subTest(label):
                found = gate(*operations)
                self.assertTrue(found['safe'], found)

    def test_0011_as_committed_still_passes_and_says_why(self):
        source = (APP_ROOT / 'studio' / 'migrations' / '0011_cux_flow.py').read_text(encoding='utf-8')
        found = install.migration_verdict(source)
        self.assertTrue(found['safe'], found)
        self.assertIn('encounter: a unique index only over rows whose client_key is set, a column this migration adds '
                      'as nullable: an older pair leaves it NULL, so none of its writes is refused', found['why'])
        # control: the same index with its condition taken away is refused
        anchor = "condition=models.Q(('client_key__isnull', False)), "
        self.assertEqual(source.count(anchor), 1)
        self.assertFalse(install.migration_verdict(source.replace(anchor, ''))['safe'])
        self.assertTrue(all(verdict['safe'] for verdict in
                            install.migration_safety(APP_ROOT / 'studio' / 'migrations').values()))


# --- L6-2: the operators phase checks migrations first and says who grants -------------------------------------------

class OperatorsR2Tests(TemporaryDirectoryTest):
    def test_the_phase_refuses_before_creating_anything_while_migrations_are_pending(self):
        etc, home = self.tmp / 'etc', self.tmp / 'home'
        etc.mkdir(mode=0o700)
        home.mkdir(mode=0o700)
        os.chmod(home, 0o700)
        root, commands = FakeRootFile(etc), []

        def oneshot(image_id, command, env, **kwargs):
            commands.append(command)
            return SimpleNamespace(returncode=1, stdout=b'', stderr=b'')
        ctx = install.Context(SimpleNamespace(phase='operators', revision=REVISION, receipts=str(self.tmp),
                                              reset_passwords=None), self.tmp)
        with mock.patch.multiple(install, installed_image=mock.Mock(return_value=IMAGE), require_db=mock.Mock(),
                                 read_protected_env=mock.Mock(return_value=b''), root_file=root,
                                 app_script=mock.Mock(side_effect=AssertionError('an account was created')),
                                 oneshot=oneshot, OPS_AGENT_CREDENTIALS=home / 'ops-agent-credentials.json'), \
                self.assertRaisesRegex(install.InstallError, 'run --phase app first. No account or file was created'):
            install.phase_operators(ctx)
        self.assertEqual(commands, [['manage', 'migrate', '--check']])
        self.assertEqual((root.calls, list(etc.iterdir()), list(home.iterdir())), ([], [], []))

    def test_who_grants_is_named_even_where_the_login_cannot_be_looked_up(self):
        self.assertTrue(install.operator_granted_by().startswith('ops/install.py --phase operators ('))
        with mock.patch.object(install.getpass, 'getuser', side_effect=KeyError('getpwuid(): uid not found: 1000')):
            self.assertEqual(install.operator_granted_by(), f'ops/install.py --phase operators (uid {os.getuid()})')
        self.assertLessEqual(len(install.operator_granted_by()), 120)


# --- what INSTALL.md says about the repairs ---------------------------------------------------------------------------

class InstallDocR2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.said = ' '.join((APP_ROOT / 'ops' / 'INSTALL.md').read_text(encoding='utf-8').split())

    def says(self, phrase):
        self.assertIn(phrase, self.said, f'INSTALL.md does not say: {phrase}')

    def test_the_repairs_are_documented(self):
        for phrase in ('Run `preflight` again right before `switch-back`',
                       'a reload that was asked for is treated as applied, whatever its call answered',
                       'In the S4 keep layout `rollback-app` acts on the right containers',
                       'only this revision\'s web writes',
                       'a unique index (`studio.models.UniqueIndex`) only when it is partial over rows whose column',
                       'nginx must also be seen loading the switched file',
                       'closed again once it has stopped taking traffic'):
            self.says(phrase)


if __name__ == '__main__':
    unittest.main()
