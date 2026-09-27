"""Isolated alert fault injection: no live Resend, backup, systemd or database calls."""
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import ModuleType, SimpleNamespace
import tempfile
import threading
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
        # ⚠️ THIS LINE USED TO BE `assert_called_once()`, AND IT ENCODED THE DEFECT: the warning
        # became a failure inside the open incident and the test required that nobody be told.
        # The failure is now announced once, as an escalation; the warning still sent only once.
        self.assertEqual(self.sender.call_count, 2)
        self.assertIn('ESCALATION', self.sender.call_args.args[1])
        self.assertIn('Condition: offsite_policy_expired', self.sender.call_args.args[2])
        a.check(self.at + timedelta(minutes=20))
        self.assertEqual(self.sender.call_count, 2)

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

    def test_crash_before_pending_receipt_never_sends_that_notice_and_announces_a_restart(self):
        """This pinned a SILENT refusal, forever. FAIL CLOSED MEANS ALERT: the unrecorded notice is
        still never sent, and the monitor restarts its record and says so."""
        self.health.return_value = 'backup_failed'
        with patch.object(a, 'attempt_alert', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                a.check(self.at)
        named = json.loads((self.alerts / 'status.json').read_text())['incident_attempt']
        result, code = a.check(self.at + timedelta(minutes=5))
        self.assertEqual((code, result['condition'], result['state_unreadable']), (1, 'backup_failed', 'notice_record_missing'))
        self.sender.assert_called_once()
        self.assertIn('MONITOR RESTARTED', self.sender.call_args.args[1])
        self.assertNotIn(named, self.sender.call_args.args[2])
        self.assertFalse(list(self.alerts.glob(f'incident-{named}-*')))

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

    def test_lost_mutable_state_is_announced_as_a_restart_never_a_resend(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        receipts = {path.name: path.read_bytes() for path in self.alerts.glob('incident-*-*.json')}
        first = json.loads((self.alerts / 'status.json').read_text())['incident_attempt']
        (self.alerts / 'status.json').unlink()
        result, code = a.check(self.at + timedelta(days=2))
        self.assertEqual((code, result['condition'], result['state_unreadable']), (1, 'backup_failed', 'state_missing'))
        self.assertEqual(self.sender.call_count, 2)
        self.assertIn('MONITOR RESTARTED', self.sender.call_args.args[1])
        self.assertNotIn(first, self.sender.call_args.args[2], 'the first notice is not requested again')
        self.assertEqual({name: (self.alerts / name).read_bytes() for name in receipts}, receipts)

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
        self.assertNotIn('canary', json.dumps(a.status(self.at)[0]))
        result, code = a.check(self.at)
        self.assertEqual((code, result['state_unreadable']), (1, 'state_invalid'))
        self.assertNotIn('canary', json.dumps(result))
        self.sender.assert_called_once()                      # the restart notice: a label, no content
        self.assertNotIn('canary', ''.join(self.sender.call_args.args[1:]))

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


class IncidentEscalationReproductionTests(unittest.TestCase):
    """⚠️ THE DEFECT, AS IT HAPPENED ON THE SYNTHETIC HOST, 2026-09-23..26.

    An incident opened on an offsite renewal-due WARNING at 05:05Z and its one alert
    was attempted. At 22:05Z the same incident became `offsite_policy_expired` — a
    FAILURE — and every later check only replayed the first receipt, so nobody was told
    that the warning had become a failure. Isolated: every send is the mocked transport.
    """
    setUp = BackupAlertsTests.setUp

    def test_escalation_within_an_open_incident_is_announced(self):
        start = datetime(2026, 9, 23, 5, 5, tzinfo=timezone.utc)
        self.recovery.return_value['condition'] = 'offsite_policy_renewal_due'
        result, code = a.check(start)
        self.assertEqual((code, result['severity']), (0, 'warning'))
        self.assertEqual(self.sender.call_count, 1)
        # The warning persists through the day: still one notice, no storm.
        for hour in range(1, 17):
            a.check(start + timedelta(hours=hour))
        self.assertEqual(self.sender.call_count, 1)
        escalated = datetime(2026, 9, 23, 22, 5, tzinfo=timezone.utc)
        self.recovery.return_value['condition'] = 'offsite_policy_expired'
        result, code = a.check(escalated)
        self.assertEqual((code, result['condition'], result['severity']),
                         (1, 'offsite_policy_expired', 'failure'))
        self.assertEqual(self.sender.call_count, 2,
                         'the warning became a failure inside the open incident and nobody was told')
        subject, body = self.sender.call_args.args[1:]
        self.assertIn('ESCALATION', subject)
        self.assertIn('Condition: offsite_policy_expired', body)


class IncidentNotificationTests(unittest.TestCase):
    """Escalation, reminder and their storm guards inside ONE open incident. Mocked transport only."""
    setUp = BackupAlertsTests.setUp
    write_config = BackupAlertsTests.write_config

    def state(self):
        """The merged view this release works from, after asserting that status.json is still
        exactly what the previous release reads: format 1, its six keys, nothing else."""
        raw = json.loads((self.alerts / 'status.json').read_text())
        self.assertEqual((set(raw), raw['format']), (set(a.STATUS_KEYS), 1))
        return a.read_state()

    def ledger(self):
        return json.loads((self.alerts / a.NOTICES_FILE).read_text())

    def sent(self):
        return [call.args[1:] for call in self.sender.call_args_list]

    def record(self, identity):
        return json.loads((self.alerts / f'incident-{identity}-result.json').read_text())

    def legacy(self, **changes):
        """Exactly what the previous release wrote: six keys, one attempt named by the incident.

        Its last check is five minutes AFTER its notice, as the previous release leaves it once it has
        checked again: equal times could not tell an opening read from the notice's receipt from
        one read from the last check."""
        identity = 'c' * 32
        value = dict({'format': 1, 'last_check_at': (self.at + timedelta(minutes=5)).isoformat(),
                      'condition': 'offsite_policy_renewal_due',
                      'incident_id': identity, 'incident_attempt': identity,
                      'last_attempt_at': self.at.isoformat()}, **changes)
        a.backup.write_private(self.alerts / 'status.json', json.dumps(value).encode())
        if value['incident_attempt']:
            receipt = {'format': 1, 'kind': 'operational', 'condition': 'offsite_policy_renewal_due',
                       'attempted_at': self.at.isoformat(), 'outcome': 'provider_accepted',
                       'provider_message_id': 'legacy-provider-id', 'provider_accepted': True,
                       'delivery_confirmed': False, 'inbox_receipt_confirmed': False}
            for suffix in ('pending', 'result'):
                a.backup.write_private(self.alerts / f"incident-{value['incident_attempt']}-{suffix}.json",
                                       json.dumps(dict(receipt, outcome='pending', provider_accepted=False,
                                                       provider_message_id=None) if suffix == 'pending'
                                                  else receipt).encode())
        return identity

    def test_escalation_is_its_own_attempt_with_identity_receipt_and_recorded_condition(self):
        self.recovery.return_value['condition'] = 'offsite_policy_renewal_due'
        a.check(self.at)
        first = self.state()
        self.assertEqual((first['incident_attempt'], first['incident_attempt_notice']),
                         (first['incident_id'], 'initial'))
        self.recovery.return_value['condition'] = 'offsite_policy_expired'
        result, code = a.check(self.at + timedelta(hours=17))
        state = self.state()
        self.assertEqual(code, 1)
        self.assertEqual(state['incident_id'], first['incident_id'])
        self.assertNotEqual(state['incident_attempt'], first['incident_attempt'])
        self.assertEqual((state['incident_attempt_condition'], state['incident_attempt_notice'],
                          state['incident_attempt_count']), ('offsite_policy_expired', 'escalation', 2))
        self.assertEqual(state['incident_conditions_announced'],
                         ['offsite_policy_renewal_due', 'offsite_policy_expired'])
        self.assertEqual(state['last_attempt_at'], (self.at + timedelta(hours=17)).isoformat())
        self.assertEqual(self.record(state['incident_attempt'])['condition'], 'offsite_policy_expired')
        self.assertEqual(self.record(first['incident_attempt'])['condition'], 'offsite_policy_renewal_due')
        self.assertEqual(len(list(self.alerts.glob('incident-*-result.json'))), 2)
        self.assertTrue(result['alert']['provider_accepted'])
        self.assertEqual(result['incident']['last_notice'], 'escalation')
        self.assertEqual(result['incident']['open_seconds'], 17 * 3600)
        subject, body = self.sent()[-1]
        self.assertEqual(subject, '[QuillMD operations] ESCALATION: backup recovery condition changed')
        for text in ('Condition: offsite_policy_expired', 'severity increased', 'offsite_policy_renewal_due',
                     'open for at least 17 hours 0 minutes', 'notice 2', 'Reference: incident-' + state['incident_attempt'],
                     a.ERRORS['offsite_policy_expired']):
            self.assertIn(text, body)
        # The status reader sees the LATEST notice, not the first.
        status, _ = a.status(self.at + timedelta(hours=17, minutes=1))
        self.assertEqual(status['alert']['provider_accepted'], True)
        self.assertEqual(status['incident']['last_notice_condition'], 'offsite_policy_expired')

    def test_severity_escalation_is_immediate_but_only_once_per_incident(self):
        self.recovery.return_value['condition'] = 'offsite_capacity_low'           # warning
        a.check(self.at)
        self.health.return_value = 'backup_failed'                                 # failure
        a.check(self.at + timedelta(minutes=5))
        self.assertEqual(self.sender.call_count, 2)
        self.assertIn('severity increased', self.sent()[-1][1])
        self.health.return_value = 'healthy'                                       # back to the warning
        a.check(self.at + timedelta(minutes=10))
        self.health.return_value = 'backup_stale'                                  # a NEW failure
        result, _ = a.check(self.at + timedelta(minutes=15))
        self.assertEqual(self.sender.call_count, 2, 'a second failure is not more severe than the first')
        self.assertEqual(result['incident']['escalation_deferred_until'],
                         (self.at + timedelta(minutes=65)).isoformat())

    def test_same_severity_change_waits_for_spacing_then_is_announced(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        for minutes in (5, 30, 59):
            result, code = a.check(self.at + timedelta(minutes=minutes))
            self.assertEqual((code, result['condition']), (1, 'backup_stale'))
            self.assertTrue(result['alert']['provider_accepted'], 'the latest receipt stays visible')
            self.assertEqual(result['incident']['escalation_deferred_until'],
                             (self.at + timedelta(hours=1)).isoformat())
        self.assertEqual(self.sender.call_count, 1)
        result, _ = a.check(self.at + timedelta(minutes=60))
        self.assertEqual(self.sender.call_count, 2)
        self.assertIn('Condition: backup_stale', self.sent()[-1][1])
        self.assertIn('severity unchanged', self.sent()[-1][1])
        self.assertIsNone(result['incident']['escalation_deferred_until'])

    def test_change_to_a_less_severe_new_condition_is_announced_as_a_decrease(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'healthy'
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at + timedelta(hours=2))
        self.assertEqual(self.sender.call_count, 2)
        self.assertIn('ESCALATION', self.sent()[-1][0])
        self.assertIn('severity decreased', self.sent()[-1][1])

    def test_a_failure_that_returns_after_a_decrease_is_announced_at_once(self):
        """⚠️ R1. The last email the operator holds says the severity DECREASED; a failure that
        returns must not wait for the 24-hour reminder merely because it was announced before."""
        self.recovery.return_value['condition'] = 'offsite_upload_failed'           # failure: first notice
        a.check(self.at)
        self.recovery.return_value['condition'] = 'offsite_capacity_low'            # warning: a decrease
        a.check(self.at + timedelta(hours=2))
        self.assertIn('severity decreased', self.sent()[-1][1])
        self.recovery.return_value['condition'] = 'offsite_upload_failed'           # the failure returns
        result, code = a.check(self.at + timedelta(hours=2, minutes=5))
        self.assertEqual((code, self.sender.call_count), (1, 3),
                         "a failure returned and the operator's last email still said the severity decreased")
        subject, body = self.sent()[-1]
        self.assertEqual(subject, '[QuillMD operations] ESCALATION: backup recovery condition changed')
        for text in ('Condition: offsite_upload_failed', 'severity increased',
                     'last notice announced offsite_capacity_low', 'notice 3'):
            self.assertIn(text, body)
        state = self.state()
        self.assertEqual((state['incident_attempt_notice'], state['incident_attempt_condition'],
                          state['incident_attempt_count'], state['incident_conditions_announced']),
                         ('escalation', 'offsite_upload_failed', 3, ['offsite_upload_failed', 'offsite_capacity_low']))
        self.assertIsNone(result['incident']['escalation_deferred_until'])

    def test_a_different_failure_after_a_decrease_is_not_held_by_the_spacing(self):
        """R1's variant: the rise is measured against the LAST notice, not the highest ever sent."""
        self.health.return_value = 'backup_failed'                                  # failure: first notice
        a.check(self.at)
        self.health.return_value = 'healthy'
        self.recovery.return_value['condition'] = 'offsite_capacity_low'            # warning: a decrease
        a.check(self.at + timedelta(hours=2))
        self.health.return_value = 'backup_stale'                                   # a NEW failure
        result, _ = a.check(self.at + timedelta(hours=2, minutes=5))
        self.assertEqual(self.sender.call_count, 3,
                         'a failure after a decrease was held an hour, as if the last notice were a failure')
        self.assertIn('Condition: backup_stale', self.sent()[-1][1])
        self.assertIn('severity increased', self.sent()[-1][1])
        self.assertIsNone(result['incident']['escalation_deferred_until'])

    def test_after_the_rise_failure_warning_flapping_sends_nothing_until_the_reminder(self):
        """The bound that keeps R1 from becoming a loop: once the last notice is the failure, a pair
        that is already announced flaps without a single extra notice until the reminder is due."""
        self.recovery.return_value['condition'] = 'offsite_upload_failed'
        a.check(self.at)
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at + timedelta(hours=2))
        rise = self.at + timedelta(hours=2, minutes=5)
        self.recovery.return_value['condition'] = 'offsite_upload_failed'
        a.check(rise)
        for step in range(1, 288):                              # every five minutes, just under 24 h
            self.recovery.return_value['condition'] = ('offsite_capacity_low' if step % 2
                                                       else 'offsite_upload_failed')
            a.check(rise + timedelta(minutes=5 * step))
        conditions = [body.split('Condition: ')[1].split('\n')[0] for _, body in self.sent()]
        self.assertEqual(conditions, ['offsite_upload_failed', 'offsite_capacity_low', 'offsite_upload_failed'])
        self.recovery.return_value['condition'] = 'offsite_upload_failed'
        a.check(rise + timedelta(hours=24))
        self.assertEqual(self.sender.call_count, 4)
        self.assertIn('REMINDER', self.sent()[-1][0])

    def test_a_notice_stamped_by_a_fast_clock_never_delays_the_next(self):
        """⚠️ R5(a). A clock three days fast stamps the first notice and is then corrected. A recorded
        time in the future is read as now: the reminder and the escalation spacing restart from the
        correction instead of waiting out the error, and the incident's age is never negative."""
        fast = self.at + timedelta(days=3)
        self.health.return_value = 'backup_failed'
        a.check(fast)
        corrected = self.at + timedelta(minutes=5)
        shown, _ = a.status(corrected)                        # corrected before any check has run
        self.assertEqual((shown['incident']['open_seconds'], shown['incident']['next_reminder_at']),
                         (0, (corrected + timedelta(hours=24)).isoformat()))
        result, _ = a.check(corrected)
        self.assertEqual(result['incident']['open_seconds'], 0)
        self.assertEqual(result['incident']['next_reminder_at'], (corrected + timedelta(hours=24)).isoformat())
        shown, _ = a.status(corrected + timedelta(minutes=1))
        self.assertEqual(shown['incident']['open_seconds'], 60)
        self.health.return_value = 'backup_stale'
        a.check(corrected + timedelta(hours=1))
        self.assertEqual(self.sender.call_count, 2, 'a same-severity change waited out a fast clock')
        a.check(corrected + timedelta(hours=25))
        self.assertEqual(self.sender.call_count, 3, 'the reminder waited out a fast clock')
        self.assertIn('REMINDER', self.sent()[-1][0])

    def test_a_fast_clock_does_not_stretch_the_interval_between_incidents(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at + timedelta(days=3))                  # the fast clock
        corrected = self.at + timedelta(minutes=5)
        self.health.return_value = 'healthy'
        a.check(corrected)                                    # the incident closes
        self.health.return_value = 'backup_stale'
        a.check(corrected + timedelta(hours=23, minutes=55))  # inside the interval: held
        self.assertEqual(self.sender.call_count, 1)
        a.check(corrected + timedelta(hours=24))
        self.assertEqual(self.sender.call_count, 2, 'the next incident waited out a fast clock')

    def test_a_warning_stamped_by_a_fast_clock_does_not_later_hold_a_failure(self):
        """The stamps are read as now with the notice time, or the next read would find a stamp
        later than every recorded request, drop it as unsent, and count the warning as a failure."""
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at + timedelta(days=3))                  # a warning notice, on the fast clock
        corrected = self.at + timedelta(minutes=5)
        self.recovery.return_value['condition'] = 'healthy'
        a.check(corrected)                                    # closes
        self.health.return_value = 'backup_failed'
        a.check(corrected + timedelta(hours=1))
        self.assertEqual(self.sender.call_count, 2, 'a warning from a fast clock held a failure')
        self.assertIn('(highest: warning)', self.sent()[-1][1])

    def test_a_close_stopped_between_its_writes_after_a_fast_clock_never_delays_the_next(self):
        """⚠️ F2, round 2, the refuter's sequence. A close writes status.json first, with its last
        notice time read as now; killed before the ledger, the ledger kept the warning's stamp three
        days ahead. That stamp was then dropped as "later than any recorded request", so the warning
        became an unknown notice, counted as a failure, and held the failure until +25 h."""
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at + timedelta(days=3))                  # a warning notice, on a clock three days fast
        self.recovery.return_value['condition'] = 'healthy'
        crash, calls = IncidentLedgerTests.crash_on_second_write(self)
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=1))             # corrected: the incident closes, killed mid-write
        self.assertEqual(calls, ['status.json', a.NOTICES_FILE])
        self.health.return_value = 'backup_failed'
        result, _ = a.check(self.at + timedelta(hours=2))
        self.assertEqual((result['alert']['outcome'], self.sender.call_count), ('provider_accepted', 2),
                         'a warning stamped by a fast clock held a failure after a close stopped between its writes')
        subject, body = self.sent()[-1]
        self.assertEqual(subject, '[QuillMD operations] ESCALATION: a more severe backup incident opened')
        self.assertIn('(highest: warning)', body)

    def test_status_reports_the_deferred_escalation_the_check_reported(self):
        """⚠️ R5(b). The summary carries any deferred escalation, from status() as from check()."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        result, _ = a.check(self.at + timedelta(minutes=5))
        deferred = (self.at + timedelta(hours=1)).isoformat()
        self.assertEqual(result['incident']['escalation_deferred_until'], deferred)
        shown, _ = a.status(self.at + timedelta(minutes=6))
        self.assertEqual(shown['incident']['escalation_deferred_until'], deferred,
                         'check() reported a deferred escalation and status() did not')
        # Past that time with no check since, it is still the last check's decision, owed at its next run.
        shown, _ = a.status(self.at + timedelta(hours=1, minutes=1))
        self.assertEqual((shown['condition'], shown['incident']['escalation_deferred_until']),
                         ('monitoring_stale', deferred))
        result, _ = a.check(self.at + timedelta(hours=1))     # sent: nothing is deferred any more
        self.assertIsNone(result['incident']['escalation_deferred_until'])
        self.assertIsNone(a.status(self.at + timedelta(hours=1, minutes=1))[0]['incident']['escalation_deferred_until'])

    def test_status_reports_no_deferral_where_the_check_planned_nothing(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_in_progress'        # keeps the incident open, plans nothing
        self.assertIsNone(a.check(self.at + timedelta(minutes=5))[0]['incident']['escalation_deferred_until'])
        shown, _ = a.status(self.at + timedelta(minutes=6))
        self.assertEqual(shown['condition'], 'backup_in_progress')
        self.assertIsNone(shown['incident']['escalation_deferred_until'])
        self.health.return_value = 'backup_failed'
        a.check(self.at + timedelta(minutes=10))
        self.write_config(enabled=False)                       # the check records this and returns
        self.assertEqual(a.check(self.at + timedelta(minutes=15))[0]['condition'], 'alert_configuration_unavailable')
        self.write_config()
        shown, _ = a.status(self.at + timedelta(minutes=16))
        self.assertIsNone(shown['incident']['escalation_deferred_until'])
        self.sender.assert_called_once()

    def test_reminder_names_duration_and_current_condition_at_a_fixed_interval(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        for hour in range(1, 24):
            a.check(self.at + timedelta(hours=hour))
        self.assertEqual(self.sender.call_count, 1)
        result, code = a.check(self.at + timedelta(hours=24))
        self.assertEqual((code, self.sender.call_count), (1, 2))
        subject, body = self.sent()[-1]
        self.assertEqual(subject, '[QuillMD operations] REMINDER: backup recovery incident still open')
        for text in ('Condition: backup_failed', 'Severity: failure', 'open for at least 24 hours 0 minutes',
                     'open since no later than ' + self.at.isoformat(), 'notice 2', 'still open'):
            self.assertIn(text, body)
        state = self.state()
        self.assertEqual((state['incident_attempt_notice'], state['incident_attempt_count'],
                          state['incident_conditions_announced']), ('reminder', 2, ['backup_failed']))
        self.assertNotEqual(state['incident_attempt'], state['incident_id'])
        self.assertEqual(result['incident']['next_reminder_at'], (self.at + timedelta(hours=48)).isoformat())
        a.check(self.at + timedelta(hours=47, minutes=55))
        self.assertEqual(self.sender.call_count, 2)
        a.check(self.at + timedelta(hours=48))
        self.assertEqual(self.sender.call_count, 3)
        self.assertIn('open for at least 48 hours 0 minutes', self.sent()[-1][1])
        self.assertIn('notice 3', self.sent()[-1][1])

    def test_reminder_is_measured_from_the_last_notice_and_names_the_current_condition(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=10))                 # escalation
        self.health.return_value = 'backup_failed'             # back to an announced condition
        a.check(self.at + timedelta(hours=33, minutes=55))
        self.assertEqual(self.sender.call_count, 2)
        a.check(self.at + timedelta(hours=34))
        self.assertEqual(self.sender.call_count, 3)
        subject, body = self.sent()[-1]
        self.assertIn('REMINDER', subject)
        self.assertIn('Condition: backup_failed', body)
        self.assertIn('open for at least 34 hours 0 minutes', body)

    def test_flapping_between_announced_conditions_sends_no_more_than_the_cooldown_allows(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        for step in range(1, 288):                             # every five minutes, just under 24 h
            self.health.return_value = 'backup_stale' if step % 2 else 'backup_failed'
            a.check(self.at + timedelta(minutes=5 * step))
        conditions = [body.split('Condition: ')[1].split('\n')[0] for _, body in self.sent()]
        self.assertEqual(conditions, ['backup_failed', 'backup_stale'])
        self.assertEqual(self.state()['last_attempt_at'], (self.at + timedelta(minutes=65)).isoformat())

    def test_flapping_between_healthy_and_failed_sends_once_per_cooldown(self):
        for step in range(288):
            self.health.return_value = 'backup_failed' if step % 2 == 0 else 'healthy'
            a.check(self.at + timedelta(minutes=5 * step))
        self.assertEqual(self.sender.call_count, 1)
        self.health.return_value = 'backup_failed'
        a.check(self.at + timedelta(hours=24))
        self.assertEqual(self.sender.call_count, 2)
        self.assertIn('Backup recovery requires attention', self.sent()[-1][0])

    def test_rotating_new_conditions_are_spaced_not_stormed(self):
        rotation = ['backup_stale', 'backup_timeout', 'backup_status_unavailable', 'backup_artifacts_unavailable',
                    'backup_schedule_unavailable', 'offsite_upload_failed', 'offsite_integrity_failed']
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        for step in range(1, 37):                              # three hours, a new condition every check
            condition = rotation[step % len(rotation)]
            if condition.startswith('offsite'):
                self.health.return_value = 'healthy'
                self.recovery.return_value['condition'] = condition
            else:
                self.health.return_value = condition
            a.check(self.at + timedelta(minutes=5 * step))
        times = [datetime.fromisoformat(json.loads(p.read_text())['attempted_at'])
                 for p in self.alerts.glob('incident-*-result.json')]
        times.sort()
        self.assertEqual(len(times), 4)                        # t0, then one per spacing window
        self.assertTrue(all((later - earlier).total_seconds() >= a.ESCALATION_SPACING_SECONDS
                            for earlier, later in zip(times, times[1:])))

    def test_crash_between_persisting_an_escalation_and_its_request_never_sends_it_and_restarts(self):
        """This pinned monitoring_state_unavailable at +3 h, +30 h and +100 h with no email: silence
        for ever. The unrecorded escalation is still never sent; the record restarts, announced."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        before = self.state()
        self.health.return_value = 'backup_stale'
        with patch.object(a, 'attempt_alert', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                a.check(self.at + timedelta(hours=2))
        persisted = self.state()
        self.assertNotEqual(persisted['incident_attempt'], before['incident_attempt'])
        self.assertEqual(persisted['incident_attempt_condition'], 'backup_stale')
        self.assertFalse(list(self.alerts.glob(f"incident-{persisted['incident_attempt']}-*")))
        shown, _ = a.status(self.at + timedelta(hours=2, minutes=1))
        self.assertEqual((shown['condition'], shown['state_unreadable']), ('monitoring_state_unavailable', 'notice_record_missing'))
        result, code = a.check(self.at + timedelta(hours=3))
        self.assertEqual((code, result['condition'], result['state_unreadable'], self.sender.call_count),
                         (1, 'backup_stale', 'notice_record_missing', 2))
        self.assertIn('MONITOR RESTARTED', self.sent()[-1][0])
        self.assertFalse(list(self.alerts.glob(f"incident-{persisted['incident_attempt']}-*")), 'never sent')
        result, _ = a.check(self.at + timedelta(hours=4))
        self.assertEqual((result['condition'], self.sender.call_count), ('backup_stale', 2))
        self.assertEqual(a.status(self.at + timedelta(hours=4, minutes=1))[0]['condition'], 'backup_stale')

    def test_interrupted_escalation_request_is_pending_and_never_followed(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        self.sender.side_effect = KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=2))
        self.sender.side_effect = None
        for hours in (3, 30, 100):
            result, code = a.check(self.at + timedelta(hours=hours))
            self.assertEqual((code, result['condition'], result['alert']['outcome']),
                             (1, 'alert_delivery_unconfirmed', 'pending'))
        self.assertEqual(self.sender.call_count, 2)

    def test_an_uncertain_notice_is_never_followed_by_escalation_or_reminder(self):
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        self.sender.side_effect = RuntimeError('provider-canary')
        result, code = a.check(self.at)
        self.assertEqual((code, result['condition']), (1, 'alert_delivery_unconfirmed'))
        self.sender.side_effect = None
        self.health.return_value = 'backup_failed'
        for hours in (1, 25, 49):
            result, code = a.check(self.at + timedelta(hours=hours))
            self.assertEqual((code, result['condition']), (1, 'alert_delivery_unconfirmed'))
            self.assertIsNone(result['incident']['next_reminder_at'])
        self.sender.assert_called_once()
        self.assertEqual(a.status(self.at + timedelta(hours=49))[0]['condition'], 'alert_delivery_unconfirmed')
        self.assertNotIn('canary', ''.join(p.read_text() for p in self.alerts.glob('*.json')))

    def test_healthy_clears_every_incident_key_and_the_next_incident_starts_fresh(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))
        self.assertEqual(self.sender.call_count, 2)
        for quiet in ('healthy', 'offsite_policy_expiring'):
            with self.subTest(quiet=quiet):
                self.health.return_value = 'healthy'
                self.recovery.return_value['condition'] = quiet
                result, _ = a.check(self.at + timedelta(hours=3))
                self.assertIsNone(result['incident'])
                self.assertEqual({key: value for key, value in self.state().items() if key.startswith('incident')},
                                 a.closed_incident())
                self.assertEqual(self.state()['last_attempt_at'], (self.at + timedelta(hours=2)).isoformat())
        for hours in (4, 26, 50):                              # nothing is reminded about a closed incident
            a.check(self.at + timedelta(hours=hours))
        self.assertEqual(self.sender.call_count, 2)
        self.health.return_value = 'backup_stale'
        result, _ = a.check(self.at + timedelta(hours=51))
        state = self.state()
        self.assertEqual(self.sender.call_count, 3)
        self.assertIn('Backup recovery requires attention', self.sent()[-1][0])
        self.assertEqual((state['incident_attempt_notice'], state['incident_attempt_count'],
                          state['incident_conditions_announced'], state['incident_attempt']),
                         ('initial', 1, ['backup_stale'], state['incident_id']))
        self.assertEqual(result['incident']['open_seconds'], 0)

    def test_new_incident_inside_the_cooldown_announces_its_current_condition_when_it_ends(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'healthy'
        a.check(self.at + timedelta(hours=1))
        self.health.return_value = 'backup_stale'
        result, _ = a.check(self.at + timedelta(hours=2))
        self.assertEqual(result['alert']['outcome'], 'cooldown_suppressed')
        self.assertEqual(result['incident']['opened_at'], (self.at + timedelta(hours=2)).isoformat())
        self.health.return_value = 'backup_timeout'
        a.check(self.at + timedelta(hours=24))
        self.assertEqual(self.sender.call_count, 2)
        self.assertIn('Condition: backup_timeout', self.sent()[-1][1])
        self.assertEqual(self.state()['incident_attempt_notice'], 'initial')

    def test_previous_release_state_upgrades_and_its_open_incident_escalates(self):
        identity = self.legacy()
        self.recovery.return_value['condition'] = 'offsite_policy_expired'
        later = self.at + timedelta(days=3, hours=17)
        status_before = (self.alerts / 'status.json').read_bytes()
        self.assertEqual(a.status(later - timedelta(minutes=1))[0]['condition'], 'monitoring_stale')
        self.assertEqual((self.alerts / 'status.json').read_bytes(), status_before, 'status stays read-only')
        self.assertFalse((self.alerts / a.NOTICES_FILE).exists(), 'the previous release keeps no ledger')
        result, code = a.check(later)
        state = self.state()                                   # asserts status.json stayed six keys
        self.assertEqual((code, self.sender.call_count), (1, 1))
        self.assertEqual(self.ledger()['incident']['incident_attempt'], state['incident_attempt'])
        self.assertEqual((state['incident_id'], state['incident_opened_at'], state['incident_attempt_count'],
                          state['incident_conditions_announced']),
                         (identity, self.at.isoformat(), 2, ['offsite_policy_renewal_due', 'offsite_policy_expired']))
        self.assertIn('ESCALATION', self.sent()[-1][0])
        self.assertIn('open for at least 89 hours 0 minutes', self.sent()[-1][1])
        self.assertEqual(self.record(identity)['provider_message_id'], 'legacy-provider-id')

    def test_previous_release_state_without_an_attempt_upgrades_to_an_open_incident(self):
        self.legacy(incident_attempt=None, last_attempt_at=None)
        self.health.return_value = 'backup_failed'
        a.check(self.at + timedelta(minutes=10))
        state = self.state()
        # No notice to read an opening from: it was open no later than the previous release's last check.
        self.assertEqual((state['incident_id'], state['incident_opened_at'], state['incident_attempt_notice']),
                         ('c' * 32, (self.at + timedelta(minutes=5)).isoformat(), 'initial'))
        self.sender.assert_called_once()

    def test_inconsistent_previous_release_state_is_restarted_and_announced(self):
        # Each has a readable receipt, so only the incident invariants can reject it.
        for count, changes in enumerate(({'incident_attempt': 'd' * 32},
                                         {'incident_attempt': None, 'last_attempt_at': None, 'last_check_at': None}), 1):
            with self.subTest(changes=changes):
                for path in self.alerts.iterdir():
                    path.unlink()
                self.legacy(**changes)
                receipts = {path.name: path.read_bytes() for path in self.alerts.glob('incident-*-*.json')}
                result, code = a.check(self.at + timedelta(days=2))
                self.assertEqual((code, result['condition'], result['state_unreadable'], self.sender.call_count),
                                 (1, 'healthy', 'incident_record_invalid', count))
                self.assertEqual({name: (self.alerts / name).read_bytes() for name in receipts}, receipts)
                self.assertEqual(a.check(self.at + timedelta(days=2, minutes=5))[0]['condition'], 'healthy')

    def test_invalid_incident_records_are_restarted_without_disclosure(self):
        """Each case tampers ONE file and leaves the other exactly as written, so the reason can only
        come from the check that case is aimed at (status.json alone would reject everything). Each
        runs on a fresh copy of the same directory, so no restart notice holds the next case's."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))
        status = json.loads((self.alerts / 'status.json').read_text())
        ledger = self.ledger()
        snapshot = {path.name: path.read_bytes() for path in self.alerts.iterdir()}
        self.assertEqual(a.read_state()['incident_attempt_notice'], 'escalation', 'the untampered pair is valid')
        cases = [('status', {'incident_opened_at': status['last_check_at']}),     # the format-2 shape
                 ('status', {'format': 2}), ('status', {'incident_id': None}),
                 ('ledger', {'format': 2}), ('ledger', {'unexpected': 'private-canary'}),
                 ('ledger', {'announced_at': {'warning': None}}),
                 ('ledger', {'announced_at': {'warning': 'private-canary', 'failure': None}}),
                 # A kept layer is validated whether or not it matches status.json: one that does not
                 # match is never read, so only the ledger's own validation can refuse it.
                 ('ledger', {'committed': 'private-canary'}),
                 ('ledger', {'committed': {'status': dict(status, format=2), 'incident': None,
                                           'announced_at': {'warning': None, 'failure': None}}}),
                 # A malformed record of an incident that is already over: nothing merges it, so
                 # only the ledger's own validation can refuse it.
                 ('stale', {'incident_attempt_count': 'private-canary'})]
        for changes in ({'incident_conditions_announced': ['private-clinical-canary', 'backup_stale']},
                        {'incident_conditions_announced': ['backup_stale', 'backup_stale']},
                        {'incident_conditions_announced': ['healthy', 'backup_stale']},
                        {'incident_attempt_count': True}, {'incident_attempt_count': 1},
                        # More conditions announced than notices sent: every other invariant holds.
                        {'incident_conditions_announced': ['backup_failed', 'backup_stale', 'backup_timeout']},
                        {'incident_attempt_notice': 'private-canary'}, {'incident_attempt_condition': 'backup_timeout'},
                        {'incident_opened_at': None}, {'incident_opened_at': 'private-canary'},
                        {'incident_attempt_notice': 'initial', 'incident_attempt_count': 1},
                        {'incident_attempt_notice': 'initial'},
                        {'incident_attempt': None, 'incident_attempt_count': 0, 'incident_conditions_announced': [],
                         'incident_attempt_condition': None},
                        {'unexpected': 'private-canary'}):
            cases.append(('record', changes))
        for count, (where, changes) in enumerate(cases, 3):
            with self.subTest(where=where, changes=changes):
                for path in self.alerts.iterdir():
                    path.unlink()
                for name, content in snapshot.items():
                    a.backup.write_private(self.alerts / name, content)
                (self.alerts / 'status.json').write_text(json.dumps(
                    dict(status, **changes) if where == 'status'
                    else dict(status, incident_id=None, incident_attempt=None) if where == 'stale' else status))
                (self.alerts / a.NOTICES_FILE).write_text(json.dumps(
                    dict(ledger, incident=dict(ledger['incident'], **changes)) if where in ('record', 'stale')
                    else dict(ledger, **changes) if where == 'ledger' else ledger))
                shown, _ = a.status(self.at + timedelta(days=2))
                result, code = a.check(self.at + timedelta(days=2))
                reason = 'state_invalid' if where == 'status' else 'ledger_invalid'
                self.assertEqual((shown['condition'], shown['state_unreadable']), ('monitoring_state_unavailable', reason))
                self.assertEqual((code, result['condition'], result['state_unreadable'], self.sender.call_count),
                                 (1, 'backup_stale', reason, count))
                for text in (json.dumps(result), json.dumps(shown), *self.sent()[-1]):
                    self.assertNotIn('canary', text)

    def test_a_receipt_that_disagrees_with_state_is_never_followed_and_the_record_restarts(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        path = next(self.alerts.glob('incident-*-result.json'))
        path.write_text(json.dumps(dict(json.loads(path.read_text()), condition='backup_stale')))
        tampered = path.read_bytes()
        shown, _ = a.status(self.at + timedelta(days=2))
        self.assertEqual((shown['condition'], shown['state_unreadable']), ('monitoring_state_unavailable', 'notice_record_mismatch'))
        result, code = a.check(self.at + timedelta(days=2))
        self.assertEqual((code, result['condition'], result['state_unreadable']), (1, 'backup_failed', 'notice_record_mismatch'))
        self.assertEqual(self.sender.call_count, 2)
        self.assertIn('MONITOR RESTARTED', self.sent()[-1][0])
        self.assertEqual(path.read_bytes(), tampered, 'a request record is evidence: never rewritten')
        self.assertNotEqual(self.state()['incident_attempt'], path.name[len('incident-'):-len('-result.json')])

    def test_notices_carry_no_secret_and_the_summary_carries_no_identity(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))
        result, _ = a.check(self.at + timedelta(hours=26))
        self.assertEqual(self.sender.call_count, 3)
        for subject, body in self.sent():
            for secret in ('re_synthetic_not_a_real_key', 'DO_NOT_COPY', 'noreply@', 'https://'):
                self.assertNotIn(secret, subject + body)
            self.assertIn('No patient information or credentials are included.', body)
        state = self.state()
        for identity in (state['incident_id'], state['incident_attempt']):
            self.assertNotIn(identity, json.dumps(result['incident']))

    def test_status_readers_keep_their_shape(self):
        """The publisher copies these report keys into the console; extended, never renamed."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))
        result, code = a.status(self.at + timedelta(hours=2, minutes=1))
        self.assertEqual(code, 1)
        self.assertLessEqual({'format', 'condition', 'action', 'checked_at', 'healthy', 'severity', 'alert',
                              'offsite_recovery_verified', 'local_capture', 'offsite', 'external_monitor',
                              'outside_host_failure_detection', 'clinical_content_included',
                              'monitor_age_seconds', 'stale_after_seconds'}, set(result))
        self.assertEqual(set(result['alert']), {'outcome', 'provider_message_id', 'provider_accepted',
                                                'delivery_confirmed', 'inbox_receipt_confirmed'})
        self.assertIs(result['clinical_content_included'], False)
        self.assertEqual(result['incident']['conditions_announced'], ['backup_failed', 'backup_stale'])
        raw = json.loads((self.alerts / 'status.json').read_text())
        self.assertEqual(tuple(sorted(raw)), tuple(sorted(a.STATUS_KEYS)))
        self.assertEqual(raw['format'], 1)


#: ⚠️ THE PREVIOUS RELEASE IS PINNED BY COMMIT AND CONTENT, NOT READ FROM `release/v1`. That ref
#: moves: once this change lands on it, `git show release/v1:...` is THIS code and the test below
#: compares the new release with itself and passes vacuously. It is also absent from a CI checkout,
#: which carries full history (fetch-depth 0) but no local branch of that name. dedac162 is the
#: installed release, an ancestor of this branch, and byte-identical to release/v1's file when this
#: was written (all three: sha256 11328255...).
PREVIOUS_RELEASE_COMMIT = 'dedac1625032e32c7a149e6771be22e26c307eb1'
PREVIOUS_RELEASE_SHA256 = '11328255580d6cfad6e7faf7d4db15685ef48ffbdd900a1070f15faf769ed9c8'


def previous_release_source():
    try:
        child = subprocess.run(['git', 'show', PREVIOUS_RELEASE_COMMIT + ':rebuild/ops/backup_alerts.py'],
                               cwd=Path(__file__).resolve().parent, capture_output=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return child.stdout if child.returncode == 0 else None


class PreviousReleaseCompatibilityTests(unittest.TestCase):
    """ROLLBACK = REVERT THE FILE. The installed release must run, unrepaired, on any directory this
    release has written, and this release must adopt whatever the previous one then leaves behind."""
    setUp_alerts = BackupAlertsTests.setUp

    def setUp(self):
        self.setUp_alerts()
        # The previous release still inserts into sys.path on every check; never let it accumulate.
        self.addCleanup(sys.path.__setitem__, slice(None), list(sys.path))
        source = previous_release_source()
        if source is None:
            if os.environ.get('CI') == 'true':
                self.fail('CI must be able to read the previous release; a skip here would be a vacuous pass')
            self.skipTest('git history holding the previous release is unavailable')
        self.assertEqual(hashlib.sha256(source).hexdigest(), PREVIOUS_RELEASE_SHA256)
        old = ModuleType('previous_release_backup_alerts')
        # `__file__` only locates rebuild/ for the transport import, exactly as when installed.
        old.__file__, old.__package__ = a.__file__, a.__package__
        exec(compile(source, PREVIOUS_RELEASE_COMMIT[:8] + ':rebuild/ops/backup_alerts.py', 'exec'), old.__dict__)
        self.old = old
        self.old_sender = patch.object(old, 'email_transport', return_value='previous-release-id').start()
        for name in ('CONFIG', 'ENV_FILE', 'EXTERNAL_CONFIG'):
            patch.object(old, name, getattr(a, name)).start()
        patch.object(old, 'backup_condition', self.health).start()
        patch.object(old, 'recovery_status', self.recovery).start()
        patch.object(old, 'local_capture_status', return_value=None).start()

    def previous_release_on_a_copy(self, at):
        """Run the installed release on a COPY of what this release wrote, as a rollback would."""
        copy = Path(tempfile.mkdtemp(dir=self.root))
        copy.rmdir()
        shutil.copytree(self.alerts, copy)
        copy.chmod(0o700)
        with patch.object(self.old, 'DIRECTORY', copy):
            checked, code = self.old.check(at)
            shown, _ = self.old.status(at + timedelta(minutes=1))
        return checked, shown, code

    def test_positive_control_the_loaded_previous_release_works_on_its_own_state(self):
        """Without this, a loader fault would read exactly like an incompatible state file."""
        with patch.object(self.old, 'DIRECTORY', self.alerts):
            self.assertEqual(self.old.check(self.at)[0]['condition'], 'healthy')
            self.health.return_value = 'backup_failed'
            result, code = self.old.check(self.at + timedelta(minutes=5))
            self.assertEqual((code, result['condition'], result['alert']['provider_message_id']),
                             (1, 'backup_failed', 'previous-release-id'))
            self.assertEqual(self.old.status(self.at + timedelta(minutes=6))[0]['condition'], 'backup_failed')
        self.old_sender.assert_called_once()
        self.sender.assert_not_called()

    def test_the_previous_release_runs_on_every_state_this_release_writes(self):
        steps = [
            (timedelta(0), 'healthy', 'healthy', None),
            (timedelta(minutes=5), 'healthy', 'offsite_policy_renewal_due', None),        # first notice
            (timedelta(minutes=10), 'backup_failed', 'offsite_policy_renewal_due', None), # escalation
            (timedelta(minutes=15), 'backup_stale', 'offsite_policy_renewal_due', None),  # deferred
            (timedelta(hours=26), 'backup_failed', 'offsite_policy_renewal_due', None),   # reminder
            (timedelta(hours=27), 'backup_timeout', 'offsite_policy_renewal_due',
             RuntimeError('provider-canary')),                                               # uncertain
            (timedelta(hours=28), 'healthy', 'healthy', None),                                # closed
            (timedelta(hours=29), 'backup_stale', 'healthy', None),                           # held by cooldown
        ]
        for offset, local, remote, failure in steps:
            with self.subTest(offset=offset):
                self.health.return_value = local
                self.recovery.return_value['condition'] = remote
                self.sender.side_effect = failure
                expected, _ = a.check(self.at + offset)
                self.sender.side_effect = None
                self.assertNotEqual(expected['condition'], 'monitoring_state_unavailable')
                checked, shown, _ = self.previous_release_on_a_copy(self.at + offset + timedelta(minutes=1))
                self.assertNotEqual(checked['condition'], 'monitoring_state_unavailable',
                                    'reverting the file must leave a working monitor')
                self.assertNotEqual(shown['condition'], 'monitoring_state_unavailable')
                # Same verdict, and the previous release replays the LATEST notice's own receipt.
                self.assertEqual(checked['condition'], expected['condition'])
                self.assertEqual(checked['alert'] and checked['alert']['outcome'],
                                 expected['alert'] and expected['alert']['outcome'])
        self.old_sender.assert_not_called()

    def test_the_previous_release_runs_on_the_shapes_the_repairs_write(self):
        """A notice time read as now after a fast clock (R5), a rise re-announcing an announced
        condition (R1), and a ledger that ran ahead of status.json with its kept layer (R2/R3)."""
        steps = [(timedelta(days=3), 'backup_failed', 'healthy'),              # a clock three days fast
                 (timedelta(0), 'backup_failed', 'healthy'),                   # corrected: read as now
                 (timedelta(hours=2), 'healthy', 'offsite_capacity_low'),      # a decrease
                 (timedelta(hours=2, minutes=5), 'backup_failed', 'healthy')]  # the rise, re-announced
        for offset, local, remote in steps:
            with self.subTest(offset=offset):
                self.health.return_value = local
                self.recovery.return_value['condition'] = remote
                expected, _ = a.check(self.at + offset)
                checked, shown, _ = self.previous_release_on_a_copy(self.at + offset + timedelta(minutes=1))
                self.assertEqual((checked['condition'], checked['alert']['outcome']),
                                 (expected['condition'], expected['alert']['outcome']))
                self.assertNotEqual(shown['condition'], 'monitoring_state_unavailable')
        self.assertEqual(self.sender.call_count, 3)
        self.health.return_value = 'backup_timeout'
        crash, _ = IncidentLedgerTests.crash_on_second_write(self)
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=4))
        self.assertIsNotNone(json.loads((self.alerts / a.NOTICES_FILE).read_text())['committed'])
        checked, shown, _ = self.previous_release_on_a_copy(self.at + timedelta(hours=4, minutes=1))
        self.assertEqual((checked['condition'], checked['alert']['outcome']), ('backup_timeout', 'provider_accepted'))
        self.assertNotEqual(shown['condition'], 'monitoring_state_unavailable')
        self.old_sender.assert_not_called()
        result, _ = a.check(self.at + timedelta(hours=4, minutes=5))          # and this release recovers
        self.assertEqual((result['condition'], self.sender.call_count), ('backup_timeout', 4))

    def test_this_release_adopts_what_the_previous_release_leaves_behind(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))                 # escalation: a notice only this release makes
        with patch.object(self.old, 'DIRECTORY', self.alerts):
            self.health.return_value = 'healthy'
            self.assertEqual(self.old.check(self.at + timedelta(hours=3))[0]['condition'], 'healthy')
            self.health.return_value = 'backup_timeout'
            result, _ = self.old.check(self.at + timedelta(hours=27))   # the previous release's own first notice
            self.assertTrue(result['alert']['provider_accepted'])
        self.old_sender.assert_called_once()
        result, code = a.check(self.at + timedelta(hours=27, minutes=5))
        self.assertEqual((code, result['condition']), (1, 'backup_timeout'))
        self.assertEqual(result['alert']['provider_message_id'], 'previous-release-id')
        self.assertEqual(result['incident']['conditions_announced'], ['backup_timeout'])
        self.assertEqual(self.sender.call_count, 2, 'adopting the previous release\'s notice sends nothing')

    def test_an_unsent_notice_the_previous_release_stepped_over_never_holds_the_next(self):
        """R2 through a rollback: this release dies between the ledger and status.json on a lifted
        failure notice, the previous release then checks once (it rewrites status.json and never
        opens the ledger), and this release returns. The ledger still stamps a failure that no
        request recorded in status.json backs: it must not hold the real failure."""
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at)                                                  # warning notice at t0
        self.recovery.return_value['condition'] = 'healthy'
        a.check(self.at + timedelta(hours=1))
        self.health.return_value = 'backup_failed'
        crash, _ = IncidentLedgerTests.crash_on_second_write(self)
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=2))
        with patch.object(self.old, 'DIRECTORY', self.alerts):
            result, _ = self.old.check(self.at + timedelta(hours=2, minutes=5))
        self.assertEqual(result['alert']['outcome'], 'cooldown_suppressed', 'the previous release holds by its own rule')
        self.old_sender.assert_not_called()
        stamped = json.loads((self.alerts / a.NOTICES_FILE).read_text())['announced_at']['failure']
        self.assertEqual(stamped, (self.at + timedelta(hours=2)).isoformat(), 'the unbacked stamp is still there')
        result, code = a.check(self.at + timedelta(hours=2, minutes=10))
        self.assertEqual((code, result['condition'], self.sender.call_count), (1, 'backup_failed', 2),
                         "an unsent failure stamped only in the ledger held the real one")
        self.assertIn('(highest: warning)', self.sender.call_args.args[2])

    def test_a_crash_the_previous_release_then_checks_over_is_adopted_and_the_owed_notice_sent(self):
        """⚠️ F1(A), round 2, the refuter's exact sequence. R3's recovery kept the layer a notice
        superseded only while status.json stayed byte-for-byte what the check began from. The
        rollback's `systemctl stop` can kill a check between the ledger and status.json; the previous
        release then checks once, rewriting status.json's check time and condition, and the kept layer
        was dropped: status.json named the escalation at +2h, the ledger described only the unsent one
        at +4h, and every later check and status() refused, forever, with no email."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)                                                   # initial notice at t0
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))                              # escalation at +2h
        self.health.return_value = 'backup_timeout'
        crash, calls = IncidentLedgerTests.crash_on_second_write(self)
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=4))                          # escalation, killed between the writes
        self.assertEqual(calls, [a.NOTICES_FILE, 'status.json'])
        with patch.object(self.old, 'DIRECTORY', self.alerts):
            result, _ = self.old.check(self.at + timedelta(hours=4, minutes=5))   # the previous release, once
        self.assertEqual((result['condition'], result['alert']['outcome']), ('backup_timeout', 'provider_accepted'))
        self.old_sender.assert_not_called()
        shown, _ = a.status(self.at + timedelta(hours=4, minutes=6))
        self.assertNotEqual(shown['condition'], 'monitoring_state_unavailable',
                            'a check the previous release made over a crashed notice wedged status()')
        self.assertEqual((shown['incident']['last_notice'], shown['incident']['last_notice_condition'],
                          shown['incident']['notices_attempted']), ('escalation', 'backup_stale', 2))
        result, code = a.check(self.at + timedelta(hours=4, minutes=10))
        self.assertEqual((code, result['condition'], self.sender.call_count), (1, 'backup_timeout', 3),
                         'the owed escalation was never sent')
        self.assertTrue(result['alert']['provider_accepted'])
        for text in ('Condition: backup_timeout', 'last notice announced backup_stale', 'notice 3'):
            self.assertIn(text, self.sender.call_args.args[2])
        for minutes in (15, 20):
            self.assertEqual(a.check(self.at + timedelta(hours=4, minutes=minutes))[0]['condition'], 'backup_timeout')
        self.assertEqual(self.sender.call_count, 3, 'and it is sent once')

    def test_the_previous_releases_first_notice_is_never_merged_with_an_unsent_one_of_the_same_incident(self):
        """⚠️ F1(B), round 2. A held incident rises and this release's lifted first notice (backup_failed)
        is killed between the ledger and status.json. The previous release later makes ITS first
        notice for the same incident, backup_stale, under the same identity. The ledger's record
        named that identity too, so it was merged over the previous release's receipt: check()
        refused forever ("Alert receipt and monitor state disagree") and status() reported a
        backup_failed notice nobody sent, with a deferral no check decided."""
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at)                                                   # warning notice at t0
        self.recovery.return_value['condition'] = 'healthy'
        a.check(self.at + timedelta(hours=1))                              # closes
        self.recovery.return_value['condition'] = 'offsite_next_run_budget_low'
        result, _ = a.check(self.at + timedelta(hours=2))                  # another warning: held
        self.assertEqual(result['alert']['outcome'], 'cooldown_suppressed')
        held = json.loads((self.alerts / 'status.json').read_text())['incident_id']
        self.health.return_value = 'backup_failed'                         # the held incident rises
        crash, _ = IncidentLedgerTests.crash_on_second_write(self)
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=3))
        self.assertEqual(json.loads((self.alerts / a.NOTICES_FILE).read_text())['incident']['incident_attempt'], held)
        self.recovery.return_value['condition'] = 'healthy'
        self.health.return_value = 'backup_stale'
        with patch.object(self.old, 'DIRECTORY', self.alerts):
            result, _ = self.old.check(self.at + timedelta(hours=24, minutes=5))  # its own first notice
        self.assertTrue(result['alert']['provider_accepted'])
        self.old_sender.assert_called_once()
        self.assertIn('Condition: backup_stale', self.old_sender.call_args.args[2])
        self.assertEqual(json.loads((self.alerts / 'status.json').read_text())['incident_attempt'], held)
        shown, _ = a.status(self.at + timedelta(hours=24, minutes=6))
        self.assertNotEqual(shown['condition'], 'monitoring_state_unavailable')
        self.assertEqual((shown['incident']['last_notice_condition'], shown['incident']['notices_attempted'],
                          shown['incident']['escalation_deferred_until']), ('backup_stale', 1, None),
                         'status() reported a notice nobody sent')
        result, code = a.check(self.at + timedelta(hours=24, minutes=10))
        self.assertEqual((code, result['condition']), (1, 'backup_stale'),
                         "an unsent notice merged over the previous release's receipt wedged the monitor")
        self.assertEqual(result['alert']['provider_message_id'], 'previous-release-id')
        self.assertEqual(result['incident']['conditions_announced'], ['backup_stale'])
        self.assertEqual(self.sender.call_count, 1, 'nothing is owed: the previous release announced it')

    def test_the_previous_release_runs_on_every_state_a_restart_leaves(self):
        """FAIL CLOSED MEANS ALERT writes new shapes: a restart marker, the unreadable files kept under
        names nothing reads, status.json replaced (never removed), and the restart's own notice, as
        an incident's first notice or on its own. The previous release must run on each."""
        self.health.return_value = 'backup_failed'
        a.backup.write_private(self.alerts / 'status.json', b'not json')
        expected, _ = a.check(self.at)                                    # restart as the incident's first notice
        self.assertTrue(expected['state_restarted'])
        checked, shown, _ = self.previous_release_on_a_copy(self.at + timedelta(minutes=1))
        self.assertEqual((checked['condition'], checked['alert']['outcome']), ('backup_failed', 'provider_accepted'))
        self.assertNotEqual(shown['condition'], 'monitoring_state_unavailable')
        self.health.return_value = 'healthy'
        (self.alerts / 'status.json').write_text('not json')
        expected, _ = a.check(self.at + timedelta(hours=25))              # restart on its own, while healthy
        self.assertEqual((expected['condition'], expected['state_restarted']), ('healthy', True))
        checked, shown, _ = self.previous_release_on_a_copy(self.at + timedelta(hours=25, minutes=1))
        self.assertEqual((checked['condition'], shown['condition']), ('healthy', 'healthy'))
        self.old_sender.assert_not_called()
        self.health.return_value = 'backup_failed'                        # killed after the restart, before any write
        (self.alerts / 'status.json').write_text('not json')
        with patch.object(a, 'write_state', side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=50))
        self.assertEqual(json.loads((self.alerts / 'status.json').read_text())['condition'], 'monitoring_stale')
        checked, shown, _ = self.previous_release_on_a_copy(self.at + timedelta(hours=50, minutes=1))
        self.assertEqual(checked['condition'], 'backup_failed', 'status.json went missing inside a restart')
        self.assertNotEqual(shown['condition'], 'monitoring_state_unavailable')


