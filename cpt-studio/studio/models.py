"""Persistent state for CPT Studio. See ARCHITECTURE.md section 4.

Immutable rows refuse updates and deletes through the ORM; a correction is a
new row. Bulk ``QuerySet.update()``/``delete()`` on immutable models is refused
by their manager, so the guard cannot be bypassed by accident.
"""
import uuid

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


DECISION_SEQUENCE = 'studio_decision_sequence'


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(f'{self.model.__name__} rows are immutable; write a new row instead.')

    def delete(self):
        raise ValidationError(f'{self.model.__name__} rows are immutable and cannot be deleted.')


class ImmutableModel(models.Model):
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(f'{type(self).__name__} rows are immutable; write a new row instead.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(f'{type(self).__name__} rows are immutable and cannot be deleted.')


class User(AbstractUser):
    HUMAN, AGENT = 'human', 'agent'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_kind = models.CharField(max_length=8, choices=[(HUMAN, 'Human'), (AGENT, 'Automated agent')], default=HUMAN)
    display_name = models.CharField(max_length=120, blank=True)

    def label(self):
        name = self.display_name or self.get_username()
        if self.actor_kind == self.AGENT:
            return f'{name} (automated agent)'
        return name


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    profiles_version = models.CharField(max_length=40)

    def __str__(self):
        return self.name


class Workspace(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    synthetic_only = models.BooleanField(default=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Membership(models.Model):
    OWNER, REVIEWER, VIEWER = 'owner', 'reviewer', 'viewer'
    ROLES = [(OWNER, 'Owner'), (REVIEWER, 'Reviewer'), (VIEWER, 'Viewer')]
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='memberships')
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name='memberships')
    role = models.CharField(max_length=10, choices=ROLES)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'workspace'], name='one_membership_per_workspace')]

    @property
    def can_review(self):
        return self.active and self.role in {self.OWNER, self.REVIEWER}


class Encounter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name='encounters')
    title = models.CharField(max_length=160)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    current_revision = models.ForeignKey('SourceRevision', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    current_context = models.ForeignKey('EncounterContext', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    current_assessment = models.ForeignKey('Assessment', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    # Encounter metadata supplied by members (service date, setting, billing
    # context). Copied into every EncounterContext snapshot; never clinical facts.
    user_values = models.JSONField(default=dict)
    # A member's Stop. While set, no stage of this encounter starts and nothing is
    # sent; a member action that asks for processing again clears it.
    stopped_at = models.DateTimeField(null=True, blank=True)
    stopped_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    # Derived list state, recomputed by review.refresh_state(); never authoritative.
    state = models.CharField(max_length=32, default='processing')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class SourceFile(ImmutableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='files')
    original_name = models.CharField(max_length=255)
    media_type = models.CharField(max_length=100)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    storage_name = models.CharField(max_length=200, unique=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class SourceRevision(models.Model):
    UPLOAD, PASTE, ADDENDUM = 'upload', 'paste', 'addendum'
    PENDING, OK, PARTIAL, FAILED = 'pending', 'ok', 'partial', 'failed'
    EXTRACTION_FIELDS = ('extraction_status', 'extraction_method', 'text', 'text_sha256', 'pages',
                         'messages', 'ocr_pages', 'engine', 'extracted_at')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='revisions')
    number = models.PositiveIntegerField()
    kind = models.CharField(max_length=10, choices=[(UPLOAD, 'Upload'), (PASTE, 'Pasted text'), (ADDENDUM, 'Addendum')])
    source_file = models.ForeignKey(SourceFile, null=True, blank=True, on_delete=models.PROTECT, related_name='revisions')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    pasted_text = models.TextField(blank=True)  # PASTE: the text exactly as submitted
    addendum_text = models.TextField(blank=True)  # ADDENDUM: the appended documentation as submitted
    answers_clarification = models.ForeignKey('Clarification', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    synthetic_attested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    synthetic_attested_at = models.DateTimeField()
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    # Write-once extraction result: 'pending' until the extract stage records it.
    extraction_status = models.CharField(max_length=10, default=PENDING)
    extraction_method = models.CharField(max_length=20, blank=True)
    text = models.TextField(blank=True)
    text_sha256 = models.CharField(max_length=64, blank=True)
    pages = models.JSONField(default=list)
    messages = models.JSONField(default=list)
    ocr_pages = models.JSONField(default=list)
    engine = models.JSONField(default=dict)
    extracted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['encounter', 'number'], name='one_revision_number')]
        ordering = ['number']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Source revisions are immutable; extraction is recorded once via record_extraction().')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Source revisions cannot be deleted.')

    @classmethod
    def record_extraction(cls, revision_id, **fields):
        """Record the extraction result exactly once (pending -> final)."""
        unknown = set(fields) - set(cls.EXTRACTION_FIELDS)
        if unknown:
            raise ValidationError(f'Not extraction fields: {sorted(unknown)}')
        if fields.get('extraction_status') not in {cls.OK, cls.PARTIAL, cls.FAILED}:
            raise ValidationError('An extraction must finish as ok, partial or failed.')
        changed = models.QuerySet(cls).filter(pk=revision_id, extraction_status=cls.PENDING).update(**fields)
        if changed != 1:
            raise ValidationError('Extraction for this revision was already recorded.')


class EncounterContext(ImmutableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='contexts')
    revision = models.ForeignKey(SourceRevision, on_delete=models.PROTECT, related_name='contexts')
    facts = models.JSONField()  # name -> {value, origin, evidence, note}
    user_values = models.JSONField(default=dict)  # metadata supplied by a member, never clinical facts
    version = models.CharField(max_length=40)
    sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)


