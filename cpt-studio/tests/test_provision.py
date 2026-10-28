"""manage.py provision: the owner, the review agent and a human reviewer (owner decision 2026-10-28, a doctor's
demonstration account). Passwords come from files and are never printed."""
import io
import tempfile
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from studio import models

OWNER_PASSWORD = 'owner-Pass-0rd-for-tests-9184'
AGENT_PASSWORD = 'agent-Pass-0rd-for-tests-7731'
REVIEWER_PASSWORD = 'reviewer-Pass-0rd-for-tests-5520'


class ProvisionTests(TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def secret(self, name, value):
        path = Path(self.dir.name) / name
        path.write_text(value + '\n', encoding='utf-8')
        return str(path)

    def run_command(self, *args):
        out = io.StringIO()
        call_command('provision', *args, stdout=out)
        return out.getvalue()

    def provision_owner_and_agent(self):
        return self.run_command('--owner-username', 'owner1', '--owner-password-file', self.secret('o', OWNER_PASSWORD),
                                '--agent-username', 'agent1', '--agent-password-file', self.secret('a', AGENT_PASSWORD))

    def test_owner_and_agent_as_before(self):
        out = self.provision_owner_and_agent()
        self.assertIn('created human account owner1 (owner)', out)
        self.assertIn('created agent account agent1 (reviewer)', out)
        self.assertTrue(models.User.objects.get(username='owner1').check_password(OWNER_PASSWORD))

    def test_a_human_reviewer_is_added_to_the_existing_workspace_without_owner_arguments(self):
        self.provision_owner_and_agent()
        owner_hash = models.User.objects.get(username='owner1').password
        out = self.run_command('--reviewer-username', 'demo-reviewer', '--reviewer-display-name', 'Demo reviewer',
                               '--reviewer-password-file', self.secret('r', REVIEWER_PASSWORD))
        self.assertIn('created human account demo-reviewer (reviewer)', out)
        self.assertNotIn(REVIEWER_PASSWORD, out)
        user = models.User.objects.get(username='demo-reviewer')
        self.assertEqual(user.actor_kind, models.User.HUMAN)
        self.assertEqual(user.display_name, 'Demo reviewer')
        self.assertTrue(user.check_password(REVIEWER_PASSWORD))
        membership = models.Membership.objects.get(user=user)
        self.assertEqual(membership.role, models.Membership.REVIEWER)
        self.assertTrue(membership.active)
        self.assertEqual(models.Workspace.objects.count(), 1)
        self.assertEqual(models.User.objects.get(username='owner1').password, owner_hash)
        events = models.AuditEvent.objects.filter(event='account.provisioned', data__username='demo-reviewer')
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.get().data['role'], models.Membership.REVIEWER)

    def test_a_second_run_keeps_the_reviewer_and_its_password(self):
        self.provision_owner_and_agent()
        self.run_command('--reviewer-username', 'demo-reviewer', '--reviewer-password-file', self.secret('r', REVIEWER_PASSWORD))
        out = self.run_command('--reviewer-username', 'demo-reviewer', '--reviewer-password-file', self.secret('r2', 'another-Pass-0rd-3311'))
        self.assertIn('kept human account demo-reviewer (reviewer)', out)
        self.assertTrue(models.User.objects.get(username='demo-reviewer').check_password(REVIEWER_PASSWORD))
        self.assertEqual(models.User.objects.filter(username='demo-reviewer').count(), 1)

    def test_a_reviewer_needs_an_existing_workspace(self):
        with self.assertRaisesMessage(CommandError, 'provision it with its owner first'):
            self.run_command('--reviewer-username', 'demo-reviewer', '--reviewer-password-file', self.secret('r', REVIEWER_PASSWORD))
        self.assertFalse(models.User.objects.filter(username='demo-reviewer').exists())
        self.assertFalse(models.Workspace.objects.exists())

    def test_a_reviewer_needs_a_password_file_and_an_empty_one_is_refused(self):
        self.provision_owner_and_agent()
        with self.assertRaisesMessage(CommandError, '--reviewer-password-file is required'):
            self.run_command('--reviewer-username', 'demo-reviewer')
        with self.assertRaisesMessage(CommandError, 'Password file is empty'):
            self.run_command('--reviewer-username', 'demo-reviewer', '--reviewer-password-file', self.secret('e', ''))
        self.assertFalse(models.User.objects.filter(username='demo-reviewer').exists())

    def test_nothing_to_provision_is_refused(self):
        with self.assertRaisesMessage(CommandError, '--owner-username is required'):
            self.run_command()

    def test_an_owner_is_never_demoted_and_an_agent_never_becomes_human(self):
        self.provision_owner_and_agent()
        with self.assertRaisesMessage(CommandError, 'never demotes an owner'):
            self.run_command('--reviewer-username', 'owner1', '--reviewer-password-file', self.secret('r', REVIEWER_PASSWORD))
        self.assertEqual(models.Membership.objects.get(user__username='owner1').role, models.Membership.OWNER)
        with self.assertRaisesMessage(CommandError, 'different actor kind'):
            self.run_command('--reviewer-username', 'agent1', '--reviewer-password-file', self.secret('r', REVIEWER_PASSWORD))
        self.assertEqual(models.User.objects.get(username='agent1').actor_kind, models.User.AGENT)
