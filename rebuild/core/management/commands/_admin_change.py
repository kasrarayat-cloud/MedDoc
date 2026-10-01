"""The shared command body of `elevate_additional_admin` and `reset_admin_mfa` (core.admin_authority)."""
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from core import admin_authority


class AdminChangeCommand(BaseCommand):
    operation = None

    def add_arguments(self, parser):
        parser.add_argument('--declaration', required=True,
                            help='docs/foundation/mutations/<YYYYMMDD>-quillmd-admin-<name>.md, committed; the same '
                                 'path given to scripts/run-ruled-mutation.sh --declaration')
        parser.add_argument('--target', required=True, help='the target account id the declaration names')

    def handle(self, *args, **options):
        refused = admin_authority.refused()
        try:
            result = admin_authority.perform(self.operation, options['declaration'], options['target'])
        except (refused, DatabaseError, OSError) as exc:
            # A refusal's text names files, ids and rules; never an email, a password or an authenticator key.
            label = str(exc) if isinstance(exc, refused) else type(exc).__name__
            raise CommandError('Administrator change refused: ' + label) from None
        self.stdout.write(json.dumps(result, sort_keys=True))
