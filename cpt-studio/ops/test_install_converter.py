"""Release 1's converter container (RELEASE-1-SPEC A7, the installer side of E3): its docker arguments, the role
'converter' of service_problems, --phase converter, the app phase's precondition, the worker's mount for a revision
that has the converter (and none for an older one), the image gate's self-test and the entrypoint role. No Docker,
root helper or network: every call is a fake, under test_install's host guard.

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_converter -v
"""
import os
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
import test_install  # noqa: E402
from test_install import TemporaryDirectoryTest, guard_host, release_host, run_body  # noqa: E402
from test_install_bluegreen import (IMAGE, OLD, OLD_IMAGE, REVISION, WEB, WORKER, BlueGreenWorld,  # noqa: E402
                                    app_args, flags, run_app)

APP_ROOT = Path(__file__).resolve().parents[1]
CONVERT_MOUNT = f'type=volume,src={install.CONVERT_VOLUME},dst={install.CONVERT_DIR},readonly'
MIB = 2 ** 20


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


def converter_container(**overrides):
    """cpt-studio-converter as docker inspect shows it when converter_args started it (healthy)."""
    container = {
        'Id': 'converter-1', 'Image': IMAGE, 'RestartCount': 0,
        'State': {'Running': True, 'Health': {'Status': 'healthy'}},
        'Config': {'User': f'{install.CONVERTER_UID}:{install.APP_UID}',
                   'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'converter', install.REVISION_LABEL: REVISION},
                   'Env': ['PATH=/usr/local/bin:/usr/bin', 'CPT_STUDIO_STATE_DIR=/var/lib/cpt-studio',
                           f'CPT_STUDIO_RELEASE_SHA={REVISION}']},
        'HostConfig': {'ReadonlyRootfs': True, 'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
                       'NetworkMode': 'none', 'Init': True, 'Memory': 1536 * MIB, 'MemorySwap': 1536 * MIB,
                       'Ulimits': [{'Name': 'core', 'Soft': 0, 'Hard': 0}], 'PortBindings': {}},
        'Mounts': [{'Type': 'volume', 'Name': install.CONVERT_VOLUME, 'Destination': install.CONVERT_DIR, 'RW': True}]}
    for path, value in overrides.items():
        target = container
        *parents, last = path.split('.')
        for key in parents:
            target = target[key]
        target[last] = value
    return container


