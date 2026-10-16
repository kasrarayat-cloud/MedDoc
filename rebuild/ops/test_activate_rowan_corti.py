"""Focused offline proofs for the new exact native publication boundary."""
import contextlib
import copy
import gzip
import io
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from ops import activate_rowan_corti as op


class NativeInstallTests(unittest.TestCase):
    def test_credential_preflight_is_readonly_and_never_returns_secret_values(self):
        result = SimpleNamespace(stdout=b'protected_credential_preflight_complete\n')
        with patch.object(op.managed_helper, 'run_helper', return_value=result) as helper:
            receipt = op.preflight_credential(Path('/private-evidence'))
        argv = helper.call_args.args[0]
        self.assertIn('--read-only', argv)
        self.assertIn('--network=none', argv)
        self.assertEqual([x for x in argv if x.startswith('type=bind,')], ['type=bind,src=/,dst=/host,readonly'])
        self.assertFalse(receipt['secret_values_recorded'])
        self.assertEqual(receipt['provider_calls'], 0)
        code = helper.call_args.kwargs['input'].decode()
        self.assertNotIn('mkdir', code)
        self.assertIn('interpolate=False', code)
        self.assertNotIn('print(values', code)

    def test_shared_credential_checks_accept_exported_data_and_refuse_bad_source_or_existing_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700)
            source = root / 'credentials.env'; target = root / 'target'
            valid = ('export CORTI_CLIENT_ID="synthetic-client"\n'
                     'export CORTI_CLIENT_SECRET="literal-${DO_NOT_EXPAND}"\n'
                     'export CORTI_ENVIRONMENT=us\nexport CORTI_TENANT_NAME=base\n')
            code = op.credential_source_checks().replace('/host/etc/quillmd-corti-test/credentials.env', str(source))
            code = code.replace('/host/var/lib/quillmd/provider-secrets', str(target))
            code = code.replace('info.st_uid==0', 'info.st_uid==os.getuid()').replace('parent.st_uid==0', 'parent.st_uid==os.getuid()')
            source.write_text(valid); source.chmod(0o600)
            scope = {}; exec(code, scope)
            self.assertEqual(scope['values']['CORTI_CLIENT_SECRET'], 'literal-${DO_NOT_EXPAND}')
            for invalid in (valid.replace('CORTI_ENVIRONMENT=us', 'CORTI_ENVIRONMENT=eu'),
                            valid.replace('CORTI_CLIENT_SECRET=', 'UNRELATED_KEY=')):
                source.write_text(invalid)
                with self.assertRaises(AssertionError): exec(code, {})
            source.write_text(valid); source.chmod(0o644)
            with self.assertRaises(AssertionError): exec(code, {})
            source.chmod(0o600); target.mkdir()
            with self.assertRaises(AssertionError): exec(code, {})

    def test_default_is_inert_and_cannot_load_private_operational_inputs(self):
        with patch('sys.argv', ['activate_rowan_corti']), patch.object(op, 'execute') as execute, \
                patch.object(op, 'private_json') as private, contextlib.redirect_stdout(io.StringIO()) as out:
            op.main()
        self.assertEqual(json.loads(out.getvalue()), {'inert': True, 'database_queries': 0, 'provider_calls': 0, 'service_actions': 0})
        execute.assert_not_called(); private.assert_not_called()

    def environment(self):
        return {'QUILLMD_CORTI_CODING_MODE': 'live', 'QUILLMD_CORTI_CREDENTIALS_FILE': str(op.CREDENTIAL_TARGET),
            'QUILLMD_CORTI_NEW_ENCOUNTERS_SINCE': '2026-10-17T00:30:00+00:00',
            'QUILLMD_CORTI_NEW_ENCOUNTER_ACTORS': '5f4d1a3d-eeb6-4207-b1df-4597dc696e82',
            'QUILLMD_CORTI_OUTPUT_REFERENCE_FILE': str(op.APP / 'ops/fixtures/corti_rowan_output_reference.json'),
            'QUILLMD_CORTI_OUTPUT_REFERENCE_SHA256': 'a' * 64}

    def test_closed_plan_rejects_global_switch_wrong_actor_and_second_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory); private.chmod(0o700)
            paths = {'rebuild/core/migrations/' + op.MIGRATION + '.py': 'a' * 64,
                     'rebuild/ops/fixtures/corti_rowan_output_reference.json': 'a' * 64,
                     **{'rebuild/static/' + n: 'a' * 64 for n in op.STATIC}}
            plan = dict(format=op.FORMAT, base=op.BASE, candidate='b' * 40,
                source_sha256=paths, environment=self.environment(), evidence_directory=str(private / 'attempt'),
                source_worktree=str(op.SOURCE), environment_before_sha256='c' * 64)
            op.validate_plan(plan)
            for change, label in ((lambda p: p['environment'].update(QUILLMD_CODING_PROVIDER='corti'), 'closed_environment_delta'),
                    (lambda p: p['environment'].update(QUILLMD_CORTI_NEW_ENCOUNTER_ACTORS='other-user'), 'one_existing_synthetic_actor'),
                    (lambda p: p['source_sha256'].update({'rebuild/core/migrations/0030_other.py': 'a' * 64}), 'one_additive_migration')):
                bad = copy.deepcopy(plan); change(bad)
                with self.assertRaisesRegex(op.Refusal, label): op.validate_plan(bad)
            (private / 'attempt').mkdir()
            with self.assertRaisesRegex(op.Refusal, 'exclusive_private_output'): op.validate_plan(plan)

    def test_activation_preserves_existing_provider_and_unrelated_bytes(self):
        original = ('# retained comment\nQUILLMD_RELEASE_SHA="' + op.BASE + '"\nQUILLMD_CODING_PROVIDER=existing\n'
                    'EXISTING_SECRET="synthetic-canary"\n').encode()
        result = op.render_environment(original, self.environment(), 'b' * 40)
        self.assertIn(b'QUILLMD_CODING_PROVIDER=existing\nEXISTING_SECRET="synthetic-canary"\n', result)
        self.assertEqual(result.count(b'QUILLMD_RELEASE_SHA='), 1)
        self.assertNotIn(op.BASE.encode(), result)
        self.assertEqual(result.count(b'QUILLMD_CORTI_CODING_MODE='), 1)

    def test_existing_corti_activation_cannot_be_overwritten_or_reused(self):
        raw = ('QUILLMD_RELEASE_SHA=' + op.BASE + '\nQUILLMD_CORTI_CODING_MODE=live\n').encode()
        with self.assertRaisesRegex(op.Refusal, 'new_activation_not_reused'):
            op.render_environment(raw, self.environment(), 'b' * 40)

    def test_global_provider_switch_is_not_admitted(self):
        raw = ('QUILLMD_RELEASE_SHA=' + op.BASE + '\nQUILLMD_CODING_PROVIDER=corti\n').encode()
        with self.assertRaisesRegex(op.Refusal, 'original_provider_and_release'):
            op.render_environment(raw, self.environment(), 'b' * 40)

    def test_duplicate_release_environment_assignment_refuses(self):
        raw = ('QUILLMD_RELEASE_SHA=' + op.BASE + '\n') .encode() * 2
        with self.assertRaisesRegex(op.Refusal, 'duplicate_environment_key'):
            op.render_environment(raw, self.environment(), 'b' * 40)

    def snapshot(self):
        before = {'tables': {'core_encounter': [1, 'original-clinical-hash'], 'core_codingdecision': [2, 'approval-hash'],
            'django_migrations': [28, 'migration-hash']}, 'migrations': [['core', '0028_outpatient_coding']],
            'schema': [['core_encounter', 'quillmd_owner', '', 'id', 'uuid', True]],
            'triggers': [['core_codingdecision', 'coding_decision_append_only', 'original-guard', 'O']],
            'constraints': [['core_encounter', 'original_unique', 'UNIQUE (id)']],
            'indexes': [['core_encounter', 'original_index', 'index-definition']],
            'functions': [['quillmd_append_only', '', 'function-hash', 'quillmd_owner', 'acl']],
            'sequences': {'django_migrations_id_seq': [28, True], 'other_seq': [9, True]},
            'pending': {'core_job': 0}}
        after = copy.deepcopy(before)
        after['tables'][op.NEW_TABLE] = [0, 'empty']; after['tables']['django_migrations'] = [29, 'new-migration-hash']
        after['migrations'].append(['core', op.MIGRATION])
        after['sequences']['django_migrations_id_seq'] = [29, True]
        after['schema'].append([op.NEW_TABLE, 'quillmd_owner', '{quillmd_runtime=arwd/quillmd_owner}', 'id', 'uuid', True])
        after['triggers'].append([op.NEW_TABLE, 'coding_output_decision_append_only',
            'CREATE TRIGGER coding_output_decision_append_only BEFORE DELETE OR UPDATE ON public.core_codingoutputdecision FOR EACH ROW EXECUTE FUNCTION quillmd_append_only()', 'O'])
        return before, after

    def test_one_empty_append_only_table_is_admitted(self):
        before, after = self.snapshot(); op.verify_migration(before, after)

    def test_changed_old_clinical_row_or_approval_refuses(self):
        before, after = self.snapshot()
        for table in ('core_encounter', 'core_codingdecision'):
            changed = copy.deepcopy(after); changed['tables'][table][1] = 'mutated'
            with self.assertRaisesRegex(op.Refusal, 'all_existing_database_rows_preserved'):
                op.verify_migration(before, changed)

    def test_created_decision_or_extra_table_refuses(self):
        before, after = self.snapshot()
        bad = copy.deepcopy(after); bad['tables'][op.NEW_TABLE][0] = 1
        with self.assertRaisesRegex(op.Refusal, 'empty_new_decisions'): op.verify_migration(before, bad)
        bad = copy.deepcopy(after); bad['tables']['unexpected'] = [0, 'empty']
        with self.assertRaisesRegex(op.Refusal, 'one_new_table'): op.verify_migration(before, bad)

    def test_changed_or_disabled_guard_refuses(self):
        before, after = self.snapshot()
        bad = copy.deepcopy(after); bad['triggers'][0][2] = 'weakened'
        with self.assertRaisesRegex(op.Refusal, 'old_guards_unchanged'): op.verify_migration(before, bad)
        bad = copy.deepcopy(after); bad['triggers'][-1][-1] = 'D'
        with self.assertRaisesRegex(op.Refusal, 'new_append_only_guard'): op.verify_migration(before, bad)

    def test_wrong_owner_or_missing_runtime_grant_refuses(self):
        before, after = self.snapshot()
        for index, value in ((1, 'quillmd_runtime'), (2, '')):
            bad = copy.deepcopy(after); bad['schema'][-1][index] = value
            with self.assertRaisesRegex(op.Refusal, 'new_owner_runtime_privileges'): op.verify_migration(before, bad)

    def test_additional_migration_or_pending_work_refuses(self):
        before, after = self.snapshot()
        bad = copy.deepcopy(after); bad['migrations'].append(['core', '0030_not_reviewed'])
        with self.assertRaisesRegex(op.Refusal, 'exact_migration_row'): op.verify_migration(before, bad)
        bad = copy.deepcopy(after); bad['pending']['core_job'] = 1
        with self.assertRaisesRegex(op.Refusal, 'no_provider_work_during_install'): op.verify_migration(before, bad)

    def test_existing_constraints_functions_and_sequences_cannot_drift(self):
        before, after = self.snapshot()
        for part, label in (('constraints', 'old_constraints_unchanged'), ('indexes', 'old_indexes_unchanged'),
                            ('functions', 'old_guard_functions_unchanged')):
            bad = copy.deepcopy(after); bad[part][0][-1] = 'changed'
            with self.assertRaisesRegex(op.Refusal, label): op.verify_migration(before, bad)
        bad = copy.deepcopy(after); bad['sequences']['other_seq'][0] += 1
        with self.assertRaisesRegex(op.Refusal, 'only_exact_migration_sequence_advance'):
            op.verify_migration(before, bad)

    def test_static_publication_preserves_old_hashes_and_updates_compressed_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); app = root / 'installed'; source = root / 'candidate'; evidence = root / 'evidence'
            static = app / 'staticfiles'; static.mkdir(parents=True, mode=0o755); evidence.mkdir(mode=0o700)
            (source / 'rebuild/static').mkdir(parents=True)
            manifest = {'version': '1.1', 'hash': 'old', 'paths': {'other.js': 'other.oldhash.js'}}
            for name in op.STATIC:
                (source / 'rebuild/static' / name).write_bytes(('new source ' + name).encode())
                (static / name).write_bytes(b'old alias')
                (static / (name + '.gz')).write_bytes(gzip.compress(b'old alias'))
                (static / ('historical.' + name)).write_bytes(b'historical bytes')
            (static / 'other.oldhash.js').write_bytes(b'unchanged other')
            (static / 'staticfiles.json').write_text(json.dumps(manifest))
            for p in static.iterdir(): p.chmod(0o644)
            plan = {'source_sha256': {'rebuild/static/' + n: op.sha((source / 'rebuild/static' / n).read_bytes()) for n in op.STATIC}}
            primitives = op.legacy.static_primitives(); primitives.static_delta = op.static_delta
            with patch.object(op, 'APP', app), patch.object(op, 'SOURCE', source):
                stage, before, staged = op.stage_static(plan, evidence, primitives)
                after = primitives.install_static(static, stage, before, staged)
            for name in op.STATIC:
                self.assertEqual((static / ('historical.' + name)).read_bytes(), b'historical bytes')
                self.assertEqual(gzip.decompress((static / (name + '.gz')).read_bytes()), (static / name).read_bytes())
            self.assertEqual(after['other.oldhash.js'], before['other.oldhash.js'])
            self.assertEqual(json.loads((static / 'staticfiles.json').read_text())['paths']['other.js'], 'other.oldhash.js')

    def test_static_historical_hash_replacement_refuses(self):
        row = {'kind': 'file', 'mode': 0o644, 'size': 1, 'sha256': 'a'}
        with self.assertRaisesRegex(op.Refusal, 'immutable_static_preserved'):
            op.static_delta({'coding.immutable.js': row}, {'coding.immutable.js': {**row, 'sha256': 'b'}})

    def test_migration_code_has_exact_one_forward_target_and_no_post_migrate(self):
        source = op.migration_source()
        self.assertIn("assert [(m.app_label,m.name,b)for m,b in e.migration_plan(target)]==[('core','0029_bounded_output_decision',False)]", source)
        self.assertIn('with transaction.atomic():e.migrate(target)', source)
        self.assertNotIn('call_command', source)
        self.assertNotIn('post_migrate', source)


if __name__ == '__main__': unittest.main()
