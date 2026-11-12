"""Platform-operator diagnostics (CORE-UX-DESIGN.md 5; R4-api-leak-surface 6.2, 6.4).

An operator is a user holding an OperatorGrant that no OperatorRevocation ended - nothing else. No workspace role
confers it (a practice owner is not an operator) and nothing here reads a Membership to decide it. Grants are recorded
by the ``grant_operator`` management command only, never over HTTP.

Every URL under /ops/ answers anyone who is not an operator - signed out, a member of any role, the owner of any
workspace, a revoked operator - exactly what an unknown URL answers (Django's 404), so the surface's existence is not
disclosed (access.py's policy, never a 403). For an operator they serve the complete provenance the customer surface
leaves out: today's full encounter serializer (studio.serializers), the administrative trace, every report artifact
as stored with its sha256, the original with its sha256, the operator report and the reconciliation of an unknown
outcome. An operator's page and API reads of an encounter are audited as ``operator.viewed`` (never shown to
customers: their activity is an allowlist, customer_api.ACTIVITY).

The operator console is today's website, frozen: ``studio/operator/ops.js`` (a copy of ``studio/static/studio/app.js``
with its API base switched to /ops/api/) and ``studio/operator/ops.css`` (a copy of its stylesheet), served by a gated
view and never from ``static/`` (WhiteNoise serves that tree to anyone). It is read-only but for the operator report
and the reconciliation: the customer actions (decisions, context, addenda, stop, resume, the second review) are not
under /ops/, so the console's buttons for them answer 404 there.
"""
import functools
import re
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from . import audit, models

ASSETS = Path(__file__).resolve().parent / 'operator'
ASSET_TYPES = {'ops.js': 'text/javascript; charset=utf-8', 'ops.css': 'text/css; charset=utf-8'}
VIEWED = 'operator.viewed'
# One audit row per operator, encounter and view within this window: the console polls an encounter that is
# processing, and each poll is not a new act of looking.
VIEW_AUDIT_WINDOW = timedelta(minutes=10)
MAX_REASON_CHARS = 2000
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')


# --- who is an operator -------------------------------------------------------------------------------------------

def active_grant(user):
    """The user's operator grant that no revocation ended (the oldest), or None. Reads no Membership."""
    if user is None or not getattr(user, 'pk', None):
        return None
    return (models.OperatorGrant.objects.filter(user_id=user.pk, revocation__isnull=True)
            .order_by('created_at', 'pk').first())


def is_operator(user) -> bool:
    """Whether ``user`` is a platform operator now: signed in, active, and holding a grant no revocation ended. A workspace
    role never makes one, and no Membership is read."""
    if not getattr(user, 'is_authenticated', False) or not getattr(user, 'is_active', False):
        return False
    return models.OperatorGrant.objects.filter(user_id=user.pk, revocation__isnull=True).exists()


def clean_reason(text) -> str:
    """A grant's or revocation's reason as recorded: the file's text, stripped; refused when empty, too long or not
    storable (PostgreSQL text holds no NUL)."""
    reason = str(text or '').strip()
    if not reason:
        raise ValueError('The reason file is empty.')
    if len(reason) > MAX_REASON_CHARS:
        raise ValueError(f'The reason can be at most {MAX_REASON_CHARS} characters.')
    if UNSTORABLE.search(reason):
        raise ValueError('The reason contains a NUL character or an invalid Unicode code point.')
    return reason


def grant(user, reason, granted_by):
    """Record a grant for ``user`` (the management command's one write). (grant, created): an operator who already holds
    a grant keeps it and nothing is written."""
    existing = active_grant(user)
    if existing is not None:
        return existing, False
    return models.OperatorGrant.objects.create(user=user, reason=clean_reason(reason),
                                               granted_by=str(granted_by or '')[:120]), True


def revoke(user, reason, revoked_by):
    """End every grant of ``user`` that no revocation ended; the revocations recorded (none when there was none)."""
    reason = clean_reason(reason)
    out = []
    for item in models.OperatorGrant.objects.filter(user_id=user.pk, revocation__isnull=True).order_by('created_at'):
        out.append(models.OperatorRevocation.objects.create(grant=item, reason=reason,
                                                            revoked_by=str(revoked_by or '')[:120]))
    return out


