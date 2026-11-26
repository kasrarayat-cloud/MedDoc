"""Release 2 (R2-4's last part, R2-6, R2-7, R2-9; D-R2-17): the installer's side of the web's process - its container's
limits beside the worker's and the one-shots', the image check that loads the worker's command beside the web
application, the variable that marks the web and that no container is given, the life-cycle lines of gunicorn the kept
log holds (each one of numbers and fixed words, and a name never), and the drain's bound against the settings file.
Docker is a fake, under test_install's host guard: no test here reaches Docker, a port or a database. (A real gunicorn's
own lines are run through the same patterns in tests/test_web_process.py, which needs the test database.)

Run from cpt-studio/:  python3 -B -m unittest ops.test_install_r2web -v
"""
import io
import sys
import tarfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import REVISION, TemporaryDirectoryTest, guard_host, release_host  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'sha256:' + 'c' * 64
# The image check's command (phase_image): the web application, warmed (R2-5), and the worker's command, which loads the
# coder's SDK at its start (R2-4: the web no longer imports it, so loading the web alone would not prove it)
IMAGE_CHECK = 'import cptstudio.wsgi, studio.management.commands.run_worker'


def setUpModule():
    guard_host()  # no test here reaches Docker, sudo, nginx or a live port (test_install)


def tearDownModule():
    release_host()


def flags(argv, flag):
    return [argv[index + 1] for index, word in enumerate(argv) if word == flag]


def gunicorn_conf() -> dict:
    """deploy/gunicorn.conf.py's names, as gunicorn reads the file: executed as Python."""
    path = APP_ROOT / 'deploy' / 'gunicorn.conf.py'
    namespace = {}
    exec(compile(path.read_text(encoding='utf-8'), str(path), 'exec'), namespace)  # noqa: S102
    return namespace


def one_shot_argv() -> list:
    """The docker run arguments of a one-shot (install.oneshot), recorded: nothing runs."""
    calls = []
    with mock.patch.object(install, 'run', lambda argv, **kwargs: calls.append(argv) or mock.Mock(returncode=0)), \
            mock.patch.object(install, 'inspect', return_value=None):
        install.oneshot(IMAGE, ['manage', 'check'], b'')
    return calls[0]


def gunicorn_line(level, message, pid=1):
    """One line of gunicorn's error log as Docker keeps it (`docker logs --timestamps`): gunicorn's own time, process
    id and level (its glogging format) after Docker's time."""
    return f'2026-11-26T10:00:01.000000000Z [2026-11-26 10:00:01 +0000] [{pid}] [{level}] {message}'


class WebContainerTests(unittest.TestCase):
    """R2-6: four processes in a gibibyte, without swap; the worker and the one-shots keep their own limits."""

    def test_the_web_has_a_gibibyte_without_swap_its_pids_and_its_tmpfs(self):
        # either side of a blue/green switch
        for name, port in ((None, install.WEB_PORT), (install.INCOMING_WEB, 9151)):
            with self.subTest(name=name):
                web = install.service_args('web', IMAGE, REVISION, 'disabled', '', name=name, port=port)
                self.assertEqual((flags(web, '--memory'), flags(web, '--memory-swap'), flags(web, '--pids-limit')),
                                 (['1g'], ['1g'], ['128']))
                self.assertEqual(flags(web, '--tmpfs'), ['/tmp:rw,noexec,nosuid,nodev,size=256m'])
        self.assertEqual(install.WEB_LIMITS, ('1g', 128, '256m'))

    def test_the_worker_and_the_one_shots_keep_their_own_limits(self):
        worker = install.service_args('worker', IMAGE, REVISION, 'disabled', '')
        self.assertEqual((flags(worker, '--memory'), flags(worker, '--memory-swap'), flags(worker, '--pids-limit')),
                         (['1536m'], ['1536m'], ['256']))
        self.assertEqual(install.WORKER_LIMITS, ('1536m', 256, '1g'))
        argv = one_shot_argv()
        self.assertEqual((flags(argv, '--memory'), flags(argv, '--memory-swap'), flags(argv, '--pids-limit')),
                         (['768m'], ['768m'], ['128']))

    def test_every_process_of_the_web_fits_the_limit_with_each_hashing_a_password(self):
        # measured (R2-6): 218 MiB for the master and four workers after the largest upload, download and report, and
        # about 100 MiB more for each process hashing a sign-in's password with Argon2; a quarter of the limit is left
        # for the health check's own process and for growth
        self.assertEqual(install.WEB_LIMITS[0], '1g')
        self.assertLessEqual(218 + gunicorn_conf()['workers'] * 100, 0.75 * 1024)


