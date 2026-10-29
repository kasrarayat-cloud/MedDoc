"""Session 7c8d38da, GI round 2, second fix round (cost): the differential round's d-edges edges-1 and d-mustfix DM-1,
one cause and a must-fix of class 2 (stage time limits). Since the fix round's extent repair (722dec88a) the reader of
the procedure lines above a stand-alone service line (studio/gi/sections.py, _declared_services) searched, for every
line of a procedure section, the line's whole soft-wrapped run with each planned, historical or cancelled cue
(_NOT_TODAYS), and, for every service name on such a line, the historical words before the name (cues.HISTORICAL_PRE)
from the run's start and the date over the name's whole item (_ITEM_DATE): quadratic in a run's length. One
132,813-character soft-wrapped procedure paragraph overran the analyze stage's 60 s, and a 71,613-character one a
member's 15 s context request, where the installed tree (2b82889f) read both in under a second.

The reading is unchanged and linear: a run's cues are read once, for its first line that names a service; a name's
historical words from PRE_WORDS words back (routing's own bound, detect.PRE_WORDS: a cues._pre match ends where the
name starts and spans at most a trigger of six words and five fillers); an item's date once for every name in it, the
semicolons that end the item found by bisection.

The cost tests count what the reader is asked to search (no wall clock). The reading tests compare the repaired reader
with the reading as at c076702c7, kept below as the reference, on generated procedure runs and at the bound's edges.
Synthetic data only; pure functions (no database, no provider)."""
import random
import re
import unittest
from unittest import mock

from studio.gi import cues, detect, sections

SYNTHETIC = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
REPORT = SYNTHETIC + 'Colonoscopy Report\nDate of service: 10/14/2026\n\nProcedures:\n'
NARRATIVE = '\n\nColonoscopy\nThe colonoscope was advanced to the cecum and a 6 mm polyp was removed.\n'
# The differential round's lines: no closing punctuation and the next line in lower case, so every line joins one run.
UNNAMED = 'the mucosa looked pink and smooth with a normal vascular pattern and no erosions seen in this segment'
NAMED = 'colonoscopy view with the mucosa pink and smooth with a normal vascular pattern and no erosions'
WORD = re.compile(r'[^\s,]+', re.A)


def report(line: str, n: int) -> str:
    """The lens's shape: a procedure section of ``n`` soft-wrapped lines (one run), then a stand-alone service line
    heading the narrative (edges-1's 'proc-run' and 'proc-run-named')."""
    return REPORT + '\n'.join([line] * n) + '.' + NARRATIVE


class Recorder:
    """A compiled pattern that records each span it is asked to search."""

    def __init__(self, pattern: re.Pattern, spans: list):
        self.pattern, self.spans = pattern, spans

    def search(self, string, pos=0, endpos=None):
        endpos = len(string) if endpos is None else min(endpos, len(string))
        self.spans.append((self.pattern.pattern, pos, endpos))
        return self.pattern.search(string, pos, endpos)


def searched(text: str) -> dict:
    """Every (pattern, pos, endpos) the layout of ``text`` searches with the runs' cues (sections._NOT_TODAYS), the
    names' historical words (cues.HISTORICAL_PRE) and the items' dates (sections._ITEM_DATE)."""
    spans = {'cues': [], 'history': [], 'date': []}
    not_todays = tuple(Recorder(pattern, spans['cues']) for pattern in sections._NOT_TODAYS)
    history = tuple((label, Recorder(pattern, spans['history'])) for label, pattern in cues.HISTORICAL_PRE)
    with mock.patch.object(sections, '_NOT_TODAYS', not_todays), mock.patch.object(cues, 'HISTORICAL_PRE', history), \
            mock.patch.object(sections, '_ITEM_DATE', Recorder(sections._ITEM_DATE, spans['date'])):
        sections.layout.__wrapped__(text)
    return spans


def characters(spans: list) -> int:
    return sum(end - pos for _, pos, end in spans)


