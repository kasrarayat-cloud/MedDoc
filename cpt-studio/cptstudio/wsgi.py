"""The web's entry point (deploy/entrypoint.sh: gunicorn cptstudio.wsgi). Release 2 (R2-5): gunicorn's master imports
it once, before it forks any worker (deploy/gunicorn.conf.py, preload_app), so what a first request would load is loaded
here and shared by every worker (cptstudio.warm). Nothing here opens a database connection or starts a thread
(specification 2.4)."""
import os

from django.core.wsgi import get_wsgi_application

from cptstudio.warm import warm_up

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cptstudio.settings')
# R2-7: the web alone keeps its database connections, with health checks (settings.DATABASES); only this module sets it,
# before the settings are read, and the worker and the commands never import it
os.environ.setdefault('CPT_STUDIO_WEB', '1')
application = get_wsgi_application()
warm_up()
