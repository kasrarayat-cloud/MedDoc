"""contract/date_literals.py: v1's eight date functions copied for L1 (docs/gemini-migration/FINAL-V2.md 3.1 L1, 5.0, 5.2,
5.6, 5.7 measure 4; step 1c of 8.1). TEXT-ONLY and SYNTHETIC: no network, no provider, no document of the acceptance set.

**The pin 5.7 names** (PinTests): the one module-level string collection in contract/ that NoWordLists cannot admit -
the month and weekday tables the parsers need - is closed by pinning instead of exempting. ``pin_findings`` compares
the module's WHOLE top level, every statement but its docstring, with a pinned structure (arbiter triage 1c#6):
1. exactly its imports and its three precision names (HEADER, pinned here as source);
2. then v1's statements of studio/interpretation/literals.py named in V1_NAMES, in v1's order, each AST-equal to v1's:
   v1's named constants and patterns, its two tables (``_MONTHS``, ``_WEEKDAYS``), ``DateLiteral``, and the eight
   functions (``_year``, ``_month``, ``_full_value``, ``full_dates``, ``dates`` with its nested ``free``, ``compare``,
   ``stored_date``, ``iso_date``);
3. the two tables also equal their pinned sha256, and v1's equal the same shas, computed in the test.
Any other top-level statement fails, whatever builds it: so a timing frame list added under a date-literal name fails
it, whether written as a display, built by ``split`` or by concatenation, compiled as a regex alternation, or hidden in
a lambda, a new class or a new function (arbiter triage 1c#6's plants R6 and R7 among them). It is the ONE copy of
the pin: step 6a's tests/test_guard_static.py calls ``pin_findings`` rather than repeating it. Each assertion refuses a
planted control applied in memory, and a comment stays green.

**The parity** (ParityTests, 8.1 step 1c: "the date parsers equal v1's on v1's literal fixtures (by value, the comparison
run once in the test)"): every parser equals v1's by value on v1's literal fixtures - every string of v1's literal tests
(tests/test_interpretation_literals.py), harvested here and run through both modules in the test - and on random
date-shaped texts; the patterns, the precision names and DateLiteral are v1's.
"""
from __future__ import annotations

import ast
from datetime import date, timedelta
from pathlib import Path

import hypothesis
from django.test import SimpleTestCase
from hypothesis import strategies as st

from studio.interpretation import literals as v1_literals
from studio.interpretation.contract import date_literals, jsonschema

APP = Path(__file__).resolve().parents[2]
DATE_LITERALS = APP / 'studio' / 'interpretation' / 'contract' / 'date_literals.py'
V1_LITERALS = APP / 'studio' / 'interpretation' / 'literals.py'
V1_LITERAL_TESTS = APP / 'tests' / 'test_interpretation_literals.py'
EIGHT = ('_year', '_month', '_full_value', 'full_dates', 'dates', 'compare', 'stored_date', 'iso_date')
# sha256_of(list(table)), pinned: a changed table changes these (and must equal v1's, computed below)
TABLE_SHA256 = {'_MONTHS': '1cc3602edef2530762b19cb46784bdf9c69abec1f4924d06b623f1579432b730',
                '_WEEKDAYS': '618e7bc66a2152bf6d0ae33065b766f7ddb4b1ba3f482b4f5efb5766da0388b9'}
# What the copy adds above v1's lines: its imports, and the three precision names taken from types.Precision.
HEADER = '''\
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

from studio.interpretation.contract.types import Precision

DAY = Precision.DAY.value
MONTH = Precision.MONTH.value
YEAR = Precision.YEAR.value
'''
# v1's top-level statements the copy holds, in v1's order (literals.py 37-174): its named constants and patterns, the
# two tables, DateLiteral, the eight functions, and the stored-date patterns between compare and stored_date.
V1_NAMES = ('_FLAGS', '_MONTHS', '_WEEKDAYS', '_MONTH', '_WEEKDAY', '_FULL', 'FULL_DATE', 'MONTH_YEAR', '_UNITS_AFTER',
            'BARE_YEAR', 'DateLiteral', '_year', '_month', '_full_value', 'full_dates', 'dates', 'compare', '_STORED',
            'stored_date', 'iso_date')


