"""The customer JSON API (BUILD-SPEC 6; client contract customer-2026-11-24). Session auth; CSRF enforced on every POST by
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
    POST /api/encounters/<id>/decisions             {round, line, code, action, acknowledgement, note, decision}: one
                                                    line of the round the page shows; an undo names the decision it
                                                    undoes (409 when the round or that decision changed)
    POST /api/encounters/<id>/stop | resume | retry
    POST /api/encounters/<id>/reports               {kind: draft|approved, fmt: pdf, round}: the PDF report of the
                                                    round the page shows (409 when it is not the latest; 503 when a
                                                    PDF cannot be made, nothing stored)
    GET  /api/encounters/<id>/original[?view=1]     the download (a Word document's converted PDF; the Word file with
                                                    format=original), or the in-page view (inline)
    GET  /api/reports/<id>/download                 a stored export, exactly as stored

Release 1, C1: every read of a document is recorded before it is served (studio.read_audit; the 503 NOT_RECORDED
answer when it cannot be), and a read of another practice's document or report is the same 404 with a refused row.
"""
import functools
import json
import math
import re
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import audit, client_contract, customer, decisions, exports, intake, jobs, models, rate, read_audit, request_meta
from . import security_events, sessions
from .access import active_membership, scoped_encounter
from .fable.document import STORAGE_TEXT
from .storage import OriginalCorrupted

# PostgreSQL text cannot hold NUL, and a lone surrogate cannot be encoded at all.
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')
REVIEWER_ONLY = 'Your role in this workspace cannot change documents or decisions.'
# release 1, C4: the team (owners only, D15)
OWNERS_ONLY = 'Only an owner of this workspace can see and change its team.'
OWN_ACCESS = 'You cannot turn off your own access. Ask another owner of the workspace, or CPT Studio.'
LAST_OWNER = 'The workspace must keep an owner with access, so this owner stays on.'
ACTIVE_REQUIRED = 'Send active: true or false.'
ROLE_REFUSED = 'Your role cannot do that.'
NOT_SAVED = 'This change could not be saved. Reload the page and try again.'
# The coding pipeline's refusals a member may read as they are (studio.jobs: fixed sentences); any other is NOT_SAVED.
# Release 1 adds Lane 4's (D1): a closed practice's and a destroyed document's sentences. They are read by name, so this
# module imports on a tree where studio.jobs does not define them yet; a name it does not define adds nothing.
JOB_REFUSAL_NAMES = ('BUSY_MESSAGE', 'RETRY_NOTHING', 'RECONCILE_FIRST', 'CLOSED_MESSAGE', 'DESTROYED_MESSAGE')


def job_refusals() -> frozenset:
    """The sentences of JOB_REFUSAL_NAMES that studio.jobs defines, read when a refusal is answered."""
    return frozenset(getattr(jobs, name) for name in JOB_REFUSAL_NAMES if isinstance(getattr(jobs, name, None), str))


JOB_REFUSALS = job_refusals()  # as studio.jobs defines them at import
VIEW_CSP = "frame-ancestors 'self'"  # the in-page view of the original: framed by CPT Studio's own page only


class ApiError(Exception):
    def __init__(self, status, message, **details):
        super().__init__(message)
        self.status, self.message, self.details = status, message, details


# --- the limits (release 1, C5; owner decision D8) --------------------------------------------------------------------
# Reports and uploads cost a web worker's time and keep copies of PHI, so each is counted per member - and reports per
# practice too - in fixed windows (studio.rate: the counter is written outside any transaction, so a refused request
# still counts). Over a limit the answer is 429 {"error": "rate_limited", "retry_after": s} with Retry-After: s, and the
# first refusal of a window writes one SecurityEvent <what>.rate_limited (ids and counts). nginx's zones are the outer
# bound (A1). Lane 4's bundle limit (D2) answers the same shape under its own scope, bundle.member.

RATE_LIMITED = 'rate_limited'
EXPORT_MEMBER_SCOPE, EXPORT_WORKSPACE_SCOPE, UPLOAD_MEMBER_SCOPE = 'export.member', 'export.workspace', 'upload.member'


class RateLimited(Exception):
    """Over a limit: answered 429 with the seconds until the window ends."""

    def __init__(self, retry_after):
        super().__init__(RATE_LIMITED)
        self.retry_after = retry_after


def retry_after(window_seconds, now=None) -> int:
    """Whole seconds until the current window of ``window_seconds`` ends (at least 1)."""
    now = now or timezone.now()
    end = rate.window_start(window_seconds, now) + timedelta(seconds=window_seconds)
    return max(1, math.ceil((end - now).total_seconds()))


