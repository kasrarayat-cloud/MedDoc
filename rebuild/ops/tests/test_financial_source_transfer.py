"""Pure metadata/refusal controls; synthetic receipts are not paid reconstruction."""
import contextlib
import copy
import io
import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch


SOURCE = Path(__file__).resolve().parents[1] / 'fixtures/financial_source_transfer.source'
ORIGINAL = SOURCE.with_name('current_wire_price_witness.source')
M = runpy.run_path(str(SOURCE), run_name='financial_source_transfer')


class FinancialTransferPreparation(unittest.TestCase):
    def test_default_prepared_never_reads_git_django_evidence_or_network(self):
        import sys
        output = io.StringIO()
        with patch.object(sys, 'argv', [str(SOURCE)]), contextlib.redirect_stdout(output), \
                patch('subprocess.check_output', side_effect=AssertionError('No Git read')) as git, \
                patch('socket.socket.connect', side_effect=AssertionError('No connection')) as network:
            runpy.run_path(str(SOURCE), run_name='__main__')
        self.assertEqual(json.loads(output.getvalue()), {'status': 'prepared',
            'new_provider_requests': 0, 'database_queries': 0,
            'fingerprints_changed': False, 'clinical_qualification': False})
        self.assertEqual((git.call_count, network.call_count), (0, 0))

    def test_derivative_changes_exactly_one_assertion_and_original_remains_immutable(self):
        original = ORIGINAL.read_bytes()
        for group in M['PAID_GROUPS']:
            changed, diff = M['derivative'](original, group['paid_revision'])
            self.assertEqual(M['digest'](original), M['WITNESS_SHA'])
            replacement = M['PROVENANCE'].replace('args.revision', repr(group['paid_revision']))
            self.assertEqual(changed.decode().replace(replacement, M['PROVENANCE'], 1).encode(), original)
            self.assertEqual(len([line for line in diff.splitlines() if line.startswith('- ') ]), 1)
            self.assertEqual(len([line for line in diff.splitlines() if line.startswith('+ ') ]), 1)
            self.assertIn("assert compiled['wire']==wire", changed.decode())
            self.assertIn("assert row['configured_pricing_fingerprint_at_enqueue']==config['pricing_version']", changed.decode())
            self.assertNotEqual(changed, original)

    def test_changed_witness_and_short_or_foreign_paid_revision_refuse(self):
        for value in ['short', 'G' * 40, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                M['derivative'](ORIGINAL.read_bytes(), value)
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            M['derivative'](ORIGINAL.read_bytes() + b'\n', 'a' * 40)

    def test_source_inventory_requires_complete_compiler_context_and_four_exact_inputs(self):
        namespace = M['source_identity'].__globals__
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder); source = parent / 'synthetic'; (source / 'rebuild').mkdir(parents=True)
            for name in (*M['MODULES'], *M['INPUTS'], *M['EXTRA']):
                path = source / 'rebuild' / name; path.parent.mkdir(exist_ok=True)
                path.write_text('value = 1\n' if name.endswith('.py') else 'synthetic input')
            (source / 'rebuild/core/v3_field_relations.py').write_text(
                'def compile_request():\n return 1\ndef maximum_cost():\n return 2\n')
            def git(argv, **kwargs):
                return '' if 'status' in argv else ('b' * 40 if 'HEAD^{tree}' in argv else 'a' * 40)
            with patch.dict(namespace, WORKTREES=parent), patch('subprocess.check_output', side_effect=git):
                proof = M['source_identity'](source, 'a' * 40)
                self.assertEqual(set(proof['files']), set((*M['MODULES'], *M['INPUTS'], *M['EXTRA'])))
                self.assertEqual(set(proof['unchanged_compiler_context_inputs']['exact_inputs']), set(M['INPUTS']))
                (source / 'rebuild/core/reviewed_procedure_source.py').unlink()
                with self.assertRaisesRegex(ValueError, 'Missing guarded dependency'):
                    M['source_identity'](source, 'a' * 40)

    def test_prepare_refuses_unset_current_source_changed_membership_and_reviewed_voice_credit(self):
        bindings = [
            {'format': M['FORMAT'], 'status': 'prepared'},
            {'format': M['FORMAT'], 'status': 'prospectively_bound', 'witness_sha256': M['WITNESS_SHA'], 'new_revision': None},
            {'format': M['FORMAT'], 'status': 'prospectively_bound', 'witness_sha256': M['WITNESS_SHA'],
             'new_revision': 'a' * 40, 'groups': M['PAID_GROUPS'][:1], 'reviewed_voice': M['VOICE_PENDING']},
            {'format': M['FORMAT'], 'status': 'prospectively_bound', 'witness_sha256': M['WITNESS_SHA'],
             'new_revision': 'a' * 40, 'groups': M['PAID_GROUPS'],
             'reviewed_voice': {**M['VOICE_PENDING'], 'live_replay_qualified': True}},
        ]
        with patch('subprocess.check_output', side_effect=AssertionError('Must refuse before Git')) as git:
            for binding in bindings:
                with self.subTest(binding=binding), self.assertRaises(ValueError):
                    M['prepare'](binding, ORIGINAL.read_bytes(), Path('/unused'))
        self.assertEqual(git.call_count, 0)

    def test_bound_synthetic_preparation_emits_only_old_original_and_one_assertion_new_commands(self):
        namespace = M['prepare'].__globals__
        current = {'commit': 'b' * 40, 'tree': 'b' * 40, 'files': {'synthetic': {}},
                   'unchanged_compiler_context_inputs': {'synthetic proof': 'equal'}}
        identities = {group['paid_revision']: {**copy.deepcopy(current), 'commit': group['paid_revision']}
                      for group in M['PAID_GROUPS']}
        binding = {'format': M['FORMAT'], 'status': 'prospectively_bound', 'witness_sha256': M['WITNESS_SHA'],
            'new_source': '/synthetic/new', 'new_revision': current['commit'], 'new_source_tree': current['tree'],
            'new_files': current['files'], 'old_sources': {key: '/synthetic/' + key for key in identities},
            'old_files': identities, 'groups': M['PAID_GROUPS'], 'reviewed_voice': M['VOICE_PENDING']}
        def identity(path, commit):
            return current if commit == current['commit'] else identities[commit]
        def envelope(row):
            return [{'attempt': int(number), 'kind': row['kind']} for number in row['attempts']]
        with tempfile.TemporaryDirectory() as folder, patch.dict(namespace, OWNED=Path(folder),
                source_identity=identity, evidence_envelope=envelope):
            output = Path(folder) / 'new-preparation'
            result = M['prepare'](binding, ORIGINAL.read_bytes(), output)
            self.assertEqual((result['status'], len(result['groups'])), ('prepared', 2))
            self.assertEqual((output / 'original-witness.py').read_bytes(), ORIGINAL.read_bytes())
            for group in result['groups']:
                self.assertEqual(group['execution'], 'NOT RUN')
                self.assertEqual(group['commands']['old'][1], str(output / 'original-witness.py'))
                self.assertNotEqual(group['commands']['old'][1], group['commands']['new'][1])
            changed = copy.deepcopy(current)
            changed['unchanged_compiler_context_inputs']['synthetic proof'] = 'different'
            namespace['source_identity'] = lambda path, commit: changed if commit == current['commit'] else identities[commit]
            with self.assertRaisesRegex(ValueError, 'AST or exact parser/package inputs changed'):
                M['prepare'](binding, ORIGINAL.read_bytes(), Path(folder) / 'refused')
            self.assertFalse((Path(folder) / 'refused').exists())


