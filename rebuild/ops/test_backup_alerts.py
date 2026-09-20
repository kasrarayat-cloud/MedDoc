"""Isolated alert fault injection: no live Resend, backup, systemd or database calls."""
from datetime import datetime, timedelta, timezone
import fcntl
import json
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import backup_alerts as a
except ImportError:
    import backup_alerts as a


class BackupAlertsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.alerts = self.root / 'alerts'
        self.alerts.mkdir(mode=0o700)
        self.config = self.root / 'config.json'
        self.env = self.root / '.env'
        self.backup_monitor = self.root / 'backup-monitor'
        self.backup_monitor.mkdir(mode=0o700)
        for name, value in (('DIRECTORY', self.alerts), ('CONFIG', self.config), ('ENV_FILE', self.env),
                            ('EXTERNAL_CONFIG', self.root / 'external-monitor.json')):
            replacement = patch.object(a, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)
        self.at = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
        self.approved = {'version': 1, 'recipient': a.RECIPIENT, 'enabled': True,
                         'synthetic_only': True, 'test_authorization_id': a.TEST_AUTHORIZATION}
        a.backup.write_private(self.config, json.dumps(self.approved).encode())
        a.backup.write_private(self.env, (
            'QUILLMD_EMAIL_MODE=resend\n'
            'QUILLMD_EMAIL_FROM=QuillMD <noreply@quillmd.com>\n'
            'QUILLMD_EMAIL_VERIFIED_DOMAIN=quillmd.com\n'
            f'QUILLMD_EMAIL_ALLOWED_RECIPIENTS={a.RECIPIENT}\n'
            'QUILLMD_APP_BASE_URL=https://app.quillmd.com:9443\n'
            'RESEND_API_KEY=re_synthetic_not_a_real_key\n'
            'QUILLMD_DB_PASSWORD=DO_NOT_COPY_DATABASE_SECRET\n'
            'QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD=DO_NOT_COPY_PREVIEW_SECRET\n').encode())
        self.sender = patch.object(a, 'email_transport', return_value='synthetic-provider-id').start()
        self.addCleanup(patch.stopall)
        self.health = patch.object(a, 'backup_condition', return_value='healthy').start()
        self.recovery = patch.object(a, 'recovery_status', return_value={
            'condition': 'healthy', 'last_isolated_restore': None}).start()
        patch.object(a, 'local_capture_status', return_value=None).start()

    def write_config(self, **changes):
        self.config.write_text(json.dumps(dict(self.approved, **changes)))

    def test_healthy_check_no_email_and_fresh_actionable_status(self):
        result, code = a.check(self.at)
        self.assertEqual((code, result['condition']), (0, 'healthy'))
        self.sender.assert_not_called()
        self.assertEqual(a.status(self.at + timedelta(minutes=14))[1], 0)
        result, code = a.status(self.at + timedelta(minutes=16))
        self.assertEqual((code, result['condition']), (1, 'monitoring_stale'))
        self.assertIn('timer', result['action'])
        self.assertFalse(result['outside_host_failure_detection'])
        self.assertFalse(result['offsite_recovery_verified'])

    def test_one_alert_per_incident_and_operational_cooldown(self):
        self.health.return_value = 'backup_failed'
        first, code = a.check(self.at)
        second, _ = a.check(self.at + timedelta(minutes=5))
        self.assertEqual(code, 1)
        self.assertEqual(first['alert']['provider_message_id'], second['alert']['provider_message_id'])
        self.sender.assert_called_once()
        self.health.return_value = 'healthy'
        self.assertEqual(a.check(self.at + timedelta(minutes=10))[1], 0)
        self.health.return_value = 'backup_stale'
        result, _ = a.check(self.at + timedelta(minutes=15))
        self.assertEqual(result['alert']['outcome'], 'cooldown_suppressed')
        self.assertEqual(self.sender.call_count, 1)
        a.check(self.at + timedelta(hours=25))
        self.assertEqual(self.sender.call_count, 2)
        self.assertEqual(len(list(self.alerts.glob('incident-*-pending.json'))), 2)

    def test_expiry_approach_is_quiet_but_uncovered_next_run_is_one_warning(self):
        self.recovery.return_value['condition'] = 'offsite_policy_expiring'
        result, code = a.check(self.at)
        self.assertEqual((code, result['severity'], result['healthy']), (0, 'warning', False))
        self.sender.assert_not_called()
        self.recovery.return_value['condition'] = 'offsite_policy_renewal_due'
        result, code = a.check(self.at + timedelta(minutes=5))
        self.assertEqual((code, result['severity']), (0, 'warning'))
        a.check(self.at + timedelta(minutes=10))
        self.sender.assert_called_once()
        self.recovery.return_value['condition'] = 'offsite_policy_expired'
        result, code = a.check(self.at + timedelta(minutes=15))
        self.assertEqual((code, result['severity']), (1, 'failure'))
        self.sender.assert_called_once()

    def test_uncertain_provider_outcome_no_retry_even_after_retention_window(self):
        self.health.return_value = 'backup_failed'
        self.sender.side_effect = RuntimeError('raw provider clinical secret canary')
        result, code = a.check(self.at)
        self.assertEqual((code, result['condition']), (1, 'alert_delivery_unconfirmed'))
        a.check(self.at + timedelta(days=4))
        self.sender.assert_called_once()
        output = ''.join(p.read_text() for p in self.alerts.glob('*.json'))
        self.assertNotIn('canary', output)
        self.assertEqual(a.status(self.at + timedelta(days=4))[0]['condition'], 'alert_delivery_unconfirmed')

    def test_pending_receipt_survives_process_interruption_and_prevents_retry(self):
        self.health.return_value = 'backup_failed'
        self.sender.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            a.check(self.at)
        pending = list(self.alerts.glob('incident-*-pending.json'))
        self.assertEqual(len(pending), 1)
        self.assertFalse(list(self.alerts.glob('incident-*-result.json')))
        self.sender.side_effect = None
        result, code = a.check(self.at + timedelta(minutes=5))
        self.assertEqual((code, result['alert']['outcome']), (1, 'pending'))
        self.sender.assert_called_once()

    def test_crash_before_pending_receipt_fails_closed_without_email(self):
        self.health.return_value = 'backup_failed'
        with patch.object(a, 'attempt_alert', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                a.check(self.at)
        result, code = a.check(self.at + timedelta(minutes=5))
        self.assertEqual((code, result['condition']), (1, 'monitoring_state_unavailable'))
        self.sender.assert_not_called()

    def test_authorized_test_exactly_once_separate_from_normal_backup_and_monitor_status(self):
        sentinel = self.backup_monitor / 'latest.json'
        sentinel.write_text('existing backup status unchanged')
        before = sentinel.read_bytes()
        a.check(self.at)
        monitor_before = (self.alerts / 'status.json').read_bytes()
        result, code = a.test_alert(self.at)
        second, _ = a.test_alert(self.at + timedelta(days=2))
        self.assertEqual(code, 0)
        self.assertTrue(result['alert']['provider_accepted'])
        self.assertFalse(result['alert']['delivery_confirmed'])
        self.assertFalse(result['alert']['inbox_receipt_confirmed'])
        self.assertEqual(second['alert']['provider_message_id'], 'synthetic-provider-id')
        self.sender.assert_called_once()
        self.assertEqual(sentinel.read_bytes(), before)
        self.assertEqual((self.alerts / 'status.json').read_bytes(), monitor_before)
        self.assertIn('NONCLINICAL TEST', self.sender.call_args.args[1])
        self.assertIn('NO BACKUP WAS INTERRUPTED', self.sender.call_args.args[2])

    def test_missing_configuration_is_visible_without_attempt_or_email(self):
        self.config.unlink()
        result, code = a.check(self.at)
        self.assertEqual((code, result['condition']), (1, 'alert_configuration_unavailable'))
        self.assertEqual(a.status(self.at)[0]['condition'], 'alert_configuration_unavailable')
        self.assertFalse(list(self.alerts.glob('*pending.json')))
        self.sender.assert_not_called()

    def test_accepted_receipt_without_provider_id_refuses_without_resend(self):
        self.assertEqual(a.test_alert(self.at)[1], 0)
        path = self.alerts / f'test-{a.TEST_AUTHORIZATION}-result.json'
        value = json.loads(path.read_text())
        value['provider_message_id'] = None
        path.write_text(json.dumps(value))
        result, code = a.test_alert(self.at + timedelta(days=2))
        self.assertEqual((code, result['condition']), (1, 'monitoring_state_unavailable'))
        self.sender.assert_called_once()

    def test_orphaned_accepted_result_prevents_resend_after_pending_marker_is_lost(self):
        self.assertEqual(a.test_alert(self.at)[1], 0)
        pending = self.alerts / f'test-{a.TEST_AUTHORIZATION}-pending.json'
        pending.unlink()
        result, code = a.test_alert(self.at + timedelta(days=2))
        self.assertEqual((code, result['alert']['outcome']), (0, 'provider_accepted'))
        self.sender.assert_called_once()

    def test_orphaned_malformed_result_also_suppresses_send_and_raw_content(self):
        path = self.alerts / f'test-{a.TEST_AUTHORIZATION}-result.json'
        a.backup.write_private(path, b'private-clinical-canary')
        result, code = a.test_alert(self.at)
        self.assertEqual((code, result['condition']), (1, 'monitoring_state_unavailable'))
        self.assertNotIn('canary', json.dumps(result))
        self.sender.assert_not_called()

    def test_lost_mutable_state_with_durable_incident_evidence_refuses_resend(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        (self.alerts / 'status.json').unlink()
        result, code = a.check(self.at + timedelta(days=2))
        self.assertEqual((code, result['condition']), (1, 'monitoring_state_unavailable'))
        self.sender.assert_called_once()

    def test_malformed_receipt_schema_and_timestamps_do_not_produce_acceptance(self):
        self.assertEqual(a.test_alert(self.at)[1], 0)
        path = self.alerts / f'test-{a.TEST_AUTHORIZATION}-result.json'
        original = json.loads(path.read_text())
        for changes in ({'provider_accepted': 1}, {'attempted_at': 'not-a-date'},
                        {'format': True}, {'unexpected': 'private-canary'}, {'kind': 'operational'},
                        {'kind': 'operational', 'condition': 'backup_failed'}):
            with self.subTest(changes=changes):
                path.write_text(json.dumps(dict(original, **changes)))
                self.assertEqual(a.test_alert(self.at)[0]['condition'], 'monitoring_state_unavailable')
        self.sender.assert_called_once()

    def test_rejects_unapproved_recipient_disabled_alerts_and_unapproved_test_authorization(self):
        for changes in ({'recipient': 'somebody@example.invalid'}, {'enabled': False},
                        {'test_authorization_id': 'invented'}, {'synthetic_only': 1}):
            with self.subTest(changes=changes):
                self.write_config(**changes)
                self.assertEqual(a.test_alert(self.at)[0]['condition'], 'alert_configuration_unavailable')
        self.sender.assert_not_called()

    def test_config_and_env_must_be_private_regular_files(self):
        self.config.chmod(0o644)
        self.assertEqual(a.check(self.at)[0]['condition'], 'alert_configuration_unavailable')
        self.config.chmod(0o600)
        target = self.env.with_name('preserved.env')
        self.env.rename(target)
        self.env.symlink_to(target)
        self.assertEqual(a.test_alert(self.at)[0]['condition'], 'alert_configuration_unavailable')
        self.sender.assert_not_called()

    def test_minimal_email_settings_exclude_db_and_preview_secrets_without_interpolation(self):
        values = a.read_configuration()
        self.assertNotIn('QUILLMD_DB_PASSWORD', values)
        self.assertEqual(values['QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD'], '')
        self.assertNotIn('DO_NOT_COPY', repr(values))
        self.assertEqual(values['QUILLMD_RESEND_ENV_FILE'], '')

    def test_invalid_sender_origin_and_recipient_allowlist_fail_before_send(self):
        original = self.env.read_text()
        replacements = [('noreply@quillmd.com', 'noreply@unapproved.invalid'),
                        ('https://app.quillmd.com:9443', 'http://app.quillmd.com:9443'),
                        (a.RECIPIENT, a.RECIPIENT + ',somebody@example.invalid')]
        for old, new in replacements:
            with self.subTest(old=old):
                self.env.write_text(original.replace(old, new))
                self.assertEqual(a.check(self.at)[0]['condition'], 'alert_configuration_unavailable')
        self.sender.assert_not_called()

    def test_parallel_checker_refuses_without_touching_state(self):
        a.check(self.at)
        before = (self.alerts / 'status.json').read_bytes()
        descriptor = os.open(self.alerts / 'monitor.lock', os.O_RDWR)
        self.addCleanup(os.close, descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result, code = a.check(self.at)
        self.assertEqual((code, result['condition']), (1, 'monitoring_state_unavailable'))
        self.assertEqual((self.alerts / 'status.json').read_bytes(), before)
        self.sender.assert_not_called()

    def test_unsafe_directory_or_lock_is_visible_without_email(self):
        self.alerts.chmod(0o755)
        self.assertEqual(a.check(self.at)[0]['condition'], 'monitoring_state_unavailable')
        self.alerts.chmod(0o700)
        target = self.root / 'untouched'; target.write_text('preserved')
        (self.alerts / 'monitor.lock').symlink_to(target)
        self.assertEqual(a.check(self.at)[0]['condition'], 'monitoring_state_unavailable')
        self.assertEqual(target.read_text(), 'preserved')
        self.sender.assert_not_called()

    def test_unknown_state_and_receipt_content_never_reaches_operator_output(self):
        a.backup.write_private(self.alerts / 'status.json', b'{"condition":"private-clinical-canary"}')
        result, code = a.check(self.at)
        self.assertEqual(code, 1)
        self.assertNotIn('canary', json.dumps(result))
        self.sender.assert_not_called()

    def test_all_generated_metadata_private(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        for path in self.alerts.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_prepared_inactive_offsite_is_visible_without_unsolicited_test_or_operational_email(self):
        self.recovery.return_value['condition'] = 'offsite_pending_configuration'
        result, code = a.check(self.at)
        self.assertEqual((result['condition'], code), ('offsite_pending_configuration', 1))
        self.assertIn('not activated', result['action'])
        self.assertFalse(result['healthy'])
        self.sender.assert_not_called()

    def test_actual_offsite_failure_uses_existing_nonclinical_route_without_duplicate_attempt(self):
        for condition in ('offsite_capacity_refused', 'offsite_upload_failed',
                          'offsite_decryption_failed', 'offsite_integrity_failed'):
            with self.subTest(condition=condition):
                self.recovery.return_value['condition'] = condition
                result, code = a.check(self.at)
                self.assertEqual((result['condition'], code), (condition, 1))
                self.assertTrue(result['alert']['provider_accepted'])
                self.assertFalse(result['alert']['delivery_confirmed'])
                self.assertFalse(result['alert']['inbox_receipt_confirmed'])
                self.assertFalse(result['outside_host_failure_detection'])
        self.sender.assert_called_once()
        self.assertIn('Condition: offsite_capacity_refused', self.sender.call_args.args[2])
        self.assertNotIn('clinical-canary', self.sender.call_args.args[2])

    def test_local_failure_takes_priority_while_remote_status_remains_visible(self):
        self.health.return_value = 'backup_failed'
        self.recovery.return_value['condition'] = 'offsite_capacity_refused'
        result, _ = a.check(self.at)
        self.assertEqual(result['condition'], 'backup_failed')
        self.assertEqual(result['offsite']['condition'], 'offsite_capacity_refused')

    def test_status_rechecks_remote_staleness_without_sending_email(self):
        a.check(self.at)
        self.recovery.return_value['condition'] = 'offsite_stale'
        result, code = a.status(self.at + timedelta(minutes=5))
        self.assertEqual((result['condition'], code), ('offsite_stale', 1))
        self.sender.assert_not_called()

    def test_status_rechecks_local_staleness_without_waiting_for_next_alert_tick(self):
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        result, code = a.status(self.at + timedelta(minutes=1))
        self.assertEqual((result['condition'], code), ('backup_stale', 1))
        self.sender.assert_not_called()

    def test_status_surfaces_newly_invalid_external_configuration_without_send(self):
        a.check(self.at)
        a.backup.write_private(self.root / 'external-monitor.json', b'{}')
        result, code = a.status(self.at + timedelta(minutes=1))
        self.assertEqual((result['condition'], code), ('external_monitor_unconfirmed', 1))
        self.assertFalse(result['healthy'])
        self.sender.assert_not_called()


class RecoveryStageTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name)
        self.directory.chmod(0o700)
        patch.object(a, 'OFFSITE_DIRECTORY', self.directory).start()
        patch.object(a, 'next_timer_run', return_value=None).start()
        patch.object(a, 'allowance_status', return_value={'eligible': False, 'reason': 'policy_missing'}).start()
        self.units = patch.object(a, 'offsite_systemd_state', return_value={
            'active': True, 'enabled': True}).start()
        self.service = patch.object(a, 'offsite_service_state', return_value={
            'active_state': 'inactive', 'result': 'success', 'failed': False}).start()
        self.policy = patch.object(a, 'offsite_policy_condition', return_value=None).start()
        self.addCleanup(patch.stopall)
        self.at = datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc)
        identity = {'run_id': '20260920T095332Z-a9da0017', 'manifest_cipher_sha256': 'a' * 64}
        self.state = {'version': 1, 'state': 'complete', 'reason_code': None,
                      'started_at': (self.at - timedelta(hours=1)).isoformat(),
                      'finished_at': self.at.isoformat(),
                      'last_remote_complete': dict(identity, completed_at=self.at.isoformat(),
                                                   object_count=44, cipher_bytes=14422252),
                      'last_verified_readback': dict(identity, verified_at=self.at.isoformat(),
                                                     object_count=44, cipher_bytes=14422252),
                      'last_isolated_restore': dict(identity, verified_at=self.at.isoformat(),
                                                    table_count=35, row_count=225615, file_count=42,
                                                    source='vps_key')}
        self.path = self.directory / 'status.json'
        a.backup.write_private(self.path, json.dumps(self.state).encode())

    def write(self):
        self.path.write_text(json.dumps(self.state))

    def test_remote_completion_readback_and_restore_are_distinct_with_custody_still_pending(self):
        result = a.recovery_status(self.at)
        self.assertEqual(result['condition'], 'healthy')
        self.assertEqual(result['last_remote_complete']['object_count'], 44)
        self.assertEqual(result['last_verified_readback']['cipher_bytes'], 14422252)
        self.assertEqual(result['last_isolated_restore']['row_count'], 225615)
        self.assertFalse(result['independent_key_custody_verified'])
        self.assertTrue(a.report('healthy', recovery=result)['offsite_recovery_verified'])
        self.assertFalse(a.report('healthy', recovery=result)['outside_host_failure_detection'])

    def test_seeded_historical_manual_evidence_remains_visible_while_recurrence_pending(self):
        self.state['state'] = 'pending_configuration'
        self.units.return_value = {'active': False, 'enabled': False}
        self.write()
        result = a.recovery_status(self.at)
        self.assertEqual(result['condition'], 'offsite_pending_configuration')
        self.assertIsNotNone(result['last_isolated_restore'])
        self.assertIsNotNone(result['last_verified_readback'])

    def test_new_remote_backup_does_not_erase_earlier_independent_key_restore(self):
        prior = self.state['last_isolated_restore']['run_id']
        self.state['last_isolated_restore']['source'] = 'independently_retrieved_key'
        for key in ('last_remote_complete', 'last_verified_readback'):
            self.state[key].update(run_id='20260920T193915Z-aabbccdd', manifest_cipher_sha256='b' * 64)
        self.write()
        result = a.recovery_status(self.at)
        self.assertEqual(result['condition'], 'healthy')
        self.assertTrue(result['independent_key_custody_verified'])
        self.assertEqual(result['last_isolated_restore']['run_id'], prior)
        self.assertNotEqual(result['last_isolated_restore']['run_id'], result['last_remote_complete']['run_id'])

    def test_failed_systemd_service_cannot_hide_behind_last_complete_record(self):
        self.service.return_value = {'active_state': 'failed', 'result': 'oom-kill', 'failed': True}
        result = a.recovery_status(self.at)
        self.assertEqual(result['condition'], 'offsite_upload_failed')
        self.assertIsNotNone(result['last_remote_complete'])

    def test_next_daily_run_outside_evidence_is_an_actionable_renewal_warning(self):
        with patch.object(a, 'next_timer_run', return_value='2026-09-21T05:00:00+00:00'), \
             patch.object(a, 'allowance_status', return_value={'eligible': True,
                          'valid_until': '2026-09-21T05:15:00+00:00'}):
            result = a.recovery_status(self.at)
            self.assertEqual(result['condition'], 'offsite_policy_renewal_due')
            self.assertFalse(result['next_run_covered_by_policy'])
        with patch.object(a, 'next_timer_run', return_value='2026-09-21T05:00:00+00:00'), \
             patch.object(a, 'allowance_status', return_value={'eligible': True,
                          'valid_until': '2026-09-21T20:16:35+00:00'}):
            self.assertTrue(a.recovery_status(self.at)['next_run_covered_by_policy'])

    def test_expired_evidence_is_failure_while_prior_backup_proof_remains_current(self):
        with patch.object(a, 'allowance_status', return_value={
                'eligible': False, 'reason': 'policy_expired',
                'observed_at': (self.at-timedelta(days=1)).isoformat(),
                'valid_until': self.at.isoformat()}):
            result = a.recovery_status(self.at)
            self.assertEqual(result['condition'], 'offsite_policy_expired')
            self.assertEqual(result['current_backup_health'], 'healthy')
            self.assertIsNotNone(result['last_isolated_restore'])
            self.assertEqual(a.report(result['condition'], recovery=result)['severity'], 'failure')

    def test_failed_renewal_keeps_deadline_and_is_visible_before_expiry(self):
        with patch.object(a, 'renewal_status', return_value={'state': 'failed', 'reason_code': 'audit_failed'}):
            result = a.recovery_status(self.at)
            self.assertEqual(result['condition'], 'offsite_renewal_failed')
            self.assertEqual(result['renewal']['reason_code'], 'audit_failed')
            self.assertEqual(result['current_backup_health'], 'healthy')

    def test_next_day_reserved_budget_shortfall_warns_without_warning_for_today_only(self):
        allowance = {'eligible': True, 'valid_until': '2026-09-21T20:16:35+00:00',
                     'daily_request_budget': 500, 'daily_download_budget_bytes': 100_000_000}
        old = {'requests': 422, 'download_bytes': 98_474_544}
        ledger = dict(version=2, day='2026-09-20', **old, days={'2026-09-20': old},
                      legacy_import=None, external_reservations=[])
        path = self.directory / 'budget.json'
        a.backup.write_private(path, json.dumps(ledger).encode())
        with patch.object(a, 'next_timer_run', return_value='2026-09-21T05:00:00+00:00'), \
             patch.object(a, 'allowance_status', return_value=allowance):
            self.assertEqual(a.recovery_status(self.at)['condition'], 'healthy')
            ledger['days']['2026-09-21'] = {'requests': 480, 'download_bytes': 90_000_000}
            path.write_text(json.dumps(ledger))
            result = a.recovery_status(self.at)
            self.assertEqual(result['condition'], 'offsite_next_run_budget_low')
            self.assertEqual(result['current_backup_health'], 'healthy')
            self.assertFalse(result['next_run_admission']['same_size_cycle_fits'])
            self.assertEqual(a.report(result['condition'])['severity'], 'warning')

    def test_controlled_success_and_timer_enablement_never_invent_scheduled_success(self):
        result = a.recovery_status(self.at)
        self.assertIsNone(result['last_successful_scheduled_run'])
        self.assertFalse(result['latest_execution']['scheduled_success_verified'])
        self.assertEqual(result['latest_execution']['origin'], 'not_recorded')
        self.assertTrue(result['recurrence_active'])
        self.state['invocation'] = dict(source='systemd_environment', systemd_invocation_id='a' * 32,
                                        timer_trigger_verified=False)
        self.write()
        result = a.recovery_status(self.at)
        self.assertEqual(result['latest_execution']['systemd_invocation_id'], 'a' * 32)
        self.assertIsNone(result['last_successful_scheduled_run'])
        self.state['invocation']['timer_trigger_verified'] = True
        self.write()
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_status_unavailable')

    def test_low_capacity_is_an_observed_scope_estimate_not_a_future_or_account_claim(self):
        self.state['last_capacity'] = {'observed_at': self.at.isoformat(),
                'scope_stored_bytes_after': 990_000_000, 'scope_ceiling_bytes': 1_000_000_000,
                'last_complete_cipher_bytes': 14_422_252}
        self.write()
        result = a.recovery_status(self.at)
        self.assertEqual(result['condition'], 'offsite_capacity_low')
        self.assertEqual(result['capacity']['remaining_scope_bytes_at_observation'], 10_000_000)
        self.assertFalse(result['capacity']['future_backup_size_known'])
        self.assertFalse(result['capacity']['account_wide_usage_measurement'])
        self.assertEqual(result['capacity']['estimated_additional_daily_backups_of_same_size'], 0)
        self.assertIsNotNone(result['last_remote_complete'])
        self.state['last_capacity']['observed_at'] = (self.at + timedelta(seconds=1)).isoformat()
        self.write()
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_status_unavailable')

    def test_manual_cleanup_failure_and_stalled_restore_are_visible_without_erasing_prior_proof(self):
        manual = {'version': 1, 'action': 'isolated_restore', 'attempt': '20260920T175000Z-12345678',
                  'state': 'failed', 'reason_code': 'cleanup_failed',
                  'started_at': (self.at - timedelta(minutes=10)).isoformat(),
                  'finished_at': self.at.isoformat(), 'run_id': self.state['last_isolated_restore']['run_id'],
                  'manifest_cipher_sha256': 'a' * 64, 'restore_verified': True, 'shared_accounting': True}
        path = self.directory / 'manual-status.json'
        a.backup.write_private(path, json.dumps(manual).encode())
        result = a.recovery_status(self.at)
        self.assertEqual(result['condition'], 'offsite_cleanup_failed')
        self.assertIsNotNone(result['last_isolated_restore'])
        with patch.object(a, 'next_timer_run', return_value='2026-09-21T05:00:00+00:00'), \
             patch.object(a, 'allowance_status', return_value={
                'eligible': True, 'valid_until': '2026-09-21T05:15:00+00:00'}):
            self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_cleanup_failed')
        manual.update(state='running', reason_code=None, restore_verified=False)
        manual.pop('finished_at'); path.write_text(json.dumps(manual))
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_in_progress')
        self.assertEqual(a.recovery_status(self.at + timedelta(minutes=6))['condition'], 'offsite_timeout')
        manual['private_canary'] = 'never-output'; path.write_text(json.dumps(manual))
        result = a.recovery_status(self.at)
        self.assertEqual(result['condition'], 'offsite_status_unavailable')
        self.assertNotIn('canary', json.dumps(result))

    def test_complete_upload_without_matching_readback_is_not_fully_healthy(self):
        for change in ({'last_verified_readback': None},
                       {'last_verified_readback': dict(self.state['last_verified_readback'],
                                                       manifest_cipher_sha256='b' * 64)}):
            with self.subTest(change=change):
                self.state.update(change); self.write()
                result = a.recovery_status(self.at)
                self.assertEqual(result['condition'], 'offsite_readback_stale')
                self.assertIsNotNone(result['last_remote_complete'])

    def test_stale_remote_does_not_reuse_local_capture_or_new_restore_timestamp(self):
        self.assertEqual(a.recovery_status(self.at + timedelta(hours=31))['condition'], 'offsite_stale')

    def test_failure_preserves_last_complete_and_restore(self):
        for reason, expected in [('capacity_refused', 'offsite_capacity_refused'),
                                 ('policy_missing', 'offsite_policy_unavailable'),
                                 ('budget_exhausted', 'offsite_budget_refused'),
                                 ('local_authentication_failed', 'offsite_decryption_failed'),
                                 ('remote_corrupt', 'offsite_integrity_failed'),
                                 ('transport_failed', 'offsite_upload_failed'),
                                 ('cleanup_failed', 'offsite_cleanup_failed'),
                                 ('deadline', 'offsite_timeout')]:
            with self.subTest(reason=reason):
                self.state.update(state='refused', reason_code=reason); self.write()
                result = a.recovery_status(self.at)
                self.assertEqual(result['condition'], expected)
                self.assertIsNotNone(result['last_remote_complete'])
                self.assertIsNotNone(result['last_isolated_restore'])

    def test_running_bound_and_disabled_schedule_are_separate(self):
        self.state.update(state='running', started_at=self.at.isoformat()); self.write()
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_in_progress')
        self.assertEqual(a.recovery_status(self.at + timedelta(seconds=1201))['condition'], 'offsite_timeout')
        self.state['state'] = 'complete'; self.write()
        self.units.return_value['enabled'] = False
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_schedule_unavailable')

    def test_contradictory_success_and_lock_refusal_cannot_report_healthy(self):
        self.state['reason_code'] = 'transport_failed'; self.write()
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_status_unavailable')
        self.state.update(state='refused', reason_code='lock_busy'); self.write()
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_upload_failed')

    def test_newer_prelock_failure_is_visible_but_concurrency_loser_does_not_hide_success(self):
        name = '20260920T180001Z-abcdef01'
        at = self.at + timedelta(seconds=1)
        attempt = {'version': 1, 'attempt': name, 'state': 'refused',
                   'reason_code': 'state_invalid', 'finished_at': at.isoformat()}
        path = self.directory / (name + '.json')
        a.backup.write_private(path, json.dumps(attempt).encode())
        self.assertEqual(a.recovery_status(at)['condition'], 'offsite_status_unavailable')
        attempt['reason_code'] = 'lock_busy'; path.write_text(json.dumps(attempt))
        self.assertEqual(a.recovery_status(at)['condition'], 'healthy')

    def test_missing_or_expired_policy_cannot_hide_behind_recent_remote_success(self):
        self.policy.return_value = 'offsite_policy_unavailable'
        result = a.recovery_status(self.at)
        self.assertEqual(result['condition'], 'offsite_policy_unavailable')
        self.assertIsNotNone(result['last_remote_complete'])
        self.state.update(state='pending_configuration', reason_code='pending_configuration'); self.write()
        self.units.return_value = {'active': False, 'enabled': False}
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_pending_configuration')

    def test_current_runner_precedes_older_history_and_malformed_attempt_is_redacted(self):
        name = '20260920T180001Z-abcdef01'
        at = self.at + timedelta(seconds=1)
        attempt = {'version': 1, 'attempt': name, 'state': 'refused',
                   'reason_code': 'state_invalid', 'finished_at': at.isoformat()}
        path = self.directory / (name + '.json')
        a.backup.write_private(path, json.dumps(attempt).encode())
        self.state.update(state='running', started_at=(at + timedelta(seconds=1)).isoformat())
        self.state.pop('finished_at'); self.write()
        self.assertEqual(a.recovery_status(at + timedelta(seconds=2))['condition'], 'offsite_in_progress')
        attempt['reason_code'] = 'private-clinical-canary'; path.write_text(json.dumps(attempt))
        result = a.recovery_status(at + timedelta(seconds=2))
        self.assertEqual(result['condition'], 'offsite_status_unavailable')
        self.assertNotIn('canary', json.dumps(result))

    def test_wrong_types_unknown_values_and_future_timestamps_fail_closed_without_disclosure(self):
        original = json.loads(json.dumps(self.state))
        for field, replacement in [('version', True), ('state', 'private-clinical-canary'),
                                   ('reason_code', 'private-secret-canary'),
                                   ('last_remote_complete', dict(original['last_remote_complete'],
                                                                 object_count=True)),
                                   ('last_remote_complete', dict(original['last_remote_complete'],
                                                                 private_secret='never-output')),
                                   ('last_remote_complete', dict(original['last_remote_complete'],
                                                                 completed_at=(self.at + timedelta(seconds=1)).isoformat()))]:
            with self.subTest(field=field):
                self.state = dict(original, **{field: replacement}); self.write()
                result = a.recovery_status(self.at)
                self.assertEqual(result['condition'], 'offsite_status_unavailable')
                self.assertNotIn('canary', json.dumps(result))
                self.assertNotIn('never-output', json.dumps(result))

    def test_private_mode_regular_file_and_directory_constraints_fail_closed(self):
        self.path.chmod(0o644)
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_status_unavailable')
        self.path.chmod(0o600)
        preserved = self.directory / 'preserved'
        self.path.rename(preserved); self.path.symlink_to(preserved)
        self.assertEqual(a.recovery_status(self.at)['condition'], 'offsite_status_unavailable')
        self.assertEqual(json.loads(preserved.read_text()), self.state)

    def test_missing_or_malformed_evidence_never_infers_completion(self):
        self.path.unlink()
        result = a.recovery_status(self.at)
        self.assertEqual(result['condition'], 'offsite_status_unavailable')
        self.assertIsNone(result['last_remote_complete'])
        a.backup.write_private(self.path, b'private-parse-failure-canary')
        self.assertNotIn('canary', json.dumps(a.recovery_status(self.at)))

class HealthConditionsTests(unittest.TestCase):
    def setUp(self):
        self.at = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)

    def test_in_progress_within_bound_is_not_alerted_even_if_previous_service_result_failed(self):
        with patch.object(a, 'systemd_state', return_value={'active': True, 'enabled': True, 'service': False}), \
             patch.object(a.scheduled, 'status', return_value={'latest_outcome': 'running', 'healthy': False}), \
             patch.object(a.scheduled, 'previous', return_value={'started_at': self.at.isoformat()}):
            self.assertEqual(a.backup_condition(self.at + timedelta(seconds=599)), 'backup_in_progress')
            self.assertEqual(a.backup_condition(self.at + timedelta(seconds=601)), 'backup_timeout')

    def test_failed_schedule_stale_and_missing_status_are_distinct(self):
        with patch.object(a, 'systemd_state', return_value={'active': True, 'enabled': True, 'service': True}) as unit, \
             patch.object(a.scheduled, 'status') as status:
            for outcome, expected in [('failed', 'backup_failed'), ('complete', 'backup_stale'),
                                      ('missing_or_invalid', 'backup_status_unavailable')]:
                status.return_value = {'latest_outcome': outcome, 'healthy': False}
                self.assertEqual(a.backup_condition(self.at), expected)
            unit.return_value['active'] = False
            self.assertEqual(a.backup_condition(self.at), 'backup_schedule_unavailable')

    def test_systemd_output_is_whitelisted_and_subprocess_failure_redacted(self):
        with patch.object(a.subprocess, 'run', return_value=SimpleNamespace(returncode=0,
                          stdout=b'private-service-canary', stderr=b'private-key-canary')) as run:
            self.assertEqual(a.systemd_state(), {'active': False, 'enabled': False, 'service': False})
            self.assertEqual(run.call_count, 3)
            self.assertEqual(set(run.call_args.kwargs['env']), {'PATH', 'LC_ALL'})
        with patch.object(a, 'systemd_state', side_effect=RuntimeError('secret-canary')):
            self.assertEqual(a.backup_condition(self.at), 'backup_status_unavailable')

    def test_offsite_systemd_output_is_whitelisted(self):
        with patch.object(a.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout=b'private-service-canary', stderr=b'private-canary')) as run:
            self.assertEqual(a.offsite_systemd_state(), {'active': False, 'enabled': False})
            self.assertEqual(run.call_count, 2)
            self.assertEqual(set(run.call_args.kwargs['env']), {'PATH', 'LC_ALL'})

    def test_offsite_service_failure_is_explicit_and_unknown_output_is_redacted(self):
        with patch.object(a.subprocess, 'run', return_value=SimpleNamespace(
                returncode=0, stdout=b'ActiveState=failed\nResult=timeout\n')) as run:
            self.assertEqual(a.offsite_service_state(),
                             {'active_state': 'failed', 'result': 'timeout', 'failed': True})
            run.return_value.stdout = b'ActiveState=private-canary\nResult=success\n'
            with self.assertRaises(RuntimeError):
                a.offsite_service_state()

    def test_policy_recheck_performs_no_http_and_redacts_validation_errors(self):
        try:
            from . import automatic_offsite as engine
        except ImportError:
            import automatic_offsite as engine
        with patch.object(engine, 'policy', side_effect=RuntimeError('private-policy-canary')) as policy, \
             patch.object(engine.requests, 'Session') as session:
            self.assertEqual(a.offsite_policy_condition(self.at), 'offsite_policy_unavailable')
            policy.assert_called_once_with(at=self.at)
            session.assert_not_called()

    def test_future_running_timestamp_fails_closed(self):
        with patch.object(a, 'systemd_state', return_value={'active': True, 'enabled': True, 'service': True}), \
             patch.object(a.scheduled, 'status', return_value={'latest_outcome': 'running'}), \
             patch.object(a.scheduled, 'previous', return_value={'started_at': (self.at + timedelta(minutes=1)).isoformat()}):
            self.assertEqual(a.backup_condition(self.at), 'backup_timeout')


