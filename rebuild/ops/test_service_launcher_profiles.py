"""The private launcher refuses and accepts exactly as before; the production profile has its own gates.

`fixtures/service_launcher_private_baseline.py` is a byte-identical copy of `rebuild/ops/service_launcher.py`
as merged at 80fb591b, before profiles existed (sha256 pinned below). Every private-path check here runs
the SAME inputs through that copy and through the current launcher and requires the same outcome: the
same refusal label, or the same resulting environment, command, proof, printed report and call order.
"""
import contextlib
import copy
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from . import service_launcher as launcher
    from . import deployment_profile
    from . import source_module
except ImportError:
    import service_launcher as launcher
    import deployment_profile
    import source_module


BASELINE = Path(__file__).resolve().with_name('fixtures') / 'service_launcher_private_baseline.py'
BASELINE_SHA256 = 'bab701c41b68e20d055bead5536595396752d372ab8d4bb35bf657a1fe86489a'
baseline = source_module.load('service_launcher_private_baseline', BASELINE)
MODULES = (('baseline', baseline), ('current', launcher))
UID, GID = 321, 654
PRODUCTION_HOST = 'quillmd-production.c1a2b3c4d5e6.us-east-1.rds.amazonaws.com'
PRODUCTION_ID = 931


def status(uid=UID, gid=GID, **changes):
    row = {name: '0000000000000000' for name in launcher.CAP_FIELDS}
    row.update(Uid=f'{uid} {uid} {uid} {uid}', Gid=f'{gid} {gid} {gid} {gid}', Groups=str(gid), NoNewPrivs='1')
    row.update(changes)
    return row


def account(shell='/usr/sbin/nologin', uid=UID, gid=GID, group=GID):
    return (patch.object(launcher.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=uid, pw_gid=gid, pw_shell=shell)),
            patch.object(launcher.grp, 'getgrnam', return_value=SimpleNamespace(gr_gid=group)))


def outcome(call):
    """('accepted', value) or ('refused', label) or ('error', class name); comparable across modules."""
    try:
        return ('accepted', call())
    except (baseline.BoundaryFailure, launcher.BoundaryFailure) as exc:
        return ('refused', str(exc))
    except SystemExit as exc:
        return ('exit', exc.code)
    except Exception as exc:  # noqa: BLE001 - the class name is the compared outcome
        return ('error', type(exc).__name__)


class BaselineIdentityTests(unittest.TestCase):
    def test_baseline_is_the_pre_profile_launcher(self):
        self.assertEqual(hashlib.sha256(BASELINE.read_bytes()).hexdigest(), BASELINE_SHA256)

    def test_private_constants_are_unchanged(self):
        for name in ('ROOT', 'APP', 'STATE', 'ACCOUNT', 'CAP_FIELDS', 'DENIED', 'SURFACES'):
            with self.subTest(name=name):
                self.assertEqual(getattr(launcher, name), getattr(baseline, name))

    def test_private_units_select_no_profile(self):
        deploy = Path(__file__).resolve().parents[1] / 'deploy'
        for surface in launcher.SURFACES:
            unit = (deploy / f'quillmd-fresh-{surface}.service').read_text()
            self.assertIn(f'ops/service_launcher.py --surface {surface}\n', unit)
            self.assertNotIn('--profile', unit)


