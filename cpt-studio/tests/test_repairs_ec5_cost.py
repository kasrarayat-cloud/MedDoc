"""Repair round ec5, cluster COST: stage time and memory limits, a must-fix class (owner decision 2026-10-27, session
ec5e7910). The documented-service reader runs in the assess stage's bounded child after the paid request was sent, so
a document it cannot read within JOB_DEADLINE_SECONDS['assess'] is paid for and never assessed.

new:neg-opening - the opening a negation word may follow (spaces, dashes, bullets, brackets, list labels) was read as
  "(?:[\\s\\-*•(]*(?:<label>)?\\s*)*": a run of those characters was tried in every way of sharing it among the
  repetitions, exponential in the run. A 153-character note - "*", 16 spaces, "Colonoscopy was performed to the
  cecum." - passed the analyze stage in 0.02 s and took the assess stage past its 120 s limit. Each repetition now
  reads one character or one whole label, which reaches the same negation words.
new:heading-date - the same in the words a heading's own date may stand among, "(?:[ \\t,...]+|<word>)*": a 204-character
  note whose procedure line reads "Procedure: Colonoscopy", 30 spaces, "x 2026-10-01" (and one with the run after the
  date) took the assess stage past its limit. Each repetition now reads one mark or one word.
cost-6 (the clause cutter's half; the other half, one cut per sentence, is d3bb7a118) - a run of whitespace was tried as
  a clause cut from each of its characters, and every try read the run to its end: one counted mention and 60,000
  spaces in its sentence took the assess stage 94 s, 120,000 past its limit. A run is now tried from its first two
  characters only, which finds the cuts the try from every character found.
cost-2 / cost-4 (the lesion vocabulary; the analyze stage's count since WIP 8k refuses the findings' own inputs) - no
  count bounds lesion nouns, and pass 3 read every lesion noun's clause: 99,600 bare "AVM" at the paste limit took the
  assess stage to 55 s of its 120 on a quiet host (twice the cost under the load the r1 verifiers saw is past it). A
  lesion's clause is now read only where its reading decides something: a sized lesion "this", "that" or "the" does
  not name, and a lesion about to be recorded.
cost-4 (the instrument vocabulary) - each unnamed "endoscope" read its sentence's anatomy again to tell whether only
  upper GI anatomy names it (in the instrument pass and in passes 2 and 3): 39,000 in one sentence took the assess
  stage to 56 s of its 120. The anatomy is read once per sentence.
new:clause-slice (routing, studio/gi/detect.py; noted by the r1 cost-0 verifier, older than this branch) - routing's
  _clauses_in sliced the document's clause list from the first clause it wanted, copying every later clause at each
  call: a list of 133,000 "A," lines (399,232 characters, each line its own clause) took the analyze stage past its
  60 s limit, and 99,750 "Ab," lines to 41 s. The clauses are read by index from that first one.

Each cost pin runs the stage's own code under a deadline well under the stage's and far over what the repaired code
takes; the reading pins compare with the code before the repair. Synthetic data only; no network.
"""
import bisect
import random
import re
import time
from datetime import date
from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from studio import bounded, jobs
from studio.gi import context as gi_context
from studio.gi import detect, services
from studio.providers import corti
from studio.reference.store import InMemoryReferenceLookup
from studio.types import (EvidenceSpan, NormalizedResponse, PageSpan, ProviderCode, ReferenceSourceInfo, from_jsonable,
                          to_jsonable)

HEAD = 'SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE\n'
DAY = date(2026, 10, 14)
PIN_SECONDS = 30  # a cost pin's own deadline: well under the stage's, and many times what the repaired code takes
FLAGS = re.A | re.I


