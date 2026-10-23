"""OCR with poppler's pdftoppm (render one page) and tesseract (recognise it).

Detection runs in the service process and is cached. Recognition runs only in
the extraction child, one page at a time, inside the child's private work
directory, under the child's resource limits and a per-page deadline.
"""
from __future__ import annotations

import contextlib
import functools
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass

from .text import canonicalize, format_seconds

OCR_LANGUAGE = 'eng'
PROBE_TIMEOUT_S = 10


@dataclass(frozen=True)
class OcrTools:
    tesseract: str  # absolute path
    pdftoppm: str  # absolute path
    tesseract_version: str  # first line of `tesseract --version`
    pdftoppm_version: str  # first line of `pdftoppm -v`


@dataclass(frozen=True)
class OcrOutcome:
    text: str | None  # canonical page text; None when the page was not read
    problem: str = ''  # why not, as a fragment for a user-facing message


class _ToolFailure(Exception):
    pass


def tool_env() -> dict[str, str]:
    """The minimal environment for OCR tools and the extraction child: no service secrets."""
    env = {'PATH': os.defpath, 'LC_ALL': 'C.UTF-8', 'OMP_THREAD_LIMIT': '1'}
    if os.environ.get('TESSDATA_PREFIX'):
        env['TESSDATA_PREFIX'] = os.environ['TESSDATA_PREFIX']
    return env


def signal_name(number: int) -> str:
    try:
        return signal.Signals(number).name
    except ValueError:
        return f'signal {number}'


def find_ocr_tools(search_path: str | None = None) -> OcrTools | None:
    """Working tesseract (with English data) and pdftoppm on ``search_path``
    (default: PATH), or None when either is missing or does not answer."""
    tesseract = shutil.which('tesseract', path=search_path)
    pdftoppm = shutil.which('pdftoppm', path=search_path)
    if not (tesseract and pdftoppm):
        return None
    tesseract_version = _first_line(_probe([tesseract, '--version']))
    pdftoppm_version = _first_line(_probe([pdftoppm, '-v']))
    languages = _probe([tesseract, '--list-langs']).split()
    if not (tesseract_version.startswith('tesseract') and pdftoppm_version.startswith('pdftoppm')
            and OCR_LANGUAGE in languages):
        return None
    return OcrTools(tesseract=os.path.abspath(tesseract), pdftoppm=os.path.abspath(pdftoppm),
                    tesseract_version=tesseract_version, pdftoppm_version=pdftoppm_version)


@functools.cache
def ocr_tools() -> OcrTools | None:
    return find_ocr_tools()


def ocr_available() -> bool:
    return ocr_tools() is not None


def ocr_page(tools: OcrTools, pdf_path: str, page: int, *, dpi: int, timeout_s: float, workdir: str) -> OcrOutcome:
    """Render ``page`` (1-based) of ``pdf_path`` and recognise it, all within ``timeout_s``."""
    deadline = time.monotonic() + timeout_s
    prefix = os.path.join(workdir, f'page-{page}')
    image = f'{prefix}.png'
    try:
        _run('pdftoppm', [tools.pdftoppm, '-q', '-r', str(dpi), '-f', str(page), '-l', str(page),
                          '-png', '-gray', '-singlefile', pdf_path, prefix], deadline, timeout_s)
        if not os.path.isfile(image):
            raise _ToolFailure('pdftoppm produced no image')
        output = _run('tesseract', [tools.tesseract, image, 'stdout', '-l', OCR_LANGUAGE, '--psm', '3',
                                    '--dpi', str(dpi), '-c', 'page_separator='], deadline, timeout_s)
        text = output.decode('utf-8')
    except _ToolFailure as failure:
        return OcrOutcome(text=None, problem=str(failure))
    except UnicodeDecodeError:
        return OcrOutcome(text=None, problem='tesseract returned text that is not valid UTF-8')
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(image)
    return OcrOutcome(text=canonicalize(text))


def _run(name: str, argv: list[str], deadline: float, timeout_s: float) -> bytes:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise _ToolFailure(f'OCR did not finish within the {format_seconds(timeout_s)}-second page limit')
    try:
        done = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              env=tool_env(), timeout=remaining, check=False)
    except subprocess.TimeoutExpired:
        raise _ToolFailure(f'OCR did not finish within the {format_seconds(timeout_s)}-second page limit') from None
    except OSError as exc:
        raise _ToolFailure(f'{name} could not start: {exc.strerror or type(exc).__name__}') from None
    if done.returncode < 0:
        raise _ToolFailure(f'{name} was stopped by {signal_name(-done.returncode)}')
    if done.returncode:
        raise _ToolFailure(f'{name} exited with status {done.returncode}')
    return done.stdout


def _probe(argv: list[str]) -> str:
    try:
        done = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, env=tool_env(),
                              timeout=PROBE_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        return ''
    return (done.stdout + done.stderr).decode('utf-8', 'replace')


def _first_line(output: str) -> str:
    return next((line.strip() for line in output.splitlines() if line.strip()), '')
