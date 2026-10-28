"""Cost bounds found by refutation round r1 (cost lens) on the documented-service reader (studio/gi/services.py).

Each input is a synthetic document shape the lens measured past the assess stage's 120 s limit, or growing faster than
linearly toward it. The bound asserted here is far above the measured time after the repair, so a loaded host does not
fail it; what it catches is the quadratic or cubic growth coming back. Synthetic data only.
"""
import itertools
import random
import time
from datetime import date

from django.test import SimpleTestCase

from studio import jobs
from studio.gi import context as gi_context
from studio.gi import detect, services

DAY = date(2026, 10, 14)
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n\n'
SITES = ['cecum', 'appendiceal orifice', 'ileocecal valve', 'ascending colon', 'hepatic flexure', 'transverse colon',
         'splenic flexure', 'descending colon', 'sigmoid colon', 'rectosigmoid', 'rectum', 'terminal ileum',
         'anal canal', 'colon', 'ileum']


def built_in(text):
    routing = detect.route(text, DAY)
    facts = gi_context.extract_context(text)
    started = time.perf_counter()
    services.build(text, service_date=DAY, routing=routing, context_facts=facts)
    return time.perf_counter() - started


class ReaderCostTests(SimpleTestCase):
    def test_a_numeric_appendix_is_read_in_linear_time(self):
        """K0: every full stop between two digits re-read the whole sentence before it (120 s at 200,000 characters)."""
        rnd = random.Random(11)
        rows = [' '.join(f'{rnd.uniform(1.0, 7.9):.1f}' for _ in range(16)) for _ in range(1500)]
        text = (HEAD + 'Date of service: 2026-10-14\n24-hour pH-impedance study\nThe 24-hour pH-impedance study was '
                'performed and recorded.\npH tracing, distal channel (one value per minute):\n' + '\n'.join(rows) + '\n')
        self.assertGreater(len(text), 95_000)
        self.assertLess(built_in(text), 20.0)  # about 0.3 s after the repair; well over 30 s before it

    def test_statements_done_and_denied_are_compared_in_bounded_time(self):
        """K3: a done act against every denied act, each scanning every act, was cubic (121 s at 1,980 acts)."""
        out = [f'A {s} mm sessile polyp was seen in the {SITES[s % 11]}.' for s in range(1, 61)]
        for s in range(1, 61):
            out.append(f'The {s} mm polyp was not biopsied, as the endoscopist recorded at the end of the withdrawal.')
            out.append(f'Nurse: the {s} mm polyp was not biopsied, as recorded on the nursing flow sheet.')
        out += [f'Random biopsies were taken from the {a}, the {b} and the {c}.'
                for a, b, c in list(itertools.permutations(SITES, 3))[:900]]
        text = (HEAD + 'COLONOSCOPY REPORT\nThe colonoscope was advanced to the cecum and the examination was '
                'complete.\n\n' + '\n'.join(out) + '\n')
        self.assertLess(built_in(text), 30.0)  # about 1.6 s after the repair; 31.6 s before it

    def test_many_history_and_plan_headings_are_read_in_linear_time(self):
        """K5: every part scanned every section, mark and timed section (42 s at 195,000 characters)."""
        text = (HEAD + 'COLONOSCOPY REPORT\nThe colonoscope was advanced to the cecum. A 6 mm polyp was removed with a '
                'cold snare.\n\n' + 'History:\nPlan:\n' * 6000)
        self.assertLess(built_in(text), 20.0)  # about 0.8 s after the repair; over 10 s before it


class AnalyzeMentionCapTests(SimpleTestCase):
    """K2/K4: the analyze stage's cap counted routing's vocabulary only, so a note naming a service only the reader
    knows ("HRM") or an act thousands of times passed it and took the assess stage past its limit."""

    def test_the_reader_s_own_vocabulary_is_counted(self):
        line = ' '.join(['HRM'] * 300) + '.'
        text = HEAD + '\n'.join([line] * 20) + '\n'
        self.assertEqual(detect.service_mention_count(text), 0)
        self.assertGreater(services.mention_count(text, 1000), 1000)
        self.assertIsInstance(jobs._analyze_child(text, {}, 1000), int)  # refused: only the count is returned
        acts = HEAD + 'Colonoscopy was performed to the cecum.\n' + ('biopsy ' * 170 + '.\n') * 10
        self.assertIsInstance(jobs._analyze_child(acts, {}, 1000), int)

    def test_an_ordinary_report_is_far_under_the_cap(self):
        text = (HEAD + 'Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope was advanced to the cecum. A '
                '6 mm polyp was removed with a cold snare and biopsies were taken from the rectum.\n')
        self.assertLess(services.mention_count(text, 1000), 20)
        self.assertNotIsInstance(jobs._analyze_child(text, {}, 1000), int)