class ConverterArgumentTests(unittest.TestCase):
    def test_the_converter_is_sealed_no_network_no_env_file_no_files_its_own_user_and_init(self):
        argv = install.converter_args(IMAGE, REVISION)
        self.assertEqual(argv[-2:], [IMAGE, 'converter'])  # the entrypoint role
        self.assertEqual(flags(argv, '--network'), ['none'])
        self.assertEqual(flags(argv, '--user'), [f'{install.CONVERTER_UID}:{install.APP_UID}'])
        self.assertIn('--init', argv)
        self.assertEqual(flags(argv, '--cpus'), ['2'])
        self.assertEqual(flags(argv, '--memory'), flags(argv, '--memory-swap'))
        self.assertEqual(flags(argv, '--memory'), ['1536m'])
        self.assertEqual(flags(argv, '--mount'), [f'type=volume,src={install.CONVERT_VOLUME},dst={install.CONVERT_DIR}'])
        for absent in ('--env-file', '-e', '-p', '--publish', '--privileged', '--cap-add'):
            self.assertNotIn(absent, argv)
        self.assertNotIn(install.FILES_VOLUME, ' '.join(argv))
        self.assertNotIn('credentials', ' '.join(argv))
        self.assertEqual(sorted(flags(argv, '--label')), sorted([f'{install.LABEL}=1', f'{install.ROLE_LABEL}=converter',
                                                                 f'{install.REVISION_LABEL}={REVISION}']))
        self.assertEqual(flags(argv, '--health-cmd'), ['python -m studio.converter_server --ping'])
        self.assertEqual(flags(argv, '--stop-timeout'), ['70'])
        self.assertEqual(flags(argv, '--restart'), ['unless-stopped'])
        for hardened in ('--read-only', '--cap-drop', '--security-opt', '--pids-limit', '--ulimit'):
            self.assertIn(hardened, argv)

    def test_a_converter_as_started_passes_and_each_forbidden_shape_is_refused(self):
        self.assertEqual(install.service_problems(converter_container(), 'converter', IMAGE), [])
        files = {'Type': 'volume', 'Name': install.FILES_VOLUME, 'Destination': install.STATE_DIR, 'RW': True}
        convert = converter_container()['Mounts'][0]
        cases = {
            'a network': ({'HostConfig.NetworkMode': install.NETWORK}, 'its network'),
            'the files volume': ({'Mounts': [convert, files]}, 'not the convert volume alone'),
            'no convert volume': ({'Mounts': []}, 'not the convert volume alone'),
            'a bind mount': ({'Mounts': [convert, {'Type': 'bind', 'Source': install.CODER['target'],
                                                   'Destination': install.CODER['mounted'], 'RW': False}]},
                             'bind-mounted'),
            'the secret key': ({'Config.Env': ['CPT_STUDIO_SECRET_KEY=x']}, 'CPT_STUDIO_SECRET_KEY'),
            'the database password': ({'Config.Env': ['CPT_STUDIO_DB_PASSWORD=x']}, 'CPT_STUDIO_DB_PASSWORD'),
            'a credentials file': ({'Config.Env': [f'{install.CODER["file_env"]}=/run/x']}, 'CREDENTIALS'),
            'an API key': ({'Config.Env': ['ANTHROPIC_API_KEY=x']}, 'ANTHROPIC_API_KEY'),
            'init off': ({'HostConfig.Init': False}, 'init is off'),
            'a writable root': ({'HostConfig.ReadonlyRootfs': False}, 'writable'),
            'capabilities': ({'HostConfig.CapDrop': []}, 'capabilities'),
            'the application user': ({'Config.User': f'{install.APP_UID}:{install.APP_UID}'}, "converter's own user"),
            'swap': ({'HostConfig.MemorySwap': -1}, 'allows swap'),
            'a published port': ({'HostConfig.PortBindings': {'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '9150'}]}},
                                 'published ports'),
        }
        for label, (overrides, said) in cases.items():
            with self.subTest(label):
                problems = install.service_problems(converter_container(**overrides), 'converter', IMAGE)
                self.assertTrue(problems)
                self.assertIn(said, ' '.join(problems))

    def test_an_older_revisions_worker_gets_no_converter_and_a_converter_revisions_worker_requires_it(self):
        older = install.service_args('worker', OLD_IMAGE, OLD, 'disabled', '')
        self.assertNotIn(CONVERT_MOUNT, flags(older, '--mount'))
        self.assertFalse([value for value in flags(older, '-e') if 'CONVERTER' in value])
        with mock.patch.object(test_install, 'CONVERTER_REVISIONS', {REVISION}):
            newer = install.service_args('worker', IMAGE, REVISION, 'disabled', '')
            web = install.service_args('web', IMAGE, REVISION, 'disabled', '')
        self.assertEqual(flags(newer, '--mount').count(CONVERT_MOUNT), 1)
        self.assertIn(f'CPT_STUDIO_CONVERTER_SOCKET={install.CONVERTER_SOCKET}', flags(newer, '-e'))
        self.assertIn('CPT_STUDIO_CONVERTER_REQUIRED=1', flags(newer, '-e'))
        self.assertNotIn(CONVERT_MOUNT, flags(web, '--mount'))  # only the worker converts
        # the socket's volume is mounted read-only into the worker: connecting needs no write
        self.assertTrue(CONVERT_MOUNT.endswith(',readonly'))

    def test_has_converter_reads_the_tree_and_refuses_a_revision_it_cannot_read(self):
        real = test_install.REAL_HAS_CONVERTER
        seen = []

        def git(answer_commit, answer_file):
            def fake_run(argv, **kwargs):
                seen.append(argv[-1])
                code = answer_commit if argv[-1].endswith('^{commit}') else answer_file
                return SimpleNamespace(returncode=code, stdout=b'', stderr=b'')
            return fake_run
        with mock.patch.object(install, 'run', git(0, 0)):
            self.assertIs(real(REVISION), True)
        self.assertEqual(seen[-1], f'{REVISION}:cpt-studio/studio/converter_server.py')
        with mock.patch.object(install, 'run', git(0, 128)):
            self.assertIs(real(REVISION), False)
        with mock.patch.object(install, 'run', git(128, 0)), self.assertRaisesRegex(install.InstallError, 'cannot read'):
            real(REVISION)
        with self.assertRaisesRegex(install.InstallError, '40-character'):
            real('abc')


class ConverterWorld(BlueGreenWorld):
    """BlueGreenWorld with this revision's converter (A7): has_converter is true for REVISION alone (OLD is the pair
    before release 1), and the converter container is modelled with its health."""

    def __init__(self, tmp, *, converter=None, **kwargs):
        super().__init__(tmp, **kwargs)
        self.converter = converter_container() if converter is None else converter

    def inspect(self, kind, name):
        if kind == 'container' and name == install.CONVERTER:
            self.act('inspect', kind, name)
            return self.done(self.converter or None)
        return super().inspect(kind, name)

    def patches(self):
        return super().patches() + [mock.patch.object(test_install, 'CONVERTER_REVISIONS', {REVISION})]


class AppPreconditionTests(TemporaryDirectoryTest):
    def test_app_refuses_without_a_healthy_converter_of_this_revision_and_starts_nothing(self):
        cases = {'none': ({}, 'is not there'),
                 'stopped': (converter_container(**{'State': {'Running': False, 'Health': {'Status': 'unhealthy'}}}),
                             'not running and healthy'),
                 'starting': (converter_container(**{'State.Health': {'Status': 'starting'}}), 'not running and healthy'),
                 'another image': (converter_container(Image=OLD_IMAGE), "not this revision's"),
                 'another revision': (converter_container(**{'Config.Labels': {
                     install.LABEL: '1', install.ROLE_LABEL: 'converter', install.REVISION_LABEL: OLD}}),
                     "not this revision's")}
        for label, (converter, said) in cases.items():
            with self.subTest(label):
                world = ConverterWorld(self.tmp, converter=converter)
                details, error = run_app(world)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn(said, str(error))
                self.assertIn('run --phase converter first', str(error))
                self.assertEqual(world.acts('run', 'stop', 'rename', 'oneshot', 'vhost'), [])

    def test_with_its_converter_the_new_worker_mounts_the_socket_and_requires_it(self):
        world = ConverterWorld(self.tmp)
        details, error = run_app(world, app_args(self.tmp))
        self.assertIsNone(error, error and str(error))
        worker = world.runs[WORKER]
        self.assertEqual(flags(worker, '--mount').count(CONVERT_MOUNT), 1)
        self.assertIn('CPT_STUDIO_CONVERTER_REQUIRED=1', flags(worker, '-e'))
        self.assertNotIn(CONVERT_MOUNT, flags(world.runs[install.INCOMING_WEB] if install.INCOMING_WEB in world.runs
                                              else world.runs[WEB], '--mount'))

    def test_an_older_revision_without_the_converter_needs_none(self):
        world = BlueGreenWorld(self.tmp)  # REVISION has no converter here (the guard's default)
        details, error = run_app(world)
        self.assertIsNone(error, error and str(error))
        self.assertNotIn(CONVERT_MOUNT, flags(world.runs[WORKER], '--mount'))


class ConverterPhaseTests(TemporaryDirectoryTest):
    def run_phase(self, current, *, healthy_after=True):
        calls, state = [], {'container': current}

        def inspect(kind, name):
            assert (kind, name) == ('container', install.CONVERTER), (kind, name)
            return state['container']

        def docker(*args, **kwargs):
            calls.append(args)
            if args[0] == 'run':
                state['container'] = converter_container(**({} if healthy_after else {
                    'State.Health': {'Status': 'unhealthy'}}))
            elif args[0] == 'rm':
                state['container'] = None
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        helper = mock.Mock(return_value={'root': {'uid': install.CONVERTER_UID, 'gid': install.APP_UID,
                                                  'mode': '0o750'}})
        kept = mock.Mock(return_value={'file': 'x', 'kept': 0, 'dropped': 3, 'sha256': '0' * 64, 'bytes': 0})
        ctx = install.Context(SimpleNamespace(phase='converter', revision=REVISION, receipts=str(self.tmp)), self.tmp)
        with mock.patch.multiple(install, inspect=inspect, docker=docker, run_helper=helper, keep_container_log=kept,
                                 installed_image=mock.Mock(return_value=IMAGE),
                                 ensure_volume=mock.Mock(return_value='created'), RELOAD_SEEN_INTERVAL=0), \
                mock.patch.object(test_install, 'CONVERTER_REVISIONS', {REVISION}), \
                mock.patch.object(install.time, 'sleep'):
            try:
                return install.phase_converter(ctx), None, calls, helper, kept
            except install.InstallError as error:
                return None, error, calls, helper, kept

    def test_a_fresh_converter_is_started_sealed_on_its_owned_volume(self):
        details, error, calls, helper, kept = self.run_phase(None)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['state'], 'started')
        runs = [call for call in calls if call[0] == 'run']
        self.assertEqual(runs, [('run', '-d', *install.converter_args(IMAGE, REVISION))])
        body, params = helper.call_args[0]
        self.assertIs(body, install.H_CONVERT_VOLUME)
        self.assertEqual(params, {'uid': install.CONVERTER_UID, 'gid': install.APP_UID})
        self.assertEqual(helper.call_args[1]['mounts'], [f'type=volume,src={install.CONVERT_VOLUME},dst=/convert'])
        kept.assert_not_called()

    def test_a_healthy_sealed_converter_of_this_revision_is_kept_as_it_is(self):
        details, error, calls, helper, kept = self.run_phase(converter_container())
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['state'], 'present')
        self.assertEqual([call for call in calls if call[0] in ('run', 'stop', 'rm')], [])

    def test_another_revisions_converter_is_stopped_with_its_70_s_its_log_kept_then_replaced(self):
        old = converter_container(Image=OLD_IMAGE, **{'Config.Labels': {
            install.LABEL: '1', install.ROLE_LABEL: 'converter', install.REVISION_LABEL: OLD}})
        details, error, calls, helper, kept = self.run_phase(old)
        self.assertIsNone(error, error and str(error))
        self.assertEqual(details['state'], 'replaced')
        verbs = [call[0] for call in calls]
        self.assertEqual(verbs, ['stop', 'rm', 'run'])
        self.assertEqual(calls[0], ('stop', '--time', '70', install.CONVERTER))
        kept.assert_called_once()
        self.assertEqual(kept.call_args[0][1], 'converter')

    def test_a_converter_that_does_not_become_healthy_is_refused(self):
        details, error, calls, helper, kept = self.run_phase(None, healthy_after=False)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn('did not become ready', str(error))

    def test_a_revision_without_the_converter_has_nothing_to_start_and_a_foreign_one_is_left(self):
        ctx = install.Context(SimpleNamespace(phase='converter', revision=REVISION, receipts=str(self.tmp)), self.tmp)
        with mock.patch.object(install, 'installed_image', return_value=IMAGE), \
                self.assertRaisesRegex(install.InstallError, 'has no converter service'):
            install.phase_converter(ctx)
        foreign = converter_container(**{'Config.Labels': {}})
        details, error, calls, helper, kept = self.run_phase(foreign)
        self.assertIn('not a CPT Studio converter container', str(error))
        self.assertEqual([call for call in calls if call[0] in ('run', 'stop', 'rm')], [])

    def test_the_volume_root_is_the_converters_with_the_applications_group(self):
        directory = self.tmp / 'convert'
        directory.mkdir()

        class Owner:  # FakeOwnership's role for this one body: records the chown instead of needing root
            def __getattr__(self, name):
                return getattr(os, name)

            def chown(self, path, uid, gid):
                self.owned = (path, uid, gid)

            def lstat(self, path):
                real = os.lstat(path)
                return SimpleNamespace(st_uid=self.owned[1], st_gid=self.owned[2], st_mode=real.st_mode)
        owner = Owner()
        answer = run_body(install.H_CONVERT_VOLUME, {'uid': install.CONVERTER_UID, 'gid': install.APP_UID},
                          {'/convert': str(directory)}, fake_os=owner)
        self.assertEqual(answer['root'], {'uid': install.CONVERTER_UID, 'gid': install.APP_UID, 'mode': '0o750'})
        self.assertEqual(stat.S_IMODE(os.stat(directory).st_mode), 0o750)


