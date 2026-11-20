"""The customer JSON API (BUILD-SPEC 6; client contract customer-2026-11-21). Session auth; CSRF enforced on every POST by
the middleware; every response no-store (access.SecurityHeadersMiddleware).

Every handler resolves the caller's ACTIVE membership first and scopes every row through it, so another workspace's
records answer 404 (access.py). Changes - an upload, answers, decisions, stop, resume, retry - need the owner or reviewer
role (403 otherwise); any member may read and make exports. Every payload is built by studio.customer and every error
the member reads is one of this module's own sentences (api_view: never an exception's or a stored text). The full
record - runs, models, usage, hashes, the coding review's whole answers - is a platform operator's, under /ops/.

    GET  /api/session                               customer.session_json
    GET  /api/encounters                            customer.list_rows
    POST /api/encounters                            an upload or a paste (multipart); starts coding round 1
    GET  /api/encounters/<id>                       customer.encounter_json
    POST /api/encounters/<id>/answers               {answers: [{question_id, text}]} -> a new round
    POST /api/encounters/<id>/decisions             {round, line, code, action, acknowledgement, note}: one line of
                                                    the round the page shows (409 when that round changed)
    POST /api/encounters/<id>/stop | resume | retry
    POST /api/encounters/<id>/reports               {kind: draft|approved, fmt: txt|csv}
    GET  /api/encounters/<id>/original[?view=1]     the original (download), or the in-page view (inline)
    GET  /api/reports/<id>/download                 a stored export, exactly as stored
"""
import functools
import json
import re
import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import client_contract, customer, decisions, exports, intake, jobs, models
from .access import active_membership, scoped_encounter
from .fable.document import STORAGE_TEXT
from .storage import OriginalCorrupted, read_original

# PostgreSQL text cannot hold NUL, and a lone surrogate cannot be encoded at all.
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')
REVIEWER_ONLY = 'Your role in this workspace cannot change documents or decisions.'
ROLE_REFUSED = 'Your role cannot do that.'
NOT_SAVED = 'This change could not be saved. Reload the page and try again.'
# The coding pipeline's refusals a member may read as they are (studio.jobs: fixed sentences); any other is NOT_SAVED.
JOB_REFUSALS = frozenset({jobs.BUSY_MESSAGE, jobs.RETRY_NOTHING})
VIEW_CSP = "frame-ancestors 'self'"  # the in-page view of the original: framed by CPT Studio's own page only


class ApiError(Exception):
    def __init__(self, status, message, **details):
        super().__init__(message)
        self.status, self.message, self.details = status, message, details


def api_view(view=None, *, contract=True):
    """A customer API view: sign-in required (401), and - unless ``contract`` is False (a download or the in-page view, a
    browser navigation that sends no header of the page's) - the page build the client contract names (409
    client_outdated before the view runs). Errors answer JSON with the member's sentence only."""
    if view is None:
        return functools.partial(api_view, contract=contract)

    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Sign in to continue.'}, status=401)
        if contract and not client_contract.current(request):
            return JsonResponse(client_contract.OUTDATED, status=409)
        try:
            return view(request, *args, **kwargs)
        except ApiError as exc:
            return JsonResponse({'error': exc.message, 'details': exc.details}, status=exc.status)
        except decisions.Refused as exc:
            return JsonResponse({'error': exc.message, 'details': {}}, status=exc.status)
        except jobs.Refused as exc:
            message = str(exc) if str(exc) in JOB_REFUSALS else NOT_SAVED
            return JsonResponse({'error': message, 'details': {}}, status=409)
        except Http404:
            return JsonResponse({'error': 'Not found.'}, status=404)
        except PermissionDenied as exc:
            return JsonResponse({'error': REVIEWER_ONLY if str(exc) == REVIEWER_ONLY else ROLE_REFUSED}, status=403)
        except ValidationError:
            return JsonResponse({'error': NOT_SAVED, 'details': {}}, status=409)
        except RecursionError:  # a backstop: a nested value that reached code recursing per level
            return JsonResponse({'error': 'The request is nested too deeply.'}, status=400)
    return wrapper


def _payload(request) -> dict:
    if request.content_type != 'application/json':
        raise ApiError(400, 'Send the request as JSON.')
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, RecursionError):  # RecursionError: nesting deeper than the parser allows
        raise ApiError(400, 'The request body is not valid JSON.')
    if not isinstance(data, dict):
        raise ApiError(400, 'The request body must be a JSON object.')
    return data


