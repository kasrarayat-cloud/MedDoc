"""The differential round over refutation cycle 4's repair (2026-11-07; HARNESS.md "The differential round over cycle 4's
repair"). Three lenses asked only whether the cycle-4 head was worse than the installed base or the previous head in a
must-fix class. Their engine-level inputs (tests/fixtures/gi4/refutation/completion-c5-cases.json: the structure lens's
inputs and heading twins, the routing lens's line-break, semicolon, reason, ellipsis and status-line inputs) were read on
the installed base (b452c6c4), the cycle-3 head (52a5f774) and the cycle-4 head (e273dc5a) before anything changed; the
repair reads each as pinned, and never READY where the installed base holds the input and its twin. The final scan added
the routing lens's U3 group (twin: the named variant) and its cancellation group (the closed form beside a cancelled,
declined, pending or hedged examination in an unnamed section; twin: the same text under "Procedure: Colonoscopy",
measured on the three trees), which pin the consumed failure's I8 gate. Synthetic documents only; nothing is sent."""
from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase

from tests.test_harness_engine import code, corti, read, run, span

FIXTURE = Path(__file__).parent / 'fixtures' / 'gi4' / 'refutation' / 'completion-c5-cases.json'
CASES = json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']
BY_LABEL = {case['label']: case for case in CASES}
QUIET = ('pass', 'not_applicable', 'not_verified', 'info')
# READY where the installed base holds the twin, recorded: the H2 (39f0ac49) shape's bolus removal, which the heading
# twin holds by its own false hold (corpus 137, the parity test's recorded exception since cycle 2)
PARITY_EXCEPTIONS = {('c5s|F4 H2 as is', '43247'), ('c5s|F4 H2 colonoscope withdrawn slowly', '43247')}


def label(p) -> str:
    if p.bucket == 'excluded':
        return 'EXCL'
    return 'READY' if p.status == 'ready' else 'HELD'


def reading(case) -> dict:
    text = case['text']
    parts = [read('astra', [code(text, c, q) for c, q in case['astra']])] if case['astra'] else []
    result = run(text, corti(*[(c, span(text, q)) for c, q in case['picks']]), parts)
    return {p.code: [label(p), sorted({c.id for c in p.checks if c.status not in QUIET}
                                      & {'service.incomplete', 'routing.family'})]
            for p in result.proposals if p.bucket != 'alternative'}


class DifferentialRoundTests(SimpleTestCase):

    def test_every_input_reads_as_pinned(self):
        for case in CASES:
            if case['day']:
                continue  # the same input on the jobs path, measured there in the session
            with self.subTest(case['label']):
                self.assertEqual(reading(case), case['head'])

    def test_no_ready_the_installed_base_holds_on_the_input_and_its_twin(self):
        for case in CASES:
            twin = BY_LABEL.get(case['twin']) if case.get('twin') else None
            with self.subTest(case['label']):
                for c, (lab, _flags) in case['head'].items():
                    if lab != 'READY' or case['base'].get(c, ['-'])[0] == 'READY' \
                            or (case['label'], c) in PARITY_EXCEPTIONS:
                        continue
                    self.assertIsNotNone(twin, 'a READY the base does not read, with no twin to bound it')
                    self.assertEqual(twin['base'][c][0], 'READY')

    def test_each_finding_was_real_on_the_cycle_4_head(self):
        for name in BY_LABEL:
            case = BY_LABEL[name]
            if not case.get('finding'):
                continue
            with self.subTest(name):
                self.assertNotEqual(case['cycle4'], case['head'])
