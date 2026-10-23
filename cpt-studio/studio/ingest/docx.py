"""DOCX extraction (ARCHITECTURE 5.1): body paragraphs and tables in document order.

python-docx opens and validates the package; the body XML is walked directly,
because the python-docx text API skips content controls, tracked insertions
and text boxes. Rules:

- One line per paragraph; one line per table row, cells joined with ' | '
  (a cell's own paragraphs are joined with spaces). Each physical cell is
  read once, so merged cells are never repeated.
- Tracked changes are read as accepted: insertions in, deletions out.
- Content controls showing placeholder text are skipped, and so are runs
  with direct hidden formatting (w:vanish); hidden text that comes from a
  style is not detected.
- Text boxes are read after the paragraph that anchors them.
- Header, footer, footnote, endnote and comment text is not extracted; when
  present its size is reported. Content that has no text here (images,
  embedded objects, symbol-font glyphs, legacy form-field values, ...) is
  counted in a message instead of disappearing silently.
"""
from __future__ import annotations

import collections
import io
import zipfile
from typing import TYPE_CHECKING

import docx
from docx.opc.constants import CONTENT_TYPE as CT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.opc.part import XmlPart
from docx.oxml.parser import parse_xml
from docx.package import Package

from studio.types import ExtractionResult

from .text import INGEST_VERSION, canonicalize, failed, non_space_count, single_page

if TYPE_CHECKING:
    from .extract import Limits

MIB = 1024 * 1024
MAX_PACKAGE_BYTES = 256 * MIB  # declared uncompressed size of all members
MAX_PACKAGE_MEMBERS = 5_000
OLE_SIGNATURE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

DAMAGED = 'The DOCX file could not be read; it is damaged or is not a Word document.'
MACROS = 'The document contains macros; macro-enabled Word documents are not accepted.'
OLE = ('The file is an OLE compound document (a legacy .doc file or a password-protected Office file), '
       'not a DOCX package.')

_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
_MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
BODY, P, R, RPR, VANISH, TBL, TR, TC, T = (
    f'{_W}{name}' for name in ('body', 'p', 'r', 'rPr', 'vanish', 'tbl', 'tr', 'tc', 't'))
TAB, PTAB, BR, CR, NO_BREAK_HYPHEN = (f'{_W}{name}' for name in ('tab', 'ptab', 'br', 'cr', 'noBreakHyphen'))
INS, DEL, MOVE_TO, MOVE_FROM = (f'{_W}{name}' for name in ('ins', 'del', 'moveTo', 'moveFrom'))
SDT, SDT_PR, SDT_CONTENT, SHOWING_PLACEHOLDER, CUSTOM_XML = (
    f'{_W}{name}' for name in ('sdt', 'sdtPr', 'sdtContent', 'showingPlcHdr', 'customXml'))
TXBX_CONTENT, ALT_CHUNK, TR_PR, FF_DATA, CHECK_BOX, DROP_DOWN = (
    f'{_W}{name}' for name in ('txbxContent', 'altChunk', 'trPr', 'ffData', 'checkBox', 'ddList'))
ALTERNATE_CONTENT, MC_CHOICE, MC_FALLBACK = (f'{_MC}{name}' for name in ('AlternateContent', 'Choice', 'Fallback'))

