"""Show the installation-wide provider holds of Corti, Astra and Fable, or release one provider's with a recorded note
(docs/gemini-migration/AMENDMENT-1.md 7.3, A16 and A20; adopted as DECISIONS D208; step 6b of its section 10).

``--status`` (or no option) prints every standing hold, per provider - installation-wide, from the stored rows: its
reason in words, the HTTP status the refusal carried, the run that set it and when - and the most recent releases;
nothing is written. A provider with none standing reads "no installation-wide hold", and nothing more: a request that
failed before is still held against its identical request (jobs._failed_before; amendment 7.3), which this command
does not list (refutation 6b-r2 F6, DECISIONS D247).

``--release <provider>`` ends every standing hold of that provider (``corti``, ``astra`` or ``fable``; Corti's replay
adapter is Corti's), each with a ProviderHoldRelease naming the operator (``--username``: an active account holding an
operator grant no revocation ended, as ``interpreter_hold`` requires) and the note - given as ``--note-file`` (read from
a file, so no prose passes through a shell) or as ``--note`` (the amendment's form). The hold rows stay. When no hold of
that provider stands, nothing is recorded and the command says so with a non-zero exit. After the release the next
member act - a Resume, or a save that queues the stage - sends the held request once; refused again, it sets a new hold
(7.3).

Every rule is studio.provider_holds' (the classification, the operator check, the note's bounds, a hold released by a
concurrent command never released twice); this command only reads its arguments and prints. No provider is called.
"""
from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError  # type: ignore[import-untyped]

from studio import models, provider_holds
from studio.management.commands.grant_operator import account

RECENT = 5


class Command(BaseCommand):  # type: ignore[misc]  # Django ships no type stubs
    help = ('Show the provider holds (--status), or release every standing hold of one provider with --release '
            '<corti|astra|fable> --username <operator> and --note-file <path> (or --note).')

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument('--status', action='store_true', help='Show every standing hold; nothing is written.')
        parser.add_argument('--release', default=None, metavar='PROVIDER',
                            help='End every standing hold of this provider (corti, astra or fable), with a note.')
        parser.add_argument('--username', default='', help='The operator recording the release.')
        note = parser.add_mutually_exclusive_group()
        note.add_argument('--note-file', default=None, help='A file holding the release note.')
        note.add_argument('--note', default=None, help='The release note.')

    def handle(self, *args: Any, **options: Any) -> None:
        if options['release'] is None:
            if options['username'] or options['note'] is not None or options['note_file'] is not None:
                raise CommandError('--username, --note and --note-file go with --release; nothing was recorded.')
            self.show()
            return
        if options['status']:
            raise CommandError('--status shows the holds and --release ends them: give one of them; nothing was '
                               'recorded.')
        provider = str(options['release']).strip()
        if not options['username']:
            raise CommandError('--release needs --username, the operator recording it; nothing was recorded.')
        if options['note'] is None and options['note_file'] is None:
            raise CommandError('--release needs --note-file or --note saying why the hold may end; nothing was '
                               'recorded.')
        note = options['note'] if options['note'] is not None else self.read_note(options['note_file'])
        user = account(options['username'])  # type: ignore[no-untyped-call]  # grant_operator is untyped
        try:
            released = provider_holds.release(provider, user=user, note=note)
        except (ValueError, PermissionError) as exc:
            raise CommandError(f'{exc} Nothing was recorded.')
        name = provider_holds.provider_of(provider) or provider
        if not released:
            raise CommandError(f'No {name} hold is standing; nothing was recorded.')
        for item in released:
            self.stdout.write(f'Released {describe(item.hold)} (release {item.pk}).')
        self.stdout.write(f'{len(released)} {name} hold{"s" if len(released) != 1 else ""} released by '
                          f'{user.username}. The next member act - a Resume, or a save that queues the stage - sends '
                          'the held request once.')

    @staticmethod
    def read_note(path: str) -> str:
        try:
            with open(path, encoding='utf-8') as handle:
                return handle.read()
        except (OSError, UnicodeDecodeError) as exc:
            raise CommandError(f'The note file cannot be read: {path} ({type(exc).__name__}); nothing was recorded.')

    def show(self) -> None:
        for name in provider_holds.PROVIDERS:
            standing = list(provider_holds.active(name))
            if not standing:  # D247 F6: no general claim about its requests - a failed request is held per request
                self.stdout.write(f'{name}: no installation-wide hold')
                continue
            self.stdout.write(f'{name} hold (installation-wide): {len(standing)} standing; no {name} request is sent by '
                              'any encounter until an operator releases it (a stored answer is still reused)')
            for hold in standing:
                self.stdout.write(f'  {describe(hold)}')
        releases = list(models.ProviderHoldRelease.objects.select_related('hold', 'released_by')
                        .order_by('-created_at', '-pk')[:RECENT])
        for item in releases:
            self.stdout.write(f'released: {item.hold.provider} hold {item.hold_id} ({item.hold.reason}) by '
                              f'{item.released_by.username} at {item.created_at.isoformat()}')


def describe(hold: Any) -> str:
    """One line for an operator: the hold, its reason in words, the status its refusal carried and the run that set it -
    provider_holds.as_json's fields, never the release note."""
    found = provider_holds.as_json(hold)
    status = f'HTTP {found["http_status"]}' if found['http_status'] is not None else 'no HTTP status'
    return (f'{found["provider"]} hold {found["id"]}: {found["reason"]} ({found["means"]}); {status}; set by run '
            f'{found["run"]} at {found["set_at"]}')
