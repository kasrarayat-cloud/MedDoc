"""Offline controls for the code-only rebuild release installer (interpretation 67, D1-D4).

Nothing here reaches the live host: git runs in temporary repositories, and the act runs against fakes of the
engine's primitives. The real engine module is imported only for its pure helpers and its own source text.
"""
import ast
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ops import activate_core_workflow_repair as engine_module
from ops import install_rebuild_release as op
from ops import venv_footprint as footprint

BASE = '1' * 40
CANDIDATE = '2' * 40
GIT_ENV = {'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_AUTHOR_NAME': 'test',
           'GIT_AUTHOR_EMAIL': 'test@example.invalid', 'GIT_COMMITTER_NAME': 'test',
           'GIT_COMMITTER_EMAIL': 'test@example.invalid'}


def git(repo, *arguments):
    return subprocess.run(['git', '-C', str(repo), *arguments], check=True, capture_output=True,
                          env={**os.environ, **GIT_ENV}).stdout.decode().strip()


def commit(repo, files, message='change', remove=()):
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, tuple):
            path.symlink_to(content[1])
        else:
            path.write_bytes(content if isinstance(content, bytes) else content.encode())
    for name in remove:
        (repo / name).unlink()
    git(repo, 'add', '-A')
    git(repo, 'commit', '-q', '--no-verify', '-m', message)
    return git(repo, 'rev-parse', 'HEAD')


def new_repo(root):
    repo = root / 'repo'
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'main')
    return repo