class RoutingRun(ImmutableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(SourceRevision, on_delete=models.PROTECT, related_name='routings')
    version = models.CharField(max_length=40)
    result = models.JSONField()
    sha256 = models.CharField(max_length=64)
    # The effective service date the revision was routed for (round 6 pipeline:0): nothing is sent to a provider for a
    # date its revision was never routed for. Null for rows recorded before the field existed.
    service_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ProviderRun(models.Model):
    RESERVED, SENDING, SUCCEEDED, FAILED, UNKNOWN, NOT_SENT, CANCELLED = (
        'reserved', 'sending', 'succeeded', 'failed', 'unknown', 'not_sent', 'cancelled')
    TERMINAL = {SUCCEEDED, FAILED, UNKNOWN, NOT_SENT, CANCELLED}
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='provider_runs')
    revision = models.ForeignKey(SourceRevision, on_delete=models.PROTECT, related_name='provider_runs')
    provider = models.CharField(max_length=20)
    adapter_version = models.CharField(max_length=40)
    request_sha256 = models.CharField(max_length=64)
    request_body = models.JSONField()  # exactly what was (or would be) sent; contains no credentials
    contexts = models.JSONField()
    state = models.CharField(max_length=10, default=RESERVED)
    sent = models.BooleanField(default=False)
    http_status = models.PositiveIntegerField(null=True, blank=True)
    provider_request_id = models.CharField(max_length=120, blank=True)
    response_sha256 = models.CharField(max_length=64, blank=True)  # of the original raw bytes
    response_bytes = models.BinaryField(blank=True, default=bytes)  # the provider's raw bytes, exactly as received
    latency_ms = models.FloatField(null=True, blank=True)
    usage = models.JSONField(default=dict)
    usage_basis = models.CharField(max_length=60, blank=True)
    error = models.TextField(blank=True)
    run_identity = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    authorization_ref = models.CharField(max_length=200, blank=True)
    requested_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    reused_from = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='reuses')
    reconciled_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciliation_note = models.TextField(blank=True)
    # The service date the request was built with (null: none was sent). An
    # assessment pairs a run only with a context carrying this same date.
    service_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['provider', 'adapter_version', 'request_sha256'])]