def _require_reviewer(membership):
    if not membership.can_review:
        raise PermissionDenied(REVIEWER_ONLY)


def _storable(value, label):
    """Refuse text the database cannot store exactly, rather than altering what the member submitted."""
    if UNSTORABLE.search(value):
        raise ApiError(400, f'{label} contains a NUL character or an invalid Unicode code point; remove it and try again.')
    return value


# The one date form the page sends. date.fromisoformat alone also reads a basic date and an ISO week date.
_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
# The upload attempt's key, a UUID the page generates per attempt (8-4-4-4-12 hex digits).
_CLIENT_KEY = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')


def _service_date(value):
    if value is None or value == '':
        return ''
    if not isinstance(value, str) or not _DATE.fullmatch(value):
        raise ApiError(400, 'Service date must be a date in YYYY-MM-DD form.')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ApiError(400, 'Service date must be a date in YYYY-MM-DD form.')


def _insurance(value):
    """Medicare, Medicaid, commercial or other, or not sure ('unknown', also for no value)."""
    if value is None or value == '':
        return 'unknown'
    if not isinstance(value, str) or value not in jobs.INSURANCE:
        raise ApiError(400, 'Choose the insurance: Medicare, Medicaid, commercial or other, or not sure.')
    return value


def _client_key(value):
    if value is None or value == '':
        return None
    if not isinstance(value, str) or not _CLIENT_KEY.fullmatch(value):
        raise ApiError(400, 'The upload key must be a UUID.')
    return uuid.UUID(value)


def _clean_title(raw, fallback):
    title = re.sub(r'\s+', ' ', UNSTORABLE.sub(' ', str(raw or ''))).strip()[:160]
    return title or fallback


@require_GET
@api_view
def session(request):
    membership = active_membership(request.user)
    return JsonResponse(customer.session_json(request.user, membership))


@api_view
def encounters(request):
    """GET the list; POST an upload (multipart: file or text, title, service_date, insurance, synthetic_attestation,
    client_key) -> 201 {id}, its coding round 1 queued in the same transaction (intake.create_encounter)."""
    membership = active_membership(request.user)
    if request.method == 'GET':
        return JsonResponse({'encounters': customer.list_rows(membership)})
    if request.method != 'POST':
        raise ApiError(405, 'Method not allowed.')
    _require_reviewer(membership)
    if request.POST.get('synthetic_attestation') not in ('yes', 'true', 'on'):
        raise ApiError(400, 'Confirm that the document is synthetic and contains no real patient information.')
    upload = request.FILES.get('file')
    text = _storable(request.POST.get('text', ''), 'The pasted text')
    if bool(upload) == bool(text.strip()):
        raise ApiError(400, 'Provide either a file or pasted text.')
    service_date = _service_date(request.POST.get('service_date'))
    insurance = _insurance(request.POST.get('insurance'))
    if upload is not None:
        if upload.size > settings.MAX_UPLOAD_BYTES:
            raise ApiError(400, f'The file is larger than {settings.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.')
        data = upload.read(settings.MAX_UPLOAD_BYTES + 1)
        filename = UNSTORABLE.sub('', upload.name)
        fallback_title = filename.rsplit('.', 1)[0][:160] or 'Uploaded document'
    else:
        data, filename = None, ''
        fallback_title = f'Pasted note {timezone.now():%Y-%m-%d %H:%M}'
    title = _clean_title(request.POST.get('title'), fallback_title)
    client_key = _client_key(request.POST.get('client_key'))
    pasted = '' if upload is not None else text
    try:
        encounter = intake.find_upload(user=request.user, workspace=membership.workspace, client_key=client_key,
                                       data=data, text=pasted)
        if encounter is None:
            encounter = intake.create_encounter(
                membership=membership, user=request.user, title=title, service_date=service_date,
                insurance=insurance, data=data, filename=filename, text=pasted, client_key=client_key)
    except intake.DuplicateUpload as exc:
        encounter = exc.encounter
    except intake.UploadKeyRefused as exc:
        raise ApiError(409, str(exc))
    except ValidationError as exc:  # intake's and storage's own sentences about the file
        raise ApiError(400, ' '.join(exc.messages))
    return JsonResponse({'id': str(encounter.pk)}, status=201)