def assess_child(text, code, phrase, seconds=PIN_SECONDS):
    """The assess stage's child as stage_assess runs it (its deadline aside), with ``code`` selected citing
    ``phrase``: its proposals by code."""
    source = ReferenceSourceInfo(key='cms-pfs-rvu26d', kind='cms-pfs', publisher='CMS', title='PFS', release='RVU26D',
                                 url='', sha256='', effective_start='2026-01-01', effective_end='2026-12-31',
                                 license_note='', scope_note='')
    reference = InMemoryReferenceLookup([source], {source.key: {(code, ''): {
        'status': 'A', 'global_days': '000', 'mult_proc': '2', 'endo_base': None, 'pctc': '0'}}})
    at = text.index(phrase)
    evidence = (EvidenceSpan(0, at, at + len(phrase), phrase, True),)
    normalized = NormalizedResponse('corti', corti.ADAPTER_VERSION, codes=(
        ProviderCode(role='selected', system='cpt', code=code, display='UNVERIFIED', evidence=evidence, index=0),))
    facts = {name: from_jsonable(type(fact), to_jsonable(fact)) for name, fact in gi_context.extract_context(text).items()}
    detect._analysis.cache_clear()
    _, result = bounded.run_bounded(
        jobs._assess_child, text, DAY, (PageSpan(1, 0, len(text)),), facts, normalized, reference, 'succeeded', 'ok', (),
        seconds=seconds, memory_bytes=settings.ASSESS_MEMORY_BYTES)
    return {p.code: p for p in result.proposals}


def build_bounded(text, seconds=PIN_SECONDS):
    """The documented-service inventory of ``text``, read in a bounded child as the assess stage reads it."""
    return bounded.run_bounded(_inventory, text, seconds=seconds, memory_bytes=settings.ASSESS_MEMORY_BYTES)


def _inventory(text):
    inv = services.build(text, service_date=DAY, routing=detect.route(text, DAY),
                         context_facts=gi_context.extract_context(text))
    return ([(s.family, s.status) for s in inv.services],
            sorted((s.family, a.kind, a.status) for s in inv.services for a in s.acts), len(inv.problems))


# --- new:neg-opening -----------------------------------------------------------------------------------------------

OLD_NEG_OPENING = r'^(?:[\s\-*•(]*(?:[A-Z]{1,3}\d{1,2}|\d{1,2}[.)])?\s*)*'  # as shipped before the repair


def bulleted(spaces):
    return HEAD + 'Date of service: 2026-10-14\n*' + ' ' * spaces + 'Colonoscopy was performed to the cecum.\n'


class NegationOpeningTests(SimpleTestCase):
    def test_a_bullet_and_a_run_of_spaces_are_read_within_the_assess_limit(self):
        """The finding's input (153 characters) and a longer run: the assess stage's child reads them in time."""
        for spaces in (16, 60):
            with self.subTest(spaces=spaces):
                started = time.perf_counter()
                proposals = assess_child(bulleted(spaces), '45378', 'Colonoscopy was performed')
                self.assertLess(time.perf_counter() - started, PIN_SECONDS)
                self.assertIn('45378', proposals)

    def test_a_dash_rule_run_into_the_sentence_is_read_within_the_limit(self):
        text = HEAD + 'Date of service: 2026-10-14\n' + '- ' * 40 + 'Colonoscopy was performed to the cecum.\n'
        services_read, _, _ = build_bounded(text)
        self.assertEqual(services_read, [('gi.colonoscopy', 'performed')])

    def test_every_opening_reaches_the_negation_word_it_reached_before(self):
        """The repaired opening against the shipped one, match by match (spans included: NEG_LEAD's end is read)."""
        tails = {'lead': services.NEG_LEAD.pattern[len(services.NEG_OPENING):],
                 'other': services.NEG_OTHER.pattern[len(services.NEG_OPENING):]}
        openings = ['', ' ', '- ', '* ', '• ', '(', '(1) ', '1. ', '12) ', '2.', 'A1 ', 'a1 ', 'AB12 ', 'ABC1 ',
                    'ABCD1 ', 'A12. ', 'A123. ', 'A1234) ', 'A12345. ', 'A1. ', 'A12', 'A1B2 ', '123. ', 'no1 ',
                    'NO1 ', '1)2) ', '- 3. ', '\t*\t', '((', '-- A1 (2) ']
        words = ['no biopsy was taken', 'No other biopsies were taken', 'none', 'nor', 'neither polyp',
                 'without biopsy', 'there was no polyp', 'There were  no other lesions', 'no tissue was sampled beyond '
                 'the three containers', 'nothing', 'Biopsies were taken', 'noted', 'no1', '.no', 'x no']
        checked = 0
        for opening in openings:
            for word in words:
                for key, tail in tails.items():
                    old = re.compile(OLD_NEG_OPENING + tail, FLAGS).match(opening + word)
                    new = (services.NEG_LEAD if key == 'lead' else services.NEG_OTHER).match(opening + word)
                    checked += 1
                    with self.subTest(text=opening + word, pattern=key):
                        self.assertEqual(old and old.span(), new and new.span())
        self.assertGreater(checked, 800)

    def test_negated_and_performed_statements_after_an_opening_read_as_before(self):
        """The control: list labels and bullets before a negation still negate; a performance still reads done."""
        for line, status in (('- No biopsies were taken.', 'negated'), ('A1 No biopsies were taken.', 'negated'),
                             ('2) No biopsies were taken.', 'negated'), ('* Biopsies were taken.', 'performed'),
                             ('(1) Biopsies were taken.', 'performed')):
            text = HEAD + 'Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope was advanced to the ' \
                'cecum.\n' + line + '\n'
            with self.subTest(line=line):
                self.assertIn(('gi.colonoscopy', 'biopsy', status), build_bounded(text)[1])


