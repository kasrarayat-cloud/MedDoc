"""The web's entry point (deploy/entrypoint.sh: gunicorn cptstudio.wsgi). Release 2 (R2-5): gunicorn's master imports
it once, before it forks any worker (deploy/gunicorn.conf.py, preload_app), so what a first request would load is loaded
here and shared by every worker (cptstudio.warm). Nothing here opens a database connection or starts a thread
(specification 2.4)."""
import os
import sys

from django.core.wsgi import get_wsgi_application

from cptstudio.warm import warm_up

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cptstudio.settings')
# R2-7: the web alone keeps its database connections, with health checks (settings.DATABASES); only this module sets it,
# before the settings are read, and the worker and the commands never import it
os.environ.setdefault('CPT_STUDIO_WEB', '1')
# With preload_app gunicorn's master imports this module before it writes a line of its own, so a web whose application
# cannot load - a setting its environment refuses, a part of the warm-up that cannot load - would leave no line the
# installer keeps (ops/install.py KEPT_LOG_FORMATS['web']; refutation round 1). One fixed line says so, never the
# error's text (which can quote a setting or a path), and the error is raised again: the web does not start.
try:
    application = get_wsgi_application()
    warm_up()
except Exception:
    print('CPT Studio web: the application could not be loaded.', file=sys.stderr, flush=True)
    raise
