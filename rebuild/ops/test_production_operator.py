"""Offline target/refusal tests. AWS and database transports are replaced; no cloud calls."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
from unittest.mock import patch
from ops import deployment_profile as profiles
from ops import production_operator as operator
from ops import production_database_roles as roles


def profile():
    raw = json.loads(profiles.PROFILE_PATH.read_text())
    raw['database']['host'] = 'quillmd-production.abcdefghijkl.us-east-1.rds.amazonaws.com'
    raw['database']['tls']['ca_bundle_sha256'] = 'ab' * 32
    return profiles.validate(raw)


def declared():
    return {'format': 1, 'operation': 'database_roles', 'profile_sha256': profile().sha256,
            'release_sha': 'a' * 40, 'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            'actions': ['inspect', 'apply', 'verify'],
            'database_arn': 'arn:aws:rds:us-east-1:123456789012:db:quillmd-production',
            'database_resource_id': 'db-SYNTHETIC',
            'kms_key_arn': 'arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012'}


def described():
    p = profile(); d = declared()
    return {'DBInstanceArn': d['database_arn'], 'DbiResourceId': d['database_resource_id'],
            'DBInstanceIdentifier': p.database_instance, 'Endpoint': {'Address': p.database_host, 'Port': p.database_port},
            'DBName': p.database_name, 'Engine': 'postgres', 'EngineVersion': '16.10', 'DBInstanceStatus': 'available',
            'StorageEncrypted': True, 'KmsKeyId': d['kms_key_arn'], 'PubliclyAccessible': False,
            'DeletionProtection': True, 'MasterUsername': 'operator'}


class ProductionTargetTests(unittest.TestCase):
    def describe(self, row):
        result = SimpleNamespace(returncode=0, stdout=json.dumps({'DBInstances': [row]}).encode())
        with patch.object(operator.subprocess, 'run', return_value=result) as run:
            found = operator.describe_target(profile(), declared())
        args = run.call_args.args[0]
        self.assertEqual(args[:3], ['aws', 'rds', 'describe-db-instances'])
        self.assertIn('quillmd-production', args)
        return found

    def test_expected_target_passes(self):
        self.assertEqual(self.describe(described())['MasterUsername'], 'operator')

    def test_each_target_or_protection_difference_refuses(self):
        cases = [('DBInstanceArn', 'wrong'), ('DbiResourceId', 'other'), ('DBInstanceIdentifier', 'private'),
                 ('DBName', 'quillmd_fresh'), ('Engine', 'mysql'), ('EngineVersion', '17.1'),
                 ('DBInstanceStatus', 'restoring'), ('StorageEncrypted', False), ('KmsKeyId', 'other'),
                 ('PubliclyAccessible', True), ('DeletionProtection', False),
                 ('Endpoint', {'Address': 'other', 'Port': 5432}),
                 ('Endpoint', {'Address': profile().database_host, 'Port': 55438})]
        for key, value in cases:
            with self.subTest(key=key), self.assertRaises(operator.OperatorError):
                self.describe(dict(described(), **{key: value}))

    def test_current_unactivated_profile_cannot_call_aws_or_database(self):
        with patch.object(roles, 'describe_target') as aws, patch.object(roles, 'connection') as db:
            with self.assertRaises(profiles.ProfileError):
                roles.run(SimpleNamespace(action='apply'))
        aws.assert_not_called(); db.assert_not_called()

    def test_transport_forces_exact_tls_and_drops_libpq_redirects(self):
        credentials = {'username': 'operator', 'password': 'synthetic-secret-not-printed'}
        with patch('ops.service_launcher.verified_ca_bundle') as ca, patch('psycopg.connect') as connect:
            operator.connection(profile(), credentials)
        kwargs = connect.call_args.kwargs
        self.assertEqual((kwargs['host'], kwargs['hostaddr'], kwargs['service']), (profile().database_host, '', ''))
        self.assertEqual((kwargs['sslmode'], kwargs['sslrootcert']), ('verify-full', str(profile().ca_bundle)))
        self.assertEqual(kwargs['options'], '-c search_path=pg_catalog')
        ca.assert_called_once_with(profile().ca_bundle, profile().ca_bundle_sha256)

    def test_ca_refusal_prevents_connection(self):
        with patch('ops.service_launcher.verified_ca_bundle', side_effect=RuntimeError('fixed')), patch('psycopg.connect') as connect:
            with self.assertRaises(RuntimeError):
                operator.connection(profile(), {'username': 'operator', 'password': 'synthetic'})
        connect.assert_not_called()

    def test_privileged_existing_role_refuses(self):
        row = dict(rolname=profile().roles['runtime'], rolcanlogin=True, marker=roles.POLICY,
                   **{key: False for key in roles.FLAGS})
        for flag in roles.FLAGS:
            with self.subTest(flag=flag), self.assertRaises(operator.OperatorError):
                roles.check_roles([dict(row, **{flag: True})], profile())
        roles.check_roles([row], profile())
        with self.assertRaises(operator.OperatorError):
            roles.check_roles([dict(row, marker='another-policy')], profile())

    def test_non_root_cannot_reach_declaration(self):
        with patch.object(operator.os, 'geteuid', return_value=1000), patch.object(Path, 'read_bytes') as read:
            with self.assertRaisesRegex(operator.OperatorError, 'operator_root'):
                operator.authority(profile(), 'database_roles')
        read.assert_not_called()

    def test_declaration_binds_operation_profile_release_and_expiry(self):
        base = profile()
        fields = dict(base.__dict__, install_root=Path(operator.__file__).resolve().parents[2])
        local = profiles.Production(**fields)
        good = dict(declared(), profile_sha256=local.sha256)
        receipt = {'release_sha': good['release_sha'], 'profile_sha256': local.sha256}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'declaration.json'
            cases = [(good, receipt, True), (dict(good, operation='first_admin'), receipt, False),
                     (dict(good, profile_sha256='ff'*32), receipt, False),
                     (dict(good, release_sha='c'*40), receipt, False),
                     (dict(good, expires_at='2020-01-01T00:00:00Z'), receipt, False)]
            for declaration, installed, passes in cases:
                path.write_text(json.dumps(declaration))
                with patch.object(operator.os, 'geteuid', return_value=0), \
                        patch.dict(operator.os.environ, {'RULED_MUTATION_DECLARATION': str(path),
                                                       'RULED_MUTATION_DECL_COMMIT': 'd'*40}), \
                        patch.object(operator, 'private_json', return_value=installed):
                    if passes:
                        self.assertEqual(operator.authority(local, 'database_roles'), declaration)
                    else:
                        with self.assertRaises(operator.OperatorError):
                            operator.authority(local, 'database_roles')
