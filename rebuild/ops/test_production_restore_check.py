"""The restore-drill check refuses the live system and fails on any trigger, invariant or file gap."""
import ast
import re
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import backup_restore as backup
    from . import deployment_profile
    from . import production_restore_check as restore_check
except ImportError:
    import backup_restore as backup
    import deployment_profile
    import production_restore_check as restore_check

LIVE = 'quillmd-production.c1a2b3c4d5e6.us-east-1.rds.amazonaws.com'
DRILL = 'quillmd-production-drill-20261101t0300.c1a2b3c4d5e6.us-east-1.rds.amazonaws.com'


def activated():
    raw = json.loads(deployment_profile.PROFILE_PATH.read_text())
    raw['database']['host'] = LIVE
    raw['database']['tls']['ca_bundle_sha256'] = 'ab' * 32
    return deployment_profile.validate(raw)


def migration_bodies():
    bodies = {}
    for path in sorted((Path(__file__).resolve().parents[1] / 'core/migrations').glob('*.py')):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                for name, body in re.findall(r'CREATE (?:OR REPLACE )?FUNCTION (quillmd_\w+)\(\) RETURNS trigger\s+LANGUAGE plpgsql AS \$\$(.*?)\$\$', node.value, re.S):
                    bodies[name] = body
    return bodies


class FakeDatabase:
    """Answers the check's queries from fixed rows; any other statement is a test failure."""

    def __init__(self, files, triggers=39, disabled=0, violations=None):
        self.files = files
        bodies = migration_bodies()
        self.triggers = []
        for i, (table, name, function, kind) in enumerate(restore_check.integrity_contract.GUARDS[:triggers]):
            event = {7:'INSERT', 23: 'INSERT OR UPDATE', 27: 'DELETE OR UPDATE', 19: 'UPDATE', 34: 'TRUNCATE'}[kind]
            each = 'ROW' if kind & 1 else 'STATEMENT'
            definition = f'CREATE TRIGGER {name} BEFORE {event} ON public.{table} FOR EACH {each} EXECUTE FUNCTION {function}()'
            self.triggers.append((table,name,function,kind,'D' if i < disabled else 'O',definition,
                                 'public',bodies[function],function,0,'plpgsql',True,False,None,False,'v','u'))
        self.violations = violations or {}

    def __call__(self, text):
        if text == restore_check.TRIGGERS:
            return self.triggers
        if text == restore_check.integrity_contract.CONTEXT:
            return [('public','origin')]
        for name, statement in backup.INVARIANTS.items():
            if text == statement:
                return [(self.violations.get(name, 0),)]
        for kind, statement in restore_check.FILE_QUERIES:
            if text == statement:
                return [(path, sha) for path, sha, row_kind in self.files if row_kind == kind]
        if text == restore_check.TABLES:
            return [('core_template',), ('core_job',)]
        if text.startswith('SELECT count(*) FROM public.'):
            return [(3,)]
        raise AssertionError('unexpected query')


class DrillTargetTests(unittest.TestCase):
    def test_live_database_live_state_or_unnamed_targets_refuse(self):
        profile = activated()
        with tempfile.TemporaryDirectory() as temp:
            cases = [
                (LIVE, '/mnt/quillmd-drill-20261101t0300', 'live_database'),
                ('evil.example.com', '/mnt/quillmd-drill-20261101t0300', 'drill_database_host'),
                (DRILL.replace('us-east-1', 'us-east-2'), '/mnt/quillmd-drill-20261101t0300', 'drill_database_host'),
                (DRILL, '/var/lib/quillmd-production', 'drill_state_root'),
                (DRILL, '/mnt/quillmd-drill-20261102t0300', 'drill_state_root'),
                (DRILL, temp, 'drill_state_root'),
            ]
            for host, state, label in cases:
                with self.subTest(label=label, host=host, state=state), \
                        self.assertRaisesRegex(restore_check.CheckError, '^' + label + '$'):
                    restore_check.drill_target(profile, host, state)
        with patch.object(Path, 'is_dir', return_value=True), patch.object(Path, 'is_symlink', return_value=False), \
                patch.object(Path, 'resolve', lambda self: self):
            self.assertEqual(restore_check.drill_target(profile, DRILL, '/mnt/quillmd-drill-20261101t0300')[0], DRILL)


class RestoreCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name)
        (self.state / 'files/originals').mkdir(parents=True)
        self.files = []
        for index, kind in enumerate(('original', 'export', 'receipt')):
            data = ('synthetic %d' % index).encode()
            relative = 'originals/%064x.docx' % index
            (self.state / 'files' / relative).write_bytes(data)
            self.files.append((relative, hashlib.sha256(data).hexdigest(), kind))

    def test_a_consistent_restore_passes_with_counts_only(self):
        report = restore_check.check(FakeDatabase(self.files), self.state, 39)
        self.assertTrue(report['passed'])
        self.assertEqual(report['files'], {'referenced': 3, 'missing': 0, 'hash_mismatched': 0, 'passed': True})
        self.assertEqual((report['tables'], report['rows']), (2, 6))
        self.assertNotIn('originals', json.dumps(report))

    def test_missing_or_changed_files_fail(self):
        (self.state / 'files' / self.files[0][0]).unlink()
        (self.state / 'files' / self.files[1][0]).write_bytes(b'changed')
        report = restore_check.check(FakeDatabase(self.files), self.state, 39)
        self.assertFalse(report['passed'])
        self.assertEqual((report['files']['missing'], report['files']['hash_mismatched']), (1, 1))

    def test_every_archived_path_family_is_a_required_file_and_hash(self):
        for field in ('input_path','result_path','original_path','export_path'):
            with self.subTest(field=field):
                relative='originals/archived-'+field+'.bin'
                rows=self.files+[(relative,hashlib.sha256(b'SYNTHETIC ARCHIVED').hexdigest(),'archived_'+field)]
                report=restore_check.check(FakeDatabase(rows),self.state,39)
                self.assertFalse(report['passed']);self.assertEqual(report['files']['missing'],1)
                path=self.state/'files'/relative;path.write_bytes(b'SYNTHETIC WRONG')
                report=restore_check.check(FakeDatabase(rows),self.state,39)
                self.assertFalse(report['passed']);self.assertEqual(report['files']['hash_mismatched'],1)
                path.write_bytes(b'SYNTHETIC ARCHIVED')
                self.assertTrue(restore_check.check(FakeDatabase(rows),self.state,39)['passed'])

    def test_a_symlinked_file_counts_as_missing(self):
        target = self.state / 'outside.docx'
        target.write_bytes(b'synthetic 0')
        path = self.state / 'files' / self.files[0][0]
        path.unlink()
        path.symlink_to(target)
        self.assertEqual(restore_check.check(FakeDatabase(self.files), self.state, 39)['files']['missing'], 1)

    def test_trigger_count_disabled_trigger_or_invariant_violation_fails(self):
        for database, failed in ((FakeDatabase(self.files, triggers=8), 'triggers'),
                                 (FakeDatabase(self.files, disabled=1), 'triggers'),
                                 (FakeDatabase(self.files, violations={'wallet_bounds': 1}), 'invariants')):
            with self.subTest(failed=failed):
                report = restore_check.check(database, self.state, 39)
                self.assertFalse(report['passed'])
                self.assertFalse(report[failed]['passed'])

    def test_every_definition_property_is_bound_even_when_count_stays_equal(self):
        mutations = {0:'core_wrong',1:'invented_trigger',2:'quillmd_wrong',3:19,4:'R',
                     5:'CREATE TRIGGER wrong',6:'other_schema',7:'BEGIN RETURN NEW; END;',
                     9:1,10:'sql',11:False,12:True,13:['search_path=other'],
                     14:True,15:'i',16:'s'}
        for column, value in mutations.items():
            with self.subTest(column=column):
                database = FakeDatabase(self.files)
                row = list(database.triggers[0]); row[column] = value
                database.triggers[0] = tuple(row)
                report = restore_check.check(database, self.state, 39)
                self.assertFalse(report['passed'])
                self.assertEqual(report['triggers']['found'],39)

    def test_missing_extra_duplicate_and_legacy_count_cannot_certify_the_release(self):
        contract = restore_check.integrity_contract
        database = FakeDatabase(self.files)
        for rows, count in ((database.triggers,9), (database.triggers,True),
                            (database.triggers[1:],16),
                            (database.triggers+[database.triggers[0]],18),
                            ([('invented','O')]*39,39)):
            self.assertFalse(contract.assess(rows,[('public','origin')],count)['passed'])
        for context in ([('public','replica')],[('other','origin')],[]):
            self.assertFalse(contract.assess(database.triggers,context,39)['passed'])

    def test_function_contract_matches_reviewed_migration_literals(self):
        bodies = migration_bodies()
        actual = {name:hashlib.sha256(body.encode()).hexdigest() for name,body in bodies.items()}
        self.assertEqual(actual,restore_check.integrity_contract.FUNCTION_SHA256)

    def test_unsafe_or_conflicting_references_refuse(self):
        with self.assertRaises(RuntimeError):
            restore_check.check(FakeDatabase([('../escape', '', 'original')]), self.state, 39)
        conflicting = [(self.files[0][0], 'a' * 64, 'original'), (self.files[0][0], 'b' * 64, 'export')]
        with self.assertRaisesRegex(restore_check.CheckError, '^conflicting_file_hashes$'):
            restore_check.check(FakeDatabase(conflicting), self.state, 39)

    def test_main_refuses_the_unactivated_profile_without_connecting(self):
        errors = io.StringIO()
        with patch.object(restore_check, 'connect', side_effect=AssertionError('connected')), \
                patch('sys.stderr', errors), patch('sys.stdout', io.StringIO()):
            self.assertEqual(restore_check.main(['--database-host', DRILL, '--state-root', '/mnt/quillmd-drill-20261101t0300',
                                                 '--credentials', '/nonexistent', '--expected-triggers', '39']), 1)
        self.assertEqual(json.loads(errors.getvalue()), {'passed': False, 'refused': 'profile_not_activated'})


if __name__ == '__main__':
    unittest.main()
