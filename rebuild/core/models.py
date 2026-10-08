import uuid
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone
from django.utils.crypto import salted_hmac

class User(AbstractUser):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    email=models.EmailField(unique=True)
    verified_at=models.DateTimeField(null=True,blank=True)
    session_version=models.PositiveBigIntegerField(default=0,editable=False)
    class Meta:
        constraints=[models.UniqueConstraint(Lower('email'),name='unique_email_casefold')]
    def __str__(self): return self.email
    def _get_session_auth_hash(self,secret=None):
        original=super()._get_session_auth_hash(secret=secret)
        # Preserve existing sessions until an administrator actually suspends
        # this account. A persistent generation also rejects a session saved by
        # an in-flight request after suspension, and cannot revive on re-enable.
        if not self.session_version:return original
        return salted_hmac('quillmd.account_session_version',
                           f'{original}:{self.session_version}',
                           secret=secret,algorithm='sha256').hexdigest()

class Entity(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: abstract=True

class ProviderIdentifiers:
    @property
    def legacy_resource_identifier(self):
        return ((self.provider.startswith('anthropic:') and self.provider_request_id.startswith('msg_'))
                or (self.provider.startswith('openai:') and self.provider_request_id.startswith('resp_')))
    @property
    def http_request_id(self):
        return '' if self.legacy_resource_identifier else self.provider_request_id
    @property
    def resource_id(self):
        return self.provider_resource_id or (self.provider_request_id if self.legacy_resource_identifier else '')

def provider_family_expression():
    return models.Func(models.F('provider'),models.Value(':'),models.Value(1),function='split_part',output_field=models.CharField())

def provider_resource_expression():
    return models.Case(
        models.When(~models.Q(provider_resource_id=''),then=models.F('provider_resource_id')),
        models.When(models.Q(provider__startswith='anthropic:',provider_request_id__startswith='msg_')|models.Q(provider__startswith='openai:',provider_request_id__startswith='resp_'),then=models.F('provider_request_id')),
        default=models.Value(''),output_field=models.CharField())

class Organization(Entity):
    name=models.CharField(max_length=140)
    def __str__(self): return self.name
class Department(Entity):
    organization=models.ForeignKey(Organization,on_delete=models.PROTECT)
    name=models.CharField(max_length=120)
    organization_pays=models.BooleanField(default=False)
    def __str__(self): return self.name
class Membership(Entity):
    ROLES=[('owner','Organization owner'),('manager','Department manager'),('clinician','Clinician'),('employee','Employee')]
    user=models.ForeignKey(User,on_delete=models.PROTECT)
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    role=models.CharField(max_length=12,choices=ROLES,default='employee')
    active=models.BooleanField(default=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['user','department'],name='one_department_membership')]
class Invitation(Entity):
    email=models.EmailField()
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    role=models.CharField(max_length=12,choices=Membership.ROLES,default='employee')
    token_hash=models.CharField(max_length=64,unique=True)
    expires_at=models.DateTimeField()
    accepted_at=models.DateTimeField(null=True)
    invited_by=models.ForeignKey(User,on_delete=models.PROTECT)
class Verification(Entity):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    token_hash=models.CharField(max_length=64,unique=True)
    expires_at=models.DateTimeField()
    used_at=models.DateTimeField(null=True)
class Patient(Entity):
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    display_name=models.CharField(max_length=140)
    reference=models.CharField(max_length=100)
    created_by=models.ForeignKey(User,on_delete=models.PROTECT)
    class Meta: constraints=[models.UniqueConstraint(fields=['department','reference'],name='patient_reference_in_department')]
    def __str__(self): return f'{self.display_name} · {self.department.name}'
class Template(Entity):
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    name=models.CharField(max_length=140)
    format=models.CharField(max_length=6)
    original_name=models.CharField(max_length=200)
    original_path=models.CharField(max_length=100)
    sha256=models.CharField(max_length=64)
    warnings=models.JSONField(default=list)
    created_by=models.ForeignKey(User,on_delete=models.PROTECT)
    def __str__(self): return self.name
