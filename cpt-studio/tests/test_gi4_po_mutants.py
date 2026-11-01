"""GI round 4, package PO, H6: the registry of PO's mutants - at least one per guard in validation/engine.py's _po_
helpers, the amendment's holds (A1-A5, declaration amendment_20261101) included - each killed by tests/test_gi4_po.py
(the detector, which holds no check of this registry: an anchor check fails on every mutated copy and would kill every
mutant by construction). Here every anchor is checked against this tree, so the
registry cannot rot silently. The harness applies a mutant to a COPY of a sealed export and prints the sha256 after it
is applied and again after it is restored (ops.gi4.mutants.applied). The Wave 1 integration moved these records,
unchanged, into ops/gi4/mutants.py (PO_MUTANTS), so python -m ops.gi4.mutants runs them; this module checks that slice.
"""
from django.test import SimpleTestCase

from ops.gi4 import boot, mutants

ENGINE = 'studio/validation/engine.py'
UNIT = 'unit:tests.test_gi4_po'
PO_MUTANTS = mutants.PO_MUTANTS


class MutantRegistryTests(SimpleTestCase):
    def test_every_po_mutant_applies_exactly_once_and_names_its_guard(self):
        source = (boot.HARNESS_TREE / ENGINE).read_text(encoding='utf-8')
        for m in PO_MUTANTS:
            self.assertEqual(m.path, ENGINE, m.name)
            self.assertEqual(source.count(m.old), 1, m.name)
            self.assertNotEqual(m.old, m.new, m.name)
            self.assertTrue(m.guard and m.detector == UNIT, m.name)
        self.assertEqual(len({m.name for m in PO_MUTANTS}), len(PO_MUTANTS))

    def test_each_is_registered_once_in_the_merged_registry(self):
        names = [m.name for m in mutants.MUTANTS]
        self.assertEqual(len(PO_MUTANTS), 21)
        for m in PO_MUTANTS:
            self.assertEqual(names.count(m.name), 1, m.name)
            self.assertIs(mutants.BY_NAME[m.name], m)
            self.assertTrue(m.name.startswith(('po-', 'po1-', 'po2-')), m.name)
