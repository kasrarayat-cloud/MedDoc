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
- NUL, private-use and control characters from any font name no character
  either; ``undecodable`` says which characters the caller counts and drops.
- **Glyph names pypdf reads by its own rule** (``mapped_font``). pypdf 6.21.4
  reads a /Differences or built-in glyph name that is not in the Adobe Glyph
  List and starts with 'u' by int(name, 16): 'u20' as a space, 'uni0000' as
  NUL, 'uF00C' as a private-use character, and a name too long for a
  character fails the font. A text font holding such a name, or whose
  program pypdf cannot read for its built-in encoding, is replaced, for
  extraction only, by a copy whose ToUnicode gives every code what the PDF
  encodes, in the precedence PDF 32000-1 9.6.6 and 9.10.2 give: the font's
  own ToUnicode, then /Differences, then the dictionary's named encoding,
  then the font program's built-in encoding (where no named encoding
  replaces it). A glyph name is read by the Adobe Glyph List specification
  (section 2: the list's own entry; else the name up to its first period,
  each '_' component a name the list holds, 'uni' and groups of four
  upper-case hex digits, or 'u' and four to six). A name that stands for no
  character (no component maps, a control or private-use code, a
  noncharacter), and a ToUnicode entry that gives none (an empty
  destination), are counted and dropped.