@dataclass(frozen=True)
class ReadOnlyAccess:
    """What the operator serializer is given in place of a membership for an operator who is not a member of the
    encounter's workspace: it allows no review action, no stop or resume and no second-review ask."""
    user_id: object
    workspace_id: object
    active: bool = True
    role: str = 'operator'
    can_review: bool = False


def access_for(user, encounter):
    """The operator's own active membership of the encounter's workspace when they hold one - the payload is then what
    serializers.encounter_detail always gave that member - else read-only access."""
    membership = (models.Membership.objects.select_related('workspace').filter(
        user=user, workspace_id=encounter.workspace_id, active=True).first())
    return membership or ReadOnlyAccess(user_id=user.pk, workspace_id=encounter.workspace_id)


def record_view(user, encounter, view, **data):
    """Audit an operator's read of ``encounter`` as operator.viewed - once per operator, encounter and view within
    VIEW_AUDIT_WINDOW."""
    since = timezone.now() - VIEW_AUDIT_WINDOW
    if models.AuditEvent.objects.filter(event=VIEWED, encounter=encounter, actor=user, created_at__gte=since,
                                        data__view=view).exists():
        return None
    return audit.record(encounter.workspace, VIEWED, encounter=encounter, actor=user, view=view, **data)


# --- the gate -----------------------------------------------------------------------------------------------------

def _as_an_unknown_url(request):
    """Leave ``request``'s session exactly as an unknown URL leaves it - never read: the gate had to read it to know the
    user, and SessionMiddleware answers a request whose session was read with "Vary: Cookie" (and deletes a stale
    session cookie it loaded), which an unknown URL's 404 never carries. So the session is handed back unread, keyed by
    the cookie the request brought, as SessionMiddleware made it."""
    if hasattr(request, 'session'):
        store = import_module(settings.SESSION_ENGINE).SessionStore
        request.session = store(request.COOKIES.get(settings.SESSION_COOKIE_NAME))


def operator_view(view):
    """Anyone who is not an operator gets exactly what an unknown URL gets - Django's 404, its body and its headers -
    before the method, the body, the CSRF token or the record is read; an operator gets the view.

    Refutation round 2, L4-2 and L4-3: Django resolves a URL before CsrfViewMiddleware runs, and an unknown URL stops
    there, so a CSRF check run before this gate answered every non-operator's POST to a real route 403 where an unknown
    URL answers 404; reading the session for the gate added "Vary: Cookie"; and CommonMiddleware redirected /ops to
    /ops/. So the global CSRF check is skipped here (csrf_exempt) and the same check (csrf_protect) runs after the gate,
    for operators only - their writes still need the token -, the session is handed back unread to a non-operator, and
    no operator URL is reached by appending a slash."""
    protected = csrf_protect(view)

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_operator(request.user):
            _as_an_unknown_url(request)
            raise Http404()
        return protected(request, *args, **kwargs)
    wrapper.csrf_exempt = True  # the CSRF check is the operator's, after the gate (csrf_protect above)
    wrapper.should_append_slash = False  # /ops answers what /opsx answers (CommonMiddleware's APPEND_SLASH)
    return wrapper


