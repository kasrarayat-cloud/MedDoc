"""Regressions for refutation round 5 over validation (round 4c repairs, VALIDATION).

Each class reproduces one confirmed finding through the real router (JSON round-tripped as the assess stage stores
it), the real span reader and the engine, and pins the controls that must keep their reading. Synthetic text only;
pure functions.
"""
import json
from datetime import date

from studio.gi.detect import route
from studio.types import EvidenceSpan, RoutingResult, from_jsonable, to_jsonable
from studio.validation import checks, engine
from tests.test_repairs_r3_validation_b import HEAD, Case
from tests.test_repairs_r4_validation import assess_timed

DAY = date(2026, 10, 21)


def routed(text, day=DAY):
    return from_jsonable(RoutingResult, json.loads(json.dumps(to_jsonable(route(text, day)))))


# --- bounded:4: a hedged passage's other-service question is indexed once per code ----------------------------------

class Bounded4OtherServiceIndexTests(Case):
    """bounded:4 (high). engine._other_service scanned every routed mention for every hedged linked passage: 20,000
    'Possible EGD?' lines cited by 43235 and 43239 took 82 s in assess() (the worker's assess stage has a 60 s
    allowance). The routed mentions are indexed once per code now, with the same overlap answer."""

    def test_many_hedged_passages_over_many_routed_mentions_assess_in_bounded_time(self):
        lines = 10000
        text = HEAD + 'Findings:\n' + 'Possible EGD?\n' * lines
        first = len(HEAD) + len('Findings:\n')
        spans = [(first + 14 * n, first + 14 * n + 13) for n in range(lines)]
        elapsed, result = assess_timed(text, ('43235', spans), ('43239', spans))
        self.assertLess(elapsed, 9.0)  # 17.6 s scanning every mention per passage; about 2.5 s indexed
        self.assertEqual([(p.code, p.status) for p in result.proposals],
                         [('43235', 'needs_clarification'), ('43239', 'needs_clarification')])

    def test_the_indexed_answer_is_the_scan_s_answer(self):
        """The round-5 verifier's mixed case: every hedged passage of every family, in four sections, answered both
        ways; the index must give the scan's answer for each."""
        lines = ['Possible EGD?', 'Possible colonoscopy?', 'Possible EGD and biopsy of the sigmoid colon?',
                 'Established patient office visit today; possible EGD if symptoms persist?',
                 'Colonoscopy with biopsy was performed today; possible EGD?',
                 'It is unclear whether biopsies were taken.', 'Rule out celiac disease?',
                 'Possible hemorrhoid banding?', 'EGD to the second portion of the duodenum.']
        body = []
        for section in ('Findings:', 'Assessment and plan:', 'History of present illness:', 'Procedure:'):
            body += [section] + lines * 2
        text = HEAD + '\n'.join(body) + '\n'
        routing = routed(text)
        families = engine._VAL_family_index(routing)
        answers = {True: 0, False: 0}
        at = len(HEAD)
        for line in text[len(HEAD):].split('\n'):
            if line.strip() and not line.endswith(':'):
                (reading,) = checks.evidence_readings(text, [EvidenceSpan(0, at, at + len(line), line, True)], DAY)
                for family in ('gi.egd', 'gi.colonoscopy', 'gi.office_em', 'gi.other'):
                    scanned = self.scan(reading, family, routing, text)
                    with self.subTest(line=line, family=family):
                        self.assertEqual(engine._other_service(reading, family, families, text), scanned)
                    answers[scanned] += 1
            at += len(line) + 1
        self.assertTrue(answers[True] and answers[False], answers)

    @staticmethod
    def scan(reading, family, routing, text):
        """engine._other_service as it read at 9a9f403: a scan of every routed mention."""
        if reading.status != 'uncertain' or checks.silent(reading.status, reading.cues):
            return False
        named = {f.family for f in routing.findings for m in f.mentions
                 if m.span.start < reading.end and reading.start < m.span.end}
        if family in checks.EM_FAMILIES:
            return 'gi.office_em' not in named
        return bool(named) and family not in named and not checks.names_intervention(text, reading.start, reading.end,
                                                                                      family)
