"""Refutation of the integrated completion diff, cycle 4 (2026-11-06; HARNESS.md "Refutation of the integrated diff,
cycle 4"). Five lenses over cycle 3's repair reported 23 findings. Their engine-level inputs, stated variants and parity
twins (tests/fixtures/gi4/refutation/completion-c4-cases.json) were read on the installed base (b452c6c4), the cycle-2
head (844fe54c) and the cycle-3 head (52a5f774) before anything changed. The repair reads every one as the installed
base reads it, apart from the releases the requirement rests on, each named below with the parity that bounds it: the
installed base reads the same statement READY in its twin (the input without the released construct, or a labelled
paragraph's "Procedure:" heading form), or the base never reads the code READY at all (the bolus removal). Synthetic
documents only; nothing is sent."""
from __future__ import annotations

import json
from pathlib import Path

from django.test import SimpleTestCase

from studio.gi import cues, detect
from studio.gi import services as gi_services
from tests.test_harness_engine import code, corti, read, run, span

FIXTURE = Path(__file__).parent / 'fixtures' / 'gi4' / 'refutation' / 'completion-c4-cases.json'
CASES = json.loads(FIXTURE.read_text(encoding='utf-8'))['cases']
BY_LABEL = {case['label']: case for case in CASES}
QUIET = ('pass', 'not_applicable', 'not_verified', 'info')

# Inputs the repair reads otherwise than the installed base, by design - each class with the parity that bounds it.
PURPOSE = ('k3 ', 'k4 ', 'k7 ')  # closed 3, 4, 7: "for future localization" read as a purpose - its twin without it
REACH = ('k5 ', 'k8 ')  # closed 5, 8: "Cecal intubation was achieved." - its twin "The colonoscope was advanced to the cecum."
BOLUS = ('k6 ',)  # closed 6: the bolus removal the base never reads READY in any form (its recorded false hold)
INTENDED_ELSEWHERE = {
    # equal eligibility (U8): Astra's removal code is read as Corti's would be - held, with the base code it holds
    'k1 d astra': {'45378': 'HELD', '45385': 'HELD'},
    # a released label's own sentence is its heading twin's first sentence: the twin's READY with service.incomplete
    's4 status': {'45385': 'READY', '45378': 'HELD'},
}


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


def labels(read_out: dict) -> dict:
    return {c: v[0] for c, v in read_out.items()}


def released(case_label: str) -> bool:
    name = case_label[3:] if case_label.startswith('TW ') else case_label
    return name.startswith(PURPOSE + REACH + BOLUS) and not name.startswith('k4 g')


class CycleFourInputTests(SimpleTestCase):
    """Every input as pinned: the fixture's head reading, equal to the installed base's but for the named releases."""

    def test_every_input_reads_as_pinned(self):
        for case in CASES:
            if case['day']:
                continue  # the same input on the jobs path, measured there in the session
            with self.subTest(case['label']):
                self.assertEqual(reading(case), case['head'])

    def test_the_head_is_the_installed_base_but_for_the_named_releases(self):
        for case in CASES:
            with self.subTest(case['label']):
                head, base = labels(case['head']), labels(case['base'])
                name = case['label']
                twin = BY_LABEL.get('TW ' + name)
                if name in INTENDED_ELSEWHERE:
                    self.assertEqual(head, INTENDED_ELSEWHERE[name])
                elif released(name) and name.startswith(BOLUS):
                    self.assertEqual(head, {**base, '43247': 'READY'})  # the bolus removal only
                elif released(name) and not name.startswith('TW ') and twin is not None:
                    # the input reads as its twin does, and the installed base reads the twin so
                    self.assertEqual(head, labels(twin['head']))
                    self.assertEqual(labels(twin['head']), labels(twin['base']))
                elif released(name):
                    # a control with no twin in the fixture ("Cecal intubation was achieved." alone): the release only
                    self.assertTrue(all(lab == base.get(c) or c in ('45381', '43236', '45385', '45378', '43235')
                                        for c, lab in head.items()))
                else:
                    self.assertEqual(head, base)

    def test_each_purpose_and_reach_release_reads_as_the_base_reads_its_twin(self):
        """closed 3, 4, 5, 7, 8: whatever the release lets through, the installed base reads the same statement READY
        without the released construct - the installed reader's own clause-local time and extent readings."""
        for case in CASES:
            name = case['label']
            if name.startswith('TW ') or not name.startswith(PURPOSE + REACH) or name.startswith('k4 g'):
                continue
            twin = BY_LABEL.get('TW ' + name)
            if twin is None:
                continue
            with self.subTest(name):
                for c, (lab, _flags) in case['head'].items():
                    if lab == 'READY' and case['base'].get(c, ['-'])[0] != 'READY':
                        self.assertEqual(twin['base'][c][0], 'READY')

    def test_the_findings_main_inputs_read_as_the_installed_base(self):
        """One assertion per finding that the repair closed (the parity classes apart)."""
        for name in ('o1 main', 'o1 band', 'o1 failed during', 'o2 main', 'o2 ercp', 'o3 main', 'o4 main', 'o4 b',
                     'o5 main', 'o5 d', 'k1 main', 'k2 main', 'k4 g', 's1 main', 's1 d', 's3 main', 's3 b', 's4 main',
                     's4 egd'):
            with self.subTest(name):
                case = BY_LABEL[name]
                self.assertEqual(labels(case['head']), labels(case['base']))
                self.assertNotEqual(case['cycle3'], case['base'])  # each finding was real at 52a5f774 (a flag counts)
        for name in ('s2 main', 's2 b', 's2 c', 's2 d'):  # held as the heading twin is
            with self.subTest(name):
                self.assertEqual(set(labels(BY_LABEL[name]['head']).values()), {'HELD'})
        # outcome 3 and 4: the installed incompleteness warning comes back
        for name in ('o3 main', 'o3 c', 'o3 f', 'o4 main', 'o4 c', 'o2 unsuccessful left', 'o2 ercp stones unsuccessful'):
            with self.subTest(name):
                case = BY_LABEL[name]
                self.assertEqual(case['head'], case['base'])
                self.assertTrue(any('service.incomplete' in flags for _lab, flags in case['head'].values()))