def top_functions(tree: ast.Module) -> dict:
    return {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


V1_FUNCTIONS = top_functions(ast.parse(V1_LITERALS.read_text(encoding='utf-8')))


def bound_name(node: ast.stmt):
    """The one name a top-level statement binds - a def's or a class's name, or a single-name assignment's target -
    else None."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None


def pinned_structure() -> list:
    """The whole top level the module may hold below its docstring: HEADER's statements, then v1's statements named in
    V1_NAMES, in that order, read from studio/interpretation/literals.py (each name bound once there)."""
    v1 = [node for node in ast.parse(V1_LITERALS.read_text(encoding='utf-8')).body if bound_name(node) in V1_NAMES]
    assert [bound_name(node) for node in v1] == list(V1_NAMES), "v1's statements are found once each, in v1's order"
    return list(ast.parse(HEADER).body) + v1


def pin_findings(source: str) -> list:
    """Every way ``source`` breaks the pin of FINAL-V2 5.7 measure 4 for contract/date_literals.py (arbiter triage
    1c#6); [] when it holds. The ONE copy of the pin: step 6a's tests/test_guard_static.py calls this helper.

    The module's whole top level - every statement but a docstring in first place - is compared statement by statement
    with ``pinned_structure()``: a statement binding a pinned name must be AST-equal to the pinned one; any other
    statement is refused, whatever it holds; every pinned statement must be present, once, in the pinned order. The two
    tables must also equal their pinned sha256."""
    body = list(ast.parse(source).body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(
            body[0].value.value, str):
        body = body[1:]
    pinned = pinned_structure()
    expected = [ast.dump(node) for node in pinned]
    names = {bound_name(node): ast.dump(node) for node in pinned if bound_name(node) is not None}
    out = []
    unmatched = list(expected)
    for node in body:
        dump, name = ast.dump(node), bound_name(node)
        if dump in unmatched:
            unmatched.remove(dump)
        elif name in names and names[name] in unmatched:
            unmatched.remove(names[name])
            out.append(f'{name} is not AST-equal to v1\'s' if name in V1_NAMES else f'{name} is not the pinned header\'s')
        else:
            out.append(f'a top-level statement the pin does not hold at line {node.lineno}'
                       + (f' (it binds {name})' if name else f' ({type(node).__name__})'))
    for node in pinned:
        if ast.dump(node) in unmatched:
            out.append(f'{bound_name(node) or ast.unparse(node)} is missing')
    if not out and [ast.dump(node) for node in body] != expected:
        out.append('the top level is not in the pinned order')
    for node in body:
        name = bound_name(node)
        if name in TABLE_SHA256 and isinstance(node, ast.Assign):
            try:
                digest = jsonschema.sha256_of(list(ast.literal_eval(node.value)))
            except (ValueError, TypeError, SyntaxError, RecursionError):
                out.append(f'{name} is not a literal table')
                continue
            if digest != TABLE_SHA256[name]:
                out.append(f'{name} does not match its pinned sha')
    return out


class PinTests(SimpleTestCase):
    def setUp(self):
        self.source = DATE_LITERALS.read_text(encoding='utf-8')

    def test_its_functions_are_ast_equal_to_v1s_eight(self):
        functions = top_functions(ast.parse(self.source))
        self.assertEqual(sorted(functions), sorted(EIGHT))
        for name in EIGHT:
            with self.subTest(name):
                self.assertEqual(ast.dump(functions[name]), ast.dump(V1_FUNCTIONS[name]))
        nested = [node.name for node in ast.walk(functions['dates']) if isinstance(node, ast.FunctionDef)]
        self.assertEqual(nested, ['dates', 'free'], "dates.free is copied inside dates, as v1's")

    def test_its_two_tables_equal_v1s_by_sha(self):
        for name, expected in TABLE_SHA256.items():
            with self.subTest(name):
                self.assertEqual(jsonschema.sha256_of(list(getattr(date_literals, name))), expected)
                self.assertEqual(jsonschema.sha256_of(list(getattr(v1_literals, name))), expected)

    def test_its_whole_top_level_is_the_pinned_structure(self):
        body = ast.parse(self.source).body
        self.assertIsInstance(body[0], ast.Expr, 'a docstring first')
        self.assertEqual([ast.dump(node) for node in body[1:]], [ast.dump(node) for node in pinned_structure()])
        self.assertEqual([bound_name(node) for node in body[1:] if bound_name(node)],
                         ['DAY', 'MONTH', 'YEAR', *V1_NAMES])
        self.assertEqual(pin_findings(self.source), [])
        # the module holds no name but these (the imported ones included)
        self.assertEqual({name for name in vars(date_literals) if not name.startswith('__')},
                         {'re', 'dataclass', 'date', 'Optional', 'Precision', 'annotations', 'DAY', 'MONTH', 'YEAR',
                          *V1_NAMES})

    def test_each_assertion_refuses_a_planted_control(self):
        source = self.source
        end = '    return stored_date(value, DAY)\n'
        self.assertEqual(source.count(end), 1)
        plants = {
            'an added function': (source + '\n\ndef _frames(text):\n    return text\n',
                                  'the pin does not hold at line'),
            "a changed pivot in _year": (source.replace('if value <= 68 else', 'if value <= 69 else', 1),
                                         "_year is not AST-equal"),
            'a changed docstring': (source.replace('A YYYY-MM-DD string as a date, or None.',
                                                   'A YYYY-MM-DD string as a date.', 1), 'iso_date is not AST-equal'),
            'a widened month table': (source.replace("'nov', 'dec')", "'nov', 'dec', 'previously')", 1),
                                      '_MONTHS does not match'),
            'a table that is no literal': (source.replace("_WEEKDAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', "
                                                          "'sun')", '_WEEKDAYS = 7', 1),
                                           '_WEEKDAYS is not a literal table'),
            'a widened unit pattern': (source.replace("|days?|weeks?|months?)'", "|days?|weeks?|months?|ago)'", 1),
                                       '_UNITS_AFTER is not AST-equal'),
            'a changed precision name': (source.replace('DAY = Precision.DAY.value', "DAY = 'day'", 1),
                                         "DAY is not the pinned header's"),
            'an added import': (source.replace('import re\n', 'import re\nfrom studio.interpretation import lexicon\n',
                                               1), 'the pin does not hold at line'),
            'a removed function': (source.replace(end, '    return None\n', 1).replace(
                '\n\ndef iso_date(value: str) -> Optional[date]:\n    """A YYYY-MM-DD string as a date, or None."""\n'
                '    return None\n', '\n', 1), 'iso_date is missing'),
            'two pinned statements swapped': (source.replace(
                "_FLAGS = re.A | re.I\n_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', "
                "'nov', 'dec')\n", "_MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', "
                "'nov', 'dec')\n_FLAGS = re.A | re.I\n", 1), 'not in the pinned order'),
            'a timing frame list': (source + "\n_FRAMES = ('at that time', 'previously')\n",
                                    'the pin does not hold at line'),
            'a frame set of characters': (source + "\n_OPEN = frozenset('<[(')\n", 'the pin does not hold at line'),
            'a frame list on a class': (source.replace('    start: int\n', "    start: int\n    FRAMES = ['earlier', "
                                                       "'prior']\n", 1), 'DateLiteral is not AST-equal'),
            'a frame dict': (source + "\nTIMES = {'earlier': -1, 'later': 1}\n", 'the pin does not hold at line'),
            # arbiter triage 1c#6's plants (R6 and R7 ran as mutants and survived the earlier pin, 12 of 12 green)
            'R6, a frame list built by split': (source.replace(end, end + "\n\n_FRAMES = 'at that time|previously|in the "
                                                               "past'.split('|')\n", 1), 'it binds _FRAMES'),
            'R7, a reader as a lambda': (source.replace(end, end + "\n\n_earlier = lambda words: 'previously' in "
                                                        "words.lower()\n", 1), 'it binds _earlier'),
            'a frame tuple by concatenation': (source + "\n_FRAMES = ('at that time',) + ('previously',) + ('in the "
                                               "past',)\n", 'it binds _FRAMES'),
            'a frame alternation as one regex': (source + "\n_FRAMES = re.compile(r'(?:at that time|previously|in the "
                                                 "past)', _FLAGS)\n", 'it binds _FRAMES'),
            'a reader as a method of a new class': (source + "\n\nclass _Frames:\n    @staticmethod\n    def earlier("
                                                    "words: str) -> bool:\n        return 'previously' in words\n",
                                                    'it binds _Frames'),
            'a frame list unpacked into two names': (source + "\n_A, _B = 'at that time', 'previously'\n",
                                                     '(Assign)'),
            'a reader under a guard': (source + "\nif True:\n    _FRAMES = ['at that time', 'previously']\n", '(If)'),
            'a rebound pinned name': (source + "\n_MONTHS = _MONTHS + ('previously',)\n", 'it binds _MONTHS'),
        }
        for name, (planted, expected) in plants.items():
            with self.subTest(name):
                self.assertNotEqual(planted, source, 'the plant applied')
                findings = pin_findings(planted)
                self.assertTrue(any(expected in finding for finding in findings), findings)
        for control in (source + '\n# a comment\n', source.replace('"""The date literals of L1', '"""The dates of L1',
                                                                   1)):
            with self.subTest(control=control[-12:]):
                self.assertNotEqual(control, source)
                self.assertEqual(pin_findings(control), [], 'a comment, or the docstring reworded, stays green')


# --- the parity -------------------------------------------------------------------------------------------------------


def v1_fixture_strings() -> list:
    """v1's literal fixtures: every string constant of tests/test_interpretation_literals.py, in a stable order."""
    tree = ast.parse(V1_LITERAL_TESTS.read_text(encoding='utf-8'))
    return sorted({node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                   and isinstance(node.value, str)})


def fields(found: tuple) -> list:
    return [(item.start, item.end, item.value, item.precision, item.iso) for item in found]


class ParityTests(SimpleTestCase):
    def setUp(self):
        self.fixtures = v1_fixture_strings()

    def test_the_harvest_holds_v1s_cases(self):
        for case in ('03/14/2026', 'Tuesday, November 9, 2026', '16-Nov-2026', '2024.5', '2019-2024', '2024-02-30'):
            self.assertIn(case, self.fixtures)

    def test_dates_and_full_dates_equal_v1s_on_v1s_fixtures(self):
        differing = [text for text in self.fixtures
                     if fields(date_literals.dates(text)) != fields(v1_literals.dates(text))
                     or fields(date_literals.full_dates(text)) != fields(v1_literals.full_dates(text))]
        self.assertEqual(differing, [])
        self.assertTrue(any(date_literals.dates(text) for text in self.fixtures), 'the fixtures read dates')

    def test_full_value_equals_v1s_on_every_match(self):
        for text in self.fixtures:
            mine = [date_literals._full_value(match) for match in date_literals.FULL_DATE.finditer(text)]
            theirs = [v1_literals._full_value(match) for match in v1_literals.FULL_DATE.finditer(text)]
            self.assertEqual(mine, theirs, text)

    def test_stored_date_and_iso_date_equal_v1s(self):
        values = self.fixtures + ['2024', '2024-03', '2024-03-14', '2024-13', '2024-02-30', '24', '2026-11-09',
                                  '11/09/2026', '', '0000-01-01', '9999-12-31']
        for value in values:
            for precision in ('day', 'month', 'year', 'decade', ''):
                self.assertEqual(date_literals.stored_date(value, precision), v1_literals.stored_date(value, precision),
                                 (value, precision))
            self.assertEqual(date_literals.iso_date(value), v1_literals.iso_date(value), value)
        self.assertEqual(date_literals.stored_date(2024, 'year'), v1_literals.stored_date(2024, 'year'))

    def test_compare_equals_v1s(self):
        service = date(2026, 11, 9)
        literals = {item.value for text in self.fixtures for item in v1_literals.dates(text)}
        values = sorted(literals | {service + timedelta(days=offset) for offset in range(-400, 401, 13)})
        for value in values:
            for precision in ('day', 'month', 'year'):
                self.assertEqual(date_literals.compare(value, precision, service),
                                 v1_literals.compare(value, precision, service), (value, precision))
        for module in (date_literals, v1_literals):
            with self.assertRaises(ValueError):
                module.compare(service, 'week', service)

    def test_year_and_month_equal_v1s(self):
        for text in [f'{year:02d}' for year in range(100)] + [str(year) for year in range(1890, 2110)]:
            self.assertEqual(date_literals._year(text), v1_literals._year(text), text)
        names = ('jan', 'January', 'FEB', 'Sept', 'sep', 'May', 'june', 'Dec.', 'nov', 'October', 'aug', 'Mar.')
        for name in names:
            self.assertEqual(date_literals._month(name), v1_literals._month(name), name)
        for module in (date_literals, v1_literals):
            with self.assertRaises(ValueError):
                module._month('xyz')

    def test_the_patterns_constants_and_class_are_v1s(self):
        for name in ('FULL_DATE', 'MONTH_YEAR', 'BARE_YEAR'):
            with self.subTest(name):
                self.assertEqual(getattr(date_literals, name).pattern, getattr(v1_literals, name).pattern)
                self.assertEqual(getattr(date_literals, name).flags, getattr(v1_literals, name).flags)
        self.assertEqual({key: pattern.pattern for key, pattern in date_literals._STORED.items()},
                         {key: pattern.pattern for key, pattern in v1_literals._STORED.items()})
        self.assertEqual((date_literals.DAY, date_literals.MONTH, date_literals.YEAR),
                         (v1_literals.DAY, v1_literals.MONTH, v1_literals.YEAR))
        mine = next(node for node in ast.parse(DATE_LITERALS.read_text(encoding='utf-8')).body
                    if isinstance(node, ast.ClassDef))
        theirs = next(node for node in ast.parse(V1_LITERALS.read_text(encoding='utf-8')).body
                      if isinstance(node, ast.ClassDef) and node.name == 'DateLiteral')
        self.assertEqual(ast.dump(mine), ast.dump(theirs))

    @hypothesis.settings(max_examples=500, deadline=None, database=None)
    @hypothesis.given(st.lists(st.sampled_from(
        ['2026', '1999', '2100', '03', '3', '14', '/', '-', ' ', ', ', '.', 'March', 'Mar.', 'Sept', 'nov', 'Monday',
         'Mon', 'tue', '14th', '1st', 'x', 'mg', 'cm', '2026-11-09', '11/09/2026', '1/2024', '\t', 'Feb', '29', '30']),
        max_size=10).map(''.join))
    def test_equal_to_v1s_on_random_date_shaped_texts(self, text):
        self.assertEqual(fields(date_literals.dates(text)), fields(v1_literals.dates(text)))
        self.assertEqual(fields(date_literals.full_dates(text)), fields(v1_literals.full_dates(text)))
