"""Installer boundary tests using files and fake systemd; no host or email acts."""
import copy
import contextlib
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
        self.assertEqual(self.calls[-2:], [['systemctl', 'disable', '--now', s.TIMER],
                                         ['systemctl', 'stop', s.SERVICE]])

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


if __name__ == '__main__':
    unittest.main()