class FinancialTransferAdjudication(unittest.TestCase):
    def setUp(self):
        self.group = {'old_source': self.identity('a'), 'new_source': self.identity('b'),
            'derivative_sha256': 'd' * 64, 'commands': {'old': ['old synthetic command'], 'new': ['new synthetic command']},
            'paid_evidence': [{'attempt': 2, 'kind': 'ordinary_single',
                **{name: 'c' * 64 for name in ('manifest_sha256', 'request_file_sha256',
                     'recorded_http_body_sha256', 'audit_sha256')}}]}
        record = self.group['paid_evidence'][0]
        row = dict.fromkeys(M['ROW_KEYS'], 'synthetic')
        row.update({key: value for key, value in record.items() if key != 'kind'})
        row.update(request_kind='ordinary_single', compiled_wire_dict_equals_actual_http_body=True,
                   all_audit_checks_pass=True, invoice_reconciled=False)
        self.old = self.report('old', row); self.new = self.report('new', row)

    def identity(self, letter):
        return {'commit': letter * 40, 'tree': letter * 40,
                'files': {name: {'bytes_sha256': 'c' * 64} for name in M['WITNESSED_MODULES']}}

    def report(self, side, row):
        identity = self.group[side + '_source']
        return {'source_head': identity['commit'], 'source_tree': identity['tree'],
            'witness_source_sha256': M['WITNESS_SHA'] if side == 'old' else self.group['derivative_sha256'],
            'source_bytes': {name: 'c' * 64 for name in M['WITNESSED_MODULES']},
            'current_actual_provider_rows': [copy.deepcopy(row)],
            'pure_batch_child_price_witnesses': [{'pure_context_fixture_not_human_review': True}],
            'network_connect_attempts': [], 'new_provider_requests': 0, 'database_queries': 0,
            'scanner_fingerprints_changed': False, 'clinical_qualification': False,
            'context_live_provider_qualified': False, 'batch_live_provider_qualified': False}

    def receipts(self, old=None, new=None):
        receipts = {}
        for side, report in [('old', old or self.old), ('new', new or self.new)]:
            raw = json.dumps(report)
            receipts[side] = {'argv': self.group['commands'][side], 'child_exit': 0, 'supervisor_exit': 0,
                'timed_out': False, 'reaped': True, 'source_unchanged': True,
                'result_bytes': raw, 'result_sha256': M['digest'](raw.encode()),
                'script_sha256': report['witness_source_sha256']}
        return receipts

    def test_full_synthetic_report_equality_keeps_original_paid_identity_and_pending_claims(self):
        result = M['adjudicate'](self.group, self.old, self.new, self.receipts())
        self.assertTrue(result['financial_reconstruction_equal'])
        self.assertNotEqual(result['paid_source'], result['reconstruction_source'])
        self.assertFalse(result['clinical_qualification'])
        self.assertFalse(result['fingerprints_changed'])
        self.assertFalse(result['invoice_reconciled'])
        self.assertIn('PENDING', result['guarded_dependency_adjudication'])

    def test_each_changed_sdk_quote_cost_settlement_and_context_control_refuses(self):
        for key in ('request_id', 'model_sent', 'model_returned', 'max_tokens', 'quoted_wire_bytes',
                    'provider_maximum_quote', 'provider_calculated_cost', 'settled_retail_charge', 'stored_customer_limit'):
            changed = copy.deepcopy(self.new); changed['current_actual_provider_rows'][0][key] = 'wrong'
            with self.subTest(key=key), self.assertRaises(ValueError):
                M['adjudicate'](self.group, self.old, changed, self.receipts(new=changed))
        changed = copy.deepcopy(self.new); changed['pure_batch_child_price_witnesses'] = []
        with self.assertRaises(ValueError):
            M['adjudicate'](self.group, self.old, changed, self.receipts(new=changed))

    def test_failed_unknown_unreaped_changed_or_foreign_execution_receipts_refuse(self):
        for key, value in [('child_exit', 1), ('supervisor_exit', 124), ('timed_out', True),
                           ('reaped', False), ('source_unchanged', False), ('argv', ['foreign']),
                           ('result_sha256', '0' * 64), ('script_sha256', '0' * 64)]:
            receipts = self.receipts(); receipts['new'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                M['adjudicate'](self.group, self.old, self.new, receipts)

    def test_missing_duplicate_or_falsely_relabelled_paid_evidence_refuses(self):
        for value in [[], self.new['current_actual_provider_rows'] * 2]:
            changed = copy.deepcopy(self.new); changed['current_actual_provider_rows'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                M['adjudicate'](self.group, self.old, changed, self.receipts(new=changed))
        for key, value in [('manifest_sha256', '0' * 64), ('request_kind', 'ordinary_batch_child'),
                           ('compiled_wire_dict_equals_actual_http_body', False), ('invoice_reconciled', True)]:
            changed = copy.deepcopy(self.new); changed['current_actual_provider_rows'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                M['adjudicate'](self.group, self.old, changed, self.receipts(new=changed))

    def test_missing_guarded_bytes_or_live_semantic_claims_refuse_even_equal_reports(self):
        for key in M['WITNESSED_MODULES']:
            changed = copy.deepcopy(self.new); changed['source_bytes'].pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                M['adjudicate'](self.group, self.old, changed, self.receipts(new=changed))
        for key in ['clinical_qualification', 'context_live_provider_qualified', 'batch_live_provider_qualified']:
            changed = copy.deepcopy(self.new); changed[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                M['adjudicate'](self.group, self.old, changed, self.receipts(new=changed))
