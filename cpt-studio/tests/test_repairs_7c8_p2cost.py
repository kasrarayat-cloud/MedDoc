"""Refutation phase 2 of the GI core, COST (stage time limits, a must-fix class; owner decision 2026-10-27).

cost2:2 (routing, studio/gi/detect.py; pre-existing at 057a7d398) - the typed done-question readers
  (_B3_SERVICE_ANSWERED_NO, _PERFORMED_ANSWERED_NO, _BOX_ANSWER_TAIL and checks' named_no) read the shared separator
  _BOX_Q_SEP before a denial. Its three runs of spaces split a run every way when the answer after it was no denial:
  'Colonoscopy performed' and 4,000 spaces (4,254 characters) took the analyze stage past 60 s, cubic in the run. The
  separator is now read once before a denial (_BOX_Q_SEP_ONCE, an atomic group): a denial opens with a letter, so only
  the separator's longest reading can be followed by one, and the group's first reading is its longest. The matches
  are the same; the pins compare with the patterns as they were.
cost2:0 (the documented-service reader, studio/gi/services.py; introduced by FORMATS' row rule 04e07d55d) - _ROW_NOTE,
  the separator of a row's note, was searched from every place in the text after a row's last mark, so a run of
  spaces there was read again from each of its spaces: 'Biopsy [X]' and 120,000 spaces (120,244 characters) took the
  assess stage past 120 s after the request was sent. A match now starts only where a run of spaces does: a start
  inside a run is never the first one.
cost2:1 (studio/gi/services.py; introduced by EXCL's every-opener rule 0e27d1dc9) - _date_owner sliced and searched an
  opener's phrase again for every earlier opener, for every date, for every mention read in the clause (instrument
  words, which no mention cap counts), and a 398,121-character paste took the assess stage past 120 s after the request
  was sent. The last mark, predicate and word before the date answer for every opener at once, and the opener loop's
  answer is read once per date and clause (_other_event_answer); the mention's place only decides whether that answer
  stands. The answers are the same; the pin compares with the function as it was.

Synthetic data only; no network.
"""
import random
import re
import time

from datetime import date

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services
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


# --- cost2:0: a row note's separator --------------------------------------------------------------------------------

OLD_ROW_NOTE = re.compile(r'[ \t]+[-–—][ \t]*|[ \t]*[:;,(][ \t]*')


class RowNoteMatchesAsBeforeTests(SimpleTestCase):
    PIECES = (' ', '  ', '\t', '-', '–', '—', ':', ';', ',', '(', ')', 'No', 'Not', 'referred to', 'x', 'Dr.', '[X]',
              'per', 'Halcyon', '.', '   - ', ' : ')

    def test_random_tails(self):
        rnd = random.Random(20261028)
        for _ in range(30000):
            tail = ''.join(rnd.choice(self.PIECES) for _ in range(rnd.randint(0, 10)))
            with self.subTest(tail=tail):
                self.assertEqual(found(services._ROW_NOTE.search(tail)), found(OLD_ROW_NOTE.search(tail)))


class RowNoteCostTests(SimpleTestCase):
    """A run of spaces after a row's mark costs the reflow no more than its length."""

    @staticmethod
    def padded(k):
        return HEAD + 'Biopsy [X]' + ' ' * k + 'x' + TAIL

    def test_a_padded_row_is_reflowed_in_linear_time(self):
        started = time.process_time()
        services.reflow(self.padded(32000))
        self.assertLess(time.process_time() - started, 2.0)  # about 17 CPU s before the repair (quadratic)

    def test_the_finding_s_paste_is_reflowed_well_inside_the_assess_limit(self):
        started = time.process_time()
        services.reflow(self.padded(120000))  # 120,244 characters: about 220 CPU s before the repair
        self.assertLess(time.process_time() - started, 5.0)


# --- cost2:1: whose date it is, for every opener before it ----------------------------------------------------------

