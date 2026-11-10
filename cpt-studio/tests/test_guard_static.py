"""The static backstops of the call guard (Gemini migration slice S12; design/FINAL.md 10.1 and 10.4(5), as
design/ADJUDICATION.md R-5 amends them; DECISIONS D17). Read from the source, never run: what the runtime matrix
(tests/test_guard_matrix_new_path.py) cannot see is a reference no world it builds reaches.

The rules, each judged over a scoped reading of every reference (``references``: imports, and loads through a name an
import bound in that scope - a parameter or a local of the same name shadows it, as Python's own scoping does: a
comprehension's targets are its own, a function or comprehension nested in a class reads past the class's names, and a
class body's own binding is never trusted to shadow, the safe way round), and each only about the modules the sentinel
denies (studio.gi but its reference tables, studio.validation's engine, reconcile, review_view and rationale,
studio.candidates, and studio.validation.checks by function):
- THE NEW PACKAGE (studio/interpretation/*): of studio.gi only the reference tables gi.profiles and gi.catalogue - never
  gi.context: the re-homed predicates are studio.context_facts' (S04), and the new code imports them from there; of
  studio.validation.checks only FINAL 7.1's names (R-5: an allowlist, without incomplete_check, R-4); of the other
  denied modules only the constants FINAL 10.1 allows (NEW_CONSTANTS: the three it names, and review_view's View,
  Stored and Decided - the dataclasses the overlay returns, whose generated code is no denied code); and no cue constant
  at all (a name ending _CUE or _CUES, LISTED_*, FAILED_ATTEMPT, HYPOTHETICAL_*, or a compiled pattern - Engine B's cue
  scan). Two pinned exceptions, each a design fact: readers.LegacyReader's own calls of the legacy overlay (FINAL 8.2:
  today's calls, moved verbatim, run labelled legacy_record) and the dynamic imports DYNAMIC names (the sentinel's own
  pinned deny list, R-1; normalize's linked S03 steps).
- THE NEW JOBS BRANCHES (studio/jobs.py): outside the archived legacy stages (sentinel.ARCHIVED_JOBS, denied whole), a
  function refers to the denied modules only through the re-homed objects (a gi.context name that IS context_facts'
  object), FINAL 7.1's checks and the constants JOBS_CONSTANTS names - or a pinned legacy branch
  (JOBS_LEGACY_REFERENCES);
  and only the pinned call sites (LEGACY_CALL_SITES, each on a branch this image refuses: jobs._refuse_legacy_context,
  jobs._legacy_reading_allowed) name an archived stage or a legacy branch (JOBS_LEGACY_BRANCHES). Importing the modules
  at load is not calling them (D17).
- THE EDITED CONSUMERS (R-5): of studio.validation.checks only FINAL 7.1's names - or a pinned legacy branch
  (CONSUMER_LEGACY_CHECKS), or a name pinned to its consumer with why it is no reading (CONSUMER_CHECKS_NAMES: review's
  modifier options, reports' fact labels); no cue constant of any denied module (CONSUMER_CUE_NAMES pins the one wording
  string the cue scan misreads by its name); no import by a computed name but the two CONSUMER_DYNAMIC pins.
- THE DENY SET'S SIZE is pinned per module (FINAL 10.4(5)), named here again.
Every pin is used (a stale one fails), and every rule refuses a planted control, so none of them passes by reading
nothing.
"""
from __future__ import annotations

import ast
import importlib
import re
from collections import namedtuple
from pathlib import Path

from django.test import SimpleTestCase

from studio import context_facts
from studio.gi import context as gi_context
from studio.interpretation import sentinel
from studio.validation import checks

APP = Path(__file__).resolve().parents[1]
PACKAGE = APP / 'studio' / 'interpretation'
JOBS = APP / 'studio' / 'jobs.py'
LEGACY_ROOTS = ('studio.gi', 'studio.validation', 'studio.candidates')
REFERENCE_TABLES = ('studio.gi.profiles', 'studio.gi.catalogue')
DENIED_MODULES = tuple(name for name in sentinel.DENY_MODULES if not name.startswith('studio.gi'))
CHECKS = sentinel.CHECKS_MODULE
CUE = re.compile(r'(?:_CUES?$|^LISTED_|^FAILED_ATTEMPT$|^HYPOTHETICAL_)')
CONSUMERS = ('review', 'answers', 'progress', 'customer_api', 'serializers', 'reports', 'api', 'operator', 'apps',
             'views')
# FINAL 10.1's constants of the denied modules the new package may reference, each with why it is no reading. Today the
# package references only review_view's dataclasses; it copies the three FINAL names (combination.py, coverage.py,
# pinned equal by their own tests), which may be referenced instead.
NEW_CONSTANTS = {
    'studio.validation.review_view.View': "the overlay's return type (FINAL 3.1: building a View runs dataclass code)",
    'studio.validation.review_view.Stored': "the overlay's stored-row type (dataclass)",
    'studio.validation.review_view.Decided': "the overlay's decision type (dataclass)",
    'studio.validation.engine.DISTINCT_LESION_KINDS': 'FINAL 10.1: the acts a separate-lesion review concerns',
    'studio.validation.engine.SECOND_REVIEW_CHECKED': 'FINAL 10.1: how many unresolved items a second review checks',
    'studio.validation.reconcile.REMOVAL_KINDS': 'FINAL 10.1: the removal act kinds',
}
# FINAL 8.2: LegacyReader's methods are today's calls, moved verbatim - the legacy overlay serving the legacy records
LEGACY_READER = {'studio.validation.review_view', 'studio.validation.review_view.stored_from',
                 'studio.validation.review_view.review_view', 'studio.validation.review_view.Decided',
                 'studio.validation.engine', 'studio.validation.engine.reviewed_completeness'}
