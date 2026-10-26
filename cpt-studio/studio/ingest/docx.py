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
- Text formatted as struck through (w:strike or w:dstrike, resolved as w:vanish
  is) and white text with nothing that may be painted behind it (no shading or
  highlight on the run, its styles, paragraph, table cell or table, no text box,
  no page colour) is read as written, counted and named; the result is
  'partial', as for the same marks in a PDF.
- Markup Compatibility: the first mc:Choice whose required namespaces this
  reader understands is read, else mc:Fallback; a skipped Choice that holds
  text is counted, and one with no Fallback to read instead makes the result
  'partial'.
- Text in a symbol font (Symbol, Wingdings, Zapf Dingbats, ...), typed or
  inserted as w:sym, is mapped to the Unicode characters its glyphs show
  where that is known (studio.ingest.symbols: Symbol and Zapf Dingbats by
  their Adobe encodings; the check boxes, check marks and bullets of
  Wingdings and Wingdings 2). Every check box is written as ☐ (unchecked) or
  ☒ (checked), whatever box shape the font draws. Other symbol-font glyphs,
  and private-use characters, are counted, never shown as the letters that
  encode them.
- A legacy check-box field (FORMCHECKBOX, w:ffData/w:checkBox) is written as
  ☐ or ☒ in place of the field: w:checked when present, else w:default.
- A check-box content control (a w:sdt whose w:sdtPr holds w14:checkbox) is
  written as ☒ when w14:checked is on and ☐ otherwise, in place of its
  content, whatever symbols its checked and unchecked states are set to; a
  hidden control writes nothing and is counted.
