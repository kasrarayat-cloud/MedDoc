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
        for name, value in (('DIRECTORY', self.alerts), ('CONFIG', self.config), ('ENV_FILE', self.env)):
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


if __name__ == '__main__':
    unittest.main()