# Elements that hold content this extractor cannot turn into text.
_UNREADABLE = {
    f'{_W}sym': 'symbol',
    f'{_W}object': 'object',
    '{http://schemas.openxmlformats.org/officeDocument/2006/math}oMath': 'equation',
    '{http://schemas.openxmlformats.org/officeDocument/2006/math}oMathPara': 'equation',
    '{http://schemas.openxmlformats.org/drawingml/2006/picture}pic': 'image',
    '{urn:schemas-microsoft-com:vml}imagedata': 'image',
    '{http://schemas.openxmlformats.org/drawingml/2006/chart}chart': 'chart',
    '{http://schemas.openxmlformats.org/drawingml/2006/diagram}relIds': 'chart',
}
_SKIPPED_LABELS = (
    ('image', 'image', 'images'),
    ('object', 'embedded object', 'embedded objects'),
    ('chart', 'chart or diagram', 'charts or diagrams'),
    ('equation', 'equation', 'equations'),
    ('symbol', 'symbol-font character', 'symbol-font characters'),
    ('form_field', 'legacy form-field value', 'legacy form-field values'),
    ('placeholder', 'empty content control (placeholder text)', 'empty content controls (placeholder text)'),
    ('hidden', 'run of hidden text', 'runs of hidden text'),
    ('altchunk', 'imported content block (altChunk)', 'imported content blocks (altChunk)'),
)
_SIDE_PARTS = {RT.HEADER: 'Header/footer text', RT.FOOTER: 'Header/footer text',
               RT.FOOTNOTES: 'Footnote/endnote text', RT.ENDNOTES: 'Footnote/endnote text',
               RT.COMMENTS: 'Comment text'}
_SIDE_ORDER = ('Header/footer text', 'Footnote/endnote text', 'Comment text')


def extract_docx(data: bytes, limits: Limits) -> ExtractionResult:
    engine = {'ingest': INGEST_VERSION, 'python-docx': docx.__version__}
    problem = _package_problem(data)
    if problem:
        return failed('docx', engine, problem)
    try:
        part = Package.open(io.BytesIO(data)).main_document_part
    except MemoryError:
        raise
    except Exception:  # any parser error on untrusted bytes means the package is unreadable
        return failed('docx', engine, DAMAGED)
    if part.content_type != CT.WML_DOCUMENT_MAIN:
        return failed('docx', engine, _content_type_problem(part.content_type))
    walker = _Walker()
    body = part.element.find(BODY)
    lines = walker.blocks(body) if body is not None else []
    notes = walker.notes() + _side_notes(part)
    return single_page(canonicalize('\n'.join(lines)), 'docx', limits, 'Word document', engine, notes)


def _package_problem(data: bytes) -> str:
    """Refuse OLE files, broken archives, zip bombs and macro projects before parsing."""
    if data.startswith(OLE_SIGNATURE):
        return OLE
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
    except MemoryError:
        raise
    except Exception:
        return DAMAGED
    if len(members) > MAX_PACKAGE_MEMBERS:
        return f'The DOCX package has more than {MAX_PACKAGE_MEMBERS:,} parts; it was not opened.'
    if sum(member.file_size for member in members) > MAX_PACKAGE_BYTES:
        return f'The DOCX package expands to more than {MAX_PACKAGE_BYTES // MIB} MB; it was not opened.'
    if any(member.filename.lower().endswith('vbaproject.bin') for member in members):
        return MACROS
    return ''


def _content_type_problem(content_type: str) -> str:
    if 'macroEnabled' in content_type:
        return MACROS
    if '.template.' in content_type:
        return 'The file is a Word template, not a Word document.'
    return 'The file is not a Word document.'


def _side_notes(part) -> list[str]:
    """Messages for header/footer, note and comment text, which is not extracted."""
    totals: collections.Counter[str] = collections.Counter()
    seen = set()
    for rel in part.rels.values():
        label = _SIDE_PARTS.get(rel.reltype)
        if label is None or rel.is_external or rel.target_part.partname in seen:
            continue
        seen.add(rel.target_part.partname)
        totals[label] += _visible_chars(rel.target_part)
    return [f'{label} is not extracted ({totals[label]:,} character{"" if totals[label] == 1 else "s"}).'
            for label in _SIDE_ORDER if totals[label]]


def _visible_chars(part) -> int:
    root = part.element if isinstance(part, XmlPart) else parse_xml(part.blob)
    return sum(non_space_count(node.text or '') for node in root.iter(T)
               if not any(ancestor.tag == MC_FALLBACK for ancestor in node.iterancestors()))


def _hidden(run) -> bool:
    vanish = run.find(f'{RPR}/{VANISH}')
    return vanish is not None and vanish.get(f'{_W}val', 'true') not in ('0', 'false', 'off')


