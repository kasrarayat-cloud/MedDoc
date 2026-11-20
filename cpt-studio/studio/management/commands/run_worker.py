import signal
import threading

from django.core.management.base import BaseCommand

from studio import jobs

# How long the command waits for the heartbeat thread to see that the worker is done (it looks every 0.1 s).
HEARTBEAT_JOIN_SECONDS = 5


class Command(BaseCommand):
    help = ('Run the CPT Studio worker - CPT_STUDIO_CONCURRENT_DOCUMENTS threads, each on its own database connection - '
            'until SIGTERM/SIGINT (each thread finishes its current job first).')

    def add_arguments(self, parser):
        parser.add_argument('--poll-seconds', type=float, default=1.0)
        parser.add_argument('--threads', type=int, default=None,
                            help='Worker threads (default: settings.CONCURRENT_DOCUMENTS).')
        parser.add_argument('--once', action='store_true', help='Process queued jobs until none are left, then exit.')

    def handle(self, *args, **options):
        stopping = threading.Event()

        def request_stop(signum, frame):
            stopping.set()

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        # One heartbeat for the process: it beats at once and then every jobs.HEARTBEAT_SECONDS from a thread of its
        # own until the worker's threads are done - never until the stop is asked for: a SIGTERM lets each thread finish
        # its current job, and a worker finishing one is busy, not gone. `--once` beats the same way while it drains.
        done = threading.Event()
        jobs.beat()
        heartbeat = jobs.start_heartbeat(done.is_set)
        try:
            if options['once']:
                jobs.mark_stale()
                jobs.drain(stopping.is_set, threads=options['threads'], poll_seconds=options['poll_seconds'])
                return
            self.stdout.write('CPT Studio worker started.')
            jobs.work(stopping.is_set, poll_seconds=options['poll_seconds'], threads=options['threads'])
            self.stdout.write('CPT Studio worker stopped.')
        finally:
            done.set()
            heartbeat.join(timeout=HEARTBEAT_JOIN_SECONDS)
