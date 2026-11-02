"""GI round 4, package PI: H6's mutant registry - one killing mutant per guard the package adds
(tests/test_gi4_pi.py pins each guard). The H6 battery applies each to a copy of a sealed export with ops.gi4.mutants
and runs the detector, tests.test_gi4_pi, which must fail on the mutant and pass without it. This module is kept apart
from that detector: its anchor check below fails on every mutated copy by construction, and would otherwise kill every
mutant whatever the behaviour. Each anchor must occur exactly once in this tree, so the registry cannot rot silently.
The Wave 1 integration moved the entries into ops/gi4/mutants.py (PI_MUTANTS: the package's (name, guard, path, old,
new, detector) tuples as Mutant records, every field unchanged), so python -m ops.gi4.mutants runs them; this module
checks that slice.
"""
from django.test import SimpleTestCase

from ops.gi4 import boot, mutants

_T = 'unit:tests.test_gi4_pi'
PI_MUTANTS = mutants.PI_MUTANTS


class MutantRegistryTests(SimpleTestCase):
    def test_every_anchor_occurs_exactly_once_in_this_tree(self):
        for m in PI_MUTANTS:
            text = (boot.HARNESS_TREE / m.path).read_text(encoding='utf-8')
            self.assertEqual(text.count(m.old), 1, m.name)
            self.assertNotEqual(m.old, m.new, m.name)
            self.assertTrue(m.guard and m.detector == _T, m.name)
        self.assertEqual(len({m.name for m in PI_MUTANTS}), len(PI_MUTANTS))

    def test_each_is_registered_once_in_the_merged_registry(self):
        names = [m.name for m in mutants.MUTANTS]
        self.assertEqual(len(PI_MUTANTS), 11)  # 18 declared, pi-office-visit, the Wave 1 repair's 4
        # (amendment_20261101_cycle1), less pi-carry-lesion-start (withdrawn with its code: amendment_20261101_cycle1_b),
        # plus pi-carry-lesion-heading (amendment_20261101_cycle1_c) and pi-head-not-today (amendment_20261101_cycle1_d):
        # 24; then cycle 2 (amendment_20261101_cycle2) retired E1's and A1's 16 with their code and added the 3
        # pi-reach-binding* mutants of S1's binding rule: 11
        retired = {'pi-e1-section', 'pi-e1-occurrence', 'pi-e1-extent-word', 'pi-e1-occurrence-word',
                   'pi-e1-routing-positive', 'pi-carry-part', 'pi-carry-part-kind', 'pi-carry-performed',
                   'pi-carry-region', 'pi-carry-reach', 'pi-carry-paragraph', 'pi-carry-field', 'pi-carry-two-named',
                   'pi-carry-lesion', 'pi-carry-lesion-paragraph', 'pi-carry-lesion-heading'}
        self.assertEqual(retired & set(names), set())
        for m in PI_MUTANTS:
            self.assertEqual(names.count(m.name), 1, m.name)
            self.assertIs(mutants.BY_NAME[m.name], m)
            self.assertTrue(m.name.startswith('pi-'), m.name)
