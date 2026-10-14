"""Owner-reviewed CPT rights and exact dated content, never an environment flag.

This verifies retained evidence and its declared scope, not a legal opinion.
No agreement, feed, permission review, or billing criteria are bundled here.
"""
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

DEFAULT_MANIFEST = '/opt/meddoc-pro/rebuild/.runtime/owner-contracts/cpt-entitlement-v1.json'
MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
REQUIREMENTS = ('protected_entitlement_manifest', 'executed_agreement', 'issuer_and_license',
                'QuillMD_product_scope', 'authorized_users', 'distribution_scope',
                'intended_AI_use', 'current_validity', 'dated_content_release',
                'documented_permission_review', 'licensed_rule_criteria')


class EntitlementUnavailable(ValidationError):
    def __init__(self, requirement, message):
        self.requirement = requirement
        super().__init__(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def _object(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate field')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('nonfinite JSON')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _read(path, limit=MAX_DOCUMENT_BYTES):
    """Read one private regular file without following links or changing it."""
    path = Path(path)
    if not path.is_absolute() or any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError('absolute non-symlink protected path required')
    parent = path.parent.stat()
    if stat.S_IMODE(parent.st_mode) != 0o700 or parent.st_uid not in (0, os.geteuid()):
        raise ValueError('private owner-controlled directory required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or stat.S_IMODE(before.st_mode) != 0o600
                or before.st_nlink != 1 or before.st_uid not in (0, os.geteuid())
                or not 0 < before.st_size <= limit):
            raise ValueError('private bounded regular evidence file required')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(limit + 1)
        after = os.fstat(fd)
        stable = ('st_dev', 'st_ino', 'st_uid', 'st_gid', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if any(getattr(before, key) != getattr(after, key) for key in stable) or len(raw) != before.st_size:
            raise ValueError('evidence changed while reading')
        return raw
    finally:
        os.close(fd)


def _artifact(parent, reference):
    if (type(reference) is not dict or set(reference) != {'filename', 'sha256'}
            or type(reference['filename']) is not str
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,150}', reference['filename'])
            or not re.fullmatch('[0-9a-f]{64}', reference.get('sha256', ''))):
        raise ValueError('closed artifact reference required')
    raw = _read(parent / reference['filename'])
    if hashlib.sha256(raw).hexdigest() != reference['sha256']:
        raise ValueError('evidence hash differs')
    return raw


def _text(value, maximum=2000):
    return type(value) is str and 0 < len(value.strip()) <= maximum and not any(ord(c) < 32 for c in value)


def _dates(value, today):
    if type(value) is not dict or set(value) != {'from', 'until'}:
        raise ValueError('closed validity interval required')
    start, end = date.fromisoformat(value['from']), date.fromisoformat(value['until'])
    if not start <= today <= end:
        raise ValueError('license is not current')
    return start, end


def verified_entitlement():
    """Read explicit owner evidence; a boolean or ID/expiry pair cannot qualify."""
    requirement = 'protected_entitlement_manifest'
    try:
        path = Path(getattr(settings, 'CPT_ENTITLEMENT_MANIFEST', DEFAULT_MANIFEST))
        raw = _read(path, 256000)
        value = _object(raw)
        keys = {'format', 'agreement', 'issuer', 'license_id', 'product', 'users', 'distribution',
                'intended_ai_use', 'validity', 'content_release', 'rules', 'permission_review'}
        if type(value) is not dict or set(value) != keys or value['format'] != 'quillmd-cpt-entitlement-v1':
            raise ValueError('closed entitlement manifest required')
        requirement = 'executed_agreement'
        _artifact(path.parent, value['agreement'])
        requirement = 'issuer_and_license'
        if not _text(value['issuer']) or not _text(value['license_id'], 150):
            raise ValueError('issuer and license reference required')
        requirement = 'QuillMD_product_scope'
        if value['product'] != 'QuillMD':
            raise ValueError('the agreement must cover QuillMD')
        requirement = 'authorized_users'
        if (type(value['users']) is not dict or set(value['users']) != {'scope', 'terms_reference'}
                or value['users']['scope'] != 'all_authorized_quillmd_users'
                or not _text(value['users']['terms_reference'])):
            raise ValueError('explicit application user coverage required')
        requirement = 'distribution_scope'
        distribution = value['distribution']
        if (type(distribution) is not dict or set(distribution) != {'uses', 'terms_reference'}
                or type(distribution['uses']) is not list
                or sorted(distribution['uses']) != ['application_display', 'clinical_export', 'coding_suggestions']
                or not _text(distribution['terms_reference'])):
            raise ValueError('display, suggestions and export coverage required')
        requirement = 'intended_AI_use'
        ai = value['intended_ai_use']
        if (type(ai) is not dict or set(ai) != {'uses', 'training', 'terms_reference'}
                or type(ai['uses']) is not list or sorted(ai['uses']) != ['coding_assistance', 'provider_processing']
                or ai['training'] != 'not_authorized_by_this_application'
                or not _text(ai['terms_reference'])):
            raise ValueError('explicit coding assistance and provider-processing permission required')
        requirement = 'current_validity'
        today = timezone.localdate()
        start, end = _dates(value['validity'], today)
        requirement = 'dated_content_release'
        release = value['content_release']
        if (type(release) is not dict or set(release) != {'version', 'effective_from', 'effective_until', 'source_url', 'sha256', 'code_count'}
                or not _text(release['version'], 60) or not _text(release['source_url'], 200)
                or not release['source_url'].startswith('https://')
                or not re.fullmatch('[0-9a-f]{64}', release.get('sha256', ''))
                or type(release['code_count']) is not int or release['code_count'] <= 0):
            raise ValueError('dated hashed content release required')
        url = urlsplit(release['source_url'])
        if (url.scheme != 'https' or not url.hostname or url.username or url.password or url.query
                or url.fragment or url.port not in (None, 443) or any(ord(c) < 33 for c in release['source_url'])):
            raise ValueError('stable credential-free release provenance required')
        effective_start, effective_end = date.fromisoformat(release['effective_from']), date.fromisoformat(release['effective_until'])
        if not start <= effective_start <= effective_end <= end:
            raise ValueError('license does not cover the supplied content period')
        requirement = 'licensed_rule_criteria'
        rules_raw = _artifact(path.parent, value['rules'])
        rules = _object(rules_raw)
        from .coding_cpt import validate_rules
        validate_rules(rules, release)
        requirement = 'documented_permission_review'
        review = _object(_artifact(path.parent, value['permission_review']))
        covered = {k: value[k] for k in ('agreement', 'issuer', 'license_id', 'product', 'users',
                   'distribution', 'intended_ai_use', 'validity', 'content_release', 'rules')}
        if (type(review) is not dict or set(review) != {'format', 'reviewed_by', 'reviewed_at', 'decision', 'coverage'}
                or review['format'] != 'quillmd-cpt-permission-review-v1'
                or review['decision'] != 'approved' or not _text(review['reviewed_by'])
                or not start <= date.fromisoformat(review['reviewed_at']) <= today
                or canonical(review['coverage']) != canonical(covered)):
            raise ValueError('a documented reviewer must approve these exact agreement and usage scopes')
        return {'manifest': value, 'manifest_sha256': hashlib.sha256(raw).hexdigest(),
                'rules': rules, 'rules_sha256': value['rules']['sha256'],
                'agreement_sha256': value['agreement']['sha256'], 'permission_review_sha256': value['permission_review']['sha256']}
    except (OSError, ValueError, TypeError, KeyError, ValidationError) as exc:
        raise EntitlementUnavailable(requirement, 'CPT unavailable: verified ' + requirement.replace('_', ' ') + ' is required.') from exc


def entitlement_for_release(*, version, effective_from, effective_until, source_url, sha256, code_count):
    proof = verified_entitlement()
    expected = {'version': version, 'effective_from': effective_from.isoformat(),
                'effective_until': effective_until.isoformat(), 'source_url': source_url,
                'sha256': sha256, 'code_count': code_count}
    if canonical(proof['manifest']['content_release']) != canonical(expected):
        raise EntitlementUnavailable('dated_content_release', 'CPT import differs from the exact owner-reviewed licensed release.')
    return proof


@transaction.atomic
def save_licensed_release(rows, metadata, proof):
    """Import the verified descriptions and criteria as one atomic release."""
    from .management.commands.import_terminology import save_release
    from .models import CodingRelease
    # Re-read protected evidence at the write boundary, not a caller boolean.
    current = entitlement_for_release(version=metadata['version'], effective_from=metadata['effective_from'],
        effective_until=metadata['effective_until'], source_url=metadata['source_url'],
        sha256=metadata['sha256'], code_count=len(rows))
    if canonical(current) != canonical(proof) or metadata['license_reference'] != current['manifest']['license_id']:
        raise EntitlementUnavailable('documented_permission_review', 'CPT entitlement changed before the import.')
    rules = current['rules']
    if any(rows.get(code) != criteria['description'] for code, criteria in rules['tabular']['codes'].items()):
        raise EntitlementUnavailable('licensed_rule_criteria', 'Licensed CPT criteria differ from the exact supplied code descriptions.')
    release, created = save_release(rows, metadata, current['manifest']['validity']['until'])
    content = {'index': rules['index'], 'tabular': rules['tabular']}
    values = {**content, 'digest': hashlib.sha256(canonical(content)).hexdigest(),
              'provenance': {'entitlement_sha256': current['manifest_sha256'], 'rules_sha256': current['rules_sha256'],
                             'agreement_sha256': current['agreement_sha256'], 'permission_review_sha256': current['permission_review_sha256']}}
    reference, new = CodingRelease.objects.get_or_create(release=release, defaults=values)
    if not new and any(getattr(reference, key) != value for key, value in values.items()):
        raise EntitlementUnavailable('licensed_rule_criteria', 'Existing CPT criteria differ; immutable references cannot be replaced.')
    return release, created


def cpt_status(service_date=None):
    """Current rights and date-of-service content are independently required."""
    try:
        proof = verified_entitlement()
    except EntitlementUnavailable as exc:
        return {'available': False, 'reason': exc.messages[0], 'missing_requirements': [exc.requirement],
                'license_verified': False, 'dated_release_verified': False}
    from .models import CodeSet, CodingRelease
    supplied = proof['manifest']['content_release']
    when = timezone.localdate() if service_date is None else service_date
    if type(when) is not date:
        return {'available': False, 'reason': 'CPT requires an explicit date of service.', 'missing_requirements': ['date_of_service'],
                'license_verified': True, 'dated_release_verified': False}
    release = CodeSet.objects.filter(system='CPT', version=supplied['version'], sha256=supplied['sha256'],
        license_reference=proof['manifest']['license_id'], source_url=supplied['source_url'],
        effective_from=supplied['effective_from'], effective_until=supplied['effective_until'],
        effective_from__lte=when, effective_until__gte=when).first()
    if release is None or release.code_set.count() != supplied['code_count']:
        return {'available': False, 'reason': 'CPT rights are recorded, but the exact licensed content release does not cover this date of service.',
                'missing_requirements': ['dated_content_release'], 'license_verified': True, 'dated_release_verified': False}
    reference = CodingRelease.objects.filter(release=release).first()
    expected = proof['rules']
    content = {'index': expected['index'], 'tabular': expected['tabular']}
    reference_digest = hashlib.sha256(canonical(content)).hexdigest()
    provenance = {'entitlement_sha256': proof['manifest_sha256'], 'rules_sha256': proof['rules_sha256'],
                  'agreement_sha256': proof['agreement_sha256'], 'permission_review_sha256': proof['permission_review_sha256']}
    if (reference is None or reference.index != content['index'] or reference.tabular != content['tabular']
            or reference.digest != reference_digest or reference.provenance != provenance):
        return {'available': False, 'reason': 'CPT requires the imported licensed rule criteria and their reviewed provenance.',
                'missing_requirements': ['licensed_rule_criteria'], 'license_verified': True, 'dated_release_verified': True}
    return {'available': True, 'reason': 'Owner-reviewed CPT entitlement and dated licensed rules are verified.',
            'missing_requirements': [], 'license_verified': True, 'dated_release_verified': True,
            'release_id': str(release.pk), 'version': release.version, 'sha256': release.sha256,
            'coding_digest': reference.digest, 'rules_sha256': proof['rules_sha256'],
            'license_reference': release.license_reference, 'effective_from': release.effective_from.isoformat(),
            'effective_until': release.effective_until.isoformat()}
