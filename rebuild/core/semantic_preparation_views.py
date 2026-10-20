"""Department-scoped, explicit clinician review of reusable answer definitions."""
import secrets
from copy import deepcopy
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from . import template_review
from django.views.decorators.http import require_GET, require_POST
from documents.semantic_preparation_roles import (
    CONSTRAINT_KEYS, POLARITIES, SUBJECTS, TEMPORALITIES, VALUE_TYPES, ANSWER_TYPES, ANSWER_MODES, DefinitionError,
    destination, protected_field,
)
from . import semantic_preparation as workflow
from .field_location import describe
from .models import Template, TemplateVersion, TemplateDefinitionPreparation
from .security import departments, membership, scoped
from .save_recovery import recoverable_save, binding as save_binding


def selected(request, pk):
    prep = get_object_or_404(TemplateDefinitionPreparation.objects.select_related('source_version__template'),
        pk=pk, source_version__template__department__in=departments(request.user))
    member = membership(request.user, prep.source_version.template.department)
    return prep, member


def revision(request):
    raw = request.POST.get('revision', '')
    if not raw.isdecimal() or len(raw) > 10:
        raise ValidationError('Reload the current definition revision.')
    return int(raw)


def posted_definitions(prep, post):
    """Destination is code controlled; no user/model location mutation is accepted."""
    values = {}
    version = workflow.definition_version(getattr(prep, 'config', {}))
    for field in prep.source_version.fields:
        prefix = 'field_'+field['key']+'_'
        values[field['key']] = {'version': version, 'meaning': post.get(prefix+'meaning', ''),
            'value_type': post.get(prefix+'value_type', ''), 'unit': post.get(prefix+'unit', '').strip() or None,
            'choices': [choice for choice in post.get(prefix+'choices', '').splitlines() if choice],
            'scope': {name: post.get(prefix+name, '') for name in ('subject', 'temporality', 'polarity')},
            'permitted_destination': destination(field),
            'constraints': {name: post.get(prefix+name, '').strip() or None for name in CONSTRAINT_KEYS}}
        if version in (2, 3, 4): values[field['key']]['answer_mode'] = post.get(prefix+'answer_mode', '')
        if version in (3, 4): values[field['key']]['patient_name_requirement'] = post.get(prefix+'patient_name_requirement', '')
        if version == 4:
            # The component contract is shown and bound in the signed review,
            # never accepted from hidden browser JSON.
            retained = getattr(prep, 'component_baseline', None)
            if retained is None:
                retained = workflow.corrected_definitions(prep)
            values[field['key']]['component_contract'] = deepcopy(retained.get(field['key'], {}).get('component_contract'))
    return values


def context(prep, member, *, definitions=None, error='', post=None):
    retained = workflow.corrected_definitions(prep)
    values = retained if definitions is None else definitions
    identity_issues = workflow.review_issues(prep, retained) if retained else {}
    proposed = {row['field_key']: row for row in prep.proposal.get('fields', [])}
    checked = {row['field_key']: row for row in prep.checker.get('fields', [])}
    rows = [{'field': field, 'definition': retained.get(field['key']), 'location': describe(field),
             'protected': protected_field(field), 'proposal': proposed.get(field['key']),
             'checker': checked.get(field['key']),
             'state': 'unresolved' if field['key'] in identity_issues else '',
             'reason': identity_issues.get(field['key'], ''),
             'name_subject': post.get('name_subject_'+field['key'], '') if post else '',
             'name_other': post.get('name_other_'+field['key'], '') if post else '',
             'decision': post.get('decision_'+field['key'], '') if post else '',
             'name_question_type': retained.get(field['key'], {}).get('value_type'),
             'reviewed': bool(post and field['key'] in post.getlist('reviewed_field'))}
            for field in prep.source_version.fields]
    reviewed_keys = workflow.fully_reviewed_keys(prep)
    for row in rows:
        if not prep.corrections or (workflow.definition_version(prep.config) == 4 and row['field']['key'] not in reviewed_keys):
            proposal, checker = row['proposal'] or {}, row['checker'] or {}
            if proposal.get('state') == 'unresolved' or checker.get('state') == 'unresolved' or proposal.get('definition') != checker.get('definition'):
                row['state'] = 'unresolved'
                row['reason'] = row['reason'] or checker.get('reason') or proposal.get('reason') or 'The independent definitions differ. Confirm which meaning belongs here.'
    if workflow.definition_version(prep.config) == 4 and member.role in ('owner', 'clinician') and prep.state in workflow.EDITABLE:
        for row in rows:
            row['components_edit_url'] = reverse('template_definitions_components', args=[prep.pk, row['field']['key']])
    baseline_rows = template_review.review_items(prep, rows)
    rows = [{**r, 'definition':values.get(r['field']['key'])} for r in baseline_rows]
    receipts = list(prep.ai_stage_receipts.order_by('created_at'))
    return {**template_review.tokens(prep, baseline_rows, getattr(member, 'user_id', None)),
        'save_binding': save_binding(prep, 'definitions'),
        'review_rows': template_review.rows(rows, template_review.label_displays(prep.source_version.template)) if values else [], 'preview_token': secrets.token_hex(24),
        'review_save_url': reverse('template_definitions_correct', args=[prep.pk]),
        'review_approve_url': reverse('template_definitions_approve', args=[prep.pk]),
        'template': prep.source_version.template, 'source_version': prep.source_version,
        'preparation': prep, 'layout_preparation':prep.source_version.preparation, 'definition_rows': rows, 'receipts': receipts,
        'provider_cost': sum((row.actual_cost or Decimal('0') for row in receipts), Decimal('0')),
        'provider_cost_unknown': any(row.actual_cost is None for row in receipts),
        'can_edit': member.role in ('owner', 'clinician') and prep.state in workflow.EDITABLE,
        'can_approve': member.role in ('owner', 'clinician') and prep.state == 'review' and not any(r['state']=='unresolved' for r in rows),
        'can_retry': member.role in ('owner','clinician') and prep.state=='blocked'
            and prep.error_code!='provider_unknown'
            and all(row.state in ('succeeded','failed') and row.actual_cost is not None for row in receipts),
        'definition_version':workflow.definition_version(prep.config), 'answer_modes':ANSWER_MODES,
        'value_types': ANSWER_TYPES if workflow.definition_version(prep.config) in (2, 3, 4) else VALUE_TYPES, 'subjects': SUBJECTS, 'temporalities': TEMPORALITIES, 'polarities': POLARITIES,
        'error': error, 'correction_reason': post.get('correction_reason', '') if post else '',
        'approved_version': prep.versions.order_by('number').first() if prep.state == 'approved' else None}


