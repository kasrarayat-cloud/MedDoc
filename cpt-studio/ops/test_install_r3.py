"""Offline tests of the round-3 refutation repairs of the installer (refute-r3, lens D; ops/install.py, ops/INSTALL.md).
No Docker, sudo, nginx or network: test_install's host guard refuses every one of them. The one in-image test runs the
close on a disposable PostgreSQL only when the CPT_STUDIO_* variables name one (test_install_harness2's DatabaseTest),
and is skipped, never passed, without one.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

Each class names the finding it holds. The worlds are test_install_r2's - test_install_bluegreen's BlueGreenWorld, in
which the REAL phase_app, switch_services, switch_upstream, publish_vhost, settle_vhost, the undos, phase_switch_back
and phase_rollback_app run - with an invariant breach RECORDED instead of raised inside the fake.

- D-3: an S3 undo that stopped half way closed nothing, and the recovery note then had the old worker started by hand
  over what the new web had queued. rollback-app now finishes that undo in its layout (the vhost naming the old web,
  this revision's incoming web beside it): nginx proven to run the vhost, the incoming web drained and stopped,
  everything it could have queued since it was created closed, the states put back, the old worker put back - before
  any older worker runs. A way back whose stop, close or put-back does not finish leaves that same layout.
- D-6: the S3 and S4 undos' last close came before the incoming web stopped; a request still held to it after a drain
  that ended bounded_out queued a stage nothing closed. The stop now comes first.
- D-2: a member's answer or a chosen modifier written BEFORE the switch held the old worker, with a receipt saying the
  new web wrote it while it served; only those written since the window began hold it now, the receipt says when, and
  an undo puts the old worker back as it was.
- D-1: rollback-app in the S4 keep layout refused on a stale preflight baseline and sent the operator to preflight,
  which refuses while a -next exists; it now reads its own baseline.
- D-4, D-5: receipts say what happened - a -next left behind fails rollback-app, a close that was started is never
  reported as having closed nothing.
- D-7: the migration gate refuses a unique column added to an existing table that an older pair's inserts fill with
  one value.
"""
import contextlib
import datetime as dt
import io
import json
import os
import socket
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host  # noqa: E402
from test_install_bluegreen import (APP_ROOT, IMAGE, KINDS_OLD, NEXT, OLD, OLD_IMAGE, REVISION, WEB,  # noqa: E402
                                    WORKER, run_app)
from test_install_r2 import (Busy, World, closes_answering, gate, named, run_rollback_app,  # noqa: E402
                             run_switch_back, switched_back_world)

REAL_INGRESS_CHECKS = install.ingress_checks
REAL_OWN_BASELINE = getattr(install, 'own_baseline', None)
CREATED_NEXT = dt.datetime(2026, 11, 3, 10, 3, tzinfo=dt.timezone.utc)  # BlueGreenWorld's third container: the -next


def setUpModule():
    guard_host()


def tearDownModule():
    try:
        harness2 = sys.modules.get('test_install_harness2')
        if harness2 is not None and 'connection' in harness2._DATABASE:  # this module's database test made it
            connection = harness2._DATABASE.pop('connection')
            connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)
    finally:
        release_host()


def told(hazards, written):
    """A close's answer that names ``hazards`` and says which member answers or modifiers were written since its
    'since' (CLOSE_STAGES' 'written_since')."""
    return {'closed': 1, 'kinds': [], 'hazards': hazards, 'relabel': [], 'written_since': written}


def s3_fails(world):
    world.fail[('https', 9151)] = install.InstallError('app.quillmd.com /health/ changed')


def s4_fails(world):
    world.unhealthy.add(WORKER)


def running_workers(world):
    return [name for name, c in world.containers.items() if c['role'] == 'worker' and c['running']]


def changes(world, mark):
    return [event for event in world.events[mark:] if event[0] in (
        'run', 'stop', 'rename', 'rm', 'start', 'close', 'vhost', 'reload', 'drain', 'put_back')]


class Racing(Busy):
    """Busy (members keep queuing stages), with the reloads numbered in ``raising`` (1-based) taking effect and then
    raising KeyboardInterrupt - a Ctrl-C while systemctl ran, or the 30 s timeout (refute-r3 D-3's input: the forward
    reload, publish_vhost's restore reload and settle's own)."""

    def __init__(self, *args, raising=(1, 2, 3), **kwargs):
        self.raising, self.reloads = set(raising), 0
        super().__init__(*args, **kwargs)

    def nginx_reload(self):
        self.reloads += 1
        result = super().nginx_reload()
        if self.reloads in self.raising:
            raise KeyboardInterrupt()
        return result


class Bounded(Busy):
    """Busy, with the incoming web's drain ending bounded_out at 600 s while an old nginx worker still holds one request
    to it (Known limits 1, refute-r3 D-6's input): it queues stages until the incoming web is stopped."""

    def drain_web(self, port):
        self.act('drain', port)
        assert port != self.nginx_port, f'drained {port} while nginx still routes to it'
        self.inflight[port] = max(self.inflight.get(port, 0), 1)
        return self.done({'port': port, 'seconds': 600.0, 'samples': 600, 'bounded_out': True,
                          'last': {'connections': 1, 'shutting_down': 1}, 'connections': 1, 'shutting_down': 1,
                          'unreadable': 0, 'nginx_unseen': 0})

    def docker(self, *args, **kwargs):
        if args[0] == 'stop' and args[-1] == NEXT and NEXT in self.containers:
            self.inflight[self.containers[NEXT]['port']] = 0  # its graceful stop ends what it holds (503 after)
        return super().docker(*args, **kwargs)


def keep_world(tmp, cls=World):
    """The REAL phase_app leaves the S4 keep layout (its new worker never ready, its close naming a shown state written
    since the switch began); the record is then cleared on this revision's web."""
    world = cls(tmp)
    world.unhealthy.add(WORKER)
    world.close_answer = told({'e1': ['member_answer']}, {'e1': ['member_answer']})
    details, failure = run_app(world)
    assert 'the new web keeps serving on 9151' in str(failure), str(failure)
    assert world.names() == {NEXT: (IMAGE, 9151, True), WEB: (OLD_IMAGE, 9150, True), WORKER: (IMAGE, None, False),
                             WORKER + '-previous': (OLD_IMAGE, None, False)}, world.names()
    world.unhealthy.discard(WORKER)
    world.close_answer = named({})
    world.inflight = {}
    world.events.clear()
    world.closes.clear()
    return world


