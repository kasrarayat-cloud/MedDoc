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
- **Glyph names pypdf reads by its own rule** (``mapped_font``). pypdf 6.21.4
  reads a /Differences or built-in glyph name that is not in the Adobe Glyph
  List and starts with 'u' by int(name, 16): 'u20' as a space, 'uni0000' as
  NUL, 'uF00C' as a private-use character, and a name too long for a
  character fails the font. A text font holding such a name is replaced,
  for extraction only, by a copy whose ToUnicode gives each of those codes
  what the name stands for under the Adobe Glyph List specification ('uni'
  and groups of four upper-case hex digits, or 'u' and four to six), in the
  precedence PDF 32000-1 9.6.6 gives: the font's own ToUnicode, then
  /Differences, then the dictionary's named encoding, then the font
  program's built-in encoding. A name that stands for no character (another
  form, a control or private-use code, a noncharacter) is counted and
  dropped. Every other code reads exactly as pypdf reads it.
- **Fonts pypdf 6.21.4 no longer builds** (a /BaseEncoding that is not a
  name, /W entries that are not widths): the copy extraction reads leaves
  that entry out, as pypdf 6.21.2 ignored it, so the text is read and is not
  replaced by U+FFFD for every byte.
- **Text pypdf cannot read as the PDF encodes it** (``decodes``): a composite
  font whose CMap pypdf does not implement (it reads the bytes as UTF-16BE),
  or a string its CMap cannot decode (an odd byte count in a two-byte font).
  The page reader treats such text as unreadable rather than read pypdf's
  U+FFFD and mojibake as text.

