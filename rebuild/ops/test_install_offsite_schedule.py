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
        self.assertEqual(result['latest_completion_at'], '2026-09-21T05:18:30+00:00')
        self.assertEqual(result['bounded_window_seconds'], 1110)
        self.assertFalse(result['actual_systemd_schedule'])

    def test_expiry_before_runtime_end_and_unknown_timezone_are_refused(self):
        for expiry in ['2026-09-21T04:59:59+00:00', '2026-09-21T05:15:59+00:00',
                       '2026-09-21T05:16:00+00:00', '2026-09-21T05:18:30+00:00', '2026-09-21T20:16:00']:
            with self.subTest(expiry=expiry), self.assertRaises(RuntimeError):
                s.first_run_coverage({'policy_expires_at': expiry}, at=self.at)
        with self.assertRaises(RuntimeError):
            s.first_run_coverage(self.limits, at=self.at.replace(tzinfo=None))

    def test_actual_systemd_schedule_must_match_next_utc_calendar(self):
        def output(args, **kwargs):
            return (b'AccuracyUSec=1min\nRandomizedDelayUSec=0\n' if '--property=AccuracyUSec,RandomizedDelayUSec' in args
                    else b'Mon 2026-09-21 05:00:00 UTC\n')
        with patch.object(s.base, 'command', side_effect=output) as command:
            self.assertTrue(s.first_run_coverage(self.limits, actual=True, at=self.at)['actual_systemd_schedule'])
            command.side_effect = None
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
                      'TimeoutStartUSec': '16min', 'TimeoutStopUSec': '1min 30s',
                      'Environment': '', 'ReadWritePaths': str(s.base.MONITOR)}
        def output(value):
            return '\n'.join(key + '=' + item for key, item in value.items()).encode()
        with patch.object(s.base, 'command', return_value=output(properties)) as command:
            self.assertEqual(s.service_identity()['EnvironmentFiles'], '')
            for field, value in [('User', 'root'), ('EnvironmentFiles', '/tmp/unreviewed'),
                                 ('Environment', 'TOKEN=private-canary'), ('TimeoutStopUSec', 'infinity')]:
                with self.subTest(field=field):
                    command.return_value = output(dict(properties, **{field: value}))
                    with self.assertRaises(RuntimeError) as failure:
                        s.service_identity()
                    self.assertNotIn('private-canary', str(failure.exception))


