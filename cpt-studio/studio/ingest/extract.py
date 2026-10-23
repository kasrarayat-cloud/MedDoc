"""Document extraction entry points (ARCHITECTURE 5.1).

``extract_document`` never parses document bytes in the calling process. It
runs ``python -m studio.ingest._child`` in a new session with address-space,
CPU, file-size, process-count and core-dump limits, a minimal environment (no
service secrets) and a private work directory, and kills the child's whole
process group at the wall-clock deadline. Every outcome — a crash, a timeout,
an oversized or inconsistent result included — is an ExtractionResult; this
module raises only for programming errors, never for a bad document.

``extract_paste`` handles pasted text and addenda in-process: there is
nothing to parse.
"""
from __future__ import annotations

import functools
import json
import math
import os
import resource
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, fields
from importlib import metadata
from itertools import pairwise
from pathlib import Path

from studio.types import ExtractionResult, PageSpan

from .ocr import OcrTools, ocr_tools, signal_name, tool_env
from .text import (INGEST_VERSION, METHOD_FOR_KIND, PAGE_SEPARATOR, canonicalize, failed, format_seconds,
                   has_surrogates, pdf_method, single_page)

MIB = 1024 * 1024
SERVICE_DIR = Path(__file__).resolve().parents[2]
CHILD_ARGV = (sys.executable, '-m', 'studio.ingest._child')
DETECT = 'detect'  # extract_document(ocr=...): detect the server's OCR tools (cached)

MEDIA_KINDS = {'application/pdf': 'pdf',
               'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
               'text/plain': 'txt'}
EXTENSION_KINDS = {'.pdf': 'pdf', '.docx': 'docx', '.txt': 'txt'}
KIND_LABELS = {'pdf': 'PDF', 'docx': 'Word (DOCX)', 'txt': 'plain text'}
KIND_METHODS = {'pdf': {'pdf-text', 'pdf-ocr', 'pdf-mixed'}, 'docx': {'docx'}, 'txt': {'txt'}}
PASTE_NOUNS = {'paste': 'pasted text', 'addendum': 'addendum'}

AS_LIMIT_BYTES = 1536 * MIB
FILE_SIZE_FLOOR_BYTES = 256 * MIB  # the document copy plus one rendered page at a time
NPROC_HEADROOM = 64  # tasks beyond the uid's current count: the child, pdftoppm, tesseract, slack for peers
CPU_GRACE_S = 5  # SIGXCPU at the soft limit, SIGKILL this much later
PIPE_CHUNK = 64 * 1024
_FLOAT_LIMITS = frozenset({'timeout_s', 'ocr_page_timeout_s'})
_RESULT_FIELDS = tuple(f.name for f in fields(ExtractionResult))


@dataclass(frozen=True)
class Limits:
    timeout_s: float = 240
    max_pages: int = 40
    max_chars: int = 400_000
    ocr_dpi: int = 300
    ocr_page_timeout_s: float = 60
    min_text_chars_per_page: int = 20
    max_bytes: int = 15 * MIB

    def __post_init__(self):
        for item in fields(self):
            value = getattr(self, item.name)
            allowed = (int, float) if item.name in _FLOAT_LIMITS else (int,)
            if isinstance(value, bool) or not isinstance(value, allowed) or not 0 < value < math.inf:
                raise ValueError(f'Limits.{item.name} must be a positive finite number, not {value!r}.')


def extract_paste(text: str, *, method: str = 'paste', limits: Limits | None = None) -> ExtractionResult:
    """Pasted text or an addendum as one canonical page; failed when empty, invalid or too long."""
    if method not in PASTE_NOUNS:
        raise ValueError(f'extract_paste method must be one of {sorted(PASTE_NOUNS)}, not {method!r}.')
    if not isinstance(text, str):
        raise TypeError(f'extract_paste needs str, not {type(text).__name__}.')
    return single_page(canonicalize(text), method, limits or Limits(), PASTE_NOUNS[method],
                       {'ingest': INGEST_VERSION})


