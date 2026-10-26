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


# --- The check-box vocabulary, defined once (ARCHITECTURE 5.1 and 5.3) -------------------------------------------
# Every reader of typed or extracted boxes builds its patterns from these strings: routing's box and unread-mark
# readers (studio.gi.detect _BOX, _BOX_UNREAD, _BOX_TEXT), the section reader's option-row guard
# (studio.gi.sections _OPTION_ROW) and the PDF reader's printed boxes (studio.ingest.pdf PRINTED_BOX). They are
# regular-expression sources, compiled by each reader.
BOX_UNREAD_MARK = '[?]'  # the unread mark: extraction writes it where a box's state or place cannot be read
BOX_PAD = r'[ \t\u00a0\u2000-\u200a\u202f\u205f\u3000]'  # a box's padding: any whitespace but a line break
# The bare glyphs read as an unchecked and as a checked box: the unchecked box glyphs routing has always read (U+2610
# U+25A1 U+25FB U+25FD U+274F U+2750 U+2751 U+2752), and every checked box shape above with the check marks and the
# filled square typed as boxes (as_box keeps U+25A0 as it is: a symbol font draws it as a bullet as often as a box).
# The other unchecked shapes above (U+25A2, U+2B1C, the white squares of every weight) are a bullet as often as a box
# when typed, so read as unread marks that hold their item, never as a box that excludes it (BOX_UNREAD_PATTERN); a
# check-box widget over one still replaces it with its own state (BOX_PRINTED_PATTERN).
BOX_OFF_GLYPHS = '\u2610\u25a1\u25fb\u25fd\u274f\u2750\u2751\u2752'
BOX_HELD_GLYPHS = ''.join(glyph for glyph, box in _BOX_SHAPES.items()
                          if box == UNCHECKED_BOX and glyph not in BOX_OFF_GLYPHS)
BOX_ON_GLYPHS = ''.join(glyph for glyph, box in _BOX_SHAPES.items() if box == CHECKED_BOX) + '\u2713\u2714\u25a0'
# Unchecked: a box glyph, "[ ]" with any inner whitespace (or none), "[_]", "( )" with some inner whitespace.
BOX_OFF_PATTERN = '[' + BOX_OFF_GLYPHS + r']|\[' + BOX_PAD + r'*\]|\[_\]|\(' + BOX_PAD + r'+\)'
# Checked: a box glyph, "[x]" and "(x)" with optional inner whitespace, "[\u2713]", "[*]", "[v]".
BOX_ON_PATTERN = ('[' + BOX_ON_GLYPHS + r']|\[' + BOX_PAD + r'*[xX\u2713\u2714]' + BOX_PAD + r'*\]|\(' + BOX_PAD
                  + r'*[xX]' + BOX_PAD + r'*\)|\[[*v]\]')
# A mark in brackets that looks like a box but is none of the contract's: the item it marks is held, never passed
# over. Square brackets or parentheses round one radio, check, cross or query mark ("(\u2022)", "(\u25cf)",
# "[\u221a]", "(\u2713)", "[?]", "(*)", "(o)", "[/]"); square brackets round one dash, plus, underscore or answer
# letter ("[-]", "[+]", "[N]", "[Y]", "[V]"; "[_]" and "[v]" alone are boxes); braces or angle brackets round only
# spaces or one such mark ("{ }", "{x}", "< >", "<x>"); and a bare unchecked shape outside routing's box glyphs
# (BOX_HELD_GLYPHS). An answer in parentheses ("(N)", "(-)") is ordinary text
# ("H. pylori (-)") unless its line marks options in boxes (BOX_PAREN_ANSWER_PATTERN, read by routing).
_BOX_UNREAD_CHARS = r'[\u2022\u25cf\u25cb\u25ef\u25c9\u25ce\u29bf\u2713\u2714\u221a\u2717\u2718\u2715\u2716?*o/\\]'
_BOX_ANSWER_CHARS = r'[-+_NYnyVv]'
_BOX_ANY_CHAR = r'(?:' + _BOX_UNREAD_CHARS + '|' + _BOX_ANSWER_CHARS + r'|[xX])'
BOX_UNREAD_PATTERN = (r'[\[(]' + BOX_PAD + '*' + _BOX_UNREAD_CHARS + BOX_PAD + r'*[\])]|\[' + BOX_PAD + '*'
                      + _BOX_ANSWER_CHARS + BOX_PAD + r'*\]|\{' + BOX_PAD + '*' + _BOX_ANY_CHAR + '?' + BOX_PAD
                      + r'*\}|<' + BOX_PAD + '*' + _BOX_ANY_CHAR + '?' + BOX_PAD + '*>|[' + BOX_HELD_GLYPHS + ']')
