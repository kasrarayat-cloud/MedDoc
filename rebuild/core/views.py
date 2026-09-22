import hashlib
import json
import os
import re
import secrets
from datetime import datetime,timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID
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
from . import field_location
from .forms import *
from .security import audit,departments,scoped,membership,digest,token,store_upload,private_path,rate_limit
from .billing import welcome_credit,credit_payment,reconcile_refund,reconciliation,stripe_test_key_configured,reconcile_usage,release
from .context import integration_status
from .jobs import enqueue,cancel,CancellationRefused,public_error,billable_outcome,may_cancel,ended_key,deliverable,RecordingOverLimit,transcription_quote,seconds_text,standard_voice_limit,UPLOAD_NAME,notes_full
from .billing import available_balance
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
                if request.POST.get('mapping_version')!=str(latest.pk):
                    form.add_error(None,'This mapping changed. Your unsaved labels are retained below. Compare them with the current mapping before saving again.')
                    return render(request,'template_detail.html',{'template':t,'version':latest,'form':form,'field_rows':field_location.rows(latest.fields),'field_locations':[field_location.describe(f) for f in latest.fields]},status=409)
                if latest.document_backend and labels!={f['key']:f['label'] for f in latest.fields}:
                    raise ValidationError('This qualified Word mapping uses fixed question labels so source evidence remains unambiguous. Keep the original labels.')
                # ⚠️ A RENAME MUST NOT REMOVE THE SIGNATURE PROTECTION. `structure()` excludes the
                # label so a renamed mapping still fills, and `clinician_identity` reads that same
                # editable label — so renaming `Electronically signed by` to `Attending physician`
                # silently turned the signature check OFF for both generation and finalization.
                # Measured: "Dr Someone Else" accepted as the signature of a different clinician.
                from .tab_review import signature_label
                lost=[f['label'] for f in latest.fields
                      if signature_label(f['label']) and not signature_label(labels[f['key']])]
                if lost:raise ValidationError('A signature question keeps a signature label, because the identity check reads it: '+', '.join(sorted(lost))+'. Rename the other questions and leave this one as the form words it.')
                fields=[{**f,'label':labels[f['key']]} for f in latest.fields]
                version=TemplateVersion.objects.create(template=t,number=latest.number+1,fields=fields,review_requirements=latest.review_requirements,document_backend=latest.document_backend,created_by=request.user)
                audit(request.user,'template.mapping_version',version.pk,department=t.department,number=version.number)
            messages.success(request,'New mapping version saved. Existing documents keep their original version.');return redirect('template_detail',pk=t.pk)
        except ValidationError as exc:form.add_error(None,error_message(exc))
    return render(request,'template_detail.html',{'template':t,'version':version,'form':form,'field_rows':field_location.rows(version.fields),'field_locations':[field_location.describe(f) for f in version.fields]})

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
            e=Encounter(department=data['patient'].department,patient=data['patient'],template_version=data['template_version'],created_by=request.user,notes=data['notes'],service_date=data['service_date']);e.full_clean(exclude=['notes','answers','finalized_at','finalized_by','export_path','export_sha256']);e.save()
            audit(request.user,'encounter.create',e.pk,department=e.department)
        return redirect('encounter_detail',pk=e.pk)
    return render(request,'encounter_form.html',{'form':form})

