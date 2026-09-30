"""Destination authority on the clinical side: whether a place may receive an answer at all.

⚠️ WHETHER A DESTINATION MAY RECEIVE AN ANSWER IS A DIFFERENT QUESTION FROM WHETHER THE ANSWER IS SUPPORTED. A model
never creates permission to write a signature, perform an attestation or change an identity field. The permission comes
from the ORIGINAL's structure, read afresh in the isolated parser at every gate (documents.word_v3.destination_roles for
a contract v3 original; the engine's kind rule on each field's PRINTED label for a legacy one) - never from the stored
mapping, which a removal, a re-added manual field or an old version could have changed.

Gates: manual add (the engine's locate refuses), mapping confirmation, mapping-assistance resolution, generation (a
field on a role place is never asked), review save and finalization (generated or accepted text there is refused; on the
legacy path a clinician's own typed value is allowed and exports), and the v3 fill itself.
"""
from django.core.exceptions import ValidationError

from . import v3_mapping
from .security import private_path

ROLE_NOT_GENERATED = ('Signed or initialled by hand on the printed form: this answer area is never generated from notes. '
                      'Enter it yourself if it belongs in this document.')
IDENTITY_NOT_GENERATED = 'Signature requires explicit review by the finalizing clinician; it is not generated from notes.'
#: A generation that would need to change what a contract's catalogue binds (the ordinary relations contract, the
#: batched complete-form contract) is refused rather than silently narrowed.
GENERATION_HELD_REFUSAL = ('This form\'s mapping places an answer area on a signing, initials, consent or protected place '
                           'of the original form (or without its printed requirement): {labels}. Nothing was sent or '
                           'charged. Correct the mapping on the form\'s page and confirm it again.')


def applies(version):
    """The qualified WM form keeps its own reviewed contract; every other Word or PDF form is read here."""
    return bool(version) and not getattr(version, 'document_backend', None)


def report(version, fields=None):
    """The isolated parser's role report for this version's ORIGINAL, bound to the template's digest."""
    import copy
    import hashlib
    import json
    from documents.service import destination_roles
    if not applies(version):
        return None
    fields = list(version.fields if fields is None else fields)
    engine = 'v3' if v3_mapping.is_v3_version(version) else 'legacy'
    # The original and a mapping version are immutable, so one reading serves every gate of one request (generation
    # asks three) - kept on this in-memory version object only, keyed by the exact mapping it judged.
    key = hashlib.sha256(json.dumps([engine, version.template.sha256, fields], sort_keys=True, default=str).encode()).hexdigest()
    cache = getattr(version, '_destination_role_reports', None)
    if cache is None:
        cache = {}
        try:
            version._destination_role_reports = cache
        except AttributeError:
            pass
    if key in cache:
        return copy.deepcopy(cache[key])
    result = destination_roles(private_path(version.template.original_path), fields, engine=engine)
    if result.get('sha256') != version.template.sha256:
        raise ValidationError('Original integrity check failed.')
    if engine == 'v3' and result.get('contract') != v3_mapping.CONTRACT:
        raise ValidationError('Original integrity check failed.')
    if engine == 'legacy' and not isinstance(result.get('legacy_roles'), dict):
        raise ValidationError('Original integrity check failed.')
    cache[key] = copy.deepcopy(result)
    return result


def v3_held(version, fields=None):
    """{key: reason} for every field of a contract v3 mapping that touches a role place it may not take."""
    result = report(version, fields)
    if not result:
        return {}
    return {key: row['reason'] for key, row in (result.get('violations') or {}).items()}


def legacy_roles(version, *, fresh=False):
    """{key: {'printed_label', 'role'}} for a legacy mapping: each field's PRINTED label and the role the engine's kind
    rule gives it (documents.word_v3.legacy_role_kind).

    fresh=True reads them from a fresh inspection of the original in the isolated parser (finalization, which fills
    from that same inspection). Otherwise from the template's FIRST mapping version: the engine's own inspection of this
    original, recorded at upload in an append-only row (a database trigger refuses UPDATE and DELETE) - a legacy
    mapping can only rename labels, never add, remove or move a field, so its keys never change."""
    if fresh:
        result = report(version)
        return (result or {}).get('legacy_roles') or {}
    from documents.word_v3 import legacy_role_kind
    first = version.template.versions.order_by('number').first()
    inspected = {f['key']: f.get('label') for f in (first.fields if first is not None else []) if isinstance(f, dict)}
    out = {}
    for field in version.fields:
        label = inspected.get(field['key'], field.get('label'))
        out[field['key']] = {'printed_label': label, 'role': legacy_role_kind(label)}
    return out


