"""The production deploy files agree with the one profile, and their tools refuse what they must.

Nothing here provisions or changes a host: the bootstrap script is exercised only in its dry run
(and, as a non-root user, its refusal to execute), the environment renderer and the artifact
installer only against temporary directories.
"""
import ast
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import importlib.util
import io
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import deployment_profile
    from . import release_artifact
    from . import render_production_environment as renderer
    from . import service_launcher as launcher
except ImportError:
    import deployment_profile
    import release_artifact
    import render_production_environment as renderer
    import service_launcher as launcher

REBUILD = Path(__file__).resolve().parents[1]
PRODUCTION = REBUILD / 'deploy' / 'production'
PROFILE = deployment_profile.load_production(require_activation=False)
COST_DOCUMENT = REBUILD.parent / 'docs' / 'rebuild' / 'v1' / 'production-cost.md'
GENERATION = REBUILD / 'core' / 'generation.py'
HOST = 'quillmd-production.c1a2b3c4d5e6.us-east-1.rds.amazonaws.com'


def activated():
    raw = json.loads(deployment_profile.PROFILE_PATH.read_text())
    raw['database']['host'] = HOST
    raw['database']['tls']['ca_bundle_sha256'] = 'ab' * 32
    return deployment_profile.validate(raw, sha256='cd' * 32)


def unit(name):
    """Parse a unit into {section: {key: [values]}} (repeated keys keep every value)."""
    sections, current = {}, None
    for line in (PRODUCTION / name).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            current = sections.setdefault(line[1:-1], {})
            continue
        key, _, value = line.partition('=')
        current.setdefault(key, []).append(value)
    return sections


def one(section, key):
    values = section.get(key, [])
    assert len(values) == 1, (key, values)
    return values[0]


METADATA_ADDRESSES = (ipaddress.ip_address('169.254.169.254'), ipaddress.ip_address('fd00:ec2::254'))
# systemd.resource-control(5): the names IPAddressAllow=/IPAddressDeny= accept besides addresses and prefixes.
SYSTEMD_IP_NAMES = {'any': ('0.0.0.0/0', '::/0'), 'localhost': ('127.0.0.0/8', '::1/128'),
                    'link-local': ('169.254.0.0/16', 'fe80::/64'), 'multicast': ('224.0.0.0/4', 'ff00::/8')}


class UnreadableUnit(AssertionError):
    """A unit line this check cannot read exactly as systemd would; failing is the safe answer."""


def unit_assignments(path):
    """(section, key, value) in file order, read as systemd reads a unit file: '#' and ';' comments, a trailing
    backslash continues the line (comment lines inside a continuation are skipped), whitespace around '=' stripped."""
    rows, section, carried = [], None, None
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if carried is not None and stripped.startswith(('#', ';')):
            continue
        line = stripped if carried is None else carried + ' ' + stripped
        if line.endswith('\\'):
            carried = line[:-1].rstrip()
            continue
        carried = None
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
            continue
        key, equals, value = line.partition('=')
        if not equals:
            raise UnreadableUnit(f'{path.name}: a line that is neither a section, a comment nor an assignment')
        rows.append((section, key.strip(), value.strip()))
    if carried is not None:
        raise UnreadableUnit(f'{path.name}: a continuation at the end of the file')
    return rows


def drop_ins(path):
    """Every drop-in systemd would read for this unit from the directory it is shipped in, in the order it applies
    them (by file name across all directories; a name used twice cannot be ordered here, so it fails)."""
    name = path.name
    stem, _, kind = name.rpartition('.')
    folders = [kind + '.d']
    parts = stem.split('-')
    folders += ['-'.join(parts[:index]) + '-.' + kind + '.d' for index in range(1, len(parts))]
    folders.append(name + '.d')
    found = {}
    for folder in folders:
        for conf in sorted((path.parent / folder).glob('*.conf')):
            if conf.name in found:
                raise UnreadableUnit(f'{name}: drop-in {conf.name} exists in two directories')
            found[conf.name] = conf
    return [found[key] for key in sorted(found)]


def ip_access_lists(path):
    """(allow, deny) as systemd builds them for this unit: each assignment appends, an empty one resets that list."""
    lists = {'IPAddressAllow': [], 'IPAddressDeny': []}
    for source in [path] + drop_ins(path):
        for section, key, value in unit_assignments(source):
            if key not in lists:
                continue
            if section != 'Service':
                raise UnreadableUnit(f'{source.name}: {key} in [{section}]')
            if not value:
                lists[key] = []
                continue
            for word in value.split():
                if word in SYSTEMD_IP_NAMES:
                    lists[key] += [ipaddress.ip_network(net) for net in SYSTEMD_IP_NAMES[word]]
                    continue
                address, slash, prefix = word.partition('/')
                try:
                    parsed = ipaddress.ip_address(address)
                except ValueError:
                    raise UnreadableUnit(f'{source.name}: {key} entry {word!r}') from None
                if slash and not (prefix.isdigit() and int(prefix) <= parsed.max_prefixlen):
                    raise UnreadableUnit(f'{source.name}: {key} entry {word!r}')
                length = int(prefix) if slash else parsed.max_prefixlen
                lists[key].append(ipaddress.ip_network(f'{address}/{length}', strict=False))
    return lists['IPAddressAllow'], lists['IPAddressDeny']


def ip_reachable(address, allow, deny):
    """systemd's rule: granted if the address matches the allow list; otherwise denied if it matches the deny
    list; otherwise granted."""
    if any(address in network for network in allow if network.version == address.version):
        return True
    return not any(address in network for network in deny if network.version == address.version)


class UnitProfileAgreementTests(unittest.TestCase):
    def test_application_units_are_bound_to_the_profile(self):
        state = PROFILE.state_root
        for surface in ('doctor', 'admin', 'worker'):
            with self.subTest(surface=surface):
                parsed = unit(PROFILE.unit(surface))
                service, header = parsed['Service'], parsed['Unit']
                self.assertEqual(one(service, 'User'), PROFILE.account)
                self.assertEqual(one(service, 'Group'), PROFILE.account)
                self.assertEqual(one(service, 'ExecStart'),
                                 f'{PROFILE.python} {PROFILE.app_root}/ops/service_launcher.py '
                                 f'--surface {surface} --profile production')
                self.assertEqual(one(service, 'WorkingDirectory'), str(PROFILE.app_root))
                self.assertEqual(one(service, 'EnvironmentFile'), str(PROFILE.environment_file))
                self.assertEqual(one(service, 'ReadWritePaths').split(),
                                 [str(state / name) for name in deployment_profile.STATE_SUBDIRECTORIES])
                hidden = one(service, 'InaccessiblePaths').split()
                for path in ('-/run/docker.sock', '-/var/run/docker.sock', str(PROFILE.environment_file.parent),
                             str(PROFILE.operator_directory), str(PROFILE.configuration_root / 'ingress')):
                    self.assertIn(path, hidden)
                self.assertIn('169.254.169.254/32', one(service, 'IPAddressDeny').split())
                self.assertEqual(one(header, 'RequiresMountsFor'), str(state))
                self.assertIn((PROFILE.unit_prefix + 'environment.service'), one(header, 'Requires').split())
                self.assertIn((PROFILE.unit_prefix + 'environment.service'), one(header, 'After').split())
                for key, value in (('MemorySwapMax', '0'), ('LimitCORE', '0'), ('NoNewPrivileges', 'true'),
                                   ('CapabilityBoundingSet', ''), ('AmbientCapabilities', ''),
                                   ('SupplementaryGroups', ''), ('ProtectSystem', 'strict'), ('PrivateTmp', 'true'),
                                   ('ProtectHome', 'true'), ('UMask', '0077')):
                    self.assertEqual(one(service, key), value, key)
                environment = dict(item.split('=', 1) for item in service['Environment'])
                self.assertEqual(environment['QUILLMD_ADMIN_SITE'], '1' if surface == 'admin' else '0')
                self.assertEqual(environment['TMPDIR'], str(state / 'tmp'))

    def test_only_declared_root_operators_can_reach_either_metadata_address(self):
        # Judged the way systemd applies IPAddressAllow=/IPAddressDeny= (systemd.resource-control(5)), over the unit
        # and every drop-in this package ships. The heartbeat unit has no launcher behind it: this is its only guard.
        units = sorted(PRODUCTION.glob('*.service'))
        expected = {'environment', 'doctor', 'admin', 'worker', 'heartbeat', 'operations-status'}
        self.assertEqual({path.name for path in units}, {PROFILE.unit_prefix + name + '.service' for name in expected})
        for path in units:
            allow, deny = ip_access_lists(path)
            with self.subTest(unit=path.name):
                if path.name in {PROFILE.unit_prefix + name + '.service' for name in ('environment', 'operations-status')}:
                    # Root operators read the configured secret or assume backup metadata read roles.
                    self.assertEqual(one(unit(path)['Service'], 'User'), 'root')
                    self.assertTrue(ip_reachable(METADATA_ADDRESSES[0], allow, deny))
                else:
                    for address in METADATA_ADDRESSES:
                        self.assertFalse(ip_reachable(address, allow, deny), f'{path.name} can reach {address}')

    def test_the_access_list_evaluator_reads_units_the_way_systemd_does(self):
        head = '[Unit]\nDescription=x\n\n[Service]\nExecStart=/bin/true\n'
        reachable = {  # unit body after [Service] -> can a process in it reach 169.254.169.254 / fd00:ec2::254?
            'IPAddressDeny=169.254.169.254/32 fd00:ec2::254/128\n': (False, False),
            'IPAddressDeny=169.254.169.254 fd00:ec2::254\n': (False, False),          # bare address = host prefix
            'IPAddressDeny=any\n': (False, False),                                      # stricter
            'IPAddressDeny=link-local\nIPAddressDeny=fd00::/8\n': (False, False),
            'IPAddressDeny=169.254.169.254/32\nIPAddressDeny=fd00:ec2::254/128\n': (False, False),
            'IPAddressDeny = 169.254.169.254/32 \\\n  fd00:ec2::254/128\n': (False, False),  # continuation
            'IPAddressDeny=169.254.169.254/32 fd00:ec2::254/128\nIPAddressAllow=any\n': (True, True),   # allow wins
            'IPAddressDeny=169.254.169.254/32 fd00:ec2::254/128\nIPAddressAllow=link-local fd00::/8\n': (True, True),
            'IPAddressDeny=169.254.169.254/32 fd00:ec2::254/128\nIPAddressAllow=169.254.169.254\n': (True, False),
            'IPAddressDeny=169.254.169.254/32 fd00:ec2::254/128\nIPAddressDeny=\n': (True, True),      # reset
            'IPAddressDeny=\nIPAddressDeny=169.254.169.254/32 fd00:ec2::254/128\n': (False, False),
            'IPAddressAllow=any\nIPAddressAllow=\nIPAddressDeny=any\n': (False, False),              # allow reset
            'IPAddressDeny=169.254.169.254/32\n': (False, True),
            '# IPAddressDeny=any\n': (True, True),
            'IPAddressDeny=169.254.0.0/16 fd00:ec2::/64\n': (False, False),
            'IPAddressDeny=169.254.169.0/24 ::/0\n': (False, False),
        }
        for body, expected in reachable.items():
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'probe.service'
                path.write_text(head + body)
                allow, deny = ip_access_lists(path)
                self.assertEqual(tuple(ip_reachable(address, allow, deny) for address in METADATA_ADDRESSES), expected)
        refused = ('IPAddressDeny=169.254.169.254/255.255.255.255\n',  # systemd takes a prefix length only
                   'IPAddressDeny="169.254.169.254"\n', 'IPAddressDeny=%I\n', 'IPAddressDeny=imds\n')
        for body in refused + ('',):
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / 'probe.service'
                path.write_text(head + body if body else '[Unit]\nIPAddressAllow=any\n[Service]\nExecStart=/bin/true\n')
                with self.assertRaises(UnreadableUnit):
                    ip_access_lists(path)
        # Drop-ins this package ships are read after the unit, by file name, across every directory systemd uses.
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path = directory / 'quillmd-production-heartbeat.service'
            path.write_text(head + 'IPAddressDeny=169.254.169.254/32 fd00:ec2::254/128\n')
            self.assertEqual([ip_reachable(a, *ip_access_lists(path)) for a in METADATA_ADDRESSES], [False, False])
            for folder, name, body in (('quillmd-production-.service.d', '10-a.conf', 'IPAddressAllow=any\n'),
                                       ('quillmd-production-heartbeat.service.d', '20-b.conf', 'IPAddressAllow=\n')):
                (directory / folder).mkdir()
                (directory / folder / name).write_text('[Service]\n' + body)
                allowed = [ip_reachable(a, *ip_access_lists(path)) for a in METADATA_ADDRESSES]
                self.assertEqual(allowed, [True, True] if name == '10-a.conf' else [False, False], folder)

    def test_environment_unit_renders_onto_the_profile_tmpfs_path(self):
        parsed = unit((PROFILE.unit_prefix + 'environment.service'))
        service = parsed['Service']
        self.assertEqual(one(service, 'ExecStart'),
                         f'/usr/bin/python3 -B -E -s {PROFILE.app_root}/ops/render_production_environment.py --execute')
        self.assertEqual(one(service, 'User'), 'root')
        self.assertEqual(one(service, 'RuntimeDirectory'), PROFILE.environment_file.parent.name)
        self.assertEqual(Path('/run') / one(service, 'RuntimeDirectory'), PROFILE.environment_file.parent)
        self.assertEqual(one(service, 'RuntimeDirectoryMode'), '0700')
        self.assertNotIn('RuntimeDirectoryPreserve', service)  # secrets vanish when the unit stops
        self.assertEqual(set(one(parsed['Unit'], 'Before').split()),
                         {PROFILE.unit(name) for name in ('doctor', 'admin', 'worker')})

    def test_heartbeat_reads_its_url_as_a_credential_and_checks_the_profile_ports(self):
        service = unit(PROFILE.unit_prefix + 'heartbeat.service')['Service']
        self.assertEqual(one(service, 'DynamicUser'), 'yes')
        self.assertEqual(one(service, 'LoadCredential'), f'heartbeat-url:{PROFILE.operator_directory}/heartbeat-url')
        self.assertEqual(one(service, 'ExecStart'), f'{PROFILE.app_root}/deploy/production/quillmd-production-heartbeat.sh')
        timer = unit(PROFILE.unit_prefix + 'heartbeat.timer')['Timer']
        self.assertEqual(one(timer, 'Unit'), PROFILE.unit_prefix + 'heartbeat.service')
        script = (PRODUCTION / 'quillmd-production-heartbeat.sh').read_text()
        self.assertIn(f'check {PROFILE.doctor.port} {PROFILE.doctor_origin.removeprefix("https://")}\n', script)
        self.assertIn(f'check {PROFILE.admin.port} {PROFILE.admin_origin.removeprefix("https://")}\n', script)

    def test_no_production_file_names_a_private_path_identity_or_docker(self):
        forbidden = re.compile(r'/opt/meddoc-pro|quillmd-fresh|\bquillmd-app\b|/var/lib/quillmd(?![-\w])|\.runtime'
                               r'|docker\.service|55438|\b9130\b|\b9131\b|/etc/quillmd(?![-\w])')
        for path in sorted(PRODUCTION.iterdir()):
            if path.name == 'bootstrap-host.sh':
                continue  # it names /opt/meddoc-pro and Docker only to refuse them; checked separately below
            with self.subTest(path=path.name):
                self.assertIsNone(forbidden.search(path.read_text()), path.name)

    def test_nginx_routes_each_host_to_its_profile_port_without_request_logs(self):
        text = (PRODUCTION / 'nginx-quillmd-production.conf').read_text()
        blocks = re.split(r'\nserver \{', text)[1:]
        self.assertEqual(len(blocks), 3)
        default, doctor, admin = blocks
        self.assertIn('default_server', default)
        self.assertIn(f'proxy_pass http://127.0.0.1:{PROFILE.doctor.port};', default)
        self.assertIn('return 444;', default)
        self.assertIn(f'server_name {PROFILE.doctor_origin.removeprefix("https://")};', doctor)
        self.assertIn(f'proxy_pass http://127.0.0.1:{PROFILE.doctor.port};', doctor)
        self.assertIn(f'server_name {PROFILE.admin_origin.removeprefix("https://")};', admin)
        self.assertIn(f'proxy_pass http://127.0.0.1:{PROFILE.admin.port};', admin)
        self.assertIn(f'include {PROFILE.configuration_root}/ingress/admin-allow.conf;', admin)
        self.assertNotIn('admin-allow', doctor)
        for block in blocks:
            self.assertIn('access_log off;', block)
            self.assertIn('listen 8443 ssl', block)
        self.assertNotRegex(text, r'listen\s+(80|443)\b')
        self.assertIn('real_ip_recursive on;', text)


