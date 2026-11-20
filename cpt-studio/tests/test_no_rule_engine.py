"""No code-family rule set (FIX-SPEC-2 section 8; the owner's condition: the earlier engine is not built again). The
dormant endoscopy rule set of studio/reference/passages.py - its retrieval, the rules that grouped codes into endoscopic
families and picked NCCI rules by code ranges and code lists, and the constants only they used - is gone; the passage
data files and their import stay. No product module carries a CPT code range or a per-code rule table. Read-only:
nothing is imported but the passages module."""
import ast
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from studio.reference import passages

STUDIO = Path(settings.BASE_DIR) / 'studio'
REMOVED = ('retrieve', '_endoscopy_rules', '_pfs_queries', '_facts', '_index', '_unapplied',
           'ENDOSCOPY', 'MULTIPLE_SURGERY', 'RULE_4_RANGES', 'RULE_7_CODES', 'RULE_16_CODES', 'NO_DATE_NOTE',
           'NOT_CONNECTED', 'FACT_LABELS', 'TOPIC_ORDER')


def code_number(node) -> bool:
    """A literal that reads as a CPT code: a five-digit string, or a five-digit integer from 10000 to 99999."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return len(node.value) == 5 and node.value.isascii() and node.value.isdigit()
    return isinstance(node, ast.Constant) and type(node.value) is int and 10000 <= node.value <= 99999


class NoRuleSetTests(SimpleTestCase):
    def test_the_dormant_endoscopy_rule_set_is_gone_and_the_import_stays(self):
        for name in REMOVED:
            with self.subTest(name=name):
                self.assertFalse(hasattr(passages, name), name)
        for name in ('import_data_file', 'read_data_file', 'parse_data', 'load_passages', 'bundled_files', 'TOPICS'):
            with self.subTest(kept=name):
                self.assertTrue(hasattr(passages, name), name)
        self.assertTrue((STUDIO / 'reference' / 'data').is_dir())
        self.assertTrue((STUDIO / 'management' / 'commands' / 'import_passages.py').is_file())

    def test_no_product_module_holds_a_table_or_range_of_cpt_codes(self):
        found = []
        for path in sorted(STUDIO.rglob('*.py')):
            if 'migrations' in path.parts:
                continue
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, (ast.Tuple, ast.List, ast.Set)) and any(code_number(item) for item in node.elts):
                    found.append(f'{path.relative_to(STUDIO)}:{node.lineno}')
        self.assertEqual(found, [])