@require_GET
@api_view
def encounter_detail(request, encounter_id):
    encounter, membership = scoped_encounter(request.user, encounter_id)
    return JsonResponse(customer.encounter_json(encounter, membership))


@require_POST
@api_view
def answers(request, encounter_id):
    """{answers: [{question_id, text}]} -> 201 {round}: the answers stored and the next round queued with every answer so
    far in its context (decisions.record_answers)."""
    data = _payload(request)
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    round_ = decisions.record_answers(encounter, request.user, decisions.answer_items(data.get('answers')))
    return JsonResponse({'round': customer.round_json(round_)}, status=201)


@require_POST
@api_view
def decide(request, encounter_id):
    """{round: the round number the page shows, line: "L2", code: "20610", action: approve|reject|revoke,
    acknowledgement, note} -> 201 {line, code, action, by, at, note} (decisions.record: 409 when the round is not the
    latest done one, or the line is not in it with that code)."""
    data = _payload(request)
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    decision = decisions.record(encounter, request.user, membership, round_number=data.get('round'),
                                line=data.get('line'), code=data.get('code'), action=data.get('action'),
                                acknowledgement=data.get('acknowledgement'), note=data.get('note'))
    return JsonResponse({'line': decision.line, 'code': decision.code, **customer.decision_json(decision)}, status=201)


@require_POST
@api_view
def stop(request, encounter_id):
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    if not jobs.busy(encounter):
        raise ApiError(409, 'Nothing is running to stop.')
    return JsonResponse({'stopped': jobs.stop_encounter(encounter, request.user)})


@require_POST
@api_view
def resume(request, encounter_id):
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    if jobs.resume(encounter, request.user) is None:
        raise ApiError(409, 'There is no stopped coding review to resume.')
    return JsonResponse({'resumed': True}, status=201)


@require_POST
@api_view
def retry(request, encounter_id):
    """A new round of the current revision (trigger retry): for a failed latest round, or for an earlier review (an
    encounter with no round) - decisions.retry."""
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    round_ = decisions.retry(encounter, request.user)
    return JsonResponse({'round': customer.round_json(round_)}, status=201)


@require_POST
@api_view
def create_report(request, encounter_id):
    """{kind: draft|approved, fmt: txt|csv} -> 201 the export as the page lists it (exports.create)."""
    data = _payload(request)
    encounter, _ = scoped_encounter(request.user, encounter_id)
    kind, fmt = data.get('kind'), data.get('fmt')
    if kind not in exports.KINDS or fmt not in exports.FORMATS:
        raise ApiError(400, 'Choose a draft or an approved export as TXT or CSV.')
    try:
        export = exports.create(encounter, request.user, kind, fmt)
    except exports.NotReady as exc:
        raise ApiError(409, exc.message, blockers=exc.blockers)
    return JsonResponse(customer.report_json(export, export.round_id), status=201)


@require_GET
@api_view(contract=False)
def download_report(request, report_id):
    """A stored export of the caller's workspace, exactly as stored (no hash header); anything else answers 404."""
    try:
        export = models.ExportArtifact.objects.select_related('encounter').get(pk=report_id)
    except (models.ExportArtifact.DoesNotExist, ValueError, ValidationError):
        raise Http404()
    active_membership(request.user, export.encounter.workspace_id)
    content, content_type, filename = exports.download(export)
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{customer.safe_name(filename, "export")}"'
    return response


@require_GET
@api_view(contract=False)
def original(request, encounter_id):
    """The original upload as a download; with view=1, what the in-page viewer shows (customer.view_content: the PDF or
    text, the pasted text, a Word document's converted PDF), inline and framable by CPT Studio's own page only."""
    encounter, _ = scoped_encounter(request.user, encounter_id)
    try:
        if request.GET.get('view') == '1':
            found = customer.view_content(encounter)
            if found is None:
                raise Http404()
            data, content_type, filename = found
            response = HttpResponse(data, content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            response['X-Frame-Options'] = 'SAMEORIGIN'
            response['Content-Security-Policy'] = VIEW_CSP
            return response
        source = customer.original_file(encounter)
        if source is None:
            raise Http404()
        data = read_original(source)
    except (OriginalCorrupted, OSError):
        raise ApiError(409, STORAGE_TEXT)
    response = HttpResponse(data, content_type=source.media_type)
    response['Content-Disposition'] = f'attachment; filename="{customer.safe_name(source.original_name)}"'
    return response  # no hash header for a customer (the operator's download carries it)
