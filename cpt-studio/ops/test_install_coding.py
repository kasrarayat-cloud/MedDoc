"""Unit tests for the Fable coding build's installer changes (DECISIONS D351-D353; the build specification, sections 3.1,
3.2, 4.1 and 11): the image checks that replace the PDF gate and the OCR version checks (`soffice --version`, reported;
the anthropic SDK, exactly the pinned release), the two owner figures read from settings.py and written into every
container with the coder's effort and mode, the coder's credential - the only file an app phase requires or mounts, in
the worker alone - and the arguments that carry the coding mode. No Docker, sudo, nginx or network.

The app phase itself (its loader check before migrate, the pair it starts) is tested in test_install_harness
(AppPhaseCodingTests) and on the fake blue/green host in test_install_bluegreen (InterpreterBlueGreenTests).

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v
"""
import base64
import io
import json
import re
import shutil
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import guard_host, release_host  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40
IMAGE = 'sha256:' + 'c' * 64
RULING = 'docs/foundation/rulings/2026-10-23-cpt-studio-gi.md'
CODER = install.CODER
CODER_MOUNT = f'type=bind,src={CODER["target"]},dst={CODER["mounted"]},readonly'
FILES_MOUNT = f'type=volume,src={install.FILES_VOLUME},dst={install.STATE_DIR}'
# A settings.py as the coding build writes its two figures (each one positional _env default, as the QUESTION pair was)
SETTINGS = ("import os\n\n\ndef _env(name, default=None, *, required=False):\n"
            "    return os.getenv(f'CPT_STUDIO_{name}', default)\n\n\n"
            "DOCUMENT_CEILING_USD = _env('DOCUMENT_CEILING_USD', '{ceiling}')\n"
            "CONCURRENT_DOCUMENTS = int(_env('CONCURRENT_DOCUMENTS', '{concurrency}'))\n")
SMOKE = ['run', '--rm', '--pull=never', '--network', 'none', '--read-only', '--tmpfs', '/tmp', '--cap-drop', 'ALL',
         '--security-opt', 'no-new-privileges', '--no-healthcheck']


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


def settings(ceiling='25', concurrency='4'):
    return SETTINGS.replace('{ceiling}', ceiling).replace('{concurrency}', concurrency)


def flags(argv, flag):
    return [argv[i + 1] for i, part in enumerate(argv) if part == flag]


def env_of(argv) -> dict:
    return dict(item.split('=', 1) for item in flags(argv, '-e'))


# --- the two owner figures ----------------------------------------------------------------------------------------------

class CodingFiguresTests(unittest.TestCase):
    def test_each_figure_is_its_one_default_named_as_the_container_reads_it(self):
        self.assertEqual(install.CODING_FIGURES, ('DOCUMENT_CEILING_USD', 'CONCURRENT_DOCUMENTS'))
        self.assertEqual(install.coding_figures(settings()),
                         {'CPT_STUDIO_DOCUMENT_CEILING_USD': '25', 'CPT_STUDIO_CONCURRENT_DOCUMENTS': '4'})
        # the values are the file's, as written: never re-formatted, never rounded
        self.assertEqual(install.coding_figures(settings('12.50', '16')),
                         {'CPT_STUDIO_DOCUMENT_CEILING_USD': '12.50', 'CPT_STUDIO_CONCURRENT_DOCUMENTS': '16'})
        self.assertEqual(install.coding_figures(settings('0', '1'))['CPT_STUDIO_DOCUMENT_CEILING_USD'], '0')

    def test_a_missing_repeated_or_malformed_default_refuses_and_starts_nothing(self):
        cases = {
            'the ceiling missing': settings().replace("_env('DOCUMENT_CEILING_USD', '25')", "'25'"),
            'the concurrency missing': settings().replace("_env('CONCURRENT_DOCUMENTS', '4')", "4"),
            'the ceiling given twice': settings() + "OTHER = _env('DOCUMENT_CEILING_USD', '30')\n",
            'a keyword default is not read': settings().replace("'CONCURRENT_DOCUMENTS', '4'",
                                                                "'CONCURRENT_DOCUMENTS', default='4'"),
            'a computed default is not read': settings().replace("'DOCUMENT_CEILING_USD', '25'",
                                                                 "'DOCUMENT_CEILING_USD', str(25)"),
            'a negative ceiling': settings('-1'), 'a word': settings('twenty'), 'not a number': settings('NaN'),
            'an infinite ceiling': settings('Infinity'), 'no documents at once': settings(concurrency='0'),
            'a fraction of a document': settings(concurrency='1.5'), 'a negative count': settings(concurrency='-2'),
            'a digit that is not ASCII': settings(concurrency='٣'), 'an empty count': settings(concurrency=''),
            # the question stage's pair, which no container is given now, is not read in their place
            'only the question pair': ("import os\n\ndef _env(name, default=None):\n    return default\n\n"
                                       "QUESTION_DOCUMENT_CEILING_USD = _env('QUESTION_DOCUMENT_CEILING_USD', '25')\n"
                                       "_concurrency = _env('QUESTION_ROUND_CONCURRENCY', '4')\n"),
        }
        for label, text in cases.items():
            with self.subTest(label), self.assertRaises(install.InstallError) as caught:
                install.coding_figures(text)
            self.assertIn('nothing was started', str(caught.exception))
            self.assertRegex(str(caught.exception), r'cptstudio/settings\.py gives (DOCUMENT_CEILING_USD|CONCURRENT_'
                                                    r'DOCUMENTS) ')

    def test_the_revisions_own_settings_give_both_once(self):
        # read from the file the install reads (SETTINGS_SOURCE: this tree's cptstudio/settings.py); lane A of the
        # build gives each one positional default there, as the QUESTION pair was given
        figures = install.coding_figures()
        self.assertEqual(sorted(figures), ['CPT_STUDIO_CONCURRENT_DOCUMENTS', 'CPT_STUDIO_DOCUMENT_CEILING_USD'])
        source = (APP_ROOT / 'ops' / 'install.py').read_text(encoding='utf-8')
        self.assertIn("SETTINGS_SOURCE = SELF.parents[1] / 'cptstudio' / 'settings.py'\n", source)


