from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.core.validators import validate_email
from django.utils import timezone
import idna
import ipaddress
from .models import User, Department, Patient, TemplateVersion, Membership, Invitation, ClinicInvitation, Organization, latest_service_date
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
#: (checked as typed, before lowercasing). The domain goes through account_domain, label by label: a label that is ASCII
#: (as typed, or once UTS46 has mapped it) is kept, lowercased, exactly as before -- a typed "xn--" label only when it is a
#: well-formed A-label (account_a_label) --; any other label is converted by idna (UTS46 mapping, non-transitional -- idna
#: 3.x has no transitional mode --, STD3 rules, IDNA2008 validity: bidi, CONTEXTJ/O, canonical Punycode) to its lowercase
#: A-label, so every spelling of one domain (case, fullwidth, NFD, soft hyphen, typed A-label, or a mix of the two forms)
#: is one stored address and two different domains (faß/fass, ıbm/ibm) stay two. The stored domain must itself pass
#: EmailValidator: that refuses a trailing dot (the fully qualified spelling of the same name, a second string for one
#: mailbox) and a converted form the email field would refuse when typed back (a@example.１２３). An IPv6 address literal is
#: accepted only in its shortest form (account_ip_literal). The bound is measured on the stored form. Nothing stored is
#: rewritten, and every ASCII input keeps exactly the lookup key it had before (account_lookup_email).
#: ⚠️ A DOOR THAT LOOKS AN ACCOUNT UP BY ADDRESS REACHES IT THROUGH accounts_at, AND KEYS ITS PER-ADDRESS LIMIT ON WHAT IT
#: REACHED (account_limit_key). Sign-in, recovery, verification resend and the check that refuses a new account for an
#: address that already has one all use it. It finds the rows stored under the lookup key (email__iexact, as every door
#: did) AND the rows stored before this rule in their own letters: main stored a Unicode domain as typed, and a lookup by
#: the A-label alone locked such an account out of sign-in and recovery and let a second account be created for its
#: mailbox (F2). The limit follows the account, not the spelling, so no respelling -- of the domain, or one the database's
#: UPPER() equates ('b@synthetic.ınvalid', 'ſam@…') -- is a fresh bucket of guesses against the same account (R1-F1).
ACCOUNT_EMAIL_NOT_ASCII=('Enter the email address in ASCII characters before the "@". The domain after it may be entered '
                         'in its own letters or in its ASCII ("xn--") form.')
ACCOUNT_EMAIL_QUOTED='Enter the email address without quotation marks.'
ACCOUNT_EMAIL_BAD_DOMAIN='Enter a valid domain after the "@", in its own letters or in its ASCII ("xn--") form.'
ACCOUNT_EMAIL_IP_LITERAL='Enter an IPv6 address after the "@" in its shortest form, in brackets: for example [2001:db8::1].'
ACCOUNT_EMAIL_MAX_LENGTH=min(User._meta.get_field('username').max_length,User._meta.get_field('email').max_length,
                             Invitation._meta.get_field('email').max_length,ClinicInvitation._meta.get_field('email').max_length)
ACCOUNT_EMAIL_TOO_LONG=f'Enter an email address of at most {ACCOUNT_EMAIL_MAX_LENGTH} characters.'
def account_a_label(label):
    """Whether a label typed in its ASCII "xn--" form is a well-formed A-label: its Punycode decodes and encodes back to
    exactly this label, under IDNA2008 (idna.ulabel) OR under IDNA2003 (the stdlib codec). Both refuse invalid Punycode
    ('xn--zz') and a non-canonical ("fake") A-label ('xn---bbk'). A name registered under IDNA2003 whose symbol IDNA2008
    disallows (☃.net is xn--n3h.net, i❤.ws is xn--i-7iq.ws) is kept, as it was before this rule (F1): its A-label is the
    only spelling of it the rule accepts, since the symbol typed in its own letters is refused, so it cannot be a second
    string for one mailbox."""
    try:
        idna.ulabel(label)
        return True
    except idna.IDNAError: pass
    try: label.encode('ascii').decode('idna')
    except UnicodeError: return False
    return True