class EnvironmentRendererTests(unittest.TestCase):
    VALID = {'QUILLMD_DEPLOYMENT_PROFILE': 'production', 'QUILLMD_SECRET_KEY': 'synthetic-Value_123',
             'QUILLMD_DB_PASSWORD': 'synthetic', 'QUILLMD_DB_HOST': HOST}

    def test_valid_secret_renders_sorted_single_quoted_lines(self):
        values = renderer.parse(json.dumps(self.VALID))
        self.assertEqual(renderer.render(values).decode().splitlines(),
                         ["QUILLMD_DB_HOST='" + HOST + "'", "QUILLMD_DB_PASSWORD='synthetic'",
                          "QUILLMD_DEPLOYMENT_PROFILE='production'", "QUILLMD_SECRET_KEY='synthetic-Value_123'"])

    def test_declared_v1_feature_flags_are_explicit_booleans_and_replay_stays_private(self):
        flags = ('QUILLMD_WM_NARRATIVE', 'QUILLMD_MAPPING_ASSISTANCE', 'QUILLMD_MAPPING_ASSISTANCE_LIVE')
        self.assertTrue(all(name not in renderer.parse(json.dumps(self.VALID)) for name in flags))
        for name in flags:
            for value in ('0', '1'):
                self.assertEqual(renderer.parse(json.dumps({**self.VALID, name: value}))[name], value)
            for value in ('true', 'yes', '2'):
                with self.subTest(name=name, value=value), self.assertRaisesRegex(renderer.RenderError, 'feature_flag_value'):
                    renderer.parse(json.dumps({**self.VALID, name: value}))
        for name in ('QUILLMD_AI_REPLAY_DIR', 'ANTHROPIC_BASE_URL'):
            with self.subTest(name=name), self.assertRaisesRegex(renderer.RenderError, 'secret_name'):
                renderer.parse(json.dumps({**self.VALID, name: '/synthetic-untrusted'}))

    def test_production_voice_settings_are_renderable_and_privacy_cannot_be_disabled(self):
        for name,values in (('QUILLMD_DEEPGRAM_MIP_OPT_OUT',('true',)),
                            ('QUILLMD_DEEPGRAM_SMART_FORMAT',('true','false'))):
            for value in values:
                self.assertEqual(renderer.parse(json.dumps({**self.VALID,name:value}))[name],value)
        for name,value,error in (('QUILLMD_DEEPGRAM_MIP_OPT_OUT','false','voice_privacy_value'),
                                 ('QUILLMD_DEEPGRAM_MIP_OPT_OUT','1','voice_privacy_value'),
                                 ('QUILLMD_DEEPGRAM_SMART_FORMAT','1','voice_format_value')):
            with self.subTest(name=name,value=value),self.assertRaisesRegex(renderer.RenderError,error):
                renderer.parse(json.dumps({**self.VALID,name:value}))

    def test_unsafe_or_unknown_secrets_refuse(self):
        cases = [
            ('[]', 'secret_shape'), ('{}', 'secret_shape'), ('not json', 'secret_shape'),
            ('{"QUILLMD_DEPLOYMENT_PROFILE": "production", "QUILLMD_DEPLOYMENT_PROFILE": "private"}', 'secret_shape'),
            (json.dumps(dict(self.VALID, QUILLMD_PREVIEW_AUTH_ENABLED='0')), 'secret_name'),
            (json.dumps(dict(self.VALID, QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD='x')), 'secret_name'),
            (json.dumps(dict(self.VALID, PGOPTIONS='-c role=x')), 'secret_name'),
            (json.dumps(dict(self.VALID, QUILLMD_STATE_DIR='/tmp')), 'secret_name'),
            (json.dumps(dict(self.VALID, QUILLMD_SECRET_KEY="a'b")), 'secret_value'),
            (json.dumps(dict(self.VALID, QUILLMD_SECRET_KEY='a\\b')), 'secret_value'),
            (json.dumps(dict(self.VALID, QUILLMD_SECRET_KEY='a\nQUILLMD_DB_HOST=evil')), 'secret_value'),
            (json.dumps(dict(self.VALID, QUILLMD_SECRET_KEY='a\x00b')), 'secret_value'),
            (json.dumps(dict(self.VALID, QUILLMD_SECRET_KEY=' padded')), 'secret_value'),
            (json.dumps(dict(self.VALID, QUILLMD_SECRET_KEY='')), 'secret_value'),
            (json.dumps(dict(self.VALID, QUILLMD_SECRET_KEY=12345)), 'secret_value'),
            (json.dumps(dict(self.VALID, QUILLMD_SECRET_KEY='x' * 8193)), 'secret_value'),
            (json.dumps({k: v for k, v in self.VALID.items() if k != 'QUILLMD_DEPLOYMENT_PROFILE'}), 'secret_profile'),
            (json.dumps(dict(self.VALID, QUILLMD_DEPLOYMENT_PROFILE='private')), 'secret_profile'),
            (' ' * (renderer.MAX_SECRET_BYTES + 1), 'secret_shape'),
        ]
        for text, label in cases:
            with self.subTest(label=label, text=text[:60]), self.assertRaisesRegex(renderer.RenderError, '^' + label + '$'):
                renderer.parse(text)

    def test_write_is_private_atomic_and_refuses_a_foreign_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / 'run'
            directory.mkdir(mode=0o700)
            target = directory / 'application.env'
            digest = renderer.write(target, b"A='1'\n", owner=os.getuid())
            self.assertEqual(target.read_bytes(), b"A='1'\n")
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(digest, hashlib.sha256(b"A='1'\n").hexdigest())
            renderer.write(target, b"A='2'\n", owner=os.getuid())
            self.assertEqual(sorted(p.name for p in directory.iterdir()), ['application.env'])
            with self.assertRaisesRegex(renderer.RenderError, '^environment_directory$'):
                renderer.write(target, b'x', owner=0 if os.getuid() else 1)
            directory.chmod(0o750)
            with self.assertRaisesRegex(renderer.RenderError, '^environment_directory$'):
                renderer.write(target, b'x', owner=os.getuid())
            directory.chmod(0o700)
            target.unlink()
            target.symlink_to(Path(temp) / 'elsewhere')
            with self.assertRaisesRegex(renderer.RenderError, '^environment_file$'):
                renderer.write(target, b'x', owner=os.getuid())
            self.assertFalse((Path(temp) / 'elsewhere').exists())

    def test_fetch_uses_the_profile_secret_and_region_only(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(self.VALID).encode() + b'\n', stderr=b'')
        text = renderer.fetch(PROFILE, runner)
        self.assertEqual(json.loads(text), self.VALID)
        command, kwargs = calls[0]
        self.assertEqual(command, ['/usr/local/bin/aws', 'secretsmanager', 'get-secret-value', '--region', 'us-east-1',
                                   '--secret-id', 'quillmd-production/application-environment', '--query',
                                   'SecretString', '--output', 'text'])
        self.assertNotIn('ANTHROPIC_API_KEY', kwargs['env'])
        failing = lambda command, **kwargs: subprocess.CompletedProcess(command, 255, stdout=b'', stderr=b'secret text')
        with self.assertRaisesRegex(renderer.RenderError, '^secret_fetch$'):
            renderer.fetch(PROFILE, failing)

    def test_main_refuses_unactivated_profile_and_non_root_and_never_prints_values(self):
        output, errors = io.StringIO(), io.StringIO()
        with patch('sys.stdout', output), patch('sys.stderr', errors):
            self.assertEqual(renderer.main(['--execute']), 1)
        self.assertEqual(json.loads(errors.getvalue()), {'rendered': False, 'refused': 'profile_not_activated'})
        if os.geteuid() == 0:
            self.skipTest('the non-root refusal cannot be shown as root')
        runner = lambda *args, **kwargs: self.fail('fetched as non-root')
        errors = io.StringIO()
        with patch.object(renderer.deployment_profile, 'load_production', return_value=activated()), \
                patch('sys.stderr', errors), patch('sys.stdout', io.StringIO()):
            self.assertEqual(renderer.main(['--execute'], runner=runner), 1)
        self.assertEqual(json.loads(errors.getvalue()), {'rendered': False, 'refused': 'not_root'})


