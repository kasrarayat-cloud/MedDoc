"""The decision engine of design v2 (docs/gemini-migration/FINAL-V2.md section 4; cpt-studio-events@2): v1's coding
rules, forked and rewired to read a typed, text-free FactSet of settled facts - enumeration members, ids, results and
integer spans - and never document text, which reaches a decision only through wording.quote(span), after it.

Its modules, by the step of 8.1 that owns each: types (0b); anatomy and catalogue (1e); requirements_table and
requirements (1f); facts, reading and derive (2d); pairing (3d); evaluate and questions (4a); coverage (4b); classes
(4c); combination (4d); assess and measure (5a).

The static rules of FINAL-V2 5.7 measure 4 hold over every module here: no import of re, regex, unicodedata, difflib,
fnmatch, lexicon, literals, a retired v1 module or contract's text modules (segment, geometry, fold, date_literals); no
attribute or subscript named text, words, quote or unit_text; no word, phrase, marker or frame list. mypy --strict
fences types, facts and reading (measure 5).

This module holds no code and imports nothing, so importing the package loads nothing else.
"""
