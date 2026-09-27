"""Fixed production target and declared operator authority; no secret values in errors."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from datetime import datetime, timezone

from . import deployment_profile


class OperatorError(RuntimeError):
    pass


def require(condition, label):
    if not condition:
        raise OperatorError(label)


def private_json(path):
    path = Path(path)
    info = path.lstat()
    require(path.is_absolute() and path.resolve() == path and stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o077
            and info.st_nlink == 1 and info.st_size < 65536, 'operator_file')
    return json.loads(path.read_bytes())


def authority(profile, operation):
    """The ruled-mutation wrapper establishes committed declaration provenance.

    Its JSON declaration also binds this exact installed release/profile, target
    and operation. Bootstrap receipt is root-only; a caller environment alone
    cannot claim a different installed release. No production operation here is
    authorized by the checked-in example.
    """
    require(os.geteuid() == 0, 'operator_root')
    require(re.fullmatch(r'[a-f0-9]{40}', os.environ.get('RULED_MUTATION_DECL_COMMIT', '')), 'declaration_commit')
    path = os.environ.get('RULED_MUTATION_DECLARATION', '')
    require(path, 'declaration_missing')
    declaration = json.loads(Path(path).read_bytes())
    require(declaration.get('format') == 1 and declaration.get('operation') == operation
            and declaration.get('profile_sha256') == profile.sha256, 'declaration_scope')
    release = declaration.get('release_sha', '')
    require(re.fullmatch(r'[a-f0-9]{40}', release), 'declaration_release')
    require(Path(__file__).resolve().parents[1] == profile.app_root, 'installed_source')
    receipt = private_json('/var/lib/quillmd-bootstrap/receipt.json')
    require(receipt.get('release_sha') == release and receipt.get('profile_sha256') == profile.sha256,
            'installed_release')
    expires = datetime.fromisoformat(declaration.get('expires_at', '').replace('Z', '+00:00'))
    require(expires.tzinfo is not None and expires > datetime.now(timezone.utc), 'declaration_expired')
    return declaration


def describe_target(profile, declaration):
    result = subprocess.run(['aws', 'rds', 'describe-db-instances', '--region', profile.region,
                             '--db-instance-identifier', profile.database_instance, '--output', 'json', '--no-cli-pager'],
                            capture_output=True, timeout=30)
    require(result.returncode == 0, 'rds_describe')
    rows = json.loads(result.stdout).get('DBInstances', [])
    require(len(rows) == 1, 'rds_count')
    row = rows[0]
    arn = declaration.get('database_arn', '')
    require(re.fullmatch(r'arn:aws:rds:' + re.escape(profile.region) + r':[0-9]{12}:db:'
                         + re.escape(profile.database_instance), arn), 'rds_arn')
    require(row.get('DBInstanceArn') == arn and row.get('DbiResourceId') == declaration.get('database_resource_id')
            and bool(row.get('DbiResourceId')), 'rds_identity')
    require(row.get('DBInstanceIdentifier') == profile.database_instance
            and row.get('Endpoint', {}).get('Address') == profile.database_host
            and row.get('Endpoint', {}).get('Port') == profile.database_port
            and row.get('DBName') == profile.database_name, 'rds_endpoint')
    require(row.get('Engine') == 'postgres' and row.get('EngineVersion', '').split('.')[0] == '16'
            and row.get('DBInstanceStatus') == 'available', 'rds_engine')
    key = declaration.get('kms_key_arn', '')
    require(re.fullmatch(r'arn:aws:kms:' + re.escape(profile.region) + r':[0-9]{12}:key/[a-f0-9-]{36}', key)
            and row.get('StorageEncrypted') is True and row.get('KmsKeyId') == key
            and row.get('PubliclyAccessible') is False and row.get('DeletionProtection') is True, 'rds_protection')
    return row


def connection(profile, credentials):
    import psycopg
    from psycopg.rows import dict_row
    from .service_launcher import verified_ca_bundle
    verified_ca_bundle(profile.ca_bundle, profile.ca_bundle_sha256)
    require(set(credentials) == {'username', 'password'} and isinstance(credentials['username'], str)
            and credentials['username'] and isinstance(credentials['password'], str) and credentials['password'], 'credentials')
    return psycopg.connect(host=profile.database_host, hostaddr='', port=profile.database_port,
                           dbname=profile.database_name, user=credentials['username'], password=credentials['password'],
                           sslmode='verify-full', sslrootcert=str(profile.ca_bundle), service='',
                           options='-c search_path=pg_catalog', connect_timeout=10,
                           target_session_attrs='read-write', row_factory=dict_row)