- **Fonts pypdf 6.21.4 no longer builds** (a /BaseEncoding that is not a
  name, /W entries that are not widths): the copy extraction reads leaves
  that entry out, as pypdf 6.21.2 ignored it, so the text is read and is not
  replaced by U+FFFD for every byte. A composite font whose /Encoding is an
  embedded CMap of two-byte codes only (fpdf2's CID-keyed CFF fonts) is read
  through a copy with the Identity CMap and its widths by code, so its
  ToUnicode decides every code.
- **Text pypdf cannot read as the PDF encodes it** (``decodes``): a composite
  font whose CMap pypdf does not implement (it reads the bytes as UTF-16BE,
  which is what a UCS-2 or UTF-16 CMap encodes and nothing else does), or a
  string its CMap cannot decode (an odd byte count in a two-byte font). The
  page reader draws such text, for extraction only, in ``unread_font``, so
  that the operator showing it is dropped and named rather than read as
  pypdf's U+FFFD and mojibake.
- ``FontReadings`` works each of these out once per font and font program for
  a whole document, and a font whose inspection fails (pypdf's structure
  limits among the reasons) is a font whose text cannot be read.

Importable without Django (the extraction child imports it).
"""
from __future__ import annotations

import bisect
import math
import re

from pypdf._cmap import _predefined_cmap
from pypdf._codecs import adobe_glyphs, charset_encoding
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject,
                           NumberObject, StreamObject)
from pypdf.generic._font import Font

from .symbols import BOX_PAD, SYMBOL_FONTS, as_box

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
    """A character no font maps a glyph to: NUL or another control code (other than tab and line ends), private use,
    or a noncharacter (U+FDD0-U+FDEF, and the last two code points of every plane, U+FFFF among them). A ToUnicode
    entry <0000> is what producers write for a glyph with no character (pdfkit for .notdef)."""
    code = ord(char)
    return ((code < 0x20 and char not in '\t\n\r') or 0x7F <= code <= 0x9F or 0xE000 <= code <= 0xF8FF
            or code >= 0xF0000 or 0xFDD0 <= code <= 0xFDEF or (code & 0xFFFE) == 0xFFFE)


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
        encoding = resolved(font.get('/Encoding'))  # a name, or (malformed) a CMap stream or a dictionary
        if '/ToUnicode' not in font and isinstance(encoding, str) and encoding in IDENTITY_CMAPS \
                and not _mapped_cids(font):
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


_UNI_NAME = re.compile(r'uni([0-9A-F]{4})|u([0-9A-F]{4,6})')


def differences(font: DictionaryObject) -> dict[int, str]:
    """{code: glyph name} for the codes a simple font's /Encoding /Differences re-encodes, read as pypdf reads the
    array, so that no name pypdf applies is missed: every item (pypdf's parser bounds an array's length), a number
    setting the next code (0 before any), any other item taking the next code, and a code from -256 to -1 standing for
    the code 256 above it (pypdf indexes its 256-entry table with it)."""
    encoding = resolved(font.get('/Encoding'))
    items = resolved(encoding.get('/Differences')) if isinstance(encoding, DictionaryObject) else None
    names: dict[int, str] = {}
    code = 0
    for item in items if isinstance(items, (list, ArrayObject)) else []:
        if isinstance(item, int) and not isinstance(item, bool):  # as pypdf: a number item, not a reference to one
            code = int(item)
            continue
        item = resolved(item)
        if isinstance(item, NameObject) and -0x100 <= code <= 0xFF:
            names[code % 0x100] = str(item).removeprefix('/')
        code += 1
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


def mapped_font(font) -> DictionaryObject | None:
    """The copy of ``font`` that extraction reads in its place, or None when pypdf reads ``font`` itself as the
    PDF encodes it (or cannot read it at all: the page reader then treats its text as unreadable)."""
    return font_reading(font)[0]


def font_reading(font, programs: dict | None = None, built: Font | None = None) -> tuple[DictionaryObject | None, bool]:
    """(the copy of ``font`` extraction reads in its place, or None; whether pypdf builds what extraction reads for
    it: the copy, or the font itself). A font pypdf cannot build is drawn by its extractor in a stand-in font that
    reads every byte as U+FFFD. ``programs``: as builtin_encoding; ``built``: pypdf's Font of a composite ``font``,
    when it was built already (it is not built again)."""
    if not isinstance(font, DictionaryObject):
        return None, False
    subtype = resolved(font.get('/Subtype'))
    if subtype == '/Type0':
        return _composite_copy(font, built)
    if symbol_glyphs(font) is not None and subtype in SIMPLE_FONTS:
        copy = mapped_simple_font(font)
        return copy, copy is not None
    if subtype in SIMPLE_FONTS or subtype == '/Type3':
        return _text_font_copy(font, programs)
    try:
        Font.from_font_resource(font)
        return None, True
    except (MemoryError, RecursionError):
        raise
    except Exception:
        return None, False


def mapped_simple_font(font: DictionaryObject) -> DictionaryObject | None:
    """A copy of a simple symbol font whose ToUnicode maps every code to the character its glyph shows, with
    the original's width model; None when ``font`` is not one, or cannot be read. A symbol font whose copy cannot
    be built is replaced by one that names no character for any glyph, so its glyphs are counted, never read as
    the letters that encode them."""
    table = symbol_glyphs(font)
    if table is None or resolved(font.get('/Subtype')) not in SIMPLE_FONTS:
        return None
    original, base = buildable(font)
    if original is None:  # a font pypdf cannot read: its text is extracted (or not) as before
        return None
    try:
        # pypdf keys a simple font's ToUnicode map by the code's own character (its encoding maps a /Differences
        # code to its glyph name's character, which may be another code's key).
        own_map = original.character_map if '/ToUnicode' in font else {}
        renamed = differences(font)
        glyphs = {code: glyph_for(code, own_map.get(chr(code)), table,
                                  named_glyph(renamed[code], table) if code in renamed else None, code in renamed)
                  for code in range(256)}
        copy = _with_to_unicode(base, glyphs, ('/ToUnicode', '/FirstChar', '/LastChar', '/Widths', '/FontDescriptor'))
        _copy_widths(original, base, copy)
        return copy
    except (MemoryError, RecursionError):
        raise
    except Exception:  # a malformed font: none of its glyphs is read
        try:
            return _with_to_unicode(base, {code: ' ' if code == 0x20 else UNMAPPED for code in range(256)},
                                    ('/ToUnicode',))
        except Exception:
            return None


# --- what pypdf 6.21.4 reads differently: glyph names, fonts it no longer builds, CMaps it does not implement --------

_AGL_UNI = re.compile(r'uni((?:[0-9A-F]{4})+)')
_AGL_U = re.compile(r'u([0-9A-F]{4,6})')
MAX_FONT_PROGRAM_BYTES = 4 * 1024 * 1024  # a Type 1 program's clear text read for its built-in encoding


def _agl_component(name: str) -> str:
    """What one component of a glyph name maps to (Adobe Glyph List specification, section 2, step 3): a name the
    list holds; 'uni' and groups of four upper-case hex digits each naming a character outside the surrogates; 'u'
    and four to six naming one; '' for anything else (other digit counts, lower case, '0x', '+')."""
    known = adobe_glyphs.get('/' + name)
    if known is not None:
        return known
    match = _AGL_UNI.fullmatch(name)
    if match:
        digits = match.group(1)
        values = [int(digits[start:start + 4], 16) for start in range(0, len(digits), 4)]
        return '' if any(0xD800 <= value <= 0xDFFF for value in values) else ''.join(map(chr, values))
    match = _AGL_U.fullmatch(name)
    if match:
        value = int(match.group(1), 16)
        return '' if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF else chr(value)
    return ''


def agl_text(name: str) -> str | None:
    """The characters the glyph ``name`` stands for under the Adobe Glyph List specification (section 2): the list's
    own entry for the whole name; else the name up to its first period ('uni2610.alt', 'u2610.001'), split at '_'
    into components ('uni2610_uni2612'), each mapped by ``_agl_component`` and joined; None when that is nothing."""
    known = adobe_glyphs.get('/' + name)
    if known is not None:
        return known
    return ''.join(_agl_component(part) for part in name.split('.', 1)[0].split('_')) or None


def pypdf_reads_by_number(name: str) -> bool:
    """Whether pypdf 6.21.4 may read the glyph ``name`` otherwise than the Adobe Glyph List specification: a name
    outside its glyph list that starts with 'u', which it reads as int(rest, 16) where that parses (pypdf 6.21.2 did
    not apply that rule to /Differences, nor to 'u' names anywhere) and else as the literal name."""
    return name.startswith('u') and '/' + name not in adobe_glyphs


def _names_no_character(text: str) -> bool:
    return not text or any(char == '\x00' or undecodable(char) for char in text)


def builtin_encoding(font: DictionaryObject, programs: dict | None = None) -> dict[int, str]:
    """{code: glyph name} of the built-in encoding pypdf reads from a Type 1 font program (/FontFile) when the font
    has no ToUnicode: the 'dup <code> /<name> put' lines of its clear text after /Encoding, as pypdf parses them,
    without its failures (a name too long for a character, bytes that are not UTF-8, a code outside 0-255).
    ``programs`` ({id(program): (program, names)}, kept by FontReadings) holds the program's names once read: every
    font dictionary that shares the program, on every page and annotation, reads them from there."""
    if '/ToUnicode' in font or resolved(font.get('/Subtype')) != '/Type1':
        return {}
    descriptor = resolved(font.get('/FontDescriptor'))
    program = resolved(descriptor.get('/FontFile')) if isinstance(descriptor, DictionaryObject) else None
    if not isinstance(program, StreamObject):
        return {}
    known = programs.get(id(program)) if programs is not None else None
    if known is not None and known[0] is program:
        return known[1]
    names = _program_names(program)
    if programs is not None:
        programs[id(program)] = (program, names)  # the program is kept with its names: its id stays its own
    return names


def _program_names(program: StreamObject) -> dict[int, str]:
    try:
        data = program.get_data()[:MAX_FONT_PROGRAM_BYTES]
    except (MemoryError, RecursionError):
        raise
    except Exception:
        return {}
    parts = data.split(b'eexec\n')[0].split(b'/Encoding')
    names: dict[int, str] = {}
    for line in (parts[1].replace(b'\r', b'\n').split(b'\n') if len(parts) > 1 else []):
        if not line.startswith(b'dup'):
            continue
        words = [word for word in line.split(b' ') if word]
        if len(words) < 3 or (len(words) > 3 and words[3] != b'put'):
            continue
        try:
            code, name = int(words[1]), words[2].decode('latin-1')
        except ValueError:
            continue
        if 0 <= code <= 0xFF and name.startswith('/'):
            names[code] = name[1:]
    return names


def _sanitised(font: DictionaryObject) -> DictionaryObject | None:
    """A copy of ``font`` without what pypdf 6.21.4 no longer reads but pypdf 6.21.2 ignored: a /BaseEncoding that is
    not a name (6.21.2 used StandardEncoding); None when there is nothing to leave out."""
    encoding = resolved(font.get('/Encoding'))
    if not isinstance(encoding, DictionaryObject) or '/BaseEncoding' not in encoding \
            or isinstance(resolved(encoding.get('/BaseEncoding')), NameObject):
        return None
    copy = DictionaryObject({NameObject(key): font.raw_get(key) for key in font})
    copy[NameObject('/Encoding')] = DictionaryObject({NameObject(key): encoding.raw_get(key) for key in encoding
                                                      if key != '/BaseEncoding'})
    return copy


def _without_program(font: DictionaryObject) -> DictionaryObject | None:
    """A copy of ``font`` whose descriptor has no embedded program, or None when it has none."""
    descriptor = resolved(font.get('/FontDescriptor'))
    if not isinstance(descriptor, DictionaryObject) or not any(key in descriptor for key in ('/FontFile', '/FontFile2',
                                                                                             '/FontFile3')):
        return None
    copy = DictionaryObject({NameObject(key): font.raw_get(key) for key in font})
    copy[NameObject('/FontDescriptor')] = DictionaryObject({NameObject(key): descriptor.raw_get(key)
                                                            for key in descriptor
                                                            if key not in ('/FontFile', '/FontFile2', '/FontFile3')})
    return copy


def buildable(font: DictionaryObject) -> tuple[Font | None, DictionaryObject | None]:
    """(the pypdf Font, the dictionary it was built from) for ``font``: itself when pypdf builds it, else the first of
    a copy without an unusable /BaseEncoding and a copy without its font program as well that pypdf builds;
    (None, None) when none does."""
    sanitised = _sanitised(font)
    for candidate in (font, sanitised, _without_program(sanitised if sanitised is not None else font)):
        if candidate is None:
            continue
        try:
            return Font.from_font_resource(candidate), candidate
        except Exception:
            continue
    return None, None


def _text_font_copy(font: DictionaryObject, programs: dict | None = None) -> tuple[DictionaryObject | None, bool]:
    """(a copy of a simple text font that pypdf reads as the PDF encodes it (see the module docstring), or None when
    pypdf reads the font itself so; whether pypdf builds what extraction reads), as font_reading.

    The copy is made for a font holding a glyph name pypdf 6.21.4 reads by its own rule, or whose program pypdf
    cannot read for the built-in encoding its codes come from: every code then reads as the source encodes it
    (``by_source``), which also keeps a /Differences character from being looked up again as another code's. A font
    whose own ToUnicode gives some code no character (an empty destination: pypdf writes nothing for the glyph) gets
    a copy in which that code is the private-use mark that is counted and dropped, every other code as pypdf reads
    it."""
    names = differences(font)
    builtin = builtin_encoding(font, programs)
    by_number = {code for code, name in names.items() if pypdf_reads_by_number(name)}
    by_number |= {code for code, name in builtin.items() if pypdf_reads_by_number(name)}
    original, base = buildable(font)
    if original is None:
        return None, False
    # True when pypdf cannot read the font program, so the codes its built-in encoding names would be read as
    # StandardEncoding guesses (pypdf reads the copy without the program).
    lost = resolved(base.get('/FontDescriptor')) is not resolved(font.get('/FontDescriptor'))
    own = original.character_map if '/ToUnicode' in font else {}  # the font's own ToUnicode, by the code's character
    by_source = bool(by_number) or (lost and bool(builtin))
    if not by_source and '' not in own.values():
        return (None, True) if base is font else (base, True)
    encoding = resolved(font.get('/Encoding'))
    named = encoding if isinstance(encoding, NameObject) else \
        resolved(encoding.get('/BaseEncoding')) if isinstance(encoding, DictionaryObject) else None
    table = charset_encoding.get(named) if isinstance(named, NameObject) else None
    pypdf_encoding = original.encoding if isinstance(original.encoding, dict) else {}

    def read(code: int) -> str:
        mine = own.get(chr(code))
        if mine is not None:  # the font's own ToUnicode decides (PDF 32000-1 9.10.2); '' gives no character
            return mine if mine and not _names_no_character(mine) else UNMAPPED
        if not by_source:
            # as pypdf reads it: its encoding, then its character map, character by character
            text = ''.join(original.character_map.get(char, char) for char in pypdf_encoding.get(code, chr(code)))
            return text or UNMAPPED
        difference = names.get(code)
        if difference is not None:
            text = agl_text(difference)  # /Differences decides (PDF 32000-1 9.6.6.1)
        elif table is not None:
            text = table[code]  # the dictionary's named encoding, which replaces the program's built-in one
        elif code in builtin:
            text = agl_text(builtin[code])  # the program's built-in encoding is the base (9.6.6.2, Table 112)
        else:
            text = pypdf_encoding.get(code, chr(code))  # a code the program does not name: as pypdf's base gives it
        return UNMAPPED if text is None or _names_no_character(text) else text

    try:
        glyphs = {code: read(code) for code in range(256)}
        copy = _with_to_unicode(base, glyphs, ('/ToUnicode', '/FirstChar', '/LastChar', '/Widths', '/FontDescriptor'))
        _copy_widths(original, base, copy)
        Font.from_font_resource(copy)
        return copy, True
    except (MemoryError, RecursionError):
        raise
    except Exception:
        return (None, True) if base is font else (base, True)


def _composite_copy(font: DictionaryObject, built: Font | None = None) -> tuple[DictionaryObject | None, bool]:
    """A copy of a composite font: read with the Identity CMap when its /Encoding is an embedded CMap of two-byte codes
    with a ToUnicode (``_identity_copy``); with its ToUnicode's empty destinations as the private-use mark that is
    counted and dropped (``_marked_copy``); or with its descendant's /W keeping only width entries, when pypdf 6.21.4
    cannot build the font itself because of the others (a string or a name where a width list belongs: pypdf 6.21.2
    kept them as widths of codes the text rarely uses). None when pypdf builds the font and reads it as the PDF
    encodes it, or cannot build a copy either; as font_reading."""
    encoding = resolved(font.get('/Encoding'))
    if isinstance(encoding, StreamObject) and '/ToUnicode' in font:
        identity = _identity_copy(font, encoding)
        if identity is not None:
            return identity, True
    if built is None:
        try:
            built = Font.from_font_resource(font)
        except (MemoryError, RecursionError):
            raise
        except Exception:
            built = None
    if built is not None:
        marked = _marked_copy(font, built)
        return marked, True
    descendants = resolved(font.get('/DescendantFonts'))
    if not isinstance(descendants, (list, ArrayObject)) or not descendants:
        return None, False
    try:
        copies = ArrayObject()
        for descendant in descendants:
            descendant = resolved(descendant)
            if not isinstance(descendant, DictionaryObject):
                return None, False
            copy = DictionaryObject({NameObject(key): descendant.raw_get(key) for key in descendant})
            if '/W' in descendant:
                copy[NameObject('/W')] = _widths_only(resolved(descendant.get('/W')))
            copies.append(copy)
        whole = DictionaryObject({NameObject(key): font.raw_get(key) for key in font})
        whole[NameObject('/DescendantFonts')] = copies
        Font.from_font_resource(whole)
        return whole, True
    except (MemoryError, RecursionError):
        raise
    except Exception:
        return None, False


def _number(value) -> bool:
    value = resolved(value)
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _widths_only(entries) -> ArrayObject:
    """The entries of a CID font's /W that are widths (PDF 32000-1 9.7.4.3): 'c [w ...]' with numbers in the list, and
    'c_first c_last w'; anything else is left out."""
    items = [resolved(item) for item in entries] if isinstance(entries, (list, ArrayObject)) else []
    kept, index = ArrayObject(), 0
    while index < len(items):
        first = items[index]
        following = items[index + 1] if index + 1 < len(items) else None
        if _number(first) and isinstance(following, (list, ArrayObject)) and not isinstance(following, str) \
                and all(_number(width) for width in following):
            kept.extend([NumberObject(int(first)), ArrayObject(FloatObject(float(resolved(width)))
                                                               for width in following)])
            index += 2
        elif _number(first) and _number(following) and index + 2 < len(items) and _number(items[index + 2]):
            kept.extend([NumberObject(int(first)), NumberObject(int(resolved(following))),
                         FloatObject(float(items[index + 2]))])
            index += 3
        else:
            index += 1
    return kept


def composite_codec(font) -> str | None:
    """The codec pypdf decodes a composite font's strings with when that is what the font's CMap encodes: its
    predefined table, or UTF-16BE for a UCS-2 or UTF-16 CMap (pypdf reads every CMap it does not implement as
    UTF-16BE, which is exactly what those encode: MuPDF's /UniKS-UTF16-H among them); None for any other (another
    predefined CMap, an embedded CMap stream, a dictionary or no /Encoding)."""
    encoding = resolved(font.get('/Encoding'))
    if not isinstance(encoding, NameObject):
        return None
    if encoding in _predefined_cmap:
        return _predefined_cmap[encoding]
    return 'utf-16-be' if '-UCS2-' in encoding or '-UTF16-' in encoding else None


def decode_plan(font) -> bool | str:
    """How the strings a font shows are judged (``decodes``), worked out once per font: True when pypdf reads every
    string as the font encodes it, False when it reads none so, else the codec under which a string must decode. A
    simple font maps each byte through a code table, unless its /Encoding names a CMap. A glyph-index font's codes are
    dropped by the page reader, so whatever pypdf makes of them is not read. Any other composite font needs a CMap
    pypdf implements under which the whole string decodes: pypdf 6.21.2 refused a string that does not (or wrote lone
    surrogates), and 6.21.4 writes U+FFFD and mojibake."""
    encoding = resolved(font.get('/Encoding'))
    if resolved(font.get('/Subtype')) != '/Type0':
        return not (isinstance(encoding, str) and encoding not in charset_encoding
                    and (encoding in _predefined_cmap or '-UCS2-' in encoding))
    if kind(font) == 'glyph-index':
        return True
    codec = composite_codec(font)
    return False if codec is None else codec


def decodes(font, string: bytes, plan: bool | str | None = None) -> bool:
    """Whether pypdf reads ``string`` shown in ``font`` (a font dictionary) as the font encodes it (``plan``: the
    font's decode_plan, when worked out already). A UTF-16BE string decodes when its byte count is even: a lone
    surrogate passes, as pypdf passes it, and the page reader replaces and names it."""
    if not string:
        return True
    plan = decode_plan(font) if plan is None else plan
    if isinstance(plan, bool):
        return plan
    if plan == 'utf-16-be':
        return len(string) % 2 == 0
    try:
        string.decode(plan, 'surrogatepass')
    except UnicodeDecodeError:
        return False
    return True


# --- reading composite fonts through a copy --------------------------------------------------------------------------

MAX_EMBEDDED_CMAP_BYTES = 1 << 20  # an embedded CMap read for its code lengths and CIDs
MAX_CMAP_CODES = 0x10000  # two-byte codes: at most this many, and four times as many range steps
MAX_WIDTH_STEPS = 1 << 20  # /W entries matched against the CIDs a copy needs
_CMAP_SECTION = re.compile(rb'begin(codespacerange|cidchar|cidrange)(.*?)end\1', re.S)
_CMAP_TOKEN = re.compile(rb'<[0-9A-Fa-f\s]*>|[-+]?\d+')


def _two_byte_code(token: bytes) -> int | None:
    digits = re.sub(rb'\s', b'', token[1:-1]) if token.startswith(b'<') else b''
    return int(digits, 16) if len(digits) == 4 else None


def _cmap_codes(cmap: StreamObject) -> dict[int, int] | None:
    """{code: CID} of an embedded CMap every code space range of which is two bytes long; None for any other (another
    code length, a CMap that uses another, one too large to read here, a malformed section)."""
    try:
        data = cmap.get_data()
    except (MemoryError, RecursionError):
        raise
    except Exception:
        return None
    if len(data) > MAX_EMBEDDED_CMAP_BYTES or b'usecmap' in data:
        return None
    spaces, codes, steps = 0, {}, 0
    for section, body in _CMAP_SECTION.findall(data):
        tokens = _CMAP_TOKEN.findall(body)
        if section == b'codespacerange':
            if not tokens or len(tokens) % 2 or any(_two_byte_code(token) is None for token in tokens):
                return None
            spaces += len(tokens) // 2
            continue
        width = 2 if section == b'cidchar' else 3
        if len(tokens) % width:
            return None
        for start in range(0, len(tokens), width):
            group = tokens[start:start + width]
            low, high = _two_byte_code(group[0]), _two_byte_code(group[width - 2])
            if low is None or high is None or high < low or group[-1].startswith(b'<'):
                return None
            steps += high - low + 1
            if steps > 4 * MAX_CMAP_CODES:
                return None
            for offset in range(high - low + 1):
                codes[low + offset] = int(group[-1]) + offset
    return codes if spaces else None


def _cid_widths(entries, needed: set) -> dict[int, float]:
    """{CID: width} for the CIDs in ``needed`` that a CID font's /W gives (its width entries, as _widths_only),
    matched through at most MAX_WIDTH_STEPS steps (past them a CID keeps the default width)."""
    items, wanted = list(_widths_only(entries)), sorted(needed)
    widths, index, steps = {}, 0, 0
    while index < len(items) and steps <= MAX_WIDTH_STEPS:
        first = int(items[index])
        if isinstance(items[index + 1], ArrayObject):
            run = items[index + 1]
            for cid in wanted[bisect.bisect_left(wanted, first):bisect.bisect_right(wanted, first + len(run) - 1)]:
                widths[cid] = float(run[cid - first])
                steps += 1
            index += 2
        else:
            last, width = int(items[index + 1]), float(items[index + 2])
            for cid in wanted[bisect.bisect_left(wanted, first):bisect.bisect_right(wanted, last)]:
                widths[cid] = width
                steps += 1
            index += 3
        steps += 1
    return widths


def _w_array(entries) -> ArrayObject:
    """A /W array giving each (code, width) of ``entries`` (sorted by code), consecutive codes in one list."""
    out, start, run = ArrayObject(), None, []
    for code, width in list(entries) + [(None, None)]:
        if run and code == start + len(run):
            run.append(width)
            continue
        if run:
            out.extend([NumberObject(start), ArrayObject(FloatObject(value) for value in run)])
        start, run = code, [width]
    return out


def _identity_copy(font: DictionaryObject, cmap: StreamObject) -> DictionaryObject | None:
    """A copy of a composite font whose /Encoding is an embedded CMap of two-byte codes (fpdf2 writes one for a
    CID-keyed CFF font), read with the Identity CMap: each code stays two bytes, the font's ToUnicode gives its
    characters, and the descendant's widths are given by code (through the CMap's CIDs), so pypdf measures the text as
    the font draws it. pypdf reads such a font one byte a code (StandardEncoding), which is right only by accident, for
    codes below 0x100 its ToUnicode holds. None when the CMap is not that, or pypdf cannot build the copy."""
    codes = _cmap_codes(cmap)
    descendants = resolved(font.get('/DescendantFonts'))
    if codes is None or not isinstance(descendants, (list, ArrayObject)) or len(descendants) != 1:
        return None
    descendant = resolved(descendants[0])
    if not isinstance(descendant, DictionaryObject):
        return None
    try:
        widths = _cid_widths(resolved(descendant.get('/W')), set(codes.values()))
        inner = DictionaryObject({NameObject(key): descendant.raw_get(key) for key in descendant})
        inner[NameObject('/W')] = _w_array(sorted((code, widths[cid]) for code, cid in codes.items() if cid in widths))
        whole = DictionaryObject({NameObject(key): font.raw_get(key) for key in font})
        vertical = resolved(cmap.get('/WMode')) == 1
        whole[NameObject('/Encoding')] = NameObject('/Identity-V' if vertical else '/Identity-H')
        whole[NameObject('/DescendantFonts')] = ArrayObject([inner])
        Font.from_font_resource(whole)
        return whole
    except (MemoryError, RecursionError):
        raise
    except Exception:
        return None


def _marked_copy(font: DictionaryObject, built: Font) -> DictionaryObject | None:
    """A copy of a composite font whose ToUnicode gives some code no character (an empty destination: pypdf writes
    nothing for the glyph, so a mark alone in typed brackets would leave an empty box): its ToUnicode followed by
    entries that give each such code the private-use mark that is counted and dropped. None when no code has an empty
    destination, or the copy does not read so."""
    empty = sorted(ord(key) for key, value in built.character_map.items()
                   if value == '' and isinstance(key, str) and len(key) == 1)
    if not empty:
        return None
    try:
        data = resolved(font.get('/ToUnicode')).get_data()
        mark = UNMAPPED.encode('utf-16-be').hex().upper()
        entries = [f'<{code:04X}> <{mark}>' for code in empty]
        added = ''.join(f'\n{len(block)} beginbfchar\n' + '\n'.join(block) + '\nendbfchar'
                        for block in (entries[start:start + 100] for start in range(0, len(entries), 100)))
        stream = DecodedStreamObject()
        stream.set_data(data + added.encode('ascii') + b'\n')
        copy = DictionaryObject({NameObject(key): font.raw_get(key) for key in font})
        copy[NameObject('/ToUnicode')] = stream
        marked = Font.from_font_resource(copy).character_map
        return copy if all(marked.get(chr(code)) == UNMAPPED for code in empty) else None
    except (MemoryError, RecursionError):
        raise
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


_PAD = re.compile(BOX_PAD)
PAD_CHARS = frozenset(chr(code) for code in range(0x3001) if _PAD.fullmatch(chr(code)))  # BOX_PAD's characters


def not_valid_text(char: str) -> bool:
    """Whether ``char`` is text that is not valid: U+FFFD (a ToUnicode writer's 'no character', pypdf's replacement)
    or a lone surrogate (shown as U+FFFD). It is kept and named, but alone in a typed box it is no box state."""
    return char == '\ufffd' or '\ud800' <= char <= '\udfff'


class BoxGuard:
    """The box contract's guard, read item by item in order: a typed box whose only content is unread glyphs (ones
    that name no character, or text that is not valid) and padding is found ('[' or '(' and padding, the unread
    glyphs, padding and ']' or ')', on one line), so that its reader writes it as its brackets round exactly '?'.
    Dropped, a glyph that names no character would leave '[]' or '( )', which routing reads as an unchecked box,
    '[\ufffd]' reads as a mark that checks it, and routing does not hold '[? ]'; written so, the box is the contract's
    unread mark ('[?]'), held. Only the open box's first unread glyph is kept (its token), so reading a page of any
    length holds one position at a time."""
    __slots__ = ('opener', 'pending')

    def __init__(self):
        self.opener = False  # the last character that is not padding opened a box
        self.pending = None  # the token of the open box's first unread glyph

    def unread(self, token) -> bool:
        """An unread glyph at ``token``: whether it is the first in an open box (its token is then pending)."""
        if self.opener and self.pending is None:
            self.pending = token
            return True
        return False

    def text(self, item: str):
        """Text that is read: the pending token when ``item`` closes the box that glyph stands alone in, else None."""
        closed = None
        for char in item:
            if char in PAD_CHARS:
                continue
            if char in '])' and self.opener and self.pending is not None:
                closed = self.pending
            self.opener, self.pending = char in '[(', None
        return closed


def unread_in_boxes(items) -> set[int]:
    """The index of the first glyph that names no character (an item None) alone in each typed box (BoxGuard).
    ``items``: in order, each glyph's text, or None for a glyph that names no character."""
    marks, guard = set(), BoxGuard()
    for index, item in enumerate(items):
        if item is None:
            guard.unread(index)
            continue
        closed = guard.text(item)
        if closed is not None:
            marks.add(closed)
    return marks


