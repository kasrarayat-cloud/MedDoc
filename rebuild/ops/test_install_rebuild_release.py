"""Offline controls for the code-only rebuild release installer (interpretation 67, D1-D4).

Nothing here reaches the live host: git runs in temporary repositories, and the act runs against fakes of the
engine's primitives. The real engine module is imported only for its pure helpers and its own source text.
Tests named after a finding (GI-*, PT-*, AS-*) pin the repair of that finding from the 2026-11-01 refutation.
"""
import ast
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from copy import deepcopy
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

from ops import activate_core_workflow_repair as engine_module
from ops import install_rebuild_release as op
from ops import managed_helper
from ops import venv_footprint as footprint

BASE = '1' * 40
CANDIDATE = '2' * 40
#: Literal, never op.SIGNALS: a test that iterates the module's own list passes vacuously when the list is emptied.
ROUTED_SIGNALS = ('SIGTERM', 'SIGINT', 'SIGHUP')
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


def new_repo(root, name='repo'):
    repo = root / name
    repo.mkdir()
    git(repo, 'init', '-q', '-b', 'main')
    return repo


def wait_for_signal():
    for _ in range(200):
        time.sleep(0.005)


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
        self.assertEqual(op.classify('scripts/ci/verify-cpt-studio.sh', 'A'), 'passenger')
        refused = [('rebuild/core/x.py', 'D'), ('rebuild/core/x.py', 'T'), ('rebuild/core/migrations/0040_x.py', 'A'),
                   ('rebuild/deploy/quillmd-fresh-worker.service', 'M'), ('rebuild/staticfiles/app.js', 'A'),
                   ('rebuild/static/fonts/x.ttf', 'A'), ('apps/x/node_modules/y.js', 'A'), ('rebuild/.venv/x', 'A'),
                   ('docs/backups/x.md', 'A'), ('/abs.py', 'A'), ('a//b.py', 'A'), ('./a.py', 'A'), ('../a.py', 'A'),
                   ('a\\b.py', 'A'), ('a\nb.py', 'A'), ('scripts/hooks/post-merge', 'A'),
                   ('scripts/hooks/pre-auto-gc', 'A'), ('.gitattributes', 'A'), ('rebuild/.gitattributes', 'M'),
                   *[(name, 'M') for name in op.GATE_INSTRUMENTS]]
        for name, status in refused:
            with self.subTest(name=name, status=status), self.assertRaises(op.Refusal):
                op.classify(name, status, hooks=frozenset({'scripts/hooks/post-merge', 'scripts/hooks/pre-auto-gc'}))

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

    def test_as1_a_dot_named_component_only_where_the_base_tracks_it(self):
        """AS-1: rebuild/.env/<x> and .env/<x> refuse; a new file under a tracked .github/ is admitted."""
        blobs = {'a' * 40: b'new', 'b' * 40: b'old'}
        tracked = frozenset({'.github', '.github/workflows', '.github/workflows/test.yml', 'rebuild',
                             'rebuild/.gitignore', '.env.example'})

        def build(name, status='A'):
            old = ('100644', 'b' * 40) if status == 'M' else ('000000', '0' * 40)
            return op.build_manifest(BASE, [(status, old[0], '100644', old[1], 'a' * 40, name)], blobs.__getitem__,
                                     base_paths=tracked)
        for name in ('.github/workflows/new.yml', 'rebuild/core/a.py'):
            build(name)
        for name in ('.github/workflows/test.yml', 'rebuild/.gitignore'):
            build(name, 'M')
        for name in ('rebuild/.env/notes.md', '.env/README.md', '.worktrees/x/rebuild/core/a.py',
                     'cpt-studio/.gitignore', 'rebuild/.runtime-copy/x.py', '.env.local'):
            with self.subTest(name=name), self.assertRaises(op.Refusal) as caught:
                build(name)
            self.assertEqual(str(caught.exception), 'untracked_dot_path')
        with self.assertRaises(op.Refusal):     # without the base listing every dot path refuses
            op.build_manifest(BASE, [('M', '100644', '100644', 'b' * 40, 'a' * 40, '.github/workflows/test.yml')],
                              blobs.__getitem__)

    def test_manifest_from_a_real_repository_and_its_refusals(self):
        repo = new_repo(self.root)
        base = commit(repo, {'rebuild/core/a.py': 'one\n', 'rebuild/requirements.txt': 'pypdf==6.21.1\n',
                             'docs/old.md': 'old\n', 'rebuild/.gitignore': '*.log\n',
                             '.github/workflows/test.yml': 'x: 1\n'})
        candidate = commit(repo, {'rebuild/core/a.py': 'two\n', 'rebuild/requirements.txt': 'pypdf==6.21.4\n',
                                  'rebuild/.gitignore': '*.log\n*.pyc\n', '.github/workflows/new.yml': 'y: 1\n'})
        manifest = op.compute_manifest(repo, base, candidate, frozenset())
        self.assertEqual({n: r['status'] for n, r in manifest['paths'].items()},
                         {'.github/workflows/new.yml': 'A', 'rebuild/.gitignore': 'M', 'rebuild/core/a.py': 'M',
                          'rebuild/requirements.txt': 'M'})
        self.assertEqual(manifest['paths']['rebuild/core/a.py']['sha256'], op.sha(b'two\n'))
        for files, remove in (({}, ('docs/old.md',)), ({'link': ('symlink', 'docs/old.md')}, ()),
                              ({'rebuild/core/migrations/0040_x.py': 'x\n'}, ()),
                              ({'rebuild/.env/notes.md': 'x\n'}, ()), ({'cpt-studio/.gitignore': '*.pyc\n'}, ()),
                              ({'scripts/check-citation.sh': 'exit 0\n'}, ())):
            with self.subTest(files=files, remove=remove):
                git(repo, 'reset', '-q', '--hard', candidate)
                refused = commit(repo, files, remove=remove)
                with self.assertRaises(op.Refusal):
                    op.compute_manifest(repo, base, refused, frozenset())

    def test_facts_name_runtime_dot_and_static_paths(self):
        rows = {'rebuild/core/a.py': 'runtime', 'rebuild/requirements.txt': 'requirements',
                'rebuild/static/app.js': 'static', 'cpt-studio/.gitignore': 'passenger', 'docs/x.md': 'passenger'}
        manifest = {'format': op.MANIFEST_FORMAT, 'base': BASE,
                    'paths': {n: {'status': 'M', 'class': c} for n, c in rows.items()},
                    'new_dot_paths': ['cpt-studio/.gitignore']}
        facts = op.manifest_facts(manifest)
        self.assertEqual(facts['runtime_paths'], ['rebuild/core/a.py', 'rebuild/requirements.txt'])
        self.assertEqual(facts['dot_paths'], ['cpt-studio/.gitignore'])
        self.assertEqual(facts['new_dot_paths'], ['cpt-studio/.gitignore'])
        self.assertEqual(facts['static'], ['app.js'])
        self.assertEqual(facts['paths']['classes'], {'passenger': 2, 'requirements': 1, 'runtime': 1, 'static': 1})

    def test_requirements_change_is_admitted_only_with_the_venv_footprint_check(self):
        manifest = {'paths': {'rebuild/requirements.txt': {}}}
        self.assertTrue(op.admit_requirements(manifest, True))
        for check in (False, None, 'yes'):
            with self.subTest(check=check), self.assertRaises(op.Refusal):
                op.admit_requirements(manifest, check)
        self.assertTrue(op.admit_requirements({'paths': {'rebuild/core/a.py': {}}}, False))


