"""PDF fonts whose codes pypdf would not turn into the characters a viewer shows (ARCHITECTURE 5.1).

- **Symbol fonts** (Symbol, Wingdings, Zapf Dingbats, ...; tables in
  studio.ingest.symbols) draw pictures at the codes of letters. A simple
  symbol font is replaced, for extraction only, by a copy whose ToUnicode
  CMap maps every code to the character its glyph shows, with check boxes
  as ☐ / ☒. The code is taken from a private-use value (U+F0xx) or a Latin
  echo in the font's own ToUnicode, else from the byte itself; a character
  the font's ToUnicode gives that is neither is trusted. The copy keeps the
  original's glyph widths, default width and space width, so pypdf lays the
  text out exactly as before. A code with no known character maps to a
  private-use mark that the caller counts and drops. A composite (Type0)
  symbol font is mapped character by character after extraction
  (``composite_glyph``).
- **Glyph-index fonts**: a composite font with an Identity CMap, no
  ToUnicode and no CIDToGIDMap stream is written in glyph indices, which name
  no character; pypdf would show them as arbitrary characters. Its text is
  counted and dropped.
- Private-use and control characters from any font name no character
  either; ``undecodable`` says which characters the caller counts and drops.

Importable without Django (the extraction child imports it).
"""
from __future__ import annotations

import re

from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject,
                           NumberObject, StreamObject)
from pypdf.generic._font import Font

from .symbols import SYMBOL_FONTS, as_box

UNMAPPED = ''  # a symbol glyph with no known character: private use, so it is counted and dropped
SIMPLE_FONTS = frozenset({'/Type1', '/MMType1', '/TrueType'})
IDENTITY_CMAPS = frozenset({'/Identity-H', '/Identity-V'})
_SUBSET = re.compile(r'^[A-Z]{6}\+')
_STYLE = re.compile(r'[-,](?:Regular|Roman|Normal|Book|Medium|Bold|Italic|BoldItalic|Oblique|BoldOblique)$', re.I)
_ALIASES = {'symbolmt': 'symbol', 'symbolps': 'symbol', 'zapfdingbatsitc': 'zapfdingbats'}
_FONT_NAME = re.compile(r'[\s_-]+')
CMAP_HEADER = ('/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n'
               '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def\n'
               '/CMapName /CptStudio-Symbol-UCS def\n/CMapType 2 def\n1 begincodespacerange\n<00> <FF>\n'
               'endcodespacerange\n')
CMAP_FOOTER = 'endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n'


def resolved(value):
    return value.get_object() if hasattr(value, 'get_object') else value


def undecodable(char: str) -> bool:
    """A character no font maps a glyph to: a control code (other than tab and line ends) or private use.
    NUL is left to canonicalisation, which removes it."""
    code = ord(char)
    return ((0 < code < 0x20 and char not in '\t\n\r') or 0x7F <= code <= 0x9F or 0xE000 <= code <= 0xF8FF
            or code >= 0xF0000)


def symbol_glyphs(font) -> dict[int, str] | None:
    """The glyph table of the symbol font ``font`` names (possibly empty), or None for a text font."""
    base = resolved(font.get('/BaseFont')) if isinstance(font, DictionaryObject) else None
    if not isinstance(base, str):
        return None
    name = _STYLE.sub('', _SUBSET.sub('', base.removeprefix('/')).split(',')[0])
    key = _FONT_NAME.sub('', name).lower()
    return SYMBOL_FONTS.get(_ALIASES.get(key, key))


def kind(font) -> str:
    """'symbol' (a simple symbol font), 'symbol-composite', 'glyph-index' or 'text'."""
    if not isinstance(font, DictionaryObject):
        return 'text'
    subtype = resolved(font.get('/Subtype'))
    table = symbol_glyphs(font)
    if subtype == '/Type0':
        if table is not None:
            return 'symbol-composite'
        if '/ToUnicode' not in font and resolved(font.get('/Encoding')) in IDENTITY_CMAPS and not _mapped_cids(font):
            return 'glyph-index'
        return 'text'
    return 'symbol' if table is not None and subtype in SIMPLE_FONTS else 'text'


def _mapped_cids(font) -> bool:
    """Whether a descendant font maps its CIDs through a CIDToGIDMap stream (its CIDs may then be characters)."""
    descendants = resolved(font.get('/DescendantFonts'))
    for descendant in descendants if isinstance(descendants, (list, ArrayObject)) else []:
        descendant = resolved(descendant)
        if isinstance(descendant, DictionaryObject) and isinstance(resolved(descendant.get('/CIDToGIDMap')),
                                                                   StreamObject):
            return True
    return False