# the new package's dynamic imports: (module, scope) -> why
DYNAMIC = {
    ('sentinel', '_import_deny_modules'): 'R-1: install() imports the pinned deny list itself, to walk its code',
    ('normalize', 'normalize'): "normalize's linked steps: the S03 modules LINKED_STEPS names",
}
# jobs.py: the legacy chain's own branches, reached only on a legacy context, which this image refuses unless
# jobs._legacy_reading_allowed (the test-only legacy chain: FINAL 16.14)
JOBS_LEGACY_BRANCHES = {
    '_record_context': "the legacy analyze's context record (tests/legacy_chain.py's legacy_stage_analyze)",
    '_remade_context': "the legacy remake of an earlier gi-context version (tests/legacy_chain.py's _earlier_reading)",
}
# the call sites that name an archived stage or a legacy branch, each behind this image's refusal of a legacy context
LEGACY_CALL_SITES = {
    ('stage_predict', '_route_child'): "the legacy router for a legacy context's date, after _refuse_legacy_context",
    ('stage_assess', '_assess_child'): 'the legacy child for a legacy context, after _refuse_legacy_context',
    ('stage_assess', '_remade_context'): 'the legacy remake for a legacy context, after _refuse_legacy_context',
    ('_change_context', 'make_context'): 'the legacy context save, only when _legacy_reading_allowed',
    ('_record_context', '_merged_facts'): 'within the legacy branch _record_context',
    ('_remade_context', 'make_context'): 'within the legacy branch _remade_context',
}
JOBS_LEGACY_REFERENCES = {
    ('_record_context', 'studio.gi.context.document_service_date_fact'): "the legacy analyze's document date",
}
# checks.py constants jobs.py names: labels and wording, none a pattern (asserted)
JOBS_CONSTANTS = {
    'studio.validation.checks.CONFIRMATION_SOURCE': 'the source label of a confirmed finding (a peer request reason)',
    'studio.validation.checks.CONFIRMED_HEADING': 'the heading of a confirmed finding (a peer request reason)',
    'studio.validation.checks.MEMBER_ENTERED': 'the clause a member-entered value is worded with',
}
# R-5 in the edited consumers: a reference to a checks function outside the allowlist, on a legacy branch, with why
CONSUMER_LEGACY_CHECKS = {
    ('serializers', 'corti_unlisted_words', 'unlisted_codes'): "a legacy assessment's unlisted-code sentence; a "
                                                               'new-path one is worded by interpretation.wording (S11)',
}
# R-5: of checks.py the edited consumers name FINAL 7.1's names only - and these, each pinned to its consumer with why
# it is no reading (the review of S12, finding 2: the rule had let through every helper the allowlist reaches and every
# constant that is no pattern - the legacy reader's word lists among them, string sets no runtime count sees):
# (module, name) -> why
CONSUMER_CHECKS_NAMES = {
    ('review', 'DISTINCT_LESION_OPTIONS'): "the two modifiers ('59', 'XS') a reviewer's chosen modifier is checked "
                                           'against (review._chosen_modifiers): a constant pair of modifier codes',
    ('reports', 'fact_label'): "a fact's display label in the reports (checks.FACT_LABELS by the fact's name): "
                               'wording, and a helper FINAL 7.1 reaches, so never denied',
}
# a name the cue scan (FINAL 10.1) reads as a cue constant, which an edited consumer names and which is none - pinned
# with why: (module, target) -> why
CONSUMER_CUE_NAMES = {
    ('reports', 'studio.validation.engine.LISTED_NOT_PROPOSED'): "a wording string (the reports' clause for a code a "
                                                                 'reader listed with no quote), never a pattern: only '
                                                                 'its name begins LISTED_',
}
# an edited consumer's import by a name it computes, pinned with what it imports - none a module the sentinel denies
# (asserted): (module, scope) -> why
CONSUMER_DYNAMIC = {
    ('review', 'estimated_cost'): "the pricing module, review.PRICING_MODULE ('studio.participants.pricing')",
    ('operator', '_as_an_unknown_url'): "Django's session engine (settings.SESSION_ENGINE)",
}
# FINAL 10.4(5): "the deny set's size is pinned per module" - named here again, so shrinking it takes an edit of both
SIZES = {'studio/gi/__init__.py': 0, 'studio/gi/clauses.py': 31, 'studio/gi/context.py': 219, 'studio/gi/cues.py': 14,
         'studio/gi/detect.py': 766, 'studio/gi/purpose.py': 5, 'studio/gi/sections.py': 71,
         'studio/gi/services.py': 456, 'studio/gi/structure.py': 152, 'studio/validation/engine.py': 452,
         'studio/validation/reconcile.py': 107, 'studio/validation/review_view.py': 45,
         'studio/validation/rationale.py': 7, 'studio/candidates.py': 45, 'studio/validation/checks.py': 164,
         'studio/jobs.py': 5}

Ref = namedtuple('Ref', 'scope target kind line')


# --- the scoped reading ----------------------------------------------------------------------------------------------

COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _walrus(node) -> set:
    """The names the assignment expressions inside a comprehension bind: the scope around it binds them (PEP 572),
    through nested comprehensions, never through a nested function or lambda."""
    names = set()

    def walk(item):
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        if isinstance(item, ast.NamedExpr) and isinstance(item.target, ast.Name):
            names.add(item.target.id)
        for child in ast.iter_child_nodes(item):
            walk(child)

    walk(node)
    return names


def _bound(node) -> set:
    """The names a function, lambda or class body binds of its own (parameters, assignments, loop, with and walrus
    targets, handlers, nested definitions, imports), not descending into nested scopes - a comprehension is one: its
    targets are its own (the review of S12, finding 5), and only a walrus inside it binds here; global and nonlocal
    names are the enclosing scopes'."""
    names, outer = set(), set()
    args = getattr(node, 'args', None)
    if isinstance(args, ast.arguments):
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg):
            if arg is not None:
                names.add(arg.arg)
    body = node.body if isinstance(node.body, list) else [node.body]

    def walk(item):
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(item.name)
            return
        if isinstance(item, ast.Lambda):
            return
        if isinstance(item, COMPREHENSIONS):
            names.update(_walrus(item))
            return
        if isinstance(item, (ast.Global, ast.Nonlocal)):
            outer.update(item.names)
        elif isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del)):
            names.add(item.id)
        elif isinstance(item, ast.ExceptHandler) and item.name:
            names.add(item.name)
        elif isinstance(item, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split('.')[0] for alias in item.names)
        for child in ast.iter_child_nodes(item):
            walk(child)

    for statement in body:
        walk(statement)
    return names - outer


class _Finder(ast.NodeVisitor):
    def __init__(self, package: str):
        self.package = package
        # per scope: (import aliases: name -> target, names it binds otherwise, its kind)
        self.scopes = [({}, set(), 'module')]
        self.where = []
        self.found = []

    def _record(self, target, kind, node):
        if kind == 'dynamic' or any(target == root or target.startswith(root + '.') for root in LEGACY_ROOTS):
            self.found.append(Ref('.'.join(self.where) or '<module>', target, kind, getattr(node, 'lineno', 0)))

    def _lookup(self, name):
        """What ``name`` names here, by Python's rules: the innermost scope, then the enclosing ones - but never a class
        body's names from a scope nested in it (a method or a comprehension reads past its class to the module). A class
        body's own binding is not trusted to shadow at all, the safe way round: its statements read a name before its
        assignment from the module."""
        for depth, (aliases, bound, kind) in enumerate(reversed(self.scopes)):
            if kind == 'class' and depth:
                continue
            if name in aliases:
                return aliases[name]
            if name in bound and kind != 'class':
                return None
        return None

    def _alias(self, name, target):
        aliases, bound, _ = self.scopes[-1]
        aliases[name] = target
        bound.discard(name)

    def visit_Import(self, node):
        for alias in node.names:
            self._record(alias.name, 'import', node)
            head = alias.name.split('.')[0]
            self._alias(alias.asname or head, alias.name if alias.asname else head)

    def visit_ImportFrom(self, node):
        base = node.module or ''
        if node.level:
            parts = self.package.split('.')
            base = '.'.join(parts[:len(parts) - node.level + 1] + ([node.module] if node.module else []))
        for alias in node.names:
            target = f'{base}.{alias.name}' if base else alias.name
            self._record(target, 'import', node)
            self._alias(alias.asname or alias.name, target)

    def _scope(self, node, name):
        for decorator in getattr(node, 'decorator_list', ()):
            self.visit(decorator)
        args = getattr(node, 'args', None)
        if isinstance(args, ast.arguments):
            for default in (*args.defaults, *[item for item in args.kw_defaults if item is not None]):
                self.visit(default)
        self.scopes.append(({}, _bound(node), 'class' if isinstance(node, ast.ClassDef) else 'function'))
        self.where.append(name)
        for statement in (node.body if isinstance(node.body, list) else [node.body]):
            self.visit(statement)
        self.where.pop()
        self.scopes.pop()

    def visit_FunctionDef(self, node):
        self._scope(node, node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        for base in node.bases:
            self.visit(base)
        self._scope(node, node.name)

    def visit_Lambda(self, node):
        self._scope(node, '<lambda>')

    def _comprehension(self, node):
        """A comprehension's own scope (its targets bound there; the review of S12, finding 5), its first iterable read
        in the scope around it, as Python reads it. Its references keep the enclosing function's name."""
        self.visit(node.generators[0].iter)
        targets = {item.id for generator in node.generators for item in ast.walk(generator.target)
                   if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
        self.scopes.append(({}, targets, 'comprehension'))
        for number, generator in enumerate(node.generators):
            if number:
                self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)
        for element in ((node.key, node.value) if isinstance(node, ast.DictComp) else (node.elt,)):
            self.visit(element)
        self.scopes.pop()

    visit_ListComp = visit_SetComp = visit_DictComp = visit_GeneratorExp = _comprehension

    def visit_Attribute(self, node):
        chain, base = [], node
        while isinstance(base, ast.Attribute):
            chain.append(base.attr)
            base = base.value
        if isinstance(base, ast.Name) and isinstance(node.ctx, ast.Load):
            target = self._lookup(base.id)
            if target is not None:
                self._record(f'{target}.{chain[-1]}', 'use', node)
                return
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            target = self._lookup(node.id)
            if target is not None:
                self._record(target, 'use', node)

    def visit_Call(self, node):
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ''
        if name in ('import_module', '__import__') and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                self._record(argument.value, 'import', node)
            else:
                self._record(ast.unparse(argument), 'dynamic', node)
        self.generic_visit(node)


def references(source: str, package: str) -> list:
    """Every Ref ``source`` makes to studio.gi, studio.validation or studio.candidates (``package``: what its relative
    imports resolve against), and every dynamic import (kind 'dynamic', its argument's source)."""
    finder = _Finder(package)
    finder.visit(ast.parse(source))
    return finder.found


def _under(target: str, module: str) -> bool:
    return target == module or target.startswith(module + '.')


def _name(target: str, module: str) -> str:
    """The first name below ``module`` that ``target`` names ('' for the module itself)."""
    return target[len(module) + 1:].split('.')[0] if target.startswith(module + '.') else ''


def denied(target: str) -> bool:
    """Whether ``target`` lies in a module the sentinel denies (whole, or checks.py by function)."""
    if any(_under(target, table) for table in REFERENCE_TABLES):
        return False
    return _under(target, 'studio.gi') or _under(target, CHECKS) or any(_under(target, name) for name in DENIED_MODULES)


def _object(target: str):
    """The live object ``target`` names (a module's attribute), or None."""
    module, _, name = target.rpartition('.')
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError, ValueError):
        return None