def old_date_owner(text, d, cs, pos, ce=None):
    """services._date_owner as it was at 2fc8cde3d (refutation phase 2's head), for the same-answers pin."""
    head = text[max(0, d.start - 60):d.start]
    if services.BIRTH_LABEL.search(head) or services.STAMP_LABEL.search(head) \
            or (d.precision == 'year' and d.bare and services.CLOCK_TIME.search(head)):
        return 'none'
    if d.precision == 'year' and services.BY_TIME.search(head):
        return 'other'
    lead = services.ATTRIBUTIVE_DATE_LEAD.search(text, max(cs, d.start - 12), d.start)
    noun = services.ATTRIBUTIVE_DATE_HEAD.match(text, d.end) if lead else None
    if noun is not None and not lead.start() <= pos < noun.end():
        return 'other'
    of = services.POSTNOMINAL_DATE.search(text, max(cs, d.start - 40), d.start)
    if of is not None and not of.start() <= pos < d.end:
        return 'other'
    paren = text.rfind('(', max(0, min(cs, d.start - 80)), d.start)
    if paren >= 0 and ')' not in text[paren:d.start] and not paren < pos < d.start \
            and services.OWN_DATE_LEAD.fullmatch(text, paren + 1, d.start) is None:
        return 'other'
    after = None
    for opener in reversed(list(services.OTHER_EVENT.finditer(text, cs, d.start))):
        if opener.start() <= pos < d.start:
            return ''
        phrase = text[opener.end():d.start]
        if re.search(r'[,;:()\n]', phrase):
            return ''
        if opener.group('event') is not None or services.OTHER_EVENT_PREDICATE.search(phrase):
            return 'other'
        if phrase.strip():
            if after is None:
                rest = text[d.end:min(len(text) if ce is None else ce, d.end + services.OTHER_EVENT_REACH)]
                rest = rest[:next((m.start() for m in re.finditer(r'[,;:()\n]', rest)), len(rest))]
                after = bool(services.OTHER_EVENT_PREDICATE.search(rest))
            if after:
                return 'other'
    return ''


def openers2(n):
    """The finding's shape: an event, 44 openers, 26 bare years and 11 instrument words to a clause."""
    unit = 'found ' + 'if ' * 44 + '2019 ' * 26 + 'colonoscope ' * 11 + '; '
    return (HEAD.split('\n')[0] + '\nDate of service: 2026-10-14\nColonoscopy was performed to the cecum.\n\n' + unit * n
            + 'end.\n')


class DateOwnerAnswersAsBeforeTests(SimpleTestCase):
    WORDS = ('after', 'before', 'because', 'since', 'if', 'which', 'who', 'when', 'while', 'although', 'unless',
             'found', 'seen', 'noted', 'held', 'stopped', 'last dose', 'started', 'was', 'were', 'had', 'has',
             'removed', 'placed', 'banded', 'the', 'polypectomy', 'polyp', 'biopsy', 'colonoscopy', 'today', 'by',
             'of', 'born', 'DOB', 'signed', 'at', 'in', 'on', 'a', 'cold', 'snare', ',', ';', ':', '(', ')', '\n', '.',
             '2019', '2025', '10/12/2026', '09/03/2025', 'March 2025', '2026-10-14', '9:15', 'Two', 'were removed')

    def test_random_clauses(self):
        rnd = random.Random(20261028)
        checked = 0
        for _ in range(4000):
            text = ' '.join(rnd.choice(self.WORDS) for _ in range(rnd.randint(2, 24)))
            dates = gi_context.find_dates(text)
            for d in dates:
                for cs in sorted({0, rnd.randint(0, max(0, d.start)), max(0, d.start - 30)}):
                    if cs > d.start:
                        continue
                    for pos in sorted({0, cs, rnd.randint(0, len(text)), d.start, d.end, max(0, d.start - 5)}):
                        for ce in (None, len(text), min(len(text), d.end + rnd.randint(0, 40))):
                            with self.subTest(text=text, date=text[d.start:d.end], cs=cs, pos=pos, ce=ce):
                                self.assertEqual(services._date_owner(text, d, cs, pos, ce),
                                                 old_date_owner(text, d, cs, pos, ce))
                            checked += 1
        self.assertGreater(checked, 10000)

    def test_the_findings_and_controls(self):
        for sentence in ('Two polyps were removed with a cold snare today because the polypectomy in 2025 had been '
                         'incomplete.', 'Biopsies were taken today since 2019.', 'The polyp was removed in 2025 because '
                         'of bleeding.', 'Apixaban held since 10/12/2026 was resumed.', 'After the banding on 09/02/2026 '
                         'failed, two rubber bands were placed today.', 'found ' + 'if ' * 44 + '2019 2019 colonoscope'):
            for d in gi_context.find_dates(sentence):
                for pos in range(0, len(sentence), 3):
                    with self.subTest(sentence=sentence[:40], date=sentence[d.start:d.end], pos=pos):
                        self.assertEqual(services._date_owner(sentence, d, 0, pos, len(sentence)),
                                         old_date_owner(sentence, d, 0, pos, len(sentence)))


class DateOwnerCostTests(SimpleTestCase):
    def test_the_opener_answer_is_read_once_per_date_and_clause(self):
        services._other_event_answer.cache_clear()
        services.build(openers2(20), service_date=date(2026, 10, 14))
        info = services._other_event_answer.cache_info()
        self.assertGreater(info.hits, info.misses)  # each mention read in a clause asks again; only the first reads

    def test_the_finding_s_shape_is_read_in_linear_time(self):
        started = time.process_time()
        services.build(openers2(200), service_date=date(2026, 10, 14))  # 80,541 characters
        self.assertLess(time.process_time() - started, 20.0)  # about 38 CPU s before the repair, about 4 s after

