"""Create a specialty's workspace and its accounts, idempotently.

The specialties (owner directions of 2026-10-23 and 2026-11-22, DECISIONS D390): Gastroenterology, Neurosurgery and
Orthopedic Surgery, each a workspace category. A workspace's specialty is a label - the page and the PDF report show
it - and nothing on the coding path reads it: Fable codes every specialty, with no engine, code list or routing (D358).

One login serves one workspace until a workspace switcher exists (D390): an account already active in another workspace
is refused, never added to a second one, so nobody is left seeing the wrong workspace's documents.

Passwords are read from files (never argv, never printed). An existing account
keeps its password unless --reset-passwords is given.

A human reviewer (for example a doctor's demonstration account, owner decision
2026-10-28) is added to the existing workspace with --reviewer-username and
--reviewer-password-file; the owner arguments may then be left out, and the
workspace must already exist.
"""
from pathlib import Path

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from studio import audit, models

# Each specialty's category: slug -> (name, profiles_version). Gastroenterology keeps the identity studio/gi/profiles.py
# defined (that module went with the earlier pipeline, DECISIONS D351-D352), so provisioning finds, and leaves as it is,
# the category an installation already has. profiles_version is a label that nothing reads.
SPECIALTIES = {
    'gastroenterology': ('Gastroenterology', 'gi-profiles@3'),
    'neurosurgery': ('Neurosurgery', 'fable-coding@1'),
    'orthopedic-surgery': ('Orthopedic Surgery', 'fable-coding@1'),
}
CATEGORY_SLUG = 'gastroenterology'
CATEGORY_NAME, PROFILES_VERSION = SPECIALTIES[CATEGORY_SLUG]


def _password(path):
    data = Path(path).read_text(encoding='utf-8').strip()
    if not data:
        raise CommandError(f'Password file is empty: {path}')
    return data


class Command(BaseCommand):
    help = ('Provision a specialty workspace (Gastroenterology unless --specialty names another) with an owner and '
            '(optionally) an automated review agent account and a human reviewer account.')

    def add_arguments(self, parser):
        parser.add_argument('--specialty', choices=sorted(SPECIALTIES), default=CATEGORY_SLUG)
        parser.add_argument('--workspace-name', default='', help="the workspace's name (default: the specialty's name)")
        parser.add_argument('--owner-username', default='')
        parser.add_argument('--owner-display-name', default='')
        parser.add_argument('--owner-password-file', default='')
        parser.add_argument('--agent-username', default='')
        parser.add_argument('--agent-display-name', default='CPT Studio review agent')
        parser.add_argument('--agent-password-file', default='')
        parser.add_argument('--reviewer-username', default='')
        parser.add_argument('--reviewer-display-name', default='')
        parser.add_argument('--reviewer-password-file', default='')
        parser.add_argument('--reset-passwords', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        if not options['owner_username'] and not options['reviewer_username']:
            raise CommandError('--owner-username is required (or --reviewer-username to add a reviewer to the existing '
                               'workspace).')
        if options['owner_username'] and not options['owner_password_file']:
            raise CommandError('--owner-password-file is required with --owner-username.')
        if options['reviewer_username'] and not options['reviewer_password_file']:
            raise CommandError('--reviewer-password-file is required with --reviewer-username.')
        slug = options['specialty']
        name, profiles_version = SPECIALTIES[slug]
        workspace_name = options['workspace_name'] or name
        category, _ = models.Category.objects.get_or_create(
            slug=slug, defaults={'name': name, 'profiles_version': profiles_version})
        if category.profiles_version != profiles_version:
            category.profiles_version = profiles_version
            category.save(update_fields=['profiles_version'])
        workspace = models.Workspace.objects.filter(category=category, name=workspace_name).first()
        if workspace is None:
            # each workspace name belongs to one specialty, and a specialty's own name is its alone (refutation
            # N1-2-1, N1-2-2): a member or a check that knows a workspace by its name always knows its specialty too
            elsewhere = (models.Workspace.objects.filter(name__iexact=workspace_name).exclude(category=category)
                         .select_related('category').first())
            if elsewhere is not None:
                raise CommandError(f'The workspace {elsewhere.name!r} is a {elsewhere.category.name} workspace; give '
                                   f'--specialty {elsewhere.category.slug} (each workspace name belongs to one '
                                   f'specialty).')
            owner_of_name = next((other for other, (other_name, _) in SPECIALTIES.items()
                                  if other_name.casefold() == workspace_name.casefold()), slug)
            if owner_of_name != slug:
                raise CommandError(f'{workspace_name!r} is the name of the {SPECIALTIES[owner_of_name][0]} specialty; '
                                   f'give --specialty {owner_of_name}.')
            if not options['owner_username']:
                raise CommandError(f'No workspace named {workspace_name!r} exists; provision it with its '
                                   f'owner first.')
            workspace = models.Workspace.objects.create(category=category, name=workspace_name)
        accounts = []
        if options['owner_username']:
            accounts.append((options['owner_username'], options['owner_display_name'], options['owner_password_file'],
                             models.User.HUMAN, models.Membership.OWNER))
        if options['agent_username']:
            if not options['agent_password_file']:
                raise CommandError('--agent-password-file is required with --agent-username.')
            accounts.append((options['agent_username'], options['agent_display_name'], options['agent_password_file'],
                             models.User.AGENT, models.Membership.REVIEWER))
        if options['reviewer_username']:
            accounts.append((options['reviewer_username'], options['reviewer_display_name'],
                             options['reviewer_password_file'], models.User.HUMAN, models.Membership.REVIEWER))
        for username, display, password_file, kind, role in accounts:
            # the row is locked, so two runs at once cannot both pass the one-workspace check (refutation N1-2-3)
            user = models.User.objects.select_for_update().filter(username=username).first()
            created = user is None
            if created:
                user = models.User(username=username, actor_kind=kind, display_name=display or username)
            elif user.actor_kind != kind:
                raise CommandError(f'Account {username} exists with a different actor kind.')
            elif models.Membership.objects.filter(user=user, active=True).exclude(workspace=workspace).exists():
                raise CommandError(f'Account {username} already serves another workspace; one login serves one '
                                   f'workspace until a workspace switcher exists (D390). Use a separate login.')
            if created or options['reset_passwords']:
                password = _password(password_file)
                validate_password(password, user)
                user.set_password(password)
            user.save()
            membership, _ = models.Membership.objects.get_or_create(user=user, workspace=workspace,
                                                                    defaults={'role': role})
            if membership.role == models.Membership.OWNER and role != models.Membership.OWNER:
                raise CommandError(f'Account {username} is this workspace\'s owner; provisioning never demotes an owner.')
            if membership.role != role or not membership.active:
                membership.role, membership.active = role, True
                membership.save(update_fields=['role', 'active'])
            audit.record(workspace, 'account.provisioned', actor=None, username=username, actor_kind=kind,
                         role=role, created=created)
            self.stdout.write(f'{"created" if created else "kept"} {kind} account {username} ({role})')
        self.stdout.write(f'workspace {workspace.pk} ({workspace.name}, {category.slug})')