class Assessment(ImmutableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='assessments')
    revision = models.ForeignKey(SourceRevision, on_delete=models.PROTECT, related_name='assessments')
    context = models.ForeignKey(EncounterContext, on_delete=models.PROTECT, related_name='assessments')
    routing = models.ForeignKey(RoutingRun, on_delete=models.PROTECT, related_name='assessments')
    provider_run = models.ForeignKey(ProviderRun, null=True, blank=True, on_delete=models.PROTECT, related_name='assessments')
    profiles_version = models.CharField(max_length=40)
    engine_version = models.CharField(max_length=40)
    reference_sources = models.JSONField(default=list)
    encounter_checks = models.JSONField(default=list)
    unsupported = models.JSONField(default=list)
    summary = models.JSONField(default=dict)
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class Proposal(ImmutableModel):
    SELECTED, ALTERNATIVE, EXCLUDED = 'selected', 'alternative', 'excluded'
    READY, NEEDS_CLARIFICATION, STATUS_EXCLUDED, INFORMATIONAL = 'ready', 'needs_clarification', 'excluded', 'informational'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name='proposals')
    key = models.CharField(max_length=40)
    bucket = models.CharField(max_length=12)  # selected | alternative | excluded
    code = models.CharField(max_length=10)
    code_kind = models.CharField(max_length=12)
    family = models.CharField(max_length=40)
    profile_version = models.CharField(max_length=40)
    status = models.CharField(max_length=24)
    exclusion_reason = models.TextField(blank=True)
    reinstatable = models.BooleanField(default=False)
    provider_display = models.TextField(blank=True)  # untrusted; diagnostics only
    evidence = models.JSONField(default=list)
    rationale = models.TextField(blank=True)
    checks = models.JSONField(default=list)
    modifier_considerations = models.JSONField(default=list)
    units = models.PositiveIntegerField(default=1)
    fingerprint = models.CharField(max_length=64)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position']
        constraints = [models.UniqueConstraint(fields=['assessment', 'key'], name='one_proposal_key_per_assessment')]


