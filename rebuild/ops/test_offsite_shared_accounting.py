"""Offline counterexamples for durable, shared B2 limits; no external requests or production state."""
from datetime import timedelta
import json
from unittest import TestCase
from unittest.mock import Mock, patch

try:
    from . import automatic_offsite as auto
    from . import test_automatic_offsite as fixtures
except ImportError:
    import automatic_offsite as auto
    import test_automatic_offsite as fixtures


class SharedAccountingTests(TestCase):
    setUp = fixtures.AutomaticOffsiteTests.setUp
    bundle = fixtures.AutomaticOffsiteTests.bundle

    def test_v1_reservations_and_all_prior_days_survive_upgrade_and_restart(self):
        original = {'version': 1, 'day': self.at.strftime('%Y-%m-%d'),
                    'requests': 296, 'download_bytes': 68_551_020}
        auto.atomic(self.state / 'budget.json', original)
        auto.Budget(self.state, self.policy, clock=lambda: self.at).debit(17)
        next_day = self.at + timedelta(days=1)
        auto.Budget(self.state, self.policy, clock=lambda: next_day).debit(23)
        value = json.loads((self.state / 'budget.json').read_text())
        self.assertEqual(value['legacy_import'], original)
        self.assertEqual(value['days'][original['day']], {'requests': 297, 'download_bytes': 68_551_037})
        self.assertEqual(value['requests'], 1)
        self.assertEqual(value['download_bytes'], 23)
        self.assertEqual(auto.budget_summary(self.state, next_day)['prior_day_count'], 1)

    def test_inflight_response_reserves_both_days_before_midnight_and_survives_crash(self):
        start = self.at.replace(hour=23, minute=59, second=50)
        budget = auto.Budget(self.state, self.policy, clock=lambda: start)
        budget.debit(1234)
        value = json.loads((self.state / 'budget.json').read_text())
        first, second = start.strftime('%Y-%m-%d'), (start + timedelta(days=1)).strftime('%Y-%m-%d')
        self.assertEqual(value['days'][first], value['days'][second])
        # The interrupted request is not refunded, including the precharged next UTC day.
        auto.Budget(self.state, self.policy, clock=lambda: start + timedelta(minutes=1)).debit(20)
        value = json.loads((self.state / 'budget.json').read_text())
        self.assertEqual(value['download_bytes'], 1254)
        self.assertEqual(value['requests'], 2)

    def test_next_day_prepaid_capacity_can_refuse_current_day_request(self):
        start = self.at.replace(hour=23, minute=59, second=50)
        limits = dict(self.policy, daily_request_budget=1)
        auto.Budget(self.state, limits, clock=lambda: start).debit(100)
        with self.assertRaisesRegex(auto.Refusal, 'budget_exhausted'):
            auto.Budget(self.state, limits, clock=lambda: start + timedelta(minutes=1)).debit(1)

    def test_clock_rollback_does_not_reopen_old_daily_allowance(self):
        auto.Budget(self.state, self.policy, clock=lambda: self.at + timedelta(days=1)).debit(100)
        with self.assertRaisesRegex(auto.Refusal, 'state_invalid'):
            auto.Budget(self.state, self.policy, clock=lambda: self.at).debit(1)

    def test_whole_cycle_insufficient_budget_refuses_before_provider_or_factory(self):
        parent, _ = self.bundle()
        factory = Mock()
        limits = dict(self.policy, daily_download_budget_bytes=1000)
        budget = auto.Budget(self.state, limits, clock=lambda: self.at)
        with patch.object(auto, 'now', return_value=self.at), \
                patch.object(auto, 'policy', return_value=limits), \
                patch.object(auto.offsite, 'configuration', return_value=self.config), \
                patch.object(auto, 'Budget', return_value=budget):
            result = auto.execute(state=self.state, key=self.key, backups=parent, transport_factory=factory)
        self.assertEqual(result['reason_code'], 'budget_exhausted')
        self.assertFalse(result['provider_calls_permitted'])
        factory.assert_not_called()
        self.assertFalse((self.state / 'budget.json').exists())

    def test_external_reservation_is_atomic_historical_and_cannot_be_replayed(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        with patch.object(budget, 'assert_live'):
            entry = budget.reserve_external(31, 2_000_000, 'desktop-account-audit-20260920')
            with self.assertRaisesRegex(auto.Refusal, 'state_invalid'):
                budget.reserve_external(31, 2_000_000, 'desktop-account-audit-20260920')
        value = json.loads((self.state / 'budget.json').read_text())
        self.assertEqual(value['requests'], 31)
        self.assertEqual(value['download_bytes'], 2_000_000)
        self.assertEqual(value['external_reservations'], [entry])

    def test_external_reservation_over_limit_leaves_no_partial_charge(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        budget.debit(20)
        before = (self.state / 'budget.json').read_bytes()
        with patch.object(budget, 'assert_live'), self.assertRaisesRegex(auto.Refusal, 'budget_exhausted'):
            budget.reserve_external(500, 0, 'unavailable-reservation')
        self.assertEqual((self.state / 'budget.json').read_bytes(), before)

    def test_noncanonical_ledger_cannot_reach_native_http(self):
        transport = auto.NativeTransport(self.config, auto.Budget(self.state, self.policy, clock=lambda: self.at))
        self.addCleanup(transport.close)
        with patch.object(transport.session, 'request') as request, self.assertRaisesRegex(auto.Refusal, 'state_invalid'):
            transport.request('GET', 'https://api.backblazeb2.com/example')
        request.assert_not_called()

    def test_arbitrary_budget_object_cannot_reach_native_http(self):
        transport = auto.NativeTransport(self.config, Mock())
        self.addCleanup(transport.close)
        with patch.object(transport.session, 'request') as request, self.assertRaisesRegex(auto.Refusal, 'state_invalid'):
            transport.request('GET', 'https://api.backblazeb2.com/example')
        request.assert_not_called()

    def test_canonical_state_without_global_lock_cannot_reach_native_http(self):
        auto.atomic(self.state / 'budget.json', {'version': 1, 'day': self.at.strftime('%Y-%m-%d'),
                                               'requests': 0, 'download_bytes': 0})
        transport = auto.NativeTransport(self.config, auto.Budget(self.state, self.policy, clock=lambda: self.at))
        self.addCleanup(transport.close)
        with patch.object(auto, 'STATE', self.state), patch.object(transport.session, 'request') as request, \
                self.assertRaisesRegex(auto.Refusal, 'lock_busy'):
            transport.request('GET', 'https://api.backblazeb2.com/example')
        request.assert_not_called()

    def test_lock_does_not_authorize_different_or_stale_policy(self):
        auto.atomic(self.state / 'budget.json', {'version': 1, 'day': self.at.strftime('%Y-%m-%d'),
                                               'requests': 0, 'download_bytes': 0})
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        with patch.object(auto, 'STATE', self.state), auto.exclusion(self.state), \
                patch.object(auto, 'policy', return_value=dict(self.policy, daily_request_budget=1)), \
                self.assertRaisesRegex(auto.Refusal, 'policy_invalid'):
            budget.assert_live()

    def test_deleted_global_journal_is_not_a_fresh_live_allowance(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        with patch.object(auto, 'STATE', self.state), auto.exclusion(self.state), \
                self.assertRaisesRegex(auto.Refusal, 'state_invalid'):
            budget.assert_live()

    def test_unfinished_uploads_fail_before_versions_or_any_write(self):
        transport = auto.NativeTransport(self.config, Mock())
        self.addCleanup(transport.close)
        for response in ({'files': [{'fileId': 'unfinished'}], 'nextFileId': None},
                         {'files': [], 'nextFileId': 'more-unfinished'}, {}):
            with self.subTest(response=response), patch.object(transport, 'api_call', return_value=response) as api:
                with self.assertRaises(auto.Refusal):
                    transport.inventory()
                api.assert_called_once_with('b2_list_unfinished_large_files', {
                    'bucketId': self.config['bucket_id'], 'namePrefix': auto.offsite.PREFIX, 'maxFileCount': 100})

    def test_direct_native_put_without_authenticated_capacity_plan_fails_before_network(self):
        transport = auto.NativeTransport(self.config, Mock())
        self.addCleanup(transport.close)
        with patch.object(transport, 'api_call') as api, self.assertRaisesRegex(auto.Refusal, 'capacity_refused'):
            transport.put(auto.offsite.PREFIX + 'unplanned', b'ciphertext')
        api.assert_not_called()

    def test_capacity_permit_cannot_repeat_put_or_rearm_stale_inventory(self):
        budget = Mock(limits=self.policy)
        transport = auto.NativeTransport(self.config, budget)
        self.addCleanup(transport.close)
        name, payload = auto.offsite.PREFIX + 'synthetic', b'ciphertext'
        inventory = []
        transport._inventory = inventory
        transport.prepare_uploads({name: payload}, inventory)
        with patch.object(transport, 'api_call', side_effect=auto.Refusal('transport_failed')) as api:
            with self.assertRaisesRegex(auto.Refusal, 'transport_failed'):
                transport.put(name, payload)
            with self.assertRaisesRegex(auto.Refusal, 'capacity_refused'):
                transport.put(name, payload)
            api.assert_called_once()
        with self.assertRaisesRegex(auto.Refusal, 'capacity_refused'):
            transport.prepare_uploads({name: payload}, inventory)

    def test_successful_or_uncertain_upload_post_consumes_capacity_permit_once(self):
        name, payload = auto.offsite.PREFIX + 'synthetic', b'ciphertext'
        upload = {'bucketId': self.config['bucket_id'], 'uploadUrl': 'https://pod-001.backblaze.com/upload',
                  'authorizationToken': 'synthetic'}
        row = {'bucketId': self.config['bucket_id'], 'fileName': name, 'fileId': 'synthetic-version',
               'action': 'upload', 'contentLength': len(payload)}
        for failed in (False, True):
            transport = auto.NativeTransport(self.config, Mock(limits=self.policy))
            self.addCleanup(transport.close)
            transport._inventory = []
            transport.prepare_uploads({name: payload}, transport._inventory)
            response = auto.Refusal('transport_failed') if failed else json.dumps(row).encode()
            with self.subTest(failed=failed), patch.object(transport, 'api_call', return_value=upload), \
                    patch.object(transport, 'request', side_effect=[response]) as request:
                if failed:
                    with self.assertRaisesRegex(auto.Refusal, 'transport_failed'):
                        transport.put(name, payload)
                else:
                    transport.put(name, payload)
                with self.assertRaisesRegex(auto.Refusal, 'capacity_refused'):
                    transport.put(name, payload)
                request.assert_called_once()

    def test_transport_cleanup_failure_is_visible_and_attempt_survives(self):
        parent, _ = self.bundle()
        self.remote.close = Mock(side_effect=OSError('synthetic-secret-cleanup-detail'))
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        with patch.object(auto, 'now', return_value=self.at), patch.object(auto, 'policy', return_value=self.policy), \
                patch.object(auto.offsite, 'configuration', return_value=self.config), \
                patch.object(auto, 'Budget', return_value=budget):
            result = auto.execute(state=self.state, key=self.key, backups=parent,
                                  transport_factory=lambda config, budget: self.remote)
        self.assertEqual(result['state'], 'failed')
        self.assertEqual(result['reason_code'], 'cleanup_failed')
        self.assertTrue(result['result']['authenticated'])
        self.assertNotIn('secret-cleanup-detail', json.dumps(result))
        self.assertEqual(len(list(self.state.glob('202*.json'))), 1)

    def test_scope_capacity_observation_survives_network_free_noop(self):
        parent, _ = self.bundle()
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        with patch.object(auto, 'now', return_value=self.at), patch.object(auto, 'policy', return_value=self.policy), \
                patch.object(auto.offsite, 'configuration', return_value=self.config), \
                patch.object(auto, 'Budget', return_value=budget):
            first = auto.execute(state=self.state, key=self.key, backups=parent,
                                 transport_factory=lambda config, budget: self.remote)
            factory = Mock()
            second = auto.execute(state=self.state, key=self.key, backups=parent, transport_factory=factory)
        self.assertEqual(first['last_capacity'], second['last_capacity'])
        self.assertEqual(second['result'], {'no_new_local_backup': True, 'provider_calls': 0})
        factory.assert_not_called()
