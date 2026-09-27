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
from .security import audit,departments,scoped,membership,digest,token,store_upload,private_path,rate_limit,client_address
from .billing import welcome_credit,welcome_credit_label,credit_payment,reconcile_refund,reconciliation,stripe_test_key_configured,stripe_key_configured,reconcile_usage,release
from .context import integration_status
from .jobs import enqueue,cancel,CancellationRefused,public_error,billable_outcome,may_cancel,ended_key,deliverable,RecordingOverLimit,transcription_quote,seconds_text,standard_voice_limit,UPLOAD_NAME,notes_full
from .billing import available_balance
from . import wm_review
from . import v3_mapping


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
    sent=wm_review.sdk_answers(encounter,actor)
    result=resolve_template(original,version.document_backend,sent,
                            claim_variants=variants,trusted_context=context)
    if (result.get('backend')!=version.document_backend.get('backend')
            or result.get('mapping_digest')!=version.document_backend.get('mapping_digest')
            or result.get('sha256')!=version.template.sha256):
        raise ValidationError('The resolved Word statements differ from the selected mapping version.')
    if result.get('conflicts'):
        # The adapter names each conflict; say which statement and which answers, on the page only.
        from .wm_conflicts import WmConflicts,describe
        raise WmConflicts(describe(result['conflicts'],version,sent,variants))
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
    'text_the_form_rewrites_labelled':'The form reads "&p", "&l", "&m", "&b" and "&&" in this table cell as formatting codes (a break, or a single "&"), so it would print differently from this answer, and on this form an answer must repeat its labelled line exactly. Change that line in the notes: write the letter after "&" as a capital (for example "thigh&Mid calf") or write "and". Then save the notes and generate again.',
}

#: ⚠️ `data_mode` WAS A HARDCODED LITERAL AND WAS BEING CITED AS PROOF OF THE GUARD.
#: It printed 'synthetic-only' unconditionally, so it would have kept printing it with
#: SYNTHETIC_ONLY flipped to False — every check that read /health/ as evidence of
#: synthetic-only operation was reading a label that could not disagree with itself.
#: It is now derived from the setting the seed and verification commands actually enforce.
#: 'real' only when the declared data mode is real (settings refused to start otherwise). The guard
#: switched off WITHOUT the declared real profile — reachable only by overriding settings — still
#: reports 'live', so the positive control above keeps a value that cannot pass for either mode.
def health_data_mode():
    if settings.SYNTHETIC_ONLY:return 'synthetic-only'
    return 'real' if getattr(settings,'QUILLMD_DATA_MODE','synthetic')=='real' else 'live'
def health(request): return JsonResponse({'status':'ok','data_mode':health_data_mode(),'surface':'admin' if settings.ADMIN_SITE else 'doctor','release':settings.RELEASE_SHA})

@require_http_methods(['GET','POST'])
def login_view(request):
    form=LoginForm(request.POST or None)
    next_url=request.POST.get('next',request.GET.get('next',''))
    if not next_url.startswith('/') or not url_has_allowed_host_and_scheme(next_url,allowed_hosts=set()):next_url=''
    if request.method=='POST' and form.is_valid():
        email=form.cleaned_data['email'].lower()
        if not rate_limit('login-ip:'+client_address(request),limit=40) or not rate_limit('login-email:'+email):
            form.add_error(None,'Too many sign-in attempts. Try again later.')
        else:
            found=User.objects.filter(email__iexact=email).first()
            user=authenticate(request,username=found.username if found else email,password=form.cleaned_data['password'])
            device=None
            enrol=False
            # Administrators always need a confirmed authenticator. With QUILLMD_MFA_REQUIRED_ALL every account
            # that HAS one must present its code; an account without one signs in with its password only far
            # enough to enrol: AccessMiddleware confines that session to /mfa/ until a code is verified.
            if user and (user.is_staff or settings.QUILLMD_MFA_REQUIRED_ALL):
                with transaction.atomic():
                    device=TOTPDevice.objects.select_for_update().filter(user=user,confirmed=True).first()
                    if device:
                        if not device.verify_token(form.cleaned_data['otp']): user=None
                    elif user.is_staff: user=None
                    else: enrol=True
            if user and user.verified_at and (not settings.ADMIN_SITE or user.is_staff):
                auth_login(request,user)
                if device: otp_login(request,device)
                if enrol:
                    audit(user,'auth.login',mfa_enrolment_required=True)
                    return redirect('mfa_setup')
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
    # QUILLMD_REGISTRATION=invite closes self-service sign-up entirely: accounts arrive only through a
    # department invitation or an administrator's clinic-owner invitation.
    if settings.ADMIN_SITE or settings.QUILLMD_REGISTRATION!='open': raise Http404
    form=RegisterForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        if not rate_limit('register:'+client_address(request),limit=5):return HttpResponse('Try again later.',status=429)
        with transaction.atomic():
            user=form.save(commit=False);user.username=form.cleaned_data['email'];user.save()
            raw=token();verification=Verification.objects.create(user=user,token_hash=digest(raw),expires_at=timezone.now()+timedelta(hours=24))
            audit(user,'account.register')
        delivery=verification_mail(user,raw,verification)
        if delivery.status=='outbox':messages.success(request,'Verification created in the private development outbox. Email delivery is not live yet.')
        elif delivery.status=='accepted':messages.success(request,'Verification submitted to the email provider. Check your inbox; inbox delivery is not yet confirmed.')
        else:messages.warning(request,'Account created, but verification email delivery could not be confirmed. Ask your administrator to recover the verification link or retry delivery.'+(' No welcome credit has been granted yet.' if welcome_credit_label() else ''))
        return redirect('login')
    return render(request,'register.html',{'form':form})

@require_http_methods(['GET','POST'])
def verify(request,raw):
    v=get_object_or_404(Verification,token_hash=digest(raw),expires_at__gt=timezone.now(),used_at__isnull=True)
    if request.method=='GET':
        label=welcome_credit_label() if settings.QUILLMD_REGISTRATION=='open' else ''
        return render(request,'confirm.html',{'title':'Verify your test account' if settings.SYNTHETIC_ONLY else 'Verify your account','description':f'Confirm ownership of this email to activate your personal {label} welcome credit.' if label else 'Confirm ownership of this email to activate your account.'})
    with transaction.atomic():
        user=User.objects.select_for_update().get(pk=v.user_id)
        v=Verification.objects.select_for_update().get(pk=v.pk)
        if v.used_at or v.expires_at<=timezone.now() or user.verified_at or not user.is_active: raise Http404
        user.verified_at=timezone.now();user.save(update_fields=['verified_at'])
        v.used_at=timezone.now();v.save(update_fields=['used_at'])
        if settings.QUILLMD_REGISTRATION!='open':
            # Invite-only: a verification link can only belong to an account registered before sign-up closed.
            # It proves the mailbox and nothing more. A personal organization is self-service onboarding, which
            # this mode closed; the account joins a clinic by invitation, and receives the credit when it does.
            audit(user,'account.verified',user.pk,workspace_created=False)
            messages.success(request,'Email verified. Sign in to accept the invitation your clinic sends you.');return redirect('login')
        org=Organization.objects.create(name=f'{user.first_name or "Personal"} workspace')
        dept=Department.objects.create(organization=org,name='Personal practice')
        Membership.objects.create(user=user,department=dept,role='owner')
        welcome_credit(user);audit(user,'account.verified',user.pk)
    label=welcome_credit_label()
    messages.success(request,f'Email verified. Your {label} personal welcome credit is available.' if label else 'Email verified.');return redirect('login')

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
    # QUILLMD_MFA_REQUIRED_ALL puts every clinician through this page, many on a phone that cannot scan its own
    # screen: the same key is also shown as grouped text for manual entry. Default mode renders the page as before.
    secret=manual_entry_key(device) if settings.QUILLMD_MFA_REQUIRED_ALL and not device.confirmed else ''
    return render(request,'mfa_setup.html',{'form':form,'provisioning_uri':device.config_url if not device.confirmed else '', 'device':device,'secret':secret})

def manual_entry_key(device):
    """The device's base32 key — exactly the `secret` in its otpauth URI — in groups of four for typing."""
    from base64 import b32encode
    key=b32encode(device.bin_key).decode().rstrip('=')
    return ' '.join(key[i:i+4] for i in range(0,len(key),4))

def dashboard(request):
    return render(request,'dashboard.html',{'encounters':scoped(Encounter,request.user).select_related('patient','template_version__template').order_by('-created_at')[:30],'templates':scoped(Template,request.user).order_by('-created_at')[:30]})

@require_http_methods(['GET','POST'])
def template_upload(request):
    from documents import inspect_template,DocumentError
    from documents.service import word_engine
    form=UploadForm(request.POST or None,request.FILES or None,user=request.user)
    if request.method=='POST' and form.is_valid():
        relative=None
        try:
            department=form.cleaned_data['department'];membership(request.user,department)
            if Path(form.cleaned_data['file'].name).suffix.lower() not in ['.docx','.pdf']:raise ValidationError('Choose a Word .docx or PDF file.')
            relative=store_upload(form.cleaned_data['file'])
            if private_path(relative).read_bytes()[:8]==OLE_CONTAINER:
                raise ValidationError('This file is password-protected, encrypted, or an old Word .doc file. Save it as an unprotected Word .docx (or a fillable PDF) and upload that.')
            # The contract for NEW inspections comes from settings (QUILLMD_WORD_ENGINE). A PDF and the qualified WM
            # file keep their own paths whatever it says; stored mappings always fill under the contract that made them.
            info=inspect_template(private_path(relative),engine=word_engine())
            contract=v3_mapping.CONTRACT if info.get('contract')==v3_mapping.CONTRACT else ''
            if contract:
                # ⚠️ The engine maps far more than 100 areas, but generation still refuses more than 100 fields, so a
                # larger v3 form is refused here, whole and with the count, rather than trimmed or left unusable.
                answerable=len(v3_mapping.answerable(info['fields']))
                if answerable>v3_mapping.GENERATION_FIELD_LIMIT:raise ValidationError(v3_mapping.too_many_fields(answerable))
            elif len(info['fields'])>100:raise ValidationError('Templates support at most 100 answer fields. Split this template explicitly.')
            with transaction.atomic():
                t=Template.objects.create(department=department,name=form.cleaned_data['name'],format=info['format'],original_name=Path(form.cleaned_data['file'].name).name[:200],original_path=relative,sha256=info['sha256'],warnings=info.get('warnings',[]),created_by=request.user)
                TemplateVersion.objects.create(template=t,number=1,fields=info['fields'],review_requirements=info.get('review_requirements',[]),document_backend=document_backend(info),contract=contract,created_by=request.user)
                audit(request.user,'template.upload',t.pk,department=department,sha256=t.sha256,field_count=len(info['fields']),**({'contract':contract} if contract else {}))
            if contract:messages.info(request,f'QuillMD found {len(info["fields"])} answer areas automatically. Check every one against your form, correct the mapping, and confirm it before creating a document.')
            return redirect('template_detail',pk=t.pk)
        except (ValidationError,DocumentError) as exc:
            if relative:private_path(relative).unlink(missing_ok=True)
            form.add_error(None,error_message(exc))
            # The engine's wording names an adapter the doctor cannot choose. Add what they CAN do,
            # keyed on the refusal's own text, without changing the refusal itself.
            message=error_message(exc)
            hint=next((text for marker,text in UPLOAD_REFUSAL_HINTS if marker in message),None)
            if hint:form.add_error(None,hint)
    return render(request,'template_upload.html',{'form':form})

