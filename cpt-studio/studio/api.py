"""JSON API (API.md). Session auth; CSRF enforced on every POST by middleware.

Every handler resolves the caller's ACTIVE membership first and scopes every
row through it, so another workspace's records answer 404.
"""
import functools
import json
import re
from datetime import date

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import audit, intake, jobs, models, reports, review, serializers
from .access import active_membership, scoped_encounter
from .ingest import canonicalize
from .storage import read_original

SETTINGS_CHOICES = {'hospital_outpatient', 'office', 'asc', 'inpatient', 'emergency', 'telehealth'}
BILLING_CHOICES = {'professional', 'facility'}
MAX_NOTE_CHARS = 2000
# PostgreSQL text cannot hold NUL, and a lone surrogate cannot be encoded at all.
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')


def _storable(value, label):
    """Refuse text the database cannot store exactly, rather than altering what the member submitted."""
    if UNSTORABLE.search(value):
        raise ApiError(400, f'{label} contains a NUL character or an invalid Unicode code point; '
                            'remove it and try again.')
    return value


def _text_field(data, name, label):
    value = _storable(str(data.get(name, '') or ''), label)
    if len(value) > MAX_NOTE_CHARS:
        raise ApiError(400, f'{label} can be at most {MAX_NOTE_CHARS} characters.')
    return value


class ApiError(Exception):
    def __init__(self, status, message, **details):
        super().__init__(message)
        self.status, self.message, self.details = status, message, details


def api_view(view):
    @functools.wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'error': 'Sign in to continue.'}, status=401)
        try:
            return view(request, *args, **kwargs)
        except ApiError as exc:
            return JsonResponse({'error': exc.message, 'details': exc.details}, status=exc.status)
        except Http404:
            return JsonResponse({'error': 'Not found.'}, status=404)
        except PermissionDenied as exc:
            return JsonResponse({'error': str(exc) or 'Your role cannot do that.'}, status=403)
        except ValidationError as exc:
            return JsonResponse({'error': ' '.join(exc.messages)}, status=409)
    return wrapper


def _payload(request):
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body or b'{}')
        except (ValueError, RecursionError):  # RecursionError: nesting deeper than the parser allows
            raise ApiError(400, 'The request body is not valid JSON.')
        if not isinstance(data, dict):
            raise ApiError(400, 'The request body must be a JSON object.')
        return data
    return request.POST


def _require_reviewer(membership):
    if not membership.can_review:
        raise PermissionDenied('Your role in this workspace cannot change documents or decisions.')


def _attested(value):
    if value not in ('yes', True, 'true', 'on'):
        raise ApiError(400, 'Confirm that the document is synthetic and contains no real patient information.')


def _parse_date(value, field):
    if value in (None, ''):
        return ''
    try:
        return date.fromisoformat(str(value)).isoformat()
    except ValueError:
        raise ApiError(400, f'{field} must be a date in YYYY-MM-DD form.')


def _clean_title(raw, fallback):
    title = re.sub(r'\s+', ' ', UNSTORABLE.sub(' ', str(raw or ''))).strip()[:160]
    return title or fallback


@require_GET
@api_view
def session(request):
    membership = active_membership(request.user)
    return JsonResponse(serializers.session_json(request.user, membership))


@api_view
def encounters(request):
    membership = active_membership(request.user)
    if request.method == 'GET':
        rows = membership.workspace.encounters.select_related(
            'current_revision', 'current_context', 'current_assessment').order_by('-created_at')
        return JsonResponse({'encounters': [serializers.encounter_summary(e) for e in rows]})
    if request.method != 'POST':
        raise ApiError(405, 'Method not allowed.')
    _require_reviewer(membership)
    _attested(request.POST.get('synthetic_attestation'))
    upload = request.FILES.get('file')
    text = _storable(request.POST.get('text', ''), 'The pasted text')
    if bool(upload) == bool(text.strip()):
        raise ApiError(400, 'Provide either a file or pasted text.')
    service_date = _parse_date(request.POST.get('service_date'), 'Service date')
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
    try:
        encounter = intake.create_encounter(
            membership=membership, user=request.user, title=title, service_date=service_date, data=data,
            filename=filename, text='' if upload is not None else text)
    except ValidationError as exc:
        raise ApiError(400, ' '.join(exc.messages))
    return JsonResponse({'id': str(encounter.pk)}, status=201)