def extract_document(data: bytes, filename: str, media_type: str, *, limits: Limits | None = None,
                     ocr: OcrTools | None | str = DETECT) -> ExtractionResult:
    """Extract an uploaded PDF, DOCX or TXT in a sandboxed child process.

    ``ocr``: DETECT (default) uses this server's OCR tools if installed; None
    treats OCR as unavailable; an OcrTools uses exactly those tools.
    """
    limits = limits or Limits()
    kind = _kind(media_type)
    if not isinstance(data, bytes):
        raise TypeError(f'extract_document needs bytes, not {type(data).__name__}.')
    if not (ocr is None or isinstance(ocr, OcrTools) or ocr == DETECT):
        raise TypeError(f'ocr must be DETECT, None or OcrTools, not {ocr!r}.')
    method = METHOD_FOR_KIND[kind]
    engine = {'ingest': INGEST_VERSION}
    problem = _extension_problem(filename, kind) or _size_problem(data, limits)
    if problem:
        return failed(method, engine, problem)
    tools = ocr_tools() if ocr == DETECT else ocr
    try:
        workdir = tempfile.mkdtemp(prefix='cpt-ingest-')
    except OSError as exc:
        return failed(method, engine, f'Extraction could not start on this server ({_reason(exc)}).')
    try:
        header = {'kind': kind, 'size': len(data), 'budget_s': _child_budget(limits.timeout_s), 'workdir': workdir,
                  'limits': asdict(limits), 'ocr': asdict(tools) if tools else None}
        run = _run_child(json.dumps(header).encode('utf-8') + b'\n' + data, limits)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)  # the child is gone: _run_child reaped its group
    return _result(run, kind, method, limits, engine)


def engine_versions() -> dict[str, str]:
    """Versions of the extraction engines on this server, for display and audit."""
    versions = {'ingest': INGEST_VERSION, 'pypdf': metadata.version('pypdf'),
                'python-docx': metadata.version('python-docx')}
    tools = ocr_tools()
    if tools:
        return versions | {'tesseract': tools.tesseract_version, 'pdftoppm': tools.pdftoppm_version}
    return versions | {'ocr': 'not available'}


def _kind(media_type: str) -> str:
    kind = MEDIA_KINDS.get(media_type.split(';', 1)[0].strip().lower())
    if kind is None:
        raise ValueError(f'Unsupported media type for extraction: {media_type!r}.')
    return kind


def _extension_problem(filename: str, kind: str) -> str:
    suffix = Path(filename or '').suffix.lower()
    named = EXTENSION_KINDS.get(suffix)
    if named is None or named == kind:
        return ''
    return f'The file name ends in {suffix} but the file is {KIND_LABELS[kind]}.'


def _size_problem(data: bytes, limits: Limits) -> str:
    if not data:
        return 'The file is empty.'
    if len(data) > limits.max_bytes:
        size = f'{limits.max_bytes // MIB} MB' if limits.max_bytes % MIB == 0 else f'{limits.max_bytes:,} bytes'
        return f'The file is larger than {size}.'
    return ''


def _child_budget(timeout_s: float) -> float:
    """Time the child may spend before returning what it has: the parent's
    deadline less a reserve for start-up and for writing the result."""
    return timeout_s - min(10.0, timeout_s / 10)


# --- the child process ------------------------------------------------------------

@dataclass(frozen=True)
class _ChildRun:
    outcome: str  # exited | timeout | overflow | not_started
    returncode: int | None = None
    stdout: bytes = b''
    error: str = ''


def _run_child(payload: bytes, limits: Limits) -> _ChildRun:
    """Run CHILD_ARGV with ``payload`` on stdin; never leaves a process behind."""
    deadline = time.monotonic() + limits.timeout_s
    try:
        proc = subprocess.Popen(CHILD_ARGV, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                cwd=SERVICE_DIR, env=_child_env(), start_new_session=True,
                                preexec_fn=functools.partial(_apply_rlimits, _rlimits(limits)))
    except (OSError, subprocess.SubprocessError) as exc:
        return _ChildRun('not_started', error=_reason(exc))
    try:
        stdout, outcome = _exchange(proc, payload, deadline, 6 * limits.max_chars + MIB)
        if outcome == 'exited' and not _exited_by(proc.pid, deadline):
            outcome = 'timeout'
    finally:
        # The leader is not reaped yet, so its process-group id cannot have
        # been reused: this kills only the child and anything it started.
        _kill_group(proc.pid)
        returncode = proc.wait()
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()
    return _ChildRun(outcome, returncode, stdout)