class GitIsolation(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        environment = patch.dict(os.environ, GIT_ENV)
        environment.start()
        self.addCleanup(environment.stop)
        self.addCleanup(self.temporary.cleanup)


class ManifestTests(GitIsolation):
    def test_raw_diff_parsing_refuses_every_malformed_or_renamed_record(self):
        raw = (b':000000 100644 ' + b'0' * 40 + b' ' + b'a' * 40 + b' A\0new.py\0'
               b':100644 100755 ' + b'b' * 40 + b' ' + b'c' * 40 + b' M\0rebuild/x.py\0')
        self.assertEqual(op.parse_raw_diff(raw), [('A', '000000', '100644', '0' * 40, 'a' * 40, 'new.py'),
                                                  ('M', '100644', '100755', 'b' * 40, 'c' * 40, 'rebuild/x.py')])
        self.assertEqual(op.parse_raw_diff(b''), [])
        for bad in (b':100644 100644 ' + b'b' * 40 + b' ' + b'c' * 40 + b' R100\0old\0new\0',
                    b':100644 100644 short short M\0x\0', b'no metadata\0x\0', raw[:-1],
                    b':000000 100644 ' + b'0' * 40 + b' ' + b'a' * 40 + b' A\0'):
            with self.subTest(bad=bad), self.assertRaises(op.Refusal):
                op.parse_raw_diff(bad)

    def test_classification_and_every_structural_refusal(self):
        self.assertEqual(op.classify('rebuild/core/x.py', 'M'), 'runtime')
        self.assertEqual(op.classify('rebuild/requirements.txt', 'M'), 'requirements')
        self.assertEqual(op.classify('rebuild/static/app.js', 'M'), 'static')
        self.assertEqual(op.classify('rebuild/core/tests/test_x.py', 'A'), 'support')
        self.assertEqual(op.classify('rebuild/ops/test_x.py', 'A'), 'support')
        self.assertEqual(op.classify('cpt-studio/studio/migrations/0001_x.py', 'A'), 'passenger')
        self.assertEqual(op.classify('.github/workflows/test.yml', 'M'), 'passenger')
        refused = [('rebuild/core/x.py', 'D'), ('rebuild/core/x.py', 'T'), ('rebuild/core/migrations/0040_x.py', 'A'),
                   ('rebuild/deploy/quillmd-fresh-worker.service', 'M'), ('rebuild/staticfiles/app.js', 'A'),
                   ('rebuild/static/fonts/x.ttf', 'A'), ('apps/x/node_modules/y.js', 'A'), ('rebuild/.venv/x', 'A'),
                   ('docs/backups/x.md', 'A'), ('/abs.py', 'A'), ('a//b.py', 'A'), ('./a.py', 'A'), ('../a.py', 'A'),
                   ('a\\b.py', 'A'), ('a\nb.py', 'A'), ('scripts/hooks/post-merge', 'A')]
        for name, status in refused:
            with self.subTest(name=name, status=status), self.assertRaises(op.Refusal):
                op.classify(name, status, hooks=frozenset({'scripts/hooks/post-merge'}))

    def test_manifest_rows_modes_sizes_and_digest(self):
        blobs = {'a' * 40: b'new', 'b' * 40: b'old', 'c' * 40: b'x' * (op.BLOB_LIMIT + 1)}
        entries = [('A', '000000', '100644', '0' * 40, 'a' * 40, 'docs/z.md'),
                   ('M', '100644', '100755', 'b' * 40, 'a' * 40, 'rebuild/core/a.py')]
        manifest = op.build_manifest(BASE, entries, blobs.__getitem__)
        self.assertEqual(manifest['paths']['rebuild/core/a.py']['base_sha256'], op.sha(b'old'))
        self.assertEqual(op.manifest_digest(manifest),
                         op.manifest_digest(op.build_manifest(BASE, list(reversed(entries)), blobs.__getitem__)))
        variants = [[('A', '000000', '120000', '0' * 40, 'a' * 40, 'link')],
                    [('A', '000000', '160000', '0' * 40, 'a' * 40, 'module')],
                    [('M', '120000', '100644', 'b' * 40, 'a' * 40, 'x.py')],
                    [('A', '100644', '100644', 'b' * 40, 'a' * 40, 'x.py')],
                    [('A', '000000', '100644', '0' * 40, 'c' * 40, 'big.bin')],
                    entries + [entries[0]], []]
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(op.Refusal):
                op.build_manifest(BASE, variant, blobs.__getitem__)

    def test_facts_name_runtime_dot_and_static_paths(self):
        rows = {'rebuild/core/a.py': 'runtime', 'rebuild/requirements.txt': 'requirements',
                'rebuild/static/app.js': 'static', 'cpt-studio/.gitignore': 'passenger', 'docs/x.md': 'passenger'}
        manifest = {'format': op.MANIFEST_FORMAT, 'base': BASE,
                    'paths': {n: {'status': 'M', 'class': c} for n, c in rows.items()}}
        facts = op.manifest_facts(manifest)
        self.assertEqual(facts['runtime_paths'], ['rebuild/core/a.py', 'rebuild/requirements.txt'])
        self.assertEqual(facts['dot_paths'], ['cpt-studio/.gitignore'])
        self.assertEqual(facts['static'], ['app.js'])
        self.assertEqual(facts['paths']['classes'], {'passenger': 2, 'requirements': 1, 'runtime': 1, 'static': 1})

    def test_requirements_change_is_admitted_only_with_the_venv_footprint_check(self):
        manifest = {'paths': {'rebuild/requirements.txt': {}}}
        self.assertTrue(op.admit_requirements(manifest, True))
        for check in (False, None, 'yes'):
            with self.subTest(check=check), self.assertRaises(op.Refusal):
                op.admit_requirements(manifest, check)
        self.assertTrue(op.admit_requirements({'paths': {'rebuild/core/a.py': {}}}, False))

    def test_manifest_from_a_real_repository_and_its_refusals(self):
        repo = new_repo(self.root)
        base = commit(repo, {'rebuild/core/a.py': 'one\n', 'rebuild/requirements.txt': 'pypdf==6.21.1\n',
                             'docs/old.md': 'old\n'})
        candidate = commit(repo, {'rebuild/core/a.py': 'two\n', 'rebuild/requirements.txt': 'pypdf==6.21.4\n',
                                  'cpt-studio/.gitignore': '*.pyc\n'})
        manifest = op.compute_manifest(repo, base, candidate, frozenset())
        self.assertEqual({n: r['status'] for n, r in manifest['paths'].items()},
                         {'cpt-studio/.gitignore': 'A', 'rebuild/core/a.py': 'M', 'rebuild/requirements.txt': 'M'})
        self.assertEqual(manifest['paths']['rebuild/core/a.py']['sha256'], op.sha(b'two\n'))
        for files, remove in (({}, ('docs/old.md',)), ({'link': ('symlink', 'docs/old.md')}, ()),
                              ({'rebuild/core/migrations/0040_x.py': 'x\n'}, ())):
            with self.subTest(files=files, remove=remove):
                git(repo, 'reset', '-q', '--hard', candidate)
                refused = commit(repo, files, remove=remove)
                with self.assertRaises(op.Refusal):
                    op.compute_manifest(repo, base, refused, frozenset())


class DeclarationTests(GitIsolation):
    """D4: the declaration lives in the candidate and is tracked, unmodified and committed there."""

    RELATIVE = 'docs/foundation/mutations/20261031-test-install.md'

    def repository(self):
        repo = new_repo(self.root)
        gate = op.SOURCE / 'scripts/lib/declaration.sh'
        base = commit(repo, {'rebuild/core/a.py': 'one\n', 'rebuild/requirements.txt': 'pypdf==6.21.1\n',
                             'scripts/lib/declaration.sh': gate.read_bytes()}, 'base')
        code = commit(repo, {'rebuild/core/a.py': 'two\n', 'rebuild/requirements.txt': 'pypdf==6.21.4\n',
                             'docs/notes.md': 'notes\n'}, 'code')
        return repo, base, code

    def measured(self, repo, base, code):
        manifest = op.compute_manifest(repo, base, code, frozenset())
        return {'manifest': manifest,
                'venv': {'footprint_sha256': 'f' * 64, 'distributions': 64, 'unrecorded_bytecode': 63},
                'requirements_mismatch': {'pypdf': {'required': '6.21.4', 'installed': '6.21.1'}},
                'foreign_venv_units': ['quillmd-corti-candidate.service'],
                'backup': {'report_sha256': 'e' * 64, 'run_id': '20261031T200000Z-0a1b2c3d',
                           'restore_run_id': 'a' * 16},
                'operator': {name: 'd' * 64 for name in op.OPERATOR_FILES}}

    def declare(self, repo, contract, extra=None):
        text = '# Install\n\nThe delta and its baseline.\n\n' + op.contract_block(contract) + '\nStop conditions.\n'
        return commit(repo, {self.RELATIVE: text, **(extra or {})}, 'declaration')

    def checks(self, repo, measured, base, candidate):
        args = SimpleNamespace(base=base, candidate=candidate, declaration=repo / self.RELATIVE)
        checks = op.Checks()
        with patch.object(op, 'SOURCE', repo):
            result = op.declaration_checks(args, checks, measured, executing=False)
        return result, checks

    def test_before_the_declaration_exists_the_contract_to_embed_is_printed_and_the_check_fails(self):
        repo, base, code = self.repository()
        measured = self.measured(repo, base, code)
        result, checks = self.checks(repo, measured, base, code)
        self.assertIsNone(result)
        self.assertFalse(checks.passed)
        contract = measured['contract_to_embed']
        self.assertEqual(contract['code_candidate'], code)
        self.assertEqual(contract['code_manifest_sha256'], op.manifest_digest(measured['manifest']))
        self.assertEqual(op.contract_from(op.contract_block(contract)), contract)

    def test_the_merged_declaration_binds_the_code_and_passes_the_real_strict_gate(self):
        repo, base, code = self.repository()
        measured = self.measured(repo, base, code)
        contract = op.build_contract(code_candidate=code, code_manifest=measured['manifest'], base=base,
                                     venv_summary=measured['venv'], mismatch=measured['requirements_mismatch'],
                                     foreign_units=measured['foreign_venv_units'], backup=measured['backup'],
                                     operator=measured['operator'])
        candidate = self.declare(repo, contract)
        measured['manifest'] = op.compute_manifest(repo, base, candidate, frozenset())
        result, checks = self.checks(repo, measured, base, candidate)
        self.assertTrue(checks.passed, checks.rows)
        self.assertEqual(result['contract'], contract)
        self.assertEqual(result['provenance']['relative'], self.RELATIVE)
        # The runner's commit must be the commit that carries the declaration.
        with patch.object(op, 'SOURCE', repo), self.assertRaises(op.Refusal):
            op.declaration_provenance(repo / self.RELATIVE, candidate, source=repo, runner_commit=base)

    def test_anything_else_in_the_declaration_merge_or_any_drift_refuses(self):
        repo, base, code = self.repository()
        measured = self.measured(repo, base, code)
        contract = op.build_contract(code_candidate=code, code_manifest=measured['manifest'], base=base,
                                     venv_summary=measured['venv'], mismatch=measured['requirements_mismatch'],
                                     foreign_units=measured['foreign_venv_units'], backup=measured['backup'],
                                     operator=measured['operator'])
        candidate = self.declare(repo, contract, extra={'rebuild/core/b.py': 'unreviewed\n'})
        measured['manifest'] = op.compute_manifest(repo, base, candidate, frozenset())
        _, checks = self.checks(repo, measured, base, candidate)
        self.assertIn({'check': 'declaration_contract_matches_measurement', 'passed': False,
                       'reason': 'declaration_is_the_only_delta'}, checks.rows)
        git(repo, 'reset', '-q', '--hard', code)
        candidate = self.declare(repo, contract)
        measured['manifest'] = op.compute_manifest(repo, base, candidate, frozenset())
        drifted = deepcopy(measured)
        drifted['venv']['footprint_sha256'] = '0' * 64
        drifted['foreign_venv_units'] = []
        _, checks = self.checks(repo, drifted, base, candidate)
        self.assertIn({'check': 'declaration_contract_matches_measurement', 'passed': False,
                       'reason': 'contract_differs:foreign_venv_units,venv'}, checks.rows)

    def test_uncommitted_modified_or_misplaced_declarations_refuse(self):
        repo, base, code = self.repository()
        path = repo / self.RELATIVE
        path.parent.mkdir(parents=True)
        path.write_text('draft\n')
        for function in (op.declaration_provenance, op.strict_gate):
            with self.subTest(function=function.__name__, state='untracked'), self.assertRaises(op.Refusal):
                function(path, code, source=repo) if function is op.declaration_provenance else function(path, repo)
        candidate = commit(repo, {}, 'declaration')
        op.declaration_provenance(path, candidate, source=repo)
        op.strict_gate(path, repo)
        path.write_text('edited after the commit\n')
        with self.assertRaises(op.Refusal):
            op.declaration_provenance(path, candidate, source=repo)
        with self.assertRaises(op.Refusal):
            op.strict_gate(path, repo)
        for wrong in (repo / 'docs/foundation/deploys/x.md', repo / 'docs/foundation/mutations/sub/x.md',
                      repo / 'docs/foundation/mutations/x.txt', Path('relative/docs/foundation/mutations/x.md'),
                      self.root / 'elsewhere/docs/foundation/mutations/x.md'):
            with self.subTest(wrong=wrong), self.assertRaises(op.Refusal):
                op.declaration_relative(wrong, repo)

    def test_contract_parsing_is_closed_and_literal(self):
        repo, base, code = self.repository()
        measured = self.measured(repo, base, code)
        contract = op.build_contract(code_candidate=code, code_manifest=measured['manifest'], base=base,
                                     venv_summary=measured['venv'], mismatch=measured['requirements_mismatch'],
                                     foreign_units=measured['foreign_venv_units'], backup=measured['backup'],
                                     operator=measured['operator'])
        block = op.contract_block(contract)
        self.assertEqual(op.contract_from('intro\n' + block + 'tail\n'), contract)
        broken = [block + block, block.replace('```json', '```'), block.rsplit('```', 1)[0],
                  block.replace('"migrations": 0', '"migrations": 0, "migrations": 0')]
        for key, value in (('migrations', 1), ('dependency_installs', 1), ('environment_delta', ['OTHER']),
                           ('extra', 1), ('format', 'other')):
            changed = dict(contract, **{key: value})
            broken.append(op.CONTRACT_MARKER + '\n```json\n' + json.dumps(changed) + '\n```\n')
        venv = dict(contract['venv'], policy='best-effort')
        broken.append(op.CONTRACT_MARKER + '\n```json\n' + json.dumps(dict(contract, venv=venv)) + '\n```\n')
        for text in broken:
            with self.subTest(text=text[:80]), self.assertRaises(op.Refusal):
                op.contract_from(text)

    def test_code_manifest_is_the_full_manifest_minus_exactly_the_added_declaration(self):
        rows = {'rebuild/core/a.py': {'status': 'M'}, self.RELATIVE: {'status': 'A'}}
        full = {'format': op.MANIFEST_FORMAT, 'base': BASE, 'paths': rows}
        code = op.without(full, self.RELATIVE)
        declared = {'code_manifest_sha256': op.manifest_digest(code)}
        entry = ('A', '000000', '100644', '0' * 40, 'a' * 40, self.RELATIVE)
        self.assertEqual(op.code_manifest_for(full, declared, self.RELATIVE, [entry]), code)
        for entries in ([], [entry, ('A', '000000', '100644', '0' * 40, 'b' * 40, 'x.md')],
                        [('M', '100644', '100644', 'a' * 40, 'b' * 40, self.RELATIVE)]):
            with self.subTest(entries=entries), self.assertRaises(op.Refusal):
                op.code_manifest_for(full, declared, self.RELATIVE, entries)
        with self.assertRaises(op.Refusal):
            op.code_manifest_for(full, {'code_manifest_sha256': '0' * 64}, self.RELATIVE, [entry])


class HostReadTests(unittest.TestCase):
    def test_locks_are_read_from_proc_without_taking_them(self):
        with tempfile.TemporaryDirectory() as temporary:
            runtime = Path(temporary)
            (runtime / 'backup-monitor').mkdir()
            lock = runtime / 'backup-monitor/capture.lock'
            lock.write_bytes(b'')
            info = lock.stat()
            held = '1: FLOCK  ADVISORY  WRITE 99 %02x:%02x:%d 0 EOF\n' % (os.major(info.st_dev), os.minor(info.st_dev),
                                                                         info.st_ino)
            rows = op.locks_free(runtime, read=lambda: '2: POSIX ADVISORY READ 5 08:02:1 0 EOF\n')
            self.assertEqual(rows['backup-monitor/capture.lock'], 'free')
            self.assertEqual(rows['legacy-model-activation.lock'], 'absent')
            with self.assertRaises(op.Refusal):
                op.locks_free(runtime, read=lambda: held)
            self.assertIn((os.major(info.st_dev), os.minor(info.st_dev), info.st_ino),
                          op.locked_inodes('1: -> FLOCK ADVISORY WRITE 7 ' + held.split()[5] + ' 0 EOF'))

    def test_scheduled_windows(self):
        import datetime as dt
        day = dt.datetime(2026, 10, 31, tzinfo=dt.timezone.utc)
        for hour, minute in ((4, 19), (4, 51), (5, 11), (19, 0)):
            op.outside_scheduled_windows(day.replace(hour=hour, minute=minute))
        for hour, minute in ((4, 20), (4, 30), (4, 50), (4, 55), (5, 0), (5, 10)):
            with self.subTest(hour=hour, minute=minute), self.assertRaises(op.Refusal):
                op.outside_scheduled_windows(day.replace(hour=hour, minute=minute))

    def test_idle_is_cpu_over_a_window_against_a_small_fraction(self):
        readings = {'a.service': [100, 100 + 2_000], 'b.service': [0, 900_000]}
        ticks = iter([10.0, 20.0])
        value = op.foreign_idle(['a.service', 'b.service'], read=lambda unit: readings[unit].pop(0),
                                clock=lambda: next(ticks), sleep=lambda seconds: None)
        self.assertTrue(value['units']['a.service']['idle'])
        self.assertFalse(value['units']['b.service']['idle'])
        self.assertFalse(value['idle'])
        with self.assertRaises(op.Refusal):
            op.idle_verdict(value)
        empty = op.foreign_idle([], sleep=lambda seconds: None)
        self.assertTrue(empty['idle'])

    def test_venv_sharing_units_come_from_their_exec_start(self):
        shown = {'quillmd-corti-candidate.service':
                 'ExecStart={ path=/opt/meddoc-pro/rebuild/.venv/bin/python ; argv[]=... }\n',
                 'nginx.service': 'ExecStart={ path=/usr/sbin/nginx ; argv[]=... }\n'}
        prior = SimpleNamespace(command=lambda argv: shown[argv[2]].encode())
        self.assertEqual(op.venv_sharing_units(prior, shown), ['quillmd-corti-candidate.service'])
        with self.assertRaises(op.Refusal):
            op.venv_sharing_units(prior, {'bad name; rm': ''})

    def test_live_venv_users_and_the_undeclared_process_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            venv = root / 'venv'
            (venv / 'bin').mkdir(parents=True)
            link = root / 'worktree-venv'
            link.symlink_to(venv)
            proc = root / 'proc'
            processes = {
                '10': ([str(venv / 'bin/python'), '-m', 'gunicorn'], '0::/system.slice/quillmd-corti-candidate.service\n'),
                '11': ([str(link / 'bin/python'), '-m', 'pytest'], '0::/user.slice/user-1000.slice/session-3.scope\n'),
                '12': (['/usr/bin/python3', 'other.py'], '0::/system.slice/other.service\n'),
                '13': (['.venv/bin/python', 'manage.py'], '0::/system.slice/quillmd-fresh-worker.service\n'),
                '14': (['python', 'x'], '0::/system.slice/x.service\n')}
            for pid, (argv, cgroup) in processes.items():
                (proc / pid).mkdir(parents=True)
                (proc / pid / 'cmdline').write_bytes(b'\0'.join(a.encode() for a in argv) + b'\0')
                (proc / pid / 'cgroup').write_text(cgroup)
            (proc / '13' / 'cwd').symlink_to(root)
            os.symlink('venv', root / '.venv')
            (proc / 'self').mkdir()
            users = op.live_venv_users(proc, venv)
            self.assertEqual(users, [{'pid': 10, 'unit': 'quillmd-corti-candidate.service'},
                                     {'pid': 11, 'unit': None},
                                     {'pid': 13, 'unit': 'quillmd-fresh-worker.service'}])
            with self.assertRaises(op.Refusal):
                op.no_undeclared_venv_users(['quillmd-corti-candidate.service'], users)
            allowed = [row for row in users if row['pid'] != 11]
            self.assertEqual(op.no_undeclared_venv_users(['quillmd-corti-candidate.service'], allowed)['processes'], 2)
            self.assertEqual(op.live_venv_users(proc, venv, exclude={10, 11, 13}), [])


class ReportingTests(unittest.TestCase):
    def test_a_failed_check_never_hides_the_ones_after_it_and_held_values_never_reach_the_report(self):
        checks = op.Checks()
        held = checks.keep('release_stamp_renders', lambda: b'QUILLMD_DB_PASSWORD=never-printed\n',
                           describe=lambda _: {'release_stamp_renders': True})
        checks.run('refused', op.require, False, 'a_fixed_label')
        checks.run('later', lambda: {'ran': True})
        checks.run('generic', lambda: (_ for _ in ()).throw(ValueError('row text that must not leak')))
        self.assertEqual(held, b'QUILLMD_DB_PASSWORD=never-printed\n')
        text = json.dumps(checks.rows)
        self.assertNotIn('never-printed', text)
        self.assertNotIn('must not leak', text)
        self.assertEqual([row['passed'] for row in checks.rows], [True, False, True, False])
        self.assertEqual(checks.rows[1]['reason'], 'a_fixed_label')
        self.assertEqual(checks.rows[3]['reason'], 'ValueError')
        self.assertFalse(checks.passed)

    def test_reason_keeps_fixed_labels_only(self):
        self.assertEqual(op.reason(op.Refusal('venv_footprint_changed')), 'venv_footprint_changed')
        self.assertEqual(op.reason(footprint.Refusal('stable_complete_file')), 'stable_complete_file')
        self.assertEqual(op.reason(engine_module.Refusal('owned_units_drained')), 'owned_units_drained')
        self.assertEqual(op.reason(RuntimeError('password=x')), 'RuntimeError')
        self.assertEqual(op.reason(op.Refusal('newline\nin label')), 'Refusal')

    def test_results_are_new_private_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            root.chmod(0o700)
            op.write_result(root / 'result.json', {'passed': True})
            self.assertEqual(oct((root / 'result.json').stat().st_mode & 0o777), '0o600')
            with self.assertRaises(FileExistsError):
                op.write_result(root / 'result.json', {})
            (root / 'open').mkdir(mode=0o755)
            (root / 'open').chmod(0o755)
            with self.assertRaises(op.Refusal):
                op.write_result(root / 'open/result.json', {})


class EngineBindingTests(unittest.TestCase):
    def test_the_pinned_engine_loads_and_any_changed_primitive_refuses(self):
        engine = op.load_engine()
        self.assertIs(engine, engine_module)
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary).resolve()
            shutil.copytree(op.SOURCE / 'rebuild/ops', source / 'rebuild/ops',
                            ignore=shutil.ignore_patterns('__pycache__'))
            (source / 'scripts').mkdir()
            shutil.copy(op.SOURCE / op.STATIC_PRIMITIVES[0], source / op.STATIC_PRIMITIVES[0])
            self.assertEqual(op.pinned_bytes(source), op.ENGINE_PINS)
            target = source / 'rebuild/ops/legacy_model_activation.py'
            target.write_bytes(target.read_bytes() + b'\n')
            with self.assertRaises(op.Refusal):
                op.pinned_bytes(source)

    def test_binding_is_restored_even_after_a_failure(self):
        engine = op.load_engine()
        before = (engine.BASE, engine.SOURCE, engine.STATIC, engine.prior.BASE, engine.prior.SOURCE, engine.prior.STATIC)
        with self.assertRaises(RuntimeError):
            with op.bound(engine, BASE, ['app.js']):
                self.assertEqual((engine.BASE, engine.prior.BASE), (BASE, BASE))
                self.assertEqual((engine.STATIC, engine.prior.STATIC), (frozenset({'app.js'}),) * 2)
                self.assertEqual((engine.SOURCE, engine.prior.SOURCE), (op.SOURCE, op.SOURCE))
                raise RuntimeError
        self.assertEqual(before, (engine.BASE, engine.SOURCE, engine.STATIC, engine.prior.BASE, engine.prior.SOURCE,
                                  engine.prior.STATIC))

    def test_the_engine_renderer_changes_only_the_release_stamp_under_the_binding(self):
        engine = op.load_engine()
        original = ('KEEP=1\nQUILLMD_RELEASE_SHA="' + BASE + '"\nOTHER="a # b"\n').encode()
        with op.bound(engine, BASE):
            self.assertEqual(engine.render_environment(original, CANDIDATE, {}), original.replace(BASE.encode(),
                                                                                                 CANDIDATE.encode()))
            with self.assertRaises(engine.Refusal):
                engine.render_environment(original.replace(BASE.encode(), CANDIDATE.encode()), '3' * 40, {})

    def test_the_guard_exception_for_a_group_writable_base_file_is_removed(self):
        guard = SimpleNamespace(GROUP_WRITABLE_BASE_PATHS=frozenset({'docs/foundation/RULINGS.md'}))
        self.assertEqual(op.bind_guard(guard).GROUP_WRITABLE_BASE_PATHS, frozenset())

    def test_act_follows_the_engine_stage_order_with_only_the_declared_insertions(self):
        def stages(path, function):
            tree = ast.parse(Path(path).read_text())
            body = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == function)
            found = [node for node in ast.walk(body) if isinstance(node, ast.Assign) and len(node.targets) == 1
                     and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'stage'
                     and isinstance(node.value, ast.Constant)]
            return [node.value.value for node in sorted(found, key=lambda node: (node.lineno, node.col_offset))]
        inserted = {'baseline_foreign_idle', 'baseline_venv', 'venv_after_stop', 'foreign_services_after_stop',
                    'foreign_idle_after_resume', 'venv_after_resume'}
        ours = stages(op.__file__, 'act')
        engine = stages(engine_module.__file__, 'execute')
        self.assertTrue(inserted <= set(ours))
        self.assertEqual([stage for stage in ours if stage not in inserted], engine)


