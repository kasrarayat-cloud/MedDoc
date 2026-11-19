"""The stored-fact predicates re-homed from studio/gi/context.py into studio/context_facts.py (Gemini migration,
FINAL.md sections 3.1 and 4.4; slice S04). Synthetic values only, no database.

- Identity: every name gi.context had is now studio.context_facts' own object (``is``, never equality), so every
  existing importer reads the one implementation.
- gi/context.py defines none of them and imports exactly them back. context_facts imports nothing from studio.gi, at
  load or anywhere in its code; its code objects live in studio/context_facts.py, so the deny set of FINAL 10.1
  (computed from the code objects of studio/gi/*.py) does not hold them, and a call to one executes no code of
  studio/gi (D17).
- The move is verbatim: each re-homed definition's source lines are pinned by sha256 to their text in gi/context.py at
  070fa0a75, which is byte for byte the rollback image's (c2e53f8e7d33), so the predicates read every stored fact
  exactly as the legacy readers and the rollback image read it (FINAL 14.3). A deliberate change to one updates its
  pin, with the reason.
- The predicates' contract on a Fact and on a stored context fact (a mapping).
"""
import ast
import hashlib
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase

from studio import context_facts
from studio.gi import context as gi_context
from studio.types import Fact

APP = Path(__file__).resolve().parents[1]
FACTS_PY = APP / 'studio' / 'context_facts.py'
CONTEXT_PY = APP / 'studio' / 'gi' / 'context.py'

# Every re-homed name (FINAL.md 3.1: gi/context.py:1888-1924, CHARGE_DATE_NOTE through charge_date_own, and 3395-3438),
# with the sha256 of its definition's source lines (the comment lines above a constant are not among them), which are
# byte for byte its lines in studio/gi/context.py at 070fa0a75 and at c2e53f8e7d33, the rollback image.
REHOMED = {
    'CHARGE_DATE_NOTE': '0147f2a239b5a46e303f7bcb7d4a95ab5132aaa7e4bd48bbb7e753e31a47dffc',
    '_CHARGE_NOTE_HEAD': '751b9cc04a81729d3090de21e981569870d04ae92c73e05f9102d100b5cf0a5f',
    'WIDE_DATE_ASK_NOTE': '9fc0b5f9c65a60e4d231b58138b539cc4326da2f8ceffe7f21f885a043b81685',
    '_WIDE_NOTE_HEAD': 'df931d72b2c7f1748105847c4c61ea5c9a521e4f9261d0eca7005800295bf75d',
    '_CHARGE_NOTE_REST': '2891e0dbd63d914c5e60acc8eb9d232ed5e84be93052891de5c76b7695b195d5',
    '_CHARGE_NOTE_OWN': 'de3b63b4d4146d68598b562cbcba8060c4a568e9b17046be9c311230beabbb45',
    'charge_date_problem': '1f21b2d73de811b7ce5844230a461203f9930c11826d6f7548e4da73c4d60859',
    'charge_date_own': 'a0690b37af0892072c94eac170d6372986f44c03308d4b479273a00c984733cf',
    'DOCUMENT_CONFLICT_NOTE': 'db61825a48f9e112918a719e789f3539dfcfa449f38fdfe3363c39492d5860dd',
    'documented_values': 'c55c926254ca605115cb259336e9efc3d4fa518745f441f912e9324037b7d162',
    'USER_CONFLICT_NOTE': '5d601bf7697e0775581c3212495b119a0dfe41d5cce4a830061776f1dac2f062',
    '_USER_CONFLICT_PREFIX': '53dd730afb08ccf23cdc4b763607cb7aab37f3ec4ca665f354797e4faf0a9428',
    'USER_ELSEWHERE_NOTE': '4291031a72722f6f5be183820549134017c91da0a4d9ce7f87b03eda24bfed0a',
    'USER_BIRTH_NOTE': '6cb34683ee361886678370e078f3012b2d926ee05d4dd2827d4d5450b8a6032b',
    'is_member_conflict': '0ee67e4b68aac32b856bc1fb0e522c56704e5e9e3e84a7df212f02c34c010795',
}
PREDICATES = ('charge_date_problem', 'charge_date_own', 'documented_values', 'is_member_conflict')
# The studio modules context_facts may import (FINAL.md 3.1: it may call studio.types; it never calls studio.gi).
ALLOWED_STUDIO_IMPORTS = {'studio.types'}


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding='utf-8'), filename=str(path))


