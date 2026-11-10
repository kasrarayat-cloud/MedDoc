"""The mutation proofs of the call-guard matrix (Gemini migration slice S12; design/FINAL.md 10.4(4), with
design/ADJUDICATION.md R-3; DECISIONS D17). Synthetic data only; nothing is sent.

A matrix that never goes red proves nothing. Each proof here plants one legacy read into new-path code and runs the
new-path matrix (tests/guard_support.World, CALL-level checks on, on a database of new-path encounters only) until its
first red entry, which must name the planted read and nothing else:
- FINAL 10.4(4)'s three: gi.services.listed_in_doubt(act) inside combination.base_included (a gi function: code);
  reconcile.FAILED_ATTEMPT.search(...) inside coverage (coverage.sessions; a legacy regex: CALL);
  review_view.stored_from(...) inside overlay (overlay.stored_from; a review_view function: code);
- R-3's three CALL forms, each in a new-path function of its own: a re.Pattern method descriptor given a denied pattern
  as its first argument (re.Pattern.search(cues.PAGE_NUMBER_LINE, ...) in overlay.coding_of), a bound builtin whose
  __self__ is a denied pattern (checks._V2_DENIAL_WORDS.search kept, then called, in facts.derive), and one of the re
  module's functions given a denied pattern (re.search(engine._NEGATED_BEFORE, ...) in events.evaluate).
A control plants a statement that reads nothing of the legacy reader, and the whole matrix stays green under it.

HOW A PLANT IS APPLIED. In memory, never on disk: other slices run their suites from this tree at the same time, and a
committed test does not edit source files. The function's own source, as its file holds it, is parsed and recompiled
under its file's name with the planted statement first in its body (after its docstring), and that code object replaces
the function's __code__ - so every importer of the function, a forked child included, runs the planted code. The
machinery is shown exact first: recompiled with nothing planted, each function's code is equal, field by field, to the
code it runs. A plant is asserted APPLIED by its marker (a constant of the planted statement, in the live code's
constants and absent before) and RESTORED by sha256 (the sha256 of the function's code - every field it runs and says -
after the restore equals its sha256 before, and its file's bytes are unchanged throughout); both are printed.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import sys
import types
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import combination, coverage, events, facts, overlay, sentinel
from tests.guard_support import CODE, LABELS, NEW, REGEX, GuardCase, Matrix, Red, World


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
    """One planted read of the legacy reader in a new-path function (module docstring). ``statement``: Python source of
    the planted statement(s), carrying ``marker``; ``within``: a text every name the red entry counts contains (what the
    planted read reaches); ``named``: a text one of them contains (the planted read itself); ``kind``: what the sentinel
    counts it as (CODE, or REGEX for a CALL-level read)."""

    def __init__(self, label, module, function, statement, marker, *, within, named, kind):
        self.label, self.module, self.function = label, module, function
        self.statement, self.marker = statement, marker
        self.within, self.named, self.kind = within, named, kind

    def target(self):
        return getattr(self.module, self.function)

    def compiled(self, planted: bool):
        """The function's code, recompiled from its file under its file's name - with the statement planted first in
        its body, or exactly as written. The whole module is compiled (never run), so the function is compiled in its
        module's own context: its future imports, and the names its imports bind (3.12 compiles an attribute call on an
        imported module otherwise than on any other global)."""
        fn = self.target()
        filename = fn.__code__.co_filename
        tree = ast.parse(Path(filename).read_text(encoding='utf-8'))
        [node] = [item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == self.function]
        if planted:
            head = node.body[0] if node.body else None
            docstring = (isinstance(head, ast.Expr) and isinstance(head.value, ast.Constant)
                         and isinstance(head.value.value, str))
            first = 1 if docstring else 0
            extra = ast.parse(self.statement).body
            line = node.body[first].lineno
            for statement in extra:
                ast.increment_lineno(statement, line - 1)
            node.body[first:first] = extra
            ast.fix_missing_locations(tree)
        code = compile(tree, filename, 'exec', dont_inherit=True)
        [found] = [const for const in code.co_consts if isinstance(const, types.CodeType)
                   and const.co_name == self.function and const.co_firstlineno == fn.__code__.co_firstlineno]
        return found

    @contextlib.contextmanager
    def applied(self):
        fn = self.target()
        path = Path(fn.__code__.co_filename)
        original = fn.__code__
        file_before, code_before = _sha(path.read_bytes()), _digest(original)
        if self.marker in _constants(original):
            raise AssertionError(f'{self.label}: the marker is in the code before the plant')
        fn.__code__ = self.compiled(planted=True)
        applied = self.marker in _constants(fn.__code__)
        print(f'\n[S12 mutation {self.label}] applied: {applied} ({self.module.__name__}.{self.function})',
              file=sys.stderr)
        try:
            if not applied:
                raise AssertionError(f'{self.label}: the mutation did not apply')
            yield fn
        finally:
            fn.__code__ = original
            code_after, file_after = _digest(fn.__code__), _sha(path.read_bytes())
            restored = fn.__code__ is original and code_after == code_before
            print(f'[S12 mutation {self.label}] restored: {restored} (code sha256 {code_before[:16]} -> '
                  f'{code_after[:16]}; file sha256 {file_before[:16]} -> {file_after[:16]})', file=sys.stderr)
            if not restored or file_after != file_before:
                raise AssertionError(f'{self.label}: not restored (code {code_before} -> {code_after}, file '
                                     f'{file_before} -> {file_after})')


# FINAL 10.4(4)
M1 = Plant('M1 gi.services.listed_in_doubt in combination.base_included', combination, 'base_included',
           "__import__('studio.gi.services', fromlist=['S12-M1']).listed_in_doubt("
           "type('S12M1Act', (), {'status': 'uncertain', 'cues': ()})())",
           'S12-M1', within='studio/gi/services.py:', named='listed_in_doubt', kind=CODE)
M2 = Plant('M2 reconcile.FAILED_ATTEMPT.search in coverage', coverage, 'sessions',
           "__import__('studio.validation.reconcile', fromlist=['S12-M2']).FAILED_ATTEMPT.search("
           "'the snare could not be passed')",
           'S12-M2', within='studio.validation.reconcile.FAILED_ATTEMPT', named='FAILED_ATTEMPT', kind=REGEX)
M3 = Plant('M3 review_view.stored_from in overlay', overlay, 'stored_from',
           "__import__('studio.validation.review_view', fromlist=['S12-M3']).stored_from(proposal, clarifications)",
           'S12-M3', within='studio/validation/review_view.py:', named='stored_from', kind=CODE)
# R-3's three CALL forms
F1 = Plant('F1 a re.Pattern method descriptor given a denied pattern', overlay, 'coding_of',
           "__import__('re').Pattern.search(__import__('studio.gi.cues', fromlist=['S12-F1']).PAGE_NUMBER_LINE, '3')",
           'S12-F1', within='studio.gi.cues.PAGE_NUMBER_LINE', named='PAGE_NUMBER_LINE', kind=REGEX)
F2 = Plant('F2 a bound builtin whose __self__ is a denied pattern', facts, 'derive',
           "_s12_bound = __import__('studio.validation.checks', fromlist=['S12-F2'])._V2_DENIAL_WORDS.search\n"
           "_s12_bound('the polyp was not removed')",
           'S12-F2', within='studio.validation.checks._V2_DENIAL_WORDS', named='_V2_DENIAL_WORDS', kind=REGEX)
F3 = Plant("F3 one of the re module's functions given a denied pattern", events, 'evaluate',
           "__import__('re').search(__import__('studio.validation.engine', fromlist=['S12-F3'])._NEGATED_BEFORE, "
           "'was not ')",
           'S12-F3', within='studio.validation.engine._NEGATED_BEFORE', named='_NEGATED_BEFORE', kind=REGEX)
CONTROL = Plant('control: a planted statement that reads nothing of the legacy reader', combination, 'base_included',
                "len(('S12-CONTROL',))", 'S12-CONTROL', within='', named='', kind=CODE)
PLANTS = (M1, M2, M3, F1, F2, F3)


class MachineryTests(SimpleTestCase):
    def test_a_function_recompiled_with_nothing_planted_is_identical_to_the_code_it_runs(self):
        for plant in PLANTS + (CONTROL,):
            with self.subTest(plant=plant.label):
                fresh, live = plant.compiled(planted=False), plant.target().__code__
                self.assertEqual(fresh, live)  # the code object's own equality: bytecode, constants, names, positions
                self.assertEqual((fresh.co_filename, fresh.co_qualname), (live.co_filename, live.co_qualname))
                self.assertEqual(_digest(fresh), _digest(live))
                self.assertNotEqual(_digest(plant.compiled(planted=True)), _digest(live))

    def test_a_plant_is_applied_by_its_marker_and_restored_by_sha256(self):
        for plant in PLANTS:
            with self.subTest(plant=plant.label):
                before = plant.target().__code__
                with plant.applied() as fn:
                    self.assertIn(plant.marker, _constants(fn.__code__))
                    self.assertIsNot(fn.__code__, before)
                    self.assertEqual(fn.__code__.co_filename, before.co_filename)
                self.assertIs(plant.target().__code__, before)
                self.assertNotIn(plant.marker, _constants(plant.target().__code__))

    def test_the_restore_is_checked_even_when_the_proof_fails(self):
        before = M1.target().__code__
        with self.assertRaises(ZeroDivisionError):
            with M1.applied():
                raise ZeroDivisionError('a proof that raised')
        self.assertIs(M1.target().__code__, before)


class MutationProofTests(GuardCase):
    """Each planted read turns the new-path matrix red at its first entry that reaches it."""

    def prove(self, plant):
        matrix = Matrix(self, stop_on=lambda item: item.count(LABELS) > 0 or item.errors > 0)
        with plant.applied(), sentinel.call_checks():
            with self.assertRaises(Red) as caught:
                World(self, matrix).run()
        red = caught.exception.observation
        names = red.names(LABELS)
        self.assertTrue(names, red.describe())
        self.assertEqual(red.errors, 0, red.describe())
        self.assertTrue(red.count(NEW) > 0, red.describe())  # new-path work ran it
        self.assertTrue(all(plant.within in line for line in names), red.describe())  # the plant's read, nothing else
        self.assertTrue(any(plant.named in line for line in names), red.describe())
        self.assertGreater(red.kinds(LABELS)[plant.kind], 0, red.describe())
        self.assertTrue(all(red is not item for item in matrix.observations[:-1]))
        self.assertEqual([item for item in matrix.observations[:-1] if item.count(LABELS)], [])  # red from here on
        print(f'[S12 mutation {plant.label}] red at {red.what} ({red.tag}): {names[0]}', file=sys.stderr)
        return red

    def test_m1_gi_services_listed_in_doubt_in_combination_base_included(self):
        self.prove(M1)

    def test_m2_reconcile_failed_attempt_search_in_coverage(self):
        self.prove(M2)

    def test_m3_review_view_stored_from_in_overlay(self):
        self.prove(M3)

    def test_r3_a_pattern_method_descriptor_given_a_denied_pattern(self):
        self.prove(F1)

    def test_r3_a_bound_builtin_whose_self_is_a_denied_pattern(self):
        self.prove(F2)

    def test_r3_a_re_module_function_given_a_denied_pattern(self):
        self.prove(F3)

    def test_the_control_plant_leaves_the_whole_matrix_green(self):
        # mutation baseline: the same machinery, a plant that reads nothing of the legacy reader - no entry turns red
        matrix = Matrix(self, stop_on=lambda item: item.count(LABELS) > 0 or item.errors > 0)
        with CONTROL.applied(), sentinel.call_checks():
            World(self, matrix).run()
        self.assertEqual(matrix.red(LABELS), [], matrix.report(LABELS))
        self.assertEqual(matrix.missing(), [])
        self.assertGreater(len(matrix.observations), 200)
