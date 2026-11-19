"""JSON API (API.md). Session auth; CSRF enforced on every POST by middleware.

Every handler resolves the caller's ACTIVE membership first and scopes every
row through it, so another workspace's records answer 404.

This is the CUSTOMER surface (CORE-UX-DESIGN.md 5, 7): every payload is built by studio.customer_api's allowlist, and
every refusal raised below this module reaches the member only through customer_api.customer_error (a fixed
vocabulary; no stored or exception text). The full record - providers, models, usage, runs, hashes, the trace, every
stored artifact - is a platform operator's, served under /ops/ by studio.operator.

FINAL-V2 amendment 1 (step 5d; D208): the codes are updated automatically after a save. A context save answers what it did
(1.3 [R:truth-T13]: 200 ``unchanged`` with nothing written, 201 ``updating``, 201 ``restored``); an addendum is accepted
while processing runs (A1), refused as a duplicate of the current revision's own (A13) and, before anything is written,
when the document or the document with it could not be read in one piece or prepared for reading (A12, the sentence by
where the cause is [R2:truth-RT7]); while an update is pending a new export answers 409 UPDATE_EXPORT (8.1) and every
decision 409 UPDATE_DECISION (review.record_decision, 5.3); an export that is not current is downloaded as an EARLIER
export with its banner, never refused (8.3, A9); and a failed update's document review is retried by one recorded member
act (POST .../retry-update, 7.2, A10).
"""
import functools
import json
import re
import uuid
from datetime import date
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import answers, audit, client_contract, customer_api, intake, jobs, models, reports, review
from .access import active_membership, scoped_encounter
from .interpretation import readers, sentinel
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
        except sentinel.Tripped as exc:
            # a new-path write the legacy-call sentinel refused (design/FINAL.md 10.3): nothing was written, the trip is
            # audited, and the member is told so in CPT Studio's own sentence (no module, provider or model is named)
            return JsonResponse({'error': customer_api.customer_error(str(exc))}, status=409)
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
        # R-6: each encounter's row read under its own label (readers.labelled), in a request that names no encounter
        return JsonResponse({'encounters': [readers.labelled(customer_api.list_row, e) for e in rows]})
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
    try:
        return _decisions(request, encounter_id, data)
    except sentinel.Tripped as exc:
        # FINAL 10.3: the decision's gate refused it inside this request's transaction, which rolled the gate's audit
        # row back with everything else: recorded again now, outside it, so the refusal is on record
        encounter = models.Encounter.objects.select_related('workspace').filter(pk=encounter_id).first()
        if encounter is not None:
            readers.record_trip(encounter, request.user, exc.data)
        raise


def _decisions(request, encounter_id, data):
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


def _unframed(text, pages) -> bool:
    """Whether ``text`` with ``pages`` fails the pure framing check (FINAL-V2 1.2 rule 8, contract/extract_prompt.unframed:
    run here, in the web process, without the interpreter adapter, whose key the worker alone holds - D14), the pages
    tiled as the reading tiles them (jobs._participant_pages: the last page runs to the end of the text). A check that
    cannot be made is a failure (fail-closed)."""
    from .interpretation.contract import extract_prompt  # local import: the reading's own pure check

    try:
        return extract_prompt.unframed(text, jobs._participant_pages(SimpleNamespace(text=text, pages=pages))) is not None
    except (TypeError, ValueError):
        return True


def _addendum_refusal(parent, combined):
    """FINAL-V2 amendment 1, 1.4 (A12 [R:truth-T7]; the sentence names where the cause is [R2:truth-RT7]): the customer
    sentence that refuses an addendum to ``parent`` whose combined text would be ``combined``, or '' when it may be added.
    The document's own text is checked first, alone: over the character bound, its pages over the page bound (an
    addendum revision carries its parent's pages), or a text that cannot be framed - then no addendum can pass, and the
    refusal says so (ADDENDUM_DOCUMENT_TOO_LONG, ADDENDUM_DOCUMENT_UNPREPARED); else the combined text over the
    character bound or one that cannot be framed (ADDENDUM_TOO_LONG, ADDENDUM_UNPREPARED). Such an addendum's update could
    never finish (the reading refuses the size, C5 forbids a member's paid retry, and no restore exists across
    revisions), so it is refused before the revision is recorded and before any decision is invalidated. The test-only
    v1 chain reads no such refusal (jobs._framing_refusal's rule)."""
    if jobs._v1_chain():
        return ''
    if jobs._size_bound(parent):
        return customer_api.ADDENDUM_DOCUMENT_TOO_LONG
    if _unframed(parent.text or '', list(parent.pages or ())):
        return customer_api.ADDENDUM_DOCUMENT_UNPREPARED
    if len(combined) > settings.INTERPRET_MAX_CHARS:
        return customer_api.ADDENDUM_TOO_LONG
    if _unframed(combined, list(parent.pages or ())):
        return customer_api.ADDENDUM_UNPREPARED
    return ''


