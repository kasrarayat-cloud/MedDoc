import uuid
from decimal import Decimal
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.core.exceptions import ValidationError

class User(AbstractUser):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    email=models.EmailField(unique=True)
    verified_at=models.DateTimeField(null=True,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(Lower('email'),name='unique_email_casefold')]
    def __str__(self): return self.email

class Entity(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: abstract=True

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
    created_by=models.ForeignKey(User,on_delete=models.PROTECT)
    class Meta: constraints=[models.UniqueConstraint(fields=['template','number'],name='mapping_version_unique')]
    def __str__(self): return f'{self.template.name} · mapping {self.number}'
class Encounter(Entity):
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    patient=models.ForeignKey(Patient,on_delete=models.PROTECT)
    template_version=models.ForeignKey(TemplateVersion,on_delete=models.PROTECT)
    created_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name='encounters')
    notes=models.TextField()
    answers=models.JSONField(default=dict)
    status=models.CharField(max_length=16,default='draft')
    revision=models.PositiveIntegerField(default=0)
    finalized_at=models.DateTimeField(null=True)
    finalized_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,related_name='finalized_encounters')
    export_path=models.CharField(max_length=100,blank=True)
    export_sha256=models.CharField(max_length=64,blank=True)
    def clean(self):
        if self.patient.department_id!=self.department_id or self.template_version.template.department_id!=self.department_id: raise ValidationError('Patient, template and encounter must share a department.')
class Job(Entity):
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
    error=models.CharField(max_length=250,blank=True)
    input_path=models.CharField(max_length=100,blank=True)
    started_at=models.DateTimeField(null=True)
    finished_at=models.DateTimeField(null=True)
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
class Usage(Entity):
    job=models.OneToOneField(Job,on_delete=models.PROTECT)
    user=models.ForeignKey(User,on_delete=models.PROTECT)
    department=models.ForeignKey(Department,on_delete=models.PROTECT)
    organization=models.ForeignKey(Organization,on_delete=models.PROTECT)
    payer=models.CharField(max_length=100)
    provider=models.CharField(max_length=80)
    provider_request_id=models.CharField(max_length=140,blank=True)
    units=models.JSONField(default=dict)
    rates=models.JSONField(default=dict)
    actual_cost=models.DecimalField(max_digits=24,decimal_places=12)
    charged_cost=models.DecimalField(max_digits=24,decimal_places=12)
    simulated=models.BooleanField(default=False)
    class Meta: constraints=[models.CheckConstraint(condition=models.Q(actual_cost__gte=0,charged_cost__gte=0)&models.Q(charged_cost=models.F('actual_cost')*Decimal('1.5')),name='exact_usage_multiplier')]
class Payment(Entity):
    user=models.ForeignKey(User,on_delete=models.PROTECT)
    wallet=models.ForeignKey(Wallet,on_delete=models.PROTECT)
    amount_cents=models.PositiveIntegerField()
    stripe_session=models.CharField(max_length=200,unique=True,null=True)
    stripe_intent=models.CharField(max_length=200,unique=True,null=True)
    status=models.CharField(max_length=20,default='pending')
class WebhookEvent(Entity):
    event_id=models.CharField(max_length=180,unique=True)
    kind=models.CharField(max_length=80)
    payload_hash=models.CharField(max_length=64)
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

class ProviderReceipt(Entity):
    job=models.OneToOneField(Job,on_delete=models.PROTECT)
    provider=models.CharField(max_length=80)
    provider_request_id=models.CharField(max_length=140,blank=True)
    actual_cost=models.DecimalField(max_digits=24,decimal_places=12)
    units=models.JSONField(default=dict)
    rates=models.JSONField(default=dict)
    simulated=models.BooleanField(default=False)
    result_path=models.CharField(max_length=100,blank=True)
    result_sha256=models.CharField(max_length=64,blank=True)
