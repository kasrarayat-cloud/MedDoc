"""The role wrapper's private target is unchanged; its production target comes only from the profile."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import deployment_profile
    from . import source_module
except ImportError:
    import deployment_profile
    import source_module

OPS = Path(__file__).resolve().parent
if str(OPS) not in sys.path:  # the wrapper imports its siblings as top-level modules, as when run
    sys.path.insert(0, str(OPS))
CURRENT = OPS / 'with_db_role.py'
BASELINE = OPS / 'fixtures' / 'with_db_role_private_baseline.py'
BASELINE_SHA256 = 'a077d5b49fb233115da392b6e2f84a8cebdf525169ce001140de2fb681a93515'
HOST = 'quillmd-production.c1a2b3c4d5e6.us-east-1.rds.amazonaws.com'
REPORTED = ('QUILLMD_DB_NAME', 'QUILLMD_DB_USER', 'QUILLMD_DB_PASSWORD', 'QUILLMD_DB_HOST', 'QUILLMD_DB_PORT',
            'PGOPTIONS', 'PGSSLMODE', 'PGSSLROOTCERT', 'PGHOST', 'QUILLMD_DEPLOYMENT_PROFILE')
MANAGE = ('import json, os, sys\n'
          'print(json.dumps({"argv": sys.argv[1:], "env": {k: os.environ.get(k) for k in ' + repr(REPORTED) + '}}))\n')


class Workspace:
    def __init__(self, credentials):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.credentials = self.root / 'roles.json'
        self.credentials.write_text(json.dumps(credentials))
        self.credentials.chmod(0o600)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'manage.py').write_text(MANAGE)

    def run(self, script, *arguments, env=None):
        environment = dict(os.environ if env is None else env, PYTHONPATH=str(OPS))
        return subprocess.run([sys.executable, '-B', str(script), '--credentials', str(self.credentials),
                               '--source', str(self.source), *arguments], capture_output=True, text=True,
                              timeout=60, env=environment)

    def close(self):
        self.directory.cleanup()


PRIVATE_CREDENTIALS = {'database': 'quillmd_fresh', 'roles': {
    'migrator': {'name': 'synthetic_migrator', 'password': 'synthetic-migrator-password'},
    'backup': {'name': 'synthetic_backup', 'password': 'synthetic-backup-password'}}}
PRODUCTION_CREDENTIALS = {'profile': 'production', 'database': 'quillmd_production', 'roles': {
    'migrator': {'name': 'quillmd_production_migrator', 'password': 'synthetic-migrator-password'},
    'backup': {'name': 'quillmd_production_backup', 'password': 'synthetic-backup-password'}}}


def comparable(result):
    last = result.stderr.strip().splitlines()[-1:] if result.returncode else []
    return result.returncode, result.stdout, last


class PrivateWrapperDifferentialTests(unittest.TestCase):
    def test_baseline_is_the_pre_profile_wrapper(self):
        self.assertEqual(hashlib.sha256(BASELINE.read_bytes()).hexdigest(), BASELINE_SHA256)

    def test_private_target_is_identical_for_every_input(self):
        cases = [
            (PRIVATE_CREDENTIALS, ['--role', 'migrator', '--', 'migrate', '--noinput']),
            (PRIVATE_CREDENTIALS, ['--role', 'backup', '--', 'check']),
            (PRIVATE_CREDENTIALS, ['--', 'showmigrations']),
            (PRIVATE_CREDENTIALS, ['--role', 'migrator', '--', 'import_terminology', '--system', 'ICD-10-CM']),
            (PRIVATE_CREDENTIALS, ['--role', 'migrator', '--', 'shell']),
            (PRIVATE_CREDENTIALS, ['--role', 'migrator', '--', 'worker']),
            (PRIVATE_CREDENTIALS, ['--role', 'migrator']),
            (dict(PRIVATE_CREDENTIALS, database='quillmd_production'), ['--', 'migrate']),
            (PRODUCTION_CREDENTIALS, ['--', 'migrate']),
            ({'database': 'quillmd_fresh', 'roles': {}}, ['--', 'migrate']),
        ]
        environment = dict(os.environ, PGHOST='operator-value', PGSSLMODE='prefer')
        for credentials, arguments in cases:
            with self.subTest(credentials=credentials.get('database'), arguments=arguments):
                workspace = Workspace(credentials)
                try:
                    old = workspace.run(BASELINE, *arguments, env=environment)
                    new = workspace.run(CURRENT, *arguments, env=environment)
                finally:
                    workspace.close()
                self.assertEqual(comparable(new), comparable(old))
        workspace = Workspace(PRIVATE_CREDENTIALS)
        try:
            result = workspace.run(CURRENT, '--role', 'migrator', '--', 'migrate', env=environment)
        finally:
            workspace.close()
        env = json.loads(result.stdout)['env']
        self.assertEqual((env['QUILLMD_DB_NAME'], env['QUILLMD_DB_HOST'], env['QUILLMD_DB_PORT'], env['PGOPTIONS']),
                         ('quillmd_fresh', '127.0.0.1', '55438', '-c role=quillmd_owner'))


class ProductionWrapperTests(unittest.TestCase):
    def test_checked_in_unactivated_profile_refuses_before_running_anything(self):
        workspace = Workspace(PRODUCTION_CREDENTIALS)
        try:
            result = workspace.run(CURRENT, '--profile', 'production', '--', 'migrate')
        finally:
            workspace.close()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, '')
        self.assertIn('Production profile refused: profile_not_activated', result.stderr)

    def activated(self):
        raw = json.loads(deployment_profile.PROFILE_PATH.read_text())
        raw['database']['host'] = HOST
        raw['database']['tls']['ca_bundle_sha256'] = 'ab' * 32
        return deployment_profile.validate(raw)

    def run_in_process(self, credentials, arguments, environment):
        module = source_module.load('with_db_role_under_test', CURRENT)
        workspace = Workspace(credentials)
        captured = {}

        class ExecSentinel(BaseException):
            pass

        def execute(path, argv, env):
            captured.update(path=path, argv=argv, env=env)
            raise ExecSentinel()
        try:
            argv = ['with_db_role.py', '--credentials', str(workspace.credentials), '--source', str(workspace.source),
                    '--profile', 'production', *arguments]
            with patch.object(sys, 'argv', argv), patch.dict(os.environ, environment, clear=True), \
                    patch.dict(sys.modules, {'deployment_profile': deployment_profile}), \
                    patch.object(deployment_profile, 'load_production', return_value=self.activated()), \
                    patch.object(module.os, 'execve', side_effect=execute):
                try:
                    module.main()
                except ExecSentinel:
                    return 'executed', captured
                except RuntimeError as exc:
                    return 'refused', str(exc)
        finally:
            workspace.close()

    def test_activated_profile_supplies_every_connection_value(self):
        outcome, captured = self.run_in_process(PRODUCTION_CREDENTIALS, ['--role', 'migrator', '--', 'migrate'],
                                                {'PATH': '/usr/bin:/bin', 'PGHOST': 'evil.example.com',
                                                 'PGSSLMODE': 'disable', 'PGSERVICE': 'other',
                                                 'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_SECRET_KEY': 'synthetic'})
        self.assertEqual(outcome, 'executed')
        env = captured['env']
        self.assertEqual({name: env.get(name) for name in (
            'QUILLMD_DB_NAME', 'QUILLMD_DB_USER', 'QUILLMD_DB_HOST', 'QUILLMD_DB_PORT', 'PGSSLMODE', 'PGSSLROOTCERT',
            'PGOPTIONS', 'QUILLMD_DEPLOYMENT_PROFILE')}, {
            'QUILLMD_DB_NAME': 'quillmd_production', 'QUILLMD_DB_USER': 'quillmd_production_migrator',
            'QUILLMD_DB_HOST': HOST, 'QUILLMD_DB_PORT': '5432', 'PGSSLMODE': 'verify-full',
            'PGSSLROOTCERT': '/etc/quillmd-production/rds-ca-global-bundle.pem',
            'PGOPTIONS': '-c role=quillmd_production_owner', 'QUILLMD_DEPLOYMENT_PROFILE': 'production'})
        self.assertNotIn('PGHOST', env)
        self.assertNotIn('PGSERVICE', env)
        self.assertEqual(env['QUILLMD_SECRET_KEY'], 'synthetic')
        self.assertEqual(captured['argv'][-1], 'migrate')
        backup = self.run_in_process(PRODUCTION_CREDENTIALS, ['--role', 'backup', '--', 'check'], {'PATH': '/usr/bin'})
        self.assertEqual(backup[1]['env']['PGOPTIONS'], '')
        self.assertEqual(backup[1]['env']['QUILLMD_DB_USER'], 'quillmd_production_backup')

    def test_credentials_for_another_target_refuse(self):
        cases = [
            PRIVATE_CREDENTIALS,
            {k: v for k, v in PRODUCTION_CREDENTIALS.items() if k != 'profile'},
            dict(PRODUCTION_CREDENTIALS, database='quillmd_fresh'),
            dict(PRODUCTION_CREDENTIALS, roles={
                'migrator': {'name': 'quillmd_migrator', 'password': 'x' * 40},
                'backup': {'name': 'quillmd_production_backup', 'password': 'x' * 40}}),
            dict(PRODUCTION_CREDENTIALS, roles={'migrator': PRODUCTION_CREDENTIALS['roles']['migrator']}),
        ]
        for credentials in cases:
            with self.subTest(credentials=credentials):
                outcome, message = self.run_in_process(credentials, ['--', 'migrate'], {'PATH': '/usr/bin'})
                self.assertEqual(outcome, 'refused')
                self.assertIn('Wrapper credentials', message)

    def test_command_allowlist_still_applies_in_production(self):
        outcome, message = self.run_in_process(PRODUCTION_CREDENTIALS, ['--', 'shell'], {'PATH': '/usr/bin'})
        self.assertEqual(outcome, 'refused')
        self.assertIn('Only migration, check and verified terminology import commands are allowed', message)


if __name__ == '__main__':
    unittest.main()
