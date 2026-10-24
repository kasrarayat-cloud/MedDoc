"""DOCX extraction (ARCHITECTURE 5.1): body paragraphs and tables in document order.

python-docx opens and validates the package; the body XML is walked directly,
because the python-docx text API skips content controls, tracked insertions
and text boxes. Rules:

- One line per paragraph; one line per table row, cells joined with ' | '
  (a cell's own paragraphs are joined with spaces). Each physical cell is
  read once, so merged cells are never repeated.
- A text element is all of its character data: comments and processing
  instructions inside it are not content and do not cut it short. A document
  that declares a DTD (which Word documents never do) is refused, so no
  entity can stand in for text.
- Tracked changes are read as accepted: insertions in, deletions out.
- Content controls showing placeholder text (showingPlcHdr on) are skipped.
- Hidden text is skipped and counted: w:vanish set on the run, or inherited
  from its character style, its paragraph style, its table's style or the
  document defaults (each through its basedOn chain; the default style of
  each kind applies when none is named). A direct w:vanish on the run decides
  over any style. Word toggles vanish when both a paragraph and a character
  style set it; that combination is treated as hidden.
- Markup Compatibility: the first mc:Choice whose required namespaces this
  reader understands is read, else mc:Fallback; a skipped Choice that holds
  text is counted, and one with no Fallback to read instead makes the result
  'partial'.
- Text in a symbol font (Symbol, Wingdings, Zapf Dingbats, ...), typed or
  inserted as w:sym, is mapped to the Unicode characters its glyphs show
  where that is known (Symbol and Zapf Dingbats by their Adobe encodings;
  check-box and check-mark glyphs of Wingdings and Wingdings 2); other
  symbol-font glyphs, and private-use characters, are counted, never shown as
  the letters that encode them.
- Text boxes are read after the paragraph that anchors them.
- Header, footer, footnote, endnote and comment text is not extracted; when
  present its size is reported. Content that has no text here (images,
  embedded objects, unmapped symbol glyphs, legacy form-field values, ...) is
  counted in a message instead of disappearing silently.
"""
from __future__ import annotations

import collections
import dataclasses
import io
import re
import zipfile
from dataclasses import dataclass
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
MAX_STYLE_CHAIN = 64
OLE_SIGNATURE = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'

DAMAGED = 'The DOCX file could not be read; it is damaged or is not a Word document.'
MACROS = 'The document contains macros; macro-enabled Word documents are not accepted.'
OLE = ('The file is an OLE compound document (a legacy .doc file or a password-protected Office file), '
       'not a DOCX package.')
DTD = 'The document declares a DTD, which Word documents do not use; it was not read.'

_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
_MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
BODY, P, R, RPR, VANISH, TBL, TR, TC, T = (
    f'{_W}{name}' for name in ('body', 'p', 'r', 'rPr', 'vanish', 'tbl', 'tr', 'tc', 't'))
PPR, PSTYLE, RSTYLE, TBL_PR, TBL_STYLE, RFONTS, SYM = (
    f'{_W}{name}' for name in ('pPr', 'pStyle', 'rStyle', 'tblPr', 'tblStyle', 'rFonts', 'sym'))
TAB, PTAB, BR, CR, NO_BREAK_HYPHEN = (f'{_W}{name}' for name in ('tab', 'ptab', 'br', 'cr', 'noBreakHyphen'))
INS, DEL, MOVE_TO, MOVE_FROM = (f'{_W}{name}' for name in ('ins', 'del', 'moveTo', 'moveFrom'))
SDT, SDT_PR, SDT_CONTENT, SHOWING_PLACEHOLDER, CUSTOM_XML = (
    f'{_W}{name}' for name in ('sdt', 'sdtPr', 'sdtContent', 'showingPlcHdr', 'customXml'))
TXBX_CONTENT, ALT_CHUNK, TR_PR, FF_DATA, CHECK_BOX, DROP_DOWN = (
    f'{_W}{name}' for name in ('txbxContent', 'altChunk', 'trPr', 'ffData', 'checkBox', 'ddList'))
STYLE, STYLE_ID, STYLE_TYPE, DEFAULT, BASED_ON, VAL = (
    f'{_W}{name}' for name in ('style', 'styleId', 'type', 'default', 'basedOn', 'val'))