# Radio glyphs written bare ("\u25cb Biopsy \u25cf Cold snare polypectomy", "\u25cb Yes \u25cf No"): a bullet as often
# as a box, so read as unread marks only where their line holds another one (routing), or before an option word (the
# option-row guard).
BOX_RADIO_PATTERN = r'[\u25cb\u25cf\u25c9\u25ef\u25ce\u29bf]'
# Crosses written bare (U+2717, U+2718, U+2715, U+2716): a mark that says yes as often as no, read as unread where a
# mark must be checked to count (routing's separately identifiable E/M statement).
BOX_CROSS_PATTERN = r'[\u2717\u2718\u2715\u2716]'
# An answer in parentheses ("(N)", "(Y)", "(-)", "(+)"), read as an unread mark only on a line that marks options in
# boxes or unread marks ("( ) Biopsy (Y) Cold snare polypectomy"; never "Biopsy for H. pylori (-)").
BOX_PAREN_ANSWER_PATTERN = r'\(' + BOX_PAD + '*[-+NYny]' + BOX_PAD + r'*\)'
# A printed box in a PDF page's text that a check-box widget over it replaces with its own state (pdf._placed_boxes):
# every unchecked spelling, and the contract's two checked ones (U+2612, "[x]"). A printed checked mark of another
# spelling stays as printed, so a widget never newly writes an unchecked box over a mark a viewer may show checked.
BOX_PRINTED_PATTERN = ('(?P<off>' + BOX_OFF_PATTERN + '|[' + BOX_HELD_GLYPHS + '])|(?P<on>' + CHECKED_BOX
                       + r'|\[[xX]\])')