class ImageCheckTests(TemporaryDirectoryTest):
    """R2-4: the image phase's smoke check loads the worker's command beside the web application - as the image's own
    user, on a read-only root, with no network - so a release whose worker cannot load the coder's SDK stops at the
    image, never at a document. The REAL phase_image, on a synthetic archive; docker is recorded."""

    def archive(self) -> bytes:
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as tar:
            for directory in ('cpt-studio', 'cpt-studio/studio', 'cpt-studio/studio/migrations', 'cpt-studio/deploy'):
                info = tarfile.TarInfo(directory)
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
            for name, data in (('cpt-studio/studio/migrations/__init__.py', b''),
                               ('cpt-studio/deploy/.dockerignore', b''),
                               ('cpt-studio/deploy/Dockerfile', b'FROM synthetic\n')):
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    def test_the_image_check_loads_the_web_application_and_the_workers_command(self):
        image = {'Id': IMAGE, 'Config': {'User': f'{install.APP_UID}:{install.APP_UID}',
                                         'Env': [f'CPT_STUDIO_RELEASE_SHA={REVISION}'],
                                         'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'app-image',
                                                    install.REVISION_LABEL: REVISION}}}
        calls = []

        def fake_docker(*args, **kwargs):
            calls.append(list(args))
            # the build and the system check pass; the load fails, so the phase stops right after it
            return SimpleNamespace(returncode=1 if '--entrypoint' in args else 0, stdout=b'', stderr=b'synthetic')
        ctx = install.Context(SimpleNamespace(phase='image', revision=REVISION), self.tmp)
        journal = {'phase': '', 'declaration': '', 'commit': '', 'lines': [], 'overflow': 0}
        with mock.patch.object(install, 'run', return_value=SimpleNamespace(returncode=0, stdout=self.archive())), \
                mock.patch.object(install, 'docker', fake_docker), \
                mock.patch.object(install, 'inspect', return_value=image), \
                mock.patch.object(install, 'JOURNAL', journal), self.assertRaises(install.InstallError) as caught:
            install.phase_image(ctx)
        self.assertIn("cannot load the web application or the worker's command", str(caught.exception))
        loads = [call for call in calls if '--entrypoint' in call]
        self.assertEqual(len(loads), 1)
        load = loads[0]
        self.assertEqual(load[load.index(IMAGE):], [IMAGE, '-c', IMAGE_CHECK])
        self.assertEqual(flags(load, '--entrypoint'), ['python'])
        self.assertEqual(flags(load, '--network'), ['none'])
        self.assertEqual(flags(load, '--cap-drop'), ['ALL'])
        self.assertIn('--read-only', load)
        self.assertNotIn('--user', load)  # the image's own user (its USER, 10150, which the phase checked above)
        # the journal names it by its fixed label, never by the command
        self.assertEqual([line for line in journal['lines'] if IMAGE_CHECK in line], [])


class NoContainerIsMarkedTheWebTests(unittest.TestCase):
    """R2-7: the web keeps its database connections because its own entry point, cptstudio/wsgi.py, sets CPT_STUDIO_WEB
    before the settings are read. The installer gives that variable to no container - so the worker and every one-shot
    keep 60 s and no check, and nothing outside the web's entry point turns it on or off."""

    def test_no_container_and_no_one_shot_is_given_the_variable(self):
        argvs = [install.service_args(role, IMAGE, REVISION, mode, 'docs/x.md', coding=coding)
                 for role in ('web', 'worker') for mode in ('disabled', 'live') for coding in ('disabled', 'live')]
        argvs += [install.runtime_env('disabled', ''), one_shot_argv()]
        for argv in argvs:
            self.assertEqual([word for word in argv if word.startswith('CPT_STUDIO_WEB=')], [])
        # and the protected environment files hold the secrets alone
        self.assertNotIn('CPT_STUDIO_WEB', install.APP_ENV_KEYS)


