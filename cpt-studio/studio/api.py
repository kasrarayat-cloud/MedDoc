"""JSON API (API.md). Session auth; CSRF enforced on every POST by middleware.

Every handler resolves the caller's ACTIVE membership first and scopes every
row through it, so another workspace's records answer 404.

This is the CUSTOMER surface (CORE-UX-DESIGN.md 5, 7): every payload is built by studio.customer_api's allowlist, and
every refusal raised below this module reaches the member only through customer_api.customer_error (a fixed
vocabulary; no stored or exception text). The full record - providers, models, usage, runs, hashes, the trace, every
stored artifact - is a platform operator's, served under /ops/ by studio.operator.
"""
import functools
import json
import re
import uuid
from datetime import date

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import answers, audit, client_contract, customer_api, intake, jobs, models, reports, review
from .access import active_membership, scoped_encounter
from .ingest import canonicalize
from .storage import read_original

SETTINGS_CHOICES = {'hospital_outpatient', 'office', 'asc', 'inpatient', 'emergency', 'telehealth'}
BILLING_CHOICES = {'professional', 'facility'}
MAX_NOTE_CHARS = 2000
# PostgreSQL text cannot hold NUL, and a lone surrogate cannot be encoded at all.
UNSTORABLE = re.compile('[\x00\ud800-\udfff]')
CANDIDATE_ID = re.compile(r'[0-9a-f]{16}')  # studio.candidates: 16 hex of a sha256


def _storable(value, label):
    """Refuse text the database cannot store exactly, rather than altering what the member submitted."""
    if UNSTORABLE.search(value):
        raise ApiError(400, f'{label} contains a NUL character or an invalid Unicode code point; '
                            'remove it and try again.')
    return value


def _text_value(data, name, label):
    """A member-supplied text field: a string, or absent/null as ''. Any other JSON type is refused, never
    turned into its Python repr (API.md: invalid input answers 400 and is never altered)."""
    value = data.get(name)
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ApiError(400, f'{label} must be text.')
    return value


def _identifier(value):
    """A row identifier from the request body. A non-string is not an identifier: refused before the ORM, whose
    lookup recurses once per level of a nested list (a RecursionError, i.e. an HTML 500)."""
    if not isinstance(value, str):
        raise ValueError('not an identifier')
    return value


def _text_field(data, name, label):
    value = _storable(_text_value(data, name, label), label)
    if len(value) > MAX_NOTE_CHARS:
        raise ApiError(400, f'{label} can be at most {MAX_NOTE_CHARS} characters.')
    return value


class ApiError(Exception):
    def __init__(self, status, message, **details):
        super().__init__(message)
        self.status, self.message, self.details = status, message, details


def api_view(view=None, *, contract=True):
    """A customer API view: JSON errors, sign-in required, and - unless ``contract`` is False (a download, which is a
    browser navigation and sends no header of the page's) - the page build the client contract names
    (studio.client_contract, decision (l)): any other answers 409 client_outdated before the view runs."""
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
        except Http404:
            return JsonResponse({'error': 'Not found.'}, status=404)
        except PermissionDenied as exc:
            return JsonResponse({'error': customer_api.customer_error(str(exc)) if str(exc)
                                 else 'Your role cannot do that.'}, status=403)
        except review.AttestationRefused as exc:
            return JsonResponse({'error': customer_api.customer_error(' '.join(exc.messages))}, status=400)
        except ValidationError as exc:
            return JsonResponse({'error': customer_api.customer_error(' '.join(exc.messages))}, status=409)
        except RecursionError:  # a backstop: a nested value that reached code recursing per level
            return JsonResponse({'error': 'The request is nested too deeply.'}, status=400)
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


# The one form API.md documents. date.fromisoformat alone also reads a JSON number's str() ('20261020'), a basic date
# and an ISO week date ('2026-W43-2', or '2026-W43' as its Monday), dates the member never wrote (round 4, pipeline:6).
_PIPE_DATE = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')


def _parse_date(value, field):
    if value is None or value == '':
        return ''
    if not isinstance(value, str) or not _PIPE_DATE.fullmatch(value):
        raise ApiError(400, f'{field} must be a date in YYYY-MM-DD form.')
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ApiError(400, f'{field} must be a date in YYYY-MM-DD form.')


