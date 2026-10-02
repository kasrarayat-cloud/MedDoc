"""Small trusted parent: opaque paths in, isolated parser result out."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile

MAX_UPLOAD = 10 * 1024 * 1024
MAX_OUTPUT = 30 * 1024 * 1024
TIMEOUT_SECONDS = 20


class DocumentError(ValueError):
    def __init__(self, message: str, code: str = "invalid_document"):
        super().__init__(message)
        self.code = code


def word_engine():
    """The Word contract used for NEW inspections: 'v3', 'legacy' or deterministic 'auto'. Stored mappings always fill under the
    contract they were made with."""
    try:
        from django.conf import settings
        value = getattr(settings, "QUILLMD_WORD_ENGINE", "legacy")
    except Exception:
        value = "legacy"
    return value if value in ("v3", "legacy", "auto") else "legacy"


def engine_fingerprint(engine, *, source_sha256=''):
    """Identity of the code/dependencies that can read or write the bound DOCX.

    A later release cannot silently execute a different writer under a stored
    engine name. It must retain this processor or use an explicit new revision.
    """
    if engine not in ('legacy', 'v3'):
        raise DocumentError('Unknown stored Word engine.', 'stale_mapping')
    modules = ('service.py', 'engine.py', 'worker.py', 'sandbox.py', 'word_v3.py',
               'source_policy.py', 'mapping_limits.py', 'tab_form.py', 'layout.py',
               'layout_source.py', 'layout_transport.py', 'layout_server.py', 'layout_pdf_worker.py',
               'import_selection.py', 'sdk_service.py', 'sdk_sandbox.py')
    processor = hashlib.sha256(engine.encode())
    try:
        for name in modules:
            processor.update(name.encode()); processor.update(Path(__file__).with_name(name).read_bytes())
        for package in ('python-docx', 'lxml', 'pypdf', 'reportlab'):
            processor.update(package.encode()); processor.update(importlib.metadata.version(package).encode())
        from .sdk_service import WM_IOV_SHA256, configuration
        if source_sha256 == WM_IOV_SHA256:
            _, manifest, expected = configuration()
            actual = hashlib.sha256(manifest.read_bytes()).hexdigest()
            if actual != expected:
                raise DocumentError('The qualified Word processor identity changed.', 'stale_mapping')
            processor.update(actual.encode())
    except (OSError, importlib.metadata.PackageNotFoundError) as exc:
        raise DocumentError('The stored Word processor identity is unavailable.', 'stale_mapping') from exc
    return processor.hexdigest()


def _run(path, operation, mapping=None, answers=None, output_path=None, *,
         document_backend=None, reviewed_requirements=None, trusted_context=None, claim_variants=None,
         engine=None, targets=None):
    source = Path(path)
    try:
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise DocumentError("The original is unavailable.", "source_unavailable") from exc
    with os.fdopen(fd, "rb") as original:
        meta = os.fstat(original.fileno())
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= MAX_UPLOAD:
            raise DocumentError("Upload a regular file between 1 byte and 10 MiB.", "upload_limit")
        payload = original.read(MAX_UPLOAD + 1)
    if len(payload) > MAX_UPLOAD:
        raise DocumentError("The upload exceeds 10 MiB.", "upload_limit")
    digest = hashlib.sha256(payload).hexdigest()
    if payload.startswith(b"PK\x03\x04"):
        suffix = ".docx"
    elif payload.startswith(b"%PDF-"):
        suffix = ".pdf"
    else:
        raise DocumentError("Only DOCX and PDF documents are supported.", "unsupported_format")
    target = Path(output_path) if output_path is not None else None
    if target is not None and (target.resolve() == source.resolve() or target.exists() or target.is_symlink()):
        raise DocumentError("Export must use a new file; originals and existing exports cannot be overwritten.", "immutable_original")
    with tempfile.TemporaryDirectory(prefix="quillmd-parser-") as directory:
        workspace = Path(directory)
        (workspace / ("input" + suffix)).write_bytes(payload)
        request = {"operation": operation, "format": suffix[1:], "mapping": mapping, "answers": answers,
                   "engine": engine or "legacy", "targets": targets}
        raw_request = json.dumps(request, ensure_ascii=False).encode()
        if len(raw_request) > 2 * 1024 * 1024:
            raise DocumentError("Mapping and answers exceed the 2 MiB processing limit.", "answer_limit")
        (workspace / "request.json").write_bytes(raw_request)
        from .sdk_service import WM_IOV_SHA256, run as run_sdk, SdkUnavailable
        if suffix == ".docx" and digest == WM_IOV_SHA256:
            if operation == "roles":
                # The qualified WM form keeps its own reviewed contract; its roles are not read by this parser.
                raise DocumentError("The qualified Word form keeps its own mapping contract.", "unsupported_format")
            sdk_request = {"operation": operation}
            if operation != "inspect":
                metadata = document_backend or {}
                if metadata.get('source_sha256') != digest or metadata.get('backend') != 'wm-iov-foss-v2':
                    raise DocumentError("The Word mapping does not identify this original.", "stale_mapping")
                sdk_request.update(mapping_digest=metadata.get('mapping_digest'), answers=answers)
                if claim_variants is not None:
                    sdk_request['claim_variants'] = claim_variants
                if reviewed_requirements is not None:
                    sdk_request['reviewed_requirements'] = reviewed_requirements
                if trusted_context is not None:
                    sdk_request['trusted_context'] = trusted_context
            try:
                response = run_sdk(workspace, sdk_request)
            except (SdkUnavailable, ValueError) as exc:
                if isinstance(exc, DocumentError):
                    raise
                raise DocumentError(str(exc), "advanced_processor_unavailable") from None
        else:
            if operation == "resolve" or document_backend:
                raise DocumentError("The advanced Word mapping does not match this original.", "stale_mapping")
            worker = Path(__file__).with_name("worker.py").resolve()
            try:
                result = subprocess.run(
                    [sys.executable, "-I", "-B", str(worker), str(workspace)],
                    cwd=workspace,
                    env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "TZ": "UTC"},
                    capture_output=True, timeout=TIMEOUT_SECONDS, check=False,
                    start_new_session=True,
                )
            except subprocess.TimeoutExpired as exc:
                raise DocumentError("Document processing exceeded its time limit.", "parser_timeout") from exc
            if result.returncode != 0:
                raise DocumentError("The isolated document processor failed or reached a resource limit.", "parser_failed")
            try:
                response = json.loads(result.stdout)
            except (ValueError, UnicodeError) as exc:
                raise DocumentError("The isolated document processor returned an invalid response.", "parser_failed") from exc
        needs_layout = response.get("code") == "layout_verification_required"
        imported = response.get('import_manifest')
        if (operation == "inspect" and response.get("layout_pending")) or needs_layout:
            from .layout_transport import verify_document
            try:
                verified, actual = verify_document(payload, mapping if needs_layout else None,
                                                   answers if needs_layout else None)
            except DocumentError as exc:
                if needs_layout:
                    raise
                response["warnings"].append(str(exc))
            else:
                response = {"format": "docx", "contract": "v3", "adapter": "word-v3",
                    "sandbox": "landlock+seccomp", "fields": mapping if needs_layout else verified["fields"],
                    "warnings": verified["warnings"], "layout_receipt": verified["receipt"]}
                if imported:
                    from .import_selection import digest as mapping_digest
                    response['import_manifest'] = {**imported, 'mapping_sha256': mapping_digest(response['fields']),
                                                   'initial_mapping_sha256': mapping_digest(response['fields'])}
                if needs_layout:
                    if operation in ("effective_options", "effective_values"):
                        response["states"] = verified["states"]
                    else:
                        (workspace / "output.docx").write_bytes(actual)
                        response["filled"] = sum(answers.get(field["key"]) not in (None, "", []) for field in mapping)
                        response["missing"] = [field["key"] for field in mapping if answers.get(field["key"]) in (None, "", [])]
        if "error" in response:
            raise DocumentError(response["error"], response.get("code", "invalid_document"))
        response["sha256"] = digest
        if operation == 'inspect' and suffix == '.docx':
            if not response.get('import_manifest'):
                # The independently qualified native WM adapter bypasses the
                # generic detector and retains its established backend contract.
                from .import_selection import manifest
                response['import_manifest'] = manifest('legacy', response['fields'],
                    {'automatic_complete': False, 'review_required': True, 'qualified_backend': response.get('adapter')})
            response['import_manifest']['source_sha256'] = digest
            selected = response['import_manifest']['engine']
            response['import_manifest']['engine_code_sha256'] = engine_fingerprint(selected, source_sha256=digest)
        if target is not None:
            export = workspace / ("output" + suffix)
            if not export.is_file() or export.is_symlink() or not 0 < export.stat().st_size <= MAX_OUTPUT:
                raise DocumentError("The document export is invalid.", "invalid_export")
            if suffix == ".docx" and response.get("contract") != "v3":
                # Output-only WM pagination: each limb repeats its own heading/units; long location
                # rows may flow across pages. Applied before hashing, so the recorded export_sha256
                # describes the stored bytes and the uploaded original is never rewritten.
                from .layout import repair_export
                response["layout"] = repair_export(export)
                if not 0 < export.stat().st_size <= MAX_OUTPUT:
                    raise DocumentError("The document export is invalid.", "invalid_export")
            # O_EXCL also protects against a concurrent export or symlink swap.
            try:
                out_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            except FileExistsError as exc:
                raise DocumentError("The export destination already exists.", "immutable_original") from exc
            try:
                with os.fdopen(out_fd, "wb") as destination, export.open("rb") as incoming:
                    shutil.copyfileobj(incoming, destination)
            except BaseException:
                target.unlink(missing_ok=True)
                raise
            response["output_sha256"] = hashlib.sha256(export.read_bytes()).hexdigest()
        return response


def inspect_template(path, *, engine=None):
    """Inspect a newly stored original. Raises DocumentError for unsafe/unsupported files."""
    return _run(path, "inspect", engine=engine or word_engine())


def outline_template(path):
    """Every place of a contract v3 Word original a clinician can map by hand (read-only)."""
    return _run(path, "outline", engine="v3")


def assistance_outline(path):
    """Full source text for blank-only mapping compilation; still processed in the isolated parser."""
    return _run(path, "assistance_outline", engine="v3")


def locate_fields(path, targets: list):
    """Clinician-chosen places -> contract v3 fields with verified anchors (recorded as manual)."""
    if not isinstance(targets, list) or len(targets) > 200:
        raise DocumentError("Add at most 200 fields at a time.", "invalid_mapping")
    return _run(path, "locate", engine="v3", targets=targets)


def destination_roles(path, mapping: list, *, engine):
    """The original's destination roles, read in the isolated parser from a FRESH inspection (never from the stored
    mapping): for a contract v3 original, every role place and each mapping field that touches one it may not take;
    for a legacy original, each stored field's printed label and the role the engine's kind rule gives it."""
    if not isinstance(mapping, list) or len(mapping) > 1500 or engine not in ("v3", "legacy"):
        raise DocumentError("Destination role mapping is invalid.", "invalid_mapping")
    return _run(path, "roles", mapping, None, engine=engine)


def effective_options(path, mapping: list, answers: dict):
    """Read the constrained controls after their actual writes, inside the sandbox.

    No export is persisted and the original remains untouched. Existing upload,
    request, memory/CPU and process-time bounds apply to this operation too.
    """
    if not isinstance(mapping, list) or not 0 < len(mapping) <= 1500 or not isinstance(answers, dict):
        raise DocumentError("Constrained option mapping is invalid.", "invalid_mapping")
    return _run(path, "effective_options", mapping, answers, engine="v3")


def effective_values(path, mapping: list, answers: dict):
    """Source-bound scalar and option read-back under the existing sandbox limits."""
    if not isinstance(mapping, list) or not 0 < len(mapping) <= 1500 or not isinstance(answers, dict):
        raise DocumentError("Constrained answer mapping is invalid.", "invalid_mapping")
    return _run(path, "effective_values", mapping, answers, engine="v3")


def fill_template(original_path, mapping: list, answers: dict, output_path, *,
                  document_backend=None, reviewed_requirements=None, trusted_context=None, claim_variants=None):
    """Fill only the verified original's mapped fields, writing a new private file."""
    if not isinstance(mapping, list) or not isinstance(answers, dict):
        raise DocumentError("Mapping must be a list and answers must be a dictionary.", "invalid_mapping")
    return _run(original_path, "fill", mapping, answers, output_path,
                document_backend=document_backend, reviewed_requirements=reviewed_requirements,
                trusted_context=trusted_context, claim_variants=claim_variants)


def resolve_template(original_path, document_backend: dict, answers: dict, *, claim_variants=None, trusted_context=None):
    """Materialize trusted template assertions for the current reviewed answers."""
    if not isinstance(document_backend, dict) or not isinstance(answers, dict):
        raise DocumentError("The Word mapping and answers are invalid.", "invalid_mapping")
    return _run(original_path, "resolve", answers=answers, document_backend=document_backend,
                claim_variants=claim_variants, trusted_context=trusted_context)