class ManifestPathsOnDiskTests(unittest.TestCase):
    """AS-1 and PT-2: every manifest path's place in the shared tree, with lstat, before anything stops."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        (self.root / 'rebuild/core').mkdir(parents=True)
        (self.root / 'rebuild/core/a.py').write_text('one\n')
        (self.root / 'rebuild/core/a.py').chmod(0o644)

    def manifest(self, rows):
        return {'paths': {name: ({'status': 'M', 'base_mode': mode} if status == 'M' else {'status': 'A'})
                          for name, (status, mode) in rows.items()}}

    def test_a_clean_tree_passes(self):
        detail = op.manifest_paths_on_disk(self.manifest({'rebuild/core/a.py': ('M', '100644'),
                                                          'rebuild/core/new.py': ('A', None),
                                                          'cpt-studio/app/new.py': ('A', None)}), root=self.root)
        self.assertEqual(detail, {'paths': 3, 'added_absent': 2, 'modified_regular': 1})

    def test_every_obstruction_refuses(self):
        def ignored_env_file(root):
            (root / 'rebuild/.env').write_text('SECRET=only-copy\n')

        def dangling_link(root):
            (root / 'cpt-studio/app').mkdir(parents=True)
            (root / 'cpt-studio/app/new.py').symlink_to('/nonexistent-target')

        def file_where_a_directory_goes(root):
            (root / 'cpt-studio').write_text('stray\n')

        def linked_directory(root):
            (root / 'elsewhere').mkdir()
            (root / 'cpt-studio').symlink_to(root / 'elsewhere')

        def modified_mode(root):
            (root / 'rebuild/core/a.py').chmod(0o755)

        def modified_link(root):
            (root / 'rebuild/core/a.py').unlink()
            (root / 'rebuild/core/a.py').symlink_to(root / 'rebuild/core/other.py')
        cases = {'ignored_env_file': (ignored_env_file, {'rebuild/.env/notes.md': ('A', None)},
                                      'manifest_path_prefix_not_a_directory'),
                 'dangling_link_at_added_path': (dangling_link, {'cpt-studio/app/new.py': ('A', None)},
                                                 'added_path_obstructed'),
                 'file_where_a_directory_goes': (file_where_a_directory_goes, {'cpt-studio/app/new.py': ('A', None)},
                                                 'manifest_path_prefix_not_a_directory'),
                 'linked_directory': (linked_directory, {'cpt-studio/app/new.py': ('A', None)},
                                      'manifest_path_prefix_not_a_directory'),
                 'added_path_exists': (lambda root: None, {'rebuild/core/a.py': ('A', None)}, 'added_path_obstructed'),
                 'modified_mode_not_declared': (modified_mode, {'rebuild/core/a.py': ('M', '100644')},
                                                'modified_path_regular_at_base_mode'),
                 'modified_path_is_a_link': (modified_link, {'rebuild/core/a.py': ('M', '100644')},
                                             'modified_path_regular_at_base_mode'),
                 'modified_path_missing': (lambda root: None, {'rebuild/core/gone.py': ('M', '100644')},
                                           'modified_path_missing')}
        for name, (setup, rows, label) in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as other:
                root = Path(other).resolve()
                (root / 'rebuild/core').mkdir(parents=True)
                (root / 'rebuild/core/a.py').write_text('one\n')
                (root / 'rebuild/core/a.py').chmod(0o644)
                setup(root)
                with self.assertRaises(op.Refusal) as caught:
                    op.manifest_paths_on_disk(self.manifest(rows), root=root)
                self.assertEqual(str(caught.exception), label)


class DeclaredDotPathTests(GitIsolation):
    """AS-1 with a declaration: the contract's new_dot_paths admits exactly the new dot-named files it names.

    The planned delta (67acb2628..origin/main) adds cpt-studio/.gitignore and cpt-studio/deploy/.dockerignore, which
    the base does not track. Every other path guard still applies to a declared path.
    """

    TRACKED = frozenset({'.github', '.github/workflows', '.github/workflows/test.yml', 'rebuild', 'rebuild/.gitignore',
                         'rebuild/.env.example'})
    PLANNED = ['cpt-studio/.gitignore', 'cpt-studio/deploy/.dockerignore']
    BLOBS = {'a' * 40: b'new', 'b' * 40: b'old'}

    def build(self, rows, declared):
        """rows: names (added, 100644) or (name, status[, mode]) tuples."""
        entries = []
        for row in rows:
            name, status, mode = (row, 'A', '100644') if isinstance(row, str) else (row + ('100644',))[:3]
            old = ('100644', 'b' * 40) if status == 'M' else ('000000', '0' * 40)
            entries.append((status, old[0], mode, old[1], 'a' * 40, name))
        return op.build_manifest(BASE, entries, self.BLOBS.__getitem__, base_paths=self.TRACKED,
                                 new_dot_paths=declared)

    def refusal(self, function, *args, **kwargs):
        with self.assertRaises(op.Refusal) as caught:
            function(*args, **kwargs)
        return str(caught.exception)

    def test_as1_declared_new_dot_files_are_admitted_and_bound_by_the_manifest(self):
        manifest = self.build(self.PLANNED + ['cpt-studio/app.py', '.github/workflows/new.yml',
                                              ('rebuild/.gitignore', 'M'), ('rebuild/.env.example', 'M')], self.PLANNED)
        self.assertEqual(manifest['new_dot_paths'], self.PLANNED)
        facts = op.manifest_facts(manifest)
        self.assertEqual(facts['new_dot_paths'], self.PLANNED)
        self.assertEqual(facts['dot_paths'], ['.github/workflows/new.yml', 'cpt-studio/.gitignore',
                                              'cpt-studio/deploy/.dockerignore', 'rebuild/.env.example',
                                              'rebuild/.gitignore'])
        self.assertNotEqual(op.manifest_digest(manifest), op.manifest_digest(dict(manifest, new_dot_paths=[])))
        self.assertEqual(self.build(['cpt-studio/app.py'], [])['new_dot_paths'], [])
        # The same on a real repository shaped like the planned delta: the base does not track cpt-studio at all.
        repo = new_repo(self.root)
        base = commit(repo, {'rebuild/core/a.py': 'one\n', '.github/workflows/test.yml': 'x: 1\n'})
        candidate = commit(repo, {'cpt-studio/.gitignore': '*.pyc\n', 'cpt-studio/deploy/.dockerignore': '.venv\n',
                                  'cpt-studio/app.py': 'app\n', '.github/workflows/cpt-studio.yml': 'y: 1\n'})
        manifest = op.compute_manifest(repo, base, candidate, frozenset(), self.PLANNED)
        self.assertEqual(manifest['new_dot_paths'], self.PLANNED)
        self.assertEqual(manifest['paths']['cpt-studio/.gitignore']['sha256'], op.sha(b'*.pyc\n'))
        self.assertEqual(self.refusal(op.compute_manifest, repo, base, candidate, frozenset()), 'untracked_dot_path')

    def test_as1_an_undeclared_new_dot_path_still_refuses(self):
        for declared in ([], ['cpt-studio/.gitignore'], ['cpt-studio/deploy/.gitignore']):
            with self.subTest(declared=declared):
                self.assertEqual(self.refusal(self.build, self.PLANNED, declared), 'untracked_dot_path')
        # A declaration admits a dot-named FILE only. A dot-named directory the base does not track still refuses,
        # declared or not, so no declared path can write into an existing ignored directory.
        for declared in (['x/.cache/y.txt'], ['x/.cache', 'x/.cache/y.txt']):
            with self.subTest(declared=declared):
                self.assertEqual(self.refusal(self.build, ['x/.cache/y.txt'], declared), 'untracked_dot_path')
        self.assertEqual(self.refusal(op.tracked_dot_components, 'rebuild/.runtime/x.json', self.TRACKED,
                                      frozenset({'rebuild/.runtime/x.json', 'rebuild/.runtime'})), 'untracked_dot_path')

    def test_as1_a_declared_dot_path_keeps_every_other_guard(self):
        manifest = self.build(self.PLANNED, self.PLANNED)
        clean = self.root / 'shared'
        (clean / 'cpt-studio/deploy').mkdir(parents=True)
        self.assertEqual(op.manifest_paths_on_disk(manifest, root=clean),
                         {'paths': 2, 'added_absent': 2, 'modified_regular': 0})

        def ignored_file_at_the_path(shared):
            (shared / 'cpt-studio').mkdir()
            (shared / 'cpt-studio/.gitignore').write_text('a local, ignored copy\n')

        def dangling_link_at_the_path(shared):
            (shared / 'cpt-studio/deploy').mkdir(parents=True)
            (shared / 'cpt-studio/deploy/.dockerignore').symlink_to('/nonexistent-target')

        def file_where_a_directory_goes(shared):
            (shared / 'cpt-studio').write_text('stray\n')

        def linked_directory(shared):
            (shared / 'elsewhere').mkdir()
            (shared / 'cpt-studio').mkdir()
            (shared / 'cpt-studio/deploy').symlink_to(shared / 'elsewhere')
        cases = ((ignored_file_at_the_path, 'added_path_obstructed'),
                 (dangling_link_at_the_path, 'added_path_obstructed'),
                 (file_where_a_directory_goes, 'manifest_path_prefix_not_a_directory'),
                 (linked_directory, 'manifest_path_prefix_not_a_directory'))
        for setup, label in cases:
            with self.subTest(case=setup.__name__), tempfile.TemporaryDirectory() as other:
                shared = Path(other).resolve()
                setup(shared)
                self.assertEqual(self.refusal(op.manifest_paths_on_disk, manifest, root=shared), label)
        # No symbolic link and no mode but the regular blob modes, declared or not.
        for mode in ('120000', '160000'):
            with self.subTest(mode=mode):
                self.assertEqual(self.refusal(self.build, [('cpt-studio/.gitignore', 'A', mode)],
                                              ['cpt-studio/.gitignore']), 'regular_blob_modes_only')

    def test_as1_git_and_env_names_refuse_even_when_declared(self):
        names = ('.env', '.env.local', 'rebuild/.env', 'cpt-studio/.env.production', 'cpt-studio/.ENV',
                 'cpt-studio/.git', 'cpt-studio/.Git')
        contract = op.build_contract(
            base=BASE, code_candidate=CANDIDATE, code_manifest=self.build(self.PLANNED, self.PLANNED),
            venv_summary={'footprint_sha256': 'f' * 64, 'distributions': 64, 'unrecorded_bytecode': 63}, mismatch={},
            foreign_units=[], backup={'report_sha256': 'e' * 64, 'run_id': 'r', 'restore_run_id': 's'},
            operator={name: 'd' * 64 for name in op.OPERATOR_FILES})
        self.assertEqual(contract['new_dot_paths'], self.PLANNED)
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(self.refusal(self.build, [name], [name]), 'declared_dot_path_git_or_env')
                self.assertEqual(self.refusal(op.new_dot_path_list, [name]), 'declared_dot_path_git_or_env')
                # The rule itself refuses them too, whatever set it is handed.
                self.assertEqual(self.refusal(op.tracked_dot_components, name, self.TRACKED, frozenset({name})),
                                 'declared_dot_path_git_or_env')
                declared = dict(contract, dot_paths=sorted(contract['dot_paths'] + [name]),
                                new_dot_paths=sorted(self.PLANNED + [name]))
                text = op.CONTRACT_MARKER + '\n```json\n' + json.dumps(declared) + '\n```\n'
                self.assertEqual(self.refusal(op.contract_from, text), 'declared_dot_path_git_or_env')
        # A base-tracked .env* template is not a declaration and stays admitted as before.
        self.assertFalse(op.tracked_dot_components('rebuild/.env.example', self.TRACKED))
        # Exact paths only: no glob, nothing absolute, a dot-named component, and a sorted list of unique names.
        shapes = ((['cpt-studio/.*'], 'declared_dot_path_exact'), (['cpt-studio/.git*'], 'declared_dot_path_exact'),
                  (['cpt-studio/.{a,b}'], 'declared_dot_path_exact'), (['/cpt-studio/.x'], 'declared_dot_path_exact'),
                  (['cpt-studio/app.py'], 'declared_dot_path_without_dot_component'),
                  (list(reversed(self.PLANNED)), 'declared_dot_path_list'),
                  ('cpt-studio/.gitignore', 'declared_dot_path_list'))
        for value, label in shapes:
            with self.subTest(value=value):
                self.assertEqual(self.refusal(op.new_dot_path_list, value), label)

    def test_as1_a_declared_path_the_delta_does_not_add_is_a_stale_declaration(self):
        self.assertEqual(self.refusal(self.build, self.PLANNED, sorted(self.PLANNED + ['cpt-studio/.npmrc'])),
                         'declared_dot_path_not_in_delta')
        # The release dropped both files after the declaration named them.
        self.assertEqual(self.refusal(self.build, ['cpt-studio/app.py'], self.PLANNED),
                         'declared_dot_path_not_in_delta')
        # A path the base already covers needs no declaration; naming it is stale too.
        for row in (('.github/workflows/new.yml', 'A'), ('rebuild/.gitignore', 'M')):
            with self.subTest(row=row):
                self.assertEqual(self.refusal(self.build, [row], [row[0]]), 'declared_dot_path_not_new')


class DeclarationTests(GitIsolation):
    """D4: the declaration lives in the candidate and is tracked, unmodified and committed there."""

    RELATIVE = 'docs/foundation/mutations/20261031-test-install.md'

    def repository(self):
        repo = new_repo(self.root)
        gates = {name: (op.SOURCE / name).read_bytes() for name in op.TRUSTED_GATE_SCRIPTS}
        base = commit(repo, {'rebuild/core/a.py': 'one\n', 'rebuild/requirements.txt': 'pypdf==6.21.1\n', **gates},
                      'base')
        code = commit(repo, {'rebuild/core/a.py': 'two\n', 'rebuild/requirements.txt': 'pypdf==6.21.4\n',
                             'docs/notes.md': 'notes\n'}, 'code')
        return repo, base, code

    def measured(self, repo, base, code, new_dot_paths=()):
        manifest = op.compute_manifest(repo, base, code, frozenset(), new_dot_paths)
        return {'manifest': manifest,
                'venv': {'footprint_sha256': 'f' * 64, 'distributions': 64, 'unrecorded_bytecode': 63},
                'requirements_mismatch': {'pypdf': {'required': '6.21.4', 'installed': '6.21.1'}},
                'foreign_venv_units': ['quillmd-corti-candidate.service'],
                'backup': {'report_sha256': 'e' * 64, 'run_id': '20261031T200000Z-0a1b2c3d',
                           'restore_run_id': 'a' * 16},
                'operator': {name: 'd' * 64 for name in op.OPERATOR_FILES},
                'gate_scripts': op.trusted_gate_scripts(base, root=repo)}

    def declare(self, repo, contract, extra=None):
        text = '# Install\n\nThe delta and its baseline.\n\n' + op.contract_block(contract) + '\nStop conditions.\n'
        return commit(repo, {self.RELATIVE: text, **(extra or {})}, 'declaration')

    def checks(self, repo, measured, base, candidate):
        args = SimpleNamespace(base=base, candidate=candidate, declaration=repo / self.RELATIVE)
        checks = op.Checks()
        with patch.object(op, 'SOURCE', repo), patch.object(op, 'ROOT', repo):
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

    def test_as1_once_committed_the_declaration_is_the_only_source_of_new_dot_paths(self):
        repo, base, _ = self.repository()
        code = commit(repo, {'cpt-studio/.gitignore': '*.pyc\n', 'cpt-studio/deploy/.dockerignore': '.venv\n'},
                      'code with two new dot files')
        planned = ['cpt-studio/.gitignore', 'cpt-studio/deploy/.dockerignore']

        def source(candidate, given):
            args = SimpleNamespace(base=base, candidate=candidate, declaration=repo / self.RELATIVE,
                                   new_dot_path=given)
            with patch.object(op, 'SOURCE', repo):
                return op.declared_new_dot_paths(args)
        # The preflight of record: nothing is declared yet, so --new-dot-path supplies the contract to embed.
        self.assertEqual(source(code, list(reversed(planned))), {'source': 'command_line', 'new_dot_paths': planned})
        measured = self.measured(repo, base, code, planned)
        contract = op.build_contract(code_candidate=code, code_manifest=measured['manifest'], base=base,
                                     venv_summary=measured['venv'], mismatch=measured['requirements_mismatch'],
                                     foreign_units=measured['foreign_venv_units'], backup=measured['backup'],
                                     operator=measured['operator'])
        self.assertEqual(contract['new_dot_paths'], planned)
        candidate = self.declare(repo, contract)
        # Merged: the declaration is read from the candidate's blob, and a different --new-dot-path refuses.
        for given in ([], planned):
            self.assertEqual(source(candidate, given), {'source': 'declaration', 'new_dot_paths': planned})
        with self.assertRaises(op.Refusal) as caught:
            source(candidate, ['cpt-studio/.gitignore'])
        self.assertEqual(str(caught.exception), 'new_dot_paths_differ_from_the_declaration')
        measured['manifest'] = op.compute_manifest(repo, base, candidate, frozenset(), planned)
        result, checks = self.checks(repo, measured, base, candidate)
        self.assertTrue(checks.passed, checks.rows)
        self.assertEqual(result['contract']['new_dot_paths'], planned)
        # A stale declaration names a dot path the release does not add: the manifest built from it refuses.
        git(repo, 'reset', '-q', '--hard', code)
        stale = dict(contract, dot_paths=sorted(contract['dot_paths'] + ['cpt-studio/.npmrc']),
                     new_dot_paths=sorted(planned + ['cpt-studio/.npmrc']))
        candidate = self.declare(repo, stale)
        declared = source(candidate, [])
        self.assertEqual(declared['source'], 'declaration')
        with self.assertRaises(op.Refusal) as caught:
            op.compute_manifest(repo, base, candidate, frozenset(), declared['new_dot_paths'])
        self.assertEqual(str(caught.exception), 'declared_dot_path_not_in_delta')

    def test_uncommitted_modified_or_misplaced_declarations_refuse(self):
        repo, base, code = self.repository()
        pins = op.trusted_gate_scripts(base, root=repo)
        path = repo / self.RELATIVE
        path.parent.mkdir(parents=True)
        path.write_text('draft\n')
        with self.assertRaises(op.Refusal):
            op.declaration_provenance(path, code, source=repo)
        with self.assertRaises(op.Refusal):
            op.strict_gate(path, repo, gate_scripts=pins, root=repo)
        candidate = commit(repo, {}, 'declaration')
        op.declaration_provenance(path, candidate, source=repo)
        op.strict_gate(path, repo, gate_scripts=pins, root=repo)
        path.write_text('edited after the commit\n')
        with self.assertRaises(op.Refusal):
            op.declaration_provenance(path, candidate, source=repo)
        with self.assertRaises(op.Refusal):
            op.strict_gate(path, repo, gate_scripts=pins, root=repo)
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


class GateInstrumentTests(GitIsolation):
    """GI-1: the citation and the strict gate are judged by the base's pinned copies, never by the candidate's."""

    def setUp(self):
        super().setUp()
        self.shared = new_repo(self.root, 'shared')
        self.declaration_lib = (op.SOURCE / 'scripts/lib/declaration.sh').read_bytes()
        self.base = commit(self.shared, {
            'scripts/check-citation.sh': '#!/usr/bin/env bash\necho "base checker: no runs for $1"\nexit 1\n',
            'scripts/lib/runs-api.sh': '# runs api\n', 'scripts/lib/declaration.sh': self.declaration_lib,
            'rebuild/core/a.py': 'one\n'}, 'base')
        # The candidate worktree carries a "simplified" checker and a gate that passes everything.
        self.candidate = self.root / 'candidate'
        (self.candidate / 'scripts/lib').mkdir(parents=True)
        (self.candidate / 'scripts/check-citation.sh').write_text(
            '#!/usr/bin/env bash\necho "**Citation \\u2014 2 of 2 on \\`$1\\`:**"\nexit 0\n')
        (self.candidate / 'scripts/lib/declaration.sh').write_text('declaration_gate() { return 0; }\n')
        self.prior = SimpleNamespace(command=engine_module.prior.command)

    def test_gi1_the_citation_runs_the_base_copy_and_refuses_a_commit_without_runs(self):
        pins = op.trusted_gate_scripts(self.base, root=self.shared)
        self.assertEqual(set(pins), {'scripts/check-citation.sh', 'scripts/lib/runs-api.sh',
                                     'scripts/lib/declaration.sh'})
        with patch.object(op, 'SOURCE', self.candidate), patch.object(op, 'ROOT', self.shared):
            with self.assertRaises(engine_module.Refusal) as caught:
                op.citation(self.prior, '3' * 40, pins)
        self.assertEqual(str(caught.exception), 'bounded_command_failed')

    def test_gi1_the_strict_gate_runs_the_base_copy(self):
        pins = op.trusted_gate_scripts(self.base, root=self.shared)
        draft = self.candidate / 'docs/foundation/mutations/20261101-x.md'
        draft.parent.mkdir(parents=True)
        draft.write_text('an uncommitted declaration\n')
        git(self.candidate.parent, 'init', '-q', '-b', 'main', str(self.candidate))
        with self.assertRaises(op.Refusal) as caught:
            op.strict_gate(draft, self.candidate, gate_scripts=pins, root=self.shared)
        self.assertEqual(str(caught.exception), 'strict_declaration_gate')

    def test_gi1_the_shared_tree_copy_must_be_the_base_blob_and_stay_pinned(self):
        pins = op.trusted_gate_scripts(self.base, root=self.shared)
        script = self.shared / 'scripts/check-citation.sh'
        script.write_text(script.read_text() + '# edited in the shared tree\n')
        with self.assertRaises(op.Refusal) as caught:
            op.trusted_gate_scripts(self.base, root=self.shared)
        self.assertEqual(str(caught.exception), 'trusted_gate_script_is_the_base_blob')
        with self.assertRaises(op.Refusal) as caught:
            op.verify_gate_scripts(self.shared, pins)
        self.assertEqual(str(caught.exception), 'gate_script_unchanged')
        with self.assertRaises(op.Refusal):
            op.verify_gate_scripts(self.shared, {name: pins[name] for name in list(pins)[:2]})


class SharedRepositoryTests(GitIsolation):
    """GI-2, GI-3/PT-5, PT-2, PT-3: git's own state, merge-time hooks and origin/main, on scratch repositories."""

    def shared(self, name='shared'):
        repo = new_repo(self.root, name)
        base = commit(repo, {'rebuild/core/a.py': 'one\n', 'rebuild/core/b.py': 'two\n'}, 'base')
        return repo, base

    def test_pt2_pt3_git_s_own_state_refuses_in_the_shared_tree(self):
        repo, base = self.shared()
        detail = op.shared_tree_at_base(base, root=repo)
        self.assertEqual(detail['git_state']['index_entries'], 2)

        def assume_unchanged(repo):
            git(repo, 'update-index', '--assume-unchanged', 'rebuild/core/b.py')
            (repo / 'rebuild/core/b.py').write_text('edited in the shared tree, hidden from status\n')

        def skip_worktree(repo):
            git(repo, 'update-index', '--skip-worktree', 'rebuild/core/b.py')
        cases = {name: (lambda repo, name=name: (repo / '.git' / name).write_bytes(b''), 'git_lock_file_present')
                 for name in ('index.lock', 'HEAD.lock', 'ORIG_HEAD.lock', 'packed-refs.lock', 'config.lock')}
        cases.update({
            'refs/heads/main.lock': (lambda repo: (repo / '.git/refs/heads/main.lock').write_bytes(b''),
                                     'git_ref_lock_present'),
            'MERGE_HEAD': (lambda repo: (repo / '.git/MERGE_HEAD').write_text(base + '\n'), 'unfinished_git_operation'),
            'CHERRY_PICK_HEAD': (lambda repo: (repo / '.git/CHERRY_PICK_HEAD').write_text(base + '\n'),
                                 'unfinished_git_operation'),
            'REVERT_HEAD': (lambda repo: (repo / '.git/REVERT_HEAD').write_text(base + '\n'),
                            'unfinished_git_operation'),
            'rebase-merge': (lambda repo: (repo / '.git/rebase-merge').mkdir(), 'unfinished_git_operation'),
            'BISECT_LOG': (lambda repo: (repo / '.git/BISECT_LOG').write_text('x\n'), 'unfinished_git_operation'),
            'assume-unchanged': (assume_unchanged, 'assume_unchanged_or_skip_worktree_entries'),
            'skip-worktree': (skip_worktree, 'assume_unchanged_or_skip_worktree_entries')})
        for name, (setup, label) in cases.items():
            with self.subTest(state=name):
                repo, base = self.shared('shared-' + name.replace('/', '-'))
                setup(repo)
                with self.assertRaises(op.Refusal) as caught:
                    op.shared_tree_at_base(base, root=repo)
                self.assertEqual(str(caught.exception), label)

    def test_gi3_pt5_pre_auto_gc_is_a_merge_time_hook_and_the_act_s_git_runs_no_hook_and_no_gc(self):
        repo = new_repo(self.root)
        git(repo, 'config', 'core.hooksPath', 'scripts/hooks')
        marker = self.root / 'hook-ran'
        hook = '#!/bin/sh\necho "$0" >> ' + str(marker) + '\nexit 0\n'
        base = commit(repo, {'rebuild/core/a.py': 'one\n', 'scripts/hooks/pre-commit': '#!/bin/sh\nexit 0\n'})
        hooks = op.merge_hooks(repo)
        self.assertIn('scripts/hooks/pre-auto-gc', hooks)
        with self.assertRaises(op.Refusal):
            op.classify('scripts/hooks/pre-auto-gc', 'A', hooks=hooks)
        # A candidate that carries the hook anyway (classify bypassed), and an object store that needs gc.
        git(repo, 'checkout', '-q', '-b', 'release')
        (repo / 'scripts/hooks/pre-auto-gc').write_text(hook)
        (repo / 'scripts/hooks/pre-auto-gc').chmod(0o755)
        (repo / 'scripts/hooks/post-merge').write_text(hook)
        (repo / 'scripts/hooks/post-merge').chmod(0o755)
        candidate = commit(repo, {'rebuild/core/a.py': 'two\n'}, 'candidate')
        git(repo, 'checkout', '-q', 'main')
        git(repo, 'config', 'gc.auto', '1')
        git(repo, 'config', 'gc.autoDetach', 'false')
        # gc --auto samples objects/17: with gc.auto=1 it is due once that bucket holds more than one loose object.
        index, bucket = 0, repo / '.git/objects/17'
        while not bucket.is_dir() or len(list(bucket.iterdir())) < 3:
            body = b'loose %d\n' % index
            raw = b'blob %d\0' % len(body) + body
            digest = hashlib.sha1(raw).hexdigest()
            if digest.startswith('17'):
                bucket.mkdir(exist_ok=True)
                (bucket / digest[2:]).write_bytes(zlib.compress(raw))
            index += 1
        with op.act_git_environment():
            subprocess.run(['git', '-C', str(repo), 'merge', '--ff-only', candidate], capture_output=True,
                           check=True, env={**os.environ, **GIT_ENV})
        self.assertEqual(git(repo, 'rev-parse', 'HEAD'), candidate)
        self.assertFalse(marker.exists())
        self.assertNotIn('GIT_CONFIG_COUNT', os.environ)    # restored
        # Control: the same merge without the act's git environment runs both hooks.
        git(repo, 'reset', '-q', '--hard', base)
        subprocess.run(['git', '-C', str(repo), 'merge', '--ff-only', candidate], capture_output=True, check=True,
                       env={**os.environ, **GIT_ENV})
        self.assertEqual({Path(line).name for line in marker.read_text().split()}, {'post-merge', 'pre-auto-gc'})
        with patch.dict(os.environ, {'GIT_DIR': str(repo / '.git')}), self.assertRaises(op.Refusal):
            with op.act_git_environment():
                pass

    def test_gi2_origin_main_is_read_exactly_on_both_sides(self):
        origin = self.root / 'origin.git'
        git(self.root, 'init', '-q', '--bare', '-b', 'main', str(origin))
        work, other = self.root / 'work', self.root / 'other'
        git(self.root, 'clone', '-q', str(origin), str(work))
        commit(work, {'a.txt': 'one\n'}, 'base')
        git(work, 'push', '-q', 'origin', 'HEAD:refs/heads/main')
        candidate = commit(work, {'a.txt': 'two\n'}, 'candidate')
        git(work, 'push', '-q', 'origin', 'HEAD:refs/heads/main')
        git(work, 'fetch', '-q', 'origin')
        with patch.object(op, 'ROOT', work), patch.object(op, 'SOURCE', work):
            self.assertEqual(op.origin_main_is(candidate), {'origin_main': candidate})
            # main moves on the remote; a branch whose name ends in /refs/heads/main still names the candidate
            git(self.root, 'clone', '-q', str(origin), str(other))
            moved = commit(other, {'a.txt': 'three\n'}, 'moved')
            git(other, 'push', '-q', 'origin', 'HEAD:refs/heads/main')
            git(work, 'push', '-q', 'origin', candidate + ':refs/heads/decl/refs/heads/main')
            with self.assertRaises(op.Refusal) as caught:
                op.origin_main_is(candidate)
            self.assertEqual(str(caught.exception), 'remote_main_is_candidate')
            # the tracking ref catches up: now a local branch named origin/main shadows it for `rev-parse origin/main`
            git(work, 'fetch', '-q', 'origin')
            self.assertEqual(op.origin_main_is(moved), {'origin_main': moved})
            git(work, 'branch', 'origin/main', candidate)
            with self.assertRaises(op.Refusal) as caught:
                op.origin_main_is(moved)
            self.assertEqual(str(caught.exception), 'origin_main_unambiguous')


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

    def test_pt1_live_venv_users_read_the_executable_and_the_process_s_own_path(self):
        uid = os.getuid()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            interpreter = root / 'interp'
            interpreter.write_bytes(b'#!/bin/sh\n')
            interpreter.chmod(0o755)
            venv = root / 'venv'
            (venv / 'bin').mkdir(parents=True)
            (venv / 'bin/python3').symlink_to(interpreter)
            (venv / 'bin/python').symlink_to('python3')
            sysbin = root / 'sysbin'
            sysbin.mkdir()
            (sysbin / 'python3').symlink_to(interpreter)
            link = root / 'worktree-venv'
            link.symlink_to(venv)
            os.symlink('venv', root / '.venv')
            proc = root / 'proc'
            corti, worker = 'quillmd-corti-candidate.service', 'quillmd-fresh-worker.service'
            processes = {   # argv, unit, uid, exe target, environ PATH, cwd
                '10': ([str(venv / 'bin/python'), '-m', 'gunicorn'], corti, 999, None, None, None),
                '11': ([str(link / 'bin/python'), '-m', 'pytest'], None, uid, None, None, None),
                '12': (['/usr/bin/python3', 'other.py'], 'other.service', 999, None, None, None),
                '13': (['.venv/bin/python', 'manage.py'], worker, 999, None, None, root),
                '14': (['python', '-m', 'pip'], 'x.service', uid, interpreter, '%s/bin:%s' % (venv, sysbin), None),
                '15': (['python3', '-c', 'pass'], None, uid, interpreter, '%s:%s/bin' % (sysbin, venv), None),
                '16': (['python', 'y.py'], None, uid, None, None, None),
                '17': (['python', 'z.py'], None, 999, None, None, None),
                '18': ([str(venv / 'bin/python'), 'w'], None, uid, root / 'other-binary', None, None),
                '19': (['gunicorn: worker [app]'], None, uid, interpreter, '/usr/bin', None),
                '20': (['nginx: worker process'], 'nginx.service', 999, None, None, None)}
            for pid, (argv, unit, owner, exe, path, cwd) in processes.items():
                entry = proc / pid
                entry.mkdir(parents=True)
                (entry / 'cmdline').write_bytes(b'\0'.join(a.encode() for a in argv) + b'\0')
                (entry / 'cgroup').write_text('0::/system.slice/%s\n' % unit if unit else
                                              '0::/user.slice/user-1000.slice/session-3.scope\n')
                (entry / 'status').write_text('Name:\tx\nUid:\t%d\t%d\t%d\t%d\n' % ((owner,) * 4))
                if exe is not None:
                    (entry / 'exe').symlink_to(exe)
                if path is not None:
                    (entry / 'environ').write_bytes(b'HOME=/x\0PATH=' + path.encode() + b'\0')
                if cwd is not None:
                    (entry / 'cwd').symlink_to(cwd)
            (proc / 'self').mkdir()
            users = op.live_venv_users(proc, venv, uid=uid)
            self.assertEqual(users, [{'pid': 10, 'unit': corti}, {'pid': 11, 'unit': None},
                                     {'pid': 13, 'unit': worker}, {'pid': 14, 'unit': 'x.service'},
                                     {'pid': 16, 'unit': None, 'undetermined': True},
                                     {'pid': 17, 'unit': None, 'uninspectable': True},
                                     {'pid': 19, 'unit': None, 'undetermined': True}])
            with self.assertRaises(op.Refusal) as caught:
                op.no_undeclared_venv_users([corti], users)
            self.assertEqual(str(caught.exception), 'undeterminable_operator_interpreter_process')
            determined = [row for row in users if not row.get('undetermined')]
            with self.assertRaises(op.Refusal) as caught:
                op.no_undeclared_venv_users([corti], determined)
            self.assertEqual(str(caught.exception), 'undeclared_process_on_the_live_venv')
            allowed = [row for row in determined if row['pid'] not in (11, 14)]
            self.assertEqual(op.no_undeclared_venv_users([corti], allowed),
                             {'processes': 2, 'units': [corti, worker], 'uninspectable_other_users': 1})
            self.assertEqual(op.live_venv_users(proc, venv, exclude={10, 11, 13, 14, 16, 17, 19}, uid=uid), [])

    def test_pt1_a_real_bare_interpreter_on_the_venv_s_path_is_found(self):
        """PT-1 with real processes: `source .venv/bin/activate && python3 ...` shows only "python3" in argv."""
        with tempfile.TemporaryDirectory() as temporary:
            venv = Path(temporary).resolve() / 'venv'
            (venv / 'bin').mkdir(parents=True)
            (venv / 'pyvenv.cfg').write_text('home = %s\n' % Path(os.path.realpath(sys.executable)).parent)
            (venv / 'bin/python3').symlink_to(os.path.realpath(sys.executable))
            (venv / 'bin/python').symlink_to('python3')
            code = 'import sys,time; print(sys.prefix, flush=True); time.sleep(30)'
            started = [subprocess.Popen(['bash', '-c', 'PATH=%s:/usr/bin:/bin exec python3 -B -c "%s"' % (bin_, code)],
                                        stdout=subprocess.PIPE) for bin_ in (venv / 'bin', '/usr/local/nothing')]
            try:
                prefixes = [process.stdout.readline().decode().strip() for process in started]
                self.assertEqual(prefixes[0], str(venv))     # it IS a process of that venv
                self.assertNotEqual(prefixes[1], str(venv))
                found = {row['pid'] for row in op.live_venv_users(venv=venv)}
                self.assertIn(started[0].pid, found)
                self.assertNotIn(started[1].pid, found)
            finally:
                for process in started:
                    process.kill()
                    process.wait()
                    process.stdout.close()


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
        self.assertEqual(op.reason(op.Interrupted('SIGTERM')), 'interrupted_by_SIGTERM')
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

    def test_as6_signals_raise_interrupted_in_the_main_thread_and_the_handlers_come_back(self):
        self.assertEqual(set(op.SIGNALS), set(ROUTED_SIGNALS))
        before = {name: signal.getsignal(getattr(signal, name)) for name in ROUTED_SIGNALS}
        for name in ROUTED_SIGNALS:
            with self.subTest(signal=name):
                with self.assertRaises(op.Interrupted) as caught:
                    with op.signal_routing():
                        os.kill(os.getpid(), getattr(signal, name))
                        wait_for_signal()
                self.assertEqual(caught.exception.signal_name, name)
        with op.signal_routing() as state:
            state['raising'] = False
            os.kill(os.getpid(), signal.SIGTERM)
            wait_for_signal()
            self.assertEqual(state['received'], ['SIGTERM'])
        self.assertEqual({name: signal.getsignal(getattr(signal, name)) for name in ROUTED_SIGNALS}, before)


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
                    'configuration_after_stop', 'clinical_files_after_stop', 'git_state_after_stop',
                    'foreign_idle_after_resume', 'venv_after_resume'}
        ours = stages(op.__file__, 'act')
        engine = stages(engine_module.__file__, 'execute')
        self.assertTrue(inserted <= set(ours))
        self.assertEqual([stage for stage in ours if stage not in inserted], engine)
        # Every re-comparison before publication sits after the stop and before the merge.
        for stage in ('venv_after_stop', 'foreign_services_after_stop', 'configuration_after_stop',
                      'clinical_files_after_stop', 'git_state_after_stop'):
            self.assertLess(ours.index('stop_owned_services'), ours.index(stage))
            self.assertLess(ours.index(stage), ours.index('source_publication'))


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
        self.configurations = []        # values for successive configuration reads (else a fixed one)
        self.inventories = []           # values for successive clinical-file inventories (else a fixed one)
        self.start_failures = set()     # units whose start helper fails
        self.start_inert = set()        # units whose `systemctl start` returns but never become active
        self.gate = {}
        for relative in op.TRUSTED_GATE_SCRIPTS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'# the base copy of ' + relative.encode() + b'\n')
            self.gate[relative] = op.sha(path.read_bytes())
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
                if action == 'start' and unit in world.start_failures:
                    raise managed_helper.HelperFailure('deadline')
                if action == 'start' and unit in world.start_inert:
                    return
                world.running[unit] = action == 'start'

            def configuration(self):
                world.fault('configuration')
                world.calls.append(('configuration',))
                if world.configurations:
                    return world.configurations.pop(0)
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

    def inventory(self, root):
        self.calls.append(('inventory',))
        if self.inventories:
            return self.inventories.pop(0)
        return {'a.pdf': {'sha256': 'b' * 64}}

    def publish(self, plan, guard, prepared):
        self.calls.append(('publish',))
        self.fault('publish')

    def health(self, revision):
        self.fault('health')
        self.fault('health_' + ('base' if revision == BASE else 'candidate'))
        self.calls.append(('health', revision))
        return {'status': 'ok', 'release': revision}

    def foreign(self):
        self.fault('foreign_' + str(sum(call[0] == 'foreign' for call in self.calls)))
        self.calls.append(('foreign',))
        return dict(self.services)

    def drain(self, host):
        for unit in op.OWNED_UNITS:
            host.service('stop', unit)
        return {'all_units_inactive': True}

    def command(self, argv, **options):
        self.calls.append(('citation', argv[1], options.get('cwd')))
        return '**Citation \u2014 2 of 2 on `{}`:**\n'.format(argv[2]).encode()

    def verify_original(self, original, guard, prepared):
        self.fault('verify_original')
        self.calls.append(('verified_original',))

    def source_state(self):
        self.fault('source_state')
        self.calls.append(('source_state',))
        return {'head': BASE}

    def engine(self):
        prior = SimpleNamespace(
            ROOT=self.root, APP=self.app, UNITS=op.OWNED_UNITS, sha=op.sha, write_new=engine_module.prior.write_new,
            static_delta=None, managed_helper=object(),
            backup_restore=SimpleNamespace(read_private=lambda path, limit: Path(path).read_bytes(),
                                           key_at=lambda key: FakeCipher()),
            source_guard=lambda: SimpleNamespace(),
            source_plan=lambda plan, guard: {'before': {}, 'after': {}},
            publish_source=self.publish, command=self.command,
            activation_exclusion=SimpleNamespace(bind_runtime=lambda path: None, hold=self.hold),
            legacy=SimpleNamespace(Host=self.host, operation_locks=self.locks, KEY=Path('/nonexistent'),
                                   static_primitives=lambda: SimpleNamespace(static_inventory=lambda root: {'.': {'kind': 'directory'}})),
            private_storage=SimpleNamespace(inventory=self.inventory),
            foreign_services=self.foreign, await_health=self.health)
        return SimpleNamespace(
            prior=prior, snapshot=self.snapshot, unchanged=engine_module.unchanged,
            render_environment=lambda original, revision, environment: original.replace(BASE.encode(),
                                                                                        revision.encode()),
            stop_failed_resume=self.drain,
            failure_diagnostics=lambda error: {'failure_type': type(error).__name__,
                                               'reason': 'protected_operational_failure'},
            verify_original_before_resume=self.verify_original, verify_static_rollback=None)

    def plan(self):
        return {'format': op.FORMAT, 'base': BASE, 'candidate': CANDIDATE, 'source_sha256': {},
                'source_worktree': str(op.SOURCE), 'evidence_directory': str(self.root / 'evidence'),
                'environment': {}, 'static': [], 'manifest_sha256': 'a' * 64, 'code_manifest_sha256': 'b' * 64,
                'declaration': {'commit': 'c' * 40, 'sha256': 'd' * 64}, 'backup': {},
                'venv_footprint_sha256': self.venv['footprint_sha256'], 'foreign_venv_units': [self.UNIT],
                'gate_scripts': dict(self.gate), 'plan_sha256': 'e' * 64}

    def context(self):
        return {'environment': {'original': self.env}, 'report': {'format': 'preflight'}, 'venv': self.venv,
                'services': dict(self.services),
                'measured': {'manifest': {'format': op.MANIFEST_FORMAT, 'base': BASE, 'paths': {}}}}


class ActTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.world = World(self.root)
        self.cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, self.cwd)
        self.addCleanup(self.temporary.cleanup)
        self.stderr = None

    def act(self, world=None, engine=None):
        world = world or self.world
        os.chdir(world.root)
        self.stderr = io.StringIO()
        with redirect_stderr(self.stderr):
            return op.act(engine or world.engine(), world.plan(), world.context(), footprint=footprint,
                          idle=lambda units: world.idles.pop(0), snapshot_venv=lambda path: world.venvs.pop(0),
                          source_state=world.source_state)

    def fresh(self, name):
        root = self.root / name
        root.mkdir()
        return World(root)

    def evidence(self, name, world=None):
        return json.loads(((world or self.world).root / 'evidence' / name).read_text())

    def exists(self, name, world=None):
        return ((world or self.world).root / 'evidence' / name).exists()

    def services(self, world=None):
        return [call for call in (world or self.world).calls if call[0] in ('start', 'stop')]

    def assert_restored(self, world=None, stage=None):
        world = world or self.world
        self.assertEqual(self.services(world)[-3:], [('start', op.OWNED_UNITS[2]), ('start', op.OWNED_UNITS[0]),
                                                     ('start', op.OWNED_UNITS[1])])
        resumed = self.evidence('original-release-resumed.json', world)
        self.assertEqual((resumed['release'], resumed['original_release_serving'], resumed['health']['release']),
                         (BASE, True, BASE))
        self.assertTrue(all(resumed['units_active'].values()))
        self.assertIn(('health', BASE), world.calls)
        failure = self.evidence('failure.json', world)
        self.assertEqual((failure['recovery'], failure['publication_attempted']), ('restore', False))
        if stage:
            self.assertEqual(failure['stage'], stage)
        return failure

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
        self.assertFalse(self.exists('failure.json'))
        self.assertEqual(self.evidence('installation-complete.json')['installed_revision'], CANDIDATE)
        self.assertTrue(self.evidence('pre-resume-preservation.json')['venv_exact_before_publication'])
        self.assertEqual(set(result['postconditions']), set(op.POSTCONDITIONS))
        # GI-1: the citation ran the base's pinned copy in the shared tree, with the shared tree as cwd.
        self.assertIn(('citation', str(self.root / 'scripts/check-citation.sh'), self.root), calls)
        # AS-3/PT-2: configuration, clinical files and git's state measured again after the stop, before the merge.
        stop, publish = calls.index(('stop', op.OWNED_UNITS[2])), calls.index(('publish',))
        between = calls[stop:publish]
        for call in (('configuration',), ('inventory',), ('source_state',)):
            self.assertIn(call, between)
        self.assertNotIn('GIT_CONFIG_COUNT', os.environ)

    def test_a_venv_change_before_publication_refuses_and_restores_the_original_release(self):
        self.world.venvs = [self.world.venv, self.world.changed_venv]
        with self.assertRaises(op.Refusal) as caught:
            self.act()
        self.assertEqual(str(caught.exception), 'installation_failed_inspect_retained_evidence')
        self.assertNotIn(('publish',), self.world.calls)
        self.assertIn(('verified_original',), self.world.calls)
        failure = self.assert_restored(stage='venv_after_stop')
        self.assertEqual(failure['label'], 'venv_unchanged_before_publication')
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
        self.assert_restored(stage='foreign_services_after_stop')

    def test_as3_configuration_files_or_git_state_changed_while_serving_refuse_before_publication_and_restore(self):
        """AS-3 (and PT-2 after the stop): a change between the baseline and the stop restores, never drains."""
        cases = {
            'configuration': (lambda w: w.configurations.extend([{'/etc/nginx/x': 'a'}, {'/etc/nginx/x': 'b'}]),
                              'configuration_after_stop', 'configuration_preserved_before_publication'),
            'clinical_files': (lambda w: w.inventories.extend([{'a.pdf': 1}, {'a.pdf': 1, 'b.pdf': 2}]),
                               'clinical_files_after_stop', 'clinical_files_preserved_before_publication'),
            'git_state': (lambda w: w.faults.__setitem__('source_state', op.Refusal('git_lock_file_present')),
                          'git_state_after_stop', 'git_lock_file_present')}
        for name, (setup, stage, label) in cases.items():
            with self.subTest(change=name):
                world = self.fresh(name)
                setup(world)
                with self.assertRaises(op.Refusal) as caught:
                    self.act(world)
                self.assertEqual(str(caught.exception), 'installation_failed_inspect_retained_evidence')
                self.assertNotIn(('publish',), world.calls)
                failure = self.assert_restored(world, stage=stage)
                self.assertEqual(failure['label'], label)

    def test_as2_a_publication_git_refused_before_any_change_restores_the_original_release(self):
        """AS-2/PT-2: a merge git refused (another process's index.lock) or a refusal inside publish_source before
        the merge leaves HEAD at BASE; verify_original_before_resume measures that and the original is restored."""
        self.world.faults['publish'] = engine_module.Refusal('bounded_command_failed')
        with self.assertRaises(op.Refusal) as caught:
            self.act()
        self.assertEqual(caught.exception.outcome['recovery'], 'restore')
        self.assertTrue(caught.exception.outcome['original_release_serving'])
        failure = self.assert_restored(stage='source_publication')
        self.assertTrue(failure['merge_invoked'])
        self.assertEqual(failure['original_verification'], {'original_intact': True})

    def test_as2_a_merge_that_moved_the_tree_is_publication_and_leaves_the_units_drained(self):
        """HEAD.lock: git updated the index and the working tree, then refused the ref: publication began."""
        self.world.faults['publish'] = engine_module.Refusal('bounded_command_failed')
        self.world.faults['verify_original'] = engine_module.Refusal('clean_original_checkout_before_recovery')
        with self.assertRaises(op.Refusal) as caught:
            self.act()
        self.assertEqual(str(caught.exception), 'installation_failed_inspect_retained_evidence')
        self.assertEqual([call[0] for call in self.services()], ['stop', 'stop', 'stop'])
        failure = self.evidence('failure.json')
        self.assertEqual((failure['publication_attempted'], failure['recovery'], failure['merge_invoked']),
                         (True, 'none', True))
        self.assertEqual(failure['original_verification']['label'], 'clean_original_checkout_before_recovery')
        self.assertFalse(self.exists('original-release-resumed.json'))
        self.assertFalse(self.exists('original-recovery-refused.json'))

    def test_a_failure_after_publication_leaves_the_units_drained_without_retry(self):
        self.world.faults['snapshot_2'] = op.Refusal('database_moved')
        with self.assertRaises(op.Refusal):
            self.act()
        self.assertIn(('publish',), self.world.calls)
        self.assertEqual([call[0] for call in self.services()], ['stop', 'stop', 'stop'])
        failure = self.evidence('failure.json')
        self.assertTrue(failure['publication_attempted'] and failure['stopped'] and not failure['resume_started'])
        self.assertFalse(self.exists('original-release-resumed.json'))

    def test_an_unverifiable_original_is_not_restarted(self):
        self.world.venvs = [self.world.venv, self.world.changed_venv]
        self.world.faults['verify_original'] = engine_module.Refusal('new_source_absent_before_recovery')
        with self.assertRaises(op.Refusal) as caught:
            self.act()
        self.assertEqual(str(caught.exception), 'original_recovery_refused_inspect_retained_evidence')
        self.assertEqual([call[0] for call in self.services()], ['stop', 'stop', 'stop'])
        self.assertEqual(self.evidence('original-recovery-refused.json')['label'], 'new_source_absent_before_recovery')

    def test_a_failed_resume_is_drained_before_the_failure_is_retained(self):
        self.world.faults['health'] = op.Refusal('normal_https_readiness_deadline')
        with self.assertRaises(op.Refusal):
            self.act()
        self.assertEqual([call[0] for call in self.services()], ['stop'] * 3 + ['start'] * 3 + ['stop'] * 3)
        self.assertTrue(self.evidence('failed-resume-drain.json')['all_units_inactive'])
        self.assertEqual(self.evidence('failure.json')['stage'], 'normal_https_health')

    def test_as4_a_disk_that_fills_after_the_stop_still_restores_every_unit_and_says_so(self):
        """AS-4(a): ENOSPC on database-after-stop.json, failure.json and the outcome file."""
        engine = self.world.engine()
        real = engine.prior.write_new

        def write_new(path, value):
            if Path(path).name in ('database-after-stop.json', 'failure.json', 'original-release-resumed.json'):
                raise OSError(errno.ENOSPC, 'No space left on device')
            return real(path, value)
        engine.prior.write_new = write_new
        with self.assertRaises(op.Refusal) as caught:
            self.act(engine=engine)
        outcome = caught.exception.outcome
        self.assertEqual((outcome['recovery'], outcome['original_release_serving'], outcome['failure_json'],
                          outcome['outcome_file']), ('restore', True, False, False))
        self.assertEqual(self.services()[3:], [('start', op.OWNED_UNITS[2]), ('start', op.OWNED_UNITS[0]),
                                               ('start', op.OWNED_UNITS[1])])
        lines = [json.loads(line.split(op.STAGE_LOG, 1)[1]) for line in self.stderr.getvalue().splitlines()
                 if line.startswith(op.STAGE_LOG + ' {')]
        self.assertIn('rebuild_release_outcome', lines[-1])
        self.assertEqual(lines[-1]['rebuild_release_outcome']['stage'], 'retain_database_after_stop')
        self.assertTrue(any(line.get('evidence_write_failed') == 'failure.json' for line in lines))

    def test_as4_as5_every_unit_is_started_and_a_restore_counts_only_when_measured(self):
        """AS-4(b): a failing start never skips the others. AS-5: `start` returning proves nothing by itself."""
        cases = {'worker_start_fails': lambda w: w.start_failures.add(op.OWNED_UNITS[2]),
                 'units_never_become_active': lambda w: w.start_inert.update(op.OWNED_UNITS),
                 'health_does_not_report_base': lambda w: w.faults.__setitem__(
                     'health_base', engine_module.Refusal('normal_https_readiness_deadline'))}
        for name, setup in cases.items():
            with self.subTest(case=name):
                world = self.fresh(name)
                world.venvs = [world.venv, world.changed_venv]
                setup(world)
                with self.assertRaises(op.Refusal) as caught:
                    self.act(world)
                self.assertEqual(str(caught.exception), 'original_restore_unverified_inspect_retained_evidence')
                self.assertEqual(self.services(world)[3:], [('start', op.OWNED_UNITS[2]),
                                                            ('start', op.OWNED_UNITS[0]),
                                                            ('start', op.OWNED_UNITS[1])])
                self.assertFalse(self.exists('original-release-resumed.json', world))
                unverified = self.evidence('original-release-restore-unverified.json', world)
                self.assertFalse(unverified['original_release_serving'])
                self.assertEqual(self.evidence('failure.json', world)['recovery'], 'restore')

    def test_as6_a_termination_signal_while_the_units_are_stopped_takes_the_failure_path(self):
        """AS-6: SIGTERM, SIGINT or SIGHUP outside any helper call restores (here: the database read after the
        stop), and a second signal during the restore is recorded without cutting it short."""
        before = {name: signal.getsignal(getattr(signal, name)) for name in ROUTED_SIGNALS}
        for name in ROUTED_SIGNALS:
            with self.subTest(signal=name):
                world = self.fresh(name)
                engine = world.engine()
                real_snapshot, real_host = engine.snapshot, engine.prior.legacy.Host

                def snapshot(environment, world=world, real_snapshot=real_snapshot, name=name):
                    if sum(call[0] == 'snapshot' for call in world.calls) == 1:
                        os.kill(os.getpid(), getattr(signal, name))
                        wait_for_signal()
                    return real_snapshot(environment)

                def host(helper, real_host=real_host, world=world):
                    instance = real_host(helper)
                    service = instance.service

                    def signalled(action, unit):
                        if action == 'start' and not any(call[0] == 'start' for call in world.calls):
                            os.kill(os.getpid(), signal.SIGTERM)
                            wait_for_signal()
                        return service(action, unit)
                    instance.service = signalled
                    return instance
                engine.snapshot, engine.prior.legacy.Host = snapshot, host
                with self.assertRaises(op.Refusal) as caught:
                    self.act(world, engine)
                failure = self.assert_restored(world, stage='database_after_stop')
                self.assertEqual((failure['label'], failure['signals_received']), ('interrupted_by_' + name, [name]))
                self.assertEqual(caught.exception.outcome['signals_received'], [name, 'SIGTERM'])
        self.assertEqual({name: signal.getsignal(getattr(signal, name)) for name in ROUTED_SIGNALS}, before)

    def test_post_conditions_after_resume_are_reported_for_judgement_not_drained(self):
        self.world.venvs = [self.world.venv, self.world.venv, self.world.changed_venv]
        self.world.idles = [{'idle': True, 'units': {}}, {'idle': False, 'units': {}}]
        result, passed = self.act()
        self.assertFalse(passed)
        self.assertEqual(result['postconditions'], {'configuration_preserved_after_resume': True,
                                                    'foreign_services_preserved_after_resume': True,
                                                    'venv_sharing_units_idle_after_resume': False,
                                                    'venv_exact_after_resume': False})
        self.assertEqual(result['venv_change']['difference']['added'], ['lib/stray.pyc'])
        self.assertEqual(self.services()[-3:], [('start', op.OWNED_UNITS[2]), ('start', op.OWNED_UNITS[0]),
                                                ('start', op.OWNED_UNITS[1])])
        self.assertFalse(self.exists('failure.json'))

    def test_as7_after_a_healthy_resume_nothing_drains_the_release(self):
        """AS-7: a foreign restart, a configuration read that fails, or an interrupt after health passed is
        reported in installation-complete.json and the act returns for judgement (exit 2)."""
        def foreign_restart(world, engine):
            real = engine.prior.foreign_services
            count = {'n': 0}

            def foreign():
                count['n'] += 1
                services = real()
                if count['n'] >= 4:     # baseline, after the stop, before the resume; then after the resume
                    services[World.UNIT] = 'MainPID=8\nInvocationID=def\n'
                return services
            engine.prior.foreign_services = foreign

        def configuration_timeout(world, engine):
            real_host = engine.prior.legacy.Host

            def host(helper):
                instance = real_host(helper)
                read = instance.configuration
                count = {'n': 0}

                def configuration():
                    count['n'] += 1
                    if count['n'] == 4:
                        raise managed_helper.HelperFailure('deadline')
                    return read()
                instance.configuration = configuration
                return instance
            engine.prior.legacy.Host = host

        def interrupt_in_idle(world, engine):
            answers = iter([{'idle': True, 'units': {}}])

            def idle(units):
                value = next(answers, None)
                if value is None:
                    os.kill(os.getpid(), signal.SIGTERM)
                    wait_for_signal()
                return value
            world.idle_function = idle
        cases = {'foreign_restart': (foreign_restart, 'foreign_services_preserved_after_resume', None),
                 'configuration_read_times_out': (configuration_timeout, 'configuration_preserved_after_resume', None),
                 'interrupt_in_the_idle_window': (interrupt_in_idle, 'venv_sharing_units_idle_after_resume',
                                                  'SIGTERM')}
        for name, (setup, failed, interrupted) in cases.items():
            with self.subTest(case=name):
                world = self.fresh(name)
                engine = world.engine()
                setup(world, engine)
                idle = getattr(world, 'idle_function', None)
                os.chdir(world.root)
                with redirect_stderr(io.StringIO()):
                    result, passed = op.act(engine, world.plan(), world.context(), footprint=footprint,
                                            idle=idle or (lambda units: world.idles.pop(0)),
                                            snapshot_venv=lambda path: world.venvs.pop(0),
                                            source_state=world.source_state)
                self.assertFalse(passed)
                self.assertFalse(result['postconditions'][failed])
                self.assertEqual(result['interrupted'], interrupted)
                self.assertEqual([call[0] for call in self.services(world)], ['stop'] * 3 + ['start'] * 3)
                self.assertFalse(self.exists('failure.json', world))
                receipt = self.evidence('installation-complete.json', world)
                self.assertEqual((receipt['installed_revision'], receipt['all_postconditions_passed']),
                                 (CANDIDATE, False))

    def test_gi1_a_gate_script_changed_after_the_preflight_refuses_before_anything(self):
        (self.root / 'scripts/check-citation.sh').write_text('#!/usr/bin/env bash\nexit 0\n')
        with self.assertRaises(op.Refusal) as caught:
            self.act()
        self.assertEqual(str(caught.exception), 'gate_script_unchanged')
        self.assertFalse((self.root / 'evidence').exists())
        self.assertEqual(self.services(), [])

    def test_an_environment_changed_since_the_preflight_refuses_before_any_evidence(self):
        (self.world.app / '.env').write_bytes(self.world.env + b'EXTRA=1\n')
        with self.assertRaises(op.Refusal):
            self.act()
        self.assertFalse((self.root / 'evidence').exists())
        self.assertEqual(self.world.calls, [])

    def test_the_act_refuses_outside_the_permanent_tree(self):
        os.chdir(self.cwd)
        with self.assertRaises(op.Refusal):
            op.act(self.world.engine(), self.world.plan(), self.world.context(), footprint=footprint,
                   source_state=self.world.source_state)


