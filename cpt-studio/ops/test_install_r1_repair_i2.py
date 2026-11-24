"""Release 1's integrated refutation, round 2: the installer's repairs (repair builder i2). Offline, under test_install's
host guard; every Docker, root-helper and in-image call stood in. Synthetic data only.

  I2-1  installer-0: one ledger limit (LEDGER_LIMIT), read by the replay step and by the ledger step, which keeps no
        ledger the replay would refuse; sized for a practice-year at the owner's figure.
  I2-2  switchback-0: a dispose step that changes rows (close, execute, a replay with --execute) runs only while the
        pair under the canonical names has disposal (read as the switch-back's refusal reads it); the dry runs and the
        ledger stay open; an install or switch in progress still refuses every step.
  I2-3  sessions-2: rollback-app ends every session (END_EVERY_SESSION, with the switch-back's receipt fields) before
        an older web without the session policy can serve again - in the S4 keep layout before the switch back, in the
        removal before the pair is removed (the parked pair without the policy, or none parked); a failed end is never
        skipped (the keep layout's new web keeps serving; the removal leaves the pair stopped, not removed).
  I2-4  switchback-1: the guide no longer says release 1's verify_login.py, scan_customer.py and walk pass against the
        pair before release 1 after a switch-back; it says why they fail closed and what to run instead.
  I2-5  installer-2: an option given more than once is refused before anything runs, the receipt naming it.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1_repair_i2 -v
"""
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_install_r1 as r1  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host  # noqa: E402


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- I2-1: a ledger's one limit -----------------------------------------------------------------------------------------

def ledger_of(size: int, lines: int = 4) -> bytes:
    """A ledger-shaped file of exactly ``size`` bytes in ``lines`` JSON lines of ids (the real ledger's MACs are the
    command's to check, and every command is stood in here)."""
    rows = [json.dumps({'entry': {'id': f'0f8fad5b-d9cb-469f-a165-7086772895{n:02d}', 'pad': ''}, 'mac': '0' * 64},
                       sort_keys=True).encode() + b'\n' for n in range(lines)]
    short = size - sum(len(row) for row in rows)
    assert short >= 0, size
    rows[-1] = rows[-1].replace(b'"pad": ""', b'"pad": "' + b'a' * short + b'"')
    data = b''.join(rows)
    assert len(data) == size, (len(data), size)
    return data


# The finding's two inputs (refutation round 2, installer-0): the genuine ledger of one whole-practice disposal of 5,000
# one-PDF documents (1,050,108 bytes in 4 lines), and the 'committed' line alone of an 8,100-document one (1,062,712
# bytes) - both over the 1 MiB the replay read before.
FIVE_THOUSAND_DOCUMENTS = 1_050_108
ONE_LINE_OF_8100_DOCUMENTS = 1_062_712


