"""Focused isolated guards for private activation. No host/service/provider acts."""
import copy
import io
import json
from pathlib import Path
import tarfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

try:
    from . import source_module
except ImportError:
    import source_module

ROOT = Path(__file__).resolve().parents[2]
activation = source_module.load('private_operations_activation_tested', ROOT / 'scripts/activate-private-operations.py')


class PrivateOperationsActivationTests(unittest.TestCase):
    def paths(self):
        return activation.RUNTIME_ALLOWED | {activation.DECL, 'docs/rebuild/private-beta-operations-20260920.md'}

    def test_exact_changes_allow_required_admin_and_backup_preparation(self):
        activation.validate_changed(self.paths())
        for name in ('rebuild/browser-tests.mjs', 'rebuild/ops/install_backup_schedule.py',
                     'rebuild/core/tests/test_reconciliation_and_license_gates.py'):
            self.assertIn(name, self.paths())

    def test_omitted_declaration_or_unrelated_or_extra_schema_change_refuses(self):
        for changed in (self.paths() - {activation.DECL},
                        self.paths() - {activation.MIGRATION_PATH},
                        self.paths() | {'rebuild/quillmd/settings.py'},
                        self.paths() | {'rebuild/core/migrations/0016_unreviewed.py'},
                        self.paths() | {'apps/another-project/server.py'},
                        self.paths() | {'docs/rebuild/../unexpected.md'}):
            with self.subTest(changed=changed), self.assertRaises(RuntimeError):
                activation.validate_changed(changed)

    def test_release_only_preserves_credential_bytes_quotes_and_crlf(self):
        for ending in (b'\n', b'\r\n', b''):
            before = (b'# synthetic fixture\nSTRIPE_SECRET_KEY="fixture-not-a-key"\n'
                      b'PATIENT_DATA_ENABLED=false\nexport QUILLMD_RELEASE_SHA = "'
                      + activation.RUNNING_RELEASE.encode() + b'"' + ending)
            changed = activation.updated_environment(before, 'a' * 40)
            prefix = before[:before.index(b'export QUILLMD_RELEASE_SHA')]
            self.assertEqual(changed, prefix + b'QUILLMD_RELEASE_SHA="' + b'a' * 40 + b'"' + ending)

    def test_missing_duplicate_wrong_release_or_short_target_refuses(self):
        before = b'QUILLMD_RELEASE_SHA=' + activation.RUNNING_RELEASE.encode() + b'\n'
        for wrong in (b'OTHER=fixture\n', before + before, before.replace(activation.RUNNING_RELEASE.encode(), b'b' * 40)):
            with self.subTest(wrong=wrong), self.assertRaises(RuntimeError):
                activation.updated_environment(wrong, 'a' * 40)
        for target in ('short', activation.RUNNING_RELEASE):
            with self.assertRaises(RuntimeError):
                activation.updated_environment(before, target)

    def plan(self, pending):
        return ('[X]  contenttypes.0001_initial\n[X]\tcore.' + activation.PREVIOUS_MIGRATION
                + '\n[' + (' ' if pending else 'X') + ']  core.' + activation.MIGRATION + '\n')

    def test_only_declared_pending_migration_then_all_applied(self):
        activation.verify_migration_plan(self.plan(True), applied=False)
        activation.verify_migration_plan(self.plan(False), applied=True)
        for plan, applied in ((self.plan(True), True), (self.plan(False), False), ('', False),
                              (self.plan(True) + '[ ] core.0016_unreviewed\n', False),
                              (self.plan(True) + 'provider warning\n', False),
                              (self.plan(True) + '[X] core.' + activation.PREVIOUS_MIGRATION, False)):
            with self.subTest(plan=plan), self.assertRaises(RuntimeError):
                activation.verify_migration_plan(plan, applied=applied)

    def test_pinned_migration_cannot_hide_an_existing_row_update(self):
        source = (ROOT / activation.MIGRATION_PATH).read_bytes()
        activation.validate_migration(source)
        with self.assertRaises(RuntimeError):
            activation.validate_migration(source + b'\n# an unreviewed change\n')

    def test_every_service_must_be_inactive_with_zero_pid(self):
        with patch.object(activation, 'output', side_effect=['inactive', '0'] * 3) as query:
            activation.stopped()
        self.assertEqual(query.call_count, 6)
        for values in (['active'], ['inactive', '12'], ['inactive', '0', 'failed']):
            with self.subTest(values=values), patch.object(activation, 'output', side_effect=values):
                with self.assertRaises(RuntimeError):
                    activation.stopped()

    def test_root_only_configs_are_hashed_through_bounded_readonly_bridge(self):
        report = {path: {'resolved': path, 'sha256': 'a' * 64}
                  for path in ('/etc/ssh/sshd_config', '/etc/nginx/nginx.conf', '/etc/ssh/sshd_config.d/50-cloud-init.conf')}
        with patch.object(activation.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout=json.dumps(report))) as execute:
            self.assertEqual(activation.shared_configs('sha256:' + 'b' * 64), report)
        command = execute.call_args.args[0]
        for flag in ('--network=none', '--read-only', '--cap-drop=ALL', '--security-opt=no-new-privileges:true'):
            self.assertIn(flag, command)
        mounts = [command[index + 1] for index, value in enumerate(command) if value == '--mount']
        self.assertEqual(mounts, ['type=bind,src=/etc/ssh,dst=/etc/ssh,readonly', 'type=bind,src=/etc/nginx,dst=/etc/nginx,readonly'])
        self.assertNotIn('--privileged', command)
        for failed in (SimpleNamespace(returncode=1, stdout=''), SimpleNamespace(returncode=0, stdout='{}')):
            with patch.object(activation.subprocess, 'run', return_value=failed), self.assertRaises(RuntimeError):
                activation.shared_configs('sha256:' + 'b' * 64)

    def catalog(self):
        before = {'functions': [{'name': 'existing()', 'body': 'prior'}], 'triggers': [{'name': 'prior'}]}
        after = copy.deepcopy(before)
        after['functions'].append({'name': activation.FUNCTION + '()', 'owner': 'quillmd_owner',
            'language': 'plpgsql', 'security_definer': False, 'config': None, 'acl': None, 'body': '\nBEGIN synthetic; END;\n'})
        after['triggers'].append({'name': activation.TRIGGER, 'table': 'core_costreconciliation',
            'function': activation.FUNCTION, 'type': 27, 'enabled': 'O', 'args': '', 'when': None})
        return before, after

    def test_only_exact_additive_guard_is_accepted(self):
        before, after = self.catalog()
        activation.check_catalog(before, after, 'BEGIN synthetic; END;')
        for kind, key, value in (('functions', 'body', 'BEGIN altered; END;'),
                                  ('functions', 'security_definer', True), ('functions', 'owner', 'postgres'),
                                  ('triggers', 'enabled', 'D'), ('triggers', 'type', 25),
                                  ('triggers', 'table', 'another_table'), ('triggers', 'when', 'false')):
            wrong = copy.deepcopy(after); wrong[kind][-1][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                activation.check_catalog(before, wrong, 'BEGIN synthetic; END;')
        wrong = copy.deepcopy(after); wrong['functions'][0]['body'] = 'modified old guard'
        with self.assertRaises(RuntimeError):
            activation.check_catalog(before, wrong, 'BEGIN synthetic; END;')

    def test_existing_rows_hashed_exactly_with_only_new_migration_excluded(self):
        old = SimpleNamespace(tables=lambda: ['core_encounter', 'django_migrations'], PSQL=['synthetic-psql'])
        payload = b'{"notes":"retain all text","amount":"1.500000"}\n'
        with patch.object(activation.subprocess, 'check_output', return_value=payload) as execute:
            actual = activation.rows(old, exclude_new=True)
        self.assertEqual(actual['core_encounter'], {'rows': 1, 'sha256': activation.sha(payload)})
        self.assertNotIn('WHERE', execute.call_args_list[0].args[0][-1])
        self.assertIn("WHERE NOT (app='core' AND name='0015_reconciliation_evidence_guard')", execute.call_args_list[1].args[0][-1])

    def test_existing_state_deltas_refuse_even_when_catalog_is_expected(self):
        old, new = self.catalog()
        before = {'rows': {'clinical': 'original'}, 'catalog': old, 'storage': {'original': 'hash'}, 'unit_files': {'unit': 'hash'}}
        after = {**copy.deepcopy(before), 'catalog': new}
        activation.validate_after(before, after, 'BEGIN synthetic; END;')
        for key in ('rows', 'storage', 'unit_files'):
            wrong = copy.deepcopy(after); wrong[key] = {'changed': 'hash'}
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                activation.validate_after(before, wrong, 'BEGIN synthetic; END;')

    def archive(self, extra=None):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w') as bundle:
            data = b'# prior synthetic source\n'
            member = tarfile.TarInfo('rebuild/manage.py'); member.size = len(data); member.mode = 0o644
            bundle.addfile(member, io.BytesIO(data))
            if extra:
                name, kind = extra
                member = tarfile.TarInfo(name); member.type = kind
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    member.linkname = '/etc/ssh/sshd_config'
                bundle.addfile(member)
        return stream.getvalue()

    def test_retained_archive_records_each_exact_file_without_extracting(self):
        archive = self.archive()
        manifest = activation.retained_source_manifest(archive)
        self.assertEqual(manifest['archive_sha256'], activation.sha(archive))
        self.assertEqual(manifest['files']['rebuild/manage.py'], {
            'bytes': 25, 'sha256': activation.sha(b'# prior synthetic source\n'), 'mode': 0o644})
        self.assertIn('Retain any applied 0015 guard', ' '.join(manifest['recovery_policy']))
        self.assertIn('Never reset main', ' '.join(manifest['recovery_policy']))

    def test_archive_traversal_links_duplicate_and_secret_paths_refuse(self):
        for extra in (('rebuild/../../etc/ssh/sshd_config', tarfile.REGTYPE),
                      ('/rebuild/file', tarfile.REGTYPE), ('other-project/file', tarfile.REGTYPE),
                      ('rebuild/link', tarfile.SYMTYPE), ('rebuild/hard', tarfile.LNKTYPE),
                      ('rebuild/manage.py', tarfile.REGTYPE), ('rebuild/.env', tarfile.REGTYPE),
                      ('rebuild/.runtime/private', tarfile.REGTYPE)):
            with self.subTest(extra=extra), self.assertRaises(RuntimeError):
                activation.retained_source_manifest(self.archive(extra))


if __name__ == '__main__':
    unittest.main()
