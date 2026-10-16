"""Offline admission/preservation checks; no database, services, or providers."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ops import activate_rowan_followup as op


class FollowupInstallTests(unittest.TestCase):
    def plan(self, root):
        return dict(format=op.FORMAT, base=op.BASE, candidate='b' * 40,
            source_sha256={'rebuild/core/migrations/' + op.MIGRATION + '.py': 'c' * 64},
            source_worktree=str(op.SOURCE), evidence_directory=str(root / 'attempt'),
            environment_before_sha256='d' * 64, environment={op.ENV_KEY: op.ORIGIN},
            guard_before_md5='e' * 32, guard_after_md5='f' * 32, static=[])

    def test_default_is_inert(self):
        with patch('sys.argv', ['operator']), patch.object(op, 'execute') as execute, \
                patch.object(op.prior, 'private_json') as private, contextlib.redirect_stdout(io.StringIO()) as out:
            op.main()
        self.assertEqual(json.loads(out.getvalue()), dict(inert=True, database_queries=0, provider_calls=0, service_actions=0))
        execute.assert_not_called(); private.assert_not_called()

    def test_binding_restores_consumed_primitive_scope_even_on_failure(self):
        before = (op.prior.BASE, op.prior.SOURCE, op.prior.STATIC)
        with self.assertRaisesRegex(RuntimeError, 'test'):
            with op.bound_primitives(['encounter-live.js']):
                self.assertEqual(op.prior.BASE, op.BASE)
                self.assertEqual(op.prior.SOURCE, op.SOURCE)
                self.assertEqual(op.prior.STATIC, frozenset({'encounter-live.js'}))
                raise RuntimeError('test')
        self.assertEqual((op.prior.BASE, op.prior.SOURCE, op.prior.STATIC), before)

    def test_plan_admits_only_exact_origin_and_migration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700)
            plan = self.plan(root); op.validate_plan(plan)
            changes = [
                (lambda p: p['environment'].update(QUILLMD_CORTI_CODING_MODE='mock'), 'one_exact_recovery_origin'),
                (lambda p: p['environment'].update({op.ENV_KEY: 'other-job'}), 'one_exact_recovery_origin'),
                (lambda p: p['source_sha256'].update({'rebuild/core/migrations/0031_extra.py': 'a' * 64}), 'one_exact_migration'),
                (lambda p: p['source_sha256'].update({'rebuild/static/other.js': 'a' * 64}), 'exact_changed_static'),
                (lambda p: p.update(guard_after_md5=p['guard_before_md5']), 'exact_guard_body_delta'),
                (lambda p: p.update(static=['unexpected.js']), 'bounded_public_static'),
            ]
            for change, label in changes:
                bad = copy.deepcopy(plan); change(bad)
                with self.subTest(label=label), self.assertRaisesRegex(op.Refusal, label): op.validate_plan(bad)
            (root / 'attempt').mkdir()
            with self.assertRaisesRegex(op.Refusal, 'exclusive_private_output'): op.validate_plan(plan)

    def original_environment(self):
        return ('# retained\nQUILLMD_RELEASE_SHA="' + op.BASE + '"\nQUILLMD_CODING_PROVIDER=existing\n'
                'QUILLMD_CORTI_CODING_MODE=live\nQUILLMD_CORTI_CREDENTIALS_FILE="' + str(op.prior.CREDENTIAL_TARGET) + '"\n'
                'SECRET="synthetic-${NO_EXPANSION}"\nQUILLMD_CORTI_NEW_ENCOUNTERS_SINCE="2026-10-16T23:32:18+00:00"\n').encode()

    def test_environment_preserves_existing_provider_credentials_cutoff_and_literal_data(self):
        original = self.original_environment(); result = op.render_environment(original, 'a' * 40)
        expected = original.replace(op.BASE.encode(), b'a' * 40) + (op.ENV_KEY + '="' + op.ORIGIN + '"\n').encode()
        self.assertEqual(result, expected)

    def test_second_recovery_admission_cannot_overwrite_existing_configuration(self):
        original = self.original_environment() + (op.ENV_KEY + '=' + op.ORIGIN + '\n').encode()
        with self.assertRaisesRegex(op.Refusal, 'recovery_admission_not_reused'):
            op.render_environment(original, 'a' * 40)

    def test_wrong_release_global_provider_or_duplicate_release_refuses(self):
        original = self.original_environment()
        for data, label in ((original.replace(op.BASE.encode(), b'a' * 40), 'installed_activation_required'),
                (original.replace(b'QUILLMD_CODING_PROVIDER=existing', b'QUILLMD_CODING_PROVIDER=corti'), 'installed_activation_required'),
                (original + ('QUILLMD_RELEASE_SHA=' + op.BASE + '\n').encode(), 'duplicate_environment_key')):
            with self.subTest(label=label), self.assertRaisesRegex(op.Refusal, label): op.render_environment(data, 'b' * 40)

    def snapshots(self):
        before = dict(tables={'core_encounter': [7, 'note-digest'], 'core_codingoutputdecision': [0, 'empty'],
            'django_migrations': [29, 'old-ledger-digest']}, migrations=[['core', '0029_bounded_output_decision']],
            migration_ledger=[['29', 'core', '0029_bounded_output_decision', 'retained-time']],
            schema=[['core_job', 'quillmd_owner', 'unchanged']], triggers=[['core_aistagereceipt', 'guard', 'definition', 'O']],
            constraints=[['core_job', 'existing', 'unchanged']], indexes=[['core_job', 'unchanged']],
            functions=[[op.FUNCTION, '', 'e' * 32, 'quillmd_owner', 'acl'], ['other_guard', '', 'same', 'quillmd_owner', 'acl']],
            sequences={'django_migrations_id_seq': [29, True], 'other': [9, True]},
            pending={'core_job': 0, 'core_codingrun': 0}, latest_enrolled_encounter='2026-10-16 23:40:00+00:00')
        after = copy.deepcopy(before)
        after['tables']['django_migrations'] = [30, 'new-ledger-digest']
        after['migrations'].append(['core', op.MIGRATION])
        after['migration_ledger'].append(['30', 'core', op.MIGRATION, 'new-time'])
        after['functions'][0][2] = 'f' * 32
        after['sequences']['django_migrations_id_seq'] = [30, True]
        return before, after, {'guard_before_md5': 'e' * 32, 'guard_after_md5': 'f' * 32}

    def test_exact_one_guard_and_migration_row_are_admitted(self):
        op.verify_migration(*self.snapshots())

    def test_all_existing_clinical_rows_and_approval_rows_must_remain_identical(self):
        before, after, plan = self.snapshots()
        for table in ('core_encounter', 'core_codingoutputdecision'):
            bad = copy.deepcopy(after); bad['tables'][table][1] = 'changed'
            with self.assertRaisesRegex(op.Refusal, 'all_existing_database_rows_preserved'): op.verify_migration(before, bad, plan)

    def test_old_migration_timestamps_and_ids_cannot_change(self):
        before, after, plan = self.snapshots()
        for index in (0, 3):
            bad = copy.deepcopy(after); bad['migration_ledger'][0][index] = 'changed'
            with self.assertRaisesRegex(op.Refusal, 'one_appended_migration_row'): op.verify_migration(before, bad, plan)

    def test_no_new_table_or_schema_trigger_constraint_index_change(self):
        before, after, plan = self.snapshots()
        bad = copy.deepcopy(after); bad['tables']['new_table'] = [0, 'empty']
        with self.assertRaisesRegex(op.Refusal, 'no_new_or_removed_tables'): op.verify_migration(before, bad, plan)
        for part in ('schema', 'triggers', 'constraints', 'indexes'):
            bad = copy.deepcopy(after); bad[part][0][-1] = 'modified'
            with self.subTest(part=part), self.assertRaisesRegex(op.Refusal, 'unchanged_' + part):
                op.verify_migration(before, bad, plan)

    def test_wrong_guard_body_owner_acl_and_other_function_changes_refuse(self):
        before, after, plan = self.snapshots()
        for index in (2, 3, 4):
            bad = copy.deepcopy(after); bad['functions'][0][index] = 'changed'
            with self.assertRaisesRegex(op.Refusal, 'exact_guard_replacement'): op.verify_migration(before, bad, plan)
        bad = copy.deepcopy(after); bad['functions'][1][2] = 'changed'
        with self.assertRaisesRegex(op.Refusal, 'other_functions_unchanged'): op.verify_migration(before, bad, plan)

    def test_pending_provider_work_or_unrelated_sequence_advance_refuses(self):
        before, after, plan = self.snapshots()
        bad = copy.deepcopy(after); bad['pending']['core_codingrun'] = 1
        with self.assertRaisesRegex(op.Refusal, 'no_provider_work_during_install'): op.verify_migration(before, bad, plan)
        bad = copy.deepcopy(after); bad['sequences']['other'][0] += 1
        with self.assertRaisesRegex(op.Refusal, 'only_exact_migration_sequence_advance'): op.verify_migration(before, bad, plan)

    def test_migration_transport_sends_only_one_forward_target_without_post_migrate(self):
        output = b'rowan_recovery_migration_committed\n'
        with patch.object(op.prior, 'database_options', return_value={'user': 'migrator', 'password': 'synthetic', 'options': '-c role=owner'}), \
                patch.object(op.prior, 'command', return_value=output) as command:
            op.migrate(self.original_environment())
        argv = command.call_args.args[0]; code = argv[-1]
        self.assertIn("assert [(m.app_label,m.name,b)for m,b in e.migration_plan(target)]==[('core','" + op.MIGRATION + "',False)]", code)
        self.assertNotIn('0029_', code)
        self.assertNotIn('post_migrate', code)
        self.assertIn('with transaction.atomic():e.migrate(target)', code)


if __name__ == '__main__': unittest.main()