class FakeCipher:
    def encrypt(self, raw):
        return b'enc:' + raw

    def decrypt(self, raw):
        return raw[4:]


class World:
    """Fakes of every engine primitive the act calls, recording the order of every host action."""

    UNIT = 'quillmd-corti-candidate.service'

    def __init__(self, root):
        self.root = root
        self.app = root / 'app'
        self.app.mkdir()
        self.env = ('KEEP=1\nQUILLMD_RELEASE_SHA="' + BASE + '"\n').encode()
        (self.app / '.env').write_bytes(self.env)
        (self.app / '.env').chmod(0o600)
        self.calls = []
        self.running = {unit: True for unit in op.OWNED_UNITS}
        self.database = {'tables': {'core_servicehealth': [1, 'h'], 'core_encounter': [5, 'e']},
                         'pending': {'core_job': 0}, 'sequences': {'s': [1, True]}}
        self.services = {self.UNIT: 'MainPID=7\nInvocationID=abc\n'}
        self.faults = {}
        venv_root = root / 'venv'
        (venv_root / 'lib').mkdir(parents=True)
        (venv_root / 'lib/module.py').write_text('x = 1\n')
        self.venv = footprint.snapshot(venv_root)
        (venv_root / 'lib/stray.pyc').write_bytes(b'stray')
        self.changed_venv = footprint.snapshot(venv_root)
        self.venvs = [self.venv, self.venv, self.venv]
        self.idles = [{'idle': True, 'units': {}}, {'idle': True, 'units': {}}]

    def fault(self, name):
        if name in self.faults:
            raise self.faults.pop(name)

    def host(self, helper):
        world = self

        class Host:
            def state(self, unit):
                return {'ActiveState': 'active' if world.running[unit] else 'inactive',
                        'MainPID': '42' if world.running[unit] else '0'}

            def service(self, action, unit):
                world.calls.append((action, unit))
                world.running[unit] = action == 'start'

            def configuration(self):
                world.fault('configuration')
                return {'/etc/systemd/system/x.service': {'sha256': 'a' * 64}}
        return Host()

    @contextmanager
    def locks(self):
        self.calls.append(('locks',))
        yield
        self.calls.append(('locks_released',))

    @contextmanager
    def hold(self, owner, timeout):
        self.calls.append(('exclusion', owner))
        yield

    def snapshot(self, environment):
        self.fault('snapshot_' + str(sum(call[0] == 'snapshot' for call in self.calls)))
        self.calls.append(('snapshot',))
        return deepcopy(self.database)

    def publish(self, plan, guard, prepared):
        self.calls.append(('publish',))
        self.fault('publish')

    def health(self, revision):
        self.fault('health')
        return {'status': 'ok', 'release': revision}

    def foreign(self):
        self.fault('foreign_' + str(sum(call[0] == 'foreign' for call in self.calls)))
        self.calls.append(('foreign',))
        return dict(self.services)

    def drain(self, host):
        for unit in op.OWNED_UNITS:
            host.service('stop', unit)
        return {'all_units_inactive': True}

    def engine(self):
        prior = SimpleNamespace(
            ROOT=self.root, APP=self.app, UNITS=op.OWNED_UNITS, sha=op.sha, write_new=engine_module.prior.write_new,
            static_delta=None, managed_helper=object(),
            backup_restore=SimpleNamespace(read_private=lambda path, limit: Path(path).read_bytes(),
                                           key_at=lambda key: FakeCipher()),
            source_guard=lambda: SimpleNamespace(),
            source_plan=lambda plan, guard: {'before': {}, 'after': {}},
            publish_source=self.publish,
            command=lambda argv, **options: self.calls.append(('citation',)) or b'',
            activation_exclusion=SimpleNamespace(bind_runtime=lambda path: None, hold=self.hold),
            legacy=SimpleNamespace(Host=self.host, operation_locks=self.locks, KEY=Path('/nonexistent'),
                                   static_primitives=lambda: SimpleNamespace(static_inventory=lambda root: {'.': {'kind': 'directory'}})),
            private_storage=SimpleNamespace(inventory=lambda root: {'a.pdf': {'sha256': 'b' * 64}}),
            foreign_services=self.foreign, await_health=self.health)
        return SimpleNamespace(
            prior=prior, snapshot=self.snapshot, unchanged=engine_module.unchanged,
            render_environment=lambda original, revision, environment: original.replace(BASE.encode(),
                                                                                        revision.encode()),
            stop_failed_resume=self.drain,
            failure_diagnostics=lambda error: {'failure_type': type(error).__name__,
                                               'reason': 'protected_operational_failure'},
            verify_original_before_resume=lambda original, guard, prepared: self.calls.append(('verified_original',)),
            verify_static_rollback=None)

    def plan(self):
        return {'format': op.FORMAT, 'base': BASE, 'candidate': CANDIDATE, 'source_sha256': {},
                'source_worktree': str(op.SOURCE), 'evidence_directory': str(self.root / 'evidence'),
                'environment': {}, 'static': [], 'manifest_sha256': 'a' * 64, 'code_manifest_sha256': 'b' * 64,
                'declaration': {'commit': 'c' * 40, 'sha256': 'd' * 64}, 'backup': {},
                'venv_footprint_sha256': self.venv['footprint_sha256'], 'foreign_venv_units': [self.UNIT],
                'plan_sha256': 'e' * 64}

    def context(self):
        return {'environment': {'original': self.env}, 'report': {'format': 'preflight'}, 'venv': self.venv,
                'services': dict(self.services)}


class ActTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.world = World(self.root)
        self.cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self.cwd)
        self.addCleanup(self.temporary.cleanup)

    def act(self):
        world = self.world
        with redirect_stderr(io.StringIO()):
            return op.act(world.engine(), world.plan(), world.context(), footprint=footprint,
                          idle=lambda units: world.idles.pop(0), snapshot_venv=lambda path: world.venvs.pop(0))

    def evidence(self, name):
        return json.loads((self.root / 'evidence' / name).read_text())

    def services(self):
        return [call for call in self.world.calls if call[0] in ('start', 'stop')]

    def test_success_runs_in_the_engine_order_and_changes_only_the_release_stamp(self):
        result, passed = self.act()
        self.assertTrue(passed and result['complete'] and result['all_postconditions_passed'])
        calls = self.world.calls
        self.assertLess(calls.index(('locks',)), calls.index(('stop', op.OWNED_UNITS[0])))
        self.assertLess(calls.index(('stop', op.OWNED_UNITS[2])), calls.index(('publish',)))
        self.assertLess(calls.index(('publish',)), calls.index(('start', op.OWNED_UNITS[2])))
        self.assertEqual(self.services(), [('stop', op.OWNED_UNITS[0]), ('stop', op.OWNED_UNITS[1]),
                                           ('stop', op.OWNED_UNITS[2]), ('start', op.OWNED_UNITS[2]),
                                           ('start', op.OWNED_UNITS[0]), ('start', op.OWNED_UNITS[1])])
        self.assertEqual((self.world.app / '.env').read_bytes(),
                         self.world.env.replace(BASE.encode(), CANDIDATE.encode()))
        self.assertEqual(result['dependency_installs'], 0)
        self.assertFalse((self.root / 'evidence/failure.json').exists())
        self.assertEqual(self.evidence('installation-complete.json')['installed_revision'], CANDIDATE)
        self.assertTrue(self.evidence('pre-resume-preservation.json')['venv_exact_before_publication'])

    def test_a_venv_change_before_publication_refuses_and_restores_the_original_release(self):
        self.world.venvs = [self.world.venv, self.world.changed_venv]
        with self.assertRaises(op.Refusal) as caught:
            self.act()
        self.assertEqual(str(caught.exception), 'installation_failed_inspect_retained_evidence')
        self.assertNotIn(('publish',), self.world.calls)
        self.assertIn(('verified_original',), self.world.calls)
        self.assertEqual(self.services()[3:], [('start', op.OWNED_UNITS[2]), ('start', op.OWNED_UNITS[0]),
                                               ('start', op.OWNED_UNITS[1])])
        failure = self.evidence('failure.json')
        self.assertEqual((failure['stage'], failure['label'], failure['publication_attempted']),
                         ('venv_after_stop', 'venv_unchanged_before_publication', False))
        self.assertEqual(self.evidence('original-release-resumed.json'), {'release': BASE})
        self.assertEqual((self.world.app / '.env').read_bytes(), self.world.env)

    def test_busy_venv_sharing_units_refuse_before_anything_stops(self):
        self.world.idles = [{'idle': False, 'units': {}}]
        with self.assertRaises(op.Refusal):
            self.act()
        self.assertEqual(self.services(), [])
        self.assertEqual(self.evidence('failure.json')['stage'], 'baseline_foreign_idle')

    def test_a_venv_differing_from_the_declaration_refuses_before_anything_stops(self):
        self.world.venvs = [self.world.changed_venv]
        with self.assertRaises(op.Refusal):
            self.act()
        self.assertEqual(self.services(), [])
        self.assertEqual(self.evidence('failure.json')['label'], 'venv_unchanged_since_preflight')

    def test_a_foreign_restart_before_publication_refuses_and_restores(self):
        self.world.faults['foreign_1'] = op.Refusal('foreign_services_preserved_before_publication')
        with self.assertRaises(op.Refusal):
            self.act()
        self.assertNotIn(('publish',), self.world.calls)
        self.assertTrue((self.root / 'evidence/original-release-resumed.json').exists())

    def test_a_failure_after_publication_leaves_the_units_drained_without_retry(self):
        self.world.faults['snapshot_2'] = op.Refusal('database_moved')
        with self.assertRaises(op.Refusal):
            self.act()
        self.assertIn(('publish',), self.world.calls)
        self.assertEqual([call[0] for call in self.services()], ['stop', 'stop', 'stop'])
        failure = self.evidence('failure.json')
        self.assertTrue(failure['publication_attempted'] and failure['stopped'] and not failure['resume_started'])
        self.assertFalse((self.root / 'evidence/original-release-resumed.json').exists())

    def test_a_failed_resume_is_drained_before_the_failure_is_retained(self):
        self.world.faults['health'] = op.Refusal('normal_https_readiness_deadline')
        with self.assertRaises(op.Refusal):
            self.act()
        self.assertEqual([call[0] for call in self.services()], ['stop'] * 3 + ['start'] * 3 + ['stop'] * 3)
        self.assertTrue(self.evidence('failed-resume-drain.json')['all_units_inactive'])
        self.assertEqual(self.evidence('failure.json')['stage'], 'normal_https_health')

    def test_post_conditions_after_resume_are_reported_for_judgement_not_drained(self):
        self.world.venvs = [self.world.venv, self.world.venv, self.world.changed_venv]
        self.world.idles = [{'idle': True, 'units': {}}, {'idle': False, 'units': {}}]
        result, passed = self.act()
        self.assertFalse(passed)
        self.assertEqual(result['postconditions'], {'venv_sharing_units_idle_after_resume': False,
                                                    'venv_exact_after_resume': False})
        self.assertEqual(result['venv_change']['difference']['added'], ['lib/stray.pyc'])
        self.assertEqual(self.services()[-3:], [('start', op.OWNED_UNITS[2]), ('start', op.OWNED_UNITS[0]),
                                                ('start', op.OWNED_UNITS[1])])
        self.assertFalse((self.root / 'evidence/failure.json').exists())

    def test_an_environment_changed_since_the_preflight_refuses_before_any_evidence(self):
        (self.world.app / '.env').write_bytes(self.world.env + b'EXTRA=1\n')
        with self.assertRaises(op.Refusal):
            self.act()
        self.assertFalse((self.root / 'evidence').exists())
        self.assertEqual(self.world.calls, [])

    def test_the_act_refuses_outside_the_permanent_tree(self):
        os.chdir(self.cwd)
        with self.assertRaises(op.Refusal):
            self.act()


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.root.chmod(0o700)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        self.addCleanup(self.temporary.cleanup)
        self.declaration = op.SOURCE / 'docs/foundation/mutations/20261031-rebuild-release.md'
        # main() sets the private operator umask 077; restore the suite's own afterwards.
        umask = os.umask(0o022)
        os.umask(umask)
        self.addCleanup(os.umask, umask)

    def argv(self, *extra):
        return ['--base', BASE, '--candidate', CANDIDATE, '--declaration', str(self.declaration),
                '--backup-report', str(self.root / 'backup.json'), '--result', str(self.root / 'result.json'), *extra]

    def test_argument_shapes(self):
        op.arguments(self.argv())
        execute = self.argv('--execute', '--evidence-directory', str(self.root / 'evidence'),
                            '--manifest-sha256', 'a' * 64)
        self.assertTrue(op.arguments(execute).execute)
        bad = [['--base', 'abc'] + self.argv()[2:], self.argv()[:2] + ['--candidate', BASE] + self.argv()[4:],
               self.argv('--execute'), self.argv('--execute', '--manifest-sha256', 'a' * 64),
               self.argv('--evidence-directory', str(self.root / 'e')), self.argv('--manifest-sha256', 'xyz'),
               self.argv()[:5] + ['relative.md'] + self.argv()[6:],
               self.argv()[:9] + [str(self.root / '../x.json')]]
        for argv in bad:
            with self.subTest(argv=argv), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                op.arguments(argv)

    def passing(self, passed=True, contract=False):
        report = {'format': op.PREFLIGHT_FORMAT, 'base': BASE, 'candidate': CANDIDATE, 'declaration': 'x',
                  'checked_at': 'now', 'passed': passed, 'checks': [], 'measured': {}}
        if contract:
            report['contract_block'] = op.CONTRACT_MARKER + '\n```json\n{}\n```\n'
        manifest = {'format': op.MANIFEST_FORMAT, 'base': BASE, 'paths': {'rebuild/core/a.py': {'sha256': 'f' * 64}}}
        contract_value = {'static': [], 'code_manifest_sha256': 'b' * 64, 'venv': {'footprint_sha256': 'c' * 64},
                          'foreign_venv_units': []}
        context = {'engine': SimpleNamespace(BASE=None, SOURCE=None, STATIC=None,
                                             prior=SimpleNamespace(BASE=None, SOURCE=None, STATIC=None)),
                   'measured': {'manifest': manifest, 'manifest_sha256': 'a' * 64, 'backup': {}},
                   'declaration': {'contract': contract_value, 'provenance': {'commit': 'd' * 40}}}
        return report, context

    def test_the_preflight_writes_its_result_and_exits_on_its_verdict(self):
        for passed, code in ((True, 0), (False, 1)):
            result = self.root / 'result.json'
            if result.exists():
                result.unlink()
            with self.subTest(passed=passed), patch.object(op, 'preflight', return_value=self.passing(passed, True)), \
                    patch.object(op, 'act') as act, redirect_stdout(io.StringIO()) as output:
                self.assertEqual(op.main(self.argv()), code)
            act.assert_not_called()
            self.assertEqual(json.loads(result.read_text())['passed'], passed)
            self.assertIn(op.CONTRACT_MARKER, output.getvalue())

    def test_execute_refuses_outside_the_runner_before_any_preflight(self):
        execute = self.argv('--execute', '--evidence-directory', str(self.root / 'evidence'),
                            '--manifest-sha256', 'a' * 64)
        with patch.object(op, 'preflight') as preflight:
            with self.assertRaises(op.Refusal):
                op.main(execute)
            os.chdir(op.SOURCE)
            with patch.dict(os.environ, {'RULED_MUTATION_DECLARATION': '', 'RULED_MUTATION_DECL_COMMIT': ''}), \
                    self.assertRaises(op.Refusal):
                op.main(execute)
            with patch.dict(os.environ, {'RULED_MUTATION_DECLARATION': str(self.declaration) + '.other',
                                         'RULED_MUTATION_DECL_COMMIT': 'd' * 40}), self.assertRaises(op.Refusal):
                op.main(execute)
        preflight.assert_not_called()

    def run_execute(self, preflight_value, act_value=None, act_error=None):
        execute = self.argv('--execute', '--evidence-directory', str(self.root / 'evidence'),
                            '--manifest-sha256', 'a' * 64)
        os.chdir(op.SOURCE)
        runner = {'RULED_MUTATION_DECLARATION': str(self.declaration), 'RULED_MUTATION_DECL_COMMIT': 'd' * 40}

        def act(engine, plan, context, footprint):
            if act_error:
                raise act_error
            (Path(plan['evidence_directory'])).mkdir(mode=0o700)
            (Path(plan['evidence_directory']) / 'installation-complete.json').write_text('{}')
            return act_value
        with patch.dict(os.environ, runner), patch.object(op, 'preflight', return_value=preflight_value), \
                patch.object(op, 'act', side_effect=act) as called, patch.object(op, 'ROOT', self.root), \
                redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return op.main(execute), called

    def test_execute_acts_only_after_a_passing_preflight_and_reports_post_conditions(self):
        code, act = self.run_execute(self.passing(False))
        self.assertEqual(code, 1)
        act.assert_not_called()
        (self.root / 'result.json').unlink()
        code, act = self.run_execute(self.passing(True), ({'complete': True}, True))
        self.assertEqual(code, 0)
        plan = act.call_args.args[1]
        self.assertEqual((plan['base'], plan['candidate'], plan['static']), (BASE, CANDIDATE, []))
        self.assertEqual(plan['plan_sha256'], op.sha(op.canonical({k: v for k, v in plan.items()
                                                                    if k != 'plan_sha256'})))
        self.assertTrue(json.loads((self.root / 'result.json').read_text())['all_postconditions_passed'])
        for name in ('result.json',):
            (self.root / name).unlink()
        shutil.rmtree(self.root / 'evidence')
        code, _ = self.run_execute(self.passing(True), ({'complete': True}, False))
        self.assertEqual(code, 2)

    def test_execute_failure_is_recorded_with_a_fixed_label(self):
        with self.assertRaises(op.Refusal):
            self.run_execute(self.passing(True), act_error=op.Refusal('installation_failed_inspect_retained_evidence'))
        self.assertEqual(json.loads((self.root / 'result.json').read_text())['label'],
                         'installation_failed_inspect_retained_evidence')

    def test_a_manifest_that_moved_since_the_preflight_refuses(self):
        report, context = self.passing(True)
        context['measured']['manifest_sha256'] = 'b' * 64
        with self.assertRaises(op.Refusal):
            self.run_execute((report, context), ({'complete': True}, True))


if __name__ == '__main__':
    unittest.main()
