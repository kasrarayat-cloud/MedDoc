"""GI round 4, package PE: one killing mutant per guard PE adds, and the release itself (H6).

Each mutant names its guard, one exact anchor in studio/gi/detect.py and its replacement; its detector is
tests.test_gi4_pe, which holds the behaviour the guard keeps and no registry check (a mutant removes its own anchor, so a
registry check in the detector module would kill every mutant whatever the behaviour tests saw). The registry check is
here: every anchor occurs exactly once in this tree. The mutants are run on COPIES of a sealed export with
ops.gi4.mutants.applied (sha256 printed after the mutation and after the restore) and ops.gi4.mutants.detect, after the
detector passes on the unmutated export. The Wave 1 integration moved the records, unchanged, into ops/gi4/mutants.py
(PE_MUTANTS), so python -m ops.gi4.mutants runs them; this module checks that slice.
"""
from django.test import SimpleTestCase

from ops.gi4 import boot, mutants

PE_MUTANTS = mutants.PE_MUTANTS


class MutantRegistryTests(SimpleTestCase):
    def test_every_anchor_occurs_exactly_once_in_this_tree(self):
        for m in PE_MUTANTS:
            text = (boot.HARNESS_TREE / m.path).read_text(encoding='utf-8')
            self.assertEqual(text.count(m.old), 1, m.name)
            self.assertNotEqual(m.old, m.new, m.name)
        self.assertEqual(len({m.name for m in PE_MUTANTS}), len(PE_MUTANTS))

    def test_each_is_registered_once_in_the_merged_registry(self):
        names = [m.name for m in mutants.MUTANTS]
        self.assertEqual(len(PE_MUTANTS), 32)  # 10, the Wave 1 repair's 19 (pe.json, amendment_20261101_cycle1), 2
        # (amendment_20261101_cycle1_b: pe-head-family, pe-head-span-body) and 1 (amendment_20261101_cycle1_d)
        for m in PE_MUTANTS:
            self.assertEqual(names.count(m.name), 1, m.name)
            self.assertIs(mutants.BY_NAME[m.name], m)
            self.assertTrue(m.name.startswith('pe-') and m.guard and m.detector == 'unit:tests.test_gi4_pe', m.name)
