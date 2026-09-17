"""Regression checks for demonstrated deployment-gate counterexamples."""
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/update-private-beta.py'
SPEC = importlib.util.spec_from_file_location('private_beta_updater_under_test', SCRIPT)
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)


class UpdateGuardTests(unittest.TestCase):
    def test_unrelated_complete_report_is_not_restore_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            app = Path(directory) / 'rebuild'
            folder = app / '.runtime/restore-checks'
            folder.mkdir(parents=True)
            report = folder / 'unrelated-activation.json'
            report.write_text(json.dumps({'complete': True}))
            report.chmod(0o600)
            with patch.object(updater, 'APP', app), patch.object(updater, 'output') as command:
                with self.assertRaisesRegex(RuntimeError, 'Verified encrypted backup'):
                    updater.validate_restore_report(report)
                command.assert_not_called()

    def test_payment_refund_webhook_changes_are_in_preservation_fingerprints(self):
        data = {'core_wallet': b'{"id":"synthetic-wallet"}\n', 'core_payment': b'',
                'core_refund': b'', 'core_webhookevent': b''}
        def copy(command):
            name = re.search(r'FROM ([a-z_]+) t ORDER BY', command[-1]).group(1)
            return data[name]
        with patch.object(updater, 'output', return_value='\n'.join(data)), \
                patch.object(updater.subprocess, 'check_output', side_effect=copy):
            before = updater.database_fingerprints()
            self.assertEqual(set(before), set(data))
            for table in ('core_payment', 'core_refund', 'core_webhookevent'):
                data[table] = b'{"id":"synthetic-new-record"}\n'
                after = updater.database_fingerprints()
                self.assertNotEqual(before[table], after[table])
                data[table] = b''


if __name__ == '__main__':
    unittest.main()
