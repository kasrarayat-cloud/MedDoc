"""Unit tests for the harness additions to ops/install.py (cpt-studio/HARNESS.md): the participants' optional
credentials, their modes and mounts, the opt-in access check, the passages phase, the migration-safety check, the
worker's stop timeout, and what a rollback does with participant stages and codes. No Docker, sudo, network or database.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

Every refusal is proven to refuse BEFORE it acts: the acting call (the copy, the migrate, the replacement, the import,
the build, the stop) is recorded and asserted not to have happened. Root-helper bodies run in-process against temporary
directories, as in test_install. Every credential value here is synthetic.
"""
import ast
import base64
import io
import json
import os
import subprocess
import sys
import tarfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import FakeOwnership, TemporaryDirectoryTest, run_body  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40
OTHER = 'b' * 40
IMAGE = 'sha256:' + 'c' * 64
RULING = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
FILES_MOUNT = f'type=volume,src={install.FILES_VOLUME},dst={install.STATE_DIR}'
INSTALLED = {'exists': True, 'kind': 'file', 'uid': install.APP_UID, 'gid': install.APP_UID, 'mode': '0o400'}
ASTRA, FABLE = install.PARTICIPANTS['astra'], install.PARTICIPANTS['fable']
# Synthetic stand-ins for vendor keys: never real, long enough to be matched by the scan.
OPENAI_VALUE = 'sk-synthetic-openai-0123456789abcdefghijklmnopqrstuv'
ANTHROPIC_VALUE = 'sk-ant-synthetic-0123456789abcdefghijklmnopqrstuv'
OPENAI_FILE = f'# synthetic\nOPENAI_API_KEY={OPENAI_VALUE}\nOPENAI_PROJECT=proj_synthetic0123\n'.encode()
ANTHROPIC_FILE = f'export ANTHROPIC_API_KEY="{ANTHROPIC_VALUE}"  # synthetic\n'.encode()
CORTI_VALUE = 'synthetic-corti-client-secret-0123456789'
CORTI_FILE = (f'CORTI_CLIENT_ID=synthetic-client\nCORTI_CLIENT_SECRET={CORTI_VALUE}\nCORTI_ENVIRONMENT=eu\n'
              'CORTI_TENANT_NAME=synthetic-tenant\n').encode()


def flags(argv, flag):
    return [argv[i + 1] for i, part in enumerate(argv) if part == flag]