def encounter_detail(request,pk):
    from documents import DocumentError
    from .coding import cpt_licensed
    # Worker adoption and source edits lock the encounter. Capture the related
    # display records while that same row is stable, then release before Word
    # processing. Lazy jobs/codes could otherwise expose a later completion
    # beside answers or source notes loaded before that completion.
    with transaction.atomic():
        e=get_object_or_404(scoped(Encounter,request.user).select_related(
            'patient','department__organization','template_version__template','finalized_by'
        ).select_for_update(of=('self',)),pk=pk)
        jobs=list(Job.objects.filter(encounter=e).order_by('-created_at'))
        visible_codes=CodeSuggestion.objects.filter(encounter=e).select_related('terminology__release','accepted_by')
        # Retain historical suggestions, but do not display licensed descriptors
        # after entitlement expires or changes to a different licensed feed.
        cpt=models.Q(terminology__release__system='CPT')
        if cpt_licensed():
            visible_codes=visible_codes.exclude(cpt & ~models.Q(terminology__release__license_reference=settings.CPT_LICENSE_ID))
        else:
            visible_codes=visible_codes.exclude(cpt)
        codes=list(visible_codes)
        can_finalize=Membership.objects.filter(user=request.user,department=e.department,active=True,role__in=['owner','clinician']).exists()
    is_wm=bool(e.template_version.document_backend)
    rows=[{**f,**e.answers.get(f['key'],{'text':'','status':'missing','evidence':[],'reviewed':False})} for f in e.template_version.fields]
    # ⚠️ A CLINICAL DECISION IS ATTRIBUTED TO THE PERSON WHO MADE IT, NOT TO WHOEVER IS READING.
    # The page told every reader "You accepted this as your answer" — so a second clinician opening
    # the encounter was informed, about somebody else's decision, that they had made it. That is
    # the same misattribution as a finalized record denying an acceptance, pointed the other way.
    # `accept_code`, in this same template, has named its accepter all along.
    accepters={str(pk):email for pk,email in User.objects.filter(
        pk__in={row['accepted_by'] for row in rows if row.get('accepted_by')}).values_list('pk','email')}
    for row in rows:
        row['accepted_by_email']=accepters.get(str(row.get('accepted_by') or ''),'')
        row['accepted_by_me']=str(row.get('accepted_by') or '')==str(request.user.pk)
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
        job.display_error=public_error(job); job.can_cancel=may_cancel(job,request.user); job.deliverable=bool(job.result_path) and deliverable(job)
    transcript_reviews=[]
    applied=set(AuditEvent.objects.filter(action='transcription.applied',target__in=[str(job.pk) for job in jobs]).values_list('target',flat=True))
    for job in jobs:
        if (job.kind=='transcription' and job.config.get('transcript_review_required')
                and job.state=='succeeded' and str(job.pk) not in applied):
            try:
                raw,transcript=review_transcript(job)
                transcript_reviews.append({'job':job,'raw':raw,'text':transcript})
            except (ValidationError,OSError,ValueError):
                job.display_error='The retained transcript could not be verified. Contact an administrator; do not resubmit a paid recording.'
    return render(request,'encounter_detail.html',{'encounter':e,'pending_job':any(job.state in ['queued','running','reconciliation'] for job in jobs),'transcript_reviews':transcript_reviews,'answer_rows':rows,'wm_template':is_wm,'manual_entry':is_wm or bool(e.template_version.fields) and all('tab_form' in f.get('locator',{}) for f in e.template_version.fields),'wm_requirements':requirements,'wm_review_error':review_error,'generation_max_charge':maximum_charge,'usage_quote':signing.dumps({'user':str(request.user.pk),'encounter':str(e.pk),'revision':e.revision,'config':configuration()},salt='usage-quote'),'voice_max_charge':voice_standard()[0],'voice_fits':voice_standard()[1],'voice_notes_full':notes_full(e.notes),'codes':codes,'jobs':jobs,'voice_form':VoiceForm(),'can_finalize':can_finalize,'prior_generations':prior_generations,'prior_transcriptions':prior_transcriptions})