def halfway_world(tmp, cls=Racing):
    """The REAL phase_app's S3 undo stops half way (refute-r3 D-3's input): the forward reload, publish_vhost's restore
    reload and settle's own each take effect, then raise; members used the new web while nginx routed to it."""
    world = cls(tmp)
    details, failure = run_app(world)
    assert 'both webs were left running' in str(failure), str(failure)
    world.raising = set()  # nginx answers again
    world.halfway_failure = failure
    return world


def sweep(test, make, runner):
    """A Ctrl-C after (World.after) and before (BlueGreenWorld.interrupt_at) every fake call of ``runner`` in a world
    ``make`` builds: it never ends in a success, every run keeps a healthy web behind the port nginx routes to, and no
    two workers run (refute-r3 D-4: three of them had ended rollback-app as a success)."""
    clean = make()
    base = clean.calls
    details, error = runner(clean)
    test.assertIsNone(error, error and str(error))
    total = clean.calls - base
    test.assertGreater(total, 20)
    fired_runs = 0
    for mode in ('after', 'before'):
        for k in range(1, total + 1):
            world = make()
            if mode == 'after':
                world.after = world.calls + k
            else:
                world.interrupt_at = world.calls + k
            with test.subTest(mode=mode, call=k):
                try:
                    details, error = runner(world)
                except KeyboardInterrupt:
                    details, error = None, 'the interrupt escaped before anything acted'
                world.invariant()
                test.assertEqual(world.violations, [], world.events[-6:])
                test.assertLessEqual(len(running_workers(world)), 1)
                fired = any(event[0] in ('interrupted', 'interrupted-after') for event in world.events)
                if fired:  # (the fake recorder's calls never reach the interrupt: nothing to judge there)
                    fired_runs += 1
                    test.assertIsNone(details, f'a Ctrl-C at call {k} ({mode}) ended the phase as a success')
                    test.assertIsNotNone(error)
    test.assertGreater(fired_runs, total)


# --- D-3: what an S3 undo that stopped half way leaves is closed before any older worker runs -------------------------

class HalfWayRecoveryTests(TemporaryDirectoryTest):
    def test_the_half_way_receipt_never_sends_the_operator_to_start_the_old_worker(self):
        world = halfway_world(self.tmp)
        message = str(world.halfway_failure)
        self.assertEqual(world.closes, [])  # nothing can be closed while nginx may still route to the incoming web
        self.assertIn("run this revision's --phase rollback-app", message)
        self.assertIn('Never start the old worker by hand', message)
        self.assertTrue([stage for stage in world.stages if stage[2] and stage[1] == REVISION])  # what it queued

    def test_rollback_app_finishes_the_undo_closing_everything_the_new_web_queued_before_the_old_worker_runs(self):
        world = halfway_world(self.tmp)
        mark = len(world.events)
        details, error = run_rollback_app(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.violations, [])
        self.assertEqual(world.at_old_worker_start, [])  # refute-r3 D-3: the note had left 19 of them open
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
        self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
        events = world.events[mark:]
        # nginx proven first (reloaded, its new workers seen, the old revision answering), then the incoming web
        # drained and stopped, then the close in this revision's image with the old worker's kinds, then the removal
        order = [events.index(event) for event in (
            ('reload', 9150), ('health', 9150, OLD), ('drain', 9151), ('stop', NEXT, '30'),
            ('close', IMAGE, tuple(KINDS_OLD)), ('put_back', OLD_IMAGE), ('rm', NEXT),
            ('rename', WORKER + '-previous', WORKER), ('start', WORKER))]
        self.assertEqual(order, sorted(order))
        self.assertEqual([close['since'] for close in world.closes], [CREATED_NEXT])  # since the -next was created
        self.assertEqual(world.closes[0]['image'], IMAGE)
        self.assertEqual(details['outcome'], 'switched')
        self.assertTrue(details['settle']['proven'])
        self.assertIn(f'went back to {OLD[:12]} on 9150 (the back layout)', details['summary'])
        self.assertIn(f'removed {NEXT} (this revision\'s web)', details['summary'])

    def test_until_nginx_is_proven_to_run_the_vhost_nothing_is_stopped_closed_or_removed(self):
        world = halfway_world(self.tmp)
        world.raising = {4}  # settle's reload takes effect and raises again
        before, mark = world.names(), len(world.events)
        details, error = run_rollback_app(world)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('nginx was not proven to run that vhost', str(error))
        self.assertIn('never start the old worker by hand', str(error))
        self.assertEqual(world.names(), before)
        self.assertEqual([event for event in changes(world, mark) if event[0] != 'reload'], [])
        self.assertEqual(world.violations, [])

    def test_a_record_the_close_names_holds_the_old_worker_and_says_why(self):
        cases = (('an outcome', {'e1': ['outcome']}, {}, 'outcome 1 hold records the old revision would act on'),
                 ('an answer written since', {'e1': ['member_answer']}, {'e1': ['member_answer']},
                  'member_answer 1 hold records only a revision since the core repair writes'),
                 ('an answer written before', {'e1': ['member_answer']}, {},
                  'which rollback-app holds too: it cannot tell whether the old worker ran beside them'))
        for label, hazards, written, words in cases:
            with self.subTest(label):
                world = halfway_world(self.tmp)
                world.close_answer = told(hazards, written)
                mark = len(world.events)
                details, error = run_rollback_app(world)
                self.assertIsInstance(error, install.InstallError)
                self.assertEqual(world.violations, [])
                self.assertIn(words, str(error))
                self.assertIn('It is held - nothing can be sent', str(error))
                self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, False)})
                self.assertNotIn(('start', WORKER), world.events[mark:])
                for path in self.tmp.iterdir():
                    path.unlink()

    def test_a_close_that_does_not_finish_leaves_the_layout_for_another_run(self):
        world = halfway_world(self.tmp)
        world.fail[('close',)] = install.InstallError('Closing the stages revision aaaaaaaaaaaa left open failed.')
        details, error = run_rollback_app(world)
        self.assertIn('did not finish', str(error))
        self.assertIn(NEXT, world.containers)
        self.assertFalse(world.containers[NEXT]['running'])  # stopped before the close: it queues nothing more
        self.assertFalse(world.containers[WORKER + '-previous']['running'])
        details, error = run_rollback_app(world)  # the rerun finds the same layout and finishes it
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.at_old_worker_start, [])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})

    def test_a_ctrl_c_at_any_call_of_it_never_ends_in_a_success(self):
        def make():
            for path in self.tmp.iterdir():
                path.unlink()
            return halfway_world(self.tmp, cls=type('RacingWorld', (Racing,), {}))
        sweep(self, make, run_rollback_app)

    def test_the_killed_outright_case_goes_back_through_rollback_app_too(self):
        # an installer killed inside S3, the vhost bytes then put back by hand (the Recovery note): no receipt, no undo
        world = halfway_world(self.tmp)
        self.assertEqual((world.file_port(), world.containers[NEXT]['running']), (9150, True))
        details, error = run_rollback_app(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.at_old_worker_start, [])