# --- new:heading-date ----------------------------------------------------------------------------------------------

OLD_COMPANION_MARKS = r'(?:[ \t,:\-–—(/]+|'  # as shipped before the repair: a run of marks per repetition
OLD_AFTER_MARKS = r'(?:[ \t,:\-–—)]+|'


def heading_line(line):
    return HEAD + 'Date of service: 2026-10-14\n' + line + '\nThe colonoscope was advanced to the cecum.\n'


class HeadingDateTests(SimpleTestCase):
    def test_a_run_of_spaces_beside_a_headings_date_is_read_within_the_assess_limit(self):
        for line in ('Procedure: Colonoscopy' + ' ' * 30 + 'x 2026-10-01',
                     'Procedure: Colonoscopy on day 2026-10-01' + ' ' * 30 + 'x',
                     'Colonoscopy' + ' ' * 30 + 'x 2026-10-01:'):  # a bare service heading (parts)
            with self.subTest(line=line):
                started = time.perf_counter()
                proposals = assess_child(heading_line(line), '45378', 'The colonoscope was advanced')
                self.assertLess(time.perf_counter() - started, PIN_SECONDS)
                self.assertIn('45378', proposals)

    def test_the_date_patterns_answer_as_they_did(self):
        before_old = re.compile(services._NAMED + services._DATE_COMPANIONS.replace(r'(?:[ \t,:\-–—(/]|',
                                                                                    OLD_COMPANION_MARKS) + r'*\Z', FLAGS)
        after_old = re.compile(services.HEADING_DATE_AFTER.pattern.replace(r'(?:[ \t,:\-–—)]|', OLD_AFTER_MARKS),
                               FLAGS)
        self.assertNotEqual(before_old.pattern, services.HEADING_DATE_BEFORE.pattern)
        self.assertNotEqual(after_old.pattern, services.HEADING_DATE_AFTER.pattern)
        labels = ['Prior colonoscopy (outside facility, ', 'Colonoscopy report (', 'Outside report reviewed (',
                  'Colonoscopy, most recent: ', 'Colonoscopy -  ', 'EGD on ', 'EGD on day ', 'Last EGD ', 'Procedure: ',
                  'Colonoscopy  history of  ', 'Colonoscopy x ', 'Findings, the ', 'Colonoscopy \u2013 an ', '']
        afters = [' colonoscopy', ', a colonoscopy', ') EGD report', ' - the findings', '  x', ' (outside)', '',
                  ' :: notes', ' an EGD', ' the', ', ']
        for label in labels:
            with self.subTest(label=label):
                self.assertEqual(bool(before_old.search(label)), bool(services.HEADING_DATE_BEFORE.search(label)))
        for after in afters:
            with self.subTest(after=after):
                self.assertEqual(bool(after_old.match(after)), bool(services.HEADING_DATE_AFTER.match(after)))

    def test_a_headings_own_date_still_times_it(self):
        """The control: a heading dated before the service date is an earlier one, a heading of today's date today's."""
        for line, kind in (('Colonoscopy report (2023-05-02):', 'earlier'), ('Colonoscopy (2016):', 'earlier'),
                           ('Colonoscopy 2026-10-14:', 'today'), ('Colonoscopy report:', '')):
            text = heading_line(line)
            ls = text.index(line)
            dates = gi_context.find_dates(text)
            with self.subTest(line=line):
                self.assertEqual(services._heading_time(text, ls, ls + len(line), DAY, dates,
                                                        [d.start for d in dates]), kind)


