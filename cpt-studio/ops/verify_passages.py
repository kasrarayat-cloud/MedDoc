"""Prove the CMS passage data files against the publishers' PDFs, offline.

    .venv/bin/python -I ops/verify_passages.py --data studio/reference/data/cms-pfs-rvu26d-documentation.json \\
        --pdf RVU26D.pdf [--data DATA --pdf PDF ...]

Each --data file is checked against the --pdf given in the same position:
  sha256    the PDF's sha256 equals the data file's source sha256 (the bytes hashed are the bytes parsed)
  passages  every passage occurs verbatim in the PDF's text as pypdf extracts it, each page's text joined by a line
            break and runs of whitespace collapsed to one space: on its page "N", or across its pages "N-M" and then
            on no single one of them
  excluded  every excluded item's anchor occurs on its page
  quotes    every "quoted" text in the source's license and scope notes occurs in the PDF's text

Exit status: 0 every check passed; 1 at least one check failed; 2 a check could not be performed (an unreadable file,
invalid JSON, pypdf unavailable) and nothing failed. It reads no network and no database, and needs the PDFs, so it
never runs in CI; its own tests (tests/test_passages_verify.py) use a small synthetic PDF.

The data file layout and the passage rules are studio/reference/passages.py's; this script reads the JSON itself so
that it runs without Django.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from pathlib import Path

PAGE = re.compile(r'([1-9][0-9]*)(?:-([1-9][0-9]*))?')
QUOTED = re.compile(r'"([^"]+)"')


class CannotCheck(Exception):
    """A check could not be performed; it neither passed nor failed."""


def collapse(text: str) -> str:
    return ' '.join(text.split())


def page_texts(data: bytes) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise CannotCheck(f'pypdf is not available: {exc}') from exc
    try:
        return [page.extract_text() or '' for page in PdfReader(io.BytesIO(data)).pages]
    except Exception as exc:  # noqa: BLE001 - any parse failure means the text could not be read
        raise CannotCheck(f'the PDF could not be read: {exc}') from exc


def span(pages: list[str], page: str) -> tuple[str, list[str]]:
    """(the collapsed text of the page or page range, the collapsed text of each of its pages)."""
    match = PAGE.fullmatch(page) if isinstance(page, str) else None
    first, last = (int(match[1]), int(match[2] or match[1])) if match else (0, 0)
    if not match or last < first or (match[2] and last == first) or last > len(pages):
        raise ValueError(f'page {page!r} is not a page or range of this {len(pages)}-page PDF')
    chosen = pages[first - 1:last]
    return collapse('\n'.join(chosen)), [collapse(text) for text in chosen]


def check_passage(pages: list[str], passage: dict) -> str:
    """'' when the passage is where it says, else why not."""
    try:
        joined, single = span(pages, passage.get('page'))
    except ValueError as exc:
        return str(exc)
    text = passage.get('text')
    if not isinstance(text, str) or not text or collapse(text) != text:
        return 'its text is empty or not whitespace-collapsed'
    if text not in joined:
        return f'not found on page {passage["page"]}'
    if len(single) > 1 and any(text in one for one in single):
        return f'found on a single page of {passage["page"]}; the page is not a range'
    return ''


def verify_file(data_path: Path, pdf_path: Path, out) -> str:
    """'pass', 'fail' or 'cannot'; each check is printed as expected / measured."""
    try:
        document = json.loads(data_path.read_text(encoding='utf-8'))
        source, passages, excluded = document['source'], document['passages'], document['excluded']
        expected_sha = source['sha256']
        if not (isinstance(expected_sha, str) and isinstance(passages, list) and isinstance(excluded, list)
                and all(isinstance(item, dict) for item in passages + excluded)
                and all(isinstance(source.get(f, ''), str) for f in ('license_note', 'scope_note'))):
            raise TypeError('the source, passages or excluded items are not in the data file layout')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f'{data_path}: cannot read the data file: {exc}', file=out)
        return 'cannot'
    print(f'{data_path.name} against {pdf_path.name}', file=out)
    try:
        data = pdf_path.read_bytes()
    except OSError as exc:
        print(f'  sha256    cannot read the PDF: {exc}', file=out)
        return 'cannot'
    measured = hashlib.sha256(data).hexdigest()
    print(f'  sha256    expected {expected_sha} / measured {measured}', file=out)
    if measured != expected_sha:
        print('  FAIL      the PDF is not the file the data file names; nothing else was checked', file=out)
        return 'fail'
    try:
        pages = page_texts(data)
    except CannotCheck as exc:
        print(f'  passages  cannot check: {exc}', file=out)
        return 'cannot'
    failed = False
    problems = [(p.get('passage_key'), check_passage(pages, p)) for p in passages]
    verified = sum(1 for _, problem in problems if not problem)
    print(f'  passages  expected {len(passages)} / verified {verified}', file=out)
    for key, problem in problems:
        if problem:
            failed = True
            print(f'  FAIL      passage {key}: {problem}', file=out)
    located = 0
    for item in excluded:
        try:
            joined, _ = span(pages, item.get('page'))
        except ValueError as exc:
            joined, problem = '', str(exc)
        else:
            problem = '' if item.get('anchor') and item['anchor'] in joined else f'not found on page {item["page"]}'
        if problem:
            failed = True
            print(f'  FAIL      excluded {item.get("topic")}={item.get("topic_value")}: anchor {problem}', file=out)
        else:
            located += 1
    print(f'  excluded  expected {len(excluded)} / located {located}', file=out)
    whole = collapse('\n'.join(pages))
    quotes = [q for field in ('license_note', 'scope_note') for q in QUOTED.findall(source.get(field, ''))]
    found = [q for q in quotes if q in whole]
    print(f'  quotes    expected {len(quotes)} / located {len(found)}', file=out)
    for quote in quotes:
        if quote not in whole:
            failed = True
            print(f'  FAIL      quoted note text not in the PDF: {quote[:80]!r}', file=out)
    return 'fail' if failed else 'pass'


def main(argv=None, out=None) -> int:
    out = out or sys.stdout
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--data', type=Path, action='append', required=True, help='a passage data file (JSON)')
    parser.add_argument('--pdf', type=Path, action='append', required=True, help='the PDF that data file names')
    args = parser.parse_args(argv)
    if len(args.data) != len(args.pdf):
        print(f'verify_passages: {len(args.data)} --data but {len(args.pdf)} --pdf; give them in pairs.', file=out)
        return 2
    outcomes = [verify_file(data, pdf, out) for data, pdf in zip(args.data, args.pdf)]
    counts = {name: outcomes.count(name) for name in ('pass', 'fail', 'cannot')}
    print(f'{len(outcomes)} data files: {counts["pass"]} passed, {counts["fail"]} failed, {counts["cannot"]} could not '
          'be checked', file=out)
    if counts['fail']:
        return 1
    return 2 if counts['cannot'] else 0


if __name__ == '__main__':
    sys.exit(main())
