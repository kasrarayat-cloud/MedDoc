"""Show the installation-wide interpreter hold, or release it with a recorded note (design/FINAL.md 11.2; DECISIONS D11).

With no option it prints every standing hold - installation-wide, from the stored rows: its reason, the HTTP and vendor
status the answer carried, the run that set it - and the most recent releases; nothing is written. It prints its own
process's interpreter mode too, labelled as that: a one-shot runs with the interpreter disabled unless it is given a mode
(FINAL 13), so its mode is not the worker's.

``--release`` ends every standing hold, each with an InterpreterHoldRelease naming the operator (``--username``: an
active account holding an operator grant no revocation ended) and the note - given as ``--note-file`` (read from a file,
as the operator commands read their reasons, so no prose passes through a shell) or as ``--note`` (FINAL 11.2's form).
The hold rows stay. When no hold stands, nothing is recorded and the command says so with a non-zero exit. Members then
Resume.
"""
from django.core.management.base import BaseCommand, CommandError

from studio import models
from studio.interpretation import holds
from studio.management.commands.grant_operator import account

RECENT = 5


class Command(BaseCommand):
    help = ('Show the interpreter hold, or release every standing hold with --release --username <operator> and '
            '--note-file <path> (or --note).')

    def add_arguments(self, parser):
        parser.add_argument('--release', action='store_true', help='End every standing hold, recorded with a note.')
        parser.add_argument('--username', default='', help='The operator recording the release.')
        note = parser.add_mutually_exclusive_group()
        note.add_argument('--note-file', default=None, help='A file holding the release note.')
        note.add_argument('--note', default=None, help='The release note.')

    def handle(self, *args, **options):
        if not options['release']:
            if options['username'] or options['note'] is not None or options['note_file'] is not None:
                raise CommandError('--username, --note and --note-file go with --release; nothing was recorded.')
            self.show()
            return
        if not options['username']:
            raise CommandError('--release needs --username, the operator recording it; nothing was recorded.')
        if options['note'] is None and options['note_file'] is None:
            raise CommandError('--release needs --note-file or --note saying why the hold may end; nothing was '
                               'recorded.')
        note = options['note'] if options['note'] is not None else self.read_note(options['note_file'])
        user = account(options['username'])
        try:
            released = holds.release(user=user, note=note)
        except (ValueError, PermissionError) as exc:
            raise CommandError(f'{exc} Nothing was recorded.')
        if not released:
            raise CommandError('No interpreter hold is standing; nothing was recorded.')
        for item in released:
            self.stdout.write(f'Released {holds.describe(item.hold)} (release {item.pk}).')
        self.stdout.write(f'{len(released)} hold{"s" if len(released) != 1 else ""} released by {user.username}. '
                          'Members may now Resume.')

    @staticmethod
    def read_note(path):
        try:
            with open(path, encoding='utf-8') as handle:
                return handle.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise CommandError(f'The note file cannot be read: {path} ({type(exc).__name__}); nothing was recorded.')

    def show(self):
        standing = list(holds.active().select_related('run'))
        if not standing:
            self.stdout.write('interpreter hold (installation-wide): none standing; interpret stages are not held')
        else:
            self.stdout.write(f'interpreter hold (installation-wide): {len(standing)} standing; every interpret stage '
                              'sends nothing until an operator releases it')
            for hold in standing:
                self.stdout.write(f'  {holds.describe(hold)}')
        self.stdout.write(f'interpreter mode (this command\'s own process): {holds.mode()}; a one-shot runs with the '
                          'interpreter disabled unless it is given a mode, and the worker\'s own setting decides for '
                          'the worker')
        releases = list(models.InterpreterHoldRelease.objects.select_related('hold', 'released_by')
                        .order_by('-created_at', '-pk')[:RECENT])
        for item in releases:
            self.stdout.write(f'released: hold {item.hold_id} ({item.hold.reason}) by {item.released_by.username} '
                              f'at {item.created_at.isoformat()}')
