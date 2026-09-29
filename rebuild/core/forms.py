from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import validate_email
from django.utils import timezone
import idna
from .models import User, Department, Patient, TemplateVersion, Membership, Invitation, ClinicInvitation, latest_service_date
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
#: ⚠️ ONE RULE FOR AN ACCOUNT'S EMAIL ADDRESS (RA-LOW-1, docs/rebuild/v1/residuals-assessment-20260929.md). The database's
#: case-insensitive uniqueness is lower(email) (User.Meta); every lookup of an account by address is email__iexact, which is
#: PostgreSQL's UPPER(); the views compare with str.lower() and the email allowlist with str.casefold(). They agree on ASCII
#: and nowhere else: lower('ſ') is 'ſ' but upper('ſ') is 'S', so 'ſam@…' passed the unique index beside 'sam@…' and both
#: answered the same iexact lookup — two accounts for one address. Django's EmailValidator admits exactly four non-ASCII
#: letters in a local part (ſ ı İ and the Kelvin sign U+212A), and only because re.IGNORECASE folds them onto its ASCII
#: class; every other one is refused already. So an account address is ASCII, stripped and lowercased: the one set on which
#: every comparison agrees. Nothing is folded into a different address (NFKC or casefold would rewrite 'ſ' as 's', and the
#: stored address is where the account's mail goes); an internationalized domain is stored in its ASCII ("xn--") form.
#: Applied where an account's address is chosen: registration, both invitation acceptances (RegisterForm), both invitation
#: issuances, and the first administrator (bootstrap_first_admin).
#: ⚠️ AND IT IS UNQUOTED AND FITS EVERY COLUMN IT IS WRITTEN TO (RR2-ACC-2, RR2-ACC-1, the second refutation of the same
#: report). EmailValidator accepts a quoted local part: '"sam"@…' and '"s\am"@…' are the mailbox 'sam@…' (RFC 5321) and a
#: different string to every comparison above, so a second account was created beside sam@…. A quoted address is refused,
#: not unquoted, for the reason nothing is folded: the stored address is where the account's mail goes. And the address
#: is the account's username (the views set username = email), a 150-character column where the email and invitation
#: columns hold 254: 151 characters or more passed every form and every door answered 500 (a DataError on the insert).
#: ⚠️ AND AN INTERNATIONALIZED DOMAIN IS ACCEPTED IN ITS OWN LETTERS AND STORED AS ITS A-LABEL (v1 close-out, email). The
#: STORED address stays ASCII, so every comparison above still agrees. The part before "@" must still be typed in ASCII
#: (checked as typed, before lowercasing). The domain goes through account_domain: an ASCII domain is lowercased exactly as
#: before, except that a typed "xn--" label must be a valid, canonical A-label; any other domain is converted by idna
#: (UTS46 mapping, non-transitional -- idna 3.x has no transitional mode --, STD3 rules, IDNA2008 validity: bidi, CONTEXTJ/O,
#: canonical Punycode) to the lowercase A-label form DNS resolves, so every spelling of one domain (case, fullwidth, NFD,
#: soft hyphen, typed A-label) is one stored address and two different domains (faß/fass, ıbm/ibm) stay two. The stored
#: domain must itself pass EmailValidator: that refuses a trailing dot (the fully qualified spelling of the same name, a
#: second string for one mailbox) and a converted form the email field would refuse when typed back (a@example.１２３).
#: The bound is measured on the stored form. The doors that LOOK an account up (sign-in, recovery, verification resend)
#: find it, and key their per-address limits, by account_lookup_email: one account and one bucket for every spelling.
#: Nothing stored is rewritten. An ASCII input gives exactly the lookup key it gave before, and the stored address it gave
#: before unless it carries an invalid "xn--" label, which is now refused where an address is chosen.
ACCOUNT_EMAIL_NOT_ASCII=('Enter the email address in ASCII characters before the "@". The domain after it may be entered '
                         'in its own letters or in its ASCII ("xn--") form.')
ACCOUNT_EMAIL_QUOTED='Enter the email address without quotation marks.'
ACCOUNT_EMAIL_BAD_DOMAIN='Enter a valid domain after the "@", in its own letters or in its ASCII ("xn--") form.'
ACCOUNT_EMAIL_MAX_LENGTH=min(User._meta.get_field('username').max_length,User._meta.get_field('email').max_length,
                             Invitation._meta.get_field('email').max_length,ClinicInvitation._meta.get_field('email').max_length)
ACCOUNT_EMAIL_TOO_LONG=f'Enter an email address of at most {ACCOUNT_EMAIL_MAX_LENGTH} characters.'
def account_domain(domain):
    """The stored form of an account address's domain (the part after the last "@"); ValidationError otherwise."""
    if domain.isascii():
        domain=domain.lower()
        try:
            for label in domain.split('.'):
                if label.startswith('xn--'): idna.ulabel(label)
        except idna.IDNAError: raise forms.ValidationError(ACCOUNT_EMAIL_BAD_DOMAIN) from None
    else:
        try: domain=idna.encode(domain,uts46=True,std3_rules=True).decode('ascii')
        except idna.IDNAError: raise forms.ValidationError(ACCOUNT_EMAIL_BAD_DOMAIN) from None
    if domain not in validate_email.domain_allowlist and not validate_email.validate_domain_part(domain):
        raise forms.ValidationError(ACCOUNT_EMAIL_BAD_DOMAIN)
    return domain
