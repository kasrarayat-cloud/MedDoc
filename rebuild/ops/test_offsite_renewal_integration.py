"""Offline composition: original account evidence -> prepaid ticket -> complete audit -> installed v2 policy."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import automatic_offsite as engine, offsite_allocation as allocation
    from . import offsite_renewal as renewal, offsite_account_audit as collector
    from . import install_offsite_policy as installer
except ImportError:
    import automatic_offsite as engine
    import offsite_allocation as allocation
    import offsite_renewal as renewal
    import offsite_account_audit as collector
    import install_offsite_policy as installer


class MetadataFixture:
    def __init__(self, credential, ticket, clock):
        self.ticket = ticket
        self.requests = self.reserved_response_bytes = self.received_response_bytes = 0

    def authorize(self):
        self.requests += 1
        self.reserved_response_bytes += 131072
        return {'application_key_id': 'readonly-fixture', 'capabilities': ['listBuckets', 'listFiles'],
                'unrestricted_buckets': True, 'unrestricted_prefix': True, 'list_keys_performed': False}

    def request(self, endpoint, params):
        self.requests += 1
        self.reserved_response_bytes += collector.RESPONSE_LIMITS[endpoint] + 65536
        target, other = self.ticket['bucket_id'], 'f' * 24
        if endpoint == 'b2_list_buckets':
            return {'buckets': [{'bucketId': bucket, 'accountId': self.ticket['account_id'],
                                 'bucketType': 'allPrivate'} for bucket in (target, other)]}
        if endpoint == 'b2_list_unfinished_large_files':
            return {'files': [], 'nextFileId': None}
        if endpoint == 'b2_list_file_versions':
            bucket = params['bucketId']
            return {'files': [{'fileId': bucket, 'bucketId': bucket, 'action': 'upload',
                               'fileName': self.ticket['prefix'] + 'synthetic' if bucket == target else 'unrelated-synthetic',
                               'contentLength': 180 if bucket == target else 900}],
                    'nextFileName': None, 'nextFileId': None}
        raise AssertionError('Unapproved fixture endpoint')


class RenewalIntegrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.secrets, self.state = self.root / 'secrets', self.root / 'state'
        self.evidence, self.records = self.root / 'account-evidence', self.root / 'installation-evidence'
        for folder in (self.secrets, self.state, self.evidence, self.records): folder.mkdir(mode=0o700)
        for target, name, value in (
            (engine, 'STATE', self.state), (engine, 'POLICY', self.secrets / 'offsite-policy.json'),
            (engine.offsite, 'CONFIG_PARENT', self.secrets),
            (allocation, 'ROOT', self.root), (allocation, 'CONTRACT', self.secrets / 'offsite-allocation.json'),
            (allocation, 'EVIDENCE_ROOT', self.evidence), (allocation, 'LEDGER', self.state / 'budget.json'),
            (allocation, 'HELPER_PATH', self.root / 'absent-old-helper.py'),
            (renewal, 'STATE', self.state / 'renewal'), (installer.base, 'EVIDENCE', self.records)):
            guard = patch.object(target, name, value); guard.start(); self.addCleanup(guard.stop)
        for relative in allocation.SOURCES:
            path = self.root / relative; path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic reviewed source ' + relative)
        self.original_at = datetime(2026, 9, 20, 20, tzinfo=timezone.utc)
        self.commit = 'a' * 40
        self.original = self.evidence / 'original'; self.original.mkdir(mode=0o700)
        engine.atomic(allocation.LEDGER, dict(version=1, day='2026-09-20', requests=422, download_bytes=98_474_544))
        policy = dict(version=1, approved=False, approval_reference='Original fixture observation',
            observed_at=self.original_at.isoformat(), valid_until=None, bucket_id='e'*24, prefix=engine.offsite.PREFIX,
            account_storage_limit_bytes=10_000_000_000, account_storage_used_bytes_at_observation=144,
            scope_storage_bytes_at_observation=144, scope_storage_ceiling_bytes=1_000_000_000,
            exclusive_scope_allocation_confirmed=False, exclusive_daily_budgets_confirmed=False,
            daily_download_budget_bytes=100_000_000, daily_request_budget=500, max_run_seconds=900, max_local_age_hours=30)
        bucket = dict(bucket_id='e'*24, bucket_type='allPrivate', is_quillmd_bucket=True,
            retained_upload_versions=44, retained_version_bytes=144, quillmd_scope_bytes=144,
            version_start_markers=0, unfinished_uploads=0, inventory_sha256='b'*64)
        scan = dict(buckets=[bucket], complete_account_total=True, unfinished_part_bytes=0,
                    completed_version_bytes=144, account_total_bytes=144, quillmd_scope_bytes=144)
        audit = dict(status='verified_over_observed_interval', stable_over_two_scans=True, complete_account_total=True,
            future_budget_guarantee=False, account_total_bytes=144, quillmd_scope_bytes=144,
            scans=[dict(copy.deepcopy(scan), started_at=(self.original_at-timedelta(seconds=2)).isoformat(),
                        completed_at=(self.original_at-timedelta(seconds=1)).isoformat()),
                   dict(copy.deepcopy(scan), started_at=(self.original_at-timedelta(seconds=1)).isoformat(),
                        completed_at=self.original_at.isoformat())])
        caps = dict(storage_cap_display='10 GB', storage_spend_cap_display='$0.00', download_cap_display='1 GB',
                    download_spend_cap_display='$0.00', class_b_daily_cap=2500, class_c_daily_cap=2500)
        updated = dict(policy_candidate=policy, provider_caps_observation=caps,
            account_audit=dict(source_sha256='c'*64, fully_paginated=True, matching_scans=2, key_inventory_complete=False,
                future_budget_guarantee=False, observed_end=self.original_at.isoformat(), observed_start=audit['scans'][0]['started_at'],
                buckets=1, retained_versions=44, inventory_sha256='b'*64, account_storage_bytes=144,
                scope_storage_bytes=144, unfinished_uploads=0, unfinished_part_bytes=0),
            audit_cleanup=dict(fresh_authorization_http_status=401, runtime_fresh_authorization_http_status=200,
                               runtime_exact_scope_verified=True))
        hashes = {}
        for name, value in (('account-audit.json', audit), ('operating-evidence.json', updated)):
            raw = installer.encoded(value); engine.backup.write_private(self.original / name, raw)
            hashes[name] = installer.digest(raw)
        provenance = dict(vps_performed_account_scans=False, original_windows_byte_hash_independently_verified=False,
            original_windows_bytes_available=False, semantic_consistency_verified=True,
            original_windows_artifact_sha256_reported='c'*64, local_artifact_hashes=hashes)
        engine.backup.write_private(self.original / 'provenance.json', installer.encoded(provenance))
        installer.install_pair(self.original, self.commit, execute=True, at=self.original_at+timedelta(minutes=1))
        self.original_policy = engine.POLICY.read_bytes()
        self.original_artifacts = {p.name: p.read_bytes() for p in self.original.iterdir()}
        self.audit_at = datetime(2026, 9, 21, 1, tzinfo=timezone.utc)
        issued = renewal.issue_ticket(self.audit_at.isoformat(), (self.audit_at+timedelta(hours=1)).isoformat(),
                                      self.commit, at=self.original_at+timedelta(hours=2))
        self.ticket_raw = Path(issued['ticket_path']).read_bytes()
        self.ticket = json.loads(self.ticket_raw)
        self.ticks = 0
        def clock():
            self.ticks += 1
            return self.audit_at + timedelta(milliseconds=self.ticks)
        self.audit = collector.collect({'application_key_id': 'synthetic-audit', 'application_key': 'synthetic-only'},
                                       self.ticket_raw, transport_factory=MetadataFixture, clock=clock)
        self.returned = self.root / 'returned.json'
        engine.backup.write_private(self.returned, installer.encoded(self.audit))

    def test_real_pair_publication_renews_from_complete_account_audit_without_refund_or_old_fact_rewrite(self):
        before = allocation.LEDGER.read_bytes()
        result = renewal.import_result(self.returned, self.ticket['ticket_id'], self.commit,
                                       at=self.audit_at+timedelta(minutes=1))
        self.assertTrue(result['success'])
        limits = engine.policy(engine.POLICY, self.audit_at+timedelta(minutes=2))
        contract = json.loads(allocation.CONTRACT.read_bytes())
        self.assertEqual(contract['version'], 2)
        self.assertIsNone(contract['windows_source_sha256'])
        self.assertEqual(limits['account_storage_used_bytes_at_observation'], 1080)
        self.assertEqual(limits['scope_storage_bytes_at_observation'], 180)
        self.assertEqual(contract['non_scope_observed_bytes'], 900)
        self.assertEqual(contract['account_reserved_bound_bytes'], 1_000_000_900)
        self.assertEqual(limits['observed_at'], self.audit['scans'][-1]['completed_at'])
        self.assertEqual(engine.timestamp(limits['valid_until']) - engine.timestamp(limits['observed_at']), timedelta(hours=24))
        self.assertEqual(allocation.LEDGER.read_bytes(), before)
        self.assertEqual({p.name: p.read_bytes() for p in self.original.iterdir()}, self.original_artifacts)
        self.assertTrue(any(p.read_bytes() == self.original_policy for p in self.records.glob('*-previous-policy.json')))
        self.assertEqual(renewal.renewal_status(self.audit_at+timedelta(minutes=2))['state'], 'installed')
        self.assertFalse((self.secrets / 'offsite-policy-installing.json').exists())

    def test_tampered_totals_retain_old_valid_policy_and_prepaid_reservation(self):
        before_policy, before_contract, before_ledger = engine.POLICY.read_bytes(), allocation.CONTRACT.read_bytes(), allocation.LEDGER.read_bytes()
        self.audit['account_total_bytes'] += 1
        self.returned.write_bytes(installer.encoded(self.audit))
        with self.assertRaises(renewal.Refusal):
            renewal.import_result(self.returned, self.ticket['ticket_id'], self.commit, at=self.audit_at+timedelta(minutes=1))
        self.assertEqual((engine.POLICY.read_bytes(), allocation.CONTRACT.read_bytes(), allocation.LEDGER.read_bytes()),
                         (before_policy, before_contract, before_ledger))
        state = renewal.renewal_status(self.audit_at+timedelta(minutes=2))
        self.assertEqual(state['state'], 'failed')
        self.assertEqual(state['last_successful_observation_at'], self.original_at.isoformat())
        self.assertEqual((renewal.STATE / (self.ticket['ticket_id']+'.returned.json')).read_bytes(), self.returned.read_bytes())

    def test_partial_v2_publication_retains_fail_closed_marker_and_every_reservation(self):
        original_policy, before_ledger = engine.POLICY.read_bytes(), allocation.LEDGER.read_bytes()
        original_replace = installer.os.replace
        def replace(source, destination):
            if Path(destination) == engine.POLICY:
                raise OSError('fixture: second policy publication failed')
            return original_replace(source, destination)
        with patch.object(installer.os, 'replace', side_effect=replace), self.assertRaises(renewal.Refusal):
            renewal.import_result(self.returned, self.ticket['ticket_id'], self.commit, at=self.audit_at+timedelta(minutes=1))
        self.assertEqual(engine.POLICY.read_bytes(), original_policy)
        self.assertEqual(json.loads(allocation.CONTRACT.read_bytes())['version'], 2)
        self.assertEqual(allocation.LEDGER.read_bytes(), before_ledger)
        self.assertTrue((self.secrets / 'offsite-policy-installing.json').exists())
        with self.assertRaises(engine.Refusal):
            engine.policy(engine.POLICY, self.audit_at+timedelta(minutes=2))
        self.assertEqual(json.loads((renewal.STATE / 'status.json').read_bytes())['state'], 'failed')
        self.assertEqual({p.name: p.read_bytes() for p in self.original.iterdir()}, self.original_artifacts)
