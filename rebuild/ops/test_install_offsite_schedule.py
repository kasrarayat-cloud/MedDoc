"""Installer boundary tests using files and fake systemd; no host or email acts."""
import copy
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

try:
    from . import install_offsite_schedule as s
except ImportError:
    import install_offsite_schedule as s


class OffsiteInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        saved = dict(vars(s.base))
        self.addCleanup(lambda: vars(s.base).update(saved))
        s.base.ROOT = self.root
        s.base.APP = self.root / 'rebuild'
        s.base.SYSTEMD = self.root / 'systemd'
        s.base.SYSTEMD.mkdir()
        s.scope()
        self.hashes = {}
        for relative in s.base.SOURCES:
            p = self.root / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('synthetic reviewed ' + relative)
            self.hashes[relative] = s.base.digest(p)
        self.state = {'units': {}, 'configuration': {'application': 'unchanged'},
                      'processes': {'doctor': 'unchanged', 'worker': 'unchanged'}}
        self.calls = []
        self.fail_start = False
        for name, value in [('baseline', lambda: copy.deepcopy(self.state)),
                            ('require_absent', lambda before: self.assertNotIn(s.SERVICE, before['units'])),
                            ('require_installed', lambda hashes: self.assertEqual(hashes, self.hashes)),
                            ('compare_baseline', self.compare), ('command', self.command)]:
            item = patch.object(s.base, name, side_effect=value)
            item.start(); self.addCleanup(item.stop)
        p = patch.object(s, 'eligibility', return_value={'synthetic': True}); p.start(); self.addCleanup(p.stop)
        p = patch.object(s, 'first_run_coverage', return_value={'synthetic': True})
        self.coverage = p.start(); self.addCleanup(p.stop)
        p = patch.object(s, 'service_identity', return_value={'User': 'claude'}); p.start(); self.addCleanup(p.stop)
        p = patch.object(s, 'verified_attempt', return_value={'synthetic': True}); p.start(); self.addCleanup(p.stop)
        p = patch.object(s.os, 'getuid', return_value=0); p.start(); self.addCleanup(p.stop)
        p = patch.object(s.os, 'fchown'); p.start(); self.addCleanup(p.stop)

    def command(self, args, timeout=40):
        self.calls.append(args)
        if args == ['systemctl', 'start', s.SERVICE] and self.fail_start:
            raise RuntimeError('synthetic failure contains no live data')
        if args == ['systemctl', 'show', s.SERVICE, '--property=Result,ExecMainStatus']:
            return b'Result=success\nExecMainStatus=0\n'
        if args[:2] == ['systemctl', 'is-active']:
            return b'active\n'
        if args[:2] == ['systemctl', 'is-enabled']:
            return b'enabled\n'
        if args[:2] == ['systemctl', 'enable']:
            self.state['units'][s.base.LINK] = 'synthetic link'
        if args[:3] == ['systemctl', 'disable', '--now']:
            self.state['units'].pop(s.base.LINK, None)
        if args in (['systemctl', 'show', s.TIMER, '--property=ActiveState', '--value'],
                    ['systemctl', 'show', s.SERVICE, '--property=ActiveState', '--value']):
            return b'inactive\n'
        return b''

    def compare(self, before, after, hashes, activate):
        self.assertEqual(before['configuration'], after['configuration'])
        self.assertEqual(before['processes'], after['processes'])
        self.assertEqual(hashes, self.hashes)

    def payload(self, action):
        return {'action': action, 'hashes': self.hashes, 'commit': 'a' * 40,
                'baseline': copy.deepcopy(self.state)}

    def test_scope_never_selects_existing_application_or_backup_units(self):
        self.assertEqual(s.base.UNITS, ('quillmd-fresh-offsite.service', 'quillmd-fresh-offsite.timer'))
        self.assertNotIn('quillmd-fresh-backup.service', s.base.UNITS)
        self.assertEqual(s.base.DECLARATION, s.DECLARATION)

    def test_install_exclusive_files_and_only_reload_systemd(self):
        result = s.root_action(self.payload('install'))
        self.assertTrue(result['success'])
        self.assertEqual(self.calls, [['systemctl', 'daemon-reload']])
        for name in s.base.UNITS:
            p = s.base.SYSTEMD / name
            self.assertEqual(p.read_bytes(), (s.base.APP / 'deploy' / name).read_bytes())
            self.assertEqual(p.stat().st_mode & 0o777, 0o644)
        # Existing bytes are never truncated even if preflight has been defeated.
        before = (s.base.SYSTEMD / s.SERVICE).read_bytes()
        self.assertFalse(s.root_action(self.payload('install'))['success'])
        self.assertEqual((s.base.SYSTEMD / s.SERVICE).read_bytes(), before)

    def test_activation_starts_monitor_only_and_enables_its_timer(self):
        self.assertTrue(s.root_action(self.payload('activate'))['success'])
        starts = [a for a in self.calls if a[:2] == ['systemctl', 'start']]
        self.assertEqual(starts, [['systemctl', 'start', s.SERVICE], ['systemctl', 'start', s.TIMER]])

    def test_failed_monitor_check_disables_only_new_timer(self):
        self.fail_start = True
        result = s.root_action(self.payload('activate'))
        self.assertFalse(result['success'])
        self.assertTrue(result['timer_disabled'])
        self.assertNotIn(['systemctl', 'enable', s.TIMER], self.calls)
        self.assertIn(['systemctl', 'disable', '--now', s.TIMER], self.calls)
        self.assertIn(['systemctl', 'stop', s.SERVICE], self.calls)

    def test_adopt_does_not_write_units_reload_or_start_services(self):
        result = s.root_action(self.payload('adopt'))
        self.assertTrue(result['success'])
        self.assertFalse(result['unit_files_changed'])
        self.assertEqual(self.calls, [['systemctl', 'show', s.TIMER, '--property=ActiveState', '--value']])

    def test_expiry_before_next_run_refuses_before_provider_work(self):
        self.coverage.side_effect = RuntimeError('Policy expires before next run')
        result = s.root_action(self.payload('activate'))
        self.assertFalse(result['success'])
        self.assertNotIn(['systemctl', 'start', s.SERVICE], self.calls)
        self.assertNotIn(['systemctl', 'enable', s.TIMER], self.calls)

    def test_post_enable_schedule_mismatch_disables_timer_and_retains_run(self):
        self.coverage.side_effect = [{}, {}, RuntimeError('Unexpected next run')]
        result = s.root_action(self.payload('activate'))
        self.assertFalse(result['success'])
        self.assertTrue(result['timer_disabled'])
        self.assertIn('controlled_run', result)
        self.assertIn(['systemctl', 'enable', s.TIMER], self.calls)

    def test_disable_retains_unit_files_and_other_sessions(self):
        self.state['units'][s.base.LINK] = 'synthetic link'
        before = copy.deepcopy(self.state)
        result = s.root_action(self.payload('disable'))
        self.assertTrue(result['success'])
        self.assertEqual(before['processes'], self.state['processes'])
        self.assertEqual(self.calls[0], ['systemctl', 'disable', '--now', s.TIMER])

    def test_missing_operating_envelope_refuses_before_service_or_enable(self):
        with patch.object(s, 'eligibility', side_effect=RuntimeError('policy_missing')):
            result = s.root_action(self.payload('activate'))
        self.assertFalse(result['success'])
        self.assertNotIn(['systemctl', 'start', s.SERVICE], self.calls)
        self.assertNotIn(['systemctl', 'enable', s.TIMER], self.calls)

    def test_incomplete_service_evidence_cannot_enable_timer(self):
        with patch.object(s, 'verified_attempt', side_effect=RuntimeError('incomplete')):
            result = s.root_action(self.payload('activate'))
        self.assertFalse(result['success'])
        self.assertNotIn(['systemctl', 'enable', s.TIMER], self.calls)

    def test_source_drift_refuses_before_host_action(self):
        (self.root / s.INSTALLER).write_text('unreviewed')
        with self.assertRaisesRegex(RuntimeError, 'source drift'):
            s.root_action(self.payload('install'))
        self.assertEqual(self.calls, [])

    def test_baseline_drift_refuses_before_host_action(self):
        payload = self.payload('activate')
        self.state['processes']['doctor'] = 'changed'
        with self.assertRaisesRegex(RuntimeError, 'Host changed'):
            s.root_action(payload)
        self.assertEqual(self.calls, [])


class ControlledReadbackEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / '20260920T190000Z-11223344.json'
        common = {'run_id': '20260920T185000Z-aabbccdd', 'manifest_cipher_sha256': 'a' * 64,
                  'object_count': 44, 'cipher_bytes': 14000000}
        self.record = {'state': 'complete', 'reason_code': None, 'provider_calls_permitted': True,
                       'started_at': '2026-09-20T19:00:00+00:00', 'finished_at': '2026-09-20T19:00:40+00:00',
                       'result': {**common, 'authenticated': True, 'ciphertext_sha256_verified': True},
                       'last_remote_complete': {**common, 'completed_at': '2026-09-20T19:00:30+00:00'},
                       'last_verified_readback': {**common, 'verified_at': '2026-09-20T19:00:31+00:00'}}
        p = patch.object(s.base, 'MONITOR', self.root); p.start(); self.addCleanup(p.stop)
        p = patch.object(s.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=os.getuid()))
        p.start(); self.addCleanup(p.stop)

    def verify(self, record):
        self.path.write_text(json.dumps(record)); self.path.chmod(0o600)
        return s.verified_attempt(set())

    def test_current_authenticated_controlled_readback_is_accepted(self):
        self.assertEqual(self.verify(self.record)['record'], self.record)

    def test_noop_with_copied_historical_hashes_cannot_activate(self):
        self.record.update(provider_calls_permitted=False, result={'no_new_local_backup': True, 'provider_calls': 0})
        with self.assertRaises(RuntimeError):
            self.verify(self.record)

    def test_matching_hash_without_actual_authentication_cannot_activate(self):
        for field in ['authenticated', 'ciphertext_sha256_verified']:
            record = copy.deepcopy(self.record); record['result'][field] = False
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                self.verify(record)

    def test_mismatched_readback_identity_cannot_activate(self):
        for field, value in [('run_id', '20260920T180000Z-deadbeef'), ('manifest_cipher_sha256', 'b' * 64),
                             ('object_count', 43), ('cipher_bytes', 13999999)]:
            record = copy.deepcopy(self.record); record['last_verified_readback'][field] = value
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                self.verify(record)

    def test_historical_or_future_readback_timestamp_cannot_activate(self):
        for timestamp in ['2026-09-20T17:11:45+00:00', '2026-09-20T20:00:00+00:00', '2026-09-20T19:00:31']:
            record = copy.deepcopy(self.record); record['last_verified_readback']['verified_at'] = timestamp
            with self.subTest(timestamp=timestamp), self.assertRaises(RuntimeError):
                self.verify(record)

    def test_prior_attempt_is_not_a_new_controlled_run(self):
        self.verify(self.record)
        with self.assertRaises(RuntimeError):
            s.verified_attempt({self.path})


