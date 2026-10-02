import signal
import time
from django.core.management.base import BaseCommand, CommandError
from core.jobs import run_one,mark_stale,reap_abandoned_voice_uploads
from core.readiness import beat
from core.redaction import sweep_left
class Command(BaseCommand):
    help=('Run private queue; graceful stop finishes the current provider request. Exactly one worker runs against a '
          'database: a second one refuses to start (core.worker_lock).')
    def add_arguments(self,p):p.add_argument('--once',action='store_true')
    def handle(self,*args,**options):
        from core.disposition import require_processing
        from core.worker_lock import WorkerRefused, acquire, refuse_nonzero_timeouts
        require_processing()
        # ⚠️ ONE WORKER, AND ONLY WITH ZERO TIMEOUTS, before anything is swept, reaped or sent (blockers.txt item 3). The
        # refusal exits non-zero with its reason; systemd's Restart=on-failure retries, so the worker of a rebuilt host
        # starts by itself once the old host's worker has stopped.
        try:
            refuse_nonzero_timeouts()
            lock=acquire()
        except WorkerRefused as exc:
            raise CommandError(str(exc)) from None
        try:
            self.serve(lock,options['once'])
        except WorkerRefused as exc:
            raise CommandError(str(exc)) from None
        finally:
            lock.release()
    def serve(self,lock,once):
        stopping=False
        def stop(signum,frame):
            nonlocal stopping
            stopping=True
        previous={number:signal.signal(number,stop) for number in (signal.SIGTERM,signal.SIGINT)}
        try:
            reaped_at=0.0
            while not stopping:
                # A lost lock (its session ended) stops the worker before the next sweep or request.
                lock.verify()
                mark_stale()
                if time.monotonic()-reaped_at>=60:
                    # A redacted document's bytes a failed unlink left here are swept again (refutation R3R-T5).
                    reap_abandoned_voice_uploads(); sweep_left(); reaped_at=time.monotonic()
                worked=run_one()
                # A completed pass is the worker's heartbeat (core.readiness; written at most every 30 s).
                beat()
                if once:return
                if not worked:time.sleep(2)
        finally:
            for number,handler in previous.items():signal.signal(number,handler)