# --- the environment every container is given, and the coder's file ----------------------------------------------------

class CodingEnvironmentTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(install, 'coding_figures', return_value={
            'CPT_STUDIO_DOCUMENT_CEILING_USD': '25', 'CPT_STUDIO_CONCURRENT_DOCUMENTS': '4'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_container_is_given_the_mode_the_effort_and_the_figures(self):
        env = dict(item.split('=', 1) for item in install.runtime_env('disabled', '')[1::2])
        self.assertEqual((env['CPT_STUDIO_CODING_MODE'], env['CPT_STUDIO_CODING_EFFORT']), ('disabled', 'max'))
        self.assertEqual((env['CPT_STUDIO_DOCUMENT_CEILING_USD'], env['CPT_STUDIO_CONCURRENT_DOCUMENTS']), ('25', '4'))
        self.assertNotIn(CODER['file_env'], env)  # disabled names no file
        self.assertFalse([name for name in env if name.startswith('CPT_STUDIO_QUESTION_')])
        # an earlier revision's providers, named disabled for a pair that reads them (a switch-back's previous pair)
        for name in ('CPT_STUDIO_PROVIDER_MODE', 'CPT_STUDIO_ASTRA_MODE', 'CPT_STUDIO_FABLE_MODE',
                     'CPT_STUDIO_GEMINI_MODE'):
            self.assertEqual(env[name], 'disabled')
        self.assertEqual((install.CODING_EFFORT, install.CODING_MODES), ('max', ('disabled', 'live')))

    def test_live_and_a_loader_checks_file_name_the_worker_path(self):
        live = dict(item.split('=', 1) for item in install.runtime_env('disabled', RULING, coding='live')[1::2])
        self.assertEqual((live['CPT_STUDIO_CODING_MODE'], live[CODER['file_env']]), ('live', CODER['mounted']))
        self.assertEqual(live['CPT_STUDIO_AUTHORIZATION_REF'], RULING)
        checked = dict(item.split('=', 1) for item in install.runtime_env('disabled', '', coding_file=True)[1::2])
        self.assertEqual((checked['CPT_STUDIO_CODING_MODE'], checked[CODER['file_env']]), ('disabled', CODER['mounted']))

    def test_an_unknown_coding_mode_is_refused_rather_than_started(self):
        for mode in ('replay', 'LIVE', 'on'):
            with self.subTest(mode=mode):
                with self.assertRaises(install.InstallError):
                    install.runtime_env('disabled', '', coding=mode)
                with self.assertRaises(install.InstallError):
                    install.coding_mode(SimpleNamespace(coding_mode=mode))
        self.assertEqual(install.coding_mode(SimpleNamespace()), 'disabled')
        self.assertEqual(install.coding_mode(SimpleNamespace(coding_mode=None)), 'disabled')
        self.assertEqual(install.coding_mode(SimpleNamespace(coding_mode='live')), 'live')

    def test_only_the_live_coders_worker_mounts_the_file_and_the_web_gets_the_path_and_no_file(self):
        worker = install.service_args('worker', IMAGE, REVISION, 'disabled', RULING, coding='live')
        self.assertEqual(flags(worker, '--mount'), [FILES_MOUNT, CODER_MOUNT])  # nothing of Corti's or Astra's
        self.assertEqual(env_of(worker)[CODER['file_env']], CODER['mounted'])
        self.assertEqual(env_of(worker)['CPT_STUDIO_CODING_MODE'], 'live')
        web = install.service_args('web', IMAGE, REVISION, 'disabled', RULING, name=install.INCOMING_WEB, port=9151,
                                   coding='live')
        self.assertEqual(flags(web, '--mount'), [FILES_MOUNT])
        self.assertEqual(env_of(web)[CODER['file_env']], CODER['mounted'])
        disabled = install.service_args('worker', IMAGE, REVISION, 'disabled', '')
        self.assertEqual(flags(disabled, '--mount'), [FILES_MOUNT])
        self.assertNotIn(CODER['file_env'], env_of(disabled))
        self.assertEqual(env_of(disabled)['CPT_STUDIO_CODING_MODE'], 'disabled')

    def test_the_one_file_is_bound_once_whichever_of_its_holders_is_live(self):
        # the coder's file is the Fable participant's and the interpreter's (one source, copy and worker path)
        for field in ('source', 'target', 'mounted', 'file_env', 'loader', 'setting', 'required', 'optional'):
            with self.subTest(field=field):
                self.assertEqual(CODER[field], install.PARTICIPANTS['fable'][field])
                self.assertEqual(CODER[field], install.INTERPRETER[field])
        self.assertEqual(install.coder_mount(), install.interpreter_mount())
        self.assertEqual(install.coder_mount(), CODER_MOUNT)
        argv = install.service_args('worker', IMAGE, REVISION, 'disabled', RULING, {'fable': 'live'},
                                    interpreter='live', coding='live')
        self.assertEqual(flags(argv, '--mount').count(CODER_MOUNT), 1)
        self.assertEqual(install.worker_credential_mounts((), False, True), [CODER_MOUNT])
        self.assertEqual(install.worker_credential_mounts(('fable',), True, True), [CODER_MOUNT])

    def test_one_shots_run_the_coder_disabled_and_the_loader_check_mounts_the_key_offline(self):
        calls = []

        def fake_run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(returncode=0, stdout=b'coding-credentials-parse-ok\n', stderr=b'')
        with mock.patch.object(install, 'run', fake_run), mock.patch.object(install, 'inspect', return_value=None):
            install.oneshot(IMAGE, ['migrate'], b'')
            install.oneshot(IMAGE, ['manage', 'shell', '-c', install.CODING_CREDENTIALS_CHECK], b'', network='none',
                            coding_file=True, timeout=120)
        plain, check = calls
        self.assertEqual(env_of(plain)['CPT_STUDIO_CODING_MODE'], 'disabled')
        self.assertNotIn(CODER['file_env'], env_of(plain))
        self.assertNotIn(CODER_MOUNT, flags(plain, '--mount'))
        self.assertEqual(env_of(check)['CPT_STUDIO_CODING_MODE'], 'disabled')  # the coder itself never sends here
        self.assertEqual(env_of(check)[CODER['file_env']], CODER['mounted'])
        self.assertEqual(flags(check, '--mount'), [CODER_MOUNT])
        self.assertEqual(flags(check, '--network'), ['none'])

    def test_no_secret_name_or_value_is_ever_an_argument(self):
        for argv in (install.service_args('worker', IMAGE, REVISION, 'disabled', RULING, coding='live'),
                     install.service_args('web', IMAGE, REVISION, 'disabled', RULING, coding='live')):
            joined = ' '.join(argv)
            for name in ('ANTHROPIC_API_KEY', 'ANTHROPIC_WORKSPACE_ID', 'SECRET_KEY', 'DB_PASSWORD'):
                self.assertNotIn(name, joined)

    def test_the_worker_may_hold_the_coders_key_read_only_and_the_web_never(self):
        def container(role, writable):
            return {'Image': IMAGE, 'Config': {'User': f'{install.APP_UID}:{install.APP_UID}',
                                               'Labels': {install.LABEL: '1', install.ROLE_LABEL: role}},
                    'HostConfig': {'ReadonlyRootfs': True, 'CapDrop': ['ALL'], 'SecurityOpt': ['no-new-privileges'],
                                   'PortBindings': ({'8000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '9150'}]}
                                                    if role == 'web' else {})},
                    'Mounts': [{'Type': 'bind', 'Source': CODER['target'], 'Destination': CODER['mounted'],
                                'RW': writable}]}
        self.assertEqual(install.service_problems(container('worker', False), 'worker', IMAGE), [])
        self.assertEqual(install.service_problems(container('worker', True), 'worker', IMAGE),
                         ['a bind mount other than a read-only credentials file'])
        self.assertEqual(install.service_problems(container('web', False), 'web', IMAGE, port=9150),
                         ['the web holds a bind-mounted file (only the worker holds credentials)'])


# --- the coder's credentials checks (an app phase's, and a switch-back's for a previous pair that codes) -----------------

class CodingCredentialChecksTests(unittest.TestCase):
    INSTALLED = {'exists': True, 'kind': 'file', 'uid': install.APP_UID, 'gid': install.APP_UID, 'mode': '0o400'}

    def test_live_needs_the_copy_the_secrets_phase_writes_and_disabled_needs_nothing(self):
        for state in ({'exists': False}, {**self.INSTALLED, 'mode': '0o440'}, {**self.INSTALLED, 'kind': 'link'}):
            with self.subTest(state=state), \
                    mock.patch.object(install, 'helper_stat', return_value={CODER['target']: state}), \
                    self.assertRaises(install.InstallError) as caught:
                install.check_credential_files('disabled', [], coding='live')
            self.assertIn(f'--coding-mode live: {CODER["target"]} is not the 10150:10150 0400 file',
                          str(caught.exception))
            self.assertIn(CODER['source'], str(caught.exception))
        with mock.patch.object(install, 'helper_stat', return_value={CODER['target']: self.INSTALLED}) as stat:
            install.check_credential_files('disabled', [], coding='live')
        stat.assert_called_once_with([CODER['target']])
        with mock.patch.object(install, 'helper_stat') as stat:
            install.check_credential_files('disabled', [], coding='disabled')
        stat.assert_not_called()  # disabled reads no file: an install without the Anthropic source stays possible

    def test_the_loader_check_is_the_coders_own_offline_and_its_error_kept_only_when_clean(self):
        compile(install.CODING_CREDENTIALS_CHECK, 'coding-credentials-check', 'exec')
        self.assertIn('from studio.fable.credentials import load_anthropic_credentials\n',
                      install.CODING_CREDENTIALS_CHECK)
        self.assertNotIn('participants', install.CODING_CREDENTIALS_CHECK)
        seen = []
        for stderr, clean in ((b'CredentialsError: ANTHROPIC_API_KEY is missing.', True),
                              (b'CredentialsError: sk-ant-synthetic-0123456789 refused', False)):
            def oneshot(image_id, command, env, **kwargs):
                seen.append((image_id, command, kwargs))
                return SimpleNamespace(returncode=1, stdout=b'', stderr=stderr)
            with self.subTest(clean=clean), mock.patch.object(install, 'oneshot', oneshot), \
                    mock.patch.object(install, 'credential_free', return_value=clean) as scan, \
                    self.assertRaises(install.InstallError) as caught:
                install.check_credential_parsing(IMAGE, b'', 'disabled', [], coding='live')
            self.assertEqual(caught.exception.output, stderr if clean else b'')
            scan.assert_called_once_with([stderr], ['anthropic'])  # the coder's file, scanned under its name
        self.assertEqual(seen[0], (IMAGE, ['manage', 'shell', '-c', install.CODING_CREDENTIALS_CHECK],
                                   {'network': 'none', 'coding_file': True, 'timeout': 120}))
        with mock.patch.object(install, 'oneshot') as oneshot:
            install.check_credential_parsing(IMAGE, b'', 'disabled', [], coding='disabled')
        oneshot.assert_not_called()


# --- the image checks --------------------------------------------------------------------------------------------------

class ImageCheckTests(unittest.TestCase):
    def docker(self, stdout=b'', stderr=b'', code=0):
        calls = []

        def fake(*args, **kwargs):
            calls.append((list(args), kwargs))
            return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)
        return fake, calls

    def test_soffice_runs_as_the_images_own_user_offline_and_its_line_is_reported(self):
        fake, calls = self.docker(b'LibreOffice 7.4.7.2 40(Build:2)\n')
        with mock.patch.object(install, 'docker', fake):
            self.assertEqual(install.image_soffice(SMOKE, IMAGE), 'LibreOffice 7.4.7.2 40(Build:2)')
        (args, kwargs), = calls
        self.assertEqual(args, [*SMOKE, '-e', 'HOME=/tmp', '--entrypoint', 'soffice', IMAGE, '--version'])
        self.assertEqual(kwargs, {'check': False, 'timeout': 120})
        # a warning printed before it is not the version line, and is not reported
        fake, _ = self.docker(b'Warning: failed to launch javaldx\nLibreOffice 7.4.7.2 40(Build:2)\n')
        with mock.patch.object(install, 'docker', fake):
            self.assertEqual(install.image_soffice(SMOKE, IMAGE), 'LibreOffice 7.4.7.2 40(Build:2)')

    def test_a_soffice_that_fails_or_names_something_else_refuses_the_image(self):
        for stdout, code in ((b'', 127), (b'LibreOffice 7.4.7.2\n', 1), (b'\n\n', 0), (b'soffice 1.0\n', 0),
                             (b'Warning: failed to launch javaldx\n', 0), (b'LibreOffice\n', 0)):
            fake, _ = self.docker(stdout, b'/bin/sh: soffice: not found\n', code)
            with self.subTest(stdout=stdout, code=code), mock.patch.object(install, 'docker', fake), \
                    self.assertRaises(install.InstallError) as caught:
                install.image_soffice(SMOKE, IMAGE)
            self.assertIn('cannot run `soffice --version`', str(caught.exception))
            self.assertIn(b'soffice: not found', caught.exception.output)

    def test_the_anthropic_sdk_must_be_exactly_the_pinned_release(self):
        self.assertEqual(install.ANTHROPIC_SDK_VERSION, '2.11.0')
        self.assertEqual(install.ANTHROPIC_SDK_SCRIPT, 'import anthropic; print(anthropic.__version__)')
        fake, calls = self.docker(b'2.11.0\n')
        with mock.patch.object(install, 'docker', fake):
            self.assertEqual(install.image_anthropic(SMOKE, IMAGE), '2.11.0')
        (args, kwargs), = calls
        self.assertEqual(args, [*SMOKE, '--entrypoint', 'python', IMAGE, '-c', install.ANTHROPIC_SDK_SCRIPT])
        self.assertEqual(kwargs, {'check': False, 'timeout': 120})
        for stdout, code in ((b'2.11.1\n', 0), (b'2.11.0rc1\n', 0), (b'2.11\n', 0), (b'', 0), (b'2.11.0\n', 1),
                             (b'', 1)):
            fake, _ = self.docker(stdout, b"ModuleNotFoundError: No module named 'anthropic'\n", code)
            with self.subTest(stdout=stdout, code=code), mock.patch.object(install, 'docker', fake), \
                    self.assertRaises(install.InstallError) as caught:
                install.image_anthropic(SMOKE, IMAGE)
            self.assertIn('does not import anthropic 2.11.0', str(caught.exception))

    def gate_answer(self, found):
        return (install.CONVERSION_ANSWER + json.dumps(found) + '\n').encode()

    def test_the_conversion_gate_converts_a_synthetic_word_file_with_the_workers_own_code_and_constraints(self):
        found = {'head': '%PDF-', 'bytes': 8123, 'sha256': 'e' * 64}
        fake, calls = self.docker(b'some import noise\n' + self.gate_answer(found))
        with mock.patch.object(install, 'docker', fake):
            self.assertEqual(install.image_conversion(IMAGE), found)
        (args, kwargs), = calls
        self.assertEqual(kwargs, {'check': False, 'timeout': 180})
        source = args[-1]
        self.assertEqual(args[:-1], ['run', '--rm', '--pull=never', '--network', 'none', '--no-healthcheck',
                                     *install.hardening(*install.WORKER_LIMITS), '-e',
                                     'CPT_STUDIO_SECRET_KEY=image-smoke-check-only', IMAGE, 'manage', 'shell', '-c'])
        # the worker's runtime: its user, a read-only root, /tmp a tmpfs, its memory and pids, and no network
        for flag in ('--read-only', f'{install.APP_UID}:{install.APP_UID}', '--network', 'none', '1536m'):
            self.assertIn(flag, args)
        self.assertTrue(any(arg.startswith('/tmp:rw,noexec') for arg in args))
        self.assertEqual(install.WORKER_LIMITS, ('1536m', 256, '1g'))  # service_args starts the worker with them
        self.assertIn('*hardening(*WORKER_LIMITS)', (APP_ROOT / 'ops' / 'install.py').read_text(encoding='utf-8'))
        # the application's own entry point, the one the worker converts with, on the synthetic document built here
        self.assertIn('from studio.fable import document', source)
        self.assertIn('document.convert_docx(base64.b64decode(DOCX))', source)
        namespace = {}
        exec(source.split('\n', 2)[0] + '\n' + source.split('\n', 2)[1], namespace)  # DOCX and ANSWER only
        self.assertEqual(base64.b64decode(namespace['DOCX']), install.synthetic_docx())
        self.assertEqual(namespace['ANSWER'], install.CONVERSION_ANSWER)

    def test_the_synthetic_word_file_is_a_minimal_docx_holding_one_paragraph_and_always_the_same_bytes(self):
        data = install.synthetic_docx()
        self.assertEqual(data, install.synthetic_docx())
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.namelist(), ['[Content_Types].xml', '_rels/.rels', 'word/document.xml'])
            body = archive.read('word/document.xml').decode()
        self.assertIn(f'<w:t>{install.CONVERSION_TEXT}</w:t>', body)
        self.assertIn('SYNTHETIC', install.CONVERSION_TEXT)
        with self.assertRaises(ValueError):
            install.synthetic_docx('a <tag> & more')

    def test_a_conversion_that_fails_or_answers_no_pdf_refuses_the_image(self):
        cases = ((b'', 1), (b'Traceback ...\nstudio.fable.document.DocumentError: The Word file could not be opened.\n', 1),
                 (self.gate_answer({'head': '<html', 'bytes': 900, 'sha256': 'e' * 64}), 0),
                 (self.gate_answer({'head': '%PDF-', 'bytes': 5, 'sha256': 'e' * 64}), 0),
                 (self.gate_answer({'head': '%PDF-', 'bytes': 800, 'sha256': 'nope'}), 0),
                 (self.gate_answer({'head': '%PDF-', 'bytes': 800, 'sha256': 'e' * 64}) * 2, 0),
                 (install.CONVERSION_ANSWER.encode() + b'not json\n', 0),
                 (self.gate_answer({'head': '%PDF-', 'bytes': 800, 'sha256': 'e' * 64}), 1))
        for stdout, code in cases:
            fake, _ = self.docker(stdout, b'soffice exited with 1\n', code)
            with self.subTest(stdout=stdout[:40], code=code), mock.patch.object(install, 'docker', fake), \
                    self.assertRaises(install.InstallError) as caught:
                install.image_conversion(IMAGE)
            self.assertIn('cannot convert a Word document to PDF', str(caught.exception))
            self.assertIn(b'soffice exited with 1', caught.exception.output)

    def test_the_image_phase_runs_no_ocr_and_no_pdf_reading(self):
        source = (APP_ROOT / 'ops' / 'install.py').read_text(encoding='utf-8')
        for gone in ('tesseract', 'pdftoppm', 'PDF_GATE', 'pdf_reading', 'extract_document'):
            self.assertNotIn(gone, source)

    def test_the_dockerfile_installs_libreoffice_writer_and_dejavu_without_recommends_and_no_ocr(self):
        dockerfile = (APP_ROOT / 'deploy' / 'Dockerfile').read_text(encoding='utf-8')
        installs = [line for line in dockerfile.splitlines() if 'apt-get install' in line]
        self.assertEqual(len(installs), 1)
        self.assertEqual(installs[0].split(), ['&&', 'apt-get', 'install', '-y', '--no-install-recommends',
                                               'libreoffice-writer-nogui', 'fonts-dejavu-core', '\\'])
        for gone in ('tesseract', 'poppler'):
            self.assertNotIn(gone, dockerfile)
        # what stays as it was: the user, the labels, collectstatic and the requirements install
        for kept in ('USER 10150:10150', 'LABEL org.opencontainers.image.title="CPT Studio"',
                     'org.opencontainers.image.revision=${REVISION}', 'python manage.py collectstatic --noinput',
                     'RUN pip install --no-cache-dir -r requirements.txt', 'rm -rf /var/lib/apt/lists/*'):
            self.assertIn(kept, dockerfile)


# --- arguments ---------------------------------------------------------------------------------------------------------

class StopBoundTests(unittest.TestCase):
    def test_the_worker_is_given_the_coding_jobs_stale_threshold_to_stop(self):
        # two max-effort sends and a conversion can outlast round r3's 1,800 s: the worker's bound is the age at which
        # the stale sweep takes a running coding job for a dead worker's (studio.jobs.CODE_STALE_SECONDS)
        self.assertEqual(install.STOP_SECONDS, {'web': 30, 'worker': 3600})
        jobs_source = (APP_ROOT / 'studio' / 'jobs.py').read_text(encoding='utf-8')
        self.assertIn(f"CODE_STALE_SECONDS = {install.STOP_SECONDS['worker']}\n", jobs_source)
        argv = install.service_args('worker', IMAGE, REVISION, 'disabled', '')
        self.assertEqual(argv[argv.index('--stop-timeout') + 1], '3600')

    def test_the_door_ceiling_is_read_as_the_door_reads_it(self):
        for value, ceiling in (('', 3600), ('abc', 3600), ('0', 3600), ('00', 3600), ('-5', 3600), ('9000', 9000),
                               ('010', 10), ('\u0669\u0660\u0660\u0660', 3600), (' 9000', 3600)):
            with self.subTest(value=value):
                self.assertEqual(install.door_ceiling({'RULED_ACT_MAX_SECS': value}), ceiling)
        self.assertEqual(install.door_ceiling({}), install.DOOR_CEILING_DEFAULT)

    # The door's $((10#$v)) wraps at 64 bits (bash's signed arithmetic) and keeps the result only when it is 1 or more:
    # a value of 2**63 or more is read as its signed 64-bit wrap, the default when that is 0 or less (install-1).
    WRAPPED = (('9223372036854775807', 9223372036854775807), ('9223372036854775808', 3600),
               ('9999999999999999999', 3600), ('10000000000000000000', 3600), ('18446744073709551616', 3600),
               ('18446744073709551618', 2), ('18446744073709555216', 3600), ('18446744073709560616', 9000),
               ('99999999999999999999', 7766279631452241919), ('0009223372036854775808', 3600))

    def test_a_ceiling_of_2_63_or_more_is_read_as_the_doors_64_bit_wrap(self):
        for value, ceiling in self.WRAPPED:
            with self.subTest(value=value):
                self.assertEqual(install.door_ceiling({'RULED_ACT_MAX_SECS': value}), ceiling)
        for value in ('9223372036854775808', '9999999999999999999', '18446744073709551618', '18446744073709555216'):
            with self.subTest(refused=value), self.assertRaises(install.InstallError):
                install.check_door_ceiling({'RULED_ACT_MAX_SECS': value}, 'app')
        self.assertEqual(install.check_door_ceiling({'RULED_ACT_MAX_SECS': '18446744073709560616'}, 'app'),
                         {'ceiling': 9000, 'needed': 9000})
        # past CPython's 4,300-digit int() limit the door still reads a number; so does the installer, never raising.
        # 10**5000 - 1 modulo 2**64, by modular exponentiation, then the signed wrap
        wrapped = (pow(10, 5000, 2 ** 64) - 1) % 2 ** 64
        wrapped = wrapped - 2 ** 64 if wrapped >= 2 ** 63 else wrapped
        self.assertEqual(install.door_ceiling({'RULED_ACT_MAX_SECS': '9' * 5000}),
                         wrapped if wrapped >= 1 else install.DOOR_CEILING_DEFAULT)

    def test_the_installer_and_the_doors_own_reader_agree_on_every_value(self):
        # scripts/lib/run-watched.sh's _watch_int itself, run by bash: one reading, two readers that cannot drift
        script = APP_ROOT.parent / 'scripts' / 'lib' / 'run-watched.sh'
        bash = shutil.which('bash')
        if bash is None or not script.is_file():
            self.skipTest('the door (scripts/lib/run-watched.sh) or bash is not here')
        values = ['', 'abc', '0', '00', '-5', '1', '8999', '9000', '010', ' 9000', '9000 ', '\u0669\u0660\u0660\u0660',
                  '9' * 30, '9' * 5000] + [value for value, _ in self.WRAPPED]
        listed = subprocess.run(
            [bash, '-c', '. "$1"; shift; for v in "$@"; do printf "%s\\n" "$(_watch_int "$v" 3600)"; done', '_',
             str(script), *values], capture_output=True, text=True, check=True, timeout=60).stdout.splitlines()
        self.assertEqual(len(listed), len(values))
        for value, door in zip(values, listed):
            with self.subTest(value=value[:40]):
                self.assertEqual(install.door_ceiling({'RULED_ACT_MAX_SECS': value}), int(door))

    def test_a_phase_that_stops_a_worker_refuses_a_ceiling_it_could_outrun(self):
        needed = 2 * install.STOP_SECONDS['worker'] + install.WORKER_PHASE_MARGIN
        self.assertEqual(needed, 9000)
        for phase in install.WORKER_PHASES:
            with self.subTest(phase=phase), self.assertRaises(install.InstallError) as caught:
                install.check_door_ceiling({}, phase)
            self.assertIn(f'RULED_ACT_MAX_SECS={needed} or more', str(caught.exception))
            self.assertIn('nothing was changed', str(caught.exception))
            self.assertEqual(install.check_door_ceiling({'RULED_ACT_MAX_SECS': str(needed)}, phase),
                             {'ceiling': needed, 'needed': needed})
        for phase in ('preflight', 'image', 'verify', 'passages'):
            self.assertEqual(install.check_door_ceiling({}, phase), {'ceiling': 3600, 'needed': 0})

    def test_main_refuses_before_the_phase_runs_and_says_so_in_the_receipt(self):
        import os
        import tempfile
        receipts = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__('shutil').rmtree(receipts, ignore_errors=True))
        app = mock.Mock(side_effect=AssertionError('the phase ran'))
        stdout = io.StringIO()
        with mock.patch.dict(os.environ, {'RULED_ACT_MAX_SECS': '3600'}), \
                mock.patch.dict(install.PHASES, {'app': app}), \
                mock.patch.object(install, 'check_door', return_value={'declaration_commit': 'b' * 40}), \
                mock.patch.object(install, 'check_tree', side_effect=AssertionError('the tree was read')), \
                mock.patch('sys.stdout', stdout):
            code = install.main(['--phase', 'app', '--revision', REVISION, '--receipts', str(receipts),
                                 '--coding-mode', 'disabled'])
        self.assertEqual(code, 1)
        self.assertFalse(app.called)
        self.assertIn('RULED_ACT_MAX_SECS=9000 or more', stdout.getvalue())