# --- the font extraction reads in place of text it cannot read ------------------------------------------------------

UNREAD_TEXT = '\ufdd7'  # what pypdf extracts where the page reader drew text it cannot read as the PDF encodes it
UNREAD_FONT = '/CptStudioUnreadText'  # the resource name the page reader gives unread_font
_UNREAD_CODE, _UNREAD_BITS = 0x41, 20  # code 0x41 + k draws UNREAD_TEXT and is 2 ** k glyph-space units wide


def unread_font() -> DictionaryObject:
    """The font the page reader draws text in that pypdf cannot read as the PDF encodes it (an operator replaced by
    unread_codes in this font): every code draws UNREAD_TEXT, which the reader counts and drops, a mark alone in a
    typed box written as the unread mark. Its codes are powers of two wide, so a string of them measures what the
    operator it stands for measured, and pypdf spaces the text around it as before."""
    last = _UNREAD_CODE + _UNREAD_BITS - 1
    stream = DecodedStreamObject()
    stream.set_data(_to_unicode({code: UNREAD_TEXT for code in range(_UNREAD_CODE, last + 1)}).encode('ascii'))
    descriptor = DictionaryObject({NameObject('/Type'): NameObject('/FontDescriptor'),
                                   NameObject('/FontName'): NameObject('/CptStudioUnreadText'),
                                   NameObject('/Flags'): NumberObject(32), NameObject('/MissingWidth'): NumberObject(0),
                                   NameObject('/FontBBox'): ArrayObject([NumberObject(0)] * 4),
                                   NameObject('/ItalicAngle'): NumberObject(0), NameObject('/Ascent'): NumberObject(0),
                                   NameObject('/Descent'): NumberObject(0), NameObject('/CapHeight'): NumberObject(0),
                                   NameObject('/StemV'): NumberObject(0)})
    return DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/CptStudioUnreadText'),
                             NameObject('/FirstChar'): NumberObject(_UNREAD_CODE),
                             NameObject('/LastChar'): NumberObject(last),
                             NameObject('/Widths'): ArrayObject(NumberObject(1 << bit) for bit in range(_UNREAD_BITS)),
                             NameObject('/FontDescriptor'): descriptor, NameObject('/ToUnicode'): stream})