def _patterns(value, depth=0) -> bool:
    if isinstance(value, re.Pattern):
        return True
    if depth < 4 and isinstance(value, (tuple, list, set, frozenset)):
        return any(_patterns(item, depth + 1) for item in value)
    if depth < 4 and isinstance(value, dict):
        return any(_patterns(item, depth + 1) for item in value.values())
    return False


def cue(target: str) -> bool:
    """A cue constant (FINAL 10.1): a name ending _CUE or _CUES, LISTED_*, FAILED_ATTEMPT, HYPOTHETICAL_*, or a compiled
    pattern (or a container of them)."""
    return bool(CUE.search(target.rpartition('.')[2])) or _patterns(_object(target))


def rehomed(target: str) -> bool:
    """A gi.context name that IS studio.context_facts' object (S04's re-homing, identity preserved)."""
    name = _name(target, 'studio.gi.context')
    return (bool(name) and hasattr(context_facts, name)
            and getattr(gi_context, name, None) is getattr(context_facts, name))


# --- the rules -------------------------------------------------------------------------------------------------------

def new_package_violations(module: str, refs, used=None) -> list:
    """What breaks the new package's rule in the references of ``module`` (a studio/interpretation module's stem).
    ``used``: a set the pins this reading met are added to."""
    used = set() if used is None else used
    out = []
    for ref in refs:
        target, scope = ref.target, ref.scope
        where = f'{module}.{scope}:{ref.line}'
        if ref.kind == 'dynamic':
            if (module, scope) in DYNAMIC:
                used.add((module, scope))
            else:
                out.append(f'{where} imports by a name it computes ({target})')
            continue
        if cue(target):  # whichever module holds it: the reference tables and questions.py too
            out.append(f'{where} names the cue constant {target}')
            continue
        if not denied(target):
            continue
        if module == 'readers' and scope.startswith('LegacyReader.') and target in LEGACY_READER:
            used.add(target)
            continue
        if _under(target, 'studio.gi'):
            why = ' (a re-homed name: import it from studio.context_facts)' if rehomed(target) else ''
            out.append(f'{where} names {target}{why}')
        elif _under(target, CHECKS):
            name = _name(target, CHECKS)
            if name and name not in sentinel.CHECKS_ALLOWLIST + sentinel.CHECKS_ALLOWLIST_CONSTANTS:
                out.append(f'{where} names {target}, which is not a FINAL 7.1 check')
        elif target in NEW_CONSTANTS:
            used.add(target)
        else:
            out.append(f'{where} names {target}')
    return out


def jobs_violations(source: str, used=None) -> list:
    """What breaks the new jobs branches' rule in ``source`` (studio/jobs.py's text). ``used``: as above."""
    used = set() if used is None else used
    out = []
    tree = ast.parse(source)
    for ref in references(source, 'studio'):
        top = ref.scope.split('.')[0]
        target = ref.target
        if top in sentinel.ARCHIVED_JOBS or (ref.kind == 'import' and ref.scope == '<module>') or not denied(target):
            continue  # an archived stage is denied whole; importing at load is not calling (D17)
        where = f'jobs.{ref.scope}:{ref.line}'
        if (top, target) in JOBS_LEGACY_REFERENCES:
            used.add((top, target))
        elif target in JOBS_CONSTANTS:
            used.add(target)
            if cue(target) or callable(_object(target)):
                out.append(f'{where} names {target}, which is no plain constant')
        elif rehomed(target):
            continue
        elif _under(target, CHECKS) and _name(target, CHECKS) in sentinel.CHECKS_ALLOWLIST:
            continue
        elif ref.kind == 'import' and target in ('studio.gi', 'studio.validation'):
            continue
        else:
            out.append(f'{where} names {target}')
    functions = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    legacy_only = (set(sentinel.ARCHIVED_JOBS) | set(JOBS_LEGACY_BRANCHES)) & functions
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name in sentinel.ARCHIVED_JOBS:
            continue
        local = _bound(node)
        for item in ast.walk(node):
            if (isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id in legacy_only
                    and item.id not in local):
                if (node.name, item.id) in LEGACY_CALL_SITES:
                    used.add((node.name, item.id))
                else:
                    out.append(f'jobs.{node.name}:{item.lineno} names the legacy-only {item.id}')
    return out


