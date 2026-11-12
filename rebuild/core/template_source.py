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

#: ⚠️ FINDING SI-4 (2026-11-01). Codes of the original check that say the CHECK could not run — the
#: worker timed out, died or hit a resource limit, the sandbox or the worker itself could not start
#: (GR-1: documents.check_original reports a spawn or workspace failure as sandbox_unavailable), or
#: the stored file changed or vanished between two reads — and nothing about the form. Every other
#: code is a verdict about the file (unsafe_upload, unreadable_pdf, invalid_document, upload_limit,
#: unsupported_format). Treating a worker failure as a verdict told a doctor to replace a clean form
#: and, on the voice route, deleted the recording they had just dictated.
CHECK_UNAVAILABLE_CODES = frozenset(('parser_timeout', 'parser_failed', 'sandbox_unavailable',
                                     'source_unavailable', 'source_changed'))
CHECK_UNAVAILABLE_MESSAGE = ('QuillMD could not check this form right now. Nothing was sent for processing and '
                             'nothing was charged. This is a temporary problem on our side, not a verdict about '
                             'your form: try again in a few minutes.')


class PdfTemplateRefused(ValidationError):
    """The stored PDF original is refused by the active-content check: a verdict about the file.
    `code` is the check's code (unsafe_upload, unreadable_pdf, ...)."""


class PdfTemplateCheckUnavailable(ValidationError):
    """The check could not run (`code` says why). Never a verdict about the form: the caller keeps the
    doctor's work, offers to try again, and sends nothing."""


def check_pdf_original(template):
    """Run the download gate's isolated-worker check on `template`'s stored PDF original. Returns
    normally when the original may be used and served; raises PdfTemplateRefused (a verdict about the
    file) or PdfTemplateCheckUnavailable (the check could not run). Nothing else escapes the check, so
    no caller can mistake a worker failure for a verdict, or turn one into a 500.

    ⚠️ GR-1 (2026-11-01): a check that could not even start raised a plain OSError past every gate
    (500s, a voice upload left on disk unaudited, an encounter form's typed notes lost). check_original
    now reports that as sandbox_unavailable, and anything else the check raises that is not its own
    DocumentError is a check that could not run as well, never a verdict about the file."""
    from documents import check_original, DocumentError
    path = private_path(template.original_path)
    try:
        check_original(path, expected_sha256=template.sha256)
    except DocumentError as exc:
        if exc.code in CHECK_UNAVAILABLE_CODES:
            raise PdfTemplateCheckUnavailable(CHECK_UNAVAILABLE_MESSAGE, code=exc.code) from None
        raise PdfTemplateRefused(str(exc), code=exc.code) from None
    except Exception:
        raise PdfTemplateCheckUnavailable(CHECK_UNAVAILABLE_MESSAGE, code='sandbox_unavailable') from None


def assert_pdf_template_usable(template):
    """⚠️ FINDING DL-2. A PDF template accepted before the raw scan existed is still stored, and its
    original is read only at finalize. So a form the download gate now refuses stayed selectable: a
    doctor could create an encounter on it and spend a paid generation, learning only at finalize
    that it can never produce a document. This runs the same isolated-worker active-content check as
    the download, on the stored original. DOCX originals are validated by source_for_version; this is
    PDF only. A missing (or changed) original is left to the step that reads it, so this never blocks
    work for a file that is simply not there.

    ⚠️ P1 round 4 (2026-11-01): it runs synchronously only where refusing loses nothing the doctor
    entered — encounter creation (the form is shown again with the typed notes) and the generate
    request (the notes are saved) — and, through provider_refusal, in the WORKER immediately before
    every provider call. The enqueue-time guards of rounds 2 and 3 are gone.

    ⚠️ SI-4: a refusal raises PdfTemplateRefused ("can no longer be used"); a check that could not
    run raises PdfTemplateCheckUnavailable ("try again"), and callers must never discard the
    doctor's input for that one. Both are ValidationErrors, so every caller sends nothing. ⚠️ GR-1:
    an original that exists but cannot be read (any read error but its absence) is a check that could
    not run, not a reason to skip it."""
    if (template.format or '').lower() != 'pdf':
        return
    path = private_path(template.original_path)
    try:
        data = path.read_bytes()
    except (FileNotFoundError, NotADirectoryError):
        return
    except OSError:
        raise PdfTemplateCheckUnavailable(CHECK_UNAVAILABLE_MESSAGE, code='source_unavailable') from None
    if hashlib.sha256(data).hexdigest() != template.sha256:
        return
    try:
        check_pdf_original(template)
    except PdfTemplateRefused as exc:
        raise PdfTemplateRefused('This form can no longer be used: ' + exc.messages[0] + ' Upload a clean PDF as '
                                 'a new form. Nothing was sent for processing and nothing was charged.',
                                 code=exc.code) from None


#: ⚠️ P1 ROUND 4 (2026-11-01). What a job, a coding run or a recheck records when the worker stops it
#: before its provider call. Fixed sentences, never the checker's own text: a job's error is shown to
#: the doctor and kept as billing evidence, and a not-processed job error leaves about 150 characters
#: for its reason. Both start with FORM_JOB_PREFIX, which coding_service.failure_message shows as is.
FORM_JOB_PREFIX = 'The PDF form of this document '
FORM_REFUSED_FOR_JOB = FORM_JOB_PREFIX + ('can no longer be used: it failed the active-content check. Upload a '
                                          'clean PDF as a new form.')
FORM_UNCHECKED_FOR_JOB = FORM_JOB_PREFIX + ('could not be checked right now. This is a temporary problem on our '
                                            'side, not a verdict about the form.')


def provider_refusal(template):
    """⚠️ P1 ROUND 4 (2026-11-01): THE guard on provider usage for an encounter's PDF form. The worker
    calls it IMMEDIATELY BEFORE every provider call — generation and transcription (core.jobs.run_one),
    the semantic generation stages (core.jobs.run_semantic_job), the semantic recheck
    (core.semantic_revalidation.run) and coding (core.coding_service.run_one) — so it covers every
    request however and whenever it was queued, one queued before this check existed included, and the
    request paths that carry a doctor's input (a recording, saved answers) no longer run it at all.

    Returns None when the call may go ahead; otherwise the fixed sentence the job fails with, through
    that path's existing not-sent failure: no provider call, no usage, the hold released. It never
    raises: a refusal is FORM_REFUSED_FOR_JOB, and anything else that goes wrong — the check timing
    out, failing or failing to start (GR-1), or this guard itself — is a check that could not run,
    FORM_UNCHECKED_FOR_JOB. A missing or changed original is left to the step that reads it, exactly
    as assert_pdf_template_usable leaves it."""
    try:
        assert_pdf_template_usable(template)
    except PdfTemplateRefused:
        return FORM_REFUSED_FOR_JOB
    except Exception:
        return FORM_UNCHECKED_FOR_JOB
    return None


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
