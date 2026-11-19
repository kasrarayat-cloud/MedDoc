"""The mutation proofs of the guard (docs/gemini-migration/FINAL-V2.md 5.7 measure 7; step 6a of its 8.1; the S12 proofs of
design/FINAL.md 10.4(4) before them). Synthetic data only; nothing is sent.

A guard that never goes red proves nothing. 5.7 measure 7's seven plants, each a reader re-planted into the new path:
- P1 ``facts.day_of`` called from ``engine/combination.procedure_day``;
- P2 ``lexicon.negation`` from ``engine/pairing`` (pairs_of);
- P3 ``events.another_role_hold`` from ``engine/evaluate`` (decide);
- P4 ``re.search`` in ``overlay.counted_codes``;
- P5 ``verify.status_words`` from ``contract/settle`` (settle);
- P6 a word tuple in ``contract/geometry.py``;
- P7 ``fold(words['text']).startswith('no')`` in ``engine/evaluate`` (decide).
Each turns ITS guard red, naming only itself: the counting guard (5.7 measures 1 and 8: the new-path matrix of
tests/test_guard_matrix_new_path.py, CALL-level checks on, stopped at its first red entry) for a call of a retired
module - P1, P2, P3, P5 - whose red entry counts the planted call's code and nothing else (every name it counts is in
the retired modules, one is the planted function); and the static rules (5.7 measure 4, tests/test_guard_static.py)
for every plant - WordsNeverDecide for P1-P5 and P7, NoWordLists for P6 - whose every finding lies on the planted
lines. P4, P6 and P7 call nothing the sentinel denies, which is why the static rules exist ("the one measure that
catches a veto re-written under a NEW name; counting cannot"). The CONTROL plants a comment: the same machinery, and
every guard stays green.

HOW A PLANT IS APPLIED. In memory, never on disk: the module's source text with the planted lines inserted (after the
function's docstring, or at the end for P6) is what the static rule reads; for the counting guard that whole text is
compiled under the module's file name and the function's code object - the planted one - replaces the function's
__code__, so every importer of it, a forked child included, runs it. APPLIED is asserted by the plant's marker (in the
planted text, and among the swapped code's constants for a code plant) and by the text's sha256 differing from the
file's; RESTORED by sha256 (the function's code digest after the restore equals its digest before, the file's bytes are
unchanged throughout); both are printed.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import sys
import types
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import overlay, sentinel
from studio.interpretation.contract import geometry, settle
from studio.interpretation.engine import combination, evaluate, pairing
from tests import test_guard_static as static
from tests.guard_support import LABELS, NEW, Matrix, Red
from tests.test_guard_matrix_new_path import V2GuardCase, V2World


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(code) -> str:
    """sha256 of everything a code object runs and says - its bytecode, its constants (a nested code object by its own
    digest, a frozenset sorted), names, flags, line table, exception table, file and names - never marshal's bytes,
    whose reference flags follow the object's reference count."""
    def const(value):
        if isinstance(value, types.CodeType):
            return ('code', _digest(value))
        if isinstance(value, frozenset):
            return ('frozenset', tuple(sorted(repr(item) for item in value)))
        if isinstance(value, tuple):
            return tuple(const(item) for item in value)
        return value

    fields = (code.co_code, tuple(const(value) for value in code.co_consts), code.co_names, code.co_varnames,
              code.co_freevars, code.co_cellvars, code.co_flags, code.co_argcount, code.co_posonlyargcount,
              code.co_kwonlyargcount, code.co_firstlineno, code.co_linetable, code.co_exceptiontable, code.co_filename,
              code.co_name, code.co_qualname)
    return _sha(repr(fields).encode())


def _constants(code) -> set:
    """Every string constant of ``code`` and of the code objects nested in it."""
    out = set()
    for const in code.co_consts:
        if isinstance(const, str):
            out.add(const)
        elif isinstance(const, tuple):
            out |= {item for item in const if isinstance(item, str)}
        elif isinstance(const, types.CodeType):
            out |= _constants(const)
    return out


