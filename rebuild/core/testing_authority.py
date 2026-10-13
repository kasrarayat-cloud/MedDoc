"""Prospective owner-sponsored synthetic testing; no credits or finite approvals.

Funding authority is distinct from provider evidence and technical bounds. Old
attempts, reservations and wallet ledgers are never relabelled or reset.
"""
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import importlib
import re
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

MODE = 'standing_authority'
AUTHORITY_ID = 'quillmd-standing-testing-20261009-v1'
AUTHORITY_SHA256 = 'eb04bade3d212ebdc06dfc44095f0ba56fecfacd0d3d1dbcec97279865d0a7a5'
KEYS = frozenset(('testing_authority_mode', 'testing_authority_id',
                  'testing_authority_sha256', 'testing_purpose'))
PURPOSES = {'preparation': 'word-template-preparation',
            'generation': 'typed-or-reviewed-voice-generation',
            'transcription': 'reviewed-synthetic-voice-transcription'}
ACTORS = {'71dc60e3-ca1e-40c7-ad49-4a2612ed8d1a': 'd41ad441-987c-4e68-bb0e-b885ec4b642a',
          '2247e403-a830-4807-9a34-6903b95a0f50': '46a5abdd-36f1-41f0-968f-8c09c39d9daa',
          '5f4d1a3d-eeb6-4207-b1df-4597dc696e82': '46a5abdd-36f1-41f0-968f-8c09c39d9daa',
          'e1a20625-455d-4603-a874-794327b19d10': '46a5abdd-36f1-41f0-968f-8c09c39d9daa'}
ACTOR_ENROLLMENT_KEY = 'testing_actor_enrollment'
ACTOR_ENROLLMENT = 'quillmd-actual-clinician-20261010-v1'
ENROLLED_ACTOR = 'e1a20625-455d-4603-a874-794327b19d10'
ACTOR_ENROLLMENTS = {ENROLLED_ACTOR: ACTOR_ENROLLMENT,
    '5f4d1a3d-eeb6-4207-b1df-4597dc696e82': 'quillmd-cedar-clinician-20261013-v1'}
FINITE_KEYS = frozenset(('campaign', 'campaign_scope_sha256', 'campaign_actor_scope_sha256', 'campaign_quote_usd'))
PROVIDER_LOCK = 717844900623  # The same actual-send lock as the retained delivery cohort.
RESERVATION_LOCK = 717844900619
# Actual canonical PostgreSQL trigger definitions, including enabled state,
# destination, events, function and the ledger's exact WHEN predicate.
TRIGGERS = {}
for _name, _table, _events, _function in (
    ('preparation_pilot_guard','core_templatepreparation','INSERT','quillmd_preparation_pilot_guard'),
    ('preparation_send_guard','core_preparationreceipt','INSERT','quillmd_preparation_send_guard'),
    ('preparation_wm_cap_guard','core_preparationreceipt','INSERT','quillmd_preparation_wm_cap_guard'),
    ('standing_job_guard','core_job','INSERT OR UPDATE','quillmd_standing_job_guard'),
    ('testing_reservation_guard','core_testingreservation','INSERT OR DELETE OR UPDATE','quillmd_testing_reservation_guard'),
    ('standing_usage_guard','core_usage','INSERT','quillmd_standing_usage_guard'),
    ('standing_wallet_reservation_guard','core_reservation','INSERT','quillmd_standing_wallet_guard'),
    ('standing_wallet_ledger_guard','core_ledgerentry','INSERT','quillmd_standing_wallet_guard'),
):
    _when = ' WHEN ((new.job_id IS NOT NULL))' if _name == 'standing_wallet_ledger_guard' else ''
    TRIGGERS[_name] = (f'CREATE TRIGGER {_name} BEFORE {_events} ON public.{_table} '
                       f'FOR EACH ROW{_when} EXECUTE FUNCTION {_function}()')


class TestingProviderRefusal(ValidationError):
    """A refusal established before a provider send; never an automatic retry."""


def identity(config):
    if type(config) is not dict:
        raise ValidationError('Provider configuration must be a recorded object.')
    present = KEYS.intersection(config)
    if not present and ACTOR_ENROLLMENT_KEY not in config:
        return None
    if (present != KEYS or FINITE_KEYS.intersection(config)
            or config['testing_authority_mode'] != MODE
            or config['testing_authority_id'] != AUTHORITY_ID
            or config['testing_authority_sha256'] != AUTHORITY_SHA256
            or config['testing_purpose'] not in PURPOSES.values()
            or (ACTOR_ENROLLMENT_KEY in config and config[ACTOR_ENROLLMENT_KEY] not in tuple(ACTOR_ENROLLMENTS.values()))):
        raise ValidationError('Testing configuration differs from the recorded standing authority.')
    return AUTHORITY_ID


