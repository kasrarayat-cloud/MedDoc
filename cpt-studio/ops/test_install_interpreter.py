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
from test_install import FakeOwnership, TemporaryDirectoryTest, guard_host, release_host, run_body  # noqa: E402
from test_install_harness import (ANTHROPIC_FILE, ANTHROPIC_VALUE, GEMINI_FILE, IMAGE, INSTALLED,  # noqa: E402
                                  REVISION, RULING, AppWorld, app_args, flags, settings_value)
from test_install import clean_v1_rows  # noqa: E402
from test_install_harness2 import DatabaseTest, module_constants, run_in_image  # noqa: E402
from test_install_bluegreen import KINDS_OLD, OLD, WEB, WORKER, container_on, rendered, sha  # noqa: E402
from test_install_r2 import run_rollback_app  # noqa: E402
from test_install_r3 import halfway_world, keep_world  # noqa: E402
from test_install_v2 import V2Rows  # noqa: E402  (a DatabaseTest with helpers and no test of its own)


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
NOTE_3 = '3 assessments were made from event inventories; the earlier image reads them fail-closed'
# The review of S14 (finding 1): an encounter stopped between analyze and assess holds a gemini context, current, and no
# assessment made from an inventory - FINAL 12.1's row the hazard declared, which ADJUDICATION P-1's note replaced.
CONTEXT_1 = ('1 encounter holds a context derived from an event inventory and no assessment made from one: the earlier '
             'image reads that context as current, keeping its holds, and an explicit act reads the document again '
             'with the earlier reader')
CONTEXT_2 = CONTEXT_1.replace('1 encounter holds', '2 encounters hold')
NOTE_3_1 = f'{NOTE_3}; {CONTEXT_1}'


def module_literal(path, name):
    """A literal assigned at module level in ``path``, read with ast (no Django code is imported for it)."""
    return module_constants(APP_ROOT / path, (name,))[name]


def env_of(argv) -> dict:
    return dict(item.split('=', 1) for item in flags(argv, '-e'))