def _top_level_definitions(path: Path) -> dict:
    """{name: its source lines} for every module-level function and assignment of ``path``."""
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    out = {}
    for node in _tree(path).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out[node.name] = ''.join(lines[node.lineno - 1:node.end_lineno])
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name):
                        out[name.id] = ''.join(lines[node.lineno - 1:node.end_lineno])
    return out


def _imported_modules(path: Path) -> set:
    """Every module an import statement anywhere in ``path`` names (relative imports resolved within studio)."""
    out = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            out |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            package = 'studio' if node.level else ''
            for _ in range(max(node.level - 1, 0)):
                package = package.rpartition('.')[0]
            module = '.'.join(part for part in (package, node.module or '') if part)
            out.add(module)
            out |= {f'{module}.{alias.name}' for alias in node.names}  # "from studio import gi" names studio.gi
    return out


def _code_objects(code):
    yield code
    for const in code.co_consts:
        if hasattr(const, 'co_code'):
            yield from _code_objects(const)


class IdentityTests(SimpleTestCase):
    def test_every_rehomed_name_is_the_same_object(self):
        for name in REHOMED:
            with self.subTest(name=name):
                self.assertIs(getattr(gi_context, name), getattr(context_facts, name))

    def test_gi_context_imports_back_exactly_the_rehomed_names(self):
        tree = _tree(CONTEXT_PY)
        found = [node for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
                 and (node.module or '').endswith('context_facts')]
        self.assertEqual(len(found), 1, 'one import of studio.context_facts')
        node = found[0]
        self.assertIn(node, tree.body, 'a module-level import, so the names are bound when gi.context loads')
        self.assertEqual((node.module, node.level), ('studio.context_facts', 0))
        self.assertEqual(sorted((alias.name, alias.asname) for alias in node.names),
                         sorted((name, None) for name in REHOMED))

    def test_gi_context_defines_none_of_them(self):
        # a definition or assignment of a re-homed name anywhere in gi/context.py would be a second implementation (or
        # would rebind the module's name away from the one object); an import from elsewhere would too
        tree = _tree(CONTEXT_PY)
        defined = sorted((node.name, node.lineno) for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                         and node.name in REHOMED)
        stored = sorted((node.id, node.lineno) for node in ast.walk(tree)
                        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del))
                        and node.id in REHOMED)
        rebound = sorted((alias.asname or alias.name, node.lineno) for node in ast.walk(tree)
                         if isinstance(node, (ast.Import, ast.ImportFrom))
                         and not (getattr(node, 'module', None) or '').endswith('context_facts')
                         for alias in node.names if (alias.asname or alias.name) in REHOMED)
        declared_global = sorted((name, node.lineno) for node in ast.walk(tree)
                                 if isinstance(node, (ast.Global, ast.Nonlocal))
                                 for name in node.names if name in REHOMED)
        self.assertEqual(defined, [])
        self.assertEqual(stored, [])
        self.assertEqual(rebound, [])
        self.assertEqual(declared_global, [])

    def test_the_existing_importers_hold_the_one_object(self):
        # FINAL.md 4.4: every existing importer keeps working unchanged. The legacy modules no slice edits bind them at
        # load (checks.py:17, engine.py:19, reconcile.py:25); the consumers later slices rewire are held to the same
        # object wherever they still bind one of these names.
        from studio import progress, reports, review, serializers
        from studio.validation import checks, engine, reconcile
        for module, names in ((checks, ('charge_date_problem', 'is_member_conflict')),
                              (engine, ('is_member_conflict',)), (reconcile, ('is_member_conflict',))):
            for name in names:
                with self.subTest(module=module.__name__, name=name):
                    self.assertIs(getattr(module, name), getattr(context_facts, name))
        for module in (progress, reports, review, serializers):
            for name in REHOMED:
                if hasattr(module, name):
                    with self.subTest(module=module.__name__, name=name):
                        self.assertIs(getattr(module, name), getattr(context_facts, name))


