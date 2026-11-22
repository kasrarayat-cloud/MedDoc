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


class ProvisionCommand:
    """Mixin: password files in a temporary folder and the provision command's output."""

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

    def provision(self, specialty, owner, agent):
        return self.run_command('--specialty', specialty, '--owner-username', owner,
                                '--owner-password-file', self.secret(owner, OWNER_PASSWORD),
                                '--agent-username', agent, '--agent-password-file', self.secret(agent, AGENT_PASSWORD))



class SpecialtyProvisionTests(ProvisionCommand, TestCase):
    """Owner direction 2026-11-22 (D390): Neurosurgery and Orthopedic Surgery are workspace categories beside
    Gastroenterology, each provisioned the GI way; one login serves one workspace until a switcher exists."""

    def test_each_specialty_is_its_own_category_and_workspace(self):
        self.provision('gastroenterology', 'owner1', 'agent1')
        out = self.provision('neurosurgery', 'owner-neuro', 'review-agent-neuro')
        self.assertIn('created human account owner-neuro (owner)', out)
        self.assertIn('(Neurosurgery, neurosurgery)', out)
        self.provision('orthopedic-surgery', 'owner-ortho', 'review-agent-ortho')
        self.assertEqual(sorted(models.Category.objects.values_list('slug', 'name')),
                         [('gastroenterology', 'Gastroenterology'), ('neurosurgery', 'Neurosurgery'),
                          ('orthopedic-surgery', 'Orthopedic Surgery')])
        for username, specialty in (('owner1', 'Gastroenterology'), ('owner-neuro', 'Neurosurgery'),
                                    ('owner-ortho', 'Orthopedic Surgery'), ('review-agent-ortho', 'Orthopedic Surgery')):
            membership = models.Membership.objects.get(user__username=username)
            self.assertEqual((membership.workspace.name, membership.workspace.category.name), (specialty, specialty))
        # Gastroenterology keeps the identity an installation already has
        self.assertEqual(models.Category.objects.get(slug='gastroenterology').profiles_version, 'gi-profiles@3')

    def test_the_default_stays_gastroenterology(self):
        self.run_command('--owner-username', 'owner1', '--owner-password-file', self.secret('o', OWNER_PASSWORD))
        workspace = models.Workspace.objects.get()
        self.assertEqual((workspace.name, workspace.category.slug), ('Gastroenterology', 'gastroenterology'))

    def test_one_login_serves_one_workspace(self):
        self.provision('gastroenterology', 'owner1', 'agent1')
        with self.assertRaisesMessage(CommandError, 'already serves another workspace'):
            self.run_command('--specialty', 'neurosurgery', '--owner-username', 'owner1',
                             '--owner-password-file', self.secret('o2', OWNER_PASSWORD))
        # refused as a whole: no Neurosurgery category or workspace is left behind
        self.assertFalse(models.Category.objects.filter(slug='neurosurgery').exists())
        self.assertEqual(models.Membership.objects.filter(user__username='owner1').count(), 1)

    def test_an_unknown_specialty_is_refused(self):
        with self.assertRaises(CommandError):
            self.run_command('--specialty', 'cardiology', '--owner-username', 'x',
                             '--owner-password-file', self.secret('x', OWNER_PASSWORD))


class WorkspaceNameTests(ProvisionCommand, TestCase):
    """Refutation N1-2-1 and N1-2-2: each workspace name belongs to one specialty, and a specialty's own name is its alone,
    so a workspace known by its name (a member, the walk's --workspace) is known with its specialty."""

    def test_a_workspace_name_belongs_to_one_specialty(self):
        self.run_command('--specialty', 'neurosurgery', '--workspace-name', 'Riverside', '--owner-username', 'own-n',
                         '--owner-password-file', self.secret('n', OWNER_PASSWORD))
        with self.assertRaisesMessage(CommandError, "'Riverside' is a Neurosurgery workspace; give --specialty neurosurgery"):
            self.run_command('--specialty', 'orthopedic-surgery', '--workspace-name', 'riverside', '--owner-username',
                             'own-o', '--owner-password-file', self.secret('o', OWNER_PASSWORD))
        self.assertEqual(list(models.Workspace.objects.values_list('name', flat=True)), ['Riverside'])
        self.assertFalse(models.User.objects.filter(username='own-o').exists())

    def test_a_specialty_name_is_that_specialtys_alone(self):
        with self.assertRaisesMessage(CommandError, "'Neurosurgery' is the name of the Neurosurgery specialty; give "
                                                    "--specialty neurosurgery"):
            self.run_command('--workspace-name', 'Neurosurgery', '--owner-username', 'drneuro2',
                             '--owner-password-file', self.secret('x', OWNER_PASSWORD))
        self.assertFalse(models.Workspace.objects.exists())

    def test_the_reviewer_path_names_the_specialty_a_workspace_has(self):
        self.provision('neurosurgery', 'owner-neuro', 'review-agent-neuro')
        with self.assertRaisesMessage(CommandError, "'Neurosurgery' is a Neurosurgery workspace; give --specialty "
                                                    "neurosurgery"):
            self.run_command('--workspace-name', 'Neurosurgery', '--reviewer-username', 'drjones',
                             '--reviewer-password-file', self.secret('r', REVIEWER_PASSWORD))
        out = self.run_command('--specialty', 'neurosurgery', '--reviewer-username', 'drjones',
                               '--reviewer-password-file', self.secret('r2', REVIEWER_PASSWORD))
        self.assertIn('created human account drjones (reviewer)', out)