def _PIPE_choice(data, name, choices, message):
    """A listed string, or '' for null or '' (which clear the value). Any other JSON type is refused, never read as
    "no value" by its truthiness: 0, false, [] and {} cleared the member's value (round 4, pipeline:6)."""
    value = data.get(name)
    if value is None or value == '':
        return ''
    if not isinstance(value, str) or value not in choices:
        raise ApiError(400, message)
    return value


# P5 FLOW: the upload attempt's key, a UUID the page generates per attempt (8-4-4-4-12 hex digits).
_CLIENT_KEY = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}')


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
    return JsonResponse(customer_api.session_json(request.user, membership))


@api_view
def encounters(request):
    membership = active_membership(request.user)
    if request.method == 'GET':
        rows = membership.workspace.encounters.select_related(
            'current_revision', 'current_context', 'current_assessment').order_by('-created_at')
        return JsonResponse({'encounters': [customer_api.list_row(e) for e in rows]})
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
    # P5 FLOW: a repeated POST of the same upload attempt (its client_key, by the same member, within 24 h, of the same
    # document) answers with the encounter the first made - 201 with the same id - and creates nothing
    client_key = _client_key(request.POST.get('client_key'))
    pasted = '' if upload is not None else text
    try:
        encounter = intake.find_upload(user=request.user, workspace=membership.workspace, client_key=client_key,
                                       data=data, text=pasted)
        if encounter is None:
            encounter = intake.create_encounter(
                membership=membership, user=request.user, title=title, service_date=service_date, data=data,
                filename=filename, text=pasted, client_key=client_key)
    except intake.DuplicateUpload as exc:
        encounter = exc.encounter
    except intake.UploadKeyRefused as exc:
        raise ApiError(409, str(exc))
    except ValidationError as exc:
        raise ApiError(400, customer_api.customer_error(' '.join(exc.messages)))
    return JsonResponse({'id': str(encounter.pk)}, status=201)


@require_GET
@api_view
def encounter_detail(request, encounter_id):
    encounter, membership = scoped_encounter(request.user, encounter_id)
    return JsonResponse(customer_api.encounter_json(encounter, membership))


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
            proposal = encounter.current_assessment.proposals.get(pk=_identifier(data.get('proposal_id')))
        except (models.Proposal.DoesNotExist, ValueError, ValidationError):
            raise ApiError(404, 'That proposal is not part of the current review.')
        action = data.get('action')
        if not isinstance(action, str) or action not in review.ACTION_LABELS:
            raise ApiError(400, 'Unknown review action.')  # round 7 bypass:3: invalid input, never a state conflict
        # CORE-UX-DESIGN.md 4: the reviewer's ONE chosen modifier on an approval, "modifiers": [] | ["59"] | ["XS"];
        # a malformed choice is invalid input (400), one the code's modifier review does not offer is a conflict (409)
        try:
            modifiers = review._chosen_modifiers(data.get('modifiers'))
            decision = review.record_decision(
                encounter=encounter, proposal=proposal, action=action, user=request.user,
                membership=membership, note=_text_field(data, 'note', 'The note'),
                acknowledgement=_text_field(data, 'acknowledgement', 'The acknowledgement'), modifiers=modifiers)
        except review.ModifierRefused as exc:
            raise ApiError(400, ' '.join(exc.messages))
    # the customer decision shape (customer_api.decision_response: the contract's decision, modifiers included)
    return JsonResponse(customer_api.decision_response(decision), status=201)


