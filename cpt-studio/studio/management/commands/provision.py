"""Create a specialty's workspace and its accounts, idempotently.

The specialties (owner directions of 2026-10-23 and 2026-11-22, DECISIONS D390): Gastroenterology, Neurosurgery and
Orthopedic Surgery, each a workspace category. A workspace's specialty is a label - the page and the PDF report show
it - and nothing on the coding path reads it: Fable codes every specialty, with no engine, code list or routing (D358).

One login serves one workspace until a workspace switcher exists (D390): a run never adds an account to a second
workspace (an account an earlier installation put in several keeps working there), so nobody is left seeing the wrong
workspace's documents.

A workspace is found by its name exactly as stored, and a name is stored as given. A NEW workspace's name is not another
specialty's name (white space and letter case aside: --specialty left out), and no workspace of another specialty has
exactly that name, so a check that knows a workspace by its name (walk --workspace, verify_login) knows its specialty
too. A refusal states what is in the way; it gives no command.

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
from django.db import connection, transaction

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
# one provisioning run at a time (a transaction-level PostgreSQL advisory lock, apart from studio/jobs.py's provider slots)
PROVISION_LOCK = 0x4350545350524F56  # 'CPTSPROV'


def _read(name: str) -> str:
    """A workspace name as a member reads it: white space around it set aside, runs of it as one space, letter case
    aside (str.casefold, which also folds a few compatibility letters such as the long s). Other look-alike letters and
    invisible characters are not folded: the operator names workspaces."""
    return ' '.join(name.split()).casefold()


def _named_alike(workspace_name: str) -> str:
    """" Named alike: ..." - every workspace, of any specialty, whose name reads the same as ``workspace_name`` (_read),
    named as stored with its specialty, sorted - or nothing. Facts for the operator; never a command."""
    reading = _read(workspace_name)
    found = sorted((each.name, each.category.name) for each in models.Workspace.objects.select_related('category')
                   if _read(each.name) == reading)
    return (' Named alike: ' + ', '.join(f'{name!r} ({specialty})' for name, specialty in found) + '.') if found else ''


def _new_name_problem(workspace_name: str, slug: str, category) -> str:
    """Why a NEW workspace could not take this name, as facts with no command (refutation N6-1-1, N6-1-2) - or nothing.
    The rules (owner direction 2026-11-22, D390): it has a name; it is not another specialty's name, read with white
    space and letter case aside (refutation N1-2-2, N2-2-1: --specialty left out); and no workspace of another specialty
    has exactly this name, so a check that knows a workspace by its exact name - walk --workspace and verify_login
    compare it exactly - knows its specialty too (refutation N1-2-1). Nothing else is ruled: a name is stored as given,
    and names that differ in case or spacing are different names, as they always were."""
    if not workspace_name.split():
        return 'A new workspace needs a name.'
    reading = _read(workspace_name)
    for other, (other_name, _) in SPECIALTIES.items():
        if other != slug and _read(other_name) == reading:
            return f'{workspace_name!r} is the name of the {other_name} specialty, and this run is for {category.name}.'
    same = sorted(each.category.name for each in models.Workspace.objects.filter(name=workspace_name)
                  .exclude(category=category).select_related('category'))
    if same:
        return f'The {same[0]} workspace {workspace_name!r} has this name, and this run is for {category.name}.'
    return ''


def _check_new_name(workspace_name: str, slug: str, category) -> None:
    problem = _new_name_problem(workspace_name, slug, category)
    if problem:
        raise CommandError(problem)


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
        parser.add_argument('--workspace-name', default=None, help="the workspace's name (default: the specialty's name)")
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
        # an explicit name is taken as given, '' included (refutation N5-1-5)
        workspace_name = name if options['workspace_name'] is None else options['workspace_name']
        # first, before any read: two runs at once cannot both pass the name rules and both create (refutation N5-1-4);
        # released when this run commits or fails
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [PROVISION_LOCK])
        category, _ = models.Category.objects.get_or_create(
            slug=slug, defaults={'name': name, 'profiles_version': profiles_version})
        if category.profiles_version != profiles_version:
            category.profiles_version = profiles_version
            category.save(update_fields=['profiles_version'])
        # an existing workspace is found by its name exactly as stored, as before; the rules below apply only when a
        # workspace is made, so an installation's existing names keep working as they did (refutation N4-1-1..3)
        workspace = models.Workspace.objects.filter(category=category, name=workspace_name).first()
        made = workspace is None
        if made:
            if not options['owner_username']:
                # adding accounts never makes a workspace. Main's instruction stands only where it holds - a run with
                # the owner would make this workspace; otherwise the refusal states the facts (the rule that run would
                # meet, and the workspaces of any specialty whose names read the same, as stored) and gives no command
                # (refutation N1-2-2, N5-1-1, N6-1-2)
                problem, alike = _new_name_problem(workspace_name, slug, category), _named_alike(workspace_name)
                if not problem and not alike:
                    raise CommandError(f'No workspace named {workspace_name!r} exists; provision it with its owner '
                                       f'first.')
                raise CommandError(f'No {category.name} workspace is named exactly {workspace_name!r}.'
                                   + (f' {problem}' if problem else '') + alike)
            _check_new_name(workspace_name, slug, category)
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
            elif not models.Membership.objects.filter(user=user, workspace=workspace, active=True).exists():
                # refused only when it would ADD the account to a second workspace: an account an earlier installation
                # made a member of several keeps working where it is (a password rotation; refutation N5-1-6); the
                # refusal names where it serves and gives no command (refutation N6-1-1)
                serves = sorted((each.workspace.category.name, each.workspace.name) for each in
                                models.Membership.objects.filter(user=user, active=True).exclude(workspace=workspace)
                                .select_related('workspace__category'))
                if serves:
                    raise CommandError(f'Account {username} already serves ' + ', '.join(
                        f'the {specialty} workspace {name!r}' for specialty, name in serves)
                        + '; one login serves one workspace until a workspace switcher exists (D390).')
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
        self.stdout.write(f'workspace {workspace.pk} ({workspace.name}, {category.slug}) '
                          f'{"created" if made else "existing"}')
