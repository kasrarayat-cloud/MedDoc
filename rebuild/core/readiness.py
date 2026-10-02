"""Readiness: is this deployment able to do its work now? Liveness (/health/) only says the process answers.

GET /health/ready/ reports, as counts, ages and fixed labels (no patient data, no secret, no identifier):

- the single worker's heartbeat age: the worker records one ServiceHealth row ('worker_heartbeat') at most every
  HEARTBEAT_EVERY seconds from its loop (manage.py worker); never recorded counts as not ready;
- the queue: how many jobs are queued, and how long the oldest has waited;
- core.admin_console.processing_health's severity, the console's own verdict.

Each check, its threshold and the setting that overrides it are rows of ops/alarms.json (source 'readiness'), the same
table section 15 of docs/rebuild/v1/production-hosting.md states and its test reads. An unreadable database, a missing
alarm table or an invalid threshold setting answers not ready, never ready.

Exposure follows /health/: on the host only. The answer is given to a request that reached the application's loopback
port directly (the outside-host heartbeat, quillmd-production-heartbeat.sh); a request that came through the host proxy
carries the X-Real-IP/X-Forwarded-For headers nginx sets and is answered 404, as is any non-loopback peer.
"""
import json
import time
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone

ALARMS = Path(__file__).resolve().parents[1] / 'ops' / 'alarms.json'
HEARTBEAT_KEY = 'worker_heartbeat'
HEARTBEAT_EVERY = 30
LOOPBACK = ('127.0.0.1', '::1')
_last_beat = [0.0]


def alarms():
    """The readiness rows of the alarm table: {id: row}. Raises ValueError when the table is missing or malformed."""
    try:
        data = json.loads(ALARMS.read_text())
    except (OSError, ValueError) as exc:
        raise ValueError('alarm_table_unreadable') from exc
    if not isinstance(data, dict) or data.get('contract') != 'quillmd-alarms-v1' or not isinstance(data.get('alarms'), list):
        raise ValueError('alarm_table_malformed')
    rows = {row.get('id'): row for row in data['alarms'] if isinstance(row, dict) and row.get('source') == 'readiness'}
    if set(rows) != {'worker_heartbeat', 'oldest_queued_job', 'queue_depth', 'processing_health'}:
        raise ValueError('alarm_table_malformed')
    return rows


def threshold(row):
    """The row's setting when set (a whole number >= 1), otherwise its default. ValueError on an invalid value."""
    if row.get('setting') is None:
        return None
    raw = getattr(settings, row['setting'].removeprefix('QUILLMD_'), '')
    value = row['default'] if raw in ('', None) else raw
    if isinstance(value, bool) or not str(value).isdigit() or int(value) < 1:
        raise ValueError('threshold_invalid')
    return int(value)


def beat():
    """Record that the worker completed a loop pass. Throttled to one write per HEARTBEAT_EVERY seconds per process; a
    database error is the worker's own next pass to meet, never a reason to stop it."""
    now = time.monotonic()
    if _last_beat[0] and now - _last_beat[0] < HEARTBEAT_EVERY:
        return False
    from .models import ServiceHealth
    try:
        ServiceHealth.objects.update_or_create(key=HEARTBEAT_KEY, defaults={
            'condition': 'worker pass completed', 'severity': 'healthy', 'healthy': True, 'action': '',
            'payload': {}, 'computed_at': timezone.now(), 'expected_interval_seconds': 60})
    except DatabaseError:
        return False
    _last_beat[0] = now
    return True


def on_host(request):
    """Reached the loopback port directly: a loopback peer and none of the forwarding headers the host proxy sets."""
    meta = request.META
    return (meta.get('REMOTE_ADDR') in LOOPBACK and not meta.get('HTTP_X_REAL_IP')
            and not meta.get('HTTP_X_FORWARDED_FOR'))


def report(at=None):
    """{'ready': bool, 'checks': [...]} with counts, ages in whole seconds, thresholds and fixed labels only."""
    at = at or timezone.now()
    try:
        rows = alarms()
        limits = {key: threshold(row) for key, row in rows.items()}
    except ValueError as exc:
        return {'ready': False, 'reason': str(exc), 'checks': [], 'release': settings.RELEASE_SHA}
    try:
        from .admin_console import processing_health
        from .models import Job, ServiceHealth
        heartbeat = ServiceHealth.objects.filter(key=HEARTBEAT_KEY).values_list('computed_at', flat=True).first()
        queued = Job.objects.filter(state='queued')
        depth = queued.count()
        oldest = queued.order_by('created_at').values_list('created_at', flat=True).first()
        severity = processing_health(at)['severity']
    except DatabaseError:
        return {'ready': False, 'reason': 'database_unavailable', 'checks': [], 'release': settings.RELEASE_SHA}
    def age(moment):
        return None if moment is None else max(0, int((at - moment).total_seconds()))
    heartbeat_age, oldest_age = age(heartbeat), age(oldest)
    checks = [
        {'id': 'worker_heartbeat', 'value': heartbeat_age, 'threshold': limits['worker_heartbeat'], 'unit': 'seconds',
         'passed': heartbeat_age is not None and heartbeat_age <= limits['worker_heartbeat']},
        {'id': 'oldest_queued_job', 'value': oldest_age, 'threshold': limits['oldest_queued_job'], 'unit': 'seconds',
         'passed': oldest_age is None or oldest_age <= limits['oldest_queued_job']},
        {'id': 'queue_depth', 'value': depth, 'threshold': limits['queue_depth'], 'unit': 'jobs',
         'passed': depth <= limits['queue_depth']},
        {'id': 'processing_health', 'value': severity, 'threshold': None, 'unit': None, 'passed': severity != 'error'},
    ]
    return {'ready': all(check['passed'] for check in checks), 'checks': checks, 'release': settings.RELEASE_SHA}