class TemplateVersion(Entity):
    template=models.ForeignKey(Template,on_delete=models.PROTECT,related_name='versions')
    number=models.PositiveIntegerField()
    fields=models.JSONField(default=list)
    review_requirements=models.JSONField(default=list,blank=True)
    document_backend=models.JSONField(default=dict,blank=True)
    prepared_path=models.CharField(max_length=100,blank=True)
    prepared_sha256=models.CharField(max_length=64,blank=True)
    preparation=models.ForeignKey('TemplatePreparation',on_delete=models.PROTECT,null=True,blank=True,related_name='versions')
    created_by=models.ForeignKey(User,on_delete=models.PROTECT)
    class Meta: constraints=[models.UniqueConstraint(fields=['template','number'],name='mapping_version_unique')]
    def __str__(self): return f'{self.template.name} · mapping {self.number}'
class TemplatePreparation(Entity):
    template=models.OneToOneField(Template,on_delete=models.PROTECT,related_name='preparation')
    requested_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='template_preparations')
    state=models.CharField(max_length=24,default='queued')
    revision=models.PositiveIntegerField(default=0)
    config=models.JSONField(default=dict)
    inventory=models.JSONField(default=dict)
    proposal=models.JSONField(default=dict)
    checker=models.JSONField(default=dict)
    corrections=models.JSONField(default=dict)
    correction_history=models.JSONField(default=list)
    candidate_path=models.CharField(max_length=100,blank=True)
    candidate_sha256=models.CharField(max_length=64,blank=True)
    candidate_info=models.JSONField(default=dict)
    candidate_history=models.JSONField(default=list)
    changes=models.JSONField(default=list)
    error_code=models.CharField(max_length=60,blank=True)
    started_at=models.DateTimeField(null=True)
    finished_at=models.DateTimeField(null=True)
    approved_at=models.DateTimeField(null=True)
    approved_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,related_name='approved_preparations')
    approval_sha256=models.CharField(max_length=64,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(models.Value(1),condition=models.Q(state__in=['inventory','proposer','checker']),name='preparation_single_running')]
class PreparationReceipt(Entity):
    preparation=models.ForeignKey(TemplatePreparation,on_delete=models.PROTECT,related_name='receipts')
    role=models.CharField(max_length=12)
    state=models.CharField(max_length=20,default='reserved')
    requested_model=models.CharField(max_length=100)
    returned_model=models.CharField(max_length=100,blank=True)
    provider=models.CharField(max_length=30)
    request_sha256=models.CharField(max_length=64)
    provider_request_id=models.CharField(max_length=140,blank=True)
    provider_resource_id=models.CharField(max_length=140,blank=True)
    quote_maximum=models.DecimalField(max_digits=24,decimal_places=12)
    computed_cost=models.DecimalField(max_digits=24,decimal_places=12,null=True)
    usage=models.JSONField(default=dict)
    rates=models.JSONField(default=dict)
    simulated=models.BooleanField(default=False)
    response_path=models.CharField(max_length=100,blank=True)
    response_sha256=models.CharField(max_length=64,blank=True)
    failure=models.JSONField(default=dict)
    failure_path=models.CharField(max_length=100,blank=True)
    failure_sha256=models.CharField(max_length=64,blank=True)
    error_code=models.CharField(max_length=60,blank=True)
    started_at=models.DateTimeField(null=True)
    finished_at=models.DateTimeField(null=True)
    elapsed_ms=models.PositiveIntegerField(null=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['preparation','role'],name='preparation_role_once'),
                     models.CheckConstraint(condition=models.Q(role__in=['proposer','checker'],quote_maximum__gte=0,quote_maximum__lte=Decimal('0.16')),name='preparation_receipt_role_cap'),
                     models.CheckConstraint(condition=models.Q(computed_cost__isnull=True)|models.Q(computed_cost__gte=0),name='preparation_cost_nonnegative')]
def latest_service_date():
    """The furthest ahead a real date of service can legitimately be.

    The application stores UTC (TIME_ZONE='UTC'), and real zone offsets span UTC-12 to UTC+14, so a
    clinic's local date can lead the UTC date by one day and never by more. Refusing 'today+1' would
    reject a visit that has already happened for the first hours of every day east of UTC.
    """
    return timezone.localdate()+timedelta(days=1)


