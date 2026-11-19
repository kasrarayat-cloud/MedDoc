"""No legacy reader in the interpretation contract (Gemini migration slice S07; design/FINAL.md 3.1, 10.1 and 10.4(5);
DECISIONS D17; design/ADJUDICATION.md R-5): over the modules of slices S01-S03 that exist, an AST scan of every import
form and a fresh interpreter that imports them, both judged by the sentinel's own pinned lists.

The rule, per FINAL 3.1's module plan:
- S01 (labels, prompt, schema, read, store) and S02 (literals, lexicon, normalize, verify) import nothing of studio.gi;
- S03 (identity, relations, mapping, dates) imports only the reference tables gi.profiles and gi.catalogue;
- none of them imports a denied validation module or studio.candidates (sentinel.DENY_MODULES), and studio.validation.
  checks only by a FINAL 7.1 name (sentinel.CHECKS_ALLOWLIST; R-5).
A module of S03 that does not exist yet is skipped by name, never silently: S01's and S02's must exist.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from studio.interpretation import normalize, sentinel

APP = Path(__file__).resolve().parents[1]
PACKAGE = APP / 'studio' / 'interpretation'
SLICES = {'S01': ('__init__', 'prompt', 'schema', 'read', 'store'),
          'S02': ('literals', 'lexicon', 'normalize', 'verify'),
          'S03': ('identity', 'relations', 'mapping', 'dates')}
REQUIRED = SLICES['S01'] + SLICES['S02']  # committed slices: their modules must be here
REFERENCE_TABLES = ('studio.gi.profiles', 'studio.gi.catalogue')
IMPORTERS = ('importlib.import_module', 'import_module', '__import__')


def present() -> dict:
    """{module: slice} of the S01-S03 modules that exist."""
    return {name: slice_ for slice_, names in SLICES.items() for name in names if (PACKAGE / f'{name}.py').is_file()}


def dotted(node) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return '.'.join(reversed(parts))
    return ''


def scan(source: str, package: str = 'studio.interpretation') -> dict:
    """Every import a module's source makes: {'modules': [(module, name or '')], 'dynamic': [source of a non-constant
    importer argument], 'attributes': [the longest dotted names that reach a studio module, through an import alias
    too]}. Relative imports are resolved against ``package`` (a module of studio/interpretation and the package's
    __init__ resolve alike)."""
    found = {'modules': [], 'dynamic': [], 'attributes': []}
    tree = ast.parse(source)
    aliases = {}  # a local name -> the studio module or attribute it is bound to
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found['modules'].append((alias.name, ''))
                if alias.asname:
                    aliases[alias.asname] = alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                parts = package.split('.')
                base = '.'.join(parts[:len(parts) - node.level + 1] + ([node.module] if node.module else []))
            for alias in node.names:
                found['modules'].append((base, alias.name))
                aliases[alias.asname or alias.name] = f'{base}.{alias.name}'
    inner = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and dotted(node.func) in IMPORTERS and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                found['modules'].append((argument.value, ''))
            else:
                found['dynamic'].append(ast.unparse(argument))
        elif isinstance(node, ast.Attribute) and id(node) not in inner:
            value = node.value
            while isinstance(value, ast.Attribute):  # only the longest chain is read, once
                inner.add(id(value))
                value = value.value
            name = dotted(node)
            head, _, rest = name.partition('.')
            if head in aliases and aliases[head].startswith('studio.'):
                name = f'{aliases[head]}.{rest}'
            if name.startswith('studio.'):
                found['attributes'].append(name)
    return found


def violations(found: dict, slice_: str) -> list:
    """What breaks the rule in one module's imports (``found``, from scan), as readable lines."""
    gi_allowed = REFERENCE_TABLES if slice_ == 'S03' else ()
    out = []
    names = [(module, name) for module, name in found['modules']]
    names += [(attribute, '') for attribute in found['attributes']]
    for module, name in names:
        full = f'{module}.{name}' if name else module
        if full == 'studio.gi' or full.startswith('studio.gi.'):
            if not any(full == table or full.startswith(table + '.') for table in gi_allowed):
                out.append(f'imports {full}')
            continue
        if any(full == denied or full.startswith(denied + '.') or module == denied
               for denied in sentinel.DENY_MODULES if not denied.startswith('studio.gi')):
            out.append(f'imports {full}')
        elif full == sentinel.CHECKS_MODULE:
            continue  # the module itself: each name read through it is judged as an attribute
        elif module == sentinel.CHECKS_MODULE or full.startswith(sentinel.CHECKS_MODULE + '.'):
            used = name or full[len(sentinel.CHECKS_MODULE) + 1:].split('.')[0]
            if used not in sentinel.CHECKS_ALLOWLIST + sentinel.CHECKS_ALLOWLIST_CONSTANTS:
                out.append(f'imports {full}, which is not a FINAL 7.1 check')
        elif module == 'studio.validation' and name and name not in ('questions', 'checks'):
            out.append(f'imports {full}')
    return out


