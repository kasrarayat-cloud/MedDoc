"""Import provenance carried by each immutable mapping version."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from documents.import_selection import digest, ENGINE_VERSIONS


def for_mapping(manifest, fields):
    if not manifest:
        return {}
    bound = deepcopy(manifest)
    bound['mapping_sha256'] = digest(fields)
    return bound


def verify(version, *, allow_unreviewed=False):
    manifest = getattr(version, 'import_manifest', {})
    if not manifest:  # historical versions retain their established contract
        return
    expected = 'v3' if version.contract == 'v3' else 'legacy'
    from documents.service import engine_fingerprint, DocumentError
    try:
        processor = engine_fingerprint(expected, source_sha256=version.template.sha256)
    except (DocumentError, ValueError):
        raise ValidationError('The bound Word processor is unavailable. Nothing was sent or exported.') from None
    if (manifest.get('source_sha256') != version.template.sha256
            or manifest.get('engine') != expected
            or manifest.get('engine_version') != ENGINE_VERSIONS.get(expected)
            or manifest.get('engine_code_sha256') != processor
            or manifest.get('mapping_sha256') != digest(version.fields)):
        raise ValidationError('The stored import choice does not match this original and mapping version. '
                              'Nothing was sent or exported; review a new mapping version.')
    if not allow_unreviewed and manifest.get('coverage', {}).get('block_generation') and not coverage_reviewed(version):
        raise ValidationError('This import has unmapped answer areas. No generation or charge is allowed until a '
                              'clinician reviews the exact exclusions or a new original/mapping repairs them. '
                              'Excluded areas remain unchanged and do not count as supported coverage.')


def coverage_reviewed(version):
    """Explicitly excluded physical areas stay unwritable and never count as support.

    A mapping review may leave an ambiguous original area unchanged; it cannot
    turn that review into a mapped answer or an attestation. Every new mapping
    is checked again against these original exclusions before money or export.
    """
    coverage = version.import_manifest.get('coverage', {})
    issues = coverage.get('selected_engine_issues') or []
    if not issues or coverage.get('comparison_unresolved'):
        return False
    reviews = version.corrections.get('coverage_review', [])
    by_id = {row.get('id'): row for row in reviews if isinstance(row, dict)}
    if any(issue['id'] not in by_id for issue in issues):return False
    from documents.service import writing_places, DocumentError
    from .security import private_path
    try:
        verify(version, allow_unreviewed=True)  # never read destinations through changed processor code
        places = writing_places(private_path(version.template.original_path), version.fields)
    except (ValidationError, DocumentError, OSError, ValueError):
        return False
    if places.get('sha256') != version.template.sha256:return False
    for issue in issues:
        row = by_id.get(issue['id'])
        if (not row or row.get('disposition') != 'leave_unchanged'
                or row.get('source_sha256') != version.template.sha256 or not row.get('reviewed_by')):
            return False
        from types import SimpleNamespace
        from documents.word_v3 import _PlaceReader, _place_id
        reader = _PlaceReader(SimpleNamespace(by_id={}))  # only compare sandbox-derived positions here
        excluded = _place_id(issue['part'], issue['slot'])
        region = {'place': excluded, 'start': issue.get('start'), 'end': issue.get('end')}
        for field in version.fields:
            if field.get('kind') in ('signature', 'initials') or field.get('write_protected'):
                continue
            if field['key'] not in places.get('places',{}):return False
            if any(reader.touches(place, region) for place in places['places'][field['key']]):
                return False
    return True


def ordinary_role_fields(version):
    """Signing-typed metadata with a real writer and NO physical role in the original.

    This grants only an explicit mapping-kind review. It never supplies a name,
    accepts an answer, or treats a review click as a signing act. Structure-bound
    signing/protection/policy roles still refuse at confirmation and export.
    """
    from . import destination_roles, v3_mapping
    if not v3_mapping.is_v3_version(version):
        return set()
    proposed = []
    eligible = set()
    for field in version.fields:
        if (field.get('kind') in v3_mapping.SIGNING_KINDS and not field.get('write_protected')
                and field.get('locator', {}).get('target', {}).get('type') not in (None, 'none')):
            eligible.add(field['key'])
            proposed.append({**field, 'kind': 'text'})
        else:
            proposed.append(field)
    if not eligible:
        return set()
    held = destination_roles.v3_held(version, proposed)
    return eligible - set(held)
