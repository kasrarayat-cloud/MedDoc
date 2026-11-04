import signal
import threading

from django.core.management.base import BaseCommand

from studio import jobs

# How long the command waits for the heartbeat thread to see that the worker is done (it looks every 0.1 s).
HEARTBEAT_JOIN_SECONDS = 5


class Command(BaseCommand):
    help = 'Run the CPT Studio pipeline worker until SIGTERM/SIGINT (the current stage finishes first).'

    def add_arguments(self, parser):
        parser.add_argument('--poll-seconds', type=float, default=1.0)
        parser.add_argument('--once', action='store_true', help='Process queued jobs until none are left, then exit.')

    def handle(self, *args, **options):
        stopping = {'flag': False}

        def request_stop(signum, frame):
            stopping['flag'] = True

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)
        # Decision (j): the process beats at once and then every jobs.HEARTBEAT_SECONDS from a thread of its own, so the
        # progress panel can tell a worker that is gone from one that is busy with a long stage. The thread beats until
        # this process is done working - its loop has returned - never until the stop is asked for: a SIGTERM (the
        # installer's `docker stop`) lets the current stage finish, and a worker finishing it is busy, not gone
        # (refutation r2, L5-2). `--once` beats the same way while it drains the queue (L5-6).
        done = threading.Event()
        jobs.beat()
        heartbeat = jobs.start_heartbeat(done.is_set)
        try:
            if options['once']:
                jobs.mark_stale()
                while not stopping['flag']:
                    job = jobs.claim_next()
                    if job is None:
                        break
                    jobs.run_job(job)
                return
            self.stdout.write('CPT Studio worker started.')
            jobs.work(lambda: stopping['flag'], poll_seconds=options['poll_seconds'])
            self.stdout.write('CPT Studio worker stopped.')
        finally:
            done.set()
            heartbeat.join(timeout=HEARTBEAT_JOIN_SECONDS)
