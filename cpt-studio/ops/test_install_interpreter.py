"""Unit tests for the Gemini migration's installer additions (ops/install.py; design/FINAL.md 13, DECISIONS D14 and D22,
design/ADJUDICATION.md P-1 and P-7): the interpreter's credential spec and its unread copy, the worker-only bind,
--interpreter-mode, the offline loader check, the note switch-back and rollback-app declare and never refuse on, the
interpret stage on an undo, and verify's one-shot of the D22 report. No Docker, sudo, nginx or network.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

Every refusal is proven to refuse BEFORE it acts: the acting call (the copy, the migrate, the replacement, the stop) is
recorded and asserted not to have happened. Root-helper bodies run in-process against temporary directories, as in
test_install. The in-image scripts also run, as `manage shell -c` runs them, on a disposable PostgreSQL when one is
configured the way CI configures it (test_install_harness2's DatabaseTest); without one those tests are skipped, never
passed. Every credential value here is synthetic.
"""
import ast
import datetime as dt
import io
import json
import os
import sys
import unittest
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import FakeOwnership, TemporaryDirectoryTest, guard_host, release_host, run_body  # noqa: E402
from test_install_harness import (GEMINI_FILE, GEMINI_VALUE, IMAGE, INSTALLED, OPENAI_FILE,  # noqa: E402
                                  REVISION, RULING, AppWorld, app_args, flags)
from test_install_harness2 import DatabaseTest, module_constants, run_in_image  # noqa: E402
from test_install_bluegreen import KINDS_OLD, OLD, WEB, WORKER, container_on, rendered, sha  # noqa: E402
from test_install_r2 import run_rollback_app  # noqa: E402
from test_install_r3 import halfway_world, keep_world  # noqa: E402


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    try:
        harness2 = sys.modules.get('test_install_harness2')
        if harness2 is not None and 'connection' in harness2._DATABASE:  # this module's database tests made it
            connection = harness2._DATABASE.pop('connection')
            connection.creation.destroy_test_db(harness2._DATABASE.pop('old_name'), verbosity=0)
    finally:
        release_host()


APP_ROOT = Path(__file__).resolve().parents[1]
GEMINI = install.INTERPRETER
GEMINI_MOUNT = f'type=bind,src={GEMINI["target"]},dst={GEMINI["mounted"]},readonly'
NOTE_3 = '3 assessments were made from event inventories; the earlier image reads them fail-closed'


def module_literal(path, name):
    """A literal assigned at module level in ``path``, read with ast (no Django code is imported for it)."""
    return module_constants(APP_ROOT / path, (name,))[name]


def env_of(argv) -> dict:
    return dict(item.split('=', 1) for item in flags(argv, '-e'))


# --- the spec: what the installer names is what the application reads -------------------------------------------------

