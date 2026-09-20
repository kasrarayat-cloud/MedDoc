import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from ops import offsite_allocation as allocation


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / 'evidence' / 'observation'
        self.directory.mkdir(parents=True, mode=0o700)
        self.directory.parent.chmod(0o700)
        self.policy = self.root / 'policy.json'
        self.contract = self.root / 'allocation.json'
        self.ledger = self.root / 'budget.json'
        self.write(self.ledger, dict(version=1, day=allocation.HISTORY_DAY, **allocation.HISTORY_FLOOR))
        self.at = datetime(2026, 9, 20, 21, tzinfo=timezone.utc)
        start = self.at - timedelta(hours=1)
        self.limits = dict(observed_at=start.isoformat(), valid_until=(start + timedelta(hours=24)).isoformat(),
                           bucket_id='bucket', account_storage_used_bytes_at_observation=144,
                           scope_storage_bytes_at_observation=144, scope_storage_ceiling_bytes=1_000_000_000,
                           account_storage_limit_bytes=10_000_000_000, daily_download_budget_bytes=100_000_000,
                           daily_request_budget=500, max_run_seconds=900, max_local_age_hours=30)
        bucket = dict(bucket_id='bucket', bucket_type='allPrivate', is_quillmd_bucket=True,
                      inventory_sha256='b'*64,
                      retained_upload_versions=44, retained_version_bytes=144, quillmd_scope_bytes=144,
                      version_start_markers=0, unfinished_uploads=0)
        scan = dict(buckets=[bucket], complete_account_total=True, unfinished_part_bytes=0,
                    completed_version_bytes=144, account_total_bytes=144, quillmd_scope_bytes=144)
        self.audit = dict(status='verified_over_observed_interval', stable_over_two_scans=True,
                          complete_account_total=True, future_budget_guarantee=False, account_total_bytes=144,
                          quillmd_scope_bytes=144, scans=[dict(scan, started_at=(start-timedelta(seconds=2)).isoformat(),
                          completed_at=(start-timedelta(seconds=1)).isoformat()),
                          dict(copy.deepcopy(scan), started_at=(start-timedelta(seconds=1)).isoformat(), completed_at=start.isoformat())])
        self.updated = dict(account_audit=dict(source_sha256='a'*64, fully_paginated=True, matching_scans=2,
                            key_inventory_complete=False, future_budget_guarantee=False, observed_end=start.isoformat(),
                            observed_start=self.audit['scans'][0]['started_at'], buckets=1, retained_versions=44,
                            inventory_sha256='b'*64,
                            account_storage_bytes=144, scope_storage_bytes=144, unfinished_uploads=0, unfinished_part_bytes=0),
                            audit_cleanup=dict(fresh_authorization_http_status=401, runtime_fresh_authorization_http_status=200,
                                               runtime_exact_scope_verified=True),
                            provider_caps_observation=dict(storage_cap_display='10 GB', storage_spend_cap_display='$0.00',
                            download_cap_display='1 GB', download_spend_cap_display='$0.00', class_b_daily_cap=2500, class_c_daily_cap=2500))
        self.item = dict(version=1, status='active', observed_at=start.isoformat(), valid_until=self.limits['valid_until'],
                         evidence_directory=str(self.directory), windows_source_sha256='a'*64, control_sources={},
                         known_consumers=allocation.CONSUMERS, administrative_constraints=allocation.CONSTRAINTS,
                         non_scope_observed_bytes=0, account_reserved_bound_bytes=1_000_000_000,
                         renewal_requires_desktop=True, key_inventory_complete=False, future_budget_guarantee=False)
        for relative in allocation.SOURCES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture code')
            self.item['control_sources'][relative] = allocation.digest(path.read_bytes())
        for name, value in (('ROOT', self.root), ('CONTRACT', self.contract), ('EVIDENCE_ROOT', self.directory.parent),
                            ('LEDGER', self.ledger), ('HELPER_PATH', self.root/'historical-inventory.py')):
            patch = mock.patch.object(allocation, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.save()

    def write(self, path, value):
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return allocation.digest(path.read_bytes())

    def save(self):
        self.item['policy_sha256'] = self.write(self.policy, self.limits)
        self.item['audit'] = dict(name='account-audit.json', local_sha256=self.write(self.directory/'account-audit.json', self.audit))
        self.item['operating_evidence'] = dict(name='operating-evidence.json', local_sha256=self.write(self.directory/'operating-evidence.json', self.updated))
        provenance = dict(vps_performed_account_scans=False, original_windows_byte_hash_independently_verified=False,
                          original_windows_bytes_available=False, semantic_consistency_verified=True,
                          original_windows_artifact_sha256_reported='a'*64,
                          local_artifact_hashes={self.item[k]['name']: self.item[k]['local_sha256'] for k in ('audit', 'operating_evidence')})
        self.item['provenance'] = dict(name='provenance.json', local_sha256=self.write(self.directory/'provenance.json', provenance))
        self.write(self.contract, self.item)

    def validate(self):
        return allocation.validate(self.limits, self.policy, self.at)

    def test_verified_finite_conditional_bound(self):
        result = self.validate()
        self.assertEqual(result['account_reserved_bound_bytes'], 1_000_000_000)
        self.assertTrue(result['renewal_requires_desktop'])

    def test_rejects_unsupported_claims_and_stale_or_overlong_evidence(self):
        for key, value in [('key_inventory_complete', True), ('future_budget_guarantee', True),
                           ('status', 'invalidated'), ('known_consumers', []), ('administrative_constraints', []),
                           ('account_reserved_bound_bytes', 144), ('windows_source_sha256', 'b'*64)]:
            with self.subTest(key=key):
                original = self.item[key]
                self.item[key] = value
                self.save()
                with self.assertRaises(ValueError): self.validate()
                self.item[key] = original
        self.save()
        with self.assertRaises(ValueError):
            allocation.validate(self.limits, self.policy, self.at + timedelta(days=1))
        self.limits['valid_until'] = self.item['valid_until'] = (self.at+timedelta(days=2)).isoformat()
        self.save()
        with self.assertRaises(ValueError): self.validate()

    def test_code_policy_and_artifact_drift_refuse(self):
        for path in (self.root/allocation.SOURCES[0], self.policy, self.directory/'account-audit.json'):
            raw = path.read_bytes()
            path.write_bytes(raw+b' ')
            with self.assertRaises(ValueError): self.validate()
            path.write_bytes(raw)

    def test_stale_caller_limits_and_conflicting_inventory_are_refused(self):
        old = dict(self.limits)
        self.limits['daily_request_budget'] = 100
        self.save()
        with self.assertRaises(ValueError): allocation.validate(old, self.policy, self.at)
        self.updated['account_audit']['inventory_sha256'] = 'c'*64
        self.save()
        with self.assertRaises(ValueError): self.validate()

    def test_incomplete_inventory_does_not_become_account_total(self):
        for mutation in ('unfinished', 'missing', 'nonmatching', 'bucket'):
            with self.subTest(mutation=mutation):
                before = copy.deepcopy(self.audit)
                if mutation == 'unfinished': self.audit['scans'][0]['unfinished_part_bytes'] = 1
                if mutation == 'missing': self.audit['complete_account_total'] = False
                if mutation == 'nonmatching': self.audit['scans'][1]['buckets'][0]['retained_version_bytes'] = 145
                if mutation == 'bucket': self.audit['scans'][0]['buckets'][0]['bucket_id'] = 'other'
                self.save()
                with self.assertRaises(ValueError): self.validate()
                self.audit = before

    def test_protected_contract_required(self):
        self.contract.chmod(0o644)
        with self.assertRaises(RuntimeError): self.validate()

    def test_historical_unbudgeted_helper_must_be_retired_before_admission(self):
        helper = self.root/'historical-inventory.py'
        helper.write_bytes(b'import requests\nrequests.get("https://api.backblazeb2.com")\n')
        helper.chmod(0o600)
        with self.assertRaises(ValueError): self.validate()
        helper.write_bytes(allocation.RETIRED_HELPER_STUB)
        self.validate()

    def test_historical_reservations_cannot_disappear_on_new_day(self):
        self.write(self.ledger, dict(version=2, day='2026-09-21', requests=0, download_bytes=0,
                                    days={allocation.HISTORY_DAY: allocation.HISTORY_FLOOR}))
        self.validate()
        self.write(self.ledger, dict(version=2, day='2026-09-21', requests=0, download_bytes=0, days={}))
        with self.assertRaises(ValueError): self.validate()

    def test_non_scope_bytes_increase_conditional_bound(self):
        other = dict(bucket_id='other', bucket_type='allPrivate', is_quillmd_bucket=False,
                     retained_upload_versions=2, retained_version_bytes=900, quillmd_scope_bytes=0,
                     version_start_markers=0, unfinished_uploads=0)
        for scan in self.audit['scans']:
            scan['buckets'].append(copy.deepcopy(other))
            scan['completed_version_bytes'] = scan['account_total_bytes'] = 1044
        self.audit['account_total_bytes'] = self.limits['account_storage_used_bytes_at_observation'] = 1044
        self.updated['account_audit'].update(account_storage_bytes=1044, buckets=2, retained_versions=46)
        self.item.update(non_scope_observed_bytes=900, account_reserved_bound_bytes=1_000_000_900)
        self.save()
        self.assertEqual(self.validate()['account_reserved_bound_bytes'], 1_000_000_900)


if __name__ == '__main__':
    unittest.main()