class LinearReadingTests(unittest.TestCase):
    """What the reader above a stand-alone service line searches grows with the text, not with its square."""

    def test_a_runs_cues_are_read_once(self):
        for line in (UNNAMED, NAMED):  # a run naming no service, and one naming it on every line
            with self.subTest(line=line[:20]):
                text = report(line, 200)
                spans = searched(text)['cues']
                self.assertEqual(len(spans), len(set(spans)))  # no span searched twice by one pattern
                self.assertLessEqual(characters(spans), len(sections._NOT_TODAYS) * len(text))

    def test_a_names_history_is_read_over_a_bounded_stretch(self):
        text = report(NAMED, 200)
        spans = searched(text)['history']
        self.assertGreaterEqual(len(spans), 200 * len(cues.HISTORICAL_PRE))  # every name of the run is read
        for _, pos, end in spans:  # routing's bound (test_the_bound_is_routings)
            self.assertLessEqual(len(WORD.findall(text, pos, end)), detect.PRE_WORDS)

    def test_an_items_date_is_read_once(self):
        text = report(NAMED, 200)
        spans = searched(text)['date']
        self.assertEqual(len(spans), len(set(spans)))
        self.assertLessEqual(characters(spans), len(text))

    def test_the_search_grows_linearly(self):
        # four times the run, four times the search (sixteen times at c076702c7)
        for line in (UNNAMED, NAMED):
            small, large = (sum(characters(spans) for spans in searched(report(line, n)).values()) for n in (100, 400))
            with self.subTest(line=line[:20]):
                self.assertGreater(small, 0)
                self.assertLess(large, 5 * small)


def whole_run_occasion(text: str, ls: int, le: int, start: int, end: int) -> bool:
    """sections._names_another_occasion as at c076702c7, the reference: the historical words searched from the run's
    start, the item's semicolons found by scanning the run."""
    if any(pattern.search(text, ls, start) for _, pattern in cues.HISTORICAL_PRE):
        return True
    item_start, item_end = text.rfind(';', ls, start), text.find(';', end, le)
    return bool(sections._ITEM_DATE.search(text, ls if item_start < 0 else item_start + 1,
                                           le if item_end < 0 else item_end))


def whole_run_declared(text: str, lines: list, headings: dict, candidates: dict, runs: tuple) -> dict:
    """sections._declared_services as at c076702c7, the reference: every procedure line rereads its run's cues."""
    declared, found, in_procedure = {}, set(), False
    for i in range(max(candidates) + 1):
        if i in candidates:
            declared[i] = frozenset(found)
        if headings[i]:
            in_procedure = headings[i][0] == 'procedure'
        if in_procedure:
            ls, le = lines[i]
            rs, re_ = runs[0][i], runs[1][i]
            if any(pattern.search(text, rs, re_) for pattern in sections._NOT_TODAYS):
                continue
            found |= {family for family, pattern in cues.SERVICE_PATTERNS for m in pattern.finditer(text, ls, le)
                      if not whole_run_occasion(text, rs, re_, m.start(), m.end())}
    return declared


def declared_calls(text: str) -> list:
    """The arguments of each _declared_services call the layout of ``text`` makes."""
    seen, real = [], sections._declared_services

    def spy(*args):
        seen.append(args)
        return real(*args)

    with mock.patch.object(sections, '_declared_services', spy):
        sections.layout.__wrapped__(text)
    return seen


# A generated procedure run: words that put a name at another occasion (each HISTORICAL_PRE trigger, in any case), the
# fillers its patterns let stand between, names, dates and years, semicolons, marks a trigger may follow or not, a few
# run cues, and separators from one blank to stretches of blanks and commas (which are no words; the long stretches are
# TheBoundReadsWhatTheRunReadsTests' own). The pools' shares keep both readings of a name common.
TRIGGERS = ('history of', 'hx of', 'h/o', 's/p', 'status post', 'personal history of', 'prior', 'previous', 'previously',
            'last', 'most recent', 'recent', 'recently', 'remote', 'earlier', 'past', 'index', 'outside', 'Prior',
            'PREVIOUS', 'History  of')
FILLERS = ('a', 'an', 'the', 'her', 'his', 'their', 'normal', 'abnormal', 'incomplete', 'complete', 'screening',
           'surveillance', 'diagnostic', 'therapeutic', 'upper', 'lower', 'gi', 'GI', 'unremarkable', 'routine',
           'elective', 'initial', 'first', 'second', 'and', 'or', 'svc', '2019', '2024')