class CodingArgumentTests(unittest.TestCase):
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

    def test_app_names_its_coding_mode_explicitly_and_live_needs_the_authority(self):
        self.assertIn('--phase app needs an explicit --coding-mode', self.refused('--phase', 'app'))
        self.assertIn('--coding-mode live needs --authorization-ref',
                      self.refused('--phase', 'app', '--coding-mode', 'live'))
        self.assertIn('only applies to --coding-mode live',
                      self.refused('--phase', 'app', '--coding-mode', 'disabled', '--authorization-ref', RULING))
        self.assertIn("invalid choice: 'replay'", self.refused('--phase', 'app', '--coding-mode', 'replay'))
        args = self.parse('--phase', 'app', '--coding-mode', 'live', '--authorization-ref', RULING)
        self.assertEqual((args.coding_mode, args.authorization_ref, install.coding_mode(args)), ('live', RULING, 'live'))
        for phase in ('preflight', 'secrets', 'image', 'db', 'verify', 'rollback-app', 'license-note', 'operators'):
            with self.subTest(phase=phase):
                self.assertIn('--coding-mode is not used by --phase', self.refused('--phase', phase, '--coding-mode',
                                                                                   'disabled'))

    def test_an_earlier_revisions_modes_are_a_switch_backs_alone(self):
        for extra in (('--provider-mode', 'disabled'), ('--astra-mode', 'disabled'), ('--fable-mode', 'disabled'),
                      ('--interpreter-mode', 'disabled')):
            with self.subTest(extra=extra):
                self.assertIn(f'{extra[0]} is not used by --phase app',
                              self.refused('--phase', 'app', '--coding-mode', 'disabled', *extra))
        args = self.parse('--phase', 'switch-back', '--provider-mode', 'live', '--astra-mode', 'live', '--fable-mode',
                          'live', '--interpreter-mode', 'live', '--authorization-ref', RULING)
        self.assertEqual((args.provider_mode, args.astra_mode, args.fable_mode, args.interpreter_mode,
                          install.coding_mode(args)), ('live', 'live', 'live', 'live', 'disabled'))
        self.assertIn('--phase switch-back needs an explicit --provider-mode', self.refused('--phase', 'switch-back'))

    def test_a_switch_back_may_name_the_previous_pairs_coding_mode(self):
        args = self.parse('--phase', 'switch-back', '--provider-mode', 'disabled', '--coding-mode', 'live',
                          '--authorization-ref', RULING)
        self.assertEqual((args.provider_mode, args.coding_mode), ('disabled', 'live'))
        self.assertIn('--coding-mode live needs --authorization-ref',
                      self.refused('--phase', 'switch-back', '--provider-mode', 'disabled', '--coding-mode', 'live'))

    def test_the_removed_arguments_and_phase_are_unknown(self):
        for extra in (('--phase', 'app', '--coding-mode', 'live', '--authorization-ref', RULING, '--access-check'),
                      ('--phase', 'app', '--coding-mode', 'disabled', '--encounter', '5f0c2a1e-8b9d-4c3e-a7f6-01234567'
                                                                                     '89ab'),
                      ('--phase', 'app', '--coding-mode', 'disabled', '--dry-run')):
            with self.subTest(extra=extra[-1]):
                self.assertIn('unrecognized arguments', self.refused(*extra))
        self.assertIn("invalid choice: 'reassess'", self.refused('--phase', 'reassess'))
        self.assertNotIn('reassess', install.PHASES)


# --- what INSTALL.md says ------------------------------------------------------------------------------------------------

class InstallDocTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.said = ' '.join((APP_ROOT / 'ops' / 'INSTALL.md').read_text(encoding='utf-8').split())

    def test_the_document_says_what_the_installer_now_does(self):
        for phrase in ('`--coding-mode live --authorization-ref', '`CPT_STUDIO_CODING_MODE`', '`CPT_STUDIO_CODING_EFFORT`',
                       '`CPT_STUDIO_DOCUMENT_CEILING_USD`', '`CPT_STUDIO_CONCURRENT_DOCUMENTS`', '`soffice --version`',
                       f'anthropic {install.ANTHROPIC_SDK_VERSION}', '/run/cpt-studio/anthropic-credentials.env'):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.said)

    def test_it_no_longer_offers_what_was_removed(self):
        for gone in ('--access-check', '`reassess`', 'reassess_retained', 'English OCR data', 'pdftoppm',
                     'QUESTION_DOCUMENT_CEILING_USD', 'interpretation_report'):
            with self.subTest(gone=gone):
                self.assertNotIn(gone, self.said)
        self.assertIsNone(re.search(r'\| 5 \| `app` \| `--provider-mode', self.said))


if __name__ == '__main__':
    unittest.main()