class Encounter(Entity):
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    patient=models.ForeignKey(Patient,on_delete=models.PROTECT)
    template_version=models.ForeignKey(TemplateVersion,on_delete=models.PROTECT)
    created_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='encounters')
    notes=models.TextField()
    # ICD-10-CM releases are fiscal-year scoped, so the applicable version is the
    # one in effect on the date of service or discharge, never the date the note
    # happens to be coded on.
    service_date=models.DateField()
    answers=models.JSONField(default=dict)
    template_review=models.JSONField(default=dict,blank=True)
    status=models.CharField(max_length=16,default='draft')
    revision=models.PositiveIntegerField(default=0)
    finalized_at=models.DateTimeField(null=True)
    finalized_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,related_name='finalized_encounters')
    export_path=models.CharField(max_length=100,blank=True)
    export_sha256=models.CharField(max_length=64,blank=True)
    def clean(self):
        if self.patient.department_id!=self.department_id or self.template_version.template.department_id!=self.department_id: raise ValidationError('Patient, template and encounter must share a department.')
        if self.service_date and self.service_date>latest_service_date(): raise ValidationError('The date of service or discharge cannot be in the future.')
class Job(ProviderIdentifiers,Entity):
    encounter=models.ForeignKey(Encounter,on_delete=models.PROTECT)
    user=models.ForeignKey(User,on_delete=models.PROTECT)
    kind=models.CharField(max_length=20,default='generation')
    state=models.CharField(max_length=20,default='queued')
    request_key=models.CharField(max_length=160,unique=True)
    revision=models.PositiveIntegerField(default=0)
    provider=models.CharField(max_length=60,blank=True)
    payer=models.CharField(max_length=100,blank=True)
    config=models.JSONField(default=dict)
    result_path=models.CharField(max_length=100,blank=True)
    result_sha256=models.CharField(max_length=64,blank=True)
    provider_request_id=models.CharField(max_length=140,blank=True)
    provider_resource_id=models.CharField(max_length=140,blank=True)
    error=models.CharField(max_length=250,blank=True)
    input_path=models.CharField(max_length=100,blank=True)
    started_at=models.DateTimeField(null=True)
    finished_at=models.DateTimeField(null=True)
    @property
    def pricing_snapshot(self):
        return self.config.get('pricing_version','Not captured for this historical job')
class Wallet(Entity):
    user=models.ForeignKey(User,on_delete=models.PROTECT,null=True)
    organization=models.ForeignKey(Organization,on_delete=models.PROTECT,null=True)
    kind=models.CharField(max_length=10,choices=[('promo','Promotional'),('paid','Paid')])
    balance=models.DecimalField(max_digits=24,decimal_places=12,default=0)
    reserved=models.DecimalField(max_digits=24,decimal_places=12,default=0)
    class Meta:
        constraints=[models.CheckConstraint(condition=models.Q(balance__gte=0,reserved__gte=0)&models.Q(balance__gte=models.F('reserved')),name='wallet_never_overspent'),models.CheckConstraint(condition=(models.Q(user__isnull=False,organization__isnull=True)|models.Q(user__isnull=True,organization__isnull=False,kind='paid')),name='wallet_single_owner'),models.UniqueConstraint(fields=['user','kind'],name='user_wallet_unique'),models.UniqueConstraint(fields=['organization','kind'],name='org_wallet_unique')]
    @property
    def label(self): return f'{self.get_kind_display()} · {self.user.email if self.user_id else self.organization.name}'
class LedgerEntry(Entity):
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=24,decimal_places=12)
    kind=models.CharField(max_length=24)
    key=models.CharField(max_length=180,unique=True)
    description=models.CharField(max_length=240)
    job=models.ForeignKey(Job,on_delete=models.PROTECT,null=True)
    balance_after=models.DecimalField(max_digits=24,decimal_places=12)
    def save(self,*args,**kwargs):
        if not self._state.adding: raise ValidationError('Ledger entries are immutable; create a compensating entry.')
        super().save(*args,**kwargs)
    def delete(self,*args,**kwargs): raise ValidationError('Ledger entries cannot be deleted.')
class Reservation(Entity):
    job=models.ForeignKey(Job,on_delete=models.PROTECT,related_name='reservations')
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT)
    amount=models.DecimalField(max_digits=24,decimal_places=12)
    state=models.CharField(max_length=12,default='held')
    class Meta: constraints=[models.UniqueConstraint(fields=['job','wallet'],name='reservation_unique')]
