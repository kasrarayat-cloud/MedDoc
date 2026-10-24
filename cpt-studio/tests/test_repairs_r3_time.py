"""Regressions for refutation round 3 over routing's time, history and today readings (the TIME repairs of round 3b).

Each class reproduces one confirmed finding (routing:N, validation:N or contract:N in the round-3 triage) from its
exact input, adds the variants the finding and its verifier list, and pins the positive controls an over-correction
would break. Routing runs for real, for the document's own service date and through the JSON round trip the pipeline
applies; the real validation engine assesses provider-shaped selections. Synthetic text only; pure functions.

The hold-only rule (round-3b contract, section 1) governs every new wording rule here: it may move a reading only to
uncertain. The exceptions are the regression repairs, which restore the reading an ordinary note had at 57b4b3747, and
the one release this round allows (a plan-section performance statement that says today, routing:26).
"""
import unittest

from studio.gi.detect import status_for_span
from tests.test_repairs_status_r2_routing import (HEADER, check, clarified, fact_value, family, read, ready, routed,
                                                  run_engine)

NOT_TODAY = ('planned', 'historical', 'cancelled', 'negated')
POSITIVE = ('performed', 'incomplete')
OFFICE_HEAD = HEADER + 'Place of service: Office (POS 11)\n'


def unproposed(result):
    return next(c for c in result.encounter_checks if c.id == 'services.unproposed')


# --- routing:0 ---------------------------------------------------------------------------------------------------

ROUTING0_FINDINGS = ('Findings: The colonoscope was advanced to the cecum. A 6 mm polyp was removed with a cold '
                     'snare.\n')
ROUTING0_POLYP = 'A 6 mm polyp was removed with a cold snare.'
ROUTING0_LINES = (
    'Colonoscopy with cold snare polypectomy for a positive FIT last month.',
    'Colonoscopy with cold snare polypectomy for iron deficiency anemia diagnosed last month.',
    'Colonoscopy with cold snare polypectomy for a colonic mass seen on CT last week.',
    'Colonoscopy with cold snare polypectomy for an abnormal CT done at an outside hospital.',
    'Colonoscopy with cold snare polypectomy for a mass found on a CT colonography performed elsewhere.',
    'Colonoscopy with cold snare polypectomy for anemia diagnosed last year.',
    'Colonoscopy with cold snare polypectomy for an abnormal CT the previous week.',
    'Colonoscopy with cold snare polypectomy for a polyp seen by her previous gastroenterologist.',
    'Colonoscopy with cold snare polypectomy today for a positive FIT last month.',
    'Colonoscopy with cold snare polypectomy for a positive CT colonography performed elsewhere.',
)
ROUTING0_VISITS = (
    'Established patient office visit to review a CT scan done last week.',
    'Established patient office visit today to review a CT scan done last week.',
    'Established patient office visit for anemia diagnosed last month.',
    'Established patient office visit to discuss a CT from an outside hospital.',
    'Established patient office visit for a positive FIT last month.',
)


def routing0_office(visit):
    return (OFFICE_HEAD + visit + '\nChief complaint: GI symptoms.\nAssessment: Stable.\n'
            'Medical decision making: moderate.\nTotal time: 32 minutes.\n')