def enabled():
    values = (getattr(settings, 'TESTING_AUTHORITY_MODE', ''),
              getattr(settings, 'TESTING_AUTHORITY_ID', ''),
              getattr(settings, 'TESTING_AUTHORITY_SHA256', ''))
    if values == ('', '', ''):
        return False
    if values != (MODE, AUTHORITY_ID, AUTHORITY_SHA256) or not settings.SYNTHETIC_ONLY:
        raise ValidationError('Standing testing activation requires its exact authority and synthetic-only enforcement.')
    return True


def active_config(base, kind):
    identity(base)
    if kind not in PURPOSES:
        raise ValidationError('This request kind is outside standing QuillMD testing.')
    if not enabled():
        if identity(base):
            raise ValidationError('Standing testing authority is not active in this environment.')
        return dict(base)
    if FINITE_KEYS.intersection(base):
        raise ValidationError('A finite approval cannot be reused as a standing testing request.')
    result = {**base, 'testing_authority_mode': MODE, 'testing_authority_id': AUTHORITY_ID,
              'testing_authority_sha256': AUTHORITY_SHA256, 'testing_purpose': PURPOSES[kind]}
    if identity(base) and base['testing_purpose'] != PURPOSES[kind]:
        raise ValidationError('A recorded testing purpose cannot be changed.')
    validate_config(result, kind)
    return result


def validate_config(config, kind):
    if not enabled() or identity(config) != AUTHORITY_ID or config['testing_purpose'] != PURPOSES.get(kind):
        raise ValidationError('This request has no active standing authority for its exact purpose.')
    if (config.get('mode') not in ('live', 'fixture')
            or config.get('provider') not in ('anthropic', 'openai')
            or config.get('provider') != settings.AI_PROVIDER
            or config.get('model') != settings.AI_MODEL):
        raise ValidationError('Standing testing retains the configured authorized provider and model.')


def admit_actor(actor, department_id, config=None):
    if (not settings.SYNTHETIC_ONLY or not getattr(actor, 'is_active', False)
            or ACTORS.get(str(getattr(actor, 'pk', ''))) != str(department_id)):
        raise ValidationError('Standing testing requires its exact authorized synthetic doctor and department.')
    from .security import membership
    membership(actor, department_id, roles=['owner', 'clinician', 'manager'])
    if config is not None:
        if identity(config) != AUTHORITY_ID:
            raise ValidationError('Actor enrollment requires the recorded standing authority.')
        if str(actor.pk) in ACTOR_ENROLLMENTS:
            if config.get(ACTOR_ENROLLMENT_KEY) != ACTOR_ENROLLMENTS[str(actor.pk)]:
                raise ValidationError('This clinician requires a new request with its exact testing enrollment.')
        elif ACTOR_ENROLLMENT_KEY in config:
            raise ValidationError('The clinician enrollment cannot be used by another testing actor.')


def bind_actor_config(config, actor, department_id):
    """Bind only a new request; never relabel a retained preparation or job."""
    admit_actor(actor, department_id)
    if identity(config) != AUTHORITY_ID:
        raise ValidationError('Actor enrollment requires the recorded standing authority.')
    if ACTOR_ENROLLMENT_KEY in config:
        admit_actor(actor, department_id, config)
    result = dict(config)
    if str(actor.pk) in ACTOR_ENROLLMENTS:
        result[ACTOR_ENROLLMENT_KEY] = ACTOR_ENROLLMENTS[str(actor.pk)]
    admit_actor(actor, department_id, result)
    return result


def admit_encounter(actor, encounter):
    """The added clinician sponsors new documents they create in their scope."""
    if (str(getattr(actor, 'pk', '')) in ACTOR_ENROLLMENTS
            and str(encounter.created_by_id) != str(actor.pk)):
        raise ValidationError('Create your own synthetic document from an approved department form before using sponsored testing.')


def quote(value):
    """A conservative accounting estimate, never a funding ceiling."""
    try:
        value = Decimal(str(value))
        if not value.is_finite() or value < 0 or value >= Decimal('1000000000000'):
            raise ValueError()
        return value.quantize(Decimal('0.000000000001'), rounding=ROUND_CEILING)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError('A finite nonnegative provider-cost estimate is required.') from None


