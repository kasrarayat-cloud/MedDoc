"""Small trusted parent: opaque paths in, isolated parser result out."""

from __future__ import annotations

import hashlib
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


def _run(path, operation, mapping=None, answers=None, output_path=None, *,
         document_backend=None, reviewed_requirements=None, trusted_context=None, claim_variants=None):
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
        request = {"operation": operation, "format": suffix[1:], "mapping": mapping, "answers": answers}
        raw_request = json.dumps(request, ensure_ascii=False).encode()
        if len(raw_request) > 2 * 1024 * 1024:
            raise DocumentError("Mapping and answers exceed the 2 MiB processing limit.", "answer_limit")
        (workspace / "request.json").write_bytes(raw_request)
        from .sdk_service import WM_IOV_SHA256, run as run_sdk, SdkUnavailable
        if suffix == ".docx" and digest == WM_IOV_SHA256:
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
        if "error" in response:
            raise DocumentError(response["error"], response.get("code", "invalid_document"))
        response["sha256"] = digest
        if target is not None:
            export = workspace / ("output" + suffix)
            if not export.is_file() or export.is_symlink() or not 0 < export.stat().st_size <= MAX_OUTPUT:
                raise DocumentError("The document export is invalid.", "invalid_export")
            if suffix == ".docx":
                # Output-layout safeguards only: heading rows keep with the measurements they label, and
                # no row splits across a page. Applied HERE, on the way out, so the customer's uploaded
                # original is never rewritten — and before the caller hashes the file, so the recorded
                # export_sha256 describes the bytes that are actually stored.
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


def inspect_template(path):
    """Inspect a newly stored original. Raises DocumentError for unsafe/unsupported files."""
    return _run(path, "inspect")


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