DOC_DEFAULTS_RPR = f'{_W}docDefaults/{_W}rPrDefault/{_W}rPr'
ALTERNATE_CONTENT, MC_CHOICE, MC_FALLBACK = (f'{_MC}{name}' for name in ('AlternateContent', 'Choice', 'Fallback'))

# Namespaces whose mc:Choice content Word displays and this walker reads as displayed.
UNDERSTOOD_NAMESPACES = frozenset({
    'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'http://schemas.openxmlformats.org/drawingml/2006/main',
    'http://schemas.openxmlformats.org/drawingml/2006/picture',
    'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'http://schemas.openxmlformats.org/officeDocument/2006/math',
    'urn:schemas-microsoft-com:vml',
    'urn:schemas-microsoft-com:office:office',
    'urn:schemas-microsoft-com:office:word',
    'http://schemas.microsoft.com/office/word/2010/wordprocessingShape',
    'http://schemas.microsoft.com/office/word/2010/wordprocessingGroup',
    'http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas',
    'http://schemas.microsoft.com/office/word/2010/wordprocessingInk',
    'http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing',
    'http://schemas.microsoft.com/office/word/2010/wordml',
    'http://schemas.microsoft.com/office/word/2012/wordml',
})

# Elements that hold content this extractor cannot turn into text.
_UNREADABLE = {
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
    ('alternate', 'alternative content block for newer Word versions (its backward-compatible version was read '
                  'instead)',
     'alternative content blocks for newer Word versions (their backward-compatible versions were read instead)'),
)
_SIDE_PARTS = {RT.HEADER: 'Header/footer text', RT.FOOTER: 'Header/footer text',
               RT.FOOTNOTES: 'Footnote/endnote text', RT.ENDNOTES: 'Footnote/endnote text',
               RT.COMMENTS: 'Comment text'}
_SIDE_ORDER = ('Header/footer text', 'Footnote/endnote text', 'Comment text')
_OFF = ('0', 'false', 'off')


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
    if part.element.getroottree().docinfo.doctype:
        return failed('docx', engine, DTD)
    walker = _Walker(_Styles.of(part))
    body = part.element.find(BODY)
    lines = walker.blocks(body) if body is not None else []
    notes = walker.notes() + _side_notes(part)
    result = single_page(canonicalize('\n'.join(lines)), 'docx', limits, 'Word document', engine, notes)
    if result.status == 'ok' and walker.unread:
        return dataclasses.replace(result, status='partial')
    return result


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
    return sum(non_space_count(character_data(node)) for node in root.iter(T)
               if not any(ancestor.tag == MC_FALLBACK for ancestor in node.iterancestors()))


def character_data(text_element) -> str:
    """All character data of a w:t: its text and the text after any comment or processing instruction."""
    return ''.join(text_element.itertext())


def is_on(element) -> bool | None:
    """An OOXML on/off property (CT_OnOff): None when absent; w:val 0, false or off means off."""
    if element is None:
        return None
    return (element.get(VAL) or 'true').strip().lower() not in _OFF


# --- styles -------------------------------------------------------------------------

