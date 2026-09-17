from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Department, Patient, TemplateVersion, Membership
from .security import departments

class LoginForm(forms.Form):
    email=forms.EmailField(widget=forms.EmailInput(attrs={'autocomplete':'email'}))
    password=forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}))
    otp=forms.CharField(label='Authenticator code (administrators)',required=False,max_length=6,widget=forms.TextInput(attrs={'autocomplete':'one-time-code','inputmode':'numeric'}))
class RegisterForm(UserCreationForm):
    synthetic_only=forms.BooleanField(label='I will use synthetic test data only.')
    class Meta: model=User; fields=['email','first_name','last_name']
    def clean_email(self): return self.cleaned_data['email'].lower().strip()
class OTPForm(forms.Form):
    code=forms.CharField(label='Six-digit authenticator code',min_length=6,max_length=6)
class ScopedForm(forms.Form):
    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,**kwargs); self.user=user
        if 'department' in self.fields: self.fields['department'].queryset=departments(user)
class UploadForm(ScopedForm):
    name=forms.CharField(max_length=140)
    department=forms.ModelChoiceField(queryset=Department.objects.none())
    file=forms.FileField(label='Original Word (.docx) or fillable PDF form')
    synthetic_only=forms.BooleanField(label='This is a blank form with no patient data.')
class MappingForm(forms.Form):
    labels=forms.JSONField(label='Field labels',help_text='JSON object mapping field keys to question labels. Locations cannot be changed; saving creates a new version.')
class PatientForm(ScopedForm):
    department=forms.ModelChoiceField(queryset=Department.objects.none())
    display_name=forms.CharField(max_length=140)
    reference=forms.CharField(max_length=100)
    synthetic_only=forms.BooleanField(label='This is a synthetic test patient.')
class EncounterForm(ScopedForm):
    patient=forms.ModelChoiceField(queryset=Patient.objects.none())
    template_version=forms.ModelChoiceField(queryset=TemplateVersion.objects.none(),label='Template and mapping version')
    notes=forms.CharField(widget=forms.Textarea(attrs={'rows':9}),max_length=50000,help_text='Record documented facts only. All answers remain subject to clinician review.')
    synthetic_only=forms.BooleanField(label='These are synthetic clinical notes.')
    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,user=user,**kwargs)
        self.fields['patient'].queryset=Patient.objects.filter(department__in=departments(user)).select_related('department')
        self.fields['template_version'].queryset=TemplateVersion.objects.filter(template__department__in=departments(user)).select_related('template').order_by('template__name','-number')
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
    audio=forms.FileField(label='Recorded audio (.wav, .webm, .mp3, .m4a)')
    consent=forms.BooleanField(label='Send this synthetic recording for transcription; charge provider usage × 1.5.')
class ReconciliationForm(forms.Form):
    reconciled_cost=forms.DecimalField(min_value=0,max_digits=24,decimal_places=12,label='Reconciled actual provider cost (USD)')
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
