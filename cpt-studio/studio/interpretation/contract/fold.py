"""The fold tier of quote location (docs/gemini-migration/FINAL-V2.md 3.1 I2, 5.0, 5.6; step 1c of 8.1): ``fold`` and
``fold_char``, copied from v1's studio/interpretation/lexicon.py (5.2: ``lexicon.py:fold_char`` 43-58 and ``fold``
61-63) with identical behaviour, so that the new path executes no v1 code (5.7) while contract/geometry.py locates a
source's words exactly as v1's binding did when the exact tier fails. tests/v2/test_fold.py proves both equal to v1's:
``fold_char`` on every code point, ``fold`` on v1's own fixtures and on random texts, the comparison computed in the
test.

**A source-integrity copy, not a reader** (5.0, 5.6): it folds characters - Unicode NFKC, case folding, a hyphen or dash
as a space, a curly quote straight, whitespace as a space, a soft hyphen removed - so that WHERE a quote is can be found
when the document and the quote differ only in those characters. It never decides what a quote means, and nothing in
it names a word.

The one change from v1 is how the character classes are held: v1 keeps them as module-level frozensets of characters;
here each is the plain string of its characters, so that no module-level set of strings exists in contract/ (NoWordLists,
5.7 measure 4). ``fold_char`` tests one character at a time against them, so the membership is v1's exactly.
"""
from __future__ import annotations

import unicodedata

DASHES = '-‐‑‒–—―−﹘﹣－'  # v1's lexicon.DASHES, as one string
SOFT_HYPHEN = '­'  # invisible: removed, never a space
SINGLE_QUOTES = '‘’‚‛′'  # v1's lexicon.SINGLE_QUOTES, as one string
DOUBLE_QUOTES = '“”„‟″'  # v1's lexicon.DOUBLE_QUOTES, as one string


def fold_char(char: str) -> str:
    """One character as the fold tier reads it (v1's FINAL C2): NFKC, case folded, a hyphen or dash as a space, a curly
    quote straight, whitespace as a space. It may give no character (a soft hyphen) or several (NFKC's "fi"). v1's
    lexicon.fold_char, unchanged in behaviour: each piece is one character, so testing it against the string of a
    class is testing it against the class."""
    out: list[str] = []
    for piece in unicodedata.normalize('NFKC', char).casefold():
        if piece == SOFT_HYPHEN:
            continue
        if piece in DASHES or piece.isspace():
            out.append(' ')
        elif piece in SINGLE_QUOTES:
            out.append("'")
        elif piece in DOUBLE_QUOTES:
            out.append('"')
        else:
            out.append(piece)
    return ''.join(out)


def fold(text: str) -> str:
    """``text`` as the fold tier reads it: each character folded (fold_char), whitespace runs collapsed, stripped. v1's
    lexicon.fold, unchanged."""
    return ' '.join(''.join(fold_char(char) for char in text).split())