def build_artifact(directory, sha, members, comment=None):
    """A git-archive-shaped tar.gz: global pax comment = commit id, every member under quillmd-<sha>/."""
    path = Path(directory) / f'quillmd-{sha}.tar.gz'
    with tarfile.open(path, 'w:gz', format=tarfile.PAX_FORMAT,
                      pax_headers={'comment': sha if comment is None else comment}) as archive:
        for name, data in members.items():
            info = tarfile.TarInfo(name)
            if isinstance(data, tuple):  # ('symlink', target)
                info.type, info.linkname = tarfile.SYMTYPE, data[1]
                archive.addfile(info)
            else:
                info.size, info.mode = len(data), 0o664
                archive.addfile(info, io.BytesIO(data))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


class ReleaseArtifactTests(unittest.TestCase):
    SHA = 'e' * 40

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile_bytes = deployment_profile.PROFILE_PATH.read_bytes()
        self.profile_sha = hashlib.sha256(self.profile_bytes).hexdigest()

    def members(self, **extra):
        prefix = f'quillmd-{self.SHA}/'
        rows = {prefix + 'rebuild/ops/production_profile.json': self.profile_bytes,
                prefix + 'rebuild/manage.py': b'print("synthetic")\n',
                prefix + 'docs/rebuild/readme.md': b'not installed\n'}
        rows.update(extra)
        return rows

    def test_verified_artifact_installs_only_the_application_without_group_write(self):
        path, digest = build_artifact(self.temp.name, self.SHA, self.members())
        destination = Path(self.temp.name) / 'install'
        result = release_artifact.install(path, digest, self.SHA, self.profile_sha, destination)
        self.assertEqual(result['installed'], 2)
        self.assertEqual(sorted(str(p.relative_to(destination)) for p in destination.rglob('*') if p.is_file()),
                         ['rebuild/manage.py', 'rebuild/ops/production_profile.json'])
        self.assertEqual((destination / 'rebuild/manage.py').stat().st_mode & 0o022, 0)
        with self.assertRaisesRegex(release_artifact.ArtifactError, '^destination$'):
            release_artifact.install(path, digest, self.SHA, self.profile_sha, destination)

    def test_every_mismatch_refuses_before_extraction(self):
        prefix = f'quillmd-{self.SHA}/'
        path, digest = build_artifact(self.temp.name, self.SHA, self.members())
        cases = [
            ((path, 'f' * 64, self.SHA, self.profile_sha), 'artifact_sha256'),
            ((path, digest, 'd' * 40, self.profile_sha), 'artifact_commit'),
            ((path, digest, self.SHA, 'a' * 64), 'artifact_profile'),
            ((path, digest, 'short', self.profile_sha), 'arguments'),
        ]
        for arguments, label in cases:
            with self.subTest(label=label), self.assertRaisesRegex(release_artifact.ArtifactError, '^' + label + '$'):
                release_artifact.verify(*arguments)
        for name, members, label in (
                ('outside', self.members(**{'other/file': b'x'}), 'artifact_prefix'),
                ('no-profile', {prefix + 'rebuild/manage.py': b'x'}, 'artifact_profile'),
                ('comment', self.members(), 'artifact_commit')):
            with self.subTest(label=label):
                directory = Path(self.temp.name) / name
                directory.mkdir()
                built, built_digest = build_artifact(directory, self.SHA, members,
                                                     comment='d' * 40 if name == 'comment' else None)
                with self.assertRaisesRegex(release_artifact.ArtifactError, '^' + label + '$'):
                    release_artifact.verify(built, built_digest, self.SHA, self.profile_sha)

    def test_the_profile_check_binds_profile_bytes_not_a_commit_and_the_module_says_so(self):
        # One running script's profile sha verifies two different commits whose profiles are byte-identical.
        verified = []
        for sha in (self.SHA, '1' * 40):
            directory = Path(self.temp.name) / sha[:1]
            directory.mkdir()
            prefix = f'quillmd-{sha}/'
            built, digest = build_artifact(directory, sha, {prefix + 'rebuild/ops/production_profile.json': self.profile_bytes,
                                                            prefix + 'rebuild/manage.py': sha.encode()})
            verified.append(release_artifact.verify(built, digest, sha, self.profile_sha)['release_sha'])
        self.assertEqual(verified, [self.SHA, '1' * 40])
        # One changed profile byte is refused.
        directory = Path(self.temp.name) / 'changed'
        directory.mkdir()
        prefix = f'quillmd-{self.SHA}/'
        built, digest = build_artifact(directory, self.SHA, {prefix + 'rebuild/ops/production_profile.json':
                                                             self.profile_bytes + b' '})
        with self.assertRaisesRegex(release_artifact.ArtifactError, '^artifact_profile$'):
            release_artifact.verify(built, digest, self.SHA, self.profile_sha)
        # So the module claims exactly that, and not that one release's script cannot install another.
        claim = ' '.join(release_artifact.__doc__.split())
        self.assertNotIn('cannot install another release', claim)
        self.assertIn('binds the profile BYTES, not a commit', claim)
        self.assertIn('WILL verify and install any other release whose profile file is byte-identical', claim)

    def test_escaping_members_refuse_and_leave_nothing_outside(self):
        prefix = f'quillmd-{self.SHA}/'
        for name, extra in (('dotdot', {prefix + 'rebuild/../../escaped': b'x'}),
                            ('link', {prefix + 'rebuild/link': ('symlink', '/etc/passwd')})):
            with self.subTest(name=name):
                directory = Path(self.temp.name) / name
                directory.mkdir()
                built, digest = build_artifact(directory, self.SHA, self.members(**extra))
                destination = directory / 'install'
                with self.assertRaisesRegex(release_artifact.ArtifactError, '^artifact_member$'):
                    release_artifact.install(built, digest, self.SHA, self.profile_sha, destination)
                self.assertFalse(destination.exists())
                self.assertEqual(sorted(p.name for p in directory.iterdir()), [built.name])
                self.assertFalse((directory / 'escaped').exists())
                self.assertFalse(Path(self.temp.name, 'escaped').exists())

    @unittest.skipUnless(shutil.which('git'), 'git is required to build a real release artifact')
    def test_build_release_script_output_verifies_by_its_real_git_commit_id(self):
        repository = Path(self.temp.name) / 'repository'
        (repository / 'rebuild/ops').mkdir(parents=True)
        (repository / 'rebuild/ops/production_profile.json').write_bytes(self.profile_bytes)
        environment = dict(os.environ, GIT_AUTHOR_NAME='synthetic', GIT_AUTHOR_EMAIL='synthetic@example.invalid',
                           GIT_COMMITTER_NAME='synthetic', GIT_COMMITTER_EMAIL='synthetic@example.invalid',
                           GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1')
        for command in (['git', 'init', '-q'], ['git', 'add', '.'], ['git', 'commit', '-q', '-m', 'synthetic']):
            subprocess.run(command, cwd=repository, check=True, env=environment, capture_output=True)
        commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=repository, check=True, env=environment,
                                capture_output=True, text=True).stdout.strip()
        output = Path(self.temp.name) / 'out'
        output.mkdir()
        built = subprocess.run(['bash', str(PRODUCTION / 'build-release.sh'), commit, str(output)], cwd=repository,
                               env=environment, capture_output=True, text=True, timeout=60)
        self.assertEqual(built.returncode, 0, built.stderr)
        digest, name = built.stdout.split()
        self.assertEqual(Path(name).name, f'quillmd-{commit}.tar.gz')
        self.assertEqual(release_artifact.verify(name, digest, commit, self.profile_sha)['release_sha'], commit)
        again = subprocess.run(['bash', str(PRODUCTION / 'build-release.sh'), commit, str(output)], cwd=repository,
                               env=environment, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(again.returncode, 0)  # never overwrites a recorded artifact


PROVIDER_CLIENTS = frozenset({'Anthropic', 'AsyncAnthropic', 'AnthropicBedrock', 'AnthropicVertex',
                              'OpenAI', 'AsyncOpenAI', 'AzureOpenAI', 'AsyncAzureOpenAI'})
PROVIDER_MODULES = frozenset({'anthropic', 'openai'})
PROVIDER_METHODS = frozenset({'create', 'parse', 'stream'})
PROVIDER_RESOURCES = frozenset({'messages', 'responses', 'completions', 'batches'})
OUTPUT_CAPS = ('max_tokens', 'max_output_tokens', 'max_completion_tokens')
# Request options that can replace any keyword in the body the SDK sends (extra_body={'max_tokens': ...} wins),
# and client views that carry such options or bypass the typed method.
OVERRIDES = frozenset({'extra_body', 'extra_query', 'extra_headers'})
INDIRECTIONS = frozenset({'with_options', 'with_raw_response', 'with_streaming_response', 'copy'})
SKIPPED_DIRECTORIES = frozenset({'.venv', '.runtime', '.word-sdk', 'node_modules', '__pycache__', 'tests'})


def application_sources():
    """Every application Python file under rebuild/ (tests excluded); a provider call may live in any of them."""
    for directory, names, files in os.walk(REBUILD):
        names[:] = sorted(name for name in names if name not in SKIPPED_DIRECTORIES)
        for name in sorted(files):
            if name.endswith('.py') and not name.startswith('test_'):
                yield Path(directory) / name


class Unresolved(AssertionError):
    """A value the cost document restates could not be traced to one number in the code."""


def bindings(tree):
    """How many times each name is bound anywhere in the module, by ANY construct; and whether a star import exists."""
    counts, star = {}, False

    def bind(name):
        counts[name] = counts.get(name, 0) + 1
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bind(node.id)
        elif isinstance(node, ast.arg):
            bind(node.arg)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                if alias.name == '*':
                    star = True
                else:
                    bind(alias.asname or alias.name.split('.')[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bind(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bind(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bind(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bind(node.rest)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                bind(name)
        elif type(node).__name__ in ('TypeVar', 'ParamSpec', 'TypeVarTuple'):
            bind(node.name)
    return counts, star


def int_constants(tree):
    """Names whose ONLY binding anywhere in the module is one module-level assignment of an int literal. A name
    also bound by an import, a star import, an except/match/for/with target, a def, a global, anything, is not one."""
    counts, star = bindings(tree)
    if star:
        return {}
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if isinstance(target, ast.Name) and isinstance(value, ast.Constant) and type(value.value) is int:
            values[target.id] = value.value
    return {name: value for name, value in values.items() if counts.get(name) == 1}


def resolve(node, constants, where):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.Name) and node.id in constants:
        return constants[node.id]
    raise Unresolved(f'{where}: {ast.unparse(node)} cannot be resolved to one number')


def chain(node):
    """['client', 'messages', 'create'] for client.messages.create; None when the root is not a name."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    return [node.id] + parts[::-1] if isinstance(node, ast.Name) else None


def attribute_path(node):
    """(root expression, [attribute names]) for any a.b.c, whatever the root is (a name, a call, a subscript...)."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    return node, parts[::-1]


PROFILE_CAP_KEY = 'max_output_tokens'
PROFILE_SOURCE = 'job_request_profile'


def parent_map(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def enclosing_function(node, parents):
    while node in parents:
        node = parents[node]
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return node
    return None


def is_profile_cap(node):
    """Exactly `profile['max_output_tokens']`: the output cap of the job's request profile."""
    return (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == 'profile'
            and isinstance(node.slice, ast.Constant) and node.slice.value == PROFILE_CAP_KEY)


def int_tables(tree, constants):
    """Module-level names whose ONLY binding is one assignment of a dict literal whose values are all ints."""
    counts, _ = bindings(tree)
    tables = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Dict) and counts.get(node.targets[0].id) == 1
                and node.value.keys and all(key is not None for key in node.value.keys)):
            try:
                tables[node.targets[0].id] = frozenset(resolve(value, constants, '') for value in node.value.values)
            except Unresolved:
                continue
    return tables


def profile_cap_values(tree, constants, where):
    """Every output cap a request profile in this module can carry: the value under 'max_output_tokens' in every dict
    literal, each an int, a constant name, or a module-level table of ints indexed by anything (every value counts).
    Fails closed on any other way to write that key: a dict value it cannot resolve, a subscript store or delete, a
    keyword argument outside a provider call, or a method call naming the key other than a `.get` read."""
    tables = int_tables(tree, constants)
    values = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if not (isinstance(key, ast.Constant) and key.value == PROFILE_CAP_KEY):
                    continue
                if (isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name)
                        and value.value.id in tables):
                    values |= tables[value.value.id]
                else:
                    values.add(resolve(value, constants, f'{where}: a request profile cap'))
        elif (isinstance(node, ast.Subscript) and isinstance(node.ctx, (ast.Store, ast.Del))
              and isinstance(node.slice, ast.Constant) and node.slice.value == PROFILE_CAP_KEY):
            raise Unresolved(f'{where}: line {node.lineno} writes a request profile cap outside a profile literal')
        elif isinstance(node, ast.Call):
            method = node.func.attr if isinstance(node.func, ast.Attribute) else None
            if any(keyword.arg == PROFILE_CAP_KEY for keyword in node.keywords) and method not in PROVIDER_METHODS:
                raise Unresolved(f'{where}: line {node.lineno} passes {PROFILE_CAP_KEY}= outside a provider call')
            if (any(isinstance(arg, ast.Constant) and arg.value == PROFILE_CAP_KEY for arg in node.args)
                    and method != 'get'):
                raise Unresolved(f'{where}: line {node.lineno} names {PROFILE_CAP_KEY} in a call that may write it')
    if not values:
        raise Unresolved(f'{where}: no request profile sets {PROFILE_CAP_KEY}')
    return frozenset(values)


def check_profile_source(tree, function, parents, where, depth=0):
    """`profile` in `function` must be the job's request profile: bound exactly once in the function, by
    `profile = job_request_profile(...)`, or a parameter never rebound that EVERY call of the function in this module
    fills with such a name. Anything else — a second binding, a default, another source, the function referenced
    without being called — fails closed."""
    counts, _ = bindings(tree)
    if depth > 3 or isinstance(function, ast.Lambda) or counts.get(PROFILE_SOURCE) != 1:
        raise Unresolved(f'{where}: the request profile cannot be traced to {PROFILE_SOURCE}')
    arguments = function.args
    positional = [arg.arg for arg in arguments.posonlyargs + arguments.args]
    parameters = positional + [arg.arg for arg in arguments.kwonlyargs]
    stores = [node for node in ast.walk(function)
              if isinstance(node, ast.Name) and node.id == 'profile' and isinstance(node.ctx, (ast.Store, ast.Del))]
    stores += [node for node in ast.walk(function) if isinstance(node, (ast.Global, ast.Nonlocal)) and 'profile' in node.names]
    if 'profile' in parameters:
        index = positional.index('profile') if 'profile' in positional else None
        defaulted = (index >= len(positional) - len(arguments.defaults) if index is not None else
                     arguments.kw_defaults[[arg.arg for arg in arguments.kwonlyargs].index('profile')] is not None)
        if stores or defaulted:
            raise Unresolved(f'{where}: the profile parameter of {function.name} is rebound or has a default')
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == function.name]
        references = [node for node in ast.walk(tree) if isinstance(node, ast.Name) and node.id == function.name]
        if not calls or len(references) != len(calls) or counts.get(function.name) != 1:
            raise Unresolved(f'{where}: {function.name} is bound or used other than by direct calls')
        for call in calls:
            given = [keyword.value for keyword in call.keywords if keyword.arg == 'profile']
            if (any(isinstance(arg, ast.Starred) for arg in call.args)
                    or any(keyword.arg is None for keyword in call.keywords)):
                raise Unresolved(f'{where}: a call of {function.name} at line {call.lineno} hides its arguments')
            if index is not None and index < len(call.args):
                given.append(call.args[index])
            if len(given) != 1 or not (isinstance(given[0], ast.Name) and given[0].id == 'profile'):
                raise Unresolved(f'{where}: {function.name} at line {call.lineno} is not given the job profile')
            caller = enclosing_function(call, parents)
            if caller is None:
                raise Unresolved(f'{where}: {function.name} is called at module level')
            check_profile_source(tree, caller, parents, where, depth + 1)
        return
    if len(stores) != 1:
        raise Unresolved(f'{where}: profile is bound {len(stores)} times in {getattr(function, "name", "?")}')
    holder = parents.get(stores[0])
    if not (isinstance(holder, ast.Assign) and holder.targets == [stores[0]] and isinstance(holder.value, ast.Call)
            and isinstance(holder.value.func, ast.Name) and holder.value.func.id == PROFILE_SOURCE):
        raise Unresolved(f'{where}: profile is not bound by {PROFILE_SOURCE}(...)')


def cap_value(tree, node, constants, parents, where):
    """('int', {n}) for a cap that is one number; ('profile', {caps}) for the job's request-profile cap."""
    if is_profile_cap(node):
        function = enclosing_function(node, parents)
        if function is None:
            raise Unresolved(f'{where}: a profile cap outside any function')
        check_profile_source(tree, function, parents, where)
        return 'profile', profile_cap_values(tree, constants, where)
    return 'int', frozenset({resolve(node, constants, where)})


def built_request(tree, node, where):
    """[(keyword, value)] of a provider call written `**builder(...)`. Allowed only when `builder` is a module-level
    function bound once, whose last statement returns a name bound once, in its body, to a dict literal with
    constant string keys and no `**`; every other use of that name in the builder must store one constant key that is
    neither an output cap nor an override (`request['thinking'] = ...`). Anything else fails closed."""
    counts, _ = bindings(tree)
    if isinstance(node, ast.Name):
        parents = parent_map(tree)
        function = enclosing_function(node, parents)
        if function is None:
            raise Unresolved(f'{where}: request alias is outside a function')
        uses = [use for use in ast.walk(function) if isinstance(use, ast.Name) and use.id == node.id]
        stores = [use for use in uses if isinstance(use.ctx, (ast.Store, ast.Del))]
        if len(stores) != 1 or len(uses) != 2 or any(arg.arg == node.id for arg in function.args.args):
            raise Unresolved(f'{where}: request alias is rebound, mutated, reused or escaped')
        assignment = parents.get(stores[0])
        if not (isinstance(assignment, ast.Assign) and assignment.targets == [stores[0]]
                and isinstance(assignment.value, ast.Call) and assignment.lineno < node.lineno):
            raise Unresolved(f'{where}: request alias is not assigned once by a preceding builder call')
        node = assignment.value
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
        raise Unresolved(f'{where}: ** of something other than a call of a request builder hides the request')
    functions = [item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == node.func.id]
    if len(functions) != 1 or counts.get(node.func.id) != 1:
        raise Unresolved(f'{where}: the request builder {node.func.id} is not one module-level function')
    builder = functions[0]
    returns = [item for item in ast.walk(builder) if isinstance(item, ast.Return)]
    last = builder.body[-1]
    if returns != [last] or not isinstance(last.value, ast.Name):
        raise Unresolved(f'{where}: {builder.name} does not end by returning one name')
    request = last.value.id
    literal = None
    for item in builder.body:
        if (isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name)
                and item.targets[0].id == request):
            if literal is not None:
                raise Unresolved(f'{where}: {builder.name} binds {request} more than once')
            literal = item.value
    if not isinstance(literal, ast.Dict) or any(
            not (isinstance(key, ast.Constant) and isinstance(key.value, str)) for key in literal.keys):
        raise Unresolved(f'{where}: {builder.name} does not build {request} as a dict literal of constant keys')
    parents = parent_map(builder)
    for use in ast.walk(builder):
        if not (isinstance(use, ast.Name) and use.id == request) or use is last.value:
            continue
        holder = parents.get(use)
        if isinstance(holder, ast.Assign) and holder.value is literal and holder.targets == [use]:
            continue
        if (isinstance(holder, ast.Subscript) and holder.value is use and isinstance(holder.ctx, ast.Store)
                and isinstance(holder.slice, ast.Constant) and isinstance(holder.slice.value, str)
                and holder.slice.value not in OUTPUT_CAPS and holder.slice.value not in OVERRIDES):
            continue
        raise Unresolved(f'{where}: {builder.name} uses {request} at line {use.lineno} in a way that can change the request')
    return [(key.value, value) for key, value in zip(literal.keys, literal.values)]


def one_function(tree, name):
    matches = [item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name]
    if len(matches) != 1:
        raise Unresolved(f'compiled mapping: {name} is not one module-level function')
    return matches[0]


def assigned_once(function, name, expression=None):
    parents = parent_map(function)
    stores = [node for node in ast.walk(function) if isinstance(node, ast.Name)
              and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del))]
    if len(stores) != 1:
        raise Unresolved(f'compiled mapping: {function.name}.{name} is not assigned once')
    assignment = parents.get(stores[0])
    if not isinstance(assignment, ast.Assign) or assignment.targets != stores:
        raise Unresolved(f'compiled mapping: {name} has an indirect assignment')
    if expression is not None and ast.dump(assignment.value) != ast.dump(ast.parse(expression, mode='eval').body):
        raise Unresolved(f'compiled mapping: {function.name}.{name} no longer has its priced source')
    return assignment.value