#: Keyed on the engine's own refusal text, not its broad code: 'unsupported_structure' also covers a
#: spell-check mark or bookmark inside an underlined answer line, which is not a content control.
UPLOAD_REFUSAL_HINTS=(
    ('content controls, text boxes, and tracked changes',
     'This form uses Word features QuillMD does not fill: dropdowns, date pickers or other content controls, text boxes, '
     'fields or tracked changes. The only supported form with dropdowns is the qualified WM IOV file, uploaded exactly as '
     'received. Otherwise use a form with two-column question/answer tables, a label followed by an underlined Tab, or '
     '{{Question}} placeholders.'),
    # One engine sentence covers every cause: the line is in a table cell, or its paragraph holds anything
    # but plain text runs and the Tab. Some of those Word adds invisibly (a spelling mark, a page-break
    # marker when the line starts a page), so the hint does not pretend to list them all.
    ('underlined answer area crosses an unsupported structure',
     'An underlined answer line must be an ordinary paragraph, not inside a table cell, holding only plain label text '
     'and an underlined Tab: no links, bookmarks, comments, symbols, footnotes or line breaks (Shift+Enter). Word can '
     'also add invisible marks, such as spelling marks or a page-break marker when the line starts a page. Retype such '
     'a line as a new paragraph, or use a two-column question/answer table instead.'),
    ('PDF text fields only','Every field in the PDF must be a plain text field: remove checkboxes, radio buttons, dropdowns, '
     'signature fields and buttons.'),
    ('Read-only, password, file-select, comb, and rich-text',
     'Turn off the read-only, password, comb and rich-text options on every PDF field, or use a supported Word (.docx) form.'),
    ('explicit font size','Set every PDF field to a fixed font size (a number, not Auto).'),
    ('Helvetica','Set every PDF field to the standard Helvetica font in its properties, or use a supported Word (.docx) form.'),
    ('Rotated PDF fields','Use unrotated PDF text fields, or a supported Word (.docx) form.'),
    ('PDF actions','Remove every link, attachment, document open action, XFA form data, and field action or format script '
     '(such as Date or Number formats) from the PDF, or use a supported Word (.docx) form.'),
    ('External links and linked resources','Remove every web or email link and linked image from the form, including in '
     'the letterhead, header and footer, then upload it again.'),
    ('non-wrapping text','Remove hidden text and turn off fit-text or do-not-wrap formatting in the form, then upload it again.'),
)
#: An encrypted Office file is an OLE container, not a ZIP, so the engine can only call it unsupported.
OLE_CONTAINER=b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

def statement_guide(version):
    """The qualified form's prewritten statements, readable BEFORE any draft exists.

    A qualified WM IOV finalization needs each kept statement as its own labelled notes line, and its
    wording depends on the answers, so until now a doctor could see it only after generating. This
    lists every statement's exact label and approved wordings from the stored mapping, with each
    answer-dependent part named by its question. It is guidance only: the document page still shows,
    and the review still checks, the exact resolved wording.
    """
    if not version or not version.document_backend:return []
    labels={f['key']:f['label'] for f in version.fields}
    def show(template):
        def token(match):
            name=match.group(1)
            if name=='signer_name':return '[your account name]'
            if name.endswith('reflux_connector'):return ' [is] '
            if name.endswith('treatment_connector'):return ' '
            return '['+labels.get(name,name)+']'
        return ' '.join(re.sub(r'\{([^{}]+)\}',token,template or '').split())
    names=lambda keys:[labels.get(key,key) for key in keys or []]
    return [{'label':row['label'],'variants':[{'label':variant.get('label') or variant.get('id',''),
             'wording':show(variant.get('text_template')),
             'needs':names(variant.get('required_control_keys')),'empty':names(variant.get('empty_control_keys'))}
             for variant in row.get('variants',[])]}
            for row in version.review_requirements if row.get('kind')=='assertion']

@require_http_methods(['GET','POST'])
def template_detail(request,pk):
    t=get_object_or_404(scoped(Template,request.user),pk=pk)
    version=t.versions.order_by('-number').first()
    if v3_mapping.is_v3_version(version):return template_detail_v3(request,t,version)
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
                    return render(request,'template_detail.html',{'template':t,'version':latest,'form':form,'field_rows':field_location.rows(latest.fields),'field_locations':[field_location.describe(f) for f in latest.fields],'statements':statement_guide(latest)},status=409)
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
    return render(request,'template_detail.html',{'template':t,'version':version,'form':form,'field_rows':field_location.rows(version.fields),'field_locations':[field_location.describe(f) for f in version.fields],'statements':statement_guide(version)})

#: At most this many unmapped places are listed at once; the search narrows the rest.
V3_PLACES_SHOWN=300
V3_MAPPING_CHANGED='This mapping changed after you opened it. Nothing was saved; the current mapping is shown below. Compare it with your corrections before saving again.'