class PrivateEnvironmentDifferentialTests(unittest.TestCase):
    BASE = {'QUILLMD_SECRET_KEY': 'synthetic-test-value', 'QUILLMD_DB_PASSWORD': 'synthetic-test-value',
            'QUILLMD_DB_USER': 'quillmd_runtime', 'QUILLMD_DB_NAME': 'quillmd_fresh', 'QUILLMD_RELEASE_SHA': 'a' * 40}

    def variants(self):
        base = self.BASE
        rows = [('valid', dict(base))]
        for name in ('QUILLMD_SECRET_KEY', 'QUILLMD_DB_PASSWORD', 'QUILLMD_DB_USER', 'QUILLMD_DB_NAME', 'QUILLMD_RELEASE_SHA'):
            rows.append(('missing ' + name, {k: v for k, v in base.items() if k != name}))
            rows.append(('empty ' + name, dict(base, **{name: ''})))
        for user in ('quillmd_fresh', 'quillmd_production_runtime', 'QUILLMD_RUNTIME'):
            rows.append(('user ' + user, dict(base, QUILLMD_DB_USER=user)))
        for name in ('quillmd_production', 'quillmd_restore'):
            rows.append(('database ' + name, dict(base, QUILLMD_DB_NAME=name)))
        for release in ('A' * 40, 'a' * 39, 'a' * 41, 'development-unrecorded', 'g' * 40):
            rows.append(('release ' + release, dict(base, QUILLMD_RELEASE_SHA=release)))
        rows.append(('redirect attempts', dict(base, QUILLMD_ADMIN_SITE='1', QUILLMD_ENV_MANAGED='0',
                                               QUILLMD_STATE_DIR='/var/lib/quillmd-production', TMPDIR='/tmp',
                                               PYTHONDONTWRITEBYTECODE='0')))
        rows.append(('production declarations ignored by private', dict(
            base, QUILLMD_DEPLOYMENT_PROFILE='production', QUILLMD_DATA_MODE='real-patient',
            QUILLMD_PAYMENT_MODE='stripe-live', PGSSLMODE='verify-full', QUILLMD_DB_HOST=PRODUCTION_HOST,
            QUILLMD_DB_PORT='5432')))
        rows.append(('a whole production file', self.production_environment()))
        return rows

    @staticmethod
    def production_environment():
        return {'QUILLMD_SECRET_KEY': 'synthetic', 'QUILLMD_DB_PASSWORD': 'synthetic',
                'QUILLMD_DEPLOYMENT_PROFILE': 'production', 'QUILLMD_DB_USER': 'quillmd_production_runtime',
                'QUILLMD_DB_NAME': 'quillmd_production', 'QUILLMD_DB_HOST': PRODUCTION_HOST, 'QUILLMD_DB_PORT': '5432',
                'QUILLMD_RELEASE_SHA': 'b' * 40}

    def run_prepare(self, module, surface, environment):
        previous = os.umask(0o022)
        self.addCleanup(os.umask, previous)
        with patch.dict(os.environ, environment, clear=True):
            launcher.tempfile.tempdir = '/sentinel'
            result = outcome(lambda: module.prepare_environment(surface))
            umask = os.umask(0o022)
            os.umask(umask)
            return result, dict(os.environ), launcher.tempfile.tempdir, umask

    def test_every_environment_is_refused_or_accepted_exactly_as_before(self):
        original_tempdir = launcher.tempfile.tempdir
        self.addCleanup(setattr, launcher.tempfile, 'tempdir', original_tempdir)
        compared = 0
        for label, environment in self.variants():
            for surface in ('doctor', 'admin', 'worker', 'bogus', '/bin/sh'):
                with self.subTest(label=label, surface=surface):
                    old = self.run_prepare(baseline, surface, environment)
                    new = self.run_prepare(launcher, surface, environment)
                    self.assertEqual(new, old)
                    compared += 1
        self.assertGreater(compared, 100)

    def test_the_differential_would_notice_a_changed_rule(self):
        """Control: a launcher that accepted the production user must differ from the baseline."""
        mutant = source_module.load('service_launcher_mutant', Path(launcher.__file__))
        original = mutant.prepare_environment

        def lenient(surface):
            if os.environ.get('QUILLMD_DB_USER') == 'quillmd_production_runtime':
                os.environ['QUILLMD_DB_USER'] = 'quillmd_runtime'
            return original(surface)
        environment = dict(self.BASE, QUILLMD_DB_USER='quillmd_production_runtime')
        old = self.run_prepare(baseline, 'doctor', environment)
        with patch.object(mutant, 'prepare_environment', lenient):
            new = self.run_prepare(mutant, 'doctor', environment)
        self.assertEqual(old[0], ('refused', 'runtime_database_user'))
        self.assertNotEqual(new, old)