class LedgerLimitTests(TemporaryDirectoryTest):
    def world(self, name, **kwargs):
        folder = self.tmp / name
        folder.mkdir(mode=0o700)
        return r1.ManageWorld(folder, **kwargs)

    def replay(self, name, ledger_path, *extra):
        world = self.world(name, output=b'Ledger rows missing: 4\n')
        details = world.run('--command', 'dispose', '--dispose-step', 'replay-ledger', '--ledger-file', str(ledger_path),
                            '--by', 'Ada Lovelace', *extra)
        return world, details

    def test_the_ledger_the_ledger_step_keeps_whole_is_one_the_replay_step_reads(self):
        ledger = r1_ledger = ledger_of(FIVE_THOUSAND_DOCUMENTS)
        printer = self.world('print', output=ledger)
        printed = printer.run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')
        kept = Path(printed['ledger_printed']['log'])
        self.assertEqual(kept.read_bytes(), ledger)
        self.assertEqual((printed['ledger_printed']['sha256'], printed['ledger_printed']['bytes'],
                          printed['ledger_printed']['lines']), (sha(ledger), len(ledger), 4))
        self.assertTrue(printed['stdout_cut'])  # the receipt keeps STDOUT_KEPT characters; the log keeps it whole
        for name, extra in (('dry-run', ()), ('execute', ('--execute', '--approved-by', 'Grace Hopper'))):
            with self.subTest(name):
                world, details = self.replay(name, kept, *extra)
                (act,) = world.acts()
                self.assertEqual(act[:4], ['manage', 'dispose', '--replay-ledger', '/run/cpt-manage/ledger'])
                # the RAM-only copy the one-shot read is the ledger, byte for byte, and the receipt names it by digest
                self.assertEqual(world.mounted['ledger'][0].encode(), r1_ledger)
                self.assertEqual(details['ledger'], {'sha256': sha(ledger), 'bytes': len(ledger)})

    def test_one_committed_line_of_an_8100_document_disposal_replays(self):
        line = ledger_of(ONE_LINE_OF_8100_DOCUMENTS, lines=1)
        path = self.tmp / 'committed-line.log'
        path.write_bytes(line)
        world, details = self.replay('one-line', path)
        self.assertEqual(world.mounted['ledger'][0].encode(), line)
        self.assertEqual(details['mode'], 'dry run')

    def test_the_ledger_step_keeps_no_ledger_the_replay_step_would_refuse_and_says_what_to_do(self):
        for name, output, why in (('over', ledger_of(install.LEDGER_LIMIT + 1), 'more than'),
                                  ('not-utf8', b'{"entry": "\xff"}\n', 'not UTF-8')):
            with self.subTest(name):
                world = self.world(name, output=output)
                with self.assertRaises(install.InstallError) as caught:
                    world.run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')
                message, record = str(caught.exception), caught.exception.details
                self.assertIn('the ledger it printed is not kept', message)
                self.assertIn('Nothing was changed', message)
                self.assertIn('never restore the database from a backup older than its newest disposal', message)
                printed = record['ledger_printed']
                self.assertIsNone(printed['log'])
                self.assertIn(why, printed['not_kept'])
                self.assertEqual((printed['sha256'], printed['bytes']), (sha(output), len(output)))
                self.assertFalse([path for path in world.tmp.glob('*.log') if path.read_bytes() == output])
                self.assertFalse(list(world.tmp.glob('*-dispose-ledger.log')))
        # exactly at the limit it is kept - and the replay reads that very file
        exact = ledger_of(install.LEDGER_LIMIT)
        world = self.world('exact', output=exact)
        kept = Path(world.run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')
                    ['ledger_printed']['log'])
        self.assertEqual(kept.read_bytes(), exact)
        replayed, _ = self.replay('exact-replay', kept)
        self.assertEqual(len(replayed.mounted['ledger'][0].encode()), install.LEDGER_LIMIT)

    def test_one_limit_is_read_by_both_steps(self):
        with mock.patch.object(install, 'LEDGER_LIMIT', 4096):
            refused = self.world('refused', output=ledger_of(4097, lines=2))
            with self.assertRaisesRegex(install.InstallError, 'not kept, since it is 4097 bytes, more than the 4096'):
                refused.run('--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')
            path = self.tmp / 'ledger-4097.log'
            path.write_bytes(ledger_of(4097, lines=2))
            with self.assertRaisesRegex(install.InstallError, 'at most 4096 bytes'):
                self.replay('refused-replay', path)
            kept = Path(self.world('kept', output=ledger_of(4096, lines=2)).run(
                '--command', 'dispose', '--dispose-step', 'ledger', '--by', 'Ada Lovelace')['ledger_printed']['log'])
            world, _ = self.replay('kept-replay', kept)
            self.assertEqual(len(world.mounted['ledger'][0]), 4096)
        self.assertEqual(install.ledger_problem(b'x' * 10), '')
        self.assertIn('not UTF-8', install.ledger_problem(b'\xff'))

    def test_the_limit_holds_a_practice_year_at_the_owners_figure_within_the_replays_memory(self):
        documents = 50 * 365  # 1,000 practices at 50 uploads a day: one practice's year
        per_document, per_further_file, per_disposal = 209, 92, 5_120  # round 2's measurement of the ledger's growth
        for files in (1, 4):
            with self.subTest(files=files):
                self.assertLess(documents * (per_document + per_further_file * (files - 1)) + per_disposal,
                                install.LEDGER_LIMIT)
        # the replay's one-shot (the act's container) reads the ledger whole: repair round 2 measured its reading at about
        # five bytes per ledger byte, so the limit keeps six well inside that container's memory
        calls = []
        with mock.patch.object(install, 'run', lambda argv, **kwargs: calls.append(argv) or mock.Mock(returncode=0)), \
                mock.patch.object(install, 'inspect', return_value=None):
            install.oneshot('sha256:' + 'c' * 64, ['manage', 'dispose'], b'')
        memory = calls[0][calls[0].index('--memory') + 1]
        self.assertEqual(memory, '768m')
        self.assertLess(6 * install.LEDGER_LIMIT, 768 * 2 ** 20)


# --- I2-2: no step that changes a row while the serving revision has no disposal ------------------------------------------

# the dispose steps whose receipt's mode is 'executed' (they change rows), and those that change none an older revision
# reads (the dry runs and the ledger), each with its own arguments beyond --command dispose and --by
CHANGES_ROWS = {
    'close': ('--dispose-step', 'close', '--workspace-id', r1.WORKSPACE, '--reason-file', 'REASON'),
    'execute': ('--dispose-step', 'execute', '--plan-id', r1.PLAN, '--approved-by', 'Grace Hopper'),
    'replay-ledger --execute': ('--dispose-step', 'replay-ledger', '--ledger-file', 'LEDGER', '--execute',
                                '--approved-by', 'Grace Hopper'),
}
CHANGES_NO_ROW_AN_OLDER_REVISION_READS = {
    'plan': ('--dispose-step', 'plan', '--workspace-id', r1.WORKSPACE, '--reason-file', 'REASON'),
    'ledger': ('--dispose-step', 'ledger'),
    'replay-ledger': ('--dispose-step', 'replay-ledger', '--ledger-file', 'LEDGER'),
}


