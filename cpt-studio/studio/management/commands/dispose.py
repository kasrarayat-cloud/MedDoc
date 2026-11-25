"""Destroy one document or a whole practice's data (release 1, D1; studio.disposal). A ruled act, run only through the
installer's --phase manage with a committed declaration (A6); never an HTTP route.

    dispose --close --workspace <id> --by <name> --reason-file F [--authorization-ref R]
        the practice closed: no new upload or coding; reading stays on.
    dispose --plan (--workspace <id> | --encounter <id>) --by <name> --reason-file F [--authorization-ref R]
        a dry run: counts per table, file counts and the files' sha256 manifest, recorded as a plan; nothing changes.
    dispose --execute --plan <plan id> --by <name> --approved-by <name> --authorization-ref R
        the plan carried out by two different people, and the destruction certificate printed for the receipt. A run
        that did not complete is recorded 'failed' with what it left, prints a certificate saying so and ends with an
        error; one interrupted after its commit (Ctrl-C, or a stop signal: SIGTERM and SIGHUP) is recorded and printed
        the same way before the interrupt goes on - a stop signal ends the command with 128 + its number. Before a
        commit a stop signal or Ctrl-C raises where the command is, and nothing is destroyed; from the moment a commit
        begins it is held (studio.disposal.STOP_SIGNAL_HOLD: refutation round 2): the commit and the run's record go to
        their end, the steps after the commit stop at their next file or statement, and the command acts on it once it
        has printed what it recorded - a plan once its row is printed, before its manifest is read again; a replay
        before its next ledger entry (refutation round 3: STOP_SIGNAL_HOLD states the longest hold). Whatever happens
        after the commit, the destruction's 'committed' DisposalEvent, written in its own transaction, records it. To
        finish a run, remove what stopped it and plan the same scope again (a destroyed document may be planned again
        while any of its files remains or its last run did not complete): the new plan takes in what was left.
    dispose --ledger
        every DisposalEvent as a signed ledger line, to keep beside the backups.
    dispose --replay-ledger FILE [--execute --by <name> --approved-by <name> --authorization-ref R]
        after a restore from an older backup, BEFORE the site is opened: what the ledger's disposals whose rows were
        destroyed ('committed', 'completed', and 'failed' with rows destroyed 'yes') would destroy again (a dry run),
        or, with --execute, every entry's refusals checked first, then the ledger's missing rows written back and those
        disposals carried out again, entry by entry. A whole practice is destroyed again as a whole: a document added
        to the restored copy after the disposal is destroyed too, and counted. A 'failed' entry whose rows destroyed is
        'unknown' is never carried out again: unless its own 'committed' entry shows its commit happened, it is listed
        as a person's decision, and the person who decides to destroy it plans the same scope again and carries the
        plan out - the later entry that run writes is the one a replay carries out, and it marks the first decided.
        Exit status: 0 when everything was carried out; 3 (DECISION_EXIT) when the only thing left is an entry that
        needs a person's decision; any other non-zero status for a real failure.

The reason is read from a file, never argv, and printed only as its digest (studio.disposal.reason_digest: in each
certificate and ledger line; the DisposalEvent rows keep its text). Every line printed holds ids, counts, digests, fixed
words, storage names (random ids) and the names of the people who ran and approved the act; never a title, a file's own
name, an answer, a reason's words or document text. A refusal writes nothing and ends with an error saying nothing was
destroyed - which is said only when it is true: a replay that stops after it destroyed something says what it destroyed.
"""
import signal
import threading
from contextlib import contextmanager
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from studio import disposal

MODES = ('close', 'plan', 'execute', 'ledger', 'replay_ledger')
DECISION_EXIT = 3  # a replay whose only open item is an entry that needs a person's decision (Lane 6's contract)
STOP_SIGNALS = ('SIGTERM', 'SIGHUP')  # and Ctrl-C (SIGINT) while Python's own handler is the one in place
INTERRUPTED_TEXT = ("Interrupted once the destruction's commit was attempted: the certificate above records what it did "
                    'and what it left. To finish it, plan the same scope again and carry that plan out.')
