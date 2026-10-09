"""Isolated renewal/accounting and whole-response deadline regressions; no provider calls."""
from datetime import timedelta
import json
import signal
import threading
import time
from unittest import TestCase
from unittest.mock import Mock, patch

try:
    from . import automatic_offsite as auto
    from . import test_automatic_offsite as fixtures
except ImportError:
    import automatic_offsite as auto
    import test_automatic_offsite as fixtures


class RenewalBudgetTests(TestCase):
    setUp = fixtures.AutomaticOffsiteTests.setUp
    bundle = fixtures.AutomaticOffsiteTests.bundle

    def transport(self, budget):
        transport = auto.NativeTransport(self.config, budget)
        self.addCleanup(transport.close)
        guard = patch.object(transport, '_assert_live')
        guard.start()
        self.addCleanup(guard.stop)
        return transport

    def shorten_active_response_deadline(self, budget):
        # Keep the production handler and real SIGALRM. Start the short fixture
        # window at the phase under test, after setup and durable reservation.
        remaining, interval = signal.getitimer(signal.ITIMER_REAL)
        self.assertGreater(remaining, 0)
        self.assertEqual(interval, 0)
        seconds = min(remaining, 0.08)
        budget.deadline = budget.monotonic() + seconds
        signal.setitimer(signal.ITIMER_REAL, seconds)

    def test_known_spend_cannot_be_refunded_to_fit_another_inventory(self):
        original = {'version': 1, 'day': '2026-09-20', 'requests': 422, 'download_bytes': 98_474_544}
        auto.atomic(self.state / 'budget.json', original)
        before = (self.state / 'budget.json').read_bytes()
        with self.assertRaisesRegex(auto.Refusal, 'budget_exhausted'):
            auto.Budget(self.state, self.policy, clock=lambda: self.at).preflight(3, 2_359_296)
        self.assertEqual((self.state / 'budget.json').read_bytes(), before)
        next_day = self.at + timedelta(days=1)
        budget = auto.Budget(self.state, self.policy, clock=lambda: next_day)
        budget.preflight(3, 2_359_296)
        budget.debit(131072)
        value = json.loads((self.state / 'budget.json').read_bytes())
        self.assertEqual(value['days']['2026-09-20'], {'requests': 422, 'download_bytes': 98_474_544})
        self.assertEqual(value['days']['2026-09-21'], {'requests': 1, 'download_bytes': 131072})
        self.assertEqual(value['legacy_import'], original)

    def test_slow_headers_stop_at_total_deadline_and_failed_reservation_survives(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        budget.deadline = time.monotonic() + 30
        transport = self.transport(budget)
        received = []
        def slow_headers(*args, **kwargs):
            self.shorten_active_response_deadline(budget)
            time.sleep(0.5)
            received.append('late response')
            return Mock()
        with patch.object(transport.session, 'request', side_effect=slow_headers) as request:
            with self.assertRaisesRegex(auto.Refusal, '^deadline$'):
                transport.request('GET', 'https://api.backblazeb2.com/fixture', limit=200)
            with self.assertRaisesRegex(auto.Refusal, '^deadline$'):
                transport.request('GET', 'https://api.backblazeb2.com/fixture', limit=200)
        self.assertEqual(received, [])
        self.assertEqual(request.call_count, 1)
        self.assertEqual(json.loads((self.state / 'budget.json').read_bytes())['download_bytes'], 65736)
        self.assertEqual(json.loads((self.state / 'budget.json').read_bytes())['requests'], 1)

    def test_slow_trickle_body_is_interrupted_before_generator_yields_late_bytes(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        budget.deadline = time.monotonic() + 30
        transport = self.transport(budget)
        entered, delivered = [], []
        response = Mock(status_code=200)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        def trickle(_size):
            entered.append(True)
            self.shorten_active_response_deadline(budget)
            time.sleep(0.5)
            delivered.append('late bytes')
            yield b'late bytes'
        response.iter_content = trickle
        with patch.object(transport.session, 'request', return_value=response) as request:
            with self.assertRaisesRegex(auto.Refusal, '^deadline$'):
                transport.request('GET', 'https://api.backblazeb2.com/fixture', limit=200)
        self.assertEqual(entered, [True])
        self.assertEqual(delivered, [])
        request.assert_called_once()
        response.__enter__.assert_called_once()
        response.__exit__.assert_called_once()
        self.assertEqual(json.loads((self.state / 'budget.json').read_bytes())['requests'], 1)

    def test_pre_body_deadline_retains_reservation_without_acquiring_a_response(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        budget.deadline = time.monotonic() + 30
        transport = self.transport(budget)
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        original_debit = budget.debit
        def slow_reservation(download):
            original_debit(download)
            self.shorten_active_response_deadline(budget)
            time.sleep(0.5)
            self.fail('pre-body deadline did not interrupt the reservation')
        with patch.object(budget, 'debit', side_effect=slow_reservation), \
                patch.object(transport.session, 'request', return_value=response) as request:
            with self.assertRaisesRegex(auto.Refusal, '^deadline$'):
                transport.request('GET', 'https://api.backblazeb2.com/fixture', limit=200)
        request.assert_not_called()
        response.__enter__.assert_not_called()
        response.__exit__.assert_not_called()
        ledger = json.loads((self.state / 'budget.json').read_bytes())
        self.assertEqual(ledger['requests'], 1)
        self.assertEqual(ledger['download_bytes'], 65736)

    def test_outer_manual_recovery_alarm_handler_and_remaining_time_survive_http(self):
        original_handler = signal.getsignal(signal.SIGALRM)
        original_timer = signal.getitimer(signal.ITIMER_REAL)
        def outer_alarm(_signal, _frame):
            raise RuntimeError('outer manual deadline')
        try:
            signal.signal(signal.SIGALRM, outer_alarm)
            signal.setitimer(signal.ITIMER_REAL, 5)
            budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
            with auto.response_deadline(budget):
                time.sleep(0.01)
            self.assertIs(signal.getsignal(signal.SIGALRM), outer_alarm)
            self.assertGreater(signal.getitimer(signal.ITIMER_REAL)[0], 0)
            self.assertLess(signal.getitimer(signal.ITIMER_REAL)[0], 5)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, original_handler)
            signal.setitimer(signal.ITIMER_REAL, *original_timer)

    def test_response_alarm_refuses_non_main_thread_before_http(self):
        budget = auto.Budget(self.state, self.policy, clock=lambda: self.at)
        transport = self.transport(budget)
        outcome = []
        def worker():
            try:
                transport.request('GET', 'https://api.backblazeb2.com/fixture', limit=200)
            except auto.Refusal as error:
                outcome.append(error.code)
        with patch.object(transport.session, 'request') as request:
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, ['state_invalid'])
        request.assert_not_called()
        self.assertFalse((self.state / 'budget.json').exists())

    def test_cleanup_grace_can_precharge_next_day_and_is_not_refunded(self):
        start = self.at.replace(hour=23, minute=59, second=17)
        budget = auto.Budget(self.state, self.policy, clock=lambda: start, monotonic=lambda: 0)
        budget.deadline = 1
        budget.debit(100)
        value = json.loads((self.state / 'budget.json').read_bytes())
        self.assertEqual(value['days']['2026-09-20'], value['days']['2026-09-21'])
        # A restart after the deadline does not release the uncertain response reservation.
        auto.Budget(self.state, self.policy, clock=lambda: start + timedelta(minutes=1)).debit(20)
        self.assertEqual(json.loads((self.state / 'budget.json').read_bytes())['download_bytes'], 120)

    def test_issued_future_day_ticket_survives_rollover_without_charging_previous_day_twice(self):
        value = {'version': 2, 'day': '2026-09-20', 'requests': 422, 'download_bytes': 98_474_544,
                 'days': {'2026-09-20': {'requests': 422, 'download_bytes': 98_474_544},
                          '2026-09-21': {'requests': 20, 'download_bytes': 8_388_608}},
                 'legacy_import': {'version': 1, 'day': '2026-09-20', 'requests': 296,
                                   'download_bytes': 68_551_020},
                 'external_reservations': [{'reference': 'future-account-audit-ticket', 'at': self.at.isoformat(),
                    'requests': 20, 'download_bytes': 8_388_608, 'charged_days': ['2026-09-21']}]}
        auto.atomic(self.state / 'budget.json', value)
        next_day = self.at + timedelta(days=1)
        auto.Budget(self.state, self.policy, clock=lambda: next_day).debit(100)
        after = json.loads((self.state / 'budget.json').read_bytes())
        self.assertEqual(after['days']['2026-09-20'], value['days']['2026-09-20'])
        self.assertEqual(after['days']['2026-09-21'], {'requests': 21, 'download_bytes': 8_388_708})
        self.assertEqual(after['external_reservations'], value['external_reservations'])
        self.assertEqual(after['legacy_import'], value['legacy_import'])

    def test_invocation_id_links_new_attempt_without_asserting_timer_origin(self):
        parent, _ = self.bundle()
        with patch.dict(auto.os.environ, {'INVOCATION_ID': 'a'*32}), \
                patch.object(auto, 'now', return_value=self.at), patch.object(auto, 'policy', return_value=self.policy), \
                patch.object(auto.offsite, 'configuration', return_value=self.config):
            result = auto.execute(state=self.state, key=self.key, backups=parent,
                                  transport_factory=lambda config, budget: self.remote)
        self.assertEqual(result['invocation'], {'source': 'systemd_environment',
                         'systemd_invocation_id': 'a'*32, 'timer_trigger_verified': False})
        self.assertEqual(auto.status_summary(result)['invocation'], result['invocation'])
        saved = json.loads(next(self.state.glob('202*.json')).read_bytes())
        self.assertEqual(saved['invocation'], result['invocation'])

    def test_malformed_invocation_environment_never_leaks_or_claims_timer_execution(self):
        for value in (None, '', 'synthetic-secret-canary', 'a'*33, 'A'*32):
            with self.subTest(value=value):
                result = auto.invocation_context({'INVOCATION_ID': value})
                self.assertEqual(result, {'source': 'unclassified', 'systemd_invocation_id': None,
                                         'timer_trigger_verified': False})

    def test_untrusted_status_cannot_promote_environment_to_timer_proof(self):
        value = {'version': 1, 'state': 'complete', 'reason_code': None,
                 'invocation': {'source': 'systemd_environment', 'systemd_invocation_id': 'a'*32,
                                'timer_trigger_verified': True}}
        with self.assertRaisesRegex(auto.Refusal, 'state_invalid'):
            auto.status_summary(value)