# --- D-6: the last close of every way back comes after the incoming web has stopped ----------------------------------

class StopBeforeTheLastCloseTests(TemporaryDirectoryTest):
    def clear(self):
        for path in self.tmp.iterdir():
            path.unlink()

    def test_after_a_bounded_drain_no_stage_the_new_web_queued_is_open_when_the_old_worker_starts(self):
        for label, setup in (('S3', s3_fails), ('S4', s4_fails)):
            with self.subTest(label):
                self.clear()
                world = Bounded(self.tmp)
                setup(world)
                details, failure = run_app(world)
                self.assertEqual(world.violations, [])
                self.assertIn(('start', WORKER), world.events)
                self.assertEqual(world.at_old_worker_start, [])  # refute-r3 D-6: S3 left 2, S4 left 5
                closes = [index for index, event in enumerate(world.events) if event[0] == 'close']
                self.assertLess(world.events.index(('stop', NEXT, '30')), closes[-1])
                self.assertLess(closes[-1], world.events.index(('rm', NEXT)))
                self.assertEqual((failure.details.get('incoming_drain') or {}).get('bounded_out'), True)

    def test_switch_back_already_stopped_its_web_before_its_last_close(self):
        # the control the finding named: B6 stops this revision's web, B7 closes
        world = switched_back_world(self.tmp, cls=Bounded)
        details, failure = run_switch_back(world)
        self.assertIsNone(failure, failure and str(failure))
        closes = [index for index, event in enumerate(world.events) if event[0] == 'close']
        self.assertLess(world.events.index(('stop', WEB, '30')), closes[-1])

    def test_an_incoming_web_that_cannot_be_stopped_leaves_the_old_worker_parked_for_rollback_app(self):
        for label, setup in (('S3', s3_fails), ('S4', s4_fails)):
            with self.subTest(label):
                self.clear()
                world = Bounded(self.tmp)
                setup(world)
                world.fail[('stop', NEXT)] = install.InstallError('docker stop cpt-studio-web-next failed with exit 1.')
                details, failure = run_app(world)
                self.assertEqual(world.violations, [])
                self.assertNotIn(('start', WORKER), world.events)
                self.assertTrue(world.containers[NEXT]['running'])
                self.assertFalse(world.containers[WORKER + '-previous']['running'])
                self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))  # the old web serves
                message = str(failure)
                self.assertIn('could not be stopped', message)
                self.assertIn('nothing more was closed', message)
                self.assertIn("run this revision's --phase rollback-app", message)
                # and rollback-app finishes it: drained and stopped, closed, removed, the old worker put back
                details, error = run_rollback_app(world)
                self.assertIsNone(error, error and str(error))
                self.assertEqual(world.violations, [])
                self.assertEqual(world.at_old_worker_start, [])
                self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})

    def test_an_s3_first_close_that_does_not_finish_leaves_the_layout_for_rollback_app(self):
        world = Busy(self.tmp)
        s3_fails(world)
        world.fail[('close',)] = install.InstallError('Closing the stages revision aaaaaaaaaaaa left open failed.')
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertIn('did not finish', str(failure))
        self.assertNotIn(('start', WORKER), world.events)
        self.assertIn(NEXT, world.containers)
        details, error = run_rollback_app(world)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.at_old_worker_start, [])


class EveryArmClosesBeforeTheOldWorkerRunsTests(TemporaryDirectoryTest):
    """D-3 and D-6 as one property, at every interrupt point: whatever a single Ctrl-C (before or after any fake call)
    leaves of an S3 or S4 undo - members queuing stages throughout, the incoming web's drain ending normally or
    bounded_out - the old worker is either not started, or started with no stage the new revision's web queued still
    open; and the site stays served."""

    def test_a_ctrl_c_at_any_call_never_lets_the_old_worker_run_what_the_new_web_queued(self):
        for cls in (Busy, Bounded):
            for label, setup in (('S3', s3_fails), ('S4', s4_fails)):
                clean = cls(self.tmp)
                setup(clean)
                run_app(clean)
                self.assertEqual(clean.at_old_worker_start, [], (cls.__name__, label))  # the control: it does start
                total, started = clean.calls, 0
                for mode in ('after', 'before'):
                    for k in range(1, total + 1):
                        for path in self.tmp.iterdir():
                            path.unlink()
                        world = cls(self.tmp)
                        setup(world)
                        if mode == 'after':
                            world.after = k
                        else:
                            world.interrupt_at = k
                        with self.subTest(world=cls.__name__, arm=label, mode=mode, call=k):
                            try:
                                run_app(world)
                            except KeyboardInterrupt:
                                pass  # before anything acted
                            world.invariant()
                            self.assertEqual(world.violations, [], world.events[-6:])
                            if world.at_old_worker_start is not None:
                                started += 1
                                self.assertEqual(world.at_old_worker_start, [], world.events[-8:])
                self.assertGreater(started, 0, (cls.__name__, label))