def consumer_violations(module: str, refs, used=None) -> list:
    """R-5 in an edited consumer: of checks.py only FINAL 7.1's names, a pinned legacy branch (CONSUMER_LEGACY_CHECKS)
    or a pinned name of its own (CONSUMER_CHECKS_NAMES); no cue constant of any denied module (the cue scan, as for the
    new package; CONSUMER_CUE_NAMES pins a name it misreads); and no import by a computed name, which no reading of the
    source can judge (CONSUMER_DYNAMIC pins the two it meets). ``used``: as above."""
    used = set() if used is None else used
    final = set(sentinel.CHECKS_ALLOWLIST) | set(sentinel.CHECKS_ALLOWLIST_CONSTANTS)
    out = []
    for ref in refs:
        where = f'{module}.{ref.scope}:{ref.line}'
        if ref.kind == 'dynamic':
            if (module, ref.scope) in CONSUMER_DYNAMIC:
                used.add((module, ref.scope))
            else:
                out.append(f'{where} imports by a name it computes ({ref.target})')
            continue
        if cue(ref.target):
            if (module, ref.target) in CONSUMER_CUE_NAMES:
                used.add((module, ref.target))
            else:
                out.append(f'{where} names the cue constant {ref.target}')
            continue
        if not _under(ref.target, CHECKS) or ref.target == CHECKS:
            continue
        name = _name(ref.target, CHECKS)
        branch = (module, ref.scope.split('.')[0], name)
        if branch in CONSUMER_LEGACY_CHECKS:
            used.add(branch)
        elif (module, name) in CONSUMER_CHECKS_NAMES:
            used.add((module, name))
        elif name not in final:
            out.append(f'{where} names {ref.target}, which R-5 does not allow')
    return out


def package_modules() -> dict:
    """{stem: source} of every module of studio/interpretation."""
    return {path.stem: path.read_text(encoding='utf-8') for path in sorted(PACKAGE.glob('*.py'))}


def imports_of(source: str) -> set:
    """Every module or name a source imports, whatever it is."""
    out = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            out |= {f'{node.module}.{alias.name}' for alias in node.names}
        elif isinstance(node, ast.Import):
            out |= {alias.name for alias in node.names}
    return out


# --- the tests -------------------------------------------------------------------------------------------------------

class NewPackageTests(SimpleTestCase):
    def test_the_new_package_names_nothing_of_the_legacy_reader_but_what_is_allowed(self):
        modules = package_modules()
        self.assertEqual(set(modules), {path.stem for path in PACKAGE.glob('*.py')})
        # every module of FINAL 3.1's plan is read, S01's to S11's
        self.assertLessEqual({'__init__', 'prompt', 'schema', 'read', 'store', 'literals', 'lexicon', 'normalize',
                              'verify', 'identity', 'relations', 'mapping', 'dates', 'adapter', 'replay', 'facts',
                              'events', 'coverage', 'combination', 'assess', 'wording', 'overlay', 'readers',
                              'holds', 'sentinel', 'report'}, set(modules))
        found, used, judged = [], set(), 0
        for stem, source in modules.items():
            refs = references(source, 'studio.interpretation')
            judged += sum(1 for ref in refs if denied(ref.target))
            found += new_package_violations(stem, refs, used)
        self.assertEqual(found, [])
        self.assertGreater(judged, 50)  # it read the package's checks, dataclass and legacy-reader references
        # every pin is met by a reference (none stale): the legacy reader's calls, the dataclasses, both dynamic imports
        self.assertEqual(used & set(DYNAMIC), set(DYNAMIC))
        self.assertLessEqual({'studio.validation.review_view.View', 'studio.validation.review_view.Stored',
                              'studio.validation.review_view.Decided'}, used)
        self.assertLessEqual({'studio.validation.review_view.stored_from', 'studio.validation.review_view.review_view',
                              'studio.validation.engine.reviewed_completeness'}, used)

    def test_the_new_code_imports_the_rehomed_predicates_from_context_facts(self):
        importers = {stem for stem, source in package_modules().items()
                     if any(_under(name, 'studio.context_facts') for name in imports_of(source))}
        self.assertTrue({'dates', 'assess'} <= importers, importers)
        for stem, source in package_modules().items():
            with self.subTest(module=stem):
                self.assertFalse([name for name in imports_of(source) if _under(name, 'studio.gi.context')])

    def test_every_allowed_constant_exists_and_is_no_cue_and_no_code(self):
        for target, why in NEW_CONSTANTS.items():
            with self.subTest(target=target):
                value = _object(target)
                self.assertTrue(why.strip())
                self.assertIsNotNone(value)
                self.assertFalse(cue(target))
                self.assertTrue(isinstance(value, type) or not callable(value))
        for target in ('studio.validation.review_view.View', 'studio.validation.review_view.Stored',
                       'studio.validation.review_view.Decided'):
            cls = _object(target)
            self.assertEqual(cls.__init__.__code__.co_filename, '<string>')  # dataclass-generated: never denied code
            self.assertNotIn(id(cls.__init__.__code__), sentinel.deny_set())
        for name in sentinel.CHECKS_ALLOWLIST_CONSTANTS:
            self.assertFalse(cue(f'{CHECKS}.{name}'))


