"""The extraction child process: ``python -m studio.ingest._child``.

Protocol: stdin carries one JSON header line, then exactly ``size`` document
bytes; stdout receives one JSON ExtractionResult and the process exits 0. A
malformed request, or a process that cannot be made non-dumpable, exits 2
with a reason on stderr. The parent has already applied resource limits, a
minimal environment and a private ``workdir``.

Never imports Django.
"""
from __future__ import annotations

import ctypes
import json
import sys
import time

from studio.ingest.extract import Limits
from studio.ingest.ocr import OcrTools
from studio.ingest.text import INGEST_VERSION, METHOD_FOR_KIND, extract_txt, failed
from studio.types import ExtractionResult, to_jsonable

MAX_HEADER_BYTES = 64 * 1024
PR_SET_DUMPABLE = 4


class StartupError(Exception):
    pass


def disable_core_dumps() -> None:
    """RLIMIT_CORE=0 does not stop a piped core_pattern (apport, systemd-coredump);
    a non-dumpable process is never dumped, so document bytes never reach a crash file."""
    if ctypes.CDLL(None, use_errno=True).prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        raise StartupError(f'cannot disable core dumps (errno {ctypes.get_errno()})')


def read_request(stream) -> tuple[dict, bytes]:
    line = stream.readline(MAX_HEADER_BYTES)
    if not line.endswith(b'\n'):
        raise StartupError('missing or oversized header line')
    header = json.loads(line)
    data = stream.read(header['size'])
    if len(data) != header['size'] or stream.read(1):
        raise StartupError('document length does not match the header')
    return header, data


def parse(data: bytes, kind: str, limits: Limits, tools: OcrTools | None, deadline: float,
          workdir: str) -> ExtractionResult:
    if kind == 'pdf':
        from studio.ingest.pdf import extract_pdf
        return extract_pdf(data, limits, tools, deadline, workdir)
    if kind == 'docx':
        from studio.ingest.docx import extract_docx
        return extract_docx(data, limits)
    return extract_txt(data, limits)


def guarded_parse(data, kind, limits, tools, deadline, workdir) -> ExtractionResult:
    """Parse; an unexpected error fails this document instead of the process."""
    method, engine = METHOD_FOR_KIND[kind], {'ingest': INGEST_VERSION}
    try:
        return parse(data, kind, limits, tools, deadline, workdir)
    except MemoryError:
        return failed(method, engine, 'The document needs more memory to read than the extraction limit allows.')
    except Exception as exc:
        return failed(method, engine,
                      f'The document could not be read: the extractor stopped unexpectedly ({type(exc).__name__}).')


def main() -> int:
    started = time.monotonic()
    try:
        disable_core_dumps()
        header, data = read_request(sys.stdin.buffer)
        kind = header['kind']
        if kind not in METHOD_FOR_KIND:
            raise StartupError(f'unknown document kind {kind!r}')
        limits = Limits(**header['limits'])
        tools = OcrTools(**header['ocr']) if header['ocr'] else None
        deadline = started + float(header['budget_s'])
        workdir = header['workdir']
    except (StartupError, ValueError, KeyError, TypeError) as exc:
        sys.stderr.write(f'extraction child: cannot start: {exc}\n')
        return 2
    result = guarded_parse(data, kind, limits, tools, deadline, workdir)
    sys.stdout.buffer.write(json.dumps(to_jsonable(result), ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
    sys.stdout.buffer.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
