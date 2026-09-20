"""Offline publication faults; account audit semantics are covered by test_offsite_allocation."""
import copy
from datetime import timedelta
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

try:
    from . import install_offsite_policy as installer
    from . import test_automatic_offsite as fixtures
except ImportError:
    import install_offsite_policy as installer
    import test_automatic_offsite as fixtures


class PolicyInstallationTests(TestCase):
    setUp = fixtures.AutomaticOffsiteTests.setUp

    def prepare(self):
        evidence_root = self.root / 'account-evidence'
        evidence_root.mkdir(mode=0o700)
        directory = evidence_root / 'observation'
        directory.mkdir(mode=0o700)
        records = self.root / 'installation-evidence'
        records.mkdir(mode=0o700)
        policy_path, contract_path = self.secrets / 'offsite-policy.json', self.secrets / 'offsite-allocation.json'
        ledger = self.state / 'budget.json'
        helper_parent = self.root / 'historical-helper'
        helper_parent.mkdir(mode=0o700)
        original = dict(version=1, day='2026-09-20', requests=296, download_bytes=68_551_020)
        installer.engine.atomic(ledger, original)
        audit = {'scans': [{'completed_at': self.at.isoformat()}],
                 'account_total_bytes': 10000, 'quillmd_scope_bytes': 10000}
        updated = {'policy_candidate': copy.deepcopy(self.policy), 'account_audit': {'source_sha256': 'a'*64}}
        for name, value in (('account-audit.json', audit), ('operating-evidence.json', updated), ('provenance.json', {})):
            installer.engine.backup.write_private(directory / name, installer.encoded(value))
        for target, name, value in (
            (installer.allocation, 'EVIDENCE_ROOT', evidence_root),
            (installer.allocation, 'CONTRACT', contract_path), (installer.allocation, 'LEDGER', ledger),
            (installer.allocation, 'HELPER_PATH', helper_parent / 'inventory_approved_prefix.py'),
            (installer.allocation, 'SOURCES', ()), (installer.engine.offsite, 'CONFIG_PARENT', self.secrets),
            (installer.engine, 'POLICY', policy_path), (installer.engine, 'STATE', self.state),
            (installer.base, 'EVIDENCE', records)):
            guard = patch.object(target, name, value)
            guard.start()
            self.addCleanup(guard.stop)
        return directory, policy_path, contract_path, ledger, records

    def original_helper(self):
        original = b'# Offline fixture of the prior raw requests helper.\nraise SystemExit("fixture")\n'
        installer.engine.backup.write_private(installer.allocation.HELPER_PATH, original)
        guard = patch.object(installer.allocation, 'HELPER_ORIGINAL_SHA256', installer.digest(original))
        guard.start()
        self.addCleanup(guard.stop)
        return original

    def test_plan_has_no_policy_candidates_receipts_or_journal_mutation(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        before = ledger.read_bytes()
        result = installer.install_pair(directory, 'f'*40, at=self.at + timedelta(hours=2))
        self.assertTrue(result['plan_prepared'])
        self.assertEqual(list(self.secrets.iterdir()), [self.key])
        self.assertEqual(list(records.iterdir()), [])
        self.assertEqual(ledger.read_bytes(), before)
        self.assertFalse(policy_path.exists() or contract_path.exists())

    def test_expiry_is_original_observation_plus_24_hours_not_install_time(self):
        directory, *_ = self.prepare()
        limits, contract = installer.candidate_pair(directory)
        self.assertEqual(limits['valid_until'], (self.at + timedelta(hours=24)).isoformat())
        self.assertEqual(contract['observed_at'], self.at.isoformat())
        with self.assertRaisesRegex(RuntimeError, 'expired'):
            installer.install_pair(directory, 'f'*40, execute=True, at=self.at + timedelta(hours=25))

    def test_invalid_candidate_preserves_both_old_files_and_ledger(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        installer.engine.backup.write_private(policy_path, b'{"prior_policy":true}')
        installer.engine.backup.write_private(contract_path, b'{"prior_allocation":true}')
        before = [path.read_bytes() for path in (policy_path, contract_path, ledger)]
        with patch.object(installer.allocation, 'validate', side_effect=ValueError('invalid evidence')):
            with self.assertRaises(ValueError):
                installer.install_pair(directory, 'f'*40, execute=True, at=self.at)
        self.assertEqual([path.read_bytes() for path in (policy_path, contract_path, ledger)], before)
        self.assertFalse((self.secrets / 'offsite-policy-installing.json').exists())
        self.assertEqual(len(list(records.glob('*-result.json'))), 1)
        self.assertEqual(len(list(records.glob('*-previous-*.json'))), 2)
        self.assertEqual(set(path.name for path in self.secrets.iterdir()),
                         {self.key.name, policy_path.name, contract_path.name})

    def test_success_revalidates_actual_pair_and_keeps_prior_reservations(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        before = ledger.read_bytes()
        with patch.object(installer.allocation, 'validate', return_value={}) as validate:
            result = installer.install_pair(directory, 'f'*40, execute=True, at=self.at)
        self.assertTrue(result['success'])
        self.assertTrue(result['shared_journal_unchanged'])
        self.assertEqual(ledger.read_bytes(), before)
        self.assertEqual(json.loads(contract_path.read_bytes())['policy_sha256'], installer.digest(policy_path.read_bytes()))
        self.assertGreaterEqual(validate.call_count, 3)
        self.assertFalse((self.secrets / 'offsite-policy-installing.json').exists())
        self.assertEqual(len(list(records.glob('*-intent.json'))), 1)
        self.assertEqual(len(list(records.glob('*-result.json'))), 1)

    def test_partial_publication_keeps_fail_closed_marker_and_failure_history(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        installer.engine.backup.write_private(policy_path, b'{"prior_policy":true}')
        installer.engine.backup.write_private(contract_path, b'{"prior_allocation":true}')
        original_replace = installer.os.replace
        def replace(source, destination):
            if Path(destination) == policy_path:
                raise OSError('injected second publication failure')
            return original_replace(source, destination)
        with patch.object(installer.allocation, 'validate', return_value={}), \
                patch.object(installer.os, 'replace', side_effect=replace), self.assertRaises(OSError):
            installer.install_pair(directory, 'f'*40, execute=True, at=self.at)
        self.assertTrue((self.secrets / 'offsite-policy-installing.json').exists())
        result = json.loads(next(records.glob('*-result.json')).read_bytes())
        self.assertFalse(result['success'])
        self.assertEqual(result['failed_stage'], 'publication')
        self.assertEqual(json.loads(ledger.read_bytes())['requests'], 296)
        with self.assertRaisesRegex(RuntimeError, 'Unfinished'):
            installer.install_pair(directory, 'f'*40, execute=True, at=self.at)

    def test_noncanonical_evidence_path_and_symlink_are_rejected(self):
        directory, *_ = self.prepare()
        with self.assertRaises(RuntimeError):
            installer.candidate_pair(self.root)
        alias = directory.parent / 'alias'
        alias.symlink_to(directory)
        with self.assertRaises(RuntimeError):
            installer.candidate_pair(alias)

    def test_failed_candidate_cleanup_is_recorded_as_failure(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        original_unlink = Path.unlink
        def unlink(path, *args, **kwargs):
            if path.parent == self.secrets and path.name.startswith('policy-'):
                raise OSError('injected candidate cleanup failure')
            return original_unlink(path, *args, **kwargs)
        with patch.object(installer.allocation, 'validate', side_effect=ValueError('invalid evidence')), \
                patch.object(Path, 'unlink', unlink), self.assertRaisesRegex(RuntimeError, 'cleanup failed'):
            installer.install_pair(directory, 'f'*40, execute=True, at=self.at)
        result = json.loads(next(records.glob('*-result.json')).read_bytes())
        self.assertFalse(result['success'])
        self.assertTrue(result['cleanup_failed'])
        self.assertEqual(result['failed_stage'], 'candidate_validation')
        self.assertFalse(policy_path.exists() or contract_path.exists())

    def test_original_candidate_observation_disagreement_refused(self):
        directory, *_ = self.prepare()
        path = directory / 'operating-evidence.json'
        value = json.loads(path.read_bytes())
        value['policy_candidate']['observed_at'] = (self.at + timedelta(hours=1)).isoformat()
        installer.engine.atomic(path, value)
        with self.assertRaisesRegex(RuntimeError, 'disagree'):
            installer.candidate_pair(directory)

    def test_known_raw_helper_archived_and_retired_before_any_candidate_validation(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        original = self.original_helper()
        def validate(*args, **kwargs):
            self.assertEqual(installer.allocation.HELPER_PATH.read_bytes(), installer.allocation.RETIRED_HELPER_STUB)
            self.assertEqual(next(records.glob('retired-prefix-inventory-original-*.txt')).read_bytes(), original)
            return {}
        with patch.object(installer.allocation, 'validate', side_effect=validate):
            result = installer.install_pair(directory, 'f'*40, execute=True, at=self.at)
        self.assertTrue(result['success'])
        self.assertEqual(result['legacy_helper']['state'], 'retired')
        self.assertEqual(installer.allocation.HELPER_PATH.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(list(records.glob('retired-prefix-inventory-original-*.txt'))), 1)
        # A repeat reads and verifies the same source-history artifact; it does not rewrite it.
        archive = next(records.glob('retired-prefix-inventory-original-*.txt'))
        before = archive.stat().st_mtime_ns
        with patch.object(installer.allocation, 'validate', return_value={}):
            installer.install_pair(directory, 'f'*40, execute=True, at=self.at)
        self.assertEqual(archive.stat().st_mtime_ns, before)

    def test_unknown_helper_source_refuses_without_policy_publication_or_replacement(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        self.original_helper()
        installer.allocation.HELPER_PATH.write_bytes(b'unrecognized changed implementation')
        before = installer.allocation.HELPER_PATH.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'Unrecognized'):
            installer.install_pair(directory, 'f'*40, at=self.at)
        with patch.object(installer.allocation, 'validate') as validate, \
                self.assertRaisesRegex(RuntimeError, 'Unrecognized'):
            installer.install_pair(directory, 'f'*40, execute=True, at=self.at)
        validate.assert_not_called()
        self.assertEqual(installer.allocation.HELPER_PATH.read_bytes(), before)
        self.assertFalse(policy_path.exists() or contract_path.exists())
        result = json.loads(next(records.glob('*-result.json')).read_bytes())
        self.assertEqual(result['failed_stage'], 'legacy_helper_retirement')
        self.assertFalse(result['success'])

    def test_helper_plan_never_retires_or_archives_source(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        original = self.original_helper()
        result = installer.install_pair(directory, 'f'*40, at=self.at)
        self.assertEqual(result['legacy_helper']['state'], 'requires_retirement')
        self.assertEqual(installer.allocation.HELPER_PATH.read_bytes(), original)
        self.assertEqual(list(records.iterdir()), [])

    def test_retired_stub_with_lost_or_corrupt_history_is_not_silently_accepted(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        installer.engine.backup.write_private(installer.allocation.HELPER_PATH, installer.allocation.RETIRED_HELPER_STUB)
        with self.assertRaisesRegex(RuntimeError, 'missing its original'):
            installer.install_pair(directory, 'f'*40, execute=True, at=self.at)
        archive = records / ('retired-prefix-inventory-original-' + installer.allocation.HELPER_ORIGINAL_SHA256 + '.txt')
        installer.engine.backup.write_private(archive, b'not original')
        with self.assertRaisesRegex(RuntimeError, 'does not match'):
            installer.install_pair(directory, 'f'*40, execute=True, at=self.at)

    def test_unsafe_helper_metadata_refuses_before_replacement(self):
        directory, policy_path, contract_path, ledger, records = self.prepare()
        original = self.original_helper()
        installer.allocation.HELPER_PATH.chmod(0o644)
        with self.assertRaises(Exception):
            installer.install_pair(directory, 'f'*40, execute=True, at=self.at)
        self.assertEqual(installer.allocation.HELPER_PATH.read_bytes(), original)
        self.assertFalse(policy_path.exists() or contract_path.exists())