class KeptLifeCycleLinesTests(unittest.TestCase):
    """R2-9: the web's kept log (KEPT_LOG_FORMATS['web'], read by ids_only_lines) keeps how a worker ended - killed with
    gunicorn 23's hint, exited with a code, a worker that failed to boot, an application that failed to load - beside
    the life cycle release 1 kept; each line is numbers and fixed words, and a name or a trailing word is dropped."""

    # each as gunicorn 23 writes it (its arbiter's format strings); the shapes release 2 adds first
    KEPT = (('ERROR', 'Worker (pid:21) was sent SIGKILL! Perhaps out of memory?'),
            ('ERROR', 'Worker (pid:21) exited with code 3'), ('ERROR', 'Worker (pid:21) exited with code 3.'),
            ('ERROR', 'Worker (pid:21) exited with code 1'), ('ERROR', 'Worker (pid:21) exited with code 255.'),
            ('ERROR', 'Reason: Worker failed to boot.'), ('ERROR', 'Reason: App failed to load.'),
            ('ERROR', 'Worker (pid:21) was sent SIGTERM!'), ('ERROR', 'Worker (pid:21) was sent SIGKILL!'),
            ('INFO', 'Starting gunicorn 23.0.0'), ('INFO', 'Listening at: http://0.0.0.0:8000 (1)'),
            ('INFO', 'Using worker: sync'), ('INFO', 'Booting worker with pid: 21'), ('INFO', 'Handling signal: term'),
            ('INFO', 'Worker exiting (pid: 21)'), ('INFO', 'Shutting down: Master'), ('ERROR', 'Shutting down: Master'),
            ('CRITICAL', 'WORKER TIMEOUT (pid:21)'), ('INFO', 'Autorestarting worker after current request.'))
    # a name, a trailing word, a near miss of a kept shape, another class, and gunicorn's lines that carry a path or
    # head a traceback
    DROPPED = (('ERROR', 'Reason: Jane Doe'), ('ERROR', 'Reason: Worker failed to boot. Jane'),
               ('ERROR', 'Reason: App failed to load'), ('ERROR', 'Reason: Worker failed to boot'),
               ('ERROR', 'Worker (pid:21) exited with code 3 Jane'), ('ERROR', 'Worker (pid:21) exited with code 3..'),
               ('ERROR', 'Worker (pid:21) exited with code Jane'), ('ERROR', 'Worker (pid:Jane) exited with code 3'),
               ('ERROR', 'Worker (pid:21) was sent SIGKILL! Perhaps out of memory? Jane'),
               ('ERROR', 'Worker (pid:21) was sent SIGKILL! Jane Doe'), ('ERROR', 'Worker (pid:21) was sent Jane!'),
               ('INFO', 'Using worker: gthread'), ('ERROR', 'Exception in worker process'),
               ('ERROR', 'Error handling request /api/encounters/jane-doe'))

    def test_every_life_cycle_line_is_kept(self):
        for level, message in self.KEPT:
            line = gunicorn_line(level, message)
            with self.subTest(message=message):
                self.assertEqual(install.ids_only_lines('web', line.encode()), ([line], 0))

    def test_a_name_or_a_trailing_word_is_still_dropped(self):
        for level, message in self.DROPPED:
            with self.subTest(message=message):
                self.assertEqual(install.ids_only_lines('web', gunicorn_line(level, message).encode()), ([], 1))

    def test_the_kept_worker_class_is_the_settings_files_own_and_no_other(self):
        # a change of worker class in deploy/gunicorn.conf.py must change the kept 'Using worker: sync' with it
        def kept(word):
            return bool(install.ids_only_lines('web', gunicorn_line('INFO', f'Using worker: {word}').encode())[0])
        found = gunicorn_conf()['worker_class']
        self.assertEqual(found, 'sync')
        self.assertTrue(kept(found))
        for other in ('gthread', 'gevent', 'eventlet', 'tornado', 'uvicorn.workers.UvicornWorker'):
            self.assertFalse(kept(other), other)

    def test_the_drain_outlasts_the_longest_request_the_settings_allow(self):
        self.assertGreater(install.DRAIN_MIN_SECONDS, gunicorn_conf()['timeout'])


if __name__ == '__main__':
    unittest.main()