class ImageSelfTestTests(unittest.TestCase):
    def test_the_self_test_runs_as_the_converter_with_no_network_and_refuses_a_failure(self):
        calls = []

        def docker(*args, **kwargs):
            calls.append(args)
            return SimpleNamespace(returncode=0, stdout=b'converter self-test: ok (%PDF-)\n', stderr=b'')
        with mock.patch.object(install, 'docker', docker):
            self.assertEqual(install.image_converter_self_test(IMAGE), {'exit': 0, 'said': 'converter self-test: ok (%PDF-)'})
        argv = calls[0]
        self.assertEqual(argv[:2], ('run', '--rm'))
        self.assertEqual(flags(list(argv), '--network'), ['none'])
        self.assertEqual(flags(list(argv), '--user'), [f'{install.CONVERTER_UID}:{install.APP_UID}'])
        self.assertEqual(list(argv[argv.index('--entrypoint'):]), ['--entrypoint', 'python', IMAGE, '-m',
                                                                    'studio.converter_server', '--self-test'])
        with mock.patch.object(install, 'docker', return_value=SimpleNamespace(returncode=1, stdout=b'', stderr=b'x')), \
                self.assertRaisesRegex(install.InstallError, 'self-test'):
            install.image_converter_self_test(IMAGE)


class EntrypointTests(TemporaryDirectoryTest):
    def run_entrypoint(self, *argv):
        """deploy/entrypoint.sh, its 'cd /app' pointed at a temporary folder and 'python' a stand-in that prints its
        arguments; (exit code, stdout, stderr)."""
        if shutil.which('sh') is None:
            self.skipTest('no sh')
        script = (APP_ROOT / 'deploy' / 'entrypoint.sh').read_text()
        assert script.count('cd /app\n') == 1
        (self.tmp / 'entrypoint.sh').write_text(script.replace('cd /app\n', f'cd {self.tmp}\n'))
        bin_dir = self.tmp / 'bin'
        bin_dir.mkdir(exist_ok=True)
        (bin_dir / 'python').write_text('#!/bin/sh\necho "python $*"\n')
        os.chmod(bin_dir / 'python', 0o755)
        if os.getuid() == 0:
            self.skipTest('the entrypoint refuses root')
        done = subprocess.run(['sh', str(self.tmp / 'entrypoint.sh'), *argv], capture_output=True, text=True,
                              timeout=30, env={'PATH': f'{bin_dir}:/usr/bin:/bin'})
        return done.returncode, done.stdout, done.stderr

    def test_the_converter_role_runs_the_socket_server_and_takes_no_argument(self):
        code, out, err = self.run_entrypoint('converter')
        self.assertEqual((code, out.strip()), (0, 'python -m studio.converter_server'))
        code, out, err = self.run_entrypoint('converter', '--self-test')
        self.assertEqual(code, 64)
        self.assertIn("'converter' takes no arguments", err)
        code, out, err = self.run_entrypoint('worker')
        self.assertEqual((code, out.strip()), (0, 'python manage.py run_worker'))


class PhasesTableTests(unittest.TestCase):
    def test_the_phase_is_in_the_table(self):
        self.assertIs(install.PHASES['converter'], install.phase_converter)


if __name__ == '__main__':
    unittest.main()