class HomeTests(SimpleTestCase):
    def test_the_code_lives_in_context_facts(self):
        home = FACTS_PY.resolve()
        for name in PREDICATES:
            function = getattr(context_facts, name)
            with self.subTest(name=name):
                self.assertEqual(function.__module__, 'studio.context_facts')
                files = {Path(code.co_filename).resolve() for code in _code_objects(function.__code__)}
                self.assertEqual(files, {home})  # the function, its lambda and its generator expression alike

    def test_context_facts_imports_nothing_from_studio_gi(self):
        modules = _imported_modules(FACTS_PY)
        self.assertEqual(sorted(m for m in modules if m == 'studio.gi' or m.startswith('studio.gi.')), [])
        studio_modules = [m for m in modules if m.split('.')[0] == 'studio' and m != 'studio']
        self.assertEqual(sorted(m for m in studio_modules
                                if not any(m == ok or m.startswith(ok + '.') for ok in ALLOWED_STUDIO_IMPORTS)), [])
        names = {node.id for node in ast.walk(_tree(FACTS_PY)) if isinstance(node, ast.Name)}
        names |= {node.attr for node in ast.walk(_tree(FACTS_PY)) if isinstance(node, ast.Attribute)}
        self.assertEqual(names & {'__import__', 'importlib', 'import_module'}, set())  # no import by name either

    def test_importing_context_facts_loads_no_legacy_module(self):
        # a fresh interpreter (isolated: no PYTHONPATH, no user site) imports the module alone; what it loaded of studio
        # is the module and, at most, studio.types - never studio.gi, so nothing the module imports reaches the legacy
        # reader either
        code = ('import sys; sys.path.insert(0, sys.argv[1]); import studio.context_facts; '
                "print(' '.join(sorted(m for m in sys.modules if m.startswith('studio.'))))")
        done = subprocess.run([sys.executable, '-I', '-B', '-c', code, str(APP)], capture_output=True, text=True,
                              timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        loaded = set(done.stdout.split())
        self.assertIn('studio.context_facts', loaded)
        self.assertEqual(sorted(loaded - {'studio.context_facts'} - ALLOWED_STUDIO_IMPORTS), [])

    def test_a_call_executes_no_code_of_studio_gi(self):
        # every Python frame a call opens - the predicate, its lambda, its generator expression - is in context_facts.py
        listed = context_facts.DOCUMENT_CONFLICT_NOTE + '2026-10-05, 2026-10-07.'
        facts = [None, {}, Fact('service_date', '2026-10-07', 'document'),
                 Fact('service_date', None, 'conflict', (), listed),
                 {'origin': 'conflict', 'value': None, 'evidence': [],
                  'note': context_facts.USER_CONFLICT_NOTE.format(user='2026-10-09', document='2026-10-07')},
                 {'origin': 'conflict', 'value': None, 'evidence': [], 'note': context_facts.CHARGE_DATE_NOTE.format(
                     heading='“Charges:”', block='“DOS 10/05/2026”', value='2026-10-07', own='“DOS: 10/07/2026”')}]
        files = set()

        def tracer(frame, event, arg):
            if event == 'call':
                files.add(frame.f_code.co_filename)
            return None

        previous = sys.gettrace()
        sys.settrace(tracer)
        try:
            for fact in facts:
                for name in PREDICATES:
                    if name != 'documented_values' or not isinstance(fact, dict):
                        getattr(gi_context, name)(fact)
        finally:
            sys.settrace(previous)
        self.assertEqual({Path(f).resolve() for f in files}, {FACTS_PY.resolve()})


class VerbatimTests(SimpleTestCase):
    def test_every_definition_is_the_legacy_text_byte_for_byte(self):
        definitions = _top_level_definitions(FACTS_PY)
        self.assertEqual(sorted(definitions), sorted(REHOMED), 'context_facts defines exactly the re-homed names')
        for name, pinned in REHOMED.items():
            with self.subTest(name=name):
                self.assertEqual(hashlib.sha256(definitions[name].encode('utf-8')).hexdigest(), pinned)


class PredicateTests(SimpleTestCase):
    """The contract the legacy readers rely on, read through the one implementation (Fact and stored mapping alike)."""

    @staticmethod
    def both(origin, note, value=None):
        return (Fact('service_date', value, origin, (), note),
                {'value': value, 'origin': origin, 'evidence': [], 'note': note})

    def test_a_member_conflict_is_one_whose_note_opens_with_the_member_prefix(self):
        notes = (context_facts.USER_CONFLICT_NOTE.format(user='2026-10-09', document='2026-10-07'),
                 context_facts.USER_ELSEWHERE_NOTE.format(user='2026-10-09', document='“Next procedure: 10/09/2026”'),
                 context_facts.USER_BIRTH_NOTE.format(user='1998-01-01', document='“DOS: 01/01/1998”'))
        for note in notes:
            for fact in self.both('conflict', note):
                with self.subTest(note=note[:70], kind=type(fact).__name__):
                    self.assertTrue(context_facts.is_member_conflict(fact))
                    self.assertIsNone(context_facts.charge_date_problem(fact))
                    self.assertIsNone(context_facts.charge_date_own(fact))
            self.assertFalse(context_facts.is_member_conflict(self.both('user', note)[1]))
        listed = context_facts.DOCUMENT_CONFLICT_NOTE + '2026-10-05, 2026-10-07.'
        for fact in (None, {}, *self.both('conflict', listed), *self.both('conflict', ''), *self.both('conflict', None),
                     *self.both('document', '', '2026-10-07')):
            with self.subTest(fact=fact):
                self.assertFalse(context_facts.is_member_conflict(fact))

    def test_a_charge_question_states_its_problem_and_keeps_the_installed_date(self):
        cases = (
            (context_facts.CHARGE_DATE_NOTE.format(heading='“Charges:”', block='“DOS 10/05/2026”', value='2026-10-07',
                                                   own='“Date of service: 10/07/2026”'),
             "The lines from “Charges:” to the document's end state “DOS 10/05/2026”, while 2026-10-07 is read from "
             '“Date of service: 10/07/2026”'),
            (context_facts.WIDE_DATE_ASK_NOTE.format(wide='“Exam date: 10/05/2026”', value='2026-10-07',
                                                     own='“DOS: 10/07/2026”'),
             'The document also states “Exam date: 10/05/2026”, while 2026-10-07 is read from “DOS: 10/07/2026”'),
            # a quote that holds the marker comes before the note's own: the last marker is the note's
            (context_facts.CHARGE_DATE_NOTE.format(heading='“Billing: x, while 2026-01-01 is read from y”',
                                                   block='“DOS 10/05/2026”', value='2026-10-07',
                                                   own='“DOS: 10/07/2026”'),
             "The lines from “Billing: x, while 2026-01-01 is read from y” to the document's end state "
             '“DOS 10/05/2026”, while 2026-10-07 is read from “DOS: 10/07/2026”'),
        )
        for note, problem in cases:
            for fact in self.both('conflict', note):
                with self.subTest(note=note[:70], kind=type(fact).__name__):
                    self.assertEqual(context_facts.charge_date_problem(fact), problem)
                    self.assertEqual(context_facts.charge_date_own(fact), '2026-10-07')
                    self.assertFalse(context_facts.is_member_conflict(fact))
            for fact in self.both('document', note, '2026-10-07'):  # only a question (origin 'conflict') asks
                self.assertIsNone(context_facts.charge_date_problem(fact))
                self.assertIsNone(context_facts.charge_date_own(fact))

    def test_a_document_conflict_lists_its_values(self):
        note = context_facts.DOCUMENT_CONFLICT_NOTE + '2026-10-05, 2026-10-07.'
        self.assertEqual(context_facts.documented_values(Fact('service_date', None, 'conflict', (), note)),
                         ('2026-10-05', '2026-10-07'))
        for fact in (Fact('service_date', '2026-10-05', 'document', (), note),
                     Fact('service_date', None, 'conflict', (), note[:-1]),
                     Fact('service_date', None, 'conflict', (), context_facts.USER_CONFLICT_NOTE.format(
                         user='2026-10-09', document='2026-10-05 or 2026-10-07')),
                     None):
            with self.subTest(fact=fact):
                self.assertEqual(context_facts.documented_values(fact), ())
