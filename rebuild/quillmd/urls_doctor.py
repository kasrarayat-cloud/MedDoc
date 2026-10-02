"""The doctor surface's URLconf: every route of quillmd.urls except the administration console.

core.middleware.AccessMiddleware resolves doctor-surface requests against this list (request.urlconf), so no console
view is routable there whatever the path rule decides — a SCRIPT_NAME, an encoding, or a route added later under
/console/ (inventory 7A, refutation R1/R2). The patterns are the SAME objects as quillmd.urls', not copies.
"""
from quillmd.urls import urlpatterns as _every_route

urlpatterns = [pattern for pattern in _every_route if not str(pattern.pattern).startswith('console')]