class PrivateIdentityAndFileDifferentialTests(unittest.TestCase):
    def test_identity_checks_match_for_every_status_and_account(self):
        statuses = [status(), status(Groups=f'{GID} 110'), status(Groups=''), status(Uid=f'{UID} {UID} 0 {UID}'),
                    status(Gid=f'{GID} {GID} {GID} 0'), status(NoNewPrivs='0'), status(CapBnd='0000000000000001'),
                    status(CapAmb='00000000000000ff'), {k: v for k, v in status().items() if k != 'CapEff'},
                    {k: v for k, v in status().items() if k != 'NoNewPrivs'}]
        accounts = [dict(), dict(shell='/bin/bash'), dict(uid=0), dict(gid=999), dict(shell='/bin/false')]
        for index, row in enumerate(statuses):
            for kind in accounts:
                with self.subTest(status=index, account=kind):
                    results = []
                    for _, module in MODULES:
                        first, second = account(**kind)
                        with first as getpwnam, second as getgrnam:
                            results.append(outcome(lambda: module.check_identity(row)))
                            self.assertEqual(getpwnam.call_args.args, ('quillmd-app',))
                            self.assertEqual(getgrnam.call_args.args, ('quillmd-app',))
                    self.assertEqual(results[1], results[0])

    def test_denial_proofs_match_for_every_errno(self):
        failures = [PermissionError(errno.EACCES, 'x'), PermissionError(errno.EPERM, 'x'), OSError(errno.EROFS, 'x'),
                    FileNotFoundError(errno.ENOENT, 'x'), OSError(errno.EIO, 'x'), OSError(errno.ELOOP, 'x')]
        for flags in (os.O_RDONLY, os.O_WRONLY, os.O_RDONLY | os.O_DIRECTORY):
            for failure in failures + [None]:
                with self.subTest(flags=flags, failure=failure):
                    results = []
                    for _, module in MODULES:
                        if failure is None:
                            with tempfile.NamedTemporaryFile() as handle:
                                results.append(outcome(lambda: module.denied_open(handle.name, os.O_RDONLY, 'label')))
                        else:
                            with patch.object(module.os, 'open', side_effect=failure):
                                results.append(outcome(lambda: module.denied_open('/synthetic', flags, 'label')))
                    self.assertEqual(results[1], results[0])

    def test_docker_socket_proofs_match(self):
        for failure in (PermissionError(errno.EACCES, 'x'), PermissionError(errno.EPERM, 'x'),
                        FileNotFoundError(errno.ENOENT, 'x'), ConnectionRefusedError(errno.ECONNREFUSED, 'x'), None):
            with self.subTest(failure=failure):
                results = []
                for _, module in MODULES:
                    with patch.object(module.socket, 'socket') as factory:
                        client = factory.return_value.__enter__.return_value
                        client.connect.side_effect = failure
                        results.append(outcome(module.denied_docker_socket))
                        client.connect.assert_called_once_with('/run/docker.sock')
                self.assertEqual(results[1], results[0])

    def test_state_directories_and_canaries_match(self):
        for mode, as_link in ((0o700, False), (0o750, False), (0o711, False), (0o700, True)):
            with self.subTest(mode=mode, link=as_link):
                results = []
                for _, module in MODULES:
                    with tempfile.TemporaryDirectory() as temp:
                        actual = Path(temp) / 'actual'
                        actual.mkdir()
                        actual.chmod(mode)
                        target = actual
                        if as_link:
                            target = Path(temp) / 'link'
                            target.symlink_to(actual)
                        results.append((outcome(lambda: module.writable_canary(target, os.getuid(), os.getgid())),
                                        sorted(p.name for p in actual.iterdir())))
                self.assertEqual(results[1], results[0])

    def test_saved_proofs_match(self):
        def scenario(module, prepare):
            with tempfile.TemporaryDirectory() as temp, patch.object(module, 'STATE', Path(temp)):
                proofs = Path(temp) / 'proofs'
                proofs.mkdir(mode=0o700)
                prepare(proofs)
                result = outcome(lambda: module.save_proof('doctor', {'passed': True, 'n': 1}))
                target = proofs / 'doctor.json'
                content = target.read_text() if target.is_file() and not target.is_symlink() else None
                mode = stat.S_IMODE(target.lstat().st_mode) if target.exists() or target.is_symlink() else None
                return result, content, mode, sorted(p.name for p in proofs.iterdir())

        def existing(mode):
            def prepare(proofs):
                (proofs / 'doctor.json').write_text('{}')
                (proofs / 'doctor.json').chmod(mode)
            return prepare
        for name, prepare in (('fresh', lambda proofs: None), ('previous 0600', existing(0o600)),
                              ('previous 0644', existing(0o644)),
                              ('symlink', lambda proofs: (proofs / 'doctor.json').symlink_to(proofs / 'other.json'))):
            with self.subTest(name=name):
                self.assertEqual(scenario(launcher, prepare), scenario(baseline, prepare))


class FakeState(type(Path())):
    """A real temporary directory whose OWN lstat reports the root-owned 0710 parent the probe requires."""
    parent_stat = None
    real_directory = None

    def lstat(self):
        if FakeState.parent_stat is not None and str(self) == FakeState.real_directory:
            return FakeState.parent_stat
        return super().lstat()


class PrivateProbeDifferentialTests(unittest.TestCase):
    def run_probe(self, module, parent):
        calls = []
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'tmp').mkdir(mode=0o700)
            FakeState.real_directory = temp
            FakeState.parent_stat = parent
            state = FakeState(temp)
            environment = dict(PrivateEnvironmentDifferentialTests.BASE)
            first, second = account()
            previous = os.umask(0o022)
            original_tempdir = launcher.tempfile.tempdir
            try:
                with first, second, patch.dict(os.environ, environment, clear=True), \
                        patch.object(module, 'STATE', state), \
                        patch.object(module, 'process_status', return_value=status()), \
                        patch.object(module, 'denied_open', side_effect=lambda path, flags, label: calls.append(
                            ('open', label, str(path).replace(temp, '<state>'), flags)) or {'denied': True, 'errno': 13}), \
                        patch.object(module, 'denied_docker_socket', side_effect=lambda: calls.append(('docker',)) or {
                            'denied': True, 'errno': 13}), \
                        patch.object(module, 'writable_canary', side_effect=lambda path, uid, gid: calls.append(
                            ('canary', str(path).replace(temp, '<state>'), uid, gid)) or {'read_write_delete': True}):
                    result = outcome(lambda: module.probe('doctor'))
            finally:
                os.umask(previous)
                launcher.tempfile.tempdir = original_tempdir
                FakeState.parent_stat = None
            if result[0] == 'accepted':
                report = dict(result[1])
                self.assertTrue(report.pop('recorded_at'))
                self.assertEqual(report.pop('pid'), os.getpid())
                report['checks'] = json.loads(json.dumps(report['checks']).replace(temp, '<state>'))
                result = ('accepted', report)
            return result, calls

    def parent(self, uid=0, gid=GID, mode=stat.S_IFDIR | 0o710):
        return os.stat_result((mode, 0, 0, 2, uid, gid, 0, 0, 0, 0))

    def test_probe_checks_the_same_paths_in_the_same_order_and_reports_the_same(self):
        old = self.run_probe(baseline, self.parent())
        new = self.run_probe(launcher, self.parent())
        self.assertEqual(old[0][0], 'accepted')
        self.assertEqual(new, old)
        self.assertEqual([c[1] for c in old[1] if c[0] == 'open'],
                         ['shared_environment', 'fresh_environment', 'operator_runtime', 'bootstrap_database_secret',
                          'synthetic_account_credentials', 'retained_credentials', 'code_write', 'launcher_write'])

    def test_probe_refuses_the_same_state_parents(self):
        for parent in (self.parent(uid=1000), self.parent(gid=1), self.parent(mode=stat.S_IFDIR | 0o750),
                       self.parent(mode=stat.S_IFREG | 0o710)):
            with self.subTest(parent=parent):
                old = self.run_probe(baseline, parent)
                new = self.run_probe(launcher, parent)
                self.assertEqual(old[0], ('refused', 'state_parent_permissions'))
                self.assertEqual(new, old)


