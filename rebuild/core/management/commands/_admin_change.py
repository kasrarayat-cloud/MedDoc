"""The shared command body of `elevate_additional_admin` and `reset_admin_mfa` (core.admin_authority)."""
import json
import subprocess

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError

from core import admin_authority
from ops import deployment_profile
from ops.production_operator import OperatorError


class AdminChangeCommand(BaseCommand):
    operation = None

    def add_arguments(self, parser):
        parser.add_argument('--declaration', required=True,
                            help='the declaration the ruled-mutation door was opened for: in production its JSON file; '
                                 'in a checkout docs/foundation/mutations/<YYYYMMDD>-quillmd-admin-<name>.md')
        parser.add_argument('--target', required=True, help='the target account id the declaration names')
        parser.add_argument('--approver-code-file', required=True,
                            help='a 0600 file of this account holding the approver\'s current six-digit authenticator '
                                 'code (standard input is detached under the door)')

    def handle(self, *args, **options):
        try:
            result = admin_authority.perform(self.operation, options['declaration'], options['target'],
                                             options['approver_code_file'])
        except (admin_authority.Refused, OperatorError, deployment_profile.ProfileError, ValueError, KeyError,
                OSError, ValidationError, DatabaseError, subprocess.SubprocessError) as exc:
            # A refusal's text names files, ids and rules; never an email, a password, a code or an authenticator key.
            labelled = (admin_authority.Refused, OperatorError, deployment_profile.ProfileError)
            label = str(exc) if isinstance(exc, labelled) else type(exc).__name__
            raise CommandError('Administrator change refused: ' + label) from None
        self.stdout.write(json.dumps(result, sort_keys=True))
