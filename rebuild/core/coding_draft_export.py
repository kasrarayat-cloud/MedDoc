"""Inspection-only Word variant of a completed synthetic Corti replay.

This reads retained selections and evidence. It cannot submit a provider task,
generate answers, accept a code or change the separate approved export.
"""
import hashlib
from datetime import date

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from . import coding_service as service
from .coding_export import DRAFT_TAG, append_review
from .corti_coding import CONTRACT as CORTI_CONTRACT, SYSTEMS, terminology
from .corti_response import adapt_response
from .models import CodingDecision, CodingRun, Encounter
from .security import audit, membership, private_path, scoped

CONTRACT = 'synthetic-retained-coding-draft-v1'
TITLE = 'Synthetic draft coding review — not approved'
TERM_STATUS = {
    'unavailable': 'No authoritative dated reference is available for the service date.',
    'unauthorized': 'Reference use authorization is unverified.',
    'version_unavailable': 'No authorized terminology release covers the service date.',
    'ambiguous_release': 'The applicable terminology release is ambiguous.',
    'unknown_code': 'The code is absent from the applicable authorized release.',
}


def draft_review(encounter):
    """Return a deliberately narrow projection; raw display text never enters it."""
    if (not settings.SYNTHETIC_ONLY or encounter.status != 'finalized'
            or encounter.template_version.template.format.lower() != 'docx'):
        raise ValidationError('This draft is available only for finalized synthetic Word encounters.')
    key = service.input_snapshot(encounter)[3]
    run = CodingRun.objects.filter(encounter=encounter, input_digest=key).first()
    if run is None:
        raise ValidationError('A completed replay for the current saved revision is required.')
    service.assert_current(run, encounter)
    if (run.config.get('provider') != 'corti' or run.config.get('mode') != 'replay'
            or run.result.get('replay') is not True or run.result.get('contract') != CORTI_CONTRACT):
        raise ValidationError('This draft is restricted to retained Corti synthetic replay results.')
    decisions = list(CodingDecision.objects.filter(run=run)[:2])
    if len(decisions) > 1:
        raise ValidationError('The saved coding decision is ambiguous.')
    decision = decisions[0] if decisions else None
    if decision and (decision.input_digest != key or decision.selection_digest != service.selection_digest(run)
                     or decision.selections != run.selection):
        raise ValidationError('The saved coding decision no longer matches this revision.')
    terms, _ = terminology(run)
    parsed = adapt_response(run.result.get('adapter', {}).get('diagnostics', {}).get('provider_response'),
        run.result.get('provider_request'), service_date=date.fromisoformat(run.inputs['service_date']), terminology=terms)
    saved = {row['id']: row for row in run.result.get('suggestions', [])}
    proposals = parsed['proposed_selections']
    if (len(saved) != len(run.result.get('suggestions', []))
            or set(saved) != {row['id'] for row in proposals}):
        raise ValidationError('Retained selected codes do not match the saved review.')
    paragraphs = [(TITLE, True),
        ('Fictional encounter. Retained-response replay; no new prediction was requested. '
         'This inspection draft is not an approved coding document and must not be used for billing.', False),
        ('Service date: ' + encounter.service_date.isoformat(), False),
        ('The finalized clinical document is preserved before this appendix. '
         'Provider candidates and alternatives are excluded. Exact quotations do not establish clinical applicability.', False)]
    rows = []
    for proposal in proposals:
        row, term = saved[proposal['id']], proposal['terminology']
        system = SYSTEMS[proposal['system']]
        if row.get('code') != proposal['code'] or row.get('system') != system:
            raise ValidationError('A retained code differs from its saved review.')
        selected = proposal['id'] in run.selection.get('selected_ids', [])
        if row.get('eligible') is not True or term['status'] != 'verified' or proposal['evidence_status'] != 'valid':
            status = 'Held — excluded from approved export.'
        elif decision:
            status = ('Accepted in the separate saved approval.' if selected else 'Rejected in the saved review.')
        else:
            status = ('Saved selection — approval pending.' if selected else 'Not selected — no saved approval.')
        paragraphs.extend([(system + ' ' + proposal['code'] + ' — provider-selected suggestion', True),
                           ('Decision status: ' + status, False)])
        if term['status'] == 'verified':
            paragraphs.extend([('Verified reference description: ' + term['description'], False),
                ('Reference: ' + term['source'] + '; release ' + term['version'] + '; effective '
                 + term['effective_from'] + ' through ' + term['effective_until'] + '.', False)])
        else:
            paragraphs.append(('Description withheld — unverified. ' + TERM_STATUS.get(term['status'],
                'Dated terminology verification is unresolved.'), False))
            if system == 'CPT':
                paragraphs.append(('CPT verification remains unresolved: an authoritative descriptor and E/M selection criteria, '
                    'with source attribution, terminology release and effective dates covering this service date, are required. '
                    'Clinician acceptance cannot establish terminology verification. Commercial-use rights are a separate requirement.', False))
        spans = [span for span in proposal['evidence'] if span['status'] == 'valid']
        paragraphs.append(('Supporting evidence: ' + ('exact retained source spans.' if spans else 'no valid source spans available.'), False))
        for span in spans:
            paragraphs.append((span['text'], False))
            paragraphs.append((f"Context {span['context_index']}; characters {span['start']}–{span['end']}. Exact source match; clinical applicability requires review.", False))
        if proposal['evidence_status'] != 'valid':
            paragraphs.append(('Supporting evidence is incomplete or invalid; the suggestion remains held.', False))
        rows.append({'id': proposal['id'], 'system': system, 'code': proposal['code'], 'decision_status': status,
                     'terminology_status': term['status'], 'valid_evidence_count': len(spans)})
    if not rows:
        raise ValidationError('No retained selected codes are available for this draft.')
    return run, decision, rows, paragraphs


