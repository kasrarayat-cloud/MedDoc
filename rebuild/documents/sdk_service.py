"""Trusted parent for the qualified Word helper; document parsing stays isolated."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import sys
import time

WM_IOV_SHA256 = 'c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b'
BACKEND = 'wm-iov-foss-v2'
MAX_REQUEST = 2 * 1024 * 1024
MAX_RESPONSE = 1024 * 1024
TIMEOUT_SECONDS = 30
SLOT_TIMEOUT_SECONDS = 8


class SdkUnavailable(ValueError):
    pass


# The private synthetic service's launcher-fixed state root and its reviewed Word installation.
PRIVATE_MANAGED_STATE = Path('/var/lib/quillmd')
PRIVATE_MANAGED_WORD = Path('/opt/meddoc-pro/rebuild/.word-sdk')


def _production_managed_roots():
    """(state root, Word root) of the ACTIVATED production profile, or None.

    Read only when the launcher-fixed state root is not the private one, so the private service
    never depends on the production record. Any refusal of the record is simply 'not production'.
    """
    try:
        from ops import deployment_profile
        profile = deployment_profile.load_production()
    except Exception:  # noqa: BLE001 - a missing/unactivated/mixed record is not a managed root
        return None
    return profile.state_root, profile.word_sdk_root


def _managed_state(state):
    if state == PRIVATE_MANAGED_STATE:
        return True
    roots = _production_managed_roots()
    return roots is not None and state == roots[0]


def _managed_word_root():
    """The reviewed Word installation paired with the launcher-fixed state root.

    Only the production state root selects the production installation; every other value keeps the
    private installation exactly as before, so a private service can never be pointed elsewhere.
    """
    state = os.getenv('QUILLMD_STATE_DIR', '')
    if state and Path(state) != PRIVATE_MANAGED_STATE:
        roots = _production_managed_roots()
        if roots is not None and Path(state) == roots[0]:
            return roots[1]
    return PRIVATE_MANAGED_WORD


@contextmanager
def _processing_slot():
    """One native helper across doctor/admin/worker; bound aggregate memory."""
    state = Path(os.getenv('QUILLMD_STATE_DIR', str(Path(__file__).resolve().parents[1] / '.runtime')))
    if not state.is_absolute() or state.resolve() != state:
        raise SdkUnavailable('The Word processing state directory is invalid.')
    root = state / 'proofs'
    if os.getenv('QUILLMD_ENV_MANAGED') == '1':
        if not _managed_state(state) or not root.is_dir():
            raise SdkUnavailable('The managed Word processing state is unavailable.')
    else:
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise SdkUnavailable('The Word processing lock directory is not private.')
    fd = os.open(root / 'word-processor.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            raise SdkUnavailable('The Word processing lock is not a private regular file.')
        deadline = time.monotonic() + SLOT_TIMEOUT_SECONDS
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise SdkUnavailable('Another Word document is being processed. Retry shortly; no document was finalized.') from None
                time.sleep(0.05)
        yield
    finally:
        os.close(fd)


def configuration():
    names = ('QUILLMD_WORD_RUNTIME', 'QUILLMD_WORD_MANIFEST', 'QUILLMD_WORD_MANIFEST_SHA256')
    values = {name: os.getenv(name, '') for name in names}
    if not all(values.values()):
        raise SdkUnavailable('The qualified WM IOV processor is not installed. The original was not changed.')
    runtime = Path(values[names[0]])
    manifest = Path(values[names[1]])
    digest = values[names[2]]
    if (not runtime.is_absolute() or not manifest.is_absolute()
            or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest)):
        raise SdkUnavailable('The qualified Word processor configuration is invalid.')
    # The systemd launcher fixes this managed flag; operator qualification and
    # CI use their isolated local artifacts. Production never uses app-owned code.
    if os.getenv('QUILLMD_ENV_MANAGED') == '1':
        approved = _managed_word_root()
        if not runtime.is_relative_to(approved) or not manifest.is_relative_to(approved):
            raise SdkUnavailable('The managed Word processor must use the reviewed application installation.')
        for path in (approved, runtime, manifest):
            try:
                info = path.lstat()
                if (stat.S_ISLNK(info.st_mode) or info.st_uid == os.getuid()
                        or info.st_mode & 0o022 or os.access(path, os.W_OK)):
                    raise SdkUnavailable('The application cannot own or modify its Word processor.')
            except OSError:
                raise SdkUnavailable('The reviewed Word processor installation is unavailable.') from None
    return runtime, manifest, digest


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate processor response property.')
        result[key] = value
    return result


def _bounded_process(command, workspace, environment):
    """Drain both pipes with strict limits; never accumulate unlimited diagnostics."""
    try:
        process = subprocess.Popen(command, cwd=workspace, env=environment,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True)
    except OSError:
        raise SdkUnavailable('The isolated Word processor could not start.') from None
    output = bytearray()
    stderr_count = 0
    deadline = time.monotonic() + TIMEOUT_SECONDS
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ, 'stdout')
            selector.register(process.stderr, selectors.EVENT_READ, 'stderr')
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SdkUnavailable('Word processing reached its time limit. No document was finalized.')
                for key, _ in selector.select(remaining):
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == 'stdout':
                        if len(output) + len(chunk) > MAX_RESPONSE:
                            raise SdkUnavailable('The Word processor response exceeded its limit.')
                        output.extend(chunk)
                    else:
                        stderr_count += len(chunk)
                        if stderr_count > 65536:
                            raise SdkUnavailable('The Word processor diagnostics exceeded their limit.')
            try:
                code = process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise SdkUnavailable('Word processing reached its time limit. No document was finalized.') from None
        return code, bytes(output)
    finally:
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        process.stdout.close()
        process.stderr.close()


def run(workspace: Path, request: dict):
    """Run a fixed qualified backend in an existing private job workspace."""
    runtime, manifest, digest = configuration()
    if request.get('operation') not in ('inspect', 'resolve', 'fill'):
        raise ValueError('Unsupported Word operation.')
    raw = json.dumps(request, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > MAX_REQUEST:
        raise ValueError('Mapping, evidence and answers exceed the 2 MiB processing limit. Nothing was truncated.')
    (workspace / 'request.json').write_bytes(raw)
    launcher = Path(__file__).with_name('sdk_sandbox.py').resolve()
    command = [sys.executable, '-I', '-B', str(launcher), '--runtime', str(runtime),
               '--manifest', str(manifest), '--manifest-sha', digest, '--workspace', str(workspace)]
    environment = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TZ': 'UTC'}
    managed = os.getenv('QUILLMD_ENV_MANAGED') == '1'
    if managed:
        environment['QUILLMD_ENV_MANAGED'] = '1'
    if os.getenv('QUILLMD_WORD_QUALIFICATION') == '1':
        if managed:
            raise SdkUnavailable('Qualification mode is unavailable to managed application services.')
        command.append('--qualification')
        environment['QUILLMD_WORD_QUALIFICATION'] = '1'
    with _processing_slot():
        code, stdout = _bounded_process(command, workspace, environment)
    if code not in (0, 2) or not stdout:
        raise SdkUnavailable('The isolated Word processor failed or reached a resource limit.')
    try:
        response = json.loads(stdout, object_pairs_hook=_object_pairs)
    except (ValueError, UnicodeError, RecursionError):
        raise SdkUnavailable('The isolated Word processor returned an invalid response.') from None
    if not isinstance(response, dict):
        raise SdkUnavailable('The isolated Word processor returned an invalid result.')
    if 'error' in response:
        # Fixed parent messages prevent even a malformed helper reply echoing
        # source text, paths or diagnostics to the browser.
        from .service import DocumentError
        messages = {
            'unsupported_original': 'This original does not match the qualified WM IOV template.',
            'stale_mapping': 'The Word mapping changed. Review the current template version.',
            'stale_review': 'The source, answers or review changed. Review the current revision.',
            'review_required': 'Review every answer and prewritten statement before finalizing.',
            'unsupported_assertion': 'A prewritten statement lacks complete matching source evidence.',
            'unsupported_answer': 'An answer lacks complete matching source evidence.',
            'template_conflict': 'The selected answers conflict with a prewritten statement.',
            'signer_mismatch': 'The document identity does not match the authenticated clinician.',
            'invalid_choice': 'Select an available template choice or mark it missing.',
            'invalid_measurement': 'A measurement needs its documented value and matching unit.',
            'missing_assertion_answer': 'A prewritten statement contains an unanswered required field.',
            'output_limit': 'The document exceeds the export limit. Nothing was truncated.',
        }
        error_code = response.get('code')
        if not isinstance(error_code, str) or error_code not in messages:
            raise SdkUnavailable('The qualified Word processor refused this operation.')
        raise DocumentError(messages[error_code], error_code)
    if code or response.get('backend') != BACKEND or response.get('source_sha256') != WM_IOV_SHA256:
        raise SdkUnavailable('The Word processor backend identity differs from the qualified release.')
    if request['operation'] == 'inspect':
        fields = response.get('fields')
        requirements = response.get('review_requirements')
        if (response.get('format') != 'docx' or response.get('source_sha256') != WM_IOV_SHA256
                or not isinstance(fields, list) or len(fields) != 90
                or not isinstance(requirements, list) or len(requirements) != 14
                or any(not isinstance(f, dict) or not isinstance(f.get('key'), str) for f in fields)
                or len({f['key'] for f in fields}) != 90):
            raise SdkUnavailable('The qualified Word mapping is incomplete.')
    return response
