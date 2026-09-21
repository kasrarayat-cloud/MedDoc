"""Provider-free boundaries for the generation-only preserving activation."""
import copy
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ops import source_module

ROOT = Path(__file__).resolve().parents[2]
c = source_module.load('typed_voice_generation_activation_tested', ROOT / 'scripts/activate-typed-voice-generation.py')


class GenerationOnlyActivationTests(unittest.TestCase):
    def test_pinned_baseline_and_qualified_drivers(self):
        self.assertEqual(c.BASELINE, 'b6b40b02c3dea69f88f4b2b0438535865f4dc32e')
        self.assertEqual(c.sha((ROOT / c.DRIVER).read_bytes()), c.DRIVER_SHA256)
        self.assertEqual(c.sha((ROOT / c.ASSET_READER).read_bytes()), c.ASSET_READER_SHA256)
        for module in (c.driver, c.driver.a, c.driver.b):
            self.assertEqual(module.BASELINE, c.BASELINE)
            self.assertEqual(module.RUNNING_RELEASE, c.BASELINE)
            self.assertEqual(module.SELF, c.SELF)
        self.assertIs(c.driver.a.load, c.load)
        self.assertIs(c.driver.b.rows, c.driver.full_rows)

    def test_only_exact_code_only_runtime_change_is_allowed(self):
        c.driver.validate_changed(c.ALLOWED)
        for bad in ('rebuild/static/app.css', 'rebuild/core/jobs.py', 'rebuild/core/migrations/0018_other.py',
                    'scripts/activate-typed-voice.py', 'rebuild/ops/offsite_backup.py'):
            with self.subTest(path=bad), self.assertRaises(RuntimeError):
                c.driver.validate_changed(c.ALLOWED | {bad})
        for missing in c.ALLOWED:
            with self.subTest(missing=missing), self.assertRaises(RuntimeError):
                c.driver.validate_changed(c.ALLOWED - {missing})

    def test_full_current_rows_include_new_calls_and_financial_history(self):
        old = SimpleNamespace(tables=Mock(return_value=['core_usage', 'core_providerreceipt', 'core_job', 'core_wallet']),
                              fingerprints=Mock(return_value={'current': 'new calls preserved'}))
        self.assertEqual(c.driver.full_rows(old), {'current': 'new calls preserved'})
        old.fingerprints.assert_called_once_with(old.tables.return_value)

    def receipt(self):
        return {'complete': True, 'target': c.BASELINE, 'stage': 'complete', 'provider_calls': 0,
                'existing_hashed_assets_retained': True, 'static_delta_source_bound': True,
                'static_transition': {'old_immutable_assets_retained': True,
                                     'after': {'app.css': {'sha256': 'css', 'size': 4}}}}

    def test_exact_completed_static_receipt_and_original_bytes_required(self):
        receipt = self.receipt()
        data = json.dumps(receipt).encode()
        with patch.object(c, 'STATIC_RECEIPT_SHA256', c.sha(data)):
            self.assertEqual(c.validate_static_receipt(data), receipt['static_transition']['after'])
            with self.assertRaises(RuntimeError):
                c.validate_static_receipt(data + b'\n')
        for key, value in [('complete', False), ('target', 'a' * 40), ('provider_calls', 1),
                           ('existing_hashed_assets_retained', False), ('static_delta_source_bound', False)]:
            changed = dict(receipt, **{key: value})
            encoded = json.dumps(changed).encode()
            with self.subTest(key=key), patch.object(c, 'STATIC_RECEIPT_SHA256', c.sha(encoded)), self.assertRaises(RuntimeError):
                c.validate_static_receipt(encoded)

    def test_static_receipt_inventory_and_current_source_must_agree(self):
        data = b'public css'
        expected = {'app.css': {'sha256': c.sha(data), 'size': len(data), 'inode': 10}}
        word = SimpleNamespace(checked_file=Mock(return_value=b'receipt'))
        identity = SimpleNamespace(static_sources=Mock(return_value={'app.css': SimpleNamespace(read_bytes=Mock(return_value=data))}))
        with patch.object(c, 'validate_static_receipt', return_value=expected), patch.object(c.assets, 'static_inventory', return_value=copy.deepcopy(expected)):
            self.assertEqual(c.current_static(identity, word), expected)
            identity.static_sources.return_value['app.css'].read_bytes.return_value = b'changed'
            with self.assertRaises(RuntimeError):
                c.current_static(identity, word)
        changed = copy.deepcopy(expected)
        changed['app.css']['inode'] += 1
        with patch.object(c, 'validate_static_receipt', return_value=expected), patch.object(c.assets, 'static_inventory', return_value=changed), self.assertRaises(RuntimeError):
            c.current_static(identity, word)

    def test_reused_loader_is_replaced_only_for_static_inventory(self):
        marker = object()
        module = SimpleNamespace(static_inventory=marker, other=marker)
        with patch.object(c, '_qualified_load', return_value=module) as original:
            self.assertIs(c.load('old', 'qualified.py', 'a' * 40), module)
            original.assert_called_once_with('old', 'qualified.py', 'a' * 40)
        self.assertIs(module.static_inventory, c.current_static)
        self.assertIs(module.other, marker)
        untouched = SimpleNamespace(static_inventory=marker)
        with patch.object(c, '_qualified_load', return_value=untouched):
            self.assertIs(c.load('identity', 'qualified.py', 'a' * 40).static_inventory, marker)

    def test_no_static_collection_or_migration_or_provider_action_in_reused_main(self):
        source = inspect.getsource(c.driver.main)
        self.assertNotIn('collectstatic', source)
        self.assertNotIn('collect_static', source)
        self.assertNotIn("management('migrate'", source)
        self.assertIn('scripts/check-citation.sh', source)
        self.assertIn("identity.verify_live(args.target, storage)", source)
        self.assertEqual(source.count('unchanged(baseline,'), 2)


if __name__ == '__main__':
    unittest.main()
