"""Two-custodian redaction of one unfinalized document's clinical content (core.redaction). An irreversible act: run it
through scripts/run-ruled-mutation.sh with a committed declaration, like every other ruled deletion.

    manage.py redaction request --custodian <email> --document <encounter id> --reason-sha256 <authority hash> \
        --request-key <uuid>
    manage.py redaction execute --custodian <second custodian email> --request <request id> \
        --checkpoint <signed checkpoint JSON file>
    manage.py redaction journal-releases --custodian <email> --document <encounter id>

'journal-releases' clears the 'hold_release_not_journaled' refusal: it journals, from each release's own recorded evidence,
every committed release of a hold in the document's scope that the independent journal lacks (any active custodian).

Output carries ids, digests and counts only; never clinical text, file paths or the reason itself.
"""
import json
from pathlib import Path

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError

from core import disposition_policy as p, redaction
from core.models import User


class Command(BaseCommand):
    help = 'Request (first custodian) or execute (second custodian) the redaction of one unfinalized document.'

    def add_arguments(self, parser):
        parser.add_argument('action', choices=('request', 'execute', 'journal-releases'))
        parser.add_argument('--custodian', required=True, help='Email of the verified administrator acting.')
        parser.add_argument('--document')
        parser.add_argument('--reason-sha256')
        parser.add_argument('--request-key')
        parser.add_argument('--request')
        parser.add_argument('--checkpoint', help='File holding the independently signed journal checkpoint.')

    def handle(self, *args, **options):
        actor = User.objects.filter(email__iexact=options['custodian']).first()
        try:
            if options['action'] == 'journal-releases':
                if not options['document']:
                    raise CommandError('journal-releases needs --document.')
                result = {'journaled_releases': redaction.journal_pending_releases(actor, options['document'])}
            elif options['action'] == 'request':
                if not (options['document'] and options['reason_sha256'] and options['request_key']):
                    raise CommandError('request needs --document, --reason-sha256 and --request-key.')
                row = redaction.request(actor, options['document'], options['reason_sha256'], options['request_key'])
                result = {'requested': True, 'request': str(row.pk), 'content_sha256': row.content_sha256}
            else:
                if not (options['request'] and options['checkpoint']):
                    raise CommandError('execute needs --request and --checkpoint.')
                with Path(options['checkpoint']).open('rb') as stream:
                    checkpoint = p.decode(stream.read(p.MAX_BYTES + 1))
                tombstone = redaction.execute(actor, options['request'], checkpoint)
                result = {'redacted': True, 'tombstone': str(tombstone.pk), 'journal_sha256': tombstone.entry_sha256,
                          'files': len(tombstone.files)}
        except OSError:
            raise CommandError('The checkpoint file could not be read.') from None
        except (ValidationError, PermissionDenied) as error:
            raise CommandError(' '.join(getattr(error, 'messages', None) or [str(error)])) from None
        self.stdout.write(json.dumps(result, sort_keys=True))