@require_POST
def start(request, pk):
    template = get_object_or_404(scoped(Template, request.user), pk=pk)
    membership(request.user, template.department, roles=['owner', 'clinician'])
    source = get_object_or_404(TemplateVersion, pk=request.POST.get('source_version'), template=template)
    try:
        prep = workflow.create_preparation(source, request.user, retry_of=request.POST.get('retry_of') or None)
    except (ValidationError, DefinitionError) as exc:
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        return HttpResponse(message, status=409, content_type='text/plain')
    return redirect('template_definitions', pk=prep.pk)


@require_GET
def detail(request, pk):
    prep, member = selected(request, pk)
    return render(request, 'template_semantic_preparation.html', context(prep, member))


@require_GET
def status(request, pk):
    prep, _ = selected(request, pk)
    result = JsonResponse({'state': prep.state, 'revision': prep.revision, 'error_code': prep.error_code,
        'stages': [{'stage': row.stage, 'state': row.state, 'attempt': row.attempt,
                    'actual_cost': str(row.actual_cost) if row.actual_cost is not None else None}
                   for row in prep.ai_stage_receipts.order_by('created_at')]})
    result['Cache-Control'] = 'no-store, private'
    return result


@recoverable_save('definitions')
@require_POST
def corrections(request, pk):
    prep, member = selected(request, pk)
    membership(request.user, prep.source_version.template.department, roles=['owner', 'clinician'])
    values = posted_definitions(prep, request.POST)
    try:
        reviewed = request.POST.getlist('reviewed_field')
        reason = request.POST.get('correction_reason', '')
        if request.POST.get('compact_review') == 'on':
            values, reviewed, reason = template_review.submitted(prep, context(prep, member)['definition_rows'], request.user, request.POST, 'save')
        workflow.correct(prep.pk, request.user, revision(request), values, reviewed, reason)
    except (ValidationError, DefinitionError) as exc:
        prep.refresh_from_db()
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        return render(request, 'template_semantic_preparation.html',
            context(prep, member, definitions=deepcopy(values), error=message, post=request.POST), status=409)
    return redirect('template_definitions', pk=pk)


@require_POST
def approval(request, pk):
    prep, member = selected(request, pk)
    membership(request.user, prep.source_version.template.department, roles=['owner', 'clinician'])
    try:
        current_rows = context(prep, member)['definition_rows']
        if any(r['state'] == 'unresolved' for r in current_rows):
            raise ValidationError('Resolve and save the open questions before approving this template.')
        reviewed = request.POST.getlist('approved_field')
        original_seen = request.POST.get('original_reviewed') == 'on'
        if request.POST.get('compact_review') == 'on':
            _, reviewed, _ = template_review.submitted(prep, current_rows, request.user, request.POST, 'approve')
            original_seen = True  # Explicit snapshot-bound summary consent above.
        workflow.approve(prep.pk, request.user, revision(request), request.POST.get('inventory_sha256', ''), reviewed, original_seen)
    except (ValidationError, DefinitionError) as exc:
        prep.refresh_from_db()
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        return render(request, 'template_semantic_preparation.html', context(prep, member, error=message), status=409)
    return redirect('template_detail', pk=prep.source_version.template_id)
