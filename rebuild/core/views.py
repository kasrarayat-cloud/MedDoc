import hashlib
import json
import os
import re
import secrets
from datetime import datetime,timedelta
from decimal import Decimal
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate,login as auth_login,logout as auth_logout
from django.core.exceptions import PermissionDenied,ValidationError
from django.core import signing
from django.db import transaction,IntegrityError
from django.http import FileResponse,HttpResponse,JsonResponse,Http404
from django.shortcuts import render,redirect,get_object_or_404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST,require_http_methods
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice
from .models import *
from .forms import *
from .security import audit,departments,scoped,membership,digest,token,store_upload,private_path,rate_limit
from .billing import welcome_credit,credit_payment,reconcile_refund,reconciliation,stripe_test_key_configured,reconcile_usage,release
from .context import integration_status
from .jobs import enqueue,cancel,CancellationRefused,public_error,billable_outcome,may_cancel
from . import wm_review


def error_message(exc):
    return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)


def document_backend(info):
    if not info.get('backend'):return {}
    result={key:info.get(key) for key in ('backend','source_sha256','mapping_digest')}
    if (result['backend']!=wm_review.BACKEND or result['source_sha256']!=info.get('sha256')
            or not isinstance(result['mapping_digest'],str) or not re.fullmatch(r'[a-f0-9]{64}',result['mapping_digest'])):
        raise ValidationError('The qualified Word mapping identity is incomplete.')
    return result


def wm_resolve(encounter,actor,decisions=None):
    from documents import resolve_template
    version=encounter.template_version
    original=private_path(version.template.original_path)
    if hashlib.sha256(original.read_bytes()).hexdigest()!=version.template.sha256:
        raise ValidationError('Original integrity check failed.')
    decisions=decisions if decisions is not None else encounter.template_review.get('decisions',{})
    variants={row['key']:decisions.get(row['key'],{}).get('variant',row['default_variant'])
              for row in version.review_requirements}
    signer=encounter.finalized_by if encounter.status=='finalized' else actor
    context={'reviewer_id':str(signer.pk),'revision':encounter.revision,'notes':encounter.notes,
             'signer_name':' '.join(signer.get_full_name().split()) or signer.email,
             'finalized_at':(encounter.finalized_at or timezone.now()).isoformat()}
    result=resolve_template(original,version.document_backend,wm_review.sdk_answers(encounter,actor),
                            claim_variants=variants,trusted_context=context)
    if (result.get('backend')!=version.document_backend.get('backend')
            or result.get('mapping_digest')!=version.document_backend.get('mapping_digest')
            or result.get('sha256')!=version.template.sha256):
        raise ValidationError('The resolved Word statements differ from the selected mapping version.')
    if result.get('conflicts'):
        raise ValidationError('The chosen answers and prewritten statement alternatives conflict. Correct their documented choices before review and export.')
    return result['review_requirements']


def source_quote_evidence(notes,label,raw,labels):
    """Convert submitted quotations into actual offsets; never accept posted offsets."""
    if len(raw)>50000:raise ValidationError('Source quotations exceed the supported limit; nothing was truncated.')
    units,_=wm_review.source_units(notes,label,labels)
    evidence=[]
    for submitted in raw.splitlines():
        quote=submitted.strip()
        if not quote:continue
        found=next((item for item in units if item[2]==quote),None)
        if found is None:raise ValidationError('Use a complete source line or the complete value for this exact question label.')
        evidence.append({'quote':quote,'start':found[0],'end':found[1]})
    wm_review.validate_evidence(notes,label,evidence,labels)
    return evidence


WM_BLOCKERS={
    'clinician_review_required':'A clinician must review this value for the current source revision.',
    'conflicting_source':'The notes contain conflicting values for this question. Correct the source first.',
    'instruction_like_source':'Instruction-like source text needs correction before clinical review.',
    'not_an_original_option':'This value is not one of the original Word choices.',
    'exact_labelled_source_required':'Quote the complete source value under this exact question label.',
    'documented_numeric_value_and_unit_required':'Document the numeric value and the original unit, such as 3.2 mm or 400 ms.',
    'documented_value_marked_missing':'The source documents a value for this field. Correct the notes before marking it missing.',
    'missing_dependent_choice':'An unanswered choice leaves this prewritten statement incomplete.',
    'statement_alternative_requires_empty_choices':'This statement alternative requires the associated choices to be left unanswered.',
    'complete_assertion_source_required':'Document the complete prewritten statement under its own exact statement label, including its side.',
    'preprinted_identity_differs_from_actual_clinician':'The preprinted identity differs from the signed-in clinician. This template cannot be finalized by this account.',
    'identity_must_come_from_authenticated_clinician':'Identity comes from the signed-in clinician, not source quotations.',
    'signature_time_must_come_from_finalization':'The signature time is set during finalization, not taken from the notes.',
    'selected_answer_conflicts_with_fixed_assertion':'The selected reflux finding contradicts this fixed negative statement. Export is blocked.',
    'symptom_conflicts_with_asymptomatic':'This symptom conflicts with the selected asymptomatic finding.',
    'asymptomatic_conflicts_with_documented_symptom':'Asymptomatic conflicts with another selected symptom.',
}

def health(request): return JsonResponse({'status':'ok','data_mode':'synthetic-only','surface':'admin' if settings.ADMIN_SITE else 'doctor','release':settings.RELEASE_SHA})

@require_http_methods(['GET','POST'])
def login_view(request):
    form=LoginForm(request.POST or None)
    next_url=request.POST.get('next',request.GET.get('next',''))
    if not next_url.startswith('/') or not url_has_allowed_host_and_scheme(next_url,allowed_hosts=set()):next_url=''
    if request.method=='POST' and form.is_valid():
        email=form.cleaned_data['email'].lower()
        if not rate_limit('login-ip:'+request.META.get('REMOTE_ADDR',''),limit=40) or not rate_limit('login-email:'+email):
            form.add_error(None,'Too many sign-in attempts. Try again later.')
        else:
            found=User.objects.filter(email__iexact=email).first()
            user=authenticate(request,username=found.username if found else email,password=form.cleaned_data['password'])
            device=None
            if user and user.is_staff:
                with transaction.atomic():
                    device=TOTPDevice.objects.select_for_update().filter(user=user,confirmed=True).first()
                    if not device or not device.verify_token(form.cleaned_data['otp']): user=None
            if user and user.verified_at and (not settings.ADMIN_SITE or user.is_staff):
                auth_login(request,user)
                if device: otp_login(request,device)
                audit(user,'auth.login')
                return redirect(next_url or ('admin_dashboard' if settings.ADMIN_SITE else 'dashboard'))
            audit(None,'auth.login_failed',details='No credentials recorded')
            form.add_error(None,'Sign-in failed. Check your credentials, verification, and authenticator code.')
    return render(request,'login.html',{'form':form,'next':next_url})