# --- the spec: what the installer names is what the application reads -------------------------------------------------

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
        source = (APP_ROOT / 'cptstudio' / 'settings.py').read_text(encoding='utf-8')
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
        adapter = (APP_ROOT / 'studio' / 'interpretation' / 'fable_adapter.py').read_text(encoding='utf-8')
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
        tree = ast.parse((APP_ROOT / 'studio' / 'interpretation' / 'fable_adapter.py').read_text(encoding='utf-8'))
        imported = {(node.module, alias.name) for node in tree.body if isinstance(node, ast.ImportFrom)
                    for alias in node.names}
        self.assertIn(('studio.participants.credentials', 'load_anthropic_credentials'), imported)
        # the loader's key names are the spec's: one required, one optional, nothing else
        keys = module_literal('studio/participants/credentials.py', 'ANTHROPIC_KEYS')
        self.assertEqual(keys, (*KEY['required'], *KEY['optional']))

    def test_replay_reads_the_recordings_the_image_ships(self):
        # the image is cpt-studio/ copied to /app (WORKDIR /app; COPY . .), and .dockerignore keeps tests/ in it
        dockerfile = (APP_ROOT / 'deploy' / 'Dockerfile').read_text(encoding='utf-8')
        self.assertIn('WORKDIR /app', dockerfile)
        self.assertIn('COPY . .', dockerfile)
        ignored = [line.strip() for line in (APP_ROOT / 'deploy' / '.dockerignore').read_text().splitlines()
                   if line.strip() and not line.startswith('#')]
        self.assertFalse([pattern for pattern in ignored
                          if pattern.rstrip('/') == 'tests' or pattern.startswith('tests/') or 'fixtures' in pattern])
        relative = PurePosixPath(KEY['replay_dir']).relative_to('/app')
        self.assertEqual(str(relative), 'tests/fixtures/interpretation')
        self.assertTrue((APP_ROOT / relative).is_dir())
        # AMENDMENT-2 1.8: every replay interpreter reads <dir>/<its recording_folder>/<request sha256><its suffix>, and
        # Fable's folder is its provider 'anthropic', its suffix '.sse' (Gemini's stay <dir>/gemini/<sha>.json)
        replay = (APP_ROOT / 'studio' / 'interpretation' / 'replay.py').read_text(encoding='utf-8')
        self.assertIn('folder = self.replay_dir / self.recording_folder', replay)
        self.assertIn('class ReplayInterpreterF(_Recordings, fable_adapter.InterpreterF):', replay)
        adapter = (APP_ROOT / 'studio' / 'interpretation' / 'fable_adapter.py').read_text(encoding='utf-8')
        self.assertIn("    recording_folder = NAME\n    recording_suffix = '.sse'\n", adapter)
        self.assertIn('NAME = interpretation.PROVIDER_V3', adapter)
        self.assertEqual(module_literal('studio/interpretation/__init__.py', 'PROVIDER_V3'), 'anthropic')

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
        # and the inventory it names; and names, as well, both shapes of a context derived from an inventory
        # (interpretation.is_new_context's family, and the inventory it names: the review of S14, finding 1)
        self.assertEqual(install.INTERPRETATION_MADE.count('Q(event_inventory__isnull=False)'), 2)
        self.assertIn("interpretation.ENGINE_VERSION.partition('@')[0] + '@'", install.INTERPRETATION_MADE)
        self.assertIn("interpretation.CONTEXT_VERSION.partition('@')[0] + '@'", install.INTERPRETATION_MADE)
        self.assertIn('models.EncounterContext.objects.filter(', install.INTERPRETATION_MADE)
        self.assertIn('Q(version__startswith=', install.INTERPRETATION_MADE)
        source = (APP_ROOT / 'studio' / 'interpretation' / '__init__.py').read_text(encoding='utf-8')
        self.assertIn("return version.partition('@')[0] + '@'", source)  # _family, the same prefix
        self.assertIn("return isinstance(version, str) and version.startswith(_family(CONTEXT_VERSION))", source)


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
        self.assertEqual(self.note({'interpretation': {'assessments': 3, 'encounters': ['e1', 'e2'],
                                                       'context_only': []}}),
                         {'assessments': 3, 'encounters': ['e1', 'e2'], 'context_only': [], 'note': NOTE_3})
        self.assertEqual(self.note({'interpretation': {'assessments': 1, 'encounters': ['e1'],
                                                       'context_only': []}})['note'],
                         '1 assessment was made from event inventories; the earlier image reads them fail-closed')
        self.assertEqual(self.note({'interpretation': {'assessments': 0, 'encounters': [], 'context_only': []}}),
                         {'assessments': 0, 'encounters': [], 'context_only': [],
                          'note': '0 assessments were made from event inventories; the earlier image reads them '
                                  'fail-closed'})
        self.assertEqual(self.note({'interpretation': None}),
                         {'assessments': 0, 'encounters': [], 'context_only': [],
                          'note': 'this image keeps no event inventory, so no assessment or context was made from '
                                  'one'})

    def test_an_encounter_holding_only_a_context_derived_from_an_inventory_is_named_too(self):
        # the review of S14, finding 1: the note names exactly the new-path encounters (ADJUDICATION P-1), and an
        # encounter stopped between analyze and assess holds a current gemini context and no assessment made from one
        self.assertEqual(self.note({'interpretation': {'assessments': 3, 'encounters': ['e1', 'e2', 'e3'],
                                                       'context_only': ['e3']}}),
                         {'assessments': 3, 'encounters': ['e1', 'e2', 'e3'], 'context_only': ['e3'],
                          'note': NOTE_3_1})
        # no assessment yet made from one: still counted, never "not counted" (encounters outnumber assessments)
        self.assertEqual(self.note({'interpretation': {'assessments': 0, 'encounters': ['e1', 'e2'],
                                                       'context_only': ['e1', 'e2']}}),
                         {'assessments': 0, 'encounters': ['e1', 'e2'], 'context_only': ['e1', 'e2'],
                          'note': '0 assessments were made from event inventories; the earlier image reads them '
                                  f'fail-closed; {CONTEXT_2}'})

    def test_a_read_that_fails_or_says_nothing_is_recorded_as_not_counted_and_never_stops_an_undo(self):
        def made(assessments, encounters, context_only):
            return {'interpretation': {'assessments': assessments, 'encounters': encounters,
                                       'context_only': context_only}}
        for answer in (install.InstallError('Counting ... failed (exit 1).'), {}, {'interpretation': 'three'},
                       made(-1, [], []), made(True, [], []), ['not', 'a', 'dict'],
                       made(1, ['e1', 'e2'], []),             # two encounters with an assessment, one assessment
                       made(0, ['e1'], []),                   # an encounter with an assessment, and none counted
                       made(3, ['e1'], ['e1']),               # three assessments, and no encounter with one
                       made(1, ['e1'], ['e2']),               # a context-only encounter that is not named
                       made(2, ['e1', 'e2'], ['e3']),         # likewise, beside one named with its assessments
                       made(2, ['e1', 'e1'], []),             # an encounter named twice
                       made(1, ['e1', 'e2', 'e3'], ['e2', 'e2']),  # a context-only encounter named twice
                       made(1, ['e1'], 'e1'), made(1, ['e1'], None), made(1, ['e1', 'e2'], ['e2', 2]),
                       {'interpretation': {'assessments': 1, 'encounters': ['e1']}}):  # not this script's answer
            with self.subTest(answer=answer):
                found = self.note(answer)
                self.assertEqual((found['assessments'], found['encounters'], found['context_only']),
                                 (None, None, None))
                self.assertTrue(found['note'].startswith('the assessments made from event inventories and the '
                                                         'contexts derived from them were not counted ('),
                                found['note'])
                self.assertTrue(found['note'].endswith('; the earlier image reads any such assessment fail-closed '
                                                       'and any such context as current, keeping its holds'),
                                found['note'])

    def test_an_interrupt_is_never_swallowed(self):
        with self.assertRaises(KeyboardInterrupt):
            self.note(KeyboardInterrupt())


