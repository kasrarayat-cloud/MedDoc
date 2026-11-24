"""Release 1's installer items (RELEASE-1-SPEC A3's database half, A5, A6, A8, B7's installer side, Section 1.3's
sentences): offline, every Docker, root-helper and in-image call replaced by a fake, under test_install's host guard.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1 -v
"""
import ast
import hashlib
import io
import json
import os
import stat
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import FakeOwnership, TemporaryDirectoryTest, guard_host, release_host, run_body  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40
OTHER = 'b' * 40
RULING = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
BASE = ['--revision', REVISION, '--receipts', '/tmp/cpt-receipts']


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


def settings_literal(name):
    """A module-level string literal of cptstudio/settings.py (read with ast; nothing is imported)."""
    for node in ast.parse((APP_ROOT / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(getattr(target, 'id', None) == name for target in node.targets):
            return ast.literal_eval(node.value)
    raise LookupError(name)


def healthy(**fields):
    return {'status': 'ok', 'service': 'cpt-studio', 'data_mode': 'synthetic-only', 'database': 'ok', **fields}


def parse(*extra):
    with mock.patch('sys.stderr', io.StringIO()):
        return install.parse_args([*BASE, *extra])


def refused(*extra) -> str:
    stderr = io.StringIO()
    with mock.patch('sys.stderr', stderr):
        try:
            install.parse_args([*BASE, *extra])
        except SystemExit as exc:
            assert exc.code == 2, exc.code
            return stderr.getvalue()
    raise AssertionError(f'{extra} was accepted')


class HealthDigestTests(unittest.TestCase):
    """B7, the installer side: either shape of /health/ is read, and a wrong digest is refused."""

    def test_the_digest_is_the_settings_prefix_and_the_release_cut_to_16_hex(self):
        self.assertEqual(install.HEALTH_DIGEST_PREFIX, settings_literal('HEALTH_DIGEST_PREFIX'))
        expected = hashlib.sha256(('cpt-studio-release:' + REVISION).encode()).hexdigest()[:16]
        self.assertEqual(install.release_digest(REVISION), expected)
        self.assertRegex(install.release_digest(REVISION), r'^[0-9a-f]{16}$')
        self.assertNotEqual(install.release_digest(REVISION), install.release_digest(OTHER))

    def test_health_ok_accepts_either_shape_and_refuses_a_wrong_or_missing_build(self):
        digest = install.release_digest(REVISION)
        self.assertTrue(install.health_ok(healthy(release=REVISION), REVISION))  # the loopback port, an older web
        self.assertTrue(install.health_ok(healthy(release_digest=digest), REVISION))  # through nginx, release 1
        self.assertTrue(install.health_ok(healthy(release=REVISION, release_digest=digest), REVISION))
        for label, body in (('another release', healthy(release=OTHER)),
                            ('another digest', healthy(release_digest=install.release_digest(OTHER))),
                            ('a release given as a digest', healthy(release_digest=REVISION)),
                            ('a digest given as a release', healthy(release=digest)),
                            ('no build at all', healthy()),
                            ('the two disagree', healthy(release=REVISION, release_digest=install.release_digest(OTHER))),
                            ('a sick database', {**healthy(release_digest=digest), 'database': 'unavailable'}),
                            ('not an object', [healthy(release=REVISION)])):
            with self.subTest(label):
                self.assertFalse(install.health_ok(body, REVISION))

    def test_the_public_path_and_the_availability_record_read_the_digest(self):
        digest = install.release_digest(REVISION)
        with mock.patch.object(install, 'probe', return_value={'status': 200, 'json': healthy(release_digest=digest)}):
            passed, observations = install.public_health(REVISION)
        self.assertTrue(passed)
        recorder = install.AvailabilityRecorder(check=lambda: {'status': 200, 'json': healthy(release_digest=digest)})
        recorder.sample()
        recorder.check = lambda: {'status': 200, 'json': healthy(release=OTHER)}
        recorder.sample()
        self.assertEqual(recorder.record['releases_seen'], [digest, OTHER])  # whichever each answer carried
        self.assertEqual(install.health_release(healthy()), None)


class LegacyVendorTests(unittest.TestCase):
    """A8: no way back to a vendor that has no BAA, in app or in switch-back; the disabled starts still work."""

    def test_each_live_legacy_mode_is_refused_in_a_switch_back_whatever_authority_is_given(self):
        for flag in ('--provider-mode', '--astra-mode', '--fable-mode', '--interpreter-mode'):
            modes = {'--provider-mode': 'disabled', flag: 'live'}
            argv = ['--phase', 'switch-back', *[part for item in modes.items() for part in item]]
            for authority in ((), ('--authorization-ref', RULING)):
                with self.subTest(flag=flag, authority=authority):
                    said = refused(*argv, *authority)
                    self.assertIn(f'{flag} live is refused', said)
                    self.assertIn('business associate agreement', said)
        # an app phase names none of them at all (its pair runs them disabled)
        for flag in ('--provider-mode', '--astra-mode', '--fable-mode', '--interpreter-mode'):
            with self.subTest(app=flag):
                self.assertIn(f'{flag} is not used by --phase app',
                              refused('--phase', 'app', '--coding-mode', 'disabled', flag, 'live'))

    def test_the_disabled_starts_and_a_replayed_interpreter_still_parse(self):
        args = parse('--phase', 'switch-back', '--provider-mode', 'disabled', '--astra-mode', 'disabled',
                     '--fable-mode', 'disabled', '--interpreter-mode', 'replay')
        self.assertEqual((args.provider_mode, args.astra_mode, args.fable_mode, args.interpreter_mode),
                         ('disabled', 'disabled', 'disabled', 'replay'))
        args = parse('--phase', 'switch-back', '--provider-mode', 'disabled', '--coding-mode', 'live',
                     '--authorization-ref', RULING)
        self.assertEqual((args.provider_mode, args.coding_mode), ('disabled', 'live'))  # the Fable coder is not legacy

    def test_the_credentials_check_refuses_them_too_before_reading_anything(self):
        with mock.patch.object(install, 'helper_stat', side_effect=AssertionError('read a credentials path')):
            for mode, live, interpreter in (('live', [], 'disabled'), ('disabled', ['astra'], 'disabled'),
                                            ('disabled', ['fable'], 'disabled'), ('disabled', [], 'live')):
                with self.subTest(mode=mode, live=live, interpreter=interpreter):
                    with self.assertRaisesRegex(install.InstallError, 'live is refused'):
                        install.check_credential_files(mode, live, interpreter)
            install.check_credential_files('disabled', [], 'disabled')  # nothing live: nothing to read
            install.check_credential_files('disabled', [], 'replay')



MIB = 2 ** 20
POSTGRES_ID = 'sha256:' + 'e' * 64


def db_container(*, memory=512 * MIB, swap=512 * MIB, cap_drop=('ALL',), core=True, shm=128 * MIB, running=True):
    """The database container as docker inspect shows it - by default exactly as db_args starts it."""
    return {'Id': 'db-1', 'Image': POSTGRES_ID, 'State': {'Running': running},
            'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'db'}},
            'NetworkSettings': {'Networks': {install.NETWORK: {}}},
            'HostConfig': {'PortBindings': {'5432/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(install.DB_PORT)}]},
                           'RestartPolicy': {'Name': 'unless-stopped'}, 'Memory': memory, 'MemorySwap': swap,
                           'CapDrop': list(cap_drop), 'ShmSize': shm,
                           'Ulimits': [{'Name': 'core', 'Soft': 0, 'Hard': 0}] if core else []}}


class DbWorld:
    """The database container and its cgroup, as phase_db reads and changes them; every docker call recorded."""

    def __init__(self, container, *, peak=200 * MIB, swapped=30 * MIB, swap_max='max', shown=None, cgroup_readable=True):
        self.container, self.calls = container, []
        self.cgroup = {'memory.max': str(container['HostConfig']['Memory']) if container['HostConfig']['Memory']
                       else 'max', 'memory.swap.max': swap_max, 'memory.peak': str(peak),
                       'memory.swap.current': str(swapped)}
        self.cgroup_readable = cgroup_readable
        self.settings = {'log_min_error_statement': 'error', 'log_error_verbosity': 'default'}
        self.shown = shown  # what SHOW answers whatever was set (None: what was set)

    def inspect(self, kind, name):
        if kind == 'image':
            return {'Id': POSTGRES_ID} if name == install.POSTGRES_IMAGE else None
        return json.loads(json.dumps(self.container)) if name == install.DB_CONTAINER else None

    def docker(self, *args, **kwargs):
        self.calls.append(args)
        out = b''
        if args[:3] == ('exec', install.DB_CONTAINER, 'sh'):
            if self.cgroup_readable:
                out = ''.join(f'{name}={value}\n' for name, value in self.cgroup.items()).encode()
        elif args[:3] == ('exec', install.DB_CONTAINER, 'psql'):
            commands = [args[i + 1] for i, part in enumerate(args) if part == '-c']
            if all(command.startswith('SHOW ') for command in commands):
                shown = self.shown if self.shown is not None else self.settings
                out = ''.join(f'{shown[command[5:]]}\n' for command in commands).encode()
            else:
                for command in commands:
                    if command.startswith('ALTER SYSTEM SET '):
                        name, _, value = command[len('ALTER SYSTEM SET '):].partition(' = ')
                        self.settings[name] = value.strip("'")
        elif args[0] == 'update':
            self.container['HostConfig'].update(Memory=512 * MIB, MemorySwap=512 * MIB)
            self.cgroup.update({'memory.max': str(512 * MIB), 'memory.swap.max': '0'})
        elif args[0] in ('start', 'run'):
            pass
        else:
            raise AssertionError(f'unexpected docker {args}')
        return SimpleNamespace(returncode=0, stdout=out, stderr=b'')

    def patches(self):
        return [mock.patch.multiple(install, inspect=self.inspect, docker=self.docker, wait_db_ready=mock.Mock(),
                                    ensure_network=mock.Mock(return_value='present'),
                                    ensure_volume=mock.Mock(return_value='present'),
                                    files_volume_helper=mock.Mock(return_value={'root': 'owned'}),
                                    read_protected_env=mock.Mock(return_value=b'POSTGRES_PASSWORD=synthetic\n'),
                                    port_problem=mock.Mock(return_value=''))]

    def run(self, tmp):
        patches = self.patches()
        for patcher in patches:
            patcher.start()
        try:
            ctx = install.Context(SimpleNamespace(phase='db', revision=REVISION, receipts=str(tmp)), tmp)
            return install.phase_db(ctx), None
        except install.InstallError as error:
            return None, error
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def acts(self, verb):
        return [call for call in self.calls if call[0] == verb]


class DatabaseMemoryTests(TemporaryDirectoryTest):
    """A3, the database half: no swap for the database - an existing container updated in place when its peak allows,
    drift reported - and its hardening held."""

    def test_db_args_start_it_with_no_swap_and_the_two_log_settings_after_the_image(self):
        argv = install.db_args()
        self.assertEqual(argv[argv.index('--memory') + 1], argv[argv.index('--memory-swap') + 1])
        self.assertEqual(argv[argv.index('--memory') + 1], '512m')
        after = argv[argv.index(install.POSTGRES_IMAGE) + 1:]
        self.assertEqual(after, ['-c', 'log_min_error_statement=panic', '-c', 'log_error_verbosity=terse'])
        for flag in ('--cap-drop', '--shm-size', '--ulimit'):
            self.assertIn(flag, argv[:argv.index(install.POSTGRES_IMAGE)])

    def test_db_container_problems_reports_swap_and_every_hardening_drift(self):
        good = {'memory.max': str(512 * MIB), 'memory.swap.max': '0'}
        self.assertEqual(install.db_container_problems(db_container(), POSTGRES_ID, good), [])
        cases = {'cgroup swap max': (db_container(), {**good, 'memory.swap.max': 'max'}, 'allows swap'),
                 'unlimited swap': (db_container(swap=-1), good, 'memory and swap limits'),
                 'no memory limit': (db_container(memory=0, swap=0), good, 'memory and swap limits'),
                 'capabilities': (db_container(cap_drop=()), good, 'every capability'),
                 'core dumps': (db_container(core=False), good, 'core dumps'),
                 'shm': (db_container(shm=64 * MIB), good, '/dev/shm')}
        for label, (container, cgroup, said) in cases.items():
            with self.subTest(label):
                problems = install.db_container_problems(container, POSTGRES_ID, cgroup)
                self.assertEqual(len(problems), 1, problems)
                self.assertIn(said, problems[0])
        # the db phase's read before its in-place update leaves the memory limits out
        self.assertEqual(install.db_container_problems(db_container(swap=-1), POSTGRES_ID, memory=False), [])

    def test_an_existing_container_with_swap_is_updated_in_place_with_exactly_those_arguments(self):
        world = DbWorld(db_container(swap=-1), peak=200 * MIB, swapped=30 * MIB)
        details, error = world.run(self.tmp)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(world.acts('update'), [('update', '--memory', '512m', '--memory-swap', '512m',
                                                 install.DB_CONTAINER)])
        memory = details['memory']
        self.assertEqual(memory['state'], 'updated')
        self.assertEqual((memory['before']['memory_swap'], memory['after']['memory_swap']), (-1, 512 * MIB))
        self.assertEqual((memory['before']['cgroup']['memory.swap.max'], memory['after']['cgroup']['memory.swap.max']),
                         ('max', '0'))
        self.assertEqual((memory['peak'], memory['swap_before']), (200 * MIB, 30 * MIB))
        self.assertEqual(world.acts('run'), [])  # never recreated: no restart, no connection dropped

    def test_a_container_whose_cgroup_swaps_despite_its_hostconfig_is_updated_too(self):
        world = DbWorld(db_container(), swap_max='max')
        details, error = world.run(self.tmp)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(len(world.acts('update')), 1)
        self.assertEqual(details['cgroup']['memory.swap.max'], '0')

    def test_a_high_peak_or_an_unreadable_cgroup_refuses_and_changes_nothing(self):
        for label, world, said in (
                ('peak', DbWorld(db_container(swap=-1), peak=int(0.8 * 512 * MIB)), 'not below 80%'),
                ('unreadable', DbWorld(db_container(swap=-1), cgroup_readable=False), 'cannot be read')):
            with self.subTest(label):
                details, error = world.run(self.tmp)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn(said, str(error))
                self.assertEqual(world.acts('update'), [])
                self.assertEqual([call for call in world.calls if 'ALTER SYSTEM' in ' '.join(call)], [])

    def test_hardening_drift_refuses_before_anything_changes(self):
        world = DbWorld(db_container(swap=-1, cap_drop=()))
        details, error = world.run(self.tmp)
        self.assertIn('does not drop every capability', str(error))
        self.assertIn("owner's call", str(error))
        self.assertEqual((world.acts('update'), world.acts('exec')), ([], []))

    def test_a_container_as_installed_is_left_as_it_is(self):
        world = DbWorld(db_container(), swap_max='0')
        details, error = world.run(self.tmp)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['memory']['state'], 'as installed')
        self.assertEqual(world.acts('update'), [])


class StatementLoggingTests(TemporaryDirectoryTest):
    """A5: the database's own log never holds statement text."""

    def test_alter_system_then_a_reload_then_show_reads_both_settings(self):
        world = DbWorld(db_container(), swap_max='0')
        details, error = world.run(self.tmp)
        self.assertIsNone(error, error and str(error))
        altered = [call for call in world.calls if call[:3] == ('exec', install.DB_CONTAINER, 'psql')
                   and any('ALTER SYSTEM' in part for part in call)]
        self.assertEqual(len(altered), 1)
        statements = [altered[0][i + 1] for i, part in enumerate(altered[0]) if part == '-c']
        self.assertEqual(statements, ["ALTER SYSTEM SET log_min_error_statement = 'panic'",
                                      "ALTER SYSTEM SET log_error_verbosity = 'terse'", 'SELECT pg_reload_conf()'])
        self.assertEqual(details['statement_logging']['shown'], {'log_min_error_statement': 'panic',
                                                                 'log_error_verbosity': 'terse'})
        self.assertIn('-U', altered[0])
        self.assertEqual(altered[0][altered[0].index('-U') + 1], install.DB_USER)

    def test_a_show_that_does_not_read_as_set_refuses(self):
        for shown in ({'log_min_error_statement': 'error', 'log_error_verbosity': 'terse'},
                      {'log_min_error_statement': 'panic', 'log_error_verbosity': 'verbose'}):
            with self.subTest(shown=shown), mock.patch.object(install.time, 'sleep'):
                world = DbWorld(db_container(), swap_max='0', shown=shown)
                details, error = world.run(self.tmp)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn('does not read as set', str(error))

    def test_the_cgroup_reading_is_name_value_lines_and_ignores_anything_else(self):
        answer = SimpleNamespace(returncode=0, stdout=b'memory.max=536870912\nmemory.swap.max=0\nnoise\nother=1\n'
                                                      b'memory.peak=12\n', stderr=b'')
        with mock.patch.object(install, 'docker', return_value=answer) as docker:
            self.assertEqual(install.db_cgroup(), {'memory.max': '536870912', 'memory.swap.max': '0',
                                                   'memory.peak': '12'})
        args = docker.call_args[0]
        self.assertEqual(args[:4], ('exec', install.DB_CONTAINER, 'sh', '-c'))
        for name in install.DB_CGROUP_FILES:
            self.assertIn(name, args[4])



REVIEW_BY = (__import__('datetime').date.today() + __import__('datetime').timedelta(days=90)).isoformat()
WORKSPACE = '7a1c2e9b-4d3f-4b8a-9c6d-0e1f2a3b4c5d'
PLAN = '1b2c3d4e-5f60-4718-8293-a4b5c6d7e8f9'
DECLARATION = 'docs/foundation/mutations/x.md'
COMMIT = 'd' * 40
SECRET_VALUE = 'S' * 48


class ManageArgumentTests(unittest.TestCase):
    """A6: --phase manage runs one allow-listed act, each with the arguments it needs and no other."""

    def manage(self, *extra):
        return ('--phase', 'manage', *extra)

    def test_a_command_not_on_the_allowlist_is_refused(self):
        self.assertEqual(sorted(install.MANAGE_COMMANDS), sorted([
            'revoke-operator', 'grant-operator', 'issue-enrolment', 'reset-second-factor', 'clear-signin-failures',
            'require-password-change', 'dispose', 'export-workspace']))
        for command in ('provision', 'shell', 'migrate', 'flush', 'createsuperuser', 'grant_operator', 'loaddata'):
            with self.subTest(command=command):
                self.assertIn('invalid choice', refused(*self.manage('--command', command, '--by', 'Ada Lovelace')))
        self.assertIn('needs --command', refused(*self.manage()))

    def test_each_act_needs_its_arguments_and_takes_no_other(self):
        reason = ('--reason-file', '/srv/reason.txt')
        by = ('--by', 'Ada Lovelace')
        accepted = [
            ('--command', 'revoke-operator', '--username', 'ops-agent', *reason, *by),
            ('--command', 'grant-operator', '--username', 'platform-operator', *reason, *by, '--review-by', REVIEW_BY),
            ('--command', 'issue-enrolment', '--username', 'platform-operator', *reason, *by),
            ('--command', 'reset-second-factor', '--username', 'platform-operator', *reason, *by),
            ('--command', 'clear-signin-failures', '--username', 'owner', *reason, *by),
            ('--command', 'require-password-change', '--all-human-accounts', *reason, *by),
            ('--command', 'require-password-change', '--username', 'owner', *reason, *by),
            ('--command', 'dispose', '--dispose-step', 'close', '--workspace-id', WORKSPACE, *reason, *by),
            ('--command', 'dispose', '--dispose-step', 'plan', '--workspace-id', WORKSPACE, *by),
            ('--command', 'dispose', '--dispose-step', 'plan', '--encounter-id', PLAN, *reason, *by),
            ('--command', 'dispose', '--dispose-step', 'execute', '--plan-id', PLAN, *by, '--approved-by', 'Grace Hopper',
             *reason),
            ('--command', 'dispose', '--dispose-step', 'ledger', *by),
            ('--command', 'dispose', '--dispose-step', 'replay-ledger', '--ledger-file', '/srv/ledger.json', *reason, *by),
            ('--command', 'export-workspace', '--workspace-id', WORKSPACE, *reason, *by),
        ]
        for extra in accepted:
            with self.subTest(accepted=extra):
                self.assertEqual(parse(*self.manage(*extra)).command, extra[1])
        refusals = {
            'no --by': (('--command', 'revoke-operator', '--username', 'ops-agent', *reason), 'needs --by'),
            'a role as --by': (('--command', 'revoke-operator', '--username', 'ops-agent', *reason, '--by', 'operator'),
                               'names a role'),
            'no reason': (('--command', 'revoke-operator', '--username', 'ops-agent', *by), 'needs --reason-file'),
            'a relative reason': (('--command', 'revoke-operator', '--username', 'ops-agent', '--reason-file', 'r.txt',
                                   *by), 'absolute'),
            'a grant without review date': (('--command', 'grant-operator', '--username', 'x-op', *reason, *by),
                                            'needs --review-by'),
            'a review date past': (('--command', 'grant-operator', '--username', 'x-op', *reason, *by, '--review-by',
                                    '2020-01-01'), 'after today'),
            'both kinds of require': (('--command', 'require-password-change', '--username', 'owner',
                                       '--all-human-accounts', *reason, *by), 'not both'),
            'neither kind of require': (('--command', 'require-password-change', *reason, *by), 'needs --username'),
            'one person runs and approves': (('--command', 'dispose', '--dispose-step', 'execute', '--plan-id', PLAN,
                                              *by, '--approved-by', 'ada lovelace', *reason), 'differ'),
            'an execute without a plan': (('--command', 'dispose', '--dispose-step', 'execute', *by, '--approved-by',
                                           'Grace Hopper', *reason), '--plan-id'),
            'an execute without a reason': (('--command', 'dispose', '--dispose-step', 'execute', '--plan-id', PLAN, *by,
                                             '--approved-by', 'Grace Hopper'), 'needs --reason-file'),
            'an approver outside execute': (('--command', 'dispose', '--dispose-step', 'close', '--workspace-id',
                                             WORKSPACE, *reason, *by, '--approved-by', 'Grace Hopper'),
                                            'belong to --dispose-step execute'),
            'a replay without its ledger': (('--command', 'dispose', '--dispose-step', 'replay-ledger', *reason, *by),
                                            '--ledger-file'),
            'a ledger file elsewhere': (('--command', 'dispose', '--dispose-step', 'ledger', '--ledger-file',
                                         '/srv/ledger.json', *by), '--ledger-file'),
            'an unknown step': (('--command', 'dispose', '--dispose-step', 'purge', *by), 'invalid choice'),
            'a workspace that is not a UUID': (('--command', 'export-workspace', '--workspace-id', 'Gastroenterology',
                                                *reason, *by), 'UUID'),
            'an argument the act does not use': (('--command', 'revoke-operator', '--username', 'ops-agent', *reason,
                                                  *by, '--workspace-id', WORKSPACE), 'not used by --command'),
            'a manage argument on another phase': (('--command', 'revoke-operator',), None),
        }
        for label, (extra, said) in refusals.items():
            with self.subTest(label):
                if said is None:
                    self.assertIn('not used by --phase verify', refused('--phase', 'verify', *extra))
                else:
                    self.assertIn(said, refused(*self.manage(*extra)))


class ManageWorld:
    """The host for --phase manage: one-shots recorded (with what their RAM-only files held), the root file a folder
    standing in for /etc/cpt-studio, containers by name."""

    def __init__(self, tmp, *, output=b'done\n', exit_code=0, containers=()):
        self.tmp, self.output, self.exit_code = tmp, output, exit_code
        self.etc = tmp / 'etc'
        self.etc.mkdir(mode=0o700, exist_ok=True)
        self.oneshots, self.mounted, self.containers = [], {}, set(containers)
        from test_install_bluegreen import FakeRootFile
        self.root = FakeRootFile(self.etc)
        self.helpers, self.owner = [], FakeOwnership()
        self.export_files = {}  # what the command writes into its --out folder: {name: bytes}

    def oneshot(self, image_id, command, env, **kwargs):
        self.oneshots.append((command, kwargs))
        if command == ['manage', 'migrate', '--check']:
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        for mount in kwargs.get('mounts', ()):
            if mount.startswith('type=bind') and not mount.endswith(f'dst={install.EXPORT_MOUNT}'):
                source = mount.split('src=', 1)[1].split(',', 1)[0]
                self.mounted[Path(source).name] = (Path(source).read_text(), stat.S_IMODE(os.stat(source).st_mode),
                                                   stat.S_IMODE(os.stat(Path(source).parent).st_mode))
        for mount in kwargs.get('mounts', ()):
            if mount.endswith(f'dst={install.EXPORT_MOUNT}'):  # the command writes its export into the folder
                folder = Path(mount.split('src=', 1)[1].split(',', 1)[0].replace(install.EXPORTS_DIR,
                                                                                    str(self.tmp / 'var-lib' /
                                                                                        'cpt-studio-exports')))
                for name, data in self.export_files.items():
                    (folder / name).parent.mkdir(parents=True, exist_ok=True)
                    (folder / name).write_bytes(data)
        output = self.output(command) if callable(self.output) else self.output
        return SimpleNamespace(returncode=self.exit_code, stdout=output, stderr=b'')

    def inspect(self, kind, name):
        return {'Id': name} if name in self.containers else None

    def run_helper(self, body, params, *, mounts, **kwargs):
        """The export folder's two helpers, their bodies run here on a temporary /var/lib."""
        assert mounts == [install.EXPORTS_MOUNT], mounts
        var_lib = self.tmp / 'var-lib'
        var_lib.mkdir(exist_ok=True)
        self.helpers.append(body)
        answer = run_body(body, params, {'/host-var-lib': str(var_lib)}, fake_os=self.owner)
        if answer.get('error'):
            raise install.InstallError(f'Root helper refused: {answer["error"]}')
        return answer

    def run(self, *extra, reason=b'Ticket 4521: the practice asked to end access.\n', ledger=b'{"ledger": []}\n'):
        path = self.tmp / 'reason.txt'
        path.write_bytes(reason)
        (self.tmp / 'ledger.json').write_bytes(ledger)
        argv = ['--phase', 'manage', *extra]
        argv = [str(path) if part == 'REASON' else str(self.tmp / 'ledger.json') if part == 'LEDGER' else part
                for part in argv]
        args = parse(*argv)
        args.receipts = str(self.tmp)
        ctx = install.Context(args, self.tmp)
        ctx.door = {'declaration': DECLARATION, 'declaration_commit': COMMIT}
        with mock.patch.multiple(install, installed_image=mock.Mock(return_value='sha256:' + 'c' * 64),
                                 require_db=mock.Mock(), oneshot=self.oneshot, inspect=self.inspect,
                                 root_file=self.root, run_helper=self.run_helper, read_protected_env=mock.Mock(
                                     return_value=f'CPT_STUDIO_SECRET_KEY={SECRET_VALUE}\n'.encode())):
            return install.phase_manage(ctx)

    def acts(self):
        return [command for command, _ in self.oneshots if command != ['manage', 'migrate', '--check']]


class ManagePhaseTests(TemporaryDirectoryTest):
    """A6: the command lines the allow-listed acts are given, their RAM-only files, and receipts that hold no secret."""

    def test_revoke_operator_runs_the_command_with_its_reason_as_a_ram_only_file(self):
        world = ManageWorld(self.tmp)
        details = world.run('--command', 'revoke-operator', '--username', 'ops-agent', '--reason-file', 'REASON',
                            '--by', 'Ada Lovelace')
        self.assertEqual(world.acts(), [['manage', 'revoke_operator', '--username', 'ops-agent', '--reason-file',
                                         '/run/cpt-manage/reason', '--by', 'Ada Lovelace']])
        text, mode, folder = world.mounted['reason']
        self.assertEqual((text, mode, folder), ('Ticket 4521: the practice asked to end access.\n', 0o600, 0o700))
        command, kwargs = world.oneshots[-1]
        self.assertEqual(kwargs['user'], f'{os.getuid()}:{os.getgid()}')
        self.assertEqual(kwargs['what'], 'manage revoke_operator')
        self.assertEqual(kwargs['by'], 'Ada Lovelace')
        self.assertTrue(all(mount.startswith('type=bind,src=/dev/shm/') for mount in kwargs['mounts']))
        # the receipt keeps the reason's digest and size, never its text
        self.assertEqual(details['reason'], {'sha256': hashlib.sha256(b'Ticket 4521: the practice asked to end access.\n')
                                             .hexdigest(), 'bytes': 47})
        self.assertNotIn('Ticket 4521', json.dumps(details))
        self.assertFalse(list(Path('/dev/shm').glob('cpt-studio-manage-*')))

    def test_grant_operator_names_the_declaration_and_the_review_date(self):
        world = ManageWorld(self.tmp)
        world.run('--command', 'grant-operator', '--username', 'second-operator', '--reason-file', 'REASON', '--by',
                  'Ada Lovelace', '--review-by', REVIEW_BY)
        self.assertEqual(world.acts(), [['manage', 'grant_operator', '--username', 'second-operator', '--reason-file',
                                         '/run/cpt-manage/reason', '--by', 'Ada Lovelace', '--authorization-ref',
                                         f'{DECLARATION}@{COMMIT}', '--review-by', REVIEW_BY]])

    def test_issue_enrolment_keeps_the_code_root_only_and_never_in_output_argv_or_receipt(self):
        world = ManageWorld(self.tmp)
        details = world.run('--command', 'issue-enrolment', '--username', 'platform-operator', '--reason-file', 'REASON',
                            '--by', 'Ada Lovelace')
        code = json.loads((world.etc / install.OPERATOR_ENROLMENT).read_text())['code']
        self.assertEqual(world.mounted['code'][:2], (code, 0o600))
        self.assertEqual(world.acts(), [['manage', 'issue_enrolment', '--username', 'platform-operator', '--code-file',
                                         '/run/cpt-manage/code', '--reason-file', '/run/cpt-manage/reason', '--by',
                                         'Ada Lovelace']])
        self.assertNotIn(code, json.dumps(details))
        for path in self.tmp.glob('*.log'):
            self.assertNotIn(code, path.read_text())
        # a command that printed the code: nothing is kept, the staged code discarded
        again = self.tmp / 'again'
        again.mkdir()
        world = ManageWorld(again)
        world.output = lambda command: f'your code: {world.mounted["code"][0]}'.encode()
        with self.assertRaisesRegex(install.InstallError, 'secret appeared'):
            world.run('--command', 'reset-second-factor', '--username', 'platform-operator', '--reason-file', 'REASON',
                      '--by', 'Ada Lovelace')
        self.assertEqual(list(world.etc.iterdir()), [])  # neither the code nor its staged copy
        self.assertFalse([path for path in again.glob('*.log')])

    def test_an_application_secret_printed_by_an_act_is_never_kept(self):
        world = ManageWorld(self.tmp, output=f'settings: {SECRET_VALUE}'.encode())
        with self.assertRaisesRegex(install.InstallError, 'secret appeared'):
            world.run('--command', 'clear-signin-failures', '--username', 'owner', '--reason-file', 'REASON', '--by',
                      'Ada Lovelace')
        for path in self.tmp.glob('*.log'):
            self.assertNotIn(SECRET_VALUE, path.read_text())

    def test_a_disposal_is_refused_while_an_install_or_switch_back_is_in_progress(self):
        for leftover in (install.INCOMING_WEB, 'cpt-studio-web-previous', 'cpt-studio-worker-previous'):
            with self.subTest(leftover=leftover):
                world = ManageWorld(self.tmp, containers=[leftover])
                with self.assertRaisesRegex(install.InstallError, 'in progress'):
                    world.run('--command', 'dispose', '--dispose-step', 'close', '--workspace-id', WORKSPACE,
                              '--reason-file', 'REASON', '--by', 'Ada Lovelace')
                self.assertEqual(world.acts(), [])  # no one-shot, so nothing was told the switch is idle

    def test_a_disposal_is_told_the_switch_is_idle_only_after_the_check_and_runs_with_the_files_volume(self):
        world = ManageWorld(self.tmp, output=f'disposal {PLAN}: 12 rows, 3 files\n'.encode())
        details = world.run('--command', 'dispose', '--dispose-step', 'execute', '--plan-id', PLAN, '--by',
                            'Ada Lovelace', '--approved-by', 'Grace Hopper', '--reason-file', 'REASON')
        command, kwargs = world.oneshots[-1]
        self.assertEqual(command, ['manage', 'dispose', '--execute', '--plan', PLAN, '--by', 'Ada Lovelace',
                                   '--approved-by', 'Grace Hopper', '--reason-file', '/run/cpt-manage/reason',
                                   '--authorization-ref', f'{DECLARATION}@{COMMIT}'])
        self.assertIn('CPT_STUDIO_SWITCH_STATE=idle', kwargs['environment'])
        self.assertIn('CPT_STUDIO_PROVIDER_MODE=disabled', kwargs['environment'])
        self.assertNotIn('user', kwargs)  # the application's own uid: the files are its own
        self.assertIn(f'type=volume,src={install.FILES_VOLUME},dst={install.STATE_DIR}', kwargs['mounts'])  # read-write
        text, mode, folder = world.mounted['reason']
        self.assertEqual((mode, folder), (0o644, 0o711))  # readable by that uid; a reason, never a secret
        self.assertEqual(details['stdout'], f'disposal {PLAN}: 12 rows, 3 files\n')  # ids and counts, in the receipt
        self.assertEqual(details['step'], 'execute')
        # no other act is ever told the switch is idle
        world.run('--command', 'revoke-operator', '--username', 'ops-agent', '--reason-file', 'REASON', '--by',
                  'Ada Lovelace')
        self.assertNotIn('environment', world.oneshots[-1][1])

    def test_each_dispose_step_has_its_command_line(self):
        world = ManageWorld(self.tmp)
        authority = ['--authorization-ref', f'{DECLARATION}@{COMMIT}']
        steps = {
            ('close', '--workspace-id', WORKSPACE, '--reason-file', 'REASON'):
                ['--close', '--workspace', WORKSPACE, '--reason-file', '/run/cpt-manage/reason', '--by', 'Ada Lovelace',
                 *authority],
            ('plan', '--workspace-id', WORKSPACE): ['--plan', '--workspace', WORKSPACE, '--by', 'Ada Lovelace', *authority],
            ('plan', '--encounter-id', PLAN): ['--plan', '--encounter', PLAN, '--by', 'Ada Lovelace', *authority],
            ('ledger',): ['--ledger', '--by', 'Ada Lovelace', *authority],
            ('replay-ledger', '--ledger-file', 'LEDGER', '--reason-file', 'REASON'):
                ['--replay-ledger', '/run/cpt-manage/ledger', '--reason-file', '/run/cpt-manage/reason', '--by',
                 'Ada Lovelace', *authority],
        }
        for (step, *extra), expected in steps.items():
            with self.subTest(step=step, extra=extra):
                details = world.run('--command', 'dispose', '--dispose-step', step, *extra, '--by', 'Ada Lovelace')
                command, kwargs = world.oneshots[-1]
                self.assertEqual(command, ['manage', 'dispose', *expected])
                self.assertIn('CPT_STUDIO_SWITCH_STATE=idle', kwargs['environment'])
        # the replayed ledger travelled as a RAM-only file, its digest in the receipt, never its text
        self.assertEqual(world.mounted['ledger'][0], '{"ledger": []}\n')
        self.assertEqual(details['ledger'], {'sha256': hashlib.sha256(b'{"ledger": []}\n').hexdigest(), 'bytes': 15})

    def test_an_export_is_written_into_a_new_folder_that_is_then_root_only(self):
        world = ManageWorld(self.tmp, output=f'exported {WORKSPACE}: 2 documents\n'.encode())
        world.export_files = {'manifest.json': b'{}', 'documents/one/record.json': b'{"x": 1}'}
        details = world.run('--command', 'export-workspace', '--workspace-id', WORKSPACE, '--reason-file', 'REASON',
                            '--by', 'Ada Lovelace')
        command, kwargs = world.oneshots[-1]
        self.assertEqual(command, ['manage', 'export_workspace', '--workspace', WORKSPACE, '--out', '/run/cpt-export',
                                   '--reason-file', '/run/cpt-manage/reason', '--by', 'Ada Lovelace',
                                   '--authorization-ref', f'{DECLARATION}@{COMMIT}'])
        self.assertNotIn('environment', kwargs)  # an export is told nothing about the switch
        self.assertIn(f'type=volume,src={install.FILES_VOLUME},dst={install.STATE_DIR},readonly', kwargs['mounts'])
        folder = details['export']['folder']
        self.assertRegex(folder, rf'^{install.EXPORTS_DIR}/{WORKSPACE}-\d{{8}}T\d+Z$')
        self.assertIn(f'type=bind,src={folder},dst={install.EXPORT_MOUNT}', kwargs['mounts'])
        self.assertEqual(world.helpers, [install.H_EXPORT_DIR, install.H_SEAL_EXPORT])
        self.assertEqual((details['export']['files'], details['export']['folders'], details['export']['bytes']), (2, 3, 10))
        # everything in it is root's: the folders 0700 and the files 0600; the base folder too
        local = self.tmp / 'var-lib' / 'cpt-studio-exports'
        for path in [local, *local.rglob('*')]:
            self.assertEqual(world.owner.owners.get(str(path)), (0, 0), path)
            self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o700 if path.is_dir() else 0o600, path)
        self.assertEqual(details['stdout'], f'exported {WORKSPACE}: 2 documents\n')
        self.assertNotIn('record.json', json.dumps(details))  # counted, never named

    def test_an_export_that_fails_is_sealed_root_only_too_and_a_link_in_it_refuses(self):
        world = ManageWorld(self.tmp, exit_code=1)
        world.export_files = {'partial.json': b'{'}
        with self.assertRaisesRegex(install.InstallError, 'failed'):
            world.run('--command', 'export-workspace', '--workspace-id', WORKSPACE, '--reason-file', 'REASON', '--by',
                      'Ada Lovelace')
        self.assertEqual(world.helpers, [install.H_EXPORT_DIR, install.H_SEAL_EXPORT])
        (partial,) = (self.tmp / 'var-lib' / 'cpt-studio-exports').rglob('partial.json')
        self.assertEqual(stat.S_IMODE(os.stat(partial).st_mode), 0o600)
        # a link the command left refuses the seal, and nothing is changed
        folder = self.tmp / 'var-lib' / 'cpt-studio-exports' / 'linked'
        folder.mkdir()
        (folder / 'outside').symlink_to('/etc')
        world2 = ManageWorld(self.tmp)
        with self.assertRaisesRegex(install.InstallError, 'neither a folder nor a regular file'):
            world2.run_helper(install.H_SEAL_EXPORT, {'dir': 'cpt-studio-exports', 'name': 'linked'},
                              mounts=[install.EXPORTS_MOUNT])

    def test_require_password_change_for_every_human_account(self):
        world = ManageWorld(self.tmp)
        world.run('--command', 'require-password-change', '--all-human-accounts', '--reason-file', 'REASON', '--by',
                  'Ada Lovelace')
        self.assertEqual(world.acts(), [['manage', 'require_password_change', '--all-human-accounts', '--reason-file',
                                         '/run/cpt-manage/reason', '--by', 'Ada Lovelace']])

    def test_a_failed_act_fails_the_phase_and_a_bad_reason_file_runs_nothing(self):
        world = ManageWorld(self.tmp, exit_code=3)
        with self.assertRaisesRegex(install.InstallError, 'failed \\(exit 3\\)'):
            world.run('--command', 'revoke-operator', '--username', 'ops-agent', '--reason-file', 'REASON', '--by',
                      'Ada Lovelace')
        for reason in (b'', b'   \n', b'\xff\xfe', b'x' * 5000):
            with self.subTest(reason=reason[:8]):
                world = ManageWorld(self.tmp)
                with self.assertRaises(install.InstallError):
                    world.run('--command', 'revoke-operator', '--username', 'ops-agent', '--reason-file', 'REASON',
                              '--by', 'Ada Lovelace', reason=reason)
                self.assertEqual(world.acts(), [])

    def test_the_enrolment_code_lifetime_is_the_settings_one(self):
        self.assertEqual(install.ENROLMENT_CODE_SECONDS, ast.literal_eval(str(settings_number('ENROLMENT_CODE_SECONDS'))))


def settings_number(name):
    """A module-level number of cptstudio/settings.py (simple arithmetic allowed; nothing imported)."""
    for node in ast.parse((APP_ROOT / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(getattr(target, 'id', None) == name for target in node.targets):
            return eval(compile(ast.Expression(node.value), 'settings', 'eval'), {'__builtins__': {}})  # noqa: S307
    raise LookupError(name)



class CountsFallbackTests(unittest.TestCase):
    """RELEASE-1-SPEC 1.3 (TEC-8 (5)): when install_counts cannot read the counts, its report never sends the operator
    to a restored copy of live; it names the synthetic rehearsal of 6.4."""

    def test_the_fallback_report_names_the_synthetic_rehearsal_and_no_restored_copy(self):
        reports = []
        with mock.patch.object(install, 'app_script', side_effect=install.InstallError('Counting failed (exit 1).')):
            reports.append(install.install_counts('sha256:' + 'a' * 64, b''))
        with mock.patch.object(install, 'app_script', return_value={'size': 'not counted'}):
            reports.append(install.install_counts('sha256:' + 'a' * 64, b''))
        for counted in reports:
            self.assertFalse(counted['counted'])
            self.assertEqual(len(counted['report']), 1)
            said = counted['report'][0]
            self.assertIn('synthetic rehearsal on the test instance (RELEASE-1-SPEC 6.4)', said)
            self.assertIn('report them to the owner as not counted', said)
            self.assertNotIn('restored dump', said)
            self.assertNotRegex(said, r'read them on|before reporting')
        self.assertTrue(reports[0]['report'][0].startswith('the install counts were not read: '))
        self.assertTrue(reports[1]['report'][0].startswith('the install counts did not say what they read: '))
        self.assertNotIn('restored dump', Path(install.__file__).read_text())



LOCK_TIMEOUT_OUTPUT = (b'Applying studio.0017_r1_security...\n'
                       b'psycopg.errors.LockNotAvailable: canceling statement due to lock timeout\n')


class MigrateLockTimeoutTests(TemporaryDirectoryTest):
    """RELEASE-1-SPEC 6.2: the migrate one-shot waits at most 5 s for a table's lock (PGOPTIONS, never the migration
    files the gate reads) and is run again on a lock timeout alone, up to 3 more times."""

    def run_bounded(self, answers):
        calls, pauses = [], []

        def oneshot(image_id, command, env_bytes, **kwargs):
            calls.append((image_id, list(command), env_bytes, kwargs))
            return answers.pop(0)
        with mock.patch.object(install, 'oneshot', oneshot), \
                mock.patch.object(install.time, 'sleep', side_effect=pauses.append):
            done, output, attempts = install.migrate_bounded('sha256:' + 'a' * 64, b'ENV=1\n')
        return done, output, attempts, calls, pauses

    def answer(self, code=0, out=b'', err=b''):
        return SimpleNamespace(returncode=code, stdout=out, stderr=err)

    def test_the_one_shot_carries_a_5_s_lock_timeout_and_runs_once_when_it_succeeds(self):
        done, output, attempts, calls, pauses = self.run_bounded([self.answer(0, b'Applying studio.0017... OK\n')])
        self.assertEqual((done.returncode, attempts, pauses), (0, 1, []))
        image, command, env_bytes, kwargs = calls[0]
        self.assertEqual((command, env_bytes), (['migrate'], b'ENV=1\n'))
        environment = kwargs['environment']
        self.assertEqual(environment[-2:], ['-e', 'PGOPTIONS=-c lock_timeout=5s'])
        self.assertEqual(environment[:-2], install.runtime_env('disabled', ''))  # every provider disabled, as before
        self.assertIn(b'--- migrate attempt 1 (exit 0)', output)

    def test_a_lock_timeout_is_tried_again_and_the_attempts_are_logged(self):
        done, output, attempts, calls, pauses = self.run_bounded([
            self.answer(1, err=LOCK_TIMEOUT_OUTPUT), self.answer(1, err=LOCK_TIMEOUT_OUTPUT), self.answer(0, b'OK\n')])
        self.assertEqual((done.returncode, attempts, len(calls)), (0, 3, 3))
        self.assertEqual(pauses, [install.MIGRATE_RETRY_PAUSE] * 2)
        for number, code in ((1, 1), (2, 1), (3, 0)):
            self.assertIn(f'--- migrate attempt {number} (exit {code})'.encode(), output)

    def test_at_most_three_retries_then_the_failure_stands(self):
        done, output, attempts, calls, pauses = self.run_bounded([self.answer(1, err=LOCK_TIMEOUT_OUTPUT)] * 5)
        self.assertEqual((done.returncode, attempts, len(calls), len(pauses)), (1, 4, 4, 3))

    def test_any_other_failure_is_never_retried(self):
        for said in (b'django.db.utils.ProgrammingError: relation "studio_x" already exists\n',
                     b'django.db.utils.OperationalError: connection refused\n', b''):
            with self.subTest(said=said):
                done, output, attempts, calls, pauses = self.run_bounded([self.answer(1, err=said), self.answer(0)])
                self.assertEqual((done.returncode, attempts, len(calls), pauses), (1, 1, 1, []))

    def test_the_lock_timeout_shapes_postgres_and_psycopg_print(self):
        for said in (b'ERROR:  canceling statement due to lock timeout', b'psycopg.errors.LockNotAvailable',
                     b'SQLSTATE 55P03'):
            self.assertTrue(install.LOCK_TIMEOUT_RE.search(said), said)
        self.assertIsNone(install.LOCK_TIMEOUT_RE.search(b'canceling statement due to statement timeout'))

    def test_a_lock_timeout_set_inside_a_migration_would_be_refused_by_the_gate(self):
        # why it is PGOPTIONS: RunSQL that does anything but set column defaults is not a safe operation
        source = ('from django.db import migrations\n\n\nclass Migration(migrations.Migration):\n'
                  '    dependencies = []\n    operations = [migrations.RunSQL("SET lock_timeout = 5000")]\n')
        self.assertFalse(install.migration_verdict(source)['safe'])

    def test_app_reports_a_lock_that_stayed_taken_and_records_the_attempts(self):
        from test_install_bluegreen import BlueGreenWorld, run_app

        class LockedWorld(BlueGreenWorld):
            def __init__(self, tmp, timeouts):
                super().__init__(tmp)
                self.timeouts = timeouts

            def oneshot(self, image_id, command, env_bytes, **kwargs):
                if list(command) == ['migrate']:
                    self.oneshots.append((image_id, list(command), dict(kwargs)))
                    if self.timeouts:
                        self.timeouts -= 1
                        return SimpleNamespace(returncode=1, stdout=b'', stderr=LOCK_TIMEOUT_OUTPUT)
                return super().oneshot(image_id, command, env_bytes, **kwargs)
        with mock.patch.object(install.time, 'sleep'):
            world = LockedWorld(self.tmp, timeouts=1)
            details, error = run_app(world)
            self.assertIsNone(error, error and str(error))
            self.assertEqual(details['migrate_attempts'], 2)
            log = Path(details['migrate_log']).read_bytes()
            self.assertIn(b'--- migrate attempt 2 (exit 0)', log)
            world = LockedWorld(self.tmp, timeouts=9)
            details, error = run_app(world)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('a table\'s lock was not free within 5s, 4 times', str(error))
        self.assertEqual(error.details, {'migrate_attempts': 4})
        self.assertEqual([command for _, command, _ in world.oneshots if command == ['migrate']], [['migrate']] * 4)
        self.assertEqual(world.acts('run', 'stop', 'rename', 'vhost'), [])  # nothing switched


if __name__ == '__main__':
    unittest.main()