def settings_value(name):
    """A literal assignment in cptstudio/settings.py, read with ast (no Django settings are loaded here)."""
    tree = ast.parse((APP_ROOT / 'cptstudio' / 'settings.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f'{name} is not a literal assignment in settings.py')


# --- arguments ------------------------------------------------------------------------

class ParticipantArgumentTests(unittest.TestCase):
    BASE = ['--revision', REVISION, '--receipts', '/tmp/receipts']

    def parse(self, *extra):
        with mock.patch('sys.stderr', io.StringIO()):
            return install.parse_args([*self.BASE, *extra])

    def refused(self, *extra):
        stderr = io.StringIO()
        with self.assertRaises(SystemExit) as caught, mock.patch('sys.stderr', stderr):
            install.parse_args([*self.BASE, *extra])
        self.assertEqual(caught.exception.code, 2)
        return stderr.getvalue()

    def test_participants_are_disabled_unless_named_live(self):
        args = self.parse('--phase', 'app', '--provider-mode', 'disabled')
        self.assertEqual((args.astra_mode, args.fable_mode, args.access_check), ('disabled', 'disabled', None))
        args = self.parse('--phase', 'app', '--provider-mode', 'disabled', '--astra-mode', 'live',
                          '--authorization-ref', RULING)
        self.assertEqual((args.astra_mode, args.fable_mode), ('live', 'disabled'))
        args = self.parse('--phase', 'app', '--provider-mode', 'live', '--astra-mode', 'live', '--fable-mode', 'live',
                          '--authorization-ref', RULING, '--access-check')
        self.assertEqual((args.astra_mode, args.fable_mode, args.access_check), ('live', 'live', True))
        self.assertEqual(self.parse('--phase', 'passages').phase, 'passages')
        # Corti is a participant the access check reaches when the provider is live (checklist 1.3)
        self.assertTrue(self.parse('--phase', 'app', '--provider-mode', 'live', '--authorization-ref', RULING,
                                   '--access-check').access_check)

    def test_refusals(self):
        # live needs the recorded authority, as Corti's live mode does
        self.assertIn('--astra-mode live needs --authorization-ref',
                      self.refused('--phase', 'app', '--provider-mode', 'disabled', '--astra-mode', 'live'))
        self.assertIn('--fable-mode live needs --authorization-ref',
                      self.refused('--phase', 'app', '--provider-mode', 'disabled', '--fable-mode', 'live'))
        # replay is for tests and development only (HARNESS.md 8): the installer offers disabled and live
        self.refused('--phase', 'app', '--provider-mode', 'disabled', '--astra-mode', 'replay')
        # the access check sends a real request, so it needs a live participant to send it
        self.assertIn('--access-check checks each live participant',
                      self.refused('--phase', 'app', '--provider-mode', 'disabled', '--access-check'))
        self.assertIn('only applies to',
                      self.refused('--phase', 'app', '--provider-mode', 'disabled', '--astra-mode', 'disabled',
                                   '--authorization-ref', RULING))
        for phase in ('preflight', 'secrets', 'passages', 'verify', 'rollback-app'):
            for extra in (('--astra-mode', 'disabled'), ('--fable-mode', 'live'), ('--access-check',)):
                with self.subTest(phase=phase, extra=extra):
                    self.refused('--phase', phase, *extra)


# --- docker arguments -----------------------------------------------------------------

class ParticipantServiceArgumentTests(unittest.TestCase):
    def test_only_the_worker_mounts_a_live_participants_file_read_only(self):
        modes = {'astra': 'live', 'fable': 'disabled'}
        worker = install.service_args('worker', IMAGE, REVISION, 'disabled', RULING, modes)
        web = install.service_args('web', IMAGE, REVISION, 'disabled', RULING, modes)
        self.assertEqual(flags(worker, '--mount'), [
            FILES_MOUNT, f'type=bind,src={ASTRA["target"]},dst=/run/cpt-studio/openai-credentials.env,readonly'])
        self.assertEqual(flags(web, '--mount'), [FILES_MOUNT])  # the path, never the file
        for argv in (worker, web):
            env = flags(argv, '-e')
            for expected in ('CPT_STUDIO_ASTRA_MODE=live', 'CPT_STUDIO_FABLE_MODE=disabled',
                             'CPT_STUDIO_OPENAI_CREDENTIALS_FILE=/run/cpt-studio/openai-credentials.env',
                             f'CPT_STUDIO_AUTHORIZATION_REF={RULING}', 'CPT_STUDIO_PROVIDER_MODE=disabled'):
                self.assertIn(expected, env)
            self.assertFalse([item for item in env if item.startswith('CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE=')])
            self.assertFalse([item for item in env if item.startswith('CPT_STUDIO_CORTI_CREDENTIALS_FILE=')])

    def test_all_three_live(self):
        modes = {'astra': 'live', 'fable': 'live'}
        worker = install.service_args('worker', IMAGE, REVISION, 'live', RULING, modes)
        self.assertEqual(flags(worker, '--mount'), [
            FILES_MOUNT, f'type=bind,src={install.CORTI_TARGET},dst={install.CREDENTIALS_IN_CONTAINER},readonly',
            f'type=bind,src={ASTRA["target"]},dst={ASTRA["mounted"]},readonly',
            f'type=bind,src={FABLE["target"]},dst=/run/cpt-studio/anthropic-credentials.env,readonly'])
        env = flags(worker, '-e')
        self.assertIn('CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE=/run/cpt-studio/anthropic-credentials.env', env)
        self.assertIn('CPT_STUDIO_FABLE_MODE=live', env)
        web = install.service_args('web', IMAGE, REVISION, 'live', RULING, modes)
        self.assertEqual(flags(web, '--mount'), [FILES_MOUNT])
        self.assertEqual(flags(web, '-e'), env)  # the web is named everything the worker is, and holds no file

    def test_without_participants_both_are_disabled_and_no_participant_file_is_named(self):
        for role in ('web', 'worker'):
            for argv in (install.service_args(role, IMAGE, REVISION, 'live', RULING),
                         install.service_args(role, IMAGE, REVISION, 'disabled', '', {'astra': 'disabled'})):
                with self.subTest(role=role):
                    env = flags(argv, '-e')
                    self.assertIn('CPT_STUDIO_ASTRA_MODE=disabled', env)
                    self.assertIn('CPT_STUDIO_FABLE_MODE=disabled', env)
                    joined = ' '.join(argv).lower()
                    self.assertNotIn('openai', joined)
                    self.assertNotIn('anthropic', joined)

    def test_one_shots_never_run_a_participant(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        with mock.patch.object(install, 'run', fake_run), mock.patch.object(install, 'inspect', return_value=None):
            install.oneshot(IMAGE, ['migrate'], b'')
            install.oneshot(IMAGE, ['manage', 'shell', '-c', install.PARTICIPANT_CREDENTIALS_CHECKS['fable']], b'',
                            network='none', participant_files=('fable',))
        plain, checked = calls
        self.assertIn('CPT_STUDIO_ASTRA_MODE=disabled', flags(plain, '-e'))
        self.assertIn('CPT_STUDIO_FABLE_MODE=disabled', flags(plain, '-e'))
        self.assertNotIn('anthropic', ' '.join(plain))
        # the parse check: the participant's file at the worker's path, read-only, named by its setting, offline,
        # and the participant itself still disabled
        self.assertEqual(flags(checked, '--network'), ['none'])
        self.assertEqual(flags(checked, '--mount'),
                         [f'type=bind,src={FABLE["target"]},dst={FABLE["mounted"]},readonly'])
        self.assertIn(f'CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE={FABLE["mounted"]}', flags(checked, '-e'))
        self.assertIn('CPT_STUDIO_FABLE_MODE=disabled', flags(checked, '-e'))
        self.assertIn('CPT_STUDIO_PROVIDER_MODE=disabled', flags(checked, '-e'))

    def test_the_parse_checks_call_the_applications_own_loaders(self):
        for name, loader, setting in (('astra', 'load_openai_credentials', 'OPENAI_CREDENTIALS_FILE'),
                                      ('fable', 'load_anthropic_credentials', 'ANTHROPIC_CREDENTIALS_FILE')):
            body = install.PARTICIPANT_CREDENTIALS_CHECKS[name]
            compile(body, name, 'exec')
            self.assertIn(f'from studio.participants.credentials import {loader}\n', body)
            self.assertIn(f'{loader}(settings.{setting})\n', body)
            # the setting the check reads is the one settings.py defines from the variable the installer sets
            source = (APP_ROOT / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')
            self.assertIn(f"{setting} = _env('{setting}', '')", source)
            self.assertEqual(install.PARTICIPANTS[name]['file_env'], f'CPT_STUDIO_{setting}')

    def test_no_secret_name_or_value_is_ever_an_argument(self):
        modes = {'astra': 'live', 'fable': 'live'}
        for argv in (install.service_args('worker', IMAGE, REVISION, 'live', RULING, modes),
                     install.service_args('web', IMAGE, REVISION, 'live', RULING, modes)):
            joined = ' '.join(argv)
            for name in ('API_KEY', 'WORKSPACE_ID', 'OPENAI_PROJECT', 'SECRET_KEY', 'DB_PASSWORD', 'CLIENT_SECRET'):
                self.assertNotIn(name, joined)


class StopTimeoutTests(unittest.TestCase):
    def test_the_worker_outlasts_every_send_deadline(self):
        participant = settings_value('PARTICIPANT_SEND_DEADLINE_SECONDS')
        corti = settings_value('PROVIDER_READ_TIMEOUT_SECONDS') + 30  # jobs._send's deadline_s
        self.assertEqual(participant, 330)
        self.assertGreater(install.STOP_SECONDS['worker'], participant)
        self.assertGreater(install.STOP_SECONDS['worker'], corti)
        self.assertEqual(flags(install.service_args('worker', IMAGE, REVISION, 'disabled', ''), '--stop-timeout'),
                         [str(install.STOP_SECONDS['worker'])])
        # the access check sends once and must not be cut off before the send deadline
        self.assertGreater(install.ACCESS_CHECK_SECONDS, participant)

    def test_parking_and_removing_wait_for_the_whole_stop_timeout(self):
        calls = []

        def fake_docker(*args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        worker = {'Id': 'w', 'Image': 'old', 'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'worker'}}}
        with mock.patch.object(install, 'docker', fake_docker), \
                mock.patch.object(install, 'inspect', side_effect=[None, worker, worker]):
            install.park('worker')
            install.remove_service_container(install.SERVICES['worker'], 'worker')
        stops = [(args, kwargs) for args, kwargs in calls if args[0] == 'stop']
        self.assertEqual([args[:3] for args, _ in stops], [('stop', '--time', '360')] * 2)
        self.assertTrue(all(kwargs['timeout'] > 360 for _, kwargs in stops))


class ServiceMountTests(unittest.TestCase):
    def container(self, role, mounts):
        return {'Image': IMAGE, 'Config': {'User': f'{install.APP_UID}:{install.APP_UID}',
                                           'Labels': {install.LABEL: '1', install.ROLE_LABEL: role}},
                'HostConfig': {'ReadonlyRootfs': True, 'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
                               'PortBindings': ({'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '9150'}]}
                                                if role == 'web' else {})},
                'Mounts': mounts}

    def bind(self, source, destination, writable=False):
        return {'Type': 'bind', 'Source': source, 'Destination': destination, 'RW': writable}

    def test_only_the_worker_holds_credentials_and_only_read_only(self):
        volume = {'Type': 'volume', 'Name': install.FILES_VOLUME, 'Destination': install.STATE_DIR, 'RW': True}
        credentials = [self.bind(install.CORTI_TARGET, install.CREDENTIALS_IN_CONTAINER),
                       self.bind(ASTRA['target'], ASTRA['mounted']), self.bind(FABLE['target'], FABLE['mounted'])]
        self.assertEqual(install.service_problems(self.container('worker', [volume, *credentials]), 'worker', IMAGE),
                         [])
        self.assertEqual(install.service_problems(self.container('web', [volume]), 'web', IMAGE), [])
        for role, mounts in (('web', [volume, self.bind(ASTRA['target'], ASTRA['mounted'])]),
                             ('worker', [volume, self.bind(ASTRA['target'], ASTRA['mounted'], writable=True)]),
                             ('worker', [volume, self.bind('/etc/passwd', ASTRA['mounted'])]),
                             ('worker', [volume, self.bind(ASTRA['target'], FABLE['mounted'])])):
            with self.subTest(role=role, mounts=mounts[1:]):
                self.assertEqual(len(install.service_problems(self.container(role, mounts), role, IMAGE)), 1)


# --- the participants' credentials: the secrets phase -----------------------------------

class ParticipantSecretsHelperTests(TemporaryDirectoryTest):
    """H_PARTICIPANT_SECRETS executed in-process; participant_secrets() builds its parameters and mounts for real."""

    def setUp(self):
        super().setUp()
        self.target = self.tmp / 'target'
        self.sources = self.tmp / 'sources'
        self.target.mkdir(mode=0o700)
        self.sources.mkdir(mode=0o700)
        os.chmod(self.sources, 0o700)
        self.fake = FakeOwnership()
        self.fake.owners[str(self.sources)] = (0, 0)
        self.helper_calls = []

    def source(self, name, data, *, mode=0o600, root=True):
        path = self.sources / name
        path.write_bytes(data)
        os.chmod(path, mode)
        if root:
            self.fake.owners[str(path)] = (0, 0)
        else:
            self.fake.owners.pop(str(path), None)  # the file's real owner, this test's user
        return path

    def helper(self, body, params, *, mounts, sensitive=False, **kwargs):
        """run_helper, the body run here: the real one's refusal on an 'error' answer included."""
        self.helper_calls.append({'params': params, 'mounts': mounts, 'sensitive': sensitive})
        result = run_body(body, params, {"'/target'": repr(str(self.target)), "'/sources'": repr(str(self.sources))},
                          self.fake)
        if result.get('error'):
            raise install.InstallError(f'Root helper refused: {result["error"]}', details=result)
        return result

    def secrets(self, folder=None):
        folder = folder or {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o700'}
        with mock.patch.object(install, 'helper_stat', return_value={install.PROVIDER_SOURCES: folder}), \
                mock.patch.object(install, 'run_helper', self.helper):
            return install.participant_secrets()

    def refused(self, folder=None):
        before = sorted(path.name for path in self.target.iterdir())
        with self.assertRaises(install.InstallError) as caught:
            self.secrets(folder)
        self.assertEqual(sorted(path.name for path in self.target.iterdir()), before)  # nothing was written
        text = str(caught.exception) + json.dumps(caught.exception.details)
        for value in (OPENAI_VALUE, ANTHROPIC_VALUE, 'proj_synthetic0123'):
            self.assertNotIn(value, text)
        return str(caught.exception)

    def owner(self, name):
        return self.fake.owners.get(str(self.target / name))

    def test_copies_each_source_once_byte_for_byte_and_reports_names_only(self):
        self.source('openai.env', OPENAI_FILE)
        self.source('anthropic.env', ANTHROPIC_FILE)
        report = self.secrets()
        self.assertEqual(report, {
            'astra': {'state': 'created', 'source': 'present', 'key_names': ['OPENAI_API_KEY', 'OPENAI_PROJECT']},
            'fable': {'state': 'created', 'source': 'present', 'key_names': ['ANTHROPIC_API_KEY']}})
        for name, data in (('openai-credentials.env', OPENAI_FILE), ('anthropic-credentials.env', ANTHROPIC_FILE)):
            path = self.target / name
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o400)
            self.assertEqual(self.owner(name), (install.APP_UID, install.APP_UID))
        self.assertEqual(sorted(path.name for path in self.target.iterdir()),
                         ['anthropic-credentials.env', 'openai-credentials.env'])  # no staged file left
        call = self.helper_calls[0]
        self.assertTrue(call['sensitive'])
        self.assertEqual(call['mounts'], [f'type=bind,src={install.ETC_DIR},dst=/target',
                                          f'type=bind,src={install.PROVIDER_SOURCES},dst=/sources,readonly'])
        for value in (OPENAI_VALUE, ANTHROPIC_VALUE, 'proj_synthetic0123'):
            self.assertNotIn(value, json.dumps(report))
            self.assertNotIn(value, json.dumps(call['params']))
        again = self.secrets()
        self.assertEqual({name: entry['state'] for name, entry in again.items()},
                         {'astra': 'present', 'fable': 'present'})
        self.assertEqual((self.target / 'openai-credentials.env').read_bytes(), OPENAI_FILE)

    def test_a_missing_source_leaves_its_participant_not_provided(self):
        self.source('openai.env', OPENAI_FILE)
        report = self.secrets()
        self.assertEqual(report['astra']['state'], 'created')
        self.assertEqual(report['fable'], {'state': 'not provided', 'source': 'absent', 'key_names': []})
        self.assertFalse((self.target / 'anthropic-credentials.env').exists())

    def test_without_the_sources_directory_nothing_is_mounted_or_written(self):
        report = self.secrets({'exists': False})
        self.assertEqual({name: entry['state'] for name, entry in report.items()},
                         {'astra': 'not provided', 'fable': 'not provided'})
        self.assertEqual(self.helper_calls[0]['mounts'], [f'type=bind,src={install.ETC_DIR},dst=/target'])
        self.assertEqual(list(self.target.iterdir()), [])

    def test_a_copy_whose_source_was_removed_stays_present(self):
        source = self.source('openai.env', OPENAI_FILE)
        self.secrets()
        source.unlink()
        report = self.secrets()
        self.assertEqual(report['astra'], {'state': 'present', 'source': 'absent',
                                           'key_names': ['OPENAI_API_KEY', 'OPENAI_PROJECT']})

    def test_every_refusal_writes_nothing_for_either_participant(self):
        good = ('anthropic.env', ANTHROPIC_FILE)
        cases = {
            'group-readable source': (('openai.env', OPENAI_FILE, 0o640, True), 'not a root-owned 0600 regular file'),
            'source not owned by root': (('openai.env', OPENAI_FILE, 0o600, False), 'not a root-owned 0600'),
            'no API key name': (('openai.env', b'OPENAI_PROJECT=proj_synthetic0123\n', 0o600, True),
                                'lacks key name(s): OPENAI_API_KEY'),
            'another key': (('openai.env', OPENAI_FILE + b'OPENAI_ORG=org-synthetic-0123456789\n', 0o600, True),
                            '1 line(s) setting no key of OPENAI_API_KEY, OPENAI_PROJECT'),
            'a pasted key with no name': (('openai.env', OPENAI_FILE + OPENAI_VALUE.encode() + b'\n', 0o600, True),
                                          '1 line(s) setting no key'),
            'a repeated key': (('openai.env', OPENAI_FILE + f'OPENAI_API_KEY={OPENAI_VALUE}x\n'.encode(), 0o600, True),
                               'sets OPENAI_API_KEY more than once'),
            'too large': (('openai.env', OPENAI_FILE + b'#' * install.PARTICIPANT_FILE_LIMIT, 0o600, True),
                          'larger than'),
        }
        for label, ((name, data, mode, root), message) in cases.items():
            with self.subTest(label):
                for path in self.sources.iterdir():
                    path.unlink()
                self.source(*good)
                self.source(name, data, mode=mode, root=root)
                self.assertIn(message, self.refused())
        # A pasted key is counted, never echoed: the unknown "name" here would be the key itself.
        for path in self.sources.iterdir():
            path.unlink()
        self.source('openai.env', f'{OPENAI_VALUE}=\nOPENAI_API_KEY={OPENAI_VALUE}\n'.encode())
        self.assertIn('1 line(s) setting no key', self.refused())

    def test_a_link_a_non_root_directory_and_a_staged_leftover_are_refused(self):
        self.source('anthropic.env', ANTHROPIC_FILE)
        elsewhere = self.tmp / 'elsewhere.env'  # a file that would pass every check, but reached through a link
        elsewhere.write_bytes(OPENAI_FILE)
        os.chmod(elsewhere, 0o600)
        self.fake.owners[str(elsewhere)] = (0, 0)
        (self.sources / 'openai.env').symlink_to(elsewhere)
        self.fake.owners[str(self.sources / 'openai.env')] = (0, 0)  # what a followed link would report (the shim
        # keys owners by the path opened)
        self.assertIn('openai.env is not a root-owned 0600 regular file', self.refused())
        (self.sources / 'openai.env').unlink()
        self.fake.owners[str(self.sources)] = (os.getuid(), os.getgid())
        self.assertIn('is not a root-owned 0700 directory', self.refused())
        self.fake.owners[str(self.sources)] = (0, 0)
        (self.target / '.anthropic-credentials.env.new').write_bytes(b'interrupted')
        self.assertIn('from an interrupted run exists', self.refused())

    def test_the_phase_refuses_a_sources_directory_that_is_not_root_only_before_mounting_it(self):
        for folder in ({'exists': True, 'kind': 'dir', 'uid': 1000, 'gid': 0, 'mode': '0o700'},
                       {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o755'},
                       {'exists': True, 'kind': 'link', 'uid': 0, 'gid': 0, 'mode': '0o777'}):
            with self.subTest(folder=folder), \
                    mock.patch.object(install, 'helper_stat', return_value={install.PROVIDER_SOURCES: folder}), \
                    mock.patch.object(install, 'run_helper') as helper, self.assertRaises(install.InstallError):
                install.participant_secrets()
            helper.assert_not_called()

    def test_an_installed_copy_must_equal_its_source_with_its_owner_and_mode(self):
        source = self.source('openai.env', OPENAI_FILE)
        self.secrets()
        source.write_bytes(OPENAI_FILE.replace(b'0123', b'9999'))
        self.assertIn('differs from its source', self.refused())
        self.assertEqual((self.target / 'openai-credentials.env').read_bytes(), OPENAI_FILE)  # kept as it was
        source.write_bytes(OPENAI_FILE)
        os.chmod(self.target / 'openai-credentials.env', 0o440)
        self.assertIn('is not the 10150:10150 0400 regular file', self.refused())

    def test_phase_secrets_runs_the_participant_step_only_after_the_three_file_set(self):
        order = []

        def helper(body, params, **kwargs):
            order.append(body)
            if body is install.H_ETC_DIR:
                return {'etc_dir': 'present'}
            if body is install.H_SECRETS:
                return {'state': 'present', 'files': {}}
            return {'participants': {'astra': {'state': 'created'}, 'fable': {'state': 'not provided'}}}
        stat = {install.PROVIDER_SOURCES: {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o700'}}
        with mock.patch.object(install, 'run_helper', helper), mock.patch.object(install, 'helper_stat',
                                                                                 return_value=stat):
            result = install.phase_secrets(SimpleNamespace())
        self.assertEqual(order, [install.H_ETC_DIR, install.H_SECRETS, install.H_PARTICIPANT_SECRETS])
        self.assertIn('participant credentials: astra created, fable not provided', result['summary'])

        def refusing(body, params, **kwargs):
            order.append(body)
            if body is install.H_SECRETS:
                raise install.InstallError('Root helper refused: partial secrets present')
            return {'etc_dir': 'present'}
        order.clear()
        with mock.patch.object(install, 'run_helper', refusing), self.assertRaises(install.InstallError):
            install.phase_secrets(SimpleNamespace())
        self.assertNotIn(install.H_PARTICIPANT_SECRETS, order)

    def test_preflight_names_a_source_that_is_not_root_only_and_accepts_one_that_is_absent(self):
        paths = {install.PROVIDER_SOURCES: {'exists': False}, ASTRA['source']: {'exists': False},
                 FABLE['source']: {'exists': False}}
        self.assertEqual(install.participant_source_problems(paths), [])
        paths[install.PROVIDER_SOURCES] = {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o700'}
        paths[ASTRA['source']] = {'exists': True, 'kind': 'file', 'uid': 0, 'gid': 0, 'mode': '0o600'}
        self.assertEqual(install.participant_source_problems(paths), [])
        paths[FABLE['source']] = {'exists': True, 'kind': 'file', 'uid': 0, 'gid': 0, 'mode': '0o644'}
        paths[install.PROVIDER_SOURCES] = {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o755'}
        self.assertEqual(install.participant_source_problems(paths),
                         [f'{install.PROVIDER_SOURCES} is not a root-owned 0700 directory',
                          f'{FABLE["source"]} is not a root-owned 0600 regular file'])


class CredentialScanTests(TemporaryDirectoryTest):
    """H_CREDENTIAL_SCAN executed in-process, through credential_free with only run_helper replaced."""

    def setUp(self):
        super().setUp()
        (self.tmp / 'astra').write_bytes(OPENAI_FILE)
        (self.tmp / 'fable').write_bytes(ANTHROPIC_FILE)
        self.mounts = []

    def helper(self, body, params, *, mounts, sensitive=False, **kwargs):
        self.mounts.append((mounts, sensitive))
        return run_body(body, params, {"'/scan/'": repr(str(self.tmp) + '/')})

    def free(self, outputs, names):
        with mock.patch.object(install, 'run_helper', self.helper):
            return install.credential_free(outputs, names)

    def test_a_value_in_any_form_is_found_and_only_key_names_come_back(self):
        self.assertTrue(self.free([b'{"ok": true, "model": "gpt-6-astra"}', b''], ['astra']))
        self.assertFalse(self.free([b'Authorization: Bearer ' + OPENAI_VALUE.encode()], ['astra']))
        self.assertFalse(self.free([b'', b'project proj_synthetic0123 refused'], ['astra']))
        self.assertFalse(self.free([b'x-api-key: ' + ANTHROPIC_VALUE.encode()], ['fable']))  # quoted in the file
        self.assertTrue(self.free([b'x-api-key: ' + ANTHROPIC_VALUE.encode()], ['astra']))  # not this file's
        self.assertEqual(self.mounts[0], ([f'type=bind,src={ASTRA["target"]},dst=/scan/astra,readonly'], True))
        result = run_body(install.H_CREDENTIAL_SCAN, {'blob': base64.b64encode(OPENAI_VALUE.encode()).decode(),
                                                      'files': ['astra'], 'limit': 32000, 'min_length': 8},
                          {"'/scan/'": repr(str(self.tmp) + '/')})
        self.assertEqual(result, {'found': ['OPENAI_API_KEY']})

    def test_when_it_cannot_be_told_the_output_is_not_recorded(self):
        with mock.patch.object(install, 'run_helper', side_effect=install.InstallError('A root helper failed')):
            self.assertFalse(install.credential_free([b'anything'], ['astra']))
        with mock.patch.object(install, 'run_helper', return_value={}):
            self.assertFalse(install.credential_free([b'anything'], ['astra']))
        self.assertTrue(install.credential_free([b'anything'], []))


# --- the app phase: live participants and the access check ----------------------------------

class AppWorld:
    """phase_app's surroundings with Docker, the database and the in-image scripts replaced: ``timeline`` records every
    call that acts or reads, in order; ``answers`` overrides a container's answer by (kind, participant)."""

    def __init__(self, tmp):
        self.tmp, self.timeline, self.answers = tmp, [], {}
        self.scan_dir = tmp / 'scan'
        self.scan_dir.mkdir(exist_ok=True)
        (self.scan_dir / 'astra').write_bytes(OPENAI_FILE)
        (self.scan_dir / 'fable').write_bytes(ANTHROPIC_FILE)
        (self.scan_dir / 'corti').write_bytes(CORTI_FILE)
        self.stat = {ASTRA['target']: INSTALLED, FABLE['target']: INSTALLED, install.CORTI_TARGET: INSTALLED}

    def respond(self, command, kwargs):
        if command[:2] == ['manage', 'shell'] and command[-1] == install.CREDENTIALS_CHECK:
            return SimpleNamespace(returncode=0, stdout=b'corti-credentials-parse-ok\n', stderr=b'')
        if command[:2] == ['manage', 'shell']:
            name = next(name for name, body in install.PARTICIPANT_CREDENTIALS_CHECKS.items() if body == command[-1])
            return self.answers.get(('parse', name)) or SimpleNamespace(
                returncode=0, stdout=f'{name}-credentials-parse-ok\n'.encode(), stderr=b'')
        if command[:2] == ['manage', 'participant_access_check']:
            name = command[-1]
            return self.answers.get(('access', name)) or SimpleNamespace(
                returncode=0, stderr=b'', stdout=json.dumps({'participant': name, 'ok': True,
                                                             'request_id': 'req_synthetic'}).encode() + b'\n')
        return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

    def oneshot(self, image_id, command, env_bytes, **kwargs):
        self.timeline.append(('oneshot', tuple(command[:2]), command, kwargs))
        return self.respond(command, kwargs)

    def app_script(self, image_id, env_bytes, body, params, **kwargs):
        self.timeline.append(('script', body))
        if body == install.UNRUNNABLE_STAGES:
            return {'known': ['analyze', 'assess', 'astra', 'extract', 'fable', 'predict', 'review2'], 'stuck': 0,
                    'kinds': []}
        return {'encounters': 0, 'changed': {}}

    def replace(self, ctx, image_id, env_bytes, mode, reference, participants=None):
        self.timeline.append(('replace', mode, reference, participants))
        return {'started': {}, 'replaced': {}}

    def helper(self, body, params, *, mounts, sensitive=False, **kwargs):
        """run_helper for H_CREDENTIAL_SCAN, its body run here on the synthetic credentials files."""
        self.timeline.append(('helper', mounts, sensitive))
        return run_body(body, params, {"'/scan/'": repr(str(self.scan_dir) + '/')})

    def patches(self):
        return [mock.patch.object(install, 'run', return_value=SimpleNamespace(returncode=0)),
                mock.patch.object(install, 'installed_image', return_value=IMAGE),
                mock.patch.object(install, 'require_db'),
                mock.patch.object(install, 'helper_stat',
                                  side_effect=lambda paths: {path: self.stat.get(path, {'exists': False})
                                                             for path in paths}),
                mock.patch.object(install, 'read_protected_env', return_value=b'CPT_STUDIO_SECRET_KEY=synthetic\n'),
                mock.patch.object(install, 'oneshot', self.oneshot),
                mock.patch.object(install, 'app_script', self.app_script),
                mock.patch.object(install, 'replace_services', self.replace),
                mock.patch.object(install, 'retire_parked'),
                mock.patch.object(install, 'run_helper', self.helper)]


def app_args(tmp, *, provider='disabled', astra='live', fable='live', access=None):
    reference = RULING if 'live' in (provider, astra, fable) else ''
    return SimpleNamespace(phase='app', revision=REVISION, receipts=str(tmp), provider_mode=provider,
                           authorization_ref=reference, astra_mode=astra, fable_mode=fable, access_check=access)


class AppPhaseParticipantTests(TemporaryDirectoryTest):
    """The REAL phase_app (participant_access_check and credential_free included) in an AppWorld."""

    def setUp(self):
        super().setUp()
        self.world = AppWorld(self.tmp)

    def app(self, args):
        patches = self.world.patches()
        for patcher in patches:
            patcher.start()
        try:
            return install.phase_app(install.Context(args, self.tmp))
        finally:
            for patcher in reversed(patches):
                patcher.stop()

    def acted(self):
        """What changed anything or sent anything: a migrate, the replacement, an access check."""
        return [event for event in self.world.timeline if event[0] == 'replace'
                or (event[0] == 'oneshot' and event[1] in (('migrate',), ('manage', 'participant_access_check')))]

    def test_a_live_participant_without_its_installed_file_refuses_before_anything_changes(self):
        for state in ({'exists': False}, {**INSTALLED, 'mode': '0o440'}, {**INSTALLED, 'uid': 0, 'gid': 0},
                      {**INSTALLED, 'kind': 'link'}):
            self.world.timeline.clear()
            self.world.stat[FABLE['target']] = state
            with self.subTest(state=state), self.assertRaises(install.InstallError) as caught:
                self.app(app_args(self.tmp))
            self.assertIn('--fable-mode live', str(caught.exception))
            self.assertIn(FABLE['source'], str(caught.exception))
            self.assertFalse([event for event in self.world.timeline if event[0] in ('oneshot', 'replace', 'script')])

    def test_a_file_its_loader_refuses_stops_before_migrating_and_its_error_is_kept_only_when_clean(self):
        for stderr, kept in ((b'CredentialsError: OPENAI_API_KEY is missing from the OpenAI credentials file.', True),
                             (b'CredentialsError: bad value ' + OPENAI_VALUE.encode(), False)):
            self.world.timeline.clear()
            self.world.answers[('parse', 'astra')] = SimpleNamespace(returncode=1, stdout=b'', stderr=stderr)
            with self.subTest(kept=kept), self.assertRaises(install.InstallError) as caught:
                self.app(app_args(self.tmp))
            self.assertIn('cannot load /etc/cpt-studio/openai-credentials.env', str(caught.exception))
            self.assertEqual(caught.exception.output, stderr if kept else b'')
            self.assertEqual(self.acted(), [])  # no migrate, no replacement, no access check
            self.assertNotIn(OPENAI_VALUE, str(caught.exception))

    def test_the_parse_checks_run_offline_in_the_workers_layout_before_migrate(self):
        self.app(app_args(self.tmp, provider='live'))
        commands = [event for event in self.world.timeline if event[0] == 'oneshot']
        self.assertEqual([event[1] for event in commands],
                         [('manage', 'shell')] * 3 + [('migrate',)])  # Corti's, Astra's, Fable's, then migrate
        corti, astra, fable = (event[3] for event in commands[:3])
        self.assertEqual(corti, {'network': 'none', 'credentials': True, 'timeout': 120})
        self.assertEqual(astra, {'network': 'none', 'participant_files': ('astra',), 'timeout': 120})
        self.assertEqual(fable, {'network': 'none', 'participant_files': ('fable',), 'timeout': 120})

    def test_live_participants_are_installed_with_their_modes_and_no_access_check_without_the_flag(self):
        details = self.app(app_args(self.tmp, astra='live', fable='disabled'))
        self.assertIn(('replace', 'disabled', RULING, {'astra': 'live', 'fable': 'disabled'}), self.world.timeline)
        self.assertEqual(details['participants'], {'astra': 'live', 'fable': 'disabled'})
        self.assertEqual(details['participant_credentials_loaded'], ['astra'])
        self.assertEqual(details['access_checks'], 'not run (no --access-check)')
        self.assertFalse([event for event in self.world.timeline if event[0] == 'oneshot'
                          and event[1] == ('manage', 'participant_access_check')])
        self.assertFalse([event for event in self.world.timeline if event[0] == 'helper'])  # nothing scanned either
        self.assertIn('astra live, fable disabled', details['summary'])

    def test_without_participant_arguments_the_phase_is_as_it_was(self):
        # An args object naming no participant (the shape the earlier phase_app tests build) installs both disabled.
        args = SimpleNamespace(phase='app', revision=REVISION, receipts=str(self.tmp), provider_mode='disabled',
                               authorization_ref='')
        details = self.app(args)
        self.assertEqual([event[1] for event in self.world.timeline if event[0] == 'oneshot'], [('migrate',)])
        self.assertIn(('replace', 'disabled', '', {'astra': 'disabled', 'fable': 'disabled'}), self.world.timeline)
        self.assertEqual(details['participants'], {'astra': 'disabled', 'fable': 'disabled'})

    def test_the_access_check_runs_once_the_pair_runs_with_the_workers_mount_and_network(self):
        details = self.app(app_args(self.tmp, access=True))
        timeline = self.world.timeline
        recompute = timeline.index(('script', install.RECOMPUTE_STATES))
        checks = [(index, event) for index, event in enumerate(timeline)
                  if event[0] == 'oneshot' and event[1] == ('manage', 'participant_access_check')]
        self.assertEqual([event[2] for _, event in checks],
                         [['manage', 'participant_access_check', '--participant', 'astra'],
                          ['manage', 'participant_access_check', '--participant', 'fable']])
        self.assertTrue(all(index > recompute for index, _ in checks))
        for (_, event), name in zip(checks, ('astra', 'fable')):
            kwargs, spec = event[3], install.PARTICIPANTS[name]
            other = install.PARTICIPANTS['fable' if name == 'astra' else 'astra']
            self.assertEqual(kwargs['network'], install.NETWORK)
            self.assertEqual(kwargs['participant_files'], (name,))
            self.assertEqual(kwargs['timeout'], install.ACCESS_CHECK_SECONDS)
            env = flags(kwargs['environment'], '-e')
            for expected in (f'{spec["mode_env"]}=live', f'{other["mode_env"]}=disabled',
                             'CPT_STUDIO_PROVIDER_MODE=disabled', f'CPT_STUDIO_AUTHORIZATION_REF={RULING}',
                             f'{spec["file_env"]}={spec["mounted"]}'):
                self.assertIn(expected, env)
            self.assertFalse([item for item in env if item.startswith(other['file_env'])])
            check = details['access_checks'][name]
            self.assertEqual((check['ok'], check['exit'], check['recorded']), (True, 0, True))
            self.assertEqual(check['receipt'], {'participant': name, 'ok': True, 'request_id': 'req_synthetic'})
            self.assertTrue(Path(check['log']).exists())
        scans = [event for event in timeline if event[0] == 'helper']
        self.assertEqual([event[1] for event in scans],
                         [[f'type=bind,src={ASTRA["target"]},dst=/scan/astra,readonly'],
                          [f'type=bind,src={FABLE["target"]},dst=/scan/fable,readonly']])
        self.assertIn('access checked: astra, fable', details['summary'])

    def test_a_live_corti_is_access_checked_first_with_its_own_mount_and_nothing_else(self):
        details = self.app(app_args(self.tmp, provider='live', access=True))
        checks = [event for event in self.world.timeline
                  if event[0] == 'oneshot' and event[1] == ('manage', 'participant_access_check')]
        self.assertEqual([event[2][-1] for event in checks], ['corti', 'astra', 'fable'])
        corti = checks[0][3]
        self.assertTrue(corti['credentials'])
        self.assertNotIn('participant_files', corti)
        self.assertEqual((corti['network'], corti['timeout']), (install.NETWORK, install.ACCESS_CHECK_SECONDS))
        env = flags(corti['environment'], '-e')
        for expected in ('CPT_STUDIO_PROVIDER_MODE=live', 'CPT_STUDIO_ASTRA_MODE=disabled',
                         'CPT_STUDIO_FABLE_MODE=disabled', f'CPT_STUDIO_AUTHORIZATION_REF={RULING}',
                         f'CPT_STUDIO_CORTI_CREDENTIALS_FILE={install.CREDENTIALS_IN_CONTAINER}'):
            self.assertIn(expected, env)
        self.assertFalse([item for item in env if 'OPENAI' in item or 'ANTHROPIC' in item])
        # Astra's and Fable's checks run with Corti disabled and no Corti file
        for event in checks[1:]:
            self.assertNotIn('credentials', event[3])
            self.assertIn('CPT_STUDIO_PROVIDER_MODE=disabled', flags(event[3]['environment'], '-e'))
        scans = [event[1] for event in self.world.timeline if event[0] == 'helper']
        self.assertEqual(scans[0], [f'type=bind,src={install.CORTI_TARGET},dst=/scan/corti,readonly'])
        self.assertEqual(sorted(details['access_checks']), ['astra', 'corti', 'fable'])
        self.assertIn('access checked: corti, astra, fable', details['summary'])

    def test_a_corti_check_whose_output_carries_its_secret_is_not_recorded(self):
        self.world.answers[('access', 'corti')] = SimpleNamespace(
            returncode=0, stdout=json.dumps({'ok': True, 'error': f'401 for {CORTI_VALUE}'}).encode(), stderr=b'')
        with self.assertRaises(install.InstallError) as caught:
            self.app(app_args(self.tmp, provider='live', access=True))
        check = caught.exception.details['access_checks']['corti']
        self.assertEqual((check['ok'], check['recorded']), (False, False))
        self.assertNotIn(CORTI_VALUE, str(caught.exception) + json.dumps(caught.exception.details))
        # the two-letter environment ('eu', in every Corti endpoint) is below the scan's length and never matches
        self.world.answers[('access', 'corti')] = SimpleNamespace(
            returncode=0, stdout=b'{"endpoint": "https://api.eu.corti.app/v2/tools/coding/"}', stderr=b'')
        details = self.app(app_args(self.tmp, provider='live', access=True))
        self.assertTrue(details['access_checks']['corti']['ok'])

    def test_a_failed_access_check_fails_the_phase_and_says_the_pair_is_installed(self):
        self.world.answers[('access', 'fable')] = SimpleNamespace(
            returncode=3, stderr=b'', stdout=b'{"participant": "fable", "ok": false, "http_status": 401}\n')
        with self.assertRaises(install.InstallError) as caught:
            self.app(app_args(self.tmp, access=True))
        message = str(caught.exception)
        self.assertIn('web and worker running', message)
        self.assertIn('the access check did not pass for fable (it exited 3.)', message)
        self.assertIn('The pair stays installed', message)
        checks = caught.exception.details['access_checks']
        self.assertTrue(checks['astra']['ok'])
        self.assertEqual(checks['fable']['receipt'], {'participant': 'fable', 'ok': False, 'http_status': 401})

    def test_an_access_check_whose_output_carries_a_credential_value_is_not_recorded(self):
        self.world.answers[('access', 'astra')] = SimpleNamespace(
            returncode=0, stdout=json.dumps({'ok': True, 'header': f'Bearer {OPENAI_VALUE}'}).encode(), stderr=b'')
        with self.assertRaises(install.InstallError) as caught:
            self.app(app_args(self.tmp, access=True))
        check = caught.exception.details['access_checks']['astra']
        self.assertEqual((check['ok'], check['recorded']), (False, False))
        self.assertNotIn('receipt', check)
        self.assertNotIn(OPENAI_VALUE, str(caught.exception) + json.dumps(caught.exception.details))
        self.assertFalse(list(self.tmp.glob('app-*-access-check-astra.log')))  # no log of it either
        self.assertTrue(caught.exception.details['access_checks']['fable']['ok'])

    def test_an_access_check_that_does_not_finish_or_answers_no_receipt_fails(self):
        answered = self.world.oneshot

        def timing_out(image_id, command, env_bytes, **kwargs):
            if command[-1] == 'astra' and 'participant_access_check' in command:
                raise install.InstallError('docker run cpt-studio-oneshot did not finish within 420 s.')
            return answered(image_id, command, env_bytes, **kwargs)
        self.world.oneshot = timing_out
        self.world.answers[('access', 'fable')] = SimpleNamespace(returncode=0, stdout=b'checked\n', stderr=b'')
        with self.assertRaises(install.InstallError) as caught:
            self.app(app_args(self.tmp, access=True))
        checks = caught.exception.details['access_checks']
        self.assertIn('Whether its request reached the vendor is not known', checks['astra']['problem'])
        self.assertEqual(checks['fable']['problem'], 'its output was not one JSON receipt.')

    def test_an_interrupted_access_check_says_the_pair_stays_installed(self):
        def interrupted(image_id, command, env_bytes, **kwargs):
            if 'participant_access_check' in command:
                raise KeyboardInterrupt()
            return AppWorld.oneshot(self.world, image_id, command, env_bytes, **kwargs)
        self.world.oneshot = interrupted
        with self.assertRaises(install.InstallError) as caught:
            self.app(app_args(self.tmp, access=True))
        self.assertIn('the access check stopped (KeyboardInterrupt) after none: the pair stays installed',
                      str(caught.exception))


class NoCredentialValueLeavesTheInstallerTests(TemporaryDirectoryTest):
    """End to end through main(): whatever the participants' containers write, no credential value reaches the
    installer's stdout, its stderr, the receipt or any log beside it."""

    def run_main(self, answers):
        world = AppWorld(self.tmp)
        world.answers = answers
        receipts = self.tmp / 'receipts'
        stdout, stderr = io.StringIO(), io.StringIO()
        umask = os.umask(0o077)
        os.umask(umask)
        patches = world.patches() + [
            mock.patch.object(install, 'check_door', return_value={'declaration_commit': OTHER}),
            mock.patch.object(install, 'check_tree', return_value={'mode': 'exact'}),
            mock.patch('sys.stdout', stdout), mock.patch('sys.stderr', stderr)]
        for patcher in patches:
            patcher.start()
        try:
            code = install.main(['--phase', 'app', '--revision', REVISION, '--receipts', str(receipts),
                                 '--provider-mode', 'disabled', '--astra-mode', 'live', '--fable-mode', 'live',
                                 '--authorization-ref', RULING, '--access-check'])
        finally:
            for patcher in reversed(patches):
                patcher.stop()
            os.umask(umask)
        written = b''.join(path.read_bytes() for path in receipts.iterdir() if path.is_file())
        return code, stdout.getvalue(), stderr.getvalue(), written, receipts

    def test_no_value_reaches_stdout_stderr_a_receipt_or_a_log(self):
        leaks = {
            'access check stdout': {('access', 'astra'): SimpleNamespace(
                returncode=0, stdout=f'{{"key": "{OPENAI_VALUE}"}}'.encode(), stderr=b'')},
            'access check stderr': {('access', 'fable'): SimpleNamespace(
                returncode=1, stdout=b'{"ok": false}', stderr=f'401 for x-api-key {ANTHROPIC_VALUE}'.encode())},
            'parse check stderr': {('parse', 'astra'): SimpleNamespace(
                returncode=1, stdout=b'', stderr=f'Traceback: value {OPENAI_VALUE} refused'.encode())},
            'project id in a receipt': {('access', 'astra'): SimpleNamespace(
                returncode=0, stdout=b'{"project": "proj_synthetic0123"}', stderr=b'')},
        }
        for label, answers in leaks.items():
            with self.subTest(label):
                code, stdout, stderr, written, receipts = self.run_main(answers)
                self.assertEqual(code, 1)
                for value in (OPENAI_VALUE, ANTHROPIC_VALUE, 'proj_synthetic0123'):
                    self.assertNotIn(value, stdout)
                    self.assertNotIn(value, stderr)
                    self.assertNotIn(value.encode(), written)
                record = json.loads(sorted(receipts.glob('app-*.json'))[-1].read_text())
                self.assertFalse(record['ok'])

    def test_controls_a_clean_run_records_every_receipt(self):
        code, stdout, _, written, receipts = self.run_main({})
        self.assertEqual(code, 0, stdout)
        record = json.loads(sorted(receipts.glob('app-*.json'))[-1].read_text())
        self.assertEqual(sorted(record['details']['access_checks']), ['astra', 'fable'])
        self.assertIn(b'req_synthetic', written)


# --- the passages phase ------------------------------------------------------------------

class PassagesPhaseTests(TemporaryDirectoryTest):
    LISTING = (b'100644 blob ' + b'1' * 40 + b'\tcpt-studio/studio/reference/data/cms-claims-manual-ch12.json\0'
               b'100644 blob ' + b'2' * 40 + b'\tcpt-studio/studio/reference/data/cms-pfs-rvu26d-doc.json\0')

    def setUp(self):
        super().setUp()
        self.calls, self.results = [], {}

    def oneshot(self, image_id, command, env_bytes, **kwargs):
        self.calls.append(command)
        default = SimpleNamespace(returncode=0, stdout=f'Loaded {command[-1]}\n'.encode(), stderr=b'')
        return self.results.get(tuple(command), default)

    def passages(self, listing=None):
        ctx = install.Context(SimpleNamespace(phase='passages', revision=REVISION), self.tmp)
        listing = self.LISTING if listing is None else listing
        with mock.patch.object(install, 'run', return_value=SimpleNamespace(returncode=0, stdout=listing)) as run, \
                mock.patch.object(install, 'installed_image', return_value=IMAGE), \
                mock.patch.object(install, 'require_db'), \
                mock.patch.object(install, 'read_protected_env', return_value=b''), \
                mock.patch.object(install, 'oneshot', self.oneshot):
            details = install.phase_passages(ctx)
        self.assertEqual(run.call_args.args[0][3:], ['ls-tree', '-r', '-z', '--full-tree', REVISION, '--',
                                                     'cpt-studio/studio/reference/data/'])
        return details

    def test_each_committed_file_is_imported_after_migrations_are_checked(self):
        details = self.passages()
        self.assertEqual(self.calls, [
            ['manage', 'migrate', '--check'],
            ['manage', 'import_passages', '--data', '/app/studio/reference/data/cms-claims-manual-ch12.json'],
            ['manage', 'import_passages', '--data', '/app/studio/reference/data/cms-pfs-rvu26d-doc.json']])
        entry = details['files']['cms-pfs-rvu26d-doc.json']
        self.assertEqual(entry['git_blob'], '2' * 40)
        self.assertEqual(entry['output'], 'Loaded /app/studio/reference/data/cms-pfs-rvu26d-doc.json')
        self.assertTrue(Path(entry['log']).exists())

    def test_pending_migrations_refuse_before_any_import(self):
        self.results[('manage', 'migrate', '--check')] = SimpleNamespace(returncode=1, stdout=b'', stderr=b'')
        with self.assertRaisesRegex(install.InstallError, 'run --phase app first'):
            self.passages()
        self.assertEqual(self.calls, [['manage', 'migrate', '--check']])

    def test_a_link_a_submodule_or_no_file_refuses_before_any_container(self):
        for listing in (b'120000 blob ' + b'3' * 40 + b'\tcpt-studio/studio/reference/data/link.json\0',
                        b'160000 commit ' + b'4' * 40 + b'\tcpt-studio/studio/reference/data/module\0', b''):
            with self.subTest(listing=listing[:6]), self.assertRaises(install.InstallError):
                self.passages(listing)
            self.assertEqual(self.calls, [])

    def test_a_failed_import_names_its_file_and_what_was_imported_before_it(self):
        self.results[('manage', 'import_passages', '--data', '/app/studio/reference/data/cms-pfs-rvu26d-doc.json')] = \
            SimpleNamespace(returncode=1, stdout=b'', stderr=b'CommandError: a different file under the same release')
        with self.assertRaises(install.InstallError) as caught:
            self.passages()
        self.assertIn('import_passages cms-pfs-rvu26d-doc.json failed (exit 1)', str(caught.exception))
        self.assertEqual(list(caught.exception.details['imported']), ['cms-claims-manual-ch12.json'])

    def test_passage_files_reads_what_the_revision_commits(self):
        # The central reader, on a real repository (round 3, evidence:2: a reader mocked in every test).
        repo = self.tmp / 'repo'
        data = repo / 'cpt-studio' / 'studio' / 'reference' / 'data'
        data.mkdir(parents=True)

        def git(*args):
            return subprocess.run(['git', '-C', str(repo), '-c', 'user.name=Synthetic', '-c',
                                   'user.email=synthetic@example.invalid', '-c', 'commit.gpgsign=false', *args],
                                  check=True, capture_output=True, text=True).stdout.strip()
        git('init', '-q')
        (data / 'b.json').write_text('{"b": 1}\n')
        (data / 'nested').mkdir()
        (data / 'nested' / 'a.json').write_text('{"a": 1}\n')
        (repo / 'cpt-studio' / 'studio' / 'reference' / 'other.json').write_text('{}\n')  # not under data/
        (data / 'untracked.json').write_text('{}\n')
        git('add', 'cpt-studio/studio/reference/data/b.json', 'cpt-studio/studio/reference/data/nested/a.json',
            'cpt-studio/studio/reference/other.json')
        git('commit', '-q', '--no-verify', '-m', 'synthetic data')
        commit = git('rev-parse', 'HEAD')
        with mock.patch.object(install, 'ROOT', repo):
            files = install.passage_files(commit)
            self.assertEqual(list(files), ['b.json', 'nested/a.json'])
            self.assertEqual(files['b.json'], git('rev-parse', f'{commit}:cpt-studio/studio/reference/data/b.json'))
            (data / 'link.json').symlink_to('b.json')
            git('add', 'cpt-studio/studio/reference/data/link.json')
            git('commit', '-q', '--no-verify', '-m', 'synthetic link')
            with self.assertRaisesRegex(install.InstallError, 'link.json is not a regular file'):
                install.passage_files(git('rev-parse', 'HEAD'))


# --- the migration-safety check ----------------------------------------------------------

MIGRATION = '''from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('studio', '0007_harness_participants_retrieval')]
    operations = [
{operations}
    ]
'''


def verdict(*operations):
    return install.migration_verdict(MIGRATION.format(operations='\n'.join(f'        {op},' for op in operations)))


class MigrationSafetyTests(TemporaryDirectoryTest):
    def test_the_committed_migrations_after_the_baseline_are_accepted_and_say_why(self):
        verdicts = install.migration_safety(APP_ROOT / 'studio' / 'migrations')
        self.assertIn('0006_services_completeness_second_review', verdicts)
        self.assertIn('0007_harness_participants_retrieval', verdicts)
        self.assertFalse([name for name in verdicts if int(name[:4]) <= install.ROLLING_BASELINE])
        for name, found in verdicts.items():
            self.assertTrue(found['safe'], (name, found))
        why = verdicts['0007_harness_participants_retrieval']['why']
        for column in ('assessment.participants', 'assessment.retrieval', 'providerrun.endpoint',
                       'providerrun.requested_model', 'providerrun.returned_model', 'providerrun.response_id'):
            self.assertIn(f"{column}: NOT NULL, given a database default by this migration's SQL", why)
        self.assertIn('PassageSource: a new table no older revision reads', why)
        self.assertIn('ReferencePassage: a new table no older revision reads', why)

    def test_safe_shapes(self):
        cases = [
            "migrations.AddField(model_name='job', name='note', field=models.TextField(null=True))",
            "migrations.AddField(model_name='job', name='flag', field=models.BooleanField(db_default=False))",
            "migrations.AddField(model_name='job', name='other', field=models.ForeignKey(null=True, "
            "on_delete=models.PROTECT, to='studio.job'))",
            "migrations.AddIndex(model_name='job', index=models.Index(fields=['kind'], name='job_kind_idx'))",
            "migrations.CreateModel(name='Thing', fields=[('id', models.BigAutoField(primary_key=True))])",
            "migrations.AddConstraint(model_name='thing', constraint=models.UniqueConstraint(fields=['id'], "
            "name='u'))",
            "migrations.AddField(model_name='job', name='tier', field=models.CharField(default='x', max_length=4))",
            "migrations.RunSQL(sql=[\"ALTER TABLE studio_job ALTER COLUMN tier SET DEFAULT 'x'\"], reverse_sql=[])",
        ]
        found = verdict(*cases)
        self.assertTrue(found['safe'], found)
        self.assertEqual(len(found['why']), len(cases))

    def test_unsafe_operations_are_refused(self):
        cases = {
            'NOT NULL, no default': ["migrations.AddField(model_name='job', name='tier', "
                                     "field=models.CharField(default='x', max_length=4))"],
            'a default for another column': [
                "migrations.AddField(model_name='job', name='tier', field=models.CharField(default='x', max_length=4))",
                "migrations.RunSQL(sql=[\"ALTER TABLE studio_job ALTER COLUMN tiers SET DEFAULT 'x'\"])"],
            'a default on another table': [
                "migrations.AddField(model_name='job', name='tier', field=models.CharField(default='x', max_length=4))",
                "migrations.RunSQL(sql=[\"ALTER TABLE studio_encounter ALTER COLUMN tier SET DEFAULT 'x'\"])"],
            'removed column': ["migrations.RemoveField(model_name='job', name='attempts')"],
            'altered column': ["migrations.AlterField(model_name='job', name='kind', "
                               "field=models.CharField(max_length=20))"],
            'renamed column': ["migrations.RenameField(model_name='job', old_name='kind', new_name='stage')"],
            'removed table': ["migrations.DeleteModel(name='LoginAttempt')"],
            'python': ['migrations.RunPython(code=migrations.RunPython.noop)'],
            'other SQL': ["migrations.RunSQL(sql=['UPDATE studio_job SET kind = 1'])"],
            'SQL with a default and more': [
                "migrations.RunSQL(sql=[\"ALTER TABLE studio_job ALTER COLUMN kind SET DEFAULT 'x'\", "
                "'DROP TABLE studio_job'])"],
            'constraint on an existing table': [
                "migrations.AddConstraint(model_name='job', constraint=models.UniqueConstraint(fields=['kind'], "
                "name='u'))"],
            'many to many': ["migrations.AddField(model_name='job', name='tags', field=models.ManyToManyField("
                             "to='studio.job'))"],
            'positional arguments': ["migrations.AddField('job', 'note', models.TextField(null=True))"],
            'a non-null foreign key': ["migrations.AddField(model_name='job', name='other', field=models.ForeignKey("
                                       "on_delete=models.PROTECT, to='studio.job'))"],
        }
        for label, operations in cases.items():
            with self.subTest(label):
                found = verdict(*operations)
                self.assertFalse(found['safe'], found)
        self.assertFalse(install.migration_verdict('not python (')['safe'])
        self.assertFalse(install.migration_verdict('class Migration:\n    pass\n')['safe'])

    def test_a_file_that_is_not_a_migration_is_refused_and_the_baseline_is_not_read(self):
        directory = self.tmp / 'migrations'
        directory.mkdir()
        (directory / '__init__.py').write_text('')
        (directory / '0003_backfill.py').write_text(MIGRATION.format(
            operations='        migrations.RunPython(code=migrations.RunPython.noop),'))
        (directory / '0008_ok.py').write_text(MIGRATION.format(
            operations="        migrations.AddIndex(model_name='job', index=models.Index(fields=['kind'], name='i')),"))
        self.assertEqual(list(install.migration_safety(directory)), ['0008_ok'])  # 0003 is at or before the baseline
        (directory / 'notes.txt').write_text('synthetic')
        self.assertEqual(install.migration_safety(directory)['notes.txt']['safe'], False)

    def image_phase(self, operations):
        """The REAL phase_image on an archive whose migrations include ``operations``; docker is recorded."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as tar:
            for directory in ('cpt-studio', 'cpt-studio/studio', 'cpt-studio/studio/migrations', 'cpt-studio/deploy'):
                info = tarfile.TarInfo(directory)
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            files = {'cpt-studio/studio/migrations/__init__.py': b'',
                     'cpt-studio/studio/migrations/0008_synthetic.py': MIGRATION.format(operations='\n'.join(
                         f'        {op},' for op in operations)).encode(),
                     'cpt-studio/deploy/.dockerignore': b'', 'cpt-studio/deploy/Dockerfile': b'FROM synthetic\n'}
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        docker_calls = []

        def fake_docker(*args, **kwargs):
            docker_calls.append(args)
            return SimpleNamespace(returncode=1, stdout=b'', stderr=b'synthetic: no daemon here')
        ctx = install.Context(SimpleNamespace(phase='image', revision=REVISION), self.tmp)
        with mock.patch.object(install, 'run', return_value=SimpleNamespace(returncode=0, stdout=buffer.getvalue())), \
                mock.patch.object(install, 'docker', fake_docker), self.assertRaises(install.InstallError) as caught:
            install.phase_image(ctx)
        return caught.exception, docker_calls

    def test_the_image_phase_refuses_an_unsafe_migration_before_building(self):
        error, calls = self.image_phase(["migrations.RemoveField(model_name='job', name='attempts')"])
        self.assertIn('not additive for a pair that does not know them, so nothing was built', str(error))
        self.assertIn('0008_synthetic', str(error))
        self.assertEqual(calls, [])  # docker build never ran
        self.assertFalse(list(self.tmp.glob('build-*')))  # the build context was removed

    def test_controls_a_safe_migration_reaches_the_build(self):
        error, calls = self.image_phase(["migrations.AddIndex(model_name='job', index=models.Index(fields=['kind'], "
                                         "name='i'))"])
        self.assertIn('docker build failed', str(error))
        self.assertEqual([call[0] for call in calls], ['build'])


# --- rollback: participant stages and codes ------------------------------------------------

class RollbackParticipantTests(TemporaryDirectoryTest):
    def pair(self, revision=REVISION):
        return {role: {'Id': f'{role}-id', 'Image': IMAGE, 'Created': '2026-11-01T12:00:00.000000Z',
                       'State': {'Running': True},
                       'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role,
                                             install.REVISION_LABEL: revision}}}
                for role in ('web', 'worker')}

    def test_no_older_worker_runs_a_participant_stage_so_every_undo_closes_them(self):
        self.assertNotIn('astra', install.COMMON_STAGE_KINDS)
        self.assertNotIn('fable', install.COMMON_STAGE_KINDS)
        self.assertEqual(install.stage_kinds_of(None, b''), list(install.COMMON_STAGE_KINDS))
        # 80df1831d168's worker, asked in its own image, runs these: the participants' kinds are not among them
        installed = ['analyze', 'assess', 'extract', 'predict', 'review2']
        with mock.patch.object(install, 'app_script', return_value={'known': installed, 'stuck': 0, 'kinds': []}):
            self.assertEqual(install.stage_kinds_of(IMAGE, b''), installed)
        # the close fails, as for a second review, every stage of a kind the next worker does not run
        self.assertIn('Job.objects.exclude(kind__in=kept)', install.CLOSE_STAGES)

    def test_rollback_app_closes_with_the_next_workers_kinds_and_a_message(self):
        live, closed = self.pair(), {}
        calls = []

        def fake_docker(*args, **kwargs):
            calls.append(args)
            if args[0] == 'rm':
                live.pop('web' if 'web' in args[2] else 'worker', None)
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def close(image_id, env_bytes, since, revision, reason, kinds):
            closed.update(kinds=kinds, reason=reason)
            return {'closed': 2, 'kinds': ['astra', 'fable'], 'hazards': {}, 'relabel': []}
        names = {install.SERVICES[role]: role for role in ('web', 'worker')}
        with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: live.get(names.get(name))), \
                mock.patch.object(install, 'docker', fake_docker), \
                mock.patch.object(install, 'read_protected_env', return_value=b''), \
                mock.patch.object(install, 'require_db'), \
                mock.patch.object(install, 'undo_hazards', return_value={}), \
                mock.patch.object(install, 'close_undone_stages', close), \
                mock.patch.object(install, 'put_back_states', return_value={'encounters': 0, 'changed': {}}):
            details = install.phase_rollback_app(install.Context(SimpleNamespace(phase='rollback-app',
                                                                                 revision=REVISION), self.tmp))
        self.assertEqual(closed['kinds'], list(install.COMMON_STAGE_KINDS))
        self.assertEqual(closed['reason'], 'its web and worker were removed (rollback-app)')
        self.assertEqual(details['stages_closed']['kinds'], ['astra', 'fable'])
        note = ('Closed by the installer: its web and worker were removed (rollback-app) (revision aaaaaaaaaaaa), so '
                'this stage will not run.')
        with mock.patch.object(install, 'app_script', side_effect=lambda image, env, body, params, **kw: params):
            self.assertTrue(install.close_undone_stages(IMAGE, b'', install.dt.datetime(2026, 11, 1), REVISION,
                                                        closed['reason'], ['extract'])['note'].startswith(note))

    def test_a_participant_code_is_shown_wrongly_whatever_state_is_handed(self):
        self.assertIn('participant', install.SHOWN_HAZARDS)
        shown, acting = install.hazards_by_kind({'e1': ['participant'], 'e2': ['outcome', 'participant'],
                                                 'e3': ['unknown']})
        self.assertEqual(shown, {'e1': ['participant'], 'e2': ['participant']})
        self.assertEqual(acting, {'e2': ['outcome'], 'e3': ['unknown']})
        self.assertIn("support__origin='participant'", install.UNDO_HAZARDS)
        compile(install.UNDO_HAZARDS_READ, 'undo-hazards', 'exec')

    def test_rollback_app_refuses_before_stopping_anything_while_a_participant_code_is_held(self):
        live, calls = self.pair(), []
        names = {install.SERVICES[role]: role for role in ('web', 'worker')}
        with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: live.get(names.get(name))), \
                mock.patch.object(install, 'docker', side_effect=lambda *args, **kw: calls.append(args)), \
                mock.patch.object(install, 'read_protected_env', return_value=b''), \
                mock.patch.object(install, 'require_db'), \
                mock.patch.object(install, 'undo_hazards', return_value={'e1': ['participant']}), \
                mock.patch.object(install, 'close_undone_stages') as close, \
                self.assertRaises(install.InstallError) as caught:
            install.phase_rollback_app(install.Context(SimpleNamespace(phase='rollback-app', revision=REVISION),
                                                       self.tmp))
        self.assertIn('1 encounter(s): participant 1', str(caught.exception))
        self.assertIn('nothing was stopped or removed', str(caught.exception))
        self.assertEqual(calls, [])  # no docker stop
        close.assert_not_called()

    def test_a_failed_replacement_is_never_restored_over_a_participant_code(self):
        old = self.pair(OTHER)
        live = {install.SERVICES[role]: {**container, 'Id': f'old-{role}', 'Image': 'sha256:' + 'd' * 64}
                for role, container in old.items()}
        calls = []

        def fake_docker(*args, **kwargs):
            calls.append(args)
            if args[0] == 'rename':
                live[args[2]] = live.pop(args[1])
            elif args[0] == 'run':
                name = args[args.index('--name') + 1]
                role = 'web' if name == install.SERVICES['web'] else 'worker'
                live[name] = {**old[role], 'Id': f'new-{role}', 'Image': IMAGE}
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def wait(role, revision, image_id):
            if role == 'worker':
                raise install.InstallError('cpt-studio-worker did not become ready')
            return {'id': 'new-web'}
        ctx = install.Context(SimpleNamespace(phase='app', revision=REVISION), self.tmp)
        with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: live.get(name)), \
                mock.patch.object(install, 'docker', fake_docker), mock.patch.object(install, 'wait_service', wait), \
                mock.patch.object(install, 'stage_kinds_of', return_value=list(install.COMMON_STAGE_KINDS)), \
                mock.patch.object(install, 'close_undone_stages',
                                  return_value={'closed': 1, 'hazards': {'e1': ['participant']}, 'relabel': []}), \
                mock.patch.object(install, 'put_back_states',
                                  return_value={'encounters': 0, 'changed': {}}) as put_back, \
                self.assertRaises(install.InstallError) as caught:
            install.replace_services(ctx, IMAGE, b'', 'disabled', RULING, {'astra': 'live', 'fable': 'live'})
        message = str(caught.exception)
        self.assertIn('1 encounter(s): participant 1', message)
        self.assertIn('a code only a harness participant proposed', message)
        self.assertIn('the new pair was left stopped and the previous pair parked', message)
        put_back.assert_not_called()
        self.assertFalse([call for call in calls if call[0] == 'rename' and call[1].endswith('-previous')])
        self.assertIn(install.SERVICES['web'] + '-previous', live)


if __name__ == '__main__':
    unittest.main()
