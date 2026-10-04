"""Pure preparation and isolation checks; the actual application is not run."""
import builtins
from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from unittest import TestCase
from unittest.mock import patch

SOURCE = Path(__file__).parents[1] / 'fixtures/ordinary_batch_application_rehearsal.source'
SUPERVISOR = SOURCE.with_name('ordinary_batch_rehearsal_packet.source')
OWNED = Path('/opt/meddoc-pro/rebuild/.runtime/v1-sol-continuation-20261002/storage-resume-20261003T215613Z/operations')
REVISION = 'b' * 40


class PreparedBatchRehearsal(TestCase):
    def setUp(self):
        self.code = compile(SOURCE.read_text(), str(SOURCE), 'exec')
        self.out, self.err = io.StringIO(), io.StringIO()
        imported = builtins.__import__

        def no_runtime(name, *args, **kwargs):
            if name.split('.')[0] in ('django', 'httpx', 'anthropic', 'core', 'ops', 'psycopg'):
                raise AssertionError('Prepared/refused execution must not import the application')
            return imported(name, *args, **kwargs)

        for guard in [patch.object(builtins, '__import__', side_effect=no_runtime),
                      patch.object(socket.socket, 'connect', side_effect=AssertionError('No network in preparation')),
                      patch.object(subprocess, 'run', side_effect=AssertionError('No child process in preparation')),
                      patch.object(Path, 'mkdir', side_effect=AssertionError('No runtime directory in preparation'))]:
            guard.start()
            self.addCleanup(guard.stop)

    def execute(self, argv):
        with patch.object(sys, 'argv', [str(SOURCE)] + argv), redirect_stdout(self.out), redirect_stderr(self.err):
            exec(self.code, {'__name__': '__main__', '__file__': str(SOURCE)})

    def test_default_is_prepared_without_source_reads_or_git_or_runtime(self):
        with patch.object(Path, 'read_text', side_effect=AssertionError('No source or credential reads')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('No source or credential reads')), \
                patch.object(subprocess, 'check_output', side_effect=AssertionError('No source commands')):
            with self.assertRaises(SystemExit) as exit_result:
                self.execute([])
        self.assertEqual(exit_result.exception.code, 0)
        self.assertEqual(json.loads(self.out.getvalue()), {'status': 'prepared', 'mocked_provider': True,
            'provider_requests': 0, 'database_queries': 0, 'live_campaign_started': False})

    def test_execute_requires_full_exact_revision_before_runtime(self):
        for args in [[], ['--source', '/opt/meddoc-pro/.worktrees/prepared-rehearsal', '--revision', 'b' * 8,
                           '--output', str(OWNED / 'never-created')]]:
            with self.subTest(args=args), self.assertRaises(SystemExit) as result:
                self.execute(['--execute'] + args)
            self.assertEqual(result.exception.code, 2)

    def test_catalog_check_also_defaults_to_prepared_without_a_connection(self):
        with self.assertRaises(SystemExit) as result:
            self.execute(['--catalog-absence'])
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(json.loads(self.out.getvalue())['database_queries'], 0)

    def test_shared_or_foreign_source_is_refused_before_source_commands(self):
        with patch.object(subprocess, 'check_output', side_effect=AssertionError('No source command')):
            for source in ['/opt/meddoc-pro', '/tmp/foreign-worktree']:
                with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'direct isolated'):
                    self.execute(['--execute', '--source', source, '--revision', REVISION,
                                  '--output', str(OWNED / 'never-created')])

    def frozen_execution(self, environ):
        with patch.object(Path, 'is_symlink', return_value=False), patch.object(Path, 'exists', return_value=False), \
                patch.object(Path, 'resolve', autospec=True, side_effect=lambda path, **kwargs: path), \
                patch.object(subprocess, 'check_output', side_effect=[REVISION + '\n', '']), \
                patch.dict(os.environ, environ, clear=True):
            self.execute(['--execute', '--source', '/opt/meddoc-pro/.worktrees/prepared-rehearsal',
                          '--revision', REVISION, '--output', str(OWNED / 'never-created')])

    def test_foreign_database_is_refused_before_django_or_directory_creation(self):
        with self.assertRaisesRegex(ValueError, 'specifically owned'):
            self.frozen_execution({'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_DB_PORT': '55731',
                'QUILLMD_DB_NAME': 'quillmd_qa_standing_20261004_3',
                'QUILLMD_DATA_MODE': 'synthetic', 'QUILLMD_AI_MODE': 'fixture', 'QUILLMD_DB_USER': 'quillmd_qa'})

    def test_provider_mode_and_real_data_modes_are_refused_before_runtime(self):
        allowed = {'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_DB_PORT': '55731',
            'QUILLMD_DB_NAME': 'quillmd_qa_sol_ops_batchrehearsal1004',
            'QUILLMD_DATA_MODE': 'synthetic', 'QUILLMD_AI_MODE': 'fixture', 'QUILLMD_DB_USER': 'quillmd_qa'}
        for key, value in [('QUILLMD_DATA_MODE', 'real'), ('QUILLMD_AI_MODE', 'live')]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'fixture-only'):
                self.frozen_execution({**allowed, key: value})

    def test_a_foreign_database_role_is_refused_before_runtime(self):
        with self.assertRaisesRegex(ValueError, 'normal protected synthetic QA role'):
            self.frozen_execution({'QUILLMD_DB_HOST': '127.0.0.1', 'QUILLMD_DB_PORT': '55731',
                'QUILLMD_DB_NAME': 'quillmd_qa_sol_ops_batchrehearsal1004',
                'QUILLMD_DATA_MODE': 'synthetic', 'QUILLMD_AI_MODE': 'fixture', 'QUILLMD_DB_USER': 'other_role'})

    def test_stale_or_dirty_source_refuses_before_runtime(self):
        for head, dirty in [('c' * 40, ''), (REVISION, ' M rebuild/core/generation.py')]:
            with self.subTest(head=head, dirty=dirty), patch.object(Path, 'is_symlink', return_value=False), \
                    patch.object(Path, 'exists', return_value=False), \
                    patch.object(Path, 'resolve', autospec=True, side_effect=lambda path, **kwargs: path), \
                    patch.object(subprocess, 'check_output', side_effect=[head + '\n', dirty]), \
                    self.assertRaisesRegex(ValueError, 'exact frozen source'):
                self.execute(['--execute', '--source', '/opt/meddoc-pro/.worktrees/prepared-rehearsal',
                              '--revision', REVISION, '--output', str(OWNED / 'never-created')])

    def test_supervisor_defaults_to_prepared_without_source_reads_or_children(self):
        code = compile(SUPERVISOR.read_text(), str(SUPERVISOR), 'exec')
        with patch.object(Path, 'read_text', side_effect=AssertionError('No source or credential reads')), \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('No source or credential reads')), \
                patch.object(subprocess, 'check_output', side_effect=AssertionError('No source commands')), \
                patch.object(subprocess, 'Popen', side_effect=AssertionError('No child process')), \
                patch.object(sys, 'argv', [str(SUPERVISOR)]), redirect_stdout(self.out), self.assertRaises(SystemExit) as result:
            exec(code, {'__name__': '__main__', '__file__': str(SUPERVISOR)})
        self.assertEqual(result.exception.code, 0)
        self.assertEqual(json.loads(self.out.getvalue()), {'status': 'prepared', 'mocked_provider': True,
            'provider_requests': 0, 'database_queries': 0, 'children_started': 0})
