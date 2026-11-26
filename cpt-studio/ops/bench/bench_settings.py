"""The bench's servers (RELEASE-2-SPEC R2-2): the measured tree's OWN settings, with only the database name, the static
root and the originals folder pointed at the bench's throwaway copies. Never live (port 55451), never another database.

gunicorn and the walk's worker import this module through DJANGO_SETTINGS_MODULE=bench_settings, with the tree first on
PYTHONPATH, so `cptstudio.settings` below is the tree's own: whatever a release changes there (connection age, health
checks, the web flag its wsgi.py sets) is what is measured. Nothing else is overridden.

BENCH_GC_LOG (the cold part only): each process appends one line per garbage collection of 1 ms or more,
"<pid> <generation> <ms> <epoch seconds>", so the longest pause in a window of requests is read from the tree's own
processes. The hook is the same for every tree and is installed only when the variable is set.
"""
import os
from pathlib import Path

from cptstudio.settings import *  # noqa: F401,F403 - the measured tree's settings, unchanged
from cptstudio.settings import CODING_MODE, DATABASES


def _refuse(why):
    raise RuntimeError(f'bench_settings refused: {why}')


_NAME = os.environ.get('BENCH_DB', '')
if not _NAME.startswith('test_cptstudio_'):
    _refuse('BENCH_DB must name a test_cptstudio_ database')
if DATABASES['default'].get('HOST') != '127.0.0.1' or str(DATABASES['default'].get('PORT')) != '55461':
    _refuse('the database must be the throwaway server at 127.0.0.1:55461')
if CODING_MODE != 'disabled':
    _refuse('CODING_MODE must be disabled')
DATABASES['default']['NAME'] = _NAME
STATIC_ROOT = Path(os.environ['BENCH_STATIC'])
ORIGINALS_DIR = Path(os.environ['BENCH_ORIGINALS'])

_GC_LOG = os.environ.get('BENCH_GC_LOG', '')
if _GC_LOG:
    import gc
    import time

    _started = {}

    def _bench_gc_pause(phase, info):
        if phase == 'start':
            _started['at'] = time.perf_counter()
            return
        began = _started.pop('at', None)
        if began is None:
            return
        ms = (time.perf_counter() - began) * 1000
        if ms >= 1.0:
            with open(_GC_LOG, 'a', encoding='ascii') as handle:
                handle.write(f'{os.getpid()} {info.get("generation")} {ms:.2f} {time.time():.3f}\n')

    gc.callbacks.append(_bench_gc_pause)
