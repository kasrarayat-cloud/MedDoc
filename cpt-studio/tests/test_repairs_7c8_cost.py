"""Continuation round 7c8, COST: stage time limits, a must-fix class (owner decision 2026-10-27, session ec5e7910).

7c8 COST skeptic, _B2_FIELD (routing, studio/gi/detect.py; flagged by the ec5 COST agent's pattern scan, older than this
  branch) - the field reader asked of the line under every "separately identifiable" E/M statement let its label run on
  into a run of spaces, and the shared separator then tried every split of the rest of the run: a failing match was cubic
  in the run. An attestation line padded with 111 spaces cost about 0.1 s, so 350 such statements (63,461 characters)
  took the analyze stage past its 60 s limit. A label now never runs on into two spaces (two spaces are the separator, so
  a shorter label always matched first wherever one could), and the line's trailing whitespace is left out of the match
  (a value must follow the separator). The matches are the same; the pins compare with the pattern as it was.

Synthetic data only; no network.
"""
import random
import re
import time

from django.conf import settings
from django.test import SimpleTestCase

from studio import jobs
from studio.gi import detect

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
PIN_SECONDS = 30  # a cost pin's own deadline: well under the stage's, and many times what the repaired code takes
EM_STATEMENT = 'The E/M service was significant and separately identifiable.'

# The pattern before the repair, for the same-matches pins.
OLD_B2_FIELD = re.compile(detect._BOX_Q_LEAD + r"(?P<label>[A-Za-z][\w /'-]{0,30}?)"
                          r"(?!(?<=[A-Za-z0-9])[-–—][A-Za-z0-9])" + detect._BOX_Q_SEP + r"(?=\S)", re.I)


def attestation_note(k, pad=111, word='Attested'):
    """``k`` separately identifiable E/M statements, each with a short line under it: an attestation word padded with
    spaces to the answer line's bound (the line _B2_FIELD is asked of)."""
    unit = EM_STATEMENT + '\n' + word + ' ' * pad + '\n'
    return HEAD + 'Date of service: 2026-10-14\nOffice visit.\n\n' + unit * k


def found(match):
    return None if match is None else (match.span(), match.groupdict())


class B2FieldMatchesAsBeforeTests(SimpleTestCase):
    """The repaired reader finds exactly the matches the pattern found before, on the lines it is asked of."""

    PIECES = ('Attested', 'Notes', 'Same-day', 'E/M', 'Agree', 'Unattested', 'Yes', 'No', 'x', 'a b', '1.', '-',
              'was ', 'the ', ' ', '  ', '   ', '\t', ':', '?', '–', '—', '|', '=', "'", '/', ' ', '\r',
              '☐', '☒', '[x]', '(', ')')

    def test_random_short_lines(self):
        rnd = random.Random(20261027)
        for _ in range(20000):
            line = ''.join(rnd.choice(self.PIECES) for _ in range(rnd.randint(1, 14)))
            for start in range(min(len(line), 3)):
                with self.subTest(line=line, start=start):
                    self.assertEqual(found(detect._b2_field(line, start, len(line))),
                                     found(OLD_B2_FIELD.match(line, start, len(line))))

    def test_field_lines(self):
        for line in ('Notes: Attested', 'Attested - Yes', 'Attestation: pending', 'E/M level: 99214',
                     '- Notes:   Agree   ', 'Notes  Attested', 'Same-day E/M: ☒ Yes ☐ No',
                     'Attested?', 'Attested?   ', 'Attested    x', 'Patient name: Synthetic  ', 'Modifier 25 appended.',
                     '1. Attested  - ', 'Attested  -   ', 'Notes : value', 'Notes  :  value  '):
            with self.subTest(line=line):
                self.assertEqual(found(detect._b2_field(line, 0, len(line))),
                                 found(OLD_B2_FIELD.match(line, 0, len(line))))


class B2FieldCostTests(SimpleTestCase):
    """A run of spaces on the answer line costs the reader no more than its length."""

    def test_padded_lines_are_read_in_linear_time(self):
        lines = ['Attested' + ' ' * 111, 'Attested' + ' ' * 108 + ' x', 'Notes' + ' ' * 112 + '\r']
        started = time.perf_counter()
        for _ in range(40):
            for line in lines:
                detect._b2_field(line, 0, len(line))
        self.assertLess(time.perf_counter() - started, 2.0)  # about 12 s before the repair

    def test_trailing_whitespace_is_left_out_of_the_match(self):
        line = 'Attested' + ' ' * 1000  # longer than any answer line, so only the trim keeps it cheap
        started = time.perf_counter()
        self.assertIsNone(detect._b2_field(line, 0, len(line)))
        self.assertLess(time.perf_counter() - started, 1.0)  # about 3 s with the label rule alone

    def test_the_analyze_stage_reads_350_padded_attestations(self):
        text = attestation_note(350)
        self.assertGreater(len(text), 63_000)
        started = time.perf_counter()
        read = jobs._bounded(jobs._analyze_child, text, {}, settings.MAX_SERVICE_MENTIONS, seconds=PIN_SECONDS)
        self.assertNotIsInstance(read, int)  # read, not refused by the mention cap
        self.assertLess(time.perf_counter() - started, PIN_SECONDS)  # over 60 s before the repair
