"""A distinct, finite delivery cohort; the original Word pilot stays closed.

The immutable discriminator lives in the existing configuration snapshot. No
historical preparation, approval, response or unknown reservation is rewritten.
The PostgreSQL migration independently enforces the same finite bounds.
"""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction

CAMPAIGN = 'word-milestone-delivery-20261008-v1'
SCOPE_SHA256 = 'fe387adcfb7f9397a7c54c342270063f9fc7f6cdd45b357e6ab16e47d16670c8'
ACTOR_SCOPE_SHA256 = 'd37378667422a1d36c5559dec32475af8435f822bfbb2c01eba4e6ac420fd77b'
ACTORS = {
    '71dc60e3-ca1e-40c7-ad49-4a2612ed8d1a': 'd41ad441-987c-4e68-bb0e-b885ec4b642a',
    '2247e403-a830-4807-9a34-6903b95a0f50': '46a5abdd-36f1-41f0-968f-8c09c39d9daa',
}
FORM_LIMITS = {
    'b2b78348f8735bddb75433d7b0cd720d1a0f416c1fbae7ac51b896fbf0fa5193': Decimal('0.10'),
    'a2a70a3b087077e55401030fd9a592958d0064402a3b12d107b132f563111102': Decimal('0.10'),
    'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b': Decimal('0.16'),
}
TOTAL_LIMIT = Decimal('1.75')
JOB_QUOTE_LIMIT = Decimal('0.20')
JOB_LIMITS = {'generation': 3, 'transcription': 1}
DISCRIMINATORS = frozenset(('campaign', 'campaign_scope_sha256', 'campaign_actor_scope_sha256'))
RESERVATION_LOCK = 717844900619  # Shared with the retained pilot's SQL guards.
PROVIDER_LOCK = 717844900623


class CampaignProviderRefusal(ValidationError):
    """A local admission refusal established before a provider send."""


def campaign_identity(config):
    """None is legacy; a partial, null or unknown discriminator is refused."""
    if not isinstance(config, dict):
        raise ValidationError('Provider configuration must be a recorded object.')
    present = DISCRIMINATORS.intersection(config)
    if not present:
        return None
    if (present != DISCRIMINATORS or config['campaign'] != CAMPAIGN
            or config['campaign_scope_sha256'] != SCOPE_SHA256
            or config['campaign_actor_scope_sha256'] != ACTOR_SCOPE_SHA256):
        raise ValidationError('The delivery campaign does not match its recorded authority.')
    return CAMPAIGN


def active_campaign_config(base, source_sha256=None):
    """Explicit opt-in only; forms and authority are fixed, never env-provided caps."""
    result = dict(base)
    campaign_identity(result)
    name = getattr(settings, 'WORD_PREPARATION_CAMPAIGN', '')
    scope = getattr(settings, 'WORD_PREPARATION_CAMPAIGN_SCOPE_SHA256', '')
    if not name and not scope:
        if campaign_identity(result) is not None:
            raise ValidationError('This environment has not enabled the delivery campaign.')
        return result
    if name != CAMPAIGN or scope != SCOPE_SHA256:
        raise ValidationError('Delivery campaign activation does not match the exact scope.')
    if not settings.SYNTHETIC_ONLY:
        raise ValidationError('The delivery campaign requires synthetic-only enforcement.')
    if source_sha256 is not None and source_sha256 not in FORM_LIMITS:
        raise ValidationError('This original is outside the three recorded delivery forms.')
    result.update(campaign=CAMPAIGN, campaign_scope_sha256=SCOPE_SHA256,
                  campaign_actor_scope_sha256=ACTOR_SCOPE_SHA256)
    return result


def legacy_preparations(queryset):
    """Preserve the legacy 8/14 limits without counting the separate campaign."""
    for key in DISCRIMINATORS:
        queryset = queryset.exclude(**{'config__has_key': key})
    return queryset


def legacy_receipts(queryset):
    for key in DISCRIMINATORS:
        queryset = queryset.exclude(**{'preparation__config__has_key': key})
    return queryset


def _lock():
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [RESERVATION_LOCK])


def _preparations():
    from .models import TemplatePreparation
    return TemplatePreparation.objects.filter(config__campaign=CAMPAIGN)


def _receipts():
    from .models import PreparationReceipt
    return PreparationReceipt.objects.filter(preparation__config__campaign=CAMPAIGN)


def exposure():
    """Keep every reservation, even after failure or an unknown response.

    Actual cost above the quote also remains visible and consumes exposure.
    Clinical jobs reserve their fixed campaign quote before any provider send.
    """
    from .models import Job, ProviderReceipt
    total = sum((max(quote, actual if actual is not None else quote)
                 for quote, actual in _receipts().values_list('quote_maximum', 'computed_cost')), Decimal('0'))
    jobs = Job.objects.filter(config__campaign=CAMPAIGN)
    costs = dict(ProviderReceipt.objects.filter(job__config__campaign=CAMPAIGN).values_list('job_id', 'actual_cost'))
    for identifier, config in jobs.values_list('id', 'config'):
        campaign_identity(config)
        quote = _job_quote(config)
        total += max(quote, costs.get(identifier, quote))
    return total


