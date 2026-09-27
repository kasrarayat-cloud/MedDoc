"""The production deploy files agree with the one profile, and their tools refuse what they must.

Nothing here provisions or changes a host: the bootstrap script is exercised only in its dry run
(and, as a non-root user, its refusal to execute), the environment renderer and the artifact
installer only against temporary directories.
"""
import ast
from decimal import Decimal, ROUND_HALF_UP
import functools
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

    def test_every_unit_but_the_secret_renderer_cannot_reach_either_metadata_address(self):
        # Judged the way systemd applies IPAddressAllow=/IPAddressDeny= (systemd.resource-control(5)), over the unit
        # and every drop-in this package ships. The heartbeat unit has no launcher behind it: this is its only guard.
        units = sorted(PRODUCTION.glob('*.service'))
        self.assertEqual(len(units), 5)
        for path in units:
            allow, deny = ip_access_lists(path)
            with self.subTest(unit=path.name):
                if path.name == PROFILE.unit_prefix + 'environment.service':
                    # Root, and it must reach IMDS: it reads the secret with the instance role.
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
        if from_client and not shaped:
            raise Unresolved(f'{where}: a provider client call this check does not know')
        if INDIRECTIONS & set(parts):
            raise Unresolved(f'{where}: reached through {sorted(INDIRECTIONS & set(parts))}, which can change options')
        if node.args:
            raise Unresolved(f'{where}: positional arguments hide the request')
        if any(keyword.arg is None for keyword in node.keywords):
            if len(node.keywords) != 1:
                raise Unresolved(f'{where}: ** beside other keywords hides the request')
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


@functools.lru_cache(maxsize=1)
def all_provider_caps():
    return tuple(cap for path in application_sources() for cap in provider_caps(path))


def maximum_cost_terms():
    """(input overhead tokens, (kind, output caps)) in core/generation.py's maximum_cost: the overhead traced to one
    number, the output term to one number or to the job's request-profile cap (`cap_value`)."""
    tree = ast.parse(GENERATION.read_text())
    constants = int_constants(tree)
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == 'maximum_cost']
    if len(functions) != 1:
        raise Unresolved(f'core/generation.py: {len(functions)} maximum_cost functions')
    terms = {}
    for node in ast.walk(functions[0]):
        if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult) and isinstance(node.right, ast.Subscript)
                and isinstance(node.right.slice, ast.Constant)):
            terms.setdefault(node.right.slice.value, []).append(node.left)
    if sorted(terms) != ['input_per_million', 'output_per_million'] or any(len(v) != 1 for v in terms.values()):
        raise Unresolved(f'core/generation.py maximum_cost: rate terms {sorted(terms)} are not one input and one output')
    where = f'core/generation.py:{functions[0].lineno} maximum_cost'
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
        self.assertEqual(output, ('profile', stated_caps))
        for where, cap in caps:
            with self.subTest(call=where):
                self.assertEqual(cap, output)

    def test_the_stated_bound_and_every_row_of_the_generation_table_agree_with_the_code(self):
        raw = COST_DOCUMENT.read_text()
        text = ' '.join(raw.split())
        rates = re.search(r'\$(\d+) per million input tokens, \$(\d+) per million output tokens', text)
        input_rate, output_rate = (Decimal(value) / 1000000 for value in rates.groups())
        overhead, (_, caps) = maximum_cost_terms()
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
