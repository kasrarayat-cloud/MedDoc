"""Offline lifecycle and prospective baseline controls; no native actions."""
from contextlib import ExitStack, contextmanager, nullcontext, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import psycopg
from ops import activate_mixed_findings as op


class MixedFindingsInstallTests(unittest.TestCase):
    def plan(self, root):
        return dict(format=op.FORMAT, base=op.BASE, candidate='a' * 40,
            source_sha256={'rebuild/core/semantic_generation.py': 'b' * 64},
            source_worktree=str(op.SOURCE), evidence_directory=str(root / 'attempt'),
            environment_before_sha256='c' * 64, environment={}, static=[],
            baseline_path=str(root / 'declared-baseline.json'), baseline_sha256='0' * 64)

    def baseline(self, plan, **updates):
        now = datetime.now(timezone.utc)
        result = dict(capture_started_at=(now - timedelta(seconds=5)).isoformat(), captured_at=now.isoformat(),
            installed_base=plan['base'], candidate=plan['candidate'], source_worktree=plan['source_worktree'],
            source_sha256=plan['source_sha256'], installed_changed_source_sha256={'runtime.py': 'old'},
            environment_sha256=plan['environment_before_sha256'], read_only=True, provider_calls=0,
            native_mutations=0, coordination_exclusion_acquired=False, database=self.database(),
            configuration={'units': 'same'}, foreign_services={'VoiceAssistMain': 'same'},
            files={'original-failed-and-completed.docx': 'same'}, static={'immutable.js': 'same'})
        result.update(updates)
        return result

    def bind_baseline(self, plan, baseline):
        raw = json.dumps(baseline, sort_keys=True).encode()
        path = Path(plan['baseline_path']); path.write_bytes(raw); path.chmod(0o600)
        plan['baseline_sha256'] = op.prior.sha(raw)
        return raw

    def original_environment(self):
        return ('# retained configuration\r\nQUILLMD_RELEASE_SHA="' + op.BASE + '"\r\n'
                'QUILLMD_CORTI_NEW_ENCOUNTER_SCOPE=authorized_synthetic_clinicians\r\n'
                'QUILLMD_CORTI_OUTPUT_REFERENCE_FILE=/original/reference.json\r\n'
                'QUILLMD_CORTI_OUTPUT_REFERENCE_SHA256=' + 'e' * 64 + '\r\n'
                'QUILLMD_CORTI_NEW_ENCOUNTERS_SINCE=2026-10-16T20:00:00+00:00\r\n'
                'QUILLMD_CORTI_NEW_ENCOUNTER_ACTORS=retained-actors\r\n'
                'QUILLMD_CORTI_CREDENTIALS_FILE=/retained/credentials\r\n'
                'QUILLMD_SEMANTIC_REVALIDATION_V2_ORIGIN_JOB_IDS=retained\r\n'
                'SECRET="synthetic-${UNEXPANDED}"').encode()

    def test_default_is_inert_and_reads_no_operational_inputs(self):
        with patch('sys.argv', ['operator']), patch.object(op, 'execute') as execute, \
                patch.object(op.prior, 'private_json') as private, redirect_stdout(io.StringIO()) as out:
            op.main()
        self.assertEqual(json.loads(out.getvalue()), dict(inert=True, database_queries=0, provider_calls=0, service_actions=0))
        execute.assert_not_called(); private.assert_not_called()

    def test_bound_primitives_restore_even_after_failure(self):
        previous = (op.prior.BASE, op.prior.SOURCE, op.prior.STATIC)
        with self.assertRaisesRegex(RuntimeError, 'synthetic'):
            with op.bound_primitives():
                self.assertEqual((op.prior.BASE, op.prior.SOURCE, op.prior.STATIC),
                                 (op.BASE, op.SOURCE, frozenset()))
                raise RuntimeError('synthetic')
        self.assertEqual((op.prior.BASE, op.prior.SOURCE, op.prior.STATIC), previous)

    def test_closed_plan_rejects_other_runtime_schema_static_and_private_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700); plan = self.plan(root)
            plan['source_sha256'].update({name: 'e' * 64 for name in op.RUNTIME | op.SUPPORT | op.FIXTURES})
            self.assertEqual(len(plan['source_sha256']), 18)
            op.validate_plan(plan)
            plan['source_sha256'] = {'rebuild/core/semantic_generation.py': 'b' * 64}
            for name in ('rebuild/core/migrations/0032_extra.py', 'rebuild/templates/coding_panel.html',
                    'rebuild/core/coding_export.py', 'rebuild/quillmd/settings.py', 'rebuild/.env',
                    'rebuild/ops/activate_fresh_workflow.py', 'rebuild/ops/activate_supporting_facts.py',
                    'rebuild/ops/activate_coordinated_workflow.py', 'rebuild/ops/test_activate_coordinated_workflow.py',
                    'docs/runbooks/coordinated-workflow-install-20261017.md',
                    'rebuild/core/clinical_source_context.py', 'rebuild/core/coding_output.py',
                    'rebuild/core/semantic_source_context.py', 'rebuild/core/coding_recovery.py', 'rebuild/core/semantic_revalidation.py',
                    '/rebuild/core/jobs.py', 'rebuild/core/../jobs.py', 'rebuild/static/app.js',
                    'rebuild/ops/fixtures/corti_office_time_output_reference.json',
                    'rebuild/core/tests/test_unrelated.py',
                    'rebuild/core/tests/fixtures/iris_unreviewed.json'):
                bad = deepcopy(plan); bad['source_sha256'][name] = 'b' * 64
                with self.subTest(name=name), self.assertRaisesRegex(op.Refusal, 'only_mixed_findings_source'):
                    op.validate_plan(bad)
            for key in ('migration', 'credentials', 'guard_after_md5'):
                with self.assertRaisesRegex(op.Refusal, 'closed_mixed_findings_plan'):
                    op.validate_plan(dict(plan, **{key: 'unexpected'}))
            bad = deepcopy(plan); bad['static'] = ['app.js']
            with self.assertRaisesRegex(op.Refusal, 'static_must_remain_unchanged'): op.validate_plan(bad)
            (root / 'attempt').symlink_to(root / 'absent')
            with self.assertRaisesRegex(op.Refusal, 'exclusive_private_output'): op.validate_plan(plan)

    def test_release_stamp_only_preserves_every_other_byte_and_line_ending(self):
        original = self.original_environment()
        old = ('QUILLMD_RELEASE_SHA="' + op.BASE + '"').encode()
        new = b'QUILLMD_RELEASE_SHA="' + b'a' * 40 + b'"'
        self.assertEqual(op.render_environment(original, 'a' * 40, {}), original.replace(old, new))
        last = ('SECRET=retained\nQUILLMD_RELEASE_SHA="' + op.BASE + '"').encode()
        self.assertEqual(op.render_environment(last, 'a' * 40, {}), last.replace(old, new))

    def test_environment_refuses_wrong_base_duplicate_or_unrecognized_release_assignment(self):
        original = self.original_environment()
        for raw, reason in ((original.replace(op.BASE.encode(), b'b' * 40), 'exact_installed_release'),
                (original + ('\nQUILLMD_RELEASE_SHA=' + op.BASE + '\n').encode(), 'duplicate_release_assignment'),
                (('  QUILLMD_RELEASE_SHA="' + op.BASE + '"\n').encode() + original, 'duplicate_release_assignment'),
                (original.replace(b'QUILLMD_RELEASE_SHA=', b'QUILLMD_RELEASE_SHA ='), 'release_assignment_found')):
            with self.subTest(reason=reason), self.assertRaisesRegex(op.Refusal, reason):
                op.render_environment(raw, 'a' * 40, {})

    def test_plan_cannot_change_any_provider_policy_or_recovery_admission(self):
        keys = ('QUILLMD_RELEASE_SHA', 'QUILLMD_CORTI_NEW_ENCOUNTER_SCOPE',
            'QUILLMD_CORTI_OUTPUT_REFERENCE_FILE', 'QUILLMD_CORTI_OUTPUT_REFERENCE_SHA256',
            'QUILLMD_CORTI_CREDENTIALS_FILE', 'QUILLMD_CORTI_NEW_ENCOUNTERS_SINCE',
            'QUILLMD_CORTI_NEW_ENCOUNTER_ACTORS', 'QUILLMD_SEMANTIC_REVALIDATION_V2_ORIGIN_JOB_IDS')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700)
            for key in keys:
                environment = {key: 'changed'}; plan = self.plan(root); plan['environment'] = environment
                with self.subTest(key=key), self.assertRaisesRegex(op.Refusal, 'release_stamp_only'):
                    op.validate_plan(plan)
                with self.assertRaisesRegex(op.Refusal, 'release_stamp_only'):
                    op.render_environment(self.original_environment(), 'a' * 40, environment)

    def database(self):
        return dict(table_fingerprint_contract=op.TABLE_FINGERPRINT_CONTRACT,
            tables={'core_encounter': [3, 'elias-nadia-failures-and-three-completed'],
            'core_codingdecision': [2, 'approved-ICD'], 'core_codingoutputdecision': [2, 'accepted-CPT'],
            'core_auditevent': [11, 'retained-history'], 'core_usage': [7, 'retained-usage'],
            'django_migrations': [49, 'retained-ledger'], 'core_servicehealth': [3, 'health']},
            migration_ledger=[['49', 'core', 'retained', 'time']],
            migrations=[['core', 'retained']], schema=['columns-owner-acl'], constraints=['same'], indexes=['same'],
            triggers=['same'], functions=['same'], sequences={'django_migrations_id_seq': [49, True]},
            pending={'core_job': 0, 'core_codingrun': 0}, latest_enrolled_encounter='current')

    def test_all_current_rows_and_catalog_parts_must_remain_unchanged(self):
        original = self.database(); op.unchanged(original, deepcopy(original))
        for name in original:
            changed = deepcopy(original); changed[name] = 'different'
            with self.subTest(name=name), self.assertRaisesRegex(op.Refusal, 'all_current_database_state_unchanged'):
                op.unchanged(original, changed)
        for table in original['tables']:
            changed = deepcopy(original); changed['tables'][table][1] = 'modified'
            with self.subTest(table=table), self.assertRaises(op.Refusal): op.unchanged(original, changed)
        pending = deepcopy(original); pending['pending']['core_job'] = 1
        with self.assertRaisesRegex(op.Refusal, 'no_provider_work_during_install'): op.unchanged(pending, pending)

    def test_plan_shape_admits_uncreated_capture_target_but_execution_loader_refuses_placeholder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700); plan = self.plan(root)
            op.validate_plan(plan)
            self.assertFalse(Path(plan['baseline_path']).exists())
            with self.assertRaises(Exception): op.declared_baseline(plan)
            baseline = self.baseline(plan); raw = self.bind_baseline(plan, baseline)
            self.assertEqual(op.declared_baseline(plan), (baseline, raw))
            plan['baseline_sha256'] = '0' * 64
            with self.assertRaisesRegex(op.Refusal, 'declared_baseline_bytes'): op.declared_baseline(plan)

    def test_declared_baseline_rejects_corruption_wrong_purpose_and_stale_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); root.chmod(0o700); plan = self.plan(root)
            baseline = self.baseline(plan); self.bind_baseline(plan, baseline)
            Path(plan['baseline_path']).write_bytes(b'corrupt')
            with self.assertRaisesRegex(op.Refusal, 'declared_baseline_bytes'): op.declared_baseline(plan)
            now = datetime.now(timezone.utc)
            cases = [('candidate', 'e' * 40), ('installed_base', 'e' * 40),
                ('source_worktree', '/different'), ('source_sha256', {}),
                ('environment_sha256', 'e' * 64), ('read_only', False), ('provider_calls', 1),
                ('native_mutations', 1), ('coordination_exclusion_acquired', True),
                ('capture_started_at', (now - timedelta(hours=2)).isoformat()),
                ('captured_at', (now + timedelta(minutes=1)).isoformat()),
                ('capture_started_at', now.replace(tzinfo=None).isoformat())]
            for key, value in cases:
                bad = deepcopy(baseline); bad[key] = value; self.bind_baseline(plan, bad)
                with self.subTest(key=key), self.assertRaises(op.Refusal): op.declared_baseline(plan)
            for key, value in [('table_fingerprint_contract', 'historical-md5'), ('pending', {'core_job': 1})]:
                bad = deepcopy(baseline); bad['database'][key] = value; self.bind_baseline(plan, bad)
                with self.subTest(key=key), self.assertRaises(op.Refusal): op.declared_baseline(plan)

    def test_pre_stop_comparison_only_admits_same_count_servicehealth_fingerprint_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); plan = self.plan(root); declared = self.baseline(plan)
        prepared = {'before': {'runtime.py': {'sha256': 'old'}}}
        locked = {key: deepcopy(declared[key]) for key in ('configuration', 'files', 'static', 'database')}
        locked['services'] = deepcopy(declared['foreign_services'])
        self.assertEqual(op.compare_declared_baseline(declared, locked, prepared)['permitted_database_table_changes'], [])
        locked['database']['tables']['core_servicehealth'][1] = 'refreshed'
        self.assertEqual(op.compare_declared_baseline(declared, locked, prepared)['permitted_database_table_changes'],
                         ['core_servicehealth'])
        for key in ('configuration', 'files', 'static', 'services'):
            bad = deepcopy(locked); bad[key]['extra'] = 'changed'
            with self.subTest(key=key), self.assertRaises(op.Refusal): op.compare_declared_baseline(declared, bad, prepared)
        for key in declared['database']:
            if key == 'tables': continue
            bad = deepcopy(locked); bad['database'][key] = 'changed'
            with self.subTest(key=key), self.assertRaises(op.Refusal): op.compare_declared_baseline(declared, bad, prepared)
        for table in declared['database']['tables']:
            bad = deepcopy(locked)
            bad['database']['tables'][table][0 if table == 'core_servicehealth' else 1] = 'changed'
            with self.subTest(table=table), self.assertRaises(op.Refusal): op.compare_declared_baseline(declared, bad, prepared)
        bad = deepcopy(locked); bad['database']['tables']['new_table'] = [0, 'empty']
        with self.assertRaises(op.Refusal): op.compare_declared_baseline(declared, bad, prepared)
        with self.assertRaisesRegex(op.Refusal, 'declared_original_source_bytes'):
            op.compare_declared_baseline(declared, locked, {'before': {'runtime.py': {'sha256': 'different'}}})

    def test_database_diagnostics_keep_sqlstate_and_classification_without_error_text(self):
        secret = 'synthetic-secret-token patient=synthetic-source'
        cases = ((psycopg.OperationalError('connection refused ' + secret), None, 'connection_refused'),
            (psycopg.OperationalError('timeout expired ' + secret), None, 'connection_timeout'),
            (psycopg.errors.InvalidPassword('password authentication failed ' + secret), '28P01', 'authentication_failed'),
            (psycopg.errors.ConnectionFailure('server closed the connection unexpectedly ' + secret), '08006', 'server_closed_connection'))
        for error, sqlstate, classification in cases:
            with self.subTest(sqlstate=sqlstate, classification=classification):
                result = op.failure_diagnostics(error)
                self.assertEqual(result['sqlstate'], sqlstate)
                self.assertEqual(result['connection_failure'], classification)
                self.assertNotIn(secret, json.dumps(result)); self.assertNotIn(str(error), json.dumps(result))
        result = op.failure_diagnostics(op.Refusal(secret))
        self.assertEqual(result['reason'], 'installation_invariant_refused')
        self.assertNotIn(secret, json.dumps(result))

    def lifecycle(self, *, failure=None):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory); root.chmod(0o700); app = root / 'app'; app.mkdir()
            original = self.original_environment(); (app / '.env').write_bytes(original)
            declaration = root / 'declaration.md'; declaration.write_text('d' * 64 + '\n' + 'a' * 40 + '\n' + op.FORMAT)
            plan = self.plan(root); plan['environment_before_sha256'] = op.prior.sha(original)
            state = {'running': {unit: True for unit in op.prior.UNITS}, 'published': False, 'locked': False}; actions = []
            @contextmanager
            def coordination():
                state['locked'] = True
                try:
                    yield
                finally:
                    state['locked'] = False
            def service(action, unit):
                self.assertTrue(state['locked'], 'service actions and original recovery retain coordination')
                actions.append((action, unit)); state['running'][unit] = action == 'start'
                if failure == 'resume_start' and action == 'start' and unit == op.prior.UNITS[0]:
                    raise OSError('synthetic-secret-start-error')
            def publish(*args): state['published'] = True
            host = SimpleNamespace(configuration=lambda: {'units': 'same'}, service=service,
                state=lambda unit: {'ActiveState': 'active' if state['running'][unit] else 'inactive',
                                    'MainPID': '123' if state['running'][unit] else '0'})
            static = SimpleNamespace(static_inventory=lambda path: {'immutable.js': 'same'})
            before = self.database(); snapshots = [deepcopy(before) for _ in range(3)]
            if failure == 'approval_changed': snapshots[2]['tables']['core_codingoutputdecision'][1] = 'changed'
            if failure in {'database_before_stop', 'database_after_stop'}:
                snapshots[0 if failure == 'database_before_stop' else 1] = psycopg.OperationalError(
                    'connection refused password=synthetic-secret-do-not-print')
            prepared = {'before': {'runtime.py': {'sha256': 'old'}}, 'after': {'runtime.py': {'sha256': 'new'}}, 'binding': {}}
            declared = self.baseline(plan)
            if failure == 'foreign_drift': declared['foreign_services']['fwupd.service'] = 'running-original-identity'
            if failure == 'clinical_drift': declared['database']['tables']['core_encounter'][1] = 'different'
            if failure == 'metadata_drift': declared['database']['sequences']['django_migrations_id_seq'] = [50, True]
            if failure == 'servicehealth_count': declared['database']['tables']['core_servicehealth'][0] = 4
            if failure == 'original_source_drift': declared['installed_changed_source_sha256']['runtime.py'] = 'changed'
            if failure is None: declared['database']['tables']['core_servicehealth'][1] = 'earlier-health-refresh'
            declared_raw = self.bind_baseline(plan, declared)
            reads = []
            def read_private(path, limit):
                reads.append(path)
                if path != Path(plan['baseline_path']): return original
                if failure == 'baseline_changed_under_lock' and state['locked']: return declared_raw + b' '
                return declared_raw
            def git(*args):
                if args[0] == 'status': return b' M runtime.py' if failure == 'stale_source' else b''
                return (plan['candidate'] if state['published'] else op.BASE).encode()
            write_new = op.prior.write_new
            def retain(path, value):
                target = {'retain_after_stop': 'database-after-stop.json',
                          'retain_before_resume': 'database-before-resume.json'}.get(failure)
                if path.name == target:
                    raise OSError('synthetic-secret-evidence-write-error')
                return write_new(path, value)
            for owner, name, value in ((op.prior, 'APP', app), (op.prior, 'source_guard', Mock()),
                (op.prior, 'write_new', retain),
                (op.prior, 'source_plan', Mock(return_value=prepared)), (op.prior, 'publish_source', Mock(side_effect=publish)),
                (op.prior, 'foreign_services', lambda: {'VoiceAssistMain': 'same'}),
                (op.prior, 'await_health', Mock(return_value={'release': plan['candidate']},
                    side_effect=op.Refusal('health_not_ready') if failure == 'health' else None)),
                (op.prior, 'git', Mock(side_effect=git)),
                (op.prior.legacy, 'Host', lambda helper: host),
                (op.prior.legacy, 'operation_locks', coordination),
                (op.prior.legacy, 'static_primitives', lambda: static),
                (op.prior.activation_exclusion, 'bind_runtime', Mock()),
                (op.prior.activation_exclusion, 'hold', lambda *args, **kwargs: nullcontext()),
                (op.prior.private_storage, 'inventory', lambda path: {'original-failed-and-completed.docx': 'same'}),
                (op.prior.backup_restore, 'read_private', read_private),
                (op.prior.backup_restore, 'key_at', lambda path: SimpleNamespace(encrypt=lambda raw: b'encrypted-test')),
                (op, 'snapshot', Mock(side_effect=snapshots)),
                (op.prior, 'command', Mock(side_effect=[str(root).encode(), declaration.read_bytes(), b'']))):
                stack.enter_context(patch.object(owner, name, value))
            stack.enter_context(patch.dict('os.environ', RULED_MUTATION_DECLARATION=str(declaration), RULED_MUTATION_DECL_COMMIT='f' * 40))
            if failure:
                with self.assertRaisesRegex(op.Refusal, 'installation_failed_inspect_retained_evidence'): op.execute(plan, 'd' * 64)
                diagnostic = json.loads((root / 'attempt/failure.json').read_text())
                self.assertFalse((root / 'attempt/installation-complete.json').exists())
                self.assertFalse(diagnostic['automatic_retry'])
                self.assertNotIn('synthetic-secret', json.dumps(diagnostic))
                if failure in {'foreign_drift', 'clinical_drift', 'metadata_drift', 'servicehealth_count',
                               'original_source_drift', 'baseline_changed_under_lock', 'stale_source'}:
                    self.assertEqual(diagnostic['stage'], 'original_source_before_stop' if failure == 'stale_source'
                                     else 'declared_baseline_comparison')
                    self.assertEqual(actions, []); op.prior.publish_source.assert_not_called()
                    self.assertFalse(diagnostic['stopped']); self.assertFalse(diagnostic['publication_attempted'])
                    self.assertEqual((app / '.env').read_bytes(), original)
                    self.assertTrue(all(state['running'].values()))
                    self.assertFalse((root / 'attempt/pre-stop-comparison.json').exists())
                elif failure == 'database_before_stop':
                    self.assertEqual(diagnostic['stage'], 'baseline_database')
                    self.assertEqual(diagnostic['connection_failure'], 'connection_refused')
                    self.assertEqual(actions, []); op.prior.publish_source.assert_not_called()
                    self.assertEqual((app / '.env').read_bytes(), original)
                elif failure in {'database_after_stop', 'retain_after_stop'}:
                    self.assertEqual(diagnostic['stage'], 'database_after_stop' if failure == 'database_after_stop'
                                     else 'retain_database_after_stop')
                    self.assertTrue((root / 'attempt/original-release-resumed.json').exists())
                    op.prior.publish_source.assert_not_called()
                    self.assertEqual(actions, [('stop', unit) for unit in op.prior.UNITS]
                        + [('start', unit) for unit in (op.prior.UNITS[2], *op.prior.UNITS[:2])])
                    self.assertEqual(op.prior.source_guard.return_value.file_proof.call_count, 2)
                elif failure in {'health', 'resume_start'}:
                    self.assertTrue(diagnostic['publication_attempted']); self.assertTrue(diagnostic['resume_started'])
                    self.assertEqual(diagnostic['stage'], 'normal_https_health' if failure == 'health' else 'resume_owned_services')
                    self.assertEqual(actions[-3:], [('stop', unit) for unit in op.prior.UNITS])
                    self.assertFalse(any(state['running'].values()))
                    self.assertTrue(diagnostic['failed_resume_drain']['all_units_inactive'])
                    self.assertTrue((root / 'attempt/failed-resume-drain.json').exists())
                    self.assertFalse((root / 'attempt/original-release-resumed.json').exists())
                elif failure == 'retain_before_resume':
                    self.assertEqual(diagnostic['stage'], 'retain_database_before_resume')
                    self.assertTrue(diagnostic['publication_attempted'])
                    self.assertFalse(diagnostic['resume_started'])
                    self.assertFalse(any(state['running'].values()))
                    self.assertFalse((root / 'attempt/original-release-resumed.json').exists())
                    self.assertTrue((root / 'attempt/database-after-stop.json').exists())
                else:
                    self.assertEqual(diagnostic['stage'], 'database_before_resume')
                    retained = json.loads((root / 'attempt/database-before-resume.json').read_text())
                    self.assertEqual(retained['tables']['core_codingoutputdecision'][1], 'changed')
                    self.assertEqual(diagnostic['reason'], 'installation_invariant_refused')
                    self.assertEqual(actions, [('stop', unit) for unit in op.prior.UNITS])
                    self.assertFalse((root / 'attempt/original-release-resumed.json').exists())
            else:
                result = op.execute(plan, 'd' * 64)
                self.assertEqual((result['migrations_executed'], result['provider_calls'], result['clinician_decisions_created']), (0, 0, 0))
                self.assertEqual(result['environment_delta'], ['QUILLMD_RELEASE_SHA'])
                self.assertEqual(actions, [('stop', unit) for unit in op.prior.UNITS]
                    + [('start', unit) for unit in (op.prior.UNITS[2], *op.prior.UNITS[:2])])
                self.assertEqual((app / '.env').read_bytes(), op.render_environment(original, plan['candidate'], {}))
                preservation = json.loads((root / 'attempt/pre-resume-preservation.json').read_text())
                baseline = json.loads((root / 'attempt/baseline.json').read_text())
                self.assertEqual(baseline['static'], {'immutable.js': 'same'})
                self.assertEqual(baseline['database'], before)
                self.assertEqual(result['evidence_sha256'], preservation['evidence_sha256'])
                self.assertEqual(set(result['evidence_sha256']),
                    {'baseline.json', 'database-after-stop.json', 'database-before-resume.json'})
                for name, digest in result['evidence_sha256'].items():
                    self.assertEqual(digest, op.prior.sha((root / 'attempt' / name).read_bytes()))
                    if name != 'baseline.json':
                        self.assertEqual(json.loads((root / 'attempt' / name).read_text()), before)
                self.assertEqual(result['plan_sha256'], 'd' * 64)
                self.assertEqual(result['declaration_commit'], 'f' * 40)
                self.assertEqual(result['declaration_sha256'], op.prior.sha(declaration.read_bytes()))
                self.assertEqual((root / 'attempt/declared-baseline.json').read_bytes(), declared_raw)
                comparison = json.loads((root / 'attempt/pre-stop-comparison.json').read_text())
                self.assertEqual(comparison['permitted_database_table_changes'], ['core_servicehealth'])
                self.assertEqual(result['declared_baseline_sha256'], op.prior.sha(declared_raw))
                self.assertEqual(result['pre_stop_comparison_sha256'],
                                 op.prior.sha((root / 'attempt/pre-stop-comparison.json').read_bytes()))
                self.assertEqual(reads.count(Path(plan['baseline_path'])), 2)

    def test_offline_lifecycle_preserves_state_and_uses_only_three_units(self): self.lifecycle()

    def test_earlier_foreign_service_disappearance_refuses_before_first_service_action(self): self.lifecycle(failure='foreign_drift')

    def test_pre_stop_gate_refuses_other_database_and_source_drift(self):
        for failure in ('clinical_drift', 'metadata_drift', 'servicehealth_count', 'original_source_drift', 'stale_source'):
            with self.subTest(failure=failure): self.lifecycle(failure=failure)

    def test_bound_baseline_changed_after_entering_locks_refuses_before_stop(self): self.lifecycle(failure='baseline_changed_under_lock')

    def test_database_failure_before_stop_retains_safe_stage_without_mutation(self): self.lifecycle(failure='database_before_stop')

    def test_database_failure_after_stop_recovers_only_unchanged_original_release(self): self.lifecycle(failure='database_after_stop')

    def test_changed_approval_after_publication_refuses_resume_and_rollback(self): self.lifecycle(failure='approval_changed')

    def test_health_failure_stops_and_verifies_every_new_unit_under_coordination(self): self.lifecycle(failure='health')

    def test_partial_new_service_start_failure_stops_and_verifies_every_unit(self): self.lifecycle(failure='resume_start')

    def test_failed_after_stop_snapshot_retention_recovers_only_verified_old_release(self):
        self.lifecycle(failure='retain_after_stop')

    def test_failed_before_resume_snapshot_retention_leaves_all_new_units_stopped(self):
        self.lifecycle(failure='retain_before_resume')

    def test_original_recovery_requires_clean_index_original_file_proofs_and_new_paths_absent(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory); original = b'original'; (root / '.env').write_bytes(original)
            guard = SimpleNamespace(file_proof=Mock())
            prepared = {'before': {'old.py': {'sha256': 'old'}},
                'after': {'old.py': {'sha256': 'new'}, 'new.py': {'sha256': 'new'}}, 'binding': {}}
            git = Mock(side_effect=lambda *args: op.BASE.encode() if args[0] == 'rev-parse' else b'')
            stack.enter_context(patch.object(op.prior, 'ROOT', root)); stack.enter_context(patch.object(op.prior, 'APP', root))
            stack.enter_context(patch.object(op.prior, 'git', git))
            op.verify_original_before_resume(original, guard, prepared)
            guard.file_proof.assert_called_once_with(root, 'old.py', prepared['before']['old.py'], {}, revision=op.BASE)
            git.side_effect = lambda *args: op.BASE.encode() if args[0] == 'rev-parse' else b'M  old.py\n'
            with self.assertRaisesRegex(op.Refusal, 'clean_original_checkout_before_recovery'):
                op.verify_original_before_resume(original, guard, prepared)
            git.side_effect = lambda *args: op.BASE.encode() if args[0] == 'rev-parse' else b''
            (root / 'new.py').symlink_to(root / 'absent')
            with self.assertRaisesRegex(op.Refusal, 'new_source_absent_before_recovery'):
                op.verify_original_before_resume(original, guard, prepared)
            (root / 'new.py').unlink(); guard.file_proof.side_effect = op.Refusal('original_file_changed')
            with self.assertRaisesRegex(op.Refusal, 'original_file_changed'):
                op.verify_original_before_resume(original, guard, prepared)

    def test_stop_failure_still_attempts_every_unit_and_does_not_claim_shutdown(self):
        actions = []
        def stop(action, unit):
            actions.append((action, unit))
            if unit == op.prior.UNITS[0]: raise OSError('synthetic-secret-service-error')
        host = SimpleNamespace(service=stop, state=lambda unit: {
            'ActiveState': 'active' if unit == op.prior.UNITS[0] else 'inactive',
            'MainPID': '123' if unit == op.prior.UNITS[0] else '0'})
        result = op.stop_failed_resume(host)
        self.assertEqual(actions, [('stop', unit) for unit in op.prior.UNITS])
        self.assertFalse(result['all_units_inactive']); self.assertEqual(len(result['units_inactive']), 3)
        self.assertIn(op.prior.UNITS[0], result['stop_errors'])
        self.assertNotIn('synthetic-secret', json.dumps(result))

    def test_real_git_partial_fast_forward_never_restarts_original_head(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory); root.chmod(0o700); repo = root / 'repo'; repo.mkdir()
            def shellgit(*args):
                return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, check=False)
            def checked(*args):
                result = shellgit(*args); self.assertEqual(result.returncode, 0, result.stderr.decode()); return result.stdout
            checked('init', '-b', 'main'); checked('config', 'user.name', 'Synthetic')
            checked('config', 'user.email', 'synthetic@example.invalid'); checked('config', 'core.hooksPath', '/dev/null')
            runtime = repo / 'runtime.py'; runtime.write_text('version="base"\n')
            checked('add', '.'); checked('commit', '-m', 'base'); base = checked('rev-parse', 'HEAD').decode().strip()
            checked('switch', '-c', 'candidate'); runtime.write_text('version="candidate"\n')
            checked('commit', '-am', 'candidate'); candidate = checked('rev-parse', 'HEAD').decode().strip()
            checked('switch', 'main')
            app = root / 'app'; app.mkdir(); original = ('QUILLMD_RELEASE_SHA="' + base + '"\n').encode()
            (app / '.env').write_bytes(original)
            declaration = root / 'declaration.md'; declaration.write_text('d' * 64 + '\n' + candidate + '\n' + op.FORMAT)
            plan = self.plan(root); plan.update(base=base, candidate=candidate, environment_before_sha256=op.prior.sha(original))
            baseline_raw = self.bind_baseline(plan, self.baseline(plan,
                installed_changed_source_sha256={}, configuration={}, foreign_services={}, files={}, static={}))
            actions = []; running = {unit: True for unit in op.prior.UNITS}
            def service(action, unit): actions.append((action, unit)); running[unit] = action == 'start'
            host = SimpleNamespace(configuration=lambda: {}, service=service, state=lambda unit: {
                'ActiveState': 'active' if running[unit] else 'inactive', 'MainPID': '123' if running[unit] else '0'})
            def git(*args, **kwargs):
                if args[0] == 'merge': (repo / '.git/refs/heads/main.lock').write_text('')
                result = shellgit(*args); op.require(result.returncode == 0, 'bounded_command_failed'); return result.stdout
            guard = SimpleNamespace(file_proof=lambda *args, **kwargs: None, current_umask=lambda: 0o077)
            for owner, name, value in ((op, 'BASE', base), (op.prior, 'BASE', base), (op.prior, 'ROOT', repo),
                (op.prior, 'APP', app), (op.prior, 'git', git), (op.prior, 'source_guard', lambda: guard),
                (op.prior, 'source_plan', lambda *args: {'before': {}, 'after': {}, 'binding': {}}),
                (op.prior, 'foreign_services', lambda: {}), (op.prior.legacy, 'Host', lambda helper: host),
                (op.prior.legacy, 'operation_locks', lambda: nullcontext()),
                (op.prior.legacy, 'static_primitives', lambda: SimpleNamespace(static_inventory=lambda path: {})),
                (op.prior.activation_exclusion, 'bind_runtime', Mock()),
                (op.prior.activation_exclusion, 'hold', lambda *args, **kwargs: nullcontext()),
                (op.prior.private_storage, 'inventory', lambda path: {}),
                (op.prior.backup_restore, 'read_private', lambda path, limit:
                    baseline_raw if path == Path(plan['baseline_path']) else original),
                (op.prior.backup_restore, 'key_at', lambda path: SimpleNamespace(encrypt=lambda raw: b'encrypted')),
                (op, 'snapshot', lambda *args: self.database()),
                (op.prior, 'command', Mock(side_effect=[str(root).encode(), declaration.read_bytes(), b'']))):
                stack.enter_context(patch.object(owner, name, value))
            stack.enter_context(patch.dict('os.environ', RULED_MUTATION_DECLARATION=str(declaration), RULED_MUTATION_DECL_COMMIT='f' * 40))
            with self.assertRaisesRegex(op.Refusal, 'installation_failed_inspect_retained_evidence'): op.execute(plan, 'd' * 64)
            self.assertEqual(checked('rev-parse', 'HEAD').decode().strip(), base)
            self.assertEqual(runtime.read_text(), 'version="candidate"\n')
            self.assertTrue(checked('status', '--porcelain').strip())
            self.assertEqual(actions, [('stop', unit) for unit in op.prior.UNITS])
            self.assertFalse(any(running.values()))
            self.assertFalse((root / 'attempt/original-release-resumed.json').exists())
            failure = json.loads((root / 'attempt/failure.json').read_text())
            self.assertTrue(failure['publication_attempted']); self.assertFalse(failure['resume_started'])


if __name__ == '__main__': unittest.main()