@require_POST
@api_view
def addenda(request, encounter_id):
    """A physician's addendum: a new revision of the document, whose pipeline starts at once. FINAL-V2 amendment 1: no
    busy refusal (A1: a stage of the earlier revision still queued ends superseded at its start, 3.4); refused (409),
    under the row lock and before anything is written, as a duplicate of the current revision's own addendum (A13,
    ADDENDUM_DUPLICATE) and when its update could never finish (A12, _addendum_refusal). No addendum refusal says the
    codes shown stay as they are: an addendum is accepted during a first processing too, when no codes are shown."""
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
        parent = encounter.current_revision
        if (parent is not None and parent.kind == models.SourceRevision.ADDENDUM
                and (parent.addendum_text or '').strip() == text):
            # A13 (3.9): a double click or a second tab - the documentation is the current revision's own already, read
            # before its text is extracted (the second click arrives while the first one's revision is being read)
            raise ApiError(409, customer_api.ADDENDUM_DUPLICATE.format(n=parent.number))
        if parent is None or parent.extraction_status not in {models.SourceRevision.OK, models.SourceRevision.PARTIAL}:
            raise ApiError(409, 'This document has no extracted text to add to.')
        number, now = encounter.revisions.count() + 1, timezone.now()
        combined_text = canonicalize(parent.text + jobs.addendum_block_text(number, now, text))
        refusal = _addendum_refusal(parent, combined_text)
        if refusal:
            raise ApiError(409, refusal)
        combined = len(combined_text)
        if combined > settings.MAX_PASTE_CHARS:
            raise ApiError(400, f'With this addendum the document would have {combined:,} characters; '
                                f'the limit is {settings.MAX_PASTE_CHARS:,}.')
        clarification = None
        answered = data.get('clarification_id')
        if answered is not None and answered != '':  # only no value means no clarification: 0, false, [] are refused
            if answers.is_detail_id(answered):
                # the customer page sends its details row's id (API.md: the customer contract): the open confirmation
                # row it names, answering the stored clarification that row shows, if any
                found, clarification = answers.addendum_detail(encounter, answered)
                if not found:
                    raise ApiError(404, 'That detail is not open on this document.')
            else:
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
    # The walk round (2026-11-07, finding 7): the revision's number, never its internal id - a customer surface carries
    # no identifier the operator view holds (ops/verification/customer-contract.json's deny values; API.md)
    return JsonResponse({'revision': revision.number}, status=201)


@require_POST
@api_view
def context(request, encounter_id):
    """A context save (FINAL-V2 amendment 1, 1.3 [R:truth-T13]): ``{"service_date", "setting", "billing_context"}``,
    any of them. Compared under the row lock with the SAVED values (jobs.change_context): a save that changes nothing
    writes nothing and answers 200 ``{"context_id", "unchanged": true, "updating"}``; a change answers 201 ``{"context_id",
    "updating"}`` (``updating``: an update of codes the member was shown is pending after it); a save of the earlier
    codes' own values that made them current again answers 201 ``{"context_id", "updating": false, "restored": true}``.
    ``context_id`` is the encounter's current context after the save (null while it has none). 409 with why for each
    refusal (A12, A18, A19, the extraction not finished)."""
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
        saved = jobs.change_context(encounter, request.user, values)  # ContextSave (amendment 1, 2.7)
    except jobs.Refused as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    context_id = str(saved.context.pk) if saved.context is not None else None
    if saved.unchanged:
        return JsonResponse({'context_id': context_id, 'unchanged': True, 'updating': bool(saved.updating)})
    if saved.restored:
        return JsonResponse({'context_id': context_id, 'updating': False, 'restored': True}, status=201)
    return JsonResponse({'context_id': context_id, 'updating': bool(saved.updating)}, status=201)


@require_POST
@api_view
def details(request, encounter_id):
    """P5 FLOW: one save for the "A few details needed" rows, ``{"answers": [{"id", "fact", "value"}]}``
    (answers.save_details): context values through one context change and its update, "not documented" or "cannot
    confirm" stored as the member's answers. An owner or reviewer only; 400 for an answer a detail does not allow, 409
    for an answer while processing runs or an update is pending (FINAL-V2 amendment 1, 1.4: a save of context values
    alone is accepted then), for a detail no longer asked, and for a context save jobs.change_context refuses. 201 when
    something was saved, 200 when the save changed nothing; ``reassessing`` when an update is pending after it or a
    recompute was queued, ``restored`` when it made the earlier codes current again (1.3 [R:truth-T13])."""
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
def retry_reading(request, encounter_id):
    """The recorded retry of a failed reading (design/FINAL.md 11.3; D11): an owner or a reviewer asks for one more
    attempt at the current document's reading (jobs.retry_reading: the failed attempt released for that one attempt,
    audited 'interpretation.retry'). 409, with why in the member's words, while processing runs or an earlier outcome is
    unknown, when the document was read or never attempted, while reading is paused on this installation, and for an
    answer cut off at its output limit - never a member's paid retry (C5): the override of that is an operator's,
    recorded, under /ops/. Nothing is sent here; the attempt is a stage of its own."""
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    try:
        jobs.retry_reading(encounter, request.user)
    except jobs.Refused as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    return JsonResponse({'retrying': True}, status=201)  # never the stage's kind