class CrossIncidentSeverityTests(unittest.TestCase):
    """A MORE SEVERE incident opening inside the between-incidents cooldown is not held by it."""
    setUp = BackupAlertsTests.setUp

    def test_a_failure_incident_after_a_warning_incident_is_announced_once(self):
        self.recovery.return_value['condition'] = 'offsite_capacity_low'           # warning
        a.check(self.at)
        self.recovery.return_value['condition'] = 'healthy'
        a.check(self.at + timedelta(hours=1))                                       # incident closes
        self.health.return_value = 'backup_failed'                                  # failure, 2 h after the warning
        result, code = a.check(self.at + timedelta(hours=2))
        self.assertEqual((code, self.sender.call_count), (1, 2),
                         'a failure opening two hours after a warning notice was held by the cooldown')
        self.assertTrue(result['alert']['provider_accepted'])
        subject, body = self.sender.call_args.args[1:]
        self.assertEqual(subject, '[QuillMD operations] ESCALATION: a more severe backup incident opened')
        for text in ('Condition: backup_failed', 'more severe (failure)', '(highest: warning)',
                     'inside the 24-hour interval between incidents'):
            self.assertIn(text, body)
        self.assertEqual(json.loads((self.alerts / 'status.json').read_text())['incident_attempt'],
                         json.loads((self.alerts / 'status.json').read_text())['incident_id'])
        # Healthy <-> failure flapping for the rest of the day: nothing more.
        for step in range(1, 264):
            self.health.return_value = 'healthy' if step % 2 else 'backup_failed'
            a.check(self.at + timedelta(hours=2, minutes=5 * step))
        self.assertEqual(self.sender.call_count, 2)

    def test_same_or_lower_severity_flapping_after_a_notice_sends_nothing_extra(self):
        for first, flap in (('offsite_capacity_low', 'offsite_capacity_low'),       # warning, warning
                            ('backup_failed', 'offsite_capacity_low'),              # failure, then a warning
                            ('backup_failed', 'backup_stale')):                     # failure, failure
            with self.subTest(first=first, flap=flap):
                self.sender.reset_mock()
                for path in self.alerts.iterdir():
                    path.unlink()
                for step in range(288):                                              # one day, every 5 min
                    condition = (first if step == 0 else flap) if step % 2 == 0 else 'healthy'
                    local = condition if condition.startswith('backup') else 'healthy'
                    self.health.return_value = local
                    self.recovery.return_value['condition'] = 'healthy' if local != 'healthy' else condition
                    a.check(self.at + timedelta(minutes=5 * step))
                self.assertEqual(self.sender.call_count, 1)

    def test_warning_then_healthy_failure_flapping_is_at_most_one_extra_notice_a_day(self):
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at)
        self.recovery.return_value['condition'] = 'healthy'
        for step in range(1, 288):
            self.health.return_value = 'backup_failed' if step % 2 else 'healthy'
            a.check(self.at + timedelta(minutes=5 * step))
        self.assertEqual(self.sender.call_count, 2)            # the warning, and ONE lifted failure
        self.health.return_value = 'backup_failed'
        a.check(self.at + timedelta(minutes=5 * 289))          # a day after the lifted failure, not before
        self.assertEqual(self.sender.call_count, 3)

    def test_a_held_incident_that_rises_above_the_recent_notices_is_announced_when_it_rises(self):
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at)
        self.recovery.return_value['condition'] = 'healthy'
        a.check(self.at + timedelta(hours=1))
        self.recovery.return_value['condition'] = 'offsite_next_run_budget_low'      # another warning: held
        result, _ = a.check(self.at + timedelta(hours=2))
        self.assertEqual(result['alert']['outcome'], 'cooldown_suppressed')
        self.health.return_value = 'backup_failed'                                   # the SAME incident rises
        a.check(self.at + timedelta(hours=3))
        self.assertEqual(self.sender.call_count, 2)
        self.assertIn('Condition: backup_failed', self.sender.call_args.args[2])

    def test_the_window_is_the_last_24_hours_not_the_incident_history(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)                                                             # failure notice at t
        self.health.return_value = 'healthy'
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at + timedelta(hours=23))                                       # warning notice at t+23h
        self.assertEqual(self.sender.call_count, 2)
        self.recovery.return_value['condition'] = 'healthy'
        a.check(self.at + timedelta(hours=23, minutes=30))
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=25))       # the t failure is 25 h old: only the warning is recent
        self.assertEqual(self.sender.call_count, 3)
        self.assertIn('(highest: warning)', self.sender.call_args.args[2])

    def test_an_unknown_recent_notice_holds_the_cooldown(self):
        """The previous release sent something an hour ago and kept no ledger: it may have been a
        failure, so a failure now is held exactly as today."""
        a.backup.write_private(self.alerts / 'status.json', json.dumps({
            'format': 1, 'last_check_at': self.at.isoformat(), 'condition': 'healthy', 'incident_id': None,
            'incident_attempt': None, 'last_attempt_at': (self.at - timedelta(hours=1)).isoformat()}).encode())
        self.health.return_value = 'backup_failed'
        result, _ = a.check(self.at + timedelta(minutes=5))
        self.assertEqual(result['alert']['outcome'], 'cooldown_suppressed')
        self.sender.assert_not_called()

    def test_the_previous_releases_own_recent_notice_is_known_by_its_receipt(self):
        """...but a notice whose receipt the previous release left behind is known, and a warning
        it announced an hour ago does not hold a failure."""
        IncidentNotificationTests.legacy(self)                    # warning incident, notice at t, no ledger
        self.recovery.return_value['condition'] = 'healthy'
        a.check(self.at + timedelta(hours=1))                     # closes; the notice is read from its receipt
        self.health.return_value = 'backup_failed'
        a.check(self.at + timedelta(hours=2))
        self.assertEqual(self.sender.call_count, 1)
        self.assertIn('(highest: warning)', self.sender.call_args.args[2])