# The built-in encodings of the two Adobe symbol fonts: glyph names in code order from each run's first code
# (Adobe's ZapfDingbats.afm and Symbol.afm). A PDF font's /Differences re-encodes codes by glyph name, so
# a code re-encoded to one of these names shows the glyph that name has in the built-in encoding.
_ZAPF_RUNS = {
    0x20: (
        'space a1 a2 a202 a3 a4 a5 a119 a118 a117 a11 a12 a13 a14 a15 a16 a105 a17 a18 a19 a20 a21 a22 '
        'a23 a24 a25 a26 a27 a28 a6 a7 a8 a9 a10 a29 a30 a31 a32 a33 a34 a35 a36 a37 a38 a39 a40 a41 a42 '
        'a43 a44 a45 a46 a47 a48 a49 a50 a51 a52 a53 a54 a55 a56 a57 a58 a59 a60 a61 a62 a63 a64 a65 a66 '
        'a67 a68 a69 a70 a71 a72 a73 a74 a203 a75 a204 a76 a77 a78 a79 a81 a82 a83 a84 a97 a98 a99 a100'),
    0x80: (
        'a89 a90 a93 a94 a91 a92 a205 a85 a206 a86 a87 a88 a95 a96'),
    0xA1: (
        'a101 a102 a103 a104 a106 a107 a108 a112 a111 a110 a109 a120 a121 a122 a123 a124 a125 a126 a127 '
        'a128 a129 a130 a131 a132 a133 a134 a135 a136 a137 a138 a139 a140 a141 a142 a143 a144 a145 a146 '
        'a147 a148 a149 a150 a151 a152 a153 a154 a155 a156 a157 a158 a159 a160 a161 a163 a164 a196 a165 '
        'a192 a166 a167 a168 a169 a170 a171 a172 a173 a162 a174 a175 a176 a177 a178 a179 a193 a180 a199 '
        'a181 a200 a182'),
    0xF1: (
        'a201 a183 a184 a197 a185 a194 a198 a186 a195 a187 a188 a189 a190 a191'),
}
_SYMBOL_RUNS = {
    0x20: (
        'space exclam universal numbersign existential percent ampersand suchthat parenleft parenright '
        'asteriskmath plus comma minus period slash zero one two three four five six seven eight nine '
        'colon semicolon less equal greater question congruent Alpha Beta Chi Delta Epsilon Phi Gamma Eta '
        'Iota theta1 Kappa Lambda Mu Nu Omicron Pi Theta Rho Sigma Tau Upsilon sigma1 Omega Xi Psi Zeta '
        'bracketleft therefore bracketright perpendicular underscore radicalex alpha beta chi delta '
        'epsilon phi gamma eta iota phi1 kappa lambda mu nu omicron pi theta rho sigma tau upsilon omega1 '
        'omega xi psi zeta braceleft bar braceright similar'),
    0xA0: (
        'Euro Upsilon1 minute lessequal fraction infinity florin club diamond heart spade arrowboth '
        'arrowleft arrowup arrowright arrowdown degree plusminus second greaterequal multiply '
        'proportional partialdiff bullet divide notequal equivalence approxequal ellipsis arrowvertex '
        'arrowhorizex carriagereturn aleph Ifraktur Rfraktur weierstrass circlemultiply circleplus '
        'emptyset intersection union propersuperset reflexsuperset notsubset propersubset reflexsubset '
        'element notelement angle gradient registerserif copyrightserif trademarkserif product radical '
        'dotmath logicalnot logicaland logicalor arrowdblboth arrowdblleft arrowdblup arrowdblright '
        'arrowdbldown lozenge angleleft registersans copyrightsans trademarksans summation parenlefttp '
        'parenleftex parenleftbt bracketlefttp bracketleftex bracketleftbt bracelefttp braceleftmid '
        'braceleftbt braceex'),
    0xF1: (
        'angleright integral integraltp integralex integralbt parenrighttp parenrightex parenrightbt '
        'bracketrighttp bracketrightex bracketrightbt bracerighttp bracerightmid bracerightbt'),
}


def _codes(runs: dict[int, str]) -> dict[str, int]:
    return {name: start + offset for start, names in runs.items() for offset, name in enumerate(names.split())}


class GlyphTable(dict):
    """A symbol font's glyphs, {code: character}. ``latin`` says whether some of its glyphs are Latin-1 characters
    of their own (Symbol's punctuation, digits and ±): only in a font without them is a Latin-1 character that a
    ToUnicode map gives certainly an echo of the glyph's code. ``names`` maps the glyph names of the font's
    built-in encoding to their codes (empty where they are not known: the TrueType symbol fonts)."""

    def __init__(self, entries=(), names: dict[str, int] | None = None):
        super().__init__(entries)
        self.latin = any(len(char) == 1 and ord(char) <= 0xFF for char in self.values())
        self.names = names or {}


def _adobe_table(module: str, name: str, runs: dict[int, str], *, latin: bool = True) -> GlyphTable:
    """pypdf's Adobe Symbol / Zapf Dingbats encodings, keeping only real characters. pypdf fills the codes Zapf
    Dingbats leaves undefined (0xF0, 0xFF) with their Latin-1 characters, which no Zapf glyph is: ``latin=False``
    drops them, so such a code is counted like any other glyph without a character."""
    try:
        table = getattr(__import__(f'pypdf._codecs.{module}', fromlist=[name]), name)
    except (ImportError, AttributeError):  # count the glyphs instead of mapping them
        return GlyphTable()
    return GlyphTable(((code, as_box(char)) for code, char in enumerate(table)
                       if char.strip() and char.isprintable() and not 0xE000 <= ord(char) <= 0xF8FF
                       and (latin or ord(char) > 0xFF)), _codes(runs))


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
    'symbol': _adobe_table('symbol', '_symbol_encoding', _SYMBOL_RUNS),
    'zapfdingbats': _adobe_table('zapfding', '_zapfding_encoding', _ZAPF_RUNS, latin=False),
    'itczapfdingbats': _adobe_table('zapfding', '_zapfding_encoding', _ZAPF_RUNS, latin=False),
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
