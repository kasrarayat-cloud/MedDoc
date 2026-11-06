"""Refutation of the integrated completion diff, cycle 3 (2026-11-06; HARNESS.md "Refutation of the integrated diff,
cycle 3"). Six lenses over cycle 2's change of approach reported 32 findings. Their engine-level inputs
(tests/fixtures/gi4/refutation/completion-c3-cases.json) were measured on the installed base (b452c6c4), the cycle-1
head (5fa33480) and the cycle-2 head (844fe54c) before anything changed; the repair reads each as the installed base
reads it, the intended releases apart (named below, each with why). The parity lens's labelled-paragraph inputs
(completion-c3-parity.json, with the base's reading of every twin) are read no more permissively than the installed
base reads their twins - against the base's own reading, never the same tree's twin (parity C3-7) - the recorded
exceptions apart. Synthetic documents only; nothing is sent."""
from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import purpose, structure
from studio.gi import services as gi_services
from tests.test_harness_engine import code, corti, read, run, span

FIXTURES = Path(__file__).parent / 'fixtures' / 'gi4' / 'refutation'
CASES = json.loads((FIXTURES / 'completion-c3-cases.json').read_text(encoding='utf-8'))['cases']
PARITY = json.loads((FIXTURES / 'completion-c3-parity.json').read_text(encoding='utf-8'))['pairs']
QUIET = ('pass', 'not_applicable', 'not_verified', 'info')
BANNER = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
REPORT_HEAD = BANNER + ('Gastroenterology Procedure Report\nDate of service: 2026-10-14\nEndoscopist: Synthetic '
                        'Endoscopist, MD (fictional)\n')

# Where the repair reads a cycle-3 input otherwise than the installed base, by design.
INTENDED = {
    # the purpose release (purpose.MARKING_STATEMENT): a marking stated done for a later localization is today's
    'closed-3 control tattooed': {'45381': 'READY'},
    # the bolus anaphor bound to a whole-sentence plain finding of today (U1)
    'closed-4 control plain': {'43247': 'READY'},
    # equal eligibility (U8): a participant's code is read as Corti's is - held, with its question, beside the base
    # code it holds; the base had not admitted it at all
    'admission-1 astra': {'45378': 'HELD', '45385': 'HELD'},
    'admission-2 astra': {'45378': 'HELD', '45385': 'HELD'},
    'admission-3b astra': {'45378': 'HELD', '45385': 'HELD'},
    'admission-3 astra': {'45378': 'HELD', '45385': 'HELD'},
}
# Labelled inputs read READY where the base holds the twin, each recorded (ACCURACY-RESIDUALS.md, cycle 3): the H2
# shape's bolus removal, which the heading twin holds by its own false hold whatever the status line says (corpus 137,
# the parity test's recorded exception; the base twin reads the same document's 43239 and 45385 READY, its status line
# beyond the base's window); and one input the base itself reads READY (its twin names both families).
PARITY_EXCEPTIONS = (('fin:F3g H2 pre-assessment', '43247'), ('b2:H2 head status', '43247'),
                     ('b2:H2 status after impression', '43247'), ('b6:H2 Consent: The patient declined', '43247'),
                     ('b8:EGDhd col-switch | Dysphagia; surv', '43251'))


def label(p) -> str:
    if p.bucket == 'excluded':
        return 'EXCL'
    return 'READY' if p.status == 'ready' else 'HELD'


def readings(text, picks, astra=()) -> dict:
    parts = [read('astra', [code(text, c, q) for c, q in astra])] if astra else []
    result = run(text, corti(*[(c, span(text, q)) for c, q in picks]), parts)
    return {p.code: label(p) for p in result.proposals if p.bucket != 'alternative'}


def proposals(text, picks) -> dict:
    result = run(text, corti(*[(c, span(text, q)) for c, q in picks]))
    return {p.code: p for p in result.proposals if p.bucket != 'alternative'}


def flagged(p) -> set:
    return {c.id for c in p.checks if c.status not in QUIET}


class CycleThreeInputTests(SimpleTestCase):
    """Every engine-level input of the findings, as the installed base reads it (the intended releases apart)."""

    def test_every_input_reads_as_the_installed_base_or_its_named_release(self):
        for case in CASES:
            if case['day']:
                continue  # the same input on the jobs path; measured there in the session, read here once
            with self.subTest(case['label']):
                expected = INTENDED.get(case['label'], case['base'])
                self.assertEqual(readings(case['text'], case['picks'], case['astra']), expected)

    def test_the_intended_releases_differ_from_the_base(self):
        for name, wanted in INTENDED.items():
            (case,) = [c for c in CASES if c['label'] == name]
            with self.subTest(name):
                self.assertNotEqual(case['base'], wanted)