def account_ip_literal(domain):
    """An address literal after "@" ([192.0.2.1], [2001:db8::1]), lowercased as before. An IPv6 address has many spellings
    ([::1], [0:0:0:0:0:0:0:1], [0000::0001]) and each was a second account for one mailbox (R1-F3), so it is accepted only
    in the one form ipaddress gives it (RFC 5952: shortest, lowercase), with no dotted IPv4 part. Another spelling is
    refused, not rewritten, for the reason a quoted local part is: an account stored in it before keeps its lookup key.
    (An IPv4 literal has one spelling already: EmailValidator refuses leading zeros.)"""
    domain=domain.lower()
    literal=domain[1:-1] if domain.endswith(']') else ''
    if ':' in literal:
        try: shortest=ipaddress.IPv6Address(literal).compressed
        except ValueError: shortest=None
        if shortest is not None and ('.' in literal or shortest!=literal):
            raise forms.ValidationError(ACCOUNT_EMAIL_IP_LITERAL)
    return domain
def account_domain(domain):
    """The stored form of an account address's domain (the part after the last "@"); ValidationError otherwise.
    Label by label, so a domain typed partly in its own letters and partly in ASCII gives the stored form its ASCII
    spelling gives: 'ab--cd.bücher.example' is 'ab--cd.xn--bcher-kva.example' (R1-F2), where converting the whole name
    refused the ASCII label 'ab--cd' that an all-ASCII domain keeps."""
    if domain.startswith('['): domain=account_ip_literal(domain)
    else:
        if domain.isascii(): labels=domain.lower().split('.')
        else:
            try: labels=idna.uts46_remap(domain,std3_rules=True).split('.')
            except idna.IDNAError: raise forms.ValidationError(ACCOUNT_EMAIL_BAD_DOMAIN) from None
        for index,label in enumerate(labels):
            if not label.isascii():
                try: labels[index]=idna.alabel(label).decode('ascii')
                except idna.IDNAError: raise forms.ValidationError(ACCOUNT_EMAIL_BAD_DOMAIN) from None
            elif label.startswith('xn--') and not account_a_label(label):
                raise forms.ValidationError(ACCOUNT_EMAIL_BAD_DOMAIN)
        domain='.'.join(labels)
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
    """The lookup key of a typed address: the stored form when the rule accepts the input, so every spelling of one domain
    gives one key; otherwise the input stripped and lowercased, exactly as before (it can match only what it matched
    before). accounts_at finds accounts by it."""
    try: return account_email(value)
    except forms.ValidationError: return (value or '').strip().lower()
#: A stored address holding a character outside ASCII (a PostgreSQL regular expression): every door now stores ASCII, so
#: only a row stored before this rule. It is the only kind of row whose lookup key the rule changed.
LEGACY_ADDRESS_PATTERN=r'[^\x01-\x7f]'
def legacy_domain(domain):
    """The stored form of a domain stored before this rule in its own letters, when that is the one name its mail can have
    gone to: when IDNA2003 (the stdlib codec Django's mail path converts a recipient's domain with) gives the same A-label
    as the rule. Otherwise None. For ß, ς, ZWJ and ZWNJ the two standards name different domains (faß.de is fass.de under
    IDNA2003 and xn--fa-hia.de under the rule), and which of them the account was verified at is not established: such a
    row is reached only by its own spelling, as before. A trailing full stop (EmailValidator admitted an ideographic or
    fullwidth one, and main stored it as typed) is the fully qualified spelling of the same name, so it is set aside."""
    if domain[-1:] in ('.','\u3002','\uff0e','\uff61'): domain=domain[:-1]
    try: stored=account_domain(domain)
    except forms.ValidationError: return None
    try: mailed=domain.encode('idna').decode('ascii').lower()
    except UnicodeError: return None
    return stored if stored==mailed else None
def legacy_accounts_at(value,accounts):
    """The rows stored before this rule with a non-ASCII address that a typed address the rule ACCEPTS reaches, and that
    email__iexact on its lookup key does not: (as typed, same name). The part before "@" is compared as the iexact lookup
    compares it, by the database's UPPER() (so a legacy 'ſam@…' answers for 'sam@…', RA-LOW-1); the domain is either the
    one typed, up to case (as the lookup before this rule matched it), or the same name under legacy_domain."""
    try: key=account_email(value)
    except forms.ValidationError: return [],[]
    local,_,domain=key.rpartition('@')
    typed_domain=(value or '').strip().rpartition('@')[2].lower()
    as_typed,same_name=[],[]
    for account in (accounts.filter(email__istartswith=local+'@',email__regex=LEGACY_ADDRESS_PATTERN)
                    .exclude(email__iexact=key).order_by('pk')):
        stored_local,_,stored_domain=account.email.strip().rpartition('@')
        if len(stored_local)!=len(local): continue          # the "@" the prefix matched is not the address's last one
        if stored_domain.lower()==typed_domain: as_typed.append(account)
        elif legacy_domain(stored_domain)==domain: same_name.append(account)
    return as_typed,same_name