class FailureWordTests(SimpleTestCase):
    """outcome 1 and 5: the services reader's failure words are the installed release's three again."""

    def test_the_failure_words_are_the_installed_releases(self):
        for said in ('failed', 'unsuccessful', 'unsuccessfully', 'abandoned'):
            self.assertIsNotNone(cues.FAILED_ACT.fullmatch(said))
        for said in ('aborted', 'terminated', 'discontinued', 'halted', 'precluded'):
            self.assertIsNone(cues.FAILED_ACT.search(said))

    def test_the_attribute_reads_across_any_three_words(self):
        self.assertEqual(cues.FAILED_ACT_BEFORE.search('The examination was abandoned before ').group('w'), 'abandoned')
        self.assertEqual(cues.FAILED_ACT_BEFORE.search('The hot snare failed during ').group('w'), 'failed')
        self.assertIsNone(cues.FAILED_ACT_BEFORE.search('The procedure was aborted after the '))
        self.assertIsNone(cues.FAILED_ACT_BEFORE.search(', with aspirin discontinued for five days, '))


class SubActFailureFormTests(SimpleTestCase):
    """outcome 2-4, cost 1: a failure is a sub-act's own only in the closed attempt form."""

    COLON = ('Colonoscopy Report\nDate of service: 2026-10-14\nEndoscopist: Test Endoscopist, MD\nIndication: Chronic '
             'diarrhea.\nProcedure: Colonoscopy. The colonoscope was advanced to the cecum. A 6 mm polyp in the ascending '
             'colon was removed with a cold snare and retrieved. ')

    def form(self, sentence: str) -> bool:
        """Whether routing reads the sentence's failure as a sub-act's own (the closed form): the colonoscopy stays
        performed, where any other failure is the examination's (incomplete, the installed reading)."""
        from tests.test_harness_engine import DAY
        return detect.route(self.COLON + sentence + '\n', DAY).finding('gi.colonoscopy').status == 'performed'

    def test_the_u3_shapes_are_the_form(self):
        for sentence in (
                'Hot snare polypectomy of a 14 mm pedunculated polyp in the sigmoid colon was attempted, but the '
                'polypectomy was unsuccessful because of poor positioning; the polyp was left in place.',
                'Hot snare polypectomy of a 14 mm sigmoid polyp was attempted, but the polypectomy was unsuccessful; the '
                'polyp was left in place.',
                'Balloon dilation of a distal esophageal stricture was attempted, but the dilation was unsuccessful because '
                'of poor positioning.'):
            with self.subTest(sentence):
                self.assertTrue(self.form(sentence))

    def test_nothing_else_is(self):
        # refutation cycle 5 (routing 2): a line break, a semicolon's unknown clause, a reason with its own clause, or an
        # elliptical next sentence ends no form
        for sentence in (
                'Hot snare polypectomy of a 14 mm polyp was attempted, but the polypectomy was unsuccessful\nas was the '
                'remainder of the examination because of desaturation.',
                'Hot snare polypectomy of a 14 mm polyp was attempted, but the polypectomy was unsuccessful; so was the '
                'remainder of the examination.',
                'Hot snare polypectomy of a 14 mm polyp was attempted, but the polypectomy was unsuccessful because of a '
                'perforation that ended the procedure.',
                'Hot snare polypectomy of a 14 mm polyp was attempted, but the polypectomy was unsuccessful. So was the '
                'remainder of the examination.',
                'The cold snare polypectomy of this polyp was aborted because of bleeding.',
                'Hot snare polypectomy and the cold forceps biopsy were unsuccessful because of poor positioning.',
                'Polypectomy of the 8 mm sigmoid polyp was aborted because of desaturation, as was the remainder of the '
                'examination.',
                'Hot snare polypectomy of the 14 mm polyp was attempted, but the polypectomy was unsuccessful.',
                'Hot snare polypectomy of a 14 mm polyp was attempted, but the polypectomy and the biopsy were '
                'unsuccessful.',
                'Hot snare polypectomy of a 14 mm polyp was attempted, but the polypectomy was unsuccessful, as was the '
                'examination.',
                'Hot snare polypectomy of a 14 mm polyp was attempted, but the biopsy was unsuccessful.'):
            with self.subTest(sentence):
                self.assertFalse(self.form(sentence))


class LabelledBindingTests(SimpleTestCase):
    """structure 2: a labelled paragraph binds its acts only until a scope sentence outside its own tract."""

    def test_the_scope_word_is_read_by_its_form(self):
        for said in ('the gastroscope', 'The colonoscope', 'the upper scope', 'the pediatric scope', 'an endoscope',
                     'the scope'):
            self.assertIsNotNone(gi_services._SCOPE_WORD.search(said))
        self.assertIsNone(gi_services._SCOPE_WORD.search('A retrieval net was passed through the working channel'))
