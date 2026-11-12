"""Harness repair 3 (owner directive 2026-11-05, second message): refutation cycle 4, the last, over cycle 3's changes,
pinned (HARNESS.md "Harness repair 3, refutation cycle 4").

Three lenses ran at 7e3924a3c: C4-1 F-ACTS' removal binding and the fronted frame, C4-2 competition and the narrowed
admission, C4-3 the seven holding rules cycle 3 narrowed. They reported 18 findings. Every engine-level input is in
tests/fixtures/gi4/refutation/h3-c4-cases.json, verbatim, with what the base 406843018, the stage commit 1974c8cb1, the
round-1 tree 8b186df05, the cycle-2 tree b32222c8f and the cycle-3 tree 7e3924a3c read, measured before anything was
decided. Under the release policy F-ACTS (refuted in cycles 3 and 4) is dropped, competition errs toward competing, and
every narrowing that opened a false READY returned to its cycle-2 form. Pinned here: no input is READY on either path
where the base is not, and no two codes for one documented act are both READY. Synthetic documents only."""
import json
from pathlib import Path

from django.test import SimpleTestCase

from studio.validation import engine
from tests.test_h3_refutation_c2 import SHORT, dated_both
from tests.test_harness_engine import code, corti, read, run, span

CASES = json.loads((Path(__file__).parent / 'fixtures' / 'gi4' / 'refutation' / 'h3-c4-cases.json')
                   .read_text(encoding='utf-8'))
# the C4-2 cases of one documented act (a restatement, a doubted second statement, an act stated twice); C4-2-2 is two
# dilations at two stated sites, both READY
ONE_ACT = ('C4-2:C4-2-1', 'C4-2:C4-2-3', 'C4-2:C4-2-4')


class CycleFourSingleTests(SimpleTestCase):
    """C4-1's and C4-3's inputs, one code on both paths through the pipeline's own date."""

    def test_every_input_reads_as_pinned(self):
        for case in CASES['single']:
            with self.subTest(case['id']):
                self.assertEqual(dated_both(case['text'], case['code'], case['quote'],
                                            tuple(map(tuple, case['primary']))),
                                 (case['corti'], case['participant'], case['day']), case['read'])

    def test_no_input_is_ready_where_the_base_is_not(self):
        # Completion repair (2026-11-06, U1; builder A): one judged release, the control the cycle-4 lens built from
        # cycle 3's judged meat-bolus release - "A large meat bolus was found at 34 cm. The bolus was removed with a Roth
        # net." is the corpus's required READY (group C), read now by the bolus's antecedent and its structural removal
        judged = {'C4-1:ctl-B6c'}
        for case in CASES['single']:
            base_corti, base_participant = case['read']['base'].split('/')
            with self.subTest(case['id']):
                if case['id'] in judged:
                    continue
                if 'READY' in case['corti']:
                    self.assertIn('READY', base_corti)
                if 'READY' in case['participant']:
                    self.assertIn('READY', base_participant)


class CycleFourCompetitionTests(SimpleTestCase):
    """C4-2's inputs: one documented act - under a Findings heading, restated, stated twice once without a site, or
    doubted beside two dilations - never has two READY codes; two dilations at two stated sites are two acts."""

    def outcome(self, case):
        by = {}
        for provider, value, *quotes in case['participants']:
            by.setdefault(provider, []).append(code(case['text'], value, *quotes))
        result = run(case['text'], corti(*[(c, span(case['text'], q)) for c, q in case['primary']]),
                     [read(p, cs) for p, cs in by.items()])
        return {value: [[SHORT.get((p.bucket, p.status), p.bucket), any(c.id == engine.COMPETING_CHECK for c in p.checks)]
                        for p in result.proposals if p.code == value] for value in case['outcome']}

    def test_every_input_reads_as_pinned(self):
        for case in CASES['multi']:
            with self.subTest(case['id']):
                self.assertEqual(self.outcome(case), case['outcome'], case['read'])

    def test_one_act_never_has_two_ready_codes(self):
        seen = 0
        for case in CASES['multi']:
            if not case['id'].startswith(ONE_ACT):
                continue
            seen += 1
            with self.subTest(case['id']):
                ready = [value for value, items in case['outcome'].items() if any(o[0] == 'READY' for o in items)]
                self.assertLessEqual(len(ready), 1, ready)
        self.assertGreaterEqual(seen, 10)
