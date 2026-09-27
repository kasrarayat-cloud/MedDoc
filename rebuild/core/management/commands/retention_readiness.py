"""No execution switch: this command can only validate and count."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError
from core import retention_readiness as retention

class Command(BaseCommand):
    help='Read-only aggregate retention readiness; no deletion or eligibility decisions.'
    requires_system_checks=[]
    requires_migrations_checks=False

    def add_arguments(self,parser):
        parser.add_argument('--policy',required=True,help='Reviewed local JSON declarations; absence refuses.')
        parser.add_argument('--validate-only',action='store_true',help='Validate complete policy shape without connecting to the database.')

    def handle(self,*args,**options):
        try:
            with Path(options['policy']).open('rb') as source:raw=source.read(retention.MAX_POLICY_BYTES+1)
            policy=retention.parse_policy(raw)
            if options['validate_only']:
                result={'contract':retention.VERSION,'policy_shape_valid':True,'policy_authority_verified':False,
                        'status':'blocked','purge_available':False,'database_queried':False}
            else:result=retention.report(policy)
        except (OSError,ValueError,DatabaseError):
            # No filenames, SQL, policy values or database exception details in public output.
            raise CommandError('retention_readiness_refused; no deletion was attempted') from None
        self.stdout.write(json.dumps(result,sort_keys=True))