class Routing0TimeOfAnotherThingTests(unittest.TestCase):
    """routing:0 (critical, a regression from round 2b status:8). The relative-time and outside-place history cues
    ('last month', 'elsewhere'; 'ago' read the same way) attached to the service named beside a test, a result or a
    diagnosis: ordinary procedure lines and E/M visit statements read historical and their codes were excluded. A cue
    is the service's only when it tells the time of the service's own act; one that trails a test, a result or a
    diagnosis is that thing's, and an E/M visit statement is never demoted by the round-2b cues."""

    def test_the_procedure_lines_read_performed(self):
        for line in ROUTING0_LINES:
            text = HEADER + 'Procedure: ' + line + '\n' + ROUTING0_FINDINGS
            with self.subTest(line=line):
                self.assertEqual(family(text, 'gi.colonoscopy'), 'performed')
                status, cues = read(text, line)
                self.assertEqual(status, 'performed', cues)
                for evidence in (line, ROUTING0_POLYP):
                    proposals, _ = run_engine(text, [('45385', evidence)])
                    self.assertTrue(ready(proposals['45385']),
                                    (evidence, proposals['45385'].exclusion_reason, clarified(proposals['45385'])))

    def test_an_egd_line_for_a_diagnosis_reads_performed(self):
        line = 'EGD with biopsy for iron deficiency anemia diagnosed last month.'
        text = HEADER + 'Procedure: ' + line + '\nFindings: The gastroscope was advanced to the second part of the ' \
                                              'duodenum. Biopsies were taken from the antrum.\n'
        self.assertEqual(family(text, 'gi.egd'), 'performed')
        proposals, _ = run_engine(text, [('43239', line)])
        self.assertTrue(ready(proposals['43239']), proposals['43239'].exclusion_reason)

    def test_an_office_visit_statement_is_never_demoted(self):
        for visit in ROUTING0_VISITS:
            text = routing0_office(visit)
            with self.subTest(visit=visit):
                status, cues = read(text, visit)
                self.assertEqual(status, 'performed', cues)
                proposals, result = run_engine(text, [('99214', visit)])
                self.assertTrue(ready(proposals['99214']), proposals['99214'].exclusion_reason)
                self.assertNotIn('Office / outpatient evaluation and management', unproposed(result).detail)

    def test_no_round_2b_cue_demotes_an_office_visit_statement(self):
        """Not even one no test precedes: the statement is the note's own visit (the round-3b brief)."""
        for visit in ('Established patient office visit following an emergency department stay last week.',
                      'Established patient office visit with records from another hospital.'):
            text = routing0_office(visit)
            with self.subTest(visit=visit):
                status, cues = read(text, visit)
                self.assertEqual(status, 'performed', cues)

    def test_the_services_own_history_stays_historical(self):
        for line in ('EGD was performed last month at an outside hospital.', 'She underwent EGD last year.',
                     'An EGD was done elsewhere.', 'Last month she underwent EGD.', 'EGD two years ago was normal.',
                     'Colonoscopy with polypectomy last year.', 'EGD was performed by her previous gastroenterologist.'):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                status, cues = read(text, 'EGD' if 'EGD' in line else 'Colonoscopy')
                self.assertEqual(status, 'historical', cues)

    def test_a_cue_whose_owner_is_unclear_holds(self):
        """Neither the service's own act nor a test stands before the cue: held for clarification, never excluded
        and never performed."""
        for line in ('EGD for dysphagia last month.', 'Colonoscopy with removal of a sessile polyp two years ago.'):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                status, cues = read(text, line.split()[0])
                self.assertEqual(status, 'uncertain', cues)
                self.assertTrue(any(line.split()[-2] in c or 'ago' in c for c in cues), cues)

    def test_a_pre_existing_cue_after_a_test_holds_and_never_releases(self):
        """'ago' was read at 57b4b3747, so its exclusion is not a round-2b regression: after a test it now holds."""
        text = HEADER + 'Procedure: Colonoscopy with cold snare polypectomy for a positive FIT two weeks ago.\n'
        status, cues = read(text, 'Colonoscopy')
        self.assertEqual(status, 'uncertain', cues)

    def test_the_services_own_history_beside_today_holds(self):
        for line in ('EGD was performed today at an outside hospital.', 'Today she underwent EGD at an outside hospital.',
                     'EGD at an outside hospital today.', 'Today she underwent EGD last month.'):
            text = HEADER + 'Procedure: ' + line + '\n'
            with self.subTest(line=line):
                status, cues = read(text, 'EGD')
                self.assertEqual(status, 'uncertain', cues)
        # a today marker of another service's group does not touch this one's history
        text = HEADER + 'Procedure: Colonoscopy today; she underwent EGD last year and colonoscopy today.\n'
        self.assertEqual(read(text, 'EGD')[0], 'historical')

    def test_a_symptoms_time_and_a_request_are_still_not_history(self):
        for line in ('Colonoscopy for rectal bleeding since last month.', 'Colonoscopy for bleeding that started two '
                     'weeks ago.', 'Colonoscopy for anemia noted over the last year.'):
            with self.subTest(line=line):
                self.assertEqual(family(HEADER + 'Procedure: ' + line + '\n', 'gi.colonoscopy'), 'performed')


if __name__ == '__main__':
    unittest.main()