class InterpreterSpecTests(unittest.TestCase):
    def test_the_credential_is_copied_from_the_owners_source_to_the_path_D14_names(self):
        self.assertEqual(GEMINI['source'], '/etc/cpt-studio-provider-sources/gemini.env')
        self.assertEqual(GEMINI['target'], '/etc/cpt-studio/gemini.env')
        self.assertEqual(PurePosixPath(GEMINI['source']).parent, PurePosixPath(install.PROVIDER_SOURCES))
        self.assertEqual(PurePosixPath(GEMINI['target']).parent, PurePosixPath(install.ETC_DIR))
        self.assertEqual(PurePosixPath(GEMINI['mounted']).parent, PurePosixPath('/run/cpt-studio'))
        self.assertEqual((GEMINI['required'], GEMINI['optional']), (('GEMINI_API_KEY',), ()))
        # its own: never one of the participants (no access check, no participant mode, never a reassess participant)
        self.assertNotIn(GEMINI['name'], install.PARTICIPANTS)
        self.assertNotIn(GEMINI['target'], {spec['target'] for spec in install.PARTICIPANTS.values()})
        self.assertNotIn(GEMINI['mounted'], {install.CREDENTIALS_IN_CONTAINER,
                                             *(spec['mounted'] for spec in install.PARTICIPANTS.values())})
        self.assertEqual(install.credentials_target('gemini'), GEMINI['target'])
        self.assertEqual(install.credentials_target('corti'), install.CORTI_TARGET)
        self.assertEqual(install.credentials_target('astra'), install.PARTICIPANTS['astra']['target'])
        self.assertEqual(len(GEMINI_FILE), 69)  # the synthetic stand-in has the shape D14 records

    def test_the_names_the_installer_sets_are_the_ones_settings_reads(self):
        source = (APP_ROOT / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')
        for variable, setting, default in ((GEMINI['mode_env'], 'GEMINI_MODE', 'disabled'),
                                           (GEMINI['file_env'], 'GEMINI_CREDENTIALS_FILE', ''),
                                           (GEMINI['replay_env'], 'GEMINI_REPLAY_DIR', '')):
            with self.subTest(variable):
                self.assertEqual(variable, f'CPT_STUDIO_{setting}')  # settings._env prefixes CPT_STUDIO_
                self.assertIn(f"{setting} = _env('{setting}', '{default}')", source)
        self.assertEqual(GEMINI['setting'], 'GEMINI_CREDENTIALS_FILE')
        # every mode the installer offers is one settings accepts at import (anything else fails there)
        self.assertIn("if GEMINI_MODE not in {'disabled', 'replay', 'live'}:", source)
        self.assertEqual(set(install.INTERPRETER_MODES), {'disabled', 'replay', 'live'})

    def test_the_loader_check_calls_the_adapters_own_loader(self):
        body = install.INTERPRETER_CREDENTIALS_CHECK
        compile(body, 'interpreter-credentials-check', 'exec')
        self.assertEqual(body, 'from django.conf import settings\n'
                               'from studio.interpretation.adapter import load_gemini_credentials\n'
                               'load_gemini_credentials(settings.GEMINI_CREDENTIALS_FILE)\n'
                               "print('gemini-credentials-parse-ok')\n")
        tree = ast.parse((APP_ROOT / 'studio' / 'interpretation' / 'adapter.py').read_text(encoding='utf-8'))
        self.assertIn('load_gemini_credentials', {node.name for node in tree.body if isinstance(node, ast.FunctionDef)})
        self.assertEqual(module_literal('studio/interpretation/adapter.py', 'CREDENTIAL_KEY'), 'GEMINI_API_KEY')

    def test_replay_reads_the_recordings_the_image_ships(self):
        # the image is cpt-studio/ copied to /app (WORKDIR /app; COPY . .), and .dockerignore keeps tests/ in it
        dockerfile = (APP_ROOT / 'deploy' / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('WORKDIR /app', dockerfile)
        self.assertIn('COPY . .', dockerfile)
        ignored = [line.strip() for line in (APP_ROOT / 'deploy' / '.dockerignore').read_text().splitlines()
                   if line.strip() and not line.startswith('#')]
        self.assertFalse([pattern for pattern in ignored
                          if pattern.rstrip('/') == 'tests' or pattern.startswith('tests/') or 'fixtures' in pattern])
        relative = PurePosixPath(GEMINI['replay_dir']).relative_to('/app')
        self.assertEqual(str(relative), 'tests/fixtures/interpretation')
        self.assertTrue((APP_ROOT / relative).is_dir())
        # ReplayInterpreter reads <dir>/<adapter.NAME>/<request sha256>.json, and adapter.NAME is the provider 'gemini'
        replay = (APP_ROOT / 'studio' / 'interpretation' / 'replay.py').read_text(encoding='utf-8')
        self.assertIn('folder = self.replay_dir / adapter.NAME', replay)
        self.assertEqual(module_literal('studio/interpretation/__init__.py', 'PROVIDER'), 'gemini')

    def test_the_interpret_stage_is_not_a_kind_every_worker_runs(self):
        kind = module_literal('studio/interpretation/__init__.py', 'JOB_KIND')
        self.assertEqual(kind, 'interpret')
        self.assertNotIn(kind, install.COMMON_STAGE_KINDS)
        self.assertNotIn(kind, KINDS_OLD)  # the installed c2e53f8e-era worker's kinds, as the fake host's old image
        # with no next worker to ask, an undo keeps only the common kinds: every interpret stage is closed
        self.assertEqual(install.stage_kinds_of(None, b''), list(install.COMMON_STAGE_KINDS))
        self.assertIn('Job.objects.exclude(kind__in=kept)', install.CLOSE_STAGES)
        self.assertIn('Job.objects.exclude(kind__in=known)', install.UNRUNNABLE_STAGES)

    def test_an_assessment_made_from_an_inventory_is_no_hazard_of_either_kind(self):
        # ADJUDICATION P-1, which governs FINAL 13: never a refusing reason; a declared note instead
        self.assertNotIn('interpretation', install.SHOWN_HAZARDS)
        self.assertNotIn("add('interpretation')", install.UNDO_HAZARDS)
        self.assertNotIn('event_inventory', install.UNDO_HAZARDS)
        self.assertNotIn('INTERPRETATION_MADE', install.UNDO_HAZARDS + install.CLOSE_STAGES)
        compile(install.INTERPRETATION_MADE, 'interpretation-made', 'exec')
        # it counts both shapes of a new-path assessment: the engine's label family (interpretation.is_new_assessment)
        # and the inventory it names
        self.assertIn('Q(event_inventory__isnull=False)', install.INTERPRETATION_MADE)
        self.assertIn("interpretation.ENGINE_VERSION.partition('@')[0] + '@'", install.INTERPRETATION_MADE)
        source = (APP_ROOT / 'studio' / 'interpretation' / '__init__.py').read_text(encoding='utf-8')
        self.assertIn("return version.partition('@')[0] + '@'", source)  # _family, the same prefix

    def test_the_self_test_checks_verify_requires_are_the_reports_own(self):
        self.assertEqual(install.INTERPRETATION_SELF_TEST,
                         module_literal('studio/interpretation/report.py', 'SELF_TEST'))
        command = (APP_ROOT / 'studio' / 'management' / 'commands' / 'interpretation_report.py').read_text()
        for option in ("'--since'", "'--self-test'", "'--json'"):
            self.assertIn(f'parser.add_argument({option}', command)
        self.assertIn("json.dumps({'report': found, 'self_test': test}", command)


# --- arguments --------------------------------------------------------------------------------------------------------

class InterpreterArgumentTests(unittest.TestCase):
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

    def test_the_mode_is_disabled_unless_given_and_any_of_the_three_may_be(self):
        self.assertEqual(self.parse('--phase', 'app', '--provider-mode', 'disabled').interpreter_mode, 'disabled')
        self.assertEqual(self.parse('--phase', 'preflight').interpreter_mode, 'disabled')
        for phase in ('app', 'switch-back'):
            for mode in ('disabled', 'replay'):
                with self.subTest(phase=phase, mode=mode):
                    self.assertEqual(self.parse('--phase', phase, '--provider-mode', 'disabled', '--interpreter-mode',
                                                mode).interpreter_mode, mode)
            args = self.parse('--phase', phase, '--provider-mode', 'disabled', '--interpreter-mode', 'live',
                              '--authorization-ref', RULING)
            self.assertEqual((args.interpreter_mode, args.authorization_ref), ('live', RULING))

    def test_refusals(self):
        # live sends under the recorded authority, as the providers and participants do (jobs._live_gate)
        self.assertIn('--interpreter-mode live needs --authorization-ref',
                      self.refused('--phase', 'app', '--provider-mode', 'disabled', '--interpreter-mode', 'live'))
        self.assertIn('--interpreter-mode live needs --authorization-ref',
                      self.refused('--phase', 'switch-back', '--provider-mode', 'disabled', '--interpreter-mode',
                                   'live'))
        self.refused('--phase', 'app', '--provider-mode', 'disabled', '--interpreter-mode', 'on')
        # an authorization nothing live uses is refused, as before (and replay is not live)
        self.assertIn('only applies to', self.refused('--phase', 'app', '--provider-mode', 'disabled',
                                                      '--interpreter-mode', 'replay', '--authorization-ref', RULING))
        # the access check is the participants': the interpreter alone does not make one
        self.assertIn('--access-check checks each live participant',
                      self.refused('--phase', 'app', '--provider-mode', 'disabled', '--interpreter-mode', 'live',
                                   '--authorization-ref', RULING, '--access-check'))
        for phase in ('preflight', 'secrets', 'image', 'db', 'verify', 'rollback-app', 'reassess', 'license-note'):
            with self.subTest(phase=phase):
                self.assertIn('--interpreter-mode is not used by --phase',
                              self.refused('--phase', phase, '--interpreter-mode', 'disabled'))

    def test_an_args_object_that_names_no_interpreter_is_disabled(self):
        self.assertEqual(install.interpreter_mode(SimpleNamespace()), 'disabled')
        self.assertEqual(install.interpreter_mode(SimpleNamespace(interpreter_mode=None)), 'disabled')
        self.assertEqual(install.interpreter_mode(SimpleNamespace(interpreter_mode='replay')), 'replay')
        with self.assertRaises(install.InstallError):
            install.interpreter_mode(SimpleNamespace(interpreter_mode='LIVE'))


# --- docker arguments: the worker alone holds the key -----------------------------------------------------------------

class InterpreterServiceArgumentTests(unittest.TestCase):
    def test_only_a_live_interpreters_worker_mounts_the_key_and_the_web_gets_the_path_and_no_file(self):
        worker = install.service_args('worker', IMAGE, REVISION, 'disabled', RULING, interpreter='live')
        web = install.service_args('web', IMAGE, REVISION, 'disabled', RULING, interpreter='live')
        self.assertIn(GEMINI_MOUNT, flags(worker, '--mount'))
        self.assertEqual(flags(web, '--mount'), [f'type=volume,src={install.FILES_VOLUME},dst={install.STATE_DIR}'])
        for argv in (worker, web):
            env = env_of(argv)
            self.assertEqual((env['CPT_STUDIO_GEMINI_MODE'], env['CPT_STUDIO_GEMINI_CREDENTIALS_FILE']),
                             ('live', GEMINI['mounted']))
            self.assertNotIn('CPT_STUDIO_GEMINI_REPLAY_DIR', env)
        self.assertEqual(flags(web, '-e'), flags(worker, '-e'))  # the web is named everything the worker is

    def test_disabled_and_replay_mount_nothing_and_name_no_key(self):
        for mode in (None, 'disabled', 'replay'):
            for role in ('web', 'worker'):
                argv = install.service_args(role, IMAGE, REVISION, 'live', RULING, {'astra': 'live'},
                                            interpreter=mode)
                with self.subTest(mode=mode, role=role):
                    self.assertNotIn(GEMINI_MOUNT, flags(argv, '--mount'))
                    env = env_of(argv)
                    self.assertEqual(env['CPT_STUDIO_GEMINI_MODE'], mode or 'disabled')
                    self.assertNotIn('CPT_STUDIO_GEMINI_CREDENTIALS_FILE', env)
                    self.assertEqual(env.get('CPT_STUDIO_GEMINI_REPLAY_DIR'),
                                     GEMINI['replay_dir'] if mode == 'replay' else None)
                    self.assertNotIn('gemini.env', ' '.join(argv))
        # the providers and participants are as they were beside it
        worker = install.service_args('worker', IMAGE, REVISION, 'live', RULING, {'astra': 'live'}, interpreter='live')
        mounts = flags(worker, '--mount')
        self.assertIn(f'type=bind,src={install.CORTI_TARGET},dst={install.CREDENTIALS_IN_CONTAINER},readonly', mounts)
        self.assertIn(install.participant_mount('astra'), mounts)
        self.assertEqual(mounts[-1], GEMINI_MOUNT)

    def test_an_unknown_mode_is_refused_rather_than_started(self):
        with self.assertRaises(install.InstallError):
            install.service_args('worker', IMAGE, REVISION, 'disabled', '', interpreter='LIVE')

    def test_one_shots_run_the_interpreter_disabled_and_the_loader_check_mounts_the_key_offline(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout=b'gemini-credentials-parse-ok\n', stderr=b'')
        with mock.patch.object(install, 'run', fake_run), mock.patch.object(install, 'inspect', return_value=None):
            install.oneshot(IMAGE, ['migrate'], b'')
            install.oneshot(IMAGE, ['manage', 'shell', '-c', install.INTERPRETER_CREDENTIALS_CHECK], b'',
                            network='none', interpreter_file=True)
        plain, checked = calls
        self.assertEqual(env_of(plain)['CPT_STUDIO_GEMINI_MODE'], 'disabled')
        self.assertNotIn('gemini.env', ' '.join(plain))
        self.assertEqual(flags(checked, '--network'), ['none'])
        self.assertEqual(flags(checked, '--mount'), [GEMINI_MOUNT])
        env = env_of(checked)
        self.assertEqual((env['CPT_STUDIO_GEMINI_MODE'], env['CPT_STUDIO_GEMINI_CREDENTIALS_FILE']),
                         ('disabled', GEMINI['mounted']))  # the file is read; the interpreter itself stays disabled
        self.assertEqual(env['CPT_STUDIO_PROVIDER_MODE'], 'disabled')

    def test_no_secret_name_or_value_is_ever_an_argument(self):
        for role in ('web', 'worker'):
            joined = ' '.join(install.service_args(role, IMAGE, REVISION, 'live', RULING, {'astra': 'live'},
                                                   interpreter='live'))
            for name in ('API_KEY', 'SECRET_KEY', 'DB_PASSWORD', 'CLIENT_SECRET', GEMINI_VALUE):
                self.assertNotIn(name, joined)


class InterpreterServiceMountTests(unittest.TestCase):
    def container(self, role, mounts):
        return {'Image': IMAGE, 'Config': {'User': f'{install.APP_UID}:{install.APP_UID}',
                                           'Labels': {install.LABEL: '1', install.ROLE_LABEL: role}},
                'HostConfig': {'ReadonlyRootfs': True, 'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
                               'PortBindings': ({'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '9150'}]}
                                                if role == 'web' else {})},
                'Mounts': mounts}

    def bind(self, source, destination, writable=False):
        return {'Type': 'bind', 'Source': source, 'Destination': destination, 'RW': writable}

    def test_the_worker_may_hold_the_key_read_only_and_the_web_never(self):
        volume = {'Type': 'volume', 'Name': install.FILES_VOLUME, 'Destination': install.STATE_DIR, 'RW': True}
        key = self.bind(GEMINI['target'], GEMINI['mounted'])
        self.assertEqual(install.service_problems(self.container('worker', [volume, key]), 'worker', IMAGE), [])
        self.assertEqual(install.service_problems(self.container('web', [volume, key]), 'web', IMAGE),
                         ['the web holds a bind-mounted file (only the worker holds credentials)'])
        for wrong in (self.bind(GEMINI['target'], GEMINI['mounted'], writable=True),
                      self.bind(GEMINI['target'], install.CREDENTIALS_IN_CONTAINER),
                      self.bind('/etc/cpt-studio-provider-sources/gemini.env', GEMINI['mounted'])):
            with self.subTest(wrong=wrong):
                self.assertEqual(install.service_problems(self.container('worker', [volume, wrong]), 'worker', IMAGE),
                                 ['a bind mount other than a read-only credentials file'])


# --- the secrets phase: copied unread, by key name only ---------------------------------------------------------------

class InterpreterSecretsHelperTests(TemporaryDirectoryTest):
    """H_PARTICIPANT_SECRETS executed in-process for the interpreter; interpreter_secrets() builds its parameters and
    mounts for real."""

    def setUp(self):
        super().setUp()
        self.target = self.tmp / 'target'
        self.sources = self.tmp / 'sources'
        self.target.mkdir(mode=0o700)
        self.sources.mkdir(mode=0o700)
        os.chmod(self.sources, 0o700)
        self.fake = FakeOwnership()
        self.fake.owners[str(self.sources)] = (0, 0)
        self.calls = []

    def source(self, name, data, *, mode=0o600):
        path = self.sources / name
        path.write_bytes(data)
        os.chmod(path, mode)
        self.fake.owners[str(path)] = (0, 0)
        return path

    def helper(self, body, params, *, mounts, sensitive=False, **kwargs):
        self.calls.append({'body': body, 'params': params, 'mounts': mounts, 'sensitive': sensitive})
        result = run_body(body, params, {"'/target'": repr(str(self.target)), "'/sources'": repr(str(self.sources))},
                          self.fake)
        if result.get('error'):
            raise install.InstallError(f'Root helper refused: {result["error"]}', details=result)
        return result

    def copy(self, folder=None):
        folder = folder or {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o700'}
        with mock.patch.object(install, 'helper_stat', return_value={install.PROVIDER_SOURCES: folder}), \
                mock.patch.object(install, 'run_helper', self.helper):
            return install.interpreter_secrets()

    def refused(self):
        before = sorted(path.name for path in self.target.iterdir())
        with self.assertRaises(install.InstallError) as caught:
            self.copy()
        self.assertEqual(sorted(path.name for path in self.target.iterdir()), before)  # nothing was written
        self.assertNotIn(GEMINI_VALUE, str(caught.exception) + json.dumps(caught.exception.details))
        return str(caught.exception)

    def test_the_source_is_copied_once_byte_for_byte_and_only_its_key_name_is_reported(self):
        self.source('gemini.env', GEMINI_FILE)
        self.source('openai.env', OPENAI_FILE)  # a participant's source beside it is not this run's to copy
        report = self.copy()
        self.assertEqual(report, {'gemini': {'state': 'created', 'source': 'present', 'key_names': ['GEMINI_API_KEY']}})
        copy = self.target / 'gemini.env'
        self.assertEqual(copy.read_bytes(), GEMINI_FILE)
        self.assertEqual(os.stat(copy).st_mode & 0o777, 0o400)
        self.assertEqual(self.fake.owners.get(str(copy)), (install.APP_UID, install.APP_UID))
        self.assertEqual(sorted(path.name for path in self.target.iterdir()), ['gemini.env'])
        call = self.calls[0]
        self.assertIs(call['body'], install.H_PARTICIPANT_SECRETS)
        self.assertTrue(call['sensitive'])  # its stderr is never kept
        self.assertEqual(call['mounts'], [f'type=bind,src={install.ETC_DIR},dst=/target',
                                          f'type=bind,src={install.PROVIDER_SOURCES},dst=/sources,readonly'])
        self.assertEqual([entry['name'] for entry in call['params']['participants']], ['gemini'])
        for text in (json.dumps(report), json.dumps(call['params'])):
            self.assertNotIn(GEMINI_VALUE, text)
        again = self.copy()
        self.assertEqual(again['gemini']['state'], 'present')
        self.assertEqual(copy.read_bytes(), GEMINI_FILE)

    def test_a_missing_source_leaves_the_interpreter_not_provided(self):
        self.assertEqual(self.copy()['gemini'], {'state': 'not provided', 'source': 'absent', 'key_names': []})
        self.assertEqual(list(self.target.iterdir()), [])
        report = self.copy({'exists': False})  # no sources directory at all: nothing mounted or written
        self.assertEqual(report['gemini']['state'], 'not provided')
        self.assertEqual(self.calls[-1]['mounts'], [f'type=bind,src={install.ETC_DIR},dst=/target'])

    def test_every_refusal_writes_nothing(self):
        cases = {
            'group-readable source': (GEMINI_FILE, 0o640, 'not a root-owned 0600 regular file'),
            'another key name': (b'GOOGLE_API_KEY=' + GEMINI_VALUE.encode() + b'\n', 0o600,
                                 'lacks key name(s): GEMINI_API_KEY'),
            'an extra key': (GEMINI_FILE + b'GEMINI_PROJECT=synthetic\n', 0o600, '1 line(s) setting no key'),
            'a pasted key with no name': (GEMINI_FILE + GEMINI_VALUE.encode() + b'\n', 0o600,
                                          '1 line(s) setting no key'),
            'the key twice': (GEMINI_FILE + GEMINI_FILE, 0o600, 'sets GEMINI_API_KEY more than once'),
            'too large': (GEMINI_FILE + b'#' * install.PARTICIPANT_FILE_LIMIT, 0o600, 'larger than'),
        }
        for label, (data, mode, message) in cases.items():
            with self.subTest(label):
                for path in self.sources.iterdir():
                    path.unlink()
                self.source('gemini.env', data, mode=mode)
                self.assertIn(message, self.refused())

    def test_an_installed_copy_must_equal_its_source(self):
        source = self.source('gemini.env', GEMINI_FILE)
        self.copy()
        source.write_bytes(GEMINI_FILE.replace(b'0123', b'9999'))
        self.assertIn('differs from its source', self.refused())
        self.assertEqual((self.target / 'gemini.env').read_bytes(), GEMINI_FILE)  # kept as it was

    def test_the_sources_directory_is_judged_before_it_is_mounted(self):
        with mock.patch.object(install, 'helper_stat', return_value={install.PROVIDER_SOURCES: {
                'exists': True, 'kind': 'dir', 'uid': 1000, 'gid': 0, 'mode': '0o700'}}), \
                mock.patch.object(install, 'run_helper') as helper, \
                self.assertRaisesRegex(install.InstallError, 'no interpreter credentials file was copied'):
            install.interpreter_secrets()
        helper.assert_not_called()

    def test_preflight_names_a_source_that_is_not_root_only_and_accepts_one_that_is_absent(self):
        self.assertEqual(install.interpreter_source_problems({GEMINI['source']: {'exists': False}}), [])
        good = {'exists': True, 'kind': 'file', 'uid': 0, 'gid': 0, 'mode': '0o600'}
        self.assertEqual(install.interpreter_source_problems({GEMINI['source']: good}), [])
        for wrong in ({**good, 'mode': '0o644'}, {**good, 'uid': 1000}, {**good, 'kind': 'link'}):
            with self.subTest(wrong=wrong):
                self.assertEqual(install.interpreter_source_problems({GEMINI['source']: wrong}),
                                 [f'{GEMINI["source"]} is not a root-owned 0600 regular file'])


class PreflightInterpreterTests(TemporaryDirectoryTest):
    """The REAL phase_preflight, every host read replaced: the interpreter's source is stat'd beside the participants',
    reported, and refused when it is there and not root-only (the secrets phase would refuse it later)."""

    def preflight(self, gemini_source):
        asked = []

        def stat(paths):
            asked.append(list(paths))
            found = {path: {'exists': True, 'kind': 'dir', 'uid': 0, 'gid': 0, 'mode': '0o700'} for path in paths}
            found[install.CORTI_SOURCE] = {'exists': True, 'kind': 'file', 'uid': 0, 'gid': 0, 'mode': '0o600'}
            for spec in install.PARTICIPANTS.values():
                found[spec['source']] = found[spec['target']] = {'exists': False}
            found[GEMINI['source']], found[GEMINI['target']] = gemini_source, {'exists': False}
            return {path: found[path] for path in paths}

        def helper(body, params, **kwargs):
            return {'written': True} if body is install.H_ACME_WRITE else {'removed': True}
        le = {'dirs': {directory: True for directory in [*install.LE_DIRS, install.ACME_CHALLENGE_DIR]},
              'accounts': ['one'], 'live': {}, 'renewal': {}}
        with mock.patch.multiple(
                install, docker_positive_control=mock.Mock(return_value='27.0.0'),
                nginx_file_state=mock.Mock(return_value={'available': {'quillmd': install.QUILLMD_VHOST_SHA256},
                                                         'enabled': {}, 'nginx_conf_sha256': '0' * 64, 'conf_d': {}}),
                nginx_test=mock.Mock(return_value={'ok': True, 'warnings': [], 'output': 'test is successful'}),
                enabled_config_texts=mock.Mock(return_value=[]), routing_targets=mock.Mock(return_value=[]),
                routing_snapshot=mock.Mock(return_value={}), cpt_probes=mock.Mock(return_value={}),
                vhost_state=mock.Mock(return_value={}), app_health=mock.Mock(return_value={'status': 200, 'json': {}}),
                cotenant_check=mock.Mock(return_value={'returncode': 0}), containers=mock.Mock(return_value={}),
                volumes=mock.Mock(return_value=[]), networks=mock.Mock(return_value=[]),
                web_port_layout=mock.Mock(return_value={'problems': []}), port_problem=mock.Mock(return_value=''),
                foreign_uid_tasks=mock.Mock(return_value=0), own_service_ids=mock.Mock(return_value=[]),
                inspect=mock.Mock(return_value={'Id': 'present'}), helper_stat=stat,
                le_state=mock.Mock(return_value=le), run_helper=helper), \
                mock.patch.object(install.socket, 'getaddrinfo',
                                  return_value=[(install.socket.AF_INET, 1, 6, '', (install.PUBLIC_IPV4, 443))]), \
                mock.patch.object(install.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 2 ** 30)):
            ctx = install.Context(SimpleNamespace(phase='preflight', revision=REVISION, receipts=str(self.tmp)),
                                  self.tmp)
            try:
                return install.phase_preflight(ctx), None, asked
            except install.InstallError as error:
                return None, error, asked

    def test_the_source_is_read_with_the_others_and_reported(self):
        for source, said in (({'exists': False}, 'absent'),
                             ({'exists': True, 'kind': 'file', 'uid': 0, 'gid': 0, 'mode': '0o600'}, 'present')):
            with self.subTest(said):
                details, error, asked = self.preflight(source)
                self.assertIsNone(error, error and str(error))
                self.assertEqual(details['interpreter_source'], said)
                self.assertIn(GEMINI['source'], asked[0])
                self.assertIn(GEMINI['target'], asked[0])

    def test_a_source_that_is_not_root_only_is_a_problem(self):
        details, error, asked = self.preflight({'exists': True, 'kind': 'file', 'uid': 0, 'gid': 0, 'mode': '0o644'})
        self.assertIsInstance(error, install.InstallError)
        self.assertIn(f'{GEMINI["source"]} is not a root-owned 0600 regular file', str(error))
        self.assertEqual(error.details['interpreter_source'], 'present')


class InterpreterCredentialScanTests(TemporaryDirectoryTest):
    def test_a_gemini_value_is_found_and_only_its_key_name_comes_back(self):
        (self.tmp / 'gemini').write_bytes(GEMINI_FILE)
        seen = []

        def helper(body, params, *, mounts=(), sensitive=False, **kwargs):
            seen.append((list(mounts), sensitive))
            return run_body(body, params, {"'/scan/'": repr(str(self.tmp) + '/')})
        with mock.patch.object(install, 'run_helper', helper):
            self.assertTrue(install.credential_free([b'CredentialsError: GEMINI_API_KEY is missing.'], ['gemini']))
            self.assertFalse(install.credential_free([b'x-goog-api-key: ' + GEMINI_VALUE.encode()], ['gemini']))
        self.assertEqual(seen[0], ([f'type=bind,src={GEMINI["target"]},dst=/scan/gemini,readonly'], True))


# --- the app phase: the interpreter's checks, before anything changes -------------------------------------------------

class AppPhaseInterpreterTests(TemporaryDirectoryTest):
    """The REAL phase_app (its checks and credential_free included) in test_install_harness's AppWorld."""

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
        return [event for event in self.world.timeline if event[0] == 'replace'
                or (event[0] == 'oneshot' and event[1] in (('migrate',), ('manage', 'participant_access_check')))]

    def live(self, **extra):
        return app_args(self.tmp, astra='disabled', fable='disabled', interpreter='live', **extra)

    def test_without_its_installed_copy_live_refuses_before_anything_changes(self):
        for state in ({'exists': False}, {**INSTALLED, 'mode': '0o440'}, {**INSTALLED, 'uid': 0, 'gid': 0},
                      {**INSTALLED, 'kind': 'link'}):
            self.world.timeline.clear()
            self.world.stat[GEMINI['target']] = state
            with self.subTest(state=state), self.assertRaises(install.InstallError) as caught:
                self.app(self.live())
            self.assertIn('--interpreter-mode live', str(caught.exception))
            self.assertIn(GEMINI['source'], str(caught.exception))
            self.assertFalse([event for event in self.world.timeline if event[0] in ('oneshot', 'replace', 'script')])

    def test_the_loader_check_runs_offline_in_the_workers_layout_before_migrate(self):
        details = self.app(self.live())
        commands = [event for event in self.world.timeline if event[0] == 'oneshot']
        self.assertEqual([event[2] for event in commands],
                         [['manage', 'shell', '-c', install.INTERPRETER_CREDENTIALS_CHECK], ['migrate']])
        self.assertEqual(commands[0][3], {'network': 'none', 'interpreter_file': True, 'timeout': 120})
        self.assertEqual(self.world.interpreter, 'live')  # the pair is started with it
        self.assertEqual(details['interpreter'], {'mode': 'live', 'credentials_loaded': True,
                                                  'worker_started_at': '2026-11-09T10:00:00.000Z'})
        self.assertIn('(provider disabled, astra disabled, fable disabled, interpreter live)', details['summary'])
        self.assertEqual(details['access_checks'], 'not run (no --access-check)')  # it has none of its own

    def test_a_file_its_loader_refuses_stops_before_migrating_and_its_error_is_kept_only_when_clean(self):
        for stderr, kept in ((b'CredentialsError: GEMINI_API_KEY is missing from the Gemini credentials file.', True),
                             (b'CredentialsError: bad value ' + GEMINI_VALUE.encode(), False)):
            self.world.timeline.clear()
            self.world.answers[('parse', 'gemini')] = SimpleNamespace(returncode=1, stdout=b'', stderr=stderr)
            with self.subTest(kept=kept), self.assertRaises(install.InstallError) as caught:
                self.app(self.live())
            self.assertIn('cannot load /etc/cpt-studio/gemini.env as mounted for the worker', str(caught.exception))
            self.assertEqual(caught.exception.output, stderr if kept else b'')
            self.assertEqual(self.acted(), [])  # no migrate, no replacement
            self.assertNotIn(GEMINI_VALUE, str(caught.exception))

    def test_replay_and_disabled_need_no_file_and_no_check(self):
        for mode in ('replay', 'disabled'):
            self.world.timeline.clear()
            self.world.stat[GEMINI['target']] = {'exists': False}
            with self.subTest(mode=mode):
                details = self.app(app_args(self.tmp, astra='disabled', fable='disabled', interpreter=mode))
                self.assertEqual([event[1] for event in self.world.timeline if event[0] == 'oneshot'], [('migrate',)])
                self.assertEqual(details['interpreter']['mode'], mode)
                self.assertFalse(details['interpreter']['credentials_loaded'])
                # the default is never named to replace_services (its stand-ins keep the arguments they had)
                self.assertEqual(self.world.interpreter, None if mode == 'disabled' else mode)

    def test_an_args_object_that_names_no_interpreter_installs_it_disabled_as_before(self):
        args = SimpleNamespace(phase='app', revision=REVISION, receipts=str(self.tmp), provider_mode='disabled',
                               authorization_ref='')
        details = self.app(args)
        self.assertEqual(details['interpreter']['mode'], 'disabled')
        self.assertIsNone(self.world.interpreter)
        self.assertEqual([event[1] for event in self.world.timeline if event[0] == 'oneshot'], [('migrate',)])


# --- ADJUDICATION P-1: the declared note, never a refusal -------------------------------------------------------------

class InterpretationNoteTests(unittest.TestCase):
    def note(self, answer):
        def script(image_id, env_bytes, body, params, **kwargs):
            self.assertEqual((image_id, body, params), (IMAGE, install.INTERPRETATION_MADE, {}))
            if isinstance(answer, BaseException):
                raise answer
            return answer
        with mock.patch.object(install, 'app_script', script):
            return install.interpretation_note(IMAGE, b'', REVISION)

    def test_the_count_and_the_encounters_with_the_sentence_p1_gives(self):
        self.assertEqual(self.note({'interpretation': {'assessments': 3, 'encounters': ['e1', 'e2']}}),
                         {'assessments': 3, 'encounters': ['e1', 'e2'], 'note': NOTE_3})
        self.assertEqual(self.note({'interpretation': {'assessments': 1, 'encounters': ['e1']}})['note'],
                         '1 assessment was made from event inventories; the earlier image reads them fail-closed')
        self.assertEqual(self.note({'interpretation': {'assessments': 0, 'encounters': []}})['assessments'], 0)
        self.assertEqual(self.note({'interpretation': None}),
                         {'assessments': 0, 'encounters': [],
                          'note': 'this image keeps no event inventory, so no assessment was made from one'})

    def test_a_read_that_fails_or_says_nothing_is_recorded_as_not_counted_and_never_stops_an_undo(self):
        for answer in (install.InstallError('Counting ... failed (exit 1).'), {}, {'interpretation': 'three'},
                       {'interpretation': {'assessments': -1, 'encounters': []}},
                       {'interpretation': {'assessments': 1, 'encounters': ['e1', 'e2']}},
                       {'interpretation': {'assessments': True, 'encounters': []}}, ['not', 'a', 'dict']):
            with self.subTest(answer=answer):
                found = self.note(answer)
                self.assertEqual((found['assessments'], found['encounters']), (None, None))
                self.assertTrue(found['note'].startswith('the assessments made from event inventories were not '
                                                         'counted ('), found['note'])

    def test_an_interrupt_is_never_swallowed(self):
        with self.assertRaises(KeyboardInterrupt):
            self.note(KeyboardInterrupt())


class RollbackNoteTests(TemporaryDirectoryTest):
    """Each rollback-app arm that hands the rows to an older pair declares the note in its receipt and goes on."""

    def test_the_keep_layout_switches_back_and_declares_the_note(self):
        world = keep_world(self.tmp)
        world.interpretation_answer = {'interpretation': {'assessments': 3, 'encounters': ['e1', 'e2']}}
        details, failure = run_rollback_app(world)
        self.assertIsNone(failure, failure and str(failure))
        self.assertEqual(world.violations, [])
        self.assertEqual(details['outcome'], 'switched')
        self.assertEqual(details['interpretation'], {'assessments': 3, 'encounters': ['e1', 'e2'], 'note': NOTE_3})
        self.assertTrue(details['summary'].endswith('; ' + NOTE_3), details['summary'])
        # read in this revision's image, once its worker is stopped, before the switch back
        read = world.events.index(('interpretation', IMAGE))
        self.assertLess(world.events.index(('close', IMAGE, tuple(KINDS_OLD))), read)
        self.assertLess(read, world.events.index(('reload', 9150)))

    def test_the_back_layout_finishes_the_way_back_and_declares_the_note(self):
        world = halfway_world(self.tmp)
        world.interpretation_answer = {'interpretation': {'assessments': 3, 'encounters': ['e1', 'e2']}}
        mark = len(world.events)
        details, failure = run_rollback_app(world)
        self.assertIsNone(failure, failure and str(failure))
        self.assertEqual(details['interpretation']['note'], NOTE_3)
        self.assertTrue(details['summary'].endswith('; ' + NOTE_3))
        events = world.events[mark:]
        self.assertLess(events.index(('health', 9150, OLD)), events.index(('interpretation', IMAGE)))

    def test_a_note_that_cannot_be_read_does_not_stop_the_rollback(self):
        world = keep_world(self.tmp)
        world.interpretation_answer = install.InstallError('Counting the assessments failed (exit 1).')
        details, failure = run_rollback_app(world)
        self.assertIsNone(failure, failure and str(failure))
        self.assertEqual(details['outcome'], 'switched')
        self.assertIsNone(details['interpretation']['assessments'])
        self.assertIn('were not counted (Counting the assessments failed (exit 1).)', details['interpretation']['note'])


# --- verify: the D22 one-shot (ADJUDICATION P-7) ----------------------------------------------------------------------

S4 = '2026-11-09T10:00:05.123Z'


def self_test(failing=(), names=install.INTERPRETATION_SELF_TEST):
    checks = [{'name': name, 'ok': name not in failing, 'detail': f'synthetic detail of {name}'} for name in names]
    return {'passed': all(check['ok'] for check in checks), 'checks': checks}


def d22_report(since=S4, held=False):
    standing = [{'id': 'h1', 'reason': 'quota', 'means': 'a quota or billing limit'}] if held else []
    return {'window': {'since': since.replace('Z', '+00:00'), 'until': '2026-11-09T11:00:00+00:00'},
            'interpreter': {'process_mode': 'disabled', 'model': 'gemini-4-argon'},
            'assessments': {'new_path': 2, 'legacy_engine': 0},
            'hold': {'held': held, 'standing': standing, 'process_mode': 'disabled', 'set': {}, 'released': []}}


def answered(report=None, test=None, *, code=0, stdout=None):
    body = json.dumps({'report': report or d22_report(), 'self_test': test or self_test()}, indent=2).encode() + b'\n'
    return SimpleNamespace(returncode=code, stdout=body if stdout is None else stdout,
                           stderr=b'CommandError: The interpretation self-test failed: x.\n' if code else b'')


def worker_container(mode='live', key=None):
    env = ['CPT_STUDIO_SECRET_KEY=synthetic-never-read', 'CPT_STUDIO_PROVIDER_MODE=disabled']
    if mode is not None:
        env.append(f'CPT_STUDIO_GEMINI_MODE={mode}')
    holds = mode == 'live' if key is None else key
    mounts = ([{'Type': 'bind', 'Source': GEMINI['target'], 'Destination': GEMINI['mounted'], 'RW': False}] if holds
              else [])
    return {**container_on(None, role='worker'), 'Config': {**container_on(None, role='worker')['Config'], 'Env': env},
            'Mounts': mounts}


class VerifyInterpretationTests(TemporaryDirectoryTest):
    """The REAL phase_verify, its host read as test_install_bluegreen's verify reads it, with an app receipt naming the
    interpreter's mode and the new worker's start, and its D22 one-shot answering ``answer``."""

    def receipt(self, phase, details=None):
        install.write_receipt(self.tmp, phase, {'phase': phase, 'ok': True, 'revision': REVISION,
                                                'details': details or {}})

    def verify(self, *, worker=None, answer=None, interpreter=('live', S4), app=True):
        files = {'available': {'quillmd': install.QUILLMD_VHOST_SHA256, install.VHOST_NAME: '1' * 64},
                 'enabled': {'quillmd': 'quillmd', install.VHOST_NAME: install.VHOST_LINK_TARGET},
                 'nginx_conf_sha256': '2' * 64, 'conf_d': {}}
        self.receipt('preflight', {'nginx_files': files, 'routing': {}, 'app_health': {'status': 200},
                                   'cotenants': {'ok': True}, 'containers': {}, 'volumes': ['v'],
                                   'letsencrypt': {'renewal': {}, 'live': {}}})
        if app:
            mode, start = interpreter
            self.receipt('app', {'interpreter': {'mode': mode, 'credentials_loaded': mode == 'live',
                                                 'worker_started_at': start}})
        vhost = rendered(9151)['https']
        current = {**files, 'available': {**files['available'], install.VHOST_NAME: sha(vhost)}}
        running = {WEB: container_on(9151), WORKER: worker if worker is not None else worker_container(),
                   install.DB_CONTAINER: {'State': {'Running': True}, 'Id': 'db'}}
        self.oneshots = []

        def oneshot(image_id, command, env_bytes, **kwargs):
            self.oneshots.append((image_id, command, env_bytes, kwargs))
            return answer if answer is not None else answered()
        with mock.patch.object(install, 'rendered_vhosts', side_effect=lambda revision, port=9150: rendered(port)), \
                mock.patch.object(install, 'installed_image', return_value=IMAGE), \
                mock.patch.object(install, 'nginx_file_state', return_value=current), \
                mock.patch.object(install, 'live_vhost_bytes', return_value=vhost.encode()), \
                mock.patch.object(install, 'ingress_checks', return_value=[]), \
                mock.patch.object(install, 'cotenant_check', return_value={'ok': True}), \
                mock.patch.object(install, 'containers', return_value={}), \
                mock.patch.object(install, 'volumes', return_value=['v']), \
                mock.patch.object(install, 'le_state', return_value={'renewal': {}, 'live': {}}), \
                mock.patch.object(install, 'inspect', side_effect=lambda kind, name: running.get(name) or (
                    {} if kind == 'image' else None)), \
                mock.patch.object(install, 'db_container_problems', return_value=[]), \
                mock.patch.object(install, 'service_problems', return_value=[]), \
                mock.patch.object(install, 'https_checks', return_value=([], {})), \
                mock.patch.object(install, 'foreign_uid_tasks', return_value=0), \
                mock.patch.object(install, 'own_service_ids', return_value=[]), \
                mock.patch.object(install, 'read_protected_env', return_value=b'CPT_STUDIO_SECRET_KEY=synthetic\n'), \
                mock.patch.object(install, 'oneshot', oneshot):
            try:
                return install.phase_verify(install.Context(SimpleNamespace(phase='verify', revision=REVISION,
                                                                            receipts=str(self.tmp)), self.tmp)), None
            except install.InstallError as error:
                return None, error

    def test_the_one_shot_reads_the_window_from_the_new_workers_start_and_passes(self):
        details, error = self.verify()
        self.assertIsNone(error, error and str(error))
        (image_id, command, env, kwargs), = self.oneshots
        self.assertEqual(image_id, IMAGE)
        self.assertEqual(command, ['manage', 'interpretation_report', '--since', S4, '--self-test', '--json'])
        self.assertEqual(env, b'CPT_STUDIO_SECRET_KEY=synthetic\n')
        self.assertEqual(kwargs, {'timeout': install.INTERPRETATION_REPORT_SECONDS})  # the interpreter disabled,
        # no file and no other network than the database's: a one-shot as every other
        evidence = details['interpretation']
        self.assertEqual((evidence['worker_mode'], evidence['app_mode'], evidence['since'], evidence['exit']),
                         ('live', 'live', S4, 0))
        self.assertTrue(evidence['worker_holds_key'])
        self.assertEqual(evidence['self_test'], self_test())
        self.assertEqual(evidence['report']['interpreter']['model'], 'gemini-4-argon')
        self.assertTrue(Path(evidence['log']).is_file())
        self.assertIn('interpreter live: self-test passed (9 of 9 checks run) since the new worker started '
                      f'({S4}); interpreter hold none standing', details['summary'])
        self.assertNotIn('synthetic-never-read', json.dumps(details))  # nothing of the worker's env but its mode

    def test_a_standing_hold_is_reported_never_judged(self):
        details, error = self.verify(answer=answered(d22_report(held=True)))
        self.assertIsNone(error, error and str(error))
        self.assertIn('interpreter hold standing (quota)', details['summary'])

    def test_a_failed_or_missing_check_or_a_report_that_is_not_one_fails_verify(self):
        cases = {
            'a failed check': (answered(test=self_test(failing=('no legacy-engine assessment',)), code=1),
                               'the interpretation self-test failed: no legacy-engine assessment (synthetic detail'),
            'a check that did not run': (answered(test=self_test(names=install.INTERPRETATION_SELF_TEST[:-1])),
                                         'the interpretation self-test did not run: no legacy-engine assessment'),
            'no check at all': (answered(test={'passed': True, 'checks': []}), 'did not run: sentinel installed'),
            'passed not said': (answered(test={**self_test(), 'passed': None}), 'did not say it passed'),
            'an exit with every check passing': (answered(code=1), 'the interpretation report exited 1'),
            'not JSON': (answered(stdout=b'Traceback (most recent call last):\n', code=1),
                         'did not answer its JSON report and self-test (exit 1)'),
            'too much': (answered(stdout=b' ' * (install.INTERPRETATION_REPORT_LIMIT + 1)),
                         'did not answer its JSON report and self-test (exit 0)'),
            'another window': (answered(d22_report(since='2026-11-09T09:00:00Z')),
                               'the interpretation report read from 2026-11-09T09:00:00+00:00, not from the new '
                               "worker's start"),
        }
        for label, (answer, words) in cases.items():
            with self.subTest(label):
                details, error = self.verify(answer=answer)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn(words, str(error))
                self.assertIn('interpretation', error.details)

    def test_the_workers_mode_must_be_the_one_the_app_phase_installed_and_hold_its_key_alone(self):
        cases = {
            'another mode': (dict(worker=worker_container('disabled')),
                             "the worker's interpreter mode is disabled, but the app phase installed live"),
            'no mode named': (dict(worker=worker_container(None, key=True)),
                              "the worker's interpreter mode is not named, but the app phase installed live"),
            'live without its key': (dict(worker=worker_container('live', key=False)),
                                     "the live interpreter's worker does not hold /etc/cpt-studio/gemini.env"),
            'its key, not live': (dict(worker=worker_container('disabled', key=True),
                                       interpreter=('disabled', S4)),
                                  'the worker holds /etc/cpt-studio/gemini.env, but its interpreter is not live'),
            'no new-worker start': (dict(interpreter=('live', None)), "the app receipt names no new worker's start"),
        }
        for label, (arguments, words) in cases.items():
            with self.subTest(label):
                for path in self.tmp.glob('*.json'):
                    path.unlink()
                details, error = self.verify(**arguments)
                self.assertIsInstance(error, install.InstallError)
                self.assertIn(words, str(error))
        # a disabled interpreter installed disabled passes: verify judges the install it was given, never the mode
        for path in self.tmp.glob('*.json'):
            path.unlink()
        details, error = self.verify(worker=worker_container('disabled'), interpreter=('disabled', S4))
        self.assertIsNone(error, error and str(error))
        self.assertIn('interpreter disabled: self-test passed', details['summary'])

    def test_without_an_app_receipt_a_worker_that_names_a_mode_fails_and_one_that_names_none_is_not_read(self):
        details, error = self.verify(app=False)
        self.assertIsInstance(error, install.InstallError)
        self.assertIn("no successful app receipt of this revision names its new worker's start", str(error))
        self.assertEqual(self.oneshots, [])
        for path in self.tmp.glob('*.json'):
            path.unlink()
        details, error = self.verify(app=False, worker=worker_container(None, key=True))  # it holds the key: judged
        self.assertIsInstance(error, install.InstallError)
        self.assertIn("no successful app receipt of this revision names its new worker's start", str(error))
        for path in self.tmp.glob('*.json'):
            path.unlink()
        details, error = self.verify(app=False, worker=worker_container(None, key=False))
        self.assertIsNone(error, error and str(error))
        self.assertEqual(self.oneshots, [])
        self.assertEqual(details['interpretation']['self_test'], 'not run')
        self.assertIn('interpretation self-test not run: the worker names no interpreter mode', details['summary'])

    def test_the_newest_app_receipt_names_the_window(self):
        # an app phase run again (a same-revision re-run) started a newer worker: its start is the window's
        self.receipt('app', {'interpreter': {'mode': 'live', 'credentials_loaded': True,
                                             'worker_started_at': '2026-11-08T08:00:00.000Z'}})
        later = '2026-11-09T12:00:00.000Z'
        details, error = self.verify(answer=answered(d22_report(since=later)), interpreter=('live', later))
        self.assertIsNone(error, error and str(error))
        self.assertEqual(self.oneshots[0][1][3], later)
        self.assertEqual(details['interpretation']['since'], later)


# --- the swap of a fresh host: the new worker's start is recorded (ADJUDICATION P-7) ----------------------------------

class SwapWorkerStartTests(TemporaryDirectoryTest):
    def test_the_worker_start_is_taken_after_the_web_and_before_the_worker_is_run(self):
        names = {'cpt-studio-web': 'web', 'cpt-studio-worker': 'worker'}
        live = {name: {'Id': f'old-{role}', 'Image': 'old', 'State': {'Running': True},
                       'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role}}}
                for name, role in names.items()}
        runs, moments = [], []

        def fake_docker(*args, **kwargs):
            if args[0] == 'rename':
                live[args[2]] = live.pop(args[1])
            elif args[0] == 'run':
                runs.append(list(args))
                moments.append(install.utc_now_ms())
                role = names[args[args.index('--name') + 1]]
                live[args[args.index('--name') + 1]] = {
                    'Id': f'new-{role}', 'Image': IMAGE, 'State': {'Running': True},
                    'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role}}}
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        ctx = install.Context(SimpleNamespace(phase='app', revision=REVISION), self.tmp)
        with mock.patch.object(install, 'inspect', side_effect=lambda kind, name: live.get(name)), \
                mock.patch.object(install, 'docker', fake_docker), \
                mock.patch.object(install, 'wait_service', return_value={'id': 'new'}):
            result = install.swap_services(ctx, IMAGE, b'', 'disabled', RULING, interpreter='live')
        web, worker = runs
        self.assertNotIn(GEMINI_MOUNT, flags(web, '--mount'))
        self.assertIn(GEMINI_MOUNT, flags(worker, '--mount'))
        started = install.utc_moment(result['worker_started_at'])
        self.assertLessEqual(install.utc_moment(moments[0]), started)
        self.assertLessEqual(started, install.utc_moment(moments[1]))


# --- the in-image scripts on a real database --------------------------------------------------------------------------

class InterpretationOnTheDatabaseTests(DatabaseTest):
    """INTERPRETATION_MADE, UNDO_HAZARDS, CLOSE_STAGES and UNRUNNABLE_STAGES on real rows: the assessments made from
    event inventories are counted and named and never a hazard (P-1), and an interpret stage is closed by every undo
    whose next worker does not run it, its Gemini run settled as any other's, and refused by a worker that cannot run
    it."""

    NOTE = 'Closed by the installer: undone (revision aaaaaaaaaaaa), so this stage will not run.'

    def gemini_run(self, encounter, state='succeeded', exchange=None):
        from django.utils import timezone
        from studio import models
        run = models.ProviderRun.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider='gemini',
            adapter_version='gemini-generate@cptstudio-1', purpose='interpretation', request_sha256='e' * 64,
            request_body={}, contexts=[], state=state, endpoint='https://generativelanguage.googleapis.com/synthetic',
            started_at=timezone.now())
        if exchange is not None:
            models.ProviderExchange.objects.create(run=run, turn=1, request_body={}, request_sha256='f' * 64,
                                                   state=exchange, http_status=200 if exchange == 'succeeded' else None)
        return run

    def assessment(self, encounter, *, engine_version, inventory=False):
        """A context, a routing stand-in and an assessment of ``encounter``'s revision (new-path rows when asked), made
        current. Synthetic."""
        from studio import models
        revision = encounter.current_revision
        made = None
        if inventory:
            made = models.EventInventory.objects.create(
                encounter=encounter, revision=revision, provider_run=self.gemini_run(encounter),
                interpretation_version='gemini-events@1', inventory_version='gemini-inventory@1',
                text_sha256='a' * 64, request_sha256='e' * 64, response_sha256='b' * 64, state='read',
                events={'passages': [], 'lesions': [], 'events': [], 'relations': []}, encounter_facts={},
                open_questions=[], verification={}, sha256='c' * 64)
        context = models.EncounterContext.objects.create(
            encounter=encounter, revision=revision, facts={}, sha256='d' * 64, event_inventory=made,
            version='gemini-context@1' if inventory else 'gi-context@5')
        routing = models.RoutingRun.objects.create(revision=revision, version='synthetic', result={}, sha256='0' * 64)
        assessment = models.Assessment.objects.create(
            encounter=encounter, revision=revision, context=context, routing=routing, profiles_version='synthetic@1',
            engine_version=engine_version, sha256='1' * 64, event_inventory=made)
        models.Encounter.objects.filter(pk=encounter.pk).update(current_context=context, current_assessment=assessment)
        return assessment

    def job(self, encounter, kind, state, *, tag=''):
        from django.utils import timezone
        from studio import models
        return models.Job.objects.create(
            encounter=encounter, revision=encounter.current_revision, kind=kind, state=state,
            idempotency_key=f'{kind}:{encounter.pk}:{state}{tag}', deadline_at=timezone.now() + dt.timedelta(minutes=9),
            started_at=timezone.now() - dt.timedelta(seconds=5) if state == models.Job.RUNNING else None)

    def test_the_count_names_exactly_the_encounters_with_a_new_path_assessment_and_none_is_a_hazard(self):
        events = self.encounter('events')
        self.assessment(events, engine_version='cpt-studio-events@1', inventory=True)
        self.assessment(events, engine_version='cpt-studio-events@1', inventory=True)
        later = self.encounter('later-version')  # a later events version is still a new-path assessment
        self.assessment(later, engine_version='cpt-studio-events@2')
        legacy = self.encounter('legacy')
        self.assessment(legacy, engine_version='cpt-studio-validation@10')
        answer = run_in_image(install.INTERPRETATION_MADE, {})
        self.assertEqual(answer, {'interpretation': {'assessments': 3,
                                                     'encounters': sorted([str(events.pk), str(later.pk)])}})
        # P-1: none of them is a reason to refuse an undo
        self.assertEqual(run_in_image(install.UNDO_HAZARDS_READ, {}), {'hazards': {}})
        from django.utils import timezone
        closed = run_in_image(install.CLOSE_STAGES, {'since': timezone.now().isoformat(), 'note': self.NOTE,
                                                     'kinds': list(install.COMMON_STAGE_KINDS)})
        self.assertEqual(closed['hazards'], {})
        self.assertNotIn('interpretation', closed)  # the close's answer is as it was (the note is read apart)
        # through the installer's own reader, as switch-back and rollback-app read it
        def in_this_image(image, env, body, params, **kwargs):
            return run_in_image(body, params)
        with mock.patch.object(install, 'app_script', in_this_image):
            note = install.interpretation_note(IMAGE, b'', REVISION)
        self.assertEqual(note['note'], '3 assessments were made from event inventories; the earlier image reads them '
                                       'fail-closed')
        self.assertEqual(note['encounters'], sorted([str(events.pk), str(later.pk)]))

    def test_an_interpret_stage_is_closed_by_an_undo_whose_next_worker_does_not_run_it(self):
        from django.utils import timezone
        from studio import models
        queued, running, stopped = (self.encounter(tag) for tag in ('queued', 'running', 'stopped'))
        self.job(queued, 'interpret', models.Job.QUEUED)
        self.job(running, 'interpret', models.Job.RUNNING)
        sending = self.gemini_run(running, state='sending', exchange='succeeded')  # the answer reached CPT Studio
        self.job(stopped, 'interpret', models.Job.CANCELLED)  # paused or stopped: its encounter's latest stage
        since = timezone.now()  # everything above was made before: only the kinds decide what is closed
        kept = sorted([*install.COMMON_STAGE_KINDS, 'interpret', 'review2'])
        answer = run_in_image(install.CLOSE_STAGES, {'since': since.isoformat(), 'note': self.NOTE, 'kinds': kept})
        self.assertEqual((answer['closed'], answer['kinds']), (0, []))  # a next worker that runs it keeps them all
        for kinds in (list(install.COMMON_STAGE_KINDS), sorted(KINDS_OLD)):
            with self.subTest(kinds=kinds):
                answer = run_in_image(install.CLOSE_STAGES, {'since': since.isoformat(), 'note': self.NOTE,
                                                             'kinds': kinds})
                if kinds == list(install.COMMON_STAGE_KINDS):
                    self.assertEqual((answer['closed'], answer['kinds'], answer['encounters']), (3, ['interpret'], 3))
                    self.assertEqual(answer['runs_unknown'], 1)
                else:
                    self.assertEqual(answer['closed'], 0)  # already closed by the first
        states = {job.encounter_id: (job.state, job.error) for job in models.Job.objects.filter(kind='interpret')}
        self.assertEqual(set(states.values()), {(models.Job.FAILED, self.NOTE)})
        sending.refresh_from_db()
        self.assertEqual((sending.state, sending.sent), (models.ProviderRun.UNKNOWN, True))  # may have reached Google

    def test_a_worker_that_cannot_run_interpret_counts_it_stuck_and_one_that_can_does_not(self):
        from studio import jobs, models
        encounter = self.encounter('stuck')
        self.job(encounter, 'interpret', models.Job.QUEUED)
        without = {kind: stage for kind, stage in jobs.STAGES.items() if kind != 'interpret'}
        with mock.patch.object(jobs, 'STAGES', without):  # the installed c2e53f8e-era worker: no interpret stage
            answer = run_in_image(install.UNRUNNABLE_STAGES, {})
        self.assertEqual((answer['stuck'], answer['kinds']), (1, ['interpret']))
        self.assertNotIn('interpret', answer['known'])
        with mock.patch.object(jobs, 'STAGES', {**without, 'interpret': object()}):  # this revision's worker
            answer = run_in_image(install.UNRUNNABLE_STAGES, {})
        self.assertEqual((answer['stuck'], answer['kinds']), (0, []))
        self.assertIn('interpret', answer['known'])

    def test_the_installers_reader_takes_the_report_commands_own_json(self):
        # the contract between verify and `manage interpretation_report`: its real --self-test --json output, read by
        # interpretation_evidence, passes exactly when the command says its self-test passed (whatever this test
        # process's sentinel finds), and names every check verify requires
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from studio.interpretation import sentinel
        self.addCleanup(sentinel.uninstall)
        since = '2026-01-01T00:00:00Z'
        out, code = io.StringIO(), 0
        try:
            call_command('interpretation_report', '--since', since, '--self-test', '--json', stdout=out)
        except CommandError:
            code = 1
        printed = json.loads(out.getvalue())
        self.assertEqual([check['name'] for check in printed['self_test']['checks']],
                         list(install.INTERPRETATION_SELF_TEST))
        install.write_receipt(self.tmp_dir(), 'app', {'phase': 'app', 'ok': True, 'revision': REVISION, 'details': {
            'interpreter': {'mode': 'live', 'credentials_loaded': True, 'worker_started_at': since}}})
        ctx = SimpleNamespace(receipts=self.tmp_dir(), revision=REVISION, log=lambda label, data: 'log')
        answer = SimpleNamespace(returncode=code, stdout=out.getvalue().encode(), stderr=b'')
        with mock.patch.object(install, 'oneshot', return_value=answer), \
                mock.patch.object(install, 'read_protected_env', return_value=b''):
            evidence, problems = install.interpretation_evidence(ctx, IMAGE, worker_container('live'))
        self.assertEqual(problems == [], printed['self_test']['passed'] is True, problems)
        self.assertEqual(evidence['self_test'], printed['self_test'])

    def tmp_dir(self):
        if not hasattr(self, '_receipts'):
            import tempfile
            holder = tempfile.TemporaryDirectory()
            self.addCleanup(holder.cleanup)
            self._receipts = Path(holder.name)
        return self._receipts


if __name__ == '__main__':
    unittest.main()
