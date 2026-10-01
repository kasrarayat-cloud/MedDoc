"""Destination authority on the clinical side: whether a place may receive an answer at all.

⚠️ WHETHER A DESTINATION MAY RECEIVE AN ANSWER IS A DIFFERENT QUESTION FROM WHETHER THE ANSWER IS SUPPORTED. A model
never creates permission to write a signature, perform an attestation or change an identity field. The permission comes
from the ORIGINAL's structure, read afresh in the isolated parser at every gate (documents.word_v3.destination_roles for
a contract v3 original; the engine's kind rule on each field's PRINTED label for a legacy one) - never from the stored
mapping, which a removal, a re-added manual field or an old version could have changed.

Gates: manual add (the engine's locate refuses), mapping confirmation, mapping-assistance resolution, generation (a
field on a role place is never asked), review save and finalization (generated or accepted text there is refused; on the
legacy path a clinician's own typed value is allowed and exports), and the v3 fill itself.

ROLES-2 (documents.word_v3.destination_state): every place is ORDINARY, PROTECTED or UNCERTAIN, by ONE decision read
from the original's printed label and structure on both engines. Protected: never generated; on v3 only a Signature or
Initials field may sit there (a text field is refused at confirmation, save, fill and export). Uncertain: never
generated, shown on the review page with what needs review; generated or accepted text is refused at save and
finalization, and a clinician's own typed value is allowed (v3: after the clinician replaces the engine's Signature or
Initials field by a text field). The reading is versioned (ROLE_READING) and is never applied to a finalized export.

ROLES-3: an uncertain hold is narrowed out of generation natively (a write_protected copy, answered 'missing' with its
reason) and no longer refuses the ordinary-relations generation (generation_refusal) or the area review of an assisted
mapping (v3_held with fields); a protected violation still refuses both. The complete-form plan, which asks the STORED
fields, still refuses every hold (v3_held without fields).
"""
import collections
import threading

from django.core.exceptions import ValidationError

from . import v3_mapping
from .security import private_path

ROLE_NOT_GENERATED = ('Signed or initialled by hand on the printed form: this answer area is never generated from notes. '
                      'Enter it yourself if it belongs in this document.')
IDENTITY_NOT_GENERATED = 'Signature requires explicit review by the finalizing clinician; it is not generated from notes.'
UNCERTAIN_NOT_GENERATED = ('Needs your review: the printed form does not show whether this is a signing or initials place '
                           'or an ordinary answer. It is never filled from the notes. If it is an answer, enter it yourself.')
#: The same, for the engine's own Signature or Initials field on such a place of a contract v3 form (it takes no typed
#: text, so the clinician replaces it first).
UNCERTAIN_REPLACE = ('Needs your review: the printed form does not show whether this is a signing or initials place or an '
                     'ordinary answer. It is never filled from the notes. If it is an answer, replace this field with a '
                     "text field on the form's answer-fields page, then enter it yourself.")
#: Every reason a destination role gives an answer it never generated (shown on the review page).
DESTINATION_REASONS = (ROLE_NOT_GENERATED, UNCERTAIN_NOT_GENERATED, UNCERTAIN_REPLACE)
#: A generation that would need to change what a contract's catalogue binds (the ordinary relations contract, the
#: batched complete-form contract) is refused rather than silently narrowed.
GENERATION_HELD_REFUSAL = ('This form\'s mapping places an answer area on a signing, initials, consent or protected place '
                           'of the original form (or without its printed requirement): {labels}. Nothing was sent or '
                           'charged. Correct the mapping on the form\'s page and confirm it again.')


