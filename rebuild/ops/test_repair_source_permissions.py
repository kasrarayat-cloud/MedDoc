"""Fictional files only: concrete scope, race, rollback and no-op controls."""
from contextlib import ExitStack, contextmanager, nullcontext
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ops import repair_source_permissions as act

TARGET = 'a' * 40


def stat_copy(info, **changes):
    fields = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
    return SimpleNamespace(**{**fields, **changes})


class FictionalOS:
    """Private proxy: fixture creator ownership represents native UID/GID1000."""
    def __init__(self, uid, gid):
        self.uid, self.gid = uid, gid

    def __getattr__(self, name):
        return getattr(os, name)

    def owner_info(self, info):
        return stat_copy(info, st_uid=1000 if info.st_uid == self.uid else info.st_uid,
                         st_gid=1000 if info.st_gid == self.gid else info.st_gid)

    def fstat(self, fd):
        return self.owner_info(os.fstat(fd))

    def getuid(self):
        return 1000

    geteuid = getuid
    getgid = getuid
    getegid = getuid

    @contextmanager
    def scandir(self, fd):
        with os.scandir(fd) as children:
            yield (SimpleNamespace(name=child.name,
                   stat=lambda follow_symlinks=False, child=child:
                       self.owner_info(child.stat(follow_symlinks=follow_symlinks))) for child in children)


