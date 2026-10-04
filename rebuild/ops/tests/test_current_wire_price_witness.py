"""The prospective financial witness refuses before reading source or runtime state."""
import contextlib
import ast
import io
import json
import os
from pathlib import Path
import runpy
import re
import sys
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'fixtures/current_wire_price_witness.source'


class StandingEvidenceIdentity(unittest.TestCase):
    """Compile the literal admission guard without executing the witness or reading evidence."""
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SOURCE.read_bytes())
        guards = [node for node in tree.body if isinstance(node, ast.If) and any(
            isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
            and call.func.attr == 'fullmatch' and call.args
            and isinstance(call.args[0], ast.Constant)
            and isinstance(call.args[0].value, str)
            and call.args[0].value.startswith('v1-standing-api-testing-')
            for call in ast.walk(node.test))]
        assert len(guards) == 1
        cls.admission = compile(ast.Expression(guards[0].test), str(SOURCE), 'eval')
        normal = ast.parse((SOURCE.parents[1] / 'standing_qa.py').read_bytes())
        declaration = next(node for node in normal.body if isinstance(node, ast.Assign)
                           and any(isinstance(target, ast.Name) and target.id == 'LIVE_CAMPAIGN'
                                   for target in node.targets))
        cls.normal_pattern = re.compile(ast.literal_eval(declaration.value.args[0]))

    def refused(self, evidence):
        return bool(eval(self.admission, {'evidence': Path(evidence), 'Path': Path, 're': re}))

    def test_first_and_all_authorized_later_campaign_roots_pass_this_guard(self):
        for suffix in ['', *['-' + str(number) for number in range(2, 100)]]:
            with self.subTest(suffix=suffix):
                self.assertFalse(self.refused('/opt/meddoc-pro/rebuild/.runtime/'
                    'v1-standing-api-testing-20261004' + suffix + '/evidence'))

    def test_zero_one_padded_and_unbounded_later_identities_refuse(self):
        for suffix in ['-0', '-1', '-01', '-02', '-100', '-999', '-2-extra', '-2/child']:
            with self.subTest(suffix=suffix):
                self.assertTrue(self.refused('/opt/meddoc-pro/rebuild/.runtime/'
                    'v1-standing-api-testing-20261004' + suffix + '/evidence'))

    def test_foreign_root_and_evidence_directory_cannot_use_a_valid_suffix(self):
        for path in ['/tmp/v1-standing-api-testing-20261004-2/evidence',
                     '/opt/meddoc-pro/rebuild/.runtime/foreign-20261004-2/evidence',
                     '/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-2/other',
                     '/opt/meddoc-pro/rebuild/.runtime/v1-standing-api-testing-20261004-2/child/evidence']:
            with self.subTest(path=path):
                self.assertTrue(self.refused(path))

    def test_literal_identity_grammar_matches_the_normal_standing_runner(self):
        identities = ['20261004', '20261004-2', '20261004-99', '20261004-100',
                      '20261004-0', '20261004-1', '20261004-02', '20261004-2-other',
                      '19991004', '2026100', '202610040', 'foreign-20261004-2']
        for identity in identities:
            with self.subTest(identity=identity):
                normal_accepts = self.normal_pattern.fullmatch(
                    'quillmd-v1-standing-api-testing-' + identity) is not None
                self.assertEqual(not self.refused('/opt/meddoc-pro/rebuild/.runtime/'
                    'v1-standing-api-testing-' + identity + '/evidence'), normal_accepts)


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