class Plant:
    """One plant (module docstring). ``module``: where it goes; ``function``: the function it is planted in (None: at
    the module's end, P6); ``lines``: the planted source lines, carrying ``marker``; ``rule``: the static rule's key
    ('wnd' WordsNeverDecide, 'nwl' NoWordLists) over ``key`` (package_modules()' key); ``counted``: for a call of a
    retired module, the text every name of its red matrix entry contains and the planted function's name, else None."""

    def __init__(self, label, module, function, lines, marker, *, key, rule, counted=None):
        self.label, self.module, self.function, self.lines, self.marker = label, module, function, lines, marker
        self.key, self.rule, self.counted = key, rule, counted

    @property
    def path(self) -> Path:
        return Path(self.module.__file__)

    def target(self):
        return getattr(self.module, self.function)

    def planted(self) -> tuple[str, range]:
        """(the module's source with the lines planted, the planted lines' numbers)."""
        source = self.path.read_text(encoding='utf-8')
        lines = source.splitlines(keepends=True)
        if self.function is None:
            at, indent = len(lines), ''
        else:
            tree = ast.parse(source)
            [node] = [item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == self.function]
            head = node.body[0]
            docstring = (isinstance(head, ast.Expr) and isinstance(head.value, ast.Constant)
                         and isinstance(head.value.value, str))
            at = head.end_lineno if docstring else head.lineno - 1
            first = node.body[1] if docstring and len(node.body) > 1 else head
            indent = ' ' * first.col_offset
        planted = [f'{indent}{line}\n' for line in self.lines]
        text = ''.join(lines[:at] + planted + lines[at:])
        return text, range(at + 1, at + 1 + len(planted))

    def findings(self, text: str) -> list:
        if self.rule == 'nwl':
            return static.no_word_lists(text, self.key)
        return static.words_never_decide(text, self.key)

    def compiled(self, text: str):
        """The function's code object as ``text`` compiles under the module's file name (the whole module compiled,
        never run, so the function is compiled in its module's own context)."""
        fn = self.target()
        code = compile(ast.parse(text), fn.__code__.co_filename, 'exec', dont_inherit=True)
        [found] = [const for const in code.co_consts if isinstance(const, types.CodeType)
                   and const.co_name == self.function]
        return found

    @contextlib.contextmanager
    def applied(self):
        """The plant applied to the function (the counting guard's form), restored and checked afterwards."""
        fn = self.target()
        original = fn.__code__
        file_before, code_before = _sha(self.path.read_bytes()), _digest(original)
        if self.marker in _constants(original):
            raise AssertionError(f'{self.label}: the marker is in the code before the plant')
        text, _ = self.planted()
        fn.__code__ = self.compiled(text)
        applied = fn.__code__ is not original and (self.marker in _constants(fn.__code__) or self.marker in text)
        print(f'\n[6a mutation {self.label}] applied: {applied} ({self.module.__name__}.{self.function}; text sha256 '
              f'{file_before[:16]} -> {_sha(text.encode())[:16]})', file=sys.stderr)
        try:
            if not applied:
                raise AssertionError(f'{self.label}: the mutation did not apply')
            yield fn
        finally:
            fn.__code__ = original
            code_after, file_after = _digest(fn.__code__), _sha(self.path.read_bytes())
            restored = fn.__code__ is original and code_after == code_before
            print(f'[6a mutation {self.label}] restored: {restored} (code sha256 {code_before[:16]} -> '
                  f'{code_after[:16]}; file sha256 {file_before[:16]} -> {file_after[:16]})', file=sys.stderr)
            if not restored or file_after != file_before:
                raise AssertionError(f'{self.label}: not restored (code {code_before} -> {code_after}, file '
                                     f'{file_before} -> {file_after})')


def _call(module, marker, call):
    """A planted call of a retired module, guarded so the world goes on (its PY_START is counted whatever it raises)."""
    return ['try:', f"    __import__('studio.interpretation.{module}', fromlist=['{marker}']).{call}",
            'except Exception:', '    pass']


P1 = Plant('P1 facts.day_of in engine/combination.procedure_day', combination, 'procedure_day',
           _call('facts', 'S6A-P1', "day_of({}, None)"), 'S6A-P1', key='engine/combination', rule='wnd',
           counted=('studio/interpretation/', 'day_of'))
