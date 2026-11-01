"""GI round 4 harness, H4: the assess battery (ops/gi4/battery.py). Synthetic provider answers go through
jobs._assess_child in-process, offline, for the permanent rows: the minimal design's 28 cases, the judge's J1-J8,
K1-K3, E1-E4 and S1-S3, and the h4-05 counterfactual (43259 citing the narrative: EXCLUDED as installed).

Pinned against installed 80df1831d168 (tests/fixtures/gi4/pins/battery.json): every code's bucket and status, and every
property violation. A package that moves a row re-pins it beside its declaration ("battery": [[row, code, from, to]]),
and a NEW violation (READY where the truth says not done today, an exclusion where it says done) always fails. The truths
are PROVISIONAL; no qualified GI coder has reviewed them.
"""
import json
import re
from pathlib import Path

from django.test import SimpleTestCase

from ops.gi4 import battery, pins

PIN = json.loads((Path(__file__).resolve().parent / 'fixtures' / 'gi4' / 'pins' / 'battery.json').read_text())


class AssessBatteryTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.result = battery.run()

    def test_the_permanent_rows(self):
        self.assertEqual(len(battery.CASES), 47)
        names = list(battery.CASES)
        for label in ('J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8', 'K1', 'K2', 'K3', 'E1', 'E2', 'E3', 'E4', 'S1', 'S2',
                      'S3'):
            self.assertEqual(sum(n.startswith(label + ' ') for n in names), 1, label)
        self.assertEqual(sum(re.match(r'(?:[JKES][1-8]|S3h) ', n) is None for n in names), 28)  # the minimal design's
        self.assertEqual(sum(n.startswith('S3h ') for n in names), 1)  # the h4-05 counterfactual

    def test_every_code_is_assessed_with_its_truth(self):
        for name, row in self.result.items():
            self.assertEqual(sorted(row['proposals']), sorted(row['truth']), name)

    def test_outcomes_equal_installed(self):
        now = pins.compact_battery(self.result)
        moved = [[n, c, PIN['rows'][n][c][:2], now[n][c][:2]] for n in PIN['rows'] for c in PIN['rows'][n]
                 if now.get(n, {}).get(c, [None, None])[:2] != PIN['rows'][n][c][:2]]
        self.assertEqual(moved, [], 'battery rows moved against installed (re-pin only beside a declaration)')

    def test_no_new_violation(self):
        known = {(n, c) for n, codes in PIN['rows'].items() for c, (_, _, v) in codes.items() if v}
        now = {(n, c) for n, row in self.result.items() for c, p in row['proposals'].items() if p['violations']}
        self.assertEqual(sorted(now - known), [])
        # installed: two C4 E/M READYs, two S2/S3 exclusions of a done colonoscopy, the h4-05 counterfactual's exclusion
        self.assertEqual(len(known), 5)

    def test_the_properties(self):
        ready = {'bucket': 'selected', 'status': 'ready', 'modifiers': [], 'checks': []}
        held = {'bucket': 'selected', 'status': 'needs_clarification', 'modifiers': [], 'checks': ['facts.required']}
        excluded = {'bucket': 'excluded', 'status': 'excluded', 'modifiers': [], 'checks': ['service.status']}
        self.assertTrue(battery.violations('not_done', ready))
        self.assertFalse(battery.violations('not_done', excluded))
        self.assertTrue(battery.violations('done', excluded))
        self.assertFalse(battery.violations('done', ready))
        self.assertTrue(battery.violations('done_incomplete', ready))
        self.assertFalse(battery.violations('done_incomplete', dict(ready, modifiers=['53'])))
        self.assertTrue(battery.violations('unsupported', ready) and battery.violations('unsupported', excluded))
        self.assertFalse(battery.violations('unsupported', held))
        self.assertFalse(battery.violations('no_ready', excluded))
        self.assertFalse(battery.violations('not_done|MAY', ready))  # disputed by the second review: never judged

    def test_movements_are_classified(self):
        base = {'r': {'proposals': {'45378': {'bucket': 'excluded', 'status': 'excluded'}}}}
        head = {'r': {'proposals': {'45378': {'bucket': 'selected', 'status': 'needs_clarification'}}}}
        self.assertEqual(battery.movements(base, head), [['r', '45378', 'excluded/excluded',
                                                          'selected/needs_clarification']])
        self.assertEqual(battery.movements(base, base), [])