class Usage(ProviderIdentifiers,Entity):
    job=models.OneToOneField(Job,on_delete=models.PROTECT)
    user=models.ForeignKey(User,on_delete=models.PROTECT)
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    organization=models.ForeignKey(Organization,on_delete=models.PROTECT)
    payer=models.CharField(max_length=100)
    provider=models.CharField(max_length=80)
    provider_request_id=models.CharField(max_length=140,blank=True)
    provider_resource_id=models.CharField(max_length=140,blank=True)
    units=models.JSONField(default=dict)
    rates=models.JSONField(default=dict)
    actual_cost=models.DecimalField(max_digits=24,decimal_places=12)
    charged_cost=models.DecimalField(max_digits=24,decimal_places=12)
    simulated=models.BooleanField(default=False)
    @property
    def cost_evidence(self):
        if self.simulated: return 'Simulated · no provider cost'
        try: receipt=self.job.providerreceipt
        except ProviderReceipt.DoesNotExist: return 'Recorded provider units · durable receipt unavailable'
        if any(getattr(receipt,key)!=getattr(self,key) for key in ['provider','provider_request_id','provider_resource_id','actual_cost','units','rates','simulated']): return 'Provider evidence mismatch · reconciliation required'
        return 'Provider-metered usage × configured rates'
    @property
    def reconciliation(self):
        try: return self.costreconciliation
        except ObjectDoesNotExist: return None
    @property
    def invoice_status(self):
        row=self.reconciliation
        return f'{row.evidence_status}: {row.evidence_reference}' if row else 'Not reconciled to a provider invoice'
    class Meta:
        constraints=[
            # Never above 1.5 × cost. Below it only when the approved customer limit capped the charge; the audit requires the
            # difference to exist, exactly, as one 'absorbed_over_limit' platform cost.
            models.CheckConstraint(condition=models.Q(actual_cost__gte=0,charged_cost__gte=0)&models.Q(charged_cost__lte=models.F('actual_cost')*Decimal('1.5')),name='usage_charge_at_most_multiplier'),
            models.UniqueConstraint(provider_family_expression(),models.F('provider_request_id'),condition=~models.Q(provider_request_id='')&models.Q(simulated=False),name='usage_provider_request_once'),
            models.UniqueConstraint(provider_family_expression(),provider_resource_expression(),condition=(~models.Q(provider_resource_id='')|models.Q(provider__startswith='anthropic:',provider_request_id__startswith='msg_')|models.Q(provider__startswith='openai:',provider_request_id__startswith='resp_'))&models.Q(simulated=False),name='usage_provider_resource_once'),
        ]
class Payment(Entity):
    user=models.ForeignKey(User,on_delete=models.PROTECT)
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT)
    amount_cents=models.PositiveIntegerField()
    stripe_session=models.CharField(max_length=200,unique=True,null=True)
    stripe_intent=models.CharField(max_length=200,unique=True,null=True)
    status=models.CharField(max_length=20,default='pending')
    request_key=models.CharField(max_length=64,unique=True,null=True)
    checkout_url=models.URLField(max_length=1000,blank=True)
class WebhookEvent(Entity):
    event_id=models.CharField(max_length=180,unique=True)
    kind=models.CharField(max_length=80)
    payload_hash=models.CharField(max_length=64)
    # Retain only billing identifiers/amounts: never customer email or raw payloads.
    object_data=models.JSONField(default=dict)
    semantic_hash=models.CharField(max_length=64,blank=True)
    status=models.CharField(max_length=20,default='processed')
    attempts=models.PositiveIntegerField(default=0)
    error=models.CharField(max_length=160,blank=True)
    processed_at=models.DateTimeField(null=True)
class Refund(Entity):
    payment=models.ForeignKey(Payment,on_delete=models.PROTECT)
    stripe_refund=models.CharField(max_length=200,unique=True)
    amount_cents=models.PositiveIntegerField()
    status=models.CharField(max_length=20)
class CodeSet(Entity):
    system=models.CharField(max_length=12)
    version=models.CharField(max_length=60)
    effective_from=models.DateField()
    effective_until=models.DateField()
    source_url=models.URLField()
    sha256=models.CharField(max_length=64)
    license_reference=models.CharField(max_length=150,blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=['system','version'],name='code_release_unique')]
class Code(Entity):
    release=models.ForeignKey(CodeSet,on_delete=models.PROTECT)
    code=models.CharField(max_length=15)
    description=models.CharField(max_length=500)
    class Meta: constraints=[models.UniqueConstraint(fields=['release','code'],name='code_in_release_unique')]