class _Styles:
    """Run properties from styles.xml: hidden (w:vanish) and fonts (w:rFonts), each through basedOn."""

    def __init__(self, root=None):
        self.by_id: dict[str, object] = {}
        self.defaults: dict[str, str] = {}
        self.document_rpr = None
        self._vanish: dict = {}
        self._fonts: dict = {}
        if root is None:
            return
        for style in root.iter(STYLE):
            style_id = style.get(STYLE_ID)
            if style_id:
                self.by_id.setdefault(style_id, style)
                if is_on_attribute(style.get(DEFAULT)):
                    self.defaults.setdefault(style.get(STYLE_TYPE) or 'paragraph', style_id)
        self.document_rpr = root.find(DOC_DEFAULTS_RPR)

    @classmethod
    def of(cls, part) -> _Styles:
        try:
            styles = part.part_related_by(RT.STYLES)
            root = styles.element if isinstance(styles, XmlPart) else parse_xml(styles.blob)
        except MemoryError:
            raise
        except Exception:  # no styles part, or one that cannot be parsed: no style properties
            return cls()
        return cls(root)

    def style_id(self, explicit, kind: str) -> str | None:
        """The named style, or the document's default style of ``kind`` when none is named."""
        name = explicit.get(VAL) if explicit is not None else None
        return name if name else self.defaults.get(kind)

    def chain(self, style_id):
        """The style and its basedOn ancestors, nearest first (cycles and runaway chains cut)."""
        seen = set()
        while style_id and style_id not in seen and len(seen) < MAX_STYLE_CHAIN:
            seen.add(style_id)
            style = self.by_id.get(style_id)
            if style is None:
                return
            yield style
            based = style.find(BASED_ON)
            style_id = based.get(VAL) if based is not None else None

    def vanish(self, style_id) -> bool | None:
        if style_id not in self._vanish:
            flags = (is_on(style.find(f'{RPR}/{VANISH}')) for style in self.chain(style_id))
            self._vanish[style_id] = next((flag for flag in flags if flag is not None), None)
        return self._vanish[style_id]

    def font(self, style_id, attribute: str) -> str | None:
        """The style chain's font for ``attribute`` (ascii or hAnsi): '' for a theme font, None if unset."""
        key = (style_id, attribute)
        if key not in self._fonts:
            choices = (font_choice(style.find(f'{RPR}/{RFONTS}'), attribute) for style in self.chain(style_id))
            self._fonts[key] = next((choice for choice in choices if choice is not None), None)
        return self._fonts[key]

    def document_vanish(self) -> bool | None:
        return is_on(self.document_rpr.find(VANISH)) if self.document_rpr is not None else None

    def document_font(self, attribute: str) -> str | None:
        return font_choice(self.document_rpr.find(RFONTS), attribute) if self.document_rpr is not None else None


def is_on_attribute(value) -> bool:
    return value is not None and value.strip().lower() not in _OFF


def font_choice(fonts, attribute: str) -> str | None:
    """From one w:rFonts: the named font for ``attribute``, '' when a theme font is used, None if unset."""
    if fonts is None:
        return None
    if fonts.get(f'{_W}{attribute}Theme') is not None:
        return ''
    return fonts.get(f'{_W}{attribute}')


# --- symbol fonts -------------------------------------------------------------------

def _adobe_table(module: str, name: str) -> dict[int, str]:
    """pypdf's Adobe Symbol / Zapf Dingbats encodings, keeping only real characters."""
    try:
        table = getattr(__import__(f'pypdf._codecs.{module}', fromlist=[name]), name)
    except (ImportError, AttributeError):  # count the glyphs instead of mapping them
        return {}
    return {code: char for code, char in enumerate(table)
            if char.strip() and char.isprintable() and not 0xE000 <= ord(char) <= 0xF8FF}


_WINGDINGS = {0x6E: '■', 0x6F: '□', 0x71: '❑', 0x72: '❒', 0x78: '⌧', 0xA8: '◻', 0xFB: '✗', 0xFC: '✓', 0xFD: '☒',
              0xFE: '☑'}
_WINGDINGS_2 = {0x52: '☑', 0x53: '☒', 0x54: '☒', 0xA3: '☐'}
SYMBOL_FONTS = {
    'symbol': _adobe_table('symbol', '_symbol_encoding'),
    'zapfdingbats': _adobe_table('zapfding', '_zapfding_encoding'),
    'itczapfdingbats': _adobe_table('zapfding', '_zapfding_encoding'),
    'wingdings': _WINGDINGS,
    'wingdings2': _WINGDINGS_2,
    'wingdings3': {}, 'webdings': {}, 'marlett': {}, 'mtextra': {}, 'msoutlook': {}, 'bookshelfsymbol7': {},
    'msreferencespecialty': {}, 'mtsymbol': {},
}
_FONT_NAME = re.compile(r'[\s_-]+')


def symbol_table(font: str | None) -> dict[int, str] | None:
    """The glyph table of a symbol font (possibly empty: count every glyph), or None for a text font."""
    return SYMBOL_FONTS.get(_FONT_NAME.sub('', font).lower()) if font else None


# --- walking the body ---------------------------------------------------------------

@dataclass(frozen=True)
class _Context:
    table_style: str | None = None
    paragraph_style: str | None = None
    ascii_font: str | None = None  # the run's fonts, for symbol-font text
    hansi_font: str | None = None


