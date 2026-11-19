"""contract/fold.py: v1's fold and fold_char, copied for the fold tier of quote location (docs/gemini-migration/FINAL-V2.md
3.1 I2, 5.0, 5.2, 5.6; step 1c of 8.1). TEXT-ONLY and SYNTHETIC: no network, no provider, no document of the acceptance
set.

What is proved here (8.1 step 1c: "fold and fold_char copied from v1 with identical behaviour (a test compares with v1's
on v1's fixtures, computed in the test)"):
- ``fold_char`` equals v1's lexicon.fold_char on every code point, and on random strings of several characters;
- ``fold`` equals v1's lexicon.fold on v1's own fixtures - every string of v1's lexicon tests
  (tests/test_interpretation_lexicon.py) and every phrase of v1's lexicon tables, harvested here - and on random texts,
  with the expected values of v1's own folding test kept;
- the character classes are v1's sets, held as strings so that no module-level set of strings exists (NoWordLists,
  5.7 measure 4, with a planted control), and the module imports only unicodedata.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import MappingProxyType

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio.interpretation import lexicon as v1_lexicon
from studio.interpretation.contract import fold
from tests.v2.test_geometry import no_word_lists

APP = Path(__file__).resolve().parents[2]
FOLD = APP / 'studio' / 'interpretation' / 'contract' / 'fold.py'
V1_LEXICON_TESTS = APP / 'tests' / 'test_interpretation_lexicon.py'


def strings_in(value: object, found: set) -> None:
    """Every str held in ``value``, at any depth of tuples, lists, sets, dicts and mapping proxies."""
    if isinstance(value, str):
        found.add(value)
    elif isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            strings_in(item, found)
    elif isinstance(value, (dict, MappingProxyType)):
        for key, item in value.items():
            strings_in(key, found)
            strings_in(item, found)


def v1_fixtures() -> list:
    """v1's own fixtures for folding: every string constant of v1's lexicon tests, and every string of v1's lexicon
    tables (its module-level values), in a stable order."""
    found: set = set()
    for node in ast.walk(ast.parse(V1_LEXICON_TESTS.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(node.value)
    for name, value in vars(v1_lexicon).items():
        if not name.startswith('__'):
            strings_in(value, found)
    return sorted(found)


class FoldCharTests(SimpleTestCase):
    def test_equal_to_v1s_on_every_code_point(self):
        differing = [hex(point) for point in range(sys.maxunicode + 1)
                     if fold.fold_char(chr(point)) != v1_lexicon.fold_char(chr(point))]
        self.assertEqual(differing, [])

    @hypothesis.settings(max_examples=300, deadline=None, database=None)
    @hypothesis.given(st.text(max_size=6))
    def test_equal_to_v1s_on_several_characters(self, text):
        self.assertEqual(fold.fold_char(text), v1_lexicon.fold_char(text))

    def test_the_character_classes_are_v1s(self):
        self.assertEqual(set(fold.DASHES), set(v1_lexicon.DASHES))
        self.assertEqual(len(fold.DASHES), len(v1_lexicon.DASHES))
        self.assertEqual(set(fold.SINGLE_QUOTES), set(v1_lexicon.SINGLE_QUOTES))
        self.assertEqual(set(fold.DOUBLE_QUOTES), set(v1_lexicon.DOUBLE_QUOTES))
        self.assertEqual(fold.SOFT_HYPHEN, v1_lexicon.SOFT_HYPHEN)


class FoldTests(SimpleTestCase):
    def test_equal_to_v1s_on_v1s_fixtures(self):
        fixtures = v1_fixtures()
        self.assertGreater(len(fixtures), 500, 'the harvest reads v1 tests and tables')
        differing = [text for text in fixtures if fold.fold(text) != v1_lexicon.fold(text)]
        self.assertEqual(differing, [])

    def test_v1s_own_expected_values(self):
        # tests/test_interpretation_lexicon.py, test_fold_is_the_normalized_tier
        for text, expected in (('  Cold‑Snare\n\tPOLYPECTOMY ', 'cold snare polypectomy'),
                               ('“No” ‘further’', '"no" \'further\''),
                               ('inter­val', 'interval'), ('ﬁne needle', 'fine needle'),
                               ('Straße', 'strasse'), ('A—B–C-D−E', 'a b c d e')):
            with self.subTest(text):
                self.assertEqual(fold.fold(text), expected)
                self.assertEqual(fold.fold(text), v1_lexicon.fold(text))

    @hypothesis.settings(max_examples=400, deadline=None, database=None)
    @hypothesis.given(st.text(max_size=40))
    def test_equal_to_v1s_on_random_texts(self, text):
        self.assertEqual(fold.fold(text), v1_lexicon.fold(text))

    @hypothesis.settings(max_examples=300, deadline=None, database=None)
    @hypothesis.given(st.text(alphabet=st.sampled_from(list('aA \t\n-‐—−­‘’“”'
                                                            '′″ﬁßİ 　﹘')),
                              max_size=30))
    def test_equal_to_v1s_on_the_folded_classes(self, text):
        self.assertEqual(fold.fold(text), v1_lexicon.fold(text))


class GuardTests(SimpleTestCase):
    def test_no_word_lists(self):
        self.assertEqual(no_word_lists(FOLD.read_text(encoding='utf-8')), [])
        self.assertTrue(no_word_lists("DASHES = frozenset('-‐‑')\n"), "v1's form is refused")
        self.assertTrue(no_word_lists("QUOTES = ('‘', '’')\n"))

    def test_the_imports(self):
        tree = ast.parse(FOLD.read_text(encoding='utf-8'))
        imported = sorted({alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                           for alias in node.names}
                          | {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)})
        self.assertEqual(imported, ['__future__', 'unicodedata'])
