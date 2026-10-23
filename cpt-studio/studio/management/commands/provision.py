"""Create the Gastroenterology workspace and its accounts, idempotently.

Passwords are read from files (never argv, never printed). An existing account
keeps its password unless --reset-passwords is given.
"""
from pathlib import Path

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from studio import audit, models
from studio.gi.profiles import CATEGORY_NAME, CATEGORY_SLUG, PROFILES_VERSION


def _password(path):
    data = Path(path).read_text(encoding='utf-8').strip()
    if not data:
        raise CommandError(f'Password file is empty: {path}')
    return data


class Command(BaseCommand):
    help = 'Provision the GI workspace with an owner and (optionally) an automated review agent account.'

    def add_arguments(self, parser):
        parser.add_argument('--workspace-name', default='Gastroenterology')
        parser.add_argument('--owner-username', required=True)
        parser.add_argument('--owner-display-name', default='')
        parser.add_argument('--owner-password-file', required=True)
        parser.add_argument('--agent-username', default='')
        parser.add_argument('--agent-display-name', default='CPT Studio review agent')
        parser.add_argument('--agent-password-file', default='')
        parser.add_argument('--reset-passwords', action='store_true')

    @transaction.atomic
    def handle(self, *args, **options):
        category, _ = models.Category.objects.get_or_create(
            slug=CATEGORY_SLUG, defaults={'name': CATEGORY_NAME, 'profiles_version': PROFILES_VERSION})
        if category.profiles_version != PROFILES_VERSION:
            category.profiles_version = PROFILES_VERSION
            category.save(update_fields=['profiles_version'])
        workspace = models.Workspace.objects.filter(category=category, name=options['workspace_name']).first()
        if workspace is None:
            workspace = models.Workspace.objects.create(category=category, name=options['workspace_name'])
        accounts = [(options['owner_username'], options['owner_display_name'], options['owner_password_file'],
                     models.User.HUMAN, models.Membership.OWNER)]
        if options['agent_username']:
            if not options['agent_password_file']:
                raise CommandError('--agent-password-file is required with --agent-username.')
            accounts.append((options['agent_username'], options['agent_display_name'], options['agent_password_file'],
                             models.User.AGENT, models.Membership.REVIEWER))
        for username, display, password_file, kind, role in accounts:
            user = models.User.objects.filter(username=username).first()
            created = user is None
            if created:
                user = models.User(username=username, actor_kind=kind, display_name=display or username)
            elif user.actor_kind != kind:
                raise CommandError(f'Account {username} exists with a different actor kind.')
            if created or options['reset_passwords']:
                password = _password(password_file)
                validate_password(password, user)
                user.set_password(password)
            user.save()
            membership, _ = models.Membership.objects.get_or_create(user=user, workspace=workspace,
                                                                    defaults={'role': role})
            if membership.role != role or not membership.active:
                membership.role, membership.active = role, True
                membership.save(update_fields=['role', 'active'])
            audit.record(workspace, 'account.provisioned', actor=None, username=username, actor_kind=kind,
                         role=role, created=created)
            self.stdout.write(f'{"created" if created else "kept"} {kind} account {username} ({role})')
        self.stdout.write(f'workspace {workspace.pk} ({workspace.name}, {category.slug})')