HELD_TEXT = ('A stop signal came while the command recorded what it did: it was held until everything above was written, '
             'and ends the command now.')
DECIDE_TEXT = ("  whether its rows were destroyed is not known (its commit's answer was lost), so it is not carried out "
               'again: a person decides. To destroy what of it remains, plan it again (dispose --plan) and carry that '
               'plan out; a later replay carries out that run.')
CARRIED_OUT = (disposal.DisposalEvent.COMPLETED, disposal.DisposalEvent.FAILED, 'unrecorded')


class Stopped(KeyboardInterrupt):
    """A stop signal (SIGTERM: docker stop, a supervisor; SIGHUP: the terminal went away) raised where the command was,
    as Ctrl-C raises KeyboardInterrupt, so a destruction under way records what it did before the command ends - with
    128 + the signal's number, as a shell reports a process that signal ended (handle turns it into that exit).

    A KeyboardInterrupt itself (refutation dataloss-2), because psycopg cancels the statement in flight - a VACUUM
    waiting for a lock, a count - only for one: after any other exception libpq is left with that statement still
    running, every later statement of the run fails ('another command is already in progress'), and the run's 'failed'
    DisposalEvent could not be written. Cancelled, the connection answers again, and the run is recorded. Raised where
    the command is only before a commit (refutation round 2): from a commit on, a stop signal is held (_stop), so no
    interrupt goes through Django's commit or psycopg, and a statement in flight after the commit is cancelled by a
    cancel request instead; the held one is raised at the command's safe points - in Django's execute wrapper, before a
    statement after the commit is handed to psycopg (studio.disposal.StopSignalHold.before_statement), so never through
    psycopg, and once what it recorded is printed (refutation round 3)."""

    def __init__(self, signum):
        super().__init__(signal.Signals(signum).name)
        self.signum = signum


def _stop(signum, frame):
    """The handler of the stop signals and of Ctrl-C: held from a commit to the command's next safe point
    (disposal.STOP_SIGNAL_HOLD, refutation round 2), else raised where the command is - Stopped, or for Ctrl-C the
    KeyboardInterrupt Python's own handler raises."""
    interrupt = KeyboardInterrupt() if signum == signal.SIGINT else Stopped(signum)
    if disposal.STOP_SIGNAL_HOLD.keep(interrupt):
        return
    raise interrupt


def signal_status(interrupt):
    """The exit status a stop signal's interrupt ends the command with: 128 + the signal's number (Ctrl-C's: 130); None
    for anything else."""
    if isinstance(interrupt, Stopped):
        return 128 + interrupt.signum
    if isinstance(interrupt, KeyboardInterrupt):
        return 128 + signal.SIGINT
    return None