def glyph_for(code: int, shown: str | None, table: dict[int, str], named: str | None = None,
              renamed: bool = False) -> str:
    """The character code ``code`` of a simple symbol font shows; ``shown`` is what its ToUnicode gives.

    ``renamed``: the font's /Differences re-encodes the code to a glyph name; ``named`` is the character that name
    shows (None when it cannot be resolved). The glyph a name selects is what viewers draw, so it decides over a
    private-use value or a Latin echo, and over the built-in table; a real Unicode ToUnicode value stays trusted.
    A re-encoded code whose name cannot be resolved names no character: the built-in table no longer applies."""
    if shown:
        if shown.isspace():
            return shown
        if len(shown) == 1:
            value = ord(shown)
            if 0xF000 <= value <= 0xF0FF:
                return named if named is not None else table.get(value - 0xF000, UNMAPPED)
            if value <= 0xFF or 0xE000 <= value <= 0xF8FF:  # a Latin echo of the code, or another private code
                return named if named is not None else UNMAPPED if renamed else table.get(code, UNMAPPED)
            return as_box(shown)
        return shown
    if renamed:
        return named if named is not None else UNMAPPED
    if code == 0x20:
        return ' '
    return table.get(code, UNMAPPED)


MAX_DIFFERENCES = 4096  # entries of an /Encoding /Differences array read (a meaningful one has at most 256 names)
_UNI_NAME = re.compile(r'uni([0-9A-F]{4})|u([0-9A-F]{4,6})')


def differences(font: DictionaryObject) -> dict[int, str]:
    """{code: glyph name} for the codes a simple font's /Encoding /Differences re-encodes."""
    encoding = resolved(font.get('/Encoding'))
    items = resolved(encoding.get('/Differences')) if isinstance(encoding, DictionaryObject) else None
    names: dict[int, str] = {}
    code = None
    for item in list(items)[:MAX_DIFFERENCES] if isinstance(items, (list, ArrayObject)) else []:
        item = resolved(item)
        if isinstance(item, NameObject):
            if code is not None and 0 <= code <= 0xFF:
                names[code] = str(item).removeprefix('/')
            code = None if code is None else code + 1
        elif isinstance(item, int) and not isinstance(item, bool):
            code = int(item)
    return names


def named_glyph(name: str, table: dict[int, str]) -> str | None:
    """The character the glyph ``name`` shows in the symbol font whose glyphs are ``table``: one of the font's own
    built-in glyph names, or a uniXXXX / uXXXX name; None for a name this cannot resolve (.notdef, a glyph
    index such as g17, a suffixed variant such as a74.alt, a name the font does not have). pypdf's glyph list is
    not used: it reads Zapf Dingbats' 'a74' as 'J' and '.notdef' as '□'."""
    if name == 'space':
        return ' '
    match = _UNI_NAME.fullmatch(name)
    if match:
        value = int(match.group(1) or match.group(2), 16)
        if 0xF000 <= value <= 0xF0FF:
            return table.get(value - 0xF000, UNMAPPED)
        if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF or undecodable(chr(value)):
            return UNMAPPED
        return as_box(chr(value))
    code = getattr(table, 'names', {}).get(name)
    return None if code is None else table.get(code, UNMAPPED)


def mapped_simple_font(font: DictionaryObject) -> DictionaryObject | None:
    """A copy of a simple symbol font whose ToUnicode maps every code to the character its glyph shows, with
    the original's width model; None when ``font`` is not one, or cannot be read. A symbol font whose copy cannot
    be built is replaced by one that names no character for any glyph, so its glyphs are counted, never read as
    the letters that encode them."""
    table = symbol_glyphs(font)
    if table is None or resolved(font.get('/Subtype')) not in SIMPLE_FONTS:
        return None
    try:
        original = Font.from_font_resource(font)
    except Exception:  # a font pypdf cannot read: its text is extracted (or not) as before
        return None
    try:
        # pypdf keys a simple font's ToUnicode map by the code's own character (its encoding maps a /Differences
        # code to its glyph name's character, which may be another code's key).
        own_map = original.character_map if '/ToUnicode' in font else {}
        renamed = differences(font)
        glyphs = {code: glyph_for(code, own_map.get(chr(code)), table,
                                  named_glyph(renamed[code], table) if code in renamed else None, code in renamed)
                  for code in range(256)}
        copy = _with_to_unicode(font, glyphs, ('/ToUnicode', '/FirstChar', '/LastChar', '/Widths', '/FontDescriptor'))
        _copy_widths(original, font, copy)
        return copy
    except (MemoryError, RecursionError):
        raise
    except Exception:  # a malformed font: none of its glyphs is read
        try:
            return _with_to_unicode(font, {code: ' ' if code == 0x20 else UNMAPPED for code in range(256)},
                                    ('/ToUnicode',))
        except Exception:
            return None