def create_preparation(template, actor, config):
    validate_config(config, 'preparation')
    config = bind_actor_config(config, actor, template.department_id)
    if template.format != 'docx':
        raise ValidationError('AI preparation requires an authorized blank Word original.')
    from .models import TemplatePreparation
    return TemplatePreparation.objects.create(template=template, requested_by=actor, config=config)


def reserve_role(prep, role, request_sha256, quoted):
    validate_config(prep.config, 'preparation')
    admit_actor(prep.requested_by, prep.template.department_id, prep.config)
    if role not in ('proposer', 'checker'):
        raise ValidationError('Only the proposer and independent checker are authorized.')
    from .models import PreparationReceipt
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_xact_lock(%s)', [RESERVATION_LOCK])
        if PreparationReceipt.objects.filter(preparation=prep, role=role).exists():
            raise ValidationError('This preparation role already has a retained attempt; it cannot be resent.')
        if role == 'checker' and not PreparationReceipt.objects.filter(
                preparation=prep, role='proposer', state='succeeded').exists():
            raise ValidationError('Independent checking requires the retained successful proposal.')
        return PreparationReceipt.objects.create(preparation=prep, role=role,
            provider=prep.config['provider'], requested_model=prep.config['model'],
            request_sha256=request_sha256, quote_maximum=quote(quoted),
            state='running', started_at=timezone.now())


def job_config(config, kind, actor, department_id, quoted):
    validate_config(config, kind)
    result = bind_actor_config(config, actor, department_id)
    return {**result, 'testing_quote_usd': str(quote(quoted))}


def reserve_job(job, quoted):
    validate_config(job.config, job.kind)
    admit_actor(job.user, job.encounter.department_id, job.config)
    admit_encounter(job.user, job.encounter)
    expected = quote(job.config.get('testing_quote_usd'))
    if quote(quoted) != expected:
        raise ValidationError('The testing request estimate differs from its immutable quote.')
    from .models import TestingReservation
    payer = 'standing:' + AUTHORITY_ID
    if job.payer and job.payer != payer:
        raise ValidationError('Standing testing cannot replace an existing payer.')
    row, created = TestingReservation.objects.get_or_create(job=job, defaults={
        'authority_id': AUTHORITY_ID, 'quoted_provider_cost': expected})
    if row.authority_id != AUTHORITY_ID or row.quoted_provider_cost != expected or row.state != 'held':
        raise ValidationError('The retained testing reservation differs from the request.')
    if not job.payer:
        job.payer = payer
        job.save(update_fields=['payer'])
    if created:
        from .security import audit
        audit(job.user, 'testing.reserve', job.pk, department=job.encounter.department,
              authority_id=AUTHORITY_ID, quoted_provider_cost=str(expected), funding_ceiling=None)
    return row


def admit_job_send(job):
    validate_config(job.config, job.kind)
    admit_actor(job.user, job.encounter.department_id, job.config)
    admit_encounter(job.user, job.encounter)
    from .models import TestingReservation, Reservation
    row = TestingReservation.objects.filter(job=job).first()
    if (row is None or row.state != 'held' or row.authority_id != AUTHORITY_ID
            or row.quoted_provider_cost != quote(job.config.get('testing_quote_usd'))
            or job.payer != 'standing:' + AUTHORITY_ID
            or Reservation.objects.filter(job=job).exists()):
        raise TestingProviderRefusal('No matching active testing reservation exists; nothing was sent.')


def settle_job(job, actual, units, rates, provider, request_id, simulated, resource_id):
    """Provider-metered calculated costs stay separate from any invoice evidence."""
    if identity(job.config) != AUTHORITY_ID:
        raise ValidationError('This job is outside standing testing accounting.')
    from .models import TestingReservation, Usage
    row = TestingReservation.objects.select_for_update().get(job=job)
    if row.state != 'held' or job.payer != 'standing:' + AUTHORITY_ID:
        raise ValidationError('No active immutable testing reservation exists for this job.')
    department = job.encounter.department
    usage = Usage.objects.create(job=job, user=job.user, department=department,
        organization=department.organization, payer=job.payer, provider=provider,
        provider_request_id=request_id, provider_resource_id=resource_id,
        units=units, rates=rates, actual_cost=actual, charged_cost=0, simulated=simulated)
    row.state = 'settled'; row.save(update_fields=['state'])
    from .security import audit
    audit(job.user, 'testing.settle', job.pk, department=department, authority_id=AUTHORITY_ID,
          calculated_provider_cost=str(actual), confirmed_provider_charge=None,
          user_charge='0', simulated=simulated)
    return usage