class ExistingResendTransportTests(unittest.TestCase):
    def test_real_backend_called_with_fixture_http_and_no_private_preview_fields(self):
        values = dict(QUILLMD_EMAIL_MODE='resend', QUILLMD_APP_BASE_URL='https://app.quillmd.com:9443',
                      ALLOWED_HOSTS=['app.quillmd.com'], RESEND_API_KEY='re_fixture_never_live',
                      QUILLMD_EMAIL_FROM='QuillMD <noreply@quillmd.com>',
                      QUILLMD_RESEND_ENV_FILE='', QUILLMD_EMAIL_VERIFIED_DOMAIN='quillmd.com',
                      QUILLMD_EMAIL_ALLOWED_RECIPIENTS=a.RECIPIENT,
                      QUILLMD_EMAIL_PRIVATE_ACCESS_USERNAME='', QUILLMD_EMAIL_PRIVATE_ACCESS_PASSWORD='',
                      DEFAULT_CHARSET='utf-8')
        with a.configured_transport(values) as transport:
            with patch.object(transport.httpx, 'post', return_value=SimpleNamespace(status_code=200,
                       json=lambda: {'id': 'fixture-provider-id'})) as post:
                result = a.email_transport(values, '[QuillMD NONCLINICAL TEST]', 'Fixture only; no real send.')
        self.assertEqual(result, 'fixture-provider-id')
        post.assert_called_once()
        self.assertEqual(post.call_args.kwargs['json']['to'], [a.RECIPIENT])
        self.assertTrue(post.call_args.kwargs['headers']['Idempotency-Key'].startswith('quillmd-account/'))
        self.assertFalse(post.call_args.kwargs['follow_redirects'])


class ExternalHeartbeatTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / 'external-monitor.json'
        patch.object(a, 'DIRECTORY', self.root).start()
        patch.object(a, 'EXTERNAL_CONFIG', self.config).start()
        self.http = patch.object(a.requests, 'Session').start()
        self.session = self.http.return_value.__enter__.return_value
        self.response = self.session.get.return_value.__enter__.return_value
        self.response.status_code = 200
        self.response.raw.read.return_value = b'OK'
        self.addCleanup(patch.stopall)
        self.at = datetime(2026, 9, 20, 20, 0, tzinfo=timezone.utc)
        self.value = {'version': 1, 'provider': 'healthchecks.io', 'synthetic_only': True,
                      'owner_approval_reference': 'synthetic-approved-fixture',
                      'check_url': 'https://hc-ping.com/00000000-0000-4000-8000-000000000000'}

    def configure(self):
        a.backup.write_private(self.config, json.dumps(self.value).encode())

    def test_absent_configuration_and_unhealthy_readonly_checks_never_send(self):
        self.assertEqual(a.external_heartbeat(self.at, healthy=True, execute=True)['outcome'], 'not_configured')
        self.configure()
        for kwargs in ({}, {'healthy': True}, {'execute': True}):
            self.assertEqual(a.external_heartbeat(self.at, **kwargs)['outcome'], 'not_attempted')
        self.http.assert_not_called()

    def test_one_bounded_tls_ping_per_period_and_no_secret_in_record(self):
        self.configure()
        first = a.external_heartbeat(self.at, healthy=True, execute=True)
        second = a.external_heartbeat(self.at + timedelta(seconds=299), healthy=True, execute=True)
        self.assertTrue(first['provider_accepted'])
        self.assertEqual(second, dict(first, stale=False))
        self.session.get.assert_called_once()
        self.assertFalse(self.session.trust_env)
        self.assertEqual(self.session.get.call_args.kwargs['timeout'], (3, 5))
        self.assertFalse(self.session.get.call_args.kwargs['allow_redirects'])
        self.assertTrue(self.session.get.call_args.kwargs['stream'])
        self.response.raw.read.assert_called_once_with(3, decode_content=False)
        self.assertFalse(first['missed_heartbeat_alert_verified'])
        self.assertFalse(first['human_inbox_confirmed'])
        self.assertNotIn('hc-ping', (self.root / 'external-heartbeat.json').read_text())
        a.external_heartbeat(self.at + timedelta(seconds=300), healthy=True, execute=True)
        self.assertEqual(self.session.get.call_count, 2)

    def test_provider_200_not_found_or_rate_limit_is_not_acceptance(self):
        self.configure()
        for index, body in enumerate((b'OK (not found)', b'OK (rate limited)', b'x' * 33, b'')):
            self.response.raw.read.return_value = body
            result = a.external_heartbeat(self.at + timedelta(seconds=index * 300), healthy=True, execute=True)
            self.assertEqual(result['outcome'], 'uncertain_no_retry')
            self.assertFalse(result['provider_accepted'])

    def test_redirect_error_and_exception_do_not_leak_and_do_not_retry(self):
        self.configure()
        self.response.status_code = 302
        result = a.external_heartbeat(self.at, healthy=True, execute=True)
        self.assertEqual(result['outcome'], 'uncertain_no_retry')
        self.response.raw.read.assert_not_called()
        self.session.get.side_effect = RuntimeError('private-url-canary')
        result = a.external_heartbeat(self.at + timedelta(minutes=5), healthy=True, execute=True)
        self.assertNotIn('canary', json.dumps(result))
        a.external_heartbeat(self.at + timedelta(minutes=6), healthy=True, execute=True)
        self.assertEqual(self.session.get.call_count, 2)

    def test_interrupt_reserves_period_before_request(self):
        self.configure()
        self.session.get.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            a.external_heartbeat(self.at, healthy=True, execute=True)
        result = a.external_heartbeat(self.at + timedelta(seconds=60), healthy=True, execute=True)
        self.assertEqual(result['outcome'], 'pending')
        self.session.get.assert_called_once()

    def test_endpoint_variants_and_unapproved_configuration_refused_before_http(self):
        self.configure()
        for change in ({'version': True}, {'synthetic_only': 1}, {'owner_approval_reference': ''},
                       {'provider': 'unknown'}, {'unexpected': 'private-canary'},
                       *({'check_url': url} for url in ('http://hc-ping.com/a',
                           self.value['check_url'] + '?create=1', self.value['check_url'] + '/fail',
                           self.value['check_url'].replace('hc-ping.com', 'hc-ping.com.evil.invalid'),
                           self.value['check_url'].replace('hc-ping.com', 'secret@hc-ping.com'),
                           self.value['check_url'].replace('hc-ping.com', 'hc-ping.com:443')))):
            with self.subTest(change=change):
                self.config.write_text(json.dumps(dict(self.value, **change)))
                result = a.external_heartbeat(self.at, healthy=True, execute=True)
                self.assertEqual(result['outcome'], 'configuration_or_state_invalid')
                self.assertNotIn('canary', json.dumps(result))
        self.http.assert_not_called()

    def test_nonprivate_symlink_and_hardlink_configuration_refused(self):
        self.configure()
        self.config.chmod(0o644)
        self.assertEqual(a.external_heartbeat(self.at)['outcome'], 'configuration_or_state_invalid')
        self.config.chmod(0o600)
        extra = self.root / 'copy'
        os.link(self.config, extra)
        self.assertEqual(a.external_heartbeat(self.at)['outcome'], 'configuration_or_state_invalid')
        extra.unlink()
        self.config.rename(extra)
        self.config.symlink_to(extra)
        self.assertEqual(a.external_heartbeat(self.at)['outcome'], 'configuration_or_state_invalid')
        self.http.assert_not_called()