class RollbackNoteTests(TemporaryDirectoryTest):
    """Each rollback-app arm that hands the rows to an older pair declares the note in its receipt and goes on."""

    def test_the_keep_layout_switches_back_and_declares_the_note(self):
        world = keep_world(self.tmp)
        world.interpretation_answer = {'interpretation': {'assessments': 3, 'encounters': ['e1', 'e2', 'e3'],
                                                          'context_only': ['e3']}}
        details, failure = run_rollback_app(world)
        self.assertIsNone(failure, failure and str(failure))
        self.assertEqual(world.violations, [])
        self.assertEqual(details['outcome'], 'switched')
        self.assertEqual(details['interpretation'], {'assessments': 3, 'encounters': ['e1', 'e2', 'e3'],
                                                     'context_only': ['e3'], 'note': NOTE_3_1})
        self.assertTrue(details['summary'].endswith('; ' + NOTE_3_1), details['summary'])
        # read in this revision's image, once its worker is stopped, before the switch back
        read = world.events.index(('interpretation', IMAGE))
        self.assertLess(world.events.index(('close', IMAGE, tuple(KINDS_OLD))), read)
        self.assertLess(read, world.events.index(('reload', 9150)))

    def test_the_back_layout_finishes_the_way_back_and_declares_the_note(self):
        world = halfway_world(self.tmp)
        world.interpretation_answer = {'interpretation': {'assessments': 3, 'encounters': ['e1', 'e2'],
                                                          'context_only': []}}
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
        self.assertIsNone(details['interpretation']['context_only'])
        self.assertIn('were not counted (Counting the assessments failed (exit 1).)', details['interpretation']['note'])


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

    def inventory(self, encounter):
        """A read EventInventory of ``encounter``'s current revision, from a succeeded Gemini run. Synthetic."""
        from studio import models
        return models.EventInventory.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider_run=self.gemini_run(encounter),
            interpretation_version='gemini-events@1', inventory_version='gemini-inventory@1',
            text_sha256='a' * 64, request_sha256='e' * 64, response_sha256='b' * 64, state='read',
            events={'passages': [], 'lesions': [], 'events': [], 'relations': []}, encounter_facts={},
            open_questions=[], verification={}, sha256='c' * 64)

    def assessment(self, encounter, *, engine_version, inventory=False):
        """A context, a routing stand-in and an assessment of ``encounter``'s revision (new-path rows when asked), made
        current. Synthetic."""
        from studio import models
        revision = encounter.current_revision
        made = self.inventory(encounter) if inventory else None
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
                                                     'encounters': sorted([str(events.pk), str(later.pk)]),
                                                     'context_only': []}})
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

    def test_an_encounter_stopped_between_analyze_and_assess_is_named_by_its_context(self):
        # The review of S14, finding 1. FINAL 12.1: the earlier image reads a gemini context as current, a row "declared
        # by the hazard" that ADJUDICATION P-1 replaced with this note, which names exactly the new-path encounters.
        # Here analyze derived the context and its routing stand-in and made it current, Astra ran, Fable is queued,
        # and no assessment was made from the inventory yet: an undo now hands the earlier image that current context.
        from django.utils import timezone
        from studio import models
        stopped = self.encounter('mid-chain')
        read = self.inventory(stopped)
        context = models.EncounterContext.objects.create(
            encounter=stopped, revision=stopped.current_revision, facts={}, sha256='d' * 64, event_inventory=read,
            version='gemini-context@1')
        models.RoutingRun.objects.create(revision=stopped.current_revision, version='gemini-routing@1',
                                         result={'inventory': str(read.pk)}, sha256='2' * 64)
        models.Encounter.objects.filter(pk=stopped.pk).update(current_context=context)
        self.job(stopped, 'fable', models.Job.QUEUED)
        later = self.encounter('later-context')  # a later gemini-context version (interpretation.is_new_context's rule)
        models.EncounterContext.objects.create(encounter=later, revision=later.current_revision, facts={},
                                               sha256='d' * 64, version='gemini-context@2')
        unread = self.encounter('inventory-only')  # interpret ran, analyze did not: no earlier image reads an inventory
        self.inventory(unread)
        events = self.encounter('events')  # an assessment and the context it was made with: named once
        self.assessment(events, engine_version='cpt-studio-events@1', inventory=True)
        legacy = self.encounter('legacy')
        self.assessment(legacy, engine_version='cpt-studio-validation@10')
        answer = run_in_image(install.INTERPRETATION_MADE, {})
        self.assertEqual(answer, {'interpretation': {
            'assessments': 1, 'encounters': sorted(str(item.pk) for item in (stopped, later, events)),
            'context_only': sorted([str(stopped.pk), str(later.pk)])}})
        # never a hazard (P-1): an undo's close - here with the fewest kinds, as when no next worker can be asked -
        # fails the queued Fable stage and names nothing
        self.assertEqual(run_in_image(install.UNDO_HAZARDS_READ, {}), {'hazards': {}})
        closed = run_in_image(install.CLOSE_STAGES, {'since': timezone.now().isoformat(), 'note': self.NOTE,
                                                     'kinds': list(install.COMMON_STAGE_KINDS)})
        self.assertEqual((closed['closed'], closed['kinds'], closed['hazards']), (1, ['fable'], {}))

        def in_this_image(image, env, body, params, **kwargs):
            return run_in_image(body, params)
        with mock.patch.object(install, 'app_script', in_this_image):
            note = install.interpretation_note(IMAGE, b'', REVISION)
        self.assertEqual(note, {**answer['interpretation'],
                                'note': '1 assessment was made from event inventories; the earlier image reads them '
                                        f'fail-closed; {CONTEXT_2}'})

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



