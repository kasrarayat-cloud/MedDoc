"""Offline installation controls; optional DB controls admit only isolated 55449."""
from contextlib import ExitStack, contextmanager, nullcontext, redirect_stdout
from copy import deepcopy
import io
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

import psycopg
from ops import activate_coordinated_workflow as op


class BoundedSnapshotTests(unittest.TestCase):
    def test_empty_duplicate_and_changed_rows_have_distinct_counted_fingerprints(self):
        a, b = hashlib.sha256(b'first').digest(), hashlib.sha256(b'second').digest()
        inputs = [[], [a], [a, a], [a, b], [b], [a, a, b]]
        results = [op.fold_row_hashes((v,) for v in sorted(values)) for values in inputs]
        self.assertEqual([v[0] for v in results], [0, 1, 2, 2, 1, 3])
        self.assertEqual(len({v[1] for v in results}), len(inputs))
        self.assertEqual(results[3], op.fold_row_hashes((v,) for v in sorted([b, a])))
        expected = hashlib.sha256(op.TABLE_FINGERPRINT_CONTRACT.encode() + b'\0' + (0).to_bytes(8, 'big'))
        self.assertEqual(results[0], [0, expected.hexdigest()])

    def test_malformed_unsorted_and_interrupted_streams_never_return_a_fingerprint(self):
        for row in [(None,), ('a' * 32,), (b'a' * 31,), (b'a' * 33,), (b'a' * 32, b'b' * 32)]:
            with self.subTest(row=row), self.assertRaises(op.Refusal): op.fold_row_hashes([row])
        with self.assertRaisesRegex(op.Refusal, 'sorted_row_fingerprints'):
            op.fold_row_hashes([(b'z' * 32,), (b'a' * 32,)])
        def interrupted():
            yield (b'a' * 32,)
            raise psycopg.OperationalError('synthetic interrupted read')
        with self.assertRaises(psycopg.OperationalError): op.fold_row_hashes(interrupted())

    def test_query_streams_complete_row_digests_through_a_bounded_named_cursor(self):
        cursor = MagicMock(); cursor.__enter__.return_value = cursor
        cursor.__iter__.return_value = iter([(b'a' * 32,), (b'b' * 32,)])
        connection = Mock(); connection.cursor.return_value = cursor
        actual = op.table_fingerprint(connection, 'mixed " table')
        connection.cursor.assert_called_once_with(name='quillmd_preservation_row_hashes')
        self.assertEqual(cursor.itersize, 128)
        query = cursor.execute.call_args.args[0].as_string(None)
        self.assertIn('sha256(convert_to(to_jsonb(t)::text, \'UTF8\'))', query)
        self.assertIn('FROM "public"."mixed "" table" t ORDER BY row_hash', query)
        self.assertNotIn('string_agg', query); self.assertNotIn('DISTINCT', query)
        self.assertEqual(actual, op.fold_row_hashes([(b'a' * 32,), (b'b' * 32,)]))
        cursor.fetchall.assert_not_called(); cursor.__exit__.assert_called_once()

    def test_snapshot_keeps_every_catalog_and_ledger_in_one_readonly_repeatable_read_connection(self):
        class Rows(list):
            def fetchone(self): return self[0]
        queries = []
        def execute(query, params=None):
            query = query if isinstance(query, str) else query.as_string(None)
            queries.append((query, params))
            if query.startswith('SET '): return Rows()
            if 'current_database()' in query: return Rows([('quillmd_fresh', 'quillmd_runtime', 'on')])
            if 'SELECT tablename FROM pg_tables' in query: return Rows([('core_encounter',), ('core_usage',)])
            if 'SELECT app,name' in query: return Rows([('core', 'retained')])
            if 'SELECT id,app,name,applied' in query: return Rows([(49, 'core', 'retained', 'original-applied-time')])
            if 'SELECT count(*)' in query: return Rows([(0,)])
            if 'JOIN pg_attribute' in query: return Rows([('table', 'owner', 'acl', 'column', 'text', False)])
            if 'FROM pg_trigger' in query: return Rows([('table', 'trigger', 'definition', 'O')])
            if 'FROM pg_constraint' in query: return Rows([('table', 'constraint', 'definition')])
            if 'FROM pg_indexes' in query: return Rows([('table', 'index', 'definition')])
            if 'FROM pg_proc' in query: return Rows([('function', 'args', 'body-md5', 'owner', 'acl')])
            if 'FROM pg_sequences' in query: return Rows([('retained_sequence',)])
            if 'SELECT last_value,is_called' in query: return Rows([(17, True)])
            if 'SELECT max(created_at)' in query: return Rows([('latest-enrolled-time',)])
            self.fail('unexpected snapshot query')
        connection = MagicMock(); connection.__enter__.return_value = connection
        connection.execute.side_effect = execute
        def table_digest(actual_connection, table):
            self.assertIs(actual_connection, connection)
            return [1, table + '-digest']
        with patch.object(op.prior, 'database_options', return_value={'synthetic': 'transport'}) as options, \
                patch('psycopg.connect', return_value=connection) as connect, \
                patch.object(op, 'table_fingerprint', side_effect=table_digest) as rows:
            actual = op.snapshot(b'unread-synthetic-env')
        options.assert_called_once_with(b'unread-synthetic-env')
        connect.assert_called_once_with(synthetic='transport'); self.assertEqual(rows.call_count, 2)
        self.assertEqual(queries[0][0], 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        self.assertIn(("SET LOCAL work_mem='4MB'", None), queries)
        self.assertEqual(actual, dict(table_fingerprint_contract=op.TABLE_FINGERPRINT_CONTRACT,
            tables={'core_encounter': [1, 'core_encounter-digest'], 'core_usage': [1, 'core_usage-digest']},
            migrations=[['core', 'retained']], migration_ledger=[['49', 'core', 'retained', 'original-applied-time']],
            schema=[['table', 'owner', 'acl', 'column', 'text', False]],
            triggers=[['table', 'trigger', 'definition', 'O']], constraints=[['table', 'constraint', 'definition']],
            indexes=[['table', 'index', 'definition']], functions=[['function', 'args', 'body-md5', 'owner', 'acl']],
            sequences={'retained_sequence': [17, True]}, pending={name: 0 for name in
                ('core_job', 'core_codingrun', 'core_aistagereceipt', 'core_templatepreparation', 'core_templatedefinitionpreparation')},
            latest_enrolled_encounter='latest-enrolled-time'))
        pending = [(q, p) for q, p in queries if 'SELECT count(*)' in q]
        self.assertEqual([p[0] for _, p in pending], [['queued', 'running'], ['queued', 'running'],
            ['reserved', 'sending', 'received'], ['queued', 'inventory', 'proposer', 'checker'],
            ['queued', 'inventory', 'proposer', 'checker']])
        self.assertTrue(all('"public".' in q for q, _ in pending))
        self.assertIn(('SELECT last_value,is_called FROM "public"."retained_sequence"', None), queries)

    def test_snapshot_refuses_wrong_database_role_or_readonly_mode_before_row_reads(self):
        for identity in [('other', 'quillmd_runtime', 'on'), ('quillmd_fresh', 'owner', 'on'),
                         ('quillmd_fresh', 'quillmd_runtime', 'off')]:
            connection = MagicMock(); connection.__enter__.return_value = connection
            connection.execute.return_value.fetchone.return_value = identity
            with self.subTest(identity=identity), patch.object(op.prior, 'database_options', return_value={}), \
                    patch('psycopg.connect', return_value=connection), patch.object(op, 'table_fingerprint') as rows:
                with self.assertRaisesRegex(op.Refusal, 'readonly_snapshot'): op.snapshot(b'synthetic')
                rows.assert_not_called()


@unittest.skipUnless(os.environ.get('QUILLMD_SNAPSHOT_TEST_DSN'), 'opt-in isolated PostgreSQL 55449 only')
class BoundedSnapshotPostgresTests(unittest.TestCase):
    def setUp(self):
        options = psycopg.conninfo.conninfo_to_dict(os.environ['QUILLMD_SNAPSHOT_TEST_DSN'])
        self.assertTrue(set(options) <= {'host', 'port', 'dbname', 'user', 'password', 'connect_timeout'})
        self.assertEqual((options.get('host'), options.get('port')), ('127.0.0.1', '55449'))
        options['connect_timeout'] = '5'
        self.connection = psycopg.connect(**options)
        self.addCleanup(self.connection.close)
        self.connection.execute("SET LOCAL work_mem='4MB'")
        self.connection.execute("SET LOCAL statement_timeout='90s'")
        self.connection.execute('CREATE TEMP TABLE snapshot_probe (value text, payload jsonb, raw bytea) ON COMMIT DROP')

    def fingerprint(self):
        return op.table_fingerprint(self.connection, 'snapshot_probe', schema='pg_temp')

    def test_real_sql_order_duplicates_nulls_and_every_column(self):
        from psycopg.types.json import Jsonb
        self.assertEqual(self.fingerprint()[0], 0)
        rows = [('a|b', Jsonb({'x': 1, 'y': [None, '']}), b'\0|'),
                (None, Jsonb({'y': [None, ''], 'x': 1}), b''), ('', None, None)]
        for row in rows: self.connection.execute('INSERT INTO snapshot_probe VALUES (%s,%s,%s)', row)
        original = self.fingerprint()
        self.connection.execute('TRUNCATE snapshot_probe')
        for row in reversed(rows): self.connection.execute('INSERT INTO snapshot_probe VALUES (%s,%s,%s)', row)
        self.assertEqual(self.fingerprint(), original)
        self.connection.execute('INSERT INTO snapshot_probe SELECT * FROM snapshot_probe LIMIT 1')
        duplicate = self.fingerprint(); self.assertEqual(duplicate[0], 4); self.assertNotEqual(duplicate, original)
        for column, value in [('value', 'changed'), ('payload', Jsonb({'x': 2})), ('raw', b'changed')]:
            self.connection.execute('SAVEPOINT before_change')
            from psycopg import sql
            self.connection.execute(sql.SQL('UPDATE snapshot_probe SET {}=%s').format(sql.Identifier(column)), (value,))
            self.assertNotEqual(self.fingerprint(), duplicate)
            self.connection.execute('ROLLBACK TO SAVEPOINT before_change')
        self.connection.execute("UPDATE snapshot_probe SET value='' WHERE value IS NULL")
        self.assertNotEqual(self.fingerprint(), duplicate)

    @unittest.skipUnless(os.environ.get('QUILLMD_SNAPSHOT_TEST_REFERENCE'), 'opt-in retained large JSON input')
    def test_large_retained_json_is_hashed_without_whole_table_aggregation(self):
        from psycopg.types.json import Jsonb
        path = Path(os.environ['QUILLMD_SNAPSHOT_TEST_REFERENCE'])
        raw = path.read_bytes(); self.assertGreater(len(raw), 75_000_000)
        retained = json.loads(raw)['coding_releases'][0]
        self.assertGreater(len(retained['index']), 80_000)
        self.connection.execute('INSERT INTO snapshot_probe VALUES (%s,%s,%s)', ('retained', Jsonb(retained), None))
        one = self.fingerprint()
        self.connection.execute('INSERT INTO snapshot_probe SELECT * FROM snapshot_probe')
        two = self.fingerprint()
        self.connection.execute('INSERT INTO snapshot_probe SELECT * FROM snapshot_probe LIMIT 1')
        three = self.fingerprint()
        self.assertEqual([one[0], two[0], three[0]], [1, 2, 3])
        self.assertEqual(len({one[1], two[1], three[1]}), 3)
        self.connection.execute("UPDATE snapshot_probe SET payload=jsonb_set(payload,'{digest}', '\"altered\"') "
                                'WHERE ctid=(SELECT ctid FROM snapshot_probe LIMIT 1)')
        changed = self.fingerprint(); self.assertEqual(changed[0], 3); self.assertNotEqual(changed, three)


class CoordinatedWorkflowInstallTests(unittest.TestCase):
    def plan(self, root):
        return dict(format=op.FORMAT, base=op.BASE, candidate='a' * 40,
            source_sha256={'rebuild/core/semantic_generation.py': 'b' * 64},
            source_worktree=str(op.SOURCE), evidence_directory=str(root / 'attempt'),
            environment_before_sha256='c' * 64, environment={}, static=[])

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
            op.validate_plan(plan)
            plan['source_sha256'] = {'rebuild/core/semantic_generation.py': 'b' * 64}
            for name in ('rebuild/core/migrations/0032_extra.py', 'rebuild/templates/coding_panel.html',
                    'rebuild/core/coding_export.py', 'rebuild/quillmd/settings.py', 'rebuild/.env',
                    'rebuild/ops/activate_fresh_workflow.py', 'rebuild/ops/activate_supporting_facts.py',
                    'rebuild/core/semantic_source_context.py', 'rebuild/core/coding_recovery.py', 'rebuild/core/semantic_revalidation.py',
                    '/rebuild/core/jobs.py', 'rebuild/core/../jobs.py', 'rebuild/static/app.js',
                    'rebuild/ops/fixtures/corti_office_time_output_reference.json',
                    'rebuild/core/tests/test_unrelated.py',
                    'rebuild/core/tests/fixtures/iris_unreviewed.json'):
                bad = deepcopy(plan); bad['source_sha256'][name] = 'b' * 64
                with self.subTest(name=name), self.assertRaisesRegex(op.Refusal, 'only_coordinated_workflow_source'):
                    op.validate_plan(bad)
            for key in ('migration', 'credentials', 'guard_after_md5'):
                with self.assertRaisesRegex(op.Refusal, 'closed_coordinated_workflow_plan'):
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
            'django_migrations': [49, 'retained-ledger']}, migration_ledger=[['49', 'core', 'retained', 'time']],
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
                (op.prior, 'git', Mock(side_effect=lambda *args: b'' if args[0] == 'status' else
                    (plan['candidate'] if state['published'] else op.BASE).encode())),
                (op.prior.legacy, 'Host', lambda helper: host),
                (op.prior.legacy, 'operation_locks', coordination),
                (op.prior.legacy, 'static_primitives', lambda: static),
                (op.prior.activation_exclusion, 'bind_runtime', Mock()),
                (op.prior.activation_exclusion, 'hold', lambda *args, **kwargs: nullcontext()),
                (op.prior.private_storage, 'inventory', lambda path: {'original-failed-and-completed.docx': 'same'}),
                (op.prior.backup_restore, 'read_private', lambda *args: original),
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
                if failure == 'database_before_stop':
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
                    op.prior.source_guard.return_value.file_proof.assert_called_once()
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

    def test_offline_lifecycle_preserves_state_and_uses_only_three_units(self): self.lifecycle()

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
                (op.prior.backup_restore, 'read_private', lambda *args: original),
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
