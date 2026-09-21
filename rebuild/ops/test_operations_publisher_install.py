"""Guards for the scoped operations-status publisher installation. No host or provider action."""
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ops import source_module

ROOT = Path(__file__).resolve().parents[2]
c = source_module.load('operations_publisher_install_tested', ROOT / 'rebuild/ops/install_operations_publisher.py')
c.scope()


class ScopeIsNarrow(unittest.TestCase):
    def test_only_the_two_new_units_are_in_scope(self):
        self.assertEqual(c.base.UNITS, (c.SERVICE, c.TIMER))
        self.assertEqual(c.base.LINK, 'timers.target.wants/' + c.TIMER)
        self.assertTrue(c.SERVICE.startswith('quillmd-fresh-operations-publisher'))
        for existing in ('quillmd-fresh-backup', 'quillmd-fresh-offsite', 'quillmd-fresh-doctor',
                         'quillmd-fresh-admin', 'quillmd-fresh-worker', 'quillmd-fresh-database'):
            self.assertNotIn(existing + '.service', c.base.UNITS)
            self.assertNotIn(existing + '.timer', c.base.UNITS)

    def test_the_reviewed_source_set_names_every_file_the_act_depends_on(self):
        for required in (c.INSTALLER, c.DECLARATION, c.COMMAND, 'rebuild/ops/managed_helper.py',
                         'rebuild/ops/backup_alerts.py', 'rebuild/deploy/' + c.SERVICE,
                         'rebuild/deploy/' + c.TIMER):
            self.assertIn(required, c.base.SOURCES)
        for path in c.base.SOURCES:
            self.assertTrue((ROOT / path).is_file(), path)

    def test_the_units_run_as_the_operations_identity_and_grant_the_web_process_nothing(self):
        service = (ROOT / 'rebuild/deploy' / c.SERVICE).read_text()
        self.assertIn('User=claude', service)
        self.assertIn('Group=claude', service)
        self.assertNotIn('quillmd-app', service)
        self.assertIn('Type=oneshot', service)
        self.assertIn('NoNewPrivileges=true', service)
        self.assertIn('ProtectSystem=strict', service)
        self.assertIn('UMask=0077', service)
        self.assertIn('publish_operations_status', service)
        for forbidden in ('chmod', 'chown', 'setuid', 'CAP_', 'PrivateDevices=no', 'User=root'):
            self.assertNotIn(forbidden, service)
        # The admin surface's masking of the runtime tree is NOT relaxed by this act.
        admin = (ROOT / 'rebuild/deploy/quillmd-fresh-admin.service').read_text()
        self.assertIn('/opt/meddoc-pro/rebuild/.runtime', admin.split('InaccessiblePaths=', 1)[1].splitlines()[0])

    def test_the_timer_repeats_at_the_existing_cadence(self):
        timer = (ROOT / 'rebuild/deploy' / c.TIMER).read_text()
        self.assertIn('OnUnitActiveSec=5min', timer)
        self.assertIn('Unit=' + c.SERVICE, timer)
        self.assertIn('WantedBy=timers.target', timer)