NAMES = ('colonoscopy', 'Colonoscopy', 'ileocolonoscopy', 'colonoscopies', 'EGD', 'upper endoscopy',
         'upper GI endoscopy', 'esophagogastroduodenoscopy', 'flexible sigmoidoscopy', 'sigmoidoscopy', 'ERCP', 'EUS',
         'enteroscopy', 'gastroscopy')
WORDS = ('mucosa', 'pink', 'with', 'biopsies', 'polyp', 'removed', 'cold', 'snare', 'segment', 'seen', 'view', 'by',
         'Dr.', 'Synthetic', 'tubular', 'adenoma', 'was', 'performed')
DATES = ('2019', '1998', '03/14/2024', '1/2/24', '(2024)', '2024.', '12/1/2019', '2026-10-14')
MARKS = ('(', ')', '-', '/', '(prior', 'x-prior', 'a/prior', 'on', ':')
SEMICOLONS = (';', '; ')
RUN_CUES = ('planned', 'will', 'ago', 'cancelled', 'scheduled', 'last month')
SEPARATORS = (' ',) * 6 + (', ', ' , ', '\t', '  ', ' ' * 30, ', , , ', ',')
POOLS = ((0.2, NAMES), (0.28, TRIGGERS), (0.5, FILLERS), (0.52, DATES), (0.6, MARKS), (0.66, SEMICOLONS),
         (0.665, RUN_CUES), (1.0, WORDS))  # each pool up to its cumulative share


def generated_line(rng: random.Random) -> str:
    pieces = []
    for _ in range(rng.randint(1, 20)):
        r = rng.random()
        pieces.append(rng.choice(next(pool for share, pool in POOLS if r < share)))
    line = pieces[0]
    for piece in pieces[1:]:
        line += rng.choice(SEPARATORS) + piece
    if rng.random() < 0.85:  # most lines go on in lower case: long runs
        line = 'and ' + line
    if rng.random() < 0.08:  # a few end a sentence or an item: the run ends there
        line += rng.choice('.;')
    return line


def generated_report(rng: random.Random) -> str:
    sections_text = []
    for _ in range(rng.randint(1, 3)):
        lines = [generated_line(rng) for _ in range(rng.randint(1, 30))]
        kind = rng.randrange(3)
        if kind == 1 and len(lines) > 1:  # the heading's own line opens the run ("Procedures: EGD; colonoscopy ...")
            heading = 'Procedures: ' + lines.pop(0)
        else:
            heading = 'Procedure performed:' if kind == 2 else 'Procedures:'
        sections_text.append(heading + '\n' + '\n'.join(lines))
        if rng.random() < 0.3:
            sections_text.append('Indications:\nIron deficiency anemia.')
    return REPORT + '\n'.join(sections_text) + '.' + NARRATIVE


class TheReadingIsUnchangedTests(unittest.TestCase):
    """The repaired reader reads every generated procedure run as the whole-run reader of c076702c7 does."""

    def test_generated_runs(self):
        rng = random.Random(20261029)
        names = occasions = bounded = documents = 0
        for _ in range(60):
            text = generated_report(rng)
            for args in declared_calls(text):
                documents += 1
                self.assertEqual(sections._declared_services(*args), whole_run_declared(*args))
                _, lines, headings, candidates, runs = args
                memo, in_procedure = {}, False
                for i in range(max(candidates) + 1):
                    if headings[i]:
                        in_procedure = headings[i][0] == 'procedure'
                    if not in_procedure:
                        continue
                    rs, re_ = runs[0][i], runs[1][i]
                    for _, pattern in cues.SERVICE_PATTERNS:
                        for m in pattern.finditer(text, *lines[i]):
                            got = sections._names_another_occasion(text, rs, re_, m.start(), m.end(), memo)
                            self.assertEqual(got, whole_run_occasion(text, rs, re_, m.start(), m.end()),
                                             (text[rs:m.end()][-300:], m.group(0)))
                            names, occasions = names + 1, occasions + got
                            bounded += len(WORD.findall(text, rs, m.start())) > sections._PRE_WORDS
        # the comparison is not vacuous: many names, both answers, and many read from a bounded start
        self.assertGreaterEqual(documents, 60)
        self.assertGreater(names, 2000)
        self.assertGreater(occasions, 500)
        self.assertGreater(names - occasions, 500)
        self.assertGreater(bounded, 1000)