# --- D-2: only member answers and chosen modifiers written in the window hold the old worker -----------------------------

class WindowedRecordTests(TemporaryDirectoryTest):
    def test_s3_records_written_before_the_switch_hold_nothing_and_are_not_said_to_be_the_new_webs(self):
        world = World(self.tmp)
        s3_fails(world)
        world.close_answer = told({'e1': ['member_answer'], 'e2': ['modifier']}, {})
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
        message = str(failure)
        self.assertNotIn('while it served', message)  # refute-r3 D-2: it had said the new web made them
        self.assertNotIn('It is held', message)
        self.assertIn('2 encounter(s): member_answer 1, modifier 1 hold such records written before the vhost file was '
                      'replaced', message)
        self.assertIn('while only the old web could take requests: they were beside the old pair before the new web '
                      'took any, so they are named only', message)

    def test_s3_records_written_since_the_switch_began_hold_the_old_worker_and_the_receipt_says_when(self):
        world = World(self.tmp)
        s3_fails(world)
        world.close_answer = told({'e1': ['member_answer'], 'e2': ['modifier']}, {'e1': ['member_answer']})
        details, failure = run_app(world)
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, False)})
        message = str(failure)
        self.assertIn('It is held - nothing can be sent', message)
        self.assertIn('1 encounter(s): member_answer 1 hold records only a revision since the core repair writes (a '
                      "member's answer, a reviewer's chosen modifier), written since the vhost file was replaced (",
                      message)
        self.assertIn('1 encounter(s): modifier 1 hold such records written before the vhost file was replaced',
                      message)
        self.assertIn('if the old revision is one, those alone need no clearing', message)
        self.assertNotIn('while it served', message)

    def test_s3_an_answer_the_close_does_not_place_in_time_holds_the_old_worker(self):
        world = World(self.tmp)
        s3_fails(world)
        world.close_answer = named({'e1': ['member_answer']})  # no 'written_since': never read as older
        details, failure = run_app(world)
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, False)})
        self.assertIn('at a time the close did not say, so held as written since the vhost file was replaced',
                      str(failure))
        # a written_since the installer cannot read is no answer either
        world = World(self.tmp)
        s3_fails(world)
        world.close_answer = {**told({'e1': ['modifier']}, {}), 'written_since': ['e1']}
        details, failure = run_app(world)
        self.assertNotIn(('start', WORKER), world.events)

    def test_a_pair_of_this_same_revision_is_not_held_by_them_whenever_they_were_written(self):
        world = World(self.tmp, serving=(REVISION, IMAGE))
        s3_fails(world)
        world.close_answer = told({'e1': ['member_answer']}, {'e1': ['member_answer']})
        details, failure = run_app(world)
        self.assertIn(('start', WORKER), world.events)

    def test_s4_records_written_before_the_switch_do_not_keep_the_new_web(self):
        world = World(self.tmp)
        s4_fails(world)
        world.close_answer = told({'e1': ['member_answer']}, {})
        details, failure = run_app(world)
        self.assertEqual(world.violations, [])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
        self.assertIn('the vhost was switched back', str(failure))
        self.assertIn('member_answer 1 hold such records written before this switch began', str(failure))

    def test_s4_a_record_written_since_the_switch_began_keeps_the_new_web(self):
        world = World(self.tmp)
        s4_fails(world)
        world.close_answer = told({'e1': ['member_answer'], 'e2': ['modifier']}, {'e2': ['modifier']})
        details, failure = run_app(world)
        self.assertIn('the new web keeps serving on 9151', str(failure))
        self.assertIn('1 encounter(s): modifier 1 hold states the old revision would show wrongly', str(failure))
        self.assertEqual(world.names()[NEXT], (IMAGE, 9151, True))

    def test_s4_the_close_after_the_drain_holds_only_what_was_written_since_the_first(self):
        for label, second, held, words in (
                ('before only', told({'e1': ['member_answer']}, {}), False,
                 'member_answer 1 hold such records written before this switch began'),
                ('one since the first close', told({'e1': ['member_answer'], 'e2': ['modifier']}, {'e2': ['modifier']}),
                 True, 'modifier 1 hold records only a revision since the core repair writes')):
            with self.subTest(label):
                world = World(self.tmp)
                s4_fails(world)
                closes_answering(world, [told({'e1': ['member_answer']}, {}), second])
                details, failure = run_app(world)
                self.assertEqual(world.violations, [])
                self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, not held)})
                self.assertIn(words, str(failure))
                self.assertEqual('It is held' in str(failure), held)
                for path in self.tmp.iterdir():
                    path.unlink()

    def test_an_old_worker_that_was_not_running_is_put_back_as_it_was(self):
        # an earlier undo had held it (or a person had stopped it): this install's undo never starts it
        for label, setup in (('S3', s3_fails), ('S4', s4_fails)):
            with self.subTest(label):
                world = World(self.tmp)
                world.containers[WORKER]['running'] = False
                setup(world)
                world.close_answer = told({'e1': ['modifier']}, {})
                details, failure = run_app(world)
                self.assertEqual(world.violations, [])
                self.assertNotIn(('start', WORKER), world.events)
                self.assertEqual(world.names()[WORKER], (OLD_IMAGE, None, False))
                self.assertIn('left stopped (cpt-studio-worker), as it was: it was not running when this install '
                              'parked it', str(failure))
                for path in self.tmp.iterdir():
                    path.unlink()

    def test_switch_back_names_what_was_written_and_when_and_never_which_web_wrote_it(self):
        world = switched_back_world(self.tmp)
        closes_answering(world, [named({}), told({'e1': ['member_answer']}, {'e1': ['member_answer']})])
        details, failure = run_switch_back(world)
        self.assertEqual(world.violations, [])
        message = str(failure)
        self.assertIn('written since this switch-back read none standing', message)
        self.assertNotIn('it wrote them before it stopped taking traffic', message)
        self.assertEqual(running_workers(world), [])  # held: switch-back refuses on any record, as before

    def test_the_split_reads_written_since_and_never_reads_an_unplaced_record_as_older(self):
        closed = told({'e1': ['member_answer', 'unknown'], 'e2': ['modifier'], 'e3': ['participant']},
                      {'e1': ['member_answer']})
        self.assertEqual(install.web_written_by_time(closed), ({'e1': ['member_answer']}, {'e2': ['modifier']}, {}))
        self.assertEqual(install.web_written_by_time(named({'e2': ['modifier']})), ({}, {}, {'e2': ['modifier']}))
        self.assertEqual(install.web_written_by_time({'hazards': None}), ({}, {}, {}))
        hold, notes = install.undo_hold([{'closed': closed, 'shown': {'e1': ['member_answer'], 'e2': ['modifier'],
                                                                     'e3': ['participant']},
                                          'acting': {'e1': ['unknown']}, 'problems': [],
                                          'since': dt.datetime(2026, 11, 4, tzinfo=dt.timezone.utc)}], same=False)
        self.assertTrue(hold)
        self.assertEqual([note.split(' hold ')[0] for note in notes],
                         ['1 encounter(s): unknown 1', '1 encounter(s): member_answer 1', '1 encounter(s): modifier 1',
                          '1 encounter(s): participant 1'])