@require_POST
def generate_view(request,pk):
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    try:
        if not rate_limit('generate:'+str(request.user.pk),limit=30):raise ValidationError('Generation rate limit reached.')
        if 'revision' in request.POST and request.POST['revision']!=str(e.revision):raise ValidationError('Source notes changed. Reload before generating answers.')
        quoted=usage_quote(request,e)
        job=enqueue(e,request.user,config=quoted,expected_revision=e.revision)
        if getattr(job,'reused',False):
            # Reached from a stale page (Back, or a second tab): a generation does not renumber the
            # revision, so the succeeded job still holds this request key. Saying "queued" would
            # promise a request that was not made and answers that will not change.
            messages.info(request,'These source notes already have an answer draft from an earlier request. No new request was made and nothing was charged. Edit and save the notes to generate again.')
        else:
            messages.success(request,'Generation queued. Refresh this page to view the result.')
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
    answers={};review_errors=[];newly_accepted=[];withdrawn=[];target_revision=e.revision+1
    for field in e.template_version.fields:
        key=field['key'];previous=e.answers.get(key,{'text':'','evidence':[],'status':'missing'})
        value=request.POST.get('answer_'+key,'')
        # ⚠️ A SUGGESTION BECOMES AN ANSWER ONLY BY AN EXPLICIT ACT, NEVER BY SAVING.
        # The textarea is deliberately NOT prefilled with the suggestion: if it were, an
        # ordinary save would accept it silently, and so would a reopen, an API read or an
        # export. Accepting takes its own checkbox, and typed text wins over it.
        suggestion=str(previous.get('suggestion') or '')
        # ⚠️ AN ACCEPTANCE IS A FACT ABOUT A DECISION ALREADY MADE, SO IT IS CARRIED FORWARD,
        # NOT RECOMPUTED FROM THE POST. Recomputing it withdrew every acceptance on the very next
        # save: once accepted, the page renders the accepted branch, which has NO checkbox to
        # re-post, so an ordinary save of any other field wrote False over a real True — and the
        # finalized record then told the doctor their own decision had not been made. Three
        # independent refutation lenses found this within minutes of each other.
        # It survives only while the stored text is still exactly the suggestion; editing away
        # withdraws it, and typing the same words by hand never grants it.
        accepted=bool(previous.get('accepted_suggestion')) and bool(suggestion) and value==suggestion
        if not value.strip() and request.POST.get('accept_'+key)=='on' and suggestion:
            # ⚠️ GATED LIKE ITS SIBLING. `reviewed` below demands owner/clinician, the template
            # renders this box `disabled` for everyone else, and the server checked nothing — so
            # an employee-role member could clear the conflict gate and have the page state, in
            # the clinician's name, that the suggestion was accepted. `accept_code` two hundred
            # lines down is the in-repo precedent: role-gated, attributed and audited.
            membership(request.user,e.department,roles=['owner','clinician'])
            value=suggestion; accepted=True; newly_accepted.append(key)
        # ⚠️ AND WITHDRAWING ONE NEEDS THE SAME AUTHORITY AS GRANTING ONE. Gating only the grant
        # left an employee-role member able to destroy a clinician's attested decision by an
        # ordinary save — unattributed, unaudited, and silently. Overwriting answer TEXT was
        # already possible before this feature; erasing an attestation was not.
        if previous.get('accepted_suggestion') and not accepted:
            membership(request.user,e.department,roles=['owner','clinician'])
            withdrawn.append(key)
        if len(value)>20000:return HttpResponse('Answer too long; nothing was truncated or saved.',status=400)
        reviewed=request.POST.get('reviewed_'+key)=='on'
        if reviewed:membership(request.user,e.department,roles=['owner','clinician'])
        answers[key]={**previous,'text':value,'reviewed':reviewed,'accepted_suggestion':accepted,
                      # The accepter is whoever performed the explicit act, carried forward while
                      # the acceptance stands. A later saver must not inherit somebody's decision.
                      'accepted_by':str(request.user.pk) if key in newly_accepted else (previous.get('accepted_by') if accepted else None),
                      'status':'edited' if value!=previous.get('text','') else previous.get('status','missing'),'reviewed_by':str(request.user.pk) if reviewed else None}
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
    audit(request.user,'encounter.answers_saved',e.pk,department=e.department,revision=e.revision,
          accepted_suggestions=sorted(newly_accepted),withdrawn_acceptances=sorted(withdrawn))
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
            finalized_at=timezone.now()
            if e.template_version.document_backend:
                version=e.template_version
                # ⚠️ COMPUTED HERE, NOT ABOVE, BECAUSE ONLY THIS BRANCH READS IT. Unconditionally
                # re-inspecting the original made finalization fail for any template the CURRENT
                # contract refuses but the stored mapping's contract accepted — a fixed-height
                # answer cell, or a wider field count — stranding a reviewed encounter that was
                # already generated. The ordinary path below fills through `version.fields` and
                # never needed a fresh inspection at all.
                canonical=inspect_template(original)
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
                from .tab_review import validate_identity
                # ⚠️ THE STORED MAPPING IS THE AUTHORITY, NOT A FRESH INSPECTION. The answers are
                # keyed to `version.fields`, and a fresh inspection can now legitimately differ
                # from it: a template imported before multi-column and mixed support yields FEWER
                # fields, so the same `cell_N` key names a DIFFERENT cell. Passing `canonical`
                # here filled one question's answer into another question's blank — measured on a
                # V1 mapping of [cell_0='Allergies'] re-inspected to [cell_0='Height', …], where
                # the allergy answer landed in the height blank of a finalized document. It also
                # made `fill_template`'s legacy-contract fallback unreachable, because the caller
                # passed the fresh fields as the mapping and the two were equal by construction.
                version=e.template_version
                validate_identity(version.fields,e.answers,request.user)
                fill_template(original,version.fields,{k:v['text'] for k,v in e.answers.items()},out)
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