class _Walker:
    """Text of WordprocessingML content in document order, plus what it could not read."""

    def __init__(self, styles: _Styles | None = None):
        self.styles = styles or _Styles()
        self.skipped: collections.Counter[str] = collections.Counter()
        self.tracked_changes = False
        self.unread_alternates = 0

    @property
    def unread(self) -> bool:
        """Content that may be displayed was not read: the result is partial."""
        return bool(self.unread_alternates)

    def notes(self) -> list[str]:
        notes = []
        if self.tracked_changes:
            notes.append('The document has tracked changes; inserted text is included and deleted text is not.')
        counted = [f'{count} {singular if count == 1 else plural}'
                   for key, singular, plural in _SKIPPED_LABELS if (count := self.skipped[key])]
        if counted:
            notes.append(f'Not extracted from the document body: {", ".join(counted)}.')
        if self.unread_alternates:
            count = self.unread_alternates
            notes.append(f'The document has {count} block{"" if count == 1 else "s"} of content for newer Word '
                         f'versions that could not be read and {"has" if count == 1 else "have"} no '
                         'backward-compatible version.')
        return notes

    def blocks(self, container, table_style: str | None = None) -> list[str]:
        lines = []
        for child in container:
            tag = child.tag
            if tag == P:
                lines.extend(self._paragraph(child, table_style))
            elif tag == TBL:
                lines.extend(self._table(child))
            elif tag in (SDT, CUSTOM_XML, INS, MOVE_TO, ALTERNATE_CONTENT):
                content = self._content(child)
                if content is not None:
                    lines.extend(self.blocks(content, table_style))
            elif tag in (DEL, MOVE_FROM):
                self.tracked_changes = True
            elif tag == ALT_CHUNK:
                self.skipped['altchunk'] += 1
        return lines

    def _content(self, wrapper):
        """The element whose children are ``wrapper``'s content, or None to skip it."""
        tag = wrapper.tag
        if tag == SDT:
            if is_on(wrapper.find(f'{SDT_PR}/{SHOWING_PLACEHOLDER}')):
                self.skipped['placeholder'] += 1
                return None
            return wrapper.find(SDT_CONTENT)
        if tag == ALTERNATE_CONTENT:
            return self._alternate(wrapper)
        if tag in (INS, MOVE_TO):
            self.tracked_changes = True
        return wrapper

    def _alternate(self, wrapper):
        """Markup Compatibility: the first Choice whose required namespaces are understood, else the Fallback."""
        skipped_text = False
        for choice in wrapper.iterchildren(MC_CHOICE):
            prefixes = (choice.get('Requires') or '').split()
            if prefixes and all(choice.nsmap.get(prefix) in UNDERSTOOD_NAMESPACES for prefix in prefixes):
                if skipped_text:
                    self.skipped['alternate'] += 1
                return choice
            skipped_text = skipped_text or any(character_data(node).strip() for node in choice.iter(T))
        fallback = wrapper.find(MC_FALLBACK)
        if skipped_text:
            if fallback is not None:
                self.skipped['alternate'] += 1
            else:
                self.unread_alternates += 1
        return fallback

    def _paragraph(self, paragraph, table_style: str | None) -> list[str]:
        """The paragraph's line, then the lines of text boxes anchored in it."""
        style = self.styles.style_id(paragraph.find(f'{PPR}/{PSTYLE}'), 'paragraph')
        parts: list[str] = []
        boxes: list[str] = []
        self._inline(paragraph, parts, boxes, _Context(table_style=table_style, paragraph_style=style))
        return [''.join(parts), *boxes]

    def _inline(self, node, parts: list[str], boxes: list[str], context: _Context) -> None:
        for child in node:
            tag = child.tag
            if tag == T:
                parts.append(self._symbols(character_data(child), context))
            elif tag in (TAB, PTAB):
                parts.append('\t')
            elif tag in (BR, CR):
                parts.append('\n')
            elif tag == NO_BREAK_HYPHEN:
                parts.append('-')
            elif tag in (DEL, MOVE_FROM):
                self.tracked_changes = True
            elif tag == SYM:
                parts.append(self._sym(child))
            elif tag in _UNREADABLE:
                self.skipped[_UNREADABLE[tag]] += 1
            elif tag == R:
                if self._run_hidden(child, context):
                    self.skipped['hidden'] += 1
                else:
                    self._inline(child, parts, boxes, self._run_context(child, context))
            elif tag == FF_DATA:
                if child.find(CHECK_BOX) is not None or child.find(DROP_DOWN) is not None:
                    self.skipped['form_field'] += 1
            elif tag == TXBX_CONTENT:
                boxes.extend(self.blocks(child))
            elif tag in (SDT, CUSTOM_XML, INS, MOVE_TO, ALTERNATE_CONTENT):
                content = self._content(child)
                if content is not None:
                    self._inline(content, parts, boxes, context)
            else:
                self._inline(child, parts, boxes, context)

    # Hidden text -------------------------------------------------------------------
    def _run_hidden(self, run, context: _Context) -> bool:
        direct = is_on(run.find(f'{RPR}/{VANISH}'))
        if direct is not None:
            return direct
        styles = self.styles
        character = styles.style_id(run.find(f'{RPR}/{RSTYLE}'), 'character')
        levels = (styles.document_vanish(), styles.vanish(context.table_style),
                  styles.vanish(context.paragraph_style), styles.vanish(character))
        return any(level is True for level in levels)

    # Symbol fonts ------------------------------------------------------------------
    def _run_context(self, run, context: _Context) -> _Context:
        fonts = run.find(f'{RPR}/{RFONTS}')
        character = self.styles.style_id(run.find(f'{RPR}/{RSTYLE}'), 'character')

        def effective(attribute: str) -> str | None:
            for choice in (font_choice(fonts, attribute), self.styles.font(character, attribute),
                           self.styles.font(context.paragraph_style, attribute),
                           self.styles.font(context.table_style, attribute), self.styles.document_font(attribute)):
                if choice is not None:
                    return choice
            return None

        return dataclasses.replace(context, ascii_font=effective('ascii'), hansi_font=effective('hAnsi'))

    def _symbols(self, text: str, context: _Context) -> str:
        """``text`` with symbol-font codes mapped to the characters they show, or counted and dropped.

        Word draws U+0000-U+007F in the run's ascii font and U+0080-U+00FF in
        its hAnsi font; U+F000-U+F0FF address a symbol font's codes directly.
        """
        low, high = symbol_table(context.ascii_font), symbol_table(context.hansi_font)
        if low is None and high is None and not any(0xF000 <= ord(char) <= 0xF0FF for char in text):
            return text
        out = []
        for char in text:
            code = ord(char)
            if 0xF000 <= code <= 0xF0FF:
                table, code = (low if low is not None else high), code - 0xF000
                if table is None:  # a private-use code in a text font: it shows no known character
                    self.skipped['symbol'] += 1
                    continue
            elif code > 0xFF or char.isspace():
                out.append(char)
                continue
            else:
                table = low if code < 0x80 else high
                if table is None:
                    out.append(char)
                    continue
            mapped = table.get(code)
            if mapped is None:
                self.skipped['symbol'] += 1
            else:
                out.append(mapped)
        return ''.join(out)

    def _sym(self, sym) -> str:
        """A w:sym glyph as the character it shows, or '' (counted) when that is not known."""
        try:
            code = int(sym.get(f'{_W}char') or '', 16)
        except ValueError:
            code = -1
        if 0xF000 <= code <= 0xF0FF:
            code -= 0xF000
        mapped = (symbol_table(sym.get(f'{_W}font')) or {}).get(code)
        if mapped is None:
            self.skipped['symbol'] += 1
            return ''
        return mapped

    # Tables ------------------------------------------------------------------------
    def _table(self, table) -> list[str]:
        style = self.styles.style_id(table.find(f'{TBL_PR}/{TBL_STYLE}'), 'table')
        lines = []
        for row in self._children(table, TR):
            if row.find(f'{TR_PR}/{DEL}') is not None:  # a tracked row deletion
                self.tracked_changes = True
                continue
            cells = [self._cell(cell, style) for cell in self._children(row, TC)]
            if any(cell.strip() for cell in cells):
                lines.append(' | '.join(cells))
        return lines

    def _children(self, node, tag):
        """``tag`` children of ``node``, looking through content-control, custom-XML and
        Markup Compatibility wrappers."""
        for child in node:
            if child.tag == tag:
                yield child
            elif child.tag in (SDT, CUSTOM_XML, ALTERNATE_CONTENT):
                content = self._content(child)
                if content is not None:
                    yield from self._children(content, tag)

    def _cell(self, cell, table_style: str | None) -> str:
        return ' '.join(line.replace('\n', ' ') for line in self.blocks(cell, table_style) if line.strip())
