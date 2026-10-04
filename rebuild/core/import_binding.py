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


def verify(version, *, allow_unreviewed=False, reviewing_reinspection=False):
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
                              'Nothing was sent or exported. Open the form and choose Recheck answer locations, '
                              'then review its freshly inspected mapping.')
    lineage = manifest.get('reinspection')
    if lineage:
        from .models import TemplateVersion
        if (not isinstance(lineage, dict) or lineage.get('source_sha256') != version.template.sha256
                or not TemplateVersion.objects.filter(pk=lineage.get('source_version_id'),
                    template_id=lineage.get('source_template_id'),
                    template__department_id=version.template.department_id,
                    template__sha256=version.template.sha256).exists()):
            raise ValidationError('This reinspection does not bind its preserved source form. Nothing was sent or exported.')
        # V3 confirmation already reads physical roles through verify(). Legacy reinspection
        # uses a separate review route; ordinary legacy imports retain their historical contract.
        if expected == 'legacy' and not allow_unreviewed and not reviewing_reinspection and version.needs_confirmation:
            raise ValidationError('Review every answer location and confirm this freshly inspected mapping before generating or exporting.')
    from documents.word_v3 import KNOWN_LAYOUT_FAILURES
    if not allow_unreviewed and (manifest.get('coverage', {}).get('layout_quarantine')
                                or version.template.sha256 in KNOWN_LAYOUT_FAILURES):
        raise ValidationError('This exact original has retained rendered answer failures and is unsupported. '
                              'No generation or charge is allowed until its whole-document growth is qualified. '
                              'Leaving areas unchanged cannot qualify this original.')
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
    from documents.word_v3 import KNOWN_LAYOUT_FAILURES
    if (not issues or coverage.get('comparison_unresolved') or coverage.get('layout_quarantine')
            or version.template.sha256 in KNOWN_LAYOUT_FAILURES):
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
    held = destination_roles.v3_held(version, proposed, mapping_review=True)
    return eligible - set(held)


def verify_review_places(version):
    """Review uses original automatic anchors or freshly compiled manual destinations.

    No answer is written and no mapping is updated. Renaming/reclassifying an ordinary
    automatic field retains its original locator. A manual field must still compile to
    the same physical destination under the current immutable original.
    """
    from .security import private_path
    from documents.service import outline_template, locate_fields
    from documents.word_v3 import box_key
    verify(version, allow_unreviewed=True)
    outline = outline_template(private_path(version.template.original_path))
    if outline.get('sha256') != version.template.sha256:
        raise ValidationError('Original integrity check failed.')
    places = {row['slot']: row for row in outline['slots']}
    initial = version.template.versions.order_by('number').first()
    initial_fields = {field['key']: field for field in initial.fields}
    manual, targets = [], []
    refusal = 'An answer location no longer matches this preserved original. Remove that field and add it again from the form; nothing was confirmed.'
    for field in version.fields:
        locator = field.get('locator') or {}
        target = locator.get('target') or {}
        references = [locator, *locator.get('extra', []), *target.get('copies', []), *target.get('boxes', [])]
        for reference in references:
            identity = str(reference.get('part', '')) + '#' + str(reference.get('slot', ''))
            # Table-row fields anchor the real whole table, absent from the manual
            # outline; its original child locations establish its existence.
            if identity not in places and not (field.get('kind') == 'table_rows'
                    and any(place.startswith(identity + '/') for place in places)):
                raise ValidationError(refusal)
        prior = initial_fields.get(field['key'])
        if field.get('origin') != 'manual':
            if (not prior or locator != prior.get('locator')
                    or field.get('source_questions') != prior.get('source_questions')
                    or field.get('source_instructions') != prior.get('source_instructions')):
                raise ValidationError(refusal)
            continue
        identity = locator['part'] + '#' + locator['slot']
        request = {'slot': identity, 'kind': field['kind'], 'label': field['label'], 'context': field.get('context', '')}
        if target.get('shape') == 'numeric_part':
            request['numeric_part'] = target.get('number')
        if field.get('kind') == 'checkbox':
            boxes = target.get('boxes') or []
            keys = places[identity].get('box_keys') or []
            empty_cell = (len(boxes) == 1 and boxes[0].get('kind') == 'cell'
                          and boxes[0].get('part') + '#' + boxes[0].get('slot') == identity
                          and places[identity].get('kind') == 'tc' and not keys)
            if len(boxes) != 1 or (not empty_cell and box_key(boxes[0]) not in keys):
                raise ValidationError(refusal)
            request['glyph'] = 0 if empty_cell else keys.index(box_key(boxes[0]))
        manual.append(field); targets.append(request)
    for start in range(0, len(targets), 200):
        compiled = locate_fields(private_path(version.template.original_path), targets[start:start + 200])
        if compiled.get('sha256') != version.template.sha256:
            raise ValidationError('Original integrity check failed.')
        for field, current in zip(manual[start:start + 200], compiled['fields']):
            if any(field.get(key) != current.get(key) for key in
                   ('locator', 'source_questions', 'source_instructions', 'write_protected', 'answer_policy')):
                raise ValidationError(refusal)
