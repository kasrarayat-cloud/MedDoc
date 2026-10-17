"""Versioned, bounded source assessments for selected synthetic API output.

No catalogue entitlement or clinician approval is created here. Historical
assessments are selected unchanged so an existing saved decision keeps its exact
review digest and export bytes when a prospective assessment is installed.
"""
from datetime import date
import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_aware

LEGACY_CONTRACT = 'synthetic-api-output-reference-v2'
CONTRACT = 'synthetic-api-output-reference-v3'


def need(condition, message):
    if not condition:
        raise ValidationError(message)


def legacy_scope(bundle, encounter, run):
    scope = bundle.get('scope', {})
    return (type(scope) is dict and str(encounter.created_by_id) in scope.get('actor_ids', [])
        and str(run.user_id) in scope.get('actor_ids', [])
        and hashlib.sha256(encounter.notes.encode()).hexdigest() in scope.get('notes_sha256', [])
        and encounter.service_date.isoformat() in scope.get('service_dates', []))


def load(encounter, run):
    path = getattr(settings, 'CORTI_OUTPUT_REFERENCE_FILE', '')
    need(getattr(settings, 'SYNTHETIC_ONLY', False) and path,
         'No dated synthetic output reference is installed.')
    try:
        raw = Path(path).read_bytes()
        need(hashlib.sha256(raw).hexdigest() == getattr(settings, 'CORTI_OUTPUT_REFERENCE_SHA256', ''),
             'The synthetic output reference failed its integrity check.')
        bundle = json.loads(raw)
    except (OSError, ValueError, TypeError) as exc:
        raise ValidationError('The dated synthetic output reference is unavailable.') from exc
    need(type(bundle) is dict and bundle.get('contract') in (LEGACY_CONTRACT, CONTRACT),
         'Unknown synthetic output reference contract.')
    if bundle['contract'] == CONTRACT:
        legacy = bundle.get('preserved_references', [])
        need(type(legacy) is list and all(type(item) is dict and item.get('contract') == LEGACY_CONTRACT
                                        for item in legacy), 'Invalid preserved output references.')
        matches = [item for item in legacy if legacy_scope(item, encounter, run)]
        need(len(matches) <= 1, 'Overlapping historical output reference scopes.')
        if matches:
            return matches[0], matches[0]['scope']['actor_ids']
        from .coding_dispatch import AUTHORIZED_SYNTHETIC_SCOPE, authorized_synthetic_actor
        scope = bundle.get('scope', {})
        need(type(scope) is dict and scope.get('actor_policy') == AUTHORIZED_SYNTHETIC_SCOPE,
             'The prospective output assessment has no authorized synthetic clinical scope.')
        cutoff = parse_datetime(scope.get('encounters_created_since', ''))
        try:
            first, last = (date.fromisoformat(scope.get(key, ''))
                           for key in ('service_date_from', 'service_date_until'))
        except (ValueError, TypeError) as exc:
            raise ValidationError('The output assessment has no bounded service-date interval.') from exc
        need(cutoff and is_aware(cutoff) and encounter.created_at and encounter.created_at >= cutoff
             and first <= encounter.service_date <= last,
             'This encounter is outside the prospective dated output assessment.')
        need(authorized_synthetic_actor(encounter.created_by, encounter.department_id)
             and authorized_synthetic_actor(run.user, encounter.department_id)
             and run.user_id == encounter.created_by_id,
             'This output requires an enrolled synthetic clinician reviewing their own encounter.')
        return bundle, [str(run.user_id)]
    need(legacy_scope(bundle, encounter, run),
         'This actor, source note or service date is outside the authorized synthetic assessment.')
    return bundle, bundle['scope']['actor_ids']


def covers(entry, when):
    if 'service_dates' in entry:
        return when.isoformat() in entry['service_dates']
    try:
        return date.fromisoformat(entry['effective_from']) <= when <= date.fromisoformat(entry['effective_until'])
    except (KeyError, ValueError, TypeError):
        return False