@require_POST
@api_view
def confirm_finding(request, encounter_id, clarification_id):
    """A reviewer's confirmation of one verified candidate answer to an open question (HARNESS.md 11.3, 12.5):
    ``{"candidate_id", "attestation"}``. An owner or reviewer only (403); the question must be open on the current
    final assessment, unconfirmed, and the candidate one of its verified candidates, recomputed server-side (409 with
    why); the attestation exactly the candidate's (400). A service date then enters as the member's date through the
    context path; any other fact is read by a re-assessment. Nothing is approved.

    Refutation round 3 (HARNESS.md 12.10, D7): this release offers no reviewer confirmation. After the session and the
    encounter's workspace scoping (401, 404 as before), every request is refused (409) with
    review.CONFIRMATIONS_NOT_OFFERED before its body, the member's role, the question or the candidate is read; nothing
    is recorded."""
    encounter, membership = scoped_encounter(request.user, encounter_id)
    if not review.confirmations_offered():
        raise ApiError(409, customer_api.customer_error(review.CONFIRMATIONS_NOT_OFFERED))
    data = _payload(request)
    _require_reviewer(membership)
    if not encounter.clarifications.filter(pk=clarification_id).exists():
        raise ApiError(404, 'That question is not part of this document.')
    candidate_id = data.get('candidate_id')
    if not isinstance(candidate_id, str) or not CANDIDATE_ID.fullmatch(candidate_id):
        raise ApiError(400, "Choose one of the question's candidates (candidate_id).")
    attestation = _storable(_text_value(data, 'attestation', 'The attestation'), 'The attestation')
    if len(attestation) > MAX_NOTE_CHARS:
        raise ApiError(400, f'The attestation can be at most {MAX_NOTE_CHARS} characters.')
    try:
        confirmation, effect = review.confirm_finding(
            encounter=encounter, clarification_id=clarification_id, candidate_id=candidate_id,
            attestation=attestation, user=request.user, membership=membership)
    except jobs.Refused as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    # never who located the passage or which runs did (participant names, run ids): those are an operator's (/ops/)
    return JsonResponse({'id': str(confirmation.pk), 'clarification_id': str(confirmation.clarification_id),
                         'fact': confirmation.fact, 'value': confirmation.value,
                         'confirmed_by': confirmation.confirmed_by.label(),
                         'confirmed_by_kind': confirmation.confirmed_by.actor_kind,
                         'attestation': confirmation.attestation,
                         'created_at': confirmation.created_at.isoformat(),
                         'current_effect': customer_api.confirmation_effect(confirmation), 'effect': effect}, status=201)