def v3_original(t):
    path=private_path(t.original_path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=t.sha256:raise ValidationError('Original integrity check failed.')
    return path

def v3_outline(t):
    from documents import outline_template
    return outline_template(v3_original(t))['slots']

def v3_page(request,t,version,*,status=200,error='',posted=None,outline=None):
    """The contract v3 mapping review: every field in document order, the places a field could still be added to,
    the corrections that made this version, and the clinician's confirmation."""
    from documents import DocumentError
    query=' '.join(request.GET.get('find','').split())[:120]
    outline_error=''
    if outline is None:
        try:outline=v3_outline(t)
        except (ValidationError,DocumentError,OSError) as exc:outline=[];outline_error=error_message(exc) if not isinstance(exc,OSError) else 'The original is unavailable.'
    places=v3_mapping.open_places(outline,version.fields,query)
    box_keys={row['slot']:row['box_keys'] for row in outline if row.get('box_keys')}
    posted=posted or {}
    # ⚠️ Repeated questions are counted with generation's own normalizer, over the fields generation reads: two of
    # them sharing a label are never filled from the notes (each is held), so the page names them for renaming.
    from .generation import question_key
    counts={}
    for f in version.fields:
        if f.get('kind') not in v3_mapping.NEVER_GENERATED:counts[question_key(f['label'])]=counts.get(question_key(f['label']),0)+1
    rows=[{'number':n,'key':f['key'],'field':f,'label':posted.get('label_'+f['key'],f['label']),
           'kind':f.get('kind'),'chosen_kind':posted.get('kind_'+f['key'],f.get('kind')),
           'kind_name':v3_mapping.KIND_NAMES.get(f.get('kind'),f.get('kind')),
           'kind_editable':f.get('kind') in v3_mapping.TEXT_KINDS,'options':f.get('options') or [],
           'location':field_location.describe(f,box_keys=box_keys),'context':f.get('context') or '',
           'origin':{'manual':'Manual','model_assisted':'Model proposal'}.get(f.get('origin'),'Automatic'),'max_chars':f.get('max_chars'),
           'remove':posted.get('remove_'+f['key'])=='on',
           'duplicate':f.get('kind') not in v3_mapping.NEVER_GENERATED and counts.get(question_key(f['label']),0)>1}
          for n,f in enumerate(version.fields,1)]
    can_confirm=Membership.objects.filter(user=request.user,department=t.department,active=True,role__in=['owner','clinician']).exists()
    return render(request,'template_detail.html',{'template':t,'version':version,'v3':True,'v3_rows':rows,'v3_error':error,
        'places':places[:V3_PLACES_SHOWN],'places_hidden':max(0,len(places)-V3_PLACES_SHOWN),'places_total':len(places),
        'find':query,'outline_error':outline_error,'posted_slot':posted.get('slot',''),'posted_add_label':posted.get('label',''),
        'posted_add_kind':posted.get('kind',''),'text_kinds':[(k,v3_mapping.KIND_NAMES[k]) for k in v3_mapping.TEXT_KINDS],
        'manual_kinds':[(k,v3_mapping.KIND_NAMES[k]) for k in v3_mapping.MANUAL_KINDS],'can_confirm':can_confirm,
        'answerable':len(v3_mapping.answerable(version.fields)),'field_limit':v3_mapping.GENERATION_FIELD_LIMIT,
        'corrections':version.corrections,'statements':[],
        'mapping_assistance_enabled':getattr(settings,'QUILLMD_MAPPING_ASSISTANCE',False)},status=status)

def template_detail_v3(request,t,version):
    from documents import DocumentError
    if request.method!='POST':return v3_page(request,t,version)
    action=request.POST.get('action','')
    handler={'v3_save':v3_save_corrections,'v3_add':v3_add_field,'v3_confirm':v3_confirm}.get(action)
    if handler is None:
        return v3_page(request,t,version,status=400,error='This mapping is reviewed field by field on this page. Nothing was saved.')
    try:
        return handler(request,t)
    except (ValidationError,DocumentError) as exc:
        latest=t.versions.order_by('-number').first()
        return v3_page(request,t,latest,status=400,error=error_message(exc),posted=request.POST)

def v3_new_version(request,t,latest,fields,*,removed=(),added=(),kind_changed=None,renamed=()):
    """A new immutable mapping version, with the corrections that made it recorded beside the fields. Added fields
    keep origin 'manual'; the new version needs its own confirmation."""
    kind_changed=kind_changed or {}
    corrections={'base_version':latest.number,'removed':list(removed),'added':list(added),'kind_changed':kind_changed,'renamed':list(renamed)}
    version=TemplateVersion.objects.create(template=t,number=latest.number+1,fields=fields,review_requirements=latest.review_requirements,
                                           document_backend=latest.document_backend,contract=latest.contract,corrections=corrections,created_by=request.user,
                                           assistance={**latest.assistance,'assisted':True} if latest.assistance else {})
    audit(request.user,'template.mapping_version',version.pk,department=t.department,number=version.number,contract=version.contract,
          removed=[row['key'] for row in removed],added=list(added),kind_changed=kind_changed,renamed=[row['key'] for row in renamed])
    return version

def v3_save_corrections(request,t):
    """Rename, change a text-like kind, or remove fields that are not answers; one new version, corrections recorded."""
    from .tab_review import signature_label
    membership(request.user,t.department,roles=['owner','clinician','manager'])
    with transaction.atomic():
        Template.objects.select_for_update().get(pk=t.pk)
        latest=t.versions.order_by('-number').first()
        if request.POST.get('mapping_version')!=str(latest.pk):
            return v3_page(request,t,latest,status=409,error=V3_MAPPING_CHANGED,posted=request.POST)
        fields=[];removed=[];renamed=[];kind_changed={}
        for number,f in enumerate(latest.fields,1):
            key=f['key']
            if request.POST.get('remove_'+key)=='on':
                removed.append({'key':key,'label':f['label'],'kind':f.get('kind'),'origin':f.get('origin','automatic')});continue
            label=str(request.POST.get('label_'+key,f['label'])).strip()
            if not label or len(label)>300 or '\n' in label:raise ValidationError(f'Give question {number} a one-line label of 1 to 300 characters.')
            kind=request.POST.get('kind_'+key,f.get('kind'))
            if kind!=f.get('kind'):
                if f.get('kind') not in v3_mapping.TEXT_KINDS or kind not in v3_mapping.TEXT_KINDS:
                    raise ValidationError(f'"{f["label"]}" keeps its kind ({v3_mapping.KIND_NAMES.get(f.get("kind"),f.get("kind"))}): only text, long text, date and time can be changed into one another. Nothing was saved.')
                kind_changed[key]=[f.get('kind'),kind]
            if label!=f['label']:
                # ⚠️ The same protection as every other mapping: the identity check reads this label.
                if signature_label(f['label']) and not signature_label(label):
                    raise ValidationError('A signature question keeps a signature label, because the identity check reads it: '+f['label']+'. Rename the other questions and leave this one as the form words it.')
                renamed.append({'key':key,'from':f['label'],'to':label})
            fields.append({**f,'label':label,'kind':kind})
        if not (removed or renamed or kind_changed):
            messages.info(request,'Nothing changed, so no new mapping version was saved.')
            return redirect('template_detail',pk=t.pk)
        version=v3_new_version(request,t,latest,fields,removed=removed,kind_changed=kind_changed,renamed=renamed)
    messages.success(request,f'Mapping version {version.number} saved with your corrections. Confirm it before creating documents; existing documents keep their original version.')
    return redirect('template_detail',pk=t.pk)

def v3_add_field(request,t):
    """A place the engine missed, chosen from the form's outline, located by the engine and recorded as manual."""
    from documents import locate_fields
    membership(request.user,t.department,roles=['owner','clinician','manager'])
    slot=request.POST.get('slot','');kind=request.POST.get('kind','');label=request.POST.get('label','').strip()
    if kind not in v3_mapping.MANUAL_KINDS:raise ValidationError('Choose what kind of answer the added field takes.')
    if not label or len(label)>300 or '\n' in label:raise ValidationError('Give the added field a one-line label of 1 to 300 characters.')
    if not slot:raise ValidationError('Choose the place on the form where the missed answer goes.')
    latest=t.versions.order_by('-number').first()
    if request.POST.get('mapping_version')!=str(latest.pk):
        return v3_page(request,t,latest,status=409,error=V3_MAPPING_CHANGED,posted=request.POST)
    outline=v3_outline(t)
    place=next((row for row in outline if row['slot']==slot),None)
    if place is None:raise ValidationError('That place is not in this form. Choose one from the list.')
    if v3_mapping.is_mapped(slot,v3_mapping.mapped_slots(latest.fields)):
        raise ValidationError('That place already belongs to a field. Correct that field instead of adding another.')
    target={'slot':slot,'kind':kind,'label':label}
    if kind=='checkbox' or place.get('kind')=='glyphs':
        # ⚠️ The box the clinician named, for ANY place that holds printed boxes; the engine refuses a number beyond
        # the boxes the place actually holds (a paragraph place used to take box 1 whatever was asked).
        try:box=int(request.POST.get('box') or 1)
        except ValueError:box=0
        if box<1:raise ValidationError('Give the number of the printed box, counting from 1.')
        target['glyph']=box-1
    field=locate_fields(v3_original(t),[target])['fields'][0]
    if field.get('kind')=='choice' and not field.get('options'):
        raise ValidationError('A field with printed options needs a Word dropdown or a legacy dropdown field as its place. Choose the dropdown, or add this answer as text.')
    if any(f['key']==field['key'] for f in latest.fields):raise ValidationError('That place already belongs to a field with this label.')
    with transaction.atomic():
        Template.objects.select_for_update().get(pk=t.pk)
        if t.versions.order_by('-number').first().pk!=latest.pk:
            return v3_page(request,t,t.versions.order_by('-number').first(),status=409,error=V3_MAPPING_CHANGED,posted=request.POST)
        fields=v3_mapping.insert_in_document_order(latest.fields,[field],outline)
        answerable=len(v3_mapping.answerable(fields))
        if answerable>v3_mapping.GENERATION_FIELD_LIMIT:
            raise ValidationError(f'Adding this field would give the form {answerable} answer areas; QuillMD can generate answers for at most {v3_mapping.GENERATION_FIELD_LIMIT} per form today. Nothing was saved.')
        version=v3_new_version(request,t,latest,fields,added=[field['key']])
    messages.success(request,f'Added "{field["label"]}" ({v3_mapping.KIND_NAMES.get(field["kind"],field["kind"])}) as a manual field in mapping version {version.number}. Confirm the mapping before creating documents.')
    return redirect('template_detail',pk=t.pk)

def v3_confirm(request,t):
    """The clinician's statement that every field was checked against the form, recorded with who and when."""
    membership(request.user,t.department,roles=['owner','clinician'])
    if request.POST.get('checked_every_field')!='on':raise ValidationError('Tick "I checked every field against the form" to confirm this mapping.')
    with transaction.atomic():
        Template.objects.select_for_update().get(pk=t.pk)
        latest=t.versions.order_by('-number').first()
        if request.POST.get('mapping_version')!=str(latest.pk):
            return v3_page(request,t,latest,status=409,error=V3_MAPPING_CHANGED)
        if latest.assistance.get('unresolved'):raise ValidationError('Resolve every mapping-assistance area before confirming this version.')
        if not latest.fields:raise ValidationError('This mapping has no fields. Add the form\'s answer areas before confirming it.')
        # ⚠️ A box that does not exist can never be confirmed (it would only refuse at export, after the review).
        missing=v3_mapping.missing_boxes(latest.fields,v3_outline(t))
        if missing:raise ValidationError('These fields point at a printed box the form does not have: '+field_list(missing)+' Remove each one and add it again with the right box number.')
        off_box=v3_mapping.checkboxes_off_box(latest.fields)
        if off_box:raise ValidationError('These checkbox fields point at a place that is not a box: '+field_list(off_box)+' Remove each one and add it again on its printed box or checkbox control, or as text.')
        if latest.confirmed:
            messages.info(request,'This mapping version was already confirmed.')
            return redirect('template_detail',pk=t.pk)
        MappingConfirmation.objects.create(version=latest,confirmed_by=request.user)
        audit(request.user,'template.mapping_confirmed',latest.pk,department=t.department,number=latest.number,field_count=len(latest.fields))
    messages.success(request,f'Mapping version {latest.number} confirmed. You can now create documents with this form.')
    return redirect('template_detail',pk=t.pk)

def template_original(request,pk):
    t=get_object_or_404(scoped(Template,request.user),pk=pk)
    path=private_path(t.original_path)
    if hashlib.sha256(path.read_bytes()).hexdigest()!=t.sha256:raise ValidationError('Original integrity check failed.')
    audit(request.user,'template.download',t.pk,department=t.department)
    return FileResponse(path.open('rb'),as_attachment=True,filename=t.original_name)

@require_http_methods(['GET','POST'])
def encounter_new(request):
    form=EncounterForm(request.POST or None,user=request.user)
    # "Use this form" links carry ?template=<template id>. Preselect that form's CURRENT mapping
    # version, taken from the form's own scoped queryset so an out-of-scope or malformed id selects
    # nothing. Without this the doctor landed on an empty list of every mapping version of every
    # form, superseded versions included, and had to find the form they had just chosen again.
    if request.method=='GET' and request.GET.get('template'):
        try:chosen=UUID(request.GET['template'])
        except (ValueError,TypeError):chosen=None
        latest=chosen and form.fields['template_version'].queryset.filter(template_id=chosen).order_by('-number').first()
        if latest:form.initial['template_version']=latest.pk
    if request.method=='POST' and form.is_valid():
        data=form.cleaned_data
        with transaction.atomic():
            membership(request.user,data['patient'].department)
            e=Encounter(department=data['patient'].department,patient=data['patient'],template_version=data['template_version'],created_by=request.user,notes=data['notes'],service_date=data['service_date']);e.full_clean(exclude=['notes','answers','finalized_at','finalized_by','export_path','export_sha256']);e.save()
            audit(request.user,'encounter.create',e.pk,department=e.department)
        return redirect('encounter_detail',pk=e.pk)
    return render(request,'encounter_form.html',{'form':form,'has_patients':form.fields['patient'].queryset.exists()})

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
    is_v3=v3_mapping.is_v3_version(e.template_version)
    rows=[{**f,**e.answers.get(f['key'],{'text':'','status':'missing','evidence':[],'reviewed':False})} for f in e.template_version.fields]
    # ⚠️ A CLINICAL DECISION IS ATTRIBUTED TO THE PERSON WHO MADE IT, NOT TO WHOEVER IS READING.
    # The page told every reader "You accepted this as your answer" — so a second clinician opening
    # the encounter was informed, about somebody else's decision, that they had made it. That is
    # the same misattribution as a finalized record denying an acceptance, pointed the other way.
    # `accept_code`, in this same template, has named its accepter all along.
    accepters={str(pk):email for pk,email in User.objects.filter(
        pk__in={row['accepted_by'] for row in rows if row.get('accepted_by')}).values_list('pk','email')}
    from .tab_review import clinician_identity
    deciders={str(pk):email for pk,email in User.objects.filter(
        pk__in={(row.get('blank_decision') or {}).get('by') for row in rows} - {None}).values_list('pk','email')}
    if e.status!='finalized' and e.answers:
        # ⚠️ THE PAGE SHOWS WHAT FINALIZATION WILL REFUSE, BY THE SAME READER. A draft from an earlier release
        # can hold a governed answer as `supported` or as a one-click offer, accepted or not; each is shown held,
        # with every line that governs it. A FINALIZED record is never re-described: it shows what was offered.
        from .generation import as_currently_governed,governance_for
        governance=governance_for(e.notes,e.template_version.fields,[row['label'] for row in e.template_version.review_requirements])
        rows=[as_currently_governed(governance,e.notes,row,is_wm) for row in rows]
    if is_v3:
        # ⚠️ A QUESTION LABEL THE FORM REPEATS IS SHOWN WITH ITS CONTEXT (counted with generation's own normalizer):
        # two questions reading "Effusion" are told apart only by where they sit on the form.
        from .generation import question_key
        label_counts={}
        for f in e.template_version.fields:label_counts[question_key(f.get('label'))]=label_counts.get(question_key(f.get('label')),0)+1
    for row in rows:
        row['accepted_by_email']=accepters.get(str(row.get('accepted_by') or ''),'')
        row['accepted_by_me']=str(row.get('accepted_by') or '')==str(request.user.pk)
        # "Leave blank — reviewed" is offered on ordinary forms only: a qualified Word form keeps
        # its own "No answer documented" choice, and a signature keeps the identity rules.
        row['blank_eligible']=not e.template_version.document_backend and not clinician_identity(row)
        row['left_blank']=row.get('status')=='left_blank'
        row['blank_by_email']=deciders.get(str((row.get('blank_decision') or {}).get('by') or ''),'')
        # ⚠️ "I REVIEWED THIS ANSWER" IS THE READER'S OWN STATEMENT, SO IT IS NEVER PRE-TICKED FROM
        # SOMEBODY ELSE'S REVIEW. Rendering the stored flag let a second clinician's plain Save
        # re-post every box and re-stamp reviewed_by to themselves — the signature row included,
        # which is exactly what validate_identity trusts. The qualified Word branch below already
        # binds the box to its reviewer; ordinary forms now do too. The stored state stays visible.
        answer=e.answers.get(row['key'],{})
        row['stored_reviewed']=answer.get('reviewed') is True
        row['reviewed']=row['stored_reviewed'] and answer.get('reviewed_by')==str(request.user.pk)
        row['reviewed_by_other']=row['stored_reviewed'] and not row['reviewed']
        row['identity']=clinician_identity(row)
        if is_v3:
            # How the page asks for each kind; the stored answer stays its text form (core/v3_mapping.py).
            kind=row.get('kind')
            row['v3_input']=v3_mapping.input_for(row)
            row['chosen']=[line for line in (row.get('text') or '').split('\n') if line] if kind=='multi_choice' else []
            row['columns_hint']=' | '.join(v3_mapping.columns(row)) if kind=='table_rows' else ''
            row['unsupported_choice']=bool(kind=='choice' and row.get('text') and row['text'] not in (row.get('options') or []))
            if kind in v3_mapping.SIGNING_KINDS:row['blank_eligible']=False
            # What the export does with this answer, in the page's words (the export sets every box of an answered
            # option field, unticks a reviewed checkbox left unticked, and keeps an unanswered choice as printed).
            row['v3_note']=v3_mapping.review_note(row)
            row['blank_note']=v3_mapping.blank_note(row)
            row['v3_final']=v3_mapping.finalized_note(row,row)
            row['v3_context']=(row.get('context') or '') if label_counts.get(question_key(row.get('label')),0)>1 else ''
    requirements=[];review_error='';assessment=None;resolved_ok=False;wm_conflicts=[]
    if is_wm:
        decisions=e.template_review.get('decisions',{})
        try:
            requirements=wm_resolve(e,request.user)
            resolved_ok=True
            # ⚠️ A FINALIZED RECORD IS NOT RE-REVIEWED BY WHOEVER VIEWS IT: its receipt is the review. Evaluated as the
            # reader's own, a second clinician was told the record's review was incomplete (the signer's identity is not
            # theirs) and was shown the template's original wordings. (Ported from feat/wm-narrative.)
            if can_finalize and e.status!='finalized':
                assessment=wm_review.evaluate_review(e,request.user,decisions,resolved_requirements=requirements)
        except (ValidationError,DocumentError) as exc:
            review_error=error_message(exc)
            wm_conflicts=getattr(exc,'rows',[])
            requirements=e.template_version.review_requirements
        for row in rows:
            answer=e.answers.get(row['key'],{})
            row['reviewed']=(answer.get('reviewed') is True and answer.get('reviewed_by')==str(request.user.pk)
                             and answer.get('review_revision')==e.revision)
            row['unsupported_choice']=bool(row.get('kind')=='choice' and row.get('text') and row['text'] not in row.get('options',[]))
            row['source_quote']=answer.get('review_quote','\n'.join(item['quote'] for item in row.get('evidence',[])))
            reasons=assessment['answers'][row['key']]['blockers'] if assessment else []
            if assessment:row['status']=assessment['answers'][row['key']]['status']
            # A held answer is a decision the page shows beside its governing lines: its badge says so, and "conflicting
            # values" (the stored record's status, or the empty held box) is not its reason (sixteenth pass).
            if e.status!='finalized' and row.get('held_candidate') and not row.get('text'):
                row['status']='conflict'; reasons=[reason for reason in reasons if reason!='conflicting_source']
            row['review_errors']=[WM_BLOCKERS.get(reason,'Clinical review is incomplete.') for reason in reasons]
            row['review_errors']+=[conflict['explanation'] for conflict in wm_conflicts if row['key'] in conflict['answer_keys']]
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
            row['review_errors']+=[conflict['explanation'] for conflict in wm_conflicts if row['key'] in conflict['statement_keys']]
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
                # An empty result (silence, a muted microphone) is a processed, charged request with
                # nothing to add; say so rather than leave an unexplained empty required box.
                transcript_reviews.append({'job':job,'raw':raw,'text':transcript,'empty':not (raw or '').strip() and not (transcript or '').strip()})
            except (ValidationError,OSError,ValueError):
                job.display_error='The retained transcript could not be verified. Contact an administrator; do not resubmit a paid recording.'
    return render(request,'encounter_detail.html',{'notes_save_clears':notes_save_clears(e),'encounter':e,'pending_job':any(job.state in ['queued','running','reconciliation'] for job in jobs),'transcript_reviews':transcript_reviews,'answer_rows':rows,'wm_template':is_wm,'manual_entry':is_wm or is_v3 or bool(e.template_version.fields) and all('tab_form' in f.get('locator',{}) for f in e.template_version.fields),'v3_template':is_v3,'wm_requirements':requirements,'wm_review_error':review_error,'wm_conflicts':wm_conflicts,'generation_max_charge':maximum_charge,'usage_quote':signing.dumps({'user':str(request.user.pk),'encounter':str(e.pk),'revision':e.revision,'config':configuration()},salt='usage-quote'),'voice_max_charge':voice_standard()[0],'voice_fits':voice_standard()[1],'voice_notes_full':notes_full(e.notes),'codes':codes,'jobs':jobs,'voice_form':VoiceForm(),'can_finalize':can_finalize,'prior_generations':prior_generations,'prior_transcriptions':prior_transcriptions,
        # The exact name validate_identity compares a signature with, so the page can say what to type.
        'signer_name':' '.join((request.user.get_full_name() or request.user.email).split())})

def clinician_decided(e):
    """Whether the saved draft carries a clinician's review state, which a generation would replace wholesale.
    (An acceptance also marks its answer `edited`; it is named for itself so no change to statuses can open this.)"""
    return (any(isinstance(a,dict) and (a.get('reviewed') or a.get('accepted_suggestion') or a.get('status') in ('edited','left_blank'))
                for a in (e.answers or {}).values())
            or bool((e.template_review or {}).get('decisions')))

def same_text(posted,stored):
    """Whether posted notes are the stored notes as a browser returns them untouched: it posts a textarea's line breaks as
    CRLF, and the HTML parser drops the one line break that directly follows <textarea>. The page now emits one there (as
    Django's Textarea widget does), so a stored leading break survives; a page rendered before that lost it, so exactly
    one leading line break (LF, CRLF or CR) missing from the post is ignored."""
    posted,stored=(text.replace('\r\n','\n').replace('\r','\n') for text in (posted,stored))
    return posted==stored or (stored.startswith('\n') and posted==stored[1:])

def notes_save_clears(e):
    """What a changed notes save would clear, as the page's warning names it ('' when nothing): the same parts, from the
    same counts, that the save audits and then states — so the warning names only what would be cleared (refutation round
    4, R4-7), and it and the saved message cannot disagree."""
    return listed(cleared_parts(review_state_counts(e)))

ANSWER_STATES=('answers_accepted_suggestion','answers_left_blank','answers_edited_not_accepted','answers_reviewed_unedited',
               'answers_unreviewed_unedited')

def review_state_counts(e,codes=True):
    """What clearing this draft discards, as counts only (never clinical text), for its audit row.

    An answer is counted only when it carries text or a decision — a review tick, an acceptance, "Leave blank — reviewed"
    or an edit (to nothing, too). An empty field nobody decided (a `missing` field, or a conflict nobody resolved) holds
    no answer to clear: counting it made notes with one supported answer and one empty field say "2 answers" (refutation
    round 4, R4-3). Each counted answer is counted once, in the first of ANSWER_STATES that fits — an accepted suggestion
    (which is also `edited` and may be reviewed), left blank, edited and not an accepted suggestion, reviewed and
    unedited, or neither reviewed nor edited (so, since R4-3, carrying text) — so those states are disjoint and sum to
    the answers counted (refutation round 2, R2-4). Across them, and NOT a further state to add to them,
    `answers_with_clinician_review` counts the answers that carried a review tick, which only an owner or clinician can
    set: two edited answers a clinician reviewed no longer audit exactly as two edits nobody reviewed (refutation round 3,
    F3). Each statement decision is counted once: reviewed, or recorded and unreviewed — which includes a wording saved
    exactly as the form rendered it, since a save records every statement's wording and the record cannot tell a
    deliberate choice of the default from none, so the key does not say "chosen" (refutation round 3, F4). Accepted codes
    only."""
    from .generation import is_empty
    counts=dict.fromkeys(ANSWER_STATES,0);counts['answers_with_clinician_review']=0
    for a in (e.answers or {}).values():
        # (a malformed entry from an earlier release is text if it is anything, so the save's count never hides it)
        a=a if isinstance(a,dict) else {'text':str(a) if a else ''}
        if a.get('accepted_suggestion'):state='answers_accepted_suggestion'
        elif a.get('status')=='left_blank':state='answers_left_blank'
        elif a.get('status')=='edited':state='answers_edited_not_accepted'
        elif a.get('reviewed'):state='answers_reviewed_unedited'
        elif not is_empty(a.get('text')):state='answers_unreviewed_unedited'
        else:continue                                     # (an empty field nobody decided: nothing to clear)
        counts[state]+=1;counts['answers_with_clinician_review']+=int(bool(a.get('reviewed')))
    decisions=[d if isinstance(d,dict) else {} for d in ((e.template_review or {}).get('decisions') or {}).values()]
    counts.update(statements_reviewed=sum(1 for d in decisions if d.get('reviewed')),
                  statements_recorded_unreviewed=sum(1 for d in decisions if not d.get('reviewed')),
                  codes_accepted=CodeSuggestion.objects.filter(encounter=e,accepted_by__isnull=False).count() if codes else 0)
    return counts

def cleared_parts(counts):
    """What a changed notes save clears, as phrases read from its audited counts: each part is named only when its count
    is not zero, so no sentence built from them can claim what the audit row does not record (refutation round 3, F2).
    Within the answer draft, the decisions a clinician made — accepted suggestions and decisions to leave blank — are named
    with the answers they are part of, beside the reviewed count that spans them: an acceptance made without the review
    tick vanished from "(2 answers, 1 reviewed by a clinician)" while the audit recorded it (refutation round 4, R4-4)."""
    def counted(number,noun,plural=None):return f'{number} '+(noun if number==1 else plural or noun+'s')
    def reviewed(total,number):return (f'{number} reviewed by a clinician' if number else 'none reviewed' if total>1 else 'not reviewed')
    answers=sum(counts[state] for state in ANSWER_STATES)
    review=reviewed(answers,counts['answers_with_clinician_review'])
    decisions=[(number,counted(number,noun,plural)) for number,noun,plural in (
        (counts['answers_accepted_suggestion'],'accepted suggestion',None),
        (counts['answers_left_blank'],'decision to leave blank','decisions to leave blank')) if number]
    named=' and '.join(text for _,text in decisions)
    if not decisions:draft=f'{counted(answers,"answer")}, {review}'
    elif sum(number for number,_ in decisions)==answers:draft=f'{counted(answers,"answer")}: {named}; {review}'
    else:draft=f'{counted(answers,"answer")}, including {named}; {review}'
    statements=counts['statements_reviewed']+counts['statements_recorded_unreviewed']
    parts=([f'the answer draft ({draft})'] if answers else [])
    parts+=([f'{counted(statements,"saved prewritten statement wording")} ({reviewed(statements,counts["statements_reviewed"])})'] if statements else [])
    parts+=([counted(counts['codes_accepted'],'accepted code')] if counts['codes_accepted'] else [])
    return parts

def listed(parts):
    return ', '.join(parts[:-1])+' and '+parts[-1] if len(parts)>1 else ''.join(parts)

def cleared_sentence(counts):
    """What a changed notes save cleared, in words, from its audited counts (see `cleared_parts`)."""
    parts=cleared_parts(counts)
    return 'Cleared, and recorded under your name: '+listed(parts)+'. ' if parts else ''

@require_POST
@transaction.atomic
def clear_review(request,pk):
    """"Clear answers and review to generate again": a clinician's explicit, confirmed and audited reset of the answer
    draft and its review. The notes, and the accepted codes that rest on them, are kept."""
    e=get_object_or_404(scoped(Encounter,request.user).select_for_update(),pk=pk)
    if e.status=='finalized':return document_refusal(request,e,'Finalized documents are immutable.',409)
    membership(request.user,e.department,roles=['owner','clinician'])
    if Job.objects.filter(encounter=e,state__in=['queued','running','reconciliation']).exists():
        return document_refusal(request,e,'Wait until the pending job is resolved. Nothing was cleared.',409)
    if request.POST.get('revision')!=str(e.revision):
        return document_refusal(request,e,'This document changed after you opened it, in another window or by a colleague. Reopen it before clearing. Nothing was cleared.',409)
    if request.POST.get('confirm_clear')!='on':
        return document_refusal(request,e,'Tick the confirmation to clear the answers and review. Nothing was cleared.',400)
    cleared=review_state_counts(e,codes=False)
    e.answers={};e.revision+=1;e.status='draft';wm_review.invalidate_review(e)
    e.save(update_fields=['answers','revision','status','template_review'])
    audit(request.user,'encounter.review_cleared',e.pk,department=e.department,revision=e.revision,cleared=cleared)
    messages.success(request,'Answers and review cleared. The notes and accepted codes are kept. Generate a new draft when ready.')
    return redirect('encounter_detail',pk=pk)

@require_POST
def generate_view(request,pk):
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    try:
        if not rate_limit('generate:'+str(request.user.pk),limit=30):raise ValidationError('Generation rate limit reached.')
        # (a finalized record says so first: the advice below names an action it refuses — refutation R2)
        if e.status=='finalized':raise ValidationError('Finalized documents are immutable.')
        if 'revision' in request.POST and request.POST['revision']!=str(e.revision):raise ValidationError('Source notes changed. Reload before generating answers.')
        # ⚠️ ADOPTING A GENERATION REPLACES EVERY ANSWER AND THE WHOLE REVIEW (`jobs.py`). The page offers it only
        # before any answer exists; a crafted POST at the current revision queued a billed job that erased reviewed,
        # accepted, edited and left-blank answers and statement decisions. A save renumbers the revision, so a request
        # raced past this check is refused by `enqueue`'s locked revision check. (Ported from feat/wm-narrative.)
        if clinician_decided(e):
            raise ValidationError("These answers include a clinician's review or decisions, and a new draft would replace them. "
                                  'Nothing was sent or charged. To generate again, a clinician can use "Clear answers and '
                                  'review to generate again" under the notes: it asks for confirmation and is recorded.')
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

def document_refusal(request,encounter,message,status):
    """A refused document edit. Every caller returns BEFORE any write, so nothing was saved; the page
    says so and links back to the document instead of leaving the doctor on a bare text response."""
    return render(request,'document_refusal.html',{'encounter':encounter,'message':message},status=status)

@require_POST
@transaction.atomic
def save_answers(request,pk):
    from documents import DocumentError
    from .tab_review import clinician_identity
    e=get_object_or_404(scoped(Encounter,request.user).select_for_update(),pk=pk)
    if e.status=='finalized':return document_refusal(request,e,'Finalized documents are immutable.',409)
    if Job.objects.filter(encounter=e,state__in=['queued','running','reconciliation']).exists():return document_refusal(request,e,'Wait until the pending job is resolved.',409)
    if request.POST.get('revision')!=str(e.revision):return document_refusal(request,e,'This document changed after you opened it, in another window or by a colleague. Reopen it to see the current version before editing.',409)
    is_wm=bool(e.template_version.document_backend)
    is_v3=v3_mapping.is_v3_version(e.template_version)
    labels=[row['label'] for row in e.template_version.fields+e.template_version.review_requirements]
    if is_wm and any(request.POST.get('claim_reviewed_'+row['key'])=='on' for row in e.template_version.review_requirements):
        membership(request.user,e.department,roles=['owner','clinician'])
    answers={};review_errors=[];newly_accepted=[];withdrawn=[];newly_blank=[];withdrawn_blank=[];target_revision=e.revision+1
    previous_answers=dict(e.answers)
    # ⚠️ ONCE PER SAVE, NOT PER FIELD: this runs under the row lock, and a 100-field save recomputed it per offer.
    from .generation import governance_for,governed_supported,held_for_decision,is_empty,looks_the_same,offer_context
    governance=governance_for(e.notes,e.template_version.fields,[row['label'] for row in e.template_version.review_requirements])
    for field in e.template_version.fields:
        key=field['key'];previous=e.answers.get(key,{'text':'','evidence':[],'status':'missing'})
        held_shown=request.POST.get('held_shown_'+key)=='1'
        supported_context=governed_supported(governance,e.notes,previous,field['label'])
        governed_offer=offer_context(governance,e.notes,previous,field['label']) is not None
        # A draft from an earlier release holding a governed answer as `supported` is saved as the page showed it —
        # held — so the clinician's answer is their decision even when it repeats the candidate's words. ⚠️ ONLY WHEN
        # THIS PAGE SHOWED IT HELD (`held_shown_`): a page opened before this release posts the pre-filled text back,
        # and taking that as a decision is the defect's own gesture. Without the marker, text that LOOKS THE SAME
        # stays `supported` (finalization refuses it); text that visibly differs is the clinician's edit, saved with
        # the candidate and its governing lines kept beside it, so the next page shows what governs it (tenth pass:
        # the edit was saved bare, and the heading was never shown again).
        held_draft=(held_for_decision(previous,[previous.get('text','')],previous['evidence'],supported_context,is_wm,prefilled=True)
                    if supported_context is not None else None)
        if held_shown and held_draft is not None:
            previous=held_draft
        # Browsers post a textarea's line breaks as CRLF. Stored as posted, a multi-line answer was
        # refused by every fillable PDF at finalize (a carriage return is not printable), exported
        # to a Word table cell as two breaks per line, and compared unequal to its own unchanged text.
        value=request.POST.get('answer_'+key,'').replace('\r\n','\n').replace('\r','\n')
        if is_v3 and field.get('kind')=='multi_choice':
            # Several printed options arrive as several ticked boxes; the text form is one option per line.
            value='\n'.join(request.POST.getlist('answer_'+key)).replace('\r\n','\n').replace('\r','\n')
        # Refused before it is read character by character (seventh pass: a 20 MB value held the row lock ~10 s).
        if len(value)>20000:return document_refusal(request,e,'Answer too long; nothing was truncated or saved.',400)
        # ⚠️ WHITESPACE IS NOT AN ANSWER. A space counted as an edit, so one keystroke could clear a
        # generated conflict — or erase a clinician's "Leave blank — reviewed" decision without the
        # authority check or audit that a real withdrawal carries. An answer is its text or nothing.
        # Nor are invisible characters or a blank braille cell: they export as a visually empty cell (fifth pass).
        if not value.strip() or is_empty(value):value=''
        # ⚠️ AND WHAT NOBODY CAN SEE IS NOT A DECISION EITHER: a page from before this release re-posting the pre-filled
        # governed text (or an accepted governed suggestion) with a stray space or invisible character keeps what it
        # re-posts, which finalization refuses.
        if not held_shown and held_draft is not None:
            if looks_the_same(value,previous.get('text','')):
                value=previous.get('text','')
            else:
                previous=held_draft
        if (not held_shown and governed_offer and previous.get('accepted_suggestion')
                and looks_the_same(value,previous.get('suggestion'))):
            value=str(previous.get('suggestion') or '')
        # "Leave blank — reviewed": the clinician's explicit decision that no answer belongs here.
        # It is a DECISION, kept apart from an untouched empty field (`missing`), a generated
        # `conflict` and an accepted suggestion, so it may not be combined with either of them.
        blank=request.POST.get('blank_'+key)=='on'
        prior_blank=previous.get('status')=='left_blank'
        # On a field already left blank the box arrives ticked as rendered; typing an answer or
        # accepting the suggestion there is the withdrawal the page describes, not a contradiction.
        if blank and prior_blank and (value.strip() or request.POST.get('accept_'+key)=='on'):
            blank=False
        if blank:
            if is_wm or clinician_identity(field):
                return document_refusal(request,e,'"'+field['label']+'" cannot be marked "Leave blank — reviewed". Nothing was saved.',400)
            if value.strip() or request.POST.get('accept_'+key)=='on':
                return document_refusal(request,e,'Choose one decision for "'+field['label']+'": your own answer, the offered suggestion, or leave it blank. Nothing was saved.',400)
            membership(request.user,e.department,roles=['owner','clinician'])
        # ⚠️ A SUGGESTION BECOMES AN ANSWER ONLY BY AN EXPLICIT ACT, NEVER BY SAVING.
        # The textarea is deliberately NOT prefilled with the suggestion: if it were, an
        # ordinary save would accept it silently, and so would a reopen, an API read or an
        # export. Accepting takes its own checkbox, and typed text wins over it.
        suggestion=str(previous.get('suggestion') or '')
        # An accepted offer the notes now show is governed is rendered HELD, with an empty box: an ordinary save
        # there keeps the recorded act (finalization still refuses it), and only a typed answer or "Leave blank —
        # reviewed" replaces it. Typing the suggestion's own words on that page is a new decision, not the old act.
        governed_acceptance=held_shown and governed_offer and bool(previous.get('accepted_suggestion'))
        kept=False
        if governed_acceptance and not value.strip() and not blank:
            value=str(previous.get('text') or '');kept=True
        # ⚠️ AN ACCEPTANCE IS A FACT ABOUT A DECISION ALREADY MADE, SO IT IS CARRIED FORWARD,
        # NOT RECOMPUTED FROM THE POST. Recomputing it withdrew every acceptance on the very next
        # save: once accepted, the page renders the accepted branch, which has NO checkbox to
        # re-post, so an ordinary save of any other field wrote False over a real True — and the
        # finalized record then told the doctor their own decision had not been made. Three
        # independent refutation lenses found this within minutes of each other.
        # It survives only while the stored text is still exactly the suggestion; editing away
        # withdraws it, and typing the same words by hand never grants it.
        accepted=bool(previous.get('accepted_suggestion')) and bool(suggestion) and value==suggestion and (kept or not governed_acceptance)
        if not value.strip() and request.POST.get('accept_'+key)=='on' and suggestion:
            # ⚠️ RECOMPUTED, NOT TRUSTED. An offer stored by an earlier release under a heading the notes now
            # show governs this line would put the denied or the family's finding in one click.
            if offer_context(governance,e.notes,previous,field['label']) is not None:
                return document_refusal(request,e,'The suggestion for "'+field['label']+'" is no longer offered: a heading or a sentence in the notes may change it. Type your own answer'+('' if is_wm else ' or choose "Leave blank — reviewed"')+'. Nothing was saved.',400)
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
        if len(value)>20000:return document_refusal(request,e,'Answer too long; nothing was truncated or saved.',400)
        if is_v3:
            # ⚠️ ONE READER FOR THE TEXT FORM: an option not printed on the form, an answer longer than its space, a
            # malformed table row or anything in a hand-signed area is refused here, naming the question, exactly as
            # finalization and export would refuse it later.
            try:value=v3_mapping.normalize(field,value)
            except ValidationError as exc:return document_refusal(request,e,error_message(exc)+' Nothing was saved.',400)
        reviewed=request.POST.get('reviewed_'+key)=='on'
        if reviewed:membership(request.user,e.department,roles=['owner','clinician'])
        answers[key]={**previous,'text':value,'reviewed':reviewed,'accepted_suggestion':accepted,
                      # The accepter is whoever performed the explicit act, carried forward while
                      # the acceptance stands. A later saver must not inherit somebody's decision.
                      'accepted_by':str(request.user.pk) if key in newly_accepted else (previous.get('accepted_by') if accepted else None),
                      'status':'edited' if value!=previous.get('text','') else previous.get('status','missing'),'reviewed_by':str(request.user.pk) if reviewed else None}
        if is_wm:
            quote=request.POST.get('source_'+key,'')
            if len(quote)>50000:return document_refusal(request,e,'Source quotations exceed the supported limit; nothing was saved.',400)
            try:evidence=source_quote_evidence(e.notes,field['label'],quote,labels)
            except ValidationError as exc:
                evidence=[];reviewed=False;review_errors.append(error_message(exc))
            answers[key].update(evidence=evidence,review_quote=quote,reviewed=reviewed,
                                reviewed_by=str(request.user.pk) if reviewed else None,
                                review_revision=target_revision if reviewed else None)
            if not value:answers[key]['status']='missing'
        else:
            # ⚠️ CARRIED FORWARD LIKE AN ACCEPTANCE, AND WITHDRAWN ONLY BY AN ACT. The box is
            # disabled for employees and so never posted by them; reading "not posted" as "untick"
            # would let an ordinary save erase a clinician's decision. Withdrawal therefore needs
            # the enabled control's marker (or typed text), and the clinician's authority.
            withdraw=prior_blank and not blank and (bool(value.strip()) or request.POST.get('blank_shown_'+key)=='1')
            stamp={'by':str(request.user.pk),'revision':target_revision,'at':timezone.now().isoformat()}
            history=list(previous.get('blank_history') or [])
            if blank:
                decision=previous.get('blank_decision') if prior_blank else {**stamp,'from_status':previous.get('status','missing')}
                if not prior_blank:
                    history.append({'decision':'left_blank',**stamp,'from_status':previous.get('status','missing')})
                    newly_blank.append(key)
                # ⚠️ A NEW decision is the clinician's own review. A CARRIED-FORWARD one is not: its box
                # arrives pre-ticked from the original decision, so stamping the saver here re-attributed
                # somebody else's review to whoever pressed Save. It keeps the review the saver ticked.
                own_review=True if not prior_blank else reviewed
                answers[key].update(text='',status='left_blank',reviewed=own_review,reviewed_by=str(request.user.pk) if own_review else None,
                                    accepted_suggestion=False,accepted_by=None,blank_decision=decision,blank_history=history)
            elif withdraw:
                membership(request.user,e.department,roles=['owner','clinician'])
                origin=(previous.get('blank_decision') or {}).get('from_status','missing')
                history.append({'decision':'withdrawn',**stamp})
                answers[key].pop('blank_decision',None)
                # ⚠️ ONLY an empty origin comes back. A `supported` or `edited` answer was cleared to
                # leave it blank, so restoring that label over empty text would show a supported
                # answer the clinician had deleted; it is an edit, and says so.
                answers[key].update(status='edited' if value.strip() or origin not in ('conflict','missing') else origin,
                                    blank_history=history)
                withdrawn_blank.append(key)
    decisions={}
    if is_wm:
        for requirement in e.template_version.review_requirements:
            key=requirement['key'];quote=request.POST.get('claim_source_'+key,'')
            if len(quote)>50000:return document_refusal(request,e,'Source quotations exceed the supported limit; nothing was saved.',400)
            reviewed=request.POST.get('claim_reviewed_'+key)=='on'
            try:evidence=source_quote_evidence(e.notes,requirement['label'],quote,labels)
            except ValidationError as exc:
                evidence=[];reviewed=False;review_errors.append(error_message(exc))
            variant=request.POST.get('claim_variant_'+key,requirement.get('default_variant'))
            if variant not in {item['id'] for item in requirement['variants']}:
                return document_refusal(request,e,'Choose an approved statement alternative. No changes were saved.',400)
            decisions[key]={'reviewed':reviewed,'evidence':evidence,'variant':variant}
    previous_decisions=dict((e.template_review or {}).get('decisions') or {}) if is_wm else {}
    e.answers=answers;e.revision=target_revision;e.status='review';wm_review.invalidate_review(e)
    clinician=is_wm and Membership.objects.filter(user=request.user,department=e.department,active=True,role__in=['owner','clinician']).exists()
    if is_wm and not clinician and previous_decisions:
        # ⚠️ A NON-CLINICIAN'S SAVE DISCARDED THE CLINICIAN'S STATEMENT DECISIONS WITHOUT A WORD: the review is emptied
        # above and only a clinician's save rebuilds one, so the chosen wordings and their sources vanished and the next
        # page fell back to the mapping's defaults. They are kept — each unreviewed (a review is its reader's own), bound
        # to this revision, as schema 0, which finalization never accepts. A wording the saver left as it was keeps the
        # clinician's sources; one the saver changed is the saver's unreviewed choice. (Ported from feat/wm-narrative.)
        kept={key for key,decision in decisions.items() if isinstance(previous_decisions.get(key),dict)
              and previous_decisions[key].get('variant')==decision['variant']}
        e.template_review={'schema':0,'decisions':{key:dict(previous_decisions[key] if key in kept else decision,reviewed=False)
                                                   for key,decision in decisions.items()},
                           'binding':wm_review.binding(e),'reviewer_id':str(request.user.pk)}
        if any(decisions[key]['evidence']!=previous_decisions[key].get('evidence') for key in kept):
            review_errors.append('A statement source you changed was not kept: a statement keeps the clinician\'s wording and '
                                 'sources until a clinician reviews it. Ask a clinician to change the source.')
        # (each named for what happened to it: a wording the saver replaced is never reported as kept — refutation R3)
        named=lambda keys:'; '.join(row['label'] for row in e.template_version.review_requirements if row['key'] in keys)
        replaced={key for key in decisions if isinstance(previous_decisions.get(key),dict) and key not in kept}
        if replaced:
            review_errors.append('Your save replaced the chosen statement wording for: '+named(replaced)+'. '
                                 'A clinician must review the new wording.')
        kept_reviewed={key for key in kept if previous_decisions[key].get('reviewed')}
        if kept_reviewed:
            review_errors.append('The statement choices a clinician reviewed were kept but are no longer reviewed: '
                                 +named(kept_reviewed)+'. A clinician must review them again.')
    if clinician:
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
    # A review is the reader's own, so saving without a tick removes a colleague's; record which.
    withdrawn_reviews=sorted(key for key,answer in answers.items() if (previous_answers.get(key) or {}).get('reviewed') and not answer.get('reviewed'))
    stored=(e.template_review or {}).get('decisions') or {}
    withdrawn_statement_reviews=sorted(key for key,decision in previous_decisions.items()
                                       if isinstance(decision,dict) and decision.get('reviewed') and not (stored.get(key) or {}).get('reviewed'))
    # Which statement's wording this save changed, as identifiers only (statement key, wording ids), never the text.
    statement_wording_changes=[{'statement':key,'from':decision.get('variant'),'to':stored[key].get('variant')}
                               for key,decision in sorted(previous_decisions.items())
                               if isinstance(decision,dict) and isinstance(stored.get(key),dict)
                               and decision.get('variant')!=stored[key].get('variant')]
    e.save(update_fields=['answers','revision','status','template_review'])
    audit(request.user,'encounter.answers_saved',e.pk,department=e.department,revision=e.revision,
          accepted_suggestions=sorted(newly_accepted),withdrawn_acceptances=sorted(withdrawn),
          left_blank=sorted(newly_blank),withdrawn_blank_decisions=sorted(withdrawn_blank),withdrawn_reviews=withdrawn_reviews,
          withdrawn_statement_reviews=withdrawn_statement_reviews,statement_wording_changes=statement_wording_changes)
    if is_wm:audit(request.user,'encounter.template_review_saved',e.pk,department=e.department,revision=e.revision,complete=e.template_review.get('assessment',{}).get('complete',False))
    messages.success(request,'Edits saved. Review every answer before finalizing.')
    for message in dict.fromkeys(review_errors):messages.warning(request,'Review remains incomplete: '+message)
    return redirect('encounter_detail',pk=pk)

def field_list(labels,limit=12):
    """Question labels for a refusal message, in form order, bounded so a long form stays readable."""
    shown=', '.join(labels[:limit])
    return shown+(f', and {len(labels)-limit} more.' if len(labels)>limit else '.')

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
            is_v3=v3_mapping.is_v3_version(e.template_version)
            # A v3 signature or initials area holds no answer (it is signed by hand on the printed form), so there is
            # nothing in it to review; every other field still needs the clinician's review.
            unreviewed=[f['label'] for f in e.template_version.fields if not e.answers.get(f['key'],{}).get('reviewed')
                        and not (is_v3 and f.get('kind') in v3_mapping.SIGNING_KINDS)]
            if unreviewed:raise ValidationError('A clinician must review every field, including missing information. Not yet reviewed: '+field_list(unreviewed))
            order=[f['key'] for f in e.template_version.fields]
            names={f['key']:f['label'] for f in e.template_version.fields}
            conflicts=[names.get(k,k) for k in sorted((k for k,v in e.answers.items() if v.get('status')=='conflict'),key=lambda k:(order.index(k) if k in order else len(order),k))]
            if conflicts:raise ValidationError('Resolve every conflict before finalizing. Each needs your decision: your own answer, the offered suggestion where there is one, or "Leave blank — reviewed" when no answer belongs there. Still in conflict: '+field_list(conflicts))
            # ⚠️ RECOMPUTED FROM THE NOTES, NOT TRUSTED FROM THE DRAFT. A draft generated before headings
            # governed their lines (or by any path that skipped the rule) can still hold a denied finding as
            # a ready answer; the review tick alone must not finalize it.
            from .generation import governed_decisions
            governed=governed_decisions(e.notes,e.template_version.fields,e.answers,
                                        [row['label'] for row in e.template_version.review_requirements])
            if governed:raise ValidationError('These answers were read from lines that a heading or a sentence in the notes may change, and still need your decision: '+field_list(governed)+' Each is shown on the document with what governs it (its lines, or the reason that applies to the whole note): enter your own answer there'+('' if e.template_version.document_backend else ' or choose "Leave blank — reviewed"')+'.')
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
                # A v3 answer is re-read from its text form (the same reader as saving) and converted per kind: an
                # option label, a list of labels, a ticked box, table rows. The engine checks every anchor's
                # fingerprint and refuses a stale one; its message is shown as it is.
                answers=(v3_mapping.fill_answers(version.fields,e.answers) if is_v3
                         else {k:v['text'] for k,v in e.answers.items()})
                fill_template(original,version.fields,answers,out)
            out.chmod(0o600)
            # ⚠️ THE REVISION IS NOT RENUMBERED HERE, DELIBERATELY: the record keeps the revision its review is bound to.
            # The Word receipt's binding (`source_revision`) and each reviewed answer's `review_revision` name THIS
            # revision, as did the trusted context the export was just filled under (the adapter refuses any other);
            # renumbering would leave the finalized record contradicting its own receipt, and the release evidence
            # (build-word-evidence.mjs) checks exactly that equality. Nothing may post to a finalized record anyway: every
            # writer refuses the status, and the database refuses any update to the row — so the status, not the revision,
            # is what stops a page opened before finalization (refutation round 4, R4-1: the code writers were the two that
            # did not check it). No legitimate action after finalization posts a revision: export is a GET.
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
        if Path(form.cleaned_data['audio'].name).suffix.lower() not in ['.wav','.webm','.mp3','.m4a']:raise ValidationError(AUDIO_FORMATS_HINT)
        relative=store_upload(form.cleaned_data['audio'],'audio')
        raw=private_path(relative).read_bytes()[:16]
        # The same frame-sync rule as core/audio.py, which measures the recording: the narrower
        # three-prefix list refused MPEG audio that the measuring reader accepts.
        if not (raw.startswith((b'RIFF',b'ID3',b'\x1aE\xdf\xa3')) or mpeg_frame_sync(raw) or raw[4:8]==b'ftyp'):raise ValidationError('This file is not a recording QuillMD can read. '+AUDIO_FORMATS_HINT)
        # ⚠️ A RECORDING EXISTS ONLY IN THE PAGE UNTIL IT IS SENT, so a quote that expires while the
        # doctor dictates discards it. The voice quote therefore lives as long as the over-limit
        # approval and the session (30 min). The limit it shows still binds, the signed pricing
        # configuration is unchanged, and length is re-measured at enqueue.
        quoted={**usage_quote(request,e,max_age=VOICE_QUOTE_SECONDS,expired=VOICE_QUOTE_EXPIRED,changed=VOICE_DOCUMENT_CHANGED),'transcript_review_required':True}
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
                messages.success(request,'Invitation accepted; your personal welcome credit is available.' if welcome_credit_label() else 'Invitation accepted.');return redirect('login')
    return render(request,'register.html',{'form':form,'invitation':invite,'existing_invited_account':existing_account})

#: ⚠️ A FINALIZED RECORD'S CODES ARE PART OF IT. Finalization does not renumber the revision (see `finalize`), so a Coding tab
#: opened before it posts the current revision afterwards: its Accept set accepted_by and audited coding.accept after
#: encounter.finalize, and its Suggest added a suggestion — while every other writer refused (refutation round 4, R4-1).
#: The database guard covers the encounter row only, not its code suggestions, so both code writers check the status.
FINALIZED_CODES='This document is finalized. Finalized documents are immutable.'
#: ⚠️ A PAGE THAT POSTS NO REVISION IS NOT EVIDENCE THAT ANYTHING CHANGED. A page rendered before the code forms carried one
#: was told "This document changed after you opened it" even when nothing had (refutation round 4, R4-7).
PAGE_OUT_OF_DATE='This page is out of date and must be reloaded: it was opened before this version of QuillMD and does not say which version of the document it showed.'

def notes_changed_since(e,revision):
    """Whether this encounter's notes changed after the revision a page posted, read from the audit rows each notes change
    leaves with the revision it made: a notes save, or a transcript an earlier release appended unreviewed."""
    try:revision=int(revision)
    except (TypeError,ValueError):return False
    return AuditEvent.objects.filter(target=str(e.pk),action__in=['encounter.notes_saved','coding.invalidated_by_transcription'],
                                     details__revision__gt=revision).exists()

def coding_refusal(request,e,planned_notes=None):
    """Why Suggest codes may not write to this encounter as the page posted it, as a refusal page; None when it may."""
    if e.status=='finalized':return document_refusal(request,e,FINALIZED_CODES+' Nothing was suggested.',409)
    if not request.POST.get('revision'):
        return document_refusal(request,e,PAGE_OUT_OF_DATE+' Nothing was suggested. Reload the document, then suggest codes again.',409)
    if request.POST.get('revision')!=str(e.revision) or (planned_notes is not None and e.notes!=planned_notes):
        return document_refusal(request,e,'This document changed after you opened it, in another window or by a colleague. Nothing was suggested. Reopen it to see the current notes before suggesting codes.',409)
    return None

@require_POST
def coding(request,pk):
    from .coding import plan,suggest
    # ⚠️ THE SUGGESTIONS ARE WORKED OUT BEFORE THE LOCK, AND ONLY WRITTEN UNDER IT. Holding the encounter's row lock for the
    # whole pass let any member stall the document — 12,000 codes in 48,000 characters held it 70.6 s, and a page view
    # waited 77.2 s (refutation round 4, R4-2). The plan is read from the notes at the page's revision; the write then takes
    # the lock, as `accept_code` below, and re-checks that revision and those notes, so a suggestion is still never drawn
    # from notes a concurrent save replaced (refutation round 3, F1) — that save now waits for the write alone.
    e=get_object_or_404(scoped(Encounter,request.user),pk=pk)
    membership(request.user,e.department)
    refused=coding_refusal(request,e)
    if refused:return refused
    planned=plan(e)
    with transaction.atomic():
        e=get_object_or_404(scoped(Encounter,request.user).select_for_update(),pk=pk)
        membership(request.user,e.department)
        refused=coding_refusal(request,e,planned_notes=planned.notes)
        if refused:return refused
        result=suggest(e,request.user,planned)
    served=e.service_date.strftime('%d %B %Y')
    from .coding import MAX_SUGGESTIONS
    over=(f' {result.omitted} further documented code{" was" if result.omitted==1 else "s were"} not suggested: a document holds '
          f'at most {MAX_SUGGESTIONS} code suggestions.' if result.omitted else '')
    if result.covered:
        messages.info(request,f'{result.count} new suggestions from explicitly documented codes, validated against {", ".join(result.versions)} for the {served} date of service.{over} Diagnosis inference is not enabled. CPT requires a licensed current feed.')
    elif result.versions:
        # A licensed CPT release can answer for a date no diagnosis release covers. Saying "nothing
        # was recorded" here would deny suggestions sitting on the page underneath the message.
        messages.warning(request,f'No ICD-10-CM release covers the {served} date of service, so no diagnosis code was validated. {result.count} new suggestions came from {", ".join(result.versions)}.{over} Import the diagnosis release in effect for that date.')
    else:
        messages.warning(request,f'No terminology release covers the {served} date of service, so nothing was validated and no suggestion was recorded. Import the release in effect for that date.')
    return redirect('/encounters/'+str(pk)+'/?tab=coding')

@require_POST
@transaction.atomic
def accept_code(request,pk,code_pk):
    # ⚠️ UNDER THE ENCOUNTER'S ROW LOCK, AT THE REVISION THE PAGE SHOWED, like every other writer of its codes or review.
    # Unlocked, an acceptance could commit after a notes save had counted what it would clear and before it cleared the
    # codes: answered and audited as accepted, then deleted by the save, which said nothing of it (refutation round 3, F1).
    # Now the two serialize: the save counts and names the accepted code, or this finds its code gone and says so.
    e=get_object_or_404(scoped(Encounter,request.user).select_for_update(),pk=pk)
    membership(request.user,e.department,roles=['owner','clinician'])
    if e.status=='finalized':return document_refusal(request,e,FINALIZED_CODES+' Nothing was accepted.',409)
    from .coding import applicable_releases,cpt_licensed
    item=CodeSuggestion.objects.select_for_update().filter(pk=code_pk,encounter=e).first()
    posted=request.POST.get('revision')
    if item is None:
        # A stale revision proves the notes changed, not that an arbitrary missing code ID
        # ever belonged to this encounter. State only availability and the observed change.
        if CodeSuggestion.objects.filter(pk=code_pk).exists():raise Http404
        if not posted:return document_refusal(request,e,PAGE_OUT_OF_DATE+' Nothing was accepted. Reload the document to see its current codes.',409)
        if not notes_changed_since(e,posted):raise Http404
        return document_refusal(request,e,'This code suggestion is unavailable. The notes changed after you opened the page, '
                                          'which clears their code suggestions. Nothing was accepted. Reopen '
                                          'it to see the current notes and codes.',409)
    if not posted:return document_refusal(request,e,PAGE_OUT_OF_DATE+' Nothing was accepted. Reload the document to see its current codes.',409)
    if posted!=str(e.revision):
        return document_refusal(request,e,'This document changed after you opened it, in another window or by a colleague. Nothing '
                                          'was accepted. Reopen it to see the current notes and codes.',409)
    if item.accepted_by_id:
        # ⚠️ AN ACCEPTANCE BELONGS TO WHOEVER MADE IT. Accepting does not renumber the revision, so a page opened before
        # clinician A accepted still posts the current revision, and B's Accept from it re-stamped the code as B's, with a
        # second coding.accept (refutation round 4, R4-6). Refused, not answered as a no-op: B is told the acceptance is
        # A's, by the email the page shows beside it, and when — nothing is written or audited.
        when=timezone.localtime(item.accepted_at).strftime('%Y-%m-%d %H:%M %Z') if item.accepted_at else 'an unrecorded time'
        return document_refusal(request,e,f'This code was already accepted by {item.accepted_by.email}, at {when}. '
                                          'Nothing was accepted. Reopen the document to see its current codes.',409)
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

#: Test mode keeps the sandbox return address it has always used (reached through the SSH tunnel).
SANDBOX_RETURN_ORIGIN='http://localhost:9130'

def checkout_return_origin():
    """Where Stripe Checkout returns the payer. Live mode: QUILLMD_APP_BASE_URL, and only a public HTTPS
    origin — never localhost, never the request's Host header. None refuses the checkout."""
    if settings.QUILLMD_STRIPE_MODE!='live':return SANDBOX_RETURN_ORIGIN
    from quillmd.application_profile import public_https_origin_problem
    origin=(settings.QUILLMD_APP_BASE_URL or '').rstrip('/')
    return None if public_https_origin_problem(origin,settings.ALLOWED_HOSTS) else origin

@require_POST
def checkout(request):
    import stripe
    from .billing import checkout_form,real_mode_refuses
    from .stripe_validation import sandbox_payments_refused
    # Real data mode checks out only in live mode: no Payment row and no provider call otherwise.
    if sandbox_payments_refused():messages.error(request,'Payments are not available. No charge was made.');return redirect('billing')
    form=checkout_form(request.user,request.POST)
    if not form.is_valid():messages.error(request,'Confirm a one-time amount between $5 and $500.');return redirect('billing')
    live=settings.QUILLMD_STRIPE_MODE=='live'
    # A key of the other mode is refused here, before authorization and before any provider call.
    if not stripe_key_configured(settings.STRIPE_SECRET_KEY):messages.error(request,'A Stripe live or restricted live key is required. No charge was made.' if live else 'A Stripe test or restricted test key is required. No charge was made.');return redirect('billing')
    return_origin=checkout_return_origin()
    if return_origin is None:messages.error(request,'Checkout needs the public HTTPS application address configured. No charge was made.');return redirect('billing')
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
        # Real data mode never spends a balance sandbox payments funded (reserve() refuses it), so live money is never
        # taken into one: refused before any Payment row or Stripe call. The payer is told what to do, and nothing that
        # identifies the balance, its payments or its amount.
        if real_mode_refuses(wallet):
            audit(request.user,'payment.checkout_refused_sandbox_balance',wallet.pk,payer='personal' if payer=='personal' else 'organization')
            messages.error(request,'This paid balance holds sandbox (test) payments, which real data mode never spends, so no live payment '
                           'can be added to it. Contact support to resolve this balance. No charge was made.')
            return redirect('billing')
        p,created=Payment.objects.get_or_create(request_key=request_key,defaults={'user':request.user,'wallet':wallet,'amount_cents':amount_cents,'status':'creating','livemode':live})
        if p.user_id!=request.user.pk or p.amount_cents!=amount_cents or p.wallet_id!=wallet.pk:raise ValidationError('A repeated checkout must use the original authorized balance and amount.')
        if not created:
            if p.checkout_url and p.status in ['pending','processing']:return redirect(p.checkout_url)
            messages.info(request,'This checkout was already submitted. Its payment status remains visible in billing.');return redirect('billing')
    try:
        session=stripe.checkout.Session.create(api_key=settings.STRIPE_SECRET_KEY,mode='payment',line_items=[{'price_data':{'currency':'usd','unit_amount':p.amount_cents,'product_data':{'name':'QuillMD one-time wallet credit' if live else 'QuillMD one-time wallet credit (test)'}},'quantity':1}],metadata={'payment_id':str(p.pk)},success_url=f'{return_origin}/billing/?payment=processing',cancel_url=f'{return_origin}/billing/',idempotency_key=f'checkout:{p.pk}')
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
    simulated=Usage.objects.filter(job=job,simulated=True).exists() or (job.kind in ('generation','mapping') and job.config.get('mode',settings.AI_MODE)!='live')
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
    audit(request.user,'job.resolved',job.pk,department=job.department,outcome=data['outcome'],evidence_note=note,settled_usage=bool(settled),simulated=simulated,actual_cost=str(absorbed.amount) if absorbed else None)
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
    if e.status=='finalized' or Job.objects.filter(encounter=e,state__in=['queued','running','reconciliation']).exists():return document_refusal(request,e,'This document is locked.',409)
    if request.POST.get('revision')!=str(e.revision):return document_refusal(request,e,'The notes changed after you opened this document, in another window or by a colleague. Reopen it to see the current notes before editing.',409)
    transcript_job=None;raw_transcript=None
    if request.POST.get('transcript_job'):
        try:transcript_id=UUID(request.POST['transcript_job'])
        except (ValueError,TypeError):return document_refusal(request,e,'Invalid transcript reference.',400)
        transcript_job=get_object_or_404(Job,pk=transcript_id,encounter=e,kind='transcription',state='succeeded')
        if not transcript_job.config.get('transcript_review_required') or AuditEvent.objects.filter(action='transcription.applied',target=str(transcript_job.pk)).exists():
            return document_refusal(request,e,'This transcript has already been applied or is not awaiting review.',409)
        if request.POST.get('transcript_reviewed')!='on' or request.POST.get('transcript_mode') not in ['append','replace']:
            return document_refusal(request,e,'Review the transcript and choose how to add it to the source notes.',400)
        try:raw_transcript,_=review_transcript(transcript_job)
        except (ValidationError,OSError,ValueError):return document_refusal(request,e,'The retained transcript could not be verified. Nothing changed.',409)
        corrected=request.POST.get('corrected_transcript','')
        if not corrected.strip() or len(corrected)>50000:return document_refusal(request,e,'Reviewed transcript must contain 1–50,000 characters.',400)
        notes=(e.notes+'\n\n'+corrected if e.notes else corrected) if request.POST['transcript_mode']=='append' else corrected
    else:notes=request.POST.get('notes','')
    if not notes.strip() or len(notes)>50000:return document_refusal(request,e,'Notes must contain 1–50,000 characters; nothing was truncated.',400)
    # ⚠️ AN UNCHANGED SAVE CHANGES NOTHING. It used to clear every answer, review decision and accepted code — by any
    # member, with only the revision audited. The stored notes stay byte-identical (a browser re-posts line breaks as
    # CRLF, which is the same text), so every evidence offset stays valid. A reviewed transcript is always a change.
    if transcript_job is None and same_text(notes,e.notes):
        messages.info(request,'Notes unchanged — nothing was cleared.');return redirect('encounter_detail',pk=pk)
    cleared=review_state_counts(e)
    e.notes=notes;e.answers={};e.revision+=1;e.status='draft';wm_review.invalidate_review(e);e.save(update_fields=['notes','answers','revision','status','template_review'])
    CodeSuggestion.objects.filter(encounter=e).update(accepted_by=None,accepted_at=None)
    CodeSuggestion.objects.filter(encounter=e).delete()
    audit(request.user,'coding.invalidated_by_source_edit',e.pk,department=e.department)
    audit(request.user,'encounter.notes_saved',e.pk,department=e.department,revision=e.revision,cleared=cleared)
    if transcript_job:
        audit(request.user,'transcription.applied',transcript_job.pk,department=e.department,revision=e.revision,
              mode=request.POST['transcript_mode'],raw_sha256=hashlib.sha256(raw_transcript.encode()).hexdigest(),
              corrected_sha256=hashlib.sha256(corrected.encode()).hexdigest(),corrected=corrected.replace('\r\n','\n')!=raw_transcript.replace('\r\n','\n'))
    # (said plainly to whoever saved: any member's changed save clears a clinician's review — refutation round 2 — and
    # exactly what it cleared, read from the counts just audited — refutation round 3, F2)
    messages.success(request,'Notes saved. '+cleared_sentence(cleared)+'Generate and review a new answer draft.')
    return redirect('encounter_detail',pk=pk)

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


def mpeg_frame_sync(raw):
    """core/audio.py's MPEG dispatch rule (11 set sync bits). The measuring reader still decides."""
    return len(raw)>1 and raw[0]==0xFF and raw[1]&0xE0==0xE0

AUDIO_FORMATS_HINT='Upload a .wav, .webm, .mp3 or .m4a recording (up to 15 MB), or record in the browser.'
VOICE_QUOTE_SECONDS=1800
VOICE_QUOTE_EXPIRED=('The price shown on this page expired before this recording was sent. Nothing was sent or '
                     'charged, and the recording was not kept. Reload the page, then record or upload it again.')
#: The revision moves when notes OR answers are saved, so the reason names the document, not the notes.
VOICE_DOCUMENT_CHANGED=('This document (its notes or answers) changed in another window or by a colleague after this page '
                        'loaded. Nothing was sent or charged, and the recording was not kept. Reload the page, then record '
                        'or upload it again.')

def usage_quote(request,encounter,max_age=600,expired='Usage quote expired or changed. Reload to review the current maximum charge.',changed=None):
    from .generation import configuration
    raw=request.POST.get('usage_quote')
    if not raw and settings.AI_MODE!='live':return configuration()
    try:
        quote=signing.loads(raw,salt='usage-quote',max_age=max_age)
        if quote['user']!=str(request.user.pk) or quote['encounter']!=str(encounter.pk):raise ValueError()
        revision,config=quote['revision'],quote['config']
    except (signing.BadSignature,ValueError,TypeError,KeyError):
        raise ValidationError(expired)
    # The same refusal either way; only the reason differs, so the doctor knows what actually happened.
    if revision!=encounter.revision:raise ValidationError(changed or expired)
    return config