Importable without Django (the extraction child imports it).
"""
from __future__ import annotations

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
    """A character no font maps a glyph to: a control code (other than tab and line ends), private use, or a
    noncharacter (U+FDD0-U+FDEF, and the last two code points of every plane, U+FFFF among them). NUL is left to
    canonicalisation, which removes it."""
    code = ord(char)
    return ((0 < code < 0x20 and char not in '\t\n\r') or 0x7F <= code <= 0x9F or 0xE000 <= code <= 0xF8FF
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


def mapped_font(font) -> DictionaryObject | None:
    """The copy of ``font`` that extraction reads in its place, or None when pypdf reads ``font`` itself as the
    PDF encodes it (or cannot read it at all: the page reader then treats its text as unreadable)."""
    return font_reading(font)[0]


def font_reading(font) -> tuple[DictionaryObject | None, bool]:
    """(the copy of ``font`` extraction reads in its place, or None; whether pypdf builds what extraction reads for
    it: the copy, or the font itself). A font pypdf cannot build is drawn by its extractor in a stand-in font that
    reads every byte as U+FFFD."""
    if not isinstance(font, DictionaryObject):
        return None, False
    subtype = resolved(font.get('/Subtype'))
    if subtype == '/Type0':
        return _composite_copy(font)
    if symbol_glyphs(font) is not None and subtype in SIMPLE_FONTS:
        copy = mapped_simple_font(font)
        return copy, copy is not None
    if subtype in SIMPLE_FONTS or subtype == '/Type3':
        return _text_font_copy(font)
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


def agl_text(name: str) -> str | None:
    """The characters the glyph ``name`` stands for under the Adobe Glyph List specification: a name the list holds,
    'uni' and groups of four upper-case hex digits each naming a character outside the surrogates, or 'u' and four
    to six naming one; None for any other name (other digit counts, lower case, '0x', '+', '_', a suffix)."""
    known = adobe_glyphs.get('/' + name)
    if known is not None:
        return known
    match = _AGL_UNI.fullmatch(name)
    if match:
        digits = match.group(1)
        values = [int(digits[start:start + 4], 16) for start in range(0, len(digits), 4)]
        return None if any(0xD800 <= value <= 0xDFFF for value in values) else ''.join(map(chr, values))
    match = _AGL_U.fullmatch(name)
    if match:
        value = int(match.group(1), 16)
        return None if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF else chr(value)
    return None


def pypdf_reads_by_number(name: str) -> bool:
    """Whether pypdf 6.21.4 reads the glyph ``name`` by its own number rule (a name outside the Adobe Glyph List that
    starts with 'u': int(rest, 16)), which pypdf 6.21.2 did not apply to /Differences, nor to 'u' names anywhere."""
    return name.startswith('u') and '/' + name not in adobe_glyphs


def _names_no_character(text: str) -> bool:
    return not text or any(char == '\x00' or undecodable(char) for char in text)


def builtin_encoding(font: DictionaryObject) -> dict[int, str]:
    """{code: glyph name} of the built-in encoding pypdf reads from a Type 1 font program (/FontFile) when the font
    has no ToUnicode: the 'dup <code> /<name> put' lines of its clear text after /Encoding, as pypdf parses them,
    without its failures (a name too long for a character, bytes that are not UTF-8, a code outside 0-255)."""
    if '/ToUnicode' in font or resolved(font.get('/Subtype')) != '/Type1':
        return {}
    descriptor = resolved(font.get('/FontDescriptor'))
    program = resolved(descriptor.get('/FontFile')) if isinstance(descriptor, DictionaryObject) else None
    if not isinstance(program, StreamObject):
        return {}
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


def _text_font_copy(font: DictionaryObject) -> tuple[DictionaryObject | None, bool]:
    """(a copy of a simple text font that pypdf reads as the PDF encodes it (see the module docstring), or None when
    pypdf reads the font itself so; whether pypdf builds what extraction reads), as font_reading."""
    names = differences(font)
    builtin = builtin_encoding(font)
    by_number = {code for code, name in names.items() if pypdf_reads_by_number(name)}
    by_number |= {code for code, name in builtin.items() if pypdf_reads_by_number(name)}
    original, base = buildable(font)
    if original is None:
        return None, False
    if not by_number:
        if base is font:
            return None, True
        if builtin and resolved(base.get('/FontDescriptor')) is not resolved(font.get('/FontDescriptor')):
            by_number = set(builtin)  # pypdf cannot read the program its codes come from: read them here
        else:
            return base, True
    has_to_unicode = '/ToUnicode' in font
    encoding = resolved(font.get('/Encoding'))
    named = encoding if isinstance(encoding, NameObject) else \
        resolved(encoding.get('/BaseEncoding')) if isinstance(encoding, DictionaryObject) else None
    table = charset_encoding.get(named) if isinstance(named, NameObject) else None
    pypdf_encoding = original.encoding if isinstance(original.encoding, dict) else {}
    # True when pypdf could not read the font program, so the built-in names are read here as pypdf reads them.
    lost = resolved(base.get('/FontDescriptor')) is not resolved(font.get('/FontDescriptor'))

    def read(code: int) -> str:
        if code not in by_number:
            # as pypdf reads it: its encoding, then its character map, character by character
            text = ''.join(original.character_map.get(char, char) for char in pypdf_encoding.get(code, chr(code)))
            return text or UNMAPPED
        own = original.character_map.get(chr(code)) if has_to_unicode else None
        if own:
            return own
        difference, inbuilt = names.get(code), builtin.get(code)
        if difference is not None and (pypdf_reads_by_number(difference) or not lost or inbuilt is None):
            text = agl_text(difference)  # /Differences decides (PDF 32000-1 9.6.6.1)
        elif inbuilt is not None and pypdf_reads_by_number(inbuilt) and table is not None:
            text = table[code]  # the dictionary's named encoding decides over the program's built-in one
        elif inbuilt is not None:
            text = agl_text(inbuilt)  # the built-in encoding, where it decides (or pypdf would have read it)
        else:
            text = table[code] if table is not None else None
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


def _composite_copy(font: DictionaryObject) -> tuple[DictionaryObject | None, bool]:
    """A copy of a composite font whose descendant's /W keeps only width entries, when pypdf 6.21.4 cannot build the
    font itself because of the others (a string or a name where a width list belongs: pypdf 6.21.2 kept them as
    widths of codes the text rarely uses); None when pypdf builds the font, or cannot build the copy either; as
    font_reading."""
    try:
        Font.from_font_resource(font)
        return None, True
    except (MemoryError, RecursionError):
        raise
    except Exception:
        pass
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
    """The codec pypdf decodes a composite font's strings with when it implements the font's CMap: its predefined
    table, or a UCS-2 CMap; None for any other (another predefined CMap, an embedded CMap stream, a dictionary or no
    /Encoding), whose bytes pypdf reads as UTF-16BE, which is not what they encode."""
    encoding = resolved(font.get('/Encoding'))
    if not isinstance(encoding, NameObject):
        return None
    if encoding in _predefined_cmap:
        return _predefined_cmap[encoding]
    return 'utf-16-be' if '-UCS2-' in encoding else None


def decodes(font, string: bytes) -> bool:
    """Whether pypdf reads ``string`` shown in ``font`` (a font dictionary) as the font encodes it. A simple font maps
    each byte through a code table, unless its /Encoding names a CMap. A glyph-index font's codes are dropped by the
    page reader, so whatever pypdf makes of them is not read. Any other composite font needs a CMap pypdf implements
    under which the whole string decodes: pypdf 6.21.2 refused a string that does not (or wrote lone surrogates),
    and 6.21.4 writes U+FFFD and mojibake."""
    if not string:
        return True
    encoding = resolved(font.get('/Encoding'))
    if resolved(font.get('/Subtype')) != '/Type0':
        return not (isinstance(encoding, str) and encoding not in charset_encoding
                    and (encoding in _predefined_cmap or '-UCS2-' in encoding))
    if kind(font) == 'glyph-index':
        return True
    codec = composite_codec(font)
    if codec is None:
        return False
    try:
        string.decode(codec, 'surrogatepass')
    except UnicodeDecodeError:
        return False
    return True


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


def unread_in_boxes(items) -> set[int]:
    """The index of the first glyph that names no character (an item None) alone in each typed box: '[' or '(' and
    padding before it, padding or more such glyphs and ']' or ')' after it, on one line. Dropped, it would leave '[]'
    or '( )', which routing reads as an unchecked box; written as '?' there, the box is the contract's unread mark
    ('[?]'), held. ``items``: in order, each glyph's text, or None for a glyph that names no character."""
    marks, opener, first = set(), False, None
    for index, item in enumerate(items):
        if item is None:
            if opener and first is None:
                first = index
            continue
        for char in item:
            if _PAD.fullmatch(char):
                continue
            if char in '])' and opener and first is not None:
                marks.add(first)
            opener, first = char in '[(', None
    return marks


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