def _admit_quote(quote):
    if exposure() + quote > TOTAL_LIMIT:
        raise ValidationError('The delivery campaign computed or reserved exposure is exhausted.')


def create_campaign_preparation(template, actor, config):
    active_campaign_config(config, template.sha256)
    if campaign_identity(config) != CAMPAIGN or template.sha256 not in FORM_LIMITS:
        raise ValidationError('This preparation is outside the exact delivery campaign.')
    admit_actor(actor, template.department_id)
    from .models import TemplatePreparation
    with transaction.atomic():
        _lock()
        rows = _preparations()
        if rows.count() >= 3 or rows.filter(template__sha256=template.sha256).exists():
            raise ValidationError('The delivery campaign allows one attempt for each of its three originals.')
        return TemplatePreparation.objects.create(template=template, requested_by=actor, config=config)


def reserve_campaign_role(prep, role, request_sha256, limit):
    active_campaign_config(prep.config, prep.template.sha256)
    if (campaign_identity(prep.config) != CAMPAIGN or role not in ('proposer', 'checker')
            or prep.template.sha256 not in FORM_LIMITS or limit != FORM_LIMITS[prep.template.sha256]):
        raise ValidationError('This preparation role is outside the exact delivery scope.')
    admit_actor(prep.requested_by, prep.template.department_id)
    from .models import PreparationReceipt
    with transaction.atomic():
        _lock()
        if _receipts().count() >= 6:
            raise ValidationError('The delivery campaign preparation sends are exhausted.')
        if PreparationReceipt.objects.filter(preparation=prep, role=role).exists():
            raise ValidationError('A preparation role cannot be reserved or sent twice.')
        if role == 'checker' and not PreparationReceipt.objects.filter(
                preparation=prep, role='proposer', state='succeeded').exists():
            raise ValidationError('Independent checking requires the retained successful proposal.')
        quote = limit if prep.config['mode'] == 'live' else Decimal('0')
        _admit_quote(quote)
        from django.utils import timezone
        return PreparationReceipt.objects.create(preparation=prep, role=role,
            provider=prep.config['provider'], requested_model=prep.config['model'],
            request_sha256=request_sha256, quote_maximum=quote, state='running', started_at=timezone.now())


def _job_quote(config):
    try:
        value = Decimal(config.get('campaign_quote_usd', ''))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError('The campaign job needs its immutable exposure reservation.') from None
    if not value.is_finite() or value != JOB_QUOTE_LIMIT:
        raise ValidationError('The campaign job exposure reservation must be exactly $0.20.')
    return value


def campaign_job_config(base, kind):
    if kind not in JOB_LIMITS:
        raise ValidationError('This job kind is outside the delivery campaign.')
    result = active_campaign_config(base)
    if campaign_identity(result) is not None:
        result['campaign_quote_usd'] = str(JOB_QUOTE_LIMIT)
    return result


def admit_actor(actor, department_id):
    if (not settings.SYNTHETIC_ONLY or not getattr(actor, 'is_active', False)
            or ACTORS.get(str(actor.pk)) != str(department_id)):
        raise ValidationError('The campaign requires its exact synthetic doctor and department.')
    from .security import membership
    membership(actor, department_id, roles=['owner', 'clinician', 'manager'])


def admit_campaign_job(config, kind, actor=None, department_id=None):
    """Call inside enqueue's transaction immediately before Job insertion."""
    if campaign_identity(config) is None:
        return
    active_campaign_config(config)
    if kind not in JOB_LIMITS:
        raise ValidationError('This job kind is outside the delivery campaign.')
    admit_actor(actor, department_id)
    quote = _job_quote(config)
    if not connection.in_atomic_block:
        raise ValidationError('Campaign job admission requires the reservation transaction.')
    _lock()
    from .models import Job
    if Job.objects.filter(config__campaign=CAMPAIGN, kind=kind).count() >= JOB_LIMITS[kind]:
        raise ValidationError('The delivery campaign clinical request count is exhausted.')
    _admit_quote(quote)


@contextmanager
def provider_slot(config):
    """One eligible campaign provider request at a time across both workers.

    Session advisory locks cover the actual request, not just the reservation.
    Failure to acquire refuses immediately; it cannot silently retry a send.
    """
    if campaign_identity(config) is None:
        yield
        return
    active_campaign_config(config)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [PROVIDER_LOCK])
        acquired = cursor.fetchone()[0]
    if acquired is not True:
        raise CampaignProviderRefusal('Another campaign provider request is already in progress.')
    try:
        # Reservations may predate an actual overrun. Recheck at the send,
        # with the provider slot held through durable response accounting.
        with transaction.atomic():
            _lock()
            if exposure() > TOTAL_LIMIT:
                raise CampaignProviderRefusal('The delivery campaign exposure is exhausted before this request was sent.')
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [PROVIDER_LOCK])
            if cursor.fetchone()[0] is not True:
                raise ValidationError('The provider request lock could not be released.')
