import signal
import time
from django.core.management.base import BaseCommand
from core.jobs import run_one,mark_stale
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
        while not stopping:
            mark_stale()
            worked=run_one()
            if options['once']:return
            if not worked:time.sleep(2)
