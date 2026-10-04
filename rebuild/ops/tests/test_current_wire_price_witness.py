"""The prospective financial witness refuses before reading source or runtime state."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'fixtures/current_wire_price_witness.source'


class PreparedPriceWitness(unittest.TestCase):
    def invoke(self, *arguments):
        output = io.StringIO()
        prior_umask = os.umask(0o077)
        with patch.object(sys, 'argv', [str(SOURCE), *arguments]), \
                patch.object(sys, 'dont_write_bytecode', True), \
                patch('subprocess.check_output', side_effect=AssertionError('No Git/source reader allowed')) as git, \
                patch('socket.socket.connect', side_effect=AssertionError('No runtime connection allowed')) as network, \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            try:
                runpy.run_path(str(SOURCE), run_name='__main__')
            except BaseException as error:
                return error, output.getvalue(), git.call_count, network.call_count
            finally:
                os.umask(prior_umask)
        self.fail('Witness did not terminate at its prepared/refusal boundary')

    def test_default_prepared_receipt_reads_no_source_or_runtime(self):
        error, output, git, network = self.invoke()
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 0)
        self.assertEqual(json.loads(output), {
            'status': 'prepared', 'provider_requests': 0, 'database_queries': 0,
            'fingerprints_changed': False, 'clinical_qualification': False,
        })
        self.assertEqual((git, network), (0, 0))

    def test_missing_execution_bindings_refuse_without_a_false_receipt(self):
        error, output, git, network = self.invoke('--execute')
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 2)
        self.assertEqual((output, git, network), ('', 0, 0))

    def test_short_revision_refuses_before_source_or_evidence_reads(self):
        error, output, git, network = self.invoke(
            '--execute', '--source', '/opt/meddoc-pro/.worktrees/unused',
            '--revision', '7907ae5a', '--evidence', '/unused', '--attempt', '016', '--output', '/unused',
        )
        self.assertIsInstance(error, SystemExit)
        self.assertEqual(error.code, 2)
        self.assertEqual((output, git, network), ('', 0, 0))

    def test_existing_foreign_source_refuses_before_git_or_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            error, output, git, network = self.invoke(
                '--execute', '--source', directory, '--revision', 'a' * 40,
                '--evidence', '/unused', '--attempt', '016', '--output', '/unused',
            )
        self.assertIsInstance(error, ValueError)
        self.assertIn('isolated', str(error))
        self.assertEqual((output, git, network), ('', 0, 0))

    def test_source_alias_refuses_before_following_or_reading_it(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source'
            source.symlink_to('/opt/meddoc-pro')
            error, output, git, network = self.invoke(
                '--execute', '--source', str(source), '--revision', 'a' * 40,
                '--evidence', '/unused', '--attempt', '016', '--output', '/unused',
            )
        self.assertIsInstance(error, ValueError)
        self.assertIn('aliases', str(error))
        self.assertEqual((output, git, network), ('', 0, 0))