class ImportScanTests(SimpleTestCase):
    def test_the_committed_slices_modules_are_all_here(self):
        found = present()
        self.assertEqual([name for name in REQUIRED if name not in found], [])
        self.assertEqual(set(found) - set(REQUIRED), {name for name in SLICES['S03'] if name in found})

    def test_no_module_of_s01_to_s03_imports_the_legacy_reader(self):
        for name, slice_ in present().items():
            with self.subTest(module=name, slice=slice_):
                found = scan((PACKAGE / f'{name}.py').read_text(encoding='utf-8'))
                if name != '__init__':
                    self.assertTrue(found['modules'], 'the scan saw no import at all')  # it reads this module
                self.assertEqual(violations(found, slice_), [])
                # the one dynamic import: normalize's linked steps, whose modules are S03's own (checked below)
                self.assertEqual(found['dynamic'], ['module'] if name == 'normalize' else [])

    def test_normalizes_linked_steps_are_s03_modules(self):
        modules = {module for module, _ in normalize.LINKED_STEPS}
        self.assertEqual(modules, {f'studio.interpretation.{name}' for name in ('identity', 'relations', 'mapping')})
        self.assertLessEqual({module.rpartition('.')[2] for module in modules}, set(SLICES['S03']))

    def test_the_scan_sees_each_form_and_the_rule_refuses_each(self):
        planted = ('import studio.gi.services\n'
                   'from studio.gi import context\n'
                   'from studio import gi\n'
                   'from ..gi import detect\n'
                   'from ..validation import reconcile\n'
                   'from studio.validation.checks import evidence_readings\n'
                   'from studio import candidates\n'
                   'import studio.validation.engine as engine\n'
                   'importlib.import_module("studio.gi.cues")\n'
                   '__import__("studio.validation.review_view")\n'
                   'value = studio.gi.structure.clinical_layout\n')
        found = scan(planted)
        expected = ['imports studio.gi.services', 'imports studio.gi.context', 'imports studio.gi',
                    'imports studio.gi.detect', 'imports studio.validation.reconcile',
                    'imports studio.validation.checks.evidence_readings, which is not a FINAL 7.1 check',
                    'imports studio.candidates', 'imports studio.validation.engine', 'imports studio.gi.cues',
                    'imports studio.validation.review_view', 'imports studio.gi.structure.clinical_layout']
        self.assertEqual(violations(found, 'S01'), expected)
        # S03 may read the reference tables; the S01 and S02 modules may not
        tables = scan('from studio.gi import profiles, catalogue\nimport studio.gi.catalogue\n'
                      'from studio.gi.profiles import family_for_code\n')
        self.assertEqual(violations(tables, 'S03'), [])
        self.assertEqual(len(violations(tables, 'S02')), 4)
        allowed = scan('from studio.validation.checks import exact_evidence, NOT_CONNECTED_CHECKS\n'
                       'from studio.validation import questions\n'
                       'from studio.validation import checks as c\nc.code_scope\n')
        self.assertEqual(violations(allowed, 'S01'), [])
        aliased = scan('from studio.validation import checks as c\nc.status_check\nimport studio.gi.cues as k\n'
                       'k.PAGE_NUMBER_LINE.search\n')  # a reader reached through an alias is the reader
        self.assertEqual(violations(aliased, 'S03'), [
            'imports studio.gi.cues', 'imports studio.validation.checks.status_check, which is not a FINAL 7.1 check',
            'imports studio.gi.cues.PAGE_NUMBER_LINE.search'])
        self.assertEqual(scan('importlib.import_module(name)\n')['dynamic'], ['name'])


class FreshInterpreterTests(SimpleTestCase):
    def loaded(self, imports: list, extra_path: str = '') -> list:
        code = (f'import sys\nsys.path[:0] = {[str(APP)] + ([extra_path] if extra_path else [])!r}\n'
                + ''.join(f'import {module}\n' for module in imports)
                + 'import json\nprint(json.dumps(sorted(name for name in sys.modules if name.startswith("studio"))))\n')
        completed = subprocess.run([sys.executable, '-I', '-B', '-c', code], capture_output=True, text=True,
                                   timeout=120, cwd=APP)
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        return json.loads(completed.stdout.strip().splitlines()[-1])

    @staticmethod
    def legacy(loaded: list, slices) -> list:
        tables = ('studio.gi',) + REFERENCE_TABLES if 'S03' in slices else ()
        return [name for name in loaded
                if (name == 'studio.gi' or name.startswith(('studio.gi.', 'studio.validation', 'studio.candidates')))
                and name not in tables]

    def test_importing_them_loads_no_legacy_module(self):
        found = present()
        modules = ['studio.interpretation' if name == '__init__' else f'studio.interpretation.{name}' for name in found]
        loaded = self.loaded(modules)
        self.assertLessEqual(set(modules), set(loaded))
        self.assertEqual(self.legacy(loaded, set(found.values())), [])
        if not any(slice_ == 'S03' for slice_ in found.values()):  # with S03 absent nothing of studio.gi loads at all
            self.assertEqual([name for name in loaded if name.startswith('studio.gi')], [])

    def test_the_control_a_planted_import_is_seen(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'planted_reader.py').write_text('import studio.gi.cues\n', encoding='utf-8')
            loaded = self.loaded(['studio.interpretation.read', 'planted_reader'], extra_path=directory)
        self.assertEqual(self.legacy(loaded, {'S01'}), ['studio.gi', 'studio.gi.cues'])
