"""Every trigger count an operator text states is the release contract's count (blockers.txt item 4a), and the host-rebuild
procedure stops the old host's units before the new host's worker starts (item 4b).

The restore drill passes an operator-typed `--expected-triggers N` to production_restore_check.py, and integrity_contract
refuses any N but len(GUARDS) (`declaration_matches_release`). The three texts that tell the operator N said 63, 17 and 9
while the contract is 82: each fails closed, and each stops a restore drill. These tests read the numbers those texts state,
in the forms they state them, and require every one to equal len(GUARDS), so the next migration that adds a guard fails
here until the texts follow.

Limit: a count spelled out in words is not read. The cutover plan's "the installed legacy revision has nine" is about the
legacy installation, not this release, and stays.
"""
from pathlib import Path
import re
import unittest

try:
    from . import integrity_contract
except ImportError:
    import integrity_contract

REBUILD = Path(__file__).resolve().parents[1]
REPOSITORY = REBUILD.parent
TEXTS = {
    'production_restore_check.py': REBUILD / 'ops/production_restore_check.py',
    'cutover-plan.md': REPOSITORY / 'docs/rebuild/v1/cutover-plan.md',
    'production-hosting.md': REPOSITORY / 'docs/rebuild/v1/production-hosting.md',
}
#: The forms the texts state a count in: the drill's flag with a number, and the cutover plan's "(N in this candidate".
FORMS = (re.compile(r'--expected-triggers[ =](\d+)'), re.compile(r'\((\d+) in this candidate'))


def stated_counts(text):
    return [int(match) for form in FORMS for match in form.findall(text)]


class OperatorTriggerCounts(unittest.TestCase):
    def test_every_stated_trigger_count_is_the_release_contract(self):
        expected = len(integrity_contract.GUARDS)
        self.assertEqual(expected, 111)  # 107 through0034 + import manifest0035 + transcript custody0036/0037
        for name, path in TEXTS.items():
            with self.subTest(text=name):
                counts = stated_counts(path.read_text())
                # Positive control: each text states at least one count, so a reworded text cannot pass by saying none.
                self.assertTrue(counts, f'{name} states no trigger count in a recognised form')
                self.assertEqual(set(counts), {expected}, f'{name} states {counts}; the contract is {expected}')

    def test_the_reader_finds_a_wrong_count(self):
        """Negative control: the counts the texts used to state are read, and differ from the contract."""
        self.assertEqual(stated_counts('        --expected-triggers 63\n'), [63])
        self.assertEqual(stated_counts('definitions (17 in this candidate; the installed legacy revision has nine).'), [17])
        self.assertEqual(stated_counts('`ops/production_restore_check.py --expected-triggers 9` (the number'), [9])
        self.assertEqual(stated_counts('`production_restore_check.py --expected-triggers <recorded>` there'), [])

    def test_the_old_host_stops_before_the_new_host_starts_its_units(self):
        text = ' '.join(TEXTS['production-hosting.md'].read_text().split())
        start = text.index('**Rebuild, never repair in place.**')
        bullet = text[start:text.index('- **Rebuild drill**', start)]
        stop = bullet.index('stop every QuillMD unit on the old instance, worker first')
        self.assertLess(stop, bullet.index('start the units on the new host'))
        self.assertLess(bullet.index('start the units on the new host'), bullet.index('terminate the old instance'))
        self.assertNotIn('start the units, re-point the target group, then terminate the old instance', bullet)


if __name__ == '__main__':
    unittest.main()