def account_email(value):
    """The address an account is created with or invited at, under the one rule above; ValidationError otherwise.
    The part before "@" is checked for ASCII as typed, before lowercasing: str.lower() itself folds the Kelvin sign onto
    'k'. A double quote can only be part of a quoted local part: EmailValidator admits it nowhere else."""
    email=(value or '').strip()
    local,at,domain=email.rpartition('@')
    if not local.isascii(): raise forms.ValidationError(ACCOUNT_EMAIL_NOT_ASCII)
    if '"' in email: raise forms.ValidationError(ACCOUNT_EMAIL_QUOTED)
    if not at: raise forms.ValidationError(ACCOUNT_EMAIL_BAD_DOMAIN)
    email=local.lower()+'@'+account_domain(domain)
    if len(email)>ACCOUNT_EMAIL_MAX_LENGTH: raise forms.ValidationError(ACCOUNT_EMAIL_TOO_LONG)
    return email
def account_lookup_email(value):
    """The address a lookup door (sign-in, recovery, verification resend) finds an account by AND keys its per-address
    rate limit on: the stored form when the rule accepts the input, so every spelling of one domain reaches one account and
    one bucket; otherwise the input stripped and lowercased, exactly as before (it can match only what it matched before)."""
    try: return account_email(value)
    except forms.ValidationError: return (value or '').strip().lower()

class RegisterForm(SyntheticAttestation,UserCreationForm):
    synthetic_only=forms.BooleanField(label='I will use synthetic test data only.')
    class Meta: model=User; fields=['email','first_name','last_name']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.drop_synthetic_attestation()
    def clean_email(self):
        email=account_email(self.cleaned_data['email'])
        # Refused when the lookup every door uses already answers with an account: an account stored before the rule (for
        # example 'ſam@…') answers email__iexact for 'sam@…', although the lower() unique index does not see one address.
        if account_created_meanwhile(email): raise forms.ValidationError(ACCOUNT_EXISTS)
        return email

#: ⚠️ TWO REQUESTS CAN CREATE ONE NEW ACCOUNT AT THE SAME MOMENT (R-A, docs/rebuild/v1/residuals-assessment-20260929.md).
#: RegisterForm's unique-email check reads committed rows, so two acceptances of different invitations for one new address
#: (or two registrations of it) can both pass it; the later account insert then waits on the unique index and fails with an
#: IntegrityError when the first commits. Its transaction rolled back whole: it created nothing and its invitation is unused.
#: The views answer it as the same request a moment later is answered (the address already has an account; sign in), never
#: with a 500 and never with a second account. Only when the account now exists: any other IntegrityError is still raised.
ACCOUNT_CREATED_MEANWHILE='An account for this email address was created a moment ago. This invitation has not been used: sign in, then open it again to accept it.'
ACCOUNT_EXISTS='An account with this email address already exists.'
def account_created_meanwhile(email): return User.objects.filter(email__iexact=email).exists()
#: ⚠️ ONE INVITATION SUBMITTED TWICE AT ONCE (RR2-ACC-3). Both requests pass validation before either commits and wait for
#: the invitation's row lock; the first accepts it (creating the account), the second then finds it used. It wrote nothing.
#: It used to answer a bare 404; it is told what happened and where to go, on the sign-in page.
INVITATION_ALREADY_ACCEPTED='This invitation has already been accepted: the account for this email address exists. Sign in to continue.'
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
        self.fields['template_version'].queryset=TemplateVersion.objects.filter(template__department__in=departments(user)).select_related('template','confirmation').order_by('template__name','-number')
        self.fields['template_version'].label_from_instance=lambda version:str(version)+(' (not yet confirmed)' if version.needs_confirmation else '')
        self.fields['service_date'].initial=timezone.localdate()
        self.drop_synthetic_attestation()
    def clean_service_date(self):
        service_date=self.cleaned_data['service_date']
        if service_date>latest_service_date(): raise forms.ValidationError('The date of service or discharge cannot be in the future.')
        return service_date
    def clean(self):
        data=super().clean()
        if data.get('patient') and data.get('template_version') and data['patient'].department_id!=data['template_version'].template.department_id: raise forms.ValidationError('Patient and template must belong to the same department.')
        # ⚠️ An automatically found (contract v3) mapping starts no document until a clinician has confirmed it.
        if data.get('template_version') and data['template_version'].needs_confirmation:
            raise forms.ValidationError(f'"{data["template_version"].template.name}" mapping version {data["template_version"].number} has not been confirmed. Open the form, check every field against it, and confirm the mapping before creating a document.')
        return data
class InvitationForm(ScopedForm):
    department=forms.ModelChoiceField(queryset=Department.objects.none())
    email=forms.EmailField()
    role=forms.ChoiceField(choices=[x for x in Membership.ROLES if x[0]!='owner'])
    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,user=user,**kwargs)
        self.fields['department'].queryset=departments(user).filter(membership__user=user,membership__active=True,membership__role__in=['owner','manager']).distinct()
    def clean_email(self): return account_email(self.cleaned_data['email'])
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
    def clean_email(self): return account_email(self.cleaned_data['email'])
class MfaResetForm(forms.Form):
    reason=forms.CharField(min_length=12,max_length=240,label='How the account holder’s identity was checked',help_text='Kept with the audit entry; it is the only record of the check.')
    confirm=forms.BooleanField(label='Remove every authenticator on this account and sign it out everywhere.')
