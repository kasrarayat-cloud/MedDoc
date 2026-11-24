"""A document's record bundle for its practice (release 1, D2; RELEASE-1-SPEC 3.4): GET /api/encounters/<id>/bundle, a
zip of the original, its converted PDF, the latest report, record.json and a manifest. Lane 1 routes it, and the view is
a stub that answers Django's 404 - so a half-merged main exposes nothing - until Lane 4 replaces it."""
from django.http import Http404
from django.views.decorators.common import no_append_slash
from django.views.decorators.csrf import csrf_exempt


# R1 stub: Lane 4 replaces this (D2)
@csrf_exempt
@no_append_slash
def encounter_bundle(request, *args, **kwargs):
    raise Http404()