@require_GET
@api_view
def encounter_detail(request, encounter_id):
    encounter, membership = scoped_encounter(request.user, encounter_id)
    return JsonResponse(serializers.encounter_detail(encounter, membership))


@require_POST
@api_view
def decisions(request, encounter_id):
    data = _payload(request)
    with transaction.atomic():
        encounter, membership = scoped_encounter(request.user, encounter_id, for_update=True)
        _require_reviewer(membership)
        if encounter.current_assessment_id is None:
            raise ApiError(409, 'There are no proposals to decide on yet.')
        try:
            proposal = encounter.current_assessment.proposals.get(pk=data.get('proposal_id'))
        except (models.Proposal.DoesNotExist, ValueError, ValidationError):
            raise ApiError(404, 'That proposal is not part of the current review.')
        decision = review.record_decision(
            encounter=encounter, proposal=proposal, action=str(data.get('action', '')), user=request.user,
            membership=membership, note=_text_field(data, 'note', 'The note'),
            acknowledgement=_text_field(data, 'acknowledgement', 'The acknowledgement'))
    return JsonResponse(serializers._decision_json(decision), status=201)


@require_POST
@api_view
def addenda(request, encounter_id):
    data = _payload(request)
    with transaction.atomic():
        encounter, membership = scoped_encounter(request.user, encounter_id, for_update=True)
        _require_reviewer(membership)
        _attested(data.get('synthetic_attestation'))
        text = _storable(str(data.get('text', '')), 'The addendum').strip()
        if not text:
            raise ApiError(400, 'Write the additional documentation to add.')
        if len(text) > 20000:
            raise ApiError(400, 'An addendum can be at most 20,000 characters.')
        if jobs.busy(encounter):
            raise ApiError(409, 'Wait for processing to finish (or stop it) before adding documentation.')
        parent = encounter.current_revision
        if parent is None or parent.extraction_status not in {models.SourceRevision.OK, models.SourceRevision.PARTIAL}:
            raise ApiError(409, 'This document has no extracted text to add to.')
        number, now = encounter.revisions.count() + 1, timezone.now()
        combined = len(canonicalize(parent.text + jobs.addendum_block_text(number, now, text)))
        if combined > settings.MAX_PASTE_CHARS:
            raise ApiError(400, f'With this addendum the document would have {combined:,} characters; '
                                f'the limit is {settings.MAX_PASTE_CHARS:,}.')
        clarification = None
        if data.get('clarification_id'):
            try:
                clarification = encounter.clarifications.get(pk=data['clarification_id'],
                                                            state=models.Clarification.OPEN)
            except (models.Clarification.DoesNotExist, ValueError, ValidationError):
                raise ApiError(404, 'That clarification is not open on this document.')
        revision = models.SourceRevision.objects.create(
            encounter=encounter, number=number, kind=models.SourceRevision.ADDENDUM,
            parent=parent, addendum_text=text, answers_clarification=clarification,
            synthetic_attested_by=request.user, synthetic_attested_at=now, created_by=request.user)
        if clarification is not None:
            clarification.state, clarification.answered_by_revision = models.Clarification.ANSWERED, revision
            clarification.save(update_fields=['state', 'answered_by_revision'])
        encounter.current_revision = revision
        encounter.save(update_fields=['current_revision', 'updated_at'])
        review.invalidate_for_new_revision(encounter, revision)
        audit.record(encounter.workspace, 'revision.addendum', encounter=encounter, actor=request.user,
                     revision=str(revision.pk), number=revision.number,
                     clarification=str(clarification.pk) if clarification else None)
        # Queued in the same transaction, so the encounter is never seen idle between the
        # new revision and its pipeline (a context change or reconcile would slip in there).
        jobs.start_pipeline(revision, request.user)
    return JsonResponse({'revision_id': str(revision.pk)}, status=201)


