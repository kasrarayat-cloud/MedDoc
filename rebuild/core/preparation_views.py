"""Department-scoped original/candidate review and explicit doctor approval."""
import hashlib
import json
import secrets
from django.core.exceptions import ValidationError
from django.http import FileResponse, HttpResponse, JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from . import template_review
from django.views.decorators.http import require_http_methods, require_GET, require_POST
from .models import Template, TemplatePreparation
from .security import scoped, membership, private_path, audit
from .preparation import approve, correct, corrected_fields, can_continue_wm_review, continue_wm_review, failure_explanation
from documents.preparation_service import read_original
from documents import DocumentError

def selected(request, pk):
    template=get_object_or_404(scoped(Template,request.user),pk=pk)
    membership(request.user,template.department)
    prep=get_object_or_404(TemplatePreparation,template=template)
    return template,prep

def revision(request):
    try: result=int(request.POST.get('revision',''))
    except (ValueError,TypeError):raise ValidationError('Reload the current preparation revision.')
    if result<0:raise ValidationError('Invalid preparation revision.')
    return result

@require_GET
def detail(request,pk):
    template,prep=selected(request,pk)
    questions={q['id']:q for q in prep.inventory.get('questions',[])}
    proposed={r['anchor_id']:r for r in prep.proposal.get('anchors',[])}
    checked={r['anchor_id']:r for r in prep.checker.get('anchors',[])}
    uncertainty_labels={'none':'Printed constraint verified', 'constraints_unstated':'Type, unit or choices not specified by the form',
        'placement_requires_review':'Doctor must choose the answer location', 'signing_protected':'Signing area protected',
        'unsupported_structure':'Assisted setup required'}
    def metadata(result):
        value=result.get('metadata')
        return {**value, 'uncertainty_label':uncertainty_labels.get(value.get('uncertainty'),'Requires review')} if value else None
    rows=[{**a,'question':questions[a['question_id']]['text'],'proposal':proposed.get(a['id'],{}).get('decision','pending'),
           'checker':checked.get(a['id'],{}).get('verdict','pending'),
           'proposal_metadata':metadata(proposed.get(a['id'],{})),
           'checker_metadata':metadata(checked.get(a['id'],{}))} for a in prep.inventory.get('anchors',[])]
    receipts=list(prep.receipts.order_by('created_at'))
    from .word_contract import review_rows, approval_issues, definition_version
    definition_rows = template_review.review_items(prep, review_rows(prep))
    if (prep.state in {'review','guided'} and definition_version(prep.config) == 4
            and membership(request.user, template.department).role in {'owner','clinician'}):
        from documents.semantic_preparation_roles import protected_field
        for row in definition_rows:
            if not protected_field(row['field']):
                row['components_edit_url'] = reverse('template_preparation_components', args=[template.pk,row['field']['key']])
    definition_issues = {r['field']['key']: r['reason'] for r in definition_rows if r['state'] == 'unresolved'} if prep.state in {'review','guided'} else {}
    from documents.semantic_preparation_roles import ANSWER_TYPES, ANSWER_MODES, SUBJECTS, TEMPORALITIES, POLARITIES
    compact = {'review_rows': template_review.rows(definition_rows, template_review.label_displays(template)),
        'review_save_url': reverse('template_preparation_correct', args=[template.pk]),
        'review_approve_url': reverse('template_preparation_approve', args=[template.pk]),
        **template_review.tokens(prep, definition_rows, request.user.pk)} if definition_rows else {}
    return render(request,'template_preparation.html',{**compact, 'template':template,'preparation':prep,'layout_preparation':prep,
        'definition_rows':definition_rows, 'definition_issues':definition_issues,
        'can_approve':prep.state == 'review' and not definition_issues,
        'definition_version':definition_version(prep.config),
        'value_types':ANSWER_TYPES, 'answer_modes':ANSWER_MODES, 'subjects':SUBJECTS, 'temporalities':TEMPORALITIES, 'polarities':POLARITIES, 'anchor_rows':rows,'field_rows':corrected_fields(prep),'issues':prep.inventory.get('issues',[]),
        'placement_rows':[r for r in rows if r['kind']=='choose_cell'],
        'protected_rows':[r for r in rows if r['protected_signing']],
        'stories':prep.inventory.get('stories',[]),
        'options':prep.inventory.get('options',[]),'receipts':receipts,
        'failure_explanation':failure_explanation(prep,receipts),
        'can_continue_wm_review':can_continue_wm_review(prep),
        'can_correct':prep.state in {'review','guided'} and membership(request.user, template.department).role in {'owner','clinician'},'preview_token':secrets.token_hex(24)})

@require_GET
def status(request,pk):
    _,prep=selected(request,pk)
    return JsonResponse({'state':prep.state,'revision':prep.revision,'error_code':prep.error_code,
        'field_count':len(prep.inventory.get('fields',[])),
        'explanation':failure_explanation(prep,prep.receipts.order_by('created_at')),
        'started_at':prep.started_at.isoformat() if prep.started_at else None,
        'finished_at':prep.finished_at.isoformat() if prep.finished_at else None,
        'proposer':prep.receipts.filter(role='proposer').values_list('state',flat=True).first(),
        'checker':prep.receipts.filter(role='checker').values_list('state',flat=True).first()})