class CodeSuggestion(Entity):
    encounter=models.ForeignKey(Encounter,on_delete=models.PROTECT)
    terminology=models.ForeignKey(Code,on_delete=models.PROTECT)
    explanation=models.CharField(max_length=600)
    evidence=models.TextField()
    accepted_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True)
    accepted_at=models.DateTimeField(null=True)
    @property
    def system(self): return self.terminology.release.system
    @property
    def code(self): return self.terminology.code
    @property
    def description(self): return self.terminology.description
    class Meta: constraints=[models.UniqueConstraint(fields=['encounter','terminology'],name='suggestion_once')]
class AuditEvent(Entity):
    actor=models.ForeignKey(User,on_delete=models.PROTECT,null=True)
    organization=models.ForeignKey(Organization,on_delete=models.PROTECT,null=True)
    department=models.ForeignKey(Department,on_delete=models.PROTECT,null=True)
    action=models.CharField(max_length=70)
    target=models.CharField(max_length=160,blank=True)
    details=models.JSONField(default=dict)
    def save(self,*args,**kwargs):
        if not self._state.adding: raise ValidationError('Audit records are append-only.')
        super().save(*args,**kwargs)
    def delete(self,*args,**kwargs): raise ValidationError('Audit records are append-only.')
class LoginAttempt(Entity):
    key=models.CharField(max_length=64,unique=True)
    count=models.PositiveIntegerField(default=0)
    window_start=models.DateTimeField()

class ProviderReceipt(ProviderIdentifiers,Entity):
    job=models.OneToOneField(Job,on_delete=models.PROTECT)
    provider=models.CharField(max_length=80)
    provider_request_id=models.CharField(max_length=140,blank=True)
    provider_resource_id=models.CharField(max_length=140,blank=True)
    actual_cost=models.DecimalField(max_digits=24,decimal_places=12)
    units=models.JSONField(default=dict)
    rates=models.JSONField(default=dict)
    simulated=models.BooleanField(default=False)
    result_path=models.CharField(max_length=100,blank=True)
    result_sha256=models.CharField(max_length=64,blank=True)
    @property
    def cost_evidence(self):
        return 'Simulated · no provider cost' if self.simulated else 'Provider-metered usage × configured rates'
    @property
    def invoice_status(self): return 'Not reconciled to a provider invoice'

class CostReconciliation(Entity):
    """Authentic provider evidence for one usage row. The Usage row and its original ledger entries are never modified;
    the difference is settled by appended ledger entries of kind 'reconciliation'."""
    EVIDENCE_KINDS=[('unclassified','Unclassified evidence · invoice status unknown'),
                    ('provider_report','Provider-reported actual · not invoice reconciled'),
                    ('invoice','Invoice-reconciled actual')]
    LEDGER_STATUSES=[('applied','Applied to the ledger'),('pending_funds','Pending available paid funds'),('absorbed','No user ledger movement: the charge was already reversed as an absorbed platform failure')]
    usage=models.OneToOneField(Usage,on_delete=models.PROTECT)
    evidence_kind=models.CharField(max_length=16,choices=EVIDENCE_KINDS,default='unclassified')
    reconciled_cost=models.DecimalField(max_digits=24,decimal_places=12)
    provider_credit_applied=models.DecimalField(max_digits=24,decimal_places=12,default=0)
    discount_applied=models.DecimalField(max_digits=24,decimal_places=12,default=0)
    evidence_reference=models.CharField(max_length=240)
    evidence_sha256=models.CharField(max_length=64,blank=True)
    recorded_by=models.ForeignKey(User,on_delete=models.PROTECT)
    note=models.CharField(max_length=240,blank=True)
    charge_delta=models.DecimalField(max_digits=24,decimal_places=12)
    # Change in the amount QuillMD absorbs above the approved customer limit (signed): the customer charge never exceeds the
    # limit the customer approved, so evidence of a higher provider cost moves this, not the customer's ledger.
    over_limit_delta=models.DecimalField(max_digits=24,decimal_places=12,default=0)
    ledger_status=models.CharField(max_length=16,choices=LEDGER_STATUSES)
    @property
    def evidence_status(self):
        return dict(self.EVIDENCE_KINDS).get(self.evidence_kind, self.EVIDENCE_KINDS[0][1])
    @property
    def invoice_reconciled(self):
        return self.evidence_kind=='invoice'
    @property
    def provider_evidence_reconciled(self):
        return self.evidence_kind in ('provider_report','invoice')
    def save(self,*args,**kwargs):
        # Evidence and amounts are append-only; only the ledger status may advance once funds exist.
        if not self._state.adding and set(kwargs.get('update_fields') or ())!={'ledger_status'}: raise ValidationError('Cost reconciliations are immutable apart from their ledger status.')
        super().save(*args,**kwargs)
    def delete(self,*args,**kwargs): raise ValidationError('Cost reconciliations cannot be deleted.')
    class Meta:
        constraints=[
            models.CheckConstraint(condition=models.Q(reconciled_cost__gte=0,provider_credit_applied__gte=0,discount_applied__gte=0),name='reconciliation_amounts_nonnegative'),
            models.CheckConstraint(condition=models.Q(ledger_status__in=['applied','pending_funds','absorbed']),name='reconciliation_ledger_status_known'),
            models.CheckConstraint(condition=~models.Q(evidence_reference=''),name='reconciliation_evidence_required'),
            models.CheckConstraint(condition=models.Q(evidence_kind__in=['unclassified','provider_report','invoice']),name='reconciliation_evidence_kind_known'),
        ]
