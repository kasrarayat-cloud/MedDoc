"""The prospective financial witness refuses before reading source or runtime state."""
import contextlib
import ast
import io
import copy
import hashlib
import json
import os
from pathlib import Path
import runpy
import re
import sys
import tempfile
import unittest
from unittest.mock import patch
from decimal import Decimal, ROUND_CEILING


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


class CapturedOrdinaryPrice(unittest.TestCase):
    """Actual full compiler and two-child quote; evidence/plan forgeries refuse."""
    @classmethod
    def setUpClass(cls):
        from core import generation as g, generation_batch as b, v3_field_relations as r
        function = next(n for n in ast.parse(SOURCE.read_bytes()).body
                        if isinstance(n, ast.FunctionDef) and n.name == 'reconstruct_request')
        namespace = dict(json=json, hashlib=hashlib, Decimal=Decimal,
                         ROUND_CEILING=ROUND_CEILING, g=g, b=b, r=r)
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), 'exec'), namespace)
        cls.read = staticmethod(namespace['reconstruct_request'])
        cls.g, cls.b, cls.r = g, b, r

    def setUp(self):
        from django.test import override_settings
        from ops import sonnet5_qa as sq, sonnet5_stages as stages, standing_qa_batch as batch
        from documents import word_v3
        settings = override_settings(**{**stages.steps.PATH_FLAGS['field_relations'],
            'AI_MODE': 'live', 'AI_PROVIDER': 'anthropic', 'AI_MODEL': self.g.SONNET_5_5,
            'AI_INPUT_RATE': '2', 'AI_OUTPUT_RATE': '10', 'AI_CACHED_RATE': '0.20'})
        settings.enable(); self.addCleanup(settings.disable)
        environment = patch.dict(os.environ, sq.PRICE_SETTINGS)
        environment.start(); self.addCleanup(environment.stop)
        fixture = batch.frozen_inputs()['batch']; self.original = batch.original_bytes()
        self.fields = word_v3.inspect(self.original)['fields']
        self.config = self.g.configuration(self.fields)
        self.plan = batch.compiled_plan({'batch': fixture}, self.fields)
        self.assertEqual([len(p['field_ids']) for p in self.plan['parts']], [100, 1])
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name); (self.folder / 'case').mkdir()
        (self.folder / 'case/form.docx').write_bytes(self.original)

    def record(self, plan, wire):
        paths = {'batch-plan.json': plan, 'compiled-child-request.json': wire}
        for name, value in paths.items():
            (self.folder / name).write_text(json.dumps(value))
        return {'evidence': {name: hashlib.sha256((self.folder / name).read_bytes()).hexdigest()
                             for name in paths}}

    def test_both_actual_children_reconstruct_their_full_source_and_individual_quote(self):
        for ordinal in (1, 2):
            wire = self.b.request(self.plan, ordinal)
            manifest = self.record(self.plan, wire)
            compiled, quote, kind = self.read(self.folder, manifest, wire, self.config)
            self.assertEqual(compiled['wire'], wire)
            self.assertEqual(kind, 'ordinary_batch_child')
            self.assertEqual(quote, Decimal(self.plan['parts'][ordinal - 1]['maximum_cost']))
            self.assertEqual(len(compiled['asked']), 101)
            self.assertEqual(len(json.loads(wire['messages'][0]['content'])['requested_field_ids']),
                             100 if ordinal == 1 else 1)

    def test_single_request_retains_its_original_complete_compiler_and_price(self):
        fields = self.fields[:2]; notes = 'The patient reports mild nausea.'
        config = self.g.configuration(fields)
        wire = self.r.compile_request(notes, fields, config)['wire']
        compiled, quote, kind = self.read(self.folder, {'evidence': {}}, wire, config)
        self.assertEqual(compiled['wire'], wire)
        self.assertEqual(quote, self.r.maximum_cost(notes, fields, config))
        self.assertEqual(kind, 'ordinary_single')

    def test_unlisted_or_changed_plan_and_child_are_not_actual_evidence(self):
        wire = self.b.request(self.plan, 1)
        for changed in ('batch-plan.json', 'compiled-child-request.json'):
            manifest = self.record(self.plan, wire)
            with self.subTest(changed=changed), self.assertRaises((AssertionError, KeyError)):
                manifest['evidence'].pop(changed)
                self.read(self.folder, manifest, wire, self.config)
            manifest = self.record(self.plan, wire)
            with (self.folder / changed).open('a') as output: output.write(' ')
            with self.subTest(changed=changed, bytes=True), self.assertRaises(AssertionError):
                self.read(self.folder, manifest, wire, self.config)

    def test_rehashed_plan_cannot_change_source_binding_child_digest_or_charge(self):
        wire = self.b.request(self.plan, 1)
        mutants = [
            ('original_sha256', '0' * 64), ('mapping_sha256', '0' * 64),
            ('notes_sha256', '0' * 64), ('notes', 'Unrelated encounter.'),
            ('patient_default_context', 'forged-token'),
        ]
        for key, value in mutants:
            plan = copy.deepcopy(self.plan); plan[key] = value
            manifest = self.record(plan, wire)
            with self.subTest(key=key), self.assertRaises(AssertionError):
                self.read(self.folder, manifest, wire, self.config)
        for key, value in [('request_sha256', '0' * 64), ('input_token_bound', 1),
                           ('maximum_cost', '0'), ('maximum_charge', '0')]:
            plan = copy.deepcopy(self.plan); plan['parts'][0][key] = value
            manifest = self.record(plan, wire)
            with self.subTest(part_key=key), self.assertRaises(AssertionError):
                self.read(self.folder, manifest, wire, self.config)

    def test_full_101_field_batch_cannot_be_mislabelled_as_one_ordinary_send(self):
        from django.core.exceptions import ValidationError
        wire = self.b.request(self.plan, 1)
        with self.assertRaises(ValidationError):
            self.read(self.folder, {'evidence': {}}, wire, self.config)
