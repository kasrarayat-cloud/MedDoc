"""Approved export source, separate from the retained uploaded original."""
import hashlib
from django.core.exceptions import ValidationError
from documents.preparation_service import read_original
from documents.preparation import digest
from .security import private_path

def approval_binding(preparation):
    binding = {'template_id': str(preparation.template_id),
                   'original_sha256': preparation.template.sha256,
                   'inventory_sha256': preparation.inventory.get('inventory_sha256'),
                   'proposal': preparation.proposal, 'checker': preparation.checker,
                   'corrections': preparation.corrections, 'revision': preparation.revision,
                   'correction_history':getattr(preparation,'correction_history',[]),
                   'candidate_sha256': preparation.candidate_sha256,
                   'candidate_info': preparation.candidate_info, 'changes': preparation.changes}
    if 'word_answer_contract' in getattr(preparation, 'config', {}):
        binding['word_answer_contract'] = preparation.config['word_answer_contract']
    from documents.question_context import CONFIG_KEY
    if CONFIG_KEY in getattr(preparation, 'config', {}):
        binding[CONFIG_KEY] = preparation.config[CONFIG_KEY]
    from documents.signing_source_context import CONFIG_KEY as signing_key, CONTEXT as signing_context
    if getattr(preparation, 'config', {}).get(signing_key) == signing_context:
        binding[signing_key] = signing_context
    return digest(binding)

def assert_pdf_template_usable(template):
    """⚠️ FINDING DL-2. A PDF template accepted before the raw scan existed is still stored, and its
    original is read only at finalize. So a form the download gate now refuses stayed selectable: a
    doctor could create an encounter on it and spend a paid generation, learning only at finalize
    that it can never produce a document. This runs the same isolated-worker active-content check as
    the download, on the stored original, at the two earliest points (encounter creation and every
    provider enqueue), so a refused form is turned away before any provider usage. DOCX originals are
    validated by source_for_version; this is PDF only. A missing or changed original is left to the
    step that reads it, so this never blocks work for an unrelated storage fault."""
    if (template.format or '').lower() != 'pdf':
        return
    from documents import check_original, DocumentError
    path = private_path(template.original_path)
    try:
        data = path.read_bytes()
    except OSError:
        return
    if hashlib.sha256(data).hexdigest() != template.sha256:
        return
    try:
        check_original(path, expected_sha256=template.sha256)
    except DocumentError as exc:
        raise ValidationError('This form can no longer be used: ' + str(exc) + ' Upload a clean PDF as a new '
                              'form. Nothing was sent for processing and nothing was charged.')


def source_for_version(version):
    from .semantic_preparation import validated_semantic_definitions
    validated_semantic_definitions(version)
    return physical_source_for_version(version)


def physical_source_for_version(version):
    original = private_path(version.template.original_path)
    data = read_original(original) if version.template.format == 'docx' else original.read_bytes()
    if hashlib.sha256(data).hexdigest() != version.template.sha256:
        raise ValidationError('Original integrity check failed.')
    if not version.preparation_id:
        if version.prepared_path or version.prepared_sha256:
            raise ValidationError('The prepared form has no layout approval.')
        return original
    prep = version.preparation
    from documents.preparation import validate_inventory
    validate_inventory(prep.inventory)
    from documents.question_context import validate_binding
    validate_binding(prep.inventory, getattr(prep, 'config', {}))
    from documents.signing_source_context import validate_binding as validate_signing_binding
    validate_signing_binding(prep.inventory, getattr(prep, 'config', {}))
    if (prep.template_id != version.template_id or prep.state != 'approved' or not prep.approved_by_id
            or not prep.approved_at or prep.approval_sha256 != approval_binding(prep)
            or version.prepared_path != prep.candidate_path or version.prepared_sha256 != prep.candidate_sha256
            or digest(version.document_backend) != digest(prep.candidate_info.get('document_backend', {}))
            or digest(version.review_requirements) != digest(prep.candidate_info.get('review_requirements', []))):
        raise ValidationError('This prepared form is unapproved, stale, or belongs to another form.')
    from documents.engine import structure
    if digest(structure(version.fields)) != digest(structure(prep.candidate_info['fields'])):
        raise ValidationError('This mapping differs from the approved answer placement.')
    if 'question_context' in prep.inventory:
        source_questions = {field['key']: field['label'] for field in prep.inventory['fields']}
        if (any(field['label'] != source_questions.get(field['key']) for field in version.fields)
                or any(field['label'] != source_questions.get(field['key']) for field in prep.candidate_info['fields'])):
            raise ValidationError('The approved source-question boundaries changed.')
    from .tab_review import signature_label
    from documents.preparation import SIGNING
    originals = {f['key']: f for f in prep.candidate_info['fields']}
    if any((signature_label(originals[f['key']]['label']) and not signature_label(f['label']))
           or (SIGNING.search(originals[f['key']]['label']) and originals[f['key']]['label']!=f['label']) for f in version.fields):
        raise ValidationError('The approved signing protection changed.')
    prepared = private_path(version.prepared_path)
    if hashlib.sha256(read_original(prepared)).hexdigest() != version.prepared_sha256:
        raise ValidationError('Prepared form integrity check failed.')
    return prepared


def export_layout_for_version(version):
    """Read only the exact layout policy sealed by an immutable preparation."""
    source_for_version(version)
    if not version.preparation_id:
        return None
    info=version.preparation.candidate_info
    if 'export_layout' not in info:
        return None  # Existing approvals keep their existing export behavior.
    if info['export_layout'] is None:
        raise ValidationError('The prepared export layout policy is invalid.')
    from documents.service import validate_export_layout
    return validate_export_layout(info['export_layout'],version.prepared_sha256,version.document_backend)