@require_POST
@api_view
def context(request, encounter_id):
    data = _payload(request)
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    values = {}
    if 'service_date' in data:
        values['service_date'] = _parse_date(data.get('service_date'), 'Service date')
    if 'setting' in data:
        setting = str(data.get('setting') or '')
        if setting and setting not in SETTINGS_CHOICES:
            raise ApiError(400, 'Choose a listed care setting.')
        values['setting'] = setting
    if 'billing_context' in data:
        billing = str(data.get('billing_context') or '')
        if billing and billing not in BILLING_CHOICES:
            raise ApiError(400, 'Billing context must be professional or facility.')
        values['billing_context'] = billing
    if not values:
        raise ApiError(400, 'Nothing to change.')
    try:
        ctx = jobs.change_context(encounter, request.user, values)
    except jobs.Refused as exc:
        raise ApiError(409, str(exc))
    return JsonResponse({'context_id': str(ctx.pk)}, status=201)


@require_POST
@api_view
def stop(request, encounter_id):
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    return JsonResponse({'stopped': jobs.stop_encounter(encounter, request.user)})


@require_POST
@api_view
def resume(request, encounter_id):
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    try:
        job = jobs.resume(encounter, request.user)
    except jobs.Refused as exc:
        raise ApiError(409, str(exc))
    if job is None:
        raise ApiError(409, 'There is no stopped stage to resume.')
    return JsonResponse({'resumed': job.kind}, status=201)


@require_POST
@api_view
def reconcile(request, encounter_id):
    data = _payload(request)
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    note = _text_field(data, 'note', 'The reconciliation note').strip()
    if len(note) < 12:
        raise ApiError(400, 'Describe how the unknown outcome was reconciled (at least 12 characters).')
    try:
        run = encounter.provider_runs.get(pk=data.get('provider_run_id'))
    except (models.ProviderRun.DoesNotExist, ValueError, ValidationError):
        raise ApiError(404, 'That provider request is not part of this document.')
    try:
        recorded = jobs.reconcile(encounter, run, request.user, note)
    except jobs.Refused as exc:
        raise ApiError(409, str(exc))
    if recorded is None:
        raise ApiError(409, 'Only an unreconciled unknown outcome can be reconciled.')
    return JsonResponse({'reconciled': str(run.pk)}, status=201)


@require_POST
@api_view
def create_report(request, encounter_id):
    data = _payload(request)
    encounter, membership = scoped_encounter(request.user, encounter_id)
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
        report = reports.generate(encounter, kind, fmt, request.user)
    except ValueError as exc:
        raise ApiError(409, str(exc))
    return JsonResponse(serializers._report_json(report), status=201)


@require_GET
@api_view
def download_report(request, report_id):
    try:
        report = models.ReportArtifact.objects.select_related('encounter').get(pk=report_id)
    except (models.ReportArtifact.DoesNotExist, ValueError, ValidationError):
        raise Http404()
    active_membership(request.user, report.encounter.workspace_id)
    content = bytes(report.content)
    content_type = 'text/csv; charset=utf-8' if report.fmt == 'csv' else 'text/plain; charset=utf-8'
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{report.filename}"'
    response['X-Content-SHA256'] = report.sha256
    return response


@require_GET
@api_view
def original(request, encounter_id):
    encounter, _ = scoped_encounter(request.user, encounter_id)
    source = encounter.files.order_by('uploaded_at').first()
    if source is None:
        raise Http404()
    data = read_original(source)
    response = HttpResponse(data, content_type=source.media_type)
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', source.original_name)[:120] or 'original'
    response['Content-Disposition'] = f'attachment; filename="{safe_name}"'
    response['X-Content-SHA256'] = source.sha256
    return response