class SourcePermissionRepairTests(unittest.TestCase):
    def setUp(self):
        self.native_os = FictionalOS(os.getuid(), os.getgid())
        self.real_metadata = act.metadata
        self.enterContext(patch.object(act, 'os', self.native_os))
        self.enterContext(patch.object(act, 'metadata', side_effect=lambda info:
            self.real_metadata(self.native_os.owner_info(info))))

    def fixture(self, tree):
        tree.chmod(0o755)
        files = {'rebuild/ops/app.py': b'fictional public source\n',
                 'rebuild/static/fonts/font.txt': b'fictional public font\n',
                 'rebuild/.env.example': b'FICTIONAL_BLANK_SETTING=\n'}
        for name, raw in files.items():
            path = tree / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o664 if name.endswith('.py') else 0o600)
        for relative in ('rebuild', 'rebuild/ops', 'rebuild/static'):
            (tree / relative).chmod(0o775)
        (tree / 'rebuild/static/fonts').chmod(0o700)
        private = tree / 'rebuild/.runtime'
        private.mkdir(mode=0o700)
        (private / 'owner').mkdir(mode=0o700)
        canary = private / 'private.txt'
        canary.write_bytes(b'fictional private canary')
        canary.chmod(0o600)
        (tree / 'rebuild/.env').write_bytes(b'FICTIONAL_PRIVATE_CANARY=private\n')
        (tree / 'rebuild/.env').chmod(0o600)
        indexed = {name: 0o644 for name in files}
        paths = set(files)
        for path in files:
            paths.update(str(parent) for parent in Path(path).parents)
        rows = []
        for name in sorted(paths):
            path = tree / name
            row = {'path': name, 'kind': 'file' if name in files else 'directory',
                   **act.metadata(path.stat())}
            row['target_mode'] = indexed[name] if name in files else (0o755 if name == act.DIRECTORY else row['mode'])
            if name in files:
                row['sha256'] = act.sha(files[name])
            rows.append(row)
        native = {'fictional': 'native identity', 'root': act.metadata(tree.stat())}
        value = {'format': 1, 'root': str(tree), 'installed_commit': act.INSTALLED, 'native_identity': native,
                 'inventory': rows, 'candidates': [row.copy() for row in rows if row['mode'] != row['target_mode']]}
        stopped = {'fictional-unit': {'ActiveState': 'inactive', 'MainPID': '0', 'InvocationID': ''}}
        stack = ExitStack()
        stack.enter_context(patch.object(act, 'ROOT', tree))
        stack.enter_context(patch.object(act, 'OUTPUT', private / 'exclusive-output'))
        stack.enter_context(patch.object(act, 'ATTEMPT', private / 'owner/exclusive-attempt'))
        stack.enter_context(patch.object(act, 'installed_index', return_value=indexed))
        stack.enter_context(patch.object(act, 'git', side_effect=lambda root, *args: files[args[-1].split(':', 1)[1]]))
        stack.enter_context(patch.object(act, 'operation_locks', return_value=nullcontext()))
        stack.enter_context(patch.object(act, 'native_identity', return_value=native))
        stack.enter_context(patch.object(act, 'stopped_state', return_value=stopped))
        return stack, value, files, stopped

    def execute(self, manifest, execute=True):
        return act.repair(manifest, act.encode(manifest), {'operator_commit': TARGET}, execute=execute)

    def test_default_never_reads_state_or_authority(self):
        with patch.object(act, 'load_contract', side_effect=AssertionError('authority read')), \
             patch.object(act, 'source_gate', side_effect=AssertionError('source read')), \
             patch.object(act, 'repair', side_effect=AssertionError('mutation')):
            self.assertEqual(act.main([]), 0)

    def test_requires_ruled_door_before_any_installed_read(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(act, 'source_gate', side_effect=AssertionError('source read')):
            with self.assertRaisesRegex(act.Refusal, 'normal_ruled_door'):
                act.main(['--execute', '--operator-commit', TARGET])

    def test_exact_repair_preserves_every_byte_and_private_modes(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, files, _ = self.fixture(tree)
            with stack:
                result = self.execute(manifest)
                self.assertTrue(result['complete'])
                for row in manifest['inventory']:
                    path = tree / row['path']
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), row['target_mode'])
                    if row['kind'] == 'file':
                        self.assertEqual(path.read_bytes(), files[row['path']])
                self.assertEqual(stat.S_IMODE((tree / 'rebuild/.env').stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE((tree / 'rebuild/.runtime/private.txt').stat().st_mode), 0o600)
                self.assertEqual((act.OUTPUT / 'original-inventory.json').read_bytes(), act.encode(manifest))
                for path in (act.ATTEMPT, act.OUTPUT / 'complete.json', act.OUTPUT / 'original-inventory.json'):
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_readonly_validates_whole_population_without_chmod_or_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            stack, manifest, _, _ = self.fixture(Path(temporary))
            with stack, patch.object(act.os, 'fchmod', side_effect=AssertionError('chmod forbidden')):
                self.assertTrue(self.execute(manifest, execute=False)['readonly'])
                self.assertFalse(act.OUTPUT.exists())
                self.assertFalse(act.ATTEMPT.exists())

    def test_source_byte_mismatch_refuses_before_any_action(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, _, _ = self.fixture(tree)
            path = tree / 'rebuild/ops/app.py'
            path.write_bytes(b'changed source same length')
            with stack, patch.object(act.os, 'fchmod', side_effect=AssertionError('chmod forbidden')):
                with self.assertRaises(act.Refusal):
                    self.execute(manifest)
                self.assertFalse(act.OUTPUT.exists())
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o664)

    def test_manifest_content_cannot_replace_installed_git_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, _, _ = self.fixture(tree)
            (tree / 'rebuild/ops/app.py').write_bytes(b'changed source same length')
            for population in (manifest['inventory'], manifest['candidates']):
                row = next(row for row in population if row['path'] == 'rebuild/ops/app.py')
                row['size'] = (tree / row['path']).stat().st_size
                row['sha256'] = act.sha((tree / row['path']).read_bytes())
            with stack, self.assertRaisesRegex(act.Refusal, 'installed_byte_identity'):
                self.execute(manifest)

    def test_symlink_file_parent_and_hardlink_refuse_without_touching_canary(self):
        for variant in ('file', 'parent', 'hardlink'):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                tree = Path(temporary)
                stack, manifest, _, _ = self.fixture(tree)
                canary = tree / 'rebuild/.runtime/private.txt'
                source = tree / 'rebuild/ops/app.py'
                if variant == 'parent':
                    source.parent.rename(tree / 'rebuild/retained-ops')
                    source.parent.symlink_to(tree / 'rebuild/retained-ops', target_is_directory=True)
                else:
                    source.unlink()
                    if variant == 'file':
                        source.symlink_to(canary)
                    else:
                        os.link(canary, source)
                with stack, patch.object(act.os, 'fchmod', side_effect=AssertionError('chmod forbidden')):
                    with self.assertRaises((OSError, act.Refusal)):
                        self.execute(manifest)
                    self.assertEqual(canary.read_bytes(), b'fictional private canary')
                    self.assertEqual(stat.S_IMODE(canary.stat().st_mode), 0o600)
                    self.assertFalse(act.ATTEMPT.exists())

    def test_metadata_and_special_mode_drift_refuse_before_any_mode_changes(self):
        for field in ('uid', 'gid', 'ino', 'dev', 'nlink', 'size', 'mode'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                tree = Path(temporary)
                stack, manifest, _, _ = self.fixture(tree)
                row = next(row for row in manifest['inventory'] if row['kind'] == 'file')
                row[field] += 1
                with stack, patch.object(act.os, 'fchmod', side_effect=AssertionError('chmod forbidden')):
                    with self.assertRaisesRegex(act.Refusal, 'inventory_metadata'):
                        self.execute(manifest)
                    self.assertFalse(act.OUTPUT.exists())
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, _, _ = self.fixture(tree)
            source = tree / 'rebuild/ops/app.py'
            source.chmod(0o4664)
            with stack, self.assertRaises(act.Refusal):
                self.execute(manifest)
            self.assertEqual(stat.S_IMODE(source.stat().st_mode), 0o4664)

    def test_candidates_cannot_widen_to_env_runtime_untracked_or_other_directory(self):
        for name in ('rebuild/.env', 'rebuild/.runtime/private.txt', 'rebuild/untracked.py', 'rebuild/ops'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                stack, manifest, _, _ = self.fixture(Path(temporary))
                manifest['candidates'][0]['path'] = name
                with stack, patch.object(act.os, 'fchmod', side_effect=AssertionError('chmod forbidden')):
                    with self.assertRaisesRegex(act.Refusal, 'candidate_scope'):
                        self.execute(manifest)
                    self.assertFalse(act.OUTPUT.exists())

    def test_candidate_and_complete_inventory_must_be_exact(self):
        for population in ('inventory', 'candidates'):
            for variant in ('omit', 'duplicate'):
                with self.subTest(population=population, variant=variant), tempfile.TemporaryDirectory() as temporary:
                    stack, manifest, _, _ = self.fixture(Path(temporary))
                    if variant == 'omit':
                        manifest[population].pop()
                    else:
                        manifest[population].append(manifest[population][0].copy())
                    with stack, patch.object(act.os, 'fchmod', side_effect=AssertionError('chmod forbidden')):
                        with self.assertRaises(act.Refusal):
                            self.execute(manifest)

    def test_inode_replacement_with_identical_content_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, files, _ = self.fixture(tree)
            path = tree / 'rebuild/ops/app.py'
            replacement = tree / 'rebuild/.runtime/replacement'
            replacement.write_bytes(files['rebuild/ops/app.py'])
            replacement.chmod(0o664)
            replacement.replace(path)
            with stack, self.assertRaisesRegex(act.Refusal, 'inventory_metadata'):
                self.execute(manifest)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o664)

    def test_attempt_or_output_reuse_refuses(self):
        for name in ('ATTEMPT', 'OUTPUT'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                stack, manifest, _, _ = self.fixture(Path(temporary))
                with stack:
                    path = getattr(act, name)
                    path.symlink_to(path.parent / 'missing')
                    with patch.object(act, 'operation_locks', side_effect=AssertionError('no locks on reuse')):
                        with self.assertRaisesRegex(act.Refusal, 'attempt_consumed'):
                            self.execute(manifest)

    def test_service_race_before_marker_refuses_without_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            stack, manifest, _, stopped = self.fixture(Path(temporary))
            with stack, patch.object(act, 'stopped_state', side_effect=[stopped, {'changed': True}]), \
                 patch.object(act.os, 'fchmod', side_effect=AssertionError('chmod forbidden')):
                with self.assertRaisesRegex(act.Refusal, 'service_race'):
                    self.execute(manifest)
                self.assertFalse(act.ATTEMPT.exists())
                self.assertFalse(act.OUTPUT.exists())

    def test_service_race_after_first_change_rolls_back_own_modes_and_consumes_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, _, stopped = self.fixture(tree)
            with stack, patch.object(act, 'stopped_state', side_effect=[stopped, stopped, stopped, {'changed': True}]):
                with self.assertRaisesRegex(act.Refusal, 'service_race'):
                    self.execute(manifest)
                failure = json.loads((act.OUTPUT / 'failed.json').read_bytes())
                self.assertEqual(failure['rollback'], {manifest['candidates'][0]['path']: True})
                self.assertTrue(act.ATTEMPT.exists())
                for row in manifest['inventory']:
                    self.assertEqual(stat.S_IMODE((tree / row['path']).stat().st_mode), row['mode'])
                with self.assertRaisesRegex(act.Refusal, 'attempt_consumed'):
                    self.execute(manifest)

    def test_chmod_failure_immediately_after_action_rolls_back_and_suppresses_arbitrary_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, _, _ = self.fixture(tree)
            original_chmod, calls = os.fchmod, []
            def fail_after_first(fd, mode):
                original_chmod(fd, mode)
                calls.append(mode)
                if len(calls) == 1:
                    raise RuntimeError('FICTIONAL_SECRET_MUST_NOT_ESCAPE')
            with stack, patch.object(act.os, 'fchmod', side_effect=fail_after_first):
                with self.assertRaisesRegex(act.Refusal, 'operation_failed'):
                    self.execute(manifest)
                receipt = (act.OUTPUT / 'failed.json').read_bytes()
                self.assertNotIn(b'FICTIONAL_SECRET', receipt)
                self.assertTrue(all(json.loads(receipt)['rollback'].values()))
                row = manifest['candidates'][0]
                self.assertEqual(stat.S_IMODE((tree / row['path']).stat().st_mode), row['mode'])

    def test_running_service_state_is_fixed_readonly_refusal(self):
        properties = {'ActiveState': 'active', 'SubState': 'running', 'MainPID': '123',
                      'InvocationID': 'a' * 32, 'ActiveEnterTimestampMonotonic': '1',
                      'InactiveEnterTimestampMonotonic': '0', 'ExecMainStartTimestampMonotonic': '1'}
        with patch.object(act, 'command', return_value=''.join(k + '=' + v + '\n' for k, v in properties.items()).encode()) as cmd:
            with self.assertRaisesRegex(act.Refusal, 'services_not_stopped'):
                act.stopped_state()
            self.assertEqual(cmd.call_args.args[0][1], 'show')

    def test_path_gate_refuses_private_and_traversal_paths(self):
        for name in ('../rebuild/app.py', '/rebuild/app.py', 'rebuild/../secret', 'rebuild/.env',
                     'rebuild/.runtime/app.py', 'rebuild/.venv/app.py', 'rebuild/node_modules/app.py'):
            with self.subTest(name=name), self.assertRaises(act.Refusal):
                act.source_path(name)
        self.assertEqual(act.source_path('rebuild/.env.example'), 'rebuild/.env.example')

    def test_even_consistently_pinned_foreign_owner_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.py'
            path.write_bytes(b'fictional source')
            path.chmod(0o644)
            info = list(path.stat())
            info[4] = 1001
            foreign = os.stat_result(info)
            row = {'kind': 'file', **act.metadata(foreign), 'sha256': act.sha(path.read_bytes())}
            fd = os.open(path, os.O_RDONLY)
            try:
                with patch.object(act.os, 'fstat', return_value=foreign), \
                     self.assertRaisesRegex(act.Refusal, 'inventory_metadata'):
                    act.verify_fd(fd, row)
            finally:
                os.close(fd)

    def test_manifest_pin_and_native_identity_are_independent_gates(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, _, _ = self.fixture(tree)
            raw = act.encode(manifest)
            contract = {'manifest_path': str(tree / 'rebuild/.runtime/owner-demo-20261006/inventory.json'),
                        'manifest_sha256': act.sha(raw)}
            with stack, patch.object(act, 'protected', return_value=raw):
                self.assertEqual(act.load_manifest(contract)[0], manifest)
                with self.assertRaisesRegex(act.Refusal, 'manifest_pin'):
                    act.load_manifest({**contract, 'manifest_sha256': '0' * 64})
                with patch.object(act, 'native_identity', return_value={'foreign': 'namespace'}), \
                     self.assertRaisesRegex(act.Refusal, 'native_identity'):
                    act.load_manifest(contract)

    def test_unknown_public_child_refuses_before_font_traversal_without_reading_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, _, _ = self.fixture(tree)
            unknown = tree / 'rebuild/static/fonts/unknown-public-secret.txt'
            unknown.write_bytes(b'fictional private canary')
            unknown.chmod(0o644)
            # Pin directory metadata after the new child to exercise names,
            # independently of the directory metadata drift guard.
            for population in (manifest['inventory'], manifest['candidates']):
                row = next(row for row in population if row['path'] == act.DIRECTORY)
                row.update(act.metadata(unknown.parent.stat()))
            with stack, patch.object(act.os, 'fchmod', side_effect=AssertionError('chmod forbidden')):
                with self.assertRaisesRegex(act.Refusal, 'directory_unknown_child'):
                    self.execute(manifest)
                self.assertEqual(stat.S_IMODE(unknown.parent.stat().st_mode), 0o700)
                self.assertEqual(unknown.read_bytes(), b'fictional private canary')
                self.assertFalse(act.ATTEMPT.exists())

    def test_unknown_child_race_rolls_back_directory_mode_even_when_its_size_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, _, _ = self.fixture(tree)
            original_chmod = os.fchmod
            unknown = tree / 'rebuild/static/fonts/unknown-public-secret.txt'
            def race(fd, mode):
                original_chmod(fd, mode)
                if stat.S_ISDIR(os.fstat(fd).st_mode) and mode == 0o755:
                    unknown.write_bytes(b'fictional private canary')
                    unknown.chmod(0o644)
            with stack, patch.object(act.os, 'fchmod', side_effect=race):
                with self.assertRaises(act.Refusal):
                    self.execute(manifest)
                self.assertEqual(stat.S_IMODE(unknown.parent.stat().st_mode), 0o700)
                self.assertEqual(unknown.read_bytes(), b'fictional private canary')
                self.assertEqual(stat.S_IMODE(unknown.stat().st_mode), 0o644)
                failure = json.loads((act.OUTPUT / 'failed.json').read_bytes())
                self.assertTrue(failure['rollback'][act.DIRECTORY])
                self.assertTrue(all(failure['rollback'].values()))

    def test_command_preserves_native_cli_auth_without_forwarding_application_secrets(self):
        native = {'HOME': '/fictional/native/home', 'GH_TOKEN': 'fictional-existing-token',
                  'GH_CONFIG_DIR': '/fictional/native/config', 'XDG_CONFIG_HOME': '/fictional/native/xdg',
                  'GITHUB_TOKEN': 'fictional-existing-github-token', 'PATH': '/untrusted',
                  'QUILLMD_API_KEY': 'fictional-private-provider', 'STRIPE_SECRET_KEY': 'fictional-private-stripe',
                  'BASH_ENV': '/fictional/bootstrap', 'GIT_DIR': '/fictional/foreign-git'}
        with patch.dict(os.environ, native, clear=True), \
             patch.object(act.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=b'cited')) as run:
            self.assertEqual(act.command(['/usr/bin/gh', 'repo', 'view']), b'cited')
            child = run.call_args.kwargs['env']
            for key in act.NATIVE_CLI_ENV:
                self.assertEqual(child[key], native[key])
            self.assertEqual(set(child), set(act.NATIVE_CLI_ENV) | set(act.PATH_ENV))
            self.assertEqual(child['PATH'], act.PATH_ENV['PATH'])

    def test_xattr_on_file_or_parent_refuses_without_any_mode_change(self):
        for name in ('rebuild/ops/app.py', 'rebuild/static/fonts'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                tree = Path(temporary)
                stack, manifest, _, _ = self.fixture(tree)
                path = tree / name
                os.setxattr(path, 'user.fictional-private-metadata', b'fictional-value')
                with stack, patch.object(act.os, 'fchmod', side_effect=AssertionError('chmod forbidden')):
                    with self.assertRaisesRegex(act.Refusal, 'inventory_xattrs'):
                        self.execute(manifest)
                    self.assertEqual(os.getxattr(path, 'user.fictional-private-metadata'), b'fictional-value')
                    self.assertFalse(act.ATTEMPT.exists())

    def test_same_inode_content_race_restores_private_mode_without_restoring_other_writer_bytes(self):
        for drift in ('content', 'size', 'xattrs'):
            with self.subTest(drift=drift), tempfile.TemporaryDirectory() as temporary:
                tree = Path(temporary)
                stack, manifest, files, _ = self.fixture(tree)
                row = manifest['candidates'][0]
                self.assertEqual(row['mode'], 0o600)
                path = tree / row['path']
                original_chmod = os.fchmod
                concurrent = b'X' * (len(files[row['path']]) + (drift == 'size'))
                def race(fd, mode):
                    original_chmod(fd, mode)
                    if os.fstat(fd).st_ino == row['ino'] and mode == row['target_mode']:
                        path.write_bytes(concurrent)
                        if drift == 'xattrs':
                            os.setxattr(path, 'user.fictional-concurrent', b'fictional-value')
                with stack, patch.object(act.os, 'fchmod', side_effect=race):
                    with self.assertRaises(act.Refusal):
                        self.execute(manifest)
                    self.assertEqual(path.stat().st_ino, row['ino'])
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                    self.assertEqual(path.read_bytes(), concurrent)
                    if drift == 'xattrs':
                        self.assertEqual(os.getxattr(path, 'user.fictional-concurrent'), b'fictional-value')
                    self.assertTrue(json.loads((act.OUTPUT / 'failed.json').read_bytes())['rollback'][row['path']])

    def test_operator_leaf_symlink_and_private_regular_file_never_read_private_bytes(self):
        for kind in ('symlink', 'private-file'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                tree = Path(temporary)
                tree.chmod(0o755)
                public = tree / 'public.py'
                public.write_bytes(b'fictional public source')
                public.chmod(0o644)
                canary = tree / 'private.env'
                canary.write_bytes(b'fictional private canary')
                canary.chmod(0o600)
                original_open = act.open_relative
                def replace_before_open(root_fd, relative, directory=False):
                    if relative == 'public.py' and public.exists() and not public.is_symlink():
                        public.unlink()
                        if kind == 'symlink':
                            public.symlink_to(canary)
                        else:
                            canary.replace(public)
                    return original_open(root_fd, relative, directory)
                with patch.object(act, 'SOURCE', tree), \
                     patch.object(act, 'open_relative', side_effect=replace_before_open), \
                     patch.object(act.os, 'read', side_effect=AssertionError('private bytes read')):
                    with self.assertRaises((OSError, act.Refusal)):
                        act.operator_bytes('public.py')

    def test_checked_citation_and_library_replacements_cannot_change_executed_buffers(self):
        assignment = b'_RA_LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/runs-api.sh"'
        top = assignment + b'\n. "$_RA_LIB"\n[ "$SOURCE_VALUE" = "checked" ] || exit 41\n'
        library = b'SOURCE_VALUE=checked\n'
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            (tree / 'scripts/lib').mkdir(parents=True)
            top_path, library_path = tree / 'scripts/check-citation.sh', tree / 'scripts/lib/runs-api.sh'
            top_path.write_bytes(top)
            library_path.write_bytes(library)
            def checked_command(argv, cwd=None, pass_fds=()):
                top_path.write_bytes(b'exit 77\n')
                library_path.write_bytes(b'exit 88\n')
                self.assertEqual(len(pass_fds), 2)
                for fd in pass_fds:
                    with self.assertRaises(OSError):
                        os.write(fd, b'unreviewed code')
                self.assertEqual(os.pread(pass_fds[1], 65536, 0), library)
                result = subprocess.run(argv, cwd=cwd, pass_fds=pass_fds, capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(argv[1].startswith('/proc/self/fd/'))
                return result.stdout
            with patch.object(act, 'SOURCE', tree), patch.object(act, 'command', side_effect=checked_command):
                act.sealed_citation(top, library, TARGET)

    def test_citation_adaptation_requires_one_exact_canonical_library_assignment(self):
        for top in (b'exit 0\n', b'_RA_LIB=unreviewed\n'):
            with self.subTest(top=top), patch.object(act, 'command', side_effect=AssertionError('execution forbidden')):
                with self.assertRaisesRegex(act.Refusal, 'citation_library_assignment'):
                    act.sealed_citation(top, b'fictional library', TARGET)

    def test_directory_xattr_race_restores_original_mode_and_leaves_new_attribute_untouched(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, _, _ = self.fixture(tree)
            path = tree / act.DIRECTORY
            original_chmod = os.fchmod
            def race(fd, mode):
                original_chmod(fd, mode)
                if stat.S_ISDIR(os.fstat(fd).st_mode) and mode == 0o755:
                    os.setxattr(fd, 'user.fictional_refutation', b'fictional only')
            with stack, patch.object(act.os, 'fchmod', side_effect=race):
                with self.assertRaisesRegex(act.Refusal, 'inventory_xattrs'):
                    self.execute(manifest)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o700)
                self.assertEqual(os.getxattr(path, 'user.fictional_refutation'), b'fictional only')
                failure = json.loads((act.OUTPUT / 'failed.json').read_bytes())
                self.assertTrue(failure['rollback'][act.DIRECTORY])
                self.assertTrue(all(failure['rollback'].values()))

    def test_late_hardlink_refuses_normal_admission_and_restores_only_original_inode_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            stack, manifest, files, _ = self.fixture(tree)
            row = manifest['candidates'][0]
            path = tree / row['path']
            alias = tree / 'rebuild/.runtime/external-alias'
            original_chmod = os.fchmod
            def race(fd, mode):
                original_chmod(fd, mode)
                if os.fstat(fd).st_ino == row['ino'] and mode == row['target_mode']:
                    os.link(path, alias)
            with stack, patch.object(act.os, 'fchmod', side_effect=race):
                with self.assertRaisesRegex(act.Refusal, 'inventory_metadata'):
                    self.execute(manifest)
                self.assertEqual(path.stat().st_ino, row['ino'])
                self.assertEqual(path.stat().st_nlink, 2)
                self.assertEqual(alias.stat().st_ino, row['ino'])
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
                self.assertEqual(path.read_bytes(), files[row['path']])
                self.assertEqual(alias.read_bytes(), files[row['path']])
                failure = json.loads((act.OUTPUT / 'failed.json').read_bytes())
                self.assertTrue(failure['rollback'][row['path']])
                self.assertFalse(failure['preservation_verified'])
                self.assertFalse(failure['external_drift_adjudicated'])
                self.assertEqual(failure['rollback_scope'], 'original_admitted_inode_modes_only')

    def test_corrective_rollback_still_refuses_foreign_owner_or_changed_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'source.py'
            path.write_bytes(b'fictional public source')
            path.chmod(0o644)
            admitted = path.stat()
            row = {'kind': 'file', **act.metadata(admitted)}
            fd = os.open(path, os.O_RDONLY)
            try:
                for field, value in ((4, 1001), (5, 1001), (0, stat.S_IFDIR | 0o644)):
                    with self.subTest(field=field):
                        changed = list(admitted)
                        changed[field] = value
                        with patch.object(act.os, 'fstat', return_value=os.stat_result(changed)), \
                             self.assertRaisesRegex(act.Refusal, 'rollback_file_identity'):
                            act.rollback_identity(fd, row, 0o644)
            finally:
                os.close(fd)

    def test_ci_uid_gid1001_representation_exercises_successful_repair_and_foreign_refusal(self):
        uid, gid = os.getuid(), os.getgid()
        ci_os = FictionalOS(1001, 1001)
        normalize = ci_os.owner_info
        represented = set()
        def ci_owner_info(info):
            observed = stat_copy(info, st_uid=1001 if info.st_uid == uid else info.st_uid,
                                 st_gid=1001 if info.st_gid == gid else info.st_gid)
            represented.add((observed.st_uid, observed.st_gid))
            return normalize(observed)
        ci_os.owner_info = ci_owner_info
        with patch.object(act, 'os', ci_os), patch.object(act, 'metadata', side_effect=lambda info:
                self.real_metadata(ci_os.owner_info(info))), tempfile.TemporaryDirectory() as temporary:
            stack, manifest, _, _ = self.fixture(Path(temporary))
            with stack:
                self.assertTrue(self.execute(manifest)['complete'])
                self.assertIn((1001, 1001), represented)
                row = manifest['candidates'][0]
                fd = os.open(Path(temporary) / row['path'], os.O_RDONLY)
                try:
                    foreign = stat_copy(os.fstat(fd), st_uid=1002, st_gid=1002)
                    with patch.object(ci_os, 'fstat', return_value=foreign), \
                         self.assertRaisesRegex(act.Refusal, 'inventory_metadata'):
                        act.verify_fd(fd, row, row['target_mode'])
                finally:
                    os.close(fd)

    def test_operator_source_paths_cannot_replace_native_repair_result_or_receipt_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            tree = Path(temporary)
            operator = tree / '.worktrees/operator'
            operator.mkdir(parents=True)
            stack, manifest, _, _ = self.fixture(tree)
            operator_paths = sorted(act.ALLOWED)
            native_paths = sorted(row['path'] for row in manifest['candidates'])
            self.assertNotEqual(native_paths, operator_paths)
            canonical = b'fictional checked operator bytes'
            def source_git(root, *args):
                if args == ('rev-parse', 'HEAD'):
                    return (TARGET if root == operator else act.INSTALLED).encode()
                if args[0] in ('status', 'merge-base'):
                    return b''
                if args[0] == 'diff':
                    return ('\n'.join(operator_paths) + '\n').encode()
                if args[0] == 'branch':
                    return b'main'
                if args == ('rev-parse', 'origin/main'):
                    return TARGET.encode()
                if args[0] == 'ls-files':
                    return b''.join((('100644 ' + 'a' * 40 + ' 0\t' + name + '\0').encode())
                                    for name in ('scripts/check-citation.sh', 'scripts/lib/runs-api.sh'))
                if args[0] == 'show':
                    return canonical
                raise AssertionError(args)
            with stack:
                with patch.object(act, 'SOURCE', operator), patch.object(act, 'git', side_effect=source_git), \
                     patch.object(act, 'operator_bytes', return_value=canonical), patch.object(act, 'sealed_citation'):
                    source = act.source_gate(TARGET)
                readonly = act.repair(manifest, act.encode(manifest), source, execute=False)
                self.assertNotIn('changed_paths', readonly)
                self.assertEqual(readonly['operator_changed_paths'], operator_paths)
                self.assertFalse(act.ATTEMPT.exists())
                result = act.repair(manifest, act.encode(manifest), source, execute=True)
                receipt = json.loads((act.OUTPUT / 'complete.json').read_bytes())
                for value in (result, receipt):
                    self.assertEqual(value['changed_paths'], native_paths)
                    self.assertEqual(value['operator_changed_paths'], operator_paths)


if __name__ == '__main__':
    unittest.main()
