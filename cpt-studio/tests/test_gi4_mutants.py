"""GI round 4 harness, H6: the mutant battery's infrastructure (ops/gi4/mutants.py). A mutant is applied to a COPY of a
sealed tree, never to a working tree; its anchor must occur exactly once (else nothing is applied and it is NOT RUN, never
killed); the sha256 is printed after it is applied and again after it is restored, and the restore is compared with the
original bytes. Every registered mutant's anchor is checked against this tree, so the registry cannot rot silently.
"""
import contextlib
import io
import shutil
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import boot, mutants


class MutantRegistryTests(SimpleTestCase):
    def test_every_anchor_occurs_exactly_once_in_this_tree(self):
        for m in mutants.MUTANTS:
            text = (boot.HARNESS_TREE / m.path).read_text(encoding='utf-8')
            self.assertEqual(text.count(m.old), 1, m.name)
            self.assertNotEqual(m.old, m.new, m.name)

    def test_every_mutant_names_a_guard_and_a_detector(self):
        kinds = {'unit', 'state', 'replay', 'freeze', 'battery'}
        for m in mutants.MUTANTS:
            self.assertTrue(m.guard, m.name)
            self.assertIn(m.detector.partition(':')[0], kinds, m.name)
        self.assertEqual(len({m.name for m in mutants.MUTANTS}), len(mutants.MUTANTS))
        self.assertTrue(set(mutants.REPLAY_CONTROLS) <= set(mutants.BY_NAME))
        self.assertEqual(len(mutants.REPLAY_CONTROLS), 3)

    def test_the_census_every_package_once(self):
        # The merged registry (the Wave 1 integration): every round-4 package's mutants, each exactly once, as the
        # packages counted them (PS and PA here since stage A and PA; PD from its scratch driver; PV1, PE, PI and PO from
        # their tests/test_gi4_<package>_mutants.py), and stage A's own controls and gates. Wave 1 repair cycle 1
        # (PA+PO, amendments amendment_20261101_r2) adds PA's 20 and PO's 7 (P1).
        names = [m.name for m in mutants.MUTANTS]
        census = {p: [n for n in names if n.startswith(prefixes)] for p, prefixes in mutants.PACKAGE_PREFIXES.items()}
        self.assertEqual({p: len(v) for p, v in census.items()},
                         {'PS': 7, 'PA': 33, 'PD': 39, 'PV1': 54, 'PE': 32, 'PI': 24, 'PO': 30})  # Wave 1 repair cycle 1 (PA, PO, PV1, PE, PI, PD)
        # and its integration: PD +7, one killing mutant per guard of the STRONG-HEAD HOLD (pd.json
        # amendment_20261101_integration: pd-head-hold, -strong, -one-date, -around, -call, -note, -charge-note);
        # then Wave 1 repair cycle 2 (group PD+PO+PA): PD -7 +2, the hold DROPPED and its seven mutants retired with
        # its code, and one killing mutant per guard of rule (c)'s DT-5 fix (pd.json amendment_20261101_cycle2:
        # pd-announced-copy, pd-dated-after-signoff); PO +2, one per new hold (po.json amendment_20261101_cycle2:
        # po1-called-off, po1-act-record-heading)
        # PE +19, PI +4: the Wave 1 repair, cycle 1 (pe.json and pi.json, amendment_20261101_cycle1); then PE +2 and PI -1
        # (amendment_20261101_cycle1_b: the head must name the family; pi-carry-lesion-start withdrawn with its code) and
        # PI +1 (amendment_20261101_cycle1_c: pi-carry-lesion-heading) and PE +1, PI +1 (amendment_20261101_cycle1_d:
        # pe-head-not-today, pi-head-not-today)
        stage_a = [n for n in names if n.startswith(mutants.STAGE_A_PREFIXES)]
        self.assertEqual(len(stage_a), 11)
        self.assertEqual(sorted(sum(census.values(), []) + stage_a), sorted(names))  # every name in one place only
        # the Wave 1 repair (PD, cycle 1): PD's 11 became 37 - six kept, three re-anchored on the repaired code
        # (pd-closing-last-lines, pd-not-closing-words, pd-wide-never-own), two retired with the code they guarded
        # (pd-around-title, pd-corroboration), and 28 new: one killing mutant per new guard (pd.json
        # amendment_20261101 and its second to fifth entries)
        self.assertEqual(len(names), 230)  # 233 - 7 + 2 + 2 (Wave 1 repair cycle 2, group PD+PO+PA)
        for package, slice_ in (('PD', mutants.PD_MUTANTS), ('PV1', mutants.PV1_MUTANTS), ('PE', mutants.PE_MUTANTS),
                                ('PI', mutants.PI_MUTANTS), ('PO', mutants.PO_MUTANTS)):
            self.assertEqual([m.name for m in slice_], census[package], package)
            detectors = {f'unit:tests.test_gi4_{package.lower()}'}
            if package == 'PV1':  # repair cycle 1's guards are killed by its own test module
                detectors.add('unit:tests.test_gi4_pv1_cycle1')
            self.assertEqual({m.detector for m in slice_}, detectors, package)


class AppliedTests(SimpleTestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='gi4-mutant-test-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.tree = self.tmp / 'sealed' / 'cpt-studio'
        (self.tree / 'studio' / 'gi').mkdir(parents=True)
        source = boot.HARNESS_TREE / 'studio' / 'gi' / 'detect.py'
        (self.tree / 'studio' / 'gi' / 'detect.py').write_bytes(source.read_bytes())
        boot.seal(self.tmp / 'sealed')
        self.addCleanup(boot.unseal, self.tmp / 'sealed')
        self.scratch = self.tmp / 'scratch'
        self.scratch.mkdir()

    def test_a_copy_is_mutated_and_restored_with_both_sha256s_printed(self):
        mutant = mutants.BY_NAME['ctl-routing-elsewhere-order']
        original = (self.tree / mutant.path).read_bytes()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with mutants.applied(self.tree, mutant.name, self.scratch) as copy:
                self.assertNotEqual(copy.resolve(), self.tree.resolve())
                self.assertIn(mutant.new, (copy / mutant.path).read_text(encoding='utf-8'))
                self.assertEqual((self.tree / mutant.path).read_bytes(), original)  # the sealed tree is untouched
        printed = out.getvalue()
        self.assertIn('mutation applied: True', printed)
        self.assertIn('restored: True', printed)
        self.assertEqual(printed.count('sha256'), 2)
        self.assertFalse(copy.exists())  # the copy is removed
        self.assertEqual((self.tree / mutant.path).read_bytes(), original)

    def test_a_missing_anchor_is_not_run(self):
        (self.tmp / 'sealed').chmod(0o700)
        boot.unseal(self.tmp / 'sealed')
        path = self.tree / 'studio' / 'gi' / 'detect.py'
        path.write_text(path.read_text(encoding='utf-8').replace("ELSEWHERE_ORDER = ('negated',", "ELSEWHERE_ORDER = ('x',"),
                        encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'NOT RUN'), contextlib.redirect_stdout(io.StringIO()):
            with mutants.applied(self.tree, 'ctl-routing-elsewhere-order', self.scratch):
                pass
