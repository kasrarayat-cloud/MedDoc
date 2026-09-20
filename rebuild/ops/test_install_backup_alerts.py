"""Installer boundary tests using files and fake systemd; no host or email acts."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from . import install_backup_alerts as s
except ImportError:
    import install_backup_alerts as s


class AlertInstallerTests(unittest.TestCase):
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
        self.assertEqual(s.base.UNITS, ('quillmd-fresh-backup-alerts.service', 'quillmd-fresh-backup-alerts.timer'))
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


if __name__ == '__main__':
    unittest.main()
