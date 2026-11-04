"""Core repair (2026-11-03), the reassess phase's participants: the command compares the final assessment's
participants with the WORKER's (--participants, which the installer passes from its app receipt), because the
installer's one-shot runs with every participant disabled - with its own configuration it refused every harness
encounter, Mara included."""
from __future__ import annotations

import io
import json

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from studio import models
from tests.test_cux_flow import TWO_EXTENTS, ColonCase
from tests.test_pipeline_api import drain


class ParticipantsTheWorkerRunsTests(ColonCase):
    """tests/test_cux_flow.ReassessRetainedTests' chain (Corti the harness suite's fake, Astra and Fable the replay
    adapters), with its helpers and none of its tests."""

    def chain(self):
        encounter_id = self.create(TWO_EXTENTS)
        drain()
        return encounter_id

    def command(self, *args):
        out = io.StringIO()
        call_command('reassess_retained', *args, stdout=out)
        return json.loads(out.getvalue())

    def refused(self, encounter_id, message):
        before = (models.Job.objects.count(), models.AuditEvent.objects.filter(event='assessment.refreshed').count())
        with self.assertRaisesMessage(CommandError, message):
            self.command('--encounter', str(encounter_id), '--tag', 'cux-participants-refused')
        self.assertEqual((models.Job.objects.count(),
                          models.AuditEvent.objects.filter(event='assessment.refreshed').count()), before)

    def test_the_worker_s_participants_are_named_where_this_process_runs_none(self):
        encounter_id = self.chain()
        with override_settings(ASTRA_MODE='disabled', FABLE_MODE='disabled'):  # the installer's one-shot
            self.refused(encounter_id, 'The participants configured here are not the ones the final assessment read')
            plan = self.command('--encounter', encounter_id, '--tag', 'cux-participants', '--dry-run',
                                '--participants', 'astra,fable')
            self.assertEqual(plan['action'], 'dry_run')
            for wrong in ('astra', 'none', 'fable,astra,astra'):
                with self.subTest(wrong), self.assertRaises(CommandError):
                    self.command('--encounter', encounter_id, '--tag', 'cux-participants', '--dry-run',
                                 '--participants', wrong)
            with self.assertRaisesMessage(CommandError, '--participants names each participant once'):
                self.command('--encounter', encounter_id, '--tag', 'x', '--participants', 'corti')
        # with no --participants, this process's own configuration is read, as before
        self.assertEqual(self.command('--encounter', encounter_id, '--tag', 'cux-participants', '--dry-run')['action'],
                         'dry_run')