@require_POST
@api_view
def addenda(request, encounter_id):
    data = _payload(request)
    with transaction.atomic():
        encounter, membership = scoped_encounter(request.user, encounter_id, for_update=True)
        _require_reviewer(membership)
        _attested(data.get('synthetic_attestation'))
        text = _storable(_text_value(data, 'text', 'The addendum'), 'The addendum').strip()
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
        answered = data.get('clarification_id')
        if answered is not None and answered != '':  # only no value means no clarification: 0, false, [] are refused
            try:
                clarification = encounter.clarifications.get(pk=_identifier(answered),
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
        values['setting'] = _PIPE_choice(data, 'setting', SETTINGS_CHOICES, 'Choose a listed care setting.')
    if 'billing_context' in data:
        values['billing_context'] = _PIPE_choice(data, 'billing_context', BILLING_CHOICES,
                                                 'Billing context must be professional or facility.')
    if not values:
        raise ApiError(400, 'Nothing to change.')
    try:
        ctx = jobs.change_context(encounter, request.user, values)
    except jobs.Refused as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    return JsonResponse({'context_id': str(ctx.pk)}, status=201)


@require_POST
@api_view
def details(request, encounter_id):
    """P5 FLOW: one save for the "A few details needed" rows, ``{"answers": [{"id", "fact", "value"}]}``
    (answers.save_details): context values through one context change and its re-assessment, "not documented" or
    "cannot confirm" stored as the member's answers. An owner or reviewer only; 400 for an answer a detail does not
    allow, 409 while processing runs or for a detail no longer asked. 201 when something was saved, 200 when the save
    changed nothing."""
    data = _payload(request)
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    try:
        saved = answers.save_details(encounter, request.user, data.get('answers'))
    except answers.InvalidAnswer as exc:  # answers.py's own fixed customer sentences
        raise ApiError(400, str(exc))
    except jobs.Refused as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    return JsonResponse(saved, status=201 if saved['saved'] else 200)


@require_POST
@api_view
def revoke_detail(request, encounter_id, answer_id):
    """P5 FLOW: withdraw one saved answer (answers.revoke_answer); the detail is asked again. 404 for an answer that is
    not this document's, 409 while processing runs or for an answer already withdrawn."""
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    try:
        revocation = answers.revoke_answer(encounter, request.user, answer_id)
    except models.MemberAnswer.DoesNotExist:
        raise Http404()
    except jobs.Refused as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    return JsonResponse({'revoked': str(revocation.answer_id)}, status=201)


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
        raise ApiError(409, customer_api.customer_error(str(exc)))
    if job is None:
        raise ApiError(409, 'There is no stopped stage to resume.')
    return JsonResponse({'resumed': True}, status=201)  # never the stage's kind: kinds name the participants


@require_POST
@api_view
def second_review(request, encounter_id):
    """Ask for the one bounded second review of the current assessment (ARCHITECTURE 5.11): a workspace owner or
    reviewer asks; an assessment never queues one (owner decision 2026-10-27)."""
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    try:
        jobs.request_second_review(encounter, request.user)
    except jobs.Refused as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    return JsonResponse({'second_review': 'queued'}, status=201)


@require_POST
@api_view
def create_report(request, encounter_id):
    """A customer report (cpt-studio-customer-report@1): ``{"kind": "draft"|"approved", "fmt": "txt"|"csv"}`` - the
    suggested codes, or the approved items only. 'reviewed', the name the page used before, is read as 'approved'.
    The operator's full report is made at /ops/ (studio.operator)."""
    data = _payload(request)
    encounter, membership = scoped_encounter(request.user, encounter_id)
    kind, fmt = str(data.get('kind', '')), str(data.get('fmt', ''))
    kind = reports.APPROVED if kind == models.ReportArtifact.REVIEWED else kind
    if kind not in reports.CUSTOMER_KINDS or fmt not in {'txt', 'csv'}:
        raise ApiError(400, 'Choose a draft or an approved export as TXT or CSV.')
    if encounter.current_assessment_id is None:
        raise ApiError(409, 'There is nothing to export yet.')
    if kind == reports.APPROVED:
        ready = customer_api.readiness(encounter)
        if not ready['approved']:
            raise ApiError(409, 'The approved export is not available yet.', blockers=ready['blockers'])
    try:
        report = reports.generate_customer(encounter, kind, fmt, request.user)
    except reports.CustomerExportNotReady as exc:  # its blockers are customer_api.readiness's, already worded
        raise ApiError(409, 'The approved export is not available yet.', blockers=exc.blockers)
    except ValueError as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    return JsonResponse(customer_api.report_json(report), status=201)


@require_GET
@api_view(contract=False)
def download_report(request, report_id):
    """A customer artifact of the caller's workspace, as stored (no sha256 header). Any other artifact - an operator's,
    or one recorded before the audience existed, which names the review participants - answers 404; an approved export
    that no longer matches the persisted decisions answers 409."""
    try:
        report = models.ReportArtifact.objects.select_related('encounter').get(pk=report_id)
    except (models.ReportArtifact.DoesNotExist, ValueError, ValidationError):
        raise Http404()
    active_membership(request.user, report.encounter.workspace_id)
    if report.audience != models.ReportArtifact.CUSTOMER:
        raise Http404()
    if report.kind == reports.APPROVED and not reports.customer_artifact_current(report):
        raise ApiError(409, customer_api.STALE_EXPORT)
    content = bytes(report.content)
    content_type = 'text/csv; charset=utf-8' if report.fmt == 'csv' else 'text/plain; charset=utf-8'
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{report.filename}"'
    return response


@require_GET
@api_view(contract=False)
def original(request, encounter_id):
    encounter, _ = scoped_encounter(request.user, encounter_id)
    source = encounter.files.order_by('uploaded_at').first()
    if source is None:
        raise Http404()
    data = read_original(source)
    response = HttpResponse(data, content_type=source.media_type)
    safe_name = re.sub(r'[^A-Za-z0-9._-]+', '_', source.original_name)[:120] or 'original'
    response['Content-Disposition'] = f'attachment; filename="{safe_name}"'
    return response  # no sha256 header for a customer (an operator's /ops/ download carries it)