@require_POST
@api_view
def retry_update(request, encounter_id):
    """FINAL-V2 amendment 1, 7.2 (A10): the recorded retry of a failed update - one more attempt at the document review
    that failed with a status no provider hold reads (a 5xx, another 4xx, a transport failure: its failed run released
    for that one attempt), at one never sent for a local reason, or at a failed stage that sends nothing - by an owner or
    a reviewer (jobs.retry_update, audited 'update.retry'). 409, with why in the member's words, while processing runs,
    when no update failed (RETRY_UPDATE_NOTHING), while an outcome is unknown, while the coding service's hold stands
    (RETRY_UPDATE_HELD), for a failed reading (RETRY_UPDATE_READING: Try reading again serves it) and for a request the
    coding service refused before (RETRY_UPDATE_REFUSED_BEFORE). Nothing is sent here; the attempt is a stage of its
    own."""
    encounter, membership = scoped_encounter(request.user, encounter_id)
    _require_reviewer(membership)
    try:
        jobs.retry_update(encounter, request.user)
    except jobs.Refused as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    return JsonResponse({'retrying': True}, status=201)  # never the stage's kind


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


def _update_export_refusal(encounter):
    """ApiError 409 UPDATE_EXPORT (its check form for an update no save started) with the update's customer blockers
    while an update of ``encounter``'s codes is pending (FINAL-V2 amendment 1, 8.1 and 5.3), else None."""
    refused = reports.update_refusal(encounter)
    if refused is None:
        return None
    blockers = customer_api.readiness(encounter)['blockers']
    return ApiError(409, refused.message, blockers=blockers or refused.blockers)


@require_POST
@api_view
def create_report(request, encounter_id):
    """A customer report (cpt-studio-customer-report@2): ``{"kind": "draft"|"approved", "fmt": "txt"|"csv"}`` - the
    suggested codes, or the approved items only, each export stating the revision, the details and the time its codes
    were made (FINAL-V2 amendment 1, 8.2). 'reviewed', the name the page used before, is read as 'approved'. While an
    update of the codes is pending neither kind is made: 409 UPDATE_EXPORT before the export is generated, and again
    under the encounter's lock (8.1), nothing written. The operator's full report is made at /ops/ (studio.operator)."""
    data = _payload(request)
    encounter, membership = scoped_encounter(request.user, encounter_id)
    kind, fmt = str(data.get('kind', '')), str(data.get('fmt', ''))
    kind = reports.APPROVED if kind == models.ReportArtifact.REVIEWED else kind
    if kind not in reports.CUSTOMER_KINDS or fmt not in {'txt', 'csv'}:
        raise ApiError(400, 'Choose a draft or an approved export as TXT or CSV.')
    if encounter.current_assessment_id is None:
        raise ApiError(409, 'There is nothing to export yet.')
    refused = _update_export_refusal(encounter)
    if refused is not None:
        raise refused
    if kind == reports.APPROVED:
        ready = customer_api.readiness(encounter)
        if not ready['approved']:
            raise ApiError(409, 'The approved export is not available yet.', blockers=ready['blockers'])
    try:
        report = reports.generate_customer(encounter, kind, fmt, request.user)
    except reports.CustomerExportNotReady as exc:  # its blockers are customer_api.readiness's, already worded
        if exc.updating:  # a save between the request's read and the lock (8.1)
            raise _update_export_refusal(encounter) or ApiError(409, exc.message, blockers=exc.blockers)
        raise ApiError(409, 'The approved export is not available yet.', blockers=exc.blockers)
    except ValueError as exc:
        raise ApiError(409, customer_api.customer_error(str(exc)))
    return JsonResponse(customer_api.report_json(report), status=201)


@require_GET
@api_view(contract=False)
def download_report(request, report_id):
    """A customer artifact of the caller's workspace (no sha256 header). Any other artifact - an operator's, or one
    recorded before the audience existed, which names the review participants - answers 404. FINAL-V2 amendment 1, 8.3
    (A9 [R:races-R1][R:truth-T1][R:legacy-L1]): a CURRENT artifact (its marker matches the encounter's and no update is
    pending: reports.customer_artifact_current) is served exactly as stored; any other - either kind, either format,
    @1 included - is served as an EARLIER export (reports.earlier_download: its banner, then the stored bytes, under the
    stored name with '-earlier'), never refused: historical reports are preserved, and the banner keeps one from being
    presented as current. The stored artifact is never changed."""
    try:
        report = models.ReportArtifact.objects.select_related('encounter', 'assessment__revision').get(pk=report_id)
    except (models.ReportArtifact.DoesNotExist, ValueError, ValidationError):
        raise Http404()
    active_membership(request.user, report.encounter.workspace_id)
    if report.audience != models.ReportArtifact.CUSTOMER:
        raise Http404()
    if reports.customer_artifact_current(report):
        content, filename = bytes(report.content), report.filename
    else:
        content, filename = reports.earlier_download(report)
    content_type = 'text/csv; charset=utf-8' if report.fmt == 'csv' else 'text/plain; charset=utf-8'
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
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
