"""Harness repair 3 (owner directive 2026-11-05, second message): refutation cycle 3 over cycle 2's rebuilt and repaired
rules, pinned (HARNESS.md "Harness repair 3, refutation cycle 3").

Four lenses ran at b32222c8f: C3-1 F-ACTS as rebuilt and the fronted frame, C3-2 the provider-neutral admission, C3-3
competition by act identity, C3-4 the holding rules as cycle 2 repaired them. They reported 25 findings. Every
engine-level input is in tests/fixtures/gi4/refutation/h3-c3-cases.json, verbatim, with what the base 406843018, the
stage commit 1974c8cb1, the round-1 tree 8b186df05 and the cycle-2 tree b32222c8f read, measured before anything was
decided. The release criteria pinned here:
- no input is READY on either path where the base is not, except the two releases judged correct below;
- no two codes for one documented act are both READY;
- a participant's code for an act read in doubt itself, or stated not done, is listed, and Corti's own proposals and the
  coding completeness read as with no participant.
Synthetic documents only; nothing is sent."""
import json
from pathlib import Path

from django.test import SimpleTestCase

from studio.validation import engine
from tests.test_h3_refutation_c2 import SHORT, dated_both
from tests.test_harness_engine import code, corti, read, run, span

CASES = json.loads((Path(__file__).parent / 'fixtures' / 'gi4' / 'refutation' / 'h3-c3-cases.json')
                   .read_text(encoding='utf-8'))
# READY where the base is not, each read against the document: F-ACTS' anaphor bound to the named meat bolus removed by
# net (the owner's 39f0ac49 shape), and biopsies taken "prior to dilation" - a point inside today's procedure (L3-9)
JUDGED_RELEASES = {'C3-1:c31-2:B6c': 'the meat bolus found at 34 cm and removed with a Roth net is done today',
                   'C3-1:c31-6:B6c': 'the same input in its second case file',
                   'C3-4-9:ctl': 'biopsies before the dilation of the same procedure are done today'}
# one documented act in each: a restatement or a doubted second statement of it
ONE_ACT = ('C3-3:f1_two_ready:', 'C3-3:f4_doubted_ready:')


def short(result, value):
    return [SHORT.get((p.bucket, p.status), f'{p.bucket}/{p.status}') for p in result.proposals if p.code == value]


class CycleThreeSingleTests(SimpleTestCase):
    """C3-1's and C3-4's inputs, one code on both paths through the pipeline's own date."""

    def test_every_input_reads_as_pinned(self):
        for case in CASES['single']:
            with self.subTest(case['id']):
                self.assertEqual(dated_both(case['text'], case['code'], case['quote'],
                                            tuple(map(tuple, case['primary']))),
                                 (case['corti'], case['participant'], case['day']), case['read'])

    def test_no_input_is_ready_where_the_base_is_not_but_the_judged_releases(self):
        released = set()
        for case in CASES['single']:
            base_corti, base_participant = case['read']['base'].split('/')
            if ('READY' in case['corti'] and 'READY' not in base_corti) or (
                    'READY' in case['participant'] and 'READY' not in base_participant):
                released.add(case['id'])
        self.assertEqual(released, set(JUDGED_RELEASES))


class CycleThreeCompetitionTests(SimpleTestCase):
    """C3-3's inputs: Corti's and the participants' codes together. A restatement (a procedure line's listing, a Diagnosis
    or findings line, an Impression) and a doubted second statement of one act compete with the act's code; two acts
    at two sites, or on two lesion records, never do."""

    def outcome(self, case):
        by = {}
        for provider, value, quote in case['participants']:
            by.setdefault(provider, []).append(code(case['text'], value, quote))
        result = run(case['text'], corti(*[(c, span(case['text'], q)) for c, q in case['primary']]),
                     [read(p, cs) for p, cs in by.items()])
        return {value: [[SHORT.get((p.bucket, p.status), p.bucket), any(c.id == engine.COMPETING_CHECK for c in p.checks)]
                        for p in result.proposals if p.code == value] for value in case['outcome']}

    def test_every_input_reads_as_pinned(self):
        for case in CASES['multi']:
            with self.subTest(case['id']):
                self.assertEqual(self.outcome(case), case['outcome'], case['read'])

    def test_one_act_never_has_two_ready_codes(self):
        for case in CASES['multi']:
            if not case['id'].startswith(ONE_ACT):
                continue
            with self.subTest(case['id']):
                ready = [value for value, items in case['outcome'].items() if any(o[0] == 'READY' for o in items)]
                self.assertLessEqual(len(ready), 1, ready)


class CycleThreeAdmissionTests(SimpleTestCase):
    """C3-2's inputs: a participant's code for an act read in doubt itself (a listed act withheld by its failure or plan,
    a consent's act, a question's act) is listed, and Corti's base code and the completeness read as with Corti alone -
    the admission adds a participant's code held only for an act stated done inside a service documented in doubt."""

    def test_every_row_reads_as_pinned_and_as_corti_alone(self):
        for case in CASES['admission']:
            text = case['text']
            sel = (case['base'], span(text, case['base_quote']))
            alone = run(text, corti(sel))
            self.assertEqual([short(alone, case['base']), alone.completeness.get('state')], case['alone'])
            for (who, quote, act_out, base_out, state), row in zip(
                    ((w, q, None, None, None) for w, q, *_ in case['rows']), case['rows']):
                with self.subTest(f"{case['id']} {who} {quote[:40]}"):
                    result = run(text, corti(sel), [read(who, [code(text, case['act'], quote)])])
                    got = [who, quote, short(result, case['act']), short(result, case['base']),
                           result.completeness.get('state')]
                    self.assertEqual(got, row, case['read'])
                    self.assertEqual(got[2], ['ALT'])
                    self.assertEqual((got[3], got[4]), (case['alone'][0], case['alone'][1]))
