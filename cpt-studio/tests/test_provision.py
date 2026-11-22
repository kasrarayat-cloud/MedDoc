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
        with self.assertRaises(CommandError) as caught:
            self.run_command('--specialty', 'neurosurgery', '--owner-username', 'owner1',
                             '--owner-password-file', self.secret('o2', OWNER_PASSWORD))
        self.assertEqual(str(caught.exception), "Account owner1 already serves the Gastroenterology workspace "
                                                "'Gastroenterology'; one login serves one workspace until a workspace "
                                                "switcher exists (D390).")
        # refused as a whole: no Neurosurgery category or workspace is left behind
        self.assertFalse(models.Category.objects.filter(slug='neurosurgery').exists())
        self.assertEqual(models.Membership.objects.filter(user__username='owner1').count(), 1)

    def test_an_unknown_specialty_is_refused(self):
        with self.assertRaises(CommandError):
            self.run_command('--specialty', 'cardiology', '--owner-username', 'x',
                             '--owner-password-file', self.secret('x', OWNER_PASSWORD))


class WorkspaceNameTests(ProvisionCommand, TestCase):
    """A workspace is found by its name exactly as stored and a name is stored as given; a new workspace's name is not
    another specialty's name (read with white space and case aside) and no workspace of another specialty has exactly
    that name (refutation N1-2-1, N1-2-2, N2-2-1). Every refusal states facts and gives no command (refutation N6-1-1,
    N6-1-2), so the whole message is pinned."""

    def refusal(self, *argv):
        with self.assertRaises(CommandError) as caught:
            self.run_command(*argv)
        return str(caught.exception)

    def test_another_specialtys_exact_workspace_name_is_refused_and_a_variant_is_another_name(self):
        self.run_command('--specialty', 'neurosurgery', '--workspace-name', 'Riverside', '--owner-username', 'own-n',
                         '--owner-password-file', self.secret('n', OWNER_PASSWORD))
        self.assertEqual(self.refusal('--specialty', 'orthopedic-surgery', '--workspace-name', 'Riverside',
                                      '--owner-username', 'own-o', '--owner-password-file',
                                      self.secret('o', OWNER_PASSWORD)),
                         "The Neurosurgery workspace 'Riverside' has this name, and this run is for Orthopedic Surgery.")
        self.assertFalse(models.User.objects.filter(username='own-o').exists())
        # walk --workspace and verify_login compare names exactly, so a case variant is a different name to them
        out = self.run_command('--specialty', 'orthopedic-surgery', '--workspace-name', 'riverside', '--owner-username',
                               'own-o', '--owner-password-file', self.secret('o2', OWNER_PASSWORD))
        self.assertIn('(riverside, orthopedic-surgery) created', out)
        self.assertEqual(sorted(models.Workspace.objects.values_list('name', 'category__slug')),
                         [('Riverside', 'neurosurgery'), ('riverside', 'orthopedic-surgery')])

    def test_a_specialty_name_is_that_specialtys_alone(self):
        for name, specialty in (('Neurosurgery', 'Neurosurgery'), ('NEUROSURGERY', 'Neurosurgery'),
                                (' Neurosurgery', 'Neurosurgery'), ('orthopedic  surgery', 'Orthopedic Surgery')):
            with self.subTest(name=name):
                self.assertEqual(self.refusal('--workspace-name', name, '--owner-username', 'drneuro2',
                                              '--owner-password-file', self.secret('x', OWNER_PASSWORD)),
                                 f"{name!r} is the name of the {specialty} specialty, and this run is for "
                                 f"Gastroenterology.")
        self.assertFalse(models.Workspace.objects.exists())
        self.assertFalse(models.Category.objects.exists())

    def test_a_new_name_is_stored_as_given_and_needs_one(self):
        out = self.run_command('--specialty', 'neurosurgery', '--workspace-name', ' Spine  Center', '--owner-username',
                               'own-n', '--owner-password-file', self.secret('n', OWNER_PASSWORD))
        self.assertIn('( Spine  Center, neurosurgery) created', out)
        for name in ('', '   '):
            with self.subTest(name=name):
                self.assertEqual(self.refusal('--specialty', 'orthopedic-surgery', '--workspace-name', name,
                                              '--owner-username', 'own-o', '--owner-password-file',
                                              self.secret('o', OWNER_PASSWORD)), 'A new workspace needs a name.')
        self.assertEqual(models.Workspace.objects.count(), 1)

    def test_adding_accounts_names_the_workspace_exactly_and_states_what_reads_alike(self):
        self.provision('neurosurgery', 'owner-neuro', 'review-agent-neuro')
        self.assertEqual(self.refusal('--specialty', 'neurosurgery', '--workspace-name', 'neurosurgery',
                                      '--reviewer-username', 'drj', '--reviewer-password-file',
                                      self.secret('r', REVIEWER_PASSWORD)),
                         "No Neurosurgery workspace is named exactly 'neurosurgery'. Named alike: 'Neurosurgery' "
                         "(Neurosurgery).")
        # --specialty left out: the facts name the workspace and its specialty (refutation N1-2-2, N6-1-2)
        self.assertEqual(self.refusal('--workspace-name', 'Neurosurgery', '--reviewer-username', 'drj',
                                      '--reviewer-password-file', self.secret('r1', REVIEWER_PASSWORD)),
                         "No Gastroenterology workspace is named exactly 'Neurosurgery'. 'Neurosurgery' is the name of "
                         "the Neurosurgery specialty, and this run is for Gastroenterology. Named alike: 'Neurosurgery' "
                         "(Neurosurgery).")
        out = self.run_command('--specialty', 'neurosurgery', '--workspace-name', 'Neurosurgery', '--reviewer-username',
                               'drj', '--reviewer-password-file', self.secret('r2', REVIEWER_PASSWORD))
        self.assertIn('created human account drj (reviewer)', out)
        self.assertIn('(Neurosurgery, neurosurgery) existing', out)
        self.assertEqual(models.Workspace.objects.count(), 1)

    def test_existing_names_are_found_exactly_as_stored(self):
        # names stored before these rules (any name as given, '' included) are reached exactly as they are
        category = models.Category.objects.create(slug='gastroenterology', name='Gastroenterology',
                                                  profiles_version='gi-profiles@3')
        spaced = models.Workspace.objects.create(category=category, name='GI  Clinic ')
        plain = models.Workspace.objects.create(category=category, name='GI Clinic')
        empty = models.Workspace.objects.create(category=category, name='')
        for name, workspace, user in (('GI  Clinic ', spaced, 'drz'), ('GI Clinic', plain, 'dry'), ('', empty, 'dre')):
            with self.subTest(name=name):
                self.run_command('--workspace-name', name, '--reviewer-username', user,
                                 '--reviewer-password-file', self.secret(user, REVIEWER_PASSWORD))
                self.assertEqual(models.Membership.objects.get(user__username=user).workspace, workspace)
        self.assertEqual(self.refusal('--workspace-name', 'GI  Clinic', '--reviewer-username', 'drx',
                                      '--reviewer-password-file', self.secret('x', REVIEWER_PASSWORD)),
                         "No Gastroenterology workspace is named exactly 'GI  Clinic'. Named alike: 'GI  Clinic ' "
                         "(Gastroenterology), 'GI Clinic' (Gastroenterology).")
        # with an owner, a name not stored is a new workspace, as it always was; nobody joins 'GI Clinic' or 'GI  Clinic '
        out = self.run_command('--workspace-name', 'GI  Clinic', '--owner-username', 'drowner2',
                               '--owner-password-file', self.secret('o', OWNER_PASSWORD))
        self.assertIn('(GI  Clinic, gastroenterology) created', out)
        self.assertEqual(models.Membership.objects.get(user__username='drowner2').workspace.name, 'GI  Clinic')
        self.assertEqual(models.Membership.objects.filter(workspace__in=[spaced, plain]).count(), 2)

    def test_an_old_workspace_named_like_a_specialty_captures_nothing(self):
        # refutation N4-1-1: a Gastroenterology workspace stored before these rules under a specialty's name (spacing
        # aside) takes no member asking for that specialty's name, and the specialty's own workspace is its own
        category = models.Category.objects.create(slug='gastroenterology', name='Gastroenterology',
                                                  profiles_version='gi-profiles@3')
        old = models.Workspace.objects.create(category=category, name='Orthopedic  Surgery')
        self.provision('orthopedic-surgery', 'drortho', 'agent-ortho')
        self.assertEqual(models.Membership.objects.get(user__username='drortho').workspace.category.slug,
                         'orthopedic-surgery')
        self.assertFalse(models.Membership.objects.filter(workspace=old).exists())
        self.assertEqual(self.refusal('--workspace-name', 'Orthopedic Surgery', '--reviewer-username', 'drgi',
                                      '--reviewer-password-file', self.secret('r', REVIEWER_PASSWORD)),
                         "No Gastroenterology workspace is named exactly 'Orthopedic Surgery'. 'Orthopedic Surgery' is "
                         "the name of the Orthopedic Surgery specialty, and this run is for Gastroenterology. Named "
                         "alike: 'Orthopedic  Surgery' (Gastroenterology), 'Orthopedic Surgery' (Orthopedic Surgery).")

    def test_an_account_already_in_several_workspaces_keeps_working_where_it_is(self):
        # refutation N5-1-6: an earlier installation's agent in two workspaces can have its password rotated in either;
        # it is only never ADDED to another workspace, reactivation included (refutation N6-1-8)
        category = models.Category.objects.create(slug='gastroenterology', name='Gastroenterology',
                                                  profiles_version='gi-profiles@3')
        first = models.Workspace.objects.create(category=category, name='Gastroenterology')
        second = models.Workspace.objects.create(category=category, name='GI Demo')
        agent = models.User.objects.create_user(username='review-agent', password='old-Pass-0rd-1',
                                                actor_kind=models.User.AGENT)
        for workspace in (first, second):
            models.Membership.objects.create(user=agent, workspace=workspace, role=models.Membership.REVIEWER)
        out = self.run_command('--workspace-name', 'GI Demo', '--owner-username', 'owner2', '--owner-password-file',
                               self.secret('o', OWNER_PASSWORD), '--agent-username', 'review-agent',
                               '--agent-password-file', self.secret('a', AGENT_PASSWORD), '--reset-passwords')
        self.assertIn('kept agent account review-agent (reviewer)', out)
        agent.refresh_from_db()
        self.assertTrue(agent.check_password(AGENT_PASSWORD))
        third = models.Workspace.objects.create(category=category, name='GI Third')
        models.Membership.objects.create(user=agent, workspace=third, role=models.Membership.REVIEWER, active=False)
        self.assertEqual(self.refusal('--workspace-name', 'GI Third', '--owner-username', 'owner3',
                                      '--owner-password-file', self.secret('o3', OWNER_PASSWORD), '--agent-username',
                                      'review-agent', '--agent-password-file', self.secret('a3', AGENT_PASSWORD)),
                         "Account review-agent already serves the Gastroenterology workspace 'GI Demo', the "
                         "Gastroenterology workspace 'Gastroenterology'; one login serves one workspace until a "
                         "workspace switcher exists (D390).")
        self.assertFalse(models.Membership.objects.filter(workspace=third, active=True).exists())
        self.assertFalse(models.User.objects.filter(username='owner3').exists())

    def test_adding_accounts_states_the_rule_an_owner_run_would_meet(self):
        # main's "provision it with its owner first" only where an owner run would make the workspace (refutation N6-1-2)
        self.run_command('--specialty', 'neurosurgery', '--workspace-name', 'Riverside', '--owner-username', 'own-n',
                         '--owner-password-file', self.secret('n', OWNER_PASSWORD))
        self.assertEqual(self.refusal('--workspace-name', 'Riverside', '--reviewer-username', 'drj',
                                      '--reviewer-password-file', self.secret('r', REVIEWER_PASSWORD)),
                         "No Gastroenterology workspace is named exactly 'Riverside'. The Neurosurgery workspace "
                         "'Riverside' has this name, and this run is for Gastroenterology. Named alike: 'Riverside' "
                         "(Neurosurgery).")
        self.assertEqual(self.refusal('--specialty', 'orthopedic-surgery', '--workspace-name', 'Neurosurgery',
                                      '--reviewer-username', 'drj', '--reviewer-password-file',
                                      self.secret('r2', REVIEWER_PASSWORD)),
                         "No Orthopedic Surgery workspace is named exactly 'Neurosurgery'. 'Neurosurgery' is the name "
                         "of the Neurosurgery specialty, and this run is for Orthopedic Surgery.")
        self.assertEqual(self.refusal('--workspace-name', '', '--reviewer-username', 'drj', '--reviewer-password-file',
                                      self.secret('r3', REVIEWER_PASSWORD)),
                         "No Gastroenterology workspace is named exactly ''. A new workspace needs a name.")
        self.assertEqual(self.refusal('--workspace-name', 'Lakeside', '--reviewer-username', 'drj',
                                      '--reviewer-password-file', self.secret('r4', REVIEWER_PASSWORD)),
                         "No workspace named 'Lakeside' exists; provision it with its owner first.")
        self.assertFalse(models.User.objects.filter(username='drj').exists())

    def test_a_run_takes_the_provisioning_lock_before_anything_else(self):
        # refutation N5-1-4: two runs at once are serialized, so both cannot pass the name rules and both create
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as queries:
            self.provision('neurosurgery', 'owner-neuro', 'review-agent-neuro')
        statements = [query['sql'] for query in queries.captured_queries
                      if not query['sql'].upper().startswith(('SAVEPOINT', 'RELEASE SAVEPOINT'))]
        self.assertIn('pg_advisory_xact_lock', statements[0])
