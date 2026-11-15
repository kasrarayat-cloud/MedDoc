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

DESIGN V2 (docs/gemini-migration/FINAL-V2.md 5.7 measures 1, 4 and 5; step 6a of its 8.1). "Words never decide":
- THE EXISTING PINS EXTENDED TO contract/ AND engine/: the new package's rule reads studio/interpretation/contract/*.py
  and engine/*.py as well (``package_modules``), and there a module the sentinel denies includes the 17 retired v1
  modules (sentinel.RETIRED_MODULES): no contract or engine module names one, with no exception. A kept module
  (sentinel.KEPT) or jobs.py names a retired module only at a pinned v1 branch (RETIRED_REFERENCES, each with why),
  so a new one arrives deliberately or not at all. The deny set's pins name the retired files too (RETIRED_SIZES).
- ``words_never_decide`` (WordsNeverDecide) over engine/*.py, contract/settle.py, contract/claims.py,
  contract/consistency.py, overlay.py and readers.py: no import of a retired module (no allowlist), of re, regex,
  unicodedata, difflib, fnmatch, lexicon, literals, or of contract's text modules (segment, geometry, fold,
  date_literals) - except consistency.py's date_literals for L1 (settle has no exemption: D206, 3a's R7); no import by
  a computed name; in engine/, no attribute or subscript named text, words, quote or unit_text (exact names, a getattr
  of one included); reading.text and revision.text nowhere in scope; no call of the listed str methods on a non-literal
  receiver, nor a getattr of one (DECISIONS D205); no in or not in with a string-constant operand; no comparison of a
  slice with a named or literal string (D205); and a display helper's return (wording's text functions, the module
  display builders pinned in DISPLAY_BUILDERS, FINAL 7.1's distinct_lesion_review_text) used only as an argument to a
  wording function, a HeldFact or clarification constructor, an f-string, a join, or another display helper's return
  - through transport only (a conditional's branches, a container, a comprehension's element, tuple, list, sorted, set,
  frozenset or dict.fromkeys, a +, a local name), never in a test, a comparison, a subscript or a method call.
- ``no_word_lists`` (NoWordLists) over contract/*.py and engine/*.py: no module-level (or class-level, outside an
  Enum's members) tuple, list, set or dict of two or more string literals unless every literal is a value of a design
  enumeration (the Enums of contract/types.py, engine/types.py, engine/anatomy.py and engine/catalogue.py; DECISIONS
  D207 and the triage hand-offs 0b#10 and 1e:R6) or the collection is a pinned OUTPUT table (OUTPUT_TABLES: claims'
  TEMPLATES, STATEMENT_TEMPLATES, KIND_LABELS, LABELS, PLACE_LABELS, STATEMENT_DATE_PHRASES and CARD_PHRASES, and
  extract_schema's DEFINITIONS, each covered by a version pin, which no code compares with document text);
  jsonschema's keyword Enum is named apart (KEYWORD_ENUMS: its values are schema keywords, not design values).
  contract/date_literals.py is the one exempt module, closed by pinning: tests/v2/test_date_literals.pin_findings (the
  one copy of the pin, hand-off 1c#6 = the integration's O1) holds every top-level statement to v1's eight functions,
  its header and its two tables by sha.
- ``single_character_geometry`` (SingleCharacterGeometry) over contract/segment.py and contract/geometry.py: no import
  of re (nor regex, unicodedata, difflib, fnmatch); no string literal longer than one character in a comparison; no
  str call but isspace, islower, isalnum, isalpha, isupper (D205), indexing, and find or rfind given a one-character
  literal; no getattr of a str method; no comparison of a slice with a named string (D205: ``NEG in t[a:a+2]``,
  ``t[a:a+2] == W``); int() only of one subscripted character (D205); a slice of the text only to copy it
  (``out += text[a:b]``, D205).
- 5.7 measure 5: ``mypy --strict`` over engine/types.py, engine/facts.py and engine/reading.py, with its positive
  control (a string operation on a fact value is a type error).
Each rule refuses a planted control of every form it names and passes its allowed forms; every pin is met (no stale
one). sentinel.retired_unarmed - the test-only v1 chain's seam - is named by no module outside tests/ (RetiredSeamTests).

Refutation 6a-r1, read fail-closed (step 6a's second round):
- F3: contract/ and engine/ are read to every depth (``package_modules`` globs ``**``, as 5.7 measure 4's engine/** and
  contract/** say and as sentinel.expected_retired accepts nested code there), and the scope test counts nested modules.
- F4: reading.text and revision.text through an attribute too (``assessment.revision.text``; a getattr or a subscript of
  one); in engine/, a mapping read of a text name (``.get('text')``, pop, setdefault, __getitem__, itemgetter or
  attrgetter given one); a str method named through ``str`` (``map(str.lower, items)``) or methodcaller; ``in`` through
  a ``__contains__`` or operator.contains call given a string; a ``match`` on a string pattern.
- F5: SingleCharacterGeometry refuses a ``match`` on a slice and a multi-character string pattern, an explicit call of
  a str dunder (``t.__contains__('no')``), and a slice handed to a method call (``{'no': 1}.get(t[a:a + 2])``, a lookup)
  or to hash().
- F6 (its local parts): membership through a name bound to a string or a string collection in the same function or
  module (``words = ('no', 'not'); value in words``); NoWordLists reads a concatenation of string collections
  (``('without',) + ('not',)``); and the display rule follows an f-string's or a join's result: it is never judged (a
  test, a comparison, a subscript or a method call, directly or through a local name).
- F7's static half: no production module of studio/ or cptstudio/ - not only the kept modules and jobs.py - names a
  retired module but at a pinned v1 branch (RETIRED_REFERENCES); a consumer importing a retired pattern is refused.
- F2's bound: every test that opens sentinel.strict without retired=True - v1's instrument, blind to the RETIRED kind -
  is pinned with why (STRICT_V1_INSTRUMENT), so a new v2-path use of the default arrives deliberately or not at all.

Refutation 6a-r2b P2 (DECISIONS D245), each form with a planted control (REFUTATION_R2B_PLANTS, REFUTATION_R2B_CONTROLS):
- a literal's split is a word list (``'no not without'.split()``, ``str.split('...')``, rsplit, splitlines, partition):
  WordsNeverDecide reads it as a string collection (inline, through a name, inside frozenset or dict.fromkeys), and
  NoWordLists refuses it at module and class level unless every word is a design value;
- a string or a string collection as the RECEIVER of a search - ``('no', 'not').__contains__(token)``,
  ``'no not'.find(token)``, and count, index, rindex, startswith, endswith given a value;
- a name bound in an ENCLOSING function and read in a nested one (Python's scoping walked outward; ``nonlocal`` and
  ``global`` followed);
- a class attribute (``K.WORDS``, and ``self.WORDS`` or ``cls.WORDS`` in a method of K) - an Enum's member never;
- reading.text and revision.text through a local alias (``source = job.revision; source.text``, or a getattr of one);
- in engine/, a comparison with a string - a non-empty string constant, an f-string, or a name or class attribute bound
  to a string (5.7 measure 4's intent: ``sentence == 'No biopsy was taken.'`` decides on words as ``in`` does); ``== ''``
  (presence, never a word) passes, and the engine's existing comparisons with its own records' and reference rows'
  values are pinned by function and value (WND_PINS), each with why. Outside engine/ the scanned modules compare their
  own stored records' strings (a question's scope, a check's status), which this rule does not read.
"""
from __future__ import annotations

import ast
import enum
import importlib
import os
import re
import subprocess
import sys
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
# FINAL-V2 5.7 measure 1: each retired file's code-object count, named here again (RETIRED_SIZE is their sum)
RETIRED_SIZES = {'studio/interpretation/prompt.py': 4, 'studio/interpretation/schema.py': 10,
                 'studio/interpretation/read.py': 13, 'studio/interpretation/normalize.py': 79,
                 'studio/interpretation/verify.py': 45, 'studio/interpretation/literals.py': 29,
                 'studio/interpretation/identity.py': 36, 'studio/interpretation/lexicon.py': 32,
                 'studio/interpretation/relations.py': 60, 'studio/interpretation/mapping.py': 47,
                 'studio/interpretation/classes.py': 36, 'studio/interpretation/ercp.py': 85,
                 'studio/interpretation/facts.py': 22, 'studio/interpretation/events.py': 171,
                 'studio/interpretation/coverage.py': 72, 'studio/interpretation/combination.py': 27,
                 'studio/interpretation/assess.py': 139}
RETIRED_ROOT = 'studio.interpretation.'
V2_PACKAGES = ('contract', 'engine')

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
    def __init__(self, package: str, roots: tuple = LEGACY_ROOTS):
        self.package = package
        self.roots = roots
        # per scope: (import aliases: name -> target, names it binds otherwise, its kind)
        self.scopes = [({}, set(), 'module')]
        self.where = []
        self.found = []

    def _record(self, target, kind, node):
        if kind == 'dynamic' or any(target == root or target.startswith(root + '.') for root in self.roots):
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


def references(source: str, package: str, roots: tuple = LEGACY_ROOTS) -> list:
    """Every Ref ``source`` makes to studio.gi, studio.validation or studio.candidates (``package``: what its relative
    imports resolve against; ``roots``: the modules a reference is recorded under, LEGACY_ROOTS by default, the retired
    modules too for design v2's rules), and every dynamic import (kind 'dynamic', its argument's source)."""
    finder = _Finder(package, roots)
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


def v2_files(root: Path = PACKAGE) -> dict:
    """{key: path} of every module of contract/ and engine/ under ``root`` (studio/interpretation), to EVERY depth
    (5.7 measure 4: engine/** and contract/**; refutation 6a-r1 F3): 'contract/<stem>', 'engine/<stem>', and a nested
    module as 'engine/<subpackage>/<stem>'."""
    found = {}
    for folder in V2_PACKAGES:
        for path in sorted((root / folder).rglob('*.py')):
            if '__pycache__' not in path.parts:
                found['/'.join((folder, *path.relative_to(root / folder).with_suffix('').parts))] = path
    return found


def package_modules(root: Path = PACKAGE) -> dict:
    """{stem: source} of every module of studio/interpretation - and, FINAL-V2 5.7's existing pins extended, every
    module of contract/ and engine/ to every depth (``v2_files``: 'contract/<stem>', 'engine/<stem>',
    'engine/<subpackage>/<stem>')."""
    found = {path.stem: path.read_text(encoding='utf-8') for path in sorted(root.glob('*.py'))}
    found.update({key: path.read_text(encoding='utf-8') for key, path in v2_files(root).items()})
    return found


def imports_of(source: str) -> set:
    """Every module or name a source imports, whatever it is."""
    out = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            out |= {f'{node.module}.{alias.name}' for alias in node.names}
        elif isinstance(node, ast.Import):
            out |= {alias.name for alias in node.names}
    return out


# --- design v2 (FINAL-V2 5.7 measures 1, 4 and 5): the rules ----------------------------------------------------------

RETIRED_TARGETS = tuple(sentinel.RETIRED_MODULES)  # the 17 retired v1 modules (FINAL-V2 5.0)
V2_ROOTS = LEGACY_ROOTS + RETIRED_TARGETS
# A kept module's or jobs.py's reference to a retired module, each a v1 branch (FINAL-V2 5.7 "Kept modules that import
# retired ones today, and how each stops"; DECISIONS D229 3b P2): (module, scope, retired module) -> why. Importing is
# not calling (D17); the sentinel counts every execution of these modules, so a branch here that ran on the new path
# would refuse its write - this pin makes a NEW reference a deliberate edit.
RETIRED_REFERENCES = {
    ('adapter', '_v1_prompt', 'studio.interpretation.prompt'): "the v1 surface's request builder (D229 3b P2: until the "
                                                                "v1 rows retire), imported when the v1 surface runs",
    ('adapter', '_v1_read', 'studio.interpretation.read'): "the v1 surface's envelope refusal (D229 3b P2)",
    ('store', '<module>', 'studio.interpretation.schema'): "v1's reader (store._v1_reader, reached only through readers' "
                                                          'V1 branch, labelled legacy_record; FINAL-V2 5.7)',
    ('store', '<module>', 'studio.interpretation.read'): "v1's reader's Refusal, STAGES and iso_date (FINAL-V2 5.7: "
                                                        "the v2 section reads contract/extract_read's own)",
    ('store', '<lambda>', 'studio.interpretation.read'): "v1's shape check of a stored date (store._ISO, v1's rows)",
    ('store', 'StoredInventory', 'studio.interpretation.read'): "a stored v1 row's Refusal (StoredInventory.refusal)",
    ('store', 'refused_row', 'studio.interpretation.read'): "v1's refused row records a read.Refusal (v1's writer)",
    ('store', '_consistent', 'studio.interpretation.read'): "v1's load check of a refused v1 row's Refusal",
    ('jobs', 'derived_facts', 'studio.interpretation.facts'): "the test-only v1 chain's derivation of a v1 row "
                                                             '(jobs._v1_rows_only)',
    ('jobs', '_stand_in', 'studio.interpretation.facts'): "the test-only v1 chain's routing stand-in over a v1 row",
    ('jobs', '_interpretation_child', 'studio.interpretation.normalize'): "the test-only v1 chain's reading child",
    ('jobs', '_interpretation_child', 'studio.interpretation.read'): "the test-only v1 chain's reading child",
    ('jobs', '_read_answer', 'studio.interpretation.read'): "the test-only v1 chain's stored-answer read (its Refusal)",
    ('jobs', '_assess_child_events', 'studio.interpretation.assess'): "the test-only v1 chain's events engine @1",
    ('jobs', '_member_date_state', 'studio.interpretation.facts'): "the test-only v1 chain's member date over a v1 row",
    ('jobs', '_assess_events', 'studio.interpretation.assess'): "the test-only v1 chain's events engine @1 "
                                                                '(after _v1_rows_only)',
}
TEXT_MODULES = ('segment', 'geometry', 'fold', 'date_literals')  # contract's text modules
FORBIDDEN_IMPORTS = ('re', 'regex', 'unicodedata', 'difflib', 'fnmatch')
FORBIDDEN_NAMES = ('lexicon', 'literals')  # named by 5.7 measure 4 beside the retired set, wherever they live
STR_METHODS = ('find', 'index', 'rfind', 'startswith', 'endswith', 'split', 'rsplit', 'partition', 'lower', 'upper',
               'casefold', 'strip', 'replace', 'count', 'istitle', 'isupper')  # 5.7 measure 4's list
ALL_STR_METHODS = frozenset(name for name in dir(str) if not name.startswith('_'))
# str's own dunders that compare, test, hash, index or build text (refutation 6a-r1 F5: ``t.__contains__('no')``), every
# one a str call SingleCharacterGeometry refuses when written out; object's protocol (__init__, __repr__ ...) is not one
STR_DUNDERS = frozenset({'__contains__', '__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__', '__hash__',
                         '__getitem__', '__iter__', '__len__', '__add__', '__mul__', '__rmul__', '__mod__', '__rmod__',
                         '__format__'})
READ_HOLDERS = ('reading', 'revision')  # 5.7 measure 4: reading.text and revision.text anywhere in scope
# a literal's split, the canonical Python word list (refutation 6a-r2b P2): 'no not without'.split(), str.split('...')
SPLITS = ('split', 'rsplit', 'splitlines', 'partition', 'rpartition')
# the str methods that search a receiver for a value: on a string or a string collection, given a value, a membership
# test written as a call (refutation 6a-r2b P2: ``('no', 'not').__contains__(token)``, ``'no not'.find(token)``)
SEARCHES = ('__contains__', 'count', 'find', 'rfind', 'index', 'rindex', 'startswith', 'endswith')
MAPPING_READS = ('get', 'pop', 'setdefault', '__getitem__')  # a mapping read by a key (refutation 6a-r1 F4)
GETTERS = ('itemgetter', 'attrgetter')  # operator's readers by a key or an attribute name
TEXT_NAMES = ('text', 'words', 'quote', 'unit_text')  # exact names (triage 0b:R1), never substrings
WORDS_NEVER_DECIDE = ('contract/settle', 'contract/claims', 'contract/consistency', 'overlay', 'readers')  # + engine/*
L1_EXEMPTION = ('contract/consistency', 'studio.interpretation.contract.date_literals')  # the one: L1 (5.7 measure 4)
# The display helpers (5.6: "wording.quote(span) and the display builders | copy slices into questions, explanations
# and labels after the decision"): the functions of wording.py that take document text to copy - a parameter named
# text, words or revision_text, or spans to slice - read from the module itself (``wording_helpers``). A label built
# from an enumeration value (event_kind_label, landmark_label, service_phrase, join) copies no slice of the document,
# so it is no display helper here (the step's NOTES record the reading and the question).
WORDING = 'studio.interpretation.wording'
TEXT_PARAMETERS = ('text', 'words', 'revision_text', 'spans', 'span')
# Each scanned module's own display builders - functions whose return is a display helper's value - with why: their
# calls are display helpers' calls (judged by the same rule), and returning a display helper's value from one is allowed
DISPLAY_BUILDERS = {
    ('overlay', '_words'): "a changed item's sentence at read time (wording.build over item_slots, with no text)",
}
# the constructors a display value may be handed to (5.7 measure 4: "a HeldFact or clarification constructor"), and
# wording's own records (a call through wording is a wording function anyway)
DISPLAY_CONSTRUCTORS = ('HeldFact', 'Clarification', 'Worded', 'Slots')
# a scanned module's own record that carries a display value to the clarification it becomes, each with why
DISPLAY_RECORDS = {
    ('overlay', 'Live'): "overlay's read-time record of a changed item: its worded field is the clarification's "
                         "sentence the view shows, and nothing compares it (read time's clarification constructor)",
}
# a WordsNeverDecide form met on a value that is no document text, each pinned with why: (module, function, form) -> why
WND_PINS = {
    ('overlay', '_pfs_rows', 'compares a slice with a string'): "a retrieval record's field NAME read for its 'pfs.' "
        'prefix (_PFS_PREFIX): CPT Studio\'s own reference record, never document text',
    # met since membership is read through a bound name too (refutation 6a-r1 F6)
    ('overlay', '_modifier_review', 'tests membership through CLAIMS_EXAMPLE_CODES'): "a proposal's CPT code (a "
        "proposer's code, never document text) looked up in the claims manual's two example codes (reference data)",
    ('overlay', 'assessment_counts', 'tests membership through name'): "a stored completeness record's own count keys "
        '(COUNTS) looked up in that record: record structure, never document text',
    # met since engine/ refuses a comparison with a string (refutation 6a-r2b P2, 5.7 measure 4's intent): each a value of
    # CPT Studio's own records or reference rows, pinned by function and value
    ('engine/assess', 'procedural', 'compares with a string through _ZERO_GLOBAL'): "a PFS reference row's global period "
        "against 'XXX' (a code that is no procedure, v1's engine._procedural): reference data, never document text",
    ('engine/assess', 'split_components', 'compares with a string through _PROFESSIONAL_ROW'): "a PFS reference row's "
        "modifier row against '26' (v1's checks.pctc_consideration): reference data, never document text",
    ('engine/assess', 'split_components', 'compares with a string through _TECHNICAL_ROW'): "a PFS reference row's "
        "modifier row against 'TC' (v1's checks.pctc_consideration): reference data, never document text",
    ('engine/coverage', '_unchallenged', 'compares with a string through RELATION_CONTRADICTION'): "a held conflict's "
        "cause against CPT Studio's own cause label (relation:contradiction, built from pairing.Relation): never document "
        'text',
    ('engine/derive', 'date_record', 'compares with a string through state'): "the date record's own state, set from the "
        "fact's state just above (dates.member_date_state's contract 8.1 values): record structure, never document text",
    ('engine/derive', 'date_record', "compares with 'stated'"): "the date record's own state value (contract 8.1), set "
        "from the fact's state: record structure, never document text",
    ('engine/derive', 'date_record', "compares with 'several'"): "the date record's own state value (contract 8.1), set "
        "from the fact's state: record structure, never document text",
    ('engine/derive', 'derive', "compares with 'not_stated'"): "date_record's own state value (contract 8.1): record "
        'structure, never document text',
    ('engine/derive', '_document_date', "compares with 'stated'"): "date_record's own state value (contract 8.1): record "
        'structure, never document text',
    ('engine/derive', '_document_date', "compares with 'several'"): "date_record's own state value (contract 8.1): "
        'record structure, never document text',
    ('engine/facts', '_pair_controls', "compares with 'pair_control'"): "a stored claim's role field against "
        "contract/types.ClaimRole's value (the store's closed vocabulary): record structure, never document text",
    ('engine/questions', '_named', 'compares with a string through UNLISTED'): "a held fact's cause against CPT Studio's "
        "own cause label ('unlisted', 3.2.6): never document text",
    ('engine/questions', 'fill', 'compares with a string through UNLISTED'): "a held fact's cause against CPT Studio's "
        "own cause label ('unlisted', 3.2.6): never document text",
    ('engine/questions', 'synthetic_entry', 'compares with a string through UNLISTED'): "a held fact's cause against CPT "
        "Studio's own cause label ('unlisted', 3.2.6): never document text",
    # the integration's fix of the combination (round w7r): repair r4a-2's D232 arm in _specific, built beside this table
    ('engine/questions', '_specific', 'compares with a string through UNLISTED'): "a held fact's cause against CPT "
        "Studio's own cause label ('unlisted', 3.2.6; D232's rule-4 pair): never document text",
}
# NoWordLists: a class's __slots__ names its attributes (identifiers of the class), never words
SLOTS = '__slots__'
# pure re-packaging a display value may pass through on its way to an allowed use (transport, never a use)
REPACKAGERS = ('tuple', 'list', 'sorted', 'set', 'frozenset', 'fromkeys')
# NoWordLists' pinned OUTPUT tables (5.7 measure 4; triage 1b:R3 and 2c:R6): (module, table) -> the pin covering it
OUTPUT_TABLES = {
    ('contract/claims', 'TEMPLATES'): 'TEMPLATES_SHA256',
    ('contract/claims', 'KIND_LABELS'): 'TEMPLATES_SHA256',
    ('contract/claims', 'LABELS'): 'TEMPLATES_SHA256',
    ('contract/claims', 'PLACE_LABELS'): 'TEMPLATES_SHA256',
    ('contract/claims', 'STATEMENT_DATE_PHRASES'): 'TEMPLATES_SHA256',
    ('contract/claims', 'CARD_PHRASES'): 'TEMPLATES_SHA256',
    ('contract/claims', 'STATEMENT_TEMPLATES'): 'STATEMENT_TEMPLATES_SHA256',
    ('contract/extract_schema', 'DEFINITIONS'): 'INSTRUCTIONS_SHA256_V2',
}
# the design's enumerations whose values a string collection may hold (triage 0b#10, 1e:R6; DECISIONS D207)
ENUM_MODULES = ('studio.interpretation.contract.types', 'studio.interpretation.engine.types',
                'studio.interpretation.engine.anatomy', 'studio.interpretation.engine.catalogue')
# jsonschema's keyword Enum, named by name (triage 0b#10): its values are schema keywords, never design values
KEYWORD_ENUMS = {('contract/jsonschema', '_Keyword'): "the six schema keywords jsonschema's canonical form reads "
                                                      "(v1's schema._KEYWORDS, copied: FINAL-V2 5.0)"}
NO_WORD_LISTS_EXEMPT = {'contract/date_literals': "closed by pinning (tests/v2/test_date_literals.pin_findings: v1's "
                                                  'eight functions, its header and its two tables by sha)'}
GEOMETRY_MODULES = ('contract/segment', 'contract/geometry')
ADMITTED = ('isspace', 'islower', 'isalnum', 'isalpha', 'isupper')  # SingleCharacterGeometry's str calls (D205)
MYPY_FENCE = ('studio/interpretation/engine/types.py', 'studio/interpretation/engine/facts.py',
              'studio/interpretation/engine/reading.py')  # 5.7 measure 5


def module_package(key: str) -> str:
    """The package a package_modules() key's relative imports resolve against (a nested key's own subpackage)."""
    return '.'.join(('studio.interpretation', *key.split('/')[:-1]))


def _retired(target: str) -> bool:
    return any(_under(target, name) for name in RETIRED_TARGETS)


def v2_package_violations(module: str, refs, used=None) -> list:
    """The new package's rule (new_package_violations) for a contract/ or engine/ module, and no reference to a retired
    v1 module at all (FINAL-V2 5.0: the new path's two packages import none; no allowlist)."""
    out = []
    plain = []
    for ref in refs:
        if ref.kind != 'dynamic' and _retired(ref.target):
            out.append(f'{module}.{ref.scope}:{ref.line} names the retired {ref.target}')
        else:
            plain.append(ref)
    return out + new_package_violations(module, plain, used)


def retired_references(module: str, source: str, package: str, used=None) -> list:
    """A kept module's (or jobs.py's) references to a retired module that RETIRED_REFERENCES does not pin."""
    used = set() if used is None else used
    out = []
    for ref in references(source, package, RETIRED_TARGETS):
        if ref.kind == 'dynamic' or not _retired(ref.target):
            continue
        name = next(item for item in RETIRED_TARGETS if _under(ref.target, item))
        key = (module, ref.scope.split('.')[0], name)
        if key in RETIRED_REFERENCES:
            used.add(key)
        else:
            out.append(f'{module}.{ref.scope}:{ref.line} names the retired {ref.target}')
    return out


def production_modules() -> dict:
    """{key: (source, package)} of every production module of studio/ and cptstudio/ - the 17 retired files, contract/
    and engine/ aside (the retired set itself, and the new package's rule) - keyed as RETIRED_REFERENCES keys a kept module
    (its stem) and jobs.py ('jobs'), any other by its dotted name (refutation 6a-r1 F7: a consumer importing a retired
    module or pattern is read too, not only the kept modules and jobs.py)."""
    retired = {PACKAGE / f'{name}.py' for name in sentinel.RETIRED_NAMES}
    out = {}
    for root in ('studio', 'cptstudio'):
        for path in sorted((APP / root).rglob('*.py')):
            relative = path.relative_to(APP)
            if '__pycache__' in path.parts or path in retired or relative.parts[:3] in (
                    ('studio', 'interpretation', 'contract'), ('studio', 'interpretation', 'engine')):
                continue
            package = '.'.join(relative.parts[:-1])
            if relative.parent == Path('studio', 'interpretation') and path.stem in sentinel.KEPT:
                key = path.stem
            elif path == JOBS:
                key = 'jobs'
            else:
                key = '.'.join(relative.with_suffix('').parts)
            out[key] = (path.read_text(encoding='utf-8'), package)
    return out


def _imports(tree, package: str) -> list:
    """[(line, the full name)] of every import anywhere in ``tree`` - each module and each name imported from one -
    relative ones resolved against ``package``; importlib.import_module and __import__ given a constant are imports, and
    given anything else ('dynamic', the argument's source)."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(node.lineno, alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                parts = package.split('.')
                base = '.'.join(parts[:len(parts) - node.level + 1] + ([node.module] if node.module else []))
            out.append((node.lineno, base))
            out += [(node.lineno, f'{base}.{alias.name}') for alias in node.names]
        elif isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', '')
            if name in ('import_module', '__import__') and node.args:
                argument = node.args[0]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    out.append((node.lineno, argument.value))
                else:
                    out.append((node.lineno, f'dynamic:{ast.unparse(argument)}'))
    return out


def _str_constant(node) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _strings_in(node) -> list:
    """The string constants a tuple, list or set display (or a dict display's keys and values) holds directly."""
    items = ([*node.keys, *node.values] if isinstance(node, ast.Dict)
             else node.elts if isinstance(node, (ast.Tuple, ast.List, ast.Set)) else [])
    return [item for item in items if _str_constant(item)]


def _sliced(node) -> bool:
    return isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice)


def _getattr_method(node, methods) -> str:
    """The str method a ``getattr(x, '<method>')`` call names, '' when it is none of ``methods``."""
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'getattr'
            and len(node.args) >= 2 and _str_constant(node.args[1]) and node.args[1].value in methods):
        return node.args[1].value
    return ''


def wording_helpers() -> frozenset:
    """The display helpers wording.py defines: its functions that take document text to copy (TEXT_PARAMETERS)."""
    tree = ast.parse((PACKAGE / 'wording.py').read_text(encoding='utf-8'))
    return frozenset(node.name for node in tree.body if isinstance(node, ast.FunctionDef)
                     and {arg.arg for arg in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)}
                     & set(TEXT_PARAMETERS))


def _holder(node, at=None, tree=None, parents=None, depth: int = 0) -> str:
    """'reading' or 'revision' when ``node`` is a name or an attribute of that name (READ_HOLDERS), or a getattr of one;
    with ``tree``, also a local name bound to one (refutation 6a-r2b P2: ``source = job.revision; source.text``), named
    'revision (through source)'; else ''."""
    if isinstance(node, ast.Name) and node.id in READ_HOLDERS:
        return node.id
    if isinstance(node, ast.Attribute) and node.attr in READ_HOLDERS:
        return node.attr
    if _getattr_method(node, READ_HOLDERS):
        return _getattr_method(node, READ_HOLDERS)
    if isinstance(node, ast.Name) and tree is not None and depth < 3:
        for value in _name_values(node.id, at, tree, parents):
            found = _holder(value, at, tree, parents, depth + 1)
            if found:
                return f'{found.split(" ")[0]} (through {node.id})'
    return ''


def _read_text(holder: str) -> str:
    """'revision.text' or 'revision.text (through source)' for a _holder answer."""
    name, _, via = holder.partition(' ')
    return f'{name}.text' + (f' {via}' if via else '')


def _call_name(node) -> str:
    """The called name of a call: ``f(...)`` -> 'f', ``x.f(...)`` -> 'f'; '' for anything else."""
    func = node.func
    return func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ''


def _mapping_read(node, names) -> str:
    """How ``node`` reads a key or an attribute in ``names`` by a mapping read or an operator getter
    (``.get('text')``, pop, setdefault, __getitem__, ``itemgetter('quote')``, ``attrgetter('words')``), '' for none."""
    if not (isinstance(node, ast.Call) and node.args and _str_constant(node.args[0]) and node.args[0].value in names):
        return ''
    name = _call_name(node)
    if (name in MAPPING_READS and isinstance(node.func, ast.Attribute)) or name in GETTERS:
        return f'[{node.args[0].value!r}] through {name}()'
    return ''


def _string_patterns(pattern) -> list:
    """The string constants a match pattern compares with (a value, an or-pattern's values, a mapping's keys)."""
    out = []
    for node in ast.walk(pattern):
        if isinstance(node, ast.MatchValue) and _str_constant(node.value):
            out.append(node.value.value)
        elif isinstance(node, ast.MatchMapping):
            out += [key.value for key in node.keys if _str_constant(key)]
    return out


def _collection_strings(node, depth: int = 0) -> list:
    """The string constants a collection expression holds: a display, a concatenation or union of displays
    (``('without',) + ('not',)``: refutation 6a-r1 F6), set/frozenset/tuple/list of one, a string itself."""
    if depth > 6 or node is None:
        return []
    if _str_constant(node):
        return [node]
    if _split_words(node):  # refutation 6a-r2b P2: 'no not without'.split() is a word list
        return _split_words(node)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'fromkeys'
            and node.args):  # dict.fromkeys(('no', 'not'))
        return _collection_strings(node.args[0], depth + 1)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set, ast.Dict)):
        return _strings_in(node) + [found for item in getattr(node, 'elts', ()) if not _str_constant(item)
                                    for found in _collection_strings(item, depth + 1)
                                    if isinstance(item, (ast.Tuple, ast.List, ast.Set))]
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.BitOr, ast.Sub, ast.BitAnd)):
        return _collection_strings(node.left, depth + 1) + _collection_strings(node.right, depth + 1)
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id in ('set', 'frozenset', 'tuple', 'list', 'sorted') and len(node.args) == 1):
        return _collection_strings(node.args[0], depth + 1)
    return []


def _split_words(node) -> list:
    """The words a literal's split makes, as string constants at the call's place (refutation 6a-r2b P2: the canonical
    Python word list) - ``'no not without'.split()``, ``str.split('no not')``, rsplit, splitlines, partition and
    rpartition; [] for any other node. A split given an argument that is no literal stands for the literal itself."""
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute) or node.func.attr not in SPLITS:
        return []
    receiver, arguments = node.func.value, list(node.args)
    if isinstance(receiver, ast.Name) and receiver.id == 'str' and arguments and _str_constant(arguments[0]):
        receiver, arguments = arguments[0], arguments[1:]
    if not _str_constant(receiver):
        return []
    words = [receiver.value]
    if all(isinstance(item, ast.Constant) for item in arguments) and all(
            isinstance(item.value, ast.Constant) for item in node.keywords):
        try:
            words = list(getattr(receiver.value, node.func.attr)(
                *[item.value for item in arguments], **{item.arg: item.value.value for item in node.keywords}))
        except (TypeError, ValueError):
            words = [receiver.value]
    return [ast.copy_location(ast.Constant(value=word), node) for word in words if isinstance(word, str) and word]


def _module_level(tree):
    """The module's own statements and expressions, never a function's or a class's body."""
    stack = list(tree.body)
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))


def _function_of(node, parents):
    """The innermost function or lambda holding ``node`` (None at module level)."""
    while node is not None and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        node = parents.get(node)
    return node


def _own_nodes(scope):
    """The nodes of ``scope``'s own body: never a nested function's, lambda's or class's body."""
    stack = list(ast.iter_child_nodes(scope))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            stack.extend(ast.iter_child_nodes(node))


def _name_values(name: str, at, tree, parents) -> list:
    """The values ``name`` is bound to where ``at`` reads it, scoped as Python scopes a plain name closely enough for a
    backstop (refutation 6a-r1 F6: a function-local word tuple; refutation 6a-r2b P2: one bound in an ENCLOSING function
    and read in a nested one): the innermost enclosing function that binds the name in any way, walking outward (a
    parameter or an unpacking binds it to nothing readable here; ``nonlocal`` defers to the functions outside, ``global``
    to the module), else the module's own top-level bindings. An assignment gives its value; a for loop's or a
    comprehension's target gives its iterable, standing for its elements."""
    scope, nodes = _function_of(at, parents), None
    while scope is not None:
        arguments = scope.args
        if name in {item.arg for item in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs,
                                          arguments.vararg, arguments.kwarg) if item is not None}:
            return []
        walked = list(ast.walk(scope))
        bound_here = any(isinstance(node, ast.Name) and node.id == name and isinstance(node.ctx, (ast.Store, ast.Del))
                         for node in walked)
        # a declaration is the scope's own, never a nested function's (whose nonlocal says nothing of this scope)
        declared = next(('global' if isinstance(node, ast.Global) else 'nonlocal' for node in _own_nodes(scope)
                         if isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names), '')
        if declared == 'global':
            break
        if bound_here and not declared:
            nodes = walked
            break
        scope = _function_of(parents.get(scope), parents)
    if nodes is None:
        nodes = list(_module_level(tree))
    out = []
    for node in nodes:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == name
                                                for target in node.targets):
            out.append(node.value)
        elif (isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name)
              and node.target.id == name and node.value is not None):
            out.append(node.value)
        elif isinstance(node, (ast.For, ast.comprehension)) and isinstance(node.target, ast.Name) and \
                node.target.id == name:
            out.append(node.iter)
        elif isinstance(node, ast.NamedExpr) and node.target.id == name:
            out.append(node.value)
    return out


def _stringish(item, at, tree, parents, depth: int = 0) -> bool:
    """Whether ``item`` (a membership operand) is a string or holds strings: a string constant, an f-string, a
    collection holding a string constant, or a name bound (``_name_values``) to one of those - the last a function-local or
    module-level word list read through its name (refutation 6a-r1 F6)."""
    if _str_constant(item) or isinstance(item, ast.JoinedStr) or _strings_in(item) or _collection_strings(item):
        return True
    if isinstance(item, ast.Name) and depth < 3:
        return any(_stringish(value, at, tree, parents, depth + 1) for value in _name_values(item.id, at, tree, parents)
                   if value is not item)
    if isinstance(item, ast.Attribute) and depth < 3:  # refutation 6a-r2b P2: a class attribute (K.WORDS, self.WORDS)
        return any(_stringish(value, at, tree, parents, depth + 1) for value in _attribute_values(item, at, tree, parents))
    return False


def _attribute_values(node, at, tree, parents) -> list:
    """The values a class attribute read is bound to (refutation 6a-r2b P2): ``K.WORDS`` for a class K the module
    defines, ``self.WORDS`` or ``cls.WORDS`` inside a method of one - the class body's own assignments to the name; []
    for an Enum's member (an enumeration member is no string) and for any other attribute (an instance's or another
    module's attribute is no binding read here)."""
    owner = None
    if isinstance(node.value, ast.Name):
        classes = {item.name: item for item in ast.walk(tree) if isinstance(item, ast.ClassDef)}
        if node.value.id in classes:
            owner = classes[node.value.id]
        elif node.value.id in ('self', 'cls'):
            owner = parents.get(at)
            while owner is not None and not isinstance(owner, ast.ClassDef):
                owner = parents.get(owner)
    if owner is None or _enum_class(owner):  # an Enum's members are enumeration members, never strings
        return []
    out = []
    for statement in owner.body:
        if isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name) and target.id == node.attr
                                                     for target in statement.targets):
            out.append(statement.value)
        elif (isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name)
              and statement.target.id == node.attr and statement.value is not None):
            out.append(statement.value)
    return out


def _display_violations(tree, module: str, used: set = None) -> list:
    """5.7 measure 4's display rule over ``tree``: a display helper's value used anywhere but as an argument to a wording
    function, a HeldFact or clarification constructor, an f-string, a join, or another display helper's return -
    through transport only (module docstring)."""
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    aliases, names = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == 'studio.interpretation':
            aliases |= {alias.asname or alias.name for alias in node.names if alias.name == 'wording'}
        elif isinstance(node, ast.ImportFrom) and node.module == WORDING:
            names.update({alias.asname or alias.name: alias.name for alias in node.names})
        elif isinstance(node, ast.Import):
            aliases |= {alias.asname for alias in node.names if alias.name == WORDING and alias.asname}
    used = set() if used is None else used
    local = {name for (owner, name) in DISPLAY_BUILDERS if owner == module}
    used |= {(module, name) for name in local}
    helpers = wording_helpers()

    def owner(node):
        while node is not None and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            node = parents.get(node)
        return node

    def is_display_call(call) -> bool:
        func = call.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in aliases:
            return func.attr in helpers
        return isinstance(func, ast.Name) and ((func.id in names and names[func.id] in helpers) or func.id in local)

    def sink(call) -> bool:
        """Whether ``call`` (whose argument the value is) is an allowed sink."""
        func = call.func
        if is_display_call(call):
            return True
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id in aliases:
            return True  # any wording function (Slots, Message, build ...)
        if isinstance(func, ast.Attribute) and func.attr == 'join':
            return True
        name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
        if (module, name) in DISPLAY_RECORDS:
            used.add((module, name))
            return True
        return name in DISPLAY_CONSTRUCTORS

    def judged(node, seen=frozenset()) -> bool:
        """Whether ``node`` (an f-string or a join holding a display value) is decided on: tested, compared,
        subscripted, a method called on it, matched - directly, or through a local name it is assigned to
        (refutation 6a-r1 F6: the rule does not end at an f-string or a join)."""
        parent = parents.get(node)
        if parent is None:
            return False
        if isinstance(parent, (ast.Compare, ast.BoolOp)) or (isinstance(parent, ast.UnaryOp)
                                                           and isinstance(parent.op, ast.Not)):
            return True
        if isinstance(parent, (ast.If, ast.While, ast.Assert)) and parent.test is node:
            return True
        if isinstance(parent, ast.IfExp):
            return parent.test is node or judged(parent, seen)
        if isinstance(parent, ast.comprehension) and node in parent.ifs:
            return True
        if isinstance(parent, (ast.Subscript, ast.Attribute)) and parent.value is node:
            return True
        if isinstance(parent, ast.Match) and parent.subject is node:
            return True
        if isinstance(parent, ast.FormattedValue):
            return judged(parents.get(parent), seen)
        if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Add):
            return judged(parent, seen)
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name):
            target, function = parent.targets[0].id, owner(parent)
            if function is None or (target, id(function)) in seen:
                return False
            return any(judged(item, seen | {(target, id(function))}) for item in ast.walk(function)
                       if isinstance(item, ast.Name) and item.id == target and isinstance(item.ctx, ast.Load))
        return False

    def allowed(node, seen=frozenset()) -> bool:
        parent = parents.get(node)
        if parent is None:
            return False
        if isinstance(parent, ast.FormattedValue):
            return not judged(parents.get(parent))  # an f-string is a use; its result is never decided on
        if isinstance(parent, ast.Call):
            if node is parent.func:
                return False
            if sink(parent):
                func = parent.func
                return not (isinstance(func, ast.Attribute) and func.attr == 'join' and judged(parent))
            func = parent.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, 'id', '')
            return name in REPACKAGERS and allowed(parent, seen)
        if isinstance(parent, ast.keyword):
            call = parents.get(parent)
            return isinstance(call, ast.Call) and sink(call)
        if isinstance(parent, ast.Return):
            function = owner(parent)
            return function is not None and getattr(function, 'name', '') in local
        if isinstance(parent, ast.IfExp):
            return node is not parent.test and allowed(parent, seen)
        if isinstance(parent, (ast.Tuple, ast.List, ast.Set, ast.Starred)):
            return allowed(parent, seen)
        if isinstance(parent, ast.Dict):
            return node in parent.values and allowed(parent, seen)
        if isinstance(parent, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            return node is parent.elt and allowed(parent, seen)
        if isinstance(parent, ast.DictComp):
            return node is parent.value and allowed(parent, seen)
        if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Add):
            return allowed(parent, seen)
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name):
            target, function = parent.targets[0].id, owner(parent)
            if function is None or (target, id(function)) in seen:
                return function is not None
            loads = [item for item in ast.walk(function) if isinstance(item, ast.Name) and item.id == target
                     and isinstance(item.ctx, ast.Load)]
            return all(allowed(item, seen | {(target, id(function))}) for item in loads)
        return False

    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and is_display_call(node) and not allowed(node):
            out.append(f'{module}:{node.lineno} uses the display value of {ast.unparse(node.func)}() '
                       f'({type(parents.get(node)).__name__})')
    return out


def words_never_decide(source: str, module: str, used: set = None) -> list:
    """WordsNeverDecide (5.7 measure 4; module docstring) over ``source``, the module ``module`` (a package_modules()
    key: 'engine/<stem>', 'contract/<stem>', 'overlay', 'readers'). ``used``: a set the pins this reading met are added
    to (WND_PINS, DISPLAY_BUILDERS, DISPLAY_RECORDS, the L1 exemption)."""
    used = set() if used is None else used
    tree, out = ast.parse(source), []
    engine = module.startswith('engine/')
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}

    def function_of(node):
        while node is not None and not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node = parents.get(node)
        return node.name if node is not None else '<module>'

    def finding(node, form, text):
        key = (module, function_of(node), form)
        if key in WND_PINS:
            used.add(key)
        else:
            out.append(text)
    for line, name in _imports(tree, module_package(module)):
        if name.startswith('dynamic:'):
            out.append(f'{module}:{line} imports by a computed name ({name[8:]})')
            continue
        parts = name.split('.')
        if parts[0] in FORBIDDEN_IMPORTS:
            out.append(f'{module}:{line} imports {name}')
        elif _retired(name):
            out.append(f'{module}:{line} imports the retired {name}')
        elif any(part in FORBIDDEN_NAMES for part in parts[1:]):
            out.append(f'{module}:{line} imports {name}')
        elif parts[:3] == ['studio', 'interpretation', 'contract'] and len(parts) > 3 and parts[3] in TEXT_MODULES:
            if (module, '.'.join(parts[:4])) == L1_EXEMPTION:
                used.add(L1_EXEMPTION)
            else:
                out.append(f'{module}:{line} imports the text module {name}')
    for node in ast.walk(tree):
        if engine and isinstance(node, ast.Attribute) and node.attr in TEXT_NAMES:
            out.append(f'{module}:{node.lineno} reads .{node.attr}')
        elif engine and isinstance(node, ast.Subscript) and _str_constant(node.slice) and node.slice.value in TEXT_NAMES:
            out.append(f'{module}:{node.lineno} reads [{node.slice.value!r}]')
        elif engine and _getattr_method(node, TEXT_NAMES):
            out.append(f'{module}:{node.lineno} reads getattr(..., {_getattr_method(node, TEXT_NAMES)!r})')
        if engine and _mapping_read(node, TEXT_NAMES):  # refutation 6a-r1 F4: row.get('text'), itemgetter('quote')
            out.append(f'{module}:{node.lineno} reads {_mapping_read(node, TEXT_NAMES)}')
        # reading.text and revision.text anywhere in scope - through a name or an attribute (refutation 6a-r1 F4:
        # assessment.revision.text), a getattr or a subscript of one
        # (refutation 6a-r2b P2: through a local alias too, ``source = job.revision; source.text``)
        if isinstance(node, ast.Attribute) and node.attr == 'text' and _holder(node.value, node, tree, parents):
            out.append(f'{module}:{node.lineno} reads {_read_text(_holder(node.value, node, tree, parents))}')
        elif (isinstance(node, ast.Call) and _getattr_method(node, ('text',)) and node.args
              and _holder(node.args[0], node, tree, parents)):
            out.append(f'{module}:{node.lineno} reads {_read_text(_holder(node.args[0], node, tree, parents))}')
        elif (isinstance(node, ast.Subscript) and _str_constant(node.slice) and node.slice.value == 'text'
              and _holder(node.value, node, tree, parents)):
            out.append(f'{module}:{node.lineno} reads {_read_text(_holder(node.value, node, tree, parents))}')
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in STR_METHODS
                and not isinstance(node.func.value, ast.Constant)):
            out.append(f'{module}:{node.lineno} calls .{node.func.attr}() on a value')
        if _getattr_method(node, STR_METHODS):
            out.append(f'{module}:{node.lineno} calls getattr(..., {_getattr_method(node, STR_METHODS)!r})')
        # a str method named through str (map(str.lower, items), str.startswith(value, 'no')) or methodcaller
        if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == 'str'
                and node.attr in STR_METHODS):
            out.append(f'{module}:{node.lineno} names str.{node.attr}')
        if (isinstance(node, ast.Call) and _call_name(node) == 'methodcaller' and node.args
                and _str_constant(node.args[0]) and node.args[0].value in STR_METHODS):
            out.append(f'{module}:{node.lineno} calls methodcaller({node.args[0].value!r})')
        # in through a call: value.__contains__('no'), operator.contains(value, 'no')
        if (isinstance(node, ast.Call) and _call_name(node) in ('__contains__', 'contains')
                and any(_stringish(item, node, tree, parents) for item in node.args)):
            out.append(f'{module}:{node.lineno} tests membership against a string')
        # refutation 6a-r2b P2: the string (or string collection) is the RECEIVER - ('no', 'not').__contains__(token),
        # 'no not without'.find(token) - a membership test written as a method call
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in SEARCHES
              and _stringish(node.func.value, node, tree, parents)
              and (node.func.attr == '__contains__' or not all(isinstance(item, ast.Constant) for item in node.args))):
            out.append(f'{module}:{node.lineno} tests membership against a string (a string receiver searched by '
                       f'.{node.func.attr}())')
        if isinstance(node, ast.match_case) and _string_patterns(node.pattern):  # a match on a string: a comparison
            out.append(f'{module}:{node.pattern.lineno} matches a string pattern '
                       f'({", ".join(repr(item) for item in _string_patterns(node.pattern)[:3])})')
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                if any(_str_constant(item) or isinstance(item, ast.JoinedStr) or _strings_in(item)
                       or _collection_strings(item) for item in operands):
                    out.append(f'{module}:{node.lineno} tests membership against a string')
                else:  # through a name bound to a string or a collection of them (refutation 6a-r1 F6), or a class
                    # attribute (refutation 6a-r2b P2): pinnable
                    for item in operands:
                        if isinstance(item, (ast.Name, ast.Attribute)) and _stringish(item, node, tree, parents):
                            through = ast.unparse(item)
                            finding(node, f'tests membership through {through}',
                                    f'{module}:{node.lineno} tests membership against a string (through {through})')
            # refutation 6a-r2b P2 (5.7 measure 4's intent): in engine/, no comparison with a string - a non-empty
            # string constant, an f-string, or a name or class attribute bound to a string - only ``== ''`` (presence,
            # never a word); pinnable, each pin naming the value
            if engine and any(not isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
                for item in operands:
                    if _str_constant(item) and item.value != '':
                        finding(node, f'compares with {item.value!r}',
                                f'{module}:{node.lineno} compares with the string {item.value!r}')
                    elif isinstance(item, ast.JoinedStr):
                        finding(node, 'compares with an f-string', f'{module}:{node.lineno} compares with an f-string')
                    elif isinstance(item, (ast.Name, ast.Attribute)) and not _sliced(item) and _stringish(
                            item, node, tree, parents):
                        through = ast.unparse(item)
                        finding(node, f'compares with a string through {through}',
                                f'{module}:{node.lineno} compares with a string (through {through})')
            if any(_sliced(item) for item in operands) and any(
                    isinstance(item, (ast.Name, ast.Attribute)) or _str_constant(item)
                    for item in operands if not _sliced(item)):
                finding(node, 'compares a slice with a string', f'{module}:{node.lineno} compares a slice with a string')
    return out + _display_violations(tree, module, used)


def _design_values() -> frozenset:
    """Every string value of the design's enumerations (ENUM_MODULES)."""
    out = set()
    for name in ENUM_MODULES:
        module = importlib.import_module(name)
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, enum.Enum) and value.__module__ == name:
                out |= {member.value for member in value if isinstance(member.value, str)}
    return frozenset(out)


def _enum_class(node) -> bool:
    return any((isinstance(base, ast.Name) and base.id.endswith(('Enum', 'Flag')))
               or (isinstance(base, ast.Attribute) and base.attr.endswith(('Enum', 'Flag'))) for base in node.bases)


def no_word_lists(source: str, module: str, values: frozenset = None) -> list:
    """NoWordLists (5.7 measure 4; module docstring) over ``source``, the module ``module`` (a package_modules() key).
    ``values``: the design values a collection may hold (``_design_values``)."""
    if module in NO_WORD_LISTS_EXEMPT:
        return []
    values = _design_values() if values is None else values
    out = []

    def bound(statement) -> str:
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        return ', '.join(ast.unparse(target) for target in targets)

    def scan(body, where):
        for statement in body:
            if isinstance(statement, ast.ClassDef):
                if _enum_class(statement):
                    continue  # an Enum's members are an enumeration (triage 0b:R1); only ENUM_MODULES' are values
                scan(statement.body, f'{where}{statement.name}.')
                continue
            if not isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)) or statement.value is None:
                continue
            name = bound(statement)
            if (module, name) in OUTPUT_TABLES and not where:
                continue
            if name == SLOTS and where and all(_str_constant(item) and item.value.isidentifier()
                                               for item in getattr(statement.value, 'elts', [None])):
                continue  # a class's attribute names
            for node in ast.walk(statement.value):
                if isinstance(node, (ast.Lambda, ast.FunctionDef)):
                    continue
                found = _strings_in(node)
                if isinstance(node, ast.BinOp):  # refutation 6a-r1 F6: ('without',) + ('not',) is one word list
                    found = _collection_strings(node)
                if _split_words(node):  # refutation 6a-r2b P2: 'no not without'.split() is one word list
                    found = _split_words(node)
                if len(found) >= 2 and any(item.value not in values for item in found):
                    out.append(f'{module}:{node.lineno} a word list in {where}{name} '
                               f'({", ".join(repr(item.value) for item in found[:3])}...)')
                    break
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id in ('set', 'frozenset', 'tuple', 'list') and node.args
                        and _str_constant(node.args[0]) and len(node.args[0].value) > 1):
                    out.append(f'{module}:{node.lineno} a collection of a string\'s characters in {where}{name}')
                    break

    scan(ast.parse(source).body, '')
    return out


def single_character_geometry(source: str, module: str = '') -> list:
    """SingleCharacterGeometry (5.7 measure 4 with DECISIONS D205; module docstring) over ``source``."""
    tree, out = ast.parse(source), []
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for line, name in _imports(tree, 'studio.interpretation.contract'):
        if name.split('.')[0] in FORBIDDEN_IMPORTS:
            out.append(f'{module}:{line} imports {name}')
    for node in ast.walk(tree):
        if isinstance(node, ast.match_case):  # refutation 6a-r1 F5: a match case is a comparison
            out += [f'{module}:{node.pattern.lineno} compares with {value!r}' for value in _string_patterns(node.pattern)
                    if len(value) > 1]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in STR_DUNDERS):
            out.append(f'{module}:{node.lineno} calls .{node.func.attr}()')  # refutation 6a-r1 F5: a str dunder
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            for operand in operands:
                out += [f'{module}:{node.lineno} compares with {leaf.value!r}' for leaf in ast.walk(operand)
                        if _str_constant(leaf) and len(leaf.value) > 1]
            if any(_sliced(item) for item in operands) and any(
                    isinstance(item, (ast.Name, ast.Attribute)) for item in operands if not _sliced(item)):
                out.append(f'{module}:{node.lineno} compares a slice with a named string')
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ALL_STR_METHODS
              and node.func.attr not in ADMITTED):
            first = node.args[0] if node.args else None
            if not (node.func.attr in ('find', 'rfind') and _str_constant(first) and len(first.value) == 1):
                out.append(f'{module}:{node.lineno} calls .{node.func.attr}()')
        if _getattr_method(node, ALL_STR_METHODS | STR_DUNDERS):
            out.append(f'{module}:{node.lineno} calls getattr(..., '
                       f'{_getattr_method(node, ALL_STR_METHODS | STR_DUNDERS)!r})')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ('eval', 'exec',
                                                                                              '__import__'):
            out.append(f'{module}:{node.lineno} calls {node.func.id}()')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'int':
            argument = node.args[0] if len(node.args) == 1 and not node.keywords else None
            if not (isinstance(argument, ast.Subscript) and not isinstance(argument.slice, ast.Slice)):
                out.append(f'{module}:{node.lineno} calls int() on more than one character')
        if _sliced(node):  # D205: a slice copies characters (into the framed text, a located-words record), never judged
            parent = parents.get(node)
            judged = (isinstance(parent, (ast.Compare, ast.BoolOp, ast.UnaryOp, ast.Subscript))
                      or (isinstance(parent, ast.Attribute) and parent.value is node)
                      or (isinstance(parent, (ast.If, ast.While, ast.IfExp, ast.Assert)) and parent.test is node)
                      or (isinstance(parent, ast.comprehension) and node in parent.ifs)
                      # refutation 6a-r1 F5: matched, or handed to a method call (a lookup: {'no': 1}.get(slice)) or
                      # to hash(); a plain constructor or function given the copy (Located(a, b, t[a:b])) copies it
                      or (isinstance(parent, ast.Match) and parent.subject is node)
                      or (isinstance(parent, ast.Call) and node is not parent.func
                          and (isinstance(parent.func, ast.Attribute)
                               or (isinstance(parent.func, ast.Name) and parent.func.id == 'hash')))
                      or (isinstance(parent, ast.keyword) and isinstance(parents.get(parent), ast.Call)
                          and isinstance(parents[parent].func, ast.Attribute)))
            if judged:
                out.append(f'{module}:{node.lineno} judges a slice of the text')
    return out


# --- the tests -------------------------------------------------------------------------------------------------------

class NewPackageTests(SimpleTestCase):
    def test_the_new_package_names_nothing_of_the_legacy_reader_but_what_is_allowed(self):
        modules = package_modules()
        self.assertEqual(set(modules), {path.stem for path in PACKAGE.glob('*.py')} | set(v2_files()))
        self.assertEqual(len(v2_files()), sum(1 for folder in V2_PACKAGES for path in (PACKAGE / folder).rglob('*.py')
                                              if '__pycache__' not in path.parts))  # every depth (refutation F3)
        self.assertTrue({'contract/settle', 'contract/claims', 'engine/assess', 'engine/evaluate'} <= set(modules))
        # every module of FINAL 3.1's plan is read, S01's to S11's
        self.assertLessEqual({'__init__', 'prompt', 'schema', 'read', 'store', 'literals', 'lexicon', 'normalize',
                              'verify', 'identity', 'relations', 'mapping', 'dates', 'adapter', 'replay', 'facts',
                              'events', 'coverage', 'combination', 'assess', 'wording', 'overlay', 'readers',
                              'holds', 'sentinel', 'report'}, set(modules))
        found, used, judged = [], set(), 0
        for stem, source in modules.items():
            refs = references(source, module_package(stem), V2_ROOTS if '/' in stem else LEGACY_ROOTS)
            judged += sum(1 for ref in refs if denied(ref.target))
            found += (v2_package_violations if '/' in stem else new_package_violations)(stem, refs, used)
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
        self.assertEqual(sentinel.LEGACY_SIZES, SIZES)
        self.assertEqual(sentinel.PINNED_SIZES, {**SIZES, **RETIRED_SIZES})  # FINAL-V2 5.7 measure 1: both kinds
        self.assertEqual(status['sizes'], {**SIZES, **RETIRED_SIZES})
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


# --- design v2 (FINAL-V2 5.7 measures 1, 4 and 5) ----------------------------------------------------------------------

def _scope() -> dict:
    """{key: source} of WordsNeverDecide's scope: engine/*.py, contract's settle, claims and consistency, overlay.py and
    readers.py."""
    modules = package_modules()
    return {key: source for key, source in modules.items()
            if key.startswith('engine/') or key in WORDS_NEVER_DECIDE}


def _v2_modules() -> dict:
    return {key: source for key, source in package_modules().items() if '/' in key}


class RetiredPinTests(SimpleTestCase):
    """FINAL-V2 5.7 measure 1, named here again: the retired list is the files, each file's size is pinned, and a kept
    module or jobs.py names a retired module only at a pinned v1 branch."""

    def test_the_retired_modules_are_the_files_but_the_kept_ones(self):
        self.assertEqual(sentinel.RETIRED_NAMES, ('prompt', 'schema', 'read', 'normalize', 'verify', 'literals',
                                                  'identity', 'lexicon', 'relations', 'mapping', 'classes', 'ercp',
                                                  'facts', 'events', 'coverage', 'combination', 'assess'))  # 5.0
        self.assertEqual(sentinel.KEPT, ('__init__', 'adapter', 'holds', 'sentinel', 'readers', 'overlay', 'store',
                                         'wording', 'report', 'replay', 'dates'))
        on_disk = {path.stem for path in PACKAGE.glob('*.py')}
        self.assertEqual(on_disk - set(sentinel.KEPT), set(sentinel.RETIRED_NAMES))
        self.assertEqual(sentinel.expected_retired(), set(sentinel.RETIRED_MODULES))
        self.assertEqual({path.name for path in PACKAGE.iterdir() if path.is_dir() and path.name != '__pycache__'},
                         set(sentinel.NEW_PACKAGES))

    def test_each_retired_files_size_is_pinned(self):
        status = sentinel.install()
        self.assertEqual(status['state'], 'ok', status['reason'])
        self.assertEqual(sentinel.RETIRED_SIZES, RETIRED_SIZES)
        self.assertEqual(sentinel.PINNED_SIZES, {**SIZES, **RETIRED_SIZES})
        self.assertEqual((sentinel.RETIRED_SIZE, status['retired_size'], status['pinned_retired_size']),
                         (sum(RETIRED_SIZES.values()),) * 3)
        self.assertEqual({key: status['sizes'][key] for key in RETIRED_SIZES}, RETIRED_SIZES)
        self.assertEqual(set(RETIRED_SIZES), {f'studio/interpretation/{name}.py' for name in sentinel.RETIRED_NAMES})
        self.assertTrue(all(size > 0 for size in RETIRED_SIZES.values()))

    def test_a_kept_module_or_jobs_names_a_retired_module_only_at_a_pinned_v1_branch(self):
        used, found = set(), []
        for name in sentinel.KEPT:
            found += retired_references(name, (PACKAGE / f'{name}.py').read_text(encoding='utf-8'),
                                        'studio.interpretation', used)
        found += retired_references('jobs', JOBS.read_text(encoding='utf-8'), 'studio', used)
        self.assertEqual(found, [])
        self.assertEqual(used, set(RETIRED_REFERENCES))  # no stale pin
        for key, why in RETIRED_REFERENCES.items():
            with self.subTest(pin=key):
                self.assertTrue(why.strip())
                self.assertIn(key[2], RETIRED_TARGETS)

    def test_no_production_module_names_a_retired_module_but_at_a_pinned_v1_branch(self):
        # refutation 6a-r1 F7: every production module of studio/ and cptstudio/ is read, not only the kept modules and
        # jobs.py - a consumer (customer_api, reports, views ...) importing a retired module or one of its patterns
        # would be no pinned v1 branch
        modules = production_modules()
        self.assertTrue({'customer_api', 'reports', 'views', 'review', 'jobs', 'adapter', 'store'}
                        <= {key.rpartition('.')[2] for key in modules})
        self.assertGreater(len(modules), 60)
        used, found = set(), []
        for key, (source, package) in modules.items():
            found += retired_references(key, source, package, used)
        self.assertEqual(found, [])
        self.assertEqual(used, set(RETIRED_REFERENCES))  # every pin met, and only by its own module
        planted = 'from .interpretation.literals import SIZE\n\ndef size_row(text):\n    return SIZE.search(text)\n'
        refused = retired_references('studio.customer_api', planted, 'studio')
        self.assertEqual(len(refused), 2, refused)  # the import and the read through it
        self.assertTrue(all('names the retired studio.interpretation.literals.SIZE' in item for item in refused))
        nested = 'def size_row(text):\n    from studio.interpretation import lexicon\n    return lexicon.negation(text)\n'
        self.assertTrue(retired_references('studio.management.commands.planted', nested, 'studio.management.commands'))

    def test_the_rules_refuse_a_planted_reference(self):
        planted = ('from studio.interpretation import lexicon\n'
                   'def f(text):\n'
                   '    from studio.interpretation.facts import day_of\n'
                   '    return lexicon.negation(text), day_of(text)\n')
        kept = retired_references('wording', planted, 'studio.interpretation')
        self.assertEqual(len(kept), 4, kept)  # both imports and both calls through them
        self.assertTrue(any('wording.f:' in item and 'studio.interpretation.facts.day_of' in item for item in kept))
        v2 = v2_package_violations('engine/planted', references(planted, 'studio.interpretation.engine', V2_ROOTS))
        self.assertTrue(any('names the retired studio.interpretation.lexicon' in item for item in v2), v2)
        self.assertTrue(any('names the retired studio.interpretation.facts.day_of' in item for item in v2), v2)
        # a pinned v1 branch is the pin's own: the same reference in another function of jobs.py is refused
        moved = 'def stage_planted(job):\n    from .interpretation import facts\n    return facts.derive\n'
        self.assertTrue(retired_references('jobs', moved, 'studio'))
        self.assertEqual(retired_references('jobs', moved.replace('stage_planted', 'derived_facts'), 'studio'), [])


# Refutation 6a-r1 F4 and F6: forms 5.7 measure 4 names that the first round let through, each refused (the finding's
# text expected) - and the scoping controls that must stay allowed
REFUTATION_WND_PLANTS = {
    'def f(assessment):\n    return assessment.revision.text\n': 'reads revision.text',
    'def f(job):\n    return len(job.revision.text)\n': 'reads revision.text',
    "def f(job):\n    return getattr(job.revision, 'text')\n": 'reads revision.text',
    "def f(revision):\n    return revision['text']\n": 'reads revision.text',
    "def f(row):\n    return row.get('text')\n": "reads ['text'] through get()",
    "def f(span):\n    return span.get('quote')\n": "reads ['quote'] through get()",
    "def f(row):\n    return row.pop('words', None)\n": "reads ['words'] through pop()",
    "def f(row):\n    return row.setdefault('unit_text', '')\n": "reads ['unit_text'] through setdefault()",
    "def f(row):\n    return row.__getitem__('text')\n": "reads ['text'] through __getitem__()",
    "from operator import itemgetter\ndef f(rows):\n    return list(map(itemgetter('quote'), rows))\n":
        "reads ['quote'] through itemgetter()",
    "import operator\ndef f(rows):\n    return list(map(operator.attrgetter('words'), rows))\n":
        "reads ['words'] through attrgetter()",
    'def f(items):\n    return list(map(str.lower, items))\n': 'names str.lower',
    "def f(value):\n    return str.startswith(value, 'no')\n": 'names str.startswith',
    "from operator import methodcaller\ndef f(items):\n    return list(map(methodcaller('startswith', 'no'), items))\n":
        "calls methodcaller('startswith')",
    "def f(value):\n    return value.__contains__('no')\n": 'tests membership against a string',
    "import operator\ndef f(value):\n    return operator.contains(value, 'no')\n": 'tests membership against a string',
    "def f(value):\n    match value:\n        case 'no' | 'not':\n            return True\n    return False\n":
        "matches a string pattern ('no', 'not')",
    "def f(value):\n    match value:\n        case {'no': x}:\n            return x\n": "matches a string pattern ('no')",
    "def f(value):\n    words = ('no', 'not', 'without')\n    return value in words\n":
        'tests membership against a string (through words)',
    "WORDS = frozenset({'no', 'not'})\ndef f(value):\n    return value not in WORDS\n":
        'tests membership against a string (through WORDS)',
    "NEG = 'no'\ndef f(text):\n    return NEG in text\n": 'tests membership against a string (through NEG)',
    "def f(text):\n    for word in ('no', 'not'):\n        if word in text:\n            return True\n":
        'tests membership against a string (through word)',
    "def f(text):\n    return any(word in text for word in ('no', 'not'))\n":
        'tests membership against a string (through word)',
    "def f(value):\n    return value in ('without',) + ('not',)\n": 'tests membership against a string',
    # the display rule follows an f-string's and a join's result (refutation 6a-r1 F6)
    "from studio.interpretation import wording\ndef f(span):\n    return f'{wording.quote(span)}' == 'x'\n":
        'uses the display value of wording.quote',
    "from studio.interpretation import wording\ndef f(span):\n    shown = f'{wording.quote(span)}'\n"
    '    if shown:\n        return 1\n': 'uses the display value of wording.quote',
    "from studio.interpretation import wording\ndef f(spans):\n    return ', '.join(wording.quote(s) for s in spans)[0]\n":
        'uses the display value of wording.quote',
}
# Refutation 6a-r2b P2 (DECISIONS D245): the five forms that passed round 2 - a literal's split, a string receiver searched
# by a call, an enclosing function's binding, a class attribute, an aliased revision.text - and, in engine/, a comparison
# with a string (5.7 measure 4's intent). Each refused, the finding's text expected (read as engine/ unless the plant
# names its module); R2B_WND_ANYWHERE are refused in every module WordsNeverDecide reads, not only in engine/
REFUTATION_R2B_PLANTS = {
    "NEGATIONS = 'no not without denies'.split()\ndef f(token):\n    return token in NEGATIONS\n":
        'tests membership against a string (through NEGATIONS)',
    "def f(token):\n    words = 'no not without'.split()\n    return token in words\n":
        'tests membership against a string (through words)',
    "def f(token):\n    return token in 'no not without'.split()\n": 'tests membership against a string',
    "WORDS = str.split('no not without')\ndef f(token):\n    return token in WORDS\n":
        'tests membership against a string (through WORDS)',
    "WORDS = frozenset('no,not'.split(','))\ndef f(token):\n    return token not in WORDS\n":
        'tests membership against a string (through WORDS)',
    "WORDS = dict.fromkeys(('no', 'not'))\ndef f(token):\n    return token in WORDS\n":
        'tests membership against a string (through WORDS)',
    "def f(token):\n    return ('no', 'not', 'without').__contains__(token)\n":
        'tests membership against a string (a string receiver searched by .__contains__())',
    "def f(token):\n    return 'no not without'.__contains__(token)\n":
        'tests membership against a string (a string receiver searched by .__contains__())',
    "def f(token):\n    return 'no not without'.find(token) >= 0\n":
        'tests membership against a string (a string receiver searched by .find())',
    "WORDS = ('no', 'not')\ndef f(token):\n    return WORDS.__contains__(token)\n":
        'tests membership against a string (a string receiver searched by .__contains__())',
    "def f(token):\n    words = ('no', 'not', 'without')\n    def inner():\n        return token in words\n"
    '    return inner()\n': 'tests membership against a string (through words)',
    "def f(token):\n    words = ('no', 'not')\n    def middle():\n        def inner():\n            return token in words\n"
    '        return inner()\n    return middle()\n': 'tests membership against a string (through words)',
    # a nested function's nonlocal says nothing of the scope that reads the name
    "def f(token):\n    words = ('no', 'not')\n    def inner():\n        nonlocal words\n        words = ()\n"
    '    inner()\n    return token in words\n': 'tests membership against a string (through words)',
    "class K:\n    WORDS = ('no', 'not', 'without')\n\ndef f(token):\n    return token in K.WORDS\n":
        'tests membership against a string (through K.WORDS)',
    "class K:\n    WORDS: tuple = ('no', 'not')\n    def f(self, token):\n        return token in self.WORDS\n":
        'tests membership against a string (through self.WORDS)',
    "def f(job):\n    source = job.revision\n    return source.text == 'No biopsy was taken.'\n":
        'reads revision.text (through source)',
    "def f(job):\n    rev = getattr(job, 'revision')\n    return len(rev.text)\n": 'reads revision.text (through rev)',
    "def f(job):\n    rev = job.reading\n    return getattr(rev, 'text')\n": 'reads reading.text (through rev)',
    "def f(sentence):\n    return sentence == 'No biopsy was taken.'\n": "compares with the string 'No biopsy was taken.'",
    "def f(token):\n    return token != 'no'\n": "compares with the string 'no'",
    "W = 'no'\ndef f(token):\n    return token == W\n": 'compares with a string (through W)',
    "class K:\n    W = 'no'\n\ndef f(token):\n    return K.W == token\n": 'compares with a string (through K.W)',
    "def f(token, w):\n    return token == f'{w}'\n": 'compares with an f-string',
}
R2B_WND_ANYWHERE = tuple(plant for plant, expected in REFUTATION_R2B_PLANTS.items() if 'compares with' not in expected)
REFUTATION_R2B_CONTROLS = (
    "def f(value):\n    return value == ''\n",  # the empty string: presence, never a word
    'def f(kind):\n    return kind == Kind.SNARE\n',  # an Enum member
    'def f(count):\n    return count == 3\n',
    "def f(kind):\n    kinds = (Kind.SNARE, Kind.BIOPSY)\n    def inner():\n        return kind in kinds\n"
    '    return inner()\n',  # an enclosing function's binding of Enum members
    "def f(token):\n    words = ('no',)\n    def inner(words):\n        return token in words\n    return inner(())\n",
    "class Rule(Enum):\n    ROUTE = 'route'\n\ndef f(rule):\n    return rule == Rule.ROUTE\n",  # an Enum's member
    "class K:\n    KINDS = (Kind.SNARE,)\n\ndef f(kind):\n    return kind in K.KINDS\n",
    "def f(value):\n    return 'x'.find('x')\n",  # a literal searched for a literal: no value is tested
    "def f():\n    return len('a b'.split())\n",  # a literal's split, counted: no value is tested against its words
)
REFUTATION_WND_CONTROLS = (
    'def f(value, words):\n    return value in words\n',  # a parameter: bound to nothing readable here
    "WORDS = ('no',)\ndef f(value):\n    WORDS = {Kind.SNARE}\n    return value in WORDS\n",  # the local binding
    "def f(value):\n    for name, found in ITEMS:\n        if name in value:\n            return found\n",
    "def f(kind):\n    match kind:\n        case Kind.SNARE:\n            return 1\n",  # an Enum member, not a string
    "def f(row):\n    return row.get('kind')\n",  # not a text name
    "from studio.interpretation import wording\ndef f(text, s):\n    return f'{wording.quote_span(text, s)}'\n",  # returned
    "from studio.interpretation import wording\ndef f(text, s, held):\n"
    "    return HeldFact(fact=held, quote=f'«{wording.quote_span(text, s)}»')\n",
)


class NestedModuleTests(SimpleTestCase):
    """Refutation 6a-r1 F3: the rules read contract/ and engine/ to every depth - the depth sentinel.expected_retired
    accepts code at - so a module nested below them is held to the same rules as a top-level one."""

    def test_a_nested_module_is_read_by_every_rule(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'interpretation'
            for name in sentinel.KEPT + sentinel.RETIRED_NAMES:
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f'{name}.py').write_text('', encoding='utf-8')
            for package in sentinel.NEW_PACKAGES:
                (folder / package).mkdir()
                (folder / package / '__init__.py').write_text('', encoding='utf-8')
            nested = folder / 'engine' / 'rules'
            nested.mkdir()
            (nested / '__init__.py').write_text('', encoding='utf-8')
            denial = "import re\nfrom ... import lexicon\nNEG = ('no', 'not')\n"
            (nested / 'denial.py').write_text(denial, encoding='utf-8')
            (folder / 'contract' / 'deep' / 'deeper').mkdir(parents=True)
            (folder / 'contract' / 'deep' / 'deeper' / 'geometry_helper.py').write_text("W = ['no', 'nor']\n",
                                                                                        encoding='utf-8')
            sentinel.check_retired_list(root)  # the sentinel accepts nested code under contract/ and engine/ ...
            modules = package_modules(folder)  # ... and the rules read it
            self.assertIn('engine/rules/denial', modules)
            self.assertIn('engine/rules/__init__', modules)
            self.assertIn('contract/deep/deeper/geometry_helper', modules)
            self.assertEqual(modules['engine/rules/denial'], denial)
        self.assertEqual(module_package('engine/rules/denial'), 'studio.interpretation.engine.rules')
        self.assertEqual(module_package('engine/facts'), 'studio.interpretation.engine')
        self.assertEqual(module_package('overlay'), 'studio.interpretation')
        found = words_never_decide(denial, 'engine/rules/denial')
        self.assertTrue(any('imports re' in item for item in found), found)
        self.assertTrue(any('imports the retired studio.interpretation.lexicon' in item for item in found), found)
        self.assertTrue(no_word_lists(denial, 'engine/rules/denial'))
        self.assertTrue(no_word_lists("W = ['no', 'nor']\n", 'contract/deep/deeper/geometry_helper'))
        refs = references(denial, module_package('engine/rules/denial'), V2_ROOTS)
        self.assertTrue(any('names the retired studio.interpretation.lexicon' in item
                            for item in v2_package_violations('engine/rules/denial', refs)))
        # the real tree: every module of contract/ and engine/ at every depth is in WordsNeverDecide's and NoWordLists'
        # readings
        self.assertEqual({key for key in _scope() if key.startswith('engine/')},
                         {key for key in v2_files() if key.startswith('engine/')})
        self.assertEqual(set(_v2_modules()), set(v2_files()))


class WordsNeverDecideTests(SimpleTestCase):
    def test_the_scope_holds_and_every_pin_is_met(self):
        scope = _scope()
        self.assertTrue({'engine/assess', 'engine/evaluate', 'engine/facts', 'engine/pairing', 'contract/settle',
                         'contract/claims', 'contract/consistency', 'overlay', 'readers'} <= set(scope))
        self.assertEqual(len([key for key in scope if key.startswith('engine/')]),
                         len([path for path in (PACKAGE / 'engine').rglob('*.py') if '__pycache__' not in path.parts]))
        used, found = set(), []
        for key, source in scope.items():
            found += words_never_decide(source, key, used)
        self.assertEqual(found, [])
        self.assertEqual(used, set(WND_PINS) | {L1_EXEMPTION} | set(DISPLAY_BUILDERS) | set(DISPLAY_RECORDS))
        for table in (WND_PINS, DISPLAY_BUILDERS, DISPLAY_RECORDS):
            for key, why in table.items():
                with self.subTest(pin=key):
                    self.assertTrue(why.strip())
                    self.assertIn(key[0], scope)

    def test_the_display_helpers_are_the_text_copying_ones(self):
        helpers = wording_helpers()
        self.assertTrue({'quote', 'quote_span', 'span_text', 'excerpt', 'build', 'question', 'explanation',
                         'act_phrase'} <= helpers, sorted(helpers))
        self.assertFalse({'event_kind_label', 'landmark_label', 'service_phrase', 'join', 'family_label'} & helpers)
        from studio.interpretation import wording

        for name in helpers:
            self.assertTrue(callable(getattr(wording, name)), name)

    def test_each_form_is_refused(self):
        plants = {
            'import re\n': 'imports re',
            'import regex\n': 'imports regex',
            'from unicodedata import category\n': 'imports unicodedata',
            'import difflib\n': 'imports difflib',
            'from fnmatch import fnmatch\n': 'imports fnmatch',
            'from studio.interpretation import lexicon\n': 'imports the retired studio.interpretation.lexicon',
            'from studio.interpretation.literals import dates\n': 'imports the retired studio.interpretation.literals',
            'from studio.interpretation import facts\n': 'imports the retired studio.interpretation.facts',
            'def f():\n    from studio.interpretation.verify import status_words\n': 'imports the retired',
            'from studio.gi import lexicon\n': 'imports studio.gi.lexicon',
            'from studio.interpretation.contract import segment\n': 'imports the text module',
            'from studio.interpretation.contract.geometry import bind_words\n': 'imports the text module',
            'from studio.interpretation.contract import fold\n': 'imports the text module',
            'from studio.interpretation.contract import date_literals\n': 'imports the text module',
            "import importlib\nX = importlib.import_module('re')\n": 'imports re',
            'import importlib\ndef f(name):\n    return importlib.import_module(name)\n': 'imports by a computed name',
            'def f(fact):\n    return fact.text\n': 'reads .text',
            'def f(fact):\n    return fact.words\n': 'reads .words',
            'def f(fact):\n    return fact.quote\n': 'reads .quote',
            'def f(fact):\n    return fact.unit_text\n': 'reads .unit_text',
            "def f(row):\n    return row['words']\n": "reads ['words']",
            "def f(row):\n    return getattr(row, 'text')\n": "reads getattr(..., 'text')",
            'def f(reading):\n    return reading.text\n': 'reads reading.text',
            'def f(revision):\n    return revision.text\n': 'reads revision.text',
            "def f(value):\n    return getattr(value, 'startswith')('no')\n": "calls getattr(..., 'startswith')",
            'def f(value):\n    return "no" in value\n': 'tests membership against a string',
            "def f(value):\n    return value in ('no', 'not')\n": 'tests membership against a string',
            "def f(value):\n    return value not in 'abc'\n": 'tests membership against a string',
            "def f(value, w):\n    return value in f'{w}'\n": 'tests membership against a string',
            'NEG = "no"\ndef f(t, a):\n    return NEG in t[a:a + 2]\n': 'compares a slice with a string',
            'W = "no"\ndef f(t, a):\n    return t[a:a + 2] == W\n': 'compares a slice with a string',
            "def f(t, a):\n    return t[a:a + 2] == 'no'\n": 'compares a slice with a string',
            # the display rule: a display helper's value never decided on
            'from studio.interpretation import wording\ndef f(text, span):\n'
            '    if wording.quote_span(text, span):\n        return 1\n': 'uses the display value of wording.quote_span',
            "from studio.interpretation import wording\ndef f(text):\n    return wording.quote(text) == 'x'\n":
                'uses the display value of wording.quote',
            'from studio.interpretation import wording\ndef f(text):\n    return wording.excerpt(text).lower()\n':
                'uses the display value of wording.excerpt',
            'from studio.interpretation import wording\ndef f(text):\n    words = wording.quote(text)\n'
            '    return words[0]\n': 'uses the display value of wording.quote',
            'from studio.interpretation.wording import span_text\ndef f(text, s):\n    shown = span_text(text, s)\n'
            '    return 1 if shown else 0\n': 'uses the display value of span_text',
        }
        for method in STR_METHODS:
            plants[f'def f(value):\n    return value.{method}("x")\n'] = f'calls .{method}() on a value'
        plants.update(REFUTATION_WND_PLANTS)
        plants.update(REFUTATION_R2B_PLANTS)
        for plant, expected in plants.items():
            with self.subTest(plant=plant.strip()):
                found = words_never_decide(plant, 'engine/planted')
                self.assertTrue(any(expected in item for item in found), found)
        # refutation 6a-r2b P2: the five forms are refused in every module WordsNeverDecide reads; the comparison with a
        # string is engine/'s alone (overlay, readers and settle read their own records' strings)
        for module in ('overlay', 'readers', 'contract/settle', 'contract/claims', 'contract/consistency'):
            for plant in R2B_WND_ANYWHERE:
                with self.subTest(module=module, plant=plant.strip()):
                    self.assertTrue(any(REFUTATION_R2B_PLANTS[plant] in item
                                        for item in words_never_decide(plant, module)), module)
            with self.subTest(module=module, plant='a comparison with a string'):
                self.assertEqual(words_never_decide("def f(s):\n    return s == 'No biopsy was taken.'\n", module), [])
        # reading.text and revision.text through an attribute are refused outside engine/ too (refutation 6a-r1 F4)
        for module in ('overlay', 'readers', 'contract/settle', 'contract/claims', 'contract/consistency'):
            with self.subTest(module=module):
                self.assertTrue(words_never_decide('def f(assessment):\n    return assessment.revision.text\n', module))
                self.assertTrue(words_never_decide('def f(job):\n    return len(job.reading.text)\n', module))
        # outside engine/ the text-name rule is engine's alone; reading.text and revision.text are refused anywhere
        self.assertEqual(words_never_decide('def f(row):\n    return row.text\n', 'overlay'), [])
        self.assertTrue(words_never_decide('def f(revision):\n    return revision.text\n', 'overlay'))
        # settle has no L1 exemption (D206; 3a's R7); consistency has exactly date_literals
        literal = 'from studio.interpretation.contract import date_literals\n'
        self.assertTrue(words_never_decide(literal, 'contract/settle'))
        self.assertEqual(words_never_decide(literal, 'contract/consistency'), [])
        self.assertTrue(words_never_decide('from studio.interpretation.contract import geometry\n',
                                           'contract/consistency'))

    def test_the_allowed_forms_pass(self):
        controls = (
            *REFUTATION_WND_CONTROLS,
            *REFUTATION_R2B_CONTROLS,
            "def f(items):\n    return ', '.join(items)\n",
            'def f(value):\n    return value.isdigit()\n',  # a proposal code's digits (1e:R6): not in the list
            'def f(kind):\n    return kind in {Kind.SNARE, Kind.BIOPSY}\n',
            "def f(value):\n    return 'x'.upper()\n",
            'from studio.interpretation.engine import facts\ndef f(R):\n    return facts.effective(R)\n',
            # a display helper's value as 5.7 measure 4 allows it
            "from studio.interpretation import wording\ndef f(text, s):\n    return f'{wording.quote_span(text, s)}'\n",
            'from studio.interpretation import wording\ndef f(text, s):\n'
            '    return wording.join([wording.quote_span(text, s)])\n',
            'from studio.interpretation import wording\ndef f(text, s, held):\n'
            '    return HeldFact(fact=held, quote=wording.quote_span(text, s))\n',
            'from studio.interpretation import wording\ndef f(text, s):\n'
            '    shown = wording.quote_span(text, s) if s else None\n    return Clarification(question=shown)\n',
            "from studio.interpretation import wording\ndef f(text, items):\n"
            "    return ', '.join(sorted({wording.excerpt(text) for item in items}))\n",
        )
        for control in controls:
            with self.subTest(control=control.strip()):
                self.assertEqual(words_never_decide(control, 'engine/planted'), [])
        # a display builder returns a display value, and its own value goes on to an allowed use (overlay's _words)
        builder = ('from studio.interpretation import wording\n'
                   'def _words(item, slots):\n    return wording.build(wording.Message(item), slots, "")\n'
                   'def g(item, slots):\n    worded = _words(item, slots) if item else None\n'
                   '    return Live(worded=worded)\n')
        self.assertEqual(words_never_decide(builder, 'overlay'), [])
        self.assertTrue(words_never_decide(builder.replace('Live(worded=worded)', 'worded is None'), 'overlay'))
        self.assertTrue(words_never_decide(builder, 'readers'))  # the builder and the record are overlay's pins

    def test_derive_takes_the_two_forms_the_triage_allows_and_their_planted_variants_are_refused(self):
        # triage 2d:R7: derive's _trimmed (member input trimmed by str.isspace) and context_of's display-only quote
        # (studio.types.from_jsonable over the stored span) are allowed - by what they are, which the rule reads
        source = (PACKAGE / 'engine' / 'derive.py').read_text(encoding='utf-8')
        self.assertEqual(words_never_decide(source, 'engine/derive'), [])
        self.assertIn('value[start].isspace()', source)
        self.assertIn('from_jsonable(studio_types.Span, span)', source)
        stripped = source.replace('    while start < end and value[start].isspace():', '    value = value.strip()\n'
                                  '    while start < end and value[start].isspace():')
        self.assertNotEqual(stripped, source)
        self.assertTrue(any('calls .strip()' in item for item in words_never_decide(stripped, 'engine/derive')))
        quoted = source.replace('from_jsonable(studio_types.Span, span)', "from_jsonable(studio_types.Span, span['text'])")
        self.assertNotEqual(quoted, source)
        self.assertTrue(any("reads ['text']" in item for item in words_never_decide(quoted, 'engine/derive')))

    def test_the_overlay_pin_is_its_own_form_alone(self):
        source = (PACKAGE / 'overlay.py').read_text(encoding='utf-8')
        self.assertIn("field[:len(_PFS_PREFIX)] == _PFS_PREFIX", source)
        planted = source + "\n\ndef _pfs_other(field):\n    return field[:4] == _PFS_PREFIX\n"
        found = words_never_decide(planted, 'overlay')
        self.assertTrue(any('compares a slice with a string' in item for item in found), found)
        self.assertEqual(len(found), 1, found)


class NoWordListsTests(SimpleTestCase):
    def test_contract_and_engine_hold(self):
        values, found = _design_values(), []
        modules = _v2_modules()
        self.assertGreater(len(modules), 25)
        for key, source in modules.items():
            found += no_word_lists(source, key, values)
        self.assertEqual(found, [])
        self.assertGreater(len(values), 300)  # it read the design's enumerations

    def test_each_output_table_is_covered_by_its_version_pin(self):
        from studio import interpretation
        from studio.interpretation.contract import claims, extract_prompt, extract_schema, jsonschema

        modules = {'contract/claims': claims, 'contract/extract_schema': extract_schema}
        documents = {'TEMPLATES_SHA256': claims.templates_document(),
                     'STATEMENT_TEMPLATES_SHA256': claims.statement_templates_document(),
                     'INSTRUCTIONS_SHA256_V2': extract_prompt.INSTRUCTIONS_2}
        for name, document in documents.items():
            with self.subTest(pin=name):
                self.assertEqual(jsonschema.sha256_of(document), getattr(interpretation, name))
        rendered = jsonschema.canonical(documents['TEMPLATES_SHA256']).decode('utf-8')
        for (module, table), pin in OUTPUT_TABLES.items():
            with self.subTest(table=(module, table)):
                value = getattr(modules[module], table)
                self.assertTrue(len(value) >= 2)
                texts = [text for text in value.values()] if hasattr(value, 'values') else list(value)
                for text in texts:
                    forms = text if isinstance(text, (tuple, list)) else (text,)
                    for form in forms:
                        covered = (form in documents[pin] if pin == 'INSTRUCTIONS_SHA256_V2'
                                   else json_in(form, documents[pin] if pin != 'TEMPLATES_SHA256' else rendered))
                        self.assertTrue(covered, (table, form[:60]))
        self.assertEqual(set(OUTPUT_TABLES.values()), set(documents))

    def test_the_keyword_enum_is_named_apart(self):
        from studio.interpretation.contract import jsonschema

        values = _design_values()
        for (module, name), why in KEYWORD_ENUMS.items():
            with self.subTest(enum=name):
                self.assertTrue(why.strip())
                found = getattr(jsonschema, name)
                self.assertTrue(issubclass(found, enum.Enum))
                # not a design enumeration: most of its keywords are no design value
                self.assertTrue({member.value for member in found} - values)
        # so a module-level collection of those keywords is a word list, the Enum notwithstanding
        self.assertTrue(no_word_lists("KEYS = ('type', 'properties')\n", 'contract/jsonschema', values))

    def test_each_form_is_refused_and_the_allowed_ones_pass(self):
        values = _design_values()
        plants = ("MARKERS = ('no', 'not')\n", "TABLE = {'denied': 1, 'without': 2}\n", "W = ['no', 'nor']\n",
                  "W: tuple = ('today', 'this morning')\n", "X = frozenset({'denied', 'without'})\n",
                  "class K:\n    WORDS = ('no', 'neither')\n", "DASHES = frozenset('-\u2010')\n",
                  "M = {Kind.SNARE: ('removed', 'snared')}\n", "N = ('snare', 'removed')\n",
                  "class R:\n    __slots__ = ('no', 'not a name')\n",
                  # refutation 6a-r1 F6: a word list built by concatenation or union
                  "WORDS = ('without',) + ('not',)\n", "WORDS = frozenset({'no'}) | frozenset({'not'})\n",
                  "WORDS = ['no'] + ['nor']\n",
                  # refutation 6a-r2b P2: a literal's split is a word list, however it is wrapped or reached
                  "NEGATIONS = 'no not without denies'.split()\n", "WORDS = str.split('no not without')\n",
                  "WORDS = frozenset('no not'.split())\n", "WORDS = 'no,not'.split(',')\n",
                  "WORDS = 'no\\nnot'.splitlines()\n", "class K:\n    WORDS = 'no not without'.split()\n",
                  "WORDS = dict.fromkeys(('no', 'not'))\n")
        for plant in plants:
            with self.subTest(plant=plant.strip()):
                self.assertTrue(no_word_lists(plant, 'engine/planted', values))
        controls = ("K = (Kind.SNARE,) + (Kind.BIOPSY,)\n", "K = ('snare',) + ('biopsy',)\n",
                    "K = 'snare biopsy'.split()\n",  # design values, split or not
                    "SEPARATOR = ', '.split()\n",  # one item: no list of words
                    "S = 'abc'.upper()\n",
                    "R = {Link.FRAME: Reason.GEOMETRY_FRAME}\n", 'SIZE = 12\n', "LIMIT = ('.',)\n",
                    "K = ('snare', 'biopsy')\n", "class Kind(Enum):\n    SNARE = 'snare'\n    NO = 'no'\n",
                    "class R:\n    __slots__ = ('R', 'order')\n")
        for control in controls:
            with self.subTest(control=control.strip()):
                self.assertEqual(no_word_lists(control, 'engine/planted', values), [])
        # an OUTPUT table is its module's own pin: the same name elsewhere, or a new table there, is a word list
        self.assertEqual(no_word_lists("TEMPLATES = ('A {x}.', 'B {y}.')\n", 'contract/claims', values), [])
        self.assertTrue(no_word_lists("TEMPLATES = ('A {x}.', 'B {y}.')\n", 'engine/planted', values))
        self.assertTrue(no_word_lists("PHRASES = ('A {x}.', 'B {y}.')\n", 'contract/claims', values))

    def test_date_literals_is_closed_by_its_pin(self):
        # the one exempt module (5.7 measure 4), closed by pinning: test_date_literals.pin_findings, the one copy of the
        # pin (hand-off 1c#6, the integration's O1), holds its top level to v1's eight functions, header and tables
        from tests.v2 import test_date_literals

        path = PACKAGE / 'contract' / 'date_literals.py'
        source = path.read_text(encoding='utf-8')
        self.assertIn('contract/date_literals', NO_WORD_LISTS_EXEMPT)
        self.assertEqual(test_date_literals.pin_findings(source), [])
        self.assertTrue(no_word_lists("_FRAMES = ('today', 'yesterday')\n", 'contract/segment'))
        plants = {
            'a timing frame list under a date-literal name': source.replace(
                "'sep', 'oct', 'nov', 'dec')", "'sep', 'oct', 'nov', 'dec', 'today')"),
            'a new module-level string collection': source + "\n_FRAMES = ('today', 'yesterday', 'tonight')\n",
            "a parser no longer v1's": source.replace('def dates(', 'def dates_(', 1),
        }
        for what, planted in plants.items():
            with self.subTest(plant=what):
                self.assertNotEqual(planted, source)  # the plant is applied
                self.assertTrue(test_date_literals.pin_findings(planted))


def json_in(form: str, rendered) -> bool:
    """Whether the text ``form`` is inside ``rendered`` (canonical JSON text, or a document to render as such)."""
    from studio.interpretation.contract import jsonschema

    text = rendered if isinstance(rendered, str) else jsonschema.canonical(rendered).decode('utf-8')
    return jsonschema.canonical(form).decode('utf-8')[1:-1] in text


class SingleCharacterGeometryTests(SimpleTestCase):
    def test_segment_and_geometry_hold(self):
        modules = package_modules()
        for key in GEOMETRY_MODULES:
            with self.subTest(module=key):
                self.assertEqual(single_character_geometry(modules[key], key), [])

    def test_each_form_is_refused(self):
        plants = {
            'import re\n': 'imports re',
            'from unicodedata import category\n': 'imports unicodedata',
            "def f(c):\n    return c == 'no'\n": "compares with 'no'",
            "def f(c):\n    return c in '.!?'\n": "compares with '.!?'",
            "def f(c):\n    return c not in ('no', 'x')\n": "compares with 'no'",
            "def f(t):\n    return t.startswith('No')\n": 'calls .startswith()',
            "def f(t):\n    return t.find('no')\n": 'calls .find()',
            'def f(t, w):\n    return t.find(w)\n': 'calls .find()',
            "def f(t):\n    return ''.join(t)\n": 'calls .join()',
            'def f(t):\n    return t.istitle()\n': 'calls .istitle()',
            'def f(t):\n    return t.isdigit()\n': 'calls .isdigit()',
            'def f(t):\n    return t.split()\n': 'calls .split()',
            # DECISIONS D205's three forms the interim checker missed
            "def f(t):\n    return getattr(t, 'startswith')('No')\n": "calls getattr(..., 'startswith')",
            'NEG = "no"\ndef f(t, a):\n    return NEG in t[a:a + 2]\n': 'compares a slice with a named string',
            'W = "no"\ndef f(t, a):\n    return t[a:a + 2] == W\n': 'compares a slice with a named string',
            'def f(t, a):\n    return int(t[a:a + 2])\n': 'calls int() on more than one character',
            'def f(t):\n    return int(t)\n': 'calls int() on more than one character',
            'def f(t, a):\n    if t[a:a + 2]:\n        return 1\n': 'judges a slice of the text',
            "def f(t):\n    return eval('t')\n": 'calls eval()',
            # refutation 6a-r1 F5
            "def f(t, a):\n    match t[a:a + 2]:\n        case 'no':\n            return True\n    return False\n":
                'judges a slice of the text',
            "def f(t, a):\n    match t[a]:\n        case 'no' | 'x':\n            return True\n": "compares with 'no'",
            "def f(t):\n    return t.__contains__('no')\n": 'calls .__contains__()',
            "def f(t):\n    return t.__eq__('no')\n": 'calls .__eq__()',
            "def f(t):\n    return getattr(t, '__contains__')('no')\n": "calls getattr(..., '__contains__')",
            "def f(t, a):\n    return {'no': 1}.get(t[a:a + 2])\n": 'judges a slice of the text',
            'def f(t, a, table):\n    return table.get(key=t[a:a + 2])\n': 'judges a slice of the text',
            'def f(t, a):\n    return hash(t[a:a + 2])\n': 'judges a slice of the text',
        }
        for plant, expected in plants.items():
            with self.subTest(plant=plant.strip()):
                found = single_character_geometry(plant, 'planted')
                self.assertTrue(any(expected in item for item in found), found)

    def test_the_admitted_forms_pass(self):
        controls = ("def f(c):\n    return c == '.'\n", "def f(t):\n    return t.find('.', 3)\n",
                    'def f(t):\n    return t[0].isspace()\n', "ENDS = ('.',)\n", 'SIZE = 600\n',
                    'def f(t, at):\n    return t[at].isalpha() and t[at].isupper()\n',  # D205's two classes
                    'def f(t, at):\n    return int(t[at])\n',  # D205: one character
                    'def f(t, a, b, out):\n    out += t[a:b]\n    return out\n',  # D205: a copy
                    'def f(t, a, b):\n    return Located(a, b, t[a:b])\n',  # geometry: the located words copied
                    "def f(c):\n    match c:\n        case '.':\n            return 1\n",  # one character
                    'class K(Base):\n    def __init__(self):\n        super().__init__()\n')  # object's protocol
        for control in controls:
            with self.subTest(control=control.strip()):
                self.assertEqual(single_character_geometry(control, 'planted'), [])


class TypingFenceTests(SimpleTestCase):
    """FINAL-V2 5.7 measure 5: mypy --strict over engine/types.py, engine/facts.py and engine/reading.py - FactSet values
    are Enum members and ids, so a string operation on a fact value is a type error at the boundary."""

    def mypy(self, *arguments):
        return subprocess.run([sys.executable, '-m', 'mypy', '--strict', '--follow-imports=silent', '--cache-dir',
                               os.devnull, *arguments], capture_output=True, text=True, timeout=900, cwd=APP)

    def test_mypy_strict_passes_on_the_three_and_refuses_a_string_operation_on_a_fact_value(self):
        result = self.mypy(*MYPY_FENCE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f'Success: no issues found in {len(MYPY_FENCE)} source files', result.stdout)
        probe = self.mypy('-c', 'from studio.interpretation.engine.types import Fact\n'
                                'def probe(fact: Fact) -> bool:\n'
                                '    return fact.value.startswith("x") if fact.value is not None else False\n')
        self.assertEqual(probe.returncode, 1, probe.stdout + probe.stderr)  # the positive control
        self.assertIn('has no attribute "startswith"', probe.stdout)


SEAMS = ('retired_unarmed', 'strict')  # the sentinel's test-only helpers that leave the RETIRED kind unarmed
# Refutation 6a-r1 F2: sentinel.strict() without retired=True is v1's instrument - the RETIRED kind unarmed while it is
# open - so a v2-path check made with it cannot see a retired call. Every test that opens it so (the sentinel's own
# tests aside: they test both modes) is pinned here with why; a new one fails, so a v2-path use of the default arrives
# deliberately or not at all. (test module, test function) -> why.
STRICT_V1_INSTRUMENT = {
    ('test_interpretation_assess', 'test_strict_mode_shows_zero_denied_executions_on_every_path'):
        "S08, v1's events engine (a retired module) recorded with v1's instrument; v1's own tests keep running as the "
        'record of v1 (FINAL-V2 5.0) and no step edits them (8.0)',
    ('test_interpretation_assess', 'test_the_instrument_is_live_a_planted_legacy_call_trips_it'):
        "S08's positive control, the same instrument (a retired module's own test)",
}
SENTINEL_OWN_TESTS = 'test_interpretation_sentinel'  # the instrument's own tests: both modes, each named


def v1_instrument_uses(source: str) -> list:
    """[(line, enclosing function)] of each ``strict(...)`` call in ``source`` that does not pass retired=True - v1's
    instrument (refutation 6a-r1 F2)."""
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    out = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _call_name(node) == 'strict'):
            continue
        if any(item.arg == 'retired' and isinstance(item.value, ast.Constant) and item.value.value is True
               for item in node.keywords):
            continue
        function = node
        while function is not None and not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
            function = parents.get(function)
        out.append((node.lineno, function.name if function is not None else '<module>'))
    return out


def seam_uses(source: str) -> list:
    """Each use in ``source`` of a sentinel helper that leaves the RETIRED kind unarmed (SEAMS): ``<sentinel>.<seam>``
    under the module's own name or an alias it is imported as, ``getattr(<sentinel>, '<seam>')``, or the name imported
    from the sentinel module. Dynamic access by a computed name escapes it, as any static pin."""
    tree = ast.parse(source)
    aliases = {'sentinel'}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            aliases |= {alias.asname for alias in node.names if alias.asname and alias.name.endswith('.sentinel')}
        elif isinstance(node, ast.ImportFrom):
            aliases |= {alias.asname for alias in node.names if alias.asname and alias.name == 'sentinel'}

    def held(node) -> bool:
        return ((isinstance(node, ast.Name) and node.id in aliases)
                or (isinstance(node, ast.Attribute) and node.attr in aliases))

    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in SEAMS and held(node.value):
            found.append(f'{node.lineno}: sentinel.{node.attr}')
        elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'getattr'
              and len(node.args) >= 2 and held(node.args[0]) and isinstance(node.args[1], ast.Constant)
              and node.args[1].value in SEAMS):
            found.append(f'{node.lineno}: getattr(sentinel, {node.args[1].value!r})')
        elif isinstance(node, ast.ImportFrom) and (node.module or '').endswith('sentinel'):
            found += [f'{node.lineno}: from {node.module} import {alias.name}' for alias in node.names
                      if alias.name in SEAMS or alias.name == '*']
    return found


class RetiredSeamTests(SimpleTestCase):
    def test_no_module_outside_tests_names_the_v1_chains_seam(self):
        # sentinel.retired_unarmed is the test-only v1 chain's seam and sentinel.strict opens it by default (v1's
        # instrument): the application never calls either (only tests/ may), so production keeps the RETIRED kind armed
        roots = [APP / 'studio', APP / 'cptstudio', APP / 'ops', APP / 'scripts']
        found = []
        for root in roots:
            for path in root.rglob('*.py'):
                if path.name.startswith('test_') or path == PACKAGE / 'sentinel.py':
                    continue
                source = path.read_text(encoding='utf-8')
                if 'retired_unarmed' in source:
                    found.append(str(path.relative_to(APP)))
                found += [f'{path.relative_to(APP)}:{use}' for use in seam_uses(source)]
        self.assertEqual(found, [])
        sentinel_source = (PACKAGE / 'sentinel.py').read_text(encoding='utf-8')
        self.assertIn('def retired_unarmed(', sentinel_source)  # the control
        self.assertIn('def strict(', sentinel_source)

    def test_every_test_using_strict_as_v1s_instrument_is_pinned(self):
        # refutation 6a-r1 F2: strict() without retired=True cannot see the RETIRED kind; every such use is pinned
        found = set()
        for path in sorted((APP / 'tests').rglob('*.py')):
            if '__pycache__' in path.parts or path.stem == SENTINEL_OWN_TESTS:
                continue
            found |= {(path.stem, function) for _, function in v1_instrument_uses(path.read_text(encoding='utf-8'))}
        self.assertEqual(found - set(STRICT_V1_INSTRUMENT), set())  # no unpinned use
        self.assertEqual(set(STRICT_V1_INSTRUMENT) - found, set())  # no stale pin
        self.assertTrue(all(why.strip() for why in STRICT_V1_INSTRUMENT.values()))
        own = v1_instrument_uses((APP / 'tests' / f'{SENTINEL_OWN_TESTS}.py').read_text(encoding='utf-8'))
        self.assertTrue(own)  # the instrument's own tests use both modes
        planted = ('from studio.interpretation import sentinel\n'
                   'def test_a_new_v2_check(self):\n    with sentinel.strict("v2 path"):\n        pass\n'
                   'def test_a_measured_check(self):\n    with sentinel.strict("v2 path", retired=True):\n        pass\n')
        self.assertEqual(v1_instrument_uses(planted), [(3, 'test_a_new_v2_check')])

    def test_the_seam_reader_finds_every_planted_form_and_nothing_else(self):
        planted = {
            'from studio.interpretation import sentinel\nwith sentinel.strict("x"):\n    pass\n': 1,
            'from studio.interpretation.sentinel import strict\n': 1,
            'from studio.interpretation.sentinel import *\n': 1,
            'from studio.interpretation import sentinel as guard\nguard.retired_unarmed()\n': 1,
            'import studio.interpretation.sentinel as guard\nwith guard.strict("x", retired=True):\n    pass\n': 1,
            'from studio import jobs\njobs.sentinel.strict("x")\n': 1,
            'getattr(sentinel, "retired_unarmed")()\n': 1,
        }
        for source, expected in planted.items():
            with self.subTest(source=source):
                self.assertEqual(len(seam_uses(source)), expected, seam_uses(source))
        for source in ('list(zip(a, b, strict=True))\n', 'state = inflate_strict(data)\n', 'json.loads(s, strict=False)\n',
                       'from studio.interpretation import sentinel\nsentinel.scope("new_path", entry="x")\n',
                       'parser.strict = True\n'):
            with self.subTest(source=source):
                self.assertEqual(seam_uses(source), [])