def voice_standard():
    """The displayed per-recording limit and the length that fits it, from the same quote an upload is checked against."""
    from .generation import configuration
    try:
        quote=transcription_quote(0,configuration())
        return Decimal(quote['standard_limit']),seconds_text(quote['fits_seconds'])
    except (ValidationError,ArithmeticError,KeyError):
        return standard_voice_limit(os.getenv('QUILLMD_VOICE_MAX_COST','0.20')),None


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
        quoted={**usage_quote(request,e),'transcript_review_required':True}
        try:
            job=enqueue(e,request.user,'transcription',relative,config=quoted,expected_revision=e.revision)
        except RecordingOverLimit as over:
            # Nothing was sent and the upload is kept: the doctor chooses a shorter segment or a clearly priced higher limit.
            approval=signing.dumps({'user':str(request.user.pk),'encounter':str(e.pk),'revision':e.revision,'path':relative,
                                    'sha256':hashlib.sha256(private_path(relative).read_bytes()).hexdigest(),
                                    'charge_limit':over.quote['charge_limit'],'config':quoted},salt='voice-limit')
            # The path lets the worker remove the upload if nobody approves it within the approval window.
            audit(request.user,'voice.over_limit_quoted',e.pk,department=e.department,seconds=over.quote['seconds'],
                  charge_limit=over.quote['charge_limit'],standard_limit=over.quote['standard_limit'],path=relative)
            # Whether the balance covers the limit, never the amount: an organization's paid balance is shown to its owners only.
            return render(request,'voice_limit.html',{'encounter':e,'message':error_message(over),'quote':over.quote,'approval':approval,
                'length':seconds_text(over.quote['seconds']),'fits':seconds_text(over.quote['fits_seconds']),
                'standard_limit':Decimal(over.quote['standard_limit']),
                'affordable':available_balance(request.user,e.department)>=Decimal(over.quote['charge_limit'])},status=409)
        if job.input_path!=relative:private_path(relative).unlink(missing_ok=True)
        if getattr(job,'reused',False):
            # The identical recording already holds this request key; the redundant upload was just
            # removed above. Nothing was sent to the provider and nothing was charged again.
            messages.info(request,'This recording was already transcribed for this document. No new request was made and nothing was charged. Its transcript is below in Document record.')
        else:
            messages.success(request,f"Transcription queued with a limit of ${Decimal(job.config.get('charge_limit','0'))}. Review the transcript before generating answers.")
    except ValidationError as exc:
        if relative:private_path(relative).unlink(missing_ok=True)
        messages.error(request,error_message(exc))
    return redirect('encounter_detail',pk=pk)

@require_POST
def voice_approve(request,pk):
    """The doctor's explicit decision on an over-limit recording: approve its quoted higher limit, or take a shorter segment."""
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    shorter=request.POST.get('decision')=='shorter'
    token=request.POST.get('approval','')
    try:
        data=signing.loads(token,salt='voice-limit',max_age=1800)
    except signing.SignatureExpired:
        # An expired approval can no longer queue anything, but choosing a shorter segment still removes its upload.
        if not shorter:
            messages.error(request,'This limit approval has expired. Upload the recording again; nothing was sent.')
            return redirect('encounter_detail',pk=pk)
        data=signing.loads(token,salt='voice-limit')
    except signing.BadSignature:
        messages.error(request,'This limit approval is invalid. Upload the recording again; nothing was sent.')
        return redirect('encounter_detail',pk=pk)
    relative=str(data.get('path',''))
    if (data.get('user')!=str(request.user.pk) or data.get('encounter')!=str(e.pk)
            or not UPLOAD_NAME.fullmatch(relative)):
        raise PermissionDenied
    path=private_path(relative)
    if shorter:
        # Under the encounter lock enqueue takes: a recording an approval already queued is never removed.
        with transaction.atomic():
            Encounter.objects.select_for_update().get(pk=e.pk)
            if Job.objects.filter(input_path=relative).exists():
                messages.info(request,'This recording was already approved and queued; its request is listed below.')
                return redirect('encounter_detail',pk=pk)
            path.unlink(missing_ok=True)
        messages.info(request,'Nothing was sent. Upload a shorter segment: recordings that fit the displayed limit are processed straight away.')
        return redirect('encounter_detail',pk=pk)
    try:
        if data.get('revision')!=e.revision:
            raise ValidationError('The document changed after the quote. Upload the recording again; nothing was sent.')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=data.get('sha256'):
            raise ValidationError('The quoted recording is no longer available. Upload it again; nothing was sent.')
        job=enqueue(e,request.user,'transcription',relative,config=data['config'],approved_limit=data['charge_limit'],expected_revision=data['revision'])
        if job.input_path!=relative:path.unlink(missing_ok=True)
        audit(request.user,'voice.limit_approved',job.pk,department=e.department,charge_limit=str(data['charge_limit']))
        messages.success(request,f"Transcription queued with your approved limit of ${data['charge_limit']}.")
    except ValidationError as exc:
        messages.error(request,error_message(exc))
    except OSError:
        messages.error(request,'The quoted recording is no longer available. Upload it again; nothing was sent.')
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
                    current_membership=Membership.objects.select_for_update().filter(user=user,department=invite.department).first()
                    if current_membership and not current_membership.active:
                        return HttpResponse('Your department access is inactive. Ask the organization owner to restore it. This invitation has not been used.',status=409,content_type='text/plain')
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
    result=suggest(e,request.user)
    served=e.service_date.strftime('%d %B %Y')
    if result.covered:
        messages.info(request,f'{result.count} new suggestions from explicitly documented codes, validated against {", ".join(result.versions)} for the {served} date of service. Diagnosis inference is not enabled. CPT requires a licensed current feed.')
    elif result.versions:
        # A licensed CPT release can answer for a date no diagnosis release covers. Saying "nothing
        # was recorded" here would deny suggestions sitting on the page underneath the message.
        messages.warning(request,f'No ICD-10-CM release covers the {served} date of service, so no diagnosis code was validated. {result.count} new suggestions came from {", ".join(result.versions)}. Import the diagnosis release in effect for that date.')
    else:
        messages.warning(request,f'No terminology release covers the {served} date of service, so nothing was validated and no suggestion was recorded. Import the release in effect for that date.')
    return redirect('/encounters/'+str(pk)+'/?tab=coding')