def _methods(*allowed):
    def decorate(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in allowed:
                return JsonResponse({'error': 'Method not allowed.'}, status=405, headers={'Allow': ', '.join(allowed)})
            return view(request, *args, **kwargs)
        return wrapper
    return decorate


def operator_api(*allowed):
    """An operator JSON endpoint: the gate first (operator_view), then the method, then the API's error handling with the
    full wording (this is the diagnostics surface: an operator reads what the stage or the adapter said)."""
    from .api import ApiError  # local import: api imports the customer layer, which imports this module

    def decorate(view):
        @functools.wraps(view)
        def handled(request, *args, **kwargs):
            try:
                return view(request, *args, **kwargs)
            except ApiError as exc:
                return JsonResponse({'error': exc.message, 'details': exc.details}, status=exc.status)
            except Http404:
                return JsonResponse({'error': 'Not found.'}, status=404)
            except PermissionDenied as exc:
                return JsonResponse({'error': str(exc) or 'Not allowed.'}, status=403)
            except ValidationError as exc:
                return JsonResponse({'error': ' '.join(exc.messages)}, status=409)
            except RecursionError:
                return JsonResponse({'error': 'The request is nested too deeply.'}, status=400)
        return operator_view(_methods(*allowed)(handled))
    return decorate


def _encounter(encounter_id):
    try:
        return models.Encounter.objects.select_related('workspace', 'workspace__category', 'created_by').get(
            pk=encounter_id)
    except (models.Encounter.DoesNotExist, ValueError, TypeError, ValidationError):
        raise Http404()


# --- the console --------------------------------------------------------------------------------------------------

@operator_view
@ensure_csrf_cookie
def index(request):
    if request.method != 'GET':
        return HttpResponse(status=405, headers={'Allow': 'GET'})
    return render(request, 'studio/ops.html', {'release': settings.RELEASE_SHA})


def _asset(name):
    @operator_view
    def serve(request):
        if request.method != 'GET':
            return HttpResponse(status=405, headers={'Allow': 'GET'})
        try:
            data = (ASSETS / name).read_bytes()
        except OSError:
            raise Http404()
        return HttpResponse(data, content_type=ASSET_TYPES[name])
    serve.__name__ = f'asset_{name.replace(".", "_")}'
    return serve


script = _asset('ops.js')
stylesheet = _asset('ops.css')


@operator_api('GET')
def session(request):
    """The console's session, in the shape of serializers.session_json (the console reads it as the website did): the
    operator, no workspace of their own, nothing to review."""
    from . import serializers
    from .gi.profiles import CATEGORY_NAME, CATEGORY_SLUG, PROFILES_VERSION

    user = request.user
    return JsonResponse({
        'user': serializers.user_json(user),
        'workspace': {'id': '', 'name': 'Operator diagnostics', 'subtitle': 'Every synthetic workspace, read-only',
                      'category': {'slug': CATEGORY_SLUG, 'name': CATEGORY_NAME, 'profiles_version': PROFILES_VERSION}},
        'role': 'operator', 'can_review': False, 'acknowledgement': '',
        'counts': {'documents': models.Encounter.objects.count(), 'queue': 0},
        'synthetic_only': settings.SYNTHETIC_ONLY, 'provider_mode': settings.PROVIDER_MODE,
        'release': settings.RELEASE_SHA,
    })


@operator_api('GET')
def encounters(request):
    """Every encounter of every workspace (``?workspace=<uuid>`` narrows it), newest first: the operator serializer's
    list row, its workspace and how many provider runs it recorded."""
    from . import serializers

    rows = models.Encounter.objects.select_related('workspace', 'current_revision', 'current_context',
                                                   'current_assessment').order_by('-created_at')
    workspace = request.GET.get('workspace')
    if workspace:
        try:
            rows = rows.filter(workspace_id=workspace)
            list(rows[:1])
        except (ValueError, ValidationError):
            from .api import ApiError
            raise ApiError(400, 'workspace must be a workspace id.')
    return JsonResponse({'encounters': [
        {**serializers.encounter_summary(encounter),
         'workspace': {'id': str(encounter.workspace_id), 'name': encounter.workspace.name},
         'provider_runs': encounter.provider_runs.count()} for encounter in rows]})


@operator_api('GET')
def encounter_detail(request, encounter_id):
    """Today's full serializers.encounter_detail: the harness, every provider run, the activity with its data."""
    from . import serializers

    encounter = _encounter(encounter_id)
    payload = serializers.encounter_detail(encounter, access_for(request.user, encounter))
    record_view(request.user, encounter, 'detail')
    return JsonResponse(payload)


@operator_api('GET')
def trace(request, encounter_id):
    """The administrative trace of the current revision (HARNESS.md 7): each participant's runs and full readings, the
    retrieval traces and the reconciliation table (serializers.trace_json)."""
    from . import serializers

    encounter = _encounter(encounter_id)
    payload = serializers.trace_json(encounter)
    record_view(request.user, encounter, 'trace')
    return JsonResponse(payload)


def report_row(report):
    return {'id': str(report.pk), 'audience': report.audience, 'kind': report.kind, 'fmt': report.fmt,
            'filename': report.filename, 'sha256': report.sha256, 'snapshot_sha256': report.snapshot_sha256,
            'generated_by': report.generated_by.label(),
            'generated_at': report.generated_at.isoformat() if report.generated_at else None,
            'download_url': f'/ops/api/reports/{report.pk}/download'}


@operator_api('GET', 'POST')
def encounter_reports(request, encounter_id):
    """GET: every report artifact of the encounter - customer and operator, legacy included - with its audience and
    hashes. POST ``{"kind": "draft"|"reviewed", "fmt": "txt"|"csv"}``: the operator's full report (format
    cpt-studio-report@4, reports.generate), under the readiness the reviewed report has always needed."""
    from . import reports, review, serializers
    from .api import ApiError, _payload

    encounter = _encounter(encounter_id)
    if request.method == 'GET':
        payload = {'reports': [report_row(r) for r in encounter.reports.select_related('generated_by')
                               .order_by('-generated_at', '-pk')]}
        record_view(request.user, encounter, 'reports')
        return JsonResponse(payload)
    data = _payload(request)
    kind, fmt = str(data.get('kind', '')), str(data.get('fmt', ''))
    if kind not in {models.ReportArtifact.DRAFT, models.ReportArtifact.REVIEWED} or fmt not in {'txt', 'csv'}:
        raise ApiError(400, 'Choose a draft or reviewed report as TXT or CSV.')
    if encounter.current_assessment_id is None:
        raise ApiError(409, 'There is nothing to report yet.')
    if kind == models.ReportArtifact.REVIEWED:
        ready = review.readiness(encounter)
        if not ready['reviewed']:
            raise ApiError(409, 'The reviewed report is not available yet.', blockers=ready['blockers'])
    try:
        report = reports.generate(encounter, kind, fmt, request.user, operator=True)
    except ValueError as exc:
        raise ApiError(409, str(exc))
    return JsonResponse(serializers._report_json(report), status=201)


@operator_api('GET')
def download_report(request, report_id):
    """Any artifact - a customer's, an operator's, one recorded before the audience existed - exactly as stored, with its
    sha256 (rollback evidence: nothing is ever re-rendered)."""
    try:
        report = models.ReportArtifact.objects.select_related('encounter__workspace').get(pk=report_id)
    except (models.ReportArtifact.DoesNotExist, ValueError, ValidationError):
        raise Http404()
    content = bytes(report.content)
    content_type = 'text/csv; charset=utf-8' if report.fmt == 'csv' else 'text/plain; charset=utf-8'
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{report.filename}"'
    response['X-Content-SHA256'] = report.sha256
    record_view(request.user, report.encounter, 'download', report=str(report.pk))
    return response


@operator_api('GET')
def original(request, encounter_id):
    """The original upload exactly as stored, with its sha256."""
    from .storage import read_original

    encounter = _encounter(encounter_id)
    source = encounter.files.order_by('uploaded_at').first()
    if source is None:
        raise Http404()
    data = read_original(source)
    response = HttpResponse(data, content_type=source.media_type)
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', source.original_name)[:120] or 'original'
    response['Content-Disposition'] = f'attachment; filename="{safe_name}"'
    response['X-Content-SHA256'] = source.sha256
    record_view(request.user, encounter, 'original')
    return response


@operator_api('POST')
def reconcile(request, encounter_id):
    """Record the reconciliation of one unknown outcome (``{"provider_run_id", "note"}``, the note at least 12
    characters) and release one new attempt (jobs.reconcile): operator work, since deciding whether a vendor received a
    request needs the vendor's request id, which only an operator may see."""
    from . import jobs
    from .api import ApiError, _identifier, _payload, _text_field

    data = _payload(request)
    encounter = _encounter(encounter_id)
    note = _text_field(data, 'note', 'The reconciliation note').strip()
    if len(note) < 12:
        raise ApiError(400, 'Describe how the unknown outcome was reconciled (at least 12 characters).')
    try:
        run = encounter.provider_runs.get(pk=_identifier(data.get('provider_run_id')))
    except (models.ProviderRun.DoesNotExist, ValueError, ValidationError):
        raise ApiError(404, 'That provider request is not part of this document.')
    try:
        recorded = jobs.reconcile(encounter, run, request.user, note)
    except jobs.Refused as exc:
        raise ApiError(409, str(exc))
    if recorded is None:
        raise ApiError(409, 'Only an unreconciled unknown outcome can be reconciled.')
    return JsonResponse({'reconciled': str(run.pk)}, status=201)