@require_POST
def corrections(request,pk):
    _,prep=selected(request,pk)
    labels={} if request.POST.get('placement_only')=='on' else {f['key']:request.POST.get('label_'+f['key'],'') for f in prep.candidate_info.get('fields',[])}
    placements={a['id']:request.POST.get('placement_'+a['id'],'') for a in prep.inventory.get('anchors',[]) if a['kind']=='choose_cell'}
    try:
        from .word_contract import active, definition_version, proposed
        definitions = None
        if active(prep.inventory, prep.config) and request.POST.get('compact_review') != 'on':
            from types import SimpleNamespace
            from .semantic_preparation_views import posted_definitions
            definitions = posted_definitions(SimpleNamespace(source_version=SimpleNamespace(fields=prep.inventory['fields']),
                config={'semantic_definition_version':definition_version(prep.config)},
                component_baseline=proposed(prep)), request.POST)
        reviewed_anchors = request.POST.getlist('reviewed_anchor')
        reviewed_fields = request.POST.getlist('reviewed_field')
        reason = request.POST.get('correction_reason','')
        if request.POST.get('compact_review') == 'on':
            from .word_contract import review_rows
            definitions, reviewed_fields, reason = template_review.submitted(prep, template_review.review_items(prep, review_rows(prep)), request.user, request.POST, 'save')
            labels = {f['key']: f['label'] for f in prep.candidate_info.get('fields', [])}
            reviewed_anchors = [a['id'] for a in prep.inventory.get('anchors', [])]
        correct(prep.pk,request.user,revision(request),labels,reviewed_anchors,reason,placements,definitions,reviewed_fields)
    except (ValidationError,DocumentError,ValueError) as exc:
        return HttpResponse('; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc),status=409,content_type='text/plain')
    return redirect('template_preparation',pk=pk)

@require_POST
def continue_review(request,pk):
    _,prep=selected(request,pk)
    try:
        continue_wm_review(prep.pk,request.user,revision(request),request.POST.get('candidate_sha256',''))
    except (ValidationError,DocumentError,ValueError) as exc:
        return HttpResponse('; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc),status=409,content_type='text/plain')
    return redirect('template_preparation',pk=pk)

@require_POST
def approval(request,pk):
    _,prep=selected(request,pk)
    try:
        from .word_contract import review_rows, approval_issues
        current_rows = template_review.review_items(prep, review_rows(prep))
        # Existing core errors still explain retained model uncertainty. This adds
        # the one-time person choice for an otherwise complete generic name label.
        if any(r['state'] == 'unresolved' for r in current_rows) and not approval_issues(prep):
            raise ValidationError('Resolve and save the open questions before approving this template.')
        reviewed = request.POST.getlist('reviewed_definition')
        changes = request.POST.getlist('approved_change')
        original_seen = request.POST.get('original_reviewed') == 'on'
        prepared_seen = request.POST.get('prepared_reviewed') == 'on'
        if request.POST.get('compact_review') == 'on':
            from .word_contract import review_rows
            _, reviewed, _ = template_review.submitted(prep, current_rows, request.user, request.POST, 'approve')
            changes = [c['anchor_id'] for c in prep.changes]
            original_seen = prepared_seen = True  # Explicit snapshot-bound summary consent above.
        approve(prep.pk,request.user,revision(request),request.POST.get('candidate_sha256',''),
                changes,original_seen,prepared_seen,reviewed)
    except ValidationError as exc:
        return HttpResponse('; '.join(exc.messages),status=409,content_type='text/plain')
    return redirect('template_detail',pk=pk)

@require_GET
def preview_bytes(request,pk,kind):
    template,prep=selected(request,pk)
    if kind=='original': relative,sha=template.original_path,template.sha256
    elif kind=='prepared' and prep.candidate_path:relative,sha=prep.candidate_path,prep.candidate_sha256
    else:raise Http404()
    raw=read_original(private_path(relative))
    if hashlib.sha256(raw).hexdigest()!=sha:raise ValidationError('The preview source failed its integrity check.')
    # Same immutable bytes are used by the renderer and export-source identity; no conversion.
    response=HttpResponse(raw,content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['X-Content-Type-Options']='nosniff'
    return response

@require_GET
def prepared_download(request,pk):
    template,prep=selected(request,pk)
    if not prep.candidate_path:raise Http404()
    raw=read_original(private_path(prep.candidate_path))
    if hashlib.sha256(raw).hexdigest()!=prep.candidate_sha256:raise ValidationError('Candidate integrity check failed.')
    audit(request.user,'template.candidate_download',prep.pk,department=template.department,sha256=prep.candidate_sha256,approved=prep.state=='approved')
    response=HttpResponse(raw,content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition']='attachment; filename="prepared-blank-form.docx"'
    return response

@require_GET
def preview_frame(request):
    # Scripts are fixed local assets. The embedding iframe has an opaque origin; it
    # cannot read authentication cookies, storage, the parent DOM, or fetch the source.
    if request.GET.get('token','').isalnum() and len(request.GET['token'])==48:
        return render(request,'docx_preview_frame.html',{'token':request.GET['token']})
    raise Http404()