def readonly_value(function, name, allowed_calls=()):
    """No alias, mutation or escape of a compiled request/profile; reads into JSON/hash/comparisons are allowed."""
    parents = parent_map(function)
    for use in ast.walk(function):
        if not isinstance(use, ast.Name) or use.id != name or not isinstance(use.ctx, ast.Load):
            continue
        top = use
        while isinstance(parents.get(top), ast.Subscript) and parents[top].value is top:
            top = parents[top]
            if not isinstance(top.ctx, ast.Load):
                raise Unresolved(f'compiled mapping: {name} is mutated')
        holder = parents.get(top)
        if isinstance(holder, (ast.Compare, ast.Return)):
            continue
        if isinstance(holder, ast.Dict) and isinstance(parents.get(holder), ast.Return):
            continue
        if isinstance(holder, ast.Call) and '.'.join(chain(holder.func) or []) in allowed_calls:
            continue
        if isinstance(holder, ast.keyword) and holder.arg is None:
            continue  # provider call itself is checked by provider_caps
        raise Unresolved(f'compiled mapping: {name} escapes through {type(holder).__name__}')


def compiled_mapping_cap(path, tree, call, expression, where):
    """Separate template queue: trace its immutable compiled request and the quote's same profile output term.

    This is an explicit second contract, not an exemption from scanning. Unknown files, aliases,
    mutations, calls, cap overrides or pricing formula changes still refuse.
    """
    if path != REBUILD / 'core' / 'mapping_jobs.py' or ast.unparse(expression) != "compiled['request']":
        raise Unresolved(f'{where}: unknown compiled request contract')
    send = one_function(tree, 'send')
    if enclosing_function(call, parent_map(tree)) is not send:
        raise Unresolved(f'{where}: compiled request outside mapping send')
    if [arg.arg for arg in send.args.args] != ['compiled', 'config']:
        raise Unresolved(f'{where}: mapping send arguments changed')
    if any(isinstance(n, ast.Name) and n.id == 'compiled' and isinstance(n.ctx, (ast.Store, ast.Del)) for n in ast.walk(send)):
        raise Unresolved(f'{where}: compiled send parameter is rebound')
    readonly_value(send, 'compiled', ('json.loads',))
    callers = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == 'send']
    if len(callers) != 1:
        raise Unresolved(f'{where}: mapping send is aliased or has additional callers')
    parent = parent_map(tree).get(callers[0])
    if not isinstance(parent, ast.Call) or ast.unparse(parent) != 'send(compiled, job.config)':
        raise Unresolved(f'{where}: mapping send does not receive the quoted compilation')
    runner = enclosing_function(parent, parent_map(tree))
    assigned_once(runner, 'compiled', 'mapping.compile_request(version, job.config)')
    readonly_value(runner, 'compiled', ('send', 'mapping.validate_proposal'))
    reviews = [n for n in ast.walk(runner) if isinstance(n, ast.Call) and chain(n.func) == ['mapping', 'validate_proposal']]
    if len(reviews) != 1 or reviews[0].lineno <= parent.lineno:
        raise Unresolved(f'{where}: compiled proposal may escape before the send')
    compiler_tree = ast.parse((REBUILD / 'core' / 'mapping_assistance.py').read_text())
    compiler = one_function(compiler_tree, 'compile_request')
    assigned_once(compiler, 'profile', 'request_profile(config)')
    # The schema carries no price: the cap is profile['max_output_tokens'] and the input bound is the compiled request's
    # own size below, which includes the per-request enum schema of a claude-sonnet-5-5 envelope (standing attempt 32).
    assigned_once(compiler, 'schema', "wire.request_schema(payload) if config['model'] == generation.SONNET_5_5 else wire.Proposal")
    assigned_once(compiler, 'request', "generation.anthropic_request(config['model'], profile, SYSTEM, payload, schema)")
    readonly_value(compiler, 'request', ('canonical', 'digest'))
    assigned_once(compiler, 'size', 'len(canonical(request).encode())')
    assigned_once(compiler, 'bound', 'size + 12000')
    returns = [n for n in ast.walk(compiler) if isinstance(n, ast.Return)]
    if len(returns) != 1 or returns[0] is not compiler.body[-1] or not isinstance(returns[0].value, ast.Dict):
        raise Unresolved(f'{where}: mapping compiler no longer returns one explicit envelope')
    returned = {k.value: v for k, v in zip(returns[0].value.keys, returns[0].value.values)
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    if not (len(returned) == len(returns[0].value.keys) and isinstance(returned.get('request'), ast.Name)
            and returned['request'].id == 'request'):
        raise Unresolved(f'{where}: mapping compiler returns a different request')
    if ast.dump(returned.get('maximum_cost', ast.Constant(None))) != ast.dump(ast.parse(
            'str(cost.quantize(generation.COST_QUANTUM, rounding=ROUND_CEILING))', mode='eval').body):
        raise Unresolved(f'{where}: mapping compiler returns a different hold')
    # The US geography adjustment occurs after this list-rate bound; both token terms use the compiled envelope.
    costs = [n for n in ast.walk(compiler) if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Name) and t.id == 'cost' for t in n.targets)]
    expected = "(Decimal(bound) * rates['input_per_million'] + Decimal(profile['max_output_tokens']) * rates['output_per_million']) / 1000000"
    if len(costs) != 1 or ast.dump(costs[0].value) != ast.dump(ast.parse(expected, mode='eval').body):
        raise Unresolved(f'{where}: mapping output hold no longer prices the compiled profile cap')
    adjustments = [n for n in ast.walk(compiler) if isinstance(n, ast.AugAssign)
                   and isinstance(n.target, ast.Name) and n.target.id == 'cost']
    if len(adjustments) != 1 or ast.unparse(adjustments[0]) != 'cost *= generation.US_INFERENCE_MULTIPLIER':
        raise Unresolved(f'{where}: mapping cost adjustment changed')
    cost_stores = [n for n in ast.walk(compiler) if isinstance(n, ast.Name) and n.id == 'cost'
                   and isinstance(n.ctx, (ast.Store, ast.Del))]
    if set(cost_stores) != {costs[0].targets[0], adjustments[0].target}:
        raise Unresolved(f'{where}: mapping cost is rebound outside its priced formula')
    profiled = one_function(compiler_tree, 'request_profile')
    assigned_once(profiled, 'base', 'generation.job_request_profile(config)')
    # MAPPING_THINKING is spread before the priced key, so max_output_tokens is MAX_OUTPUT_TOKENS whatever it holds.
    assigned_once(profiled, 'profile', "{**base, **MAPPING_THINKING.get(config['model'], {}), 'profile': PROFILE, "
                                       "'max_output_tokens': MAX_OUTPUT_TOKENS, 'timeout_seconds': TIMEOUT_SECONDS}")
    readonly_value(profiled, 'profile', ('digest',))
    returns = [n for n in ast.walk(profiled) if isinstance(n, ast.Return)]
    if len(returns) != 1 or returns[0] is not profiled.body[-1] or ast.unparse(returns[0]) != 'return profile':
        raise Unresolved(f'{where}: mapping profile returns another envelope')
    cap = resolve(ast.Name(id='MAX_OUTPUT_TOKENS'), int_constants(compiler_tree), where)
    if profile_cap_values(compiler_tree, int_constants(compiler_tree), where) != frozenset({cap}):
        raise Unresolved(f'{where}: mapping profile has another output cap')
    return 'mapping-profile', frozenset({cap})


