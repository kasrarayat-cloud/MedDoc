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
    TARGET_BYTES, OTHER_BYTES = 180, 900

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
                               'contentLength': self.TARGET_BYTES if bucket == target else self.OTHER_BYTES}],
                    'nextFileName': None, 'nextFileId': None}
        raise AssertionError('Unapproved fixture endpoint')


class LaterMetadataFixture(MetadataFixture):
    """A later account observation: the QuillMD prefix grew and the unrelated bucket shrank."""
    TARGET_BYTES, OTHER_BYTES = 540, 700


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

    def renew_from_renewed_policy(self, issued_at, audit_at):
        """First import (v1 -> v2), then a second ticket, audit and returned file against that v2 policy."""
        self.assertTrue(renewal.import_result(self.returned, self.ticket['ticket_id'], self.commit,
                                              at=self.audit_at+timedelta(minutes=1))['success'])
        first = dict(policy=engine.POLICY.read_bytes(), contract=allocation.CONTRACT.read_bytes())
        first['directory'] = Path(json.loads(first['contract'])['evidence_directory'])
        first['evidence'] = {p.name: p.read_bytes() for p in first['directory'].iterdir()}
        first['limits'] = json.loads(first['policy'])
        first['history'] = {p: p.read_bytes() for root in (self.records, renewal.STATE)
                            for p in root.rglob('*') if p.is_file() and p.name != 'status.json'}
        ledger_before_ticket = json.loads(allocation.LEDGER.read_bytes())
        issued = renewal.issue_ticket(audit_at.isoformat(), (audit_at+timedelta(hours=1)).isoformat(),
                                      self.commit, at=issued_at)
        ticket_raw = Path(issued['ticket_path']).read_bytes()
        ticket = json.loads(ticket_raw)
        ledger = json.loads(allocation.LEDGER.read_bytes())
        day = audit_at.strftime('%Y-%m-%d')
        prior = ledger_before_ticket['days'].get(day, {'requests': 0, 'download_bytes': 0})
        self.assertEqual(ledger['days'][day], {'requests': prior['requests']+20, 'download_bytes': prior['download_bytes']+8388608})
        self.assertEqual({d: v for d, v in ledger['days'].items() if d != day},
                         {d: v for d, v in ledger_before_ticket['days'].items() if d != day})
        self.assertEqual(ledger['external_reservations'][:-1], ledger_before_ticket['external_reservations'])
        ticks = [0]
        def clock():
            ticks[0] += 1
            return audit_at + timedelta(milliseconds=ticks[0])
        audit = collector.collect({'application_key_id': 'synthetic-audit', 'application_key': 'synthetic-only'},
                                  ticket_raw, transport_factory=LaterMetadataFixture, clock=clock)
        returned = self.root / 'returned-again.json'
        # Reversed keys, 3-space indent and CRLF: no plain JSON round trip reproduces these bytes.
        engine.backup.write_private(returned, json.dumps(dict(reversed(list(audit.items()))), indent=3)
                                    .replace('\n', '\r\n').encode())
        return first, ticket, ticket_raw, audit, returned

    def assert_renewed_from_renewed_policy(self, first, ticket, ticket_raw, audit, returned, import_at):
        def snapshot():
            return {str(p): p.read_bytes() for root in (self.secrets, self.state, self.evidence, self.records)
                    for p in sorted(root.rglob('*')) if p.is_file()}
        # While the second ticket awaits, the consumed first one refuses on its own identity.
        before = snapshot()
        with self.assertRaises(renewal.Refusal) as stale:
            renewal.import_result(returned, self.ticket['ticket_id'], self.commit, at=import_at)
        self.assertEqual(stale.exception.code, 'ticket_invalid')
        self.assertEqual(snapshot(), before)
        waiting = json.loads((renewal.STATE / 'status.json').read_bytes())
        self.assertEqual((waiting['state'], waiting['ticket_id']), ('awaiting_external_audit', ticket['ticket_id']))
        ledger_before = allocation.LEDGER.read_bytes()
        issued = {p: p.read_bytes() for p in renewal.STATE.iterdir() if p.is_file() and p.name != 'status.json'}
        result = renewal.import_result(returned, ticket['ticket_id'], self.commit, at=import_at)
        self.assertTrue(result['success'])
        self.assertEqual({p: p.read_bytes() if p.exists() else None for p in issued}, issued)
        self.assertEqual((renewal.STATE / (ticket['ticket_id']+'.installed.json')).read_bytes(), installer.encoded(result))
        # Expiry is the LAST scan's completion + 24 h: not the first scan, the ticket window or the import.
        observed = engine.timestamp(audit['scans'][-1]['completed_at'])
        self.assertNotEqual(observed, engine.timestamp(audit['scans'][0]['completed_at']))
        self.assertNotEqual(observed + timedelta(hours=24), import_at + timedelta(hours=24))
        self.assertEqual((engine.timestamp(result['observed_at']), engine.timestamp(result['valid_until'])),
                         (observed, observed + timedelta(hours=24)))
        limits = engine.policy(engine.POLICY, import_at)
        self.assertEqual((engine.timestamp(limits['observed_at']), engine.timestamp(limits['valid_until'])),
                         (observed, observed + timedelta(hours=24)))
        self.assertEqual((limits['account_storage_used_bytes_at_observation'], limits['scope_storage_bytes_at_observation']),
                         (1240, 540))
        self.assertEqual({k: v for k, v in limits.items() if k not in (
            'observed_at', 'valid_until', 'account_storage_used_bytes_at_observation', 'scope_storage_bytes_at_observation')},
            {k: v for k, v in first['limits'].items() if k not in (
            'observed_at', 'valid_until', 'account_storage_used_bytes_at_observation', 'scope_storage_bytes_at_observation')})
        engine.policy(engine.POLICY, observed + timedelta(hours=24) - timedelta(microseconds=1))
        with self.assertRaises(engine.Refusal) as expired:
            engine.policy(engine.POLICY, observed + timedelta(hours=24))
        self.assertEqual(expired.exception.code, 'policy_expired')
        # The allocation contract now describes the second observation, in its own evidence directory.
        contract, previous = json.loads(allocation.CONTRACT.read_bytes()), json.loads(first['contract'])
        directory = allocation.EVIDENCE_ROOT / ('renewal-' + ticket['ticket_id'])
        self.assertEqual((contract['version'], contract['status'], contract['evidence_directory']), (2, 'active', str(directory)))
        self.assertNotEqual(contract['evidence_directory'], previous['evidence_directory'])
        self.assertEqual(contract['policy_sha256'], installer.digest(engine.POLICY.read_bytes()))
        self.assertEqual((engine.timestamp(contract['observed_at']), engine.timestamp(contract['valid_until'])),
                         (observed, observed + timedelta(hours=24)))
        self.assertEqual((contract['non_scope_observed_bytes'], contract['account_reserved_bound_bytes']), (700, 1_000_000_700))
        self.assertIsNone(contract['windows_source_sha256'])
        self.assertEqual(contract['control_sources'], previous['control_sources'])
        for field in ('audit', 'operating_evidence', 'provenance'):
            self.assertEqual(installer.digest((directory / contract[field]['name']).read_bytes()), contract[field]['local_sha256'])
        self.assertEqual((directory / 'account-audit.json').read_bytes(), returned.read_bytes())
        self.assertEqual((directory / 'ticket.json').read_bytes(), ticket_raw)
        # Caps are a historical observation: every renewal carries the ORIGINAL one, never a rewritten copy.
        original_caps = json.loads(self.original_artifacts['operating-evidence.json'])['provider_caps_observation']
        for evidence in (first['evidence']['operating-evidence.json'], (directory / 'operating-evidence.json').read_bytes()):
            self.assertEqual(json.loads(evidence)['provider_caps_observation'], original_caps)
        allocation.validate(limits, engine.POLICY, import_at)
        # Import never charges, refunds or re-dates: the ledger is byte-identical, and history is kept.
        self.assertEqual(allocation.LEDGER.read_bytes(), ledger_before)
        self.assertEqual({p.name: p.read_bytes() for p in first['directory'].iterdir()}, first['evidence'])
        self.assertEqual({p.name: p.read_bytes() for p in self.original.iterdir()}, self.original_artifacts)
        self.assertTrue(any(p.read_bytes() == first['policy'] for p in self.records.glob('*-previous-policy.json')))
        self.assertTrue(any(p.read_bytes() == first['contract'] for p in self.records.glob('*-previous-allocation.json')))
        self.assertTrue(any(p.read_bytes() == self.original_policy for p in self.records.glob('*-previous-policy.json')))
        self.assertEqual({p: p.read_bytes() if p.exists() else None for p in first['history']}, first['history'])
        self.assertEqual((renewal.STATE / (ticket['ticket_id']+'.returned.json')).read_bytes(), returned.read_bytes())
        self.assertFalse((self.secrets / 'offsite-policy-installing.json').exists())
        status = renewal.renewal_status(import_at)
        self.assertEqual((status['state'], status['ticket_id'], status['reason_code']), ('installed', ticket['ticket_id'], None))
        self.assertEqual(engine.timestamp(status['last_successful_observation_at']), observed)
        # A duplicate import — the same file, a re-delivered copy, or the consumed first ticket — refuses
        # before it can touch anything, and does not flip the installed renewal to failed.
        copy_path = self.root / 'redelivered.json'
        engine.backup.write_private(copy_path, returned.read_bytes())
        before = snapshot()
        for path, ticket_id in ((returned, ticket['ticket_id']), (copy_path, ticket['ticket_id']),
                                (self.returned, self.ticket['ticket_id']), (returned, self.ticket['ticket_id']),
                                (self.returned, ticket['ticket_id'])):
            with self.assertRaises(renewal.Refusal) as duplicate:
                renewal.import_result(path, ticket_id, self.commit, at=import_at+timedelta(minutes=1))
            self.assertEqual(duplicate.exception.code, 'ticket_invalid')
        self.assertEqual(snapshot(), before)
        self.assertEqual(renewal.renewal_status(import_at+timedelta(minutes=2))['state'], 'installed')

    def test_renewal_after_the_renewed_policy_expired_installs_from_the_later_scan(self):
        """The 2026-09-22 production path: the v2 policy lapsed, then a new ticket renewed it.

        The ticket is issued late on one UTC day for a window after midnight, so the import runs on a
        later day than the ledger last recorded; a normalise-and-write-back would change its bytes.
        """
        expiry = engine.timestamp(self.audit['scans'][-1]['completed_at']) + timedelta(hours=24)
        issued_at, audit_at = expiry + timedelta(hours=22, minutes=30), expiry + timedelta(hours=23, minutes=30)
        self.assertNotEqual(issued_at.date(), (audit_at+timedelta(minutes=45)).date())
        first, ticket, ticket_raw, audit, returned = self.renew_from_renewed_policy(issued_at, audit_at)
        with self.assertRaises(engine.Refusal) as lapsed:
            engine.policy(engine.POLICY, issued_at)
        self.assertEqual(lapsed.exception.code, 'policy_expired')
        self.assert_renewed_from_renewed_policy(first, ticket, ticket_raw, audit, returned, audit_at+timedelta(minutes=45))

    def test_renewal_before_the_renewed_policy_expires_replaces_it_from_the_later_scan(self):
        expiry = engine.timestamp(self.audit['scans'][-1]['completed_at']) + timedelta(hours=24)
        issued_at, audit_at = expiry - timedelta(hours=4), expiry - timedelta(hours=3)
        first, ticket, ticket_raw, audit, returned = self.renew_from_renewed_policy(issued_at, audit_at)
        engine.policy(engine.POLICY, issued_at)
        self.assert_renewed_from_renewed_policy(first, ticket, ticket_raw, audit, returned, audit_at+timedelta(minutes=45))
        self.assertGreater(engine.timestamp(json.loads(engine.POLICY.read_bytes())['valid_until']), expiry)

    def test_a_renewed_policy_whose_evidence_no_longer_holds_refuses_renewal_and_moves_nothing(self):
        """Renewing FROM a v2 policy first re-validates it: refunded or rewritten evidence refuses."""
        self.assertTrue(renewal.import_result(self.returned, self.ticket['ticket_id'], self.commit,
                                              at=self.audit_at+timedelta(minutes=1))['success'])
        at = self.audit_at + timedelta(minutes=2)
        directory = Path(json.loads(allocation.CONTRACT.read_bytes())['evidence_directory'])
        fields = {'account-audit.json': 'audit', 'operating-evidence.json': 'operating_evidence', 'provenance.json': 'provenance'}

        def rewrite(name, change):
            """Change one artifact and re-hash it into provenance and the contract, so only its CONTENT is wrong."""
            def tamper():
                value = json.loads((directory / name).read_bytes()); change(value)
                raw = installer.encoded(value); (directory / name).write_bytes(raw)
                contract = json.loads(allocation.CONTRACT.read_bytes())
                contract[fields[name]]['local_sha256'] = installer.digest(raw)
                if name != 'provenance.json':
                    provenance = json.loads((directory / 'provenance.json').read_bytes())
                    provenance['local_artifact_hashes'][name] = installer.digest(raw)
                    if name == 'account-audit.json':
                        provenance['source_artifact_sha256'] = installer.digest(raw)
                    raw = installer.encoded(provenance); (directory / 'provenance.json').write_bytes(raw)
                    contract['provenance']['local_sha256'] = installer.digest(raw)
                allocation.CONTRACT.write_bytes(installer.encoded(contract))
            return tamper

        def refund():
            ledger = json.loads(allocation.LEDGER.read_bytes())
            reference = self.ticket['reservation_reference']
            [entry] = [row for row in ledger['external_reservations'] if row['reference'] == reference]
            ledger['external_reservations'].remove(entry)
            for day in entry['charged_days']:
                ledger['days'][day]['requests'] -= entry['requests']
                ledger['days'][day]['download_bytes'] -= entry['download_bytes']
            engine.atomic(allocation.LEDGER, ledger)

        tampers = {'the first ticket reservation refunded': refund,
                   'an audit below the collector call floor': rewrite('account-audit.json', lambda a: a.update(api_calls=6)),
                   'an audit bound to another ticket': rewrite('account-audit.json', lambda a: a.update(ticket_sha256='f'*64)),
                   'caps no longer marked historical': rewrite('operating-evidence.json', lambda e: e.update(caps_are_historical=False)),
                   'provenance claiming a VPS scan': rewrite('provenance.json', lambda p: p.update(vps_performed_account_scans=True))}
        watched = [engine.POLICY, allocation.CONTRACT, allocation.LEDGER, *sorted(directory.iterdir())]
        engine.policy(engine.POLICY, at)
        for label, tamper in tampers.items():
            with self.subTest(label):
                original = {p: p.read_bytes() for p in watched}
                tamper()
                tampered = ({p: p.read_bytes() for p in watched}, sorted(renewal.STATE.iterdir()),
                            (renewal.STATE / 'status.json').read_bytes())
                self.assertNotEqual(tampered[0], original)
                with self.assertRaises(engine.Refusal) as refused:
                    engine.policy(engine.POLICY, at)
                self.assertEqual(refused.exception.code, 'policy_invalid')
                start = at + timedelta(hours=1)
                with self.assertRaises(engine.Refusal) as refused:
                    renewal.issue_ticket(start.isoformat(), (start+timedelta(hours=1)).isoformat(), self.commit, at=at)
                self.assertEqual(refused.exception.code, 'policy_invalid')
                self.assertEqual(({p: p.read_bytes() for p in watched}, sorted(renewal.STATE.iterdir()),
                                  (renewal.STATE / 'status.json').read_bytes()), tampered)
                for path, raw in original.items():
                    path.write_bytes(raw)
                engine.policy(engine.POLICY, at)  # the original bytes validate again: the tamper alone refused
