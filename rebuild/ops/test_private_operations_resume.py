"""Isolated fixtures for the one recorded activation resume; no host mutation."""
import copy
import hashlib
import json
import marshal
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from . import source_module
except ImportError:
    import source_module

ROOT = Path(__file__).resolve().parents[2]
resume = source_module.load('private_operations_resume_tested', ROOT / 'scripts/resume-private-operations.py')
activation = source_module.load('private_operations_resume_original_tested', ROOT / 'scripts/activate-private-operations.py')


class ResumeStateTests(unittest.TestCase):
    def report(self):
        return {'complete': False, 'failure_kind': 'RuntimeError', 'failure_services_stopped': True,
                'target': resume.FAILED_TARGET, 'stage': 'apply_only_declared_reconciliation_guard',
                'provider_calls': 0, 'state_directory': str(resume.PRIOR_STATE),
                'stopped_before': {'rows': {'synthetic': 'before'}},
                'stopped_after_migration': {'rows': {'synthetic': 'after'}}}

    def load_report(self, report):
        data = json.dumps(report).encode()
        with patch.object(resume, 'REPORT_SHA256', resume.sha(data)):
            return resume.failure_report(SimpleNamespace(checked_file=lambda *a, **kw: data))

    def test_only_exact_failed_stage_and_stopped_identity_accepted(self):
        self.assertEqual(self.load_report(self.report()), self.report())
        for key, value in (('complete', True), ('failure_kind', 'OtherFailure'),
                           ('failure_services_stopped', False), ('target', 'b' * 40),
                           ('stage', 'replace_release_setting_only'), ('provider_calls', 1),
                           ('state_directory', '/elsewhere'), ('stopped_after_migration', {})):
            wrong = {**self.report(), key: value}
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.load_report(wrong)

    def test_failure_record_bytes_are_pinned_before_interpretation(self):
        with self.assertRaisesRegex(RuntimeError, 'record changed'):
            resume.failure_report(SimpleNamespace(checked_file=lambda *a, **kw: json.dumps(self.report()).encode()))

    def test_target_scope_is_exact_three_paths(self):
        expected = {resume.SELF, resume.TEST, resume.DECL}
        resume.validate_changed(expected)
        for wrong in (expected - {resume.DECL}, expected | {'rebuild/core/views.py'},
                       expected | {'rebuild/ops/__pycache__/other.pyc'},
                       expected | {'docs/rebuild/unrelated.md'}):
            with self.subTest(wrong=wrong), self.assertRaises(RuntimeError):
                resume.validate_changed(wrong)

    def state(self):
        before = {'rows': {'core_encounter': {'rows': 1, 'sha256': 'c' * 64}},
                  'constraints': [['synthetic', 'constraint']], 'files': {'original': 'hash'},
                  'catalog': {'functions': [], 'triggers': []}}
        after = copy.deepcopy(before)
        after['catalog'] = {'functions': [{'name': activation.FUNCTION + '()', 'owner': 'quillmd_owner',
            'language': 'plpgsql', 'security_definer': False, 'config': None, 'acl': None, 'body': 'BEGIN reviewed; END;'}],
            'triggers': [{'name': activation.TRIGGER, 'table': 'core_costreconciliation',
                'function': activation.FUNCTION, 'type': 27, 'enabled': 'O', 'args': '', 'when': None}]}
        return {'stopped_before': before, 'stopped_after_migration': after}

    def test_saved_json_and_live_tuples_compare_without_false_refusal(self):
        report = self.state()
        live = copy.deepcopy(report['stopped_after_migration'])
        live['constraints'] = [('synthetic', 'constraint')]
        resume.check_state(report, live, activation, 'BEGIN reviewed; END;')

    def test_any_actual_row_file_constraint_or_trigger_delta_refuses(self):
        report = self.state()
        for key in ('rows', 'files', 'constraints', 'catalog'):
            live = copy.deepcopy(report['stopped_after_migration']); live[key] = {'unreviewed': 'change'}
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                resume.check_state(report, live, activation, 'BEGIN reviewed; END;')

    def test_matching_after_snapshot_does_not_bypass_original_additive_guard(self):
        report = self.state()
        report['stopped_after_migration']['catalog']['triggers'][0]['enabled'] = 'D'
        with self.assertRaisesRegex(RuntimeError, 'enabled unconditional'):
            resume.check_state(report, report['stopped_after_migration'], activation, 'BEGIN reviewed; END;')

    def test_retained_failure_lock_checks_digest_and_inode_without_deleting(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'failed.lock'; data = b'{"synthetic":"prior failure"}\n'
            path.write_bytes(data); path.chmod(0o600)
            word = SimpleNamespace(checked_file=lambda path, **kw: path.read_bytes())
            with patch.object(resume, 'FAILED_LOCK', path), patch.object(resume, 'FAILED_LOCK_SHA256', resume.sha(data)):
                saved, identity = resume.exact_lock(word)
                self.assertEqual(saved, data); self.assertEqual(identity['inode'], path.stat().st_ino)
                path.write_bytes(b'changed')
                with self.assertRaisesRegex(RuntimeError, 'lock changed'):
                    resume.exact_lock(word)
            self.assertTrue(path.exists())

    def test_new_private_evidence_cannot_overwrite_or_follow_existing_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); path = root / 'evidence.json'
            resume.private_bytes(path, b'original')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            with self.assertRaises(FileExistsError):
                resume.private_bytes(path, b'replacement')
            link = root / 'link'; link.symlink_to(path)
            with self.assertRaises(FileExistsError):
                resume.private_bytes(link, b'replacement')
            self.assertEqual(path.read_bytes(), b'original')


class CachePermissionFixtureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.app = Path(temporary.name)
        (self.app / 'ops/__pycache__').mkdir(parents=True)
        pins = {}
        for name in resume.CACHES:
            source = self.app / 'ops' / (name + '.py')
            source.write_bytes(b'PUBLIC_SYNTHETIC_LABEL = "not a secret"\n')
            data = b'\0' * 16 + marshal.dumps(compile(source.read_bytes(), str(source), 'exec'))
            cache = self.app / 'ops/__pycache__' / (name + '.cpython-312.pyc')
            cache.write_bytes(data); cache.chmod(0o600)
            pins[name] = (resume.sha(data), len(data), resume.sha(source.read_bytes()))
        self.pins = patch.object(resume, 'CACHES', pins); self.pins.start(); self.addCleanup(self.pins.stop)
        self.real_fstat = os.fstat
        self.owner = 1000
        def file_info(fd):
            got = self.real_fstat(fd)
            return SimpleNamespace(**{key: getattr(got, key) for key in ('st_mode', 'st_nlink', 'st_size', 'st_dev', 'st_ino', 'st_mtime_ns')},
                                   st_uid=self.owner, st_gid=1000)
        # Explicitly model the pinned host account in temporary-file fixtures.
        # CI need not have an account named claude or run with host UID1000.
        for context in (patch.object(resume.os, 'getuid', return_value=1000), patch.object(resume.os, 'fstat', side_effect=file_info)):
            context.start(); self.addCleanup(context.stop)

    def cache(self, name='source_module'):
        return self.app / 'ops/__pycache__' / (name + '.cpython-312.pyc')

    def test_only_three_modes_change_with_identical_bytes_inodes_owners_and_mtime(self):
        before = resume.cache_inventory(0o600, app=self.app)
        outside = self.app / 'private.env'; outside.write_bytes(b'private synthetic'); outside.chmod(0o600)
        after = resume.repair_cache_modes(before, app=self.app)
        self.assertEqual({key: {**value, 'mode': 0o600} for key, value in after.items()}, before)
        self.assertEqual(len(after), 3)
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o600)
        self.assertEqual(outside.read_bytes(), b'private synthetic')

    def test_hash_owner_mode_and_source_changes_refuse_before_chmod(self):
        before = resume.cache_inventory(0o600, app=self.app)
        path = self.cache(); original = path.read_bytes()
        path.write_bytes(b'wrong bytes')
        with self.assertRaises(RuntimeError):
            resume.repair_cache_modes(before, app=self.app)
        path.write_bytes(original)
        self.owner = 1001
        with self.assertRaises(RuntimeError):
            resume.cache_inventory(0o600, app=self.app)
        self.owner = 1000; path.chmod(0o644)
        with self.assertRaises(RuntimeError):
            resume.cache_inventory(0o600, app=self.app)
        path.chmod(0o600)
        (self.app / 'ops/source_module.py').write_bytes(b'CHANGED = True\n')
        with self.assertRaises(RuntimeError):
            resume.cache_inventory(0o600, app=self.app)
        self.assertTrue(all(stat.S_IMODE(self.cache(name).stat().st_mode) == 0o600 for name in resume.CACHES))

    def test_symlinks_hardlinks_and_unknown_repair_paths_refuse(self):
        before = resume.cache_inventory(0o600, app=self.app)
        with self.assertRaises(RuntimeError):
            resume.repair_cache_modes({**before, 'ops/__pycache__/other.pyc': {}}, app=self.app)
        path = self.cache(); target = path.with_name('retained-original.pyc'); path.rename(target); path.symlink_to(target)
        with self.assertRaises(RuntimeError):
            resume.cache_inventory(0o600, app=self.app)
        path.unlink(); target.rename(path)
        os.link(path, self.app / 'another-link')
        with self.assertRaises(RuntimeError):
            resume.cache_inventory(0o600, app=self.app)

    def test_matching_hash_pins_cannot_substitute_compiled_source_identity(self):
        source = self.app / 'ops/source_module.py'; source.write_bytes(b'OTHER_SOURCE = 17\n')
        cache_hash, size, _ = resume.CACHES['source_module']
        resume.CACHES['source_module'] = (cache_hash, size, resume.sha(source.read_bytes()))
        with self.assertRaisesRegex(RuntimeError, 'compiled nonsecret source'):
            resume.cache_inventory(0o600, app=self.app)

    def test_descriptor_identity_change_between_inventory_and_chmod_refuses(self):
        before = resume.cache_inventory(0o600, app=self.app)
        real_open = resume.os.open
        calls = 0
        def raced(path, flags, *args):
            nonlocal calls
            calls += 1
            if calls == 4:
                path = Path(path)
                replacement = path.with_suffix('.replacement')
                replacement.write_bytes(path.read_bytes()); replacement.chmod(0o600)
                replacement.replace(path)
            return real_open(path, flags, *args)
        with patch.object(resume.os, 'open', side_effect=raced), self.assertRaisesRegex(RuntimeError, 'during repair'):
            resume.repair_cache_modes(before, app=self.app)
        self.assertTrue(all(stat.S_IMODE(self.cache(name).stat().st_mode) == 0o600 for name in resume.CACHES))


if __name__ == '__main__':
    unittest.main()
