"""Release 1's installer items (RELEASE-1-SPEC A3's database half, A5, A6, A8, B7's installer side, Section 1.3's
sentences): offline, every Docker, root-helper and in-image call replaced by a fake, under test_install's host guard.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r1 -v
"""
import ast
import hashlib
import io
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


if __name__ == '__main__':
    unittest.main()
