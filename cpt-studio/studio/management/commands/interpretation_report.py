"""The D22 operator report on interpretation for a window, and the installer's self-test (design/FINAL.md 13; DECISIONS
D22; design/ADJUDICATION.md P-7):

    python manage.py interpretation_report --since 2026-11-10T09:00:00Z [--until <time>] [--self-test]
                                           [--expect-mode live] [--json]

It installs this process's legacy-call sentinel first (ADJUDICATION R-1: every process, one-shots included; a sentinel
already installed is left as it stands), then prints every D22 field for [since, until): the interpreter mode and model,
the Gemini runs (state, models, the paused ones, usage, estimated cost), the event inventories, the assessments by
engine version, the legacy calls their records count, the sentinel's trips, this process's sentinel and the interpreter
hold (studio.interpretation.report). Nothing is written and nothing is sent.

``--self-test`` adds the installer's checks (report.self_test); the exit status is 1 when one fails. The installer gives
``--since`` the new worker's start (P-7) and ``--expect-mode`` the mode it installed.
"""
import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import dateparse

from studio.interpretation import report, sentinel

MODES = ('disabled', 'replay', 'live')


def moment(value, name):
    """An ISO 8601 date and time with its offset (a 'Z' or '+00:00'); CommandError otherwise."""
    try:
        parsed = dateparse.parse_datetime(value or '')
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CommandError(f'--{name} must be an ISO 8601 date and time with its offset, such as '
                           '2026-11-10T09:00:00Z; nothing was read.')
    return parsed


class Command(BaseCommand):
    help = 'Print the D22 interpretation report for a window, and with --self-test the installer\'s checks.'

    def add_arguments(self, parser):
        parser.add_argument('--since', required=True, help='The window\'s start, ISO 8601 with its offset.')
        parser.add_argument('--until', default=None, help='The window\'s end (default: now).')
        parser.add_argument('--self-test', action='store_true', help='Add the installer\'s checks; exit 1 on a failure.')
        parser.add_argument('--expect-mode', choices=MODES, default=None,
                            help='With --self-test: the interpreter mode the installation must be in.')
        parser.add_argument('--json', action='store_true', help='Print one JSON document instead of text.')

    def handle(self, *args, **options):
        since = moment(options['since'], 'since')
        until = moment(options['until'], 'until') if options['until'] is not None else None
        if options['expect_mode'] and not options['self_test']:
            raise CommandError('--expect-mode goes with --self-test; nothing was read.')
        sentinel.install()
        try:
            found = report.window(since, until)
        except ValueError as exc:
            raise CommandError(f'{exc} Nothing was read.')
        test = report.self_test(found, expect_mode=options['expect_mode']) if options['self_test'] else None
        if options['json']:
            self.stdout.write(json.dumps({'report': found, 'self_test': test}, indent=2, sort_keys=True))
        else:
            for line in report.render(found, test):
                self.stdout.write(line)
        if test is not None and not test['passed']:
            failed = ', '.join(item['name'] for item in test['checks'] if not item['ok'])
            raise CommandError(f'The interpretation self-test failed: {failed}.')