# Whole normalized modules bind helpers, imports, constants and their execution
# paths as well as the priced functions. A function-only fingerprint missed an
# undercharging replacement of Decimal. These fixed identities accompany reviewed
# offline compiler/price witnesses; they are never learned from inspected source.
# Any semantic module change fails until its dependency/price proof is reviewed.
# The MONEY-1/MONEY-2 addendum (ordinary-cost-scanner-20260928.md) reviews the
# batch_jobs delta: billing classification in finish/stop/run_one's handler only.
# The relations-contract-v2 addendum (fix/v1-relations-contract): parse_part reads an ordinary part through
# v3_field_relations.parse (the keyed answer); the request, its price and every other path are unchanged.
# The settlement-guard addendum (fix/v1-settlement-worker): resolve_view and recover_recorded pass allowed_states to
# settle(); with that keyword removed both are AST-identical to 17623922, and run_one (the send boundary) is unchanged.
# The destination-roles addendum (integration 98aebf7b, fix/v1-roles-salvage): enqueue refuses, before any hold or
# send, a complete-form plan whose ORIGINAL has a field on a role place (destination_roles.v3_held); resolve_view and
# recover_recorded keep the settlement keyword above; run_one (the send boundary) and every other definition unchanged.
# The Sonnet 5.5 addendum (fix/v2-sonnet55-notes 9833e79a; was 1da9f91b... / a5b04bf5...): the model gates and model
# names only. generation_batch: require_config admits the exact native claude-sonnet-5 OR claude-sonnet-5-5
# (core.generation.NATIVE_MODELS); parse_part judges a response against the model the plan's own config named, not the
# constant claude-sonnet-5; assemble signs relation records with that model. batch_jobs: the fixture response, the
# receipt provider and a metering-failure provider carry the plan's model. plan_for, request (the priced wire),
# constraints, partitions and every other definition are AST-identical, so the request and its price are unchanged.
# The relations field-batch addendum (fix/v2-sonnet55-notes 0e9f1025; was 375235d1... / 18f0910f...): a form whose
# single field-relations response would exceed its bound is asked in bounded parts under the relations contract's own
# plan contract 'ordinary-field-relations-parts-v1' (generation_batch.RELATIONS_PARTS_CONTRACT): partitions keeps every
# field sharing a printed context in one part (by_context), each part's wire is v3_field_relations.compile_request for
# that part's fields over the whole note and catalogue, and plan_constraints is None for such a plan without a
# manifest; batch_jobs.current_plan compares plan_constraints. Each part is priced and held as before (one reservation
# per part, settled on success or failure); the union is adopted only whole.
# The provider-refusal addendum (fix/v2-relations-scale; batch_jobs was c759a6a1...): billing classification in run_one's
# handler and stop() only. A part whose only attempt the provider DEFINITELY refused without processing it (an HTTP 400
# invalid_request_error or 413 the SDK raised for its first attempt: core.jobs.provider_refused) records a
# 'provider_refused' event and an audit row with the provider's request id, and stop() ends that part 'failed' (not
# processed) with its hold RELEASED, where it used to hold it in 'reconciliation' for an administrator. No usage, receipt
# or ledger row is written for it; a part that was settled is absorbed exactly as before. PRICED EFFECT: none on any
# request or price - generation_batch (plan_for, request: the priced wire) is unchanged, and in batch_jobs the send
# (client.messages.create(**wire), max_retries=0, inside run_one's try) and every definition but stop() and run_one's
# exception handler are AST-identical; a refused part's hold is released instead of kept.
BATCH_PRICED_MODULES = {
    'core/generation_batch.py': '3dab6c7c7157b3149fdd35d5091af15e19a28a7a3aef4ab0a703eedab6848152',
    'core/batch_jobs.py': 'b8b5b0471d4a6590f22bc96fc4c5964ec8837fe843dd7f900d95f1dc5ba09f74',
}

# Reviewed c14dda34 compiler/profile on the40fb602f union, including unchanged
# quarantine admission gates. See ordinary-cost-scanner-20260928.md for the
# independent exact-wire/price/reservation witness and negative controls. The
# 17f0aefe addendum reviews source-reader and disposition-denial-only deltas. The relations-contract-v2 addendum
# (fix/v1-relations-contract; was 97d38fed…): CONTRACT/SALT v2, the per-request keyed schema (response_schema, sent
# through the same anthropic_request and refused unless it reaches the wire unchanged), the keyed response_bound, the
# strict parse, and one refusal of a unit-less source; the priced wire is still the one compile_request builds and
# maximum_cost measures, byte for byte. The disagreement-holds addendum (fix/v1-relations-contract; was ad7b29dd…):
# records() no longer refuses the WHOLE response when one field's selection disagrees with its relations (live attempt
# 020); it records that field as returned, and read() refuses it through the new `disagrees` predicate (the same
# refusal as before, proved equivalent over every selection and relation of up to four units). Only disagrees, records
# and read changed; compile_request, maximum_cost, generate, parse, response_schema and response_bound are AST-identical.
# The claimed-units addendum (fix/v1-relations-contract; was ccfe1a51…): a field's CLAIM (`claimed`: its selection plus
# every unit its relations call answer or qualifier) is what records() stores in competing_output and read() compares
# between competing repeated questions (refutation of dfde4fc8, F1/F2). Only claimed (added), records and read changed;
# compile_request, maximum_cost, generate, parse, response_schema, response_bound, disagrees, validated, CONTRACT, SALT
# and INSTRUCTIONS are AST-identical, so the priced wire is unchanged byte for byte.
# The Sonnet 5.5 addendum (fix/v2-sonnet55-notes 9833e79a; was 51120e0a...): require_config, records and read admit
# the exact native claude-sonnet-5 or claude-sonnet-5-5 (core.generation.NATIVE_MODELS); generate adds the requested
# model to its in-memory result and validated refuses a response from any other model. compile_request, maximum_cost,
# response_schema, response_bound, parse, disagrees, claimed, CONTRACT, SALT and INSTRUCTIONS are AST-identical, so the
# priced wire is unchanged byte for byte (on claude-sonnet-5-5 the ordinary profile is claude-sonnet-5-5-ordinary-v1:
# the same 20000-token cap the scanner already resolves).
# The single-patient addendum (fix/v2-sonnet55-notes 0e9f1025; was a554409a...): enabled(model) reads
# core.generation.field_relations_enabled (claude-sonnet-5-5 takes the contract by default unless the switch says
# '0'), and require_config and records pass the config's / record's model to it (the django settings import is gone);
# read() adds sole_released / sole_independent / SOLE_FIELD_TOPICS / option_view (evidence of WHO, read after the
# response - nothing reaches the wire). compile_request, maximum_cost, generate, validated, response_schema,
# response_bound, parse, disagrees, claimed, CONTRACT, SALT and INSTRUCTIONS are AST-identical, so the priced wire is
# unchanged byte for byte.
# The refutation round-4 addendum (fix/v2-sonnet55-notes, repair over 0e9f1025; was 90fc7d89...): enabled() is on
# only while the deployment's own switch is on AND (for a request or record) the model it names takes the contract;
# read() refuses a record whose model the switch does not take; sole_independent sets apart only an assessment's doubt
# about something else. compile_request, maximum_cost, generate, validated, response_schema, response_bound, parse,
# disagrees, claimed, CONTRACT, SALT and INSTRUCTIONS are AST-identical, so the priced wire is unchanged byte for byte.
# The refutation round-5 addendum (fix/v2-sonnet55-notes, repair over 737590c1; was 5f94cea6...): sole_independent
# holds a denial, ending or contraindication against every other line naming a topic class it bears on, holds a
# doubt of the answer's own class whatever its word, and nothing else in the module changed. compile_request,
# maximum_cost, generate, validated, response_schema, response_bound, parse, disagrees, claimed, records, read,
# CONTRACT, SALT and INSTRUCTIONS are AST-identical, so the priced wire is unchanged byte for byte.
# The refutation round 6 addendum (fix/v2-sonnet55-notes, was bd3902aa...): sole_independent only (a line denying a
# class that bears on the answer's, in either direction; its docstring) - read after the response, nothing reaches
# the wire; every other definition is AST-identical.
# The relations-contract-v3 addendum (fix/v2-relations-scale; was 6fc2071f...): the answer schema no longer grows with
# fields x units (v2's 14 units x 10 fields was refused live, "Schema is too complex for compilation"). CONTRACT/SALT v3
# (so the pricing version moves: ordinary_pricing_version hashes the contract), READABLE (read() also verifies a stored
# v2 record under v2's own salt and binding; binding() takes the record's contract), INSTRUCTIONS (the positional
# self-naming shape), response_schema (fields a list of answers naming their key; context a list of {unit, relation};
# FieldKey/UnitId/OptionId/Relation enums, each once; no length keyword - transform_schema leaves it unchanged and
# compile_request still refuses otherwise), parse (proves the exact coverage the grammar cannot: every requested key
# once, every offered unit once per field in the offered order) and response_bound (the positional worst-case body).
# PRICED EFFECT: the request bytes change (instructions and schema), so maximum_cost - the same formula, (request bytes
# + 12000) x input rate + the profile's max_output_tokens x output rate - prices the new bytes; the response bound is
# larger per unit, so fewer fields fit one bounded response and the relations field batches split sooner (each part
# still priced and held as before). compile_request, maximum_cost, generate, validated, records, claimed, disagrees and
# the send (client.messages.create(**compiled['wire']), max_retries=0, the profile cap) are AST-identical.
# The relations-contract-v4 addendum (fix/v2-relations-compact; was 50e02822...): each field's relations are a
# PARTITION of the offered unit IDs - context an object of five closed lists (answer, qualifier, contrary, unresolved,
# independent) of UnitId enum values - instead of v3's one {unit, relation} entry per unit. CONTRACT/SALT v4 (the pricing
# version moves with the contract identity), READABLE (stored v3 records read too), INSTRUCTIONS (the partition shape),
# PARTITION (the list names), response_schema (the same fixed vocabulary: FieldKey/UnitId/OptionId enums each once, a
# closed Partition object, no length keyword), parse (proves the partition: every offered unit exactly once across the
# five lists, none unknown) and response_bound (the true worst case: every unit in one list). PRICED EFFECT: the request
# bytes change (instructions and schema), so maximum_cost - the same formula - prices the new bytes; the response bound
# is about a fifth of v3's per unit, so far more fields fit one bounded 20,000-token response (25 units: 60 fields, was
# 17) and the relations field batches split far later. compile_request, maximum_cost, generate, validated, records,
# read, claimed, disagrees and the send are AST-identical.
# Financial renewal 2026-10-04, elicited-proof correction: only the complete
# relations reader/source-dependency AST and three generation governance floors
# changed. Independent ROOT33 controls qualify the finished semantic correction;
# the SDK compiler, quotes, caps, billing and 13 other guarded ASTs/four inputs
# remain identical. Four genuine OLD-paid/NEW1229 offline reconstructions pass
# with unchanged actual request/usage/QA-settlement rows. Full original and new
# identities, proof limits and affected119 gate are recorded separately in
# docs/rebuild/v1/financial-renewal-20261004/ELICITED-RENEWAL.md.
# Old campaigns stay closed. This is no voice, corpus or invoice qualification.
ORDINARY_PRICED_SHA256 = '2819cea85a4e1a911603dd55b15dd21244f8a24064677c35ae61a2b72c4de1bc'