class OperatorVisibilityTests(unittest.TestCase):
    def test_renewal_adapter_exposes_only_valid_local_handoff_status(self):
        try:
            from . import offsite_renewal
        except ImportError:
            import offsite_renewal
        at = datetime(2026, 9, 20, 22, tzinfo=timezone.utc)
        value = {'state': 'awaiting_external_audit', 'last_attempt_at': at.isoformat(),
                 'last_successful_observation_at': (at-timedelta(hours=2)).isoformat(),
                 'valid_until': (at+timedelta(hours=22)).isoformat(),
                 'reason_code': 'audit_access_unavailable', 'ticket_id': 'a'*32,
                 'unattended_available': False, 'required_access': 'separate_account_wide_read_only_audit',
                 'failure_does_not_extend_validity': True}
        with patch.object(offsite_renewal, 'renewal_status', return_value=value) as reader:
            self.assertEqual(a.renewal_status(at), value)
            for changes in ({'reason_code': 'private-secret-canary'}, {'unattended_available': True},
                            {'ticket_id': 'unprotected-path-canary'},
                            {'last_attempt_at': (at+timedelta(seconds=1)).isoformat()}):
                reader.return_value = dict(value, **changes)
                result = a.renewal_status(at)
                self.assertEqual(result['state'], 'unavailable')
                self.assertNotIn('canary', json.dumps(result))
            reader.return_value = dict(value, state='importing', reason_code=None)
            self.assertEqual(a.renewal_status(at + timedelta(minutes=4))['state'], 'importing')
            stale = a.renewal_status(at + timedelta(minutes=6))
            self.assertEqual((stale['state'], stale['reason_code']), ('failed', 'state_invalid'))

    def test_capture_metadata_cannot_hide_missing_or_changed_encrypted_members(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        run_id = '20260920T225900Z-aabbccdd'
        capture = root / run_id
        capture.mkdir(mode=0o700)
        objects = capture / 'objects'
        objects.mkdir(mode=0o700)
        a.backup.write_private(capture / 'manifest.json.fernet', b'synthetic ciphertext')
        a.backup.write_private(capture / 'database.dump.fernet', b'synthetic dump ciphertext')
        member = objects / ('a' * 64 + '.fernet')
        a.backup.write_private(member, b'synthetic file ciphertext')
        summary = dict(complete=True, run_id=run_id, database='quillmd_fresh', table_count=1,
                       row_count=1, file_count=1, file_bytes=4, source_commit='a'*40, encrypted=True,
                       manifest_cipher_sha256=a.backup.digest(b'synthetic ciphertext'))
        a.backup.write_private(capture / 'summary.json', json.dumps(summary).encode())
        state = dict(healthy=True, latest_outcome='complete', last_success_run_id=run_id)
        with patch.object(a.scheduled, 'DESTINATION', root), \
             patch.object(a.scheduled, 'status', return_value=state), \
             patch.object(a, 'systemd_state', return_value=dict(active=True, enabled=True, service=True)):
            self.assertTrue(a.current_local_bundle(state))
            self.assertEqual(a.backup_condition(datetime.now(timezone.utc)), 'healthy')
            member.unlink()
            self.assertEqual(a.backup_condition(datetime.now(timezone.utc)), 'backup_artifacts_unavailable')
            a.backup.write_private(member, b'synthetic file ciphertext')
            (capture / 'manifest.json.fernet').write_bytes(b'tampered ciphertext')
            self.assertEqual(a.backup_condition(datetime.now(timezone.utc)), 'backup_artifacts_unavailable')
            (capture / 'manifest.json.fernet').write_bytes(b'synthetic ciphertext')
            (capture / 'database.dump.fernet').unlink()
            self.assertEqual(a.backup_condition(datetime.now(timezone.utc)), 'backup_artifacts_unavailable')

    def test_timer_date_is_utc_and_unknown_output_is_redacted(self):
        with patch.object(a.subprocess, 'run', return_value=SimpleNamespace(returncode=0,
                          stdout=b'Mon 2026-09-21 04:30:00 UTC')) as process:
            self.assertEqual(a.next_timer_run('quillmd-fresh-backup.timer'), '2026-09-21T04:30:00+00:00')
            process.return_value.stdout = b'private-canary'
            self.assertIsNone(a.next_timer_run('quillmd-fresh-offsite.timer'))
            calls = process.call_count
            self.assertIsNone(a.next_timer_run('unapproved.service'))
            self.assertEqual(process.call_count, calls)

    def test_allowance_reports_reservations_and_freshness_not_account_usage(self):
        try:
            from . import automatic_offsite as engine
        except ImportError:
            import automatic_offsite as engine
        at = datetime(2026, 9, 20, 20, 0, tzinfo=timezone.utc)
        limits = dict(observed_at=(at-timedelta(minutes=30)).isoformat(),
                      valid_until=(at+timedelta(hours=1)).isoformat(),
                      daily_request_budget=500, daily_download_budget_bytes=100_000_000,
                      account_storage_used_bytes_at_observation=123, private_canary='never-output')
        budget = dict(version=1, day='2026-09-20', requests=44, download_bytes=12345)
        with patch.object(engine, 'policy', return_value=limits), patch.object(engine, 'budget_summary', return_value=budget), \
             patch.object(a, 'allocation_status', return_value={'renewal_requires_desktop': True}):
            result = a.allowance_status(at)
            self.assertTrue(result['eligible'])
            self.assertEqual(result['observation_age_seconds'], 1800)
            self.assertEqual(result['local_reservations']['requests'], 44)
            self.assertTrue(result['local_reservations']['current_utc_day'])
            self.assertNotIn('canary', json.dumps(result))
            self.assertNotIn('account_storage', json.dumps(result))
            self.assertEqual(result['remaining_requests'], 456)
            self.assertEqual(result['remaining_reserved_response_bytes'], 99_987_655)
            self.assertFalse(result['provider_download_charges_confirmed'])

    def test_expired_authenticated_observation_remains_visible_without_becoming_eligible(self):
        try:
            from . import automatic_offsite as engine
        except ImportError:
            import automatic_offsite as engine
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / 'policy.json'
        at = datetime(2026, 9, 21, 21, 0, tzinfo=timezone.utc)
        observed = at - timedelta(hours=25)
        limits = dict(observed_at=observed.isoformat(), valid_until=(at-timedelta(hours=1)).isoformat(),
                      daily_request_budget=500, daily_download_budget_bytes=100_000_000)
        a.backup.write_private(path, json.dumps(limits).encode())
        def validate(*, at):
            if at == observed:
                return limits
            raise engine.Refusal('policy_expired')
        with patch.object(engine, 'POLICY', path), patch.object(engine, 'policy', side_effect=validate), \
             patch.object(engine, 'budget_summary', return_value=dict(day='2026-09-21', requests=2, download_bytes=10)), \
             patch.object(a, 'allocation_status', return_value={'renewal_requires_desktop': True}):
            result = a.allowance_status(at)
            self.assertFalse(result['eligible'])
            self.assertEqual(result['reason'], 'policy_expired')
            self.assertEqual(result['observed_at'], limits['observed_at'])
            self.assertEqual(result['valid_until'], limits['valid_until'])
            self.assertEqual(result['observation_age_seconds'], 25 * 3600)
            self.assertEqual(result['seconds_until_expiry'], -3600)
            self.assertEqual(result['remaining_requests'], 498)
            # A concurrent candidate change cannot give unvalidated historical dates.
            path.write_text(json.dumps(dict(limits, valid_until=(at+timedelta(days=1)).isoformat())))
            changed = a.allowance_status(at)
            self.assertIsNone(changed['valid_until'])
            self.assertFalse(changed['eligible'])

    def test_next_day_forecast_preserves_prepaid_midnight_reservations_without_mutation(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        path = root / 'budget.json'
        old = dict(requests=422, download_bytes=98_474_544)
        prepaid = dict(requests=8, download_bytes=8_000_000)
        ledger = dict(version=2, day='2026-09-20', **old,
                      days={'2026-09-20': old, '2026-09-21': prepaid},
                      legacy_import=None, external_reservations=[])
        a.backup.write_private(path, json.dumps(ledger).encode())
        original = path.read_bytes()
        at = datetime(2026, 9, 20, 22, 0, tzinfo=timezone.utc)
        allowance = dict(eligible=True, valid_until='2026-09-21T20:16:35+00:00',
                         daily_request_budget=500, daily_download_budget_bytes=100_000_000)
        remote = dict(object_count=44, cipher_bytes=14_423_108)
        with patch.object(a, 'OFFSITE_DIRECTORY', root):
            today = a.next_run_admission(at, '2026-09-20T23:00:00+00:00', allowance, remote)
            tomorrow = a.next_run_admission(at, '2026-09-21T05:00:00+00:00', allowance, remote)
        self.assertEqual(today['remaining_reserved_response_bytes'], 1_525_456)
        self.assertFalse(today['same_size_cycle_fits'])
        self.assertEqual(tomorrow['remaining_requests'], 492)
        self.assertEqual(tomorrow['remaining_reserved_response_bytes'], 92_000_000)
        self.assertTrue(tomorrow['same_size_cycle_fits'])
        self.assertTrue(tomorrow['policy_covered'])
        self.assertFalse(tomorrow['future_success_verified'])
        self.assertEqual(tomorrow['same_size_cycle_estimate']['requests'], 92)
        self.assertEqual(tomorrow['same_size_cycle_estimate']['reserved_response_bytes'], 25_564_228)
        self.assertEqual(path.read_bytes(), original)

    def test_expired_policy_and_bad_ledger_fail_closed_with_specific_reason(self):
        try:
            from . import automatic_offsite as engine
        except ImportError:
            import automatic_offsite as engine
        with patch.object(engine, 'policy', side_effect=engine.Refusal('policy_expired')), \
             patch.object(engine, 'budget_summary', return_value=dict(day='2026-09-20', requests=44, download_bytes=12)):
            result = a.allowance_status(datetime.now(timezone.utc))
            self.assertFalse(result['eligible'])
            self.assertEqual(result['reason'], 'policy_expired')
            self.assertEqual(result['local_reservations']['requests'], 44)


if __name__ == '__main__':
    unittest.main()
