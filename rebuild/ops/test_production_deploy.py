"""The production deploy files agree with the one profile, and their tools refuse what they must.

Nothing here provisions or changes a host: the bootstrap script is exercised only in its dry run
(and, as a non-root user, its refusal to execute), the environment renderer and the artifact
installer only against temporary directories.
"""
import hashlib
import io
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
except ImportError:
    import deployment_profile
    import release_artifact
    import render_production_environment as renderer

REBUILD = Path(__file__).resolve().parents[1]
PRODUCTION = REBUILD / 'deploy' / 'production'
PROFILE = deployment_profile.load_production(require_activation=False)
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