# Financial renewal 2026-10-04: genuine paid campaign-3 children 002/003 on
# 04fb7603 and campaign-2 ordinary request 016 on 481b65ad. All 15 complete
# guarded ASTs and four parser/package inputs are identical at reviewed 1983e7fa.
# Full request/compiler/quote/receipt/settlement evidence and original fingerprints
# remain in docs/rebuild/v1/financial-renewal-20261004/RENEWAL.md.
# This source identity proof does not certify clinical or Word compatibility.
ORDINARY_PRICED_DEPENDENCY_PATHS = (
    'core/generation.py', 'core/ordinary_source_scope.py', 'core/reviewed_source.py',
    'core/reviewed_procedure_source.py', 'core/source_scope.py', 'core/v3_actors.py',
    'core/v3_syntax.py', 'core/v3_literal_facts.py', 'core/reviewed_speaker.py',
    'core/transcript_context.py', 'core/v3_destination.py', 'core/v3_mapping.py',
)
ORDINARY_PRICED_DEPENDENCIES = {
    'core/generation.py': '840bf7af85ccdbe0cec7f8cf84a3c58819ec6267f51867c17ab61745f2812227',
    'core/ordinary_source_scope.py': '259211c1f8de25e5d10e4c5cc794fd771d052bb30205e1c5f4a0824556a5525e',
    'core/reviewed_source.py': '8a0f3f687f367100d00d5e6299df19992b22476c996cbb349d94c77b0bfbc157',
    'core/reviewed_procedure_source.py': 'aa4d75a2603f2642de278ffba7850e6d1c78fdf234263b4fdaaa8e6bc8e47fa0',
    'core/source_scope.py': '5b1bf9d765303c426047477decddb5f1b90e611651e634d9adafeb84a68016c1',
    'core/v3_actors.py': 'bac5d81f5d7112db20502b4c0a952d86b05d3388b07cf8b788e148ac26e81275',
    'core/v3_syntax.py': 'd38b74fa82c00a0d2a37cc80cacec4163a4ad9fe9a2b3025874f56fc4d207c96',
    'core/v3_literal_facts.py': '5a496beae391ec92f9144e8fa995b5a13b5e358fb880fbc0262cf5a1cf4af034',
    'core/reviewed_speaker.py': '4da43d8c4dc86b9847604f84edf0f0fc28133242ec4d73270d24dfc36e3c1b91',
    'core/transcript_context.py': 'e4bdacc5301976b07fac91d5bc63fd0e7295201a0b969b47ec38148bc7c8dfff',
    'core/v3_destination.py': 'b8ff1dff5825ef66c86c43d3db21fd9e7b9b8468179205ebac01899e347809ef',
    'core/v3_mapping.py': '34cae0324aa323299cea26e035c560d32a5aeda23fc25e435234ab73c2e5c87c',
}
ORDINARY_PRICED_INPUT_PATHS = (
    'core/v3_syntax_model.json', 'requirements.txt', 'requirements-production.lock',
    'requirements-production.manifest.json',
)
ORDINARY_PRICED_INPUTS = {
    'core/v3_syntax_model.json': 'b10eb2639ed76ce01b1122796ad6f5e1a2d6fd42124aafdddae579672ca197bc',
    'requirements.txt': '702f180a80b5bb1d7ba7b2a0fa137feabcf19b86133e06b163fd7ba31d1f213b',
    'requirements-production.lock': 'b94c81f52375162561c9b6445e2ffabf3a7452613c573a94ffc42d8019652473',
    'requirements-production.manifest.json': '0226d37c2e5ab391679d65cc257a940db29976fc1a70e54c9d2bcf11777f6ade',
}


def ordinary_dependency_proof(where):
    """Union of complete helper/caller ASTs and exact pinned parser inputs.

    This verifies declared source, not installed packages or provider access.
    An unchanged importing caller cannot conceal a changed helper body/import.
    """
    if (set(ORDINARY_PRICED_DEPENDENCIES) != set(ORDINARY_PRICED_DEPENDENCY_PATHS)
            or set(ORDINARY_PRICED_INPUTS) != set(ORDINARY_PRICED_INPUT_PATHS)):
        raise Unresolved(f'{where}: ordinary dependency proof is incomplete')
    for relative, expected in ORDINARY_PRICED_DEPENDENCIES.items():
        try:
            tree = ast.parse((REBUILD / relative).read_text())
        except (OSError, SyntaxError, UnicodeError):
            raise Unresolved(f'{where}: {relative} is unreadable; its ordinary proof needs review') from None
        actual = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
        if actual != expected:
            raise Unresolved(f'{where}: {relative} changed or is unreviewed; its complete ordinary proof needs review')
    for relative, expected in ORDINARY_PRICED_INPUTS.items():
        try:
            actual = hashlib.sha256((REBUILD / relative).read_bytes()).hexdigest()
        except OSError:
            raise Unresolved(f'{where}: {relative} is unreadable; its ordinary parser input needs review') from None
        if actual != expected:
            raise Unresolved(f'{where}: {relative} changed or is unreviewed; its ordinary parser input needs review')


def ordinary_module_proof(where):
    path = REBUILD / 'core/v3_field_relations.py'
    tree = ast.parse(path.read_text())
    actual = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
    if actual != ORDINARY_PRICED_SHA256:
        raise Unresolved(f'{where}: complete ordinary compiler/binding/price proof needs review')
    ordinary_dependency_proof(where)
    return tree


def ordinary_dispatch(tree, name):
    """The checked imported price/send branch must be the actual early route."""
    function = one_function(tree, name)
    tail = ('return ordinary.maximum_cost(notes,fields,config,context_labels,requirements or ())'
            if name == 'maximum_cost' else
            'return ordinary.generate(notes,fields,config,context_labels=context_labels,requirements=requirements or ())')
    expected = ast.parse("if config.get('ordinary_field_contract') and natural_v3(fields):\n"
        "    from . import v3_field_relations as ordinary\n    " + tail).body[0]
    index = 2 if name == 'maximum_cost' else 1
    first = ast.parse('config=config or configuration(fields)').body[0]
    if (function.decorator_list or len(function.body) <= index or
            ast.dump(function.body[0]) != ast.dump(first) or
            ast.dump(function.body[index]) != ast.dump(expected)):
        raise Unresolved(f'{name}: ordinary execution route bypasses its checked compiler')
    return function.body[index].body[-1]


def compiled_ordinary_cap(path, tree, call, expression, where):
    if path != REBUILD / 'core/v3_field_relations.py' or ast.unparse(expression) != "compiled['wire']":
        raise Unresolved(f'{where}: unknown ordinary request contract')
    if enclosing_function(call, parent_map(tree)) is not one_function(tree, 'generate'):
        raise Unresolved(f'{where}: ordinary request moved outside its reviewed send boundary')
    ordinary_module_proof(where)
    profile_tree = ast.parse(GENERATION.read_text())
    ordinary_dispatch(profile_tree, 'generate')
    ordinary_dispatch(profile_tree, 'maximum_cost')
    return 'profile', profile_cap_values(profile_tree, int_constants(profile_tree), where)

def compiled_batch_cap(path, tree, call, expression, where):
    if path != REBUILD / 'core/batch_jobs.py' or ast.unparse(expression) != 'wire':
        raise Unresolved(f'{where}: unknown batch request contract')
    if enclosing_function(call, parent_map(tree)) is not one_function(tree, 'run_one'):
        raise Unresolved(f'{where}: batch request is outside the reviewed send boundary')
    modules = {str(path.relative_to(REBUILD)): tree,
               'core/generation_batch.py': ast.parse((REBUILD / 'core/generation_batch.py').read_text())}
    for relative, module in modules.items():
        counts, _ = bindings(module)
        names = ('g', 'b') if relative.endswith('/batch_jobs.py') else ('g',)
        parents = parent_map(module)
        for name in names:
            matches = [n for n in module.body if isinstance(n, ast.ImportFrom) and n.level == 1
                       and n.module is None and any(a.asname == name and a.name ==
                           ('generation' if name == 'g' else 'generation_batch') for a in n.names)]
            if len(matches) != 1 or counts.get(name) != 1:
                raise Unresolved(f'{where}: batch compiler module identity changed')
            for use in ast.walk(module):
                if not isinstance(use, ast.Name) or use.id != name or not isinstance(use.ctx, ast.Load):
                    continue
                top = use
                while isinstance(parents.get(top), ast.Attribute):
                    top = parents[top]
                if top is use or not isinstance(top.ctx, ast.Load):
                    raise Unresolved(f'{where}: batch compiler module is mutated or escapes')
    for relative, expected in BATCH_PRICED_MODULES.items():
        actual = hashlib.sha256(ast.dump(modules[relative], include_attributes=False).encode()).hexdigest()
        if actual != expected:
            raise Unresolved(f'{where}: {relative} changed; its complete binding/price proof needs review')
    ordinary_module_proof(where)  # Batch compilation imports this complete request/price contract too.
    profile_tree = ast.parse(GENERATION.read_text())
    return 'profile', profile_cap_values(profile_tree, int_constants(profile_tree), where)


#: Client calls that send no tokens and are never priced (reviewed 2026-10-01 for the standing runner's model-access
#: preflight, ops/standing_qa.run_preflight: GET /v1/models/<id> through a guard that allows one request). Anything
#: else on a provider client still has to be a traced, capped provider call.
UNBILLED_CLIENT_CALLS = frozenset({('models', 'retrieve'), ('close',)})


