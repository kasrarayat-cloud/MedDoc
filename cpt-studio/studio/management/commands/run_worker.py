import signal

from django.core.management.base import BaseCommand

from studio import jobs


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
        if options['once']:
            jobs.mark_stale()
            while not stopping['flag']:
                job = jobs.claim_next()
                if job is None:
                    break
                jobs.run_job(job)
            return
        self.stdout.write('CPT Studio worker started.')
        # decision (j): the process beats at once and then every jobs.HEARTBEAT_SECONDS from a thread of its own, so the
        # progress panel can tell a worker that is gone from one that is busy with a long stage
        jobs.beat()
        jobs.start_heartbeat(lambda: stopping['flag'])
        jobs.work(lambda: stopping['flag'], poll_seconds=options['poll_seconds'])
        self.stdout.write('CPT Studio worker stopped.')