class PublicationIsProvedNotAssumed(unittest.TestCase):
    def row(self, **over):
        now = datetime.now(timezone.utc)
        base = {'key': 'backup', 'condition': 'healthy', 'severity': 'healthy', 'healthy': True,
                'computed_at': now.isoformat(), 'published_at': now.isoformat(), 'interval': 300,
                'payload_keys': ['alert', 'local_capture', 'offsite']}
        base.update(over)
        return base

    def test_a_refreshed_recent_clean_row_is_accepted(self):
        with patch.object(c, 'published_row', return_value=self.row()):
            self.assertEqual(c.verify_publication(None)['key'], 'backup')
            self.assertEqual(c.verify_publication(self.row(published_at='2020-01-01T00:00:00+00:00'))['key'],
                             'backup')

    def test_a_row_that_did_not_move_is_not_a_publication(self):
        same = self.row()
        with patch.object(c, 'published_row', return_value=same), self.assertRaises(RuntimeError) as caught:
            c.verify_publication(same)
        self.assertIn('not refreshed', str(caught.exception))

    def test_a_missing_stale_or_undersized_row_refuses(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        for value, label in ((None, 'nothing published'),
                             (self.row(published_at=old), 'published long ago'),
                             (self.row(interval=30), 'interval below the schema floor')):
            with self.subTest(case=label), patch.object(c, 'published_row', return_value=value), \
                 self.assertRaises(RuntimeError):
                c.verify_publication(None)

    def test_a_payload_naming_a_clinical_field_refuses_publication(self):
        for key in ('patient', 'encounter', 'note', 'transcript', 'clinical'):
            with self.subTest(key=key), \
                 patch.object(c, 'published_row', return_value=self.row(payload_keys=['alert', key])), \
                 self.assertRaises(RuntimeError):
                c.verify_publication(None)

    def test_the_row_is_read_back_through_the_application_model(self):
        import inspect
        source = inspect.getsource(c.published_row)
        self.assertIn('from core.models import ServiceHealth', source)
        self.assertIn("filter(key=", source)
        for forbidden in ('psql', 'DROP', 'UPDATE ', 'DELETE ', 'INSERT '):
            self.assertNotIn(forbidden, source)


class HostActionIsBoundedAndReversible(unittest.TestCase):
    def payload(self, action='install', **over):
        p = {'action': action, 'hashes': {s: 'h' for s in c.base.SOURCES},
             'baseline': {'units': {}, 'configuration': {}, 'processes': {}}, 'commit': 'a' * 40}
        p.update(over)
        return p

    def test_the_helper_refuses_an_unexpected_scope_or_caller(self):
        with patch.object(c.base.os, 'getuid', return_value=1000), self.assertRaises(RuntimeError):
            c.root_action(self.payload())
        with patch.object(c.base.os, 'getuid', return_value=0), self.assertRaises(RuntimeError):
            c.root_action(self.payload(action='reboot'))
        with patch.object(c.base.os, 'getuid', return_value=0), self.assertRaises(RuntimeError):
            c.root_action(self.payload(extra='unreviewed'))
        bad = self.payload()
        bad['hashes'] = dict(bad['hashes'], **{'rebuild/ops/offsite_renewal.py': 'h'})
        with patch.object(c.base.os, 'getuid', return_value=0), self.assertRaises(RuntimeError):
            c.root_action(bad)

    def test_source_drift_refuses_before_any_systemd_command(self):
        with patch.object(c.base.os, 'getuid', return_value=0), \
             patch.object(c.base, 'digest', return_value='different'), \
             patch.object(c.base, 'command') as command, self.assertRaises(RuntimeError):
            c.root_action(self.payload())
        command.assert_not_called()

    def test_the_act_never_touches_an_existing_service_or_the_database_directly(self):
        import inspect
        source = inspect.getsource(c.root_action)
        for forbidden in ('quillmd-fresh-doctor', 'quillmd-fresh-admin', 'quillmd-fresh-worker',
                          'quillmd-fresh-database', 'quillmd-fresh-backup', 'quillmd-fresh-offsite',
                          'psql', 'rm ', "'chmod'", 'chmod -R', 'chown -R', '0o777', '0o666'):
            self.assertNotIn(forbidden, source)
        # The only mode change is on the file descriptor of a unit this act exclusively created.
        self.assertEqual(source.count('chmod'), 1)
        self.assertIn('os.fchmod(stream.fileno(), 0o644)', source)
        self.assertIn('os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW', source)
        self.assertIn("payload['action'] in ('install', 'activate', 'disable')", source)

    def test_disable_is_a_real_rollback_that_keeps_every_unit_and_record(self):
        import inspect
        source = inspect.getsource(c.root_action)
        self.assertIn("'disable', '--now', TIMER", source)
        self.assertIn('Timer enablement survived rollback', source)
        self.assertNotIn('os.unlink', source)
        self.assertNotIn('shutil.rmtree', source)

    def test_a_failed_activation_disables_the_timer_it_may_have_enabled(self):
        import inspect
        source = inspect.getsource(c.root_action)
        tail = source.split('except Exception:', 1)[1]
        self.assertIn("disable', '--now', TIMER", tail)
        self.assertIn('timer_stopped_disabled', tail)


class ReadOnlyByDefault(unittest.TestCase):
    def drive(self, *extra):
        """Run main() for real with only the host boundary stubbed; returns the helper mock."""
        import sys
        with patch.object(c.base, 'reviewed_source', return_value={x: 'h' for x in c.base.SOURCES}), \
             patch.object(c.base, 'baseline', return_value={'units': {}, 'configuration': {}, 'processes': {}}), \
             patch.object(c.base, 'require_absent'), patch.object(c.base, 'require_installed'), \
             patch.object(c.base, 'private_directory'), patch.object(c.base, 'write_private'), \
             patch.object(c, 'published_row', return_value=None), \
             patch.object(c.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=4242)), \
             patch.object(c.os, 'getuid', return_value=4242), \
             patch.object(c.base, 'managed_helper_run') as helper, \
             patch.object(sys, 'argv', ['install', '--expected-commit', 'a' * 40, *extra]):
            helper.return_value = SimpleNamespace(returncode=0, stdout=b'{"success": false}')
            c.main()
        return helper

    def test_execute_is_opt_in(self):
        """Behavioural: a disabling default leaves the asserted source text intact."""
        self.drive().assert_not_called()
        self.assertEqual(self.drive('--execute').call_count, 1)

    def test_the_plan_reports_no_mutation(self):
        import inspect
        source = inspect.getsource(c.main)
        self.assertIn("'host_mutation': False", source)
        self.assertLess(source.index('if not args.execute'), source.index('managed_helper_run'))

    def test_only_the_project_operator_may_run_it(self):
        """Behavioural: a mismatched uid must refuse before anything is read or run."""
        import inspect, sys
        self.assertIn("pwd.getpwnam('claude').pw_uid", inspect.getsource(c.main))
        with patch.object(c.pwd, 'getpwnam', return_value=SimpleNamespace(pw_uid=4242)), \
             patch.object(c.os, 'getuid', return_value=4243), \
             patch.object(c.base, 'reviewed_source') as reviewed, \
             patch.object(c.base, 'managed_helper_run') as helper, \
             patch.object(sys, 'argv', ['install', '--expected-commit', 'a' * 40, '--execute']), \
             self.assertRaises(RuntimeError):
            c.main()
        reviewed.assert_not_called()
        helper.assert_not_called()


if __name__ == '__main__':
    unittest.main()