class WrittenSinceOnTheDatabaseTests(unittest.TestCase):
    """CLOSE_STAGES' 'written_since' on real rows (a disposable PostgreSQL; skipped, never passed, without one): of the
    answers and modifiers it names, exactly those written at or after its 'since'."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import test_install_harness2 as harness2
        problem = harness2.database_problem()
        if problem:
            raise unittest.SkipTest(problem)
        harness2.database()
        cls.run_in_image = staticmethod(harness2.run_in_image)

    def setUp(self):
        from django.db import transaction
        atomic = transaction.atomic()
        atomic.__enter__()

        def rollback():
            transaction.set_rollback(True)
            atomic.__exit__(None, None, None)
        self.addCleanup(rollback)

    def answered(self):
        from studio import answers
        from tests.test_cux_review import persist
        s = persist('selected')
        detail = answers.detail_id('base_included', 'gi.colonoscopy', '45378')
        saved = answers.save_details(s.encounter, s.reviewer,
                                     [{'id': detail, 'fact': 'base_included', 'value': 'cannot_confirm'}])
        self.assertEqual(saved['saved'], 1)
        return str(s.encounter.pk)

    def modified(self):
        from tests.test_cux_review import decide, persist
        s = persist('pair')
        decide(s, '45380', 'approve', modifiers=['XS'], note='Synthetic: a separate lesion.')
        return str(s.encounter.pk)

    def close(self, since):
        return self.run_in_image(install.CLOSE_STAGES, {'since': since.isoformat(), 'note': 'Synthetic close.',
                                                        'kinds': sorted(install.COMMON_STAGE_KINDS)})

    def test_only_what_was_written_since_is_named_written_since(self):
        from django.utils import timezone
        old_answer, old_modifier = self.answered(), self.modified()
        since = timezone.now()
        new_answer, new_modifier = self.answered(), self.modified()
        closed = self.close(since)
        self.assertEqual(closed['hazards'], {old_answer: ['member_answer'], old_modifier: ['modifier'],
                                             new_answer: ['member_answer'], new_modifier: ['modifier']})
        self.assertEqual(closed['written_since'], {new_answer: ['member_answer'], new_modifier: ['modifier']})
        # and the installer reads them so: the new ones hold, the old ones are named only
        written, before, unplaced = install.web_written_by_time(closed)
        self.assertEqual((written, before, unplaced), (
            {new_answer: ['member_answer'], new_modifier: ['modifier']},
            {old_answer: ['member_answer'], old_modifier: ['modifier']}, {}))
        # control: from before all of them, every one was written since
        everything = self.close(since - dt.timedelta(days=1))
        self.assertEqual(everything['written_since'], everything['hazards'])

    def test_a_close_that_names_no_answer_or_modifier_answers_as_it_did(self):
        from django.utils import timezone
        from tests.test_cux_review import persist
        persist('selected')
        closed = self.close(timezone.now() - dt.timedelta(days=1))
        self.assertEqual(closed['hazards'], {})
        self.assertNotIn('written_since', closed)  # the exact answer the suite pins (tests.test_repairs_r1_m)


# --- D-1: rollback-app in the S4 keep layout reads its own baseline ------------------------------------------------

STATE = {}
CONF = '''
server { listen 80; server_name app.quillmd.com cotenant-b.example.org; location / { proxy_pass http://127.0.0.1:8000; } }
server { listen 443 ssl; server_name app.quillmd.com; location / { proxy_pass http://127.0.0.1:8000; } }
server { listen 443 ssl; server_name cotenant-b.example.org; location / { proxy_pass http://127.0.0.1:8100; } }
'''


def fake_probe(scheme, host, path='/', *, port=None, connect_ip=None, verify=True, method='GET', headers=None,
               timeout=5.0, keep_body=False):
    """The network as the baseline reads it: app.quillmd.com's release and each co-tenant's certificate (STATE)."""
    result = {'status': 404 if host == install.UNMATCHED_HOST else 200}
    if scheme == 'https':
        result['cert_sha256'] = STATE['certs'].get(host, 'cert-' + host)
    if host == install.APP_HEALTH_HOST and path == '/health/':
        result['json'] = {'status': 'ok', 'release': STATE['release']}
        if STATE.get('app_down'):
            result = {'error': 'ConnectionRefusedError'}
    return result


class KeepBaselineEndToEndTests(TemporaryDirectoryTest):
    """D-1 through the REAL install.main(): preflight, app (left in the S4 keep layout), rollback-app - with the REAL
    ingress_checks, own_baseline, app_health, routing_snapshot and routing_diff; only the probe (the network) and the
    nginx files' read are faked, so drift is a changed answer of app.quillmd.com or of a co-tenant's certificate."""

    def setUp(self):
        super().setUp()
        STATE.clear()
        STATE.update(release='app-release-1', certs={'app.quillmd.com': 'cert-app-1',
                                                    'cotenant-b.example.org': 'cert-b-1'})

    def run_phase(self, world, phase, *extra):
        """The REAL install.main() for ``phase``: (exit code, its printed line, its receipt). main() leaves its lock on
        <receipts>/.lock open, as a process does until it exits; it is closed here after each run."""
        lock_fds, real_open = [], os.open

        def tracking_open(path, flags, mode=0o777, *, dir_fd=None):
            fd = real_open(path, flags, mode, dir_fd=dir_fd)
            if str(path).endswith('/.lock'):
                lock_fds.append(fd)
            return fd
        patches = world.patches() + [
            mock.patch.object(install, 'ingress_checks', REAL_INGRESS_CHECKS),
            *([mock.patch.object(install, 'own_baseline', REAL_OWN_BASELINE)] if REAL_OWN_BASELINE else []),
            mock.patch.object(install, 'probe', fake_probe),
            mock.patch.object(install, 'enabled_config_texts', lambda: [CONF]),
            mock.patch.object(install, 'published_by', lambda port: sorted(
                n for n, c in world.containers.items() if c['running'] and c['port'] == port)),
            mock.patch.object(install, 'check_door', lambda environ, revision: {'declaration_commit': '0' * 40}),
            mock.patch.object(install, 'check_tree', lambda revision, commit: {'mode': 'exact'}),
            mock.patch.object(install.os, 'open', tracking_open)]
        if phase == 'preflight':
            patches += self.preflight_patches(world)
        out = io.StringIO()
        for patcher in patches:
            patcher.start()
        try:
            with contextlib.redirect_stdout(out):
                code = install.main(['--phase', phase, '--revision', REVISION, '--receipts', str(world.tmp), *extra])
        finally:
            for patcher in reversed(patches):
                patcher.stop()
            for fd in lock_fds:
                os.close(fd)
        line = json.loads(out.getvalue().strip().splitlines()[-1])
        return code, line, json.loads(Path(line['receipt']).read_text(encoding='utf-8'))

    def preflight_patches(self, world):
        world_inspect = world.inspect

        def inspect(kind, name):
            if kind == 'image' and name in (install.HELPER_IMAGE, install.POSTGRES_IMAGE):
                return {'Id': name}
            return world_inspect(kind, name)
        present = {install.CORTI_SOURCE, install.ETC_DIR, *install.LE_DIRS, install.ACME_CHALLENGE_DIR}

        def helper_stat(paths):
            return {path: ({'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o755'} if path in present
                           else {'exists': False}) for path in paths}

        def run_helper(body, params, *, mounts, network='none', timeout=60, sensitive=False):
            if body == install.H_ACME_WRITE:
                return {'written': True}
            if body == install.H_ACME_REMOVE:
                return {'removed': True}
            raise AssertionError('unexpected root helper call in preflight')
        return [mock.patch.object(install, 'docker_positive_control', lambda: '27.0.0'),
                mock.patch.object(install, 'nginx_file_state', lambda: {
                    'available': {'quillmd': install.QUILLMD_VHOST_SHA256}, 'enabled': {}, 'nginx_conf_sha256': 'x',
                    'conf_d': []}),
                mock.patch.object(install, 'containers', lambda: {
                    n: {'id': c['Id'], 'image': c['Image'], 'state': 'running' if c['running'] else 'exited'}
                    for n, c in world.containers.items()}),
                mock.patch.object(install, 'volumes', lambda: ['cpt-studio-pg', 'cpt-studio-files']),
                mock.patch.object(install, 'networks', lambda: ['cpt-studio-net']),
                mock.patch.object(install, 'foreign_uid_tasks', lambda uid, ids, proc_root=None: 0),
                mock.patch.object(install, 'own_service_ids', lambda: []),
                mock.patch.object(install, 'inspect', inspect),
                mock.patch.object(install, 'helper_stat', helper_stat),
                mock.patch.object(install, 'le_state', lambda: {
                    'dirs': {d: True for d in [*install.LE_DIRS, install.ACME_CHALLENGE_DIR]}, 'accounts': ['one'],
                    'live': {}, 'renewal': {}}),
                mock.patch.object(install, 'run_helper', run_helper),
                mock.patch.object(install.socket, 'getaddrinfo', lambda host, port, type=0: [
                    (socket.AF_INET, socket.SOCK_STREAM, 6, '', (install.PUBLIC_IPV4, port))]),
                mock.patch.object(install.shutil, 'disk_usage', lambda path: SimpleNamespace(
                    total=200 * 2 ** 30, used=50 * 2 ** 30, free=150 * 2 ** 30))]

    def keep_layout_after_a_real_preflight(self):
        world = World(self.tmp)
        for path in self.tmp.glob('preflight-*.json'):  # the REAL preflight writes the baseline instead
            path.unlink()
        code, line, receipt = self.run_phase(world, 'preflight')
        self.assertEqual((code, receipt['ok']), (0, True), line)
        world.unhealthy.add(WORKER)
        world.close_answer = told({'e1': ['member_answer']}, {'e1': ['member_answer']})
        code, line, receipt = self.run_phase(world, 'app', '--provider-mode', 'disabled')
        self.assertEqual(code, 1)
        self.assertIn('the new web keeps serving on 9151', line['summary'])
        # the named record is cleared on this revision's web
        world.unhealthy.discard(WORKER)
        world.close_answer = named({})
        world.inflight = {}
        return world

    def test_after_the_baseline_drifted_rollback_app_switches_back_without_a_new_preflight(self):
        for label, drift in (('app.quillmd.com was deployed', lambda: STATE.update(release='app-release-2')),
                             ('a co-tenant certificate renewed',
                              lambda: STATE['certs'].update({'cotenant-b.example.org': 'cert-b-2'}))):
            with self.subTest(label):
                for path in self.tmp.iterdir():
                    path.unlink()
                STATE.update(release='app-release-1', certs={'app.quillmd.com': 'cert-app-1',
                                                            'cotenant-b.example.org': 'cert-b-1'})
                world = self.keep_layout_after_a_real_preflight()
                drift()
                # preflight still refuses in this layout (its port check), so it is not the way back any more
                code, line, receipt = self.run_phase(world, 'preflight')
                self.assertEqual(code, 1)
                self.assertIn(f'{NEXT} is left from an interrupted app', line['summary'])
                code, line, receipt = self.run_phase(world, 'rollback-app')
                self.assertEqual((code, receipt['ok']), (0, True), line)
                self.assertIn(f'switched back to {OLD[:12]} on 9150 (the S4 keep layout)', line['summary'])
                self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})
                self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
                baseline = receipt['details']['baseline']
                self.assertEqual(baseline['phase'], 'rollback-app')
                self.assertEqual(baseline['details']['app_health']['json']['release'], STATE['release'])
                self.assertEqual(world.violations, [])

    def test_a_baseline_it_cannot_read_refuses_changing_nothing(self):
        world = self.keep_layout_after_a_real_preflight()
        STATE['app_down'] = True
        before, mark = world.names(), len(world.events)
        code, line, receipt = self.run_phase(world, 'rollback-app')
        self.assertEqual(code, 1)
        self.assertIn('app.quillmd.com /health/ did not answer 200 JSON', line['summary'])
        self.assertIn('nothing was stopped or removed', line['summary'])
        self.assertEqual(world.names(), before)
        self.assertEqual(changes(world, mark), [])


class KeepBaselineTests(TemporaryDirectoryTest):
    def test_a_drift_during_the_switch_back_says_to_run_rollback_app_again_not_preflight(self):
        world = keep_world(self.tmp)
        world.ingress_answers = [['app.quillmd.com /health/ changed']]  # between its own read and the switch back
        details, failure = run_rollback_app(world)
        self.assertIsInstance(failure, install.InstallError)
        message = str(failure)
        self.assertIn('since the baseline rollback-app read for this switch back', message)
        self.assertIn('run --phase rollback-app: in this layout it reads co-tenant routing and app.quillmd.com afresh',
                      message)
        self.assertNotIn('Run --phase preflight again', message)
        self.assertEqual(world.names()[NEXT], (IMAGE, 9151, True))  # the new web keeps serving
        self.assertEqual(world.acts('baseline'), [('baseline',)])

    def test_its_baseline_is_read_before_anything_is_stopped(self):
        world = keep_world(self.tmp)
        world.baseline_failure = install.InstallError('app.quillmd.com /health/ did not answer 200 JSON, so no '
                                                      'baseline the switch back could be verified against was read')
        before = world.names()
        details, failure = run_rollback_app(world)
        self.assertIn('did not answer 200 JSON', str(failure))
        self.assertEqual(world.names(), before)
        self.assertEqual(changes(world, 0), [])
        self.assertEqual([event[0] for event in world.events if event[0] in ('hazards', 'baseline')],
                         ['hazards', 'baseline'])

    def test_it_needs_no_preflight_receipt(self):
        world = keep_world(self.tmp)
        for path in self.tmp.glob('preflight-*.json'):
            path.unlink()
        details, failure = run_rollback_app(world)
        self.assertIsNone(failure, failure and str(failure))
        self.assertEqual(details['baseline']['phase'], 'rollback-app')


# --- D-4: rollback-app in the keep layout succeeds only when it did everything it says ---------------------------

class KeepRollbackReceiptTests(TemporaryDirectoryTest):
    def test_an_incoming_web_that_cannot_be_removed_fails_the_phase_and_the_receipt_says_it_is_left(self):
        world = keep_world(self.tmp)
        world.fail[('rm', NEXT)] = install.InstallError('docker rm --force cpt-studio-web-next failed with exit 1.')
        details, failure = run_rollback_app(world)
        self.assertIsNone(details)  # refute-r3 D-4: it had ended ok, "this revision's web and worker removed"
        self.assertIsInstance(failure, install.InstallError)
        message = str(failure)
        self.assertIn(f'the incoming web could not be removed (docker rm --force {NEXT} failed', message)
        self.assertIn('remove it by hand', message)
        self.assertNotIn('removed after closing', message)
        self.assertTrue(failure.details['incoming_left'])
        self.assertIn(NEXT, failure.details['left']['containers'])
        # everything else was done: stopped before the close, closed, the old pair serving and processing
        self.assertFalse(world.containers[NEXT]['running'])
        self.assertEqual((world.nginx_port, world.file_port()), (9150, 9150))
        self.assertEqual(world.names()[WORKER], (OLD_IMAGE, None, True))
        self.assertEqual(world.violations, [])

    def test_a_ctrl_c_at_any_call_never_ends_in_a_success(self):
        def make():
            for path in self.tmp.iterdir():
                path.unlink()
            return keep_world(self.tmp)
        sweep(self, make, run_rollback_app)

    def test_the_summary_names_what_was_removed(self):
        world = keep_world(self.tmp)
        details, failure = run_rollback_app(world)
        self.assertIsNone(failure, failure and str(failure))
        self.assertIn(f"removed {NEXT} (this revision's web) and {WORKER} (this revision's worker) after closing their "
                      'open stages', details['summary'])
        self.assertEqual(world.names(), {WEB: (OLD_IMAGE, 9150, True), WORKER: (OLD_IMAGE, None, True)})


class RollbackAppOwnPairTests(TemporaryDirectoryTest):
    def test_it_never_removes_another_revisions_pair(self):
        # the old pair an undo put back serves under the canonical names: this revision's rollback-app leaves it
        world = World(self.tmp)
        details, failure = run_rollback_app(world)
        self.assertIsInstance(failure, install.InstallError)
        self.assertIn("this revision's rollback-app removes only this revision's own pair", str(failure))
        self.assertIn('nothing was stopped or removed', str(failure))
        self.assertEqual(world.acts('stop', 'rm', 'close', 'hazards'), [])
        self.assertEqual(world.violations, [])


# --- D-5: a close that was started is never reported as having closed nothing ------------------------------------

class SwitchBackCloseReceiptTests(TemporaryDirectoryTest):
    def test_a_close_that_took_effect_and_then_stopped_is_not_reported_as_nothing_closed(self):
        for label, error in (('a Ctrl-C', KeyboardInterrupt()),
                             ('the 180 s timeout', install.InstallError('docker run cpt-studio-oneshot-0 did not finish '
                                                                        'within 180 s.'))):
            with self.subTest(label):
                for path in self.tmp.iterdir():
                    path.unlink()
                world = switched_back_world(self.tmp)
                original = world.close

                def close(*args, _original=original, _error=error):
                    _original(*args)  # it committed
                    raise _error
                world.close = close
                details, failure = run_switch_back(world)
                self.assertEqual(len(world.closes), 1)
                self.assertEqual(failure.details['failed_at'], 'B4')
                message = str(failure)
                self.assertNotIn('Nothing was closed.', message)  # refute-r3 D-5
                self.assertIn('The close was started and gave no answer, so it may have closed some or all of this '
                              "revision's open stages before it stopped", message)
                self.assertTrue(failure.details['closes']['first_started_at'])
                self.assertEqual(world.names(), {WEB: (IMAGE, 9151, True), WORKER: (IMAGE, None, True)})

    def test_control_a_refusal_before_the_close_still_says_nothing_was_closed(self):
        world = switched_back_world(self.tmp)
        world.ingress_answers = [[], ['app.quillmd.com /health/ changed']]
        details, failure = run_switch_back(world)
        self.assertEqual(world.closes, [])
        self.assertIn('Nothing was closed.', str(failure))

    def test_an_undo_close_that_does_not_finish_says_it_may_have_closed_some(self):
        world = World(self.tmp)
        s4_fails(world)
        world.fail[('close',)] = install.InstallError('Closing the stages revision aaaaaaaaaaaa left open failed.')
        details, failure = run_app(world)
        self.assertIn('it may have closed some or all of them before it stopped', str(failure))
        self.assertNotIn('could not be closed', str(failure))


# --- D-7: a unique column added to an existing table ------------------------------------------------------------------

class UniqueColumnGateTests(unittest.TestCase):
    REFUSED = {
        'unique, db_default (the finding)': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(unique=True, "
            "db_default=0))"],
        'unique, a default the SQL sets (the finding)': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(unique=True, default=0))",
            "migrations.RunSQL(sql=['ALTER TABLE studio_decision ALTER COLUMN slot SET DEFAULT 0'])"],
        'nullable unique, db_default': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(null=True, unique=True, "
            "db_default=0))"],
        'nullable unique, a default the SQL sets': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(null=True, unique=True))",
            "migrations.RunSQL(sql=['ALTER TABLE studio_decision ALTER COLUMN slot SET DEFAULT 0'])"],
        'a one-to-one field with db_default': [
            "migrations.AddField(model_name='decision', name='twin', field=models.OneToOneField(to='studio.proposal', "
            "on_delete=models.PROTECT, db_default=1))"],
        'a primary key with db_default': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(primary_key=True, "
            "db_default=0))"],
        'unique given by a name the check cannot read': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(unique=UNIQUE, "
            "db_default=0))"],
        'NOT NULL unique with no default': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(unique=True))"],
    }
    ACCEPTED = {
        'nullable unique with no database default': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(null=True, unique=True))"],
        'a nullable one-to-one field with no default': [
            "migrations.AddField(model_name='decision', name='twin', field=models.OneToOneField(to='studio.proposal', "
            "on_delete=models.PROTECT, null=True))"],
        'a unique column of a table this migration creates': [
            "migrations.CreateModel(name='Thing', fields=[('id', models.BigAutoField(primary_key=True))])",
            "migrations.AddField(model_name='thing', name='slot', field=models.IntegerField(unique=True, db_default=0))"],
        'db_default without unique (control)': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(db_default=0))"],
        'unique=False with db_default (control)': [
            "migrations.AddField(model_name='decision', name='slot', field=models.IntegerField(unique=False, "
            "db_default=0))"],
    }

    def test_a_unique_column_an_older_pair_fills_with_one_value_is_refused(self):
        for label, operations in self.REFUSED.items():
            with self.subTest(label):
                found = gate(*operations)
                self.assertFalse(found['safe'], found)
        self.assertEqual(gate(*self.REFUSED['unique, db_default (the finding)'])['why'], [
            "decision.slot: a unique column added to an existing table that is NOT NULL or has a database default: an "
            "older pair's insert names no value for it, so it is refused, or gets the one default and its second insert "
            "is refused"])

    def test_the_unique_columns_an_older_pair_cannot_collide_on_are_accepted(self):
        for label, operations in self.ACCEPTED.items():
            with self.subTest(label):
                found = gate(*operations)
                self.assertTrue(found['safe'], found)
        self.assertEqual(gate(*self.ACCEPTED['nullable unique with no database default'])['why'], [
            'decision.slot: a nullable unique column with no database default: an older pair leaves it NULL, which no '
            'unique constraint refuses'])

    def test_the_committed_migrations_still_pass(self):
        verdicts = install.migration_safety(APP_ROOT / 'studio' / 'migrations')
        self.assertTrue(verdicts)
        self.assertTrue(all(verdict['safe'] for verdict in verdicts.values()), verdicts)


# --- what INSTALL.md says about the repairs ---------------------------------------------------------------------------

class InstallDocR3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.said = ' '.join((APP_ROOT / 'ops' / 'INSTALL.md').read_text(encoding='utf-8').split())

    def says(self, phrase):
        self.assertIn(phrase, self.said, f'INSTALL.md does not say: {phrase}')

    def test_the_repairs_are_documented(self):
        recovery = self.said.split('## Recovery notes', 1)[1].split('## Local build and tests', 1)[0]
        for phrase in ('never start the old worker by hand', "Run this revision's `rollback-app`: it proves nginx runs "
                       'the vhost', 'rollback-app reads co-tenant routing and app.quillmd.com itself',
                       "then run this revision's `rollback-app`, which finishes the way back"):
            self.assertIn(phrase, recovery, f'the Recovery notes do not say: {phrase}')
        # refute-r3 D-3 and D-1: the two steps that led nowhere safe are gone - the old worker started by hand after an
        # app undo, and a preflight the keep layout refuses
        for phrase in ('put the old worker back if it is parked', 'reload, and put the old worker back',
                       "run `preflight` again, then run this revision's `rollback-app`"):
            self.assertNotIn(phrase, recovery)
        for phrase in ('drained and stopped, and only then closed again',
                       'written since the file was replaced',
                       'written before the switch began are named only',
                       'put back as it was',
                       'a unique column (`unique`, a primary key or a one-to-one field) added to an existing table'):
            self.says(phrase)


if __name__ == '__main__':
    unittest.main()
