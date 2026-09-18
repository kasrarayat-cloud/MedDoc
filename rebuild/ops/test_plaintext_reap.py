"""Guards of the plaintext recovery-and-reap act: a fixed deletion list, accounting before removal, secrets never printed,
and root programs that behave as claimed on real directory trees."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/verify-and-reap-fresh-plaintext.py'
MIGRATE = ROOT / 'scripts/migrate-fresh-storage.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def function_source(name):
    source = SCRIPT.read_text()
    node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(source, node)


class DeletionList(unittest.TestCase):
    def setUp(self):
        self.reap = load('reap_plaintext', SCRIPT)

    def test_exactly_the_declared_plaintext_copies(self):
        paths = [t['path'] for t in self.reap.TARGETS]
        runtime = '/opt/meddoc-pro/rebuild/.runtime/'
        self.assertEqual(paths, ['/var/lib/quillmd-rollback-20260918', runtime + 'files', runtime + 'mail']
                         + [runtime + f'restore-checks/restore-{run}/files' for run in sorted(self.reap.RESTORE_COPIES)])
        self.assertEqual(len(self.reap.RESTORE_COPIES), 6)
        for target in self.reap.TARGETS:
            self.assertEqual(os.path.normpath(target['path']), target['path'])
            self.assertTrue(target['path'].startswith('/'))
            self.assertIn(target['kind'], ('rollback', 'state'))
            self.assertTrue(target['origin'])
            if target['kind'] == 'state':
                self.assertIn(target['live'], self.reap.LIVE)

    def test_declared_counts_match_the_declaration_totals(self):
        text = (ROOT / self.reap.DECL).read_text()
        files, size = re.search(r'Totals: \*\*([\d,]+) files, ([\d,]+) bytes, nine directories\.\*\*', text).groups()
        self.assertEqual(sum(t['files'] for t in self.reap.TARGETS), int(files.replace(',', '')))
        self.assertEqual(sum(t['bytes'] for t in self.reap.TARGETS), int(size.replace(',', '')))
        self.assertEqual(len(self.reap.TARGETS), 9)
        for run, (backup, commit, count, size) in self.reap.RESTORE_COPIES.items():
            self.assertIn(f'restore-{run}/files', text)
            self.assertIn(backup, text)
            self.assertIn(f'| {count} | {size:,} |', text)

    def test_nothing_protected_is_a_target_or_inside_one(self):
        protected = self.reap.PROTECTED
        for needed in ('/var/lib/quillmd', '/etc/quillmd', '/var/lib/quillmd-encrypted', '/opt/meddoc-pro/backups'):
            self.assertIn(needed, protected)
        for target in self.reap.TARGETS:
            for path in protected:
                self.assertFalse(target['path'] == path or target['path'].startswith(path + '/') or path.startswith(target['path'] + '/'),
                                 (target['path'], path))
        # The verification report of every restore check stays; only its decrypted documents go.
        self.assertTrue(all(t['path'].endswith('/files') for t in self.reap.TARGETS if 'restore-checks' in t['path']))

    def test_the_storage_act_allows_this_act_as_a_later_rollback_target(self):
        migrate = load('migrate_for_reap', MIGRATE)
        # The reap merge is the rollback target from now on, so everything it changes since the baseline must be allowed.
        if not subprocess.run(['git', '-C', str(ROOT), 'cat-file', '-e', migrate.BASELINE + '^{commit}'], capture_output=True).returncode:
            changed = set(subprocess.check_output(['git', '-C', str(ROOT), 'diff', '--name-only', migrate.BASELINE, 'HEAD'], text=True).split())
            self.assertEqual(sorted(changed - migrate.ALLOWED), [])
        self.assertEqual(migrate.ROLLBACK, self.reap.ROLLBACK)
        self.assertIn(self.reap.DECL, migrate.REAP_PATHS)
        self.assertIn(self.reap.SELF, migrate.REAP_PATHS)
        self.assertIn('rebuild/ops/test_plaintext_reap.py', migrate.REAP_PATHS)
        self.assertTrue((ROOT / self.reap.SELF).is_file())


class ActOrdering(unittest.TestCase):
    def setUp(self):
        self.source = SCRIPT.read_text()
        self.main = function_source('main')

    def test_nothing_is_removed_without_execute_and_the_committed_declaration(self):
        read_only = self.main.split('if not args.execute:')[0]
        self.assertNotIn('ROOT_REAP', read_only)
        self.assertNotIn('drill(', read_only)
        for check in ('validate_restore_report(', "backup.get('decrypted_files_written') == 0", 'live_rows == backup.get', 'verify(', 'account('):
            self.assertIn(check, read_only)
        execute = self.main.split('if not args.execute:')[1]
        self.assertLess(execute.index('RULED_MUTATION_DECL_COMMIT'), execute.index('private_write(lock'))
        self.assertLess(execute.index('private_write(lock'), execute.index('drill('))

    def test_recovery_is_proved_and_accounting_repeated_before_removal(self):
        execute = self.main.split('if not args.execute:')[1]
        order = ['drill(', "'Rows changed across the recovery drill.'", "result['after_drill'] = verify(", 'accounting = account(', 'ROOT_REAP']
        positions = [execute.index(marker) for marker in order]
        self.assertEqual(positions, sorted(positions))
        after = execute.split('ROOT_REAP')[1]
        for check in ("'A declared plaintext copy is still present.'", "'Rows changed.'", "'Live files changed.'",
                      "'The encrypted backup is no longer intact.'", 'verify('):
            self.assertIn(check, after)

    def test_accounting_demands_identity_with_the_live_encrypted_store(self):
        account = function_source('account')
        self.assertIn("not entry['unaccounted']", account)
        self.assertIn("entry['census'] == {'pg_data': copied['pg'], 'state': copied['state']}", account)
        self.assertIn("entry['present']", account)
        self.assertIn("v.get('special')", account)

    def test_the_drill_closes_the_volume_through_the_reviewed_unit_control_only(self):
        drill = function_source('drill')
        self.assertIn("m.systemctl('stop', ['quillmd-fresh-volume.service'], image)", drill)
        self.assertLess(drill.index("m.systemctl('stop'"), drill.index('m.ROOT_WRITE_PROBE'))
        self.assertLess(drill.index('m.ROOT_WRITE_PROBE'), drill.index("m.systemctl('start', ['quillmd-fresh-volume.service']"))
        self.assertIn("closed['pg_data_listing'] == []", drill)
        self.assertIn("after_manual['pg_data_listing'] == []", drill)
        self.assertNotIn('reboot', self.source)

    def test_no_bulk_deletion_primitives_and_no_key_slot_changes(self):
        for forbidden in ('shutil.rmtree', 'rm -rf', "'-rf'", '/usr/bin/rm', 'luksKillSlot', 'luksRemoveKey', 'luksErase', 'luksAddKey', 'wipefs', 'docker rm'):
            self.assertNotIn(forbidden, self.source)
        self.assertEqual(self.source.count("'/usr/bin/shred'"), 1)
        self.assertIn("'/usr/bin/shred','-u','-n','3','-z'", self.reap_program())

    def reap_program(self):
        return load('reap_program', SCRIPT).ROOT_REAP

    def test_key_check_never_prints_key_material(self):
        keys = load('reap_keys', SCRIPT).ROOT_KEYS
        emitted = keys[keys.index('emit('):]
        self.assertNotIn('phrase', emitted)
        self.assertIn('del phrase', keys)
        self.assertLess(keys.index('del phrase'), keys.index('emit('))
        self.assertNotIn("'luksDump'", keys.split('lines=')[1])
        self.assertIn("l.endswith(': luks2')", keys)
        verify = function_source('verify')
        self.assertIn("keys['slots'] == ['0: luks2', '1: luks2']", verify)
        for flag in ("keys['keyfile_opens_slot0']", "keys['recovery_file_opens_slot1']", "keys['typed_recovery_opens_slot1']"):
            self.assertIn(flag, verify)


class StorageAndBackupChecks(unittest.TestCase):
    def setUp(self):
        self.reap = load('reap_checks', SCRIPT)

    def test_a_mount_stacked_over_the_encrypted_one_is_not_encrypted_storage(self):
        mapper = 'quillmd-fresh-encrypted'
        good = {'/var/lib/quillmd': '/dev/mapper/quillmd-fresh-encrypted[/state]'}
        self.assertTrue(self.reap.on_encrypted_mapper(good, mapper))
        for sources in ({'/var/lib/quillmd': '/dev/mapper/quillmd-fresh-encrypted[/state]\n/dev/sda2[/var/lib/plain]'},
                        {'/var/lib/quillmd': '/dev/sda2[/var/lib/quillmd]'}, {'/var/lib/quillmd': 'ERROR'},
                        {'/var/lib/quillmd': '/dev/mapper/quillmd-fresh-encrypted-other[/state]'}, {}):
            with self.subTest(sources=sources):
                self.assertFalse(self.reap.on_encrypted_mapper(sources, mapper))

    def test_the_backup_must_match_every_live_table_not_just_the_total_count(self):
        main = function_source('main')
        read_only = main.split('if not args.execute:')[0]
        self.assertIn('live_tables(backup_tool) == backup_tables(backup_tool, backup)', read_only)
        self.assertIn("'backup': 'rebuild/ops/backup_restore.py'", SCRIPT.read_text())
        # The same fingerprint function and session settings the restore check uses.
        live = function_source('live_tables')
        self.assertIn('backup.fingerprint(query,', live)
        self.assertIn("SET timezone='UTC'; SET datestyle='ISO, MDY';", live)

    def test_a_failure_stops_the_running_shred_and_records_before_it_exits(self):
        main = function_source('main')
        handler = main.split('except BaseException as error:')[1]
        self.assertLess(handler.index('stop_reaping(m, image)'), handler.index('private_write(result_path'))
        # Keyed to whether removal ever began, not to a stage name a later step overwrites.
        self.assertIn("if not result.get('removal_started') and result['services_restarted']:", handler)
        execute = main.split('if not args.execute:')[1]
        self.assertLess(execute.index("result['removal_started'] = True"), execute.index('m.root(ROOT_REAP'))
        self.assertLess(handler.index('private_write(result_path'), handler.index('lock.unlink()'))
        stop = function_source('stop_reaping')
        self.assertLess(stop.index("inflight = REAPING['unit'], m.ACT['step']"), stop.index('m.root(ROOT_STOP_REAP'))
        self.assertLess(stop.index("m.ACT['step'] = inflight"), stop.index('m.settle_root_step('))
        loop = main.split("result['stage'] = 'removing_redundant_plaintext'")[1].split("result['stage'] = 'final_checks'")[0]
        self.assertLess(loop.index("result['reaped'].append(record)"), loop.index("require(record['removed']"))
        self.assertIn('timeout=REAP_MAX_SECONDS + 30 + 2 * 120 + 60', loop)  # the unit's bound, both deletes, and slack
        # systemd ignores RuntimeMaxSec on Type=oneshot units; TimeoutStartSec is the bound that applies to them.
        self.assertIn("'--property=Type=oneshot'", self.reap.ROOT_REAP)
        self.assertIn("'--property=TimeoutStartSec='+str(P['max_seconds'])", self.reap.ROOT_REAP)
        self.assertNotIn("'--property=RuntimeMaxSec=", self.reap.ROOT_REAP)
        stop = function_source('stop_reaping')
        order = ['m.root(ROOT_STOP_REAP', "m.ACT['step'] = inflight", 'm.settle_root_step(', 'm.root(ROOT_COUNT_LEFT']
        self.assertEqual([stop.index(x) for x in order], sorted(stop.index(x) for x in order))
        self.assertIn("'systemctl','stop',P['unit']+'.service'", self.reap.ROOT_STOP_REAP)


class RootPrograms(unittest.TestCase):
    """The root programs themselves, run by a real interpreter against temporary trees. Only the chroot and the systemd-run
    prefix are removed, each by an asserted one-occurrence replacement, so every line the act runs is the line tested."""

    @classmethod
    def setUpClass(cls):
        cls.reap = load('reap_root', SCRIPT)
        library = load('migrate_root', MIGRATE).ROOT_LIBRARY
        chroot = "os.chroot('/host');os.chdir('/');"
        prefix = "['systemd-run','--wait','--pipe','--collect','--quiet','--property=Type=oneshot',*cmd]"
        assert library.count(chroot) == 1 and library.count(prefix) == 1
        cls.library = library.replace(chroot, '').replace(prefix, 'list(cmd)')

    UNIT_PREFIX = "'systemd-run','--wait','--pipe','--collect','--quiet','--property=Type=oneshot','--unit='+P['unit'],'--property=TimeoutStartSec='+str(P['max_seconds']),"

    def run_program(self, name, params):
        code = self.library + getattr(self.reap, name)
        if name == 'ROOT_REAP':
            assert code.count(self.UNIT_PREFIX) == 1
            code = code.replace(self.UNIT_PREFIX, '')
        result = subprocess.run([sys.executable, '-B', '-c', code], input=json.dumps(params) + '\n', capture_output=True, text=True, timeout=120)
        return result

    def emit(self, name, params):
        result = self.run_program(name, params)
        self.assertEqual(result.returncode, 0, result.stderr[-800:])
        return json.loads(result.stdout.strip().splitlines()[-1])

    def tree(self, base, files):
        for relative, data in files.items():
            path = base / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return base

    def test_every_root_program_compiles_and_imports_nothing_after_the_chroot(self):
        library = load('migrate_imports', MIGRATE).ROOT_LIBRARY
        imported = set(re.search(r'^import ([\w,]+)$', library.split("os.chroot('/host')")[0], re.M).group(1).split(','))
        for name in ('ROOT_VERIFY_STORAGE', 'ROOT_KEYS', 'ROOT_ACCOUNT', 'ROOT_REAP', 'ROOT_STOP_REAP', 'ROOT_COUNT_LEFT'):
            code = getattr(self.reap, name)
            compile(library + code, name, 'exec')
            tree = ast.parse(code)
            self.assertFalse([n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))], name)
            used = {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
            modules = used & {'os', 'sys', 'json', 'subprocess', 'stat', 'hashlib', 'time', 'secrets', 'shutil', 're', 'base64', 'random', 'tempfile', 'datetime'}
            self.assertLessEqual(modules, imported, name)
        host = re.findall(r"host\('(/[^']+)'", self.reap.ROOT_VERIFY_STORAGE + self.reap.ROOT_KEYS + self.reap.ROOT_ACCOUNT + self.reap.ROOT_REAP)
        self.assertTrue(host)
        self.assertLessEqual(set(host), {'/usr/bin/findmnt', '/usr/sbin/cryptsetup', '/usr/bin/find'})

    def test_accounting_accepts_an_identical_copy_and_names_every_difference(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            live = self.tree(base / 'live/files', {'audio/a.wav': b'one', 'exports/e.docx': b'two'})
            mail = self.tree(base / 'live/mail', {'m.log': b'mail'})
            same = self.tree(base / 'same', {'audio/a.wav': b'one'})
            changed = self.tree(base / 'changed', {'audio/a.wav': b'ONE'})
            extra = self.tree(base / 'extra', {'exports/e.docx': b'two', 'exports/new.docx': b'three'})
            moved = self.tree(base / 'moved', {'exports/a.wav': b'one'})
            targets = [{'path': str(p), 'kind': 'state', 'live': 'files', 'origin': 'test'} for p in (same, changed, extra, moved)]
            view = self.emit('ROOT_ACCOUNT', {'targets': targets + [{'path': str(base / 'absent'), 'kind': 'state', 'live': 'files', 'origin': 'test'}],
                                               'live': {'files': str(live), 'mail': str(mail)}})
            got = {Path(e['path']).name: e.get('unaccounted') for e in view['targets']}
            self.assertEqual(got, {'same': [], 'changed': ['audio/a.wav'], 'extra': ['exports/new.docx'], 'moved': ['exports/a.wav'], 'absent': None})
            self.assertFalse(view['targets'][-1]['present'])
            self.assertEqual(view['live_counts'], {'files': 2, 'mail': 1})

    def test_rollback_accounting_reports_layout_census_and_state_differences(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            live = self.tree(base / 'live/files', {'a/x': b'x'})
            mail = self.tree(base / 'live/mail', {'m': b'm'})
            snap = self.tree(base / 'snap', {'pg_data/base/1': b'row', 'state/files/a/x': b'x', 'state/mail/m': b'm', 'state/proofs/doctor.json': b'{}'})
            target = [{'path': str(snap), 'kind': 'rollback', 'origin': 'test'}]
            view = self.emit('ROOT_ACCOUNT', {'targets': target, 'live': {'files': str(live), 'mail': str(mail)}})['targets'][0]
            self.assertEqual((view['top_level'], view['unaccounted'], view['unexpected_state']), (['pg_data', 'state'], [], []))
            self.assertEqual(view['census']['pg_data']['files'], 1)
            self.assertEqual(view['census']['state']['files'], 3)
            self.assertEqual(list(view['pg_data_files']), ['base/1'])
            (snap / 'state/mail/m').write_bytes(b'changed')
            (snap / 'state/tmp').mkdir()
            view = self.emit('ROOT_ACCOUNT', {'targets': target, 'live': {'files': str(live), 'mail': str(mail)}})['targets'][0]
            self.assertEqual((view['unaccounted'], view['unexpected_state']), (['mail/m'], ['tmp']))

    def test_accounting_refuses_a_symlinked_or_unresolved_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            real = self.tree(base / 'real', {'a': b'a'})
            (base / 'link').symlink_to(real)
            for path in (str(base / 'link'), str(base / 'real') + '/../real'):
                result = self.run_program('ROOT_ACCOUNT', {'targets': [{'path': path, 'kind': 'state', 'live': 'files', 'origin': 't'}],
                                                           'live': {'files': str(real)}})
                self.assertNotEqual(result.returncode, 0, path)
                self.assertIn('target is not a resolved directory', result.stderr)

    def reap_one(self, path):
        return self.emit('ROOT_REAP', {'path': str(path), 'unit': 'quillmd-plaintext-reap-test', 'max_seconds': 60})

    def test_reap_shreds_every_file_then_removes_only_the_named_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            restore = base / 'restore-1'
            self.tree(restore, {'verification.json': b'{}', 'files/audio/a.wav': b'a' * 5000, 'files/exports/e.docx': b'e'})
            (restore / 'files/exports/link').symlink_to(base / 'outside')
            outside = self.tree(base / 'outside', {'keep': b'keep'})
            self.assertEqual(self.reap_one(restore / 'files'), {'path': str(restore / 'files'), 'files_before': 2, 'shred_exit': 0, 'files_left': 0, 'removed': True})
            self.assertEqual(self.reap_one(base / 'never-existed'),
                             {'path': str(base / 'never-existed'), 'files_before': 0, 'shred_exit': None, 'files_left': 0, 'removed': False, 'reason': 'absent'})
            self.assertFalse((restore / 'files').exists())
            self.assertEqual(sorted(p.name for p in restore.iterdir()), ['verification.json'])
            self.assertEqual((outside / 'keep').read_bytes(), b'keep')

    def test_a_directory_with_a_surviving_file_is_recorded_and_kept(self):
        if os.geteuid() == 0:
            self.skipTest('root can unlink from a read-only directory')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            target = self.tree(base / 'files', {'locked/a': b'a', 'open/b': b'b'})
            os.chmod(target / 'locked', 0o500)
            try:
                record = self.reap_one(target)
                # The record says exactly what happened, and no directory is removed while a file survives.
                self.assertEqual((record['files_before'], record['files_left'], record['removed']), (2, 1, False))
                self.assertNotEqual(record['shred_exit'], 0)
                self.assertTrue((target / 'locked/a').exists()); self.assertTrue((target / 'open').is_dir())
            finally:
                os.chmod(target / 'locked', 0o700)

    def test_reap_refuses_a_symlinked_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            real = self.tree(base / 'real', {'a': b'a'})
            (base / 'link').symlink_to(real)
            result = self.run_program('ROOT_REAP', {'path': str(base / 'link'), 'unit': 'quillmd-plaintext-reap-test', 'max_seconds': 60})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('refusing unresolved path', result.stderr)
            self.assertEqual((real / 'a').read_bytes(), b'a')


if __name__ == '__main__':
    unittest.main()