def printed(field, roles):
    """The field as identity reads it. Its PRINTED (inspected) label decides wherever that label is itself a signing
    place (legacy_reason: identity, a signature or initials role, or another named person's signature line), so a
    participant's signature line renamed 'Signature' is not the finalizer's (design matrix L05). Everywhere else the
    mapping's label decides, as on 43fcf214.

    ⚠️ Reading ONLY the printed label (refutation of 258650f2, L1:R1-02) dropped identity from a field a clinician
    renamed TO a signature label: a Word row 'Doctor' renamed "Doctor's signature" and a PDF field 'Text1' renamed
    'Signature' finalized another clinician's typed name, and 'Leave blank - reviewed' was accepted there. The rename
    guard refuses only renames AWAY from a signature label, so this is the only way such a field becomes identity.
    So identity = the printed label's identity, or the mapped label's where the printed label is no signing place."""
    row = (roles or {}).get(field.get('key'))
    if not row:
        return field
    return {**field, 'label': row['printed_label']} if legacy_reason(field, row) else field


def legacy_reason(field, row):
    """Why a legacy field is never generated (its printed label is identity, a signature or initials, or another named
    person's signature line - tab_review.another_signers_line), or ''."""
    from .tab_review import another_signers_line, clinician_identity
    if not row:
        return ''
    printed_field = {**field, 'label': row['printed_label']}
    if clinician_identity(printed_field):
        return IDENTITY_NOT_GENERATED
    return ROLE_NOT_GENERATED if row.get('role') or another_signers_line(printed_field) else ''


def held(version, *, fresh=False):
    """{key: reason} for every field of this version that sits on a role place (v3, always read fresh) or reads as a
    signature, initials or identity row by its printed label (legacy). The qualified WM form: empty."""
    if not applies(version):
        return {}
    if v3_mapping.is_v3_version(version):
        return v3_held(version)
    roles = legacy_roles(version, fresh=fresh)
    return {f['key']: reason for f in version.fields if (reason := legacy_reason(f, roles.get(f['key'])))}


def generation_fields(version):
    """The version's fields as generation must see them: a field on a role place is never asked.

    Copies only - nothing is stored. A v3 field is held exactly as a protected area is held (write_protected with its
    reason: never asked, its label kept as a context label, answered 'missing' with the reason); a legacy field carries
    `destination_role`, which generation's field selection reads the same way."""
    fields = [dict(field) for field in version.fields]
    reasons = held(version)
    for field in fields:
        reason = reasons.get(field['key'])
        if not reason:
            continue
        if v3_mapping.is_v3_version(version):
            field.update(write_protected=True, review_reason=reason)
        else:
            field['destination_role'] = {'reason': reason}
    return fields


def generation_refusal(version, fields, config):
    """A contract whose request binds the complete catalogue (ordinary relations) cannot silently drop a field; refuse
    before anything is sent when any field is held."""
    from . import generation
    labels = [v3_mapping.label_of(f) for f in fields if f.get('write_protected') and
              not next((o for o in version.fields if o['key'] == f['key'] and o.get('write_protected')), None)]
    if labels and config.get('ordinary_field_contract') and generation.natural_v3(version.fields):
        return GENERATION_HELD_REFUSAL.format(labels=', '.join(labels[:12]))
    return ''


def generated_text(answer):
    """Text that generation produced or a one-click suggestion supplied, never the clinician's own typed value."""
    if not isinstance(answer, dict) or not str(answer.get('text') or '').strip():
        return False
    return bool(answer.get('accepted_suggestion')) or answer.get('status') in ('supported', 'conflict')