@require_POST
@transaction.atomic
def accept_code(request,pk,code_pk):
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    membership(request.user,e.department,roles=['owner','clinician'])
    from .coding import applicable_releases,cpt_licensed
    item=get_object_or_404(CodeSuggestion.objects.select_for_update(),pk=code_pk,encounter=e)
    if not applicable_releases(e).filter(pk=item.terminology.release_id).exists():raise ValidationError('This release is not the one in effect for the encounter date of service; generate new coding suggestions.')
    if item.evidence not in e.notes:raise ValidationError('Source documentation changed; generate new coding suggestions.')
    if item.system=='CPT' and (not cpt_licensed() or item.terminology.release.license_reference!=settings.CPT_LICENSE_ID):raise PermissionDenied
    item.accepted_by=request.user;item.accepted_at=timezone.now();item.save(update_fields=['accepted_by','accepted_at'])
    audit(request.user,'coding.accept',item.pk,department=e.department,code=item.code,release=item.terminology.release.version)
    return redirect('/encounters/'+str(pk)+'/?tab=coding')

def billing(request):
    from .billing import checkout_form
    from .admin_queries import page_for,searched
    query=request.GET.get('q','').strip()[:100]
    owned_orgs=Membership.objects.filter(user=request.user,active=True,role='owner').values_list('department__organization_id',flat=True)
    wallets=Wallet.objects.filter(models.Q(user=request.user)|models.Q(organization_id__in=owned_orgs))
    usage=searched(Usage.objects.filter(user=request.user).select_related('user','department','job__providerreceipt','costreconciliation__recorded_by').order_by('-created_at','pk'),query,['provider','provider_request_id','provider_resource_id','department__name'])
    ledger=searched(LedgerEntry.objects.filter(wallet__in=wallets).select_related('wallet').order_by('-created_at','pk'),query,['kind','description','key'])
    payments=searched(Payment.objects.filter(user=request.user).select_related('wallet__organization').order_by('-created_at','pk'),query,['status','stripe_session','stripe_intent'])
    up=page_for(request,usage,'usage_page','usage');lp=page_for(request,ledger,'ledger_page','ledger');pp=page_for(request,payments,'payments_page','payments')
    return render(request,'billing.html',{'wallets':wallets,'ledger':lp['page'],'usage':usage_rows(list(up['page'])),'payments':pp['page'],'usage_navigation':up,'ledger_navigation':lp,'payments_navigation':pp,'query':query,'usage_totals':usage.aggregate(cost=models.Sum('actual_cost'),charge=models.Sum('charged_cost')),'form':checkout_form(request.user),'checkout_token':signing.dumps({'user':str(request.user.pk),'nonce':secrets.token_hex(24)},salt='checkout-authorization')})

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
    from .stripe_validation import validate_event_environment
    try:validate_event_environment(event)
    except ValidationError:return HttpResponse('Payment event environment is not supported.',status=400)
    try:
        row=record_stripe_event(event,hashlib.sha256(request.body).hexdigest())
        if not process_stripe_event(row.pk):return HttpResponse('Payment requires reconciliation.',status=409)
    except (ValidationError,IntegrityError,TypeError,KeyError):return HttpResponse('Payment requires reconciliation.',status=409)
    return HttpResponse(status=200)

