"""GI round 4, package PV1, H6: one killing mutant per guard PV1 adds, each detected by tests/test_gi4_pv1.py (a unit
test, no database). PV1 registered them here rather than in ops/gi4/mutants.py, stage A's registry, which no package of
the round edits; the Wave 1 integration merged them into it, unchanged (PV1_MUTANTS). ops.gi4.mutants.applied runs them:
a sealed copy is mutated, the sha256 is printed after the mutation is applied and again after it is restored, and an
anchor that does not occur exactly once is NOT RUN, never killed. Each anchor is checked against this tree below, so the
registry cannot rot silently.
"""
from django.test import SimpleTestCase

from ops.gi4 import boot, mutants

UNIT = 'unit:tests.test_gi4_pv1'
MUTANTS = mutants.PV1_MUTANTS
BY_NAME = {m.name: m for m in MUTANTS}


class PV1MutantRegistryTests(SimpleTestCase):
    def test_every_anchor_occurs_exactly_once_in_this_tree(self):
        for m in MUTANTS:
            text = (boot.HARNESS_TREE / m.path).read_text(encoding='utf-8')
            self.assertEqual(text.count(m.old), 1, m.name)
            self.assertNotEqual(m.old, m.new, m.name)
            self.assertIn(m.new, text.replace(m.old, m.new, 1), m.name)

    def test_names_detectors_and_guards(self):
        names = [m.name for m in MUTANTS]
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(len(names), 17)
        self.assertTrue(all(n.startswith('pv1-') for n in names))  # never a stage A name
        registered = [m.name for m in mutants.MUTANTS]
        for m in MUTANTS:
            self.assertEqual(registered.count(m.name), 1, m.name)  # once in the merged registry
            self.assertIs(mutants.BY_NAME[m.name], m)
            self.assertEqual(m.detector, UNIT, m.name)
            self.assertTrue(m.guard, m.name)