P2 = Plant('P2 lexicon.negation in engine/pairing.pairs_of', pairing, 'pairs_of',
           _call('lexicon', 'S6A-P2', "negation('no')"), 'S6A-P2', key='engine/pairing', rule='wnd',
           counted=('studio/interpretation/', 'negation'))
P3 = Plant('P3 events.another_role_hold in engine/evaluate.decide', evaluate, 'decide',
           _call('events', 'S6A-P3', "another_role_hold('45385', None, (), None, (), 'S6A')"), 'S6A-P3',
           key='engine/evaluate', rule='wnd', counted=('studio/interpretation/', 'another_role_hold'))
P4 = Plant('P4 re.search in overlay.counted_codes', overlay, 'counted_codes',
           ["__import__('re').search('no', 'S6A-P4')"], 'S6A-P4', key='overlay', rule='wnd')
P5 = Plant('P5 verify.status_words in contract/settle.settle', settle, 'settle',
           _call('verify', 'S6A-P5', "status_words('not_performed', 'no')"), 'S6A-P5', key='contract/settle',
           rule='wnd', counted=('studio/interpretation/', 'status_words'))
P6 = Plant('P6 a word tuple in contract/geometry.py', geometry, None,
           ["_S6A_P6_WORDS = ('no', 'not', 'without')"], '_S6A_P6_WORDS', key='contract/geometry', rule='nwl')
P7 = Plant("P7 fold(words['text']).startswith('no') in engine/evaluate.decide", evaluate, 'decide',
           ['from studio.interpretation.contract.fold import fold', "words = {'text': 'S6A-P7'}",
            "fold(words['text']).startswith('no')"], 'S6A-P7', key='engine/evaluate', rule='wnd')
CONTROL = Plant('control: a planted comment', combination, 'procedure_day', ['# S6A-CONTROL: a comment, nothing more'],
                'S6A-CONTROL', key='engine/combination', rule='wnd')
PLANTS = (P1, P2, P3, P4, P5, P6, P7)
COUNTED = tuple(plant for plant in PLANTS if plant.counted is not None)


class MachineryTests(SimpleTestCase):
    def test_a_function_recompiled_from_its_own_text_is_identical_to_the_code_it_runs(self):
        for plant in (P1, P2, P3, P4, P5, P7, CONTROL):
            with self.subTest(plant=plant.label):
                live = plant.target().__code__
                fresh = plant.compiled(plant.path.read_text(encoding='utf-8'))
                self.assertEqual(fresh, live)  # the code object's own equality: bytecode, constants, names, positions
                self.assertEqual(_digest(fresh), _digest(live))
                self.assertNotEqual(_digest(plant.compiled(plant.planted()[0])), _digest(live))

    def test_each_plant_is_applied_by_its_marker_and_restored_by_sha256(self):
        for plant in (P1, P2, P3, P4, P5, P7):
            with self.subTest(plant=plant.label):
                before = plant.target().__code__
                with plant.applied() as fn:
                    self.assertIsNot(fn.__code__, before)
                    self.assertIn(plant.marker, _constants(fn.__code__))
                    self.assertEqual(fn.__code__.co_filename, before.co_filename)
                self.assertIs(plant.target().__code__, before)
                self.assertNotIn(plant.marker, _constants(plant.target().__code__))
        text, lines = P6.planted()
        self.assertIn(P6.marker, text)
        self.assertNotIn(P6.marker, P6.path.read_text(encoding='utf-8'))
        self.assertEqual(len(lines), 1)

    def test_the_restore_is_checked_even_when_the_proof_fails(self):
        before = P1.target().__code__
        with self.assertRaises(ZeroDivisionError):
            with P1.applied():
                raise ZeroDivisionError('a proof that raised')
        self.assertIs(P1.target().__code__, before)