class _Walker:
    """Text of WordprocessingML content in document order, plus what it could not read."""

    def __init__(self):
        self.skipped: collections.Counter[str] = collections.Counter()
        self.tracked_changes = False

    def notes(self) -> list[str]:
        notes = []
        if self.tracked_changes:
            notes.append('The document has tracked changes; inserted text is included and deleted text is not.')
        counted = [f'{count} {singular if count == 1 else plural}'
                   for key, singular, plural in _SKIPPED_LABELS if (count := self.skipped[key])]
        if counted:
            notes.append(f'Not extracted from the document body: {", ".join(counted)}.')
        return notes

    def blocks(self, container) -> list[str]:
        lines = []
        for child in container:
            tag = child.tag
            if tag == P:
                lines.extend(self._paragraph(child))
            elif tag == TBL:
                lines.extend(self._table(child))
            elif tag in (SDT, CUSTOM_XML, INS, MOVE_TO, ALTERNATE_CONTENT):
                content = self._content(child)
                if content is not None:
                    lines.extend(self.blocks(content))
            elif tag in (DEL, MOVE_FROM):
                self.tracked_changes = True
            elif tag == ALT_CHUNK:
                self.skipped['altchunk'] += 1
        return lines

    def _content(self, wrapper):
        """The element whose children are ``wrapper``'s content, or None to skip it."""
        tag = wrapper.tag
        if tag == SDT:
            if wrapper.find(f'{SDT_PR}/{SHOWING_PLACEHOLDER}') is not None:
                self.skipped['placeholder'] += 1
                return None
            return wrapper.find(SDT_CONTENT)
        if tag == ALTERNATE_CONTENT:
            # Choice and Fallback hold the same content twice: read one.
            choice = wrapper.find(MC_CHOICE)
            return choice if choice is not None else wrapper.find(MC_FALLBACK)
        if tag in (INS, MOVE_TO):
            self.tracked_changes = True
        return wrapper

    def _paragraph(self, paragraph) -> list[str]:
        """The paragraph's line, then the lines of text boxes anchored in it."""
        parts: list[str] = []
        boxes: list[str] = []
        self._inline(paragraph, parts, boxes)
        return [''.join(parts), *boxes]

    def _inline(self, node, parts: list[str], boxes: list[str]) -> None:
        for child in node:
            tag = child.tag
            if tag == T:
                parts.append(child.text or '')
            elif tag in (TAB, PTAB):
                parts.append('\t')
            elif tag in (BR, CR):
                parts.append('\n')
            elif tag == NO_BREAK_HYPHEN:
                parts.append('-')
            elif tag in (DEL, MOVE_FROM):
                self.tracked_changes = True
            elif tag in _UNREADABLE:
                self.skipped[_UNREADABLE[tag]] += 1
            elif tag == R and _hidden(child):
                self.skipped['hidden'] += 1
            elif tag == FF_DATA:
                if child.find(CHECK_BOX) is not None or child.find(DROP_DOWN) is not None:
                    self.skipped['form_field'] += 1
            elif tag == TXBX_CONTENT:
                boxes.extend(self.blocks(child))
            elif tag in (SDT, CUSTOM_XML, INS, MOVE_TO, ALTERNATE_CONTENT):
                content = self._content(child)
                if content is not None:
                    self._inline(content, parts, boxes)
            else:
                self._inline(child, parts, boxes)

    def _table(self, table) -> list[str]:
        lines = []
        for row in self._children(table, TR):
            if row.find(f'{TR_PR}/{DEL}') is not None:  # a tracked row deletion
                self.tracked_changes = True
                continue
            cells = [self._cell(cell) for cell in self._children(row, TC)]
            if any(cell.strip() for cell in cells):
                lines.append(' | '.join(cells))
        return lines

    def _children(self, node, tag):
        """``tag`` children of ``node``, looking through content-control and custom-XML wrappers."""
        for child in node:
            if child.tag == tag:
                yield child
            elif child.tag in (SDT, CUSTOM_XML):
                content = self._content(child)
                if content is not None:
                    yield from self._children(content, tag)

    def _cell(self, cell) -> str:
        return ' '.join(line.replace('\n', ' ') for line in self.blocks(cell) if line.strip())