def admin_dashboard(request):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    from .admin_queries import page_for,searched
    from . import admin_console
    query=request.GET.get('q','').replace('\x00','').strip()[:100]
    # An inclusive UTC calendar window. When no dates are given `filters` is empty and every
    # queryset below is byte-identical to what it was before the window existed.
    window=admin_console.date_window(request)
    audit(request.user,'admin.dashboard')
    # Third element of each tuple is the DATE COLUMN the window filters on. It is not always
    # `created_at`: User extends AbstractUser and carries `date_joined` instead.
    sources={
        'users':(User.objects.order_by('-date_joined','pk'),['email','first_name','last_name'],'accounts','date_joined'),
        'memberships':(Membership.objects.select_related('user','department__organization').order_by('-created_at','pk'),['user__email','department__name','department__organization__name','role'],'permissions','created_at'),
        'jobs':(Job.objects.select_related('user').order_by('-created_at','pk'),['user__email','kind','state','provider_request_id','provider_resource_id'],'jobs','created_at'),
        'usage':(Usage.objects.select_related('user','department','organization','job__providerreceipt','costreconciliation__recorded_by').order_by('-created_at','pk'),['user__email','department__name','organization__name','provider','provider_request_id','provider_resource_id','payer'],'costs','created_at'),
        'platform_costs':(PlatformCost.objects.select_related('job','recorded_by').order_by('-created_at','pk'),['kind','description','evidence_reference'],'platform-costs','created_at'),
        'payments':(Payment.objects.select_related('user','wallet__user','wallet__organization').order_by('-created_at','pk'),['user__email','status','stripe_session','stripe_intent'],'payments','created_at'),
        'refunds':(Refund.objects.select_related('payment').order_by('-created_at','pk'),['status','stripe_refund','payment__user__email'],'refunds','created_at'),
        'stripe_events':(WebhookEvent.objects.order_by('-created_at','pk'),['event_id','kind','status'],'stripe-events','created_at'),
        'wallets':(Wallet.objects.select_related('user','organization').order_by('-created_at','pk'),['user__email','organization__name','kind'],'credits','created_at'),
        'ledger':(LedgerEntry.objects.select_related('wallet__user','wallet__organization').order_by('-created_at','pk'),['wallet__user__email','wallet__organization__name','kind','key','description'],'credits','created_at'),
        'receipts':(ProviderReceipt.objects.select_related('job').order_by('-created_at','pk'),['provider','provider_request_id','provider_resource_id','job__user__email'],'provider-receipts','created_at'),
    }
    context={'query':query,'window':window}
    for key,(rows,fields,anchor,date_field) in sources.items():
        # One window narrows every list consistently, against whichever date column that model
        # actually has — see admin_console.window_filters for why that is not always created_at.
        filtered=searched(rows.filter(**admin_console.window_filters(window,date_field)),query,fields)
        if key=='jobs' and request.GET.get('job_state'):filtered=filtered.filter(state=request.GET['job_state'][:20])
        if key=='users' and request.GET.get('account_status') in ('active','inactive','unverified'):
            filtered=filtered.filter(verified_at__isnull=True) if request.GET['account_status']=='unverified' else filtered.filter(is_active=request.GET['account_status']=='active')
        navigation=page_for(request,filtered,key+'_page',anchor)
        context[key]=navigation['page'];context[key+'_navigation']=navigation
        if key=='usage':context['usage_totals']=filtered.aggregate(cost=models.Sum('actual_cost'),charge=models.Sum('charged_cost'))
    context.update(usage_rows=usage_rows(list(context['usage'])),
        platform_totals={label:PlatformCost.objects.filter(kind=kind).aggregate(total=models.Sum('amount'))['total'] or Decimal('0') for kind,label in PlatformCost.KINDS},
        reconciliation=reconciliation(),audit_events=AuditEvent.objects.exclude(action='admin.dashboard').select_related('actor').order_by('-created_at','pk')[:8],
        overview=admin_console.business_overview(window),
        processing=admin_console.processing_health(),
        published=admin_console.published_operations(),
        reconciliation_form=ReconciliationForm(),
        refunded=admin_console.refunded_cents([p.pk for p in context['payments']]))
    return render(request,'admin_dashboard.html',context)


def admin_job_detail(request,pk):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    from .admin_queries import financial_context,page_for
    job=get_object_or_404(Job.objects.select_related('user','encounter__department'),pk=pk)
    context=financial_context(job)
    events=AuditEvent.objects.filter(target__in=context.pop('audit_targets')).select_related('actor').order_by('-created_at','pk')
    context['event_navigation']=page_for(request,events,anchor='charge-audit')
    context['audit_events']=context['event_navigation']['page']
    context['administrative']=True
    audit(request.user,'admin.job_financial_read',job.pk)
    return render(request,'financial_detail.html',context)