class PrivateMainDifferentialTests(unittest.TestCase):
    def run_main(self, module, argv, probe=None, error=None):
        calls, output = [], io.StringIO()

        class ExecSentinel(BaseException):
            pass

        def execute(*args):
            calls.append(('exec', args))
            raise ExecSentinel()
        if error == 'boundary':
            error = module.BoundaryFailure('uid')  # each module recognises only its own class
        probe_patch = (patch.object(module, 'probe', side_effect=error) if error is not None else
                       patch.object(module, 'probe', side_effect=lambda surface: calls.append(('probe', surface)) or probe))
        with probe_patch, patch.object(module, 'save_proof', side_effect=lambda *args: calls.append(('proof',) + args)), \
                patch.object(module.os, 'chdir', side_effect=lambda path: calls.append(('chdir', path))), \
                patch.object(module.os, 'execv', side_effect=execute), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(io.StringIO()):
            try:
                result = module.main(argv)
            except ExecSentinel:
                result = 'exec'
            except SystemExit as exc:
                result = ('exit', exc.code)
        return result, calls, output.getvalue()

    def test_success_failure_and_argument_errors_match(self):
        report = {'passed': True, 'surface': 'x', 'pid': 1}
        for argv in (['--surface', 'doctor'], ['--surface', 'admin'], ['--surface', 'worker'], ['--surface', 'bogus'], []):
            for error in (None, 'boundary', RuntimeError('sensitive synthetic token'), KeyError('secret')):
                with self.subTest(argv=argv, error=error):
                    new = self.run_main(launcher, argv, report, error)
                    old = self.run_main(baseline, argv, report, error)
                    self.assertEqual(new, old)
                    self.assertNotIn('sensitive synthetic token', new[2])
        self.assertEqual(self.run_main(launcher, ['--surface', 'doctor'], report, 'boundary')[2],
                         '{"event": "quillmd_service_boundary", "passed": false, "surface": "doctor", "check": "uid"}\n')


class ProductionProfileFixture:
    @staticmethod
    def profile(**changes):
        raw = json.loads(deployment_profile.PROFILE_PATH.read_text())
        raw['database']['host'] = PRODUCTION_HOST
        raw['database']['tls']['ca_bundle_sha256'] = 'ab' * 32
        for path, value in changes.items():
            target = raw
            keys = path.split('.')
            for key in keys[:-1]:
                target = target[key]
            target[keys[-1]] = value
        return deployment_profile.validate(raw, sha256='cd' * 32)

    @staticmethod
    def environment(**changes):
        environment = {
            'QUILLMD_SECRET_KEY': 'synthetic-test-value', 'QUILLMD_DB_PASSWORD': 'synthetic-test-value',
            'QUILLMD_DEPLOYMENT_PROFILE': 'production', 'QUILLMD_DB_USER': 'quillmd_production_runtime',
            'QUILLMD_DB_NAME': 'quillmd_production', 'QUILLMD_DB_HOST': PRODUCTION_HOST, 'QUILLMD_DB_PORT': '5432',
            'QUILLMD_RELEASE_SHA': 'c' * 40, 'QUILLMD_EMAIL_MODE': 'resend',
            'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com', 'QUILLMD_AI_MODE': 'live',
            'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_HTTPS': '1', 'QUILLMD_TRUST_PROXY': '1'}
        for name, value in changes.items():
            if value is None:
                environment.pop(name, None)
            else:
                environment[name] = value
        return environment


