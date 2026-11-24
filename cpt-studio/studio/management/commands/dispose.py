"""Destroy one document or a whole practice's data (release 1, D1; studio.disposal). A ruled act, run only through the
installer's --phase manage with a committed declaration (A6); never an HTTP route.

    dispose --close --workspace <id> --by <name> --reason-file F [--authorization-ref R]
        the practice closed: no new upload or coding; reading stays on.
    dispose --plan (--workspace <id> | --encounter <id>) --by <name> --reason-file F [--authorization-ref R]
        a dry run: counts per table, file counts and the files' sha256 manifest, recorded as a plan; nothing changes.
    dispose --execute --plan <plan id> --by <name> --approved-by <name> --authorization-ref R
        the plan carried out by two different people, and the destruction certificate printed for the receipt. A run
        that did not complete is recorded 'failed' with what it left, prints a certificate saying so and ends with an
        error; to finish it, remove what stopped it and plan the same scope again (a destroyed document may be planned
        again while its last run failed): the new plan takes in what the failed run left.
    dispose --ledger
        every DisposalEvent as a signed ledger line, to keep beside the backups.
    dispose --replay-ledger FILE [--execute --by <name> --approved-by <name> --authorization-ref R]
        after a restore from an older backup: what the ledger's disposals whose rows were destroyed ('completed', and
        'failed' ones) would destroy again (a dry run), or, with --execute, every entry's refusals checked first, then
        the ledger's missing rows written back and those disposals carried out again, entry by entry.

The reason is read from a file, never argv. Every line printed holds ids, counts, digests, fixed words, storage names
(random ids) and the names of the people who ran and approved the act; never a title, a file's own name, an answer or
document text. A refusal writes nothing and ends with an error saying nothing was destroyed - which is said only when it
is true: a replay that stops after it destroyed something says what it destroyed.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from studio import disposal

MODES = ('close', 'plan', 'execute', 'ledger', 'replay_ledger')


def _reason(path):
    if not path:
        raise CommandError('--reason-file is required.')
    try:
        return Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError) as exc:
        raise CommandError(f'The reason file cannot be read ({type(exc).__name__}).')


class Command(BaseCommand):
    help = "Close a practice, plan or execute the destruction of a document's or a practice's data, or replay the ledger."

    def add_arguments(self, parser):
        parser.add_argument('--close', action='store_true', help='Close the practice (--workspace).')
        parser.add_argument('--plan', nargs='?', const=True, default=None,
                            help='Alone: make a plan (a dry run). With --execute: the id of the plan to carry out.')
        parser.add_argument('--execute', action='store_true', help='Carry out a plan, or a ledger replay.')
        parser.add_argument('--ledger', action='store_true', help='Print every DisposalEvent as a signed ledger line.')
        parser.add_argument('--replay-ledger', default='', help='A ledger file to replay after a restore.')
        parser.add_argument('--workspace', default='', help="The practice's id.")
        parser.add_argument('--encounter', default='', help="The document's id.")
        parser.add_argument('--by', default='', help='The person who runs the act.')
        parser.add_argument('--approved-by', default='', help='The person who approves it (a destruction only).')
        parser.add_argument('--reason-file', default='', help='The reason, read from this file.')
        parser.add_argument('--authorization-ref', default='',
                            help='The ruled act this rests on (the committed declaration and its commit).')

    def handle(self, *args, **options):
        try:
            self._handle(options)
        except disposal.Refused as exc:  # raised only before anything was destroyed (studio.disposal)
            raise CommandError('Refused, nothing was destroyed: ' + ' '.join(exc.reasons))
        except disposal.NotDestroyed as exc:
            raise CommandError(str(exc))
        except disposal.Unrecorded as exc:
            self.stdout.write(exc.text)
            raise CommandError('The destruction ran, but its DisposalEvent could not be written: the certificate above is '
                               'its only record. Keep it with the receipt.')

    def _mode(self, options):
        plan = options['plan']
        chosen = [name for name, on in (('close', options['close']), ('plan', plan is True),
                                        ('execute', options['execute'] and not options['replay_ledger']),
                                        ('ledger', options['ledger']), ('replay_ledger', bool(options['replay_ledger'])))
                  if on]
        if len(chosen) != 1:
            raise CommandError('Choose one of --close, --plan, --execute --plan <id>, --ledger or --replay-ledger.')
        if isinstance(plan, str) and chosen != ['execute']:
            raise CommandError('--plan <id> names the plan --execute carries out.')
        if chosen == ['execute'] and not isinstance(plan, str):
            raise CommandError('--execute needs --plan <the plan id>.')
        return chosen[0]

    def _handle(self, options):
        mode = self._mode(options)
        if mode == 'close':
            if not options['workspace'] or options['encounter']:
                raise CommandError('--close takes --workspace <id>.')
            event = disposal.close(options['workspace'], by=options['by'], reason=_reason(options['reason_file']),
                                   authorization_ref=options['authorization_ref'])
            self.stdout.write(f'Closed practice {event.workspace_id} at {disposal.iso_time(event.created_at)}: no new upload '
                              f'or coding; reading stays on. DisposalEvent {event.pk} (closed).')
        elif mode == 'plan':
            self._plan(options)
        elif mode == 'execute':
            event, _ = disposal.execute(options['plan'], by=options['by'], approved_by=options['approved_by'],
                                        authorization_ref=options['authorization_ref'])
            self.stdout.write(disposal.certificate(event))
            if event.stage != disposal.DisposalEvent.COMPLETED:
                raise CommandError(f'The destruction did not complete (DisposalEvent {event.pk}, failed): see what '
                                   'remains above.')
        elif mode == 'ledger':
            for line in disposal.ledger_lines():
                self.stdout.write(line)
        else:
            self._replay(options)

    def _plan(self, options):
        if bool(options['workspace']) == bool(options['encounter']):
            raise CommandError('--plan takes --workspace <id> (a whole practice) or --encounter <id> (one document).')
        scope = (disposal.workspace_scope(options['workspace']) if options['workspace']
                 else disposal.document_scope(options['encounter']))
        event = disposal.plan(scope, by=options['by'], reason=_reason(options['reason_file']),
                              authorization_ref=options['authorization_ref'])
        rows = event.counts['rows']
        self.stdout.write(f'Plan {event.pk} for {scope.label()} ({event.counts["documents"]} document(s)); nothing was '
                          f'changed. Carry it out within {int(disposal.PLAN_MAX_AGE.total_seconds() // 3600)} hours with '
                          '--execute --plan <id>, run and approved by two different people.')
        self.stdout.write('Rows in scope: ' + ', '.join(f'{table} {count}' for table, count in sorted(rows.items())))
        files = event.files
        self.stdout.write(f'Files in scope: {files["files"]} ({files["bytes"]} bytes; {files["missing"]} missing); '
                          f'manifest sha256 {event.manifest_digest}')
        for entry in disposal.plan_manifest(event):
            self.stdout.write(f'  {entry["sha256"] or "missing":64}  {entry["bytes"] if entry["bytes"] is not None else "-"}'
                              f'  {entry["name"]}')
        if scope.kind == disposal.DOCUMENT:
            self.stdout.write(disposal.MISFILED_REMINDER)

    def _replay(self, options):
        try:
            lines = Path(options['replay_ledger']).read_text(encoding='utf-8').splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            raise CommandError(f'The ledger file cannot be read ({type(exc).__name__}).')
        report = disposal.replay(lines, execute_it=options['execute'], by=options['by'],
                                 approved_by=options['approved_by'], authorization_ref=options['authorization_ref'])
        for name in ('ledger_rows_restored', 'ledger_rows_missing'):
            if name in report:
                self.stdout.write(f'{name.replace("_", " ").capitalize()}: {report[name]}')
        for item in report['items']:
            if item['scope'] is None:
                self.stdout.write(f'Ledger entry {item["entry"]}: nothing of its scope exists in this database.')
                continue
            remains = item['remains']
            self.stdout.write(f'Ledger entry {item["entry"]} ({item["scope"].label()}): rows '
                              f'{sum(remains["rows"].values())}, documents not destroyed {remains["documents_alive"]}, '
                              f'files {"not listable" if remains["files"] is None else remains["files"]}, memberships on '
                              f'{remains["memberships_on"]}' + (f'; {item["status"]}' if options['execute'] else ''))
            if item['error']:
                self.stdout.write(f'  stopped here: {item["error"]}')
            if item['event'] is not None:
                self.stdout.write(disposal.certificate(item['event']))
            elif item['certificate']:
                self.stdout.write(item['certificate'])
        if not options['execute']:
            self.stdout.write('Dry run: nothing was changed. Replay with --execute, run and approved by two different '
                              'people, while the worker is stopped.')
            return
        done = [item for item in report['items'] if item['status'] in (disposal.DisposalEvent.COMPLETED,
                                                                        disposal.DisposalEvent.FAILED, 'unrecorded')]
        if report['stopped']:
            before = (f'{len(done)} ledger entr{"y was" if len(done) == 1 else "ies were"} carried out again before it '
                      '(certificates above)') if done else 'no entry was carried out again before it'
            later = sum(item['status'] == 'not attempted' for item in report['items'])
            raise CommandError(f'The replay stopped at ledger entry {report["stopped"]}: {before}; '
                               f'{later} later entr{"y was" if later == 1 else "ies were"} not attempted. Fix what stopped '
                               'it and replay the ledger again: entries already carried out are skipped.')
        failed = [item['entry'] for item in report['items'] if item['status'] == disposal.DisposalEvent.FAILED]
        if failed:
            raise CommandError(f'{len(failed)} replayed disposal(s) did not complete ({", ".join(failed)}): see their '
                               'certificates above.')