def _reason(exc: Exception) -> str:
    """A short reason for a user-facing message: no paths, no internals."""
    return getattr(exc, 'strerror', None) or str(exc) or type(exc).__name__


def _child_env() -> dict[str, str]:
    return tool_env() | {'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1', 'PYTHONUTF8': '1'}


def _rlimits(limits: Limits) -> tuple[tuple[int, int, int], ...]:
    """(resource, soft, hard) for the child, computed before fork."""
    cpu_s = math.ceil(limits.timeout_s) + 1  # a backstop: the wall-clock kill comes first
    file_bytes = max(FILE_SIZE_FLOOR_BYTES, 2 * limits.max_bytes)
    tasks = _user_task_count() + NPROC_HEADROOM
    wanted = ((resource.RLIMIT_AS, AS_LIMIT_BYTES, AS_LIMIT_BYTES),
              (resource.RLIMIT_CPU, cpu_s, cpu_s + CPU_GRACE_S),
              (resource.RLIMIT_FSIZE, file_bytes, file_bytes),
              (resource.RLIMIT_NPROC, tasks, tasks),
              (resource.RLIMIT_CORE, 0, 0))
    return tuple((which, *_capped(which, soft, hard)) for which, soft, hard in wanted)


def _capped(which: int, soft: int, hard: int) -> tuple[int, int]:
    """Never ask for more than the current hard limit: raising it needs privilege."""
    current = resource.getrlimit(which)[1]
    if current != resource.RLIM_INFINITY:
        hard = min(hard, current)
    return min(soft, hard), hard


def _apply_rlimits(rlimits) -> None:
    # Runs in the forked child before exec: only precomputed setrlimit calls.
    for which, soft, hard in rlimits:
        resource.setrlimit(which, (soft, hard))


def _user_task_count() -> int:
    """Tasks (threads) the real uid owns now; RLIMIT_NPROC counts all of them."""
    uid = os.getuid()
    return sum(_tasks_owned_by(entry.name, uid) for entry in os.scandir('/proc') if entry.name.isdigit())


def _tasks_owned_by(pid: str, uid: int) -> int:
    try:
        with open(f'/proc/{pid}/status', 'rb') as handle:
            status = dict(line.split(b':', 1) for line in handle.read().splitlines() if b':' in line)
        owner, threads = int(status[b'Uid'].split()[0]), int(status[b'Threads'])
    except (OSError, KeyError, ValueError, IndexError):  # the process ended mid-scan
        return 0
    return threads if owner == uid else 0


def _exchange(proc: subprocess.Popen, payload: bytes, deadline: float, max_output: int) -> tuple[bytes, str]:
    """Feed stdin while draining stdout (kept, bounded) and stderr (discarded).

    Ends with 'exited' at EOF on both outputs, 'timeout' at the deadline, or
    'overflow' when stdout exceeds ``max_output`` bytes.
    """
    stdout = bytearray()
    pending = memoryview(payload)
    os.set_blocking(proc.stdin.fileno(), False)
    with selectors.DefaultSelector() as selector:
        selector.register(proc.stdin, selectors.EVENT_WRITE)
        selector.register(proc.stdout, selectors.EVENT_READ)
        selector.register(proc.stderr, selectors.EVENT_READ)
        open_outputs = 2
        while open_outputs:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return bytes(stdout), 'timeout'
            for key, _ in selector.select(remaining):
                if key.fileobj is proc.stdin:
                    pending = _feed(key.fd, pending)
                    if not pending:
                        selector.unregister(proc.stdin)
                        proc.stdin.close()
                    continue
                chunk = os.read(key.fd, PIPE_CHUNK)
                if not chunk:
                    selector.unregister(key.fileobj)
                    open_outputs -= 1
                elif key.fileobj is proc.stdout:
                    stdout += chunk
                    if len(stdout) > max_output:
                        return bytes(stdout), 'overflow'
    return bytes(stdout), 'exited'


def _feed(fd: int, pending: memoryview) -> memoryview:
    try:
        written = os.write(fd, pending[:PIPE_CHUNK])
    except BlockingIOError:
        return pending
    except BrokenPipeError:  # the child stopped reading; its exit status says why
        return pending[:0]
    return pending[written:]