class ManageOnHost(r1.ManageWorld):
    """ManageWorld whose containers are a blue/green host's, labelled as docker inspect shows them."""

    def __init__(self, tmp, host, **kwargs):
        super().__init__(tmp, **kwargs)
        self.host = host

    def inspect(self, kind, name):
        return self.host.inspect(kind, name)


class ServingDisposalTests(TemporaryDirectoryTest):
    def folder(self, name):
        folder = self.tmp / name.replace(' ', '-')
        folder.mkdir(mode=0o700)
        return folder

    def dispose(self, world, extra):
        try:
            return world.run('--command', 'dispose', *extra, '--by', 'Ada Lovelace'), None
        except install.InstallError as error:
            return None, error

    def assert_each_step(self, make_world, revision):
        """Every step that changes a row is refused, running nothing; every other runs."""
        for step, extra in CHANGES_ROWS.items():
            with self.subTest(refused=step):
                world = make_world(self.folder(f'refused {step}'))
                details, error = self.dispose(world, extra)
                self.assertIsInstance(error, install.InstallError, details and details.get('summary'))
                self.assertIn('changes rows', str(error))
                self.assertIn(f'is revision {revision[:12]}, which has no disposal', str(error))
                self.assertIn('nothing was disposed of', str(error))
                self.assertIn('install one (--phase app), then run this step again', str(error))
                self.assertEqual(world.acts(), [])
        for step, extra in CHANGES_NO_ROW_AN_OLDER_REVISION_READS.items():
            with self.subTest(open=step):
                world = make_world(self.folder(f'open {step}'))
                details, error = self.dispose(world, extra)
                self.assertIsNone(error, error and str(error))
                self.assertEqual(world.acts()[0][:2], ['manage', 'dispose'])
                self.assertIn(details['mode'], ('dry run', 'read'))

    def test_after_a_switch_back_to_a_revision_without_disposal_no_step_that_changes_a_row_runs(self):
        # the finding's input: release 1's own switch-back to OLD (nothing closed or destroyed, so it is allowed), then
        # release 1's --phase manage on that host, OLD's web and worker serving under the canonical names
        import test_install
        from test_install_bluegreen import IMAGE, OLD, OLD_IMAGE, REVISION, WEB, WORKER, switch_back_args
        from test_install_r1_repair import SessionWorld
        host = SessionWorld(self.tmp, live=9151, serving=(REVISION, IMAGE), pre_policy=(OLD,))
        install.write_receipt(self.tmp, 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
            'replaced': {'web': {'id': 'web-old', 'image': OLD_IMAGE, 'revision': OLD},
                         'worker': {'id': 'worker-old', 'image': OLD_IMAGE, 'revision': OLD}}}})
        patches = host.patches() + [mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', {OLD})]
        for patcher in patches:
            patcher.start()
        try:
            install.phase_switch_back(install.Context(switch_back_args(self.tmp), self.tmp))
        finally:
            for patcher in reversed(patches):
                patcher.stop()
        self.assertEqual({name: host.containers[name]['revision'] for name in (WEB, WORKER)}, {WEB: OLD, WORKER: OLD})
        self.assertEqual([name for name in host.containers if name.endswith(('-next', '-previous'))], [])
        with mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', {OLD}):
            self.assert_each_step(lambda folder: ManageOnHost(folder, host), OLD)

    def test_after_an_app_that_migrated_and_failed_at_s1_the_older_web_serving_is_read_too(self):
        import test_install
        from test_install_bluegreen import NEXT, OLD, BlueGreenWorld, run_app
        host = BlueGreenWorld(self.tmp)  # OLD serves on 9150
        host.unhealthy.add(NEXT)
        details, failure = run_app(host)
        self.assertEqual((failure.details or {}).get('failed_at'), 'S1')
        with mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', {OLD}):
            self.assert_each_step(lambda folder: ManageOnHost(folder, host), OLD)

    def test_what_serves_is_read_fail_closed(self):
        import test_install
        old = 'b' * 40
        close = CHANGES_ROWS['close']

        class Unowned(r1.ManageWorld):
            labels = {}

            def inspect(self, kind, name):
                if name == install.SERVICES['web']:
                    return {'Id': name, 'Config': {'Labels': self.labels}, 'State': {'Running': True}}
                return super().inspect(kind, name)
        unlabelled = type('Unlabelled', (Unowned,), {'labels': {install.LABEL: '1', install.ROLE_LABEL: 'web'}})
        refused = {
            'no web': (lambda folder: r1.ManageWorld(folder, serving={'web': None, 'worker': None}),
                       'there is no cpt-studio-web, so the revision that serves next is not known'),
            'no web, a worker': (lambda folder: r1.ManageWorld(folder, serving={'web': None, 'worker': r1.REVISION}),
                                 'there is no cpt-studio-web'),
            'an older worker': (lambda folder: r1.ManageWorld(folder, serving={'web': r1.REVISION, 'worker': old}),
                                f'cpt-studio-worker is revision {old[:12]}, which has no disposal'),
            'a web not this installer\'s': (Unowned, 'cpt-studio-web is not a CPT Studio web container'),
            'a web with no revision label': (unlabelled, 'cpt-studio-web carries no revision label'),
        }
        with mock.patch.object(test_install, 'PRE_DISPOSAL_REVISIONS', {old}):
            for label, (make, said) in refused.items():
                with self.subTest(refused=label):
                    world = make(self.folder(label))
                    details, error = self.dispose(world, close)
                    self.assertIsInstance(error, install.InstallError)
                    self.assertIn(said, str(error))
                    self.assertIn('nothing was disposed of', str(error))
                    self.assertEqual(world.acts(), [])
            # a revision this checkout cannot read is never taken for one with disposal
            cannot = install.InstallError(f'Cannot tell whether {old[:12]} has release 1\'s disposal: this checkout '
                                          'cannot read that revision.')
            with mock.patch.object(install, 'has_disposal', side_effect=cannot):
                world = r1.ManageWorld(self.folder('unreadable'))
                details, error = self.dispose(world, close)
            self.assertIn('cannot read that revision', str(error))
            self.assertIn('Nothing was disposed of.', str(error))
            self.assertEqual(world.acts(), [])
            # controls: this revision's pair, or a later one that has disposal, serving - the step runs
            for label, serving in (('this revision', None), ('a later one', {'web': 'c' * 40, 'worker': 'c' * 40})):
                with self.subTest(control=label):
                    world = r1.ManageWorld(self.folder(f'control {label}'), serving=serving)
                    details, error = self.dispose(world, close)
                    self.assertIsNone(error, error and str(error))
                    self.assertEqual(details['summary'], 'dispose close: executed')

    def test_an_install_or_switch_in_progress_still_refuses_every_step_read_only_ones_too(self):
        for leftover in (install.INCOMING_WEB, 'cpt-studio-web-previous', 'cpt-studio-worker-previous'):
            for step, extra in {**CHANGES_ROWS, **CHANGES_NO_ROW_AN_OLDER_REVISION_READS}.items():
                with self.subTest(leftover=leftover, step=step):
                    world = r1.ManageWorld(self.folder(f'{leftover} {step}'), containers=[leftover])
                    details, error = self.dispose(world, extra)
                    self.assertIn('in progress', str(error))
                    self.assertEqual(world.acts(), [])


# --- I2-3: rollback-app ends every session before an older web without the session policy serves again ---------------

EVENT_ID = '0f8fad5b-d9cb-469f-a165-70867728950e'


class RollbackKeepSessionTests(TemporaryDirectoryTest):
    """rollback-app in the S4 keep layout switches the upstream back to the old web (return_to_old_web)."""

    def keep(self):
        """The S4 keep layout (round 1's KeepLayoutDisposalTests' own): this revision's incoming web serves on 9151,
        its worker stopped, the old worker parked; the old web (OLD) runs on 9150 with no traffic."""
        from test_install_bluegreen import WORKER
        from test_install_r2 import World, named
        from test_install_bluegreen import run_app

        class KeepSessionWorld(World):
            session_answer = {'ended': 3, 'event': EVENT_ID}

            def app_script(self, image_id, env_bytes, body, params, **kwargs):
                if body == install.END_EVERY_SESSION:
                    self.act('end_sessions', image_id, params['from_revision'], params['to_revision'])
                    if isinstance(self.session_answer, BaseException):
                        raise self.session_answer
                    return self.done(dict(self.session_answer))
                return super().app_script(image_id, env_bytes, body, params, **kwargs)
        world = KeepSessionWorld(self.tmp)
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

    def rollback(self, world, pre_policy):
        import test_install
        from test_install_r2 import run_rollback_app
        with mock.patch.object(test_install, 'PRE_SESSION_POLICY_REVISIONS', set(pre_policy)):
            return run_rollback_app(world)

    def test_every_session_is_ended_before_the_switch_back_to_a_web_without_the_policy(self):
        from test_install_bluegreen import IMAGE, NEXT, OLD, OLD_IMAGE, REVISION
        world = self.keep()
        details, failure = self.rollback(world, (OLD,))
        self.assertIsNone(failure, failure and str(failure))
        self.assertEqual(details['outcome'], 'switched')
        acts = world.acts('close', 'end_sessions', 'put_back', 'vhost', 'reload', 'drain')
        ended = acts.index(('end_sessions', IMAGE, REVISION, OLD))
        self.assertEqual(acts[0][0], 'close')                              # the first close, then the end,
        self.assertEqual(acts[ended + 1:ended + 3], [('put_back', OLD_IMAGE), ('vhost', 'replace', 9150)])
        self.assertEqual(world.acts('end_sessions'), [('end_sessions', IMAGE, REVISION, OLD)])  # once
        # the receipt's fields are a switch-back's (B4)
        record = details['sessions_ended']
        self.assertEqual((record['ended'], record['event'], record['from_revision'], record['to_revision']),
                         (3, EVENT_ID, REVISION, OLD))
        self.assertTrue(record['started_at'])
        self.assertIn('every session ended (3', details['summary'])
        self.assertNotIn(NEXT, world.containers)

    def test_between_two_revisions_with_the_policy_no_session_is_ended(self):
        world = self.keep()
        details, failure = self.rollback(world, ())
        self.assertIsNone(failure, failure and str(failure))
        self.assertEqual(world.acts('end_sessions'), [])
        self.assertNotIn('sessions_ended', details)

    def test_an_end_that_fails_keeps_this_revisions_web_serving_and_says_it_may_have_ended_them(self):
        from test_install_bluegreen import NEXT, OLD
        world = self.keep()
        world.session_answer = install.InstallError('Ending every session failed (exit 1).')
        details, failure = self.rollback(world, (OLD,))
        self.assertIsInstance(failure, install.InstallError)
        message = str(failure)
        self.assertIn('the end of every session did not finish (Ending every session failed (exit 1).)', message)
        self.assertIn('the new web keeps serving on 9151', message)
        self.assertIn('it may have ended every session', message)
        self.assertEqual(world.acts('vhost', 'reload'), [])  # never the old web over sessions it would read again
        self.assertEqual((world.nginx_port, world.containers[NEXT]['running']), (9151, True))
        self.assertTrue(failure.details['sessions_ended']['started_at'])
        self.assertEqual(failure.details['outcome'], 'kept')

    def test_a_policy_that_cannot_be_read_refuses_before_anything_is_stopped(self):
        from test_install_bluegreen import OLD
        world = self.keep()
        before = world.names()
        cannot = install.InstallError(f'Cannot tell whether {OLD[:12]} has release 1\'s session policy: this checkout '
                                      'cannot read that revision.')
        with mock.patch.object(install, 'has_session_policy', side_effect=cannot):
            details, failure = self.rollback(world, (OLD,))
        self.assertIn('Nothing was stopped or removed.', str(failure))
        self.assertEqual(world.names(), before)
        self.assertEqual(world.acts('stop', 'close', 'end_sessions', 'vhost'), [])


class RollbackRemovalSessionTests(TemporaryDirectoryTest):
    """rollback-app's removal of this revision's pair: what runs next is the parked pair, or not known."""

    REVISION, OLD, LATER = 'a' * 40, 'b' * 40, 'c' * 40
    IMAGE, OLD_IMAGE = 'sha256:' + 'c' * 64, 'sha256:' + 'd' * 64

    def containers(self, parked=None):
        def container(role, image, revision, running=True):
            return {'Id': f'{role}-{revision[:4]}', 'Image': image, 'Created': '2026-11-01T12:00:00.000000Z',
                    'State': {'Running': running},
                    'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role,
                                          install.REVISION_LABEL: revision}}}
        live = {install.SERVICES[role]: container(role, self.IMAGE, self.REVISION) for role in ('web', 'worker')}
        if parked is not None:
            live.update({install.SERVICES[role] + '-previous': container(role, self.OLD_IMAGE, parked, running=False)
                         for role in ('web', 'worker')})
        return live

    def run_phase(self, live, *, pre_policy=('b' * 40,), session_answer=None, rm_fails=None):
        import test_install
        calls = []

        def fake_docker(*args, **kwargs):
            calls.append(args[:3])
            if args[0] == 'rm':
                if rm_fails is not None:
                    raise rm_fails
                for name in [name for name, c in live.items() if c['Id'] == args[-1]]:
                    del live[name]
            if args[0] == 'stop':
                for name in [name for name in live if name == args[-1]]:
                    live[name]['State']['Running'] = False
            return mock.Mock(returncode=0, stdout=b'', stderr=b'')

        def in_image(image_id, env_bytes, body, params, **kwargs):
            if body == install.END_EVERY_SESSION:
                calls.append(('end_sessions', image_id, params['from_revision'], params['to_revision']))
                if isinstance(session_answer, BaseException):
                    raise session_answer
                return {'ended': 2, 'event': EVENT_ID}
            assert body == install.CODING_MADE, body[:60]
            return {'coding': {'encounters': [], 'created': [], 'rounds': 0, 'answers': 0,
                               'decisions': {'approve': 0, 'reject': 0, 'revoke': 0}, 'approved': 0,
                               'exports': {'draft': 0, 'approved': 0}}}
        ctx = install.Context(mock.Mock(phase='rollback-app', revision=self.REVISION), self.tmp)
        with mock.patch.multiple(install, inspect=lambda kind, name: live.get(name), docker=fake_docker,
                                 read_protected_env=mock.Mock(return_value=b''), require_db=mock.Mock(),
                                 undo_hazards=mock.Mock(return_value={}),
                                 close_undone_stages=mock.Mock(return_value={'closed': 0, 'kinds': [], 'hazards': {},
                                                                             'relabel': []}),
                                 put_back_states=mock.Mock(return_value={'encounters': 0, 'changed': {}}),
                                 stage_kinds_of=mock.Mock(return_value=list(install.COMMON_STAGE_KINDS)),
                                 app_script=in_image, keep_container_log=mock.Mock(return_value={'kept': 0})), \
                mock.patch.object(test_install, 'PRE_SESSION_POLICY_REVISIONS', set(pre_policy)):
            try:
                return install.phase_rollback_app(ctx), None, calls
            except install.InstallError as error:
                return None, error, calls

    def test_every_session_is_ended_before_the_pair_is_removed_when_what_runs_next_lacks_the_policy(self):
        for parked, to_revision, said in ((self.OLD, self.OLD, f'{self.REVISION[:12]} and {self.OLD[:12]} do not share'),
                                          (None, None, 'the revision that runs after')):
            with self.subTest(parked=parked):
                details, error, calls = self.run_phase(self.containers(parked))
                self.assertIsNone(error, error and str(error))
                names = [call[0] for call in calls]
                end = calls.index(('end_sessions', self.IMAGE, self.REVISION, to_revision))
                self.assertEqual(names[:2], ['stop', 'stop'])  # the pair is stopped first: no sign-in follows the end
                self.assertNotIn('rm', names[:end])  # and it is removed only after the end
                self.assertIn('rm', names[end:])
                record = details['sessions_ended']
                self.assertEqual((record['ended'], record['event'], record['to_revision']), (2, EVENT_ID, to_revision))
                self.assertIn(said, details['summary'])

    def test_a_parked_pair_with_the_policy_ends_none(self):
        details, error, calls = self.run_phase(self.containers(self.LATER))
        self.assertIsNone(error, error and str(error))
        self.assertFalse([call for call in calls if call[0] == 'end_sessions'])
        self.assertNotIn('sessions_ended', details)

    def test_an_end_that_fails_leaves_the_pair_stopped_and_not_removed(self):
        for failure in (install.InstallError('Ending every session failed (exit 1).'), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__):
                live = self.containers(None)
                details, error, calls = self.run_phase(live, session_answer=failure)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn('Web and worker stopped, not removed: the end of every session did not finish', str(error))
                self.assertIn('it may have ended every session', str(error))
                self.assertFalse([call for call in calls if call[0] == 'rm'])
                self.assertEqual(sorted(live), [install.SERVICES['web'], install.SERVICES['worker']])
                self.assertTrue(error.details['sessions_ended']['started_at'])

    def test_a_removal_that_fails_after_the_end_says_every_session_was_ended(self):
        details, error, calls = self.run_phase(self.containers(None),
                                               rm_fails=install.InstallError('docker rm failed (exit 1).'))
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('Every session was ended (2; SecurityEvent sessions.ended_at_install)', str(error))
        self.assertEqual(error.details['sessions_ended']['ended'], 2)

    def test_a_parked_pair_whose_policy_cannot_be_read_refuses_before_anything_is_stopped(self):
        cannot = install.InstallError(f'Cannot tell whether {self.OLD[:12]} has release 1\'s session policy: this '
                                      'checkout cannot read that revision.')
        with mock.patch.object(install, 'has_session_policy', side_effect=cannot):
            details, error, calls = self.run_phase(self.containers(self.OLD))
        self.assertIn('Nothing was stopped or removed.', str(error))
        self.assertEqual(calls, [])


