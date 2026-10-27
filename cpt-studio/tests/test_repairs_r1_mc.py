"""Refutation r1 repairs, cluster MC: cost and bounds of the documented-service reader (studio/gi/services.py) and of
the analyze stage's bound on it. Stage time and memory limits are a must-fix class (owner, 2026-10-25); where a cost is
inherent in the input it is met by a documented bound that refuses or holds, never truncates (interpretation 7).

cost-6 - every counted service mention, and every instrument, cut its whole sentence into clauses again: 299 mentions
  at the head of one unpunctuated 196,000-character sentence took 13 s, and with a few long runs of spaces in that
  sentence a 4,880-character note overran the assess stage. A sentence is cut into clauses once and every mention read
  in it shares the cut.
cost-2 (per read) - every read of a mention scanned its row window for a "[X] Performed [ ] Not performed" pair even
  on a row without a bracket, most of a read's cost: the scan now runs only on a row with one.

The cost pins count the work the reader does (characters cut into clauses, row scans), so a loaded host can neither
fail them nor pass the cost coming back. Synthetic data only; no network.
"""
from datetime import date
from unittest import mock

from django.test import SimpleTestCase

from studio.gi import context as gi_context
from studio.gi import detect, services

DAY = date(2026, 10, 14)
HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n\n'
PROSE = ('the mucosa of the examined segment appeared pink with a normal vascular pattern and the folds were '
         'unremarkable throughout while the lumen remained patent and the patient remained comfortable with stable '
         'vital signs and adequate oxygen saturation for the whole examination as recorded by the nursing staff ')


def prose(chars):
    return (PROSE * (chars // len(PROSE) + 1))[:chars]


def inventory(text, day=DAY):
    return services.build(text, service_date=day, routing=detect.route(text, day),
                          context_facts=gi_context.extract_context(text))


def summary(inv):
    return ([(s.family, s.status) for s in inv.services],
            sorted((s.family, a.kind, a.status) for s in inv.services for a in s.acts))


class _Counting:
    """A compiled pattern's stand-in that counts the scans made with it and the characters they cover."""

    def __init__(self, pattern):
        self.pattern, self.scans, self.chars = pattern, 0, 0

    def finditer(self, text, pos=0, endpos=None):
        end = len(text) if endpos is None else min(endpos, len(text))
        self.scans += 1
        self.chars += max(0, end - pos)
        return self.pattern.finditer(text, pos, end)

    def __getattr__(self, name):
        return getattr(self.pattern, name)


def clause_work(text, day=DAY):
    """The inventory of ``text`` and the characters the reader cut into clauses to build it."""
    routing, facts = detect.route(text, day), gi_context.extract_context(text)
    calls = []
    real = services.clauses

    def counted(t, start, end):
        calls.append(end - start)
        return real(t, start, end)

    with mock.patch.object(services, 'clauses', counted):
        inv = services.build(text, service_date=day, routing=routing, context_facts=facts)
    return inv, sum(calls)


# --- cost-6: a sentence is cut into clauses once -------------------------------------------------------------------

def egd_tail(chars, names=299, name='EGD'):
    """The finding's shape: ``names`` counted mentions at the head of one unpunctuated sentence of about ``chars``."""
    return HEAD + ' '.join([name] * names) + ' and ' + prose(chars) + '\n'


def scope_run(chars, word='colonoscope'):
    """An instrument named again and again through one unpunctuated sentence (read over the whole sentence)."""
    unit = f'the {word} was advanced and '
    return HEAD + f'The {word} was advanced and ' + (unit * (chars // len(unit) + 1))[:chars] + '\n'


class ClausesOncePerSentenceTests(SimpleTestCase):
    def test_the_mentions_of_one_long_sentence_cut_it_once(self):
        """The finding's input: before the repair the 51,269-character note was cut 301 times (15.4 million
        characters); the reader's whole document is now cut a few times at most."""
        for text in (egd_tail(50_000), egd_tail(50_000, names=150, name='upper endoscopy'),
                     egd_tail(20_000, names=60, name='EGD.') + 'Biopsies were taken from the antrum.\n'):
            inv, cut = clause_work(text)
            with self.subTest(text=text[len(HEAD):40]):
                self.assertLess(cut, 4 * len(text))
                self.assertIn(('gi.egd', 'uncertain'), summary(inv)[0])

    def test_the_instruments_of_one_long_sentence_cut_it_once(self):
        """'The colonoscope was advanced and the colonoscope ...': each instrument cut the whole sentence again
        (40,000 characters: 1,212 cuts, 48 million characters)."""
        for text in (scope_run(40_000), scope_run(30_000, 'gastroscope')):
            inv, cut = clause_work(text)
            with self.subTest(text=text[len(HEAD):30]):
                self.assertLess(cut, 4 * len(text))
                self.assertEqual(len(inv.services), 1)
                self.assertEqual(inv.services[0].status, 'performed')

    def test_names_and_instruments_in_many_short_sentences_read_as_before(self):
        """The control: short sentences are cut once each, as before, and read as they did."""
        text = HEAD + ('Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope was advanced to the cecum. '
                       'A 6 mm polyp in the rectum was removed with a cold snare. Biopsies were taken from the '
                       'sigmoid colon, but no tattoo was placed.\n')
        inv, cut = clause_work(text)
        self.assertLess(cut, 4 * len(text))
        self.assertEqual(summary(inv), ([('gi.colonoscopy', 'performed')],
                                        [('gi.colonoscopy', 'biopsy', 'performed'),
                                         ('gi.colonoscopy', 'snare', 'performed'),
                                         ('gi.colonoscopy', 'tattoo', 'negated')]))


# --- cost-2 (per read): the row scan for a performed / not-performed pair runs only on a row with a bracket --------

class BoxRowScanTests(SimpleTestCase):
    def scans(self, text):
        counting = _Counting(services.BOX_ROW)
        with mock.patch.object(services, 'BOX_ROW', counting):
            inv = inventory(text)
        return inv, counting

    def test_a_row_without_a_bracket_is_never_scanned_for_a_pair(self):
        text = HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum. ' + 'A polyp was seen. ' * 40
        text += '\n'
        inv, counting = self.scans(text)
        self.assertEqual(counting.scans, 0)
        self.assertEqual(summary(inv)[0], [('gi.colonoscopy', 'performed')])

    def test_a_row_with_a_bracket_is_still_read_for_its_pair(self):
        for row, status in (('Cold snare polypectomy [X] Performed [ ] Not performed', 'performed'),
                            ('Cold snare polypectomy [ ] Performed [X] Not performed', 'negated'),
                            ('Cold snare polypectomy: [x] yes [ ] no', 'performed')):
            text = HEAD + 'Colonoscopy report\nThe colonoscope was advanced to the cecum.\n' + row + '\n'
            inv, counting = self.scans(text)
            with self.subTest(row=row):
                self.assertGreater(counting.scans, 0)
                self.assertIn(('gi.colonoscopy', 'snare', status), summary(inv)[1])