class ServiceHealth(Entity):
    """Operational status PUBLISHED into the database by a privileged process, for the console to read.

    The web process cannot compute this and must not pretend to. `quillmd-fresh-admin.service`
    runs as `quillmd-app` and carries `InaccessiblePaths=/opt/meddoc-pro/rebuild/.runtime`, so
    every backup/offsite state file is masked from its mount namespace; the state directories are
    also mode 0700 owned by a different identity. A view that reads those paths returns
    'unavailable' on a perfectly healthy host — a false red, which becomes a false green the first
    time somebody decides the panel is unreliable.

    So the identity that owns the state publishes here (`manage.py publish_operations_status`) and
    the console reads a row. `computed_at` and `expected_interval_seconds` exist so the reader can
    tell 'fresh' from 'stale' from 'never published' rather than collapsing all three into silence.

    The payload carries only what the publishing side already redacts: conditions, timestamps, run
    identifiers and boolean verdicts. Never a secret, never a path, never clinical content.
    """
    KEYS = {'backup': 'Backup and offsite recovery'}
    SEVERITIES = [('healthy', 'Healthy'), ('warning', 'Warning'), ('in_progress', 'In progress'), ('failure', 'Failure')]
    key = models.CharField(max_length=40, unique=True)
    condition = models.CharField(max_length=60)
    severity = models.CharField(max_length=12, choices=SEVERITIES)
    healthy = models.BooleanField()
    action = models.CharField(max_length=400)
    payload = models.JSONField(default=dict)
    computed_at = models.DateTimeField()
    published_at = models.DateTimeField(auto_now=True)
    expected_interval_seconds = models.PositiveIntegerField(default=300)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(expected_interval_seconds__gte=60), name='service_health_interval_sane')]
    def __str__(self): return f'{self.key} · {self.condition}'


class PlatformCost(Entity):
    """Costs QuillMD carries itself. Never charged to a user and never part of a wallet ledger."""
    KINDS=[('fixed_overhead','Fixed overhead'),('absorbed_failure','Provider cost of a platform failure'),
           ('absorbed_over_limit','Charge above the approved customer limit')]
    kind=models.CharField(max_length=20,choices=KINDS)
    amount=models.DecimalField(max_digits=24,decimal_places=12)
    description=models.CharField(max_length=240)
    period_start=models.DateField(null=True,blank=True)
    period_end=models.DateField(null=True,blank=True)
    evidence_reference=models.CharField(max_length=240,blank=True)
    job=models.ForeignKey(Job,on_delete=models.PROTECT,null=True,blank=True)
    recorded_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True)
    class Meta:
        constraints=[
            models.UniqueConstraint(fields=['job'],condition=models.Q(kind='absorbed_failure'),name='one_absorbed_failure_per_job'),
            models.UniqueConstraint(fields=['job'],condition=models.Q(kind='absorbed_over_limit'),name='one_over_limit_absorption_per_job'),
            models.CheckConstraint(condition=models.Q(amount__gte=0),name='platform_cost_nonnegative'),
            models.CheckConstraint(condition=models.Q(kind__in=['fixed_overhead','absorbed_failure','absorbed_over_limit']),name='platform_cost_kind_known'),
            models.CheckConstraint(condition=models.Q(kind='fixed_overhead')|models.Q(job__isnull=False),name='absorbed_failure_names_job'),
        ]