class ConcurrentStatusReadTests(unittest.TestCase):
    """⚠️ R4. status() read status.json and then the ledger with no lock, while check() writes them
    under the monitor lock. A check landing between its two reads made status() report the monitor
    broken. The publisher runs status() every five minutes, beside the check's own five-minute timer."""
    setUp = BackupAlertsTests.setUp

    def test_a_status_read_across_a_checks_writes_is_consistent_and_the_check_still_runs(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))                  # status.json names a later notice
        self.health.return_value = 'backup_timeout'
        real, paused, release, results = a.read_notices, threading.Event(), threading.Event(), {}

        def pausing():
            if threading.current_thread().name == 'status-reader' and not paused.is_set():
                paused.set()                                   # status.json is read; the ledger is not
                release.wait(30)
            return real()

        def reader():
            results['status'] = a.status(self.at + timedelta(hours=2, minutes=1))

        def writer():
            results['check'] = a.check(self.at + timedelta(hours=4))
        with patch.object(a, 'read_notices', side_effect=pausing), \
                patch.object(a, 'LOCK_WAIT_SECONDS', 30, create=True):
            reading = threading.Thread(target=reader, name='status-reader')
            reading.start()
            self.assertTrue(paused.wait(30))
            writing = threading.Thread(target=writer, name='check-writer')
            writing.start()
            writing.join(1.5)                                  # unlocked, the whole check lands in here
            release.set()
            reading.join(30)
            writing.join(30)
        self.assertFalse(reading.is_alive() or writing.is_alive())
        shown, _ = results['status']
        self.assertNotEqual(shown['condition'], 'monitoring_state_unavailable',
                            'a concurrent check made status() report the monitor broken')
        self.assertEqual(shown['incident']['last_notice_condition'], 'backup_stale')
        checked, _ = results['check']
        self.assertEqual(checked['condition'], 'backup_timeout', 'a status reader made the check refuse')
        self.assertEqual(self.sender.call_count, 3)

    def test_waiting_for_a_reader_is_bounded_so_a_parallel_check_is_still_refused(self):
        a.check(self.at)
        before = (self.alerts / 'status.json').read_bytes()
        descriptor = os.open(self.alerts / 'monitor.lock', os.O_RDWR)
        self.addCleanup(os.close, descriptor)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)      # a parallel check, holding on
        started = datetime.now(timezone.utc)
        with patch.object(a, 'LOCK_WAIT_SECONDS', 0.5):
            result, code = a.check(self.at + timedelta(minutes=5))
        waited = (datetime.now(timezone.utc) - started).total_seconds()
        self.assertEqual((code, result['condition']), (1, 'monitoring_state_unavailable'))
        self.assertGreaterEqual(waited, 0.5)
        self.assertLess(waited, 10, 'the wait for a reader is not bounded')
        self.assertEqual((self.alerts / 'status.json').read_bytes(), before)
        self.sender.assert_not_called()

    def test_status_takes_the_lock_without_creating_or_writing_anything(self):
        """The publisher runs status() in a sandbox with no write grant to this directory, so the
        reader's lock is opened read-only and never created: a writable open would fail there."""
        self.assertEqual(a.status(self.at)[0]['condition'], 'monitoring_stale')   # fresh: no lock file yet
        self.assertEqual(list(self.alerts.iterdir()), [], 'status() created something')
        a.check(self.at)
        real, opened = os.open, []

        def recording(path, flags, *args, **kwargs):
            opened.append((str(path), flags))
            return real(path, flags, *args, **kwargs)
        with patch.object(a.os, 'open', side_effect=recording):
            self.assertEqual(a.status(self.at + timedelta(minutes=1))[0]['condition'], 'healthy')
        writable = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        self.assertEqual([flags & writable for path, flags in opened if path.endswith('monitor.lock')], [0])
        self.assertEqual([path for path, flags in opened if flags & writable and path.startswith(str(self.alerts))], [])


