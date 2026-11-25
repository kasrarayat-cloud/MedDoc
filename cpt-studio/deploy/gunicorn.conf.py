"""Gunicorn settings for the web role. The bind is inside the container; the
host publishes it on loopback only and host nginx is the sole client."""

bind = '0.0.0.0:8000'
workers = 2
worker_class = 'sync'
timeout = 120
graceful_timeout = 30
keepalive = 5
max_requests = 1000
max_requests_jitter = 100

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