def _limited(request, scope, key, limit, *, workspace_id):
    """Count one more of ``scope`` for ``key`` (an account's or a practice's id); RateLimited when that goes over
    ``limit`` - (how many, window seconds), a settings constant - and on the first refusal of the window one SecurityEvent
    <what>.rate_limited naming the account and the practice."""
    allowed, window_seconds = limit
    hits = rate.hit(scope, key, window_seconds=window_seconds)
    if hits <= allowed:
        return
    if hits == allowed + 1:
        security_events.record(f'{scope.split(".")[0]}.rate_limited', actor=request.user, subject=request.user,
                               workspace_id=workspace_id, scope=scope, limit=allowed, window_seconds=window_seconds)
    raise RateLimited(retry_after(window_seconds))


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
        except RateLimited as exc:  # release 1, C5: the contract's rate_limited answer
            response = JsonResponse({'error': RATE_LIMITED, 'retry_after': exc.retry_after}, status=429)
            response['Retry-After'] = str(exc.retry_after)
            return response
        except ApiError as exc:
            return JsonResponse({'error': exc.message, 'details': exc.details}, status=exc.status)
        except decisions.Refused as exc:
            return JsonResponse({'error': exc.message, 'details': {}}, status=exc.status)
        except jobs.Refused as exc:
            message = str(exc) if str(exc) in job_refusals() else NOT_SAVED
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


# --- the read records (release 1, C1) -------------------------------------------------------------------------------
# Every read of a document - the list, the document, its in-page view, its download, a report's download - writes its
# AccessRecord before the answer leaves (studio.read_audit.record); a read whose row cannot be written answers 503 with
# the fixed sentence and nothing else (fail closed). A document or report that exists in another practice is answered
# exactly as a missing one (404), with a refused row that shows the probing (TEC-10).

def _recorded(request, view, **fields):
    """The AccessRecord of this read, written before it is served; ApiError 503 (read_audit.NOT_RECORDED, no PHI) when
    it cannot be written."""
    try:
        return read_audit.record(request, view=view, **fields)
    except read_audit.NotRecorded:
        raise ApiError(503, read_audit.NOT_RECORDED)


def _refused_read(request, view, **fields):
    """The refused row of a read of another practice's document or report. The answer is the same 404 whether or not
    the row could be written: a 503 here would tell an existing document from a missing one."""
    try:
        read_audit.record(request, view=view, outcome=read_audit.REFUSED, **fields)
    except read_audit.NotRecorded:
        pass


