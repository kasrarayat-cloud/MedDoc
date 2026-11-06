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


class UniqueIndex(models.Index):
    """A UNIQUE index, added by AddIndex (P5 FLOW, 2026-11-03). Django's Index has no unique form and a UniqueConstraint
    is an AddConstraint, which the installer's migration gate refuses on an existing table (ops/install.py
    migration_verdict: it can refuse an older revision's rows). Used only as a partial index over a column no older
    revision writes (its rows hold NULL there, and NULL is outside the index), so no older revision's insert or update is
    ever refused by it."""
    UNIQUE_SQL = 'CREATE UNIQUE INDEX %(name)s ON %(table)s (%(columns)s)%(include)s%(condition)s'

    def create_sql(self, model, schema_editor, using='', **kwargs):
        kwargs['sql'] = self.UNIQUE_SQL
        return super().create_sql(model, schema_editor, using=using, **kwargs)


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
    # The upload attempt's key the page generated (P5 FLOW, 2026-11-03): a repeated POST of the same attempt by the same
    # member answers with this encounter instead of making a second one (intake.find_upload). Null for rows made before
    # it existed and for uploads that sent none; unique per member where set.
    client_key = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [UniqueIndex(fields=['created_by', 'client_key'], condition=Q(client_key__isnull=False),
                               name='studio_enc_upload_key_uniq')]


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
    # The document's own service date fact BEFORE a member's value is merged in (gi.context.document_service_date_fact,
    # P5 FLOW), recorded when the context is made, so a screen can show the document's date beside the one a member
    # entered without reading the note's prose. Outside ``sha256``. Null for contexts made before it existed.
    document_date = models.JSONField(null=True, blank=True)


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
    # 'primary': the revision's whole text; 'second_review': one bounded second request about documented services that
    # had no supported proposal, sent once per revision and service date (ARCHITECTURE 5.11). ``scope`` records what it
    # was for: the excerpt's offsets in the revision text and the unresolved items.
    # 'independent': a harness participant's (Astra, Fable) own reading of the revision (HARNESS.md 2), never Corti's.
    # 'peer_review': its phase-2 run, made after every first assessment was frozen (HARNESS.md 11.1)
    PRIMARY, SECOND_REVIEW, INDEPENDENT, PEER_REVIEW = 'primary', 'second_review', 'independent', 'peer_review'
    # scope['held'] of a run deliberately not sent: the service date is a member-vs-document conflict (jobs.stage_predict)
    HELD_MEMBER_DATE_CONFLICT = 'member_date_conflict'
    purpose = models.CharField(max_length=16, default=PRIMARY)
    scope = models.JSONField(default=dict, blank=True)
    # What was actually called and what answered (HARNESS.md 6); '' on rows recorded before the harness, and the models
    # are '' for Corti, whose API names none. response_id is the vendor's own object id (resp_..., msg_...).
    endpoint = models.CharField(max_length=200, blank=True, default='')
    requested_model = models.CharField(max_length=100, blank=True, default='')
    returned_model = models.CharField(max_length=100, blank=True, default='')
    response_id = models.CharField(max_length=140, blank=True, default='')
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
    # The bounded second review whose proposals this assessment also read (null: none).
    second_run = models.ForeignKey(ProviderRun, null=True, blank=True, on_delete=models.PROTECT,
                                   related_name='second_assessments')
    profiles_version = models.CharField(max_length=40)
    engine_version = models.CharField(max_length=40)
    reference_sources = models.JSONField(default=list)
    encounter_checks = models.JSONField(default=list)
    unsupported = models.JSONField(default=list)
    summary = models.JSONField(default=dict)
    services = models.JSONField(default=dict)  # the documented-service inventory (gi/services.py)
    completeness = models.JSONField(default=dict)  # coding completeness, unresolved and bundled items (reconcile.py)
    # HARNESS.md 6: one entry per harness participant (state, run, models, refusal reason, unverified quotes) and the
    # reference retrieval traces. Both are recorded beside the engine's result, outside its sha256, so an assessment with
    # no participant configured is the engine's result exactly (I1). Neither decides whether an identical re-assessment
    # is the recorded one: _same_assessment reads only the participant runs the entries name (HARNESS.md 9, I1).
    participants = models.JSONField(default=list)
    retrieval = models.JSONField(default=list)
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
    support = models.JSONField(default=dict)  # the documented service and act it was matched to, and passage support

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
    # Completion repair (2026-11-06, U11): the member's answer this question was closed with (state ANSWERED) - by the
    # assessment that read the answer (engine._MemberAnswers), and on the assessment whose question the member answered.
    # Null for any other state, and for a question an addendum answered (answered_by_revision). Nullable, so a row an
    # older release inserts leaves it NULL (ops/install.py migration_verdict).
    answer = models.ForeignKey('MemberAnswer', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class FindingConfirmation(ImmutableModel):
    """A reviewer-confirmed answer to an open question (HARNESS.md 11.3): the passage a participant located, accepted by
    an owner or reviewer with an attestation. Append-only and bound to its revision: a new revision's assessment never
    reads it. The service date never comes this way (it enters through the context as the member's date)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='finding_confirmations')
    revision = models.ForeignKey(SourceRevision, on_delete=models.PROTECT, related_name='finding_confirmations')
    clarification = models.ForeignKey(Clarification, on_delete=models.PROTECT, related_name='confirmations')
    scope = models.CharField(max_length=12)  # service | proposal
    fact = models.CharField(max_length=40)
    family = models.CharField(max_length=40)
    proposal_key = models.CharField(max_length=40, blank=True)
    value = models.CharField(max_length=200)
    spans = models.JSONField()  # [{start, end, text, page}]: exact slices of the revision text
    located_by = models.JSONField(default=list)  # the participants whose quote it was
    runs = models.JSONField(default=list)  # their run ids
    confirmed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    attestation = models.TextField()
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
    # CORE-UX-DESIGN.md 4 (P3): the reviewer's ONE chosen modifier on an approval ('59' or 'XS'), only where the review
    # overlay offers a separate-lesion modifier review (review.record_decision); [] otherwise. Never prefilled, never
    # both, never a free list. Carried with the decision (review._carry_decisions).
    modifiers = models.JSONField(default=list)
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


class MemberAnswer(ImmutableModel):
    """A member's answer to a detail CPT Studio asked (directive section 4; P5 FLOW, 2026-11-03): that it is not
    documented, or that the member cannot confirm it. Bound to its revision and to the question it answered - the code,
    family and fact it was asked of and that question's fingerprint (``question``; studio.validation.questions) - never to
    a clarification row or a proposal key, which every re-assessment makes anew. A later assessment applies it only
    where it asks the same question (completion repair 2026-11-06, U11); otherwise it is kept and shown as an earlier
    answer. It is what a member said, never clinical documentation: it never enters the document text, a provider request
    or an addendum, and it approves nothing. Append-only; a MemberAnswerRevocation withdraws it."""
    NOT_DOCUMENTED, CANNOT_CONFIRM = 'not_documented', 'cannot_confirm'
    VALUES = [(NOT_DOCUMENTED, 'Not documented'), (CANNOT_CONFIRM, 'Cannot confirm')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.ForeignKey(Encounter, on_delete=models.PROTECT, related_name='member_answers')
    revision = models.ForeignKey(SourceRevision, on_delete=models.PROTECT, related_name='member_answers')
    # the assessment whose question the member answered (provenance: the answer binds to the question it answered)
    assessment = models.ForeignKey('Assessment', on_delete=models.PROTECT, related_name='+')
    fact = models.CharField(max_length=40)
    family = models.CharField(max_length=40, blank=True)
    code = models.CharField(max_length=10, blank=True)
    value = models.CharField(max_length=20, choices=VALUES)
    # Completion repair (2026-11-06, U11): the fingerprint of the question answered (questions.fingerprint, 64 hex). ''
    # for an answer recorded before answers carried one - given to the earlier form of the question, which showed no
    # passage - which answers no question asked now (questions.EARLIER_FORM). The database default keeps a row an older
    # release inserts valid (ops/install.py migration_verdict).
    question = models.CharField(max_length=64, blank=True, default='', db_default='')
    answered_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    answered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['answered_at']


class MemberAnswerRevocation(ImmutableModel):
    """A member's answer withdrawn: by the member ('withdrawn'), or by a later answer to the same detail
    ('superseded'), so at most one answer to a detail ever stands and a withdrawn one is never resurrected."""
    WITHDRAWN, SUPERSEDED = 'withdrawn', 'superseded'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    answer = models.OneToOneField(MemberAnswer, on_delete=models.PROTECT, related_name='revocation')
    reason = models.CharField(max_length=12, choices=[(WITHDRAWN, 'Withdrawn'), (SUPERSEDED, 'Superseded')])
    revoked_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='+')
    revoked_at = models.DateTimeField(auto_now_add=True)


class Job(models.Model):
    EXTRACT, ANALYZE, PREDICT, ASSESS, REVIEW2 = 'extract', 'analyze', 'predict', 'assess', 'review2'
    ASTRA, FABLE = 'astra', 'fable'  # the harness participants' stages (HARNESS.md 2), run after predict
    PARTICIPANT_KINDS = (ASTRA, FABLE)
    # harness@2 (HARNESS.md 11.1): each participant's peer review, after every first assessment is frozen
    ASTRA_PEER, FABLE_PEER = 'astra_peer', 'fable_peer'
    PEER_KINDS = (ASTRA_PEER, FABLE_PEER)
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
    # A customer report's approved export (cpt-studio-customer-report@1): approved items only (CORE-UX-DESIGN.md 5).
    APPROVED = 'approved'
    # Who an artifact is for. Every row recorded before this column existed names the review participants, so the
    # database default makes it an operator artifact without an ORM update (ImmutableModel is never involved), and a row
    # an older release inserts during a rollback is an operator artifact too (the safe direction). Customers download
    # only customer artifacts; operators download any, as stored.
    OPERATOR, CUSTOMER = 'operator', 'customer'
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
    audience = models.CharField(max_length=10, default=OPERATOR, db_default=OPERATOR)


class OperatorGrant(ImmutableModel):
    """A platform-operator grant (CORE-UX-DESIGN.md 5): the only thing that opens the operator diagnostics at /ops/. Held
    by a user, never conferred by a workspace role - a practice owner gains nothing from it. Append-only: recorded by
    the ``grant_operator`` management command (never over HTTP), ended by an OperatorRevocation row."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='operator_grants')
    reason = models.TextField()
    granted_by = models.CharField(max_length=120)  # the label of whoever ran the command (its own words)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']


class OperatorRevocation(ImmutableModel):
    """The end of one OperatorGrant, recorded by the ``revoke_operator`` management command; the grant row stays."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grant = models.OneToOneField(OperatorGrant, on_delete=models.PROTECT, related_name='revocation')
    reason = models.TextField()
    revoked_by = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)


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


class ProviderExchange(models.Model):
    """One HTTP exchange of a participant run's tool loop (HARNESS.md 11.2): what was sent (stored form; a PDF original
    is named by sha256, never its bytes), what came back, exactly. A run's own request and response fields hold its first
    request and its final response; every turn is here."""
    id = models.BigAutoField(primary_key=True)
    run = models.ForeignKey(ProviderRun, on_delete=models.PROTECT, related_name='exchanges')
    turn = models.PositiveSmallIntegerField()  # 1-based
    request_body = models.JSONField()
    request_sha256 = models.CharField(max_length=64)
    state = models.CharField(max_length=10)  # succeeded | failed | unknown | not_sent
    http_status = models.PositiveIntegerField(null=True, blank=True)
    response_bytes = models.BinaryField(blank=True, default=bytes)
    response_sha256 = models.CharField(max_length=64, blank=True)
    latency_ms = models.FloatField(null=True, blank=True)
    usage = models.JSONField(default=dict)
    provider_request_id = models.CharField(max_length=120, blank=True)
    response_id = models.CharField(max_length=140, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['run', 'turn']
        constraints = [models.UniqueConstraint(fields=['run', 'turn'], name='one_exchange_per_run_turn')]


class ToolCall(models.Model):
    """A reference tool call a participant made, as CPT Studio executed it (HARNESS.md 11.2): the tool trace. ``refs``
    lists every reference the result returned (passage keys and 'fact:<source>:<code>:<field>' refs), each dated by its
    source in ``result``; a participant's references_used is checked against these."""
    id = models.BigAutoField(primary_key=True)
    exchange = models.ForeignKey(ProviderExchange, on_delete=models.PROTECT, related_name='tool_calls')
    call_id = models.CharField(max_length=120)
    tool = models.CharField(max_length=40)
    arguments = models.JSONField()
    result = models.JSONField()
    result_sha256 = models.CharField(max_length=64)
    refs = models.JSONField(default=list)
    executed_at = models.DateTimeField()

    class Meta:
        ordering = ['exchange', 'id']
        constraints = [models.UniqueConstraint(fields=['exchange', 'call_id'], name='one_tool_call_per_exchange_id')]