class DisableWithoutProviderConfigurationTests(unittest.TestCase):
    def test_disable_reaches_owned_root_action_without_b2_config_or_policy(self):
        previous_umask = os.umask(0o022)
        self.addCleanup(os.umask, previous_umask)
        revision = 'a' * 40
        hashes = {'synthetic': 'reviewed'}
        result = SimpleNamespace(returncode=0, stdout=json.dumps({'success': True}).encode())
        written = []
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sys, 'argv', ['installer', '--expected-commit', revision,
                                                          '--action', 'disable', '--execute']))
            # Preserve module globals changed by scope() across the entire test.
            saved = dict(vars(s.base)); self.addCleanup(lambda: vars(s.base).update(saved))
            stack.enter_context(patch.object(s.os, 'getuid', return_value=1000))
            stack.enter_context(patch.object(s.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=1000)))
            stack.enter_context(patch.object(s.base, 'reviewed_source', return_value=hashes))
            stack.enter_context(patch.object(s.base, 'baseline', return_value={'units': {}}))
            stack.enter_context(patch.object(s, 'unchanged_backups', return_value={}))
            stack.enter_context(patch.object(s.base, 'require_installed'))
            stack.enter_context(patch.object(s.base, 'read_private', return_value={
                'success': True, 'commit': revision, 'hashes': hashes}))
            stack.enter_context(patch.object(s, 'installation_receipt', return_value={'commit': revision}))
            stack.enter_context(patch.object(s.base, 'private_directory'))
            stack.enter_context(patch.object(s.base, 'write_private', side_effect=lambda path, value: written.append(value)))
            stack.enter_context(patch.object(s.base, 'metadata', side_effect=AssertionError('B2 metadata must not be read')))
            stack.enter_context(patch.object(s, 'configuration', side_effect=AssertionError('B2 configuration must not be read')))
            stack.enter_context(patch.object(s, 'eligibility', side_effect=AssertionError('Policy must not be read')))
            runner = stack.enter_context(patch.object(s.subprocess, 'run', return_value=result))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(s.main(), 0)
            self.assertTrue(runner.called)
        final = written[-1]
        self.assertTrue(final['success'])
        self.assertFalse(final['b2_configuration_checked'])
        self.assertIsNone(final['b2_configuration_unchanged'])


class NextRunCoverageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'deploy').mkdir()
        self.calendar = self.root / 'deploy' / s.TIMER
        self.calendar.write_text('OnCalendar=*-*-* 05:00:00 UTC\nRandomizedDelaySec=0\nPersistent=true\n')
        p = patch.object(s.base, 'APP', self.root); p.start(); self.addCleanup(p.stop)
        self.at = datetime(2026, 9, 20, 22, tzinfo=timezone.utc)
        self.limits = {'policy_expires_at': '2026-09-21T20:16:35.867379+00:00'}

    def test_next_daily_run_and_entire_runtime_are_inside_evidence(self):
        result = s.first_run_coverage(self.limits, at=self.at)
        self.assertEqual(result['next_run_at'], '2026-09-21T05:00:00+00:00')
        self.assertEqual(result['latest_completion_at'], '2026-09-21T05:16:00+00:00')
        self.assertFalse(result['actual_systemd_schedule'])

    def test_expiry_before_runtime_end_and_unknown_timezone_are_refused(self):
        for expiry in ['2026-09-21T04:59:59+00:00', '2026-09-21T05:15:59+00:00',
                       '2026-09-21T05:16:00+00:00', '2026-09-21T20:16:00']:
            with self.subTest(expiry=expiry), self.assertRaises(RuntimeError):
                s.first_run_coverage({'policy_expires_at': expiry}, at=self.at)
        with self.assertRaises(RuntimeError):
            s.first_run_coverage(self.limits, at=self.at.replace(tzinfo=None))

    def test_actual_systemd_schedule_must_match_next_utc_calendar(self):
        with patch.object(s.base, 'command', return_value=b'Mon 2026-09-21 05:00:00 UTC\n') as command:
            self.assertTrue(s.first_run_coverage(self.limits, actual=True, at=self.at)['actual_systemd_schedule'])
            command.return_value = b'Tue 2026-09-22 05:00:00 UTC\n'
            with self.assertRaises(RuntimeError):
                s.first_run_coverage(self.limits, actual=True, at=self.at)
        self.calendar.write_text('OnCalendar=*-*-* 05:00:00\nRandomizedDelaySec=0\nPersistent=true\n')
        with self.assertRaises(RuntimeError):
            s.first_run_coverage(self.limits, at=self.at)


class AdoptionReceiptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        p = patch.object(s.base, 'MONITOR', self.root); p.start(); self.addCleanup(p.stop)
        self.hashes = {'rebuild/deploy/' + name: 'a' * 64 for name in (s.SERVICE, s.TIMER)}
        self.old = dict(success=True, commit='b' * 40, hashes=dict(self.hashes, old_source='original'))
        s.base.write_private(self.root / 'installation.json', self.old)
        self.original = (self.root / 'installation.json').read_bytes()

    def test_adoption_changes_source_revision_only_and_keeps_original(self):
        result = s.installation_receipt('c' * 40, dict(self.hashes, source='new'), adopt=True)
        self.assertEqual(result['commit'], 'b' * 40)
        self.assertEqual((self.root / 'installation.json').read_bytes(), self.original)
        with self.assertRaises(RuntimeError):
            s.installation_receipt('c' * 40, self.hashes)
        s.base.write_private(s.adoption_receipt('c' * 40), dict(success=True, commit='c' * 40, hashes=self.hashes))
        self.assertEqual(s.installation_receipt('c' * 40, self.hashes)['commit'], 'c' * 40)

    def test_changed_effective_units_cannot_be_adopted(self):
        altered = dict(self.hashes)
        altered['rebuild/deploy/' + s.SERVICE] = 'd' * 64
        with self.assertRaises(RuntimeError):
            s.installation_receipt('c' * 40, altered, adopt=True)


class EffectiveServiceIdentityTests(unittest.TestCase):
    def test_environment_file_or_wrong_user_refuses_without_echoing_environment(self):
        properties = {'User': 'claude', 'Group': 'claude', 'WorkingDirectory': str(s.base.APP),
                      'KillMode': 'control-group', 'NoNewPrivileges': 'yes', 'ProtectSystem': 'strict',
                      'PrivateTmp': 'yes', 'MemoryMax': '1073741824', 'MemorySwapMax': '0',
                      'TimeoutStartUSec': '16min', 'Environment': '', 'ReadWritePaths': str(s.base.MONITOR)}
        def output(value):
            return '\n'.join(key + '=' + item for key, item in value.items()).encode()
        with patch.object(s.base, 'command', return_value=output(properties)) as command:
            self.assertEqual(s.service_identity()['EnvironmentFiles'], '')
            for field, value in [('User', 'root'), ('EnvironmentFiles', '/tmp/unreviewed'),
                                 ('Environment', 'TOKEN=private-canary')]:
                with self.subTest(field=field):
                    command.return_value = output(dict(properties, **{field: value}))
                    with self.assertRaises(RuntimeError) as failure:
                        s.service_identity()
                    self.assertNotIn('private-canary', str(failure.exception))


if __name__ == '__main__':
    unittest.main()