# --- cost-6: a run of whitespace is tried as a clause cut from its first two characters only ----------------------

def shipped_clauses(text, start, end):
    """The clause cutter before the repair: _CLAUSE_CUT tried from every character of [start, end), with the EXCL
    cluster's own-time rule as it stood on the integrated tree (ec5 integration: the two repairs met in clauses(); the
    own_time cut is made only after an act predicate stated since the last cut)."""
    out, pos = [], start
    stated, scanned = False, start
    for m in services._CLAUSE_CUT.finditer(text, start, end):
        if m.lastgroup == 'own_time':
            if not stated:
                lo = max(pos, scanned - 60)
                stated = bool(services.ACT_VERB.search(text, lo, m.start())
                              or services.BARE_PARTICIPLE.search(text, lo, m.start()))
                scanned = m.start()
            if not stated:
                continue
        seg = services._trim(text, pos, m.start())
        if seg:
            out.append(seg)
        pos = m.end()
        stated, scanned = False, pos
    seg = services._trim(text, pos, end)
    if seg:
        out.append(seg)
    return out or [(start, end)]


def one_run(spaces):
    return HEAD + 'Date of service: 2026-10-14\nColonoscopy was performed with mucosa' + ' ' * spaces + 'pink.\n'


class ClauseCutTests(SimpleTestCase):
    def test_one_run_of_whitespace_is_cut_in_linear_time(self):
        """20,000 spaces in one clause took about 9 s to cut before the repair (the time grew fourfold per doubling)."""
        text = 'Colonoscopy was performed with mucosa' + ' ' * 20_000 + 'pink.'
        started = time.perf_counter()
        self.assertEqual(services.clauses(text, 0, len(text)), [(0, len(text))])
        self.assertLess(time.perf_counter() - started, 1.0)

    def test_a_note_with_a_long_run_is_assessed_within_the_limit(self):
        """One counted mention and a run of 120,000 spaces in its sentence overran the assess stage."""
        started = time.perf_counter()
        proposals = assess_child(one_run(120_000), '45378', 'Colonoscopy was performed')
        self.assertLess(time.perf_counter() - started, PIN_SECONDS)
        self.assertIn('45378', proposals)

    def test_the_cuts_are_the_ones_a_try_from_every_character_found(self):
        texts = ['Biopsies were obtained and dilation was not performed',
                 'A polyp was seen at 30  and the polyp was not removed',  # a digit before a run: cut at its second
                 'A polyp was seen at 30 and the polyp was not removed',  # one space after a digit: no cut
                 'A polyp was seen at 3.   and the polyp was not removed',
                 'The polyp was removed;   biopsies were taken, but  the clip was not placed',
                 'Snare polypectomy was done,   while the patient was sedated',
                 'Tattoo was placed \t but\n\nbiopsies were not taken',
                 'The colonoscope was advanced\t\tand was not withdrawn, and it was then removed',
                 'mucosa' + ' ' * 50 + 'pink;' + ' ' * 7 + 'and the ring was not dilated',
                 'x ,  the polyp was removed', '  and the polyp was not seen  ', ';;  ,,', '',
                 # the own-time cut (EXCL, negtime-4) after an act predicate, and its absence before one
                 'Cold forceps biopsies were obtained from the antrum   and will be sent to pathology',
                 'Biopsy and polypectomy will be performed  and repeat EGD is planned',
                 'The polyp was removed and   dilation was deferred, and the clip was placed and we will follow up']
        rnd = random.Random(1027)
        tokens = [' ', '  ', '\t', '\n', ';', ',', '.', '3', '30', 'and', 'And', 'but', 'whereas', 'although',
                  'while', 'was', 'were', 'not', "n't", 'the', 'it', 'they', 'two', 'had', 'polyp', 'x',
                  'will', 'removed', 'deferred', 'planned', 'obtained', 'is']
        for _ in range(1500):
            texts.append(''.join(rnd.choice(tokens) + rnd.choice(['', ' ', '  ', '\t'])
                                 for _ in range(rnd.randint(1, 30))))
        checked = 0
        for text in texts:
            windows = {(0, len(text))} | {tuple(sorted((rnd.randint(0, len(text)), rnd.randint(0, len(text)))))
                                          for _ in range(3)}
            for start, end in windows:
                checked += 1
                with self.subTest(text=text, start=start, end=end):
                    self.assertEqual(services.clauses(text, start, end), shipped_clauses(text, start, end))
        self.assertGreater(checked, 4000)