def provider_caps(path):
    """[(where, (kind, caps))] for every provider call in one file. Fails closed, naming the call, on anything it
    cannot trace: a provider-shaped call whose receiver is not a client constructed and bound to a name in this file;
    a client constructed anywhere else (returned, passed on, called inline); a client name bound any other way or used
    any other way; a view (with_options, with_raw_response, with_streaming_response, copy); extra_body, extra_query,
    extra_headers, positional arguments, or `**` other than one request builder `built_request` can read; not exactly
    one output cap; a cap that is neither one number nor the job's request-profile cap (`cap_value`)."""
    tree = ast.parse(path.read_text())
    constants = int_constants(tree)
    counts, _ = bindings(tree)
    name = path.relative_to(REBUILD.parent)
    parents = parent_map(tree)
    imported = {}  # local name -> provider client class, for `from anthropic import Anthropic as A`
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or '').split('.')[0] in PROVIDER_MODULES:
            for alias in node.names:
                if alias.name in PROVIDER_CLIENTS:
                    imported[alias.asname or alias.name] = alias.name

    def constructs_client(call):
        root, parts = attribute_path(call.func)
        if parts:
            return parts[-1] in PROVIDER_CLIENTS
        return isinstance(root, ast.Name) and (root.id in PROVIDER_CLIENTS or root.id in imported)
    clients, client_bindings = set(), {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and constructs_client(node)):
            continue
        holder = parents.get(node)
        target = (holder.targets[0] if isinstance(holder, ast.Assign) and len(holder.targets) == 1 else
                  holder.target if isinstance(holder, ast.AnnAssign) else None)
        if not (isinstance(target, ast.Name) and holder.value is node):
            raise Unresolved(f'{name}:{node.lineno}: a provider client is constructed but not bound to one name')
        clients.add(target.id)
        client_bindings[target.id] = client_bindings.get(target.id, 0) + 1
    for client in clients:
        if counts.get(client) != client_bindings[client]:
            raise Unresolved(f'{name}: the name {client} is bound to something other than a provider client too')
    for node in ast.walk(tree):  # a client may only be the root of a provider call; anything else hides the cap
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in clients:
            top = node
            while isinstance(parents.get(top), ast.Attribute):
                top = parents[top]
            if not (isinstance(parents.get(top), ast.Call) and parents[top].func is top and top is not node):
                raise Unresolved(f'{name}:{node.lineno}: provider client {node.id} used other than as a provider call')
    caps = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        root, parts = attribute_path(node.func)
        shaped = (len(parts) >= 2 and parts[-1] in PROVIDER_METHODS
                  and bool(PROVIDER_RESOURCES & set(parts[:-1])))
        from_client = isinstance(root, ast.Name) and root.id in clients and bool(parts)
        capped = any(keyword.arg in OUTPUT_CAPS for keyword in node.keywords)
        if not (shaped or from_client or capped):
            continue
        where = f'{name}:{node.lineno} {ast.unparse(node.func)}'
        if shaped and not from_client:
            raise Unresolved(f'{where}: the receiver cannot be traced to a provider client constructed in this file')
        if from_client and not shaped and tuple(parts) in UNBILLED_CLIENT_CALLS and not capped:
            continue  # reviewed: model metadata lookup / client close carry no tokens and no price
        if from_client and not shaped:
            raise Unresolved(f'{where}: a provider client call this check does not know')
        if INDIRECTIONS & set(parts):
            raise Unresolved(f'{where}: reached through {sorted(INDIRECTIONS & set(parts))}, which can change options')
        if node.args:
            raise Unresolved(f'{where}: positional arguments hide the request')
        if any(keyword.arg is None for keyword in node.keywords):
            if len(node.keywords) != 1:
                raise Unresolved(f'{where}: ** beside other keywords hides the request')
            if isinstance(node.keywords[0].value, ast.Subscript):
                if path == REBUILD / 'core/v3_field_relations.py':
                    caps.append((where, compiled_ordinary_cap(path, tree, node, node.keywords[0].value, where)))
                    continue
                caps.append((where, compiled_mapping_cap(path, tree, node, node.keywords[0].value, where)))
                continue
            if path == REBUILD / 'core/batch_jobs.py':
                caps.append((where, compiled_batch_cap(path, tree, node, node.keywords[0].value, where)))
                continue
            keywords = built_request(tree, node.keywords[0].value, where)
        else:
            keywords = [(keyword.arg, keyword.value) for keyword in node.keywords]
        overriding = sorted(OVERRIDES & {key for key, _ in keywords})
        if overriding:
            raise Unresolved(f'{where}: {overriding} can override the output cap')
        found = [value for key, value in keywords if key in OUTPUT_CAPS]
        if len(found) != 1:
            raise Unresolved(f'{where}: {len(found)} output caps (exactly one is required)')
        caps.append((where, cap_value(tree, found[0], constants, parents, where)))
    return caps


def all_provider_caps():
    return tuple(cap for path in application_sources() for cap in provider_caps(path))


def history_cost_adjustment(function):
    """Admit only the measured, additive history charge; never skip unknown rate terms."""
    expected = ast.parse("""
if config.get('history_context_contract'):
    from . import v3_history_context as history
    target_keys = list(history.targets(asked, units)) if v3_fields is not None else []
    if target_keys:
        history.refuse_request(config)
        extra = len((history.INSTRUCTIONS + json.dumps(history.HistorySelections.model_json_schema())
                     + json.dumps({'history_context_targets': target_keys})).encode())
        bound += Decimal(extra)*r['input_per_million']/1000000
""").body[0]
    matches = [node for node in ast.walk(function) if isinstance(node, ast.If)
               and ast.dump(node.test) == ast.dump(expected.test)]
    if len(matches) != 1 or ast.dump(matches[0]) != ast.dump(expected):
        raise Unresolved('maximum_cost: history charge no longer measures its full guarded request addition')
    # A correct formula in dead code is not a priced request. Require the actual
    # straight-line tail: base bound, history addition, geography, final return.
    tail = function.body[-4:]
    geography = ast.parse("if profile.get('inference_geo') == 'us': "
                          "bound=(bound * US_INFERENCE_MULTIPLIER).quantize(COST_QUANTUM, rounding=ROUND_CEILING)").body[0]
    if (len(tail) != 4 or not isinstance(tail[0], ast.Assign)
            or [ast.dump(target) for target in tail[0].targets] != [ast.dump(ast.Name(id='bound', ctx=ast.Store()))]
            or tail[1] is not matches[0] or ast.dump(tail[2]) != ast.dump(geography)
            or ast.dump(tail[3]) != ast.dump(ast.parse('return bound').body[0])):
        raise Unresolved('maximum_cost: history charge is not on the final priced execution path')
    # A matching subtree must not mask another assignment elsewhere in the function.
    assigned_once(function, 'target_keys')
    assigned_once(function, 'extra')
    return matches[0].body[-1].body[-1]


def maximum_cost_terms():
    """(input overhead tokens, (kind, output caps)) in core/generation.py's maximum_cost: the overhead traced to one
    number, the output term to one number or to the job's request-profile cap (`cap_value`)."""
    tree = ast.parse(GENERATION.read_text())
    constants = int_constants(tree)
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'maximum_cost']
    if len(functions) != 1:
        raise Unresolved(f'core/generation.py: {len(functions)} maximum_cost functions')
    ordinary_module_proof('maximum_cost')
    ordinary_return = ordinary_dispatch(tree, 'maximum_cost')
    history_charge = history_cost_adjustment(functions[0])
    parents = parent_map(tree)
    branches = {}
    for node in ast.walk(functions[0]):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult) and isinstance(node.right, ast.Subscript)
                and isinstance(node.right.slice, ast.Constant)):
            assignment = node
            while assignment in parents and not isinstance(assignment, (ast.Assign, ast.AugAssign)):
                assignment = parents[assignment]
            if assignment is history_charge:
                continue
            if not isinstance(assignment, ast.Assign):
                raise Unresolved('maximum_cost: rate term outside a bounded assignment')
            branches.setdefault(assignment, {}).setdefault(node.right.slice.value, []).append(node.left)
    if not branches:
        raise Unresolved('maximum_cost: no priced branches')
    zero_return = ast.parse("if config['mode'] != 'live': return Decimal('0')").body[0]
    allowed_zero = [node for node in ast.walk(functions[0]) if isinstance(node, ast.If)
                    and ast.dump(node) == ast.dump(zero_return)]
    if len(allowed_zero) != 1:
        raise Unresolved('maximum_cost: unpriced mode return changed')
    narrative_test = ast.parse('narrative_contract(fields,config)', mode='eval').body
    narrative = [node for node in functions[0].body if isinstance(node, ast.If)
                 and ast.dump(node.test) == ast.dump(narrative_test)]
    if len(narrative) != 1 or not isinstance(narrative[0].body[-1], ast.Return):
        raise Unresolved('maximum_cost: narrative priced return is not explicit')
    allowed_returns = (allowed_zero[0].body[0], narrative[0].body[-1], functions[0].body[-1], ordinary_return)
    for node in ast.walk(functions[0]):
        if isinstance(node, ast.Return) and node not in allowed_returns:
            raise Unresolved('maximum_cost: an early return bypasses the priced execution path')
        if isinstance(node, ast.Return) and node not in (allowed_zero[0].body[0], ordinary_return):
            if not isinstance(node.value, ast.Name) or node.value.id != 'bound':
                raise Unresolved('maximum_cost: priced branch returns something other than bound')
        if isinstance(node, ast.Name) and node.id == 'bound' and isinstance(node.ctx, (ast.Store, ast.Del)):
            holder = parents.get(node)
            if holder in branches or holder is history_charge:
                continue
            adjustment = '(bound * US_INFERENCE_MULTIPLIER).quantize(COST_QUANTUM, rounding=ROUND_CEILING)'
            if not (isinstance(holder, ast.Assign) and holder.targets == [node]
                    and ast.dump(holder.value) == ast.dump(ast.parse(adjustment, mode='eval').body)):
                raise Unresolved('maximum_cost: bound is rebound outside its priced formula')
    results = set()
    for terms in branches.values():
        if sorted(terms) != ['input_per_million', 'output_per_million'] or any(len(v) != 1 for v in terms.values()):
            raise Unresolved(f'core/generation.py maximum_cost: branch rate terms {sorted(terms)} are not one input and one output')
        results.add(cost_branch_terms(tree, functions[0], terms, constants))
    if len(results) != 1:
        raise Unresolved('maximum_cost: narrative and general branches price different caps or overheads')
    return next(iter(results))


def cost_branch_terms(tree, function, terms, constants):
    where = f'core/generation.py:{function.lineno} maximum_cost'
    inputs, output = terms['input_per_million'][0], terms['output_per_million'][0]
    if not (isinstance(inputs, ast.Call) and chain(inputs.func) == ['Decimal'] and len(inputs.args) == 1
            and isinstance(inputs.args[0], ast.BinOp) and isinstance(inputs.args[0].op, ast.Add)
            and isinstance(inputs.args[0].left, ast.Call) and chain(inputs.args[0].left.func) == ['len']):
        raise Unresolved(f'{where}: input term {ast.unparse(inputs)} is not Decimal(len(request) + overhead)')
    if not (isinstance(output, ast.Call) and chain(output.func) == ['Decimal'] and len(output.args) == 1):
        raise Unresolved(f'{where}: output term {ast.unparse(output)} is not Decimal(tokens)')
    return (resolve(inputs.args[0].right, constants, where),
            cap_value(tree, output.args[0], constants, parent_map(tree), where))


def number(text):
    return int(text.replace(',', ''))