def release_job(job):
    from .models import TestingReservation
    row = TestingReservation.objects.select_for_update().filter(job=job).first()
    if row is not None and row.state == 'held':
        row.state = 'released'; row.save(update_fields=['state'])
        from .security import audit
        audit(job.user, 'testing.release', job.pk, department=job.encounter.department,
              authority_id=AUTHORITY_ID, quoted_provider_cost=str(row.quoted_provider_cost))


@contextmanager
def provider_slot(config):
    kind = next((key for key, value in PURPOSES.items() if value == config.get('testing_purpose')), None)
    try:
        validate_config(config, kind)
    except ValidationError as exc:
        raise TestingProviderRefusal('Standing testing authority no longer admits this request; nothing was sent.') from exc
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_lock(%s)', [PROVIDER_LOCK])
        acquired = cursor.fetchone()[0]
    if acquired is not True:
        raise TestingProviderRefusal('Another authorized provider request is already in progress; nothing was sent.')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_unlock(%s)', [PROVIDER_LOCK])
            if cursor.fetchone()[0] is not True:
                raise ValidationError('The provider request lock could not be released.')


def runtime_admission(actor, department_id):
    """Read-only installed-control witness; makes no provider request or hold."""
    if not enabled():
        raise ValidationError('Standing authority has not been enabled.')
    admit_actor(actor, department_id)
    witness = bind_actor_config(active_config(
        importlib.import_module('core.generation').configuration(), 'preparation'), actor, department_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*)=3 FROM django_migrations WHERE app='core' AND name IN "
                       "('0024_standing_testing_authority','0025_personal_synthetic_testing_actor','0027_cedar_synthetic_clinician')")
        migrated = cursor.fetchone()[0]
        cursor.execute('SELECT quillmd_standing_config(%s::jsonb)', [
            json.dumps(witness)])
        matched = cursor.fetchone()[0]
        cursor.execute('SELECT quillmd_standing_actor(%s::uuid,%s::uuid,%s::jsonb)',
                       [str(actor.pk), str(department_id), json.dumps(witness)])
        cursor.fetchone()
        cursor.execute('SELECT tgname,tgenabled,pg_get_triggerdef(t.oid) FROM pg_trigger t '
                       'JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace '
                       'WHERE NOT tgisinternal AND n.nspname=%s AND tgname=ANY(%s)', ['public',list(TRIGGERS)])
        guard_rows = cursor.fetchall()
        guards = len(guard_rows)
        guards_match = (guards == len(TRIGGERS) and all(
            enabled == 'O' and definition == TRIGGERS.get(name)
            for name, enabled, definition in guard_rows))
        migration = importlib.import_module('core.migrations.0024_standing_testing_authority')
        pattern = r'CREATE (?:OR REPLACE )?FUNCTION (quillmd_[a-z_]+)\([^)]*\) RETURNS [^$]*?AS \$\$(.*?)\$\$;'
        expected = {name: body for name, body in re.findall(pattern, migration.SQL, re.S)}
        enrollment = importlib.import_module('core.migrations.0025_personal_synthetic_testing_actor')
        expected.update({name: body for name, body in re.findall(pattern, enrollment.SQL, re.S)})
        clinician = importlib.import_module('core.migrations.0027_cedar_synthetic_clinician')
        expected.update({name: body for name, body in re.findall(pattern, clinician.SQL, re.S)})
        previous = importlib.import_module('core.migrations.0023_delivery_campaign')
        expected.update({name: body for name, body in re.findall(pattern, previous.SQL, re.S)
                         if name == 'quillmd_delivery_actor'})
        cursor.execute('SELECT proname,prosrc,prosecdef FROM pg_proc JOIN pg_namespace n ON n.oid=pronamespace '
                       'WHERE n.nspname=%s AND proname=ANY(%s)', ['public', list(expected)])
        rows = cursor.fetchall()
        definitions_match = (len(rows) == len(expected) and all(
            body == expected.get(name) and security_definer is False for name, body, security_definer in rows))
    if migrated is not True or matched is not True or not guards_match or not definitions_match:
        raise ValidationError('Installed standing-authority database controls are incomplete.')
    return {'admitted': True, 'mode': MODE, 'authority_id': AUTHORITY_ID,
            'authority_sha256': AUTHORITY_SHA256, 'monetary_ceiling': None,
            'cumulative_call_ceiling': None, 'wallet_credit_created': False,
            'provider_calls': 0, 'synthetic_only': True, 'database_guards': guards,
            'actor_enrollment': witness.get(ACTOR_ENROLLMENT_KEY),
            'database_function_definitions_verified': len(expected)}