class ConsumedFailureTests(SimpleTestCase):
    """Routing gives a failure to a sub-act only where the services reader reads that act failed by the same word."""

    def test_a_failure_the_services_reader_does_not_read_keeps_the_examinations_flag(self):
        text = (BANNER + 'ERCP report (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient '
                'department\nProcedure: ERCP with biliary stent placement\nThe duodenoscope was advanced to the second '
                'portion of the duodenum. Deep biliary cannulation was achieved. A distal common bile duct stricture was '
                'seen.\nThe stent could not be advanced through the stricture.\n')
        (p,) = proposals(text, [('43274', 'ERCP with biliary stent placement')]).values()
        self.assertEqual(label(p), 'READY')
        self.assertIn('service.incomplete', flagged(p))  # the installed release's warning, back (outcome C3-3)

    def test_a_sub_act_the_services_reader_has_no_act_for_keeps_the_hold(self):
        text = (REPORT_HEAD + 'Procedure: Colonoscopy\nIndications: Surveillance.\nDescription of procedure: The '
                'colonoscope was introduced through the anus and advanced to the cecum. A cold snare was placed around '
                'the 6 mm polyp in the sigmoid colon. Removal was aborted because of bleeding, and the polyp was left in '
                'place.\n')
        (p,) = proposals(text, [('45385', 'A cold snare was placed around the 6 mm polyp in the sigmoid colon.')]).values()
        self.assertEqual(label(p), 'HELD')  # cost C3-1

    def test_the_examinations_abort_after_done_biopsies_is_the_examinations(self):
        text = (REPORT_HEAD + 'Procedure: Colonoscopy\nIndications: Surveillance.\nDescription of procedure: The '
                'colonoscope was introduced through the anus and advanced to the cecum. Cecal intubation was achieved. '
                'Cold forceps biopsies were obtained from the sigmoid colon. The procedure was aborted after the '
                'biopsies due to poor preparation.\n')
        (p,) = proposals(text, [('45380', 'Cold forceps biopsies were obtained from the sigmoid colon.')]).values()
        self.assertEqual(label(p), 'READY')
        self.assertIn('service.incomplete', flagged(p))  # cost C3-4: READY with the installed warning, never held

    def test_a_sub_acts_own_failure_is_still_its_own(self):
        # the required shape (D|RT-a1, e888f9ce): the services reader reads the failed attempt, routing gives it there
        text = (BANNER + 'Colonoscopy Report\nDate of service: 2026-10-14\nEndoscopist: Test Endoscopist, MD\n'
                'Indication: Chronic diarrhea.\nProcedure: The colonoscope was advanced to the cecum. A 6 mm polyp in the '
                'ascending colon was removed with a cold snare and retrieved. Hot snare polypectomy of a 14 mm polyp in '
                'the sigmoid colon was attempted, but the polypectomy was unsuccessful because of poor positioning; the '
                'polyp was left in place.\n')
        quote = 'A 6 mm polyp in the ascending colon was removed with a cold snare and retrieved.'
        (p,) = proposals(text, [('45385', quote)]).values()
        self.assertEqual(label(p), 'READY')
        self.assertNotIn('service.incomplete', flagged(p))


class ReachTests(SimpleTestCase):
    def test_a_retracted_reach_statement_asks_the_extent(self):
        text = (REPORT_HEAD + 'Procedure: Colonoscopy\nIndications: Surveillance.\nDescription of procedure: The '
                'colonoscope was introduced through the anus. Cecal intubation was achieved. A 6 mm polyp in the sigmoid '
                'colon was removed with a cold snare. Correction: cecal intubation was not achieved.\n')
        (p,) = proposals(text, [('45385', 'A 6 mm polyp in the sigmoid colon was removed with a cold snare.')]).values()
        self.assertEqual(label(p), 'HELD')
        self.assertIn('extent', [q.fact for q in p.clarifications])  # cost C3-5

    def test_a_lone_reach_statement_still_completes_the_extent(self):
        text = BANNER + ('Date of service: 2026-10-14\nProcedure: Colonoscopy.\nCecal intubation was achieved. A 6 mm '
                         'sigmoid polyp was removed with a cold snare.\n')
        (p,) = proposals(text, [('45385', 'A 6 mm sigmoid polyp was removed with a cold snare.')]).values()
        self.assertEqual(label(p), 'READY')  # D|ARCH-D10b


class UnitsTests(SimpleTestCase):
    def test_two_stents_listed_twice_are_two_units_with_the_installed_prompt(self):
        text = (BANNER + 'ERCP report (fictional)\nDate of service: 2026-10-14\nPlace of service: Hospital outpatient '
                'department\nProcedure: ERCP\nThe duodenoscope was advanced to the second portion of the duodenum.\nThe '
                'common bile duct was deeply cannulated.\nA 10 Fr by 7 cm plastic stent was placed in the common bile '
                'duct.\nA 10 Fr by 9 cm plastic stent was placed across the prior sphincterotomy into the left hepatic '
                'duct.\n')
        result = run(text, corti(('43274', span(text, 'A 10 Fr by 7 cm plastic stent was placed in the common bile duct')),
                                 ('43274', span(text, 'A 10 Fr by 9 cm plastic stent was placed across the prior '
                                                      'sphincterotomy into the left hepatic duct'))))
        (p,) = [p for p in result.proposals if p.code == '43274' and p.bucket != 'alternative']
        self.assertEqual((label(p), p.units), ('READY', 2))  # admission C3-4
        self.assertIn('units.duplicate', flagged(p))


