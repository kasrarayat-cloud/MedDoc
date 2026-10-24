"""Symbol-font glyph tables shared by DOCX and PDF extraction (ARCHITECTURE 5.1).

A symbol font (Symbol, Wingdings, Zapf Dingbats, ...) draws pictures where
its character codes would be letters, so its text is mapped code by code to
the Unicode character each glyph shows; a code with no known character is
counted by the caller, never shown as the letter that encodes it.

Check boxes follow the contract shared with routing: every recognised
unchecked box is written as ☐ (U+2610) and every checked box as ☒ (U+2612),
whatever box shape the font draws (□ ◻ ❏ ❑ ...; ☑ ⌧ ...). A filled square
(■) is a bullet as often as a box, so it is kept as it is.

Importable without Django (the extraction child imports it).
"""
from __future__ import annotations

import re

UNCHECKED_BOX = '☐'  # ☐
CHECKED_BOX = '☒'  # ☒

# Every Unicode box shape a symbol font's glyph may stand for, as the contract's two boxes. The white squares of
# every weight (U+1F78E-U+1F793) are what Unicode 7 names Wingdings 0xA8, 0x6F and 0x70 and Wingdings 2
# 0xA4-0xA6, as converters write them in a ToUnicode map.
_BOX_SHAPES = dict.fromkeys('☐□▢◻◽⬜❏❐❑❒\U0001f78e\U0001f78f\U0001f790\U0001f791\U0001f792\U0001f793',
                            UNCHECKED_BOX)
_BOX_SHAPES |= dict.fromkeys('☒☑⌧⮽\U0001f5f5\U0001f5f7\U0001f5f9', CHECKED_BOX)


def as_box(glyph: str) -> str:
    """``glyph`` as ☐ / ☒ when it is a box shape, else unchanged."""
    return _BOX_SHAPES.get(glyph, glyph)


class GlyphTable(dict):
    """A symbol font's glyphs, {code: character}. ``latin`` says whether some of its glyphs are Latin-1 characters
    of their own (Symbol's punctuation, digits and ±): only in a font without them is a Latin-1 character that a
    ToUnicode map gives certainly an echo of the glyph's code."""

    def __init__(self, entries=()):
        super().__init__(entries)
        self.latin = any(len(char) == 1 and ord(char) <= 0xFF for char in self.values())


def _adobe_table(module: str, name: str, *, latin: bool = True) -> GlyphTable:
    """pypdf's Adobe Symbol / Zapf Dingbats encodings, keeping only real characters. pypdf fills the codes Zapf
    Dingbats leaves undefined (0xF0, 0xFF) with their Latin-1 characters, which no Zapf glyph is: ``latin=False``
    drops them, so such a code is counted like any other glyph without a character."""
    try:
        table = getattr(__import__(f'pypdf._codecs.{module}', fromlist=[name]), name)
    except (ImportError, AttributeError):  # count the glyphs instead of mapping them
        return GlyphTable()
    return GlyphTable((code, as_box(char)) for code, char in enumerate(table)
                      if char.strip() and char.isprintable() and not 0xE000 <= ord(char) <= 0xF8FF
                      and (latin or ord(char) > 0xFF))


# Wingdings: its check boxes and check marks, and the bullets Word's bullet library draws with it. Every box
# shape of Wingdings, Wingdings 2 and Webdings is listed (the white squares of each weight, the shadowed squares
# and the ballot boxes; Unicode's own mapping of the fonts, as mammoth's dingbat table gives it).
_WINGDINGS = GlyphTable({0x6C: '●', 0x6E: '■', 0x6F: UNCHECKED_BOX, 0x70: UNCHECKED_BOX, 0x71: UNCHECKED_BOX,
                         0x72: UNCHECKED_BOX, 0x76: '❖', 0x78: CHECKED_BOX, 0xA7: '▪', 0xA8: UNCHECKED_BOX,
                         0xD8: '➢', 0xFB: '✗', 0xFC: '✓', 0xFD: CHECKED_BOX, 0xFE: CHECKED_BOX})
_WINGDINGS_2 = GlyphTable({0x51: CHECKED_BOX, 0x52: CHECKED_BOX, 0x53: CHECKED_BOX, 0x54: CHECKED_BOX,
                           0xA3: UNCHECKED_BOX, 0xA4: UNCHECKED_BOX, 0xA5: UNCHECKED_BOX, 0xA6: UNCHECKED_BOX})
_WEBDINGS = GlyphTable({0x63: UNCHECKED_BOX})
SYMBOL_FONTS = {
    'symbol': _adobe_table('symbol', '_symbol_encoding'),
    'zapfdingbats': _adobe_table('zapfding', '_zapfding_encoding', latin=False),
    'itczapfdingbats': _adobe_table('zapfding', '_zapfding_encoding', latin=False),
    'wingdings': _WINGDINGS,
    'wingdings2': _WINGDINGS_2,
    'webdings': _WEBDINGS,
    'wingdings3': GlyphTable(), 'marlett': GlyphTable(), 'mtextra': GlyphTable(), 'msoutlook': GlyphTable(),
    'bookshelfsymbol7': GlyphTable(), 'msreferencespecialty': GlyphTable(), 'mtsymbol': GlyphTable(),
}
_FONT_NAME = re.compile(r'[\s_-]+')


def symbol_table(font: str | None) -> dict[int, str] | None:
    """The glyph table of a symbol font (possibly empty: count every glyph), or None for a text font."""
    return SYMBOL_FONTS.get(_FONT_NAME.sub('', font).lower()) if font else None
