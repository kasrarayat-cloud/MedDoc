"""The walk's worker (RELEASE-2-SPEC R2-32, the walk part): the measured tree's own `run_worker` over the tree's own
fake coder (tests.support), which answers synthetic reader and checker messages. Every stage but the paid send is the
shipped code; nothing is sent to any vendor: the coder object is replaced before the worker starts, and bench_settings
refuses any CODING_MODE but 'disabled'.

    DJANGO_SETTINGS_MODULE=bench_settings PYTHONPATH=<tree>:<this folder> python -B bench_worker.py

(bench_run.py starts it, with the round's database and originals folder in BENCH_DB and BENCH_ORIGINALS.)
"""
import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'bench_settings'

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from studio.fable import client as fable_client  # noqa: E402
from tests.support import coding as fake_coding, rounds as fake_rounds  # noqa: E402

BENCH_CODER = fake_coding.FakeCoder(
    reader=lambda request: fake_coding.succeeded(fake_rounds.reader_message(fake_rounds.READER)),
    checker=lambda request: fake_coding.succeeded(fake_rounds.checker_message(fake_rounds.CHECKER)))
fable_client.coder = lambda *args, **kwargs: BENCH_CODER

if __name__ == '__main__':
    call_command('run_worker', threads=1, poll_seconds=0.3)