class TheBoundReadsWhatTheRunReadsTests(unittest.TestCase):
    """The edges of the bound, each read alike by the repaired reader and the reference."""

    NOISE = ' '.join(f'word{n}' for n in range(300))

    def reads(self, text: str, ls: int = 0, le: int = None) -> bool:
        """The reading of the text's last 'colonoscopy' on the run [ls, le) (the whole text by default)."""
        le = len(text) if le is None else le
        start = text.rindex('colonoscopy', ls, le)
        end = start + len('colonoscopy')
        got = sections._names_another_occasion(text, ls, le, start, end, {})
        self.assertEqual(got, whole_run_occasion(text, ls, le, start, end), text[max(ls, start - 200):le])
        return got

    def test_the_longest_history_trigger_far_into_a_run(self):
        # a trigger of three words and three fillers, 300 words after the run's start
        self.assertTrue(self.reads(self.NOISE + ' personal history of the screening upper colonoscopy'))
        self.assertTrue(self.reads(self.NOISE + ' s/p her complete, routine colonoscopy'))
        self.assertTrue(self.reads(self.NOISE + ' most\trecent 2019 colonoscopy'))

    def test_one_filler_too_many_reads_no_history(self):
        self.assertFalse(self.reads(self.NOISE + ' personal history of the routine screening upper colonoscopy'))

    def test_blanks_and_commas_are_no_words(self):
        self.assertTrue(self.reads(self.NOISE + ' prior' + ', ' * 3000 + 'colonoscopy'))
        self.assertTrue(self.reads(self.NOISE + ' prior' + ' ' * 5000 + 'colonoscopy'))
        self.assertTrue(self.reads(self.NOISE + ' prior\n' + ' \t' * 2000 + 'colonoscopy'))

    def test_a_trigger_before_the_run_reads_nothing(self):
        # the run's start bounds the search however many words stand before it
        text = self.NOISE + ' prior\ncolonoscopy with a cold snare'
        self.assertFalse(self.reads(text, ls=text.index('\n') + 1))
        self.assertTrue(self.reads(text))  # the same lines as one run

    def test_what_stands_before_the_trigger(self):
        self.assertTrue(self.reads(self.NOISE + ' (prior colonoscopy'))
        self.assertFalse(self.reads(self.NOISE + ' x-prior colonoscopy'))
        self.assertFalse(self.reads(self.NOISE + ' a/prior colonoscopy'))

    def test_an_items_date_and_its_semicolons(self):
        self.assertTrue(self.reads(self.NOISE + '; EGD; colonoscopy (2019); ERCP'))
        self.assertFalse(self.reads(self.NOISE + ' 2019; EGD; colonoscopy with a cold snare; ERCP 03/14/2024'))
        self.assertTrue(self.reads(self.NOISE + ' 2019 and colonoscopy with a cold snare'))
        # a semicolon outside the run bounds nothing: the item stops at the run's start or end, the date beyond it unread
        text = 'Polyp seen; 2019\n' + self.NOISE + ' colonoscopy'
        self.assertFalse(self.reads(text, ls=text.index('\n') + 1))
        self.assertTrue(self.reads(text))  # the same lines as one run: the year is in the name's item
        text = self.NOISE + ' colonoscopy\n2019; polyp seen'
        self.assertFalse(self.reads(text, le=text.index('\n')))
        self.assertTrue(self.reads(text))

    def test_the_bound_is_routings(self):
        # one bound for every cues._pre reader: routing's (detect._pre_start) and this one never drift apart
        self.assertEqual(sections._PRE_WORDS, detect.PRE_WORDS)
        self.assertEqual((sections._PRE_WORD.pattern, sections._PRE_WORD.flags),
                         (detect._PRE_TOKEN.pattern, detect._PRE_TOKEN.flags))
        for _, pattern in cues.HISTORICAL_PRE:  # the cues._pre shape the bound counts on: anchored where the name starts
            self.assertTrue(pattern.pattern.endswith(r'[\s,]*$'), pattern.pattern)


if __name__ == '__main__':
    unittest.main()
