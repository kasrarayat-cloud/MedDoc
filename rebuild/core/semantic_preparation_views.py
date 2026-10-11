"""Department-scoped, explicit clinician review of reusable answer definitions."""
from copy import deepcopy
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST
from documents.semantic_preparation_roles import (
    CONSTRAINT_KEYS, POLARITIES, SUBJECTS, TEMPORALITIES, VALUE_TYPES, ANSWER_TYPES, ANSWER_MODES, DefinitionError,
    destination, protected_field,
)
from . import semantic_preparation as workflow
from .field_location import describe
from .models import Template, TemplateVersion, TemplateDefinitionPreparation
from .security import departments, membership, scoped


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
        if version == 2: values[field['key']]['answer_mode'] = post.get(prefix+'answer_mode', '')
    return values


def context(prep, member, *, definitions=None, error='', post=None):
    values = workflow.corrected_definitions(prep) if definitions is None else definitions
    proposed = {row['field_key']: row for row in prep.proposal.get('fields', [])}
    checked = {row['field_key']: row for row in prep.checker.get('fields', [])}
    rows = [{'field': field, 'definition': values.get(field['key']), 'location': describe(field),
             'protected': protected_field(field), 'proposal': proposed.get(field['key']),
             'checker': checked.get(field['key']),
             'reviewed': bool(post and field['key'] in post.getlist('reviewed_field'))}
            for field in prep.source_version.fields]
    receipts = list(prep.ai_stage_receipts.order_by('created_at'))
    return {'template': prep.source_version.template, 'source_version': prep.source_version,
        'preparation': prep, 'definition_rows': rows, 'receipts': receipts,
        'provider_cost': sum((row.actual_cost or Decimal('0') for row in receipts), Decimal('0')),
        'provider_cost_unknown': any(row.actual_cost is None for row in receipts),
        'can_edit': member.role in ('owner', 'clinician') and prep.state in workflow.EDITABLE,
        'can_approve': member.role in ('owner', 'clinician') and prep.state == 'review',
        'can_retry': member.role in ('owner','clinician') and prep.state=='blocked'
            and prep.error_code!='provider_unknown'
            and all(row.state in ('succeeded','failed') and row.actual_cost is not None for row in receipts),
        'definition_version':workflow.definition_version(prep.config), 'answer_modes':ANSWER_MODES,
        'value_types': ANSWER_TYPES if workflow.definition_version(prep.config)==2 else VALUE_TYPES, 'subjects': SUBJECTS, 'temporalities': TEMPORALITIES, 'polarities': POLARITIES,
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


@require_POST
def corrections(request, pk):
    prep, member = selected(request, pk)
    membership(request.user, prep.source_version.template.department, roles=['owner', 'clinician'])
    values = posted_definitions(prep, request.POST)
    try:
        workflow.correct(prep.pk, request.user, revision(request), values,
            request.POST.getlist('reviewed_field'), request.POST.get('correction_reason', ''))
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
        workflow.approve(prep.pk, request.user, revision(request), request.POST.get('inventory_sha256', ''),
            request.POST.getlist('approved_field'), request.POST.get('original_reviewed') == 'on')
    except (ValidationError, DefinitionError) as exc:
        prep.refresh_from_db()
        message = '; '.join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        return render(request, 'template_semantic_preparation.html', context(prep, member, error=message), status=409)
    return redirect('template_detail', pk=prep.source_version.template_id)
