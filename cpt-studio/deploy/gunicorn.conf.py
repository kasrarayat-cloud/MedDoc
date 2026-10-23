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
# identifiers. The client address is the one host nginx overwrote.
access_log_format = '%(t)s %({x-forwarded-for}i)s "%(m)s %(U)s %(H)s" %(s)s %(B)s %(M)sms'
