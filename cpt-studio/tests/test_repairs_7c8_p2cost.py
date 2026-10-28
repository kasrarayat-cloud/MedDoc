"""Refutation phase 2 of the GI core, COST (stage time limits, a must-fix class; owner decision 2026-10-27).

cost2:2 (routing, studio/gi/detect.py; pre-existing at 057a7d398) - the typed done-question readers
  (_B3_SERVICE_ANSWERED_NO, _PERFORMED_ANSWERED_NO, _BOX_ANSWER_TAIL and checks' named_no) read the shared separator
  _BOX_Q_SEP before a denial. Its three runs of spaces split a run every way when the answer after it was no denial:
  'Colonoscopy performed' and 4,000 spaces (4,254 characters) took the analyze stage past 60 s, cubic in the run. The
  separator is now read once before a denial (_BOX_Q_SEP_ONCE, an atomic group): a denial opens with a letter, so only
  the separator's longest reading can be followed by one, and the group's first reading is its longest. The matches
  are the same; the pins compare with the patterns as they were.

Synthetic data only; no network.
"""
import random
import re
import time

from django.test import SimpleTestCase

from studio.gi import detect
from studio.validation import checks

HEAD = ('SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\nDate of service: 2026-10-14\n'
        'COLONOSCOPY REPORT\nThe colonoscope was advanced to the cecum and the examination was complete.\n')
TAIL = '\nThe patient tolerated the procedure well.\n'


def _before(pattern):
    """``pattern`` as it was: the separator read with every split before the denial."""
    assert detect._BOX_Q_SEP_ONCE in pattern.pattern
    return re.compile(pattern.pattern.replace(detect._BOX_Q_SEP_ONCE, detect._BOX_Q_SEP), pattern.flags)


def found(match):
    return None if match is None else (match.span(), match.groupdict())


class SeparatorOnceMatchesAsBeforeTests(SimpleTestCase):
    """Every reader of the separator before a denial finds exactly the matches it found before."""

    PIECES = ('Colonoscopy', 'EGD', 'Procedure', 'Tattoo injection [X]', 'Biopsy', 'performed', 'completed', 'done',
              'today', 'was the', 'Was', '- ', '1. ', ' ', '  ', '   ', '\t', '?', ':', '=', '|', '-', '–',
              '—', 'No', 'no', 'N', 'None', 'NA', 'N/A', 'not done', 'Not performed', 'not applicable', 'Yes',
              'x', '.', ',', '(', ')', ';', '!', 'polyps', 'no polyps')

    def patterns(self):
        return {'service_answered_no': detect._B3_SERVICE_ANSWERED_NO,
                'performed_answered_no': detect._PERFORMED_ANSWERED_NO,
                'box_answer_tail': detect._BOX_ANSWER_TAIL,
                'named_no': checks._V2_patterns()['named_no']}

    def test_every_reader_is_covered(self):
        """Every compiled reader that reads the separator before a denial is among those compared."""
        readers = [p for p in vars(detect).values() if isinstance(p, re.Pattern) and detect._BOX_Q_SEP_ONCE in p.pattern]
        readers += [p for p in checks._V2_patterns().values()
                    if isinstance(p, re.Pattern) and detect._BOX_Q_SEP_ONCE in p.pattern]
        self.assertEqual(set(readers), set(self.patterns().values()))  # a reader may be bound to two names

    def test_random_lines(self):
        rnd = random.Random(20261028)
        pairs = [(name, new, _before(new)) for name, new in self.patterns().items()]
        for _ in range(20000):
            line = ''.join(rnd.choice(self.PIECES) for _ in range(rnd.randint(1, 12)))
            for start in range(min(len(line), 3)):
                for name, new, old in pairs:
                    with self.subTest(pattern=name, line=line, start=start):
                        self.assertEqual(found(new.match(line, start, len(line))),
                                         found(old.match(line, start, len(line))))

    def test_field_lines(self):
        pairs = [(name, new, _before(new)) for name, new in self.patterns().items()]
        for line in ('Colonoscopy performed? No', 'Was the EUS performed today? No', 'EUS performed:  no.',
                     'Procedure performed: No (patient refused).', 'Exam completed? no', 'Procedure performed\tNo',
                     'Procedure performed?: No', 'Procedure performed? - No', 'Procedure performed ?  No',
                     'Procedure performed :   N/A', 'Procedure performed - Not done', 'Colonoscopy performed: no polyps',
                     'Colonoscopy performed' + ' ' * 40, 'Colonoscopy performed' + ' ' * 40 + 'No',
                     'Colonoscopy performed ?:- No', 'Biopsy done? :  no', ' today: No', ' today  -  none.'):
            for name, new, old in pairs:
                with self.subTest(pattern=name, line=line):
                    self.assertEqual(found(new.match(line)), found(old.match(line)))


class SeparatorOnceCostTests(SimpleTestCase):
    """A run of spaces after a typed done-question costs routing no more than its length."""

    def test_padded_done_questions_are_routed_in_linear_time(self):
        for line in ('Colonoscopy performed' + ' ' * 2000, 'Colonoscopy performed' + ' ' * 2000 + 'x',
                     'Procedure performed' + ' ' * 2000 + 'x', 'Tattoo injection [X] Performed' + ' ' * 2000):
            with self.subTest(line=line[:30]):
                started = time.process_time()
                detect.route(HEAD + line + TAIL, None)
                self.assertLess(time.process_time() - started, 2.0)  # about 17 CPU s each before the repair (cubic)

    def test_the_finding_s_paste_is_routed_well_inside_the_analyze_limit(self):
        started = time.process_time()
        detect.route(HEAD + 'Colonoscopy performed' + ' ' * 16000 + TAIL, None)  # 4,000 spaces overran 60 s before
        self.assertLess(time.process_time() - started, 5.0)