#: Verified role readings of unchanged originals, reused across requests by this process (see report()).
_PROCESS_REPORTS = collections.OrderedDict()
_PROCESS_LOCK = threading.Lock()
_PROCESS_LIMIT = 64
_PROCESS_ENTRY_LIMIT = 256 * 1024     # bytes of a reading's JSON; larger readings are not retained


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
    path = private_path(version.template.original_path)
    # The original and a mapping version are immutable, so one reading serves every gate of one request (generation
    # asks three) - kept on this in-memory version object, keyed by the exact mapping it judged.
    from documents.word_v3 import ROLE_READING
    key = hashlib.sha256(json.dumps([ROLE_READING, engine, version.template.sha256, fields], sort_keys=True,
                                    default=str).encode()).hexdigest()
    cache = getattr(version, '_destination_role_reports', None)
    if cache is None:
        cache = {}
        try:
            version._destination_role_reports = cache
        except AttributeError:
            pass
    if key in cache:
        return copy.deepcopy(cache[key])
    # ⚠️ AND ACROSS REQUESTS, IN THIS PROCESS (integrated-candidate refutation R2-1): every v3 review save re-ran the
    # isolated parser under the encounter row lock, 5-11x slower than 43fcf214. The report is a pure function of the
    # original's bytes, the mapping and the engine, so a verified reading is reused for the same template and mapping -
    # but ONLY after the file is read and hashed again here and still equals the recorded digest (cache refutation
    # F1/F2: a file identity on disk is not its content, and an unreadable or rewritten original must still refuse).
    # Any read failure or digest mismatch is a miss, and the isolated parser then refuses exactly as before.
    template_pk = getattr(version.template, 'pk', None)
    process_key = (key, str(template_pk)) if template_pk is not None else None   # an unsaved template is never shared
    with _PROCESS_LOCK:
        hit = _PROCESS_REPORTS.get(process_key) if process_key is not None else None
        if hit is not None:
            _PROCESS_REPORTS.move_to_end(process_key)
    if hit is not None and _current_digest(path) == version.template.sha256:
        cache[key] = copy.deepcopy(hit)
        return copy.deepcopy(hit)
    result = destination_roles(path, fields, engine=engine)
    if result.get('sha256') != version.template.sha256:
        raise ValidationError('Original integrity check failed.')
    if engine == 'v3' and result.get('contract') != v3_mapping.CONTRACT:
        raise ValidationError('Original integrity check failed.')
    if engine == 'legacy' and not isinstance(result.get('legacy_roles'), dict):
        raise ValidationError('Original integrity check failed.')
    cache[key] = copy.deepcopy(result)
    # Bounded by size as well as count (cache refutation F4): a pathological reading is never retained.
    if process_key is not None and len(json.dumps(result, default=str)) <= _PROCESS_ENTRY_LIMIT:
        with _PROCESS_LOCK:
            _PROCESS_REPORTS[process_key] = copy.deepcopy(result)
            while len(_PROCESS_REPORTS) > _PROCESS_LIMIT:
                _PROCESS_REPORTS.popitem(last=False)
    return result