# --- AMENDMENT-2 8.5: the rows the Fable candidate writes, on a real database -----------------------------------------

# round r3 (DECISIONS D322 (5)): the D15 inventory's question record - an established (supported) answer whose witness
# names the approved ready code 45378, the code an established answer released. Synthetic.
D15_QUESTION_EVENTS = {'questions': [
    {'id': 'q1.1.1', 'result': 'supported', 'witnesses': [{'code': '45378', 'fact': 'event_session'}]}]}


class FableRows(V2Rows):
    """Rows the Fable candidate writes (AMENDMENT-2 8.1, 8.5), each label read from the interpretation package: its runs
    (provider PROVIDER_V3, adapter ADAPTER_VERSION_V3, model MODEL_V3), an inventory of INTERPRETATION_PAIR_V3 and
    INVENTORY_VERSION_V3 bound to both runs, a context of CONTEXT_VERSION_V2 (unchanged by 8.1) and an assessment of
    ENGINE_VERSION_V3. Nothing in them is Gemini's. Synthetic. Helpers only: no test of its own (ops/test_rollback_check
    builds its D15 database with fill_d15)."""

    def fable_run(self, encounter, purpose, *, state='succeeded', request='a', scope=None, sent=True):
        from django.utils import timezone
        from studio import interpretation, models
        return models.ProviderRun.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider=interpretation.PROVIDER_V3,
            adapter_version=interpretation.ADAPTER_VERSION_V3, purpose=purpose, request_sha256=request * 64,
            request_body={}, contexts=[], state=state, sent=sent, http_status=200 if sent else None,
            scope=scope or {}, endpoint='https://api.anthropic.com/v1/messages',
            requested_model=interpretation.MODEL_V3, returned_model=interpretation.MODEL_V3 if sent else '',
            started_at=timezone.now())

    def fable_inventory(self, encounter, events=None):
        from studio import interpretation, models
        first = self.fable_run(encounter, interpretation.PURPOSE, request='a')
        second = self.fable_run(encounter, interpretation.APPRAISAL_PURPOSE, request='b')
        return models.EventInventory.objects.create(
            encounter=encounter, revision=encounter.current_revision, provider_run=first, appraisal_run=second,
            interpretation_version=interpretation.INTERPRETATION_PAIR_V3,
            inventory_version=interpretation.INVENTORY_VERSION_V3, text_sha256='a' * 64, request_sha256='e' * 64,
            response_sha256='b' * 64, state='read', events=events or {}, encounter_facts={}, open_questions=[],
            verification={}, sha256='c' * 64)

    def fable(self, tag, events=None):
        """An interpreted and appraised upload of the Fable candidate, its @3 assessment current: (encounter,
        assessment); its inventory's events ``events`` (none when not given)."""
        from studio import interpretation
        encounter = self.extracted(self.encounter(tag))
        made = self.fable_inventory(encounter, events)
        context = self.context(encounter, version=interpretation.CONTEXT_VERSION_V2, inventory=made)
        assessment = self.assessment(encounter, context, engine_version=interpretation.ENGINE_VERSION_V3,
                                     provider_run=self.made_run(encounter), inventory=made)
        return encounter, assessment

    def fill_d15(self):
        """A database the Fable candidate filled with every record kind of FINAL-V2 6.4's D15 run and AMENDMENT-2 8.5's
        rows - each on @3 rows and anthropic runs only, none of FINAL-V2's @2 or Gemini's: an interpreted and appraised
        upload; a held, an excluded and a reinstated code; an approved code with a modifier and its export; a member
        answer; a second review; an interpreter hold (a decline's); a queued interpret and a queued appraise job; a
        pass-2 refusal and an unhealthy appraisal; a held code whose item is a new fact; and round r3's question
        stage records (a queued question job, a question run, a code an established answer released). Returns the
        encounter."""
        from studio import interpretation, models
        # round r3: the inventory records an established answer naming the approved ready code 45378 (below)
        encounter, assessment = self.fable('d15', D15_QUESTION_EVENTS)
        revision, user = encounter.current_revision, encounter.created_by

        def proposal(code, position, **fields):
            return models.Proposal.objects.create(
                assessment=assessment, key=f'k{position}', code=code, code_kind='cpt', family='gi.colonoscopy',
                profile_version='synthetic@1', fingerprint=f'{code}{position}'.ljust(64, '0'), position=position,
                **fields)

        def decision(item, action, modifiers=()):
            return models.Decision.objects.create(
                encounter=encounter, assessment=assessment, revision=revision, proposal=item, action=action,
                reviewer=user, reviewer_kind='human', profile_version='synthetic@1',
                proposal_fingerprint=item.fingerprint, modifiers=list(modifiers))
        proposal('45385', 0, bucket='selected', status='needs_clarification')
        excluded = proposal('45380', 1, bucket='excluded', status='excluded')
        decision(excluded, 'reinstate')
        approved = proposal('45378', 2, bucket='selected', status='ready')
        decision(approved, 'approve', ['59'])
        models.ReportArtifact.objects.create(encounter=encounter, assessment=assessment, kind='approved', fmt='txt',
                                             filename='approved.txt', content=b'Synthetic approved export.',
                                             sha256='4' * 64, snapshot_sha256='5' * 64, generated_by=user,
                                             audience='customer')
        models.MemberAnswer.objects.create(encounter=encounter, revision=revision, assessment=assessment, fact='extent',
                                           family='gi.colonoscopy', code='45378', value='not_documented',
                                           answered_by=user)
        self.made_run(encounter, purpose='second_review', request='2')
        declined = self.fable_run(encounter, interpretation.PURPOSE, request='d')
        models.InterpreterHold.objects.create(reason=models.InterpreterHold.DECLINED, http_status=200,
                                              vendor_status='cyber', run=declined)
        queued = self.extracted(self.encounter('d15-queued'))
        self.job(queued, 'interpret', models.Job.QUEUED)
        self.job(queued, 'appraise', models.Job.QUEUED)
        self.fable_run(encounter, interpretation.APPRAISAL_PURPOSE, request='r', scope={'refused': 'reading'})
        self.fable_run(encounter, interpretation.APPRAISAL_PURPOSE, request='u', scope={'refused': 'unhealthy'})
        models.Clarification.objects.create(encounter=encounter, assessment=assessment, scope='service',
                                            family='gi.colonoscopy', fact='event_entry', question='Synthetic?',
                                            reason='Synthetic.')
        # round r3 (DECISIONS D322 (5)): the question stage's records - a queued question job, a question run, and the
        # approved ready code 45378 released by an established answer the inventory records (D15_QUESTION_EVENTS)
        self.job(queued, 'question', models.Job.QUEUED)
        self.fable_run(encounter, interpretation.APPRAISAL_PURPOSE, request='q',
                       scope={'question': {'round': 1, 'batch': 1}})
        return encounter


