"""Regression checks for demonstrated deployment-gate counterexamples."""
import importlib.util
import copy
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
    def protected_fixture(self, root):
        expected = {'name': '/synthetic-protected-caddy', 'id': 'synthetic-container',
                    'image': 'synthetic-image', 'running': True, 'mounts': [
                        {'source': '/synthetic/config', 'destination': '/config'},
                        {'source': '/synthetic/data', 'destination': '/data'},
                        {'source': '/synthetic/Caddyfile', 'destination': '/etc/caddy/Caddyfile'}]}
        folder = root / 'docs/rebuild'
        folder.mkdir(parents=True)
        (folder / 'activation-baseline.json').write_text(json.dumps({'containers': [expected]}))
        return {'Id': expected['id'], 'Image': expected['image'], 'State': {'Running': True},
                'Mounts': [{'Source': m['source'], 'Destination': m['destination']} for m in expected['mounts']]}

    def test_protected_mount_reordering_passes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            actual = self.protected_fixture(root)
            actual['Mounts'] = actual['Mounts'][1:] + actual['Mounts'][:1]
            with patch.object(updater, 'ROOT', root), \
                    patch.object(updater, 'output', return_value=json.dumps([actual])):
                self.assertEqual(updater.protected(), 1)

    def test_protected_changed_missing_or_duplicate_mount_refuses(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = self.protected_fixture(root)
            for mutation in ('source', 'destination', 'missing', 'duplicate'):
                actual = copy.deepcopy(baseline)
                if mutation == 'source':
                    actual['Mounts'][0]['Source'] = '/synthetic/wrong-config'
                elif mutation == 'destination':
                    actual['Mounts'][0]['Destination'] = '/wrong-config'
                elif mutation == 'missing':
                    actual['Mounts'].pop()
                else:
                    actual['Mounts'].append(copy.deepcopy(actual['Mounts'][0]))
                with self.subTest(mutation=mutation), patch.object(updater, 'ROOT', root), \
                        patch.object(updater, 'output', return_value=json.dumps([actual])):
                    with self.assertRaisesRegex(RuntimeError, 'protected mount changed'):
                        updater.protected()

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