def billing_job_detail(request,pk):
    from .admin_queries import financial_context
    # Personal billing history remains available after clinical membership revocation.
    # Organization owners can inspect organization-paid charges without clinical access.
    owned=Membership.objects.filter(user=request.user,active=True,role='owner').values_list('department__organization_id',flat=True)
    allowed=models.Q(user=request.user)|models.Q(payer__in=[f'organization:{pk}' for pk in owned])
    job=get_object_or_404(Job.objects.filter(allowed).select_related('user','encounter__department'),pk=pk)
    visible=set(Wallet.objects.filter(models.Q(user=request.user)|models.Q(organization_id__in=owned)).values_list('pk',flat=True))
    context=financial_context(job,visible);context.pop('audit_targets')
    audit(request.user,'billing.job_read',job.pk)
    return render(request,'financial_detail.html',context)

@require_POST
def admin_reconcile_usage(request,pk):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    usage=get_object_or_404(Usage,pk=pk)
    form=ReconciliationForm(request.POST)
    if not form.is_valid():raise ValidationError('; '.join(f'{field}: {" ".join(errors)}' for field,errors in form.errors.items()))
    data=form.cleaned_data
    row=reconcile_usage(usage,data['reconciled_cost'],data['evidence_reference'],request.user,evidence_kind=data['evidence_kind'],provider_credit_applied=data.get('provider_credit_applied') or Decimal('0'),discount_applied=data.get('discount_applied') or Decimal('0'),evidence_sha256=data.get('evidence_sha256') or '',note=data.get('note') or '')
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
    # Lock only the job row, as settle, cancel and absorb do: locking the encounter and department before the wallets deadlocks a wallet holder that audits.
    job=get_object_or_404(Job.objects.select_for_update(of=('self',)).select_related('encounter__department'),pk=pk)
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
    # A resolved job ended without success: free its request key so the same revision or recording can be requested again.
    job.request_key=ended_key(job,'failed')
    job.save(update_fields=['state','error','finished_at','request_key'])
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
    from .admin_queries import page_for
    from . import admin_console
    q=request.GET.get('q','').replace('\x00','')[:100]
    window=admin_console.date_window(request)
    events=AuditEvent.objects.select_related('actor','department','organization').filter(models.Q(action__icontains=q)|models.Q(actor__email__icontains=q)|models.Q(target__icontains=q)).filter(**window['filters']).order_by('-created_at','pk')
    # An EXACT action match, beside the free-text box rather than replacing it. `action__icontains`
    # silently widens across a family: 'payment.refund' also matches 'payment.refund_failed', and
    # 'admin.account' matches 'admin.account_read' — so an investigator filtering for one action can
    # be reading three. The picker is populated from the actions that actually exist, so it can
    # never offer a value that returns nothing.
    # A NUL byte cannot exist in PostgreSQL text; psycopg raises DataError out of the view.
    action=request.GET.get('action','').replace('\x00','')[:70]
    if action:events=events.filter(action=action)
    actions=list(AuditEvent.objects.values_list('action',flat=True).order_by('action').distinct())
    audit(request.user,'admin.audit_read',query=q,action_filter=action,window=window['label'])
    navigation=page_for(request,events,size=50)
    return render(request,'audit.html',{'audit_events':navigation['page'],'query':q,'navigation':navigation,
                                        'window':window,'actions':actions,'action':action})

