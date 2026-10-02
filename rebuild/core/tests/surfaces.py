"""A test client for the two surfaces production runs (inventory 7A, F1).

QuillMD runs two processes: the doctor surface (QUILLMD_ADMIN_SITE=0) and the administration surface
(QUILLMD_ADMIN_SITE=1). The console exists on the administration surface only: on the doctor surface the access
middleware answers every `/console/` request 404 (core.middleware). Tests of console BEHAVIOUR therefore send their
console requests to the administration surface, as a browser would reach admin.quillmd.com, and every other request to
whatever surface the test configured. `core.tests.test_console_surface` proves the doctor surface refuses the console;
this client keeps the console's own tests about the console.

The surface is answered PER THREAD, to the access middleware only. `override_settings` is process-global, and the
lock-order tests (core.tests.test_retention_flow_locks) run a console request and a doctor request in two threads at
once: a global ADMIN_SITE=True would have answered the doctor's concurrent upload 404. The middleware reads its
settings through a proxy installed here, which returns the real `django.conf.settings` value — overrides included —
for every attribute, and ADMIN_SITE=True only on a thread that is serving a SurfaceClient console request.
"""
import threading

from django.conf import settings as django_settings
from django.test import Client

from core import middleware


class _Surface(threading.local):
    admin = None


_surface = _Surface()


class _SurfaceSettings:
    def __getattr__(self, name):
        if name == 'ADMIN_SITE' and _surface.admin is not None:
            return _surface.admin
        return getattr(django_settings, name)


if not isinstance(middleware.settings, _SurfaceSettings):
    middleware.settings = _SurfaceSettings()


class SurfaceClient(Client):
    """Serves a request under /console/ as the administration surface; any other request is unchanged."""

    def request(self, **request):
        if not request.get('PATH_INFO', '').startswith('/console/'):
            return super().request(**request)
        previous, _surface.admin = _surface.admin, True
        try:
            return super().request(**request)
        finally:
            _surface.admin = previous