@require_POST
def logout_view(request):
    audit(request.user,'auth.logout');auth_logout(request);return redirect('login')

def verification_mail(user,raw,verification):
    from .email_delivery import deliver_account_email
    return deliver_account_email(user,verification.pk,user.email,'verification',raw)

@require_http_methods(['GET','POST'])
def register(request):
    if settings.ADMIN_SITE: raise Http404
    form=RegisterForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        if not rate_limit('register:'+request.META.get('REMOTE_ADDR',''),limit=5):return HttpResponse('Try again later.',status=429)
        with transaction.atomic():
            user=form.save(commit=False);user.username=form.cleaned_data['email'];user.save()
            raw=token();verification=Verification.objects.create(user=user,token_hash=digest(raw),expires_at=timezone.now()+timedelta(hours=24))
            audit(user,'account.register')
        delivery=verification_mail(user,raw,verification)
        if delivery.status=='outbox':messages.success(request,'Verification created in the private development outbox. Email delivery is not live yet.')
        elif delivery.status=='accepted':messages.success(request,'Verification submitted to the email provider. Check your inbox; inbox delivery is not yet confirmed.')
        else:messages.warning(request,'Account created, but verification email delivery could not be confirmed. Ask your administrator to recover the verification link or retry delivery. No welcome credit has been granted yet.')
        return redirect('login')
    return render(request,'register.html',{'form':form})

@require_http_methods(['GET','POST'])
def verify(request,raw):
    v=get_object_or_404(Verification,token_hash=digest(raw),expires_at__gt=timezone.now(),used_at__isnull=True)
    if request.method=='GET':return render(request,'confirm.html',{'title':'Verify your test account','description':'Confirm ownership of this email to activate your personal $10 welcome credit.'})
    with transaction.atomic():
        user=User.objects.select_for_update().get(pk=v.user_id)
        v=Verification.objects.select_for_update().get(pk=v.pk)
        if v.used_at or v.expires_at<=timezone.now() or user.verified_at or not user.is_active: raise Http404
        user.verified_at=timezone.now();user.save(update_fields=['verified_at'])
        v.used_at=timezone.now();v.save(update_fields=['used_at'])
        org=Organization.objects.create(name=f'{user.first_name or "Personal"} workspace')
        dept=Department.objects.create(organization=org,name='Personal practice')
        Membership.objects.create(user=user,department=dept,role='owner')
        welcome_credit(user);audit(user,'account.verified',user.pk)
    messages.success(request,'Email verified. Your $10 personal welcome credit is available.');return redirect('login')

@require_http_methods(['GET','POST'])
def mfa_setup(request):
    if not request.user.is_authenticated: return redirect('login')
    device=TOTPDevice.objects.filter(user=request.user).first()
    if not device:device=TOTPDevice.objects.create(user=request.user,name='Authenticator',confirmed=False)
    form=OTPForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            device=TOTPDevice.objects.select_for_update().get(pk=device.pk)
            if device.verify_token(form.cleaned_data['code']):
                device.confirmed=True;device.save(update_fields=['confirmed']);otp_login(request,device);audit(request.user,'auth.mfa_verified');return redirect('admin_dashboard' if settings.ADMIN_SITE else 'dashboard')
        form.add_error('code','Invalid or already used code.')
    return render(request,'mfa_setup.html',{'form':form,'provisioning_uri':device.config_url if not device.confirmed else '', 'device':device})

def dashboard(request):
    return render(request,'dashboard.html',{'encounters':scoped(Encounter,request.user).select_related('patient','template_version__template').order_by('-created_at')[:30],'templates':scoped(Template,request.user).order_by('-created_at')[:30]})

@require_http_methods(['GET','POST'])
def template_upload(request):
    from documents import inspect_template,DocumentError
    form=UploadForm(request.POST or None,request.FILES or None,user=request.user)
    if request.method=='POST' and form.is_valid():
        relative=None
        try:
            department=form.cleaned_data['department'];membership(request.user,department)
            if Path(form.cleaned_data['file'].name).suffix.lower() not in ['.docx','.pdf']:raise ValidationError('Choose a Word .docx or PDF file.')
            relative=store_upload(form.cleaned_data['file'])
            info=inspect_template(private_path(relative))
            if len(info['fields'])>100:raise ValidationError('Templates support at most 100 answer fields. Split this template explicitly.')
            with transaction.atomic():
                t=Template.objects.create(department=department,name=form.cleaned_data['name'],format=info['format'],original_name=Path(form.cleaned_data['file'].name).name[:200],original_path=relative,sha256=info['sha256'],warnings=info.get('warnings',[]),created_by=request.user)
                TemplateVersion.objects.create(template=t,number=1,fields=info['fields'],review_requirements=info.get('review_requirements',[]),document_backend=document_backend(info),created_by=request.user)
                audit(request.user,'template.upload',t.pk,department=department,sha256=t.sha256,field_count=len(info['fields']))
            return redirect('template_detail',pk=t.pk)
        except (ValidationError,DocumentError) as exc:
            if relative:private_path(relative).unlink(missing_ok=True)
            form.add_error(None,error_message(exc))
    return render(request,'template_upload.html',{'form':form})

@require_http_methods(['GET','POST'])
def template_detail(request,pk):
    t=get_object_or_404(scoped(Template,request.user),pk=pk)
    version=t.versions.order_by('-number').first()
    form=MappingForm(request.POST or None,initial={'labels':{f['key']:f['label'] for f in version.fields}})
    if request.method=='POST' and form.is_valid():
        try:
            membership(request.user,t.department,roles=['owner','clinician','manager'])
            labels=form.cleaned_data['labels']
            if not isinstance(labels,dict) or set(labels)!={f['key'] for f in version.fields} or any(not isinstance(v,str) or not v.strip() or len(v)>300 for v in labels.values()):raise ValidationError('Provide one question label of at most 300 characters for each existing field key.')
            with transaction.atomic():
                Template.objects.select_for_update().get(pk=t.pk)
                latest=t.versions.order_by('-number').first()
                if latest.document_backend and labels!={f['key']:f['label'] for f in latest.fields}:
                    raise ValidationError('This qualified Word mapping uses fixed question labels so source evidence remains unambiguous. Keep the original labels.')
                fields=[{**f,'label':labels[f['key']]} for f in latest.fields]
                version=TemplateVersion.objects.create(template=t,number=latest.number+1,fields=fields,review_requirements=latest.review_requirements,document_backend=latest.document_backend,created_by=request.user)
                audit(request.user,'template.mapping_version',version.pk,department=t.department,number=version.number)
            messages.success(request,'New mapping version saved. Existing documents keep their original version.');return redirect('template_detail',pk=t.pk)
        except ValidationError as exc:form.add_error(None,error_message(exc))
    return render(request,'template_detail.html',{'template':t,'version':version,'form':form})

