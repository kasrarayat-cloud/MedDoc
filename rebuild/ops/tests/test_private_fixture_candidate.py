"""Bounded fixture preparation controls; no factory CLI, host process or provider execution."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import tarfile

from ops import private_fixture_candidate as f
from ops import v1_private_install_preparation as p

ROOT = Path(__file__).resolve().parents[3]
TARGET = 'a' * 40


def archive(files, target=TARGET):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.PAX_FORMAT,
                      pax_headers={'comment': target}) as stream:
        for name, data in files:
            item = tarfile.TarInfo(name); item.size = len(data)
            stream.addfile(item, io.BytesIO(data))
    return output.getvalue()


def tree_for(files):
    return {name: ('100644', 'blob', hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest())
            for name, data in files}


class PrivateFixtureCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.helpers = {name: (ROOT / 'rebuild/ops/fixtures/private_demo_789c' / name).read_bytes()
                       for name in f.HELPERS}
        cls.schema = (ROOT / f.SCHEMA_PATH).read_bytes()
        schema = json.loads(cls.schema)
        paths = p.REQUIRED_SOURCE | {'rebuild/core/migrations/' + name + '.py'
            for name in {**schema['baseline_prefix_sha256'], **schema['forward_migration_sha256']}}
        cls.files = [(path, (ROOT / path).read_bytes()) for path in sorted(paths)]
        cls.archive = archive(cls.files); cls.tree = tree_for(cls.files)
        cls.declaration = {'format': 'quillmd-private-v1-preparation-v1', 'baseline': p.BASELINE,
            'target': TARGET, 'schema_sha256': p.SCHEMA_SHA256,
            'source_sha256': {name: p.sha(raw) for name, raw in cls.files}, 'data_mode': 'synthetic',
            'payment_mode': 'test', 'public_maintenance': True, 'cpt_enabled': False}
        cls.evidence = {'ci': [{'workflow': name, 'head_sha': TARGET, 'run_id': i + 1,
            'attempt': 1, 'status': 'completed', 'conclusion': 'success'}
            for i, name in enumerate(sorted(p.WORKFLOWS))],
            'source_refutation': {'target': TARGET, 'complete': True, 'clinical_unsafe': 0, 'word_unsafe': 0},
            'ai_mode': 'fixture', 'isolated_state': True}
        cls.word = {'runtime': f.WORD_RUNTIME, 'manifest': f.WORD_MANIFEST,
                    'manifest_sha256': f.WORD_SHA256, 'qualification': True}

    def test_archive_matches_supplied_full_tree_and_refuses_omitted_changed_duplicate_or_secret_bytes(self):
        self.assertEqual(f.archive_sources(self.archive, TARGET, self.tree), dict(self.files))
        variants = [(archive(self.files, 'b' * 40), self.tree),
                    (archive(self.files[:-1]), self.tree),
                    (archive(self.files + [self.files[0]]), self.tree),
                    (archive(self.files), {**self.tree, 'rebuild/omitted.py': ('100644', 'blob', 'b' * 40)}),
                    (archive([('rebuild/.env', b'synthetic forbidden environment')]),
                     tree_for([('rebuild/.env', b'synthetic forbidden environment')])),
                    (archive([('rebuild/../outside.py', b'x')]), tree_for([('rebuild/../outside.py', b'x')]))]
        changed = dict(self.tree); changed[self.files[0][0]] = ('100644', 'blob', 'b' * 40)
        variants.append((self.archive, changed))
        for raw, tree in variants:
            with self.subTest(tree_count=len(tree)), self.assertRaises(ValueError):
                f.archive_sources(raw, TARGET, tree)

    def test_retained_helpers_are_pinned_and_each_new_launcher_profile_uses_fresh_fixture_invite_settings(self):
        destination, database, rendered = f.helpers(TARGET, self.helpers)
        self.assertNotEqual(destination, f.OLD_ROOT)
        self.assertEqual(database, 'quillmd_qa_int_sol_' + TARGET[:8])
        for content in rendered.values():
            self.assertNotIn(str(f.OLD_ROOT).encode(), content)
            self.assertNotIn(f.OLD_RELEASE.encode(), content)
        with tempfile.TemporaryDirectory() as directory:
            scratch = Path(directory); source = scratch / 'source'; source.mkdir()
            namespace = {'__name__': 'fixture_launcher_control', '__file__': str(scratch / 'qa_launch.py')}
            exec(compile(rendered['qa_launch.py'], namespace['__file__'], 'exec'), namespace)
            namespace.update(SRC=source, WORD_FILE=scratch / 'absent-word', PASSWORD_FILE=scratch / 'absent-password',
                             secret_key=lambda create: 'synthetic unit secret')
            with patch.dict('os.environ', {'QUILLMD_AI_MODE': 'live', 'ANTHROPIC_API_KEY': 'synthetic never send',
                                          'OPENAI_API_KEY': 'synthetic never send'}):
                for profile in ('ci', 'v1'):
                    for surface in ('doctor', 'admin'):
                        env = namespace['build'](SimpleNamespace(surface=surface, profile=profile, wm_replay=False), False)
                        self.assertEqual(env['QUILLMD_AI_MODE'], 'fixture')
                        self.assertEqual(env['QUILLMD_AI_MODEL'], p.MODEL)
                        self.assertEqual(env['QUILLMD_V3_FIELD_RELATIONS'], '1')
                        self.assertEqual(env['QUILLMD_REGISTRATION'], 'invite')
                        self.assertEqual(env['QUILLMD_DATA_MODE'], 'synthetic')
                        self.assertEqual(env['QUILLMD_STRIPE_MODE'], 'test')
                        self.assertEqual(env['QUILLMD_EMAIL_MODE'], 'file')
                        self.assertEqual(env['QUILLMD_ADMIN_SITE'], '1' if surface == 'admin' else '0')
                        self.assertNotIn('ANTHROPIC_API_KEY', env); self.assertNotIn('OPENAI_API_KEY', env)
        changed = {**self.helpers, 'qa_launch.py': self.helpers['qa_launch.py'] + b'\n# changed\n'}
        with self.assertRaises(ValueError): f.helpers(TARGET, changed)
        with self.assertRaises(ValueError): f.helpers(f.OLD_RELEASE, self.helpers)

    def test_bundle_is_prepared_fixture_configuration_not_live_provider_or_installed_authority(self):
        _, sources, result = f.bundle(self.declaration, self.evidence, self.schema, self.archive,
                                      self.tree, self.helpers, self.word)
        self.assertEqual(set(sources), set(self.tree))
        self.assertTrue(result['prepared_only']); self.assertFalse(result['launched'])
        self.assertEqual(result['installed_units'], [])
        self.assertFalse(result['installed_mutation_performed'])
        self.assertFalse(result['old_demo_modified'])
        self.assertFalse(result['plan']['execution_authorized'])
        self.assertEqual(result['ports'], [9160, 9161])
        self.assertEqual(result['model_configuration'], p.MODEL)
        self.assertNotIn('returned_model', result)
        for updates in ({'ai_mode': 'live'}, {'isolated_state': False},
                        {'source_refutation': {'target': TARGET, 'complete': True, 'clinical_unsafe': 1, 'word_unsafe': 0}}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                f.bundle(self.declaration, {**self.evidence, **updates}, self.schema, self.archive,
                         self.tree, self.helpers, self.word)

    def test_runtime_redirection_cannot_turn_manifest_verification_into_an_arbitrary_file_read(self):
        for key, value in (('manifest', '/tmp/unapproved-manifest'), ('runtime', '/tmp/unapproved-runtime'),
                           ('manifest_sha256', 'b' * 64), ('qualification', False)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                f.bundle(self.declaration, self.evidence, self.schema, self.archive,
                         self.tree, self.helpers, {**self.word, key: value})

    def test_task_metadata_refuses_foreign_or_linked_paths_before_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); file = root / 'declaration.json'
            file.write_text('{}'); file.chmod(0o600)
            with patch.object(f, 'RUNTIME', root):
                self.assertEqual(f.protected_metadata(file), {})
                linked = root / 'linked.json'; linked.symlink_to(file)
                with patch('os.open', side_effect=AssertionError('Must refuse before open')):
                    with self.assertRaises(ValueError): f.protected_metadata(linked)
                    with self.assertRaises(ValueError): f.protected_metadata(root.parent / 'foreign.json')
                file.chmod(0o644)
                with self.assertRaises(ValueError): f.protected_metadata(file)

    def test_readonly_inventory_discovers_declared_git_bytes_without_helper_reads_ci_or_host_actions(self):
        source = '/opt/meddoc-pro/.worktrees/synthetic-fixture-inventory'
        tree_raw = b'\0'.join((' '.join(value) + '\t' + name).encode()
                              for name, value in self.tree.items()) + b'\0'
        replies = {('rev-parse', 'HEAD'): TARGET.encode() + b'\n', ('status', '--porcelain'): b'',
                   ('ls-tree', '-rz', '--full-tree', TARGET, '--', 'rebuild'): tree_raw,
                   ('archive', TARGET, 'rebuild'): self.archive,
                   ('show', TARGET + ':' + f.SCHEMA_PATH): self.schema,
                   ('rev-parse', '--show-object-format'): b'sha1\n'}
        def git(command, **kwargs):
            self.assertEqual(command[0], 'git')
            return replies[tuple(command[1:])]
        output = io.StringIO()
        with patch('sys.argv', ['factory', '--source', source, '--inventory', '--commit', TARGET]), \
             patch.object(f.subprocess, 'check_output', side_effect=git), \
             patch.object(f.subprocess, 'run', side_effect=AssertionError('No external checker or host action')), \
             patch.object(f, 'regular_bytes', side_effect=AssertionError('No retained file or credential read')), \
             patch('sys.stdout', output):
            f.main()
        result = json.loads(output.getvalue())
        self.assertEqual(result['source_sha256'], self.declaration['source_sha256'])
        self.assertEqual(result['target'], TARGET)

    def test_cli_rejects_tracked_environment_before_archive_or_read_and_bad_ci_before_git(self):
        source = '/opt/meddoc-pro/.worktrees/synthetic-fixture-inventory'
        def git(command, **kwargs):
            if command[1:] == ['rev-parse', 'HEAD']: return TARGET.encode() + b'\n'
            if command[1:] == ['status', '--porcelain']: return b''
            if command[1] == 'ls-tree': return b'100644 blob ' + b'a' * 40 + b'\trebuild/.env\0'
            raise AssertionError('Archive/credential access must not occur')
        with patch('sys.argv', ['factory', '--source', source, '--inventory', '--commit', TARGET]), \
             patch.object(f.subprocess, 'check_output', side_effect=git), \
             patch.object(f, 'regular_bytes', side_effect=AssertionError('No file read')), self.assertRaises(ValueError):
            f.main()
        with patch('sys.argv', ['factory', '--source', '/opt/meddoc-pro/.worktrees/../outside',
                               '--inventory', '--commit', TARGET]), \
             patch.object(f.subprocess, 'check_output', side_effect=AssertionError('Must refuse before Git')), \
             self.assertRaises(ValueError):
            f.main()
        evidence = copy.deepcopy(self.evidence); evidence['ci'][0]['head_sha'] = 'b' * 40
        with patch('sys.argv', ['factory', '--source', source, '--declaration', '/test/declaration.json',
                               '--evidence', '/test/evidence.json']), \
             patch.object(f, 'protected_metadata', side_effect=[self.declaration, evidence]), \
             patch.object(f.subprocess, 'check_output', side_effect=AssertionError('Must refuse before Git')), \
             self.assertRaises(ValueError):
            f.main()
