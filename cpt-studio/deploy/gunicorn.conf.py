"""Gunicorn settings for the web role. The bind is inside the container; the
host publishes it on loopback only and host nginx is the sole client.

Release 2 (R2-5 to R2-8, D-R2-17): four sync processes, all forked from one
master that has loaded and warmed the application (cptstudio/wsgi.py,
cptstudio/warm.py), recycled every 10,000 requests or so. Nothing here imports
Django when the file is read: gunicorn reads it before it loads the application,
and the application's settings must be read after cptstudio/wsgi.py marks the
process as the web's."""
import gc

bind = '0.0.0.0:8000'
# R2-6: a page opens with two or three requests at once, so each gets a process
# and one is left for everyone else. Processes, not threads (measured, gthread
# refused): a sign-in's Argon2 takes about 100 MiB, so the number of processes
# bounds it; the timeout below ends a request that hangs, which a threaded
# worker's heartbeat does not; and a threaded worker dropped requests when it
# was recycled. Four keep the worst case - every process hashing a password -
# inside the container's memory limit (ops/install.py, WEB_LIMITS). The kept log
# names the class: ops/install.py keeps 'Using worker: sync', and a test ties
# that word to this one.
workers = 4
worker_class = 'sync'
timeout = 120
graceful_timeout = 30
keepalive = 5
# R2-5: the application is imported once, in the master, before any worker is
# forked; no request of a new worker waits for it, and the workers share it.
preload_app = True
# R2-8: each replacement is a fork of the warmed master, so a recycle costs a
# request nothing; the jitter keeps the four from being recycled together.
max_requests = 10000
max_requests_jitter = 1000

# The JSON API needs short request lines and few headers; refuse anything larger.
limit_request_line = 4094
limit_request_fields = 64
limit_request_field_size = 8190

# Heartbeat files on the in-memory /dev/shm: the root filesystem is read-only.
worker_tmp_dir = '/dev/shm'

accesslog = '-'
errorlog = '-'
# The path without its query string (%(U)s), and no Referer: either can carry
# identifiers. The client address is the one host nginx overwrote. Release 1
# (RELEASE-1-SPEC A2): nginx's request id, as its own access log has it, and the
# session reference the application names in its X-CPT-Actor answer header (a
# sign-in reference, never a name; nginx hides it from the browser). Each is '-'
# when absent: a direct probe of this port sends no request id.
access_log_format = ('%(t)s %({x-forwarded-for}i)s "%(m)s %(U)s %(H)s" %(s)s %(B)s %(M)sms '
                     '%({x-request-id}i)s %({x-cpt-actor}o)s')


def when_ready(server):
    """R2-5: the master has loaded the application and has forked no worker yet.
    Every database connection is closed - a worker forked with one would share it,
    which corrupts both sides - and the loaded objects leave the garbage
    collector's lists: no request then pays a full collection of them, and no
    collection writes to the memory pages the workers share with the master."""
    from django.db import connections

    connections.close_all()
    gc.collect()
    gc.freeze()


def post_worker_init(worker):
    """R2-5: each worker opens its own database connection before its first
    request. A database that does not answer yet is /health/'s to report, never a
    reason for a worker not to start: the first query connects again."""
    from django.db import connection

    try:
        connection.ensure_connection()
    except Exception:  # noqa: BLE001 - the worker serves without it; the next query connects
        pass
