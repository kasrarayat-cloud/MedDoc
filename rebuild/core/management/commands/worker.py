import signal
import time
from django.core.management.base import BaseCommand
from core.jobs import run_one,mark_stale,reap_abandoned_voice_uploads
class Command(BaseCommand):
    help='Run private queue; graceful stop finishes the current provider request.'
    def add_arguments(self,p):p.add_argument('--once',action='store_true')
    def handle(self,*args,**options):
        stopping=False
        def stop(signum,frame):
            nonlocal stopping
            stopping=True
        signal.signal(signal.SIGTERM,stop)
        signal.signal(signal.SIGINT,stop)
        reaped_at=0.0
        while not stopping:
            mark_stale()
            if time.monotonic()-reaped_at>=60:
                reap_abandoned_voice_uploads(); reaped_at=time.monotonic()
            worked=run_one()
            if not worked:
                from core.preparation import run_one as prepare_one
                worked=prepare_one()
            if not worked:
                from core.semantic_preparation import run_one as define_one
                worked=define_one()
            if options['once']:return
            if not worked:time.sleep(2)