class JobsTests(SimpleTestCase):
    def test_the_new_jobs_branches_name_nothing_of_the_legacy_reader(self):
        used = set()
        self.assertEqual(jobs_violations(JOBS.read_text(encoding='utf-8'), used), [])
        expected = set(LEGACY_CALL_SITES) | set(JOBS_LEGACY_REFERENCES) | set(JOBS_CONSTANTS)
        self.assertEqual(used, expected)  # no stale pin
        source = JOBS.read_text(encoding='utf-8')
        functions = {node.name for node in ast.parse(source).body if isinstance(node, ast.FunctionDef)}
        self.assertLessEqual(set(JOBS_LEGACY_BRANCHES) | set(sentinel.ARCHIVED_JOBS), functions)
        for target in JOBS_CONSTANTS:
            with self.subTest(target=target):
                self.assertIsInstance(_object(target), str)

    def test_the_rehomed_objects_it_names_are_context_facts_own(self):
        names = {ref.target for ref in references(JOBS.read_text(encoding='utf-8'), 'studio')
                 if _under(ref.target, 'studio.gi.context') and ref.scope != '<module>'
                 and ref.scope.split('.')[0] not in sentinel.ARCHIVED_JOBS}
        rehomed_names = {name for name in names if rehomed(name)}
        self.assertIn('studio.gi.context.is_member_conflict', rehomed_names)
        self.assertEqual(names - rehomed_names, {'studio.gi.context.document_service_date_fact'})  # the legacy branch's
        self.assertIs(gi_context.is_member_conflict, context_facts.is_member_conflict)


class ConsumerTests(SimpleTestCase):
    def test_the_edited_consumers_name_only_allowed_checks(self):
        found, used, judged = [], set(), 0
        for stem in CONSUMERS:
            source = (APP / 'studio' / f'{stem}.py').read_text(encoding='utf-8')
            refs = references(source, 'studio')
            judged += sum(1 for ref in refs if _under(ref.target, CHECKS))
            found += consumer_violations(stem, refs, used)
        self.assertEqual(found, [])
        self.assertEqual(used, set(CONSUMER_LEGACY_CHECKS) | set(CONSUMER_CHECKS_NAMES) | set(CONSUMER_CUE_NAMES)
                         | set(CONSUMER_DYNAMIC))  # no stale pin
        self.assertGreater(judged, 3)

    def test_each_pinned_name_is_no_reading(self):
        status = sentinel.install()
        self.assertEqual(status['state'], 'ok', status['reason'])
        denied_codes = sentinel.deny_set()
        self.assertIn(id(checks.status_check.__code__), denied_codes)  # the control: the deny set is armed
        for (module, name), why in CONSUMER_CHECKS_NAMES.items():
            with self.subTest(pin=(module, name)):
                value = getattr(checks, name)
                self.assertIn(module, CONSUMERS)
                self.assertTrue(why.strip())
                self.assertNotIn(name, sentinel.CHECKS_ALLOWLIST + sentinel.CHECKS_ALLOWLIST_CONSTANTS)
                self.assertFalse(cue(f'{CHECKS}.{name}'))
                if callable(value):  # a helper the allowlist reaches through checks.py's own calls: never denied
                    self.assertIn(name, sentinel.CHECKS_ALLOWED_HELPERS)
                    self.assertNotIn(id(value.__code__), denied_codes)
                else:
                    self.assertFalse(_patterns(value))
        for (module, target), why in CONSUMER_CUE_NAMES.items():
            with self.subTest(pin=(module, target)):
                self.assertIn(module, CONSUMERS)
                self.assertTrue(why.strip())
                self.assertIsInstance(_object(target), str)  # a plain string: never a pattern, nor a container of one
        from django.conf import settings

        computed = (importlib.import_module('studio.review').PRICING_MODULE, settings.SESSION_ENGINE)
        self.assertEqual(computed[0], 'studio.participants.pricing')
        self.assertFalse([name for name in computed
                          if denied(name) or any(_under(name, root) for root in LEGACY_ROOTS)])


class DenySetPinTests(SimpleTestCase):
    def test_the_deny_set_size_is_pinned_per_module(self):
        status = sentinel.install()
        self.assertEqual(status['state'], 'ok', status['reason'])
        self.assertEqual(sentinel.PINNED_SIZES, SIZES)
        self.assertEqual(status['sizes'], SIZES)
        self.assertEqual((status['deny_size'], sentinel.DENY_SIZE), (sum(SIZES.values()), sum(SIZES.values())))
        self.assertTrue(all(SIZES[key] > 0 for key in SIZES if key != 'studio/gi/__init__.py'))


