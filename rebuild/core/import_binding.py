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


def verify(version):
    manifest = getattr(version, 'import_manifest', {})
    if not manifest:  # historical versions retain their established contract
        return
    if manifest.get('coverage', {}).get('block_generation'):
        raise ValidationError('This import has unmapped answer areas and the alternative engine could not preserve '
                              'its existing destinations. No generation or charge is allowed. Create and confirm '
                              'a separately reviewed advanced mapping; existing documents retain their engine.')
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