class ClosedFormTests(SimpleTestCase):
    """The releases kept because required, each recognized whole."""

    def statement(self, sentence, word='for future'):
        text = BANNER + 'Colonoscopy report\nDate of service: 2026-10-14\nProcedure: Colonoscopy\n' + sentence + '\n'
        pos = text.index(word)
        from studio.gi import sections
        return purpose.marking_statement(text, pos, sections.layout(text).sentence_for(pos, pos + len(word)))

    def test_the_marking_statement_recognizes_the_required_shapes(self):
        for sentence in ('The lesion in the ascending colon was marked with submucosal tattoo for future localization '
                         'and not resected.',
                         'India ink was injected adjacent to the lesion in the ascending colon for future localization.',
                         'Tattoo ink injected into the transverse colon submucosa for future localization.',
                         'The transverse colon lesion was tattooed for future localization.',
                         'A separate 25 mm flat lesion in the transverse colon was marked\nwith submucosal tattoo for '
                         'future localization and not resected today; it will be referred for endoscopic mucosal\n'
                         'resection.'):
            with self.subTest(sentence):
                self.assertIsNotNone(self.statement(sentence))

    def test_the_marking_statement_admits_nothing_else(self):
        for sentence in ('A tattoo referral was placed for future localization.',
                         'A tattoo kit was obtained for future localization.',
                         'India ink was obtained from the pharmacy for future localization.',
                         'India ink was placed on the tray for future localization.',
                         'The tattoo needle was inserted into the accessory channel for future localization.',
                         'A tattoo was placed at her first colonoscopy for future localization.',
                         'India ink was injected distal to the lesion for future localization at the time of EMR.',
                         'India ink will be injected for future localization.',
                         'If India ink was injected adjacent to the lesion for future localization, surgery is easier.'):
            with self.subTest(sentence):
                self.assertIsNone(self.statement(sentence))

    def test_a_failed_technique_beside_a_done_act_naming_none_is_another_instance(self):
        self.assertTrue(gi_services._techniques_differ('balloon', ''))  # admission C3-5
        self.assertTrue(gi_services._techniques_differ('balloon', 'guidewire'))
        self.assertFalse(gi_services._techniques_differ('snare', 'cold snare'))
        self.assertFalse(gi_services._techniques_differ('cold snare', 'snare'))
        self.assertFalse(gi_services._techniques_differ('', 'balloon'))
        self.assertFalse(gi_services._techniques_differ('balloon', 'balloon'))


class LabelledParagraphParityTests(SimpleTestCase):
    """A labelled input is read no more permissively than the installed base reads its twin (parity C3-1 to C3-7)."""

    def test_no_labelled_input_is_ready_where_the_base_holds_its_twin(self):
        for pair in PARITY:
            got = readings(pair['text'], pair['picks'])
            for value, state in got.items():
                if state != 'READY' or pair['base_twin'].get(value) == 'READY':
                    continue
                with self.subTest(pair['name'], code=value):
                    self.assertTrue(any(pair['name'].startswith(name) and value == c for name, c in PARITY_EXCEPTIONS),
                                    f"{pair['name']} {value}: READY where the base holds the twin")

    def test_the_status_line_reaches_a_released_label(self):
        # parity C3-7: the pinned L7 with a report field line before its status line - released, so routing reads it
        text = (REPORT_HEAD + 'Indications: Screening.\nColonoscopy: The colonoscope was introduced through the anus and '
                'advanced to the cecum.\nWithdrawal time: 8 minutes.\nStatus: Cancelled - inadequate bowel '
                'preparation.\nImpression: Normal colon.\n')
        got = readings(text, [('45378', 'The colonoscope was introduced through the anus and advanced to the cecum.')])
        self.assertEqual(got, {'45378': 'HELD'})

    def test_the_frame_read_is_bounded(self):
        # parity C3-5: soft-wrapped label lines run into one layout sentence; each candidate reads its own extent only
        text = REPORT_HEAD + 'Indications: Screening.\n' + 'egd: a scope was passed and\n' * 400 + 'Impression: Normal.\n'
        lay = structure.gi_sections.layout(text)
        for c in structure._candidates(text, lay):
            self.assertLessEqual(structure._frame_end(c, len(text)) - c.body, structure.FRAME_REACH)