class TransportImportPathTests(unittest.TestCase):
    """⚠️ configured_transport() inserted rebuild/ into sys.path on EVERY call, unconditionally.

    Harmless under the unit (each tick is a fresh process), but a long-lived process accumulates
    one entry per check: one run of this module took sys.path from 5 entries to 2,271 (6
    distinct). A multiprocessing `spawn` child inherits that path, so the offsite-audit watchdog
    tests that run later in the same process timed out before their worker started (2 failures,
    only after this module, never alone).
    """
    setUp = BackupAlertsTests.setUp

    def test_repeated_checks_do_not_grow_the_import_path(self):
        self.addCleanup(sys.path.__setitem__, slice(None), list(sys.path))
        a.check(self.at)
        before = list(sys.path)
        for minutes in range(5, 255, 5):
            a.check(self.at + timedelta(minutes=minutes))
        self.assertEqual(sys.path, before)


class IncidentLedgerTests(unittest.TestCase):
    """The sidecar ledger: created on first need, private, and consistent across a crash."""
    setUp = BackupAlertsTests.setUp
    state = IncidentNotificationTests.state
    ledger = IncidentNotificationTests.ledger

    def crash_on_second_write(self):
        real, calls = a.scheduled.atomic_status, []

        def write(path, value):
            calls.append(path.name)
            if len(calls) == 2:
                raise KeyboardInterrupt
            return real(path, value)
        return patch.object(a.scheduled, 'atomic_status', side_effect=write), calls

    def test_created_on_first_need_only(self):
        for minutes in range(0, 60, 5):
            a.check(self.at + timedelta(minutes=minutes))
        self.assertFalse((self.alerts / a.NOTICES_FILE).exists(), 'a monitor that announced nothing keeps no ledger')
        self.health.return_value = 'backup_failed'
        a.check(self.at + timedelta(hours=1))
        self.assertEqual(self.ledger()['incident']['incident_id'], self.state()['incident_id'])
        self.assertEqual((self.alerts / a.NOTICES_FILE).stat().st_mode & 0o777, 0o600)
        self.health.return_value = 'healthy'
        a.check(self.at + timedelta(hours=2))
        self.assertIsNone(self.ledger()['incident'])
        self.assertEqual(self.ledger()['announced_at']['failure'], (self.at + timedelta(hours=1)).isoformat())

    def test_unsafe_or_malformed_ledger_restarts_once_a_day_without_following_or_disclosing_it(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        path = self.alerts / a.NOTICES_FILE
        preserved = self.root / 'preserved-ledger'
        path.rename(preserved)
        path.symlink_to(preserved)
        original = preserved.read_bytes()
        result, _ = a.check(self.at + timedelta(days=2))
        self.assertEqual((result['condition'], result['state_unreadable'], self.sender.call_count),
                         ('backup_failed', 'ledger_invalid', 2))
        self.assertEqual(preserved.read_bytes(), original, 'the link is kept, never followed or written through')
        kept = [item for item in self.alerts.iterdir() if item.is_symlink()]
        self.assertEqual([os.readlink(item) for item in kept], [str(preserved)])
        self.assertFalse(path.is_symlink())
        path.unlink()
        a.backup.write_private(path, b'private-clinical-canary')
        result, _ = a.check(self.at + timedelta(days=2, minutes=5))   # inside the day: held, and said so
        self.assertEqual((result['condition'], result['state_unreadable'], result['state_restarted']),
                         ('monitoring_state_unavailable', 'ledger_invalid', False))
        self.assertNotIn('canary', json.dumps(result))
        self.assertEqual(self.sender.call_count, 2)
        result, _ = a.check(self.at + timedelta(days=3))
        self.assertEqual((result['condition'], self.sender.call_count), ('backup_failed', 3))
        self.assertNotIn('canary', ''.join(self.sender.call_args.args[1:]))

    def test_lost_status_with_the_ledger_still_present_is_restarted_and_announced(self):
        """Not the fresh-monitor crash: this ledger keeps no layer, so nothing says what began."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        for path in self.alerts.glob('incident-*-*.json'):
            path.unlink()
        (self.alerts / 'status.json').unlink()
        self.assertTrue((self.alerts / a.NOTICES_FILE).exists())
        ledger = (self.alerts / a.NOTICES_FILE).read_bytes()
        result, _ = a.check(self.at + timedelta(days=2))
        self.assertEqual((result['condition'], result['state_unreadable'], self.sender.call_count),
                         ('backup_failed', 'state_missing', 2))
        self.assertEqual([item.read_bytes() for item in self.alerts.glob('monitor-restart-*-incident-notices.json')],
                         [ledger], 'the ledger is kept for diagnosis')

    def test_an_inconsistent_state_is_refused_on_the_way_out_and_nothing_is_written(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        before = {path.name: path.read_bytes() for path in self.alerts.glob('*.json')}
        state = a.read_state()
        state.update(incident_id=None, incident_attempt=None)      # a partial close: stale extension keys
        with self.assertRaises(RuntimeError):
            a.write_state(state)
        self.assertEqual({path.name: path.read_bytes() for path in self.alerts.glob('*.json')}, before)

    def test_crash_between_the_two_writes_of_a_notice_after_a_first_notice_recovers(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        first = self.state()['incident_attempt']
        self.health.return_value = 'backup_stale'
        crash, calls = self.crash_on_second_write()
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=2))
        self.assertEqual(calls, [a.NOTICES_FILE, 'status.json'], 'the ledger leads while an incident is open')
        phantom = self.ledger()['incident']['incident_attempt']
        self.assertEqual(json.loads((self.alerts / 'status.json').read_text())['incident_attempt'], first)
        self.assertFalse(list(self.alerts.glob(f'incident-{phantom}-*')), 'no request began for it')
        result, code = a.check(self.at + timedelta(hours=3))
        self.assertEqual((code, result['condition'], self.sender.call_count), (1, 'backup_stale', 2))
        self.assertNotEqual(self.state()['incident_attempt'], phantom)
        self.assertEqual(self.state()['incident_conditions_announced'], ['backup_failed', 'backup_stale'])

    def test_crash_between_the_two_writes_of_a_lifted_first_notice_sends_it_at_the_next_check(self):
        """⚠️ R2, the exact sequence. The ledger is written first and records the failure as announced;
        the process dies before status.json records the attempt, so no request ever began. That
        unsent 'failure' must not hold the real one for the rest of the day."""
        self.recovery.return_value['condition'] = 'offsite_capacity_low'           # warning notice at t0
        a.check(self.at)
        self.recovery.return_value['condition'] = 'healthy'
        a.check(self.at + timedelta(hours=1))                                       # the incident closes
        self.health.return_value = 'backup_failed'                                  # qualifies for the lift
        crash, calls = self.crash_on_second_write()
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=2))
        self.assertEqual(calls, [a.NOTICES_FILE, 'status.json'])
        status = json.loads((self.alerts / 'status.json').read_text())
        self.assertEqual((status['incident_id'], status['last_attempt_at']), (None, self.at.isoformat()),
                         'status.json never recorded the attempt')
        self.assertEqual(self.ledger()['announced_at']['failure'], (self.at + timedelta(hours=2)).isoformat())
        phantom = self.ledger()['incident']['incident_attempt']
        self.assertFalse(list(self.alerts.glob(f'incident-{phantom}-*')), 'no request began for it')
        result, code = a.check(self.at + timedelta(hours=2, minutes=5))
        self.assertEqual((code, result['condition'], self.sender.call_count), (1, 'backup_failed', 2),
                         "the ledger's unsent failure held the real one")
        self.assertTrue(result['alert']['provider_accepted'])
        self.assertIn('(highest: warning)', self.sender.call_args.args[2])
        self.assertEqual(a.check(self.at + timedelta(hours=2, minutes=10))[1], 1)
        self.assertEqual(self.sender.call_count, 2, 'and it is sent once')

    def test_crash_between_the_two_writes_when_a_held_incident_rises_sends_it_at_the_next_check(self):
        """R2's held variant: the incident is already open and held at a warning, then rises."""
        self.recovery.return_value['condition'] = 'offsite_capacity_low'
        a.check(self.at)
        self.recovery.return_value['condition'] = 'healthy'
        a.check(self.at + timedelta(hours=1))
        self.recovery.return_value['condition'] = 'offsite_next_run_budget_low'     # another warning: held
        result, _ = a.check(self.at + timedelta(hours=2))
        self.assertEqual(result['alert']['outcome'], 'cooldown_suppressed')
        held = self.state()['incident_id']
        self.health.return_value = 'backup_failed'                                   # the held incident rises
        crash, calls = self.crash_on_second_write()
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=3))
        status = json.loads((self.alerts / 'status.json').read_text())
        self.assertEqual((status['incident_id'], status['incident_attempt']), (held, None))
        self.assertEqual(self.ledger()['incident']['incident_attempt'], held)
        self.assertFalse(list(self.alerts.glob(f'incident-{held}-*')), 'no request began for it')
        result, code = a.check(self.at + timedelta(hours=3, minutes=5))
        self.assertEqual((code, result['condition'], self.sender.call_count), (1, 'backup_failed', 2),
                         "the ledger's unsent failure held the real one")
        self.assertEqual(self.state()['incident_id'], held)

    def test_crash_between_the_two_writes_of_a_later_notice_recovers_and_sends_it(self):
        """⚠️ R3. This used to pin a PERMANENT monitoring_state_unavailable: a monitor that emails
        nothing, forever, over a notice that provably never began (status.json, the commit point,
        never named it, and no request record exists for it). It must recover exactly the notice
        status.json does name, and send what is owed at the next check, once."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))                 # status.json now names a LATER notice
        committed = self.state()
        self.health.return_value = 'backup_timeout'
        crash, calls = self.crash_on_second_write()
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=4))
        self.assertEqual(calls, [a.NOTICES_FILE, 'status.json'])
        phantom = self.ledger()['incident']['incident_attempt']
        self.assertEqual(json.loads((self.alerts / 'status.json').read_text())['incident_attempt'],
                         committed['incident_attempt'])
        self.assertFalse(list(self.alerts.glob(f'incident-{phantom}-*')), 'no request began for it')
        shown, _ = a.status(self.at + timedelta(hours=4, minutes=1))
        self.assertNotEqual(shown['condition'], 'monitoring_state_unavailable')
        self.assertEqual((shown['incident']['last_notice'], shown['incident']['last_notice_condition'],
                          shown['incident']['notices_attempted']), ('escalation', 'backup_stale', 2))
        result, code = a.check(self.at + timedelta(hours=5))
        self.assertEqual((code, result['condition'], self.sender.call_count), (1, 'backup_timeout', 3),
                         'a crash that sent nothing wedged the monitor')
        self.assertTrue(result['alert']['provider_accepted'])
        state = self.state()
        self.assertNotIn(state['incident_attempt'], (phantom, committed['incident_attempt']))
        self.assertEqual((state['incident_attempt_notice'], state['incident_attempt_count'],
                          state['incident_conditions_announced'], state['incident_opened_at']),
                         ('escalation', 3, ['backup_failed', 'backup_stale', 'backup_timeout'], self.at.isoformat()))
        for text in ('Condition: backup_timeout', 'last notice announced backup_stale', 'notice 3'):
            self.assertIn(text, self.sender.call_args.args[2])
        self.assertFalse(list(self.alerts.glob(f'incident-{phantom}-*')), 'the unsent identity is never used')
        for hours in (6, 7):
            a.check(self.at + timedelta(hours=hours))
        self.assertEqual(self.sender.call_count, 3, 'and it is sent once')

    def test_crash_between_the_two_writes_of_a_fresh_monitors_first_notice_recovers(self):
        """R3's first-notice form: on a fresh directory status.json does not exist yet, so the lost-state
        guard (status.json missing while incident evidence remains) saw the ledger alone and refused
        forever. The ledger kept the pristine state it began from, and no request record exists."""
        self.health.return_value = 'backup_failed'
        crash, calls = self.crash_on_second_write()
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at)
        self.assertEqual(calls, [a.NOTICES_FILE, 'status.json'])
        self.assertFalse((self.alerts / 'status.json').exists())
        self.assertEqual(sorted(path.name for path in self.alerts.glob('incident-*')), [a.NOTICES_FILE])
        result, code = a.check(self.at + timedelta(minutes=5))
        self.assertEqual((code, result['condition'], self.sender.call_count), (1, 'backup_failed', 1),
                         'a crash that sent nothing wedged a fresh monitor')
        self.assertTrue(result['alert']['provider_accepted'])
        a.check(self.at + timedelta(minutes=10))
        self.sender.assert_called_once()

    def test_an_unreadable_request_record_for_the_discarded_notice_restarts_and_never_sends_it(self):
        """The recovery discards a notice only because nothing can have been sent for it. If a request
        record exists for it that cannot be read, that premise cannot be checked: the discarded
        notice is never sent, and the record restarts, announced (it used to refuse for ever)."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        crash, _ = self.crash_on_second_write()
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=2))
        phantom = self.ledger()['incident']['incident_attempt']
        a.backup.write_private(self.alerts / f'incident-{phantom}-pending.json', b'{}')
        result, code = a.check(self.at + timedelta(hours=3))
        self.assertEqual((code, result['condition'], result['state_unreadable'], self.sender.call_count),
                         (1, 'backup_stale', 'notice_record_invalid', 2))
        self.assertIn('MONITOR RESTARTED', self.sender.call_args.args[1])
        self.assertNotIn(phantom, self.sender.call_args.args[2])
        self.assertEqual((self.alerts / f'incident-{phantom}-pending.json').read_bytes(), b'{}')
        self.assertFalse((self.alerts / f'incident-{phantom}-result.json').exists())
        a.check(self.at + timedelta(hours=4))
        self.assertEqual(self.sender.call_count, 2)

    def test_the_recovered_notice_is_exactly_the_one_status_json_names_even_a_reminder(self):
        """What is recovered is the committed record itself, not a guess at it: a reminder cannot be
        told from an escalation by anything the later notice leaves behind."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        a.check(self.at + timedelta(hours=24))                # a reminder: status.json names it
        committed = self.state()
        self.assertEqual(committed['incident_attempt_notice'], 'reminder')
        self.health.return_value = 'backup_stale'
        crash, _ = self.crash_on_second_write()
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=25))
        recovered = a.read_state()
        self.assertEqual({key: recovered[key] for key in a.RECORD_KEYS + ('announced_at',)},
                         {key: committed[key] for key in a.RECORD_KEYS + ('announced_at',)})
        a.check(self.at + timedelta(hours=25, minutes=5))
        self.assertEqual(self.sender.call_count, 3)
        self.assertIn('Condition: backup_stale', self.sender.call_args.args[2])

    def test_crash_between_the_two_writes_of_a_close_leaves_a_working_monitor(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))                 # a later notice: the hard case to close
        self.health.return_value = 'healthy'
        crash, calls = self.crash_on_second_write()
        with crash, self.assertRaises(KeyboardInterrupt):
            a.check(self.at + timedelta(hours=3))
        self.assertEqual(calls, ['status.json', a.NOTICES_FILE], 'status.json leads once the incident is closed')
        self.assertEqual(a.check(self.at + timedelta(hours=4))[0]['condition'], 'healthy')
        self.health.return_value = 'backup_timeout'
        result, _ = a.check(self.at + timedelta(hours=30))
        self.assertEqual((result['condition'], self.sender.call_count), ('backup_timeout', 3))

    def test_an_incident_this_release_opened_keeps_its_opening_when_the_previous_release_notifies(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        self.health.return_value = 'healthy'
        a.check(self.at + timedelta(hours=1))
        self.health.return_value = 'backup_stale'
        a.check(self.at + timedelta(hours=2))                 # opened, held by the cooldown
        held = self.state()['incident_id']
        # The previous release's check, as after a rollback: its first notice for the same incident.
        status = json.loads((self.alerts / 'status.json').read_text())
        receipt = {'format': 1, 'kind': 'operational', 'condition': 'backup_stale',
                   'attempted_at': (self.at + timedelta(hours=25)).isoformat(), 'outcome': 'provider_accepted',
                   'provider_message_id': 'previous-release-id', 'provider_accepted': True,
                   'delivery_confirmed': False, 'inbox_receipt_confirmed': False}
        a.backup.write_private(self.alerts / f'incident-{held}-result.json', json.dumps(receipt).encode())
        # Exactly the fields the previous release's check writes: its check time and its attempt.
        (self.alerts / 'status.json').write_text(json.dumps(dict(
            status, incident_attempt=held, last_attempt_at=receipt['attempted_at'],
            last_check_at=receipt['attempted_at'])))
        result, _ = a.check(self.at + timedelta(hours=25, minutes=5))
        state = self.state()
        self.assertEqual((state['incident_opened_at'], state['incident_attempt_count'], self.sender.call_count),
                         ((self.at + timedelta(hours=2)).isoformat(), 1, 1))
        self.assertEqual(result['alert']['provider_message_id'], 'previous-release-id')


class FailClosedMeansAlertTests(unittest.TestCase):
    """⚠️ THE LEAD'S DESIGN RULE, 2026-09-27: FOR AN ALERTING MONITOR, FAIL CLOSED MEANS ALERT, NOT SILENCE.

    A state this release cannot validate or recover must never leave the monitor refusing forever
    with no email. At most once per 24 hours it sends an operator notice saying plainly that it could
    not read its own state (a reason label, no content), what the backup condition is now, and that it
    has restarted its incident record from now; then it continues from a fresh, valid state. A
    possible duplicate is acceptable; permanent silence is not. Mocked transport only."""
    setUp = BackupAlertsTests.setUp
    write_config = BackupAlertsTests.write_config
    state = IncidentNotificationTests.state
    sent = IncidentNotificationTests.sent

    def assert_restart_notice(self, reason, condition):
        subject, body = self.sent()[-1]
        self.assertEqual(subject, '[QuillMD operations] MONITOR RESTARTED: the backup monitor could not read its own state')
        for text in (f'(reason: {reason})', 'restarted its incident record from this check',
                     f'Condition: {condition}', f'Severity: {a.severity(condition)}', a.ERRORS[condition],
                     'No patient information or credentials are included.'):
            self.assertIn(text, body)

    def test_a_named_notice_with_no_request_record_sends_one_restart_notice_and_resumes(self):
        """The shape the doc used to call "fails closed for operator review": status.json names a
        notice for which no request record exists. It used to refuse, silently, at every check."""
        self.health.return_value = 'backup_failed'
        with patch.object(a, 'attempt_alert', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                a.check(self.at)
        named = json.loads((self.alerts / 'status.json').read_text())['incident_attempt']
        self.assertFalse(list(self.alerts.glob(f'incident-{named}-*')))
        result, code = a.check(self.at + timedelta(minutes=5))
        self.assertEqual((code, result['condition'], self.sender.call_count), (1, 'backup_failed', 1),
                         'a state the monitor could not validate left it refusing with no email')
        self.assertEqual((result['state_unreadable'], result['state_restarted']), ('notice_record_missing', True))
        self.assert_restart_notice('notice_record_missing', 'backup_failed')
        self.assertTrue(result['alert']['provider_accepted'])
        state = self.state()
        self.assertEqual((state['incident_opened_at'], state['incident_attempt_notice'], state['incident_attempt_count'],
                          state['incident_conditions_announced']),
                         ((self.at + timedelta(minutes=5)).isoformat(), 'initial', 1, ['backup_failed']))
        self.assertNotEqual(state['incident_id'], named)
        self.assertFalse(list(self.alerts.glob(f'incident-{named}-*')), 'the unrecorded notice is never sent')
        shown, _ = a.status(self.at + timedelta(minutes=6))
        self.assertEqual((shown['condition'], shown['incident']['last_notice_condition']), ('backup_failed', 'backup_failed'))
        result, code = a.check(self.at + timedelta(minutes=10))
        self.assertEqual((code, result['condition'], self.sender.call_count), (1, 'backup_failed', 1))
        self.assertNotIn('state_unreadable', result)

    def test_a_restart_notice_is_sent_at_most_once_a_day_and_the_monitor_is_never_silent_for_good(self):
        self.health.return_value = 'backup_failed'
        a.check(self.at)                                                    # an ordinary first notice
        ledger = self.alerts / a.NOTICES_FILE

        def corrupt():
            ledger.unlink()
            a.backup.write_private(ledger, b'private-clinical-canary')
        corrupt()
        result, _ = a.check(self.at + timedelta(hours=1))
        self.assertEqual((result['condition'], result.get('state_unreadable'), result.get('state_restarted'),
                          self.sender.call_count), ('backup_failed', 'ledger_invalid', True, 2),
                         'a ledger the monitor could not read left it refusing with no email')
        self.assert_restart_notice('ledger_invalid', 'backup_failed')
        for hours in (2, 24):                                               # corrupted again inside the day
            corrupt()
            before = {path.name: path.read_bytes() for path in self.alerts.iterdir()}
            result, code = a.check(self.at + timedelta(hours=hours))
            self.assertEqual((code, result['condition'], result['state_unreadable'], result['state_restarted']),
                             (1, 'monitoring_state_unavailable', 'ledger_invalid', False))
            self.assertEqual(result['next_state_notice_at'], (self.at + timedelta(hours=25)).isoformat())
            self.assertEqual({path.name: path.read_bytes() for path in self.alerts.iterdir()}, before,
                             'a held restart changes nothing')
            self.assertEqual(self.sender.call_count, 2)
        result, _ = a.check(self.at + timedelta(hours=25))                  # a day after the last one
        self.assertEqual((result['condition'], result['state_restarted'], self.sender.call_count),
                         ('backup_failed', True, 3))
        self.assert_restart_notice('ledger_invalid', 'backup_failed')
        for subject, body in self.sent():
            self.assertNotIn('canary', subject + body)
        self.assertNotIn('canary', json.dumps(result))

    def test_a_restart_while_healthy_is_announced_and_holds_nothing(self):
        a.backup.write_private(self.alerts / 'status.json', b'{"condition":"private-clinical-canary"}')
        result, code = a.check(self.at)
        self.assertEqual((code, result['condition'], result.get('state_unreadable'), self.sender.call_count),
                         (1, 'healthy', 'state_invalid', 1), 'an unreadable status.json left the monitor silent')
        self.assert_restart_notice('state_invalid', 'healthy')
        self.assertNotIn('canary', json.dumps(result) + ''.join(self.sent()[-1]))
        raw = json.loads((self.alerts / 'status.json').read_text())
        self.assertEqual((raw['incident_id'], raw['incident_attempt'], raw['last_attempt_at']), (None, None, None))
        kept = [path for path in self.alerts.iterdir() if path.read_bytes() == b'{"condition":"private-clinical-canary"}']
        self.assertEqual(len(kept), 1, 'the unreadable file is kept for diagnosis')
        self.assertFalse(kept[0].name.startswith('incident-'))
        self.health.return_value = 'backup_failed'
        result, _ = a.check(self.at + timedelta(minutes=5))
        self.assertEqual((result['condition'], self.sender.call_count), ('backup_failed', 2),
                         'a restart notice announcing a healthy state held a failure')
        self.assertIn('Backup recovery requires attention', self.sent()[-1][0])

    def test_without_a_working_email_configuration_nothing_is_restarted(self):
        """Nothing can be sent, so nothing about the unreadable state may change: it is kept for the
        check that can announce the restart."""
        a.backup.write_private(self.alerts / 'status.json', b'not json')
        self.write_config(enabled=False)
        result, code = a.check(self.at)
        self.assertEqual((code, result['condition'], result['state_unreadable'], result['state_restarted'],
                          result['next_state_notice_at']), (1, 'monitoring_state_unavailable', 'state_invalid', False, None))
        self.assertEqual(sorted(path.name for path in self.alerts.iterdir()), ['monitor.lock', 'status.json'])
        self.assertEqual((self.alerts / 'status.json').read_bytes(), b'not json')
        self.sender.assert_not_called()
        self.write_config()
        self.assertEqual(a.check(self.at + timedelta(minutes=5))[0]['state_restarted'], True)
        self.sender.assert_called_once()

    def test_a_restart_counts_toward_the_day_only_once_its_request_began(self):
        """A restart stopped before its notice's request began sent nothing, so it holds nothing: the
        next check restarts again and announces it."""
        self.health.return_value = 'backup_failed'
        a.check(self.at)
        (self.alerts / 'status.json').write_text('not json')
        with patch.object(a, 'attempt_alert', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                a.check(self.at + timedelta(hours=1))
        markers = [path for path in self.alerts.iterdir() if a.RESTART_MARKER.fullmatch(path.name)]
        self.assertEqual(len(markers), 1)
        self.assertFalse(a.requested('incident-' + a.RESTART_MARKER.fullmatch(markers[0].name)[1]))
        result, _ = a.check(self.at + timedelta(hours=1, minutes=5))
        self.assertEqual((result['state_unreadable'], result['state_restarted'], self.sender.call_count),
                         ('notice_record_missing', True, 2))
        self.assertIn('MONITOR RESTARTED', self.sent()[-1][0])

    def test_a_restart_marker_that_cannot_be_read_or_lies_in_the_future_holds_nothing(self):
        self.health.return_value = 'backup_failed'
        a.backup.write_private(self.alerts / 'status.json', b'not json')
        a.check(self.at + timedelta(days=3))                                   # a clock three days fast
        self.assertEqual(self.sender.call_count, 1)
        (self.alerts / 'status.json').write_text('not json')
        result, _ = a.check(self.at)                                           # corrected
        self.assertEqual((result['state_restarted'], self.sender.call_count), (True, 2),
                         'a restart stamped in the future held the next for three days')
        (self.alerts / 'status.json').write_text('not json')
        for marker in self.alerts.glob('monitor-restart-*.json'):
            if a.RESTART_MARKER.fullmatch(marker.name):
                marker.write_text('private-clinical-canary')
        result, _ = a.check(self.at + timedelta(minutes=5))
        self.assertEqual((result['state_restarted'], self.sender.call_count), (True, 3))
        self.assertNotIn('canary', json.dumps(result) + ''.join(self.sent()[-1]))

    def test_an_uncertain_restart_notice_is_never_followed_or_repeated(self):
        self.health.return_value = 'backup_failed'
        a.backup.write_private(self.alerts / 'status.json', b'not json')
        self.sender.side_effect = RuntimeError('provider-canary')
        result, code = a.check(self.at)
        self.assertEqual((code, result['condition'], result['state_restarted']), (1, 'alert_delivery_unconfirmed', True))
        self.sender.side_effect = None
        for hours in (1, 25, 49):
            result, code = a.check(self.at + timedelta(hours=hours))
            self.assertEqual((code, result['condition']), (1, 'alert_delivery_unconfirmed'))
            self.assertNotIn('state_unreadable', result)
        self.sender.assert_called_once()


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


class RecoveryFailureIsRecordedNotSwallowed(unittest.TestCase):
    """⚠️ THE `except Exception: pass` THAT CONCEALED A SIX-HOUR OUTAGE.

    On 2026-09-22 the shipped exclusion lock sat on a path this unit's `ProtectSystem=strict`
    sandbox makes read-only, so any `_open_lock()` here raises EROFS and the bare `pass` would
    swallow it.

    ⚠️ AND THE PRECISE CLAIM MATTERS: it did NOT fire during that outage. `recover_publication()`
    returns at `pause_owed()` before opening the lock, and no pause was owed. What was disabled is
    the path that pays a pause DEBT — the one case this hook exists for — so the failure would
    arrive on the day an activation dies mid-act, and arrive silently.

    ⚠️ AND THE RECORD CANNOT GO TO THE DEFERRAL LEDGER. That ledger lives beside the lock, so in
    the failure being recorded it is exactly the thing that is unwritable. A failure record
    written to the path whose unwritability IS the failure is not a record. It goes in this
    unit's own `ReadWritePaths` grant, which is writable precisely when recovery is not.
    """

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / 'backup-alerts'
        patch.object(a, 'DIRECTORY', self.directory).start()
        self.addCleanup(patch.stopall)

    def ledger(self):
        path = self.directory / 'recovery-failures.jsonl'
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def test_the_erofs_that_actually_happened_is_recorded(self):
        a._record_recovery_failure(
            OSError(30, 'Read-only file system',
                    '/opt/meddoc-pro/rebuild/.runtime/publication/.activation-publication.lock'))
        records = self.ledger()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['event'], 'publication_recovery_failed')
        self.assertEqual(records[0]['error_class'], 'OSError')
        self.assertEqual(records[0]['errno'], 30)
        self.assertIn('Read-only file system', records[0]['detail'])

    def test_the_record_lands_in_the_directory_this_unit_can_always_write(self):
        """The grant is `.runtime/backup-alerts`; nothing outside it is writable under the
        sandbox, so the record must be inside it or it is not a record."""
        a._record_recovery_failure(OSError(30, 'Read-only file system', '/somewhere'))
        written = self.directory / 'recovery-failures.jsonl'
        self.assertTrue(written.exists())
        self.assertEqual(written.parent, self.directory)
        self.assertEqual(oct(written.stat().st_mode)[-3:], '600')

    def test_the_recorder_can_never_fail_its_caller(self):
        """⚠️ A recorder that raises reintroduces the exact problem the `except` exists to avoid:
        a monitor that dies trying to report something monitors nothing."""
        with patch.object(a, 'DIRECTORY', Path('/proc/nonexistent-and-unwritable/alerts')):
            a._record_recovery_failure(OSError(30, 'Read-only file system', '/x'))  # must not raise

    def test_records_accumulate_rather_than_overwrite(self):
        """Failure history is evidence; the second tick must not erase the first."""
        for index in range(3):
            a._record_recovery_failure(OSError(30, 'Read-only file system', '/x%d' % index))
        self.assertEqual(len(self.ledger()), 3)

    def test_an_unbounded_message_is_truncated(self):
        a._record_recovery_failure(RuntimeError('x' * 5000))
        self.assertLessEqual(len(self.ledger()[0]['detail']), 300)

    def test_check_records_the_failure_instead_of_swallowing_it(self):
        """⚠️ THE END-TO-END CLAIM, AND THE POSITIVE CONTROL FOR IT.

        `check()` must still not raise — its own outer handler guarantees that — and must no
        longer be SILENT. The control is the second half: with recovery succeeding, nothing is
        written, so a recorder that fired unconditionally would fail here.

        ⚠️ AND THE PATCH COVERS EVERY NAME THE MODULE CAN RESOLVE, because `check()` imports it
        two ways on purpose: `from . import` under the package layout, `import` under the script
        layout its unit actually uses. Patching one name passed under one layout and silently did
        nothing under the other — which is the same two-objects-one-name trap that made the hook
        inert in the first place. Both are patched, so the test cannot pass by missing.
        """
        import contextlib as _contextlib
        import importlib
        targets = []
        for name in ('ops.activation_exclusion', 'activation_exclusion'):
            try:
                targets.append(importlib.import_module(name))
            except ImportError:
                continue
        self.assertTrue(targets, 'the recovery module must be importable under this layout')

        def erofs():
            raise OSError(30, 'Read-only file system',
                          '/opt/meddoc-pro/rebuild/.runtime/publication/.activation-publication.lock')

        with _contextlib.ExitStack() as stack:
            for module in targets:
                stack.enter_context(patch.object(module, 'recover_publication', erofs))
            stack.enter_context(patch.object(a, 'locked',
                                             side_effect=RuntimeError('stop after the recovery step')))
            result, code = a.check()
        self.assertEqual(result['condition'], 'monitoring_state_unavailable')
        self.assertEqual(code, 1)
        self.assertEqual(len(self.ledger()), 1, 'the swallowed failure left no record')
        self.assertEqual(self.ledger()[0]['errno'], 30)

        with _contextlib.ExitStack() as stack:
            for module in targets:
                stack.enter_context(patch.object(module, 'recover_publication',
                                                 lambda: {'recovered': False, 'reason': 'no_pause_owed'}))
            stack.enter_context(patch.object(a, 'locked',
                                             side_effect=RuntimeError('stop after the recovery step')))
            a.check()
        self.assertEqual(len(self.ledger()), 1,
                         'a successful recovery must write nothing; the recorder is not unconditional')


class TheRecoveryHookImportsUnderItsOwnUnit(unittest.TestCase):
    """⚠️ THE HOOK WAS INERT FROM THE MOMENT IT SHIPPED, AND NOTHING SAID SO.

    `quillmd-fresh-backup-alerts.service` runs
    `python -B /opt/meddoc-pro/rebuild/ops/backup_alerts.py check`. Running a FILE puts its own
    directory — `rebuild/ops` — on `sys.path`, not `rebuild`. So `from ops import
    activation_exclusion` raises ModuleNotFoundError on every tick, and in `52b28b36` that landed
    inside a bare `except Exception: pass`.

    The independent recovery path — the one thing positioned to pay a pause debt after an
    activation dies — therefore never ran at all, and the EROFS story everyone told about it
    (including me, in the declaration for this very release) was the wrong mechanism. The
    recorder added alongside it is what surfaced the truth, in production, on its first two
    ticks:

        {"event": "publication_recovery_failed", "error_class": "ModuleNotFoundError",
         "detail": "No module named 'ops'"}    16:39:55Z and 16:44:55Z

    ⚠️ THIS TEST REPRODUCES THE UNIT'S INVOCATION rather than asserting on the source text. A
    grep for the import form would pass the day somebody changes the form and breaks the path
    some other way; only running it the way systemd runs it can fail for the right reason.
    """

    def run_as_the_unit(self, body):
        """A child with ONLY rebuild/ops on sys.path — exactly what `python ops/backup_alerts.py`
        gives you, and nothing this test process has already imported."""
        import subprocess
        ops = str(Path(__file__).resolve().parent)
        program = 'import sys\nsys.path[:] = [%r] + [p for p in sys.path if p != %r]\n' % (ops, ops)
        return subprocess.run([sys.executable, '-B', '-c', program + body],
                              capture_output=True, text=True, timeout=120, cwd=ops)

    def test_the_broken_form_really_does_fail_that_way(self):
        """⚠️ THE POSITIVE CONTROL. Without it the test above could pass because the import is
        trivially satisfiable, rather than because the fallback form is what saves it."""
        done = self.run_as_the_unit('from ops import activation_exclusion\n')
        self.assertNotEqual(done.returncode, 0, 'the shipped form must still fail this way')
        self.assertIn('No module named', done.stderr)

    def test_check_reaches_recovery_under_the_unit_invocation(self):
        """End to end: `check()` must actually call it, not merely be able to import it."""
        done = self.run_as_the_unit(
            'import backup_alerts as a, activation_exclusion as x, pathlib, tempfile\n'
            'from unittest.mock import patch\n'
            'called = []\n'
            'd = pathlib.Path(tempfile.mkdtemp())\n'
            'a.DIRECTORY = d\n'
            'x.recover_publication = lambda: called.append(1) or {"recovered": False}\n'
            'with patch.object(a, "locked", side_effect=RuntimeError("stop")):\n'
            '    a.check()\n'
            'print("CALLED", bool(called), "RECORDED", (d / "recovery-failures.jsonl").exists())\n')
        self.assertEqual(done.returncode, 0, done.stderr[-400:])
        self.assertIn('CALLED True', done.stdout)
        self.assertIn('RECORDED False', done.stdout,
                      'a successful recovery must not write a failure record')