def _materialize(encounter, run, decision, paragraphs, original):
    binding = service.digest({'contract': CONTRACT, 'original_sha256': encounter.export_sha256,
        'run': str(run.pk), 'input_digest': run.input_digest, 'selection_digest': service.selection_digest(run),
        'decision': str(decision.pk) if decision else None, 'paragraphs': paragraphs})
    path = private_path(f'exports/coding-draft/{encounter.pk}/{binding}.docx')
    for directory in (path.parent.parent, path.parent):
        directory.mkdir(exist_ok=True, mode=0o700)
    output = append_review(original, paragraphs, tag=DRAFT_TAG)
    expected = hashlib.sha256(output).hexdigest()
    try:
        with path.open('xb') as handle:
            path.chmod(0o600)
            handle.write(output)
    except FileExistsError:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValidationError('The retained draft failed its integrity check.')
    return path, expected


@login_required
@never_cache
@require_GET
@transaction.atomic
def export_synthetic_coding_draft(request, pk):
    if not settings.SYNTHETIC_ONLY:
        raise Http404
    encounter = get_object_or_404(scoped(Encounter, request.user).select_for_update(of=('self',))
        .select_related('patient', 'department', 'template_version__template'), pk=pk, status='finalized')
    membership(request.user, encounter.department, roles=['owner', 'clinician'])
    try:
        run, decision, rows, paragraphs = draft_review(encounter)
        original = private_path(encounter.export_path).read_bytes()
        if hashlib.sha256(original).hexdigest() != encounter.export_sha256:
            raise ValidationError('The original finalized export failed its integrity check.')
        path, sha256 = _materialize(encounter, run, decision, paragraphs, original)
    except (ValidationError, OSError, ValueError, TypeError, KeyError) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else 'The retained synthetic draft could not be verified or stored.'
        return HttpResponse(message, status=409, content_type='text/plain')
    audit(request.user, 'encounter.export_synthetic_coding_draft', encounter.pk, department=encounter.department,
        run_id=str(run.pk), input_digest=run.input_digest, selection_digest=service.selection_digest(run),
        original_sha256=encounter.export_sha256, export_sha256=sha256, selected_suggestion_count=len(rows),
        approved_export=False, synthetic_replay=True)
    return FileResponse(path.open('rb'), as_attachment=True,
        filename=f'quillmd-{str(encounter.pk)[:8]}-synthetic-draft-not-approved.docx')