class ActiveInstallationRefreshTests(unittest.TestCase):
    """Refresh never turns an active schedule off or repeats provider qualification."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        saved = dict(vars(s.base)); self.addCleanup(lambda: vars(s.base).update(saved))
        s.base.ROOT, s.base.APP, s.base.SYSTEMD = self.root, self.root / 'rebuild', self.root / 'systemd'
        s.scope()
        for folder in (s.base.MONITOR, s.base.EVIDENCE, s.base.APP / '.runtime/backup-secrets'):
            folder.mkdir(parents=True, mode=0o700)
        self.patch(s, 'CONFIG', s.base.APP / '.runtime/backup-secrets/b2-offsite.json')
        self.patch(s.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=os.getuid()))
        clock = self.patch(s, 'datetime', wraps=datetime)
        clock.now.return_value = datetime(2026, 9, 20, 22, tzinfo=timezone.utc)
        for relative in s.base.SOURCES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('reviewed fixture ' + relative)
        (s.base.APP / 'deploy' / s.TIMER).write_text(
            'OnCalendar=*-*-* 05:00:00 UTC\nRandomizedDelaySec=0\nPersistent=true\n')
        self.hashes = {relative: s.base.digest(self.root / relative) for relative in s.base.SOURCES}
        self.baseline = {'units': {s.base.LINK: {'uid': 0, 'gid': 0, 'mode': 0o777,
                           'link': str(s.base.SYSTEMD / s.TIMER)}},
                         'configuration': {'working_keys': 'unchanged'}, 'processes': {'app': 'same'}}
        self.payload = dict(action='refresh', hashes=self.hashes, baseline=copy.deepcopy(self.baseline), commit='a'*40)
        for name in ('budget', 'status', 'active', '20260920T212054Z-9fb5d226'):
            s.base.write_private(s.base.MONITOR / (name + '.json'), {'fixture': name})
        for path in (s.CONFIG, s.CONFIG.parent / 'offsite-policy.json', s.CONFIG.parent / 'offsite-allocation.json'):
            s.base.write_private(path, {'fixture': path.name})
        s.base.write_private(s.base.MONITOR / 'execution.lock', {})
        s.base.write_private(s.base.MONITOR / 'installation.json', dict(
            success=True, commit='b'*40, hashes=self.hashes))
        self.original_receipt = (s.base.MONITOR / 'installation.json').read_bytes()
        identity = dict(run_id='20260920T193915Z-9cc67364', manifest_cipher_sha256='d'*64,
                        object_count=44, cipher_bytes=14_423_108)
        self.record = dict(version=1, attempt='20260920T212054Z-9fb5d226', state='complete', reason_code=None,
            provider_calls_permitted=True, started_at='2026-09-20T21:20:54+00:00',
            finished_at='2026-09-20T21:21:24+00:00',
            result=dict(identity, authenticated=True, ciphertext_sha256_verified=True),
            last_remote_complete=dict(identity, completed_at='2026-09-20T21:21:24+00:00'),
            last_verified_readback=dict(identity, verified_at='2026-09-20T21:21:24+00:00'))
        self.attempt_path = s.base.MONITOR / (self.record['attempt'] + '.json')
        self.attempt_path.write_bytes(json.dumps(self.record).encode())
        (s.base.MONITOR / 'status.json').write_bytes(self.attempt_path.read_bytes())
        (s.base.MONITOR / 'active.json').write_text(json.dumps(dict(complete=True, pending=None,
            run_id=identity['run_id'], manifest_cipher_sha256=identity['manifest_cipher_sha256'])))
        self.qualification = dict(action='resume', success=True, commit='b'*40,
            baseline_preserved=True, b2_configuration_unchanged=True, backup_records_unchanged=True,
            shared_journal_unchanged=True, first_run_coverage_actual={'actual_systemd_schedule': True},
            hashes=self.hashes, controlled_run={'path': str(self.attempt_path),
                'sha256': s.base.digest(self.attempt_path), 'record': self.record})
        self.qualification_path = s.base.EVIDENCE / s.QUALIFIED_RESUME
        s.base.write_private(self.qualification_path, self.qualification)
        self.patch(s, 'QUALIFIED_RESUME_SHA256', s.base.digest(self.qualification_path))
        self.limits = {'policy_expires_at': '2026-09-21T20:16:35.867379+00:00'}
        self.calls = []
        self.patch(s.base, 'command', side_effect=self.command)
        self.patch(s, 'eligibility', return_value=self.limits)
        self.identity = self.patch(s, 'service_identity', return_value={'User': 'claude'})
        self.patch(s.base, 'baseline', side_effect=lambda: copy.deepcopy(self.baseline))
        self.patch(s.base, 'require_installed')
        self.patch(s.base, 'compare_baseline', side_effect=lambda before, after, _hashes, _active: self.assertEqual(before, after))
        self.patch(s.os, 'getuid', return_value=0)

    def patch(self, target, name, value=None, **kwargs):
        item = patch.object(target, name, value, **kwargs) if value is not None else patch.object(target, name, **kwargs)
        result = item.start(); self.addCleanup(item.stop); return result

    def command(self, args, **kwargs):
        self.calls.append(args)
        if args == ['systemctl', 'is-active', s.TIMER]: return b'active\n'
        if args == ['systemctl', 'is-enabled', s.TIMER]: return b'enabled\n'
        if '--property=ActiveState,Result,ExecMainStatus' in args:
            return b'ActiveState=inactive\nResult=success\nExecMainStatus=0\n'
        if '--property=NextElapseUSecRealtime' in args: return b'Mon 2026-09-21 05:00:00 UTC\n'
        if '--property=AccuracyUSec,RandomizedDelayUSec' in args:
            return b'AccuracyUSec=1min\nRandomizedDelayUSec=0\n'
        raise AssertionError('Unexpected command: ' + repr(args))

    def test_refresh_checks_active_schedule_and_preserves_every_existing_journal_byte(self):
        before = {p.name: p.read_bytes() for p in s.base.MONITOR.iterdir()}
        result = s.root_action(self.payload)
        self.assertTrue(result['success'])
        self.assertEqual(result['provider_calls'], 0)
        self.assertEqual(result['timer_actions'], 0)
        self.assertFalse(result['new_service_start'])
        self.assertTrue(result['shared_journal_unchanged'])
        self.assertEqual(result['retained_activation_qualification']['receipt_sha256'], s.QUALIFIED_RESUME_SHA256)
        self.assertEqual(result['first_run_coverage_actual']['bounded_window_seconds'], 1110)
        self.assertEqual({p.name: p.read_bytes() for p in s.base.MONITOR.iterdir()}, before)
        self.assertEqual((s.base.MONITOR / 'installation.json').read_bytes(), self.original_receipt)
        self.assertTrue(all(command[1] in {'show', 'is-active', 'is-enabled'} or command[0] == '/usr/bin/env'
                            for command in self.calls))

    def test_manually_enabled_but_unqualified_timer_is_refused(self):
        self.qualification_path.unlink()
        result = s.root_action(self.payload)
        self.assertFalse(result['success'])
        self.assertEqual(self.calls, [])

    def test_changed_or_unauthenticated_controlled_attempt_cannot_refresh(self):
        self.record['result']['authenticated'] = False
        self.attempt_path.write_text(json.dumps(self.record))
        self.assertFalse(s.root_action(self.payload)['success'])
        self.assertEqual(self.calls, [])

    def test_empty_or_partial_current_status_cannot_reuse_an_old_qualification(self):
        for changes in ({}, {'state': 'complete'}, dict(self.record, last_verified_readback=None)):
            with self.subTest(changes=list(changes)):
                (s.base.MONITOR / 'status.json').write_text(json.dumps(changes))
                self.assertFalse(s.root_action(self.payload)['success'])
        self.assertEqual(self.calls, [])

    def test_later_authenticated_cycle_is_accepted_without_replacing_original_qualification(self):
        newer = copy.deepcopy(self.record)
        newer.update(attempt='20260920T214001Z-12345678', started_at='2026-09-20T21:40:01+00:00',
                     finished_at='2026-09-20T21:40:30+00:00')
        for name in ('result', 'last_remote_complete', 'last_verified_readback'):
            newer[name].update(run_id='20260920T213900Z-12345678', manifest_cipher_sha256='e'*64)
        newer['last_remote_complete']['completed_at'] = '2026-09-20T21:40:30+00:00'
        newer['last_verified_readback']['verified_at'] = '2026-09-20T21:40:30+00:00'
        path = s.base.MONITOR / (newer['attempt'] + '.json')
        s.base.write_private(path, newer)
        (s.base.MONITOR / 'status.json').write_bytes(path.read_bytes())
        (s.base.MONITOR / 'active.json').write_text(json.dumps(dict(complete=True, pending=None,
            run_id=newer['result']['run_id'], manifest_cipher_sha256=newer['result']['manifest_cipher_sha256'])))
        result = s.root_action(self.payload)
        self.assertTrue(result['success'])
        proof = result['retained_activation_qualification']
        self.assertEqual(proof['controlled_attempt_path'], str(self.attempt_path))
        self.assertEqual(proof['current_readback_attempt_path'], str(path))

    def test_later_failure_can_adopt_repair_source_without_erasing_or_relabelling_execution(self):
        failed = copy.deepcopy(self.record)
        failed.update(attempt='20260920T214001Z-12345678', started_at='2026-09-20T21:40:01+00:00',
                      finished_at='2026-09-20T21:40:30+00:00', state='failed', reason_code='cleanup_failed')
        failed.pop('result')
        path = s.base.MONITOR / (failed['attempt'] + '.json')
        s.base.write_private(path, failed)
        (s.base.MONITOR / 'status.json').write_bytes(path.read_bytes())
        (s.base.MONITOR / 'active.json').write_text('{"complete":false,"pending":{"fixture":"uncertain put"}}')
        def stopped(args, **kwargs):
            if '--property=ActiveState,Result,ExecMainStatus' in args:
                return b'ActiveState=failed\nResult=exit-code\nExecMainStatus=1\n'
            return self.command(args, **kwargs)
        before = {p.name: p.read_bytes() for p in s.base.MONITOR.iterdir()}
        with patch.object(s.base, 'command', side_effect=stopped):
            result = s.root_action(self.payload)
        self.assertTrue(result['success'])
        self.assertFalse(result['execution_verification_performed'])
        self.assertEqual(result['latest_service_state']['Result'], 'exit-code')
        proof = result['retained_activation_qualification']
        self.assertEqual(proof['latest_execution']['reason_code'], 'cleanup_failed')
        self.assertFalse(proof['current_publication_complete'])
        self.assertEqual(proof['current_readback_attempt_path'], str(self.attempt_path))
        self.assertEqual({p.name: p.read_bytes() for p in s.base.MONITOR.iterdir()}, before)

    def test_running_service_cannot_be_refreshed_even_with_prior_qualification(self):
        def running(args, **kwargs):
            if '--property=ActiveState,Result,ExecMainStatus' in args:
                return b'ActiveState=activating\nResult=success\nExecMainStatus=0\n'
            return self.command(args, **kwargs)
        with patch.object(s.base, 'command', side_effect=running):
            self.assertFalse(s.root_action(self.payload)['success'])

    def test_expiry_or_unit_receipt_drift_refuses_without_timer_or_service_action(self):
        self.limits['policy_expires_at'] = '2026-09-21T05:17:00+00:00'
        self.assertFalse(s.root_action(self.payload)['success'])
        self.limits['policy_expires_at'] = '2026-09-21T20:16:35+00:00'
        path = s.base.MONITOR / 'installation.json'
        value = json.loads(path.read_bytes())
        value['hashes']['rebuild/deploy/' + s.TIMER] = 'c' * 64
        path.write_text(json.dumps(value))
        self.assertFalse(s.root_action(self.payload)['success'])
        self.assertFalse(any(command[1] in {'start', 'stop', 'enable', 'disable', 'daemon-reload'} for command in self.calls))

    def test_competing_consumer_refuses_without_any_systemd_call(self):
        descriptor = os.open(s.base.MONITOR / 'execution.lock', os.O_RDONLY)
        try:
            s.fcntl.flock(descriptor, s.fcntl.LOCK_EX | s.fcntl.LOCK_NB)
            self.assertFalse(s.root_action(self.payload)['success'])
        finally:
            os.close(descriptor)
        self.assertEqual(self.calls, [])

    def test_concurrent_policy_or_ledger_change_refuses_without_claiming_unchanged(self):
        def change():
            (s.base.MONITOR / 'budget.json').write_text('{"fixture":"concurrent reservation"}')
            return {'User': 'claude'}
        self.identity.side_effect = change
        result = s.root_action(self.payload)
        self.assertFalse(result['success'])
        self.assertNotIn('shared_journal_unchanged', result)

    def test_replaced_lock_is_not_accepted_as_exclusion(self):
        def change():
            replacement = s.base.MONITOR / 'replacement.lock'
            s.base.write_private(replacement, {})
            replacement.replace(s.base.MONITOR / 'execution.lock')
            return {'User': 'claude'}
        self.identity.side_effect = change
        self.assertFalse(s.root_action(self.payload)['success'])


class RetainedQualificationResumeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        saved = dict(vars(s.base)); self.addCleanup(lambda: vars(s.base).update(saved))
        s.base.ROOT = self.root
        s.base.APP = self.root / 'rebuild'
        s.scope()
        for folder in (s.base.MONITOR, s.base.EVIDENCE, s.base.APP / '.runtime/backup-secrets'):
            folder.mkdir(parents=True, mode=0o700)
        self.patch(s, 'CONFIG', s.base.APP / '.runtime/backup-secrets/b2-offsite.json')
        self.patch(s.pwd, 'getpwnam', SimpleNamespace(pw_uid=os.getuid()), returns=True)
        self.clock = self.patch(s, 'datetime', wraps=datetime)
        self.clock.now.return_value = datetime(2026, 9, 20, 22, tzinfo=timezone.utc)
        self.hashes = {}
        for relative in s.base.SOURCES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('reviewed fixture ' + relative)
        (s.base.APP / 'deploy' / s.TIMER).write_text(
            'OnCalendar=*-*-* 05:00:00 UTC\nRandomizedDelaySec=0\nPersistent=true\n')
        self.hashes = {relative: s.base.digest(self.root / relative) for relative in s.base.SOURCES}
        self.baseline = {'units': {}, 'configuration': {'synthetic': 'unchanged'}, 'processes': {'app': 'same'}}
        self.payload = dict(action='resume', hashes=self.hashes, baseline=copy.deepcopy(self.baseline), commit='a'*40)
        old = dict(self.hashes, **{s.INSTALLER: 'b'*64, s.DECLARATION: 'c'*64})
        self.before = dict(action='activate', hashes=old, baseline=copy.deepcopy(self.baseline), commit=s.RESUME_COMMIT)
        self.limits = {'policy_expires_at': '2026-09-21T20:16:35.867379+00:00', 'scope_ceiling_bytes': 1_000_000_000,
                       'daily_request_budget': 500, 'daily_download_budget_bytes': 100_000_000}
        identity = dict(run_id='20260920T193915Z-9cc67364', manifest_cipher_sha256='d'*64,
                        object_count=44, cipher_bytes=14_423_108)
        self.record = dict(version=1, attempt='20260920T212054Z-9fb5d226', state='complete', reason_code=None,
                           provider_calls_permitted=True, started_at='2026-09-20T21:20:54+00:00',
                           finished_at='2026-09-20T21:21:24+00:00',
                           result=dict(identity, authenticated=True, ciphertext_sha256_verified=True),
                           last_remote_complete=dict(identity, completed_at='2026-09-20T21:21:24+00:00'),
                           last_verified_readback=dict(identity, verified_at='2026-09-20T21:21:24+00:00'))
        self.attempt = s.base.MONITOR / (self.record['attempt'] + '.json')
        self.write(self.attempt, self.record)
        self.controlled = dict(path=str(self.attempt), sha256=s.base.digest(self.attempt), record=self.record)
        self.failure = dict(action='activate', commit=s.RESUME_COMMIT, hashes=old, success=False, timer_disabled=True,
                            backup_records_unchanged=True, b2_configuration_unchanged=True,
                            finished_at='2026-09-20T21:22:00+00:00', controlled_run=self.controlled,
                            eligibility=self.limits, eligibility_after_run=self.limits,
                            first_run_coverage_before_enable=s.first_run_coverage(self.limits))
        self.policy = {'observed_at': '2026-09-20T20:16:35.867379+00:00', 'valid_until': self.limits['policy_expires_at']}
        self.budget = {'version': 2, 'day': '2026-09-20', 'requests': 419, 'download_bytes': 96_115_248}
        active = dict(version=1, complete=True, pending=None, **{key: identity[key] for key in ('run_id','manifest_cipher_sha256')})
        files = {'b2_configuration': (s.CONFIG, {'fixture': True}),
                 'policy': (s.CONFIG.parent/'offsite-policy.json', self.policy),
                 'allocation': (s.CONFIG.parent/'offsite-allocation.json', {'fixture': True}),
                 'status': (s.base.MONITOR/'status.json', self.record),
                 'active': (s.base.MONITOR/'active.json', active),
                 'budget': (s.base.MONITOR/'budget.json', self.budget)}
        self.context = dict(at='2026-09-20T21:28:24+00:00', prior_commit=s.RESUME_COMMIT,
                            original_baseline_identical_after_failure=True,
                            inspection_does_not_retroactively_measure_pre_failure_config=True, provider_calls=0,
                            controlled_attempt=str(self.attempt), controlled_attempt_sha256=self.controlled['sha256'],
                            attempt_files={self.attempt.name:self.controlled['sha256']}, budget=self.budget, protected_files={})
        for name, (path, value) in files.items():
            self.write(path, value)
            metadata = s.base.metadata(path)
            self.context['protected_files'][name] = dict(path=str(path), sha256=metadata.pop('sha256'), metadata=metadata)
        self.write(s.base.MONITOR / 'execution.lock', {})
        self.reseal()
        self.calls = []
        self.patch(s.base, 'command', side_effect=self.command)
        self.patch(s, 'eligibility', self.limits, returns=True)
        self.patch(s, 'service_identity', {'User':'claude'}, returns=True)
        self.patch(s.base, 'baseline', side_effect=lambda: copy.deepcopy(self.baseline))
        self.patch(s.base, 'require_installed')
        self.patch(s.base, 'compare_baseline')

    def patch(self, target, name, value=None, *, returns=False, **kwargs):
        if returns:
            kwargs['return_value'] = value
            item = patch.object(target, name, **kwargs)
        elif value is not None:
            item = patch.object(target, name, value, **kwargs)
        else:
            item = patch.object(target, name, **kwargs)
        value = item.start(); self.addCleanup(item.stop)
        return value

    def write(self, path, value):
        path.write_text(json.dumps(value, sort_keys=True)); path.chmod(0o600)

    def reseal(self):
        self.write(s.base.EVIDENCE/s.RESUME_FAILURE, self.failure)
        self.write(s.base.EVIDENCE/s.RESUME_BASELINE, self.before)
        self.context['failed_report_sha256'] = s.base.digest(s.base.EVIDENCE/s.RESUME_FAILURE)
        self.context['before_payload_sha256'] = s.base.digest(s.base.EVIDENCE/s.RESUME_BASELINE)
        self.write(s.base.EVIDENCE/s.RESUME_CONTEXT, self.context)
        self.patch(s, 'RESUME_FAILURE_SHA256', self.context['failed_report_sha256'])
        self.patch(s, 'RESUME_BASELINE_SHA256', self.context['before_payload_sha256'])
        self.patch(s, 'RESUME_CONTEXT_SHA256', s.base.digest(s.base.EVIDENCE/s.RESUME_CONTEXT))

    def command(self, args, timeout=40):
        self.calls.append(args)
        if args == ['systemctl','show',s.SERVICE,'--property=ActiveState,Result,ExecMainStatus']:
            return b'ActiveState=inactive\nResult=success\nExecMainStatus=0\n'
        if '--property=NextElapseUSecRealtime' in args:
            return b'Mon 2026-09-21 05:00:00 UTC\n'
        if '--property=AccuracyUSec,RandomizedDelayUSec' in args:
            return b'AccuracyUSec=1min\nRandomizedDelayUSec=0\n'
        if args[:2] == ['systemctl','is-active']:return b'active\n'
        if args[:2] == ['systemctl','is-enabled']:return b'enabled\n'
        if '--property=ActiveState' in args:return b'inactive\n'
        if args[:2] == ['systemctl','enable']:self.baseline['units'][s.base.LINK]='enabled'
        if args[:3] == ['systemctl','disable','--now']:self.baseline['units'].pop(s.base.LINK,None)
        return b''

    def test_resume_starts_only_timer_with_readonly_lock_and_no_budget_or_proof_changes(self):
        original_open = s.os.open
        with patch.object(s.os,'open',wraps=original_open) as opened:
            result=s.resume_activation(self.payload,{})
        self.assertEqual(opened.call_args.args[1], s.os.O_RDONLY | s.os.O_NOFOLLOW)
        self.assertEqual([call for call in self.calls if call[:2]==['systemctl','start']], [['systemctl','start',s.TIMER]])
        self.assertFalse(result['new_service_start'])
        self.assertEqual(result['provider_calls'],0)
        self.assertEqual(json.loads((s.base.MONITOR/'budget.json').read_bytes()), self.budget)
        self.assertEqual(json.loads(self.attempt.read_bytes()), self.record)

    def test_missing_lazy_parser_import_does_not_affect_actual_next_run_comparison(self):
        import builtins
        original_import=builtins.__import__
        def guarded(name,*args,**kwargs):
            if name=='_strptime':raise ModuleNotFoundError('no _strptime in helper chroot')
            return original_import(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=guarded):
            self.assertTrue(s.first_run_coverage(self.limits,actual=True)['actual_systemd_schedule'])

    def test_state_budget_config_or_extra_attempt_drift_refuses_before_timer_mutation(self):
        for name in ('status','budget','active','policy','allocation','b2_configuration'):
            path=Path(self.context['protected_files'][name]['path']);raw=path.read_bytes()
            with self.subTest(name=name):
                path.write_bytes(raw+b' ')
                with self.assertRaises(RuntimeError):s.resume_activation(self.payload,{})
                self.assertFalse(self.calls)
                path.write_bytes(raw)
        self.write(s.base.MONITOR/'20260920T213000Z-aaaaaaaa.json',self.record)
        with self.assertRaises(RuntimeError):s.resume_activation(self.payload,{})
        self.assertFalse(self.calls)

    def test_source_or_original_host_baseline_drift_refuses(self):
        for target,key in ((self.payload['hashes'],'rebuild/ops/automatic_offsite.py'),
                           (self.payload['baseline']['processes'],'app')):
            original=target[key];target[key]='changed'
            with self.assertRaises(RuntimeError):s.resume_qualification(self.payload)
            target[key]=original
        self.assertFalse(self.calls)

    def test_noop_or_unauthenticated_retained_evidence_cannot_qualify_even_with_resealed_fixture(self):
        for field in ('authenticated','ciphertext_sha256_verified','no_new_local_backup'):
            original=copy.deepcopy(self.record)
            self.record['result'][field]=(field=='no_new_local_backup')
            self.write(self.attempt,self.record)
            with self.assertRaises(RuntimeError):s.verified_attempt(set())
            self.record.clear();self.record.update(original)
        self.assertFalse(self.calls)

    def test_failed_original_receipt_predicates_are_not_optional(self):
        self.failure['timer_disabled']=False;self.reseal()
        with self.assertRaises(RuntimeError):s.resume_qualification(self.payload)
        self.assertFalse(self.calls)

    def test_competing_lock_refuses_without_disabling_another_consumer(self):
        fd=s.os.open(s.base.MONITOR/'execution.lock',s.os.O_RDONLY)
        try:
            s.fcntl.flock(fd,s.fcntl.LOCK_EX|s.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):s.resume_activation(self.payload,{})
            self.assertFalse(self.calls)
        finally:s.os.close(fd)

    def test_post_enable_mismatch_disables_only_timer_preserving_readback(self):
        original=self.command
        def wrong(args,timeout=40):
            if '--property=NextElapseUSecRealtime' in args:return b'Tue 2026-09-22 05:00:00 UTC'
            return original(args,timeout)
        with patch.object(s.base,'command',side_effect=wrong):
            result={}
            with self.assertRaises(RuntimeError):s.resume_activation(self.payload,result)
        self.assertTrue(result['timer_disabled'])
        self.assertIn(['systemctl','disable','--now',s.TIMER],self.calls)
        self.assertNotIn(['systemctl','stop',s.SERVICE],self.calls)
        self.assertEqual(json.loads(self.attempt.read_bytes()),self.record)

    def test_replaced_lock_during_timer_enablement_refuses_and_contains_timer(self):
        original=self.command
        def replace_lock(args,timeout=40):
            if args == ['systemctl','enable',s.TIMER]:
                replacement=s.base.MONITOR/'fixture-replacement.lock'
                self.write(replacement,{})
                s.os.replace(replacement,s.base.MONITOR/'execution.lock')
            return original(args,timeout)
        result={}
        with patch.object(s.base,'command',side_effect=replace_lock), self.assertRaisesRegex(RuntimeError,'lock changed'):
            s.resume_activation(self.payload,result)
        self.assertTrue(result['timer_disabled'])
        self.assertNotIn(['systemctl','start',s.SERVICE],self.calls)
        self.assertNotIn(['systemctl','stop',s.SERVICE],self.calls)


if __name__ == '__main__':
    unittest.main()
