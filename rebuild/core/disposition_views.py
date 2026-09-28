"""Verified admin review proposals; no deletion or restore admission endpoint."""
import uuid
from django import forms
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from django.views.decorators.http import require_http_methods
from .admin_views import gate
from .admin_queries import page_for
from . import disposition as d, models as m
from .security import audit

class Fingerprint(forms.RegexField):
    def __init__(self,**kwargs):
        super().__init__(regex=r'\A[0-9a-f]{64}\Z',max_length=64,
            widget=forms.TextInput(attrs={'spellcheck':'false','autocomplete':'off'}),**kwargs)

class RequestForm(forms.Form):
    department=forms.UUIDField(label='Department ID')
    scope=forms.ChoiceField(choices=[('patient','Patient'),('encounter','Document')])
    target=forms.UUIDField(label='Record ID')
    authority=Fingerprint(label='Request evidence SHA-256')
    request_key=forms.UUIDField(initial=uuid.uuid4,widget=forms.HiddenInput)
    confirmed=forms.BooleanField(label='I checked the scope and request evidence. This is a review proposal only.')

class PlanForm(forms.Form):
    request=forms.UUIDField(label='Request ID')

class ReviewForm(forms.Form):
    plan=forms.UUIDField(label='Plan ID')
    graph_sha256=Fingerprint(label='Plan SHA-256')
    decision=forms.ChoiceField(choices=[('reviewed','Reviewed proposal'),('rejected','Rejected proposal')])
    evidence=Fingerprint(label='Review evidence SHA-256')
    confirmed=forms.BooleanField(label='I am a distinct custodian. This review does not authorize deletion.')

class RestoreForm(forms.Form):
    instance=forms.UUIDField(label='Configured restore instance ID')
    backup=Fingerprint(label='Backup identity SHA-256')
    confirmed=forms.BooleanField(label='This is the selected quarantined target. Preparation cannot admit it into service.')

@require_http_methods(['GET','POST'])
def page(request):
    gate(request);d.retention.custodian(request.user)
    action=request.POST.get('action') if request.method=='POST' else None
    definitions={'request':RequestForm,'plan':PlanForm,'review':ReviewForm}
    forms_by_name={k:cls(request.POST if action==k else None,prefix=k) for k,cls in definitions.items()}
    form=forms_by_name.get(action)
    if form and form.is_valid():
        v=form.cleaned_data
        try:
            if action=='request':d.submit(request.user,v['department'],v['scope'],v['target'],v['authority'],v['request_key'])
            elif action=='plan':d.prepare(request.user,v['request'])
            else:d.review(request.user,v['plan'],v['graph_sha256'],v['decision'],v['evidence'])
            return redirect('disposition_review')
        except (m.DispositionRequest.DoesNotExist,m.DispositionPlan.DoesNotExist):form.add_error(None,'The proposal was not found.')
        except ValidationError as error:form.add_error(None,error)
    plans=m.DispositionPlan.objects.select_related('request','review','created_by').order_by('-created_at','pk')
    navigation=page_for(request,plans,anchor='plans',size=25)
    labels={'policy_unset':'Retention policy has not been approved.', 'external_copies_unverified':'External copies have not been reconciled.',
        'deletion_unavailable':'Deletion is unavailable in this workflow.', 'work_or_finance_unresolved':'Work or financial reconciliation is still open.',
        'funds_held':'Funds remain reserved.', 'receipt_accounting_unresolved':'A provider receipt needs financial reconciliation.',
        'financial_history_unresolved':'A payment, refund or reconciliation is still unresolved.',
        'historical_preservation':'Historical preservation instructions remain relevant.', 'active_hold':'An active preservation hold applies.',
        'preserved_evidence':'Protected historical evidence remains retained.', 'shared_reference':'Another record references a shared source or file.',
        'file_bytes_unverified':'Referenced files have not been inspected.', 'immutable_evidence':'Immutable evidence remains protected.'}
    for plan in navigation['page']:plan.display_blockers=[labels.get(code,'An unsupported dependency needs review.') for code in plan.graph['blockers']]
    audit(request.user,'disposition.proposals_read')
    return render(request,'disposition_review.html',{'request_form':forms_by_name['request'],
        'plan_form':forms_by_name['plan'],'review_form':forms_by_name['review'],'navigation':navigation,
        'plans':navigation['page'],'requests':m.DispositionRequest.objects.order_by('-created_at','pk')[:25]})

@require_http_methods(['GET','POST'])
def restore(request):
    gate(request);d.retention.custodian(request.user)
    form=RestoreForm(request.POST if request.method=='POST' else None)
    if form.is_valid():
        try:
            d.prepare_restore(request.user,form.cleaned_data['instance'],form.cleaned_data['backup'])
            return redirect('restore_preparation')
        except ValidationError as error:form.add_error(None,error)
    return render(request,'restore_preparation.html',{'form':form,'quarantined':d.quarantined(),
        'rows':m.RestorePreparation.objects.order_by('-created_at','pk')[:25]})
