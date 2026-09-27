#!/usr/bin/env python3
"""The one reviewed PRODUCTION deployment profile, and the refusal of a missing or mixed one.

Every host-specific value of the production target is bound together in ONE checked-in record,
`production_profile.json` beside this file: install root, state root, configuration root,
environment file, service identity, unit names, loopback ports, database endpoint/name/roles/TLS,
the Secrets Manager name, public origins, and the data, payment, email and AI modes. Nothing here
reads the environment or a command line to choose a path or a value. A tool selects the profile by
a fixed argument in a reviewed unit file or command, and gets values only from the reviewed record.

The private synthetic system is NOT a profile in this file. Its tools (service_launcher.py,
database_roles.py, with_db_role.py, install_unit_policy.py, deploy/quillmd-fresh-*) keep their own
hard-coded constants and never call this module. `PRIVATE` lists those pinned values only so a
production record that reuses any of them is refused as MIXED: a production target that shares a
path, account, port, database or role name with the private system is the failure this prevents.

Two values cannot be known until the AWS resources exist: the RDS endpoint host name, and the
sha256 of the RDS CA bundle actually installed on the host. They are `null` in the checked-in
record. `load_production()` refuses an unactivated record (`profile_not_activated`), so production
services cannot start until a reviewed commit pins both. That is deliberate: the activation value
is reviewed like any other, never typed into an environment file.

Errors carry a fixed label only, never a path, a value or exception text.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

PROFILE_PATH = Path(__file__).resolve().with_name('production_profile.json')
MAX_PROFILE_BYTES = 64 * 1024
SURFACES = ('doctor', 'admin', 'worker')
STATE_SUBDIRECTORIES = ('files', 'mail', 'proofs', 'tmp')

# Values the PRIVATE synthetic tools pin today. Used only to refuse a mixed production record.
PRIVATE = {
    'paths': ('/opt/meddoc-pro', '/var/lib/quillmd', '/etc/quillmd', '/var/lib/quillmd-encrypted',
              '/mnt/quillmd-fresh-encrypted', '/var/lib/docker'),
    'account': 'quillmd-app',
    'unit_prefix': 'quillmd-fresh-',
    'ports': (9130, 9131, 55438, 55439),
    'database_names': ('quillmd_fresh', 'quillmd_restore', 'quillmd_ci'),
    'role_names': ('quillmd_owner', 'quillmd_runtime', 'quillmd_migrator', 'quillmd_backup',
                   'quillmd_fresh', 'restore_owner', 'quillmd_ci'),
    'origins': ('https://app.quillmd.com:9443', 'http://localhost:9130', 'http://127.0.0.1:9130'),
}

# The exact shape of the record: every key required, no other key accepted, at every level.
SHAPE = {
    'format': int, 'name': str, 'reviewed_on': str,
    'host': {'provider': str, 'region': str, 'operating_system': str, 'install_root': str,
             'state_root': str, 'configuration_root': str, 'environment_file': str, 'docker': str},
    'service': {'account': str, 'unit_prefix': str,
                'doctor': {'bind': str, 'port': int, 'workers': int},
                'admin': {'bind': str, 'port': int, 'workers': int}},
    'database': {'engine': str, 'instance_identifier': str, 'host': (str, type(None)), 'port': int,
                 'name': str,
                 'roles': {'owner': str, 'runtime': str, 'migrator': str, 'backup': str},
                 'tls': {'sslmode': str, 'ca_bundle': str, 'ca_bundle_sha256': (str, type(None))}},
    'secrets': {'application_environment': str},
    'public': {'doctor_origin': str, 'admin_origin': str},
    'modes': {'data': str, 'payment': str, 'email': str, 'email_content': str,
              'ai_provider': str, 'ai_mode': str},
}

# Fixed vocabulary. A value outside it is not a production profile.
FIXED = {
    ('host', 'provider'): ('aws',),
    ('host', 'region'): ('us-east-1', 'us-east-2'),
    ('host', 'operating_system'): ('ubuntu-24.04-lts',),
    ('host', 'docker'): ('absent',),
    ('database', 'engine'): ('aws-rds-postgresql',),
    ('modes', 'data'): ('real-patient',),
    ('modes', 'payment'): ('stripe-live',),
    # Only the transport the application already implements. An SES backend does not exist yet;
    # accepting 'ses' here would start services whose mail silently lands in the file outbox.
    ('modes', 'email'): ('resend',),
    ('modes', 'email_content'): ('no-phi-fixed-templates',),
    ('modes', 'ai_provider'): ('anthropic',),
    ('modes', 'ai_mode'): ('live',),
}

# Environment names the production renderer may write. Anything else is refused, so a private-only
# setting (preview gate credentials, preview auth) cannot be carried into production by copy.
ENVIRONMENT_NAMES = frozenset({
    'QUILLMD_DEPLOYMENT_PROFILE', 'QUILLMD_DATA_MODE', 'QUILLMD_PAYMENT_MODE',
    'QUILLMD_SECRET_KEY', 'QUILLMD_RELEASE_SHA',
    'QUILLMD_DB_NAME', 'QUILLMD_DB_USER', 'QUILLMD_DB_PASSWORD', 'QUILLMD_DB_HOST', 'QUILLMD_DB_PORT',
    'QUILLMD_HTTPS', 'QUILLMD_TRUST_PROXY',
    'QUILLMD_EMAIL_MODE', 'QUILLMD_APP_BASE_URL', 'QUILLMD_EMAIL_FROM', 'QUILLMD_EMAIL_VERIFIED_DOMAIN',
    'QUILLMD_EMAIL_ALLOWED_RECIPIENTS', 'RESEND_API_KEY',
    'QUILLMD_AI_MODE', 'QUILLMD_AI_PROVIDER', 'QUILLMD_AI_MODEL', 'QUILLMD_AI_INPUT_RATE',
    'QUILLMD_AI_OUTPUT_RATE', 'QUILLMD_AI_CACHED_RATE', 'ANTHROPIC_API_KEY',
    'DEEPGRAM_API_KEY', 'QUILLMD_DEEPGRAM_RATE_PER_MINUTE', 'QUILLMD_DEEPGRAM_RATE_PER_SECOND',
    'QUILLMD_VOICE_MAX_COST', 'QUILLMD_VOICE_MAX_MINUTES', 'QUILLMD_PROVIDER_DISCOUNT_RATE',
    'QUILLMD_WORD_RUNTIME', 'QUILLMD_WORD_MANIFEST', 'QUILLMD_WORD_MANIFEST_SHA256',
    'STRIPE_SECRET_KEY', 'STRIPE_WEBHOOK_SECRET',
    'QUILLMD_PAYER_ROLE_GRANTED', 'CPT_LICENSE_ID', 'CPT_LICENSE_EXPIRY',
})
# Private-preview mechanisms. Present in a production environment means a private file was copied.
PRIVATE_ONLY_ENVIRONMENT = ('QUILLMD_PREVIEW_AUTH_ENABLED', 'QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME',
                            'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD', 'QUILLMD_RESEND_ENV_FILE',
                            'QUILLMD_WORD_QUALIFICATION', 'OPENAI_API_KEY')

NAME = re.compile(r'[a-z][a-z0-9_]{0,62}')
ACCOUNT = re.compile(r'[a-z][a-z0-9-]{0,30}')
PREFIX = re.compile(r'[a-z][a-z0-9-]{0,40}-')
IDENTIFIER = re.compile(r'[a-z][a-z0-9-]{0,62}')
SECRET_NAME = re.compile(r'[A-Za-z0-9/_+=.@-]{1,512}')
ORIGIN = re.compile(r'https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+')
SHA256 = re.compile(r'[0-9a-f]{64}')
DATE = re.compile(r'20[0-9]{2}-[01][0-9]-[0-3][0-9]')


class ProfileError(RuntimeError):
    """Contains only a fixed label, never a path, a value or exception text."""


def require(condition, label):
    if not condition:
        raise ProfileError(label)


@dataclass(frozen=True)
class Surface:
    bind: str
    port: int
    workers: int


@dataclass(frozen=True)
class Production:
    """A validated production record. Paths are derived here, never supplied from elsewhere."""
    sha256: str
    region: str
    install_root: Path
    state_root: Path
    configuration_root: Path
    environment_file: Path
    account: str
    unit_prefix: str
    doctor: Surface
    admin: Surface
    database_instance: str
    database_host: object  # str once activated, None before
    database_port: int
    database_name: str
    roles: dict
    sslmode: str
    ca_bundle: Path
    ca_bundle_sha256: object  # str once activated, None before
    secret_name: str
    doctor_origin: str
    admin_origin: str
    data_mode: str
    payment_mode: str
    email_mode: str
    ai_provider: str
    ai_mode: str

    @property
    def app_root(self):
        return self.install_root / 'rebuild'

    @property
    def python(self):
        return self.app_root / '.venv/bin/python'

    @property
    def word_sdk_root(self):
        return self.app_root / '.word-sdk'

    @property
    def operator_directory(self):
        """Root-only operator material (for example role credentials); hidden from every service."""
        return self.configuration_root / 'operator'

    @property
    def activated(self):
        return self.database_host is not None and self.ca_bundle_sha256 is not None

    def surface(self, name):
        require(name in ('doctor', 'admin'), 'surface')
        return self.doctor if name == 'doctor' else self.admin

    def unit(self, name):
        require(name in SURFACES, 'surface')
        return self.unit_prefix + name + '.service'


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'profile_shape')
        result[key] = value
    return result


def _shape(value, shape):
    if isinstance(shape, dict):
        require(isinstance(value, dict) and set(value) == set(shape), 'profile_shape')
        for key, inner in shape.items():
            _shape(value[key], inner)
    else:
        # bool is an int subclass; a port of `true` is not a port.
        require(isinstance(value, shape) and not isinstance(value, bool), 'profile_shape')


def _path(text):
    """An absolute, normalised POSIX path of at least two components; no '..', no trailing slash."""
    require(isinstance(text, str) and text.startswith('/') and '\x00' not in text, 'profile_path')
    pure = PurePosixPath(text)
    require(str(pure) == text and '..' not in pure.parts and len(pure.parts) >= 3, 'profile_path')
    return pure


def _overlaps(first, second):
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def validate(raw, *, sha256='', require_activation=True):
    """Validate a parsed record; return a Production or raise ProfileError(label)."""
    _shape(raw, SHAPE)
    require(raw['format'] == 1 and raw['name'] == 'production', 'profile_identity')
    require(DATE.fullmatch(raw['reviewed_on']) is not None, 'profile_identity')
    for (section, key), allowed in FIXED.items():
        require(raw[section][key] in allowed, 'profile_value')

    host = raw['host']
    paths = {key: _path(host[key]) for key in ('install_root', 'state_root', 'configuration_root',
                                                'environment_file')}
    tls = raw['database']['tls']
    ca_bundle = _path(tls['ca_bundle'])
    # Secrets are rendered onto tmpfs at boot and never written to a disk.
    require(paths['environment_file'].parts[1] == 'run' and len(paths['environment_file'].parts) == 4,
            'profile_environment_file')
    require(ca_bundle.parent == paths['configuration_root'], 'profile_path')
    roots = [paths['install_root'], paths['state_root'], paths['configuration_root'],
             paths['environment_file'].parent]
    for index, first in enumerate(roots):
        for second in roots[index + 1:]:
            require(not _overlaps(first, second), 'profile_overlap')
    for mine in roots + [ca_bundle]:
        for private in PRIVATE['paths']:
            require(not _overlaps(mine, PurePosixPath(private)), 'profile_mixed')

    service = raw['service']
    require(ACCOUNT.fullmatch(service['account']) is not None
            and PREFIX.fullmatch(service['unit_prefix']) is not None, 'profile_value')
    require(service['account'] != PRIVATE['account']
            and service['unit_prefix'] != PRIVATE['unit_prefix'], 'profile_mixed')
    ports = []
    for name in ('doctor', 'admin'):
        row = service[name]
        require(row['bind'] == '127.0.0.1' and 1024 <= row['port'] <= 65535
                and 1 <= row['workers'] <= 8, 'profile_value')
        require(row['port'] not in PRIVATE['ports'], 'profile_mixed')
        ports.append(row['port'])
    require(len(set(ports)) == 2, 'profile_value')

    database = raw['database']
    region = host['region']
    require(IDENTIFIER.fullmatch(database['instance_identifier']) is not None
            and database['port'] == 5432 and NAME.fullmatch(database['name']) is not None, 'profile_value')
    require(database['name'] not in PRIVATE['database_names'], 'profile_mixed')
    endpoint = re.compile(re.escape(database['instance_identifier']) + r'\.[a-z0-9]{6,63}\.'
                          + re.escape(region) + r'\.rds\.amazonaws\.com')
    require(database['host'] is None or endpoint.fullmatch(database['host']) is not None, 'profile_database_host')
    roles = database['roles']
    require(all(NAME.fullmatch(name) is not None for name in roles.values())
            and len(set(roles.values())) == 4 and database['name'] not in roles.values(), 'profile_value')
    require(not set(roles.values()) & set(PRIVATE['role_names']), 'profile_mixed')
    require(tls['sslmode'] == 'verify-full', 'profile_value')
    require(tls['ca_bundle_sha256'] is None or SHA256.fullmatch(tls['ca_bundle_sha256']) is not None,
            'profile_value')
    require(SECRET_NAME.fullmatch(raw['secrets']['application_environment']) is not None, 'profile_value')

    public = raw['public']
    for key in ('doctor_origin', 'admin_origin'):
        require(ORIGIN.fullmatch(public[key]) is not None, 'profile_value')
        require(public[key] not in PRIVATE['origins'], 'profile_mixed')
    require(public['doctor_origin'] != public['admin_origin'], 'profile_value')

    if require_activation:
        require(database['host'] is not None and tls['ca_bundle_sha256'] is not None, 'profile_not_activated')
    modes = raw['modes']
    return Production(
        sha256=sha256, region=region,
        install_root=Path(host['install_root']), state_root=Path(host['state_root']),
        configuration_root=Path(host['configuration_root']), environment_file=Path(host['environment_file']),
        account=service['account'], unit_prefix=service['unit_prefix'],
        doctor=Surface(**service['doctor']), admin=Surface(**service['admin']),
        database_instance=database['instance_identifier'], database_host=database['host'],
        database_port=database['port'], database_name=database['name'], roles=dict(roles),
        sslmode=tls['sslmode'], ca_bundle=Path(tls['ca_bundle']), ca_bundle_sha256=tls['ca_bundle_sha256'],
        secret_name=raw['secrets']['application_environment'],
        doctor_origin=public['doctor_origin'], admin_origin=public['admin_origin'],
        data_mode=modes['data'], payment_mode=modes['payment'], email_mode=modes['email'],
        ai_provider=modes['ai_provider'], ai_mode=modes['ai_mode'])


def read_record(path=PROFILE_PATH):
    """Read the record without following a symlink; return (bytes, sha256)."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except FileNotFoundError:
        raise ProfileError('profile_missing') from None
    except OSError:
        raise ProfileError('profile_unreadable') from None
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= MAX_PROFILE_BYTES, 'profile_unreadable')
        data = os.read(fd, MAX_PROFILE_BYTES + 1)
    finally:
        os.close(fd)
    require(len(data) <= MAX_PROFILE_BYTES, 'profile_unreadable')
    return data, hashlib.sha256(data).hexdigest()


def load_production(path=PROFILE_PATH, *, require_activation=True):
    data, digest = read_record(path)
    try:
        raw = json.loads(data.decode('utf-8'), object_pairs_hook=_pairs)
    except ProfileError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise ProfileError('profile_shape') from None
    return validate(raw, sha256=digest, require_activation=require_activation)