def unread_codes(width: float) -> bytes:
    """Codes of unread_font together ``width`` glyph-space units wide (rounded, within 1 and 2 ** 20 - 1)."""
    units = min(max(round(width), 1), (1 << _UNREAD_BITS) - 1) if math.isfinite(width) else 1
    return bytes(_UNREAD_CODE + bit for bit in range(_UNREAD_BITS) if units >> bit & 1)


class FontReadings:
    """How extraction reads each font of one document, worked out once per font dictionary and font program and
    shared by the walkers of all its pages and annotation appearances (pdfcontent.readings_for): the copy pypdf reads
    in its place and whether pypdf builds it (font_reading), how its strings are judged (decode_plan), its kind, and
    each Type 1 program's built-in encoding. A font whose inspection fails (pypdf's structure limits among the
    reasons: an object past one is never read, however often it is asked for) is unusable: its text is unread and
    named, never the reason the document fails. Each font is kept with its reading, so its id stays its own."""

    def __init__(self):
        self.programs: dict = {}  # id(font program) -> (program, its built-in encoding)
        self._readings: dict = {}  # id(font dict) -> (font dict, copy or None, usable)
        self._plans: dict = {}  # id(font dict) -> (font dict, decode plan)
        self._kinds: dict = {}  # id(font dict) -> (font dict, kind)
        self.unread = unread_font()

    def known(self, font) -> bool:
        """Whether ``font`` was read already."""
        known = self._readings.get(id(font))
        return known is not None and known[0] is font

    def reading(self, font, built: Font | None = None) -> tuple[DictionaryObject | None, bool]:
        """(the copy of ``font`` extraction reads in its place, or None; whether pypdf builds what it reads)."""
        known = self._readings.get(id(font))
        if known is None or known[0] is not font:
            try:
                copy, usable = font_reading(font, self.programs, built)
            except (MemoryError, RecursionError):
                raise
            except Exception:
                copy, usable = None, False
            known = self._readings[id(font)] = (font, copy, usable)
        return known[1], known[2]

    def plan(self, font) -> bool | str:
        """decode_plan of what extraction reads for ``font`` (False when pypdf builds nothing for it)."""
        known = self._plans.get(id(font))
        if known is None or known[0] is not font:
            copy, usable = self.reading(font)
            try:
                plan = decode_plan(copy if copy is not None else font) if usable else False
            except (MemoryError, RecursionError):
                raise
            except Exception:
                plan = False
            known = self._plans[id(font)] = (font, plan)
        return known[1]

    def kind(self, font) -> str:
        """kind(font), once per font ('text' for a font whose inspection fails: its glyphs are read as pypdf writes
        them, which the plan has judged)."""
        known = self._kinds.get(id(font))
        if known is None or known[0] is not font:
            try:
                value = kind(font)
            except (MemoryError, RecursionError):
                raise
            except Exception:
                value = 'text'
            known = self._kinds[id(font)] = (font, value)
        return known[1]


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