class StaticProofTests(SimpleTestCase):
    """Each plant turns its static rule red, naming only itself (every finding on the planted lines); the control stays
    green; and nothing on disk changes."""

    def test_each_plant_turns_its_static_rule_red_naming_only_itself(self):
        for plant in PLANTS:
            with self.subTest(plant=plant.label):
                file_before = _sha(plant.path.read_bytes())
                self.assertEqual(plant.findings(plant.path.read_text(encoding='utf-8')), [])  # green before
                text, lines = plant.planted()
                self.assertIn(plant.marker, text)  # applied
                self.assertNotEqual(_sha(text.encode()), file_before)
                found = plant.findings(text)
                self.assertTrue(found, plant.label)
                planted = [line for line in found if int(line.split(':')[1].split()[0]) in lines]
                self.assertEqual(found, planted, (plant.label, list(lines)))  # naming only itself
                print(f'[6a mutation {plant.label}] static red: {found[0]} ({len(found)} finding(s)); file sha256 '
                      f'{file_before[:16]} -> {_sha(plant.path.read_bytes())[:16]}', file=sys.stderr)
                self.assertEqual(_sha(plant.path.read_bytes()), file_before)  # restored: nothing was written

    def test_the_control_plant_leaves_every_rule_green(self):
        text, lines = CONTROL.planted()
        self.assertIn(CONTROL.marker, text)
        self.assertEqual(len(lines), 1)
        for key in ('engine/combination',):
            self.assertEqual(static.words_never_decide(text, key), [])
            self.assertEqual(static.no_word_lists(text, key), [])
        self.assertEqual(CONTROL.compiled(text).co_code, CONTROL.target().__code__.co_code)  # a comment changes no code


class MiniWorld(V2World):
    """The new-path matrix's first encounter (V2World's E1: upload, the worker - extract, pass 1, pass 2, analyze,
    predict, assess - and its reads), which reaches every function a counting plant is planted in."""

    def _run(self):
        self.no_encounter()
        self.v2_upload('E1', file=True)
        self.drain('E1 first')
        self.reads('E1')
        return self


class CountingProofTests(V2GuardCase):
    """Each counting plant turns the new-path matrix red at its first entry that reaches it, naming the planted call's
    code only; the control leaves the whole of it green."""

    def prove(self, plant):
        matrix = Matrix(self, stop_on=lambda item: item.count(LABELS) > 0 or item.errors > 0)
        with plant.applied(), sentinel.call_checks():
            with self.assertRaises(Red) as caught:
                MiniWorld(self, matrix).run()
        red = caught.exception.observation
        names = red.names(LABELS)
        within, named = plant.counted
        self.assertTrue(names, red.describe())
        self.assertEqual(red.errors, 0, red.describe())
        self.assertTrue(red.count(NEW) > 0, red.describe())  # new-path work ran it
        # the plant's call, nothing else: each name a retired module's code (its file) or cache wrapper (its module)
        self.assertTrue(all(within in line or within.replace('/', '.') in line for line in names), red.describe())
        self.assertFalse([line for line in names if '/engine/' in line or '/contract/' in line], red.describe())
        self.assertTrue(any(f' {named} ' in f'{line} ' or line.endswith(f' {named}') or f' {named} x' in line
                            for line in names), red.describe())
        self.assertTrue(all(sentinel.kind_of(key) == sentinel.RETIRED for label in LABELS for key in red.hits[label]),
                        red.describe())  # the RETIRED kind's, each
        self.assertEqual([item for item in matrix.observations[:-1] if item.count(LABELS)], [])  # red from here on
        print(f'[6a mutation {plant.label}] red at {red.what} ({red.tag}): {names[0]}', file=sys.stderr)
        return red

    def test_p1_facts_day_of_in_engine_combination_procedure_day(self):
        self.prove(P1)

    def test_p2_lexicon_negation_in_engine_pairing(self):
        self.prove(P2)

    def test_p3_events_another_role_hold_in_engine_evaluate(self):
        self.prove(P3)

    def test_p5_verify_status_words_in_contract_settle(self):
        self.prove(P5)

    def test_the_control_plant_leaves_the_whole_matrix_green(self):
        matrix = Matrix(self, stop_on=lambda item: item.count(LABELS) > 0 or item.errors > 0)
        with CONTROL.applied(), sentinel.call_checks():
            MiniWorld(self, matrix).run()
        self.assertEqual(matrix.red(LABELS), [], matrix.report(LABELS))
        self.assertTrue(any(item.key == ('stage', 'assess') for item in matrix.observations))
        self.assertGreater(len(matrix.observations), 20)