def _exited_by(pid: int, deadline: float) -> bool:
    """Wait for the child to exit without reaping it (WNOWAIT)."""
    while os.waitid(os.P_PID, pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is None:
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.005)
    return True


def _kill_group(pgid: int) -> None:
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


# --- the child's answer -----------------------------------------------------------

def _result(run: _ChildRun, kind: str, method: str, limits: Limits, engine: dict) -> ExtractionResult:
    problem = _run_problem(run, limits)
    if problem:
        return failed(method, engine, problem)
    result = _parse_output(run.stdout)
    if result is None or not _consistent(result, kind, limits):
        return failed(method, engine, 'Extraction failed: the extractor returned an unreadable or inconsistent result.')
    return result


def _run_problem(run: _ChildRun, limits: Limits) -> str:
    if run.outcome == 'not_started':
        return f'Extraction could not start on this server ({run.error}).'
    if run.outcome == 'timeout':
        return f'Extraction stopped after {format_seconds(limits.timeout_s)} seconds.'
    if run.outcome == 'overflow':
        return 'Extraction stopped: the extractor produced more output than allowed.'
    if run.returncode > 0:
        return f'Extraction failed: the extraction process exited with status {run.returncode}.'
    if run.returncode < 0:
        return _signal_problem(-run.returncode)
    return ''


def _signal_problem(number: int) -> str:
    if number == signal.SIGXCPU:
        return 'Extraction stopped: the document needed more CPU time than allowed.'
    if number == signal.SIGXFSZ:
        return 'Extraction stopped: the document needed more temporary disk space than allowed.'
    if number == signal.SIGKILL:
        return ('Extraction stopped: the extraction process was killed, usually because the document '
                'needed more memory than allowed.')
    return f'Extraction failed: the extraction process crashed ({signal_name(number)}).'


def _parse_output(raw: bytes) -> ExtractionResult | None:
    """The child's JSON as an ExtractionResult, or None if it is not exactly that shape."""
    try:
        data = json.loads(raw)
        if set(data) != set(_RESULT_FIELDS):
            return None
        return ExtractionResult(
            status=_typed(data['status'], str), method=_typed(data['method'], str), text=_typed(data['text'], str),
            pages=tuple(PageSpan(page=_typed(span['page'], int), start=_typed(span['start'], int),
                                 end=_typed(span['end'], int)) for span in _typed(data['pages'], list)),
            messages=tuple(_typed(message, str) for message in _typed(data['messages'], list)),
            ocr_pages=tuple(_typed(page, int) for page in _typed(data['ocr_pages'], list)),
            engine={_typed(key, str): _typed(value, str) for key, value in _typed(data['engine'], dict).items()})
    except (ValueError, KeyError, TypeError, RecursionError):
        return None


def _typed(value, kind: type):
    if type(value) is not kind:  # exact: a bool is not an int here
        raise TypeError(f'expected {kind.__name__}')
    return value


def _consistent(result: ExtractionResult, kind: str, limits: Limits) -> bool:
    """Re-check every invariant the child promises before anything trusts its offsets."""
    if result.method not in KIND_METHODS[kind]:
        return False
    if result.status == 'failed':
        return not (result.text or result.pages or result.ocr_pages) and bool(result.messages)
    if result.status not in ('ok', 'partial') or (result.status == 'partial' and not result.messages):
        return False
    text, pages = result.text, result.pages
    if (not text.strip() or len(text) > limits.max_chars or canonicalize(text) != text or has_surrogates(text)
            or not pages or len(pages) > limits.max_pages):
        return False
    tiled = (all(span.page == number and span.start <= span.end for number, span in enumerate(pages, 1))
             and pages[0].start == 0 and pages[-1].end == len(text)
             and all(text[left.end:right.start] == PAGE_SEPARATOR for left, right in pairwise(pages)))
    if not tiled:
        return False
    ocr_pages = list(result.ocr_pages)
    if ocr_pages != sorted(set(ocr_pages)) or not set(ocr_pages) <= {span.page for span in pages}:
        return False
    if kind == 'pdf':
        return result.method == pdf_method(len(ocr_pages), len(pages))
    return result.status == 'ok' and len(pages) == 1 and not ocr_pages