class ProductionCostDocumentTests(unittest.TestCase):
    """production-cost.md restates the application's own generation bound; its numbers must be the code's."""

    def test_every_provider_output_cap_is_the_one_the_hold_prices_and_the_document_states(self):
        raw = COST_DOCUMENT.read_text()
        text = ' '.join(raw.split())
        stated = re.search(r'The output caps a request profile can set are ([0-9, and]+?) tokens', text)
        self.assertIsNotNone(stated, 'the document no longer states the output caps it assumes')
        stated_caps = frozenset(number(value) for value in re.findall(r'[0-9]{1,3}(?:,[0-9]{3})*', stated.group(1)))
        caps = all_provider_caps()
        self.assertTrue(caps, 'no provider call was found, so nothing was checked')
        bound = re.search(r"\(request bytes \+ ([0-9,]+)\) input tokens plus the request profile's output cap", text)
        self.assertIsNotNone(bound, 'the document no longer states the bound formula')
        overhead, output = maximum_cost_terms()
        self.assertEqual(overhead, number(bound.group(1)))
        # The hold prices exactly the cap each call sends: the same number, or the same job's request-profile cap.
        self.assertEqual(stated_caps, frozenset().union(*(cap[1] for _, cap in caps)))
        for where, cap in caps:
            with self.subTest(call=where):
                if cap[0] == 'mapping-profile':
                    self.assertEqual(cap[1], frozenset({20000}))
                else:
                    self.assertEqual(cap, output)

    def test_the_stated_bound_and_every_row_of_the_generation_table_agree_with_the_code(self):
        raw = COST_DOCUMENT.read_text()
        text = ' '.join(raw.split())
        rates = re.search(r'\$(\d+) per million input tokens, \$(\d+) per million output tokens', text)
        input_rate, output_rate = (Decimal(value) / 1000000 for value in rates.groups())
        overhead, _ = maximum_cost_terms()
        caps = frozenset().union(*(cap[1] for _, cap in all_provider_caps()))
        sentence = re.search(r'a 20,000-byte request is bounded at (.*?)\.(?:\s|$)', text)
        self.assertIsNotNone(sentence)
        pairs = re.findall(r'\*\*\$([0-9]+\.[0-9]{3})\*\* \(([0-9]{1,3}(?:,[0-9]{3})*)-token cap', sentence.group(1))
        self.assertTrue(pairs, 'the document no longer states the bound for any cap')
        stated_caps = {number(cap) for _, cap in pairs}
        self.assertLessEqual(stated_caps, caps)
        self.assertIn(max(caps), stated_caps)  # the worst case is always stated
        for cost, cap in pairs:
            with self.subTest(cap=cap):
                self.assertEqual(Decimal(cost), (20000 + overhead) * input_rate + number(cap) * output_rate)
        lines = raw.splitlines()
        header = lines.index('| Generation | Input tokens | Output tokens | Cost |')
        self.assertTrue(re.fullmatch(r'\|(?: -+:? \|)+', lines[header + 1]), lines[header + 1])
        rows = []
        for line in lines[header + 2:]:
            if not line.startswith('|'):
                break
            rows.append(line)
        self.assertTrue(rows, 'the generation table has no rows')
        cell = r'((?:[0-9]+ x )?[0-9]{1,3}(?:,[0-9]{3})*)'
        for line in rows:
            with self.subTest(row=line):
                match = re.fullmatch(r'\| ([^|]+?) \| ' + cell + r' \| ' + cell + r' \| \$([0-9]+\.[0-9]{3}) \|', line)
                self.assertIsNotNone(match, 'a row this check cannot read')  # fail closed on any other shape
                label, input_cell, output_cell, cost = match.groups()
                calls, _, per_call_input = input_cell.rpartition(' x ')
                output_calls, _, per_call_output = output_cell.rpartition(' x ')
                self.assertEqual(calls, output_calls)
                calls = int(calls or 1)
                self.assertLessEqual(number(per_call_output), max(caps))  # no call can return more than a cap
                expected = calls * (number(per_call_input) * input_rate + number(per_call_output) * output_rate)
                self.assertEqual(Decimal(cost), expected.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP))


class ApplicationContractTests(unittest.TestCase):
    """The production launcher and the application agree: what the launcher starts is a configuration the application's
    own settings accept in real data mode with live payments. (Two streams named the same switches differently:
    the launcher forced QUILLMD_DATA_MODE=real-patient, which the settings refuse, and QUILLMD_PAYMENT_MODE, which
    nothing reads; and the renderer could not deliver QUILLMD_STRIPE_MODE, QUILLMD_REGISTRATION or
    QUILLMD_MFA_REQUIRED_ALL, without which real mode refuses to start.)"""

    SECRET = {
        'QUILLMD_DEPLOYMENT_PROFILE': 'production', 'QUILLMD_SECRET_KEY': 's' * 50, 'QUILLMD_RELEASE_SHA': 'c' * 40,
        'QUILLMD_DB_PASSWORD': 'synthetic', 'QUILLMD_HTTPS': '1', 'QUILLMD_TRUST_PROXY': '1',
        'QUILLMD_EMAIL_MODE': 'resend', 'QUILLMD_EMAIL_FROM': 'QuillMD <no-reply@quillmd.com>',
        'QUILLMD_EMAIL_VERIFIED_DOMAIN': 'quillmd.com', 'RESEND_API_KEY': 're_synthetic',
        'QUILLMD_AI_MODE': 'live', 'QUILLMD_AI_PROVIDER': 'anthropic', 'QUILLMD_AI_MODEL': 'claude-sonnet-5',
        'QUILLMD_AI_INPUT_RATE': '2', 'QUILLMD_AI_OUTPUT_RATE': '10', 'QUILLMD_AI_CACHED_RATE': '0.20',
        'ANTHROPIC_API_KEY': 'synthetic', 'DEEPGRAM_API_KEY': 'synthetic', 'QUILLMD_DEEPGRAM_RATE_PER_MINUTE': '0.0043',
        'STRIPE_SECRET_KEY': 'rk_live_synthetic', 'STRIPE_WEBHOOK_SECRET': 'whsec_synthetic',
    }
    SETTINGS_PROBE = ("import os; os.environ['DJANGO_SETTINGS_MODULE'] = 'quillmd.settings'; import quillmd.settings as s; "
                      "print(s.QUILLMD_DATA_MODE, s.QUILLMD_STRIPE_MODE, s.QUILLMD_REGISTRATION, s.QUILLMD_MFA_REQUIRED_ALL)")

    def launched_environment(self, surface='doctor'):
        profile = deployment_profile.validate(self.profile_raw(), sha256='cd' * 32)
        secret = dict(self.SECRET, QUILLMD_APP_BASE_URL=profile.doctor_origin, QUILLMD_DB_NAME=profile.database_name,
                      QUILLMD_DB_USER=profile.roles['runtime'], QUILLMD_DB_HOST=profile.database_host,
                      QUILLMD_DB_PORT=str(profile.database_port))
        # Everything the secret carries is a name the renderer may write.
        self.assertLessEqual(set(secret), deployment_profile.ENVIRONMENT_NAMES)
        previous_umask, previous_tempdir = os.umask(0o022), tempfile.tempdir
        try:
            with patch.dict(os.environ, secret, clear=True):
                launcher.prepare_production_environment(surface, profile)
                return dict(os.environ)
        finally:
            os.umask(previous_umask)
            tempfile.tempdir = previous_tempdir

    @staticmethod
    def profile_raw():
        raw = json.loads(deployment_profile.PROFILE_PATH.read_text())
        raw['database']['host'] = HOST
        raw['database']['tls']['ca_bundle_sha256'] = 'ab' * 32
        return raw

    def settings_import(self, environment):
        return subprocess.run([sys.executable, '-c', self.SETTINGS_PROBE], cwd=REBUILD, capture_output=True, text=True,
                              timeout=60, env=dict(environment, PATH=os.environ.get('PATH', '/usr/bin:/bin')))

    def test_the_launched_environment_starts_the_application_in_real_and_live_mode(self):
        for surface in ('doctor', 'admin', 'worker'):
            with self.subTest(surface=surface):
                started = self.settings_import(self.launched_environment(surface))
                self.assertEqual(started.returncode, 0, started.stderr[-600:])
                self.assertEqual(started.stdout.split(), ['real', 'live', 'invite', 'True'])

    def test_the_settings_probe_can_fail(self):
        # Negative controls: the probe refuses what the application refuses, so its pass above means something.
        launched = self.launched_environment()
        for changes in ({'QUILLMD_DATA_MODE': 'real-patient'}, {'QUILLMD_REGISTRATION': 'open'},
                        {'QUILLMD_MFA_REQUIRED_ALL': '0'}, {'QUILLMD_STRIPE_MODE': 'test'}):
            with self.subTest(changes=changes):
                self.assertNotEqual(self.settings_import(dict(launched, **changes)).returncode, 0)

    def test_the_profile_doctor_origin_is_the_host_the_application_links_to(self):
        spec = importlib.util.spec_from_file_location('application_profile', REBUILD / 'quillmd' / 'application_profile.py')
        application = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(application)
        self.assertEqual(PROFILE.doctor_origin, 'https://' + application.DOCTOR_HOST)
        allowed = ast.literal_eval(re.search(r'^ALLOWED_HOSTS = (\[.*\])$', (REBUILD / 'quillmd' / 'settings.py').read_text(),
                                             re.M).group(1))
        self.assertIsNone(application.public_https_origin_problem(PROFILE.doctor_origin, allowed))
        self.assertIn(PROFILE.admin_origin.removeprefix('https://'), allowed)


class BootstrapScriptTests(unittest.TestCase):
    SCRIPT = PRODUCTION / 'bootstrap-host.sh'
    SHA = 'c' * 40

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        profile = deployment_profile.PROFILE_PATH.read_bytes()
        self.artifact, self.digest = build_artifact(self.temp.name, self.SHA, {
            f'quillmd-{self.SHA}/rebuild/ops/production_profile.json': profile,
            f'quillmd-{self.SHA}/rebuild/manage.py': b'print(1)\n'})
        self.cli = Path(self.temp.name) / 'awscli-exe-linux-x86_64-synthetic.zip'
        self.cli.write_bytes(b'synthetic cli bundle')
        self.cli_sha = hashlib.sha256(b'synthetic cli bundle').hexdigest()

    def run_script(self, *arguments):
        return subprocess.run(['bash', str(self.SCRIPT), *arguments], capture_output=True, text=True, timeout=60,
                              env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})

    def arguments(self, **changes):
        values = {'--release-sha': self.SHA, '--artifact': str(self.artifact), '--artifact-sha256': self.digest,
                  '--aws-cli-artifact': str(self.cli), '--aws-cli-sha256': self.cli_sha,
                  '--data-volume-id': 'vol-0123456789abcdef0'}
        values.update(changes)
        result = []
        for key, value in values.items():
            if value is not None:
                result += [key, value]
        return result

    def test_syntax_is_valid(self):
        for name in ('bootstrap-host.sh', 'build-release.sh', 'quillmd-production-heartbeat.sh'):
            with self.subTest(name=name):
                self.assertEqual(subprocess.run(['bash', '-n', str(PRODUCTION / name)]).returncode, 0)

    def test_dry_run_verifies_and_prints_the_plan_without_changing_anything(self):
        result = self.run_script(*self.arguments())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('artifact verified', result.stdout)
        self.assertIn(f'{PROFILE.account} uid=gid={PROFILE.uid}', result.stdout)
        self.assertIn(f'-> {PROFILE.state_root} (nodev,nosuid) FORMAT only if blank', result.stdout)
        self.assertIn('dry run: nothing was changed', result.stdout)
        self.assertIn('AWS CLI v2 -> /usr/local/bin/aws', result.stdout)

    def test_bad_inputs_refuse_in_the_dry_run(self):
        cases = [
            ({'--release-sha': 'c' * 39}, 'full 40-character commit'),
            ({'--artifact-sha256': 'F' * 64}, 'artifact-sha256'),
            ({'--data-volume-id': 'vol-123'}, 'data-volume-id'),
            ({'--artifact': str(Path(self.temp.name) / 'absent.tar.gz')}, 'existing regular file'),
            ({'--artifact-sha256': 'f' * 64}, 'failed verification'),
            ({'--release-sha': 'd' * 40}, 'failed verification'),
            ({'--aws-cli-artifact': None}, 'aws-cli-artifact must be an existing regular file'),
            ({'--aws-cli-sha256': 'e' * 64}, 'AWS CLI bundle sha256 differs'),
            ({'--aws-cli-sha256': 'short'}, 'aws-cli-sha256 must be 64'),
        ]
        for changes, message in cases:
            with self.subTest(changes=changes):
                result = self.run_script(*self.arguments(**changes))
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
        result = self.run_script(*self.arguments(), '--unknown')
        self.assertIn('unknown argument', result.stderr)
        result = self.run_script(*self.arguments(), '--word-sdk-artifact')
        self.assertIn('needs a value', result.stderr)

    @unittest.skipIf(os.geteuid() == 0, 'executing as root would change this host')
    def test_execute_refuses_without_root_before_any_change(self):
        result = self.run_script(*self.arguments(), '--execute')
        self.assertEqual(result.returncode, 1)
        self.assertIn('must run as root', result.stderr)
        self.assertNotIn('identity', result.stdout)

    def test_the_script_never_enables_or_starts_production_services(self):
        text = self.SCRIPT.read_text()
        self.assertIsNone(re.search(r'systemctl\s+(enable|start|restart|reload)\b(?!.*journald)', text))
        self.assertEqual(re.findall(r'systemctl\s+(?:disable --now)\s+(\S+)', text), ['nginx', 'ssh.socket'])
        self.assertNotRegex(text, r'(?m)^\s*docker\s')
        self.assertIn('refuse "Docker is present', text)
        self.assertIn('[ ! -e "$PRIVATE_INSTALL" ] || refuse', text)


if __name__ == '__main__':
    unittest.main()