def _with_to_unicode(font: DictionaryObject, glyphs: dict[int, str], dropped: tuple) -> DictionaryObject:
    copy = DictionaryObject({NameObject(key): font.raw_get(key) for key in font if key not in dropped})
    stream = DecodedStreamObject()
    stream.set_data(_to_unicode(glyphs).encode('ascii'))
    copy[NameObject('/ToUnicode')] = stream
    return copy


def _to_unicode(glyphs: dict[int, str]) -> str:
    # 'surrogatepass': a lone surrogate the font's own ToUnicode gives is carried as it is; pypdf decodes it the
    # same way, and the page reader replaces it and names the page, as for any text font.
    entries = [f'<{code:02X}> <{text.encode("utf-16-be", "surrogatepass").hex().upper()}>'
               for code, text in sorted(glyphs.items())]
    blocks = [entries[start:start + 100] for start in range(0, len(entries), 100)]
    return CMAP_HEADER + ''.join(f'{len(block)} beginbfchar\n' + '\n'.join(block) + '\nendbfchar\n'
                                 for block in blocks) + CMAP_FOOTER


def _copy_widths(original: Font, font: DictionaryObject, copy: DictionaryObject) -> None:
    """Explicit widths for codes 0-255, a /MissingWidth and the original flags, so that pypdf derives the same
    glyph widths, default width and space width from the copy as from the original."""
    widths = original.character_widths
    default = widths.get('default', 0)
    space = original.space_char
    entries = []
    for code in range(256):
        char = chr(code)
        width = widths.get(char)
        if width is None:  # pypdf falls back to the default; the space falls back through its own rule
            width = 0 if char == space else default
        entries.append(FloatObject(width) if isinstance(width, float) else NumberObject(int(width)))
    copy[NameObject('/FirstChar')] = NumberObject(0)
    copy[NameObject('/LastChar')] = NumberObject(255)
    copy[NameObject('/Widths')] = ArrayObject(entries)
    descriptor = resolved(font.get('/FontDescriptor'))
    described = DictionaryObject({NameObject(key): descriptor.raw_get(key) for key in descriptor}) \
        if isinstance(descriptor, DictionaryObject) else DictionaryObject({NameObject('/Type'): NameObject(
            '/FontDescriptor')})
    described[NameObject('/Flags')] = NumberObject(int(original.font_descriptor.flags))
    described[NameObject('/MissingWidth')] = FloatObject(default) if isinstance(default, float) \
        else NumberObject(int(default))
    copy[NameObject('/FontDescriptor')] = described


def composite_map(font: DictionaryObject) -> frozenset:
    """The characters a composite symbol font's ToUnicode gives (its trusted outputs)."""
    try:
        return frozenset(value for value in Font.from_font_resource(font).character_map.values()
                         if isinstance(value, str))
    except Exception:
        return frozenset()


def composite_glyph(char: str, trusted: frozenset, table: dict[int, str]) -> str | None:
    """The character a composite symbol font's extracted ``char`` stands for, or None when it names none.

    A character the font's ToUnicode gives is trusted. A Latin-1 one is the echo of the symbol code (a browser
    printing a page styled in Wingdings writes '¨' for the empty box), read through the table as ``glyph_for``
    reads a simple font's echo; but only in a font none of whose glyphs is a Latin-1 character (not Symbol, whose
    '×' or '±' may be the glyph itself): there it stays unread and counted."""
    if char.isspace():
        return char
    value = ord(char)
    if 0xF000 <= value <= 0xF0FF:
        return table.get(value - 0xF000)
    if char in trusted and not undecodable(char):
        if value > 0xFF:
            return as_box(char)
        if not getattr(table, 'latin', True):
            return table.get(value)
    return None