def _scoped(request, encounter_id, view):
    """(encounter, membership) as access.scoped_encounter gives them; a document that exists in a practice the caller
    is no active member of is answered the same 404, with a refused row of ``view``; a destroyed document's tombstone is
    answered 404 too (D1)."""
    try:
        encounter, membership = scoped_encounter(request.user, encounter_id)
    except Http404:
        try:
            found = models.Encounter.objects.only('pk', 'workspace_id').get(pk=encounter_id)
        except (models.Encounter.DoesNotExist, ValueError, TypeError, ValidationError):
            raise Http404() from None
        _refused_read(request, view, workspace_id=found.workspace_id, encounter_ids=[found.pk])
        raise Http404() from None
    if encounter.destroyed_at is not None:  # a disposal's tombstone (D1): nothing of it is left to show
        raise Http404()
    return encounter, membership


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
@read_audit.phi_read(read_audit.MEMBER_LIST)
def encounters(request):
    """GET the list; POST an upload (multipart: file or text, title, service_date, insurance, synthetic_attestation,
    client_key) -> 201 {id}, its coding round 1 queued in the same transaction (intake.create_encounter). The list is
    recorded as member.list: the practice, the time it was read and how many rows it holds - the whole practice, with no
    paging, so that says exactly which rows were shown."""
    membership = active_membership(request.user)
    if request.method == 'GET':
        as_of = timezone.now()
        rows = customer.list_rows(membership)
        _recorded(request, read_audit.MEMBER_LIST, workspace_id=membership.workspace_id, count=len(rows), as_of=as_of)
        return JsonResponse({'encounters': rows})
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
    _limited(request, UPLOAD_MEMBER_SCOPE, request.user.pk, settings.UPLOAD_LIMIT_PER_MEMBER,
             workspace_id=membership.workspace_id)  # C5: before the file is read, stored or queued
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
@read_audit.phi_read(read_audit.MEMBER_DETAIL)
def encounter_detail(request, encounter_id):
    """The document as the page shows it, recorded as member.detail on every call - except the page's poll while coding
    runs (X-CPT-Poll: 1), which writes at most one row per sign-in and document a minute (read_audit.detail_seen_recently;
    TEC-9 (4))."""
    encounter, membership = _scoped(request, encounter_id, read_audit.MEMBER_DETAIL)
    if not (request_meta.is_poll(request) and read_audit.detail_seen_recently(request, encounter.pk)):
        _recorded(request, read_audit.MEMBER_DETAIL, workspace_id=encounter.workspace_id, encounter_ids=[encounter.pk])
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
    acknowledgement, note, decision: for an undo, the id of the decision it undoes} -> 201 {id, line, code, action, by,
    at, note} (decisions.record: 409 when the round is not the latest done one, the line is not in it with that code, or
    an undo names a decision that is not the line's current one)."""
    data = _payload(request)
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    decision = decisions.record(encounter, request.user, membership, round_number=data.get('round'),
                                line=data.get('line'), code=data.get('code'), action=data.get('action'),
                                acknowledgement=data.get('acknowledgement'), note=data.get('note'),
                                decision=data.get('decision'))
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
    """{kind: draft|approved, fmt: pdf, round: the round number the page shows} -> 201 the export as the page lists it,
    or 200 the stored copy when that report is still current (exports.create, release 1 C5: 400 for any format but the
    PDF, the only one made since 2026-11-21; 409 when that round is not the latest; 503 when the PDF cannot be made,
    nothing stored). Any member may (owner decision D8: viewers keep making reports), within the member's and the
    practice's limits (429), which count only the reports actually made: a stored copy answered again counts toward
    none (lead ruling 2026-11-24)."""
    data = _payload(request)
    encounter, _ = scoped_encounter(request.user, encounter_id)
    kind, fmt, round_number = data.get('kind'), data.get('fmt'), data.get('round')
    if kind not in exports.KINDS or fmt not in exports.FORMATS:
        raise ApiError(400, exports.FORMAT_REQUIRED)
    if type(round_number) is not int or round_number < 1:
        raise ApiError(400, exports.ROUND_REQUIRED)

    def charge():
        """A report about to be made counts toward the member's and the practice's limits; a reused one never does
        (exports.create calls this only on the made path)."""
        _limited(request, EXPORT_MEMBER_SCOPE, request.user.pk, settings.EXPORT_LIMIT_PER_MEMBER,
                 workspace_id=encounter.workspace_id)
        _limited(request, EXPORT_WORKSPACE_SCOPE, encounter.workspace_id, settings.EXPORT_LIMIT_PER_WORKSPACE,
                 workspace_id=encounter.workspace_id)
    try:
        export = exports.create(encounter, request.user, kind, fmt, round_number=round_number, charge=charge)
    except exports.NotReady as exc:
        raise ApiError(409, exc.message, blockers=exc.blockers)
    except exports.NotMade as exc:
        raise ApiError(503, exc.message)
    return JsonResponse(customer.report_json(export, export.round_id), status=200 if export.reused else 201)


@require_GET
@api_view(contract=False)
@read_audit.phi_read(read_audit.MEMBER_REPORT_DOWNLOAD)
def download_report(request, report_id):
    """A stored export of the caller's workspace, exactly as stored (no hash header), recorded as
    member.report_download (the report and its document); anything else answers 404 - another practice's report with a
    refused row."""
    try:
        export = models.ExportArtifact.objects.select_related('encounter').get(pk=report_id)
    except (models.ExportArtifact.DoesNotExist, ValueError, ValidationError):
        raise Http404()
    workspace_id = export.encounter.workspace_id
    try:
        active_membership(request.user, workspace_id)
    except Http404:
        _refused_read(request, read_audit.MEMBER_REPORT_DOWNLOAD, workspace_id=workspace_id,
                      encounter_ids=[export.encounter_id], export_id=export.pk)
        raise
    content, content_type, filename = exports.download(export)
    _recorded(request, read_audit.MEMBER_REPORT_DOWNLOAD, workspace_id=workspace_id, encounter_ids=[export.encounter_id],
              export_id=export.pk)
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{customer.safe_name(filename, "export")}"'
    return response


@require_GET
@api_view(contract=False)
@read_audit.phi_read(read_audit.MEMBER_DOWNLOAD)  # and member.inline, for view=1
def original(request, encounter_id):
    """The upload as a download (customer.download_content, release 1 C6: a Word document's is the PDF its coding review
    read; the Word file itself only with format=original, which the page asks for after its warning, and the only one
    a Word document with no PDF yet has), recorded as member.download with the format it served; with view=1, what the
    in-page viewer shows (customer.view_content: the PDF or text, the pasted text, a Word document's converted PDF),
    inline and framable by CPT Studio's own page only, recorded as member.inline. Each row is written before the bytes
    are sent."""
    inline = request.GET.get('view') == '1'
    view = read_audit.MEMBER_INLINE if inline else read_audit.MEMBER_DOWNLOAD
    encounter, _ = _scoped(request, encounter_id, view)
    record = {'workspace_id': encounter.workspace_id, 'encounter_ids': [encounter.pk]}
    try:
        if inline:
            found = customer.view_content(encounter)
            if found is None:
                raise Http404()
            data, content_type, filename = found
            _recorded(request, view, **record)
            response = HttpResponse(data, content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            response['X-Frame-Options'] = 'SAMEORIGIN'
            response['Content-Security-Policy'] = VIEW_CSP
            return response
        try:
            found = customer.download_content(encounter, original=request.GET.get('format') == customer.ORIGINAL)
        except customer.OriginalOnly:
            raise ApiError(409, customer.ORIGINAL_ONLY, original_url=f'/api/encounters/{encounter.pk}/original'
                                                                     f'?format={customer.ORIGINAL}')
        if found is None:
            raise Http404()
    except (OriginalCorrupted, OSError):
        raise ApiError(409, STORAGE_TEXT)
    _recorded(request, view, filters={'format': found.fmt}, **record)
    response = HttpResponse(found.data, content_type=found.content_type)
    response['Content-Disposition'] = f'attachment; filename="{found.filename}"'
    return response  # no hash header for a customer (the operator's download carries it)


# --- the team (release 1, C4; owner decision D15) --------------------------------------------------------------------

def _owner(request):
    """The caller's active membership when it is an owner's; ApiError 403 OWNERS_ONLY otherwise."""
    membership = active_membership(request.user)
    if membership.role != models.Membership.OWNER or not membership.active:
        raise ApiError(403, OWNERS_ONLY)
    return membership


@require_GET
@api_view
def members(request):
    """GET api/members -> {members: [member]} (customer.members_json), for an owner of the practice."""
    membership = _owner(request)
    return JsonResponse({'members': customer.members_json(membership)})


@require_POST
@api_view
def member_access(request, user_id):
    """POST api/members/<user>/access {active: false|true} -> {member}: that person's access to this practice
    (Membership.active, never the account's is_active), for an owner; refused for the owner's own membership and for
    the practice's last active owner. A person left with no active membership is signed out everywhere. Each change
    writes an AuditEvent member.access_off or member.access_on naming the owner, which the practice's activity shows;
    the person loses the practice at their next request (access.active_membership is read on every one)."""
    data = _payload(request)
    active = data.get('active')
    if not isinstance(active, bool):
        raise ApiError(400, ACTIVE_REQUIRED)
    membership = _owner(request)
    target = _set_member_access(membership, user_id, active, request.user)
    return JsonResponse({'member': customer.member_json(
        target, customer.last_sign_ins([target.user.username]).get(target.user.username))})


def _set_member_access(owner_membership, user_id, active, actor):
    """Set ``user_id``'s access to ``owner_membership``'s practice, decided under one lock on the practice's memberships
    (every one, in id order), so two owners turning each other off at once leave the practice an active owner: the one
    decided second finds the other already off and is refused as the last active owner. The membership changed (or
    found already so)."""
    try:
        with transaction.atomic():
            rows = list(models.Membership.objects.select_for_update(of=('self',)).select_related('user')
                        .filter(workspace_id=owner_membership.workspace_id).order_by('pk'))
            target = next((row for row in rows if str(row.user_id) == str(user_id)), None)
            if target is None:
                raise Http404()
            if target.pk == owner_membership.pk:
                raise ApiError(409, OWN_ACCESS)
            if (not active and target.role == models.Membership.OWNER and target.active
                    and not any(row.role == models.Membership.OWNER and row.active and row.pk != target.pk
                                for row in rows)):
                raise ApiError(409, LAST_OWNER)
            mine = next((row for row in rows if row.pk == owner_membership.pk), None)
            if mine is None or not mine.active or mine.role != models.Membership.OWNER:
                raise ApiError(403, OWNERS_ONLY)  # no longer an owner with access, by the time the lock was held
            if target.active == active:
                return target
            models.Membership.objects.filter(pk=target.pk).update(active=active)
            target.active = active
            values = {}
            if not active and not models.Membership.objects.filter(user_id=target.user_id, active=True).exists():
                values['sessions_ended'] = sessions.end_sessions(target.user)
            audit.record(owner_membership.workspace, f'member.access_{"on" if active else "off"}', actor=actor,
                         user=str(target.user_id), membership=str(target.pk), role=target.role, **values)
            return target
    except sessions.Refused:
        raise ApiError(409, NOT_SAVED)