# --- cost-2 / cost-4: a lesion's clause is read only where its reading decides something --------------------------

def lesion_lines(lines, unit='AVM', per_line=300):
    line = ' '.join([unit] * per_line) + '.'
    return (HEAD + 'Date of service: 2026-10-14\nColonoscopy was performed to the cecum.\n\n'
            + '\n'.join([line] * lines) + '\n')


LESION_NOTE = (HEAD + 'Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope was advanced to the cecum.\n'
               'A 6 mm sessile polyp in the sigmoid colon was removed with a cold snare (jar A).\n'
               'The 6 mm polyp was retrieved.\n'
               'A 4 mm polyp in the rectum was not removed.\n'
               'Two diminutive polyps in the ascending colon were removed with cold forceps (jar B).\n'
               'No polyps were seen in the transverse colon.\n'
               'A 10 mm polyp in the cecum was removed in 2023.\n'
               'The 4 mm polyp was biopsied and the site was tattooed.\n'
               'An AVM in the cecum was treated with argon plasma coagulation.\n'
               'Several AVMs, polyps and an ulcer were seen in the descending colon, the ulcer was biopsied.\n')


class LesionReadTests(SimpleTestCase):
    def reads(self, text):
        calls = []
        real = services.read_clause

        def counted(*args, **kwargs):
            calls.append(args[2])
            return real(*args, **kwargs)

        with mock.patch.object(services, 'read_clause', counted):
            inv = services.build(text, service_date=DAY, routing=detect.route(text, DAY),
                                 context_facts=gi_context.extract_context(text))
        return inv, len(calls)

    def test_bare_lesion_nouns_are_not_read_one_by_one(self):
        """20 lines of 300 bare "AVM": each was read (6,000 reads); none decides anything."""
        inv, reads = self.reads(lesion_lines(20))
        self.assertLess(reads, 20)
        self.assertEqual([(s.family, s.status) for s in inv.services], [('gi.colonoscopy', 'performed')])

    def test_a_note_of_lesion_nouns_at_the_paste_limit_is_assessed_in_time(self):
        """99,600 bare "AVM" (398,868 characters): 55 s of the assess stage's 120 before, on a quiet host."""
        text = lesion_lines(332)
        self.assertLessEqual(len(text), settings.MAX_PASTE_CHARS)
        started = time.perf_counter()
        proposals = assess_child(text, '45378', 'Colonoscopy was performed')
        self.assertLess(time.perf_counter() - started, PIN_SECONDS)
        self.assertIn('45378', proposals)

    def test_sized_denied_dated_and_named_lesions_read_as_before(self):
        """The control (its inventory as the reader gave it before the repair): sized lesions, a denied one, one of
        another time, one "the" names again, specimen labels, and the acts tied to them."""
        inv, _ = self.reads(LESION_NOTE)
        self.assertEqual([(l.id, l.noun, l.size, l.anatomy, l.specimen, l.morphology)
                          for s in inv.services for l in s.lesions],
                         [('S1-L1', 'polyp', '6 mm', 'sigmoid colon', 'A', 'sessile'),
                          ('S1-L2', 'polyps', '', 'ascending colon', 'B', 'diminutive'),
                          ('S1-L3', 'avm', '', 'cecum', '', ''), ('S1-L4', 'avms', '', 'descending colon', '', ''),
                          ('S1-L5', 'ulcer', '', 'descending colon', '', '')])
        # gi3 inventory, R3: "The 4 mm polyp was biopsied and the site was tattooed" names the rectal 4 mm polyp, which
        # the reader does not record (its removal is denied) - never the ascending colon's diminutive polyps (S1-L2),
        # which this pin had both acts bound to (the biopsy merged into their forceps removal). Both now stand on their
        # own, bound to no lesion.
        self.assertEqual(sorted((a.kind, a.status, a.lesion, a.evidence[0].start) for s in inv.services for a in s.acts),
                         [('ablation', 'performed', 'S1-L3', 545), ('biopsy', 'performed', '', 490),
                          ('biopsy', 'performed', 'S1-L2', 312), ('biopsy', 'performed', 'S1-L5', 677),
                          ('snare', 'performed', 'S1-L1', 157), ('tattoo', 'performed', '', 522)])
        self.assertEqual(inv.problems, ())

    def test_lesions_past_the_services_cap_are_still_a_recorded_problem(self):
        """A sized lesion is read to be recorded, so the 61st is still the recorded cap problem, never dropped."""
        text = (HEAD + 'Date of service: 2026-10-14\nColonoscopy report\nThe colonoscope was advanced to the cecum.\n'
                + ''.join(f'A {n} mm polyp in the sigmoid colon was removed with a cold snare.\n' for n in range(1, 63)))
        inv, _ = self.reads(text)
        self.assertEqual(len(inv.services[0].lesions), services.MAX_LESIONS_PER_SERVICE)
        self.assertIn(f'More than {services.MAX_LESIONS_PER_SERVICE} lesions are documented for one service; the rest '
                      'were not inventoried.', inv.problems)


