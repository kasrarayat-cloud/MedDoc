"""Production publisher against synthetic DB, injected AWS projection and temporary locks."""
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone
from core.admin_console import published_operations
from core.models import ServiceHealth
from core.management.commands import publish_operations_status as command
from ops import activation_exclusion as exclusion, aws_backup_status
from ops.production_operator import OperatorError
from ops.test_aws_backup_status import config, profile, Transport, NOW


class ProductionOperationsStatusTests(TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.profile = SimpleNamespace(operator_directory=Path(temporary.name))
        old_runtime = exclusion.RUNTIME
        self.addCleanup(exclusion.bind_runtime, old_runtime)
        self.report = aws_backup_status.collect(profile(), config(), Transport(), NOW)
        context = patch.object(command, 'production_context', return_value=self.profile)
        context.start(); self.addCleanup(context.stop)
        self.context = context
        self.aws = patch.object(aws_backup_status, 'status', return_value=self.report).start()
        self.addCleanup(patch.stopall)
        self.private = patch.object(command, 'collect').start()

    def publish(self, **options):
        output = io.StringIO()
        call_command('publish_operations_status', profile='production', stdout=output, **options)
        return output.getvalue()

    def test_production_projection_publishes_counts_not_restore_proof(self):
        self.publish()
        row = ServiceHealth.objects.get(key='backup')
        self.assertEqual(row.condition, 'aws_capture_current')
        self.assertEqual(row.payload['offsite']['copy_resources_current'], 2)
        self.assertFalse(row.healthy)
        self.assertFalse(row.payload['offsite_recovery_verified'])
        self.private.assert_not_called()
        self.assertEqual(exclusion.RUNTIME, self.profile.operator_directory / 'operations-publication')

    def test_api_failure_is_published_as_unknown_then_signalled(self):
        self.aws.return_value = ({'condition': 'aws_backup_unknown', 'severity': 'failure', 'healthy': False,
                                  'clinical_content_included': False, 'action': 'Check operator access.'}, 1)
        with self.assertRaises(SystemExit): self.publish()
        self.assertEqual(ServiceHealth.objects.get(key='backup').condition, 'aws_backup_unknown')

    def test_a_locked_production_act_defers_collection_and_keeps_old_row(self):
        self.publish(); old = ServiceHealth.objects.get(key='backup').computed_at
        self.aws.reset_mock()
        with exclusion.hold('synthetic-production-activation'):
            self.assertIn('Publication deferred', self.publish())
        self.aws.assert_not_called()
        self.assertEqual(ServiceHealth.objects.get(key='backup').computed_at, old)

    def test_dry_run_and_unverified_target_do_not_publish(self):
        self.assertIn('aws_capture_current', self.publish(dry_run=True))
        self.assertFalse(ServiceHealth.objects.exists())
        with patch.object(command, 'production_context', side_effect=OperatorError('wrong-target')):
            with self.assertRaises(CommandError): self.publish()
        self.assertFalse(ServiceHealth.objects.exists())

    def test_production_environment_cannot_accidentally_use_private_collector(self):
        with patch.dict(os.environ, {'QUILLMD_DEPLOYMENT_PROFILE': 'production'}):
            with self.assertRaises(CommandError): call_command('publish_operations_status')
        self.private.assert_not_called(); self.aws.assert_not_called()

    def test_existing_console_marks_missing_and_stale_production_status(self):
        self.assertEqual(published_operations()[0]['status'], 'Never published')
        self.publish()
        from datetime import timedelta
        ServiceHealth.objects.filter(key='backup').update(computed_at=timezone.now()-timedelta(seconds=610))
        row = published_operations()[0]
        self.assertTrue(row['stale']); self.assertEqual(row['severity'], 'warning')
