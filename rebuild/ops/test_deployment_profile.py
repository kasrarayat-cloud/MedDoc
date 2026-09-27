"""The production profile is one fixed record; a missing, unactivated, malformed or mixed one refuses."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

try:
    from . import deployment_profile as profile
except ImportError:
    import deployment_profile as profile


RECORD = json.loads(profile.PROFILE_PATH.read_text())
HOST = 'quillmd-production.c1a2b3c4d5e6.us-east-1.rds.amazonaws.com'
CA_SHA = 'ab' * 32


def activated(**changes):
    raw = copy.deepcopy(RECORD)
    raw['database']['host'] = HOST
    raw['database']['tls']['ca_bundle_sha256'] = CA_SHA
    for path, value in changes.items():
        target = raw
        keys = path.split('.')
        for key in keys[:-1]:
            target = target[key]
        target[keys[-1]] = value
    return raw


class CheckedInRecordTests(unittest.TestCase):
    def test_checked_in_record_is_valid_but_not_activated(self):
        loaded = profile.load_production(require_activation=False)
        self.assertFalse(loaded.activated)
        self.assertIsNone(loaded.database_host)
        self.assertIsNone(loaded.ca_bundle_sha256)
        with self.assertRaisesRegex(profile.ProfileError, '^profile_not_activated$'):
            profile.load_production()

    def test_checked_in_values_are_the_reviewed_production_namespace(self):
        loaded = profile.load_production(require_activation=False)
        self.assertEqual(loaded.install_root, Path('/opt/quillmd-production'))
        self.assertEqual(loaded.app_root, Path('/opt/quillmd-production/rebuild'))
        self.assertEqual(loaded.state_root, Path('/var/lib/quillmd-production'))
        self.assertEqual(loaded.environment_file, Path('/run/quillmd-production/application.env'))
        self.assertEqual(loaded.account, 'quillmd-production-app')
        self.assertEqual(loaded.uid, 931)
        self.assertEqual((loaded.doctor.port, loaded.admin.port), (9140, 9141))
        self.assertEqual((loaded.doctor.bind, loaded.admin.bind), ('127.0.0.1', '127.0.0.1'))
        self.assertEqual(loaded.database_name, 'quillmd_production')
        self.assertEqual(loaded.roles, {'owner': 'quillmd_production_owner', 'runtime': 'quillmd_production_runtime',
                                        'migrator': 'quillmd_production_migrator', 'backup': 'quillmd_production_backup'})
        self.assertEqual(loaded.sslmode, 'verify-full')
        self.assertEqual((loaded.doctor_origin, loaded.admin_origin), ('https://app.quillmd.com', 'https://admin.quillmd.com'))
        self.assertEqual((loaded.data_mode, loaded.payment_mode, loaded.email_mode, loaded.ai_provider, loaded.ai_mode),
                         ('real-patient', 'stripe-live', 'resend', 'anthropic', 'live'))
        self.assertEqual([loaded.unit(name) for name in profile.SURFACES],
                         ['quillmd-production-doctor.service', 'quillmd-production-admin.service',
                          'quillmd-production-worker.service'])

    def test_record_hash_is_reported(self):
        data = profile.PROFILE_PATH.read_bytes()
        import hashlib
        self.assertEqual(profile.load_production(require_activation=False).sha256, hashlib.sha256(data).hexdigest())


class ActivationTests(unittest.TestCase):
    def test_both_activation_values_are_required(self):
        loaded = profile.validate(activated())
        self.assertTrue(loaded.activated)
        self.assertEqual(loaded.database_host, HOST)
        for missing in ('database.host', 'database.tls.ca_bundle_sha256'):
            with self.subTest(missing=missing), self.assertRaisesRegex(profile.ProfileError, '^profile_not_activated$'):
                profile.validate(activated(**{missing: None}))

    def test_database_host_must_be_this_instance_in_this_region(self):
        for host in ('evil.example.com', 'quillmd-production.c1a2b3c4d5e6.us-east-2.rds.amazonaws.com',
                     'other-db.c1a2b3c4d5e6.us-east-1.rds.amazonaws.com', 'quillmd-production.us-east-1.rds.amazonaws.com',
                     HOST + '.evil.example.com', '127.0.0.1', ''):
            with self.subTest(host=host), self.assertRaisesRegex(profile.ProfileError, '^profile_database_host$'):
                profile.validate(activated(**{'database.host': host}))

    def test_ca_hash_must_be_a_lowercase_sha256(self):
        for value in ('AB' * 32, 'ab' * 31, 'zz' * 32):
            with self.subTest(value=value), self.assertRaisesRegex(profile.ProfileError, '^profile_value$'):
                profile.validate(activated(**{'database.tls.ca_bundle_sha256': value}))


class MixedProfileTests(unittest.TestCase):
    def test_every_private_value_is_refused_as_mixed(self):
        cases = (
            ('host.state_root', '/var/lib/quillmd'),
            ('host.install_root', '/opt/meddoc-pro'),
            ('host.configuration_root', '/etc/quillmd'),
            ('service.account', 'quillmd-app'),
            ('service.uid', 988),
            ('service.unit_prefix', 'quillmd-fresh-'),
            ('service.doctor.port', 9130),
            ('service.admin.port', 9131),
            ('service.doctor.port', 55438),
            ('database.name', 'quillmd_fresh'),
            ('database.roles.runtime', 'quillmd_runtime'),
            ('database.roles.owner', 'quillmd_owner'),
        )
        for path, value in cases:
            with self.subTest(path=path), self.assertRaisesRegex(profile.ProfileError, '^profile_mixed$'):
                raw = activated(**{path: value})
                if path == 'host.configuration_root':
                    raw['database']['tls']['ca_bundle'] = value + '/rds-ca-global-bundle.pem'
                profile.validate(raw)

    def test_nested_inside_or_around_a_private_path_is_mixed(self):
        for path, value in (('host.install_root', '/opt/meddoc-pro/production'),
                            ('host.state_root', '/var/lib/quillmd/production'),
                            ('host.state_root', '/var/lib/docker/quillmd')):
            with self.subTest(value=value), self.assertRaisesRegex(profile.ProfileError, '^profile_mixed$'):
                profile.validate(activated(**{path: value}))

    def test_production_roots_may_not_overlap_each_other(self):
        with self.assertRaisesRegex(profile.ProfileError, '^profile_overlap$'):
            profile.validate(activated(**{'host.state_root': '/opt/quillmd-production/state'}))

    def test_private_values_in_modes_are_refused(self):
        for path, value in (('modes.data', 'synthetic-only'), ('modes.payment', 'stripe-test'),
                            ('modes.email', 'file'), ('modes.email', 'ses'), ('modes.ai_mode', 'fixture'),
                            ('modes.ai_provider', 'openai'), ('host.docker', 'present'),
                            ('database.tls.sslmode', 'require'), ('service.doctor.bind', '0.0.0.0'),
                            ('database.engine', 'docker-postgresql'), ('host.region', 'eu-west-1'),
                            ('database.port', 55438), ('service.uid', 0), ('service.uid', 1000),
                            ('service.uid', 65534), ('service.uid', 999)):
            with self.subTest(path=path, value=value), self.assertRaises(profile.ProfileError):
                profile.validate(activated(**{path: value}))

    def test_preview_or_plain_origin_is_refused(self):
        for value in ('https://app.quillmd.com:9443', 'http://app.quillmd.com', 'https://app.quillmd.com/',
                      'https://app.quillmd.com/console', 'app.quillmd.com'):
            with self.subTest(value=value), self.assertRaises(profile.ProfileError):
                profile.validate(activated(**{'public.doctor_origin': value}))
        with self.assertRaisesRegex(profile.ProfileError, '^profile_value$'):
            profile.validate(activated(**{'public.admin_origin': 'https://app.quillmd.com'}))


class ShapeTests(unittest.TestCase):
    def test_extra_or_missing_keys_refuse_at_every_level(self):
        for mutate in (lambda raw: raw.update(extra=1), lambda raw: raw.pop('modes'),
                       lambda raw: raw['host'].update(ssh_port=22), lambda raw: raw['database']['roles'].pop('backup'),
                       lambda raw: raw['database']['tls'].update(sslcert='/x/y/z')):
            raw = activated()
            mutate(raw)
            with self.assertRaisesRegex(profile.ProfileError, '^profile_shape$'):
                profile.validate(raw)

    def test_wrong_types_refuse_including_bool_for_int(self):
        for path, value in (('service.doctor.port', '9140'), ('service.doctor.port', True),
                            ('service.doctor.workers', 2.0), ('host.state_root', None), ('format', '1')):
            with self.subTest(path=path, value=value), self.assertRaisesRegex(profile.ProfileError, '^profile_shape$'):
                profile.validate(activated(**{path: value}))

    def test_paths_must_be_absolute_normalised_and_deep_enough(self):
        for value in ('var/lib/quillmd-production', '/var/lib/quillmd-production/', '/var/lib/../quillmd-production',
                      '/var//lib/quillmd-production', '/srv', '/'):
            with self.subTest(value=value), self.assertRaisesRegex(profile.ProfileError, '^profile_path$'):
                profile.validate(activated(**{'host.state_root': value}))

    def test_a_path_not_in_normal_form_is_refused_before_the_mixed_check(self):
        # PurePosixPath keeps a leading '//', so '//var/lib/quillmd' did not overlap '/var/lib/quillmd' and a
        # record naming the private state root that way was accepted. Every non-normal spelling is profile_path.
        cases = [
            ('host.state_root', '//var/lib/quillmd'),
            ('host.install_root', '//opt/meddoc-pro'),
            ('host.state_root', '//var/lib/quillmd-production'),
            ('host.environment_file', '//run/quillmd-production/application.env'),
            ('host.state_root', '/var/./lib/quillmd'),
            ('host.state_root', '/./var/lib/quillmd-production'),
            ('host.state_root', '/var/lib/quillmd-production/.'),
            ('host.state_root', '/var/lib/quillmd-production/../quillmd'),
            ('host.state_root', '/var/lib/quillmd/'),
            ('host.state_root', '/var//lib/quillmd'),
            ('host.install_root', '/opt//quillmd-production'),
        ]
        for path, value in cases:
            with self.subTest(path=path, value=value), self.assertRaisesRegex(profile.ProfileError, '^profile_path$'):
                profile.validate(activated(**{path: value}))
        for value in ('//etc/quillmd', '//etc/quillmd-production'):
            with self.subTest(configuration_root=value), \
                    self.assertRaisesRegex(profile.ProfileError, '^profile_path$'):
                profile.validate(activated(**{'host.configuration_root': value,
                                              'database.tls.ca_bundle': value + '/rds-ca-global-bundle.pem'}))
        # The normal spelling of a private path is still refused as mixed, and the record itself still validates.
        with self.assertRaisesRegex(profile.ProfileError, '^profile_mixed$'):
            profile.validate(activated(**{'host.state_root': '/var/lib/quillmd'}))
        self.assertEqual(str(profile.validate(activated()).state_root), RECORD['host']['state_root'])

    def test_environment_file_must_be_on_run_tmpfs(self):
        for value in ('/etc/quillmd-production-env/application.env', '/run/application.env',
                      '/run/quillmd-production/nested/application.env'):
            with self.subTest(value=value), self.assertRaises(profile.ProfileError):
                profile.validate(activated(**{'host.environment_file': value}))

    def test_ca_bundle_must_live_in_the_configuration_root(self):
        with self.assertRaisesRegex(profile.ProfileError, '^profile_path$'):
            profile.validate(activated(**{'database.tls.ca_bundle': '/opt/quillmd-production/rds.pem'}))

    def test_duplicate_keys_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            text = json.dumps(activated())
            path.write_text(text[:-1] + ', "name": "production"}')
            with self.assertRaisesRegex(profile.ProfileError, '^profile_shape$'):
                profile.load_production(path)


class RecordFileTests(unittest.TestCase):
    def test_missing_symlinked_directory_or_oversized_record_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(profile.ProfileError, '^profile_missing$'):
                profile.load_production(root / 'absent.json')
            real = root / 'real.json'
            real.write_text(json.dumps(activated()))
            self.assertTrue(profile.load_production(real).activated)
            link = root / 'link.json'
            link.symlink_to(real)
            with self.assertRaisesRegex(profile.ProfileError, '^profile_unreadable$'):
                profile.load_production(link)
            with self.assertRaisesRegex(profile.ProfileError, '^profile_unreadable$'):
                profile.load_production(root)
            big = root / 'big.json'
            big.write_bytes(b' ' * (profile.MAX_PROFILE_BYTES + 1))
            with self.assertRaisesRegex(profile.ProfileError, '^profile_unreadable$'):
                profile.load_production(big)
            broken = root / 'broken.json'
            broken.write_text('{"format": 1,')
            with self.assertRaisesRegex(profile.ProfileError, '^profile_shape$'):
                profile.load_production(broken)

    def test_error_text_never_carries_the_path_or_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'synthetic-secret-name.json'
            path.write_text(json.dumps(activated(**{'database.host': 'synthetic-secret.example.com'})))
            with self.assertRaises(profile.ProfileError) as caught:
                profile.load_production(path)
            self.assertNotIn('synthetic-secret', str(caught.exception))


class EnvironmentVocabularyTests(unittest.TestCase):
    def test_private_only_names_are_not_renderable(self):
        self.assertFalse(set(profile.PRIVATE_ONLY_ENVIRONMENT) & profile.ENVIRONMENT_NAMES)
        for name in ('QUILLMD_ADMIN_SITE', 'QUILLMD_ENV_MANAGED', 'QUILLMD_STATE_DIR', 'TMPDIR', 'PGOPTIONS',
                     'PGSSLMODE', 'QUILLMD_PREVIEW_AUTH_ENABLED', 'OPENAI_API_KEY'):
            self.assertNotIn(name, profile.ENVIRONMENT_NAMES)


if __name__ == '__main__':
    unittest.main()
