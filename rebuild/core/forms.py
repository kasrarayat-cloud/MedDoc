from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import User, Department, Patient, TemplateVersion, Membership, latest_service_date
from .security import departments


class SyntheticAttestation:
    """Drops the synthetic-data attestation when QUILLMD_DATA_MODE=real.

    In synthetic mode the checkbox is required exactly as before. In real mode the statement is
    false by design, so asking for it would train people to tick a box that says the opposite of
    what they are doing. Checked at construction, so it follows the setting a test overrides.
    """
    def drop_synthetic_attestation(self):
        if not settings.SYNTHETIC_ONLY: self.fields.pop('synthetic_only',None)

class LoginForm(forms.Form):
    email=forms.EmailField(widget=forms.EmailInput(attrs={'autocomplete':'email'}))
    password=forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}))
    otp=forms.CharField(label='Authenticator code (administrators)',required=False,max_length=6,widget=forms.TextInput(attrs={'autocomplete':'one-time-code','inputmode':'numeric'}))
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if settings.QUILLMD_MFA_REQUIRED_ALL:
            self.fields['otp'].label='Authenticator code'
            self.fields['otp'].help_text='Required once you have set up an authenticator. Leave it blank on your first sign-in and you will be asked to set one up.'
class RegisterForm(SyntheticAttestation,UserCreationForm):
    synthetic_only=forms.BooleanField(label='I will use synthetic test data only.')
    class Meta: model=User; fields=['email','first_name','last_name']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.drop_synthetic_attestation()
    def clean_email(self): return self.cleaned_data['email'].lower().strip()
class OTPForm(forms.Form):
    code=forms.CharField(label='Six-digit authenticator code',min_length=6,max_length=6)
class ScopedForm(forms.Form):
    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,**kwargs); self.user=user
        if 'department' in self.fields:
            self.fields['department'].queryset=departments(user)
            # A doctor with one department is not asked to find it in a list of one.
            only=list(self.fields['department'].queryset[:2])
            if len(only)==1 and not self.is_bound: self.initial.setdefault('department',only[0].pk)
class UploadForm(ScopedForm):
    name=forms.CharField(max_length=140)
    department=forms.ModelChoiceField(queryset=Department.objects.none())
    # `accept` narrows the OS picker to the two formats the adapter supports, so an
    # unsupported file is not chosen, uploaded and only then refused. It is a convenience,
    # never a check: the suffix test and the adapter's own validation still decide.
    file=forms.FileField(label='Original Word (.docx) or fillable PDF form',
                         help_text='A blank form. Word .docx or a fillable PDF, up to 10 MB. Password-protected files, macros and active content are refused.',
                         widget=forms.ClearableFileInput(attrs={'accept':'.docx,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf'}))
    synthetic_only=forms.BooleanField(label='This is a blank form with no patient data.')
class MappingForm(forms.Form):
    labels=forms.JSONField(label='Field labels',help_text='JSON object mapping field keys to question labels. Locations cannot be changed; saving creates a new version.')
class PatientForm(SyntheticAttestation,ScopedForm):
    department=forms.ModelChoiceField(queryset=Department.objects.none())
    display_name=forms.CharField(max_length=140)
    reference=forms.CharField(max_length=100)
    synthetic_only=forms.BooleanField(label='This is a synthetic test patient.')
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.drop_synthetic_attestation()
class EncounterForm(SyntheticAttestation,ScopedForm):
    patient=forms.ModelChoiceField(queryset=Patient.objects.none())
    template_version=forms.ModelChoiceField(queryset=TemplateVersion.objects.none(),label='Template and mapping version')
    notes=forms.CharField(label='Type source notes (or add voice next)',required=False,widget=forms.Textarea(attrs={'rows':9}),max_length=50000,help_text='Type documented facts here, or leave this blank to record or upload audio after creating the document. Review is required before export.')
    service_date=forms.DateField(label='Date of service or discharge',widget=forms.DateInput(attrs={'type':'date'}),help_text='The date the service was provided, in your local time. Diagnosis codes are validated against the ICD-10-CM release in effect on that date, not the date you write the note. Check it if your clinic is not on UTC; it cannot be changed afterwards.')
    synthetic_only=forms.BooleanField(label='These are synthetic clinical notes.')
    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,user=user,**kwargs)
        self.fields['patient'].queryset=Patient.objects.filter(department__in=departments(user)).select_related('department')
        self.fields['template_version'].queryset=TemplateVersion.objects.filter(template__department__in=departments(user)).select_related('template').order_by('template__name','-number')
        self.fields['service_date'].initial=timezone.localdate()
        self.drop_synthetic_attestation()
    def clean_service_date(self):
        service_date=self.cleaned_data['service_date']
        if service_date>latest_service_date(): raise forms.ValidationError('The date of service or discharge cannot be in the future.')
        return service_date
    def clean(self):
        data=super().clean()
        if data.get('patient') and data.get('template_version') and data['patient'].department_id!=data['template_version'].template.department_id: raise forms.ValidationError('Patient and template must belong to the same department.')
        return data
