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

# Every Unicode box shape a symbol font's glyph may stand for, as the contract's two boxes.
_BOX_SHAPES = dict.fromkeys('☐□▢◻◽⬜❏❐❑❒\U0001f790', UNCHECKED_BOX)
_BOX_SHAPES |= dict.fromkeys('☒☑⌧⮽\U0001f5f5\U0001f5f7\U0001f5f9', CHECKED_BOX)


def as_box(glyph: str) -> str:
    """``glyph`` as ☐ / ☒ when it is a box shape, else unchanged."""
    return _BOX_SHAPES.get(glyph, glyph)


def _adobe_table(module: str, name: str) -> dict[int, str]:
    """pypdf's Adobe Symbol / Zapf Dingbats encodings, keeping only real characters."""
    try:
        table = getattr(__import__(f'pypdf._codecs.{module}', fromlist=[name]), name)
    except (ImportError, AttributeError):  # count the glyphs instead of mapping them
        return {}
    return {code: as_box(char) for code, char in enumerate(table)
            if char.strip() and char.isprintable() and not 0xE000 <= ord(char) <= 0xF8FF}


# Wingdings: its check boxes and check marks, and the bullets Word's bullet library draws with it.
_WINGDINGS = {0x6C: '●', 0x6E: '■', 0x6F: UNCHECKED_BOX, 0x71: UNCHECKED_BOX, 0x72: UNCHECKED_BOX,
              0x76: '❖', 0x78: CHECKED_BOX, 0xA7: '▪', 0xA8: UNCHECKED_BOX, 0xD8: '➢',
              0xFB: '✗', 0xFC: '✓', 0xFD: CHECKED_BOX, 0xFE: CHECKED_BOX}
_WINGDINGS_2 = {0x52: CHECKED_BOX, 0x53: CHECKED_BOX, 0x54: CHECKED_BOX, 0xA3: UNCHECKED_BOX}
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
