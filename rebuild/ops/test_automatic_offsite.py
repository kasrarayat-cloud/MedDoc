"""Deterministic fault injection only: these tests do not contact B2 or restore a live database."""
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet

try:
    from . import automatic_offsite as auto
except ImportError:
    import automatic_offsite as auto


class MemoryB2:
    def __init__(self):
        self.rows, self.payloads, self.writes, self.reads = [], {}, [], []
        self.fail_after_write = False
        self.fail_before_write = False
        self.corrupt_read = False
        self.events = []

    def authorize(self):
        return {'provider_verified': True, 'evidence': 'isolated synthetic fake'}

    def close(self):
        pass

    def inventory(self):
        return copy.deepcopy(self.rows)

    def put(self, name, payload):
        if self.fail_before_write:
            self.fail_before_write = False
            raise auto.Refusal('transport_failed')
        file_id = str(len(self.writes) + 1)
        row = {'fileName': name, 'fileId': file_id, 'contentLength': len(payload), 'action': 'upload'}
        self.rows.insert(0, row)
        self.payloads[file_id] = payload
        self.writes.append(name)
        self.events.append(('put', name))
        if self.fail_after_write:
            self.fail_after_write = False
            raise auto.Refusal('transport_failed')
        return row

    def get(self, row, size):
        self.reads.append(row['fileName'])
        self.events.append(('get', row['fileName']))
        value = self.payloads[row['fileId']]
        if self.corrupt_read:
            return b'corrupt readback'
        auto.check(len(value) == size, 'remote_corrupt')
        return value


class AutomaticOffsiteTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / 'state'
        self.state.mkdir(mode=0o700)
        self.secrets = self.root / 'secrets'
        self.secrets.mkdir(mode=0o700)
        self.run_id = '20260920T180000Z-aabbccdd'
        self.at = datetime(2026, 9, 20, 18, 30, tzinfo=timezone.utc)
        self.cipher = Fernet(Fernet.generate_key())
        self.key = self.secrets / 'key'
        # Store the same generated Fernet key through an explicit fixture key.
        key = Fernet.generate_key()
        self.cipher = Fernet(key)
        auto.backup.write_private(self.key, key)
        plain = b'SYNTHETIC fixture database; not a real database backup'
        encrypted = self.cipher.encrypt(plain)
        self.manifest = {'format': 1, 'complete': True, 'database': 'quillmd_fresh', 'run_id': self.run_id,
                         'image_id': 'sha256:' + 'c' * 64, 'files': [],
                         'dump': {'sha256': auto.backup.digest(plain), 'size': len(plain),
                                  'cipher_sha256': auto.backup.digest(encrypted)}}
        self.objects = {'database.dump.fernet': encrypted,
                        'manifest.json.fernet': self.cipher.encrypt(json.dumps(self.manifest).encode())}
        self.policy = {'version': 1, 'approved': True, 'approval_reference': 'Synthetic fixture, not owner evidence',
                       'observed_at': self.at.isoformat(), 'valid_until': (self.at + timedelta(days=7)).isoformat(),
                       'bucket_id': 'e' * 24, 'prefix': auto.offsite.PREFIX,
                       'account_storage_limit_bytes': 10_000_000_000,
                       'account_storage_used_bytes_at_observation': 10000,
                       'scope_storage_bytes_at_observation': 10000,
                       'scope_storage_ceiling_bytes': 100_000_000,
                       'exclusive_scope_allocation_confirmed': True, 'exclusive_daily_budgets_confirmed': True,
                       'daily_download_budget_bytes': 100_000_000, 'daily_request_budget': 500,
                       'max_run_seconds': 300, 'max_local_age_hours': 30}
        self.config = {'bucket_id': 'e' * 24, 'bucket': 'synthetic-fixture', 'prefix': auto.offsite.PREFIX,
                       'endpoint': 'https://s3.us-west-004.backblazeb2.com',
                       'application_key_id': 'synthetic-key-id', 'application_key': 'synthetic-key-value'}
        self.remote = MemoryB2()

    def native_transport(self, config, budget):
        """Explicit offline injection: HTTP is mocked in every caller; bypass only the live-path guard."""
        transport = auto.NativeTransport(config, budget)
        guard = patch.object(transport, '_assert_live')
        guard.start()
        self.addCleanup(guard.stop)
        return transport

    def call(self, remote=None, limits=None):
        return auto.transfer(self.manifest, self.objects, self.cipher, remote or self.remote,
                             limits or self.policy, self.state)

    def policy_file(self, value=None):
        path = self.secrets / 'policy.json'
        auto.atomic(path, value or self.policy)
        return path

    def bundle(self):
        parent = self.root / 'backups'
        parent.mkdir(mode=0o700)
        directory = parent / self.run_id
        directory.mkdir(mode=0o700)
        (directory / 'objects').mkdir(mode=0o700)
        for name, payload in self.objects.items():
            auto.backup.write_private(directory / name, payload)
        return parent, directory

    def test_manifest_published_only_after_data_readback(self):
        result = self.call()
        self.assertEqual(result['object_count'], 2)
        self.assertTrue(result['ciphertext_sha256_verified'])
        self.assertEqual([event[0] for event in self.remote.events], ['put', 'get', 'put', 'get'])
        self.assertTrue(self.remote.events[2][1].endswith('manifest.json.fernet'))
        self.assertTrue(json.loads((self.state / 'active.json').read_text())['complete'])

    def test_failed_readback_does_not_publish_manifest(self):
        self.remote.corrupt_read = True
        with self.assertRaisesRegex(auto.Refusal, 'remote_corrupt'):
            self.call()
        self.assertEqual(len(self.remote.writes), 1)
        self.assertFalse(self.remote.writes[0].endswith('manifest.json.fernet'))
        self.assertFalse(json.loads((self.state / 'active.json').read_text())['complete'])

    def test_interruption_after_provider_write_before_journal_reuses_verified_object(self):
        self.remote.fail_after_write = True
        with self.assertRaisesRegex(auto.Refusal, 'transport_failed'):
            self.call()
        self.assertIsNotNone(json.loads((self.state / 'active.json').read_text())['pending'])
        result = self.call()
        self.assertEqual(len(self.remote.writes), 2)
        self.assertEqual(result['new_object_count'], 1)
        self.assertEqual(len(self.remote.rows), 2)

    def test_manifest_put_interruption_recovered_without_duplicate_complete_set(self):
        original = self.remote.put
        def put(name, payload):
            self.remote.fail_after_write = name.endswith('manifest.json.fernet')
            return original(name, payload)
        self.remote.put = put
        with self.assertRaisesRegex(auto.Refusal, 'transport_failed'):
            self.call()
        self.remote.put = original
        self.call()
        self.assertEqual(len(self.remote.writes), 2)
        self.assertEqual(sum(name.endswith('manifest.json.fernet') for name in self.remote.writes), 1)

    def test_uncertain_put_with_no_inventory_entry_is_not_blindly_repeated(self):
        self.remote.fail_before_write = True
        with self.assertRaisesRegex(auto.Refusal, 'transport_failed'):
            self.call()
        with self.assertRaisesRegex(auto.Refusal, 'remote_uncertain'):
            self.call()
        self.assertEqual(self.remote.writes, [])

    def test_retry_complete_set_performs_no_writes(self):
        self.call()
        result = self.call()
        self.assertEqual(result['new_object_count'], 0)
        self.assertEqual(len(self.remote.writes), 2)

    def test_published_manifest_with_missing_data_refuses_without_repair_put(self):
        self.call()
        self.remote.rows = [row for row in self.remote.rows if row['fileName'].endswith('manifest.json.fernet')]
        with self.assertRaisesRegex(auto.Refusal, 'remote_corrupt'):
            self.call()
        self.assertEqual(len(self.remote.writes), 2)

    def test_corrupt_or_hidden_existing_object_never_overwritten(self):
        self.call()
        row = next(row for row in self.remote.rows if row['fileName'].endswith('database.dump.fernet'))
        self.remote.payloads[row['fileId']] = b'corrupt'
        with self.assertRaisesRegex(auto.Refusal, 'remote_corrupt'):
            self.call()
        row['action'] = 'hide'
        with self.assertRaisesRegex(auto.Refusal, 'remote_corrupt'):
            self.call()
        self.assertEqual(len(self.remote.writes), 2)

    def test_capacity_counts_all_versions_including_unrelated_prefix_sets(self):
        self.remote.rows = [{'fileName': auto.offsite.PREFIX + 'prior/object', 'fileId': str(index),
                             'action': 'upload', 'contentLength': 10_000} for index in range(3)]
        with self.assertRaisesRegex(auto.Refusal, 'capacity_refused'):
            self.call(limits=dict(self.policy, scope_storage_ceiling_bytes=20_000))
        self.assertEqual(self.remote.writes, [])

    def test_capacity_exact_boundary_and_existing_bytes_not_recounted(self):
        total = sum(map(len, self.objects.values()))
        result = self.call(limits=dict(self.policy, scope_storage_ceiling_bytes=total))
        self.assertEqual(result['scope_stored_bytes_after'], total)
        self.call(limits=dict(self.policy, scope_storage_ceiling_bytes=total))
        self.assertEqual(len(self.remote.writes), 2)

    def test_wrong_key_and_unauthenticated_local_payload_refused_before_inventory(self):
        remote = Mock()
        for cipher, objects in [(Fernet(Fernet.generate_key()), self.objects),
                                (self.cipher, dict(self.objects, **{'database.dump.fernet': b'bad'}))]:
            with self.assertRaisesRegex(auto.Refusal, 'local_authentication_failed'):
                auto.transfer(self.manifest, objects, cipher, remote, self.policy, self.state)
        remote.inventory.assert_not_called()
        remote.put.assert_not_called()

    def test_concurrent_invocation_fails_without_replacing_holder_status(self):
        auto.atomic(self.state / 'status.json', {'version': 1, 'state': 'running', 'attempt': 'holder'})
        with auto.exclusion(self.state):
            result = auto.execute(state=self.state)
        self.assertEqual(result['reason_code'], 'lock_busy')
        self.assertEqual(json.loads((self.state / 'status.json').read_text())['attempt'], 'holder')
        self.assertEqual(len(list(self.state.glob('202*.json'))), 1)

    def test_missing_policy_makes_no_transport_or_provider_call_and_preserves_proof(self):
        original = {'run_id': self.run_id, 'completed_at': self.at.isoformat(),
                    'manifest_cipher_sha256': 'e' * 64, 'object_count': 2, 'cipher_bytes': 123}
        auto.atomic(self.state / 'status.json', {'version': 1, 'state': 'pending_configuration',
                                               'last_remote_complete': original})
        factory = Mock()
        with patch.object(auto.offsite, 'CONFIG_PARENT', self.secrets):
            result = auto.execute(state=self.state, policy_path=self.secrets / 'absent', transport_factory=factory)
        self.assertEqual(result['reason_code'], 'policy_missing')
        self.assertEqual(result['last_remote_complete'], original)
        self.assertFalse(result['provider_calls_permitted'])
        factory.assert_not_called()

    def test_policy_validation_refuses_stale_unapproved_and_unallocated_envelopes(self):
        with patch.object(auto.offsite, 'CONFIG_PARENT', self.secrets):
            self.assertEqual(auto.policy(self.policy_file(), self.at), self.policy)
            mutations = [dict(approved=False), dict(exclusive_scope_allocation_confirmed=False),
                         dict(exclusive_daily_budgets_confirmed=False), dict(daily_request_budget=1001),
                         dict(daily_download_budget_bytes=1_000_000_001), dict(account_storage_limit_bytes=20_000_000_000),
                         dict(scope_storage_ceiling_bytes=10_000_000_001), dict(max_run_seconds=901),
                         dict(valid_until=(self.at - timedelta(seconds=1)).isoformat()),
                         dict(valid_until=(self.at + timedelta(days=32)).isoformat()),
                         dict(account_storage_used_bytes_at_observation=0)]
            for update in mutations:
                with self.subTest(update=update), self.assertRaises(auto.Refusal):
                    auto.policy(self.policy_file(dict(self.policy, **update)), self.at)

    def test_policy_symlink_and_nonprivate_file_refused(self):
        with patch.object(auto.offsite, 'CONFIG_PARENT', self.secrets):
            path = self.policy_file()
            path.chmod(0o644)
            with self.assertRaisesRegex(auto.Refusal, 'policy_invalid'):
                auto.policy(path, self.at)
            path.chmod(0o600)
            linked = self.secrets / 'linked'
            linked.symlink_to(path)
            with self.assertRaisesRegex(auto.Refusal, 'policy_invalid'):
                auto.policy(linked, self.at)

    def test_budget_debits_before_http_and_keeps_failed_reservations(self):
        budget = auto.Budget(self.state, dict(self.policy, daily_request_budget=1), clock=lambda: self.at)
        transport = self.native_transport(self.config, budget)
        self.addCleanup(transport.close)
        with patch.object(transport.session, 'request', side_effect=OSError('SECRET should never propagate')) as request:
            with self.assertRaisesRegex(auto.Refusal, '^transport_failed$'):
                transport.request('GET', 'https://api.backblazeb2.com/example', limit=50)
            self.assertEqual(json.loads((self.state / 'budget.json').read_text())['download_bytes'], 50 + 65536)
            with self.assertRaisesRegex(auto.Refusal, 'budget_exhausted'):
                transport.request('GET', 'https://api.backblazeb2.com/example', limit=50)
            self.assertEqual(request.call_count, 1)

    def test_default_budget_clock_resolves_at_construction_and_checks_each_reservation(self):
        # The whole-cycle executor and its budget must share the operation clock.
        # A policy may expire between requests: admission never extends it.
        with patch.object(auto, 'now', side_effect=[self.at, self.at + timedelta(days=8)]):
            budget = auto.Budget(self.state, self.policy)
            budget.debit(0)
            with self.assertRaises(auto.Refusal) as caught:
                budget.debit(0)
        self.assertEqual(caught.exception.code, 'policy_expired')

    def test_budget_download_expiry_and_deadline_prevent_network(self):
        cases = [(dict(self.policy, daily_download_budget_bytes=10), lambda: self.at, lambda: 1, 'budget_exhausted'),
                 (self.policy, lambda: self.at + timedelta(days=8), lambda: 1, 'policy_expired')]
        for limits, clock, monotonic, reason in cases:
            with self.subTest(reason=reason):
                budget = auto.Budget(self.state, limits, clock=clock, monotonic=monotonic)
                with self.assertRaisesRegex(auto.Refusal, reason):
                    budget.debit(11)
        times = iter([0, 999])
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at, monotonic=lambda: next(times))
        with self.assertRaisesRegex(auto.Refusal, 'deadline'):
            budget.debit(1)

    def test_budget_survives_restart_and_resets_only_on_next_utc_day(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        budget.debit(123)
        auto.Budget(self.state, self.policy, clock=lambda: self.at).debit(77)
        self.assertEqual(json.loads((self.state / 'budget.json').read_text())['requests'], 2)
        auto.Budget(self.state, self.policy, clock=lambda: self.at + timedelta(days=1)).debit(9)
        self.assertEqual(json.loads((self.state / 'budget.json').read_text())['download_bytes'], 9)

    def test_native_inventory_counts_versions_and_refuses_unfinished_or_foreign_objects(self):
        transport = self.native_transport(self.config, Mock())
        self.addCleanup(transport.close)
        row = {'bucketId': self.config['bucket_id'], 'fileName': auto.offsite.PREFIX + 'file',
               'fileId': 'id', 'contentLength': 10, 'action': 'upload'}
        with patch.object(transport, 'api_call', side_effect=[{'files': [], 'nextFileId': None}, {'files': [row], 'nextFileName': None, 'nextFileId': None}]) as api:
            self.assertEqual(transport.inventory()[0]['contentLength'], 10)
            self.assertEqual(api.call_args[0][1]['prefix'], auto.offsite.PREFIX)
            self.assertEqual(api.call_args[0][1]['bucketId'], self.config['bucket_id'])
        for update, code in [(dict(action='start', contentLength=0), 'capacity_refused'),
                             (dict(fileName='another-project/file'), 'remote_corrupt'),
                             (dict(bucketId='f' * 24), 'remote_corrupt')]:
            with patch.object(transport, 'api_call', side_effect=[{'files': [], 'nextFileId': None},
                              {'files': [dict(row, **update)], 'nextFileName': None, 'nextFileId': None}]), self.assertRaisesRegex(auto.Refusal, code):
                transport.inventory()

    def test_native_inventory_paginates_all_versions_and_rejects_repeated_cursor(self):
        transport = self.native_transport(self.config, Mock())
        self.addCleanup(transport.close)
        row = {'bucketId': self.config['bucket_id'], 'fileName': auto.offsite.PREFIX + 'file',
               'fileId': 'one', 'contentLength': 10, 'action': 'upload'}
        first = {'files': [row], 'nextFileName': row['fileName'], 'nextFileId': 'two'}
        second = {'files': [dict(row, fileId='two')], 'nextFileName': None, 'nextFileId': None}
        with patch.object(transport, 'api_call', side_effect=[{'files': [], 'nextFileId': None}, first, second]):
            self.assertEqual(sum(x['contentLength'] for x in transport.inventory()), 20)
        with patch.object(transport, 'api_call', side_effect=[{'files': [], 'nextFileId': None}, first, dict(first, files=[])]), self.assertRaisesRegex(auto.Refusal, 'remote_corrupt'):
            transport.inventory()

    def test_native_scope_uses_v4_and_existing_exact_guard(self):
        transport = self.native_transport(self.config, Mock())
        self.addCleanup(transport.close)
        response = {'authorizationToken': 'synthetic-token', 'apiInfo': {'storageApi': {
            's3ApiUrl': self.config['endpoint'], 'apiUrl': 'https://api004.backblazeb2.com',
            'downloadUrl': 'https://f004.backblazeb2.com', 'allowed': {
                'buckets': [{'id': self.config['bucket_id'], 'name': self.config['bucket']}],
                'namePrefix': auto.offsite.PREFIX, 'capabilities': sorted(auto.offsite.CAPABILITIES)}}}}
        with patch.object(transport, 'request', return_value=json.dumps(response).encode()) as request:
            result = transport.authorize()
            self.assertIn('/b2api/v4/b2_authorize_account', request.call_args.args[1])
            self.assertNotIn('synthetic-token', json.dumps(result))
        response['apiInfo']['storageApi']['allowed']['capabilities'].append('deleteFiles')
        with patch.object(transport, 'request', return_value=json.dumps(response).encode()), self.assertRaisesRegex(auto.Refusal, 'scope_refused'):
            transport.authorize()

    def test_foreign_plaintext_redirect_or_credential_urls_refused_before_request(self):
        for url in ['http://api.backblazeb2.com', 'https://backblazeb2.com.attacker.invalid',
                    'https://user:password@api.backblazeb2.com', 'https://api.backblazeb2.com:444']:
            with self.subTest(url=url), self.assertRaisesRegex(auto.Refusal, 'scope_refused'):
                auto.provider_url(url)

    def test_select_latest_complete_ignores_incomplete_and_checks_actual_decryption(self):
        parent, directory = self.bundle()
        later = parent / '20260920T182000Z-aabbccde'
        later.mkdir(mode=0o700)
        auto.backup.write_private(later / 'INCOMPLETE', b'not done')
        manifest, objects, _ = auto.select_bundle(parent, self.key, self.policy, {}, self.at)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(objects, self.objects)
        badkey = self.secrets / 'badkey'
        auto.backup.write_private(badkey, Fernet.generate_key())
        with self.assertRaisesRegex(auto.Refusal, 'local_authentication_failed'):
            auto.select_bundle(parent, badkey, self.policy, {}, self.at)
        with self.assertRaisesRegex(auto.Refusal, 'local_backup_stale'):
            auto.select_bundle(parent, self.key, self.policy, {}, self.at + timedelta(days=3))

    def test_active_incomplete_bundle_is_resumed_before_newer_snapshot(self):
        parent, directory = self.bundle()
        newer = parent / '20260920T182000Z-aabbccde'
        newer.mkdir(mode=0o700)  # Even malformed newer snapshot cannot redirect the active attempt.
        active = {'run_id': self.run_id, 'complete': False}
        manifest, _, _ = auto.select_bundle(parent, self.key, self.policy, active, self.at)
        self.assertEqual(manifest['run_id'], self.run_id)

    def test_completed_same_local_snapshot_is_network_free_and_does_not_refresh_proof(self):
        parent, _ = self.bundle()
        self.call()
        proof = {'run_id': self.run_id, 'manifest_cipher_sha256': auto.backup.digest(self.objects['manifest.json.fernet']),
                 'completed_at': self.at.isoformat(), 'object_count': 2, 'cipher_bytes': 123}
        auto.atomic(self.state / 'status.json', {'last_remote_complete': proof,
                                               'last_verified_readback': dict(proof, verified_at=self.at.isoformat())})
        factory = Mock()
        with patch.object(auto, 'now', return_value=self.at), patch.object(auto, 'policy', return_value=self.policy), \
                patch.object(auto.offsite, 'configuration', return_value=self.config):
            result = auto.execute(state=self.state, key=self.key, backups=parent, transport_factory=factory)
        self.assertEqual(result['state'], 'complete')
        self.assertEqual(result['last_remote_complete'], proof)
        self.assertEqual(result['last_verified_readback']['verified_at'], self.at.isoformat())
        factory.assert_not_called()

    def test_execute_live_path_fixture_records_completion_and_no_restore(self):
        parent, _ = self.bundle()
        with patch.object(auto, 'now', return_value=self.at), patch.object(auto, 'policy', return_value=self.policy), \
                patch.object(auto.offsite, 'configuration', return_value=self.config):
            result = auto.execute(state=self.state, key=self.key, backups=parent,
                                  transport_factory=lambda config, budget: self.remote)
        self.assertEqual(result['state'], 'complete')
        self.assertFalse(result['restore_performed'])
        self.assertFalse(result['independent_custody_verified'])
        self.assertEqual(result['last_remote_complete']['object_count'], 2)
        self.assertEqual(len(list(self.state.glob('202*.json'))), 1)

    def test_inspect_and_execute_never_echo_unknown_protected_status_fields(self):
        proof = {'run_id': self.run_id, 'manifest_cipher_sha256': 'a' * 64, 'verified_at': self.at.isoformat(),
                 'table_count': 35, 'row_count': 123, 'file_count': 42, 'source': 'vps_key',
                 'unexpected_secret': 'synthetic-stage-redaction-canary'}
        auto.atomic(self.state / 'status.json', {'version': 1, 'state': 'pending_configuration',
                                               'unexpected_secret': 'synthetic-top-redaction-canary',
                                               'last_isolated_restore': proof})
        with patch.object(auto.offsite, 'CONFIG_PARENT', self.secrets):
            inspected = auto.inspect(self.secrets / 'absent', self.state)
            executed = auto.execute(state=self.state, policy_path=self.secrets / 'absent')
        for result in (inspected, executed):
            self.assertNotIn('canary', json.dumps(result))
            self.assertNotIn('unexpected_secret', json.dumps(result))
        self.assertEqual(inspected['status']['last_isolated_restore']['source'], 'vps_key')

    def test_malformed_status_proof_refused_without_emitting_provider_material(self):
        auto.atomic(self.state / 'status.json', {'version': 1, 'state': 'complete',
                                               'last_remote_complete': {'run_id': 'secret-canary'}})
        with patch.object(auto.offsite, 'CONFIG_PARENT', self.secrets):
            result = auto.inspect(self.secrets / 'absent', self.state)
        self.assertFalse(result['eligible'])
        self.assertEqual(result['reason_code'], 'state_invalid')
        self.assertNotIn('canary', json.dumps(result))

    def test_native_http_enforces_tls_no_redirect_proxy_netrc_or_implicit_retry(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        transport = self.native_transport(self.config, budget)
        self.addCleanup(transport.close)
        response = Mock()
        response.status_code = 200
        response.iter_content.return_value = [b'ciphertext']
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(transport.session, 'request', return_value=response) as request:
            self.assertEqual(transport.request('GET', 'https://f004.backblazeb2.com/test', limit=10), b'ciphertext')
        self.assertFalse(transport.session.trust_env)
        self.assertTrue(transport.session.verify)
        self.assertEqual(transport.session.adapters['https://'].max_retries.total, 0)
        self.assertEqual(request.call_args.kwargs['timeout'], (10, 30))
        self.assertFalse(request.call_args.kwargs['allow_redirects'])
        self.assertTrue(request.call_args.kwargs['stream'])
        charged = json.loads((self.state / 'budget.json').read_text())
        self.assertEqual(charged['download_bytes'], 10 + 65536)
        self.assertEqual(charged['requests'], 1)

    def test_native_http_error_body_never_reported_and_redirect_is_not_followed(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        transport = self.native_transport(self.config, budget)
        self.addCleanup(transport.close)
        for code in (302, 401, 503):
            response = Mock(status_code=code)
            response.text = 'synthetic-secret-error-canary'
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            with self.subTest(code=code), patch.object(transport.session, 'request', return_value=response) as request:
                with self.assertRaisesRegex(auto.Refusal, '^transport_failed$'):
                    transport.request('GET', 'https://f004.backblazeb2.com/test', limit=50)
                self.assertEqual(request.call_count, 1)
                response.iter_content.assert_not_called()

    def test_native_http_oversized_response_refused_with_reservation_retained(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        transport = self.native_transport(self.config, budget)
        self.addCleanup(transport.close)
        response = Mock(status_code=200)
        response.iter_content.return_value = [b'too many bytes']
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch.object(transport.session, 'request', return_value=response), self.assertRaisesRegex(auto.Refusal, 'remote_corrupt'):
            transport.request('GET', 'https://f004.backblazeb2.com/test', limit=2)
        self.assertEqual(json.loads((self.state / 'budget.json').read_text())['download_bytes'], 2 + 65536)

    def test_native_put_uses_explicit_bucket_v4_upload_and_authenticated_byte_readback_by_id(self):
        transport = self.native_transport(self.config, Mock())
        self.addCleanup(transport.close)
        transport.api, transport.download, transport.token = ('https://api004.backblazeb2.com',
            'https://f004.backblazeb2.com', 'synthetic-authorized-token')
        full_name = auto.offsite.PREFIX + self.run_id + '/' + 'c' * 64 + '/database.dump.fernet'
        payload = self.objects['database.dump.fernet']
        transport._write_permits[full_name] = (len(payload), auto.backup.digest(payload))
        upload = {'bucketId': self.config['bucket_id'],
                  'uploadUrl': 'https://pod-001-0001-01.backblaze.com/b2api/v4/b2_upload_file?bucket=synthetic',
                  'authorizationToken': 'synthetic-upload-token'}
        row = {'bucketId': self.config['bucket_id'], 'fileName': full_name, 'fileId': 'synthetic-file-id',
               'action': 'upload', 'contentLength': len(payload), 'contentSha1': 'unverified:irrelevant'}
        with patch.object(transport, 'request', side_effect=[json.dumps(upload).encode(), json.dumps(row).encode(), payload]) as request:
            actual = transport.put(full_name, payload)
            self.assertEqual(transport.get(actual, len(payload)), payload)
        first, second, third = request.call_args_list
        self.assertEqual(first.args, ('POST', transport.api + '/b2api/v4/b2_get_upload_url'))
        self.assertEqual(first.kwargs['json'], {'bucketId': self.config['bucket_id']})
        self.assertEqual(second.args, ('POST', upload['uploadUrl']))
        self.assertEqual(second.kwargs['data'], payload)
        self.assertEqual(second.kwargs['headers']['Content-Length'], str(len(payload)))
        self.assertEqual(second.kwargs['headers']['X-Bz-File-Name'], full_name)
        self.assertEqual(second.kwargs['headers']['X-Bz-Content-Sha1'], auto.hashlib.sha1(payload).hexdigest())
        self.assertEqual(third.args, ('GET', transport.download + '/b2api/v4/b2_download_file_by_id'))
        self.assertEqual(third.kwargs['params'], {'fileId': 'synthetic-file-id'})
        self.assertEqual(third.kwargs['limit'], len(payload))

    def test_native_put_cannot_accept_other_bucket_or_foreign_upload_url(self):
        for upload in ({'bucketId': 'another-bucket', 'uploadUrl': 'https://pod-001.backblaze.com/upload'},
                       {'bucketId': self.config['bucket_id'], 'uploadUrl': 'https://attacker.invalid/upload'}):
            transport = self.native_transport(self.config, Mock())
            self.addCleanup(transport.close)
            transport._write_permits[auto.offsite.PREFIX + 'synthetic'] = (7, auto.backup.digest(b'fixture'))
            with patch.object(transport, 'api_call', return_value=dict(upload, authorizationToken='synthetic')), \
                    patch.object(transport, 'request') as request, self.assertRaisesRegex(auto.Refusal, 'scope_refused'):
                transport.put(auto.offsite.PREFIX + 'synthetic', b'fixture')
            request.assert_not_called()

    def test_symlink_execution_lock_preserves_safe_status_and_records_visible_refusal(self):
        original = {'version': 1, 'state': 'complete', 'attempt': 'prior'}
        auto.atomic(self.state / 'status.json', original)
        target = self.root / 'unrelated'
        target.write_text('preserve me')
        (self.state / 'execution.lock').symlink_to(target)
        result = auto.execute(state=self.state)
        self.assertEqual(result['reason_code'], 'state_invalid')
        self.assertEqual(json.loads((self.state / 'status.json').read_text()), original)
        self.assertEqual(target.read_text(), 'preserve me')
        self.assertEqual(len(list(self.state.glob('202*.json'))), 1)


if __name__ == '__main__':
    unittest.main()