class InvitationForm(ScopedForm):
    department=forms.ModelChoiceField(queryset=Department.objects.none())
    email=forms.EmailField()
    role=forms.ChoiceField(choices=[x for x in Membership.ROLES if x[0]!='owner'])
    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,user=user,**kwargs)
        self.fields['department'].queryset=departments(user).filter(membership__user=user,membership__active=True,membership__role__in=['owner','manager']).distinct()
class DepartmentForm(forms.Form):
    name=forms.CharField(max_length=120)
    organization_pays=forms.BooleanField(required=False,label='Charge this organization after each user’s personal promotional credit')
class CheckoutForm(forms.Form):
    payer=forms.ChoiceField(choices=[('personal','My personal paid balance')],required=False,initial='personal',label='Balance to fund')
    amount=forms.DecimalField(min_value=5,max_value=500,decimal_places=2,label='One-time top-up (USD)')
    consent=forms.BooleanField(label='I authorize this one-time payment. There are no automatic top-ups.')
class VoiceForm(forms.Form):
    audio=forms.FileField(label='Recorded audio (.wav, .webm, .mp3, .m4a)',
                          help_text='Up to 15 MB: about 1½ minutes of CD-quality WAV. Use MP3, M4A or the browser recorder for longer recordings.',
                          widget=forms.ClearableFileInput(attrs={'accept':'.wav,.webm,.mp3,.m4a,audio/*'}))
    consent=forms.BooleanField(label='Send this synthetic recording for transcription; charge provider usage × 1.5, never more than the limit shown.')
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if not settings.SYNTHETIC_ONLY:
            self.fields['consent'].label='Send this recording for transcription; charge provider usage × 1.5, never more than the limit shown.'
class ReconciliationForm(forms.Form):
    evidence_kind=forms.ChoiceField(choices=[('', 'Select the authenticated evidence type'),('provider_report', 'Provider cost report or export (not an invoice)'),('invoice', 'Provider invoice')],label='Evidence type')
    reconciled_cost=forms.DecimalField(min_value=0,max_digits=24,decimal_places=11,label='Reconciled actual provider cost (USD, up to 11 decimals)')
    evidence_reference=forms.CharField(max_length=240,label='Evidence reference (invoice number, export sha256 or report id)')
    evidence_sha256=forms.CharField(max_length=64,required=False,label='Evidence file sha256 (optional)')
    provider_credit_applied=forms.DecimalField(min_value=0,max_digits=24,decimal_places=12,required=False,label='Allocated provider credit (USD, informational)')
    discount_applied=forms.DecimalField(min_value=0,max_digits=24,decimal_places=12,required=False,label='Discount applied (USD, informational)')
    note=forms.CharField(max_length=240,required=False)
class PlatformCostForm(forms.Form):
    amount=forms.DecimalField(min_value=0,max_digits=24,decimal_places=12,label='Amount (USD)')
    description=forms.CharField(max_length=240)
    period_start=forms.DateField(required=False)
    period_end=forms.DateField(required=False)
    evidence_reference=forms.CharField(max_length=240,required=False)
    def clean(self):
        data=super().clean()
        if data.get('period_start') and data.get('period_end') and data['period_start']>data['period_end']: raise forms.ValidationError('Period start must not be after period end.')
        return data
class JobResolutionForm(forms.Form):
    OUTCOMES=[('release_no_cost','Release held funds: no provider cost evidenced'),('absorb_platform_failure','Absorb evidenced provider cost as a platform failure')]
    outcome=forms.ChoiceField(choices=OUTCOMES)
    evidence_note=forms.CharField(min_length=12,max_length=240,label='Evidence note (provider console reference)')
    actual_cost=forms.DecimalField(min_value=0,max_digits=24,decimal_places=12,required=False,label='Evidenced provider cost (USD)')
    def clean(self):
        data=super().clean()
        if data.get('outcome')=='absorb_platform_failure' and data.get('actual_cost') is None: raise forms.ValidationError('Absorbing a platform failure requires the evidenced provider cost.')
        return data
class ClinicInvitationForm(forms.Form):
    email=forms.EmailField(label='Clinic owner email')
    organization_name=forms.CharField(max_length=140,label='Clinic (organization) name')
    department_name=forms.CharField(max_length=120,label='First department name',initial='Main practice')
    def clean_email(self): return self.cleaned_data['email'].lower().strip()
class MfaResetForm(forms.Form):
    reason=forms.CharField(min_length=12,max_length=240,label='How the account holder’s identity was checked',help_text='Kept with the audit entry; it is the only record of the check.')
    confirm=forms.BooleanField(label='Remove every authenticator on this account and sign it out everywhere.')