# --- cost-4: an unnamed endoscope's anatomy is read once per sentence ----------------------------------------------

def endoscopes(n, tail=' was advanced to the stomach and duodenum.'):
    return HEAD + 'Date of service: 2026-10-14\n' + ' '.join(['endoscope'] * n) + tail + '\n'


class UnnamedEndoscopeTests(SimpleTestCase):
    def anatomy_reads(self, text):
        calls = []
        real = services._upper_only

        def counted(*args):
            calls.append(args[1:])
            return real(*args)

        with mock.patch.object(services, '_upper_only', counted):
            inv = services.build(text, service_date=DAY, routing=detect.route(text, DAY),
                                 context_facts=gi_context.extract_context(text))
        return inv, calls

    def test_the_anatomy_of_a_sentence_of_unnamed_endoscopes_is_read_once_a_pass(self):
        inv, calls = self.anatomy_reads(endoscopes(2000))
        self.assertLessEqual(len(calls), 3)  # the instrument pass, pass 2 and pass 3 (4,000 before)

    def test_a_sentence_of_unnamed_endoscopes_is_assessed_within_the_limit(self):
        """39,000 "endoscope" in one sentence (390,138 characters): 56 s of the assess stage's 120 before."""
        started = time.perf_counter()
        proposals = assess_child(endoscopes(39_000), '43235', 'endoscope')
        self.assertLess(time.perf_counter() - started, PIN_SECONDS)
        self.assertIn('43235', proposals)

    def test_an_unnamed_endoscope_is_named_by_its_sentences_anatomy_as_before(self):
        """The control: upper anatomy alone names the EGD; lower or no anatomy names nothing."""
        for text, expected in ((HEAD + 'Date of service: 2026-10-14\nThe endoscope was advanced to the second portion of '
                                'the duodenum and the stomach was examined.\n', [('gi.egd', 'performed')]),
                               (HEAD + 'Date of service: 2026-10-14\nThe endoscope was advanced to the cecum.\n', []),
                               (HEAD + 'Date of service: 2026-10-14\nThe endoscope was cleaned.\n', [])):
            inv, _ = self.anatomy_reads(text)
            with self.subTest(text=text[len(HEAD):80]):
                self.assertEqual([(s.family, s.status) for s in inv.services if s.family != 'gi.office_em'], expected)