class Clarification(models.Model):
    OPEN, ANSWERED, WITHDRAWN = 'open', 'answered', 'withdrawn'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='clarifications')
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name='clarifications')
    proposal = models.ForeignKey(Proposal, null=True, blank=True, on_delete=models.PROTECT, related_name='clarifications')
    scope = models.CharField(max_length=10)  # encounter | service | proposal
    family = models.CharField(max_length=40, blank=True)
    fact = models.CharField(max_length=40)
    question = models.TextField()
    reason = models.TextField()
    state = models.CharField(max_length=10, default=OPEN)
    answered_by_revision = models.ForeignKey(SourceRevision, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class Decision(ImmutableModel):
    APPROVE, REJECT, REINSTATE, REVOKE, CONFIRM = 'approve', 'reject', 'reinstate', 'revoke', 'confirm'
    ACTIONS = [(APPROVE, 'Approve'), (REJECT, 'Reject'), (REINSTATE, 'Reinstate for review'), (REVOKE, 'Revoke decision'),
               (CONFIRM, 'Confirm exclusion')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='decisions')
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name='decisions')
    revision = models.ForeignKey(SourceRevision, on_delete=models.PROTECT, related_name='decisions')
    proposal = models.ForeignKey(Proposal, on_delete=models.PROTECT, related_name='decisions')
    action = models.CharField(max_length=10, choices=ACTIONS)
    note = models.TextField(blank=True)
    reviewer = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    reviewer_kind = models.CharField(max_length=8)
    acknowledgement = models.TextField(blank=True)
    profile_version = models.CharField(max_length=40)
    proposal_fingerprint = models.CharField(max_length=64)
    carried_from = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='carries')
    # Recording order, assigned by a database sequence at insert. Every writer
    # holds the encounter row lock, so for one encounter a later decision always
    # has a larger number, whatever the wall clock says. created_at is display only.
    sequence = models.BigIntegerField(
        db_default=models.Func(models.Value(DECISION_SEQUENCE), function='nextval'), unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['sequence']


class DecisionInvalidation(ImmutableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    decision = models.OneToOneField(Decision, on_delete=models.PROTECT, related_name='invalidation')
    reason = models.TextField()
    by_revision = models.ForeignKey(SourceRevision, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    by_context = models.ForeignKey(EncounterContext, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)


class Job(models.Model):
    EXTRACT, ANALYZE, PREDICT, ASSESS = 'extract', 'analyze', 'predict', 'assess'
    QUEUED, RUNNING, SUCCEEDED, FAILED, UNKNOWN, CANCELLED = 'queued', 'running', 'succeeded', 'failed', 'unknown', 'cancelled'
    TERMINAL = {SUCCEEDED, FAILED, UNKNOWN, CANCELLED}
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='jobs')
    revision = models.ForeignKey(SourceRevision, on_delete=models.PROTECT, related_name='jobs')
    context = models.ForeignKey(EncounterContext, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    # The provider run an 'assess' job consumes (null: provider disabled or not run).
    provider_run = models.ForeignKey(ProviderRun, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    kind = models.CharField(max_length=10)
    idempotency_key = models.CharField(max_length=200, unique=True)
    state = models.CharField(max_length=10, default=QUEUED)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=1)
    deadline_at = models.DateTimeField()
    requested_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    stop_requested_at = models.DateTimeField(null=True, blank=True)
    stop_requested_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    error = models.TextField(blank=True)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [models.Index(fields=['state', 'created_at'])]


class ReportArtifact(ImmutableModel):
    DRAFT, REVIEWED = 'draft', 'reviewed'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='reports')
    assessment = models.ForeignKey(Assessment, on_delete=models.PROTECT, related_name='reports')
    kind = models.CharField(max_length=10)
    fmt = models.CharField(max_length=4)
    filename = models.CharField(max_length=200)
    content = models.BinaryField()
    sha256 = models.CharField(max_length=64)
    snapshot_sha256 = models.CharField(max_length=64)
    generated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    generated_at = models.DateTimeField(auto_now_add=True)


class AuditEvent(ImmutableModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(Workspace, on_delete=models.PROTECT, related_name='audit_events')
    encounter = models.ForeignKey(Encounter, null=True, blank=True, on_delete=models.PROTECT, related_name='audit_events')
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    actor_kind = models.CharField(max_length=8)  # human | agent | system
    event = models.CharField(max_length=60)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class ReferenceSource(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=60, unique=True)
    kind = models.CharField(max_length=40)  # cms-pfs | cms-mue-practitioner
    publisher = models.CharField(max_length=120)
    title = models.CharField(max_length=200)
    release = models.CharField(max_length=60)
    url = models.URLField(max_length=400)
    sha256 = models.CharField(max_length=64)
    retrieved_at = models.DateTimeField()
    effective_start = models.DateField()
    effective_end = models.DateField()
    license_note = models.TextField()
    scope_note = models.TextField()
    row_count = models.PositiveIntegerField(default=0)
    loaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(effective_start__lte=models.F('effective_end')), name='reference_window_ordered')]


class ReferenceCodeFact(models.Model):
    id = models.BigAutoField(primary_key=True)
    source = models.ForeignKey(ReferenceSource, on_delete=models.PROTECT, related_name='facts')
    code = models.CharField(max_length=10)
    modifier = models.CharField(max_length=4, blank=True)
    facts = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'code', 'modifier'], name='one_fact_row_per_code_modifier')]
        indexes = [models.Index(fields=['code'])]


class LoginAttempt(models.Model):
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=150)
    client = models.CharField(max_length=64)
    succeeded = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['username', 'client', 'created_at'])]