class PreflightFlowTests(unittest.TestCase):
    """The whole preflight body with every host read faked: rows, held values, the contract to embed."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        venv = self.root / 'venv'
        (venv / footprint.SITE / 'pypdf-6.21.1.dist-info').mkdir(parents=True)
        (venv / footprint.SITE / 'pypdf-6.21.1.dist-info/METADATA').write_text(
            'Metadata-Version: 2.1\nName: pypdf\nVersion: 6.21.1\n')
        (venv / footprint.SITE / 'pypdf-6.21.1.dist-info/RECORD').write_text('pypdf-6.21.1.dist-info/RECORD,,\n')
        self.venv = footprint.snapshot(venv)
        self.manifest = op.build_manifest(BASE, [('M', '100644', '100644', 'a' * 40, 'b' * 40,
                                                  'rebuild/requirements.txt')], lambda blob: blob.encode())
        self.environment = ('QUILLMD_RELEASE_SHA="' + BASE + '"\n').encode()
        self.calls = []
        prior = SimpleNamespace(
            await_health=lambda revision: {'release': revision}, foreign_services=lambda: {'x.service': 'MainPID=1'},
            legacy=SimpleNamespace(Host=lambda helper: SimpleNamespace(state=lambda unit: {
                'ActiveState': 'active', 'MainPID': '9'})),
            managed_helper=object(), backup_restore=SimpleNamespace(read_private=lambda path, limit: self.environment),
            source_guard=lambda: SimpleNamespace(), source_plan=lambda plan, guard: {'before': {'a': 1}, 'after': {}},
            BASE=None, SOURCE=None, STATIC=None)
        self.engine = SimpleNamespace(prior=prior, BASE=None, SOURCE=None, STATIC=None,
                                      snapshot=lambda original: {'tables': {'core_encounter': [5, 'x']},
                                                                 'pending': {'core_job': 0}, 'migrations': [1]},
                                      unchanged=engine_module.unchanged,
                                      render_environment=lambda original, revision, environment: original)
        fake_footprint = SimpleNamespace(snapshot=lambda path: self.venv, summary=footprint.summary,
                                         requirement_pins=footprint.requirement_pins,
                                         requirements_mismatch=footprint.requirements_mismatch)
        backup = SimpleNamespace(verify_report=lambda path, **kwargs: {
            'report_sha256': 'e' * 64, 'run_id': 'r', 'restore_run_id': 's', 'source_commit': BASE})
        modules = {'venv_footprint': fake_footprint, 'rebuild_release_backup': backup}
        patches = {
            'ops_module': lambda name, source=None: modules[name], 'load_engine': lambda: self.engine,
            'ROOT': self.root, 'git_environment_clean': lambda: {'refused_variables_present': 0},
            'candidate_worktree': lambda candidate: {'head': candidate},
            'shared_tree_at_base': lambda base: {'head': base}, 'origin_main_is': lambda candidate: {},
            'trusted_gate_scripts': lambda base: {name: 'c' * 64 for name in op.TRUSTED_GATE_SCRIPTS},
            'merge_hooks': lambda: frozenset(), 'compute_manifest': lambda *args: self.manifest,
            'manifest_paths_on_disk': lambda manifest: {'paths': 1},
            'git': lambda repo, *arguments, **options: b'pypdf==6.21.4\n',
            'venv_sharing_units': lambda prior, services: ['quillmd-corti-candidate.service'],
            'foreign_idle': lambda units: {'idle': True, 'units': {}},
            'live_venv_users': lambda exclude=(): [{'pid': 1, 'unit': 'quillmd-corti-candidate.service'}],
            'locks_free': lambda: {}, 'outside_scheduled_windows': lambda moment: 'ok',
            'citation': lambda prior, candidate, gate_scripts: {'citation': '**Citation — 2 of 2**'},
            'operator_hashes': lambda: {name: 'd' * 64 for name in op.OPERATOR_FILES},
            'PENDING_ENVIRONMENT': self.root / 'absent-pending-env'}
        for name, value in patches.items():
            patcher = patch.object(op, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.args = SimpleNamespace(base=BASE, candidate=CANDIDATE, manifest_sha256=None, new_dot_path=[],
                                    declaration=self.root / 'missing.md', backup_report=self.root / 'backup.json')

    def test_before_the_declaration_only_the_declaration_rows_fail_and_nothing_secret_is_reported(self):
        report, context = op.preflight(self.args)
        failed = sorted(row['check'] for row in report['checks'] if not row['passed'])
        self.assertEqual(failed, ['declaration_contract', 'declaration_provenance', 'strict_declaration_gate'])
        rows = [row['check'] for row in report['checks']]
        for name in ('git_environment_clean', 'trusted_gate_scripts', 'declared_new_dot_paths',
                     'manifest_paths_unobstructed'):
            self.assertIn(name, rows)
        self.assertEqual(context['environment']['original'], self.environment)
        self.assertNotIn(self.environment.decode().strip(), json.dumps(report, default=str))
        contract = op.contract_from(report['contract_block'])
        self.assertEqual(contract['requirements_mismatch'], {'pypdf': {'required': '6.21.4', 'installed': '6.21.1'}})
        self.assertEqual(contract['code_candidate'], CANDIDATE)
        self.assertEqual(contract['venv']['footprint_sha256'], self.venv['footprint_sha256'])
        self.assertEqual(report['measured']['database']['tables'], {'core_encounter': 5})
        self.assertIsNone(self.engine.BASE)  # the binding is restored after the preflight

    def test_as1_the_preflight_prints_the_declared_dot_paths_it_admitted(self):
        planned = ['cpt-studio/.gitignore', 'cpt-studio/deploy/.dockerignore']
        entries = [('M', '100644', '100644', 'a' * 40, 'b' * 40, 'rebuild/requirements.txt'),
                   *[('A', '000000', '100644', '0' * 40, 'c' * 40, name) for name in planned]]

        def compute(repo, base, candidate, hooks, new_dot_paths):
            return op.build_manifest(BASE, entries, lambda blob: blob.encode(), hooks=hooks,
                                     base_paths=frozenset({'rebuild', 'rebuild/requirements.txt'}),
                                     new_dot_paths=new_dot_paths)
        declared = SimpleNamespace(**dict(vars(self.args), new_dot_path=list(reversed(planned))))
        stale = SimpleNamespace(**dict(vars(self.args), new_dot_path=planned + ['cpt-studio/.npmrc']))
        with patch.object(op, 'compute_manifest', compute):
            report, _ = op.preflight(declared)
            undeclared, _ = op.preflight(self.args)
            stale_report, _ = op.preflight(stale)
        rows = {row['check']: row for row in report['checks']}
        self.assertEqual(rows['declared_new_dot_paths']['detail'], {'source': 'command_line', 'new_dot_paths': planned})
        self.assertEqual(rows['whole_repository_manifest']['detail']['new_dot_paths_admitted'], planned)
        self.assertEqual(op.summary(report)['measured']['manifest_facts']['new_dot_paths'], planned)
        self.assertEqual(op.contract_from(report['contract_block'])['new_dot_paths'], planned)
        self.assertEqual(sorted(row['check'] for row in report['checks'] if not row['passed']),
                         ['declaration_contract', 'declaration_provenance', 'strict_declaration_gate'])
        for value, label in ((undeclared, 'untracked_dot_path'), (stale_report, 'declared_dot_path_not_in_delta')):
            with self.subTest(label=label):
                failed = {row['check']: row['reason'] for row in value['checks'] if not row['passed']}
                self.assertEqual(failed['whole_repository_manifest'], label)
                self.assertNotIn('contract_block', value)

    def test_a_changed_manifest_busy_units_or_a_stray_process_fail_their_rows(self):
        changed = SimpleNamespace(**vars(self.args))
        changed.manifest_sha256 = '0' * 64
        with patch.object(op, 'foreign_idle', lambda units: {'idle': False, 'units': {}}), \
                patch.object(op, 'live_venv_users', lambda exclude=(): [{'pid': 2, 'unit': None}]):
            report, _ = op.preflight(changed)
        failed = {row['check'] for row in report['checks'] if not row['passed']}
        self.assertTrue({'manifest_equals_the_preflight', 'venv_sharing_units_idle',
                         'no_undeclared_live_venv_process'} <= failed)

    def test_without_trusted_gate_scripts_the_citation_and_the_strict_gate_cannot_pass(self):
        with patch.object(op, 'trusted_gate_scripts', lambda base: op.require(False, 'trusted_gate_script_file')):
            report, _ = op.preflight(self.args)
        reasons = {row['check']: row.get('reason') for row in report['checks'] if not row['passed']}
        self.assertEqual((reasons['trusted_gate_scripts'], reasons['citation'], reasons['strict_declaration_gate']),
                         ('trusted_gate_script_file', 'prerequisite_failed', 'prerequisite_failed'))


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
        self.assertEqual(op.arguments(execute).new_dot_path, [])
        self.assertEqual(op.arguments(self.argv('--new-dot-path', 'cpt-studio/deploy/.dockerignore', '--new-dot-path',
                                                'cpt-studio/.gitignore')).new_dot_path,
                         ['cpt-studio/deploy/.dockerignore', 'cpt-studio/.gitignore'])
        bad = [['--base', 'abc'] + self.argv()[2:], self.argv()[:2] + ['--candidate', BASE] + self.argv()[4:],
               self.argv('--execute'), self.argv('--execute', '--manifest-sha256', 'a' * 64),
               self.argv('--evidence-directory', str(self.root / 'e')), self.argv('--manifest-sha256', 'xyz'),
               self.argv()[:5] + ['relative.md'] + self.argv()[6:],
               self.argv()[:9] + [str(self.root / '../x.json')],
               # AS-1: exact new dot paths, never .git or .env*, and never on the act's command line.
               self.argv('--new-dot-path', '.env.local'), self.argv('--new-dot-path', 'cpt-studio/.git'),
               self.argv('--new-dot-path', 'cpt-studio/.*'), self.argv('--new-dot-path', 'cpt-studio/app.py'),
               self.argv('--new-dot-path', '/cpt-studio/.gitignore'),
               execute + ['--new-dot-path', 'cpt-studio/.gitignore']]
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
                   'measured': {'manifest': manifest, 'manifest_sha256': 'a' * 64, 'backup': {},
                                'gate_scripts': {name: 'e' * 64 for name in op.TRUSTED_GATE_SCRIPTS}},
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

    def run_execute(self, preflight_value, act_value=None, act_error=None, write_receipt=True):
        execute = self.argv('--execute', '--evidence-directory', str(self.root / 'evidence'),
                            '--manifest-sha256', 'a' * 64)
        os.chdir(op.SOURCE)
        runner = {'RULED_MUTATION_DECLARATION': str(self.declaration), 'RULED_MUTATION_DECL_COMMIT': 'd' * 40}

        def act(engine, plan, context, footprint):
            if act_error:
                raise act_error
            (Path(plan['evidence_directory'])).mkdir(mode=0o700)
            if write_receipt:
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
        self.assertEqual(plan['gate_scripts'], {name: 'e' * 64 for name in op.TRUSTED_GATE_SCRIPTS})
        self.assertEqual(plan['plan_sha256'], op.sha(op.canonical({k: v for k, v in plan.items()
                                                                    if k != 'plan_sha256'})))
        self.assertTrue(json.loads((self.root / 'result.json').read_text())['all_postconditions_passed'])
        for name in ('result.json',):
            (self.root / name).unlink()
        shutil.rmtree(self.root / 'evidence')
        code, _ = self.run_execute(self.passing(True), ({'complete': True}, False))
        self.assertEqual(code, 2)
        (self.root / 'result.json').unlink()
        shutil.rmtree(self.root / 'evidence')
        code, _ = self.run_execute(self.passing(True), ({'complete': True, 'receipt_retained': False}, False),
                                   write_receipt=False)
        self.assertEqual(code, 2)
        self.assertIsNone(json.loads((self.root / 'result.json').read_text())['receipt_sha256'])

    def test_execute_failure_is_recorded_with_a_fixed_label_and_the_recovery_outcome(self):
        refusal = op.Refusal('installation_failed_inspect_retained_evidence')
        refusal.outcome = {'recovery': 'restore', 'original_release_serving': True}
        with self.assertRaises(op.Refusal):
            self.run_execute(self.passing(True), act_error=refusal)
        value = json.loads((self.root / 'result.json').read_text())
        self.assertEqual((value['label'], value['recovery']),
                         ('installation_failed_inspect_retained_evidence', refusal.outcome))

    def test_a_manifest_that_moved_since_the_preflight_refuses(self):
        report, context = self.passing(True)
        context['measured']['manifest_sha256'] = 'b' * 64
        with self.assertRaises(op.Refusal):
            self.run_execute((report, context), ({'complete': True}, True))


if __name__ == '__main__':
    unittest.main()
