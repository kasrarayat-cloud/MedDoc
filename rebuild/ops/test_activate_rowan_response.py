"""Focused offline operator controls; all operational transports are mocked."""
from contextlib import ExitStack, nullcontext, redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ops import activate_rowan_response as op


class ResponseInstallTests(unittest.TestCase):
    def plan(self, root):
        return dict(format=op.FORMAT, base=op.BASE, candidate='a' * 40,
            source_sha256={'rebuild/core/coding_views.py': 'b' * 64},
            source_worktree=str(op.SOURCE), evidence_directory=str(root / 'attempt'),
            environment_before_sha256='c' * 64, static=[])

    def test_default_is_inert_and_reads_no_operational_inputs(self):
        with patch('sys.argv', ['operator']), patch.object(op, 'execute') as execute, \
                patch.object(op.prior, 'private_json') as private, redirect_stdout(io.StringIO()) as out:
            op.main()
        self.assertEqual(json.loads(out.getvalue()), dict(inert=True, database_queries=0, provider_calls=0, service_actions=0))
        execute.assert_not_called(); private.assert_not_called()

    def test_scope_binding_restores_every_primitive_even_after_failure(self):
        previous = (op.prior.BASE, op.prior.SOURCE, op.prior.STATIC)
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            with op.bound_primitives(['coding.js']):
                self.assertEqual((op.prior.BASE, op.prior.SOURCE, op.prior.STATIC),
                                 (op.BASE, op.SOURCE, frozenset({'coding.js'})))
                raise RuntimeError('synthetic')
        self.assertEqual((op.prior.BASE, op.prior.SOURCE, op.prior.STATIC), previous)

    def test_closed_plan_rejects_schema_settings_other_runtime_and_private_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700)
            plan = self.plan(root); op.validate_plan(plan)
            for name in ('rebuild/core/migrations/0032_extra.py', 'rebuild/quillmd/settings.py',
                         'rebuild/core/jobs.py', 'rebuild/core/billing.py', 'rebuild/.env',
                         '/rebuild/core/coding_views.py', 'rebuild/core/../coding_views.py'):
                bad = deepcopy(plan); bad['source_sha256'][name] = 'b' * 64
                with self.subTest(name=name), self.assertRaisesRegex(op.Refusal, 'only_review_response_source'):
                    op.validate_plan(bad)
            for extra in ('environment', 'guard_after_md5', 'migration'):
                bad = dict(plan, **{extra: 'unreviewed'})
                with self.assertRaisesRegex(op.Refusal, 'closed_response_plan'): op.validate_plan(bad)
            (root / 'attempt').mkdir()
            with self.assertRaisesRegex(op.Refusal, 'exclusive_private_output'): op.validate_plan(plan)

    def test_only_exact_changed_coding_static_is_admitted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700); plan = self.plan(root)
            plan['source_sha256']['rebuild/static/coding.js'] = 'e' * 64
            with self.assertRaisesRegex(op.Refusal, 'exact_changed_static'): op.validate_plan(plan)
            plan['static'] = ['coding.js']; op.validate_plan(plan)
            plan['static'] = ['encounter-live.js']
            with self.assertRaisesRegex(op.Refusal, 'only_coding_static'): op.validate_plan(plan)

    def original_environment(self):
        return ('# unchanged\r\nQUILLMD_RELEASE_SHA="' + op.BASE + '"\r\n'
                'QUILLMD_CODING_PROVIDER=existing\r\nQUILLMD_CORTI_CODING_MODE=live\r\n'
                'QUILLMD_SEMANTIC_REVALIDATION_ORIGIN_JOB_IDS=retained-v1\r\n'
                'QUILLMD_SEMANTIC_REVALIDATION_V2_ORIGIN_JOB_IDS=retained-v2\r\n'
                'SECRET="synthetic-${UNEXPANDED}"').encode()

    def test_environment_changes_only_the_release_line_and_preserves_all_other_bytes(self):
        original = self.original_environment()
        result = op.render_environment(original, 'a' * 40)
        old = ('QUILLMD_RELEASE_SHA="' + op.BASE + '"\r\n').encode()
        self.assertEqual(result, original.replace(old, b'QUILLMD_RELEASE_SHA="' + b'a' * 40 + b'"\n'))

    def test_environment_refuses_wrong_base_duplicate_or_unrecognized_release_line(self):
        original = self.original_environment()
        for raw, label in ((original.replace(op.BASE.encode(), b'b' * 40), 'exact_installed_release'),
                (original + ('\nQUILLMD_RELEASE_SHA=' + op.BASE + '\n').encode(), 'duplicate_release_assignment'),
                (original.replace(b'QUILLMD_RELEASE_SHA=', b'QUILLMD_RELEASE_SHA ='), 'release_assignment_found')):
            with self.subTest(label=label), self.assertRaisesRegex(op.Refusal, label): op.render_environment(raw, 'a' * 40)

    def database(self):
        return dict(tables={'core_encounter': [1, 'finalized'], 'core_codingrun': [2, 'selection-revision-2'],
            'core_codingdecision': [0, 'empty'], 'core_usage': [7, 'current'], 'django_migrations': [31, 'retained']},
            migration_ledger=[['31', 'core', '0031_retained_semantic_revalidation_v2', 'time']],
            migrations=[['core', '0031_retained_semantic_revalidation_v2']], schema=['columns-owner-acl'],
            constraints=['unchanged'], indexes=['unchanged'], triggers=['unchanged'], functions=['unchanged'],
            sequences={'django_migrations_id_seq': [31, True]}, pending={'core_job': 0, 'core_codingrun': 0},
            latest_enrolled_encounter='current')

    def test_every_current_row_and_catalog_part_must_remain_identical(self):
        original = self.database(); op.unchanged(original, deepcopy(original))
        for name in original:
            changed = deepcopy(original); changed[name] = 'different'
            with self.subTest(name=name), self.assertRaisesRegex(op.Refusal, 'all_current_database_state_unchanged'):
                op.unchanged(original, changed)
        for table in ('core_encounter', 'core_codingrun', 'core_codingdecision', 'core_usage', 'django_migrations'):
            changed = deepcopy(original); changed['tables'][table][1] = 'modified'
            with self.subTest(table=table), self.assertRaises(op.Refusal): op.unchanged(original, changed)
        pending = deepcopy(original); pending['pending']['core_job'] = 1
        with self.assertRaisesRegex(op.Refusal, 'no_provider_work_during_install'): op.unchanged(pending, pending)

    def lifecycle(self, *, database_change=False):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory); root.chmod(0o700)
            app = root / 'app'; app.mkdir(); original = self.original_environment(); (app / '.env').write_bytes(original)
            declaration = root / 'declaration.md'; declaration.write_text('d' * 64 + '\n' + 'a' * 40 + '\n' + op.FORMAT)
            plan = self.plan(root); plan['environment_before_sha256'] = op.prior.sha(original)
            state = {'running': True}; actions = []
            def service(action, unit):
                actions.append((action, unit)); state['running'] = action == 'start'
            host = SimpleNamespace(configuration=lambda: {'units': 'same'}, service=service,
                state=lambda unit: {'ActiveState': 'active' if state['running'] else 'inactive',
                                    'MainPID': '123' if state['running'] else '0'})
            static = SimpleNamespace(static_inventory=lambda path: {'old-hashed.js': 'retained'})
            before = self.database(); after = deepcopy(before)
            if database_change: after['tables']['core_codingrun'][1] = 'selection-reset'
            for owner, name, value in ((op.prior, 'APP', app), (op.prior, 'source_guard', Mock()),
                (op.prior, 'source_plan', Mock(return_value={})), (op.prior, 'publish_source', Mock()),
                (op.prior, 'foreign_services', lambda: {'VoiceAssistMain': 'same'}),
                (op.prior, 'await_health', Mock(return_value={'release': plan['candidate']})),
                (op.prior, 'git', Mock(return_value=plan['candidate'].encode())),
                (op.prior.legacy, 'Host', lambda helper: host),
                (op.prior.legacy, 'operation_locks', lambda: nullcontext()),
                (op.prior.legacy, 'static_primitives', lambda: static),
                (op.prior.activation_exclusion, 'bind_runtime', Mock()),
                (op.prior.activation_exclusion, 'hold', lambda *args, **kwargs: nullcontext()),
                (op.prior.private_storage, 'inventory', lambda path: {'original.docx': 'same'}),
                (op.prior.backup_restore, 'read_private', lambda *args: original),
                (op.prior.backup_restore, 'key_at', lambda path: SimpleNamespace(encrypt=lambda raw: b'encrypted-test')),
                (op, 'snapshot', Mock(side_effect=[deepcopy(before), deepcopy(before), after])),
                (op.prior, 'command', Mock(side_effect=[str(root).encode(), declaration.read_bytes(), b'']))):
                stack.enter_context(patch.object(owner, name, value))
            stack.enter_context(patch.dict('os.environ', RULED_MUTATION_DECLARATION=str(declaration), RULED_MUTATION_DECL_COMMIT='f' * 40))
            if database_change:
                with self.assertRaisesRegex(op.Refusal, 'installation_failed_inspect_retained_evidence'): op.execute(plan, 'd' * 64)
                failure = json.loads((root / 'attempt/failure.json').read_text())
                self.assertEqual(failure['reason'], 'all_current_database_state_unchanged')
                self.assertEqual(actions, [('stop', unit) for unit in op.prior.UNITS])
                self.assertFalse((root / 'attempt/installation-complete.json').exists())
            else:
                result = op.execute(plan, 'd' * 64)
                self.assertEqual(result['migrations_executed'], 0); self.assertEqual(result['provider_calls'], 0)
                self.assertEqual(result['clinician_decisions_created'], 0)
                self.assertEqual(actions, [('stop', unit) for unit in op.prior.UNITS]
                    + [('start', unit) for unit in (op.prior.UNITS[2], *op.prior.UNITS[:2])])
                self.assertEqual((app / '.env').read_bytes(), op.render_environment(original, plan['candidate']))
                self.assertTrue((root / 'attempt/pre-resume-preservation.json').exists())

    def test_offline_lifecycle_preserves_state_and_uses_only_three_units(self):
        self.lifecycle()

    def test_changed_selection_refuses_resume_without_automatic_rollback_or_retry(self):
        self.lifecycle(database_change=True)


if __name__ == '__main__': unittest.main()