class FableRowsOnTheDatabaseTests(FableRows):
    """AMENDMENT-2 8.5: the installer's reads that name versions accept the Fable candidate's rows - V1_ROWS (v1 rows
    only, by exact version) never trips on them, INTERPRETATION_MADE names them by family, INSTALL_COUNTS reads them as
    read at the current versions, and CLOSE_STAGES settles an anthropic run in flight as any other's."""

    def test_the_v1_rows_read_never_trips_on_amendment_2s_rows(self):
        self.fable('fable')
        self.v2('stored-v2')  # FINAL-V2's @2 row, read as stored, beside it
        answer = run_in_image(install.V1_ROWS, {'engine_version': install.V1_ENGINE_VERSION,
                                                'interpretation_version': install.V1_INTERPRETATION_VERSION,
                                                'limit': install.NAMED_LIMIT})
        self.assertEqual(answer, clean_v1_rows())
        self.assertIsNone(install.v1_rows_refusal(answer))
        held = self.extracted(self.encounter('v1'))  # and a v1 row still does
        self.assessment(held, self.context(held), engine_version=install.V1_ENGINE_VERSION)
        answer = run_in_image(install.V1_ROWS, {'engine_version': install.V1_ENGINE_VERSION,
                                                'interpretation_version': install.V1_INTERPRETATION_VERSION,
                                                'limit': install.NAMED_LIMIT})
        self.assertEqual((answer['assessments'], answer['encounters']), (1, [str(held.pk)]))

    def test_the_note_and_the_counts_read_the_fable_rows_by_their_families_and_current_versions(self):
        encounter, _ = self.fable('fable')
        made = run_in_image(install.INTERPRETATION_MADE, {})
        self.assertEqual(made, {'interpretation': {'assessments': 1, 'encounters': [str(encounter.pk)],
                                                   'context_only': []}})
        counts = run_in_image(install.INSTALL_COUNTS, {'limit': install.NAMED_LIMIT,
                                                       'token_sentence': install.CORTI_TOKEN_REFUSAL})
        self.assertEqual(install.counts_problem(counts), '')
        self.assertEqual(counts['size']['without_inventory'], 0)  # read at jobs.current_versions: the @3 pair
        self.assertFalse(counts['values']['first_install'])  # a gemini context and a new-path inventory exist
        self.assertEqual(run_in_image(install.UNDO_HAZARDS_READ, {}), {'hazards': {}})  # P-1: never a hazard

    def test_an_undo_settles_an_anthropic_run_in_flight_as_any_other(self):
        from studio import interpretation, models
        running = self.extracted(self.encounter('running'))
        self.job(running, 'appraise', models.Job.RUNNING)
        sending = self.fable_run(running, interpretation.APPRAISAL_PURPOSE, state='sending', sent=False)
        models.ProviderExchange.objects.create(run=sending, turn=1, request_body={}, request_sha256='f' * 64,
                                               state='succeeded', http_status=200)  # the answer reached CPT Studio
        closed = self.close(revert=True)
        self.assertEqual((closed['closed'], closed['kinds'], closed['runs_unknown']), (1, ['appraise'], 1))
        sending.refresh_from_db()
        self.assertEqual((sending.state, sending.sent), (models.ProviderRun.UNKNOWN, True))  # may have reached Anthropic


if __name__ == '__main__':
    unittest.main()