def _current_digest(path):
    """sha256 of the file's bytes now, or None when it cannot be read."""
    import hashlib
    digest = hashlib.sha256()
    try:
        with open(path, 'rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                digest.update(block)
    except OSError:
        return None
    return digest.hexdigest()


def v3_protected(version, fields=None):
    """{key: reason} for every field of a contract v3 mapping that touches a role place it may not take (refused at
    confirmation, save, fill and export)."""
    result = report(version, fields)
    if not result:
        return {}
    return {key: row['reason'] for key, row in (result.get('violations') or {}).items()}


def v3_uncertain(version, fields=None):
    """{key: reason} for every text field of a contract v3 mapping on an UNCERTAIN place (roles-2): never generated, its
    generated or accepted text refused at save and finalization, a clinician's typed value allowed."""
    result = report(version, fields)
    if not result:
        return {}
    return {key: UNCERTAIN_NOT_GENERATED for key in (result.get('held') or {})}


def v3_held(version, fields=None):
    """{key: reason} - for the version's STORED mapping (fields=None): every field never GENERATED for its place,
    protected (v3_protected) or uncertain (v3_uncertain); the complete-form plan, which asks the stored fields, refuses
    them. For a mapping the clinician's area decisions produce (fields given - mapping assistance's validate_mapping):
    the protected fields only, exactly what confirmation refuses.

    ⚠️ roles-3 (L3:RF3-04): with the uncertain fields as well, the area review of an assisted mapping refused every form
    that carries the signer's consent choice or the clinician's own text field on an uncertain place - fields
    confirmation accepts and generation narrows out natively - so the review could never be saved."""
    result = report(version, fields)
    if not result:
        return {}
    held = {} if fields is not None else {key: UNCERTAIN_NOT_GENERATED for key in (result.get('held') or {})}
    held.update({key: row['reason'] for key, row in (result.get('violations') or {}).items()})
    return held


def legacy_roles(version, *, fresh=True):
    """{key: {'printed_label', 'role', 'state', 'basis', 'reading'}} for a legacy mapping: each field's PRINTED label
    and its roles-2 destination state, read from a fresh inspection of the original in the isolated parser (the label
    cell's paragraphs and line breaks read as spaces, the labels beside it in the same table read as its structure).

    ⚠️ ALWAYS FRESH (roles-2, residual L3:F3-01). The first mapping version's stored labels join a wrapped label cell
    with no separator ('Consultantsignature'), so generation and save read no role there while finalization, reading
    the original, refused it - three gates, two answers. Every gate now reads the same original the same way (a
    verified reading is reused in this process, so the cost is one isolated parse per template and mapping). `fresh`
    is kept for callers; it no longer selects another reader."""
    result = report(version)
    return (result or {}).get('legacy_roles') or {}


def printed(field, roles):
    """The field as identity reads it. Its PRINTED (inspected) label decides wherever that label is itself a signing
    place (legacy_reason: identity, a signature or initials role, or another named person's signature line), so a
    participant's signature line renamed 'Signature' is not the finalizer's (design matrix L05). Everywhere else the
    mapping's label decides, as on 43fcf214.

    ⚠️ Reading ONLY the printed label (refutation of 258650f2, L1:R1-02) dropped identity from a field a clinician
    renamed TO a signature label: a Word row 'Doctor' renamed "Doctor's signature" and a PDF field 'Text1' renamed
    'Signature' finalized another clinician's typed name, and 'Leave blank - reviewed' was accepted there. The rename
    guard refuses only renames AWAY from a signature label, so this is the only way such a field becomes identity.
    So identity = the printed label's identity, or the mapped label's where the printed label is no signing place.

    ⚠️ AND THE MAPPED LABEL'S IDENTITY IS NEVER DROPPED (final verification of 8951fdec, FV-01, a regression vs
    43fcf214). Returning the printed label whenever it is a signing place dropped identity from a real signing place
    renamed TO a signature label ('Initials', 'Sign here', 'Signature and date', a PDF field 'Initials' renamed
    'Signature'): another clinician's typed name finalized and 'Leave blank - reviewed' was accepted, where 43fcf214
    refused both. Identity is therefore the mapped label's OR the printed label's, never less than 43fcf214's reading;
    the design-matrix L05 relaxation (another person's line renamed 'Signature' is not the finalizer's) is withdrawn,
    because it was the same drop."""
    from .tab_review import clinician_identity
    row = (roles or {}).get(field.get('key'))
    if not row or clinician_identity(field):
        return field
    return {**field, 'label': row['printed_label']} if legacy_reason(field, row) else field


def legacy_reason(field, row):
    """Why a legacy field is never generated (its printed label is identity, its destination state protected - a
    signature or initials place, or another named person's signature line (tab_review.another_signers_line) - or
    uncertain), or ''."""
    from .tab_review import another_signers_line, clinician_identity
    if not row:
        return ''
    printed_field = {**field, 'label': row['printed_label']}
    if clinician_identity(printed_field):
        return IDENTITY_NOT_GENERATED
    if another_signers_line(printed_field):
        return ROLE_NOT_GENERATED
    state = row.get('state')
    if state == 'uncertain':
        return UNCERTAIN_NOT_GENERATED
    return ROLE_NOT_GENERATED if state == 'protected' or (state is None and row.get('role')) else ''


def held(version, *, fresh=True):
    """{key: reason} for every field of this version that is never generated: on a protected or uncertain place (v3) or
    whose printed label is identity, a signing place or uncertain (legacy) - both read fresh from the original. The
    qualified WM form: empty."""
    if not applies(version):
        return {}
    if v3_mapping.is_v3_version(version):
        return v3_held(version)
    roles = legacy_roles(version, fresh=fresh)
    return {f['key']: reason for f in version.fields if (reason := legacy_reason(f, roles.get(f['key'])))}


def review_reasons(version):
    """{key: reason} the review page shows for each field held by its destination state (roles-2), read from the
    original now: legacy - the printed label's reason; v3 - a text field on an uncertain place, or any field (the
    engine's Signature or Initials field included) on a place whose role cannot be established. Never called for a
    finalized record (its stored answers are what was decided)."""
    if not applies(version):
        return {}
    if v3_mapping.is_v3_version(version):
        result = report(version) or {}
        signing = {f['key'] for f in version.fields if f.get('kind') in v3_mapping.SIGNING_KINDS}
        out = {key: UNCERTAIN_REPLACE if key in signing else UNCERTAIN_NOT_GENERATED
               for key in result.get('uncertain_places') or []}
        out.update({key: UNCERTAIN_NOT_GENERATED for key in (result.get('held') or {})})
        return out
    roles = legacy_roles(version)
    return {f['key']: reason for f in version.fields
            if (reason := legacy_reason(f, roles.get(f['key']))) in DESTINATION_REASONS}


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
    before anything is sent when a field sits on a PROTECTED place (a stored text field the confirmation gate would
    refuse today - f5fe720f's refusal, unchanged).

    ⚠️ roles-3 (L2:R2-03, L3:RF3-04): an UNCERTAIN hold is not dropped silently - its write_protected copy is part of
    the catalogue the contract sends, never asked (v3_generation_fields) and answered 'missing' with its reason
    (v3_adopted) - so it no longer refuses the whole generation of a form that carries the signer's consent choice or
    the clinician's own text field on an uncertain place."""
    from . import generation
    if not any(f.get('write_protected') for f in fields):
        return ''
    protected = v3_protected(version) if v3_mapping.is_v3_version(version) else {}
    labels = [v3_mapping.label_of(f) for f in fields if f.get('write_protected') and f['key'] in protected and
              not next((o for o in version.fields if o['key'] == f['key'] and o.get('write_protected')), None)]
    if labels and config.get('ordinary_field_contract') and generation.natural_v3(version.fields):
        return GENERATION_HELD_REFUSAL.format(labels=', '.join(labels[:12]))
    return ''


def generated_text(answer):
    """Text that generation produced or a one-click suggestion supplied, never the clinician's own typed value."""
    if not isinstance(answer, dict) or not str(answer.get('text') or '').strip():
        return False
    return bool(answer.get('accepted_suggestion')) or answer.get('status') in ('supported', 'conflict')