@require_POST
@transaction.atomic
def admin_account(request,pk):
    if not request.user.is_staff or not request.user.is_verified():raise Http404
    user=get_object_or_404(User.objects.select_for_update(),pk=pk)
    if user.is_staff:raise PermissionDenied('Administrators cannot be changed through this screen.')
    active=request.POST.get('active')=='on'
    revoked=user.is_active and not active
    if revoked:user.session_version+=1
    user.is_active=active;user.save(update_fields=['is_active','session_version'])
    audit(request.user,'admin.account_access',user.pk,active=user.is_active,sessions_invalidated=revoked)
    if revoked:
        # ⚠️ SUSPENDING AN ACCOUNT CAN LEAVE A DEPARTMENT WITH NO USABLE OWNER, and this is
        # deliberately NOT refused: a security suspension must never be blocked by organization
        # structure. The membership screen refuses the equivalent edit, so the invariant it states
        # is about THAT screen, not about the product. Here the state is announced instead.
        orphaned=[m.department.name for m in Membership.objects.filter(user=user,active=True,role='owner').select_related('department')
                  if not Membership.objects.filter(department=m.department_id,active=True,role='owner',user__is_active=True,user__verified_at__isnull=False).exclude(user=user).exists()]
        if orphaned:
            messages.warning(request,'Suspended. '+', '.join(orphaned)+' now has no active, verified owner: nobody can invite into it, create patients in it, or restore access from the clinician side. Give another member the owner role.')
        else:
            messages.success(request,'Account suspended and signed out of every session.')
    elif user.is_active:
        messages.success(request,'Account enabled. Existing sessions were not restored; the account can sign in again.')
    return redirect(request.POST.get('back') if (request.POST.get('back') or '').startswith('/console/') else 'admin_dashboard')

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
    transcript_job=None;raw_transcript=None
    if request.POST.get('transcript_job'):
        try:transcript_id=UUID(request.POST['transcript_job'])
        except (ValueError,TypeError):return HttpResponse('Invalid transcript reference.',status=400)
        transcript_job=get_object_or_404(Job,pk=transcript_id,encounter=e,kind='transcription',state='succeeded')
        if not transcript_job.config.get('transcript_review_required') or AuditEvent.objects.filter(action='transcription.applied',target=str(transcript_job.pk)).exists():
            return HttpResponse('This transcript has already been applied or is not awaiting review.',status=409)
        if request.POST.get('transcript_reviewed')!='on' or request.POST.get('transcript_mode') not in ['append','replace']:
            return HttpResponse('Review the transcript and choose how to add it to the source notes.',status=400)
        try:raw_transcript,_=review_transcript(transcript_job)
        except (ValidationError,OSError,ValueError):return HttpResponse('The retained transcript could not be verified. Nothing changed.',status=409)
        corrected=request.POST.get('corrected_transcript','')
        if not corrected.strip() or len(corrected)>50000:return HttpResponse('Reviewed transcript must contain 1–50,000 characters.',status=400)
        notes=(e.notes+'\n\n'+corrected if e.notes else corrected) if request.POST['transcript_mode']=='append' else corrected
    else:notes=request.POST.get('notes','')
    if not notes.strip() or len(notes)>50000:return HttpResponse('Notes must contain 1–50,000 characters; nothing was truncated.',status=400)
    e.notes=notes;e.answers={};e.revision+=1;e.status='draft';wm_review.invalidate_review(e);e.save(update_fields=['notes','answers','revision','status','template_review'])
    CodeSuggestion.objects.filter(encounter=e).update(accepted_by=None,accepted_at=None)
    CodeSuggestion.objects.filter(encounter=e).delete()
    audit(request.user,'coding.invalidated_by_source_edit',e.pk,department=e.department)
    audit(request.user,'encounter.notes_saved',e.pk,department=e.department,revision=e.revision)
    if transcript_job:
        audit(request.user,'transcription.applied',transcript_job.pk,department=e.department,revision=e.revision,
              mode=request.POST['transcript_mode'],raw_sha256=hashlib.sha256(raw_transcript.encode()).hexdigest(),
              corrected_sha256=hashlib.sha256(corrected.encode()).hexdigest(),corrected=corrected.replace('\r\n','\n')!=raw_transcript.replace('\r\n','\n'))
    messages.success(request,'Notes saved. Generate and review a new answer draft.');return redirect('encounter_detail',pk=pk)

def review_transcript(job):
    """Read only the bounded, hash-bound retained result for a reviewed transcript."""
    if not job.result_path or not deliverable(job):raise ValidationError('Transcript is not deliverable.')
    with private_path(job.result_path).open('rb') as source:payload=source.read(1024*1024+1)
    if len(payload)>1024*1024 or hashlib.sha256(payload).hexdigest()!=job.result_sha256:
        raise ValidationError('Transcript integrity check failed.')
    data=json.loads(payload)
    if not isinstance(data,dict) or not isinstance(data.get('raw_transcript'),str) or not isinstance(data.get('transcript'),str):
        raise ValidationError('Transcript is unavailable.')
    return data['raw_transcript'],data['transcript']


def job_result(request,pk):
    job=get_object_or_404(Job.objects.filter(encounter__department__in=departments(request.user)),pk=pk)
    receipt=get_object_or_404(ProviderReceipt,job=job)
    if not job.result_path:raise Http404('Provider output was not stored; financial receipt is retained.')
    # Output of a request that is not charged (absorbed platform failure, pending reconciliation) is not delivered.
    if not deliverable(job):raise Http404('Provider output is delivered only for charged requests and usable transcripts.')
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
