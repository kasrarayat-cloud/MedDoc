"""Focused synthetic manual-consumer checks; no provider or object content is accessed."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

try:
    from . import offsite_operator as operator
except ImportError:
    import offsite_operator as operator

engine = operator.engine


class OperatorAccountingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name)
        self.policy_path = self.state / 'offsite-policy.json'
        at = datetime.now(timezone.utc)
        self.limits = {'observed_at': (at - timedelta(hours=1)).isoformat(),
                       'valid_until': (at + timedelta(hours=1)).isoformat(),
                       'max_run_seconds': 900, 'daily_request_budget': 500,
                       'daily_download_budget_bytes': 100_000_000}
        self.original = {'version': 1, 'day': at.strftime('%Y-%m-%d'),
                         'requests': 296, 'download_bytes': 68_551_020}
        engine.atomic(self.state / 'budget.json', self.original)
        for name, value in [('STATE', self.state), ('POLICY', self.policy_path)]:
            patched = patch.object(engine, name, value); patched.start(); self.addCleanup(patched.stop)
        patched = patch.object(engine, 'policy', return_value=self.limits)
        patched.start(); self.addCleanup(patched.stop)
        patched = patch('requests.Session', side_effect=AssertionError('No provider use allowed in this fixture.'))
        patched.start(); self.addCleanup(patched.stop)

    def test_external_reservation_preserves_consumed_history_without_http_or_credentials(self):
        with patch.object(engine.offsite, 'configuration', side_effect=AssertionError('No secret access')):
            result = operator.reserve_external(31, 2_000_000, 'desktop-audit-and-navigation-reserve')
        self.assertEqual(result['provider_calls'], 0)
        value = json.loads((self.state / 'budget.json').read_text())
        self.assertEqual(value['legacy_import'], self.original)
        self.assertEqual(value['requests'], 327)
        self.assertEqual(value['download_bytes'], 70_551_020)
        self.assertEqual(value['external_reservations'][0]['reference'], 'desktop-audit-and-navigation-reserve')
        self.assertEqual((self.state / 'budget.json').stat().st_mode & 0o777, 0o600)

    def test_duplicate_reference_cannot_double_charge_or_rewrite_history(self):
        operator.reserve_external(31, 2_000_000, 'desktop-audit')
        before = (self.state / 'budget.json').read_bytes()
        with self.assertRaises(engine.Refusal):
            operator.reserve_external(31, 2_000_000, 'desktop-audit')
        self.assertEqual((self.state / 'budget.json').read_bytes(), before)

    def test_reservation_cannot_exceed_cap_or_refund_consumption(self):
        before = (self.state / 'budget.json').read_bytes()
        for requests, downloaded in ((205, 0), (0, 31_448_981), (-1, 0), (0, -1), (True, 0)):
            with self.subTest(requests=requests, downloaded=downloaded), self.assertRaises(engine.Refusal):
                operator.reserve_external(requests, downloaded, 'fixture-rejected')
            self.assertEqual((self.state / 'budget.json').read_bytes(), before)

    def test_operator_competing_with_scheduled_lock_cannot_reserve(self):
        before = (self.state / 'budget.json').read_bytes()
        with engine.exclusion(self.state), self.assertRaises(engine.Refusal) as caught:
            operator.reserve_external(1, 1, 'overlap')
        self.assertEqual(caught.exception.code, 'lock_busy')
        self.assertEqual((self.state / 'budget.json').read_bytes(), before)

    def test_expired_policy_cannot_reserve(self):
        before = (self.state / 'budget.json').read_bytes()
        with patch.object(engine, 'policy', side_effect=engine.Refusal('policy_expired')):
            with self.assertRaises(engine.Refusal):
                operator.reserve_external(1, 1, 'expired')
        self.assertEqual((self.state / 'budget.json').read_bytes(), before)

    def test_cli_has_no_alternate_state_or_config_budget_option(self):
        with patch('sys.argv', ['offsite_operator.py', 'inventory', '--state-dir', '/tmp/new-budget']), \
             patch('sys.stderr', new_callable=io.StringIO), self.assertRaises(SystemExit) as caught:
            operator.main()
        self.assertEqual(caught.exception.code, 2)


class OperatorMetadataTests(unittest.TestCase):
    def test_metadata_is_explicitly_scoped_and_counts_retained_versions(self):
        rows = [{'fileName': 'same', 'action': 'upload', 'contentLength': 10},
                {'fileName': 'same', 'action': 'upload', 'contentLength': 20},
                {'fileName': 'hidden', 'action': 'hide', 'contentLength': 0}]
        transport = SimpleNamespace(inventory=Mock(return_value=rows))
        @contextmanager
        def session():
            yield transport
        with patch.object(engine, 'live_session', side_effect=session):
            result = operator.inventory()
        self.assertEqual(result['retained_versions'], 2)
        self.assertEqual(result['retained_version_bytes'], 30)
        self.assertEqual(result['retained_names'], 1)
        self.assertEqual(result['hide_markers'], 1)
        self.assertIn('not account-wide', result['scope'])
        self.assertEqual(result['provider_mutations'], 0)

    def test_failed_session_cleanup_cannot_report_complete_metadata(self):
        @contextmanager
        def session():
            yield SimpleNamespace(inventory=Mock(return_value=[]))
            raise engine.Refusal('cleanup_failed')
        with patch.object(engine, 'live_session', side_effect=session), self.assertRaises(engine.Refusal):
            operator.inventory()


if __name__ == '__main__':
    unittest.main()