def accounts_at(value,accounts=None):
    """Every account a door that LOOKS an account up by a typed address reaches, the one it acts on first: a legacy row
    stored exactly as typed (so each account the lookup before this rule reached is still reached by that spelling), then
    the rows stored under the lookup key (the one stored exactly as the key first, then by primary key, the order
    .first() took them in), then a legacy row with the same name. `accounts` narrows the rows (for example to active
    ones)."""
    accounts=User.objects.all() if accounts is None else accounts
    key=account_lookup_email(value)
    stored=sorted(accounts.filter(email__iexact=key),key=lambda account:(account.email.strip().lower()!=key,account.pk))
    as_typed,same_name=legacy_accounts_at(value,accounts)
    return as_typed+stored+same_name
def account_limit_key(account,key):
    """What a lookup door keys its per-address limit on: the stored address of the account it reached, so every spelling
    that reaches one account shares that account's one bucket; the lookup key when it reached none."""
    return account.email.strip().lower() if account is not None else key

class RegisterForm(SyntheticAttestation,UserCreationForm):
    synthetic_only=forms.BooleanField(label='I will use synthetic test data only.')
    class Meta: model=User; fields=['email','first_name','last_name']
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.drop_synthetic_attestation()
    def clean_email(self):
        email=account_email(self.cleaned_data['email'])
        # Refused when the lookup every door uses already answers with an account: an account stored before the rule (for
        # example 'ſam@…', or 'sam@bücher.example' stored in its own letters) answers the lookup for 'sam@…' (for
        # 'sam@xn--bcher-kva.example'), although the lower() unique index does not see one address.
        if accounts_at(self.cleaned_data['email']): raise forms.ValidationError(ACCOUNT_EXISTS)
        return email

#: ⚠️ TWO REQUESTS CAN CREATE ONE NEW ACCOUNT AT THE SAME MOMENT (R-A, docs/rebuild/v1/residuals-assessment-20260929.md).
#: RegisterForm's unique-email check reads committed rows, so two acceptances of different invitations for one new address
#: (or two registrations of it) can both pass it; the later account insert then waits on the unique index and fails with an
#: IntegrityError when the first commits. Its transaction rolled back whole: it created nothing and its invitation is unused.
#: The views answer it as the same request a moment later is answered (the address already has an account; sign in), never
#: with a 500 and never with a second account. Only when the account now exists: any other IntegrityError is still raised.
ACCOUNT_CREATED_MEANWHILE='An account for this email address was created a moment ago. This invitation has not been used: sign in, then open it again to accept it.'
ACCOUNT_EXISTS='An account with this email address already exists.'
def account_created_meanwhile(email): return bool(accounts_at(email))
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
    # The organization the department belongs to: one the caller owns a department of (an active owner membership).
    # It was taken from `.first()` of those memberships, so an owner of two organizations got the department in
    # whichever one the database returned first (inventory 7A, ISOLATION). One organization needs no choice.
    organization=forms.ModelChoiceField(queryset=Organization.objects.none(),required=False)
    def __init__(self,*args,user=None,**kwargs):
        super().__init__(*args,**kwargs)
        owned=Organization.objects.filter(department__membership__user=user,department__membership__active=True,
                                          department__membership__role='owner').distinct().order_by('name','pk') if user else Organization.objects.none()
        self.fields['organization'].queryset=owned
        self.owned=list(owned[:2])
        if len(self.owned)==1:
            self.fields['organization'].widget=forms.HiddenInput()
            self.fields['organization'].initial=self.owned[0].pk
    def clean(self):
        data=super().clean()
        if not data.get('organization') and not self.errors.get('organization'):
            if len(self.owned)==1:data['organization']=self.owned[0]
            else:self.add_error('organization','Choose the organization the department belongs to.')
        return data
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
