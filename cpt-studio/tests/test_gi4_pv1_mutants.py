"""GI round 4, package PV1, H6: one killing mutant per guard PV1 adds, each detected by tests/test_gi4_pv1.py (a unit
test, no database). PV1 registered them here rather than in ops/gi4/mutants.py, stage A's registry, which no package of
the round edits; the Wave 1 integration merged them into it, unchanged (PV1_MUTANTS). ops.gi4.mutants.applied runs them:
a sealed copy is mutated, the sha256 is printed after the mutation is applied and again after it is restored, and an
anchor that does not occur exactly once is NOT RUN, never killed. Each anchor is checked against this tree below, so the
registry cannot rot silently.
"""
from django.test import SimpleTestCase

from ops.gi4 import boot, mutants

UNITS = ('unit:tests.test_gi4_pv1', 'unit:tests.test_gi4_pv1_cycle1',  # Wave 1's guards; repair cycle 1's
         'unit:tests.test_gi4_pv1_cycle2')  # repair cycle 2's (pv1-line-quote-sentence)
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
        # Wave 1's 17, less the 2 repair cycle 1 removed, plus its 39 (54); repair cycle 2 (pv1.json
        # amendment_20261101_cycle2) retires the 23 that guarded C1, C2 and the visit evidence, with their code, and adds
        # pv1-line-quote-sentence (32)
        self.assertEqual(len(names), 32)
        for retired in ('pv1-c1-after-only', 'pv1-c1-plan-work', 'pv1-c1-planned-time', 'pv1-c1-dates-count',
                        'pv1-c1-time-only', 'pv1-c2-shared', 'pv1-c2-drop', 'pv1-c2-office-visit', 'pv1-c2-kept-c4',
                        'pv1-c2-kept-own', 'pv1-c2-opens-line', 'pv1-c2-history-section', 'pv1-c2-governing',
                        'pv1-c2-section-heading', 'pv1-c2-line-rest', 'pv1-visit-exam', 'pv1-visit-setting',
                        'pv1-visit-not-a-visit', 'pv1-visit-procedure-day', 'pv1-visit-around-title',
                        'pv1-visit-reported', 'pv1-c1-office-visit', 'pv1-c1-nouns'):
            self.assertNotIn(retired, names)
        self.assertTrue(all(n.startswith('pv1-') for n in names))  # never a stage A name
        registered = [m.name for m in mutants.MUTANTS]
        for m in MUTANTS:
            self.assertEqual(registered.count(m.name), 1, m.name)  # once in the merged registry
            self.assertIs(mutants.BY_NAME[m.name], m)
            self.assertIn(m.detector, UNITS, m.name)
            self.assertTrue(m.guard, m.name)