class ProductionProfileSelectionTests(unittest.TestCase):
    def test_checked_in_profile_is_not_activated_so_production_refuses_before_any_probe(self):
        output = io.StringIO()
        with patch.object(launcher, 'probe_production') as probe, patch.object(launcher, 'probe') as private_probe, \
                patch.object(launcher.os, 'execv') as execute, contextlib.redirect_stdout(output):
            self.assertEqual(launcher.main(['--surface', 'doctor', '--profile', 'production']), 1)
        probe.assert_not_called()
        private_probe.assert_not_called()
        execute.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), {'event': 'quillmd_service_boundary', 'passed': False,
                                                         'surface': 'doctor', 'check': 'profile_not_activated',
                                                         'profile': 'production'})

    def test_missing_or_mixed_record_refuses_with_its_label(self):
        for error in ('profile_missing', 'profile_mixed', 'profile_shape'):
            with self.subTest(error=error):
                output = io.StringIO()
                with patch.object(deployment_profile, 'load_production',
                                  side_effect=deployment_profile.ProfileError(error)), \
                        patch.object(launcher.os, 'execv') as execute, contextlib.redirect_stdout(output):
                    self.assertEqual(launcher.main(['--surface', 'worker', '--profile', 'production']), 1)
                execute.assert_not_called()
                self.assertEqual(json.loads(output.getvalue())['check'], error)

    def test_unknown_profile_is_an_argument_error(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            launcher.main(['--surface', 'doctor', '--profile', 'staging'])

    def test_production_success_executes_the_profile_command_from_the_profile_root(self):
        profile = ProductionProfileFixture.profile()
        calls = []

        class ExecSentinel(BaseException):
            pass

        def execute(*args):
            calls.append(('exec', args))
            raise ExecSentinel()
        with patch.object(launcher, 'production_profile', return_value=profile), \
                patch.object(launcher, 'probe_production', return_value={'passed': True}), \
                patch.object(launcher, 'probe') as private_probe, \
                patch.object(launcher, 'save_proof', side_effect=lambda *args: calls.append(('proof',) + args)), \
                patch.object(launcher.os, 'chdir', side_effect=lambda path: calls.append(('chdir', path))), \
                patch.object(launcher.os, 'execv', side_effect=execute), contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(ExecSentinel):
            launcher.main(['--surface', 'admin', '--profile', 'production'])
        private_probe.assert_not_called()
        command = ['/opt/quillmd-production/rebuild/.venv/bin/python', '-m', 'gunicorn', 'quillmd.wsgi:application',
                   '--bind', '127.0.0.1:9141', '--workers', '1', '--timeout', '120']
        self.assertEqual(calls, [('proof', 'admin', {'passed': True}, Path('/var/lib/quillmd-production')),
                                 ('chdir', Path('/opt/quillmd-production/rebuild')),
                                 ('exec', (command[0], command))])


class ProductionCommandTests(unittest.TestCase):
    def test_commands_come_only_from_the_profile(self):
        profile = ProductionProfileFixture.profile()
        self.assertEqual(launcher.production_command('doctor', profile)[-6:],
                         ['--bind', '127.0.0.1:9140', '--workers', '2', '--timeout', '120'])
        self.assertEqual(launcher.production_command('worker', profile),
                         ['/opt/quillmd-production/rebuild/.venv/bin/python', '/opt/quillmd-production/rebuild/manage.py',
                          'worker'])
        for surface in ('/bin/sh', 'production', ''):
            with self.subTest(surface=surface), self.assertRaises(launcher.BoundaryFailure):
                launcher.production_command(surface, profile)
        self.assertNotEqual(launcher.production_command('doctor', profile), launcher.fixed_command('doctor'))


class ProductionEnvironmentTests(unittest.TestCase):
    def prepare(self, surface='doctor', **changes):
        profile = ProductionProfileFixture.profile()
        previous = os.umask(0o022)
        self.addCleanup(os.umask, previous)
        original_tempdir = launcher.tempfile.tempdir
        self.addCleanup(setattr, launcher.tempfile, 'tempdir', original_tempdir)
        with patch.dict(os.environ, ProductionProfileFixture.environment(**changes), clear=True):
            result = outcome(lambda: launcher.prepare_production_environment(surface, profile))
            return result, dict(os.environ)

    def test_matching_environment_is_accepted_and_profile_values_are_forced(self):
        result, environment = self.prepare('admin', QUILLMD_ADMIN_SITE='0', QUILLMD_ENV_MANAGED='0',
                                           QUILLMD_STATE_DIR='/var/lib/quillmd', TMPDIR='/tmp')
        self.assertEqual(result, ('accepted', None))
        for name, value in {'QUILLMD_ADMIN_SITE': '1', 'QUILLMD_ENV_MANAGED': '1',
                            'QUILLMD_STATE_DIR': '/var/lib/quillmd-production',
                            'TMPDIR': '/var/lib/quillmd-production/tmp', 'PYTHONDONTWRITEBYTECODE': '1',
                            'QUILLMD_DEPLOYMENT_PROFILE': 'production', 'QUILLMD_DATA_MODE': 'real-patient',
                            'QUILLMD_PAYMENT_MODE': 'stripe-live', 'PGSSLMODE': 'verify-full',
                            'PGSSLROOTCERT': '/etc/quillmd-production/rds-ca-global-bundle.pem'}.items():
            self.assertEqual(environment[name], value)
        self.assertEqual(self.prepare('doctor')[1]['QUILLMD_ADMIN_SITE'], '0')

    def test_each_mismatch_refuses_with_its_label(self):
        cases = [
            ({'QUILLMD_SECRET_KEY': None}, 'required_environment'),
            ({'QUILLMD_DB_PASSWORD': ''}, 'required_environment'),
            ({'QUILLMD_DEPLOYMENT_PROFILE': None}, 'profile_declaration'),
            ({'QUILLMD_DEPLOYMENT_PROFILE': 'private'}, 'profile_declaration'),
            ({'QUILLMD_DB_USER': 'quillmd_runtime'}, 'runtime_database_user'),
            ({'QUILLMD_DB_USER': 'quillmd_production_migrator'}, 'runtime_database_user'),
            ({'QUILLMD_DB_NAME': 'quillmd_fresh'}, 'runtime_database_name'),
            ({'QUILLMD_DB_HOST': '127.0.0.1'}, 'database_endpoint'),
            ({'QUILLMD_DB_HOST': None}, 'database_endpoint'),
            ({'QUILLMD_DB_PORT': '55438'}, 'database_endpoint'),
            ({'QUILLMD_RELEASE_SHA': 'development-unrecorded'}, 'release_identity'),
            ({'QUILLMD_DATA_MODE': 'synthetic-only'}, 'data_mode'),
            ({'QUILLMD_PAYMENT_MODE': 'stripe-test'}, 'payment_mode'),
            ({'STRIPE_SECRET_KEY': 'sk_test_synthetic'}, 'payment_mode'),
            ({'STRIPE_SECRET_KEY': 'rk_test_synthetic'}, 'payment_mode'),
            ({'STRIPE_SECRET_KEY': 'sk_live_unrestricted'}, 'payment_mode'),
            ({'QUILLMD_EMAIL_MODE': 'file'}, 'email_mode'),
            ({'QUILLMD_EMAIL_MODE': None}, 'email_mode'),
            ({'QUILLMD_APP_BASE_URL': 'https://app.quillmd.com:9443'}, 'public_origin'),
            ({'QUILLMD_APP_BASE_URL': 'http://localhost:9130'}, 'public_origin'),
            ({'QUILLMD_AI_MODE': 'fixture'}, 'ai_mode'),
            ({'QUILLMD_AI_MODE': None}, 'ai_mode'),
            ({'QUILLMD_AI_PROVIDER': 'openai'}, 'ai_mode'),
            ({'QUILLMD_HTTPS': '0'}, 'transport'),
            ({'QUILLMD_TRUST_PROXY': None}, 'transport'),
            ({'QUILLMD_PREVIEW_AUTH_ENABLED': '0'}, 'private_only_setting'),
            ({'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME': 'synthetic'}, 'private_only_setting'),
            ({'QUILLMD_WORD_QUALIFICATION': '1'}, 'private_only_setting'),
            ({'OPENAI_API_KEY': 'synthetic'}, 'private_only_setting'),
            ({'PGOPTIONS': '-c role=quillmd_production_owner'}, 'database_client_environment'),
            ({'PGSSLMODE': 'disable'}, 'database_client_environment'),
            ({'PGHOST': 'evil.example.com'}, 'database_client_environment'),
        ]
        for changes, label in cases:
            with self.subTest(changes=changes):
                self.assertEqual(self.prepare(**changes)[0], ('refused', label))
        self.assertEqual(self.prepare(STRIPE_SECRET_KEY='rk_live_synthetic')[0], ('accepted', None))
        self.assertEqual(self.prepare(QUILLMD_DATA_MODE='real-patient', QUILLMD_PAYMENT_MODE='stripe-live')[0],
                         ('accepted', None))

    def test_a_private_environment_file_cannot_start_production(self):
        private = dict(PrivateEnvironmentDifferentialTests.BASE)
        profile = ProductionProfileFixture.profile()
        with patch.dict(os.environ, private, clear=True):
            self.assertEqual(outcome(lambda: launcher.prepare_production_environment('doctor', profile)),
                             ('refused', 'profile_declaration'))

    def test_a_production_environment_file_cannot_start_the_private_units(self):
        environment = ProductionProfileFixture.environment()
        for module_name, module in MODULES:
            with self.subTest(module=module_name), patch.dict(os.environ, environment, clear=True):
                self.assertEqual(outcome(lambda: module.prepare_environment('doctor')),
                                 ('refused', 'runtime_database_user'))


class ProductionHelperTests(unittest.TestCase):
    def test_docker_socket_must_be_absent_not_merely_denied(self):
        with tempfile.TemporaryDirectory() as temp:
            path = str(Path(temp) / 'docker.sock')
            self.assertEqual(launcher.absent_socket(path, 'docker_socket'), {'absent': True})
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.addCleanup(server.close)
            server.bind(path)
            server.listen(1)
            with self.assertRaisesRegex(launcher.BoundaryFailure, '^docker_socket_accessible$'):
                launcher.absent_socket(path, 'docker_socket')
            for failure, label in ((PermissionError(errno.EACCES, 'x'), 'docker_socket_present'),
                                   (ConnectionRefusedError(errno.ECONNREFUSED, 'x'), 'docker_socket_inconclusive')):
                with patch.object(launcher.socket, 'socket') as factory:
                    factory.return_value.__enter__.return_value.connect.side_effect = failure
                    with self.subTest(label=label), self.assertRaisesRegex(launcher.BoundaryFailure, '^' + label + '$'):
                        launcher.absent_socket(path, 'docker_socket')

    def test_instance_metadata_must_be_refused_by_policy_not_by_timeout(self):
        for failure, expected in ((PermissionError(errno.EPERM, 'x'), {'denied': True, 'errno': errno.EPERM}),
                                  (socket.timeout('timed out'), 'instance_metadata_inconclusive'),
                                  (OSError(errno.ENETUNREACH, 'x'), 'instance_metadata_inconclusive'),
                                  (None, 'instance_metadata_accessible')):
            with self.subTest(failure=failure), patch.object(launcher.socket, 'socket') as factory:
                client = factory.return_value.__enter__.return_value
                client.connect.side_effect = failure
                if isinstance(expected, dict):
                    self.assertEqual(launcher.denied_instance_metadata(), expected)
                else:
                    with self.assertRaisesRegex(launcher.BoundaryFailure, '^' + expected + '$'):
                        launcher.denied_instance_metadata()
                client.connect.assert_called_once_with(('169.254.169.254', 80))
                client.send.assert_not_called()
                client.sendall.assert_not_called()

    def test_private_installation_must_be_absent(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(launcher.absent_path(Path(temp) / 'absent', 'private_installation'), {'absent': True})
            with self.assertRaisesRegex(launcher.BoundaryFailure, '^private_installation_present$'):
                launcher.absent_path(Path(temp), 'private_installation')
        with patch.object(launcher.os, 'lstat', side_effect=PermissionError(errno.EACCES, 'x')), \
                self.assertRaisesRegex(launcher.BoundaryFailure, '^private_installation_inconclusive$'):
            launcher.absent_path('/synthetic', 'private_installation')

    def test_ca_bundle_must_be_owned_unwritable_and_exactly_pinned(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = Path(temp) / 'bundle.pem'
            data = b'-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----\n'
            bundle.write_bytes(data)
            bundle.chmod(0o644)
            digest = hashlib.sha256(data).hexdigest()
            self.assertEqual(launcher.verified_ca_bundle(bundle, digest, os.getuid()),
                             {'sha256': digest, 'bytes': len(data)})
            refusals = [(bundle, 'ab' * 32, os.getuid()),        # wrong bytes
                        (bundle, digest, 0 if os.getuid() else 1),  # wrong owner
                        (Path(temp) / 'absent.pem', digest, os.getuid())]
            link = Path(temp) / 'link.pem'
            link.symlink_to(bundle)
            refusals.append((link, digest, os.getuid()))
            for path, expected, owner in refusals:
                with self.subTest(path=path.name, owner=owner), \
                        self.assertRaisesRegex(launcher.BoundaryFailure, '^database_ca_bundle$'):
                    launcher.verified_ca_bundle(path, expected, owner)
            bundle.chmod(0o664)
            with self.assertRaisesRegex(launcher.BoundaryFailure, '^database_ca_bundle$'):
                launcher.verified_ca_bundle(bundle, digest, os.getuid())
            bundle.chmod(0o644)
            bundle.write_bytes(b'')
            with self.assertRaisesRegex(launcher.BoundaryFailure, '^database_ca_bundle$'):
                launcher.verified_ca_bundle(bundle, hashlib.sha256(b'').hexdigest(), os.getuid())

    def test_state_root_must_be_a_mounted_root_owned_0710_parent(self):
        profile = ProductionProfileFixture.profile()

        def parent(uid=0, gid=GID, mode=stat.S_IFDIR | 0o710):
            return os.stat_result((mode, 0, 0, 2, uid, gid, 0, 0, 0, 0))
        with patch.object(type(profile.state_root), 'lstat', return_value=parent()), \
                patch.object(launcher.os.path, 'ismount', return_value=True):
            self.assertIsNone(launcher.production_state_parent(profile, GID))
        with patch.object(type(profile.state_root), 'lstat', return_value=parent()), \
                patch.object(launcher.os.path, 'ismount', return_value=False), \
                self.assertRaisesRegex(launcher.BoundaryFailure, '^state_volume_not_mounted$'):
            launcher.production_state_parent(profile, GID)
        for bad in (parent(uid=1000), parent(gid=1), parent(mode=stat.S_IFDIR | 0o750)):
            with self.subTest(bad=bad), patch.object(type(profile.state_root), 'lstat', return_value=bad), \
                    patch.object(launcher.os.path, 'ismount', return_value=True), \
                    self.assertRaisesRegex(launcher.BoundaryFailure, '^state_parent_permissions$'):
                launcher.production_state_parent(profile, GID)


class ProductionProbeTests(unittest.TestCase):
    def run_probe(self, identity_number=PRODUCTION_ID, **patches):
        profile = ProductionProfileFixture.profile()
        calls = []
        first, second = account(uid=identity_number, gid=identity_number, group=identity_number)
        previous = os.umask(0o022)
        self.addCleanup(os.umask, previous)
        original_tempdir = launcher.tempfile.tempdir
        self.addCleanup(setattr, launcher.tempfile, 'tempdir', original_tempdir)
        defaults = {
            'process_status': lambda: status(identity_number, identity_number),
            'production_state_parent': lambda profile, gid: calls.append(('state_parent', gid)),
            'denied_open': lambda path, flags, label: calls.append(('open', label, str(path), flags)) or {'denied': True},
            'absent_socket': lambda path, label: calls.append(('absent_socket', label, path)) or {'absent': True},
            'denied_instance_metadata': lambda: calls.append(('imds',)) or {'denied': True},
            'absent_path': lambda path, label: calls.append(('absent_path', label, str(path))) or {'absent': True},
            'verified_ca_bundle': lambda path, digest: calls.append(('ca', str(path), digest)) or {'sha256': digest},
            'writable_canary': lambda path, uid, gid: calls.append(('canary', str(path))) or {'read_write_delete': True},
        }
        defaults.update(patches)
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / 'tmp').mkdir()
            with first, second, patch.dict(os.environ, ProductionProfileFixture.environment(), clear=True), \
                    contextlib.ExitStack() as stack:
                for name, replacement in defaults.items():
                    stack.enter_context(patch.object(launcher, name, side_effect=replacement))
                # The probe compares gettempdir() with the profile's tmp; point it at a real directory.
                stack.enter_context(patch.object(launcher.tempfile, 'gettempdir',
                                                 return_value='/var/lib/quillmd-production/tmp'))
                return outcome(lambda: launcher.probe_production('worker', profile)), calls

    def test_probe_runs_every_production_check_and_reports_the_profile(self):
        result, calls = self.run_probe()
        self.assertEqual(result[0], 'accepted')
        report = result[1]
        self.assertEqual((report['profile'], report['profile_sha256'], report['surface']), ('production', 'cd' * 32, 'worker'))
        self.assertEqual(report['database'], {'host': PRODUCTION_HOST, 'name': 'quillmd_production',
                                              'role': 'quillmd_production_runtime', 'sslmode': 'verify-full'})
        self.assertEqual(calls[0], ('state_parent', PRODUCTION_ID))
        self.assertEqual([c[1] for c in calls if c[0] == 'open'],
                         ['environment_file', 'operator_configuration', 'code_write', 'launcher_write', 'profile_write'])
        self.assertIn(('open', 'environment_file', '/run/quillmd-production/application.env', os.O_RDONLY), calls)
        self.assertEqual([c[2] for c in calls if c[0] == 'absent_socket'], ['/run/docker.sock', '/var/run/docker.sock'])
        self.assertIn(('imds',), calls)
        self.assertIn(('absent_path', 'private_installation', '/opt/meddoc-pro'), calls)
        self.assertIn(('ca', '/etc/quillmd-production/rds-ca-global-bundle.pem', 'ab' * 32), calls)
        self.assertEqual([c[1] for c in calls if c[0] == 'canary'],
                         ['/var/lib/quillmd-production/' + name for name in ('files', 'mail', 'proofs', 'tmp')])
        self.assertEqual(report['provider_calls'], 0)

    def test_any_failed_production_check_refuses(self):
        def fail(label):
            def raiser(*args):
                raise launcher.BoundaryFailure(label)
            return raiser
        for name, label in (('absent_socket', 'docker_socket_present'),
                            ('denied_instance_metadata', 'instance_metadata_accessible'),
                            ('absent_path', 'private_installation_present'),
                            ('verified_ca_bundle', 'database_ca_bundle'),
                            ('production_state_parent', 'state_volume_not_mounted'),
                            ('denied_open', 'environment_file_accessible')):
            with self.subTest(name=name):
                self.assertEqual(self.run_probe(**{name: fail(label)})[0], ('refused', label))

    def test_operator_identity_refuses(self):
        self.assertEqual(self.run_probe(process_status=lambda: status(PRODUCTION_ID, PRODUCTION_ID,
                                                                      Groups=f'{PRODUCTION_ID} 110'))[0],
                         ('refused', 'supplementary_groups'))

    def test_a_consistent_identity_with_another_number_refuses(self):
        # check_identity accepts it (UID, GID and group agree); only the profile's fixed number differs.
        self.assertEqual(self.run_probe(identity_number=PRODUCTION_ID + 1)[0], ('refused', 'service_identity_number'))
        self.assertEqual(self.run_probe(identity_number=PRODUCTION_ID)[0][0], 'accepted')

if __name__ == '__main__':
    unittest.main()