@contextmanager
def stop_signals_raise():
    """While the command runs, SIGTERM and SIGHUP - and Ctrl-C, while Python's own handler is the one in place - go to
    _stop instead of ending the process where it stands (in the main thread only: no other can set a signal handler),
    and disposal.STOP_SIGNAL_HOLD is armed; the handlers before are put back afterwards, held meanwhile, and the hold
    disarmed."""
    if threading.current_thread() is not threading.main_thread():
        yield
        return
    numbers = [number for number in (getattr(signal, name, None) for name in STOP_SIGNALS) if number is not None]
    if signal.getsignal(signal.SIGINT) is signal.default_int_handler:
        numbers.append(signal.SIGINT)
    previous = {}
    disposal.STOP_SIGNAL_HOLD.reset(armed=True)
    try:
        for number in numbers:
            previous[number] = signal.signal(number, _stop)
        yield
    finally:
        disposal.STOP_SIGNAL_HOLD.hold()  # the command is over: a signal now ends nothing more
        for number, handler in previous.items():
            signal.signal(number, handler)
        disposal.STOP_SIGNAL_HOLD.reset(armed=False)


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
        with stop_signals_raise():
            try:
                self._act(options)
                self._printed()  # everything recorded and printed: a stop signal held till now ends the command here
            except Stopped as exc:  # a stop signal ends the command with 128 + its number
                raise SystemExit(128 + exc.signum) from exc
            except KeyboardInterrupt:  # Ctrl-C ends it as Python ends it
                raise
            except BaseException as exc:  # anything else ends it as it is - with the status of a stop signal held
                status = signal_status(disposal.STOP_SIGNAL_HOLD.pending)
                if status is None or isinstance(exc, SystemExit):
                    raise
                if isinstance(exc, CommandError):
                    exc.returncode = status  # its message as Django prints it, and the signal's status
                    raise
                self.stderr.write(f'A stop signal came while the command recorded what it did, and it then ended on an '
                                  f'error ({type(exc).__name__}).')
                raise SystemExit(status) from exc

    def _printed(self):
        """A safe point of the command's (disposal.STOP_SIGNAL_HOLD.safe_point), once what it recorded is printed: a
        stop signal held since a commit ends the command here (HELD_TEXT first), and from here one raises at once."""
        if disposal.STOP_SIGNAL_HOLD.pending is not None:
            self.stderr.write(HELD_TEXT)
        disposal.STOP_SIGNAL_HOLD.safe_point()

    def _act(self, options):
        try:
            self._handle(options)
        except disposal.Refused as exc:  # raised only before anything was destroyed (studio.disposal)
            raise CommandError('Refused, nothing was destroyed: ' + ' '.join(exc.reasons))
        except disposal.NotDestroyed as exc:
            raise CommandError(str(exc))
        except disposal.Unrecorded as exc:
            self.stdout.write(exc.text)
            raise CommandError("The destruction ran, but its final DisposalEvent could not be written: its "
                               "'committed' DisposalEvent (named above) records the destruction, and the "
                               'certificate above what happened to its files. Keep it with the receipt.')
        except BaseException as exc:  # an interrupt after a destruction's commit brings its record: printed first
            certificate = getattr(exc, 'disposal_certificate', '')
            if certificate and getattr(exc, 'disposal_report', None) is None:
                self.stdout.write(certificate)
                self.stderr.write(INTERRUPTED_TEXT)
            raise

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
        # the plan's row committed and is printed, its manifest's digest with it: the hold is over (refutation round 3,
        # disposal-0). Reading and hashing every file again, for the lines below, is never held: a stop signal ends the
        # command at once, between two chunks of a file
        self._printed()
        for entry in disposal.plan_manifest(event):
            self.stdout.write(f'  {entry["sha256"] or "missing":64}  {entry["bytes"] if entry["bytes"] is not None else "-"}'
                              f'  {entry["name"]}')
        if scope.kind == disposal.DOCUMENT:
            self.stdout.write(disposal.MISFILED_REMINDER)

    def _replay(self, options):
        try:
            # line by line on the newline alone: a JSON string may hold U+2028, U+2029 or U+0085 raw (ledger_line writes
            # json.dumps(ensure_ascii=False)), which str.splitlines() would cut a genuine line at (refutation dataloss-0)
            lines = Path(options['replay_ledger']).read_text(encoding='utf-8').split('\n')
        except (OSError, UnicodeDecodeError) as exc:
            raise CommandError(f'The ledger file cannot be read ({type(exc).__name__}).')
        try:
            report = disposal.replay(lines, execute_it=options['execute'], by=options['by'],
                                     approved_by=options['approved_by'], authorization_ref=options['authorization_ref'])
        except BaseException as exc:  # an interrupt: what the replay did is printed, then the interrupt goes on
            report = getattr(exc, 'disposal_report', None)
            if report is None:
                raise
            self._report(report, options)
            self.stderr.write(self._stopped(report))
            raise
        self._report(report, options)
        if not options['execute']:
            self.stdout.write('Dry run: nothing was changed. Replay with --execute, run and approved by two different '
                              'people, while the worker is stopped.')
            return
        if report['stopped']:
            raise CommandError(self._stopped(report))
        problems = []
        failed = [item['entry'] for item in report['items'] if item['status'] == disposal.DisposalEvent.FAILED]
        if failed:
            problems.append(f'{len(failed)} replayed disposal(s) did not complete ({", ".join(failed)}): see their '
                            'certificates above.')
        undecided = [item['entry'] for item in report['items'] if item['status'] == disposal.DECIDE]
        if undecided:
            problems.append(f'{len(undecided)} ledger entr{"y needs" if len(undecided) == 1 else "ies need"} a person\'s '
                            f'decision ({", ".join(undecided)}): nothing of {"it" if len(undecided) == 1 else "them"} was '
                            'carried out again (see above).')
        if problems:  # exit 3 when a decision is all that is left; any other failure is a failure (1)
            raise CommandError(' '.join(problems), returncode=1 if failed else DECISION_EXIT)

    def _report(self, report, options):
        """The replay's report, entry by entry (ids, counts and statuses; certificates)."""
        for name in ('ledger_rows_restored', 'ledger_rows_missing'):
            if name in report:
                self.stdout.write(f'{name.replace("_", " ").capitalize()}: {report[name]}')
        for item in report['items']:
            if item['scope'] is None:
                self.stdout.write(f'Ledger entry {item["entry"]}: nothing of its scope exists in this database.')
                continue
            remains = item['remains']
            decision = item['status'] in (disposal.DECIDE, disposal.DECIDED)
            self.stdout.write(f'Ledger entry {item["entry"]} ({item["scope"].label()}): rows '
                              f'{sum(remains["rows"].values())}, documents not destroyed {remains["documents_alive"]}, '
                              f'files {"not listable" if remains["files"] is None else remains["files"]}, memberships on '
                              f'{remains["memberships_on"]}'
                              + (f'; {item["status"]}' if options['execute'] or decision else ''))
            if item['status'] == disposal.DECIDE:
                self.stdout.write(DECIDE_TEXT)
            elif item['status'] == disposal.DECIDED:
                self.stdout.write(
                    f"  its commit's answer was lost, but its own 'committed' entry {item['decided_by']} shows the commit "
                    'happened' if item.get('own_commit') else "  its commit's answer was lost; " + (
                        f'ledger entry {item["decided_by"]}, a later run of the same scope, decided it'
                        if item['decided_by'] else 'nothing of its scope remains'))
            if item.get('added'):
                count = item['added']
                done = options['execute'] and item['status'] in CARRIED_OUT
                verb = (('was' if count == 1 else 'were') + ' also destroyed' if done
                        else 'would also be destroyed' if not options['execute']
                        else ('is' if count == 1 else 'are') + ' in its scope too')
                self.stdout.write(f'  {count} document{"" if count == 1 else "s"} added after the disposal {verb}')
            if item['error']:
                self.stdout.write(f'  stopped here: {item["error"]}')
            if item['event'] is not None:
                self.stdout.write(disposal.certificate(item['event']))
            elif item['certificate']:
                self.stdout.write(item['certificate'])

    def _stopped(self, report):
        """Where the replay stopped: what the stopped entry did, how many entries were carried out before it, how many
        after it were not attempted."""
        items = report['items']
        stopped = next(item for item in items if item['entry'] == report['stopped'])
        done = sum(item is not stopped and item['status'] in CARRIED_OUT for item in items)
        own = {'unrecorded': "it was carried out again, but its final DisposalEvent could not be written (its "
                             "'committed' one and the certificate above are its record)",
               'refused': 'it was refused, and nothing of it was destroyed',
               'not destroyed': 'it rolled back, and nothing of it was destroyed',
               'error': 'it stopped on an error (logged), and whether it destroyed anything is not known',
               disposal.INTERRUPTED: ('it was interrupted after its commit (its certificate above says what it did and '
                                      'left)') if stopped['certificate'] else 'it was interrupted before its run was recorded',
               }[stopped['status']]
        before = (f'{done} ledger entr{"y was" if done == 1 else "ies were"} carried out again before it (certificates '
                  'above)') if done else 'no entry was carried out again before it'
        later = sum(item['status'] == 'not attempted' for item in items)
        return (f'The replay stopped at ledger entry {stopped["entry"]}: {own}; {before}; {later} later '
                f'entr{"y was" if later == 1 else "ies were"} not attempted. '
                + ('Replay the ledger again to go on' if stopped['status'] == disposal.INTERRUPTED
                   else 'Fix what stopped it and replay the ledger again')
                + ': entries already carried out are skipped.')