# --- new:clause-slice: routing reads a window's clauses by index -----------------------------------------------------

def shipped_clauses_in(an, s, e):
    """Routing's _clauses_in before the repair."""
    clauses = an.lay.clauses
    found = []
    for c in clauses[bisect.bisect_left(clauses, (s, -1)):]:
        if c[0] >= e:
            break
        if c[1] <= e:
            found.append(c)
    return found


class _CountedClauses:
    """A clause list that counts the clauses it hands out, one by one or in slices."""

    def __init__(self, items):
        self.items, self.handed = items, 0

    def __len__(self):
        return len(self.items)

    def __getitem__(self, key):
        got = self.items[key]
        self.handed += len(got) if isinstance(key, slice) else 1
        return got


class _Analysis:
    def __init__(self, clauses):
        self.lay = type('Lay', (), {'clauses': clauses})()


def comma_rows(lines):
    rows = '\n'.join('ABCDEFGH'[i % 8] + ',' for i in range(lines))
    return (HEAD + 'UPPER ENDOSCOPY REPORT\nDate of service: 2026-10-14\nEsophagogastroduodenoscopy was performed to '
            'the second portion of the duodenum.\n\nGrid:\n' + rows + '\nand nothing else of note.\n')


class RoutingClauseWindowTests(SimpleTestCase):
    def test_a_window_hands_out_only_its_own_clauses(self):
        clauses = _CountedClauses(tuple((3 * i, 3 * i + 2) for i in range(100_000)))
        an = _Analysis(clauses)
        for i in range(1000):
            detect._clauses_in(an, 3 * i, 3 * i + 7)
        # the bisection's probes and the window's own clauses; about 100 million before (every later clause, each call)
        self.assertLess(clauses.handed, 50_000)

    def test_the_clauses_are_the_ones_the_slice_found(self):
        rnd = random.Random(1027)
        for _ in range(300):
            starts = sorted(rnd.sample(range(5000), rnd.randint(0, 60)))
            clauses = tuple((a, a + rnd.randint(1, 120)) for a in starts)
            an = _Analysis(clauses)
            for _ in range(10):
                s, e = sorted((rnd.randint(0, 5200), rnd.randint(0, 5200)))
                with self.subTest(s=s, e=e):
                    self.assertEqual(detect._clauses_in(an, s, e), shipped_clauses_in(an, s, e))

    def test_a_long_list_of_comma_rows_is_routed_within_the_analyze_limit(self):
        """133,000 "A," lines at the paste limit: the analyze stage's child, under the stage's own limits."""
        text = comma_rows(133_000)
        self.assertLessEqual(len(text), settings.MAX_PASTE_CHARS)
        detect._analysis.cache_clear()
        facts, service_date, data = bounded.run_bounded(
            jobs._analyze_child, text, {}, settings.MAX_SERVICE_MENTIONS,
            seconds=settings.JOB_DEADLINE_SECONDS['analyze'], memory_bytes=settings.BOUNDED_MEMORY_BYTES)
        self.assertEqual(service_date, DAY)
        self.assertIn('gi.egd', [f['family'] for f in data['findings']])