class PassageSource(models.Model):
    """A CMS document whose verbatim passages the harness retrieves (HARNESS.md 5). Kept apart from ReferenceSource,
    whose rows every lookup lists, so importing passages never changes an assessment's reference-source entries."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.CharField(max_length=60, unique=True)
    kind = models.CharField(max_length=40)  # cms-pfs-documentation | cms-ncci-policy-manual | cms-claims-manual
    publisher = models.CharField(max_length=120)
    title = models.CharField(max_length=200)
    release = models.CharField(max_length=60)
    url = models.URLField(max_length=400)
    sha256 = models.CharField(max_length=64)  # of the publisher's file the passages were read from
    retrieved_at = models.DateTimeField()
    effective_start = models.DateField()
    effective_end = models.DateField()
    license_note = models.TextField()
    scope_note = models.TextField()
    passage_count = models.PositiveIntegerField(default=0)
    loaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(effective_start__lte=models.F('effective_end')),
                                              name='passage_window_ordered')]


class ReferencePassage(models.Model):
    """One verbatim passage of a PassageSource, with where it is (page, section) and the rule it states, keyed by what
    retrieval matches it on (topic, e.g. 'pfs.mult_proc' with value '3')."""
    id = models.BigAutoField(primary_key=True)
    source = models.ForeignKey(PassageSource, on_delete=models.PROTECT, related_name='passages')
    passage_key = models.CharField(max_length=80)
    section = models.CharField(max_length=200)
    page = models.CharField(max_length=20, blank=True)
    topic = models.CharField(max_length=60)
    topic_value = models.CharField(max_length=20, blank=True)
    text = models.TextField()
    sha256 = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source', 'passage_key'], name='one_passage_key_per_source')]
        indexes = [models.Index(fields=['topic', 'topic_value'])]


class LoginAttempt(models.Model):
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=150)
    client = models.CharField(max_length=64)
    succeeded = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['username', 'client', 'created_at'])]


class WorkerBeat(models.Model):
    """Decision (j) of the core repair (2026-11-03): the worker process's heartbeat - one row per worker name, written
    every jobs.HEARTBEAT_SECONDS by a thread of the worker process (jobs.start_heartbeat), so it says whether a worker
    is alive, not whether its loop is between stages. The progress panel reads it (jobs.worker_responding): while a
    document waits on processing and the newest beat is older than jobs.WORKER_SILENT_SECONDS, it says processing is
    paused and does not animate. No row at all is never read as a dead worker (nothing is known)."""
    name = models.CharField(primary_key=True, max_length=20)
    beat_at = models.DateTimeField()
    revision = models.CharField(max_length=64, blank=True)
    pid = models.PositiveIntegerField(null=True, blank=True)
