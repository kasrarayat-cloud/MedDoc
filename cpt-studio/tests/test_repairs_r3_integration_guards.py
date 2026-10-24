"""Guards for the class of defect parallel repairs produce: two engineers defining the same top-level name in one module.

Round 3b integration found two. pdfannots.MARKS: FONTS' strike-out subtypes, replaced by FORMS' box-mark words, so
StrikeOut and Redact marks were never named. detect._WORD: the orchestrator's pre-trigger token pattern, replaced by
the gi.other code's whole-word pattern. Both merged with no textual conflict; the later definition silently served
both users.
"""
import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

STUDIO = Path(settings.BASE_DIR) / 'studio'


def top_level_assignments(tree):
    """(name, node) for every top-level assignment, function and class, in order."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield node.name, node
        targets = node.targets if isinstance(node, ast.Assign) else (
            [node.target] if isinstance(node, ast.AnnAssign) and node.value is not None else [])
        for target in targets:
            for name in ast.walk(target):
                if isinstance(name, ast.Name):
                    yield name.id, node


class TopLevelNamesAreAssignedOnceTests(SimpleTestCase):
    def test_no_module_assigns_a_top_level_name_twice(self):
        duplicates = []
        for path in sorted(STUDIO.rglob('*.py')):
            if 'migrations' in path.parts:
                continue
            seen = set()
            for name, node in top_level_assignments(ast.parse(path.read_text(encoding='utf-8'))):
                # a deliberate extension reads the name it rebinds: X = X + (...)
                extends = isinstance(node, ast.Assign) and any(
                    isinstance(n, ast.Name) and n.id == name for n in ast.walk(node.value))
                if name in seen and not extends:
                    duplicates.append(f'{path.relative_to(STUDIO.parent)}: {name}')
                seen.add(name)
        self.assertEqual(duplicates, [])
