"""A document's record bundle for its practice (release 1, D2; RELEASE-1-SPEC 3.4): GET /api/encounters/<id>/bundle, a
zip of the original, its converted PDF, the latest report, record.json and a manifest (studio.record_bundle).

A browser download, like the original's: outside the client contract (studio.client_contract), sign-in required (401),
GET only (HEAD and every other method 405). In order:

1. the document must exist and not be destroyed (404 otherwise, no record: there is nothing to read);
2. the caller must hold an active membership of its practice - else the same 404 as an unknown id, and an AccessRecord
   member.bundle_download with outcome refused, which shows probing (C1 item 6, TEC-10); a refused row that cannot be
   written still answers that 404, so the answer never tells whether the document exists;
3. the bundle limit (C5; settings.BUNDLE_LIMIT_PER_MEMBER, OWNER DECISION D8): over it, 429
   {"error": "rate_limited", "retry_after": s} with Retry-After, and the first refusal of a window writes one
   SecurityEvent bundle.rate_limited;
4. the bundle is built in memory: over settings.BUNDLE_MAX_BYTES, 413 with record_bundle.TOO_LARGE; a stored file that
   cannot be read back unchanged, 409;
5. the read is recorded (read_audit.record, member.bundle_download, the document's id) before any byte is sent: a row
   that cannot be written answers 503 read_audit.NOT_RECORDED and serves nothing (fail closed) - one whose write met a
   lost connection is answered as a database that cannot be reached, the same 503 with Retry-After (studio.
   db_unavailable; integrated refutation round 2, I2-4);
6. the zip, as an attachment named by the document's id - never its title.
"""
import functools
import math
from datetime import timedelta

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from . import db_unavailable, models, rate, read_audit, record_bundle, security_events
from .access import active_membership
from .fable.document import STORAGE_TEXT
from .storage import OriginalCorrupted

RATE_SCOPE = 'bundle.member'
LIMITED_EVENT = 'bundle.rate_limited'
SIGN_IN = {'error': 'Sign in to continue.'}
NOT_FOUND = {'error': 'Not found.'}


def _signed_in(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(SIGN_IN, status=401)
        return view(request, *args, **kwargs)
    return wrapper


def _refused(request, encounter):
    """The refused read's row (a member asking for another practice's document); never an answer of its own."""
    try:
        read_audit.record(request, view=read_audit.MEMBER_BUNDLE_DOWNLOAD, workspace_id=encounter.workspace_id,
                          encounter_ids=[encounter.pk], outcome=read_audit.REFUSED)
    except read_audit.NotRecorded:
        pass  # the same 404 either way: whether the row was written must not show whether the document exists


def _limited(user, workspace_id):
    """None under the member's bundle limit, else the 429 (its first refusal in a window writes a SecurityEvent)."""
    limit, window = settings.BUNDLE_LIMIT_PER_MEMBER
    count = rate.hit(RATE_SCOPE, str(user.pk), window_seconds=window)
    if count <= limit:
        return None
    ends = rate.window_start(window) + timedelta(seconds=window)
    retry_after = max(1, math.ceil((ends - timezone.now()).total_seconds()))
    if count == limit + 1:
        security_events.record(LIMITED_EVENT, actor=user, workspace_id=workspace_id, limit=limit,
                               window_seconds=window)
    response = JsonResponse({'error': 'rate_limited', 'retry_after': retry_after}, status=429)
    response['Retry-After'] = str(retry_after)
    return response


@read_audit.phi_read(read_audit.MEMBER_BUNDLE_DOWNLOAD)
@require_GET
@_signed_in
def encounter_bundle(request, encounter_id):
    encounter = models.Encounter.objects.select_related('workspace').filter(pk=encounter_id).first()
    if encounter is None or encounter.destroyed_at is not None:
        return JsonResponse(NOT_FOUND, status=404)
    try:
        membership = active_membership(request.user, encounter.workspace_id)
    except Http404:
        _refused(request, encounter)
        return JsonResponse(NOT_FOUND, status=404)
    limited = _limited(request.user, encounter.workspace_id)
    if limited is not None:
        return limited
    now = timezone.now()
    try:
        data = record_bundle.bundle(encounter, membership, now=now)
    except record_bundle.TooLarge:
        return JsonResponse({'error': record_bundle.TOO_LARGE, 'details': {}}, status=413)
    except (OriginalCorrupted, OSError):
        return JsonResponse({'error': STORAGE_TEXT, 'details': {}}, status=409)
    try:
        read_audit.record(request, view=read_audit.MEMBER_BUNDLE_DOWNLOAD, workspace_id=encounter.workspace_id,
                          encounter_ids=[encounter.pk])
    except read_audit.NotRecorded as refused:
        db_unavailable.raise_if_lost(refused)  # a lost connection: the 503 with Retry-After (I2-4)
        return JsonResponse({'error': read_audit.NOT_RECORDED}, status=503)
    response = HttpResponse(data, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="cpt-studio-document-{encounter.pk}.zip"'
    return response