def template_original(request,pk):
    t=get_object_or_404(scoped(Template,request.user),pk=pk)
    path=private_path(t.original_path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=t.sha256:raise ValidationError('Original integrity check failed.')
    audit(request.user,'template.download',t.pk,department=t.department)
    return FileResponse(path.open('rb'),as_attachment=True,filename=t.original_name)

@require_http_methods(['GET','POST'])
def encounter_new(request):
    form=EncounterForm(request.POST or None,user=request.user)
    if request.method=='POST' and form.is_valid():
        data=form.cleaned_data
        with transaction.atomic():
            membership(request.user,data['patient'].department)
            e=Encounter(department=data['patient'].department,patient=data['patient'],template_version=data['template_version'],created_by=request.user,notes=data['notes']);e.full_clean(exclude=['answers','finalized_at','finalized_by','export_path','export_sha256']);e.save()
            audit(request.user,'encounter.create',e.pk,department=e.department)
        return redirect('encounter_detail',pk=e.pk)
    return render(request,'encounter_form.html',{'form':form})

def encounter_detail(request,pk):
    from documents import DocumentError
    # Worker adoption and source edits lock the encounter. Capture the related
    # display records while that same row is stable, then release before Word
    # processing. Lazy jobs/codes could otherwise expose a later completion
    # beside answers or source notes loaded before that completion.
    with transaction.atomic():
        e=get_object_or_404(scoped(Encounter,request.user).select_related(
            'patient','department__organization','template_version__template','finalized_by'
        ).select_for_update(of=('self',)),pk=pk)
        jobs=list(Job.objects.filter(encounter=e).order_by('-created_at'))
        codes=list(CodeSuggestion.objects.filter(encounter=e).select_related('terminology__release','accepted_by'))
        can_finalize=Membership.objects.filter(user=request.user,department=e.department,active=True,role__in=['owner','clinician']).exists()
    is_wm=bool(e.template_version.document_backend)
    rows=[{**f,**e.answers.get(f['key'],{'text':'','status':'missing','evidence':[],'reviewed':False})} for f in e.template_version.fields]
    requirements=[];review_error='';assessment=None;resolved_ok=False
    if is_wm:
        decisions=e.template_review.get('decisions',{})
        try:
            requirements=wm_resolve(e,request.user)
            resolved_ok=True
            if can_finalize:
                assessment=wm_review.evaluate_review(e,request.user,decisions,resolved_requirements=requirements)
        except (ValidationError,DocumentError) as exc:
            review_error=error_message(exc)
            requirements=e.template_version.review_requirements
        for row in rows:
            answer=e.answers.get(row['key'],{})
            row['reviewed']=(answer.get('reviewed') is True and answer.get('reviewed_by')==str(request.user.pk)
                             and answer.get('review_revision')==e.revision)
            row['unsupported_choice']=bool(row.get('kind')=='choice' and row.get('text') and row['text'] not in row.get('options',[]))
            row['source_quote']=answer.get('review_quote','\n'.join(item['quote'] for item in row.get('evidence',[])))
            reasons=assessment['answers'][row['key']]['blockers'] if assessment else []
            if assessment:row['status']=assessment['answers'][row['key']]['status']
            row['review_errors']=[WM_BLOCKERS.get(reason,'Clinical review is incomplete.') for reason in reasons]
        for row in requirements:
            row['unresolved']=not resolved_ok
            decision=decisions.get(row['key'],{})
            row['reviewed']=bool(decision.get('reviewed') and e.template_review.get('reviewer_id')==str(request.user.pk)
                                  and e.template_review.get('binding',{}).get('source_revision')==e.revision)
            row['source_quote']='\n'.join(item['quote'] for item in decision.get('evidence',[]))
            row['selected_variant']=decision.get('variant') or row.get('selected_variant') or row.get('default_variant')
            if resolved_ok:
                row['review_token']=signing.dumps({'encounter':str(e.pk),'revision':e.revision,
                    'actor':str(request.user.pk),'key':row['key'],'text_sha256':row['text_sha256'],
                    'variant':row['selected_variant']},salt='wm-statement-review')
            reasons=assessment['assertions'][row['key']]['blockers'] if assessment else []
            row['review_errors']=[WM_BLOCKERS.get(reason,'Clinical review is incomplete.') for reason in reasons]
    from .generation import maximum_cost,configuration
    try:maximum_charge=maximum_cost(e.notes,e.template_version.fields,context_labels=[row['label'] for row in e.template_version.review_requirements])*Decimal('1.5')
    except ValidationError:maximum_charge=None
    audit(request.user,'encounter.view',e.pk,department=e.department)
    # Billing boundary: earlier charged requests (successes, and successes the user's own state declined) stay charged, so a
    # further request is disclosed as separately billable. The doctor reads the classification in words, is offered cancel only
    # where the server allows it, and receives provider output only for requests that stand charged.
    prior_generations=sum(1 for job in jobs if job.kind=='generation' and billable_outcome(job))
    prior_transcriptions=sum(1 for job in jobs if job.kind=='transcription' and billable_outcome(job))
    for job in jobs:
        job.display_error=public_error(job); job.can_cancel=may_cancel(job,request.user); job.deliverable=bool(job.result_path) and billable_outcome(job)
    return render(request,'encounter_detail.html',{'encounter':e,'answer_rows':rows,'wm_template':is_wm,'wm_requirements':requirements,'wm_review_error':review_error,'generation_max_charge':maximum_charge,'usage_quote':signing.dumps({'user':str(request.user.pk),'encounter':str(e.pk),'revision':e.revision,'config':configuration()},salt='usage-quote'),'voice_max_charge':Decimal(os.getenv('QUILLMD_VOICE_MAX_COST','0.20'))*Decimal('1.5'),'codes':codes,'jobs':jobs,'voice_form':VoiceForm(),'can_finalize':can_finalize,'prior_generations':prior_generations,'prior_transcriptions':prior_transcriptions})

@require_POST
def generate_view(request,pk):
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    try:
        if not rate_limit('generate:'+str(request.user.pk),limit=30):raise ValidationError('Generation rate limit reached.')
        quoted=usage_quote(request,e)
        enqueue(e,request.user,config=quoted);messages.success(request,'Generation queued. Refresh this page to view the result.')
    except ValidationError as exc:messages.error(request,error_message(exc))
    return redirect('encounter_detail',pk=pk)

@require_POST
def job_cancel(request,pk,job_pk):
    """Cancel a queued request before any provider request; anything later is billed by result (409 with the reason)."""
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    job=get_object_or_404(Job,pk=job_pk,encounter=e)
    try:cancel(job,request.user)
    except CancellationRefused as exc:return HttpResponse(error_message(exc),status=409)
    messages.success(request,'Queued request cancelled before any provider request. Held funds were released; nothing was charged.')
    return redirect('encounter_detail',pk=pk)

@require_POST
@transaction.atomic
def save_answers(request,pk):
    from documents import DocumentError
    e=get_object_or_404(scoped(Encounter,request.user).select_for_update(),pk=pk)
    if e.status=='finalized':return HttpResponse('Finalized documents are immutable.',status=409)
    if Job.objects.filter(encounter=e,state__in=['queued','running','reconciliation']).exists():return HttpResponse('Wait until the pending job is resolved.',status=409)
    if request.POST.get('revision')!=str(e.revision):return HttpResponse('This document changed. Reload before editing.',status=409)
    is_wm=bool(e.template_version.document_backend)
    labels=[row['label'] for row in e.template_version.fields+e.template_version.review_requirements]
    if is_wm and any(request.POST.get('claim_reviewed_'+row['key'])=='on' for row in e.template_version.review_requirements):
        membership(request.user,e.department,roles=['owner','clinician'])
    answers={};review_errors=[];target_revision=e.revision+1
    for field in e.template_version.fields:
        key=field['key'];previous=e.answers.get(key,{'text':'','evidence':[],'status':'missing'})
        value=request.POST.get('answer_'+key,'')
        if len(value)>20000:return HttpResponse('Answer too long; nothing was truncated or saved.',status=400)
        reviewed=request.POST.get('reviewed_'+key)=='on'
        if reviewed:membership(request.user,e.department,roles=['owner','clinician'])
        answers[key]={**previous,'text':value,'reviewed':reviewed,'status':'edited' if value!=previous.get('text','') else previous.get('status','missing'),'reviewed_by':str(request.user.pk) if reviewed else None}
        if is_wm:
            quote=request.POST.get('source_'+key,'')
            if len(quote)>50000:return HttpResponse('Source quotations exceed the supported limit; nothing was saved.',status=400)
            try:evidence=source_quote_evidence(e.notes,field['label'],quote,labels)
            except ValidationError as exc:
                evidence=[];reviewed=False;review_errors.append(error_message(exc))
            answers[key].update(evidence=evidence,review_quote=quote,reviewed=reviewed,
                                reviewed_by=str(request.user.pk) if reviewed else None,
                                review_revision=target_revision if reviewed else None)
            if not value:answers[key]['status']='missing'
    decisions={}
    if is_wm:
        for requirement in e.template_version.review_requirements:
            key=requirement['key'];quote=request.POST.get('claim_source_'+key,'')
            if len(quote)>50000:return HttpResponse('Source quotations exceed the supported limit; nothing was saved.',status=400)
            reviewed=request.POST.get('claim_reviewed_'+key)=='on'
            try:evidence=source_quote_evidence(e.notes,requirement['label'],quote,labels)
            except ValidationError as exc:
                evidence=[];reviewed=False;review_errors.append(error_message(exc))
            variant=request.POST.get('claim_variant_'+key,requirement.get('default_variant'))
            if variant not in {item['id'] for item in requirement['variants']}:
                return HttpResponse('Choose an approved statement alternative. No changes were saved.',status=400)
            decisions[key]={'reviewed':reviewed,'evidence':evidence,'variant':variant}
    e.answers=answers;e.revision=target_revision;e.status='review';wm_review.invalidate_review(e)
    if is_wm and Membership.objects.filter(user=request.user,department=e.department,active=True,role__in=['owner','clinician']).exists():
        try:
            resolved=wm_resolve(e,request.user,decisions)
            for requirement in resolved:
                key=requirement['key']
                if not decisions[key]['reviewed']:continue
                try:
                    visible=signing.loads(request.POST.get('claim_token_'+key,''),salt='wm-statement-review',max_age=3600)
                    expected={'encounter':str(e.pk),'revision':target_revision-1,'actor':str(request.user.pk),
                              'key':key,'text_sha256':requirement['text_sha256'],
                              'variant':requirement['selected_variant']}
                    if visible!=expected:raise ValueError()
                except (signing.BadSignature,ValueError,TypeError):
                    decisions[key]['reviewed']=False
                    review_errors.append('A statement changed or its displayed review expired. Review the updated wording shown below, then save its review again.')
            e.template_review=wm_review.build_review(e,request.user,decisions,resolved_requirements=resolved)
        except (ValidationError,DocumentError) as exc:
            # Retain incomplete choices for correction, visibly unqualified.
            # Schema0 is never accepted by the finalization helper.
            for decision in decisions.values():decision['reviewed']=False
            e.template_review={'schema':0,'decisions':decisions,'binding':wm_review.binding(e),
                               'reviewer_id':str(request.user.pk)}
            review_errors.append(error_message(exc))
    e.save(update_fields=['answers','revision','status','template_review'])
    audit(request.user,'encounter.answers_saved',e.pk,department=e.department,revision=e.revision)
    if is_wm:audit(request.user,'encounter.template_review_saved',e.pk,department=e.department,revision=e.revision,complete=e.template_review.get('assessment',{}).get('complete',False))
    messages.success(request,'Edits saved. Review every answer before finalizing.')
    for message in dict.fromkeys(review_errors):messages.warning(request,'Review remains incomplete: '+message)
    return redirect('encounter_detail',pk=pk)

@require_POST
def finalize(request,pk):
    from documents import inspect_template,fill_template,DocumentError
    try:
        with transaction.atomic():
            e=get_object_or_404(scoped(Encounter,request.user).select_for_update(),pk=pk)
            membership(request.user,e.department,roles=['owner','clinician'])
            if e.status=='finalized':return redirect('encounter_detail',pk=pk)
            if request.POST.get('reviewed')!='on':raise ValidationError('Explicit clinical review confirmation is required.')
            if request.POST.get('revision')!=str(e.revision):raise ValidationError('Document changed; reload before finalizing.')
            if Job.objects.filter(encounter=e,state__in=['queued','running','reconciliation']).exists():raise ValidationError('Resolve pending jobs before finalizing.')
            if any(not e.answers.get(f['key'],{}).get('reviewed') for f in e.template_version.fields):raise ValidationError('A clinician must review every field, including missing information.')
            if any(v.get('status')=='conflict' for v in e.answers.values()):raise ValidationError('Resolve every conflict by editing the answer before finalizing.')
            original=private_path(e.template_version.template.original_path)
            if hashlib.sha256(original.read_bytes()).hexdigest()!=e.template_version.template.sha256:raise ValidationError('Original integrity check failed.')
            relative=f'exports/{secrets.token_hex(24)}.{e.template_version.template.format.lower()}'
            out=private_path(relative);out.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            canonical=inspect_template(original)
            finalized_at=timezone.now()
            if e.template_version.document_backend:
                version=e.template_version
                if (document_backend(canonical)!=version.document_backend or canonical['fields']!=version.fields
                        or canonical.get('review_requirements')!=version.review_requirements):
                    raise ValidationError('The original Word mapping differs from this immutable mapping version.')
                resolved=wm_resolve(e,request.user)
                reviewed=wm_review.validate_for_finalize(e,request.user,resolved_requirements=resolved)
                fill_template(original,version.fields,reviewed['answers'],out,
                              document_backend=version.document_backend,
                              reviewed_requirements=reviewed['reviewed_requirements'],
                              claim_variants=reviewed['claim_variants'],
                              trusted_context=reviewed['trusted_context'])
                finalized_at=datetime.fromisoformat(reviewed['trusted_context']['finalized_at'])
            else:
                fill_template(original,canonical['fields'],{k:v['text'] for k,v in e.answers.items()},out)
            out.chmod(0o600)
            e.export_path=relative;e.export_sha256=hashlib.sha256(out.read_bytes()).hexdigest();e.finalized_at=finalized_at;e.finalized_by=request.user;e.status='finalized';e.save()
            audit(request.user,'encounter.finalize',e.pk,department=e.department,export_sha256=e.export_sha256,mapping_version=e.template_version.number)
        messages.success(request,'Finalized. The original structure is preserved in your export.')
    except (ValidationError,DocumentError) as exc:messages.error(request,error_message(exc))
    return redirect('encounter_detail',pk=pk)

def export(request,pk):
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk,status='finalized')
    path=private_path(e.export_path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=e.export_sha256:return HttpResponse('Export integrity check failed.',status=409)
    audit(request.user,'encounter.export',e.pk,department=e.department)
    return FileResponse(path.open('rb'),as_attachment=True,filename=f'quillmd-{str(e.pk)[:8]}.{e.template_version.template.format.lower()}')

@require_POST
def voice(request,pk):
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    form=VoiceForm(request.POST,request.FILES)
    relative=None
    try:
        if not form.is_valid():raise ValidationError('Choose a supported recording and confirm provider processing.')
        if Path(form.cleaned_data['audio'].name).suffix.lower() not in ['.wav','.webm','.mp3','.m4a']:raise ValidationError('Unsupported audio file.')
        relative=store_upload(form.cleaned_data['audio'],'audio')
        raw=private_path(relative).read_bytes()[:16]
        if not (raw.startswith((b'RIFF',b'ID3',b'\x1aE\xdf\xa3',b'\xff\xfb',b'\xff\xf3',b'\xff\xf2')) or raw[4:8]==b'ftyp'):raise ValidationError('Audio file signature does not match a supported recording.')
        quoted=usage_quote(request,e)
        job=enqueue(e,request.user,'transcription',relative,config=quoted)
        if job.input_path!=relative:private_path(relative).unlink(missing_ok=True)
        messages.success(request,'Transcription queued. Review the transcript before generating answers.')
    except ValidationError as exc:
        if relative:private_path(relative).unlink(missing_ok=True)
        messages.error(request,error_message(exc))
    return redirect('encounter_detail',pk=pk)

@require_http_methods(['GET','POST'])
def patients(request):
    form=PatientForm(request.POST or None,user=request.user)
    if request.method=='POST' and form.is_valid():
        try:
            with transaction.atomic():
                d=form.cleaned_data['department'];membership(request.user,d)
                p=Patient.objects.create(department=d,display_name=form.cleaned_data['display_name'],reference=form.cleaned_data['reference'],created_by=request.user)
                audit(request.user,'patient.create',p.pk,department=d)
            return redirect('patients')
        except IntegrityError:form.add_error('reference','This reference already exists in the department.')
    q=request.GET.get('q','')[:140]
    rows=scoped(Patient,request.user).filter(models.Q(display_name__icontains=q)|models.Q(reference__icontains=q)).select_related('department').order_by('display_name')[:100]
    return render(request,'patients.html',{'patients':rows,'form':form,'query':q})

@require_http_methods(['GET','POST'])
def team(request):
    form=InvitationForm(request.POST or None,user=request.user)
    if request.method=='POST' and form.is_valid():
        d=form.cleaned_data['department'];membership(request.user,d,roles=['owner','manager'])
        if not rate_limit('invite:'+str(request.user.pk),limit=30):return HttpResponse('Invitation limit reached. Try again later.',status=429)
        raw=token()
        invitation=Invitation.objects.create(email=form.cleaned_data['email'].lower(),department=d,role=form.cleaned_data['role'],token_hash=digest(raw),expires_at=timezone.now()+timedelta(days=7),invited_by=request.user)
        from .email_delivery import deliver_account_email
        delivery=deliver_account_email(request.user,invitation.pk,invitation.email,'invitation',raw,department=d)
        audit(request.user,'department.invite',invitation.pk,department=d,role=invitation.role)
        if delivery.status=='outbox':messages.success(request,'Invitation saved in the private development outbox.')
        elif delivery.status=='accepted':messages.success(request,'Invitation submitted to the email provider. Inbox delivery is not yet confirmed.')
        else:messages.warning(request,'Invitation saved, but email delivery could not be confirmed. Ask your administrator to recover the private invitation link or send a new invitation after delivery is repaired.')
        return redirect('team')
    ds=departments(request.user)
    return render(request,'team.html',{'form':form,'department_form':DepartmentForm(),'memberships':Membership.objects.filter(department__in=ds).select_related('user','department'),'invitations':Invitation.objects.filter(department__in=ds).select_related('department'),'departments':ds,'now':timezone.now()})

@require_POST
@transaction.atomic
def invitation_revoke(request,pk):
    invite=get_object_or_404(Invitation.objects.select_for_update().filter(department__in=departments(request.user)),pk=pk)
    membership(request.user,invite.department,roles=['owner','manager'])
    if invite.accepted_at:return HttpResponse('Invitation already accepted. Change department membership to revoke access.',status=409)
    invite.expires_at=timezone.now();invite.save(update_fields=['expires_at'])
    audit(request.user,'department.invitation_revoked',invite.pk,department=invite.department)
    messages.success(request,'Invitation revoked. The link no longer grants access.')
    return redirect('team')

@require_POST
@transaction.atomic
def create_department(request):
    form=DepartmentForm(request.POST)
    owner=Membership.objects.filter(user=request.user,active=True,role='owner').select_related('department__organization').first()
    if not owner:raise PermissionDenied
    if form.is_valid():
        d=Department.objects.create(organization=owner.department.organization,**form.cleaned_data)
        Membership.objects.create(user=request.user,department=d,role='owner')
        Wallet.objects.get_or_create(organization=d.organization,kind='paid')
        audit(request.user,'department.create',d.pk,department=d)
    else:messages.error(request,'Enter a department name.')
    return redirect('team')

@require_POST
@transaction.atomic
def membership_update(request,pk):
    target=get_object_or_404(Membership.objects.select_for_update(),pk=pk)
    actor=membership(request.user,target.department,roles=['owner'])
    if target.pk==actor.pk or target.role=='owner':raise ValidationError('Owner membership cannot be removed here.')
    role=request.POST.get('role',target.role)
    if role not in ['manager','clinician','employee']:raise ValidationError('Invalid role.')
    target.role=role;target.active=request.POST.get('active')=='on';target.save(update_fields=['role','active'])
    audit(request.user,'department.membership_update',target.pk,department=target.department,role=role,active=target.active)
    return redirect('team')

@require_http_methods(['GET','POST'])
def invite_accept(request,raw):
    invite=get_object_or_404(Invitation,token_hash=digest(raw),expires_at__gt=timezone.now(),accepted_at__isnull=True)
    existing_account=User.objects.filter(email__iexact=invite.email).exists()
    form=RegisterForm(request.POST or None,initial={'email':invite.email})
    if request.method=='POST':
        existing=request.user if request.user.is_authenticated else None
        if existing and existing.email.lower()!=invite.email:raise PermissionDenied
        if existing or form.is_valid():
            if not existing and form.cleaned_data['email']!=invite.email:form.add_error('email','Use the invited email address.')
            else:
                with transaction.atomic():
                    invite=Invitation.objects.select_for_update().get(pk=invite.pk)
                    if invite.accepted_at or invite.expires_at<=timezone.now():raise Http404
                    # An outstanding invitation cannot outlive its issuer's authority.
                    membership(invite.invited_by,invite.department,roles=['owner','manager'])
                    if existing:user=existing
                    else:user=form.save(commit=False);user.username=invite.email;user.verified_at=timezone.now();user.save()
                    # Possession of the emailed high-entropy invitation verifies this mailbox.
                    if not user.verified_at:user.verified_at=timezone.now();user.save(update_fields=['verified_at'])
                    Membership.objects.get_or_create(user=user,department=invite.department,defaults={'role':invite.role})
                    welcome_credit(user);invite.accepted_at=timezone.now();invite.save(update_fields=['accepted_at'])
                    audit(user,'department.invitation_accepted',invite.pk,department=invite.department)
                messages.success(request,'Invitation accepted; your personal welcome credit is available.');return redirect('login')
    return render(request,'register.html',{'form':form,'invitation':invite,'existing_invited_account':existing_account})

@require_POST
def coding(request,pk):
    from .coding import suggest
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    membership(request.user,e.department)
    count=suggest(e,request.user)
    messages.info(request,f'{count} new suggestions from explicitly documented codes. Diagnosis inference is not enabled. CPT requires a licensed current feed.')
    return redirect('/encounters/'+str(pk)+'/?tab=coding')

@require_POST
@transaction.atomic
def accept_code(request,pk,code_pk):
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    membership(request.user,e.department,roles=['owner','clinician'])
    item=get_object_or_404(CodeSuggestion.objects.select_for_update(),pk=code_pk,encounter=e)
    if item.terminology.release.effective_until<timezone.localdate():raise ValidationError('This code release is no longer current.')
    if item.evidence not in e.notes:raise ValidationError('Source documentation changed; generate new coding suggestions.')
    if item.system=='CPT' and (not settings.CPT_LICENSE_ID or item.terminology.release.license_reference!=settings.CPT_LICENSE_ID or settings.CPT_LICENSE_EXPIRY<timezone.localdate().isoformat()):raise PermissionDenied
    item.accepted_by=request.user;item.accepted_at=timezone.now();item.save(update_fields=['accepted_by','accepted_at'])
    audit(request.user,'coding.accept',item.pk,department=e.department,code=item.code,release=item.terminology.release.version)
    return redirect('/encounters/'+str(pk)+'/?tab=coding')

def billing(request):
    from .billing import checkout_form
    personal=Wallet.objects.filter(user=request.user)
    owned_orgs=Membership.objects.filter(user=request.user,active=True,role='owner').values_list('department__organization_id',flat=True)
    wallets=Wallet.objects.filter(models.Q(user=request.user)|models.Q(organization_id__in=owned_orgs))
    usage=list(Usage.objects.filter(user=request.user).select_related('user','department','job__providerreceipt','costreconciliation__recorded_by').order_by('-created_at')[:100])
    return render(request,'billing.html',{'wallets':wallets,'ledger':LedgerEntry.objects.filter(wallet__in=wallets).select_related('wallet').order_by('-created_at')[:100],'usage':usage_rows(usage),'payments':Payment.objects.filter(user=request.user).select_related('wallet__organization').order_by('-created_at')[:30],'form':checkout_form(request.user),'checkout_token':signing.dumps({'user':str(request.user.pk),'nonce':secrets.token_hex(24)},salt='checkout-authorization')})

def usage_rows(usage):
    # Reconciled and absorbed evidence is read from the append-only ledger; the usage rows themselves are never edited.
    absorbed={entry['job_id']:entry['total'] for entry in LedgerEntry.objects.filter(kind='absorbed',job_id__in=[item.job_id for item in usage]).values('job_id').annotate(total=models.Sum('amount'))}
    return [{'usage':item,'reconciliation':item.reconciliation,'absorbed':absorbed.get(item.job_id)} for item in usage]

@require_POST
def checkout(request):
    import stripe
    from .billing import checkout_form
    form=checkout_form(request.user,request.POST)
    if not form.is_valid():messages.error(request,'Confirm a one-time amount between $5 and $500.');return redirect('billing')
    if not stripe_test_key_configured(settings.STRIPE_SECRET_KEY):messages.error(request,'A Stripe test or restricted test key is required. No charge was made.');return redirect('billing')
    try:
        authorization=signing.loads(request.POST.get('checkout_token',''),salt='checkout-authorization',max_age=900)
        if authorization.get('user')!=str(request.user.pk) or not isinstance(authorization.get('nonce'),str):raise signing.BadSignature()
    except (signing.BadSignature,ValueError,TypeError):
        messages.error(request,'Reload billing to authorize this one-time checkout.');return redirect('billing')
    if not rate_limit('checkout:'+str(request.user.pk),limit=10):return HttpResponse('Try again later.',status=429)
    payer=form.cleaned_data.get('payer') or 'personal'
    request_key=hashlib.sha256((str(request.user.pk)+':'+authorization['nonce']).encode()).hexdigest()
    amount_cents=int(form.cleaned_data['amount']*100)
    with transaction.atomic():
        if payer=='personal':wallet=Wallet.objects.get(user=request.user,kind='paid')
        else:
            organization_id=payer.split(':',1)[1]
            if not Membership.objects.select_for_update().filter(user=request.user,user__is_active=True,user__verified_at__isnull=False,active=True,role='owner',department__organization_id=organization_id).exists():raise PermissionDenied
            wallet,_=Wallet.objects.get_or_create(organization_id=organization_id,kind='paid')
        p,created=Payment.objects.get_or_create(request_key=request_key,defaults={'user':request.user,'wallet':wallet,'amount_cents':amount_cents,'status':'creating'})
        if p.user_id!=request.user.pk or p.amount_cents!=amount_cents or p.wallet_id!=wallet.pk:raise ValidationError('A repeated checkout must use the original authorized balance and amount.')
        if not created:
            if p.checkout_url and p.status in ['pending','processing']:return redirect(p.checkout_url)
            messages.info(request,'This checkout was already submitted. Its payment status remains visible in billing.');return redirect('billing')
    try:
        session=stripe.checkout.Session.create(api_key=settings.STRIPE_SECRET_KEY,mode='payment',line_items=[{'price_data':{'currency':'usd','unit_amount':p.amount_cents,'product_data':{'name':'QuillMD one-time wallet credit (test)'}},'quantity':1}],metadata={'payment_id':str(p.pk)},success_url='http://localhost:9130/billing/?payment=processing',cancel_url='http://localhost:9130/billing/',idempotency_key=f'checkout:{p.pk}')
        with transaction.atomic():
            p=Payment.objects.select_for_update().get(pk=p.pk)
            if p.stripe_session and p.stripe_session!=session.id:raise ValidationError('Checkout session requires reconciliation.')
            p.stripe_session=session.id;p.checkout_url=session.url
            if p.status=='creating':p.status='pending'
            p.save(update_fields=['stripe_session','checkout_url','status'])
        audit(request.user,'payment.checkout',p.pk,amount_cents=p.amount_cents)
        return redirect(session.url)
    except Exception:
        Payment.objects.filter(pk=p.pk,status='creating').update(status='uncertain')
        audit(request.user,'payment.checkout_uncertain',p.pk)
        messages.error(request,'Checkout could not be confirmed. No paid balance was granted by this request.');return redirect('billing')

@csrf_exempt
@require_POST
def webhook(request):
    import stripe
    from .billing import record_stripe_event,process_stripe_event
    if not settings.STRIPE_WEBHOOK_SECRET:return HttpResponse(status=503)
    if len(request.body)>1024*1024:return HttpResponse(status=413)
    try:event=stripe.Webhook.construct_event(request.body,request.headers.get('Stripe-Signature',''),settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError,stripe.SignatureVerificationError):return HttpResponse(status=400)
    if event.get('livemode') is not False:return HttpResponse('Only explicit test-mode payment events are accepted.',status=400)
    try:
        row=record_stripe_event(event,hashlib.sha256(request.body).hexdigest())
        if not process_stripe_event(row.pk):return HttpResponse('Payment requires reconciliation.',status=409)
    except (ValidationError,IntegrityError,TypeError,KeyError):return HttpResponse('Payment requires reconciliation.',status=409)
    return HttpResponse(status=200)

def admin_dashboard(request):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    counts={'accounts':User.objects.count(),'organizations':Organization.objects.count(),'departments':Department.objects.count(),'jobs':Job.objects.count(),'welcome_credits':LedgerEntry.objects.filter(kind='welcome').count()}
    audit(request.user,'admin.dashboard')
    usage=list(Usage.objects.select_related('user','department','organization','job__providerreceipt','costreconciliation__recorded_by').order_by('-created_at')[:100])
    platform_costs=list(PlatformCost.objects.select_related('job','recorded_by').order_by('-created_at')[:100])
    platform_totals={label:PlatformCost.objects.filter(kind=kind).aggregate(total=models.Sum('amount'))['total'] or Decimal('0') for kind,label in PlatformCost.KINDS}
    return render(request,'admin_dashboard.html',{'counts':counts,'users':User.objects.order_by('-date_joined')[:100],'memberships':Membership.objects.select_related('user','department__organization')[:100],'jobs':Job.objects.select_related('user','encounter').order_by('-created_at')[:100],'usage':usage,'usage_rows':usage_rows(usage),'platform_costs':platform_costs,'platform_totals':platform_totals,'resolution_form':JobResolutionForm(),'platform_cost_form':PlatformCostForm(),'reconciliation_form':ReconciliationForm(),'payments':Payment.objects.select_related('user').order_by('-created_at')[:100],'refunds':Refund.objects.select_related('payment').order_by('-created_at')[:100],'stripe_events':WebhookEvent.objects.order_by('-created_at')[:100],'wallets':Wallet.objects.select_related('user','organization')[:100],'ledger':LedgerEntry.objects.select_related('wallet').order_by('-created_at')[:100],'reconciliation':reconciliation(),'receipts':ProviderReceipt.objects.select_related('job').order_by('-created_at')[:100],'audit_events':AuditEvent.objects.select_related('actor').order_by('-created_at')[:100]})

@require_POST
def admin_reconcile_usage(request,pk):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    usage=get_object_or_404(Usage,pk=pk)
    form=ReconciliationForm(request.POST)
    if not form.is_valid():raise ValidationError('; '.join(f'{field}: {" ".join(errors)}' for field,errors in form.errors.items()))
    data=form.cleaned_data
    row=reconcile_usage(usage,data['reconciled_cost'],data['evidence_reference'],request.user,provider_credit_applied=data.get('provider_credit_applied') or Decimal('0'),discount_applied=data.get('discount_applied') or Decimal('0'),evidence_sha256=data.get('evidence_sha256') or '',note=data.get('note') or '')
    messages.success(request,f'Reconciliation recorded. Charge delta ${row.charge_delta}; ledger status {row.ledger_status}.')
    return redirect('/console/#cost-reconciliation')

@require_POST
@transaction.atomic
def admin_platform_cost(request):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    form=PlatformCostForm(request.POST)
    if not form.is_valid():raise ValidationError('; '.join(f'{field}: {" ".join(errors)}' for field,errors in form.errors.items()))
    data=form.cleaned_data
    row=PlatformCost.objects.create(kind='fixed_overhead',amount=data['amount'],description=data['description'],period_start=data.get('period_start'),period_end=data.get('period_end'),evidence_reference=data.get('evidence_reference') or '',recorded_by=request.user)
    audit(request.user,'platform_cost.recorded',row.pk,kind=row.kind,amount=str(row.amount))
    messages.success(request,'Fixed overhead recorded. It is tracked separately and never charged to users.')
    return redirect('/console/#platform-costs')

@require_POST
@transaction.atomic
def admin_resolve_job(request,pk):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    job=get_object_or_404(Job.objects.select_for_update().select_related('encounter__department'),pk=pk)
    if job.state!='reconciliation':return HttpResponse('Only jobs held for reconciliation can be resolved.',status=409)
    form=JobResolutionForm(request.POST)
    if not form.is_valid():raise ValidationError('; '.join(f'{field}: {" ".join(errors)}' for field,errors in form.errors.items()))
    data=form.cleaned_data;note=data['evidence_note'].strip()
    from .billing import absorb_failed_job
    settled=Usage.objects.filter(job=job,simulated=False).first()
    simulated=Usage.objects.filter(job=job,simulated=True).exists() or (job.kind=='generation' and job.config.get('mode',settings.AI_MODE)!='live')
    release(job)
    job.state='failed';job.finished_at=timezone.now()
    job.error='Resolved by administrator: settled provider cost absorbed by QuillMD.' if settled else 'Resolved by administrator: synthetic fixture job carries no provider cost.' if simulated else 'Resolved by administrator: no provider cost evidenced.' if data['outcome']=='release_no_cost' else 'Resolved by administrator: provider cost absorbed by QuillMD.'
    job.save(update_fields=['state','error','finished_at'])
    if settled:
        # The worker settled the charge before the outcome became uncertain: reverse it, whatever amount the form carried.
        absorbed=absorb_failed_job(job,actor=request.user,note=note)
    elif simulated: absorbed=None
    elif data['outcome']=='absorb_platform_failure':
        absorbed,_=PlatformCost.objects.get_or_create(job=job,kind='absorbed_failure',defaults={'amount':data['actual_cost'],'description':'Provider cost absorbed: uncertain outcome resolved by administrator','evidence_reference':note,'recorded_by':request.user})
    else: absorbed=None
    audit(request.user,'job.resolved',job.pk,department=job.encounter.department,outcome=data['outcome'],evidence_note=note,settled_usage=bool(settled),simulated=simulated,actual_cost=str(absorbed.amount) if absorbed else None)
    messages.success(request,'Job resolved. Held funds were released and the settled charge was reversed.' if settled else 'Job resolved. Held funds were released and the user was not charged.')
    return redirect('/console/#jobs')

def audit_view(request):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    q=request.GET.get('q','')[:100]
    events=AuditEvent.objects.select_related('actor','department','organization').filter(models.Q(action__icontains=q)|models.Q(actor__email__icontains=q)|models.Q(target__icontains=q)).order_by('-created_at')[:200]
    return render(request,'audit.html',{'audit_events':events,'query':q})

@require_POST
@transaction.atomic
def admin_account(request,pk):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    user=get_object_or_404(User.objects.select_for_update(),pk=pk)
    if user.is_staff:raise PermissionDenied('Administrators cannot be changed through this screen.')
    user.is_active=request.POST.get('active')=='on';user.save(update_fields=['is_active'])
    audit(request.user,'admin.account_access',user.pk,active=user.is_active)
    return redirect('admin_dashboard')

# Minimal API endpoints share the same query boundary as HTML and downloads.
def api_patients(request):
    q=request.GET.get('q','')[:140]
    return JsonResponse({'patients':list(scoped(Patient,request.user).filter(display_name__icontains=q).values('id','display_name','reference','department_id')[:100])})
def api_encounter(request,pk):
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    audit(request.user,'api.encounter_read',e.pk,department=e.department)
    return JsonResponse({'id':str(e.pk),'notes':e.notes,'answers':e.answers,'status':e.status,'revision':e.revision})

@require_POST
@transaction.atomic
def encounter_notes(request,pk):
    e=get_object_or_404(scoped(Encounter,request.user).select_for_update(),pk=pk)
    if e.status=='finalized' or Job.objects.filter(encounter=e,state__in=['queued','running','reconciliation']).exists():return HttpResponse('This document is locked.',status=409)
    if request.POST.get('revision')!=str(e.revision):return HttpResponse('Reload before editing changed notes.',status=409)
    notes=request.POST.get('notes','')
    if not notes.strip() or len(notes)>50000:return HttpResponse('Notes must contain 1–50,000 characters; nothing was truncated.',status=400)
    e.notes=notes;e.answers={};e.revision+=1;e.status='draft';wm_review.invalidate_review(e);e.save(update_fields=['notes','answers','revision','status','template_review'])
    CodeSuggestion.objects.filter(encounter=e).update(accepted_by=None,accepted_at=None)
    CodeSuggestion.objects.filter(encounter=e).delete()
    audit(request.user,'coding.invalidated_by_source_edit',e.pk,department=e.department)
    audit(request.user,'encounter.notes_saved',e.pk,department=e.department,revision=e.revision)
    messages.success(request,'Notes saved. Generate and review a new answer draft.');return redirect('encounter_detail',pk=pk)

def job_result(request,pk):
    job=get_object_or_404(Job.objects.filter(encounter__department__in=departments(request.user)),pk=pk)
    receipt=get_object_or_404(ProviderReceipt,job=job)
    if not job.result_path:raise Http404('Provider output was not stored; financial receipt is retained.')
    # Output of a request that is not charged (absorbed platform failure, pending reconciliation) is not delivered.
    if not billable_outcome(job):raise Http404('Provider output is delivered only for requests that stand charged.')
    path=private_path(job.result_path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=job.result_sha256:raise ValidationError('Provider output integrity check failed.')
    audit(request.user,'job.result_download',job.pk,department=job.encounter.department)
    return FileResponse(path.open('rb'),as_attachment=True,filename=f'quillmd-provider-result-{str(job.pk)[:8]}.json',content_type='application/json')


def usage_quote(request,encounter):
    from .generation import configuration
    raw=request.POST.get('usage_quote')
    if not raw and settings.AI_MODE!='live':return configuration()
    try:
        quote=signing.loads(raw,salt='usage-quote',max_age=600)
        if quote['user']!=str(request.user.pk) or quote['encounter']!=str(encounter.pk) or quote['revision']!=encounter.revision:raise ValueError()
        return quote['config']
    except (signing.BadSignature,ValueError,TypeError,KeyError):
        raise ValidationError('Usage quote expired or changed. Reload to review the current maximum charge.')