# --- I2-4: what the guide says passes after a switch-back to the pair before release 1 --------------------------------

class SwitchBackVerificationGuideTests(unittest.TestCase):
    OPS = Path(__file__).resolve().parent

    def said(self):
        return ' '.join((self.OPS / 'INSTALL.md').read_text(encoding='utf-8').split())

    def test_the_guide_no_longer_says_release_1s_tools_pass_against_the_pair_before_it(self):
        said = self.said()
        # switchback-1: the sentence that said the walk, verify_login.py and scan_customer.py pass after a switch-back
        self.assertNotIn('and so do the walk (`--release <its revision>`: it reads B7 from that tree) and '
                         '`verify_login.py` and `scan_customer.py`', said)
        for phrase in ("Release 1's own `verify_login.py`, `scan_customer.py` and walk do not, and are not meant to",
                       'Each fails closed - a fail, never a pass',
                       "Run that pair's own tools instead, from a checkout of its revision",
                       "its `ops/verify_login.py` and `ops/scan_customer.py` send its own client version and read its "
                       'own contract, and pass against it'):
            with self.subTest(phrase=phrase[:40]):
                self.assertIn(phrase, said)

    def test_the_facts_it_gives_for_why_are_the_tools_own(self):
        said = self.said()
        sys.path.insert(0, str(self.OPS))
        import verify_login  # noqa: E402 - the release's own tool, read for its client version
        self.assertIn(f'`X-CPT-Studio-Client: {verify_login.CLIENT_VERSION}`', said)
        walk = (self.OPS / 'walk.cjs').read_text(encoding='utf-8')
        self.assertIn(f"const CLIENT_HEADERS = {{ 'X-CPT-Studio-Client': '{verify_login.CLIENT_VERSION}' }};", walk)
        contract = (self.OPS / 'verification' / 'customer-contract.json').read_text(encoding='utf-8')
        self.assertIn('"can_manage_team"', contract)
        self.assertIn('(`can_manage_team`)', said)