class PlantedTests(SimpleTestCase):
    """Each rule refuses a planted violation of each form, and passes what it allows - so no rule passes by reading
    nothing, and the scoping is Python's (a parameter named like a module is not the module)."""

    def test_the_new_package_rule_refuses_each_form(self):
        planted = ('from studio.gi import context\n'
                   'from studio.gi.context import is_member_conflict\n'
                   'from studio.gi import cues, profiles, catalogue\n'
                   'import studio.gi.detect as detect\n'
                   'from studio.validation.checks import evidence_readings, code_scope\n'
                   'from studio.validation import checks as c, questions\n'
                   'from studio.validation import reconcile\n'
                   'from studio.candidates import candidates\n'
                   'from studio.validation.review_view import View, stored_from\n'
                   'def f(text):\n'
                   '    c.status_check(text)\n'
                   '    c.exact_evidence(text)\n'
                   '    reconcile.FAILED_ATTEMPT.search(text)\n'
                   '    return detect.route(text, None)\n'
                   'def g(checks, reconcile):\n'
                   '    return checks.status_check, reconcile.anything\n'
                   'def h(NAME):\n'
                   '    import importlib\n'
                   '    return importlib.import_module(NAME)\n'
                   'def k():\n'
                   '    from studio.gi import services\n'
                   '    return services.LISTED_DOUBTED_CUE\n')
        found = new_package_violations('planted', references(planted, 'studio.interpretation'))
        expected = ['names studio.gi.context', 'names studio.gi.context.is_member_conflict (a re-homed name',
                    'names studio.gi.cues', 'names studio.gi.detect',
                    'names studio.validation.checks.evidence_readings',
                    'names studio.validation.reconcile', 'names studio.candidates.candidates',
                    'names studio.validation.review_view.stored_from', 'names studio.validation.checks.status_check',
                    'names the cue constant studio.validation.reconcile.FAILED_ATTEMPT',
                    'names studio.gi.detect.route', 'imports by a name it computes (NAME)',
                    'names studio.gi.services', 'names the cue constant studio.gi.services.LISTED_DOUBTED_CUE']
        for line in expected:
            with self.subTest(expected=line):
                self.assertTrue(any(line in item for item in found), found)
        joined = '\n'.join(found)
        for allowed in ('profiles', 'catalogue', 'code_scope', 'exact_evidence', 'questions', 'review_view.View'):
            self.assertNotIn(allowed, joined)
        self.assertNotIn('planted.g:', joined)  # parameters named checks and reconcile are not the modules

    def test_the_scoping_is_pythons_comprehensions_and_class_bodies_included(self):
        # the review of S12, finding 5: a comprehension's target is the comprehension's own, never a local of the
        # function around it; and a function nested in a class does not see the class's names
        planted = ('from studio.validation import checks\n'
                   'from studio.gi import detect\n'
                   'def f(rows, text):\n'
                   '    labels = [checks for checks in rows]\n'
                   '    seen = {detect for detect in rows}\n'
                   '    pairs = {checks: detect for checks, detect in rows}\n'
                   '    lazy = list(checks for checks in rows)\n'
                   '    return checks.status_check(text), detect.route(text, None)\n'
                   'def g(rows, text):\n'
                   '    return [checks.status_check(text) for checks in rows], [1 for detect in detect.route(text)]\n'
                   'def h(rows, text):\n'
                   '    [(checks := row) for row in rows]\n'
                   '    return checks.status_check(text)\n'
                   'class A:\n'
                   '    checks = None\n'
                   '    def m(self, text):\n'
                   '        return checks.status_check(text)\n'
                   '    listed = [checks.cite(text) for text in ()]\n'
                   '    direct = checks.restated\n')
        found = new_package_violations('overlay', references(planted, 'studio.interpretation'))
        expected = ('overlay.f:8 names studio.validation.checks.status_check',
                    'overlay.f:8 names studio.gi.detect.route', 'overlay.g:10 names studio.gi.detect.route',
                    'overlay.A.m:17 names studio.validation.checks.status_check',
                    'overlay.A:18 names studio.validation.checks.cite',
                    # a class body's own binding is not trusted to shadow (it reads a name before its assignment from
                    # the module): read as the module's, the safe way round
                    'overlay.A:19 names studio.validation.checks.restated')
        for line in expected:
            with self.subTest(expected=line):
                self.assertTrue(any(item.startswith(line) for item in found), found)
        # within its own comprehension the target is the comprehension's, and a walrus there binds the function's name
        self.assertFalse([item for item in found if item.startswith('overlay.g:10 names studio.validation.checks')])
        self.assertFalse([item for item in found if item.startswith('overlay.h:')], found)

    def test_the_legacy_reader_exception_is_the_legacy_readers_alone(self):
        planted = ('class LegacyReader:\n'
                   '    def views(self):\n'
                   '        from studio.validation import review_view\n'
                   '        return review_view.review_view\n'
                   'class EventReader:\n'
                   '    def views(self):\n'
                   '        from studio.validation import review_view\n'
                   '        return review_view.review_view\n')
        in_readers = new_package_violations('readers', references(planted, 'studio.interpretation'))
        self.assertTrue(in_readers and all('EventReader' in item for item in in_readers), in_readers)
        self.assertEqual(len(new_package_violations('overlay', references(planted, 'studio.interpretation'))), 4)

    def test_the_jobs_rule_refuses_a_new_branch_that_names_the_legacy_reader(self):
        planted = JOBS.read_text(encoding='utf-8') + (
            '\n\ndef stage_planted(job):\n'
            '    context = make_context(job.encounter, job.revision)\n'
            '    _remade_context(job)\n'
            '    gi_context.extract_context(job.revision.text)\n'
            '    validation_checks.status_check(job)\n'
            '    validation_checks.code_scope(job)\n'
            '    gi_detect.route(job.revision.text, None)\n'
            '    return gi_context.is_member_conflict(None)\n')
        found = [item for item in jobs_violations(planted) if 'stage_planted' in item]
        for line in ('names the legacy-only make_context', 'names the legacy-only _remade_context',
                     'names studio.gi.context.extract_context', 'names studio.validation.checks.status_check',
                     'names studio.gi.detect.route'):
            with self.subTest(expected=line):
                self.assertTrue(any(line in item for item in found), found)
        self.assertEqual(len(found), 5)  # the re-homed is_member_conflict and the 7.1 code_scope are allowed

    def test_the_consumer_rule_refuses_a_checks_reader_outside_its_pin(self):
        planted = ('from .validation import checks\n'
                   'def corti_unlisted_words(n):\n'
                   '    return checks.unlisted_codes(n)\n'
                   'def elsewhere(n):\n'
                   '    return (checks.unlisted_codes(n), checks.status_check(n), checks.code_scope(n),\n'
                   '            checks.NOT_CONNECTED_CHECKS)\n')
        found = consumer_violations('serializers', references(planted, 'studio'))
        self.assertEqual(len(found), 2, found)
        self.assertTrue(all('serializers.elsewhere' in item for item in found))
        self.assertTrue(any('unlisted_codes' in item for item in found))
        self.assertTrue(any('status_check' in item for item in found))

    def test_the_consumer_rule_allows_only_the_final_7_1_names_and_its_pins(self):
        # the review of S12, finding 2: R-5 lets an edited consumer name FINAL 7.1's checks only - never a word list of
        # the legacy reader (a string tuple or set, which no runtime count sees), an unpinned helper or constant, or a
        # cue constant of any denied module
        planted = ('from .validation import checks\n'
                   'from .validation.checks import fact_label\n'
                   'from .validation.engine import LISTED_NOT_PROPOSED\n'
                   'from .gi.cues import PAGE_NUMBER_LINE\n'
                   'def code_rows(text):\n'
                   '    return any(w in text.lower().split() for w in checks._V2_NEG_BEFORE '
                   '| set(checks._V2_NEG_AFTER))\n'
                   'def sections(text):\n'
                   '    return [name for name in checks._V2_UNREAD_SECTIONS if name in text]\n'
                   'def others(text):\n'
                   '    return (checks.DISTINCT_LESION_OPTIONS, checks.fact_label(text), checks.code_scope(text),\n'
                   '            checks.NOT_CONNECTED_CHECKS, LISTED_NOT_PROPOSED, PAGE_NUMBER_LINE.search(text))\n'
                   'def computed(name):\n'
                   '    return __import__(name)\n')
        found = consumer_violations('customer_api', references(planted, 'studio'))
        expected = ('customer_api.code_rows:6 names studio.validation.checks._V2_NEG_BEFORE',
                    'customer_api.code_rows:6 names studio.validation.checks._V2_NEG_AFTER',
                    'customer_api.sections:8 names studio.validation.checks._V2_UNREAD_SECTIONS',
                    'customer_api.others:10 names studio.validation.checks.DISTINCT_LESION_OPTIONS',
                    'customer_api.others:10 names studio.validation.checks.fact_label',
                    'customer_api.<module>:2 names studio.validation.checks.fact_label',
                    'customer_api.<module>:3 names the cue constant studio.validation.engine.LISTED_NOT_PROPOSED',
                    'customer_api.others:11 names the cue constant studio.validation.engine.LISTED_NOT_PROPOSED',
                    'customer_api.<module>:4 names the cue constant studio.gi.cues.PAGE_NUMBER_LINE',
                    'customer_api.computed:13 imports by a name it computes (name)')
        for line in expected:
            with self.subTest(expected=line):
                self.assertTrue(any(item.startswith(line) for item in found), found)
        self.assertEqual(len(found), len(expected), found)
        joined = '\n'.join(found)
        self.assertNotIn('code_scope', joined)  # FINAL 7.1's
        self.assertNotIn('NOT_CONNECTED_CHECKS', joined)
        # the pins are each consumer's own: review's options and reports' labels and wording, nowhere else
        pinned = ('from .validation.checks import fact_label\n'
                  'from .validation.engine import LISTED_NOT_PROPOSED\n'
                  'def _fact_title(fact):\n'
                  '    return fact_label(fact), LISTED_NOT_PROPOSED\n'
                  'def _chosen_modifiers(value):\n'
                  '    from .validation.checks import DISTINCT_LESION_OPTIONS\n'
                  '    return DISTINCT_LESION_OPTIONS\n')
        self.assertEqual(len(consumer_violations('reports', references(pinned, 'studio'))), 2)  # the options
        self.assertEqual(len(consumer_violations('review', references(pinned, 'studio'))), 4)  # labels and wording

    def test_the_cue_scan(self):
        for target in ('studio.gi.services.LISTED_DOUBTED_CUE', 'studio.validation.reconcile.FAILED_ATTEMPT',
                       'studio.gi.cues.PAGE_NUMBER_LINE', 'studio.gi.cues.INSTRUMENTS', 'studio.validation.checks.'
                       '_V2_DENIAL_WORDS', 'studio.x.HYPOTHETICAL_PAST', 'studio.x.LISTED_ANYTHING',
                       'studio.x.SOME_CUES'):
            with self.subTest(target=target):
                self.assertTrue(cue(target))
        for target in ('studio.validation.review_view.View', 'studio.validation.engine.DISTINCT_LESION_KINDS',
                       'studio.validation.checks.NOT_CONNECTED_CHECKS'):
            with self.subTest(target=target):
                self.assertFalse(cue(target))
