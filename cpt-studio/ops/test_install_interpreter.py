"""Unit tests for the Gemini migration's installer additions (ops/install.py; design/FINAL.md 13, DECISIONS D14 and D22,
design/ADJUDICATION.md P-1 and P-7): the interpreter's credential spec and its unread copy, the worker-only bind,
--interpreter-mode, the offline loader check, the note switch-back and rollback-app declare and never refuse on, and the
interpret stage on an undo. No Docker, sudo, nginx or network.

The Fable coding build (DECISIONS D351-D353) removed verify's D22 one-shot, the access check and the interpreter's place
in the app phase and the secrets phase: their tests went with them, and the coder's own are ops/test_install_coding.py.
What stays here is what a switch-back to an earlier revision's pair still uses - --interpreter-mode and its worker-only
bind - and the undo machinery's reads.

AMENDMENT-2 (docs/gemini-migration/AMENDMENT-2.md, adopted by DECISIONS D279: the interpreter is Claude Fable 5.2,
D275; step F8): the interpreter's credential is the Fable participant's file - 1.11's installer table, copied once, bound
once in the worker, and the earlier interpreter's key copy only reported; verify clean with that participant live and
the interpreter disabled or in replay [R:replay-R3]; the access check that waits out a reading in flight
[R:cost-F-COST-8]; the version-naming reads accepting AMENDMENT-2's rows (8.5).

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
from test_install import (TemporaryDirectoryTest, earlier_files, earlier_literal, earlier_text,  # noqa: E402
                          guard_host, release_host, run_body)
from test_install_harness import ANTHROPIC_FILE, ANTHROPIC_VALUE, GEMINI_FILE, IMAGE, REVISION, RULING, flags  # noqa: E402
from test_install_bluegreen import KINDS_OLD  # noqa: E402


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


APP_ROOT = Path(__file__).resolve().parents[1]
# AMENDMENT-2 1.11: the interpreter's credential is the Fable participant's file, one bind target
KEY = install.INTERPRETER
FABLE = install.PARTICIPANTS['fable']
KEY_MOUNT = f'type=bind,src={KEY["target"]},dst={KEY["mounted"]},readonly'
# 1.11's installer table, as AMENDMENT-2 writes it (ETC_DIR and PROVIDER_SOURCES spelled out)
TABLE_1_11 = {'name': 'anthropic', 'source': '/etc/cpt-studio-provider-sources/anthropic.env',
              'target': '/etc/cpt-studio/anthropic-credentials.env',
              'mounted': '/run/cpt-studio/anthropic-credentials.env', 'file_env': 'CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE',
              'mode_env': 'CPT_STUDIO_GEMINI_MODE', 'replay_env': 'CPT_STUDIO_GEMINI_REPLAY_DIR',
              'replay_dir': '/app/tests/fixtures/interpretation', 'module': 'studio.interpretation.fable_adapter',
              'loader': 'load_anthropic_credentials', 'setting': 'ANTHROPIC_CREDENTIALS_FILE',
              'required': ('ANTHROPIC_API_KEY',), 'optional': ('ANTHROPIC_WORKSPACE_ID',)}
def env_of(argv) -> dict:
    return dict(item.split('=', 1) for item in flags(argv, '-e'))


# --- the spec: what the installer names is what the earlier revision's application reads ---------------------------------
# The interpreter exists only in the pair a switch-back returns to (the Fable coding build removed it from this tree), so
# its names are held to the earlier revision's files, read from git (test_install.earlier_text: skipped in a clone
# without that commit).

class InterpreterSpecTests(unittest.TestCase):
    def test_the_credential_is_the_fable_participants_file_as_1_11s_table_names_it(self):
        # AMENDMENT-2 1.11 (DECISIONS D275: CPT Studio's existing Anthropic credential): the installer's table, exactly
        self.assertEqual(KEY, TABLE_1_11)
        self.assertEqual(KEY['source'], f'{install.PROVIDER_SOURCES}/anthropic.env')
        self.assertEqual(KEY['target'], f'{install.ETC_DIR}/anthropic-credentials.env')
        # the same source, target and mount as the Fable participant's, its loader and its key names: one file
        self.assertEqual(install.INTERPRETER_SHARES, 'fable')
        for field in ('source', 'target', 'mounted', 'file_env', 'loader', 'setting', 'required', 'optional'):
            with self.subTest(field=field):
                self.assertEqual(KEY[field], FABLE[field])
        self.assertEqual(install.interpreter_mount(), install.participant_mount('fable'))
        # still its own mode and no participant mode or access check of its own
        self.assertNotIn(KEY['name'], install.PARTICIPANTS)
        self.assertNotEqual(KEY['mode_env'], FABLE['mode_env'])
        self.assertEqual(install.credentials_target(KEY['name']), FABLE['target'])
        self.assertEqual(install.credentials_target('corti'), install.CORTI_TARGET)
        self.assertEqual(install.credentials_target('astra'), install.PARTICIPANTS['astra']['target'])
        # the earlier interpreter's own key copy is named only to be reported; no spec copies or mounts it
        self.assertEqual(install.LEGACY_INTERPRETER_COPY, '/etc/cpt-studio/gemini.env')
        specs = [KEY, *install.PARTICIPANTS.values()]
        self.assertNotIn(install.LEGACY_INTERPRETER_COPY, {spec['target'] for spec in specs})
        self.assertFalse([spec for spec in specs if 'gemini' in spec['source'] or 'gemini' in spec['mounted']])
        self.assertEqual(len(GEMINI_FILE), 69)  # the legacy copy's synthetic stand-in has the shape D14 records

    def test_the_names_the_installer_sets_are_the_ones_settings_and_the_adapter_read(self):
        source = earlier_text('cptstudio/settings.py')
        for variable, setting, default in ((KEY['mode_env'], 'GEMINI_MODE', 'disabled'),
                                           (KEY['file_env'], 'ANTHROPIC_CREDENTIALS_FILE', ''),
                                           (KEY['replay_env'], 'GEMINI_REPLAY_DIR', '')):
            with self.subTest(variable):
                self.assertEqual(variable, f'CPT_STUDIO_{setting}')  # settings._env prefixes CPT_STUDIO_
                self.assertIn(f"{setting} = _env('{setting}', '{default}')", source)
        self.assertEqual(KEY['setting'], 'ANTHROPIC_CREDENTIALS_FILE')
        # every mode the installer offers is one settings accepts at import (anything else fails there)
        self.assertIn("if GEMINI_MODE not in {'disabled', 'replay', 'live'}:", source)
        self.assertEqual(set(install.INTERPRETER_MODES), {'disabled', 'replay', 'live'})
        # the Fable interpreter reads exactly these at call time: its mode, its credential live, its folder in replay
        adapter = earlier_text('studio/interpretation/fable_adapter.py')
        for read in ('mode = settings.GEMINI_MODE if mode is None else mode',
                     'return FableInterpreter(settings.ANTHROPIC_CREDENTIALS_FILE,',
                     'replay = ReplayInterpreterF(settings.GEMINI_REPLAY_DIR, **limits)'):
            self.assertIn(read, adapter)

    def test_the_loader_check_calls_the_loader_the_adapter_reads_the_key_with(self):
        body = install.INTERPRETER_CREDENTIALS_CHECK
        compile(body, 'interpreter-credentials-check', 'exec')
        self.assertEqual(body, 'from django.conf import settings\n'
                               'from studio.interpretation.fable_adapter import load_anthropic_credentials\n'
                               'load_anthropic_credentials(settings.ANTHROPIC_CREDENTIALS_FILE)\n'
                               "print('anthropic-credentials-parse-ok')\n")
        tree = ast.parse(earlier_text('studio/interpretation/fable_adapter.py'))
        imported = {(node.module, alias.name) for node in tree.body if isinstance(node, ast.ImportFrom)
                    for alias in node.names}
        self.assertIn(('studio.participants.credentials', 'load_anthropic_credentials'), imported)
        # the loader's key names are the spec's: one required, one optional, nothing else
        keys = earlier_literal('studio/participants/credentials.py', 'ANTHROPIC_KEYS')
        self.assertEqual(keys, (*KEY['required'], *KEY['optional']))

    def test_replay_reads_the_recordings_the_earlier_image_ships(self):
        # that image is the earlier revision's cpt-studio/ copied to /app (WORKDIR /app; COPY . .), and its
        # .dockerignore keeps tests/ in it
        dockerfile = earlier_text('deploy/Dockerfile')
        self.assertIn('WORKDIR /app', dockerfile)
        self.assertIn('COPY . .', dockerfile)
        ignored = [line.strip() for line in earlier_text('deploy/.dockerignore').splitlines()
                   if line.strip() and not line.startswith('#')]
        self.assertFalse([pattern for pattern in ignored
                          if pattern.rstrip('/') == 'tests' or pattern.startswith('tests/') or 'fixtures' in pattern])
        relative = PurePosixPath(KEY['replay_dir']).relative_to('/app')
        self.assertEqual(str(relative), 'tests/fixtures/interpretation')
        self.assertTrue(earlier_files(str(relative)))
        # AMENDMENT-2 1.8: every replay interpreter reads <dir>/<its recording_folder>/<request sha256><its suffix>, and
        # Fable's folder is its provider 'anthropic', its suffix '.sse' (Gemini's stay <dir>/gemini/<sha>.json)
        replay = earlier_text('studio/interpretation/replay.py')
        self.assertIn('folder = self.replay_dir / self.recording_folder', replay)
        self.assertIn('class ReplayInterpreterF(_Recordings, fable_adapter.InterpreterF):', replay)
        adapter = earlier_text('studio/interpretation/fable_adapter.py')
        self.assertIn("    recording_folder = NAME\n    recording_suffix = '.sse'\n", adapter)
        self.assertIn('NAME = interpretation.PROVIDER_V3', adapter)
        self.assertEqual(earlier_literal('studio/interpretation/__init__.py', 'PROVIDER_V3'), 'anthropic')

    def test_the_interpret_stage_is_not_a_kind_every_worker_runs(self):
        kind = earlier_literal('studio/interpretation/__init__.py', 'JOB_KIND')
        self.assertEqual(kind, 'interpret')
        self.assertNotIn(kind, install.COMMON_STAGE_KINDS)
        self.assertNotIn(kind, KINDS_OLD)  # the installed c2e53f8e-era worker's kinds, as the fake host's old image
        # with no next worker to ask, an undo keeps only the common kinds: every interpret stage is closed
        self.assertEqual(install.stage_kinds_of(None, b''), list(install.COMMON_STAGE_KINDS))
        self.assertIn('Job.objects.exclude(kind__in=kept)', install.CLOSE_STAGES)
        self.assertIn('Job.objects.exclude(kind__in=known)', install.UNRUNNABLE_STAGES)

    def test_an_assessment_made_from_an_inventory_is_no_hazard_of_either_kind(self):
        # ADJUDICATION P-1 (FINAL 13): never a refusing reason. The Fable coding build reads no inventory at all: its
        # hazards name only its own unknown coding runs, and its declared note says what it coded (CODING_MADE)
        self.assertNotIn('interpretation', install.SHOWN_HAZARDS)
        self.assertNotIn("add('interpretation')", install.UNDO_HAZARDS)
        self.assertNotIn('event_inventory', install.UNDO_HAZARDS + install.CLOSE_STAGES + install.CODING_MADE)
        self.assertFalse(hasattr(install, 'INTERPRETATION_MADE'))


# --- docker arguments: the worker alone holds the key, bound once ----------------------------------------------------

class InterpreterServiceArgumentTests(unittest.TestCase):
    def test_only_a_live_interpreters_worker_mounts_the_key_and_the_web_gets_the_path_and_no_file(self):
        worker = install.service_args('worker', IMAGE, REVISION, 'disabled', RULING, interpreter='live')
        web = install.service_args('web', IMAGE, REVISION, 'disabled', RULING, interpreter='live')
        self.assertIn(KEY_MOUNT, flags(worker, '--mount'))
        self.assertEqual(flags(web, '--mount'), [f'type=volume,src={install.FILES_VOLUME},dst={install.STATE_DIR}'])
        for argv in (worker, web):
            env = env_of(argv)
            self.assertEqual((env['CPT_STUDIO_GEMINI_MODE'], env['CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE']),
                             ('live', KEY['mounted']))
            self.assertEqual(env['CPT_STUDIO_FABLE_MODE'], 'disabled')  # the participant stays as it was given
            self.assertNotIn('CPT_STUDIO_GEMINI_REPLAY_DIR', env)
            self.assertNotIn('CPT_STUDIO_GEMINI_CREDENTIALS_FILE', env)  # the Gemini key is named nowhere now
        self.assertEqual(flags(web, '-e'), flags(worker, '-e'))  # the web is named everything the worker is

    def test_the_shared_credential_is_bound_once_whichever_of_its_holders_is_live(self):
        # AMENDMENT-2 1.11: "The worker binds the file once when the Fable participant or the interpreter is live (one
        # bind target)" - Docker refuses a container naming one destination twice
        for fable in ('disabled', 'live'):
            for interpreter in ('disabled', 'replay', 'live'):
                worker = install.service_args('worker', IMAGE, REVISION, 'disabled', RULING, {'fable': fable},
                                              interpreter=interpreter)
                web = install.service_args('web', IMAGE, REVISION, 'disabled', RULING, {'fable': fable},
                                           interpreter=interpreter)
                held = 'live' in (fable, interpreter)
                with self.subTest(fable=fable, interpreter=interpreter):
                    mounts = flags(worker, '--mount')
                    self.assertEqual(mounts.count(KEY_MOUNT), 1 if held else 0)
                    self.assertEqual(len(mounts), len(set(mounts)))  # no destination named twice
                    self.assertEqual([m for m in mounts if KEY['mounted'] in m], [KEY_MOUNT] if held else [])
                    self.assertNotIn(KEY_MOUNT, flags(web, '--mount'))
                    file_flags = [item for item in flags(worker, '-e') if item.startswith(KEY['file_env'] + '=')]
                    self.assertEqual(file_flags, [f'{KEY["file_env"]}={KEY["mounted"]}'] if held else [])
                    self.assertEqual(flags(web, '-e'), flags(worker, '-e'))
        # beside Astra and Corti, both live, the order is the participants' then the interpreter's, each once
        worker = install.service_args('worker', IMAGE, REVISION, 'live', RULING, {'astra': 'live', 'fable': 'live'},
                                      interpreter='live')
        self.assertEqual(flags(worker, '--mount')[1:],
                         [f'type=bind,src={install.CORTI_TARGET},dst={install.CREDENTIALS_IN_CONTAINER},readonly',
                          install.participant_mount('astra'), KEY_MOUNT])
        self.assertEqual(install.worker_credential_mounts(['fable'], True), [KEY_MOUNT])
        self.assertEqual(install.worker_credential_mounts([], True), [KEY_MOUNT])
        self.assertEqual(install.worker_credential_mounts(['astra'], False), [install.participant_mount('astra')])

    def test_disabled_and_replay_mount_nothing_and_name_no_key(self):
        for mode in (None, 'disabled', 'replay'):
            for role in ('web', 'worker'):
                argv = install.service_args(role, IMAGE, REVISION, 'live', RULING, {'astra': 'live'},
                                            interpreter=mode)
                with self.subTest(mode=mode, role=role):
                    self.assertNotIn(KEY_MOUNT, flags(argv, '--mount'))
                    env = env_of(argv)
                    self.assertEqual(env['CPT_STUDIO_GEMINI_MODE'], mode or 'disabled')
                    self.assertNotIn('CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE', env)
                    self.assertEqual(env.get('CPT_STUDIO_GEMINI_REPLAY_DIR'),
                                     KEY['replay_dir'] if mode == 'replay' else None)
                    self.assertNotIn('anthropic-credentials.env', ' '.join(argv))
                    self.assertNotIn('gemini.env', ' '.join(argv))
        # the providers and participants are as they were beside it
        worker = install.service_args('worker', IMAGE, REVISION, 'live', RULING, {'astra': 'live'}, interpreter='live')
        mounts = flags(worker, '--mount')
        self.assertIn(f'type=bind,src={install.CORTI_TARGET},dst={install.CREDENTIALS_IN_CONTAINER},readonly', mounts)
        self.assertIn(install.participant_mount('astra'), mounts)
        self.assertEqual(mounts[-1], KEY_MOUNT)

    def test_an_unknown_mode_is_refused_rather_than_started(self):
        with self.assertRaises(install.InstallError):
            install.service_args('worker', IMAGE, REVISION, 'disabled', '', interpreter='LIVE')

    def test_one_shots_run_the_interpreter_disabled_and_the_loader_check_mounts_the_key_offline(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout=b'anthropic-credentials-parse-ok\n', stderr=b'')
        with mock.patch.object(install, 'run', fake_run), mock.patch.object(install, 'inspect', return_value=None):
            install.oneshot(IMAGE, ['migrate'], b'')
            install.oneshot(IMAGE, ['manage', 'shell', '-c', install.INTERPRETER_CREDENTIALS_CHECK], b'',
                            network='none', interpreter_file=True)
            install.oneshot(IMAGE, ['manage', 'shell', '-c', 'pass'], b'', network='none', interpreter_file=True,
                            participant_files=('fable',))  # both holders of the one file: one bind
        plain, checked, both = calls
        self.assertEqual(env_of(plain)['CPT_STUDIO_GEMINI_MODE'], 'disabled')
        self.assertNotIn('anthropic-credentials.env', ' '.join(plain))
        self.assertEqual(flags(checked, '--network'), ['none'])
        self.assertEqual(flags(checked, '--mount'), [KEY_MOUNT])
        env = env_of(checked)
        self.assertEqual((env['CPT_STUDIO_GEMINI_MODE'], env['CPT_STUDIO_ANTHROPIC_CREDENTIALS_FILE']),
                         ('disabled', KEY['mounted']))  # the file is read; the interpreter itself stays disabled
        self.assertEqual((env['CPT_STUDIO_PROVIDER_MODE'], env['CPT_STUDIO_FABLE_MODE']), ('disabled', 'disabled'))
        self.assertEqual(flags(both, '--mount'), [KEY_MOUNT])

    def test_no_secret_name_or_value_is_ever_an_argument(self):
        for role in ('web', 'worker'):
            joined = ' '.join(install.service_args(role, IMAGE, REVISION, 'live', RULING, {'astra': 'live',
                                                                                           'fable': 'live'},
                                                   interpreter='live'))
            for name in ('API_KEY', 'WORKSPACE_ID', 'SECRET_KEY', 'DB_PASSWORD', 'CLIENT_SECRET', ANTHROPIC_VALUE):
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
        key = self.bind(KEY['target'], KEY['mounted'])
        self.assertEqual(install.service_problems(self.container('worker', [volume, key]), 'worker', IMAGE), [])
        self.assertEqual(install.service_problems(self.container('web', [volume, key]), 'web', IMAGE),
                         ['the web holds a bind-mounted file (only the worker holds credentials)'])
        # the earlier interpreter's key copy is no credentials file a worker may hold now (AMENDMENT-2 1.11)
        for wrong in (self.bind(KEY['target'], KEY['mounted'], writable=True),
                      self.bind(KEY['target'], install.CREDENTIALS_IN_CONTAINER),
                      self.bind(KEY['source'], KEY['mounted']),
                      self.bind(install.LEGACY_INTERPRETER_COPY, '/run/cpt-studio/gemini.env')):
            with self.subTest(wrong=wrong):
                self.assertEqual(install.service_problems(self.container('worker', [volume, wrong]), 'worker', IMAGE),
                                 ['a bind mount other than a read-only credentials file'])


# --- the credential scan of the shared file -------------------------------------------------------------------------

class InterpreterCredentialScanTests(TemporaryDirectoryTest):
    def test_a_value_of_the_shared_file_is_found_and_only_its_key_name_comes_back(self):
        (self.tmp / KEY['name']).write_bytes(ANTHROPIC_FILE)
        seen = []

        def helper(body, params, *, mounts=(), sensitive=False, **kwargs):
            seen.append((list(mounts), sensitive))
            return run_body(body, params, {"'/scan/'": repr(str(self.tmp) + '/')})
        with mock.patch.object(install, 'run_helper', helper):
            self.assertTrue(install.credential_free([b'CredentialsError: ANTHROPIC_API_KEY is missing.'],
                                                    [KEY['name']]))
            self.assertFalse(install.credential_free([b'x-api-key: ' + ANTHROPIC_VALUE.encode()], [KEY['name']]))
        self.assertEqual(seen[0], ([f'type=bind,src={KEY["target"]},dst=/scan/anthropic,readonly'], True))


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
        self.assertNotIn(KEY_MOUNT, flags(web, '--mount'))
        self.assertIn(KEY_MOUNT, flags(worker, '--mount'))
        started = install.utc_moment(result['worker_started_at'])
        self.assertLessEqual(install.utc_moment(moments[0]), started)
        self.assertLessEqual(started, install.utc_moment(moments[1]))


if __name__ == '__main__':
    unittest.main()