# --- I2-5: an option given more than once ---------------------------------------------------------------------------------

class RepeatedOptionTests(TemporaryDirectoryTest):
    def main(self, *extra, phase='manage'):
        """install.main for ``extra`` (REASON / LEDGER stand for real files), the host stood in as ManageWorld does and
        the door and tree checks answered: (exit code, the receipt, the world, the door check's mock)."""
        world = r1.ManageWorld(self.tmp)
        (self.tmp / 'reason.txt').write_bytes(b'Ticket 4521: the practice asked to end access.\n')
        (self.tmp / 'reason-2.txt').write_bytes(b'Ticket 4522: the other practice asked to end access.\n')
        (self.tmp / 'ledger.json').write_bytes(b'{"ledger": []}\n')
        receipts = self.tmp / 'receipts'
        argv = ['--phase', phase, '--revision', r1.REVISION, '--receipts', str(receipts)]
        argv += [str(self.tmp / 'reason.txt') if part == 'REASON' else str(self.tmp / 'reason-2.txt')
                 if part == 'REASON2' else str(self.tmp / 'ledger.json') if part == 'LEDGER' else part for part in extra]
        door = mock.Mock(return_value={'declaration': r1.DECLARATION, 'declaration_commit': r1.COMMIT,
                                       'declaration_sha256': '0' * 64})
        printed, locks, real_open = io.StringIO(), [], install.os.open

        def tracking_open(path, flags, mode=0o777, *, dir_fd=None):  # main() keeps <receipts>/.lock open, as a process
            fd = real_open(path, flags, mode, dir_fd=dir_fd)  # does until it exits: closed after each run here
            if str(path).endswith('/.lock'):
                locks.append(fd)
            return fd
        try:
            with mock.patch.multiple(install, installed_image=mock.Mock(return_value='sha256:' + 'c' * 64),
                                     require_db=mock.Mock(), oneshot=world.oneshot, inspect=world.inspect,
                                     root_file=world.root, run_helper=world.run_helper, read_protected_env=mock.Mock(
                                         return_value=f'CPT_STUDIO_SECRET_KEY={r1.SECRET_VALUE}\n'.encode()),
                                     app_script=world.app_script, check_door=door,
                                     check_tree=mock.Mock(return_value={'mode': 'exact'})), \
                    mock.patch.object(install.os, 'open', tracking_open), \
                    mock.patch('sys.stdout', printed), mock.patch('sys.stderr', io.StringIO()):
                code = install.main(argv)
        finally:
            for fd in locks:
                install.os.close(fd)
        (path,) = receipts.glob(f'{phase}-*.json')
        record = json.loads(path.read_text(encoding='utf-8'))
        path.unlink()
        return code, record, world, door

    # the finding's three inputs and the verifier's three (the shape of a command line edited from an earlier one)
    REPEATED = {
        '--workspace-id': ('--command', 'dispose', '--dispose-step', 'close', '--workspace-id', r1.WORKSPACE,
                           '--reason-file', 'REASON', '--by', 'Ada Lovelace', '--workspace-id',
                           '9b2e7c41-3f6d-4c8a-b1e5-6a7d8c9e0f12'),
        '--encounter-id': ('--command', 'dispose', '--dispose-step', 'plan', '--encounter-id', r1.PLAN, '--reason-file',
                           'REASON', '--by', 'Ada Lovelace', '--encounter-id', '9b2e7c41-3f6d-4c8a-b1e5-6a7d8c9e0f12'),
        '--username': ('--command', 'revoke-operator', '--username', 'ops-agent', '--reason-file', 'REASON', '--by',
                       'Ada Lovelace', '--username', 'platform-operator'),
        '--dispose-step': ('--command', 'dispose', '--dispose-step', 'plan', '--workspace-id', r1.WORKSPACE,
                           '--reason-file', 'REASON', '--by', 'Ada Lovelace', '--dispose-step', 'close'),
        '--reason-file': ('--command', 'dispose', '--dispose-step', 'close', '--workspace-id', r1.WORKSPACE,
                          '--reason-file', 'REASON', '--by', 'Ada Lovelace', '--reason-file', 'REASON2'),
        '--command': ('--command', 'export-workspace', '--workspace-id', r1.WORKSPACE, '--reason-file', 'REASON',
                      '--by', 'Ada Lovelace', '--command', 'dispose', '--dispose-step', 'close'),
    }

    def test_an_option_given_twice_is_refused_before_anything_runs_and_the_receipt_names_it(self):
        for option, extra in self.REPEATED.items():
            with self.subTest(option=option):
                code, record, world, door = self.main(*extra)
                self.assertEqual((code, record['ok']), (1, False))
                self.assertIn(f'{option} given more than once', record['error'])
                self.assertIn('nothing was run', record['error'])
                self.assertEqual(record['details'], {'given_more_than_once': [option]})
                self.assertEqual(world.oneshots, [])  # not even the migration check
                door.assert_not_called()  # before the door: nothing at all ran
        # control: the same command lines, each option once, run
        once = self.REPEATED['--workspace-id'][:-2]
        code, record, world, door = self.main(*once)
        self.assertEqual((code, record['ok']), (0, True), record.get('error'))
        self.assertEqual(world.acts()[0][:4], ['manage', 'dispose', '--close', '--workspace'])

    def test_the_equals_form_a_flag_and_another_phase_are_refused_too(self):
        for label, phase, extra, option in (
                ('--name=value', 'manage', ('--command', 'dispose', '--dispose-step', 'close',
                                            f'--workspace-id={r1.WORKSPACE}', '--reason-file', 'REASON', '--by',
                                            'Ada Lovelace', '--workspace-id', '9b2e7c41-3f6d-4c8a-b1e5-6a7d8c9e0f12'),
                 '--workspace-id'),
                ('a flag', 'manage', ('--command', 'dispose', '--dispose-step', 'replay-ledger', '--ledger-file',
                                      'LEDGER', '--execute', '--approved-by', 'Grace Hopper', '--by', 'Ada Lovelace',
                                      '--execute'), '--execute'),
                ('the same value twice', 'manage', ('--command', 'revoke-operator', '--username', 'ops-agent',
                                                    '--reason-file', 'REASON', '--by', 'Ada Lovelace', '--by',
                                                    'Ada Lovelace'), '--by'),
                ('another phase', 'app', ('--coding-mode', 'disabled', '--coding-mode', 'disabled'), '--coding-mode')):
            with self.subTest(label):
                code, record, world, door = self.main(*extra, phase=phase)
                self.assertEqual((code, record['ok']), (1, False))
                self.assertEqual(record['details'], {'given_more_than_once': [option]})
                self.assertEqual(world.oneshots, [])
                door.assert_not_called()

    def test_every_option_is_counted_whichever_it_is(self):
        # a census over every option the parser has, read from the parser itself: each named '--' and its destination
        seen = {}
        real = install.argparse.ArgumentParser.parse_args

        def parse_args(parser, *args, **kwargs):
            seen['parser'] = parser
            return real(parser, *args, **kwargs)
        with mock.patch.object(install.argparse.ArgumentParser, 'parse_args', parse_args), \
                mock.patch('sys.stderr', io.StringIO()), mock.patch.object(install, 'argument_problem', return_value=''):
            args = install.parse_args(['--revision', r1.REVISION, '--receipts', '/r', '--phase', 'verify'])
        options = [option for action in seen['parser']._actions for option in action.option_strings
                   if option.startswith('--') and option != '--help']
        self.assertEqual(sorted(options), sorted('--' + name.replace('_', '-') for name in vars(args)))
        for option in options:
            with self.subTest(option=option):
                for argv in ([option, 'x', option, 'y'], [f'{option}=x', option, 'y'], [option, option]):
                    self.assertEqual(install.repeated_options(argv, args), [option])
                self.assertEqual(install.repeated_options([option, 'x', '--', option], args), [])
                self.assertEqual(install.repeated_options([option, 'x'], args), [])


if __name__ == '__main__':
    unittest.main()