- A list paragraph whose numbering bullet is a box glyph (Wingdings, Wingdings
  2, Zapf Dingbats or a box character in any font) starts with ☐ or ☒ when its
  own list's bullets (a run of consecutive box-bulleted paragraphs) show a
  checked box too (a checklist); when none of them is a checked box, a
  box-shaped bullet may be a bullet or an empty box, so it is written as the
  unread mark '[?]' (routing holds the item) and counted in a note: a checked
  box in another list says nothing of it. Any other paragraph ends a list, and
  so do a table cell's boundary and a text box's (its paragraphs are lists of
  their own; the anchoring paragraph's list resumes after them). A paragraph
  whose mark is hidden belongs to no list and never makes one a checklist: Word
  does not show its bullet as its own, so with no text shown nothing is
  written, and where its text shows a box bullet is written unread. Other
  bullets and numbering are not written.
- Text boxes are read after the paragraph that anchors them.
- Header, footer, footnote, endnote and comment text is not extracted; when
  present its size is reported. Content that has no text here (images,
  embedded objects, unmapped symbol glyphs, legacy drop-down values, ...) is
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

from .symbols import SYMBOL_FONTS, CHECKED_BOX, UNCHECKED_BOX, as_box, symbol_table  # noqa: F401 (SYMBOL_FONTS re-exported)
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
_W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'
W14_CHECKBOX, W14_CHECKED, W14_VAL = f'{_W14}checkbox', f'{_W14}checked', f'{_W14}val'
NUM_PR, NUM_ID, ILVL, NUM, ABSTRACT_NUM, ABSTRACT_NUM_ID, LVL, LVL_OVERRIDE, NUM_FMT, LVL_TEXT, NUM_STYLE_LINK = (
    f'{_W}{name}' for name in ('numPr', 'numId', 'ilvl', 'num', 'abstractNum', 'abstractNumId', 'lvl', 'lvlOverride',
                               'numFmt', 'lvlText', 'numStyleLink'))
MAX_NUMBERING_LINKS = 4  # numStyleLink indirections followed (a cycle or a runaway chain is cut)
BODY, P, R, RPR, VANISH, TBL, TR, TC, T = (
    f'{_W}{name}' for name in ('body', 'p', 'r', 'rPr', 'vanish', 'tbl', 'tr', 'tc', 't'))
PPR, PSTYLE, RSTYLE, TBL_PR, TBL_STYLE, RFONTS, SYM = (
    f'{_W}{name}' for name in ('pPr', 'pStyle', 'rStyle', 'tblPr', 'tblStyle', 'rFonts', 'sym'))
TAB, PTAB, BR, CR, NO_BREAK_HYPHEN = (f'{_W}{name}' for name in ('tab', 'ptab', 'br', 'cr', 'noBreakHyphen'))
INS, DEL, MOVE_TO, MOVE_FROM = (f'{_W}{name}' for name in ('ins', 'del', 'moveTo', 'moveFrom'))
SDT, SDT_PR, SDT_CONTENT, SHOWING_PLACEHOLDER, CUSTOM_XML = (
    f'{_W}{name}' for name in ('sdt', 'sdtPr', 'sdtContent', 'showingPlcHdr', 'customXml'))
TXBX_CONTENT, ALT_CHUNK, TR_PR, FF_DATA, CHECK_BOX, CHECKED_STATE, DROP_DOWN = (
    f'{_W}{name}' for name in ('txbxContent', 'altChunk', 'trPr', 'ffData', 'checkBox', 'checked', 'ddList'))
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

# Run formatting that changes what the text shows (named, partial: the text is read as written), and the shading that
# can be painted behind a run, so that white text on it shows.
_ING_STRIKES = (f'{_W}strike', f'{_W}dstrike')
_ING_COLOR, _ING_SHD, _ING_HIGHLIGHT, _ING_BACKGROUND, _ING_TC_PR = (
    f'{_W}{name}' for name in ('color', 'shd', 'highlight', 'background', 'tcPr'))
_ING_WHITE_LEVEL = 0xFD  # each channel of a colour at least this is white (0.99 of full, as for PDF text)
# The unread mark of the box contract (studio.ingest.pdf): a box bullet that may be a bullet or an unchecked box.
_ING_UNREAD_BOX = '[?]'
_ING_BULLET = '\x00'  # stands for an unchecked box bullet until every bullet is read (XML text holds no NUL)
_ING_PLACEHOLDER = re.compile('\x00([0-9]+)\x00')  # an unchecked box bullet's placeholder, tagged with its list


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
    styles = _Styles.of(part)
    walker = _Walker(styles, _Numbering.of(part, styles), _ING_background(part))
    body = part.element.find(BODY)
    lines = walker.blocks(body) if body is not None else []
    text = walker.bulleted('\n'.join(lines))
    notes = walker.notes() + _side_notes(part)
    result = single_page(canonicalize(text), 'docx', limits, 'Word document', engine, notes)
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


def check_box_control(sdt) -> bool | None:
    """A check-box content control's state (w:sdtPr/w14:checkbox): w14:checked on or off, None for any other
    control. w14:checked is an on/off value in the w14 namespace: absent attribute means on; 0, false or off mean
    off; no w14:checked element means unchecked."""
    properties = sdt.find(SDT_PR)
    box = properties.find(W14_CHECKBOX) if properties is not None else None
    if box is None:
        return None
    checked = box.find(W14_CHECKED)
    if checked is None:
        return False
    return (checked.get(W14_VAL) or 'true').strip().lower() not in _OFF


def legacy_box_checked(box) -> bool:
    """A legacy FORMCHECKBOX's state (w:ffData/w:checkBox): w:checked when present, else w:default, else off."""
    checked = is_on(box.find(CHECKED_STATE))
    if checked is None:
        checked = is_on(box.find(DEFAULT))
    return bool(checked)


# --- styles -------------------------------------------------------------------------

class _Styles:
    """Run properties from styles.xml: hidden (w:vanish) and fonts (w:rFonts), each through basedOn."""

    def __init__(self, root=None):
        self.by_id: dict[str, object] = {}
        self.defaults: dict[str, str] = {}
        self.document_rpr = None
        self._vanish: dict = {}
        self._fonts: dict = {}
        self._toggles: dict = {}
        self._colours: dict = {}
        self._shaded: dict = {}
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

    def toggle(self, style_id, tag: str) -> bool | None:
        """An on/off run property (strike, dstrike) along the style chain, read as vanish is."""
        key = (style_id, tag)
        if key not in self._toggles:
            flags = (is_on(style.find(f'{RPR}/{tag}')) for style in self.chain(style_id))
            self._toggles[key] = next((flag for flag in flags if flag is not None), None)
        return self._toggles[key]

    def document_toggle(self, tag: str) -> bool | None:
        return is_on(self.document_rpr.find(tag)) if self.document_rpr is not None else None

    def colour(self, style_id) -> str | None:
        """The style chain's text colour (w:color), None if unset."""
        if style_id not in self._colours:
            colours = (style.find(f'{RPR}/{_ING_COLOR}') for style in self.chain(style_id))
            self._colours[style_id] = next((c.get(VAL) for c in colours if c is not None and c.get(VAL)), None)
        return self._colours[style_id]

    def document_colour(self) -> str | None:
        found = self.document_rpr.find(_ING_COLOR) if self.document_rpr is not None else None
        return found.get(VAL) if found is not None else None

    def shaded(self, style_id) -> bool:
        """Whether the style chain may paint behind text: any shading or highlight it sets (a table style's
        conditional formatting included)."""
        if style_id not in self._shaded:
            self._shaded[style_id] = any(_ING_paints(found) for style in self.chain(style_id)
                                         for found in style.iter(_ING_SHD, _ING_HIGHLIGHT))
        return self._shaded[style_id]


def is_on_attribute(value) -> bool:
    return value is not None and value.strip().lower() not in _OFF


def font_choice(fonts, attribute: str) -> str | None:
    """From one w:rFonts: the named font for ``attribute``, '' when a theme font is used, None if unset."""
    if fonts is None:
        return None
    if fonts.get(f'{_W}{attribute}Theme') is not None:
        return ''
    return fonts.get(f'{_W}{attribute}')


def _ING_white(value) -> bool:
    """Whether a colour value (RRGGBB) is white: every channel at least _ING_WHITE_LEVEL. 'auto' is not."""
    if not value or len(value) != 6:
        return False
    try:
        return all(int(value[i:i + 2], 16) >= _ING_WHITE_LEVEL for i in (0, 2, 4))
    except ValueError:
        return False


def _ING_paints(element) -> bool:
    """Whether a w:shd or w:highlight paints something behind text: a highlight that is neither none nor white, a
    shading pattern, or a fill that is neither auto nor white."""
    if element.tag == _ING_HIGHLIGHT:
        return (element.get(VAL) or 'none').strip().lower() not in ('none', 'white')
    fill = (element.get(f'{_W}fill') or 'auto').strip()
    return (element.get(VAL) or 'clear').strip().lower() not in ('clear', 'nil') or \
        (fill.lower() != 'auto' and not _ING_white(fill))


def _ING_numbering(sources) -> tuple:
    """(numId, ilvl) from w:numPr elements in order of precedence: each the first one that sets it."""
    num_id = ilvl = None
    for numbering in sources:
        if numbering is None:
            continue
        if num_id is None and numbering.find(NUM_ID) is not None:
            num_id = numbering.find(NUM_ID).get(VAL)
        if ilvl is None and numbering.find(ILVL) is not None:
            ilvl = numbering.find(ILVL).get(VAL)
    return num_id, ilvl


def _ING_background(part) -> bool:
    """Whether the document has a page colour (w:background) that is not white: white text may show on it."""
    background = part.element.find(_ING_BACKGROUND)
    return background is not None and not _ING_white(background.get(f'{_W}color'))


class _Numbering:
    """Numbering levels from numbering.xml: w:num (with w:lvlOverride) over w:abstractNum, following
    w:numStyleLink through the numbering style's w:numPr."""

    def __init__(self, root=None, styles: _Styles | None = None):
        self.nums: dict[str, object] = {}
        self.abstracts: dict[str, object] = {}
        self.styles = styles or _Styles()
        # Each w:num and w:abstractNum is read once, on first use: a level is then found by dictionary lookups, so the
        # cost does not grow with the number of levels times the number of list paragraphs.
        self._nums: dict = {}  # numId -> ({ilvl: the level of its first override for that ilvl}, abstract reference)
        self._abstracts: dict = {}  # abstractNumId -> ({ilvl: its first level for that ilvl}, numbering style link)
        if root is None:
            return
        for num in root.iter(NUM):
            self.nums.setdefault(num.get(f'{_W}numId'), num)
        for abstract in root.iter(ABSTRACT_NUM):
            self.abstracts.setdefault(abstract.get(f'{_W}abstractNumId'), abstract)

    @classmethod
    def of(cls, part, styles: _Styles) -> _Numbering:
        try:
            numbering = part.part_related_by(RT.NUMBERING)
            root = numbering.element if isinstance(numbering, XmlPart) else parse_xml(numbering.blob)
        except MemoryError:
            raise
        except Exception:  # no numbering part, or one that cannot be parsed: no numbering
            return cls(styles=styles)
        return cls(root, styles)

    def level(self, num_id: str | None, ilvl: str):
        """The w:lvl element for (numId, ilvl), or None (numId 0 means no numbering)."""
        for _ in range(MAX_NUMBERING_LINKS):
            num = self.nums.get(num_id) if num_id not in (None, '0') else None
            if num is None:
                return None
            if num_id not in self._nums:
                overrides = {}
                for override in num.iter(LVL_OVERRIDE):  # the first override for an ilvl that holds a level
                    found = override.find(LVL)
                    if found is not None:
                        overrides.setdefault(override.get(f'{_W}ilvl'), found)
                reference = num.find(ABSTRACT_NUM_ID)
                self._nums[num_id] = (overrides, (reference.get(VAL),) if reference is not None else None)
            overrides, reference = self._nums[num_id]
            if ilvl in overrides:
                return overrides[ilvl]
            abstract = self.abstracts.get(reference[0]) if reference is not None else None
            if abstract is None:
                return None
            if reference[0] not in self._abstracts:
                levels = {}
                for found in abstract.iter(LVL):  # the first level for an ilvl, in document order
                    levels.setdefault(found.get(f'{_W}ilvl'), found)
                link = abstract.find(NUM_STYLE_LINK)
                self._abstracts[reference[0]] = (levels, (link.get(VAL),) if link is not None else None)
            levels, link = self._abstracts[reference[0]]
            if link is not None:  # the levels live with the numbering style's own numbering
                style = self.styles.by_id.get(link[0])
                linked = style.find(f'{PPR}/{NUM_PR}/{NUM_ID}') if style is not None else None
                num_id = linked.get(VAL) if linked is not None else None
                continue
            return levels.get(ilvl)
        return None


# --- walking the body ---------------------------------------------------------------

@dataclass(frozen=True)
class _Context:
    table_style: str | None = None
    paragraph_style: str | None = None
    ascii_font: str | None = None  # the run's fonts, for symbol-font text
    hansi_font: str | None = None


class _Walker:
    """Text of WordprocessingML content in document order, plus what it could not read."""

    def __init__(self, styles: _Styles | None = None, numbering: _Numbering | None = None, background: bool = False):
        self.styles = styles or _Styles()
        self.numbering = numbering or _Numbering()
        self.skipped: collections.Counter[str] = collections.Counter()
        self.tracked_changes = False
        self.unread_alternates = 0
        self.background = background  # the page has a colour: white text may show on it
        self.struck = 0  # runs of text formatted as struck through, read as written
        self.unseen = 0  # runs of white text with nothing shaded behind them, read
        self.checked_bullets = 0  # list paragraphs whose bullet is a checked box
        self.unread_bullets = 0  # unchecked box bullets written unread (no checked box bullet in their list)
        self._style_numbering: dict = {}  # paragraph style -> (numId, ilvl) its chain gives
        self._ING_list = 0  # the list being read: a run of consecutive paragraphs whose bullets are boxes
        self._I2_lists = 0  # list ids handed out (_I2_end_list): a list that ends never resumes under another's id
        self._ING_checked_lists: set = set()  # the lists whose bullets show a checked box
        self._ING_behind: dict = {}  # element -> whether something may be painted behind the text inside it

    @property
    def unread(self) -> bool:
        """Content that may be displayed was not read, or was read although a viewer shows it struck through or may
        not show it: the result is partial."""
        return bool(self.unread_alternates or self.struck or self.unseen)

    def bulleted(self, text: str) -> str:
        """``text`` with each unchecked box bullet written: ☐ when the bullets of its own list (a run of consecutive
        box-bulleted paragraphs in one table cell, one text box or the body) show a checked box too (a checklist), else
        the unread mark, counted: a box-shaped bullet on its own may be a bullet or an empty box, and a checked box in
        another list says nothing of it."""
        if _ING_BULLET not in text:
            return text

        def written(placeholder) -> str:
            if int(placeholder.group(1)) in self._ING_checked_lists:
                return UNCHECKED_BOX
            self.unread_bullets += 1
            return _ING_UNREAD_BOX

        return _ING_PLACEHOLDER.sub(written, text)

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
        if self.struck:
            notes.append(f'The document has text formatted as struck through ({self.struck} '
                         f'run{"" if self.struck == 1 else "s"}); it was read as written, so check it against the '
                         'original.')
        if self.unseen:
            notes.append(f'The document has text that a viewer may not show (white text with nothing shaded behind it, '
                         f'{self.unseen} run{"" if self.unseen == 1 else "s"}); it was read, so check it against the '
                         'original.')
        if self.unread_bullets:
            count = self.unread_bullets
            where = ('and no list bullet that is a checked box' if not self.checked_bullets
                     else f'in {"a list that shows" if count == 1 else "lists that show"} no checked box bullet')
            notes.append(f'The document has {count} list item{"" if count == 1 else "s"} whose bullet is a box, {where}; '
                         f'{"it was" if count == 1 else "they were"} written as unread ([?]), so check the original.')
        return notes

    def blocks(self, container, table_style: str | None = None) -> list[str]:
        lines = []
        for child in container:
            tag = child.tag
            if tag == P:
                lines.extend(self._paragraph(child, table_style))
            elif tag == TBL:
                lines.extend(self._table(child))
            elif tag == SDT and check_box_control(child) is not None:
                glyph = self._check_box(child, _Context(table_style=table_style))
                if glyph:
                    lines.append(glyph)
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
        context = _Context(table_style=table_style, paragraph_style=style)
        self._inline(paragraph, parts, boxes, context)
        line = ''.join(parts)
        if self._I2_mark_hidden(paragraph, context):
            bullet = self._I2_hidden_mark_bullet(paragraph, style, bool(line.strip()))
        else:
            bullet = self._box_bullet(paragraph, style)
        if bullet:  # a checklist drawn with box bullets: Word shows the box before the item
            line = bullet + (' ' + line if line else '')
        return [line, *boxes]

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
                    before = len(parts)
                    self._inline(child, parts, boxes, self._run_context(child, context))
                    if ''.join(parts[before:]).strip():
                        self.struck += self._run_struck(child, context)
                        self.unseen += self._run_unseen(child, context)
            elif tag == FF_DATA:
                box = child.find(CHECK_BOX)
                if box is not None:  # a legacy FORMCHECKBOX: Word draws its state in place of the field
                    parts.append(CHECKED_BOX if legacy_box_checked(box) else UNCHECKED_BOX)
                elif child.find(DROP_DOWN) is not None:
                    self.skipped['form_field'] += 1
            elif tag == TXBX_CONTENT:
                # A text box's paragraphs are lists of their own: they neither join nor check the list of the paragraph
                # that anchors the box (read before the anchor's own bullet), which resumes after them.
                outer = self._ING_list
                self._I2_end_list()
                boxes.extend(self.blocks(child))
                self._ING_list = outer
            elif tag == SDT and check_box_control(child) is not None:
                parts.append(self._check_box(child, context))
            elif tag in (SDT, CUSTOM_XML, INS, MOVE_TO, ALTERNATE_CONTENT):
                content = self._content(child)
                if content is not None:
                    self._inline(content, parts, boxes, context)
            else:
                self._inline(child, parts, boxes, context)

    # Check boxes -------------------------------------------------------------------
    def _check_box(self, sdt, context: _Context) -> str:
        """A check-box content control's glyph, written in place of its content: '' (counted) when it shows a
        placeholder or its content is hidden."""
        content = self._content(sdt)  # a placeholder is skipped and counted, as for any control
        if content is None:
            return ''
        runs = list(content.iter(R))
        if runs and all(self._run_hidden(run, context) for run in runs):
            self.skipped['hidden'] += len(runs)
            return ''
        return CHECKED_BOX if check_box_control(sdt) else UNCHECKED_BOX

    def _box_bullet(self, paragraph, style: str | None) -> str:
        """☒, or the placeholder of an unchecked box tagged with its list (written by bulleted), when the paragraph's
        numbering level is a bullet that draws a box, else '': any other paragraph ends the list of box bullets (as do
        a table cell's and a text box's boundaries, _cell and _inline)."""
        glyph = self._ING_bullet_box(paragraph, style)
        if glyph == CHECKED_BOX:
            self.checked_bullets += 1
            self._ING_checked_lists.add(self._ING_list)
            return CHECKED_BOX
        if glyph == UNCHECKED_BOX:
            return f'{_ING_BULLET}{self._ING_list}{_ING_BULLET}'
        self._I2_end_list()
        return ''

    def _I2_hidden_mark_bullet(self, paragraph, style: str | None, shown: bool) -> str:
        """The bullet of a paragraph whose mark is hidden. Word does not show the bullet as the paragraph's own: with
        no text shown it does not show the paragraph at all; text that shows runs on into the next paragraph. Its box
        never makes a list a checklist and it belongs to no list: where its text shows, a box bullet is the unread mark
        (the placeholder of a list of its own, which shows no checked box); else nothing is written."""
        glyph = self._ING_bullet_box(paragraph, style)
        self._I2_end_list()
        placeholder = f'{_ING_BULLET}{self._ING_list}{_ING_BULLET}' if glyph and shown else ''
        self._I2_end_list()
        return placeholder

    def _I2_end_list(self) -> None:
        """End the list of box bullets being read: what follows starts a list of its own, under an id never used."""
        self._I2_lists += 1
        self._ING_list = self._I2_lists

    def _I2_mark_hidden(self, paragraph, context: _Context) -> bool:
        """Whether a paragraph's mark is hidden: w:vanish in its pPr/rPr, else from its character style, its paragraph
        or table style or the document defaults (resolved as for a run, _run_hidden); or deleted (or moved away) as a
        tracked change, read as accepted. The mark formats the bullet."""
        properties = paragraph.find(PPR)
        mark = properties.find(RPR) if properties is not None else None
        if mark is not None and (mark.find(DEL) is not None or mark.find(MOVE_FROM) is not None):
            return True  # a tracked deletion of the mark, read as accepted: the paragraph runs on into the next
        direct = is_on(mark.find(VANISH)) if mark is not None else None
        if direct is not None:
            return direct
        styles = self.styles
        character = styles.style_id(mark.find(RSTYLE) if mark is not None else None, 'character')
        levels = (styles.document_vanish(), styles.vanish(context.table_style), styles.vanish(context.paragraph_style),
                  styles.vanish(character))
        return any(level is True for level in levels)

    def _ING_bullet_box(self, paragraph, style: str | None) -> str:
        """☐ or ☒ when the paragraph's numbering level is a bullet that draws a box, else ''."""
        level = self.numbering.level(*self._numbering_of(paragraph, style))
        if level is None:
            return ''
        fmt = level.find(NUM_FMT)
        text = level.find(LVL_TEXT)
        if fmt is None or fmt.get(VAL) != 'bullet' or text is None or is_on(level.find(f'{RPR}/{VANISH}')):
            return ''
        fonts = level.find(f'{RPR}/{RFONTS}')
        low, high = symbol_table(font_choice(fonts, 'ascii')), symbol_table(font_choice(fonts, 'hAnsi'))
        shown = []
        for char in text.get(VAL) or '':
            code = ord(char)
            if 0xF000 <= code <= 0xF0FF:
                shown.append(((low if low is not None else high) or {}).get(code - 0xF000, ''))
            elif code <= 0xFF and (low if code < 0x80 else high) is not None:
                shown.append((low if code < 0x80 else high).get(code, ''))
            else:
                shown.append(as_box(char))
        glyph = ''.join(shown).strip()
        return glyph if glyph in (CHECKED_BOX, UNCHECKED_BOX) else ''

    def _numbering_of(self, paragraph, style: str | None) -> tuple[str | None, str]:
        """(numId, ilvl) of the paragraph: its own w:numPr, else its paragraph style chain's (read once per style)."""
        num_id, ilvl = _ING_numbering([paragraph.find(f'{PPR}/{NUM_PR}')])
        if num_id is None or ilvl is None:
            if style not in self._style_numbering:
                self._style_numbering[style] = _ING_numbering(found.find(f'{PPR}/{NUM_PR}')
                                                              for found in self.styles.chain(style))
            inherited = self._style_numbering[style]
            num_id = num_id if num_id is not None else inherited[0]
            ilvl = ilvl if ilvl is not None else inherited[1]
        return num_id, ilvl or '0'

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

    # Text a viewer shows struck through, or may not show -----------------------------
    def _run_struck(self, run, context: _Context) -> bool:
        """Whether a run is formatted as struck through (w:strike or w:dstrike), resolved as w:vanish is: set on the run
        decides; else on in its character, paragraph or table style or the document defaults (each through basedOn).
        Word's toggling of a property both a paragraph and a character style set is read as on."""
        styles = self.styles
        character = styles.style_id(run.find(f'{RPR}/{RSTYLE}'), 'character')
        for tag in _ING_STRIKES:
            direct = is_on(run.find(f'{RPR}/{tag}'))
            if direct is not None:
                if direct:
                    return True
                continue
            levels = (styles.document_toggle(tag), styles.toggle(context.table_style, tag),
                      styles.toggle(context.paragraph_style, tag), styles.toggle(character, tag))
            if any(level is True for level in levels):
                return True
        return False

    def _run_unseen(self, run, context: _Context) -> bool:
        """Whether a run's text is white (on the run, else from its character, paragraph or table style or the document
        defaults) with nothing that may be painted behind it: no shading or highlight on the run, its styles, its
        paragraph, table cell or table, no text box, no page colour."""
        styles = self.styles
        character = styles.style_id(run.find(f'{RPR}/{RSTYLE}'), 'character')
        direct = run.find(f'{RPR}/{_ING_COLOR}')
        choices = (direct.get(VAL) if direct is not None else None, styles.colour(character),
                   styles.colour(context.paragraph_style), styles.colour(context.table_style), styles.document_colour())
        if not _ING_white(next((choice for choice in choices if choice), None)) or self.background:
            return False
        properties = run.find(RPR)
        if properties is not None and any(_ING_paints(found) for found in properties
                                          if found.tag in (_ING_SHD, _ING_HIGHLIGHT)):
            return False
        if styles.shaded(character) or styles.shaded(context.paragraph_style) or styles.shaded(context.table_style):
            return False
        return not self._ING_painted(run.getparent())

    def _ING_painted(self, node) -> bool:
        """Whether something may be painted behind the text inside ``node``: it or an ancestor is a text box, or a
        paragraph, table cell or table whose own shading paints. Each element's verdict is read once and kept, keyed
        by the element itself (the cache holds it, so lxml keeps its identity; never id(), which lxml reuses), so a
        white run costs a lookup, not a walk over its ancestors."""
        chain = []
        verdict = False
        while node is not None:
            known = self._ING_behind.get(node)
            if known is not None:
                verdict = known
                break
            chain.append(node)
            node = node.getparent()
        for element in reversed(chain):  # from the outermost not yet read down to ``node``
            if not verdict:
                if element.tag == TXBX_CONTENT:
                    verdict = True
                else:
                    holder = {P: PPR, TC: _ING_TC_PR, TBL: TBL_PR}.get(element.tag)
                    found = element.find(holder) if holder else None
                    verdict = found is not None and any(_ING_paints(shading) for shading in found
                                                        if shading.tag == _ING_SHD)
            self._ING_behind[element] = verdict
        return verdict

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
        self._I2_end_list()  # a list of box bullets never runs across a cell's boundary, into or out of it
        lines = self.blocks(cell, table_style)
        self._I2_end_list()
        return ' '.join(line.replace('\n', ' ') for line in lines if line.strip())
