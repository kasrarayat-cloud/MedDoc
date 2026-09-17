import hashlib
import json
import os
import re
import secrets
from datetime import timedelta
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
from .billing import welcome_credit,credit_payment,reconcile_refund,reconciliation,stripe_test_key_configured
from .context import integration_status
from .jobs import enqueue


def error_message(exc):
    return '; '.join(exc.messages) if isinstance(exc,ValidationError) else str(exc)

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
                TemplateVersion.objects.create(template=t,number=1,fields=info['fields'],created_by=request.user)
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
                fields=[{**f,'label':labels[f['key']]} for f in latest.fields]
                version=TemplateVersion.objects.create(template=t,number=latest.number+1,fields=fields,created_by=request.user)
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
    e=get_object_or_404(scoped(Encounter,request.user).select_related('patient','template_version__template'),pk=pk)
    rows=[{'key':f['key'],'label':f['label'],**e.answers.get(f['key'],{'text':'','status':'missing','evidence':[],'reviewed':False})} for f in e.template_version.fields]
    from .generation import maximum_cost,configuration
    try:maximum_charge=maximum_cost(e.notes,e.template_version.fields)*Decimal('1.5')
    except ValidationError:maximum_charge=None
    audit(request.user,'encounter.view',e.pk,department=e.department)
    return render(request,'encounter_detail.html',{'encounter':e,'answer_rows':rows,'generation_max_charge':maximum_charge,'usage_quote':signing.dumps({'user':str(request.user.pk),'encounter':str(e.pk),'revision':e.revision,'config':configuration()},salt='usage-quote'),'voice_max_charge':Decimal(os.getenv('QUILLMD_VOICE_MAX_COST','0.20'))*Decimal('1.5'),'codes':CodeSuggestion.objects.filter(encounter=e).select_related('terminology__release','accepted_by'),'jobs':Job.objects.filter(encounter=e).order_by('-created_at'),'voice_form':VoiceForm(),'can_finalize':Membership.objects.filter(user=request.user,department=e.department,active=True,role__in=['owner','clinician']).exists()})

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
@transaction.atomic
def save_answers(request,pk):
    e=get_object_or_404(scoped(Encounter,request.user).select_for_update(),pk=pk)
    if e.status=='finalized':return HttpResponse('Finalized documents are immutable.',status=409)
    if Job.objects.filter(encounter=e,state__in=['queued','running','reconciliation']).exists():return HttpResponse('Wait until the pending job is resolved.',status=409)
    if request.POST.get('revision')!=str(e.revision):return HttpResponse('This document changed. Reload before editing.',status=409)
    answers={}
    for field in e.template_version.fields:
        key=field['key'];previous=e.answers.get(key,{'text':'','evidence':[],'status':'missing'})
        value=request.POST.get('answer_'+key,'')
        if len(value)>20000:return HttpResponse('Answer too long; nothing was truncated or saved.',status=400)
        reviewed=request.POST.get('reviewed_'+key)=='on'
        if reviewed:membership(request.user,e.department,roles=['owner','clinician'])
        answers[key]={**previous,'text':value,'reviewed':reviewed,'status':'edited' if value!=previous.get('text','') else previous.get('status','missing'),'reviewed_by':str(request.user.pk) if reviewed else None}
    e.answers=answers;e.revision+=1;e.status='review';e.save(update_fields=['answers','revision','status'])
    audit(request.user,'encounter.answers_saved',e.pk,department=e.department,revision=e.revision)
    messages.success(request,'Edits saved. Review every answer before finalizing.');return redirect('encounter_detail',pk=pk)

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
            fill_template(original,canonical['fields'],{k:v['text'] for k,v in e.answers.items()},out)
            out.chmod(0o600)
            e.export_path=relative;e.export_sha256=hashlib.sha256(out.read_bytes()).hexdigest();e.finalized_at=timezone.now();e.finalized_by=request.user;e.status='finalized';e.save()
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
    return render(request,'billing.html',{'wallets':wallets,'ledger':LedgerEntry.objects.filter(wallet__in=wallets).select_related('wallet').order_by('-created_at')[:100],'usage':Usage.objects.filter(user=request.user).select_related('user','department','job__providerreceipt').order_by('-created_at')[:100],'payments':Payment.objects.filter(user=request.user).select_related('wallet__organization').order_by('-created_at')[:30],'form':checkout_form(request.user),'checkout_token':signing.dumps({'user':str(request.user.pk),'nonce':secrets.token_hex(24)},salt='checkout-authorization')})

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
    return render(request,'admin_dashboard.html',{'counts':counts,'users':User.objects.order_by('-date_joined')[:100],'memberships':Membership.objects.select_related('user','department__organization')[:100],'jobs':Job.objects.select_related('user','encounter').order_by('-created_at')[:100],'usage':Usage.objects.select_related('user','department','organization','job__providerreceipt').order_by('-created_at')[:100],'payments':Payment.objects.select_related('user').order_by('-created_at')[:100],'refunds':Refund.objects.select_related('payment').order_by('-created_at')[:100],'stripe_events':WebhookEvent.objects.order_by('-created_at')[:100],'wallets':Wallet.objects.select_related('user','organization')[:100],'ledger':LedgerEntry.objects.select_related('wallet').order_by('-created_at')[:100],'reconciliation':reconciliation(),'receipts':ProviderReceipt.objects.select_related('job').order_by('-created_at')[:100],'audit_events':AuditEvent.objects.select_related('actor').order_by('-created_at')[:100]})

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
    e.notes=notes;e.answers={};e.revision+=1;e.status='draft';e.save(update_fields=['notes','answers','revision','status'])
    CodeSuggestion.objects.filter(encounter=e).update(accepted_by=None,accepted_at=None)
    CodeSuggestion.objects.filter(encounter=e).delete()
    audit(request.user,'coding.invalidated_by_source_edit',e.pk,department=e.department)
    audit(request.user,'encounter.notes_saved',e.pk,department=e.department,revision=e.revision)
    messages.success(request,'Notes saved. Generate and review a new answer draft.');return redirect('encounter_detail',pk=pk)

def job_result(request,pk):
    job=get_object_or_404(Job.objects.filter(encounter__department__in=departments(request.user)),pk=pk)
    receipt=get_object_or_404(ProviderReceipt,job=job)
    if not job.result_path:raise Http404('Provider output was not stored; financial receipt is retained.')
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
